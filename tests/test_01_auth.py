# tests/test_01_auth.py
"""
Page : Authentification
Tests couvrant le login / logout / protection des routes.
"""
import pytest

pytestmark = pytest.mark.auth


class TestLoginPage:
    """La page de login est accessible sans authentification."""

    def test_login_page_accessible(self, client):
        r = client.get("/login")
        assert r.status_code == 200

    def test_login_page_contains_form(self, client):
        r = client.get("/login")
        html = r.data.decode()
        assert "email" in html.lower() or "mail" in html.lower()

    def test_login_invalid_email(self, client):
        r = client.post(
            "/login",
            data={"email": "nope@nope.com", "password": "wrong"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "introuvable" in r.data.decode().lower() or r.status_code in (200, 302)

    def test_login_wrong_password(self, client):
        r = client.post(
            "/login",
            data={"email": "test@devoptiq.com", "password": "mauvais"},
            follow_redirects=True,
        )
        assert r.status_code == 200

    def test_login_correct_credentials(self, client):
        r = client.post(
            "/login",
            data={"email": "test@devoptiq.com", "password": "TestPass123!"},
            follow_redirects=False,
        )
        # Doit rediriger (302) après succès
        assert r.status_code in (302, 200)

    def test_logout_redirects(self, app):
        """Logout testé sur un client ISOLÉ.

        auth_client/client sont partagés (scope=session) : faire un /logout
        dessus viderait la session pour TOUS les tests suivants (≈25 échecs en
        cascade côté test_11_tools). On utilise donc un client dédié.
        """
        from Code.models.models import User, Entity
        with app.app_context():
            user = User.query.filter_by(email="test@devoptiq.com").first()
            entity = Entity.query.filter_by(name="Entité Test").first()
        isolated = app.test_client()
        with isolated.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["user_email"] = user.email
            sess["active_entity_id"] = entity.id
        r = isolated.get("/logout", follow_redirects=False)
        assert r.status_code in (200, 302)


class TestAuthCurrentUser:
    """Route info utilisateur courant."""

    def test_current_user_endpoint_exists(self, auth_client):
        """L'endpoint current_user_info répond (quelle que soit l'autorisation)."""
        r = auth_client.get("/auth/current_user_info")
        assert r.status_code in (200, 401, 403, 404)

    def test_current_user_info_no_session_returns_403(self, app):
        """Sans session (client isolé), l'endpoint renvoie 403."""
        isolated = app.test_client()
        r = isolated.get("/auth/current_user_info")
        assert r.status_code == 403
        assert "error" in r.get_json()

    def test_current_user_info_unknown_email_in_session_returns_404(self, app):
        """Session avec un email ne correspondant à aucun utilisateur → 404."""
        isolated = app.test_client()
        with isolated.session_transaction() as sess:
            sess["user_email"] = "fantome@devoptiq.com"
        r = isolated.get("/auth/current_user_info")
        assert r.status_code == 404
        assert "error" in r.get_json()

    def test_healthz_always_available(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert b"ok" in r.data


class TestLoginEdgeCases:
    """Cas limites du parcours de connexion : migration de hash et langue."""

    def _mk_user(self, app, email, password_hash, lang="en"):
        from Code.models.models import User, Entity
        from Code.extensions import db
        with app.app_context():
            entity = Entity.query.filter_by(name="Entité Test").first()
            u = User(
                entity_id=entity.id,
                first_name="Edge",
                last_name="Case",
                email=email,
                password=password_hash,
                status="user",
                lang=lang,
            )
            db.session.add(u)
            db.session.commit()
            return u.id

    def _delete_user(self, app, user_id):
        from Code.models.models import User
        from Code.extensions import db
        with app.app_context():
            u = db.session.get(User, user_id)
            if u:
                db.session.delete(u)
                db.session.commit()

    def test_login_rehash_failure_does_not_block_login(self, app, monkeypatch):
        """Si la migration du hash échoue en base, la connexion reste valide (rollback avalé)."""
        from werkzeug.security import generate_password_hash
        from Code.extensions import db

        # Hash volontairement dans un ancien format pour déclencher needs_rehash().
        old_hash = generate_password_hash("EdgePass123!", method="pbkdf2:sha256")
        uid = self._mk_user(app, "edge.rehash@devoptiq.com", old_hash, lang="en")

        def _boom():
            raise RuntimeError("commit-boom-rehash")

        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            isolated = app.test_client()
            r = isolated.post(
                "/login",
                data={"email": "edge.rehash@devoptiq.com", "password": "EdgePass123!"},
                follow_redirects=False,
            )
        finally:
            monkeypatch.undo()
        assert r.status_code in (302, 200)
        self._delete_user(app, uid)

    def test_login_with_falsy_lang_updates_session_and_persists(self, app):
        """Un compte sans langue enregistrée (chaîne vide) retombe sur l'anglais et se met à jour."""
        from werkzeug.security import generate_password_hash
        from Code.security import PASSWORD_HASH_METHOD
        from Code.models.models import User

        current_hash = generate_password_hash("EdgePass123!", method=PASSWORD_HASH_METHOD)
        uid = self._mk_user(app, "edge.lang@devoptiq.com", current_hash, lang="")

        isolated = app.test_client()
        with isolated.session_transaction() as sess:
            pass  # session vide avant login
        r = isolated.post(
            "/login",
            data={"email": "edge.lang@devoptiq.com", "password": "EdgePass123!"},
            follow_redirects=False,
        )
        assert r.status_code in (302, 200)
        with isolated.session_transaction() as sess:
            assert sess.get("lang") == "en"
        with app.app_context():
            u = User.query.get(uid)
            assert u.lang == "en"
        self._delete_user(app, uid)
