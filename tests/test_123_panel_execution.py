# tests/test_123_panel_execution.py
"""
Page : Panel de Tests — orchestration d'un run (`_executer_run`, `_run_thread`).

Le sous-processus pytest est remplacé par un faux `Popen` : on vérifie que les
lignes de sortie sont relayées, que le XML JUnit est consommé puis supprimé,
que l'échec de lancement est signalé, et que le drapeau `done` est posé en
dernier. Données dédiées, nettoyées après chaque test (base partagée).
"""
import io
import os

import pytest

import Code.routes.test_panel as _tp
from Code.extensions import db
from Code.models.test_models import TestRun

pytestmark = pytest.mark.test_panel


class _FauxPopen:
    def __init__(self, args, stdout=None, stderr=None, cwd=None, text=None, bufsize=None):
        _FauxPopen.args = args
        self.stdout = io.StringIO("ligne 1\nligne 2\n")

    def wait(self):
        return 0


def _nouveau_run(app):
    with app.app_context():
        run = TestRun(scope="all", status="running")
        db.session.add(run)
        db.session.commit()
        return run.id


def _purger(app, run_id):
    with app.app_context():
        run = db.session.get(TestRun, run_id)
        if run:
            db.session.delete(run)
            db.session.commit()
    with _tp._runs_lock:
        _tp._runs.pop(run_id, None)


class TestExecuterRun:

    def test_relaie_la_sortie_du_sous_processus(self, app, monkeypatch):
        run_id = _nouveau_run(app)
        monkeypatch.setattr(_tp.subprocess, "Popen", _FauxPopen)
        lignes = []
        try:
            _tp._executer_run(run_id, "all", app, lignes.append)
            assert "ligne 1\n" in lignes and "ligne 2\n" in lignes
            assert lignes[0].startswith("$ pytest")
        finally:
            _purger(app, run_id)

    def test_echec_de_lancement_est_signale(self, app, monkeypatch):
        run_id = _nouveau_run(app)

        def _boom(*a, **k):
            raise OSError("introuvable")

        monkeypatch.setattr(_tp.subprocess, "Popen", _boom)
        lignes = []
        try:
            _tp._executer_run(run_id, "all", app, lignes.append)
            assert any("[ERROR lors du lancement] introuvable" in l for l in lignes)
        finally:
            _purger(app, run_id)

    def test_sans_xml_le_run_est_marque_termine_sur_sqlite_fichier(self, app, monkeypatch, tmp_path):
        # Cible le repli « aucun XML produit » sur une base SQLite réelle (fichier).
        import sqlite3
        base = tmp_path / "panel.db"
        con = sqlite3.connect(base)
        con.execute("CREATE TABLE test_runs (id INTEGER PRIMARY KEY, status TEXT, finished_at TEXT)")
        con.execute("INSERT INTO test_runs (id, status) VALUES (7, 'running')")
        con.commit()
        con.close()
        monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{base}")
        monkeypatch.setattr(_tp.subprocess, "Popen", _FauxPopen)
        monkeypatch.setattr(_tp, "_build_args",
                            lambda scope, xml: ["py", "-m", "pytest", "--junit-xml=" + xml])
        monkeypatch.setattr(_tp.os.path, "exists", lambda p: False)
        _tp._executer_run(7, "all", app, lambda l: None)
        con = sqlite3.connect(base)
        statut, fin = con.execute("SELECT status, finished_at FROM test_runs WHERE id=7").fetchone()
        con.close()
        assert statut == "done" and fin

    def test_xml_present_est_consomme_puis_supprime(self, app, monkeypatch):
        run_id = _nouveau_run(app)
        sauvegardes = []
        monkeypatch.setattr(_tp.subprocess, "Popen", _FauxPopen)
        monkeypatch.setattr(_tp, "_save_results",
                            lambda url, rid, xml, emit: sauvegardes.append((rid, xml)))
        fichiers = []
        vrai_mkstemp = _tp.tempfile.mkstemp

        def _mkstemp(*a, **k):
            fd, chemin = vrai_mkstemp(*a, **k)
            fichiers.append(chemin)
            return fd, chemin

        monkeypatch.setattr(_tp.tempfile, "mkstemp", _mkstemp)
        try:
            _tp._executer_run(run_id, "all", app, lambda l: None)
            assert sauvegardes == [(run_id, fichiers[0])]
            assert not os.path.exists(fichiers[0])
        finally:
            _purger(app, run_id)


class TestRunThread:

    def test_pose_done_apres_execution_et_libere_le_creneau(self, app, monkeypatch):
        run_id = _nouveau_run(app)
        avant = _tp._actifs
        with _tp._runs_lock:
            _tp._runs[run_id] = {"lines": [], "done": False}
        monkeypatch.setattr(_tp, "_executer_run",
                            lambda rid, scope, a, emit: emit("ok\n"))
        try:
            _tp._run_thread(run_id, "all", app)
            assert _tp._runs[run_id]["lines"] == ["ok\n"]
            assert _tp._actifs == avant
        finally:
            _purger(app, run_id)

    def test_refus_quand_aucun_creneau_libre(self, app, monkeypatch):
        run_id = _nouveau_run(app)
        with _tp._runs_lock:
            _tp._runs[run_id] = {"lines": [], "done": False}
        monkeypatch.setattr(_tp, "_reserver_creneau", lambda: False)
        try:
            _tp._run_thread(run_id, "all", app)
            assert "[REFUSÉ]" in _tp._runs[run_id]["lines"][0]
            assert _tp._runs[run_id]["done"] is True
            with app.app_context():
                assert db.session.get(TestRun, run_id).status == "done"
        finally:
            _purger(app, run_id)
