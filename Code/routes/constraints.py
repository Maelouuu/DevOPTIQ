# Code/routes/constraints.py

from flask import Blueprint, request, jsonify, render_template
from Code.extensions import db
from Code.models.models import Activities, Constraint

constraints_bp = Blueprint('constraints', __name__, url_prefix='/constraints')

@constraints_bp.route('/<int:activity_id>/add', methods=['POST'])
def add_constraint(activity_id):
    """
    Ajoute une contrainte à l'activité <activity_id>.
    JSON attendu : { "description": "<str>" }
    """
    data = request.get_json() or {}
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"error": "description is required"}), 400

    file_path = (data.get("file_path") or "").strip() or None

    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    try:
        new_constraint = Constraint(description=description, activity_id=activity_id, file_path=file_path)
        db.session.add(new_constraint)
        db.session.commit()
        return jsonify({
            "id": new_constraint.id,
            "description": new_constraint.description,
            "file_path": new_constraint.file_path
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@constraints_bp.route('/<int:activity_id>/<int:constraint_id>', methods=['PUT'])
def update_constraint(activity_id, constraint_id):
    """
    Modifie une contrainte existante sur l'activité <activity_id>.
    JSON attendu : { "description": "<str>" }
    """
    data = request.get_json() or {}
    new_desc = data.get("description", "").strip()
    if not new_desc:
        return jsonify({"error": "description is required"}), 400

    constraint_obj = Constraint.query.filter_by(id=constraint_id, activity_id=activity_id).first()
    if not constraint_obj:
        return jsonify({"error": "Constraint not found for this activity"}), 404

    try:
        constraint_obj.description = new_desc
        if "file_path" in data:
            constraint_obj.file_path = (data["file_path"] or "").strip() or None
        db.session.commit()
        return jsonify({
            "id": constraint_obj.id,
            "description": constraint_obj.description,
            "file_path": constraint_obj.file_path
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@constraints_bp.route('/<int:activity_id>/<int:constraint_id>', methods=['DELETE'])
def delete_constraint(activity_id, constraint_id):
    """
    Supprime une contrainte existante de l'activité <activity_id>.
    """
    constraint_obj = Constraint.query.filter_by(id=constraint_id, activity_id=activity_id).first()
    if not constraint_obj:
        return jsonify({"error": "Constraint not found for this activity"}), 404

    try:
        db.session.delete(constraint_obj)
        db.session.commit()
        return jsonify({"message": "Constraint deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# -----------------------------
# NOUVELLE ROUTE : Rendu partiel des contraintes
# -----------------------------
@constraints_bp.route('/<int:activity_id>/render', methods=['GET'])
def render_constraints(activity_id):
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activité non trouvée"}), 404
    return render_template('constraints_partial.html', activity=activity)
