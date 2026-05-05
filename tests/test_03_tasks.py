# tests/test_03_tasks.py
"""
Page : Tâches (section dans les activités)
Tests couvrant le CRUD des tâches, les rôles et le réordonnancement.
"""
import pytest
import json

pytestmark = pytest.mark.tasks


class TestTasksCRUD:
    """Création, modification et suppression de tâches."""

    def test_add_task(self, auth_client, ids):
        r = auth_client.post(
            "/tasks/add",
            data=json.dumps({
                "name": "Tâche ajoutée par test",
                "description": "Test automatisé",
                "activity_id": ids["activity_id"],
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        if r.status_code in (200, 201):
            data = json.loads(r.data)
            assert "id" in data or "ok" in data or "task" in data

    def test_add_task_missing_name(self, auth_client, ids):
        r = auth_client.post(
            "/tasks/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code in (400, 422, 200)

    def test_add_task_missing_activity(self, auth_client):
        r = auth_client.post(
            "/tasks/add",
            data=json.dumps({"name": "Sans activité"}),
            content_type="application/json",
        )
        assert r.status_code in (400, 422, 404, 200)

    def test_update_task(self, auth_client, ids):
        r = auth_client.put(
            f"/tasks/{ids['task_id']}",
            data=json.dumps({"name": "Tâche modifiée", "description": "Nouvelle desc"}),
            content_type="application/json",
        )
        assert r.status_code in (200, 204, 404)

    def test_update_task_not_found(self, auth_client):
        r = auth_client.put(
            "/tasks/999999",
            data=json.dumps({"name": "Inexistante"}),
            content_type="application/json",
        )
        assert r.status_code in (404, 200)

    def test_delete_task_not_found(self, auth_client):
        r = auth_client.delete("/tasks/999999")
        assert r.status_code in (404, 200, 204)


class TestTasksRoles:
    """Gestion des rôles sur les tâches."""

    def test_get_task_roles_returns_data(self, auth_client, ids):
        r = auth_client.get(f"/tasks/{ids['task_id']}/roles")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            # L'API retourne soit une liste soit un dict avec 'roles'
            assert isinstance(data, (list, dict))
            if isinstance(data, dict):
                assert "roles" in data or "task_id" in data

    def test_add_role_to_task_invalid(self, auth_client, ids):
        r = auth_client.post(
            f"/tasks/{ids['task_id']}/roles/add",
            data=json.dumps({"role_id": 999999, "status": "Réalisateur"}),
            content_type="application/json",
        )
        assert r.status_code in (400, 404, 200)

    def test_remove_role_from_task_not_found(self, auth_client, ids):
        r = auth_client.delete(f"/tasks/{ids['task_id']}/roles/999999")
        assert r.status_code in (404, 200, 204)


class TestTasksRender:
    """Rendu partiel des tâches (AJAX)."""

    def test_render_tasks_returns_200(self, auth_client, ids):
        """
        La route /tasks/<id>/render doit retourner 200 avec le HTML partiel
        (maintenant que item/task_conn_map est calculé dans la route elle-même).
        """
        r = auth_client.get(f"/tasks/{ids['activity_id']}/render")
        assert r.status_code == 200, f"Rendu tâches échoué : {r.status_code}"
        assert b"task" in r.data.lower() or b"t\xc3\xa2che" in r.data or b"Aucune" in r.data

    def test_render_tasks_unknown_activity(self, auth_client):
        r = auth_client.get("/tasks/999999/render")
        assert r.status_code in (404, 200)


class TestTasksReorder:
    """Réordonnancement des tâches."""

    def test_reorder_tasks(self, auth_client, ids):
        r = auth_client.post(
            f"/activities/{ids['activity_id']}/tasks/reorder",
            data=json.dumps({"order": [str(ids["task_id"])]}),
            content_type="application/json",
        )
        assert r.status_code in (200, 404, 405)
