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
