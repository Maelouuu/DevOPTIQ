# Code/routes/activities_view.py
"""
Vue des activités - Affiche la liste des activités de l'entité active.

MODIFICATION POUR MULTI-ENTITÉS:
- Changement: Activities.query.all() → Activities.for_active_entity().all()
- C'est la seule modification nécessaire pour filtrer par entité.
"""
from flask import render_template
from sqlalchemy import or_, desc, text
from .activities_bp import activities_bp
from Code.extensions import db
from Code.models.models import Activities, Task, Link, Data, Performance, Role, activity_roles


@activities_bp.route('/view', methods=['GET'])
def view_activities():
    # Crée la table task_link_assignments si elle n'existe pas
    try:
        from Code.routes.task_link_assignments import ensure_table as _ensure_tla
        _ensure_tla()
    except Exception:
        pass
    """
    Affiche la liste des activités de l'ENTITÉ ACTIVE.
    
    Pour chaque activité :
    - Tâches (triées par order)
    - Connexions entrantes/sortantes
    - Performance associée
    - Garant (rôle avec statut 'Garant')
    """

    # ========================================
    # MODIFICATION POUR MULTI-ENTITÉS
    # Avant:  activities = Activities.query.all()
    # Après:  activities = Activities.for_active_entity().all()
    # ========================================
    activities = Activities.for_active_entity().order_by(Activities.name).all()

    activity_data = []
    for activity in activities:
        # Tâches triées par "order"
        tasks_sorted = db.session.query(Task).filter_by(activity_id=activity.id)\
                           .order_by(Task.order.asc().nullsfirst()).all()

        # Connexions entrantes
        incoming_links = db.session.query(Link).filter(
            or_(
                Link.target_activity_id == activity.id,
                Link.target_data_id == activity.id
            )
        ).all()

        incoming_list = []
        for link in incoming_links:
            data_name = resolve_data_name(link, incoming=True)
            source_name = resolve_source_name(link)
            d_type = resolve_data_type(link, incoming=True)

            incoming_list.append({
                'type': d_type,
                'data_name': data_name,
                'source_name': source_name,
                'link_id': link.id
            })

        # Connexions sortantes
        outgoing_links = db.session.query(Link).filter(
            or_(
                Link.source_activity_id == activity.id,
                Link.source_data_id == activity.id
            )
        ).all()

        outgoing_list = []
        for link in outgoing_links:
            data_name = resolve_data_name(link, incoming=False)
            target_name = resolve_target_name(link)
            d_type = resolve_data_type(link, incoming=False)
            perf_obj = link.performance

            perf_dict = None
            if perf_obj:
                perf_dict = {
                    "id": perf_obj.id,
                    "name": perf_obj.name,
                    "description": perf_obj.description
                }

            outgoing_list.append({
                'type': d_type,
                'data_name': data_name,
                'target_name': target_name,
                'link_id': link.id,
                'performance': perf_dict
            })

        # Récupérer le rôle "Garant"
        garant_role = db.session.query(Role).\
                      join(activity_roles).\
                      filter(activity_roles.c.activity_id == activity.id).\
                      filter(activity_roles.c.role_id == Role.id).\
                      filter(activity_roles.c.status == 'Garant').\
                      first()

        garant_dict = None
        if garant_role:
            garant_dict = {
                "id": garant_role.id,
                "name": garant_role.name
            }

        # Charger les task-link assignments pour cette activité
        # (ensure_table appelé une seule fois via le blueprint au premier hit)
        task_conn_map = {}
        try:
            rows = db.session.execute(text("""
                SELECT tla.link_id, tla.task_id, tla.direction
                FROM task_link_assignments tla
                JOIN tasks t ON t.id = tla.task_id
                WHERE t.activity_id = :aid
            """), {"aid": activity.id}).fetchall()

            # Construire un lookup : link_id → {data_name, type}
            link_lookup = {}
            for c in incoming_list:
                link_lookup[(c['link_id'], 'incoming')] = {'data_name': c['data_name'], 'conn_type': c['type']}
            for c in outgoing_list:
                link_lookup[(c['link_id'], 'outgoing')] = {'data_name': c['data_name'], 'conn_type': c['type']}

            for row in rows:
                tid = str(row[1])
                direction = row[2]
                info = link_lookup.get((row[0], direction), {'data_name': '?', 'conn_type': ''})
                if tid not in task_conn_map:
                    task_conn_map[tid] = {}
                task_conn_map[tid][direction] = {
                    'link_id': row[0],
                    'data_name': info['data_name'],
                    'conn_type': info['conn_type']
                }
        except Exception:
            db.session.rollback()

        # Ajout dans la liste
        activity_data.append({
            'activity': activity,
            'tasks': tasks_sorted,
            'incoming': incoming_list,
            'outgoing': outgoing_list,
            'garant': garant_dict,
            'constraints': activity.constraints,
            'competencies': activity.competencies,
            'softskills': activity.softskills,
            'savoirs': activity.savoirs,
            'savoir_faires': activity.savoir_faires,
            'aptitudes': activity.aptitudes,
            'task_conn_map': task_conn_map
        })

    return render_template('display_list.html', activity_data=activity_data)


# ===================== FONCTIONS UTILITAIRES =====================

def resolve_data_name(link, incoming=True):
    """Cherche le nom data pour un link."""
    data_id = link.source_data_id if incoming else link.source_data_id
    if not data_id:
        return link.description or "[Data inconnue]"
    d_obj = Data.query.get(data_id)
    if d_obj:
        return d_obj.name
    return link.description or "[Data sans nom]"


def resolve_source_name(link):
    """Résout le nom de la source."""
    if link.source_activity_id:
        act = Activities.query.get(link.source_activity_id)
        if act:
            return act.name
        return "[Activité inconnue]"
    elif link.source_data_id:
        d_obj = Data.query.get(link.source_data_id)
        if d_obj:
            return d_obj.name
        return "[Data inconnue]"
    return "[Source ?]"


def resolve_target_name(link):
    """Résout le nom de la cible."""
    if link.target_activity_id:
        act = Activities.query.get(link.target_activity_id)
        if act:
            return act.name
        return "[Activité inconnue]"
    elif link.target_data_id:
        d_obj = Data.query.get(link.target_data_id)
        if d_obj:
            return d_obj.name
        return "[Data inconnue]"
    return "[Cible ?]"


def resolve_data_type(link, incoming=True):
    """Retourne le type du Data."""
    data_id = link.source_data_id if incoming else link.source_data_id
    if data_id:
        d_obj = Data.query.get(data_id)
        if d_obj and d_obj.type:
            return d_obj.type
    return link.type or "[type non défini]"
