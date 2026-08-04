# tests/test_51_qualify_outputs.py
# CDC 1 (V1.1) — Les « données de sortie » d'une activité sont ses CONNEXIONS SORTANTES.
# Régression corrigée : le panneau « Configurer (qualifier les sorties) » affichait toujours
# « aucune donnée de sortie » car on ne cherchait que des Data ciblées par target_data_id, alors
# que les cartos réelles stockent les sorties en Link activité→activité (libellé de la flèche).
# On matérialise désormais chaque connexion sortante en Data durable (producer_activity_id).
import json
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


def test_outputs_unknown_activity_returns_404(auth_client):
    r = auth_client.get("/qualify/outputs/999999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "activity_not_found"


# ===========================================================================
# POST /qualify/analyze/<activity_id> — Qualification IA (fake client)
# ===========================================================================

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content=None, raise_exc=None):
        self.completions = _FakeChatCompletions(content, raise_exc)


class _FakeOpenAIClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_ai(monkeypatch, content=None, raise_exc=None):
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (fake_client, None),
    )


class TestAnalyzeOutputs:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post("/qualify/analyze/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_no_outputs_returns_no_outputs_source(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['z']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "no_outputs"
        assert body["outputs"] == []

    def test_no_ai_key_falls_back_without_error(self, client, carto):
        """Sans clé IA (environnement de test), repli explicite : aucune nature inventée."""
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] != "AI"
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_ai_success_qualifies_targeted_output(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        did = outs[0]["data_id"]
        content = json.dumps({"outputs": [
            {"data_id": did, "suggested_nature": "RESULT", "confidence": "high",
             "justification": "Démontre la tenue de l'activité",
             "suggested_minimum_performance": "Cote respectée"},
        ]})
        _mock_ai(monkeypatch, content=content)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "AI"
        target = next(o for o in body["outputs"] if o["data_id"] == did)
        assert target["suggested_nature"] == "RESULT"
        assert target["suggested_minimum_performance"] == "Cote respectée"
        # les sorties non traitées par l'IA repartent en "à qualifier"
        others = [o for o in body["outputs"] if o["data_id"] != did]
        assert others and all(o["suggested_nature"] is None for o in others)

    def test_ai_zero_results_warns_no_result_identified(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_ai(monkeypatch, content=json.dumps({"outputs": []}))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert body["warning"] is not None
        assert "résultat" in body["warning"].lower()

    def test_ai_more_than_three_results_warns_granularity(self, app, client, monkeypatch):
        """> 3 résultats identifiés pour une même activité → alerte de granularité."""
        with app.app_context():
            ent = Entity(name="QualifOutGranEnt")
            db.session.add(ent); db.session.flush()
            a = Activities(entity_id=ent.id, name="Activité multi-résultats", shape_id="qo_gran_a")
            b = Activities(entity_id=ent.id, name="Aval", shape_id="qo_gran_b")
            db.session.add_all([a, b]); db.session.flush()
            links = [Link(entity_id=ent.id, source_activity_id=a.id, target_activity_id=b.id,
                          type="flux", description=f"Sortie {i}") for i in range(4)]
            db.session.add_all(links); db.session.commit()
            entity_id, aid, bid = ent.id, a.id, b.id
        try:
            _sess(client, entity_id)
            outs = client.get(f"/qualify/outputs/{aid}").get_json()["outputs"]
            assert len(outs) == 4
            content = json.dumps({"outputs": [
                {"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs
            ]})
            _mock_ai(monkeypatch, content=content)
            r = client.post(f"/qualify/analyze/{aid}")
            body = r.get_json()
            assert body["warning"] is not None
            assert "trois" in body["warning"].lower() or "three" in body["warning"].lower()
        finally:
            with app.app_context():
                Data.query.filter_by(producer_activity_id=aid).delete()
                Link.query.filter(Link.source_activity_id.in_([aid, bid])).delete(synchronize_session=False)
                Activities.query.filter(Activities.id.in_([aid, bid])).delete(synchronize_session=False)
                Entity.query.filter_by(id=entity_id).delete()
                db.session.commit()

    def test_ai_exception_falls_back_with_error_source(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_ai(monkeypatch, raise_exc=RuntimeError("boom"))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "error"
        assert "boom" in body["error"]
        # repli : aucune nature inventée malgré l'échec IA
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_ai_unknown_data_id_is_ignored(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        content = json.dumps({"outputs": [{"data_id": 999999, "suggested_nature": "RESULT"}]})
        _mock_ai(monkeypatch, content=content)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_ai_invalid_nature_code_becomes_none(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        did = outs[0]["data_id"]
        content = json.dumps({"outputs": [{"data_id": did, "suggested_nature": "BOGUS_CODE"}]})
        _mock_ai(monkeypatch, content=content)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        target = next(o for o in body["outputs"] if o["data_id"] == did)
        assert target["suggested_nature"] is None


# ===========================================================================
# POST /qualify/save/<activity_id> — cas limites
# ===========================================================================

class TestSaveOutputsEdgeCases:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post("/qualify/save/999999", json={"outputs": []})
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_unknown_data_id_is_skipped_not_saved(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": 999999, "nature": "RESULT"}]})
        assert r.status_code == 200
        assert r.get_json()["saved"] == 0

    def test_invalid_nature_code_is_stored_as_none(self, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        did = outs[0]["data_id"]
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": did, "nature": "NOT_A_REAL_CODE"}]})
        assert r.status_code == 200
        target = next(o for o in r.get_json()["outputs"] if o["data_id"] == did)
        assert target["nature"] is None

    def test_requalify_result_to_other_nature_emits_warning(self, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        did = outs[0]["data_id"]
        client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": did, "nature": "RESULT", "source": "MANUAL"}]})
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": did, "nature": "MEASURE", "source": "MANUAL"}]})
        body = r.get_json()
        assert len(body["warnings"]) == 1
        assert body["warnings"][0]["data_id"] == did

    def test_empty_outputs_payload_saves_nothing(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/save/{carto['a']}", json={})
        assert r.status_code == 200
        assert r.get_json()["saved"] == 0
