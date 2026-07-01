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
# 9. GET /testpanel/stream/<run_id> — SSE de sortie pytest en direct
# ===========================================================================

class TestTestPanelStream:

    def _run_id(self, auth_client, monkeypatch):
        """Démarre un run (thread pytest neutralisé) et renvoie son id."""
        import Code.routes.test_panel as _tp
        monkeypatch.setattr(_tp, "_run_thread", lambda *a, **kw: None)
        r = auth_client.post("/testpanel/run/all")
        return r.get_json()["run_id"]

    def test_stream_unknown_run_returns_200(self, auth_client, monkeypatch):
        """run_id jamais démarré → la génération attend puis se termine sans erreur (200)."""
        monkeypatch.setattr("time.sleep", lambda s: None)
        r = auth_client.get("/testpanel/stream/999999999")
        assert r.status_code == 200

    def test_stream_unknown_run_body_is_empty(self, auth_client, monkeypatch):
        """run_id inconnu → aucune ligne n'est jamais poussée, le flux reste vide."""
        monkeypatch.setattr("time.sleep", lambda s: None)
        r = auth_client.get("/testpanel/stream/999999999")
        assert r.get_data(as_text=True) == ""

    def test_stream_content_type_is_event_stream(self, auth_client, monkeypatch):
        """Le type MIME de la réponse est text/event-stream."""
        run_id = self._run_id(auth_client, monkeypatch)
        import Code.routes.test_panel as _tp
        with _tp._runs_lock:
            _tp._runs[run_id]['done'] = True
        r = auth_client.get(f"/testpanel/stream/{run_id}")
        assert r.mimetype == "text/event-stream"

    def test_stream_done_run_yields_done_marker(self, auth_client, monkeypatch):
        """Un run déjà terminé (done=True) émet immédiatement le marqueur [DONE]."""
        run_id = self._run_id(auth_client, monkeypatch)
        import Code.routes.test_panel as _tp
        with _tp._runs_lock:
            _tp._runs[run_id]['done'] = True
        r = auth_client.get(f"/testpanel/stream/{run_id}")
        body = r.get_data(as_text=True)
        assert '"[DONE]"' in body

    def test_stream_emits_buffered_lines_in_order(self, auth_client, monkeypatch):
        """Les lignes déjà accumulées dans _runs sont renvoyées, dans l'ordre."""
        run_id = self._run_id(auth_client, monkeypatch)
        import Code.routes.test_panel as _tp
        with _tp._runs_lock:
            _tp._runs[run_id]['lines'] = ["premiere ligne\n", "deuxieme ligne\n"]
            _tp._runs[run_id]['done'] = True
        r = auth_client.get(f"/testpanel/stream/{run_id}")
        body = r.get_data(as_text=True)
        assert body.index("premiere ligne") < body.index("deuxieme ligne")

    def test_stream_no_auth_still_reachable(self, client, monkeypatch):
        """Le panel de tests n'exige pas d'authentification (outil interne)."""
        monkeypatch.setattr("time.sleep", lambda s: None)
        r = client.get("/testpanel/stream/999999999")
        assert r.status_code == 200
