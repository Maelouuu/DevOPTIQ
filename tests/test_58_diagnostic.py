# tests/test_58_diagnostic.py
"""
Page : Diagnostic d'écart & plan d'accompagnement (/diagnostic — CDC 6)
Couverture :
  - GET  /diagnostic/families                              → familles de causes
  - GET  /diagnostic/<user_id>/<activity_id>/<data_id>      → état du diagnostic d'un résultat
  - POST /diagnostic/save                                    → validation des familles de causes
  - POST /diagnostic/plan                                    → plan d'accompagnement (repli sans clé IA)
"""
import json
import pytest

pytestmark = pytest.mark.diagnostic


# ---------------------------------------------------------------------------
# Fake client IA — couvre /diagnostic/plan "avec clé IA" (succès + exception),
# branches non exercées par les tests de repli sans clé.
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content=None, raise_exc=None):
        self.completions = _FakeChatCompletions(content, raise_exc)


class _FakeOpenAIClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_ai(monkeypatch, content=None, raise_exc=None):
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.diagnostic.openai_client_or_none",
        lambda: (fake_client, None),
    )


def _create_activity(app, entity_id, name="Activité Diagnostic Test 58"):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="Description")
        db.session.add(a)
        db.session.commit()
        return a.id


def _create_result_data(app, entity_id, activity_id, name="Résultat Diagnostic Test 58"):
    with app.app_context():
        from Code.models.models import Data
        from Code.extensions import db
        d = Data(entity_id=entity_id, name=name, type="flux",
                 producer_activity_id=activity_id, semantic_nature="RESULT",
                 minimum_performance_text="Standard minimal")
        db.session.add(d)
        db.session.commit()
        return d.id


def _create_savoir_faire(app, activity_id, description="Régler la machine Test 58"):
    with app.app_context():
        from Code.models.models import SavoirFaire
        from Code.extensions import db
        sf = SavoirFaire(activity_id=activity_id, description=description)
        db.session.add(sf)
        db.session.commit()
        return sf.id


def _link_capability(app, entity_id, activity_id, data_id, item_type, item_id, required_level=2):
    with app.app_context():
        from Code.models.models import ResultCapabilityLink
        from Code.extensions import db
        lk = ResultCapabilityLink(entity_id=entity_id, activity_id=activity_id, data_id=data_id,
                                   item_type=item_type, item_id=item_id, required_level=required_level,
                                   source="MANUAL")
        db.session.add(lk)
        db.session.commit()
        return lk.id


def _cleanup(app, activity_id):
    with app.app_context():
        from Code.models.models import (Activities, Data, SavoirFaire, ResultCapabilityLink,
                                        ResultDiagnostic, CompetencyEvaluation)
        from Code.extensions import db
        ResultDiagnostic.query.filter_by(activity_id=activity_id).delete()
        ResultCapabilityLink.query.filter_by(activity_id=activity_id).delete()
        CompetencyEvaluation.query.filter_by(activity_id=activity_id).delete()
        SavoirFaire.query.filter_by(activity_id=activity_id).delete()
        Data.query.filter_by(producer_activity_id=activity_id).delete()
        a = Activities.query.get(activity_id)
        if a:
            db.session.delete(a)
        db.session.commit()


def _set_reference_level(app, user_id, activity_id, data_id, mastery_level, eval_number="2"):
    """Crée une évaluation VALIDANTE (Garant/Manager) du résultat, consommée par _reference_level()."""
    with app.app_context():
        from Code.models.models import CompetencyEvaluation
        from Code.extensions import db
        ev = CompetencyEvaluation(user_id=user_id, activity_id=activity_id, item_id=data_id,
                                   item_type="activity_results", eval_number=eval_number,
                                   note="x", mastery_level=mastery_level)
        db.session.add(ev)
        db.session.commit()


def _create_role_with_required_level(app, activity_id, required_mastery_level, name="Rôle Diagnostic Test 58"):
    with app.app_context():
        from Code.models.models import Role, activity_roles
        from Code.extensions import db
        role = Role(name=name)
        db.session.add(role)
        db.session.flush()
        rid = role.id
        db.session.execute(activity_roles.insert().values(
            activity_id=activity_id, role_id=rid, status="active",
            required_mastery_level=required_mastery_level))
        db.session.commit()
        return rid


def _cleanup_role(app, activity_id, role_id):
    with app.app_context():
        from Code.models.models import Role, activity_roles
        from Code.extensions import db
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id == activity_id, activity_roles.c.role_id == role_id))
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
        db.session.commit()


class TestFamilies:

    def test_families_returns_three_codes(self, auth_client):
        r = auth_client.get("/diagnostic/families")
        assert r.status_code == 200
        codes = {f["code"] for f in r.get_json()["families"]}
        assert codes == {"WORK_ARCHITECTURE", "ABILITY_TO_ACT", "EXECUTION_CONDITIONS"}


class TestGetDiagnostic:

    def test_not_a_result_returns_400(self, auth_client, ids):
        r = auth_client.get(f"/diagnostic/{ids['user_id']}/{ids['activity_id']}/999999")
        assert r.status_code == 400
        assert r.get_json()["error"] == "not_a_result"

    def test_no_diagnostic_saved_defaults_empty(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["families"] == []
            assert data["note"] == ""
            assert data["status"]["code"] == "not_assessed"
            assert data["individual_family"] == "ABILITY_TO_ACT"
            assert data["capabilities"] == []
        finally:
            _cleanup(app, aid)

    def test_includes_linked_capability_with_gap(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        sfid = _create_savoir_faire(app, aid)
        _link_capability(app, ids["entity_id"], aid, did, "SAVOIR_FAIRE", sfid, required_level=3)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            data = r.get_json()
            assert len(data["capabilities"]) == 1
            cap = data["capabilities"][0]
            assert cap["item_id"] == sfid
            assert cap["required_level"] == 3
            assert cap["demonstrated_level"] is None
            assert cap["gap"] is None
        finally:
            _cleanup(app, aid)

    def test_status_autonomy_not_demonstrated_below_level_2(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _set_reference_level(app, ids["user_id"], aid, did, mastery_level=1)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            data = r.get_json()
            assert data["demonstrated_level"] == 1
            assert data["status"]["code"] == "autonomy_not_demonstrated"
        finally:
            _cleanup(app, aid)

    def test_status_development_gap_below_required(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _set_reference_level(app, ids["user_id"], aid, did, mastery_level=2)
        rid = _create_role_with_required_level(app, aid, required_mastery_level=3)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}?role_id={rid}")
            data = r.get_json()
            assert data["demonstrated_level"] == 2
            assert data["required_level"] == 3
            assert data["status"]["code"] == "development_gap"
        finally:
            _cleanup_role(app, aid, rid)
            _cleanup(app, aid)

    def test_status_met_when_demonstrated_covers_required(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _set_reference_level(app, ids["user_id"], aid, did, mastery_level=3)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            data = r.get_json()
            assert data["demonstrated_level"] == 3
            assert data["status"]["code"] == "met"
        finally:
            _cleanup(app, aid)

    def test_capability_demonstrated_level_from_valid_evaluation(self, auth_client, app, ids):
        """Notes parsables en entier → meilleur niveau retenu (max)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        sfid = _create_savoir_faire(app, aid)
        _link_capability(app, ids["entity_id"], aid, did, "SAVOIR_FAIRE", sfid, required_level=3)
        with app.app_context():
            from Code.models.models import CompetencyEvaluation
            from Code.extensions import db
            db.session.add_all([
                CompetencyEvaluation(user_id=ids["user_id"], activity_id=aid, item_id=sfid,
                                     item_type="savoir_faires", eval_number="0", note="1"),
                CompetencyEvaluation(user_id=ids["user_id"], activity_id=aid, item_id=sfid,
                                     item_type="savoir_faires", eval_number="1", note="2"),
                CompetencyEvaluation(user_id=ids["user_id"], activity_id=aid, item_id=sfid,
                                     item_type="savoir_faires", eval_number="2", note="non-numerique"),
            ])
            db.session.commit()
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            cap = r.get_json()["capabilities"][0]
            assert cap["demonstrated_level"] == 2
            assert cap["gap"] == -1
        finally:
            _cleanup(app, aid)

    def test_capability_with_unrecognized_item_type_has_no_demonstrated_level(self, auth_client, app, ids):
        """item_type inconnu de EVAL_ITEM_TYPE → demonstrated_level=None, label=None (pas de crash)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _link_capability(app, ids["entity_id"], aid, did, "BOGUS_TYPE", 999999, required_level=2)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            cap = r.get_json()["capabilities"][0]
            assert cap["demonstrated_level"] is None
            assert cap["label"] is None
            assert cap["gap"] is None
        finally:
            _cleanup(app, aid)

    def test_capability_with_missing_item_has_no_label(self, auth_client, app, ids):
        """item_type valide mais item_id inexistant → label=None (pas de crash)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _link_capability(app, ids["entity_id"], aid, did, "SAVOIR_FAIRE", 999999, required_level=2)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            cap = r.get_json()["capabilities"][0]
            assert cap["label"] is None
        finally:
            _cleanup(app, aid)


class TestSaveDiagnostic:

    def test_missing_fields_returns_400(self, auth_client):
        r = auth_client.post(
            "/diagnostic/save",
            data=json.dumps({"user_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_save_filters_unknown_family_codes(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/diagnostic/save",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                                  "families": ["ABILITY_TO_ACT", "BOGUS_FAMILY"], "note": "Observation"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["ok"] is True
            assert data["families"] == ["ABILITY_TO_ACT"]

            with app.app_context():
                from Code.models.models import ResultDiagnostic
                row = ResultDiagnostic.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, data_id=did).first()
                assert json.loads(row.families) == ["ABILITY_TO_ACT"]
                assert row.note == "Observation"
        finally:
            _cleanup(app, aid)

    def test_save_upserts_same_row(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            payload = lambda fams: json.dumps({"user_id": ids["user_id"], "activity_id": aid,
                                                "data_id": did, "families": fams})
            auth_client.post("/diagnostic/save", data=payload(["WORK_ARCHITECTURE"]), content_type="application/json")
            auth_client.post("/diagnostic/save", data=payload(["EXECUTION_CONDITIONS"]), content_type="application/json")
            with app.app_context():
                from Code.models.models import ResultDiagnostic
                rows = ResultDiagnostic.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, data_id=did).all()
                assert len(rows) == 1
                assert json.loads(rows[0].families) == ["EXECUTION_CONDITIONS"]
        finally:
            _cleanup(app, aid)


class TestGeneratePlan:

    def test_missing_fields_returns_400(self, auth_client):
        r = auth_client.post(
            "/diagnostic/plan",
            data=json.dumps({"user_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_no_individual_family_returns_no_plan(self, auth_client, app, ids):
        """Écart classé 'Architecture du travail' → pas de plan de développement individuel (CDC 6.8)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            auth_client.post(
                "/diagnostic/save",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                                  "families": ["WORK_ARCHITECTURE"]}),
                content_type="application/json",
            )
            r = auth_client.post(
                "/diagnostic/plan",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["plan"] is None
            assert data["no_individual_plan"] is True
        finally:
            _cleanup(app, aid)

    def test_individual_family_no_ai_key_returns_explicit_source(self, auth_client, app, ids):
        """CDC 6.8 : famille ABILITY_TO_ACT → tentative de plan, mais sans clé IA en test, repli
        explicite (jamais de 500)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            auth_client.post(
                "/diagnostic/save",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                                  "families": ["ABILITY_TO_ACT"]}),
                content_type="application/json",
            )
            r = auth_client.post(
                "/diagnostic/plan",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["plan"] is None
            assert data["source"] != "AI"
            assert "context" in data
        finally:
            _cleanup(app, aid)

    def test_families_from_payload_used_when_not_saved(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/diagnostic/plan",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                                  "families": ["ABILITY_TO_ACT"]}),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["source"] != "AI"
        finally:
            _cleanup(app, aid)

    def test_plan_with_ai_key_returns_generated_plan(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _mock_ai(monkeypatch, content=json.dumps({"plan": ["Former sur X", "Tutorat 2 semaines"]}))
        try:
            r = auth_client.post(
                "/diagnostic/plan",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                                  "families": ["ABILITY_TO_ACT"]}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["source"] == "AI"
            assert data["plan"] == ["Former sur X", "Tutorat 2 semaines"]
            assert data["context"]["result"] == "Résultat Diagnostic Test 58"
        finally:
            _cleanup(app, aid)

    def test_plan_ai_exception_returns_error_source(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _mock_ai(monkeypatch, raise_exc=RuntimeError("ai down"))
        try:
            r = auth_client.post(
                "/diagnostic/plan",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                                  "families": ["ABILITY_TO_ACT"]}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["plan"] is None
            assert data["source"] == "error"
            assert "ai down" in data["error"]
            assert "context" in data
        finally:
            _cleanup(app, aid)
