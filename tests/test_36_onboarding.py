# tests/test_36_onboarding.py
"""
Couvre :
  - GET  /roles/<id>/onboarding          (onboarding.py)
  - POST /roles/<id>/onboarding/generate (onboarding.py)
  - POST /translate_softskills/translate (translate_softskills.py)
"""
import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.onboarding


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
        "Code.ai_client.make_ai_client",
        lambda *a, **kw: (fake, "gpt-4o-mini", None),
    )


def _create_role(app, ids):
    """Crée un rôle de test et retourne son id."""
    from Code.extensions import db
    from Code.models.models import Role

    with app.app_context():
        role = Role(entity_id=ids["entity_id"], name="Rôle Onboarding Test")
        db.session.add(role)
        db.session.commit()
        return role.id


def _delete_role(app, role_id):
    from Code.extensions import db
    from Code.models.models import Role

    with app.app_context():
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
            db.session.commit()


# ===========================================================================
# 1. GET /roles/<id>/onboarding
# ===========================================================================

class TestGetOnboarding:

    def test_role_inexistant_404(self, auth_client):
        """Rôle inconnu → 404."""
        r = auth_client.get("/roles/999999/onboarding")
        assert r.status_code == 404
        data = r.get_json()
        assert "error" in data

    def test_role_sans_plan_404(self, auth_client, app, ids):
        """Rôle existant sans plan d'onboarding → 404."""
        role_id = _create_role(app, ids)
        try:
            r = auth_client.get(f"/roles/{role_id}/onboarding")
            assert r.status_code == 404
            data = r.get_json()
            assert "error" in data
        finally:
            _delete_role(app, role_id)

    def test_role_avec_plan_retourne_plan(self, auth_client, app, ids):
        """Rôle avec onboarding_plan → 200 avec le plan."""
        from Code.extensions import db
        from Code.models.models import Role

        role_id = _create_role(app, ids)
        with app.app_context():
            role = Role.query.get(role_id)
            role.onboarding_plan = "Contenu du plan test"
            db.session.commit()

        try:
            r = auth_client.get(f"/roles/{role_id}/onboarding")
            assert r.status_code == 200
            data = r.get_json()
            assert "onboarding_plan" in data
            assert data["onboarding_plan"] == "Contenu du plan test"
        finally:
            _delete_role(app, role_id)

    def test_reponse_content_type_json(self, auth_client):
        """La réponse est bien du JSON."""
        r = auth_client.get("/roles/999999/onboarding")
        assert r.content_type.startswith("application/json")


# ===========================================================================
# 2. POST /roles/<id>/onboarding/generate
# ===========================================================================

class TestGenerateOnboarding:

    def test_role_inexistant_404(self, auth_client):
        """Rôle inconnu → 404."""
        r = auth_client.post(
            "/roles/999999/onboarding/generate",
            json={"hsc_list": ["Auto-organisation"]},
            content_type="application/json",
        )
        assert r.status_code == 404
        data = r.get_json()
        assert "error" in data

    def test_sans_cle_openai_retourne_500(self, auth_client, app, ids, monkeypatch):
        """Sans clé OPENAI_API_KEY → 500 avec message d'erreur."""
        import os
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": ["Auto-organisation", "Coopération"]},
                content_type="application/json",
            )
            assert r.status_code == 500
            data = r.get_json()
            assert "error" in data
        finally:
            _delete_role(app, role_id)

    def test_payload_vide_sans_cle_retourne_500(self, auth_client, app, ids, monkeypatch):
        """Payload JSON vide (hsc_list=[]) + pas de clé → 500."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={},
                content_type="application/json",
            )
            assert r.status_code == 500
        finally:
            _delete_role(app, role_id)

    def test_reponse_content_type_json(self, auth_client, monkeypatch):
        """La réponse est du JSON."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/roles/999999/onboarding/generate",
            json={"hsc_list": []},
            content_type="application/json",
        )
        assert r.content_type.startswith("application/json")

    def test_prompt_indisponible_retourne_500(self, auth_client, app, ids, monkeypatch):
        """get_prompt renvoie None (prompts non chargés) → 500 avant même de vérifier la clé IA."""
        monkeypatch.setattr("Code.routes.onboarding.get_prompt", lambda *a, **kw: None)
        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": ["Auto-organisation"]},
                content_type="application/json",
            )
            assert r.status_code == 500
            assert "error" in r.get_json()
        finally:
            _delete_role(app, role_id)

    def test_prompt_indisponible_message_anglais(self, auth_client, app, ids, monkeypatch):
        """Même repli, message en anglais si lang=en en session."""
        monkeypatch.setattr("Code.routes.onboarding.get_prompt", lambda *a, **kw: None)
        role_id = _create_role(app, ids)
        try:
            with auth_client.session_transaction() as sess:
                sess["lang"] = "en"
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": []},
                content_type="application/json",
            )
            assert r.status_code == 500
            assert "AI unavailable" in r.get_json()["error"]
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("lang", None)
            _delete_role(app, role_id)

    def test_generation_reussie_sauvegarde_le_plan(self, auth_client, app, ids, monkeypatch):
        """Client IA mocké → 200, plan renvoyé et persisté sur le rôle."""
        from Code.extensions import db
        from Code.models.models import Role

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        _patch_ai_client(monkeypatch, content="  Plan d'onboarding généré.  ")
        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": ["Auto-organisation"]},
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["onboarding_plan"] == "Plan d'onboarding généré."
            assert "message" in data

            with app.app_context():
                role = Role.query.get(role_id)
                assert role.onboarding_plan == "Plan d'onboarding généré."
        finally:
            _delete_role(app, role_id)

    def test_generation_exception_ia_retourne_500(self, auth_client, app, ids, monkeypatch):
        """Une exception du client IA pendant la génération → 500 avec le message d'erreur."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
        _patch_ai_client(monkeypatch, raise_exc=RuntimeError("panne réseau IA"))
        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": ["Coopération"]},
                content_type="application/json",
            )
            assert r.status_code == 500
            assert "panne réseau IA" in r.get_json()["error"]
        finally:
            _delete_role(app, role_id)


# ===========================================================================
# 3. POST /translate_softskills/translate
# ===========================================================================

class TestTranslateSoftskills:

    def test_sans_user_input_retourne_400(self, auth_client):
        """Payload sans 'user_input' → 400."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"activity_data": {}},
            content_type="application/json",
        )
        assert r.status_code == 400
        data = r.get_json()
        assert "error" in data

    def test_user_input_vide_retourne_400(self, auth_client):
        """'user_input' vide → 400."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "", "activity_data": {}},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_sans_cle_openai_retourne_500(self, auth_client, monkeypatch):
        """Sans clé OPENAI_API_KEY → 500."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "communication, adaptabilité",
                "activity_data": {
                    "name": "Accueil client",
                    "tasks": ["Répondre aux appels"],
                    "constraints": [],
                    "outgoing": [],
                },
            },
            content_type="application/json",
        )
        assert r.status_code == 500
        data = r.get_json()
        assert "error" in data

    def test_payload_vide_retourne_400(self, auth_client):
        """Payload JSON vide → 400 (pas de user_input)."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_content_type_json(self, auth_client):
        """La réponse est du JSON."""
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "", "activity_data": {}},
            content_type="application/json",
        )
        assert r.content_type.startswith("application/json")
