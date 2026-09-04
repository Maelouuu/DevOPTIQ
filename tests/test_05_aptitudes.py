# tests/test_05_aptitudes.py
"""
API : Aptitudes (/aptitudes)
Couvre : ajout, mise à jour, suppression et rendu HTML des aptitudes
         associées à une activité.
"""
import json
import pytest

pytestmark = pytest.mark.aptitudes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_aptitude(app, activity_id, description="Aptitude Fixture"):
    with app.app_context():
        from Code.models.models import Aptitude
        from Code.extensions import db
        a = Aptitude(description=description, activity_id=activity_id)
        db.session.add(a)
        db.session.commit()
        return a.id


def _delete_aptitude(app, aptitude_id):
    with app.app_context():
        from Code.models.models import Aptitude
        from Code.extensions import db
        a = Aptitude.query.get(aptitude_id)
        if a:
            db.session.delete(a)
            db.session.commit()


# ===========================================================================
# 1. POST /aptitudes/add — ajouter une aptitude
# ===========================================================================

class TestAddAptitude:

    def test_add_aptitude_valid_returns_201(self, auth_client, ids, app):
        """POST /aptitudes/add avec données valides → 201 + id + description."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Sens de l'organisation", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        assert data["description"] == "Sens de l'organisation"
        _delete_aptitude(app, data["id"])

    def test_add_aptitude_missing_description_returns_400(self, auth_client, ids):
        """description absente → 400."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_add_aptitude_empty_description_returns_400(self, auth_client, ids):
        """description vide après strip → 400."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "   ", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_aptitude_missing_activity_id_returns_400(self, auth_client):
        """activity_id absent → 400."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Quelque chose"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_aptitude_invalid_activity_returns_404(self, auth_client):
        """activity_id inexistant → 404."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Test aptitude", "activity_id": 999999}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_add_aptitude_response_has_id_and_description(self, auth_client, ids, app):
        """La réponse contient exactement les champs id et description."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Aptitude champs test", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert set(data.keys()) >= {"id", "description"}
        assert isinstance(data["id"], int)
        _delete_aptitude(app, data["id"])

    def test_add_aptitude_persists_in_db(self, auth_client, ids, app):
        """Après création, l'aptitude est retrouvable en base."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({"description": "Aptitude Persistée", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        aptitude_id = json.loads(r.data)["id"]
        with app.app_context():
            from Code.models.models import Aptitude
            a = Aptitude.query.get(aptitude_id)
            assert a is not None
            assert a.description == "Aptitude Persistée"
            assert a.activity_id == ids["activity_id"]
        _delete_aptitude(app, aptitude_id)

    def test_add_aptitude_empty_json_body_returns_400(self, auth_client, ids):
        """Corps JSON vide {} → 400 (description et activity_id manquants)."""
        r = auth_client.post(
            "/aptitudes/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ===========================================================================
# 2. PUT /aptitudes/<activity_id>/<aptitude_id> — modifier une aptitude
# ===========================================================================

class TestUpdateAptitude:

    def test_update_aptitude_valid_returns_200(self, auth_client, ids, app):
        """PUT avec nouvelle description → 200 + description mise à jour."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude Avant Modif")
        try:
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{aptitude_id}",
                data=json.dumps({"description": "Aptitude Après Modif"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["description"] == "Aptitude Après Modif"
            assert data["id"] == aptitude_id
        finally:
            _delete_aptitude(app, aptitude_id)

    def test_update_aptitude_persists_change(self, auth_client, ids, app):
        """La modification est persistée en base."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Avant")
        try:
            auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{aptitude_id}",
                data=json.dumps({"description": "Après"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Aptitude
                a = Aptitude.query.get(aptitude_id)
                assert a.description == "Après"
        finally:
            _delete_aptitude(app, aptitude_id)

    def test_update_aptitude_empty_description_returns_400(self, auth_client, ids, app):
        """description vide → 400."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude Update Vide")
        try:
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{aptitude_id}",
                data=json.dumps({"description": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_aptitude(app, aptitude_id)

    def test_update_aptitude_wrong_aptitude_id_returns_404(self, auth_client, ids):
        """aptitude_id inexistant pour cette activité → 404."""
        r = auth_client.put(
            f"/aptitudes/{ids['activity_id']}/999999",
            data=json.dumps({"description": "Modif"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_aptitude_wrong_activity_id_returns_404(self, auth_client, ids, app):
        """aptitude_id existant mais activité incorrecte → 404 (filtre activity_id)."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude Mauvaise Activité")
        try:
            r = auth_client.put(
                f"/aptitudes/999999/{aptitude_id}",
                data=json.dumps({"description": "Modif"}),
                content_type="application/json",
            )
            assert r.status_code == 404
        finally:
            _delete_aptitude(app, aptitude_id)

    def test_update_aptitude_whitespace_only_returns_400(self, auth_client, ids, app):
        """description composée d'espaces → 400."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude WS")
        try:
            r = auth_client.put(
                f"/aptitudes/{ids['activity_id']}/{aptitude_id}",
                data=json.dumps({"description": "   "}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_aptitude(app, aptitude_id)


# ===========================================================================
# 3. DELETE /aptitudes/<activity_id>/<aptitude_id> — supprimer une aptitude
# ===========================================================================

class TestDeleteAptitude:

    def test_delete_aptitude_valid_returns_200(self, auth_client, ids, app):
        """DELETE sur aptitude existante → 200 + message."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude À Supprimer")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{aptitude_id}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "message" in data

    def test_delete_aptitude_removes_from_db(self, auth_client, ids, app):
        """Après suppression, l'aptitude n'existe plus en base."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude Supprimée Vérifiée")
        auth_client.delete(f"/aptitudes/{ids['activity_id']}/{aptitude_id}")
        with app.app_context():
            from Code.models.models import Aptitude
            assert Aptitude.query.get(aptitude_id) is None

    def test_delete_aptitude_not_found_returns_404(self, auth_client, ids):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/999999")
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_delete_aptitude_wrong_activity_returns_404(self, auth_client, ids, app):
        """aptitude_id valide mais activité incorrecte → 404."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude Mauvaise Act Delete")
        try:
            r = auth_client.delete(f"/aptitudes/999999/{aptitude_id}")
            assert r.status_code == 404
        finally:
            _delete_aptitude(app, aptitude_id)

    def test_delete_aptitude_idempotent_returns_404_on_second_call(self, auth_client, ids, app):
        """Supprimer deux fois la même aptitude → 404 au deuxième appel."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude Double Suppression")
        auth_client.delete(f"/aptitudes/{ids['activity_id']}/{aptitude_id}")
        r2 = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{aptitude_id}")
        assert r2.status_code == 404


# ===========================================================================
# 4. GET /aptitudes/<activity_id>/render — fragment HTML
# ===========================================================================

class TestRenderAptitudes:

    def test_render_aptitudes_valid_activity_returns_200(self, auth_client, ids):
        """GET /aptitudes/<id>/render sur activité valide → 200 HTML."""
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"<" in r.data

    def test_render_aptitudes_invalid_activity_returns_404(self, auth_client):
        """GET /aptitudes/999999/render → 404."""
        r = auth_client.get("/aptitudes/999999/render")
        assert r.status_code == 404

    def test_render_aptitudes_contains_seeded_content(self, auth_client, ids, app):
        """Le rendu HTML inclut une aptitude créée au préalable."""
        aptitude_id = _create_aptitude(app, ids["activity_id"], "Aptitude Rendu Test")
        try:
            r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
            assert r.status_code == 200
            assert b"Aptitude Rendu Test" in r.data
        finally:
            _delete_aptitude(app, aptitude_id)
