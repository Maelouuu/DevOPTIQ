# tests/test_130_activities_form_reorder.py
"""
Route : POST /activities/<id>/tasks/reorder (activities_form.py)
Ordre des tâches par glisser-déposer. Chaque test crée sa propre activité
et ses tâches, nettoyées ensuite : aucune dépendance au seed partagé.
"""
import pytest

pytestmark = pytest.mark.activities_form


def _make_activity_with_tasks(app, ids, n=3, tag="A"):
    with app.app_context():
        from Code.models.models import Activities, Task
        from Code.extensions import db
        act = Activities(name=f"ActReorder-{tag}", entity_id=ids["entity_id"])
        db.session.add(act)
        db.session.flush()
        tasks = []
        for i in range(n):
            t = Task(name=f"T{tag}{i}", activity_id=act.id, order=i)
            db.session.add(t)
            tasks.append(t)
        db.session.commit()
        return act.id, [t.id for t in tasks]


def _cleanup(app, *activity_ids):
    with app.app_context():
        from Code.models.models import Activities, Task
        from Code.extensions import db
        for aid in activity_ids:
            for t in Task.query.filter_by(activity_id=aid).all():
                db.session.delete(t)
            db.session.flush()
            a = db.session.get(Activities, aid)
            if a:
                db.session.delete(a)
        db.session.commit()


def _orders(app, task_ids):
    with app.app_context():
        from Code.models.models import Task
        from Code.extensions import db
        return {tid: db.session.get(Task, tid).order for tid in task_ids}


class TestReorderTasks:
    def test_reorder_applique_le_nouvel_ordre(self, app, auth_client, ids):
        aid, tids = _make_activity_with_tasks(app, ids, tag="R1")
        try:
            new = [tids[2], tids[0], tids[1]]
            r = auth_client.post(f"/activities/{aid}/tasks/reorder", json={"order": new})
            assert r.status_code == 200
            assert r.get_json() == {"message": "Order updated"}
            orders = _orders(app, tids)
            assert [orders[t] for t in new] == [0, 1, 2]
        finally:
            _cleanup(app, aid)

    def test_reorder_sans_liste_renvoie_400(self, app, auth_client, ids):
        aid, tids = _make_activity_with_tasks(app, ids, tag="R2")
        try:
            r = auth_client.post(f"/activities/{aid}/tasks/reorder", json={})
            assert r.status_code == 400
            assert "order" in r.get_json()["error"]
        finally:
            _cleanup(app, aid)

    def test_reorder_liste_vide_renvoie_400(self, app, auth_client, ids):
        aid, tids = _make_activity_with_tasks(app, ids, tag="R3")
        try:
            r = auth_client.post(f"/activities/{aid}/tasks/reorder", json={"order": []})
            assert r.status_code == 400
        finally:
            _cleanup(app, aid)

    def test_reorder_ignore_les_taches_d_une_autre_activite(self, app, auth_client, ids):
        aid1, t1 = _make_activity_with_tasks(app, ids, n=2, tag="R4a")
        aid2, t2 = _make_activity_with_tasks(app, ids, n=2, tag="R4b")
        try:
            avant = _orders(app, t2)
            r = auth_client.post(f"/activities/{aid1}/tasks/reorder",
                                 json={"order": [t2[1], t1[1], t1[0]]})
            assert r.status_code == 200
            assert _orders(app, t2) == avant
            o1 = _orders(app, t1)
            assert (o1[t1[1]], o1[t1[0]]) == (1, 2)
        finally:
            _cleanup(app, aid1, aid2)

    def test_reorder_ids_inconnus_sans_erreur(self, app, auth_client, ids):
        aid, tids = _make_activity_with_tasks(app, ids, n=1, tag="R5")
        try:
            r = auth_client.post(f"/activities/{aid}/tasks/reorder",
                                 json={"order": [999999991, 999999992]})
            assert r.status_code == 200
            assert _orders(app, tids) == {tids[0]: 0}
        finally:
            _cleanup(app, aid)

    def test_reorder_erreur_base_renvoie_500_et_rollback(self, app, auth_client, ids, monkeypatch):
        aid, tids = _make_activity_with_tasks(app, ids, n=2, tag="R6")
        try:
            from Code.extensions import db

            def boom():
                raise RuntimeError("db down")
            monkeypatch.setattr(db.session, "commit", boom)
            r = auth_client.post(f"/activities/{aid}/tasks/reorder",
                                 json={"order": [tids[1], tids[0]]})
            assert r.status_code == 500
            assert "db down" in r.get_json()["error"]
            monkeypatch.undo()
            assert _orders(app, tids) == {tids[0]: 0, tids[1]: 1}
        finally:
            _cleanup(app, aid)
