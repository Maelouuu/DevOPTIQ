# tests/test_40_cartography_translate.py
"""
Couverture des routes non encore testées :
  - activities_cartography.py → GET /activities/update-cartography
  - translate_softskills.py   → POST /translate_softskills/translate
"""
import os
import json as json_module
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


# ---------------------------------------------------------------------------
# Fake OpenAI client — simule le SDK sans appel réseau réel, pour couvrir les
# branches "avec client dispo" de translate_softskills (succès, JSON invalide,
# type non-liste, exception).
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


class _FakeOpenAIClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_translate_client(monkeypatch, content=None, raise_exc=None):
    """Patche get_openai_client() importé dans translate_softskills."""
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.translate_softskills.get_openai_client",
        lambda: (fake_client, None),
    )


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

    def test_existing_file_success_returns_summary(self, auth_client, ids, app, monkeypatch):
        """Fichier de cartographie trouvé + traitement OK → 200 + résumé."""
        filename = "cartographie_test_existante.vsdx"
        svg_dir = os.path.join("static", "svg")
        os.makedirs(svg_dir, exist_ok=True)
        file_path = os.path.join(svg_dir, filename)
        with open(file_path, "w") as f:
            f.write("dummy")

        monkeypatch.setattr(
            "Code.routes.activities_cartography.process_visio_file",
            lambda path: None,
        )
        monkeypatch.setattr(
            "Code.routes.activities_cartography.print_summary",
            lambda: print("Résumé de traitement OK"),
        )

        _set_svg_filename(app, ids["entity_id"], filename)
        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 200
            body = r.get_json()
            assert "message" in body
            assert "summary" in body
            assert body["file"] == filename
        finally:
            _set_svg_filename(app, ids["entity_id"], None)
            os.remove(file_path)

    def test_processing_exception_returns_500(self, auth_client, ids, app, monkeypatch):
        """Fichier trouvé mais process_visio_file lève une exception → 500."""
        filename = "cartographie_test_erreur.vsdx"
        svg_dir = os.path.join("static", "svg")
        os.makedirs(svg_dir, exist_ok=True)
        file_path = os.path.join(svg_dir, filename)
        with open(file_path, "w") as f:
            f.write("dummy")

        def _boom(path):
            raise RuntimeError("Fichier Visio corrompu")

        monkeypatch.setattr(
            "Code.routes.activities_cartography.process_visio_file",
            _boom,
        )

        _set_svg_filename(app, ids["entity_id"], filename)
        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 500
            body = r.get_json()
            assert "error" in body
            assert "Fichier Visio corrompu" in body["error"]
        finally:
            _set_svg_filename(app, ids["entity_id"], None)
            os.remove(file_path)


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

    def test_clean_json_returns_raw_text_if_no_json_markers(self):
        """clean_json_response renvoie le texte brut si ni tableau ni objet détecté."""
        from Code.routes.translate_softskills import clean_json_response
        raw = "Pas de JSON ici du tout."
        result = clean_json_response(raw)
        assert result == raw

    # --- Succès avec client IA simulé ---

    def test_success_with_fake_client_returns_proposals(self, auth_client, monkeypatch):
        """Client IA dispo + réponse JSON valide (liste) → 200 + proposals avec niveau traduit."""
        _mock_translate_client(
            monkeypatch,
            content=json_module.dumps([
                {"habilete": "Communication", "niveau": "2"},
                {"habilete": "Leadership", "niveau": 3},
            ]),
        )
        r = auth_client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "communication, leadership",
                "activity_data": {
                    "name": "Pilotage projet",
                    "tasks": [{"description": "Coordonner l'équipe"}],
                    "constraints": [{"description": "Délai serré"}],
                    "outgoing": [
                        {"performance": {"name": "Livraison", "description": "À temps"}},
                        {"autre_champ": "ignoré"},
                    ],
                },
            },
        )
        assert r.status_code == 200
        body = r.get_json()
        proposals = body["proposals"]
        assert len(proposals) == 2
        assert proposals[0]["niveau"] == "2 (Acquisition)"
        assert proposals[1]["niveau"] == "3 (Maîtrise)"

    def test_success_english_session_lang_translates_niveau(self, app, monkeypatch):
        """Session lang='en' → prompt anglais + libellés de niveau en anglais."""
        _mock_translate_client(
            monkeypatch,
            content=json_module.dumps([{"habilete": "Teamwork", "niveau": "1"}]),
        )
        fresh = app.test_client()
        with fresh.session_transaction() as sess:
            sess["lang"] = "en"
        r = fresh.post(
            "/translate_softskills/translate",
            json={"user_input": "teamwork"},
        )
        assert r.status_code == 200
        proposals = r.get_json()["proposals"]
        assert proposals[0]["niveau"] == "1 (Basic)"

    def test_success_dict_response_wrapped_in_list(self, auth_client, monkeypatch):
        """Réponse JSON = objet unique (pas une liste) → transformé en liste d'un élément."""
        _mock_translate_client(
            monkeypatch,
            content=json_module.dumps({"habilete": "Rigueur", "niveau": "4"}),
        )
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "rigueur"},
        )
        assert r.status_code == 200
        proposals = r.get_json()["proposals"]
        assert isinstance(proposals, list)
        assert len(proposals) == 1
        assert proposals[0]["niveau"] == "4 (Excellence)"

    def test_invalid_json_response_returns_400(self, auth_client, monkeypatch):
        """Réponse IA non-JSON → 400 + message de parsing."""
        _mock_translate_client(monkeypatch, content="Ceci n'est pas du JSON valide {{{")
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 400
        assert "parsing" in r.get_json()["error"].lower()

    def test_json_response_not_list_or_dict_returns_400(self, auth_client, monkeypatch):
        """Réponse JSON valide mais scalaire (ni liste ni objet) → 400."""
        _mock_translate_client(monkeypatch, content=json_module.dumps("juste une chaîne"))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 400
        assert "tableau" in r.get_json()["error"].lower()

    def test_client_exception_returns_500(self, auth_client, monkeypatch):
        """Le client IA lève une exception pendant l'appel → 500 + message d'erreur."""
        _mock_translate_client(monkeypatch, raise_exc=RuntimeError("Timeout API"))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 500
        assert "Timeout API" in r.get_json()["error"]

    def test_success_no_activity_data_uses_empty_enumerations(self, auth_client, monkeypatch):
        """Sans activity_data (tâches/contraintes absentes) → make_enumeration renvoie
        le libellé « Aucune » sans planter la requête IA."""
        _mock_translate_client(
            monkeypatch,
            content=json_module.dumps([{"habilete": "Autonomie", "niveau": "2"}]),
        )
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "autonomie"},
        )
        assert r.status_code == 200

    def test_success_with_plain_string_tasks_and_constraints(self, auth_client, monkeypatch):
        """tasks/constraints donnés en chaînes simples (pas des dicts) → make_enumeration
        prend la branche non-dict sans erreur."""
        _mock_translate_client(
            monkeypatch,
            content=json_module.dumps([{"habilete": "Rigueur", "niveau": "2"}]),
        )
        r = auth_client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "rigueur",
                "activity_data": {
                    "name": "Activité Test",
                    "tasks": ["Préparer le dossier", "Valider"],
                    "constraints": ["Respect des délais"],
                    "outgoing": [],
                },
            },
        )
        assert r.status_code == 200
