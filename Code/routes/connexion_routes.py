from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy.orm.attributes import flag_modified
from Code.models.models import User, Role, UserRole, DEFAULT_LANG, default_lang_for  # Ajout de UserRole
from Code.extensions import db
from Code.security import hash_password, verify_password, needs_rehash
from Code import mot_de_passe as mdp
from Code.translations import t

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password')

        # Vérifier si l'utilisateur existe dans la base de données
        # (insensible à la casse : les adresses d'entreprise sont souvent
        # affichées Prenom.Nom@… alors qu'elles sont stockées en minuscules)
        from sqlalchemy import func
        user = User.query.filter(func.lower(User.email) == email.lower()).first()
        # ⚠️ UN SEUL message pour les deux moitiés. « Compte introuvable. »
        # d'un côté et « Mot de passe incorrect. » de l'autre disaient à un
        # inconnu quelles adresses ont un compte chez nous : il suffisait
        # d'essayer des adresses pour dresser la liste du personnel.
        if user is None or not verify_password(user.password, password):
            flash(t('login.bad_credentials'), 'error')
            return redirect(url_for('auth.login'))

        # Migration transparente : re-hache les formats historiques (scrypt…)
        # vers le standard PBKDF2 au fil des connexions réussies.
        if needs_rehash(user.password):
            try:
                user.password = hash_password(password)
                flag_modified(user, 'password')
                db.session.commit()
            except Exception:
                db.session.rollback()  # le login reste valide même si la migration échoue

        # Email canonique (celui de la base) : les lectures par
        # session['user_email'] restent des égalités strictes.
        session['user_email'] = user.email
        session['user_id'] = user.id  # IMPORTANT pour le filtrage des entités
        # Empreinte du dernier changement de mot de passe : un `before_request`
        # la compare, et ferme la session si le mot de passe a changé depuis.
        session['pwd_at'] = mdp.empreinte_session(user)
        # Langue du compte. Les comptes créés avant l'ajout de la colonne
        # n'ont rien : on retombe sur le défaut produit (anglais), sauf pour
        # les comptes explicitement français.
        lang = getattr(user, 'lang', None) or default_lang_for(user.email)
        session['lang'] = lang
        if getattr(user, 'lang', None) != lang:
            try:
                user.lang = lang
                db.session.commit()
            except Exception:
                db.session.rollback()  # le login reste valide
        return redirect(url_for('activities_map_bp.activities_map_page'))

    return render_template('connexion.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_id', None)  # Nettoyer l'ID utilisateur
    session.pop('active_entity_id', None)  # Nettoyer l'entité active
    session['lang'] = DEFAULT_LANG  # l'écran de connexion repart en anglais
    flash(t('login.logged_out'), 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/auth/current_user_info')
def current_user_info():
    from flask import session, jsonify
    from Code.models.models import User, UserRole, Role

    email = session.get('user_email')
    if not email:
        return jsonify({'error': 'Utilisateur non connecté'}), 403

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    roles = [ur.role.name for ur in user.user_roles]
    manager = User.query.get(user.manager_id) if user.manager_id else None

    return jsonify({
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'roles': roles,
        'manager_id': user.manager_id,
        'manager_first_name': manager.first_name if manager else "",
        'manager_last_name': manager.last_name if manager else ""
    })