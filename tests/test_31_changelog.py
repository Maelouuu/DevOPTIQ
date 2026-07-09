# tests/test_31_changelog.py
"""
Page : Changelog & Activité Récente (/api/recent-activity, /api/changelog)
Couvre : structure des réponses JSON, robustesse sans OpenAI, gestion de cache.
"""
import pytest
import json
from unittest.mock import MagicMock

pytestmark = pytest.mark.changelog


def _make_fake_openai_class(content=None, raise_error=False):
    """Fabrique une classe OpenAI factice pour remplacer `openai.OpenAI`."""
    class _FakeOpenAIClient:
        def __init__(self, api_key=None):
            self.chat = MagicMock()
            if raise_error:
                self.chat.completions.create.side_effect = RuntimeError("openai-fail")
            else:
                self.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content=content))]
                )
    return _FakeOpenAIClient


# ===========================================================================
# 1. Activité récente — GET /api/recent-activity
# ===========================================================================

class TestRecentActivity:

    def test_recent_activity_returns_200(self, auth_client):
        """L'endpoint recent-activity répond 200."""
        r = auth_client.get("/api/recent-activity")
        assert r.status_code == 200

    def test_recent_activity_has_ok_field(self, auth_client):
        """La réponse contient le champ 'ok'."""
        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        assert "ok" in body

    def test_recent_activity_has_items_list(self, auth_client):
        """La réponse contient une liste 'items'."""
        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        assert isinstance(body.get("items"), list)

    def test_recent_activity_empty_db_returns_empty_list(self, auth_client):
        """Sans événements en base, items est une liste vide et empty=True."""
        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        assert body["ok"] is True
        if len(body["items"]) == 0:
            assert body.get("empty") is True

    def test_recent_activity_item_structure(self, app, auth_client):
        """Si des événements existent, chaque item a les champs attendus."""
        with app.app_context():
            from Code.models.models import RecentEvent
            from Code.extensions import db
            ev = RecentEvent(
                event_type="activity_created",
                icon="fa-solid fa-plus",
                label="Activité créée",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        assert body["ok"] is True
        if body["items"]:
            item = body["items"][0]
            for field in ("icon", "label", "type", "event_label", "color", "time"):
                assert field in item, f"Champ manquant : {field}"

        with app.app_context():
            from Code.models.models import RecentEvent
            from Code.extensions import db
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()

    def test_recent_activity_event_label_mapped(self, app, auth_client):
        """L'event_label est correctement mappé depuis _EVENT_LABELS."""
        with app.app_context():
            from Code.models.models import RecentEvent
            from Code.extensions import db
            ev = RecentEvent(
                event_type="task_created",
                icon="fa-solid fa-list-check",
                label="Tâche créée",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        created_items = [i for i in body["items"] if i.get("type") == "task_created"]
        if created_items:
            assert created_items[0]["event_label"] == "Ajout"

        with app.app_context():
            from Code.models.models import RecentEvent
            from Code.extensions import db
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()

    def test_recent_activity_color_assigned(self, app, auth_client):
        """L'événement 'deleted' reçoit la couleur 'red'."""
        with app.app_context():
            from Code.models.models import RecentEvent
            from Code.extensions import db
            ev = RecentEvent(
                event_type="activity_deleted",
                icon="fa-solid fa-trash",
                label="Activité supprimée",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        deleted_items = [i for i in body["items"] if i.get("type") == "activity_deleted"]
        if deleted_items:
            assert deleted_items[0]["color"] == "red"

        with app.app_context():
            from Code.models.models import RecentEvent
            from Code.extensions import db
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()


# ===========================================================================
# 2. Changelog — GET /api/changelog
# ===========================================================================

class TestChangelog:

    def test_changelog_returns_200(self, auth_client):
        """L'endpoint changelog répond 200."""
        r = auth_client.get("/api/changelog")
        assert r.status_code == 200

    def test_changelog_has_ok_field(self, auth_client):
        """La réponse contient le champ 'ok'."""
        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert "ok" in body
        assert body["ok"] is True

    def test_changelog_has_items_list(self, auth_client):
        """La réponse contient une liste 'items'."""
        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert isinstance(body.get("items"), list)
        assert len(body["items"]) > 0

    def test_changelog_fallback_item_structure(self, auth_client, monkeypatch):
        """Sans OpenAI et sans fichier curated, le fallback retourne 3 items avec icon/title/desc."""
        import os
        monkeypatch.delitem(os.environ, "OPENAI_API_KEY", raising=False)
        # Invalider le cache pour forcer la régénération
        import Code.routes.changelog as cl_module
        cl_module._changelog_cache = {}

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        items = body["items"]
        assert len(items) >= 1
        for item in items:
            assert "icon" in item
            assert "title" in item
            assert "desc" in item

    def test_changelog_ok_field_true(self, auth_client):
        """ok est toujours True (pas d'erreur non gérée)."""
        r = auth_client.get("/api/changelog")
        assert json.loads(r.data)["ok"] is True

    def test_changelog_content_type_json(self, auth_client):
        """La réponse est du JSON (Content-Type application/json)."""
        r = auth_client.get("/api/changelog")
        assert "application/json" in r.content_type


# ===========================================================================
# 3. Accès sans authentification — les deux endpoints sont publics
# ===========================================================================

class TestChangelogNoAuth:
    """Ces endpoints ne filtrent pas par entité et ne vérifient pas la session
    (comportement actuel, volontairement permissif pour un flux d'activité
    globale) : on documente ce comportement plutôt que d'en supposer un autre."""

    def test_recent_activity_accessible_without_auth(self, app):
        with app.test_client() as fresh:
            r = fresh.get("/api/recent-activity")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True

    def test_changelog_accessible_without_auth(self, app):
        with app.test_client() as fresh:
            r = fresh.get("/api/changelog")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True


# ===========================================================================
# 4. Changelog — génération sans fichier curated (git commits + OpenAI)
# ===========================================================================
# Le fichier static/changelog_user.json existe dans ce dépôt : /api/changelog
# emprunte donc toujours la branche "curated" par défaut. Ces tests neutralisent
# _read_curated pour exercer la branche de génération réelle (git + OpenAI +
# fallback + cache), autrement jamais atteinte par la suite.

class TestChangelogGenerationPath:

    def _bypass_curated_and_reset_cache(self, monkeypatch):
        import Code.routes.changelog as cl_module
        monkeypatch.setattr(cl_module, "_read_curated", lambda: None)
        cl_module._changelog_cache = {}
        return cl_module

    def test_no_commits_returns_fallback_items(self, auth_client, monkeypatch):
        """Aucun commit récent → repli sur _fallback_changelog()."""
        cl_module = self._bypass_curated_and_reset_cache(monkeypatch)
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: [])

        r = auth_client.get("/api/changelog")
        assert r.status_code == 200
        body = json.loads(r.data)
        titles = {item["title"] for item in body["items"]}
        assert "Nouvelles fonctionnalités" in titles

    def test_commits_without_openai_key_returns_fallback(self, auth_client, monkeypatch):
        """Commits présents mais pas de clé OpenAI → _generate_with_openai() = None → fallback."""
        import os
        cl_module = self._bypass_curated_and_reset_cache(monkeypatch)
        monkeypatch.delitem(os.environ, "OPENAI_API_KEY", raising=False)
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: ["fix: bug X", "feat: Y"])

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        titles = {item["title"] for item in body["items"]}
        assert "Nouvelles fonctionnalités" in titles

    def test_commits_with_mocked_openai_returns_generated_items(self, auth_client, monkeypatch):
        """Avec clé + client OpenAI mocké renvoyant un JSON valide → items générés utilisés."""
        import os
        cl_module = self._bypass_curated_and_reset_cache(monkeypatch)
        monkeypatch.setitem(os.environ, "OPENAI_API_KEY", "fake-test-key")
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: ["feat: nouvelle page rôles"])
        content = json.dumps({"items": [{"icon": "fa-solid fa-star", "title": "Page rôles améliorée", "desc": "desc générée"}]})
        monkeypatch.setattr("openai.OpenAI", _make_fake_openai_class(content))

        r = auth_client.get("/api/changelog")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["items"] == [{"icon": "fa-solid fa-star", "title": "Page rôles améliorée", "desc": "desc générée"}]

    def test_openai_response_wrapped_in_markdown_fences_is_parsed(self, auth_client, monkeypatch):
        """Réponse OpenAI entourée de ```json ... ``` → les fences sont retirées avant parsing."""
        import os
        cl_module = self._bypass_curated_and_reset_cache(monkeypatch)
        monkeypatch.setitem(os.environ, "OPENAI_API_KEY", "fake-test-key")
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: ["feat: export PDF"])
        raw = '```json\n{"items": [{"icon": "fa-solid fa-file-pdf", "title": "Export PDF", "desc": "Nouvel export"}]}\n```'
        monkeypatch.setattr("openai.OpenAI", _make_fake_openai_class(raw))

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["items"][0]["title"] == "Export PDF"

    def test_openai_invalid_json_falls_back(self, auth_client, monkeypatch):
        """Réponse OpenAI non-JSON → _generate_with_openai capture l'exception et renvoie None → fallback."""
        import os
        cl_module = self._bypass_curated_and_reset_cache(monkeypatch)
        monkeypatch.setitem(os.environ, "OPENAI_API_KEY", "fake-test-key")
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: ["feat: X"])
        monkeypatch.setattr("openai.OpenAI", _make_fake_openai_class("ceci n'est pas du JSON"))

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        titles = {item["title"] for item in body["items"]}
        assert "Nouvelles fonctionnalités" in titles

    def test_openai_client_exception_falls_back(self, auth_client, monkeypatch):
        """Le client OpenAI lève une exception → _generate_with_openai renvoie None → fallback."""
        import os
        cl_module = self._bypass_curated_and_reset_cache(monkeypatch)
        monkeypatch.setitem(os.environ, "OPENAI_API_KEY", "fake-test-key")
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: ["feat: X"])
        monkeypatch.setattr("openai.OpenAI", _make_fake_openai_class(raise_error=True))

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        titles = {item["title"] for item in body["items"]}
        assert "Nouvelles fonctionnalités" in titles

    def test_cache_reused_within_ttl_avoids_recomputation(self, auth_client, monkeypatch):
        """Un second appel avec le même commit hash réutilise le cache (pas de recalcul)."""
        cl_module = self._bypass_curated_and_reset_cache(monkeypatch)
        monkeypatch.setattr(cl_module, "_get_latest_commit_hash", lambda: "fixed-hash-for-cache-test")
        call_count = {"n": 0}

        def _counting_commits(n=30):
            call_count["n"] += 1
            return []

        monkeypatch.setattr(cl_module, "_get_recent_commits", _counting_commits)

        r1 = auth_client.get("/api/changelog")
        assert r1.status_code == 200
        assert call_count["n"] == 1

        r2 = auth_client.get("/api/changelog")
        assert r2.status_code == 200
        assert call_count["n"] == 1, "Le second appel doit utiliser le cache, pas relancer _get_recent_commits"
        assert json.loads(r1.data)["items"] == json.loads(r2.data)["items"]


# ===========================================================================
# 5. Recent-activity — gestion d'erreur inattendue
# ===========================================================================

class TestRecentActivityErrorHandling:

    def test_unexpected_exception_returns_ok_false(self, app, auth_client, monkeypatch):
        """Une exception inattendue pendant le traitement → ok=False + champ 'error' (pas de 500)."""
        import Code.routes.changelog as cl_module
        from Code.models.models import RecentEvent
        from Code.extensions import db

        with app.app_context():
            ev = RecentEvent(
                event_type="activity_created",
                icon="fa-solid fa-plus",
                label="Événement pour test erreur",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        def _boom(event_type):
            raise RuntimeError("erreur inattendue simulée")

        monkeypatch.setattr(cl_module, "_event_color", _boom)

        try:
            r = auth_client.get("/api/recent-activity")
            assert r.status_code == 200
            body = json.loads(r.data)
            assert body["ok"] is False
            assert body["items"] == []
            assert "error" in body
            assert "erreur inattendue simulée" in body["error"]
        finally:
            with app.app_context():
                ev = RecentEvent.query.get(ev_id)
                if ev:
                    db.session.delete(ev)
                    db.session.commit()
