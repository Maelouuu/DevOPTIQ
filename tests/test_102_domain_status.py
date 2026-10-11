# tests/test_102_domain_status.py
"""
Page : Domaines de technicité — état du tableau (domain_status / domain_gap)
Couverture :
  - domain_status : none / gap (non évalué, sous le niveau) / ok
  - domain_gap : compat booléenne
  - GET /domains/activity/<id> : lien orphelin ignoré, rôle/utilisateur absents
"""
import pytest

pytestmark = pytest.mark.technical_domains


@pytest.fixture
def setup(app, ids):
    """Domaine + rôle dédiés, nettoyés après le test."""
    from Code.models.models import (TechnicalDomain, Role, ActivityTechnicalDomain,
                                    RoleActivityDomainRequirement, UserDomainLevel)
    from Code.extensions import db
    with app.app_context():
        d = TechnicalDomain(entity_id=ids["entity_id"], name_fr="Domaine Statut 102", active=True)
        r = Role(entity_id=ids["entity_id"], name="Rôle Statut 102")
        db.session.add_all([d, r])
        db.session.commit()
        did, rid = d.id, r.id
    yield {"domain_id": did, "role_id": rid, **ids}
    with app.app_context():
        ActivityTechnicalDomain.query.filter_by(domain_id=did).delete()
        RoleActivityDomainRequirement.query.filter_by(domain_id=did).delete()
        UserDomainLevel.query.filter_by(domain_id=did).delete()
        ActivityTechnicalDomain.query.filter_by(domain_id=999999).delete()
        TechnicalDomain.query.filter_by(id=did).delete()
        Role.query.filter_by(id=rid).delete()
        db.session.commit()


def _require(app, s, level):
    from Code.models.models import RoleActivityDomainRequirement
    from Code.extensions import db
    with app.app_context():
        db.session.add(RoleActivityDomainRequirement(
            role_id=s["role_id"], activity_id=s["activity_id"],
            domain_id=s["domain_id"], required_level=level))
        db.session.commit()


def _demonstrate(app, s, level):
    from Code.models.models import UserDomainLevel
    from Code.extensions import db
    with app.app_context():
        db.session.add(UserDomainLevel(user_id=s["user_id"], domain_id=s["domain_id"],
                                       demonstrated_level=level))
        db.session.commit()


def _status(app, s):
    from Code.routes.technical_domains import domain_status
    with app.app_context():
        return domain_status(s["user_id"], s["role_id"], s["activity_id"])


class TestDomainStatus:

    def test_status_none_without_requirement(self, app, setup):
        assert _status(app, setup) == "none"

    def test_status_none_when_required_level_is_null(self, app, setup):
        _require(app, setup, None)
        assert _status(app, setup) == "none"

    def test_status_gap_when_not_evaluated(self, app, setup):
        _require(app, setup, 2)
        assert _status(app, setup) == "gap"

    def test_status_gap_when_demonstrated_below_required(self, app, setup):
        _require(app, setup, 3)
        _demonstrate(app, setup, 1)
        assert _status(app, setup) == "gap"

    def test_status_ok_when_demonstrated_equals_required(self, app, setup):
        _require(app, setup, 2)
        _demonstrate(app, setup, 2)
        assert _status(app, setup) == "ok"

    def test_status_ok_when_demonstrated_above_required(self, app, setup):
        _require(app, setup, 1)
        _demonstrate(app, setup, 4)
        assert _status(app, setup) == "ok"

    def test_gap_helper_true_only_on_gap(self, app, setup):
        from Code.routes.technical_domains import domain_gap
        _require(app, setup, 3)
        with app.app_context():
            assert domain_gap(setup["user_id"], setup["role_id"], setup["activity_id"]) is True
        _demonstrate(app, setup, 3)
        with app.app_context():
            assert domain_gap(setup["user_id"], setup["role_id"], setup["activity_id"]) is False


class TestActivityDomainsEdgeCases:

    def test_orphan_link_is_ignored(self, auth_client, app, setup):
        from Code.models.models import ActivityTechnicalDomain
        from Code.extensions import db
        with app.app_context():
            db.session.add(ActivityTechnicalDomain(activity_id=setup["activity_id"], domain_id=999999))
            db.session.commit()
        r = auth_client.get(f"/domains/activity/{setup['activity_id']}")
        assert r.status_code == 200
        assert 999999 not in [d["domain_id"] for d in r.get_json()["domains"]]

    def test_levels_null_without_role_or_user(self, auth_client, app, setup):
        from Code.models.models import ActivityTechnicalDomain
        from Code.extensions import db
        with app.app_context():
            db.session.add(ActivityTechnicalDomain(activity_id=setup["activity_id"], domain_id=setup["domain_id"]))
            db.session.commit()
        r = auth_client.get(f"/domains/activity/{setup['activity_id']}")
        entry = next(d for d in r.get_json()["domains"] if d["domain_id"] == setup["domain_id"])
        assert entry["required_level"] is None
        assert entry["demonstrated_level"] is None
        assert entry["gap"] is None

    def test_gap_computed_with_role_and_user(self, auth_client, app, setup):
        from Code.models.models import ActivityTechnicalDomain
        from Code.extensions import db
        with app.app_context():
            db.session.add(ActivityTechnicalDomain(activity_id=setup["activity_id"], domain_id=setup["domain_id"]))
            db.session.commit()
        _require(app, setup, 3)
        _demonstrate(app, setup, 1)
        r = auth_client.get(f"/domains/activity/{setup['activity_id']}"
                            f"?role_id={setup['role_id']}&user_id={setup['user_id']}")
        entry = next(d for d in r.get_json()["domains"] if d["domain_id"] == setup["domain_id"])
        assert entry["gap"] == -2
