# tests/test_51_softskills_aptitudes_avance.py
"""
Tests avancés : Softskills (HSC) & Aptitudes — branches non couvertes par test_06 / test_05.

Couverture ciblée :
  Softskills
  - Upsert : même habilete (insensible à la casse) → 200 + mise à jour
  - Add : habilete manquante → 400 ; niveau manquant → 400
  - Update : valeurs mises à jour dans la DB ; mauvais ss_id → 404 ;
             activity_id mismatch → 404 ; habilete manquante → 400 ; niveau manquant → 400
  - Delete : retrait réel de la DB ; activity_id mismatch → 404
  - Render : activité inexistante → 404 ; rendu HTML valide → 200

  Aptitudes
  - Add : succès → 201 + champs corrects ; description vide → 400 ;
          activity_id absent → 400 ; activity_id inexistant → 404
  - Update : succès → 200 + description modifiée ; description vide → 400 ;
             aptitude_id inexistant → 404 ; activity_id mismatch → 404
  - Delete : succès → 200 + retiré de la DB ; aptitude non trouvée → 404 ;
             activity_id mismatch → 404
  - Render : activité inexistante → 404 ; rendu HTML valide → 200

Isolation : chaque test crée et nettoie ses propres objets.
"""
import json
import pytest

pytestmark = pytest.mark.softskills


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _put_json(client, url, payload):
    return client.put(url, data=json.dumps(payload), content_type="application/json")


def _create_softskill(app, activity_id, habilete="HSC-Test-Avance", niveau="2"):
    from Code.models.models import Softskill
    from Code.extensions import db
    with app.app_context():
        ss = Softskill(habilete=habilete, niveau=niveau, activity_id=activity_id)
        db.session.add(ss)
        db.session.commit()
        return ss.id


def _create_aptitude(app, activity_id, description="Aptitude-Test-Avance"):
    from Code.models.models import Aptitude
    from Code.extensions import db
    with app.app_context():
        ap = Aptitude(description=description, activity_id=activity_id)
        db.session.add(ap)
        db.session.commit()
        return ap.id


def _softskill_exists(app, ss_id):
    from Code.models.models import Softskill
    with app.app_context():
        return Softskill.query.get(ss_id) is not None


def _aptitude_exists(app, ap_id):
    from Code.models.models import Aptitude
    with app.app_context():
        return Aptitude.query.get(ap_id) is not None


def _delete_softskill(app, ss_id):
    from Code.models.models import Softskill
    from Code.extensions import db
    with app.app_context():
        ss = Softskill.query.get(ss_id)
        if ss:
            db.session.delete(ss)
            db.session.commit()


def _delete_aptitude(app, ap_id):
    from Code.models.models import Aptitude
    from Code.extensions import db
    with app.app_context():
        ap = Aptitude.query.get(ap_id)
        if ap:
            db.session.delete(ap)
            db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# SOFTSKILLS — tests avancés
# ─────────────────────────────────────────────────────────────────────────────

class TestSoftskillsUpsert:
    """POST /softskills/add — comportement upsert (même habilete = update)."""

    def test_add_creates_new_returns_201(self, auth_client, ids, app):
        habilete = "HSC-Upsert-Nouvelle-51"
        r = _post_json(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": habilete,
            "niveau": "2",
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data["habilete"] == habilete
        assert data["niveau"] == "2"
        assert "id" in data
        _delete_softskill(app, data["id"])

    def test_add_duplicate_habilete_updates_existing(self, auth_client, ids, app):
        habilete = "HSC-Upsert-Doublon-51"
        ss_id = _create_softskill(app, ids["activity_id"], habilete=habilete, niveau="1")

        r = _post_json(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": habilete,
            "niveau": "5",
            "justification": "Modifié via upsert",
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["id"] == ss_id
        assert data["niveau"] == "5"
        _delete_softskill(app, ss_id)

    def test_add_duplicate_habilete_case_insensitive(self, auth_client, ids, app):
        habilete = "HSC-CaseInsensitive-51"
        ss_id = _create_softskill(app, ids["activity_id"], habilete=habilete, niveau="1")

        r = _post_json(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": habilete.upper(),
            "niveau": "3",
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["id"] == ss_id
        _delete_softskill(app, ss_id)

    def test_add_missing_habilete_returns_400(self, auth_client, ids):
        r = _post_json(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "niveau": "2",
        })
        assert r.status_code == 400

    def test_add_missing_niveau_returns_400(self, auth_client, ids):
        r = _post_json(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": "HSC-Sans-Niveau-51",
        })
        assert r.status_code == 400

    def test_add_returns_correct_fields(self, auth_client, ids, app):
        r = _post_json(auth_client, "/softskills/add", {
            "activity_id": ids["activity_id"],
            "habilete": "HSC-Fields-51",
            "niveau": "2",
            "justification": "Justif",
        })
        assert r.status_code == 201
        data = r.get_json()
        assert set(["id", "activity_id", "habilete", "niveau", "justification"]).issubset(data.keys())
        assert data["activity_id"] == ids["activity_id"]
        _delete_softskill(app, data["id"])


class TestSoftskillsUpdate:
    """PUT /softskills/<activity_id>/<ss_id>."""

    def test_update_persists_to_db(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-Update-Persist-51", niveau="1")
        r = _put_json(auth_client, f"/softskills/{ids['activity_id']}/{ss_id}", {
            "habilete": "HSC-Updated-51",
            "niveau": "4",
            "justification": "Nouvelle justif",
        })
        assert r.status_code == 200
        from Code.models.models import Softskill
        with app.app_context():
            ss = Softskill.query.get(ss_id)
            assert ss.habilete == "HSC-Updated-51"
            assert ss.niveau == "4"
        _delete_softskill(app, ss_id)

    def test_update_wrong_ss_id_returns_404(self, auth_client, ids):
        r = _put_json(auth_client, f"/softskills/{ids['activity_id']}/999999", {
            "habilete": "X",
            "niveau": "1",
        })
        assert r.status_code == 404

    def test_update_activity_id_mismatch_returns_404(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-Mismatch-51", niveau="1")
        r = _put_json(auth_client, f"/softskills/999999/{ss_id}", {
            "habilete": "X",
            "niveau": "1",
        })
        assert r.status_code == 404
        _delete_softskill(app, ss_id)

    def test_update_missing_habilete_returns_400(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-NoHabilete-51", niveau="1")
        r = _put_json(auth_client, f"/softskills/{ids['activity_id']}/{ss_id}", {
            "niveau": "3",
        })
        assert r.status_code == 400
        _delete_softskill(app, ss_id)

    def test_update_missing_niveau_returns_400(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-NoNiveau-51", niveau="1")
        r = _put_json(auth_client, f"/softskills/{ids['activity_id']}/{ss_id}", {
            "habilete": "X",
        })
        assert r.status_code == 400
        _delete_softskill(app, ss_id)

    def test_update_response_contains_updated_values(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-Response-51", niveau="1")
        r = _put_json(auth_client, f"/softskills/{ids['activity_id']}/{ss_id}", {
            "habilete": "HSC-Nouvelle-51",
            "niveau": "5",
            "justification": "Justif",
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["habilete"] == "HSC-Nouvelle-51"
        assert data["niveau"] == "5"
        assert data["id"] == ss_id
        _delete_softskill(app, ss_id)


class TestSoftskillsDelete:
    """DELETE /softskills/<activity_id>/<ss_id>."""

    def test_delete_removes_from_db(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-Delete-DB-51", niveau="1")
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        assert r.status_code == 200
        assert not _softskill_exists(app, ss_id)

    def test_delete_activity_id_mismatch_returns_404(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-Del-Mismatch-51", niveau="1")
        r = auth_client.delete(f"/softskills/999999/{ss_id}")
        assert r.status_code == 404
        assert _softskill_exists(app, ss_id)
        _delete_softskill(app, ss_id)

    def test_delete_nonexistent_returns_404(self, auth_client, ids):
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/999999")
        assert r.status_code == 404

    def test_delete_response_has_message(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="HSC-Del-Msg-51", niveau="1")
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert "message" in data


class TestSoftskillsRender:
    """GET /softskills/<activity_id>/render."""

    def test_render_valid_activity_returns_200(self, auth_client, ids):
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert r.status_code == 200

    def test_render_invalid_activity_returns_404(self, auth_client):
        r = auth_client.get("/softskills/999999/render")
        assert r.status_code == 404

    def test_render_returns_html(self, auth_client, ids):
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"<" in r.data


# ─────────────────────────────────────────────────────────────────────────────
# APTITUDES — tests avancés
# ─────────────────────────────────────────────────────────────────────────────

class TestAptitudesAdd:
    """POST /aptitudes/add."""

    def test_add_valid_returns_201(self, auth_client, ids, app):
        r = _post_json(auth_client, "/aptitudes/add", {
            "description": "Aptitude-Add-Valid-51",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = r.get_json()
        assert data["description"] == "Aptitude-Add-Valid-51"
        assert "id" in data
        _delete_aptitude(app, data["id"])

    def test_add_returns_correct_fields(self, auth_client, ids, app):
        r = _post_json(auth_client, "/aptitudes/add", {
            "description": "Aptitude-Fields-51",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        data = r.get_json()
        assert "id" in data and "description" in data
        _delete_aptitude(app, data["id"])

    def test_add_missing_description_returns_400(self, auth_client, ids):
        r = _post_json(auth_client, "/aptitudes/add", {
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 400

    def test_add_empty_description_returns_400(self, auth_client, ids):
        r = _post_json(auth_client, "/aptitudes/add", {
            "description": "   ",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 400

    def test_add_missing_activity_id_returns_400(self, auth_client):
        r = _post_json(auth_client, "/aptitudes/add", {
            "description": "Aptitude-No-Activity-51",
        })
        assert r.status_code == 400

    def test_add_invalid_activity_id_returns_404(self, auth_client):
        r = _post_json(auth_client, "/aptitudes/add", {
            "description": "Aptitude-Bad-Activity-51",
            "activity_id": 999999,
        })
        assert r.status_code == 404

    def test_add_persists_in_db(self, auth_client, ids, app):
        r = _post_json(auth_client, "/aptitudes/add", {
            "description": "Aptitude-Persist-51",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code == 201
        ap_id = r.get_json()["id"]
        assert _aptitude_exists(app, ap_id)
        _delete_aptitude(app, ap_id)


class TestAptitudesUpdate:
    """PUT /aptitudes/<activity_id>/<aptitudes_id>."""

    def test_update_valid_returns_200(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Update-51")
        r = _put_json(auth_client, f"/aptitudes/{ids['activity_id']}/{ap_id}", {
            "description": "Aptitude-Updated-51",
        })
        assert r.status_code == 200
        _delete_aptitude(app, ap_id)

    def test_update_persists_to_db(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Persist-Update-51")
        _put_json(auth_client, f"/aptitudes/{ids['activity_id']}/{ap_id}", {
            "description": "Aptitude-Modifiee-51",
        })
        from Code.models.models import Aptitude
        with app.app_context():
            ap = Aptitude.query.get(ap_id)
            assert ap.description == "Aptitude-Modifiee-51"
        _delete_aptitude(app, ap_id)

    def test_update_returns_updated_description(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Resp-51")
        r = _put_json(auth_client, f"/aptitudes/{ids['activity_id']}/{ap_id}", {
            "description": "Aptitude-Nouvelle-Desc-51",
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["description"] == "Aptitude-Nouvelle-Desc-51"
        _delete_aptitude(app, ap_id)

    def test_update_empty_description_returns_400(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-EmptyDesc-51")
        r = _put_json(auth_client, f"/aptitudes/{ids['activity_id']}/{ap_id}", {
            "description": "  ",
        })
        assert r.status_code == 400
        _delete_aptitude(app, ap_id)

    def test_update_nonexistent_aptitude_returns_404(self, auth_client, ids):
        r = _put_json(auth_client, f"/aptitudes/{ids['activity_id']}/999999", {
            "description": "X",
        })
        assert r.status_code == 404

    def test_update_activity_id_mismatch_returns_404(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Mismatch-51")
        r = _put_json(auth_client, f"/aptitudes/999999/{ap_id}", {
            "description": "X",
        })
        assert r.status_code == 404
        _delete_aptitude(app, ap_id)


class TestAptitudesDelete:
    """DELETE /aptitudes/<activity_id>/<aptitudes_id>."""

    def test_delete_valid_returns_200(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Del-51")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{ap_id}")
        assert r.status_code == 200

    def test_delete_removes_from_db(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Del-DB-51")
        auth_client.delete(f"/aptitudes/{ids['activity_id']}/{ap_id}")
        assert not _aptitude_exists(app, ap_id)

    def test_delete_response_has_message(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Del-Msg-51")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{ap_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert "message" in data

    def test_delete_nonexistent_returns_404(self, auth_client, ids):
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/999999")
        assert r.status_code == 404

    def test_delete_activity_id_mismatch_returns_404(self, auth_client, ids, app):
        ap_id = _create_aptitude(app, ids["activity_id"], "Aptitude-Mismatch-Del-51")
        r = auth_client.delete(f"/aptitudes/999999/{ap_id}")
        assert r.status_code == 404
        assert _aptitude_exists(app, ap_id)
        _delete_aptitude(app, ap_id)


class TestAptitudesRender:
    """GET /aptitudes/<activity_id>/render."""

    def test_render_valid_activity_returns_200(self, auth_client, ids):
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert r.status_code == 200

    def test_render_invalid_activity_returns_404(self, auth_client):
        r = auth_client.get("/aptitudes/999999/render")
        assert r.status_code == 404

    def test_render_returns_html(self, auth_client, ids):
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"<" in r.data


# ─────────────────────────────────────────────────────────────────────────────
# ASSIGN_MANAGER — chemin succès manquant dans test_12
# ─────────────────────────────────────────────────────────────────────────────

class TestAssignManagerSuccess:
    """POST /gestion_rh/assign_manager — chemin succès + validations."""

    def test_assign_manager_success(self, auth_client, ids, app):
        """Chemin nominal : manager_id + assignments valides → 200 + success."""
        from Code.models.models import User
        with app.app_context():
            user = User.query.get(ids["user_id"])
            old_manager = user.manager_id

        r = auth_client.post(
            "/gestion_rh/assign_manager",
            data=json.dumps({
                "manager_id": ids["user_id"],
                "assignments": [{"user_id": ids["user_id"], "role_id": None}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("success") is True

        with app.app_context():
            from Code.models.models import User
            from Code.extensions import db
            user = User.query.get(ids["user_id"])
            user.manager_id = old_manager
            db.session.commit()

    def test_assign_manager_missing_manager_id_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/gestion_rh/assign_manager",
            data=json.dumps({"assignments": [{"user_id": ids["user_id"]}]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_assign_manager_empty_assignments_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/gestion_rh/assign_manager",
            data=json.dumps({"manager_id": ids["user_id"], "assignments": []}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_assign_manager_unknown_user_in_assignments_ignored(self, auth_client, ids):
        """Les user_id inconnus sont silencieusement ignorés (pas de crash)."""
        r = auth_client.post(
            "/gestion_rh/assign_manager",
            data=json.dumps({
                "manager_id": ids["user_id"],
                "assignments": [{"user_id": 999999, "role_id": None}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
