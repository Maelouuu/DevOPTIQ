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


def _remplir(entity_id, combien=None):
    """Pose garant + tache + outil sur les `combien` premieres activites.

    ⚠️ Sans cette aide, le banc ne montre QUE le cas malheureux : une carto
    toute vide, ou le panneau du socle dit « 0 sur 42 » et le bouton reste
    eteint. Ce qu'on vient regarder, c'est une saisie EN COURS — donc des
    activites completes a cote d'activites qui manquent de l'un des trois.
    """
    from Code.extensions import db as _db
    from Code.models.models import (Activities, Role, Task, Tool,
                                    activity_roles, task_tools)
    from Code.socle_activites import _perimetre, ETAT_SAISIE
    from Code.models.models import Entity as _E

    ent = _db.session.get(_E, entity_id)
    perim = _perimetre(ent)
    if combien is None:
        combien = len(perim)
    role = Role.query.filter_by(entity_id=entity_id).order_by(Role.id).first()
    outil = Tool(name="Gabarit de controle", entity_id=entity_id)
    _db.session.add(outil)
    _db.session.commit()

    def _garant(aid):
        """⚠️ `_sync_carto_to_db` a DEJA lie la bande de la carte a chaque
        activite : un INSERT buterait sur la contrainte d'unicite
        (activity_id, role_id). On met donc a jour le statut de la ligne qui
        existe, et on n'insere que s'il n'y en a aucune."""
        if role is None:
            return
        deja = _db.session.execute(
            activity_roles.select().where(
                activity_roles.c.activity_id == aid)).first()
        if deja is not None:
            _db.session.execute(activity_roles.update().where(
                activity_roles.c.activity_id == aid,
                activity_roles.c.role_id == deja.role_id
            ).values(status="Garant"))
            return
        _db.session.execute(activity_roles.insert().values(
            activity_id=aid, role_id=role.id, status="Garant"))

    for aid, nom in perim[:combien]:
        _garant(aid)
        t = Task(name="Preparer le dossier", activity_id=aid, order=1)
        _db.session.add(t)
        _db.session.flush()
        _db.session.execute(task_tools.insert().values(
            task_id=t.id, tool_id=outil.id))
    # ⚠️ Et quelques activites a MOITIE remplies : une tache sans outil, un
    # garant sans tache. Les trois exigences ne se voient qu'ainsi.
    for aid, nom in perim[combien:combien + 2]:
        t = Task(name="Esquisse", activity_id=aid, order=1)
        _db.session.add(t)
    for aid, nom in perim[combien + 2:combien + 4]:
        _garant(aid)
    # ⚠️ Et quelques activites SANS garant. L'import carto en pose un a chaque
    # activite (la bande de la carte) : sans ce retrait, la troisieme exigence
    # du palier est toujours satisfaite au banc et on ne la voit JAMAIS a
    # l'ecran. Mesure avant : « il manque 26 taches · 28 outils », zero garant.
    for aid, nom in perim[combien + 4:combien + 9]:
        _db.session.execute(activity_roles.update().where(
            activity_roles.c.activity_id == aid).values(status="Acteur"))
    _db.session.commit()


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
    # Et un rôle sur la carto PRIVÉE du coordinateur, que l'administrateur
    # n'ouvre pas : c'est le rôle que l'ancienne fiche de compte effaçait dès
    # qu'on y corrigeait un nom.
    ailleurs = Role.query.filter_by(entity_id=ent2.id).order_by(Role.id).first()
    if ailleurs and not UserRole.query.filter_by(user_id=simple.id, role_id=ailleurs.id).first():
        db.session.add(UserRole(user_id=simple.id, role_id=ailleurs.id))
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

    # Une TROISIÈME carto, commune, avec sa propre proposition : le bandeau de
    # la page Carte réunit les propositions de TOUTES les cartos — avec une
    # seule, on ne voit jamais qu'il le fait. Et la carto a bougé APRÈS le
    # dépôt : c'est le cas où l'appliquer effacerait une retouche, que la
    # fenêtre d'examen doit annoncer.
    ent3 = Entity(name="Troisième carto (commune)", description="pour le bandeau",
                  owner_id=coord.id, is_shared=True,
                  optiqcarto_data=json.dumps(diagram, ensure_ascii=False))
    db.session.add(ent3)
    db.session.commit()
    _sync_carto_to_db(ent3, diagram)
    cr3 = CartoChangeRequest(
        entity_id=ent3.id, author_id=champion.id, status="pending",
        title="Ajout d'un contrôle qualité",
        message="Un contrôle manquait entre la réception et le chiffrage.",
        diagram=json.dumps(_modifier(diagram), ensure_ascii=False),
        base_diagram=json.dumps(diagram, ensure_ascii=False))
    db.session.add(cr3)
    retouche = copy.deepcopy(diagram)
    for s in retouche.get("shapes", [])[-2:]:
        s["x"] = int(s.get("x", 0)) - 180
    ent3.optiqcarto_data = json.dumps(retouche, ensure_ascii=False)
    db.session.commit()

    # ══ LE SOCLE : les trois etats, en meme temps ══════════════════
    # ⚠️ Les trois a la fois, et c'est le point : avec un seul etat on ne voit
    # jamais ce que l'ecran doit savoir montrer. `ent` est en SAISIE (le cas
    # du champion), une quatrieme carto est SOUMISE (le cas du coordinateur),
    # et `ent3` est VALIDEE — c'est elle qui garde le regime « une
    # modification, une demande », donc le bandeau des propositions.
    from Code.socle_activites import ETAT_SAISIE, ETAT_SOUMIS, ETAT_VALIDE
    from datetime import datetime as _dt

    assurer_roles_permanents(ent.id)
    db.session.commit()
    _remplir(ent.id, 8)
    ent.socle_etat = ETAT_SAISIE

    ent3.socle_etat = ETAT_VALIDE
    ent2.socle_etat = ETAT_VALIDE

    ent4 = Entity(name="Quatrieme carto (socle soumis)",
                  description="pour la validation du coordinateur",
                  owner_id=coord.id, is_shared=True,
                  optiqcarto_data=json.dumps(diagram, ensure_ascii=False))
    db.session.add(ent4)
    db.session.commit()
    _sync_carto_to_db(ent4, diagram)
    assurer_roles_permanents(ent4.id)
    db.session.commit()
    _remplir(ent4.id)                      # complete : le palier est franchi
    ent4.socle_etat = ETAT_SOUMIS
    ent4.socle_par_id = champion.id
    ent4.socle_le = _dt.utcnow()
    ent4.socle_message = ("J'ai repris les trois activites amont avec Camille, "
                          "et outille chaque tache.")
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
    print(f"[devrun] propositions en attente : #{cr.id}, #{cr3.id} (carto retouchée depuis)")
    print(f"[devrun] socle      : #{ent.id} saisie (8 completes) | "
          f"#{ent4.id} soumis | #{ent3.id} valide")
    print(f"[devrun] bascule    : /devrun/socle/<saisie|soumis|valide>")
    print(f"[devrun] carto      : /devrun/carto/<id>")
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


@app.route("/devrun/socle/<etat>")
def _devrun_socle(etat):
    """Bascule le socle de la carto ACTIVE, pour rejouer les trois etats."""
    from flask import redirect
    from Code.models.models import Entity
    from Code.socle_activites import ETATS

    if etat not in ETATS:
        return "etat inconnu : %s (attendus : %s)" % (etat, ", ".join(ETATS)), 400
    ent = Entity.get_active()
    if ent is None:
        return "aucune carto active", 404
    ent.socle_etat = etat
    db.session.commit()
    return redirect("/activities/view")


@app.route("/devrun/carto/<int:entity_id>")
def _devrun_carto(entity_id):
    """Rend une carto active en un clic."""
    from flask import redirect, session
    session["active_entity_id"] = entity_id
    return redirect("/activities/view")


app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
