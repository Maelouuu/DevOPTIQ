# tests/test_60_activity_items_extras.py
"""
Pages : API "items d'activité" pour le plan de formation (/your_api/activity_items)
        + endpoints legacy d'ajout via le blueprint activités (/activities/constraints/add,
        /activities/data/add).
Aucun de ces trois endpoints n'avait de couverture dédiée avant ce fichier.
"""
import json

import pytest

pytestmark = pytest.mark.activity_items_extras


# ---------------------------------------------------------------------------
# Helpers — isolation : activité dédiée + items dédiés, nettoyés après coup.
# ---------------------------------------------------------------------------

def _create_activity(app, entity_id, name):
    with app.app_context():
        from Code.extensions import db
        from Code.models.models import Activities
        a = Activities(entity_id=entity_id, name=name, description="")
        db.session.add(a)
        db.session.commit()
        return a.id


def _delete_activity(app, activity_id):
    with app.app_context():
        from Code.extensions import db
        from Code.models.models import Activities
        a = Activities.query.get(activity_id)
        if a:
            db.session.delete(a)
            db.session.commit()


def _add_items(app, activity_id):
    with app.app_context():
        from Code.extensions import db
        from Code.models.models import Savoir, SavoirFaire, Softskill
        sv = Savoir(activity_id=activity_id, description="Connaître les normes qualité")
        sf = SavoirFaire(activity_id=activity_id, description="Réaliser un contrôle qualité")
        hsc = Softskill(activity_id=activity_id, habilete="Rigueur", niveau="3")
        db.session.add_all([sv, sf, hsc])
        db.session.commit()
        return {"savoir_id": sv.id, "savoir_faire_id": sf.id, "softskill_id": hsc.id}


# ===========================================================================
# 1. GET /your_api/activity_items/<activity_id>
# ===========================================================================

class TestActivityItemsApi:

    def test_items_returns_savoirs_savoir_faire_hsc(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Items Test")
        try:
            _add_items(app, aid)
            r = auth_client.get(f"/your_api/activity_items/{aid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert len(data["savoirs"]) == 1
            assert data["savoirs"][0]["name"] == "Connaître les normes qualité"
            assert len(data["savoir_faire"]) == 1
            assert data["savoir_faire"][0]["name"] == "Réaliser un contrôle qualité"
            assert len(data["hsc"]) == 1
        finally:
            _delete_activity(app, aid)

    def test_items_hsc_label_includes_niveau(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité HSC Label Test")
        try:
            _add_items(app, aid)
            r = auth_client.get(f"/your_api/activity_items/{aid}")
            data = json.loads(r.data)
            assert data["hsc"][0]["name"] == "Rigueur (3)"
        finally:
            _delete_activity(app, aid)

    def test_items_empty_activity_returns_empty_lists(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], "Activité Sans Items")
        try:
            r = auth_client.get(f"/your_api/activity_items/{aid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data == {"savoirs": [], "savoir_faire": [], "hsc": []}
        finally:
            _delete_activity(app, aid)

    def test_items_unknown_activity_returns_empty_lists(self, auth_client):
        r = auth_client.get("/your_api/activity_items/999999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == {"savoirs": [], "savoir_faire": [], "hsc": []}


# ===========================================================================
# 2. POST /activities/constraints/add
# ===========================================================================

class TestActivitiesBlueprintAddConstraint:

    def test_add_constraint_success(self, auth_client, app, ids):
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"activity_id": ids["activity_id"], "description": "Contrainte legacy"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data).get("message")

        with app.app_context():
            from Code.extensions import db
            from Code.models.models import Constraint
            row = Constraint.query.filter_by(
                activity_id=ids["activity_id"], description="Contrainte legacy"
            ).first()
            assert row is not None
            db.session.delete(row)
            db.session.commit()

    def test_add_constraint_missing_activity_id_400(self, auth_client):
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"description": "Sans activité"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_constraint_missing_description_400(self, auth_client, ids):
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_constraint_empty_body_400(self, auth_client):
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ===========================================================================
# 3. POST /activities/data/add
# ===========================================================================

class TestActivitiesBlueprintAddData:

    def test_add_data_success(self, auth_client, app):
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"name": "Donnée legacy", "type": "nourrissante"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data).get("message")

        with app.app_context():
            from Code.extensions import db
            from Code.models.models import Data
            row = Data.query.filter_by(name="Donnée legacy", type="nourrissante").first()
            assert row is not None
            db.session.delete(row)
            db.session.commit()

    def test_add_data_missing_name_400(self, auth_client):
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"type": "nourrissante"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_data_missing_type_400(self, auth_client):
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"name": "Donnée sans type"}),
            content_type="application/json",
        )
        assert r.status_code == 400
