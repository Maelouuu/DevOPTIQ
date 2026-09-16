# tests/test_64_activities_map_gaps.py
"""
Complète la couverture de Code/routes/activities_map.py sur les zones non
exercées par test_15/test_42/test_44/test_50 :
  - Réassignation de l'entité active en session après suppression
  - PATCH description seule sur une entité
  - Extraction SVG Visio (mID/layerMember) + synchro (ajout/renommage/suppression)
  - /api/cross_carto_matches avec correspondances réelles (carto JSON + DB)
  - /api/liaison_matches avec liaison déjà officialisée (has_active_liaison)
  - /api/reverse_liaisons_map et /api/reverse_liaisons avec liaison active
  - /api/officialize_liaison : propagation des liens + injection de formes
  - /api/liaison_deoffice_preview et /api/liaison_deoffice sur formes injectées
"""
import io
import json
import uuid
from urllib.parse import quote

import pytest

pytestmark = pytest.mark.activities_map

VISIO_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:v="http://schemas.microsoft.com/visio/2003/SVGExtensions/"
     width="600" height="400">
  <g v:mID="1" v:layerMember="1"><text>Activite Renommee</text></g>
  <g v:mID="2" v:layerMember="1"><text>Activite Nouvelle</text></g>
  <g v:mID="3" v:layerMember="0"><text>Ignoree Hors Layer</text></g>
  <g v:mID="4" v:layerMember="1"><text>{trop_long}</text></g>
  <g v:mID="5" v:layerMember="1"><text>Activite Nouvelle</text></g>
</svg>""".format(trop_long="X" * 90)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers DB
# ─────────────────────────────────────────────────────────────────────────────

def _create_entity(app, user_id, name, optiqcarto_data=None):
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        e = Entity(name=name, description="", owner_id=user_id, optiqcarto_data=optiqcarto_data)
        db.session.add(e)
        db.session.commit()
        return e.id


def _create_activity(app, entity_id, name, shape_id=None, shape_subtype=None):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="",
                        shape_id=shape_id, shape_subtype=shape_subtype)
        db.session.add(a)
        db.session.commit()
        return a.id


def _create_link(app, entity_id, source_activity_id=None, target_activity_id=None, type="nourrissante"):
    with app.app_context():
        from Code.models.models import Link
        from Code.extensions import db
        lk = Link(entity_id=entity_id, source_activity_id=source_activity_id,
                  target_activity_id=target_activity_id, type=type)
        db.session.add(lk)
        db.session.commit()
        return lk.id


def _create_liaison(app, extco_entity_id, extco_activity_id, origin_entity_id, origin_activity_id, display_label=None):
    with app.app_context():
        from Code.models.models import CrossCartoLiaison
        from Code.extensions import db
        liaison = CrossCartoLiaison(
            extco_entity_id=extco_entity_id, extco_activity_id=extco_activity_id,
            origin_entity_id=origin_entity_id, origin_activity_id=origin_activity_id,
            is_active=True, display_label=display_label,
        )
        db.session.add(liaison)
        db.session.commit()
        return liaison.id


def _set_active(client, user_id, entity_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["active_entity_id"] = entity_id


def _get_entity_optiqcarto(app, entity_id):
    with app.app_context():
        from Code.models.models import Entity
        e = Entity.query.get(entity_id)
        return json.loads(e.optiqcarto_data) if e.optiqcarto_data else None


# ===========================================================================
# 1. CRUD entités — branches non couvertes
# ===========================================================================

class TestEntityCrudGaps:

    def test_delete_active_entity_reassigns_session(self, app, auth_client, ids):
        e1 = _create_entity(app, ids["user_id"], "Entité À Garder")
        e2 = _create_entity(app, ids["user_id"], "Entité À Supprimer")
        _set_active(auth_client, ids["user_id"], e2)

        resp = auth_client.delete(f"/activities/api/entities/{e2}")
        assert resp.status_code == 200

        with auth_client.session_transaction() as sess:
            assert sess.get("active_entity_id") in (e1, ids["entity_id"])

    def test_update_entity_description_only(self, app, auth_client, ids):
        eid = _create_entity(app, ids["user_id"], "Entité Description")
        _set_active(auth_client, ids["user_id"], eid)

        resp = auth_client.patch(f"/activities/api/entities/{eid}",
                                  json={"description": "Nouvelle description détaillée"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["entity"]["description"] == "Nouvelle description détaillée"


# ===========================================================================
# 2. Extraction SVG Visio + synchro activités
# ===========================================================================

class TestSvgExtractAndSync:

    def test_upload_new_svg_extracts_renames_adds_deletes(self, app, auth_client, ids):
        eid = _create_entity(app, ids["user_id"], "Entité Extraction SVG")
        # Activité déjà présente, sera renommée (shape_id="1" existe dans le nouveau SVG)
        old_act_id = _create_activity(app, eid, "Nom Ancien", shape_id="1")
        # Activité à supprimer (absente du nouveau SVG), avec un lien rattaché
        to_delete_id = _create_activity(app, eid, "A Supprimer", shape_id="99")
        _create_link(app, eid, source_activity_id=old_act_id, target_activity_id=to_delete_id)

        _set_active(auth_client, ids["user_id"], eid)

        resp = auth_client.post(
            "/activities/upload-cartography",
            data={
                "entity_id": str(eid),
                "mode": "new",
                "svg_file": (io.BytesIO(VISIO_SVG.encode("utf-8")), "carto.svg"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        sync = body["stats"]["sync"]

        # shape_id 1 renommé, shape_id 2 ajouté (5 est un doublon de nom, ignoré),
        # shape_id 4 ignoré (texte > 80 caractères), shape_id 3 ignoré (hors layer 1)
        assert sync["renamed"] == 1
        assert sync["added"] == 1
        assert sync["deleted"] == 1
        # Seuls les shapes 1 et 2 sont extraits : 3 (hors layer), 4 (texte >80
        # caractères) et 5 (nom déjà vu) sont ignorés par extract_activities_from_svg
        assert sync["total"] == 2

        with app.app_context():
            from Code.models.models import Activities, Link
            names = {a.shape_id: a.name for a in Activities.query.filter_by(entity_id=eid).all()}
            assert names.get("1") == "Activite Renommee"
            assert "99" not in names
            # Le lien référençant l'activité supprimée a été purgé en cascade
            assert Link.query.filter_by(entity_id=eid).filter(
                (Link.source_activity_id == to_delete_id) | (Link.target_activity_id == to_delete_id)
            ).count() == 0

    def test_keep_svg_without_existing_file_does_not_crash(self, app, auth_client, ids):
        eid = _create_entity(app, ids["user_id"], "Entité Keep Svg Sans Fichier")
        _set_active(auth_client, ids["user_id"], eid)

        resp = auth_client.post(
            "/activities/upload-cartography",
            data={"entity_id": str(eid), "mode": "update", "keep_svg": "true"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["stats"]["svg_kept"] is False

    def test_upload_uses_active_entity_when_no_entity_id(self, app, auth_client, ids):
        eid = _create_entity(app, ids["user_id"], "Entité Active Implicite")
        _set_active(auth_client, ids["user_id"], eid)

        resp = auth_client.post(
            "/activities/upload-cartography",
            data={
                "mode": "new",
                "svg_file": (io.BytesIO(VISIO_SVG.encode("utf-8")), "carto.svg"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["stats"]["activities"] >= 1


# ===========================================================================
# 3. /api/cross_carto_matches — correspondances réelles
# ===========================================================================

class TestCrossCartoMatchesReal:

    def test_matches_from_json_carto_and_from_plain_activities(self, app, auth_client, ids):
        active_carto = json.dumps({
            "shapes": [
                {"id": "1", "label": "Alpha Partagee", "subtype": "extco"},
                {"id": "2", "label": "Beta Partagee", "subtype": "extco"},
            ]
        })
        active_id = _create_entity(app, ids["user_id"], "Entité Active Cross Carto", optiqcarto_data=active_carto)

        # Autre entité avec carto JSON : une forme déjà en DB, une seulement dans le JSON
        other_carto = json.dumps({
            "shapes": [
                {"id": "10", "label": "Alpha Partagee", "subtype": "process"},
                {"id": "11", "label": "Gamma Json Only", "subtype": "process"},
            ]
        })
        other_id = _create_entity(app, ids["user_id"], "Entité Autre Cross Carto Json", optiqcarto_data=other_carto)
        _create_activity(app, other_id, "Alpha Partagee", shape_id="10")

        # Troisième entité SANS carto JSON : activités DB traitées comme non-hachurées
        plain_id = _create_entity(app, ids["user_id"], "Entité Autre Cross Carto Plain")
        _create_activity(app, plain_id, "Beta Partagee", shape_id="20")

        _set_active(auth_client, ids["user_id"], active_id)
        resp = auth_client.get("/activities/api/cross_carto_matches")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2
        matched_names = {m["activity_name"] for m in data["matches"]}
        assert matched_names == {"Alpha Partagee", "Beta Partagee"}


# ===========================================================================
# 4. Liaisons cross-carto : matches, reverse, officialisation, dé-officialisation
# ===========================================================================

class TestLiaisonFullCycle:

    @pytest.fixture
    def scenario(self, app, ids):
        """Entité A (extco) liée à une activité interne, entité B (origine) avec
        une activité de même nom que l'extco de A, et une carto JSON positionnée.

        Les noms incluent un suffixe unique par test pour éviter toute
        interférence avec les entités laissées en base par les autres tests
        de cette classe (même utilisateur propriétaire, session DB partagée).
        """
        suffix = uuid.uuid4().hex[:8]
        shared_name = f"Nom Partage {suffix}"
        interne_name = f"Activite Interne A {suffix}"

        active_carto = json.dumps({
            "shapes": [
                {"id": "20", "label": shared_name, "subtype": "extco",
                 "x": 400, "y": 100, "w": 160, "h": 60},
                {"id": "10", "label": interne_name,
                 "x": 400, "y": 300, "w": 160, "h": 60},
            ],
            "connections": [
                {"id": "30", "fromId": "20", "toId": "10", "label": "Flux Partage"},
            ],
            "nextId": 1000,
        })
        entity_a = _create_entity(app, ids["user_id"], f"Entité A Extco {suffix}", optiqcarto_data=active_carto)
        extco_act = _create_activity(app, entity_a, shared_name, shape_id="20", shape_subtype="extco")
        interne_act = _create_activity(app, entity_a, interne_name, shape_id="10")
        # Lien sortant de l'extco vers l'activité interne (sera propagé)
        _create_link(app, entity_a, source_activity_id=extco_act, target_activity_id=interne_act)

        origin_carto = json.dumps({
            "shapes": [
                {"id": "100", "label": shared_name, "x": 100, "y": 100, "w": 160, "h": 60},
            ],
            "connections": [],
            "nextId": 1000,
        })
        entity_b = _create_entity(app, ids["user_id"], f"Entité B Origine {suffix}", optiqcarto_data=origin_carto)
        origin_act = _create_activity(app, entity_b, shared_name, shape_id="100")

        return {
            "entity_a": entity_a, "extco_act": extco_act, "interne_act": interne_act,
            "entity_b": entity_b, "origin_act": origin_act,
            "shared_name": shared_name, "interne_name": interne_name,
            "entity_a_name": f"Entité A Extco {suffix}",
        }

    def test_officialize_liaison_propagates_links_and_injects_shapes(self, app, auth_client, ids, scenario):
        _set_active(auth_client, ids["user_id"], scenario["entity_a"])

        resp = auth_client.post("/activities/api/officialize_liaison", json={
            "extco_activity_id": scenario["extco_act"],
            "origin_entity_id": scenario["entity_b"],
            "origin_activity_id": scenario["origin_act"],
            "display_label": "Nom Partage (lié)",
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["links_created"] == 1

        with app.app_context():
            from Code.models.models import Link
            propagated = Link.query.filter_by(entity_id=scenario["entity_b"]).first()
            assert propagated is not None
            assert propagated.description == scenario["interne_name"]

        origin_carto = _get_entity_optiqcarto(app, scenario["entity_b"])
        injected = [s for s in origin_carto["shapes"] if s.get("crossCartoImport")]
        assert len(injected) == 1
        assert injected[0]["label"] == scenario["interne_name"]
        # Le label de la connexion source ("Flux Partage") a été récupéré
        injected_conn = [c for c in origin_carto["connections"] if c.get("toId") == injected[0]["id"] or c.get("fromId") == injected[0]["id"]]
        assert len(injected_conn) == 1

        # Rejouer la même officialisation -> already_exists
        resp2 = auth_client.post("/activities/api/officialize_liaison", json={
            "extco_activity_id": scenario["extco_act"],
            "origin_entity_id": scenario["entity_b"],
            "origin_activity_id": scenario["origin_act"],
        })
        assert resp2.status_code == 200
        assert resp2.get_json()["already_exists"] is True

    def test_liaison_matches_reports_existing_liaison(self, app, auth_client, ids, scenario):
        _create_liaison(app, scenario["entity_a"], scenario["extco_act"],
                         scenario["entity_b"], scenario["origin_act"], display_label="Déjà Lié")
        _set_active(auth_client, ids["user_id"], scenario["entity_a"])

        resp = auth_client.get(f"/activities/api/liaison_matches?name={quote(scenario['shared_name'])}")
        assert resp.status_code == 200
        matches = resp.get_json()["matches"]
        assert len(matches) == 1
        assert matches[0]["has_active_liaison"] is True
        assert matches[0]["display_label"] == "Déjà Lié"
        assert matches[0]["liaison_id"] is not None

    def test_reverse_liaisons_map_and_reverse_liaisons(self, app, auth_client, ids, scenario):
        _create_liaison(app, scenario["entity_a"], scenario["extco_act"],
                         scenario["entity_b"], scenario["origin_act"])
        _set_active(auth_client, ids["user_id"], scenario["entity_b"])

        resp_map = auth_client.get("/activities/api/reverse_liaisons_map")
        assert resp_map.status_code == 200
        origins = resp_map.get_json()["origins"]
        assert len(origins) == 1
        assert origins[0]["origin_activity_name"] == scenario["shared_name"]
        assert origins[0]["liaisons"][0]["entity_name"] == scenario["entity_a_name"]

        resp_rev = auth_client.get(f"/activities/api/reverse_liaisons?name={quote(scenario['shared_name'])}")
        assert resp_rev.status_code == 200
        matches = resp_rev.get_json()["matches"]
        assert len(matches) == 1
        assert matches[0]["entity_id"] == scenario["entity_a"]

    def test_liaison_deoffice_preview_and_deoffice_cleanup(self, app, auth_client, ids, scenario):
        _set_active(auth_client, ids["user_id"], scenario["entity_a"])
        resp = auth_client.post("/activities/api/officialize_liaison", json={
            "extco_activity_id": scenario["extco_act"],
            "origin_entity_id": scenario["entity_b"],
            "origin_activity_id": scenario["origin_act"],
        })
        assert resp.status_code == 200

        with app.app_context():
            from Code.models.models import CrossCartoLiaison
            liaison = CrossCartoLiaison.query.filter_by(
                extco_entity_id=scenario["entity_a"], origin_entity_id=scenario["entity_b"]
            ).first()
            liaison_id = liaison.id

        preview = auth_client.get(f"/activities/api/liaison_deoffice_preview?liaison_id={liaison_id}")
        assert preview.status_code == 200
        pdata = preview.get_json()
        assert pdata["shapes_to_remove"] == [scenario["interne_name"]]
        assert pdata["connections_to_remove"] == 1
        assert pdata["db_links_to_remove"] == 1

        deoffice = auth_client.post("/activities/api/liaison_deoffice", json={"liaison_id": liaison_id})
        assert deoffice.status_code == 200
        assert deoffice.get_json()["ok"] is True

        origin_carto = _get_entity_optiqcarto(app, scenario["entity_b"])
        assert all(not s.get("crossCartoImport") for s in origin_carto["shapes"])

        with app.app_context():
            from Code.models.models import Link, CrossCartoLiaison
            assert Link.query.filter_by(cross_carto_liaison_id=liaison_id).count() == 0
            assert CrossCartoLiaison.query.get(liaison_id) is None
