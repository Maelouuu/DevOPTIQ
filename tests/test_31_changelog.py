# tests/test_31_changelog.py
"""
Page : Changelog & Activité Récente (/api/recent-activity, /api/changelog)
Couvre : structure des réponses JSON, robustesse sans OpenAI, gestion de cache.
"""
import pytest
import json
from datetime import datetime, timedelta

pytestmark = pytest.mark.changelog


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
# 4. Fonctions internes — branches non atteignables via l'API tant que
#    static/changelog_user.json existe (le chemin "curated" prioritaire
#    court-circuite toujours la génération/le cache/le fallback commit-based).
# ===========================================================================

class TestReadCurated:

    def test_returns_none_when_file_missing(self, app, tmp_path, monkeypatch):
        import Code.routes.changelog as cl_module
        with app.app_context():
            monkeypatch.setattr(cl_module, "_curated_file", lambda: str(tmp_path / "absent.json"))
            assert cl_module._read_curated() is None

    def test_returns_none_on_malformed_json(self, app, tmp_path, monkeypatch):
        import Code.routes.changelog as cl_module
        bad_file = tmp_path / "changelog_user.json"
        bad_file.write_text("{ not valid json", encoding="utf-8")
        with app.app_context():
            monkeypatch.setattr(cl_module, "_curated_file", lambda: str(bad_file))
            assert cl_module._read_curated() is None

    def test_returns_none_when_items_empty(self, app, tmp_path, monkeypatch):
        import Code.routes.changelog as cl_module
        empty_file = tmp_path / "changelog_user.json"
        empty_file.write_text("[]", encoding="utf-8")
        with app.app_context():
            monkeypatch.setattr(cl_module, "_curated_file", lambda: str(empty_file))
            assert cl_module._read_curated() is None

    def test_returns_items_when_valid(self, app, tmp_path, monkeypatch):
        import Code.routes.changelog as cl_module
        valid_file = tmp_path / "changelog_user.json"
        valid_file.write_text(json.dumps([{"icon": "x", "title": "t", "desc": "d"}]), encoding="utf-8")
        with app.app_context():
            monkeypatch.setattr(cl_module, "_curated_file", lambda: str(valid_file))
            result = cl_module._read_curated()
            assert result == {"items": [{"icon": "x", "title": "t", "desc": "d"}]}


class TestGitHelpers:
    """_get_latest_commit_hash / _get_recent_commits — appellent réellement
    git dans le dépôt courant (aucun mock nécessaire pour le chemin nominal)."""

    def test_get_latest_commit_hash_returns_string(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            h = cl_module._get_latest_commit_hash()
        assert isinstance(h, str) and h != ""

    def test_get_latest_commit_hash_unknown_on_exception(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        def _raise(*a, **kw):
            raise OSError("git introuvable")

        with app.app_context():
            monkeypatch.setattr(cl_module.subprocess, "run", _raise)
            assert cl_module._get_latest_commit_hash() == "unknown"

    def test_get_latest_commit_hash_unknown_on_nonzero_returncode(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        class _FakeResult:
            returncode = 1
            stdout = ""

        with app.app_context():
            monkeypatch.setattr(cl_module.subprocess, "run", lambda *a, **kw: _FakeResult())
            assert cl_module._get_latest_commit_hash() == "unknown"

    def test_get_recent_commits_returns_list_of_strings(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            commits = cl_module._get_recent_commits(5)
        assert isinstance(commits, list)
        assert all(isinstance(c, str) for c in commits)

    def test_get_recent_commits_empty_on_exception(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        def _raise(*a, **kw):
            raise OSError("git introuvable")

        with app.app_context():
            monkeypatch.setattr(cl_module.subprocess, "run", _raise)
            assert cl_module._get_recent_commits(5) == []

    def test_get_recent_commits_empty_on_nonzero_returncode(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        class _FakeResult:
            returncode = 1
            stdout = ""

        with app.app_context():
            monkeypatch.setattr(cl_module.subprocess, "run", lambda *a, **kw: _FakeResult())
            assert cl_module._get_recent_commits(5) == []


class TestGenerateWithOpenai:

    def test_returns_none_without_api_key(self, app, monkeypatch):
        import Code.routes.changelog as cl_module
        with app.app_context():
            monkeypatch.setattr(cl_module, "get_openai_key", lambda: None)
            assert cl_module._generate_with_openai(["fix: bug"]) is None

    def test_returns_none_without_system_prompt(self, app, monkeypatch):
        import Code.routes.changelog as cl_module
        with app.app_context():
            monkeypatch.setattr(cl_module, "get_openai_key", lambda: "fake-key")
            monkeypatch.setattr(cl_module, "get_prompt", lambda key: None)
            assert cl_module._generate_with_openai(["fix: bug"]) is None

    def test_success_parses_json_and_strips_code_fence(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        payload = {"items": [{"icon": "fa-solid fa-star", "title": "T", "desc": "D"}]}

        class _FakeMessage:
            content = "```json\n" + json.dumps(payload) + "\n```"

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

        with app.app_context():
            monkeypatch.setattr(cl_module, "get_openai_key", lambda: "fake-key")
            monkeypatch.setattr(cl_module, "get_prompt", lambda key: "system prompt")
            monkeypatch.setattr(
                "Code.ai_client.make_ai_client",
                lambda: (_FakeClient(), "fake-model", None),
            )
            result = cl_module._generate_with_openai(["fix: bug", "feat: new page"])
        assert result == payload

    def test_returns_none_on_client_exception(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        def _raise():
            raise RuntimeError("réseau indisponible")

        with app.app_context():
            monkeypatch.setattr(cl_module, "get_openai_key", lambda: "fake-key")
            monkeypatch.setattr(cl_module, "get_prompt", lambda key: "system prompt")
            monkeypatch.setattr("Code.ai_client.make_ai_client", _raise)
            assert cl_module._generate_with_openai(["fix: bug"]) is None


class TestGetChangelogWithoutCuratedFile:
    """Force le chemin génération (fichier curated absent) : commits réels du
    dépôt, pas de clé OpenAI en environnement de test → repli fallback."""

    def test_falls_back_when_no_curated_and_no_key(self, app, auth_client, tmp_path, monkeypatch):
        import Code.routes.changelog as cl_module
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(tmp_path / "absent.json"))
        monkeypatch.setattr(cl_module, "get_openai_key", lambda: None)
        cl_module._changelog_cache = {}

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        assert len(body["items"]) >= 1
        for item in body["items"]:
            assert "icon" in item and "title" in item and "desc" in item

        cl_module._changelog_cache = {}

    def test_uses_cache_on_second_call_within_ttl(self, app, auth_client, tmp_path, monkeypatch):
        import Code.routes.changelog as cl_module
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(tmp_path / "absent.json"))
        monkeypatch.setattr(cl_module, "get_openai_key", lambda: None)
        cl_module._changelog_cache = {}

        r1 = auth_client.get("/api/changelog")
        cache_after_first = dict(cl_module._changelog_cache)
        assert cache_after_first  # une entrée a été mise en cache

        r2 = auth_client.get("/api/changelog")
        assert json.loads(r1.data)["items"] == json.loads(r2.data)["items"]

        cl_module._changelog_cache = {}


class TestFormatRelativeTime:

    def test_none_returns_empty_string(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            assert cl_module._format_relative_time(None) == ""

    def test_seconds_ago(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            r = cl_module._format_relative_time(datetime.utcnow() - timedelta(seconds=10))
        assert r == "à l'instant"

    def test_minutes_ago(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            r = cl_module._format_relative_time(datetime.utcnow() - timedelta(minutes=5))
        assert r == "il y a 5 min"

    def test_hours_ago(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            r = cl_module._format_relative_time(datetime.utcnow() - timedelta(hours=3))
        assert r == "il y a 3h"

    def test_days_ago(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            r = cl_module._format_relative_time(datetime.utcnow() - timedelta(days=2))
        assert r == "il y a 2j"


class TestFormatDate:

    def test_none_returns_empty_string(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            assert cl_module._format_date(None) == ""

    def test_known_date_formatted(self, app):
        import Code.routes.changelog as cl_module
        dt = datetime(2026, 3, 5, 14, 7)
        with app.app_context():
            r = cl_module._format_date(dt)
        assert r == "5 mars à 14:07"


class TestEventColor:

    def test_unknown_suffix_defaults_gray(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            assert cl_module._event_color("something_unmapped") == "gray"

    def test_known_suffixes(self, app):
        import Code.routes.changelog as cl_module
        with app.app_context():
            assert cl_module._event_color("activity_created") == "green"
            assert cl_module._event_color("activity_updated") == "orange"
            assert cl_module._event_color("activity_deleted") == "red"
            assert cl_module._event_color("tool_linked") == "blue"


class TestRecentActivityDetailAndErrors:

    def test_detail_json_parsed_into_dict(self, app, auth_client):
        from Code.models.models import RecentEvent
        from Code.extensions import db
        with app.app_context():
            ev = RecentEvent(
                event_type="tool_linked",
                icon="fa-solid fa-link",
                label="Outil lié",
                detail=json.dumps({"tool": "Excel"}),
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        matching = [i for i in body["items"] if i.get("type") == "tool_linked"]
        if matching:
            assert matching[0]["detail"] == {"tool": "Excel"}

        with app.app_context():
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()

    def test_detail_malformed_json_is_ignored(self, app, auth_client):
        from Code.models.models import RecentEvent
        from Code.extensions import db
        with app.app_context():
            ev = RecentEvent(
                event_type="tool_updated",
                icon="fa-solid fa-pen",
                label="Outil modifié",
                detail="{ pas du json valide",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        r = auth_client.get("/api/recent-activity")
        assert r.status_code == 200
        body = json.loads(r.data)
        matching = [i for i in body["items"] if i.get("type") == "tool_updated"]
        if matching:
            assert matching[0]["detail"] is None

        with app.app_context():
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()

    def test_user_id_resolved_to_full_name(self, app, auth_client, ids):
        from Code.models.models import RecentEvent
        from Code.extensions import db
        with app.app_context():
            ev = RecentEvent(
                event_type="activity_updated",
                icon="fa-solid fa-pen",
                label="Activité modifiée",
                user_id=ids["user_id"],
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        matching = [i for i in body["items"] if i.get("type") == "activity_updated"]
        if matching:
            assert matching[0]["user"] == "Test User"

        with app.app_context():
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()

    def test_internal_exception_returns_ok_false_with_error(self, app, auth_client, monkeypatch):
        from Code.models.models import RecentEvent
        from Code.extensions import db
        import Code.routes.changelog as cl_module

        with app.app_context():
            ev = RecentEvent(
                event_type="activity_created",
                icon="fa-solid fa-plus",
                label="Activité créée",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        def _boom(*a, **kw):
            raise RuntimeError("panne inattendue")

        monkeypatch.setattr(cl_module, "_format_relative_time", _boom)
        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        assert body["ok"] is False
        assert body["items"] == []
        assert "error" in body

        with app.app_context():
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()
