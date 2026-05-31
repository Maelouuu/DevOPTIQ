# tests/test_30_skills_api.py
"""
Page : API Compétences Legacy (/skills)
Couvre : CRUD compétence (ajout, mise à jour, suppression), cas limites, proposition IA (sans clé → 500).
"""
import pytest
import json

pytestmark = pytest.mark.skills_api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_competency(app, activity_id, description="Compétence test"):
    """Insère une compétence en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Competency
        from Code.extensions import db
        c = Competency(activity_id=activity_id, description=description)
        db.session.add(c)
        db.session.commit()
        return c.id


def _delete_competency(app, competency_id):
    """Supprime une compétence (nettoyage)."""
    with app.app_context():
        from Code.models.models import Competency
        from Code.extensions import db
        c = Competency.query.get(competency_id)
        if c:
            db.session.delete(c)
            db.session.commit()


# ===========================================================================
# 1. Ajout — POST /skills/add
# ===========================================================================

class TestSkillsAdd:

    def test_add_competency_success(self, auth_client, ids, app):
        """Ajoute une compétence valide → 201 + objet retourné."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({"activity_id": ids["activity_id"], "description": "Maîtriser le flux de données"}),
            content_type="application/json",
        )
        assert r.status_code == 201
        body = json.loads(r.data)
        assert "id" in body
        assert body["description"] == "Maîtriser le flux de données"
        assert body["activity_id"] == ids["activity_id"]
        _delete_competency(app, body["id"])

    def test_add_competency_missing_activity_id_returns_400(self, auth_client):
        """Sans activity_id → 400."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({"description": "Aucun identifiant activité"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_competency_missing_description_returns_400(self, auth_client, ids):
        """Sans description → 400."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_competency_empty_description_returns_400(self, auth_client, ids):
        """Description vide → 400."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({"activity_id": ids["activity_id"], "description": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_competency_empty_payload_returns_400(self, auth_client):
        """Payload vide → 400."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ===========================================================================
# 2. Mise à jour — PUT /skills/<competency_id>
# ===========================================================================

class TestSkillsUpdate:

    def test_update_competency_success(self, auth_client, ids, app):
        """Met à jour la description d'une compétence → 200 + nouvelle valeur."""
        cid = _create_competency(app, ids["activity_id"], "Ancienne description")
        r = auth_client.put(
            f"/skills/{cid}",
            data=json.dumps({"description": "Nouvelle description"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["description"] == "Nouvelle description"
        _delete_competency(app, cid)

    def test_update_competency_empty_description_returns_400(self, auth_client, ids, app):
        """Description vide lors de la mise à jour → 400."""
        cid = _create_competency(app, ids["activity_id"], "À modifier")
        r = auth_client.put(
            f"/skills/{cid}",
            data=json.dumps({"description": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400
        _delete_competency(app, cid)

    def test_update_competency_not_found_returns_404(self, auth_client):
        """Compétence inexistante → 404."""
        r = auth_client.put(
            "/skills/999999",
            data=json.dumps({"description": "Ghost"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_competency_missing_description_returns_400(self, auth_client, ids, app):
        """Payload sans clé description → 400."""
        cid = _create_competency(app, ids["activity_id"], "Sans clé")
        r = auth_client.put(
            f"/skills/{cid}",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400
        _delete_competency(app, cid)


# ===========================================================================
# 3. Suppression — DELETE /skills/<competency_id>
# ===========================================================================

class TestSkillsDelete:

    def test_delete_competency_success(self, auth_client, ids, app):
        """Supprime une compétence existante → 200 + message."""
        cid = _create_competency(app, ids["activity_id"], "À supprimer")
        r = auth_client.delete(f"/skills/{cid}")
        assert r.status_code == 200
        assert b"deleted" in r.data.lower()

    def test_delete_competency_not_found_returns_404(self, auth_client):
        """Compétence inexistante → 404."""
        r = auth_client.delete("/skills/999999")
        assert r.status_code == 404

    def test_delete_competency_twice_returns_404(self, auth_client, ids, app):
        """Supprimer deux fois → première OK, deuxième 404."""
        cid = _create_competency(app, ids["activity_id"], "Double suppression")
        r1 = auth_client.delete(f"/skills/{cid}")
        assert r1.status_code == 200
        r2 = auth_client.delete(f"/skills/{cid}")
        assert r2.status_code == 404


# ===========================================================================
# 4. Proposition IA — POST /skills/propose (sans clé OpenAI → 500)
# ===========================================================================

class TestSkillsPropose:

    def test_propose_without_openai_key_returns_500(self, auth_client, ids, monkeypatch):
        """Sans OPENAI_API_KEY, l'endpoint retourne 500 avec message d'erreur."""
        import os
        monkeypatch.delitem(os.environ, "OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({
                "name": "Gestion documentaire",
                "input_data": "Documents entrants",
                "output_data": "Rapports validés",
                "tasks": [{"name": "Classifier"}, {"name": "Archiver"}],
                "outgoing": [],
                "tools": [{"name": "SharePoint"}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 500
        body = json.loads(r.data)
        assert "error" in body

    def test_propose_minimal_payload_without_key_returns_500(self, auth_client, monkeypatch):
        """Payload minimal sans clé → 500."""
        import os
        monkeypatch.delitem(os.environ, "OPENAI_API_KEY", raising=False)
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 500
