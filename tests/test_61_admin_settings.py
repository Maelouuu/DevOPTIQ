# Tests de la section admin de la page Paramètres : clé IA à chaud (app_settings),
# masquage, révélation, URL BDD, console serveur. Données dédiées + cleanup
# (base partagée scope=session).

import pytest


class TestAiKeyAccessor:

    def test_repli_env(self, app, monkeypatch):
        from Code.ai_key import get_openai_key, set_openai_key
        with app.app_context():
            set_openai_key("")                      # aucun réglage en base
            monkeypatch.setenv("OPENAI_API_KEY", "sk-env-test")
            assert get_openai_key() == "sk-env-test"

    def test_priorite_base_sur_env(self, app, monkeypatch):
        from Code.ai_key import get_openai_key, set_openai_key
        with app.app_context():
            monkeypatch.setenv("OPENAI_API_KEY", "sk-env-test")
            set_openai_key("sk-db-test-123456")
            assert get_openai_key() == "sk-db-test-123456"
            set_openai_key("")                      # cleanup → retour au repli env
            assert get_openai_key() == "sk-env-test"

    def test_masquage(self):
        from Code.ai_key import mask_key
        masked = mask_key("sk-proj-abcdefghijklmnop1234")
        assert masked.startswith("sk-proj") and masked.endswith("1234")
        assert "abcdefgh" not in masked
        assert mask_key(None) is None


class TestAdminEndpoints:

    def test_overview_admin(self, auth_client):
        r = auth_client.get("/parametres/admin/overview")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert "db_url_masked" in body and "openai_key_set" in body

    def test_reveal_et_sauvegarde(self, app, auth_client, monkeypatch):
        from Code.ai_key import get_openai_key, set_openai_key
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        r = auth_client.post("/parametres/admin/openai-key",
                             json={"key": "sk-test-nouvelle-cle-9876"})
        assert r.get_json()["ok"] is True
        with app.app_context():
            assert get_openai_key() == "sk-test-nouvelle-cle-9876"
        r = auth_client.post("/parametres/admin/openai-key/reveal")
        assert r.get_json()["key"] == "sk-test-nouvelle-cle-9876"
        with app.app_context():
            set_openai_key("")                      # cleanup

    def test_format_invalide_rejete(self, auth_client):
        r = auth_client.post("/parametres/admin/openai-key", json={"key": "pas-une-cle"})
        assert r.status_code == 400

    def test_logs_admin(self, auth_client):
        from Code import logstream
        logstream._append("MARQUEUR-TEST-CONSOLE-61\n")
        r = auth_client.get("/parametres/admin/logs?offset=0")
        assert r.status_code == 200
        assert "MARQUEUR-TEST-CONSOLE-61" in r.get_json()["data"]

    def test_page_parametres_signale_admin(self, auth_client):
        r = auth_client.get("/parametres/")
        assert r.status_code == 200
        assert b"stt-console" in r.data              # section admin rendue


class TestNonAdminRefuse:

    @pytest.fixture()
    def user_client(self, app):
        """Client authentifié avec un utilisateur SANS statut administrateur."""
        from Code.extensions import db
        from Code.models.models import User, Entity
        from werkzeug.security import generate_password_hash
        with app.app_context():
            entity = Entity.query.filter_by(name="Entité Test").first()
            user = User(entity_id=entity.id, first_name="Sans", last_name="Droits",
                        email="viewer61@test.fr",
                        password=generate_password_hash("x" * 10), status="user")
            db.session.add(user)
            db.session.commit()
            uid, eid = user.id, entity.id
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = uid
            sess["user_email"] = "viewer61@test.fr"
            sess["active_entity_id"] = eid
        yield c
        with app.app_context():
            u = db.session.get(User, uid)
            if u:
                db.session.delete(u)
                db.session.commit()

    def test_endpoints_refuses(self, user_client):
        assert user_client.get("/parametres/admin/overview").status_code == 403
        assert user_client.post("/parametres/admin/openai-key/reveal").status_code == 403
        assert user_client.post("/parametres/admin/openai-key",
                                json={"key": "sk-x"}).status_code == 403
        assert user_client.get("/parametres/admin/logs").status_code == 403

    def test_section_invisible(self, user_client):
        r = user_client.get("/parametres/")
        assert r.status_code == 200
        assert b"stt-console" not in r.data          # aucune trace de la section admin

    def test_anonyme_refuse(self, app):
        c = app.test_client()
        assert c.get("/parametres/admin/overview").status_code == 403
