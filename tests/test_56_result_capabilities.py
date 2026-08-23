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


def _fake_client_raising(message):
    class _RaisingCompletions:
        def create(self, **kwargs):
            raise RuntimeError(message)

    class _RaisingChat:
        completions = _RaisingCompletions()

    class _RaisingClient:
        chat = _RaisingChat()

    return _RaisingClient()


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

    def test_success_returns_ai_competence_filtering_unknown_result_ids(self, auth_client, app, ids, monkeypatch):
        import Code.routes.result_capabilities as rc_module

        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        ai_payload = json.dumps({
            "activity_competence": {"description_fr": "Usiner conforme", "description_en": "Machine to spec"},
            "result_ids_used": [did, 999999],
            "granularity_alert": {"alert": True, "reason_fr": "Trop de résultats", "reason_en": "Too many results"},
        })
        monkeypatch.setattr(rc_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_returning(ai_payload), "fake-model", None),
        )
        try:
            r = auth_client.post(f"/competence/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["source"] == "AI"
            assert data["competence"]["description_fr"] == "Usiner conforme"
            assert data["result_ids_used"] == [did]
            assert data["granularity_alert"]["alert"] is True
        finally:
            _cleanup_activity(app, aid)

    def test_ai_exception_returns_error_source(self, auth_client, app, ids, monkeypatch):
        import Code.routes.result_capabilities as rc_module

        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        monkeypatch.setattr(rc_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_raising("panne IA"), "fake-model", None),
        )
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

    def test_success_creates_items_and_links_for_valid_results_only(self, auth_client, app, ids, monkeypatch):
        """L'IA propose SF/Savoir/HSC pour un résultat valide et un data_id inconnu (ignoré) ;
        les items sont créés à la volée et les liens (source=AI) enregistrés."""
        import Code.routes.result_capabilities as rc_module

        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        ai_payload = json.dumps({
            "results": [
                {"data_id": did,
                 "savoir_faires": ["Régler la machine"],
                 "savoirs": ["Lecture de plan"],
                 "hsc": [{"name": "Rigueur", "required_level": 3}, "ignoré (pas un dict)"]},
                {"data_id": 999999, "savoir_faires": ["Ne doit jamais être créé"]},
            ]
        })
        monkeypatch.setattr(rc_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_returning(ai_payload), "fake-model", None),
        )
        try:
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["source"] == "AI"
            assert data["created"] == 3
            items = data["links"]["by_result"][0]["items"]
            labels = {(it["item_type"], it["item_label"]) for it in items}
            assert ("SAVOIR_FAIRE", "Régler la machine") in labels
            assert ("SAVOIR", "Lecture de plan") in labels
            assert ("HSC", "Rigueur") in labels
            hsc_item = next(it for it in items if it["item_type"] == "HSC")
            assert hsc_item["required_level"] == 3

            with app.app_context():
                from Code.models.models import SavoirFaire, Data
                assert SavoirFaire.query.filter_by(activity_id=aid, description="Régler la machine").count() == 1
                assert Data.query.get(999999) is None
        finally:
            _cleanup_activity(app, aid)

    def test_success_second_call_deduplicates_and_upgrades_level(self, auth_client, app, ids, monkeypatch):
        """Un appel répété ne duplique pas les liens ; un required_level manquant peut être complété."""
        import Code.routes.result_capabilities as rc_module

        aid = _create_activity(app, ids["entity_id"])
        did = _create_result_data(app, ids["entity_id"], aid)
        first_payload = json.dumps({"results": [{"data_id": did, "hsc": [{"name": "Rigueur"}]}]})
        second_payload = json.dumps({"results": [{"data_id": did, "hsc": [{"name": "Rigueur", "required_level": 4}]}]})
        monkeypatch.setattr(rc_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")

        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_returning(first_payload), "fake-model", None),
        )
        try:
            auth_client.post(f"/competence/result_links/generate/{aid}")

            monkeypatch.setattr(
                "Code.ai_client.make_ai_client",
                lambda: (_fake_client_returning(second_payload), "fake-model", None),
            )
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["created"] == 0
            items = data["links"]["by_result"][0]["items"]
            assert len(items) == 1
            assert items[0]["required_level"] == 4

            with app.app_context():
                from Code.models.models import ResultCapabilityLink
                rows = ResultCapabilityLink.query.filter_by(activity_id=aid, item_type="HSC").all()
                assert len(rows) == 1
        finally:
            _cleanup_activity(app, aid)

    def test_ai_exception_rolls_back_and_returns_error_source(self, auth_client, app, ids, monkeypatch):
        import Code.routes.result_capabilities as rc_module

        aid = _create_activity(app, ids["entity_id"])
        _create_result_data(app, ids["entity_id"], aid)
        monkeypatch.setattr(rc_module, "get_prompt", lambda *a, **k: "SYSTEM PROMPT")
        monkeypatch.setattr(
            "Code.ai_client.make_ai_client",
            lambda: (_fake_client_raising("panne IA"), "fake-model", None),
        )
        try:
            r = auth_client.post(f"/competence/result_links/generate/{aid}")
            assert r.status_code == 200
            data = r.get_json()
            assert data["links"] == []
            assert data["source"] == "error"
            assert "panne IA" in data["error"]
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
