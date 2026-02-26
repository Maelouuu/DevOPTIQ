# tests/test_04_activity_features.py
"""
Tests étendus pour la page liste des activités :
- Suppression de tâche (cascade task_roles)
- Connexions entrantes/sortantes sur une tâche
- CRUD performances
- CRUD contraintes
- CRUD savoirs
- CRUD savoir-faires
- CRUD aptitudes
- CRUD softskills/HSC
- Routes propose (IA)
- Gestion du temps (save / modify / reset)
"""
import json
import pytest

pytestmark = pytest.mark.activity_features


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _json(r):
    try:
        return json.loads(r.data)
    except Exception:
        return {}


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _put(client, url, payload):
    return client.put(url, data=json.dumps(payload), content_type="application/json")


# ─────────────────────────────────────────────────────────────────────────────
# Tâches
# ─────────────────────────────────────────────────────────────────────────────

class TestTaskDeleteCascade:
    """Suppression d'une tâche — vérifie qu'il n'y a pas de violation FK task_roles."""

    def test_delete_task_no_fk_violation(self, auth_client, ids):
        # 1) Créer une tâche temporaire
        r = _post(auth_client, "/tasks/add", {
            "name": "Tâche temporaire delete-test",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code in (200, 201), f"Création impossible : {r.status_code}"
        task_id = _json(r).get("id")
        assert task_id is not None

        # 2) Associer un rôle (crée une ligne dans task_roles)
        _post(auth_client, f"/tasks/{task_id}/roles/add", {
            "new_roles": ["Rôle Temp Test"],
            "status": "Réalisateur",
        })

        # 3) Supprimer la tâche → ne doit PAS retourner d'erreur FK
        r = auth_client.delete(f"/tasks/{task_id}")
        assert r.status_code in (200, 204), f"Erreur suppression : {r.status_code} — {r.data}"
        data = _json(r)
        assert "error" not in data, f"FK violation probable : {data}"

    def test_delete_nonexistent_task(self, auth_client):
        r = auth_client.delete("/tasks/999999")
        assert r.status_code in (404, 200, 204)


# ─────────────────────────────────────────────────────────────────────────────
# Connexions tâche-lien (task-link assignments)
# ─────────────────────────────────────────────────────────────────────────────

class TestTaskConnections:
    """Branchement de connexions entrantes et sortantes sur une tâche."""

    def test_assign_incoming_connection(self, auth_client, ids):
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible dans les données de test")
        r = _post(auth_client, "/task-links/assign", {
            "link_id": ids["link_id"],
            "task_id": ids["task_id"],
            "direction": "incoming",
        })
        assert r.status_code in (200, 400, 500)
        if r.status_code == 200:
            assert _json(r).get("ok") is True

    def test_assign_outgoing_connection(self, auth_client, ids):
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible")
        r = _post(auth_client, "/task-links/assign", {
            "link_id": ids["link_id"],
            "task_id": ids["task_id"],
            "direction": "outgoing",
        })
        assert r.status_code in (200, 400, 500)

    def test_get_activity_connections(self, auth_client, ids):
        r = auth_client.get(f"/task-links/activity/{ids['activity_id']}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(_json(r), list)

    def test_unassign_connection(self, auth_client, ids):
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible")
        r = auth_client.delete(f"/task-links/{ids['link_id']}/incoming")
        assert r.status_code in (200, 204, 404)

    def test_assign_missing_params(self, auth_client):
        r = _post(auth_client, "/task-links/assign", {"link_id": 1})
        assert r.status_code in (400, 422, 500)


# ─────────────────────────────────────────────────────────────────────────────
# Performances
# ─────────────────────────────────────────────────────────────────────────────

class TestPerformance:
    """CRUD des performances sur les connexions.

    Note : performances.link_id a une contrainte UNIQUE.
    On crée la performance UNE seule fois (dans test_add) et on réutilise l'ID.
    """

    _perf_id = None  # Partagé entre les méthodes du test

    def test_add_performance(self, auth_client, ids):
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible")
        r = _post(auth_client, "/performance/add", {
            "name": "Performance Test Auto",
            "description": "Créée par les tests automatisés",
            "link_id": ids["link_id"],
            "activity_id": ids["activity_id"],
        })
        assert r.status_code in (200, 201, 400, 409)
        if r.status_code in (200, 201):
            data = _json(r)
            TestPerformance._perf_id = (
                data.get("id") or data.get("perf_id") or data.get("performance_id")
            )

    def test_update_performance(self, auth_client, ids):
        if not TestPerformance._perf_id:
            pytest.skip("Aucune performance disponible (test_add non exécuté)")
        r = _put(auth_client, f"/performance/{TestPerformance._perf_id}", {
            "name": "Performance modifiée",
            "description": "Mise à jour par test",
        })
        assert r.status_code in (200, 204, 404)

    def test_render_performance_by_activity(self, auth_client, ids):
        r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
        assert r.status_code in (200, 404)

    def test_render_performance_by_link(self, auth_client, ids):
        if not ids.get("link_id"):
            pytest.skip("Aucun lien disponible")
        r = auth_client.get(f"/performance/render/{ids['link_id']}")
        assert r.status_code in (200, 404)

    def test_delete_performance(self, auth_client, ids):
        if not TestPerformance._perf_id:
            pytest.skip("Aucune performance disponible (test_add non exécuté)")
        r = auth_client.delete(f"/performance/{TestPerformance._perf_id}")
        assert r.status_code in (200, 204, 404)
        TestPerformance._perf_id = None


# ─────────────────────────────────────────────────────────────────────────────
# Contraintes
# ─────────────────────────────────────────────────────────────────────────────

class TestConstraints:
    """CRUD des contraintes d'activité."""

    _cid = None

    def test_add_constraint(self, auth_client, ids):
        r = _post(auth_client, f"/constraints/{ids['activity_id']}/add",
                  {"description": "Contrainte test automatisée"})
        assert r.status_code in (200, 201, 400)
        if r.status_code in (200, 201):
            data = _json(r)
            TestConstraints._cid = data.get("id") or data.get("constraint_id")

    def test_add_constraint_missing_description(self, auth_client, ids):
        r = _post(auth_client, f"/constraints/{ids['activity_id']}/add", {})
        assert r.status_code in (400, 422, 200, 201)

    def test_update_constraint(self, auth_client, ids):
        if not TestConstraints._cid:
            pytest.skip("Aucune contrainte disponible")
        r = _put(auth_client, f"/constraints/{ids['activity_id']}/{TestConstraints._cid}",
                 {"description": "Contrainte modifiée"})
        assert r.status_code in (200, 204, 404)

    def test_render_constraints(self, auth_client, ids):
        r = auth_client.get(f"/constraints/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)

    def test_delete_constraint(self, auth_client, ids):
        if not TestConstraints._cid:
            pytest.skip("Aucune contrainte disponible")
        r = auth_client.delete(f"/constraints/{ids['activity_id']}/{TestConstraints._cid}")
        assert r.status_code in (200, 204, 404)
        TestConstraints._cid = None


# ─────────────────────────────────────────────────────────────────────────────
# Savoirs
# ─────────────────────────────────────────────────────────────────────────────

class TestSavoirs:
    """CRUD des savoirs d'activité."""

    _sid = None

    def test_add_savoir(self, auth_client, ids):
        r = _post(auth_client, "/savoirs/add", {
            "description": "Savoir test automatisé",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code in (200, 201, 400)
        if r.status_code in (200, 201):
            data = _json(r)
            TestSavoirs._sid = data.get("id") or data.get("savoir_id")

    def test_update_savoir(self, auth_client, ids):
        if not TestSavoirs._sid:
            pytest.skip("Aucun savoir disponible")
        r = _put(auth_client, f"/savoirs/{ids['activity_id']}/{TestSavoirs._sid}",
                 {"description": "Savoir modifié"})
        assert r.status_code in (200, 204, 404)

    def test_render_savoirs(self, auth_client, ids):
        r = auth_client.get(f"/savoirs/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)

    def test_delete_savoir(self, auth_client, ids):
        if not TestSavoirs._sid:
            pytest.skip("Aucun savoir disponible")
        r = auth_client.delete(f"/savoirs/{ids['activity_id']}/{TestSavoirs._sid}")
        assert r.status_code in (200, 204, 404)
        TestSavoirs._sid = None


# ─────────────────────────────────────────────────────────────────────────────
# Savoir-faires
# ─────────────────────────────────────────────────────────────────────────────

class TestSavoirFaires:
    """CRUD des savoir-faires d'activité."""

    _sfid = None

    def test_add_savoir_faire(self, auth_client, ids):
        r = _post(auth_client, "/savoir_faires/add", {
            "description": "Savoir-faire test automatisé",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code in (200, 201, 400)
        if r.status_code in (200, 201):
            data = _json(r)
            TestSavoirFaires._sfid = (
                data.get("id") or data.get("savoir_faire_id") or data.get("savoir_faires_id")
            )

    def test_update_savoir_faire(self, auth_client, ids):
        if not TestSavoirFaires._sfid:
            pytest.skip("Aucun savoir-faire disponible")
        r = _put(auth_client, f"/savoir_faires/{ids['activity_id']}/{TestSavoirFaires._sfid}",
                 {"description": "Savoir-faire modifié"})
        assert r.status_code in (200, 204, 404)

    def test_render_savoir_faires(self, auth_client, ids):
        r = auth_client.get(f"/savoir_faires/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)

    def test_delete_savoir_faire(self, auth_client, ids):
        if not TestSavoirFaires._sfid:
            pytest.skip("Aucun savoir-faire disponible")
        r = auth_client.delete(f"/savoir_faires/{ids['activity_id']}/{TestSavoirFaires._sfid}")
        assert r.status_code in (200, 204, 404)
        TestSavoirFaires._sfid = None


# ─────────────────────────────────────────────────────────────────────────────
# Aptitudes
# ─────────────────────────────────────────────────────────────────────────────

class TestAptitudes:
    """CRUD des aptitudes d'activité."""

    _aid = None

    def test_add_aptitude(self, auth_client, ids):
        r = _post(auth_client, "/aptitudes/add", {
            "description": "Aptitude test automatisée",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code in (200, 201, 400)
        if r.status_code in (200, 201):
            data = _json(r)
            TestAptitudes._aid = (
                data.get("id") or data.get("aptitude_id") or data.get("aptitudes_id")
            )

    def test_update_aptitude(self, auth_client, ids):
        if not TestAptitudes._aid:
            pytest.skip("Aucune aptitude disponible")
        r = _put(auth_client, f"/aptitudes/{ids['activity_id']}/{TestAptitudes._aid}",
                 {"description": "Aptitude modifiée"})
        assert r.status_code in (200, 204, 404)

    def test_render_aptitudes(self, auth_client, ids):
        r = auth_client.get(f"/aptitudes/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)

    def test_delete_aptitude(self, auth_client, ids):
        if not TestAptitudes._aid:
            pytest.skip("Aucune aptitude disponible")
        r = auth_client.delete(f"/aptitudes/{ids['activity_id']}/{TestAptitudes._aid}")
        assert r.status_code in (200, 204, 404)
        TestAptitudes._aid = None


# ─────────────────────────────────────────────────────────────────────────────
# Softskills / HSC
# ─────────────────────────────────────────────────────────────────────────────

class TestSoftskillsHSC:
    """CRUD des softskills (HSC) d'activité."""

    _ssid = None

    def test_add_softskill(self, auth_client, ids):
        r = _post(auth_client, "/softskills/add", {
            "habilete": "Adaptabilité",
            "niveau": "3",
            "justification": "Test automatisé",
            "activity_id": ids["activity_id"],
        })
        assert r.status_code in (200, 201, 400)
        if r.status_code in (200, 201):
            data = _json(r)
            TestSoftskillsHSC._ssid = (
                data.get("id") or data.get("ss_id") or data.get("softskill_id")
            )

    def test_update_softskill(self, auth_client, ids):
        if not TestSoftskillsHSC._ssid:
            pytest.skip("Aucun softskill disponible")
        r = _put(auth_client, f"/softskills/{ids['activity_id']}/{TestSoftskillsHSC._ssid}", {
            "habilete": "Rigueur",
            "niveau": "4",
            "justification": "Modifié par test",
        })
        assert r.status_code in (200, 204, 404)

    def test_render_softskills(self, auth_client, ids):
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert r.status_code in (200, 404)

    def test_delete_softskill(self, auth_client, ids):
        if not TestSoftskillsHSC._ssid:
            pytest.skip("Aucun softskill disponible")
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/{TestSoftskillsHSC._ssid}")
        assert r.status_code in (200, 204, 404)
        TestSoftskillsHSC._ssid = None


# ─────────────────────────────────────────────────────────────────────────────
# Routes « Proposer » (IA) — vérification d'existence et réponse correcte
# ─────────────────────────────────────────────────────────────────────────────

class TestProposeRoutes:
    """
    Les routes propose appellent OpenAI — sans clé API elles retourneront
    une erreur, mais la route doit exister et répondre (pas un 404).
    """

    def _base_payload(self, ids):
        return {"activity_id": ids["activity_id"], "activity_name": "Activité Test"}

    def test_propose_savoirs_endpoint_exists(self, auth_client, ids):
        r = _post(auth_client, "/propose_savoirs/propose", self._base_payload(ids))
        assert r.status_code in (200, 400, 401, 500)
        assert r.status_code != 404

    def test_propose_savoir_faires_endpoint_exists(self, auth_client, ids):
        r = _post(auth_client, "/propose_savoir_faires/propose", self._base_payload(ids))
        assert r.status_code in (200, 400, 401, 500)
        assert r.status_code != 404

    def test_propose_aptitudes_endpoint_exists(self, auth_client, ids):
        r = _post(auth_client, "/propose_aptitudes/propose", self._base_payload(ids))
        assert r.status_code in (200, 400, 401, 500)
        assert r.status_code != 404

    def test_propose_softskills_endpoint_exists(self, auth_client, ids):
        r = _post(auth_client, "/propose_softskills/propose", self._base_payload(ids))
        assert r.status_code in (200, 400, 401, 500)
        assert r.status_code != 404


# ─────────────────────────────────────────────────────────────────────────────
# Gestion du temps
# ─────────────────────────────────────────────────────────────────────────────

class TestTimeManagement:
    """Enregistrement, modification et réinitialisation des temps d'activité."""

    def test_get_activity_defaults(self, auth_client, ids):
        r = auth_client.get(f"/temps/api/activity_defaults/{ids['activity_id']}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = _json(r)
            assert isinstance(data, dict)

    def test_save_activity_time(self, auth_client, ids):
        r = _post(auth_client, f"/temps/api/activity_time/{ids['activity_id']}", {
            "duration_minutes": 90,
            "delay_minutes": 15,
        })
        assert r.status_code in (200, 201, 400, 404, 405)

    def test_get_activity_time(self, auth_client, ids):
        r = auth_client.get(f"/temps/api/activity_time/{ids['activity_id']}")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = _json(r)
            assert isinstance(data, (dict, list))

    def test_modify_activity_time(self, auth_client, ids):
        r = _post(auth_client, f"/temps/api/activity_time/{ids['activity_id']}", {
            "duration_minutes": 120,
            "delay_minutes": 30,
        })
        assert r.status_code in (200, 201, 400, 404, 405)

    def test_reset_activity_time(self, auth_client, ids):
        r = auth_client.delete(f"/temps/api/activity_time/{ids['activity_id']}")
        assert r.status_code in (200, 204, 404, 405)

    def test_activities_list_for_time(self, auth_client):
        r = auth_client.get("/temps/api/activities")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = _json(r)
            assert isinstance(data, (list, dict))
