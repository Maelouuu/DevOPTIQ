# Code/routes/task_link_assignments.py
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from Code.extensions import db

task_links_bp = Blueprint('task_links', __name__, url_prefix='/task-links')

_table_ensured = False


def ensure_table():
    """Crée la table task_link_assignments via SQLAlchemy (compatible SQLite + PostgreSQL)."""
    global _table_ensured
    if _table_ensured:
        return
    try:
        from Code.models.models import TaskLinkAssignment
        TaskLinkAssignment.__table__.create(db.engine, checkfirst=True)
        _table_ensured = True
    except Exception:
        pass


@task_links_bp.route('/assign', methods=['POST'])
def assign():
    ensure_table()
    data = request.get_json(force=True) or {}
    link_id = data.get('link_id')
    task_id = data.get('task_id')
    direction = data.get('direction')

    if not link_id or not task_id or not direction:
        return jsonify({"error": "link_id, task_id et direction sont requis"}), 400

    try:
        db.session.execute(
            text("DELETE FROM task_link_assignments WHERE link_id = :lid AND direction = :dir"),
            {"lid": link_id, "dir": direction}
        )
        db.session.execute(
            text("INSERT INTO task_link_assignments (link_id, task_id, direction) VALUES (:lid, :tid, :dir)"),
            {"lid": link_id, "tid": task_id, "dir": direction}
        )
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@task_links_bp.route('/<int:link_id>/<direction>', methods=['DELETE'])
def unassign(link_id, direction):
    ensure_table()
    try:
        db.session.execute(
            text("DELETE FROM task_link_assignments WHERE link_id = :lid AND direction = :dir"),
            {"lid": link_id, "dir": direction}
        )
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@task_links_bp.route('/activity/<int:activity_id>', methods=['GET'])
def get_assignments(activity_id):
    ensure_table()
    try:
        rows = db.session.execute(text("""
            SELECT tla.link_id, tla.task_id, tla.direction
            FROM task_link_assignments tla
            JOIN tasks t ON t.id = tla.task_id
            WHERE t.activity_id = :aid
        """), {"aid": activity_id}).fetchall()
        return jsonify([{"link_id": r[0], "task_id": r[1], "direction": r[2]} for r in rows])
    except Exception:
        db.session.rollback()
        return jsonify([])
