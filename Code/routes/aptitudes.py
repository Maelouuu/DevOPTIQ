# Code/routes/aptitudes.py

from flask import Blueprint, request, jsonify, render_template, session
from Code.extensions import db
from Code.models.models import Activities, Aptitude


aptitudes_bp = Blueprint('aptitudes_bp', __name__, url_prefix='/aptitudes')


def _require_auth():
    if not session.get('user_id'):
        return jsonify({"error": "Non connecté"}), 401
    return None


@aptitudes_bp.route('/add', methods=['POST'])
def add_aptitude():
    """
    Ajoute une "Aptitude" à l'activité <activity_id>.
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
        new_ap = Aptitude(description=desc, activity_id=activity_id)
        db.session.add(new_ap)
        db.session.commit()
        return jsonify({
            "id": new_ap.id,
            "description": new_ap.description
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@aptitudes_bp.route('/<int:activity_id>/<int:aptitudes_id>', methods=['PUT'])
def update_aptitude(activity_id, aptitudes_id):
    """
    Met à jour une "Aptitude" existante sur l'activité <activity_id>.
    JSON attendu : { "description": "<str>" }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    data = request.get_json() or {}
    new_desc = data.get("description", "").strip()
    if not new_desc:
        return jsonify({"error": "description is required"}), 400

    ap_obj = Aptitude.query.filter_by(id=aptitudes_id, activity_id=activity_id).first()
    if not ap_obj:
        return jsonify({"error": "Aptitude not found"}), 404

    try:
        ap_obj.description = new_desc
        db.session.commit()
        return jsonify({
            "id": ap_obj.id,
            "description": ap_obj.description
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@aptitudes_bp.route('/<int:activity_id>/<int:aptitudes_id>', methods=['DELETE'])
def delete_aptitude(activity_id, aptitudes_id):
    """
    Supprime une "Aptitude" existant de l'activité <activity_id>.
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    aptitudes_obj = Aptitude.query.filter_by(id=aptitudes_id, activity_id=activity_id).first()
    if not aptitudes_obj:
        return jsonify({"error": "Aptitude not found"}), 404

    try:
        db.session.delete(aptitudes_obj)
        db.session.commit()
        return jsonify({"message": "Aptitude deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@aptitudes_bp.route('/<int:activity_id>/render', methods=['GET'])
def render_aptitudes(activity_id):
    """
    Retourne le fragment HTML affichant la liste des "Aptitudes" d'une activité
    pour être inclus dynamiquement (type partial).
    """
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activité non trouvée"}), 404
    return render_template('activity_aptitudes.html', activity=activity)
