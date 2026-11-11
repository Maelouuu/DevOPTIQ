"""Instance jetable pour mettre au point la PAGE TEMPS.

    python tools/devrun_temps.py    → http://127.0.0.1:8127/temps/

Les états que l'accueil doit savoir montrer, tous présents en même temps :
une charge mesurée qui dépasse le temps plein sur un rôle et pas sur l'autre,
des faiblesses de coûts très inégaux, et surtout des activités **non
chiffrées** — sans elles on ne voit jamais que le cas heureux, où le total
annoncé porte sur toute la carto.

`/devrun/en` et `/devrun/fr` basculent la langue : les libellés construits en
JS ne se vérifient qu'à l'écran.

Outil de mise au point AFDEC : `tools/` est exclu de l'image (.dockerignore).
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = int(os.environ.get("PORT", "8127"))

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

from Code.app import create_app                      # noqa: E402
from Code.extensions import db                       # noqa: E402

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///%s" % db_path,
    "SECRET_KEY": "dev-temps",
    "WTF_CSRF_ENABLED": False,
    "MAIL_SUPPRESS_SEND": True,
    # Sinon Jinja garde le gabarit compilé en mémoire et le navigateur garde
    # les fichiers statiques : on retouche le CSS et rien ne bouge à l'écran.
    "TEMPLATES_AUTO_RELOAD": True,
    "SEND_FILE_MAX_AGE_DEFAULT": 0,
})
app.jinja_env.auto_reload = True

# (nom, durée min, délai min)
ACTIVITES = [
    ("Clarifier la demande client", 45, 120),
    ("Chiffrer l'offre", 90, 240),
    ("Concevoir la solution preliminaire", 180, 480),
    ("Consulter les fournisseurs", 60, 1440),
    ("Valider le devis fournisseur", 30, 120),
    ("Emettre la commande", 25, 60),
    ("Suivre la livraison", 20, 0),
    ("Controler la reception", 40, 0),
    ("Mettre a jour la base articles", 35, 0),
    ("Archiver le dossier", 15, 0),
    ("Repondre a une reclamation", 75, 360),
    ("Preparer la revue mensuelle", 120, 0),
]

# Analyses d'activité : (index activité, récurrence, fréquence, personnes)
#   Seules SIX des douze activités sont chiffrées : c'est ce qui rend la carte
#   « ce qui n'est pas chiffré » lisible, et le total honnête.
CHIFFREES = [
    (0, "journalier",   2, 1),
    (1, "hebdomadaire", 3, 2),
    (2, "mensuel",      2, 1),
    (3, "hebdomadaire", 1, 1),
    (5, "journalier",   4, 1),
    (10, "mensuel",     1, 1),
]

# Faiblesses : (index activité, libellé, récurrence, fréq, 1/N, +travail, +attente)
FAIBLESSES = [
    (1, "Donnees techniques manquantes", "hebdomadaire", 3, 2, 45, 180),
    (3, "Fournisseur qui ne repond pas", "hebdomadaire", 1, 3, 20, 2880),
    (8, "Reference article erronee", "journalier", 1, 10, 15, 0),
]

with app.app_context():
    from Code.models.models import (Activities, Entity, EntrepriseSettings, Role,
                                    TimeAnalysis, TimeProject, TimeProjectLine,
                                    TimeRoleAnalysis, TimeRoleLine, TimeWeakness,
                                    User, UserRole, activity_roles)
    from Code.roles_permanents import role_dev_competences
    from Code.security import hash_password

    db.drop_all()
    db.create_all()

    dev = User(first_name="Mael", last_name="Girardin", email="dev@test.local",
               password=hash_password("Test1234!"), status="administrateur", lang="fr")
    db.session.add(dev)
    db.session.commit()

    ent = Entity(name="Achats", description="entite de mise au point",
                 owner_id=dev.id, is_active=True)
    db.session.add(ent)
    db.session.commit()

    # Le calendrier de travail : sans lui `get_calendar_params` retombe sur son
    # repli, et on ne verrait jamais si la page lit bien ce qui est réglé.
    db.session.add(EntrepriseSettings(entity_id=ent.id, work_hours_per_day=7,
                                      work_days_per_week=5, work_weeks_per_year=45))
    db.session.commit()

    role_dev_competences(ent.id)
    acheteur = Role(name="Acheteur", entity_id=ent.id)
    appro = Role(name="Approvisionneur", entity_id=ent.id)
    db.session.add_all([acheteur, appro])
    db.session.commit()
    db.session.add(UserRole(user_id=dev.id, role_id=acheteur.id))
    db.session.commit()

    actes = []
    for i, (nom, duree, delai) in enumerate(ACTIVITES):
        a = Activities(name=nom, entity_id=ent.id, shape_id="tm-%d" % i)
        a.duration_minutes = duree
        a.delay_minutes = delai
        db.session.add(a)
        actes.append(a)
    db.session.commit()

    # Qui tient quoi : l'Acheteur en porte huit, l'Approvisionneur quatre —
    # une barre au-dessus du temps plein, l'autre bien en dessous.
    for i, a in enumerate(actes):
        db.session.execute(activity_roles.insert().values(
            activity_id=a.id, role_id=(acheteur.id if i < 8 else appro.id),
            status="Garant"))
    db.session.commit()

    for idx, rec, freq, nb in CHIFFREES:
        db.session.add(TimeAnalysis(
            type="activity", activity_id=actes[idx].id,
            duration=int(actes[idx].duration_minutes), recurrence=rec,
            frequency=freq, nb_people=nb, delay=None, impact_unit="minutes"))
    db.session.commit()

    # Deux analyses de rôle : celle de l'Acheteur déborde le temps plein.
    for role, bornes, nom in ((acheteur, (0, 8), "Charge d'un acheteur"),
                              (appro, (8, 12), "Charge d'un approvisionneur")):
        R = TimeRoleAnalysis(role_id=role.id, name=nom, created_at=datetime.utcnow())
        db.session.add(R)
        db.session.flush()
        for i in range(*bornes):
            db.session.add(TimeRoleLine(
                role_analysis_id=R.id, activity_id=actes[i].id,
                recurrence=("journalier" if i % 3 == 0 else
                            "hebdomadaire" if i % 3 == 1 else "mensuel"),
                frequency=(2 if i % 2 else 1),
                duration_minutes=float(actes[i].duration_minutes)))
    db.session.commit()

    for idx, libelle, rec, freq, denom, travail, attente in FAIBLESSES:
        db.session.add(TimeWeakness(
            activity_id=actes[idx].id, task_id=None,
            duration_std_minutes=float(actes[idx].duration_minutes),
            delay_std_minutes=float(actes[idx].delay_minutes),
            recurrence=rec, frequency=freq, weakness=libelle,
            work_added_qty=travail, work_added_unit="minutes",
            wait_added_qty=attente, wait_added_unit="minutes",
            prob_denom=denom, created_at=datetime.utcnow()))
    db.session.commit()

    for nom, lignes, jours in (("Refonte du catalogue fournisseurs", (0, 1, 2), 3),
                               ("Campagne de renegociation", (3, 4), 9)):
        p = TimeProject(name=nom, entity_id=ent.id,
                        created_at=datetime.utcnow() - timedelta(days=jours))
        db.session.add(p)
        db.session.flush()
        for i in lignes:
            db.session.add(TimeProjectLine(
                project_id=p.id, activity_id=actes[i].id,
                duration_minutes=float(actes[i].duration_minutes),
                delay_minutes=float(actes[i].delay_minutes), nb_people=2))
    db.session.commit()

    print("[devrun] base  : %s" % db_path)
    print("[devrun] compte: dev@test.local / Test1234!")
    print("[devrun] %d activites, %d chiffrees, %d faiblesses, 2 roles, 2 projets"
          % (len(ACTIVITES), len(CHIFFREES), len(FAIBLESSES)))
    print("[devrun] http://127.0.0.1:%d/temps/   (/devrun/en pour l'anglais)" % PORT)


@app.before_request
def _devrun_toujours_connecte():
    """On arrive toujours connecté : l'outil sert à REGARDER la page."""
    from flask import redirect, request, session
    from Code.models.models import User

    if request.path.startswith("/devrun/"):
        return None
    if not session.get("user_id"):
        u = User.query.filter_by(email="dev@test.local").first()
        if u:
            session["user_email"] = u.email
            session["user_id"] = u.id
            session["lang"] = session.get("lang") or "fr"
    if request.path == "/":
        return redirect("/temps/")
    return None


@app.route("/devrun/<langue>")
def _devrun_langue(langue):
    """Bascule de langue en un clic : les libellés construits en JS ne se
    vérifient qu'à l'écran, dans les deux langues."""
    from flask import redirect, session
    from Code.models.models import User

    u = User.query.filter_by(email="dev@test.local").first()
    session["user_email"] = u.email
    session["user_id"] = u.id
    session["lang"] = "en" if langue.startswith("en") else "fr"
    return redirect("/temps/")


app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
