# tests/test_09_time.py
"""
Page : Gestion du Temps
Tests couvrant les endpoints de l'API temps.
"""
import pytest
import json

pytestmark = pytest.mark.time


class TestTimePage:

    def test_time_page_accessible(self, auth_client):
        r = auth_client.get("/temps/", follow_redirects=True)
        assert r.status_code in (200, 302)

    def test_get_calendar_params(self, auth_client):
        r = auth_client.get("/temps/api/calendar_params")
        assert r.status_code in (200, 404)

    def test_get_activity_defaults(self, auth_client, ids):
        r = auth_client.get(f"/temps/api/activity_defaults/{ids['activity_id']}")
        assert r.status_code in (200, 404)

    def test_get_activity_time_empty(self, auth_client, ids):
        r = auth_client.get(f"/temps/api/activity_time/{ids['activity_id']}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, (dict, list))

    def test_post_activity_time(self, auth_client, ids, app):
        """Mode 'activity' (implicite) : duration/delay au niveau racine du payload
        remplacent directement duration_minutes/delay_minutes de l'activité."""
        try:
            r = auth_client.post(
                f"/temps/api/activity_time/{ids['activity_id']}",
                data=json.dumps({
                    "duration": 60,
                    "duration_unit": "minutes",
                    "delay": 10,
                    "delay_unit": "minutes",
                    "tasks": [],
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["ok"] is True
            assert data["duration_minutes"] == 60.0
            assert data["delay_minutes"] == 10.0
        finally:
            with app.app_context():
                from Code.models.models import Activities
                from Code.extensions import db
                a = Activities.query.get(ids["activity_id"])
                a.duration_minutes = 0
                a.delay_minutes = 0
                db.session.commit()

    def test_post_activity_time_mode_tasks_sums_task_durations(self, auth_client, ids, app):
        """Mode 'tasks' : duration_minutes de l'activité = somme des durées des
        tâches envoyées (agrégation, branche distincte du mode 'activity')."""
        with app.app_context():
            from Code.models.models import Task
            from Code.extensions import db
            t1 = Task(name="Tâche Temps A", activity_id=ids["activity_id"], order=1)
            t2 = Task(name="Tâche Temps B", activity_id=ids["activity_id"], order=2)
            db.session.add_all([t1, t2])
            db.session.commit()
            t1_id, t2_id = t1.id, t2.id

        try:
            r = auth_client.post(
                f"/temps/api/activity_time/{ids['activity_id']}",
                data=json.dumps({
                    "mode": "tasks",
                    "tasks": [
                        {"task_id": t1_id, "duration": 15, "duration_unit": "minutes"},
                        {"task_id": t2_id, "duration": 25, "duration_unit": "minutes"},
                    ],
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["ok"] is True
            assert data["duration_minutes"] == 40.0

            with app.app_context():
                from Code.models.models import Task
                assert Task.query.get(t1_id).duration_minutes == 15.0
                assert Task.query.get(t2_id).duration_minutes == 25.0
        finally:
            with app.app_context():
                from Code.models.models import Task, Activities
                from Code.extensions import db
                Task.query.filter(Task.id.in_([t1_id, t2_id])).delete(synchronize_session=False)
                a = Activities.query.get(ids["activity_id"])
                a.duration_minutes = 0
                a.delay_minutes = 0
                db.session.commit()

    def test_delete_activity_time(self, auth_client, ids, app):
        """DELETE remet duration_minutes/delay_minutes à 0, pour l'activité ET ses
        tâches (vérifié via un GET de suivi, pas juste le statut de la réponse)."""
        with app.app_context():
            from Code.models.models import Activities, Task
            from Code.extensions import db
            a = Activities.query.get(ids["activity_id"])
            a.duration_minutes = 90
            a.delay_minutes = 30
            t = Task(name="Tâche Temps Delete", activity_id=ids["activity_id"], order=1,
                     duration_minutes=45, delay_minutes=15)
            db.session.add(t)
            db.session.commit()
            task_id = t.id

        try:
            r = auth_client.delete(f"/temps/api/activity_time/{ids['activity_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data == {"ok": True, "reset": True}

            r2 = auth_client.get(f"/temps/api/activity_time/{ids['activity_id']}")
            data2 = json.loads(r2.data)
            assert data2["activity"]["duration_minutes"] == 0.0
            assert data2["activity"]["delay_minutes"] == 0.0
            task_entry = next(t for t in data2["tasks"] if t["id"] == task_id)
            assert task_entry["duration_minutes"] == 0.0
            assert task_entry["delay_minutes"] == 0.0
        finally:
            with app.app_context():
                from Code.models.models import Task
                from Code.extensions import db
                Task.query.filter_by(id=task_id).delete()
                db.session.commit()

    def test_get_activities_list(self, auth_client):
        r = auth_client.get("/temps/api/activities")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            # Peut retourner une liste ou un dict avec 'items'
            assert isinstance(data, (list, dict))

    def test_get_projects_list(self, auth_client):
        r = auth_client.get("/temps/api/projects")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, (list, dict))

    def test_get_time_analyses_list(self, auth_client):
        r = auth_client.get("/temps/api/time_analyses")
        assert r.status_code in (200, 404)

    def test_create_time_analysis(self, auth_client, ids):
        r = auth_client.post(
            "/temps/api/time_analysis",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "duration": 30,
                "recurrence": "hebdomadaire",
                "frequency": 1,
                "type": "travail",
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201, 400)

    def test_create_time_analysis_mode_tasks_creates_task_rows(self, auth_client, ids, app):
        """mode='tasks' crée une TimeAnalysis de type 'task' par tâche envoyée
        (branche distincte du mode 'activity' par défaut)."""
        with app.app_context():
            from Code.models.models import Task
            from Code.extensions import db
            t = Task(name="Tâche Analyse Temps", activity_id=ids["activity_id"], order=1)
            db.session.add(t)
            db.session.commit()
            task_id = t.id

        try:
            r = auth_client.post(
                "/temps/api/time_analysis",
                data=json.dumps({
                    "mode": "tasks",
                    "activity_id": ids["activity_id"],
                    "recurrence": "hebdomadaire",
                    "frequency": 1,
                    "tasks": [{"task_id": task_id, "duration": 20, "duration_unit": "minutes"}],
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert json.loads(r.data)["ok"] is True

            with app.app_context():
                from Code.models.models import TimeAnalysis
                row = TimeAnalysis.query.filter_by(task_id=task_id, type="task").first()
                assert row is not None
                assert row.duration == 20
                assert row.activity_id == ids["activity_id"]
        finally:
            with app.app_context():
                from Code.models.models import TimeAnalysis, Task
                from Code.extensions import db
                TimeAnalysis.query.filter_by(task_id=task_id).delete()
                Task.query.filter_by(id=task_id).delete()
                db.session.commit()

    def test_get_role_analyses_list(self, auth_client):
        r = auth_client.get("/temps/api/role_analyses")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = json.loads(r.data)
            assert isinstance(data, (list, dict))
