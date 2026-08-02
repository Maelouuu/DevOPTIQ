# tests/test_40_cartography_translate.py
"""
Couverture des routes non encore testées :
  - activities_cartography.py → GET /activities/update-cartography
  - translate_softskills.py   → POST /translate_softskills/translate
"""
import os
import pytest

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

    def test_existing_file_but_processing_raises_returns_500(self, auth_client, ids, app, monkeypatch):
        """Fichier trouvé (Code/example.vsdx) mais process_visio_file lève →
        500 + message d'erreur (couvre la branche try/except sans déclencher
        le traitement réel — process_visio_file vide la table 'links' de
        façon globale, non isolée par entité : l'appeler réellement ici
        polluerait toute la suite de tests partagée)."""
        assert os.path.exists(os.path.join("Code", "example.vsdx"))
        monkeypatch.setattr(
            "Code.routes.activities_cartography.process_visio_file",
            lambda path: (_ for _ in ()).throw(RuntimeError("parse boom")),
        )
        _set_svg_filename(app, ids["entity_id"], "example.vsdx")
        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 500
            body = r.get_json()
            assert "parse boom" in body["error"]
        finally:
            _set_svg_filename(app, ids["entity_id"], None)

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


# ---------------------------------------------------------------------------
# Fake client IA — simule Code.routes.translate_softskills.get_openai_client()
# pour couvrir les branches "avec client" (succès, erreurs de parsing,
# exception) sans appel réseau réel.
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


class _FakeTranslateClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_translate_client(monkeypatch, content=None, raise_exc=None):
    """Patche get_openai_client() dans translate_softskills.py."""
    fake_client = _FakeTranslateClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.translate_softskills.get_openai_client",
        lambda: (fake_client, None),
    )


def _lang_client(app, lang):
    """Client frais (non partagé, donc pas de pollution de auth_client) avec
    la langue de session forcée."""
    fresh = app.test_client()
    with fresh.session_transaction() as sess:
        sess["lang"] = lang
    return fresh


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

    # --- Avec client IA simulé (succès + branches de traitement) ---

    def test_success_returns_proposals_with_niveau_mapped_fr(self, app, monkeypatch):
        """Réponse IA valide (JSON array) → 200 + niveau numérique traduit en FR."""
        content = '[{"habilete": "Coopération", "niveau": "2", "justification": "..."}]'
        _mock_translate_client(monkeypatch, content=content)
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "travail en équipe"},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["proposals"][0]["niveau"] == "2 (Acquisition)"

    def test_success_lang_en_uses_english_niveau_mapping(self, app, monkeypatch):
        """Session lang=en → prompt/niveau en anglais."""
        content = '[{"habilete": "Cooperation", "niveau": 3, "justification": "..."}]'
        _mock_translate_client(monkeypatch, content=content)
        fresh = _lang_client(app, "en")
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "teamwork"},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["proposals"][0]["niveau"] == "3 (Proficient)"

    def test_success_with_outgoing_performance_included(self, app, monkeypatch):
        """activity_data.outgoing avec 'performance' → couvre make_enumeration/perf_lines."""
        content = '[{"habilete": "Rigueur", "niveau": "1", "justification": "..."}]'
        _mock_translate_client(monkeypatch, content=content)
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={
                "user_input": "rigueur, autonomie",
                "activity_data": {
                    "name": "Activité Test",
                    "tasks": [{"description": "Analyser les données"}],
                    "constraints": [{"description": "Confidentialité"}],
                    "outgoing": [
                        {"performance": {"name": "Qualité", "description": "Taux d'erreur faible"}},
                        {"no_performance_here": True},
                    ],
                },
            },
        )
        assert r.status_code == 200
        assert r.get_json()["proposals"][0]["habilete"] == "Rigueur"

    def test_dict_response_is_wrapped_in_list(self, app, monkeypatch):
        """L'IA renvoie un objet JSON seul (pas un tableau) → normalisé en liste."""
        content = '{"habilete": "Adaptabilité", "niveau": "4", "justification": "..."}'
        _mock_translate_client(monkeypatch, content=content)
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "adaptabilité"},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert isinstance(body["proposals"], list)
        assert body["proposals"][0]["habilete"] == "Adaptabilité"

    def test_non_list_non_dict_response_returns_400(self, app, monkeypatch):
        """L'IA renvoie un JSON scalaire (ni liste ni objet) → 400."""
        _mock_translate_client(monkeypatch, content='"juste une chaine"')
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 400
        assert "tableau" in r.get_json()["error"].lower()

    def test_invalid_json_response_returns_400(self, app, monkeypatch):
        """Réponse IA non-JSON → 400 + message de parsing."""
        _mock_translate_client(monkeypatch, content="ceci n'est pas du JSON {")
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 400
        assert "parsing" in r.get_json()["error"].lower()

    def test_markdown_wrapped_json_response_is_cleaned_then_parsed(self, app, monkeypatch):
        """Réponse IA entourée de backticks markdown → nettoyée puis parsée avec succès."""
        content = '```json\n[{"habilete": "Ecoute", "niveau": "2", "justification": "..."}]\n```'
        _mock_translate_client(monkeypatch, content=content)
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "écoute active"},
        )
        assert r.status_code == 200
        assert r.get_json()["proposals"][0]["habilete"] == "Ecoute"

    def test_exception_during_ai_call_returns_500(self, app, monkeypatch):
        """Exception levée pendant l'appel IA → 500 + message d'erreur."""
        _mock_translate_client(monkeypatch, raise_exc=RuntimeError("boom"))
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 500
        assert "boom" in r.get_json()["error"]

    def test_non_digit_niveau_left_untouched(self, app, monkeypatch):
        """niveau non numérique (déjà un libellé) → laissé tel quel, pas de KeyError."""
        content = '[{"habilete": "Ecoute", "niveau": "NA", "justification": "..."}]'
        _mock_translate_client(monkeypatch, content=content)
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "écoute"},
        )
        assert r.status_code == 200
        assert r.get_json()["proposals"][0]["niveau"] == "NA"

    def test_prompts_not_loaded_returns_500(self, app, monkeypatch):
        """get_prompt() renvoie None (catalogue non chargé) → 500 explicite."""
        _mock_translate_client(monkeypatch, content="[]")
        monkeypatch.setattr(
            "Code.routes.translate_softskills.get_prompt",
            lambda *a, **k: None,
        )
        fresh = app.test_client()
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 500
        assert "prompt" in r.get_json()["error"].lower()

    # --- Unitaire : make_enumeration ---

    def test_make_enumeration_empty_list_returns_placeholder(self):
        """make_enumeration sur liste vide → placeholder '(Aucune ...)'."""
        from Code.routes.translate_softskills import make_enumeration
        assert make_enumeration("T", []) == "(Aucune T)"

    def test_make_enumeration_with_dict_items(self):
        """make_enumeration sur des dicts → utilise le champ 'description'."""
        from Code.routes.translate_softskills import make_enumeration
        result = make_enumeration("T", [{"description": "Premiere tache"}])
        assert result == "T1: Premiere tache"

    def test_make_enumeration_with_plain_strings(self):
        """make_enumeration sur des chaînes brutes (pas de dict)."""
        from Code.routes.translate_softskills import make_enumeration
        result = make_enumeration("C", ["Délai serré", "Budget limité"])
        assert result == "C1: Délai serré\nC2: Budget limité"

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
