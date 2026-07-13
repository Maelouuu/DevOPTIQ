# Code/routes/savoirs.py

from flask import Blueprint, request, jsonify, render_template, session
from Code.extensions import db
from Code.models.models import Activities, Savoir

# Utiliser un préfixe différent pour le blueprint, si nécessaire, mais ici on garde '/savoirs'
savoirs_bp = Blueprint('savoirs_bp', __name__, url_prefix='/savoirs')


def _require_auth():
    if not session.get('user_id'):
        return jsonify({"error": "Non connecté"}), 401
    return None


@savoirs_bp.route('/add', methods=['POST'])
def add_savoir():
    """
    Ajoute un "Savoir" à l'activité <activity_id>.
    JSON attendu : { "description": "<str>", "activity_id": <int> }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    data = request.get_json() or {}
    desc = data.get("description", "").strip()
    activity_id = data.get("activity_id")
    if not desc or not activity_id:
        return jsonify({"error": "description and activity_id are required"}), 400

    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    try:
        new_savoir = Savoir(description=desc, activity_id=activity_id)
        db.session.add(new_savoir)
        db.session.commit()
        return jsonify({
            "id": new_savoir.id,
            "description": new_savoir.description
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@savoirs_bp.route('/<int:activity_id>/<int:savoir_id>', methods=['PUT'])
def update_savoir(activity_id, savoir_id):
    """
    Met à jour un "Savoir" existant sur l'activité <activity_id>.
    JSON attendu : { "description": "<str>" }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    data = request.get_json() or {}
    new_desc = data.get("description", "").strip()
    if not new_desc:
        return jsonify({"error": "description is required"}), 400

    savoir_obj = Savoir.query.filter_by(id=savoir_id, activity_id=activity_id).first()
    if not savoir_obj:
        return jsonify({"error": "Savoir not found for this activity"}), 404

    try:
        savoir_obj.description = new_desc
        db.session.commit()
        return jsonify({
            "id": savoir_obj.id,
            "description": savoir_obj.description
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@savoirs_bp.route('/<int:activity_id>/<int:savoir_id>', methods=['DELETE'])
def delete_savoir(activity_id, savoir_id):
    """
    Supprime un "Savoir" existant de l'activité <activity_id>.
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    savoir_obj = Savoir.query.filter_by(id=savoir_id, activity_id=activity_id).first()
    if not savoir_obj:
        return jsonify({"error": "Savoir not found"}), 404

    try:
        db.session.delete(savoir_obj)
        db.session.commit()
        return jsonify({"message": "Savoir deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@savoirs_bp.route('/<int:activity_id>/render', methods=['GET'])
def render_savoirs(activity_id):
    """
    Retourne le fragment HTML affichant la liste des "Savoirs" d'une activité
    pour être inclus dynamiquement (type partial).
    """
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activité non trouvée"}), 404
    return render_template('activity_savoirs.html', activity=activity)
