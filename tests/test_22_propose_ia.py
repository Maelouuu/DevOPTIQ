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
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.propose_ia


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


# ===========================================================================
# 8. Chemin IA "avec clé" (client OpenAI mocké, sans réseau) —
#    propose_savoirs / propose_savoir_faires / propose_softskills /
#    propose_aptitudes. Ces routes ont un chemin `if client is None: fallback`
#    déjà couvert plus haut ; ici on force `openai_client_or_none()` à
#    renvoyer un faux client pour exercer l'appel réel + parsing + erreurs.
# ===========================================================================

class _FakeCompletions:
    def __init__(self, content=None, exc=None):
        self._content = content
        self._exc = exc

    def create(self, **kwargs):
        if self._exc is not None:
            raise self._exc
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))]
        )


class FakeOpenAIClient:
    """Simule le client OpenAI (chat.completions.create) sans appel réseau."""

    def __init__(self, content=None, exc=None):
        self.chat = SimpleNamespace(completions=_FakeCompletions(content, exc))


def _isolated_auth_client(app, lang=None):
    """Client isolé (session dédiée) pour tester lang='en' sans polluer auth_client."""
    from Code.models.models import User, Entity

    with app.app_context():
        user = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.filter_by(name="Entité Test").first()
    isolated = app.test_client()
    with isolated.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_email"] = user.email
        sess["active_entity_id"] = entity.id
        if lang:
            sess["lang"] = lang
    return isolated


class TestProposeSavoirsWithAIClient:
    """/propose_savoirs/propose avec client OpenAI mocké (succès + erreur)."""

    def test_ai_success_parses_bullet_lines(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_savoirs.openai_client_or_none",
            lambda: (FakeOpenAIClient(content="- Règles de nomenclature\n- Procédure interne\n"), None),
        )
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Traitement des commandes"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == ["Règles de nomenclature", "Procédure interne"]
        assert "source" not in data

    def test_ai_exception_returns_200_with_error_field(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_savoirs.openai_client_or_none",
            lambda: (FakeOpenAIClient(exc=RuntimeError("boom-savoirs")), None),
        )
        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert "boom-savoirs" in data["error"]

    def test_ai_success_with_english_lang(self, app, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_savoirs.openai_client_or_none",
            lambda: (FakeOpenAIClient(content="- Catalogue naming rules\n"), None),
        )
        client = _isolated_auth_client(app, lang="en")
        r = client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Order processing"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"] == ["Catalogue naming rules"]


class TestProposeSavoirFairesWithAIClient:
    """/propose_savoir_faires/propose avec client OpenAI mocké (succès + erreur)."""

    def test_ai_success_parses_bullet_lines(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_savoir_faires.openai_client_or_none",
            lambda: (FakeOpenAIClient(content="- Utiliser le logiciel ERP\n- Vérifier les écarts\n"), None),
        )
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "Gestion du stock"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == ["Utiliser le logiciel ERP", "Vérifier les écarts"]
        assert "source" not in data

    def test_ai_exception_returns_200_with_error_field(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_savoir_faires.openai_client_or_none",
            lambda: (FakeOpenAIClient(exc=RuntimeError("boom-sf")), None),
        )
        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert "boom-sf" in data["error"]


class TestProposeSoftskillsWithAIClient:
    """/propose_softskills/propose avec client OpenAI mocké — tous les embranchements
    de parsing (JSON liste, JSON objet unique, JSON invalide, réponse vide, exception)."""

    def test_ai_success_json_list(self, auth_client, monkeypatch):
        content = json.dumps([
            {"habilete": "Coopération", "niveau": "3", "justification": "Travail en équipe étroit."}
        ])
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=content), None),
        )
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Coordination de projet"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert proposals == [{
            "habilete": "Coopération",
            "niveau": "3 (Maîtrise)",
            "justification": "Travail en équipe étroit.",
        }]

    def test_ai_success_json_single_object_wrapped_in_list(self, auth_client, monkeypatch):
        """Un objet JSON unique (pas une liste) doit être enveloppé dans une liste."""
        content = json.dumps({"habilete": "Planification", "niveau": 2, "justification": "J"})
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=content), None),
        )
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 1
        assert proposals[0]["habilete"] == "Planification"
        assert proposals[0]["niveau"] == "2 (Acquisition)"

    def test_ai_invalid_json_falls_back_to_line_parsing(self, auth_client, monkeypatch):
        """Réponse non-JSON → repli sur un parsing ligne à ligne du texte brut."""
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (FakeOpenAIClient(content="Ceci n'est pas du JSON valide du tout."), None),
        )
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 1
        assert proposals[0]["habilete"] == "Ceci n'est pas du JSON valide du tout."

    def test_ai_empty_response_falls_back_to_default_proposal(self, auth_client, monkeypatch):
        """Réponse vide → aucun proposal parsé → item par défaut renvoyé."""
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=""), None),
        )
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 1
        assert proposals[0]["habilete"] == "Communication professionnelle"

    def test_ai_exception_returns_200_with_error_field(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (FakeOpenAIClient(exc=RuntimeError("boom-hsc")), None),
        )
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert "boom-hsc" in data["error"]
        assert data["proposals"][0]["habilete"] == "Habileté non déterminée (erreur serveur)."

    def test_ai_success_with_english_lang(self, app, monkeypatch):
        content = json.dumps([{"habilete": "Cooperation", "niveau": "4", "justification": "J"}])
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=content), None),
        )
        client = _isolated_auth_client(app, lang="en")
        r = client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Project coordination"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert proposals[0]["niveau"] == "4 (Highly Proficient)"


class TestProposeAptitudesWithAIClient:
    """/propose_aptitudes/propose & /feasibility avec client OpenAI mocké."""

    def test_propose_ai_success_returns_parsed_dict(self, auth_client, monkeypatch):
        payload_json = json.dumps({
            "vision": {"niveau": "1 (Faible)", "risque": "Écran prolongé", "leviers": ["Zoom logiciel"]},
        })
        monkeypatch.setattr(
            "Code.routes.propose_aptitudes.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=payload_json), None),
        )
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Contrôle qualité"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"]["vision"]["niveau"] == "1 (Faible)"

    def test_propose_ai_success_strips_markdown_fences(self, auth_client, monkeypatch):
        fenced = "```json\n" + json.dumps({"vision": {"niveau": "0 (Aucune)"}}) + "\n```"
        monkeypatch.setattr(
            "Code.routes.propose_aptitudes.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=fenced), None),
        )
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"]["vision"]["niveau"] == "0 (Aucune)"

    def test_propose_ai_invalid_json_returns_error_field(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_aptitudes.openai_client_or_none",
            lambda: (FakeOpenAIClient(content="pas du json"), None),
        )
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_propose_ai_exception_returns_error_field(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_aptitudes.openai_client_or_none",
            lambda: (FakeOpenAIClient(exc=RuntimeError("boom-apt")), None),
        )
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "boom-apt" in data["error"]

    def test_feasibility_ai_success_with_dict_scoring_and_string_assistive(self, auth_client, monkeypatch):
        """inclusion_scoring_json en dict (converti en str) + assistive_products en str (non-liste)."""
        result_json = json.dumps({
            "statut": "OK avec adaptations",
            "mesures_deja_en_place": [],
            "ajouts_recommandes": ["Poste ergonomique"],
            "a_ajuster": [],
            "risque_residuel": "Faible",
            "points_a_instruire": [],
            "commentaire": "RAS",
        })
        monkeypatch.setattr(
            "Code.routes.propose_aptitudes.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=result_json), None),
        )
        payload = {
            "activity_name": "Saisie de données",
            "inclusion_scoring_json": {"vision": {"niveau": "1 (Faible)"}},
            "profil_fonctionnel": {"vision": "normale"},
            "assistive_products": "Loupe électronique",
        }
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"]["statut"] == "OK avec adaptations"

    def test_feasibility_ai_invalid_json_returns_error_field(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_aptitudes.openai_client_or_none",
            lambda: (FakeOpenAIClient(content="pas du json"), None),
        )
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data

    def test_feasibility_ai_exception_returns_error_field(self, auth_client, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_aptitudes.openai_client_or_none",
            lambda: (FakeOpenAIClient(exc=RuntimeError("boom-feas")), None),
        )
        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "boom-feas" in data["error"]


# ===========================================================================
# 9. Fonctions utilitaires pures (sans Flask) — build_activity_summary,
#    clean_json_response, make_enumeration.
# ===========================================================================

class TestProposeAptitudesHelpers:

    def test_build_activity_summary_combines_all_sections(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        activity = {
            "description": "Contrôle qualité des pièces usinées",
            "tools": ["Pied à coulisse", "Comparateur"],
            "constraints": ["Cadence 200 pièces/h"],
            "tasks": [{"description": "Mesurer les cotes"}, "Vérifier visuellement"],
            "outgoing": [{"performance": {"name": "Taux de conformité", "description": "> 98%"}}],
        }
        summary = build_activity_summary(activity)
        assert "Contrôle qualité des pièces usinées" in summary
        assert "Outils : Pied à coulisse, Comparateur" in summary
        assert "Contraintes : Cadence 200 pièces/h" in summary
        assert "T1: Mesurer les cotes" in summary
        assert "T2: Vérifier visuellement" in summary
        assert "Performance : Taux de conformité - > 98%" in summary

    def test_build_activity_summary_empty_activity_returns_default(self):
        from Code.routes.propose_aptitudes import build_activity_summary
        assert build_activity_summary({}) == "Non renseigné"

    def test_clean_json_response_extracts_json_array(self):
        from Code.routes.propose_aptitudes import clean_json_response
        text = "Voici la réponse : [1, 2, 3] fin."
        assert clean_json_response(text) == "[1, 2, 3]"

    def test_clean_json_response_no_brackets_returns_text_as_is(self):
        from Code.routes.propose_aptitudes import clean_json_response
        assert clean_json_response("juste du texte") == "juste du texte"


class TestProposeSoftskillsHelpers:

    def test_make_enumeration_with_dict_items(self):
        from Code.routes.propose_softskills import make_enumeration
        items = [{"description": "Analyser les données"}, {"description": "Rédiger le rapport"}]
        result = make_enumeration("T", items)
        assert result == "T1: Analyser les données\nT2: Rédiger le rapport"

    def test_make_enumeration_with_plain_items(self):
        from Code.routes.propose_softskills import make_enumeration
        assert make_enumeration("C", ["Délai serré"]) == "C1: Délai serré"

    def test_make_enumeration_empty_list_returns_placeholder(self):
        from Code.routes.propose_softskills import make_enumeration
        assert make_enumeration("T", []) == "(Aucune T)"

    def test_clean_json_response_extracts_json_array(self):
        from Code.routes.propose_softskills import clean_json_response
        text = "```json\n[{\"a\": 1}]\n```"
        assert clean_json_response(text) == '[{"a": 1}]'

    def test_ai_success_with_outgoing_performances_in_prompt(self, auth_client, monkeypatch):
        """outgoing contient une performance → alimente perf_lines (branche dédiée)."""
        captured = {}

        class _CapturingCompletions(_FakeCompletions):
            def create(self, **kwargs):
                captured["prompt"] = kwargs["messages"][1]["content"]
                return super().create(**kwargs)

        fake = FakeOpenAIClient(content=json.dumps([
            {"habilete": "Synthèse", "niveau": "2", "justification": "J"}
        ]))
        fake.chat.completions = _CapturingCompletions(
            content=json.dumps([{"habilete": "Synthèse", "niveau": "2", "justification": "J"}])
        )
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (fake, None),
        )
        payload = {
            "name": "Reporting mensuel",
            "outgoing": [
                {"performance": {"name": "Fiabilité", "description": "0 erreur"}},
                {"no_performance_here": True},
            ],
        }
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert "P1: Fiabilité - 0 erreur" in captured["prompt"]

    def test_ai_empty_response_english_lang_falls_back_to_default(self, app, monkeypatch):
        monkeypatch.setattr(
            "Code.routes.propose_softskills.openai_client_or_none",
            lambda: (FakeOpenAIClient(content=""), None),
        )
        client = _isolated_auth_client(app, lang="en")
        r = client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert proposals[0]["habilete"] == "Professional Communication"
