# Code/routes/tasks.py

from flask import Blueprint, request, jsonify, render_template
from sqlalchemy import text
from Code.extensions import db
from Code.models.models import Task, Activities, Role, task_roles, Link, Data

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

@tasks_bp.route('/add', methods=['POST'])
def add_task():
    """
    Ajoute une tâche associée à une activité.
    Expects JSON with keys: activity_id, name, (optionnellement description et order).
    """
    data = request.get_json()
    if not data or 'activity_id' not in data or 'name' not in data:
        return jsonify({'error': 'Données invalides. "activity_id" et "name" sont requis.'}), 400

    activity = Activities.query.get(data['activity_id'])
    if not activity:
        return jsonify({'error': 'Activité non trouvée.'}), 404

    new_task = Task(
        name=data['name'],
        description=data.get('description', ''),
        order=data.get('order', None),
        activity_id=data['activity_id']
    )
    db.session.add(new_task)
    db.session.commit()

    return jsonify({
        'id': new_task.id,
        'name': new_task.name,
        'description': new_task.description,
        'order': new_task.order,
        'activity_id': new_task.activity_id
    }), 201


#
# -------------------------------------------------------
# Ici, on n’a plus la route de reorder => c’est dans activities.py
# -------------------------------------------------------


#
# -------------------------------------------------------
# NOUVELLES ROUTES POUR ASSOCIER DES RÔLES À LA TÂCHE
# -------------------------------------------------------
#
@tasks_bp.route('/<int:task_id>/roles/add', methods=['POST'])
def add_roles_to_task(task_id):
    """
    Ajoute un ou plusieurs rôles à une tâche, chacun avec le même statut.
    Ex: POST /tasks/42/roles/add
        {
          "existing_role_ids": [1, 2],
          "new_roles": ["Chef de projet", "Expert Contrôle"],
          "status": "Réalisateur"
        }
    """
    data = request.get_json() or {}
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    existing_role_ids = data.get('existing_role_ids', [])
    new_roles = data.get('new_roles', [])
    chosen_status = data.get('status', '').strip()
    if not chosen_status:
        return jsonify({"error": "A 'status' is required"}), 400

    added_roles = []

    try:
        # (1) Associer des rôles existants
        for rid in existing_role_ids:
            role_obj = Role.query.get(rid)
            if role_obj:
                # Vérifier si association déjà existante
                res = db.session.execute(
                    text("SELECT 1 FROM task_roles WHERE task_id=:tid AND role_id=:rid"),
                    {"tid": task_id, "rid": rid}
                ).fetchone()
                if not res:
                    db.session.execute(
                        text("""INSERT INTO task_roles (task_id, role_id, status)
                                VALUES (:tid, :rid, :st)"""),
                        {"tid": task_id, "rid": rid, "st": chosen_status}
                    )
                    added_roles.append({
                        "id": role_obj.id,
                        "name": role_obj.name,
                        "status": chosen_status
                    })

        # (2) Créer/associer de nouveaux rôles
        for role_name in new_roles:
            role_name = role_name.strip()
            if not role_name:
                continue
            existing_role = Role.query.filter_by(name=role_name).first()
            if not existing_role:
                new_role = Role(name=role_name)
                db.session.add(new_role)
                db.session.flush()  # pour obtenir l'id
                rid = new_role.id
                db.session.execute(
                    text("""INSERT INTO task_roles (task_id, role_id, status)
                            VALUES (:tid, :rid, :st)"""),
                    {"tid": task_id, "rid": rid, "st": chosen_status}
                )
                added_roles.append({
                    "id": new_role.id,
                    "name": new_role.name,
                    "status": chosen_status
                })
            else:
                rid = existing_role.id
                res = db.session.execute(
                    text("SELECT 1 FROM task_roles WHERE task_id=:tid AND role_id=:rid"),
                    {"tid": task_id, "rid": rid}
                ).fetchone()
                if not res:
                    db.session.execute(
                        text("""INSERT INTO task_roles (task_id, role_id, status)
                                VALUES (:tid, :rid, :st)"""),
                        {"tid": task_id, "rid": rid, "st": chosen_status}
                    )
                    added_roles.append({
                        "id": existing_role.id,
                        "name": existing_role.name,
                        "status": chosen_status
                    })

        db.session.commit()
        return jsonify({"task_id": task.id, "added_roles": added_roles}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@tasks_bp.route('/<int:task_id>/roles/<int:role_id>', methods=['DELETE'])
def delete_role_from_task(task_id, role_id):
    """
    Supprime un rôle associé à la tâche dans la table d'association task_roles.
    Ex: DELETE /tasks/42/roles/7
    """
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Vérifier existence association
    res = db.session.execute(
        text("SELECT status FROM task_roles WHERE task_id=:tid AND role_id=:rid"),
        {"tid": task_id, "rid": role_id}
    ).fetchone()
    if not res:
        return jsonify({"error": "This role is not associated with the task"}), 404

    try:
        db.session.execute(
            text("DELETE FROM task_roles WHERE task_id=:tid AND role_id=:rid"),
            {"tid": task_id, "rid": role_id}
        )
        db.session.commit()
        return jsonify({"message": f"Role {role_id} removed from task {task_id}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


#
# -----------------------------------------------
# ROUTE POUR LISTER LES RÔLES D'UNE TÂCHE
# -----------------------------------------------
#
@tasks_bp.route('/<int:task_id>/roles', methods=['GET'])
def get_roles_for_task(task_id):
    """
    Retourne la liste des rôles associés à la tâche <task_id>,
    avec le status de chacun.
    """
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Récupérer la liste des rôles via la table d'association task_roles
    results = db.session.execute(
        text("""
        SELECT r.id AS role_id, r.name AS role_name, tr.status AS role_status
        FROM roles r
        JOIN task_roles tr ON r.id = tr.role_id
        WHERE tr.task_id = :tid
        """),
        {"tid": task_id}
    ).fetchall()

    roles_list = []
    for row in results:
        roles_list.append({
            "id": row.role_id,
            "name": row.role_name,
            "status": row.role_status
        })

    return jsonify({
        "task_id": task_id,
        "roles": roles_list
    }), 200


# -----------------------------------------------
# Rendu partiel des tâches => tasks_partial.html
# -----------------------------------------------
@tasks_bp.route('/<int:activity_id>/render', methods=['GET'])
def render_tasks(activity_id):
    """
    Retourne le bloc HTML (partial) des tâches de l'activité <activity_id>.
    Trié par le champ "order".
    """
    activity = Activities.query.get(activity_id)
    if not activity:
        return "Activité introuvable.", 404

    sorted_tasks = sorted(activity.tasks, key=lambda t: t.order if t.order is not None else 0)

    # Construire task_conn_map pour l'affichage des connexions dans le partial
    task_conn_map = {}
    try:
        rows = db.session.execute(text("""
            SELECT tla.link_id, tla.task_id, tla.direction
            FROM task_link_assignments tla
            JOIN tasks t ON t.id = tla.task_id
            WHERE t.activity_id = :aid
        """), {"aid": activity_id}).fetchall()

        link_lookup = {}
        for link in Link.query.filter_by(target_activity_id=activity_id).all():
            d = Data.query.get(link.source_data_id) if link.source_data_id else None
            link_lookup[(link.id, 'incoming')] = {
                'data_name': d.name if d else (link.description or '?'),
                'conn_type': link.type or '',
            }
        for link in Link.query.filter_by(source_activity_id=activity_id).all():
            d = Data.query.get(link.source_data_id) if link.source_data_id else None
            link_lookup[(link.id, 'outgoing')] = {
                'data_name': d.name if d else (link.description or '?'),
                'conn_type': link.type or '',
            }

        for row in rows:
            tid = str(row[1])
            direction = row[2]
            info = link_lookup.get((row[0], direction), {'data_name': '?', 'conn_type': ''})
            if tid not in task_conn_map:
                task_conn_map[tid] = {}
            task_conn_map[tid][direction] = {
                'link_id': row[0],
                'data_name': info['data_name'],
                'conn_type': info['conn_type'],
            }
    except Exception:
        db.session.rollback()

    return render_template('tasks_partial.html',
                           activity=activity,
                           tasks=sorted_tasks,
                           item={'task_conn_map': task_conn_map})


# -----------------------------------------------
# NOUVELLES ROUTES POUR LA MODIFICATION ET SUPPRESSION DES TÂCHES
# -----------------------------------------------
@tasks_bp.route('/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """
    Modifie une tâche existante.
    Expects JSON with keys: name, description.
    """
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if 'name' in data:
        task.name = data['name']
    if 'description' in data:
        task.description = data['description']

    try:
        db.session.commit()
        return jsonify({
            'id': task.id,
            'name': task.name,
            'description': task.description,
            'order': task.order,
            'activity_id': task.activity_id
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """
    Supprime une tâche existante.
    """
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    try:
        # Supprimer les associations task_roles avant de supprimer la tâche
        db.session.execute(
            task_roles.delete().where(task_roles.c.task_id == task_id)
        )
        db.session.delete(task)
        db.session.commit()
        return jsonify({"message": f"Task {task_id} deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500