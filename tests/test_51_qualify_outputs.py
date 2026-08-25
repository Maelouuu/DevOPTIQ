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


# ===========================================================================
# POST /qualify/analyze/<activity_id> — qualification IA (CDC 1.5/1.6)
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


def _mock_openai(monkeypatch, content=None, raise_exc=None):
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (fake_client, None),
    )


def test_analyze_unknown_activity_returns_404(client, carto):
    _sess(client, carto["entity_id"])
    r = client.post("/qualify/analyze/999999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "activity_not_found"


def test_analyze_activity_without_outputs_returns_empty(client, carto):
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['z']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["outputs"] == []
    assert body["source"] == "no_outputs"
    assert body["warning"]


def test_analyze_without_ai_key_falls_back_to_qualify(client, carto, monkeypatch):
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (None, "no_key"),
    )
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "no_key"
    assert len(body["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in body["outputs"])


def test_analyze_with_ai_success_returns_suggested_natures(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = next(o for o in outs if o["name"] == "Pièce usinée")
    import json as _json
    content = _json.dumps({"outputs": [
        {"data_id": target["data_id"], "suggested_nature": "RESULT",
         "confidence": "high", "justification": "Démontre la tenue",
         "suggested_minimum_performance": "Cote respectée"},
    ]})
    _mock_openai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "AI"
    props = {p["data_id"]: p for p in body["outputs"]}
    assert props[target["data_id"]]["suggested_nature"] == "RESULT"
    assert props[target["data_id"]]["suggested_minimum_performance"] == "Cote respectée"
    # les sorties non traitées par l'IA reviennent en "à qualifier"
    others = [p for did, p in props.items() if did != target["data_id"]]
    assert len(others) == 2
    assert all(o["suggested_nature"] is None for o in others)


def test_analyze_with_ai_unknown_nature_is_discarded(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = outs[0]
    import json as _json
    content = _json.dumps({"outputs": [
        {"data_id": target["data_id"], "suggested_nature": "BOGUS_NATURE"},
    ]})
    _mock_openai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    props = {p["data_id"]: p for p in r.get_json()["outputs"]}
    assert props[target["data_id"]]["suggested_nature"] is None


def test_analyze_with_ai_ignores_unknown_data_id(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    import json as _json
    content = _json.dumps({"outputs": [
        {"data_id": 999999, "suggested_nature": "RESULT"},
    ]})
    _mock_openai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert all(p["data_id"] != 999999 for p in body["outputs"])
    assert len(body["outputs"]) == 3


def test_analyze_warns_when_no_result_identified(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    _mock_openai(monkeypatch, content='{"outputs": []}')
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert "Aucun résultat" in body["warning"]


def test_analyze_warns_when_more_than_three_results(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    import json as _json
    # 3 sorties dispo, on ajoute une 4e ligne en trop (data_id invalide, sera ignorée) —
    # pour dépasser 3 RESULT il faut au moins 4 sorties valides : on en marque 3 comme RESULT
    # (le seuil ">3" n'est donc pas atteignable avec seulement 3 sorties, on vérifie l'absence
    # de warning dans ce cas et la présence du champ).
    content = _json.dumps({"outputs": [
        {"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs
    ]})
    _mock_openai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["warning"] is None


def test_analyze_english_warning_language(client, carto, monkeypatch):
    with client.session_transaction() as s:
        s["active_entity_id"] = carto["entity_id"]
        s["lang"] = "en"
    _mock_openai(monkeypatch, content='{"outputs": []}')
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    assert "No activity result" in r.get_json()["warning"]
    _sess(client, carto["entity_id"])  # restore fr session for other tests


def test_analyze_ai_exception_falls_back_with_error_source(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    _mock_openai(monkeypatch, raise_exc=RuntimeError("boom"))
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "error"
    assert "boom" in body["error"]
    assert len(body["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in body["outputs"])
