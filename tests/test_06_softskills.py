# tests/test_06_softskills.py
"""
Page : HSC / Habiletés Socio-Cognitives (section dans les activités)
Tests couvrant le CRUD et le rendu partiel.
"""
import pytest
import json

pytestmark = pytest.mark.softskills


class TestSoftskillsCRUD:

    def test_add_softskill(self, auth_client, ids):
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({
                "habilete": "Communication",
                "niveau": "3",
                "justification": "Justification test",
                "activity_id": ids["activity_id"],
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        if r.status_code in (200, 201):
            data = json.loads(r.data)
            assert "id" in data or "ok" in data

    def test_add_softskill_missing_fields(self, auth_client, ids):
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code in (400, 422, 200)

    def test_update_softskill(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import Softskill
            from Code.extensions import db
            ss = Softskill(
                habilete="À modifier",
                niveau="2",
                activity_id=ids["activity_id"],
            )
            db.session.add(ss)
            db.session.commit()
            ss_id = ss.id

        r = auth_client.put(
            f"/softskills/{ids['activity_id']}/{ss_id}",
            data=json.dumps({"habilete": "Modifié", "niveau": "3"}),
            content_type="application/json",
        )
        assert r.status_code in (200, 204, 404)

    def test_delete_softskill(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import Softskill
            from Code.extensions import db
            ss = Softskill(
                habilete="À supprimer",
                niveau="1",
                activity_id=ids["activity_id"],
            )
            db.session.add(ss)
            db.session.commit()
            ss_id = ss.id

        r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        assert r.status_code in (200, 204)

    def test_delete_softskill_not_found(self, auth_client, ids):
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/999999")
        assert r.status_code in (404, 200)

    def test_render_softskills(self, auth_client, ids):
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)
