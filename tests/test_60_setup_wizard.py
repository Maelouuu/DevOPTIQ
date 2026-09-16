# Tests de l'assistant d'installation (/setup) — mode premier démarrage.
#
# Isolé volontairement de la fixture `app` partagée (scope=session) : le mode
# setup exige une app créée SANS test_config, avec SETUP_WIZARD=1 et un
# CONFIG_DIR dédié. Chaque test crée sa propre instance et son propre tmpdir.

import json
import os
import signal
import sys
import time as real_time

import pytest


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

    def test_mail_connexion_reussie(self, setup_app, monkeypatch):
        import smtplib

        class _FakeSMTP:
            def __init__(self, server, port, timeout=10):
                pass

            def starttls(self):
                pass

            def login(self, username, password):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
        r = setup_app.test_client().post("/setup/api/test-mail", json={
            "server": "smtp.test", "port": 587,
            "username": "a@b.fr", "password": "x"})
        assert r.get_json()["ok"] is True

    def test_db_postgres_scheme_normalise(self, setup_app):
        """Le préfixe legacy postgres:// est normalisé en postgresql://."""
        r = setup_app.test_client().post(
            "/setup/api/test-db",
            json={"url": "postgres://x:y@hote-inexistant-optiq:5/z"})
        assert r.get_json()["ok"] is False

    def test_openai_cle_valide(self, setup_app, monkeypatch):
        import openai

        class _FakeModels:
            def list(self):
                return {"data": []}

        class _FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            models = _FakeModels()

        monkeypatch.setattr(openai, "OpenAI", _FakeClient)
        r = setup_app.test_client().post(
            "/setup/api/test-openai", json={"key": "sk-test123"})
        assert r.get_json()["ok"] is True

    def test_openai_cle_anthropic_utilise_base_url_claude(self, setup_app, monkeypatch):
        import openai

        calls = {}

        class _FakeModels:
            def list(self):
                return {"data": []}

        class _FakeClient:
            def __init__(self, **kwargs):
                calls.update(kwargs)

            models = _FakeModels()

        monkeypatch.setattr(openai, "OpenAI", _FakeClient)
        r = setup_app.test_client().post(
            "/setup/api/test-openai", json={"key": "sk-ant-test123"})
        assert r.get_json()["ok"] is True
        assert "base_url" in calls

    def test_openai_cle_invalide_retourne_erreur(self, setup_app, monkeypatch):
        import openai

        class _FakeModels:
            def list(self):
                raise RuntimeError("clé invalide")

        class _FakeClient:
            def __init__(self, **kwargs):
                pass

            models = _FakeModels()

        monkeypatch.setattr(openai, "OpenAI", _FakeClient)
        r = setup_app.test_client().post(
            "/setup/api/test-openai", json={"key": "sk-mauvaise"})
        data = r.get_json()
        assert data["ok"] is False
        assert "clé invalide" in data["error"]

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

    def test_finish_db_url_manquante(self, setup_app):
        r = setup_app.test_client().post("/setup/api/finish", json={
            "admin": {"email": "a@b.fr", "password": "longmotdepasse"}})
        data = r.get_json()
        assert data["ok"] is False
        assert "base de données" in data["error"].lower()

    def test_finish_postgres_scheme_normalise(self, setup_app):
        import Code.app as app_module
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": "postgres://x:y@hote/db",
            "admin": {"email": "c@d.fr", "password": "longmotdepasse"}})
        assert r.get_json()["ok"] is True
        content = open(app_module.CONFIG_ENV_PATH).read()
        assert 'DATABASE_URL="postgresql://x:y@hote/db"' in content

    def test_finish_licence_requise_manquante_bloque(self, setup_app, monkeypatch):
        import Code.licensing as licensing_mod
        monkeypatch.setenv("REQUIRE_LICENSE", "1")

        def _fake_verify():
            raise licensing_mod.LicenseError("pas de licence")

        monkeypatch.setattr(licensing_mod, "verify_license", _fake_verify)
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": "sqlite:///x.db",
            "admin": {"email": "a@b.fr", "password": "longmotdepasse"}})
        data = r.get_json()
        assert data["ok"] is False
        assert "licence" in data["error"].lower()

    def test_finish_inclut_license_path_si_fichier_present(self, setup_app, tmp_path):
        import Code.app as app_module
        os.makedirs(app_module.CONFIG_DIR, exist_ok=True)
        lic_path = os.path.join(app_module.CONFIG_DIR, "optiqfluent.lic")
        with open(lic_path, "w", encoding="utf-8") as f:
            f.write("dummy")
        r = setup_app.test_client().post("/setup/api/finish", json={
            "database_url": f"sqlite:///{tmp_path}/t3.db",
            "admin": {"email": "e@f.fr", "password": "longmotdepasse"}})
        data = r.get_json()
        assert data["ok"] is True
        content = open(app_module.CONFIG_ENV_PATH).read()
        assert f'LICENSE_PATH="{lic_path}"' in content

    def test_finish_erreur_ecriture_config(self, tmp_path, monkeypatch):
        """CONFIG_DIR pointe sur un chemin bloqué (fichier existant) → 'ok': False."""
        import Code.app as app_module
        blocker = tmp_path / "config_bloque"
        blocker.write_text("un fichier, pas un dossier")
        monkeypatch.setenv("SETUP_WIZARD", "1")
        monkeypatch.setenv("SETUP_NO_RESTART", "1")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("REQUIRE_LICENSE", raising=False)
        monkeypatch.setattr(app_module, "CONFIG_DIR", str(blocker))
        monkeypatch.setattr(app_module, "CONFIG_ENV_PATH", str(blocker / "optiqfluent.env"))
        flask_app = app_module.create_app()
        flask_app.config["TESTING"] = True
        r = flask_app.test_client().post("/setup/api/finish", json={
            "database_url": "sqlite:///x.db",
            "admin": {"email": "a@b.fr", "password": "longmotdepasse"}})
        data = r.get_json()
        assert data["ok"] is False
        assert "Écriture impossible" in data["error"]

    def test_schedule_restart_declenche_sigterm(self, setup_app, monkeypatch):
        """Sous gunicorn (simulé), _schedule_restart programme un SIGTERM différé."""
        import Code.routes.setup_wizard as sw_module

        monkeypatch.delenv("SETUP_NO_RESTART", raising=False)
        monkeypatch.setitem(sys.modules, "gunicorn", object())
        monkeypatch.setattr(sw_module.time, "sleep", lambda s: None)

        killed = {}

        def _fake_kill(pid, sig):
            killed["pid"] = pid
            killed["sig"] = sig

        monkeypatch.setattr(sw_module.os, "kill", _fake_kill)

        assert sw_module._schedule_restart() is True

        for _ in range(50):
            if killed:
                break
            real_time.sleep(0.05)

        assert killed.get("sig") == signal.SIGTERM


class TestLicenseApi:

    def test_licence_invalide_rejetee(self, setup_app, monkeypatch):
        monkeypatch.setenv("REQUIRE_LICENSE", "1")
        r = setup_app.test_client().post(
            "/setup/api/license", json={"content": '{"pas": "une licence"}'})
        assert r.get_json()["ok"] is False

    def test_licence_contenu_vide(self, setup_app):
        r = setup_app.test_client().post("/setup/api/license", json={"content": "   "})
        data = r.get_json()
        assert data["ok"] is False
        assert "vide" in data["error"].lower()

    def test_licence_valide_enregistree(self, setup_app, monkeypatch):
        import Code.app as app_module
        import Code.licensing as licensing_mod
        from datetime import date, timedelta

        def _fake_verify_bytes(raw):
            return {"licensee": "ACME Corp", "expires_at": date.today() + timedelta(days=10)}

        monkeypatch.setattr(licensing_mod, "verify_license_bytes", _fake_verify_bytes)
        r = setup_app.test_client().post(
            "/setup/api/license", json={"content": "peu importe le contenu"})
        data = r.get_json()
        assert data["ok"] is True
        assert data["licensee"] == "ACME Corp"
        lic_file = os.path.join(app_module.CONFIG_DIR, "optiqfluent.lic")
        assert os.path.isfile(lic_file)

    def test_licence_erreur_ecriture(self, tmp_path, monkeypatch):
        """CONFIG_DIR bloqué (fichier existant) → écriture de la licence impossible."""
        import Code.app as app_module
        import Code.licensing as licensing_mod
        from datetime import date, timedelta

        blocker = tmp_path / "config_bloque"
        blocker.write_text("un fichier, pas un dossier")
        monkeypatch.setenv("SETUP_WIZARD", "1")
        monkeypatch.setenv("SETUP_NO_RESTART", "1")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("REQUIRE_LICENSE", raising=False)
        monkeypatch.setattr(app_module, "CONFIG_DIR", str(blocker))
        monkeypatch.setattr(app_module, "CONFIG_ENV_PATH", str(blocker / "optiqfluent.env"))
        flask_app = app_module.create_app()
        flask_app.config["TESTING"] = True

        def _fake_verify_bytes(raw):
            return {"licensee": "ACME", "expires_at": date.today() + timedelta(days=10)}

        monkeypatch.setattr(licensing_mod, "verify_license_bytes", _fake_verify_bytes)
        r = flask_app.test_client().post(
            "/setup/api/license", json={"content": "peu importe"})
        data = r.get_json()
        assert data["ok"] is False
        assert "Écriture impossible" in data["error"]

    def test_licence_expiree_rejetee(self, setup_app, monkeypatch):
        import Code.licensing as licensing_mod
        from datetime import date, timedelta

        def _fake_verify_bytes(raw):
            return {"licensee": "ACME", "expires_at": date.today() - timedelta(days=1)}

        monkeypatch.setattr(licensing_mod, "verify_license_bytes", _fake_verify_bytes)
        r = setup_app.test_client().post(
            "/setup/api/license", json={"content": "peu importe"})
        data = r.get_json()
        assert data["ok"] is False
        assert "expirée" in data["error"].lower()


class TestLicenseStatusPage:
    """Couvre _license_status() via la page d'accueil de l'assistant (GET /setup/)."""

    def test_page_licence_valide(self, setup_app, monkeypatch):
        import Code.licensing as licensing_mod
        from datetime import date, timedelta

        monkeypatch.setenv("REQUIRE_LICENSE", "1")

        def _fake_verify():
            return {"licensee": "ACME", "expires_at": date.today() + timedelta(days=30)}

        monkeypatch.setattr(licensing_mod, "verify_license", _fake_verify)
        r = setup_app.test_client().get("/setup/")
        assert r.status_code == 200

    def test_page_licence_invalide(self, setup_app, monkeypatch):
        import Code.licensing as licensing_mod

        monkeypatch.setenv("REQUIRE_LICENSE", "1")

        def _fake_verify():
            raise licensing_mod.LicenseError("licence expirée")

        monkeypatch.setattr(licensing_mod, "verify_license", _fake_verify)
        r = setup_app.test_client().get("/setup/")
        assert r.status_code == 200

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
