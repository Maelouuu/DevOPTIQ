# tests/test_152_panel_admin_residuel.py
"""
Page : Panel de Tests — routes d'administration et branches résiduelles.

Les fichiers 37, 65, 69, 123 et 131 couvrent l'essentiel du panel. Restaient
sans aucun test :

- `/testpanel/admin/clone_entity` : la copie profonde d'une entité. Écrire ces
  tests a révélé trois défauts — `= ANY(:ids)` (PostgreSQL seulement) faisait
  tomber en 500 toute copie d'une entité ayant des activités sur SQLite ; une
  entité inconnue répondait 500 au lieu de 404 ; une cible absente levait un
  `TypeError` non rattrapé (500 HTML) au lieu d'un 400.
- `/testpanel/admin/migrate_entities` (simulation et exécution).
- des branches défensives des fonctions internes : marqueur `pytestmark` en
  liste, fichier de test illisible, cas JUnit en `<error>`, base injoignable,
  chemin PostgreSQL de `_save_results` et de `run_status`, runs périmés.

Toutes les données sont dédiées et nettoyées (base partagée, scope=session).
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine as _vrai_create_engine

import Code.routes.test_panel as _tp
from Code.extensions import db
from Code.models.models import (Activities, Aptitude, Competency, Constraint,
                                Data, Entity, Link, Performance, Role, Savoir,
                                SavoirFaire, Softskill, Task, Tool, User,
                                activity_roles, task_roles, task_tools)
from Code.models.test_models import (TestCase, TestPage, TestPatch, TestResult,
                                     TestRun)

pytestmark = pytest.mark.test_panel


def _marque():
    return "z152_" + uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Outils : entités jetables pour la copie
# ---------------------------------------------------------------------------

def _purger_entite(eid):
    ent = db.session.get(Entity, eid)
    if ent is None:
        return
    act_ids = [a.id for a in Activities.query.filter_by(entity_id=eid).all()]
    task_ids = [t.id for t in Task.query.filter(Task.activity_id.in_(act_ids)).all()] if act_ids else []
    if task_ids:
        db.session.execute(task_roles.delete().where(task_roles.c.task_id.in_(task_ids)))
        db.session.execute(task_tools.delete().where(task_tools.c.task_id.in_(task_ids)))
    if act_ids:
        db.session.execute(activity_roles.delete().where(activity_roles.c.activity_id.in_(act_ids)))
    for lk in Link.query.filter_by(entity_id=eid).all():
        Performance.query.filter_by(link_id=lk.id).delete()
        db.session.delete(lk)
    db.session.flush()
    for a in Activities.query.filter_by(entity_id=eid).all():
        db.session.delete(a)
    for model in (Tool, Data, Role):
        for o in model.query.filter_by(entity_id=eid).all():
            db.session.delete(o)
    db.session.flush()
    db.session.delete(ent)
    db.session.commit()


@pytest.fixture
def entites(app):
    """Une source et une cible vides, supprimées avec tout leur contenu."""
    with app.app_context():
        m = _marque()
        src = Entity(name=m + "_source")
        cible = Entity(name=m + "_cible")
        db.session.add_all([src, cible])
        db.session.commit()
        ids = {"source": src.id, "cible": cible.id, "marque": m}
    yield ids
    with app.app_context():
        db.session.rollback()
        _purger_entite(ids["cible"])
        _purger_entite(ids["source"])


def _peupler_source(eid, m):
    """Une source complète : outil, activité garnie, tâche, rôle, donnée, lien."""
    role = Role(name=m + "_role")
    outil = Tool(entity_id=eid, name=m + "_outil")
    db.session.add_all([role, outil])
    db.session.flush()
    act = Activities(entity_id=eid, shape_id="s1", name=m + "_act",
                     description="desc", is_result=False,
                     duration_minutes=12, delay_minutes=3)
    db.session.add(act)
    db.session.flush()
    db.session.add_all([
        Competency(description="comp", activity_id=act.id),
        Savoir(description="savoir", activity_id=act.id),
        SavoirFaire(description="sf", activity_id=act.id),
        Aptitude(description="apt", activity_id=act.id),
        Softskill(habilete="Écoute", niveau="2", justification="j", activity_id=act.id),
        Constraint(description="contrainte", activity_id=act.id),
    ])
    tache = Task(name=m + "_tache", description="t", order=1, activity_id=act.id,
                 duration_minutes=5, delay_minutes=1)
    db.session.add(tache)
    db.session.flush()
    db.session.execute(activity_roles.insert().values(
        activity_id=act.id, role_id=role.id, status="Garant"))
    db.session.execute(task_roles.insert().values(
        task_id=tache.id, role_id=role.id, status="Réalisateur"))
    db.session.execute(task_tools.insert().values(task_id=tache.id, tool_id=outil.id))
    donnee = Data(entity_id=eid, shape_id="d1", name=m + "_donnee", type="nourrissante")
    db.session.add(donnee)
    db.session.flush()
    lien = Link(entity_id=eid, source_data_id=donnee.id, target_activity_id=act.id,
                type="nourrissante", choice_label="Oui")
    db.session.add(lien)
    db.session.flush()
    db.session.add(Performance(name="perf", description="pd", link_id=lien.id))
    db.session.commit()
    return role.id


def _cloner(client, **corps):
    return client.post("/testpanel/admin/clone_entity", json=corps)


# ---------------------------------------------------------------------------
# /admin/clone_entity
# ---------------------------------------------------------------------------

class TestCloneEntityValidation:

    def test_cible_absente_renvoie_400(self, client):
        r = _cloner(client, source_id=1)
        assert r.status_code == 400
        assert r.get_json()["ok"] is False

    def test_cible_non_entiere_renvoie_400(self, client):
        r = _cloner(client, source_id=1, target_id="abc")
        assert r.status_code == 400

    def test_corps_absent_renvoie_400(self, client):
        r = client.post("/testpanel/admin/clone_entity", data="pas du json",
                        content_type="text/plain")
        assert r.status_code == 400

    def test_source_inconnue_renvoie_404(self, client, entites):
        r = _cloner(client, source_id=99999999, target_id=entites["cible"])
        assert r.status_code == 404

    def test_cible_inconnue_renvoie_404(self, client, entites):
        r = _cloner(client, source_id=entites["source"], target_id=99999999)
        assert r.status_code == 404


class TestCloneEntityCopie:

    def test_source_vide_donne_des_compteurs_a_zero(self, client, entites):
        r = _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        assert r.status_code == 200
        corps = r.get_json()
        assert corps["ok"] is True
        assert (corps["activities"], corps["tasks"], corps["tools"],
                corps["data_shapes"], corps["links"], corps["roles"]) == (0, 0, 0, 0, 0, 0)

    def test_noms_source_et_cible_sont_renvoyes(self, client, entites):
        corps = _cloner(client, source_id=entites["source"],
                        target_id=entites["cible"]).get_json()
        assert corps["source"] == entites["marque"] + "_source"
        assert corps["target"] == entites["marque"] + "_cible"

    def test_copie_complete_renvoie_les_compteurs(self, app, client, entites):
        with app.app_context():
            _peupler_source(entites["source"], entites["marque"])
        corps = _cloner(client, source_id=entites["source"],
                        target_id=entites["cible"]).get_json()
        assert corps["ok"] is True, corps.get("error")
        assert (corps["activities"], corps["tasks"], corps["tools"],
                corps["data_shapes"], corps["links"], corps["roles"]) == (1, 1, 1, 1, 1, 1)

    def test_copie_reprend_le_contenu_de_l_activite(self, app, client, entites):
        with app.app_context():
            _peupler_source(entites["source"], entites["marque"])
        _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        with app.app_context():
            act = Activities.query.filter_by(entity_id=entites["cible"]).one()
            assert act.name == entites["marque"] + "_act"
            assert (act.duration_minutes, act.delay_minutes) == (12, 3)
            assert [c.description for c in act.competencies] == ["comp"]
            assert [s.description for s in act.savoirs] == ["savoir"]
            assert [s.description for s in act.savoir_faires] == ["sf"]
            assert [a.description for a in act.aptitudes] == ["apt"]
            assert [(s.habilete, s.niveau) for s in act.softskills] == [("Écoute", "2")]
            assert [c.description for c in act.constraints] == ["contrainte"]

    def test_copie_reprend_les_roles_communs_sans_en_creer(self, app, client, entites):
        with app.app_context():
            role_id = _peupler_source(entites["source"], entites["marque"])
            nb_roles = Role.query.count()
        _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        with app.app_context():
            assert Role.query.count() == nb_roles
            act = Activities.query.filter_by(entity_id=entites["cible"]).one()
            lignes = db.session.execute(activity_roles.select().where(
                activity_roles.c.activity_id == act.id)).fetchall()
            assert [(l.role_id, l.status) for l in lignes] == [(role_id, "Garant")]

    def test_copie_rattache_role_et_outil_a_la_nouvelle_tache(self, app, client, entites):
        with app.app_context():
            role_id = _peupler_source(entites["source"], entites["marque"])
        _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        with app.app_context():
            act = Activities.query.filter_by(entity_id=entites["cible"]).one()
            tache = Task.query.filter_by(activity_id=act.id).one()
            outil = Tool.query.filter_by(entity_id=entites["cible"]).one()
            tr = db.session.execute(task_roles.select().where(
                task_roles.c.task_id == tache.id)).fetchall()
            tt = db.session.execute(task_tools.select().where(
                task_tools.c.task_id == tache.id)).fetchall()
            assert [(l.role_id, l.status) for l in tr] == [(role_id, "Réalisateur")]
            assert [l.tool_id for l in tt] == [outil.id]

    def test_copie_rebranche_le_lien_et_sa_performance(self, app, client, entites):
        with app.app_context():
            _peupler_source(entites["source"], entites["marque"])
        _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        with app.app_context():
            cible = entites["cible"]
            act = Activities.query.filter_by(entity_id=cible).one()
            donnee = Data.query.filter_by(entity_id=cible).one()
            lien = Link.query.filter_by(entity_id=cible).one()
            assert donnee.shape_id == f"d1_e{cible}"
            assert (lien.source_data_id, lien.target_activity_id) == (donnee.id, act.id)
            assert lien.choice_label == "Oui"
            assert lien.performance.name == "perf"

    def test_copie_laisse_la_source_intacte(self, app, client, entites):
        with app.app_context():
            _peupler_source(entites["source"], entites["marque"])
        _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        with app.app_context():
            assert Activities.query.filter_by(entity_id=entites["source"]).count() == 1
            assert Link.query.filter_by(entity_id=entites["source"]).count() == 1

    def test_les_donnees_partielles_de_la_cible_sont_effacees(self, app, client, entites):
        with app.app_context():
            cible = entites["cible"]
            vieux_role = Role(entity_id=cible, name=entites["marque"] + "_vieux_role")
            act = Activities(entity_id=cible, name=entites["marque"] + "_vieille_act")
            db.session.add_all([
                vieux_role, act,
                Tool(entity_id=cible, name="vieil outil"),
            ])
            db.session.flush()
            donnee = Data(entity_id=cible, name="vieille donnée", type="nourrissante")
            db.session.add(donnee)
            db.session.flush()
            db.session.add(Link(entity_id=cible, source_data_id=donnee.id,
                                target_activity_id=act.id, type="nourrissante"))
            db.session.commit()
        r = _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        assert r.status_code == 200
        with app.app_context():
            cible = entites["cible"]
            for model in (Activities, Role, Tool, Data, Link):
                assert model.query.filter_by(entity_id=cible).count() == 0, model.__name__

    def test_erreur_en_cours_de_copie_est_annulee_et_renvoie_500(self, app, client, entites, monkeypatch):
        with app.app_context():
            act = Activities(entity_id=entites["cible"], name=entites["marque"] + "_garde")
            db.session.add(act)
            db.session.commit()

        class _Requete:
            def filter_by(self, **_):
                raise RuntimeError("panne simulée")

        monkeypatch.setattr(Tool, "query", _Requete())
        r = _cloner(client, source_id=entites["source"], target_id=entites["cible"])
        monkeypatch.undo()
        assert r.status_code == 500
        corps = r.get_json()
        assert corps["ok"] is False and "panne simulée" in corps["error"]
        with app.app_context():
            # Rien n'a été effacé : le nettoyage préalable a été annulé.
            assert Activities.query.filter_by(entity_id=entites["cible"]).count() == 1


# ---------------------------------------------------------------------------
# /admin/migrate_entities
# ---------------------------------------------------------------------------

_MAEL = "mael.pierre.girardin@icloud.com"
_HUBERT = "h.grandjean@afdec.fr"


@pytest.fixture
def comptes_migration(app):
    """Les deux comptes attendus par la migration, retirés ensuite avec ce
    qu'elle a créé ; les entités orphelines reprennent leur état d'origine."""
    with app.app_context():
        ent = db.session.get(Entity, 1)
        crees = []
        for email in (_MAEL, _HUBERT):
            if not User.query.filter_by(email=email).first():
                u = User(entity_id=ent.id, first_name="M", last_name="152",
                         email=email, password="x", status="user")
                db.session.add(u)
                crees.append(email)
        db.session.commit()
        orphelines = [e.id for e in Entity.query.filter_by(owner_id=None).all()]
        avant = {e.id for e in Entity.query.all()}
    yield {"orphelines": orphelines}
    with app.app_context():
        db.session.rollback()
        for eid in orphelines:
            e = db.session.get(Entity, eid)
            if e:
                e.owner_id = None
        for e in Entity.query.all():
            if e.id not in avant:
                db.session.delete(e)
        db.session.flush()
        for email in crees:
            User.query.filter_by(email=email).delete()
        db.session.commit()


class TestMigrateEntities:

    def test_compte_mael_absent_renvoie_404(self, app, client):
        with app.app_context():
            assert User.query.filter_by(email=_MAEL).first() is None
        r = client.get("/testpanel/admin/migrate_entities")
        assert r.status_code == 404
        assert _MAEL in r.get_json()["error"]

    def test_compte_hubert_absent_renvoie_404(self, app, client):
        with app.app_context():
            assert User.query.filter_by(email=_HUBERT).first() is None
            db.session.add(User(entity_id=1, first_name="M", last_name="152",
                                email=_MAEL, password="x", status="user"))
            db.session.commit()
        try:
            r = client.get("/testpanel/admin/migrate_entities")
            assert r.status_code == 404
            assert _HUBERT in r.get_json()["error"]
        finally:
            with app.app_context():
                User.query.filter_by(email=_MAEL).delete()
                db.session.commit()

    def test_get_est_une_simulation_sans_effet(self, app, client, comptes_migration):
        with app.app_context():
            orpheline = Entity(name=_marque() + "_orpheline")
            db.session.add(orpheline)
            db.session.commit()
            oid = orpheline.id
        comptes_migration["orphelines"].append(oid)
        r = client.get("/testpanel/admin/migrate_entities")
        assert r.status_code == 200
        corps = r.get_json()
        assert corps["dry_run"] is True and "done" not in corps
        assert oid in [o["id"] for o in corps["orphans"]]
        with app.app_context():
            assert db.session.get(Entity, oid).owner_id is None

    def test_post_rattache_les_orphelines_au_premier_compte(self, app, client, comptes_migration):
        with app.app_context():
            orpheline = Entity(name=_marque() + "_orpheline")
            db.session.add(orpheline)
            db.session.commit()
            oid = orpheline.id
        comptes_migration["orphelines"].append(oid)
        corps = client.post("/testpanel/admin/migrate_entities").get_json()
        assert corps["done"] is True and corps["dry_run"] is False
        with app.app_context():
            assert db.session.get(Entity, oid).owner_id == corps["mael_id"]

    def test_post_duplique_l_entite_de_base_pour_le_second_compte(self, app, client, comptes_migration):
        with app.app_context():
            base = Entity(name=_marque() + " entité de base", description="socle",
                          owner_id=1)
            db.session.add(base)
            db.session.commit()
        corps = client.post("/testpanel/admin/migrate_entities").get_json()
        assert corps["base_entity"] is not None
        nouvelle = corps["new_entity_id"]
        assert nouvelle
        with app.app_context():
            e = db.session.get(Entity, nouvelle)
            source = db.session.get(Entity, corps["base_entity"]["id"])
            assert e.owner_id == corps["hubert_id"]
            assert e.name.startswith(source.name + " — Hubert")
            assert e.is_active is False


# ---------------------------------------------------------------------------
# Fonctions internes — branches défensives
# ---------------------------------------------------------------------------

class TestParseEtEmpreinte:

    def test_marqueur_en_liste_prend_le_premier(self, tmp_path):
        f = tmp_path / "test_9_liste.py"
        f.write_text("import pytest\npytestmark = [pytest.mark.premier, pytest.mark.second]\n"
                     "def test_a():\n    pass\n", encoding="utf-8")
        assert _tp._parse_test_file(f)["marker"] == "premier"

    def test_marqueur_en_liste_non_attribut_est_ignore(self, tmp_path):
        f = tmp_path / "test_9_liste2.py"
        f.write_text("pytestmark = ['texte']\n", encoding="utf-8")
        assert _tp._parse_test_file(f)["marker"] == ""

    def test_fichier_illisible_est_saute_par_l_empreinte(self, tmp_path, monkeypatch):
        (tmp_path / "test_1_ok.py").write_text("x = 1\n", encoding="utf-8")
        os.symlink(tmp_path / "absent.py", tmp_path / "test_2_casse.py")
        monkeypatch.setattr(_tp, "_TESTS_DIR", tmp_path)
        noms = [m[0] for m in _tp._empreinte_tests()]
        assert noms == ["test_1_ok.py"]


def _xml(tmp_path, corps):
    p = tmp_path / "res.xml"
    p.write_text(f'<?xml version="1.0"?><testsuites><testsuite>{corps}</testsuite></testsuites>',
                 encoding="utf-8")
    return str(p)


@pytest.fixture
def cas_jetable(app):
    with app.app_context():
        m = _marque()
        page = TestPage(slug=m, title=m, file_name=f"test_{m}.py")
        db.session.add(page)
        db.session.flush()
        node = f"tests/test_{m}.py::Classe::test_x"
        cas = TestCase(page_id=page.id, node_id=node, class_name="Classe", name="test_x")
        run = TestRun(scope="all", status="running")
        db.session.add_all([cas, run])
        db.session.commit()
        ids = {"m": m, "page": page.id, "cas": cas.id, "run": run.id, "node": node}
    yield ids
    with app.app_context():
        TestResult.query.filter_by(run_id=ids["run"]).delete()
        TestRun.query.filter_by(id=ids["run"]).delete()
        TestCase.query.filter_by(id=ids["cas"]).delete()
        TestPage.query.filter_by(id=ids["page"]).delete()
        db.session.commit()


class TestSaveResultsBranches:

    def test_cas_en_error_est_enregistre_avec_son_message(self, app, tmp_path, cas_jetable):
        m = cas_jetable["m"]
        xml = _xml(tmp_path, f'<testcase classname="tests.test_{m}.Classe" name="test_x" time="0.5">'
                             '<error message="fixture cassée">trace</error></testcase>')
        with app.app_context():
            _tp._save_results(app.config["SQLALCHEMY_DATABASE_URI"], cas_jetable["run"], xml,
                              lambda l: None)
            db.session.expire_all()
            res = TestResult.query.filter_by(run_id=cas_jetable["run"]).one()
            assert res.status == "error"
            assert "fixture cassée" in res.message and "trace" in res.message

    def test_classname_sans_module_de_test_est_ignore(self, app, tmp_path, cas_jetable):
        xml = _xml(tmp_path, '<testcase classname="autre.chose" name="test_x" time="0"/>')
        lignes = []
        with app.app_context():
            _tp._save_results(app.config["SQLALCHEMY_DATABASE_URI"], cas_jetable["run"], xml,
                              lignes.append)
            assert TestResult.query.filter_by(run_id=cas_jetable["run"]).count() == 0
        assert any("0/0" in l for l in lignes)

    def test_base_sqlite_injoignable_emet_une_erreur_sans_lever(self, tmp_path):
        xml = _xml(tmp_path, '<testcase classname="tests.test_a" name="test_b" time="0"/>')
        lignes = []
        _tp._save_results(f"sqlite:///{tmp_path}/dossier/absent/x.db", 1, xml, lignes.append)
        assert any("DB ERROR sqlite3" in l for l in lignes)

    def test_chemin_postgresql_persiste_les_resultats(self, app, tmp_path, cas_jetable, monkeypatch):
        url = app.config["SQLALCHEMY_DATABASE_URI"]
        import sqlalchemy
        monkeypatch.setattr(sqlalchemy, "create_engine",
                            lambda *_a, **_k: _vrai_create_engine(url))
        m = cas_jetable["m"]
        xml = _xml(tmp_path,
                   f'<testcase classname="tests.test_{m}.Classe" name="test_x" time="0.1"/>'
                   '<testcase classname="tests.test_inconnu" name="test_y" time="0"/>')
        lignes = []
        _tp._save_results("postgresql://faux/base", cas_jetable["run"], xml, lignes.append)
        assert any("2 résultats sauvegardés" in l for l in lignes)
        with app.app_context():
            db.session.expire_all()
            assert db.session.get(TestRun, cas_jetable["run"]).status == "done"
            assert db.session.get(TestCase, cas_jetable["cas"]).last_status == "passed"
            assert TestResult.query.filter_by(run_id=cas_jetable["run"]).count() == 1

    def test_chemin_postgresql_en_panne_emet_une_erreur(self, tmp_path, monkeypatch):
        import sqlalchemy

        class _Moteur:
            def connect(self):
                raise RuntimeError("serveur muet")

            def dispose(self):
                _Moteur.libere = True

        monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_a, **_k: _Moteur())
        xml = _xml(tmp_path, '<testcase classname="tests.test_a" name="test_b" time="0"/>')
        lignes = []
        _tp._save_results("postgresql://faux/base", 1, xml, lignes.append)
        assert any("DB ERROR postgresql" in l for l in lignes)
        assert _Moteur.libere is True


class _FauxPopen:
    def __init__(self, *a, **k):
        import io
        self.stdout = io.StringIO("")

    def wait(self):
        return 0


class TestExecuterRunBranches:

    def test_xml_impossible_a_supprimer_n_interrompt_pas_le_run(self, app, monkeypatch):
        run_id = 15200001
        monkeypatch.setattr(_tp.subprocess, "Popen", _FauxPopen)
        monkeypatch.setattr(_tp, "_save_results", lambda *a: None)
        monkeypatch.setattr(_tp, "_build_args", lambda scope, xml: ["py", "-m", "pytest"])

        def _refus(_p):
            raise OSError("verrouillé")

        crees = []
        vrai_mkstemp = _tp.tempfile.mkstemp

        def _mkstemp(*a, **k):
            fd, chemin = vrai_mkstemp(*a, **k)
            crees.append(chemin)
            return fd, chemin

        monkeypatch.setattr(_tp.tempfile, "mkstemp", _mkstemp)
        monkeypatch.setattr(_tp.os, "unlink", _refus)
        with _tp._runs_lock:
            _tp._runs[run_id] = {"lines": [], "done": False}
        try:
            _tp._executer_run(run_id, "all", app, lambda l: None)
            with _tp._runs_lock:
                assert _tp._runs[run_id]["done"] is True
        finally:
            monkeypatch.undo()
            for chemin in crees:
                os.unlink(chemin)
            with _tp._runs_lock:
                _tp._runs.pop(run_id, None)

    def test_sans_xml_base_injoignable_reste_silencieux(self, app, monkeypatch, tmp_path):
        monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI",
                            f"sqlite:///{tmp_path}/absent/dossier/x.db")
        monkeypatch.setattr(_tp.subprocess, "Popen", _FauxPopen)
        monkeypatch.setattr(_tp, "_build_args", lambda scope, xml: ["py", "-m", "pytest"])
        monkeypatch.setattr(_tp.os.path, "exists", lambda p: False)
        lignes = []
        _tp._executer_run(15200002, "all", app, lignes.append)
        assert not any("ERROR" in l for l in lignes)


class TestRunsPerimes:

    def test_run_bloque_depuis_plus_de_15_minutes_est_clos(self, app):
        with app.app_context():
            vieux = TestRun(scope="all", status="running",
                            started_at=datetime.utcnow() - timedelta(minutes=20))
            recent = TestRun(scope="all", status="running")
            db.session.add_all([vieux, recent])
            db.session.commit()
            ids = (vieux.id, recent.id)
            try:
                _tp._expire_stale_runs()
                db.session.expire_all()
                assert db.session.get(TestRun, ids[0]).status == "done"
                assert db.session.get(TestRun, ids[1]).status == "running"
            finally:
                TestRun.query.filter(TestRun.id.in_(ids)).delete(synchronize_session=False)
                db.session.commit()


class TestRunStatusPostgres:

    def _passer_en_postgres(self, app, monkeypatch):
        monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI", "postgresql://faux/base")

    def test_run_inconnu_renvoie_404(self, app, client, monkeypatch):
        self._passer_en_postgres(app, monkeypatch)
        r = client.get("/testpanel/run/99999999/status")
        assert r.status_code == 404 and r.get_json()["status"] == "unknown"

    def test_run_termine_expose_son_taux(self, app, client, cas_jetable, monkeypatch):
        with app.app_context():
            run = db.session.get(TestRun, cas_jetable["run"])
            run.status = "done"
            run.finished_at = datetime(2026, 1, 2, 3, 4, 5)
            db.session.add(TestResult(run_id=run.id, case_id=cas_jetable["cas"],
                                      status="passed", duration=0.1))
            db.session.commit()
        self._passer_en_postgres(app, monkeypatch)
        corps = client.get(f"/testpanel/run/{cas_jetable['run']}/status").get_json()
        assert corps == {"status": "done", "total": 1, "passed": 1, "pct": 100,
                         "finished_at": "2026-01-02T03:04:05"}

    def test_run_sans_resultat_donne_0_pour_cent(self, app, client, cas_jetable, monkeypatch):
        self._passer_en_postgres(app, monkeypatch)
        corps = client.get(f"/testpanel/run/{cas_jetable['run']}/status").get_json()
        assert corps["total"] == 0 and corps["pct"] == 0 and corps["finished_at"] is None

    def test_sqlite_injoignable_renvoie_500(self, app, client, monkeypatch, tmp_path):
        monkeypatch.setitem(app.config, "SQLALCHEMY_DATABASE_URI",
                            f"sqlite:///{tmp_path}/absent/x.db")
        r = client.get("/testpanel/run/1/status")
        assert r.status_code == 500 and r.get_json()["status"] == "error"


class TestEcransBranches:

    def test_barre_laterale_en_panne_reste_vide(self, auth_client, monkeypatch):
        class _Requete:
            def order_by(self, *_):
                raise RuntimeError("base muette")

        monkeypatch.setattr(TestPage, "query", _Requete())
        with auth_client.application.test_request_context("/testpanel/journal"):
            ctx = _tp._inject_nav()
        assert ctx == {"nav_pages": [], "nav_global_pct": 0}

    def test_synchro_en_panne_n_empeche_pas_l_affichage(self, auth_client, monkeypatch):
        def _panne(*_a, **_k):
            raise RuntimeError("disque plein")

        monkeypatch.setattr(_tp, "sync_tests_to_db", _panne)
        assert auth_client.get("/testpanel/journal").status_code == 200

    def test_page_detail_liste_les_patchs_par_slug_et_par_cas(self, app, auth_client, cas_jetable):
        m = cas_jetable["m"]
        with app.app_context():
            par_cas = TestPatch(patch_uid=m + "-cas", title="Patch par cas",
                                node_ids=json.dumps([cas_jetable["node"]]), page_slug="autre")
            par_slug = TestPatch(patch_uid=m + "-slug", title="Patch par slug",
                                 node_ids=json.dumps([]), page_slug=m)
            db.session.add_all([par_cas, par_slug])
            db.session.commit()
        try:
            r = auth_client.get(f"/testpanel/page/{m}")
            assert r.status_code == 200
            html = r.get_data(as_text=True)
            assert "Patch par cas" in html and "Patch par slug" in html
        finally:
            with app.app_context():
                TestPatch.query.filter(TestPatch.patch_uid.like(m + "%")).delete(
                    synchronize_session=False)
                db.session.commit()

    def test_tableau_de_bord_trace_l_historique_d_un_run_complet(self, app, auth_client, cas_jetable):
        with app.app_context():
            run = db.session.get(TestRun, cas_jetable["run"])
            run.status = "done"
            run.finished_at = datetime.utcnow()
            db.session.add(TestResult(run_id=run.id, case_id=cas_jetable["cas"],
                                      status="passed", duration=0.1))
            db.session.commit()
        assert auth_client.get("/testpanel/").status_code == 200

    def test_compteur_de_journal_illisible_est_ramene_a_zero(self, auth_client, tmp_path, monkeypatch):
        f = tmp_path / "journal.json"
        f.write_text(json.dumps({"plan": {}, "entries": [
            {"new_tests": "beaucoup", "tests_fixed": None, "patches": [1]}]}), encoding="utf-8")
        monkeypatch.setattr(_tp, "_JOURNAL_FILE", f)
        r = auth_client.get("/testpanel/journal")
        assert r.status_code == 200
