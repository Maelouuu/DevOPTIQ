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

    def test_add_aptitude_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Peu importe", "activity_id": 999999}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert r.get_json()["error"] == "Activity not found"

    def test_update_aptitude_empty_description_returns_400(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import Aptitude
            from Code.extensions import db
            a = Aptitude(description="Avant", activity_id=ids["activity_id"])
            db.session.add(a)
            db.session.commit()
            apt_id = a.id
        try:
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{apt_id}",
                data=json.dumps({"description": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "description is required"
        finally:
            with app.app_context():
                from Code.models.models import Aptitude
                from Code.extensions import db
                obj = Aptitude.query.get(apt_id)
                if obj:
                    db.session.delete(obj)
                    db.session.commit()

    def test_update_aptitude_not_found_returns_404(self, auth_client, ids):
        r = auth_client.put(
            f"/aptitudes/{ids['activity_id']}/999999",
            data=json.dumps({"description": "Peu importe"}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert r.get_json()["error"] == "Aptitude not found"

    def test_render_aptitudes_unknown_activity_returns_404(self, auth_client):
        r = auth_client.get("/aptitudes/999999/render")
        assert r.status_code == 404
        assert r.get_json()["error"] == "Activité non trouvée"


class TestAptitudesDbErrors:
    """Force un échec de commit pour couvrir les branches except (500 + rollback)."""

    def _break_commit(self, monkeypatch, app):
        with app.app_context():
            from Code.extensions import db
            def _boom(*a, **kw):
                raise RuntimeError("panne DB simulée")
            monkeypatch.setattr(db.session, "commit", _boom)

    def test_add_aptitude_db_error_returns_500(self, auth_client, ids, app, monkeypatch):
        self._break_commit(monkeypatch, app)
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Va échouer", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 500
        assert "panne DB simulée" in r.get_json()["error"]

    def test_update_aptitude_db_error_returns_500(self, auth_client, ids, app, monkeypatch):
        with app.app_context():
            from Code.models.models import Aptitude
            from Code.extensions import db
            a = Aptitude(description="Avant échec", activity_id=ids["activity_id"])
            db.session.add(a)
            db.session.commit()
            apt_id = a.id
        try:
            self._break_commit(monkeypatch, app)
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{apt_id}",
                data=json.dumps({"description": "Nouvelle valeur"}),
                content_type="application/json",
            )
            assert r.status_code == 500
            assert "panne DB simulée" in r.get_json()["error"]
        finally:
            monkeypatch.undo()
            with app.app_context():
                from Code.models.models import Aptitude
                from Code.extensions import db
                obj = Aptitude.query.get(apt_id)
                if obj:
                    db.session.delete(obj)
                    db.session.commit()

    def test_delete_aptitude_db_error_returns_500(self, auth_client, ids, app, monkeypatch):
        with app.app_context():
            from Code.models.models import Aptitude
            from Code.extensions import db
            a = Aptitude(description="Sera gardée (échec suppression)", activity_id=ids["activity_id"])
            db.session.add(a)
            db.session.commit()
            apt_id = a.id
        try:
            self._break_commit(monkeypatch, app)
            r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
            assert r.status_code == 500
            assert "panne DB simulée" in r.get_json()["error"]
        finally:
            monkeypatch.undo()
            with app.app_context():
                from Code.models.models import Aptitude
                from Code.extensions import db
                obj = Aptitude.query.get(apt_id)
                if obj:
                    db.session.delete(obj)
                    db.session.commit()
