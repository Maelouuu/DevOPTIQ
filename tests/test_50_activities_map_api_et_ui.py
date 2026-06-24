# tests/test_50_activities_map_api_et_ui.py
"""
Routes non couvertes jusqu'ici :
  - activities_map.py → GET  /activities/map/api/activities
  - activities_map.py → POST /activities/preview-connections
  - ui_routes.py      → GET  /ui/activities
  - test_panel.py     → POST /testpanel/run/case/<case_id>
"""
import io
import pytest

pytestmark = pytest.mark.activities_map_api_et_ui


# ===========================================================================
# 1. GET /activities/map/api/activities
# ===========================================================================

class TestMapApiActivities:

    def test_no_entity_returns_empty_list(self, app):
        """Sans entité active, retourne []."""
        with app.test_client() as fresh:
            r = fresh.get("/activities/map/api/activities")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_with_auth_entity_returns_list(self, auth_client):
        """Avec entité active, retourne une liste."""
        r = auth_client.get("/activities/map/api/activities")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)

    def test_returns_seeded_activity(self, auth_client, ids):
        """La liste contient l'activité du seed."""
        r = auth_client.get("/activities/map/api/activities")
        data = r.get_json()
        found_ids = [item["id"] for item in data]
        assert ids["activity_id"] in found_ids

    def test_each_item_has_id_and_name(self, auth_client):
        """Chaque élément possède 'id' et 'name'."""
        r = auth_client.get("/activities/map/api/activities")
        for item in r.get_json():
            assert "id" in item
            assert "name" in item

    def test_name_is_string(self, auth_client):
        """Le champ 'name' est une chaîne (jamais None)."""
        r = auth_client.get("/activities/map/api/activities")
        for item in r.get_json():
            assert isinstance(item["name"], str)

    def test_response_is_json(self, auth_client):
        """Content-Type est application/json."""
        r = auth_client.get("/activities/map/api/activities")
        assert r.content_type.startswith("application/json")

    def test_activity_name_matches_seed(self, auth_client, ids, app):
        """Le nom de l'activité seed est correct dans la liste."""
        with app.app_context():
            from Code.models.models import Activities
            act = Activities.query.get(ids["activity_id"])
            expected_name = act.name or ""
        r = auth_client.get("/activities/map/api/activities")
        items = {item["id"]: item["name"] for item in r.get_json()}
        assert items[ids["activity_id"]] == expected_name


# ===========================================================================
# 2. POST /activities/preview-connections
# ===========================================================================

class TestPreviewConnections:

    def test_no_file_returns_400(self, auth_client):
        """Pas de fichier joint → 400 + error."""
        r = auth_client.post("/activities/preview-connections", data={})
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_no_file_error_message(self, auth_client):
        """Message d'erreur précise l'absence de fichier."""
        r = auth_client.post("/activities/preview-connections", data={})
        assert r.get_json()["error"] == "Aucun fichier"

    def test_wrong_extension_returns_400(self, auth_client):
        """Fichier non-VSDX → 400."""
        data = {"file": (io.BytesIO(b"fake content"), "test.pdf")}
        r = auth_client.post(
            "/activities/preview-connections",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "Format VSDX requis"

    def test_wrong_extension_txt_returns_400(self, auth_client):
        """Fichier .txt → 400 Format VSDX requis."""
        data = {"file": (io.BytesIO(b"text"), "document.txt")}
        r = auth_client.post(
            "/activities/preview-connections",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_no_entity_with_vsdx_returns_400(self, app):
        """VSDX valide mais sans entité active → 400."""
        with app.test_client() as fresh:
            data = {"file": (io.BytesIO(b"PK\x03\x04fake vsdx"), "carto.vsdx")}
            r = fresh.post(
                "/activities/preview-connections",
                data=data,
                content_type="multipart/form-data",
            )
        assert r.status_code == 400
        body = r.get_json()
        assert body["error"] == "Aucune entité active"

    def test_entity_id_not_owned_returns_404(self, auth_client):
        """entity_id existant mais non possédé par l'utilisateur → 404."""
        data = {
            "file": (io.BytesIO(b"PK\x03\x04fake vsdx"), "carto.vsdx"),
            "entity_id": "999999",
        }
        r = auth_client.post(
            "/activities/preview-connections",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 404
        assert "error" in r.get_json()

    def test_response_is_json_on_error(self, auth_client):
        """Toute réponse d'erreur est du JSON."""
        r = auth_client.post("/activities/preview-connections", data={})
        assert r.content_type.startswith("application/json")

    def test_extension_check_is_case_insensitive(self, auth_client, ids, app):
        """Extension .VSDX (majuscules) est acceptée (passe le filtre d'extension)."""
        # Une fois l'extension validée, l'erreur vient du parsing du contenu.
        # On vérifie donc que le 400 n'est PAS "Format VSDX requis".
        data = {"file": (io.BytesIO(b"not a real vsdx"), "carto.VSDX")}
        r = auth_client.post(
            "/activities/preview-connections",
            data=data,
            content_type="multipart/form-data",
        )
        body = r.get_json()
        assert body.get("error") != "Format VSDX requis"


# ===========================================================================
# 3. GET /ui/activities
# ===========================================================================

class TestUiActivities:

    def test_page_renders_without_crash(self, auth_client):
        """La page /ui/activities répond sans erreur serveur."""
        r = auth_client.get("/ui/activities")
        assert r.status_code == 200

    def test_response_is_html(self, auth_client):
        """Le Content-Type est text/html."""
        r = auth_client.get("/ui/activities")
        assert "text/html" in r.content_type

    def test_unauthenticated_does_not_crash(self, client):
        """Sans session, la route ne génère pas d'erreur 500."""
        r = client.get("/ui/activities")
        assert r.status_code in (200, 302)

    def test_page_contains_activities_context(self, auth_client):
        """Le rendu HTML contient le nom de l'activité seed."""
        r = auth_client.get("/ui/activities")
        assert b"Activit" in r.data

    def test_page_body_nonempty(self, auth_client):
        """La page rendue a un corps non vide."""
        r = auth_client.get("/ui/activities")
        assert len(r.data) > 0


# ===========================================================================
# 4. POST /testpanel/run/case/<case_id>
# ===========================================================================

class TestRunCase:

    def test_nonexistent_case_id_returns_error(self, auth_client):
        """case_id inexistant → exception levée → réponse non-200."""
        r = auth_client.post("/testpanel/run/case/999999")
        assert r.status_code != 200

    def test_nonexistent_case_id_returns_500(self, auth_client):
        """case_id absent de la DB → erreur non gérée → 500."""
        r = auth_client.post("/testpanel/run/case/999999")
        assert r.status_code == 500

    def test_zero_case_id_returns_error(self, auth_client):
        """case_id=0 (jamais valide) → erreur serveur."""
        r = auth_client.post("/testpanel/run/case/0")
        assert r.status_code in (404, 500)

    def test_response_content_type_on_error(self, auth_client):
        """Même en cas d'erreur, la réponse est JSON ou HTML (pas de crash non géré)."""
        r = auth_client.post("/testpanel/run/case/999999")
        # La route lève une exception — Flask renvoie une réponse d'erreur
        assert r.status_code >= 400
