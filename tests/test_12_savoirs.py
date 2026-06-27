# tests/test_12_savoirs.py
"""
Tests pour les savoirs (savoirs.py).
Couverture : CRUD complet, validation, cas limites, rendu HTML.
"""
import json
import pytest


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _put(client, url, payload):
    return client.put(url, data=json.dumps(payload), content_type="application/json")


class TestSavoirsCRUD:
    """CRUD complet des savoirs d'activité."""

    _sid = None

    def test_add_savoir_success(self, auth_client, ids):
        r = _post(auth_client, "/savoirs/add", {
            "description": "Savoir test isolé 12",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        assert data["description"] == "Savoir test isolé 12"
        TestSavoirsCRUD._sid = data["id"]

    def test_add_savoir_missing_description(self, auth_client, ids):
        r = _post(auth_client, "/savoirs/add", {
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "error" in data

    def test_add_savoir_empty_description(self, auth_client, ids):
        r = _post(auth_client, "/savoirs/add", {
            "description": "   ",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 400

    def test_add_savoir_missing_activity_id(self, auth_client):
        r = _post(auth_client, "/savoirs/add", {
            "description": "Sans activity_id",
        })
        assert r.status_code == 400

    def test_add_savoir_activity_not_found(self, auth_client):
        r = _post(auth_client, "/savoirs/add", {
            "description": "Activité inexistante",
            "activity_id": 999999,
        })
        assert r.status_code == 404

    def test_update_savoir_success(self, auth_client, ids):
        if not TestSavoirsCRUD._sid:
            pytest.skip("Aucun savoir créé")
        r = _put(auth_client, f"/savoirs/{ids['activity_id']}/{TestSavoirsCRUD._sid}", {
            "description": "Savoir modifié isolé 12",
        })
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["description"] == "Savoir modifié isolé 12"

    def test_update_savoir_missing_description(self, auth_client, ids):
        if not TestSavoirsCRUD._sid:
            pytest.skip("Aucun savoir créé")
        r = _put(auth_client, f"/savoirs/{ids['activity_id']}/{TestSavoirsCRUD._sid}", {})
        assert r.status_code == 400

    def test_update_savoir_empty_description(self, auth_client, ids):
        if not TestSavoirsCRUD._sid:
            pytest.skip("Aucun savoir créé")
        r = _put(auth_client, f"/savoirs/{ids['activity_id']}/{TestSavoirsCRUD._sid}", {
            "description": "   "
        })
        assert r.status_code == 400

    def test_update_savoir_not_found(self, auth_client, ids):
        r = _put(auth_client, f"/savoirs/{ids['activity_id']}/999999", {
            "description": "Inexistant"
        })
        assert r.status_code == 404

    def test_update_savoir_wrong_activity(self, auth_client, ids):
        if not TestSavoirsCRUD._sid:
            pytest.skip("Aucun savoir créé")
        r = _put(auth_client, f"/savoirs/999999/{TestSavoirsCRUD._sid}", {
            "description": "Mauvaise activité"
        })
        assert r.status_code == 404

    def test_render_savoirs_success(self, auth_client, ids):
        r = auth_client.get(f"/savoirs/{ids['activity_id']}/render")
        assert r.status_code == 200

    def test_render_savoirs_activity_not_found(self, auth_client):
        r = auth_client.get("/savoirs/999999/render")
        assert r.status_code == 404

    def test_delete_savoir_success(self, auth_client, ids):
        # Créer un savoir dédié à la suppression
        r = _post(auth_client, "/savoirs/add", {
            "description": "Savoir à supprimer",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        sid = json.loads(r.data)["id"]

        r = auth_client.delete(f"/savoirs/{ids['activity_id']}/{sid}")
        assert r.status_code == 200

    def test_delete_savoir_not_found(self, auth_client, ids):
        r = auth_client.delete(f"/savoirs/{ids['activity_id']}/999999")
        assert r.status_code == 404

    def test_delete_savoir_wrong_activity(self, auth_client, ids):
        if not TestSavoirsCRUD._sid:
            pytest.skip("Aucun savoir créé")
        r = auth_client.delete(f"/savoirs/999999/{TestSavoirsCRUD._sid}")
        assert r.status_code == 404

    def test_delete_savoir_cleanup(self, auth_client, ids):
        """Nettoyage : supprime le savoir créé au début."""
        if not TestSavoirsCRUD._sid:
            pytest.skip("Rien à nettoyer")
        auth_client.delete(f"/savoirs/{ids['activity_id']}/{TestSavoirsCRUD._sid}")
        TestSavoirsCRUD._sid = None
