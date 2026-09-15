# tests/test_54_hsc_positioning.py
"""
Page : Auto-positionnement HSC (/hsc — CDC 7)
Couverture :
  - GET  /hsc/levels                          → libellés des 4 niveaux HSC
  - GET  /hsc/descriptors/<hsc_name>           → descripteurs comportementaux par niveau
  - POST /hsc/descriptors                      → upsert d'un descripteur
  - POST /hsc/position                         → auto-positionnement (repli sans clé IA)
"""
import json
import pytest

pytestmark = pytest.mark.hsc_positioning


def _cleanup_descriptors(app, hsc_name):
    with app.app_context():
        from Code.models.models import HscLevelDescriptor
        from Code.extensions import db
        HscLevelDescriptor.query.filter_by(hsc_name=hsc_name).delete()
        db.session.commit()


def _force_lang(client, lang="fr"):
    """Force explicitement la langue de session : l'app par défaut part en anglais
    (Code/app.py::_default_language), donc les tests qui vérifient des libellés FR
    ne doivent jamais dépendre d'un état de session laissé par un test précédent."""
    with client.session_transaction() as s:
        s["lang"] = lang


def _clear_lang(client):
    """Retire toute langue de session : le client de test étant partagé (scope=session,
    cf. conftest.py), un test précédent peut avoir laissé 'lang' en session."""
    with client.session_transaction() as s:
        s.pop("lang", None)


# ---------------------------------------------------------------------------
# Fake client IA — mêmes contrats que _FakeOpenAIClient de test_22_propose_ia,
# dupliqué ici pour couvrir /hsc/position "avec clé IA" (succès + exception),
# branches non exercées par le test de repli sans clé.
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


def _mock_ai(monkeypatch, content=None, raise_exc=None):
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.hsc_positioning.openai_client_or_none",
        lambda: (fake_client, None),
    )


class TestHscLevels:

    def test_levels_returns_four_levels(self, auth_client):
        r = auth_client.get("/hsc/levels")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data["levels"].keys()) == {"1", "2", "3", "4"}

    def test_levels_labels_in_french_when_lang_fr(self, auth_client):
        """Session lang='fr' explicite : les libellés de niveau sont traduits en français.
        (L'app démarre en anglais par défaut — Code/app.py::_default_language — donc ce test
        ne doit pas dépendre d'un défaut FR implicite ni d'un état laissé par un autre test.)"""
        _force_lang(auth_client, "fr")
        r = auth_client.get("/hsc/levels")
        data = r.get_json()
        assert data["levels"]["4"] == "Expertise"

    def test_levels_labels_in_english_by_default(self, auth_client):
        """Sans langue explicite en session, l'app retombe sur l'anglais (comportement voulu)."""
        _clear_lang(auth_client)
        r = auth_client.get("/hsc/levels")
        data = r.get_json()
        assert data["levels"]["4"] == "Expert"

    def test_levels_accessible_without_auth(self, client):
        r = client.get("/hsc/levels")
        assert r.status_code == 200


class TestHscDescriptors:

    def test_descriptors_empty_for_unknown_hsc(self, auth_client):
        r = auth_client.get("/hsc/descriptors/Inconnue")
        assert r.status_code == 200
        data = r.get_json()
        assert data["hsc_name"] == "Inconnue"
        assert data["descriptors"] == []

    def test_upsert_descriptor_creates_row(self, auth_client, app):
        name = "Auto-organisation Test 54"
        _force_lang(auth_client, "fr")
        try:
            r = auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({
                    "hsc_name": name, "level": 2,
                    "descriptor_fr": "Organise ses priorités seul.",
                    "observable_behaviors_fr": "Planifie sa semaine sans rappel.",
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["ok"] is True
            assert isinstance(data["id"], int)

            r2 = auth_client.get(f"/hsc/descriptors/{name}")
            data2 = r2.get_json()
            assert len(data2["descriptors"]) == 1
            d = data2["descriptors"][0]
            assert d["level"] == 2
            assert d["level_label"] == "Acquisition"
            assert d["descriptor"] == "Organise ses priorités seul."
        finally:
            _cleanup_descriptors(app, name)

    def test_upsert_descriptor_missing_name_returns_400(self, auth_client):
        r = auth_client.post(
            "/hsc/descriptors",
            data=json.dumps({"level": 1}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid"

    def test_upsert_descriptor_invalid_level_returns_400(self, auth_client):
        r = auth_client.post(
            "/hsc/descriptors",
            data=json.dumps({"hsc_name": "Coopération", "level": 9}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_upsert_descriptor_twice_updates_not_duplicates(self, auth_client, app):
        name = "Ecoute Active Test 54"
        try:
            auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({"hsc_name": name, "level": 1, "descriptor_fr": "Première version."}),
                content_type="application/json",
            )
            auth_client.post(
                "/hsc/descriptors",
                data=json.dumps({"hsc_name": name, "level": 1, "descriptor_fr": "Version corrigée."}),
                content_type="application/json",
            )
            r = auth_client.get(f"/hsc/descriptors/{name}")
            data = r.get_json()
            assert len(data["descriptors"]) == 1
            assert data["descriptors"][0]["descriptor"] == "Version corrigée."
        finally:
            _cleanup_descriptors(app, name)


class TestHscPosition:

    def test_position_missing_name_returns_400(self, auth_client):
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"responses": ["a"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid"

    def test_position_without_ai_key_returns_null_proposal(self, auth_client):
        """Sans clé OpenAI configurée, repli : proposal=None, source explicite (jamais d'erreur 500)."""
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Auto-organisation", "responses": ["Je planifie mes tâches chaque lundi."]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "proposal" in data
        assert "source" in data

    def test_position_accepts_empty_responses(self, auth_client):
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Coopération"}),
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_position_with_ai_key_returns_proposal(self, auth_client, monkeypatch):
        """Avec un client IA disponible, le niveau probable est parsé et le libellé résolu."""
        payload = json.dumps({
            "probable_level": 3, "confidence": "high",
            "evidence_summary": "Anticipe les conflits.",
            "missing_evidence_for_next_level": "Former d'autres personnes.",
            "development_focus": "Mentorat.",
        })
        _mock_ai(monkeypatch, content=payload)
        _force_lang(auth_client, "fr")
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({
                "hsc_name": "Coopération",
                "responses": ["Je résous les désaccords en réunion."],
                "examples": "Cas concret vécu la semaine dernière.",
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["source"] == "AI"
        proposal = data["proposal"]
        assert proposal["hsc_name"] == "Coopération"
        assert proposal["probable_level"] == 3
        assert proposal["probable_label"] == "Maîtrise"
        assert proposal["confidence"] == "high"
        assert proposal["evidence_summary"] == "Anticipe les conflits."

    def test_position_with_ai_key_invalid_level_falls_back_to_none(self, auth_client, monkeypatch):
        """Un niveau hors [1-4] renvoyé par l'IA est ignoré (pas de label bancal)."""
        payload = json.dumps({"probable_level": 99, "confidence": "low"})
        _mock_ai(monkeypatch, content=payload)
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Coopération", "responses": ["a"]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposal = r.get_json()["proposal"]
        assert proposal["probable_level"] is None
        assert proposal["probable_label"] is None
        assert proposal["confidence"] == "low"

    def test_position_ai_exception_returns_error_source(self, auth_client, monkeypatch):
        """Une exception du client IA (timeout, JSON invalide...) ne fait jamais planter la route."""
        _mock_ai(monkeypatch, raise_exc=RuntimeError("boom"))
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Coopération", "responses": ["a"]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["proposal"] is None
        assert data["source"] == "error"
        assert "boom" in data["error"]
