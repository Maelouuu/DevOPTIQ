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
# Faux client IA (voir tests/test_22_propose_ia.py pour le pattern complet)
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
        self.chat = _FakeChat(content, raise_exc)


def _mock_ai(monkeypatch, content=None, raise_exc=None):
    """Patche openai_client_or_none() importé dans qualify_outputs."""
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.qualify_outputs.openai_client_or_none",
        lambda: (fake_client, None),
    )


class TestNotFound:

    def test_outputs_unknown_activity_404(self, client):
        r = client.get("/qualify/outputs/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_analyze_unknown_activity_404(self, client):
        r = client.post("/qualify/analyze/999999")
        assert r.status_code == 404

    def test_save_unknown_activity_404(self, client):
        r = client.post("/qualify/save/999999", json={"outputs": []})
        assert r.status_code == 404


class TestAnalyzeNoOutputs:

    def test_analyze_activity_without_outputs(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['z']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["outputs"] == []
        assert body["source"] == "no_outputs"
        assert body["warning"]


class TestAnalyzeWithoutAI:

    def test_analyze_falls_back_when_no_ai_key(self, client, carto):
        """Sans clé IA (environnement de test) : repli « à qualifier », jamais de nature inventée."""
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"]
        assert len(body["outputs"]) == 3
        assert all(o["suggested_nature"] is None for o in body["outputs"])


class TestAnalyzeWithAI:

    def test_analyze_ai_success_parses_and_flags_result(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Pièce usinée")
        content = json.dumps({"outputs": [
            {"data_id": target["data_id"], "suggested_nature": "RESULT",
             "confidence": "high", "justification": "démontre la tenue",
             "suggested_minimum_performance": "Cote conforme"},
        ]})
        _mock_ai(monkeypatch, content=content)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "AI"
        props = {p["data_id"]: p for p in body["outputs"]}
        assert props[target["data_id"]]["suggested_nature"] == "RESULT"
        assert props[target["data_id"]]["suggested_minimum_performance"] == "Cote conforme"
        others = [p for did, p in props.items() if did != target["data_id"]]
        assert len(others) == 2
        assert all(o["suggested_nature"] is None for o in others)   # non traitées par l'IA
        assert body["warning"] is None                              # exactement 1 RESULT → pas d'alerte

    def test_analyze_ai_zero_results_warns(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_ai(monkeypatch, content=json.dumps({"outputs": []}))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert body["warning"] and "Aucun résultat" in body["warning"]

    def test_analyze_ai_more_than_three_results_warns(self, app, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        with app.app_context():
            lk = Link(entity_id=carto["entity_id"], source_activity_id=carto["a"],
                      target_activity_id=carto["b"], type="flux", description="Rapport final")
            db.session.add(lk)
            db.session.commit()
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        assert len(outs) == 4
        content = json.dumps({"outputs": [
            {"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs
        ]})
        _mock_ai(monkeypatch, content=content)
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert body["warning"] and "trois" in body["warning"].lower()

    def test_analyze_ai_ignores_unknown_data_id(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_ai(monkeypatch, content=json.dumps(
            {"outputs": [{"data_id": 999999, "suggested_nature": "RESULT"}]}))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert len(body["outputs"]) == 3
        assert all(p["data_id"] != 999999 for p in body["outputs"])

    def test_analyze_ai_invalid_nature_becomes_none(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = outs[0]
        _mock_ai(monkeypatch, content=json.dumps(
            {"outputs": [{"data_id": target["data_id"], "suggested_nature": "BOGUS"}]}))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        prop = next(p for p in r.get_json()["outputs"] if p["data_id"] == target["data_id"])
        assert prop["suggested_nature"] is None

    def test_analyze_ai_exception_falls_back(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_ai(monkeypatch, raise_exc=RuntimeError("boom"))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "error"
        assert "boom" in body["error"]
        assert len(body["outputs"]) == 3


class TestSaveEdgeCases:

    def test_save_ignores_unknown_data_id(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": 999999, "nature": "RESULT"}]})
        assert r.status_code == 200
        assert r.get_json()["saved"] == 0

    def test_save_invalid_nature_stored_as_none(self, app, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = outs[0]
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "BOGUS"}]})
        assert r.status_code == 200
        with app.app_context():
            d = Data.query.get(target["data_id"])
            assert d.semantic_nature is None
            assert d.qualification_source is None

    def test_save_ai_source_when_not_manual(self, app, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = outs[0]
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "EVENT"}]})
        assert r.status_code == 200
        with app.app_context():
            d = Data.query.get(target["data_id"])
            assert d.qualification_source == "AI"

    def test_save_requalifying_result_returns_warning(self, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = outs[0]
        client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]})
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "MEASURE", "source": "MANUAL"}]})
        body = r.get_json()
        assert body["warnings"] and body["warnings"][0]["data_id"] == target["data_id"]

    def test_save_no_longer_result_but_still_result_no_warning(self, client, carto):
        """Re-sauvegarder un RESULT en RESULT ne doit pas déclencher l'avertissement."""
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = outs[0]
        client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]})
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]})
        assert r.get_json()["warnings"] == []


class TestLegacyDataLinks:
    """Compat héritage (CDC 1) : sorties ciblées explicitement par Link.target_data_id."""

    def test_legacy_target_data_link_included_in_outputs(self, app, client):
        with app.app_context():
            ent = Entity(name="QualifLegacyECo")
            db.session.add(ent); db.session.flush()
            a = Activities(entity_id=ent.id, name="Produire le rapport", shape_id="qo_legacy_a")
            d = Data(entity_id=ent.id, name="Rapport PDF", type="document")
            db.session.add_all([a, d]); db.session.flush()
            lk = Link(entity_id=ent.id, source_activity_id=a.id, target_data_id=d.id, type="flux")
            db.session.add(lk); db.session.commit()
            ids = {"entity_id": ent.id, "a": a.id, "data_id": d.id}
        _sess(client, ids["entity_id"])
        try:
            r = client.get(f"/qualify/outputs/{ids['a']}")
            assert r.status_code == 200
            outs = r.get_json()["outputs"]
            # matérialisée (via _current_output_specs, nom repris du Data ciblé) + héritage
            # (Link.target_data_id explicite, non déjà vu) → les deux apparaissent.
            names = [o["name"] for o in outs]
            assert names.count("Rapport PDF") == 2
        finally:
            with app.app_context():
                Data.query.filter_by(producer_activity_id=ids["a"]).delete()
                Link.query.filter_by(source_activity_id=ids["a"]).delete()
                Data.query.filter_by(id=ids["data_id"]).delete()
                Activities.query.filter_by(id=ids["a"]).delete()
                Entity.query.filter_by(id=ids["entity_id"]).delete()
                db.session.commit()


class TestCurrentOutputSpecsInternals:
    """Fonctions internes non exposées en HTTP : dédoublonnage et repli sans activité."""

    def test_dedup_and_empty_name_links_are_skipped(self, app):
        from Code.routes.qualify_outputs import _current_output_specs

        with app.app_context():
            ent = Entity(name="QualifDedupECo")
            db.session.add(ent); db.session.flush()
            a = Activities(entity_id=ent.id, name="A", shape_id="qo_dedup_a")
            db.session.add(a); db.session.flush()
            links = [
                Link(entity_id=ent.id, source_activity_id=a.id, type="flux", description="Sortie X"),
                Link(entity_id=ent.id, source_activity_id=a.id, type="flux", description="Sortie X"),
                Link(entity_id=ent.id, source_activity_id=a.id, type="flux", description=None),
            ]
            db.session.add_all(links); db.session.commit()
            try:
                assert _current_output_specs(a) == [("Sortie X", "flux")]
            finally:
                Link.query.filter_by(source_activity_id=a.id).delete()
                Activities.query.filter_by(id=a.id).delete()
                Entity.query.filter_by(id=ent.id).delete()
                db.session.commit()

    def test_materialize_outputs_unknown_activity_returns_empty(self, app):
        from Code.routes.qualify_outputs import materialize_activity_outputs

        with app.app_context():
            assert materialize_activity_outputs(999999) == []
