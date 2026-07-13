import re
from flask import Blueprint, request, jsonify, render_template, session
from sqlalchemy import func
from Code.extensions import db
from Code.models.models import Softskill, Activities

softskills_crud_bp = Blueprint("softskills_crud_bp", __name__, url_prefix="/softskills")


def _require_auth():
    if not session.get('user_id'):
        return jsonify({"error": "Non connecté"}), 401
    return None


# ==========================================================
# AJOUT MANUEL
# ==========================================================
@softskills_crud_bp.route("/add", methods=["POST"])
def add_softskill():
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    data = request.get_json() or {}

    activity_id = data.get("activity_id")
    habilete = (data.get("habilete") or "").strip()
    niveau = (data.get("niveau") or "").strip()
    justification = (data.get("justification") or "").strip()

    if not activity_id or not habilete or not niveau:
        return jsonify({"error": "activity_id, habilete et niveau sont obligatoires"}), 400

    try:
        existing = Softskill.query.filter(
            func.lower(Softskill.habilete) == habilete.lower(),
            Softskill.activity_id == activity_id,
        ).first()

        if existing:
            existing.habilete = habilete
            existing.niveau = niveau
            existing.justification = justification
            db.session.commit()

            return jsonify({
                "id": existing.id,
                "activity_id": existing.activity_id,
                "habilete": existing.habilete,
                "niveau": existing.niveau,
                "justification": existing.justification or ""
            }), 200

        new_ss = Softskill(
            activity_id=activity_id,
            habilete=habilete,
            niveau=niveau,
            justification=justification,
        )
        db.session.add(new_ss)
        db.session.commit()

        return jsonify({
            "id": new_ss.id,
            "activity_id": new_ss.activity_id,
            "habilete": new_ss.habilete,
            "niveau": new_ss.niveau,
            "justification": new_ss.justification or ""
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================================================
# MODIFICATION (nouvelle route !)
# ==========================================================
@softskills_crud_bp.route("/<int:activity_id>/<int:ss_id>", methods=["PUT"])
def update_softskill(activity_id, ss_id):
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    data = request.get_json() or {}

    habilete = (data.get("habilete") or "").strip()
    niveau = (data.get("niveau") or "").strip()
    justification = (data.get("justification") or "").strip()

    if not habilete or not niveau:
        return jsonify({"error": "habilete et niveau sont obligatoires"}), 400

    ss = Softskill.query.get(ss_id)
    if not ss or ss.activity_id != activity_id:
        return jsonify({"error": "Softskill introuvable"}), 404

    try:
        ss.habilete = habilete
        ss.niveau = niveau
        ss.justification = justification
        db.session.commit()

        return jsonify({
            "id": ss.id,
            "activity_id": ss.activity_id,
            "habilete": ss.habilete,
            "niveau": ss.niveau,
            "justification": ss.justification or ""
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================================================
# SUPPRESSION (nouvelle route !)
# ==========================================================
@softskills_crud_bp.route("/<int:activity_id>/<int:ss_id>", methods=["DELETE"])
def delete_softskill(activity_id, ss_id):
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    ss = Softskill.query.get(ss_id)

    if not ss:
        return jsonify({"error": "Softskill not found"}), 404

    # 🔥 Correction majeure : on vérifie que la HSC appartient à l’activité
    if ss.activity_id != activity_id:
        return jsonify({"error": "Mismatch activity_id"}), 404

    try:
        db.session.delete(ss)
        db.session.commit()
        return jsonify({"message": "Softskill deleted"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500




# ==========================================================
# RENDU PARTIEL (RAFRAÎCHISSEMENT)
# ==========================================================
@softskills_crud_bp.route("/<int:activity_id>/render", methods=["GET"])
def render_softskills_partial(activity_id):
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activité non trouvée"}), 404

    return render_template("softskills_partial.html", activity=activity)
