# tests/test_40_cartography_translate.py
"""
Couverture des routes non encore testées :
  - activities_cartography.py → GET /activities/update-cartography
  - translate_softskills.py   → POST /translate_softskills/translate
"""
import pytest

pytestmark = pytest.mark.cartography_translate


# ===========================================================================
# Fake client OpenAI (simule le SDK sans appel réseau) pour couvrir les
# branches "avec client dispo" de translate_softskills.translate_softskills.
# ===========================================================================

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content=None, raise_exc=None):
        self.completions = _FakeChatCompletions(content, raise_exc)


class _FakeOpenAIClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_translate_client(monkeypatch, content=None, raise_exc=None):
    """Patche get_openai_client() dans translate_softskills pour renvoyer un faux client."""
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.translate_softskills.get_openai_client",
        lambda: (fake_client, None),
    )


def _lang_client(app, lang):
    """Client isolé (session dédiée) avec la langue forcée."""
    fresh = app.test_client()
    with fresh.session_transaction() as sess:
        sess["lang"] = lang
    return fresh


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

    def test_success_path_returns_200_with_summary(self, auth_client, ids, app, monkeypatch, tmp_path):
        """Fichier trouvé + process_visio_file/print_summary mockés → 200 avec résumé."""
        fake_file = tmp_path / "carto-succes.vsdx"
        fake_file.write_bytes(b"fake vsdx content")
        _set_svg_filename(app, ids["entity_id"], str(fake_file))

        calls = {"process": None, "summary": False}

        def _fake_process_visio_file(path):
            calls["process"] = path

        def _fake_print_summary():
            calls["summary"] = True
            print("résumé de test")

        monkeypatch.setattr(
            "Code.routes.activities_cartography.process_visio_file",
            _fake_process_visio_file,
        )
        monkeypatch.setattr(
            "Code.routes.activities_cartography.print_summary",
            _fake_print_summary,
        )

        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 200
            data = r.get_json()
            assert "summary" in data
            assert data["file"] == str(fake_file)
            assert calls["process"] == str(fake_file)
            assert calls["summary"] is True
        finally:
            _set_svg_filename(app, ids["entity_id"], None)

    def test_processing_exception_returns_500(self, auth_client, ids, app, monkeypatch, tmp_path):
        """Une exception levée par process_visio_file → 500 avec message d'erreur."""
        fake_file = tmp_path / "carto-erreur.vsdx"
        fake_file.write_bytes(b"fake vsdx content")
        _set_svg_filename(app, ids["entity_id"], str(fake_file))

        def _raise(path):
            raise RuntimeError("boom traitement visio")

        monkeypatch.setattr(
            "Code.routes.activities_cartography.process_visio_file",
            _raise,
        )

        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 500
            data = r.get_json()
            assert "boom traitement visio" in data["error"]
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

    # --- Chemin de succès (client IA mocké) ---

    def test_success_fr_returns_proposals_with_mapped_niveau(self, app, monkeypatch):
        """Client IA dispo (FR) + JSON valide → 200, niveau numérique traduit en libellé FR."""
        _mock_translate_client(
            monkeypatch,
            content='[{"habilete": "Coopération", "niveau": "2"}]',
        )
        client = _lang_client(app, "fr")
        r = client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "travail en équipe",
                "activity_data": {
                    "name": "Activité Test",
                    "tasks": [{"description": "Tâche"}],
                    "constraints": [],
                    "outgoing": [{"performance": {"name": "P1", "description": "desc"}}],
                },
            },
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["proposals"] == [{"habilete": "Coopération", "niveau": "2 (Acquisition)"}]

    def test_success_en_returns_proposals_with_mapped_niveau(self, app, monkeypatch):
        """Client IA dispo (EN) + JSON valide → 200, niveau numérique traduit en libellé EN."""
        _mock_translate_client(
            monkeypatch,
            content='[{"habilete": "Teamwork", "niveau": 3}]',
        )
        client = _lang_client(app, "en")
        r = client.post(
            "/translate_softskills/translate",
            json={"user_input": "teamwork, communication"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["proposals"] == [{"habilete": "Teamwork", "niveau": "3 (Proficient)"}]

    def test_success_response_object_wrapped_into_list(self, app, monkeypatch):
        """Si le JSON renvoyé est un objet unique (pas un tableau) → il est enveloppé dans une liste."""
        _mock_translate_client(
            monkeypatch,
            content='{"habilete": "Rigueur", "niveau": "1"}',
        )
        client = _lang_client(app, "fr")
        r = client.post(
            "/translate_softskills/translate",
            json={"user_input": "rigueur"},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["proposals"] == [{"habilete": "Rigueur", "niveau": "1 (Aptitude)"}]

    def test_response_not_list_or_dict_returns_400(self, app, monkeypatch):
        """JSON valide mais ni liste ni objet (ex: nombre) → 400."""
        _mock_translate_client(monkeypatch, content="42")
        client = _lang_client(app, "fr")
        r = client.post(
            "/translate_softskills/translate",
            json={"user_input": "test"},
        )
        assert r.status_code == 400
        assert "tableau" in r.get_json()["error"].lower()

    def test_invalid_json_returns_400_with_parse_error(self, app, monkeypatch):
        """Réponse IA non-JSON → 400 avec message de parsing."""
        _mock_translate_client(monkeypatch, content="ceci n'est pas du JSON")
        client = _lang_client(app, "fr")
        r = client.post(
            "/translate_softskills/translate",
            json={"user_input": "test"},
        )
        assert r.status_code == 400
        assert "parsing" in r.get_json()["error"].lower()

    def test_ai_call_exception_returns_500(self, app, monkeypatch):
        """Exception levée par le client IA pendant l'appel → 500 avec le message d'erreur."""
        _mock_translate_client(monkeypatch, raise_exc=RuntimeError("boom appel IA"))
        client = _lang_client(app, "fr")
        r = client.post(
            "/translate_softskills/translate",
            json={"user_input": "test"},
        )
        assert r.status_code == 500
        assert "boom appel ia" in r.get_json()["error"].lower()

    def test_prompts_not_loaded_returns_500(self, app, monkeypatch):
        """Client IA dispo mais get_prompt() renvoie None (catalogue absent) → 500 explicite."""
        _mock_translate_client(monkeypatch, content='[]')
        monkeypatch.setattr(
            "Code.routes.translate_softskills.get_prompt",
            lambda *args, **kwargs: None,
        )
        client = _lang_client(app, "fr")
        r = client.post(
            "/translate_softskills/translate",
            json={"user_input": "test"},
        )
        assert r.status_code == 500
        assert "prompts ia non charg" in r.get_json()["error"].lower()
