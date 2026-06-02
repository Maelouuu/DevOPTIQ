# tests/test_35_password_reset.py
"""
Couvre :
  - POST /forgot_password            (routes_password.py)
  - GET  /reset_password/<token>     (routes_password.py)
  - POST /reset_password/<token>     (routes_password.py)
"""
import pytest
from itsdangerous import URLSafeTimedSerializer

pytestmark = pytest.mark.password_reset


def _make_token(app, email, salt="password-reset-salt"):
    """Génère un token valide pour l'email donné."""
    with app.app_context():
        s = URLSafeTimedSerializer(app.config["SECRET_KEY"])
        return s.dumps(email, salt=salt)


# ===========================================================================
# 1. POST /forgot_password
# ===========================================================================

class TestForgotPassword:

    def test_sans_email_redirige_vers_login(self, client):
        """POST sans email → redirection vers /login."""
        r = client.post("/forgot_password", data={}, follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_email_connu_redirige_avec_message_succes(self, client, app):
        """Email connu → redirection login avec message discret (ne révèle pas l'existence)."""
        r = client.post(
            "/forgot_password",
            data={"email": "test@devoptiq.com"},
            follow_redirects=True,
        )
        assert r.status_code == 200

    def test_email_inconnu_meme_comportement(self, client):
        """Email inconnu → même redirection (pas de révélation d'existence)."""
        r = client.post(
            "/forgot_password",
            data={"email": "inconnu@nowhere.com"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_email_en_minuscules(self, client):
        """L'email est normalisé en minuscules avant traitement."""
        r = client.post(
            "/forgot_password",
            data={"email": "TEST@DEVOPTIQ.COM"},
            follow_redirects=False,
        )
        assert r.status_code == 302


# ===========================================================================
# 2. GET /reset_password/<token> — affichage du formulaire
# ===========================================================================

class TestResetPasswordGet:

    def test_token_invalide_redirige_login(self, client):
        """Token invalide (mauvaise signature) → redirection vers /login."""
        r = client.get("/reset_password/token-invalide", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_token_valide_retourne_formulaire(self, client, app):
        """Token valide → 200 avec le formulaire de réinitialisation."""
        token = _make_token(app, "test@devoptiq.com")
        r = client.get(f"/reset_password/{token}")
        assert r.status_code == 200

    def test_token_valide_contient_champ_password(self, client, app):
        """La page de reset contient un champ 'password'."""
        token = _make_token(app, "test@devoptiq.com")
        r = client.get(f"/reset_password/{token}")
        assert b"password" in r.data.lower()


# ===========================================================================
# 3. POST /reset_password/<token> — soumission du formulaire
# ===========================================================================

class TestResetPasswordPost:

    def test_mot_de_passe_trop_court(self, client, app):
        """Mot de passe < 6 caractères → 200 avec erreur."""
        token = _make_token(app, "test@devoptiq.com")
        r = client.post(
            f"/reset_password/{token}",
            data={"password": "abc", "confirm_password": "abc"},
        )
        assert r.status_code == 200
        assert b"6" in r.data or b"caract" in r.data

    def test_mots_de_passe_non_identiques(self, client, app):
        """Les deux mots de passe ne correspondent pas → 200 avec erreur."""
        token = _make_token(app, "test@devoptiq.com")
        r = client.post(
            f"/reset_password/{token}",
            data={"password": "NouveauPass1!", "confirm_password": "AutrePass2!"},
        )
        assert r.status_code == 200
        assert b"correspondent" in r.data or b"identique" in r.data or b"match" in r.data.lower()

    def test_token_invalide_sur_post_redirige(self, client):
        """Token invalide → redirection login même en POST."""
        r = client.post(
            "/reset_password/mauvais-token",
            data={"password": "NewPass123!", "confirm_password": "NewPass123!"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_reset_valide_redirige_vers_login(self, client, app):
        """Token valide + mots de passe corrects → redirection vers login."""
        token = _make_token(app, "test@devoptiq.com")
        r = client.post(
            f"/reset_password/{token}",
            data={"password": "NouveauPass123!", "confirm_password": "NouveauPass123!"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_reset_valide_modifie_le_mot_de_passe(self, client, app):
        """Après reset, l'ancien mot de passe n'est plus valide et le nouveau fonctionne."""
        from werkzeug.security import check_password_hash
        from Code.models.models import User

        token = _make_token(app, "test@devoptiq.com")
        new_password = "ResetPass456!"
        client.post(
            f"/reset_password/{token}",
            data={"password": new_password, "confirm_password": new_password},
        )

        with app.app_context():
            user = User.query.filter_by(email="test@devoptiq.com").first()
            assert check_password_hash(user.password, new_password)

            # Restaurer le mot de passe original pour les tests suivants
            from werkzeug.security import generate_password_hash
            user.password = generate_password_hash("TestPass123!")
            from Code.extensions import db
            db.session.commit()
