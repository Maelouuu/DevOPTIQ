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

    def test_inject_outgoing_link_with_matching_target_activity_sets_target_id(self, auth_client, ids, app):
        """target_activity_name correspondant à une activité existante → le Link
        créé a bien target_activity_id renseigné (résolution par nom, insensible
        à la casse)."""
        with app.app_context():
            from Code.models.models import Activities
            from Code.extensions import db
            target = Activities(entity_id=ids["entity_id"], name="Activité Cible Chatbot Lien", description="")
            db.session.add(target)
            db.session.commit()
            target_id = target.id

        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{
                    "label": "Tâche Chatbot Lien Cible Trouvée",
                    "tools": [],
                    "outgoing_link": {
                        "data_name": "Donnée Chatbot Lien Cible Trouvée",
                        "data_type": "nourrissante",
                        "target_activity_name": "activité cible chatbot lien",
                    },
                }],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        try:
            with app.app_context():
                from Code.models.models import Data, Link
                d = Data.query.filter_by(name="Donnée Chatbot Lien Cible Trouvée", entity_id=ids["entity_id"]).first()
                assert d is not None
                lnk = Link.query.filter_by(source_data_id=d.id, source_activity_id=ids["activity_id"]).first()
                assert lnk is not None
                assert lnk.target_activity_id == target_id
        finally:
            with app.app_context():
                from Code.models.models import Data, Link, Task, Activities
                from Code.extensions import db
                Link.query.filter_by(source_activity_id=ids["activity_id"], target_activity_id=target_id).delete()
                Data.query.filter_by(name="Donnée Chatbot Lien Cible Trouvée", entity_id=ids["entity_id"]).delete()
                Task.query.filter_by(name="Tâche Chatbot Lien Cible Trouvée", activity_id=ids["activity_id"]).delete()
                Activities.query.filter_by(id=target_id).delete()
                db.session.commit()

    def test_inject_outgoing_link_with_unknown_target_activity_leaves_target_id_none(self, auth_client, ids, app):
        """target_activity_name qui ne correspond à aucune activité → le Link est
        créé quand même, mais target_activity_id reste None (pas d'erreur)."""
        r = auth_client.post(
            "/api/chatbot/inject",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "tasks": [{
                    "label": "Tâche Chatbot Lien Cible Inconnue",
                    "tools": [],
                    "outgoing_link": {
                        "data_name": "Donnée Chatbot Lien Cible Inconnue",
                        "data_type": "nourrissante",
                        "target_activity_name": "Activité Qui N'Existe Pas Du Tout",
                    },
                }],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        try:
            with app.app_context():
                from Code.models.models import Data, Link
                d = Data.query.filter_by(name="Donnée Chatbot Lien Cible Inconnue", entity_id=ids["entity_id"]).first()
                assert d is not None
                lnk = Link.query.filter_by(source_data_id=d.id, source_activity_id=ids["activity_id"]).first()
                assert lnk is not None
                assert lnk.target_activity_id is None
        finally:
            with app.app_context():
                from Code.models.models import Data, Link, Task
                from Code.extensions import db
                Link.query.filter_by(source_activity_id=ids["activity_id"]).filter(
                    Link.description == "Donnée Chatbot Lien Cible Inconnue"
                ).delete()
                Data.query.filter_by(name="Donnée Chatbot Lien Cible Inconnue", entity_id=ids["entity_id"]).delete()
                Task.query.filter_by(name="Tâche Chatbot Lien Cible Inconnue", activity_id=ids["activity_id"]).delete()
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
        """Message valide → 200 si OpenAI disponible, 500 sinon (clé absente en test)."""
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
        assert r.status_code in (200, 500)

    def test_chat_mode_ameliorer_accepted(self, auth_client):
        """mode='ameliorer' est accepté et produit 200 ou 500 (OpenAI)."""
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
        assert r.status_code in (200, 500)

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
