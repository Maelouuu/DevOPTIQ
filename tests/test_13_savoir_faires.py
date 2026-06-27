# tests/test_13_savoir_faires.py
"""
Tests pour les savoir-faires (savoir_faires.py).
Couverture : ajout unitaire, ajout en lot, CRUD complet, validation, rendu HTML.
"""
import json
import pytest


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _put(client, url, payload):
    return client.put(url, data=json.dumps(payload), content_type="application/json")


class TestSavoirFairesCRUD:
    """CRUD complet des savoir-faires."""

    _sf_id = None

    def test_add_savoir_faire_single(self, auth_client, ids):
        r = _post(auth_client, "/savoir_faires/add", {
            "activity_id": ids["activity_id"],
            "description": "SF unitaire isolé 13",
        })
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        assert data["description"] == "SF unitaire isolé 13"
        TestSavoirFairesCRUD._sf_id = data["id"]

    def test_add_savoir_faire_bulk(self, auth_client, ids):
        r = _post(auth_client, "/savoir_faires/add", {
            "activity_id": ids["activity_id"],
            "savoir_faires": ["SF lot A", "SF lot B", "SF lot C"],
        })
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data.get("created") == 3
        assert len(data.get("items", [])) == 3

    def test_add_savoir_faire_bulk_skips_empty(self, auth_client, ids):
        r = _post(auth_client, "/savoir_faires/add", {
            "activity_id": ids["activity_id"],
            "savoir_faires": ["SF valide", "", "   "],
        })
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data.get("created") == 1

    def test_add_savoir_faire_missing_activity_id(self, auth_client):
        r = _post(auth_client, "/savoir_faires/add", {
            "description": "Sans activity_id",
        })
        assert r.status_code == 400

    def test_add_savoir_faire_activity_not_found(self, auth_client):
        r = _post(auth_client, "/savoir_faires/add", {
            "activity_id": 999999,
            "description": "Activité inexistante",
        })
        assert r.status_code == 404

    def test_add_savoir_faire_missing_description(self, auth_client, ids):
        r = _post(auth_client, "/savoir_faires/add", {
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 400

    def test_add_savoir_faire_empty_description(self, auth_client, ids):
        r = _post(auth_client, "/savoir_faires/add", {
            "activity_id": ids["activity_id"],
            "description": "   ",
        })
        assert r.status_code == 400

    def test_update_savoir_faire_success(self, auth_client, ids):
        if not TestSavoirFairesCRUD._sf_id:
            pytest.skip("Aucun SF créé")
        r = _put(auth_client,
                 f"/savoir_faires/{ids['activity_id']}/{TestSavoirFairesCRUD._sf_id}",
                 {"description": "SF modifié isolé 13"})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["description"] == "SF modifié isolé 13"

    def test_update_savoir_faire_missing_description(self, auth_client, ids):
        if not TestSavoirFairesCRUD._sf_id:
            pytest.skip("Aucun SF créé")
        r = _put(auth_client,
                 f"/savoir_faires/{ids['activity_id']}/{TestSavoirFairesCRUD._sf_id}",
                 {})
        assert r.status_code == 400

    def test_update_savoir_faire_empty_description(self, auth_client, ids):
        if not TestSavoirFairesCRUD._sf_id:
            pytest.skip("Aucun SF créé")
        r = _put(auth_client,
                 f"/savoir_faires/{ids['activity_id']}/{TestSavoirFairesCRUD._sf_id}",
                 {"description": "   "})
        assert r.status_code == 400

    def test_update_savoir_faire_not_found(self, auth_client, ids):
        r = _put(auth_client, f"/savoir_faires/{ids['activity_id']}/999999",
                 {"description": "Inexistant"})
        assert r.status_code == 404

    def test_update_savoir_faire_wrong_activity(self, auth_client, ids):
        if not TestSavoirFairesCRUD._sf_id:
            pytest.skip("Aucun SF créé")
        r = _put(auth_client,
                 f"/savoir_faires/999999/{TestSavoirFairesCRUD._sf_id}",
                 {"description": "Mauvaise activité"})
        assert r.status_code == 404

    def test_render_savoir_faires_success(self, auth_client, ids):
        r = auth_client.get(f"/savoir_faires/{ids['activity_id']}/render")
        assert r.status_code == 200

    def test_render_savoir_faires_not_found(self, auth_client):
        r = auth_client.get("/savoir_faires/999999/render")
        assert r.status_code == 404

    def test_delete_savoir_faire_success(self, auth_client, ids):
        r = _post(auth_client, "/savoir_faires/add", {
            "activity_id": ids["activity_id"],
            "description": "SF à supprimer",
        })
        assert r.status_code == 201
        sf_id = json.loads(r.data)["id"]

        r = auth_client.delete(f"/savoir_faires/{ids['activity_id']}/{sf_id}")
        assert r.status_code == 200

    def test_delete_savoir_faire_not_found(self, auth_client, ids):
        r = auth_client.delete(f"/savoir_faires/{ids['activity_id']}/999999")
        assert r.status_code == 404

    def test_delete_savoir_faire_wrong_activity(self, auth_client, ids):
        if not TestSavoirFairesCRUD._sf_id:
            pytest.skip("Aucun SF créé")
        r = auth_client.delete(f"/savoir_faires/999999/{TestSavoirFairesCRUD._sf_id}")
        assert r.status_code == 404

    def test_delete_savoir_faire_cleanup(self, auth_client, ids):
        """Nettoyage du SF créé au début."""
        if not TestSavoirFairesCRUD._sf_id:
            pytest.skip("Rien à nettoyer")
        auth_client.delete(
            f"/savoir_faires/{ids['activity_id']}/{TestSavoirFairesCRUD._sf_id}"
        )
        TestSavoirFairesCRUD._sf_id = None
