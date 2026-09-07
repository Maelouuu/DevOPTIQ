# tests/test_56_result_capabilities.py
"""
Page : Compétence principale & S/SF/HSC par résultat (/competence — CDC 2)
Couverture (sans clé IA configurée → repli explicite, jamais de 500) :
  - POST /competence/generate/<activity_id>              → génération compétence (repli no_ai / no_result)
  - POST /competence/save/<activity_id>                   → sauvegarde manuelle de la compétence
  - POST /competence/result_links/generate/<activity_id>  → génération S/SF/HSC (repli no_ai / no_result)
  - GET  /competence/result_links/<activity_id>            → lecture des liens groupés par résultat
  - POST /competence/result_links/<activity_id>            → création/suppression manuelle d'un lien
Couverture avec IA mockée (chemins succès/erreur, jamais d'appel réseau réel) :
  - POST /competence/generate/<activity_id>              → succès IA + alerte granularité, exception IA
  - POST /competence/result_links/generate/<activity_id>  → création/réutilisation d'items S/SF/HSC,
    dédoublonnage des liens, mise à jour du niveau requis, exception IA
  - _item_label (via GET result_links)                    → item supprimé après coup / item_type inconnu
"""
import json
import pytest

pytestmark = pytest.mark.result_capabilities


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
        "Code.routes.result_capabilities.openai_client_or_none",
        lambda: (fake_client, None),
    )


def _create_activity(app, entity_id, name="Activité Compétence Test 56"):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="Description")
        db.session.add(a)
        db.session.commit()
        return a.id


def _create_result_data(app, entity_id, activity_id, name="Résultat Test 56", min_perf="Standard atteint"):
    with app.app_context():
        from Code.models.models import Data
        from Code.extensions import db
        d = Data(entity_id=entity_id, name=name, type="flux",
                 producer_activity_id=activity_id, semantic_nature="RESULT",
                 minimum_performance_text=min_perf)
        db.session.add(d)
        db.session.commit()
        return d.id


def _create_savoir_faire(app, activity_id, description="Régler la machine Test 56"):
    with app.app_context():
        from Code.models.models import SavoirFaire
        from Code.extensions import db
        sf = SavoirFaire(activity_id=activity_id, description=description)
        db.session.add(sf)
        db.session.commit()
        return sf.id


def _cleanup_activity(app, activity_id):
    with app.app_context():
        from Code.models.models import (Activities, Data, Competency, ResultCapabilityLink,
                                        SavoirFaire, Savoir, Softskill)
        from Code.extensions import db
        ResultCapabilityLink.query.filter_by(activity_id=activity_id).delete()
        Competency.query.filter_by(activity_id=activity_id).delete()
        Data.query.filter_by(producer_activity_id=activity_id).delete()
        SavoirFaire.query.filter_by(activity_id=activity_id).delete()
        Savoir.query.filter_by(activity_id=activity_id).delete()
        Softskill.query.filter_by(activity_id=activity_id).delete()
        a = Activities.query.get(activity_id)
        if a:
            db.session.delete(a)
        db.session.commit()


class TestGenerateCompetence:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post("/competence/generate/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_no_result_returns_warning(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.post(f"/competence/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["competence"] is None
            assert data["source"] == "no_result"
        finally:
            _cleanup_activity(app, aid)

    def test_with_result_no_ai_key_returns_explicit_source(self, auth_client, app, ids):
        """Sans clé OpenAI configurée dans l'environnement de test, la génération ne doit
        jamais lever d'exception : repli explicite avec source non-AI."""
        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(f"/competence/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert "competence" in data
            assert "source" in data
            assert data["source"] != "AI"
        finally:
            _cleanup_activity(app, aid)


class TestSaveCompetence:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post(
            "/competence/save/999999",
            data=json.dumps({"description": "x"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_empty_description_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.post(
                f"/competence/save/{aid}",
                data=json.dumps({"description": "   "}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup_activity(app, aid)

    def test_save_valid_replaces_existing(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r1 = auth_client.post(
                f"/competence/save/{aid}",
                data=json.dumps({"description": "Première formulation"}),
                content_type="application/json",
            )
            assert r1.status_code == 200

            r2 = auth_client.post(
                f"/competence/save/{aid}",
                data=json.dumps({"description": "Formulation corrigée"}),
                content_type="application/json",
            )
            assert r2.status_code == 200
            assert r2.get_json()["description"] == "Formulation corrigée"

            with app.app_context():
                from Code.models.models import Competency
                rows = Competency.query.filter_by(activity_id=aid).all()
                assert len(rows) == 1
                assert rows[0].description == "Formulation corrigée"
        finally:
            _cleanup_activity(app, aid)


class TestGenerateResultLinks:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post("/competence/result_links/generate/999999")
        assert r.status_code == 404

    def test_no_result_returns_no_result_source(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["links"] == []
            assert data["source"] == "no_result"
        finally:
            _cleanup_activity(app, aid)

    def test_with_result_no_ai_key_returns_empty_links(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        try:
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["links"] == []
            assert data["source"] != "AI"
        finally:
            _cleanup_activity(app, aid)


class TestGetResultLinks:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.get("/competence/result_links/999999")
        assert r.status_code == 404

    def test_empty_when_no_links(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.get(f"/competence/result_links/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["by_result"] == []
            assert data["badges"] == {}
        finally:
            _cleanup_activity(app, aid)


class TestUpsertResultLink:

    def test_unknown_activity_returns_404(self, auth_client):
        r = auth_client.post(
            "/competence/result_links/999999",
            data=json.dumps({"data_id": 1, "item_type": "SAVOIR_FAIRE", "item_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_invalid_payload_returns_400(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        try:
            r = auth_client.post(
                f"/competence/result_links/{aid}",
                data=json.dumps({"item_type": "BOGUS"}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup_activity(app, aid)

    def test_create_manual_link_then_appears_in_get(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        sfid = _create_savoir_faire(app, aid)
        try:
            r = auth_client.post(
                f"/competence/result_links/{aid}",
                data=json.dumps({"data_id": did, "item_type": "SAVOIR_FAIRE", "item_id": sfid, "required_level": 2}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["ok"] is True
            assert len(data["links"]["by_result"]) == 1
            items = data["links"]["by_result"][0]["items"]
            assert any(it["item_id"] == sfid and it["source"] == "MANUAL" for it in items)

            r2 = auth_client.get(f"/competence/result_links/{aid}")
            data2 = r2.get_json()
            assert len(data2["by_result"]) == 1
            assert f"SAVOIR_FAIRE:{sfid}" in data2["badges"]
        finally:
            _cleanup_activity(app, aid)

    def test_create_link_is_not_duplicated(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        sfid = _create_savoir_faire(app, aid)
        try:
            payload = json.dumps({"data_id": did, "item_type": "SAVOIR_FAIRE", "item_id": sfid})
            auth_client.post(f"/competence/result_links/{aid}", data=payload, content_type="application/json")
            auth_client.post(f"/competence/result_links/{aid}", data=payload, content_type="application/json")
            with app.app_context():
                from Code.models.models import ResultCapabilityLink
                rows = ResultCapabilityLink.query.filter_by(
                    activity_id=aid, data_id=did, item_type="SAVOIR_FAIRE", item_id=sfid).all()
                assert len(rows) == 1
        finally:
            _cleanup_activity(app, aid)

    def test_delete_link_by_delete_id(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        sfid = _create_savoir_faire(app, aid)
        try:
            create = auth_client.post(
                f"/competence/result_links/{aid}",
                data=json.dumps({"data_id": did, "item_type": "SAVOIR_FAIRE", "item_id": sfid}),
                content_type="application/json",
            )
            link_id = create.get_json()["links"]["by_result"][0]["items"][0]["id"]

            r = auth_client.post(
                f"/competence/result_links/{aid}",
                data=json.dumps({"delete_id": link_id}),
                content_type="application/json",
            )
            assert r.status_code == 200
            assert r.get_json()["links"]["by_result"] == []
        finally:
            _cleanup_activity(app, aid)


class TestGenerateCompetenceWithAI:

    def test_ai_success_returns_description_and_filters_result_ids(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            content = json.dumps({
                "activity_competence": {"description_fr": "  Tenir la ligne  ", "description_en": "  Hold the line  "},
                "result_ids_used": [did, 999999],
                "granularity_alert": {"alert": True, "reason_fr": "trop large", "reason_en": "too broad"},
            })
            _mock_openai(monkeypatch, content=content)
            r = auth_client.post(f"/competence/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["source"] == "AI"
            assert data["competence"]["description_fr"] == "Tenir la ligne"
            assert data["competence"]["description_en"] == "Hold the line"
            assert data["result_ids_used"] == [did]
            assert data["granularity_alert"]["alert"] is True
        finally:
            _cleanup_activity(app, aid)

    def test_ai_exception_returns_error_source(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        try:
            _mock_openai(monkeypatch, raise_exc=RuntimeError("boom"))
            r = auth_client.post(f"/competence/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["competence"] is None
            assert data["source"] == "error"
            assert "boom" in data["error"]
        finally:
            _cleanup_activity(app, aid)


class TestGenerateResultLinksWithAI:

    def test_ai_success_creates_and_reuses_items(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        # Savoir-faire déjà existant : l'IA doit le retrouver (comparaison insensible à la casse)
        # au lieu d'en créer un doublon.
        existing_sf_id = _create_savoir_faire(app, aid, description="régler la machine")
        try:
            content = json.dumps({"results": [
                {
                    "data_id": did,
                    "savoir_faires": ["Régler LA machine", "   "],
                    "savoirs": ["Norme ISO nouvelle"],
                    "hsc": [{"name": "Rigueur", "required_level": 3}],
                },
                {"data_id": 999999, "savoir_faires": ["ignoré"], "savoirs": [], "hsc": []},
            ]})
            _mock_openai(monkeypatch, content=content)
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["source"] == "AI"
            assert data["created"] == 3
            items = data["links"]["by_result"][0]["items"]
            assert len(items) == 3
            assert any(it["item_id"] == existing_sf_id and it["item_type"] == "SAVOIR_FAIRE" for it in items)

            with app.app_context():
                from Code.models.models import SavoirFaire, Savoir, Softskill
                assert SavoirFaire.query.filter_by(activity_id=aid).count() == 1
                assert Savoir.query.filter_by(activity_id=aid).count() == 1
                assert Softskill.query.filter_by(activity_id=aid).count() == 1
        finally:
            _cleanup_activity(app, aid)

    def test_regenerating_updates_required_level_without_duplicating_link(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            first_pass = json.dumps({"results": [
                {"data_id": did, "savoir_faires": [], "savoirs": [],
                 "hsc": [{"name": "Rigueur", "required_level": None}]},
            ]})
            _mock_openai(monkeypatch, content=first_pass)
            r1 = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r1.get_json()["created"] == 1

            second_pass = json.dumps({"results": [
                {"data_id": did, "savoir_faires": [], "savoirs": [],
                 "hsc": [{"name": "RIGUEUR", "required_level": 3}]},
            ]})
            _mock_openai(monkeypatch, content=second_pass)
            r2 = auth_client.post(f"/competence/result_links/generate/{aid}")
            data2 = r2.get_json()
            assert data2["created"] == 0

            with app.app_context():
                from Code.models.models import ResultCapabilityLink, Softskill
                assert Softskill.query.filter_by(activity_id=aid).count() == 1
                link = ResultCapabilityLink.query.filter_by(activity_id=aid, data_id=did, item_type="HSC").one()
                assert link.required_level == 3
        finally:
            _cleanup_activity(app, aid)

    def test_ai_exception_returns_error_source(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        try:
            _mock_openai(monkeypatch, raise_exc=RuntimeError("boom"))
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["links"] == []
            assert data["source"] == "error"
            assert "boom" in data["error"]
        finally:
            _cleanup_activity(app, aid)


class TestItemLabelEdgeCases:

    def test_item_label_none_when_underlying_item_deleted(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        sfid = _create_savoir_faire(app, aid)
        try:
            auth_client.post(
                f"/competence/result_links/{aid}",
                data=json.dumps({"data_id": did, "item_type": "SAVOIR_FAIRE", "item_id": sfid}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import SavoirFaire
                from Code.extensions import db
                SavoirFaire.query.filter_by(id=sfid).delete()
                db.session.commit()

            r = auth_client.get(f"/competence/result_links/{aid}")
            items = r.get_json()["by_result"][0]["items"]
            assert items[0]["item_label"] is None
        finally:
            _cleanup_activity(app, aid)

    def test_item_label_none_when_item_type_unknown(self, auth_client, app, ids):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        try:
            with app.app_context():
                from Code.models.models import ResultCapabilityLink, Activities
                from Code.extensions import db
                entity_id = Activities.query.get(aid).entity_id
                db.session.add(ResultCapabilityLink(
                    entity_id=entity_id, activity_id=aid, data_id=did,
                    item_type="BOGUS", item_id=1, source="MANUAL"))
                db.session.commit()

            r = auth_client.get(f"/competence/result_links/{aid}")
            items = r.get_json()["by_result"][0]["items"]
            assert items[0]["item_label"] is None
        finally:
            _cleanup_activity(app, aid)
