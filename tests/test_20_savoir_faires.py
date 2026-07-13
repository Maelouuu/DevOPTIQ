# tests/test_20_savoir_faires.py
"""
API : Savoir-Faires (/savoir_faires)
Couvre : ajout unitaire, ajout en lot, mise à jour, suppression et rendu HTML
         des savoir-faires pratiques associés à une activité.
"""
import json
import pytest

pytestmark = pytest.mark.savoir_faires


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_sf(app, activity_id, description="SF Fixture"):
    with app.app_context():
        from Code.models.models import SavoirFaire
        from Code.extensions import db
        sf = SavoirFaire(description=description, activity_id=activity_id)
        db.session.add(sf)
        db.session.commit()
        return sf.id


def _delete_sf(app, sf_id):
    with app.app_context():
        from Code.models.models import SavoirFaire
        from Code.extensions import db
        sf = SavoirFaire.query.get(sf_id)
        if sf:
            db.session.delete(sf)
            db.session.commit()


# ===========================================================================
# 1. POST /savoir_faires/add — ajout unitaire
# ===========================================================================

class TestAddSavoirFaireUnique:

    def test_add_sf_valid_returns_201(self, auth_client, ids, app):
        """POST avec description et activity_id valides → 201 + id + description."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"description": "Savoir-faire test unique", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        assert data["description"] == "Savoir-faire test unique"
        _delete_sf(app, data["id"])

    def test_add_sf_missing_description_returns_400(self, auth_client, ids):
        """description absente (ajout unitaire) → 400."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_add_sf_empty_description_returns_400(self, auth_client, ids):
        """description vide après strip → 400."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"description": "   ", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_sf_missing_activity_id_returns_400(self, auth_client):
        """activity_id absent → 400."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"description": "Sans activité"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_sf_invalid_activity_returns_404(self, auth_client):
        """activity_id inexistant → 404."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"description": "SF orphelin", "activity_id": 999999}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_add_sf_persists_in_db(self, auth_client, ids, app):
        """Le savoir-faire créé est retrouvable en base avec les bonnes valeurs."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"description": "SF Persisté", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        sf_id = json.loads(r.data)["id"]
        with app.app_context():
            from Code.models.models import SavoirFaire
            sf = SavoirFaire.query.get(sf_id)
            assert sf is not None
            assert sf.description == "SF Persisté"
            assert sf.activity_id == ids["activity_id"]
        _delete_sf(app, sf_id)

    def test_add_sf_response_has_id_and_description(self, auth_client, ids, app):
        """La réponse unitaire contient exactement id et description."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"description": "SF Champs", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        assert "description" in data
        _delete_sf(app, data["id"])


# ===========================================================================
# 2. POST /savoir_faires/add — ajout en lot (savoir_faires=[...])
# ===========================================================================

class TestAddSavoirFairesBatch:

    def test_add_sf_batch_valid_returns_201(self, auth_client, ids, app):
        """Lot de deux SF valides → 201, created=2, items liste de deux."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "savoir_faires": ["Maîtriser Excel", "Rédiger un rapport"],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["created"] == 2
        assert len(data["items"]) == 2
        for item in data["items"]:
            _delete_sf(app, item["id"])

    def test_add_sf_batch_empty_list_returns_201_count_zero(self, auth_client, ids):
        """Lot vide → 201, created=0."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"activity_id": ids["activity_id"], "savoir_faires": []}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["created"] == 0
        assert data["items"] == []

    def test_add_sf_batch_skips_empty_strings(self, auth_client, ids):
        """Entrées vides dans le lot sont ignorées."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "savoir_faires": ["", "  ", ""],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["created"] == 0

    def test_add_sf_batch_mixed_valid_and_empty(self, auth_client, ids, app):
        """Lot mixte (valides + vides) → seuls les valides sont créés."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "savoir_faires": ["SF Valide A", "", "SF Valide B", "   "],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["created"] == 2
        for item in data["items"]:
            _delete_sf(app, item["id"])

    def test_add_sf_batch_invalid_activity_returns_404(self, auth_client):
        """Lot avec activity_id inexistant → 404."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({"activity_id": 999999, "savoir_faires": ["SF Test"]}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_add_sf_batch_items_have_id_and_description(self, auth_client, ids, app):
        """Chaque item du lot a les champs id et description."""
        r = auth_client.post(
            "/savoir_faires/add",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "savoir_faires": ["SF Champs Batch"],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        item = data["items"][0]
        assert "id" in item
        assert "description" in item
        assert item["description"] == "SF Champs Batch"
        _delete_sf(app, item["id"])


# ===========================================================================
# 3. PUT /savoir_faires/<activity_id>/<sf_id> — modifier un savoir-faire
# ===========================================================================

class TestUpdateSavoirFaire:

    def test_update_sf_valid_returns_200(self, auth_client, ids, app):
        """PUT avec nouvelle description → 200 + données mises à jour."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Avant Modif")
        try:
            r = auth_client.put(
                f"/savoir_faires/{ids['activity_id']}/{sf_id}",
                data=json.dumps({"description": "SF Après Modif"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["description"] == "SF Après Modif"
            assert data["id"] == sf_id
        finally:
            _delete_sf(app, sf_id)

    def test_update_sf_persists_change(self, auth_client, ids, app):
        """La modification est bien persistée en base."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Avant")
        try:
            auth_client.put(
                f"/savoir_faires/{ids['activity_id']}/{sf_id}",
                data=json.dumps({"description": "SF Après"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import SavoirFaire
                sf = SavoirFaire.query.get(sf_id)
                assert sf.description == "SF Après"
        finally:
            _delete_sf(app, sf_id)

    def test_update_sf_empty_description_returns_400(self, auth_client, ids, app):
        """description vide → 400."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Update Vide")
        try:
            r = auth_client.put(
                f"/savoir_faires/{ids['activity_id']}/{sf_id}",
                data=json.dumps({"description": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_sf(app, sf_id)

    def test_update_sf_whitespace_description_returns_400(self, auth_client, ids, app):
        """description d'espaces seuls → 400."""
        sf_id = _create_sf(app, ids["activity_id"], "SF WS")
        try:
            r = auth_client.put(
                f"/savoir_faires/{ids['activity_id']}/{sf_id}",
                data=json.dumps({"description": "   "}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_sf(app, sf_id)

    def test_update_sf_wrong_sf_id_returns_404(self, auth_client, ids):
        """sf_id inexistant → 404."""
        r = auth_client.put(
            f"/savoir_faires/{ids['activity_id']}/999999",
            data=json.dumps({"description": "Modif"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_sf_wrong_activity_id_returns_404(self, auth_client, ids, app):
        """sf_id valide mais mauvaise activité → 404."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Mauvaise Activité Update")
        try:
            r = auth_client.put(
                f"/savoir_faires/999999/{sf_id}",
                data=json.dumps({"description": "Modif"}),
                content_type="application/json",
            )
            assert r.status_code == 404
        finally:
            _delete_sf(app, sf_id)


# ===========================================================================
# 4. DELETE /savoir_faires/<activity_id>/<sf_id> — supprimer un savoir-faire
# ===========================================================================

class TestDeleteSavoirFaire:

    def test_delete_sf_valid_returns_200(self, auth_client, ids, app):
        """DELETE sur SF existant → 200 + message."""
        sf_id = _create_sf(app, ids["activity_id"], "SF À Supprimer")
        r = auth_client.delete(f"/savoir_faires/{ids['activity_id']}/{sf_id}")
        assert r.status_code == 200
        assert "message" in json.loads(r.data)

    def test_delete_sf_removes_from_db(self, auth_client, ids, app):
        """Après suppression, le SF n'existe plus en base."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Supprimé Vérifié")
        auth_client.delete(f"/savoir_faires/{ids['activity_id']}/{sf_id}")
        with app.app_context():
            from Code.models.models import SavoirFaire
            assert SavoirFaire.query.get(sf_id) is None

    def test_delete_sf_not_found_returns_404(self, auth_client, ids):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete(f"/savoir_faires/{ids['activity_id']}/999999")
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_delete_sf_wrong_activity_returns_404(self, auth_client, ids, app):
        """SF valide mais activité incorrecte → 404."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Mauvaise Act Delete")
        try:
            r = auth_client.delete(f"/savoir_faires/999999/{sf_id}")
            assert r.status_code == 404
        finally:
            _delete_sf(app, sf_id)

    def test_delete_sf_idempotent_returns_404_on_second_call(self, auth_client, ids, app):
        """Deuxième suppression du même SF → 404."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Double Delete")
        auth_client.delete(f"/savoir_faires/{ids['activity_id']}/{sf_id}")
        r2 = auth_client.delete(f"/savoir_faires/{ids['activity_id']}/{sf_id}")
        assert r2.status_code == 404


# ===========================================================================
# 5. GET /savoir_faires/<activity_id>/render — fragment HTML
# ===========================================================================

class TestRenderSavoirFaires:

    def test_render_sf_valid_activity_returns_200(self, auth_client, ids):
        """GET /savoir_faires/<id>/render sur activité valide → 200 HTML."""
        r = auth_client.get(f"/savoir_faires/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"<" in r.data

    def test_render_sf_invalid_activity_returns_404(self, auth_client):
        """GET /savoir_faires/999999/render → 404."""
        r = auth_client.get("/savoir_faires/999999/render")
        assert r.status_code == 404

    def test_render_sf_contains_created_sf(self, auth_client, ids, app):
        """Le rendu HTML inclut un SF créé au préalable."""
        sf_id = _create_sf(app, ids["activity_id"], "SF Rendu HTML Test")
        try:
            r = auth_client.get(f"/savoir_faires/{ids['activity_id']}/render")
            assert r.status_code == 200
            assert b"SF Rendu HTML Test" in r.data
        finally:
            _delete_sf(app, sf_id)


# ===========================================================================
# 6. Sécurité — mutations sans session
# ===========================================================================

class TestSavoirFairesNoAuth:
    """Utilise un client isolé (app.test_client() dédié par test) car le
    fixture `client` partage son cookie-jar avec `auth_client` (scope=session)."""

    def test_add_sf_requires_auth(self, app, ids):
        with app.test_client() as fresh:
            r = fresh.post(
                "/savoir_faires/add",
                data=json.dumps({"description": "Sans Session", "activity_id": ids["activity_id"]}),
                content_type="application/json",
            )
        assert r.status_code == 401

    def test_update_sf_requires_auth(self, app, ids):
        with app.test_client() as fresh:
            r = fresh.put(
                f"/savoir_faires/{ids['activity_id']}/999999",
                data=json.dumps({"description": "X"}),
                content_type="application/json",
            )
        assert r.status_code == 401

    def test_delete_sf_requires_auth(self, app, ids):
        with app.test_client() as fresh:
            r = fresh.delete(f"/savoir_faires/{ids['activity_id']}/999999")
        assert r.status_code == 401
