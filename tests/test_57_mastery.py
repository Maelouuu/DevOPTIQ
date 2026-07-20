# tests/test_57_mastery.py
# CDC 3 (V1.1) — Niveaux de maîtrise par résultat (/mastery).
"""
Page : Maîtrise des compétences par résultat (/mastery — CDC 3)
Couverture :
  - GET  /mastery/scale                                    → échelle de maîtrise (0..4)
  - GET  /mastery/activity/<user_id>/<activity_id>          → état de maîtrise d'une activité
  - POST /mastery/required                                  → niveau requis Rôle × Activité
  - POST /mastery/evaluate                                  → niveau démontré d'un résultat
  - GET  /mastery/dashboard/<user_id>/<role_id>              → tableau des activités d'un rôle
"""
import json
import pytest
from Code.extensions import db

pytestmark = pytest.mark.mastery


def _create_role(app, entity_id, name):
    with app.app_context():
        from Code.models.models import Role
        r = Role(entity_id=entity_id, name=name)
        db.session.add(r)
        db.session.commit()
        return r.id


def _create_activity(app, entity_id, name):
    with app.app_context():
        from Code.models.models import Activities
        a = Activities(entity_id=entity_id, name=name)
        db.session.add(a)
        db.session.commit()
        return a.id


def _link_role(app, activity_id, role_id, required=None):
    with app.app_context():
        from Code.models.models import activity_roles
        db.session.execute(activity_roles.insert().values(
            activity_id=activity_id, role_id=role_id, status="active",
            required_mastery_level=required))
        db.session.commit()


def _create_result(app, entity_id, activity_id, name="Résultat Test 57"):
    with app.app_context():
        from Code.models.models import Data
        d = Data(entity_id=entity_id, name=name, type="flux",
                  producer_activity_id=activity_id, semantic_nature="RESULT")
        db.session.add(d)
        db.session.commit()
        return d.id


def _create_non_result(app, entity_id, activity_id, name="Mesure Test 57"):
    with app.app_context():
        from Code.models.models import Data
        d = Data(entity_id=entity_id, name=name, type="flux",
                  producer_activity_id=activity_id, semantic_nature="MEASURE")
        db.session.add(d)
        db.session.commit()
        return d.id


def _cleanup(app, activity_id=None, role_id=None, data_ids=None, user_id=None):
    with app.app_context():
        from Code.models.models import Activities, Role, Data, CompetencyEvaluation, activity_roles
        if activity_id and user_id:
            CompetencyEvaluation.query.filter_by(activity_id=activity_id, user_id=user_id).delete()
        if activity_id and role_id:
            db.session.execute(activity_roles.delete().where(
                (activity_roles.c.activity_id == activity_id) & (activity_roles.c.role_id == role_id)))
        for did in (data_ids or []):
            d = Data.query.get(did)
            if d:
                db.session.delete(d)
        if activity_id:
            a = Activities.query.get(activity_id)
            if a:
                db.session.delete(a)
        if role_id:
            r = Role.query.get(role_id)
            if r:
                db.session.delete(r)
        db.session.commit()


def _set_lang(client, lang="fr"):
    with client.session_transaction() as s:
        s["lang"] = lang


class TestScale:

    def test_scale_returns_five_levels_fr(self, auth_client):
        _set_lang(auth_client, "fr")
        r = auth_client.get("/mastery/scale")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data["mastery"].keys()) == {"0", "1", "2", "3", "4"}
        assert data["mastery"]["4"] == "Expertise"
        assert data["not_assessed"] == "Non évalué"

    def test_scale_returns_english_labels(self, auth_client):
        _set_lang(auth_client, "en")
        r = auth_client.get("/mastery/scale")
        assert r.status_code == 200
        data = r.get_json()
        assert data["mastery"]["0"] == "Not demonstrated"
        assert data["not_assessed"] == "Not assessed"
        _set_lang(auth_client, "fr")


class TestGetActivity:

    def test_unknown_activity_returns_404(self, auth_client, ids):
        r = auth_client.get(f"/mastery/activity/{ids['user_id']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_activity_without_results_is_empty(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité sans résultat 57")
        try:
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            assert r.status_code == 200
            body = r.get_json()
            assert body["n_results"] == 0
            assert body["results"] == []
            assert body["global_level"] is None
            assert body["color"] == "grey"
        finally:
            _cleanup(app, activity_id=aid)

    def test_result_not_evaluated_keeps_global_level_none(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité résultat non évalué 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            assert r.status_code == 200
            body = r.get_json()
            assert body["n_results"] == 1
            assert body["complete"] is False
            assert body["global_level"] is None
            assert body["results"][0]["demonstrated_level"] is None
            assert body["results"][0]["self_level"] is None
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], user_id=ids["user_id"])

    def test_self_evaluation_does_not_validate_global_level(self, auth_client, app, ids):
        """L'auto-évaluation (evaluator 0) ne suffit pas à valider le niveau de référence."""
        aid = _create_activity(app, ids["entity_id"], "Activité auto-eval seule 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "0", "mastery_level": 3,
            })
            assert r.status_code == 200

            r2 = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            body = r2.get_json()
            assert body["results"][0]["self_level"] == 3
            assert body["results"][0]["demonstrated_level"] is None
            assert body["global_level"] is None
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], user_id=ids["user_id"])

    def test_garant_evaluation_validates_global_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité validée garant 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 2, "evidence": "Vu en atelier",
            })
            assert r.status_code == 200
            assert r.get_json()["ok"] is True

            r2 = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            body = r2.get_json()
            assert body["complete"] is True
            assert body["global_level"] == 2
            assert body["color"] == "green"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], user_id=ids["user_id"])

    def test_color_red_when_demonstrated_below_two(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité couleur rouge 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "2", "mastery_level": 1,
            })
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}")
            assert r.get_json()["color"] == "red"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], user_id=ids["user_id"])

    def test_color_orange_when_below_required(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité couleur orange 57")
        rid = _create_role(app, ids["entity_id"], "Rôle couleur orange 57")
        did = _create_result(app, ids["entity_id"], aid)
        _link_role(app, aid, rid, required=3)
        try:
            auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 2,
            })
            r = auth_client.get(f"/mastery/activity/{ids['user_id']}/{aid}?role_id={rid}")
            body = r.get_json()
            assert body["required_level"] == 3
            assert body["gap"] == -1
            assert body["color"] == "orange"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid, data_ids=[did], user_id=ids["user_id"])


class TestSetRequired:

    def test_missing_payload_returns_400(self, auth_client, ids):
        r = auth_client.post("/mastery/required", json={"activity_id": ids["activity_id"]})
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_invalid_level_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité niveau invalide 57")
        rid = _create_role(app, ids["entity_id"], "Rôle niveau invalide 57")
        _link_role(app, aid, rid)
        try:
            r = auth_client.post("/mastery/required", json={
                "activity_id": aid, "role_id": rid, "required_mastery_level": 99,
            })
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_level"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_association_not_found_returns_404(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité sans assoc 57")
        rid = _create_role(app, ids["entity_id"], "Rôle sans assoc 57")
        try:
            r = auth_client.post("/mastery/required", json={
                "activity_id": aid, "role_id": rid, "required_mastery_level": 2,
            })
            assert r.status_code == 404
            assert r.get_json()["error"] == "association_not_found"
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_valid_sets_required_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité set requis 57")
        rid = _create_role(app, ids["entity_id"], "Rôle set requis 57")
        _link_role(app, aid, rid)
        try:
            r = auth_client.post("/mastery/required", json={
                "activity_id": aid, "role_id": rid, "required_mastery_level": 3,
            })
            assert r.status_code == 200
            assert r.get_json()["required_mastery_level"] == 3

            with app.app_context():
                from Code.models.models import activity_roles
                row = db.session.execute(db.select(activity_roles.c.required_mastery_level).where(
                    (activity_roles.c.activity_id == aid) & (activity_roles.c.role_id == rid))).first()
                assert row[0] == 3
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)

    def test_valid_can_clear_required_level(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité clear requis 57")
        rid = _create_role(app, ids["entity_id"], "Rôle clear requis 57")
        _link_role(app, aid, rid, required=2)
        try:
            r = auth_client.post("/mastery/required", json={
                "activity_id": aid, "role_id": rid, "required_mastery_level": None,
            })
            assert r.status_code == 200
            assert r.get_json()["required_mastery_level"] is None
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)


class TestEvaluate:

    def test_missing_fields_returns_400(self, auth_client, ids):
        r = auth_client.post("/mastery/evaluate", json={
            "user_id": ids["user_id"], "activity_id": ids["activity_id"],
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_unknown_evaluator_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité évaluateur invalide 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "9", "mastery_level": 2,
            })
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_payload"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_invalid_level_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité niveau eval invalide 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "0", "mastery_level": 42,
            })
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_level"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_data_not_a_result_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité mesure pas résultat 57")
        did = _create_non_result(app, ids["entity_id"], aid)
        try:
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "0", "mastery_level": 2,
            })
            assert r.status_code == 400
            assert r.get_json()["error"] == "not_a_result"
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did])

    def test_unknown_data_id_returns_400(self, auth_client, ids):
        r = auth_client.post("/mastery/evaluate", json={
            "user_id": ids["user_id"], "activity_id": ids["activity_id"], "data_id": 999999,
            "evaluator": "0", "mastery_level": 2,
        })
        assert r.status_code == 400
        assert r.get_json()["error"] == "not_a_result"

    def test_valid_creates_evaluation(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité créer eval 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "0", "mastery_level": 1, "evidence": "Premier essai",
            })
            assert r.status_code == 200
            body = r.get_json()
            assert body["ok"] is True
            assert body["state"]["results"][0]["self_level"] == 1

            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                count = CompetencyEvaluation.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, item_id=did,
                    item_type="activity_results").count()
                assert count == 1
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], user_id=ids["user_id"])

    def test_repeated_evaluation_upserts_instead_of_duplicating(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité upsert eval 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 1,
            })
            r = auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "1", "mastery_level": 3,
            })
            assert r.status_code == 200
            assert r.get_json()["state"]["global_level"] == 3

            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                count = CompetencyEvaluation.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, item_id=did,
                    item_type="activity_results", eval_number="1").count()
                assert count == 1
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], user_id=ids["user_id"])

    def test_evidence_blank_is_stored_as_null(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité preuve vide 57")
        did = _create_result(app, ids["entity_id"], aid)
        try:
            auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "0", "mastery_level": 2, "evidence": "   ",
            })
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                ev = CompetencyEvaluation.query.filter_by(
                    user_id=ids["user_id"], activity_id=aid, item_id=did,
                    item_type="activity_results", eval_number="0").first()
                assert ev.evidence is None
        finally:
            _cleanup(app, activity_id=aid, data_ids=[did], user_id=ids["user_id"])


class TestDashboard:

    def test_unknown_role_returns_404(self, auth_client, ids):
        r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "role_not_found"

    def test_dashboard_lists_role_activities(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité dashboard 57")
        rid = _create_role(app, ids["entity_id"], "Rôle dashboard 57")
        did = _create_result(app, ids["entity_id"], aid)
        _link_role(app, aid, rid, required=2)
        try:
            auth_client.post("/mastery/evaluate", json={
                "user_id": ids["user_id"], "activity_id": aid, "data_id": did,
                "evaluator": "2", "mastery_level": 2,
            })
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            body = r.get_json()
            assert body["role_id"] == rid
            assert body["role_name"] == "Rôle dashboard 57"
            row = next(x for x in body["activities"] if x["activity_id"] == aid)
            assert row["required_level"] == 2
            assert row["demonstrated_level"] == 2
            assert row["color"] == "green"
            assert row["technicity"] == "none"
            assert row["technicity_alert"] is False
        finally:
            _cleanup(app, activity_id=aid, role_id=rid, data_ids=[did], user_id=ids["user_id"])

    def test_dashboard_excludes_activities_of_other_roles(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité hors rôle 57")
        rid = _create_role(app, ids["entity_id"], "Rôle vide dashboard 57")
        try:
            r = auth_client.get(f"/mastery/dashboard/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            ids_listed = [x["activity_id"] for x in r.get_json()["activities"]]
            assert aid not in ids_listed
        finally:
            _cleanup(app, activity_id=aid, role_id=rid)
