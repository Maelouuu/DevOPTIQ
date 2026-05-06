"""Blueprint OptiqCarto — éditeur de cartographie intégré à DevOPTIQ.

Chaque entité active a sa propre carto JSON stockée dans :
  Code/static/entities/entity_{id}/optiqcarto.json
"""
import json
import os
import re

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from Code.extensions import db
from Code.models.models import Entity

cartography_editor_bp = Blueprint("cartography_editor", __name__, url_prefix="/cartography")

# Répertoire de base des entités (même endroit que les VSDX existants)
_ENTITIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "Code", "static", "entities"
)


def _require_auth():
    return bool(session.get("user_email"))


def _get_active_entity():
    user_id = session.get("user_id")
    entity_id = session.get("active_entity_id")
    if not user_id:
        return None
    if entity_id:
        e = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
        if e:
            return e
    return Entity.query.filter_by(owner_id=user_id).order_by(Entity.id.desc()).first()


def _carto_path(entity_id):
    folder = os.path.join(_ENTITIES_DIR, f"entity_{entity_id}")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "optiqcarto.json")


def _vsdx_path(entity):
    if not entity.vsdx_filename:
        return None
    candidates = [
        os.path.join(_ENTITIES_DIR, f"entity_{entity.id}", "connections.vsdx"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                     "Code", entity.vsdx_filename),
        entity.vsdx_filename,
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


# ─────────────────────────────────────────────
# PAGE ÉDITEUR
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/viewer")
def viewer():
    if not _require_auth():
        return ("", 403)
    entity = _get_active_entity()
    has_optiqcarto = bool(entity and os.path.exists(_carto_path(entity.id)))
    has_vsdx = bool(entity and _vsdx_path(entity))
    entity_name = entity.name if entity else ""
    return render_template(
        "cartography_viewer.html",
        entity_name=entity_name,
        entity_id=entity.id if entity else None,
        has_optiqcarto=has_optiqcarto,
        has_vsdx=has_vsdx,
    )


@cartography_editor_bp.route("/editor")
def editor():
    if not _require_auth():
        return redirect(url_for("auth.login"))

    entity = _get_active_entity()
    has_vsdx = False
    has_optiqcarto = False
    entity_name = ""
    entity_id = None

    if entity:
        entity_id = entity.id
        entity_name = entity.name or ""
        has_vsdx = bool(_vsdx_path(entity))
        has_optiqcarto = os.path.exists(_carto_path(entity.id))

    return render_template(
        "cartography_editor.html",
        entity_name=entity_name,
        entity_id=entity_id,
        has_vsdx=has_vsdx,
        has_optiqcarto=has_optiqcarto,
    )


# ─────────────────────────────────────────────
# API SAVE / LOAD / LIST / DELETE
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/api/save", methods=["POST"])
def api_save():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    data = request.get_json(force=True)
    diagram = data.get("diagram", data)  # accepte {diagram: ...} ou le state direct

    path = _carto_path(entity.id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(diagram, f, ensure_ascii=False, indent=2)

    return jsonify({"ok": True, "name": entity.name or f"entity_{entity.id}"})


@cartography_editor_bp.route("/api/load/<name>")
def api_load(name):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    path = _carto_path(entity.id)
    if not os.path.exists(path):
        return jsonify({"error": "Introuvable"}), 404

    with open(path, encoding="utf-8") as f:
        return jsonify(json.load(f))


@cartography_editor_bp.route("/api/list")
def api_list():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify([])

    path = _carto_path(entity.id)
    name = entity.name or f"entity_{entity.id}"
    if os.path.exists(path):
        return jsonify([name])
    return jsonify([])


@cartography_editor_bp.route("/api/delete/<name>", methods=["DELETE"])
def api_delete(name):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    path = _carto_path(entity.id)
    if os.path.exists(path):
        os.remove(path)

    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# SERVIR LE VSDX EXISTANT (pour auto-import migration)
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/api/vsdx")
def api_vsdx():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    path = _vsdx_path(entity)
    if not path:
        return jsonify({"error": "Aucun fichier VSDX"}), 404

    return send_file(path, mimetype="application/octet-stream",
                     download_name="connections.vsdx")
