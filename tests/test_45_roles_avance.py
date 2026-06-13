# tests/test_45_roles_avance.py
"""
Couverture avancée de la page Rôles (roles.py) — complément de test_10.

Routes couvertes :
  GET  /roles/list                          → liste triée des rôles de l'entité active
  POST /roles/garant/activity/<activity_id> → affectation (ou création) d'un rôle Garant
  PUT  /roles/<role_id>                     → renommer un rôle
  DELETE /roles/<role_id>                   → supprimer un rôle + ses associations

test_10 avait 5 tests très permissifs (assert in (200, 404)).
Ce fichier teste les comportements précis : codes HTTP exacts, contenu JSON,
effets en base de données, cas limites.
"""
import pytest

pytestmark = pytest.mark.roles_avance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_role(app, entity_id, name="Rôle Test Avancé"):
    """Insère un rôle en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        role = Role(name=name, entity_id=entity_id)
        db.session.add(role)
        db.session.commit()
        return role.id


def _delete_role(app, role_id):
    """Supprime un rôle en base (nettoyage)."""
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        from sqlalchemy import text
        db.session.execute(text("DELETE FROM activity_roles WHERE role_id=:rid"), {"rid": role_id})
        db.session.execute(text("DELETE FROM task_roles WHERE role_id=:rid"), {"rid": role_id})
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
        db.session.commit()


def _role_exists(app, role_id):
    """Retourne True si le rôle existe encore en base."""
    with app.app_context():
        from Code.models.models import Role
        return Role.query.get(role_id) is not None


def _get_role_name(app, role_id):
    """Retourne le nom du rôle en base."""
    with app.app_context():
        from Code.models.models import Role
        r = Role.query.get(role_id)
        return r.name if r else None


def _get_garant_role_id(app, activity_id):
    """Retourne le role_id du garant pour une activité, ou None."""
    with app.app_context():
        from Code.extensions import db
        from sqlalchemy import text
        row = db.session.execute(
            text("SELECT role_id FROM activity_roles WHERE activity_id=:aid AND status='Garant'"),
            {"aid": activity_id}
        ).fetchone()
        return row[0] if row else None


# ===========================================================================
# 1. GET /roles/list
# ===========================================================================

class TestListRoles:

    def test_retourne_200(self, auth_client):
        """GET /roles/list retourne toujours 200."""
        r = auth_client.get("/roles/list")
        assert r.status_code == 200

    def test_reponse_est_tableau_json(self, auth_client):
        """La réponse est un tableau JSON (même vide)."""
        r = auth_client.get("/roles/list")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)

    def test_contient_id_et_name(self, auth_client, app, ids):
        """Chaque rôle retourné expose les champs id et name."""
        rid = _create_role(app, ids["entity_id"], "Rôle Champs List")
        try:
            r = auth_client.get("/roles/list")
            data = r.get_json()
            found = [x for x in data if x.get("id") == rid]
            assert len(found) == 1
            assert "id" in found[0]
            assert "name" in found[0]
        finally:
            _delete_role(app, rid)

    def test_role_cree_apparait_dans_liste(self, auth_client, app, ids):
        """Un rôle créé en base apparaît dans GET /roles/list."""
        rid = _create_role(app, ids["entity_id"], "Rôle Visible List")
        try:
            r = auth_client.get("/roles/list")
            data = r.get_json()
            names = [x["name"] for x in data]
            assert "Rôle Visible List" in names
        finally:
            _delete_role(app, rid)

    def test_role_supprime_absent_de_liste(self, auth_client, app, ids):
        """Après suppression, le rôle n'apparaît plus dans GET /roles/list."""
        rid = _create_role(app, ids["entity_id"], "Rôle À Supprimer List")
        _delete_role(app, rid)
        r = auth_client.get("/roles/list")
        data = r.get_json()
        names = [x["name"] for x in data]
        assert "Rôle À Supprimer List" not in names

    def test_contenu_type_json(self, auth_client):
        """Content-Type est application/json."""
        r = auth_client.get("/roles/list")
        assert r.content_type.startswith("application/json")


# ===========================================================================
# 2. POST /roles/garant/activity/<activity_id>
# ===========================================================================

class TestGarantRole:

    def test_sans_role_name_retourne_400(self, auth_client, ids):
        """Corps sans role_name → 400."""
        r = auth_client.post(
            f"/roles/garant/activity/{ids['activity_id']}",
            json={},
        )
        assert r.status_code == 400

    def test_role_name_vide_retourne_400(self, auth_client, ids):
        """role_name vide → 400."""
        r = auth_client.post(
            f"/roles/garant/activity/{ids['activity_id']}",
            json={"role_name": "   "},
        )
        assert r.status_code == 400

    def test_garant_succes_retourne_200(self, auth_client, ids, app):
        """Affectation valide d'un garant → 200."""
        rid = _create_role(app, ids["entity_id"], "Garant Succès Test")
        try:
            r = auth_client.post(
                f"/roles/garant/activity/{ids['activity_id']}",
                json={"role_name": "Garant Succès Test"},
            )
            assert r.status_code == 200
        finally:
            _delete_role(app, rid)

    def test_garant_reponse_contient_message(self, auth_client, ids, app):
        """La réponse 200 contient un champ 'message'."""
        rid = _create_role(app, ids["entity_id"], "Garant Message Test")
        try:
            r = auth_client.post(
                f"/roles/garant/activity/{ids['activity_id']}",
                json={"role_name": "Garant Message Test"},
            )
            assert r.status_code == 200
            data = r.get_json()
            assert "message" in data
        finally:
            _delete_role(app, rid)

    def test_garant_reponse_contient_role(self, auth_client, ids, app):
        """La réponse 200 contient un objet 'role' avec id et name."""
        rid = _create_role(app, ids["entity_id"], "Garant Role Object")
        try:
            r = auth_client.post(
                f"/roles/garant/activity/{ids['activity_id']}",
                json={"role_name": "Garant Role Object"},
            )
            assert r.status_code == 200
            data = r.get_json()
            assert "role" in data
            assert "id" in data["role"]
            assert "name" in data["role"]
        finally:
            _delete_role(app, rid)

    def test_garant_cree_role_si_inexistant(self, auth_client, ids, app):
        """Si le rôle n'existe pas, il est créé automatiquement."""
        unique_name = "Rôle Auto-Créé Garant XYZ"
        r = auth_client.post(
            f"/roles/garant/activity/{ids['activity_id']}",
            json={"role_name": unique_name},
        )
        assert r.status_code == 200
        with app.app_context():
            from Code.models.models import Role
            role = Role.query.filter_by(name=unique_name).first()
            assert role is not None
            role_id = role.id
        _delete_role(app, role_id)

    def test_garant_enregistre_en_activity_roles(self, auth_client, ids, app):
        """Après affectation, activity_roles contient le garant."""
        rid = _create_role(app, ids["entity_id"], "Garant DB Check")
        try:
            auth_client.post(
                f"/roles/garant/activity/{ids['activity_id']}",
                json={"role_name": "Garant DB Check"},
            )
            garant_rid = _get_garant_role_id(app, ids["activity_id"])
            assert garant_rid == rid
        finally:
            _delete_role(app, rid)

    def test_garant_remplace_ancien(self, auth_client, ids, app):
        """Un second garant remplace le premier dans activity_roles."""
        rid1 = _create_role(app, ids["entity_id"], "Garant Ancien")
        rid2 = _create_role(app, ids["entity_id"], "Garant Nouveau")
        try:
            auth_client.post(
                f"/roles/garant/activity/{ids['activity_id']}",
                json={"role_name": "Garant Ancien"},
            )
            auth_client.post(
                f"/roles/garant/activity/{ids['activity_id']}",
                json={"role_name": "Garant Nouveau"},
            )
            garant_rid = _get_garant_role_id(app, ids["activity_id"])
            assert garant_rid == rid2
        finally:
            _delete_role(app, rid1)
            _delete_role(app, rid2)


# ===========================================================================
# 3. PUT /roles/<role_id>
# ===========================================================================

class TestUpdateRole:

    def test_update_succes_retourne_200(self, auth_client, ids, app):
        """PUT avec nom valide → 200."""
        rid = _create_role(app, ids["entity_id"], "Rôle À Renommer")
        try:
            r = auth_client.put(f"/roles/{rid}", json={"name": "Rôle Renommé"})
            assert r.status_code == 200
        finally:
            _delete_role(app, rid)

    def test_update_nom_vide_retourne_400(self, auth_client, ids, app):
        """PUT avec nom vide → 400."""
        rid = _create_role(app, ids["entity_id"], "Rôle Nom Vide Test")
        try:
            r = auth_client.put(f"/roles/{rid}", json={"name": ""})
            assert r.status_code == 400
        finally:
            _delete_role(app, rid)

    def test_update_inexistant_retourne_404(self, auth_client):
        """PUT sur ID inexistant → 404."""
        r = auth_client.put("/roles/999999", json={"name": "Fantôme"})
        assert r.status_code == 404

    def test_update_persist_en_db(self, auth_client, ids, app):
        """Après PUT, le nouveau nom est en base."""
        rid = _create_role(app, ids["entity_id"], "Avant Update")
        try:
            auth_client.put(f"/roles/{rid}", json={"name": "Après Update"})
            assert _get_role_name(app, rid) == "Après Update"
        finally:
            _delete_role(app, rid)

    def test_update_reponse_contient_id(self, auth_client, ids, app):
        """La réponse PUT contient l'id du rôle mis à jour."""
        rid = _create_role(app, ids["entity_id"], "Rôle ID Réponse")
        try:
            r = auth_client.put(f"/roles/{rid}", json={"name": "Nom Mis À Jour"})
            assert r.status_code == 200
            data = r.get_json()
            assert "role" in data
            assert data["role"]["id"] == rid
        finally:
            _delete_role(app, rid)

    def test_update_reponse_contient_nouveau_nom(self, auth_client, ids, app):
        """La réponse PUT contient le nouveau nom dans l'objet role."""
        rid = _create_role(app, ids["entity_id"], "Rôle Nom Réponse")
        try:
            r = auth_client.put(f"/roles/{rid}", json={"name": "Nouveau Nom Réponse"})
            assert r.status_code == 200
            data = r.get_json()
            assert data["role"]["name"] == "Nouveau Nom Réponse"
        finally:
            _delete_role(app, rid)

    def test_update_sans_body_retourne_400(self, auth_client, ids, app):
        """PUT sans body JSON → 400 (name manquant)."""
        rid = _create_role(app, ids["entity_id"], "Rôle Sans Body")
        try:
            r = auth_client.put(f"/roles/{rid}", json={})
            assert r.status_code == 400
        finally:
            _delete_role(app, rid)


# ===========================================================================
# 4. DELETE /roles/<role_id>
# ===========================================================================

class TestDeleteRole:

    def test_delete_succes_retourne_200(self, auth_client, ids, app):
        """DELETE sur rôle existant → 200."""
        rid = _create_role(app, ids["entity_id"], "Rôle À Supprimer Delete")
        r = auth_client.delete(f"/roles/{rid}")
        assert r.status_code == 200

    def test_delete_inexistant_retourne_404(self, auth_client):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete("/roles/999999")
        assert r.status_code == 404

    def test_delete_supprime_de_db(self, auth_client, ids, app):
        """Après DELETE, le rôle n'existe plus en base."""
        rid = _create_role(app, ids["entity_id"], "Rôle Supprimé DB")
        auth_client.delete(f"/roles/{rid}")
        assert not _role_exists(app, rid)

    def test_delete_reponse_contient_message(self, auth_client, ids, app):
        """La réponse DELETE contient un champ 'message'."""
        rid = _create_role(app, ids["entity_id"], "Rôle Message Delete")
        r = auth_client.delete(f"/roles/{rid}")
        assert r.status_code == 200
        data = r.get_json()
        assert "message" in data

    def test_delete_supprime_associations_activity_roles(self, auth_client, ids, app):
        """Après DELETE, les entrées dans activity_roles sont supprimées."""
        rid = _create_role(app, ids["entity_id"], "Rôle Associations")
        # Créer une association garant
        auth_client.post(
            f"/roles/garant/activity/{ids['activity_id']}",
            json={"role_name": "Rôle Associations"},
        )
        # Supprimer le rôle via l'API
        auth_client.delete(f"/roles/{rid}")
        # Vérifier que l'association a été supprimée
        with app.app_context():
            from Code.extensions import db
            from sqlalchemy import text
            row = db.session.execute(
                text("SELECT 1 FROM activity_roles WHERE role_id=:rid"),
                {"rid": rid}
            ).fetchone()
            assert row is None

    def test_delete_content_type_json(self, auth_client, ids, app):
        """La réponse DELETE est en JSON."""
        rid = _create_role(app, ids["entity_id"], "Rôle ContentType Delete")
        r = auth_client.delete(f"/roles/{rid}")
        assert r.content_type.startswith("application/json")

    def test_double_delete_retourne_404(self, auth_client, ids, app):
        """Supprimer deux fois le même rôle → 404 au second appel."""
        rid = _create_role(app, ids["entity_id"], "Rôle Double Delete")
        auth_client.delete(f"/roles/{rid}")
        r = auth_client.delete(f"/roles/{rid}")
        assert r.status_code == 404
