"""Instance jetable pour mettre au point la FENÊTRE DE BIENVENUE.

    python tools/devrun_bienvenue.py           → http://127.0.0.1:8127

Les QUATRE paliers, mot de passe `Test1234!` :
    user@test.local      user          — CONSULTE : ne modifie rien, ne propose rien
    champion@test.local  champion      — propose, ne valide pas
    coord@test.local     coordinateur  — règle l'accès, arbitre les propositions
    admin@test.local     administrateur

La fenêtre s'adapte au palier : il faut les quatre comptes côte à côte pour
voir ce qui s'ouvre et ce qui disparaît. Le journal d'activité récente est
garni (créations, modifications avec avant/après, suppression, association)
sinon le volet de droite ne montre que son état vide.

Bascule de compte sans retaper le mot de passe :
    /devrun/as/<email>              (reste en français)
    /devrun/as/<email>?lang=en      (et bascule le compte en anglais)
    /devrun/as/<email>?oublier=1    (rejoue une PREMIÈRE arrivée)

⚠️ `oublier` n'est pas un confort : depuis que « déjà vue » se mémorise sur le
COMPTE et non dans le navigateur, vider le stockage du navigateur ne rejoue
plus l'arrivée. Sans cette bascule, on n'éprouve la fenêtre qu'une seule fois
par compte et par base.

Outil de mise au point AFDEC : `tools/` est exclu de l'image (.dockerignore).
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CARTO = sys.argv[1] if len(sys.argv) > 1 else "tools/provisioning/carto/map_rfq_fluidclip.json"
PORT = int(os.environ.get("PORT", "8127"))

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

from Code.app import create_app                      # noqa: E402
from Code.extensions import db                       # noqa: E402

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
    "SECRET_KEY": "dev-bienvenue",
    "WTF_CSRF_ENABLED": False,
    "MAIL_SUPPRESS_SEND": True,
})

with app.app_context():
    from Code.models.models import Entity, RecentEvent, User
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
    db.session.add_all([coord, champion, simple, admin])
    db.session.commit()

    ent = Entity(name="Carto commune — RFQ FluidClip", description="carto de référence",
                 owner_id=coord.id, is_active=True, is_shared=True,
                 optiqcarto_data=json.dumps(diagram, ensure_ascii=False))
    db.session.add(ent)
    db.session.commit()
    _sync_carto_to_db(ent, diagram)

    # ── Deux propositions EN ATTENTE, déposées par le champion ───────────
    # Sans elles, le bloc « ce qui vous attend » ne se voit jamais — et c'est
    # le seul bloc de la fenêtre qui apparaît ou disparaît selon le palier ET
    # selon l'état de la base.
    from Code.models.models import CartoChangeRequest
    for titre, mot in (
            ("Réorganisation du bloc amont",
             "J'ai renommé la première activité et retiré un doublon."),
            ("Ajout d'un contrôle qualité",
             "Un contrôle manquait entre la réception et le chiffrage.")):
        db.session.add(CartoChangeRequest(
            entity_id=ent.id, author_id=champion.id, status="pending",
            title=titre, message=mot,
            diagram=json.dumps(diagram, ensure_ascii=False),
            base_diagram=json.dumps(diagram, ensure_ascii=False)))
    db.session.commit()

    # ── Une carto PROPOSÉE à l'administrateur ────────────────────────────
    # ⚠️ C'est ce qui permet d'éprouver la CHAÎNE : la notification de
    # transfert attend par MutationObserver que la bienvenue soit refermée.
    # Sans offre en attente, on ne voit jamais si l'enchaînement tient.
    from Code.models.models import EntityShareOffer
    db.session.add(EntityShareOffer(
        from_user_id=coord.id, to_user_id=admin.id, source_entity_id=ent.id,
        entity_name="Carto proposée — Atelier peinture",
        description="Le coordinateur vous propose sa cartographie.",
        status="pending",
        optiqcarto_data=json.dumps(diagram, ensure_ascii=False)))
    db.session.commit()

    # ── Le journal, garni des QUATRE familles d'événements ───────────────
    # Les couleurs et les sections déroulantes du volet droit dépendent du
    # suffixe du type (`created`/`updated`/`deleted`/`linked`) et de la forme
    # du détail : sans les quatre, trois rendus sur quatre ne se voient pas.
    maintenant = datetime.utcnow()
    journal = [
        ("activity_updated", "fa-solid fa-pen", "Activité modifiée : Chiffrage RFQ", 12,
         {"changes": [{"field": "description", "before": "Chiffrage à la demande",
                       "after": "Chiffrage sous 48 h, revue par le coordinateur"},
                      {"field": "mission", "before": "—", "after": "Tenir le délai de réponse"}]}),
        ("role_created", "fa-solid fa-user-plus", "Rôle créé : Qualité fournisseur", 40,
         {"name": "Qualité fournisseur",
          "description": "Suit les non-conformités des pièces reçues"}),
        ("tool_linked", "fa-solid fa-link", "Outil associé à une tâche", 150,
         {"tool": "ERP — module achats", "task": "Saisir la commande fournisseur"}),
        ("task_deleted", "fa-solid fa-trash", "Tâche supprimée : Relance manuelle", 1500,
         {"name": "Relance manuelle",
          "description": "Remplacée par la relance automatique de l'ERP"}),
    ]
    for i, (type_ev, icone, libelle, minutes, detail) in enumerate(journal):
        db.session.add(RecentEvent(
            event_type=type_ev, icon=icone, label=libelle,
            entity_id=ent.id, user_id=[coord, champion, simple, admin][i % 4].id,
            created_at=maintenant - timedelta(minutes=minutes),
            detail=json.dumps(detail, ensure_ascii=False)))
    db.session.commit()

    print(f"[devrun] base      : {db_path}")
    print(f"[devrun] journal   : {RecentEvent.query.count()} événements")
    print("[devrun] user      : user@test.local     / Test1234!  (consulte seulement)")
    print("[devrun] champion  : champion@test.local / Test1234!  (propose)")
    print("[devrun] coord     : coord@test.local    / Test1234!")
    print("[devrun] admin     : admin@test.local    / Test1234!")
    print(f"[devrun] bascule   : http://127.0.0.1:{PORT}/devrun/as/admin@test.local?lang=en")
    print(f"[devrun] http://127.0.0.1:{PORT}/login")


@app.route("/devrun/as/<email>")
def _devrun_as(email):
    """Bascule de compte en un clic, pour la mise au point.

    ⚠️ Cette route vit dans l'OUTIL, pas dans l'application : `tools/` est exclu
    de l'image, et rien de tout ceci n'existe sur une instance déployée. Elle
    évite de retaper un mot de passe à chaque changement de palier pendant
    qu'on compare ce que la fenêtre ouvre à un `user` et à un administrateur.
    """
    from flask import redirect, request, session
    from Code.models.models import User

    u = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if not u:
        return f"compte inconnu : {email}", 404
    langue = request.args.get("lang")
    if langue in ("fr", "en"):
        u.lang = langue
        db.session.commit()
    if request.args.get("oublier"):
        from Code.models.models import WelcomeSeen
        ligne = db.session.get(WelcomeSeen, u.id)
        if ligne is not None:
            db.session.delete(ligne)
            db.session.commit()
    session.clear()
    session["user_email"] = u.email
    session["user_id"] = u.id
    session["lang"] = u.lang or "fr"
    return redirect(request.args.get("next") or "/activities/map")


app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
