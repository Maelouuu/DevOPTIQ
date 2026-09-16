# tests/test_17_chatbot.py
"""
API : Assistant OPTIQ Chatbot (/api/chatbot)
Couvre : récupération du contexte activité, injection de tâches (avec outils et liens),
         et validation du routage chat (message vide, mode, OpenAI indisponible).
"""
import json
import pytest

pytestmark = pytest.mark.chatbot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cleanup_task(app, name, activity_id):
    with app.app_context():
        from Code.models.models import Task
        from Code.extensions import db
        t = Task.query.filter_by(name=name, activity_id=activity_id).first()
        if t:
            db.session.delete(t)
            db.session.commit()


def _create_activity(app, entity_id, name):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="Description")
        db.session.add(a)
        db.session.commit()
        return a.id


def _delete_activity(app, activity_id):
    with app.app_context():
        from Code.models.models import Activities, Link, Data
        from Code.extensions import db
        Link.query.filter(
            db.or_(Link.source_activity_id == activity_id, Link.target_activity_id == activity_id)
        ).delete(synchronize_session=False)
        Data.query.filter_by(producer_activity_id=activity_id).delete()
        a = Activities.query.get(activity_id)
        if a:
            db.session.delete(a)
        db.session.commit()


# ===========================================================================
# 1. GET /api/chatbot/activity/<id>/context
# ===========================================================================

class TestChatbotContext:

    def test_get_context_valid_activity_returns_200(self, auth_client, ids):
        """GET context sur activité valide → 200 avec tous les champs attendus."""
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["name"] == "Activité Test"
        assert "tasks" in data
        assert "incoming" in data
        assert "outgoing" in data
        assert "available_tools" in data

    def test_get_context_invalid_activity_returns_404(self, auth_client):
        """GET context sur activité inexistante → 404."""
        r = auth_client.get("/api/chatbot/activity/999999/context")
        assert r.status_code == 404
        data = json.loads(r.data)
        assert "error" in data

    def test_get_context_contains_seeded_task(self, auth_client, ids):
        """Le contexte inclut la tâche créée au seed."""
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert any(t["name"] == "Tâche Test" for t in data["tasks"])

    def test_get_context_available_tools_is_list(self, auth_client, ids):
        """available_tools est une liste (vide ou non)."""
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        assert r.status_code == 200
        assert isinstance(json.loads(r.data)["available_tools"], list)

    def test_get_context_optional_fields_present(self, auth_client, ids):
        """Champs optionnels présents même vides : contraintes, savoirs, aptitudes, etc."""
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        assert r.status_code == 200
        data = json.loads(r.data)
        for field in ("contraintes", "competences", "savoirs", "savoir_faires", "hsc", "aptitudes"):
            assert field in data
            assert isinstance(data[field], list)

    def test_get_context_description_present(self, auth_client, ids):
        """Le contexte contient la description de l'activité."""
        r = auth_client.get(f"/api/chatbot/activity/{ids['activity_id']}/context")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "description" in data

    def test_get_context_resolves_incoming_links_from_data_and_activity(self, auth_client, app, ids):
        """Connexions entrantes : résolution du nom/source/type, données trouvées ou absentes."""
        aid = _create_activity(app, ids["entity_id"], "Activité Chatbot Incoming")
        other_aid = _create_activity(app, ids["entity_id"], "Activité Chatbot Amont")
        with app.app_context():
            from Code.models.models import Data, Link
            from Code.extensions import db
            data_in = Data(entity_id=ids["entity_id"], name="Donnée Amont Chatbot", type="flux")
            db.session.add(data_in)
            db.session.flush()

            db.session.add(Link(entity_id=ids["entity_id"], source_data_id=data_in.id,
                                 target_activity_id=aid, type="nourrissante"))
            db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=other_aid,
                                 target_activity_id=aid, description="Lien direct",
                                 type="descendante"))
            db.session.add(Link(entity_id=ids["entity_id"], target_activity_id=aid, type=""))
            db.session.commit()
        try:
            r = auth_client.get(f"/api/chatbot/activity/{aid}/context")
            assert r.status_code == 200
            incoming = {i["source_name"]: i for i in r.get_json()["incoming"]}
            assert incoming["Donnée Amont Chatbot"]["data_name"] == "Donnée Amont Chatbot"
            assert incoming["Donnée Amont Chatbot"]["type"] == "flux"
            assert incoming["Activité Chatbot Amont"]["data_name"] == "Lien direct"
            assert incoming["Activité Chatbot Amont"]["type"] == "descendante"
            assert incoming["[Source ?]"]["data_name"] == "[Data inconnue]"
            assert incoming["[Source ?]"]["type"] == "[type ?]"
        finally:
            _delete_activity(app, aid)
            _delete_activity(app, other_aid)

    def test_get_context_resolves_outgoing_links_to_data_and_activity(self, auth_client, app, ids):
        """Connexions sortantes : résolution de la cible (activité/donnée/absente) et performance liée."""
        aid = _create_activity(app, ids["entity_id"], "Activité Chatbot Outgoing")
        other_aid = _create_activity(app, ids["entity_id"], "Activité Chatbot Aval")
        with app.app_context():
            from Code.models.models import Data, Link, Performance
            from Code.extensions import db
            data_out = Data(entity_id=ids["entity_id"], name="Donnée Aval Chatbot", type="flux")
            db.session.add(data_out)
            db.session.flush()

            link_with_perf = Link(entity_id=ids["entity_id"], source_activity_id=aid,
                                   target_data_id=data_out.id, type="descendante")
            db.session.add(link_with_perf)
            db.session.flush()
            db.session.add(Performance(name="Perf Chatbot Test", link_id=link_with_perf.id))

            db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=aid,
                                 target_activity_id=other_aid, description="Lien vers aval",
                                 type="descendante"))
            db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=aid, type=""))
            db.session.commit()
        try:
            r = auth_client.get(f"/api/chatbot/activity/{aid}/context")
            assert r.status_code == 200
            outgoing = {o["target_name"]: o for o in r.get_json()["outgoing"]}
            assert outgoing["Donnée Aval Chatbot"]["data_name"] == "Donnée Aval Chatbot"
            assert outgoing["Donnée Aval Chatbot"]["performance"] == {"name": "Perf Chatbot Test"}
            assert outgoing["Activité Chatbot Aval"]["data_name"] == "Lien vers aval"
            assert outgoing["[Cible ?]"]["data_name"] == "[Data inconnue]"
        finally:
            _delete_activity(app, aid)
            _delete_activity(app, other_aid)


# ===========================================================================
# 2. POST /api/chatbot/inject
# ===========================================================================

class TestChatbotInject:

    def test_inject_no_activity_id_returns_400(self, auth_client):
        """POST inject sans activity_id → 400."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({"tasks": [{"label": "Tâche A", "tools": []}]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_inject_invalid_activity_returns_404(self, auth_client):
        """activity_id inexistant → 404."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({"activity_id": 999999, "tasks": [{"label": "X", "tools": []}]}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_inject_empty_tasks_returns_201_count_zero(self, auth_client, ids):
        """tasks=[] → 201, count=0, created=[]."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({"activity_id": ids["activity_id"], "tasks": []}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["count"] == 0
        assert data["created"] == []

    def test_inject_task_without_label_skipped(self, auth_client, ids):
        """Tâche avec label vide est ignorée → count=0."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{"label": "", "tools": []}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["count"] == 0

    def test_inject_whitespace_label_skipped(self, auth_client, ids):
        """Label composé uniquement d'espaces → ignoré."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{"label": "   ", "tools": []}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["count"] == 0

    def test_inject_valid_task_creates_it(self, auth_client, ids, app):
        """Tâche valide → 201 avec count=1 et name correct."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{"label": "Tâche Chatbot Créée", "tools": []}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["count"] == 1
        assert data["created"][0]["name"] == "Tâche Chatbot Créée"
        _cleanup_task(app, "Tâche Chatbot Créée", ids["activity_id"])

    def test_inject_response_contains_task_id(self, auth_client, ids, app):
        """Chaque tâche créée a un id non-nul dans la réponse."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{"label": "Tâche Chatbot ID Test", "tools": []}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data["created"][0]
        assert data["created"][0]["id"] is not None
        _cleanup_task(app, "Tâche Chatbot ID Test", ids["activity_id"])

    def test_inject_multiple_tasks_creates_all(self, auth_client, ids, app):
        """Plusieurs tâches valides → toutes créées (count = nombre envoyé)."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [
                    {"label": "Tâche Chatbot Multi 1", "tools": []},
                    {"label": "Tâche Chatbot Multi 2", "tools": []},
                ],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["count"] == 2
        _cleanup_task(app, "Tâche Chatbot Multi 1", ids["activity_id"])
        _cleanup_task(app, "Tâche Chatbot Multi 2", ids["activity_id"])

    def test_inject_task_with_new_tool_creates_tool(self, auth_client, ids, app):
        """Outil inconnu dans tools → outil créé automatiquement."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{"label": "Tâche Chatbot Outil", "tools": ["Outil Chatbot Créé"]}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        with app.app_context():
            from Code.models.models import Tool
            tool = Tool.query.filter_by(name="Outil Chatbot Créé", entity_id=ids["entity_id"]).first()
            assert tool is not None
            from Code.extensions import db
            db.session.delete(tool)
            db.session.commit()
        _cleanup_task(app, "Tâche Chatbot Outil", ids["activity_id"])

    def test_inject_task_with_outgoing_link_creates_data_and_link(self, auth_client, ids, app):
        """outgoing_link avec data_name → Data et Link créés en base."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{
                    "label": "Tâche Chatbot Lien Test",
                    "tools": [],
                    "outgoing_link": {
                        "data_name": "Donnée Chatbot Lien Test",
                        "data_type": "nourrissante",
                        "target_activity_name": "",
                    },
                }],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        with app.app_context():
            from Code.models.models import Data, Link
            from Code.extensions import db
            d = Data.query.filter_by(name="Donnée Chatbot Lien Test", entity_id=ids["entity_id"]).first()
            assert d is not None
            lnk = Link.query.filter_by(source_data_id=d.id, source_activity_id=ids["activity_id"]).first()
            assert lnk is not None
            db.session.delete(lnk)
            db.session.delete(d)
            db.session.commit()
        _cleanup_task(app, "Tâche Chatbot Lien Test", ids["activity_id"])

    def test_inject_outgoing_link_not_duplicated(self, auth_client, ids, app):
        """Appel double avec le même outgoing_link ne crée pas de lien en double."""
        payload = json.dumps({
            "activity_id": ids["activity_id"],
            "tasks": [{
                "label": "Tâche Lien Doublon Chatbot",
                "tools": [],
                "outgoing_link": {
                    "data_name": "Donnée Doublon Chatbot",
                    "data_type": "nourrissante",
                    "target_activity_name": "",
                },
            }],
        })
        auth_client.post("/api/chatbot/inject", data=payload, content_type="application/json")
        r2 = auth_client.post("/api/chatbot/inject", data=payload, content_type="application/json")
        assert r2.status_code == 201
        with app.app_context():
            from Code.models.models import Data, Link
            from Code.extensions import db
            d = Data.query.filter_by(name="Donnée Doublon Chatbot", entity_id=ids["entity_id"]).first()
            if d:
                links = Link.query.filter_by(source_data_id=d.id, source_activity_id=ids["activity_id"]).all()
                assert len(links) == 1
                for lnk in links:
                    db.session.delete(lnk)
                db.session.delete(d)
                db.session.commit()
        with app.app_context():
            from Code.models.models import Task
            from Code.extensions import db
            for t in Task.query.filter_by(name="Tâche Lien Doublon Chatbot", activity_id=ids["activity_id"]).all():
                db.session.delete(t)
            db.session.commit()


# ===========================================================================
# 3. POST /api/chatbot/chat
# ===========================================================================

class TestChatbotChat:

    def test_chat_empty_message_returns_400(self, auth_client):
        """message vide après strip → 400."""
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({"activity": {}, "history": [], "message": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_chat_whitespace_message_returns_400(self, auth_client):
        """message composé d'espaces → 400."""
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({"activity": {}, "history": [], "message": "   "}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_chat_missing_message_field_returns_400(self, auth_client):
        """Champ message absent → 400 (None → strip → vide)."""
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({"activity": {}, "history": []}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_chat_with_message_returns_200_or_500(self, auth_client):
        """Message valide → 200 si OpenAI dispo, 503 clé absente, 500 erreur API."""
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({
                "activity": {"name": "Test", "description": "Activité de test"},
                "history": [],
                "message": "Bonjour, je veux définir les tâches.",
                "mode": "creer",
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 500, 503)

    def test_chat_mode_ameliorer_accepted(self, auth_client):
        """mode='ameliorer' accepté → 200/503/500 selon la disponibilité IA."""
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({
                "activity": {"name": "Test", "tasks": []},
                "history": [],
                "message": "Analyse mes tâches existantes.",
                "mode": "ameliorer",
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 500, 503)

    def test_chat_error_response_has_error_key(self, auth_client):
        """En cas d'erreur OpenAI, la réponse JSON contient le champ 'error'."""
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({
                "activity": {},
                "history": [],
                "message": "Test message pour OpenAI",
            }),
            content_type="application/json",
        )
        if r.status_code == 500:
            data = json.loads(r.data)
            assert "error" in data

    def test_chat_rich_activity_exercises_context_formatting(self, auth_client):
        """Une activité complètement renseignée doit être formatée sans erreur avant l'appel IA."""
        rich_activity = {
            "name": "Activité Riche",
            "description": "Description riche",
            "tasks": [{"name": "Tâche A", "tools": ["Outil A", "Outil B"]}],
            "incoming": [{"type": "nourrissante", "data_name": "Donnée In", "source_name": "Amont"}],
            "outgoing": [{"data_name": "Donnée Out", "target_name": "Aval",
                          "performance": {"name": "Perf X"}}],
            "contraintes": ["Contrainte A"],
            "competences": ["Compétence A"],
            "savoirs": ["Savoir A"],
            "savoir_faires": ["Savoir-faire A"],
            "hsc": [{"habilete": "Rigueur", "niveau": 3, "justification": "Précision requise"}],
            "aptitudes": ["Aptitude A"],
            "available_tools": ["Outil A", "Outil B", "Outil C"],
        }
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({"activity": rich_activity, "history": [], "message": "Bonjour"}),
            content_type="application/json",
        )
        assert r.status_code in (200, 500, 503)

    def test_chat_prompts_unavailable_returns_503(self, auth_client, monkeypatch):
        """Si les prompts système ne sont pas chargés sur l'instance → 503 explicite (pas de 500)."""
        monkeypatch.setattr("Code.routes.chatbot.get_prompt", lambda key: None)
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({"activity": {}, "history": [], "message": "Bonjour"}),
            content_type="application/json",
        )
        assert r.status_code == 503
        assert "error" in r.get_json()

    def test_chat_ai_success_returns_parsed_json_result(self, auth_client, monkeypatch):
        """Clé IA + client mockés → la réponse JSON du modèle est renvoyée telle quelle."""
        class _FakeMessage:
            content = json.dumps({"reply": "Voici votre réponse", "tasks": []})

        class _FakeChoice:
            message = _FakeMessage()

        class _FakeCompletion:
            choices = [_FakeChoice()]

        class _FakeChatCompletions:
            def create(self, **kwargs):
                return _FakeCompletion()

        class _FakeChat:
            completions = _FakeChatCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr("Code.routes.chatbot.get_openai_key", lambda: "fake-key")
        monkeypatch.setattr("Code.ai_client.make_ai_client", lambda: (_FakeClient(), "fake-model", None))
        r = auth_client.post(
            "/api/chatbot/chat",
            data=json.dumps({
                "activity": {"name": "Test"},
                "history": [{"role": "user", "content": "précédent"}],
                "message": "Bonjour",
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json() == {"reply": "Voici votre réponse", "tasks": []}

    def test_chat_ai_exception_returns_500_with_french_error(self, auth_client, monkeypatch):
        """Le client IA lève une exception → 500 avec message d'erreur en français par défaut."""
        class _FakeChatCompletions:
            def create(self, **kwargs):
                raise RuntimeError("panne-ia")

        class _FakeChat:
            completions = _FakeChatCompletions()

        class _FakeClient:
            chat = _FakeChat()

        monkeypatch.setattr("Code.routes.chatbot.get_openai_key", lambda: "fake-key")
        monkeypatch.setattr("Code.ai_client.make_ai_client", lambda: (_FakeClient(), "fake-model", None))
        with auth_client.session_transaction() as sess:
            sess["lang"] = "fr"
        try:
            r = auth_client.post(
                "/api/chatbot/chat",
                data=json.dumps({"activity": {"name": "Test"}, "history": [], "message": "Bonjour"}),
                content_type="application/json",
            )
            assert r.status_code == 500
            assert "panne-ia" in r.get_json()["error"]
            assert "Erreur API OpenAI" in r.get_json()["error"]
        finally:
            with auth_client.session_transaction() as sess:
                sess["lang"] = "en"


class TestChatbotInjectEdgeCases:

    def test_inject_blank_tool_name_is_skipped(self, auth_client, ids, app):
        """Un nom d'outil vide/espaces dans la liste est ignoré (pas d'outil créé)."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{"label": "Tâche Chatbot Outil Vide", "tools": ["   ", ""]}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        with app.app_context():
            from Code.models.models import Task
            t = Task.query.filter_by(name="Tâche Chatbot Outil Vide", activity_id=ids["activity_id"]).first()
            assert t is not None
            assert t.tools == []
        _cleanup_task(app, "Tâche Chatbot Outil Vide", ids["activity_id"])

    def test_inject_outgoing_link_resolves_existing_target_activity(self, auth_client, ids, app):
        """target_activity_name correspondant à une activité existante → target_activity_id résolu."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{
                    "label": "Tâche Chatbot Cible Résolue",
                    "tools": [],
                    "outgoing_link": {
                        "data_name": "Donnée Chatbot Cible Résolue",
                        "data_type": "nourrissante",
                        "target_activity_name": "activité test",
                    },
                }],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        with app.app_context():
            from Code.models.models import Data, Link
            from Code.extensions import db
            d = Data.query.filter_by(name="Donnée Chatbot Cible Résolue", entity_id=ids["entity_id"]).first()
            assert d is not None
            lnk = Link.query.filter_by(source_data_id=d.id, source_activity_id=ids["activity_id"]).first()
            assert lnk is not None
            assert lnk.target_activity_id == ids["activity_id"]
            db.session.delete(lnk)
            db.session.delete(d)
            db.session.commit()
        _cleanup_task(app, "Tâche Chatbot Cible Résolue", ids["activity_id"])

    def test_inject_exception_rolls_back_and_returns_500(self, auth_client, ids, monkeypatch):
        """Une exception pendant le traitement → rollback + 500 avec message d'erreur."""
        def _boom(**kwargs):
            raise RuntimeError("boom-inject")

        monkeypatch.setattr("Code.routes.chatbot.Task", _boom)
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{"label": "Tâche Qui Explose", "tools": []}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 500
        assert "boom-inject" in r.get_json()["error"]
