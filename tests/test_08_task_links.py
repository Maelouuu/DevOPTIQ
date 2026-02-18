# tests/test_08_task_links.py
"""
Page : Drag & Drop connexions → tâches
Tests couvrant les assignations de connexions aux tâches.
"""
import pytest
import json

pytestmark = pytest.mark.task_links


class TestTaskLinkAssignments:

    def test_assign_link_to_task(self, auth_client, ids, app):
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible")

        # Cleanup préventif pour éviter les conflits d'ordre d'exécution
        with app.app_context():
            from Code.extensions import db
            from sqlalchemy import text
            try:
                db.session.execute(
                    text("DELETE FROM task_link_assignments WHERE link_id=:lid AND direction='incoming'"),
                    {"lid": ids["link_id"]}
                )
                db.session.commit()
            except Exception:
                db.session.rollback()

        r = auth_client.post(
            "/task-links/assign",
            data=json.dumps({
                "link_id": ids["link_id"],
                "task_id": ids["task_id"],
                "direction": "incoming",
                "activity_id": ids["activity_id"],
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        data = json.loads(r.data)
        assert data.get("ok") is True

    def test_assign_missing_fields(self, auth_client):
        r = auth_client.post(
            "/task-links/assign",
            data=json.dumps({"link_id": 1}),
            content_type="application/json",
        )
        assert r.status_code in (400, 422)

    def test_get_assignments_for_activity(self, auth_client, ids):
        r = auth_client.get(f"/task-links/activity/{ids['activity_id']}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_get_assignments_empty_activity(self, auth_client):
        r = auth_client.get("/task-links/activity/999999")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, list)

    def test_unassign_link(self, auth_client, ids):
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible")

        # D'abord assigner pour pouvoir désassigner
        auth_client.post(
            "/task-links/assign",
            data=json.dumps({
                "link_id": ids["link_id"],
                "task_id": ids["task_id"],
                "direction": "outgoing",
                "activity_id": ids["activity_id"],
            }),
            content_type="application/json",
        )

        r = auth_client.delete(f"/task-links/{ids['link_id']}/outgoing")
        assert r.status_code in (200, 204)
        data = json.loads(r.data)
        assert data.get("ok") is True

    def test_unassign_nonexistent(self, auth_client):
        r = auth_client.delete("/task-links/999999/incoming")
        assert r.status_code in (200, 204)
        data = json.loads(r.data)
        assert data.get("ok") is True  # DELETE idempotent

    def test_assign_then_reassign(self, auth_client, ids):
        """Réassigner un lien déjà assigné doit fonctionner (upsert)."""
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible")

        payload = {
            "link_id": ids["link_id"],
            "task_id": ids["task_id"],
            "direction": "incoming",
            "activity_id": ids["activity_id"],
        }

        r1 = auth_client.post(
            "/task-links/assign",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r1.status_code in (200, 201)

        r2 = auth_client.post(
            "/task-links/assign",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r2.status_code in (200, 201)
        data = json.loads(r2.data)
        assert data.get("ok") is True
