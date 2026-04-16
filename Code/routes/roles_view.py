from flask import Blueprint, render_template, jsonify, request
from sqlalchemy import text, func, bindparam
from Code.extensions import db
from Code.models.models import Role, Entity

roles_view_bp = Blueprint('roles_view', __name__, url_prefix='/roles_view', template_folder='templates')

def _get_role_mission(role_id: int) -> str:
    """Récupère mission_generale même si le modèle Role ne possède pas l'attribut."""
    row = db.session.execute(
        text("SELECT mission_generale FROM roles WHERE id = :rid"),
        {"rid": role_id}
    ).fetchone()
    return row[0] if row and row[0] else ""

def _table_exists(name: str) -> bool:
    row = db.session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": name}
    ).fetchone()
    return bool(row)

def _get_validation_level(user_id: int, role_id: int):
    """
    Essaie de récupérer le niveau de validation depuis une table connue.
    Retourne None si aucune table/colonne attendue n'est trouvée.
    """
    # Cherche une table plausible
    table = None
    for candidate in ("user_role_validations", "role_validations"):
        if _table_exists(candidate):
            table = candidate
            break
    if not table:
        return None

    # Inspecte les colonnes
    cols_rows = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
    cols = {r[1] for r in cols_rows}  # r[1] = name
    level_col = 'level' if 'level' in cols else ('validation_level' if 'validation_level' in cols else None)
    user_col = 'user_id' if 'user_id' in cols else ('users_id' if 'users_id' in cols else None)
    role_col = 'role_id' if 'role_id' in cols else None

    if not all([level_col, user_col, role_col]):
        return None

    row = db.session.execute(
        text(f"""
            SELECT {level_col}
            FROM {table}
            WHERE {user_col} = :uid AND {role_col} = :rid
            LIMIT 1
        """),
        {"uid": user_id, "rid": role_id}
    ).fetchone()

    return row[0] if row else None

@roles_view_bp.route('/', methods=['GET'])
def view_roles():
    # MODIFIÉ: Filtrer les rôles par entité active
    roles = Role.for_active_entity().order_by(func.lower(Role.name)).all()

    roles_data = []
    for role in roles:
        # Bloc 1 : Activités où le rôle est Garant
        stmt1 = text("""
            SELECT a.id, a.name, a.description
            FROM activity_roles ar
            JOIN activities a ON ar.activity_id = a.id
            WHERE ar.role_id = :rid AND ar.status = 'Garant'
        """)
        garant_activities = db.session.execute(stmt1, {"rid": role.id}).fetchall()
        block1 = [{"id": row[0], "name": row[1], "description": row[2]} for row in garant_activities]

        # Bloc 2 : Tâches où ce rôle intervient (non Garant)
        stmt2 = text("""
            SELECT a.id AS activity_id, a.name AS activity_name,
                   t.id AS task_id, t.name AS task_name,
                   tr.status AS role_status
            FROM tasks t
            JOIN activities a ON a.id = t.activity_id
            JOIN task_roles tr ON tr.task_id = t.id
            WHERE tr.role_id = :rid
            ORDER BY a.name, t.name
        """)
        non_garant_tasks = db.session.execute(stmt2, {"rid": role.id}).fetchall()
        block2 = [
            {
                "activity_id": row.activity_id,
                "activity_name": row.activity_name,
                "task_id": row.task_id,
                "task_name": row.task_name,
                "status": row.role_status
            }
            for row in non_garant_tasks
        ]

        # Bloc 3 : Compétences associées aux activités Garant
        stmt3 = text("""
            SELECT c.id, c.description
            FROM competencies c
            JOIN activity_roles ar ON c.activity_id = ar.activity_id
            WHERE ar.role_id = :rid AND ar.status = 'Garant'
        """)
        competencies = db.session.execute(stmt3, {"rid": role.id}).fetchall()
        block3 = [{"id": comp[0], "description": comp[1]} for comp in competencies]

        # Bloc 4 : Savoirs, Savoir-faire, Aptitudes, HSC des activités Garant
        stmt_ids = text("""
            SELECT DISTINCT ar.activity_id
            FROM activity_roles ar
            WHERE ar.role_id = :rid AND ar.status = 'Garant'
        """)
        activity_ids = [row[0] for row in db.session.execute(stmt_ids, {"rid": role.id}).fetchall()]

        savoirs = {}
        savoir_faires = {}
        aptitudes = {}
        softskills = {}

        if activity_ids:
            stmt_savoirs = (
                text("SELECT s.id, s.description FROM savoirs s WHERE s.activity_id IN :act_ids")
                .bindparams(bindparam("act_ids", expanding=True))
            )
            for row in db.session.execute(stmt_savoirs, {"act_ids": activity_ids}).fetchall():
                savoirs[row[0]] = row[1]

            stmt_savoir_faires = (
                text("SELECT sf.id, sf.description FROM savoir_faires sf WHERE sf.activity_id IN :act_ids")
                .bindparams(bindparam("act_ids", expanding=True))
            )
            for row in db.session.execute(stmt_savoir_faires, {"act_ids": activity_ids}).fetchall():
                savoir_faires[row[0]] = row[1]

            stmt_aptitudes = (
                text("SELECT a.id, a.description FROM aptitudes a WHERE a.activity_id IN :act_ids")
                .bindparams(bindparam("act_ids", expanding=True))
            )
            for row in db.session.execute(stmt_aptitudes, {"act_ids": activity_ids}).fetchall():
                aptitudes[row[0]] = row[1]

            stmt_softskills = (
                text("""
                    SELECT ss.id, ss.habilete, ss.niveau, ss.justification
                    FROM softskills ss
                    WHERE ss.activity_id IN :act_ids
                """).bindparams(bindparam("act_ids", expanding=True))
            )
            for row in db.session.execute(stmt_softskills, {"act_ids": activity_ids}).fetchall():
                softskills[row[0]] = {
                    "habilete": row[1],
                    "niveau": row[2],
                    "justification": row[3] or "Pas de justification"
                }

        block4 = []
        added_savoirs = set()
        added_savoir_faires = set()
        added_aptitudes = set()
        added_softskills = set()

        for _id, desc in savoirs.items():
            if _id not in added_savoirs:
                block4.append({"type": "savoir", "value": desc})
                added_savoirs.add(_id)

        for _id, desc in savoir_faires.items():
            if _id not in added_savoir_faires:
                block4.append({"type": "savoir-faire", "value": desc})
                added_savoir_faires.add(_id)

        for _id, desc in aptitudes.items():
            if _id not in added_aptitudes:
                block4.append({"type": "aptitude", "value": desc})
                added_aptitudes.add(_id)

        for _id, details in softskills.items():
            if _id not in added_softskills:
                block4.append({
                    "type": "softskill",
                    "value": details["habilete"],
                    "niveau": details["niveau"],
                    "justification": details["justification"]
                })
                added_softskills.add(_id)

        # Bloc 5 : Titulaires du rôle (utilisateurs affectés à ce rôle)
        # Table attendue : user_roles(user_id, role_id)
        holders = []
        try:
            stmt_holders = text("""
                SELECT u.id, u.first_name, u.last_name, u.email
                FROM user_roles ur
                JOIN users u ON u.id = ur.user_id
                WHERE ur.role_id = :rid
                ORDER BY COALESCE(u.last_name, ''), COALESCE(u.first_name, '')
            """)
            rows = db.session.execute(stmt_holders, {"rid": role.id}).fetchall()
            for r in rows:
                holders.append({
                    "id": r[0],
                    "first_name": r[1],
                    "last_name": r[2],
                    "email": r[3],
                })
        except Exception:
            # Si la table n'existe pas, on laisse vide.
            holders = []

        roles_data.append({
            "role": {"id": role.id, "name": role.name},
            "mission_generale": _get_role_mission(role.id),
            "block1": block1,
            "block2": block2,
            "block3": block3,
            "block4": block4,
            "holders": holders
        })

    active_entity = Entity.get_active()
    active_entity_dict = {"id": active_entity.id, "name": active_entity.name} if active_entity else None
    return render_template("roles_view.html", roles_data=roles_data, active_entity=active_entity_dict)

@roles_view_bp.route('/<int:role_id>/mission', methods=['PUT'])
def update_role_mission(role_id: int):
    """
    Met à jour la mission_generale du rôle (colonne TEXT `mission_generale` dans la table roles).
    """
    data = request.get_json(silent=True) or {}
    mission = data.get("mission_generale", "").strip()

    # UPDATE direct pour éviter toute dépendance au modèle SQLAlchemy
    db.session.execute(
        text("UPDATE roles SET mission_generale = :m WHERE id = :rid"),
        {"m": mission, "rid": role_id}
    )
    db.session.commit()
    return jsonify({"ok": True, "role_id": role_id, "mission_generale": mission})

@roles_view_bp.route('/validation_level/<int:user_id>/<int:role_id>', methods=['GET'])
def get_validation_level(user_id: int, role_id: int):
    """
    Fournit le niveau de validation pour un couple (user_id, role_id).
    Renvoie {"level": null} si non trouvé.
    """
    level = _get_validation_level(user_id, role_id)
    return jsonify({"level": level})
