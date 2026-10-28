# tests/test_122_propose_aptitudes_gaps.py
"""
Lacunes de /propose_aptitudes/propose et /propose_aptitudes/feasibility :
prompt indisponible, JSON invalide, entrées minimales, helpers purs.
Faux client OpenAI, aucun appel réseau, aucune donnée persistée.
"""
import json
import pytest

from Code.routes.propose_aptitudes import build_activity_summary, clean_json_response

pytestmark = pytest.mark.propose_ia

MODULE = "Code.routes.propose_aptitudes"


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


class _Completion:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _FakeClient:
    def __init__(self, content="{}"):
        self.calls = []
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return _Completion(content)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _use_client(monkeypatch, content="{}"):
    client = _FakeClient(content)
    monkeypatch.setattr(f"{MODULE}.openai_client_or_none", lambda: (client, None))
    return client


class TestPromptIndisponible:

    def test_propose_prompt_none_renvoie_source_prompts_unavailable(self, app, monkeypatch):
        client = _use_client(monkeypatch)
        monkeypatch.setattr(f"{MODULE}.get_prompt", lambda *a, **k: None)
        r = app.test_client().post("/propose_aptitudes/propose", json={"name": "A"})
        assert r.status_code == 200
        assert r.get_json() == {"proposals": {}, "source": "prompts-unavailable"}
        assert client.calls == []

    def test_feasibility_prompt_none_renvoie_source_prompts_unavailable(self, app, monkeypatch):
        client = _use_client(monkeypatch)
        monkeypatch.setattr(f"{MODULE}.get_prompt", lambda *a, **k: None)
        r = app.test_client().post("/propose_aptitudes/feasibility", json={"activity_name": "A"})
        assert r.status_code == 200
        assert r.get_json() == {"result": {}, "source": "prompts-unavailable"}
        assert client.calls == []


class TestJsonInvalide:

    def test_propose_json_invalide_renvoie_erreur_parsing(self, app, monkeypatch):
        _use_client(monkeypatch, "{pas du json")
        r = app.test_client().post("/propose_aptitudes/propose", json={"name": "A"})
        body = r.get_json()
        assert r.status_code == 200
        assert body["proposals"] == {}
        assert body["error"].startswith("Erreur parsing JSON")

    def test_feasibility_json_invalide_renvoie_erreur_parsing(self, app, monkeypatch):
        _use_client(monkeypatch, "{pas du json")
        r = app.test_client().post("/propose_aptitudes/feasibility", json={"activity_name": "A"})
        body = r.get_json()
        assert r.status_code == 200
        assert body["result"] == {}
        assert body["error"].startswith("Erreur parsing JSON")


class TestSuccesEtEntrees:

    def test_propose_succes_retire_les_balises_markdown(self, app, monkeypatch):
        _use_client(monkeypatch, '```json\n{"risque": "faible"}\n```')
        r = app.test_client().post("/propose_aptitudes/propose", json={"name": "A"})
        assert r.get_json() == {"proposals": {"risque": "faible"}}

    def test_feasibility_accepte_json_dict_et_aides_en_liste(self, app, monkeypatch):
        client = _use_client(monkeypatch, '{"ok": true}')
        r = app.test_client().post("/propose_aptitudes/feasibility", json={
            "activity_name": "Soudure",
            "inclusion_scoring_json": {"score": 3},
            "assistive_products": ["loupe", "casque"],
            "profil_fonctionnel": {"vision": "faible"},
        })
        assert r.get_json() == {"result": {"ok": True}}
        user_prompt = client.calls[0]["messages"][1]["content"]
        assert "- loupe" in user_prompt and "- casque" in user_prompt

    def test_feasibility_aides_chaine_conservee_telle_quelle(self, app, monkeypatch):
        client = _use_client(monkeypatch, "{}")
        app.test_client().post("/propose_aptitudes/feasibility", json={
            "activity_name": "A", "assistive_products": "fauteuil",
        })
        assert "fauteuil" in client.calls[0]["messages"][1]["content"]

    def test_propose_langue_anglaise_dans_le_message_systeme(self, app, monkeypatch):
        client = _use_client(monkeypatch)
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["lang"] = "en"
        c.post("/propose_aptitudes/propose", json={"name": "A"})
        assert "Respond in English" in client.calls[0]["messages"][0]["content"]

    def test_feasibility_sans_cle_renvoie_source(self, app, monkeypatch):
        monkeypatch.setattr(f"{MODULE}.openai_client_or_none", lambda: (None, "no-key"))
        r = app.test_client().post("/propose_aptitudes/feasibility", json={})
        assert r.get_json() == {"result": {}, "source": "no-key"}


class TestHelpers:

    def test_clean_json_sans_delimiteur_renvoie_le_texte(self):
        assert clean_json_response("bonjour") == "bonjour"

    def test_clean_json_extrait_tableau_avant_objet(self):
        assert clean_json_response('x [1, {"a": 2}] y') == '[1, {"a": 2}]'

    def test_clean_json_fermeture_absente_renvoie_le_texte(self):
        assert clean_json_response("[1, 2") == "[1, 2"

    def test_clean_json_objet_seul(self):
        assert json.loads(clean_json_response('texte {"a": 1} fin')) == {"a": 1}

    def test_summary_vide_donne_non_renseigne(self):
        assert build_activity_summary({}) == "Non renseigné"

    def test_summary_assemble_toutes_les_sections(self):
        s = build_activity_summary({
            "description": "Desc",
            "outils": ["Marteau"],
            "constraints": ["Bruit"],
            "tasks": [{"description": "Frapper"}, "Ranger"],
            "outgoing": [{"performance": {"name": "P", "description": "D"}}, {}],
        })
        assert s.splitlines() == [
            "Desc", "Outils : Marteau", "Contraintes : Bruit",
            "T1: Frapper", "T2: Ranger", "Performance : P - D",
        ]
