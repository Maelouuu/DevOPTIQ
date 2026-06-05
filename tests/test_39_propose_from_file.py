# tests/test_39_propose_from_file.py
"""
Page : Propositions depuis fichier de référence (/propose_from_file)

Couverture :
  POST   /propose_from_file/upload           → upload Excel de référence
  GET    /propose_from_file/status           → état du fichier uploadé
  POST   /propose_from_file/propose_sf       → propositions Savoir / Savoir-faire
  POST   /propose_from_file/propose_aptitudes → propositions Aptitudes
  POST   /propose_from_file/propose_hsc      → propositions HSC (soft skills)
  DELETE /propose_from_file/delete           → suppression du fichier de référence
"""
import io
import json
import pytest

pytestmark = pytest.mark.propose_from_file


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_xlsx(rows: list[tuple]) -> bytes:
    """
    Crée un fichier xlsx minimal en mémoire.
    Chaque ligne est un tuple (ObjectID, JobId, JobText, GrpName, CompName, Score).
    """
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ObjectID", "JobId", "JobText", "GrpName", "CompName", "Required Score"])
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sample_xlsx() -> bytes:
    """Fichier de référence minimaliste couvrant tous les groupes pertinents."""
    rows = [
        ("O1", "J1", "Software Engineer", "Technical Skills",            "Python Programming",        3),
        ("O2", "J1", "Software Engineer", "Technical Skills",            "Database Management",       2),
        ("O3", "J1", "Software Engineer", "Functional Competencies",     "Requirements Analysis",     3),
        ("O4", "J1", "Software Engineer", "Functional Competencies",     "System Design",             2),
        ("O5", "J1", "Software Engineer", "Behavioural Competencies",    "Communication",             4),
        ("O6", "J1", "Software Engineer", "Leadership Competencies",     "Team Leadership",           3),
        ("O7", "J2", "Data Analyst",      "Technical Skills",            "Statistical Analysis",      3),
        ("O8", "J2", "Data Analyst",      "Functional Competencies",     "Data Visualization",        2),
        ("O9", "J2", "Data Analyst",      "Behavioural Competencies",    "Critical Thinking",         4),
    ]
    return _make_xlsx(rows)


def _upload_ref(auth_client) -> None:
    """Upload le fichier de référence pour l'utilisateur de test."""
    data = _sample_xlsx()
    auth_client.post(
        "/propose_from_file/upload",
        data={"file": (io.BytesIO(data), "ref.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        content_type="multipart/form-data",
    )


def _delete_ref(auth_client) -> None:
    """Supprime le fichier de référence pour nettoyer après un test."""
    auth_client.delete("/propose_from_file/delete")


# ─────────────────────────────────────────────────────────────────────────────
# 1. POST /propose_from_file/upload
# ─────────────────────────────────────────────────────────────────────────────

class TestProposeFromFileUpload:

    def test_upload_valid_xlsx_returns_200(self, auth_client):
        data = _sample_xlsx()
        r = auth_client.post(
            "/propose_from_file/upload",
            data={"file": (io.BytesIO(data), "ref.xlsx", "application/vnd.ms-excel")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        _delete_ref(auth_client)

    def test_upload_returns_ok_true(self, auth_client):
        data = _sample_xlsx()
        r = auth_client.post(
            "/propose_from_file/upload",
            data={"file": (io.BytesIO(data), "ref.xlsx")},
            content_type="multipart/form-data",
        )
        body = r.get_json()
        assert body.get("ok") is True
        _delete_ref(auth_client)

    def test_upload_returns_stats_dict(self, auth_client):
        data = _sample_xlsx()
        r = auth_client.post(
            "/propose_from_file/upload",
            data={"file": (io.BytesIO(data), "ref.xlsx")},
            content_type="multipart/form-data",
        )
        body = r.get_json()
        assert isinstance(body.get("stats"), dict)
        _delete_ref(auth_client)

    def test_upload_stats_contain_known_group(self, auth_client):
        data = _sample_xlsx()
        r = auth_client.post(
            "/propose_from_file/upload",
            data={"file": (io.BytesIO(data), "ref.xlsx")},
            content_type="multipart/form-data",
        )
        body = r.get_json()
        assert "Technical Skills" in body["stats"]
        _delete_ref(auth_client)

    def test_upload_no_file_returns_400(self, auth_client):
        r = auth_client.post("/propose_from_file/upload", data={}, content_type="multipart/form-data")
        assert r.status_code == 400

    def test_upload_invalid_content_returns_200_with_warning(self, auth_client):
        """Un fichier non-xlsx valide est stocké mais parse_stats échoue → warning."""
        r = auth_client.post(
            "/propose_from_file/upload",
            data={"file": (io.BytesIO(b"not an xlsx file"), "ref.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body.get("ok") is True
        _delete_ref(auth_client)

    def test_upload_overwrites_existing_blob(self, auth_client):
        """Un second upload remplace le fichier précédent."""
        data1 = _sample_xlsx()
        data2 = _make_xlsx([
            ("O1", "J1", "Nurse", "Technical Skills", "Patient Care", 3),
        ])
        auth_client.post(
            "/propose_from_file/upload",
            data={"file": (io.BytesIO(data1), "ref.xlsx")},
            content_type="multipart/form-data",
        )
        r2 = auth_client.post(
            "/propose_from_file/upload",
            data={"file": (io.BytesIO(data2), "ref.xlsx")},
            content_type="multipart/form-data",
        )
        assert r2.status_code == 200
        body = r2.get_json()
        assert body["ok"] is True
        _delete_ref(auth_client)


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /propose_from_file/status
# ─────────────────────────────────────────────────────────────────────────────

class TestProposeFromFileStatus:

    def test_status_without_file_returns_has_file_false(self, auth_client):
        _delete_ref(auth_client)
        r = auth_client.get("/propose_from_file/status")
        assert r.status_code == 200
        assert r.get_json().get("has_file") is False

    def test_status_with_file_returns_has_file_true(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.get("/propose_from_file/status")
        assert r.status_code == 200
        assert r.get_json().get("has_file") is True
        _delete_ref(auth_client)

    def test_status_with_file_returns_stats(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.get("/propose_from_file/status")
        body = r.get_json()
        assert isinstance(body.get("stats"), dict)
        _delete_ref(auth_client)

    def test_status_unauthenticated_returns_has_file_false(self, client):
        """Sans session, la route répond has_file=False (pas de 403)."""
        r = client.get("/propose_from_file/status")
        assert r.status_code == 200
        assert r.get_json().get("has_file") is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. POST /propose_from_file/propose_sf
# ─────────────────────────────────────────────────────────────────────────────

class TestProposeFromFileSF:

    def test_propose_sf_without_file_returns_404(self, auth_client, ids):
        _delete_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 404

    def test_propose_sf_no_file_error_field_is_no_file(self, auth_client, ids):
        """Sans fichier, le champ error est 'no_file'."""
        _delete_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.get_json().get("error") == "no_file"

    def test_propose_sf_with_file_returns_200(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 200
        _delete_ref(auth_client)

    def test_propose_sf_returns_proposals_sf_list(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        body = r.get_json()
        assert "proposals_sf" in body
        assert isinstance(body["proposals_sf"], list)
        _delete_ref(auth_client)

    def test_propose_sf_returns_proposals_s_list(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        body = r.get_json()
        assert "proposals_s" in body
        assert isinstance(body["proposals_s"], list)
        _delete_ref(auth_client)

    def test_propose_sf_source_is_file(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.get_json().get("source") == "file"
        _delete_ref(auth_client)

    def test_propose_sf_with_activity_name_instead_of_id(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_name": "Software Engineer"},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert len(body.get("proposals_sf", []) + body.get("proposals_s", [])) > 0
        _delete_ref(auth_client)

    def test_propose_sf_empty_body_returns_200(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.post("/propose_from_file/propose_sf", json={})
        assert r.status_code == 200
        _delete_ref(auth_client)

    def test_propose_sf_invalid_activity_id_falls_back(self, auth_client):
        """Un activity_id inexistant ne plante pas — contexte vide, fallback."""
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": 999999},
        )
        assert r.status_code == 200
        _delete_ref(auth_client)


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /propose_from_file/propose_aptitudes
# ─────────────────────────────────────────────────────────────────────────────

class TestProposeFromFileAptitudes:

    def test_propose_aptitudes_without_file_returns_404(self, auth_client, ids):
        _delete_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 404

    def test_propose_aptitudes_no_file_returns_404_error_field(self, auth_client, ids):
        """Sans fichier de référence, la réponse contient un champ error."""
        _delete_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 404
        assert "error" in r.get_json()

    def test_propose_aptitudes_with_file_returns_200(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 200
        _delete_ref(auth_client)

    def test_propose_aptitudes_returns_proposals_list(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        body = r.get_json()
        assert "proposals" in body
        assert isinstance(body["proposals"], list)
        _delete_ref(auth_client)

    def test_propose_aptitudes_source_is_file(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.get_json().get("source") == "file"
        _delete_ref(auth_client)

    def test_propose_aptitudes_with_activity_name(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_name": "Data Analyst"},
        )
        assert r.status_code == 200
        _delete_ref(auth_client)

    def test_propose_aptitudes_proposals_are_strings(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        proposals = r.get_json().get("proposals", [])
        for p in proposals:
            assert isinstance(p, str)
        _delete_ref(auth_client)


# ─────────────────────────────────────────────────────────────────────────────
# 5. POST /propose_from_file/propose_hsc
# ─────────────────────────────────────────────────────────────────────────────

class TestProposeFromFileHSC:

    def test_propose_hsc_without_file_returns_404(self, auth_client, ids):
        _delete_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 404

    def test_propose_hsc_no_file_error_is_no_file(self, auth_client, ids):
        """Sans fichier de référence, le champ error vaut 'no_file'."""
        _delete_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 404
        assert r.get_json().get("error") == "no_file"

    def test_propose_hsc_with_file_returns_200(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 200
        _delete_ref(auth_client)

    def test_propose_hsc_returns_proposals_list(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        body = r.get_json()
        assert "proposals" in body
        assert isinstance(body["proposals"], list)
        _delete_ref(auth_client)

    def test_propose_hsc_source_is_file(self, auth_client, ids):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.get_json().get("source") == "file"
        _delete_ref(auth_client)

    def test_propose_hsc_proposals_have_habilete_field(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_name": "Software Engineer"},
        )
        body = r.get_json()
        for p in body.get("proposals", []):
            assert "habilete" in p
        _delete_ref(auth_client)

    def test_propose_hsc_proposals_have_niveau_field(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_name": "Software Engineer"},
        )
        body = r.get_json()
        for p in body.get("proposals", []):
            assert "niveau" in p
        _delete_ref(auth_client)

    def test_propose_hsc_niveau_is_string(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_name": "Software Engineer"},
        )
        body = r.get_json()
        for p in body.get("proposals", []):
            assert isinstance(p["niveau"], str)
        _delete_ref(auth_client)

    def test_propose_hsc_with_activity_name_returns_proposals(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_name": "Software Engineer"},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert len(body.get("proposals", [])) > 0
        _delete_ref(auth_client)


# ─────────────────────────────────────────────────────────────────────────────
# 6. DELETE /propose_from_file/delete
# ─────────────────────────────────────────────────────────────────────────────

class TestProposeFromFileDelete:

    def test_delete_returns_ok_field(self, auth_client):
        """La réponse de delete contient toujours ok=True."""
        r = auth_client.delete("/propose_from_file/delete")
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

    def test_delete_when_no_file_returns_200(self, auth_client):
        """Idempotent : supprimer sans fichier existant ne plante pas."""
        _delete_ref(auth_client)
        r = auth_client.delete("/propose_from_file/delete")
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

    def test_delete_existing_file_returns_200(self, auth_client):
        _upload_ref(auth_client)
        r = auth_client.delete("/propose_from_file/delete")
        assert r.status_code == 200
        assert r.get_json().get("ok") is True

    def test_delete_makes_status_has_file_false(self, auth_client):
        _upload_ref(auth_client)
        auth_client.delete("/propose_from_file/delete")
        r = auth_client.get("/propose_from_file/status")
        assert r.get_json().get("has_file") is False

    def test_delete_makes_propose_sf_return_404(self, auth_client, ids):
        _upload_ref(auth_client)
        auth_client.delete("/propose_from_file/delete")
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 404

    def test_delete_idempotent_second_call(self, auth_client):
        """Deux suppressions consécutives répondent toutes deux 200."""
        _delete_ref(auth_client)
        r1 = auth_client.delete("/propose_from_file/delete")
        r2 = auth_client.delete("/propose_from_file/delete")
        assert r1.status_code == 200
        assert r2.status_code == 200
