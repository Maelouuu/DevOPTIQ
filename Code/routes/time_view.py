# Code/routes/time_view.py
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from sqlalchemy import text
from Code.extensions import db
from Code.models.models import (
    Activities, Task, Role, TimeAnalysis,
    TimeProject, TimeProjectLine, TimeWeakness,
    TimeRoleAnalysis, TimeRoleLine,
    activity_roles, Entity
)

time_bp = Blueprint('time_view', __name__, url_prefix='/temps')

# ---------- Helpers ----------
UNIT_TO_MIN = {'minutes': 1, 'heures': 60, 'jours': 1440}
def to_minutes(qty, unit):
    return float(qty or 0) * UNIT_TO_MIN.get((unit or 'minutes').lower(), 1)

def get_company_params():
    defaults = {'Js': 5, 'Sa': 47, 'Ja': 220}
    try:
        row = db.session.execute(text("SELECT Js, Sa, Ja FROM company_params LIMIT 1")).fetchone()
        if row:
            return {'Js': int(row[0] or 5), 'Sa': int(row[1] or 47), 'Ja': int(row[2] or 220)}
    except Exception:
        pass
    try:
        row = db.session.execute(text("""
            SELECT days_per_week, weeks_per_year, days_per_year
            FROM gestion_rh_params LIMIT 1
        """)).fetchone()
        if row:
            return {'Js': int(row[0] or 5), 'Sa': int(row[1] or 47), 'Ja': int(row[2] or 220)}
    except Exception:
        pass
    return defaults

def get_calendar_params():
    # Paramètres saisis dans Gestion RH (table entreprise_settings, par entité).
    # NB : l'ancienne requête visait une table `enterprise_settings` inexistante.
    try:
        from Code.models.models import EntrepriseSettings, Entity
        try:
            eid = Entity.get_active_id()
        except Exception:
            eid = None
        row = EntrepriseSettings.query.filter_by(entity_id=eid).first() if eid else None
        if row is None:
            row = EntrepriseSettings.query.order_by(EntrepriseSettings.id).first()
        if row:
            return {'hours_per_day': float(row.work_hours_per_day or 7),
                    'days_per_week': int(row.work_days_per_week or 5),
                    'weeks_per_year': int(row.work_weeks_per_year or 47)}
    except Exception:
        db.session.rollback()
    cp = get_company_params()
    return {'hours_per_day': 7.0, 'days_per_week': cp['Js'], 'weeks_per_year': cp['Sa']}

# Semaines par mois : la base « mois TRAVAILLES » de l'onglet Faiblesse.
SEMAINES_PAR_MOIS = 4.34524
SEMAINES_PAR_AN = 52.1429


def annuel_minutes(par_periode, recurrence, params=None):
    """Minutes par an d'une charge exprimee PAR PERIODE de recurrence.

    Une seule implementation : l'onglet Role, le tableau de bord et l'apercu
    du navigateur s'y referent tous. Deux versions de cette regle finiraient
    par donner deux chiffres pour la meme analyse.

    Calendrier civil pour le mensuel (12) et l'annuel (1) ; ce n'est PAS la
    base de l'onglet Faiblesse, qui compte en periodes TRAVAILLEES (voir
    `cout_faiblesse`). Les deux coexistent depuis toujours et n'ont pas ete
    unifiees : changer l'une deplacerait des analyses deja enregistrees.
    """
    p = params or get_calendar_params()
    r = (recurrence or '').strip().lower()
    q = float(par_periode or 0)
    if r.startswith('jour'):
        return q * float(p['days_per_week']) * float(p['weeks_per_year'])
    if r.startswith('hebdo'):
        return q * float(p['weeks_per_year'])
    if r.startswith('mens'):
        return q * 12.0
    return q


def heures_plein_temps(params=None):
    """Les heures d'un temps plein sur le calendrier de l'entite."""
    p = params or get_calendar_params()
    return float(p['hours_per_day']) * float(p['days_per_week']) * float(p['weeks_per_year'])


def cout_faiblesse(duree_std_min, delai_std_min, recurrence, frequence,
                   travail_ajoute_min, attente_ajoutee_min, denom_proba,
                   params=None):
    """Les variables O..AA de l'onglet Faiblesse.

    Extrait de `api_weakness`, qui l'appelle : le tableau de bord doit chiffrer
    une faiblesse ENREGISTREE exactement comme l'ecran qui l'a produite.

    `H` compte les occurrences par an : les PERIODES travaillees (le mensuel
    divise par 4,34524 semaines, pas par douze) multipliees par la frequence.
    """
    p = params or get_calendar_params()
    Js, Sa = float(p['days_per_week']), float(p['weeks_per_year'])
    rec = (recurrence or '').strip().lower()

    if rec.startswith('jour'):
        H = Js * Sa
    elif rec.startswith('hebdo'):
        H = Sa
    elif rec.startswith('mens'):
        H = Sa / SEMAINES_PAR_MOIS
    else:
        H = Sa / SEMAINES_PAR_AN

    H = H * max(1, int(frequence or 1))

    B = float(duree_std_min or 0)
    C = float(delai_std_min or 0)
    L = float(travail_ajoute_min or 0)
    M = float(attente_ajoutee_min or 0)
    N = max(1, int(denom_proba or 1))

    O = 1.0 / N
    P_ = H * O
    Q = L * O
    Rv = (L + M) * O
    S = B + Q
    T = C + Rv
    U = L * P_
    V = (L + M) * P_
    base_mois = (Sa / SEMAINES_PAR_MOIS)
    W = U / base_mois if base_mois else 0
    X = V / base_mois if base_mois else 0
    Y = C + M
    Z = M
    AA = P_
    return {"O": O, "P": P_, "Q": Q, "R": Rv, "S": S, "T": T,
            "U": U, "V": V, "W": W, "X": X, "Y": Y, "Z": Z, "AA": AA}


def activity_duration_minutes(activity_id):
    a = Activities.query.get(activity_id)
    return float(getattr(a, 'duration_minutes', 0) or 0)

def ensure_time_role_schema():
    """Auto-patch : ajoute les colonnes manquantes dans les tables rôle si nécessaire (SQLite)."""
    try:
        # time_role_analysis
        cols_ra = db.session.execute(text("PRAGMA table_info(time_role_analysis)")).fetchall()
        if cols_ra:
            names_ra = {c[1] for c in cols_ra}
            if 'name' not in names_ra:
                db.session.execute(text("ALTER TABLE time_role_analysis ADD COLUMN name TEXT DEFAULT 'Analyse rôle'"))
            if 'created_at' not in names_ra:
                db.session.execute(text("ALTER TABLE time_role_analysis ADD COLUMN created_at TEXT DEFAULT (datetime('now'))"))
        # time_role_line
        cols_rl = db.session.execute(text("PRAGMA table_info(time_role_line)")).fetchall()
        if cols_rl:
            names_rl = {c[1] for c in cols_rl}
            if 'duration_minutes' not in names_rl:
                db.session.execute(text("ALTER TABLE time_role_line ADD COLUMN duration_minutes REAL"))
        db.session.commit()
    except Exception:
        db.session.rollback()

# ---------- Page ----------
@time_bp.route('/', methods=['GET'])
def page():
    # MODIFIÉ: Filtrer par entité active
    activities = Activities.for_active_entity().order_by(Activities.name.asc()).all()
    roles = Role.query.order_by(Role.name.asc()).all()
    return render_template('time_dashboard.html', activities=activities, roles=roles)

@time_bp.route('/api/calendar_params', methods=['GET'])
def api_calendar_params():
    return jsonify({"ok": True, **get_calendar_params()})

# ---------- API: Defaults activité ----------
@time_bp.route('/api/activity_defaults/<int:activity_id>', methods=['GET'])
def api_activity_defaults(activity_id):
    a = Activities.query.get_or_404(activity_id)
    duration_min = getattr(a, 'duration_minutes', 0) or 0
    delay_min    = getattr(a, 'delay_minutes', 0) or 0
    tasks = Task.query.filter_by(activity_id=activity_id).order_by(Task.order.asc(), Task.id.asc()).all()
    return jsonify({
        "duration_minutes": float(duration_min),
        "delay_minutes": float(delay_min),
        "tasks": [{
            "id": t.id,
            "name": t.name,
            "duration_minutes": float(getattr(t, 'duration_minutes', 0) or 0),
            "delay_minutes":    float(getattr(t, 'delay_minutes', 0) or 0)
        } for t in tasks]
    })

# ---------- API: Saisie durée/délai directe ----------
@time_bp.route('/api/activity_time/<int:activity_id>', methods=['GET', 'POST', 'DELETE'])
def api_activity_time(activity_id):
    a = Activities.query.get_or_404(activity_id)

    if request.method == 'GET':
        tasks = Task.query.filter_by(activity_id=activity_id).order_by(Task.order.asc(), Task.id.asc()).all()
        sum_tasks = sum(float(t.duration_minutes or 0) for t in tasks)
        suggested_mode = 'tasks' if sum_tasks > 0 and abs(sum_tasks - (a.duration_minutes or 0)) < 0.001 else 'activity'
        return jsonify({
            "ok": True,
            "activity": {
                "id": a.id, "name": a.name,
                "duration_minutes": float(a.duration_minutes or 0),
                "delay_minutes": float(a.delay_minutes or 0)
            },
            "tasks": [{
                "id": t.id, "name": t.name,
                "duration_minutes": float(t.duration_minutes or 0),
                "delay_minutes": float(t.delay_minutes or 0)
            } for t in tasks],
            "mode": suggested_mode
        })

    if request.method == 'DELETE':
        a.duration_minutes = 0
        a.delay_minutes = 0
        Task.query.filter_by(activity_id=activity_id).update({
            Task.duration_minutes: 0,
            Task.delay_minutes: 0
        })
        db.session.commit()
        return jsonify({"ok": True, "reset": True})

    data = request.get_json(force=True) or {}
    mode = (data.get('mode') or 'activity').strip().lower()

    a.delay_minutes = to_minutes(data.get('delay', 0), data.get('delay_unit') or 'minutes')

    if mode == 'tasks':
        rows = data.get('tasks') or []
        total = 0.0
        for row in rows:
            tid = int(row['task_id'])
            dur_mn = to_minutes(row.get('duration', 0), row.get('duration_unit') or 'minutes')
            t = Task.query.get(tid)
            if t and t.activity_id == activity_id:
                t.duration_minutes = dur_mn
                if row.get('delay') is not None and row.get('delay_unit'):
                    t.delay_minutes = to_minutes(row.get('delay', 0), row.get('delay_unit') or 'minutes')
                total += dur_mn
        a.duration_minutes = total
    else:
        a.duration_minutes = to_minutes(data.get('duration', 0), data.get('duration_unit') or 'minutes')

    db.session.commit()
    return jsonify({"ok": True, "activity_id": a.id, "duration_minutes": float(a.duration_minutes or 0), "delay_minutes": float(a.delay_minutes or 0)})

# ========================= CHARGES : PROJET =========================
@time_bp.route('/api/project', methods=['POST'])
def api_project_create():
    data = request.get_json(force=True) or {}
    name = (data.get('name') or 'Projet sans titre').strip()
    lines = data.get('lines') or []

    # MODIFIÉ: Associer le projet à l'entité active
    active_entity_id = Entity.get_active_id()
    proj = TimeProject(name=name, created_at=datetime.utcnow(), entity_id=active_entity_id)
    db.session.add(proj)
    db.session.flush()

    for ln in lines:
        db.session.add(TimeProjectLine(
            project_id=proj.id,
            activity_id=int(ln['activity_id']),
            duration_minutes=to_minutes(ln.get('duration', 0), ln.get('duration_unit')),
            delay_minutes=to_minutes(ln.get('delay', 0), ln.get('delay_unit')),
            nb_people=int(ln.get('nb_people') or 1)
        ))
    db.session.commit()
    return jsonify({"ok": True, "project_id": proj.id})

@time_bp.route('/api/project/<int:project_id>', methods=['GET'])
def api_project_read(project_id):
    proj = TimeProject.query.get_or_404(project_id)
    rows, tot_nb, tot_dur, tot_charge, sum_delay = [], 0, 0.0, 0.0, 0.0
    for ln in proj.lines:
        charge = float(ln.duration_minutes) * max(1, ln.nb_people)
        rows.append({
            "id": ln.id,
            "activity_id": ln.activity_id,
            "activity": Activities.query.get(ln.activity_id).name if ln.activity_id else "",
            "duration_minutes": float(ln.duration_minutes),
            "delay_minutes": float(ln.delay_minutes),
            "nb_people": ln.nb_people,
            "charge_minutes": charge
        })
        tot_nb += ln.nb_people
        tot_dur += float(ln.duration_minutes)
        tot_charge += charge
        sum_delay += float(ln.delay_minutes)
    return jsonify({
        "ok": True,
        "project": {"id": proj.id, "name": proj.name, "created_at": proj.created_at.isoformat() if proj.created_at else None},
        "lines": rows,
        "total_nb_people": tot_nb,
        "total_duration_minutes": tot_dur,
        "total_charge_minutes": tot_charge,
        "total_delay_minutes": sum_delay
    })

@time_bp.route('/api/projects', methods=['GET'])
def api_projects_list():
    # MODIFIÉ: Filtrer par entité active
    projs = TimeProject.for_active_entity().order_by(TimeProject.created_at.desc(), TimeProject.id.desc()).all()
    out = []
    for p in projs:
        tot_dur = sum(float(ln.duration_minutes) for ln in p.lines)
        tot_charge = sum(float(ln.duration_minutes) * max(1, ln.nb_people) for ln in p.lines)
        out.append({
            "id": p.id,
            "name": p.name,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "line_count": len(p.lines),
            "total_duration_minutes": tot_dur,
            "total_charge_minutes": tot_charge
        })
    return jsonify({"ok": True, "items": out})

@time_bp.route('/api/project/<int:project_id>', methods=['PATCH'])
def api_project_rename(project_id):
    proj = TimeProject.query.get_or_404(project_id)
    d = request.get_json(force=True) or {}
    new_name = (d.get('name') or '').strip()
    if new_name:
        proj.name = new_name
        db.session.commit()
    return jsonify({"ok": True, "id": proj.id, "name": proj.name})

@time_bp.route('/api/project/<int:project_id>', methods=['PUT'])
def api_project_update(project_id):
    """Remplace le nom ET les lignes. Même forme que la création : on ne
    modifie pas avec un vocabulaire différent de celui qui a servi à créer."""
    proj = TimeProject.query.get_or_404(project_id)
    d = request.get_json(force=True) or {}
    nom = (d.get('name') or '').strip()
    if nom:
        proj.name = nom

    lignes = d.get('lines')
    if lignes is not None:
        # ⚠️ Objet par objet, PAS `delete(synchronize_session=False)` : ce
        # dernier laisse les lignes supprimées vivantes dans la session, et
        # le prochain flush tombe sur une ligne qui n'existe plus.
        for ancienne in TimeProjectLine.query.filter_by(project_id=proj.id).all():
            db.session.delete(ancienne)
        db.session.flush()
        for ln in lignes:
            db.session.add(TimeProjectLine(
                project_id=proj.id,
                activity_id=int(ln['activity_id']),
                duration_minutes=to_minutes(ln.get('duration', 0), ln.get('duration_unit')),
                delay_minutes=to_minutes(ln.get('delay', 0), ln.get('delay_unit')),
                nb_people=int(ln.get('nb_people') or 1)
            ))
    db.session.commit()
    return jsonify({"ok": True, "id": proj.id, "name": proj.name})


@time_bp.route('/api/project/<int:project_id>', methods=['DELETE'])
def api_project_delete(project_id):
    proj = TimeProject.query.get_or_404(project_id)
    db.session.delete(proj)
    db.session.commit()
    return jsonify({"ok": True, "deleted": True})

@time_bp.route('/api/project_line/<int:line_id>', methods=['DELETE'])
def api_project_line_delete(line_id):
    ln = TimeProjectLine.query.get_or_404(line_id)
    proj_id = ln.project_id
    db.session.delete(ln)
    db.session.flush()
    remaining = TimeProjectLine.query.filter_by(project_id=proj_id).count()
    deleted = False
    if remaining == 0:
        proj = TimeProject.query.get(proj_id)
        if proj:
            db.session.delete(proj)
            deleted = True
    db.session.commit()
    return jsonify({"ok": True, "project_deleted": deleted, "project_id": proj_id})

# ========================= TIME ANALYSIS =========================
@time_bp.route('/api/time_analysis', methods=['POST'])
def api_time_analysis_create():
    d = request.get_json(force=True) or {}
    mode = (d.get('mode') or 'activity').strip().lower()
    rec = (d.get('recurrence') or 'journalier').strip().lower()
    freq = int(d.get('frequency') or 1)
    delay_total = to_minutes(d.get('delay', 0), d.get('delay_unit') or 'minutes')
    activity_id = int(d.get('activity_id')) if d.get('activity_id') else None

    if mode == 'tasks':
        tasks_payload = d.get('tasks') or []
        for t in tasks_payload:
            dur = to_minutes(t.get('duration', 0), t.get('duration_unit') or 'minutes')
            db.session.add(TimeAnalysis(
                type='task', activity_id=activity_id, task_id=int(t.get('task_id')),
                duration=int(dur), recurrence=rec, frequency=freq, delay=int(delay_total)
            ))
    else:
        dur = to_minutes(d.get('duration', 0), d.get('duration_unit') or 'minutes')
        db.session.add(TimeAnalysis(
            type='activity', activity_id=activity_id, task_id=None,
            duration=int(dur), recurrence=rec, frequency=freq, delay=int(delay_total)
        ))
    db.session.commit()
    return jsonify({"ok": True})

@time_bp.route('/api/time_analyses', methods=['GET'])
def api_time_analyses_list():
    activity_id = request.args.get('activity_id', type=int)
    q = TimeAnalysis.query
    if activity_id:
        q = q.filter(TimeAnalysis.activity_id == activity_id)
    items = q.order_by(TimeAnalysis.id.desc()).all()
    out = []
    for x in items:
        act = Activities.query.get(x.activity_id)
        out.append({
            "id": x.id,
            "type": x.type,
            "activity_id": x.activity_id,
            "activity": act.name if act else "",
            "task_id": x.task_id,
            "duration": x.duration,
            "recurrence": x.recurrence,
            "frequency": x.frequency,
            "delay": x.delay,
            "annual_time": x.annual_time
        })
    return jsonify({"ok": True, "items": out})

@time_bp.route('/api/time_analysis/<int:tid>', methods=['DELETE'])
def api_time_analysis_delete(tid):
    x = TimeAnalysis.query.get_or_404(tid)
    db.session.delete(x)
    db.session.commit()
    return jsonify({"ok": True, "deleted": True})

# ========================= CHARGES : ANALYSE ACTIVITÉ =========================
# Endpoints appelés par static/js/time.js (onglet Activité). Ils existaient sur
# la lignée main (avant divergence des branches) mais manquaient ici : l'onglet
# chargeait dans le vide (404). Restaurés à l'identique — TimeAnalysis porte
# déjà nb_people/impact_unit/delay_increase.

def _workload_total(x):
    return float(x.duration or 0) * max(1, x.frequency or 1) * max(1, x.nb_people or 1)

def _workload_json(x):
    act = Activities.query.get(x.activity_id)
    return {
        "id": x.id,
        "activity_id": x.activity_id,
        "activity": act.name if act else "",
        "duration_minutes": float(x.duration or 0),
        "recurrence": x.recurrence,
        "frequency": int(x.frequency or 1),
        "nb_people": int(x.nb_people or 1),
        "total_minutes": _workload_total(x)
    }

@time_bp.route('/api/activity_workload', methods=['POST'])
def api_activity_workload():
    d = request.get_json(force=True) or {}
    ta = TimeAnalysis(
        type='activity',
        activity_id=int(d['activity_id']),
        duration=int(round(to_minutes(d.get('duration', 0), d.get('duration_unit')))),
        recurrence=(d.get('recurrence') or 'journalier').strip().lower(),
        frequency=int(d.get('frequency') or 1),
        nb_people=int(d.get('nb_people') or 1),
        delay=None,
        delay_increase=None,
        impact_unit='minutes'
    )
    db.session.add(ta)
    db.session.commit()
    return jsonify({"ok": True, "id": ta.id, "total_minutes": _workload_total(ta)})

@time_bp.route('/api/activity_workload/<int:wk_id>', methods=['GET'])
def api_activity_workload_read(wk_id):
    x = TimeAnalysis.query.get_or_404(wk_id)
    return jsonify({"ok": True, "item": _workload_json(x)})

@time_bp.route('/api/activity_workload/<int:wk_id>', methods=['PATCH'])
def api_activity_workload_update(wk_id):
    x = TimeAnalysis.query.get_or_404(wk_id)
    if x.type != 'activity':
        return jsonify({"ok": False, "error": "bad_type"}), 400
    d = request.get_json(force=True) or {}
    if d.get('activity_id') is not None: x.activity_id = int(d['activity_id'])
    if d.get('duration') is not None and d.get('duration_unit'):
        x.duration = int(round(to_minutes(d['duration'], d['duration_unit'])))
    if d.get('recurrence') is not None: x.recurrence = (d['recurrence'] or '').strip().lower()
    if d.get('frequency') is not None: x.frequency = int(d['frequency'])
    if d.get('nb_people') is not None: x.nb_people = int(d['nb_people'])
    db.session.commit()
    return jsonify({"ok": True, "id": x.id, "total_minutes": _workload_total(x)})

@time_bp.route('/api/activity_workload/<int:wk_id>', methods=['DELETE'])
def api_activity_workload_delete(wk_id):
    x = TimeAnalysis.query.get_or_404(wk_id)
    if x.type != 'activity':
        return jsonify({"ok": False, "error": "bad_type"}), 400
    db.session.delete(x)
    db.session.commit()
    return jsonify({"ok": True, "deleted": True})

@time_bp.route('/api/activity_workloads', methods=['GET'])
def api_activity_workloads_list():
    entity_activity_ids = [a.id for a in Activities.for_active_entity().all()]
    items = (TimeAnalysis.query
             .filter_by(type='activity')
             .filter(TimeAnalysis.activity_id.in_(entity_activity_ids))
             .order_by(TimeAnalysis.id.desc())
             .all())
    return jsonify({"ok": True, "items": [_workload_json(x) for x in items]})

@time_bp.route('/api/role_activities/<int:role_id>', methods=['GET'])
def api_role_activities(role_id):
    qs = (Activities.query
          .join(activity_roles, Activities.id == activity_roles.c.activity_id)
          .filter(activity_roles.c.role_id == role_id)
          .order_by(Activities.name.asc()))
    return jsonify({"ok": True, "activities": [{"id": a.id, "name": a.name} for a in qs.all()]})

# ========================= ACTIVITÉS (liste) =========================
@time_bp.route('/api/activities', methods=['GET'])
def api_activities_list():
    # MODIFIÉ: Filtrer par entité active
    qs = (Activities.for_active_entity()
          .order_by(Activities.name.asc())
          .all())
    return jsonify({
        "ok": True,
        "items": [{
            "id": a.id,
            "name": a.name,
            "duration_minutes": float(getattr(a, 'duration_minutes', 0) or 0),
            "delay_minutes": float(getattr(a, 'delay_minutes', 0) or 0)
        } for a in qs]
    })

# ========================= ROLE ANALYSIS =========================
@time_bp.route('/api/role_analysis', methods=['POST'])
def api_role_analysis_create():
    ensure_time_role_schema()
    d = request.get_json(force=True) or {}
    role_id = int(d.get('role_id'))
    name = (d.get('name') or 'Analyse rôle').strip()
    lines = d.get('lines') or []

    R = TimeRoleAnalysis(role_id=role_id, name=name, created_at=datetime.utcnow())
    db.session.add(R)
    db.session.flush()

    for ln in lines:
        db.session.add(TimeRoleLine(
            role_analysis_id=R.id,
            activity_id=int(ln['activity_id']),
            recurrence=(ln.get('recurrence') or 'journalier').strip().lower(),
            frequency=int(ln.get('frequency') or 1),
            duration_minutes=float(ln.get('duration') or 0)
        ))
    db.session.commit()
    return jsonify({"ok": True, "id": R.id})

def _line_duration(l):
    if getattr(l, 'duration_minutes', None):
        return float(l.duration_minutes or 0)
    return activity_duration_minutes(l.activity_id)

def _role_summary(R):
    sum_day = sum(_line_duration(l) * max(1, l.frequency) for l in R.lines if l.recurrence.startswith('jour'))
    sum_week = sum(_line_duration(l) * max(1, l.frequency) for l in R.lines if l.recurrence.startswith('hebdo'))
    sum_month = sum(_line_duration(l) * max(1, l.frequency) for l in R.lines if l.recurrence.startswith('mens'))
    sum_year = sum(_line_duration(l) * max(1, l.frequency) for l in R.lines if l.recurrence.startswith('ann'))

    p = get_calendar_params()
    # Une seule regle (`annuel_minutes`) : elle etait reecrite ici ET dans le
    # navigateur, et le tableau de bord en aurait fait une troisieme.
    annual = (annuel_minutes(sum_day, 'journalier', p)
              + annuel_minutes(sum_week, 'hebdomadaire', p)
              + annuel_minutes(sum_month, 'mensuel', p)
              + annuel_minutes(sum_year, 'annuel', p))
    monthly = annual / 12.0

    return {
        "sum_daily_minutes": float(sum_day),
        "sum_weekly_minutes": float(sum_week),
        "sum_monthly_minutes": float(sum_month),
        "sum_yearly_minutes": float(sum_year),
        "annual_minutes": float(annual),
        "monthly_minutes": float(monthly),
        "calendar": p
    }

@time_bp.route('/api/role_analysis/<int:rid>', methods=['GET', 'PATCH', 'DELETE'])
def api_role_analysis_read_patch_delete(rid):
    ensure_time_role_schema()
    R = TimeRoleAnalysis.query.get_or_404(rid)
    if request.method == 'PATCH':
        data = request.get_json(force=True) or {}
        new_name = (data.get('name') or '').strip()
        if new_name:
            R.name = new_name
        if data.get('role_id'):
            R.role_id = int(data['role_id'])
        # Le renommage seul reste possible : `lines` absent ne touche à rien.
        lignes = data.get('lines')
        if lignes is not None:
            for ancienne in TimeRoleLine.query.filter_by(role_analysis_id=R.id).all():
                db.session.delete(ancienne)
            db.session.flush()
            for ln in lignes:
                db.session.add(TimeRoleLine(
                    role_analysis_id=R.id,
                    activity_id=int(ln['activity_id']),
                    recurrence=(ln.get('recurrence') or 'journalier').strip().lower(),
                    frequency=int(ln.get('frequency') or 1),
                    duration_minutes=float(ln.get('duration') or 0)))
        db.session.commit()
        return jsonify({"ok": True, "id": R.id, "name": R.name})
    if request.method == 'DELETE':
        db.session.delete(R)
        db.session.commit()
        return jsonify({"ok": True, "deleted": True})

    rows = []
    for ln in R.lines:
        dur = _line_duration(ln)
        rows.append({
            "id": ln.id,
            "activity_id": ln.activity_id,
            "activity": Activities.query.get(ln.activity_id).name if ln.activity_id else "",
            "duration_minutes": float(dur),
            "recurrence": ln.recurrence,
            "frequency": ln.frequency,
            "weight_minutes": float(dur) * max(1, ln.frequency)
        })
    return jsonify({
        "ok": True,
        "role": {"id": R.id, "role_id": R.role_id, "name": R.name, "created_at": R.created_at.isoformat() if hasattr(R, "created_at") and R.created_at else None},
        "lines": rows,
        "summary": _role_summary(R)
    })

@time_bp.route('/api/role_analyses', methods=['GET'])
def api_role_analyses_list():
    ensure_time_role_schema()
    Rs = TimeRoleAnalysis.query.order_by(TimeRoleAnalysis.created_at.desc(), TimeRoleAnalysis.id.desc()).all()
    out = []
    for R in Rs:
        s = _role_summary(R)
        out.append({
            "id": R.id,
            "role_id": R.role_id,
            "role": Role.query.get(R.role_id).name if R.role_id else "",
            "name": getattr(R, "name", "Analyse rôle"),
            "created_at": R.created_at.isoformat() if hasattr(R, "created_at") and R.created_at else None,
            **s
        })
    return jsonify({"ok": True, "items": out})

@time_bp.route('/api/role_line/<int:line_id>', methods=['DELETE'])
def api_role_line_delete(line_id):
    ensure_time_role_schema()
    ln = TimeRoleLine.query.get_or_404(line_id)
    rid = ln.role_analysis_id
    db.session.delete(ln)
    db.session.flush()
    remaining = TimeRoleLine.query.filter_by(role_analysis_id=rid).count()
    deleted = False
    if remaining == 0:
        R = TimeRoleAnalysis.query.get(rid)
        if R:
            db.session.delete(R)
            deleted = True
    db.session.commit()
    return jsonify({"ok": True, "analysis_deleted": deleted, "analysis_id": rid})

# ========================= FAIBLESSE =========================
@time_bp.route('/api/weakness', methods=['POST'])
def api_weakness():
    d = request.get_json(force=True) or {}
    mode = (d.get('mode') or 'activity').strip().lower()
    activity_id = int(d.get('activity_id'))
    rec = (d.get('recurrence') or 'journalier').strip().lower()
    freq = int(d.get('frequency') or 1)
    weakness_txt = (d.get('weakness') or '').strip()
    save = bool(d.get('save'))

    L_qty = to_minutes(d.get('L_work_added', 0), d.get('L_unit') or 'minutes')
    M_qty = to_minutes(d.get('M_wait_added', 0), d.get('M_unit') or 'minutes')
    N_denom = max(1, int(d.get('N_prob_denom') or 1))

    C = to_minutes(d.get('delay_std', 0), d.get('delay_unit') or 'minutes')

    tasks_payload = d.get('tasks') or []
    if mode == 'tasks':
        B = sum(to_minutes(t.get('duration_std', 0), t.get('duration_unit') or 'minutes') for t in tasks_payload)
    else:
        B = to_minutes(d.get('duration_std', 0), d.get('duration_unit') or 'minutes')

    params = get_calendar_params()
    Sa = params['weeks_per_year']

    m = cout_faiblesse(B, C, rec, freq, L_qty, M_qty, N_denom, params)
    O, P, Q, Rv = m["O"], m["P"], m["Q"], m["R"]
    S, T, U, V = m["S"], m["T"], m["U"], m["V"]
    W, X, Y, Z, AA = m["W"], m["X"], m["Y"], m["Z"], m["AA"]

    if save:
        if mode == 'tasks' and tasks_payload:
            for t in tasks_payload:
                dur_task = to_minutes(t.get('duration_std', 0), t.get('duration_unit') or 'minutes')
                del_task = to_minutes(t.get('delay_std', 0), t.get('delay_unit') or 'minutes') if t.get('delay_std') is not None else 0
                db.session.add(TimeWeakness(
                    activity_id=activity_id, task_id=int(t.get('task_id')),
                    duration_std_minutes=dur_task, delay_std_minutes=del_task or 0,
                    recurrence=rec, frequency=freq, weakness=weakness_txt,
                    work_added_qty=L_qty, work_added_unit='minutes',
                    wait_added_qty=M_qty, wait_added_unit='minutes',
                    prob_denom=N_denom, created_at=datetime.utcnow()
                ))
            db.session.add(TimeWeakness(
                activity_id=activity_id, task_id=None,
                duration_std_minutes=B, delay_std_minutes=C,
                recurrence=rec, frequency=freq, weakness=weakness_txt,
                work_added_qty=L_qty, work_added_unit='minutes',
                wait_added_qty=M_qty, wait_added_unit='minutes',
                prob_denom=N_denom, created_at=datetime.utcnow()
            ))
        else:
            db.session.add(TimeWeakness(
                activity_id=activity_id, task_id=None,
                duration_std_minutes=B, delay_std_minutes=C,
                recurrence=rec, frequency=freq, weakness=weakness_txt,
                work_added_qty=L_qty, work_added_unit='minutes',
                wait_added_qty=M_qty, wait_added_unit='minutes',
                prob_denom=N_denom, created_at=datetime.utcnow()
            ))
        db.session.commit()

    return jsonify({
        "ok": True,
        "mode": mode,
        "activity_id": activity_id,
        "calc": {"O": O, "P": P, "Q": Q, "R": Rv, "S": S, "T": T, "U": U, "V": V, "W": W, "X": X, "Y": Y, "Z": Z, "AA": AA},
        "B_minutes": B, "C_minutes": C,
        "params": get_calendar_params()
    })


@time_bp.route('/api/weakness/<int:wid>', methods=['GET'])
def api_weakness_read(wid):
    """Tout ce qu'il faut pour rouvrir l'écran tel qu'il a été enregistré.

    ⚠️ Les quantités sont rendues EN MINUTES, avec leur unité à 'minutes' :
    c'est ainsi qu'elles sont stockées (`api_weakness` convertit avant
    d'écrire). Les rendre dans l'unité saisie demanderait de la stocker, ce
    que la table ne fait pas.
    """
    w = TimeWeakness.query.get_or_404(wid)
    act = Activities.query.get(w.activity_id)
    taches = []
    if w.task_id is None:
        for t in (TimeWeakness.query
                  .filter_by(activity_id=w.activity_id, weakness=w.weakness)
                  .filter(TimeWeakness.task_id.isnot(None))
                  .order_by(TimeWeakness.id).all()):
            tache = Task.query.get(t.task_id)
            taches.append({"task_id": t.task_id,
                           "task": tache.name if tache else "",
                           "duration_std": float(t.duration_std_minutes or 0),
                           "delay_std": float(t.delay_std_minutes or 0)})
    return jsonify({
        "ok": True,
        "item": {
            "id": w.id,
            "activity_id": w.activity_id,
            "activity": act.name if act else "",
            "mode": "tasks" if taches else "activity",
            "weakness": w.weakness or "",
            "recurrence": w.recurrence,
            "frequency": int(w.frequency or 1),
            "duration_std": float(w.duration_std_minutes or 0),
            "delay_std": float(w.delay_std_minutes or 0),
            "L_work_added": to_minutes(w.work_added_qty, w.work_added_unit),
            "M_wait_added": to_minutes(w.wait_added_qty, w.wait_added_unit),
            "N_prob_denom": int(w.prob_denom or 1),
            "tasks": taches,
        },
        "calc": cout_faiblesse(w.duration_std_minutes, w.delay_std_minutes,
                               w.recurrence, w.frequency,
                               to_minutes(w.work_added_qty, w.work_added_unit),
                               to_minutes(w.wait_added_qty, w.wait_added_unit),
                               w.prob_denom),
        "params": get_calendar_params(),
    })


@time_bp.route('/api/weakness/<int:wid>', methods=['PUT'])
def api_weakness_update(wid):
    """Modifie la faiblesse SANS changer son identifiant : l'écran qui vient
    de l'ouvrir la retrouve au même endroit."""
    w = TimeWeakness.query.get_or_404(wid)
    d = request.get_json(force=True) or {}
    mode = (d.get('mode') or 'activity').strip().lower()
    taches = d.get('tasks') or []

    L = to_minutes(d.get('L_work_added', 0), d.get('L_unit') or 'minutes')
    M = to_minutes(d.get('M_wait_added', 0), d.get('M_unit') or 'minutes')
    C = to_minutes(d.get('delay_std', 0), d.get('delay_unit') or 'minutes')
    if mode == 'tasks':
        B = sum(to_minutes(t.get('duration_std', 0),
                           t.get('duration_unit') or 'minutes') for t in taches)
    else:
        B = to_minutes(d.get('duration_std', 0), d.get('duration_unit') or 'minutes')

    # Les lignes par tâche de l'ANCIENNE version s'en vont : le libellé a pu
    # changer, et c'est lui qui les rattachait.
    for ligne in (TimeWeakness.query
                  .filter_by(activity_id=w.activity_id, weakness=w.weakness)
                  .filter(TimeWeakness.task_id.isnot(None)).all()):
        db.session.delete(ligne)
    db.session.flush()

    if d.get('activity_id'):
        w.activity_id = int(d['activity_id'])
    w.duration_std_minutes = B
    w.delay_std_minutes = C
    w.recurrence = (d.get('recurrence') or 'journalier').strip().lower()
    w.frequency = int(d.get('frequency') or 1)
    w.weakness = (d.get('weakness') or '').strip()
    w.work_added_qty = L
    w.work_added_unit = 'minutes'
    w.wait_added_qty = M
    w.wait_added_unit = 'minutes'
    w.prob_denom = max(1, int(d.get('N_prob_denom') or 1))

    if mode == 'tasks':
        for t in taches:
            db.session.add(TimeWeakness(
                activity_id=w.activity_id, task_id=int(t.get('task_id')),
                duration_std_minutes=to_minutes(t.get('duration_std', 0),
                                                t.get('duration_unit') or 'minutes'),
                delay_std_minutes=to_minutes(t.get('delay_std', 0),
                                             t.get('delay_unit') or 'minutes'),
                recurrence=w.recurrence, frequency=w.frequency, weakness=w.weakness,
                work_added_qty=L, work_added_unit='minutes',
                wait_added_qty=M, wait_added_unit='minutes',
                prob_denom=w.prob_denom, created_at=datetime.utcnow()))

    db.session.commit()
    return jsonify({
        "ok": True, "id": w.id,
        "calc": cout_faiblesse(B, C, w.recurrence, w.frequency, L, M, w.prob_denom),
        "params": get_calendar_params(),
    })


@time_bp.route('/api/weakness/<int:wid>', methods=['DELETE'])
def api_weakness_delete(wid):
    """Il n'existait aucune route pour retirer une faiblesse : une fois
    enregistree elle pesait a jamais dans le total de l'accueil."""
    w = TimeWeakness.query.get_or_404(wid)
    # Le mode « par taches » ecrit une ligne par tache PLUS une ligne de total
    # (task_id nul) : retirer le total doit emporter ses taches, sinon elles
    # restent en base sans rien qui les rattache.
    if w.task_id is None:
        # ⚠️ Objet par objet, PAS `delete(synchronize_session=False)` : ce
        # dernier laisse les lignes supprimees vivantes dans la session, et
        # le prochain flush tombe en « 'NoneType' object has no attribute
        # '__dict__' » — dans une route sans rapport.
        for ligne in (TimeWeakness.query
                      .filter_by(activity_id=w.activity_id, weakness=w.weakness)
                      .filter(TimeWeakness.task_id.isnot(None)).all()):
            db.session.delete(ligne)
    db.session.delete(w)
    db.session.commit()
    return jsonify({"ok": True, "deleted": True})


# ========================= TABLEAU DE BORD =========================
@time_bp.route('/api/tableau_de_bord', methods=['GET'])
def api_tableau_de_bord():
    """Tout ce que l'accueil de la page Temps affiche, en UNE requete.

    L'ecran s'ouvrait sur un formulaire vide a 0,0 h : on ne voyait nulle part
    ce qui avait deja ete mesure, ni ce qui restait a mesurer.
    """
    ensure_time_role_schema()
    params = get_calendar_params()
    plein_temps_min = heures_plein_temps(params) * 60.0

    activites = Activities.for_active_entity().order_by(Activities.name.asc()).all()
    noms = {a.id: a.name for a in activites}
    ids = list(noms.keys())

    # — Par activite : une ligne par analyse d'activite enregistree
    par_activite = []
    if ids:
        for x in (TimeAnalysis.query
                  .filter_by(type='activity')
                  .filter(TimeAnalysis.activity_id.in_(ids))
                  .order_by(TimeAnalysis.id.desc()).all()):
            par_periode = (float(x.duration or 0)
                           * max(1, int(x.frequency or 1))
                           * max(1, int(x.nb_people or 1)))
            par_activite.append({
                "id": x.id,
                "activity_id": x.activity_id,
                "activite": noms.get(x.activity_id, ""),
                "recurrence": x.recurrence,
                "frequence": int(x.frequency or 1),
                "personnes": int(x.nb_people or 1),
                "par_periode_min": par_periode,
                "annuel_min": annuel_minutes(par_periode, x.recurrence, params),
            })

    charge_annuelle = sum(a["annuel_min"] for a in par_activite)

    # — Par role : seules les analyses qui portent sur cette carto
    par_role = []
    for R in (TimeRoleAnalysis.query
              .order_by(TimeRoleAnalysis.created_at.desc(), TimeRoleAnalysis.id.desc())
              .all()):
        lignes = list(R.lines)
        if not any(ln.activity_id in noms for ln in lignes):
            continue
        resume = _role_summary(R)
        role = Role.query.get(R.role_id) if R.role_id else None
        par_role.append({
            "id": R.id,
            "role_id": R.role_id,
            "role": role.name if role else "",
            "nom": getattr(R, "name", None) or "",
            "n_activites": len(lignes),
            "annuel_min": resume["annual_minutes"],
            "mensuel_min": resume["monthly_minutes"],
        })

    # — Faiblesses : SEULEMENT les lignes de total (task_id nul). Le mode « par
    #   taches » ecrit en plus une ligne par tache : les compter toutes
    #   doublerait le cout de chaque faiblesse detaillee.
    faiblesses = []
    if ids:
        for w in (TimeWeakness.query
                  .filter(TimeWeakness.task_id.is_(None))
                  .filter(TimeWeakness.activity_id.in_(ids))
                  .order_by(TimeWeakness.id.desc()).all()):
            m = cout_faiblesse(w.duration_std_minutes, w.delay_std_minutes,
                               w.recurrence, w.frequency,
                               to_minutes(w.work_added_qty, w.work_added_unit),
                               to_minutes(w.wait_added_qty, w.wait_added_unit),
                               w.prob_denom, params)
            faiblesses.append({
                "id": w.id,
                "activity_id": w.activity_id,
                "activite": noms.get(w.activity_id, ""),
                "nom": (w.weakness or "").strip(),
                "recurrence": w.recurrence,
                "occurrences": m["AA"],
                "travail_annuel_min": m["U"],
                "attente_annuelle_min": m["V"],
                "annuel_min": m["U"] + m["V"],
                "mensuel_min": m["W"] + m["X"],
            })
    # ⚠️ On trie sur le TRAVAIL refait, pas sur le total : l'attente d'un
    # fournisseur peut peser des centaines d'heures sans couter une minute de
    # travail, et mettrait cette faiblesse-la en tete de liste.
    faiblesses.sort(key=lambda f: f["travail_annuel_min"], reverse=True)
    travail_faiblesses = sum(f["travail_annuel_min"] for f in faiblesses)
    attente_faiblesses = sum(f["attente_annuelle_min"] for f in faiblesses)

    # — Projets : ponctuels, ils ne rentrent pas dans la charge ANNUELLE
    projets = []
    for p in (TimeProject.for_active_entity()
              .order_by(TimeProject.created_at.desc(), TimeProject.id.desc()).all()):
        projets.append({
            "id": p.id,
            "nom": p.name or "",
            "n_activites": len(p.lines),
            "charge_min": sum(float(ln.duration_minutes) * max(1, ln.nb_people) for ln in p.lines),
            "duree_min": sum(float(ln.duration_minutes) for ln in p.lines),
        })

    mesurees = {a["activity_id"] for a in par_activite}
    # ⚠️ Les NOMS, pas seulement le compte : « 12 sur 12 » ne dit pas quoi
    # faire. Plafonné — une carto de six cents activités n'a pas a les
    # envoyer toutes pour remplir une carte qui en montre trois.
    a_chiffrer = [{"id": a.id, "nom": a.name}
                  for a in activites if a.id not in mesurees][:60]
    chiffrees = len(mesurees)

    return jsonify({
        "ok": True,
        "calendrier": params,
        "plein_temps_min": plein_temps_min,
        "charge": {
            "annuel_min": charge_annuelle,
            "mensuel_min": charge_annuelle / 12.0,
            "hebdo_min": (charge_annuelle / float(params['weeks_per_year'])
                          if params['weeks_per_year'] else 0.0),
            # ⚠️ NUL (et non zero) quand rien n'est mesure : « 0 equivalent
            # temps plein » se lit comme un resultat, « — » comme une absence.
            "etp": (charge_annuelle / plein_temps_min) if (plein_temps_min and charge_annuelle) else None,
        },
        "faiblesses": {
            # ⚠️ DEUX natures, jamais additionnees : `travail_min` est du
            # travail refait, comparable a la charge ; `attente_min` est du
            # temps d'horloge, qui ne coute de travail a personne. Les sommer
            # donnait « 84 % de la charge » pour 5 % reels.
            "travail_min": travail_faiblesses,
            "attente_min": attente_faiblesses,
            "part": (travail_faiblesses / charge_annuelle) if charge_annuelle else None,
            "items": faiblesses,
        },
        "couverture": {"chiffrees": chiffrees, "total": len(ids),
                       "a_chiffrer": a_chiffrer},
        "par_role": par_role,
        "par_activite": par_activite,
        "projets": projets,
    })
