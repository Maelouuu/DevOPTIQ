# tests/test_16_import_full.py
"""
Page : Import global IA depuis Excel (/api/import-full)
Couvre : analyse algorithmique (POST /analyze), injection en base (POST /inject),
         validations, cas limites, doublons et sécurité cross-entité.
"""
import io
import json
import pytest
import openpyxl

pytestmark = pytest.mark.import_full


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_excel(rows: list) -> bytes:
    """Crée un Excel minimal compatible avec _parse_excel_bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Activities"
    ws.append([
        'ID', 'Department', 'Activity', 'Guarantor',
        'Task', 'Tool', 'Doer', 'Approver', 'Skills', 'Commentary',
    ])
    for row in rows:
        ws.append([
            row.get('id', ''), row.get('department', ''), row.get('activity', ''),
            row.get('guarantor', ''), row.get('task', ''), row.get('tool', ''),
            row.get('doer', ''), row.get('approver', ''), row.get('skills', ''),
            row.get('commentary', ''),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _set_session(client, ids):
    with client.session_transaction() as sess:
        sess["user_id"] = ids["user_id"]
        sess["active_entity_id"] = ids["entity_id"]


@pytest.fixture(scope="module", autouse=True)
def _setup_module(client, ids):
    """Initialise la session authentifiée pour tous les tests du module."""
    _set_session(client, ids)
    yield


# ===========================================================================
# 1. POST /api/import-full/analyze — Analyse algorithmique
# ===========================================================================

class TestImportAnalyze:

    def test_analyze_no_file_returns_400(self, auth_client, ids):
        """POST /analyze sans fichier retourne 400 avec clé 'error'."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/import-full/analyze",
            data={},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_analyze_wrong_extension_returns_400(self, auth_client, ids):
        """POST /analyze avec un .pdf retourne 400 (format non supporté)."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(b"fake"), "document.pdf")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert "format" in json.loads(r.data)["error"].lower()

    def test_analyze_no_entity_in_session_returns_400(self, client):
        """POST /analyze sans active_entity_id en session retourne 400 mentionnant l'entité."""
        with client.session_transaction() as sess:
            sess.clear()
        xlsx = _make_excel([{"activity": "A", "task": "T"}])
        r = client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert "entité" in json.loads(r.data)["error"].lower()

    def test_analyze_exact_match_returns_matched_group(self, auth_client, ids):
        """POST /analyze avec activité connue (correspondance exacte) retourne matched_groups."""
        _set_session(auth_client, ids)
        xlsx = _make_excel([{"activity": "Activité Test", "task": "Tâche importée"}])
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"
        assert data["stats"]["matched_activities"] >= 1
        assert len(data["analysis"]["matched_groups"]) >= 1

    def test_analyze_unknown_activity_goes_to_unmatched(self, auth_client, ids):
        """POST /analyze avec activité inconnue retourne au moins un unmatched_group."""
        _set_session(auth_client, ids)
        xlsx = _make_excel([{"activity": "ZzZActivitéFantômeXxX9999", "task": "Tâche fantôme"}])
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        assert json.loads(r.data)["stats"]["unmatched_activities"] >= 1

    def test_analyze_stats_has_all_keys(self, auth_client, ids):
        """POST /analyze retourne un objet stats avec les 6 clés attendues."""
        _set_session(auth_client, ids)
        xlsx = _make_excel([
            {"activity": "Activité Test", "task": "T1"},
            {"activity": "Activité Test", "task": "T2"},
        ])
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        stats = json.loads(r.data)["stats"]
        for key in (
            "total_groups_excel", "matched_activities", "unmatched_activities",
            "total_tasks", "matched_tasks", "unmatched_tasks",
        ):
            assert key in stats, f"Clé manquante dans stats : {key}"

    def test_analyze_returns_db_activities_list(self, auth_client, ids):
        """POST /analyze retourne db_activities contenant l'activité 'Activité Test'."""
        _set_session(auth_client, ids)
        xlsx = _make_excel([{"activity": "Activité Test", "task": "Tâche"}])
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        db_activities = json.loads(r.data)["db_activities"]
        assert isinstance(db_activities, list)
        assert any(a["name"] == "Activité Test" for a in db_activities)

    def test_analyze_empty_excel_no_data_rows_returns_400(self, auth_client, ids):
        """POST /analyze avec Excel sans lignes de données retourne 400 'Aucune donnée'."""
        _set_session(auth_client, ids)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Activities"
        ws.append([
            'ID', 'Department', 'Activity', 'Guarantor',
            'Task', 'Tool', 'Doer', 'Approver', 'Skills', 'Commentary',
        ])
        buf = io.BytesIO()
        wb.save(buf)
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(buf.getvalue()), "vide.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_analyze_matched_group_structure(self, auth_client, ids):
        """Un matched_group contient activity_id, activity_name_db et une liste de tâches."""
        _set_session(auth_client, ids)
        xlsx = _make_excel([{"activity": "Activité Test", "task": "Tâche importée 2"}])
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        groups = json.loads(r.data)["analysis"]["matched_groups"]
        assert len(groups) >= 1
        g = groups[0]
        assert "activity_id" in g
        assert "activity_name_db" in g
        assert "tasks" in g and isinstance(g["tasks"], list)

    def test_analyze_unmatched_group_has_possible_matches(self, auth_client, ids):
        """Un unmatched_group contient possible_matches (suggestions de l'algo)."""
        _set_session(auth_client, ids)
        xlsx = _make_excel([{"activity": "ZzZSansCorrespondanceXxX", "task": "Tâche X"}])
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        unmatched = json.loads(r.data)["analysis"]["unmatched_groups"]
        assert len(unmatched) >= 1
        assert "possible_matches" in unmatched[0]
        assert isinstance(unmatched[0]["possible_matches"], list)

    def test_analyze_analysis_notes_present(self, auth_client, ids):
        """POST /analyze retourne analysis_notes dans l'objet analysis."""
        _set_session(auth_client, ids)
        xlsx = _make_excel([{"activity": "Activité Test", "task": "T"}])
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(xlsx), "import.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        assert "analysis_notes" in json.loads(r.data)["analysis"]

    def test_analyze_wrong_extension_csv_returns_400(self, auth_client, ids):
        """POST /analyze avec un .csv retourne 400 (seuls .xlsx/.xls/.xlsm acceptés)."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/import-full/analyze",
            data={"file": (io.BytesIO(b"col1,col2\nval1,val2"), "data.csv")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400


# ===========================================================================
# 2. POST /api/import-full/inject — Injection en base
# ===========================================================================

class TestImportInject:

    def test_inject_no_groups_returns_400(self, auth_client, ids):
        """POST /inject avec liste vide retourne 400."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps({"groups": []}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_inject_missing_groups_key_returns_400(self, auth_client, ids):
        """POST /inject sans clé 'groups' dans le body retourne 400."""
        _set_session(auth_client, ids)
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_inject_no_entity_in_session_returns_400(self, client):
        """POST /inject sans active_entity_id en session retourne 400."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.post(
            "/api/import-full/inject",
            data=json.dumps({"groups": [{"activity_id": 1, "tasks": [{"name": "T"}]}]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_inject_invalid_activity_id_skipped_silently(self, auth_client, ids):
        """POST /inject avec activity_id inexistant ne crée rien et ne lève pas d'erreur."""
        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": 999999,
                "guarantor": "",
                "tasks": [{
                    "name": "Tâche Ghost", "tools": [], "doer": "",
                    "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["stats"]["tasks_created"] == 0

    def test_inject_creates_task_and_tool(self, auth_client, ids):
        """POST /inject crée une tâche et un outil pour l'activité spécifiée."""
        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": ids["activity_id"],
                "guarantor": "",
                "tasks": [{
                    "name": "Tâche Inject Unique A",
                    "tools": ["Outil Inject A"],
                    "doer": "", "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        stats = json.loads(r.data)["stats"]
        assert stats["tasks_created"] >= 1
        assert stats["tools_created"] >= 1
        assert stats["activities_updated"] == 1

    def test_inject_duplicate_task_not_recreated(self, auth_client, ids):
        """POST /inject ne recrée pas une tâche dont le nom existe déjà pour l'activité."""
        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": ids["activity_id"],
                "guarantor": "",
                "tasks": [{
                    "name": "Tâche Inject Unique A",  # même nom que le test précédent
                    "tools": [], "doer": "", "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["stats"]["tasks_created"] == 0

    def test_inject_creates_guarantor_role(self, auth_client, ids):
        """POST /inject crée un rôle garant et le lie à l'activité."""
        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": ids["activity_id"],
                "guarantor": "Responsable Inject",
                "tasks": [{
                    "name": "Tâche Garant Test",
                    "tools": [], "doer": "", "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["stats"]["roles_created"] >= 1

    def test_inject_creates_doer_and_approver_roles(self, auth_client, ids):
        """POST /inject crée deux rôles distincts : exécutant et approbateur."""
        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": ids["activity_id"],
                "guarantor": "",
                "tasks": [{
                    "name": "Tâche Doer Approver Inject",
                    "tools": [],
                    "doer": "Exécutant Inject",
                    "approver": "Approbateur Inject",
                    "skills": [], "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["stats"]["roles_created"] >= 2

    def test_inject_creates_competencies(self, auth_client, ids):
        """POST /inject crée autant de compétences que d'éléments dans 'skills'."""
        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": ids["activity_id"],
                "guarantor": "",
                "tasks": [{
                    "name": "Tâche Compétences Inject",
                    "tools": [], "doer": "", "approver": "",
                    "skills": ["Compétence Inject Alpha", "Compétence Inject Beta"],
                    "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        assert json.loads(r.data)["stats"]["competencies_created"] >= 2

    def test_inject_tool_reused_not_recreated(self, auth_client, ids):
        """POST /inject réutilise un outil existant sans en créer un doublon."""
        _set_session(auth_client, ids)
        tool_name = "Outil Réutilisation Inject"

        payload1 = {
            "groups": [{
                "activity_id": ids["activity_id"], "guarantor": "",
                "tasks": [{
                    "name": "Tâche Outil Réutilisé 1", "tools": [tool_name],
                    "doer": "", "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r1 = auth_client.post(
            "/api/import-full/inject", data=json.dumps(payload1), content_type="application/json",
        )
        assert json.loads(r1.data)["stats"]["tools_created"] >= 1

        payload2 = {
            "groups": [{
                "activity_id": ids["activity_id"], "guarantor": "",
                "tasks": [{
                    "name": "Tâche Outil Réutilisé 2", "tools": [tool_name],
                    "doer": "", "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r2 = auth_client.post(
            "/api/import-full/inject", data=json.dumps(payload2), content_type="application/json",
        )
        assert json.loads(r2.data)["stats"]["tools_created"] == 0

    def test_inject_cross_entity_activity_ignored(self, app, auth_client, ids):
        """POST /inject ignore silencieusement les activités d'une autre entité."""
        with app.app_context():
            from Code.models.models import Entity, Activities
            from Code.extensions import db
            other = Entity(name="Entité Cross Inject Test", description="")
            db.session.add(other)
            db.session.flush()
            other_act = Activities(entity_id=other.id, name="Activité Cross Inject")
            db.session.add(other_act)
            db.session.commit()
            cross_id = other_act.id

        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": cross_id,
                "guarantor": "",
                "tasks": [{
                    "name": "Tâche Cross Entity Inject",
                    "tools": [], "doer": "", "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        stats = json.loads(r.data)["stats"]
        assert stats["tasks_created"] == 0
        assert stats["activities_updated"] == 0

    def test_inject_returns_stats_structure(self, auth_client, ids):
        """POST /inject retourne un objet stats avec les 5 compteurs attendus."""
        _set_session(auth_client, ids)
        payload = {
            "groups": [{
                "activity_id": ids["activity_id"], "guarantor": "",
                "tasks": [{
                    "name": "Tâche Stats Structure", "tools": [],
                    "doer": "", "approver": "", "skills": [], "commentary": "",
                }],
            }]
        }
        r = auth_client.post(
            "/api/import-full/inject",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 201
        stats = json.loads(r.data)["stats"]
        for key in ("tasks_created", "tools_created", "roles_created",
                    "competencies_created", "activities_updated"):
            assert key in stats, f"Clé manquante dans stats : {key}"
