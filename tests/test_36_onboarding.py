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
        """get_prompt() renvoie None (prompts non chargés) → 500 avant même de vérifier la clé."""
        import Code.routes.onboarding as onboarding_module

        monkeypatch.setattr(onboarding_module, "get_prompt", lambda *a, **k: None)

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

    def test_succes_genere_et_sauvegarde_le_plan(self, auth_client, app, ids, monkeypatch):
        """Cas nominal : IA mockée renvoie un plan, sauvegardé sur le rôle → 200."""
        import Code.routes.onboarding as onboarding_module
        from Code.extensions import db
        from Code.models.models import Role

        class _FakeMessage:
            content = "Plan d'onboarding généré par l'IA."

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

        monkeypatch.setattr(onboarding_module, "get_prompt", lambda *a, **k: "PROMPT")
        monkeypatch.setattr(onboarding_module, "get_openai_key", lambda: "fake-key")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_FakeClient(), "fake-model", None),
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
            assert data["onboarding_plan"] == "Plan d'onboarding généré par l'IA."
            with app.app_context():
                role = Role.query.get(role_id)
                assert role.onboarding_plan == "Plan d'onboarding généré par l'IA."
        finally:
            _delete_role(app, role_id)

    def test_exception_client_ia_retourne_500(self, auth_client, app, ids, monkeypatch):
        """Le client IA lève une exception pendant l'appel → 500 avec le message d'erreur."""
        import Code.routes.onboarding as onboarding_module

        class _FakeCompletions:
            def create(self, **kwargs):
                raise RuntimeError("panne réseau IA")

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr(onboarding_module, "get_prompt", lambda *a, **k: "PROMPT")
        monkeypatch.setattr(onboarding_module, "get_openai_key", lambda: "fake-key")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_FakeClient(), "fake-model", None),
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
            assert "panne réseau IA" in data["error"]
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

    def test_prompt_indisponible_retourne_500(self, auth_client, monkeypatch):
        """get_prompt() renvoie None (prompts non chargés) → 500, une fois le client IA dispo."""
        import Code.routes.translate_softskills as ts_module

        class _FakeClient:
            pass

        monkeypatch.setattr(ts_module, "get_prompt", lambda *a, **k: None)
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_FakeClient(), "fake-model", None),
        )
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication", "activity_data": {}},
            content_type="application/json",
        )
        assert r.status_code == 500
        data = r.get_json()
        assert "error" in data

    @staticmethod
    def _fake_client_returning(content):
        class _FakeMessage:
            pass

        class _FakeChoice:
            pass

        class _FakeResponse:
            pass

        class _FakeCompletions:
            def create(self, **kwargs):
                msg = _FakeMessage()
                msg.content = content
                choice = _FakeChoice()
                choice.message = msg
                resp = _FakeResponse()
                resp.choices = [choice]
                return resp

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        return _FakeClient()

    def test_succes_liste_de_propositions_avec_niveau_traduit(self, auth_client, monkeypatch):
        """Cas nominal FR : réponse IA = liste JSON → 200, niveau numérique traduit en libellé."""
        import Code.routes.translate_softskills as ts_module

        payload = json.dumps([
            {"description": "Écoute active", "niveau": "2"},
            {"description": "Sans niveau numérique", "niveau": "déjà un libellé"},
        ])
        monkeypatch.setattr(ts_module, "get_prompt", lambda *a, **k: "PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (self._fake_client_returning(payload), "fake-model", None),
        )

        r = auth_client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "communication, adaptabilité",
                "activity_data": {
                    "name": "Accueil client",
                    "tasks": ["Répondre aux appels"],
                    "constraints": ["Bruit ambiant"],
                    "outgoing": [
                        {"performance": {"name": "Satisfaction", "description": "Taux de satisfaction élevé"}},
                        {"no_performance_key": True},
                    ],
                },
            },
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["proposals"]) == 2
        assert data["proposals"][0]["niveau"] == "2 (Acquisition)"
        assert data["proposals"][1]["niveau"] == "déjà un libellé"

    def test_succes_en_anglais_traduit_niveau(self, auth_client, monkeypatch):
        """Cas nominal EN (session lang=en) : prompt/system anglais, niveau map anglaise."""
        import Code.routes.translate_softskills as ts_module

        payload = json.dumps([{"description": "Active listening", "niveau": 3}])
        monkeypatch.setattr(ts_module, "get_prompt", lambda *a, **k: "PROMPT EN")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (self._fake_client_returning(payload), "fake-model", None),
        )

        with auth_client.session_transaction() as sess:
            sess["lang"] = "en"
        try:
            r = auth_client.post(
                "/translate_softskills/translate",
                json={"user_input": "communication", "activity_data": {}},
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["proposals"][0]["niveau"] == "3 (Proficient)"
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("lang", None)

    def test_reponse_objet_unique_est_enveloppee_en_liste(self, auth_client, monkeypatch):
        """L'IA renvoie un objet JSON seul (pas un tableau) → enveloppé dans une liste, 200."""
        import Code.routes.translate_softskills as ts_module

        payload = json.dumps({"description": "Rigueur", "niveau": "1"})
        monkeypatch.setattr(ts_module, "get_prompt", lambda *a, **k: "PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (self._fake_client_returning(payload), "fake-model", None),
        )

        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "rigueur", "activity_data": {}},
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data["proposals"], list)
        assert data["proposals"][0]["description"] == "Rigueur"

    def test_reponse_json_ni_liste_ni_objet_retourne_400(self, auth_client, monkeypatch):
        """L'IA renvoie un JSON scalaire (ni liste ni objet) → 400."""
        import Code.routes.translate_softskills as ts_module

        payload = json.dumps("juste une chaîne")
        monkeypatch.setattr(ts_module, "get_prompt", lambda *a, **k: "PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (self._fake_client_returning(payload), "fake-model", None),
        )

        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "x", "activity_data": {}},
            content_type="application/json",
        )
        assert r.status_code == 400
        data = r.get_json()
        assert "error" in data

    def test_reponse_non_json_retourne_400(self, auth_client, monkeypatch):
        """L'IA renvoie un texte non-JSON → erreur de parsing → 400."""
        import Code.routes.translate_softskills as ts_module

        monkeypatch.setattr(ts_module, "get_prompt", lambda *a, **k: "PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (self._fake_client_returning("ceci n'est pas du JSON"), "fake-model", None),
        )

        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "x", "activity_data": {}},
            content_type="application/json",
        )
        assert r.status_code == 400
        data = r.get_json()
        assert "error" in data

    def test_exception_pendant_appel_ia_retourne_500(self, auth_client, monkeypatch):
        """Le client IA lève une exception pendant l'appel → 500."""
        import Code.routes.translate_softskills as ts_module

        class _FakeCompletions:
            def create(self, **kwargs):
                raise RuntimeError("panne réseau IA")

        class _FakeChat:
            completions = _FakeCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr(ts_module, "get_prompt", lambda *a, **k: "PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_FakeClient(), "fake-model", None),
        )

        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "x", "activity_data": {}},
            content_type="application/json",
        )
        assert r.status_code == 500
        data = r.get_json()
        assert "panne réseau IA" in data["error"]
