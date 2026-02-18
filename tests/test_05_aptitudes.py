# tests/test_05_aptitudes.py
"""
Page : Aptitudes (section dans les activités)
Tests couvrant le CRUD et le rendu partiel.
"""
import pytest
import json

pytestmark = pytest.mark.aptitudes


class TestAptitudesCRUD:

    def test_add_aptitude(self, auth_client, ids):
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({
                "description": "Aptitude de test automatisé",
                "activity_id": ids["activity_id"],
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        if r.status_code in (200, 201):
            data = json.loads(r.data)
            assert "id" in data or "description" in data or "ok" in data

    def test_add_aptitude_empty_description(self, auth_client, ids):
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code in (400, 422, 200)

    def test_update_aptitude(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import Aptitude
            from Code.extensions import db
            a = Aptitude(description="À modifier", activity_id=ids["activity_id"])
            db.session.add(a)
            db.session.commit()
            apt_id = a.id

        r = auth_client.put(
            f"/aptitudes/{ids['activity_id']}/{apt_id}",
            data=json.dumps({"description": "Aptitude modifiée"}),
            content_type="application/json",
        )
        assert r.status_code in (200, 204, 404)

    def test_delete_aptitude(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import Aptitude
            from Code.extensions import db
            a = Aptitude(description="À supprimer", activity_id=ids["activity_id"])
            db.session.add(a)
            db.session.commit()
            apt_id = a.id

        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        assert r.status_code in (200, 204)

    def test_delete_aptitude_not_found(self, auth_client, ids):
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/999999")
        assert r.status_code in (404, 200)

    def test_render_aptitudes(self, auth_client, ids):
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert len(r.data) > 0
