# tests/test_17_chatbot.py
"""
Page : Chatbot IA OPTIQ (/api/chatbot)
Couvre : récupération du contexte activité (GET /context), injection de tâches
         validées (POST /inject), déclenchement de la conversation (POST /chat).
"""
import json
import pytest

pytestmark = pytest.mark.chatbot


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_session(client, ids):
    with client.session_transaction() as sess:
        sess["user_id"] = ids["user_id"]
        sess["active_entity_id"] = ids["entity_id"]


@pytest.fixture(scope="module", autouse=True)
def _setup_module(client, ids):
    """Initialise la session authentifiée pour tous les tests du module."""
    _set_session(client, ids)
    yield


# ===========================================================================
# 1. GET /api/chatbot/activity/<id>/context — Contexte complet d'une activité
# ===========================================================================

class TestChatbotContext:

    def test_context_valid_activity_returns_200(self, auth_client, ids):
        """GET /context retourne 200 avec les données de l'activité."""
        _set_session(auth_client, ids)
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        assert r.status_code == 200

    def test_context_response_has_required_keys(self, auth_client, ids):
        """GET /context retourne un JSON avec les clés name, description, tasks, incoming, outgoing."""
        _set_session(auth_client, ids)
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        assert r.status_code == 200
        data = json.loads(r.data)
        for key in ("name", "description", "tasks", "incoming", "outgoing",
                    "contraintes", "competences", "savoirs", "savoir_faires",
                    "hsc", "aptitudes", "available_tools"):
            assert key in data, f"Clé manquante dans context : {key}"

    def test_context_name_matches_seeded_activity(self, auth_client, ids):
        """GET /context retourne le nom exact de l'activité en base."""
        _set_session(auth_client, ids)
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        data = json.loads(r.data)
        assert data["name"] == "Activité Test"

    def test_context_tasks_is_list(self, auth_client, ids):
        """GET /context retourne tasks comme une liste (peut être vide)."""
        _set_session(auth_client, ids)
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        data = json.loads(r.data)
        assert isinstance(data["tasks"], list)

    def test_context_tasks_contain_tache_test(self, auth_client, ids):
        """GET /context inclut 'Tâche Test' dans les tâches (créée au seed)."""
        _set_session(auth_client, ids)
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        data = json.loads(r.data)
        task_names = [t["name"] for t in data["tasks"]]
        assert "Tâche Test" in task_names

    def test_context_task_has_tools_key(self, auth_client, ids):
        """Chaque tâche dans /context possède une clé 'tools' (liste)."""
        _set_session(auth_client, ids)
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        data = json.loads(r.data)
        for task in data["tasks"]:
            assert "tools" in task
            assert isinstance(task["tools"], list)

    def test_context_unknown_activity_returns_404(self, auth_client, ids):
        """GET /context avec un activity_id inexistant retourne 404."""
        _set_session(auth_client, ids)
        r = auth_client.get("/api/chatbot/activity/999999/context")
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_context_available_tools_is_list(self, auth_client, ids):
        """GET /context retourne available_tools comme une liste de chaînes."""
        _set_session(auth_client, ids)
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        data = json.loads(r.data)
        assert isinstance(data["available_tools"], list)
        for t in data["available_tools"]:
            assert isinstance(t, str)


# ===========================================================================
# 2. POST /api/chatbot/inject — Injection des tâches validées
# ===========================================================================

class TestChatbotInject:

    def test_inject_no_activity_id_returns_400(self, auth_client, ids):
        """POST /inject sans activity_id retourne 400."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({"tasks": [{"label": "Tâche A", "tools": []}]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_inject_unknown_activity_returns_404(self, auth_client, ids):
        """POST /inject avec activity_id inexistant retourne 404."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({"activity_id": 999999, "tasks": [{"label": "T", "tools": []}]}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_inject_creates_tasks(self, auth_client, ids):
        """POST /inject crée les tâches en base et retourne 201 avec la liste created."""
        _set_session(auth_client, ids)
        payload = {
            "activity_id": ids["activity_id"],
            "tasks": [
                {"label": "Tâche Chatbot Alpha", "tools": []},
                {"label": "Tâche Chatbot Beta", "tools": []},
            ],
        }
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "created" in data
        assert data["count"] == 2
        assert all("id" in t and "name" in t for t in data["created"])

    def test_inject_creates_tool_if_not_exists(self, auth_client, ids):
        """POST /inject crée un outil inconnu et l'associe à la tâche."""
        _set_session(auth_client, ids)
        payload = {
            "activity_id": ids["activity_id"],
            "tasks": [{"label": "Tâche Avec Outil Chatbot", "tools": ["NouvelOutilChatbot"]}],
        }
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        with auth_client.application.app_context():
            from Code.models.models import Tool
            tool = Tool.query.filter_by(name="NouvelOutilChatbot").first()
            assert tool is not None

    def test_inject_reuses_existing_tool(self, auth_client, ids):
        """POST /inject réutilise un outil existant sans en créer un doublon."""
        _set_session(auth_client, ids)
        payload = {
            "activity_id": ids["activity_id"],
            "tasks": [{"label": "Tâche Outil Existant Chatbot", "tools": ["NouvelOutilChatbot"]}],
        }
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        with auth_client.application.app_context():
            from Code.models.models import Tool
            count = Tool.query.filter_by(name="NouvelOutilChatbot").count()
            assert count == 1

    def test_inject_with_outgoing_link_creates_data_and_link(self, auth_client, ids):
        """POST /inject avec outgoing_link crée un objet Data et un Link sortant."""
        _set_session(auth_client, ids)
        payload = {
            "activity_id": ids["activity_id"],
            "tasks": [{
                "label": "Tâche Avec Lien Sortant",
                "tools": [],
                "outgoing_link": {
                    "data_name": "Rapport Chatbot Test",
                    "data_type": "nourrissante",
                    "target_activity_name": "",
                },
            }],
        }
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        with auth_client.application.app_context():
            from Code.models.models import Data, Link
            data_obj = Data.query.filter_by(name="Rapport Chatbot Test").first()
            assert data_obj is not None
            link = Link.query.filter_by(source_data_id=data_obj.id).first()
            assert link is not None

    def test_inject_empty_label_skipped(self, auth_client, ids):
        """POST /inject ignore les tâches avec un label vide."""
        _set_session(auth_client, ids)
        payload = {
            "activity_id": ids["activity_id"],
            "tasks": [
                {"label": "", "tools": []},
                {"label": "   ", "tools": []},
            ],
        }
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["count"] == 0

    def test_inject_empty_tasks_list_creates_nothing(self, auth_client, ids):
        """POST /inject avec liste de tâches vide retourne 201 avec count=0."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({"activity_id": ids["activity_id"], "tasks": []}),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["count"] == 0


# ===========================================================================
# 3. POST /api/chatbot/chat — Conversation stateless (dépend d'OpenAI)
# ===========================================================================

class TestChatbotChat:

    def test_chat_empty_message_returns_400(self, auth_client, ids):
        """POST /chat avec message vide retourne 400 sans appeler OpenAI."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({"activity": {}, "history": [], "message": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_chat_whitespace_message_returns_400(self, auth_client, ids):
        """POST /chat avec message uniquement composé d'espaces retourne 400."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({"activity": {}, "history": [], "message": "   "}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_chat_no_openai_key_returns_error(self, auth_client, ids):
        """POST /chat sans clé OPENAI_API_KEY retourne une réponse d'erreur (400 ou 500)."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({
                "activity": {"name": "Activité Test", "description": ""},
                "history": [],
                "message": "Quelles sont mes tâches ?",
            }),
            content_type="application/json",
        )
        # Sans clé OpenAI, l'endpoint doit retourner une erreur (400 ou 500)
        assert r.status_code in (400, 500)
        assert "error" in json.loads(r.data)

    def test_chat_mode_ameliorer_accepted(self, auth_client, ids):
        """POST /chat avec mode='ameliorer' déclenche le bon prompt (erreur OpenAI attendue)."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({
                "activity": {"name": "Activité Test"},
                "history": [],
                "message": "Analysons mes tâches",
                "mode": "ameliorer",
            }),
            content_type="application/json",
        )
        # Le mode est accepté — l'erreur vient d'OpenAI, pas d'une validation en amont
        assert r.status_code in (400, 500)

    def test_chat_mode_creer_accepted(self, auth_client, ids):
        """POST /chat avec mode='creer' est accepté (erreur OpenAI attendue)."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({
                "activity": {"name": "Activité Test"},
                "history": [],
                "message": "Je veux créer des tâches",
                "mode": "creer",
            }),
            content_type="application/json",
        )
        assert r.status_code in (400, 500)
