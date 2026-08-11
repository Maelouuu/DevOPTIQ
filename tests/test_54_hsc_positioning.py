# tests/test_54_hsc_positioning.py
"""
Page : Auto-positionnement HSC (/hsc — CDC 7)
Couverture :
  - GET  /hsc/levels                          → libellés des 4 niveaux HSC
  - GET  /hsc/descriptors/<hsc_name>           → descripteurs comportementaux par niveau
  - POST /hsc/descriptors                      → upsert d'un descripteur
  - POST /hsc/position                         → auto-positionnement (repli sans clé IA)
"""
import json
import pytest

pytestmark = pytest.mark.hsc_positioning


def _cleanup_descriptors(app, hsc_name):
    with app.app_context():
        from Code.models.models import HscLevelDescriptor
        from Code.extensions import db
        HscLevelDescriptor.query.filter_by(hsc_name=hsc_name).delete()
        db.session.commit()


class TestHscLevels:

    def test_levels_returns_four_levels(self, auth_client):
        r = auth_client.get("/hsc/levels")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data["levels"].keys()) == {"1", "2", "3", "4"}

    def test_levels_default_language_french(self, auth_client):
        r = auth_client.get("/hsc/levels")
        data = r.get_json()
        assert data["levels"]["4"] == "Expertise"

    def test_levels_accessible_without_auth(self, client):
        r = client.get("/hsc/levels")
        assert r.status_code == 200

    def test_levels_english_language(self, auth_client):
        with auth_client.session_transaction() as s:
            s["lang"] = "en"
        r = auth_client.get("/hsc/levels")
        data = r.get_json()
        assert data["levels"]["4"] == "Expert"
        with auth_client.session_transaction() as s:
            s["lang"] = "fr"


class TestHscDescriptors:

    def test_descriptors_empty_for_unknown_hsc(self, auth_client):
        r = auth_client.get("/hsc/descriptors/Inconnue")
        assert r.status_code == 200
        data = r.get_json()
        assert data["hsc_name"] == "Inconnue"
        assert data["descriptors"] == []

    def test_upsert_descriptor_creates_row(self, auth_client, app):
        name = "Auto-organisation Test 54"
        try:
            r = auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({
                    "hsc_name": name, "level": 2,
                    "descriptor_fr": "Organise ses priorités seul.",
                    "observable_behaviors_fr": "Planifie sa semaine sans rappel.",
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["ok"] is True
            assert isinstance(data["id"], int)

            r2 = auth_client.get(f"/hsc/descriptors/{name}")
            data2 = r2.get_json()
            assert len(data2["descriptors"]) == 1
            d = data2["descriptors"][0]
            assert d["level"] == 2
            assert d["level_label"] == "Acquisition"
            assert d["descriptor"] == "Organise ses priorités seul."
        finally:
            _cleanup_descriptors(app, name)

    def test_upsert_descriptor_missing_name_returns_400(self, auth_client):
        r = auth_client.post(
            "/hsc/descriptors",
            data=json.dumps({"level": 1}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid"

    def test_upsert_descriptor_invalid_level_returns_400(self, auth_client):
        r = auth_client.post(
            "/hsc/descriptors",
            data=json.dumps({"hsc_name": "Coopération", "level": 9}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_upsert_descriptor_twice_updates_not_duplicates(self, auth_client, app):
        name = "Ecoute Active Test 54"
        try:
            auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({"hsc_name": name, "level": 1, "descriptor_fr": "Première version."}),
                content_type="application/json",
            )
            auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({"hsc_name": name, "level": 1, "descriptor_fr": "Version corrigée."}),
                content_type="application/json",
            )
            r = auth_client.get(f"/hsc/descriptors/{name}")
            data = r.get_json()
            assert len(data["descriptors"]) == 1
            assert data["descriptors"][0]["descriptor"] == "Version corrigée."
        finally:
            _cleanup_descriptors(app, name)

    def test_upsert_descriptor_english_fields_used_when_lang_en(self, auth_client, app):
        name = "Rigueur Test 54 EN"
        try:
            auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({
                    "hsc_name": name, "level": 3,
                    "descriptor_fr": "Version française.",
                    "descriptor_en": "English version.",
                }),
                content_type="application/json",
            )
            with auth_client.session_transaction() as s:
                s["lang"] = "en"
            r = auth_client.get(f"/hsc/descriptors/{name}")
            data = r.get_json()
            assert data["descriptors"][0]["descriptor"] == "English version."
            with auth_client.session_transaction() as s:
                s["lang"] = "fr"
        finally:
            _cleanup_descriptors(app, name)

    def test_descriptor_created_for_other_entity_not_visible(self, auth_client, app, ids):
        """Un descripteur créé pour une entité active B n'est pas visible depuis l'entité A
        (sauf s'il est global, entity_id NULL). Force la session sur un ID connu (ids fixture)
        plutôt que de faire confiance à l'état ambiant : d'autres tests peuvent laisser
        active_entity_id à None dans la session partagée (scope=session)."""
        name = "Confidentialité Test 54"
        from Code.models.models import Entity, User
        from Code.extensions import db
        with app.app_context():
            user = User.query.filter_by(email="test@devoptiq.com").first()
            other = Entity(name="HSC Autre Entité Test 54", owner_id=user.id)
            db.session.add(other)
            db.session.commit()
            other_id = other.id
        try:
            with auth_client.session_transaction() as s:
                s["active_entity_id"] = other_id
            auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({"hsc_name": name, "level": 1, "descriptor_fr": "Spécifique à Autre Entité."}),
                content_type="application/json",
            )
            with auth_client.session_transaction() as s:
                s["active_entity_id"] = ids["entity_id"]
            r = auth_client.get(f"/hsc/descriptors/{name}")
            assert r.get_json()["descriptors"] == []
        finally:
            _cleanup_descriptors(app, name)
            with app.app_context():
                Entity.query.filter_by(id=other_id).delete()
                db.session.commit()
            with auth_client.session_transaction() as s:
                s["active_entity_id"] = ids["entity_id"]

    def test_multiple_levels_returned_sorted(self, auth_client, app):
        name = "Adaptabilité Test 54"
        try:
            for lvl in (3, 1, 2):
                auth_client.post(
                    "/hsc/descriptors",
                    data=json.dumps({"hsc_name": name, "level": lvl, "descriptor_fr": f"Niveau {lvl}."}),
                    content_type="application/json",
                )
            r = auth_client.get(f"/hsc/descriptors/{name}")
            levels = [d["level"] for d in r.get_json()["descriptors"]]
            assert levels == [1, 2, 3]
        finally:
            _cleanup_descriptors(app, name)


class TestHscPosition:

    def test_position_missing_name_returns_400(self, auth_client):
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"responses": ["a"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid"

    def test_position_without_ai_key_returns_null_proposal(self, auth_client):
        """Sans clé OpenAI configurée, repli : proposal=None, source explicite (jamais d'erreur 500)."""
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Auto-organisation", "responses": ["Je planifie mes tâches chaque lundi."]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "proposal" in data
        assert "source" in data

    def test_position_accepts_empty_responses(self, auth_client):
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Coopération"}),
            content_type="application/json",
        )
        assert r.status_code == 200
