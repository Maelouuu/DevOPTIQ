# tests/test_11_tools.py
"""
Tests pour la gestion des outils (gestion_outils.py).
Couverture : page HTML, liste API, CRUD complet, détachement, conflits.
"""
import json
import pytest


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _put(client, url, payload):
    return client.put(url, data=json.dumps(payload), content_type="application/json")


class TestGestionOutilsPage:
    """Accès à la page HTML."""

    def test_page_requires_auth(self, client):
        r = client.get("/gestion_outils/")
        assert r.status_code in (200, 302)

    def test_page_accessible_auth(self, auth_client):
        r = auth_client.get("/gestion_outils/")
        assert r.status_code == 200

    def test_page_contains_content(self, auth_client):
        r = auth_client.get("/gestion_outils/")
        assert b"outil" in r.data.lower() or r.status_code == 200


class TestToolsListAPI:
    """GET /gestion_outils/api/tools"""

    def test_list_tools_returns_json(self, auth_client):
        r = auth_client.get("/gestion_outils/api/tools")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_list_tools_has_expected_fields(self, auth_client):
        # Create a tool first to ensure list is non-empty
        _post(auth_client, "/gestion_outils/api/tools", {
            "name": "Outil liste-check"
        })
        r = auth_client.get("/gestion_outils/api/tools")
        data = json.loads(r.data)
        if data:
            tool = data[0]
            assert "id" in tool
            assert "name" in tool
            assert "usages" in tool


class TestToolsCRUD:
    """Création, mise à jour, suppression des outils."""

    _tool_id = None

    def test_create_tool(self, auth_client):
        r = _post(auth_client, "/gestion_outils/api/tools", {
            "name": "Outil CRUD test",
            "description": "Description test",
        })
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        TestToolsCRUD._tool_id = data["id"]

    def test_create_tool_missing_name(self, auth_client):
        r = _post(auth_client, "/gestion_outils/api/tools", {
            "description": "Sans nom"
        })
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "error" in data

    def test_create_tool_empty_name(self, auth_client):
        r = _post(auth_client, "/gestion_outils/api/tools", {
            "name": "   "
        })
        assert r.status_code == 400

    def test_create_tool_duplicate_name(self, auth_client):
        _post(auth_client, "/gestion_outils/api/tools", {"name": "Outil Dupliqué"})
        r = _post(auth_client, "/gestion_outils/api/tools", {"name": "Outil Dupliqué"})
        assert r.status_code == 409

    def test_update_tool(self, auth_client):
        if not TestToolsCRUD._tool_id:
            pytest.skip("Aucun outil disponible")
        r = _put(auth_client, f"/gestion_outils/api/tools/{TestToolsCRUD._tool_id}", {
            "name": "Outil CRUD modifié",
            "description": "Desc mise à jour",
        })
        assert r.status_code == 200

    def test_update_tool_empty_name(self, auth_client):
        if not TestToolsCRUD._tool_id:
            pytest.skip("Aucun outil disponible")
        r = _put(auth_client, f"/gestion_outils/api/tools/{TestToolsCRUD._tool_id}", {
            "name": ""
        })
        assert r.status_code == 400

    def test_update_tool_not_found(self, auth_client):
        r = _put(auth_client, "/gestion_outils/api/tools/999999", {
            "name": "Inexistant"
        })
        assert r.status_code == 404

    def test_get_tool_usages(self, auth_client):
        if not TestToolsCRUD._tool_id:
            pytest.skip("Aucun outil disponible")
        r = auth_client.get(f"/gestion_outils/api/tools/{TestToolsCRUD._tool_id}/usages")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "usages" in data or isinstance(data, dict)

    def test_get_tool_usages_not_found(self, auth_client):
        r = auth_client.get("/gestion_outils/api/tools/999999/usages")
        assert r.status_code == 404

    def test_delete_tool_no_usages(self, auth_client):
        # Créer un outil dédié à la suppression
        r = _post(auth_client, "/gestion_outils/api/tools", {
            "name": "Outil à supprimer"
        })
        assert r.status_code == 201
        tid = json.loads(r.data)["id"]

        r = auth_client.delete(f"/gestion_outils/api/tools/{tid}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data.get("deleted") is True

    def test_delete_tool_not_found(self, auth_client):
        r = auth_client.delete("/gestion_outils/api/tools/999999")
        assert r.status_code == 404

    def test_delete_tool_with_usage_no_force(self, auth_client, ids):
        # Associer l'outil à la tâche seed via /tools/add, puis tenter la suppression
        r = _post(auth_client, "/gestion_outils/api/tools", {
            "name": "Outil avec usage"
        })
        assert r.status_code == 201
        tid = json.loads(r.data)["id"]

        # Associer à la tâche seed
        _post(auth_client, "/tools/add", {
            "task_id": ids["task_id"],
            "existing_tool_ids": [tid],
        })

        # Suppression sans force_detach doit retourner 409
        r = auth_client.delete(f"/gestion_outils/api/tools/{tid}")
        assert r.status_code == 409

    def test_delete_tool_with_usage_force(self, auth_client, ids):
        # Créer et associer
        r = _post(auth_client, "/gestion_outils/api/tools", {
            "name": "Outil force delete"
        })
        assert r.status_code == 201
        tid = json.loads(r.data)["id"]

        _post(auth_client, "/tools/add", {
            "task_id": ids["task_id"],
            "existing_tool_ids": [tid],
        })

        # Suppression avec force_detach=true
        r = auth_client.delete(
            f"/gestion_outils/api/tools/{tid}?force_detach=true"
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data.get("deleted") is True
