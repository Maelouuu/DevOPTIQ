# tests/test_51_propose_ia_ai_path.py
"""
Couverture du chemin "avec IA" (client OpenAI simulé) pour les routes de
proposition automatique :
  - /propose_savoirs/propose
  - /propose_savoir_faires/propose
  - /propose_softskills/propose
  - /propose_aptitudes/propose
  - /propose_aptitudes/feasibility

test_22_propose_ia.py ne couvre que le chemin "sans clé OpenAI" (fallback).
Ce fichier simule un client OpenAI (monkeypatch de openai_client_or_none dans
chaque module de route) pour exercer :
  - le parsing JSON/texte réussi de la réponse IA,
  - le fallback quand la réponse IA n'est pas un JSON valide,
  - la gestion d'exception levée pendant l'appel IA,
  - la branche de langue anglaise (session['lang'] = 'en').
"""
import json
import contextlib
import pytest

import Code.routes.propose_savoirs as propose_savoirs_mod
import Code.routes.propose_savoir_faires as propose_savoir_faires_mod
import Code.routes.propose_softskills as propose_softskills_mod
import Code.routes.propose_aptitudes as propose_aptitudes_mod

pytestmark = pytest.mark.propose_ia


# ---------------------------------------------------------------------------
# Faux client OpenAI
# ---------------------------------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content=None, raise_exc=None):
        self.completions = _FakeCompletions(content, raise_exc)


class _FakeClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _patch_client(monkeypatch, module, content=None, raise_exc=None):
    """Force openai_client_or_none() à renvoyer un faux client dans `module`."""
    fake = _FakeClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(module, "openai_client_or_none", lambda: (fake, None))


@contextlib.contextmanager
def _lang(client, value):
    """Bascule session['lang'] pendant le test puis la restaure (client de session partagée)."""
    with client.session_transaction() as sess:
        previous = sess.get("lang")
        sess["lang"] = value
    try:
        yield
    finally:
        with client.session_transaction() as sess:
            if previous is None:
                sess.pop("lang", None)
            else:
                sess["lang"] = previous


# ===========================================================================
# 1. POST /propose_savoirs/propose — avec IA simulée
# ===========================================================================

class TestProposeSavoirsAI:

    def test_ai_bullet_list_parsed_into_proposals(self, auth_client, monkeypatch):
        content = "- Règles de nomenclature catalogue\n- Procédure interne de transfert\n- Principes de faisabilité technique"
        _patch_client(monkeypatch, propose_savoirs_mod, content=content)
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Activité X", "savoir_faires": ["Vérifier les données"]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == [
            "Règles de nomenclature catalogue",
            "Procédure interne de transfert",
            "Principes de faisabilité technique",
        ]

    def test_ai_exception_returns_200_with_error(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_savoirs_mod, raise_exc=RuntimeError("boom"))
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Activité X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"]

    def test_ai_english_lang_error_message(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_savoirs_mod, raise_exc=RuntimeError("boom"))
        with _lang(auth_client, "en"):
            r = auth_client.post(
                "/propose_savoirs/propose",
                data=json.dumps({"name": "Activity X"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == ["Knowledge not determined (server error)"]


# ===========================================================================
# 2. POST /propose_savoir_faires/propose — avec IA simulée
# ===========================================================================

class TestProposeSavoirFairesAI:

    def test_ai_bullet_list_parsed_into_proposals(self, auth_client, monkeypatch):
        content = "- Utiliser la checklist sécurité\n- Vérifier les équipements avant intervention"
        _patch_client(monkeypatch, propose_savoir_faires_mod, content=content)
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "Intervention terrain"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == [
            "Utiliser la checklist sécurité",
            "Vérifier les équipements avant intervention",
        ]

    def test_ai_exception_returns_200_with_error(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_savoir_faires_mod, raise_exc=ValueError("kaput"))
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "Activité X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"] == ["Savoir-faire non déterminé (erreur serveur)"]


# ===========================================================================
# 3. POST /propose_softskills/propose — avec IA simulée
# ===========================================================================

class TestProposeSoftskillsAI:

    def test_ai_valid_json_array_parsed(self, auth_client, monkeypatch):
        content = json.dumps([
            {"habilete": "Coopération", "niveau": "3 (Maîtrise)", "justification": "Travail en équipe requis (T1, C1)."},
            {"habilete": "Planification", "niveau": "2", "justification": "Jalons multiples (T2)."},
        ])
        _patch_client(monkeypatch, propose_softskills_mod, content=content)
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({
                "name": "Projet complexe",
                "tasks": ["Analyser le besoin", "Planifier les jalons"],
                "constraints": [{"name": "Délai serré"}],
                "outgoing": [{"performance": {"name": "Livraison", "description": "Dans les temps"}}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert len(data["proposals"]) == 2
        assert data["proposals"][0]["habilete"] == "Coopération"
        assert data["proposals"][0]["niveau"] == "3 (Maîtrise)"
        assert data["proposals"][1]["niveau"] == "2 (Acquisition)"

    def test_ai_json_wrapped_in_backticks_is_cleaned(self, auth_client, monkeypatch):
        content = "```json\n[{\"habilete\": \"Synthèse\", \"niveau\": \"1\", \"justification\": \"OK\"}]\n```"
        _patch_client(monkeypatch, propose_softskills_mod, content=content)
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Activité Y"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"][0]["habilete"] == "Synthèse"
        assert data["proposals"][0]["niveau"] == "1 (Aptitude)"

    def test_ai_single_dict_response_wrapped_into_list(self, auth_client, monkeypatch):
        content = json.dumps({"habilete": "Adaptation relationnelle", "niveau": "4", "justification": "Multi-acteurs (T1, C2)."})
        _patch_client(monkeypatch, propose_softskills_mod, content=content)
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Activité Z"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert len(data["proposals"]) == 1
        assert data["proposals"][0]["niveau"] == "4 (Excellence)"

    def test_ai_invalid_json_falls_back_to_text_lines(self, auth_client, monkeypatch):
        content = "- Communication\n- Rigueur\n"
        _patch_client(monkeypatch, propose_softskills_mod, content=content)
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Activité W"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert any(p["habilete"] == "Communication" for p in data["proposals"])

    def test_ai_empty_response_uses_default_proposal(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_softskills_mod, content="   ")
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Activité V"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"][0]["habilete"] == "Communication professionnelle"

    def test_ai_exception_returns_200_with_default_proposal(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_softskills_mod, raise_exc=RuntimeError("boom"))
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Activité U"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"][0]["habilete"] == "Habileté non déterminée (erreur serveur)."

    def test_ai_english_lang_valid_json(self, auth_client, monkeypatch):
        content = json.dumps([{"habilete": "Cooperation", "niveau": "3", "justification": "Team work (T1)."}])
        _patch_client(monkeypatch, propose_softskills_mod, content=content)
        with _lang(auth_client, "en"):
            r = auth_client.post(
                "/propose_softskills/propose",
                data=json.dumps({"name": "Complex project"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"][0]["niveau"] == "3 (Proficient)"


# ===========================================================================
# 4. POST /propose_aptitudes/propose & /propose_aptitudes/feasibility — avec IA
# ===========================================================================

class TestProposeAptitudesAI:

    VALID_SCORING = {
        "vision": {"niveau": "0 (Aucune)", "risque": "Pas d'exigence visuelle particulière", "leviers": []},
        "auditif": {"niveau": "1 (Faible)", "risque": "Échanges oraux occasionnels", "leviers": ["Interprétariat si besoin"]},
        "physique": {"haut_du_corps": "1 (Faible)", "bas_du_corps": "0 (Aucune)", "fatigabilite": "1 (Faible)", "risque": "Saisie ponctuelle", "leviers": []},
        "environnemental": {"niveau": "0 (Aucune)", "risque": "Environnement calme", "leviers": []},
        "exposition_risque": {"niveau": "0 (Aucune)", "risque": "Aucune exposition", "leviers": []},
        "profils_valorisables": [],
    }

    def test_propose_ai_valid_json_returns_parsed_proposals(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_aptitudes_mod, content=json.dumps(self.VALID_SCORING))
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Contrôle qualité", "description": "Vérification visuelle de pièces"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"]["vision"]["niveau"] == "0 (Aucune)"
        assert "error" not in data

    def test_propose_ai_invalid_json_returns_error_field(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_aptitudes_mod, content="ceci n'est pas du JSON")
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Activité"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_propose_ai_exception_returns_200_with_error(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_aptitudes_mod, raise_exc=RuntimeError("boom"))
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Activité"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_propose_ai_english_lang(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_aptitudes_mod, content=json.dumps(self.VALID_SCORING))
        with _lang(auth_client, "en"):
            r = auth_client.post(
                "/propose_aptitudes/propose",
                data=json.dumps({"name": "Quality control"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"]["vision"]["niveau"] == "0 (Aucune)"

    VALID_FEASIBILITY = {
        "statut": "OK avec adaptations",
        "mesures_deja_en_place": ["Poste ergonomique"],
        "ajouts_recommandes": ["Logiciel de grossissement d'écran"],
        "a_ajuster": [],
        "risque_residuel": "Faible avec les aménagements proposés.",
        "points_a_instruire": [],
        "commentaire": "Faisabilité confirmée sous réserve d'aménagements simples.",
    }

    def test_feasibility_ai_valid_json_returns_parsed_result(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_aptitudes_mod, content=json.dumps(self.VALID_FEASIBILITY))
        payload = {
            "activity_name": "Saisie de données",
            "inclusion_scoring_json": self.VALID_SCORING,
            "profil_fonctionnel": {"vision": "réduite", "motricite_fine": "normale"},
            "assistive_products": ["Loupe électronique"],
        }
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"]["statut"] == "OK avec adaptations"
        assert "error" not in data

    def test_feasibility_ai_invalid_json_returns_error_field(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_aptitudes_mod, content="pas du JSON du tout")
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "Activité"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data

    def test_feasibility_ai_dict_scoring_json_serialized(self, auth_client, monkeypatch):
        """inclusion_scoring_json fourni en dict (pas string) doit être sérialisé sans crash."""
        _patch_client(monkeypatch, propose_aptitudes_mod, content=json.dumps(self.VALID_FEASIBILITY))
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({
                "activity_name": "Activité",
                "inclusion_scoring_json": self.VALID_SCORING,
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"]["statut"] == "OK avec adaptations"

    def test_feasibility_ai_exception_returns_200_with_error(self, auth_client, monkeypatch):
        _patch_client(monkeypatch, propose_aptitudes_mod, raise_exc=RuntimeError("boom"))
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "Activité"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data
