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
                              is_admin_status, is_competency_manager_status)

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

        # Récupérer tous les utilisateurs (tri alphabétique par NOM COMPLET)
        if active_entity_id:
            users = User.query.filter_by(entity_id=active_entity_id).order_by(User.first_name, User.last_name).all()
        else:
            users = User.query.order_by(User.first_name, User.last_name).all()

        print(f"👥 Nombre d'utilisateurs trouvés: {len(users)}")

        # Créer un dictionnaire utilisateur -> liste de rôles
        users_with_roles = []
        for user in users:
            user_roles = UserRole.query.filter_by(user_id=user.id).all()
            role_names = [Role.query.get(ur.role_id).name for ur in user_roles if Role.query.get(ur.role_id)]
            users_with_roles.append({
                'user': user,
                'roles': role_names
            })

        # Pour compatibilité avec le template existant, créer aussi role_users
        role_users = {}
        for role in roles:
            role_users[role.name] = []

        # Récupérer les managers
        if active_entity_id:
            manager_role = Role.query.filter_by(name="manager", entity_id=active_entity_id).first()
        else:
            manager_role = Role.query.filter_by(name="manager").first()

        if manager_role:
            if active_entity_id:
                managers = User.query.filter_by(entity_id=active_entity_id).join(UserRole, User.id == UserRole.user_id).filter(UserRole.role_id == manager_role.id).all()
            else:
                managers = User.query.join(UserRole, User.id == UserRole.user_id).filter(UserRole.role_id == manager_role.id).all()
        else:
            managers = []

        print(f"👔 Nombre de managers trouvés: {len(managers)}")

        me = _current_user()
        return render_template(
            'gestion_compte_new.html',
            role_users=role_users,
            roles=roles,
            users=users,
            users_with_roles=users_with_roles,
            managers=managers,
            is_admin=_is_admin(me),
            can_create_accounts=_can_create_accounts(me),
            current_user_id=(me.id if me else None),
            is_admin_status=is_admin_status,
            is_competency_manager_status=is_competency_manager_status,
        )

    except Exception as e:
        print(f"❌ Erreur dans list_users: {e}")
        import traceback
        traceback.print_exc()

        # Retourner une page avec des listes vides en cas d'erreur
        me = _current_user()
        return render_template(
            'gestion_compte_new.html',
            role_users={},
            roles=[],
            users=[],
            users_with_roles=[],
            managers=[],
            is_admin=_is_admin(me),
            can_create_accounts=_can_create_accounts(me),
            current_user_id=(me.id if me else None),
        )

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
    if not role_id_raw:
        return redirect(url_for('gestion_compte.list_users', msg='error_missing_role'))
    if User.query.filter_by(email=email).first():
        return redirect(url_for('gestion_compte.list_users', msg='error_email_exists'))

    try:
        role_id = int(role_id_raw)
    except ValueError:
        return redirect(url_for('gestion_compte.list_users', msg='error_missing_role'))

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

    user_role = UserRole(user_id=user.id, role_id=role_id)
    db.session.add(user_role)
    db.session.commit()

    return redirect(url_for('gestion_compte.list_users', tab='list-tab', msg='created'))

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
        return redirect(url_for('gestion_compte.list_users', tab='list-tab', msg='updated'))

    current_role = UserRole.query.filter_by(user_id=user.id).first()
    return render_template('edit_user.html', user=user, roles=roles, current_role=current_role,
                           is_admin_status=is_admin_status,
                           is_competency_manager_status=is_competency_manager_status)

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


@gestion_compte_bp.route('/import_excel', methods=['POST'])
def import_excel():
    """
    Import d'utilisateurs via fichier Excel
    Format attendu: prenom, nom, email, age, mot_de_passe, role, statut
    """
    if not _can_create_accounts():
        return jsonify({'success': False,
                        'error': "Seuls les administrateurs et les gestionnaires de compétences "
                                 "peuvent créer des comptes."}), 403
    try:
        print("📥 Import Excel - Début")
        data = request.get_json()
        print(f"📊 Data reçue: {data}")

        users_data = data.get('users', [])
        print(f"👥 Nombre d'utilisateurs à importer: {len(users_data)}")

        if not users_data:
            print("⚠️ Aucune donnée fournie")
            return jsonify({'success': False, 'message': 'Aucune donnée fournie'}), 400

        active_entity_id = Entity.get_active_id()
        print(f"🏢 Active entity ID: {active_entity_id}")

        imported_count = 0
        errors = []

        for idx, user_data in enumerate(users_data):
            print(f"\n--- Traitement utilisateur {idx + 1}/{len(users_data)} ---")
            print(f"📧 Email: {user_data.get('email')}")
            print(f"👤 Nom: {user_data.get('prenom')} {user_data.get('nom')}")
            try:
                # Vérifier que l'email n'existe pas déjà
                existing_user = User.query.filter_by(email=user_data.get('email')).first()
                if existing_user:
                    error_msg = f"Email {user_data.get('email')} déjà existant"
                    print(f"⚠️ {error_msg}")
                    errors.append(error_msg)
                    continue

                # Trouver le rôle
                role_name = user_data.get('role', '').strip()
                print(f"🔍 Recherche du rôle: '{role_name}'")

                role = Role.query.filter_by(name=role_name, entity_id=active_entity_id).first() if role_name else None

                if not role and role_name:
                    error_msg = f"Rôle '{role_name}' introuvable pour {user_data.get('email')}"
                    print(f"⚠️ {error_msg}")
                    errors.append(error_msg)
                    continue

                print(f"✅ Rôle trouvé: {role.name if role else 'Aucun'}")

                # Créer l'utilisateur
                print(f"➕ Création de l'utilisateur...")
                user = User(
                    first_name=user_data.get('prenom', '').strip(),
                    last_name=user_data.get('nom', '').strip(),
                    email=user_data.get('email', '').strip(),
                    age=int(user_data.get('age')) if user_data.get('age') and str(user_data.get('age')).strip() else None,
                    password=hash_password(user_data.get('mot_de_passe', '').strip()),
                    status=user_data.get('statut', 'user').strip(),
                    lang=default_lang_for(user_data.get('email', '')),
                    entity_id=active_entity_id
                )
                db.session.add(user)
                db.session.flush()  # Pour obtenir l'ID
                print(f"✅ Utilisateur créé avec ID: {user.id}")

                # Associer le rôle si trouvé
                if role:
                    print(f"🔗 Association du rôle {role.name}")
                    user_role = UserRole(user_id=user.id, role_id=role.id)
                    db.session.add(user_role)

                imported_count += 1
                print(f"✅ Utilisateur importé avec succès ({imported_count}/{len(users_data)})")

            except Exception as e:
                error_msg = f"Erreur pour {user_data.get('email')}: {str(e)}"
                print(f"❌ {error_msg}")
                import traceback
                traceback.print_exc()
                errors.append(error_msg)
                continue

        print(f"\n💾 Commit de la transaction...")
        db.session.commit()
        print(f"✅ Transaction commitée avec succès")

        message = f"{imported_count} utilisateur(s) importé(s)"
        if errors:
            message += f". {len(errors)} erreur(s): {', '.join(errors[:3])}"

        print(f"\n📊 Résultat final:")
        print(f"   - Importés: {imported_count}")
        print(f"   - Erreurs: {len(errors)}")
        if errors:
            print(f"   - Liste des erreurs: {errors}")

        return jsonify({
            'success': True,
            'imported': imported_count,
            'errors': errors,
            'message': message
        })

    except Exception as e:
        print(f"\n❌ ERREUR GLOBALE: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erreur serveur: {str(e)}'}), 500
