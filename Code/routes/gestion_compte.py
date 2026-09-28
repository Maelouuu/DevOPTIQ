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


def _veut_json():
    """La fiche envoie en arrière-plan et le dit (`Accept: application/json`).

    ⚠️ Un envoi classique rechargeait la page sur la moindre erreur : un e-mail
    déjà pris, et tout ce qu'on venait de saisir était perdu. La fiche reste
    désormais ouverte et montre l'erreur SOUS le champ fautif. Le retour par
    redirection est gardé pour tout autre appelant.
    """
    return 'application/json' in (request.headers.get('Accept') or '')


# Le champ que chaque refus désigne : c'est sous lui que la fiche l'écrit.
_CHAMP_EN_CAUSE = {
    'error_missing_name': 'first_name',
    'error_missing_email': 'email',
    'error_email_exists': 'email',
    'error_missing_password': 'password',
    'error_invalid_age': 'age',
    'error_status_too_high': 'status',
    'error_role_unknown': 'roles',
    'error_forbidden_roles': 'roles',
}


def _fin(code, ok=False, http=400):
    if _veut_json():
        return jsonify({'ok': ok, 'code': code,
                        'champ': None if ok else _CHAMP_EN_CAUSE.get(code)}), (200 if ok else http)
    return redirect(url_for('gestion_compte.list_users', msg=code))


def _forbidden(msg_key):
    """Refus sur une soumission de formulaire : retour à la liste avec message."""
    if _veut_json():
        return jsonify({'ok': False, 'code': msg_key, 'champ': None}), 403
    return redirect(url_for('gestion_compte.list_users', tab='list-tab', msg=msg_key))


def _peut_gerer_roles(moi):
    """Donner ou retirer un rôle ouvre ou ferme des cartos : c'est le travail
    de qui règle la page RH, pas de quiconque modifie son propre compte."""
    from Code.permissions import can_access_rh
    return bool(moi and (_is_admin(moi) or can_access_rh(moi)))


def _ids_de(form, cle):
    ids = []
    for brut in form.getlist(cle):
        try:
            ids.append(int(brut))
        except (TypeError, ValueError):
            continue
    return ids


def _appliquer_roles(moi, user, ajout, retrait):
    """Ajoute et retire des rôles PAR PAIRE (compte, rôle). Renvoie un code
    d'erreur, ou None.

    ⚠️ Jamais « remplacer les rôles de la personne par ceux du formulaire ».
    L'ancienne fiche ne portait qu'UN rôle, pris parmi ceux de la carto
    active : pour quelqu'un qui en tenait un sur une autre carto, corriger son
    nom renvoyait un rôle vide — et son rôle était SUPPRIMÉ, avec l'accès à la
    carto qu'il ouvrait. Seul ce que la fiche nomme bouge ; le reste est
    intact, y compris le développeur de compétences posé sur chaque rôle.
    """
    if not ajout and not retrait:
        return None
    if not _peut_gerer_roles(moi):
        return 'error_forbidden_roles'
    # Un administrateur a tous les droits ; les autres n'attribuent que les
    # rôles des cartos qu'ils ouvrent (un rôle ouvre une carto : on ne donne
    # pas accès à ce qu'on ne voit pas soi-même).
    for rid in dict.fromkeys(ajout):
        role = db.session.get(Role, rid)
        if role is None:
            return 'error_role_unknown'
        if not UserRole.query.filter_by(user_id=user.id, role_id=rid).first():
            db.session.add(UserRole(user_id=user.id, role_id=rid))
    for rid in dict.fromkeys(retrait):
        if rid in ajout:
            continue
        if db.session.get(Role, rid) is None:
            return 'error_role_unknown'
        UserRole.query.filter_by(user_id=user.id, role_id=rid).delete()
    return None

def _famille(statut):
    """Le palier d'un statut écrit en clair : le libellé varie d'une instance
    à l'autre, le palier non — c'est lui qui filtre et qui colore."""
    from Code.permissions import famille_statut
    return famille_statut(statut)


@gestion_compte_bp.route('/')
def list_users():
    me = _current_user()
    try:
        roles = Role.query.order_by(Role.name).all()

        # Tous les utilisateurs de la base, SANS filtre d'entité : la page
        # Comptes administre les comptes de l'instance entière — filtrer par
        # entité active masquait les comptes sans entité (page « 0 users »
        # dès qu'une entité était sélectionnée).
        users = User.query.order_by(User.first_name, User.last_name).all()

        # Les rôles de chacun en TROIS requêtes : une par utilisateur faisait
        # deux allers en base par ligne de la liste.
        from Code.role_i18n import nom_affiche
        tous_roles = {r.id: r for r in Role.query.all()}
        cartos = {e.id: e.name for e in Entity.query.all()}
        par_user = {}
        detail = {}
        for ur in UserRole.query.all():
            r = tous_roles.get(ur.role_id)
            if r is None:
                continue
            par_user.setdefault(ur.user_id, []).append(r.name)
            detail.setdefault(ur.user_id, []).append({'id': r.id, 'name': nom_affiche(r)})
        users_with_roles = [{'user': u, 'roles': sorted(par_user.get(u.id, [])),
                             'roles_detail': sorted(detail.get(u.id, []),
                                                    key=lambda x: x['name'].lower()),
                             'famille': _famille(u.status)} for u in users]

        familles = {f: sum(1 for x in users_with_roles if x['famille'] == f)
                    for f in ('admin', 'coordinateur', 'champion', 'user')}

        # Ce que la fiche peut attribuer : les rôles de l'entreprise.
        from Code.permissions import niveau
        catalogue = [{'id': r.id, 'name': nom_affiche(r)}
                     for r in sorted(tous_roles.values(),
                                     key=lambda r: nom_affiche(r).lower())]
        return render_template(
            'gestion_compte_new.html',
            roles=roles,
            users=users,
            users_with_roles=users_with_roles,
            familles=familles,
            is_admin=_is_admin(me),
            can_create_accounts=_can_create_accounts(me),
            current_user_id=(me.id if me else None),
            catalogue_roles=catalogue,
            peut_gerer_roles=_peut_gerer_roles(me),
            mon_niveau=niveau(me) if me else -1,
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
            catalogue_roles=[], peut_gerer_roles=False, mon_niveau=-1,
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
        return _fin('error_missing_name')
    if not email:
        return _fin('error_missing_email')
    if not password or len(password) < 6:
        return _fin('error_missing_password')
    # Rôle FACULTATIF : un compte peut exister sans rôle (ex. premier admin
    # avant que les rôles de l'entité soient créés).
    if User.query.filter_by(email=email).first():
        return _fin('error_email_exists')

    # ⚠️ On ne crée pas AU-DESSUS de soi : sans ce contrôle, un compte
    # autorisé à créer des comptes se fabriquait un administrateur — et se
    # donnait par la bande des droits qu'il n'a pas. Le masquage du champ
    # dans la page n'y suffit pas, il ne coûte rien de le contourner.
    from Code.permissions import niveau, niveau_status
    moi = _current_user()
    if niveau_status(status) > niveau(moi):
        return _fin('error_status_too_high', http=403)

    try:
        age = int(age_raw) if age_raw else None
    except ValueError:
        return _fin('error_invalid_age')

    # Les rôles de départ : la fiche en envoie plusieurs (`roles_ajout`) ;
    # `role_id` reste compris pour qui envoie encore l'ancien formulaire.
    ajout = _ids_de(request.form, 'roles_ajout')
    if role_id_raw:
        ajout += _ids_de(request.form, 'role_id')

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
    db.session.flush()
    erreur = _appliquer_roles(moi, user, ajout, [])
    if erreur:
        # Rien n'est créé à moitié : un compte sans les rôles demandés
        # laisserait croire que tout est en place.
        db.session.rollback()
        return _fin(erreur, http=403 if erreur == 'error_forbidden_roles' else 400)
    db.session.commit()
    return _fin('created', ok=True)

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
    roles = Role.query.all()

    if request.method == 'POST':
        form = request.form
        moi = _current_user()
        prenom = (form.get('first_name') or '').strip()
        nom    = (form.get('last_name')  or '').strip()
        email  = (form.get('email')      or '').strip()
        if not prenom or not nom:
            return _fin('error_missing_name')
        if not email:
            return _fin('error_missing_email')
        if User.query.filter(User.email == email, User.id != user.id).first():
            return _fin('error_email_exists')

        # Un champ « âge » laissé vide arrive comme '' : tel quel dans une
        # colonne entière, PostgreSQL rejette la requête et TOUTE modification
        # (même un simple nom de famille) repartait en erreur 500.
        age_brut = (form.get('age') or '').strip()
        try:
            age = int(age_brut) if age_brut else None
        except ValueError:
            return _fin('error_invalid_age')

        new_password = form.get('password', '').strip()
        if new_password and len(new_password) < 6:
            return _fin('error_missing_password')

        user.first_name = prenom
        user.last_name = nom
        user.email = email
        user.age = age
        # Seul un administrateur change un statut : sinon n'importe qui
        # s'auto-promeut depuis l'édition de son propre compte.
        # ⚠️ Et pas le SIEN : un administrateur qui se retire son palier perd
        # l'écran depuis lequel il le remettrait — la porte se refermerait de
        # l'intérieur. C'est un autre administrateur qui le fait.
        if _is_admin(moi) and moi.id != user.id and form.get('status'):
            # La colonne fait 20 caractères : un libellé plus long serait tronqué
            # par la base (ou refusé), avec des droits inexpliqués à la clé.
            user.status = form.get('status').strip()[:20]

        if new_password:
            new_hash = hash_password(new_password)
            user.password = new_hash
            flag_modified(user, 'password')  # force SQLAlchemy à inclure password dans l'UPDATE

        # Les rôles bougent PAR PAIRE, et seulement ceux que la fiche nomme.
        # `role_id` (ancien formulaire) ne fait plus qu'AJOUTER : vide, il ne
        # retire plus rien — c'était la porte par laquelle un simple
        # « Enregistrer » effaçait un rôle tenu sur une autre carto.
        ajout = _ids_de(form, 'roles_ajout')
        if (form.get('role_id') or '').strip():
            ajout += _ids_de(form, 'role_id')
        erreur = _appliquer_roles(moi, user, ajout, _ids_de(form, 'roles_retrait'))
        if erreur:
            db.session.rollback()
            return _fin(erreur, http=403 if erreur == 'error_forbidden_roles' else 400)

        db.session.add(user)
        try:
            db.session.commit()
        except SQLAlchemyError:
            # Mieux vaut un message dans la page qu'une 500 opaque.
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return _fin('error_update', http=500)
        return _fin('updated', ok=True)

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

