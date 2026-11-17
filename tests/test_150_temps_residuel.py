# -*- coding: utf-8 -*-
"""Page : Gestion du Temps (/temps) — couverture résiduelle de time_view.py.

Ce que la suite ne touchait pas encore :
  * les tables historiques de paramètres (`company_params`, `gestion_rh_params`)
    lues en repli quand `entreprise_settings` est vide ou illisible ;
  * le pourcentage de probabilité invalide ou nul (`_lire_pct`) ;
  * l'auto-patch de schéma des analyses de rôle (`ensure_time_role_schema`) ;
  * le changement de rôle d'une analyse (PATCH role_id) ;
  * la relecture et la modification d'une faiblesse saisie PAR TÂCHES ;
  * le tableau de bord avec une analyse de rôle et un projet sur la carto active.

Chaque test crée ses propres données sur l'entité du seed, force l'entité
active, et nettoie tout en sortant.
"""
import json
import uuid

import pytest

from Code.extensions import db

pytestmark = pytest.mark.time


def _uid():
    return uuid.uuid4().hex[:8]


def _json(c, method, url, body=None):
    return getattr(c, method)(url, data=json.dumps(body or {}),
                              content_type="application/json")


@pytest.fixture()
def carto(app, auth_client, ids):
    """Deux activités et deux tâches sur l'entité du seed, entité forcée active."""
    from Code.models.models import (Activities, Task, TimeProject, TimeRoleAnalysis,
                                    TimeWeakness)
    with auth_client.session_transaction() as sess:
        avant = sess.get("active_entity_id")
        sess["active_entity_id"] = ids["entity_id"]
    with app.app_context():
        a1 = Activities(entity_id=ids["entity_id"], name=f"T150 A1 {_uid()}", description="")
        a2 = Activities(entity_id=ids["entity_id"], name=f"T150 A2 {_uid()}", description="")
        db.session.add_all([a1, a2])
        db.session.flush()
        t1 = Task(activity_id=a1.id, name=f"T150 tâche 1 {_uid()}")
        t2 = Task(activity_id=a1.id, name=f"T150 tâche 2 {_uid()}")
        db.session.add_all([t1, t2])
        db.session.commit()
        d = {"a1": a1.id, "a2": a2.id, "t1": t1.id, "t2": t2.id,
             "role_analyses": [], "projects": []}
    yield d
    with app.app_context():
        db.session.rollback()
        for rid in d["role_analyses"]:
            r = db.session.get(TimeRoleAnalysis, rid)
            if r is not None:
                db.session.delete(r)
        for pid in d["projects"]:
            p = db.session.get(TimeProject, pid)
            if p is not None:
                db.session.delete(p)
        TimeWeakness.query.filter(
            TimeWeakness.activity_id.in_([d["a1"], d["a2"]])).delete(synchronize_session=False)
        Task.query.filter(Task.id.in_([d["t1"], d["t2"]])).delete(synchronize_session=False)
        Activities.query.filter(
            Activities.id.in_([d["a1"], d["a2"]])).delete(synchronize_session=False)
        db.session.commit()
    with auth_client.session_transaction() as sess:
        sess["active_entity_id"] = avant if avant is not None else ids["entity_id"]


# ── Paramètres calendaires : les tables historiques ────────────────────────

class TestParametresHistoriques:

    def _table(self, app, ddl, insert):
        from sqlalchemy import text
        with app.app_context():
            db.session.execute(text(ddl))
            db.session.execute(text(insert))
            db.session.commit()

    def _drop(self, app, nom):
        from sqlalchemy import text
        with app.app_context():
            db.session.rollback()
            db.session.execute(text(f"DROP TABLE IF EXISTS {nom}"))
            db.session.commit()

    def test_company_params_est_lue_en_premier(self, app):
        from Code.routes.time_view import get_company_params
        self._table(app, "CREATE TABLE company_params (Js INTEGER, Sa INTEGER, Ja INTEGER)",
                    "INSERT INTO company_params VALUES (4, 45, 180)")
        try:
            with app.app_context():
                assert get_company_params() == {"Js": 4, "Sa": 45, "Ja": 180}
        finally:
            self._drop(app, "company_params")

    def test_company_params_valeurs_nulles_retombent_sur_les_defauts(self, app):
        from Code.routes.time_view import get_company_params
        self._table(app, "CREATE TABLE company_params (Js INTEGER, Sa INTEGER, Ja INTEGER)",
                    "INSERT INTO company_params VALUES (NULL, NULL, NULL)")
        try:
            with app.app_context():
                assert get_company_params() == {"Js": 5, "Sa": 47, "Ja": 220}
        finally:
            self._drop(app, "company_params")

    def test_gestion_rh_params_sert_de_repli(self, app):
        from Code.routes.time_view import get_company_params
        self._table(app, "CREATE TABLE gestion_rh_params "
                         "(days_per_week INTEGER, weeks_per_year INTEGER, days_per_year INTEGER)",
                    "INSERT INTO gestion_rh_params VALUES (6, 44, 250)")
        try:
            with app.app_context():
                assert get_company_params() == {"Js": 6, "Sa": 44, "Ja": 250}
        finally:
            self._drop(app, "gestion_rh_params")

    def test_sans_aucune_table_historique_les_defauts(self, app):
        from Code.routes.time_view import get_company_params
        with app.app_context():
            assert get_company_params() == {"Js": 5, "Sa": 47, "Ja": 220}

    def test_entreprise_settings_illisible_retombe_sur_company_params(self, app, monkeypatch):
        """Une table `entreprise_settings` qui lève : rollback, puis repli sur
        les paramètres historiques — jamais une erreur 500 sur la page Temps."""
        from Code.models import models
        from Code.routes.time_view import get_calendar_params

        class _Illisible:
            def __getattr__(self, _nom):
                raise RuntimeError("table illisible")

        monkeypatch.setattr(models.EntrepriseSettings, "query", _Illisible())
        with app.app_context():
            p = get_calendar_params()
        assert p["hours_per_day"] == 7.0
        assert p["days_per_week"] == 5
        assert p["weeks_per_year"] == 47


# ── Pourcentage de probabilité ─────────────────────────────────────────────

class TestLirePourcentage:

    @pytest.mark.parametrize("brut", ["abc", [1, 2], {"x": 1}])
    def test_valeur_non_numerique_ignoree(self, brut):
        from Code.routes.time_view import _lire_pct
        assert _lire_pct({"N_prob_pct": brut}) is None

    @pytest.mark.parametrize("brut", [0, "0", -5, "-0.1"])
    def test_valeur_nulle_ou_negative_ignoree(self, brut):
        from Code.routes.time_view import _lire_pct
        assert _lire_pct({"N_prob_pct": brut}) is None

    def test_valeur_plafonnee_a_100(self):
        from Code.routes.time_view import _lire_pct
        assert _lire_pct({"N_prob_pct": 250}) == 100.0

    def test_valeur_decimale_texte_acceptee(self):
        from Code.routes.time_view import _lire_pct
        assert _lire_pct({"N_prob_pct": "12.5"}) == 12.5


# ── Auto-patch du schéma des analyses de rôle ──────────────────────────────

class _SessionFactice:
    """Remplace db.session.execute : PRAGMA rend des colonnes choisies, les
    ALTER sont enregistrés au lieu d'être joués."""

    def __init__(self, cols_ra, cols_rl, lever=False):
        self.cols = {"time_role_analysis": cols_ra, "time_role_line": cols_rl}
        self.alters = []
        self.lever = lever
        self.commits = 0
        self.rollbacks = 0

    def execute(self, stmt, *a, **kw):
        sql = str(stmt)
        if self.lever:
            raise RuntimeError("base indisponible")
        if sql.startswith("PRAGMA"):
            nom = sql.split("(")[1].rstrip(")")
            lignes = [(i, c) for i, c in enumerate(self.cols[nom])]
            return type("R", (), {"fetchall": lambda _s: lignes})()
        self.alters.append(sql)
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class TestSchemaRoleAutoPatch:

    def _jouer(self, app, monkeypatch, fausse):
        from Code.routes import time_view
        with app.app_context():
            monkeypatch.setattr(time_view.db, "session", fausse)
            time_view.ensure_time_role_schema()
            monkeypatch.undo()

    def test_colonnes_manquantes_ajoutees(self, app, monkeypatch):
        fausse = _SessionFactice(["id", "role_id"], ["id", "activity_id"])
        self._jouer(app, monkeypatch, fausse)
        joue = " | ".join(fausse.alters)
        assert "time_role_analysis ADD COLUMN name" in joue
        assert "time_role_analysis ADD COLUMN created_at" in joue
        assert "time_role_line ADD COLUMN duration_minutes" in joue
        assert fausse.commits == 1

    def test_schema_complet_aucun_alter(self, app, monkeypatch):
        fausse = _SessionFactice(["id", "role_id", "name", "created_at"],
                                 ["id", "duration_minutes"])
        self._jouer(app, monkeypatch, fausse)
        assert fausse.alters == []
        assert fausse.commits == 1

    def test_tables_absentes_aucun_alter(self, app, monkeypatch):
        fausse = _SessionFactice([], [])
        self._jouer(app, monkeypatch, fausse)
        assert fausse.alters == []

    def test_erreur_base_fait_un_rollback(self, app, monkeypatch):
        fausse = _SessionFactice([], [], lever=True)
        self._jouer(app, monkeypatch, fausse)
        assert fausse.rollbacks == 1
        assert fausse.commits == 0


# ── Analyse de rôle : changement de rôle ───────────────────────────────────

class TestAnalyseRoleChangementDeRole:

    def _role(self, app, ids, nom):
        from Code.models.models import Role
        with app.app_context():
            r = Role(entity_id=ids["entity_id"], name=nom)
            db.session.add(r)
            db.session.commit()
            return r.id

    def _suppr_role(self, app, *rids):
        from Code.models.models import Role
        with app.app_context():
            Role.query.filter(Role.id.in_(rids)).delete(synchronize_session=False)
            db.session.commit()

    def test_patch_role_id_rattache_l_analyse_a_un_autre_role(self, app, auth_client, ids, carto):
        r1 = self._role(app, ids, f"T150 Rôle A {_uid()}")
        r2 = self._role(app, ids, f"T150 Rôle B {_uid()}")
        try:
            rep = _json(auth_client, "post", "/temps/api/role_analysis", {
                "role_id": r1, "name": "Avant",
                "lines": [{"activity_id": carto["a1"], "duration": 10}]})
            assert rep.status_code == 200, rep.data
            rid = rep.get_json()["id"]
            carto["role_analyses"].append(rid)

            rep = _json(auth_client, "patch", f"/temps/api/role_analysis/{rid}",
                        {"role_id": r2})
            assert rep.status_code == 200
            assert rep.get_json()["name"] == "Avant"
            from Code.models.models import TimeRoleAnalysis
            with app.app_context():
                R = db.session.get(TimeRoleAnalysis, rid)
                assert R.role_id == r2
                assert len(R.lines) == 1, "sans `lines`, les lignes ne bougent pas"
        finally:
            from Code.models.models import TimeRoleAnalysis
            with app.app_context():
                for rid in list(carto["role_analyses"]):
                    R = db.session.get(TimeRoleAnalysis, rid)
                    if R is not None:
                        db.session.delete(R)
                db.session.commit()
            carto["role_analyses"].clear()
            self._suppr_role(app, r1, r2)

    def test_patch_analyse_inexistante_404(self, auth_client):
        rep = _json(auth_client, "patch", "/temps/api/role_analysis/99999999", {"role_id": 1})
        assert rep.status_code == 404


# ── Faiblesse saisie par tâches : relecture et modification ────────────────

def _faiblesse_par_taches(c, carto, libelle):
    rep = _json(c, "post", "/temps/api/weakness", {
        "mode": "tasks", "activity_id": carto["a1"], "save": True,
        "weakness": libelle, "recurrence": "hebdomadaire", "frequency": 2,
        "tasks": [
            {"task_id": carto["t1"], "duration_std": 10, "delay_std": 20},
            {"task_id": carto["t2"], "duration_std": 1, "duration_unit": "heures",
             "delay_std": 2, "delay_unit": "heures"},
        ]})
    assert rep.status_code == 200, rep.data
    from Code.models.models import TimeWeakness
    total = (TimeWeakness.query
             .filter_by(activity_id=carto["a1"], weakness=libelle, task_id=None)
             .one())
    return total.id


class TestFaiblesseParTaches:

    def test_get_rend_les_lignes_par_tache_et_le_mode_tasks(self, app, auth_client, carto):
        with app.app_context():
            wid = _faiblesse_par_taches(auth_client, carto, f"Ressaisie {_uid()}")
        rep = auth_client.get(f"/temps/api/weakness/{wid}")
        assert rep.status_code == 200
        item = rep.get_json()["item"]
        assert item["mode"] == "tasks"
        assert [t["task_id"] for t in item["tasks"]] == [carto["t1"], carto["t2"]]
        assert item["tasks"][1]["duration_std"] == 60.0
        assert item["tasks"][1]["delay_std"] == 120.0
        assert item["duration_std"] == 70.0

    def test_get_tache_supprimee_rend_un_nom_vide(self, app, auth_client, carto):
        from Code.models.models import Task
        with app.app_context():
            wid = _faiblesse_par_taches(auth_client, carto, f"Orpheline {_uid()}")
            db.session.delete(db.session.get(Task, carto["t2"]))
            db.session.commit()
        rep = auth_client.get(f"/temps/api/weakness/{wid}")
        assert rep.status_code == 200
        taches = rep.get_json()["item"]["tasks"]
        assert taches[1]["task_id"] == carto["t2"]
        assert taches[1]["task"] == ""

    def test_put_par_taches_remplace_les_anciennes_lignes(self, app, auth_client, carto):
        from Code.models.models import TimeWeakness
        ancien = f"Ancien {_uid()}"
        nouveau = f"Nouveau {_uid()}"
        with app.app_context():
            wid = _faiblesse_par_taches(auth_client, carto, ancien)
        rep = _json(auth_client, "put", f"/temps/api/weakness/{wid}", {
            "mode": "tasks", "weakness": nouveau, "recurrence": "journalier",
            "tasks": [{"task_id": carto["t1"], "duration_std": 2,
                       "duration_unit": "heures", "delay_std": 3,
                       "delay_unit": "heures"}]})
        assert rep.status_code == 200, rep.data
        with app.app_context():
            assert TimeWeakness.query.filter_by(
                activity_id=carto["a1"], weakness=ancien).count() == 0
            lignes = (TimeWeakness.query
                      .filter_by(activity_id=carto["a1"], weakness=nouveau)
                      .filter(TimeWeakness.task_id.isnot(None)).all())
            assert [(l.task_id, l.duration_std_minutes, l.delay_std_minutes)
                    for l in lignes] == [(carto["t1"], 120.0, 180.0)]
            total = db.session.get(TimeWeakness, wid)
            assert total.weakness == nouveau
            assert total.duration_std_minutes == 120.0
        rep = auth_client.get(f"/temps/api/weakness/{wid}")
        assert rep.get_json()["item"]["mode"] == "tasks"

    def test_put_repasse_en_mode_activite_efface_le_detail(self, app, auth_client, carto):
        from Code.models.models import TimeWeakness
        libelle = f"Simplifiée {_uid()}"
        with app.app_context():
            wid = _faiblesse_par_taches(auth_client, carto, libelle)
        rep = _json(auth_client, "put", f"/temps/api/weakness/{wid}", {
            "mode": "activity", "weakness": libelle, "duration_std": 15})
        assert rep.status_code == 200
        with app.app_context():
            assert TimeWeakness.query.filter_by(activity_id=carto["a1"]).filter(
                TimeWeakness.task_id.isnot(None)).count() == 0
        assert auth_client.get(f"/temps/api/weakness/{wid}").get_json()["item"]["mode"] == "activity"


# ── Tableau de bord : rôles et projets de la carto active ──────────────────

class TestTableauDeBordRolesEtProjets:

    def _role(self, app, ids):
        from Code.models.models import Role
        with app.app_context():
            r = Role(entity_id=ids["entity_id"], name=f"T150 Rôle TdB {_uid()}")
            db.session.add(r)
            db.session.commit()
            return r.id

    def test_analyse_de_role_de_la_carto_apparait(self, app, auth_client, ids, carto):
        from Code.models.models import Role
        rid_role = self._role(app, ids)
        try:
            rep = _json(auth_client, "post", "/temps/api/role_analysis", {
                "role_id": rid_role, "name": "Charge rôle T150",
                "lines": [{"activity_id": carto["a1"], "recurrence": "journalier",
                           "frequency": 2, "duration": 30}]})
            rid = rep.get_json()["id"]
            carto["role_analyses"].append(rid)
            tdb = auth_client.get("/temps/api/tableau_de_bord").get_json()
            ligne = next(r for r in tdb["par_role"] if r["id"] == rid)
            assert ligne["role_id"] == rid_role
            assert ligne["role"].startswith("T150 Rôle TdB")
            assert ligne["nom"] == "Charge rôle T150"
            assert ligne["n_activites"] == 1
            assert ligne["annuel_min"] > 0
            assert ligne["mensuel_min"] == pytest.approx(ligne["annuel_min"] / 12.0)
        finally:
            from Code.models.models import TimeRoleAnalysis
            with app.app_context():
                for rid in list(carto["role_analyses"]):
                    R = db.session.get(TimeRoleAnalysis, rid)
                    if R is not None:
                        db.session.delete(R)
                db.session.commit()
                carto["role_analyses"].clear()
                Role.query.filter_by(id=rid_role).delete()
                db.session.commit()

    def test_analyse_d_une_autre_carto_est_ecartee(self, app, auth_client, ids, carto):
        from Code.models.models import Activities, Entity, TimeRoleAnalysis, TimeRoleLine
        with app.app_context():
            ent = Entity(name=f"T150 autre carto {_uid()}", owner_id=ids["user_id"])
            db.session.add(ent)
            db.session.flush()
            ailleurs = Activities(entity_id=ent.id, name=f"T150 ailleurs {_uid()}")
            db.session.add(ailleurs)
            db.session.flush()
            R = TimeRoleAnalysis(role_id=99999999, name="Hors carto")
            db.session.add(R)
            db.session.flush()
            db.session.add(TimeRoleLine(role_analysis_id=R.id, activity_id=ailleurs.id,
                                        recurrence="journalier", frequency=1,
                                        duration_minutes=10))
            db.session.commit()
            rid, eid = R.id, ent.id
        try:
            tdb = auth_client.get("/temps/api/tableau_de_bord").get_json()
            assert rid not in [r["id"] for r in tdb["par_role"]]
        finally:
            with app.app_context():
                db.session.delete(db.session.get(TimeRoleAnalysis, rid))
                db.session.delete(db.session.get(Entity, eid))
                db.session.commit()

    def test_role_supprime_rend_un_nom_vide(self, app, auth_client, carto):
        from Code.models.models import TimeRoleAnalysis, TimeRoleLine
        with app.app_context():
            R = TimeRoleAnalysis(role_id=99999998, name="Sans rôle")
            db.session.add(R)
            db.session.flush()
            db.session.add(TimeRoleLine(role_analysis_id=R.id, activity_id=carto["a1"],
                                        recurrence="hebdomadaire", frequency=1,
                                        duration_minutes=60))
            db.session.commit()
            carto["role_analyses"].append(R.id)
            rid = R.id
        tdb = auth_client.get("/temps/api/tableau_de_bord").get_json()
        ligne = next(r for r in tdb["par_role"] if r["id"] == rid)
        assert ligne["role"] == ""
        assert ligne["role_id"] == 99999998

    def test_projet_de_la_carto_apparait_avec_sa_charge(self, app, auth_client, carto):
        rep = _json(auth_client, "post", "/temps/api/project", {
            "name": "Projet T150",
            "lines": [
                {"activity_id": carto["a1"], "duration": 2, "duration_unit": "heures",
                 "nb_people": 3},
                {"activity_id": carto["a2"], "duration": 30, "nb_people": 0},
            ]})
        assert rep.status_code == 200
        pid = rep.get_json()["project_id"]
        carto["projects"].append(pid)
        tdb = auth_client.get("/temps/api/tableau_de_bord").get_json()
        p = next(x for x in tdb["projets"] if x["id"] == pid)
        assert p["nom"] == "Projet T150"
        assert p["n_activites"] == 2
        assert p["duree_min"] == 150.0
        # nb_people=0 compte pour une personne (max(1, …)) : 120×3 + 30×1
        assert p["charge_min"] == 390.0

    def test_projet_n_entre_pas_dans_la_charge_annuelle(self, app, auth_client, carto):
        avant = auth_client.get("/temps/api/tableau_de_bord").get_json()["charge"]["annuel_min"]
        rep = _json(auth_client, "post", "/temps/api/project", {
            "name": "Ponctuel T150",
            "lines": [{"activity_id": carto["a1"], "duration": 8, "duration_unit": "heures"}]})
        carto["projects"].append(rep.get_json()["project_id"])
        apres = auth_client.get("/temps/api/tableau_de_bord").get_json()["charge"]["annuel_min"]
        assert apres == avant
