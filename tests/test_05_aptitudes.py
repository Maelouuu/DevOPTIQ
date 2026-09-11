# tests/test_05_aptitudes.py
"""
Page : Aptitudes (section dans les activités)
Couvre : ajout, modification, suppression, rendu partiel, cas limites
(champs manquants, activité/aptitude introuvable) et erreurs DB.
"""
import pytest
import json

pytestmark = pytest.mark.aptitudes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_aptitude(app, activity_id, description="À modifier"):
    from Code.models.models import Aptitude
    from Code.extensions import db
    with app.app_context():
        a = Aptitude(description=description, activity_id=activity_id)
        db.session.add(a)
        db.session.commit()
        return a.id


def _delete_aptitude(app, aptitude_id):
    from Code.models.models import Aptitude
    from Code.extensions import db
    with app.app_context():
        a = Aptitude.query.get(aptitude_id)
        if a:
            db.session.delete(a)
            db.session.commit()


class TestAptitudesAdd:

    def test_add_aptitude_success(self, auth_client, ids, app):
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({
                "description": "Aptitude de test automatisé",
                "activity_id": ids["activity_id"],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["description"] == "Aptitude de test automatisé"
        assert "id" in data
        _delete_aptitude(app, data["id"])

    def test_add_aptitude_empty_description_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert json.loads(r.data)["error"] == "description and activity_id are required"

    def test_add_aptitude_missing_activity_id_returns_400(self, auth_client):
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Une aptitude"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_aptitude_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Une aptitude", "activity_id": 999999}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "Activity not found"

    def test_add_aptitude_db_error_rolls_back_and_returns_500(self, auth_client, ids, monkeypatch):
        from Code.extensions import db

        def _boom():
            raise RuntimeError("commit-boom-aptitude-add")

        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            r = auth_client.post(
                "/aptitudes/add",
                data=json.dumps({"description": "Va échouer", "activity_id": ids["activity_id"]}),
                content_type="application/json",
            )
        finally:
            monkeypatch.undo()
        assert r.status_code == 500
        assert "commit-boom-aptitude-add" in json.loads(r.data)["error"]


class TestAptitudesUpdate:

    def test_update_aptitude_success(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"])
        try:
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{apt_id}",
                data=json.dumps({"description": "Aptitude modifiée"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["id"] == apt_id
            assert data["description"] == "Aptitude modifiée"
        finally:
            _delete_aptitude(app, apt_id)

    def test_update_aptitude_empty_description_returns_400(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"])
        try:
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{apt_id}",
                data=json.dumps({"description": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert json.loads(r.data)["error"] == "description is required"
        finally:
            _delete_aptitude(app, apt_id)

    def test_update_aptitude_not_found_returns_404(self, auth_client, ids):
        r = auth_client.put(
            f"/aptitudes/{ids['activity_id']}/999999",
            data=json.dumps({"description": "x"}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "Aptitude not found"

    def test_update_aptitude_db_error_rolls_back_and_returns_500(self, auth_client, ids, app, monkeypatch):
        from Code.extensions import db

        apt_id = _create_aptitude(app, ids["activity_id"])

        def _boom():
            raise RuntimeError("commit-boom-aptitude-update")

        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{apt_id}",
                data=json.dumps({"description": "x"}),
                content_type="application/json",
            )
        finally:
            monkeypatch.undo()
            _delete_aptitude(app, apt_id)
        assert r.status_code == 500
        assert "commit-boom-aptitude-update" in json.loads(r.data)["error"]


class TestAptitudesDelete:

    def test_delete_aptitude_success(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], description="À supprimer")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        assert r.status_code == 200
        assert json.loads(r.data)["message"] == "Aptitude deleted"

        from Code.models.models import Aptitude
        with app.app_context():
            assert Aptitude.query.get(apt_id) is None

    def test_delete_aptitude_not_found_returns_404(self, auth_client, ids):
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/999999")
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "Aptitude not found"

    def test_delete_aptitude_db_error_rolls_back_and_returns_500(self, auth_client, ids, app, monkeypatch):
        from Code.extensions import db

        apt_id = _create_aptitude(app, ids["activity_id"])

        def _boom():
            raise RuntimeError("commit-boom-aptitude-delete")

        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        finally:
            monkeypatch.undo()
            _delete_aptitude(app, apt_id)
        assert r.status_code == 500
        assert "commit-boom-aptitude-delete" in json.loads(r.data)["error"]


class TestAptitudesRenderPartial:

    def test_render_aptitudes_found(self, auth_client, ids):
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert r.content_type.startswith("text/html")

    def test_render_aptitudes_activity_not_found_returns_404(self, auth_client):
        r = auth_client.get("/aptitudes/999999/render")
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "Activité non trouvée"
