"""Base de démonstration réaliste pour le guide utilisateur (tools/guide).

Injecte la cartographie example.vsdx via l'API (→ activités/rôles/liens réels),
puis enrichit : tâches, outils, compétences, S/SF/Apt/HSC, titulaires, managers,
paramètres RH, analyses de temps. Enfin sert l'app sur :5601.
"""
import io
import json
import os
import random
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(BASE, '..', '..'))
sys.path.insert(0, REPO)
sys.path.insert(0, BASE)
random.seed(42)

DB = os.path.join(BASE, 'demo_v2.db')
if os.path.exists(DB):
    os.remove(DB)

import demo_data_i18n as I

from flask import session

from Code.app import create_app
from Code.extensions import db

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{DB}",
    "SECRET_KEY": "guide-demo",
    "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
})

from Code.security import hash_password
from Code.models.models import (Entity, User, Activities, Task, Tool, Role,
                                Competency, Softskill, Savoir, SavoirFaire,
                                Aptitude, UserRole, EntrepriseSettings,
                                activity_roles)

with app.app_context():
    db.create_all()
    ent = Entity(name=I.ENTITE_NOM, description=I.ENTITE_DESC)
    db.session.add(ent); db.session.flush()

    def mkuser(fn, ln, email, status="viewer", age=None):
        # lang=I.LANG : le guide existe en FR et en EN, les captures doivent
        # montrer l'interface dans la langue du guide. L'anglais est le défaut
        # produit depuis que users.lang existe : sans ce paramètre, tout sortirait en anglais.
        u = User(entity_id=ent.id, first_name=fn, last_name=ln, email=email,
                 password=hash_password("Visual123!"), status=status, age=age,
                 lang=I.LANG)
        db.session.add(u)
        return u

    admin  = mkuser("Mael", "Girardin", "demo@afdec.fr", "admin", 34)
    claire = mkuser("Claire", "Dupont", "claire@afdec.fr", age=41)
    karim  = mkuser("Karim", "Benali", "karim@afdec.fr", age=29)
    sophie = mkuser("Sophie", "Martin", "sophie@afdec.fr", age=36)
    lucas  = mkuser("Lucas", "Moreau", "lucas@afdec.fr", age=25)
    db.session.flush()
    ent.owner_id = admin.id
    for u in (claire, karim, sophie, lucas):
        u.manager_id = admin.id

    st = EntrepriseSettings(work_hours_per_day=7.5, work_days_per_week=5,
                            work_weeks_per_year=47)
    try:
        st.work_days_per_year = 220
    except Exception:
        pass
    st.entity_id = ent.id if hasattr(st, 'entity_id') else None
    db.session.add(st)
    db.session.commit()
    print("[seed] entité + utilisateurs OK")

# ── Injection de la cartographie via l'API (crée activités/rôles/liens) ──
client = app.test_client()
with client.session_transaction() as s:
    s['user_id'] = 1
    s['user_email'] = 'demo@afdec.fr'
    s['active_entity_id'] = 1

diagram = json.load(io.open(os.path.join(BASE, 'example_diagram.json'), encoding='utf-8'))
print('[seed] langue =', I.LANG, '| libelles sans traduction :',
      I.libelles_non_traduits(diagram) or 'aucun')
I.traduire_diagramme(diagram)
r = client.post('/cartography/api/save', json={'diagram': diagram})
print("[seed] save carto:", r.status_code, r.get_json())

# ── Enrichissement des activités créées par la carto ──
TOOL_POOL = I.OUTILS
TASK_VERBS = I.VERBES

# test_request_context (et non app_context) : les listeners RecentEvent lisent
# session['lang'] pour ecrire « Role cree : … » dans la bonne langue.
with app.test_request_context():
    session['lang'] = I.LANG
    ent = Entity.query.first()
    acts = Activities.query.filter_by(entity_id=ent.id).order_by(Activities.id).all()
    roles = Role.query.filter_by(entity_id=ent.id).order_by(Role.id).all()
    print(f"[seed] {len(acts)} activités, {len(roles)} rôles issus de la carto :",
          [r_.name for r_ in roles])

    tools = []
    for name, desc in TOOL_POOL:
        t = Tool(entity_id=ent.id, name=name, description=desc)
        db.session.add(t); tools.append(t)
    db.session.flush()

    for i, a in enumerate(acts):
        if not a.description:
            a.description = I.description_activite(a.name.strip())
        for j in range(1, random.choice([3, 4])):
            db.session.add(Task(
                name=f"{TASK_VERBS[(i + j) % len(TASK_VERBS)]} {a.name.strip().lower()[:40]}",
                description="", activity_id=a.id, order=j,
                duration_minutes=random.choice([15, 30, 45, 60]),
                delay_minutes=random.choice([0, 30, 60])))
        db.session.add(Competency(
            description=I.competence_activite(a.name.strip()),
            activity_id=a.id))
        if i % 2 == 0:
            db.session.add(Savoir(description=I.SAVOIR, activity_id=a.id))
            db.session.add(SavoirFaire(description=I.SAVOIR_FAIRE, activity_id=a.id))
        if i % 3 == 0:
            db.session.add(Aptitude(description=I.APTITUDE, activity_id=a.id))
            db.session.add(Softskill(habilete=I.HSC,
                                     niveau=3, justification=I.HSC_JUSTIF,
                                     activity_id=a.id))

    # Titulaires : répartir les collaborateurs sur les rôles qui portent
    # réellement des activités (bandes Garant de la carto)
    rows = db.session.execute(activity_roles.select()).fetchall()
    role_ids_with_acts = [r_.id for r_ in roles if any(x.role_id == r_.id for x in rows)]
    pool = role_ids_with_acts or [r_.id for r_ in roles]
    users = User.query.filter(User.email != 'demo@afdec.fr').all()
    for k, u in enumerate(users):
        db.session.add(UserRole(user_id=u.id, role_id=pool[k % len(pool)], manager_id=1))
        if len(pool) > 1 and k == 0:
            db.session.add(UserRole(user_id=u.id, role_id=pool[1 % len(pool)], manager_id=1))

    # Missions générales sur les rôles
    missions = I.MISSIONS
    for k, r_ in enumerate(roles[:3]):
        r_.mission_generale = missions[k % len(missions)]

    db.session.commit()
    print("[seed] enrichissement OK")

# ── Analyses de temps via les mêmes APIs que l'UI ──
with app.app_context():
    ids = [a.id for a in Activities.query.order_by(Activities.id).limit(6).all()]
    role_ids = [r_.id for r_ in Role.query.order_by(Role.id).all()]

r = client.post('/temps/api/project', json={
    "name": I.PROJET_NOM,
    "lines": [
        {"activity_id": ids[0], "duration": 2, "duration_unit": "heures", "delay": 1, "delay_unit": "jours", "nb_people": 2},
        {"activity_id": ids[1], "duration": 4, "duration_unit": "heures", "delay": 2, "delay_unit": "jours", "nb_people": 1},
        {"activity_id": ids[2], "duration": 1, "duration_unit": "jours", "delay": 3, "delay_unit": "jours", "nb_people": 3},
    ]})
print("[seed] projet temps:", r.status_code)

for aid, dur in [(ids[0], 45), (ids[3], 90)]:
    r = client.post('/temps/api/activity_workload', json={
        "activity_id": aid, "duration": dur, "duration_unit": "minutes",
        "recurrence": "hebdomadaire", "frequency": 2, "nb_people": 1})
    print("[seed] analyse activité:", r.status_code)

if role_ids:
    r = client.post('/temps/api/role_analysis', json={
        "role_id": role_ids[0], "name": I.CHARGE_ROLE,
        "lines": [
            {"activity_id": ids[0], "duration": 90, "recurrence": "journalier", "frequency": 1},
            {"activity_id": ids[1], "duration": 120, "recurrence": "hebdomadaire", "frequency": 2},
        ]})
    print("[seed] analyse rôle:", r.status_code)

r = client.post('/temps/api/weakness', json={
    "mode": "activity", "activity_id": ids[1], "recurrence": "hebdomadaire",
    "frequency": 3, "weakness": I.FAIBLESSE,
    "L_work_added": 25, "L_unit": "minutes", "M_wait_added": 2, "M_unit": "heures",
    "N_prob_denom": 4, "duration_std": 40, "duration_unit": "minutes",
    "delay_std": 1, "delay_unit": "heures", "save": True})
print("[seed] faiblesse:", r.status_code)

print("SEED V2 OK")
app.run(host="127.0.0.1", port=5601, debug=False, use_reloader=False)
