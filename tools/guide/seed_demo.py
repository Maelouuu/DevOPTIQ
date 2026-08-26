"""Base de démonstration réaliste pour le guide utilisateur (tools/guide).

Injecte la cartographie example.vsdx via l'API (→ activités/rôles/liens réels),
puis enrichit : tâches, outils, compétences, S/SF/Apt/HSC, titulaires, managers,
paramètres RH, analyses de temps. Enfin sert l'app sur :5601.
"""
import json
import os
import random
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(BASE, '..', '..'))
sys.path.insert(0, REPO)
random.seed(42)

DB = os.path.join(BASE, 'demo_v2.db')
if os.path.exists(DB):
    os.remove(DB)

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
    ent = Entity(name="AFDEC Industrie", description="Site de production — démo")
    db.session.add(ent); db.session.flush()

    def mkuser(fn, ln, email, status="viewer", age=None):
        # lang='fr' : le guide est en français, les captures doivent montrer
        # l'interface française. L'anglais est le défaut produit depuis que
        # users.lang existe — sans ce paramètre les écrans sortiraient en anglais.
        u = User(entity_id=ent.id, first_name=fn, last_name=ln, email=email,
                 password=hash_password("Visual123!"), status=status, age=age,
                 lang="fr")
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

diagram = json.load(open(os.path.join(BASE, 'example_diagram.json')))
r = client.post('/cartography/api/save', json={'diagram': diagram})
print("[seed] save carto:", r.status_code, r.get_json())

# ── Enrichissement des activités créées par la carto ──
TOOL_POOL = [
    ("ERP OptiFab", "ERP de gestion de production"),
    ("CRM VentePlus", "Suivi des demandes et offres clients"),
    ("Suite bureautique", "Documents, tableurs et messagerie"),
    ("Banc de test labo", "Essais et mesures en laboratoire"),
    ("GED Docurex", "Gestion électronique des documents"),
]
TASK_VERBS = ["Préparer", "Vérifier", "Saisir", "Valider", "Transmettre", "Contrôler"]

with app.app_context():
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
            a.description = f"Réaliser « {a.name.strip()} » dans le respect des standards qualité."
        for j in range(1, random.choice([3, 4])):
            db.session.add(Task(
                name=f"{TASK_VERBS[(i + j) % len(TASK_VERBS)]} {a.name.strip().lower()[:40]}",
                description="", activity_id=a.id, order=j,
                duration_minutes=random.choice([15, 30, 45, 60]),
                delay_minutes=random.choice([0, 30, 60])))
        db.session.add(Competency(
            description=f"Produire le résultat attendu de « {a.name.strip()} » conforme du premier coup",
            activity_id=a.id))
        if i % 2 == 0:
            db.session.add(Savoir(description="Processus qualité ISO 9001 du site", activity_id=a.id))
            db.session.add(SavoirFaire(description="Utiliser l'ERP OptiFab au quotidien", activity_id=a.id))
        if i % 3 == 0:
            db.session.add(Aptitude(description="Rigueur et sens du détail", activity_id=a.id))
            db.session.add(Softskill(habilete="Communiquer efficacement avec les parties prenantes",
                                     niveau=3, justification="Interfaces quotidiennes avec les clients et l'atelier",
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
    missions = ["Garantir le traitement des demandes clients de bout en bout.",
                "Piloter la réalisation des offres et leur négociation.",
                "Assurer la préparation et le suivi des projets."]
    for k, r_ in enumerate(roles[:3]):
        r_.mission_generale = missions[k % len(missions)]

    db.session.commit()
    print("[seed] enrichissement OK")

# ── Analyses de temps via les mêmes APIs que l'UI ──
with app.app_context():
    ids = [a.id for a in Activities.query.order_by(Activities.id).limit(6).all()]
    role_ids = [r_.id for r_ in Role.query.order_by(Role.id).all()]

r = client.post('/temps/api/project', json={
    "name": "Lancement gamme 2026",
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
        "role_id": role_ids[0], "name": "Charge type — semaine standard",
        "lines": [
            {"activity_id": ids[0], "duration": 90, "recurrence": "journalier", "frequency": 1},
            {"activity_id": ids[1], "duration": 120, "recurrence": "hebdomadaire", "frequency": 2},
        ]})
    print("[seed] analyse rôle:", r.status_code)

r = client.post('/temps/api/weakness', json={
    "mode": "activity", "activity_id": ids[1], "recurrence": "hebdomadaire",
    "frequency": 3, "weakness": "Données client incomplètes à la réception",
    "L_work_added": 25, "L_unit": "minutes", "M_wait_added": 2, "M_unit": "heures",
    "N_prob_denom": 4, "duration_std": 40, "duration_unit": "minutes",
    "delay_std": 1, "delay_unit": "heures", "save": True})
print("[seed] faiblesse:", r.status_code)

print("SEED V2 OK")
app.run(host="127.0.0.1", port=5601, debug=False, use_reloader=False)
