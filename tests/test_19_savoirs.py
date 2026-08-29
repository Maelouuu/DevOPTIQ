# tests/test_19_savoirs.py
"""
API : Savoirs (/savoirs)
Couvre : ajout, mise à jour, suppression et rendu HTML des savoirs théoriques
         associés à une activité.
"""
import json
import pytest

pytestmark = pytest.mark.savoirs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_savoir(app, activity_id, description="Savoir Fixture"):
    with app.app_context():
        from Code.models.models import Savoir
        from Code.extensions import db
        s = Savoir(description=description, activity_id=activity_id)
        db.session.add(s)
        db.session.commit()
        return s.id


def _delete_savoir(app, savoir_id):
    with app.app_context():
        from Code.models.models import Savoir
        from Code.extensions import db
        s = Savoir.query.get(savoir_id)
        if s:
            db.session.delete(s)
            db.session.commit()


# ===========================================================================
# 1. POST /savoirs/add — ajouter un savoir
# ===========================================================================

class TestAddSavoir:

    def test_add_savoir_valid_returns_201(self, auth_client, ids, app):
        """POST /savoirs/add avec données valides → 201 + id + description."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"description": "Connaissance en comptabilité", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        assert data["description"] == "Connaissance en comptabilité"
        _delete_savoir(app, data["id"])

    def test_add_savoir_missing_description_returns_400(self, auth_client, ids):
        """description absente → 400."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_add_savoir_empty_description_returns_400(self, auth_client, ids):
        """description vide après strip → 400."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"description": "   ", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_savoir_missing_activity_id_returns_400(self, auth_client):
        """activity_id absent → 400."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"description": "Quelque chose"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_savoir_invalid_activity_returns_404(self, auth_client):
        """activity_id inexistant → 404."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"description": "Test savoir", "activity_id": 999999}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_add_savoir_response_has_id_and_description(self, auth_client, ids, app):
        """La réponse contient exactement les champs id et description."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"description": "Savoir champs test", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert set(data.keys()) >= {"id", "description"}
        assert isinstance(data["id"], int)
        _delete_savoir(app, data["id"])

    def test_add_savoir_persists_in_db(self, auth_client, ids, app):
        """Après création, le savoir est retrouvable en base."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"description": "Savoir Persisté", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        savoir_id = json.loads(r.data)["id"]
        with app.app_context():
            from Code.models.models import Savoir
            s = Savoir.query.get(savoir_id)
            assert s is not None
            assert s.description == "Savoir Persisté"
            assert s.activity_id == ids["activity_id"]
        _delete_savoir(app, savoir_id)

    def test_add_savoir_empty_json_body_returns_400(self, auth_client, ids):
        """Corps JSON vide {} → 400 (description et activity_id manquants)."""
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ===========================================================================
# 2. PUT /savoirs/<activity_id>/<savoir_id> — modifier un savoir
# ===========================================================================

class TestUpdateSavoir:

    def test_update_savoir_valid_returns_200(self, auth_client, ids, app):
        """PUT avec nouvelle description → 200 + description mise à jour."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir Avant Modif")
        try:
            r = auth_client.put(
                f"/savoirs/{ids['activity_id']}/{savoir_id}",
                data=json.dumps({"description": "Savoir Après Modif"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["description"] == "Savoir Après Modif"
            assert data["id"] == savoir_id
        finally:
            _delete_savoir(app, savoir_id)

    def test_update_savoir_persists_change(self, auth_client, ids, app):
        """La modification est persistée en base."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Avant")
        try:
            auth_client.put(
                f"/savoirs/{ids['activity_id']}/{savoir_id}",
                data=json.dumps({"description": "Après"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Savoir
                s = Savoir.query.get(savoir_id)
                assert s.description == "Après"
        finally:
            _delete_savoir(app, savoir_id)

    def test_update_savoir_empty_description_returns_400(self, auth_client, ids, app):
        """description vide → 400."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir Update Vide")
        try:
            r = auth_client.put(
                f"/savoirs/{ids['activity_id']}/{savoir_id}",
                data=json.dumps({"description": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_savoir(app, savoir_id)

    def test_update_savoir_wrong_savoir_id_returns_404(self, auth_client, ids):
        """savoir_id inexistant pour cette activité → 404."""
        r = auth_client.put(
            f"/savoirs/{ids['activity_id']}/999999",
            data=json.dumps({"description": "Modif"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_savoir_wrong_activity_id_returns_404(self, auth_client, ids, app):
        """savoir_id existant mais activité incorrecte → 404 (filtre activity_id)."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir Mauvaise Activité")
        try:
            r = auth_client.put(
                f"/savoirs/999999/{savoir_id}",
                data=json.dumps({"description": "Modif"}),
                content_type="application/json",
            )
            assert r.status_code == 404
        finally:
            _delete_savoir(app, savoir_id)

    def test_update_savoir_whitespace_only_returns_400(self, auth_client, ids, app):
        """description composée d'espaces → 400."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir WS")
        try:
            r = auth_client.put(
                f"/savoirs/{ids['activity_id']}/{savoir_id}",
                data=json.dumps({"description": "   "}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_savoir(app, savoir_id)


# ===========================================================================
# 3. DELETE /savoirs/<activity_id>/<savoir_id> — supprimer un savoir
# ===========================================================================

class TestDeleteSavoir:

    def test_delete_savoir_valid_returns_200(self, auth_client, ids, app):
        """DELETE sur savoir existant → 200 + message."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir À Supprimer")
        r = auth_client.delete(f"/savoirs/{ids['activity_id']}/{savoir_id}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "message" in data

    def test_delete_savoir_removes_from_db(self, auth_client, ids, app):
        """Après suppression, le savoir n'existe plus en base."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir Supprimé Vérifié")
        auth_client.delete(f"/savoirs/{ids['activity_id']}/{savoir_id}")
        with app.app_context():
            from Code.models.models import Savoir
            assert Savoir.query.get(savoir_id) is None

    def test_delete_savoir_not_found_returns_404(self, auth_client, ids):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete(f"/savoirs/{ids['activity_id']}/999999")
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_delete_savoir_wrong_activity_returns_404(self, auth_client, ids, app):
        """savoir_id valide mais activité incorrecte → 404."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir Mauvaise Act Delete")
        try:
            r = auth_client.delete(f"/savoirs/999999/{savoir_id}")
            assert r.status_code == 404
        finally:
            _delete_savoir(app, savoir_id)

    def test_delete_savoir_idempotent_returns_404_on_second_call(self, auth_client, ids, app):
        """Supprimer deux fois le même savoir → 404 au deuxième appel."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir Double Suppression")
        auth_client.delete(f"/savoirs/{ids['activity_id']}/{savoir_id}")
        r2 = auth_client.delete(f"/savoirs/{ids['activity_id']}/{savoir_id}")
        assert r2.status_code == 404


# ===========================================================================
# 4. GET /savoirs/<activity_id>/render — fragment HTML
# ===========================================================================

class TestRenderSavoirs:

    def test_render_savoirs_valid_activity_returns_200(self, auth_client, ids):
        """GET /savoirs/<id>/render sur activité valide → 200 HTML."""
        r = auth_client.get(f"/savoirs/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"<" in r.data

    def test_render_savoirs_invalid_activity_returns_404(self, auth_client):
        """GET /savoirs/999999/render → 404."""
        r = auth_client.get("/savoirs/999999/render")
        assert r.status_code == 404

    def test_render_savoirs_contains_seeded_content(self, auth_client, ids, app):
        """Le rendu HTML inclut un savoir créé au préalable."""
        savoir_id = _create_savoir(app, ids["activity_id"], "Savoir Rendu Test")
        try:
            r = auth_client.get(f"/savoirs/{ids['activity_id']}/render")
            assert r.status_code == 200
            assert b"Savoir Rendu Test" in r.data
        finally:
            _delete_savoir(app, savoir_id)


# ===========================================================================
# 5. Erreurs DB (branches except → 500 + rollback)
# ===========================================================================

class TestSavoirDbErrors:

    def _break_commit(self, monkeypatch, app):
        with app.app_context():
            from Code.extensions import db
            def _boom(*a, **kw):
                raise RuntimeError("panne DB simulée")
            monkeypatch.setattr(db.session, "commit", _boom)

    def test_add_savoir_db_error_returns_500(self, auth_client, ids, app, monkeypatch):
        self._break_commit(monkeypatch, app)
        r = auth_client.post(
            "/savoirs/add",
            data=json.dumps({"description": "Va échouer", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 500
        assert "panne DB simulée" in json.loads(r.data)["error"]

    def test_update_savoir_db_error_returns_500(self, auth_client, ids, app, monkeypatch):
        savoir_id = _create_savoir(app, ids["activity_id"], "Avant échec update")
        try:
            self._break_commit(monkeypatch, app)
            r = auth_client.put(
                f"/savoirs/{ids['activity_id']}/{savoir_id}",
                data=json.dumps({"description": "Nouvelle valeur"}),
                content_type="application/json",
            )
            assert r.status_code == 500
            assert "panne DB simulée" in json.loads(r.data)["error"]
        finally:
            monkeypatch.undo()
            _delete_savoir(app, savoir_id)

    def test_delete_savoir_db_error_returns_500(self, auth_client, ids, app, monkeypatch):
        savoir_id = _create_savoir(app, ids["activity_id"], "Avant échec delete")
        try:
            self._break_commit(monkeypatch, app)
            r = auth_client.delete(f"/savoirs/{ids['activity_id']}/{savoir_id}")
            assert r.status_code == 500
            assert "panne DB simulée" in json.loads(r.data)["error"]
        finally:
            monkeypatch.undo()
            _delete_savoir(app, savoir_id)
