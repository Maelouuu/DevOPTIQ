# tests/test_62_activities_constraints_items.py
"""
Page : Contraintes & Données via /activities (Code/routes/activities_constraints.py)
       + API items d'activité (Code/routes/activity_items_api.py)
Tests isolés : chaque test crée ses propres objets (pas de dépendance au seed
partagé) pour ne pas polluer / être pollué par les autres tests de la suite.
"""
import json

import pytest

pytestmark = pytest.mark.activities_constraints_items


def _make_activity(app, entity_id, name):
    from Code.extensions import db
    from Code.models.models import Activities

    with app.app_context():
        act = Activities(entity_id=entity_id, name=name, description="")
        db.session.add(act)
        db.session.commit()
        return act.id


class TestAddConstraintViaActivitiesBlueprint:

    def test_add_constraint_success(self, auth_client, ids, app):
        activity_id = _make_activity(app, ids["entity_id"], "Act. contrainte OK")
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"activity_id": activity_id, "description": "Contrainte auto"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["message"] == "Contrainte ajoutée"

        with app.app_context():
            from Code.models.models import Constraint
            saved = Constraint.query.filter_by(activity_id=activity_id).first()
            assert saved is not None
            assert saved.description == "Contrainte auto"

    def test_add_constraint_missing_activity_id(self, auth_client):
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"description": "Sans activité"}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_add_constraint_missing_description(self, auth_client, ids, app):
        activity_id = _make_activity(app, ids["entity_id"], "Act. contrainte vide")
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"activity_id": activity_id, "description": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_constraint_no_body(self, auth_client):
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


class TestAddDataViaActivitiesBlueprint:

    def test_add_data_success(self, auth_client, app):
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"name": "Donnée auto 62", "type": "nourrissante"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["message"] == "Donnée ajoutée"

        with app.app_context():
            from Code.models.models import Data
            saved = Data.query.filter_by(name="Donnée auto 62").first()
            assert saved is not None
            assert saved.type == "nourrissante"

    def test_add_data_missing_name(self, auth_client):
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"type": "nourrissante"}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_add_data_missing_type(self, auth_client):
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"name": "Donnée sans type"}),
            content_type="application/json",
        )
        assert r.status_code == 400


class TestActivityItemsApi:

    def test_activity_items_returns_linked_savoirs_savoir_faires_hsc(self, auth_client, ids, app):
        activity_id = _make_activity(app, ids["entity_id"], "Act. items complète")
        with app.app_context():
            from Code.extensions import db
            from Code.models.models import Savoir, SavoirFaire, Softskill

            db.session.add(Savoir(description="Savoir A", activity_id=activity_id))
            db.session.add(SavoirFaire(description="Savoir-faire A", activity_id=activity_id))
            db.session.add(Softskill(habilete="Rigueur", niveau="2", activity_id=activity_id))
            db.session.commit()

        r = auth_client.get(f"/your_api/activity_items/{activity_id}")
        assert r.status_code == 200
        payload = r.get_json()
        assert [item["name"] for item in payload["savoirs"]] == ["Savoir A"]
        assert [item["name"] for item in payload["savoir_faire"]] == ["Savoir-faire A"]
        assert payload["hsc"][0]["name"] == "Rigueur (2)"

    def test_activity_items_no_niveau_omits_parentheses(self, auth_client, ids, app):
        activity_id = _make_activity(app, ids["entity_id"], "Act. items sans niveau")
        with app.app_context():
            from Code.extensions import db
            from Code.models.models import Softskill

            db.session.add(Softskill(habilete="Ecoute", niveau="", activity_id=activity_id))
            db.session.commit()

        r = auth_client.get(f"/your_api/activity_items/{activity_id}")
        assert r.status_code == 200
        assert r.get_json()["hsc"][0]["name"] == "Ecoute"

    def test_activity_items_unknown_activity_returns_empty_lists(self, auth_client):
        r = auth_client.get("/your_api/activity_items/999999")
        assert r.status_code == 200
        payload = r.get_json()
        assert payload == {"savoirs": [], "savoir_faire": [], "hsc": []}

    def test_activity_items_no_auth_still_reachable(self, client):
        # Route non protégée : elle répond que le client soit authentifié ou non.
        r = client.get("/your_api/activity_items/999999")
        assert r.status_code == 200
