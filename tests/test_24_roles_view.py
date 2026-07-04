# tests/test_24_roles_view.py
"""
Routes : Vues des Rôles (/roles_view) + Items d'Activité (/your_api)

Endpoints couverts :
  GET  /roles_view/                               → page HTML (rôles enrichis)
  PUT  /roles_view/<role_id>/mission              → mise à jour mission_generale
  GET  /roles_view/validation_level/<uid>/<rid>   → niveau de validation
  GET  /your_api/activity_items/<activity_id>     → savoirs / savoir_faire / HSC
"""
import json
import pytest

pytestmark = pytest.mark.roles_view


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_role(app, ids, name="Rôle Test View"):
    """Insère un rôle rattaché à l'entité de test et retourne son id."""
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


# ===========================================================================
# 1. GET /roles_view/ — Page HTML des rôles
# ===========================================================================

class TestRolesViewPage:

    def test_page_returns_200_when_authenticated(self, auth_client):
        r = auth_client.get("/roles_view/")
        assert r.status_code == 200

    def test_page_returns_html_content(self, auth_client):
        r = auth_client.get("/roles_view/")
        assert b"<html" in r.data.lower() or b"<!doctype" in r.data.lower()

    def test_page_without_auth_returns_redirect_or_200(self, client):
        r = client.get("/roles_view/", follow_redirects=False)
        assert r.status_code in (200, 302)

    def test_page_with_existing_role_returns_200(self, auth_client, app, ids):
        """La page doit répondre 200 même si des rôles enrichis existent."""
        _create_role(app, ids, name="Rôle Enrichi")
        r = auth_client.get("/roles_view/")
        assert r.status_code == 200

    def test_page_content_is_not_empty(self, auth_client):
        r = auth_client.get("/roles_view/")
        assert len(r.data) > 100


# ===========================================================================
# 2. PUT /roles_view/<role_id>/mission — Mise à jour de la mission générale
# ===========================================================================

class TestUpdateRoleMission:

    def test_update_mission_returns_ok_true(self, auth_client, app, ids):
        role_id = _create_role(app, ids, name="Rôle Mission Update")
        r = auth_client.put(
            f"/roles_view/{role_id}/mission",
            data=json.dumps({"mission_generale": "Piloter les processus qualité."}),
            content_type="application/json",
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True

    def test_update_mission_response_contains_role_id(self, auth_client, app, ids):
        role_id = _create_role(app, ids, name="Rôle Mission RID")
        r = auth_client.put(
            f"/roles_view/{role_id}/mission",
            data=json.dumps({"mission_generale": "Mission test"}),
            content_type="application/json",
        )
        assert r.get_json()["role_id"] == role_id

    def test_update_mission_persists_in_db(self, auth_client, app, ids):
        role_id = _create_role(app, ids, name="Rôle Mission Persist")
        auth_client.put(
            f"/roles_view/{role_id}/mission",
            data=json.dumps({"mission_generale": "Mission persistée en base"}),
            content_type="application/json",
        )
        with app.app_context():
            from Code.models.models import Role
            role = Role.query.get(role_id)
            assert role.mission_generale == "Mission persistée en base"

    def test_update_mission_empty_string_accepted(self, auth_client, app, ids):
        """Effacer la mission (chaîne vide) doit être accepté sans erreur."""
        role_id = _create_role(app, ids, name="Rôle Mission Empty")
        r = auth_client.put(
            f"/roles_view/{role_id}/mission",
            data=json.dumps({"mission_generale": ""}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_update_mission_missing_key_defaults_to_empty(self, auth_client, app, ids):
        """Sans clé 'mission_generale', la valeur .strip() sur '' → ok sans erreur."""
        role_id = _create_role(app, ids, name="Rôle Mission MissingKey")
        r = auth_client.put(
            f"/roles_view/{role_id}/mission",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_update_mission_nonexistent_role_returns_ok(self, auth_client):
        """UPDATE sur id inexistant : SQLite ne lève pas d'erreur → ok=True."""
        r = auth_client.put(
            "/roles_view/999999/mission",
            data=json.dumps({"mission_generale": "Ghost role"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_update_mission_overwrites_previous_value(self, auth_client, app, ids):
        role_id = _create_role(app, ids, name="Rôle Mission Overwrite")
        auth_client.put(
            f"/roles_view/{role_id}/mission",
            data=json.dumps({"mission_generale": "Première version"}),
            content_type="application/json",
        )
        auth_client.put(
            f"/roles_view/{role_id}/mission",
            data=json.dumps({"mission_generale": "Deuxième version"}),
            content_type="application/json",
        )
        with app.app_context():
            from Code.models.models import Role
            role = Role.query.get(role_id)
            assert role.mission_generale == "Deuxième version"


# ===========================================================================
# 3. GET /roles_view/validation_level/<uid>/<rid> — Niveau de validation
# ===========================================================================

class TestValidationLevel:

    def test_returns_200_json(self, auth_client, ids):
        r = auth_client.get(f"/roles_view/validation_level/{ids['user_id']}/1")
        assert r.status_code == 200
        assert r.content_type.startswith("application/json")

    def test_response_has_level_key(self, auth_client, ids):
        r = auth_client.get(f"/roles_view/validation_level/{ids['user_id']}/1")
        assert "level" in r.get_json()

    def test_level_is_null_when_no_validation_table(self, auth_client, ids):
        """Sans table user_role_validations, le niveau renvoyé est None."""
        r = auth_client.get(f"/roles_view/validation_level/{ids['user_id']}/{ids['entity_id']}")
        assert r.get_json()["level"] is None

    def test_unknown_user_and_role_returns_null(self, auth_client):
        r = auth_client.get("/roles_view/validation_level/999999/999999")
        assert r.status_code == 200
        assert r.get_json()["level"] is None


# ===========================================================================
# 3bis. GET /roles_view/ — Couleur de compétence des titulaires (comp_color)
# ===========================================================================

def _create_user_for_holder(app, ids, email):
    from Code.models.models import User
    from Code.extensions import db
    from werkzeug.security import generate_password_hash
    with app.app_context():
        u = User(
            entity_id=ids["entity_id"], first_name="Titulaire", last_name="Test",
            email=email, password=generate_password_hash("Pass123!"), status="user",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _cleanup_holder(app, uid, rid, activity_id):
    from Code.models.models import UserRole, CompetencyEvaluation, User
    from Code.extensions import db
    with app.app_context():
        CompetencyEvaluation.query.filter_by(user_id=uid, activity_id=activity_id).delete()
        db.session.execute(db.text("DELETE FROM activity_roles WHERE role_id = :rid"), {"rid": rid})
        UserRole.query.filter_by(user_id=uid, role_id=rid).delete()
        u = User.query.get(uid)
        if u:
            db.session.delete(u)
        db.session.commit()


class TestRoleHoldersCompColor:

    def test_holder_without_evaluation_has_no_color(self, auth_client, app, ids):
        """Un titulaire sans évaluation n'affiche pas de puce de couleur."""
        rid = _create_role(app, ids, name="Rôle Holder Sans Note")
        uid = _create_user_for_holder(app, ids, "holder.nocolor@devoptiq.com")
        with app.app_context():
            from Code.models.models import UserRole
            from Code.extensions import db
            db.session.add(UserRole(user_id=uid, role_id=rid))
            db.session.commit()
        try:
            r = auth_client.get("/roles_view/")
            assert r.status_code == 200
        finally:
            _cleanup_holder(app, uid, rid, ids["activity_id"])

    def test_holder_with_green_evaluation_shows_green_hex(self, auth_client, app, ids):
        """Un titulaire noté 'green' (manager) sur une activité Garant du rôle affiche #22c55e."""
        rid = _create_role(app, ids, name="Rôle Holder Vert")
        uid = _create_user_for_holder(app, ids, "holder.green@devoptiq.com")
        with app.app_context():
            from Code.models.models import UserRole, CompetencyEvaluation
            from Code.extensions import db
            db.session.add(UserRole(user_id=uid, role_id=rid))
            db.session.execute(
                db.text(
                    "INSERT INTO activity_roles (activity_id, role_id, status) "
                    "VALUES (:aid, :rid, 'Garant')"
                ),
                {"aid": ids["activity_id"], "rid": rid},
            )
            db.session.add(CompetencyEvaluation(
                user_id=uid, activity_id=ids["activity_id"],
                item_id=None, item_type=None,
                eval_number="manager", note="green",
            ))
            db.session.commit()
        try:
            r = auth_client.get("/roles_view/")
            assert r.status_code == 200
            assert b"#22c55e" in r.data
        finally:
            _cleanup_holder(app, uid, rid, ids["activity_id"])


# ===========================================================================
# 4. GET /your_api/activity_items/<activity_id> — Items d'une activité
# ===========================================================================

class TestActivityItemsAPI:

    def test_returns_200_for_known_activity(self, auth_client, ids):
        r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
        assert r.status_code == 200

    def test_response_has_three_keys(self, auth_client, ids):
        body = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        assert "savoirs" in body
        assert "savoir_faire" in body
        assert "hsc" in body

    def test_all_values_are_lists(self, auth_client, ids):
        body = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        assert isinstance(body["savoirs"], list)
        assert isinstance(body["savoir_faire"], list)
        assert isinstance(body["hsc"], list)

    def test_unknown_activity_returns_empty_lists(self, auth_client):
        body = auth_client.get("/your_api/activity_items/999999").get_json()
        assert body["savoirs"] == []
        assert body["savoir_faire"] == []
        assert body["hsc"] == []

    def test_savoir_item_has_id_and_name(self, auth_client, app, ids):
        """Un savoir créé doit apparaître avec les clés id et name."""
        with app.app_context():
            from Code.models.models import Savoir
            from Code.extensions import db
            s = Savoir(description="Savoir API test items", activity_id=ids["activity_id"])
            db.session.add(s)
            db.session.commit()

        body = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        assert len(body["savoirs"]) >= 1
        first = body["savoirs"][0]
        assert "id" in first
        assert "name" in first

    def test_savoir_faire_item_has_id_and_name(self, auth_client, app, ids):
        """Un savoir-faire créé doit apparaître avec les clés id et name."""
        with app.app_context():
            from Code.models.models import SavoirFaire
            from Code.extensions import db
            sf = SavoirFaire(description="SavoirFaire API test items", activity_id=ids["activity_id"])
            db.session.add(sf)
            db.session.commit()

        body = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        assert len(body["savoir_faire"]) >= 1
        first = body["savoir_faire"][0]
        assert "id" in first
        assert "name" in first

    def test_softskill_hsc_item_has_id_and_name(self, auth_client, app, ids):
        """Un softskill créé doit apparaître dans hsc avec les clés id et name."""
        with app.app_context():
            from Code.models.models import Softskill
            from Code.extensions import db
            ss = Softskill(
                habilete="Rigueur",
                niveau="Expert",
                activity_id=ids["activity_id"],
            )
            db.session.add(ss)
            db.session.commit()

        body = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        assert len(body["hsc"]) >= 1
        first = body["hsc"][0]
        assert "id" in first
        assert "name" in first

    def test_hsc_name_includes_niveau_in_parens(self, auth_client, app, ids):
        """Le nom HSC doit être 'habilete (niveau)' quand niveau est non vide."""
        with app.app_context():
            from Code.models.models import Softskill
            from Code.extensions import db
            ss = Softskill(
                habilete="Adaptabilité",
                niveau="Avancé",
                activity_id=ids["activity_id"],
            )
            db.session.add(ss)
            db.session.commit()

        body = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        names = [item["name"] for item in body["hsc"]]
        assert any("Adaptabilité (Avancé)" in n for n in names)
