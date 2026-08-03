# tests/test_51_qualify_outputs.py
# CDC 1 (V1.1) — Les « données de sortie » d'une activité sont ses CONNEXIONS SORTANTES.
# Régression corrigée : le panneau « Configurer (qualifier les sorties) » affichait toujours
# « aucune donnée de sortie » car on ne cherchait que des Data ciblées par target_data_id, alors
# que les cartos réelles stockent les sorties en Link activité→activité (libellé de la flèche).
# On matérialise désormais chaque connexion sortante en Data durable (producer_activity_id).
import pytest
from Code.extensions import db
from Code.models.models import Entity, Activities, Link, Data


@pytest.fixture()
def carto(app):
    """Entité dédiée : activité A avec 3 connexions sortantes (2 avec libellé, 1 sans),
    activité Z sans aucune connexion sortante. Nettoyage complet après le test."""
    with app.app_context():
        ent = Entity(name="QualifOutECo")
        db.session.add(ent); db.session.flush()
        a = Activities(entity_id=ent.id, name="Usiner la pièce", shape_id="qo_s1")
        b = Activities(entity_id=ent.id, name="Contrôle qualité", shape_id="qo_s2")
        z = Activities(entity_id=ent.id, name="Sans sortie", shape_id="qo_s3")
        db.session.add_all([a, b, z]); db.session.flush()
        links = [
            Link(entity_id=ent.id, source_activity_id=a.id, target_activity_id=b.id,
                 type="flux", description="Pièce usinée"),
            Link(entity_id=ent.id, source_activity_id=a.id, target_activity_id=b.id,
                 type="flux", description="Fiche suiveuse"),
            Link(entity_id=ent.id, source_activity_id=a.id, target_activity_id=b.id,
                 type="flux", description=None),   # sans libellé → nom du destinataire
        ]
        db.session.add_all(links); db.session.commit()
        ids = {"entity_id": ent.id, "a": a.id, "b": b.id, "z": z.id}
    yield ids
    with app.app_context():
        Data.query.filter_by(producer_activity_id=ids["a"]).delete()
        Link.query.filter(Link.source_activity_id.in_([ids["a"], ids["b"], ids["z"]])).delete(
            synchronize_session=False)
        Activities.query.filter(Activities.id.in_([ids["a"], ids["b"], ids["z"]])).delete(
            synchronize_session=False)
        Entity.query.filter_by(id=ids["entity_id"]).delete()
        db.session.commit()


def _sess(client, entity_id):
    with client.session_transaction() as s:
        s["active_entity_id"] = entity_id
        s["lang"] = "fr"


def test_outputs_lists_outgoing_connections(client, carto):
    _sess(client, carto["entity_id"])
    r = client.get(f"/qualify/outputs/{carto['a']}")
    assert r.status_code == 200
    names = {o["name"] for o in r.get_json()["outputs"]}
    # 2 libellés + la connexion sans libellé prend le nom du destinataire
    assert names == {"Pièce usinée", "Fiche suiveuse", "Contrôle qualité"}


def test_activity_without_outgoing_has_no_outputs(client, carto):
    _sess(client, carto["entity_id"])
    r = client.get(f"/qualify/outputs/{carto['z']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["outputs"] == []
    assert body["all_qualified"] is False


def test_materialization_is_idempotent(app, client, carto):
    _sess(client, carto["entity_id"])
    client.get(f"/qualify/outputs/{carto['a']}")
    client.get(f"/qualify/outputs/{carto['a']}")
    with app.app_context():
        assert Data.query.filter_by(producer_activity_id=carto["a"]).count() == 3


def test_save_qualification_persists(app, client, carto):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = next(o for o in outs if o["name"] == "Pièce usinée")
    r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
        {"data_id": target["data_id"], "nature": "RESULT",
         "minimum_performance_text": "Cote respectée", "source": "MANUAL"}]})
    assert r.status_code == 200 and r.get_json()["saved"] == 1
    with app.app_context():
        d = Data.query.get(target["data_id"])
        assert d.semantic_nature == "RESULT"
        assert d.minimum_performance_text == "Cote respectée"


def test_qualified_output_survives_connection_rename(app, client, carto):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = next(o for o in outs if o["name"] == "Pièce usinée")
    client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
        {"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]})
    # la carto renomme le libellé de la connexion
    with app.app_context():
        lk = Link.query.filter_by(source_activity_id=carto["a"], description="Pièce usinée").first()
        lk.description = "Pièce finie"
        db.session.commit()
    names = {o["name"] for o in client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]}
    assert "Pièce finie" in names          # nouvelle connexion matérialisée
    assert "Pièce usinée" in names         # sortie qualifiée conservée (travail préservé)


class TestSave:
    def test_unknown_activity_returns_404(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post("/qualify/save/999999", json={"outputs": []})
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_unknown_data_id_is_ignored(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": 999999, "nature": "RESULT", "source": "MANUAL"}]})
        assert r.status_code == 200
        assert r.get_json()["saved"] == 0

    def test_requalifying_a_result_emits_warning(self, app, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Pièce usinée")
        client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]})
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "MEASURE", "source": "MANUAL"}]})
        assert r.status_code == 200
        body = r.get_json()
        assert body["saved"] == 1
        assert len(body["warnings"]) == 1
        assert body["warnings"][0]["data_id"] == target["data_id"]
        with app.app_context():
            d = Data.query.get(target["data_id"])
            assert d.semantic_nature == "MEASURE"


class TestAnalyze:
    """POST /qualify/analyze/<activity_id> — pas de clé IA en test → repli explicite
    (CDC §8 : jamais de nature inventée, jamais de 500)."""

    def test_unknown_activity_returns_404(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post("/qualify/analyze/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_no_outputs_returns_warning(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['z']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["outputs"] == []
        assert body["source"] == "no_outputs"
        assert body["warning"]

    def test_no_ai_key_returns_fallback_proposals(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] != "AI"
        assert body.get("warning") is None  # avertissement calculé seulement sur repli IA (raw), pas absence de clé
        assert len(body["outputs"]) == 3
        for prop in body["outputs"]:
            assert prop["suggested_nature"] is None
            assert prop["confidence"] == "none"
