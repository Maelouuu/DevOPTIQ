# Code/routes/savoir_faires.py

from flask import Blueprint, request, jsonify, render_template, abort, session
from Code.extensions import db
from Code.models.models import Activities, SavoirFaire

# Blueprint pour les savoir-faires
# (on garde le même nom de variable/endpoint pour ne pas casser les url_for éventuels)
savoir_faires_bp = Blueprint('savoir_faires_bp', __name__, url_prefix='/savoir_faires')


def _require_auth():
    if not session.get('user_id'):
        return jsonify({"error": "Non connecté"}), 401
    return None


@savoir_faires_bp.route('/add', methods=['POST'])
def add_savoir_faires():
    """
    Ajoute des 'SavoirFaire' à une activité.
    Deux formats JSON sont acceptés :

    1) Ajout unitaire :
       {
         "activity_id": <int>,
         "description": "<str>"
       }

    2) Ajout en lot (depuis la modale de propositions) :
       {
         "activity_id": <int>,
         "savoir_faires": ["<str>", "<str>", ...]
       }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    data = request.get_json(silent=True) or {}
    activity_id = data.get("activity_id")

    if not activity_id:
        return jsonify({"error": "activity_id is required"}), 400

    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({"error": "Activity not found"}), 404

    # Cas 2 : ajout en lot
    items = data.get("savoir_faires")
    if isinstance(items, list):
        created = []
        try:
            for raw in items:
                desc = (raw or "").strip()
                if not desc:
                    continue
                sf = SavoirFaire(description=desc, activity_id=activity_id)
                db.session.add(sf)
                created.append(sf)
            db.session.commit()
            return jsonify({
                "created": len(created),
                "items": [{"id": sf.id, "description": sf.description} for sf in created]
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    # Cas 1 : ajout unitaire
    desc = (data.get("description") or "").strip()
    if not desc:
        return jsonify({"error": "description is required"}), 400

    try:
        new_sf = SavoirFaire(description=desc, activity_id=activity_id)
        db.session.add(new_sf)
        db.session.commit()
        return jsonify({
            "id": new_sf.id,
            "description": new_sf.description
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@savoir_faires_bp.route('/<int:activity_id>/<int:savoir_faires_id>', methods=['PUT'])
def update_savoir_faires(activity_id, savoir_faires_id):
    """
    Met à jour un 'SavoirFaire' existant sur l'activité <activity_id>.
    JSON attendu : { "description": "<str>" }
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    data = request.get_json(silent=True) or {}
    new_desc = (data.get("description") or "").strip()
    if not new_desc:
        return jsonify({"error": "description is required"}), 400

    sf_obj = SavoirFaire.query.filter_by(id=savoir_faires_id, activity_id=activity_id).first()
    if not sf_obj:
        return jsonify({"error": "SavoirFaire not found for this activity"}), 404

    try:
        sf_obj.description = new_desc
        db.session.commit()
        return jsonify({
            "id": sf_obj.id,
            "description": sf_obj.description
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@savoir_faires_bp.route('/<int:activity_id>/<int:savoir_faires_id>', methods=['DELETE'])
def delete_savoir_faires(activity_id, savoir_faires_id):
    """
    Supprime un 'SavoirFaire' existant de l'activité <activity_id>.
    """
    auth_error = _require_auth()
    if auth_error:
        return auth_error
    sf_obj = SavoirFaire.query.filter_by(id=savoir_faires_id, activity_id=activity_id).first()
    if not sf_obj:
        return jsonify({"error": "SavoirFaire not found"}), 404

    try:
        db.session.delete(sf_obj)
        db.session.commit()
        return jsonify({"message": "SavoirFaire deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@savoir_faires_bp.route('/<int:activity_id>/render', methods=['GET'])
def render_savoir_faires(activity_id):
    """
    Retourne le fragment HTML affichant la liste des 'SavoirFaire' d'une activité,
    pour inclusion dynamique (partial).
    """
    activity = Activities.query.get(activity_id)
    if not activity:
        abort(404, description="Activité non trouvée")

    # ⚠️ IMPORTANT : le template s'appelle 'activity_savoirs_faires.html'
    # (avec 'savoirs' au pluriel), pour correspondre à ton fichier existant.
    return render_template('sf_sv_body.html', activity=activity)
