from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from Code.extensions import db
from Code.models.models import User, Role, UserRole, Entity

gestion_compte_bp = Blueprint('gestion_compte', __name__, url_prefix='/comptes')

@gestion_compte_bp.route('/')
def list_users():
    try:
        # MODIFIÉ: Filtrer par entité active
        active_entity_id = Entity.get_active_id()

        print(f"🔍 Active entity ID: {active_entity_id}")

        # Récupérer les rôles
        if active_entity_id:
            roles = Role.query.filter_by(entity_id=active_entity_id).all()
        else:
            roles = Role.query.all()

        print(f"📊 Nombre de rôles trouvés: {len(roles)}")

        # Récupérer les utilisateurs par rôle
        role_users = {}
        for role in roles:
            if active_entity_id:
                users_for_role = User.query.filter_by(entity_id=active_entity_id).join(UserRole).filter(UserRole.role_id == role.id).all()
            else:
                users_for_role = User.query.join(UserRole).filter(UserRole.role_id == role.id).all()
            role_users[role.name] = users_for_role

        # Récupérer tous les utilisateurs
        if active_entity_id:
            users = User.query.filter_by(entity_id=active_entity_id).all()
        else:
            users = User.query.all()

        print(f"👥 Nombre d'utilisateurs trouvés: {len(users)}")

        # Récupérer les managers
        if active_entity_id:
            manager_role = Role.query.filter_by(name="manager", entity_id=active_entity_id).first()
        else:
            manager_role = Role.query.filter_by(name="manager").first()

        if manager_role:
            if active_entity_id:
                managers = User.query.filter_by(entity_id=active_entity_id).join(UserRole).filter(UserRole.role_id == manager_role.id).all()
            else:
                managers = User.query.join(UserRole).filter(UserRole.role_id == manager_role.id).all()
        else:
            managers = []

        print(f"👔 Nombre de managers trouvés: {len(managers)}")

        return render_template(
            'gestion_compte_new.html',
            role_users=role_users,
            roles=roles,
            users=users,
            managers=managers
        )

    except Exception as e:
        print(f"❌ Erreur dans list_users: {e}")
        import traceback
        traceback.print_exc()

        # Retourner une page avec des listes vides en cas d'erreur
        return render_template(
            'gestion_compte_new.html',
            role_users={},
            roles=[],
            users=[],
            managers=[]
        )

@gestion_compte_bp.route('/create', methods=['POST'])
def create_user():
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    age = request.form.get('age')
    email = request.form['email']
    password = request.form['password']  
    role_id = int(request.form['role_id'])
    status = request.form['status']

    # MODIFIÉ: Associer le nouvel utilisateur à l'entité active
    active_entity_id = Entity.get_active_id()
    user = User(
        first_name=first_name, 
        last_name=last_name, 
        age=age, 
        email=email, 
        password=password, 
        status=status,
        entity_id=active_entity_id
    )
    db.session.add(user)
    db.session.commit()

    user_role = UserRole(user_id=user.id, role_id=role_id)
    db.session.add(user_role)
    db.session.commit()
    
    return redirect(url_for('gestion_compte.list_users'))

@gestion_compte_bp.route('/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    User.query.filter_by(id=user_id).delete()
    db.session.commit()
    return redirect(url_for('gestion_compte.list_users'))



@gestion_compte_bp.route('/update/<int:user_id>', methods=['GET', 'POST'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    # MODIFIÉ: Filtrer les rôles par entité active
    roles = Role.for_active_entity().all()

    if request.method == 'POST':
        user.first_name = request.form['first_name']
        user.last_name = request.form['last_name']
        user.age = request.form.get('age')
        user.email = request.form['email']
        user.status = request.form['status']

        # Mise à jour du rôle
        new_role_id = int(request.form['role_id'])
        user_role = UserRole.query.filter_by(user_id=user.id).first()
        if user_role:
            user_role.role_id = new_role_id
        else:
            db.session.add(UserRole(user_id=user.id, role_id=new_role_id))

        db.session.commit()
        return redirect(url_for('gestion_compte.list_users'))

    current_role = UserRole.query.filter_by(user_id=user.id).first()
    return render_template('edit_user.html', user=user, roles=roles, current_role=current_role)

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

@gestion_compte_bp.route('/import_excel', methods=['POST'])
def import_excel():
    """
    Import d'utilisateurs via fichier Excel
    Format attendu: prenom, nom, email, age, mot_de_passe, role, statut
    """
    try:
        data = request.get_json()
        users_data = data.get('users', [])

        if not users_data:
            return jsonify({'success': False, 'message': 'Aucune donnée fournie'}), 400

        active_entity_id = Entity.get_active_id()
        imported_count = 0
        errors = []

        for user_data in users_data:
            try:
                # Vérifier que l'email n'existe pas déjà
                existing_user = User.query.filter_by(email=user_data.get('email')).first()
                if existing_user:
                    errors.append(f"Email {user_data.get('email')} déjà existant")
                    continue

                # Trouver le rôle
                role_name = user_data.get('role', '').strip()
                role = Role.query.filter_by(name=role_name).first() if role_name else None

                if not role and role_name:
                    errors.append(f"Rôle '{role_name}' introuvable pour {user_data.get('email')}")
                    continue

                # Créer l'utilisateur
                user = User(
                    first_name=user_data.get('prenom', '').strip(),
                    last_name=user_data.get('nom', '').strip(),
                    email=user_data.get('email', '').strip(),
                    age=user_data.get('age') if user_data.get('age') else None,
                    password=user_data.get('mot_de_passe', '').strip(),
                    status=user_data.get('statut', 'user').strip(),
                    entity_id=active_entity_id
                )
                db.session.add(user)
                db.session.flush()  # Pour obtenir l'ID

                # Associer le rôle si trouvé
                if role:
                    user_role = UserRole(user_id=user.id, role_id=role.id)
                    db.session.add(user_role)

                imported_count += 1

            except Exception as e:
                errors.append(f"Erreur pour {user_data.get('email')}: {str(e)}")
                continue

        db.session.commit()

        message = f"{imported_count} utilisateur(s) importé(s)"
        if errors:
            message += f". {len(errors)} erreur(s): {', '.join(errors[:3])}"

        return jsonify({
            'success': True,
            'imported': imported_count,
            'errors': errors,
            'message': message
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'}), 500
