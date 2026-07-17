# tests/test_53_cadence.py
"""
Page : Cadences & Cohérence des rythmes (/cadence — CDC 5)
Couverture :
  - GET  /cadence/codes                       → liste des codes de cadence
  - POST /cadence/activity/<id>                → fixe la cadence d'une activité
  - POST /cadence/data/<id>                    → fixe la cadence de mise à jour d'une donnée
  - GET  /cadence/consistency                   → analyse de cohérence (lecture seule)
"""
import json
import pytest

pytestmark = pytest.mark.cadence


def _create_activity(app, entity_id, name="Activité Cadence Test"):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="")
        db.session.add(a)
        db.session.commit()
        return a.id


def _create_data(app, entity_id, name="Donnée Cadence Test", type_="nourrissante"):
    with app.app_context():
        from Code.models.models import Data
        from Code.extensions import db
        d = Data(entity_id=entity_id, name=name, type=type_)
        db.session.add(d)
        db.session.commit()
        return d.id


def _cleanup_activity(app, activity_id):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities.query.get(activity_id)
        if a:
            db.session.delete(a)
            db.session.commit()


def _cleanup_data(app, data_id):
    with app.app_context():
        from Code.models.models import Data
        from Code.extensions import db
        d = Data.query.get(data_id)
        if d:
            db.session.delete(d)
            db.session.commit()


class TestCadenceCodes:

    def test_codes_returns_list(self, auth_client):
        r = auth_client.get("/cadence/codes")
        assert r.status_code == 200
        data = r.get_json()
        assert "cadences" in data
        codes = [c["code"] for c in data["cadences"]]
        assert "DAILY" in codes
        assert "WEEKLY" in codes

    def test_codes_each_entry_has_label_and_badge(self, auth_client):
        r = auth_client.get("/cadence/codes")
        data = r.get_json()
        for c in data["cadences"]:
            assert "label" in c
            assert "badge" in c

    def test_codes_accessible_without_auth(self, client):
        r = client.get("/cadence/codes")
        assert r.status_code == 200


class TestSetActivityCadence:

    def test_set_valid_cadence(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.post(
                f"/cadence/activity/{aid}",
                data=json.dumps({"cadence_code": "WEEKLY", "cadence_details": "Tous les lundis"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["ok"] is True
            with app.app_context():
                from Code.models.models import Activities
                a = Activities.query.get(aid)
                assert a.cadence_code == "WEEKLY"
                assert a.cadence_details == "Tous les lundis"
        finally:
            _cleanup_activity(app, aid)

    def test_set_invalid_cadence_code_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.post(
                f"/cadence/activity/{aid}",
                data=json.dumps({"cadence_code": "NOT_A_CODE"}),
                content_type="application/json",
            )
            assert r.status_code == 400
            assert r.get_json()["error"] == "invalid_code"
        finally:
            _cleanup_activity(app, aid)

    def test_set_cadence_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post(
            "/cadence/activity/999999",
            data=json.dumps({"cadence_code": "DAILY"}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert r.get_json()["error"] == "not_found"

    def test_set_cadence_null_code_clears_it(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            auth_client.post(
                f"/cadence/activity/{aid}",
                data=json.dumps({"cadence_code": "DAILY"}),
                content_type="application/json",
            )
            r = auth_client.post(
                f"/cadence/activity/{aid}",
                data=json.dumps({"cadence_code": None}),
                content_type="application/json",
            )
            assert r.status_code == 200
            with app.app_context():
                from Code.models.models import Activities
                a = Activities.query.get(aid)
                assert a.cadence_code is None
        finally:
            _cleanup_activity(app, aid)


class TestSetDataCadence:

    def test_set_valid_cadence(self, auth_client, app, ids):
        did = _create_data(app, ids["entity_id"])
        try:
            r = auth_client.post(
                f"/cadence/data/{did}",
                data=json.dumps({"update_cadence_code": "MONTHLY", "max_age_hours": 720}),
                content_type="application/json",
            )
            assert r.status_code == 200
            with app.app_context():
                from Code.models.models import Data
                d = Data.query.get(did)
                assert d.update_cadence_code == "MONTHLY"
                assert d.max_age_hours == 720
        finally:
            _cleanup_data(app, did)

    def test_set_invalid_cadence_code_returns_400(self, auth_client, app, ids):
        did = _create_data(app, ids["entity_id"])
        try:
            r = auth_client.post(
                f"/cadence/data/{did}",
                data=json.dumps({"update_cadence_code": "BOGUS"}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup_data(app, did)

    def test_set_cadence_unknown_data_returns_404(self, auth_client):
        r = auth_client.post(
            "/cadence/data/999999",
            data=json.dumps({"update_cadence_code": "DAILY"}),
            content_type="application/json",
        )
        assert r.status_code == 404


class TestConsistency:

    def test_consistency_returns_warnings_list(self, auth_client):
        r = auth_client.get("/cadence/consistency")
        assert r.status_code == 200
        data = r.get_json()
        assert "warnings" in data
        assert "count" in data
        assert data["count"] == len(data["warnings"])

    def test_consistency_detects_slower_data_than_activity(self, auth_client, app, ids):
        """Une donnée mise à jour moins souvent que l'activité aval qui la consomme
        doit produire un point de vigilance (CDC 5.5-5.6)."""
        aid = _create_activity(app, ids["entity_id"], name="Activité Rythme Rapide")
        did = _create_data(app, ids["entity_id"], name="Donnée Rythme Lent")
        with app.app_context():
            from Code.models.models import Link
            from Code.extensions import db
            link = Link(entity_id=ids["entity_id"], source_data_id=did, target_activity_id=aid, type="nourrissante")
            db.session.add(link)
            db.session.commit()
            link_id = link.id
        try:
            auth_client.post(
                f"/cadence/activity/{aid}",
                data=json.dumps({"cadence_code": "CONTINUOUS"}),
                content_type="application/json",
            )
            auth_client.post(
                f"/cadence/data/{did}",
                data=json.dumps({"update_cadence_code": "YEARLY"}),
                content_type="application/json",
            )
            r = auth_client.get("/cadence/consistency")
            data = r.get_json()
            matches = [w for w in data["warnings"] if w["source_data_id"] == did and w["target_activity_id"] == aid]
            assert len(matches) == 1
            w = matches[0]
            assert w["severity"] == "watch"
            assert "finding" in w
            assert "optiq_question" in w
        finally:
            with app.app_context():
                from Code.models.models import Link
                from Code.extensions import db
                lk = Link.query.get(link_id)
                if lk:
                    db.session.delete(lk)
                    db.session.commit()
            _cleanup_data(app, did)
            _cleanup_activity(app, aid)

    def test_consistency_no_warning_when_ranks_ok(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"], name="Activité Rythme Lent")
        did = _create_data(app, ids["entity_id"], name="Donnée Rythme Rapide")
        with app.app_context():
            from Code.models.models import Link
            from Code.extensions import db
            link = Link(entity_id=ids["entity_id"], source_data_id=did, target_activity_id=aid, type="nourrissante")
            db.session.add(link)
            db.session.commit()
            link_id = link.id
        try:
            auth_client.post(
                f"/cadence/activity/{aid}",
                data=json.dumps({"cadence_code": "YEARLY"}),
                content_type="application/json",
            )
            auth_client.post(
                f"/cadence/data/{did}",
                data=json.dumps({"update_cadence_code": "DAILY"}),
                content_type="application/json",
            )
            r = auth_client.get("/cadence/consistency")
            data = r.get_json()
            matches = [w for w in data["warnings"] if w["source_data_id"] == did and w["target_activity_id"] == aid]
            assert len(matches) == 0
        finally:
            with app.app_context():
                from Code.models.models import Link
                from Code.extensions import db
                lk = Link.query.get(link_id)
                if lk:
                    db.session.delete(lk)
                    db.session.commit()
            _cleanup_data(app, did)
            _cleanup_activity(app, aid)
