# tests/test_22_propose_ia.py
"""
API : Propositions IA (/propose_savoirs, /propose_savoir_faires, /propose_softskills,
                        /propose_aptitudes) + Compétences CRUD (/skills)
                        + Items Activité (/your_api/activity_items)

Sans clé OPENAI_API_KEY (environnement de test) :
  - propose_savoirs, propose_savoir_faires, propose_softskills, propose_aptitudes → 200 + fallback
  - skills.propose → 400 si pas de tâches, 500 si tâches présentes mais pas de clé
  - activity_items → 200 + JSON (pur SQL, sans IA)
  - skills CRUD (add/update/delete) → 200/201/404 sans dépendance externe
"""
import json
import pytest

pytestmark = pytest.mark.propose_ia


# ---------------------------------------------------------------------------
# Fake OpenAI client — simule le SDK openai sans appel réseau réel, pour
# couvrir les branches "avec clé" (succès + parsing + exception) des routes
# propose_savoirs / propose_savoir_faires / propose_softskills / propose_aptitudes.
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


class _FakeOpenAIClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_openai(monkeypatch, module, content=None, raise_exc=None):
    """Patche openai_client_or_none() importé dans <module> pour renvoyer un faux client."""
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        f"Code.routes.{module}.openai_client_or_none",
        lambda: (fake_client, None),
    )


def _mock_skills_ai(monkeypatch, content=None, raise_exc=None):
    """Simule une clé OpenAI + client IA fonctionnels pour /skills/propose.

    skills.py construit son client via `from Code.ai_client import make_ai_client`
    importé localement dans la fonction : on patche la source, pas la référence
    locale à skills.py (qui n'existe qu'au moment de l'appel).
    """
    monkeypatch.setattr("Code.routes.skills.get_openai_key", lambda: "sk-fake-key")
    fake_client = _FakeOpenAIClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.ai_client.make_ai_client",
        lambda *a, **kw: (fake_client, "gpt-4o-mini", None),
    )


def _lang_client(app, lang):
    """Client isolé (non partagé) avec la langue de session forcée."""
    fresh = app.test_client()
    with fresh.session_transaction() as sess:
        sess["lang"] = lang
    return fresh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_competency(app, activity_id, description="Compétence test IA"):
    with app.app_context():
        from Code.models.models import Competency
        from Code.extensions import db
        comp = Competency(activity_id=activity_id, description=description)
        db.session.add(comp)
        db.session.commit()
        return comp.id


def _delete_competency(app, comp_id):
    with app.app_context():
        from Code.models.models import Competency
        from Code.extensions import db
        c = Competency.query.get(comp_id)
        if c:
            db.session.delete(c)
            db.session.commit()


# ===========================================================================
# 1. POST /propose_savoirs/propose
# ===========================================================================

class TestProposeSavoirs:

    def test_fallback_no_openai_key_returns_200(self, auth_client):
        """Sans clé OpenAI, retourne 200 + liste non vide de proposals."""
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Activité Test Savoirs"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "proposals" in data
        assert isinstance(data["proposals"], list)
        assert len(data["proposals"]) > 0

    def test_fallback_source_field_present(self, auth_client):
        """La réponse fallback expose un champ 'source' mentionnant la clé manquante."""
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "source" in data
        assert data["source"]  # non vide

    def test_empty_body_no_crash(self, auth_client):
        """Corps JSON vide → 200 sans crash."""
        r = auth_client.post(
            "/propose_savoirs/propose",
            data="{}",
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_proposals_are_non_empty_strings(self, auth_client):
        """Chaque proposition fallback est une chaîne non vide."""
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Traitement des commandes"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert all(isinstance(p, str) and len(p.strip()) > 0 for p in proposals)

    def test_with_savoir_faires_context(self, auth_client):
        """Payload incluant savoir_faires → 200 sans crash."""
        payload = {
            "name": "Gestion du stock",
            "description": "Contrôle et mise à jour des inventaires",
            "savoir_faires": ["Utiliser le logiciel ERP", "Vérifier les écarts"],
        }
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data["proposals"], list)

    def test_fallback_returns_at_least_three_proposals(self, auth_client):
        """Le fallback renvoie au moins 3 propositions (dummy_from_context)."""
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) >= 3

    def test_with_openai_key_success_returns_parsed_lines(self, app, monkeypatch):
        """Avec client OpenAI mocké (succès), les puces de la réponse sont nettoyées et renvoyées."""
        _mock_openai(
            monkeypatch, "propose_savoirs",
            content="- Règles de nomenclature catalogue\n- Procédure interne de transfert\n\n- Principes qualité",
        )
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_savoirs/propose",
                data=json.dumps({"name": "Gestion catalogue", "savoir_faires": ["Utiliser l'ERP"]}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "source" not in data
        assert data["proposals"] == [
            "Règles de nomenclature catalogue",
            "Procédure interne de transfert",
            "Principes qualité",
        ]

    def test_with_openai_key_english_lang_success(self, app, monkeypatch):
        """Langue de session 'en' → la route répond toujours 200 sans erreur (branche EN exécutée)."""
        _mock_openai(monkeypatch, "propose_savoirs", content="- Catalogue naming rules\n- Internal transfer procedure")
        fresh = _lang_client(app, "en")
        r = fresh.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Catalog management"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"] == ["Catalogue naming rules", "Internal transfer procedure"]

    def test_with_openai_key_exception_returns_fallback_error_fr(self, app, monkeypatch):
        """Si le client OpenAI lève une exception → 200 + message d'erreur FR + champ 'error'."""
        _mock_openai(monkeypatch, "propose_savoirs", raise_exc=RuntimeError("boom"))
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post(
                "/propose_savoirs/propose",
                data=json.dumps({"name": "X"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"] == ["Savoir non déterminé (erreur serveur)"]

    def test_with_openai_key_exception_returns_fallback_error_en(self, app, monkeypatch):
        """Exception + langue 'en' → message d'erreur en anglais."""
        _mock_openai(monkeypatch, "propose_savoirs", raise_exc=RuntimeError("boom"))
        fresh = _lang_client(app, "en")
        r = fresh.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == ["Knowledge not determined (server error)"]


# ===========================================================================
# 2. POST /propose_savoir_faires/propose
# ===========================================================================

class TestProposeSavoirFaires:

    def test_fallback_returns_200_with_proposals(self, auth_client):
        """Sans clé OpenAI, retourne 200 + liste non vide."""
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "Activité Test SF"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "proposals" in data
        assert len(data["proposals"]) > 0

    def test_proposals_are_strings(self, auth_client):
        """Les proposals fallback sont des chaînes non vides."""
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert all(isinstance(p, str) and len(p.strip()) > 0 for p in proposals)

    def test_source_field_present(self, auth_client):
        """Champ 'source' présent dans la réponse fallback."""
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = json.loads(r.data)
        assert "source" in data

    def test_with_full_activity_context(self, auth_client):
        """Payload riche (tâches, outils, contraintes) → 200 sans crash."""
        payload = {
            "name": "Analyse des risques",
            "tasks": ["Identifier les risques", "Évaluer les impacts"],
            "tools": ["Excel", "AMDEC"],
            "constraints": ["Délai 48h"],
        }
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_fallback_at_least_three_items(self, auth_client):
        """Le fallback renvoie au moins 3 items (dummy_from_context)."""
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) >= 3

    def test_with_openai_key_success_returns_parsed_lines(self, app, monkeypatch):
        """Avec client OpenAI mocké (succès), les puces sont nettoyées et renvoyées."""
        _mock_openai(
            monkeypatch, "propose_savoir_faires",
            content="- Utiliser le logiciel ERP\n• Vérifier les écarts d'inventaire\n\n- Documenter les anomalies",
        )
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_savoir_faires/propose",
                data=json.dumps({"name": "Gestion du stock"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "source" not in data
        assert data["proposals"] == [
            "Utiliser le logiciel ERP",
            "Vérifier les écarts d'inventaire",
            "Documenter les anomalies",
        ]

    def test_with_openai_key_english_lang_success(self, app, monkeypatch):
        """Langue de session 'en' → la route répond 200 (branche EN exécutée)."""
        _mock_openai(monkeypatch, "propose_savoir_faires", content="- Use the ERP software\n- Verify inventory gaps")
        fresh = _lang_client(app, "en")
        r = fresh.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "Stock management"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"] == ["Use the ERP software", "Verify inventory gaps"]

    def test_with_openai_key_exception_returns_fallback_error_fr(self, app, monkeypatch):
        """Exception côté client OpenAI → 200 + message d'erreur FR + champ 'error'."""
        _mock_openai(monkeypatch, "propose_savoir_faires", raise_exc=RuntimeError("boom"))
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post(
                "/propose_savoir_faires/propose",
                data=json.dumps({"name": "X"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"] == ["Savoir-faire non déterminé (erreur serveur)"]

    def test_with_openai_key_exception_returns_fallback_error_en(self, app, monkeypatch):
        """Exception + langue 'en' → message d'erreur en anglais."""
        _mock_openai(monkeypatch, "propose_savoir_faires", raise_exc=RuntimeError("boom"))
        fresh = _lang_client(app, "en")
        r = fresh.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == ["Practical skill not determined (server error)"]


# ===========================================================================
# 3. POST /propose_softskills/propose
# ===========================================================================

class TestProposeSoftskills:

    def test_fallback_returns_200_with_proposals(self, auth_client):
        """Sans clé OpenAI, retourne 200 + liste de proposals HSC."""
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Coordination de projet"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "proposals" in data
        assert isinstance(data["proposals"], list)
        assert len(data["proposals"]) > 0

    def test_proposals_have_habilete_field(self, auth_client):
        """Chaque proposal HSC contient le champ 'habilete'."""
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        for p in proposals:
            assert "habilete" in p
            assert isinstance(p["habilete"], str)

    def test_proposals_have_niveau_field(self, auth_client):
        """Chaque proposal HSC contient le champ 'niveau'."""
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        proposals = json.loads(r.data)["proposals"]
        for p in proposals:
            assert "niveau" in p

    def test_proposals_have_justification_field(self, auth_client):
        """Chaque proposal HSC contient le champ 'justification'."""
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        proposals = json.loads(r.data)["proposals"]
        for p in proposals:
            assert "justification" in p

    def test_source_field_in_fallback(self, auth_client):
        """Champ 'source' présent dans la réponse fallback."""
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        data = json.loads(r.data)
        assert "source" in data

    def test_with_tasks_and_constraints(self, auth_client):
        """Payload avec tâches et contraintes → 200 sans crash."""
        payload = {
            "name": "Management opérationnel",
            "tasks": [{"name": "Animer des réunions"}, {"name": "Suivre les indicateurs"}],
            "constraints": [{"name": "Délais serrés"}],
        }
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_with_openai_key_valid_json_array_success(self, app, monkeypatch):
        """Réponse IA = tableau JSON valide → proposals structurées avec niveau mappé."""
        content = json.dumps([
            {"habilete": "Coopération", "niveau": "3 (Maîtrise)", "justification": "Travail multi-acteurs."},
            {"habilete": "Synthèse", "niveau": "2", "justification": "Rédaction de comptes rendus."},
        ])
        _mock_openai(monkeypatch, "propose_softskills", content=content)
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post(
                "/propose_softskills/propose",
                data=json.dumps({
                    "name": "Coordination de projet",
                    "tasks": [{"description": "Animer des réunions"}],
                    "constraints": [{"description": "Délais serrés"}],
                    "outgoing": [{"performance": {"name": "Livraison", "description": "À date"}}],
                }),
                content_type="application/json",
            )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 2
        assert proposals[0] == {"habilete": "Coopération", "niveau": "3 (Maîtrise)", "justification": "Travail multi-acteurs."}
        assert proposals[1]["niveau"] == "2 (Acquisition)"

    def test_with_openai_key_single_dict_response_is_wrapped(self, app, monkeypatch):
        """Réponse IA = objet JSON unique (pas un tableau) → transformé en liste à 1 élément."""
        content = json.dumps({"habilete": "Planification", "niveau": 4, "justification": "Jalons multiples."})
        _mock_openai(monkeypatch, "propose_softskills", content=content)
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 1
        assert proposals[0]["habilete"] == "Planification"
        assert proposals[0]["niveau"] == "4 (Excellence)"

    def test_with_openai_key_english_lang_success(self, app, monkeypatch):
        """Langue 'en' → niveau mappé sur le libellé anglais correspondant."""
        content = json.dumps([{"habilete": "Cooperation", "niveau": "1", "justification": "Team work."}])
        _mock_openai(monkeypatch, "propose_softskills", content=content)
        fresh = _lang_client(app, "en")
        r = fresh.post("/propose_softskills/propose", data=json.dumps({"name": "Ops"}), content_type="application/json")
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert proposals[0]["niveau"] == "1 (Basic)"

    def test_with_openai_key_invalid_json_falls_back_to_text_lines(self, app, monkeypatch):
        """Réponse IA non-JSON → repli sur un parsing ligne par ligne du texte brut."""
        _mock_openai(monkeypatch, "propose_softskills", content="- Coopération renforcée\n- Synthèse rapide des échanges")
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 2
        assert proposals[0]["habilete"] == "Coopération renforcée"
        assert proposals[0]["niveau"] == "2 (Acquisition)"
        assert proposals[0]["justification"] == ""

    def test_with_openai_key_empty_json_array_uses_default_entry(self, app, monkeypatch):
        """Réponse IA = tableau JSON vide et aucune ligne exploitable → entrée par défaut."""
        _mock_openai(monkeypatch, "propose_softskills", content="[]")
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 1
        assert proposals[0]["habilete"] == "Communication professionnelle"

    def test_with_openai_key_unknown_niveau_uses_default_level(self, app, monkeypatch):
        """Un niveau non reconnu (hors 1-4) retombe sur le niveau par défaut (2)."""
        content = json.dumps([{"habilete": "Adaptation relationnelle", "niveau": "9 (Inconnu)", "justification": "X"}])
        _mock_openai(monkeypatch, "propose_softskills", content=content)
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        proposals = json.loads(r.data)["proposals"]
        assert proposals[0]["niveau"] == "2 (Acquisition)"

    def test_with_openai_key_exception_returns_fallback_error_fr(self, app, monkeypatch):
        """Exception côté client OpenAI → 200 + entrée d'erreur FR + champ 'error'."""
        _mock_openai(monkeypatch, "propose_softskills", raise_exc=RuntimeError("boom"))
        with _lang_client(app, 'fr') as fresh:
            r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert data["proposals"][0]["habilete"] == "Habileté non déterminée (erreur serveur)."

    def test_with_openai_key_exception_returns_fallback_error_en(self, app, monkeypatch):
        """Exception + langue 'en' → entrée d'erreur en anglais."""
        _mock_openai(monkeypatch, "propose_softskills", raise_exc=RuntimeError("boom"))
        fresh = _lang_client(app, "en")
        r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"][0]["habilete"] == "Ability not determined (server error)."

    def test_with_openai_key_unclosed_bracket_falls_back_to_text_lines(self, app, monkeypatch):
        """Réponse IA avec crochet ouvrant non refermé → clean_json_response renvoie le texte brut tel quel."""
        _mock_openai(monkeypatch, "propose_softskills", content="[Coopération renforcée sans fermeture")
        with app.test_client() as fresh:
            r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) >= 1

    def test_with_openai_key_plain_string_tasks_and_constraints(self, app, monkeypatch):
        """Tâches/contraintes en simples chaînes (pas des dicts) → branche 'else' de make_enumeration."""
        content = json.dumps([{"habilete": "Coopération", "niveau": "2", "justification": "X"}])
        _mock_openai(monkeypatch, "propose_softskills", content=content)
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_softskills/propose",
                data=json.dumps({
                    "name": "Support client",
                    "tasks": ["Répondre aux appels", "Escalader les incidents"],
                    "constraints": ["Délai de réponse 24h"],
                }),
                content_type="application/json",
            )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"][0]["habilete"] == "Coopération"

    def test_with_openai_key_empty_result_english_uses_default_entry(self, app, monkeypatch):
        """Tableau JSON vide + langue 'en' + aucune ligne exploitable → entrée par défaut anglaise."""
        _mock_openai(monkeypatch, "propose_softskills", content="[]")
        fresh = _lang_client(app, "en")
        r = fresh.post("/propose_softskills/propose", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert proposals[0]["habilete"] == "Professional Communication"


# ===========================================================================
# 4. POST /propose_aptitudes/propose  &  /propose_aptitudes/feasibility
# ===========================================================================

class TestProposeAptitudes:

    def test_propose_returns_200_fallback(self, auth_client):
        """Sans clé OpenAI, /propose_aptitudes/propose retourne 200."""
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Contrôle qualité"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "proposals" in data

    def test_propose_source_field_present(self, auth_client):
        """Champ 'source' présent dans la réponse fallback."""
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "source" in data

    def test_propose_empty_body_no_crash(self, auth_client):
        """Corps vide → 200 sans crash."""
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data="{}",
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_propose_full_payload_no_crash(self, auth_client):
        """Payload complet (description, tools, tasks, outgoing) → 200."""
        payload = {
            "name": "Intervention terrain",
            "description": "Inspection sur site avec équipements de sécurité",
            "tools": ["EPI", "Checklist sécurité"],
            "tasks": ["Vérifier les équipements", "Rédiger le rapport"],
            "constraints": [{"name": "Délai 2h"}],
        }
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_feasibility_returns_200_fallback(self, auth_client):
        """Sans clé OpenAI, /propose_aptitudes/feasibility retourne 200."""
        payload = {
            "activity_name": "Saisie de données",
            "inclusion_scoring_json": {},
            "profil_fonctionnel": {
                "vision": "normale",
                "audition": "normale",
                "motricite_fine": "normale",
                "mobilite_posture": "normale",
                "endurance": "normale",
                "sensibilite_env": "faible",
            },
            "assistive_products": [],
        }
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "result" in data

    def test_feasibility_empty_body_no_crash(self, auth_client):
        """Corps vide pour feasibility → 200 sans crash."""
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data="{}",
            content_type="application/json",
        )
        assert r.status_code == 200

    def test_feasibility_source_field_present(self, auth_client):
        """Champ 'source' dans la réponse fallback de feasibility."""
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data="{}",
            content_type="application/json",
        )
        data = json.loads(r.data)
        assert "source" in data

    def test_feasibility_with_assistive_list(self, auth_client):
        """Liste assistive_products peuplée → 200 sans crash."""
        payload = {
            "activity_name": "Accueil téléphonique",
            "profil_fonctionnel": {"audition": "déficit léger"},
            "assistive_products": ["Amplificateur de son", "Boucle magnétique"],
        }
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200

    # -- /propose --------------------------------------------------------

    def test_propose_with_openai_key_success_full_payload(self, app, monkeypatch):
        """Succès avec payload riche (description, outils, contraintes, tâches, performance)."""
        content = json.dumps({
            "vision": {"niveau": "1 (Faible)", "risque": "Ecran prolongé", "leviers": ["Zoom logiciel"]},
            "exposition_risque": {"niveau": "2 (Moderee)", "risque": "Terrain", "leviers": ["EPI"]},
        })
        _mock_openai(monkeypatch, "propose_aptitudes", content=content)
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_aptitudes/propose",
                data=json.dumps({
                    "title": "Intervention terrain",
                    "description": "Inspection sur site",
                    "tools": ["EPI", "Checklist"],
                    "constraints": ["Délai 2h"],
                    "tasks": [{"description": "Vérifier les équipements"}, "Rédiger le rapport"],
                    "outgoing": [{"performance": {"name": "Conformité", "description": "0 défaut"}}],
                    "competences_text": "Lecture de plans",
                    "savoirs_text": "Normes sécurité",
                    "savoir_faire_text": "Utiliser un détecteur",
                    "hsc_context": "Vigilance",
                }),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" not in data
        assert data["proposals"]["vision"]["niveau"] == "1 (Faible)"

    def test_propose_with_openai_key_empty_payload_uses_defaults(self, app, monkeypatch):
        """Payload vide en succès → nom/summary par défaut ('Non renseigné'), pas de crash."""
        _mock_openai(monkeypatch, "propose_aptitudes", content=json.dumps({"vision": {"niveau": "0 (Aucune)"}}))
        with app.test_client() as fresh:
            r = fresh.post("/propose_aptitudes/propose", data="{}", content_type="application/json")
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"]["vision"]["niveau"] == "0 (Aucune)"

    def test_propose_with_openai_key_english_lang_success(self, app, monkeypatch):
        """Langue 'en' → branche EN exécutée sans erreur."""
        _mock_openai(monkeypatch, "propose_aptitudes", content=json.dumps({"vision": {"niveau": "1 (Low)"}}))
        fresh = _lang_client(app, "en")
        r = fresh.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Quality control"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"]["vision"]["niveau"] == "1 (Low)"

    def test_propose_with_openai_key_invalid_json_returns_error(self, app, monkeypatch):
        """Réponse IA non-JSON → 200 + proposals={} + champ 'error' (échec de parsing)."""
        _mock_openai(monkeypatch, "propose_aptitudes", content="Ceci n'est pas du JSON valide {{{")
        with app.test_client() as fresh:
            r = fresh.post("/propose_aptitudes/propose", data=json.dumps({"name": "X"}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_propose_with_openai_key_exception_returns_error(self, app, monkeypatch):
        """Exception côté client OpenAI → 200 + proposals={} + champ 'error'."""
        _mock_openai(monkeypatch, "propose_aptitudes", raise_exc=RuntimeError("boom"))
        with app.test_client() as fresh:
            r = fresh.post("/propose_aptitudes/propose", data=json.dumps({"name": "X"}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_propose_with_openai_key_no_brackets_returns_error(self, app, monkeypatch):
        """Réponse IA sans '[' ni '{' → clean_json_response renvoie le texte tel quel → échec parsing."""
        _mock_openai(monkeypatch, "propose_aptitudes", content="Reponse totalement libre sans structure JSON")
        with app.test_client() as fresh:
            r = fresh.post("/propose_aptitudes/propose", data=json.dumps({"name": "X"}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_propose_with_openai_key_bare_array_response(self, app, monkeypatch):
        """Réponse IA = tableau JSON sans accolade (ex: [1, 2, 3]) → extraction par crochets."""
        _mock_openai(monkeypatch, "propose_aptitudes", content="[1, 2, 3]")
        with app.test_client() as fresh:
            r = fresh.post("/propose_aptitudes/propose", data=json.dumps({"name": "X"}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" not in data
        assert data["proposals"] == [1, 2, 3]

    # -- /feasibility ------------------------------------------------------

    def test_feasibility_with_openai_key_success_full_payload(self, app, monkeypatch):
        """Succès avec inclusion_scoring_json en dict, assistive_products peuplée, profil complet."""
        content = json.dumps({
            "statut": "OK avec adaptations",
            "mesures_deja_en_place": ["Amplificateur"],
            "ajouts_recommandes": ["Boucle magnétique"],
            "a_ajuster": [],
            "risque_residuel": "Faible",
            "points_a_instruire": [],
            "commentaire": "Adapté.",
        })
        _mock_openai(monkeypatch, "propose_aptitudes", content=content)
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_aptitudes/feasibility",
                data=json.dumps({
                    "activity_name": "Accueil téléphonique",
                    "inclusion_scoring_json": {"auditif": {"niveau": "2 (Moderee)"}},
                    "profil_fonctionnel": {"audition": "déficit léger", "vision": "normale"},
                    "commentaire_court": "RAS",
                    "assistive_products": ["Amplificateur de son", "Boucle magnétique"],
                }),
                content_type="application/json",
            )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" not in data
        assert data["result"]["statut"] == "OK avec adaptations"

    def test_feasibility_with_openai_key_no_assistive_products_default_text(self, app, monkeypatch):
        """Liste assistive_products vide → texte par défaut 'Aucune aide renseignée' (pas de crash)."""
        _mock_openai(monkeypatch, "propose_aptitudes", content=json.dumps({"statut": "A instruire"}))
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_aptitudes/feasibility",
                data=json.dumps({"activity_name": "Saisie", "assistive_products": []}),
                content_type="application/json",
            )
        assert r.status_code == 200
        assert json.loads(r.data)["result"]["statut"] == "A instruire"

    def test_feasibility_with_openai_key_non_list_assistive_products(self, app, monkeypatch):
        """assistive_products non-liste (ex: chaîne) → convertie en texte via str() sans crash."""
        _mock_openai(monkeypatch, "propose_aptitudes", content=json.dumps({"statut": "OK"}))
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_aptitudes/feasibility",
                data=json.dumps({"activity_name": "Saisie", "assistive_products": "Loupe électronique"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        assert json.loads(r.data)["result"]["statut"] == "OK"

    def test_feasibility_with_openai_key_english_lang_success(self, app, monkeypatch):
        """Langue 'en' → branche EN exécutée sans erreur."""
        _mock_openai(monkeypatch, "propose_aptitudes", content=json.dumps({"statut": "OK"}))
        fresh = _lang_client(app, "en")
        r = fresh.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "Data entry"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["result"]["statut"] == "OK"

    def test_feasibility_with_openai_key_invalid_json_returns_error(self, app, monkeypatch):
        """Réponse IA non-JSON → 200 + result={} + champ 'error'."""
        _mock_openai(monkeypatch, "propose_aptitudes", content="pas du JSON {{{")
        with app.test_client() as fresh:
            r = fresh.post("/propose_aptitudes/feasibility", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data

    def test_feasibility_with_openai_key_exception_returns_error(self, app, monkeypatch):
        """Exception côté client OpenAI → 200 + result={} + champ 'error'."""
        _mock_openai(monkeypatch, "propose_aptitudes", raise_exc=RuntimeError("boom"))
        with app.test_client() as fresh:
            r = fresh.post("/propose_aptitudes/feasibility", data=json.dumps({}), content_type="application/json")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data


# ===========================================================================
# 5. POST /skills/propose (retourne 400 sans tâches, 500 sans clé avec tâches)
# ===========================================================================

class TestSkillsPropose:

    def test_no_tasks_returns_400(self, auth_client):
        """Sans tâches dans le payload, /skills/propose retourne 400."""
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({"name": "Activité sans tâches"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_empty_tasks_list_returns_400(self, auth_client):
        """Liste de tâches vide → 400."""
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({"name": "X", "tasks": []}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_whitespace_only_tasks_returns_400(self, auth_client):
        """Tâches uniquement composées d'espaces → filtrées → 400."""
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({"name": "X", "tasks": [{"name": "  "}, {"name": "   "}]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_with_tasks_no_key_returns_500(self, auth_client):
        """Avec tâches valides mais sans clé OpenAI → 500 + message d'erreur."""
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({
                "name": "Activité avec tâches",
                "tasks": [{"name": "Analyser les données"}, {"name": "Rédiger le rapport"}],
            }),
            content_type="application/json",
        )
        assert r.status_code == 500
        data = json.loads(r.data)
        assert "error" in data

    def test_empty_body_returns_400(self, auth_client):
        """Corps vide → 400 (absence de tâches)."""
        r = auth_client.post(
            "/skills/propose",
            data="{}",
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_prompt_indisponible_retourne_500(self, auth_client, monkeypatch):
        """get_prompt() renvoie None (prompts non chargés) → 500 explicite."""
        monkeypatch.setattr("Code.routes.skills.get_prompt", lambda *a, **kw: None)
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({"name": "X", "tasks": [{"name": "Analyser"}]}),
            content_type="application/json",
        )
        assert r.status_code == 500
        assert "error" in r.get_json()

    def test_output_data_dict_et_connexions_completes_avec_ia(self, auth_client, monkeypatch):
        """Couvre les branches dict pour output_data, outgoing et tools + les 3 propositions IA."""
        _mock_skills_ai(monkeypatch, content="Analyse de données\nRédaction de rapports\nGestion des priorités")
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({
                "name": "Activité complète",
                "input_data": "Bon de commande",
                "output_data": {"text": "Rapport final"},
                "tasks": [{"name": "Analyser"}, "Rédiger"],
                "outgoing": [{"target_name": "Comptabilité"}, "Direction"],
                "tools": [{"name": "Excel"}, "CRM"],
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["proposals"] == ["Analyse de données", "Rédaction de rapports", "Gestion des priorités"]

    def test_reponse_ia_sur_une_ligne_est_decoupee_en_phrases(self, auth_client, monkeypatch):
        """Fallback : l'IA renvoie tout sur une ligne → découpage en phrases par '. '."""
        _mock_skills_ai(monkeypatch, content="Analyser les données. Rédiger le rapport. Prioriser les tâches.")
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({"name": "X", "tasks": [{"name": "Analyser"}]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = r.get_json()["proposals"]
        assert len(proposals) == 3
        assert proposals[0] == "Analyser les données"

    def test_plus_de_trois_lignes_ia_tronque_a_trois(self, auth_client, monkeypatch):
        """Plus de 3 lignes renvoyées par l'IA → tronqué à 3."""
        _mock_skills_ai(monkeypatch, content="Une\nDeux\nTrois\nQuatre")
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({"name": "X", "tasks": [{"name": "Analyser"}]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["proposals"] == ["Une", "Deux", "Trois"]

    def test_exception_ia_retourne_500(self, auth_client, monkeypatch):
        """Le client IA lève une exception → 500 avec le message d'erreur."""
        _mock_skills_ai(monkeypatch, raise_exc=RuntimeError("panne IA"))
        r = auth_client.post(
            "/skills/propose",
            data=json.dumps({"name": "X", "tasks": [{"name": "Analyser"}]}),
            content_type="application/json",
        )
        assert r.status_code == 500
        assert "panne IA" in r.get_json()["error"]


# ===========================================================================
# 6. CRUD Compétences via /skills
# ===========================================================================

class TestSkillsCRUD:

    def test_add_competency_success_returns_201(self, auth_client, ids, app):
        """POST /skills/add crée une compétence et retourne 201 + id."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "description": "Maîtriser les outils de planification",
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        assert data["activity_id"] == ids["activity_id"]
        _delete_competency(app, data["id"])

    def test_add_competency_response_has_description(self, auth_client, ids, app):
        """La réponse POST /skills/add retourne la description saisie."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({
                "activity_id": ids["activity_id"],
                "description": "Analyser les processus métier",
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "Analyser" in data["description"]
        _delete_competency(app, data["id"])

    def test_add_missing_activity_id_returns_400(self, auth_client):
        """Sans activity_id → 400."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({"description": "Compétence orpheline"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_empty_description_returns_400(self, auth_client, ids):
        """Description vide → 400."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({"activity_id": ids["activity_id"], "description": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_empty_body_returns_400(self, auth_client):
        """Corps vide → 400."""
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_update_competency_success(self, auth_client, ids, app):
        """PUT /skills/<id> met à jour la description et retourne 200."""
        comp_id = _create_competency(app, ids["activity_id"], "Description initiale update")
        try:
            r = auth_client.put(
                f"/skills/{comp_id}",
                data=json.dumps({"description": "Description mise à jour"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "mise à jour" in data["description"]
        finally:
            _delete_competency(app, comp_id)

    def test_update_response_has_id_and_description(self, auth_client, ids, app):
        """La réponse PUT contient les champs id et description."""
        comp_id = _create_competency(app, ids["activity_id"], "Desc champs réponse")
        try:
            r = auth_client.put(
                f"/skills/{comp_id}",
                data=json.dumps({"description": "Champs OK"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "id" in data
            assert "description" in data
        finally:
            _delete_competency(app, comp_id)

    def test_update_empty_description_returns_400(self, auth_client, ids, app):
        """PUT avec description vide → 400."""
        comp_id = _create_competency(app, ids["activity_id"], "Desc pour test vide")
        try:
            r = auth_client.put(
                f"/skills/{comp_id}",
                data=json.dumps({"description": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_competency(app, comp_id)

    def test_update_nonexistent_returns_404(self, auth_client):
        """PUT sur ID inexistant → 404."""
        r = auth_client.put(
            "/skills/999999",
            data=json.dumps({"description": "Fantôme"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_delete_competency_success(self, auth_client, ids, app):
        """DELETE /skills/<id> supprime la compétence et retourne 200."""
        comp_id = _create_competency(app, ids["activity_id"], "À supprimer delete")
        r = auth_client.delete(f"/skills/{comp_id}")
        assert r.status_code == 200

    def test_delete_response_has_message(self, auth_client, ids, app):
        """La réponse DELETE contient un champ 'message'."""
        comp_id = _create_competency(app, ids["activity_id"], "Delete message check")
        r = auth_client.delete(f"/skills/{comp_id}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "message" in data

    def test_delete_nonexistent_returns_404(self, auth_client):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete("/skills/999999")
        assert r.status_code == 404

    def test_delete_removes_from_db(self, auth_client, ids, app):
        """Après DELETE, la compétence est absente de la base."""
        comp_id = _create_competency(app, ids["activity_id"], "Vérif suppression DB")
        auth_client.delete(f"/skills/{comp_id}")
        with app.app_context():
            from Code.models.models import Competency
            assert Competency.query.get(comp_id) is None

    def test_add_erreur_commit_retourne_500(self, auth_client, ids, monkeypatch):
        """Une exception au commit (DB down) → rollback + 500 avec le message d'erreur."""
        from sqlalchemy.orm import Session as SqlaSession

        def raise_commit_error(self):
            raise RuntimeError("DB down")

        monkeypatch.setattr(SqlaSession, "commit", raise_commit_error)
        r = auth_client.post(
            "/skills/add",
            data=json.dumps({"activity_id": ids["activity_id"], "description": "Ne sera jamais créée"}),
            content_type="application/json",
        )
        assert r.status_code == 500
        assert "DB down" in r.get_json()["error"]

    def test_update_erreur_commit_retourne_500(self, auth_client, ids, app, monkeypatch):
        """Une exception au commit lors d'un update → rollback + 500."""
        from sqlalchemy.orm import Session as SqlaSession

        comp_id = _create_competency(app, ids["activity_id"], "Avant erreur commit update")
        try:
            def raise_commit_error(self):
                raise RuntimeError("DB down")

            monkeypatch.setattr(SqlaSession, "commit", raise_commit_error)
            r = auth_client.put(
                f"/skills/{comp_id}",
                data=json.dumps({"description": "Nouvelle valeur"}),
                content_type="application/json",
            )
            assert r.status_code == 500
            assert "DB down" in r.get_json()["error"]
        finally:
            monkeypatch.undo()
            _delete_competency(app, comp_id)

    def test_delete_erreur_commit_retourne_500(self, auth_client, ids, app, monkeypatch):
        """Une exception au commit lors d'un delete → rollback + 500."""
        from sqlalchemy.orm import Session as SqlaSession

        comp_id = _create_competency(app, ids["activity_id"], "Avant erreur commit delete")
        try:
            def raise_commit_error(self):
                raise RuntimeError("DB down")

            monkeypatch.setattr(SqlaSession, "commit", raise_commit_error)
            r = auth_client.delete(f"/skills/{comp_id}")
            assert r.status_code == 500
            assert "DB down" in r.get_json()["error"]
        finally:
            monkeypatch.undo()
            _delete_competency(app, comp_id)


# ===========================================================================
# 7. GET /your_api/activity_items/<activity_id>
# ===========================================================================

class TestActivityItemsAPI:

    def test_returns_200_for_existing_activity(self, auth_client, ids):
        """GET /your_api/activity_items/<id> retourne 200 pour une activité existante."""
        r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
        assert r.status_code == 200

    def test_response_has_savoirs_key(self, auth_client, ids):
        """La réponse contient la clé 'savoirs'."""
        r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
        data = json.loads(r.data)
        assert "savoirs" in data

    def test_response_has_savoir_faire_key(self, auth_client, ids):
        """La réponse contient la clé 'savoir_faire'."""
        r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
        data = json.loads(r.data)
        assert "savoir_faire" in data

    def test_response_has_hsc_key(self, auth_client, ids):
        """La réponse contient la clé 'hsc'."""
        r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
        data = json.loads(r.data)
        assert "hsc" in data

    def test_all_values_are_lists(self, auth_client, ids):
        """savoirs, savoir_faire et hsc sont tous des listes."""
        r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
        data = json.loads(r.data)
        assert isinstance(data["savoirs"], list)
        assert isinstance(data["savoir_faire"], list)
        assert isinstance(data["hsc"], list)

    def test_nonexistent_activity_returns_empty_lists(self, auth_client):
        """activity_id inexistant → 200 avec 3 listes vides (pas de 404)."""
        r = auth_client.get("/your_api/activity_items/999999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["savoirs"] == []
        assert data["savoir_faire"] == []
        assert data["hsc"] == []

    def test_seeded_savoir_appears_in_response(self, auth_client, ids, app):
        """Un savoir inséré en base pour l'activité apparaît dans la réponse."""
        with app.app_context():
            from Code.models.models import Savoir
            from Code.extensions import db
            s = Savoir(description="Savoir Items API Test", activity_id=ids["activity_id"])
            db.session.add(s)
            db.session.commit()
            savoir_id = s.id
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            data = json.loads(r.data)
            found = any(item.get("id") == savoir_id for item in data["savoirs"])
            assert found
        finally:
            with app.app_context():
                from Code.models.models import Savoir
                from Code.extensions import db
                sv = Savoir.query.get(savoir_id)
                if sv:
                    db.session.delete(sv)
                    db.session.commit()

    def test_items_have_id_and_name_fields(self, auth_client, ids, app):
        """Chaque item retourné a les champs 'id' et 'name'."""
        with app.app_context():
            from Code.models.models import Savoir
            from Code.extensions import db
            s = Savoir(description="Item champs test", activity_id=ids["activity_id"])
            db.session.add(s)
            db.session.commit()
            savoir_id = s.id
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            data = json.loads(r.data)
            matching = [item for item in data["savoirs"] if item.get("id") == savoir_id]
            assert len(matching) == 1
            item = matching[0]
            assert "id" in item
            assert "name" in item
        finally:
            with app.app_context():
                from Code.models.models import Savoir
                from Code.extensions import db
                sv = Savoir.query.get(savoir_id)
                if sv:
                    db.session.delete(sv)
                    db.session.commit()
