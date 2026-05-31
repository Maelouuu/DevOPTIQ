# tests/test_29_constraints.py
"""
Pages : API Contraintes (/constraints) + ajouts via blueprint activités (/activities)
Couvre : CRUD complet des contraintes, rendu partiel, cas limites (vide, 404, mauvaise activité).
"""
import pytest
import json

pytestmark = pytest.mark.constraints


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_constraint(app, activity_id, description="Contrainte de test", file_path=None):
    """Insère une contrainte en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Constraint
        from Code.extensions import db
        c = Constraint(activity_id=activity_id, description=description, file_path=file_path)
        db.session.add(c)
        db.session.commit()
        return c.id


def _delete_constraint(app, constraint_id):
    """Supprime une contrainte en base (nettoyage)."""
    with app.app_context():
        from Code.models.models import Constraint
        from Code.extensions import db
        c = Constraint.query.get(constraint_id)
        if c:
            db.session.delete(c)
            db.session.commit()


# ===========================================================================
# 1. Création de contrainte — POST /constraints/<activity_id>/add
# ===========================================================================

class TestConstraintsCreate:

    def test_add_constraint_success(self, auth_client, ids, app):
        """Crée une contrainte avec description valide → 201 + objet retourné."""
        r = auth_client.post(
            f"/constraints/{ids['activity_id']}/add",
            data=json.dumps({"description": "Contrainte créée en test"}),
            content_type="application/json",
        )
        assert r.status_code == 201
        body = json.loads(r.data)
        assert "id" in body
        assert body["description"] == "Contrainte créée en test"
        assert body.get("file_path") is None
        _delete_constraint(app, body["id"])

    def test_add_constraint_with_file_path(self, auth_client, ids, app):
        """Crée une contrainte avec file_path → retourné dans la réponse."""
        r = auth_client.post(
            f"/constraints/{ids['activity_id']}/add",
            data=json.dumps({"description": "Avec fichier", "file_path": "/docs/ref.pdf"}),
            content_type="application/json",
        )
        assert r.status_code == 201
        body = json.loads(r.data)
        assert body["file_path"] == "/docs/ref.pdf"
        _delete_constraint(app, body["id"])

    def test_add_constraint_empty_description_returns_400(self, auth_client, ids):
        """Description vide → 400."""
        r = auth_client.post(
            f"/constraints/{ids['activity_id']}/add",
            data=json.dumps({"description": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert b"description" in r.data.lower()

    def test_add_constraint_missing_description_returns_400(self, auth_client, ids):
        """Payload sans clé description → 400."""
        r = auth_client.post(
            f"/constraints/{ids['activity_id']}/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_constraint_whitespace_description_returns_400(self, auth_client, ids):
        """Description contenant uniquement des espaces → 400 (après strip)."""
        r = auth_client.post(
            f"/constraints/{ids['activity_id']}/add",
            data=json.dumps({"description": "   "}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_constraint_activity_not_found_returns_404(self, auth_client):
        """Activité inexistante → 404."""
        r = auth_client.post(
            "/constraints/999999/add",
            data=json.dumps({"description": "Test 404"}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert b"not found" in r.data.lower()


# ===========================================================================
# 2. Mise à jour — PUT /constraints/<activity_id>/<constraint_id>
# ===========================================================================

class TestConstraintsUpdate:

    def test_update_constraint_success(self, auth_client, ids, app):
        """Met à jour la description d'une contrainte → 200 + description mise à jour."""
        cid = _create_constraint(app, ids["activity_id"], "Description initiale")
        r = auth_client.put(
            f"/constraints/{ids['activity_id']}/{cid}",
            data=json.dumps({"description": "Description modifiée"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["description"] == "Description modifiée"
        _delete_constraint(app, cid)

    def test_update_constraint_file_path(self, auth_client, ids, app):
        """Met à jour file_path → retourné dans la réponse."""
        cid = _create_constraint(app, ids["activity_id"], "Avec fichier update")
        r = auth_client.put(
            f"/constraints/{ids['activity_id']}/{cid}",
            data=json.dumps({"description": "Avec fichier update", "file_path": "/new/path.pdf"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["file_path"] == "/new/path.pdf"
        _delete_constraint(app, cid)

    def test_update_constraint_empty_description_returns_400(self, auth_client, ids, app):
        """Description vide lors de la mise à jour → 400."""
        cid = _create_constraint(app, ids["activity_id"], "À modifier")
        r = auth_client.put(
            f"/constraints/{ids['activity_id']}/{cid}",
            data=json.dumps({"description": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400
        _delete_constraint(app, cid)

    def test_update_constraint_not_found_returns_404(self, auth_client, ids):
        """Contrainte inexistante → 404."""
        r = auth_client.put(
            f"/constraints/{ids['activity_id']}/999999",
            data=json.dumps({"description": "Ghost update"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_constraint_wrong_activity_returns_404(self, auth_client, ids, app):
        """Contrainte existante mais associée à une autre activité → 404."""
        cid = _create_constraint(app, ids["activity_id"], "Bonne activité")
        r = auth_client.put(
            f"/constraints/999999/{cid}",
            data=json.dumps({"description": "Mauvaise activité"}),
            content_type="application/json",
        )
        assert r.status_code == 404
        _delete_constraint(app, cid)


# ===========================================================================
# 3. Suppression — DELETE /constraints/<activity_id>/<constraint_id>
# ===========================================================================

class TestConstraintsDelete:

    def test_delete_constraint_success(self, auth_client, ids, app):
        """Supprime une contrainte existante → 200 + message."""
        cid = _create_constraint(app, ids["activity_id"], "À supprimer")
        r = auth_client.delete(f"/constraints/{ids['activity_id']}/{cid}")
        assert r.status_code == 200
        assert b"deleted" in r.data.lower()

    def test_delete_constraint_not_found_returns_404(self, auth_client, ids):
        """Contrainte inexistante → 404."""
        r = auth_client.delete(f"/constraints/{ids['activity_id']}/999999")
        assert r.status_code == 404

    def test_delete_constraint_wrong_activity_returns_404(self, auth_client, ids, app):
        """Contrainte existante sur une autre activité → 404."""
        cid = _create_constraint(app, ids["activity_id"], "Mauvaise activité suppr")
        r = auth_client.delete(f"/constraints/999999/{cid}")
        assert r.status_code == 404
        _delete_constraint(app, cid)

    def test_delete_constraint_twice_returns_404(self, auth_client, ids, app):
        """Supprimer deux fois la même contrainte → première OK, deuxième 404."""
        cid = _create_constraint(app, ids["activity_id"], "Double suppression")
        r1 = auth_client.delete(f"/constraints/{ids['activity_id']}/{cid}")
        assert r1.status_code == 200
        r2 = auth_client.delete(f"/constraints/{ids['activity_id']}/{cid}")
        assert r2.status_code == 404


# ===========================================================================
# 4. Rendu partiel — GET /constraints/<activity_id>/render
# ===========================================================================

class TestConstraintsRender:

    def test_render_constraints_activity_exists(self, auth_client, ids):
        """L'activité existe → rendu HTML (200)."""
        r = auth_client.get(f"/constraints/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"html" in r.data.lower() or len(r.data) > 0

    def test_render_constraints_with_data(self, auth_client, ids, app):
        """Rendu contient la contrainte si elle existe."""
        cid = _create_constraint(app, ids["activity_id"], "Contrainte visible dans le rendu")
        r = auth_client.get(f"/constraints/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"Contrainte visible dans le rendu" in r.data
        _delete_constraint(app, cid)

    def test_render_constraints_activity_not_found(self, auth_client):
        """Activité inexistante → 404."""
        r = auth_client.get("/constraints/999999/render")
        assert r.status_code == 404


# ===========================================================================
# 5. Ajout via blueprint activités — POST /activities/constraints/add
# ===========================================================================

class TestActivitiesConstraintsBlueprint:

    def test_add_constraint_via_activities_bp(self, auth_client, ids, app):
        """Ajoute une contrainte via le blueprint activités → 200."""
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"activity_id": ids["activity_id"], "description": "Via activities bp"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert b"ajout" in r.data.lower()

    def test_add_constraint_via_activities_bp_missing_activity_id_returns_400(self, auth_client):
        """Sans activity_id → 400."""
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"description": "Pas d'activité"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_constraint_via_activities_bp_empty_description_returns_400(self, auth_client, ids):
        """Description vide → 400."""
        r = auth_client.post(
            "/activities/constraints/add",
            data=json.dumps({"activity_id": ids["activity_id"], "description": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_data_via_activities_bp(self, auth_client):
        """Ajoute une donnée via /activities/data/add → 200."""
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"name": "Donnée blueprint test", "type": "nourrissante"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert b"ajout" in r.data.lower()

    def test_add_data_missing_name_returns_400(self, auth_client):
        """Sans name → 400."""
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"type": "nourrissante"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_data_missing_type_returns_400(self, auth_client):
        """Sans type → 400."""
        r = auth_client.post(
            "/activities/data/add",
            data=json.dumps({"name": "Sans type"}),
            content_type="application/json",
        )
        assert r.status_code == 400
