"""Instance jetable pour mettre au point la CARTO COMMUNE (page Partage, examen).

    python tools/devrun_partage.py           → http://127.0.0.1:8124

Les QUATRE paliers, mot de passe `Test1234!` :
    user@test.local      user          — CONSULTE : ne modifie rien, ne propose rien
    champion@test.local  champion      — propose, ne valide pas
    coord@test.local     coordinateur  — règle l'accès, arbitre les propositions
    admin@test.local     administrateur

Une carto commune (ouverte à tous, aucun rôle coché) appartenant au champion, et
une proposition EN ATTENTE déposée par `user` — de quoi ouvrir l'examen sans
avoir à rejouer tout le parcours à chaque essai.

Outil de mise au point AFDEC : `tools/` est exclu de l'image (.dockerignore).
"""
import copy
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CARTO = sys.argv[1] if len(sys.argv) > 1 else "tools/provisioning/carto/map_rfq_fluidclip.json"
PORT = int(os.environ.get("PORT", "8124"))

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

from Code.app import create_app                      # noqa: E402
from Code.extensions import db                       # noqa: E402

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
    "SECRET_KEY": "dev-partage",
    "WTF_CSRF_ENABLED": False,
    "MAIL_SUPPRESS_SEND": True,
})


def _modifier(diagram):
    """Une proposition doit CHANGER quelque chose de visible : on renomme,
    on déplace et on retire, pour que l'avant/après ait de quoi montrer."""
    d = copy.deepcopy(diagram)
    formes = d.get("shapes", [])
    for s in formes[:1]:
        s["label"] = "ACTIVITÉ RENOMMÉE PAR LA PROPOSITION"
    for s in formes[1:3]:
        s["x"] = int(s.get("x", 0)) + 260
        s["y"] = int(s.get("y", 0)) + 90
    if len(formes) > 6:
        retiree = formes[5]["id"]
        d["shapes"] = [s for s in formes if s["id"] != retiree]
        d["connections"] = [c for c in d.get("connections", [])
                            if c.get("from") != retiree and c.get("to") != retiree]
    return d


with app.app_context():
    from Code.models.models import CartoChangeRequest, Entity, User
    from Code.routes.cartography_editor import _sync_carto_to_db
    from Code.security import hash_password

    db.drop_all()
    db.create_all()

    payload = json.load(open(CARTO, encoding="utf-8"))
    diagram = payload.get("diagram") if payload.get("format") == "optiqcarto/entity" else payload

    coord = User(first_name="Camille", last_name="Fontaine", email="coord@test.local",
                 password=hash_password("Test1234!"), status="coordinateur", lang="fr")
    champion = User(first_name="Lou", last_name="Vasseur", email="champion@test.local",
                    password=hash_password("Test1234!"), status="champion", lang="fr")
    simple = User(first_name="Noe", last_name="Berthier", email="user@test.local",
                  password=hash_password("Test1234!"), status="user", lang="fr")
    admin = User(first_name="Mael", last_name="Girardin", email="admin@test.local",
                 password=hash_password("Test1234!"), status="administrateur", lang="fr")
    # DEUX développeurs de compétences : un collaborateur peut être suivi par
    # l'un sur un rôle et par l'autre sur un second — avec un seul candidat, ce
    # cas ne peut même pas se jouer au banc.
    dev2 = User(first_name="Sacha", last_name="Morel", email="dev2@test.local",
                password=hash_password("Test1234!"), status="user", lang="fr")
    db.session.add_all([coord, champion, simple, admin, dev2])
    db.session.commit()

    ent = Entity(name="Carto commune — RFQ FluidClip", description="carto de référence",
                 owner_id=coord.id, is_active=True, is_shared=True,
                 optiqcarto_data=json.dumps(diagram, ensure_ascii=False))
    db.session.add(ent)
    db.session.commit()
    _sync_carto_to_db(ent, diagram)

    # ── Une SECONDE carto, et un collaborateur à deux rôles ──────────────
    # ⚠️ Sans elles, la page RH ne montre jamais ce qu'on vient y régler :
    # « un rôle sur plusieurs cartos » demande plusieurs cartos, et « un
    # développeur par rôle » demande quelqu'un qui en tienne plus d'un.
    ent2 = Entity(name="Seconde carto (privée)", description="pour la page RH",
                  owner_id=coord.id, is_shared=False,
                  optiqcarto_data=json.dumps(diagram, ensure_ascii=False))
    db.session.add(ent2)
    db.session.commit()
    _sync_carto_to_db(ent2, diagram)

    from Code.models.models import Role, UserRole
    from Code.roles_permanents import assurer_roles_permanents
    assurer_roles_permanents(ent.id)
    db.session.commit()

    deux = Role.query.filter_by(entity_id=ent.id).order_by(Role.id).limit(2).all()
    for r in deux:
        if not UserRole.query.filter_by(user_id=simple.id, role_id=r.id).first():
            db.session.add(UserRole(user_id=simple.id, role_id=r.id))
    # Le champion devient développeur de compétences : la page a besoin d'au
    # moins un candidat à proposer, sinon le sélecteur est vide.
    dev_role = Role.query.filter_by(entity_id=ent.id).filter(
        Role.name.ilike("%ompétence%")).first()
    for qui in (champion, dev2):
        if dev_role and not UserRole.query.filter_by(
                user_id=qui.id, role_id=dev_role.id).first():
            db.session.add(UserRole(user_id=qui.id, role_id=dev_role.id))
    db.session.commit()

    propose = _modifier(diagram)
    cr = CartoChangeRequest(
        entity_id=ent.id, author_id=champion.id, status="pending",
        title="Réorganisation du bloc amont",
        message="J'ai renommé la première activité, déplacé deux formes et retiré un doublon.",
        diagram=json.dumps(propose, ensure_ascii=False),
        base_diagram=json.dumps(diagram, ensure_ascii=False))
    db.session.add(cr)
    db.session.commit()

    print(f"[devrun] base      : {db_path}")
    print(f"[devrun] carto     : {len(diagram.get('shapes', []))} formes, "
          f"{len(diagram.get('connections', []))} connexions — commune, ouverte à tous")
    print(f"[devrun] user      : user@test.local     / Test1234!  (consulte seulement)")
    print(f"[devrun] champion  : champion@test.local / Test1234!  (propose)")
    print(f"[devrun] coord     : coord@test.local    / Test1234!  (entité {ent.id})")
    print(f"[devrun] admin     : admin@test.local    / Test1234!")
    print(f"[devrun] dev2      : dev2@test.local     / Test1234!  (2e développeur)")
    print(f"[devrun] seconde carto : « {ent2.name} » (entité {ent2.id}, privée)")
    print(f"[devrun] {simple.email} tient {len(deux)} rôle(s) : "
          + ", ".join(r.name for r in deux))
    print(f"[devrun] proposition en attente : #{cr.id}")
    print(f"[devrun] http://127.0.0.1:{PORT}/login")

@app.route("/devrun/as/<email>")
def _devrun_as(email):
    """Bascule de compte en un clic, pour la mise au point.

    ⚠️ Cette route vit dans l'OUTIL, pas dans l'application : `tools/` est exclu
    de l'image, et rien de tout ceci n'existe sur une instance déployée. Elle
    évite de retaper un mot de passe à chaque changement de rôle pendant qu'on
    compare ce que voient un champion et un utilisateur ordinaire.
    """
    from flask import redirect, session
    from Code.models.models import User

    u = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if not u:
        return f"compte inconnu : {email}", 404
    session.clear()
    session["user_email"] = u.email
    session["user_id"] = u.id
    session["lang"] = u.lang or "fr"
    return redirect("/activities/map")


app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
