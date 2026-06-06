# tests/test_39_propose_from_file.py
"""
Couverture des routes non encore testées :
  - propose_from_file.py → /propose_from_file/* (upload, status, propose_sf,
    propose_aptitudes, propose_hsc, delete)
  - activities_render.py → GET /activities/performance/render/<link_id>
"""
import io
import pytest

pytestmark = pytest.mark.propose_from_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_xlsx() -> bytes:
    """Crée un fichier Excel minimal valide en mémoire."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ObjectID", "JobId", "JobText", "GrpName", "CompName", "Required Score"])
    ws.append([1, 101, "Data Analyst", "Technical Skills", "SQL Mastery", 3])
    ws.append([2, 101, "Data Analyst", "Behavioural Competencies", "Self-Regulation", 2])
    ws.append([3, 102, "Project Manager", "Leadership Competencies", "Cooperation", 3])
    ws.append([4, 102, "Project Manager", "Functional Competencies", "Resource Planning", 2])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _upload(auth_client, xlsx_bytes: bytes):
    """POST un fichier xlsx à /propose_from_file/upload."""
    return auth_client.post(
        "/propose_from_file/upload",
        data={"file": (
            io.BytesIO(xlsx_bytes),
            "ref.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )},
        content_type="multipart/form-data",
    )


def _ensure_file(auth_client):
    """Garantit qu'un fichier est uploadé pour l'utilisateur courant."""
    _upload(auth_client, _make_minimal_xlsx())


def _ensure_no_file(auth_client):
    """Garantit qu'aucun fichier n'existe pour l'utilisateur courant."""
    auth_client.delete("/propose_from_file/delete")


def _fresh_link_with_perf(app, ids, name: str):
    """Crée Data + Link + Performance isolés ; retourne (link_id, perf_id)."""
    with app.app_context():
        from Code.models.models import Data, Link, Performance
        from Code.extensions import db
        d = Data(entity_id=ids["entity_id"], name=f"Data-{name}", type="nourrissante")
        db.session.add(d)
        db.session.flush()
        lnk = Link(
            entity_id=ids["entity_id"],
            source_data_id=d.id,
            target_activity_id=ids["activity_id"],
            type="nourrissante",
        )
        db.session.add(lnk)
        db.session.flush()
        perf = Performance(link_id=lnk.id, name=name, description=f"Desc {name}")
        db.session.add(perf)
        db.session.commit()
        return lnk.id, perf.id


def _delete_link_and_perf(app, link_id):
    """Supprime Performance puis Link."""
    with app.app_context():
        from Code.models.models import Link, Performance
        from Code.extensions import db
        p = Performance.query.filter_by(link_id=link_id).first()
        if p:
            db.session.delete(p)
            db.session.flush()
        lnk = Link.query.get(link_id)
        if lnk:
            db.session.delete(lnk)
        db.session.commit()


# ===========================================================================
# 1. POST /propose_from_file/upload
# ===========================================================================

class TestProposeFromFileUpload:

    def test_upload_without_auth_returns_403(self, app):
        """Upload sans session utilisateur → 403."""
        xlsx = _make_minimal_xlsx()
        with app.test_client() as fresh:
            r = fresh.post(
                "/propose_from_file/upload",
                data={"file": (io.BytesIO(xlsx), "ref.xlsx")},
                content_type="multipart/form-data",
            )
        assert r.status_code == 403

    def test_upload_no_file_field_returns_400(self, auth_client):
        """POST sans champ 'file' → 400."""
        r = auth_client.post(
            "/propose_from_file/upload",
            data={},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_upload_valid_xlsx_returns_200_ok(self, auth_client):
        """Upload d'un xlsx valide → 200 + ok: true."""
        r = _upload(auth_client, _make_minimal_xlsx())
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_upload_returns_stats_dict(self, auth_client):
        """La réponse contient un dictionnaire 'stats' non vide."""
        r = _upload(auth_client, _make_minimal_xlsx())
        data = r.get_json()
        assert "stats" in data
        assert isinstance(data["stats"], dict)
        assert len(data["stats"]) > 0

    def test_upload_second_time_replaces_file(self, auth_client):
        """Un second upload remplace le fichier précédent (idempotent)."""
        _upload(auth_client, _make_minimal_xlsx())
        r2 = _upload(auth_client, _make_minimal_xlsx())
        assert r2.status_code == 200
        assert r2.get_json()["ok"] is True


# ===========================================================================
# 2. GET /propose_from_file/status
# ===========================================================================

class TestProposeFromFileStatus:

    def test_status_unauthenticated_returns_has_file_false(self, app):
        """GET /status sans session → 200 + has_file: False."""
        with app.test_client() as fresh:
            r = fresh.get("/propose_from_file/status")
        assert r.status_code == 200
        assert r.get_json()["has_file"] is False

    def test_status_without_file_returns_has_file_false(self, auth_client):
        """GET /status quand aucun fichier uploadé → has_file: False."""
        _ensure_no_file(auth_client)
        r = auth_client.get("/propose_from_file/status")
        assert r.status_code == 200
        assert r.get_json()["has_file"] is False

    def test_status_after_upload_returns_has_file_true(self, auth_client):
        """GET /status après upload → has_file: True."""
        _ensure_file(auth_client)
        r = auth_client.get("/propose_from_file/status")
        assert r.status_code == 200
        assert r.get_json()["has_file"] is True

    def test_status_after_upload_includes_stats(self, auth_client):
        """GET /status après upload inclut les stats."""
        _ensure_file(auth_client)
        r = auth_client.get("/propose_from_file/status")
        data = r.get_json()
        assert "stats" in data
        assert isinstance(data["stats"], dict)

    def test_status_after_delete_returns_has_file_false(self, auth_client):
        """GET /status après suppression du fichier → has_file: False."""
        _ensure_file(auth_client)
        auth_client.delete("/propose_from_file/delete")
        r = auth_client.get("/propose_from_file/status")
        assert r.get_json()["has_file"] is False


# ===========================================================================
# 3. POST /propose_from_file/propose_sf
# ===========================================================================

class TestProposeFromFileSf:

    def test_propose_sf_without_auth_returns_403(self, app):
        """propose_sf sans session → 403."""
        with app.test_client() as fresh:
            r = fresh.post("/propose_from_file/propose_sf", json={})
        assert r.status_code == 403

    def test_propose_sf_no_file_returns_404(self, auth_client):
        """propose_sf sans fichier uploadé → 404 + error no_file."""
        _ensure_no_file(auth_client)
        r = auth_client.post("/propose_from_file/propose_sf", json={})
        assert r.status_code == 404
        assert r.get_json()["error"] == "no_file"

    def test_propose_sf_with_file_returns_200(self, auth_client, ids):
        """propose_sf avec fichier et activity_id → 200 + proposals."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "proposals_sf" in data
        assert "proposals_s" in data
        assert data["source"] == "file"

    def test_propose_sf_proposals_are_lists_of_strings(self, auth_client, ids):
        """proposals_sf et proposals_s sont des listes de chaînes."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        data = r.get_json()
        assert isinstance(data["proposals_sf"], list)
        assert isinstance(data["proposals_s"], list)
        assert all(isinstance(s, str) for s in data["proposals_sf"])
        assert all(isinstance(s, str) for s in data["proposals_s"])

    def test_propose_sf_total_at_most_14(self, auth_client, ids):
        """Total proposals_sf + proposals_s ne dépasse pas 14 (max_results)."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_sf",
            json={"activity_id": ids["activity_id"]},
        )
        data = r.get_json()
        assert len(data["proposals_sf"]) + len(data["proposals_s"]) <= 14

    def test_propose_sf_without_activity_id_returns_200(self, auth_client):
        """propose_sf sans activity_id → 200 (contexte vide, fallback fréquence)."""
        _ensure_file(auth_client)
        r = auth_client.post("/propose_from_file/propose_sf", json={})
        assert r.status_code == 200


# ===========================================================================
# 4. POST /propose_from_file/propose_aptitudes
# ===========================================================================

class TestProposeFromFileAptitudes:

    def test_propose_aptitudes_without_auth_returns_403(self, app):
        """propose_aptitudes sans session → 403."""
        with app.test_client() as fresh:
            r = fresh.post("/propose_from_file/propose_aptitudes", json={})
        assert r.status_code == 403

    def test_propose_aptitudes_no_file_returns_404(self, auth_client):
        """propose_aptitudes sans fichier → 404."""
        _ensure_no_file(auth_client)
        r = auth_client.post("/propose_from_file/propose_aptitudes", json={})
        assert r.status_code == 404

    def test_propose_aptitudes_with_file_returns_200(self, auth_client, ids):
        """propose_aptitudes avec fichier → 200 + proposals list + source."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "proposals" in data
        assert isinstance(data["proposals"], list)
        assert data["source"] == "file"

    def test_propose_aptitudes_at_most_8_proposals(self, auth_client, ids):
        """propose_aptitudes retourne au plus 8 proposals (max_results=8)."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_aptitudes",
            json={"activity_id": ids["activity_id"]},
        )
        assert len(r.get_json()["proposals"]) <= 8


# ===========================================================================
# 5. POST /propose_from_file/propose_hsc
# ===========================================================================

class TestProposeFromFileHsc:

    def test_propose_hsc_without_auth_returns_403(self, app):
        """propose_hsc sans session → 403."""
        with app.test_client() as fresh:
            r = fresh.post("/propose_from_file/propose_hsc", json={})
        assert r.status_code == 403

    def test_propose_hsc_no_file_returns_404(self, auth_client):
        """propose_hsc sans fichier → 404."""
        _ensure_no_file(auth_client)
        r = auth_client.post("/propose_from_file/propose_hsc", json={})
        assert r.status_code == 404

    def test_propose_hsc_with_file_returns_200(self, auth_client, ids):
        """propose_hsc avec fichier → 200 + proposals."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "proposals" in data
        assert isinstance(data["proposals"], list)
        assert data["source"] == "file"

    def test_propose_hsc_proposals_have_required_fields(self, auth_client, ids):
        """Chaque proposal HSC a les champs habilete, niveau, justification."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        for p in r.get_json()["proposals"]:
            assert "habilete" in p
            assert "niveau" in p
            assert "justification" in p

    def test_propose_hsc_at_most_9_proposals(self, auth_client, ids):
        """propose_hsc retourne au plus 9 proposals (max_results=9)."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        assert len(r.get_json()["proposals"]) <= 9

    def test_propose_hsc_niveau_non_empty(self, auth_client, ids):
        """Le champ 'niveau' de chaque proposal HSC est une chaîne non vide."""
        _ensure_file(auth_client)
        r = auth_client.post(
            "/propose_from_file/propose_hsc",
            json={"activity_id": ids["activity_id"]},
        )
        for p in r.get_json()["proposals"]:
            assert isinstance(p["niveau"], str) and len(p["niveau"]) > 0


# ===========================================================================
# 6. DELETE /propose_from_file/delete
# ===========================================================================

class TestProposeFromFileDelete:

    def test_delete_without_auth_returns_403(self, app):
        """DELETE sans session → 403."""
        with app.test_client() as fresh:
            r = fresh.delete("/propose_from_file/delete")
        assert r.status_code == 403

    def test_delete_when_no_file_still_returns_200(self, auth_client):
        """DELETE sans fichier existant → 200 ok (idempotent)."""
        _ensure_no_file(auth_client)
        r = auth_client.delete("/propose_from_file/delete")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_delete_removes_uploaded_file(self, auth_client):
        """Après DELETE, /status retourne has_file: False."""
        _ensure_file(auth_client)
        r_del = auth_client.delete("/propose_from_file/delete")
        assert r_del.status_code == 200
        r_status = auth_client.get("/propose_from_file/status")
        assert r_status.get_json()["has_file"] is False

    def test_delete_is_idempotent(self, auth_client):
        """Double DELETE → 200 les deux fois."""
        _ensure_file(auth_client)
        r1 = auth_client.delete("/propose_from_file/delete")
        r2 = auth_client.delete("/propose_from_file/delete")
        assert r1.status_code == 200
        assert r2.status_code == 200


# ===========================================================================
# 7. GET /activities/performance/render/<link_id>  (activities_render.py)
# ===========================================================================

class TestActivitiesRenderPerformance:

    def test_render_unknown_link_returns_empty_list(self, auth_client):
        """GET avec link_id inexistant → 200 + liste vide."""
        r = auth_client.get("/activities/performance/render/999999")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_render_with_perf_returns_the_performance(self, auth_client, ids, app):
        """Une Performance créée pour un link → elle apparaît dans la réponse."""
        link_id, perf_id = _fresh_link_with_perf(app, ids, "KPI Render Test")
        try:
            r = auth_client.get(f"/activities/performance/render/{link_id}")
            assert r.status_code == 200
            items = r.get_json()
            assert isinstance(items, list)
            assert any(p["id"] == perf_id for p in items)
        finally:
            _delete_link_and_perf(app, link_id)

    def test_render_response_items_have_id_name_description(self, auth_client, ids, app):
        """Chaque item de la réponse a les champs id, name, description."""
        link_id, perf_id = _fresh_link_with_perf(app, ids, "KPI Fields Check")
        try:
            r = auth_client.get(f"/activities/performance/render/{link_id}")
            items = r.get_json()
            matching = [p for p in items if p.get("id") == perf_id]
            assert len(matching) == 1
            item = matching[0]
            assert "id" in item
            assert "name" in item
            assert "description" in item
        finally:
            _delete_link_and_perf(app, link_id)

    def test_render_name_matches_stored_value(self, auth_client, ids, app):
        """Le champ 'name' retourné correspond à ce qui est stocké en base."""
        link_id, perf_id = _fresh_link_with_perf(app, ids, "KPI Name Match")
        try:
            r = auth_client.get(f"/activities/performance/render/{link_id}")
            items = r.get_json()
            found = next((p for p in items if p.get("id") == perf_id), None)
            assert found is not None
            assert found["name"] == "KPI Name Match"
        finally:
            _delete_link_and_perf(app, link_id)

    def test_render_returns_json_content_type(self, auth_client):
        """La réponse est bien du JSON (Content-Type application/json)."""
        r = auth_client.get("/activities/performance/render/999999")
        assert r.content_type.startswith("application/json")
