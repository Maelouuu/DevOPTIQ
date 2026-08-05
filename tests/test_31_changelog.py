# tests/test_31_changelog.py
"""
Page : Changelog & Activité Récente (/api/recent-activity, /api/changelog)
Couvre : structure des réponses JSON, robustesse sans OpenAI, gestion de cache.
"""
import pytest
import json

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

    def test_recent_activity_includes_user_name(self, app, auth_client, ids):
        """Un événement avec user_id renseigné expose le nom complet de l'utilisateur."""
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
        matches = [i for i in body["items"] if i.get("label") == "Activité modifiée"]
        if matches:
            assert matches[0]["user"] == "Test User"

        with app.app_context():
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()

    def test_recent_activity_malformed_detail_json_is_ignored(self, app, auth_client):
        """Un detail JSON invalide ne fait pas planter la route (detail=None en sortie)."""
        from Code.models.models import RecentEvent
        from Code.extensions import db
        with app.app_context():
            ev = RecentEvent(
                event_type="tool_created",
                icon="fa-solid fa-wrench",
                label="Outil créé — detail cassé",
                detail="{not valid json",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        r = auth_client.get("/api/recent-activity")
        assert r.status_code == 200
        body = json.loads(r.data)
        matches = [i for i in body["items"] if i.get("label") == "Outil créé — detail cassé"]
        if matches:
            assert matches[0]["detail"] is None

        with app.app_context():
            ev = RecentEvent.query.get(ev_id)
            if ev:
                db.session.delete(ev)
                db.session.commit()

    def test_recent_activity_query_error_returns_ok_false(self, monkeypatch, auth_client):
        """Une exception inattendue est absorbée et renvoyée sous forme ok=False."""
        from Code.models.models import RecentEvent

        def _boom(*args, **kwargs):
            raise RuntimeError("db down")

        monkeypatch.setattr(RecentEvent, "query", property(_boom))
        r = auth_client.get("/api/recent-activity")
        body = json.loads(r.data)
        assert body["ok"] is False
        assert body["items"] == []
        assert "error" in body

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
        import Code.routes.changelog as cl_module
        monkeypatch.delitem(os.environ, "OPENAI_API_KEY", raising=False)
        # Le fichier curated existe réellement dans le repo (static/changelog_user.json) :
        # il faut le neutraliser pour atteindre effectivement le chemin de fallback.
        monkeypatch.setattr(cl_module, "_curated_file", lambda: "/nonexistent/changelog_user.json")
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: [])
        # Invalider le cache pour forcer la régénération
        cl_module._changelog_cache = {}

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        items = body["items"]
        assert len(items) == 3
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
# 2bis. Fonctions internes — git, cache, fallback, formatage
# ===========================================================================

class TestChangelogInternals:

    def test_get_latest_commit_hash_returns_hash_in_git_repo(self):
        from Code.routes.changelog import _get_latest_commit_hash
        result = _get_latest_commit_hash()
        assert result == "unknown" or len(result) >= 7

    def test_get_recent_commits_returns_list_of_strings(self):
        from Code.routes.changelog import _get_recent_commits
        commits = _get_recent_commits(5)
        assert isinstance(commits, list)
        assert len(commits) <= 5
        assert all(isinstance(c, str) for c in commits)

    def test_get_recent_commits_nonzero_returncode_returns_empty(self, monkeypatch):
        import subprocess
        import Code.routes.changelog as cl_module

        class _FakeResult:
            returncode = 1
            stdout = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _FakeResult())
        assert cl_module._get_recent_commits(5) == []

    def test_get_recent_commits_bad_git_dir_returns_empty(self, monkeypatch):
        import subprocess
        import Code.routes.changelog as cl_module

        def fake_run(*args, **kwargs):
            raise OSError("git not found")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert cl_module._get_recent_commits(5) == []

    def test_get_latest_commit_hash_exception_returns_unknown(self, monkeypatch):
        import subprocess
        import Code.routes.changelog as cl_module

        def fake_run(*args, **kwargs):
            raise OSError("git not found")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert cl_module._get_latest_commit_hash() == "unknown"

    def test_read_curated_missing_file_returns_none(self, monkeypatch):
        import Code.routes.changelog as cl_module
        monkeypatch.setattr(cl_module, "_curated_file", lambda: "/nonexistent/x.json")
        assert cl_module._read_curated() is None

    def test_read_curated_invalid_json_returns_none(self, monkeypatch, tmp_path):
        import Code.routes.changelog as cl_module
        bad_file = tmp_path / "changelog_user.json"
        bad_file.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(bad_file))
        assert cl_module._read_curated() is None

    def test_read_curated_empty_list_returns_none(self, monkeypatch, tmp_path):
        import Code.routes.changelog as cl_module
        empty_file = tmp_path / "changelog_user.json"
        empty_file.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(empty_file))
        assert cl_module._read_curated() is None

    def test_read_curated_valid_list_returns_items(self, monkeypatch, tmp_path):
        import Code.routes.changelog as cl_module
        valid_file = tmp_path / "changelog_user.json"
        valid_file.write_text('[{"icon": "x", "title": "t", "desc": "d"}]', encoding="utf-8")
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(valid_file))
        result = cl_module._read_curated()
        assert result == {"items": [{"icon": "x", "title": "t", "desc": "d"}]}

    def test_fallback_changelog_has_three_items(self):
        from Code.routes.changelog import _fallback_changelog
        data = _fallback_changelog()
        assert len(data["items"]) == 3
        for item in data["items"]:
            assert set(item.keys()) == {"icon", "title", "desc"}

    def test_format_relative_time_none_is_empty(self):
        from Code.routes.changelog import _format_relative_time
        assert _format_relative_time(None) == ""

    def test_format_relative_time_just_now(self):
        from datetime import datetime
        from Code.routes.changelog import _format_relative_time
        assert _format_relative_time(datetime.utcnow()) == "à l'instant"

    def test_format_relative_time_minutes(self):
        from datetime import datetime, timedelta
        from Code.routes.changelog import _format_relative_time
        dt = datetime.utcnow() - timedelta(minutes=5)
        assert _format_relative_time(dt) == "il y a 5 min"

    def test_format_relative_time_hours(self):
        from datetime import datetime, timedelta
        from Code.routes.changelog import _format_relative_time
        dt = datetime.utcnow() - timedelta(hours=3)
        assert _format_relative_time(dt) == "il y a 3h"

    def test_format_relative_time_days(self):
        from datetime import datetime, timedelta
        from Code.routes.changelog import _format_relative_time
        dt = datetime.utcnow() - timedelta(days=2)
        assert _format_relative_time(dt) == "il y a 2j"

    def test_format_date_none_is_empty(self):
        from Code.routes.changelog import _format_date
        assert _format_date(None) == ""

    def test_format_date_formats_month_and_time(self):
        from datetime import datetime
        from Code.routes.changelog import _format_date
        dt = datetime(2026, 3, 15, 9, 5)
        assert _format_date(dt) == "15 mars à 09:05"

    def test_event_color_created_is_green(self):
        from Code.routes.changelog import _event_color
        assert _event_color("activity_created") == "green"

    def test_event_color_updated_is_orange(self):
        from Code.routes.changelog import _event_color
        assert _event_color("task_updated") == "orange"

    def test_event_color_deleted_is_red(self):
        from Code.routes.changelog import _event_color
        assert _event_color("role_deleted") == "red"

    def test_event_color_linked_is_blue(self):
        from Code.routes.changelog import _event_color
        assert _event_color("tool_linked") == "blue"

    def test_event_color_unknown_suffix_is_gray(self):
        from Code.routes.changelog import _event_color
        assert _event_color("something_weird") == "gray"

    def test_generate_with_openai_no_api_key_returns_none(self, app, monkeypatch):
        import Code.routes.changelog as cl_module
        monkeypatch.setattr(cl_module, "get_openai_key", lambda: None)
        with app.app_context():
            assert cl_module._generate_with_openai(["fix: bug"]) is None

    def test_generate_with_openai_no_prompt_returns_none(self, app, monkeypatch):
        import Code.routes.changelog as cl_module
        monkeypatch.setattr(cl_module, "get_openai_key", lambda: "sk-fake")
        monkeypatch.setattr(cl_module, "get_prompt", lambda key: None)
        with app.app_context():
            assert cl_module._generate_with_openai(["fix: bug"]) is None

    def test_generate_with_openai_success_parses_json(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        class _Msg:
            content = '```json\n{"items": [{"icon": "a", "title": "b", "desc": "c"}]}\n```'

        class _Choice:
            message = _Msg()

        class _Response:
            choices = [_Choice()]

        class _Completions:
            def create(self, **kwargs):
                return _Response()

        class _Chat:
            completions = _Completions()

        class _FakeClient:
            chat = _Chat()

        monkeypatch.setattr(cl_module, "get_openai_key", lambda: "sk-fake")
        monkeypatch.setattr(cl_module, "get_prompt", lambda key: "system prompt")
        monkeypatch.setattr("Code.ai_client.make_ai_client", lambda: (_FakeClient(), "gpt-test", None))

        with app.app_context():
            result = cl_module._generate_with_openai(["fix: bug"])
        assert result == {"items": [{"icon": "a", "title": "b", "desc": "c"}]}

    def test_generate_with_openai_client_error_returns_none(self, app, monkeypatch):
        import Code.routes.changelog as cl_module

        def _boom():
            raise RuntimeError("no client")

        monkeypatch.setattr(cl_module, "get_openai_key", lambda: "sk-fake")
        monkeypatch.setattr(cl_module, "get_prompt", lambda key: "system prompt")
        monkeypatch.setattr("Code.ai_client.make_ai_client", _boom)

        with app.app_context():
            assert cl_module._generate_with_openai(["fix: bug"]) is None


# ===========================================================================
# 2ter. Changelog — chemin non-curated : cache et génération
# ===========================================================================

class TestChangelogNonCuratedPath:

    def test_changelog_uses_fresh_cache_within_ttl(self, auth_client, monkeypatch):
        """Un second appel avec le même hash de commit réutilise le cache (pas de régénération)."""
        import Code.routes.changelog as cl_module

        call_count = {"n": 0}

        def fake_generate(commits):
            call_count["n"] += 1
            return {"items": [{"icon": "x", "title": f"gen-{call_count['n']}", "desc": "d"}]}

        monkeypatch.setattr(cl_module, "_curated_file", lambda: "/nonexistent/changelog_user.json")
        monkeypatch.setattr(cl_module, "_get_latest_commit_hash", lambda: "fixed-hash-for-test")
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: ["fix: something"])
        monkeypatch.setattr(cl_module, "_generate_with_openai", fake_generate)
        monkeypatch.setattr(cl_module, "_changelog_cache", {})

        r1 = auth_client.get("/api/changelog")
        r2 = auth_client.get("/api/changelog")
        assert call_count["n"] == 1
        assert json.loads(r1.data)["items"] == json.loads(r2.data)["items"]

    def test_changelog_no_commits_uses_fallback(self, auth_client, monkeypatch):
        import Code.routes.changelog as cl_module

        monkeypatch.setattr(cl_module, "_curated_file", lambda: "/nonexistent/changelog_user.json")
        monkeypatch.setattr(cl_module, "_get_latest_commit_hash", lambda: "hash-no-commits")
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: [])
        monkeypatch.setattr(cl_module, "_changelog_cache", {})

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        assert len(body["items"]) == 3


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
