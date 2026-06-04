# tests/test_38_temps_avance.py
"""
Page : Gestion du Temps — routes avancées (/temps)
Couverture des endpoints non testés dans test_09_time.py :
  - POST   /temps/api/project               → création projet de charges
  - GET    /temps/api/project/<id>           → lecture projet
  - DELETE /temps/api/project/<id>           → suppression projet
  - DELETE /temps/api/project_line/<id>      → suppression ligne projet
  - DELETE /temps/api/time_analysis/<id>     → suppression analyse de temps
  - POST   /temps/api/role_analysis          → création analyse rôle
  - GET    /temps/api/role_analysis/<id>     → lecture analyse rôle + summary
  - PATCH  /temps/api/role_analysis/<id>     → renommage analyse rôle
  - DELETE /temps/api/role_analysis/<id>     → suppression analyse rôle
  - DELETE /temps/api/role_line/<id>         → suppression ligne rôle
  - POST   /temps/api/weakness               → calcul + sauvegarde faiblesse
"""
import json
import pytest

pytestmark = pytest.mark.temps_avance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_role(app, entity_id, name="Rôle Test Temps"):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        r = Role(entity_id=entity_id, name=name)
        db.session.add(r)
        db.session.commit()
        return r.id


def _create_project(auth_client, activity_id, name="Projet Test"):
    r = auth_client.post(
        "/temps/api/project",
        data=json.dumps({
            "name": name,
            "lines": [{"activity_id": activity_id, "duration": 60, "duration_unit": "minutes", "delay": 0, "nb_people": 1}]
        }),
        content_type="application/json",
    )
    return r


def _create_time_analysis(app, activity_id):
    with app.app_context():
        from Code.models.models import TimeAnalysis
        from Code.extensions import db
        ta = TimeAnalysis(
            type='activity', activity_id=activity_id, task_id=None,
            duration=30, recurrence='journalier', frequency=1, delay=0
        )
        db.session.add(ta)
        db.session.commit()
        return ta.id


def _create_role_analysis(auth_client, role_id, activity_id, name="Analyse Rôle Test"):
    r = auth_client.post(
        "/temps/api/role_analysis",
        data=json.dumps({
            "role_id": role_id,
            "name": name,
            "lines": [{"activity_id": activity_id, "recurrence": "journalier", "frequency": 1, "duration": 30}]
        }),
        content_type="application/json",
    )
    return r


# ===========================================================================
# 1. Projet de charges
# ===========================================================================

class TestTimeProject:

    def test_create_project_returns_project_id(self, auth_client, ids):
        r = _create_project(auth_client, ids["activity_id"])
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        assert isinstance(data.get("project_id"), int)

    def test_create_project_empty_name_uses_default(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/project",
            data=json.dumps({"lines": [{"activity_id": ids["activity_id"], "duration": 10}]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True

    def test_create_project_no_lines_still_creates(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/project",
            data=json.dumps({"name": "Sans lignes"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "project_id" in data

    def test_read_project_returns_lines_and_totals(self, auth_client, ids):
        create = _create_project(auth_client, ids["activity_id"], name="Projet Lecture")
        pid = create.get_json()["project_id"]

        r = auth_client.get(f"/temps/api/project/{pid}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "project" in data
        assert "lines" in data
        assert isinstance(data["lines"], list)
        assert "total_duration_minutes" in data

    def test_read_project_not_found_returns_404(self, auth_client):
        r = auth_client.get("/temps/api/project/999999")
        assert r.status_code == 404

    def test_list_projects_returns_array(self, auth_client):
        r = auth_client.get("/temps/api/projects")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        assert isinstance(data.get("items"), list)

    def test_delete_project_removes_it(self, auth_client, ids):
        create = _create_project(auth_client, ids["activity_id"], name="Projet À Supprimer")
        pid = create.get_json()["project_id"]

        r = auth_client.delete(f"/temps/api/project/{pid}")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        assert data.get("deleted") is True

    def test_delete_project_not_found_returns_404(self, auth_client):
        r = auth_client.delete("/temps/api/project/999999")
        assert r.status_code == 404

    def test_delete_project_line_removes_line(self, auth_client, ids):
        create = _create_project(auth_client, ids["activity_id"], name="Projet Ligne")
        pid = create.get_json()["project_id"]

        project = auth_client.get(f"/temps/api/project/{pid}").get_json()
        lines = project["lines"]
        assert len(lines) == 1
        line_id = lines[0]["id"]

        r = auth_client.delete(f"/temps/api/project_line/{line_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        assert "project_id" in data

    def test_delete_project_line_auto_deletes_empty_project(self, auth_client, ids):
        create = _create_project(auth_client, ids["activity_id"], name="Projet Auto-Delete")
        pid = create.get_json()["project_id"]
        project = auth_client.get(f"/temps/api/project/{pid}").get_json()
        line_id = project["lines"][0]["id"]

        r = auth_client.delete(f"/temps/api/project_line/{line_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("project_deleted") is True

    def test_delete_project_line_not_found_returns_404(self, auth_client):
        r = auth_client.delete("/temps/api/project_line/999999")
        assert r.status_code == 404


# ===========================================================================
# 2. Analyse de temps (TimeAnalysis) — suppression
# ===========================================================================

class TestTimeAnalysisDelete:

    def test_delete_time_analysis_removes_it(self, auth_client, ids, app):
        ta_id = _create_time_analysis(app, ids["activity_id"])

        r = auth_client.delete(f"/temps/api/time_analysis/{ta_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        assert data.get("deleted") is True

    def test_delete_time_analysis_not_found_returns_404(self, auth_client):
        r = auth_client.delete("/temps/api/time_analysis/999999")
        assert r.status_code == 404


# ===========================================================================
# 3. Analyse de rôle (TimeRoleAnalysis)
# ===========================================================================

class TestTimeRoleAnalysis:

    def test_create_role_analysis_returns_id(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"])
        r = _create_role_analysis(auth_client, role_id, ids["activity_id"])
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        assert isinstance(data.get("id"), int)

    def test_create_role_analysis_with_lines(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"], name="Rôle Lignes")
        r = auth_client.post(
            "/temps/api/role_analysis",
            data=json.dumps({
                "role_id": role_id,
                "name": "Avec lignes",
                "lines": [
                    {"activity_id": ids["activity_id"], "recurrence": "hebdomadaire", "frequency": 2, "duration": 45},
                ]
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True

    def test_read_role_analysis_returns_summary(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"], name="Rôle Lecture")
        create = _create_role_analysis(auth_client, role_id, ids["activity_id"], name="Analyse Lue")
        rid = create.get_json()["id"]

        r = auth_client.get(f"/temps/api/role_analysis/{rid}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "role" in data
        assert "lines" in data
        assert "summary" in data
        summary = data["summary"]
        assert "annual_minutes" in summary
        assert "monthly_minutes" in summary

    def test_read_role_analysis_not_found_returns_404(self, auth_client):
        r = auth_client.get("/temps/api/role_analysis/999999")
        assert r.status_code == 404

    def test_patch_role_analysis_renames_it(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"], name="Rôle Renommage")
        create = _create_role_analysis(auth_client, role_id, ids["activity_id"], name="Ancien Nom")
        rid = create.get_json()["id"]

        r = auth_client.patch(
            f"/temps/api/role_analysis/{rid}",
            data=json.dumps({"name": "Nouveau Nom"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["name"] == "Nouveau Nom"

    def test_patch_role_analysis_empty_name_ignored(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"], name="Rôle Patch Vide")
        create = _create_role_analysis(auth_client, role_id, ids["activity_id"], name="Nom Stable")
        rid = create.get_json()["id"]

        r = auth_client.patch(
            f"/temps/api/role_analysis/{rid}",
            data=json.dumps({"name": ""}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["name"] == "Nom Stable"

    def test_delete_role_analysis_removes_it(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"], name="Rôle Suppression")
        create = _create_role_analysis(auth_client, role_id, ids["activity_id"])
        rid = create.get_json()["id"]

        r = auth_client.delete(f"/temps/api/role_analysis/{rid}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["deleted"] is True

    def test_delete_role_analysis_not_found_returns_404(self, auth_client):
        r = auth_client.delete("/temps/api/role_analysis/999999")
        assert r.status_code == 404

    def test_list_role_analyses_returns_array(self, auth_client):
        r = auth_client.get("/temps/api/role_analyses")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True
        assert isinstance(data.get("items"), list)

    def test_delete_role_line_removes_line(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"], name="Rôle Ligne Del")
        create = _create_role_analysis(auth_client, role_id, ids["activity_id"])
        rid = create.get_json()["id"]

        analysis = auth_client.get(f"/temps/api/role_analysis/{rid}").get_json()
        lines = analysis["lines"]
        assert len(lines) == 1
        line_id = lines[0]["id"]

        r = auth_client.delete(f"/temps/api/role_line/{line_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("ok") is True

    def test_delete_role_line_auto_deletes_empty_analysis(self, auth_client, ids, app):
        role_id = _create_role(app, ids["entity_id"], name="Rôle Auto-Delete Ligne")
        create = _create_role_analysis(auth_client, role_id, ids["activity_id"])
        rid = create.get_json()["id"]

        analysis = auth_client.get(f"/temps/api/role_analysis/{rid}").get_json()
        line_id = analysis["lines"][0]["id"]

        r = auth_client.delete(f"/temps/api/role_line/{line_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("analysis_deleted") is True

    def test_delete_role_line_not_found_returns_404(self, auth_client):
        r = auth_client.delete("/temps/api/role_line/999999")
        assert r.status_code == 404


# ===========================================================================
# 4. Calcul de faiblesse (Weakness)
# ===========================================================================

class TestWeaknessCalculation:

    def test_weakness_calculation_returns_ok_and_calc_fields(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/weakness",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "mode": "activity",
                "duration_std": 60,
                "duration_unit": "minutes",
                "delay_std": 10,
                "delay_unit": "minutes",
                "recurrence": "journalier",
                "frequency": 1,
                "L_work_added": 5,
                "L_unit": "minutes",
                "M_wait_added": 2,
                "M_unit": "minutes",
                "N_prob_denom": 4,
                "weakness": "Interruptions fréquentes",
                "save": False,
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "calc" in data
        calc = data["calc"]
        assert "O" in calc
        assert "P" in calc
        assert "AA" in calc
        assert calc["O"] == pytest.approx(1.0 / 4)

    def test_weakness_without_save_does_not_persist(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import TimeWeakness
            count_before = TimeWeakness.query.filter_by(activity_id=ids["activity_id"]).count()

        auth_client.post(
            "/temps/api/weakness",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "mode": "activity",
                "duration_std": 30,
                "duration_unit": "minutes",
                "recurrence": "hebdomadaire",
                "frequency": 1,
                "save": False,
            }),
            content_type="application/json",
        )

        with app.app_context():
            from Code.models.models import TimeWeakness
            count_after = TimeWeakness.query.filter_by(activity_id=ids["activity_id"]).count()

        assert count_after == count_before

    def test_weakness_with_save_persists_record(self, auth_client, ids, app):
        with app.app_context():
            from Code.models.models import TimeWeakness
            count_before = TimeWeakness.query.filter_by(activity_id=ids["activity_id"]).count()

        r = auth_client.post(
            "/temps/api/weakness",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "mode": "activity",
                "duration_std": 45,
                "duration_unit": "minutes",
                "delay_std": 5,
                "delay_unit": "minutes",
                "recurrence": "mensuel",
                "frequency": 2,
                "L_work_added": 0,
                "M_wait_added": 0,
                "N_prob_denom": 1,
                "weakness": "Test persistance",
                "save": True,
            }),
            content_type="application/json",
        )
        assert r.status_code == 200

        with app.app_context():
            from Code.models.models import TimeWeakness
            count_after = TimeWeakness.query.filter_by(activity_id=ids["activity_id"]).count()

        assert count_after > count_before

    def test_weakness_task_mode_sums_task_durations(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/weakness",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "mode": "tasks",
                "tasks": [
                    {"task_id": ids["task_id"], "duration_std": 20, "duration_unit": "minutes"},
                ],
                "recurrence": "journalier",
                "frequency": 1,
                "save": False,
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["B_minutes"] == pytest.approx(20.0)

    def test_weakness_prob_denom_1_gives_full_probability(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/weakness",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "mode": "activity",
                "duration_std": 60,
                "duration_unit": "minutes",
                "recurrence": "journalier",
                "frequency": 1,
                "N_prob_denom": 1,
                "save": False,
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["calc"]["O"] == pytest.approx(1.0)

    def test_weakness_annual_recurrence(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/weakness",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "mode": "activity",
                "duration_std": 60,
                "duration_unit": "minutes",
                "recurrence": "annuel",
                "frequency": 1,
                "save": False,
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "calc" in data
