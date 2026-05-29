# tests/test_26_import_tasks.py
"""
Routes : Import de Tâches via CSV/JSON (/api/import-tasks)

Modules couverts :
  import_tasks.py  →  POST /api/import-tasks/validate
                       POST /api/import-tasks/inject

Flux testé : parsing CSV → validation → rapport d'erreurs → injection en base.
"""
import json
import pytest

pytestmark = pytest.mark.import_tasks

# ── CSV minimal valide (colonnes requises) ────────────────────────────────────
_CSV_OK = (
    "nom_tache,activite,description,outils,entree_nom,entree_type,sortie_nom,sortie_type,sortie_activite_cible\r\n"
    "Tâche Import CSV,Activité Test,Desc CSV,Outil Import,,,,,"
)

# ── CSV avec activité introuvable ─────────────────────────────────────────────
_CSV_BAD_ACTIVITY = (
    "nom_tache,activite,description\r\n"
    "Tâche X,Activité Inexistante,Desc"
)

# ── CSV avec nom de tâche vide ────────────────────────────────────────────────
_CSV_MISSING_NAME = (
    "nom_tache,activite,description\r\n"
    ",Activité Test,Desc"
)

# ── JSON valide ───────────────────────────────────────────────────────────────
_JSON_OK = json.dumps([{
    "nom": "Tâche Import JSON",
    "activite": "Activité Test",
    "description": "Desc JSON",
    "outils": ["Outil JSON"],
}])

# ── JSON avec connexions entrante et sortante ─────────────────────────────────
_JSON_WITH_LINKS = json.dumps([{
    "nom": "Tâche Liée",
    "activite": "Activité Test",
    "description": "Avec liens",
    "entree": {"nom": "Donnée Entrée", "type": "nourrissante"},
    "sortie": {"nom": "Donnée Sortie", "type": "descendante"},
}])

# ── JSON avec type de donnée invalide (→ warning, pas error) ─────────────────
_JSON_BAD_TYPE = json.dumps([{
    "nom": "Tâche Type Invalide",
    "activite": "Activité Test",
    "entree": {"nom": "Donnée X", "type": "inventé"},
}])

# ── JSON qui n'est pas un tableau ─────────────────────────────────────────────
_JSON_NOT_ARRAY = json.dumps({"nom": "objet", "activite": "Activité Test"})


def _post_validate(auth_client, content, fmt="csv"):
    return auth_client.post(
        "/api/import-tasks/validate",
        json={"format": fmt, "content": content},
    )


def _post_inject(auth_client, results):
    return auth_client.post(
        "/api/import-tasks/inject",
        json={"results": results},
    )


class TestImportTasksValidate:

    def test_validate_csv_valid_row_returns_ok_status(self, auth_client):
        r = _post_validate(auth_client, _CSV_OK, fmt="csv")
        assert r.status_code == 200
        body = r.get_json()
        assert body["summary"]["total"] == 1
        assert body["summary"]["ok"] == 1
        assert body["summary"]["error"] == 0
        assert body["summary"]["can_inject"] is True

    def test_validate_csv_unknown_activity_is_error(self, auth_client):
        r = _post_validate(auth_client, _CSV_BAD_ACTIVITY, fmt="csv")
        assert r.status_code == 200
        body = r.get_json()
        row = body["results"][0]
        assert row["status"] == "error"
        assert any("Activité introuvable" in e for e in row["errors"])
        assert body["summary"]["can_inject"] is False

    def test_validate_csv_missing_task_name_is_error(self, auth_client):
        r = _post_validate(auth_client, _CSV_MISSING_NAME, fmt="csv")
        assert r.status_code == 200
        body = r.get_json()
        assert body["results"][0]["status"] == "error"
        assert any("Nom de tâche manquant" in e for e in body["results"][0]["errors"])

    def test_validate_json_valid_row_returns_ok(self, auth_client):
        r = _post_validate(auth_client, _JSON_OK, fmt="json")
        assert r.status_code == 200
        body = r.get_json()
        assert body["summary"]["ok"] == 1
        assert body["results"][0]["nom_tache"] == "Tâche Import JSON"

    def test_validate_json_with_connections_parses_links(self, auth_client):
        r = _post_validate(auth_client, _JSON_WITH_LINKS, fmt="json")
        assert r.status_code == 200
        body = r.get_json()
        row = body["results"][0]
        assert row["entree"]["nom"] == "Donnée Entrée"
        assert row["entree"]["type"] == "nourrissante"
        assert row["sortie"]["nom"] == "Donnée Sortie"
        assert row["sortie"]["type"] == "descendante"

    def test_validate_json_invalid_data_type_becomes_warning(self, auth_client):
        r = _post_validate(auth_client, _JSON_BAD_TYPE, fmt="json")
        assert r.status_code == 200
        body = r.get_json()
        row = body["results"][0]
        assert row["status"] == "warning"
        assert row["entree"]["type"] == "nourrissante"

    def test_validate_empty_content_returns_400(self, auth_client):
        r = _post_validate(auth_client, "", fmt="csv")
        assert r.status_code == 400
        body = r.get_json()
        assert "error" in body

    def test_validate_json_not_array_returns_400(self, auth_client):
        r = _post_validate(auth_client, _JSON_NOT_ARRAY, fmt="json")
        assert r.status_code == 400

    def test_validate_response_contains_summary_keys(self, auth_client):
        r = _post_validate(auth_client, _CSV_OK, fmt="csv")
        body = r.get_json()
        assert all(k in body["summary"] for k in ("total", "ok", "warning", "error", "can_inject"))

    def test_validate_row_has_expected_fields(self, auth_client):
        r = _post_validate(auth_client, _CSV_OK, fmt="csv")
        row = r.get_json()["results"][0]
        assert all(k in row for k in ("row", "nom_tache", "activite", "activity_id", "status", "errors", "warnings"))

    def test_validate_csv_multiple_rows_counts_correctly(self, auth_client):
        csv_two_rows = (
            "nom_tache,activite,description\r\n"
            "T1,Activité Test,D1\r\n"
            "T2,Activité Inconnue,D2"
        )
        r = _post_validate(auth_client, csv_two_rows, fmt="csv")
        body = r.get_json()
        assert body["summary"]["total"] == 2
        assert body["summary"]["ok"] == 1
        assert body["summary"]["error"] == 1
        assert body["summary"]["can_inject"] is False

    def test_validate_tools_parsed_from_semicolon_separated(self, auth_client):
        csv_tools = (
            "nom_tache,activite,outils\r\n"
            "T,Activité Test,OutilA;OutilB;OutilC"
        )
        r = _post_validate(auth_client, csv_tools, fmt="csv")
        row = r.get_json()["results"][0]
        assert row["outils"] == ["OutilA", "OutilB", "OutilC"]


class TestImportTasksInject:

    def _valid_result(self, ids, task_name="Tâche Injectée"):
        return {
            "row": 1,
            "nom_tache": task_name,
            "activite": "Activité Test",
            "activity_id": ids["activity_id"],
            "description": "Créée par test inject",
            "outils": [],
            "entree": None,
            "sortie": None,
            "errors": [],
            "warnings": [],
            "status": "ok",
        }

    def test_inject_creates_task_in_db(self, auth_client, app, ids):
        task_name = "Tâche Inject Simple"
        r = _post_inject(auth_client, [self._valid_result(ids, task_name)])
        assert r.status_code == 201
        body = r.get_json()
        assert body["count"] == 1
        assert any(c["tache"] == task_name for c in body["created"])

    def test_inject_with_new_tool_creates_tool(self, auth_client, app, ids):
        result = self._valid_result(ids, "Tâche Avec Nouvel Outil")
        result["outils"] = ["Outil Créé Par Inject"]
        r = _post_inject(auth_client, [result])
        assert r.status_code == 201
        with app.app_context():
            from Code.models.models import Tool
            tool = Tool.query.filter_by(name="Outil Créé Par Inject").first()
            assert tool is not None

    def test_inject_with_existing_tool_reuses_it(self, auth_client, app, ids):
        with app.app_context():
            from Code.models.models import Tool
            from Code.extensions import db
            existing = Tool(name="Outil Existant Inject", entity_id=ids["entity_id"])
            db.session.add(existing)
            db.session.commit()
            tool_id = existing.id

        result = self._valid_result(ids, "Tâche Réutilise Outil")
        result["outils"] = ["Outil Existant Inject"]
        r = _post_inject(auth_client, [result])
        assert r.status_code == 201

        with app.app_context():
            from Code.models.models import Tool
            tools = Tool.query.filter_by(name="Outil Existant Inject").all()
            assert len(tools) == 1
            assert tools[0].id == tool_id

    def test_inject_with_incoming_link_creates_data_and_link(self, auth_client, app, ids):
        result = self._valid_result(ids, "Tâche Avec Entrée")
        result["entree"] = {"nom": "Donnée Entrante Test", "type": "nourrissante"}
        r = _post_inject(auth_client, [result])
        assert r.status_code == 201
        with app.app_context():
            from Code.models.models import Data
            d = Data.query.filter_by(name="Donnée Entrante Test").first()
            assert d is not None

    def test_inject_with_outgoing_link_creates_data_and_link(self, auth_client, app, ids):
        result = self._valid_result(ids, "Tâche Avec Sortie")
        result["sortie"] = {"nom": "Donnée Sortante Test", "type": "descendante", "activite_cible": None, "activity_id_cible": None}
        r = _post_inject(auth_client, [result])
        assert r.status_code == 201
        with app.app_context():
            from Code.models.models import Data
            d = Data.query.filter_by(name="Donnée Sortante Test").first()
            assert d is not None

    def test_inject_no_results_returns_400(self, auth_client, ids):
        r = _post_inject(auth_client, [])
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_inject_all_error_rows_returns_400(self, auth_client, ids):
        bad_result = {
            "row": 1,
            "nom_tache": "",
            "activite": "Inexistante",
            "activity_id": None,
            "description": "",
            "outils": [],
            "entree": None,
            "sortie": None,
            "errors": ["Activité introuvable"],
            "warnings": [],
            "status": "error",
        }
        r = _post_inject(auth_client, [bad_result])
        assert r.status_code == 400

    def test_inject_returns_created_list_with_tache_and_activite(self, auth_client, ids):
        r = _post_inject(auth_client, [self._valid_result(ids, "Tâche Inspect Retour")])
        body = r.get_json()
        item = body["created"][0]
        assert "tache" in item
        assert "activite" in item

    def test_inject_multiple_rows_creates_all_tasks(self, auth_client, ids):
        rows = [
            self._valid_result(ids, "Tâche Multi A"),
            self._valid_result(ids, "Tâche Multi B"),
            self._valid_result(ids, "Tâche Multi C"),
        ]
        r = _post_inject(auth_client, rows)
        assert r.status_code == 201
        body = r.get_json()
        assert body["count"] == 3

    def test_full_flow_validate_then_inject(self, auth_client, app, ids):
        r_val = _post_validate(auth_client, _JSON_OK, fmt="json")
        assert r_val.status_code == 200
        results = r_val.get_json()["results"]
        assert results[0]["status"] == "ok"

        r_inj = _post_inject(auth_client, results)
        assert r_inj.status_code == 201
        assert r_inj.get_json()["count"] == 1
