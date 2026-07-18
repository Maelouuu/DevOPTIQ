# tests/test_57_mastery.py
"""
Page : Niveaux de maîtrise (/mastery — CDC 3, V1.1)
Couverture :
  - GET  /mastery/scale                                → échelle de maîtrise (0..4)
  - GET  /mastery/activity/<user_id>/<activity_id>      → état d'évaluation d'une activité
  - POST /mastery/required                              → niveau requis Rôle × Activité
  - POST /mastery/evaluate                              → enregistrement du niveau démontré (upsert)
  - GET  /mastery/dashboard/<user_id>/<role_id>          → tableau des activités d'un rôle
"""
import json
import pytest
from Code.extensions import db

pytestmark = pytest.mark.mastery


def _create_activity(app, entity_id, name="Activité Maîtrise 57"):
    with app.app_context():
        from Code.models.models import Activities
        a = Activities(entity_id=entity_id, name=name)
        db.session.add(a)
        db.session.commit()
        return a.id


def _create_result(app, entity_id, activity_id, name="Résultat Test 57", min_perf=None):
    with app.app_context():
        from Code.models.models import Data
        d = Data(entity_id=entity_id, name=name, type="flux",
                  producer_activity_id=activity_id, semantic_nature="RESULT",
                  minimum_performance_text=min_perf)
        db.session.add(d)
        db.session.commit()
        return d.id


def _create_role(app, entity_id, name="Rôle Maîtrise Test 57"):
    with app.app_context():
        from Code.models.models import Role
        r = Role(entity_id=entity_id, name=name)
        db.session.add(r)
        db.session.commit()
        return r.id


def _link_role(app, activity_id, role_id, status="garant", required_mastery_level=None):
    with app.app_context():
        from Code.models.models import activity_roles
        db.session.execute(activity_roles.insert().values(
            activity_id=activity_id, role_id=role_id, status=status,
            required_mastery_level=required_mastery_level))
        db.session.commit()


def _force_entity(client, entity_id, user_id=None):
    """La session (scope=session) peut être polluée par d'autres fichiers de test qui
    activent une entité dédiée sans la restaurer. On force explicitement user_id +
    l'entité active avant les requêtes qui dépendent du filtrage par entité (ex: dashboard)."""
    with client.session_transaction() as sess:
        if user_id is not None:
            sess["user_id"] = user_id
        sess["active_entity_id"] = entity_id


def _cleanup(app, activity_id=None, role_id=None, data_ids=None, user_id=None):
    with app.app_context():
        from Code.models.models import (Activities, Role, Data, activity_roles,
                                         CompetencyEvaluation)
        if activity_id:
            CompetencyEvaluation.query.filter_by(activity_id=activity_id).delete()
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.activity_id == activity_id))
        if data_ids:
            Data.query.filter(Data.id.in_(data_ids)).delete(synchronize_session=False)
        if activity_id:
            a = Activities.query.get(activity_id)
            if a:
                db.session.delete(a)
        if role_id:
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

    def test_no_result_evaluated_yields_null_global_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result(app, ids["entity_id"], aid, min_perf="Zéro défaut")
        try:
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["global_level"] is None
            assert data["complete"] is False
            assert data["n_results"] == 1
            assert data["color"] == "grey"
            assert data["results"][0]["minimum_performance_text"] == "Zéro défaut"
            assert data["results"][0]["demonstrated_level"] is None
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_global_level_is_minimum_of_results(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Min Maîtrise 57")
        d1 = _create_result(app, ids["entity_id"], aid, "Résultat A 57")
        d2 = _create_result(app, ids["entity_id"], aid, "Résultat B 57")
        try:
            auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": d1,
                "evaluator": "1", "mastery_level": 3,
            }), content_type="application/json")
            auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": d2,
                "evaluator": "2", "mastery_level": 1,
            }), content_type="application/json")
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            data = r.get_json()
            assert data["complete"] is True
            assert data["global_level"] == 1
            assert data["color"] == "red"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[d1, d2])

    def test_self_evaluation_does_not_validate_reference_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Self Only 57")
        did = _create_result(app, ids["entity_id"], aid, "Résultat Self 57")
        try:
            auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "0", "mastery_level": 4,
            }), content_type="application/json")
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            data = r.get_json()
            assert data["global_level"] is None
            assert data["complete"] is False
            assert data["results"][0]["self_level"] == 4
            assert data["results"][0]["demonstrated_level"] is None
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_gap_and_color_with_required_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Gap 57")
        did = _create_result(app, ids["entity_id"], aid, "Résultat Gap 57")
        rid = _create_role(app, ids["entity_id"], "Rôle Gap 57")
        _link_role(app, aid, rid, required_mastery_level=3)
        try:
            auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 2,
            }), content_type="application/json")
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}",
                                 query_string={"role_id": rid})
            data = r.get_json()
            assert data["required_level"] == 3
            assert data["global_level"] == 2
            assert data["gap"] == -1
            assert data["color"] == "orange"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], role_id=rid)


class TestSetRequired:

    def test_missing_fields_returns_400(self, auth_client, ids):
        r = auth_client.post("/mastery/required", data=json.dumps({
            "activity_id": ids["activity_id"],
        }), content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_invalid_level_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Req Invalid 57")
        rid = _create_role(app, ids["entity_id"], "Rôle Req Invalid 57")
        _link_role(app, aid, rid)
        try:
            r = auth_client.post("/mastery/required", data=json.dumps({
                "activity_id": aid, "role_id": rid, "required_mastery_level": 42,
            }), content_type="application/json")
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_level"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_association_not_found_returns_404(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Sans Assoc 57")
        rid = _create_role(app, ids["entity_id"], "Rôle Sans Assoc 57")
        try:
            r = auth_client.post("/mastery/required", data=json.dumps({
                "activity_id": aid, "role_id": rid, "required_mastery_level": 2,
            }), content_type="application/json")
            assert r.status_code == 404
            assert r.get_json()["error"] == "association_not_found"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_valid_update_persists(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Req Valid 57")
        rid = _create_role(app, ids["entity_id"], "Rôle Req Valid 57")
        _link_role(app, aid, rid)
        try:
            r = auth_client.post("/mastery/required", data=json.dumps({
                "activity_id": aid, "role_id": rid, "required_mastery_level": 3,
            }), content_type="application/json")
            assert r.status_code == 200
            assert r.get_json()["ok"] is True
            with app.app_context():
                from Code.models.models import activity_roles
                row = db.session.execute(db.select(activity_roles.c.required_mastery_level).where(
                    (activity_roles.c.activity_id == aid) & (activity_roles.c.role_id == rid)
                )).first()
                assert row[0] == 3
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)


class TestEvaluate:

    def test_missing_fields_returns_400(self, auth_client, ids):
        r = auth_client.post("/mastery/evaluate", data=json.dumps({
            "user_id": ids["user_id"], "activity_id": ids["activity_id"],
        }), content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_unknown_evaluator_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Eval Bad 57")
        did = _create_result(app, ids["entity_id"], aid, "Résultat Eval Bad 57")
        try:
            r = auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "9", "mastery_level": 2,
            }), content_type="application/json")
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_payload"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_invalid_level_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Eval Lvl 57")
        did = _create_result(app, ids["entity_id"], aid, "Résultat Eval Lvl 57")
        try:
            r = auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 99,
            }), content_type="application/json")
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_level"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_not_a_result_returns_400(self, auth_client, app, ids):
        with app.app_context():
            from Code.models.models import Data
            d = Data(entity_id=ids["entity_id"], name="Donnée non-résultat 57", type="flux")
            db.session.add(d)
            db.session.commit()
            did = d.id
        try:
            r = auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": ids["activity_id"], "data_id": did,
                "evaluator": "1", "mastery_level": 2,
            }), content_type="application/json")
            assert r.status_code == 400
            assert r.get_json()["error"] == "not_a_result"
        finally:
            with app.app_context():
                from Code.models.models import Data as D2
                obj = D2.query.get(did)
                if obj:
                    db.session.delete(obj)
                    db.session.commit()

    def test_unknown_data_id_returns_400(self, auth_client, ids):
        r = auth_client.post("/mastery/evaluate", data=json.dumps({
            "user_id": ids["user_id"], "activity_id": ids["activity_id"], "data_id": 999999,
            "evaluator": "1", "mastery_level": 2,
        }), content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["error"] == "not_a_result"

    def test_evaluate_is_upsert_not_duplicated(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Upsert 57")
        did = _create_result(app, ids["entity_id"], aid, "Résultat Upsert 57")
        try:
            for lvl in (1, 3):
                r = auth_client.post("/mastery/evaluate", data=json.dumps({
                    "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                    "evaluator": "2", "mastery_level": lvl, "evidence": f"preuve-{lvl}",
                }), content_type="application/json")
                assert r.status_code == 200
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                rows = CompetencyEvaluation.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, item_id=did,
                    item_type="activity_results", eval_number="2").all()
                assert len(rows) == 1
                assert rows[0].mastery_level == 3
                assert rows[0].evidence == "preuve-3"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_evaluate_returns_updated_state(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Retour Etat 57")
        did = _create_result(app, ids["entity_id"], aid, "Résultat Retour Etat 57")
        try:
            r = auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 4,
            }), content_type="application/json")
            assert r.status_code == 200
            body = r.get_json()
            assert body["ok"] is True
            assert body["state"]["global_level"] == 4
            assert body["state"]["activity_id"] == aid
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])


class TestDashboard:

    def test_unknown_role_returns_404(self, auth_client):
        r = auth_client.get("/mastery/dashboard/1/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "role_not_found"

    def test_dashboard_lists_role_activities_with_levels(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Dashboard 57")
        did = _create_result(app, ids["entity_id"], aid, "Résultat Dashboard 57")
        rid = _create_role(app, ids["entity_id"], "Rôle Dashboard 57")
        _link_role(app, aid, rid, required_mastery_level=2)
        try:
            _force_entity(auth_client, ids["entity_id"], ids["user_id"])
            auth_client.post("/mastery/evaluate", data=json.dumps({
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "2", "mastery_level": 2,
            }), content_type="application/json")
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["role_id"] == rid
            row = next(x for x in data["activities"] if x["activity_id"] == aid)
            assert row["required_level"] == 2
            assert row["demonstrated_level"] == 2
            assert row["gap"] == 0
            assert row["color"] == "green"
            assert row["complete"] is True
            assert row["last_evaluation"] is not None
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], role_id=rid)

    def test_dashboard_excludes_activity_from_other_entity(self, auth_client, app, ids):
        with app.app_context():
            from Code.models.models import Entity
            other = Entity(name="Autre Entité 57")
            db.session.add(other)
            db.session.commit()
            other_id = other.id
        aid = _create_activity(app, other_id, "Activité Autre Entité 57")
        rid = _create_role(app, ids["entity_id"], "Rôle Cross Entity 57")
        _link_role(app, aid, rid)
        try:
            _force_entity(auth_client, ids["entity_id"], ids["user_id"])
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            activity_ids = [x["activity_id"] for x in r.get_json()["activities"]]
            assert aid not in activity_ids
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)
            with app.app_context():
                from Code.models.models import Entity
                e = Entity.query.get(other_id)
                if e:
                    db.session.delete(e)
                    db.session.commit()
