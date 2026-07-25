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


@pytest.fixture()
def carto4(app):
    """Entité dédiée : activité avec 4 connexions sortantes libellées (pour tester le seuil
    « plus de trois résultats » de /qualify/analyze). Nettoyage complet après le test."""
    with app.app_context():
        ent = Entity(name="QualifOutEco4")
        db.session.add(ent); db.session.flush()
        a = Activities(entity_id=ent.id, name="Produire", shape_id="qo4_s1")
        b = Activities(entity_id=ent.id, name="Réceptionner", shape_id="qo4_s2")
        db.session.add_all([a, b]); db.session.flush()
        links = [
            Link(entity_id=ent.id, source_activity_id=a.id, target_activity_id=b.id,
                 type="flux", description=f"Sortie {i}")
            for i in range(1, 5)
        ]
        db.session.add_all(links); db.session.commit()
        ids = {"entity_id": ent.id, "a": a.id}
    yield ids
    with app.app_context():
        Data.query.filter_by(producer_activity_id=ids["a"]).delete()
        Link.query.filter(Link.source_activity_id == ids["a"]).delete(synchronize_session=False)
        Activities.query.filter(Activities.id == ids["a"]).delete(synchronize_session=False)
        Entity.query.filter_by(id=ids["entity_id"]).delete()
        db.session.commit()


def _sess(client, entity_id):
    with client.session_transaction() as s:
        s["active_entity_id"] = entity_id
        s["lang"] = "fr"


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


def _mock_openai(monkeypatch, content=None, raise_exc=None):
    """Patche openai_client_or_none() importé dans qualify_outputs pour renvoyer un faux client."""
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (fake_client, None),
    )


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


class TestAnalyze:
    """POST /qualify/analyze/<activity_id> — qualification IA des sorties (non persistante)."""

    def test_unknown_activity_returns_404(self, client):
        r = client.post("/qualify/analyze/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_no_outputs_returns_source_no_outputs_with_warning(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['z']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["outputs"] == []
        assert body["source"] == "no_outputs"
        assert body["warning"]

    def test_no_ai_key_returns_fallback_proposals(self, client, carto, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert "Clé OpenAI" in body["source"]
        assert len(body["outputs"]) == 3
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_ai_success_parses_valid_outputs(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Pièce usinée")
        payload = json.dumps({"outputs": [
            {"data_id": target["data_id"], "suggested_nature": "RESULT",
             "confidence": "high", "justification": "Démontre la tenue",
             "suggested_minimum_performance": "Cote conforme"},
        ]})
        _mock_openai(monkeypatch, content=payload)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "AI"
        result = next(p for p in body["outputs"] if p["data_id"] == target["data_id"])
        assert result["suggested_nature"] == "RESULT"
        assert result["suggested_minimum_performance"] == "Cote conforme"
        # les 2 autres sorties non traitées par l'IA reçoivent une proposition « à qualifier »
        others = [p for p in body["outputs"] if p["data_id"] != target["data_id"]]
        assert len(others) == 2
        assert all(p["suggested_nature"] is None for p in others)

    def test_ai_returns_unknown_data_id_is_filtered_out(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        payload = json.dumps({"outputs": [
            {"data_id": 9999999, "suggested_nature": "RESULT", "confidence": "high"},
        ]})
        _mock_openai(monkeypatch, content=payload)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert all(p["data_id"] != 9999999 for p in body["outputs"])
        assert len(body["outputs"]) == 3
        assert all(p["suggested_nature"] is None for p in body["outputs"])

    def test_ai_returns_invalid_nature_becomes_none(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = outs[0]
        payload = json.dumps({"outputs": [
            {"data_id": target["data_id"], "suggested_nature": "NOT_A_VALID_NATURE"},
        ]})
        _mock_openai(monkeypatch, content=payload)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        result = next(p for p in body["outputs"] if p["data_id"] == target["data_id"])
        assert result["suggested_nature"] is None

    def test_zero_result_gives_warning(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        payload = json.dumps({"outputs": []})
        _mock_openai(monkeypatch, content=payload)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert body["warning"]

    def test_between_one_and_three_results_no_warning(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        payload = json.dumps({"outputs": [
            {"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs
        ]})
        _mock_openai(monkeypatch, content=payload)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert body["warning"] is None

    def test_more_than_three_results_gives_warning(self, client, carto4, monkeypatch):
        _sess(client, carto4["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto4['a']}").get_json()["outputs"]
        assert len(outs) == 4
        payload = json.dumps({"outputs": [
            {"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs
        ]})
        _mock_openai(monkeypatch, content=payload)
        r = client.post(f"/qualify/analyze/{carto4['a']}")
        body = r.get_json()
        assert body["warning"]

    def test_ai_exception_falls_back_with_source_error(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_openai(monkeypatch, raise_exc=RuntimeError("boom"))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "error"
        assert "boom" in body["error"]
        assert len(body["outputs"]) == 3
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_ai_success_response_content_type_is_json(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        payload = json.dumps({"outputs": []})
        _mock_openai(monkeypatch, content=payload)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.content_type.startswith("application/json")
