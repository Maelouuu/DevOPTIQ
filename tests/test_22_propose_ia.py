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
from unittest.mock import MagicMock

pytestmark = pytest.mark.propose_ia


def _fake_openai_client(content):
    """Client OpenAI factice : chat.completions.create(...) renvoie `content`."""
    fake = MagicMock()
    fake.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    return fake


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
# 8. POST /propose_savoirs/propose — avec client OpenAI (mock)
# ===========================================================================

class TestProposeSavoirsWithClient:

    def test_mocked_client_returns_parsed_lines(self, auth_client, monkeypatch):
        """Avec un client OpenAI mocké, la réponse texte est parsée en liste de lignes."""
        import Code.routes.propose_savoirs as mod
        fake_client = _fake_openai_client("- Règles de nomenclature\n- Procédure qualité\n- Normes RGPD")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Activité Test Savoirs IA"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == ["Règles de nomenclature", "Procédure qualité", "Normes RGPD"]
        assert "source" not in data

    def test_mocked_client_strips_bullets_and_blank_lines(self, auth_client, monkeypatch):
        """Les puces (-,•) et lignes vides sont retirées du résultat."""
        import Code.routes.propose_savoirs as mod
        fake_client = _fake_openai_client("• Item un\n\n-   Item deux   \n")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["proposals"] == ["Item un", "Item deux"]

    def test_mocked_client_english_lang_uses_english_prompt(self, auth_client, monkeypatch):
        """Avec lang='en' en session, le prompt système anglais est utilisé (capturé via le mock)."""
        import Code.routes.propose_savoirs as mod
        fake_client = _fake_openai_client("- Knowledge item A\n- Knowledge item B")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        with auth_client.session_transaction() as sess:
            sess["lang"] = "en"
        try:
            r = auth_client.post(
                "/propose_savoirs/propose",
                data=json.dumps({"name": "Order processing"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["proposals"] == ["Knowledge item A", "Knowledge item B"]
            call_kwargs = fake_client.chat.completions.create.call_args.kwargs
            system_msg = call_kwargs["messages"][0]["content"]
            assert "precise and concise HR/training assistant" in system_msg
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("lang", None)

    def test_mocked_client_exception_falls_back_to_200_with_error(self, auth_client, monkeypatch):
        """Si le client OpenAI lève une exception, la route renvoie 200 + message d'erreur (pas de crash)."""
        import Code.routes.propose_savoirs as mod
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("boom")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_savoirs/propose",
            data=json.dumps({"name": "Activité en erreur"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert "boom" in data["error"]
        assert len(data["proposals"]) == 1


# ===========================================================================
# 9. POST /propose_savoir_faires/propose — avec client OpenAI (mock)
# ===========================================================================

class TestProposeSavoirFairesWithClient:

    def test_mocked_client_returns_parsed_lines(self, auth_client, monkeypatch):
        """Avec un client OpenAI mocké, la réponse texte est parsée en liste de lignes."""
        import Code.routes.propose_savoir_faires as mod
        fake_client = _fake_openai_client("- Utiliser le logiciel ERP\n- Vérifier les écarts de stock")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "Gestion du stock"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == ["Utiliser le logiciel ERP", "Vérifier les écarts de stock"]
        assert "source" not in data

    def test_mocked_client_english_lang_uses_english_prompt(self, auth_client, monkeypatch):
        """Avec lang='en' en session, le prompt système anglais est utilisé."""
        import Code.routes.propose_savoir_faires as mod
        fake_client = _fake_openai_client("- Apply the safety checklist")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        with auth_client.session_transaction() as sess:
            sess["lang"] = "en"
        try:
            r = auth_client.post(
                "/propose_savoir_faires/propose",
                data=json.dumps({"name": "Field inspection"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            call_kwargs = fake_client.chat.completions.create.call_args.kwargs
            system_msg = call_kwargs["messages"][0]["content"]
            assert "precise and concise HR/training assistant" in system_msg
            assert "=== CONTEXT ===" in call_kwargs["messages"][1]["content"]
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("lang", None)

    def test_mocked_client_exception_falls_back_to_200_with_error(self, auth_client, monkeypatch):
        """Si le client OpenAI lève une exception, la route renvoie 200 + message d'erreur (pas de crash)."""
        import Code.routes.propose_savoir_faires as mod
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("kaboom")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_savoir_faires/propose",
            data=json.dumps({"name": "Activité en erreur SF"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert "kaboom" in data["error"]
        assert len(data["proposals"]) == 1


# ===========================================================================
# 10. POST /propose_softskills/propose — avec client OpenAI (mock)
# ===========================================================================

class TestProposeSoftskillsWithClient:

    def test_mocked_client_json_array_parsed(self, auth_client, monkeypatch):
        """Réponse JSON valide (tableau) → proposals mappées avec niveau traduit."""
        import Code.routes.propose_softskills as mod
        content = json.dumps([
            {"habilete": "Autonomie", "niveau": "3 - Maîtrise", "justification": "Contexte X"},
        ])
        fake_client = _fake_openai_client(content)
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Pilotage projet"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert proposals == [{"habilete": "Autonomie", "niveau": "3 (Maîtrise)", "justification": "Contexte X"}]

    def test_mocked_client_single_dict_wrapped_in_list(self, auth_client, monkeypatch):
        """Réponse JSON = objet unique (pas un tableau) → traité comme liste à 1 élément."""
        import Code.routes.propose_softskills as mod
        content = json.dumps({"habilete": "Rigueur", "niveau": "2", "justification": "j"})
        fake_client = _fake_openai_client(content)
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 1
        assert proposals[0]["habilete"] == "Rigueur"
        assert proposals[0]["niveau"] == "2 (Acquisition)"

    def test_mocked_client_niveau_as_int(self, auth_client, monkeypatch):
        """Un niveau fourni en entier (pas string) est converti correctement."""
        import Code.routes.propose_softskills as mod
        content = json.dumps([{"habilete": "Excellence op.", "niveau": 4, "justification": "j"}])
        fake_client = _fake_openai_client(content)
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        proposals = json.loads(r.data)["proposals"]
        assert proposals[0]["niveau"] == "4 (Excellence)"

    def test_mocked_client_invalid_json_falls_back_to_line_parsing(self, auth_client, monkeypatch):
        """Réponse non-JSON → repli sur un parsing ligne par ligne avec niveau par défaut."""
        import Code.routes.propose_softskills as mod
        fake_client = _fake_openai_client("Autonomie\nRigueur professionnelle\nCommunication claire")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        proposals = json.loads(r.data)["proposals"]
        assert len(proposals) == 3
        assert all(p["niveau"] == "2 (Acquisition)" for p in proposals)
        assert {p["habilete"] for p in proposals} == {"Autonomie", "Rigueur professionnelle", "Communication claire"}

    def test_mocked_client_lang_en_maps_niveau_and_prompt(self, auth_client, monkeypatch):
        """lang='en' → prompt et niveau_map anglais utilisés."""
        import Code.routes.propose_softskills as mod
        content = json.dumps([{"habilete": "Autonomy", "niveau": "1", "justification": "j"}])
        fake_client = _fake_openai_client(content)
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        with auth_client.session_transaction() as sess:
            sess["lang"] = "en"
        try:
            r = auth_client.post(
                "/propose_softskills/propose",
                data=json.dumps({"name": "Project steering"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            proposals = json.loads(r.data)["proposals"]
            assert proposals[0]["niveau"] == "1 (Basic)"
            call_kwargs = fake_client.chat.completions.create.call_args.kwargs
            assert "Socio-Cognitive Abilities" in call_kwargs["messages"][0]["content"]
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("lang", None)

    def test_mocked_client_outgoing_performance_and_tasks_in_prompt(self, auth_client, monkeypatch):
        """tasks/constraints/outgoing.performance sont bien injectés dans le prompt (make_enumeration)."""
        import Code.routes.propose_softskills as mod
        fake_client = _fake_openai_client(json.dumps([{"habilete": "X", "niveau": "2", "justification": "j"}]))
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        payload = {
            "name": "Support client",
            "tasks": [{"description": "Répondre aux tickets"}, "Suivre le CRM"],
            "constraints": ["Délai 24h"],
            "outgoing": [{"performance": {"name": "Satisfaction", "description": "Taux de résolution"}}],
        }
        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "T1: Répondre aux tickets" in prompt
        assert "T2: Suivre le CRM" in prompt
        assert "C1: Délai 24h" in prompt
        assert "P1: Satisfaction - Taux de résolution" in prompt

    def test_mocked_client_exception_returns_default_fallback(self, auth_client, monkeypatch):
        """Exception dans l'appel OpenAI → 200 avec proposal par défaut + champ 'error'."""
        import Code.routes.propose_softskills as mod
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("hsc-boom")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_softskills/propose",
            data=json.dumps({"name": "Activité en erreur HSC"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "error" in data
        assert "hsc-boom" in data["error"]
        assert data["proposals"] == [{
            "habilete": "Habileté non déterminée (erreur serveur).",
            "niveau": "2 (Acquisition)",
            "justification": "",
        }]


# ===========================================================================
# 11. POST /propose_aptitudes/propose & /feasibility — avec client OpenAI (mock)
# ===========================================================================

class TestProposeAptitudesWithClient:

    def test_propose_mocked_client_valid_json_returns_result(self, auth_client, monkeypatch):
        """JSON valide → 'proposals' contient l'objet parsé tel quel."""
        import Code.routes.propose_aptitudes as mod
        payload_result = {"categories": [{"nom": "Vision", "score": 1}]}
        fake_client = _fake_openai_client(json.dumps(payload_result))
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Saisie de données", "tools": ["Excel"]}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == payload_result
        assert "error" not in data

    def test_propose_mocked_client_invalid_json_returns_error(self, auth_client, monkeypatch):
        """JSON invalide → proposals={} + champ 'error' explicite."""
        import Code.routes.propose_aptitudes as mod
        fake_client = _fake_openai_client("not a json at all")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "error" in data

    def test_propose_mocked_client_exception_returns_error(self, auth_client, monkeypatch):
        """Exception dans l'appel OpenAI → proposals={} + champ 'error'."""
        import Code.routes.propose_aptitudes as mod
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("aptitude-boom")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps({"name": "Activité en erreur aptitudes"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["proposals"] == {}
        assert "aptitude-boom" in data["error"]

    def test_propose_mocked_client_builds_summary_with_tools_constraints_tasks(self, auth_client, monkeypatch):
        """build_activity_summary : outils/contraintes/tâches/performance apparaissent dans le prompt."""
        import Code.routes.propose_aptitudes as mod
        fake_client = _fake_openai_client(json.dumps({}))
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        payload = {
            "name": "Intervention terrain",
            "description": "Inspection sur site",
            "tools": ["EPI", "Checklist"],
            "constraints": ["Délai 2h"],
            "tasks": [{"description": "Vérifier équipements"}, "Rédiger rapport"],
            "outgoing": [{"performance": {"name": "Conformité", "description": "Taux OK"}}],
        }
        r = auth_client.post(
            "/propose_aptitudes/propose",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "EPI, Checklist" in prompt
        assert "Délai 2h" in prompt
        assert "T1: Vérifier équipements" in prompt
        assert "T2: Rédiger rapport" in prompt
        assert "Conformité - Taux OK" in prompt

    def test_feasibility_mocked_client_valid_json_returns_result(self, auth_client, monkeypatch):
        """JSON valide → 'result' contient l'objet parsé tel quel."""
        import Code.routes.propose_aptitudes as mod
        payload_result = {"ajouts_recommandes": ["Ecran adapté"]}
        fake_client = _fake_openai_client(json.dumps(payload_result))
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({
                "activity_name": "Saisie de données",
                "inclusion_scoring_json": {"vision": 2},
                "profil_fonctionnel": {"vision": "faible"},
                "assistive_products": ["Loupe numérique", "Contraste élevé"],
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == payload_result
        prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "Loupe numérique" in prompt
        assert "Contraste élevé" in prompt

    def test_feasibility_mocked_client_invalid_json_returns_error(self, auth_client, monkeypatch):
        """JSON invalide → result={} + champ 'error'."""
        import Code.routes.propose_aptitudes as mod
        fake_client = _fake_openai_client("nope not json")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "error" in data

    def test_feasibility_mocked_client_exception_returns_error(self, auth_client, monkeypatch):
        """Exception dans l'appel OpenAI → result={} + champ 'error'."""
        import Code.routes.propose_aptitudes as mod
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError("feasibility-boom")
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "Y"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["result"] == {}
        assert "feasibility-boom" in data["error"]

    def test_feasibility_mocked_client_no_assistive_products_default_text(self, auth_client, monkeypatch):
        """Sans assistive_products → texte par défaut 'Aucune aide renseignée' dans le prompt."""
        import Code.routes.propose_aptitudes as mod
        fake_client = _fake_openai_client(json.dumps({}))
        monkeypatch.setattr(mod, "openai_client_or_none", lambda: (fake_client, None))

        r = auth_client.post(
            "/propose_aptitudes/feasibility",
            data=json.dumps({"activity_name": "Z"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
        assert "Aucune aide renseignée" in prompt
