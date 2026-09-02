# tests/test_56_result_capabilities.py
"""
Page : Compétence principale & S/SF/HSC par résultat (/competence — CDC 2)
Couverture (sans clé IA configurée → repli explicite, jamais de 500) :
  - POST /competence/generate/<activity_id>              → génération compétence (repli no_ai / no_result)
  - POST /competence/save/<activity_id>                   → sauvegarde manuelle de la compétence
  - POST /competence/result_links/generate/<activity_id>  → génération S/SF/HSC (repli no_ai / no_result)
  - GET  /competence/result_links/<activity_id>            → lecture des liens groupés par résultat
  - POST /competence/result_links/<activity_id>            → création/suppression manuelle d'un lien
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
    """Patche openai_client_or_none() importé dans result_capabilities pour renvoyer un faux client."""
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

    def test_with_ai_key_success_returns_competence(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        content = json.dumps({
            "activity_competence": {"description_fr": "Traiter les commandes.", "description_en": "Process orders."},
            "result_ids_used": [did, 999999],
            "granularity_alert": {"alert": True, "reason_fr": "Trop large", "reason_en": "Too broad"},
        })
        _mock_openai(monkeypatch, content=content)
        try:
            r = auth_client.post(f"/competence/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["source"] == "AI"
            assert data["competence"]["description_fr"] == "Traiter les commandes."
            assert data["competence"]["description_en"] == "Process orders."
            # result_ids_used est filtré aux résultats réels de l'activité (999999 exclu)
            assert data["result_ids_used"] == [did]
            assert data["granularity_alert"]["alert"] is True
        finally:
            _cleanup_activity(app, aid)

    def test_with_ai_key_exception_returns_error_source(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        _mock_openai(monkeypatch, raise_exc=RuntimeError("panne IA"))
        try:
            r = auth_client.post(f"/competence/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["competence"] is None
            assert data["source"] == "error"
            assert "panne IA" in data["error"]
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

    def test_with_ai_key_success_creates_items_and_links(self, auth_client, app, ids, monkeypatch):
        """L'IA propose un SF déjà existant (réutilisé, insensible à la casse), un savoir nouveau
        et une HSC nouvelle : couvre la création d'items ET la réutilisation par _get_or_create_item."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        existing_sf_id = _create_savoir_faire(app, aid, description="Régler la machine Test 56")
        content = json.dumps({"results": [{
            "data_id": did,
            "savoir_faires": ["régler la machine test 56", "Contrôler la qualité de l'outil"],
            "savoirs": ["Norme qualité ISO"],
            "hsc": [{"name": "Rigueur", "required_level": 3}, "pas_un_dict_ignore"],
        }]})
        _mock_openai(monkeypatch, content=content)
        try:
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["source"] == "AI"
            # "created" compte les LIENS (pas les items) : 4 triplets valides (le 5e, une chaîne
            # brute au lieu d'un dict, est filtré par l'`isinstance(h, dict)` sur le bloc hsc).
            assert data["created"] == 4

            with app.app_context():
                from Code.models.models import SavoirFaire, ResultCapabilityLink
                sf_count = SavoirFaire.query.filter_by(activity_id=aid).count()
                assert sf_count == 2  # l'existant réutilisé + le nouveau
                links = ResultCapabilityLink.query.filter_by(activity_id=aid, data_id=did).all()
                assert len(links) == 4
                sf_link = ResultCapabilityLink.query.filter_by(
                    activity_id=aid, data_id=did, item_type="SAVOIR_FAIRE", item_id=existing_sf_id).first()
                assert sf_link is not None
                assert sf_link.source == "AI"
                hsc_link = ResultCapabilityLink.query.filter_by(
                    activity_id=aid, data_id=did, item_type="HSC").first()
                assert hsc_link.required_level == 3

            # Rejouer la génération : les liens existants ne sont pas dupliqués (created=0)
            r2 = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r2.get_json()["created"] == 0
        finally:
            _cleanup_activity(app, aid)

    def test_with_ai_key_ignores_empty_text_and_unknown_result(self, auth_client, app, ids, monkeypatch):
        """Texte vide (après strip) ignoré sans planter ; bloc pointant vers un data_id qui n'est
        pas un résultat de l'activité totalement ignoré."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        content = json.dumps({"results": [
            {"data_id": did, "savoir_faires": ["   ", ""], "savoirs": [], "hsc": []},
            {"data_id": 999999, "savoir_faires": ["Ne doit jamais être créé"], "savoirs": [], "hsc": []},
        ]})
        _mock_openai(monkeypatch, content=content)
        try:
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["created"] == 0
            with app.app_context():
                from Code.models.models import SavoirFaire
                assert SavoirFaire.query.filter_by(
                    activity_id=aid, description="Ne doit jamais être créé").first() is None
        finally:
            _cleanup_activity(app, aid)

    def test_with_ai_key_updates_missing_required_level_on_replay(self, auth_client, app, ids, monkeypatch):
        """Un lien HSC existant sans niveau requis se voit compléter le niveau à la regénération."""
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _mock_openai(monkeypatch, content=json.dumps({"results": [{
            "data_id": did, "savoir_faires": [], "savoirs": [],
            "hsc": [{"name": "Ecoute", "required_level": None}],
        }]}))
        try:
            auth_client.post(f"/competence/result_links/generate/{aid}")
            with app.app_context():
                from Code.models.models import ResultCapabilityLink
                link = ResultCapabilityLink.query.filter_by(activity_id=aid, data_id=did, item_type="HSC").first()
                assert link.required_level is None

            _mock_openai(monkeypatch, content=json.dumps({"results": [{
                "data_id": did, "savoir_faires": [], "savoirs": [],
                "hsc": [{"name": "Ecoute", "required_level": 2}],
            }]}))
            r2 = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r2.get_json()["created"] == 0
            with app.app_context():
                from Code.models.models import ResultCapabilityLink
                link = ResultCapabilityLink.query.filter_by(activity_id=aid, data_id=did, item_type="HSC").first()
                assert link.required_level == 2
        finally:
            _cleanup_activity(app, aid)

    def test_with_ai_key_exception_rolls_back(self, auth_client, app, ids, monkeypatch):
        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        _mock_openai(monkeypatch, raise_exc=RuntimeError("panne IA"))
        try:
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["links"] == []
            assert data["source"] == "error"
            assert "panne IA" in data["error"]
            with app.app_context():
                from Code.models.models import ResultCapabilityLink
                assert ResultCapabilityLink.query.filter_by(activity_id=aid, data_id=did).count() == 0
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

    def test_item_label_null_when_underlying_item_deleted(self, auth_client, app, ids):
        """Un lien pointant vers un item supprimé (orphelin) : item_label est None, sans planter."""
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
            assert r.status_code == 200
            items = r.get_json()["by_result"][0]["items"]
            assert items[0]["item_label"] is None
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
