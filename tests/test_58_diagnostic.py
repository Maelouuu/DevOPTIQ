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
from datetime import datetime

import pytest

pytestmark = pytest.mark.diagnostic


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


def _create_reference_eval(app, user_id, activity_id, data_id, mastery_level, eval_number="1"):
    """Évaluation de référence (Garant/Manager) sur le RÉSULTAT lui-même —
    alimente _reference_level() (Code/routes/mastery.py)."""
    with app.app_context():
        from Code.models.models import CompetencyEvaluation
        from Code.extensions import db
        ev = CompetencyEvaluation(user_id=user_id, activity_id=activity_id,
                                  item_type="activity_results", item_id=data_id,
                                  eval_number=eval_number, note="x", mastery_level=mastery_level,
                                  evaluated_at=datetime.utcnow())
        db.session.add(ev)
        db.session.commit()
        return ev.id


def _set_required_mastery_level(app, activity_id, role_id, level):
    with app.app_context():
        from Code.models.models import activity_roles
        from Code.extensions import db
        db.session.execute(activity_roles.update().where(
            (activity_roles.c.activity_id == activity_id) &
            (activity_roles.c.role_id == role_id)).values(required_mastery_level=level))
        db.session.commit()


def _create_role_garant(app, entity_id, activity_id, name):
    with app.app_context():
        from Code.models.models import Role, activity_roles
        from Code.extensions import db
        role = Role(name=name, entity_id=entity_id)
        db.session.add(role)
        db.session.commit()
        rid = role.id
        db.session.execute(activity_roles.insert().values(
            activity_id=activity_id, role_id=rid, status="Garant"))
        db.session.commit()
        return rid


def _create_capability_eval(app, user_id, activity_id, item_type, item_id, note, eval_number):
    with app.app_context():
        from Code.models.models import CompetencyEvaluation
        from Code.extensions import db
        ev = CompetencyEvaluation(user_id=user_id, activity_id=activity_id,
                                  item_type=item_type, item_id=item_id,
                                  eval_number=eval_number, note=note)
        db.session.add(ev)
        db.session.commit()
        return ev.id


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
        """Niveau démontré < 2 → 'autonomy_not_demonstrated' (CDC 6.5)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _create_reference_eval(app, ids["user_id"], aid, did, mastery_level=1, eval_number="1")
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            data = r.get_json()
            assert data["demonstrated_level"] == 1
            assert data["status"]["code"] == "autonomy_not_demonstrated"
        finally:
            _cleanup(app, aid)

    def test_status_development_gap_below_required_level(self, auth_client, app, ids):
        """Niveau démontré >= 2 mais < niveau requis pour le rôle → 'development_gap'."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        rid = _create_role_garant(app, ids["entity_id"], aid, "Role Diagnostic Gap")
        _set_required_mastery_level(app, aid, rid, 4)
        _create_reference_eval(app, ids["user_id"], aid, did, mastery_level=2, eval_number="1")
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}?role_id={rid}")
            data = r.get_json()
            assert data["demonstrated_level"] == 2
            assert data["required_level"] == 4
            assert data["status"]["code"] == "development_gap"
        finally:
            _cleanup(app, aid)

    def test_status_met_when_demonstrated_reaches_required(self, auth_client, app, ids):
        """Niveau démontré >= niveau requis → 'met'."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        rid = _create_role_garant(app, ids["entity_id"], aid, "Role Diagnostic Met")
        _set_required_mastery_level(app, aid, rid, 2)
        _create_reference_eval(app, ids["user_id"], aid, did, mastery_level=3, eval_number="1")
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}?role_id={rid}")
            data = r.get_json()
            assert data["demonstrated_level"] == 3
            assert data["status"]["code"] == "met"
        finally:
            _cleanup(app, aid)

    def test_capability_demonstrated_ignores_non_numeric_note_and_keeps_max(self, auth_client, app, ids):
        """Plusieurs évaluations sur le même S/SF : une note non numérique est
        ignorée, le niveau démontré retenu est le MAX des notes valides."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        sfid = _create_savoir_faire(app, aid)
        _link_capability(app, ids["entity_id"], aid, did, "SAVOIR_FAIRE", sfid, required_level=3)
        _create_capability_eval(app, ids["user_id"], aid, "savoir_faires", sfid, note="abc", eval_number="1")
        _create_capability_eval(app, ids["user_id"], aid, "savoir_faires", sfid, note="2", eval_number="2")
        _create_capability_eval(app, ids["user_id"], aid, "savoir_faires", sfid, note="4", eval_number="3")
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            cap = r.get_json()["capabilities"][0]
            assert cap["demonstrated_level"] == 4
            assert cap["gap"] == 1
        finally:
            _cleanup(app, aid)

    def test_capability_unknown_item_type_has_no_demonstrated_level_or_label(self, auth_client, app, ids):
        """Un lien avec un item_type inconnu (hors SAVOIR/SAVOIR_FAIRE/HSC) ne
        fait pas planter le diagnostic : niveau démontré et libellé restent None."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _link_capability(app, ids["entity_id"], aid, did, "UNKNOWN_TYPE", 12345, required_level=2)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            assert r.status_code == 200
            cap = r.get_json()["capabilities"][0]
            assert cap["demonstrated_level"] is None
            assert cap["label"] is None
        finally:
            _cleanup(app, aid)

    def test_capability_item_id_pointing_to_deleted_object_has_no_label(self, auth_client, app, ids):
        """item_type valide mais item_id orphelin (objet supprimé) → libellé None,
        sans erreur 500."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _link_capability(app, ids["entity_id"], aid, did, "SAVOIR", 999999999, required_level=2)
        try:
            r = auth_client.get(f"/diagnostic/{ids['user_id']}/{aid}/{did}")
            assert r.status_code == 200
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

    def test_ai_success_returns_parsed_plan(self, auth_client, app, ids, monkeypatch):
        """Client IA + prompt disponibles et réponse JSON valide → plan renvoyé,
        source='AI' (CDC 6.8)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)

        class _FakeMessage:
            content = json.dumps({"plan": [{"action": "Former au savoir-faire X"}]})

        class _FakeChoice:
            message = _FakeMessage()

        class _FakeCompletion:
            choices = [_FakeChoice()]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeCompletion()

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr("Code.routes.diagnostic.openai_client_or_none",
                            lambda: (_FakeClient(), None))
        monkeypatch.setattr("Code.routes.diagnostic.get_prompt",
                            lambda key: "Tu es un expert en plan de développement.")
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
            assert data["source"] == "AI"
            assert data["plan"] == [{"action": "Former au savoir-faire X"}]
        finally:
            _cleanup(app, aid)

    def test_ai_exception_falls_back_to_error_source(self, auth_client, app, ids, monkeypatch):
        """Le SDK IA lève une exception (timeout, réponse invalide…) → repli
        explicite source='error', jamais de 500 (CDC 6.8)."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)

        class _FakeCompletions:
            def create(self, **kwargs):
                raise RuntimeError("boom")

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr("Code.routes.diagnostic.openai_client_or_none",
                            lambda: (_FakeClient(), None))
        monkeypatch.setattr("Code.routes.diagnostic.get_prompt",
                            lambda key: "Tu es un expert en plan de développement.")
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
            assert data["source"] == "error"
            assert "boom" in data["error"]
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
