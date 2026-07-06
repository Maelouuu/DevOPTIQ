from flask import request, jsonify
from .activities_bp import activities_bp
from Code.extensions import db
from Code.models.models import Task
import traceback

from .activities_performance import add_performance, update_performance, delete_performance

@activities_bp.route("/performance/add", methods=["POST"])
def add_perf():
    data = request.get_json(silent=True) or {}
    if not data.get("link_id") or not data.get("name"):
        return jsonify({"error": "link_id et name sont requis"}), 400
    return add_performance(data["link_id"], data["name"], data.get("description",""))

@activities_bp.route("/performance/<int:perf_id>", methods=["PUT"])
def update_perf(perf_id):
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name est requis"}), 400
    return update_performance(perf_id, data["name"], data.get("description",""))

@activities_bp.route("/performance/<int:perf_id>", methods=["DELETE"])
def delete_perf(perf_id):
    return delete_performance(perf_id)

@activities_bp.route('/<int:activity_id>/tasks/reorder', methods=['POST'])
def reorder_tasks(activity_id):
    """
    Gère le drag&drop (ordre des tâches).
    JSON: { "order": [12, 13, 15] }
    """
    data = request.get_json() or {}
    new_order = data.get('order')
    if not new_order:
        return jsonify({"error": "order list is required"}), 400
    try:
        for idx, t_id in enumerate(new_order):
            task = Task.query.filter_by(id=t_id, activity_id=activity_id).first()
            if task:
                task.order = idx
        db.session.commit()
        return jsonify({"message": "Order updated"}), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
