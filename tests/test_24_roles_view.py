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
