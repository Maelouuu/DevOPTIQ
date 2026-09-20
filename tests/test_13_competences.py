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

    def test_current_user_manager_is_manager_true_when_managing_someone(self, client, app, ids):
        """Un compte qui encadre un collaborateur (users.manager_id) est
        reconnu comme son propre manager affiché."""
        collab_id = _create_user(app, ids, email="comp_cum_collab@test.com",
                                  first="Collab", last="CUM", manager_id=ids["user_id"])
        try:
            with client.session_transaction() as sess:
                sess["user_id"] = ids["user_id"]
                sess["user_email"] = "test@devoptiq.com"
                sess["active_entity_id"] = ids["entity_id"]
            r = client.get("/competences/current_user_manager")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["is_manager"] is True
            assert data["manager_id"] == ids["user_id"]
        finally:
            _delete_user(app, collab_id)

    def test_current_user_manager_returns_own_manager_when_not_managing(self, client, app, ids):
        """Un compte qui n'encadre personne mais a un manager reçoit CE
        manager, pas une erreur."""
        dev_id = _create_user(app, ids, email="comp_cum_dev@test.com", first="Dev", last="CUM")
        collab_id = _create_user(app, ids, email="comp_cum_collab2@test.com",
                                  first="Collab2", last="CUM", manager_id=dev_id)
        try:
            with client.session_transaction() as sess:
                sess["user_id"] = collab_id
                sess["user_email"] = "comp_cum_collab2@test.com"
                sess["active_entity_id"] = ids["entity_id"]
            r = client.get("/competences/current_user_manager")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["is_manager"] is False
            assert data["manager_id"] == dev_id
        finally:
            with client.session_transaction() as sess:
                sess["user_id"] = ids["user_id"]
                sess["user_email"] = "test@devoptiq.com"
                sess["active_entity_id"] = ids["entity_id"]
            _delete_user(app, collab_id)
            _delete_user(app, dev_id)


# ===========================================================================
# 2bis. Contexte (qui note qui, sur cette page)
# ===========================================================================

class TestContexteEndpoint:
    """GET /competences/contexte — décide qui note qui et qui est visible."""

    def test_admin_sans_collaborateur_direct_voit_tout_le_monde(self, client, app, ids):
        """Un statut élevé (admin/champion) sans rattachement direct passe
        quand même en mode développeur, avec tous les autres comptes."""
        uid = _create_user(app, ids, email="comp_ctx_tiers@test.com", first="Tiers", last="Ctx")
        try:
            with client.session_transaction() as sess:
                sess["user_id"] = ids["user_id"]
                sess["user_email"] = "test@devoptiq.com"
                sess["active_entity_id"] = ids["entity_id"]
            r = client.get("/competences/contexte")
            assert r.status_code == 200
            data = r.get_json()
            assert data["est_dev"] is True
            assert uid in [c["id"] for c in data["collaborateurs"]]
        finally:
            _delete_user(app, uid)

    def test_encadrement_par_role_sans_rattachement_direct(self, client, app, ids):
        """Un collaborateur rattaché seulement via user_roles.manager_id
        (pas users.manager_id) apparaît quand même dans la liste."""
        dev_id = _create_user(app, ids, email="comp_ctx_dev@test.com", first="Dev", last="Ctx")
        collab_id = _create_user(app, ids, email="comp_ctx_collab@test.com", first="Collab", last="Ctx")
        rid = _create_role(app, ids, name="Rôle Ctx UserRole")
        with app.app_context():
            from Code.models.models import UserRole
            from Code.extensions import db
            db.session.add(UserRole(user_id=collab_id, role_id=rid, manager_id=dev_id))
            db.session.commit()
        try:
            with client.session_transaction() as sess:
                sess["user_id"] = dev_id
                sess["user_email"] = "comp_ctx_dev@test.com"
            r = client.get("/competences/contexte")
            assert r.status_code == 200
            data = r.get_json()
            assert data["est_dev"] is True
            assert collab_id in [c["id"] for c in data["collaborateurs"]]
        finally:
            with client.session_transaction() as sess:
                sess["user_id"] = ids["user_id"]
                sess["user_email"] = "test@devoptiq.com"
                sess["active_entity_id"] = ids["entity_id"]
            _delete_role(app, rid)
            _delete_user(app, collab_id)
            _delete_user(app, dev_id)

    def test_ia_disponible_reste_false_si_le_client_ia_leve_une_exception(
        self, client, ids, monkeypatch
    ):
        """Une panne du client IA ne doit jamais faire planter la page :
        `ia_disponible` retombe sur False."""
        import Code.routes.propose_common as propose_common

        def _boom():
            raise RuntimeError("panne IA simulée")

        monkeypatch.setattr(propose_common, "openai_client_or_none", _boom)
        with client.session_transaction() as sess:
            sess["user_id"] = ids["user_id"]
            sess["user_email"] = "test@devoptiq.com"
            sess["active_entity_id"] = ids["entity_id"]
        r = client.get("/competences/contexte")
        assert r.status_code == 200
        data = r.get_json()
        assert data["ia_disponible"] is False


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

    def test_get_evaluations_null_created_at_returns_empty_string(self, auth_client, app, ids):
        """Une évaluation sans date de création renvoie created_at vide, sans planter."""
        uid = _create_user(app, ids, email="comp_eval_no_date@test.com")
        eid = _create_evaluation(
            app, uid, ids["activity_id"],
            item_id=None, item_type="activities", eval_number="rh", note="green"
        )
        with app.app_context():
            from Code.models.models import CompetencyEvaluation
            from Code.extensions import db
            ev = CompetencyEvaluation.query.get(eid)
            ev.created_at = None
            db.session.commit()
        try:
            r = auth_client.get(f"/competences/get_user_evaluations_by_user/{uid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert len(data) >= 1
            assert data[0]["created_at"] == ""
        finally:
            _delete_evaluations(app, uid)
            _delete_user(app, uid)

    def test_get_evaluations_unparseable_date_string_returned_as_is(self, auth_client, app, ids):
        """Une date stockée dans un format inconnu est renvoyée telle quelle
        (repli défensif), au lieu de faire échouer l'appel."""
        uid = _create_user(app, ids, email="comp_eval_bad_date@test.com")
        eid = _create_evaluation(
            app, uid, ids["activity_id"],
            item_id=None, item_type="activities", eval_number="garant", note="orange"
        )
        with app.app_context():
            from Code.models.models import CompetencyEvaluation
            from Code.extensions import db
            ev = CompetencyEvaluation.query.get(eid)
            ev.created_at = "n'importe quoi"
            db.session.commit()
        try:
            r = auth_client.get(f"/competences/get_user_evaluations_by_user/{uid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data[0]["created_at"] == "n'importe quoi"
        finally:
            _delete_evaluations(app, uid)
            _delete_user(app, uid)

    def test_get_evaluations_without_active_entity_returns_all(self, client, app, ids):
        """Un compte sans aucune entité accessible voit quand même les
        évaluations demandées (repli sans filtre d'entité active)."""
        orphan_id = _create_user(app, ids, email="comp_eval_orphan@test.com",
                                  first="Orphan", last="NoEnt")
        eval_id = _create_evaluation(
            app, ids["user_id"], ids["activity_id"],
            item_id=None, item_type="activities", eval_number="manager", note="green"
        )
        try:
            with client.session_transaction() as sess:
                sess.clear()
                sess["user_id"] = orphan_id
                sess["user_email"] = "comp_eval_orphan@test.com"
            r = client.get(f"/competences/get_user_evaluations_by_user/{ids['user_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert any(e["activity_id"] == ids["activity_id"] for e in data)
        finally:
            with client.session_transaction() as sess:
                sess["user_id"] = ids["user_id"]
                sess["user_email"] = "test@devoptiq.com"
                sess["active_entity_id"] = ids["entity_id"]
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                from Code.extensions import db
                CompetencyEvaluation.query.filter_by(id=eval_id).delete()
                db.session.commit()
            _delete_user(app, orphan_id)


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

    def test_role_structure_synthese_evals_populated_from_activity_level_evaluation(
        self, auth_client, app, ids
    ):
        """Une évaluation posée sur l'ACTIVITÉ elle-même (garant/manager/rh)
        apparaît dans la synthèse du rôle, pas seulement les évaluations
        d'items (savoirs/savoir-faire/HSC)."""
        rid = _create_role(app, ids, name="Rôle Synthèse Activité")
        _link_activity_to_role(app, ids["activity_id"], rid)
        eval_id = _create_evaluation(
            app, ids["user_id"], ids["activity_id"],
            item_id=None, item_type="activities", eval_number="garant", note="green"
        )
        try:
            r = auth_client.get(f"/competences/role_structure/{ids['user_id']}/{rid}")
            assert r.status_code == 200
            data = json.loads(r.data)
            entry = next(e for e in data["synthese"] if e["activity_id"] == ids["activity_id"])
            assert entry["evals"]["garant"].get("note") == "green"
        finally:
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                from Code.extensions import db
                CompetencyEvaluation.query.filter_by(id=eval_id).delete()
                db.session.commit()
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

    def test_global_summary_role_without_activities_shows_message(self, auth_client, app, ids):
        """Un rôle assigné sans aucune activité liée affiche le message dédié
        plutôt qu'un tableau vide silencieux."""
        rid = _create_role(app, ids, name="Rôle Sans Activité GS")
        _assign_role(app, ids["user_id"], rid)
        try:
            r = auth_client.get(f"/competences/global_summary/{ids['user_id']}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert "No activity for this role." in body
        finally:
            with app.app_context():
                from Code.models.models import UserRole
                from Code.extensions import db
                UserRole.query.filter_by(user_id=ids["user_id"], role_id=rid).delete()
                db.session.commit()
            _delete_role(app, rid)

    def test_global_summary_activity_evals_rendered_in_table(self, auth_client, app, ids):
        """Une évaluation d'activité (garant/manager/rh) colore la cellule
        correspondante dans le tableau de synthèse."""
        rid = _create_role(app, ids, name="Rôle GS Eval")
        _assign_role(app, ids["user_id"], rid)
        _link_activity_to_role(app, ids["activity_id"], rid)
        eval_id = _create_evaluation(
            app, ids["user_id"], ids["activity_id"],
            item_id=None, item_type="activities", eval_number="manager", note="green"
        )
        try:
            r = auth_client.get(f"/competences/global_summary/{ids['user_id']}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert "eval-cell green" in body
        finally:
            with app.app_context():
                from Code.models.models import CompetencyEvaluation, UserRole
                from Code.extensions import db
                CompetencyEvaluation.query.filter_by(id=eval_id).delete()
                UserRole.query.filter_by(user_id=ids["user_id"], role_id=rid).delete()
                db.session.commit()
            _unlink_activity_from_role(app, ids["activity_id"], rid)
            _delete_role(app, rid)

    def test_global_summary_internal_error_returns_500(self, auth_client, ids, monkeypatch):
        """Une panne interne renvoie un JSON d'erreur (500), jamais une page cassée."""
        from Code.models.models import Entity

        def _boom(*a, **kw):
            raise RuntimeError("panne simulée")

        monkeypatch.setattr(Entity, "get_active_id", staticmethod(_boom))
        r = auth_client.get(f"/competences/global_summary/{ids['user_id']}")
        assert r.status_code == 500
        data = json.loads(r.data)
        assert "error" in data


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

    def test_flat_summary_role_with_eval_shows_note_and_excludes_empty_role(
        self, auth_client, app, ids
    ):
        """Le tableau à plat affiche la note manager (avec sa date), colore
        l'en-tête du rôle en vert quand tout est validé, et ignore les rôles
        sans aucune activité liée."""
        role_with = _create_role(app, ids, name="Rôle Flat Avec Activité")
        role_empty = _create_role(app, ids, name="Rôle Flat Vide")
        _assign_role(app, ids["user_id"], role_with)
        _assign_role(app, ids["user_id"], role_empty)
        _link_activity_to_role(app, ids["activity_id"], role_with)
        eval_id = _create_evaluation(
            app, ids["user_id"], ids["activity_id"],
            item_id=None, item_type="activities", eval_number="manager", note="green"
        )
        try:
            r = auth_client.get(f"/competences/global_flat_summary/{ids['user_id']}")
            assert r.status_code == 200
            body = r.data.decode("utf-8", errors="replace")
            assert "Rôle Flat Avec Activité" in body
            assert "Rôle Flat Vide" not in body
            assert 'class="eval-cell green"' in body
        finally:
            with app.app_context():
                from Code.models.models import CompetencyEvaluation, UserRole
                from Code.extensions import db
                CompetencyEvaluation.query.filter_by(id=eval_id).delete()
                UserRole.query.filter_by(user_id=ids["user_id"], role_id=role_with).delete()
                UserRole.query.filter_by(user_id=ids["user_id"], role_id=role_empty).delete()
                db.session.commit()
            _unlink_activity_from_role(app, ids["activity_id"], role_with)
            _delete_role(app, role_with)
            _delete_role(app, role_empty)


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

    def test_users_global_summary_without_active_entity_uses_all_roles(self, client, app, ids):
        """Un compte sans entité active voit quand même la synthèse (repli
        sans filtre d'entité pour la liste des rôles)."""
        orphan_id = _create_user(app, ids, email="comp_ugs_orphan@test.com",
                                  first="Orphan", last="UGS")
        try:
            with client.session_transaction() as sess:
                sess.clear()
                sess["user_id"] = orphan_id
                sess["user_email"] = "comp_ugs_orphan@test.com"
            r = client.get("/competences/users/global_summary")
            assert r.status_code == 200
        finally:
            with client.session_transaction() as sess:
                sess["user_id"] = ids["user_id"]
                sess["user_email"] = "test@devoptiq.com"
                sess["active_entity_id"] = ids["entity_id"]
            _delete_user(app, orphan_id)

    def test_users_global_summary_internal_error_returns_html_500(self, auth_client, monkeypatch):
        """Une panne interne renvoie un message HTML explicite (500), pas un
        crash brut sans contexte."""
        from Code.models.models import Entity

        def _boom(*a, **kw):
            raise RuntimeError("panne simulée")

        monkeypatch.setattr(Entity, "get_active_id", staticmethod(_boom))
        r = auth_client.get("/competences/users/global_summary")
        assert r.status_code == 500
        body = r.data.decode("utf-8", errors="replace")
        assert "Erreur" in body


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
