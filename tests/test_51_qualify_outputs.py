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
from Code.routes.qualify_outputs import materialize_activity_outputs


# ---------------------------------------------------------------------------
# Fake client IA (même patron que test_22_propose_ia.py) pour couvrir la
# branche "avec client IA" de analyze() sans appel réseau réel.
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


def test_outputs_unknown_activity_returns_404(client):
    r = client.get("/qualify/outputs/999999")
    assert r.status_code == 404
    assert r.get_json()["error"] == "activity_not_found"


def test_materialize_unknown_activity_returns_empty_list(app):
    with app.app_context():
        assert materialize_activity_outputs(999999) == []


@pytest.fixture()
def carto_edge(app):
    """Entité dédiée aux cas limites de résolution de nom :
    - connexion sans description ni destinataire résolvable → ignorée (nom vide)
    - deux connexions résolvant au même nom → dédupliquées
    - connexion ciblant directement une Data (target_data_id) sans libellé → nom = Data.name,
      et la Data brute ciblée est incluse en plus par compat héritage (id différent du matérialisé)."""
    with app.app_context():
        ent = Entity(name="QualifOutEdgeECo")
        db.session.add(ent); db.session.flush()
        a = Activities(entity_id=ent.id, name="Activité Edge", shape_id="qo_edge_s1")
        b = Activities(entity_id=ent.id, name="Cible B", shape_id="qo_edge_s2")
        db.session.add_all([a, b]); db.session.flush()
        raw_data = Data(entity_id=ent.id, name="Rapport brut", type="flux")
        db.session.add(raw_data); db.session.flush()
        links = [
            # nom vide : ni description, ni target_activity_id, ni target_data_id → ignorée
            Link(entity_id=ent.id, source_activity_id=a.id, type="flux", description=None),
            # deux connexions avec le même libellé → dédupliquées à une seule sortie
            Link(entity_id=ent.id, source_activity_id=a.id, target_activity_id=b.id,
                 type="flux", description="Compte-rendu"),
            Link(entity_id=ent.id, source_activity_id=a.id, target_activity_id=b.id,
                 type="flux", description="Compte-rendu"),
            # cible une Data existante directement, sans libellé → nom = Data.name (compat héritage)
            Link(entity_id=ent.id, source_activity_id=a.id, target_data_id=raw_data.id,
                 type="flux", description=None),
        ]
        db.session.add_all(links); db.session.commit()
        ids = {"entity_id": ent.id, "a": a.id, "b": b.id, "raw_data": raw_data.id}
    yield ids
    with app.app_context():
        Data.query.filter(
            (Data.producer_activity_id == ids["a"]) | (Data.id == ids["raw_data"])
        ).delete(synchronize_session=False)
        Link.query.filter(Link.source_activity_id.in_([ids["a"], ids["b"]])).delete(
            synchronize_session=False)
        Activities.query.filter(Activities.id.in_([ids["a"], ids["b"]])).delete(
            synchronize_session=False)
        Entity.query.filter_by(id=ids["entity_id"]).delete()
        db.session.commit()


class TestOutputNameResolutionEdgeCases:
    def test_connection_without_resolvable_name_is_skipped(self, client, carto_edge):
        _sess(client, carto_edge["entity_id"])
        names = {o["name"] for o in client.get(f"/qualify/outputs/{carto_edge['a']}").get_json()["outputs"]}
        assert "" not in names

    def test_duplicate_names_are_deduplicated(self, client, carto_edge):
        _sess(client, carto_edge["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto_edge['a']}").get_json()["outputs"]
        comptes_rendus = [o for o in outs if o["name"] == "Compte-rendu"]
        assert len(comptes_rendus) == 1

    def test_target_data_id_without_label_uses_data_name(self, client, carto_edge):
        _sess(client, carto_edge["entity_id"])
        names = {o["name"] for o in client.get(f"/qualify/outputs/{carto_edge['a']}").get_json()["outputs"]}
        assert "Rapport brut" in names

    def test_target_data_id_legacy_compat_includes_raw_data(self, client, carto_edge):
        """La Data brute directement ciblée par target_data_id est incluse en plus de sa
        version matérialisée (compat héritage, cf. get_activity_outputs)."""
        _sess(client, carto_edge["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto_edge['a']}").get_json()["outputs"]
        ids = {o["data_id"] for o in outs}
        assert carto_edge["raw_data"] in ids


class TestAnalyzeRoute:
    def test_unknown_activity_returns_404(self, client):
        r = client.post("/qualify/analyze/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_activity_without_outputs_returns_no_outputs_source(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['z']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["outputs"] == []
        assert body["source"] == "no_outputs"
        assert "warning" in body

    def test_without_ai_key_returns_fallback_to_qualify(self, client, carto):
        """Sans clé IA (environnement de test par défaut) : repli « à qualifier », jamais de nature inventée."""
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] != "AI"
        assert len(body["outputs"]) == 3
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_ai_success_parses_valid_proposals_and_filters_invalid(self, app, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        piece = next(o for o in outs if o["name"] == "Pièce usinée")
        fiche = next(o for o in outs if o["name"] == "Fiche suiveuse")
        ai_payload = {
            "outputs": [
                {"data_id": piece["data_id"], "suggested_nature": "RESULT",
                 "confidence": "high", "justification": "Pièce conforme au plan.",
                 "suggested_minimum_performance": "Cote respectée"},
                # nature invalide → doit être neutralisée en None
                {"data_id": fiche["data_id"], "suggested_nature": "BOGUS_NATURE"},
                # data_id hors périmètre de l'activité → ignoré silencieusement
                {"data_id": 999999, "suggested_nature": "RESULT"},
            ]
        }
        _mock_ai(monkeypatch, content=json.dumps(ai_payload))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "AI"
        by_id = {p["data_id"]: p for p in body["outputs"]}
        assert by_id[piece["data_id"]]["suggested_nature"] == "RESULT"
        assert by_id[piece["data_id"]]["suggested_minimum_performance"] == "Cote respectée"
        assert by_id[fiche["data_id"]]["suggested_nature"] is None
        assert 999999 not in by_id
        # 3e sortie ("Contrôle qualité") non traitée par l'IA → repli "à qualifier"
        controle = next(o for o in outs if o["name"] == "Contrôle qualité")
        assert by_id[controle["data_id"]]["suggested_nature"] is None
        assert body["warning"] is None  # exactement 1 RESULT → pas d'avertissement

    def test_ai_zero_results_returns_warning(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_ai(monkeypatch, content=json.dumps({"outputs": []}))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert r.status_code == 200
        assert body["warning"] is not None
        assert "Aucun résultat" in body["warning"]

    def test_ai_more_than_three_results_returns_warning(self, app, client, carto, monkeypatch):
        """Les Links/Data créés ici vivent sur l'activité 'a' du fixture carto, dont le
        teardown purge déjà tout Link/Data rattaché — pas de nettoyage dédié nécessaire."""
        _sess(client, carto["entity_id"])
        with app.app_context():
            db.session.add_all([
                Link(entity_id=carto["entity_id"], source_activity_id=carto["a"],
                     target_activity_id=carto["b"], type="flux", description="Sortie extra 1"),
                Link(entity_id=carto["entity_id"], source_activity_id=carto["a"],
                     target_activity_id=carto["b"], type="flux", description="Sortie extra 2"),
            ])
            db.session.commit()
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        assert len(outs) == 5
        ai_payload = {"outputs": [
            {"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs
        ]}
        _mock_ai(monkeypatch, content=json.dumps(ai_payload))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        body = r.get_json()
        assert r.status_code == 200
        assert body["warning"] is not None
        assert "trois" in body["warning"]

    def test_ai_exception_returns_fallback_with_error_source(self, client, carto, monkeypatch):
        _sess(client, carto["entity_id"])
        _mock_ai(monkeypatch, raise_exc=RuntimeError("boom"))
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "error"
        assert "error" in body
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_english_language_no_outputs_warning_is_translated(self, client, carto):
        with client.session_transaction() as s:
            s["active_entity_id"] = carto["entity_id"]
            s["lang"] = "en"
        r = client.post(f"/qualify/analyze/{carto['z']}")
        body = r.get_json()
        assert "no output data" in body["warning"]


class TestSaveRoute:
    def test_unknown_activity_returns_404(self, client):
        r = client.post("/qualify/save/999999", json={"outputs": []})
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_unknown_data_id_is_skipped(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": 999999, "nature": "RESULT"}]})
        assert r.status_code == 200
        assert r.get_json()["saved"] == 0

    def test_invalid_nature_is_stored_as_null(self, app, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Fiche suiveuse")
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "NOT_A_REAL_NATURE", "source": "MANUAL"}]})
        assert r.status_code == 200
        with app.app_context():
            d = Data.query.get(target["data_id"])
            assert d.semantic_nature is None

    def test_requalifying_a_result_returns_warning(self, app, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Contrôle qualité")
        client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]})
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "MEASURE", "source": "MANUAL"}]})
        body = r.get_json()
        assert r.status_code == 200
        assert len(body["warnings"]) == 1
        assert body["warnings"][0]["data_id"] == target["data_id"]
        with app.app_context():
            d = Data.query.get(target["data_id"])
            assert d.semantic_nature == "MEASURE"

    def test_ai_source_defaults_when_nature_present_without_explicit_source(self, app, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Pièce usinée")
        r = client.post(f"/qualify/save/{carto['a']}", json={"outputs": [
            {"data_id": target["data_id"], "nature": "EVENT"}]})
        assert r.status_code == 200
        with app.app_context():
            d = Data.query.get(target["data_id"])
            assert d.qualification_source == "AI"
