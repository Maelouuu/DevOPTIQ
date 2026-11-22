# -*- coding: utf-8 -*-
"""Modèles — les méthodes de périmètre et d'affichage jamais appelées par la suite.

`for_active_entity()` existe sur huit modèles ; la plupart des routes passent
par d'autres requêtes, si bien que la branche « aucune entité active » (requête
VIDE, jamais `query.all()` de toute l'instance) n'était éprouvée nulle part.
C'est pourtant elle qui empêche une session sans entité de lire les données de
tous les clients.

⚠️ Chaque test pose sa propre session (`test_request_context`) et nettoie les
lignes qu'il crée : rien ne fuit vers la session partagée de la suite.
"""
import pytest
from flask import session

from Code.extensions import db
from Code.models import models as m


MODELES_PERIMETRE = ["Data", "Tool", "Role", "Link", "User", "TimeProject"]


@pytest.fixture()
def lignes_jetables(app, ids):
    """Un outil et un rôle dans l'entité du décor (absents du seed)."""
    t = m.Tool(name="Outil 158", entity_id=ids["entity_id"])
    r = m.Role(name="Rôle 158", entity_id=ids["entity_id"])
    db.session.add_all([t, r])
    db.session.commit()
    yield t, r
    db.session.rollback()
    for obj in (t, r):
        db.session.delete(db.session.get(type(obj), obj.id))
    db.session.commit()


@pytest.fixture()
def autre_compte(app):
    """Un compte étranger et sa carto privée — supprimés après le test."""
    u = m.User(first_name="Autre", last_name="Compte", email="autre-158@test.fr",
               password="x", status="user")
    db.session.add(u)
    db.session.flush()
    e = m.Entity(name="Carto privée 158", owner_id=u.id)
    db.session.add(e)
    db.session.commit()
    yield u, e
    db.session.rollback()
    db.session.delete(db.session.get(m.Entity, e.id))
    db.session.delete(db.session.get(m.User, u.id))
    db.session.commit()


class TestPerimetreSansEntiteActive:

    @pytest.mark.parametrize("nom", MODELES_PERIMETRE)
    def test_sans_session_requete_vide(self, app, lignes_jetables, nom):
        modele = getattr(m, nom)
        if nom != "TimeProject":
            assert modele.query.count() > 0   # la requête vide n'est pas un hasard
        with app.test_request_context("/"):
            assert modele.for_active_entity().all() == []

    @pytest.mark.parametrize("nom", MODELES_PERIMETRE)
    def test_avec_entite_active_borne_a_l_entite(self, app, ids, lignes_jetables, nom):
        modele = getattr(m, nom)
        with app.test_request_context("/"):
            session["user_id"] = ids["user_id"]
            session["active_entity_id"] = ids["entity_id"]
            lignes = modele.for_active_entity().all()
        assert all(l.entity_id == ids["entity_id"] for l in lignes)

    def test_user_for_active_entity_exclut_les_autres_entites(self, app, ids, autre_compte):
        u, _ = autre_compte
        with app.test_request_context("/"):
            session["user_id"] = ids["user_id"]
            session["active_entity_id"] = ids["entity_id"]
            emails = {x.email for x in m.User.for_active_entity().all()}
        assert u.email not in emails
        assert "test@devoptiq.com" in emails


class TestEntite:

    def test_repr(self, app, ids):
        e = db.session.get(m.Entity, ids["entity_id"])
        assert repr(e) == f"<Entity {e.id}: Entité Test>"

    def test_accessible_lit_la_session(self, app, ids):
        with app.test_request_context("/"):
            session["user_id"] = ids["user_id"]
            noms = [e.name for e in m.Entity.accessible()]
        assert "Entité Test" in noms

    def test_accessible_sans_compte_vide(self, app):
        with app.test_request_context("/"):
            assert m.Entity.accessible() == []

    def test_accessible_compte_inconnu_vide(self, app):
        assert m.Entity.accessible(user_id=987654) == []

    def test_set_active_sans_compte_refuse(self, app, ids):
        with app.test_request_context("/"):
            assert m.Entity.set_active(ids["entity_id"]) is None
            assert "active_entity_id" not in session

    def test_set_active_sur_sa_carto(self, app, ids):
        with app.test_request_context("/"):
            session["user_id"] = ids["user_id"]
            e = m.Entity.set_active(ids["entity_id"])
            assert e.id == ids["entity_id"]
            assert session["active_entity_id"] == ids["entity_id"]

    def test_set_active_user_id_explicite(self, app, ids):
        with app.test_request_context("/"):
            e = m.Entity.set_active(ids["entity_id"], user_id=ids["user_id"])
            assert e is not None and session["active_entity_id"] == e.id

    def test_set_active_carto_privee_d_autrui_refusee(self, app, ids, autre_compte):
        _, privee = autre_compte
        with app.test_request_context("/"):
            session["user_id"] = ids["user_id"]
            session["active_entity_id"] = ids["entity_id"]
            assert m.Entity.set_active(privee.id) is None
            assert session["active_entity_id"] == ids["entity_id"]

    def test_set_active_entite_inexistante(self, app, ids):
        with app.test_request_context("/"):
            assert m.Entity.set_active(999999, user_id=ids["user_id"]) is None

    def test_for_user_rend_ses_cartos_triees(self, app, autre_compte):
        u, e = autre_compte
        b = m.Entity(name="A — avant 158", owner_id=u.id)
        db.session.add(b)
        db.session.commit()
        try:
            assert [x.name for x in m.Entity.for_user(u.id).all()] == [b.name, e.name]
        finally:
            db.session.delete(b)
            db.session.commit()

    def test_for_user_lit_la_session(self, app, autre_compte):
        u, e = autre_compte
        with app.test_request_context("/"):
            session["user_id"] = u.id
            assert [x.id for x in m.Entity.for_user().all()] == [e.id]

    def test_for_user_sans_compte_vide(self, app):
        with app.test_request_context("/"):
            assert m.Entity.for_user().all() == []


class TestLienExtremites:

    def test_source_activite_prioritaire(self):
        assert m.Link(source_activity_id=3, source_data_id=9, type="x").source_id == 3

    def test_source_donnee_sinon(self):
        assert m.Link(source_data_id=9, type="x").source_id == 9

    def test_cible_activite_prioritaire(self):
        assert m.Link(target_activity_id=4, target_data_id=8, type="x").target_id == 4

    def test_cible_donnee_sinon(self):
        assert m.Link(target_data_id=8, type="x").target_id == 8

    def test_activite_zero_n_est_pas_absente(self):
        """`is not None`, pas un test de vérité : l'id 0 reste une activité."""
        assert m.Link(source_activity_id=0, source_data_id=9, type="x").source_id == 0

    def test_sans_extremite_none(self):
        lk = m.Link(type="x")
        assert (lk.source_id, lk.target_id) == (None, None)


class TestAnalyseTempsRetards:

    @pytest.mark.parametrize("delay,inc,gap", [
        (10, 5, 15), (10, None, 10), (None, 4, 4), (None, None, 0), (0, 3, 3)])
    def test_delay_gap(self, delay, inc, gap):
        assert m.TimeAnalysis(delay=delay, delay_increase=inc).delay_gap == gap

    @pytest.mark.parametrize("delay,inc,ratio", [
        (10, 5, 50.0), (3, 1, 33.3), (10, None, 0), (None, 4, 0), (0, 4, 0)])
    def test_delay_ratio(self, delay, inc, ratio):
        assert m.TimeAnalysis(delay=delay, delay_increase=inc).delay_ratio == ratio


class TestJournalAutomatique:

    def test_log_recent_connexion_en_echec_avale(self, app):
        class _Connexion:
            def execute(self, *a, **k):
                raise RuntimeError("table absente")
        assert m._log_recent(_Connexion(), "x", "i", "libellé") is None

    def test_log_recent_ecrit_l_auteur_de_la_session(self, app, ids):
        appels = []

        class _Connexion:
            def execute(self, sql, params):
                appels.append(params)
        with app.test_request_context("/"):
            session["user_id"] = ids["user_id"]
            m._log_recent(_Connexion(), "tool_created", "i", "Outil", entity_id=7,
                          detail={"name": "é"})
        assert appels[0]["uid"] == ids["user_id"]
        assert appels[0]["eid"] == 7
        assert appels[0]["detail"] == '{"name": "é"}'

    def test_log_recent_sans_detail_ni_requete(self, app):
        appels = []

        class _Connexion:
            def execute(self, sql, params):
                appels.append(params)
        m._log_recent(_Connexion(), "x", "i", "l")
        assert appels[0]["detail"] is None and appels[0]["uid"] is None

    def test_capture_changes_objet_non_mappe_vide(self):
        assert m._capture_changes(object(), {"name": "Nom"}) == []

    def test_capture_changes_avant_apres(self, app, lignes_jetables):
        t = lignes_jetables[0]
        ancien = t.name
        try:
            t.name = ancien + " (modifié)"
            assert m._capture_changes(t, {"name": "Nom"}) == [
                {"field": "Nom", "before": ancien, "after": ancien + " (modifié)"}]
        finally:
            db.session.rollback()

    def test_capture_changes_sans_modification(self, app, lignes_jetables):
        t = lignes_jetables[0]
        assert m._capture_changes(t, {"name": "Nom"}) == []


class TestPermissionsResiduel:

    @pytest.mark.parametrize("statut", ["coordinateur RH", "Coordinator (site)",
                                        "coordinateur-adjoint"])
    def test_coordinateur_prefixe_reconnu(self, statut):
        from Code.permissions import is_coordinator_status
        assert is_coordinator_status(statut) is True

    @pytest.mark.parametrize("statut,attendu", [
        ("champion", True), ("coordinateur", True), ("administrateur", True),
        ("user", False)])
    def test_is_champion_compte_explicite(self, app, statut, attendu):
        from Code.permissions import is_champion
        u = m.User(first_name="a", last_name="b", email="x@y.z", password="x",
                   status=statut)
        assert is_champion(u) is attendu

    def test_reglages_hors_contexte_vides(self, app):
        """Hors contexte d'application (script, import), pas de lecture de base."""
        from flask import globals as fg
        from Code.permissions import _reglages_stockes
        # La suite tourne DANS un contexte d'app : on en sort le temps d'un appel.
        jeton = fg._cv_app.set(None)
        try:
            assert _reglages_stockes() == {}
        finally:
            fg._cv_app.reset(jeton)

    def test_reglages_illisibles_et_rollback_en_echec(self, app, monkeypatch):
        from Code import permissions

        def _boum(*a, **k):
            raise RuntimeError("HS")
        monkeypatch.setattr(db.session, "get", _boum)
        monkeypatch.setattr(db.session, "rollback", _boum)
        assert permissions._reglages_stockes() == {}

    @pytest.mark.parametrize("acteur_vide", [True, False])
    def test_changer_statut_sans_acteur_ou_cible_interdit(self, app, acteur_vide):
        from Code.permissions import peut_changer_statut
        u = m.User(id=1, status="administrateur")
        args = (None, u) if acteur_vide else (u, None)
        assert peut_changer_statut(*args, "user") == "error_forbidden_edit"

    def test_reprise_table_absente_se_rejouera(self, app, monkeypatch):
        from Code import permissions

        def _boum(*a, **k):
            raise RuntimeError("no such table: app_settings")
        appels = []
        monkeypatch.setattr(db.session, "get", _boum)
        monkeypatch.setattr(db.session, "rollback", lambda: appels.append(1))
        assert permissions._reprise_deja_faite() is False
        assert appels == [1]
