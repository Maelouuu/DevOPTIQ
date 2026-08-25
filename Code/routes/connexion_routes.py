from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from sqlalchemy.orm.attributes import flag_modified
from Code.models.models import User, Role, UserRole, DEFAULT_LANG, default_lang_for  # Ajout de UserRole
from Code.extensions import db
from Code.security import hash_password, verify_password, needs_rehash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password')

        # Vérifier si l'utilisateur existe dans la base de données
        user = User.query.filter_by(email=email).first()
        if user is None:
            flash('Compte introuvable.', 'error')
            return redirect(url_for('auth.login'))

        # Vérifier si le mot de passe correspond
        if not verify_password(user.password, password):
            flash('Mot de passe incorrect.', 'error')
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

        session['user_email'] = email
        session['user_id'] = user.id  # IMPORTANT pour le filtrage des entités
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
    flash('Déconnexion réussie.', 'success')
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