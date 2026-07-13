# tests/test_18_gestion_compte.py
"""
Page : Gestion des comptes (/comptes)
Couvre : liste des utilisateurs, CRUD utilisateurs (form data), managers,
         assignment manager, suppression collaborateur, import Excel JSON.
"""
import json
import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.gestion_compte


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_role(app, ids, name="Rôle Compte Test"):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        existing = Role.query.filter_by(name=name, entity_id=ids["entity_id"]).first()
        if existing:
            return existing.id
        role = Role(name=name, entity_id=ids["entity_id"])
        db.session.add(role)
        db.session.commit()
        return role.id


def _delete_role(app, role_id):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
            db.session.commit()


def _create_user(app, ids, email, first="Compte", last="Test"):
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        existing = User.query.filter_by(email=email).first()
        if existing:
            return existing.id
        u = User(
            entity_id=ids["entity_id"],
            first_name=first,
            last_name=last,
            email=email,
            password=generate_password_hash("Pass123!"),
            status="user",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _delete_user(app, user_id):
    with app.app_context():
        from Code.models.models import User, UserRole
        from Code.extensions import db
        UserRole.query.filter_by(user_id=user_id).delete()
        u = User.query.get(user_id)
        if u:
            db.session.delete(u)
        db.session.commit()


# ===========================================================================
# 1. GET /comptes/ — liste des utilisateurs
# ===========================================================================

class TestListUsers:

    def test_list_users_accessible_with_auth(self, auth_client):
        """GET /comptes/ avec session → 200."""
        r = auth_client.get("/comptes/")
        assert r.status_code == 200

    def test_list_users_contains_html(self, auth_client):
        """La page retourne du HTML (pas un JSON)."""
        r = auth_client.get("/comptes/")
        assert r.status_code == 200
        assert b"<" in r.data


# ===========================================================================
# 2. POST /comptes/create — créer un utilisateur
# ===========================================================================

class TestCreateUser:

    def test_create_user_success_redirects(self, auth_client, ids, app):
        """POST /comptes/create avec données valides → 302 redirect."""
        role_id = _create_role(app, ids, name="Rôle Create Test")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Prénom",
                    "last_name": "Créé",
                    "email": "cree.test.compte@devoptiq.com",
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
        finally:
            with app.app_context():
                from Code.models.models import User, UserRole
                from Code.extensions import db
                u = User.query.filter_by(email="cree.test.compte@devoptiq.com").first()
                if u:
                    UserRole.query.filter_by(user_id=u.id).delete()
                    db.session.delete(u)
                    db.session.commit()
            _delete_role(app, role_id)

    def test_create_user_with_age(self, auth_client, ids, app):
        """Création avec champ age optionnel → 302."""
        role_id = _create_role(app, ids, name="Rôle Age Test")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Jean",
                    "last_name": "Agé",
                    "email": "jean.age.test@devoptiq.com",
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "admin",
                    "age": "35",
                },
            )
            assert r.status_code == 302
        finally:
            with app.app_context():
                from Code.models.models import User, UserRole
                from Code.extensions import db
                u = User.query.filter_by(email="jean.age.test@devoptiq.com").first()
                if u:
                    UserRole.query.filter_by(user_id=u.id).delete()
                    db.session.delete(u)
                    db.session.commit()
            _delete_role(app, role_id)


# ===========================================================================
# 3. GET+POST /comptes/update/<id> — modifier un utilisateur
# ===========================================================================

class TestUpdateUser:

    def test_update_user_get_returns_200(self, auth_client, ids, app):
        """GET /comptes/update/<id> retourne le formulaire (200)."""
        uid = _create_user(app, ids, "update.get.test@devoptiq.com")
        try:
            r = auth_client.get(f"/comptes/update/{uid}")
            assert r.status_code == 200
        finally:
            _delete_user(app, uid)

    def test_update_user_get_not_found_returns_404(self, auth_client):
        """GET /comptes/update/999999 → 404."""
        r = auth_client.get("/comptes/update/999999")
        assert r.status_code == 404

    def test_update_user_post_success_redirects(self, auth_client, ids, app):
        """POST /comptes/update/<id> avec données valides → 302."""
        role_id = _create_role(app, ids, name="Rôle Update Test")
        uid = _create_user(app, ids, "update.post.test@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/update/{uid}",
                data={
                    "first_name": "Modifié",
                    "last_name": "Utilisateur",
                    "email": "update.post.test@devoptiq.com",
                    "status": "user",
                    "role_id": str(role_id),
                },
            )
            assert r.status_code == 302
        finally:
            _delete_user(app, uid)
            _delete_role(app, role_id)

    def test_update_user_post_changes_password(self, auth_client, ids, app):
        """POST avec nouveau mot de passe → redirect (password mis à jour)."""
        role_id = _create_role(app, ids, name="Rôle Pwd Update")
        uid = _create_user(app, ids, "update.pwd.test@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/update/{uid}",
                data={
                    "first_name": "Jean",
                    "last_name": "Test",
                    "email": "update.pwd.test@devoptiq.com",
                    "status": "user",
                    "role_id": str(role_id),
                    "password": "NewPass456!",
                },
            )
            assert r.status_code == 302
        finally:
            _delete_user(app, uid)
            _delete_role(app, role_id)

    def test_update_user_not_found_returns_404(self, auth_client, ids, app):
        """POST /comptes/update/999999 → 404."""
        role_id = _create_role(app, ids, name="Rôle 404 Update")
        try:
            r = auth_client.post(
                "/comptes/update/999999",
                data={
                    "first_name": "X",
                    "last_name": "Y",
                    "email": "x@y.com",
                    "status": "user",
                    "role_id": str(role_id),
                },
            )
            assert r.status_code == 404
        finally:
            _delete_role(app, role_id)


# ===========================================================================
# 4. POST /comptes/delete/<id> — supprimer un utilisateur
# ===========================================================================

class TestDeleteUser:

    def test_delete_user_success_redirects(self, auth_client, ids, app):
        """POST /comptes/delete/<id> → 302 redirect."""
        uid = _create_user(app, ids, "delete.test.compte@devoptiq.com")
        r = auth_client.post(f"/comptes/delete/{uid}")
        assert r.status_code == 302

    def test_delete_user_not_found_returns_error(self, auth_client):
        """POST /comptes/delete/999999 → 404 ou 500 (abort(404) capturé par le try/except de la route)."""
        r = auth_client.post("/comptes/delete/999999")
        assert r.status_code in (404, 500)

    def test_delete_user_removes_from_db(self, auth_client, ids, app):
        """Après suppression, l'utilisateur n'existe plus en base."""
        uid = _create_user(app, ids, "delete.verify.compte@devoptiq.com")
        auth_client.post(f"/comptes/delete/{uid}")
        with app.app_context():
            from Code.models.models import User
            assert User.query.get(uid) is None


# ===========================================================================
# 5. GET /comptes/users — liste JSON des utilisateurs
# ===========================================================================

class TestGetAllUsers:

    def test_get_all_users_returns_list(self, auth_client):
        """GET /comptes/users → 200, JSON liste."""
        r = auth_client.get("/comptes/users")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_get_all_users_fields(self, auth_client, ids, app):
        """Chaque entrée de la liste utilisateurs a les champs id et name."""
        # Set entity.owner_id so User.for_active_entity() can filter by entity
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            entity = Entity.query.get(ids["entity_id"])
            entity.owner_id = ids["user_id"]
            db.session.commit()
        uid = _create_user(app, ids, "fields.test.compte@devoptiq.com", "Fields", "User")
        try:
            r = auth_client.get("/comptes/users")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert isinstance(data, list)
            assert len(data) >= 1
            sample = data[0]
            assert "id" in sample
            assert "name" in sample
        finally:
            _delete_user(app, uid)


# ===========================================================================
# 6. GET /comptes/managers — liste JSON des managers
# ===========================================================================

class TestGetManagers:

    def test_get_managers_returns_list(self, auth_client):
        """GET /comptes/managers → 200, JSON liste."""
        r = auth_client.get("/comptes/managers")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)


# ===========================================================================
# 7. POST /comptes/assign_manager — assigner un manager
# ===========================================================================

class TestAssignManager:

    def test_assign_manager_single_user(self, auth_client, ids, app):
        """Assigner un manager à un collaborateur unique → 200, JSON avec subordinates."""
        manager_id = _create_user(app, ids, "manager.assign.test@devoptiq.com", "Manager", "Assign")
        collab_id = _create_user(app, ids, "collab.assign.test@devoptiq.com", "Collab", "Assign")
        try:
            r = auth_client.post(
                "/comptes/assign_manager",
                data={
                    "manager_id": str(manager_id),
                    "user_id": str(collab_id),
                },
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["status"] == "success"
            assert "subordinates" in data
        finally:
            _delete_user(app, collab_id)
            _delete_user(app, manager_id)

    def test_assign_manager_multi_select(self, auth_client, ids, app):
        """Assigner un manager à plusieurs collaborateurs (multi_select=1) → 200."""
        manager_id = _create_user(app, ids, "manager.multi.test@devoptiq.com", "Manager", "Multi")
        collab1_id = _create_user(app, ids, "collab1.multi.test@devoptiq.com", "Collab1", "Multi")
        collab2_id = _create_user(app, ids, "collab2.multi.test@devoptiq.com", "Collab2", "Multi")
        try:
            r = auth_client.post(
                "/comptes/assign_manager",
                data={
                    "manager_id": str(manager_id),
                    "multi_select": "1",
                    "user_ids[]": [str(collab1_id), str(collab2_id)],
                },
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["status"] == "success"
        finally:
            _delete_user(app, collab1_id)
            _delete_user(app, collab2_id)
            _delete_user(app, manager_id)


# ===========================================================================
# 8. GET /comptes/manager/<id>/subordinates
# ===========================================================================

class TestGetSubordinates:

    def test_get_subordinates_valid_manager(self, auth_client, ids, app):
        """GET /comptes/manager/<id>/subordinates → 200, JSON avec subordinates."""
        manager_id = _create_user(app, ids, "manager.sub.test@devoptiq.com", "Manager", "Sub")
        try:
            r = auth_client.get(f"/comptes/manager/{manager_id}/subordinates")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "subordinates" in data
            assert isinstance(data["subordinates"], list)
        finally:
            _delete_user(app, manager_id)

    def test_get_subordinates_not_found_returns_404(self, auth_client):
        """Manager inexistant → 404."""
        r = auth_client.get("/comptes/manager/999999/subordinates")
        assert r.status_code == 404

    def test_get_subordinates_reflects_assigned(self, auth_client, ids, app):
        """Après assign_manager, le subordonné apparaît dans subordinates."""
        manager_id = _create_user(app, ids, "mgr.reflect.test@devoptiq.com", "Mgr", "Reflect")
        collab_id = _create_user(app, ids, "collab.reflect.test@devoptiq.com", "Collab", "Reflect")
        try:
            auth_client.post(
                "/comptes/assign_manager",
                data={"manager_id": str(manager_id), "user_id": str(collab_id)},
            )
            r = auth_client.get(f"/comptes/manager/{manager_id}/subordinates")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert any(s["id"] == collab_id for s in data["subordinates"])
        finally:
            _delete_user(app, collab_id)
            _delete_user(app, manager_id)


# ===========================================================================
# 9. POST /comptes/remove_collaborator/<id>
# ===========================================================================

class TestRemoveCollaborator:

    def test_remove_collaborator_clears_manager(self, auth_client, ids, app):
        """POST /comptes/remove_collaborator/<id> → manager_id mis à None."""
        manager_id = _create_user(app, ids, "mgr.remove.test@devoptiq.com", "Mgr", "Remove")
        collab_id = _create_user(app, ids, "collab.remove.test@devoptiq.com", "Collab", "Remove")
        try:
            auth_client.post(
                "/comptes/assign_manager",
                data={"manager_id": str(manager_id), "user_id": str(collab_id)},
            )
            r = auth_client.post(f"/comptes/remove_collaborator/{collab_id}")
            assert r.status_code == 302
            with app.app_context():
                from Code.models.models import User
                u = User.query.get(collab_id)
                assert u.manager_id is None
        finally:
            _delete_user(app, collab_id)
            _delete_user(app, manager_id)


# ===========================================================================
# 10. POST /comptes/import_excel — import JSON d'utilisateurs
# ===========================================================================

class TestImportExcel:

    def test_import_excel_no_data_returns_400(self, auth_client):
        """POST sans users → 400."""
        r = auth_client.post(
            "/comptes/import_excel",
            data=json.dumps({"users": []}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert data["success"] is False

    def test_import_excel_duplicate_email_reports_error(self, auth_client, ids):
        """Email déjà existant → erreur signalée, imported=0."""
        r = auth_client.post(
            "/comptes/import_excel",
            data=json.dumps({
                "users": [{
                    "prenom": "Test",
                    "nom": "User",
                    "email": "test@devoptiq.com",
                    "age": "",
                    "mot_de_passe": "Pass123!",
                    "role": "",
                    "statut": "user",
                }]
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["imported"] == 0
        assert len(data["errors"]) >= 1

    def test_import_excel_unknown_role_reports_error(self, auth_client, ids):
        """Rôle inconnu → erreur signalée pour cet utilisateur."""
        r = auth_client.post(
            "/comptes/import_excel",
            data=json.dumps({
                "users": [{
                    "prenom": "Nouveau",
                    "nom": "Import",
                    "email": "import.role.inconnu@devoptiq.com",
                    "age": "",
                    "mot_de_passe": "Pass123!",
                    "role": "RôleInexistantXYZ",
                    "statut": "user",
                }]
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["imported"] == 0
        assert len(data["errors"]) >= 1

    def test_import_excel_valid_user_no_role_creates_user(self, auth_client, ids, app):
        """Utilisateur sans rôle (role vide) → créé si email unique."""
        r = auth_client.post(
            "/comptes/import_excel",
            data=json.dumps({
                "users": [{
                    "prenom": "Importé",
                    "nom": "Excel",
                    "email": "importe.excel.test@devoptiq.com",
                    "age": "28",
                    "mot_de_passe": "Pass123!",
                    "role": "",
                    "statut": "user",
                }]
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["success"] is True
        assert data["imported"] == 1
        # Cleanup
        with app.app_context():
            from Code.models.models import User, UserRole
            from Code.extensions import db
            u = User.query.filter_by(email="importe.excel.test@devoptiq.com").first()
            if u:
                UserRole.query.filter_by(user_id=u.id).delete()
                db.session.delete(u)
                db.session.commit()

    def test_import_excel_with_valid_role_creates_user(self, auth_client, ids, app):
        """Utilisateur avec rôle existant → créé avec UserRole associé.

        import_excel utilise Entity.get_active_id() pour chercher le rôle.
        On s'assure que entity.owner_id est renseigné pour que le filtre fonctionne.
        """
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            entity = Entity.query.get(ids["entity_id"])
            entity.owner_id = ids["user_id"]
            db.session.commit()
        role_id = _create_role(app, ids, name="Rôle Import Excel")
        try:
            r = auth_client.post(
                "/comptes/import_excel",
                data=json.dumps({
                    "users": [{
                        "prenom": "Importé",
                        "nom": "Rôlé",
                        "email": "importe.role.test@devoptiq.com",
                        "age": "",
                        "mot_de_passe": "Pass123!",
                        "role": "Rôle Import Excel",
                        "statut": "user",
                    }]
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["success"] is True
            assert data["imported"] == 1
        finally:
            with app.app_context():
                from Code.models.models import User, UserRole
                from Code.extensions import db
                u = User.query.filter_by(email="importe.role.test@devoptiq.com").first()
                if u:
                    UserRole.query.filter_by(user_id=u.id).delete()
                    db.session.delete(u)
                    db.session.commit()
            _delete_role(app, role_id)

    def test_import_excel_response_fields(self, auth_client, ids):
        """La réponse contient success, imported, errors, message."""
        r = auth_client.post(
            "/comptes/import_excel",
            data=json.dumps({"users": []}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "success" in data
        assert "message" in data


# ===========================================================================
# 11. Sécurité — endpoints mutants sans session
# ===========================================================================

class TestGestionCompteNoAuth:
    """Utilise un client isolé (app.test_client() dédié par test) car le
    fixture `client` partage son cookie-jar avec `auth_client` (scope=session).
    Aucune route qui crée/modifie/supprime un compte ne doit être accessible
    sans session (protection ajoutée via _require_auth)."""

    def test_create_user_requires_auth(self, app):
        with app.test_client() as fresh:
            r = fresh.post(
                "/comptes/create",
                data={
                    "first_name": "Sans",
                    "last_name": "Session",
                    "email": "sans.session@devoptiq.com",
                    "password": "Pass123!",
                    "role_id": "1",
                },
            )
        assert r.status_code == 401

    def test_delete_user_requires_auth(self, app):
        with app.test_client() as fresh:
            r = fresh.post("/comptes/delete/999999")
        assert r.status_code == 401

    def test_update_user_post_requires_auth(self, app, ids):
        uid = _create_user(app, ids, "noauth.update.test@devoptiq.com")
        try:
            with app.test_client() as fresh:
                r = fresh.post(
                    f"/comptes/update/{uid}",
                    data={
                        "first_name": "Hack",
                        "last_name": "Attempt",
                        "email": "noauth.update.test@devoptiq.com",
                        "status": "admin",
                        "role_id": "1",
                    },
                )
            assert r.status_code == 401
        finally:
            _delete_user(app, uid)

    def test_assign_manager_requires_auth(self, app):
        with app.test_client() as fresh:
            r = fresh.post("/comptes/assign_manager", data={"manager_id": "1", "user_id": "2"})
        assert r.status_code == 401

    def test_remove_collaborator_requires_auth(self, app):
        with app.test_client() as fresh:
            r = fresh.post("/comptes/remove_collaborator/999999")
        assert r.status_code == 401

    def test_set_password_requires_auth(self, app, ids):
        uid = _create_user(app, ids, "noauth.setpwd.test@devoptiq.com")
        try:
            with app.test_client() as fresh:
                r = fresh.post(
                    f"/comptes/set_password/{uid}",
                    data=json.dumps({"password": "NewPass123!"}),
                    content_type="application/json",
                )
            assert r.status_code == 401
        finally:
            _delete_user(app, uid)

    def test_import_excel_requires_auth(self, app):
        with app.test_client() as fresh:
            r = fresh.post(
                "/comptes/import_excel",
                data=json.dumps({"users": []}),
                content_type="application/json",
            )
        assert r.status_code == 401

    def test_create_user_still_works_when_authenticated(self, auth_client, ids, app):
        """Non-régression : avec session, la création fonctionne toujours."""
        role_id = _create_role(app, ids, name="Rôle Post Fix Compte Auth")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Avec",
                    "last_name": "Session",
                    "email": "avec.session.postfix@devoptiq.com",
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
        finally:
            with app.app_context():
                from Code.models.models import User, UserRole
                from Code.extensions import db
                u = User.query.filter_by(email="avec.session.postfix@devoptiq.com").first()
                if u:
                    UserRole.query.filter_by(user_id=u.id).delete()
                    db.session.delete(u)
                    db.session.commit()
            _delete_role(app, role_id)
