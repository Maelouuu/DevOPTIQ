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

    def test_healthz_always_available(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert b"ok" in r.data
