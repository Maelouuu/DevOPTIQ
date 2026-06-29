# tests/test_51_aptitudes_softskills_avance.py
"""
Page : Aptitudes & HSC — CRUD avancé & isolation (aptitudes.py, softskills.py)
Couvre :
  - POST /aptitudes/add                         → création, validation, format exact
  - PUT  /aptitudes/<act_id>/<apt_id>           → mise à jour, persistance, isolation cross-activité
  - DELETE /aptitudes/<act_id>/<apt_id>         → suppression, vérification DB
  - GET  /aptitudes/<act_id>/render             → rendu HTML partiel
  - POST /softskills/add                        → création & idempotence (même habilete)
  - PUT  /softskills/<act_id>/<ss_id>           → mise à jour & isolation
  - DELETE /softskills/<act_id>/<ss_id>         → suppression & isolation cross-activité
  - GET  /softskills/<act_id>/render            → rendu HTML partiel
"""
import json
import pytest

pytestmark = pytest.mark.aptitudes_softskills_avance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _put(client, url, payload):
    return client.put(url, data=json.dumps(payload), content_type="application/json")


def _create_activity(app, ids, name="Activité Apt/SS Avancé"):
    """Insère une activité de test dédiée et retourne son id."""
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        act = Activities(entity_id=ids["entity_id"], name=name, description="test avancé")
        db.session.add(act)
        db.session.commit()
        return act.id


def _create_aptitude(app, activity_id, description="Aptitude Fixture"):
    """Insère une aptitude en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Aptitude
        from Code.extensions import db
        a = Aptitude(description=description, activity_id=activity_id)
        db.session.add(a)
        db.session.commit()
        return a.id


def _create_softskill(app, activity_id, habilete="Gestion du stress", niveau="2"):
    """Insère un softskill en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Softskill
        from Code.extensions import db
        ss = Softskill(activity_id=activity_id, habilete=habilete, niveau=niveau, justification="")
        db.session.add(ss)
        db.session.commit()
        return ss.id


# ===========================================================================
# APTITUDES — création
# ===========================================================================

class TestAptitudesCreate:

    def test_create_returns_201(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude avancée créée", "activity_id": ids["activity_id"]
        })
        assert r.status_code == 201

    def test_create_response_has_id_field(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude avec id", "activity_id": ids["activity_id"]
        })
        assert "id" in r.get_json()

    def test_create_response_has_description_field(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude avec description", "activity_id": ids["activity_id"]
        })
        body = r.get_json()
        assert body.get("description") == "Aptitude avec description"

    def test_create_persists_in_db(self, auth_client, ids, app):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude persistée DB", "activity_id": ids["activity_id"]
        })
        apt_id = r.get_json()["id"]
        with app.app_context():
            from Code.models.models import Aptitude
            stored = Aptitude.query.get(apt_id)
            assert stored is not None
            assert stored.description == "Aptitude persistée DB"
            assert stored.activity_id == ids["activity_id"]

    def test_create_missing_description_returns_400(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {"activity_id": ids["activity_id"]})
        assert r.status_code == 400

    def test_create_empty_description_returns_400(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "", "activity_id": ids["activity_id"]
        })
        assert r.status_code == 400

    def test_create_missing_activity_id_returns_400(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {"description": "Sans activité"})
        assert r.status_code == 400

    def test_create_nonexistent_activity_returns_404(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude activité fantôme", "activity_id": 999999
        })
        assert r.status_code == 404

    def test_create_whitespace_only_description_returns_400(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "   ", "activity_id": ids["activity_id"]
        })
        assert r.status_code == 400

    def test_create_multiple_aptitudes_independent(self, auth_client, ids, app):
        """Plusieurs aptitudes sur la même activité → IDs distincts."""
        r1 = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude multi 1", "activity_id": ids["activity_id"]
        })
        r2 = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude multi 2", "activity_id": ids["activity_id"]
        })
        assert r1.get_json()["id"] != r2.get_json()["id"]


# ===========================================================================
# APTITUDES — mise à jour
# ===========================================================================

class TestAptitudesUpdate:

    def test_update_returns_200(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], "Avant màj")
        r = _put(auth_client, f"/aptitudes/{ids['activity_id']}/{apt_id}",
                 {"description": "Après màj"})
        assert r.status_code == 200

    def test_update_response_has_id_and_description(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], "Avant format")
        r = _put(auth_client, f"/aptitudes/{ids['activity_id']}/{apt_id}",
                 {"description": "Après format"})
        body = r.get_json()
        assert "id" in body
        assert body.get("description") == "Après format"

    def test_update_persists_in_db(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], "Avant persist")
        _put(auth_client, f"/aptitudes/{ids['activity_id']}/{apt_id}",
             {"description": "Après persist"})
        with app.app_context():
            from Code.models.models import Aptitude
            a = Aptitude.query.get(apt_id)
            assert a.description == "Après persist"

    def test_update_empty_description_returns_400(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], "Non modifié")
        r = _put(auth_client, f"/aptitudes/{ids['activity_id']}/{apt_id}",
                 {"description": ""})
        assert r.status_code == 400

    def test_update_nonexistent_aptitude_returns_404(self, auth_client, ids):
        r = _put(auth_client, f"/aptitudes/{ids['activity_id']}/999999",
                 {"description": "Fantôme"})
        assert r.status_code == 404

    def test_update_cross_activity_isolation(self, auth_client, ids, app):
        """PUT avec un activity_id différent → 404 (l'aptitude appartient à une autre activité)."""
        other_act_id = _create_activity(app, ids, "Activité Apt Isolation Màj")
        apt_id = _create_aptitude(app, other_act_id, "Aptitude isolée màj")
        r = _put(auth_client, f"/aptitudes/{ids['activity_id']}/{apt_id}",
                 {"description": "Tentative cross"})
        assert r.status_code == 404


# ===========================================================================
# APTITUDES — suppression
# ===========================================================================

class TestAptitudesDelete:

    def test_delete_returns_200(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], "À supprimer 200")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        assert r.status_code == 200

    def test_delete_removes_from_db(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], "À supprimer DB")
        auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        with app.app_context():
            from Code.models.models import Aptitude
            assert Aptitude.query.get(apt_id) is None

    def test_delete_response_has_message(self, auth_client, ids, app):
        apt_id = _create_aptitude(app, ids["activity_id"], "À supprimer msg")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        body = r.get_json()
        assert "message" in body

    def test_delete_nonexistent_returns_404(self, auth_client, ids):
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/999999")
        assert r.status_code == 404

    def test_delete_cross_activity_isolation(self, auth_client, ids, app):
        """DELETE avec un activity_id différent → 404."""
        other_act_id = _create_activity(app, ids, "Activité Apt Isolation Delete")
        apt_id = _create_aptitude(app, other_act_id, "Aptitude isolée delete")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        assert r.status_code == 404

    def test_delete_idempotent_second_call_returns_404(self, auth_client, ids, app):
        """Supprimer deux fois le même id → la deuxième fois 404."""
        apt_id = _create_aptitude(app, ids["activity_id"], "À supprimer 2x")
        auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{apt_id}")
        assert r.status_code == 404


# ===========================================================================
# APTITUDES — rendu partiel
# ===========================================================================

class TestAptitudesRender:

    def test_render_valid_activity_returns_200(self, auth_client, ids):
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert r.status_code == 200

    def test_render_returns_html(self, auth_client, ids):
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert b"<" in r.data

    def test_render_nonexistent_activity_returns_404(self, auth_client):
        r = auth_client.get("/aptitudes/999999/render")
        assert r.status_code == 404

    def test_render_contains_created_aptitude(self, auth_client, ids, app):
        """Une aptitude créée apparaît dans le rendu HTML."""
        _create_aptitude(app, ids["activity_id"], "Aptitude visible dans rendu")
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert b"Aptitude visible dans rendu" in r.data


# ===========================================================================
# SOFTSKILLS — création
# ===========================================================================

class TestSoftskillsCreate:

    def test_create_new_returns_201(self, auth_client, ids):
        r = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": "Prise de décision Test 201",
            "niveau": "2",
            "justification": "Justification test",
        })
        assert r.status_code == 201

    def test_create_response_has_all_fields(self, auth_client, ids):
        r = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": "Résolution de problèmes Champs",
            "niveau": "3",
            "justification": "Justif champs",
        })
        body = r.get_json()
        for field in ("id", "activity_id", "habilete", "niveau", "justification"):
            assert field in body, f"Champ manquant : {field}"

    def test_create_persists_in_db(self, auth_client, ids, app):
        r = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": "Persister SS DB",
            "niveau": "1",
        })
        ss_id = r.get_json()["id"]
        with app.app_context():
            from Code.models.models import Softskill
            stored = Softskill.query.get(ss_id)
            assert stored is not None
            assert stored.habilete == "Persister SS DB"
            assert stored.activity_id == ids["activity_id"]

    def test_create_duplicate_habilete_updates_in_place(self, auth_client, ids, app):
        """Ajouter la même habilete deux fois → mise à jour (200), pas de doublon."""
        habilete = "Idempotence Habilete"
        _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"], "habilete": habilete, "niveau": "1"
        })
        r2 = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"], "habilete": habilete, "niveau": "3"
        })
        assert r2.status_code == 200
        with app.app_context():
            from Code.models.models import Softskill
            count = Softskill.query.filter_by(
                activity_id=ids["activity_id"], habilete=habilete
            ).count()
            assert count == 1

    def test_create_duplicate_case_insensitive(self, auth_client, ids, app):
        """Habilete en casse différente → même comportement idempotent."""
        habilete = "CaseSensitiveHabilete"
        _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"], "habilete": habilete, "niveau": "2"
        })
        r2 = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"], "habilete": habilete.lower(), "niveau": "3"
        })
        assert r2.status_code == 200

    def test_create_missing_habilete_returns_400(self, auth_client, ids):
        r = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"], "niveau": "2"
        })
        assert r.status_code == 400

    def test_create_missing_niveau_returns_400(self, auth_client, ids):
        r = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"], "habilete": "Sans niveau"
        })
        assert r.status_code == 400

    def test_create_missing_activity_id_returns_400(self, auth_client, ids):
        r = _post(auth_client, "/softskills/add", {
            "habilete": "Sans activite", "niveau": "1"
        })
        assert r.status_code == 400

    def test_create_justification_optional(self, auth_client, ids):
        """Création sans justification → 201 (champ optionnel)."""
        r = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": "Habilete Sans Justif",
            "niveau": "1",
        })
        assert r.status_code == 201

    def test_create_justification_stored_empty_when_absent(self, auth_client, ids, app):
        r = _post(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": "Habilete Justif Vide",
            "niveau": "2",
        })
        ss_id = r.get_json()["id"]
        with app.app_context():
            from Code.models.models import Softskill
            ss = Softskill.query.get(ss_id)
            assert ss.justification is None or ss.justification == ""


# ===========================================================================
# SOFTSKILLS — mise à jour
# ===========================================================================

class TestSoftskillsUpdate:

    def test_update_returns_200(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Update 200")
        ss_id = _create_softskill(app, act_id, "À mettre à jour 200", "1")
        r = _put(auth_client, f"/softskills/{act_id}/{ss_id}",
                 {"habilete": "Mis à jour 200", "niveau": "3"})
        assert r.status_code == 200

    def test_update_response_has_all_fields(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Update Fields")
        ss_id = _create_softskill(app, act_id, "À mettre à jour Champs", "1")
        r = _put(auth_client, f"/softskills/{act_id}/{ss_id}",
                 {"habilete": "Mis à jour Champs", "niveau": "2", "justification": "nouvelle justif"})
        body = r.get_json()
        for field in ("id", "activity_id", "habilete", "niveau", "justification"):
            assert field in body

    def test_update_persists_habilete_and_niveau(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Update Persist")
        ss_id = _create_softskill(app, act_id, "Avant persist SS", "1")
        _put(auth_client, f"/softskills/{act_id}/{ss_id}",
             {"habilete": "Après persist SS", "niveau": "3"})
        with app.app_context():
            from Code.models.models import Softskill
            ss = Softskill.query.get(ss_id)
            assert ss.habilete == "Après persist SS"
            assert ss.niveau == "3"

    def test_update_persists_justification(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Update Justif")
        ss_id = _create_softskill(app, act_id, "Avant justif", "1")
        _put(auth_client, f"/softskills/{act_id}/{ss_id}",
             {"habilete": "Avant justif", "niveau": "1", "justification": "justif persistée"})
        with app.app_context():
            from Code.models.models import Softskill
            ss = Softskill.query.get(ss_id)
            assert ss.justification == "justif persistée"

    def test_update_missing_habilete_returns_400(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Update No Hab")
        ss_id = _create_softskill(app, act_id, "Hab obligatoire", "2")
        r = _put(auth_client, f"/softskills/{act_id}/{ss_id}", {"niveau": "3"})
        assert r.status_code == 400

    def test_update_missing_niveau_returns_400(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Update No Niv")
        ss_id = _create_softskill(app, act_id, "Niveau obligatoire", "1")
        r = _put(auth_client, f"/softskills/{act_id}/{ss_id}",
                 {"habilete": "Niveau obligatoire"})
        assert r.status_code == 400

    def test_update_nonexistent_ss_returns_404(self, auth_client, ids):
        r = _put(auth_client, f"/softskills/{ids['activity_id']}/999999",
                 {"habilete": "Fantôme", "niveau": "1"})
        assert r.status_code == 404

    def test_update_cross_activity_isolation(self, auth_client, ids, app):
        """PUT avec un activity_id différent → 404 (mismatch détecté par la route)."""
        act_id = _create_activity(app, ids, "Activité SS Isolation Màj")
        ss_id = _create_softskill(app, act_id, "SS isolé màj", "2")
        r = _put(auth_client, f"/softskills/{ids['activity_id']}/{ss_id}",
                 {"habilete": "Tentative cross", "niveau": "3"})
        assert r.status_code == 404


# ===========================================================================
# SOFTSKILLS — suppression
# ===========================================================================

class TestSoftskillsDelete:

    def test_delete_returns_200(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Delete 200")
        ss_id = _create_softskill(app, act_id, "À supprimer 200 SS", "1")
        r = auth_client.delete(f"/softskills/{act_id}/{ss_id}")
        assert r.status_code == 200

    def test_delete_removes_from_db(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Delete DB")
        ss_id = _create_softskill(app, act_id, "À supprimer DB SS", "1")
        auth_client.delete(f"/softskills/{act_id}/{ss_id}")
        with app.app_context():
            from Code.models.models import Softskill
            assert Softskill.query.get(ss_id) is None

    def test_delete_response_has_message(self, auth_client, ids, app):
        act_id = _create_activity(app, ids, "Activité SS Delete Msg")
        ss_id = _create_softskill(app, act_id, "À supprimer msg SS", "1")
        r = auth_client.delete(f"/softskills/{act_id}/{ss_id}")
        assert "message" in r.get_json()

    def test_delete_nonexistent_returns_404(self, auth_client, ids):
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/999999")
        assert r.status_code == 404

    def test_delete_cross_activity_isolation(self, auth_client, ids, app):
        """DELETE avec mauvais activity_id → 404 (mismatch détecté)."""
        act_id = _create_activity(app, ids, "Activité SS Isolation Delete")
        ss_id = _create_softskill(app, act_id, "SS isolé delete", "2")
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        assert r.status_code == 404

    def test_delete_second_call_returns_404(self, auth_client, ids, app):
        """Supprimer deux fois le même id → la seconde fois 404."""
        act_id = _create_activity(app, ids, "Activité SS Delete 2x")
        ss_id = _create_softskill(app, act_id, "À supprimer 2x SS", "1")
        auth_client.delete(f"/softskills/{act_id}/{ss_id}")
        r = auth_client.delete(f"/softskills/{act_id}/{ss_id}")
        assert r.status_code == 404


# ===========================================================================
# SOFTSKILLS — rendu partiel
# ===========================================================================

class TestSoftskillsRender:

    def test_render_valid_activity_returns_200(self, auth_client, ids):
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert r.status_code == 200

    def test_render_returns_html(self, auth_client, ids):
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert b"<" in r.data

    def test_render_nonexistent_activity_returns_404(self, auth_client):
        r = auth_client.get("/softskills/999999/render")
        assert r.status_code == 404

    def test_render_shows_created_softskill(self, auth_client, ids, app):
        """Un softskill créé dans l'activité apparaît dans le rendu HTML."""
        act_id = _create_activity(app, ids, "Activité SS Render Visible")
        _create_softskill(app, act_id, "Habilete Visible Render", "3")
        r = auth_client.get(f"/softskills/{act_id}/render")
        assert r.status_code == 200
        assert b"Habilete Visible Render" in r.data
