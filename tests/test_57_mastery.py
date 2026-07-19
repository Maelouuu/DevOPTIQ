# tests/test_57_mastery.py
"""
Page : Niveaux de maîtrise (/mastery — CDC 3)
Couverture :
  - GET  /mastery/scale                              → échelle de maîtrise (0..4)
  - GET  /mastery/activity/<user_id>/<activity_id>    → état de maîtrise d'une activité pour un individu
  - POST /mastery/evaluate                             → enregistre le niveau démontré d'un résultat
  - POST /mastery/required                             → fixe le niveau requis Rôle × Activité
  - GET  /mastery/dashboard/<user_id>/<role_id>        → tableau des activités d'un rôle
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


def _create_result_data(app, entity_id, activity_id, name="Résultat Test 57", min_perf="Standard atteint"):
    with app.app_context():
        from Code.models.models import Data
        from Code.extensions import db
        d = Data(entity_id=entity_id, name=name, type="flux",
                 producer_activity_id=activity_id, semantic_nature="RESULT",
                 minimum_performance_text=min_perf)
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


def _link_role_activity(app, activity_id, role_id, status="Garant"):
    with app.app_context():
        from Code.models.models import activity_roles
        from Code.extensions import db
        db.session.execute(activity_roles.insert().values(
            activity_id=activity_id, role_id=role_id, status=status))
        db.session.commit()


def _cleanup(app, activity_id=None, role_id=None):
    with app.app_context():
        from Code.models.models import Activities, Data, Role, CompetencyEvaluation, activity_roles
        from Code.extensions import db
        if activity_id:
            CompetencyEvaluation.query.filter_by(activity_id=activity_id).delete()
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.activity_id == activity_id))
            Data.query.filter_by(producer_activity_id=activity_id).delete()
            a = Activities.query.get(activity_id)
            if a:
                db.session.delete(a)
        if role_id:
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.role_id == role_id))
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
        assert data["mastery"]["0"] == "Non démontré"
        assert data["mastery"]["4"] == "Expertise"
        assert data["not_assessed"] == "Non évalué"


class TestGetActivity:

    def test_unknown_activity_returns_404(self, auth_client, ids):
        r = auth_client.get(f"/mastery/activity/{ids['user_id']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_no_result_returns_zero_results_null_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["n_results"] == 0
            assert data["global_level"] is None
            assert data["color"] == "grey"
            assert data["results"] == []
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
            assert data["results"][0]["demonstrated_level"] is None
            assert data["results"][0]["self_level"] is None
        finally:
            _cleanup(app, activity_id=aid)


class TestEvaluate:

    def test_invalid_payload_missing_fields_returns_400(self, auth_client):
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
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "9", "mastery_level": 2,
                }),
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
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "1", "mastery_level": 99,
                }),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_level"
        finally:
            _cleanup(app, activity_id=aid)

    def test_not_a_result_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        with app.app_context():
            from Code.models.models import Data
            from Code.extensions import db
            d = Data(entity_id=ids["entity_id"], name="Pas un résultat", type="flux")
            db.session.add(d)
            db.session.commit()
            did = d.id
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "1", "mastery_level": 2,
                }),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "not_a_result"
        finally:
            _cleanup(app, activity_id=aid)

    def test_unknown_data_id_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/mastery/evaluate",
            data=json.dumps({
                "user_id": ids["user_id"], "activity_id": ids["activity_id"], "data_id": 999999,
                "evaluator": "1", "mastery_level": 2,
            }),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "not_a_result"

    def test_self_evaluation_alone_does_not_validate(self, auth_client, app, ids):
        """CDC 3.6 : l'auto-évaluation (evaluator=0) reste visible mais ne suffit pas
        à établir le niveau démontré de référence."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "0", "mastery_level": 3,
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            state = r.get_json()["state"]
            assert state["results"][0]["self_level"] == 3
            assert state["results"][0]["demonstrated_level"] is None
            assert state["global_level"] is None
            assert state["color"] == "grey"
        finally:
            _cleanup(app, activity_id=aid)

    def test_garant_evaluation_validates_global_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "1", "mastery_level": 2, "evidence": "Observation directe",
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            state = r.get_json()["state"]
            assert state["complete"] is True
            assert state["global_level"] == 2
            assert state["color"] == "green"
            assert state["results"][0]["demonstrated_level"] == 2
        finally:
            _cleanup(app, activity_id=aid)

    def test_low_level_gives_red_color(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "2", "mastery_level": 1,
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["state"]["color"] == "red"
        finally:
            _cleanup(app, activity_id=aid)

    def test_evaluate_is_upsert_not_duplicated(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            payload1 = json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 1,
            })
            payload2 = json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 3,
            })
            auth_client.post("/mastery/evaluate", data=payload1, content_type="application/json")
            r2 = auth_client.post("/mastery/evaluate", data=payload2, content_type="application/json")
            assert r2.get_json()["state"]["global_level"] == 3
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                rows = CompetencyEvaluation.query.filter_by(
                    activity_id=aid, item_id=did, item_type="activity_results", eval_number="1").all()
                assert len(rows) == 1
                assert rows[0].mastery_level == 3
        finally:
            _cleanup(app, activity_id=aid)

    def test_multiple_results_global_level_is_minimum(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did1 = _create_result_data(app, ids["entity_id"], aid, name="Résultat A 57")
        did2 = _create_result_data(app, ids["entity_id"], aid, name="Résultat B 57")
        try:
            auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did1,
                    "evaluator": "1", "mastery_level": 4,
                }),
                content_type="application/json",
            )
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did2,
                    "evaluator": "1", "mastery_level": 2,
                }),
                content_type="application/json",
            )
            state = r.get_json()["state"]
            assert state["complete"] is True
            assert state["global_level"] == 2
            assert state["n_results"] == 2
        finally:
            _cleanup(app, activity_id=aid)

    def test_one_unevaluated_result_keeps_global_level_null(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did1 = _create_result_data(app, ids["entity_id"], aid, name="Résultat C 57")
        _create_result_data(app, ids["entity_id"], aid, name="Résultat D 57")
        try:
            r = auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did1,
                    "evaluator": "1", "mastery_level": 4,
                }),
                content_type="application/json",
            )
            state = r.get_json()["state"]
            assert state["complete"] is False
            assert state["global_level"] is None
        finally:
            _cleanup(app, activity_id=aid)


class TestRequired:

    def test_invalid_payload_returns_400(self, auth_client):
        r = auth_client.post(
            "/mastery/required",
            data=json.dumps({"activity_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_invalid_level_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        rid = _create_role(app, ids["entity_id"])
        _link_role_activity(app, aid, rid)
        try:
            r = auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": aid, "role_id": rid, "required_mastery_level": 42}),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_level"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_association_not_found_returns_404(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        rid = _create_role(app, ids["entity_id"])
        try:
            r = auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": aid, "role_id": rid, "required_mastery_level": 2}),
                content_type="application/json",
            )
            assert r.status_code == 404
            assert r.get_json()["error"] == "association_not_found"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_set_required_valid_then_reflected_in_activity_state(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        rid = _create_role(app, ids["entity_id"])
        _link_role_activity(app, aid, rid)
        try:
            r = auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": aid, "role_id": rid, "required_mastery_level": 3}),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["required_mastery_level"] == 3

            auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "1", "mastery_level": 2,
                }),
                content_type="application/json",
            )
            r2 = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}?role_id={rid}")
            data = r2.get_json()
            assert data["required_level"] == 3
            assert data["gap"] == -1
            assert data["color"] == "orange"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_set_required_to_null_clears_it(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        rid = _create_role(app, ids["entity_id"])
        _link_role_activity(app, aid, rid)
        try:
            auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": aid, "role_id": rid, "required_mastery_level": 2}),
                content_type="application/json",
            )
            r = auth_client.post(
                "/mastery/required",
                data=json.dumps({"activity_id": aid, "role_id": rid, "required_mastery_level": None}),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["required_mastery_level"] is None
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)


class TestDashboard:

    def test_unknown_role_returns_404(self, auth_client, ids):
        r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "role_not_found"

    def test_dashboard_lists_activities_of_role(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        rid = _create_role(app, ids["entity_id"])
        _link_role_activity(app, aid, rid)
        try:
            auth_client.post(
                "/mastery/evaluate",
                data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "1", "mastery_level": 2,
                }),
                content_type="application/json",
            )
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["role_id"] == rid
            row = next(x for x in data["activities"] if x["activity_id"] == aid)
            assert row["demonstrated_level"] == 2
            assert row["color"] == "green"
            assert row["technicity"] == "none"
            assert row["technicity_alert"] is False
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_dashboard_empty_when_role_has_no_activities(self, auth_client, app, ids):
        rid = _create_role(app, ids["entity_id"], name="Rôle Sans Activité 57")
        try:
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            assert r.get_json()["activities"] == []
        finally:
            _cleanup(app, role_id=rid)
