# tests/test_54_technical_domains.py
"""
Page : Domaines de technicité (/domains)
CDC 4 (V1.1) — Une même activité peut être exercée dans des contextes techniques différents
(Plastic/Metal, Français/Maths…) sans dupliquer l'activité. Le niveau technique est un AXE
SÉPARÉ du niveau de maîtrise de l'activité.
Couvre : /domains/scale, /domains/list, /domains/create, /domains/delete, /domains/activity/<id>,
/domains/activity/<id>/link, /domains/required, /domains/user_level.
"""
import pytest
import json
from Code.extensions import db
from Code.models.models import (
    Entity, Activities, Role, User, TechnicalDomain, ActivityTechnicalDomain,
    RoleActivityDomainRequirement, UserDomainLevel,
)

pytestmark = pytest.mark.technical_domains


@pytest.fixture()
def scene(app, ids):
    """Entité dédiée + activité + rôle, pour tester les domaines de technicité isolément."""
    with app.app_context():
        ent = Entity(name="TechDomainsECo")
        db.session.add(ent)
        db.session.flush()
        act = Activities(entity_id=ent.id, name="Usiner pièce plastique", shape_id="td_a1")
        role = Role(entity_id=ent.id, name="Opérateur technique")
        db.session.add_all([act, role])
        db.session.commit()
        result = {"entity_id": ent.id, "activity_id": act.id, "role_id": role.id, "user_id": ids["user_id"]}
    yield result
    with app.app_context():
        RoleActivityDomainRequirement.query.filter_by(activity_id=result["activity_id"]).delete()
        ActivityTechnicalDomain.query.filter_by(activity_id=result["activity_id"]).delete()
        UserDomainLevel.query.filter_by(user_id=result["user_id"]).delete()
        Role.query.filter_by(id=result["role_id"]).delete()
        Activities.query.filter_by(id=result["activity_id"]).delete()
        TechnicalDomain.query.filter_by(entity_id=result["entity_id"]).delete()
        Entity.query.filter_by(id=result["entity_id"]).delete()
        db.session.commit()


def _sess(client, entity_id, lang="fr"):
    with client.session_transaction() as s:
        s["active_entity_id"] = entity_id
        s["lang"] = lang


# ===========================================================================
# 1. GET /domains/scale
# ===========================================================================

class TestScale:

    def test_scale_returns_five_levels(self, client):
        r = client.get("/domains/scale")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert set(body["scale"].keys()) == {"0", "1", "2", "3", "4"}
        assert body["scale"]["4"] == "Référence technique"


# ===========================================================================
# 2. POST /domains/create + GET /domains/list + POST /domains/delete
# ===========================================================================

class TestCreateListDeleteDomain:

    def test_create_domain_returns_id(self, client, scene):
        _sess(client, scene["entity_id"])
        r = client.post("/domains/create", data=json.dumps(
            {"name_fr": "Plastique", "name_en": "Plastic"}), content_type="application/json")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["ok"] is True
        assert "id" in body

    def test_create_domain_empty_name_returns_400(self, client, scene):
        _sess(client, scene["entity_id"])
        r = client.post("/domains/create", data=json.dumps({"name_fr": "   "}), content_type="application/json")
        assert r.status_code == 400

    def test_list_domains_scoped_to_active_entity(self, client, scene):
        _sess(client, scene["entity_id"])
        client.post("/domains/create", data=json.dumps({"name_fr": "Métal"}), content_type="application/json")
        r = client.get("/domains/list")
        assert r.status_code == 200
        names = {d["name_fr"] for d in json.loads(r.data)["domains"]}
        assert "Métal" in names

    def test_delete_domain_hides_from_list_but_keeps_row(self, app, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "À supprimer"}), content_type="application/json").data)["id"]
        r = client.post(f"/domains/delete/{did}")
        assert r.status_code == 200
        names = {d["name_fr"] for d in json.loads(client.get("/domains/list").data)["domains"]}
        assert "À supprimer" not in names
        with app.app_context():
            row = TechnicalDomain.query.get(did)
            assert row is not None
            assert row.active is False

    def test_delete_unknown_domain_is_noop_ok(self, client):
        r = client.post("/domains/delete/999999")
        assert r.status_code == 200
        assert json.loads(r.data)["ok"] is True


# ===========================================================================
# 3. Liaison activité ↔ domaine — /domains/activity/<id> et /activity/<id>/link
# ===========================================================================

class TestActivityDomainLink:

    def test_activity_has_no_domains_initially(self, client, scene):
        r = client.get(f"/domains/activity/{scene['activity_id']}")
        assert r.status_code == 200
        assert json.loads(r.data)["domains"] == []

    def test_link_domain_to_activity(self, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "Plastique"}), content_type="application/json").data)["id"]
        r = client.post(f"/domains/activity/{scene['activity_id']}/link",
                        data=json.dumps({"domain_id": did}), content_type="application/json")
        assert r.status_code == 200
        domains = json.loads(client.get(f"/domains/activity/{scene['activity_id']}").data)["domains"]
        assert [d["domain_id"] for d in domains] == [did]

    def test_link_domain_twice_not_duplicated(self, app, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "Métal"}), content_type="application/json").data)["id"]
        client.post(f"/domains/activity/{scene['activity_id']}/link",
                    data=json.dumps({"domain_id": did}), content_type="application/json")
        client.post(f"/domains/activity/{scene['activity_id']}/link",
                    data=json.dumps({"domain_id": did}), content_type="application/json")
        with app.app_context():
            n = ActivityTechnicalDomain.query.filter_by(activity_id=scene["activity_id"], domain_id=did).count()
            assert n == 1

    def test_unlink_domain_removes_association(self, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "Bois"}), content_type="application/json").data)["id"]
        client.post(f"/domains/activity/{scene['activity_id']}/link",
                    data=json.dumps({"domain_id": did}), content_type="application/json")
        client.post(f"/domains/activity/{scene['activity_id']}/link",
                    data=json.dumps({"domain_id": did, "unlink": True}), content_type="application/json")
        domains = json.loads(client.get(f"/domains/activity/{scene['activity_id']}").data)["domains"]
        assert domains == []

    def test_link_missing_domain_id_returns_400(self, client, scene):
        r = client.post(f"/domains/activity/{scene['activity_id']}/link",
                        data=json.dumps({}), content_type="application/json")
        assert r.status_code == 400


# ===========================================================================
# 4. Niveaux requis / démontrés — /domains/required, /domains/user_level
# ===========================================================================

class TestRequiredAndUserLevel:

    def test_set_required_level_then_read_via_activity(self, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "Plastique"}), content_type="application/json").data)["id"]
        client.post(f"/domains/activity/{scene['activity_id']}/link",
                    data=json.dumps({"domain_id": did}), content_type="application/json")
        r = client.post("/domains/required", data=json.dumps(
            {"role_id": scene["role_id"], "activity_id": scene["activity_id"],
             "domain_id": did, "required_level": 3}), content_type="application/json")
        assert r.status_code == 200
        domains = json.loads(client.get(
            f"/domains/activity/{scene['activity_id']}?role_id={scene['role_id']}").data)["domains"]
        assert domains[0]["required_level"] == 3
        assert domains[0]["required_label"] == "Maîtrise complexe"

    def test_set_required_invalid_level_returns_400(self, client, scene):
        r = client.post("/domains/required", data=json.dumps(
            {"role_id": scene["role_id"], "activity_id": scene["activity_id"],
             "domain_id": 1, "required_level": 99}), content_type="application/json")
        assert r.status_code == 400

    def test_set_required_missing_fields_returns_400(self, client):
        r = client.post("/domains/required", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 400

    def test_set_user_level_then_gap_computed(self, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "Plastique"}), content_type="application/json").data)["id"]
        client.post(f"/domains/activity/{scene['activity_id']}/link",
                    data=json.dumps({"domain_id": did}), content_type="application/json")
        client.post("/domains/required", data=json.dumps(
            {"role_id": scene["role_id"], "activity_id": scene["activity_id"],
             "domain_id": did, "required_level": 3}), content_type="application/json")
        client.post("/domains/user_level", data=json.dumps(
            {"user_id": scene["user_id"], "domain_id": did, "demonstrated_level": 1}),
            content_type="application/json")
        domains = json.loads(client.get(
            f"/domains/activity/{scene['activity_id']}?role_id={scene['role_id']}&user_id={scene['user_id']}"
        ).data)["domains"]
        assert domains[0]["demonstrated_level"] == 1
        assert domains[0]["gap"] == 1 - 3

    def test_set_user_level_invalid_level_returns_400(self, client, scene):
        r = client.post("/domains/user_level", data=json.dumps(
            {"user_id": scene["user_id"], "domain_id": 1, "demonstrated_level": 42}),
            content_type="application/json")
        assert r.status_code == 400

    def test_set_user_level_missing_fields_returns_400(self, client):
        r = client.post("/domains/user_level", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 400


# ===========================================================================
# 5. domain_status() — helper utilisé par le tableau de bord maîtrise (CDC 6.3)
# ===========================================================================

class TestDomainStatusHelper:

    def test_status_none_when_no_requirement(self, app, scene):
        from Code.routes.technical_domains import domain_status
        with app.app_context():
            assert domain_status(scene["user_id"], scene["role_id"], scene["activity_id"]) == "none"

    def test_status_gap_when_not_evaluated(self, app, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "Plastique"}), content_type="application/json").data)["id"]
        client.post("/domains/required", data=json.dumps(
            {"role_id": scene["role_id"], "activity_id": scene["activity_id"],
             "domain_id": did, "required_level": 2}), content_type="application/json")
        from Code.routes.technical_domains import domain_status
        with app.app_context():
            assert domain_status(scene["user_id"], scene["role_id"], scene["activity_id"]) == "gap"

    def test_status_ok_when_level_met(self, app, client, scene):
        _sess(client, scene["entity_id"])
        did = json.loads(client.post("/domains/create", data=json.dumps(
            {"name_fr": "Plastique"}), content_type="application/json").data)["id"]
        client.post("/domains/required", data=json.dumps(
            {"role_id": scene["role_id"], "activity_id": scene["activity_id"],
             "domain_id": did, "required_level": 2}), content_type="application/json")
        client.post("/domains/user_level", data=json.dumps(
            {"user_id": scene["user_id"], "domain_id": did, "demonstrated_level": 2}),
            content_type="application/json")
        from Code.routes.technical_domains import domain_status
        with app.app_context():
            assert domain_status(scene["user_id"], scene["role_id"], scene["activity_id"]) == "ok"
