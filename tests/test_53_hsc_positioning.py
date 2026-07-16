# tests/test_53_hsc_positioning.py
"""
Page : Auto-positionnement et évaluation des HSC (/hsc)
CDC 7 (V1.1) — Positionnement à partir de comportements observables ; l'IA propose un
niveau probable, seul un évaluateur habilité valide. Sans OPENAI_API_KEY (env. de test),
/hsc/position doit retourner 200 + proposal=None + source='no_ai' (jamais planter).
Couvre : /hsc/levels, /hsc/descriptors (GET/POST), /hsc/position.
"""
import pytest
import json
from Code.extensions import db
from Code.models.models import Entity, HscLevelDescriptor

pytestmark = pytest.mark.hsc_positioning


@pytest.fixture()
def entity(app):
    with app.app_context():
        ent = Entity(name="HscPositioningECo")
        db.session.add(ent)
        db.session.commit()
        eid = ent.id
    yield eid
    with app.app_context():
        HscLevelDescriptor.query.filter_by(entity_id=eid).delete()
        Entity.query.filter_by(id=eid).delete()
        db.session.commit()


def _sess(client, entity_id, lang="fr"):
    with client.session_transaction() as s:
        s["active_entity_id"] = entity_id
        s["lang"] = lang


# ===========================================================================
# 1. GET /hsc/levels
# ===========================================================================

class TestLevels:

    def test_levels_returns_four_levels_fr(self, client):
        with client.session_transaction() as s:
            s["lang"] = "fr"
        r = client.get("/hsc/levels")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["levels"] == {"1": "Aptitude", "2": "Acquisition", "3": "Maîtrise", "4": "Expertise"}

    def test_levels_returns_four_levels_en(self, client):
        with client.session_transaction() as s:
            s["lang"] = "en"
        r = client.get("/hsc/levels")
        body = json.loads(r.data)
        assert body["levels"]["1"] == "Basic"
        assert body["levels"]["4"] == "Expert"


# ===========================================================================
# 2. POST /hsc/descriptors — création / mise à jour d'un descripteur
# ===========================================================================

class TestUpsertDescriptor:

    def test_create_descriptor_returns_id(self, client, entity):
        _sess(client, entity)
        r = client.post(
            "/hsc/descriptors",
            data=json.dumps({
                "hsc_name": "Adaptabilité", "level": 2,
                "descriptor_fr": "S'ajuste à un changement de contexte connu.",
                "observable_behaviors_fr": "Modifie sa méthode sans qu'on le lui demande.",
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["ok"] is True
        assert "id" in body

    def test_upsert_same_hsc_and_level_updates_existing(self, app, client, entity):
        _sess(client, entity)
        r1 = client.post("/hsc/descriptors", data=json.dumps(
            {"hsc_name": "Rigueur", "level": 1, "descriptor_fr": "Premier jet"}),
            content_type="application/json")
        id1 = json.loads(r1.data)["id"]
        r2 = client.post("/hsc/descriptors", data=json.dumps(
            {"hsc_name": "Rigueur", "level": 1, "descriptor_fr": "Version corrigée"}),
            content_type="application/json")
        id2 = json.loads(r2.data)["id"]
        assert id1 == id2
        with app.app_context():
            row = HscLevelDescriptor.query.get(id1)
            assert row.descriptor_fr == "Version corrigée"

    def test_missing_hsc_name_returns_400(self, client, entity):
        _sess(client, entity)
        r = client.post("/hsc/descriptors", data=json.dumps({"level": 2}), content_type="application/json")
        assert r.status_code == 400

    def test_invalid_level_returns_400(self, client, entity):
        _sess(client, entity)
        r = client.post("/hsc/descriptors", data=json.dumps(
            {"hsc_name": "Curiosité", "level": 9}), content_type="application/json")
        assert r.status_code == 400

    def test_blank_optional_field_stored_as_none(self, app, client, entity):
        _sess(client, entity)
        r = client.post("/hsc/descriptors", data=json.dumps(
            {"hsc_name": "Écoute", "level": 3, "descriptor_fr": "   "}), content_type="application/json")
        did = json.loads(r.data)["id"]
        with app.app_context():
            row = HscLevelDescriptor.query.get(did)
            assert row.descriptor_fr is None


# ===========================================================================
# 3. GET /hsc/descriptors/<hsc_name>
# ===========================================================================

class TestGetDescriptors:

    def test_get_descriptors_returns_saved_levels(self, client, entity):
        _sess(client, entity)
        client.post("/hsc/descriptors", data=json.dumps(
            {"hsc_name": "Coopération", "level": 1, "descriptor_fr": "Niveau 1"}),
            content_type="application/json")
        client.post("/hsc/descriptors", data=json.dumps(
            {"hsc_name": "Coopération", "level": 2, "descriptor_fr": "Niveau 2"}),
            content_type="application/json")
        r = client.get("/hsc/descriptors/Coopération")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["hsc_name"] == "Coopération"
        levels = [d["level"] for d in body["descriptors"]]
        assert levels == [1, 2]
        assert body["descriptors"][0]["descriptor"] == "Niveau 1"
        assert body["descriptors"][0]["level_label"] == "Aptitude"

    def test_get_descriptors_unknown_hsc_returns_empty_list(self, client, entity):
        _sess(client, entity)
        r = client.get("/hsc/descriptors/Inconnue")
        assert r.status_code == 200
        assert json.loads(r.data)["descriptors"] == []

    def test_global_descriptor_visible_without_active_entity(self, app, client):
        """Un descripteur sans entity_id (référentiel global) est visible même sans entité active."""
        with app.app_context():
            row = HscLevelDescriptor(entity_id=None, hsc_name="Global HSC Test", level=4,
                                     descriptor_fr="Référentiel global")
            db.session.add(row)
            db.session.commit()
            row_id = row.id
        r = client.get("/hsc/descriptors/Global HSC Test")
        body = json.loads(r.data)
        assert len(body["descriptors"]) == 1
        assert body["descriptors"][0]["descriptor"] == "Référentiel global"
        with app.app_context():
            HscLevelDescriptor.query.filter_by(id=row_id).delete()
            db.session.commit()


# ===========================================================================
# 4. POST /hsc/position — auto-positionnement (fallback sans clé IA)
# ===========================================================================

class TestPosition:

    def test_position_without_openai_key_returns_no_ai(self, client):
        r = client.post("/hsc/position", data=json.dumps({
            "hsc_name": "Adaptabilité",
            "responses": ["J'ai changé de méthode quand le contexte a évolué."],
        }), content_type="application/json")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["proposal"] is None
        assert body["source"] != "AI"

    def test_position_missing_hsc_name_returns_400(self, client):
        r = client.post("/hsc/position", data=json.dumps({"responses": []}), content_type="application/json")
        assert r.status_code == 400
