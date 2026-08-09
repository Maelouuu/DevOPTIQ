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


# ---------------------------------------------------------------------------
# Fake client IA — simule le SDK (chat.completions.create) sans appel réseau
# réel, pour couvrir les branches "avec IA" (succès + exception) de /analyze.
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


class _FakeAIClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_ai(monkeypatch, content=None, raise_exc=None):
    """Patche openai_client_or_none() importé dans qualify_outputs pour renvoyer un faux client."""
    fake_client = _FakeAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (fake_client, None),
    )


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
# POST /qualify/analyze/<activity_id>
# ---------------------------------------------------------------------------

def test_analyze_unknown_activity_returns_404(client):
    r = client.post("/qualify/analyze/999999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "activity_not_found"


def test_analyze_no_outputs_returns_warning_and_empty_list(client, carto):
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['z']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["outputs"] == []
    assert body["source"] == "no_outputs"
    assert body["warning"]


def test_analyze_without_ai_key_returns_fallback_to_qualify(client, carto):
    """Sans clé IA configurée (environnement de test), analyze() renvoie le repli
    « à qualifier » (CDC §8 : ne jamais inventer de nature)."""
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] != "AI"
    assert len(body["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in body["outputs"])


def test_analyze_with_ai_success_classifies_result(app, client, monkeypatch, carto):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = next(o for o in outs if o["name"] == "Pièce usinée")
    content = json.dumps({"outputs": [
        {"data_id": target["data_id"], "suggested_nature": "RESULT",
         "confidence": "high", "justification": "Démontre la tenue",
         "suggested_minimum_performance": "Cote respectée"},
    ]})
    _mock_ai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "AI"
    proposal = next(p for p in body["outputs"] if p["data_id"] == target["data_id"])
    assert proposal["suggested_nature"] == "RESULT"
    assert proposal["suggested_minimum_performance"] == "Cote respectée"
    # les sorties non traitées par l'IA sont complétées par le repli « à qualifier »
    others = [p for p in body["outputs"] if p["data_id"] != target["data_id"]]
    assert len(others) == 2
    assert all(o["suggested_nature"] is None for o in others)


def test_analyze_ignores_data_id_outside_activity(app, client, monkeypatch, carto):
    """Un data_id renvoyé par l'IA mais n'appartenant pas aux sorties de l'activité
    doit être ignoré (pas d'injection de qualification hors périmètre)."""
    _sess(client, carto["entity_id"])
    content = json.dumps({"outputs": [{"data_id": 999999, "suggested_nature": "RESULT"}]})
    _mock_ai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    body = r.get_json()
    assert body["source"] == "AI"
    assert all(p["data_id"] != 999999 for p in body["outputs"])
    assert len(body["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in body["outputs"])


def test_analyze_invalid_nature_from_ai_becomes_none(app, client, monkeypatch, carto):
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = outs[0]
    content = json.dumps({"outputs": [
        {"data_id": target["data_id"], "suggested_nature": "NOT_A_VALID_CODE"},
    ]})
    _mock_ai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    body = r.get_json()
    proposal = next(p for p in body["outputs"] if p["data_id"] == target["data_id"])
    assert proposal["suggested_nature"] is None


def test_analyze_warns_when_no_result_identified(app, client, monkeypatch, carto):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    content = json.dumps({"outputs": [
        {"data_id": outs[0]["data_id"], "suggested_nature": "INFORMATION", "confidence": "low"},
    ]})
    _mock_ai(monkeypatch, content=content)
    r = client.post(f"/qualify/analyze/{carto['a']}")
    body = r.get_json()
    assert body["warning"] is not None
    assert "résultat" in body["warning"].lower()


def test_analyze_warns_when_more_than_three_results(app, client, monkeypatch, carto):
    """> 3 résultats identifiés : avertissement invitant à revoir la granularité."""
    _sess(client, carto["entity_id"])
    with app.app_context():
        extra = Activities(entity_id=carto["entity_id"], name="Destination Extra", shape_id="qo_extra")
        db.session.add(extra)
        db.session.flush()
        db.session.add(Link(entity_id=carto["entity_id"], source_activity_id=carto["a"],
                             target_activity_id=extra.id, type="flux", description="Sortie 4"))
        db.session.commit()
        extra_id = extra.id
    try:
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        assert len(outs) == 4
        content = json.dumps({"outputs": [
            {"data_id": o["data_id"], "suggested_nature": "RESULT", "confidence": "high"} for o in outs
        ]})
        _mock_ai(monkeypatch, content=content)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert body["warning"] is not None
        assert "trois" in body["warning"].lower()
    finally:
        with app.app_context():
            Link.query.filter_by(source_activity_id=carto["a"], description="Sortie 4").delete()
            Data.query.filter_by(producer_activity_id=carto["a"], name="Sortie 4").delete()
            Activities.query.filter_by(id=extra_id).delete()
            db.session.commit()


def test_analyze_ai_exception_falls_back_with_error_source(app, client, monkeypatch, carto):
    _sess(client, carto["entity_id"])
    _mock_ai(monkeypatch, raise_exc=RuntimeError("boom"))
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "error"
    assert "boom" in body["error"]
    assert len(body["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in body["outputs"])


def test_analyze_english_lang_no_ai_warning_text(app, carto):
    """Client isolé (non partagé) : ne pas polluer la session du client global partagé
    entre tous les tests avec lang=en."""
    fresh = app.test_client()
    with fresh.session_transaction() as s:
        s["active_entity_id"] = carto["entity_id"]
        s["lang"] = "en"
    r = fresh.post(f"/qualify/analyze/{carto['z']}")
    body = r.get_json()
    assert body["warning"] == "This activity has no output data."
