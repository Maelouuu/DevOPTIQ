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


def _mock_openai(monkeypatch, content=None, raise_exc=None):
    """Patche openai_client_or_none() importé dans hsc_positioning pour renvoyer un faux client."""
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.hsc_positioning.openai_client_or_none",
        lambda: (fake_client, None),
    )


def _authed_client(app, lang):
    """Client isolé (non partagé) authentifié, avec la langue de session forcée.

    L'anglais est la langue par défaut de l'app (before_request _default_language
    dans Code/app.py) : un test qui veut vérifier le rendu français doit le forcer
    explicitement plutôt que de compter sur une pollution laissée par un test
    précédent sur le client partagé (auth_client).
    """
    from Code.models.models import User, Entity

    with app.app_context():
        user = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.filter_by(name="Entité Test").first()
        uid, umail, eid = user.id, user.email, entity.id

    fresh = app.test_client()
    with fresh.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_email"] = umail
        sess["active_entity_id"] = eid
        sess["lang"] = lang
    return fresh


def _cleanup_descriptors(app, hsc_name):
    with app.app_context():
        from Code.models.models import HscLevelDescriptor
        from Code.extensions import db
        HscLevelDescriptor.query.filter_by(hsc_name=hsc_name).delete()
        db.session.commit()


class TestHscLevels:

    def test_levels_returns_four_levels(self, auth_client):
        r = auth_client.get("/hsc/levels")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data["levels"].keys()) == {"1", "2", "3", "4"}

    def test_levels_default_language_french(self, app):
        r = _authed_client(app, "fr").get("/hsc/levels")
        data = r.get_json()
        assert data["levels"]["4"] == "Expertise"

    def test_levels_default_language_is_english_without_lang_in_session(self, app):
        """Sans lang en session, le before_request _default_language() retombe sur l'anglais (DEFAULT_LANG).

        Client tout neuf (pas le `client` partagé par la suite) : celui-ci peut
        avoir hérité un 'lang' en session d'un test précédent, ce qui masquerait
        justement ce comportement par défaut.
        """
        r = app.test_client().get("/hsc/levels")
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

    def test_upsert_descriptor_creates_row(self, app):
        name = "Auto-organisation Test 54"
        fr_client = _authed_client(app, "fr")
        try:
            r = fr_client.post(
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

            r2 = fr_client.get(f"/hsc/descriptors/{name}")
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

    def test_position_with_ai_key_success_returns_proposal(self, app, monkeypatch):
        content = json.dumps({
            "probable_level": 3, "confidence": "high",
            "evidence_summary": "Organise seul son travail.",
            "missing_evidence_for_next_level": "Peu d'exemples d'accompagnement d'autrui.",
            "development_focus": "Coacher un pair.",
        })
        _mock_openai(monkeypatch, content=content)
        r = _authed_client(app, "fr").post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Auto-organisation", "responses": ["Je planifie mes tâches."],
                              "examples": "Semaine chargée bien gérée."}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["source"] == "AI"
        proposal = data["proposal"]
        assert proposal["hsc_name"] == "Auto-organisation"
        assert proposal["probable_level"] == 3
        assert proposal["probable_label"] == "Maîtrise"
        assert proposal["confidence"] == "high"
        assert proposal["evidence_summary"] == "Organise seul son travail."
        assert proposal["development_focus"] == "Coacher un pair."
        assert "évaluateur" in data["note"]

    def test_position_with_ai_key_english_lang(self, app, monkeypatch):
        content = json.dumps({"probable_level": 4, "confidence": "medium"})
        _mock_openai(monkeypatch, content=content)
        fresh = _authed_client(app, "en")
        r = fresh.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Self-organisation", "responses": ["I plan my week."]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["proposal"]["probable_label"] == "Expert"

    def test_position_with_ai_key_unknown_level_returns_null_label(self, auth_client, monkeypatch):
        _mock_openai(monkeypatch, content=json.dumps({"probable_level": 99, "confidence": "low"}))
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Coopération", "responses": ["a"]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposal = r.get_json()["proposal"]
        assert proposal["probable_level"] is None
        assert proposal["probable_label"] is None

    def test_position_with_ai_key_exception_returns_error_source(self, auth_client, monkeypatch):
        _mock_openai(monkeypatch, raise_exc=RuntimeError("boom"))
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
