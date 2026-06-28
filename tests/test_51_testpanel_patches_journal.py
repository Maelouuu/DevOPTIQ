# tests/test_51_testpanel_patches_journal.py
"""
Routes non couvertes dans test_37 :
  - GET  /testpanel/patches              → page HTML tous les patchs
  - GET  /testpanel/journal              → page HTML carnet de bord
  - POST /testpanel/run/case/<case_id>   → lancer un cas de test spécifique
  - GET  /testpanel/stream/<run_id>      → SSE stream de sortie
"""
import pytest

pytestmark = pytest.mark.testpanel_patches_journal


# ===========================================================================
# 1. GET /testpanel/patches — Page des correctifs tracés
# ===========================================================================

class TestTestPanelPatches:

    def test_patches_returns_200(self, auth_client):
        """GET /testpanel/patches répond 200."""
        r = auth_client.get("/testpanel/patches")
        assert r.status_code == 200

    def test_patches_response_is_html(self, auth_client):
        """La réponse contient du HTML."""
        r = auth_client.get("/testpanel/patches")
        assert b"html" in r.data.lower() or b"<" in r.data

    def test_patches_no_auth_does_not_crash(self, client):
        """Sans auth, /testpanel/patches ne génère pas de 500."""
        r = client.get("/testpanel/patches")
        assert r.status_code in (200, 302, 401, 403)

    def test_patches_page_contains_patch_reference(self, auth_client, app):
        """La page contient un mot-clé attendu des patchs."""
        from Code.models.test_models import TestPatch
        with app.app_context():
            count = TestPatch.query.count()
        r = auth_client.get("/testpanel/patches")
        body = r.data.decode("utf-8", errors="replace").lower()
        assert "patch" in body or "correctif" in body or count == 0

    def test_patches_page_shows_known_patch(self, auth_client, app):
        """Si un patch existe, il apparaît dans la page."""
        from Code.models.test_models import TestPatch
        with app.app_context():
            patch = TestPatch.query.first()
        if patch is None:
            pytest.skip("Aucun patch en DB")
        r = auth_client.get("/testpanel/patches")
        body = r.data.decode("utf-8", errors="replace")
        assert patch.title in body or patch.patch_uid in body

    def test_patches_summary_visible(self, auth_client):
        """La page contient une section résumé (statistiques)."""
        r = auth_client.get("/testpanel/patches")
        body = r.data.decode("utf-8", errors="replace").lower()
        assert any(kw in body for kw in ("total", "bug", "patch", "correctif"))

    def test_patches_page_200_even_empty_db(self, app):
        """La page ne plante pas si la table patches est vide."""
        with app.test_client() as c:
            with c.session_transaction() as sess:
                from Code.models.models import User, Entity
                with app.app_context():
                    u = User.query.filter_by(email="test@devoptiq.com").first()
                    e = Entity.query.filter_by(name="Entité Test").first()
                sess["user_id"] = u.id
                sess["active_entity_id"] = e.id
            r = c.get("/testpanel/patches")
        assert r.status_code == 200


# ===========================================================================
# 2. GET /testpanel/journal — Carnet de bord de la routine
# ===========================================================================

class TestTestPanelJournal:

    def test_journal_returns_200(self, auth_client):
        """GET /testpanel/journal répond 200."""
        r = auth_client.get("/testpanel/journal")
        assert r.status_code == 200

    def test_journal_response_is_html(self, auth_client):
        """La réponse est du HTML."""
        r = auth_client.get("/testpanel/journal")
        assert r.content_type.startswith("text/html")

    def test_journal_no_auth_does_not_crash(self, client):
        """Sans auth, /testpanel/journal ne génère pas de 500."""
        r = client.get("/testpanel/journal")
        assert r.status_code in (200, 302, 401, 403)

    def test_journal_page_has_plan_reference(self, auth_client):
        """La page contient une référence au plan ou au journal."""
        r = auth_client.get("/testpanel/journal")
        body = r.data.decode("utf-8", errors="replace").lower()
        assert any(kw in body for kw in ("plan", "journal", "routine", "étape", "step"))

    def test_journal_page_has_entries_section(self, auth_client):
        """La page contient une section pour les entrées d'historique."""
        r = auth_client.get("/testpanel/journal")
        body = r.data.decode("utf-8", errors="replace").lower()
        assert any(kw in body for kw in ("entries", "run", "exécution", "historique"))

    def test_journal_page_200_with_empty_json(self, app, tmp_path, monkeypatch):
        """La page répond 200 même si journal.json est vide ou invalide."""
        import json as _json
        fake_journal = tmp_path / "journal.json"
        fake_journal.write_text(_json.dumps({"plan": {}, "entries": []}))

        import Code.routes.test_panel as tp
        monkeypatch.setattr(tp, "_JOURNAL_FILE", fake_journal)

        with app.test_client() as c:
            with c.session_transaction() as sess:
                from Code.models.models import User, Entity
                with app.app_context():
                    u = User.query.filter_by(email="test@devoptiq.com").first()
                    e = Entity.query.filter_by(name="Entité Test").first()
                sess["user_id"] = u.id
                sess["active_entity_id"] = e.id
            r = c.get("/testpanel/journal")
        assert r.status_code == 200


# ===========================================================================
# 3. POST /testpanel/run/case/<case_id> — Lancer un cas de test
# ===========================================================================

class TestTestPanelRunCase:

    def test_run_case_unknown_id_not_200(self, auth_client):
        """POST /testpanel/run/case/<id_inexistant> ne retourne pas 200."""
        r = auth_client.post("/testpanel/run/case/999999")
        assert r.status_code != 200

    def test_run_case_known_id_returns_run_id(self, auth_client, app, monkeypatch):
        """POST /testpanel/run/case/<id_connu> retourne un run_id."""
        from Code.models.test_models import TestCase, TestPage
        import Code.routes.test_panel as tp

        monkeypatch.setattr(tp, "_start_run", lambda scope: 9999)

        with app.app_context():
            page = TestPage.query.first()
            if page is None:
                pytest.skip("Aucune TestPage disponible")
            case = TestCase.query.filter_by(page_id=page.id).first()
            if case is None:
                pytest.skip("Aucun TestCase disponible")
            case_id = case.id

        r = auth_client.post(f"/testpanel/run/case/{case_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert "run_id" in data
        assert data["run_id"] == 9999

    def test_run_case_response_is_json(self, auth_client, app, monkeypatch):
        """La réponse de run/case est du JSON."""
        from Code.models.test_models import TestCase, TestPage
        import Code.routes.test_panel as tp

        monkeypatch.setattr(tp, "_start_run", lambda scope: 42)

        with app.app_context():
            page = TestPage.query.first()
            if page is None:
                pytest.skip("Aucune TestPage disponible")
            case = TestCase.query.filter_by(page_id=page.id).first()
            if case is None:
                pytest.skip("Aucun TestCase disponible")
            case_id = case.id

        r = auth_client.post(f"/testpanel/run/case/{case_id}")
        assert r.status_code == 200
        assert r.content_type.startswith("application/json")

    def test_run_case_scope_includes_case_id(self, auth_client, app, monkeypatch):
        """Le scope passé à _start_run contient 'case:<id>'."""
        from Code.models.test_models import TestCase, TestPage
        import Code.routes.test_panel as tp

        captured = {}

        def fake_start(scope):
            captured["scope"] = scope
            return 1

        monkeypatch.setattr(tp, "_start_run", fake_start)

        with app.app_context():
            page = TestPage.query.first()
            if page is None:
                pytest.skip("Aucune TestPage disponible")
            case = TestCase.query.filter_by(page_id=page.id).first()
            if case is None:
                pytest.skip("Aucun TestCase disponible")
            case_id = case.id

        auth_client.post(f"/testpanel/run/case/{case_id}")
        assert captured.get("scope") == f"case:{case_id}"


# ===========================================================================
# 4. GET /testpanel/stream/<run_id> — SSE streaming
# ===========================================================================

class TestTestPanelStream:

    def test_stream_unknown_run_returns_event_stream(self, auth_client, monkeypatch):
        """GET /testpanel/stream/<id> répond avec mimetype text/event-stream."""
        import Code.routes.test_panel as tp
        import threading

        # Injecter un run fictif "done" dans _runs pour éviter de bloquer
        fake_run_id = 88888
        with tp._runs_lock:
            tp._runs[fake_run_id] = {"lines": ["[DONE]"], "done": True}

        r = auth_client.get(f"/testpanel/stream/{fake_run_id}", buffered=True)
        content_type = r.content_type
        assert "text/event-stream" in content_type

        # Nettoyage
        with tp._runs_lock:
            tp._runs.pop(fake_run_id, None)

    def test_stream_returns_done_marker(self, auth_client):
        """Le flux SSE contient la marque [DONE] pour un run terminé."""
        import Code.routes.test_panel as tp

        fake_run_id = 77777
        with tp._runs_lock:
            tp._runs[fake_run_id] = {"lines": ["Test output line"], "done": True}

        r = auth_client.get(f"/testpanel/stream/{fake_run_id}", buffered=True)
        body = r.data.decode("utf-8", errors="replace")
        assert "[DONE]" in body

        with tp._runs_lock:
            tp._runs.pop(fake_run_id, None)

    def test_stream_includes_output_lines(self, auth_client):
        """Le flux SSE contient les lignes de sortie enregistrées."""
        import Code.routes.test_panel as tp

        fake_run_id = 66666
        test_line = "PASSED test_something"
        with tp._runs_lock:
            tp._runs[fake_run_id] = {"lines": [test_line], "done": True}

        r = auth_client.get(f"/testpanel/stream/{fake_run_id}", buffered=True)
        body = r.data.decode("utf-8", errors="replace")
        assert test_line in body

        with tp._runs_lock:
            tp._runs.pop(fake_run_id, None)

    def test_stream_no_auth_does_not_crash(self, client):
        """Sans auth, /testpanel/stream/<id> ne génère pas de 500 inattendu."""
        import Code.routes.test_panel as tp

        fake_run_id = 55555
        with tp._runs_lock:
            tp._runs[fake_run_id] = {"lines": [], "done": True}

        r = client.get(f"/testpanel/stream/{fake_run_id}", buffered=True)
        assert r.status_code in (200, 302, 401, 403)

        with tp._runs_lock:
            tp._runs.pop(fake_run_id, None)
