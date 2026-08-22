# Tests de l'assistant d'installation (/setup) — mode premier démarrage.
#
# Isolé volontairement de la fixture `app` partagée (scope=session) : le mode
# setup exige une app créée SANS test_config, avec SETUP_WIZARD=1 et un
# CONFIG_DIR dédié. Chaque test crée sa propre instance et son propre tmpdir.

import json
import os
import smtplib

import pytest

pytestmark = pytest.mark.setup_wizard


@pytest.fixture()
def setup_app(tmp_path, monkeypatch):
    """App en mode installation, CONFIG_DIR isolé, sans restart réel."""
    import Code.app as app_module
    cfg_dir = tmp_path / "config"
    monkeypatch.setenv("SETUP_WIZARD", "1")
    monkeypatch.setenv("SETUP_NO_RESTART", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REQUIRE_LICENSE", raising=False)
    monkeypatch.setattr(app_module, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(app_module, "CONFIG_ENV_PATH", str(cfg_dir / "optiqfluent.env"))
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    return flask_app


class TestSetupMode:

    def test_setup_page_rendue(self, setup_app):
        r = setup_app.test_client().get("/setup/")
        assert r.status_code == 200
        assert b"Assistant d'installation" in r.data

    def test_gate_redirige_tout_vers_setup(self, setup_app):
        c = setup_app.test_client()
        for path in ("/", "/login", "/activities/view"):
            r = c.get(path, follow_redirects=False)
            assert r.status_code == 302
            assert "/setup" in r.headers["Location"]

    def test_healthz_reste_accessible(self, setup_app):
        assert setup_app.test_client().get("/healthz").status_code == 200

    def test_ping_repond(self, setup_app):
        r = setup_app.test_client().get("/setup/ping")
        assert r.get_json() == {"setup": True}

    def test_pas_de_mode_setup_si_deja_configure(self, tmp_path, monkeypatch):
        import Code.app as app_module
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        (cfg_dir / "optiqfluent.env").write_text("SETUP_DONE=1\n")
        monkeypatch.setattr(app_module, "CONFIG_DIR", str(cfg_dir))
        monkeypatch.setattr(app_module, "CONFIG_ENV_PATH",
                            str(cfg_dir / "optiqfluent.env"))
        monkeypatch.setenv("SETUP_WIZARD", "1")
        assert app_module._setup_done() is True


class TestSetupApis:

    def test_db_ko(self, setup_app):
        r = setup_app.test_client().post(
            "/setup/api/test-db",
            json={"url": "postgresql://x:y@hote-inexistant-optiq:5/z"})
        assert r.get_json()["ok"] is False

    def test_db_ok(self, setup_app, tmp_path):
        r = setup_app.test_client().post(
            "/setup/api/test-db", json={"url": f"sqlite:///{tmp_path}/t.db"})
        assert r.get_json()["ok"] is True

    def test_db_url_vide(self, setup_app):
        r = setup_app.test_client().post("/setup/api/test-db", json={"url": ""})
        assert r.get_json()["ok"] is False

    def test_openai_cle_vide(self, setup_app):
        r = setup_app.test_client().post("/setup/api/test-openai", json={"key": ""})
        assert r.get_json()["ok"] is False

    def test_mail_champs_vides(self, setup_app):
        r = setup_app.test_client().post("/setup/api/test-mail", json={})
        data = r.get_json()
        assert data["ok"] is False
        assert "requis" in data["error"].lower()

    def test_mail_port_invalide(self, setup_app):
        r = setup_app.test_client().post("/setup/api/test-mail", json={
            "username": "a@b.fr", "password": "x", "port": "pas-un-port"})
        data = r.get_json()
        assert data["ok"] is False
        assert "port" in data["error"].lower()

    def test_mail_echec_connexion(self, setup_app):
        r = setup_app.test_client().post("/setup/api/test-mail", json={
            "server": "hote-inexistant-optiq", "port": 587,
            "username": "a@b.fr", "password": "x"})
        assert r.get_json()["ok"] is False

    def test_finish_valide_email_admin(self, setup_app, tmp_path):
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": f"sqlite:///{tmp_path}/t.db",
            "admin": {"email": "pas-un-email", "password": "longmotdepasse"}})
        assert r.get_json()["ok"] is False

    def test_finish_valide_mdp_court(self, setup_app, tmp_path):
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": f"sqlite:///{tmp_path}/t.db",
            "admin": {"email": "a@b.fr", "password": "court"}})
        assert r.get_json()["ok"] is False

    def test_finish_ecrit_la_config(self, setup_app, tmp_path):
        import Code.app as app_module
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": f"sqlite:///{tmp_path}/t.db",
            "openai_key": "sk-test",
            "mail": {"username": "n@e.fr", "password": "appmdp",
                     "server": "smtp.gmail.com", "port": 587},
            "admin": {"email": "Admin@Client.FR", "password": "longmotdepasse",
                      "first_name": "Ada", "last_name": "Lovelace"}})
        body = r.get_json()
        assert body["ok"] is True and body["restarting"] is False
        content = open(app_module.CONFIG_ENV_PATH).read()
        assert "SETUP_DONE=1" in content
        assert 'ADMIN_EMAIL="admin@client.fr"' in content
        assert 'OPENAI_API_KEY="sk-test"' in content
        assert 'MAIL_USERNAME="n@e.fr"' in content
        assert "SECRET_KEY=" in content
        assert app_module._setup_done() is True

    def test_scrub_admin_password(self, setup_app, tmp_path):
        import Code.app as app_module
        setup_app.test_client().post("/setup/api/finish", json={
            "database_url": f"sqlite:///{tmp_path}/t.db",
            "admin": {"email": "a@b.fr", "password": "longmotdepasse"}})
        assert "ADMIN_PASSWORD=" in open(app_module.CONFIG_ENV_PATH).read()
        app_module._scrub_admin_password()
        content = open(app_module.CONFIG_ENV_PATH).read()
        assert "ADMIN_PASSWORD=" not in content
        assert 'ADMIN_EMAIL="a@b.fr"' in content


class TestLicenseApi:

    def test_licence_invalide_rejetee(self, setup_app, monkeypatch):
        monkeypatch.setenv("REQUIRE_LICENSE", "1")
        r = setup_app.test_client().post(
            "/setup/api/license", json={"content": '{"pas": "une licence"}'})
        assert r.get_json()["ok"] is False

    def test_licence_repli_config_dir(self, tmp_path, monkeypatch):
        """Une licence sauvée par l'assistant dans CONFIG_DIR doit être trouvée
        même si un LICENSE_PATH d'environnement pointe vers un fichier absent
        (cas du docker-compose historique — bug de la répétition générale)."""
        monkeypatch.setenv("LICENSE_PATH", str(tmp_path / "nexiste-pas.lic"))
        monkeypatch.delenv("OPTIQFLUENT_LICENSE", raising=False)
        monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
        (tmp_path / "optiqfluent.lic").write_bytes(b'{"marqueur": 1}')
        from Code.licensing import _read_license_raw
        raw, mtime = _read_license_raw()
        assert raw == b'{"marqueur": 1}'
        assert mtime is not None

    def test_licence_contenu_vide_rejetee(self, setup_app):
        r = setup_app.test_client().post("/setup/api/license", json={"content": "   "})
        data = r.get_json()
        assert data["ok"] is False
        assert "vide" in data["error"].lower()

    def test_finish_bloque_si_licence_requise_absente(self, setup_app, tmp_path, monkeypatch):
        """REQUIRE_LICENSE=1 sans licence valide déposée doit bloquer /api/finish,
        même si le reste du payload (db, admin) est valide."""
        monkeypatch.setenv("REQUIRE_LICENSE", "1")
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": f"sqlite:///{tmp_path}/t.db",
            "admin": {"email": "a@b.fr", "password": "longmotdepasse"}})
        data = r.get_json()
        assert data["ok"] is False
        assert "licence" in data["error"].lower()


class TestSetupDbUrlNormalization:
    """postgres:// doit être réécrit en postgresql:// avant toute connexion,
    aussi bien pour le test de connexion que pour la config finale écrite."""

    def test_test_db_normalise_le_schema_postgres(self, setup_app):
        r = setup_app.test_client().post(
            "/setup/api/test-db",
            json={"url": "postgres://x:y@hote-inexistant-optiq:5/z"})
        # Doit échouer (hôte inexistant) mais sans lever d'exception non gérée
        data = r.get_json()
        assert data["ok"] is False
        assert "error" in data

    def test_finish_normalise_le_schema_postgres_dans_la_config(self, setup_app, tmp_path):
        import Code.app as app_module
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": "postgres://user:pass@host/db",
            "admin": {"email": "a@b.fr", "password": "longmotdepasse"}})
        assert r.get_json()["ok"] is True
        content = open(app_module.CONFIG_ENV_PATH).read()
        assert "postgresql://user:pass@host/db" in content
        assert "postgres://user:pass@host/db" not in content


class TestSetupApisMocked:
    """Chemins de succès de /api/test-openai et /api/test-mail — le succès
    réel dépend d'un service externe, on le simule pour rester déterministe
    et rapide (les hôtes inexistants ci-dessus couvrent déjà l'échec réseau)."""

    def test_openai_cle_valide_ok(self, setup_app, monkeypatch):
        calls = {}

        class FakeModels:
            def list(self):
                calls["listed"] = True

        class FakeClient:
            def __init__(self, **kwargs):
                calls["kwargs"] = kwargs
                self.models = FakeModels()

        monkeypatch.setattr("openai.OpenAI", FakeClient)
        r = setup_app.test_client().post("/setup/api/test-openai", json={"key": "sk-test-123"})
        data = r.get_json()
        assert data["ok"] is True
        assert calls.get("listed") is True
        assert "base_url" not in calls["kwargs"]

    def test_openai_cle_anthropic_utilise_base_url_dediee(self, setup_app, monkeypatch):
        calls = {}

        class FakeModels:
            def list(self):
                pass

        class FakeClient:
            def __init__(self, **kwargs):
                calls["kwargs"] = kwargs
                self.models = FakeModels()

        monkeypatch.setattr("openai.OpenAI", FakeClient)
        r = setup_app.test_client().post("/setup/api/test-openai", json={"key": "sk-ant-abcdef"})
        data = r.get_json()
        assert data["ok"] is True
        assert "base_url" in calls["kwargs"]

    def test_openai_erreur_client_retournee(self, setup_app, monkeypatch):
        class FailingClient:
            def __init__(self, **kwargs):
                raise RuntimeError("clé invalide")

        monkeypatch.setattr("openai.OpenAI", FailingClient)
        r = setup_app.test_client().post("/setup/api/test-openai", json={"key": "sk-test-123"})
        data = r.get_json()
        assert data["ok"] is False
        assert "clé invalide" in data["error"]

    def test_mail_connexion_reussie_ok(self, setup_app, monkeypatch):
        class FakeSMTP:
            def __init__(self, server, port, timeout=None):
                pass

            def starttls(self):
                pass

            def login(self, username, password):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
        r = setup_app.test_client().post("/setup/api/test-mail", json={
            "server": "smtp.example.com", "port": 587,
            "username": "a@b.fr", "password": "x"})
        assert r.get_json()["ok"] is True
