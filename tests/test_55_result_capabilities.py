# tests/test_55_result_capabilities.py
"""
Page : Compétence principale & liens S/SF/HSC par résultat (/competence)
CDC 2 (V1.1) — La compétence = capacité démontrée à tenir l'activité en produisant ses
RÉSULTATS au niveau minimal requis. Les S/SF/HSC sont reliés à chaque RESULT (diagnostic
d'écart). Sans OPENAI_API_KEY (env. de test), generate/generate_result_links doivent
retourner 200 + source != 'AI' (jamais planter).
Couvre : /competence/generate/<id>, /competence/save/<id>,
/competence/result_links/generate/<id>, /competence/result_links/<id> (GET/POST).
"""
import pytest
import json
from Code.extensions import db
from Code.models.models import (
    Entity, Activities, Data, Link, Competency, Savoir, SavoirFaire, Softskill,
    ResultCapabilityLink,
)

pytestmark = pytest.mark.result_capabilities


@pytest.fixture()
def scene(app):
    """Entité dédiée, activité avec une connexion sortante matérialisée + qualifiée en RESULT."""
    with app.app_context():
        ent = Entity(name="ResultCapECo")
        db.session.add(ent)
        db.session.flush()
        act = Activities(entity_id=ent.id, name="Souder le châssis", shape_id="rc_a1")
        other = Activities(entity_id=ent.id, name="Contrôle final", shape_id="rc_a2")
        db.session.add_all([act, other])
        db.session.flush()
        link = Link(entity_id=ent.id, source_activity_id=act.id, target_activity_id=other.id,
                    type="flux", description="Châssis soudé")
        db.session.add(link)
        db.session.commit()
        result = {"entity_id": ent.id, "activity_id": act.id}

    # matérialise la sortie en Data puis la qualifie en RESULT (via /qualify, comme en prod)
    with app.test_client() as c:
        with c.session_transaction() as s:
            s["active_entity_id"] = result["entity_id"]
        outs = c.get(f"/qualify/outputs/{result['activity_id']}").get_json()["outputs"]
        data_id = outs[0]["data_id"]
        c.post(f"/qualify/save/{result['activity_id']}", json={"outputs": [
            {"data_id": data_id, "nature": "RESULT", "minimum_performance_text": "Cordon continu"}]})
    result["data_id"] = data_id
    yield result

    with app.app_context():
        ResultCapabilityLink.query.filter_by(activity_id=result["activity_id"]).delete()
        Competency.query.filter_by(activity_id=result["activity_id"]).delete()
        Savoir.query.filter_by(activity_id=result["activity_id"]).delete()
        SavoirFaire.query.filter_by(activity_id=result["activity_id"]).delete()
        Softskill.query.filter_by(activity_id=result["activity_id"]).delete()
        Link.query.filter_by(entity_id=result["entity_id"]).delete()
        Data.query.filter_by(producer_activity_id=result["activity_id"]).delete()
        Activities.query.filter(Activities.entity_id == result["entity_id"]).delete()
        Entity.query.filter_by(id=result["entity_id"]).delete()
        db.session.commit()


# ===========================================================================
# 1. POST /competence/generate/<activity_id>
# ===========================================================================

class TestGenerateCompetence:

    def test_generate_without_openai_key_returns_no_ai(self, client, scene):
        r = client.post(f"/competence/generate/{scene['activity_id']}")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["competence"] is None
        assert body["source"] != "AI"

    def test_generate_activity_not_found_returns_404(self, client):
        r = client.post("/competence/generate/999999")
        assert r.status_code == 404

    def test_generate_no_qualified_result_returns_no_result(self, app, client):
        with app.app_context():
            ent = Entity(name="ResultCapNoResultECo")
            db.session.add(ent)
            db.session.flush()
            act = Activities(entity_id=ent.id, name="Activité sans résultat", shape_id="rc_none")
            db.session.add(act)
            db.session.commit()
            aid, eid = act.id, ent.id
        r = client.post(f"/competence/generate/{aid}")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["competence"] is None
        assert body["source"] == "no_result"
        with app.app_context():
            Activities.query.filter_by(id=aid).delete()
            Entity.query.filter_by(id=eid).delete()
            db.session.commit()


# ===========================================================================
# 2. POST /competence/save/<activity_id>
# ===========================================================================

class TestSaveCompetence:

    def test_save_persists_description(self, app, client, scene):
        r = client.post(f"/competence/save/{scene['activity_id']}",
                        data=json.dumps({"description": "Capable de souder un châssis conforme."}),
                        content_type="application/json")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["ok"] is True
        with app.app_context():
            comps = Competency.query.filter_by(activity_id=scene["activity_id"]).all()
            assert len(comps) == 1
            assert comps[0].description == "Capable de souder un châssis conforme."

    def test_save_replaces_existing_competency(self, app, client, scene):
        client.post(f"/competence/save/{scene['activity_id']}",
                    data=json.dumps({"description": "Première version"}), content_type="application/json")
        client.post(f"/competence/save/{scene['activity_id']}",
                    data=json.dumps({"description": "Seconde version"}), content_type="application/json")
        with app.app_context():
            comps = Competency.query.filter_by(activity_id=scene["activity_id"]).all()
            assert len(comps) == 1
            assert comps[0].description == "Seconde version"

    def test_save_empty_description_returns_400(self, client, scene):
        r = client.post(f"/competence/save/{scene['activity_id']}",
                        data=json.dumps({"description": "  "}), content_type="application/json")
        assert r.status_code == 400

    def test_save_activity_not_found_returns_404(self, client):
        r = client.post("/competence/save/999999",
                        data=json.dumps({"description": "Ghost"}), content_type="application/json")
        assert r.status_code == 404


# ===========================================================================
# 3. POST /competence/result_links/generate/<activity_id>
# ===========================================================================

class TestGenerateResultLinks:

    def test_generate_links_without_openai_key_returns_empty(self, client, scene):
        r = client.post(f"/competence/result_links/generate/{scene['activity_id']}")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["links"] == []
        assert body["source"] != "AI"

    def test_generate_links_activity_not_found_returns_404(self, client):
        r = client.post("/competence/result_links/generate/999999")
        assert r.status_code == 404


# ===========================================================================
# 4. GET/POST /competence/result_links/<activity_id> — gestion manuelle des liens
# ===========================================================================

class TestResultLinksManual:

    def test_get_result_links_empty_initially(self, client, scene):
        r = client.get(f"/competence/result_links/{scene['activity_id']}")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["by_result"] == []
        assert body["badges"] == {}

    def test_get_result_links_activity_not_found_returns_404(self, client):
        r = client.get("/competence/result_links/999999")
        assert r.status_code == 404

    def test_upsert_creates_manual_link_to_existing_savoir_faire(self, app, client, scene):
        with app.app_context():
            sf = SavoirFaire(activity_id=scene["activity_id"], description="Régler le poste à souder")
            db.session.add(sf)
            db.session.commit()
            sf_id = sf.id
        r = client.post(f"/competence/result_links/{scene['activity_id']}", data=json.dumps({
            "data_id": scene["data_id"], "item_type": "SAVOIR_FAIRE", "item_id": sf_id,
            "required_level": 2,
        }), content_type="application/json")
        assert r.status_code == 200
        body = json.loads(r.data)
        assert len(body["links"]["by_result"]) == 1
        item = body["links"]["by_result"][0]["items"][0]
        assert item["item_type"] == "SAVOIR_FAIRE"
        assert item["item_id"] == sf_id
        assert item["source"] == "MANUAL"
        assert item["required_level"] == 2

    def test_upsert_missing_fields_returns_400(self, client, scene):
        r = client.post(f"/competence/result_links/{scene['activity_id']}",
                        data=json.dumps({"data_id": scene["data_id"]}), content_type="application/json")
        assert r.status_code == 400

    def test_upsert_invalid_item_type_returns_400(self, client, scene):
        r = client.post(f"/competence/result_links/{scene['activity_id']}", data=json.dumps({
            "data_id": scene["data_id"], "item_type": "BOGUS", "item_id": 1,
        }), content_type="application/json")
        assert r.status_code == 400

    def test_delete_link_via_delete_id(self, app, client, scene):
        with app.app_context():
            sav = Savoir(activity_id=scene["activity_id"], description="Métallurgie de base")
            db.session.add(sav)
            db.session.commit()
            sav_id = sav.id
        created = client.post(f"/competence/result_links/{scene['activity_id']}", data=json.dumps({
            "data_id": scene["data_id"], "item_type": "SAVOIR", "item_id": sav_id,
        }), content_type="application/json").get_json()
        link_id = created["links"]["by_result"][0]["items"][0]["id"]
        r = client.post(f"/competence/result_links/{scene['activity_id']}",
                        data=json.dumps({"delete_id": link_id}), content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["links"]["by_result"] == []

    def test_result_label_is_stable_r1(self, app, client, scene):
        with app.app_context():
            sav = Savoir(activity_id=scene["activity_id"], description="Norme de soudure")
            db.session.add(sav)
            db.session.commit()
            sav_id = sav.id
        r = client.post(f"/competence/result_links/{scene['activity_id']}", data=json.dumps({
            "data_id": scene["data_id"], "item_type": "SAVOIR", "item_id": sav_id,
        }), content_type="application/json")
        body = json.loads(r.data)
        assert body["links"]["by_result"][0]["result_label"] == "R1"
