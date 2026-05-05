from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from Code.models.models import User, Role, UserRole  # Ajout de UserRole
from Code.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Vérifier si l'utilisateur existe dans la base de données
        user = User.query.filter_by(email=email).first()
        if user is None:
            flash('Compte introuvable.', 'error')
            return redirect(url_for('auth.login'))

        # Vérifier si le mot de passe correspond
        if not check_password_hash(user.password, password):
            flash('Mot de passe incorrect.', 'error')
            return redirect(url_for('auth.login'))

        session['user_email'] = email
        session['user_id'] = user.id  # IMPORTANT pour le filtrage des entités
        return redirect(url_for('activities_map_bp.activities_map_page'))

    return render_template('connexion.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_id', None)  # Nettoyer l'ID utilisateur
    session.pop('active_entity_id', None)  # Nettoyer l'entité active
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