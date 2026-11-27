"""Instance jetable pour mettre au point la CHARGE DE TRAVAIL (page RH).

    python tools/devrun_charge.py    → http://127.0.0.1:8142/gestion_rh/

Tous les états que la section ④ doit savoir montrer, présents EN MÊME TEMPS :

  · un rôle mesuré dans DEUX cartos — c'est la comparaison « extra entité »,
    et sans elle le damier n'a qu'une colonne ;
  · un rôle qui dépasse largement un temps plein, et d'autres très légers —
    sinon l'échelle de chaleur ne montre jamais que sa première teinte ;
  · un rôle mesuré le mois DERNIER seulement, et un rôle JAMAIS mesuré : les
    deux absences ne se corrigent pas de la même façon, et « non mesuré » ne
    vaut jamais zéro ;
  · une personne au-delà du plafond de 80 %, une juste en dessous, une très
    légère, et une dont le seul rôle n'est pas mesuré ;
  · DEUX périodes, pour que le sélecteur de mois existe.

`/devrun/en` et `/devrun/fr` basculent la langue : les libellés construits en
JS ne se vérifient qu'à l'écran.

Outil de mise au point AFDEC : `tools/` est exclu de l'image (.dockerignore).
"""
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PORT = int(os.environ.get("PORT", "8142"))

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

from Code.app import create_app                      # noqa: E402
from Code.extensions import db                       # noqa: E402

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///%s" % db_path,
    "SECRET_KEY": "dev-charge",
    "WTF_CSRF_ENABLED": False,
    "MAIL_SUPPRESS_SEND": True,
    "TEMPLATES_AUTO_RELOAD": True,
    "SEND_FILE_MAX_AGE_DEFAULT": 0,
})
app.jinja_env.auto_reload = True

MOIS, MOIS_AVANT = "2026-11", "2026-10"

#: (rôle, carto, période, nb d'activités, durée min, récurrence, fréquence)
#  Le poids vient du RYTHME autant que de la durée : « Qualité » déborde parce
#  qu'elle est journalière sur neuf activités.
ANALYSES = [
    ("Qualité",     "FluidClip", MOIS,       9, 55, "journalier",   1),
    ("Qualité",     "END_DT",    MOIS,       7, 42, "journalier",   1),
    ("Logistique",  "FluidClip", MOIS,       5, 70, "hebdomadaire", 3),
    ("Méthodes",    "FluidClip", MOIS,       4, 90, "hebdomadaire", 1),
    ("Achats",      "END_DT",    MOIS,       4, 120, "mensuel",     2),
    ("Maintenance", "FluidClip", MOIS_AVANT, 3, 45, "hebdomadaire", 2),
]

#: qui tient quoi — « Réseau » n'est jamais mesuré
TENUS = [
    ("Hubert", ("Qualité", "Achats")),
    ("Madhuri", ("Logistique",)),
    ("Vaishali", ("Méthodes", "Maintenance")),
    ("Priya", ("Réseau",)),
]

with app.app_context():
    from Code.models.models import (Activities, Entity, EntrepriseSettings, Role,
                                    TimeRoleAnalysis, TimeRoleLine, User, UserRole,
                                    activity_roles)
    from Code.roles_permanents import role_dev_competences
    from Code.security import hash_password

    db.drop_all()
    db.create_all()

    dev = User(first_name="Mael", last_name="Girardin", email="dev@test.local",
               password=hash_password("Test1234!"), status="administrateur", lang="fr")
    db.session.add(dev)
    db.session.commit()

    cartos = {}
    for i, nom in enumerate(("FluidClip", "END_DT")):
        e = Entity(name=nom, description="carto de mise au point",
                   owner_id=dev.id, is_active=(i == 0), is_shared=True)
        db.session.add(e)
        cartos[nom] = e
    db.session.commit()

    # ⚠️ Le calendrier : sans lui `get_calendar_params` retombe sur son repli,
    # et on ne verrait jamais si l'écran lit bien ce qui est réglé.
    # 47 sem. × 5 j × 7 h = 1 645 h → plafond 80 % = 1 316 h.
    db.session.add(EntrepriseSettings(entity_id=cartos["FluidClip"].id,
                                      work_hours_per_day=7, work_days_per_week=5,
                                      work_weeks_per_year=47))
    db.session.commit()

    role_dev_competences(cartos["FluidClip"].id)
    roles = {}
    for nom in ("Qualité", "Logistique", "Achats", "Méthodes", "Maintenance", "Réseau"):
        r = Role(name=nom, entity_id=cartos["FluidClip"].id)
        db.session.add(r)
        roles[nom] = r
    db.session.commit()

    gens = {}
    for prenom, nom, mail, statut in (
            ("Hubert", "Grandjean", "hubert@test.local", "champion"),
            ("Madhuri", "Patil", "madhuri@test.local", "champion"),
            ("Vaishali", "Rao", "vaishali@test.local", "user"),
            ("Priya", "Bhivare", "priya@test.local", "user")):
        u = User(first_name=prenom, last_name=nom, email=mail,
                 password=hash_password("Test1234!"), status=statut, lang="fr")
        db.session.add(u)
        gens[prenom] = u
    db.session.commit()

    # Les activités : deux cartos, assez pour que chaque analyse ait les
    # siennes. ⚠️ Toutes dans LEUR carto : c'est de là que la section tire la
    # colonne d'une mesure.
    actes = {}
    for nom, e in cartos.items():
        for i in range(12):
            a = Activities(name="%s · activité %d" % (nom, i + 1),
                           entity_id=e.id, shape_id="ch-%s-%d" % (nom, i))
            a.duration_minutes = 45 + i * 5
            db.session.add(a)
            actes.setdefault(nom, []).append(a)
    db.session.commit()

    for nom, e in cartos.items():
        for i, a in enumerate(actes[nom]):
            db.session.execute(activity_roles.insert().values(
                activity_id=a.id, role_id=roles["Qualité" if i < 6 else "Logistique"].id,
                status="Garant"))
    db.session.commit()

    for role, carto, per, n, duree, rec, freq in ANALYSES:
        R = TimeRoleAnalysis(role_id=roles[role].id, name="Charge · " + role,
                             periode=per, created_at=datetime.utcnow())
        db.session.add(R)
        db.session.flush()
        for i in range(n):
            db.session.add(TimeRoleLine(
                role_analysis_id=R.id, activity_id=actes[carto][i].id,
                recurrence=rec, frequency=freq, duration_minutes=float(duree)))
    db.session.commit()

    for qui, rs in TENUS:
        for r in rs:
            db.session.add(UserRole(user_id=gens[qui].id, role_id=roles[r].id))
    db.session.commit()

    from Code.charge_travail import charge
    d = charge()
    print("[devrun] base  : %s" % db_path)
    print("[devrun] compte: dev@test.local / Test1234!")
    print("[devrun] periode %s | temps plein %.0f h | plafond %.0f h"
          % (d["periode"], d["plein_temps_min"] / 60, d["plafond_min"] / 60))
    for r in d["roles"]:
        print("[devrun]   %-13s %7s  %d mesure(s)"
              % (r["nom"],
                 "—" if r["annuel_min"] is None else "%.0f h" % (r["annuel_min"] / 60),
                 len(r["mesures"])))
    for p in d["personnes"]:
        if p["n_roles"]:
            print("[devrun]   · %-20s %7s  %s du plafond"
                  % (p["nom"],
                     "—" if p["annuel_min"] is None else "%.0f h" % (p["annuel_min"] / 60),
                     "—" if p["part_plafond"] is None else "%.0f %%" % (p["part_plafond"] * 100)))
    print("[devrun] http://127.0.0.1:%d/gestion_rh/   (/devrun/en pour l'anglais)" % PORT)


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
        return redirect("/gestion_rh/")
    return None


@app.route("/devrun/<langue>")
def _devrun_langue(langue):
    from flask import redirect, session
    from Code.models.models import User

    u = User.query.filter_by(email="dev@test.local").first()
    session["user_email"] = u.email
    session["user_id"] = u.id
    session["lang"] = "en" if langue.startswith("en") else "fr"
    return redirect("/gestion_rh/")


app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
