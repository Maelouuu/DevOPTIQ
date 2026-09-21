# tests/test_88_decision_a_l_auteur.py
"""
Le mot du valideur parvient à l'auteur d'une proposition — qu'elle soit
appliquée OU refusée.

⚠️ Le défaut : la fenêtre d'examen offrait un champ « un mot pour l'auteur »,
le serveur l'enregistrait (`review_comment`)… et AUCUN écran ne le montrait à
son destinataire. Ni la page Partage, ni l'éditeur, ni la moindre
notification. Désormais :
  - `GET /cartography/api/changes/decisions` rend les décisions prises sur mes
    propositions que je n'ai pas encore lues ;
  - une fenêtre les annonce sur n'importe quelle page, jusqu'à « Compris »
    (`POST …/decisions/vues`).
"""
import json

import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.carto_sharing

DIAG = {"shapes": [{"id": "a", "type": "process", "label": "T88", "x": 0, "y": 0, "w": 100, "h": 50}],
        "bands": [], "connections": []}


@pytest.fixture(scope="module", autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email="test@devoptiq.com").first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = umail
        sess["active_entity_id"] = ids["entity_id"]
        sess["lang"] = "fr"


def _mk_user(email, status):
    from Code.extensions import db
    from Code.models.models import User
    u = User.query.filter_by(email=email).first()
    if u is None:
        u = User(first_name="T88", last_name=email.split("@")[0], email=email,
                 password=generate_password_hash("Test1234!"), status=status)
        db.session.add(u)
    u.status = status
    db.session.commit()
    return u.id


def _as(client, uid, email):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = email
        sess["lang"] = "fr"


@pytest.fixture(scope="module")
def monde(app):
    from Code.extensions import db
    from Code.models.models import CartoChangeRequest, Entity

    with app.app_context():
        coord = _mk_user("t88.coord@devoptiq.com", "coordinateur")
        auteur = _mk_user("t88.auteur@devoptiq.com", "champion")
        tiers = _mk_user("t88.tiers@devoptiq.com", "champion")
        e = Entity(name="T88 Carto commune", owner_id=coord, is_shared=True,
                   optiqcarto_data=json.dumps(DIAG))
        db.session.add(e)
        db.session.commit()

        def prop(titre, qui=auteur):
            cr = CartoChangeRequest(entity_id=e.id, author_id=qui, status="pending",
                                    title=titre, diagram=json.dumps(DIAG),
                                    base_diagram=json.dumps(DIAG))
            db.session.add(cr)
            db.session.commit()
            return cr.id

        m = {"coord": coord, "auteur": auteur, "tiers": tiers, "entite": e.id,
             "p_refus": prop("T88 à refuser"), "p_ok": prop("T88 à appliquer"),
             "p_coord": prop("T88 du coordinateur", qui=coord)}
    yield m
    with app.app_context():
        from Code.models.models import Activities, Link, Role
        CartoChangeRequest.query.filter_by(entity_id=m["entite"]).delete()
        # Appliquer une proposition dérive la carto en base (_sync_carto_to_db).
        for modele in (Link, Activities, Role):
            modele.query.filter_by(entity_id=m["entite"]).delete()
        ent = db.session.get(Entity, m["entite"])
        if ent:
            ent.is_shared = False
            db.session.delete(ent)
        db.session.commit()


def _decisions(client):
    return {d["id"]: d for d in client.get("/cartography/api/changes/decisions").get_json()["decisions"]}


class TestLeMotArriveALAuteur:

    def test_refusee_avec_son_explication(self, client, monde):
        _as(client, monde["coord"], "t88.coord@devoptiq.com")
        rep = client.post(f"/cartography/api/changes/{monde['p_refus']}/reject",
                          json={"comment": "  Le contrôle existe déjà dans la carto Qualité.  "})
        assert rep.status_code == 200
        _as(client, monde["auteur"], "t88.auteur@devoptiq.com")
        d = _decisions(client)[monde["p_refus"]]
        assert d["status"] == "rejected"
        assert d["review_comment"] == "Le contrôle existe déjà dans la carto Qualité."
        assert d["reviewer"] and d["entity_name"] == "T88 Carto commune"

    def test_appliquee_aussi(self, client, monde):
        _as(client, monde["coord"], "t88.coord@devoptiq.com")
        client.post(f"/cartography/api/changes/{monde['p_ok']}/approve",
                    json={"comment": "Merci, c'est appliqué."})
        _as(client, monde["auteur"], "t88.auteur@devoptiq.com")
        d = _decisions(client)[monde["p_ok"]]
        assert d["status"] == "approved" and d["review_comment"] == "Merci, c'est appliqué."

    def test_personne_d_autre_ne_les_voit(self, client, monde):
        _as(client, monde["tiers"], "t88.tiers@devoptiq.com")
        vus = _decisions(client)
        assert monde["p_refus"] not in vus and monde["p_ok"] not in vus

    def test_on_ne_s_annonce_pas_sa_propre_decision(self, client, monde):
        _as(client, monde["coord"], "t88.coord@devoptiq.com")
        client.post(f"/cartography/api/changes/{monde['p_coord']}/reject", json={"comment": "x"})
        assert monde["p_coord"] not in _decisions(client)

    def test_le_detail_porte_le_mot(self, client, monde):
        """La page Partage et l'éditeur relisent la proposition par cette route."""
        _as(client, monde["auteur"], "t88.auteur@devoptiq.com")
        d = client.get(f"/cartography/api/changes/{monde['p_refus']}").get_json()
        assert d["review_comment"] == "Le contrôle existe déjà dans la carto Qualité."


class TestCompris:

    def test_un_tiers_ne_marque_rien(self, client, monde):
        _as(client, monde["tiers"], "t88.tiers@devoptiq.com")
        rep = client.post("/cartography/api/changes/decisions/vues",
                          json={"ids": [monde["p_refus"], monde["p_ok"]]})
        assert rep.get_json()["n"] == 0
        _as(client, monde["auteur"], "t88.auteur@devoptiq.com")
        assert {monde["p_refus"], monde["p_ok"]} <= set(_decisions(client))

    def test_l_auteur_ne_les_revoit_plus(self, client, monde):
        _as(client, monde["auteur"], "t88.auteur@devoptiq.com")
        rep = client.post("/cartography/api/changes/decisions/vues",
                          json={"ids": [monde["p_refus"], monde["p_ok"], "pas-un-nombre"]})
        assert rep.get_json()["n"] == 2
        vus = _decisions(client)
        assert monde["p_refus"] not in vus and monde["p_ok"] not in vus

    def test_la_fenetre_est_sur_toutes_les_pages(self, client, monde):
        _as(client, monde["auteur"], "t88.auteur@devoptiq.com")
        html = client.get("/comptes/").get_data(as_text=True)
        assert 'id="cdp-overlay"' in html
