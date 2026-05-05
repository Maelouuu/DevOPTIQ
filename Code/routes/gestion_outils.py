# Code/routes/gestion_outils.py
from flask import Blueprint, render_template, jsonify, request, abort
from sqlalchemy import func
from Code.extensions import db
from Code.models.models import Tool, Task, Activities, task_tools, Entity

bp_tools = Blueprint("gestion_outils", __name__, url_prefix="/gestion_outils")


# -------------------------
# Page HTML
# -------------------------
@bp_tools.route("/", methods=["GET"])
def page():
    return render_template("gestion_outils.html")


# -------------------------
# API: Lister les outils + usages
# -------------------------
@bp_tools.route("/api/tools", methods=["GET"])
def list_tools():
    # MODIFIÉ: Filtrer par entité active
    tools = Tool.for_active_entity().order_by(func.lower(Tool.name)).all()

    # Précharger les usages: tasks + activity
    usages_by_tool = {t.id: [] for t in tools}
    if tools:
        tool_ids = [t.id for t in tools]

        rows = (
            db.session.query(
                task_tools.c.tool_id.label("tool_id"),
                Task.id.label("task_id"),
                Task.name.label("task_name"),
                Activities.id.label("activity_id"),
                Activities.name.label("activity_name"),
            )
            .join(Task, Task.id == task_tools.c.task_id)
            .join(Activities, Activities.id == Task.activity_id)
            .filter(task_tools.c.tool_id.in_(tool_ids))
            .order_by(func.lower(Activities.name), func.lower(Task.name))
            .all()
        )
        for r in rows:
            usages_by_tool[r.tool_id].append({
                "task_id": r.task_id,
                "task_name": r.task_name,
                "activity_id": r.activity_id,
                "activity_name": r.activity_name
            })

    data = []
    for t in tools:
        data.append({
            "id": t.id,
            "name": t.name,
            "description": t.description or "",
            "file_path": t.file_path or "",
            "usages": usages_by_tool.get(t.id, [])
        })
    return jsonify(data)


# -------------------------
# API: Créer un outil
# -------------------------
@bp_tools.route("/api/tools", methods=["POST"])
def create_tool():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip() or None
    file_path = (payload.get("file_path") or "").strip() or None

    if not name:
        return jsonify({"error": "Le nom de l'outil est requis."}), 400

    # MODIFIÉ: Unicité par entité active
    exists = Tool.for_active_entity().filter(func.lower(Tool.name) == func.lower(name)).first()
    if exists:
        return jsonify({"error": "Un outil avec ce nom existe déjà."}), 409

    # MODIFIÉ: Créer l'outil avec l'entité active
    active_entity_id = Entity.get_active_id()
    tool = Tool(name=name, description=description, file_path=file_path, entity_id=active_entity_id)
    db.session.add(tool)
    db.session.commit()
    return jsonify({"message": "Outil créé.", "id": tool.id}), 201


# -------------------------
# API: Renommer / modifier la description d'un outil
# -------------------------
@bp_tools.route("/api/tools/<int:tool_id>", methods=["PUT"])
def update_tool(tool_id):
    tool = Tool.query.get_or_404(tool_id)
    payload = request.get_json(silent=True) or {}

    new_name = payload.get("name")
    new_desc = payload.get("description")

    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            return jsonify({"error": "Le nom ne peut pas être vide."}), 400

        # MODIFIÉ: Vérifier unicité par entité active (hors l'outil courant)
        exists = (
            Tool.for_active_entity()
            .filter(func.lower(Tool.name) == func.lower(new_name), Tool.id != tool.id)
            .first()
        )
        if exists:
            return jsonify({"error": "Un autre outil avec ce nom existe déjà."}), 409

        tool.name = new_name

    if new_desc is not None:
        new_desc = new_desc.strip() or None
        tool.description = new_desc

    new_file = payload.get("file_path")
    if new_file is not None:
        tool.file_path = new_file.strip() or None

    db.session.commit()
    return jsonify({"message": "Outil mis à jour.", "file_path": tool.file_path})


# -------------------------
# API: Pré-alerte de suppression (liste des usages)
# -------------------------
@bp_tools.route("/api/tools/<int:tool_id>/usages", methods=["GET"])
def tool_usages(tool_id):
    tool = Tool.query.get_or_404(tool_id)
    rows = (
        db.session.query(
            Task.id.label("task_id"),
            Task.name.label("task_name"),
            Activities.id.label("activity_id"),
            Activities.name.label("activity_name"),
        )
        .join(task_tools, task_tools.c.task_id == Task.id)
        .join(Activities, Activities.id == Task.activity_id)
        .filter(task_tools.c.tool_id == tool.id)
        .order_by(func.lower(Activities.name), func.lower(Task.name))
        .all()
    )
    usages = [{
        "task_id": r.task_id,
        "task_name": r.task_name,
        "activity_id": r.activity_id,
        "activity_name": r.activity_name
    } for r in rows]
    return jsonify({
        "tool": {"id": tool.id, "name": tool.name},
        "usages": usages
    })


# -------------------------
# API: Remplacer un outil par un autre (reliage des usages)
# -------------------------
@bp_tools.route("/api/tools/<int:tool_id>/replace", methods=["POST"])
def replace_tool(tool_id):
    tool_src = Tool.query.get_or_404(tool_id)
    payload = request.get_json(silent=True) or {}
    replacement_id = payload.get("replacement_id")
    task_ids_filter = payload.get("task_ids")  # optionnel : liste de task_id ciblés

    if not replacement_id:
        return jsonify({"error": "replacement_id est requis."}), 400

    tool_dst = Tool.query.get(replacement_id)
    if not tool_dst:
        return jsonify({"error": "Outil de remplacement introuvable."}), 404

    if tool_src.id == tool_dst.id:
        return jsonify({"error": "Impossible de remplacer un outil par lui-même."}), 400

    # Trouver toutes les tasks liées à src
    all_linked = [
        r[0] for r in db.session.query(task_tools.c.task_id)
        .filter(task_tools.c.tool_id == tool_src.id).all()
    ]

    # Filtrer sur les task_ids sélectionnés si fournis
    if task_ids_filter is not None:
        task_ids = [tid for tid in all_linked if tid in task_ids_filter]
    else:
        task_ids = all_linked

    if task_ids:
        existing_pairs = set(
            db.session.query(task_tools.c.task_id)
            .filter(task_tools.c.tool_id == tool_dst.id, task_tools.c.task_id.in_(task_ids))
            .all()
        )
        existing_task_ids = {tid for (tid,) in existing_pairs}

        inserts = [{"task_id": tid, "tool_id": tool_dst.id}
                   for tid in task_ids if tid not in existing_task_ids]
        if inserts:
            db.session.execute(task_tools.insert(), inserts)

        db.session.execute(
            task_tools.delete().where(
                (task_tools.c.tool_id == tool_src.id) & (task_tools.c.task_id.in_(task_ids))
            )
        )

    db.session.commit()
    return jsonify({"message": f"Usages remplacés.", "replaced_count": len(task_ids)})


# -------------------------
# API: Supprimer un outil
#   - task_ids dans le corps JSON => détachement partiel
#   - force_detach=true          => détacher tout et supprimer
#   - sinon, si usages, renvoyer 409
# -------------------------
@bp_tools.route("/api/tools/<int:tool_id>", methods=["DELETE"])
def delete_tool(tool_id):
    tool = Tool.query.get_or_404(tool_id)
    force_detach = request.args.get("force_detach", "false").lower() == "true"

    payload = request.get_json(silent=True) or {}
    task_ids_filter = payload.get("task_ids")  # optionnel : liste de task_id à détacher

    # ── Détachement partiel ──
    if task_ids_filter is not None:
        db.session.execute(
            task_tools.delete().where(
                (task_tools.c.tool_id == tool.id) &
                (task_tools.c.task_id.in_(task_ids_filter))
            )
        )
        remaining = db.session.query(task_tools).filter(task_tools.c.tool_id == tool.id).count()
        db.session.commit()
        if remaining == 0:
            db.session.delete(tool)
            db.session.commit()
            return jsonify({"message": "Outil détaché et supprimé.", "deleted": True})
        return jsonify({
            "message": f"Détaché de {len(task_ids_filter)} tâche(s). {remaining} usage(s) restant(s).",
            "deleted": False,
            "remaining": remaining
        })

    # ── Suppression complète ──
    count_usages = db.session.query(task_tools).filter(task_tools.c.tool_id == tool.id).count()
    if count_usages > 0 and not force_detach:
        return jsonify({
            "error": "Cet outil est utilisé. Fournir force_detach=true pour détacher et supprimer.",
            "usages_count": count_usages
        }), 409

    if count_usages > 0:
        db.session.execute(task_tools.delete().where(task_tools.c.tool_id == tool.id))

    db.session.delete(tool)
    db.session.commit()
    return jsonify({"message": "Outil supprimé.", "deleted": True})
