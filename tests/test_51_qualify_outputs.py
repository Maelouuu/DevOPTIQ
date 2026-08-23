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


def _fake_client_returning(content):
    """Client IA factice : chat.completions.create(...) renvoie `content` comme message.content."""
    class _FakeMessage:
        pass

    class _FakeChoice:
        pass

    class _FakeResponse:
        pass

    class _FakeCompletions:
        def create(self, **kwargs):
            msg = _FakeMessage()
            msg.content = content
            choice = _FakeChoice()
            choice.message = msg
            resp = _FakeResponse()
            resp.choices = [choice]
            return resp

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    return _FakeClient()


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


class TestAnalyze:

    def test_unknown_activity_returns_404(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post("/qualify/analyze/999999")
        assert r.status_code == 404

    def test_no_outputs_returns_warning(self, client, carto):
        """Activité sans connexion sortante → source=no_outputs, pas d'appel IA."""
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['z']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["outputs"] == []
        assert body["source"] == "no_outputs"
        assert "warning" in body

    def test_no_ai_client_falls_back(self, client, carto, monkeypatch):
        """Pas de clé IA (make_ai_client renvoie client=None) → repli « à qualifier »."""
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (None, None, "Clé IA non renseignée."),
        )
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "Clé IA non renseignée."
        assert len(body["outputs"]) == 3
        assert all(o["suggested_nature"] is None for o in body["outputs"])

    def test_no_system_prompt_falls_back(self, client, carto, monkeypatch):
        """Client IA dispo mais prompts non chargés (get_prompt→None) → repli, source=no_ai."""
        import Code.routes.qualify_outputs as qo_module

        monkeypatch.setattr(qo_module, "get_prompt", lambda *a, **k: None)
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_returning("{}"), "fake-model", None),
        )
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        assert r.get_json()["source"] == "no_ai"

    def test_success_maps_valid_outputs_and_ignores_unknown_ids(self, client, carto, monkeypatch):
        """Réponse IA valide : filtre les data_id inconnus, invalide les natures inconnues,
        complète les sorties non traitées par le repli « à qualifier »."""
        import Code.routes.qualify_outputs as qo_module

        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Pièce usinée")

        ai_payload = json.dumps({
            "outputs": [
                {"data_id": target["data_id"], "suggested_nature": "RESULT",
                 "confidence": "high", "justification": "Sortie tangible",
                 "suggested_minimum_performance": "Cote respectée"},
                {"data_id": 999999, "suggested_nature": "RESULT"},  # data_id inconnu → ignoré
                {"data_id": next(o for o in outs if o["name"] == "Fiche suiveuse")["data_id"],
                 "suggested_nature": "NOT_A_REAL_NATURE"},  # nature invalide → None
            ]
        })
        monkeypatch.setattr(qo_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_returning(ai_payload), "fake-model", None),
        )
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "AI"
        by_id = {p["data_id"]: p for p in body["outputs"]}
        assert by_id[target["data_id"]]["suggested_nature"] == "RESULT"
        assert by_id[target["data_id"]]["suggested_minimum_performance"] == "Cote respectée"
        fiche = next(o for o in outs if o["name"] == "Fiche suiveuse")
        assert by_id[fiche["data_id"]]["suggested_nature"] is None
        # la 3e sortie (sans libellé → nom du destinataire), non traitée par l'IA, en repli
        troisieme = next(o for o in outs if o["name"] == "Contrôle qualité")
        assert by_id[troisieme["data_id"]]["confidence"] == "none"
        assert 999999 not in by_id

    def test_zero_results_gives_warning(self, client, carto, monkeypatch):
        """Aucune sortie proposée en RESULT → avertissement de fiabilité."""
        import Code.routes.qualify_outputs as qo_module

        monkeypatch.setattr(qo_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_returning(json.dumps({"outputs": []})), "fake-model", None),
        )
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["warning"] is not None
        assert "résultat" in body["warning"].lower()

    def test_more_than_three_results_gives_warning(self, app, client, carto, monkeypatch):
        """Plus de 3 sorties proposées en RESULT → avertissement de granularité."""
        import Code.routes.qualify_outputs as qo_module

        with app.app_context():
            extra = Link(entity_id=carto["entity_id"], source_activity_id=carto["a"],
                         target_activity_id=carto["z"], type="flux", description="Sortie supplémentaire")
            db.session.add(extra)
            db.session.commit()
        try:
            outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
            assert len(outs) == 4
            ai_payload = json.dumps({
                "outputs": [{"data_id": o["data_id"], "suggested_nature": "RESULT"} for o in outs]
            })
            monkeypatch.setattr(qo_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
            monkeypatch.setattr(
                "Code.ai_client.make_ai_client",
                lambda: (_fake_client_returning(ai_payload), "fake-model", None),
            )
            _sess(client, carto["entity_id"])
            r = client.post(f"/qualify/analyze/{carto['a']}")
            assert r.status_code == 200
            body = r.get_json()
            assert body["warning"] is not None
            assert "granularité" in body["warning"].lower() or "granularity" in body["warning"].lower()
        finally:
            with app.app_context():
                Link.query.filter_by(entity_id=carto["entity_id"], description="Sortie supplémentaire").delete()
                db.session.commit()

    def test_ai_exception_falls_back_with_error_source(self, client, carto, monkeypatch):
        """Le client IA lève une exception → repli « à qualifier », source=error, 200 (pas 500)."""
        import Code.routes.qualify_outputs as qo_module

        class _RaisingCompletions:
            def create(self, **kwargs):
                raise RuntimeError("panne IA")

        class _RaisingChat:
            completions = _RaisingCompletions()

        class _RaisingClient:
            chat = _RaisingChat()

        monkeypatch.setattr(qo_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_RaisingClient(), "fake-model", None),
        )
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/analyze/{carto['a']}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["source"] == "error"
        assert "panne IA" in body["error"]
        assert len(body["outputs"]) == 3


class TestSave:

    def test_unknown_activity_returns_404(self, client, carto):
        r = client.post(f"/qualify/save/999999", json={"outputs": []})
        assert r.status_code == 404

    def test_unknown_data_id_is_skipped(self, client, carto):
        _sess(client, carto["entity_id"])
        r = client.post(f"/qualify/save/{carto['a']}", json={
            "outputs": [{"data_id": 999999, "nature": "RESULT"}]
        })
        assert r.status_code == 200
        assert r.get_json()["saved"] == 0

    def test_invalid_nature_is_stored_as_none(self, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Pièce usinée")
        r = client.post(f"/qualify/save/{carto['a']}", json={
            "outputs": [{"data_id": target["data_id"], "nature": "NOT_A_REAL_NATURE"}]
        })
        assert r.status_code == 200
        saved = next(o for o in r.get_json()["outputs"] if o["data_id"] == target["data_id"])
        assert saved["nature"] is None
        assert saved["qualified"] is False

    def test_requalifying_a_result_returns_warning(self, client, carto):
        """Repasser un RESULT déjà qualifié à une autre nature déclenche un avertissement non bloquant."""
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Pièce usinée")
        client.post(f"/qualify/save/{carto['a']}", json={
            "outputs": [{"data_id": target["data_id"], "nature": "RESULT", "source": "MANUAL"}]
        })
        r = client.post(f"/qualify/save/{carto['a']}", json={
            "outputs": [{"data_id": target["data_id"], "nature": "MEASURE", "source": "MANUAL"}]
        })
        assert r.status_code == 200
        body = r.get_json()
        assert len(body["warnings"]) == 1
        assert body["warnings"][0]["data_id"] == target["data_id"]

    def test_qualification_source_ai_when_nature_present_without_manual_flag(self, app, client, carto):
        _sess(client, carto["entity_id"])
        outs = client.get(f"/qualify/outputs/{carto['a']}").get_json()["outputs"]
        target = next(o for o in outs if o["name"] == "Fiche suiveuse")
        r = client.post(f"/qualify/save/{carto['a']}", json={
            "outputs": [{"data_id": target["data_id"], "nature": "MEASURE"}]
        })
        assert r.status_code == 200
        with app.app_context():
            d = Data.query.get(target["data_id"])
            assert d.qualification_source == "AI"
