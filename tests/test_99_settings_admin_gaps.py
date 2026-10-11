# tests/test_99_settings_admin_gaps.py
"""
Routes : /parametres — branches rarement atteintes
(masquage de l'URL de base, offset de logs invalide, persistance de la langue).
"""
import pytest

pytestmark = pytest.mark.settings


class TestVueAdminUrlBase:

    def test_mot_de_passe_de_la_base_est_masque(self, auth_client, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://optiq:S3cr3t!@db.example:5432/optiq")
        r = auth_client.get("/parametres/admin/overview")
        assert r.status_code == 200
        masked = r.get_json()["db_url_masked"]
        assert "S3cr3t" not in masked
        assert masked == "postgresql://optiq:••••••@db.example:5432/optiq"

    def test_url_sans_identifiants_reste_inchangee(self, auth_client, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///local.db")
        r = auth_client.get("/parametres/admin/overview")
        assert r.get_json()["db_url_masked"] == "sqlite:///local.db"

    def test_sans_url_indique_la_base_locale(self, auth_client, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        r = auth_client.get("/parametres/admin/overview")
        assert r.get_json()["db_url_masked"] == "(base SQLite locale)"


class TestLogsOffsetInvalide:

    def test_offset_non_numerique_retombe_sur_zero(self, auth_client):
        r = auth_client.get("/parametres/admin/logs?offset=abc")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert isinstance(body["data"], str)
        assert body["offset"] >= 0


class TestLangueEchecPersistance:

    def test_langue_reste_active_en_session_si_la_base_echoue(
            self, app, auth_client, monkeypatch):
        from Code.extensions import db
        original = db.session.commit

        def _boom():
            raise RuntimeError("commit impossible")

        with app.app_context():
            from Code.models.models import User
            user = User.query.filter_by(email="test@devoptiq.com").first()
            previous = user.lang
        target = "en" if previous != "en" else "fr"
        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            r = auth_client.post("/parametres/set_language", json={"lang": target})
        finally:
            monkeypatch.setattr(db.session, "commit", original)
        assert r.status_code == 200
        assert r.get_json() == {"ok": True, "lang": target}
        with auth_client.session_transaction() as sess:
            assert sess["lang"] == target
            sess["lang"] = "fr"
        with app.app_context():
            from Code.models.models import User
            assert User.query.filter_by(email="test@devoptiq.com").first().lang == previous
