# tests/test_51_propose_ia_avance.py
"""
Tests avancés des routes de proposition IA (/propose_aptitudes, /propose_softskills,
/propose_savoirs, /propose_savoir_faires).

test_22_propose_ia.py ne couvre que le chemin "sans clé OpenAI" (fallback).
Ce fichier mocke `openai_client_or_none` pour exercer le chemin "avec IA" :
parsing JSON réussi, JSON invalide, exception du client, variantes de langue,
et les fonctions utilitaires pures (clean_json_response, build_activity_summary).
"""
import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.propose_ia_avance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_client(content):
    """Client OpenAI factice dont chat.completions.create renvoie `content`."""
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    return client


def _broken_client(exc=RuntimeError("boom")):
    client = MagicMock()
    client.chat.completions.create.side_effect = exc
    return client


def _set_lang(client, lang):
    with client.session_transaction() as sess:
        sess["lang"] = lang


def _reset_lang(client):
    with client.session_transaction() as sess:
        sess.pop("lang", None)


# ===========================================================================
# 1. clean_json_response (propose_aptitudes.py) — fonction pure
# ===========================================================================

class TestCleanJsonResponseAptitudes:

    def test_strips_markdown_fences(self):
        from Code.routes.propose_aptitudes import clean_json_response
        raw = '```json\n{"a": 1}\n```'
        assert clean_json_response(raw) == '{"a": 1}'

    def test_extracts_object_with_surrounding_text(self):
        from Code.routes.propose_aptitudes import clean_json_response
        raw = 'Voici le résultat : {"a": 1} Merci.'
        assert clean_json_response(raw) == '{"a": 1}'

    def test_extracts_array(self):
        from Code.routes.propose_aptitudes import clean_json_response
        assert clean_json_response("[1, 2, 3]") == "[1, 2, 3]"

    def test_no_json_returns_original_text(self):
        from Code.routes.propose_aptitudes import clean_json_response
        raw = "pas de json ici"
        assert clean_json_response(raw) == raw

    def test_picks_earliest_bracket_or_brace(self):
        from Code.routes.propose_aptitudes import clean_json_response
        raw = 'prefix [1,2] {"a":1} suffix'
        assert clean_json_response(raw) == "[1,2]"


# ===========================================================================
# 2. build_activity_summary (propose_aptitudes.py) — fonction pure
# ===========================================================================

class TestBuildActivitySummary:

    def test_uses_description(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        assert "Une activité" in build_activity_summary({"description": "Une activité"})

    def test_lists_tools(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        result = build_activity_summary({"tools": ["Excel", "SAP"]})
        assert "Excel" in result and "SAP" in result

    def test_lists_outils_alias(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        assert "Word" in build_activity_summary({"outils": ["Word"]})

    def test_lists_constraints(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        assert "Délai 24h" in build_activity_summary({"constraints": ["Délai 24h"]})

    def test_lists_tasks_as_dicts(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        result = build_activity_summary({"tasks": [{"description": "Vérifier"}]})
        assert "T1: Vérifier" in result

    def test_lists_tasks_as_strings(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        assert "T1: Analyser" in build_activity_summary({"tasks": ["Analyser"]})

    def test_lists_outgoing_performance(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        activity = {"outgoing": [{"performance": {"name": "Qualité", "description": "Zéro défaut"}}]}
        result = build_activity_summary(activity)
        assert "Qualité" in result and "Zéro défaut" in result

    def test_empty_activity_returns_default(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        assert build_activity_summary({}) == "Non renseigné"


# ===========================================================================
# 3. POST /propose_aptitudes/propose — avec IA mockée
# ===========================================================================

class TestProposeAptitudesMockedSuccess:

    def test_valid_json_response_returns_proposals(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        content = json.dumps({"vision": {"niveau": "0 (Aucune)", "risque": "rien", "leviers": []}})
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_aptitudes/propose",
                data=json.dumps({"name": "Saisie"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"]["vision"]["niveau"] == "0 (Aucune)"

    def test_markdown_fenced_json_is_parsed(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        content = "```json\n" + json.dumps({"vision": {"niveau": "1 (Faible)"}}) + "\n```"
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_aptitudes/propose", data=json.dumps({}), content_type="application/json"
            )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"]["vision"]["niveau"] == "1 (Faible)"

    def test_invalid_json_returns_empty_proposals_and_error(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client("not json at all"), None)):
            r = auth_client.post(
                "/propose_aptitudes/propose", data=json.dumps({}), content_type="application/json"
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_client_exception_returns_200_with_error(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_broken_client(), None)):
            r = auth_client.post(
                "/propose_aptitudes/propose", data=json.dumps({}), content_type="application/json"
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_full_payload_reaches_ai_and_returns_parsed_result(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        content = json.dumps({"exposition_risque": {"niveau": "2 (Moderee)", "risque": "chute", "leviers": ["EPI"]}})
        payload = {
            "name": "Intervention terrain",
            "description": "Inspection en hauteur",
            "tools": ["Harnais"],
            "constraints": ["Délai 2h"],
            "tasks": [{"description": "Grimper"}],
        }
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_aptitudes/propose", data=json.dumps(payload), content_type="application/json"
            )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"]["exposition_risque"]["niveau"] == "2 (Moderee)"


class TestProposeFeasibilityMockedSuccess:

    def test_valid_json_returns_result(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        content = json.dumps({"statut": "OK", "mesures_deja_en_place": []})
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_aptitudes/feasibility",
                data=json.dumps({"activity_name": "X"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        assert json.loads(r.data)["result"]["statut"] == "OK"

    def test_dict_inclusion_scoring_json_is_serialized_without_crash(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        content = json.dumps({"statut": "A instruire"})
        payload = {"activity_name": "Y", "inclusion_scoring_json": {"vision": {"niveau": "1"}}}
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_aptitudes/feasibility", data=json.dumps(payload), content_type="application/json"
            )
        assert r.status_code == 200
        assert json.loads(r.data)["result"]["statut"] == "A instruire"

    def test_invalid_json_returns_empty_result_and_error(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client("garbage"), None)):
            r = auth_client.post(
                "/propose_aptitudes/feasibility", data=json.dumps({}), content_type="application/json"
            )
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data

    def test_client_exception_returns_200_with_error(self, auth_client):
        from Code.routes import propose_aptitudes as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_broken_client(), None)):
            r = auth_client.post(
                "/propose_aptitudes/feasibility", data=json.dumps({}), content_type="application/json"
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data


# ===========================================================================
# 4. POST /propose_softskills/propose — avec IA mockée
# ===========================================================================

class TestProposeSoftskillsMockedSuccess:

    def test_valid_json_array_maps_niveau_fr(self, auth_client):
        from Code.routes import propose_softskills as mod
        content = json.dumps([{"habilete": "Coopération", "niveau": "3", "justification": "car..."}])
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_softskills/propose", data=json.dumps({"name": "Test"}), content_type="application/json"
            )
        assert r.status_code == 200
        data = json.loads(r.data)["proposals"]
        assert data[0]["habilete"] == "Coopération"
        assert data[0]["niveau"] == "3 (Maîtrise)"

    def test_valid_json_object_is_wrapped_as_list(self, auth_client):
        from Code.routes import propose_softskills as mod
        content = json.dumps({"habilete": "Solo", "niveau": "4"})
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_softskills/propose", data=json.dumps({}), content_type="application/json"
            )
        data = json.loads(r.data)["proposals"]
        assert len(data) == 1
        assert data[0]["niveau"] == "4 (Excellence)"

    def test_lang_en_maps_niveau_english(self, auth_client):
        from Code.routes import propose_softskills as mod
        content = json.dumps([{"habilete": "Cooperation", "niveau": "2"}])
        _set_lang(auth_client, "en")
        try:
            with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
                r = auth_client.post(
                    "/propose_softskills/propose", data=json.dumps({}), content_type="application/json"
                )
            data = json.loads(r.data)["proposals"]
            assert data[0]["niveau"] == "2 (Developing)"
        finally:
            _reset_lang(auth_client)

    def test_unknown_niveau_falls_back_to_default(self, auth_client):
        from Code.routes import propose_softskills as mod
        content = json.dumps([{"habilete": "X", "niveau": "9"}])
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_softskills/propose", data=json.dumps({}), content_type="application/json"
            )
        data = json.loads(r.data)["proposals"]
        assert data[0]["niveau"] == "2 (Acquisition)"

    def test_unparseable_json_falls_back_to_line_splitting(self, auth_client):
        from Code.routes import propose_softskills as mod
        content = "- Coopération renforcée\n- Auto-régulation avancée"
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_softskills/propose", data=json.dumps({}), content_type="application/json"
            )
        habiletes = [p["habilete"] for p in json.loads(r.data)["proposals"]]
        assert "Coopération renforcée" in habiletes

    def test_totally_empty_response_uses_default_proposal(self, auth_client):
        from Code.routes import propose_softskills as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(""), None)):
            r = auth_client.post(
                "/propose_softskills/propose", data=json.dumps({}), content_type="application/json"
            )
        data = json.loads(r.data)["proposals"]
        assert len(data) == 1
        assert data[0]["habilete"] == "Communication professionnelle"

    def test_client_exception_returns_default_error_proposal(self, auth_client):
        from Code.routes import propose_softskills as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_broken_client(), None)):
            r = auth_client.post(
                "/propose_softskills/propose", data=json.dumps({}), content_type="application/json"
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"][0]["habilete"] == "Habileté non déterminée (erreur serveur)."

    def test_tasks_and_constraints_are_reflected_in_prompt(self, auth_client):
        from Code.routes import propose_softskills as mod
        client = _mock_client(json.dumps([{"habilete": "X", "niveau": "1"}]))
        payload = {"tasks": [{"description": "Animer une réunion"}], "constraints": [{"description": "Délai serré"}]}
        with patch.object(mod, "openai_client_or_none", return_value=(client, None)):
            r = auth_client.post(
                "/propose_softskills/propose", data=json.dumps(payload), content_type="application/json"
            )
        assert r.status_code == 200
        prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "Animer une réunion" in prompt
        assert "Délai serré" in prompt


# ===========================================================================
# 5. POST /propose_savoirs/propose — avec IA mockée
# ===========================================================================

class TestProposeSavoirsMockedSuccess:

    def test_valid_response_returns_bullet_lines(self, auth_client):
        from Code.routes import propose_savoirs as mod
        content = "- Règles de nomenclature\n- Procédure interne de transfert"
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_savoirs/propose", data=json.dumps({"name": "Test"}), content_type="application/json"
            )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert "Règles de nomenclature" in proposals
        assert "Procédure interne de transfert" in proposals

    def test_with_savoir_faires_context_included_in_prompt(self, auth_client):
        from Code.routes import propose_savoirs as mod
        client = _mock_client("- Connaissance A")
        payload = {"name": "Test", "savoir_faires": ["Utiliser ERP"]}
        with patch.object(mod, "openai_client_or_none", return_value=(client, None)):
            r = auth_client.post(
                "/propose_savoirs/propose", data=json.dumps(payload), content_type="application/json"
            )
        assert r.status_code == 200
        prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "Utiliser ERP" in prompt

    def test_lang_en_uses_english_system_message(self, auth_client):
        from Code.routes import propose_savoirs as mod
        client = _mock_client("- Knowledge A")
        _set_lang(auth_client, "en")
        try:
            with patch.object(mod, "openai_client_or_none", return_value=(client, None)):
                r = auth_client.post(
                    "/propose_savoirs/propose", data=json.dumps({}), content_type="application/json"
                )
            assert r.status_code == 200
            system_msg = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
            assert "precise and concise HR" in system_msg
        finally:
            _reset_lang(auth_client)

    def test_client_exception_returns_error_message(self, auth_client):
        from Code.routes import propose_savoirs as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_broken_client(), None)):
            r = auth_client.post(
                "/propose_savoirs/propose", data=json.dumps({}), content_type="application/json"
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"] == ["Savoir non déterminé (erreur serveur)"]


# ===========================================================================
# 6. POST /propose_savoir_faires/propose — avec IA mockée
# ===========================================================================

class TestProposeSavoirFairesMockedSuccess:

    def test_valid_response_returns_bullet_lines(self, auth_client):
        from Code.routes import propose_savoir_faires as mod
        content = "- Utiliser le logiciel ERP\n- Vérifier les écarts de stock"
        with patch.object(mod, "openai_client_or_none", return_value=(_mock_client(content), None)):
            r = auth_client.post(
                "/propose_savoir_faires/propose",
                data=json.dumps({"name": "Gestion du stock"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert "Utiliser le logiciel ERP" in proposals
        assert "Vérifier les écarts de stock" in proposals

    def test_lang_en_uses_english_system_message(self, auth_client):
        from Code.routes import propose_savoir_faires as mod
        client = _mock_client("- Use the ERP tool")
        _set_lang(auth_client, "en")
        try:
            with patch.object(mod, "openai_client_or_none", return_value=(client, None)):
                r = auth_client.post(
                    "/propose_savoir_faires/propose", data=json.dumps({}), content_type="application/json"
                )
            assert r.status_code == 200
            system_msg = client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
            assert "precise and concise HR" in system_msg
        finally:
            _reset_lang(auth_client)

    def test_client_exception_returns_error_message(self, auth_client):
        from Code.routes import propose_savoir_faires as mod
        with patch.object(mod, "openai_client_or_none", return_value=(_broken_client(), None)):
            r = auth_client.post(
                "/propose_savoir_faires/propose", data=json.dumps({}), content_type="application/json"
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"] == ["Savoir-faire non déterminé (erreur serveur)"]
