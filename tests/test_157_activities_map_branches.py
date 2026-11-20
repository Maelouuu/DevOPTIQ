# -*- coding: utf-8 -*-
"""Carte des activités — branches encore jamais empruntées.

Chaque cas crée ses propres entités (nommées `T157 …`) et les efface ; quand il
change l'entité active de la session, il la rend telle qu'il l'a trouvée. La
session et la base sont partagées par toute la suite : un test qui laisserait
la carto « T157 » active ferait échouer des fichiers qu'il ne connaît pas.
"""
import json
import uuid

import pytest

from Code.extensions import db
from Code.models.models import (
    Activities, CrossCartoLiaison, Entity, Link, Role, User, activity_roles,
)


def _nom(prefixe="T157"):
    return f"{prefixe} {uuid.uuid4().hex[:8]}"


@pytest.fixture
def entite_active(app, auth_client):
    """Rend l'entité active d'avant, quelle que soit l'issue du test."""
    with auth_client.session_transaction() as s:
        avant = s.get("active_entity_id")

    def poser(entity_id):
        with auth_client.session_transaction() as s:
            s["active_entity_id"] = entity_id

    yield poser
    with auth_client.session_transaction() as s:
        if avant is None:
            s.pop("active_entity_id", None)
        else:
            s["active_entity_id"] = avant


@pytest.fixture
def jetables(app):
    """Entités / comptes créés par le test, effacés à la fin."""
    crees = {"entities": [], "users": [], "liaisons": []}
    yield crees
    with app.app_context():
        for lid in crees["liaisons"]:
            Link.query.filter_by(cross_carto_liaison_id=lid).delete()
            l = db.session.get(CrossCartoLiaison, lid)
            if l:
                db.session.delete(l)
        db.session.commit()
        for eid in crees["entities"]:
            Link.query.filter_by(entity_id=eid).delete()
            for a in Activities.query.filter_by(entity_id=eid).all():
                db.session.execute(activity_roles.delete().where(
                    activity_roles.c.activity_id == a.id))
                db.session.delete(a)
            e = db.session.get(Entity, eid)
            if e:
                db.session.delete(e)
        db.session.commit()
        for uid in crees["users"]:
            u = db.session.get(User, uid)
            if u:
                db.session.delete(u)
        db.session.commit()


def _entite(app, crees, owner_id, carto=None, raw=None):
    with app.app_context():
        e = Entity(name=_nom(), owner_id=owner_id)
        if raw is not None:
            e.optiqcarto_data = raw
        elif carto is not None:
            e.optiqcarto_data = json.dumps(carto)
        db.session.add(e)
        db.session.commit()
        crees["entities"].append(e.id)
        return e.id


def _compte(app, crees):
    with app.app_context():
        u = User(first_name="Autre", last_name="T157",
                 email=f"t157-{uuid.uuid4().hex[:8]}@devoptiq.test",
                 password="x", status="user")
        db.session.add(u)
        db.session.commit()
        crees["users"].append(u.id)
        return u.id


def _activite(app, entity_id, nom="Act T157"):
    with app.app_context():
        a = Activities(entity_id=entity_id, name=nom)
        db.session.add(a)
        db.session.commit()
        return a.id


def _liaison(app, crees, origin_id, extco_id):
    a1 = _activite(app, origin_id, "Origine T157")
    a2 = _activite(app, extco_id, "Extco T157")
    with app.app_context():
        l = CrossCartoLiaison(origin_entity_id=origin_id, origin_activity_id=a1,
                              extco_entity_id=extco_id, extco_activity_id=a2)
        db.session.add(l)
        db.session.commit()
        crees["liaisons"].append(l.id)
        return l.id


class TestActivitiesMapPartage:
    def test_share_destinataires_non_numeriques_refuses_400(self, app, auth_client, ids, jetables):
        eid = _entite(app, jetables, ids["user_id"])
        r = auth_client.post(f"/activities/api/entities/{eid}/share",
                             json={"user_ids": ["pas-un-id"]})
        assert r.status_code == 400
        assert r.get_json()["error"] == "Liste de destinataires invalide"

    def test_share_admin_remplacement_illisible_refuse_400(self, app, auth_client, ids, jetables):
        eid = _entite(app, jetables, ids["user_id"])
        autre = _compte(app, jetables)
        r = auth_client.post(f"/activities/api/entities/{eid}/share",
                             json={"user_ids": [autre], "replace": {"x": "y"}})
        assert r.status_code == 400
        assert r.get_json()["error"] == "Entité à remplacer invalide"

    def test_share_remplacement_illisible_ne_cree_aucune_copie(self, app, auth_client, ids, jetables):
        eid = _entite(app, jetables, ids["user_id"])
        autre = _compte(app, jetables)
        auth_client.post(f"/activities/api/entities/{eid}/share",
                         json={"user_ids": [autre], "replace": {"1": "abc"}})
        with app.app_context():
            assert Entity.query.filter_by(owner_id=autre).count() == 0


class TestActivitiesMapDivers:
    def test_update_cartography_est_servi_par_l_import_visio(self, app):
        """L'URL est déclarée DEUX fois (activities_bp et activities_map_bp) :
        c'est l'import Visio d'`activities_cartography.py` qui la sert, le
        « ok » factice de la carte n'est jamais atteint."""
        adapter = app.url_map.bind("localhost")
        endpoint, _ = adapter.match("/activities/update-cartography", method="GET")
        assert endpoint == "activities.update_cartography"

    def test_activer_entite_sans_proprietaire_desactive_les_autres_legacy(
            self, app, auth_client, jetables, entite_active):
        entite_active(None)
        legacy = _entite(app, jetables, None)
        autre_legacy = _entite(app, jetables, None)
        with app.app_context():
            db.session.get(Entity, autre_legacy).is_active = True
            db.session.commit()
        r = auth_client.post(f"/activities/api/entities/{legacy}/activate")
        assert r.status_code == 200
        with app.app_context():
            assert db.session.get(Entity, autre_legacy).is_active is False
            assert db.session.get(Entity, legacy).is_active is True
        with auth_client.session_transaction() as s:
            assert s["active_entity_id"] == legacy

    def test_supprimer_entite_efface_le_role_qui_ne_sert_plus(self, app, auth_client, ids, jetables):
        eid = _entite(app, jetables, ids["user_id"])
        aid = _activite(app, eid)
        with app.app_context():
            role = Role(name=_nom("Rôle T157"), entity_id=eid)
            db.session.add(role)
            db.session.flush()
            db.session.execute(activity_roles.insert().values(
                activity_id=aid, role_id=role.id, status="Réalisateur"))
            db.session.commit()
            rid = role.id
        r = auth_client.delete(f"/activities/api/entities/{eid}")
        assert r.status_code == 200
        with app.app_context():
            assert db.session.get(Role, rid) is None
            assert db.session.get(Entity, eid) is None


class TestActivitiesMapCrossCartoMatches:
    def test_carto_active_json_illisible_renvoie_liste_vide(self, app, auth_client, ids, jetables, entite_active):
        eid = _entite(app, jetables, ids["user_id"], raw="{pas du json")
        entite_active(eid)
        r = auth_client.get("/activities/api/cross_carto_matches")
        assert r.status_code == 200
        assert r.get_json() == {"matches": [], "total": 0}

    def test_carto_active_sans_forme_hachuree_renvoie_liste_vide(self, app, auth_client, ids, jetables, entite_active):
        carto = {"shapes": [{"id": "s1", "label": "Normale", "subtype": "activity"},
                            {"id": "s2", "label": "  ", "subtype": "extco"}]}
        eid = _entite(app, jetables, ids["user_id"], carto=carto)
        entite_active(eid)
        r = auth_client.get("/activities/api/cross_carto_matches")
        assert r.get_json() == {"matches": [], "total": 0}


class TestActivitiesMapDeofficialisation:
    def test_apercu_liaison_d_un_autre_compte_refuse_403(self, app, auth_client, jetables):
        autre = _compte(app, jetables)
        o = _entite(app, jetables, autre)
        x = _entite(app, jetables, autre)
        lid = _liaison(app, jetables, o, x)
        r = auth_client.get(f"/activities/api/liaison_deoffice_preview?liaison_id={lid}")
        assert r.status_code == 403
        assert r.get_json()["error"] == "Non autorisé"

    def test_deoffice_liaison_d_un_autre_compte_refuse_et_la_garde(self, app, auth_client, jetables):
        autre = _compte(app, jetables)
        o = _entite(app, jetables, autre)
        x = _entite(app, jetables, autre)
        lid = _liaison(app, jetables, o, x)
        r = auth_client.post("/activities/api/liaison_deoffice", json={"liaison_id": lid})
        assert r.status_code == 403
        with app.app_context():
            assert db.session.get(CrossCartoLiaison, lid) is not None

    def test_apercu_carto_origine_illisible_ne_compte_rien(self, app, auth_client, ids, jetables):
        o = _entite(app, jetables, ids["user_id"], raw="[[cassé")
        x = _entite(app, jetables, ids["user_id"])
        lid = _liaison(app, jetables, o, x)
        r = auth_client.get(f"/activities/api/liaison_deoffice_preview?liaison_id={lid}")
        assert r.status_code == 200
        d = r.get_json()
        assert d["shapes_to_remove"] == []
        assert d["connections_to_remove"] == 0

    def test_deoffice_carto_origine_illisible_supprime_quand_meme_la_liaison(self, app, auth_client, ids, jetables):
        o = _entite(app, jetables, ids["user_id"], raw="[[cassé")
        x = _entite(app, jetables, ids["user_id"])
        lid = _liaison(app, jetables, o, x)
        with app.app_context():
            db.session.add(Link(entity_id=o, type="cross", cross_carto_liaison_id=lid))
            db.session.commit()
        r = auth_client.post("/activities/api/liaison_deoffice", json={"liaison_id": lid})
        assert r.status_code == 200
        assert r.get_json() == {"ok": True}
        with app.app_context():
            assert db.session.get(CrossCartoLiaison, lid) is None
            assert Link.query.filter_by(cross_carto_liaison_id=lid).count() == 0
            assert db.session.get(Entity, o).optiqcarto_data == "[[cassé"

    def test_deoffice_retire_les_formes_injectees_de_la_carto_origine(self, app, auth_client, ids, jetables):
        x = _entite(app, jetables, ids["user_id"])
        with app.app_context():
            nom_x = db.session.get(Entity, x).name
        carto = {"shapes": [
            {"id": "a", "label": "Garde"},
            {"id": "b", "label": "Injectée", "crossCartoImport": True, "crossCartoSource": nom_x},
        ], "connections": [{"fromId": "a", "toId": "b"}]}
        o = _entite(app, jetables, ids["user_id"], carto=carto)
        lid = _liaison(app, jetables, o, x)
        apercu = auth_client.get(f"/activities/api/liaison_deoffice_preview?liaison_id={lid}").get_json()
        assert apercu["shapes_to_remove"] == ["Injectée"]
        assert apercu["connections_to_remove"] == 1
        auth_client.post("/activities/api/liaison_deoffice", json={"liaison_id": lid})
        with app.app_context():
            reste = json.loads(db.session.get(Entity, o).optiqcarto_data)
        assert [s["id"] for s in reste["shapes"]] == ["a"]
        assert reste["connections"] == []
