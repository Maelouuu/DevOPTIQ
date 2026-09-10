# tests/test_69_panel_internals.py
"""
Page : Panel de Tests — fonctions internes non couvertes par l'API HTTP.

`test_37_test_panel.py` et `test_65_panel_api.py` couvrent les routes et
`_fiabilite`, mais plusieurs fonctions qui font le vrai travail du panel
n'étaient exercées par aucun test direct : la construction de la commande
pytest (`_build_args`), la persistance d'un run depuis son XML JUnit
(`_save_results`), la synchronisation tolérante de `patches.json`
(`sync_patches_to_db`), et les petits agrégats utilisés par les templates
(`_patches_for_nodes`, `_patch_to_dict`, `_patch_category_counts`,
`_recent_runs`). Ce fichier isole chacune, avec des données dédiées et un
nettoyage explicite pour ne pas polluer la base partagée (scope=session).
"""
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import Code.routes.test_panel as _tp
from Code.extensions import db
from Code.models.test_models import TestCase, TestPage, TestPatch, TestResult, TestRun

pytestmark = pytest.mark.test_panel


# ---------------------------------------------------------------------------
# _build_args
# ---------------------------------------------------------------------------

class TestBuildArgs:

    def test_scope_all_ajoute_le_dossier_tests(self, app):
        with app.app_context():
            args = _tp._build_args("all", "/tmp/whatever.xml")
        assert args[-1] == str(_tp._TESTS_DIR)
        assert "--junit-xml=/tmp/whatever.xml" in args

    def test_scope_page_inconnue_n_ajoute_rien(self, app):
        with app.app_context():
            base = _tp._build_args("all", "/tmp/x.xml")
            args = _tp._build_args("page:slug_69_inexistant_xyz", "/tmp/x.xml")
        # Rien à exécuter : le suffixe reste celui de la commande de base.
        assert args == base[:-1]  # base sans le "tests/" final propre à 'all'

    def test_scope_page_connue_ajoute_son_fichier(self, app):
        with app.app_context():
            page = TestPage(slug="page_69_interne", title="Page 69 interne",
                             file_name="test_69_panel_internals.py")
            db.session.add(page)
            db.session.commit()
            try:
                args = _tp._build_args("page:page_69_interne", "/tmp/x.xml")
                assert args[-1] == str(_tp._TESTS_DIR / "test_69_panel_internals.py")
            finally:
                db.session.delete(page)
                db.session.commit()

    def test_scope_case_inconnu_n_ajoute_rien(self, app):
        with app.app_context():
            base = _tp._build_args("all", "/tmp/x.xml")
            args = _tp._build_args("case:99999999", "/tmp/x.xml")
        assert args == base[:-1]

    def test_scope_case_connu_ajoute_son_node_id(self, app):
        with app.app_context():
            page = TestPage(slug="page_69_case", title="Page 69 case",
                             file_name="test_69_panel_internals.py")
            db.session.add(page)
            db.session.flush()
            case = TestCase(page_id=page.id, node_id="tests/test_69_panel_internals.py::test_x",
                             name="test_x")
            db.session.add(case)
            db.session.commit()
            try:
                args = _tp._build_args(f"case:{case.id}", "/tmp/x.xml")
                assert args[-1] == case.node_id
            finally:
                db.session.delete(case)
                db.session.delete(page)
                db.session.commit()


# ---------------------------------------------------------------------------
# _save_results
# ---------------------------------------------------------------------------

def _write_junit_xml(path, testcases_xml):
    Path(path).write_text(
        '<?xml version="1.0"?><testsuites><testsuite>'
        + testcases_xml + '</testsuite></testsuites>',
        encoding="utf-8",
    )


class TestSaveResults:

    def _make_run_and_case(self, node_id):
        page = TestPage(slug="page_69_save", title="Page 69 save",
                         file_name="test_69_panel_internals.py")
        db.session.add(page)
        db.session.flush()
        case = TestCase(page_id=page.id, node_id=node_id, name="test_y")
        db.session.add(case)
        run = TestRun(scope="all", status="running")
        db.session.add(run)
        db.session.commit()
        return page, case, run

    def test_resultat_passe_est_persiste_et_case_mise_a_jour(self, app):
        with app.app_context():
            node_id = "tests/test_69_panel_internals.py::test_y"
            page, case, run = self._make_run_and_case(node_id)
            db_url = app.config["SQLALCHEMY_DATABASE_URI"]
            fd, xml_path = tempfile.mkstemp(suffix=".xml")
            import os
            os.close(fd)
            try:
                _write_junit_xml(
                    xml_path,
                    '<testcase classname="tests.test_69_panel_internals" '
                    'name="test_y" time="0.01"></testcase>',
                )
                lines = []
                _tp._save_results(db_url, run.id, xml_path, lines.append)

                db.session.expire_all()
                refreshed_case = db.session.get(TestCase, case.id)
                refreshed_run = db.session.get(TestRun, run.id)
                result = TestResult.query.filter_by(run_id=run.id, case_id=case.id).first()

                assert result is not None
                assert result.status == "passed"
                assert refreshed_case.last_status == "passed"
                assert refreshed_run.status == "done"
                assert any("sauvegardés" in l for l in lines)
            finally:
                os.unlink(xml_path)
                TestResult.query.filter_by(run_id=run.id).delete()
                db.session.delete(run)
                db.session.delete(case)
                db.session.delete(page)
                db.session.commit()

    def test_resultat_en_echec_porte_le_message_de_failure(self, app):
        with app.app_context():
            node_id = "tests/test_69_panel_internals.py::test_z"
            page, case, run = self._make_run_and_case(node_id)
            db_url = app.config["SQLALCHEMY_DATABASE_URI"]
            fd, xml_path = tempfile.mkstemp(suffix=".xml")
            import os
            os.close(fd)
            try:
                _write_junit_xml(
                    xml_path,
                    '<testcase classname="tests.test_69_panel_internals" '
                    'name="test_z" time="0.02">'
                    '<failure message="assert 1 == 2">trace ici</failure>'
                    '</testcase>',
                )
                lines = []
                _tp._save_results(db_url, run.id, xml_path, lines.append)

                db.session.expire_all()
                result = TestResult.query.filter_by(run_id=run.id, case_id=case.id).first()
                assert result.status == "failed"
                assert "assert 1 == 2" in result.message
                assert "trace ici" in result.message
            finally:
                os.unlink(xml_path)
                TestResult.query.filter_by(run_id=run.id).delete()
                db.session.delete(run)
                db.session.delete(case)
                db.session.delete(page)
                db.session.commit()

    def test_resultat_sans_case_correspondante_est_ignore_sans_erreur(self, app):
        with app.app_context():
            run = TestRun(scope="all", status="running")
            db.session.add(run)
            db.session.commit()
            db_url = app.config["SQLALCHEMY_DATABASE_URI"]
            fd, xml_path = tempfile.mkstemp(suffix=".xml")
            import os
            os.close(fd)
            try:
                _write_junit_xml(
                    xml_path,
                    '<testcase classname="tests.test_69_panel_internals" '
                    'name="test_orphelin_69" time="0.0"></testcase>',
                )
                lines = []
                _tp._save_results(db_url, run.id, xml_path, lines.append)
                db.session.expire_all()
                assert TestResult.query.filter_by(run_id=run.id).count() == 0
                assert db.session.get(TestRun, run.id).status == "done"
            finally:
                os.unlink(xml_path)
                db.session.delete(run)
                db.session.commit()

    def test_xml_invalide_emet_un_avertissement_sans_lever(self, app):
        with app.app_context():
            run = TestRun(scope="all", status="running")
            db.session.add(run)
            db.session.commit()
            db_url = app.config["SQLALCHEMY_DATABASE_URI"]
            fd, xml_path = tempfile.mkstemp(suffix=".xml")
            import os
            os.close(fd)
            try:
                Path(xml_path).write_text("<<< pas du xml >>>", encoding="utf-8")
                lines = []
                _tp._save_results(db_url, run.id, xml_path, lines.append)
                assert any("WARN" in l for l in lines)
            finally:
                os.unlink(xml_path)
                db.session.delete(run)
                db.session.commit()


# ---------------------------------------------------------------------------
# sync_patches_to_db — tolérance aux fichiers absents/malformés
# ---------------------------------------------------------------------------

class TestSyncPatchesToDbTolerant:

    def test_fichier_absent_ne_leve_pas(self, app, monkeypatch, tmp_path):
        monkeypatch.setattr(_tp, "_PATCHES_FILE", tmp_path / "n_existe_pas.json")
        with app.app_context():
            _tp.sync_patches_to_db()  # ne doit pas lever

    def test_json_malforme_ne_leve_pas(self, app, monkeypatch, tmp_path):
        f = tmp_path / "patches.json"
        f.write_text("{ceci n'est pas du json", encoding="utf-8")
        monkeypatch.setattr(_tp, "_PATCHES_FILE", f)
        with app.app_context():
            _tp.sync_patches_to_db()  # ne doit pas lever

    def test_json_qui_n_est_pas_une_liste_est_ignore(self, app, monkeypatch, tmp_path):
        f = tmp_path / "patches.json"
        f.write_text(json.dumps({"patch_uid": "pas-une-liste"}), encoding="utf-8")
        monkeypatch.setattr(_tp, "_PATCHES_FILE", f)
        with app.app_context():
            _tp.sync_patches_to_db()
            assert TestPatch.query.filter_by(patch_uid="pas-une-liste").first() is None

    def test_entree_sans_patch_uid_est_ignoree(self, app, monkeypatch, tmp_path):
        f = tmp_path / "patches.json"
        f.write_text(json.dumps([{"title": "Sans uid"}]), encoding="utf-8")
        monkeypatch.setattr(_tp, "_PATCHES_FILE", f)
        with app.app_context():
            before = TestPatch.query.count()
            _tp.sync_patches_to_db()
            assert TestPatch.query.count() == before

    def test_fixed_at_invalide_est_mis_a_none_sans_lever(self, app, monkeypatch, tmp_path):
        uid = "2026-09-10-test-69-fixed-at-invalide"
        f = tmp_path / "patches.json"
        f.write_text(json.dumps([{
            "patch_uid": uid, "title": "Fixed_at invalide",
            "fixed_at": "pas-une-date",
        }]), encoding="utf-8")
        monkeypatch.setattr(_tp, "_PATCHES_FILE", f)
        with app.app_context():
            try:
                _tp.sync_patches_to_db()
                p = TestPatch.query.filter_by(patch_uid=uid).first()
                assert p is not None
                assert p.fixed_at is None
            finally:
                TestPatch.query.filter_by(patch_uid=uid).delete()
                db.session.commit()

    def test_entree_valide_est_upsertee(self, app, monkeypatch, tmp_path):
        uid = "2026-09-10-test-69-upsert"
        f = tmp_path / "patches.json"
        entry = {
            "patch_uid": uid, "title": "Titre initial",
            "node_ids": ["tests/test_69_panel_internals.py::test_a"],
            "page_slug": "panel_internals", "failure_reason": "r",
            "was_real_bug": False, "root_cause": "test_quality",
            "error": "e", "fix_description": "f",
            "files_changed": ["tests/test_69_panel_internals.py"],
            "author": "routine", "fixed_at": "2026-09-10T10:00:00",
        }
        f.write_text(json.dumps([entry]), encoding="utf-8")
        monkeypatch.setattr(_tp, "_PATCHES_FILE", f)
        with app.app_context():
            try:
                _tp.sync_patches_to_db()
                p = TestPatch.query.filter_by(patch_uid=uid).first()
                assert p.title == "Titre initial"
                assert p.was_real_bug is False
                assert p.fixed_at == datetime(2026, 9, 10, 10, 0, 0)

                # Ré-application avec un titre modifié : upsert, pas de doublon.
                entry["title"] = "Titre mis à jour"
                f.write_text(json.dumps([entry]), encoding="utf-8")
                _tp.sync_patches_to_db()
                assert TestPatch.query.filter_by(patch_uid=uid).count() == 1
                assert TestPatch.query.filter_by(patch_uid=uid).first().title == "Titre mis à jour"
            finally:
                TestPatch.query.filter_by(patch_uid=uid).delete()
                db.session.commit()


# ---------------------------------------------------------------------------
# _patches_for_nodes / _patch_to_dict / _patch_category_counts
# ---------------------------------------------------------------------------

class TestPatchesForNodes:

    def test_ne_retourne_que_les_patchs_dont_un_node_id_correspond(self, app):
        with app.app_context():
            p_match = TestPatch(
                patch_uid="2026-09-10-test-69-match", title="Match",
                node_ids=json.dumps(["tests/test_69_panel_internals.py::test_cible"]),
                root_cause="app_bug",
            )
            p_no_match = TestPatch(
                patch_uid="2026-09-10-test-69-no-match", title="No match",
                node_ids=json.dumps(["tests/autre_fichier.py::test_autre"]),
                root_cause="app_bug",
            )
            db.session.add_all([p_match, p_no_match])
            db.session.commit()
            try:
                found = _tp._patches_for_nodes(["tests/test_69_panel_internals.py::test_cible"])
                found_uids = {p.patch_uid for p in found}
                assert "2026-09-10-test-69-match" in found_uids
                assert "2026-09-10-test-69-no-match" not in found_uids
            finally:
                db.session.delete(p_match)
                db.session.delete(p_no_match)
                db.session.commit()


class TestPatchToDict:

    def test_expose_les_champs_attendus_par_le_template(self, app):
        with app.app_context():
            p = TestPatch(
                patch_uid="2026-09-10-test-69-to-dict", title="Titre",
                node_ids=json.dumps(["tests/x.py::test_x"]),
                page_slug="panel_internals", failure_reason="raison",
                was_real_bug=True, root_cause="app_bug", error="erreur",
                fix_description="fix", files_changed=json.dumps(["Code/routes/test_panel.py"]),
                author="claude", fixed_at=datetime(2026, 9, 10, 12, 30),
            )
            db.session.add(p)
            db.session.commit()
            try:
                d = _tp._patch_to_dict(p)
                assert d["patch_uid"] == "2026-09-10-test-69-to-dict"
                assert d["node_ids"] == ["tests/x.py::test_x"]
                assert d["files_changed"] == ["Code/routes/test_panel.py"]
                assert d["was_real_bug"] is True
                assert d["fixed_at"] == "10/09/26 12:30"
            finally:
                db.session.delete(p)
                db.session.commit()


class TestPatchCategoryCounts:

    class _FauxPatch:
        def __init__(self, root_cause):
            self.root_cause = root_cause

    def test_compte_chaque_categorie_connue(self):
        patches = [self._FauxPatch("app_bug"), self._FauxPatch("app_bug"),
                   self._FauxPatch("test_isolation"), self._FauxPatch("test_quality")]
        counts = _tp._patch_category_counts(patches)
        assert counts["app_bug"] == 2
        assert counts["test_isolation"] == 1
        assert counts["test_quality"] == 1
        assert counts["other"] == 0

    def test_categorie_inconnue_tombe_dans_other(self):
        patches = [self._FauxPatch("root_cause_inconnue"), self._FauxPatch(None)]
        counts = _tp._patch_category_counts(patches)
        assert counts["other"] == 2


# ---------------------------------------------------------------------------
# _recent_runs
# ---------------------------------------------------------------------------

class TestRecentRuns:

    def test_calcule_pct_total_et_duree_du_run(self, app):
        with app.app_context():
            started = datetime(2026, 9, 10, 9, 0, 0)
            finished = started + timedelta(seconds=12)
            run = TestRun(scope="page:panel_internals_69", status="done",
                           started_at=started, finished_at=finished)
            db.session.add(run)
            db.session.flush()

            page = TestPage(slug="page_69_recent", title="Page 69 recent",
                             file_name="test_69_panel_internals.py")
            db.session.add(page)
            db.session.flush()
            case1 = TestCase(page_id=page.id, node_id="tests/t.py::c1", name="c1")
            case2 = TestCase(page_id=page.id, node_id="tests/t.py::c2", name="c2")
            db.session.add_all([case1, case2])
            db.session.flush()
            db.session.add_all([
                TestResult(run_id=run.id, case_id=case1.id, status="passed", duration=0.1),
                TestResult(run_id=run.id, case_id=case2.id, status="failed", duration=0.2),
            ])
            db.session.commit()
            try:
                runs = _tp._recent_runs(limit=200)
                entry = next(r for r in runs if r["id"] == run.id)
                assert entry["total"] == 2
                assert entry["passed"] == 1
                assert entry["failed"] == 1
                assert entry["pct"] == 50
                assert entry["duration_s"] == 12.0
                assert entry["scope"] == "page:panel_internals_69"
            finally:
                TestResult.query.filter_by(run_id=run.id).delete()
                db.session.delete(case1)
                db.session.delete(case2)
                db.session.delete(page)
                db.session.delete(run)
                db.session.commit()
