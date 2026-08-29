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
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.hsc_positioning


class _FakeCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc:
            raise self._raise_exc
        message = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = SimpleNamespace(completions=_FakeCompletions(content=content, raise_exc=raise_exc))


def _patch_ai_client(monkeypatch, content=None, raise_exc=None):
    fake = _FakeClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.hsc_positioning.openai_client_or_none",
        lambda: (fake, None),
    )


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

    def test_levels_default_language_french(self, auth_client):
        r = auth_client.get("/hsc/levels")
        data = r.get_json()
        assert data["levels"]["4"] == "Expertise"

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

    def test_position_with_mocked_ai_returns_proposal(self, auth_client, monkeypatch):
        """Client IA mocké renvoie un JSON valide → proposal complète, source=AI."""
        _patch_ai_client(
            monkeypatch,
            content=json.dumps({
                "probable_level": 3,
                "confidence": "high",
                "evidence_summary": "Anticipe les blocages.",
                "missing_evidence_for_next_level": "Peu d'exemples de mentorat.",
                "development_focus": "Accompagner un pair.",
            }),
        )
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({
                "hsc_name": "Auto-organisation",
                "responses": ["Je priorise mes tâches sans qu'on me le demande."],
                "examples": "Livraison anticipée d'un projet.",
            }),
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
        assert proposal["evidence_summary"] == "Anticipe les blocages."

    def test_position_with_mocked_ai_invalid_level_becomes_null(self, auth_client, monkeypatch):
        """Un niveau hors 1-4 renvoyé par l'IA est neutralisé (pas de label ni de niveau)."""
        _patch_ai_client(monkeypatch, content=json.dumps({"probable_level": 9}))
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Coopération", "responses": ["a"]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposal = r.get_json()["proposal"]
        assert proposal["probable_level"] is None
        assert proposal["probable_label"] is None
        assert proposal["confidence"] == "medium"

    def test_position_ai_client_exception_returns_error_source(self, auth_client, monkeypatch):
        """Une exception du client IA est capturée : réponse 200 avec source=error, jamais de 500."""
        _patch_ai_client(monkeypatch, raise_exc=RuntimeError("panne réseau IA"))
        r = auth_client.post(
            "/hsc/position",
            data=json.dumps({"hsc_name": "Coopération", "responses": ["a"]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["proposal"] is None
        assert data["source"] == "error"
        assert "panne réseau IA" in data["error"]
