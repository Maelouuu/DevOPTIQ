# tests/test_37_test_panel.py
"""
Panel de tests intégré (/testpanel)

Couvre :
  - GET  /testpanel/                  (panel.html — auto-sync des fichiers test)
  - GET  /testpanel/page/<slug>       (page.html — 404 si slug inconnu)
  - GET  /testpanel/case/<id>         (case.html — 404 si id inconnu)
  - GET  /testpanel/global/stats      (JSON statistiques globales)
  - GET  /testpanel/run/<id>/status   (JSON statut d'une exécution)
  - POST /testpanel/admin/reset-stale (JSON — expire les runs bloqués)
  - POST /testpanel/run/page/<slug>   (JSON — 404 si slug inconnu, run_id sinon)
  - POST /testpanel/run/all           (JSON — retourne run_id, sans lancer pytest)
  - GET  /testpanel/patches           (patches.html — registre des correctifs tracés)
  - GET  /testpanel/journal           (journal.html — plan versionné + historique)
  - GET  /testpanel/stream/<run_id>   (SSE — sleep neutralisé pour éviter tout blocage)
"""
import pytest

pytestmark = pytest.mark.test_panel

# ---------------------------------------------------------------------------
# Helper : s'assurer que la sync a peuplé TestPage/TestCase
# ---------------------------------------------------------------------------

def _ensure_synced(auth_client):
    """Déclenche la sync automatique via GET /testpanel/."""
    auth_client.get("/testpanel/")


def _create_test_run(app, status="done"):
    """Insère un TestRun en base et retourne son id."""
    from Code.models.test_models import TestRun
    from Code.extensions import db
    with app.app_context():
        run = TestRun(scope="all", status=status)
        db.session.add(run)
        db.session.commit()
        return run.id


# ===========================================================================
# 1. GET /testpanel/ — Page principale
# ===========================================================================

class TestTestPanelMain:

    def test_panel_accessible_auth(self, auth_client):
        """GET /testpanel/ retourne 200 pour un utilisateur connecté."""
        r = auth_client.get("/testpanel/")
        assert r.status_code == 200

    def test_panel_response_is_html(self, auth_client):
        """La réponse du panel est du HTML."""
        r = auth_client.get("/testpanel/")
        assert "text/html" in r.content_type

    def test_panel_syncs_test_pages(self, auth_client, app):
        """Après GET /testpanel/, des TestPage existent en base (auto-sync)."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            count = TestPage.query.count()
        assert count > 0

    def test_panel_syncs_test_cases(self, auth_client, app):
        """Après GET /testpanel/, des TestCase existent en base."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestCase
            count = TestCase.query.count()
        assert count > 0

    def test_panel_no_auth_no_crash(self, client):
        """Sans session, le panel répond 302 ou 200 (pas de crash serveur)."""
        r = client.get("/testpanel/")
        assert r.status_code in (200, 302)

    def test_panel_page_contains_testpanel_reference(self, auth_client):
        """Le HTML retourné contient une référence au panel de tests."""
        r = auth_client.get("/testpanel/")
        assert b"testpanel" in r.data.lower() or b"test" in r.data.lower()


# ===========================================================================
# 2. GET /testpanel/page/<slug>
# ===========================================================================

class TestTestPanelPageDetail:

    def test_unknown_slug_returns_404(self, auth_client):
        """Slug inexistant → 404."""
        r = auth_client.get("/testpanel/page/slug_inexistant_xyz_abc")
        assert r.status_code == 404

    def test_known_slug_returns_200(self, auth_client, app):
        """Un slug référencé en base après sync → 200."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            page = TestPage.query.first()
        if page is None:
            pytest.skip("Aucune page de test en base après sync")
        r = auth_client.get(f"/testpanel/page/{page.slug}")
        assert r.status_code == 200

    def test_known_slug_returns_html(self, auth_client, app):
        """Le détail de page retourne du HTML."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            page = TestPage.query.first()
        if page is None:
            pytest.skip("Aucune page de test en base")
        r = auth_client.get(f"/testpanel/page/{page.slug}")
        assert "text/html" in r.content_type

    def test_synced_page_has_slug_and_title(self, auth_client, app):
        """Les pages synchées ont un slug et un title."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            pages = TestPage.query.all()
        for p in pages[:5]:
            assert p.slug
            assert p.title

    def test_pages_have_file_name(self, auth_client, app):
        """Les pages synchées ont un file_name non vide."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            pages = TestPage.query.all()
        for p in pages[:5]:
            assert p.file_name and p.file_name.endswith(".py")


# ===========================================================================
# 3. GET /testpanel/case/<id>
# ===========================================================================

class TestTestPanelCaseDetail:

    def test_unknown_case_returns_404(self, auth_client):
        """case_id inexistant → 404."""
        r = auth_client.get("/testpanel/case/999999")
        assert r.status_code == 404

    def test_known_case_returns_200(self, auth_client, app):
        """Un case existant en base → 200."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestCase
            case = TestCase.query.first()
        if case is None:
            pytest.skip("Aucun test case en base après sync")
        r = auth_client.get(f"/testpanel/case/{case.id}")
        assert r.status_code == 200

    def test_known_case_returns_html(self, auth_client, app):
        """Le détail d'un case retourne du HTML."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestCase
            case = TestCase.query.first()
        if case is None:
            pytest.skip("Aucun test case en base")
        r = auth_client.get(f"/testpanel/case/{case.id}")
        assert "text/html" in r.content_type

    def test_synced_case_has_node_id(self, auth_client, app):
        """Les cases synchés ont un node_id au format attendu."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestCase
            cases = TestCase.query.limit(5).all()
        for c in cases:
            assert c.node_id
            assert "tests/" in c.node_id

    def test_synced_cases_have_class_and_name(self, auth_client, app):
        """Les cases synchés ont class_name et name renseignés."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestCase
            cases = TestCase.query.limit(5).all()
        for c in cases:
            assert c.class_name
            assert c.name and c.name.startswith("test_")


# ===========================================================================
# 4. GET /testpanel/global/stats
# ===========================================================================

class TestTestPanelGlobalStats:

    def test_stats_returns_200(self, auth_client):
        """GET /testpanel/global/stats retourne 200."""
        r = auth_client.get("/testpanel/global/stats")
        assert r.status_code == 200

    def test_stats_response_is_json(self, auth_client):
        """La réponse est du JSON."""
        r = auth_client.get("/testpanel/global/stats")
        assert r.content_type.startswith("application/json")

    def test_stats_has_summary_key(self, auth_client):
        """La réponse contient la clé 'summary'."""
        data = auth_client.get("/testpanel/global/stats").get_json()
        assert "summary" in data

    def test_stats_summary_has_total_runs(self, auth_client):
        """summary.total_runs est un entier."""
        summary = auth_client.get("/testpanel/global/stats").get_json()["summary"]
        assert "total_runs" in summary
        assert isinstance(summary["total_runs"], int)

    def test_stats_summary_has_overall_pct(self, auth_client):
        """summary.overall_pct est un entier entre 0 et 100."""
        summary = auth_client.get("/testpanel/global/stats").get_json()["summary"]
        assert "overall_pct" in summary
        assert 0 <= summary["overall_pct"] <= 100

    def test_stats_summary_has_avg_duration(self, auth_client):
        """summary.avg_duration_s est None ou un nombre."""
        summary = auth_client.get("/testpanel/global/stats").get_json()["summary"]
        assert "avg_duration_s" in summary
        assert summary["avg_duration_s"] is None or isinstance(summary["avg_duration_s"], (int, float))

    def test_stats_summary_has_most_failing(self, auth_client):
        """summary.most_failing est None ou un dict."""
        summary = auth_client.get("/testpanel/global/stats").get_json()["summary"]
        assert "most_failing" in summary
        assert summary["most_failing"] is None or isinstance(summary["most_failing"], dict)

    def test_stats_has_chart_points_list(self, auth_client):
        """chart_points est une liste."""
        data = auth_client.get("/testpanel/global/stats").get_json()
        assert "chart_points" in data
        assert isinstance(data["chart_points"], list)

    def test_stats_has_recent_runs_list(self, auth_client):
        """recent_runs est une liste."""
        data = auth_client.get("/testpanel/global/stats").get_json()
        assert "recent_runs" in data
        assert isinstance(data["recent_runs"], list)

    def test_stats_period_day_default(self, auth_client):
        """Sans paramètre → period='day'."""
        data = auth_client.get("/testpanel/global/stats").get_json()
        assert data.get("period") == "day"

    def test_stats_period_hour(self, auth_client):
        """?period=hour → period='hour' dans la réponse."""
        data = auth_client.get("/testpanel/global/stats?period=hour").get_json()
        assert data.get("period") == "hour"

    def test_stats_period_month(self, auth_client):
        """?period=month → period='month' dans la réponse."""
        data = auth_client.get("/testpanel/global/stats?period=month").get_json()
        assert data.get("period") == "month"


# ===========================================================================
# 5. GET /testpanel/run/<id>/status
# ===========================================================================

class TestTestPanelRunStatus:

    def test_unknown_run_returns_404(self, auth_client):
        """run_id inexistant → 404."""
        r = auth_client.get("/testpanel/run/999999/status")
        assert r.status_code == 404

    def test_unknown_run_has_status_unknown(self, auth_client):
        """La réponse 404 contient status='unknown'."""
        data = auth_client.get("/testpanel/run/999999/status").get_json()
        assert data is not None
        assert data.get("status") == "unknown"

    def test_known_run_returns_200(self, auth_client, app):
        """Un TestRun existant → 200."""
        run_id = _create_test_run(app, status="done")
        r = auth_client.get(f"/testpanel/run/{run_id}/status")
        assert r.status_code == 200

    def test_known_run_has_status_field(self, auth_client, app):
        """La réponse contient 'status'."""
        run_id = _create_test_run(app, status="done")
        data = auth_client.get(f"/testpanel/run/{run_id}/status").get_json()
        assert "status" in data

    def test_known_run_has_pct_field(self, auth_client, app):
        """La réponse contient 'pct' (entier 0-100)."""
        run_id = _create_test_run(app, status="done")
        data = auth_client.get(f"/testpanel/run/{run_id}/status").get_json()
        assert "pct" in data
        assert 0 <= data["pct"] <= 100

    def test_known_run_has_total_and_passed(self, auth_client, app):
        """La réponse contient 'total' et 'passed'."""
        run_id = _create_test_run(app, status="done")
        data = auth_client.get(f"/testpanel/run/{run_id}/status").get_json()
        assert "total" in data
        assert "passed" in data

    def test_run_status_returns_json(self, auth_client):
        """La réponse de status est toujours du JSON."""
        r = auth_client.get("/testpanel/run/999999/status")
        assert r.content_type.startswith("application/json")


# ===========================================================================
# 6. POST /testpanel/admin/reset-stale
# ===========================================================================

class TestTestPanelResetStale:

    def test_reset_stale_returns_200(self, auth_client):
        """POST /testpanel/admin/reset-stale retourne 200."""
        r = auth_client.post("/testpanel/admin/reset-stale")
        assert r.status_code == 200

    def test_reset_stale_response_is_json(self, auth_client):
        """La réponse est du JSON."""
        r = auth_client.post("/testpanel/admin/reset-stale")
        assert r.content_type.startswith("application/json")

    def test_reset_stale_has_expired_key(self, auth_client):
        """La réponse contient la clé 'expired'."""
        data = auth_client.post("/testpanel/admin/reset-stale").get_json()
        assert "expired" in data
        assert isinstance(data["expired"], int)

    def test_reset_stale_expires_running_run(self, auth_client, app):
        """Un run 'running' est passé à 'done' après reset-stale."""
        run_id = _create_test_run(app, status="running")
        r = auth_client.post("/testpanel/admin/reset-stale")
        data = r.get_json()
        assert data["expired"] >= 1
        with app.app_context():
            from Code.models.test_models import TestRun
            run = TestRun.query.get(run_id)
            assert run.status == "done"

    def test_reset_stale_zero_when_no_running(self, auth_client, app):
        """Sans runs 'running', expired=0."""
        with app.app_context():
            from Code.models.test_models import TestRun
            from Code.extensions import db
            TestRun.query.filter_by(status="running").update({"status": "done"})
            db.session.commit()
        data = auth_client.post("/testpanel/admin/reset-stale").get_json()
        assert data["expired"] == 0

    def test_reset_stale_idempotent(self, auth_client):
        """Appeler reset-stale deux fois ne génère pas d'erreur."""
        auth_client.post("/testpanel/admin/reset-stale")
        r = auth_client.post("/testpanel/admin/reset-stale")
        assert r.status_code == 200


# ===========================================================================
# 7. POST /testpanel/run/page/<slug>
# ===========================================================================

class TestTestPanelRunPage:

    def test_run_unknown_slug_returns_404(self, auth_client):
        """Slug inexistant → 404."""
        r = auth_client.post("/testpanel/run/page/slug_inexistant_xyz")
        assert r.status_code == 404

    def test_run_known_slug_returns_run_id(self, auth_client, app, monkeypatch):
        """Slug connu → 200 avec run_id (monkeypatch pour éviter subprocess pytest)."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            page = TestPage.query.first()
        if page is None:
            pytest.skip("Aucune page synchée en base")

        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)

        r = auth_client.post(f"/testpanel/run/page/{page.slug}")
        assert r.status_code == 200
        data = r.get_json()
        assert "run_id" in data
        assert isinstance(data["run_id"], int)
        assert data["run_id"] > 0

    def test_run_page_creates_test_run_in_db(self, auth_client, app, monkeypatch):
        """Après POST run/page, un TestRun est créé en base."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            page = TestPage.query.first()
        if page is None:
            pytest.skip("Aucune page synchée en base")

        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)

        r = auth_client.post(f"/testpanel/run/page/{page.slug}")
        run_id = r.get_json()["run_id"]

        with app.app_context():
            from Code.models.test_models import TestRun
            run = TestRun.query.get(run_id)
        assert run is not None
        assert f"page:{page.slug}" == run.scope

    def test_run_page_run_starts_as_running(self, auth_client, app, monkeypatch):
        """Le TestRun créé a initialement le statut 'running'."""
        _ensure_synced(auth_client)
        with app.app_context():
            from Code.models.test_models import TestPage
            page = TestPage.query.first()
        if page is None:
            pytest.skip("Aucune page synchée en base")

        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)

        r = auth_client.post(f"/testpanel/run/page/{page.slug}")
        run_id = r.get_json()["run_id"]

        with app.app_context():
            from Code.models.test_models import TestRun
            run = TestRun.query.get(run_id)
        assert run.status == "running"


# ===========================================================================
# 8. POST /testpanel/run/all
# ===========================================================================

class TestTestPanelRunAll:

    def test_run_all_returns_200(self, auth_client, monkeypatch):
        """POST /testpanel/run/all retourne 200."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)
        r = auth_client.post("/testpanel/run/all")
        assert r.status_code == 200

    def test_run_all_response_is_json(self, auth_client, monkeypatch):
        """La réponse est du JSON."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)
        r = auth_client.post("/testpanel/run/all")
        assert r.content_type.startswith("application/json")

    def test_run_all_response_has_run_id(self, auth_client, monkeypatch):
        """La réponse contient run_id (entier positif)."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)
        r = auth_client.post("/testpanel/run/all")
        data = r.get_json()
        assert "run_id" in data
        assert isinstance(data["run_id"], int)
        assert data["run_id"] > 0

    def test_run_all_creates_test_run_in_db(self, auth_client, app, monkeypatch):
        """Après POST run/all, un TestRun est enregistré en base."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)
        r = auth_client.post("/testpanel/run/all")
        run_id = r.get_json()["run_id"]
        with app.app_context():
            from Code.models.test_models import TestRun
            run = TestRun.query.get(run_id)
        assert run is not None
        assert run.scope == "all"

    def test_run_all_run_scope_is_all(self, auth_client, app, monkeypatch):
        """Le scope du TestRun créé est 'all'."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)
        r = auth_client.post("/testpanel/run/all")
        run_id = r.get_json()["run_id"]
        with app.app_context():
            from Code.models.test_models import TestRun
            run = TestRun.query.get(run_id)
        assert run.scope == "all"

    def test_run_all_sequential_runs_have_distinct_ids(self, auth_client, monkeypatch):
        """Deux appels successifs créent deux runs avec des IDs distincts."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)
        r1 = auth_client.post("/testpanel/run/all")
        r2 = auth_client.post("/testpanel/run/all")
        assert r1.get_json()["run_id"] != r2.get_json()["run_id"]


# ===========================================================================
# 9. GET /testpanel/patches
# ===========================================================================

def _get_or_create_patch(app, **overrides):
    """Crée (ou réutilise) un TestPatch dédié aux tests, isolé par patch_uid unique."""
    from Code.models.test_models import TestPatch
    from Code.extensions import db
    with app.app_context():
        patch = TestPatch.query.filter_by(patch_uid="unit-test-panel-patch-coverage").first()
        if patch is None:
            patch = TestPatch(patch_uid="unit-test-panel-patch-coverage")
            db.session.add(patch)
        patch.title           = overrides.get("title", "Patch de couverture unitaire")
        patch.node_ids        = "[\"tests/test_00_fake.py::T::test_fake\"]"
        patch.page_slug       = overrides.get("page_slug", "tools")
        patch.failure_reason  = "Échec simulé pour couverture du panel."
        patch.was_real_bug    = overrides.get("was_real_bug", True)
        patch.root_cause      = overrides.get("root_cause", "app_bug")
        patch.error            = "Erreur simulée."
        patch.fix_description  = "Correctif simulé."
        patch.files_changed    = "[\"Code/routes/tools.py\"]"
        patch.author           = "routine"
        db.session.commit()
        return patch.id


class TestTestPanelPatches:

    def test_patches_page_accessible_auth(self, auth_client):
        r = auth_client.get("/testpanel/patches")
        assert r.status_code == 200

    def test_patches_page_no_auth_no_crash(self, client):
        """La page patches ne doit pas planter (500) sans session active."""
        r = client.get("/testpanel/patches")
        assert r.status_code != 500

    def test_patches_page_response_is_html(self, auth_client):
        r = auth_client.get("/testpanel/patches")
        assert "text/html" in r.content_type

    def test_patches_page_lists_seeded_patch_title(self, auth_client, app):
        """Un patch enregistré en base apparaît dans le rendu de la page."""
        _get_or_create_patch(app, title="Patch de couverture unitaire")
        r = auth_client.get("/testpanel/patches")
        assert b"Patch de couverture unitaire" in r.data

    def test_patches_page_real_bug_flag_rendered(self, auth_client, app):
        """was_real_bug=True doit se traduire par le libellé 'Oui' dans le HTML."""
        _get_or_create_patch(app, was_real_bug=True)
        r = auth_client.get("/testpanel/patches")
        assert "Oui".encode() in r.data

    def test_patches_page_contains_files_changed(self, auth_client, app):
        _get_or_create_patch(app)
        r = auth_client.get("/testpanel/patches")
        assert b"Code/routes/tools.py" in r.data


# ===========================================================================
# 10. GET /testpanel/journal
# ===========================================================================

class TestTestPanelJournal:

    def test_journal_page_accessible_auth(self, auth_client):
        r = auth_client.get("/testpanel/journal")
        assert r.status_code == 200

    def test_journal_page_no_auth_no_crash(self, client):
        r = client.get("/testpanel/journal")
        assert r.status_code != 500

    def test_journal_page_response_is_html(self, auth_client):
        r = auth_client.get("/testpanel/journal")
        assert "text/html" in r.content_type

    def test_journal_page_reflects_versioned_plan_title(self, auth_client):
        """Le titre du plan versionné (tests/journal.json) apparaît dans la page."""
        r = auth_client.get("/testpanel/journal")
        assert "Plan de couverture".encode() in r.data

    def test_journal_page_missing_file_no_crash(self, auth_client, monkeypatch):
        """Si tests/journal.json est introuvable, la page reste fonctionnelle."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_JOURNAL_FILE", _tp._TESTS_DIR / "journal_inexistant.json")
        r = auth_client.get("/testpanel/journal")
        assert r.status_code == 200


# ===========================================================================
# 11. GET /testpanel/stream/<run_id>
# ===========================================================================

class TestTestPanelStream:

    def test_stream_known_run_returns_200(self, auth_client, monkeypatch):
        """Un run déjà terminé en mémoire se stream immédiatement (pas de blocage)."""
        import Code.routes.test_panel as _tp
        import time as _time_mod
        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        run_id = 999001
        with _tp._runs_lock:
            _tp._runs[run_id] = {"lines": ["ligne 1", "ligne 2"], "done": True}
        r = auth_client.get(f"/testpanel/stream/{run_id}")
        assert r.status_code == 200

    def test_stream_known_run_content_type_is_event_stream(self, auth_client, monkeypatch):
        import Code.routes.test_panel as _tp
        import time as _time_mod
        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        run_id = 999002
        with _tp._runs_lock:
            _tp._runs[run_id] = {"lines": [], "done": True}
        r = auth_client.get(f"/testpanel/stream/{run_id}")
        assert r.content_type.startswith("text/event-stream")

    def test_stream_known_run_body_contains_lines(self, auth_client, monkeypatch):
        import Code.routes.test_panel as _tp
        import time as _time_mod
        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        run_id = 999003
        with _tp._runs_lock:
            _tp._runs[run_id] = {"lines": ["patch appliqué"], "done": True}
        r = auth_client.get(f"/testpanel/stream/{run_id}")
        assert b"patch appliqu" in r.data

    def test_stream_known_run_body_ends_with_done_marker(self, auth_client, monkeypatch):
        import Code.routes.test_panel as _tp
        import time as _time_mod
        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        run_id = 999004
        with _tp._runs_lock:
            _tp._runs[run_id] = {"lines": [], "done": True}
        r = auth_client.get(f"/testpanel/stream/{run_id}")
        assert b"[DONE]" in r.data

    def test_stream_unknown_run_returns_200_without_hanging(self, auth_client, monkeypatch):
        """Un run_id jamais initialisé sort de la boucle sans bloquer (sleep neutralisé)."""
        import Code.routes.test_panel as _tp
        import time as _time_mod
        monkeypatch.setattr(_time_mod, "sleep", lambda s: None)
        r = auth_client.get("/testpanel/stream/999999")
        assert r.status_code == 200
