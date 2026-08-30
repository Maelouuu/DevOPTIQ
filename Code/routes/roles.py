# Code/routes/roles.py

from flask import Blueprint, request, jsonify
from sqlalchemy import text, func
from Code.extensions import db
from Code.models.models import Role, Entity
from Code.role_i18n import on_role_name_saved

roles_bp = Blueprint('roles', __name__, url_prefix='/roles')

@roles_bp.route('/list', methods=['GET'])
def list_roles():
    """
    Retourne la liste de tous les rôles, triés par ordre alphabétique insensible à la casse.
    MODIFIÉ: Filtrer par entité active
    """
    roles = Role.for_active_entity().order_by(func.lower(Role.name)).all()
    data = [{"id": r.id, "name": r.name} for r in roles]
    return jsonify(data), 200

@roles_bp.route('/garant/activity/<int:activity_id>', methods=['POST'])
def set_garant_role(activity_id):
    """
    Affecte un rôle Garant à une activité.
    JSON attendu : { "role_name": "<str>" }
    - Si le rôle n'existe pas, on le crée
    - On supprime l'ancien Garant (s'il existe)
    - On insère le nouveau (status='Garant')
    """
    data = request.get_json() or {}
    role_name = data.get("role_name", "").strip()
    if not role_name:
        return jsonify({"error": "role_name is required"}), 400

    # MODIFIÉ: Vérifier si le rôle existe déjà pour l'entité active
    existing = Role.for_active_entity().filter_by(name=role_name).first()
    if not existing:
        # MODIFIÉ: Créer le rôle avec l'entité active
        active_entity_id = Entity.get_active_id()
        existing = Role(name=role_name, entity_id=active_entity_id)
        on_role_name_saved(existing, role_name)
        db.session.add(existing)
        db.session.commit()

    # Supprimer l'ancien Garant
    db.session.execute(
        text("DELETE FROM activity_roles WHERE activity_id=:aid AND LOWER(status)='garant'"),
        {"aid": activity_id}
    )
    # Ajouter le nouveau Garant
    db.session.execute(
        text("INSERT INTO activity_roles (activity_id, role_id, status) VALUES (:aid, :rid, 'Garant')"),
        {"aid": activity_id, "rid": existing.id}
    )
    db.session.commit()

    return jsonify({
        "message": f"Rôle Garant '{existing.name}' assigné à l'activité {activity_id}",
        "role": {"id": existing.id, "name": existing.name}
    }), 200

@roles_bp.route('/<int:role_id>', methods=['PUT'])
def update_role(role_id):
    """
    Met à jour le nom d'un rôle.
    JSON attendu : { "name": "<str>" }
    Si le rôle est utilisé dans des activités (comme garant) ou dans des tâches pour d'autres statuts,
    cette modification doit être répercutée grâce à l'utilisation de l'ID du rôle.
    """
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "Role not found"}), 404
    data = request.get_json() or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "Name is required"}), 400
    on_role_name_saved(role, new_name)
    db.session.commit()
    return jsonify({"message": "Role updated", "role": {"id": role.id, "name": role.name}}), 200

@roles_bp.route('/<int:role_id>', methods=['DELETE'])
def delete_role(role_id):
    """
    Supprime un rôle.
    Avant suppression, supprime les associations dans les tables activity_roles et task_roles pour éviter les incohérences.
    """
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "Role not found"}), 404
    # Supprimer les associations du rôle dans activity_roles et task_roles
    db.session.execute(
        text("DELETE FROM activity_roles WHERE role_id=:rid"),
        {"rid": role_id}
    )
    db.session.execute(
        text("DELETE FROM task_roles WHERE role_id=:rid"),
        {"rid": role_id}
    )
    db.session.delete(role)
    db.session.commit()
    return jsonify({"message": "Role deleted"}), 200

