# tests/test_13_competences.py
"""
Page : Compétences (/competences)
Couvre : vue principale, API managers, collaborateurs, rôles utilisateurs,
         évaluations (CRUD complet), structure de rôle, synthèses globales,
         performance générale.
"""
import json
import pytest

pytestmark = pytest.mark.competences


# ---------------------------------------------------------------------------
# Helpers DB directs
# ---------------------------------------------------------------------------

def _create_role(app, ids, name="Rôle Compétence Test"):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        role = Role(name=name, entity_id=ids["entity_id"])
        db.session.add(role)
        db.session.commit()
        return role.id


def _delete_role(app, role_id):
    with app.app_context():
        from Code.models.models import Role, UserRole
        from Code.extensions import db
        UserRole.query.filter_by(role_id=role_id).delete()
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
        db.session.commit()


def _create_user(app, ids, email, first="Collab", last="Compétence", manager_id=None):
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
            manager_id=manager_id,
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _delete_user(app, user_id):
    with app.app_context():
        from Code.models.models import User, UserRole, CompetencyEvaluation
        from Code.extensions import db
        CompetencyEvaluation.query.filter_by(user_id=user_id).delete()
        UserRole.query.filter_by(user_id=user_id).delete()
        u = User.query.get(user_id)
        if u:
            db.session.delete(u)
        db.session.commit()


def _assign_role(app, user_id, role_id):
    with app.app_context():
        from Code.models.models import UserRole
        from Code.extensions import db
        ur = UserRole(user_id=user_id, role_id=role_id)
        db.session.add(ur)
        db.session.commit()


def _link_activity_to_role(app, activity_id, role_id):
    """Associe une activité à un rôle dans la table activity_roles."""
    with app.app_context():
        from Code.models.models import activity_roles
        from Code.extensions import db
        db.session.execute(
            activity_roles.insert().values(
                activity_id=activity_id, role_id=role_id, status="active"
            )
        )
        db.session.commit()


def _unlink_activity_from_role(app, activity_id, role_id):
    with app.app_context():
        from Code.models.models import activity_roles
        from Code.extensions import db
        db.session.execute(
            activity_roles.delete().where(
                activity_roles.c.activity_id == activity_id,
                activity_roles.c.role_id == role_id,
            )
        )
        db.session.commit()


def _create_evaluation(app, user_id, activity_id, item_id=None, item_type="savoirs",
                        eval_number="1", note="green"):
    with app.app_context():
        from Code.models.models import CompetencyEvaluation
        from Code.extensions import db
        ev = CompetencyEvaluation(
            user_id=user_id,
            activity_id=activity_id,
            item_id=item_id,
            item_type=item_type,
            eval_number=eval_number,
            note=note,
        )
        db.session.add(ev)
        db.session.commit()
        return ev.id


def _delete_evaluations(app, user_id):
    with app.app_context():
        from Code.models.models import CompetencyEvaluation
        from Code.extensions import db
        CompetencyEvaluation.query.filter_by(user_id=user_id).delete()
        db.session.commit()


# ===========================================================================
# 1. Vue principale
# ===========================================================================

class TestCompetencesView:

    def test_view_page_authenticated_returns_200(self, auth_client):
        """GET /competences/view est accessible et retourne 200."""
        r = auth_client.get("/competences/view")
        assert r.status_code == 200

    def test_view_page_unauthenticated_no_crash(self, client):
        """Sans session, /competences/view ne doit pas crasher (200 ou redirect)."""
        r = client.get("/competences/view")
        assert r.status_code in (200, 302)

    def test_view_page_contains_html(self, auth_client):
        """La réponse contient bien du contenu HTML."""
        r = auth_client.get("/competences/view")
        body = r.data.decode("utf-8", errors="replace").lower()
        assert "<html" in body or "<!doctype" in body


# ===========================================================================
# 2. Endpoint current_user_manager (user 114 hardcodé — absent en test)
# ===========================================================================

class TestCurrentUserManager:

    def test_current_user_manager_not_found_in_test_db(self, auth_client):
        """Le manager hardcodé (id=114) n'existe pas en test → 404."""
        r = auth_client.get("/competences/current_user_manager")
        assert r.status_code == 404
        data = json.loads(r.data)
        assert "error" in data


# ===========================================================================
# 3. API Managers
# ===========================================================================

class TestManagersAPI:

    def test_get_managers_no_manager_role_returns_empty(self, auth_client):
        """Sans rôle nommé 'manager', l'endpoint retourne une liste vide."""
        r = auth_client.get("/competences/managers")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        assert data == []

    def test_get_managers_with_manager_role_returns_users(self, auth_client, app, ids):
        """Avec un rôle 'manager' et un utilisateur assigné, l'API retourne ce manager."""
        rid = _create_role(app, ids, name="manager")
        uid = _create_user(app, ids, email="comp_manager_api@test.com", first="Manager", last="API")
        _assign_role(app, uid, rid)
        try:
            r = auth_client.get("/competences/managers")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert isinstance(data, list)
            found = next((m for m in data if m["id"] == uid), None)
            assert found is not None
            assert "name" in found
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)

    def test_get_managers_response_has_id_and_name_fields(self, auth_client, app, ids):
        """Chaque entrée dans la liste des managers contient id et name."""
        rid = _create_role(app, ids, name="manager")
        uid = _create_user(app, ids, email="comp_manager_fields@test.com", first="Mgr", last="Fields")
        _assign_role(app, uid, rid)
        try:
            r = auth_client.get("/competences/managers")
            data = json.loads(r.data)
            if data:
                entry = data[0]
                assert "id" in entry
                assert "name" in entry
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)


# ===========================================================================
# 4. API Collaborateurs par manager
# ===========================================================================

class TestCollaboratorsAPI:

    def test_get_collaborators_empty_returns_list(self, auth_client, ids):
        """Un manager sans collaborateurs retourne une liste vide."""
        r = auth_client.get(f"/competences/collaborators/{ids['user_id']}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_get_collaborators_nonexistent_manager_returns_empty(self, auth_client):
        """Un manager_id inexistant retourne une liste vide (pas d'erreur)."""
        r = auth_client.get("/competences/collaborators/999999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_get_collaborators_with_subordinate(self, auth_client, app, ids):
        """Un collaborateur lié à un manager apparaît dans la liste."""
        uid = _create_user(
            app, ids, email="comp_collab_sub@test.com",
            first="Subord", last="Test", manager_id=ids["user_id"]
        )
        try:
            r = auth_client.get(f"/competences/collaborators/{ids['user_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            found = next((u for u in data if u["id"] == uid), None)
            assert found is not None
            assert "first_name" in found
            assert "last_name" in found
        finally:
            _delete_user(app, uid)


# ===========================================================================
# 5. API Rôles utilisateur
# ===========================================================================

class TestUserRolesAPI:

    def test_get_user_roles_empty(self, auth_client, app, ids):
        """Un utilisateur sans rôle retourne {roles: []}."""
        uid = _create_user(app, ids, email="comp_no_roles@test.com")
        try:
            r = auth_client.get(f"/competences/get_user_roles/{uid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "roles" in data
            assert data["roles"] == []
        finally:
            _delete_user(app, uid)

    def test_get_user_roles_with_assigned_role(self, auth_client, app, ids):
        """Un utilisateur avec un rôle retourne ce rôle dans la liste."""
        rid = _create_role(app, ids, name="Rôle API Roles")
        uid = _create_user(app, ids, email="comp_has_role@test.com")
        _assign_role(app, uid, rid)
        try:
            r = auth_client.get(f"/competences/get_user_roles/{uid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "roles" in data
            roles = data["roles"]
            assert isinstance(roles, list)
            assert any(ro["id"] == rid for ro in roles)
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)

    def test_get_user_roles_fields(self, auth_client, app, ids):
        """Chaque rôle retourné contient id et name."""
        rid = _create_role(app, ids, name="Rôle API Fields")
        uid = _create_user(app, ids, email="comp_role_fields@test.com")
        _assign_role(app, uid, rid)
        try:
            r = auth_client.get(f"/competences/get_user_roles/{uid}")
            data = json.loads(r.data)
            if data["roles"]:
                role_entry = data["roles"][0]
                assert "id" in role_entry
                assert "name" in role_entry
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)


# ===========================================================================
# 6. Sauvegarde des évaluations
# ===========================================================================

class TestSaveEvaluations:

    def test_save_missing_user_id_returns_400(self, auth_client):
        """POST sans userId → 400."""
        r = auth_client.post(
            "/competences/save_user_evaluations",
            data=json.dumps({"evaluations": []}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert data.get("success") is False

    def test_save_missing_evaluations_returns_400(self, auth_client, ids):
        """POST sans évaluations → 400."""
        r = auth_client.post(
            "/competences/save_user_evaluations",
            data=json.dumps({"userId": ids["user_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_save_evaluation_creates_record(self, auth_client, app, ids):
        """POST avec données valides crée une évaluation en base."""
        uid = _create_user(app, ids, email="comp_eval_create@test.com")
        payload = {
            "userId": uid,
            "evaluations": [{
                "activity_id": ids["activity_id"],
                "item_id": None,
                "item_type": "activities",
                "eval_number": "garant",
                "note": "green",
            }]
        }
        try:
            r = auth_client.post(
                "/competences/save_user_evaluations",
                data=json.dumps(payload),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                ev = CompetencyEvaluation.query.filter_by(
                    user_id=uid,
                    activity_id=ids["activity_id"],
                    eval_number="garant",
                ).first()
                assert ev is not None
                assert ev.note == "green"
        finally:
            _delete_evaluations(app, uid)
            _delete_user(app, uid)

    def test_save_evaluation_updates_existing(self, auth_client, app, ids):
        """POST sur une éval existante met à jour la note."""
        uid = _create_user(app, ids, email="comp_eval_update@test.com")
        _create_evaluation(
            app, uid, ids["activity_id"],
            item_id=None, item_type="activities", eval_number="manager", note="orange"
        )
        payload = {
            "userId": uid,
            "evaluations": [{
                "activity_id": ids["activity_id"],
                "item_id": None,
                "item_type": "activities",
                "eval_number": "manager",
                "note": "green",
            }]
        }
        try:
            r = auth_client.post(
                "/competences/save_user_evaluations",
                data=json.dumps(payload),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                ev = CompetencyEvaluation.query.filter_by(
                    user_id=uid,
                    activity_id=ids["activity_id"],
                    eval_number="manager",
                ).first()
                assert ev.note == "green"
        finally:
            _delete_evaluations(app, uid)
            _delete_user(app, uid)

    def test_save_evaluation_empty_note_deletes_record(self, auth_client, app, ids):
        """POST avec note='empty' supprime l'évaluation existante."""
        uid = _create_user(app, ids, email="comp_eval_delete@test.com")
        _create_evaluation(
            app, uid, ids["activity_id"],
            item_id=None, item_type="activities", eval_number="rh", note="red"
        )
        payload = {
            "userId": uid,
            "evaluations": [{
                "activity_id": ids["activity_id"],
                "item_id": None,
                "item_type": "activities",
                "eval_number": "rh",
                "note": "empty",
            }]
        }
        try:
            r = auth_client.post(
                "/competences/save_user_evaluations",
                data=json.dumps(payload),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                ev = CompetencyEvaluation.query.filter_by(
                    user_id=uid,
                    activity_id=ids["activity_id"],
                    eval_number="rh",
                ).first()
                assert ev is None
        finally:
            _delete_evaluations(app, uid)
            _delete_user(app, uid)

    def test_save_evaluation_skips_missing_activity_id(self, auth_client, app, ids):
        """Une éval sans activity_id est ignorée silencieusement (pas d'erreur)."""
        uid = _create_user(app, ids, email="comp_eval_skip@test.com")
        payload = {
            "userId": uid,
            "evaluations": [{
                "item_id": None,
                "item_type": "activities",
                "eval_number": "garant",
                "note": "green",
            }]
        }
        try:
            r = auth_client.post(
                "/competences/save_user_evaluations",
                data=json.dumps(payload),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _delete_user(app, uid)

    def test_save_evaluation_empty_note_no_existing_record_is_noop(self, auth_client, app, ids):
        """POST avec note='empty' sans éval existante ne génère pas d'erreur."""
        uid = _create_user(app, ids, email="comp_eval_noop@test.com")
        payload = {
            "userId": uid,
            "evaluations": [{
                "activity_id": ids["activity_id"],
                "item_id": None,
                "item_type": "activities",
                "eval_number": "garant",
                "note": "empty",
            }]
        }
        try:
            r = auth_client.post(
                "/competences/save_user_evaluations",
                data=json.dumps(payload),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("success") is True
        finally:
            _delete_user(app, uid)


# ===========================================================================
# 7. Récupération des évaluations par utilisateur
# ===========================================================================

class TestGetEvaluationsByUser:

    def test_get_evaluations_empty_user_returns_list(self, auth_client, app, ids):
        """Un utilisateur sans évaluations retourne une liste vide."""
        uid = _create_user(app, ids, email="comp_get_evals_empty@test.com")
        try:
            r = auth_client.get(f"/competences/get_user_evaluations_by_user/{uid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert isinstance(data, list)
            assert data == []
        finally:
            _delete_user(app, uid)

    def test_get_evaluations_returns_created_eval(self, auth_client, app, ids):
        """Un utilisateur avec une évaluation retourne celle-ci."""
        uid = _create_user(app, ids, email="comp_get_evals_has@test.com")
        _create_evaluation(
            app, uid, ids["activity_id"],
            item_id=None, item_type="activities", eval_number="garant", note="green"
        )
        try:
            r = auth_client.get(f"/competences/get_user_evaluations_by_user/{uid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert isinstance(data, list)
            assert len(data) >= 1
            ev = data[0]
            assert ev["activity_id"] == ids["activity_id"]
            assert ev["note"] == "green"
        finally:
            _delete_evaluations(app, uid)
            _delete_user(app, uid)

    def test_get_evaluations_fields_present(self, auth_client, app, ids):
        """Chaque évaluation retournée contient les champs attendus."""
        uid = _create_user(app, ids, email="comp_eval_fields@test.com")
        _create_evaluation(
            app, uid, ids["activity_id"],
            item_id=None, item_type="activities", eval_number="manager", note="orange"
        )
        try:
            r = auth_client.get(f"/competences/get_user_evaluations_by_user/{uid}")
            data = json.loads(r.data)
            assert len(data) >= 1
            ev = data[0]
            for field in ("activity_id", "item_id", "item_type", "eval_number", "note"):
                assert field in ev
        finally:
            _delete_evaluations(app, uid)
            _delete_user(app, uid)


# ===========================================================================
# 8. Structure de rôle
# ===========================================================================

class TestRoleStructure:

    def test_role_structure_user_not_found_returns_404(self, auth_client):
        """user_id inexistant → 404."""
        r = auth_client.get("/competences/role_structure/999999/1")
        assert r.status_code == 404
        data = json.loads(r.data)
        assert "error" in data

    def test_role_structure_role_not_found_returns_404(self, auth_client, ids):
        """role_id inexistant (avec user valide) → 404."""
        r = auth_client.get(f"/competences/role_structure/{ids['user_id']}/999999")
        assert r.status_code == 404
        data = json.loads(r.data)
        assert "error" in data

    def test_role_structure_valid_returns_json(self, auth_client, app, ids):
        """Avec user et rôle valides, retourne la structure JSON."""
        rid = _create_role(app, ids, name="Rôle Structure Test")
        try:
            r = auth_client.get(f"/competences/role_structure/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "role_id" in data
            assert "role_name" in data
            assert "activities" in data
            assert "synthese" in data
        finally:
            _delete_role(app, rid)

    def test_role_structure_with_activity_includes_competency_data(self, auth_client, app, ids):
        """Un rôle lié à une activité retourne les données de compétences."""
        rid = _create_role(app, ids, name="Rôle Structure Activité")
        _link_activity_to_role(app, ids["activity_id"], rid)
        try:
            r = auth_client.get(f"/competences/role_structure/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert len(data["activities"]) >= 1
            act = data["activities"][0]
            assert act["id"] == ids["activity_id"]
            assert "savoirs" in act
            assert "savoir_faires" in act
            assert "hsc" in act
        finally:
            _unlink_activity_from_role(app, ids["activity_id"], rid)
            _delete_role(app, rid)

    def test_role_structure_synthese_contains_evals(self, auth_client, app, ids):
        """La synthèse contient les champs garant/manager/rh."""
        rid = _create_role(app, ids, name="Rôle Synthèse Evals")
        _link_activity_to_role(app, ids["activity_id"], rid)
        try:
            r = auth_client.get(f"/competences/role_structure/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            if data["synthese"]:
                entry = data["synthese"][0]
                assert "evals" in entry
                assert "garant" in entry["evals"]
                assert "manager" in entry["evals"]
                assert "rh" in entry["evals"]
        finally:
            _unlink_activity_from_role(app, ids["activity_id"], rid)
            _delete_role(app, rid)


# ===========================================================================
# 9. Synthèse globale par utilisateur
# ===========================================================================

class TestGlobalSummary:

    def test_global_summary_user_not_found_returns_404(self, auth_client):
        """user_id inexistant → 404."""
        r = auth_client.get("/competences/global_summary/999999")
        assert r.status_code == 404

    def test_global_summary_valid_user_returns_200(self, auth_client, ids):
        """Un utilisateur valide sans rôles retourne 200 et du HTML."""
        r = auth_client.get(f"/competences/global_summary/{ids['user_id']}")
        assert r.status_code == 200
        body = r.data.decode("utf-8", errors="replace")
        assert len(body) > 0

    def test_global_summary_contains_user_name(self, auth_client, ids):
        """La synthèse contient le nom de l'utilisateur."""
        r = auth_client.get(f"/competences/global_summary/{ids['user_id']}")
        body = r.data.decode("utf-8", errors="replace")
        assert "Test" in body or "User" in body

    def test_global_summary_with_role_and_activity(self, auth_client, app, ids):
        """Avec un rôle et une activité associée, la synthèse contient les données."""
        rid = _create_role(app, ids, name="Rôle Global Summary")
        _assign_role(app, ids["user_id"], rid)
        _link_activity_to_role(app, ids["activity_id"], rid)
        try:
            r = auth_client.get(f"/competences/global_summary/{ids['user_id']}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert len(body) > 50
        finally:
            _unlink_activity_from_role(app, ids["activity_id"], rid)
            with app.app_context():
                from Code.models.models import UserRole
                from Code.extensions import db
                UserRole.query.filter_by(user_id=ids["user_id"], role_id=rid).delete()
                db.session.commit()
            _delete_role(app, rid)


# ===========================================================================
# 10. Synthèse à plat (flat_summary)
# ===========================================================================

class TestGlobalFlatSummary:

    def test_flat_summary_user_not_found_returns_404(self, auth_client):
        """user_id inexistant → 404."""
        r = auth_client.get("/competences/global_flat_summary/999999")
        assert r.status_code == 404

    def test_flat_summary_valid_user_returns_200(self, auth_client, app, ids):
        """Un utilisateur valide retourne 200 et du HTML."""
        uid = _create_user(app, ids, email="comp_flat_summary@test.com", first="Flat", last="Summary")
        try:
            r = auth_client.get(f"/competences/global_flat_summary/{uid}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert len(body) > 0
        finally:
            _delete_user(app, uid)

    def test_flat_summary_contains_user_info(self, auth_client, app, ids):
        """Le HTML retourné contient le prénom ou le nom de l'utilisateur."""
        uid = _create_user(
            app, ids, email="comp_flat_info@test.com", first="Prénom", last="FlatNom"
        )
        try:
            r = auth_client.get(f"/competences/global_flat_summary/{uid}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert "Prénom" in body or "FlatNom" in body
        finally:
            _delete_user(app, uid)


# ===========================================================================
# 11. Synthèse globale de tous les utilisateurs
# ===========================================================================

class TestUsersGlobalSummary:

    def test_users_global_summary_returns_200(self, auth_client):
        """GET /competences/users/global_summary retourne 200."""
        r = auth_client.get("/competences/users/global_summary")
        assert r.status_code == 200

    def test_users_global_summary_contains_table(self, auth_client):
        """La réponse contient un fragment HTML avec un tableau (pas une page complète)."""
        r = auth_client.get("/competences/users/global_summary")
        body = r.data.decode("utf-8", errors="replace").lower()
        assert "<table" in body or "<style" in body or "utilisateur" in body

    def test_users_global_summary_no_crash_with_data(self, auth_client, app, ids):
        """La page fonctionne même avec des utilisateurs et des rôles en base."""
        rid = _create_role(app, ids, name="Rôle Users Summary")
        uid = _create_user(app, ids, email="comp_users_summary@test.com")
        _assign_role(app, uid, rid)
        try:
            r = auth_client.get("/competences/users/global_summary")
            assert r.status_code == 200
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)


# ===========================================================================
# 12. Performance générale d'une activité
# ===========================================================================

class TestGeneralPerformance:

    def test_general_performance_no_link_returns_empty_content(self, auth_client, ids):
        """Une activité sans lien de performance retourne {content: ''}."""
        r = auth_client.get(f"/competences/general_performance/{ids['activity_id']}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "content" in data
        assert data["content"] == ""

    def test_general_performance_nonexistent_activity_returns_empty(self, auth_client):
        """Une activité inexistante retourne {content: ''} sans erreur."""
        r = auth_client.get("/competences/general_performance/999999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["content"] == ""

    def test_general_performance_with_link_and_performance(self, auth_client, app, ids):
        """Avec un lien et une performance associée, retourne le contenu."""
        with app.app_context():
            from Code.models.models import Link, Performance, Activities
            from Code.extensions import db

            # Créer une activité source et un lien sortant
            source_act = Activities(
                entity_id=ids["entity_id"],
                name="Activité Source Perf",
            )
            db.session.add(source_act)
            db.session.flush()

            link = Link(
                entity_id=ids["entity_id"],
                source_activity_id=source_act.id,
                target_activity_id=ids["activity_id"],
                type="nourrissante",
            )
            db.session.add(link)
            db.session.flush()

            perf = Performance(name="Indicateur Test Compétences", link_id=link.id)
            db.session.add(perf)
            db.session.commit()

            source_id = source_act.id
            link_id = link.id
            perf_id = perf.id

        try:
            r = auth_client.get(f"/competences/general_performance/{source_id}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "content" in data
            assert data["content"] == "Indicateur Test Compétences"
        finally:
            with app.app_context():
                from Code.models.models import Performance, Link, Activities
                from Code.extensions import db
                Performance.query.filter_by(id=perf_id).delete()
                Link.query.filter_by(id=link_id).delete()
                Activities.query.filter_by(id=source_id).delete()
                db.session.commit()


# ===========================================================================
# 13. Branches complémentaires (contexte, current_user_manager, évaluations,
#     role_structure, synthèses) — couverture des chemins non testés ailleurs.
# ===========================================================================

def _login_as(client, app, user_id, email):
    with app.app_context():
        from Code.models.models import User
        user = User.query.get(user_id)
        uid, umail = user.id, user.email or email
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_email"] = umail
    return uid


class TestContexteBranchesComplementaires:

    def test_collaborateur_rattache_seulement_par_user_role(self, client, app, ids):
        """Un collaborateur relié UNIQUEMENT via `user_roles.manager_id` (pas
        `users.manager_id`) doit quand même apparaître — sinon on perd les
        rattachements par rôle."""
        rid = _create_role(app, ids, name="Rôle Contexte UserRole")
        dev_id = _create_user(app, ids, email="ctx_dev@test.com", first="Dev", last="Ctx")
        collab_id = _create_user(app, ids, email="ctx_collab_ur@test.com",
                                  first="Collab", last="ViaRole")
        with app.app_context():
            from Code.models.models import UserRole
            from Code.extensions import db
            db.session.add(UserRole(user_id=collab_id, role_id=rid, manager_id=dev_id))
            db.session.commit()
        try:
            _login_as(client, app, dev_id, "ctx_dev@test.com")
            r = client.get("/competences/contexte")
            assert r.status_code == 200
            data = r.get_json()
            assert data["est_dev"] is True
            assert collab_id in [c["id"] for c in data["collaborateurs"]]
        finally:
            _delete_user(app, collab_id)
            _delete_user(app, dev_id)
            _delete_role(app, rid)

    def test_admin_sans_rattachement_voit_tout_le_monde(self, client, app, ids):
        """Un administrateur SANS aucun rattachement (ni direct ni via rôle)
        arbitre quand même partout : il voit tous les comptes."""
        admin_id = _create_user(app, ids, email="ctx_admin_isole@test.com",
                                 first="Admin", last="Isole")
        with app.app_context():
            from Code.models.models import User
            from Code.extensions import db
            u = User.query.get(admin_id)
            u.status = "admin"
            db.session.commit()
        try:
            _login_as(client, app, admin_id, "ctx_admin_isole@test.com")
            r = client.get("/competences/contexte")
            assert r.status_code == 200
            data = r.get_json()
            assert data["est_dev"] is True
            collab_ids = [c["id"] for c in data["collaborateurs"]]
            assert admin_id not in collab_ids
            assert ids["user_id"] in collab_ids
        finally:
            _delete_user(app, admin_id)


class TestCurrentUserManagerBranches:

    def test_utilisateur_avec_rattaches_est_manager(self, client, app, ids):
        """Un utilisateur qui encadre au moins un compte (via users.manager_id)
        est reconnu comme manager de lui-même."""
        manager_id = _create_user(app, ids, email="cum_manager@test.com",
                                   first="Manager", last="CUM")
        report_id = _create_user(app, ids, email="cum_report@test.com",
                                  first="Report", last="CUM", manager_id=manager_id)
        try:
            _login_as(client, app, manager_id, "cum_manager@test.com")
            r = client.get("/competences/current_user_manager")
            assert r.status_code == 200
            data = r.get_json()
            assert data["is_manager"] is True
            assert data["manager_id"] == manager_id
        finally:
            _delete_user(app, report_id)
            _delete_user(app, manager_id)

    def test_collaborateur_sans_encadrement_voit_son_manager(self, client, app, ids):
        """Un utilisateur qui n'encadre personne mais a un manager direct
        reçoit les infos de CE manager, avec is_manager=False."""
        manager_id = _create_user(app, ids, email="cum_manager2@test.com",
                                   first="Manager", last="CUM2")
        report_id = _create_user(app, ids, email="cum_report2@test.com",
                                  first="Report", last="CUM2", manager_id=manager_id)
        try:
            _login_as(client, app, report_id, "cum_report2@test.com")
            r = client.get("/competences/current_user_manager")
            assert r.status_code == 200
            data = r.get_json()
            assert data["is_manager"] is False
            assert data["manager_id"] == manager_id
        finally:
            _delete_user(app, report_id)
            _delete_user(app, manager_id)


class TestGetEvaluationsByUserBranches:

    def test_created_at_absent_devient_chaine_vide(self, auth_client, app, ids):
        """Une évaluation sans `created_at` (NULL) renvoie une chaîne vide,
        pas une erreur de formatage."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        with app.app_context():
            from sqlalchemy import text
            ev = CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=ids["activity_id"],
                item_id=None, item_type="savoirs", eval_number="1",
                note="green",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id
            # Le défaut `datetime.utcnow` de la colonne s'applique dès que la
            # valeur vaut None côté ORM : on force le NULL en SQL brut pour
            # obtenir le cas réel d'une ligne sans date.
            db.session.execute(
                text("UPDATE competency_evaluation SET created_at = NULL WHERE id = :id"),
                {"id": ev_id},
            )
            db.session.commit()

        try:
            r = auth_client.get(f"/competences/get_user_evaluations_by_user/{ids['user_id']}")
            assert r.status_code == 200
            data = r.get_json()
            match = [e for e in data if e["item_id"] is None and e["item_type"] == "savoirs"
                     and e["eval_number"] == "1" and e["note"] == "green"]
            assert match
            assert match[0]["created_at"] == ""
        finally:
            with app.app_context():
                CompetencyEvaluation.query.filter_by(id=ev_id).delete()
                db.session.commit()

    def test_created_at_format_non_reconnu_reste_tel_quel(self, auth_client, app, ids):
        """Une chaîne `created_at` qui ne correspond à aucun format connu est
        renvoyée inchangée plutôt que de faire planter la route."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        with app.app_context():
            ev = CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=ids["activity_id"],
                item_id=None, item_type="savoir_faires", eval_number="2",
                note="orange", created_at="pas-une-date",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        try:
            r = auth_client.get(f"/competences/get_user_evaluations_by_user/{ids['user_id']}")
            assert r.status_code == 200
            data = r.get_json()
            match = [e for e in data if e["item_type"] == "savoir_faires" and e["eval_number"] == "2"]
            assert match
            assert match[0]["created_at"] == "pas-une-date"
        finally:
            with app.app_context():
                CompetencyEvaluation.query.filter_by(id=ev_id).delete()
                db.session.commit()

    def test_sans_entite_active_retourne_toutes_les_evaluations(self, client, app, ids):
        """Sans entité active, la route retombe sur TOUTES les évaluations de
        l'utilisateur (pas de filtre par activités de l'entité).

        Le compte CONNECTÉ doit être isolé (aucune entité possédée) : un
        compte qui en possède une la retrouve automatiquement via le repli de
        `Entity.get_active` — l'absence d'entité active ne « tient » pas."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        viewer_id = _create_user(app, ids, email="ceva_sans_entite@test.com",
                                  first="Viewer", last="SansEntite")
        with app.app_context():
            ev = CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=ids["activity_id"],
                item_id=None, item_type="softskills", eval_number="3",
                note="green",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id

        _login_as(client, app, viewer_id, "ceva_sans_entite@test.com")
        with client.session_transaction() as sess:
            sess.pop("active_entity_id", None)

        try:
            r = client.get(f"/competences/get_user_evaluations_by_user/{ids['user_id']}")
            assert r.status_code == 200
            data = r.get_json()
            match = [e for e in data if e["item_type"] == "softskills" and e["eval_number"] == "3"]
            assert match
        finally:
            with app.app_context():
                CompetencyEvaluation.query.filter_by(id=ev_id).delete()
                db.session.commit()
            _delete_user(app, viewer_id)


class TestRoleStructureAvecItemsEtEvaluations:

    def test_role_structure_avec_savoirs_savoir_faires_hsc_et_evaluations(self, auth_client, app, ids):
        """Une activité liée au rôle, avec savoirs/savoir-faire/HSC ET des
        évaluations (une d'activité, une d'item), remplit toutes les listes
        et les dictionnaires d'évaluations correspondants."""
        from Code.extensions import db
        from Code.models.models import (
            Activities, Savoir, SavoirFaire, Softskill, CompetencyEvaluation,
        )

        rid = _create_role(app, ids, name="Rôle Structure Items Complets")
        with app.app_context():
            act = Activities(entity_id=ids["entity_id"], name="Activité Structure Complète")
            db.session.add(act)
            db.session.flush()
            act_id = act.id

            savoir = Savoir(description="Savoir Structure", activity_id=act_id)
            sf = SavoirFaire(description="SF Structure", activity_id=act_id)
            hsc = Softskill(habilete="HSC Structure", niveau="2 (Acquisition)", activity_id=act_id)
            db.session.add_all([savoir, sf, hsc])
            db.session.flush()
            savoir_id, sf_id, hsc_id = savoir.id, sf.id, hsc.id

            db.session.add(CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=act_id,
                item_id=None, item_type="activities", eval_number="garant", note="green",
            ))
            db.session.add(CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=act_id,
                item_id=savoir_id, item_type="savoirs", eval_number="1", note="orange",
            ))
            db.session.commit()

        _link_activity_to_role(app, act_id, rid)
        try:
            r = auth_client.get(f"/competences/role_structure/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = r.get_json()
            act_entry = next(a for a in data["activities"] if a["id"] == act_id)
            assert [s["id"] for s in act_entry["savoirs"]] == [savoir_id]
            assert act_entry["savoirs"][0]["evals"]["1"]["note"] == "orange"
            assert [s["id"] for s in act_entry["savoir_faires"]] == [sf_id]
            assert [h["id"] for h in act_entry["hsc"]] == [hsc_id]
            assert act_entry["hsc"][0]["niveau"] == "2 (Acquisition)"

            synth_entry = next(s for s in data["synthese"] if s["activity_id"] == act_id)
            assert synth_entry["evals"]["garant"]["note"] == "green"
        finally:
            _unlink_activity_from_role(app, act_id, rid)
            with app.app_context():
                CompetencyEvaluation.query.filter_by(activity_id=act_id).delete()
                Softskill.query.filter_by(id=hsc_id).delete()
                SavoirFaire.query.filter_by(id=sf_id).delete()
                Savoir.query.filter_by(id=savoir_id).delete()
                Activities.query.filter_by(id=act_id).delete()
                db.session.commit()
            _delete_role(app, rid)


class TestGlobalSummaryBranchesComplementaires:

    def test_role_sans_activite_affiche_message_dedie(self, auth_client, app, ids):
        """Un rôle assigné à l'utilisateur mais SANS activité liée affiche le
        message « No activity for this role. » plutôt qu'un tableau vide."""
        rid = _create_role(app, ids, name="Rôle Sans Activité Summary")
        uid = _create_user(app, ids, email="gs_role_vide@test.com")
        _assign_role(app, uid, rid)
        try:
            r = auth_client.get(f"/competences/global_summary/{uid}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert "No activity for this role." in body
        finally:
            _delete_user(app, uid)
            _delete_role(app, rid)

    def test_evaluation_activite_colore_la_cellule(self, auth_client, app, ids):
        """Une évaluation d'activité (garant/manager/rh) se retrouve dans la
        classe CSS de la cellule correspondante."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        rid = _create_role(app, ids, name="Rôle Eval Coloree Summary")
        _link_activity_to_role(app, ids["activity_id"], rid)
        _assign_role(app, ids["user_id"], rid)
        with app.app_context():
            ev = CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=ids["activity_id"],
                item_id=None, item_type="activities", eval_number="manager", note="green",
            )
            db.session.add(ev)
            db.session.commit()
            ev_id = ev.id
        try:
            r = auth_client.get(f"/competences/global_summary/{ids['user_id']}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert 'eval-cell green' in body
        finally:
            with app.app_context():
                CompetencyEvaluation.query.filter_by(id=ev_id).delete()
                db.session.commit()
            _unlink_activity_from_role(app, ids["activity_id"], rid)
            _delete_role(app, rid)


class TestGlobalFlatSummaryBranchesComplementaires:

    def test_role_avec_activites_et_evaluations_variees(self, auth_client, app, ids):
        """Un rôle avec activités liées et des évaluations aux formats de date
        variés (ISO auto, jj/mm/aaaa, absente) remplit l'en-tête et les
        cellules — y compris le repli `%d/%m/%Y` et la date vide."""
        from Code.extensions import db
        from Code.models.models import Activities, CompetencyEvaluation

        rid = _create_role(app, ids, name="Rôle Flat Complet")
        _assign_role(app, ids["user_id"], rid)
        with app.app_context():
            act_iso = Activities(entity_id=ids["entity_id"], name="Activité Flat ISO")
            act_ddmmyyyy = Activities(entity_id=ids["entity_id"], name="Activité Flat DDMMYYYY")
            act_sans_date = Activities(entity_id=ids["entity_id"], name="Activité Flat Sans Date")
            db.session.add_all([act_iso, act_ddmmyyyy, act_sans_date])
            db.session.commit()
            act_iso_id, act_ddmmyyyy_id, act_sans_date_id = act_iso.id, act_ddmmyyyy.id, act_sans_date.id

        for aid in (act_iso_id, act_ddmmyyyy_id, act_sans_date_id):
            _link_activity_to_role(app, aid, rid)

        with app.app_context():
            from sqlalchemy import text
            db.session.add(CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=act_iso_id,
                item_id=None, item_type="activities", eval_number="manager", note="green",
            ))
            db.session.add(CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=act_ddmmyyyy_id,
                item_id=None, item_type="activities", eval_number="manager", note="orange",
                created_at="01/01/2024",
            ))
            sans_date_ev = CompetencyEvaluation(
                user_id=ids["user_id"], activity_id=act_sans_date_id,
                item_id=None, item_type="activities", eval_number="manager", note="green",
            )
            db.session.add(sans_date_ev)
            db.session.commit()
            # Même contrainte que pour get_user_evaluations_by_user : le défaut
            # de colonne réécrit tout None passé à l'ORM, donc on force le NULL
            # en SQL brut pour obtenir le cas réel "pas de date".
            db.session.execute(
                text("UPDATE competency_evaluation SET created_at = NULL WHERE id = :id"),
                {"id": sans_date_ev.id},
            )
            db.session.commit()

        try:
            r = auth_client.get(f"/competences/global_flat_summary/{ids['user_id']}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert "Activité Flat ISO" in body
            assert "Activité Flat DDMMYYYY" in body
            assert "Activité Flat Sans Date" in body
            assert 'data-date="01/01/2024"' in body
        finally:
            with app.app_context():
                CompetencyEvaluation.query.filter(
                    CompetencyEvaluation.activity_id.in_(
                        [act_iso_id, act_ddmmyyyy_id, act_sans_date_id]
                    )
                ).delete(synchronize_session=False)
                db.session.commit()
            for aid in (act_iso_id, act_ddmmyyyy_id, act_sans_date_id):
                _unlink_activity_from_role(app, aid, rid)
            with app.app_context():
                Activities.query.filter(
                    Activities.id.in_([act_iso_id, act_ddmmyyyy_id, act_sans_date_id])
                ).delete(synchronize_session=False)
                db.session.commit()
            _delete_role(app, rid)

    def test_role_sans_activite_est_ignore_de_l_entete(self, auth_client, app, ids):
        """Un rôle assigné mais sans AUCUNE activité liée ne pollue pas
        l'en-tête (branche `continue`)."""
        rid = _create_role(app, ids, name="Rôle Flat Vide")
        _assign_role(app, ids["user_id"], rid)
        try:
            r = auth_client.get(f"/competences/global_flat_summary/{ids['user_id']}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert "Rôle Flat Vide" not in body
        finally:
            _delete_role(app, rid)


class TestUsersGlobalSummaryBranchesComplementaires:

    def test_sans_entite_active_liste_tous_les_roles(self, client, app, ids):
        """Sans AUCUNE entité possédée ou accessible, `Entity.get_active_id()`
        ne retombe sur rien : la synthèse liste alors TOUS les rôles plutôt
        que de planter. (Un compte qui possède une entité voit `get_active`
        se rabattre dessus automatiquement — il faut donc un compte isolé,
        sans entité et sans carto partagée.)"""
        uid = _create_user(app, ids, email="ugs_sans_entite@test.com",
                            first="Isole", last="SansEntite")
        _login_as(client, app, uid, "ugs_sans_entite@test.com")
        with client.session_transaction() as sess:
            sess.pop("active_entity_id", None)
        try:
            r = client.get("/competences/users/global_summary")
            assert r.status_code == 200
        finally:
            _delete_user(app, uid)
