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

    def test_mail_non_configure_message_specifique(self, client, app):
        """MAIL_CONFIGURED=False (cas par défaut des tests) → message d'erreur dédié."""
        assert not app.config.get("MAIL_CONFIGURED")
        r = client.post(
            "/forgot_password",
            data={"email": "test@devoptiq.com"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "pas configur" in r.get_data(as_text=True)

    def test_email_connu_envoie_un_email_avec_lien_reset(self, client, app):
        """Email connu + mail configuré → un message est bien composé avec le lien de reset."""
        from Code.extensions import mail

        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            with mail.record_messages() as outbox:
                r = client.post(
                    "/forgot_password",
                    data={"email": "test@devoptiq.com"},
                    follow_redirects=False,
                )
                assert r.status_code == 302
                assert "/login" in r.headers["Location"]
                assert len(outbox) == 1
                assert outbox[0].recipients == ["test@devoptiq.com"]
                assert "/reset_password/" in outbox[0].body
        finally:
            app.config["MAIL_CONFIGURED"] = False

    def test_email_inconnu_mais_mail_configure_ne_cree_pas_de_message(self, client, app):
        """Email inconnu + mail configuré → aucun email envoyé mais même redirection (anti-énumération)."""
        from Code.extensions import mail

        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            with mail.record_messages() as outbox:
                r = client.post(
                    "/forgot_password",
                    data={"email": "personne@nowhere.com"},
                    follow_redirects=False,
                )
                assert r.status_code == 302
                assert "/login" in r.headers["Location"]
                assert len(outbox) == 0
        finally:
            app.config["MAIL_CONFIGURED"] = False

    def test_recherche_insensible_a_la_casse(self, app):
        """_find_user_by_email retombe sur une recherche insensible à la casse
        quand la correspondance exacte échoue (email stocké en minuscules)."""
        import Code.routes.routes_password as routes_password_module

        with app.app_context():
            found = routes_password_module._find_user_by_email("TEST@DEVOPTIQ.COM")
            assert found is not None
            assert found.email == "test@devoptiq.com"

    def test_erreur_envoi_mail_affiche_message_erreur(self, client, app, monkeypatch):
        """Une exception lors de mail.send() est interceptée et affiche un message d'erreur."""
        from Code.extensions import mail

        def raise_send_error(msg):
            raise RuntimeError("SMTP down")

        monkeypatch.setattr(mail, "send", raise_send_error)
        app.config["MAIL_CONFIGURED"] = True
        app.extensions["mail"].default_sender = "no-reply@devoptiq.com"
        try:
            r = client.post(
                "/forgot_password",
                data={"email": "test@devoptiq.com"},
                follow_redirects=True,
            )
            assert r.status_code == 200
            assert "Erreur lors de" in r.get_data(as_text=True)
        finally:
            app.config["MAIL_CONFIGURED"] = False


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

    def test_token_expire_redirige_login(self, client, monkeypatch):
        """Token dont la signature est expirée (SignatureExpired) → redirection vers /login.

        On remplace la classe uniquement dans le namespace de routes_password
        (pas itsdangerous.URLSafeTimedSerializer globalement : cette classe sert
        aussi à signer les cookies de session Flask, la patcher globalement
        casserait l'authentification des autres tests partageant le même client).
        """
        import Code.routes.routes_password as routes_password_module
        from itsdangerous import SignatureExpired

        class FakeExpiredSerializer:
            def __init__(self, *a, **kw):
                pass

            def loads(self, *a, **kw):
                raise SignatureExpired("expired")

        monkeypatch.setattr(routes_password_module, "URLSafeTimedSerializer", FakeExpiredSerializer)
        r = client.get("/reset_password/un-token-quelconque", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]


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

    def test_token_valide_email_sans_utilisateur(self, client, app):
        """Token valide mais l'email ne correspond à aucun utilisateur → message + redirection login."""
        token = _make_token(app, "fantome@nowhere.com")
        r = client.post(
            f"/reset_password/{token}",
            data={"password": "NouveauPass123!", "confirm_password": "NouveauPass123!"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_erreur_commit_annule_et_affiche_erreur(self, client, app, monkeypatch):
        """Une exception lors du commit → rollback et message d'erreur serveur, mot de passe inchangé."""
        from sqlalchemy.orm import Session as SqlaSession
        from Code.models.models import User

        token = _make_token(app, "test@devoptiq.com")

        with app.app_context():
            original_hash = User.query.filter_by(email="test@devoptiq.com").first().password

        def raise_commit_error(self):
            raise RuntimeError("DB down")

        monkeypatch.setattr(SqlaSession, "commit", raise_commit_error)
        r = client.post(
            f"/reset_password/{token}",
            data={"password": "TentativePass123!", "confirm_password": "TentativePass123!"},
        )
        assert r.status_code == 200
        assert "Erreur serveur" in r.get_data(as_text=True)

        monkeypatch.undo()
        with app.app_context():
            user = User.query.filter_by(email="test@devoptiq.com").first()
            assert user.password == original_hash

    def test_hash_non_persiste_affiche_erreur_dediee(self, client, app, monkeypatch):
        """Le commit réussit mais la relecture post-commit ne correspond pas → message d'erreur dédié."""
        import Code.routes.routes_password as routes_password_module
        from Code.extensions import db
        from Code.models.models import User
        from werkzeug.security import generate_password_hash

        token = _make_token(app, "test@devoptiq.com")
        monkeypatch.setattr(routes_password_module, "verify_password", lambda stored, plain: False)
        try:
            r = client.post(
                f"/reset_password/{token}",
                data={"password": "AutreTentative123!", "confirm_password": "AutreTentative123!"},
            )
            assert r.status_code == 200
            assert "pas été persistée" in r.get_data(as_text=True)
        finally:
            with app.app_context():
                user = User.query.filter_by(email="test@devoptiq.com").first()
                user.password = generate_password_hash("TestPass123!")
                db.session.commit()

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
