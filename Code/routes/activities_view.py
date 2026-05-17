# Code/routes/activities_view.py
from flask import render_template, request, jsonify
from sqlalchemy import or_, desc, text
from .activities_bp import activities_bp
from Code.extensions import db
from Code.models.models import Activities, Task, Link, Data, Performance, Role, activity_roles

PAGE_SIZE    = 20
SPECIAL_SIZE = 10


@activities_bp.route('/view', methods=['GET'])
def view_activities():
    try:
        from Code.routes.task_link_assignments import ensure_table as _ensure_tla
        _ensure_tla()
    except Exception:
        pass

    activity_id = request.args.get('activity_id', type=int)
    total       = Activities.for_active_entity().count()

    if not total:
        return render_template('display_list.html', activity_data=[],
                               has_more=False, next_offset=0, total=0,
                               pinned_activity_id=None)

    if activity_id:
        target = Activities.for_active_entity().filter(Activities.id == activity_id).first()
        others = (Activities.for_active_entity()
                  .filter(Activities.id != activity_id)
                  .order_by(Activities.name)
                  .limit(SPECIAL_SIZE).all())
        to_load     = ([target] if target else []) + others
        next_offset = SPECIAL_SIZE
        others_total = total - (1 if target else 0)
        has_more     = others_total > SPECIAL_SIZE
    else:
        to_load     = Activities.for_active_entity().order_by(Activities.name).limit(PAGE_SIZE).all()
        next_offset = PAGE_SIZE
        has_more    = total > PAGE_SIZE

    activity_data = _build_activity_data(to_load)
    return render_template('display_list.html',
                           activity_data=activity_data,
                           has_more=has_more,
                           next_offset=next_offset,
                           total=total,
                           pinned_activity_id=activity_id)


@activities_bp.route('/view/more', methods=['GET'])
def view_activities_more():
    offset     = request.args.get('offset', PAGE_SIZE, type=int)
    exclude_id = request.args.get('exclude_id', type=int)

    q = Activities.for_active_entity().order_by(Activities.name)
    if exclude_id:
        q = q.filter(Activities.id != exclude_id)

    total_filtered = q.count()
    more_acts      = q.offset(offset).limit(PAGE_SIZE).all()

    if not more_acts:
        return jsonify({'html': '', 'has_more': False, 'next_offset': offset})

    activity_data = _build_activity_data(more_acts)
    html          = render_template('activity_cards_partial.html', activity_data=activity_data)
    has_more      = (offset + len(more_acts)) < total_filtered

    return jsonify({
        'html':        html,
        'has_more':    has_more,
        'next_offset': offset + len(more_acts),
    })


# ─── Batch loader ─────────────────────────────────────────────────────────────

def _build_activity_data(activities):
    """Batch-load tasks, links and metadata for the given Activity objects."""
    if not activities:
        return []

    activity_ids = [a.id for a in activities]
    act_set      = set(activity_ids)
    act_by_id    = {a.id: a for a in activities}

    # Tâches
    all_tasks = db.session.query(Task).filter(
        Task.activity_id.in_(activity_ids)
    ).order_by(Task.activity_id, Task.order.asc().nullsfirst()).all()
    tasks_by_act = {}
    for t in all_tasks:
        tasks_by_act.setdefault(t.activity_id, []).append(t)

    # Liens entrants
    all_incoming = db.session.query(Link).filter(
        or_(Link.target_activity_id.in_(activity_ids),
            Link.target_data_id.in_(activity_ids))
    ).all()
    incoming_by_act = {}
    for lk in all_incoming:
        key = lk.target_activity_id if lk.target_activity_id in act_set else lk.target_data_id
        if key in act_set:
            incoming_by_act.setdefault(key, []).append(lk)

    # Liens sortants
    all_outgoing = db.session.query(Link).filter(
        or_(Link.source_activity_id.in_(activity_ids),
            Link.source_data_id.in_(activity_ids))
    ).all()
    outgoing_by_act = {}
    for lk in all_outgoing:
        key = lk.source_activity_id if lk.source_activity_id in act_set else lk.source_data_id
        if key in act_set:
            outgoing_by_act.setdefault(key, []).append(lk)

    # Résolution des noms référencés par les liens
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

    # Garants
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

    # Task-link assignments
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
            tla_by_task.setdefault(str(row[1]), {})[row[2]] = row[0]
    except Exception:
        db.session.rollback()

    # Helpers de résolution (sans requête)
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

    def _resolve_data_name(lk):
        did = lk.source_data_id
        if did:
            d = ref_data.get(did)
            return d.name if d else (lk.description or '[Data sans nom]')
        return lk.description or '[Data inconnue]'

    # Assemblage
    activity_data = []
    for activity in activities:
        aid = activity.id

        incoming_list = []
        for lk in incoming_by_act.get(aid, []):
            incoming_list.append({
                'type':        resolve_data_type(lk, incoming=True),
                'data_name':   _resolve_data_name(lk),
                'source_name': _resolve_source(lk),
                'link_id':     lk.id,
            })

        outgoing_list = []
        for lk in outgoing_by_act.get(aid, []):
            perf_obj = lk.performance
            outgoing_list.append({
                'type':        resolve_data_type(lk, incoming=False),
                'data_name':   _resolve_data_name(lk),
                'target_name': _resolve_target(lk),
                'link_id':     lk.id,
                'performance': {
                    'id': perf_obj.id, 'name': perf_obj.name,
                    'description': perf_obj.description
                } if perf_obj else None,
            })

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
            'activity':      activity,
            'tasks':         tasks,
            'incoming':      incoming_list,
            'outgoing':      outgoing_list,
            'garant':        garant_by_act.get(aid),
            'constraints':   activity.constraints,
            'competencies':  activity.competencies,
            'softskills':    activity.softskills,
            'savoirs':       activity.savoirs,
            'savoir_faires': activity.savoir_faires,
            'aptitudes':     activity.aptitudes,
            'task_conn_map': task_conn_map,
        })

    return activity_data


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def resolve_data_type(link, incoming=True):
    data_id = link.source_data_id
    if data_id:
        d_obj = Data.query.get(data_id)
        if d_obj and d_obj.type:
            return d_obj.type
    return link.type or "[type non défini]"
