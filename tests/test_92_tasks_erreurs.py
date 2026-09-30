# tests/test_92_tasks_erreurs.py
"""
Page : Tâches — chemins d'erreur (/tasks)
Couvre les branches non atteintes ailleurs : échec de commit (500 + rollback),
tâche/rôle inexistants, statut manquant, association déjà présente.
"""
import json
import pytest

pytestmark = pytest.mark.tasks


def _task(app, ids, name):
    with app.app_context():
        from Code.models.models import Task
        from Code.extensions import db
        t = Task(name=name, activity_id=ids["activity_id"])
        db.session.add(t)
        db.session.commit()
        return t.id


def _cleanup_task(app, tid):
    with app.app_context():
        from Code.models.models import Task
        from Code.extensions import db
        from sqlalchemy import text
        db.session.execute(text("DELETE FROM task_roles WHERE task_id=:t"), {"t": tid})
        t = Task.query.get(tid)
        if t:
            db.session.delete(t)
        db.session.commit()


def _cleanup_roles(app, names):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        from sqlalchemy import text
        for n in names:
            for r in Role.query.filter_by(name=n).all():
                db.session.execute(text("DELETE FROM task_roles WHERE role_id=:r"), {"r": r.id})
                db.session.delete(r)
        db.session.commit()


def _boom(*a, **k):
    raise RuntimeError("commit KO")


class TestTasksErreurs:

    def test_add_roles_sans_statut_400(self, auth_client, app, ids):
        tid = _task(app, ids, "T92 sans statut")
        try:
            r = auth_client.post(f"/tasks/{tid}/roles/add",
                                 data=json.dumps({"new_roles": ["X"]}),
                                 content_type="application/json")
            assert r.status_code == 400
        finally:
            _cleanup_task(app, tid)

    def test_add_roles_tache_inexistante_404(self, auth_client):
        r = auth_client.post("/tasks/999999/roles/add",
                             data=json.dumps({"status": "R"}),
                             content_type="application/json")
        assert r.status_code == 404

    def test_add_role_existant_deja_associe_pas_de_doublon(self, auth_client, app, ids):
        tid = _task(app, ids, "T92 doublon")
        try:
            body = json.dumps({"new_roles": ["Rôle T92 A"], "status": "Réalisateur"})
            r1 = auth_client.post(f"/tasks/{tid}/roles/add", data=body, content_type="application/json")
            assert len(r1.get_json()["added_roles"]) == 1
            r2 = auth_client.post(f"/tasks/{tid}/roles/add", data=body, content_type="application/json")
            assert r2.status_code == 200
            assert r2.get_json()["added_roles"] == []
        finally:
            _cleanup_task(app, tid)
            _cleanup_roles(app, ["Rôle T92 A"])

    def test_add_roles_commit_echoue_500(self, auth_client, app, ids, monkeypatch):
        tid = _task(app, ids, "T92 commit KO")
        try:
            from Code.extensions import db
            monkeypatch.setattr(db.session, "commit", _boom)
            r = auth_client.post(f"/tasks/{tid}/roles/add",
                                 data=json.dumps({"new_roles": ["Rôle T92 B"], "status": "R"}),
                                 content_type="application/json")
            assert r.status_code == 500
            assert "commit KO" in r.get_json()["error"]
            monkeypatch.undo()
            with app.app_context():
                from Code.models.models import Role
                assert Role.query.filter_by(name="Rôle T92 B").first() is None
        finally:
            monkeypatch.undo()
            _cleanup_task(app, tid)
            _cleanup_roles(app, ["Rôle T92 B"])

    def test_delete_role_tache_inexistante_404(self, auth_client):
        assert auth_client.delete("/tasks/999999/roles/1").status_code == 404

    def test_delete_role_non_associe_404(self, auth_client, app, ids):
        tid = _task(app, ids, "T92 role non associé")
        try:
            r = auth_client.delete(f"/tasks/{tid}/roles/999999")
            assert r.status_code == 404
            assert "not associated" in r.get_json()["error"]
        finally:
            _cleanup_task(app, tid)

    def test_delete_role_commit_echoue_500(self, auth_client, app, ids, monkeypatch):
        tid = _task(app, ids, "T92 del role KO")
        try:
            auth_client.post(f"/tasks/{tid}/roles/add",
                             data=json.dumps({"new_roles": ["Rôle T92 C"], "status": "R"}),
                             content_type="application/json")
            with app.app_context():
                from Code.models.models import Role
                rid = Role.query.filter_by(name="Rôle T92 C").first().id
            from Code.extensions import db
            monkeypatch.setattr(db.session, "commit", _boom)
            r = auth_client.delete(f"/tasks/{tid}/roles/{rid}")
            assert r.status_code == 500
            monkeypatch.undo()
            assert len(auth_client.get(f"/tasks/{tid}/roles").get_json()["roles"]) == 1
        finally:
            monkeypatch.undo()
            _cleanup_task(app, tid)
            _cleanup_roles(app, ["Rôle T92 C"])

    def test_roles_d_une_tache_inexistante_404(self, auth_client):
        assert auth_client.get("/tasks/999999/roles").status_code == 404

    def test_render_activite_inexistante_404(self, auth_client):
        assert auth_client.get("/tasks/999999/render").status_code == 404

    def test_update_commit_echoue_500(self, auth_client, app, ids, monkeypatch):
        tid = _task(app, ids, "T92 update KO")
        try:
            from Code.extensions import db
            monkeypatch.setattr(db.session, "commit", _boom)
            r = auth_client.put(f"/tasks/{tid}", data=json.dumps({"name": "Nouveau"}),
                                content_type="application/json")
            assert r.status_code == 500
        finally:
            monkeypatch.undo()
            _cleanup_task(app, tid)

    def test_update_tache_inexistante_404(self, auth_client):
        r = auth_client.put("/tasks/999999", data=json.dumps({"name": "x"}),
                            content_type="application/json")
        assert r.status_code == 404

    def test_delete_commit_echoue_500_et_tache_conservee(self, auth_client, app, ids, monkeypatch):
        tid = _task(app, ids, "T92 delete KO")
        try:
            from Code.extensions import db
            monkeypatch.setattr(db.session, "commit", _boom)
            r = auth_client.delete(f"/tasks/{tid}")
            assert r.status_code == 500
            monkeypatch.undo()
            with app.app_context():
                from Code.models.models import Task
                assert Task.query.get(tid) is not None
        finally:
            monkeypatch.undo()
            _cleanup_task(app, tid)

    def test_delete_tache_inexistante_404(self, auth_client):
        assert auth_client.delete("/tasks/999999").status_code == 404
