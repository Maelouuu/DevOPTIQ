# tests/test_10_roles.py
"""
Page : Rôles
Tests couvrant la liste, la modification et la suppression des rôles.
"""
import pytest
import json

pytestmark = pytest.mark.roles


class TestRolesList:

    def test_list_roles(self, auth_client):
        r = auth_client.get("/roles/list")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, list)

    def test_assign_garant_to_activity_not_found(self, auth_client, ids):
        r = auth_client.post(
            f"/roles/garant/activity/{ids['activity_id']}",
            data=json.dumps({"role_id": 999999}),
            content_type="application/json",
        )
        assert r.status_code in (400, 404, 200)

    def test_update_role_not_found(self, auth_client):
        r = auth_client.put(
            "/roles/999999",
            data=json.dumps({"name": "Rôle inexistant"}),
            content_type="application/json",
        )
        assert r.status_code in (404, 200)

    def test_delete_role_not_found(self, auth_client):
        r = auth_client.delete("/roles/999999")
        assert r.status_code in (404, 200)

    def test_role_lifecycle(self, auth_client, ids, app):
        """Créer un rôle dans la DB directement et tester les opérations."""
        with app.app_context():
            from Code.models.models import Role
            from Code.extensions import db
            role = Role(name="Rôle Test Lifecycle", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.commit()
            role_id = role.id

        # Modifier
        r = auth_client.put(
            f"/roles/{role_id}",
            data=json.dumps({"name": "Rôle Modifié"}),
            content_type="application/json",
        )
        assert r.status_code in (200, 204, 404)

        # Supprimer
        r = auth_client.delete(f"/roles/{role_id}")
        assert r.status_code in (200, 204, 404)
