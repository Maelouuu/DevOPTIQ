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
    try:
        from Code.routes.task_link_assignments import ensure_table as _ensure_tla
        _ensure_tla()
    except Exception:
        pass

    activities = Activities.for_active_entity().order_by(Activities.name).all()
    if not activities:
        return render_template('display_list.html', activity_data=[])

    activity_ids = [a.id for a in activities]
    act_set      = set(activity_ids)
    act_by_id    = {a.id: a for a in activities}

    # ── Batch load : 1 requête par type de données ────────────────────────────

    # Tâches
    all_tasks = db.session.query(Task).filter(
        Task.activity_id.in_(activity_ids)
    ).order_by(Task.activity_id, Task.order.asc().nullsfirst()).all()
    tasks_by_act = {}
    for t in all_tasks:
        tasks_by_act.setdefault(t.activity_id, []).append(t)

    # Liens entrants (target = une de nos activités)
    all_incoming = db.session.query(Link).filter(
        or_(Link.target_activity_id.in_(activity_ids),
            Link.target_data_id.in_(activity_ids))
    ).all()
    incoming_by_act = {}
    for lk in all_incoming:
        key = lk.target_activity_id if lk.target_activity_id in act_set else lk.target_data_id
        if key in act_set:
            incoming_by_act.setdefault(key, []).append(lk)

    # Liens sortants (source = une de nos activités)
    all_outgoing = db.session.query(Link).filter(
        or_(Link.source_activity_id.in_(activity_ids),
            Link.source_data_id.in_(activity_ids))
    ).all()
    outgoing_by_act = {}
    for lk in all_outgoing:
        key = lk.source_activity_id if lk.source_activity_id in act_set else lk.source_data_id
        if key in act_set:
            outgoing_by_act.setdefault(key, []).append(lk)

    # Pré-charger Activities et Data référencées par les liens (résolution des noms)
    ref_act_ids  = set()
    ref_data_ids = set()
    for lk in all_incoming + all_outgoing:
        for fid in (lk.source_activity_id, lk.target_activity_id):
            if fid and fid not in act_by_id:
                ref_act_ids.add(fid)
        for fid in (lk.source_data_id, lk.target_data_id):
            if fid:
                ref_data_ids.add(fid)
    ref_acts = dict(act_by_id)
    if ref_act_ids:
        for a in Activities.query.filter(Activities.id.in_(list(ref_act_ids))).all():
            ref_acts[a.id] = a
    ref_data = {}
    if ref_data_ids:
        for d in Data.query.filter(Data.id.in_(list(ref_data_ids))).all():
            ref_data[d.id] = d

    # Garants (1 requête + join roles)
    garant_by_act = {}
    if activity_ids:
        from sqlalchemy import select as sa_select, func as sa_func
        garant_rows = db.session.execute(
            sa_select(activity_roles.c.activity_id, Role.id, Role.name)
            .join(Role, activity_roles.c.role_id == Role.id)
            .where(activity_roles.c.activity_id.in_(activity_ids))
            .where(sa_func.lower(activity_roles.c.status) == 'garant')
        ).fetchall()
        for row in garant_rows:
            garant_by_act[row[0]] = {"id": row[1], "name": row[2]}

    # Task-link assignments (1 requête pour toutes les activités)
    tla_by_task = {}
    try:
        id_list = ','.join(str(i) for i in activity_ids)
        tla_rows = db.session.execute(text(f"""
            SELECT tla.link_id, tla.task_id, tla.direction
            FROM task_link_assignments tla
            JOIN tasks t ON t.id = tla.task_id
            WHERE t.activity_id IN ({id_list})
        """)).fetchall()
        for row in tla_rows:
            tla_by_task.setdefault(str(row[1]), {})[row[2]] = row[0]  # tid→dir→link_id
    except Exception:
        db.session.rollback()

    # ── Helpers de résolution de noms (sans requête) ──────────────────────────
    def _act_name(fid):
        a = ref_acts.get(fid)
        return a.name if a else '[Activité inconnue]'

    def _data_name(fid):
        d = ref_data.get(fid)
        return d.name if d else '[Data inconnue]'

    def _resolve_source(lk):
        if lk.source_activity_id: return _act_name(lk.source_activity_id)
        if lk.source_data_id:     return _data_name(lk.source_data_id)
        return '[Source ?]'

    def _resolve_target(lk):
        if lk.target_activity_id: return _act_name(lk.target_activity_id)
        if lk.target_data_id:     return _data_name(lk.target_data_id)
        return '[Cible ?]'

    def _resolve_data_name(lk, incoming):
        did = lk.source_data_id if incoming else lk.source_data_id
        if did:
            d = ref_data.get(did)
            return d.name if d else (lk.description or '[Data sans nom]')
        return lk.description or '[Data inconnue]'

    # ── Assemblage final (aucune requête supplémentaire) ──────────────────────
    activity_data = []
    for activity in activities:
        aid = activity.id

        incoming_list = []
        for lk in incoming_by_act.get(aid, []):
            incoming_list.append({
                'type':        resolve_data_type(lk, incoming=True),
                'data_name':   _resolve_data_name(lk, incoming=True),
                'source_name': _resolve_source(lk),
                'link_id':     lk.id,
            })

        outgoing_list = []
        for lk in outgoing_by_act.get(aid, []):
            perf_obj = lk.performance
            outgoing_list.append({
                'type':        resolve_data_type(lk, incoming=False),
                'data_name':   _resolve_data_name(lk, incoming=False),
                'target_name': _resolve_target(lk),
                'link_id':     lk.id,
                'performance': {
                    'id': perf_obj.id, 'name': perf_obj.name,
                    'description': perf_obj.description
                } if perf_obj else None,
            })

        # Lookup link_id → {data_name, conn_type} pour les TLA
        link_lookup = {}
        for c in incoming_list:
            link_lookup[(c['link_id'], 'incoming')] = {'data_name': c['data_name'], 'conn_type': c['type']}
        for c in outgoing_list:
            link_lookup[(c['link_id'], 'outgoing')] = {'data_name': c['data_name'], 'conn_type': c['type']}

        tasks = tasks_by_act.get(aid, [])
        task_conn_map = {}
        for t in tasks:
            tid = str(t.id)
            if tid in tla_by_task:
                task_conn_map[tid] = {}
                for direction, link_id in tla_by_task[tid].items():
                    info = link_lookup.get((link_id, direction), {'data_name': '?', 'conn_type': ''})
                    task_conn_map[tid][direction] = {
                        'link_id':   link_id,
                        'data_name': info['data_name'],
                        'conn_type': info['conn_type'],
                    }

        activity_data.append({
            'activity':     activity,
            'tasks':        tasks,
            'incoming':     incoming_list,
            'outgoing':     outgoing_list,
            'garant':       garant_by_act.get(aid),
            'constraints':  activity.constraints,
            'competencies': activity.competencies,
            'softskills':   activity.softskills,
            'savoirs':      activity.savoirs,
            'savoir_faires': activity.savoir_faires,
            'aptitudes':    activity.aptitudes,
            'task_conn_map': task_conn_map,
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
