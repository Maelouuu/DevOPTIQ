"""Blueprint OptiqCarto — éditeur de cartographie intégré à DevOPTIQ.

La carto JSON de chaque entité est stockée en base de données (colonne
Entity.optiqcarto_data) pour survivre aux redémarrages Cloud Run.
Le fichier VSDX reste sur disque (upload ponctuel, non critique).
"""
import json
import os
import tempfile

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
from Code.models.models import Activity, Entity, Link, Role, activity_roles

cartography_editor_bp = Blueprint("cartography_editor", __name__, url_prefix="/cartography")

# Répertoire de base des entités (pour les fichiers VSDX uploadés)
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


def _has_carto(entity) -> bool:
    """Retourne True si l'entité a une carto OptiqCarto enregistrée en base."""
    return bool(entity and entity.optiqcarto_data)


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
# PAGES
# ─────────────────────────────────────────────

@cartography_editor_bp.route("/viewer")
def viewer():
    if not _require_auth():
        return ("", 403)
    entity = _get_active_entity()
    has_optiqcarto = _has_carto(entity)
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
        has_optiqcarto = _has_carto(entity)

    return render_template(
        "cartography_editor.html",
        entity_name=entity_name,
        entity_id=entity_id,
        has_vsdx=has_vsdx,
        has_optiqcarto=has_optiqcarto,
    )


# ─────────────────────────────────────────────
# CARTO → DB SYNC HELPERS
# ─────────────────────────────────────────────

_ACTIVITY_TYPES = {'process', 'start-end', 'special'}
_BANDS_START_Y  = -200  # matches editor.js getBandForY()


def _get_band_for_y(bands, mid_y):
    """Return the band dict that contains mid_y, or None."""
    y = _BANDS_START_Y
    for band in bands:
        h = band.get('height', 180)
        if y <= mid_y < y + h:
            return band
        y += h
    return None


def _compute_removals(entity, new_diagram):
    """Dry-run: return names that would be deleted if new_diagram is saved."""
    new_shapes = new_diagram.get('shapes', [])
    new_bands  = new_diagram.get('bands',  [])

    new_shape_ids  = {str(s['id']) for s in new_shapes if s.get('type') in _ACTIVITY_TYPES}
    new_band_names = {(b.get('label') or '').strip() for b in new_bands}

    existing_acts  = Activity.query.filter_by(entity_id=entity.id).filter(
        Activity.shape_id.isnot(None)
    ).all()
    existing_roles = Role.query.filter_by(entity_id=entity.id).all()

    removed_activities = [a.name for a in existing_acts  if str(a.shape_id) not in new_shape_ids]
    removed_roles      = [r.name for r in existing_roles if r.name not in new_band_names]
    return {'removed_activities': removed_activities, 'removed_roles': removed_roles}


def _sync_carto_to_db(entity, diagram):
    """Full re-extraction: upsert activities, roles, links from the carto diagram."""
    shapes      = diagram.get('shapes',      [])
    bands       = diagram.get('bands',       [])
    connections = diagram.get('connections', [])

    act_shapes = [s for s in shapes if s.get('type') in _ACTIVITY_TYPES]

    # ── Activities ────────────────────────────────────────────────────────────
    existing_acts = {a.shape_id: a for a in
                     Activity.query.filter_by(entity_id=entity.id).filter(
                         Activity.shape_id.isnot(None)).all()}

    new_shape_ids  = {str(s['id']) for s in act_shapes}
    shape_to_act   = {}  # str(shape_id) → Activity

    for s in act_shapes:
        sid   = str(s['id'])
        label = (s.get('label') or '').strip()
        is_result = s.get('type') == 'special'

        if sid in existing_acts:
            act = existing_acts[sid]
            act.name      = label
            act.is_result = is_result
        else:
            act = Activity(entity_id=entity.id, shape_id=sid,
                           name=label, is_result=is_result)
            db.session.add(act)
        shape_to_act[sid] = act

    for sid, act in existing_acts.items():
        if sid not in new_shape_ids:
            db.session.delete(act)

    db.session.flush()  # assign IDs to new activities

    # ── Roles (bands) ─────────────────────────────────────────────────────────
    existing_roles = {r.name: r for r in Role.query.filter_by(entity_id=entity.id).all()}
    new_band_names = {(b.get('label') or '').strip() for b in bands}
    band_to_role   = {}  # band id → Role

    for band in bands:
        name = (band.get('label') or '').strip()
        if name in existing_roles:
            role = existing_roles[name]
        else:
            role = Role(entity_id=entity.id, name=name)
            db.session.add(role)
        band_to_role[band['id']] = role

    for name, role in existing_roles.items():
        if name not in new_band_names:
            db.session.delete(role)

    db.session.flush()

    # ── Activity-Role associations ────────────────────────────────────────────
    act_ids = [a.id for a in shape_to_act.values() if a.id]
    if act_ids:
        db.session.execute(
            activity_roles.delete().where(activity_roles.c.activity_id.in_(act_ids))
        )

    for s in act_shapes:
        sid = str(s['id'])
        act = shape_to_act.get(sid)
        if not act or not act.id:
            continue
        mid_y = s.get('y', 0) + s.get('h', 0) / 2
        band  = _get_band_for_y(bands, mid_y)
        if not band:
            continue
        role = band_to_role.get(band['id'])
        if role and role.id:
            db.session.execute(activity_roles.insert().values(
                activity_id=act.id, role_id=role.id, status='garant'
            ))

    # ── Links (connections) ───────────────────────────────────────────────────
    # Delete all carto-derived links for this entity, then re-insert
    Link.query.filter_by(entity_id=entity.id).filter(
        Link.source_activity_id.isnot(None),
        Link.target_activity_id.isnot(None),
    ).delete()

    for conn in connections:
        from_sid = str(conn.get('fromId', ''))
        to_sid   = str(conn.get('toId',   ''))
        from_act = shape_to_act.get(from_sid)
        to_act   = shape_to_act.get(to_sid)
        if not from_act or not to_act or not from_act.id or not to_act.id:
            continue
        label = (conn.get('label') or '').strip()
        db.session.add(Link(
            entity_id=entity.id,
            source_activity_id=from_act.id,
            target_activity_id=to_act.id,
            type=label or 'flux',
            description=label or None,
        ))

    db.session.commit()


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

    data    = request.get_json(force=True)
    diagram = data.get("diagram", data)  # accepte {diagram: ...} ou le state direct

    entity.optiqcarto_data = json.dumps(diagram, ensure_ascii=False)
    db.session.commit()

    # Re-extract activities / roles / links from the saved diagram
    try:
        _sync_carto_to_db(entity, diagram)
    except Exception as exc:
        # Non-blocking: the carto is saved; sync failure is logged only
        import traceback
        traceback.print_exc()

    return jsonify({"ok": True, "name": entity.name or f"entity_{entity.id}"})


@cartography_editor_bp.route("/api/save-diff", methods=["POST"])
def api_save_diff():
    """Return what would be removed if the given diagram is saved (no commit)."""
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    if not entity.optiqcarto_data:
        return jsonify({"removed_activities": [], "removed_roles": []})

    data    = request.get_json(force=True)
    diagram = data.get("diagram", data)
    return jsonify(_compute_removals(entity, diagram))


@cartography_editor_bp.route("/api/load/<name>")
def api_load(name):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    if not entity.optiqcarto_data:
        return jsonify({"error": "Introuvable"}), 404

    return jsonify(json.loads(entity.optiqcarto_data))


@cartography_editor_bp.route("/api/list")
def api_list():
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify([])

    if entity.optiqcarto_data:
        return jsonify([entity.name or f"entity_{entity.id}"])
    return jsonify([])


@cartography_editor_bp.route("/api/delete/<name>", methods=["DELETE"])
def api_delete(name):
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    entity.optiqcarto_data = None
    db.session.commit()

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


@cartography_editor_bp.route("/api/vsdx-compare", methods=["POST"])
def api_vsdx_compare():
    """Compare un fichier VSDX uploadé avec la carto sauvegardée dans notre outil."""
    if not _require_auth():
        return jsonify({"error": "Non autorisé"}), 403

    entity = _get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    if not entity.optiqcarto_data:
        return jsonify({"error": "Aucune cartographie sauvegardée pour cette entité"}), 404

    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".vsdx"):
        return jsonify({"error": "Format invalide (attendu .vsdx)"}), 400

    tmp = tempfile.NamedTemporaryFile(suffix=".vsdx", delete=False)
    try:
        f.save(tmp.name)
        tmp.close()

        from Code.routes.vsdx_conection_parser import (
            VsdxConnectionParser,
            normalize_activity_name,
        )

        parser = VsdxConnectionParser(tmp.name)
        connections, errors = parser.parse()

        vsdx_activities = set(
            normalize_activity_name(a) for a in parser.get_unique_activities()
        )
        vsdx_connections = set(
            (normalize_activity_name(c["source_name"]), normalize_activity_name(c["target_name"]))
            for c in connections
        )

        carto = json.loads(entity.optiqcarto_data)
        carto_shapes = carto.get("shapes", [])
        carto_conns = carto.get("connections", [])

        shape_labels = {s["id"]: (s.get("label") or "").strip() for s in carto_shapes}

        # Map norm_label → type pour les activités (pour diagnostic des écarts)
        norm_to_type = {}
        for s in carto_shapes:
            if s.get("type") != "decision" and (s.get("label") or "").strip():
                norm = normalize_activity_name(s.get("label", ""))
                # Si la même étiquette existe en process et start-end, on garde process
                existing = norm_to_type.get(norm)
                if not existing or s.get("type") == "process":
                    norm_to_type[norm] = s.get("type", "process")

        carto_activities = set(norm_to_type.keys())

        carto_connections = set()
        for c in carto_conns:
            fl = shape_labels.get(c.get("fromId"), "")
            tl = shape_labels.get(c.get("toId"), "")
            if fl and tl:
                carto_connections.add((normalize_activity_name(fl), normalize_activity_name(tl)))

        matched_act = carto_activities & vsdx_activities
        only_carto_act = sorted(carto_activities - vsdx_activities)
        only_vsdx_act = sorted(vsdx_activities - carto_activities)

        # Comptage par type des shapes de notre carto pour expliquer l'écart avec le VSDX
        type_counts = {}
        for s in carto_shapes:
            t = s.get("type", "process")
            type_counts[t] = type_counts.get(t, 0) + 1

        matched_conn = carto_connections & vsdx_connections
        only_carto_conn = sorted(carto_connections - vsdx_connections)
        only_vsdx_conn = sorted(vsdx_connections - carto_connections)

        # Bidirectional: extra activities/connections in carto also reduce compatibility
        ref_act = max(len(vsdx_activities), len(carto_activities), 1)
        ref_conn = max(len(vsdx_connections), len(carto_connections), 1)
        compat_act = round(len(matched_act) / ref_act * 100)
        compat_conn = round(len(matched_conn) / ref_conn * 100)
        compat_global = round(
            (len(matched_act) + len(matched_conn))
            / max(ref_act + ref_conn, 1)
            * 100
        )

        return jsonify({
            "compatibility": {
                "global": compat_global,
                "activities": compat_act,
                "connections": compat_conn,
            },
            "counts": {
                "vsdx_activities": len(vsdx_activities),
                "carto_activities": len(carto_activities),
                "matched_activities": len(matched_act),
                "extra_activities": len(only_carto_act),   # in carto but not in VSDX
                "missing_activities": len(only_vsdx_act),  # in VSDX but not in carto
                "vsdx_connections": len(vsdx_connections),
                "carto_connections": len(carto_connections),
                "matched_connections": len(matched_conn),
                "extra_connections": len(only_carto_conn),
                "missing_connections": len(only_vsdx_conn),
                # Détail par type des shapes dans notre carto (aide à expliquer l'écart)
                "carto_shapes_by_type": type_counts,
            },
            "differences": {
                "activities_only_in_carto": [
                    {"label": lbl, "type": norm_to_type.get(lbl, "process")}
                    for lbl in only_carto_act
                ],
                "activities_only_in_vsdx": only_vsdx_act,
                "connections_only_in_carto": [[a, b] for a, b in only_carto_conn],
                "connections_only_in_vsdx": [[a, b] for a, b in only_vsdx_conn],
            },
            "parse_errors": errors,
        })
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
