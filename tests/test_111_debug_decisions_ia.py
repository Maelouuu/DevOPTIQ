# tests/test_111_debug_decisions_ia.py
"""
Page : Carte des activités — débogage des décisions (VSDX / outil / IA)
Couvre _tool_decisions_from_entity, _ai_extract_decisions et les routes
/activities/api/debug-decisions/* sur les chemins que test_44 n'exerce pas
(IA simulée : aucun appel réseau).
"""
import io
import json
import os
import shutil
import types
import uuid

import pytest

pytestmark = pytest.mark.activities_map

VSDX_SRC = os.path.join(os.path.dirname(__file__), "..", "Code", "example.vsdx")


def _fake_client(content=None, boom=None):
    def create(**kwargs):
        if boom:
            raise boom
        msg = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


@pytest.fixture
def entite_jetable(app, ids):
    from Code.models.models import Entity
    from Code.extensions import db
    with app.app_context():
        e = Entity(name=f"Debug Décisions {uuid.uuid4().hex[:6]}", description="",
                   owner_id=ids["user_id"])
        db.session.add(e)
        db.session.commit()
        eid = e.id
    yield eid
    with app.app_context():
        from Code.routes import activities_map as am
        shutil.rmtree(am.get_entity_dir(eid), ignore_errors=True)
        ent = db.session.get(Entity, eid)
        if ent:
            db.session.delete(ent)
            db.session.commit()


def _activer(client, eid):
    with client.session_transaction() as s:
        s["active_entity_id"] = eid


class TestToolDecisionsFromEntity:

    def test_json_carto_et_liens_db(self, app, ids, entite_jetable):
        from Code.models.models import Entity, Activities, Link
        from Code.extensions import db
        from Code.routes.activities_map import _tool_decisions_from_entity
        carto = {
            "shapes": [
                {"id": "d1", "_type": "decision", "label": "Valider ?"},
                {"id": "a1", "_type": "activity", "label": "Entrée"},
                {"id": "a2", "_type": "activity", "label": "Sortie"},
            ],
            "connections": [
                {"id": "c1", "fromId": "a1", "toId": "d1", "label": "in"},
                {"id": "c2", "fromId": "d1", "toId": "a2", "label": "Oui"},
            ],
        }
        with app.app_context():
            ent = db.session.get(Entity, entite_jetable)
            ent.optiqcarto_data = json.dumps(carto)
            src = Activities(entity_id=ent.id, name="Choix DB", description="")
            tgt = Activities(entity_id=ent.id, name="Cible DB", description="")
            db.session.add_all([src, tgt])
            db.session.flush()
            db.session.add(Link(entity_id=ent.id, source_activity_id=src.id,
                                target_activity_id=tgt.id, type="nourrissante",
                                choice_label="Non"))
            db.session.commit()
            res = _tool_decisions_from_entity(ent)
        assert res["total_shapes"] == 3
        assert res["total_connections"] == 2
        carto_dec = next(d for d in res["decisions"] if d["id"] == "d1")
        assert carto_dec["outgoing"][0]["to_label"] == "Sortie"
        assert carto_dec["outgoing"][0]["badge"] == "Oui"
        assert carto_dec["incoming"][0]["from_label"] == "Entrée"
        db_dec = next(d for d in res["decisions"] if d.get("source") == "db")
        assert db_dec["label"] == "Choix DB"
        assert db_dec["outgoing"][0]["badge"] == "Non"
        assert db_dec["outgoing"][0]["to_label"] == "Cible DB"

    def test_json_invalide_ignore(self, app, entite_jetable):
        from Code.models.models import Entity
        from Code.extensions import db
        from Code.routes.activities_map import _tool_decisions_from_entity
        with app.app_context():
            ent = db.session.get(Entity, entite_jetable)
            ent.optiqcarto_data = "{pas du json"
            db.session.commit()
            res = _tool_decisions_from_entity(ent)
        assert res == {"decisions": [], "total_shapes": 0, "total_connections": 0}

    def test_decision_db_deja_presente_dans_carto_non_dupliquee(self, app, entite_jetable):
        from Code.models.models import Entity, Activities, Link
        from Code.extensions import db
        from Code.routes.activities_map import _tool_decisions_from_entity
        with app.app_context():
            ent = db.session.get(Entity, entite_jetable)
            ent.optiqcarto_data = json.dumps(
                {"shapes": [{"id": "d1", "_type": "decision", "label": "Même nom"}],
                 "connections": []})
            src = Activities(entity_id=ent.id, name="Même nom", description="")
            db.session.add(src)
            db.session.flush()
            db.session.add(Link(entity_id=ent.id, source_activity_id=src.id,
                                type="nourrissante", choice_label="Oui"))
            db.session.commit()
            res = _tool_decisions_from_entity(ent)
        assert [d["label"] for d in res["decisions"]] == ["Même nom"]


class TestAiExtractDecisions:

    VSDX = {"decisions": [{"id": "5", "label": "OK ?", "master_name": "Decision",
                           "splice": True,
                           "incoming": [{"from_label": "Début"}],
                           "outgoing": [{"to_label": "Fin", "badge": "Oui"}]}],
            "total_shapes": 4, "total_connectors": 3}

    def test_sans_client_retourne_erreur(self, monkeypatch):
        from Code.routes import activities_map as am
        monkeypatch.setattr(am, "openai_client_or_none", lambda: (None, "pas de clé"))
        res = am._ai_extract_decisions(self.VSDX, "f.vsdx")
        assert res["source"] == "error"
        assert res["error"] == "pas de clé"
        assert res["data"] == {"decisions": []}

    def test_reponse_json_extraite(self, monkeypatch):
        from Code.routes import activities_map as am
        monkeypatch.setattr(am, "openai_client_or_none",
                            lambda: (_fake_client('Voici: {"decisions": [{"id": "5"}]} fin'), None))
        res = am._ai_extract_decisions(self.VSDX, "f.vsdx")
        assert res == {"source": "openai", "data": {"decisions": [{"id": "5"}]}}

    def test_reponse_sans_json_conserve_le_brut(self, monkeypatch):
        from Code.routes import activities_map as am
        monkeypatch.setattr(am, "openai_client_or_none",
                            lambda: (_fake_client("aucun json ici"), None))
        res = am._ai_extract_decisions(self.VSDX)
        assert res["source"] == "openai"
        assert res["data"] == {"decisions": []}
        assert res["raw"] == "aucun json ici"

    def test_exception_client_retourne_erreur(self, monkeypatch):
        from Code.routes import activities_map as am
        monkeypatch.setattr(am, "openai_client_or_none",
                            lambda: (_fake_client(boom=RuntimeError("quota")), None))
        res = am._ai_extract_decisions(self.VSDX)
        assert res["source"] == "error"
        assert "quota" in res["error"]

    def test_resume_envoye_contient_les_losanges(self, monkeypatch):
        from Code.routes import activities_map as am
        vus = {}

        def create(**kwargs):
            vus["messages"] = kwargs["messages"]
            msg = types.SimpleNamespace(content="{}")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
        monkeypatch.setattr(am, "openai_client_or_none", lambda: (client, None))
        am._ai_extract_decisions(self.VSDX, "f.vsdx")
        user = vus["messages"][1]["content"]
        assert 'ID 5 "OK ?" [Decision] [splice]' in user
        assert '← "Début"' in user
        assert '→ "Fin" [badge:Oui]' in user


class TestAnalyzeFileAi:

    def test_fichier_valide_appelle_l_ia(self, auth_client, monkeypatch):
        from Code.routes import activities_map as am
        monkeypatch.setattr(am, "openai_client_or_none",
                            lambda: (_fake_client('{"decisions": []}'), None))
        with open(VSDX_SRC, "rb") as f:
            data = {"vsdx": (io.BytesIO(f.read()), "example.vsdx")}
        r = auth_client.post("/activities/api/debug-decisions/analyze-file/ai",
                             data=data, content_type="multipart/form-data")
        assert r.status_code == 200
        assert r.get_json()["source"] == "openai"

    def test_analyze_file_valide_retourne_vsdx(self, auth_client):
        with open(VSDX_SRC, "rb") as f:
            data = {"vsdx": (io.BytesIO(f.read()), "example.vsdx")}
        r = auth_client.post("/activities/api/debug-decisions/analyze-file",
                             data=data, content_type="multipart/form-data")
        assert r.status_code == 200
        assert isinstance(r.get_json()["vsdx"]["decisions"], list)

    def test_sans_auth_analyze_file_401(self, app):
        r = app.test_client().post("/activities/api/debug-decisions/analyze-file")
        assert r.status_code == 401


class TestLegacyDebugDecisions:

    def test_get_avec_vsdx_stocke(self, auth_client, entite_jetable):
        from Code.routes import activities_map as am
        os.makedirs(am.get_entity_dir(entite_jetable), exist_ok=True)
        shutil.copy(VSDX_SRC, am.get_entity_vsdx_path(entite_jetable))
        _activer(auth_client, entite_jetable)
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 200
        body = r.get_json()
        assert body["entity_id"] == entite_jetable
        assert body["has_vsdx"] is True
        assert "decisions" in body["vsdx"]

    def test_ai_avec_vsdx_stocke_appelle_l_ia(self, auth_client, entite_jetable, monkeypatch):
        from Code.routes import activities_map as am
        os.makedirs(am.get_entity_dir(entite_jetable), exist_ok=True)
        shutil.copy(VSDX_SRC, am.get_entity_vsdx_path(entite_jetable))
        monkeypatch.setattr(am, "openai_client_or_none",
                            lambda: (_fake_client('{"decisions": []}'), None))
        _activer(auth_client, entite_jetable)
        r = auth_client.post("/activities/api/debug-decisions/ai")
        assert r.status_code == 200
        assert r.get_json()["source"] == "openai"

    def test_ai_vsdx_corrompu_ne_plante_pas(self, auth_client, entite_jetable, monkeypatch):
        from Code.routes import activities_map as am
        os.makedirs(am.get_entity_dir(entite_jetable), exist_ok=True)
        with open(am.get_entity_vsdx_path(entite_jetable), "wb") as f:
            f.write(b"pas un zip")
        monkeypatch.setattr(am, "openai_client_or_none",
                            lambda: (_fake_client('{"decisions": []}'), None))
        _activer(auth_client, entite_jetable)
        r = auth_client.post("/activities/api/debug-decisions/ai")
        assert r.status_code == 200
        assert r.get_json()["data"] == {"decisions": []}

    def test_ai_extraction_en_erreur_500_json(self, auth_client, entite_jetable, monkeypatch):
        from Code.routes import activities_map as am
        os.makedirs(am.get_entity_dir(entite_jetable), exist_ok=True)
        shutil.copy(VSDX_SRC, am.get_entity_vsdx_path(entite_jetable))

        def _boom(path):
            raise ValueError("extraction impossible")
        monkeypatch.setattr(am, "extract_decisions_from_vsdx", _boom)
        _activer(auth_client, entite_jetable)
        r = auth_client.post("/activities/api/debug-decisions/ai")
        assert r.status_code == 500
        assert r.get_json()["error"] == "extraction impossible"
