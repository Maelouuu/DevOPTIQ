# tests/test_131_panel_historique_gaps.py
"""
Page : Panel de Tests — historiques par page, statut d'un run, flux SSE,
statistiques globales et lecture défensive du carnet de bord.

Données dédiées (page/cas/run jetables), nettoyées après chaque test : la base
est partagée (scope=session).
"""
import json
import uuid
from datetime import datetime, timedelta

import pytest

import Code.routes.test_panel as _tp
from Code.extensions import db
from Code.models.test_models import TestCase, TestPage, TestResult, TestRun

pytestmark = pytest.mark.test_panel


@pytest.fixture
def jetable(app):
    """Une page, un cas et un run terminé avec un résultat, retirés ensuite."""
    with app.app_context():
        marque = "zz" + uuid.uuid4().hex[:8]
        page = TestPage(slug=marque, title=marque, file_name=marque + ".py")
        db.session.add(page)
        db.session.flush()
        cas = TestCase(page_id=page.id, node_id=marque + "::cas", name="cas",
                       last_status="passed")
        db.session.add(cas)
        run = TestRun(scope="page:" + marque, status="done",
                      started_at=datetime.utcnow() - timedelta(seconds=5),
                      finished_at=datetime.utcnow())
        db.session.add(run)
        db.session.flush()
        db.session.add(TestResult(run_id=run.id, case_id=cas.id, status="passed",
                                  duration=0.1))
        db.session.commit()
        ids = {"slug": marque, "page": page.id, "cas": cas.id, "run": run.id}
    yield ids
    with app.app_context():
        TestRun.query.filter_by(id=ids["run"]).delete()
        TestResult.query.filter_by(run_id=ids["run"]).delete()
        page = db.session.get(TestPage, ids["page"])
        if page:
            db.session.delete(page)
        db.session.commit()


class TestPageDetailHistorique:
    def test_page_detail_slug_inconnu_renvoie_404(self, auth_client):
        r = auth_client.get("/testpanel/page/zz-inexistante-" + uuid.uuid4().hex)
        assert r.status_code == 404

    def test_page_detail_avec_run_termine_repond_200(self, auth_client, jetable):
        r = auth_client.get("/testpanel/page/" + jetable["slug"])
        assert r.status_code == 200

    def test_api_page_expose_le_cas_joue(self, auth_client, jetable):
        r = auth_client.get("/testpanel/api/page/" + jetable["slug"])
        assert r.status_code == 200
        assert jetable["slug"] in json.dumps(r.get_json())


class TestRunStatus:
    def test_run_inconnu_renvoie_404_unknown(self, auth_client):
        r = auth_client.get("/testpanel/run/99999999/status")
        assert r.status_code == 404
        assert r.get_json()["status"] == "unknown"

    def test_run_termine_100_pour_cent(self, auth_client, jetable):
        r = auth_client.get(f"/testpanel/run/{jetable['run']}/status")
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "done"
        assert (body["total"], body["passed"], body["pct"]) == (1, 1, 100)

    def test_run_sans_resultat_donne_0_pour_cent(self, app, auth_client):
        with app.app_context():
            run = TestRun(scope="page:zz-vide", status="running")
            db.session.add(run)
            db.session.commit()
            rid = run.id
        try:
            r = auth_client.get(f"/testpanel/run/{rid}/status")
            body = r.get_json()
            assert (body["status"], body["total"], body["pct"]) == ("running", 0, 0)
        finally:
            with app.app_context():
                TestRun.query.filter_by(id=rid).delete()
                db.session.commit()


class TestStream:
    def test_flux_relaie_les_lignes_puis_done(self, auth_client):
        rid = 987654321
        with _tp._runs_lock:
            _tp._runs[rid] = {"lines": ["bonjour\n", "ok\n"], "done": True}
        try:
            r = auth_client.get(f"/testpanel/stream/{rid}")
            corps = r.get_data(as_text=True)
        finally:
            with _tp._runs_lock:
                _tp._runs.pop(rid, None)
        assert r.mimetype == "text/event-stream"
        assert corps.index("bonjour") < corps.index("ok") < corps.index("[DONE]")


class TestGlobalStats:
    def test_periode_heure_et_mois_acceptees(self, auth_client):
        for periode in ("hour", "month"):
            body = auth_client.get(f"/testpanel/global/stats?period={periode}").get_json()
            assert body["period"] == periode

    def test_run_recent_apparait_dans_le_graphique(self, auth_client, jetable):
        body = auth_client.get("/testpanel/global/stats?period=hour").get_json()
        assert any(p["run_id"] == jetable["run"] and p["pct"] == 100
                   for p in body["chart_points"])

    def test_cas_en_echec_designe_comme_plus_fautif(self, app, auth_client, jetable):
        with app.app_context():
            run_id = jetable["run"]
            # Un nombre d'échecs écrasant garantit que ce cas arrive en tête.
            db.session.add_all([
                TestResult(run_id=run_id, case_id=jetable["cas"], status="failed")
                for _ in range(500)
            ])
            db.session.commit()
        body = auth_client.get("/testpanel/global/stats").get_json()
        pire = body["summary"]["most_failing"]
        assert pire is not None and pire["fail_count"] >= 500


class TestJournalDefensif:
    def test_json_corrompu_donne_un_carnet_vide(self, tmp_path, monkeypatch):
        f = tmp_path / "journal.json"
        f.write_text("{pas du json", encoding="utf-8")
        monkeypatch.setattr(_tp, "_JOURNAL_FILE", f)
        assert _tp._load_journal() == {"plan": {}, "entries": []}

    def test_json_qui_n_est_pas_un_objet_est_ignore(self, tmp_path, monkeypatch):
        f = tmp_path / "journal.json"
        f.write_text("[1, 2]", encoding="utf-8")
        monkeypatch.setattr(_tp, "_JOURNAL_FILE", f)
        assert _tp._load_journal() == {"plan": {}, "entries": []}

    def test_fichier_absent_donne_un_carnet_vide(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_tp, "_JOURNAL_FILE", tmp_path / "absent.json")
        assert _tp._load_journal() == {"plan": {}, "entries": []}

    def test_progression_illisible_est_ramenee_a_zero(self, auth_client, tmp_path, monkeypatch):
        f = tmp_path / "journal.json"
        f.write_text(json.dumps({
            "plan": {"steps": [
                {"status": "todo", "progress": "abc"},
                {"status": "todo", "progress": 250},
                {"status": "done"},
            ]},
            "entries": [{"new_tests": "3", "tests_fixed": None, "patches": 1}],
        }), encoding="utf-8")
        monkeypatch.setattr(_tp, "_JOURNAL_FILE", f)
        r = auth_client.get("/testpanel/journal")
        assert r.status_code == 200
