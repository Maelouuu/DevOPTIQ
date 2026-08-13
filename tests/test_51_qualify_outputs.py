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
# GET /qualify/outputs/<id> — activité inconnue
# ===========================================================================

def test_outputs_unknown_activity_returns_404(client):
    r = client.get("/qualify/outputs/999999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "activity_not_found"


# ===========================================================================
# _current_output_specs — branche legacy target_data_id + nom vide + doublon
# ===========================================================================

def test_output_spec_falls_back_to_target_data_name(app, client, carto):
    """Connexion sortante sans description et sans target_activity_id, mais avec
    target_data_id → le nom de la Data cible est utilisé (branche legacy)."""
    with app.app_context():
        d = Data(entity_id=carto["entity_id"], name="Rapport qualité", type="information")
        db.session.add(d); db.session.flush()
        lk = Link(entity_id=carto["entity_id"], source_activity_id=carto["z"],
                   target_data_id=d.id, type="information", description=None)
        db.session.add(lk); db.session.commit()
        data_id, link_id = d.id, lk.id
    _sess(client, carto["entity_id"])
    try:
        r = client.get(f"/qualify/outputs/{carto['z']}")
        assert r.status_code == 200
        names = {o["name"] for o in r.get_json()["outputs"]}
        assert "Rapport qualité" in names
    finally:
        with app.app_context():
            Data.query.filter_by(producer_activity_id=carto["z"]).delete()
            Link.query.filter_by(id=link_id).delete()
            Data.query.filter_by(id=data_id).delete()
            db.session.commit()


def test_output_spec_skips_link_with_no_resolvable_name(app, client, carto):
    """Connexion sans description, sans target_activity_id ni target_data_id → ignorée
    (aucun nom résolvable), ne casse pas la liste des sorties."""
    with app.app_context():
        lk = Link(entity_id=carto["entity_id"], source_activity_id=carto["z"],
                   type="flux", description=None)
        db.session.add(lk); db.session.commit()
        link_id = lk.id
    _sess(client, carto["entity_id"])
    try:
        r = client.get(f"/qualify/outputs/{carto['z']}")
        assert r.status_code == 200
        assert r.get_json()["outputs"] == []
    finally:
        with app.app_context():
            Link.query.filter_by(id=link_id).delete()
            db.session.commit()


# ===========================================================================
# POST /qualify/analyze/<id> — qualification IA
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


def _mock_qualify_client(monkeypatch, content=None, raise_exc=None):
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (fake_client, None),
    )


def test_analyze_unknown_activity_returns_404(client):
    r = client.post("/qualify/analyze/999999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "activity_not_found"


def test_analyze_no_outputs_returns_warning(client, carto):
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['z']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["outputs"] == []
    assert body["source"] == "no_outputs"
    assert "aucune donnée" in body["warning"].lower()


def test_analyze_without_ai_client_returns_fallback(client, carto, monkeypatch):
    """Pas de client IA dispo → fallback « à qualifier », jamais d'invention de nature."""
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (None, "Clé IA non renseignée"),
    )
    _sess(client, carto["entity_id"])
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "Clé IA non renseignée"
    assert len(body["outputs"]) == 3
    assert all(o["suggested_nature"] is None for o in body["outputs"])


def test_analyze_success_with_fake_client(client, carto, monkeypatch):
    """Client IA dispo + réponse JSON valide → propositions avec nature suggérée."""
    outs = client.get(f"/qualify/outputs/{carto['a']}")  # matérialise les Data
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = next(o for o in outs if o["name"] == "Pièce usinée")

    import json as json_module
    _mock_qualify_client(monkeypatch, content=json_module.dumps({
        "outputs": [
            {"data_id": target["data_id"], "suggested_nature": "RESULT",
             "confidence": "high", "justification": "Démontre la tenue de l'activité",
             "suggested_minimum_performance": "Cote respectée"},
            {"data_id": 9999999, "suggested_nature": "RESULT"},  # id inconnu → ignoré
        ]
    }))
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "AI"
    props = {p["data_id"]: p for p in body["outputs"]}
    assert props[target["data_id"]]["suggested_nature"] == "RESULT"
    # les 2 autres sorties non traitées par l'IA → fallback "à qualifier"
    others = [p for did, p in props.items() if did != target["data_id"]]
    assert all(p["suggested_nature"] is None for p in others)
    # un seul RESULT identifié → pas d'avertissement
    assert body["warning"] is None


def test_analyze_no_result_identified_gives_warning(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    client.get(f"/qualify/outputs/{carto['a']}")

    import json as json_module
    _mock_qualify_client(monkeypatch, content=json_module.dumps({"outputs": []}))
    r = client.post(f"/qualify/analyze/{carto['a']}")
    body = r.get_json()
    assert body["source"] == "AI"
    assert "Aucun résultat" in body["warning"]


def test_analyze_too_many_results_gives_warning(app, client, carto, monkeypatch):
    """Plus de 3 sorties qualifiées RESULT → avertissement de granularité."""
    with app.app_context():
        extra = Link(entity_id=carto["entity_id"], source_activity_id=carto["a"],
                      target_activity_id=carto["b"], type="flux", description="Rapport final")
        db.session.add(extra); db.session.commit()
        extra_id = extra.id

    _sess(client, carto["entity_id"])
    try:
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        assert len(outs) == 4

        import json as json_module
        _mock_qualify_client(monkeypatch, content=json_module.dumps({
            "outputs": [
                {"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs
            ]
        }))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert "granularité" in body["warning"]
    finally:
        with app.app_context():
            Link.query.filter_by(id=extra_id).delete()
            Data.query.filter_by(producer_activity_id=carto["a"], name="Rapport final").delete()
            db.session.commit()


def test_analyze_invalid_nature_from_ai_is_discarded(client, carto, monkeypatch):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = outs[0]

    import json as json_module
    _mock_qualify_client(monkeypatch, content=json_module.dumps({
        "outputs": [{"data_id": target["data_id"], "suggested_nature": "NOT_A_REAL_CODE"}]
    }))
    r = client.post(f"/qualify/analyze/{carto['a']}")
    body = r.get_json()
    prop = next(p for p in body["outputs"] if p["data_id"] == target["data_id"])
    assert prop["suggested_nature"] is None


def test_analyze_ai_exception_falls_back_gracefully(client, carto, monkeypatch):
    """Le client IA lève une exception → 200 + fallback (jamais d'erreur 500 exposée)."""
    _sess(client, carto["entity_id"])
    client.get(f"/qualify/outputs/{carto['a']}")
    _mock_qualify_client(monkeypatch, raise_exc=RuntimeError("Timeout IA"))
    r = client.post(f"/qualify/analyze/{carto['a']}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["source"] == "error"
    assert "Timeout IA" in body["error"]
    assert len(body["outputs"]) == 3


# ===========================================================================
# POST /qualify/save/<id> — cas limites
# ===========================================================================

def test_save_unknown_activity_returns_404(client):
    r = client.post("/qualify/save/999999", json={"outputs": []})
    assert r.status_code == 404
    assert r.get_json()["error"] == "activity_not_found"


def test_save_ignores_unknown_data_id(client, carto):
    _sess(client, carto["entity_id"])
    client.get(f"/qualify/outputs/{carto['a']}")
    r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
        {"data_id": 9999999, "nature": "RESULT"}]})
    assert r.status_code == 200
    assert r.get_json()["saved"] == 0


def test_save_invalid_nature_is_stored_as_null(app, client, carto):
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = outs[0]
    r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
        {"data_id": target["data_id"], "nature": "NOT_A_REAL_CODE"}]})
    assert r.status_code == 200
    assert r.get_json()["saved"] == 1
    with app.app_context():
        d = Data.query.get(target["data_id"])
        assert d.semantic_nature is None


def test_save_downgrading_result_returns_warning(app, client, carto):
    """Requalifier une sortie déjà RESULT vers autre chose → avertissement non bloquant."""
    _sess(client, carto["entity_id"])
    outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
    target = outs[0]
    client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
        {"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]})
    r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
        {"data_id": target["data_id"], "nature": "MEASURE", "source": "MANUAL"}]})
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["warnings"]) == 1
    assert body["warnings"][0]["data_id"] == target["data_id"]
    with app.app_context():
        d = Data.query.get(target["data_id"])
        assert d.semantic_nature == "MEASURE"
