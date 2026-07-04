# tests/test_49_tasks_avance.py
"""
Page : Tâches — CRUD complet & gestion des rôles avancée (tasks.py)
Couvre :
  - POST /tasks/add                           → création avec champs optionnels
  - PUT  /tasks/<id>                          → mise à jour & persistance en DB
  - DELETE /tasks/<id>                        → suppression & vérification DB
  - POST /tasks/<id>/roles/add                → ajout rôle (existant / nouveau / doublon)
  - GET  /tasks/<id>/roles                    → liste des rôles de la tâche
  - DELETE /tasks/<id>/roles/<role_id>        → dissociation rôle
  - GET /tasks/<activity_id>/render           → rendu HTML partiel
"""
import json
import pytest

pytestmark = pytest.mark.tasks_avance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client, url, payload):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


def _put(client, url, payload):
    return client.put(
        url,
        data=json.dumps(payload),
        content_type="application/json",
    )


def _create_task(app, ids, name="Tâche Test Avancé", description="", order=None):
    """Insère une tâche en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Task
        from Code.extensions import db
        t = Task(
            name=name,
            description=description,
            order=order,
            activity_id=ids["activity_id"],
        )
        db.session.add(t)
        db.session.commit()
        return t.id


def _delete_task(app, task_id):
    """Supprime une tâche de test (nettoyage sûr)."""
    with app.app_context():
        from Code.models.models import Task
        from Code.extensions import db
        from sqlalchemy import text
        db.session.execute(
            text("DELETE FROM task_roles WHERE task_id = :tid"),
            {"tid": task_id},
        )
        t = Task.query.get(task_id)
        if t:
            db.session.delete(t)
        db.session.commit()


def _create_role(app, name="Rôle Test Avancé"):
    """Insère un rôle en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        r = Role(name=name)
        db.session.add(r)
        db.session.commit()
        return r.id


def _delete_role(app, role_id):
    """Supprime un rôle de test."""
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        from sqlalchemy import text
        db.session.execute(
            text("DELETE FROM task_roles WHERE role_id = :rid"),
            {"rid": role_id},
        )
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
        db.session.commit()


# ===========================================================================
# 1. POST /tasks/add — Création de tâche
# ===========================================================================

class TestTaskCreate:

    def test_create_returns_201(self, auth_client, ids):
        """POST /tasks/add crée une tâche et retourne 201."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche Création 201",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201

    def test_create_response_has_id(self, auth_client, ids, app):
        """La réponse de création contient un champ 'id'."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche ID Test",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = r.get_json()
        assert "id" in data
        _delete_task(app, data["id"])

    def test_create_response_has_name(self, auth_client, ids, app):
        """La réponse contient le nom exact de la tâche créée."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche Nom Précis",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data["name"] == "Tâche Nom Précis"
        _delete_task(app, data["id"])

    def test_create_persists_in_db(self, auth_client, ids, app):
        """La tâche créée via API est bien présente en base."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche Persistance",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        task_id = r.get_json()["id"]
        try:
            with app.app_context():
                from Code.models.models import Task
                t = Task.query.get(task_id)
                assert t is not None
                assert t.name == "Tâche Persistance"
        finally:
            _delete_task(app, task_id)

    def test_create_with_description(self, auth_client, ids, app):
        """Le champ description est optionnel et correctement enregistré."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche Avec Desc",
            "description": "Description complète",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data.get("description") == "Description complète"
        _delete_task(app, data["id"])

    def test_create_with_order(self, auth_client, ids, app):
        """Le champ order est optionnel et correctement enregistré."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche Avec Ordre",
            "order": 5,
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data.get("order") == 5
        _delete_task(app, data["id"])

    def test_create_missing_name_returns_400(self, auth_client, ids):
        """L'absence de 'name' retourne 400."""
        r = _post(auth_client, "/tasks/add", {
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 400

    def test_create_missing_activity_id_returns_400(self, auth_client):
        """L'absence de 'activity_id' retourne 400."""
        r = _post(auth_client, "/tasks/add", {"name": "Sans Activité"})
        assert r.status_code == 400

    def test_create_activity_not_found_returns_404(self, auth_client):
        """Un activity_id inexistant retourne 404."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Activité Fantôme",
            "activity_id": 999999,
        })
        assert r.status_code == 404

    def test_create_response_contains_activity_id(self, auth_client, ids, app):
        """La réponse contient l'activity_id de rattachement."""
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche Activity Ref",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data.get("activity_id") == ids["activity_id"]
        _delete_task(app, data["id"])


# ===========================================================================
# 2. PUT /tasks/<task_id> — Mise à jour de tâche
# ===========================================================================

class TestTaskUpdate:

    def test_update_name_returns_200(self, auth_client, app, ids):
        """PUT /tasks/<id> avec un nouveau nom retourne 200."""
        tid = _create_task(app, ids, name="Tâche Avant Update")
        try:
            r = _put(auth_client, f"/tasks/{tid}", {"name": "Tâche Après Update"})
            assert r.status_code == 200
        finally:
            _delete_task(app, tid)

    def test_update_name_persists_in_db(self, auth_client, app, ids):
        """Le nouveau nom est bien enregistré en base."""
        tid = _create_task(app, ids, name="Tâche Ancienne")
        try:
            _put(auth_client, f"/tasks/{tid}", {"name": "Tâche Nouvelle"})
            with app.app_context():
                from Code.models.models import Task
                t = Task.query.get(tid)
                assert t.name == "Tâche Nouvelle"
        finally:
            _delete_task(app, tid)

    def test_update_description_persists_in_db(self, auth_client, app, ids):
        """La description mise à jour est bien enregistrée en base."""
        tid = _create_task(app, ids, name="Tâche Desc Update")
        try:
            _put(auth_client, f"/tasks/{tid}", {"description": "Nouvelle description"})
            with app.app_context():
                from Code.models.models import Task
                t = Task.query.get(tid)
                assert t.description == "Nouvelle description"
        finally:
            _delete_task(app, tid)

    def test_update_response_contains_new_name(self, auth_client, app, ids):
        """La réponse JSON contient le nom mis à jour."""
        tid = _create_task(app, ids, name="Tâche Response Test")
        try:
            r = _put(auth_client, f"/tasks/{tid}", {"name": "Tâche Renommée"})
            assert r.status_code == 200
            data = r.get_json()
            assert data.get("name") == "Tâche Renommée"
        finally:
            _delete_task(app, tid)

    def test_update_not_found_returns_404(self, auth_client):
        """PUT sur un task_id inexistant retourne 404."""
        r = _put(auth_client, "/tasks/999999", {"name": "Fantôme"})
        assert r.status_code == 404

    def test_update_no_body_returns_400(self, auth_client, app, ids):
        """PUT sans body JSON retourne 400."""
        tid = _create_task(app, ids, name="Tâche No Body")
        try:
            r = auth_client.put(f"/tasks/{tid}")
            assert r.status_code == 400
        finally:
            _delete_task(app, tid)

    def test_update_wrong_content_type_returns_400_not_500(self, auth_client, app, ids):
        """PUT avec un Content-Type non-JSON et un corps non-vide retourne 400 (pas 415/500)."""
        tid = _create_task(app, ids, name="Tâche Wrong Content-Type")
        try:
            r = auth_client.put(
                f"/tasks/{tid}",
                data="name=Ignoré",
                content_type="text/plain",
            )
            assert r.status_code == 400
        finally:
            _delete_task(app, tid)

    def test_update_partial_only_name(self, auth_client, app, ids):
        """PUT avec seulement 'name' ne modifie pas la description existante."""
        tid = _create_task(app, ids, name="Tâche Partial", description="Desc originale")
        try:
            _put(auth_client, f"/tasks/{tid}", {"name": "Tâche Partial Renommée"})
            with app.app_context():
                from Code.models.models import Task
                t = Task.query.get(tid)
                assert t.description == "Desc originale"
        finally:
            _delete_task(app, tid)


# ===========================================================================
# 3. DELETE /tasks/<task_id> — Suppression de tâche
# ===========================================================================

class TestTaskDelete:

    def test_delete_success_returns_200(self, auth_client, app, ids):
        """DELETE /tasks/<id> sur une tâche existante retourne 200."""
        tid = _create_task(app, ids, name="Tâche À Supprimer")
        r = auth_client.delete(f"/tasks/{tid}")
        assert r.status_code == 200

    def test_delete_removes_from_db(self, auth_client, app, ids):
        """La tâche supprimée n'existe plus en base."""
        tid = _create_task(app, ids, name="Tâche Suppression DB")
        auth_client.delete(f"/tasks/{tid}")
        with app.app_context():
            from Code.models.models import Task
            assert Task.query.get(tid) is None

    def test_delete_response_has_message(self, auth_client, app, ids):
        """La réponse de suppression contient un champ 'message'."""
        tid = _create_task(app, ids, name="Tâche Message Delete")
        r = auth_client.delete(f"/tasks/{tid}")
        assert r.status_code == 200
        data = r.get_json()
        assert "message" in data

    def test_double_delete_returns_404(self, auth_client, app, ids):
        """Supprimer deux fois la même tâche → 404 au second appel."""
        tid = _create_task(app, ids, name="Tâche Double Delete")
        auth_client.delete(f"/tasks/{tid}")
        r = auth_client.delete(f"/tasks/{tid}")
        assert r.status_code == 404

    def test_delete_not_found_returns_404(self, auth_client):
        """DELETE sur un ID inexistant retourne 404."""
        r = auth_client.delete("/tasks/999999")
        assert r.status_code == 404

    def test_delete_cascades_task_roles(self, auth_client, app, ids):
        """Supprimer une tâche efface aussi ses associations task_roles."""
        tid = _create_task(app, ids, name="Tâche Cascade Rôles")
        # Associer un rôle avant la suppression
        rid = _create_role(app, name="Rôle Cascade Delete")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            auth_client.delete(f"/tasks/{tid}")
            with app.app_context():
                from sqlalchemy import text
                from Code.extensions import db
                count = db.session.execute(
                    text("SELECT COUNT(*) FROM task_roles WHERE task_id = :tid"),
                    {"tid": tid},
                ).scalar()
                assert count == 0
        finally:
            _delete_role(app, rid)


# ===========================================================================
# 4. POST /tasks/<task_id>/roles/add — Association de rôles
# ===========================================================================

class TestTaskRolesAdd:

    def test_add_existing_role_by_id_returns_200(self, auth_client, app, ids):
        """Ajouter un rôle existant via existing_role_ids → 200."""
        tid = _create_task(app, ids, name="Tâche Role Add Existant")
        rid = _create_role(app, name="Rôle Existant Add")
        try:
            r = _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            assert r.status_code == 200
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_add_existing_role_response_has_added_roles(self, auth_client, app, ids):
        """La réponse contient la clé 'added_roles' avec le rôle ajouté."""
        tid = _create_task(app, ids, name="Tâche Role Resp")
        rid = _create_role(app, name="Rôle Resp Add")
        try:
            r = _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            assert r.status_code == 200
            data = r.get_json()
            assert "added_roles" in data
            assert len(data["added_roles"]) == 1
            assert data["added_roles"][0]["id"] == rid
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_add_new_role_by_name_creates_and_associates(self, auth_client, app, ids):
        """Ajouter un rôle via new_roles crée le rôle et l'associe."""
        tid = _create_task(app, ids, name="Tâche Role Nouveau")
        role_name = "Rôle Nouveau Via API Avancé"
        try:
            r = _post(auth_client, f"/tasks/{tid}/roles/add", {
                "new_roles": [role_name],
                "status": "Support",
            })
            assert r.status_code == 200
            data = r.get_json()
            assert "added_roles" in data
            assert len(data["added_roles"]) == 1
            assert data["added_roles"][0]["name"] == role_name
        finally:
            # Nettoyer le rôle créé
            with app.app_context():
                from Code.models.models import Role
                r_obj = Role.query.filter_by(name=role_name).first()
                if r_obj:
                    _delete_role(app, r_obj.id)
            _delete_task(app, tid)

    def test_add_role_status_is_stored(self, auth_client, app, ids):
        """Le status passé est bien enregistré dans task_roles."""
        tid = _create_task(app, ids, name="Tâche Role Status")
        rid = _create_role(app, name="Rôle Status Test")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Garant",
            })
            with app.app_context():
                from sqlalchemy import text
                from Code.extensions import db
                row = db.session.execute(
                    text("SELECT status FROM task_roles WHERE task_id=:tid AND role_id=:rid"),
                    {"tid": tid, "rid": rid},
                ).fetchone()
                assert row is not None
                assert row[0] == "Garant"
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_add_duplicate_role_not_duplicated(self, auth_client, app, ids):
        """Ajouter deux fois le même rôle ne crée pas de doublon en DB."""
        tid = _create_task(app, ids, name="Tâche Role Doublon")
        rid = _create_role(app, name="Rôle Doublon")
        try:
            payload = {"existing_role_ids": [rid], "status": "Réalisateur"}
            _post(auth_client, f"/tasks/{tid}/roles/add", payload)
            r = _post(auth_client, f"/tasks/{tid}/roles/add", payload)
            assert r.status_code == 200
            data = r.get_json()
            # Au second appel, added_roles doit être vide (déjà présent)
            assert data["added_roles"] == []
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_add_role_missing_status_returns_400(self, auth_client, app, ids):
        """L'absence de 'status' retourne 400."""
        tid = _create_task(app, ids, name="Tâche Role Sans Status")
        rid = _create_role(app, name="Rôle Sans Status")
        try:
            r = _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
            })
            assert r.status_code == 400
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_add_role_empty_status_returns_400(self, auth_client, app, ids):
        """Un status vide (chaîne) retourne 400."""
        tid = _create_task(app, ids, name="Tâche Role Status Vide")
        rid = _create_role(app, name="Rôle Status Vide")
        try:
            r = _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "",
            })
            assert r.status_code == 400
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_add_role_task_not_found_returns_404(self, auth_client):
        """Ajouter un rôle sur une tâche inexistante → 404."""
        r = _post(auth_client, "/tasks/999999/roles/add", {
            "existing_role_ids": [1],
            "status": "Réalisateur",
        })
        assert r.status_code == 404

    def test_add_role_response_has_task_id(self, auth_client, app, ids):
        """La réponse contient le task_id de la tâche modifiée."""
        tid = _create_task(app, ids, name="Tâche Role Task ID")
        rid = _create_role(app, name="Rôle Task ID")
        try:
            r = _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            assert r.status_code == 200
            data = r.get_json()
            assert data.get("task_id") == tid
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)


# ===========================================================================
# 5. GET /tasks/<task_id>/roles — Liste des rôles d'une tâche
# ===========================================================================

class TestTaskRolesGet:

    def test_get_roles_empty_returns_200(self, auth_client, app, ids):
        """GET /tasks/<id>/roles sur tâche sans rôle → 200 + liste vide."""
        tid = _create_task(app, ids, name="Tâche Sans Rôle Get")
        try:
            r = auth_client.get(f"/tasks/{tid}/roles")
            assert r.status_code == 200
            data = r.get_json()
            assert data["roles"] == []
        finally:
            _delete_task(app, tid)

    def test_get_roles_returns_dict_with_keys(self, auth_client, app, ids):
        """La réponse contient 'task_id' et 'roles'."""
        tid = _create_task(app, ids, name="Tâche Roles Clés")
        try:
            r = auth_client.get(f"/tasks/{tid}/roles")
            assert r.status_code == 200
            data = r.get_json()
            assert "task_id" in data
            assert "roles" in data
            assert data["task_id"] == tid
        finally:
            _delete_task(app, tid)

    def test_get_roles_not_found_returns_404(self, auth_client):
        """GET /tasks/999999/roles retourne 404."""
        r = auth_client.get("/tasks/999999/roles")
        assert r.status_code == 404

    def test_get_roles_shows_assigned_role(self, auth_client, app, ids):
        """Un rôle ajouté apparaît dans la liste GET."""
        tid = _create_task(app, ids, name="Tâche Roles Affichage")
        rid = _create_role(app, name="Rôle Affiché Get")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            r = auth_client.get(f"/tasks/{tid}/roles")
            assert r.status_code == 200
            roles = r.get_json()["roles"]
            assert any(ro["id"] == rid for ro in roles)
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_get_roles_has_status_field(self, auth_client, app, ids):
        """Chaque rôle dans la liste contient un champ 'status'."""
        tid = _create_task(app, ids, name="Tâche Roles Status Field")
        rid = _create_role(app, name="Rôle Status Field Get")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Support",
            })
            r = auth_client.get(f"/tasks/{tid}/roles")
            assert r.status_code == 200
            roles = r.get_json()["roles"]
            assert len(roles) >= 1
            for ro in roles:
                assert "status" in ro
                assert "id" in ro
                assert "name" in ro
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_get_roles_status_matches_added(self, auth_client, app, ids):
        """Le status retourné correspond au status assigné."""
        tid = _create_task(app, ids, name="Tâche Status Match")
        rid = _create_role(app, name="Rôle Status Match")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Expert",
            })
            r = auth_client.get(f"/tasks/{tid}/roles")
            roles = r.get_json()["roles"]
            found = next((ro for ro in roles if ro["id"] == rid), None)
            assert found is not None
            assert found["status"] == "Expert"
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)


# ===========================================================================
# 6. DELETE /tasks/<task_id>/roles/<role_id> — Dissociation de rôle
# ===========================================================================

class TestTaskRolesDelete:

    def test_delete_role_success_returns_200(self, auth_client, app, ids):
        """DELETE /tasks/<id>/roles/<role_id> retourne 200."""
        tid = _create_task(app, ids, name="Tâche Dissociation Rôle")
        rid = _create_role(app, name="Rôle À Dissocier")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            r = auth_client.delete(f"/tasks/{tid}/roles/{rid}")
            assert r.status_code == 200
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_delete_role_removes_association(self, auth_client, app, ids):
        """Après dissociation, le rôle n'apparaît plus dans GET /tasks/<id>/roles."""
        tid = _create_task(app, ids, name="Tâche Remove Assoc")
        rid = _create_role(app, name="Rôle Remove Assoc")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            auth_client.delete(f"/tasks/{tid}/roles/{rid}")
            r = auth_client.get(f"/tasks/{tid}/roles")
            roles = r.get_json()["roles"]
            assert not any(ro["id"] == rid for ro in roles)
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_delete_role_not_associated_returns_404(self, auth_client, app, ids):
        """Dissocier un rôle non lié à la tâche → 404."""
        tid = _create_task(app, ids, name="Tâche Rôle Non Lié")
        rid = _create_role(app, name="Rôle Non Lié Delete")
        try:
            r = auth_client.delete(f"/tasks/{tid}/roles/{rid}")
            assert r.status_code == 404
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_delete_role_task_not_found_returns_404(self, auth_client):
        """Tâche inexistante → 404."""
        r = auth_client.delete("/tasks/999999/roles/1")
        assert r.status_code == 404

    def test_delete_role_response_has_message(self, auth_client, app, ids):
        """La réponse de dissociation contient un champ 'message'."""
        tid = _create_task(app, ids, name="Tâche Delete Msg")
        rid = _create_role(app, name="Rôle Delete Msg")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            r = auth_client.delete(f"/tasks/{tid}/roles/{rid}")
            assert r.status_code == 200
            data = r.get_json()
            assert "message" in data
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)

    def test_double_dissociation_returns_404(self, auth_client, app, ids):
        """Dissocier deux fois le même rôle → 404 au second appel."""
        tid = _create_task(app, ids, name="Tâche Double Disso")
        rid = _create_role(app, name="Rôle Double Disso")
        try:
            _post(auth_client, f"/tasks/{tid}/roles/add", {
                "existing_role_ids": [rid],
                "status": "Réalisateur",
            })
            auth_client.delete(f"/tasks/{tid}/roles/{rid}")
            r = auth_client.delete(f"/tasks/{tid}/roles/{rid}")
            assert r.status_code == 404
        finally:
            _delete_task(app, tid)
            _delete_role(app, rid)


# ===========================================================================
# 7. GET /tasks/<activity_id>/render — Rendu partiel HTML
# ===========================================================================

class TestTaskRender:

    def test_render_valid_activity_returns_200(self, auth_client, ids):
        """GET /tasks/<activity_id>/render retourne 200 pour une activité connue."""
        r = auth_client.get(f"/tasks/{ids['activity_id']}/render")
        assert r.status_code == 200

    def test_render_returns_html(self, auth_client, ids):
        """La réponse est du HTML (pas du JSON)."""
        r = auth_client.get(f"/tasks/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert r.content_type.startswith("text/html")

    def test_render_contains_seeded_task(self, auth_client, ids):
        """Le rendu contient le nom de la tâche seed ('Tâche Test')."""
        r = auth_client.get(f"/tasks/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert "Tâche Test".encode("utf-8") in r.data

    def test_render_nonexistent_activity_returns_404(self, auth_client):
        """GET /tasks/999999/render sur activité inexistante → 404."""
        r = auth_client.get("/tasks/999999/render")
        assert r.status_code == 404

    def test_render_with_new_task_shows_it(self, auth_client, app, ids):
        """Une tâche créée apparaît dans le rendu partiel."""
        tid = _create_task(app, ids, name="Tâche Visible Render")
        try:
            r = auth_client.get(f"/tasks/{ids['activity_id']}/render")
            assert r.status_code == 200
            assert "Tâche Visible Render".encode("utf-8") in r.data
        finally:
            _delete_task(app, tid)
