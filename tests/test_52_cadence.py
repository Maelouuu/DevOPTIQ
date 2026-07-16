# tests/test_52_cadence.py
"""
Page : Cadences et cohérence des rythmes (/cadence)
CDC 5 (V1.1) — LECTURE SEULE : détecte les écarts de rythme entre une donnée et l'activité
aval qui la consomme, sans jamais corriger. Vocabulaire imposé : « point de vigilance ».
Couvre : /cadence/codes, /cadence/activity/<id>, /cadence/data/<id>, /cadence/consistency.
"""
import pytest
import json
from Code.extensions import db
from Code.models.models import Entity, Activities, Data, Link

pytestmark = pytest.mark.cadence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def carto(app, ids):
    """Entité dédiée, propriétaire = utilisateur de test (pour Entity.get_active_id()).
    Une activité aval + une donnée amont reliées par un Link source_data → target_activity."""
    with app.app_context():
        ent = Entity(name="CadenceECo", owner_id=ids["user_id"])
        db.session.add(ent)
        db.session.flush()
        act = Activities(entity_id=ent.id, name="Facturer le client", shape_id="cad_a1")
        data = Data(entity_id=ent.id, name="Référentiel tarifaire", type="nourrissante")
        db.session.add_all([act, data])
        db.session.flush()
        link = Link(entity_id=ent.id, source_data_id=data.id, target_activity_id=act.id, type="nourrissante")
        db.session.add(link)
        db.session.commit()
        result = {"entity_id": ent.id, "activity_id": act.id, "data_id": data.id}
    yield result
    with app.app_context():
        Link.query.filter_by(entity_id=result["entity_id"]).delete()
        Activities.query.filter_by(id=result["activity_id"]).delete()
        Data.query.filter_by(id=result["data_id"]).delete()
        Entity.query.filter_by(id=result["entity_id"]).delete()
        db.session.commit()


def _sess(client, user_id, entity_id, lang="fr"):
    with client.session_transaction() as s:
        s["user_id"] = user_id
        s["active_entity_id"] = entity_id
        s["lang"] = lang


# ===========================================================================
# 1. GET /cadence/codes
# ===========================================================================

class TestCadenceCodes:

    def test_codes_returns_all_cadences_fr(self, client):
        with client.session_transaction() as s:
            s["lang"] = "fr"
        r = client.get("/cadence/codes")
        assert r.status_code == 200
        body = json.loads(r.data)
        codes = {c["code"] for c in body["cadences"]}
        assert codes == {"EVENT", "CONTINUOUS", "DAILY", "WEEKLY", "MONTHLY",
                          "QUARTERLY", "YEARLY", "PROJECT", "OTHER"}

    def test_codes_label_localized_en(self, client):
        with client.session_transaction() as s:
            s["lang"] = "en"
        r = client.get("/cadence/codes")
        body = json.loads(r.data)
        daily = next(c for c in body["cadences"] if c["code"] == "DAILY")
        assert daily["label"] == "Daily"
        assert daily["badge"] == "D"

    def test_codes_label_localized_fr_explicit(self, client):
        with client.session_transaction() as s:
            s["lang"] = "fr"
        r = client.get("/cadence/codes")
        body = json.loads(r.data)
        daily = next(c for c in body["cadences"] if c["code"] == "DAILY")
        assert daily["label"] == "Journalière"


# ===========================================================================
# 2. POST /cadence/activity/<activity_id>
# ===========================================================================

class TestSetActivityCadence:

    def test_set_valid_code_persists(self, app, client, carto):
        r = client.post(
            f"/cadence/activity/{carto['activity_id']}",
            data=json.dumps({"cadence_code": "WEEKLY", "cadence_details": "Chaque lundi"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True
        with app.app_context():
            a = Activities.query.get(carto["activity_id"])
            assert a.cadence_code == "WEEKLY"
            assert a.cadence_details == "Chaque lundi"

    def test_set_details_blank_becomes_none(self, app, client, carto):
        r = client.post(
            f"/cadence/activity/{carto['activity_id']}",
            data=json.dumps({"cadence_code": "DAILY", "cadence_details": "   "}),
            content_type="application/json",
        )
        assert r.status_code == 200
        with app.app_context():
            a = Activities.query.get(carto["activity_id"])
            assert a.cadence_details is None

    def test_set_invalid_code_returns_400(self, client, carto):
        r = client.post(
            f"/cadence/activity/{carto['activity_id']}",
            data=json.dumps({"cadence_code": "NOT_A_CODE"}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert json.loads(r.data)["error"] == "invalid_code"

    def test_set_null_code_clears_cadence(self, app, client, carto):
        client.post(f"/cadence/activity/{carto['activity_id']}",
                    data=json.dumps({"cadence_code": "MONTHLY"}), content_type="application/json")
        r = client.post(
            f"/cadence/activity/{carto['activity_id']}",
            data=json.dumps({"cadence_code": None}),
            content_type="application/json",
        )
        assert r.status_code == 200
        with app.app_context():
            a = Activities.query.get(carto["activity_id"])
            assert a.cadence_code is None

    def test_set_activity_not_found_returns_404(self, client):
        r = client.post(
            "/cadence/activity/999999",
            data=json.dumps({"cadence_code": "DAILY"}),
            content_type="application/json",
        )
        assert r.status_code == 404


# ===========================================================================
# 3. POST /cadence/data/<data_id>
# ===========================================================================

class TestSetDataCadence:

    def test_set_valid_code_persists(self, app, client, carto):
        r = client.post(
            f"/cadence/data/{carto['data_id']}",
            data=json.dumps({"update_cadence_code": "QUARTERLY", "max_age_hours": 2160}),
            content_type="application/json",
        )
        assert r.status_code == 200
        with app.app_context():
            d = Data.query.get(carto["data_id"])
            assert d.update_cadence_code == "QUARTERLY"
            assert d.max_age_hours == 2160

    def test_set_invalid_code_returns_400(self, client, carto):
        r = client.post(
            f"/cadence/data/{carto['data_id']}",
            data=json.dumps({"update_cadence_code": "BOGUS"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_set_data_not_found_returns_404(self, client):
        r = client.post(
            "/cadence/data/999999",
            data=json.dumps({"update_cadence_code": "DAILY"}),
            content_type="application/json",
        )
        assert r.status_code == 404


# ===========================================================================
# 4. GET /cadence/consistency
# ===========================================================================

class TestConsistency:

    def test_no_warning_when_cadences_not_set(self, client, carto, ids):
        _sess(client, ids["user_id"], carto["entity_id"])
        r = client.get("/cadence/consistency")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["warnings"] == []
        assert body["count"] == 0

    def test_no_warning_when_data_faster_than_activity(self, client, carto, ids):
        client.post(f"/cadence/data/{carto['data_id']}",
                    data=json.dumps({"update_cadence_code": "DAILY"}), content_type="application/json")
        client.post(f"/cadence/activity/{carto['activity_id']}",
                    data=json.dumps({"cadence_code": "WEEKLY"}), content_type="application/json")
        _sess(client, ids["user_id"], carto["entity_id"])
        r = client.get("/cadence/consistency")
        assert json.loads(r.data)["warnings"] == []

    def test_warning_when_data_slower_than_activity(self, client, carto, ids):
        """Donnée mise à jour trimestriellement alors que l'activité aval fonctionne au quotidien."""
        client.post(f"/cadence/data/{carto['data_id']}",
                    data=json.dumps({"update_cadence_code": "QUARTERLY"}), content_type="application/json")
        client.post(f"/cadence/activity/{carto['activity_id']}",
                    data=json.dumps({"cadence_code": "DAILY"}), content_type="application/json")
        _sess(client, ids["user_id"], carto["entity_id"])
        r = client.get("/cadence/consistency")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["count"] == 1
        w = body["warnings"][0]
        assert w["source_data_id"] == carto["data_id"]
        assert w["target_activity_id"] == carto["activity_id"]
        assert w["severity"] == "watch"
        assert "vigilance" not in w  # champ non présent tel quel, mais le vocabulaire est dans finding/optiq_question
        assert "?" in w["optiq_question"]

    def test_no_warning_for_event_or_project_cadences(self, client, carto, ids):
        """EVENT/PROJECT/OTHER n'ont pas de rank comparable → jamais de point de vigilance."""
        client.post(f"/cadence/data/{carto['data_id']}",
                    data=json.dumps({"update_cadence_code": "EVENT"}), content_type="application/json")
        client.post(f"/cadence/activity/{carto['activity_id']}",
                    data=json.dumps({"cadence_code": "DAILY"}), content_type="application/json")
        _sess(client, ids["user_id"], carto["entity_id"])
        r = client.get("/cadence/consistency")
        assert json.loads(r.data)["warnings"] == []
