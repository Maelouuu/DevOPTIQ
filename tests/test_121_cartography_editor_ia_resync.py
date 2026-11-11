# tests/test_121_cartography_editor_ia_resync.py
"""
Éditeur OptiqCarto — chemins non couverts :
  POST /cartography/api/architect   → réponses OpenAI / Anthropic simulées, erreurs
  POST /cartography/api/resync/<id> → 404, 400, succès, erreur de sync
  POST /cartography/api/save-diff   → sans carto stockée
  DELETE /cartography/api/delete    → remise à zéro de la carto

Chaque test travaille sur une entité et un utilisateur jetables (créés puis
supprimés) pour ne pas polluer la base partagée de la session.
"""
import json
import uuid
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.cartography_editor_ia_resync

ARCHITECT = "/cartography/api/architect"

STATE = {
    "state": {
        "shapes": [
            {"id": 1, "label": "A", "type": "process", "x": 200, "y": 0, "w": 170, "h": 70},
            {"id": 2, "label": "B", "type": "process", "x": 400, "y": 0, "w": 170, "h": 70},
        ],
        "bands": [{"id": 1, "label": "Bande", "height": 220}],
        "connections": [{"fromId": 1, "toId": 2}],
    }
}


@pytest.fixture
def carto_env(app):
    """Entité + utilisateur jetables, et un client authentifié sur ce compte."""
    from Code.extensions import db
    from Code.models.models import Entity, User

    tag = uuid.uuid4().hex[:8]
    with app.app_context():
        entity = Entity(name=f"EntCarto {tag}")
        db.session.add(entity)
        db.session.flush()
        user = User(entity_id=entity.id, first_name="C", last_name="T",
                    email=f"carto-{tag}@devoptiq.com", password="x", status="admin")
        db.session.add(user)
        db.session.flush()
        entity.owner_id = user.id
        db.session.commit()
        ent_id, user_id, email = entity.id, user.id, user.email

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_email"] = email
        sess["active_entity_id"] = ent_id

    yield SimpleNamespace(client=client, entity_id=ent_id, user_id=user_id)

    with app.app_context():
        Entity.query.filter_by(id=ent_id).update({"owner_id": None})
        User.query.filter_by(id=user_id).delete()
        Entity.query.filter_by(id=ent_id).delete()
        db.session.commit()


def _set_carto(app, entity_id, data):
    from Code.extensions import db
    from Code.models.models import Entity
    with app.app_context():
        Entity.query.get(entity_id).optiqcarto_data = data
        db.session.commit()


def _fake_openai(content=None, exc=None):
    def create(**kwargs):
        if exc:
            raise exc
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return lambda: (client, "gpt-test", None)


class TestArchitectOpenAI:
    def test_reponse_json_brute_renvoyee_telle_quelle(self, carto_env, monkeypatch):
        monkeypatch.setattr("Code.ai_client.make_ai_client",
                            _fake_openai('{"1": {"x": 210, "y": 20}}'))
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 200
        assert r.get_json() == {"1": {"x": 210, "y": 20}}

    def test_reponse_dans_un_bloc_markdown_json_est_decodee(self, carto_env, monkeypatch):
        monkeypatch.setattr("Code.ai_client.make_ai_client",
                            _fake_openai('```json\n{"2": {"x": 300, "y": 40}}\n```'))
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 200
        assert r.get_json() == {"2": {"x": 300, "y": 40}}

    def test_reponse_non_json_donne_500_openai(self, carto_env, monkeypatch):
        monkeypatch.setattr("Code.ai_client.make_ai_client", _fake_openai("pas du json"))
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 500
        assert r.get_json()["error"].startswith("Erreur OpenAI")

    def test_exception_du_client_donne_500_openai(self, carto_env, monkeypatch):
        monkeypatch.setattr("Code.ai_client.make_ai_client",
                            _fake_openai(exc=RuntimeError("quota")))
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 500
        assert "quota" in r.get_json()["error"]

    def test_prompt_systeme_absent_donne_500(self, carto_env, monkeypatch):
        monkeypatch.setattr("Code.routes.cartography_editor.get_prompt",
                            lambda *a, **k: None)
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 500
        assert "Prompts IA" in r.get_json()["error"]


class TestArchitectAnthropic:
    @pytest.fixture(autouse=True)
    def _sans_openai(self, monkeypatch):
        monkeypatch.setattr("Code.ai_client.make_ai_client",
                            lambda: (None, None, "pas de clé"))

    def test_sans_aucune_cle_message_explicite(self, carto_env, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_KEY", raising=False)
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 500
        assert "Aucune clé IA" in r.get_json()["error"]

    def test_cle_anthropic_reponse_decodee(self, carto_env, monkeypatch):
        import anthropic
        monkeypatch.setenv("ANTHROPIC_KEY", "sk-test")

        class FakeAnthropic:
            def __init__(self, api_key):
                self.messages = SimpleNamespace(create=lambda **kw: SimpleNamespace(
                    content=[SimpleNamespace(text='{"1": {"x": 250, "y": 10}}')]))

        monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropic)
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 200
        assert r.get_json() == {"1": {"x": 250, "y": 10}}

    def test_cle_anthropic_exception_donne_500_anthropic(self, carto_env, monkeypatch):
        import anthropic
        monkeypatch.setenv("ANTHROPIC_KEY", "sk-test")

        class BoomAnthropic:
            def __init__(self, api_key):
                def boom(**kw):
                    raise RuntimeError("indisponible")
                self.messages = SimpleNamespace(create=boom)

        monkeypatch.setattr(anthropic, "Anthropic", BoomAnthropic)
        r = carto_env.client.post(ARCHITECT, json=STATE)
        assert r.status_code == 500
        assert r.get_json()["error"].startswith("Erreur Anthropic")


class TestResync:
    def test_sans_auth_403(self, app):
        r = app.test_client().post("/cartography/api/resync/1")
        assert r.status_code == 403

    def test_entite_inexistante_404(self, carto_env):
        r = carto_env.client.post("/cartography/api/resync/99999999")
        assert r.status_code == 404

    def test_entite_d_un_autre_proprietaire_404(self, carto_env, ids):
        r = carto_env.client.post(f"/cartography/api/resync/{ids['entity_id']}")
        assert r.status_code == 404

    def test_sans_carto_stockee_400(self, carto_env):
        r = carto_env.client.post(f"/cartography/api/resync/{carto_env.entity_id}")
        assert r.status_code == 400
        assert "Aucune cartographie" in r.get_json()["error"]

    def test_carto_vide_valide_renvoie_ok(self, app, carto_env):
        _set_carto(app, carto_env.entity_id, json.dumps({"shapes": [], "bands": []}))
        r = carto_env.client.post(f"/cartography/api/resync/{carto_env.entity_id}")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_json_stocke_corrompu_donne_500(self, app, carto_env):
        _set_carto(app, carto_env.entity_id, "{pas du json")
        r = carto_env.client.post(f"/cartography/api/resync/{carto_env.entity_id}")
        assert r.status_code == 500
        assert "error" in r.get_json()


class TestSaveDiffEtSuppression:
    def test_save_diff_sans_carto_stockee_liste_vide(self, carto_env):
        r = carto_env.client.post("/cartography/api/save-diff", json={"diagram": {}})
        assert r.status_code == 200
        assert r.get_json() == {"removed_activities": [], "removed_roles": []}

    def test_save_diff_sans_auth_403(self, app):
        r = app.test_client().post("/cartography/api/save-diff", json={})
        assert r.status_code == 403

    def test_delete_efface_la_carto_et_la_liste_devient_vide(self, app, carto_env):
        _set_carto(app, carto_env.entity_id, json.dumps({"shapes": []}))
        c = carto_env.client
        assert len(c.get("/cartography/api/list").get_json()) == 1
        r = c.delete("/cartography/api/delete/x")
        assert r.status_code == 200 and r.get_json()["ok"] is True
        assert c.get("/cartography/api/list").get_json() == []

    def test_delete_sans_auth_403(self, app):
        assert app.test_client().delete("/cartography/api/delete/x").status_code == 403
