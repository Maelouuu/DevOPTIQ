# -*- coding: utf-8 -*-
"""Modèles — les méthodes que les routes n'appellent plus, mais que les
scripts et les blueprints plus anciens utilisent encore.

Ces cas tournent dans un `test_request_context` à eux : la session HTTP
partagée de la suite (`client`) n'est jamais touchée.
"""
import uuid

import pytest

from Code.extensions import db
from Code.models.models import (
    Data, Entity, Link, Role, TimeAnalysis, TimeProject, Tool, User,
    _capture_changes,
)


@pytest.fixture
def req(app):
    """Contexte de requête vierge (session vide) dans l'app de test."""
    with app.test_request_context("/"):
        yield


@pytest.fixture
def entite_etrangere(app):
    """Une entité appartenant à un AUTRE compte, effacée à la fin."""
    with app.app_context():
        u = User(first_name="Ext", last_name="T158",
                 email=f"t158-{uuid.uuid4().hex[:8]}@devoptiq.test",
                 password="x", status="user")
        db.session.add(u)
        db.session.flush()
        e = Entity(name=f"T158 {uuid.uuid4().hex[:6]}", owner_id=u.id)
        db.session.add(e)
        db.session.commit()
        eid, uid = e.id, u.id
    yield eid
    with app.app_context():
        e = db.session.get(Entity, eid)
        if e:
            db.session.delete(e)
        u = db.session.get(User, uid)
        if u:
            db.session.delete(u)
        db.session.commit()


class TestEntiteMethodes:
    def test_repr_donne_id_et_nom(self, app, ids):
        with app.app_context():
            e = db.session.get(Entity, ids["entity_id"])
            assert repr(e) == f"<Entity {e.id}: Entité Test>"

    def test_accessible_sans_compte_en_session_est_vide(self, req):
        assert Entity.accessible() == []

    def test_accessible_compte_inexistant_est_vide(self, req):
        assert Entity.accessible(user_id=987654321) == []

    def test_accessible_lit_le_compte_en_session(self, req, ids):
        from flask import session
        session["user_id"] = ids["user_id"]
        assert ids["entity_id"] in [e.id for e in Entity.accessible()]

    def test_set_active_sans_compte_ne_fait_rien(self, req, ids):
        from flask import session
        assert Entity.set_active(ids["entity_id"]) is None
        assert "active_entity_id" not in session

    def test_set_active_entite_du_compte_la_pose_en_session(self, req, ids):
        from flask import session
        session["user_id"] = ids["user_id"]
        e = Entity.set_active(ids["entity_id"])
        assert e is not None and e.id == ids["entity_id"]
        assert session["active_entity_id"] == ids["entity_id"]

    def test_set_active_entite_d_un_autre_compte_refusee(self, req, ids, entite_etrangere):
        from flask import session
        session["user_id"] = ids["user_id"]
        assert Entity.set_active(entite_etrangere) is None
        assert "active_entity_id" not in session

    def test_set_active_entite_inexistante_refusee(self, req, ids):
        assert Entity.set_active(987654321, user_id=ids["user_id"]) is None

    def test_for_user_anonyme_renvoie_requete_vide(self, req):
        assert Entity.for_user().all() == []

    def test_for_user_ne_rend_que_ses_entites(self, req, ids, entite_etrangere):
        from flask import session
        session["user_id"] = ids["user_id"]
        noms = [e.id for e in Entity.for_user()]
        assert ids["entity_id"] in noms
        assert entite_etrangere not in noms


class TestForActiveEntity:
    MODELES = [Data, Tool, Role, Link, User, TimeProject]

    @pytest.mark.parametrize("modele", MODELES, ids=lambda m: m.__name__)
    def test_sans_entite_active_requete_vide(self, req, modele):
        assert modele.for_active_entity().all() == []

    @pytest.mark.parametrize("modele", MODELES, ids=lambda m: m.__name__)
    def test_avec_entite_active_filtre_sur_elle(self, req, ids, modele):
        from flask import session
        session["user_id"] = ids["user_id"]
        session["active_entity_id"] = ids["entity_id"]
        lignes = modele.for_active_entity().all()
        assert all(l.entity_id == ids["entity_id"] for l in lignes)

    def test_data_et_lien_du_seed_remontent(self, req, ids):
        from flask import session
        session["user_id"] = ids["user_id"]
        session["active_entity_id"] = ids["entity_id"]
        assert "Donnée Test" in [d.name for d in Data.for_active_entity()]
        assert ids["link_id"] in [l.id for l in Link.for_active_entity()]


class TestLienExtremites:
    def test_source_et_cible_preferent_l_activite(self):
        l = Link(source_activity_id=1, source_data_id=2,
                 target_activity_id=3, target_data_id=4, type="x")
        assert (l.source_id, l.target_id) == (1, 3)

    def test_source_et_cible_retombent_sur_la_donnee(self):
        l = Link(source_data_id=2, target_data_id=4, type="x")
        assert (l.source_id, l.target_id) == (2, 4)

    def test_extremites_vides(self):
        l = Link(type="x")
        assert (l.source_id, l.target_id) == (None, None)


class TestAnalyseTempsRetards:
    @pytest.mark.parametrize("delay, hausse, attendu", [
        (10, 5, 15),
        (10, None, 10),
        (None, 5, 5),
        (None, None, 0),
        (0, 0, 0),
    ])
    def test_delay_gap(self, delay, hausse, attendu):
        assert TimeAnalysis(delay=delay, delay_increase=hausse).delay_gap == attendu

    @pytest.mark.parametrize("delay, hausse, attendu", [
        (10, 5, 50.0),
        (3, 1, 33.3),
        (10, None, 0),
        (None, 5, 0),
        (0, 5, 0),
    ])
    def test_delay_ratio(self, delay, hausse, attendu):
        assert TimeAnalysis(delay=delay, delay_increase=hausse).delay_ratio == attendu

    @pytest.mark.parametrize("recurrence, facteur", [
        ("journalier", 220), ("hebdo", 42), ("mensuel", 10.5),
        ("annuel", 1), ("inconnue", 0),
    ])
    def test_recurrence_factor(self, recurrence, facteur):
        assert TimeAnalysis(recurrence=recurrence).recurrence_factor == facteur


class TestCaptureChanges:
    def test_objet_non_mappe_renvoie_liste_vide(self):
        assert _capture_changes(object(), {"name": "Nom"}) == []

    def test_champ_inconnu_renvoie_liste_vide(self, app, ids):
        with app.app_context():
            e = db.session.get(Entity, ids["entity_id"])
            assert _capture_changes(e, {"champ_qui_n_existe_pas": "X"}) == []

    def test_modification_detectee_avant_apres(self, app, ids):
        with app.app_context():
            e = db.session.get(Entity, ids["entity_id"])
            e.description = "Changée T158"
            try:
                ch = _capture_changes(e, {"description": "Description"})
            finally:
                db.session.rollback()
            assert ch == [{"field": "Description",
                           "before": "Entité de test automatisée",
                           "after": "Changée T158"}]
