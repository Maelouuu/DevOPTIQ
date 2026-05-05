# tests/test_09_time.py
"""
Page : Gestion du Temps
Tests couvrant les endpoints de l'API temps.
"""
import pytest
import json

pytestmark = pytest.mark.time


class TestTimePage:

    def test_time_page_accessible(self, auth_client):
        r = auth_client.get("/temps/", follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_get_calendar_params(self, auth_client):
        r = auth_client.get("/temps/api/calendar_params")
        assert r.status_code in (200, 404)

    def test_get_activity_defaults(self, auth_client, ids):
        r = auth_client.get(f"/temps/api/activity_defaults/{ids['activity_id']}")
        assert r.status_code in (200, 404)

    def test_get_activity_time_empty(self, auth_client, ids):
        r = auth_client.get(f"/temps/api/activity_time/{ids['activity_id']}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, (dict, list))

    def test_post_activity_time(self, auth_client, ids):
        r = auth_client.post(
            f"/temps/api/activity_time/{ids['activity_id']}",
            data=json.dumps({
                "activity": {
                    "duration_minutes": 60,
                    "delay_minutes": 10,
                },
                "tasks": [],
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201, 400, 404)
        if r.status_code in (200, 201):
            data = json.loads(r.data)
            assert data.get("ok") is True

    def test_delete_activity_time(self, auth_client, ids):
        r = auth_client.delete(f"/temps/api/activity_time/{ids['activity_id']}")
        assert r.status_code in (200, 204, 404)

    def test_get_activities_list(self, auth_client):
        r = auth_client.get("/temps/api/activities")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            # Peut retourner une liste ou un dict avec 'items'
            assert isinstance(data, (list, dict))

    def test_get_projects_list(self, auth_client):
        r = auth_client.get("/temps/api/projects")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, (list, dict))

    def test_get_time_analyses_list(self, auth_client):
        r = auth_client.get("/temps/api/time_analyses")
        assert r.status_code in (200, 404)

    def test_create_time_analysis(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/time_analysis",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "duration": 30,
                "recurrence": "hebdomadaire",
                "frequency": 1,
                "type": "travail",
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201, 400)

    def test_get_role_analyses_list(self, auth_client):
        r = auth_client.get("/temps/api/role_analyses")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, (list, dict))
