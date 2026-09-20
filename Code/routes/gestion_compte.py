from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import text
from Code.extensions import db
from Code.models.models import (User, Role, UserRole, Entity, CompetencyEvaluation,
                                TimeAnalysis, default_lang_for)
from Code.security import hash_password, verify_password
from Code.permissions import (can_create_accounts,
                              can_edit_account, current_user, is_admin,
                              is_admin_status, is_champion_status,
                              is_competency_manager_status, is_coordinator_status)

gestion_compte_bp = Blueprint('gestion_compte', __name__, url_prefix='/comptes')


# Les règles de droits vivent dans Code/permissions.py : la page Comptes,
# les paramètres et le partage d'entités s'appuient sur les mêmes.
_current_user = current_user
_is_admin = is_admin
_can_create_accounts = can_create_accounts
_can_edit_account = can_edit_account


def _forbidden(msg_key):
    """Refus sur une soumission de formulaire : retour à la liste avec message."""
    return redirect(url_for('gestion_compte.list_users', tab='list-tab', msg=msg_key))

def _famille(statut):
    """Le palier d'un statut écrit en clair : le libellé varie d'une instance
    à l'autre, le palier non — c'est lui qui filtre et qui colore."""
    if is_admin_status(statut):
        return 'admin'
    if is_coordinator_status(statut):
        return 'coordinateur'
    if is_champion_status(statut):
        return 'champion'
    return 'user'


@gestion_compte_bp.route('/')
def list_users():
    me = _current_user()
    try:
        # Les rôles de l'entité active : ce sont eux qu'on attribue depuis
        # cette page.
        active_entity_id = Entity.get_active_id()
        roles = (Role.query.filter_by(entity_id=active_entity_id).order_by(Role.name).all()
                 if active_entity_id else Role.query.order_by(Role.name).all())

        # Tous les utilisateurs de la base, SANS filtre d'entité : la page
        # Comptes administre les comptes de l'instance entière — filtrer par
        # entité active masquait les comptes sans entité (page « 0 users »
        # dès qu'une entité était sélectionnée).
        users = User.query.order_by(User.first_name, User.last_name).all()

        # Les rôles de chacun en DEUX requêtes : une par utilisateur faisait
        # deux allers en base par ligne de la liste.
        noms = {r.id: r.name for r in Role.query.all()}
        par_user = {}
        pour_le_role = {}
        for ur in UserRole.query.all():
            if ur.role_id in noms:
                par_user.setdefault(ur.user_id, []).append(noms[ur.role_id])
                pour_le_role.setdefault(ur.user_id, []).append(ur.role_id)
        users_with_roles = [{'user': u, 'roles': sorted(par_user.get(u.id, [])),
                             'role_ids': pour_le_role.get(u.id, []),
                             'famille': _famille(u.status)} for u in users]

        familles = {f: sum(1 for x in users_with_roles if x['famille'] == f)
                    for f in ('admin', 'coordinateur', 'champion', 'user')}
        return render_template(
            'gestion_compte_new.html',
            roles=roles,
            users=users,
            users_with_roles=users_with_roles,
            familles=familles,
            is_admin=_is_admin(me),
            can_create_accounts=_can_create_accounts(me),
            current_user_id=(me.id if me else None),
        )

    except Exception:
        import traceback
        traceback.print_exc()
        # Une page vide plutôt qu'une 500 : la liste est le cœur de l'écran,
        # mais le reste (créer, importer) doit rester joignable.
        return render_template(
            'gestion_compte_new.html',
            roles=[], users=[], users_with_roles=[],
            familles={'admin': 0, 'coordinateur': 0, 'champion': 0, 'user': 0},
            is_admin=_is_admin(me),
            can_create_accounts=_can_create_accounts(me),
            current_user_id=(me.id if me else None),
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Ce que chaque palier ouvre — le tableau des droits
# ═══════════════════════════════════════════════════════════════════════════
# L'échelle `user < champion < coordinateur < admin` est la grammaire du
# produit et ne se règle pas. Ce que chaque palier OUVRE, si : une entreprise
# où tout le monde propose n'a pas les mêmes usages qu'une où seul un
# coordinateur touche à la carto.
#
# ⚠️ **Seul un ADMINISTRATEUR écrit ce tableau**, et la colonne `admin` y est
# verrouillée à vrai. Sans ces deux règles, on pourrait se retirer l'accès aux
# Paramètres — c'est-à-dire perdre l'écran depuis lequel on le remettrait. La
# porte se refermerait de l'intérieur, sans poignée.
#
# Le tableau vit sur la page Comptes : c'est là qu'on donne un statut à
# quelqu'un, donc là qu'on doit pouvoir lire ce que ce statut ouvre.

@gestion_compte_bp.route('/droits')
def lire_droits():
    from Code.permissions import DROITS_DEFAUT, PALIERS, droits_effectifs

    me = _current_user()
    if not (_is_admin(me) or _can_create_accounts(me)):
        return jsonify({'error': 'Accès refusé'}), 403
    return jsonify({
        'paliers': list(PALIERS),
        'droits': droits_effectifs(),
        'defaut': {d: dict(v, admin=True) for d, v in DROITS_DEFAUT.items()},
        'modifiable': bool(_is_admin(me)),
    })


@gestion_compte_bp.route('/droits', methods=['POST'])
def ecrire_droits():
    from Code.permissions import droits_effectifs, enregistrer_droits

    me = _current_user()
    if not (_is_admin(me) or _can_create_accounts(me)):
        return jsonify({'error': 'Accès refusé'}), 403
    if not _is_admin(me):
        # ⚠️ Un coordinateur qui pourrait s'attribuer les Paramètres
        # d'administration s'attribuerait la clé IA de l'entreprise. Le tableau
        # se lit à son palier, il ne s'écrit qu'au-dessus.
        return jsonify({'error': 'Seul un administrateur règle les droits'}), 403

    data = request.get_json(silent=True) or {}
    table = data.get('droits')
    if not isinstance(table, dict):
        return jsonify({'error': 'Tableau attendu'}), 400
    enregistrer_droits(table)
    return jsonify({'ok': True, 'droits': droits_effectifs()})

@gestion_compte_bp.route('/create', methods=['POST'])
def create_user():
    if not _can_create_accounts():
        return _forbidden('error_forbidden_create')
    first_name = request.form.get('first_name', '').strip()
    last_name  = request.form.get('last_name',  '').strip()
    email      = request.form.get('email',      '').strip()
    password   = request.form.get('password',   '').strip()
    role_id_raw = request.form.get('role_id',   '').strip()
    status     = request.form.get('status',     'user').strip()
    age_raw    = request.form.get('age',        '').strip()

    # Validation des champs obligatoires
    if not first_name or not last_name:
        return redirect(url_for('gestion_compte.list_users', msg='error_missing_name'))
    if not email:
        return redirect(url_for('gestion_compte.list_users', msg='error_missing_email'))
    if not password or len(password) < 6:
        return redirect(url_for('gestion_compte.list_users', msg='error_missing_password'))
    # Rôle FACULTATIF : un compte peut exister sans rôle (ex. premier admin
    # avant que les rôles de l'entité soient créés).
    if User.query.filter_by(email=email).first():
        return redirect(url_for('gestion_compte.list_users', msg='error_email_exists'))

    # ⚠️ On ne crée pas AU-DESSUS de soi : sans ce contrôle, un compte
    # autorisé à créer des comptes se fabriquait un administrateur — et se
    # donnait par la bande des droits qu'il n'a pas. Le masquage du champ
    # dans la page n'y suffit pas, il ne coûte rien de le contourner.
    from Code.permissions import niveau, niveau_status
    if niveau_status(status) > niveau(_current_user()):
        return redirect(url_for('gestion_compte.list_users', msg='error_status_too_high'))

    try:
        role_id = int(role_id_raw) if role_id_raw else None
    except ValueError:
        role_id = None

    age = int(age_raw) if age_raw else None

    active_entity_id = Entity.get_active_id()
    user = User(
        first_name=first_name,
        last_name=last_name,
        age=age,
        email=email,
        password=hash_password(password),
        status=status,
        lang=default_lang_for(email),
        entity_id=active_entity_id
    )
    db.session.add(user)
    db.session.commit()

    if role_id:
        db.session.add(UserRole(user_id=user.id, role_id=role_id))
        db.session.commit()

    return redirect(url_for('gestion_compte.list_users', msg='created'))

@gestion_compte_bp.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    # Supprimer un compte reste réservé aux administrateurs — y compris le sien.
    if not _is_admin():
        return _forbidden('error_forbidden_edit')
    try:
        # Récupérer l'utilisateur
        user = User.query.get_or_404(user_id)

        print(f"🗑️ Suppression de l'utilisateur: {user.first_name} {user.last_name} (ID: {user_id})")

        # 1. Détacher les entités dont cet user est owner
        Entity.query.filter_by(owner_id=user_id).update({'owner_id': None})

        # 2. Retirer ce user comme manager d'autres users
        User.query.filter_by(manager_id=user_id).update({'manager_id': None})

        # 3. Retirer ce user comme manager dans user_roles (manager par rôle)
        UserRole.query.filter_by(manager_id=user_id).update({'manager_id': None})

        # 4. Supprimer les évaluations de compétences liées (user_id NOT NULL)
        CompetencyEvaluation.query.filter_by(user_id=user_id).delete()

        # 5. Détacher les analyses de temps liées
        TimeAnalysis.query.filter_by(user_id=user_id).update({'user_id': None})

        # 6. Supprimer les rôles assignés
        UserRole.query.filter_by(user_id=user_id).delete()

        # 7. Supprimer l'utilisateur
        db.session.delete(user)
        db.session.commit()
        print(f"   ✅ Utilisateur supprimé")

        return redirect(url_for('gestion_compte.list_users', tab='list-tab', msg='deleted'))
    except Exception as e:
        print(f"❌ Erreur lors de la suppression de l'utilisateur {user_id}: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return f"Erreur lors de la suppression: {str(e)}", 500



@gestion_compte_bp.route('/update/<int:user_id>', methods=['GET', 'POST'])
def update_user(user_id):
    if not _can_edit_account(user_id):
        return _forbidden('error_forbidden_edit')
    user = User.query.get_or_404(user_id)
    # MODIFIÉ: Filtrer les rôles par entité active
    roles = Role.for_active_entity().all()

    if request.method == 'POST':
        form = request.form
        prenom = (form.get('first_name') or '').strip()
        nom    = (form.get('last_name')  or '').strip()
        email  = (form.get('email')      or '').strip()
        if not prenom or not nom:
            return redirect(url_for('gestion_compte.list_users', msg='error_missing_name'))
        if not email:
            return redirect(url_for('gestion_compte.list_users', msg='error_missing_email'))
        if User.query.filter(User.email == email, User.id != user.id).first():
            return redirect(url_for('gestion_compte.list_users', msg='error_email_exists'))

        # Un champ « âge » laissé vide arrive comme '' : tel quel dans une
        # colonne entière, PostgreSQL rejette la requête et TOUTE modification
        # (même un simple nom de famille) repartait en erreur 500.
        age_brut = (form.get('age') or '').strip()
        try:
            age = int(age_brut) if age_brut else None
        except ValueError:
            return redirect(url_for('gestion_compte.list_users', msg='error_invalid_age'))

        user.first_name = prenom
        user.last_name = nom
        user.email = email
        user.age = age
        # Seul un administrateur change un statut : sinon n'importe qui
        # s'auto-promeut depuis l'édition de son propre compte.
        if _is_admin():
            # La colonne fait 20 caractères : un libellé plus long serait tronqué
            # par la base (ou refusé), avec des droits inexpliqués à la clé.
            statut = (form.get('status') or user.status or 'user').strip()
            user.status = statut[:20]

        new_password = form.get('password', '').strip()
        if new_password:
            new_hash = hash_password(new_password)
            user.password = new_hash
            flag_modified(user, 'password')  # force SQLAlchemy à inclure password dans l'UPDATE

        # Mise à jour du rôle — FACULTATIF : vide = « aucun rôle » (le rôle
        # existant est retiré). Exiger un rôle empêchait p.ex. de passer un
        # compte en administrateur avant la création des rôles de l'entité.
        new_role_raw = (form.get('role_id') or '').strip()
        user_role = UserRole.query.filter_by(user_id=user.id).first()
        if new_role_raw:
            try:
                new_role_id = int(new_role_raw)
            except ValueError:
                return redirect(url_for('gestion_compte.list_users', msg='error_missing_role'))
            if user_role:
                user_role.role_id = new_role_id
            else:
                db.session.add(UserRole(user_id=user.id, role_id=new_role_id))
        elif user_role:
            db.session.delete(user_role)

        db.session.add(user)
        try:
            db.session.commit()
        except SQLAlchemyError:
            # Mieux vaut un message dans la page qu'une 500 opaque.
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return redirect(url_for('gestion_compte.list_users', msg='error_update'))
        return redirect(url_for('gestion_compte.list_users', msg='updated'))

    # La modification se fait dans la liste, pas sur une page à part : créer
    # et modifier un compte posent les mêmes questions, elles méritaient le
    # même écran. Un lien direct ouvre donc la fiche par-dessus la liste.
    return redirect(url_for('gestion_compte.list_users', edit=user.id))

@gestion_compte_bp.route('/managers')
def get_managers():
    # MODIFIÉ: Filtrer par entité active
    managers = User.for_active_entity().filter(User.subordinates.any()).all()
    return jsonify([
        {
            "id": m.id,
            "name": f"{m.first_name} {m.last_name}",
            "subordinates": [
                {"id": s.id, "name": f"{s.first_name} {s.last_name}"}
                for s in m.subordinates
            ]
        }
        for m in managers
    ])

@gestion_compte_bp.route('/assign_manager', methods=['POST'])
def assign_manager():
    manager_id = int(request.form['manager_id'])
    multi = request.form.get('multi_select', '0') == '1'

    if multi:
        user_ids = request.form.getlist('user_ids[]')
        for user_id in user_ids:
            user = User.query.get(int(user_id))
            if user:
                user.manager_id = manager_id
    else:
        user_id = request.form.get('user_id')
        if user_id:
            user = User.query.get(int(user_id))
            if user:
                user.manager_id = manager_id


    db.session.commit()

    # Récupérer la nouvelle liste des subordonnés
    subordinates = User.query.filter_by(manager_id=manager_id).all()
    # Retourner en JSON
    return jsonify({
        'status': 'success',
        'subordinates': [
            {'id': s.id, 'name': f"{s.first_name} {s.last_name}"}
            for s in subordinates
        ]
    })


@gestion_compte_bp.route('/remove_collaborator/<int:user_id>', methods=['POST'])
def remove_collaborator(user_id):
    user = User.query.get(user_id)
    if user:
        user.manager_id = None
        db.session.commit()
    return redirect(url_for('gestion_compte.list_users'))

@gestion_compte_bp.route('/users')
def get_all_users():
    # MODIFIÉ: Filtrer par entité active
    users = User.for_active_entity().all()
    return jsonify([
        {'id': u.id, 'name': f"{u.first_name} {u.last_name}"}
        for u in users
    ])

@gestion_compte_bp.route('/manager/<int:manager_id>/subordinates')
def get_subordinates(manager_id):
    manager = User.query.get_or_404(manager_id)
    subordinates = manager.subordinates
    return jsonify({
        'subordinates': [
            {'id': s.id, 'name': f"{s.first_name} {s.last_name}"}
            for s in subordinates
        ]
    })

@gestion_compte_bp.route('/set_password/<int:user_id>', methods=['POST'])
def set_password(user_id):
    if not _can_edit_account(user_id):
        return jsonify({'ok': False, 'error': "Vous ne pouvez modifier que votre propre compte."}), 403
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    new_password = (data.get('password') or '').strip()
    if len(new_password) < 6:
        return jsonify({'ok': False, 'error': 'Le mot de passe doit contenir au moins 6 caractères.'}), 400
    try:
        user.password = hash_password(new_password)
        flag_modified(user, 'password')
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

    # Vérification post-commit : on relit le hash réellement en base pour
    # garantir que la modification a bien été persistée (jamais de faux succès).
    stored = db.session.execute(
        text("SELECT password FROM users WHERE id = :uid"), {"uid": user_id}
    ).scalar()
    if not verify_password(stored, new_password):
        return jsonify({'ok': False,
                        'error': "La modification n'a pas été persistée en base. Contactez l'administrateur."}), 500
    return jsonify({'ok': True})

