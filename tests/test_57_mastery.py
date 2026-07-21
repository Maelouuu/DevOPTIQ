# tests/test_57_mastery.py
"""
Page : Niveaux de maîtrise (/mastery — CDC 3)
Couverture :
  - GET  /mastery/scale                             → échelle de maîtrise (5 niveaux)
  - GET  /mastery/dashboard/<user_id>/<role_id>      → tableau activités du rôle
  - POST /mastery/required                            → niveau requis Rôle × Activité
  - GET  /mastery/activity/<user_id>/<activity_id>    → état complet d'une activité
  - POST /mastery/evaluate                             → enregistre le niveau démontré d'un résultat
"""
import json
import pytest

pytestmark = pytest.mark.mastery


def _create_activity(app, entity_id, name="Activité Maîtrise Test 57"):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="Description")
        db.session.add(a)
        db.session.commit()
        return a.id


def _create_result_data(app, entity_id, activity_id, name="Résultat Maîtrise Test 57"):
    with app.app_context():
        from Code.models.models import Data
        from Code.extensions import db
        d = Data(entity_id=entity_id, name=name, type="flux",
                 producer_activity_id=activity_id, semantic_nature="RESULT",
                 minimum_performance_text="Standard minimal")
        db.session.add(d)
        db.session.commit()
        return d.id


def _create_role(app, entity_id, name="Rôle Maîtrise Test 57"):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        r = Role(entity_id=entity_id, name=name)
        db.session.add(r)
        db.session.commit()
        return r.id


def _link_role_activity(app, activity_id, role_id, status="garant"):
    with app.app_context():
        from Code.models.models import activity_roles
        from Code.extensions import db
        db.session.execute(
            activity_roles.insert().values(activity_id=activity_id, role_id=role_id, status=status)
        )
        db.session.commit()


def _cleanup(app, activity_id=None, role_id=None):
    with app.app_context():
        from Code.models.models import (Activities, Data, Role, CompetencyEvaluation, activity_roles)
        from Code.extensions import db
        if activity_id:
            CompetencyEvaluation.query.filter_by(activity_id=activity_id).delete()
            db.session.execute(activity_roles.delete().where(activity_roles.c.activity_id == activity_id))
            Data.query.filter_by(producer_activity_id=activity_id).delete()
            a = Activities.query.get(activity_id)
            if a:
                db.session.delete(a)
        if role_id:
            db.session.execute(activity_roles.delete().where(activity_roles.c.role_id == role_id))
            r = Role.query.get(role_id)
            if r:
                db.session.delete(r)
        db.session.commit()


class TestScale:

    def test_scale_returns_five_levels(self, auth_client):
        r = auth_client.get("/mastery/scale")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data["mastery"].keys()) == {"0", "1", "2", "3", "4"}
        assert data["mastery"]["4"] == "Expertise"
        assert data["not_assessed"] == "Non évalué"


class TestGetActivity:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.get("/mastery/activity/1/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_no_result_returns_null_global_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["n_results"] == 0
            assert data["global_level"] is None
            assert data["color"] == "grey"
        finally:
            _cleanup(app, activity_id=aid)

    def test_result_not_evaluated_is_incomplete(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            data = r.get_json()
            assert data["n_results"] == 1
            assert data["complete"] is False
            assert data["global_level"] is None
            assert len(data["results"]) == 1
            assert data["results"][0]["demonstrated_level"] is None
        finally:
            _cleanup(app, activity_id=aid)


class TestEvaluate:

    def test_missing_fields_returns_400(self, auth_client):
        r = auth_client.post(
            "/mastery/evaluate",
            data=json.dumps({"user_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_invalid_evaluator_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid,
                                  "data_id": did, "evaluator": "9", "mastery_level": 2}),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_payload"
        finally:
            _cleanup(app, activity_id=aid)

    def test_invalid_level_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid,
                                  "data_id": did, "evaluator": "1", "mastery_level": 42}),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_level"
        finally:
            _cleanup(app, activity_id=aid)

    def test_not_a_result_returns_400(self, auth_client, app, ids):
        r = auth_client.post(
            "/mastery/evaluate",
            data=json.dumps({"user_id": ids["user_id"], "activity_id": ids["activity_id"],
                              "data_id": 999999, "evaluator": "1", "mastery_level": 2}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "not_a_result"

    def test_self_evaluation_does_not_validate_global_level(self, auth_client, app, ids):
        """CDC 3.6 : l'auto-évaluation (evaluator=0) n'est pas VALIDATING — le niveau
        global de référence reste None tant que Garant/Manager n'a pas évalué."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid,
                                  "data_id": did, "evaluator": "0", "mastery_level": 3}),
                content_type="application/json",
            )
            assert r.status_code == 200
            state = r.get_json()["state"]
            assert state["results"][0]["self_level"] == 3
            assert state["results"][0]["demonstrated_level"] is None
            assert state["global_level"] is None
        finally:
            _cleanup(app, activity_id=aid)

    def test_garant_evaluation_sets_global_level_and_color(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid,
                                  "data_id": did, "evaluator": "1", "mastery_level": 2,
                                  "evidence": "Observation directe"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            state = r.get_json()["state"]
            assert state["global_level"] == 2
            assert state["complete"] is True
            assert state["color"] == "green"

            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                ev = CompetencyEvaluation.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, item_id=did, eval_number="1").first()
                assert ev.mastery_level == 2
                assert ev.evidence == "Observation directe"
        finally:
            _cleanup(app, activity_id=aid)

    def test_low_level_gives_red_color(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({"user_id": ids["user_id"], "activity_id": aid,
                                  "data_id": did, "evaluator": "2", "mastery_level": 1}),
                content_type="application/json",
            )
            assert r.get_json()["state"]["color"] == "red"
        finally:
            _cleanup(app, activity_id=aid)

    def test_reevaluation_upserts_same_row(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            payload = lambda lvl: json.dumps({"user_id": ids["user_id"], "activity_id": aid,
                                               "data_id": did, "evaluator": "1", "mastery_level": lvl})
            auth_client.post("/mastery/evaluate", data=payload(1), content_type="application/json")
            auth_client.post("/mastery/evaluate", data=payload(3), content_type="application/json")
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                rows = CompetencyEvaluation.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, item_id=did, eval_number="1").all()
                assert len(rows) == 1
                assert rows[0].mastery_level == 3
        finally:
            _cleanup(app, activity_id=aid)


class TestRequired:

    def test_missing_fields_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/mastery/required",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_invalid_level_returns_400(self, auth_client, app, ids):
        rid = _create_role(app, ids["entity_id"])
        try:
            r = auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": ids["activity_id"], "role_id": rid,
                                  "required_mastery_level": 99}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, role_id=rid)

    def test_unknown_association_returns_404(self, auth_client, app, ids):
        rid = _create_role(app, ids["entity_id"])
        try:
            r = auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": ids["activity_id"], "role_id": rid,
                                  "required_mastery_level": 2}),
                content_type="application/json",
            )
            assert r.status_code == 404
            assert r.get_json()["error"] == "association_not_found"
        finally:
            _cleanup(app, role_id=rid)

    def test_set_required_valid(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        rid = _create_role(app, ids["entity_id"])
        _link_role_activity(app, aid, rid)
        try:
            r = auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": aid, "role_id": rid, "required_mastery_level": 3}),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["ok"] is True

            r2 = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}", query_string={"role_id": rid})
            assert r2.get_json()["required_level"] == 3
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)


class TestDashboard:

    def test_unknown_role_returns_404(self, auth_client, ids):
        r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "role_not_found"

    def test_dashboard_lists_linked_activity(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], name="Activité Dashboard Test 57")
        rid = _create_role(app, ids["entity_id"])
        _link_role_activity(app, aid, rid)
        try:
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["role_id"] == rid
            act_ids = [row["activity_id"] for row in data["activities"]]
            assert aid in act_ids
            row = next(row for row in data["activities"] if row["activity_id"] == aid)
            assert row["demonstrated_level"] is None
            assert row["color"] == "grey"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_dashboard_empty_when_no_activities_linked(self, auth_client, app, ids):
        rid = _create_role(app, ids["entity_id"], name="Rôle Vide Test 57")
        try:
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            assert r.get_json()["activities"] == []
        finally:
            _cleanup(app, role_id=rid)
