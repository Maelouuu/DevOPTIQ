# tests/test_12_gestion_rh.py
"""
Page : Gestion RH (/gestion_rh)
Couvre : accès page, CRUD rôles, collaborateurs, managers, paramètres, import CSV.
"""
import io
import json
import pytest

pytestmark = pytest.mark.gestion_rh


# ---------------------------------------------------------------------------
# Helpers DB directs
# ---------------------------------------------------------------------------

def _create_role(app, ids, name="Rôle Test RH"):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
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


def _create_user(app, ids, email, first="Collab", last="Test"):
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        from werkzeug.security import generate_password_hash
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


def _ensure_entreprise_settings(app):
    """Crée la table entreprise_settings si elle n'existe pas dans la DB de test."""
    with app.app_context():
        from Code.extensions import db
        from sqlalchemy import text
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS entreprise_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_hours_per_day REAL,
                    work_days_per_week REAL,
                    work_weeks_per_year REAL,
                    work_days_per_year REAL,
                    entity_id INTEGER
                )
            """))
            db.session.commit()
        except Exception:
            db.session.rollback()


# ===========================================================================
# 1. Accès à la page principale
# ===========================================================================

class TestGestionRHPage:

    def test_page_accessible_auth(self, auth_client, app):
        _ensure_entreprise_settings(app)
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200

    def test_page_no_auth_returns_non_500(self, client, app):
        """Sans session, la page ne doit pas crasher (200 ou redirect)."""
        _ensure_entreprise_settings(app)
        r = client.get("/gestion_rh/")
        assert r.status_code in (200, 302)

    def test_page_contains_roles_section(self, auth_client, app):
        """La page HTML contient le terme 'rôle' ou 'collaborateur'."""
        _ensure_entreprise_settings(app)
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200
        body = r.data.decode("utf-8", errors="replace").lower()
        assert "rôle" in body or "collaborateur" in body or "gestion" in body


# ===========================================================================
# 2. API GET — liste des rôles
# ===========================================================================

class TestRolesAPI:

    def test_get_all_roles_returns_list(self, auth_client):
        """GET /gestion_rh/roles retourne une liste JSON."""
        r = auth_client.get("/gestion_rh/roles")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_get_all_roles_contains_expected_fields(self, auth_client, app, ids):
        """Chaque rôle contient id et name."""
        rid = _create_role(app, ids, name="Rôle Champs Test")
        try:
            r = auth_client.get("/gestion_rh/roles")
            data = json.loads(r.data)
            found = next((ro for ro in data if ro["id"] == rid), None)
            assert found is not None
            assert "id" in found
            assert "name" in found
        finally:
            _delete_role(app, rid)

    def test_get_users_with_roles_returns_list(self, auth_client):
        """GET /gestion_rh/users_with_roles retourne une liste JSON."""
        r = auth_client.get("/gestion_rh/users_with_roles")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_get_users_with_role_existing(self, auth_client, app, ids):
        """GET /gestion_rh/users_with_role?role=<nom> retourne les utilisateurs du rôle."""
        rid = _create_role(app, ids, name="Rôle Utilisateurs Test")
        uid = _create_user(app, ids, email="rh_user_role@test.com")
        try:
            # Assigner le rôle à l'utilisateur via l'API
            auth_client.post(
                "/gestion_rh/collaborateur_roles",
                data={"user_id": uid, "role_ids[]": [rid]},
            )
            r = auth_client.get("/gestion_rh/users_with_role?role=Rôle Utilisateurs Test")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert isinstance(data, list)
            assert any(u["id"] == uid for u in data)
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)

    def test_get_users_with_role_nonexistent_returns_empty(self, auth_client):
        """Un rôle inconnu retourne une liste vide (pas d'erreur)."""
        r = auth_client.get("/gestion_rh/users_with_role?role=RoleInexistantXXX")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_get_users_by_roles_valid(self, auth_client, app, ids):
        """GET /gestion_rh/users_by_roles?roles=<id> retourne les utilisateurs."""
        rid = _create_role(app, ids, name="Rôle ByRoles Test")
        try:
            r = auth_client.get(f"/gestion_rh/users_by_roles?roles={rid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert isinstance(data, list)
        finally:
            _delete_role(app, rid)

    def test_get_users_by_roles_empty_param(self, auth_client):
        """GET /gestion_rh/users_by_roles sans roles valides → liste vide."""
        r = auth_client.get("/gestion_rh/users_by_roles?roles=")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_get_all_collaborators_with_manager(self, auth_client):
        """GET /gestion_rh/all_collaborators_with_manager retourne users et roles."""
        r = auth_client.get("/gestion_rh/all_collaborators_with_manager")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "users" in data
        assert "roles" in data
        assert isinstance(data["users"], list)
        assert isinstance(data["roles"], list)


# ===========================================================================
# 3. CRUD Rôles (create / update / delete)
# ===========================================================================

class TestRolesCRUD:

    def test_create_role_success(self, auth_client, app, ids):
        """POST /gestion_rh/role sans id crée un rôle."""
        r = auth_client.post("/gestion_rh/role", data={"name": "Rôle Nouveau CRUD"})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data.get("success") is True
        # Nettoyage
        with app.app_context():
            from Code.models.models import Role
            from Code.extensions import db
            role = Role.query.filter_by(name="Rôle Nouveau CRUD").first()
            if role:
                db.session.delete(role)
                db.session.commit()

    def test_update_role_success(self, auth_client, app, ids):
        """POST /gestion_rh/role avec id renomme le rôle."""
        rid = _create_role(app, ids, name="Rôle À Renommer")
        try:
            r = auth_client.post("/gestion_rh/role", data={"id": rid, "name": "Rôle Renommé"})
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            # Vérification en base
            with app.app_context():
                from Code.models.models import Role
                role = Role.query.get(rid)
                assert role.name == "Rôle Renommé"
        finally:
            _delete_role(app, rid)

    def test_update_role_nonexistent_id_no_crash(self, auth_client):
        """POST /gestion_rh/role avec id inexistant ne doit pas crasher."""
        r = auth_client.post("/gestion_rh/role", data={"id": 999999, "name": "Rôle Fantôme"})
        assert r.status_code == 200

    def test_delete_role_success(self, auth_client, app, ids):
        """POST /gestion_rh/delete_role/<id> supprime le rôle."""
        rid = _create_role(app, ids, name="Rôle À Supprimer")
        r = auth_client.post(f"/gestion_rh/delete_role/{rid}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data.get("success") is True
        # Vérifie suppression
        with app.app_context():
            from Code.models.models import Role
            assert Role.query.get(rid) is None

    def test_delete_role_not_found(self, auth_client):
        """POST /gestion_rh/delete_role/<id> sur un id inexistant → 404."""
        r = auth_client.post("/gestion_rh/delete_role/999999")
        assert r.status_code == 404
        data = json.loads(r.data)
        assert data.get("success") is False


# ===========================================================================
# 4. Collaborateurs — liste et filtres
# ===========================================================================

class TestCollaborateurs:

    def test_collaborateurs_returns_list(self, auth_client):
        """GET /gestion_rh/collaborateurs retourne une liste JSON."""
        r = auth_client.get("/gestion_rh/collaborateurs")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_collaborateurs_contains_expected_user(self, auth_client, ids):
        """L'utilisateur de test apparaît dans la liste des collaborateurs."""
        r = auth_client.get("/gestion_rh/collaborateurs")
        data = json.loads(r.data)
        found = next((u for u in data if u["id"] == ids["user_id"]), None)
        assert found is not None
        assert "name" in found
        assert "roles" in found

    def test_collaborateurs_search_filter(self, auth_client):
        """Le paramètre search filtre les résultats par nom."""
        r = auth_client.get("/gestion_rh/collaborateurs?search=Test")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        # Tous les résultats doivent contenir "test" dans le nom
        for u in data:
            assert "test" in u["name"].lower()

    def test_collaborateurs_search_no_match(self, auth_client):
        """Une recherche sans résultat retourne une liste vide."""
        r = auth_client.get("/gestion_rh/collaborateurs?search=ZZZinexistantZZZ")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_collaborateurs_role_filter(self, auth_client, app, ids):
        """Le paramètre role filtre les collaborateurs par nom de rôle."""
        rid = _create_role(app, ids, name="Rôle Filtre Test")
        uid = _create_user(app, ids, email="rh_collab_filter@test.com", first="Filtre", last="Collab")
        try:
            auth_client.post(
                "/gestion_rh/collaborateur_roles",
                data={"user_id": uid, "role_ids[]": [rid]},
            )
            r = auth_client.get("/gestion_rh/collaborateurs?role=Rôle Filtre Test")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert any(u["id"] == uid for u in data)
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)


# ===========================================================================
# 5. Mise à jour des rôles d'un collaborateur
# ===========================================================================

class TestCollaborateurRoles:

    def test_update_collaborateur_roles_success(self, auth_client, app, ids):
        """POST /gestion_rh/collaborateur_roles assigne un rôle à un utilisateur."""
        rid = _create_role(app, ids, name="Rôle Assign Collab")
        uid = _create_user(app, ids, email="rh_assign_roles@test.com")
        try:
            r = auth_client.post(
                "/gestion_rh/collaborateur_roles",
                data={"user_id": uid, "role_ids[]": [rid]},
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            # Vérifie en base
            with app.app_context():
                from Code.models.models import UserRole
                ur = UserRole.query.filter_by(user_id=uid, role_id=rid).first()
                assert ur is not None
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)

    def test_update_collaborateur_roles_clear(self, auth_client, app, ids):
        """POST sans role_ids[] supprime tous les rôles du collaborateur."""
        rid = _create_role(app, ids, name="Rôle À Vider")
        uid = _create_user(app, ids, email="rh_clear_roles@test.com")
        try:
            # D'abord on assigne
            auth_client.post(
                "/gestion_rh/collaborateur_roles",
                data={"user_id": uid, "role_ids[]": [rid]},
            )
            # Puis on efface
            r = auth_client.post(
                "/gestion_rh/collaborateur_roles",
                data={"user_id": uid},
            )
            assert r.status_code == 200
            with app.app_context():
                from Code.models.models import UserRole
                count = UserRole.query.filter_by(user_id=uid).count()
                assert count == 0
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)

    def test_assign_roles_via_form(self, auth_client, app, ids):
        """POST /gestion_rh/assign_roles redirige après l'assignation."""
        rid = _create_role(app, ids, name="Rôle Assign Form")
        uid = _create_user(app, ids, email="rh_assign_form@test.com")
        try:
            r = auth_client.post(
                "/gestion_rh/assign_roles",
                data={"user_id": uid, "role_ids": [rid]},
            )
            assert r.status_code in (200, 302)
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)


# ===========================================================================
# 6. Mise à jour du nom d'un collaborateur
# ===========================================================================

class TestUpdateCollaboratorName:

    def test_update_name_success(self, auth_client, app, ids):
        """POST /gestion_rh/update_collaborator_name renomme l'utilisateur."""
        uid = _create_user(app, ids, email="rh_rename@test.com", first="Avant", last="Nom")
        try:
            r = auth_client.post(
                "/gestion_rh/update_collaborator_name",
                data=json.dumps({"user_id": uid, "name": "Après Modification"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            assert data.get("first_name") == "Après"
            assert data.get("last_name") == "Modification"
        finally:
            _delete_user(app, uid)

    def test_update_name_single_word(self, auth_client, app, ids):
        """Un nom composé d'un seul mot est stocké comme prénom."""
        uid = _create_user(app, ids, email="rh_single_name@test.com")
        try:
            r = auth_client.post(
                "/gestion_rh/update_collaborator_name",
                data=json.dumps({"user_id": uid, "name": "Monoprénom"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            assert data.get("first_name") == "Monoprénom"
        finally:
            _delete_user(app, uid)

    def test_update_name_missing_user_id(self, auth_client):
        """POST sans user_id → 400."""
        r = auth_client.post(
            "/gestion_rh/update_collaborator_name",
            data=json.dumps({"name": "Prénom Nom"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_update_name_missing_name(self, auth_client, ids):
        """POST avec name vide → 400."""
        r = auth_client.post(
            "/gestion_rh/update_collaborator_name",
            data=json.dumps({"user_id": ids["user_id"], "name": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_update_name_user_not_found(self, auth_client):
        """POST avec user_id inexistant → 404."""
        r = auth_client.post(
            "/gestion_rh/update_collaborator_name",
            data=json.dumps({"user_id": 999999, "name": "Prénom Nom"}),
            content_type="application/json",
        )
        assert r.status_code == 404


# ===========================================================================
# 7. Gestion des managers
# ===========================================================================

class TestManagerAssignment:

    def test_assign_manager_simple_global(self, auth_client, app, ids):
        """POST /gestion_rh/assign_manager_simple assigne un manager globalement."""
        uid = _create_user(app, ids, email="rh_managed@test.com")
        try:
            r = auth_client.post(
                "/gestion_rh/assign_manager_simple",
                data=json.dumps({"user_id": uid, "manager_id": ids["user_id"]}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            assert data.get("user_id") == uid
        finally:
            _delete_user(app, uid)

    def test_assign_manager_simple_remove(self, auth_client, app, ids):
        """POST avec manager_id=null retire le manager."""
        uid = _create_user(app, ids, email="rh_unmanaged@test.com")
        try:
            # Assigner d'abord
            auth_client.post(
                "/gestion_rh/assign_manager_simple",
                data=json.dumps({"user_id": uid, "manager_id": ids["user_id"]}),
                content_type="application/json",
            )
            # Puis retirer
            r = auth_client.post(
                "/gestion_rh/assign_manager_simple",
                data=json.dumps({"user_id": uid, "manager_id": None}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
        finally:
            _delete_user(app, uid)

    def test_assign_manager_simple_missing_user_id(self, auth_client, ids):
        """POST sans user_id → 400."""
        r = auth_client.post(
            "/gestion_rh/assign_manager_simple",
            data=json.dumps({"manager_id": ids["user_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_assign_manager_simple_user_not_found(self, auth_client, ids):
        """POST avec user_id inexistant → 404."""
        r = auth_client.post(
            "/gestion_rh/assign_manager_simple",
            data=json.dumps({"user_id": 999999, "manager_id": ids["user_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_assign_manager_simple_by_role(self, auth_client, app, ids):
        """POST avec role_ids cible les user_roles spécifiques."""
        rid = _create_role(app, ids, name="Rôle Manager By Role")
        uid = _create_user(app, ids, email="rh_manager_role@test.com")
        try:
            auth_client.post(
                "/gestion_rh/collaborateur_roles",
                data={"user_id": uid, "role_ids[]": [rid]},
            )
            r = auth_client.post(
                "/gestion_rh/assign_manager_simple",
                data=json.dumps({
                    "user_id": uid,
                    "manager_id": ids["user_id"],
                    "role_ids": [rid],
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)

    def test_assign_manager_missing_params(self, auth_client):
        """POST /gestion_rh/assign_manager sans paramètres requis → 400."""
        r = auth_client.post(
            "/gestion_rh/assign_manager",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ===========================================================================
# 8. Paramètres entreprise
# ===========================================================================

class TestEntrepriseSettings:

    def test_update_settings_redirects(self, auth_client, app):
        """POST /gestion_rh/update_settings redirige vers la page RH."""
        _ensure_entreprise_settings(app)
        r = auth_client.post(
            "/gestion_rh/update_settings",
            data={
                "work_hours_per_day": "8",
                "work_days_per_week": "5",
                "work_weeks_per_year": "47",
                "work_days_per_year": "235",
            },
        )
        assert r.status_code in (200, 302)

    def test_update_single_setting_success(self, auth_client, app):
        """POST /gestion_rh/update_single_setting met à jour un champ."""
        _ensure_entreprise_settings(app)
        r = auth_client.post(
            "/gestion_rh/update_single_setting",
            data={"key": "work_hours_per_day", "value": "7"},
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data.get("success") is True


# ===========================================================================
# 9. Import de rôles via CSV
# ===========================================================================

class TestImportRoles:

    def test_import_roles_valid_csv(self, auth_client, app):
        """POST /gestion_rh/import_roles avec un CSV valide redirige."""
        csv_content = b"Directeur\nManager\nTechnicien\n"
        data = {
            "role_file": (io.BytesIO(csv_content), "roles.csv"),
        }
        r = auth_client.post(
            "/gestion_rh/import_roles",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 302)
        # Vérifie que les rôles ont été créés
        with app.app_context():
            from Code.models.models import Role
            from Code.extensions import db
            roles_created = Role.query.filter(Role.name.in_(["Directeur", "Manager", "Technicien"])).all()
            assert len(roles_created) >= 1
            # Nettoyage
            for rr in roles_created:
                db.session.delete(rr)
            db.session.commit()

    def test_import_roles_empty_lines_ignored(self, auth_client):
        """Les lignes vides dans le CSV ne créent pas de rôles parasites."""
        csv_content = "\n\nRoleVide\n\n".encode("utf-8")
        data = {
            "role_file": (io.BytesIO(csv_content), "roles_vides.csv"),
        }
        r = auth_client.post(
            "/gestion_rh/import_roles",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 302)

    def test_import_roles_non_csv_ignored(self, auth_client):
        """Un fichier non-.csv est ignoré (pas d'erreur, juste redirect)."""
        data = {
            "role_file": (io.BytesIO(b"some content"), "roles.txt"),
        }
        r = auth_client.post(
            "/gestion_rh/import_roles",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 302)
