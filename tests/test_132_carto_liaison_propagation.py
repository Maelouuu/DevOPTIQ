# tests/test_132_carto_liaison_propagation.py
"""
Éditeur OptiqCarto — propagation des liaisons cross-carto lors d'un save :
une activité hachurée (extco) officialisée reporte ses connexions vers
l'activité d'origine (autre entité) sous forme de Link orphelins d'un côté.

Entités et utilisateur jetables, supprimés en fin de test.
"""
import json
import uuid
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.carto_liaison_propagation

DIAGRAM = {
    "shapes": [
        {"id": 1, "label": "Hachuree", "type": "process", "subtype": "extco",
         "x": 200, "y": 0, "w": 170, "h": 70},
        {"id": 2, "label": "Aval", "type": "process",
         "x": 400, "y": 0, "w": 170, "h": 70},
        {"id": 3, "label": "Amont", "type": "process",
         "x": 0, "y": 0, "w": 170, "h": 70},
    ],
    "bands": [{"id": 1, "label": "Bande", "height": 220}],
    "connections": [{"fromId": 1, "toId": 2}, {"fromId": 3, "toId": 1}],
}


@pytest.fixture
def env(app):
    from Code.extensions import db
    from Code.models.models import (Activities, CrossCartoLiaison, Entity,
                                    Link, User)

    tag = uuid.uuid4().hex[:8]
    with app.app_context():
        ent = Entity(name=f"Extco {tag}")
        origin = Entity(name=f"Origine {tag}")
        db.session.add_all([ent, origin])
        db.session.flush()
        user = User(entity_id=ent.id, first_name="L", last_name="P",
                    email=f"liai-{tag}@devoptiq.com", password="x", status="admin")
        db.session.add(user)
        db.session.flush()
        ent.owner_id = user.id
        origin.optiqcarto_data = json.dumps({
            "shapes": [{"id": 50, "label": "Orig", "type": "process",
                        "x": 300, "y": 300, "w": 170, "h": 70}],
            "bands": [], "connections": [], "nextId": 100})
        origin_act = Activities(entity_id=origin.id, name=f"Orig {tag}", shape_id="50")
        db.session.add(origin_act)
        db.session.commit()
        ids = SimpleNamespace(tag=tag, ent=ent.id, origin=origin.id, user=user.id,
                              email=user.email, origin_act=origin_act.id)

    client = app.test_client()
    with client.session_transaction() as s:
        s["user_id"] = ids.user
        s["user_email"] = ids.email
        s["active_entity_id"] = ids.ent
    ids.client = client
    yield ids

    with app.app_context():
        for eid in (ids.ent, ids.origin):
            Link.query.filter_by(entity_id=eid).delete()
        CrossCartoLiaison.query.filter(
            CrossCartoLiaison.extco_entity_id == ids.ent).delete()
        for eid in (ids.ent, ids.origin):
            acts = Activities.query.filter_by(entity_id=eid).all()
            for a in acts:
                db.session.execute(
                    db.text("DELETE FROM activity_roles WHERE activity_id=:i"), {"i": a.id})
                db.session.delete(a)
        from Code.models.models import Role
        Role.query.filter_by(entity_id=ids.ent).delete()
        Entity.query.filter_by(id=ids.ent).update({"owner_id": None})
        User.query.filter_by(id=ids.user).delete()
        Entity.query.filter_by(id=ids.ent).delete()
        Entity.query.filter_by(id=ids.origin).delete()
        db.session.commit()


def _save(env):
    r = env.client.post("/cartography/api/save", json={"diagram": DIAGRAM})
    assert r.status_code == 200
    return r.get_json()


def _liaise(app, env):
    from Code.extensions import db
    from Code.models.models import Activities, CrossCartoLiaison
    with app.app_context():
        extco = Activities.query.filter_by(entity_id=env.ent, name="Hachuree").one()
        lid = CrossCartoLiaison(extco_entity_id=env.ent, extco_activity_id=extco.id,
                                origin_entity_id=env.origin,
                                origin_activity_id=env.origin_act, is_active=True)
        db.session.add(lid)
        db.session.commit()
        return lid.id


class TestLiaisonPropagation:
    def test_save_reporte_les_liens_sortants_et_entrants_vers_l_origine(self, app, env):
        from Code.models.models import Link
        _save(env)
        lid = _liaise(app, env)
        body = _save(env)
        assert "sync_warning" not in body
        with app.app_context():
            links = Link.query.filter_by(entity_id=env.origin,
                                         cross_carto_liaison_id=lid).all()
            sortant = [l for l in links if l.source_activity_id == env.origin_act]
            entrant = [l for l in links if l.target_activity_id == env.origin_act]
            assert [l.description for l in sortant] == ["Aval"]
            assert [l.description for l in entrant] == ["Amont"]
            assert {l.cross_carto_label for l in links} == {f"Extco {env.tag}"}

    def test_resave_ne_duplique_pas_les_liens_propages(self, app, env):
        from Code.models.models import Link
        _save(env)
        lid = _liaise(app, env)
        _save(env)
        _save(env)
        with app.app_context():
            n = Link.query.filter_by(entity_id=env.origin,
                                     cross_carto_liaison_id=lid).count()
            assert n == 2

    def test_liaison_inactive_ne_propage_rien(self, app, env):
        from Code.extensions import db
        from Code.models.models import CrossCartoLiaison, Link
        _save(env)
        lid = _liaise(app, env)
        with app.app_context():
            CrossCartoLiaison.query.get(lid).is_active = False
            db.session.commit()
        _save(env)
        with app.app_context():
            assert Link.query.filter_by(entity_id=env.origin,
                                        cross_carto_liaison_id=lid).count() == 0

    def test_save_injecte_les_formes_dans_la_carto_d_origine(self, app, env):
        from Code.models.models import Entity
        _save(env)
        _liaise(app, env)
        _save(env)
        with app.app_context():
            data = Entity.query.get(env.origin).optiqcarto_data
        assert data
        labels = {s.get("label") for s in json.loads(data).get("shapes", [])}
        assert {"Aval", "Amont"} & labels
