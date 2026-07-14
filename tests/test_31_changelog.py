# tests/test_31_changelog.py
"""
Page : Changelog & Activité Récente (/api/recent-activity, /api/changelog)
Couvre : structure des réponses JSON, robustesse sans OpenAI, gestion de cache.
"""
import pytest
import json
from datetime import datetime, timedelta

pytestmark = pytest.mark.changelog


_UNSET = object()


def _make_event(app, event_type="activity_created", icon="fa-solid fa-plus",
                 label="Test", created_at=_UNSET, user_id=None, detail=None):
    """created_at par défaut = l'instant de l'appel (pas figé à l'import du module),
    pour que l'événement reste dans le top 20 des events les plus récents malgré
    les autres événements créés en continu par le reste de la suite."""
    from Code.models.models import RecentEvent
    from Code.extensions import db
    if created_at is _UNSET:
        created_at = datetime.utcnow()
    with app.app_context():
        ev = RecentEvent(
            event_type=event_type, icon=icon, label=label,
            created_at=created_at, user_id=user_id, detail=detail,
        )
        db.session.add(ev)
        db.session.commit()
        return ev.id


def _delete_event(app, ev_id):
    from Code.models.models import RecentEvent
    from Code.extensions import db
    with app.app_context():
        ev = RecentEvent.query.get(ev_id)
        if ev:
            db.session.delete(ev)
            db.session.commit()


def _clear_recent_events(app):
    """Vide la table recent_events : nécessaire car GET /api/recent-activity ne
    renvoie que les 20 événements les plus récents, et le reste de la suite (session
    scope=session) en crée en continu — un événement volontairement daté dans le
    passé (bucket minutes/heures/jours) serait sinon systématiquement évincé."""
    from Code.models.models import RecentEvent
    from Code.extensions import db
    with app.app_context():
        RecentEvent.query.delete()
        db.session.commit()


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
# 4. Formatage temporel, couleurs d'événement, utilisateur et détail JSON
# ===========================================================================

class TestRecentActivityFormatting:

    def test_event_color_gray_for_unknown_suffix(self, app, auth_client):
        """Un event_type sans suffixe connu (created/updated/deleted/linked) → couleur 'gray'."""
        _clear_recent_events(app)
        ev_id = _make_event(app, event_type="custom_other_thing")
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            items = [i for i in body["items"] if i.get("type") == "custom_other_thing"]
            assert items and items[0]["color"] == "gray"
        finally:
            _delete_event(app, ev_id)

    def test_event_label_unmapped_defaults_evenement(self, app, auth_client):
        """Un event_type absent de _EVENT_LABELS → event_label = 'Événement'."""
        _clear_recent_events(app)
        ev_id = _make_event(app, event_type="something_unmapped")
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            items = [i for i in body["items"] if i.get("type") == "something_unmapped"]
            assert items and items[0]["event_label"] == "Événement"
        finally:
            _delete_event(app, ev_id)

    def test_created_at_none_gives_empty_time_and_date(self, app, auth_client):
        """created_at NULL → 'time' et 'date' sont des chaînes vides."""
        _clear_recent_events(app)
        ev_id = _make_event(app, event_type="tool_linked")
        # Le default Python de la colonne s'applique à l'INSERT ; on force la
        # valeur NULL via un UPDATE explicite (pas concerné par ce default).
        from Code.models.models import RecentEvent
        from Code.extensions import db
        with app.app_context():
            ev = RecentEvent.query.get(ev_id)
            ev.created_at = None
            db.session.commit()
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            items = [i for i in body["items"] if i.get("type") == "tool_linked"]
            assert items
            assert items[0]["time"] == ""
            assert items[0]["date"] == ""
            assert items[0]["color"] == "blue"
        finally:
            _delete_event(app, ev_id)

    def test_relative_time_minutes_bucket(self, app, auth_client):
        _clear_recent_events(app)
        ev_id = _make_event(app, created_at=datetime.utcnow() - timedelta(minutes=5))
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            item = next(i for i in body["items"] if i.get("label") == "Test")
            assert "min" in item["time"]
        finally:
            _delete_event(app, ev_id)

    def test_relative_time_hours_bucket(self, app, auth_client):
        _clear_recent_events(app)
        ev_id = _make_event(app, created_at=datetime.utcnow() - timedelta(hours=3))
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            item = next(i for i in body["items"] if i.get("label") == "Test")
            assert item["time"].endswith("h")
        finally:
            _delete_event(app, ev_id)

    def test_relative_time_days_bucket(self, app, auth_client):
        _clear_recent_events(app)
        ev_id = _make_event(app, created_at=datetime.utcnow() - timedelta(days=2))
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            item = next(i for i in body["items"] if i.get("label") == "Test")
            assert item["time"].endswith("j")
        finally:
            _delete_event(app, ev_id)

    def test_user_name_resolved_when_user_exists(self, app, auth_client, ids):
        _clear_recent_events(app)
        ev_id = _make_event(app, event_type="task_updated", user_id=ids["user_id"])
        try:
            with app.app_context():
                from Code.models.models import User
                u = User.query.get(ids["user_id"])
                expected_name = f"{u.first_name} {u.last_name}"
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            items = [i for i in body["items"] if i.get("type") == "task_updated"]
            assert items and items[0]["user"] == expected_name
        finally:
            _delete_event(app, ev_id)

    def test_user_none_when_user_id_unknown(self, app, auth_client):
        _clear_recent_events(app)
        ev_id = _make_event(app, event_type="role_deleted", user_id=999999)
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            items = [i for i in body["items"] if i.get("type") == "role_deleted"]
            assert items and items[0]["user"] is None
        finally:
            _delete_event(app, ev_id)

    def test_detail_valid_json_is_parsed(self, app, auth_client):
        _clear_recent_events(app)
        ev_id = _make_event(app, event_type="tool_created", detail=json.dumps({"before": "x", "after": "y"}))
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            items = [i for i in body["items"] if i.get("type") == "tool_created"]
            assert items and items[0]["detail"] == {"before": "x", "after": "y"}
        finally:
            _delete_event(app, ev_id)

    def test_detail_invalid_json_falls_back_to_none(self, app, auth_client):
        _clear_recent_events(app)
        ev_id = _make_event(app, event_type="tool_updated", detail="not valid json {")
        try:
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            items = [i for i in body["items"] if i.get("type") == "tool_updated"]
            assert items and items[0]["detail"] is None
        finally:
            _delete_event(app, ev_id)

    def test_recent_activity_exception_returns_ok_false(self, auth_client, monkeypatch):
        """Une exception dans la requête DB est absorbée : ok=False + error."""
        from Code.models.models import RecentEvent

        class _RaisingQuery:
            def order_by(self, *a, **k):
                return self

            def limit(self, *a, **k):
                return self

            def all(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(RecentEvent, "query", _RaisingQuery())
        r = auth_client.get("/api/recent-activity")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["ok"] is False
        assert "error" in body
        assert body["items"] == []


# ===========================================================================
# 5. Génération du changelog sans fichier curated (git + OpenAI + cache)
# ===========================================================================

class TestChangelogGeneration:

    def test_no_curated_generates_via_openai_success(self, auth_client, monkeypatch):
        """Sans fichier curated, avec une clé OpenAI mockée : le JSON généré est renvoyé tel quel."""
        import Code.routes.changelog as cl_module
        import openai

        monkeypatch.setattr(cl_module, "_read_curated", lambda: None)
        cl_module._changelog_cache = {}
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-tests")

        fake_content = json.dumps({"items": [
            {"icon": "fa-solid fa-star", "title": "Nouveau", "desc": "Détail de la fonctionnalité"}
        ]})

        class _FakeMsg:
            def __init__(self, content):
                self.content = content

        class _FakeChoice:
            def __init__(self, content):
                self.message = _FakeMsg(content)

        class _FakeResp:
            def __init__(self, content):
                self.choices = [_FakeChoice(content)]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResp(fake_content)

        class _FakeChat:
            def __init__(self):
                self.completions = _FakeCompletions()

        class _FakeOpenAI:
            def __init__(self, api_key=None):
                self.chat = _FakeChat()

        monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        assert body["items"][0]["title"] == "Nouveau"

        cl_module._changelog_cache = {}

    def test_no_curated_openai_exception_falls_back(self, auth_client, monkeypatch):
        """Si l'appel OpenAI lève une exception, le fallback statique est utilisé."""
        import Code.routes.changelog as cl_module
        import openai

        monkeypatch.setattr(cl_module, "_read_curated", lambda: None)
        cl_module._changelog_cache = {}
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-tests")

        class _FakeCompletions:
            def create(self, **kwargs):
                raise RuntimeError("API down")

        class _FakeChat:
            def __init__(self):
                self.completions = _FakeCompletions()

        class _FakeOpenAI:
            def __init__(self, api_key=None):
                self.chat = _FakeChat()

        monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        fallback_titles = {i["title"] for i in cl_module._fallback_changelog()["items"]}
        assert body["items"][0]["title"] in fallback_titles

        cl_module._changelog_cache = {}

    def test_no_curated_no_commits_uses_fallback(self, auth_client, monkeypatch):
        """Sans curated et sans commits récents, le fallback statique est utilisé directement."""
        import Code.routes.changelog as cl_module

        monkeypatch.setattr(cl_module, "_read_curated", lambda: None)
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: [])
        cl_module._changelog_cache = {}

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        fallback_titles = {i["title"] for i in cl_module._fallback_changelog()["items"]}
        assert body["items"][0]["title"] in fallback_titles

        cl_module._changelog_cache = {}

    def test_no_curated_cache_hit_skips_regeneration(self, auth_client, monkeypatch):
        """Un second appel dans l'heure réutilise le cache (pas de nouvel appel commits)."""
        import Code.routes.changelog as cl_module

        monkeypatch.setattr(cl_module, "_read_curated", lambda: None)
        cl_module._changelog_cache = {
            cl_module._get_latest_commit_hash(): {
                "ts": __import__("time").time(),
                "data": {"items": [{"icon": "fa-solid fa-clock", "title": "Depuis cache", "desc": "x"}]},
            }
        }

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        assert body["items"][0]["title"] == "Depuis cache"

        cl_module._changelog_cache = {}

    def test_curated_file_invalid_json_ignored(self, auth_client, monkeypatch, tmp_path):
        """Un fichier curated invalide (JSON cassé) est ignoré, on retombe sur le fallback."""
        import Code.routes.changelog as cl_module

        bad_file = tmp_path / "changelog_user.json"
        bad_file.write_text("not valid json {", encoding="utf-8")
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(bad_file))
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: [])
        cl_module._changelog_cache = {}

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        fallback_titles = {i["title"] for i in cl_module._fallback_changelog()["items"]}
        assert body["items"][0]["title"] in fallback_titles

        cl_module._changelog_cache = {}

    def test_curated_file_empty_list_treated_as_missing(self, auth_client, monkeypatch, tmp_path):
        """Un fichier curated présent mais vide ([]) est traité comme absent."""
        import Code.routes.changelog as cl_module

        empty_file = tmp_path / "changelog_user.json"
        empty_file.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(empty_file))
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: [])
        cl_module._changelog_cache = {}

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        fallback_titles = {i["title"] for i in cl_module._fallback_changelog()["items"]}
        assert body["items"][0]["title"] in fallback_titles

        cl_module._changelog_cache = {}

    def test_curated_file_does_not_exist_returns_none(self, auth_client, monkeypatch, tmp_path):
        """Un chemin de fichier curated inexistant → _read_curated() renvoie None → fallback."""
        import Code.routes.changelog as cl_module

        missing_file = tmp_path / "does_not_exist.json"
        monkeypatch.setattr(cl_module, "_curated_file", lambda: str(missing_file))
        monkeypatch.setattr(cl_module, "_get_recent_commits", lambda n=30: [])
        cl_module._changelog_cache = {}

        r = auth_client.get("/api/changelog")
        body = json.loads(r.data)
        assert body["ok"] is True
        fallback_titles = {i["title"] for i in cl_module._fallback_changelog()["items"]}
        assert body["items"][0]["title"] in fallback_titles

        cl_module._changelog_cache = {}

    def test_generate_with_openai_no_key_returns_none(self):
        """_generate_with_openai() sans clé OPENAI_API_KEY renvoie None directement (pas d'appel réseau)."""
        import Code.routes.changelog as cl_module
        import os

        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            assert cl_module._generate_with_openai(["Un commit"]) is None
        finally:
            if old_key is not None:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_generate_with_openai_strips_markdown_fences(self, monkeypatch):
        """La réponse IA entourée de ```json ... ``` est nettoyée avant le json.loads."""
        import Code.routes.changelog as cl_module
        import openai

        fenced = "```json\n" + json.dumps({"items": [{"icon": "fa-solid fa-star", "title": "T", "desc": "D"}]}) + "\n```"

        class _FakeMsg:
            def __init__(self, content):
                self.content = content

        class _FakeChoice:
            def __init__(self, content):
                self.message = _FakeMsg(content)

        class _FakeResp:
            def __init__(self, content):
                self.choices = [_FakeChoice(content)]

        class _FakeCompletions:
            def create(self, **kwargs):
                return _FakeResp(fenced)

        class _FakeChat:
            def __init__(self):
                self.completions = _FakeCompletions()

        class _FakeOpenAI:
            def __init__(self, api_key=None):
                self.chat = _FakeChat()

        monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-tests")
        monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)

        result = cl_module._generate_with_openai(["Un commit"])
        assert result == {"items": [{"icon": "fa-solid fa-star", "title": "T", "desc": "D"}]}
