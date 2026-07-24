# tests/test_60_activity_items_api.py
# Couverture de Code/routes/activity_items_api.py — endpoint agrégé
# GET /your_api/activity_items/<activity_id> (savoirs + savoir-faire + HSC).
import pytest
from Code.extensions import db
from Code.models.models import Entity, Activities, Savoir, SavoirFaire, Softskill


@pytest.fixture()
def carto(app):
    """Entité dédiée : activité avec 2 savoirs, 1 savoir-faire, 2 HSC (avec/sans niveau),
    et une activité sans aucun item. Nettoyage complet après le test."""
    with app.app_context():
        ent = Entity(name="ActivityItemsApiEco")
        db.session.add(ent); db.session.flush()
        a = Activities(entity_id=ent.id, name="Activité avec items", shape_id="aia_s1")
        empty = Activities(entity_id=ent.id, name="Activité sans item", shape_id="aia_s2")
        db.session.add_all([a, empty]); db.session.flush()

        db.session.add_all([
            Savoir(description="Connaître la norme ISO", activity_id=a.id),
            Savoir(description="Connaître le process qualité", activity_id=a.id),
            SavoirFaire(description="Appliquer le protocole de contrôle", activity_id=a.id),
            Softskill(habilete="Rigueur", niveau="Confirmé", activity_id=a.id),
            Softskill(habilete="Communication", niveau="", activity_id=a.id),
        ])
        db.session.commit()
        ids = {"entity_id": ent.id, "activity_id": a.id, "empty_activity_id": empty.id}
    yield ids
    with app.app_context():
        Savoir.query.filter_by(activity_id=ids["activity_id"]).delete()
        SavoirFaire.query.filter_by(activity_id=ids["activity_id"]).delete()
        Softskill.query.filter_by(activity_id=ids["activity_id"]).delete()
        Activities.query.filter(
            Activities.id.in_([ids["activity_id"], ids["empty_activity_id"]])
        ).delete(synchronize_session=False)
        Entity.query.filter_by(id=ids["entity_id"]).delete()
        db.session.commit()


class TestActivityItemsApi:
    def test_returns_savoirs_savoir_faire_and_hsc(self, client, carto):
        r = client.get(f"/your_api/activity_items/{carto['activity_id']}")
        assert r.status_code == 200
        body = r.get_json()
        savoir_names = {s["name"] for s in body["savoirs"]}
        assert savoir_names == {"Connaître la norme ISO", "Connaître le process qualité"}
        sf_names = {s["name"] for s in body["savoir_faire"]}
        assert sf_names == {"Appliquer le protocole de contrôle"}

    def test_hsc_label_includes_level_when_present(self, client, carto):
        r = client.get(f"/your_api/activity_items/{carto['activity_id']}")
        hsc_names = {h["name"] for h in r.get_json()["hsc"]}
        assert "Rigueur (Confirmé)" in hsc_names

    def test_hsc_label_omits_empty_level(self, client, carto):
        r = client.get(f"/your_api/activity_items/{carto['activity_id']}")
        hsc_names = {h["name"] for h in r.get_json()["hsc"]}
        assert "Communication" in hsc_names
        assert not any(n.startswith("Communication (") for n in hsc_names)

    def test_activity_without_items_returns_empty_lists(self, client, carto):
        r = client.get(f"/your_api/activity_items/{carto['empty_activity_id']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body == {"savoirs": [], "savoir_faire": [], "hsc": []}

    def test_unknown_activity_id_returns_empty_lists(self, client, carto):
        r = client.get("/your_api/activity_items/999999")
        assert r.status_code == 200
        body = r.get_json()
        assert body == {"savoirs": [], "savoir_faire": [], "hsc": []}

    def test_accessible_without_auth(self, app, carto):
        anon_client = app.test_client()
        r = anon_client.get(f"/your_api/activity_items/{carto['activity_id']}")
        assert r.status_code == 200
