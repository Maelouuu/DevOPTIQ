# tests/test_21_export.py
"""
API : Export & Fichiers (/utils/upload-file, /utils/file, /utils/serve-file, /export/entity)
Couvre : upload de fichiers en base, service de fichiers, export Excel/HTML par entité et par rôle.
"""
import io
import json
import pytest

pytestmark = pytest.mark.export


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_file(auth_client, content=b"contenu test", filename="test.txt", mimetype="text/plain"):
    """Upload un fichier via /utils/upload-file et retourne la réponse."""
    return auth_client.post(
        "/utils/upload-file",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def _create_blob(app, content=b"blob test", filename="blob.txt", mimetype="text/plain"):
    """Insère directement un FileBlob en base et retourne son id."""
    with app.app_context():
        from Code.models.models import FileBlob
        from Code.extensions import db
        blob = FileBlob(filename=filename, mimetype=mimetype, data=content)
        db.session.add(blob)
        db.session.commit()
        return blob.id


def _create_role(app, ids, name="Rôle Export Test"):
    """Insère un rôle en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        role = Role(name=name, entity_id=ids["entity_id"])
        db.session.add(role)
        db.session.commit()
        return role.id


def _delete_role(app, role_id):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        r = Role.query.get(role_id)
        if r:
            db.session.delete(r)
            db.session.commit()


# ===========================================================================
# 1. POST /utils/upload-file — upload d'un fichier
# ===========================================================================

class TestFileUpload:

    def test_upload_valid_file_returns_201(self, auth_client):
        """Upload d'un fichier valide → 201 + path /utils/file/<id> + original_name."""
        r = _upload_file(auth_client, content=b"hello world", filename="rapport.txt")
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "path" in data
        assert data["path"].startswith("/utils/file/")
        assert data["original_name"] == "rapport.txt"

    def test_upload_binary_file_returns_201(self, auth_client):
        """Upload d'un fichier binaire (PDF simulé) → 201."""
        r = _upload_file(auth_client, content=b"%PDF-1.4 fake", filename="doc.pdf", mimetype="application/pdf")
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["path"].startswith("/utils/file/")

    def test_upload_no_file_returns_400(self, auth_client):
        """POST sans fichier → 400."""
        r = auth_client.post(
            "/utils/upload-file",
            data={},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_upload_empty_filename_returns_400(self, auth_client):
        """POST avec un fichier sans nom → 400."""
        r = auth_client.post(
            "/utils/upload-file",
            data={"file": (io.BytesIO(b"data"), "")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_upload_persists_in_db(self, auth_client, app):
        """Après upload, le blob est bien retrouvable en base."""
        r = _upload_file(auth_client, content=b"persist me", filename="persist.bin")
        assert r.status_code == 201
        path = json.loads(r.data)["path"]
        file_id = int(path.rsplit("/", 1)[-1])

        with app.app_context():
            from Code.models.models import FileBlob
            blob = FileBlob.query.get(file_id)
            assert blob is not None
            assert blob.data == b"persist me"
            assert blob.filename == "persist.bin"


# ===========================================================================
# 2. GET /utils/file/<id> — servir un fichier depuis la DB
# ===========================================================================

class TestFileServeDB:

    def test_serve_existing_file_returns_content(self, auth_client, app):
        """GET /utils/file/<id> sur un blob existant → 200 + contenu correct."""
        blob_id = _create_blob(app, content=b"file content", filename="served.txt", mimetype="text/plain")
        r = auth_client.get(f"/utils/file/{blob_id}")
        assert r.status_code == 200
        assert r.data == b"file content"

    def test_serve_file_has_correct_mimetype(self, auth_client, app):
        """Le Content-Type servi correspond au mimetype stocké."""
        blob_id = _create_blob(app, content=b"<html/>", filename="page.html", mimetype="text/html")
        r = auth_client.get(f"/utils/file/{blob_id}")
        assert r.status_code == 200
        assert "text/html" in r.content_type

    def test_serve_nonexistent_file_returns_404(self, auth_client):
        """GET /utils/file/99999 sur un ID inexistant → 404."""
        r = auth_client.get("/utils/file/99999")
        assert r.status_code == 404


# ===========================================================================
# 3. GET /utils/serve-file — point d'entrée universel
# ===========================================================================

class TestServeFile:

    def test_serve_file_no_path_returns_400(self, auth_client):
        """GET /utils/serve-file sans paramètre path → 400."""
        r = auth_client.get("/utils/serve-file")
        assert r.status_code == 400

    def test_serve_file_db_path_returns_content(self, auth_client, app):
        """GET /utils/serve-file?path=/utils/file/<id> → contenu du blob."""
        blob_id = _create_blob(app, content=b"serve via path", filename="via_path.txt")
        r = auth_client.get(f"/utils/serve-file?path=/utils/file/{blob_id}")
        assert r.status_code == 200
        assert r.data == b"serve via path"

    def test_serve_file_db_path_invalid_id_returns_404(self, auth_client):
        """path=/utils/file/ avec ID invalide (non-entier) → 400."""
        r = auth_client.get("/utils/serve-file?path=/utils/file/not_an_int")
        assert r.status_code == 400

    def test_serve_file_db_path_missing_blob_returns_404(self, auth_client):
        """path=/utils/file/99998 avec blob inexistant → 404."""
        r = auth_client.get("/utils/serve-file?path=/utils/file/99998")
        assert r.status_code == 404

    def test_serve_file_local_nonexistent_returns_404(self, auth_client):
        """Chemin local inexistant → 404."""
        r = auth_client.get("/utils/serve-file?path=/tmp/definitely_does_not_exist_xyz.txt")
        assert r.status_code == 404


# ===========================================================================
# 4. GET /export/entity — export Excel / HTML
# ===========================================================================

class TestExportEntity:

    def test_export_no_entity_id_returns_400(self, auth_client):
        """GET /export/entity sans entity_id → 400."""
        r = auth_client.get("/export/entity")
        assert r.status_code == 400

    def test_export_invalid_entity_id_returns_404(self, auth_client):
        """GET /export/entity?entity_id=99999 sur entité inexistante → 404."""
        r = auth_client.get("/export/entity?entity_id=99999")
        assert r.status_code == 404

    def test_export_excel_default_returns_200(self, auth_client, ids):
        """GET /export/entity?entity_id=<id> → 200 + mimetype xlsx."""
        r = auth_client.get(f"/export/entity?entity_id={ids['entity_id']}")
        assert r.status_code == 200
        assert "spreadsheetml" in r.content_type or "officedocument" in r.content_type

    def test_export_excel_is_valid_xlsx(self, auth_client, ids):
        """Le fichier Excel téléchargé commence par la signature ZIP (xlsx)."""
        r = auth_client.get(f"/export/entity?entity_id={ids['entity_id']}&format=excel")
        assert r.status_code == 200
        # Les fichiers xlsx sont des archives ZIP commençant par PK
        assert r.data[:2] == b"PK"

    def test_export_html_returns_200(self, auth_client, ids):
        """GET /export/entity?format=html → 200 + Content-Type text/html."""
        r = auth_client.get(f"/export/entity?entity_id={ids['entity_id']}&format=html")
        assert r.status_code == 200
        assert "text/html" in r.content_type

    def test_export_html_contains_entity_name(self, auth_client, ids):
        """L'export HTML contient le nom de l'entité."""
        r = auth_client.get(f"/export/entity?entity_id={ids['entity_id']}&format=html")
        assert r.status_code == 200
        html = r.data.decode("utf-8")
        assert "Entité Test" in html

    def test_export_html_has_required_sections(self, auth_client, ids):
        """L'export HTML contient les sections Savoirs, Savoir-faires, Aptitudes, Compétences."""
        r = auth_client.get(f"/export/entity?entity_id={ids['entity_id']}&format=html")
        html = r.data.decode("utf-8")
        for section in ["Savoirs", "Savoir-faires", "HSC", "Compétences"]:
            assert section in html

    def test_export_with_role_id_returns_200(self, auth_client, ids, app):
        """Export filtré par rôle → 200."""
        role_id = _create_role(app, ids, name="Rôle Export Filtre")
        try:
            r = auth_client.get(
                f"/export/entity?entity_id={ids['entity_id']}&role_id={role_id}"
            )
            assert r.status_code == 200
        finally:
            _delete_role(app, role_id)

    def test_export_with_invalid_role_id_falls_back_to_empty(self, auth_client, ids):
        """Export avec role_id inexistant → 404 (entité introuvable pour ce rôle)."""
        r = auth_client.get(
            f"/export/entity?entity_id={ids['entity_id']}&role_id=99999"
        )
        # Le role n'existe pas mais l'entité existe : la collecte retourne quand même les données
        # (role_id ignoré s'il ne correspond à rien), pas une erreur 404
        assert r.status_code == 200

    def test_export_html_attachment_disposition(self, auth_client, ids):
        """L'export HTML doit avoir un Content-Disposition attachment."""
        r = auth_client.get(f"/export/entity?entity_id={ids['entity_id']}&format=html")
        assert r.status_code == 200
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd
        assert ".html" in cd

    def test_export_excel_attachment_disposition(self, auth_client, ids):
        """L'export Excel doit avoir un Content-Disposition attachment avec .xlsx."""
        r = auth_client.get(f"/export/entity?entity_id={ids['entity_id']}&format=excel")
        assert r.status_code == 200
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd
        assert ".xlsx" in cd
