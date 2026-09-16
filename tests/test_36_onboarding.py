# tests/test_36_onboarding.py
"""
Couvre :
  - GET  /roles/<id>/onboarding          (onboarding.py)
  - POST /roles/<id>/onboarding/generate (onboarding.py)
  - POST /translate_softskills/translate (translate_softskills.py)
"""
import json
import pytest

pytestmark = pytest.mark.onboarding


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
        """get_prompt() renvoie None (prompts non chargés) → 500."""
        import Code.routes.onboarding as onboarding_mod

        monkeypatch.setattr(onboarding_mod, "get_prompt", lambda *a, **k: None)

        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": ["Auto-organisation"]},
                content_type="application/json",
            )
            assert r.status_code == 500
            data = r.get_json()
            assert "error" in data
        finally:
            _delete_role(app, role_id)

    def test_prompt_indisponible_message_anglais(self, auth_client, app, ids, monkeypatch):
        """get_prompt() renvoie None avec lang='en' → message anglais."""
        import Code.routes.onboarding as onboarding_mod

        monkeypatch.setattr(onboarding_mod, "get_prompt", lambda *a, **k: None)

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
            data = r.get_json()
            assert "prompts not loaded" in data["error"]
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("lang", None)
            _delete_role(app, role_id)

    def test_generation_reussie_retourne_plan(self, auth_client, app, ids, monkeypatch):
        """Clé + client IA fonctionnels → 200 et le plan est sauvegardé sur le rôle."""
        import Code.routes.onboarding as onboarding_mod
        import Code.ai_client as ai_client_mod
        from Code.extensions import db
        from Code.models.models import Role

        monkeypatch.setattr(onboarding_mod, "get_openai_key", lambda: "fake-key")

        class _FakeMessage:
            content = "Plan d'onboarding généré (fake)."

        class _FakeChoice:
            message = _FakeMessage()

        class _FakeResponse:
            choices = [_FakeChoice()]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResponse()

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr(
            ai_client_mod, "make_ai_client", lambda *a, **k: (_FakeClient(), "fake-model", None)
        )

        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": ["Auto-organisation"]},
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["onboarding_plan"] == "Plan d'onboarding généré (fake)."
            assert "message" in data

            with app.app_context():
                role = Role.query.get(role_id)
                assert role.onboarding_plan == "Plan d'onboarding généré (fake)."
        finally:
            _delete_role(app, role_id)

    def test_generation_exception_client_retourne_500(self, auth_client, app, ids, monkeypatch):
        """Exception levée par le client IA → 500 avec le message de l'exception."""
        import Code.routes.onboarding as onboarding_mod
        import Code.ai_client as ai_client_mod

        monkeypatch.setattr(onboarding_mod, "get_openai_key", lambda: "fake-key")

        class _FakeCompletions:
            def create(self, **kwargs):
                raise RuntimeError("boom IA")

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr(
            ai_client_mod, "make_ai_client", lambda *a, **k: (_FakeClient(), "fake-model", None)
        )

        role_id = _create_role(app, ids)
        try:
            r = auth_client.post(
                f"/roles/{role_id}/onboarding/generate",
                json={"hsc_list": []},
                content_type="application/json",
            )
            assert r.status_code == 500
            data = r.get_json()
            assert data["error"] == "boom IA"
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
