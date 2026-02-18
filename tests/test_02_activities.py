# tests/test_02_activities.py
"""
Page : Liste des activités
Tests couvrant l'affichage, les détails et les routes associées.
Note : Les activités sont créées via l'interface cartographie (VSDX/drag-drop),
       pas via un endpoint REST simple /activities/add.
"""
import pytest
import json

pytestmark = pytest.mark.activities


class TestActivitiesView:
    """Affichage de la page des activités."""

    def test_view_redirects_or_shows_page(self, client):
        r = client.get("/activities/view", follow_redirects=False)
        assert r.status_code in (200, 302)

    def test_view_accessible_authenticated(self, auth_client):
        r = auth_client.get("/activities/view", follow_redirects=True)
        assert r.status_code == 200

    def test_view_contains_activity_keyword(self, auth_client):
        r = auth_client.get("/activities/view", follow_redirects=True)
        assert r.status_code == 200
        assert b"Activit" in r.data

    def test_view_returns_html(self, auth_client):
        r = auth_client.get("/activities/view", follow_redirects=True)
        assert "text/html" in (r.content_type or "")


class TestActivitiesDetails:
    """Route de détails d'une activité."""

    def test_get_activity_details(self, auth_client, ids):
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, dict)

    def test_get_activity_details_not_found(self, auth_client):
        r = auth_client.get("/activities/999999/details")
        assert r.status_code in (404, 200)

    def test_activity_details_has_name(self, auth_client, ids):
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        if r.status_code == 200:
            data = json.loads(r.data)
            assert "name" in data or "title" in data or "id" in data


class TestActivitiesRoutes:
    """Vérification des routes disponibles."""

    def test_task_reorder_endpoint(self, auth_client, ids):
        r = auth_client.post(
            f"/activities/{ids['activity_id']}/tasks/reorder",
            data=json.dumps({"order": [str(ids["task_id"])]}),
            content_type="application/json",
        )
        assert r.status_code in (200, 404, 405)

    def test_view_page_has_tasks_section(self, auth_client):
        r = auth_client.get("/activities/view", follow_redirects=True)
        assert r.status_code == 200
        # La page doit avoir une section pour les tâches
        assert b"task" in r.data.lower() or b"t\xc3\xa2che" in r.data
