# -*- coding: utf-8 -*-
"""Les PALIERS DE PERFORMANCE — le parcours de Bob, au mot près.

« La performance globale attendue est de 48 h. Bob commence, son gestionnaire
de compétences va lui donner 96 h pour la première fois et 30 jours pour
arriver à ce palier. 30 jours plus tard il a réussi : on le passe à 72 h sous
15 jours. Rebelote, réussi : on l'aligne sur les 48 h de l'entreprise, il est
désormais qualifié. Mais il peut aussi faire mieux — 24 h — et avoir un niveau
de maîtrise supérieur. L'inverse est possible aussi. »
"""
import io
import json
import os
from datetime import date, datetime, timedelta

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(chemin):
    return io.open(os.path.join(RACINE, chemin), encoding="utf-8").read()


_N = [0]


@pytest.fixture
def bob(app, ids):
    """Bob, son rôle, son activité, et la sortie que l'entreprise mesure."""
    from Code.models.models import (Activities, Data, Link, Role, User, UserRole,
                                    activity_roles)
    from Code.security import hash_password
    _N[0] += 1
    n = _N[0]
    with app.app_context():
        dev = User(first_name="Dev", last_name="T108", email="dev.t108.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        b = User(first_name="Bob", last_name="T108", email="bob.t108.%d@test" % n,
                 password=hash_password("Test1234!"), status="user")
        db.session.add_all([dev, b])
        db.session.commit()

        role = Role(name="T108 Rédacteur %d" % n, entity_id=ids["entity_id"])
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=b.id, role_id=role.id, manager_id=dev.id))

        act = Activities(name="T108 Documenter %d" % n, entity_id=ids["entity_id"])
        aval = Activities(name="T108 Aval %d" % n, entity_id=ids["entity_id"])
        db.session.add_all([act, aval])
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant",
            required_mastery_level=2))
        # La sortie EST une connexion sortante de la carto.
        db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=act.id,
                            target_activity_id=aval.id, description="Documentation %d" % n,
                            type="flux"))
        db.session.commit()

        from Code.routes.qualify_outputs import get_activity_outputs
        sortie = get_activity_outputs(act.id)[0]
        # La norme de l'entreprise : fournir la doc sous 48 h.
        sortie.norme_valeur = 48.0
        sortie.norme_unite = "h"
        sortie.norme_sens = "moins"
        db.session.commit()
        info = {"dev_id": dev.id, "bob_id": b.id, "role_id": role.id,
                "activity_id": act.id, "data_id": sortie.id}
    yield info
    with app.app_context():
        from Code.models.models import PalierPerformance, SessionEvaluation
        for m in (PalierPerformance, SessionEvaluation):
            for x in m.query.filter_by(user_id=info["bob_id"]).all():
                db.session.delete(x)
        db.session.commit()


@pytest.fixture
def comme_dev(auth_client, bob):
    """On agit en tant que développeur de compétences de Bob."""
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")
        sess["user_id"] = bob["dev_id"]
    yield
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


def _palier(client, bob, cible, jours=30):
    r = client.post("/paliers/palier", json={
        "user_id": bob["bob_id"], "data_id": bob["data_id"], "role_id": bob["role_id"],
        "cible": cible,
        "echeance": (date.today() + timedelta(days=jours)).isoformat()})
    assert r.status_code == 200, r.data
    etat = json.loads(r.data)["etat"]
    return etat["palier_en_cours"]["id"], etat


def _trancher(client, pid, mesure):
    r = client.post("/paliers/palier/%d/trancher" % pid, json={"mesure": mesure})
    assert r.status_code == 200, r.data
    return json.loads(r.data)


class TestLeParcoursDeBob:

    def test_de_96_a_48_puis_au_dela(self, auth_client, bob, comme_dev):
        # ── Palier 1 : 96 h sous 30 jours. Réussi.
        p1, etat = _palier(auth_client, bob, 96, 30)
        assert etat["niveau"] is None, "rien n'est encore mesuré"
        d = _trancher(auth_client, p1, 88)
        assert d["statut"] == "atteint"
        assert d["etat"]["niveau"] == 1, "un palier franchi, pas encore la norme"
        assert d["etat"]["qualifie"] is False

        # ── Palier 2 : 72 h sous 15 jours. Réussi.
        p2, _ = _palier(auth_client, bob, 72, 15)
        d = _trancher(auth_client, p2, 70)
        assert d["statut"] == "atteint"
        assert d["etat"]["niveau"] == 1

        # ── Palier 3 : la norme. Bob est QUALIFIÉ.
        p3, _ = _palier(auth_client, bob, 48, 15)
        d = _trancher(auth_client, p3, 47)
        assert d["statut"] == "atteint"
        assert d["etat"]["niveau"] == 2, "la norme atteinte = qualifié"
        assert d["etat"]["qualifie"] is True

        # ── Et mieux que la norme : niveau supérieur.
        p4, _ = _palier(auth_client, bob, 48, 15)
        d = _trancher(auth_client, p4, 24)
        assert d["etat"]["niveau"] == 3, "dépasser la norme = maîtrise étendue"

    def test_un_echec_ne_fait_pas_reculer_le_verdict_du_palier(self, auth_client, bob, comme_dev):
        """Bob n'arrive pas à passer de 96 à 72."""
        p1, _ = _palier(auth_client, bob, 96, 30)
        _trancher(auth_client, p1, 88)
        p2, _ = _palier(auth_client, bob, 72, 15)
        d = _trancher(auth_client, p2, 80)
        assert d["statut"] == "manque"
        # Il reste au-dessus de la première marche : il n'a pas « rien démontré ».
        assert d["etat"]["niveau"] == 1

    def test_pire_que_la_premiere_marche_vaut_zero(self, auth_client, bob, comme_dev):
        """⚠️ 0 (« non démontré ») et NULL (« pas encore mesuré ») ne sont pas
        la même chose — c'est la distinction que tout le module tient."""
        p1, _ = _palier(auth_client, bob, 96, 30)
        d = _trancher(auth_client, p1, 140)
        assert d["statut"] == "manque"
        assert d["etat"]["niveau"] == 0

    def test_poser_la_marche_suivante_ne_fait_pas_retomber_le_niveau(
            self, auth_client, bob, comme_dev):
        """⚠️ Le niveau lit le dernier palier ÉVALUÉ, pas le dernier créé.
        Sinon il repasserait à « non évalué » entre deux sessions."""
        p1, _ = _palier(auth_client, bob, 96, 30)
        _trancher(auth_client, p1, 88)
        _palier(auth_client, bob, 72, 15)
        r = auth_client.get("/paliers/activite/%d/%d?role_id=%d"
                            % (bob["bob_id"], bob["activity_id"], bob["role_id"]))
        sortie = json.loads(r.data)["sorties"][0]
        assert sortie["niveau"] == 1
        assert sortie["palier_en_cours"]["cible"] == 72


class TestLeSensDeLaMesure:
    """⚠️ Une durée se bat à la BAISSE, un taux à la HAUSSE. Sans le sens,
    « mieux » n'a pas de définition — et il est stocké pour ça."""

    def test_moins_c_est_mieux(self, app):
        from Code.paliers import atteint, niveau_depuis_mesure
        assert atteint(47, 48, "moins") is True
        assert atteint(49, 48, "moins") is False
        # ⚠️ Sans MARGE, « mieux que la norme » ne vaut pas « avancé » : à
        # une heure près de 48 h, la norme est tenue, pas dépassée.
        assert niveau_depuis_mesure(47, 48, "moins", 96) == 2
        assert niveau_depuis_mesure(24, 48, "moins", 96) == 2
        # Avec le pas que le développeur a posé (72 → 48, soit 24), un palier
        # de mieux que la norme = maîtrise étendue.
        assert niveau_depuis_mesure(24, 48, "moins", 96, marge=24) == 3
        assert niveau_depuis_mesure(47, 48, "moins", 96, marge=24) == 2
        assert niveau_depuis_mesure(48, 48, "moins", 96) == 2

    def test_plus_c_est_mieux(self, app):
        from Code.paliers import atteint, niveau_depuis_mesure
        assert atteint(96, 95, "plus") is True
        assert atteint(94, 95, "plus") is False
        # Un taux de conformité : la norme est 95 %, il en fait 99.
        assert niveau_depuis_mesure(99, 95, "plus", 70, marge=3) == 3
        assert niveau_depuis_mesure(96, 95, "plus", 70, marge=3) == 2
        assert niveau_depuis_mesure(95, 95, "plus", 70) == 2
        assert niveau_depuis_mesure(80, 95, "plus", 70) == 1
        assert niveau_depuis_mesure(60, 95, "plus", 70) == 0

    def test_sans_mesure_le_niveau_est_NUL(self, app):
        from Code.paliers import niveau_depuis_mesure
        assert niveau_depuis_mesure(None, 48, "moins", 96) is None


class TestLesDeuxRegimesCohabitent:
    """⚠️ Toutes les sorties ne sont pas mesurables : « Cahier des charges
    validé » n'a pas de durée. Une sortie sans norme chiffrée reste jugée à la
    main sur l'échelle 0→4."""

    def test_une_sortie_sans_norme_n_est_pas_mesurable(self, app, bob):
        from Code.models.models import Data
        from Code.paliers import mesurable
        with app.app_context():
            d = db.session.get(Data, bob["data_id"])
            assert mesurable(d) is True
            d.norme_valeur = None
            db.session.commit()
            assert mesurable(d) is False
            d.norme_valeur = 48.0
            db.session.commit()

    def test_une_sortie_MESURABLE_ne_se_note_pas_a_la_main(
            self, auth_client, bob, comme_dev):
        """Deux notes pour une même chose finiraient par se contredire, et
        c'est le chiffre mesuré qui fait foi."""
        r = auth_client.post("/mastery/evaluate", json={
            "user_id": bob["bob_id"], "activity_id": bob["activity_id"],
            "role_id": bob["role_id"], "data_id": bob["data_id"],
            "evaluator": "2", "mastery_level": 4})
        assert r.status_code == 400, r.data
        assert json.loads(r.data)["error"] == "measured_output"

    def test_mais_l_auto_evaluation_reste_permise(self, auth_client, bob):
        """C'est un repère que le collaborateur se donne, jamais le niveau qui
        fait foi."""
        with auth_client.session_transaction() as sess:
            avant = sess.get("user_id")
            sess["user_id"] = bob["bob_id"]
        try:
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": bob["bob_id"], "activity_id": bob["activity_id"],
                "role_id": bob["role_id"], "data_id": bob["data_id"],
                "evaluator": "0", "mastery_level": 3})
            assert r.status_code == 200, r.data
        finally:
            with auth_client.session_transaction() as sess:
                if avant is None:
                    sess.pop("user_id", None)
                else:
                    sess["user_id"] = avant

    def test_le_niveau_de_l_activite_vient_de_ses_sorties(
            self, auth_client, bob, comme_dev):
        """« C'est l'ensemble des notations sur les sorties qui génère un degré
        de compétence sur une activité. » La règle du MINIMUM ne change pas."""
        p1, _ = _palier(auth_client, bob, 96, 30)
        _trancher(auth_client, p1, 47)       # d'emblée la norme
        r = auth_client.get("/mastery/activity/%d/%d?role_id=%d"
                            % (bob["bob_id"], bob["activity_id"], bob["role_id"]))
        assert r.status_code == 200, r.data
        etat = json.loads(r.data)
        assert etat["global_level"] == 2
        sortie = etat["results"][0]
        assert sortie["mesurable"] is True
        assert sortie["demonstrated_level"] == 2
        assert sortie["performance"]["mesure"] == 47


class TestLesSessionsAuCalendrier:

    def test_planifier_tenir_et_retrouver(self, auth_client, bob, comme_dev):
        quand = (date.today() + timedelta(days=30)).isoformat()
        r = auth_client.post("/paliers/session", json={
            "user_id": bob["bob_id"], "role_id": bob["role_id"],
            "date_prevue": quand, "objet": "Premier point"})
        assert r.status_code == 200, r.data
        sid = json.loads(r.data)["session"]["id"]

        r = auth_client.get("/paliers/sessions/%d?role_id=%d"
                            % (bob["bob_id"], bob["role_id"]))
        liste = json.loads(r.data)["sessions"]
        assert [s["id"] for s in liste] == [sid]
        assert liste[0]["date_prevue"] == quand
        assert liste[0]["en_retard"] is False

        r = auth_client.post("/paliers/session/%d" % sid,
                             json={"statut": "tenue", "note": "Bob a réussi"})
        assert r.status_code == 200, r.data
        assert json.loads(r.data)["session"]["statut"] == "tenue"

    def test_une_session_passee_est_signalee_EN_RETARD(self, auth_client, bob, comme_dev):
        """Une échéance dépassée qui ressemble à une échéance à venir ne sert
        à rien : c'est tout l'intérêt du calendrier."""
        hier = (date.today() - timedelta(days=3)).isoformat()
        auth_client.post("/paliers/session", json={
            "user_id": bob["bob_id"], "role_id": bob["role_id"], "date_prevue": hier})
        liste = json.loads(auth_client.get(
            "/paliers/sessions/%d" % bob["bob_id"]).data)["sessions"]
        assert liste[0]["en_retard"] is True

    def test_supprimer_une_session_ne_detruit_pas_les_mesures(
            self, auth_client, bob, comme_dev):
        """⚠️ Les paliers SURVIVENT, détachés : ils portent des mesures, et
        supprimer un rendez-vous n'efface pas ce qui a été constaté."""
        from Code.models.models import PalierPerformance
        r = auth_client.post("/paliers/session", json={
            "user_id": bob["bob_id"], "role_id": bob["role_id"],
            "date_prevue": date.today().isoformat()})
        sid = json.loads(r.data)["session"]["id"]
        p1, _ = _palier(auth_client, bob, 96, 30)
        pal = db.session.get(PalierPerformance, p1)
        pal.session_id = sid
        db.session.commit()
        _trancher(auth_client, p1, 88)

        assert auth_client.delete("/paliers/session/%d" % sid).status_code == 200
        pal = db.session.get(PalierPerformance, p1)
        assert pal is not None and pal.mesure_valeur == 88
        assert pal.session_id is None


class TestLHistoriqueEtLesDroits:

    def test_chaque_mesure_fait_un_point(self, auth_client, bob, comme_dev):
        for cible, mesure in ((96, 88), (72, 70), (48, 47)):
            pid, _ = _palier(auth_client, bob, cible, 15)
            _trancher(auth_client, pid, mesure)
        r = auth_client.get("/paliers/historique/%d/%d?role_id=%d"
                            % (bob["bob_id"], bob["activity_id"], bob["role_id"]))
        assert r.status_code == 200, r.data
        series = json.loads(r.data)["series"]
        assert len(series) == 1
        assert [p["mesure"] for p in series[0]["points"]] == [88, 70, 47]
        assert series[0]["norme"] == 48.0

    def test_une_cible_posee_n_est_PAS_un_point(self, auth_client, bob, comme_dev):
        """Tracer une cible dessinerait une progression qui n'a pas eu lieu."""
        _palier(auth_client, bob, 96, 30)
        series = json.loads(auth_client.get(
            "/paliers/historique/%d/%d" % (bob["bob_id"], bob["activity_id"])).data)["series"]
        assert series[0]["points"] == []

    def test_un_tiers_ne_pose_pas_de_cible(self, auth_client, bob, ids):
        """Poser une cible décide de la carrière de quelqu'un."""
        with auth_client.session_transaction() as sess:
            avant = sess.get("user_id")
            sess["user_id"] = bob["bob_id"]        # Bob lui-même
        try:
            r = auth_client.post("/paliers/palier", json={
                "user_id": bob["bob_id"], "data_id": bob["data_id"],
                "role_id": bob["role_id"], "cible": 10})
            assert r.status_code == 403, r.data
        finally:
            with auth_client.session_transaction() as sess:
                if avant is None:
                    sess.pop("user_id", None)
                else:
                    sess["user_id"] = avant

    def test_le_role_est_obligatoire(self, auth_client, bob, comme_dev):
        """⚠️ Sans rôle, le contrôle retombe sur la règle par personne :
        l'omettre suffirait à contourner le développeur par rôle."""
        r = auth_client.post("/paliers/palier", json={
            "user_id": bob["bob_id"], "data_id": bob["data_id"], "cible": 96})
        assert r.status_code == 400
        assert json.loads(r.data)["reason"] == "role_required"

    def test_une_sortie_NON_mesurable_refuse_les_paliers(
            self, app, auth_client, bob, comme_dev):
        from Code.models.models import Data
        d = db.session.get(Data, bob["data_id"])
        d.norme_valeur = None
        db.session.commit()
        try:
            r = auth_client.post("/paliers/palier", json={
                "user_id": bob["bob_id"], "data_id": bob["data_id"],
                "role_id": bob["role_id"], "cible": 96})
            assert r.status_code == 400
            assert json.loads(r.data)["error"] == "not_measurable"
        finally:
            d = db.session.get(Data, bob["data_id"])
            d.norme_valeur = 48.0
            db.session.commit()


class TestLaPropositionDeCible:
    """Rien ne remplace le jugement du développeur — mais partir d'une page
    blanche à chaque palier est pénible."""

    def test_le_premier_palier_part_du_double_pour_une_duree(self, app, bob):
        from Code.models.models import Data
        from Code.paliers import proposer_cible
        with app.app_context():
            d = db.session.get(Data, bob["data_id"])
            assert proposer_cible(d, bob["bob_id"], bob["role_id"]) == 96.0

    def test_ensuite_on_coupe_en_deux_ce_qui_reste(self, auth_client, bob, comme_dev, app):
        from Code.models.models import Data
        from Code.paliers import proposer_cible
        p1, _ = _palier(auth_client, bob, 96, 30)
        _trancher(auth_client, p1, 96)
        d = db.session.get(Data, bob["data_id"])
        # De 96 à 48, la moitié du chemin : 72.
        assert proposer_cible(d, bob["bob_id"], bob["role_id"]) == 72.0

class TestLaMargeVientDeLaProgression:
    """⚠️ « Mieux que la norme » n'est pas « une heure de mieux ». La marge
    n'est pas un seuil inventé : c'est le dernier PAS que le développeur a
    lui-même posé — 96 → 72 → 48 donne 24, exactement le chiffre du niveau
    supérieur dans l'exemple."""

    def test_le_pas_se_lit_sur_les_cibles(self, app):
        from Code.paliers import pas_de_progression
        assert pas_de_progression([96, 72, 48], 48, "moins") == 24
        assert pas_de_progression([96], 48, "moins") == 48

    def test_sans_marche_sous_la_norme_il_n_y_a_PAS_de_pas(self, app):
        """Le premier palier EST la norme : on n'invente pas un seuil pour
        pouvoir afficher « avancé »."""
        from Code.paliers import pas_de_progression
        assert pas_de_progression([48], 48, "moins") is None
        assert pas_de_progression([], 48, "moins") is None
