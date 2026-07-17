# tests/test_55_technical_domains.py
"""
Page : Domaines de technicité (/domains — CDC 4)
Couverture :
  - GET  /domains/scale                         → échelle technique
  - GET  /domains/list                           → domaines actifs de l'entité
  - POST /domains/create                          → création d'un domaine
  - POST /domains/delete/<id>                     → désactivation (soft delete)
  - GET  /domains/activity/<id>                   → domaines liés à une activité
  - POST /domains/activity/<id>/link              → lier/délier un domaine à une activité
  - POST /domains/required                         → niveau requis Rôle × Activité × Domaine
  - POST /domains/user_level                       → niveau démontré d'un individu
"""
import json
import pytest

pytestmark = pytest.mark.technical_domains


def _create_domain(app, entity_id, name_fr="Domaine Test 55"):
    with app.app_context():
        from Code.models.models import TechnicalDomain
        from Code.extensions import db
        d = TechnicalDomain(entity_id=entity_id, name_fr=name_fr, active=True)
        db.session.add(d)
        db.session.commit()
        return d.id


def _create_role(app, entity_id, name="Rôle Domaine Test 55"):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        r = Role(entity_id=entity_id, name=name)
        db.session.add(r)
        db.session.commit()
        return r.id


def _cleanup_domain(app, domain_id):
    with app.app_context():
        from Code.models.models import (TechnicalDomain, ActivityTechnicalDomain,
                                        RoleActivityDomainRequirement, UserDomainLevel)
        from Code.extensions import db
        ActivityTechnicalDomain.query.filter_by(domain_id=domain_id).delete()
        RoleActivityDomainRequirement.query.filter_by(domain_id=domain_id).delete()
        UserDomainLevel.query.filter_by(domain_id=domain_id).delete()
        d = TechnicalDomain.query.get(domain_id)
        if d:
            db.session.delete(d)
        db.session.commit()


def _cleanup_role(app, role_id):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
            db.session.commit()


class TestScale:

    def test_scale_returns_five_levels(self, auth_client):
        r = auth_client.get("/domains/scale")
        assert r.status_code == 200
        data = r.get_json()
        assert set(data["scale"].keys()) == {"0", "1", "2", "3", "4"}
        assert data["scale"]["4"] == "Référence technique"


class TestListDomains:

    def test_list_includes_created_domain(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        try:
            r = auth_client.get("/domains/list")
            assert r.status_code == 200
            data = r.get_json()
            names = [d["name"] for d in data["domains"]]
            assert "Domaine Test 55" in names
        finally:
            _cleanup_domain(app, did)

    def test_list_excludes_inactive_domain(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"], name_fr="Domaine Inactif Test 55")
        try:
            auth_client.post(f"/domains/delete/{did}")
            r = auth_client.get("/domains/list")
            ids_listed = [d["id"] for d in r.get_json()["domains"]]
            assert did not in ids_listed
        finally:
            _cleanup_domain(app, did)


class TestCreateDomain:

    def test_create_valid_domain(self, auth_client, app):
        r = auth_client.post(
            "/domains/create",
            data=json.dumps({"name_fr": "Plastique Test 55", "name_en": "Plastic", "description": "Matière plastique"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert isinstance(data["id"], int)
        _cleanup_domain(app, data["id"])

    def test_create_empty_name_returns_400(self, auth_client):
        r = auth_client.post(
            "/domains/create",
            data=json.dumps({"name_fr": "   "}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "empty_name"


class TestDeleteDomain:

    def test_delete_deactivates_domain(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"], name_fr="Domaine à supprimer 55")
        try:
            r = auth_client.post(f"/domains/delete/{did}")
            assert r.status_code == 200
            assert r.get_json()["ok"] is True
            with app.app_context():
                from Code.models.models import TechnicalDomain
                d = TechnicalDomain.query.get(did)
                assert d.active is False
        finally:
            _cleanup_domain(app, did)

    def test_delete_unknown_domain_still_ok(self, auth_client):
        r = auth_client.post("/domains/delete/999999")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


class TestActivityDomainLink:

    def test_link_then_appears_in_activity_domains(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        try:
            r = auth_client.post(
                f"/domains/activity/{ids['activity_id']}/link",
                data=json.dumps({"domain_id": did}),
                content_type="application/json",
            )
            assert r.status_code == 200

            r2 = auth_client.get(f"/domains/activity/{ids['activity_id']}")
            data = r2.get_json()
            domain_ids = [d["domain_id"] for d in data["domains"]]
            assert did in domain_ids
        finally:
            auth_client.post(
                f"/domains/activity/{ids['activity_id']}/link",
                data=json.dumps({"domain_id": did, "unlink": True}),
                content_type="application/json",
            )
            _cleanup_domain(app, did)

    def test_unlink_removes_from_activity_domains(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        try:
            auth_client.post(
                f"/domains/activity/{ids['activity_id']}/link",
                data=json.dumps({"domain_id": did}),
                content_type="application/json",
            )
            auth_client.post(
                f"/domains/activity/{ids['activity_id']}/link",
                data=json.dumps({"domain_id": did, "unlink": True}),
                content_type="application/json",
            )
            r = auth_client.get(f"/domains/activity/{ids['activity_id']}")
            domain_ids = [d["domain_id"] for d in r.get_json()["domains"]]
            assert did not in domain_ids
        finally:
            _cleanup_domain(app, did)

    def test_link_missing_domain_id_returns_400(self, auth_client, ids):
        r = auth_client.post(
            f"/domains/activity/{ids['activity_id']}/link",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_activity_domains_includes_required_and_demonstrated(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        rid = _create_role(app, ids["entity_id"])
        try:
            auth_client.post(
                f"/domains/activity/{ids['activity_id']}/link",
                data=json.dumps({"domain_id": did}),
                content_type="application/json",
            )
            auth_client.post(
                "/domains/required",
                data=json.dumps({"role_id": rid, "activity_id": ids["activity_id"], "domain_id": did, "required_level": 3}),
                content_type="application/json",
            )
            auth_client.post(
                "/domains/user_level",
                data=json.dumps({"user_id": ids["user_id"], "domain_id": did, "demonstrated_level": 2}),
                content_type="application/json",
            )
            r = auth_client.get(
                f"/domains/activity/{ids['activity_id']}",
                query_string={"role_id": rid, "user_id": ids["user_id"]},
            )
            data = r.get_json()
            entry = next(d for d in data["domains"] if d["domain_id"] == did)
            assert entry["required_level"] == 3
            assert entry["demonstrated_level"] == 2
            assert entry["gap"] == -1
        finally:
            auth_client.post(
                f"/domains/activity/{ids['activity_id']}/link",
                data=json.dumps({"domain_id": did, "unlink": True}),
                content_type="application/json",
            )
            _cleanup_role(app, rid)
            _cleanup_domain(app, did)


class TestRequiredLevel:

    def test_set_required_valid(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        rid = _create_role(app, ids["entity_id"])
        try:
            r = auth_client.post(
                "/domains/required",
                data=json.dumps({"role_id": rid, "activity_id": ids["activity_id"], "domain_id": did, "required_level": 2}),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["ok"] is True
        finally:
            _cleanup_role(app, rid)
            _cleanup_domain(app, did)

    def test_set_required_missing_fields_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/domains/required",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_set_required_invalid_level_returns_400(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        rid = _create_role(app, ids["entity_id"])
        try:
            r = auth_client.post(
                "/domains/required",
                data=json.dumps({"role_id": rid, "activity_id": ids["activity_id"], "domain_id": did, "required_level": 99}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup_role(app, rid)
            _cleanup_domain(app, did)


class TestUserLevel:

    def test_set_user_level_valid(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        try:
            r = auth_client.post(
                "/domains/user_level",
                data=json.dumps({"user_id": ids["user_id"], "domain_id": did, "demonstrated_level": 4, "evidence": "Certifié"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            with app.app_context():
                from Code.models.models import UserDomainLevel
                row = UserDomainLevel.query.filter_by(user_id=ids["user_id"], domain_id=did).first()
                assert row.demonstrated_level == 4
                assert row.evidence == "Certifié"
        finally:
            _cleanup_domain(app, did)

    def test_set_user_level_missing_fields_returns_400(self, auth_client):
        r = auth_client.post(
            "/domains/user_level",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_set_user_level_invalid_level_returns_400(self, auth_client, app, ids):
        did = _create_domain(app, ids["entity_id"])
        try:
            r = auth_client.post(
                "/domains/user_level",
                data=json.dumps({"user_id": ids["user_id"], "domain_id": did, "demonstrated_level": 42}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup_domain(app, did)
