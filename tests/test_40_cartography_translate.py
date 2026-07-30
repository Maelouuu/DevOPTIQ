# tests/test_40_cartography_translate.py
"""
Couverture des routes non encore testées :
  - activities_cartography.py → GET /activities/update-cartography
  - translate_softskills.py   → POST /translate_softskills/translate
"""
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.cartography_translate


# ===========================================================================
# Helpers
# ===========================================================================

def _set_svg_filename(app, entity_id, value):
    """Met à jour svg_filename sur l'entité en base."""
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        e = Entity.query.get(entity_id)
        e.svg_filename = value
        db.session.commit()


# ===========================================================================
# 1. GET /activities/update-cartography  (activities_cartography.py)
# ===========================================================================

class TestUpdateCartography:

    def test_no_auth_no_entity_returns_400(self, app):
        """Sans session utilisateur, Entity.get_active() retourne None → 400."""
        with app.test_client() as fresh:
            r = fresh.get("/activities/update-cartography")
        assert r.status_code == 400
        body = r.get_json()
        assert "error" in body

    def test_auth_entity_without_svg_returns_400(self, auth_client, ids):
        """Entité active sans svg_filename → 400 + message lisible."""
        # L'entité seed n'a pas de svg_filename
        _set_svg_filename(auth_client.application, ids["entity_id"], None)
        r = auth_client.get("/activities/update-cartography")
        assert r.status_code == 400
        body = r.get_json()
        assert "error" in body

    def test_auth_entity_nonexistent_svg_returns_404(self, auth_client, ids, app):
        """Entité avec svg_filename pointant vers un fichier inexistant → 404."""
        _set_svg_filename(app, ids["entity_id"], "fichier_inexistant.vsdx")
        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 404
            body = r.get_json()
            assert "error" in body
        finally:
            _set_svg_filename(app, ids["entity_id"], None)

    def test_response_is_json(self, auth_client, ids):
        """La réponse (quelle que soit l'erreur) est du JSON."""
        r = auth_client.get("/activities/update-cartography")
        assert r.content_type.startswith("application/json")

    def test_no_auth_error_message_mentions_entity(self, app):
        """Le message d'erreur évoque l'entité manquante."""
        with app.test_client() as fresh:
            r = fresh.get("/activities/update-cartography")
        body = r.get_json()
        assert "entit" in body.get("error", "").lower()

    def test_no_svg_error_message_mentions_cartographie(self, auth_client, ids, app):
        """Le message d'erreur (svg manquant) mentionne 'cartographie'."""
        _set_svg_filename(app, ids["entity_id"], None)
        r = auth_client.get("/activities/update-cartography")
        body = r.get_json()
        error_text = (body.get("error", "") + body.get("message", "")).lower()
        assert "cartographie" in error_text or "svg" in error_text or "visio" in error_text

    def test_nonexistent_svg_error_includes_filename(self, auth_client, ids, app):
        """Le message d'erreur (fichier absent) contient le nom du fichier."""
        filename = "cartographie_test_manquante.vsdx"
        _set_svg_filename(app, ids["entity_id"], filename)
        try:
            r = auth_client.get("/activities/update-cartography")
            body = r.get_json()
            combined = body.get("error", "") + body.get("message", "")
            assert filename in combined
        finally:
            _set_svg_filename(app, ids["entity_id"], None)

    def test_success_path_returns_200_with_summary(self, auth_client, ids, app):
        """Fichier trouvé + traitement OK (mocké) → 200 avec message/summary/file."""
        _set_svg_filename(app, ids["entity_id"], "example.vsdx")
        try:
            with patch("Code.routes.activities_cartography.process_visio_file") as mock_process, \
                 patch("Code.routes.activities_cartography.print_summary") as mock_summary:
                mock_summary.side_effect = lambda: print("Résumé de test")
                r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 200
            body = r.get_json()
            assert body["file"] == "example.vsdx"
            assert "Résumé de test" in body["summary"]
            assert "message" in body
            mock_process.assert_called_once()
            called_path = mock_process.call_args[0][0]
            assert called_path.endswith("example.vsdx")
        finally:
            _set_svg_filename(app, ids["entity_id"], None)

    def test_processing_exception_returns_500(self, auth_client, ids, app):
        """Une exception levée pendant le traitement Visio → 500 + message d'erreur."""
        _set_svg_filename(app, ids["entity_id"], "example.vsdx")
        try:
            with patch(
                "Code.routes.activities_cartography.process_visio_file",
                side_effect=RuntimeError("boom"),
            ):
                r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 500
            body = r.get_json()
            assert body["error"] == "boom"
            assert "message" in body
        finally:
            _set_svg_filename(app, ids["entity_id"], None)


# ===========================================================================
# 2. POST /translate_softskills/translate  (translate_softskills.py)
# ===========================================================================

class TestTranslateSoftskills:

    # --- Validation d'entrée ---

    def test_empty_user_input_returns_400(self, auth_client):
        """user_input vide → 400 + message d'erreur."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": ""},
        )
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_whitespace_only_user_input_returns_400(self, auth_client):
        """user_input composé uniquement d'espaces → 400 (strip vide)."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "   "},
        )
        assert r.status_code == 400

    def test_missing_user_input_field_returns_400(self, auth_client):
        """Pas de champ user_input du tout → 400."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"activity_data": {}},
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "Aucun texte saisi pour la traduction."

    def test_empty_body_returns_400(self, auth_client):
        """Corps JSON vide {} → 400 (user_input absent)."""
        r = auth_client.post("/translate_softskills/translate", json={})
        assert r.status_code == 400

    def test_error_message_on_empty_input(self, auth_client):
        """Le champ 'error' contient bien le message attendu."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": ""},
        )
        assert r.get_json()["error"] == "Aucun texte saisi pour la traduction."

    # --- Sans clé OpenAI (environnement de test) ---

    def test_valid_input_no_openai_key_returns_500(self, auth_client, monkeypatch):
        """user_input valide + pas de clé OpenAI → 500 + error."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication, leadership"},
        )
        assert r.status_code == 500
        assert "error" in r.get_json()

    def test_error_mentions_openai_key_when_missing(self, auth_client, monkeypatch):
        """Quand la clé OpenAI est absente, le message le précise."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "travail en équipe"},
        )
        body = r.get_json()
        assert "openai" in body["error"].lower() or "clé" in body["error"].lower()

    def test_with_activity_data_no_openai_key_returns_500(self, auth_client, ids, monkeypatch):
        """user_input + activity_data structuré, sans clé → 500."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "adaptabilité, rigueur",
                "activity_data": {
                    "name": "Activité Test",
                    "tasks": [{"description": "Tâche principale"}],
                    "constraints": [{"description": "Délai serré"}],
                    "outgoing": [],
                },
            },
        )
        assert r.status_code == 500

    # --- Format de la réponse ---

    def test_response_content_type_is_json(self, auth_client):
        """La réponse est bien du JSON."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": ""},
        )
        assert r.content_type.startswith("application/json")

    def test_error_response_has_error_key(self, auth_client):
        """Toute réponse d'erreur contient la clé 'error'."""
        r = auth_client.post("/translate_softskills/translate", json={})
        assert "error" in r.get_json()

    # --- Unitaire : clean_json_response ---

    def test_clean_json_strips_markdown_backticks(self):
        """clean_json_response retire les backticks markdown."""
        from Code.routes.translate_softskills import clean_json_response
        raw = "```json\n[{\"a\": 1}]\n```"
        result = clean_json_response(raw)
        assert result.startswith("[")
        assert result.endswith("]")

    def test_clean_json_extracts_array(self):
        """clean_json_response isole le tableau JSON."""
        from Code.routes.translate_softskills import clean_json_response
        raw = "Voici le résultat : [{\"habilete\": \"Planification\"}] fin."
        result = clean_json_response(raw)
        assert result == '[{"habilete": "Planification"}]'

    def test_clean_json_returns_object_if_no_array(self):
        """clean_json_response retourne l'objet JSON si pas de tableau."""
        from Code.routes.translate_softskills import clean_json_response
        raw = '{"habilete": "Coopération"}'
        result = clean_json_response(raw)
        assert result == '{"habilete": "Coopération"}'
