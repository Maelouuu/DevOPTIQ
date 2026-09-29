# tests/test_90_tasks_roles_par_nom.py
"""
Page : Tâches — rôles ajoutés par nom (tasks.py, POST /tasks/<id>/roles/add)
Couvre : nom vide ignoré, rôle déjà existant réutilisé (pas de doublon de Role),
association déjà présente non dupliquée, rôle inexistant ignoré, rendu partiel.
"""
import json
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.tasks_roles_nom


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def tache(app, ids):
    """Tâche jetable + rôle jetable, nettoyés après le test."""
    from Code.models.models import Task, Role
    from Code.extensions import db
    with app.app_context():
        t = Task(name="Tâche rôles par nom", activity_id=ids["activity_id"])
        r = Role(name="Rôle Par Nom Existant")
        db.session.add_all([t, r])
        db.session.commit()
        tid, rid = t.id, r.id
    yield {"task_id": tid, "role_id": rid, "role_name": "Rôle Par Nom Existant"}
    with app.app_context():
        db.session.execute(text("DELETE FROM task_roles WHERE task_id=:t"), {"t": tid})
        Task.query.filter_by(id=tid).delete()
        Role.query.filter(Role.name.in_(["Rôle Par Nom Existant", "Rôle Par Nom Neuf"])).delete(
            synchronize_session=False)
        db.session.commit()


class TestRolesParNom:
    def test_nom_vide_ignore(self, auth_client, tache):
        r = _post(auth_client, f"/tasks/{tache['task_id']}/roles/add",
                  {"new_roles": ["   ", ""], "status": "Réalisateur"})
        assert r.status_code == 200
        assert r.get_json()["added_roles"] == []

    def test_role_existant_par_nom_est_associe_sans_doublon_de_role(self, app, auth_client, tache):
        from Code.models.models import Role
        r = _post(auth_client, f"/tasks/{tache['task_id']}/roles/add",
                  {"new_roles": [tache["role_name"]], "status": "Réalisateur"})
        assert r.status_code == 200
        added = r.get_json()["added_roles"]
        assert len(added) == 1
        assert added[0]["id"] == tache["role_id"]
        assert added[0]["status"] == "Réalisateur"
        with app.app_context():
            assert Role.query.filter_by(name=tache["role_name"]).count() == 1

    def test_role_existant_par_nom_deja_associe_non_duplique(self, auth_client, tache):
        url = f"/tasks/{tache['task_id']}/roles/add"
        payload = {"new_roles": [tache["role_name"]], "status": "Réalisateur"}
        assert len(_post(auth_client, url, payload).get_json()["added_roles"]) == 1
        second = _post(auth_client, url, payload)
        assert second.status_code == 200
        assert second.get_json()["added_roles"] == []
        roles = auth_client.get(f"/tasks/{tache['task_id']}/roles").get_json()["roles"]
        assert len([x for x in roles if x["id"] == tache["role_id"]]) == 1

    def test_role_id_existant_deja_associe_non_duplique(self, auth_client, tache):
        url = f"/tasks/{tache['task_id']}/roles/add"
        payload = {"existing_role_ids": [tache["role_id"]], "status": "Approbateur"}
        assert len(_post(auth_client, url, payload).get_json()["added_roles"]) == 1
        assert _post(auth_client, url, payload).get_json()["added_roles"] == []

    def test_role_id_inexistant_ignore(self, auth_client, tache):
        r = _post(auth_client, f"/tasks/{tache['task_id']}/roles/add",
                  {"existing_role_ids": [99999999], "status": "Réalisateur"})
        assert r.status_code == 200
        assert r.get_json()["added_roles"] == []

    def test_nouveau_role_par_nom_cree_puis_liste(self, auth_client, tache):
        r = _post(auth_client, f"/tasks/{tache['task_id']}/roles/add",
                  {"new_roles": ["Rôle Par Nom Neuf"], "status": "Contributeur"})
        assert r.status_code == 200
        noms = [x["name"] for x in
                auth_client.get(f"/tasks/{tache['task_id']}/roles").get_json()["roles"]]
        assert "Rôle Par Nom Neuf" in noms

    def test_statut_manquant_400(self, auth_client, tache):
        r = _post(auth_client, f"/tasks/{tache['task_id']}/roles/add",
                  {"new_roles": ["X"], "status": "  "})
        assert r.status_code == 400

    def test_tache_inconnue_404(self, auth_client):
        r = _post(auth_client, "/tasks/99999999/roles/add", {"status": "R"})
        assert r.status_code == 404
