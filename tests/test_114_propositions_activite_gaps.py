# -*- coding: utf-8 -*-
"""Les routes `/api/propositions/*` — accès, 404, 409 et lecture.

Complète `test_112_propositions_activite` : ici les refus (non connecté,
introuvable, déjà traitée), la lecture d'une proposition et le vidage du
brouillon. Chaque cas monte SON décor — la base et la session sont partagées.
"""
import json

import pytest

from Code.extensions import db

_N = [0]


@pytest.fixture
def decor(app):
    from Code.models.models import Activities, Entity, User
    from Code.security import hash_password

    _N[0] += 1
    n = _N[0]
    with app.app_context():
        faire = lambda r, s: User(
            first_name=r.capitalize(), last_name="G%d" % n,
            email="%s%d@acpg.test" % (r, n), password=hash_password("x"), status=s)
        coord, champ, autre = faire("coord", "coordinateur"), faire("champ", "champion"), faire("autre", "champion")
        db.session.add_all([coord, champ, autre])
        db.session.commit()
        ent = Entity(name="ACPG carto %d" % n, owner_id=coord.id, is_shared=True)
        db.session.add(ent)
        db.session.commit()
        act = Activities(name="ACPG activité %d" % n, entity_id=ent.id)
        db.session.add(act)
        db.session.commit()
        d = {"coord": coord.id, "champ": champ.id, "autre": autre.id,
             "ent": ent.id, "act": act.id}
    yield d
    with app.app_context():
        from Code.models.models import (ActivityChangeRequest, Competency,
                                        Task, Tool)
        ActivityChangeRequest.query.filter_by(entity_id=d["ent"]).delete()
        Task.query.filter_by(activity_id=d["act"]).delete()
        Competency.query.filter_by(activity_id=d["act"]).delete()
        Tool.query.filter_by(entity_id=d["ent"]).delete()
        db.session.query(Activities).filter_by(id=d["act"]).delete()
        db.session.query(Entity).filter_by(id=d["ent"]).delete()
        User.query.filter(User.id.in_(
            [d["coord"], d["champ"], d["autre"]])).delete(synchronize_session=False)
        db.session.commit()


def _comme(app, uid, entity_id):
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["active_entity_id"] = entity_id
    return c


def _anonyme(app):
    return app.test_client()


def _proposer(app, decor, noms=("Peser",)):
    c = _comme(app, decor["champ"], decor["ent"])
    for nom in noms:
        assert c.post("/tasks/add", json={"activity_id": decor["act"], "name": nom}).status_code == 202


def _envoyer(app, decor, noms=("Peser",)):
    _proposer(app, decor, noms)
    c = _comme(app, decor["champ"], decor["ent"])
    assert c.post("/api/propositions/envoyer", json={"message": "m"}).status_code == 201
    from Code.models.models import ActivityChangeRequest
    with app.app_context():
        return ActivityChangeRequest.query.filter_by(
            entity_id=decor["ent"], status="pending").first().id


class TestSansConnexion:

    @pytest.mark.parametrize("methode,url", [
        ("get", "/api/propositions/brouillon"),
        ("delete", "/api/propositions/brouillon"),
        ("delete", "/api/propositions/brouillon/0"),
        ("post", "/api/propositions/envoyer"),
        ("get", "/api/propositions/a_examiner"),
        ("get", "/api/propositions/miennes"),
        ("get", "/api/propositions/1"),
        ("post", "/api/propositions/1/approve"),
        ("post", "/api/propositions/1/reject"),
        ("delete", "/api/propositions/1"),
        ("get", "/api/propositions/decisions"),
        ("post", "/api/propositions/decisions/vues"),
    ])
    def test_refuse_401_sans_session(self, app, methode, url):
        r = getattr(_anonyme(app), methode)(url)
        assert r.status_code == 401
        assert r.get_json()["error"] == "Non connecté"


class TestBrouillon:

    def test_brouillon_absent_rend_none_et_zero(self, app, decor):
        r = _comme(app, decor["champ"], decor["ent"]).get("/api/propositions/brouillon")
        assert r.status_code == 200
        assert r.get_json() == {"brouillon": None, "n": 0}

    def test_brouillon_porte_ses_gestes_sans_le_corps(self, app, decor):
        _proposer(app, decor, ("A", "B"))
        j = _comme(app, decor["champ"], decor["ent"]).get("/api/propositions/brouillon").get_json()
        assert j["n"] == 2
        b = j["brouillon"]
        assert b["status"] == "draft" and b["is_mine"] is True
        assert len(b["gestes"]) == 2
        assert set(b["gestes"][0]) == {"op", "objet", "activite", "activity_id"}

    def test_retirer_un_geste_hors_borne_rend_404(self, app, decor):
        _proposer(app, decor)
        c = _comme(app, decor["champ"], decor["ent"])
        assert c.delete("/api/propositions/brouillon/5").status_code == 404

    def test_retirer_un_geste_sans_brouillon_rend_404(self, app, decor):
        r = _comme(app, decor["champ"], decor["ent"]).delete("/api/propositions/brouillon/0")
        assert r.status_code == 404
        assert r.get_json()["error"] == "Geste introuvable"

    def test_retirer_un_geste_garde_les_autres(self, app, decor):
        _proposer(app, decor, ("A", "B"))
        c = _comme(app, decor["champ"], decor["ent"])
        assert c.delete("/api/propositions/brouillon/0").status_code == 200
        assert c.get("/api/propositions/brouillon").get_json()["n"] == 1

    def test_vider_le_brouillon_le_supprime(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        _proposer(app, decor, ("A", "B"))
        c = _comme(app, decor["champ"], decor["ent"])
        assert c.delete("/api/propositions/brouillon").status_code == 200
        with app.app_context():
            assert ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"], status="draft").count() == 0
        assert c.get("/api/propositions/brouillon").get_json()["n"] == 0

    def test_vider_sans_brouillon_reste_ok(self, app, decor):
        r = _comme(app, decor["champ"], decor["ent"]).delete("/api/propositions/brouillon")
        assert r.status_code == 200 and r.get_json() == {"ok": True}

    def test_le_brouillon_d_un_autre_compte_n_est_pas_vu(self, app, decor):
        _proposer(app, decor)
        j = _comme(app, decor["autre"], decor["ent"]).get("/api/propositions/brouillon").get_json()
        assert j["brouillon"] is None


class TestEnvoyer:

    def test_envoyer_sans_message_laisse_le_message_vide(self, app, decor):
        _proposer(app, decor)
        c = _comme(app, decor["champ"], decor["ent"])
        r = c.post("/api/propositions/envoyer", json={"message": "   "})
        assert r.status_code == 201
        p = r.get_json()["proposition"]
        assert p["status"] == "pending" and p["message"] == "" and p["submitted_at"]

    def test_envoyer_sans_corps_json_fonctionne(self, app, decor):
        _proposer(app, decor)
        r = _comme(app, decor["champ"], decor["ent"]).post("/api/propositions/envoyer")
        assert r.status_code == 201

    def test_envoyer_sans_rien_rend_code_vide(self, app, decor):
        r = _comme(app, decor["champ"], decor["ent"]).post("/api/propositions/envoyer", json={})
        assert r.status_code == 400 and r.get_json()["code"] == "vide"

    def test_envoyer_un_brouillon_aux_actions_vides_est_refuse(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        with app.app_context():
            db.session.add(ActivityChangeRequest(
                entity_id=decor["ent"], author_id=decor["champ"], status="draft", actions="[]"))
            db.session.commit()
        r = _comme(app, decor["champ"], decor["ent"]).post("/api/propositions/envoyer", json={})
        assert r.status_code == 400 and r.get_json()["code"] == "vide"

    def test_envoyer_renseigne_le_nom_de_la_carto(self, app, decor):
        _proposer(app, decor)
        r = _comme(app, decor["champ"], decor["ent"]).post("/api/propositions/envoyer", json={})
        assert r.get_json()["proposition"]["entity_name"].startswith("ACPG carto")


class TestLecture:

    def test_get_proposition_pour_son_auteur(self, app, decor):
        rid = _envoyer(app, decor)
        j = _comme(app, decor["champ"], decor["ent"]).get("/api/propositions/%d" % rid).get_json()
        assert j["id"] == rid and j["is_mine"] is True and j["can_review"] is False
        assert len(j["gestes"]) == 1 and j["message"] == "m"

    def test_get_proposition_pour_le_coordinateur_peut_trancher(self, app, decor):
        rid = _envoyer(app, decor)
        j = _comme(app, decor["coord"], decor["ent"]).get("/api/propositions/%d" % rid).get_json()
        assert j["can_review"] is True and j["is_mine"] is False

    def test_get_proposition_inconnue_rend_404(self, app, decor):
        r = _comme(app, decor["coord"], decor["ent"]).get("/api/propositions/99999999")
        assert r.status_code == 404

    def test_get_proposition_invisible_pour_un_tiers(self, app, decor):
        rid = _envoyer(app, decor)
        r = _comme(app, decor["autre"], decor["ent"]).get("/api/propositions/%d" % rid)
        assert r.status_code == 404

    def test_get_un_brouillon_par_id_rend_404(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        _proposer(app, decor)
        with app.app_context():
            did = ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"], status="draft").first().id
        assert _comme(app, decor["champ"], decor["ent"]).get(
            "/api/propositions/%d" % did).status_code == 404
        assert _comme(app, decor["coord"], decor["ent"]).get(
            "/api/propositions/%d" % did).status_code == 404

    def test_get_proposition_traitee_n_est_plus_a_trancher(self, app, decor):
        rid = _envoyer(app, decor)
        coord = _comme(app, decor["coord"], decor["ent"])
        coord.post("/api/propositions/%d/reject" % rid, json={})
        assert coord.get("/api/propositions/%d" % rid).get_json()["can_review"] is False

    def test_miennes_exclut_les_brouillons(self, app, decor):
        rid = _envoyer(app, decor)
        _proposer(app, decor, ("Autre",))
        c = _comme(app, decor["champ"], decor["ent"])
        ids = [r["id"] for r in c.get("/api/propositions/miennes").get_json()["requests"]]
        assert ids == [rid]

    def test_miennes_ne_montre_pas_celles_des_autres(self, app, decor):
        _envoyer(app, decor)
        j = _comme(app, decor["autre"], decor["ent"]).get("/api/propositions/miennes").get_json()
        assert j["requests"] == []

    def test_a_examiner_liste_la_proposition_au_coordinateur(self, app, decor):
        rid = _envoyer(app, decor)
        j = _comme(app, decor["coord"], decor["ent"]).get("/api/propositions/a_examiner").get_json()
        assert rid in [r["id"] for r in j["requests"]]
        assert j["n"] == len(j["requests"]) and j["cartos"] >= 1

    def test_a_examiner_vide_pour_l_auteur_champion(self, app, decor):
        _envoyer(app, decor)
        j = _comme(app, decor["champ"], decor["ent"]).get("/api/propositions/a_examiner").get_json()
        assert j == {"requests": [], "n": 0, "cartos": 0}


class TestDecision:

    def test_approuver_inconnue_rend_404(self, app, decor):
        r = _comme(app, decor["coord"], decor["ent"]).post("/api/propositions/99999999/approve", json={})
        assert r.status_code == 404

    def test_refuser_inconnue_rend_404(self, app, decor):
        r = _comme(app, decor["coord"], decor["ent"]).post("/api/propositions/99999999/reject", json={})
        assert r.status_code == 404

    def test_approuver_un_brouillon_rend_404(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        _proposer(app, decor)
        with app.app_context():
            did = ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"], status="draft").first().id
        coord = _comme(app, decor["coord"], decor["ent"])
        assert coord.post("/api/propositions/%d/approve" % did, json={}).status_code == 404
        assert coord.post("/api/propositions/%d/reject" % did, json={}).status_code == 404

    def test_refuser_enregistre_commentaire_et_valideur(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        rid = _envoyer(app, decor)
        r = _comme(app, decor["coord"], decor["ent"]).post(
            "/api/propositions/%d/reject" % rid, json={"comment": "  non  "})
        assert r.status_code == 200
        with app.app_context():
            cr = db.session.get(ActivityChangeRequest, rid)
            assert cr.status == "rejected" and cr.review_comment == "non"
            assert cr.reviewer_id == decor["coord"] and cr.reviewed_at is not None
            assert cr.author_seen_at is None

    def test_refuser_sans_commentaire_laisse_none(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        rid = _envoyer(app, decor)
        _comme(app, decor["coord"], decor["ent"]).post("/api/propositions/%d/reject" % rid)
        with app.app_context():
            assert db.session.get(ActivityChangeRequest, rid).review_comment is None

    def test_refuser_deux_fois_rend_409(self, app, decor):
        rid = _envoyer(app, decor)
        coord = _comme(app, decor["coord"], decor["ent"])
        assert coord.post("/api/propositions/%d/reject" % rid, json={}).status_code == 200
        r = coord.post("/api/propositions/%d/reject" % rid, json={})
        assert r.status_code == 409 and r.get_json()["error"] == "Proposition déjà traitée"

    def test_approuver_une_refusee_rend_409(self, app, decor):
        rid = _envoyer(app, decor)
        coord = _comme(app, decor["coord"], decor["ent"])
        coord.post("/api/propositions/%d/reject" % rid, json={})
        assert coord.post("/api/propositions/%d/approve" % rid, json={}).status_code == 409

    def test_refus_interdit_a_un_champion_avec_code_forbidden(self, app, decor):
        rid = _envoyer(app, decor)
        r = _comme(app, decor["autre"], decor["ent"]).post("/api/propositions/%d/reject" % rid, json={})
        assert r.status_code == 403 and r.get_json()["code"] == "forbidden"

    def test_approuver_depuis_une_autre_carto_restaure_la_session(self, app, decor):
        from Code.models.models import Entity, Task
        rid = _envoyer(app, decor)
        with app.app_context():
            autre = Entity(name="ACPG autre %d" % decor["ent"], owner_id=decor["coord"])
            db.session.add(autre)
            db.session.commit()
            autre_id = autre.id
        try:
            coord = _comme(app, decor["coord"], autre_id)
            r = coord.post("/api/propositions/%d/approve" % rid, json={})
            assert r.status_code == 200 and r.get_json()["entity_id"] == decor["ent"]
            with coord.session_transaction() as s:
                assert s["active_entity_id"] == autre_id
            with app.app_context():
                assert Task.query.filter_by(activity_id=decor["act"]).count() == 1
        finally:
            with app.app_context():
                db.session.query(Entity).filter_by(id=autre_id).delete()
                db.session.commit()

    def test_approuver_marque_lu_si_le_valideur_est_l_auteur(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        with app.app_context():
            cr = ActivityChangeRequest(
                entity_id=decor["ent"], author_id=decor["coord"], status="pending",
                actions=json.dumps([]))
            db.session.add(cr)
            db.session.commit()
            rid = cr.id
        r = _comme(app, decor["coord"], decor["ent"]).post(
            "/api/propositions/%d/reject" % rid, json={})
        assert r.status_code == 200
        with app.app_context():
            assert db.session.get(ActivityChangeRequest, rid).author_seen_at is not None


class TestRetraitEtDecisions:

    def test_retirer_inconnue_rend_404(self, app, decor):
        r = _comme(app, decor["champ"], decor["ent"]).delete("/api/propositions/99999999")
        assert r.status_code == 404

    def test_retirer_une_traitee_rend_409(self, app, decor):
        rid = _envoyer(app, decor)
        _comme(app, decor["coord"], decor["ent"]).post("/api/propositions/%d/reject" % rid, json={})
        r = _comme(app, decor["champ"], decor["ent"]).delete("/api/propositions/%d" % rid)
        assert r.status_code == 409

    def test_retirer_son_brouillon_par_id_fonctionne(self, app, decor):
        from Code.models.models import ActivityChangeRequest
        _proposer(app, decor)
        with app.app_context():
            did = ActivityChangeRequest.query.filter_by(
                entity_id=decor["ent"], status="draft").first().id
        r = _comme(app, decor["champ"], decor["ent"]).delete("/api/propositions/%d" % did)
        assert r.status_code == 200
        with app.app_context():
            assert db.session.get(ActivityChangeRequest, did) is None

    def test_decisions_vide_tant_que_rien_n_est_tranche(self, app, decor):
        _envoyer(app, decor)
        j = _comme(app, decor["champ"], decor["ent"]).get("/api/propositions/decisions").get_json()
        assert j["decisions"] == []

    def test_decisions_vues_ids_invalides_ignores(self, app, decor):
        c = _comme(app, decor["champ"], decor["ent"])
        r = c.post("/api/propositions/decisions/vues", json={"ids": ["abc", "-1", None, ""]})
        assert r.status_code == 200 and r.get_json() == {"ok": True, "n": 0}

    def test_decisions_vues_sans_corps_rend_zero(self, app, decor):
        r = _comme(app, decor["champ"], decor["ent"]).post("/api/propositions/decisions/vues")
        assert r.get_json()["n"] == 0

    def test_decisions_vues_accepte_des_ids_en_chaine(self, app, decor):
        rid = _envoyer(app, decor)
        _comme(app, decor["coord"], decor["ent"]).post("/api/propositions/%d/reject" % rid, json={})
        c = _comme(app, decor["champ"], decor["ent"])
        assert c.post("/api/propositions/decisions/vues",
                      json={"ids": [str(rid)]}).get_json()["n"] == 1
