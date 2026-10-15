# -*- coding: utf-8 -*-
"""Paliers : la NORME et les chemins d'erreur des routes /paliers.

Chaque cas fabrique ses propres données (compteur) et les retire ensuite :
la base et la session sont communes à toute la suite.
"""
import json
from datetime import date, timedelta

import pytest

from Code.extensions import db

_N = [0]


@pytest.fixture
def cadre(app, ids):
    """Un développeur, Bob (son collaborateur), un rôle, une activité et une
    sortie SANS norme."""
    from Code.models.models import (Activities, Link, Role, User, UserRole,
                                    activity_roles)
    from Code.security import hash_password
    _N[0] += 1
    n = _N[0]
    with app.app_context():
        dev = User(first_name="Dev", last_name="T110", email="dev.t110.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        bob = User(first_name="Bob", last_name="T110", email="bob.t110.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        tiers = User(first_name="Tiers", last_name="T110", email="tiers.t110.%d@test" % n,
                     password=hash_password("Test1234!"), status="user")
        db.session.add_all([dev, bob, tiers])
        db.session.commit()
        role = Role(name="T110 Rôle %d" % n, entity_id=ids["entity_id"])
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=bob.id, role_id=role.id, manager_id=dev.id))
        act = Activities(name="T110 Act %d" % n, entity_id=ids["entity_id"])
        aval = Activities(name="T110 Aval %d" % n, entity_id=ids["entity_id"])
        db.session.add_all([act, aval])
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant",
            required_mastery_level=2))
        db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=act.id,
                            target_activity_id=aval.id,
                            description="Doc T110 %d" % n, type="flux"))
        db.session.commit()
        from Code.routes.qualify_outputs import get_activity_outputs
        sortie = get_activity_outputs(act.id)[0]
        info = {"dev_id": dev.id, "bob_id": bob.id, "tiers_id": tiers.id,
                "role_id": role.id, "activity_id": act.id, "data_id": sortie.id}
    yield info
    with app.app_context():
        from Code.models.models import Data, PalierPerformance, SessionEvaluation
        for m in (PalierPerformance, SessionEvaluation):
            for x in m.query.filter_by(user_id=info["bob_id"]).all():
                db.session.delete(x)
        d = db.session.get(Data, info["data_id"])
        if d is not None:
            d.norme_valeur = d.norme_unite = d.norme_sens = None
        db.session.commit()


def _comme(client, uid):
    with client.session_transaction() as sess:
        sess["user_id"] = uid


@pytest.fixture
def comme_dev(auth_client, cadre):
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")
        sess["user_id"] = cadre["dev_id"]
    yield
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


@pytest.fixture
def comme_tiers(auth_client, cadre):
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")
        sess["user_id"] = cadre["tiers_id"]
    yield
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


def _norme(client, cadre, **corps):
    return client.post("/paliers/norme/%d" % cadre["data_id"], json=corps)


def _donnee(app, cadre):
    from Code.models.models import Data
    with app.app_context():
        d = db.session.get(Data, cadre["data_id"])
        return d.norme_valeur, d.norme_unite, d.norme_sens


class TestPoserNorme:
    def test_sans_connexion_401(self, client, cadre):
        r = client.post("/paliers/norme/%d" % cadre["data_id"], json={"valeur": 5})
        assert r.status_code == 401
        assert r.get_json()["error"] == "not_logged_in"

    def test_sortie_inconnue_404(self, auth_client):
        r = auth_client.post("/paliers/norme/99999999", json={"valeur": 5})
        assert r.status_code == 404
        assert r.get_json()["error"] == "unknown_output"

    def test_un_tiers_sans_equipe_est_refuse_403(self, auth_client, cadre, comme_tiers):
        r = _norme(auth_client, cadre, valeur=5)
        assert r.status_code == 403

    def test_poser_une_norme_la_rend_mesurable(self, app, auth_client, cadre, comme_dev):
        r = _norme(auth_client, cadre, valeur="48", unite="h", sens="moins")
        assert r.status_code == 200
        j = r.get_json()
        assert j["mesurable"] is True
        assert j["norme"] == {"valeur": 48.0, "unite": "h", "sens": "moins"}
        assert _donnee(app, cadre) == (48.0, "h", "moins")

    def test_sens_par_defaut_moins_et_majuscules_acceptees(self, auth_client, cadre, comme_dev):
        assert _norme(auth_client, cadre, valeur=3).get_json()["norme"]["sens"] == "moins"
        r = _norme(auth_client, cadre, valeur=3, sens="  PLUS ")
        assert r.get_json()["norme"]["sens"] == "plus"

    def test_unite_tronquee_a_20_caracteres(self, auth_client, cadre, comme_dev):
        r = _norme(auth_client, cadre, valeur=1, unite="x" * 40)
        assert r.get_json()["norme"]["unite"] == "x" * 20

    def test_unite_vide_devient_chaine_vide(self, auth_client, cadre, comme_dev):
        r = _norme(auth_client, cadre, valeur=1, unite="   ")
        assert r.get_json()["norme"]["unite"] == ""

    def test_valeur_non_numerique_400(self, app, auth_client, cadre, comme_dev):
        r = _norme(auth_client, cadre, valeur="abc")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_value"
        assert _donnee(app, cadre)[0] is None

    def test_sens_inconnu_400_et_rien_n_est_ecrit(self, app, auth_client, cadre, comme_dev):
        r = _norme(auth_client, cadre, valeur=5, sens="lateral")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_direction"
        assert _donnee(app, cadre) == (None, None, None)

    @pytest.mark.parametrize("vide", [None, ""])
    def test_valeur_vide_efface_la_norme(self, app, auth_client, cadre, comme_dev, vide):
        _norme(auth_client, cadre, valeur=10, unite="j", sens="plus")
        r = _norme(auth_client, cadre, valeur=vide)
        assert r.status_code == 200
        assert r.get_json() == {"ok": True, "mesurable": False}
        assert _donnee(app, cadre) == (None, None, None)


class TestLecturesEtDroits:
    def test_etat_activite_sortie_non_mesurable(self, auth_client, cadre, comme_dev):
        r = auth_client.get("/paliers/activite/%d/%d?role_id=%d" % (
            cadre["bob_id"], cadre["activity_id"], cadre["role_id"]))
        assert r.status_code == 200
        s = [x for x in r.get_json()["sorties"] if x["data_id"] == cadre["data_id"]][0]
        assert s["mesurable"] is False and s["paliers"] == [] and s["norme"] is None

    def test_etat_activite_sortie_mesurable_porte_une_proposition(
            self, auth_client, cadre, comme_dev):
        _norme(auth_client, cadre, valeur=48, unite="h", sens="moins")
        r = auth_client.get("/paliers/activite/%d/%d?role_id=%d" % (
            cadre["bob_id"], cadre["activity_id"], cadre["role_id"]))
        s = [x for x in r.get_json()["sorties"] if x["data_id"] == cadre["data_id"]][0]
        assert "proposition" in s and s["mesurable"] is True

    def test_etat_activite_refuse_a_un_tiers(self, auth_client, cadre, comme_tiers):
        r = auth_client.get("/paliers/activite/%d/%d" % (cadre["bob_id"], cadre["activity_id"]))
        assert r.status_code == 403

    def test_historique_refuse_a_un_tiers(self, auth_client, cadre, comme_tiers):
        r = auth_client.get("/paliers/historique/%d/%d" % (cadre["bob_id"], cadre["activity_id"]))
        assert r.status_code == 403

    def test_historique_sans_norme_est_vide(self, auth_client, cadre, comme_dev):
        r = auth_client.get("/paliers/historique/%d/%d" % (cadre["bob_id"], cadre["activity_id"]))
        assert r.status_code == 200
        assert r.get_json()["series"] == []

    def test_lister_sessions_refuse_a_un_tiers(self, auth_client, cadre, comme_tiers):
        assert auth_client.get("/paliers/sessions/%d" % cadre["bob_id"]).status_code == 403

    def test_lister_sessions_compte_les_paliers_rattaches(self, auth_client, cadre, comme_dev):
        _norme(auth_client, cadre, valeur=48, unite="h", sens="moins")
        sid = auth_client.post("/paliers/session", json={
            "user_id": cadre["bob_id"], "role_id": cadre["role_id"],
            "date_prevue": date.today().isoformat()}).get_json()["session"]["id"]
        auth_client.post("/paliers/palier", json={
            "user_id": cadre["bob_id"], "data_id": cadre["data_id"],
            "role_id": cadre["role_id"], "cible": 96, "session_id": sid})
        r = auth_client.get("/paliers/sessions/%d?role_id=%d" % (cadre["bob_id"], cadre["role_id"]))
        assert r.status_code == 200
        j = r.get_json()
        assert j["aujourdhui"] == date.today().isoformat()
        assert len(j["sessions"]) == 1


class TestCreerPalierErreurs:
    def _poser(self, client, cadre, **sur):
        corps = {"user_id": cadre["bob_id"], "data_id": cadre["data_id"],
                 "role_id": cadre["role_id"], "cible": 96}
        corps.update(sur)
        return client.post("/paliers/palier", json=corps)

    def test_refuse_a_un_tiers_403(self, auth_client, cadre, comme_tiers):
        assert self._poser(auth_client, cadre).status_code == 403

    def test_sortie_inconnue_400(self, auth_client, cadre, comme_dev):
        r = self._poser(auth_client, cadre, data_id=99999999)
        assert r.status_code == 400 and r.get_json()["error"] == "not_measurable"

    def test_cible_illisible_400(self, auth_client, cadre, comme_dev):
        _norme(auth_client, cadre, valeur=48, unite="h", sens="moins")
        r = self._poser(auth_client, cadre, cible="beaucoup")
        assert r.status_code == 400 and r.get_json()["error"] == "invalid_value"

    def test_cible_absente_400(self, auth_client, cadre, comme_dev):
        _norme(auth_client, cadre, valeur=48, unite="h", sens="moins")
        corps = {"user_id": cadre["bob_id"], "data_id": cadre["data_id"],
                 "role_id": cadre["role_id"]}
        assert auth_client.post("/paliers/palier", json=corps).status_code == 400

    def test_role_qui_ne_porte_pas_l_activite_404(self, app, auth_client, cadre, comme_dev, ids):
        from Code.models.models import Role, UserRole
        _norme(auth_client, cadre, valeur=48, unite="h", sens="moins")
        with app.app_context():
            autre = Role(name="T110 Autre %d" % _N[0], entity_id=ids["entity_id"])
            db.session.add(autre)
            db.session.commit()
            db.session.add(UserRole(user_id=cadre["bob_id"], role_id=autre.id,
                                    manager_id=cadre["dev_id"]))
            db.session.commit()
            autre_id = autre.id
        try:
            r = self._poser(auth_client, cadre, role_id=autre_id)
            assert r.status_code == 404
            assert r.get_json()["error"] == "association_not_found"
        finally:
            with app.app_context():
                for ur in UserRole.query.filter_by(role_id=autre_id).all():
                    db.session.delete(ur)
                db.session.commit()
                db.session.delete(db.session.get(Role, autre_id))
                db.session.commit()

    def test_echeance_illisible_est_ignoree(self, auth_client, cadre, comme_dev):
        _norme(auth_client, cadre, valeur=48, unite="h", sens="moins")
        r = self._poser(auth_client, cadre, echeance="pas-une-date")
        assert r.status_code == 200
        assert r.get_json()["etat"]["paliers"][-1]["id"]


class TestPalierTrancherSupprimer:
    def _palier(self, client, cadre):
        _norme(client, cadre, valeur=48, unite="h", sens="moins")
        r = client.post("/paliers/palier", json={
            "user_id": cadre["bob_id"], "data_id": cadre["data_id"],
            "role_id": cadre["role_id"], "cible": 96,
            "echeance": (date.today() + timedelta(days=30)).isoformat()})
        assert r.status_code == 200
        return r.get_json()["etat"]["paliers"][-1]["id"]

    def test_trancher_inconnu_404(self, auth_client):
        assert auth_client.post("/paliers/palier/99999999/trancher",
                                json={"mesure": 1}).status_code == 404

    def test_supprimer_inconnu_404(self, auth_client):
        assert auth_client.delete("/paliers/palier/99999999").status_code == 404

    def test_trancher_refuse_a_un_tiers(self, auth_client, cadre, comme_dev):
        pid = self._palier(auth_client, cadre)
        _comme(auth_client, cadre["tiers_id"])
        assert auth_client.post("/paliers/palier/%d/trancher" % pid,
                                json={"mesure": 50}).status_code == 403

    def test_supprimer_refuse_a_un_tiers(self, auth_client, cadre, comme_dev):
        pid = self._palier(auth_client, cadre)
        _comme(auth_client, cadre["tiers_id"])
        assert auth_client.delete("/paliers/palier/%d" % pid).status_code == 403

    def test_trancher_mesure_illisible_400(self, auth_client, cadre, comme_dev):
        pid = self._palier(auth_client, cadre)
        r = auth_client.post("/paliers/palier/%d/trancher" % pid, json={"mesure": "x"})
        assert r.status_code == 400 and r.get_json()["error"] == "invalid_value"

    def test_trancher_sans_mesure_400(self, auth_client, cadre, comme_dev):
        pid = self._palier(auth_client, cadre)
        assert auth_client.post("/paliers/palier/%d/trancher" % pid, json={}).status_code == 400

    def test_trancher_rend_un_statut_et_l_etat(self, auth_client, cadre, comme_dev):
        pid = self._palier(auth_client, cadre)
        r = auth_client.post("/paliers/palier/%d/trancher" % pid, json={"mesure": 90})
        assert r.status_code == 200
        j = r.get_json()
        assert j["statut"] and j["etat"]["data_id"] == cadre["data_id"]

    def test_supprimer_un_palier_le_retire_de_l_etat(self, auth_client, cadre, comme_dev):
        pid = self._palier(auth_client, cadre)
        r = auth_client.delete("/paliers/palier/%d" % pid)
        assert r.status_code == 200
        assert pid not in [p["id"] for p in r.get_json()["etat"]["paliers"]]
        assert auth_client.delete("/paliers/palier/%d" % pid).status_code == 404


class TestSessionsErreurs:
    def _session(self, client, cadre, **sur):
        corps = {"user_id": cadre["bob_id"], "role_id": cadre["role_id"],
                 "date_prevue": date.today().isoformat()}
        corps.update(sur)
        return client.post("/paliers/session", json=corps)

    def test_role_obligatoire_400(self, auth_client, cadre, comme_dev):
        r = auth_client.post("/paliers/session", json={"user_id": cadre["bob_id"]})
        assert r.status_code == 400 and r.get_json()["reason"] == "role_required"

    def test_planifier_refuse_a_un_tiers(self, auth_client, cadre, comme_tiers):
        assert self._session(auth_client, cadre).status_code == 403

    def test_date_invalide_400(self, auth_client, cadre, comme_dev):
        r = self._session(auth_client, cadre, date_prevue="demain")
        assert r.status_code == 400 and r.get_json()["error"] == "invalid_date"

    def test_objet_tronque_a_200(self, auth_client, cadre, comme_dev):
        r = self._session(auth_client, cadre, objet="o" * 300)
        assert len(r.get_json()["session"]["objet"]) == 200

    def test_maj_inconnue_404(self, auth_client):
        assert auth_client.post("/paliers/session/99999999", json={}).status_code == 404

    def test_supprimer_inconnue_404(self, auth_client):
        assert auth_client.delete("/paliers/session/99999999").status_code == 404

    def test_maj_refusee_a_un_tiers(self, auth_client, cadre, comme_dev):
        sid = self._session(auth_client, cadre).get_json()["session"]["id"]
        _comme(auth_client, cadre["tiers_id"])
        assert auth_client.post("/paliers/session/%d" % sid, json={"note": "x"}).status_code == 403
        assert auth_client.delete("/paliers/session/%d" % sid).status_code == 403

    def test_statut_invalide_400(self, auth_client, cadre, comme_dev):
        sid = self._session(auth_client, cadre).get_json()["session"]["id"]
        r = auth_client.post("/paliers/session/%d" % sid, json={"statut": "rêvée"})
        assert r.status_code == 400 and r.get_json()["error"] == "invalid_status"

    def test_replanifier_date_invalide_400(self, auth_client, cadre, comme_dev):
        sid = self._session(auth_client, cadre).get_json()["session"]["id"]
        r = auth_client.post("/paliers/session/%d" % sid, json={"date_prevue": "zzz"})
        assert r.status_code == 400 and r.get_json()["error"] == "invalid_date"

    def test_replanifier_note_et_objet(self, auth_client, cadre, comme_dev):
        sid = self._session(auth_client, cadre, objet="avant").get_json()["session"]["id"]
        nouvelle = (date.today() + timedelta(days=9)).isoformat()
        r = auth_client.post("/paliers/session/%d" % sid, json={
            "date_prevue": nouvelle, "note": "  vu  ", "objet": ""})
        assert r.status_code == 200
        s = r.get_json()["session"]
        assert s["date_prevue"] == nouvelle
        assert s["note"] == "vu" and not s["objet"]

    def test_tenir_puis_annuler_efface_la_date_de_tenue(self, auth_client, cadre, comme_dev):
        sid = self._session(auth_client, cadre).get_json()["session"]["id"]
        tenue = auth_client.post("/paliers/session/%d" % sid, json={"statut": "tenue"})
        assert tenue.get_json()["session"]["statut"] == "tenue"
        annulee = auth_client.post("/paliers/session/%d" % sid, json={"statut": "ANNULEE"})
        assert annulee.status_code == 200
        assert annulee.get_json()["session"]["statut"] == "annulee"
