from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from Code.extensions import db
from Code.models.models import User, Role, UserRole, Entity, EntrepriseSettings
from Code.role_i18n import on_role_name_saved
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

gestion_rh_bp = Blueprint('gestion_rh', __name__, url_prefix='/gestion_rh')

# Colonnes modifiables de entreprise_settings (liste blanche — jamais de clé
# arbitraire interpolée dans le SQL)
SETTING_KEYS = ("work_hours_per_day", "work_days_per_week",
                "work_weeks_per_year", "work_days_per_year")


def get_active_entity_id():
    """Récupère l'ID de l'entité active depuis la session."""
    return session.get('active_entity_id')


def _ensure_settings_table():
    """Crée entreprise_settings si absente (DB historiques sans le modèle)."""
    try:
        EntrepriseSettings.__table__.create(db.engine, checkfirst=True)
    except Exception:
        db.session.rollback()


def _get_settings_row(entity_id, create=False):
    """Ligne de paramètres de l'entité active (ou la 1re ligne sans entité)."""
    q = EntrepriseSettings.query
    row = (q.filter_by(entity_id=entity_id).first() if entity_id
           else q.order_by(EntrepriseSettings.id).first())
    if row is None and create:
        row = EntrepriseSettings(entity_id=entity_id)
        db.session.add(row)
    return row


def ensure_manager_id_column():
    """Ajoute la colonne manager_id à user_roles si elle n'existe pas."""
    try:
        db.session.execute(text(
            "ALTER TABLE user_roles ADD COLUMN manager_id INTEGER REFERENCES users(id)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


@gestion_rh_bp.route('/')
def gestion_rh_home():
    # ⚠️ Cette page n'avait AUCUN contrôle d'accès : tout compte connecté
    # l'ouvrait, et pouvait de là créer des rôles et affecter des personnes.
    # Elle est réservée au coordinateur et à l'administrateur.
    from Code.permissions import can_access_rh, current_user
    if not can_access_rh(current_user()):
        return redirect('/')
    try:
        ensure_manager_id_column()
        active_entity_id = get_active_entity_id()

        # Le développeur de compétences existe dans TOUTE entité : on le crée au
        # premier affichage plutôt que d'exiger qu'on y pense. Sans lui, la
        # section Affectation n'a personne à proposer.
        try:
            from Code.roles_permanents import assurer_roles_permanents
            if assurer_roles_permanents(active_entity_id):
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ rôle permanent non créé : {e}")

        # Récupérer les paramètres entreprise
        try:
            _ensure_settings_table()
            row = _get_settings_row(active_entity_id)
            settings = {}
            if row:
                for k in SETTING_KEYS:
                    v = getattr(row, k)
                    if v is None:
                        continue
                    settings[k] = int(v) if isinstance(v, float) and v.is_integer() else v
        except Exception as e:
            print(f"⚠️ Erreur récupération settings: {e}")
            db.session.rollback()  # IMPORTANT: Rollback pour réinitialiser la transaction
            settings = {}

        # Filtrer par entité active
        if active_entity_id:
            roles = Role.query.filter_by(entity_id=active_entity_id).order_by(Role.name).all()
            users = User.query.filter_by(entity_id=active_entity_id).order_by(User.first_name).all()
        else:
            roles = Role.query.order_by(Role.name).all()
            users = User.query.order_by(User.first_name).all()

        return render_template('gestion_rh.html', settings=settings, roles=roles, users=users)
    except Exception as e:
        print(f"❌ Erreur dans gestion_rh_home: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()  # Rollback en cas d'erreur globale
        return f"<h1>Erreur</h1><p>Une erreur est survenue: {str(e)}</p><pre>{traceback.format_exc()}</pre>", 500


def _parse_setting_value(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(str(raw).replace(",", "."))
    except ValueError:
        return None


@gestion_rh_bp.route('/update_settings', methods=['POST'])
def update_settings():
    data = request.form
    active_entity_id = get_active_entity_id()

    _ensure_settings_table()
    row = _get_settings_row(active_entity_id, create=True)
    for key in SETTING_KEYS:
        setattr(row, key, _parse_setting_value(data.get(key)))
    db.session.commit()
    return redirect(url_for('gestion_rh.gestion_rh_home'))


@gestion_rh_bp.route('/assign_roles', methods=['POST'])
def assign_roles():
    user_id = request.form.get("user_id")
    role_ids = request.form.getlist("role_ids")
    db.session.query(UserRole).filter_by(user_id=user_id).delete()
    for rid in role_ids:
        db.session.add(UserRole(user_id=user_id, role_id=rid))
    db.session.commit()
    return redirect(url_for('gestion_rh.gestion_rh_home'))


import csv
from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@gestion_rh_bp.route('/import_roles', methods=['POST'])
def import_roles():
    file = request.files['role_file']
    if file and file.filename.endswith('.csv'):
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
        file.save(filepath)

        active_entity_id = get_active_entity_id()

        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if row:  # première colonne = nom du rôle
                    name = row[0].strip()
                    if name:
                        try:
                            db.session.execute(
                                text("INSERT INTO roles (name, entity_id) VALUES (:name, :entity_id)"), 
                                {'name': name, 'entity_id': active_entity_id}
                            )
                        except IntegrityError:
                            db.session.rollback()  # si doublon, ignorer
                        else:
                            db.session.commit()
    return redirect(url_for('gestion_rh.gestion_rh_home'))


@gestion_rh_bp.route('/update_single_setting', methods=['POST'])
def update_single_setting():
    key = request.form.get("key")
    value = request.form.get("value")

    if key not in SETTING_KEYS:
        return jsonify(success=False, error="Paramètre inconnu"), 400

    try:
        active_entity_id = get_active_entity_id()
        _ensure_settings_table()
        row = _get_settings_row(active_entity_id, create=True)
        setattr(row, key, _parse_setting_value(value))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur update_single_setting: {e}")
        return jsonify(success=False, error=str(e)), 500

    # Relecture en base : ne jamais annoncer un succès non persisté
    saved = db.session.execute(
        text("SELECT {} FROM entreprise_settings WHERE id = :rid".format(key)),
        {"rid": row.id}
    ).scalar()
    return jsonify(success=True, key=key, value=saved)


@gestion_rh_bp.route('/role', methods=['POST'])
def create_or_update_role():
    role_id = request.form.get('id')
    name = request.form.get('name').strip()

    if role_id:
        role = Role.query.get(role_id)
        if role:
            on_role_name_saved(role, name)
    else:
        active_entity_id = get_active_entity_id()
        new_role = Role(name=name, entity_id=active_entity_id)
        on_role_name_saved(new_role, name)
        db.session.add(new_role)
    db.session.commit()
    return jsonify(success=True)


@gestion_rh_bp.route('/delete_role/<int:role_id>', methods=['POST'])
def delete_role(role_id):
    role = Role.query.get(role_id)
    if role:
        db.session.delete(role)
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False), 404


@gestion_rh_bp.route('/collaborateurs')
def get_collaborateurs():
    search = request.args.get('search', '').lower()
    role_filter = request.args.get('role', '')

    active_entity_id = get_active_entity_id()
    query = db.session.query(User).join(UserRole, User.id == UserRole.user_id, isouter=True).join(Role, UserRole.role_id == Role.id, isouter=True)
    
    if active_entity_id:
        query = query.filter(User.entity_id == active_entity_id)

    if search:
        query = query.filter((User.first_name + ' ' + User.last_name).ilike(f"%{search}%"))

    if role_filter:
        query = query.filter(Role.name == role_filter)

    users = query.order_by(User.last_name).all()

    # Récupération manuelle des rôles pour chaque user
    user_roles = db.session.execute(text("""
        SELECT ur.user_id, r.name
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
    """)).fetchall()

    user_roles_map = {}
    for row in user_roles:
        user_roles_map.setdefault(row[0], []).append(row[1])

    return jsonify([
        {
            "id": u.id,
            "name": f"{u.first_name} {u.last_name}",
            "roles": user_roles_map.get(u.id, [])
        }
        for u in users
    ])


@gestion_rh_bp.route('/collaborateur_roles', methods=['POST'])
def update_collaborateur_roles():
    user_id = request.form.get('user_id')
    new_roles = request.form.getlist('role_ids[]')  # tableau de IDs
    db.session.query(UserRole).filter_by(user_id=user_id).delete()
    for rid in new_roles:
        db.session.add(UserRole(user_id=user_id, role_id=int(rid)))
    db.session.commit()
    return jsonify(success=True)


@gestion_rh_bp.route('/update_collaborator_name', methods=['POST'])
def update_collaborator_name():
    """
    Met à jour le nom d'un collaborateur.
    Body JSON: { "user_id": int, "name": "Prénom Nom" }
    """
    data = request.get_json()
    user_id = data.get('user_id')
    full_name = data.get('name', '').strip()
    
    if not user_id or not full_name:
        return jsonify(success=False, error="Données manquantes"), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify(success=False, error="Utilisateur non trouvé"), 404
    
    # Séparer prénom et nom (prend le premier mot comme prénom, le reste comme nom)
    parts = full_name.split(' ', 1)
    if len(parts) == 2:
        user.first_name = parts[0]
        user.last_name = parts[1]
    else:
        # Si un seul mot, on le met en prénom
        user.first_name = full_name
        user.last_name = ''
    
    db.session.commit()
    return jsonify(success=True, first_name=user.first_name, last_name=user.last_name)


@gestion_rh_bp.route('/assign_manager', methods=['POST'])
def assign_manager():
    data = request.get_json()
    manager_id = data.get('manager_id')
    assignments = data.get('assignments', [])  # liste de { user_id, role_id }

    if not manager_id or not assignments:
        return jsonify({'error': 'Paramètres manquants'}), 400

    for a in assignments:
        user = User.query.get(a['user_id'])
        if user:
            user.manager_id = manager_id

    db.session.commit()
    return jsonify({'success': True})


@gestion_rh_bp.route('/roles')
def get_all_roles():
    active_entity_id = get_active_entity_id()
    
    if active_entity_id:
        roles = Role.query.filter_by(entity_id=active_entity_id).order_by(Role.name).all()
    else:
        roles = Role.query.order_by(Role.name).all()
    
    return jsonify([{'id': r.id, 'name': r.name} for r in roles])


@gestion_rh_bp.route('/users_by_roles')
def get_users_by_roles():
    role_ids = request.args.get('roles', '')
    role_ids = [int(rid) for rid in role_ids.split(',') if rid.isdigit()]
    user_roles = UserRole.query.filter(UserRole.role_id.in_(role_ids)).all()

    users_map = {}
    for ur in user_roles:
        user = ur.user
        if user.id not in users_map:
            users_map[user.id] = {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'roles': []
            }
        users_map[user.id]['roles'].append(ur.role.name)

    return jsonify(list(users_map.values()))


@gestion_rh_bp.route('/users_with_roles')
def get_users_with_roles():
    # ⚠️ Filtrer les COMPTES sur `User.entity_id` vide la liste : la colonne
    # n'est renseignée nulle part. Ce sont les RÔLES qui appartiennent à une
    # entité — et la boucle ci-dessous ne garde déjà que les comptes qui en ont.
    users = User.query.all()

    result = []
    for user in users:
        roles = [ur.role.name for ur in user.user_roles if ur.role is not None]
        if roles:
            result.append({
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'roles': roles
            })
    return jsonify(result)


@gestion_rh_bp.route('/users_with_role')
def get_users_with_role():
    role_name = request.args.get('role')
    active_entity_id = get_active_entity_id()

    # ⚠️ `?role=manager` était le SEUL moyen d'atteindre le développeur de
    # compétences, par son nom littéral : sur une entité qui n'en avait pas, la
    # liste revenait vide et la section Affectation semblait morte. On reconnaît
    # désormais la famille de noms, et on crée le rôle s'il manque — il est
    # permanent, il doit exister.
    from Code.roles_permanents import est_dev_competences, role_dev_competences
    if est_dev_competences(role_name):
        role = role_dev_competences(active_entity_id)
        if role:
            db.session.commit()
    elif active_entity_id:
        role = Role.query.filter_by(name=role_name, entity_id=active_entity_id).first()
    else:
        role = Role.query.filter_by(name=role_name).first()

    if not role:
        return jsonify([])
    
    users = db.session.query(User).join(UserRole, User.id == UserRole.user_id).filter(UserRole.role_id == role.id).all()
    return jsonify([{'id': u.id, 'first_name': u.first_name, 'last_name': u.last_name} for u in users])


@gestion_rh_bp.route('/all_collaborators_with_manager')
def get_all_collaborators_with_manager():
    """Retourne TOUS les collaborateurs de l'entité avec leurs rôles et affectations manager par rôle"""
    active_entity_id = get_active_entity_id()

    if active_entity_id:
        users = User.query.filter_by(entity_id=active_entity_id).order_by(User.last_name).all()
        all_roles = Role.query.filter_by(entity_id=active_entity_id).order_by(Role.name).all()
    else:
        users = User.query.order_by(User.last_name).all()
        all_roles = Role.query.order_by(Role.name).all()

    # Activités (Garant) par rôle — pour scoper la couleur de compétences au rôle
    from Code.competency_color import user_competency_hex
    role_acts = {}
    for rid, aid in db.session.execute(text(
        "SELECT role_id, activity_id FROM activity_roles WHERE LOWER(status) = 'garant'"
    )).fetchall():
        role_acts.setdefault(rid, []).append(aid)

    users_data = []
    for u in users:
        roles = []
        for ur in u.user_roles:
            if ur.role:
                roles.append({
                    'id': ur.role.id,
                    'name': ur.role.name,
                    'manager_id': ur.manager_id,
                    # Couleur = moyenne des notes du manager pour ce user sur les
                    # activités du rôle (None si aucune évaluation).
                    'comp_color': user_competency_hex(
                        u.id, role_acts.get(ur.role.id, []), evaluator='manager'),
                })
        users_data.append({
            'id': u.id,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'manager_id': u.manager_id,
            'roles': roles
        })

    roles_data = [{'id': r.id, 'name': r.name} for r in all_roles]
    return jsonify({'users': users_data, 'roles': roles_data})


@gestion_rh_bp.route('/assign_manager_simple', methods=['POST'])
def assign_manager_simple():
    """
    Affecte ou retire un collaborateur d'un manager.
    Body JSON:
    - user_id: int (requis)
    - manager_id: int ou null (null pour retirer)
    - role_ids: list[int] ou null (null = global, liste = par rôle)
    """
    data = request.get_json()
    user_id = data.get('user_id')
    manager_id = data.get('manager_id')
    role_ids = data.get('role_ids')  # None = global, liste = par rôle

    if not user_id:
        return jsonify({'success': False, 'message': 'user_id requis'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Utilisateur introuvable'}), 404

    if role_ids is not None:
        # Affectation par rôle : mettre à jour manager_id sur les user_roles spécifiques
        for ur in user.user_roles:
            if ur.role_id in role_ids:
                ur.manager_id = manager_id
            elif manager_id is None:
                # Si on retire, on retire aussi des rôles spécifiés
                pass
    else:
        # Affectation globale : mettre à jour tous les user_roles + le user.manager_id
        user.manager_id = manager_id
        for ur in user.user_roles:
            ur.manager_id = manager_id

    db.session.commit()

    return jsonify({
        'success': True,
        'user_id': user.id,
        'manager_id': user.manager_id
    })

# ═══════════════════════════════════════════════════════════════════════════
#  Le tableau de la page RH — tout ce dont elle a besoin, en UN appel
# ═══════════════════════════════════════════════════════════════════════════

@gestion_rh_bp.route('/api/tableau')
def api_tableau():
    """Les personnes, les rôles, l'accès à la carto et les propositions.

    La page appelait DIX endpoints qui se recoupaient : chacun refaisait ses
    requêtes, et deux d'entre eux se contredisaient sur qui est collaborateur.
    Un seul appel, une seule vérité, un seul rendu.

    ⚠️ **Tous les comptes sont des collaborateurs**, quel que soit leur statut.
    L'ancienne liste filtrait sur `User.entity_id` — une colonne que la page des
    Comptes ne remplit jamais. Elle revenait donc VIDE sur toutes les instances,
    et la page semblait cassée alors que les comptes étaient bien là.
    """
    from Code.carto_access import access_summary, can_manage_access, entity_role_ids
    from Code.models.models import CartoChangeRequest
    from Code.permissions import is_admin, is_coordinator
    from Code.roles_permanents import ROLE_DEV_COMPETENCES, est_dev_competences

    moi = db.session.get(User, session.get('user_id')) if session.get('user_id') else None
    if moi is None:
        return jsonify({'error': 'Non connecté'}), 401

    # ── L'entité regardée ────────────────────────────────────────────────
    ouvrables = Entity.accessible(moi.id)
    demandee = request.args.get('entity_id', type=int)
    entite = None
    if demandee:
        entite = next((e for e in ouvrables if e.id == demandee), None)
    if entite is None:
        actif = get_active_entity_id()
        entite = next((e for e in ouvrables if e.id == actif), None)
    if entite is None and ouvrables:
        entite = ouvrables[0]

    entity_id = entite.id if entite else None
    if entity_id:
        session['active_entity_id'] = entity_id
        try:
            from Code.roles_permanents import assurer_roles_permanents
            if assurer_roles_permanents(entity_id):
                db.session.commit()
        except Exception:
            db.session.rollback()

    # ── Les rôles de l'entité, leurs titulaires, leur accès ──────────────
    roles = (Role.query.filter_by(entity_id=entity_id).order_by(Role.name).all()
             if entity_id else [])
    ouvrent = entity_role_ids(entity_id) if entity_id else set()
    titulaires = {}
    if roles:
        for ur in UserRole.query.filter(
                UserRole.role_id.in_([r.id for r in roles])).all():
            titulaires.setdefault(ur.role_id, []).append(ur.user_id)

    from Code.role_i18n import nom_affiche
    roles_json = [{
        'id': r.id,
        'name': nom_affiche(r),
        # Le développeur de compétences n'est pas une bande de la carto : il ne
        # se supprime pas, et l'interface doit le dire au lieu de proposer une
        # corbeille qui ne marchera pas.
        'permanent': est_dev_competences(r.name),
        'ouvre_carto': r.id in ouvrent,
        'titulaires': sorted(titulaires.get(r.id, [])),
    } for r in roles]
    # Le tri suit le nom AFFICHÉ : trié sur le nom en base, le rôle système
    # restait à la place de « Développeur » dans une liste anglaise.
    roles_json.sort(key=lambda r: r["name"].lower())

    id_dev = next((r['id'] for r in roles_json if r['permanent']), None)
    ids_dev = set(titulaires.get(id_dev, [])) if id_dev else set()

    # ── Les personnes : TOUS les comptes ─────────────────────────────────
    comptes = User.query.order_by(User.last_name, User.first_name).all()
    par_role = {}
    for ur in UserRole.query.all():
        par_role.setdefault(ur.user_id, []).append(ur)
    noms_roles = {r.id: nom_affiche(r) for r in Role.query.all()}

    personnes = []
    for u in comptes:
        siens = [{'id': ur.role_id, 'name': noms_roles.get(ur.role_id, '—'),
                  'dev_id': ur.manager_id}
                 for ur in par_role.get(u.id, [])
                 if ur.role_id in {r['id'] for r in roles_json}]
        personnes.append({
            'id': u.id,
            'prenom': u.first_name,
            'nom': u.last_name,
            'email': u.email,
            'statut': u.status,
            'roles': siens,
            'dev_id': u.manager_id,
            'est_dev': u.id in ids_dev,
        })

    # ── Les propositions en attente sur cette carto ──────────────────────
    propositions = []
    if entity_id:
        for cr in (CartoChangeRequest.query
                   .filter_by(entity_id=entity_id, status='pending')
                   .order_by(CartoChangeRequest.created_at.desc()).all()):
            auteur = db.session.get(User, cr.author_id)
            propositions.append({
                'id': cr.id,
                'titre': cr.title or '',
                'auteur': (f"{auteur.first_name} {auteur.last_name}"
                           if auteur else '—'),
                'le': cr.created_at.isoformat() if cr.created_at else None,
                'a_moi': cr.author_id == moi.id,
            })

    # ── Le calendrier de travail ─────────────────────────────────────────
    calendrier = {}
    try:
        _ensure_settings_table()
        row = _get_settings_row(entity_id)
        if row:
            for k in SETTING_KEYS:
                v = getattr(row, k)
                if v is not None:
                    calendrier[k] = int(v) if isinstance(v, float) and v.is_integer() else v
    except Exception:
        db.session.rollback()

    resume = access_summary(entite) if entite else {}
    return jsonify({
        'entites': [{
            'id': e.id, 'name': e.name,
            'is_shared': bool(getattr(e, 'is_shared', False)),
        } for e in ouvrables],
        'entite': ({'id': entite.id, 'name': entite.name,
                    'is_shared': bool(entite.is_shared),
                    'open_to_all': bool(resume.get('open_to_all'))}
                   if entite else None),
        'calendrier': calendrier,
        'personnes': personnes,
        'roles': roles_json,
        'role_dev_id': id_dev,
        'role_dev_nom': ROLE_DEV_COMPETENCES,
        'propositions': propositions,
        'moi': {'id': moi.id, 'est_dev': moi.id in ids_dev},
        'droits': {
            'gere_acces': bool(entite and can_manage_access(entite, moi)),
            # Qui peut attribuer un collaborateur : un développeur de
            # compétences, un champion ou un administrateur.
            'affecte': bool(moi.id in ids_dev or is_coordinator(moi) or is_admin(moi)),
            'admin': bool(is_admin(moi)),
        },
    })


# ═══════════════════════════════════════════════════════════════════════════
#  Un rôle, PLUSIEURS cartos — en une manœuvre
# ═══════════════════════════════════════════════════════════════════════════
# Ouvrir une carto à un rôle se faisait carto par carto : il fallait changer
# l'entité en haut de page, cocher, recommencer. Pour cinq cartos, cinq
# allers-retours — et aucun endroit d'où VOIR ce qu'un rôle ouvre au total.
#
# ⚠️ `set_access` (page Partage) n'accepte que les rôles DE l'entité réglée.
# C'est juste là-bas : on y règle une carto et on coche parmi SES bandes. Ici
# on part du rôle, et le rôle appartient à la carto d'où on le regarde — le
# même rôle est donc légitimement posé sur d'autres cartos. `can_read` s'en
# accommode depuis toujours : il compare les rôles du compte aux rôles
# autorisés, sans jamais demander à quelle entité ces rôles appartiennent.

def _entites_gerables(moi):
    """Les cartos dont CE compte règle l'accès, indexées par id."""
    from Code.carto_access import can_manage_access
    return {e.id: e for e in Entity.accessible(moi.id)
            if can_manage_access(e, moi)}


@gestion_rh_bp.route('/role_cartos/<int:role_id>')
def role_cartos(role_id):
    """Ce qu'un rôle ouvre, et ce qu'il POURRAIT ouvrir.

    Chaque carto porte de quoi décider en connaissance de cause :
      · `ouverte`    — ce rôle y donne-t-il accès aujourd'hui ;
      · `commune`    — une carto PRIVÉE ignore les rôles (`can_read` rend la
                       main au propriétaire avant même de les consulter) : la
                       cocher la rendra donc commune, et l'écran doit le dire ;
      · `sans_filtre`— ⚠️ une carto commune SANS aucun rôle autorisé est
                       ouverte à TOUS les comptes. Y ajouter le premier rôle
                       la RESTREINT. Cocher peut donc retirer l'accès à des
                       gens qui l'avaient : c'est le piège de cet écran, il
                       est annoncé ligne par ligne.
    """
    from Code.carto_access import entity_role_ids
    from Code.permissions import can_access_rh, current_user

    moi = current_user()
    if not can_access_rh(moi):
        return jsonify({'error': 'Accès refusé'}), 403
    role = db.session.get(Role, role_id)
    if role is None:
        return jsonify({'error': 'Rôle introuvable'}), 404

    gerables = _entites_gerables(moi)
    cartos = []
    for e in sorted(gerables.values(), key=lambda x: (x.name or '').lower()):
        autorises = entity_role_ids(e.id)
        cartos.append({
            'id': e.id,
            'name': e.name,
            'commune': bool(getattr(e, 'is_shared', False)),
            'ouverte': role.id in autorises,
            'sans_filtre': bool(getattr(e, 'is_shared', False)) and not autorises,
            'n_roles': len(autorises),
        })
    return jsonify({
        'role': {'id': role.id, 'name': role.name, 'entity_id': role.entity_id},
        'cartos': cartos,
    })


@gestion_rh_bp.route('/role_cartos', methods=['POST'])
def set_role_cartos():
    """Pose ce rôle sur les cartos cochées, le retire des autres. UNE manœuvre.

    ⚠️ On ne touche QUE les cartos dont l'appelant règle l'accès, et on ne
    touche QUE la ligne de CE rôle : les autres rôles autorisés sur ces cartos
    ne bougent pas. Sans cette précaution, régler un rôle effacerait le travail
    fait sur les autres.
    """
    from Code.models.models import EntityRoleAccess
    from Code.permissions import can_access_rh, current_user

    moi = current_user()
    if not can_access_rh(moi):
        return jsonify({'error': 'Accès refusé'}), 403

    data = request.get_json(silent=True) or {}
    role = db.session.get(Role, data.get('role_id'))
    if role is None:
        return jsonify({'error': 'Rôle introuvable'}), 404
    voulues = {int(x) for x in (data.get('entity_ids') or [])}

    gerables = _entites_gerables(moi)
    refusees = sorted(voulues - set(gerables))
    voulues &= set(gerables)

    ouvertes, fermees, rendues_communes = [], [], []
    for eid, entite in gerables.items():
        ligne = EntityRoleAccess.query.filter_by(
            entity_id=eid, role_id=role.id).first()
        if eid in voulues and ligne is None:
            # Une carto privée ignore les rôles : la cocher la rend commune,
            # sinon on enregistrerait un accès qui ne produit rien.
            if not getattr(entite, 'is_shared', False):
                entite.is_shared = True
                rendues_communes.append(eid)
            db.session.add(EntityRoleAccess(entity_id=eid, role_id=role.id))
            ouvertes.append(eid)
        elif eid not in voulues and ligne is not None:
            db.session.delete(ligne)
            fermees.append(eid)
    db.session.commit()

    return jsonify({
        'ok': True,
        'ouvertes': ouvertes,
        'fermees': fermees,
        'rendues_communes': rendues_communes,
        'refusees': refusees,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  Le développeur de compétences, RÔLE PAR RÔLE
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ `user_roles.manager_id` porte ce lien depuis toujours, et
# `competences_acces.encadre()` le lit déjà — mais AUCUN écran ne le posait :
# la page envoyait `role_ids: null`, c'est-à-dire « le même développeur pour
# tous les rôles ». Or celui qui suit quelqu'un sur « Qualité » ne le suit pas
# forcément sur « Logistique ».

def _dissoudre_lien_global(user):
    """Reporte le développeur GLOBAL sur chaque rôle tenu, puis l'efface.

    ⚠️ **Sans ça, régler un rôle ne produit RIEN.** `encadre()` lit les DEUX
    rattachements (`users.manager_id` et `user_roles.manager_id`) : tant que le
    lien global existe, il couvre tous les rôles — y compris celui dont on
    vient de retirer le développeur. On ne perd personne au passage, ce que le
    lien global couvrait est repris rôle par rôle ; ensuite seulement la
    portée demandée veut dire quelque chose.
    """
    if user is None or user.manager_id is None:
        return False
    global_id = user.manager_id
    for ur in user.user_roles:
        if ur.manager_id is None:
            ur.manager_id = global_id
    user.manager_id = None
    return True


@gestion_rh_bp.route('/role_dev', methods=['POST'])
def set_role_dev():
    """Qui suit CE collaborateur sur CE rôle. `dev_id` nul = personne."""
    from Code.permissions import can_access_rh, current_user

    moi = current_user()
    if not can_access_rh(moi):
        return jsonify({'error': 'Accès refusé'}), 403

    data = request.get_json(silent=True) or {}
    lien = UserRole.query.filter_by(user_id=data.get('user_id'),
                                    role_id=data.get('role_id')).first()
    if lien is None:
        # Poser un développeur sur un rôle que la personne ne tient pas n'a pas
        # de sens : le lien qui porterait l'information n'existe pas.
        return jsonify({'error': 'Ce compte ne tient pas ce rôle'}), 404

    dev_id = data.get('dev_id')
    if dev_id is not None:
        dev_id = int(dev_id)
        if db.session.get(User, dev_id) is None:
            return jsonify({'error': 'Développeur introuvable'}), 404
        if dev_id == lien.user_id:
            return jsonify({'error': 'Un collaborateur ne se suit pas lui-même'}), 400
    _dissoudre_lien_global(db.session.get(User, lien.user_id))
    lien.manager_id = dev_id
    db.session.commit()
    return jsonify({'ok': True, 'user_id': lien.user_id,
                    'role_id': lien.role_id, 'dev_id': lien.manager_id})


# ═══════════════════════════════════════════════════════════════════════════
#  … et la PORTÉE de ce développeur, en une seule décision
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️ Poser un développeur et choisir sur quoi il suit la personne sont deux
# moitiés de la MÊME décision. Les faire en deux appels laissait un état
# intermédiaire faux — le développeur posé partout le temps que la portée
# arrive — et surtout deux écrans pour une seule question, ce qu'on vient de
# reprocher à cette page.

@gestion_rh_bp.route('/dev_scope', methods=['POST'])
def set_dev_scope():
    """Qui suit ce collaborateur, et SUR QUELS RÔLES.

    `role_ids` nul = tous ses rôles : c'est le lien global, et il couvrira
    aussi les rôles qu'il recevra plus tard. Une LISTE = exactement ces
    rôles — ce développeur est retiré des autres, sans jamais toucher aux
    affectations des autres développeurs.
    """
    from Code.permissions import can_access_rh, current_user

    moi = current_user()
    if not can_access_rh(moi):
        return jsonify({'error': 'Accès refusé'}), 403

    data = request.get_json(silent=True) or {}
    user = (db.session.get(User, int(data['user_id']))
            if data.get('user_id') else None)
    if user is None:
        return jsonify({'error': 'Utilisateur introuvable'}), 404

    dev_id = data.get('dev_id')
    if dev_id is not None:
        dev_id = int(dev_id)
        if db.session.get(User, dev_id) is None:
            return jsonify({'error': 'Développeur introuvable'}), 404
        if dev_id == user.id:
            return jsonify({'error': 'Un collaborateur ne se suit pas lui-même'}), 400

    role_ids = data.get('role_ids', None)
    if role_ids is None:
        # Tous ses rôles : le lien global, ET chaque lien de rôle — l'écran
        # lit les liens de rôle, il doit dire la même chose que le droit.
        user.manager_id = dev_id
        for ur in user.user_roles:
            ur.manager_id = dev_id
    else:
        demandes = {int(x) for x in role_ids}
        tenus = {ur.role_id for ur in user.user_roles}
        inconnus = sorted(demandes - tenus)
        if inconnus:
            # Le lien qui porterait l'information n'existe pas : mieux vaut le
            # dire que d'enregistrer une portée qui ne s'applique à rien.
            return jsonify({'error': 'Ce compte ne tient pas ce rôle',
                            'roles': inconnus}), 404
        _dissoudre_lien_global(user)
        for ur in user.user_roles:
            if ur.role_id in demandes:
                ur.manager_id = dev_id
            elif dev_id is not None and ur.manager_id == dev_id:
                ur.manager_id = None

    db.session.commit()
    return jsonify({'ok': True, 'user_id': user.id, 'dev_id': user.manager_id,
                    'roles': [{'id': ur.role_id, 'dev_id': ur.manager_id}
                              for ur in user.user_roles]})


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
# Un coordinateur LIT le tableau : savoir ce qui est ouvert à qui fait partie
# de son travail, même quand il ne le décide pas.

@gestion_rh_bp.route('/droits')
def lire_droits():
    from Code.permissions import (DROITS_DEFAUT, PALIERS, can_access_rh,
                                  current_user, droits_effectifs, is_admin)

    moi = current_user()
    if not can_access_rh(moi):
        return jsonify({'error': 'Accès refusé'}), 403
    return jsonify({
        'paliers': list(PALIERS),
        'droits': droits_effectifs(),
        'defaut': {d: dict(v, admin=True) for d, v in DROITS_DEFAUT.items()},
        'modifiable': bool(is_admin(moi)),
    })


@gestion_rh_bp.route('/droits', methods=['POST'])
def ecrire_droits():
    from Code.permissions import (can_access_rh, current_user,
                                  droits_effectifs, enregistrer_droits,
                                  is_admin)

    moi = current_user()
    if not can_access_rh(moi):
        return jsonify({'error': 'Accès refusé'}), 403
    if not is_admin(moi):
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
