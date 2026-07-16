# tests/test_56_mastery.py
"""
Page : Niveaux de maîtrise et tableau de bord (/mastery)
CDC 3 (V1.1) — Trois notions distinctes : standard minimal (Data.minimum_performance_text),
niveau REQUIS par le rôle (activity_roles.required_mastery_level), niveau DÉMONTRÉ par
l'individu (CompetencyEvaluation.mastery_level, PAR RÉSULTAT). Niveau global d'activité =
MINIMUM des résultats (jamais moyenne) ; seuls Garant/Manager (eval_number 1/2) valident la
référence, l'auto-évaluation (0) reste visible mais ne valide pas seule.
Couvre : /mastery/scale, /mastery/required, /mastery/activity/<uid>/<aid>, /mastery/evaluate,
/mastery/dashboard/<uid>/<rid>, et les helpers color_for/domain_status (via dashboard).
"""
import pytest
import json
from Code.extensions import db
from Code.models.models import (
    Entity, Activities, Data, Link, Role, CompetencyEvaluation, activity_roles,
)

pytestmark = pytest.mark.mastery


@pytest.fixture()
def scene(app, ids):
    """Entité dédiée : activité avec 1 résultat (RESULT) qualifié + rôle associé (sans
    niveau requis par défaut) + une donnée non-résultat pour le cas 'not_a_result'."""
    with app.app_context():
        ent = Entity(name="MasteryECo", owner_id=ids["user_id"])
        db.session.add(ent)
        db.session.flush()
        act = Activities(entity_id=ent.id, name="Souder le châssis", shape_id="ms_a1")
        sink = Activities(entity_id=ent.id, name="Contrôle", shape_id="ms_a2")
        db.session.add_all([act, sink])
        db.session.flush()
        link = Link(entity_id=ent.id, source_activity_id=act.id, target_activity_id=sink.id,
                    type="flux", description="Châssis soudé")
        role = Role(entity_id=ent.id, name="Soudeur Mastery")
        measure = Data(entity_id=ent.id, name="Compteur de pièces", type="nourrissante",
                       semantic_nature="MEASURE")
        db.session.add_all([link, role, measure])
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="active"))
        db.session.commit()
        result = {"entity_id": ent.id, "activity_id": act.id, "sink_id": sink.id,
                  "role_id": role.id, "user_id": ids["user_id"], "measure_id": measure.id}

    with app.test_client() as c:
        with c.session_transaction() as s:
            s["active_entity_id"] = result["entity_id"]
        outs = c.get(f"/qualify/outputs/{result['activity_id']}").get_json()["outputs"]
        data_id = outs[0]["data_id"]
        c.post(f"/qualify/save/{result['activity_id']}", json={"outputs": [
            {"data_id": data_id, "nature": "RESULT", "minimum_performance_text": "Cordon continu"}]})
    result["data_id"] = data_id
    yield result

    with app.app_context():
        CompetencyEvaluation.query.filter_by(activity_id=result["activity_id"]).delete()
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id == result["activity_id"]))
        Role.query.filter_by(id=result["role_id"]).delete()
        Link.query.filter_by(entity_id=result["entity_id"]).delete()
        Data.query.filter(Data.entity_id == result["entity_id"]).delete()
        Activities.query.filter(Activities.entity_id == result["entity_id"]).delete()
        Entity.query.filter_by(id=result["entity_id"]).delete()
        db.session.commit()


def _sess(client, entity_id):
    with client.session_transaction() as s:
        s["active_entity_id"] = entity_id


def _evaluate(client, user_id, activity_id, data_id, evaluator, mastery_level, **extra):
    payload = {"user_id": user_id, "activity_id": activity_id, "data_id": data_id,
              "evaluator": evaluator, "mastery_level": mastery_level, **extra}
    return client.post("/mastery/evaluate", data=json.dumps(payload), content_type="application/json")


# ===========================================================================
# 1. GET /mastery/scale
# ===========================================================================

class TestScale:

    def test_scale_returns_five_levels(self, client):
        r = client.get("/mastery/scale")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert set(body["mastery"].keys()) == {"0", "1", "2", "3", "4"}
        assert body["mastery"]["0"] == "Non démontré"
        assert body["not_assessed"] == "Non évalué"


# ===========================================================================
# 2. POST /mastery/required
# ===========================================================================

class TestSetRequired:

    def test_set_required_level_persists(self, app, client, scene):
        r = client.post("/mastery/required", data=json.dumps(
            {"activity_id": scene["activity_id"], "role_id": scene["role_id"],
             "required_mastery_level": 3}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["required_mastery_level"] == 3
        with app.app_context():
            row = db.session.execute(db.select(activity_roles.c.required_mastery_level).where(
                (activity_roles.c.activity_id == scene["activity_id"]) &
                (activity_roles.c.role_id == scene["role_id"]))).first()
            assert row[0] == 3

    def test_set_required_missing_fields_returns_400(self, client):
        r = client.post("/mastery/required", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 400

    def test_set_required_invalid_level_returns_400(self, client, scene):
        r = client.post("/mastery/required", data=json.dumps(
            {"activity_id": scene["activity_id"], "role_id": scene["role_id"],
             "required_mastery_level": 99}), content_type="application/json")
        assert r.status_code == 400

    def test_set_required_unassociated_pair_returns_404(self, client, scene):
        r = client.post("/mastery/required", data=json.dumps(
            {"activity_id": scene["sink_id"], "role_id": scene["role_id"],
             "required_mastery_level": 2}), content_type="application/json")
        assert r.status_code == 404


# ===========================================================================
# 3. GET /mastery/activity/<user_id>/<activity_id>
# ===========================================================================

class TestGetActivity:

    def test_activity_not_found_returns_404(self, client, scene):
        r = client.get(f"/mastery/activity/{scene['user_id']}/999999")
        assert r.status_code == 404

    def test_not_yet_evaluated_is_incomplete_and_grey(self, client, scene):
        r = client.get(f"/mastery/activity/{scene['user_id']}/{scene['activity_id']}")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["n_results"] == 1
        assert body["complete"] is False
        assert body["global_level"] is None
        assert body["color"] == "grey"
        assert body["results"][0]["demonstrated_level"] is None

    def test_self_evaluation_does_not_validate_reference(self, client, scene):
        _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                  evaluator="0", mastery_level=4)
        body = json.loads(client.get(
            f"/mastery/activity/{scene['user_id']}/{scene['activity_id']}").data)
        assert body["results"][0]["self_level"] == 4
        assert body["results"][0]["demonstrated_level"] is None
        assert body["global_level"] is None

    def test_manager_evaluation_sets_reference_level(self, client, scene):
        _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                  evaluator="2", mastery_level=3)
        body = json.loads(client.get(
            f"/mastery/activity/{scene['user_id']}/{scene['activity_id']}"
            f"?role_id={scene['role_id']}").data)
        assert body["complete"] is True
        assert body["global_level"] == 3
        assert body["color"] == "green"


# ===========================================================================
# 4. POST /mastery/evaluate — cas limites
# ===========================================================================

class TestEvaluate:

    def test_missing_fields_returns_400(self, client, scene):
        r = client.post("/mastery/evaluate", data=json.dumps(
            {"user_id": scene["user_id"]}), content_type="application/json")
        assert r.status_code == 400

    def test_invalid_evaluator_returns_400(self, client, scene):
        r = _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                     evaluator="9", mastery_level=2)
        assert r.status_code == 400

    def test_invalid_level_returns_400(self, client, scene):
        r = _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                     evaluator="1", mastery_level=42)
        assert r.status_code == 400

    def test_data_not_a_result_returns_400(self, client, scene):
        r = _evaluate(client, scene["user_id"], scene["activity_id"], scene["measure_id"],
                     evaluator="1", mastery_level=2)
        assert r.status_code == 400
        assert json.loads(r.data)["error"] == "not_a_result"

    def test_data_unknown_returns_400(self, client, scene):
        r = _evaluate(client, scene["user_id"], scene["activity_id"], 999999,
                     evaluator="1", mastery_level=2)
        assert r.status_code == 400

    def test_reevaluate_same_evaluator_upserts_not_duplicates(self, app, client, scene):
        _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                 evaluator="1", mastery_level=1)
        _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                 evaluator="1", mastery_level=2)
        with app.app_context():
            rows = CompetencyEvaluation.query.filter_by(
                user_id=scene["user_id"], activity_id=scene["activity_id"],
                item_id=scene["data_id"], item_type="activity_results", eval_number="1").all()
            assert len(rows) == 1
            assert rows[0].mastery_level == 2

    def test_null_level_clears_evaluation(self, app, client, scene):
        _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                 evaluator="1", mastery_level=2)
        r = _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                     evaluator="1", mastery_level=None)
        assert r.status_code == 200
        with app.app_context():
            row = CompetencyEvaluation.query.filter_by(
                user_id=scene["user_id"], activity_id=scene["activity_id"],
                item_id=scene["data_id"], item_type="activity_results", eval_number="1").first()
            assert row.mastery_level is None


# ===========================================================================
# 5. GET /mastery/dashboard/<user_id>/<role_id>
# ===========================================================================

class TestDashboard:

    def test_role_not_found_returns_404(self, client, scene):
        r = client.get(f"/mastery/dashboard/{scene['user_id']}/999999")
        assert r.status_code == 404

    def test_dashboard_lists_associated_activity(self, client, scene):
        _sess(client, scene["entity_id"])
        r = client.get(f"/mastery/dashboard/{scene['user_id']}/{scene['role_id']}")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["role_id"] == scene["role_id"]
        acts = {row["activity_id"] for row in body["activities"]}
        assert scene["activity_id"] in acts
        assert scene["sink_id"] not in acts   # non associée au rôle

    def test_dashboard_reflects_required_and_gap_after_evaluation(self, client, scene):
        _sess(client, scene["entity_id"])
        client.post("/mastery/required", data=json.dumps(
            {"activity_id": scene["activity_id"], "role_id": scene["role_id"],
             "required_mastery_level": 3}), content_type="application/json")
        _evaluate(client, scene["user_id"], scene["activity_id"], scene["data_id"],
                 evaluator="2", mastery_level=1)
        body = json.loads(client.get(
            f"/mastery/dashboard/{scene['user_id']}/{scene['role_id']}").data)
        row = next(r for r in body["activities"] if r["activity_id"] == scene["activity_id"])
        assert row["required_level"] == 3
        assert row["demonstrated_level"] == 1
        assert row["gap"] == 1 - 3
        assert row["color"] == "red"          # < 2 : autonomie non démontrée
        assert row["last_evaluation"] is not None
        assert row["technicity"] == "none"    # aucun domaine technique paramétré
        assert row["technicity_alert"] is False


# ===========================================================================
# 6. color_for() — helper de calcul de couleur (CDC 3.5)
# ===========================================================================

class TestColorForHelper:

    def test_none_is_grey(self):
        from Code.routes.mastery import color_for
        assert color_for(None, 3) == "grey"

    def test_below_two_is_red(self):
        from Code.routes.mastery import color_for
        assert color_for(1, None) == "red"

    def test_below_required_is_orange(self):
        from Code.routes.mastery import color_for
        assert color_for(2, 3) == "orange"

    def test_meets_required_is_green(self):
        from Code.routes.mastery import color_for
        assert color_for(3, 3) == "green"

    def test_no_required_and_autonomous_is_green(self):
        from Code.routes.mastery import color_for
        assert color_for(2, None) == "green"
