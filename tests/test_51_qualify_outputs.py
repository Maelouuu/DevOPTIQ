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


# ---------------------------------------------------------------------------
# POST /qualify/analyze/<activity_id> — Qualification IA (CDC 1.5/1.6)
# ---------------------------------------------------------------------------

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
        self.chat = _FakeChat(content=content, raise_exc=raise_exc)


def _mock_openai(monkeypatch, content=None, raise_exc=None):
    """Patche openai_client_or_none() importé dans qualify_outputs pour renvoyer un faux client."""
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (fake_client, None),
    )


def test_analyze_no_ai_key_returns_fallback_to_qualify(client, carto):
    """Sans clé IA (environnement de test par défaut), retourne 200 + propositions 'à qualifier'."""
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"] != "AI"
    assert len(data["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in data["outputs"])


def test_analyze_unknown_activity_returns_404(client, carto):
    _sess(client, carto["entity_id"])
    r = client.post("/qualify/analyze/999999")
    assert r.status_code == 404


def test_analyze_no_outputs_returns_warning(client, carto):
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['z']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"] == "no_outputs"
    assert data["outputs"] == []
    assert data["warning"]


def test_analyze_with_ai_success_parses_proposals(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    ids_by_name = {o["name"]: o["data_id"] for o in outs}
    content = json.dumps({"outputs": [
        {"data_id": ids_by_name["Pièce usinée"], "suggested_nature": "RESULT",
         "confidence": "high", "justification": "Démontre la tenue",
         "suggested_minimum_performance": "Cote respectée"},
    ]})
    _mock_openai(monkeypatch, content=content)

    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"] == "AI"
    props_by_id = {p["data_id"]: p for p in data["outputs"]}
    result_prop = props_by_id[ids_by_name["Pièce usinée"]]
    assert result_prop["suggested_nature"] == "RESULT"
    assert result_prop["suggested_minimum_performance"] == "Cote respectée"
    # les 2 autres sorties non traitées par l'IA retombent en "à qualifier"
    others = [p for p in data["outputs"] if p["data_id"] != ids_by_name["Pièce usinée"]]
    assert len(others) == 2
    assert all(p["suggested_nature"] is None for p in others)
    assert data["warning"] is None  # exactement 1 RESULT → pas d'alerte


def test_analyze_ai_unknown_data_id_is_ignored(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    content = json.dumps({"outputs": [
        {"data_id": 999999, "suggested_nature": "RESULT", "confidence": "high"},
    ]})
    _mock_openai(monkeypatch, content=content)

    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    data = r.get_json()
    assert all(p["data_id"] != 999999 for p in data["outputs"])
    assert len(data["outputs"]) == 3


def test_analyze_ai_invalid_nature_falls_back_to_none(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    did = outs[0]["data_id"]
    content = json.dumps({"outputs": [
        {"data_id": did, "suggested_nature": "NOT_A_REAL_NATURE", "confidence": "low"},
    ]})
    _mock_openai(monkeypatch, content=content)

    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    prop = next(p for p in r.get_json()["outputs"] if p["data_id"] == did)
    assert prop["suggested_nature"] is None


def test_analyze_no_result_identified_triggers_warning(client, carto, monkeypatch):
    """Aucune sortie qualifiée RESULT par l'IA → avertissement (CDC : compétence non fiable)."""
    _sess(client, carto["entity_id"])
    content = json.dumps({"outputs": []})
    _mock_openai(monkeypatch, content=content)

    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["warning"] is not None
    assert "résultat" in data["warning"].lower() or "result" in data["warning"].lower()


def test_analyze_more_than_three_results_triggers_warning(app, client, monkeypatch):
    """Plus de 3 RESULT identifiés → avertissement de granularité."""
    with app.app_context():
        ent = Entity(name="QualifOutECoMany")
        db.session.add(ent); db.session.flush()
        src = Activities(entity_id=ent.id, name="Source many", shape_id="qo_many_src")
        db.session.add(src); db.session.flush()
        links = []
        for i in range(4):
            dst = Activities(entity_id=ent.id, name=f"Dest {i}", shape_id=f"qo_many_dst_{i}")
            db.session.add(dst); db.session.flush()
            links.append(Link(entity_id=ent.id, source_activity_id=src.id, target_activity_id=dst.id,
                               type="flux", description=f"Sortie {i}"))
        db.session.add_all(links); db.session.commit()
        entity_id, activity_id = ent.id, src.id

    try:
        _sess(client, entity_id)
        outs = client.get(f"/qualify/outputs/{activity_id}").get_json()["outputs"]
        content = json.dumps({"outputs": [
            {"data_id": o["data_id"], "suggested_nature": "RESULT", "confidence": "high"}
            for o in outs
        ]})
        _mock_openai(monkeypatch, content=content)

        r = client.post(f"/qualify/analyze/{activity_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["warning"] is not None
        assert "trois" in data["warning"].lower() or "three" in data["warning"].lower()
    finally:
        with app.app_context():
            Data.query.filter_by(producer_activity_id=activity_id).delete()
            Link.query.filter_by(source_activity_id=activity_id).delete(synchronize_session=False)
            Activities.query.filter(Activities.entity_id == entity_id).delete(synchronize_session=False)
            Entity.query.filter_by(id=entity_id).delete()
            db.session.commit()


def test_analyze_ai_exception_falls_back_gracefully(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    _mock_openai(monkeypatch, raise_exc=RuntimeError("boom"))

    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"] == "error"
    assert len(data["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in data["outputs"])


def test_analyze_ai_invalid_json_falls_back_gracefully(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    _mock_openai(monkeypatch, content="ceci n'est pas du JSON")

    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["source"] == "error"
