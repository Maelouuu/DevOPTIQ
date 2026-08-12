# tests/test_40_cartography_translate.py
"""
Couverture des routes non encore testées :
  - activities_cartography.py → GET /activities/update-cartography
  - translate_softskills.py   → POST /translate_softskills/translate
"""
import json
import pytest

pytestmark = pytest.mark.cartography_translate


# ---------------------------------------------------------------------------
# Fake client IA (même patron que test_22_propose_ia.py) pour couvrir la
# branche "avec client IA" de translate_softskills() sans appel réseau réel.
# ---------------------------------------------------------------------------

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


class _FakeAIClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_translate_client(monkeypatch, content=None, raise_exc=None):
    """Patche get_openai_client() importé dans translate_softskills pour renvoyer un faux client."""
    fake_client = _FakeAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.translate_softskills.get_openai_client",
        lambda: (fake_client, None),
    )


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

    def test_clean_json_returns_text_unchanged_if_no_brackets(self):
        """clean_json_response renvoie le texte tel quel si aucun tableau ni objet détecté."""
        from Code.routes.translate_softskills import clean_json_response
        raw = "Pas de JSON ici."
        assert clean_json_response(raw) == "Pas de JSON ici."

    # --- Construction du prompt (langue, tâches, contraintes, performances) ---

    def test_english_lang_no_key_still_returns_500(self, auth_client, monkeypatch):
        """lang='en' : le prompt anglais est construit avant l'échec (pas de clé) → 500."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with auth_client.session_transaction() as s:
            s["lang"] = "en"
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication, leadership"},
        )
        assert r.status_code == 500
        with auth_client.session_transaction() as s:
            s.pop("lang", None)

    def test_outgoing_with_performance_builds_perf_lines_no_key(self, auth_client, monkeypatch):
        """outgoing contenant une performance structurée : la boucle P1/P2 s'exécute
        (branche couverte même sans clé IA, car construite avant l'appel client)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "rigueur",
                "activity_data": {
                    "name": "Usinage",
                    "tasks": [],
                    "constraints": [],
                    "outgoing": [
                        {"performance": {"name": "Cote respectée", "description": "±0.1mm"}},
                        {"performance": None},
                        "not_a_dict",
                    ],
                },
            },
        )
        assert r.status_code == 500

    # --- Avec client IA mocké (succès, erreurs de parsing, exception) ---

    def test_ai_success_list_response_maps_niveau_fr(self, auth_client, monkeypatch):
        _mock_translate_client(monkeypatch, content=json.dumps(
            [{"habilete": "Adaptabilité", "niveau": "3"}]
        ))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "adaptabilité"},
        )
        assert r.status_code == 200
        proposals = r.get_json()["proposals"]
        assert proposals[0]["niveau"] == "3 (Maîtrise)"

    def test_ai_success_english_lang_maps_niveau_en(self, auth_client, monkeypatch):
        _mock_translate_client(monkeypatch, content=json.dumps(
            [{"habilete": "Adaptability", "niveau": 4}]
        ))
        with auth_client.session_transaction() as s:
            s["lang"] = "en"
        try:
            r = auth_client.post(
                "/translate_softskills/translate",
                json={"user_input": "adaptability"},
            )
            assert r.status_code == 200
            proposals = r.get_json()["proposals"]
            assert proposals[0]["niveau"] == "4 (Highly Proficient)"
        finally:
            with auth_client.session_transaction() as s:
                s.pop("lang", None)

    def test_ai_success_object_response_is_wrapped_in_list(self, auth_client, monkeypatch):
        """Une réponse IA renvoyant un objet unique (pas un tableau) est encapsulée dans une liste."""
        _mock_translate_client(monkeypatch, content=json.dumps(
            {"habilete": "Coopération", "niveau": "1"}
        ))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "coopération"},
        )
        assert r.status_code == 200
        proposals = r.get_json()["proposals"]
        assert isinstance(proposals, list) and len(proposals) == 1
        assert proposals[0]["habilete"] == "Coopération"

    def test_ai_success_non_digit_niveau_left_unchanged(self, auth_client, monkeypatch):
        """Un niveau déjà textuel (non numérique) n'est pas réécrit par niveau_map."""
        _mock_translate_client(monkeypatch, content=json.dumps(
            [{"habilete": "Rigueur", "niveau": "Non évalué"}]
        ))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "rigueur"},
        )
        assert r.status_code == 200
        assert r.get_json()["proposals"][0]["niveau"] == "Non évalué"

    def test_ai_response_invalid_json_returns_400(self, auth_client, monkeypatch):
        _mock_translate_client(monkeypatch, content="ceci n'est pas du JSON")
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 400
        assert "Erreur de parsing JSON" in r.get_json()["error"]

    def test_ai_response_scalar_json_returns_400(self, auth_client, monkeypatch):
        """Un JSON valide mais ni liste ni objet (ex: un nombre) → 400."""
        _mock_translate_client(monkeypatch, content="42")
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 400
        assert "tableau" in r.get_json()["error"]

    def test_ai_client_exception_returns_500(self, auth_client, monkeypatch):
        _mock_translate_client(monkeypatch, raise_exc=RuntimeError("boom"))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 500
        assert r.get_json()["error"] == "boom"

    def test_prompts_unavailable_returns_500(self, auth_client, monkeypatch):
        """get_prompt() renvoie None (prompts non chargés) alors qu'un client IA est disponible."""
        monkeypatch.setattr("Code.routes.translate_softskills.get_prompt", lambda *a, **k: None)
        _mock_translate_client(monkeypatch, content=json.dumps([{"habilete": "X", "niveau": "2"}]))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 500
        assert "Prompts IA" in r.get_json()["error"]
