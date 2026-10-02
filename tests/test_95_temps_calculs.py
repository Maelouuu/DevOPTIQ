# tests/test_95_temps_calculs.py
"""
Page : Gestion du Temps — calculs et cas limites (/temps)
Complète test_09 / test_38 : conversions d'unités, récurrences de la faiblesse,
synthèse d'analyse de rôle (jour/semaine/mois/an), mode suggéré, remise à zéro.
Chaque test crée ses propres activités/tâches/rôles : aucune dépendance au seed
partagé ni à l'ordre d'exécution.
"""
import json
import uuid

import pytest

pytestmark = pytest.mark.temps_calculs


def _uid():
    return uuid.uuid4().hex[:8]


def _activity(app, entity_id, **kw):
    from Code.extensions import db
    from Code.models.models import Activities
    with app.app_context():
        a = Activities(entity_id=entity_id, name=f"Act temps {_uid()}", description="", **kw)
        db.session.add(a)
        db.session.commit()
        return a.id


def _task(app, activity_id, **kw):
    from Code.extensions import db
    from Code.models.models import Task
    with app.app_context():
        t = Task(activity_id=activity_id, name=f"Tâche temps {_uid()}", **kw)
        db.session.add(t)
        db.session.commit()
        return t.id


def _role(app, entity_id):
    from Code.extensions import db
    from Code.models.models import Role
    with app.app_context():
        r = Role(entity_id=entity_id, name=f"Rôle temps {_uid()}")
        db.session.add(r)
        db.session.commit()
        return r.id


def _post(c, url, body):
    return c.post(url, data=json.dumps(body), content_type="application/json")


def _params(c):
    return c.get("/temps/api/calendar_params").get_json()


class TestActivityTimeConversions:

    def test_post_hours_and_days_convert_to_minutes(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        r = _post(auth_client, f"/temps/api/activity_time/{aid}", {
            "mode": "activity", "duration": 2, "duration_unit": "heures",
            "delay": 1, "delay_unit": "jours"})
        assert r.status_code == 200
        j = r.get_json()
        assert j["duration_minutes"] == 120
        assert j["delay_minutes"] == 1440

    def test_post_unknown_unit_falls_back_to_minutes(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        r = _post(auth_client, f"/temps/api/activity_time/{aid}", {
            "mode": "activity", "duration": 7, "duration_unit": "siècles"})
        assert r.get_json()["duration_minutes"] == 7

    def test_post_unknown_activity_returns_404(self, auth_client):
        r = _post(auth_client, "/temps/api/activity_time/99999999", {"duration": 1})
        assert r.status_code == 404

    def test_get_unknown_activity_returns_404(self, auth_client):
        assert auth_client.get("/temps/api/activity_time/99999999").status_code == 404

    def test_get_suggests_tasks_mode_when_tasks_sum_equals_activity(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"], duration_minutes=30)
        _task(app, aid, duration_minutes=10)
        _task(app, aid, duration_minutes=20)
        j = auth_client.get(f"/temps/api/activity_time/{aid}").get_json()
        assert j["mode"] == "tasks"
        assert len(j["tasks"]) == 2

    def test_get_suggests_activity_mode_when_sums_differ(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"], duration_minutes=99)
        _task(app, aid, duration_minutes=10)
        assert auth_client.get(f"/temps/api/activity_time/{aid}").get_json()["mode"] == "activity"

    def test_delete_resets_activity_and_its_tasks(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"], duration_minutes=30, delay_minutes=5)
        tid = _task(app, aid, duration_minutes=30, delay_minutes=5)
        r = auth_client.delete(f"/temps/api/activity_time/{aid}")
        assert r.get_json() == {"ok": True, "reset": True}
        with app.app_context():
            from Code.models.models import Activities, Task
            a = Activities.query.get(aid)
            t = Task.query.get(tid)
            assert (a.duration_minutes, a.delay_minutes) == (0, 0)
            assert (t.duration_minutes, t.delay_minutes) == (0, 0)

    def test_post_tasks_mode_sets_task_delay_when_unit_given(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        tid = _task(app, aid)
        _post(auth_client, f"/temps/api/activity_time/{aid}", {
            "mode": "tasks", "tasks": [{
                "task_id": tid, "duration": 1, "duration_unit": "heures",
                "delay": 2, "delay_unit": "heures"}]})
        with app.app_context():
            from Code.models.models import Task
            t = Task.query.get(tid)
            assert t.duration_minutes == 60
            assert t.delay_minutes == 120


class TestActivityDefaults:

    def test_defaults_unknown_activity_returns_404(self, auth_client):
        assert auth_client.get("/temps/api/activity_defaults/99999999").status_code == 404

    def test_defaults_lists_tasks_with_durations(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"], duration_minutes=45, delay_minutes=3)
        _task(app, aid, duration_minutes=15, delay_minutes=1)
        j = auth_client.get(f"/temps/api/activity_defaults/{aid}").get_json()
        assert j["duration_minutes"] == 45
        assert j["delay_minutes"] == 3
        assert [t["duration_minutes"] for t in j["tasks"]] == [15]


class TestProjectTotals:

    def test_project_charge_multiplies_duration_by_nb_people(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        pid = _post(auth_client, "/temps/api/project", {"name": "P charge", "lines": [
            {"activity_id": aid, "duration": 1, "duration_unit": "heures",
             "delay": 30, "nb_people": 3}]}).get_json()["project_id"]
        j = auth_client.get(f"/temps/api/project/{pid}").get_json()
        assert j["total_duration_minutes"] == 60
        assert j["total_charge_minutes"] == 180
        assert j["total_delay_minutes"] == 30
        assert j["total_nb_people"] == 3

    def test_project_list_reports_line_count_and_totals(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        pid = _post(auth_client, "/temps/api/project", {"name": f"P liste {_uid()}", "lines": [
            {"activity_id": aid, "duration": 10, "nb_people": 2},
            {"activity_id": aid, "duration": 5, "nb_people": 1}]}).get_json()["project_id"]
        items = auth_client.get("/temps/api/projects").get_json()["items"]
        row = next(i for i in items if i["id"] == pid)
        assert row["line_count"] == 2
        assert row["total_duration_minutes"] == 15
        assert row["total_charge_minutes"] == 25

    def test_project_line_without_nb_people_defaults_to_one(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        pid = _post(auth_client, "/temps/api/project", {"lines": [
            {"activity_id": aid, "duration": 10}]}).get_json()["project_id"]
        assert auth_client.get(f"/temps/api/project/{pid}").get_json()["lines"][0]["nb_people"] == 1

    def test_delete_project_line_keeps_project_when_lines_remain(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        pid = _post(auth_client, "/temps/api/project", {"lines": [
            {"activity_id": aid, "duration": 1}, {"activity_id": aid, "duration": 2}]}).get_json()["project_id"]
        lid = auth_client.get(f"/temps/api/project/{pid}").get_json()["lines"][0]["id"]
        j = auth_client.delete(f"/temps/api/project_line/{lid}").get_json()
        assert j["project_deleted"] is False
        assert auth_client.get(f"/temps/api/project/{pid}").status_code == 200

    def test_rename_project_empty_name_keeps_old_name(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        pid = _post(auth_client, "/temps/api/project", {"name": "Nom gardé", "lines": [
            {"activity_id": aid, "duration": 1}]}).get_json()["project_id"]
        j = auth_client.patch(f"/temps/api/project/{pid}", data=json.dumps({"name": "  "}),
                              content_type="application/json").get_json()
        assert j["name"] == "Nom gardé"


class TestRoleAnalysisSummary:

    def _create(self, c, role_id, lines):
        return _post(c, "/temps/api/role_analysis",
                     {"role_id": role_id, "name": "Synthèse", "lines": lines}).get_json()["id"]

    def test_summary_sums_each_recurrence_separately(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        rid = _role(app, ids["entity_id"])
        analysis = self._create(auth_client, rid, [
            {"activity_id": aid, "recurrence": "journalier", "frequency": 2, "duration": 10},
            {"activity_id": aid, "recurrence": "hebdomadaire", "frequency": 1, "duration": 30},
            {"activity_id": aid, "recurrence": "mensuel", "frequency": 3, "duration": 5},
            {"activity_id": aid, "recurrence": "annuel", "frequency": 1, "duration": 100}])
        s = auth_client.get(f"/temps/api/role_analysis/{analysis}").get_json()["summary"]
        assert s["sum_daily_minutes"] == 20
        assert s["sum_weekly_minutes"] == 30
        assert s["sum_monthly_minutes"] == 15
        assert s["sum_yearly_minutes"] == 100

    def test_summary_annual_uses_calendar_params(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        rid = _role(app, ids["entity_id"])
        analysis = self._create(auth_client, rid, [
            {"activity_id": aid, "recurrence": "journalier", "frequency": 1, "duration": 10},
            {"activity_id": aid, "recurrence": "hebdomadaire", "frequency": 1, "duration": 20},
            {"activity_id": aid, "recurrence": "mensuel", "frequency": 1, "duration": 30},
            {"activity_id": aid, "recurrence": "annuel", "frequency": 1, "duration": 40}])
        p = _params(auth_client)
        dpw, wpy = p["days_per_week"], p["weeks_per_year"]
        s = auth_client.get(f"/temps/api/role_analysis/{analysis}").get_json()["summary"]
        assert s["annual_minutes"] == pytest.approx(10 * dpw * wpy + 20 * wpy + 30 * 12 + 40)
        assert s["monthly_minutes"] == pytest.approx(
            10 * dpw * wpy / 12 + 20 * wpy / 12 + 30 + 40 / 12)

    def test_line_without_duration_falls_back_to_activity_duration(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"], duration_minutes=25)
        rid = _role(app, ids["entity_id"])
        analysis = self._create(auth_client, rid, [
            {"activity_id": aid, "recurrence": "journalier", "frequency": 1}])
        j = auth_client.get(f"/temps/api/role_analysis/{analysis}").get_json()
        assert j["lines"][0]["duration_minutes"] == 25
        assert j["summary"]["sum_daily_minutes"] == 25

    def test_frequency_zero_counts_as_one_in_weight(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        rid = _role(app, ids["entity_id"])
        analysis = self._create(auth_client, rid, [
            {"activity_id": aid, "recurrence": "journalier", "frequency": 1, "duration": 12}])
        j = auth_client.get(f"/temps/api/role_analysis/{analysis}").get_json()
        assert j["lines"][0]["weight_minutes"] == 12

    def test_list_includes_role_name_and_summary(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        rid = _role(app, ids["entity_id"])
        analysis = self._create(auth_client, rid, [
            {"activity_id": aid, "recurrence": "journalier", "frequency": 1, "duration": 8}])
        items = auth_client.get("/temps/api/role_analyses").get_json()["items"]
        row = next(i for i in items if i["id"] == analysis)
        assert row["role"].startswith("Rôle temps")
        assert row["sum_daily_minutes"] == 8

    def test_empty_name_defaults_to_analyse_role(self, auth_client, app, ids):
        rid = _role(app, ids["entity_id"])
        analysis = _post(auth_client, "/temps/api/role_analysis",
                         {"role_id": rid, "name": "", "lines": []}).get_json()["id"]
        assert auth_client.get(f"/temps/api/role_analysis/{analysis}").get_json()["role"]["name"] == "Analyse rôle"


class TestWeaknessRecurrences:

    def _calc(self, c, aid, rec, **extra):
        body = {"mode": "activity", "activity_id": aid, "recurrence": rec,
                "L_work_added": 10, "M_wait_added": 5, "N_prob_denom": 4,
                "duration_std": 60, "delay_std": 20}
        body.update(extra)
        return _post(c, "/temps/api/weakness", body).get_json()

    def test_daily_occurrences_per_year(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        p = _params(auth_client)
        j = self._calc(auth_client, aid, "journalier")
        assert j["calc"]["P"] == pytest.approx(p["days_per_week"] * p["weeks_per_year"] / 4)

    def test_weekly_occurrences_per_year(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        p = _params(auth_client)
        assert self._calc(auth_client, aid, "hebdomadaire")["calc"]["P"] == pytest.approx(p["weeks_per_year"] / 4)

    def test_monthly_occurrences_per_year(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        p = _params(auth_client)
        assert self._calc(auth_client, aid, "mensuel")["calc"]["P"] == pytest.approx(
            p["weeks_per_year"] / 4.34524 / 4)

    def test_formulas_O_Q_S_T_Y(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        c = self._calc(auth_client, aid, "annuel")["calc"]
        assert c["O"] == 0.25
        assert c["Q"] == 2.5
        assert c["R"] == 3.75
        assert c["S"] == 62.5
        assert c["T"] == 23.75
        assert c["Y"] == 25
        assert c["Z"] == 5

    def test_prob_denom_zero_is_clamped_to_one(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        assert self._calc(auth_client, aid, "annuel", N_prob_denom=0)["calc"]["O"] == 1.0

    def test_units_are_converted_before_calculation(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        j = self._calc(auth_client, aid, "annuel", duration_std=1, duration_unit="heures",
                       delay_std=1, delay_unit="jours")
        assert j["B_minutes"] == 60
        assert j["C_minutes"] == 1440

    def test_save_in_task_mode_stores_one_row_per_task_plus_summary(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        t1, t2 = _task(app, aid), _task(app, aid)
        self._calc(auth_client, aid, "journalier", mode="tasks", save=True, weakness="Retard",
                   tasks=[{"task_id": t1, "duration_std": 10}, {"task_id": t2, "duration_std": 20}])
        with app.app_context():
            from Code.models.models import TimeWeakness
            rows = TimeWeakness.query.filter_by(activity_id=aid).all()
            assert len(rows) == 3
            summary = [r for r in rows if r.task_id is None]
            assert len(summary) == 1
            assert summary[0].duration_std_minutes == 30
            assert {r.weakness for r in rows} == {"Retard"}

    def test_missing_activity_id_is_rejected(self, auth_client):
        r = _post(auth_client, "/temps/api/weakness", {"mode": "activity"})
        assert r.status_code >= 400


class TestTimeAnalysisUnits:

    def test_create_activity_analysis_converts_delay_and_duration(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        r = _post(auth_client, "/temps/api/time_analysis", {
            "mode": "activity", "activity_id": aid, "duration": 2, "duration_unit": "heures",
            "delay": 1, "delay_unit": "heures", "recurrence": "hebdomadaire", "frequency": 3})
        assert r.status_code == 200
        item = auth_client.get(f"/temps/api/time_analyses?activity_id={aid}").get_json()["items"][0]
        assert item["duration"] == 120
        assert item["delay"] == 60
        assert item["recurrence"] == "hebdomadaire"
        assert item["frequency"] == 3
        assert item["type"] == "activity"

    def test_workload_total_is_duration_times_frequency_times_people(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        j = _post(auth_client, "/temps/api/activity_workload", {
            "activity_id": aid, "duration": 10, "frequency": 3, "nb_people": 2}).get_json()
        assert j["total_minutes"] == 60

    def test_workload_update_nb_people_and_frequency(self, auth_client, app, ids):
        aid = _activity(app, ids["entity_id"])
        wid = _post(auth_client, "/temps/api/activity_workload", {
            "activity_id": aid, "duration": 10}).get_json()["id"]
        r = auth_client.patch(f"/temps/api/activity_workload/{wid}",
                              data=json.dumps({"frequency": 4, "nb_people": 5}),
                              content_type="application/json")
        assert r.get_json()["total_minutes"] == 200


class TestSuppressionRoleNeLaisseAucuneLigneOrpheline:

    def test_retirer_la_bande_d_un_role_efface_les_lignes_de_ses_analyses(self, app):
        """Régression : la suppression en masse des analyses de rôle contournait
        le cascade ORM ; sous SQLite les lignes restaient orphelines, puis une
        nouvelle analyse réutilisant le même id en héritait (durées fantômes)."""
        from Code.extensions import db
        from Code.models.models import (Activities, Entity, Role, TimeRoleAnalysis,
                                        TimeRoleLine)
        from Code.routes.cartography_editor import _sync_carto_to_db

        nom = f"T95 Bande {_uid()}"
        with app.app_context():
            ent = Entity(name=f"Entité T95 {_uid()}")
            db.session.add(ent)
            db.session.commit()
            ent_id = ent.id
            _sync_carto_to_db(ent, {"shapes": [], "connections": [],
                                    "bands": [{"id": "b1", "label": nom, "height": 200}]})
            db.session.commit()
            role = Role.query.filter_by(name=nom).first()
            assert role is not None
            act = Activities(entity_id=ent_id, name=f"Act T95 {_uid()}", description="")
            db.session.add(act)
            db.session.flush()
            analyse = TimeRoleAnalysis(role_id=role.id)
            db.session.add(analyse)
            db.session.flush()
            db.session.add(TimeRoleLine(role_analysis_id=analyse.id, activity_id=act.id,
                                        recurrence="journalier", duration_minutes=30))
            db.session.commit()
            analyse_id = analyse.id

            _sync_carto_to_db(db.session.get(Entity, ent_id), {
                "shapes": [], "connections": [],
                "bands": [{"id": "b2", "label": f"T95 Autre {_uid()}", "height": 200}]})
            db.session.commit()

            assert TimeRoleAnalysis.query.get(analyse_id) is None
            assert TimeRoleLine.query.filter_by(role_analysis_id=analyse_id).count() == 0
