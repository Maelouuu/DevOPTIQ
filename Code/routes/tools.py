import json
import json
from flask import Blueprint, request, jsonify, session
from Code.extensions import db
from Code.models.models import Task, Tool, Entity, RecentEvent
from sqlalchemy import func

tools_bp = Blueprint('tools', __name__, url_prefix='/tools')

@tools_bp.route('/add', methods=['POST'])
def add_tools_to_task():
    data = request.get_json()
    if not data or 'task_id' not in data:
        return jsonify({"error": "task_id is required"}), 400

    task = Task.query.get(data['task_id'])
    if not task:
        return jsonify({"error": "Task not found"}), 404

    added_tools = []
    try:
        # (1) Associer des outils existants via leurs IDs
        if 'existing_tool_ids' in data and isinstance(data['existing_tool_ids'], list):
            for tool_id in data['existing_tool_ids']:
                tool = Tool.query.get(tool_id)
                if tool and tool not in task.tools:
                    task.tools.append(tool)
                    added_tools.append({"id": tool.id, "name": tool.name})
        # (2) Créer ou associer de nouveaux outils par leur nom
        if 'new_tools' in data and isinstance(data['new_tools'], list):
            for tool_name in data['new_tools']:
                if tool_name:
                    # MODIFIÉ: Vérifier si un outil du même nom existe déjà pour l'entité active
                    tool = Tool.for_active_entity().filter(func.lower(Tool.name) == tool_name.lower()).first()
                    if not tool:
                        # MODIFIÉ: Créer l'outil avec l'entité active
                        active_entity_id = Entity.get_active_id()
                        tool = Tool(name=tool_name, entity_id=active_entity_id)
                        db.session.add(tool)
                        db.session.flush()  # obtenir l'id du nouvel outil
                    if tool not in task.tools:
                        task.tools.append(tool)
                        added_tools.append({"id": tool.id, "name": tool.name})
        # Log tool-task associations
        for t in added_tools:
            try:
                ev = RecentEvent(
                    event_type='tool_linked',
                    icon='fa-solid fa-link',
                    label=f'Outil associé : {t["name"]}',
                    detail=json.dumps({"tool": t["name"], "task": task.name}, ensure_ascii=False),
                    user_id=session.get('user_id'),
                )
                db.session.add(ev)
            except Exception:
                pass
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"task_id": task.id, "added_tools": added_tools}), 200

@tools_bp.route('/all', methods=['GET'])
def get_all_tools():
    # MODIFIÉ: Filtrer par entité active
    tools = Tool.for_active_entity().order_by(Tool.name).all()
    return jsonify([{'id': tool.id, 'name': tool.name, 'file_path': tool.file_path or ''} for tool in tools])

@tools_bp.route('/delete', methods=['POST'])
def delete_tool_from_task():
    data = request.get_json()
    if not data or 'task_id' not in data or 'tool_id' not in data:
        return jsonify({"error": "task_id and tool_id are required"}), 400

    task_id = data['task_id']
    tool_id = data['tool_id']

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    tool = Tool.query.get(tool_id)
    if not tool:
        return jsonify({"error": "Tool not found"}), 404

    if tool not in task.tools:
        return jsonify({"error": "Tool is not associated with this task"}), 404

    try:
        task.tools.remove(tool)
        db.session.commit()
        return jsonify({"message": "Tool removed from task"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
