# tests/test_138_couverture_residuelle.py
"""
Branches résiduelles : rendu partiel des tâches avec connexions (entrantes /
sortantes), échec du journal d'événements lors de l'ajout d'un outil, et
repli de `settings._is_admin` quand la vérification de droits échoue.
"""
import pytest

pytestmark = pytest.mark.tasks


@pytest.fixture
def activite_avec_connexions(app, ids):
    """Activité dédiée + 2 liens (entrant nommé, sortant sans donnée) + tâche."""
    from Code.models.models import Activities, Task, Link, Data
    from Code.extensions import db
    from sqlalchemy import text
    with app.app_context():
        act = Activities(name="Act Conn 138", entity_id=ids["entity_id"])
        autre = Activities(name="Autre Conn 138", entity_id=ids["entity_id"])
        data = Data(name="Donnée 138", type="Flux", entity_id=ids["entity_id"])
        db.session.add_all([act, autre, data])
        db.session.flush()
        task = Task(name="Tâche Conn 138", activity_id=act.id)
        entrant = Link(source_activity_id=autre.id, source_data_id=data.id,
                       target_activity_id=act.id, type="Entrée",
                       entity_id=ids["entity_id"])
        sortant = Link(source_activity_id=act.id, target_activity_id=autre.id,
                       type="Sortie", description="desc sortante",
                       entity_id=ids["entity_id"])
        db.session.add_all([task, entrant, sortant])
        db.session.flush()
        db.session.execute(text(
            "INSERT INTO task_link_assignments (link_id, task_id, direction) "
            "VALUES (:l, :t, :d)"), {"l": entrant.id, "t": task.id, "d": "incoming"})
        db.session.execute(text(
            "INSERT INTO task_link_assignments (link_id, task_id, direction) "
            "VALUES (:l, :t, :d)"), {"l": sortant.id, "t": task.id, "d": "outgoing"})
        db.session.commit()
        info = {"act": act.id, "autre": autre.id, "task": task.id,
                "links": [entrant.id, sortant.id], "data": data.id}
    yield info
    with app.app_context():
        db.session.execute(text("DELETE FROM task_link_assignments WHERE task_id=:t"),
                           {"t": info["task"]})
        Link.query.filter(Link.id.in_(info["links"])).delete(synchronize_session=False)
        Task.query.filter_by(id=info["task"]).delete()
        Data.query.filter_by(id=info["data"]).delete()
        Activities.query.filter(Activities.id.in_([info["act"], info["autre"]])).delete(
            synchronize_session=False)
        db.session.commit()


class TestRenderTasksConnexions:

    def test_render_affiche_la_tache_avec_ses_connexions(self, auth_client, activite_avec_connexions):
        r = auth_client.get(f"/tasks/{activite_avec_connexions['act']}/render")
        assert r.status_code == 200
        assert "Tâche Conn 138" in r.get_data(as_text=True)

    def test_render_activite_inexistante_404(self, auth_client):
        assert auth_client.get("/tasks/99999999/render").status_code == 404


class TestOutilsJournalEnEchec:

    def test_ajout_outil_reussit_meme_si_le_journal_echoue(self, app, auth_client, ids, monkeypatch):
        from Code.routes import tools as tools_mod
        from Code.models.models import Tool
        from Code.extensions import db

        def boom(*a, **k):
            raise RuntimeError("journal indisponible")
        monkeypatch.setattr(tools_mod, "RecentEvent", boom)

        r = auth_client.post("/tools/add", json={
            "task_id": ids["task_id"], "new_tools": ["Outil Journal 138"]})
        assert r.status_code == 200
        with app.app_context():
            t = Tool.query.filter_by(name="Outil Journal 138").first()
            assert t is not None
            from Code.models.models import Task
            task = Task.query.get(ids["task_id"])
            if t in task.tools:
                task.tools.remove(t)
            db.session.delete(t)
            db.session.commit()


class TestSettingsIsAdminRepli:

    def test_is_admin_faux_si_la_verification_leve(self, app, monkeypatch):
        import Code.permissions as perms
        from Code.routes import settings as settings_mod

        def boom():
            raise RuntimeError("panne")
        monkeypatch.setattr(perms, "is_admin", boom)
        with app.test_request_context("/"):
            assert settings_mod._is_admin() is False
