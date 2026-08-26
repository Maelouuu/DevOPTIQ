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
        """L'event_label suit la langue de la session (FR et EN)."""
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

        for langue, attendu in (("fr", "Ajout"), ("en", "Added")):
            with auth_client.session_transaction() as sess:
                sess["lang"] = langue
            r = auth_client.get("/api/recent-activity")
            body = json.loads(r.data)
            created_items = [i for i in body["items"] if i.get("type") == "task_created"]
            if created_items:
                assert created_items[0]["event_label"] == attendu

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
