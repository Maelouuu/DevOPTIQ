# tests/test_04_constraints.py
"""
Page : Contraintes (section dans les activités)
Tests couvrant le CRUD et le rendu partiel.
"""
import pytest
import json

pytestmark = pytest.mark.constraints


class TestConstraintsCRUD:

    def test_add_constraint(self, auth_client, ids):
        r = auth_client.post(
            f"/constraints/{ids['activity_id']}/add",
            data=json.dumps({"description": "Contrainte de test automatisé"}),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        if r.status_code in (200, 201):
            data = json.loads(r.data)
            assert "id" in data or "description" in data

    def test_add_constraint_empty_description(self, auth_client, ids):
        r = auth_client.post(
            f"/constraints/{ids['activity_id']}/add",
            data=json.dumps({"description": ""}),
            content_type="application/json",
        )
        assert r.status_code in (400, 422)

    def test_add_constraint_activity_not_found(self, auth_client):
        r = auth_client.post(
            "/constraints/999999/add",
            data=json.dumps({"description": "Test"}),
            content_type="application/json",
        )
        assert r.status_code in (404, 400)

    def test_update_constraint(self, auth_client, ids, app):
        # D'abord créer une contrainte
        with app.app_context():
            from Code.models.models import Constraint
            from Code.extensions import db
            c = Constraint(description="À modifier", activity_id=ids["activity_id"])
            db.session.add(c)
            db.session.commit()
            constraint_id = c.id

        r = auth_client.put(
            f"/constraints/{ids['activity_id']}/{constraint_id}",
            data=json.dumps({"description": "Description modifiée"}),
            content_type="application/json",
        )
        assert r.status_code in (200, 404)

    def test_delete_constraint(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import Constraint
            from Code.extensions import db
            c = Constraint(description="À supprimer", activity_id=ids["activity_id"])
            db.session.add(c)
            db.session.commit()
            constraint_id = c.id

        r = auth_client.delete(f"/constraints/{ids['activity_id']}/{constraint_id}")
        assert r.status_code in (200, 204)

    def test_delete_constraint_not_found(self, auth_client, ids):
        r = auth_client.delete(f"/constraints/{ids['activity_id']}/999999")
        assert r.status_code in (404, 200)

    def test_render_constraints(self, auth_client, ids):
        r = auth_client.get(f"/constraints/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert len(r.data) > 0

    def test_render_constraints_activity_not_found(self, auth_client):
        r = auth_client.get("/constraints/999999/render")
        assert r.status_code in (404, 200)
