# tests/test_73_connexion_routes.py
"""
Page : Authentification (Code/routes/connexion_routes.py)

Complète test_01_auth.py sur les comportements non couverts :
  - insensibilité à la casse de l'email au login
  - migration transparente du hash de mot de passe (needs_rehash)
  - langue de session posée selon default_lang_for() à la connexion
  - redirection effective après login réussi / logout
  - contenu JSON précis de /auth/current_user_info (succès, non connecté,
    utilisateur introuvable, avec/sans manager)

Le client/app sont partagés (scope=session) : chaque test qui touche la
session ou crée des comptes utilise un client isolé ou restaure l'état.
"""
import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.auth


def _mk_user(app, email, password="TestPass123!", status="user",
             first_name="T", last_name="User", manager_id=None, lang=None):
    from Code.models.models import User
    from Code.extensions import db
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                first_name=first_name, last_name=last_name, email=email,
                password=generate_password_hash(password), status=status,
                manager_id=manager_id,
            )
            db.session.add(user)
        else:
            user.password = generate_password_hash(password)
            user.status = status
            user.manager_id = manager_id
        if lang is not None:
            user.lang = lang
        db.session.commit()
        return user.id


def _get_password_hash(app, email):
    from Code.models.models import User
    with app.app_context():
        return User.query.filter_by(email=email).first().password


class TestLoginCaseInsensitive:
    """L'email est comparé insensible à la casse (func.lower)."""

    def test_login_email_majuscules_reussit(self, app):
        _mk_user(app, "case.test@devoptiq.com", "SecretPass1!")
        isolated = app.test_client()
        r = isolated.post(
            "/login",
            data={"email": "CASE.TEST@DEVOPTIQ.COM", "password": "SecretPass1!"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" not in r.headers["Location"]

    def test_login_email_avec_espaces_est_strippe(self, app):
        _mk_user(app, "spaced.test@devoptiq.com", "SecretPass1!")
        isolated = app.test_client()
        r = isolated.post(
            "/login",
            data={"email": "  spaced.test@devoptiq.com  ", "password": "SecretPass1!"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" not in r.headers["Location"]


class TestLoginRehash:
    """Migration transparente vers le hash standard pbkdf2:sha256:600000."""

    def test_login_reussi_migre_le_hash_legacy(self, app):
        email = "rehash.test@devoptiq.com"
        _mk_user(app, email, "MigratePass1!")
        before = _get_password_hash(app, email)
        assert not before.startswith("pbkdf2:sha256:600000$")

        isolated = app.test_client()
        r = isolated.post(
            "/login",
            data={"email": email, "password": "MigratePass1!"},
            follow_redirects=False,
        )
        assert r.status_code == 302

        after = _get_password_hash(app, email)
        assert after.startswith("pbkdf2:sha256:600000$")

    def test_reconnexion_apres_migration_fonctionne_toujours(self, app):
        email = "rehash.twice@devoptiq.com"
        _mk_user(app, email, "MigratePass2!")
        isolated = app.test_client()
        isolated.post("/login", data={"email": email, "password": "MigratePass2!"})

        isolated2 = app.test_client()
        r = isolated2.post(
            "/login",
            data={"email": email, "password": "MigratePass2!"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" not in r.headers["Location"]


class TestLoginRedirectAndLang:

    def test_login_reussi_redirige_vers_la_carte_des_activites(self, app):
        email = "redirect.test@devoptiq.com"
        _mk_user(app, email, "RedirectPass1!")
        isolated = app.test_client()
        r = isolated.post(
            "/login",
            data={"email": email, "password": "RedirectPass1!"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/activities/map") or "map" in r.headers["Location"]

    def test_compte_standard_recoit_la_langue_anglaise(self, app):
        email = "lang.standard@devoptiq.com"
        _mk_user(app, email, "LangPass1!")
        isolated = app.test_client()
        isolated.post("/login", data={"email": email, "password": "LangPass1!"})
        with isolated.session_transaction() as sess:
            assert sess["lang"] == "en"

    def test_compte_francophone_deja_en_base_est_respecte_au_login(self, app):
        """`default_lang_for()` fixe la langue à la CRÉATION du compte
        (gestion_compte.py) ; la colonne `lang` étant NOT NULL avec un
        défaut, le repli `getattr(user, 'lang', None) or default_lang_for(...)`
        du login ne fait que respecter la valeur déjà posée en base — vérifié
        ici pour le compte francophone par défaut."""
        email = "afdec.enterprise.services@gmail.com"
        _mk_user(app, email, "LangPassFR1!", lang="fr")
        isolated = app.test_client()
        isolated.post("/login", data={"email": email, "password": "LangPassFR1!"})
        with isolated.session_transaction() as sess:
            assert sess["lang"] == "fr"


class TestLoginFailures:

    def test_login_email_vide(self, client):
        r = client.post(
            "/login", data={"email": "", "password": "whatever"},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_login_mot_de_passe_vide(self, client):
        r = client.post(
            "/login", data={"email": "test@devoptiq.com", "password": ""},
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]


class TestLogout:

    def test_logout_vide_la_session_et_redirige_vers_login(self, app):
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
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

        with isolated.session_transaction() as sess:
            assert "user_id" not in sess
            assert "user_email" not in sess
            assert "active_entity_id" not in sess

    def test_logout_reinitialise_la_langue_par_defaut(self, app):
        isolated = app.test_client()
        with isolated.session_transaction() as sess:
            sess["lang"] = "fr"
        isolated.get("/logout", follow_redirects=False)
        with isolated.session_transaction() as sess:
            assert sess["lang"] == "en"


class TestCurrentUserInfo:

    def test_non_connecte_renvoie_403(self, app):
        isolated = app.test_client()
        r = isolated.get("/auth/current_user_info")
        assert r.status_code == 403
        assert r.get_json()["error"]

    def test_utilisateur_introuvable_renvoie_404(self, app):
        isolated = app.test_client()
        with isolated.session_transaction() as sess:
            sess["user_email"] = "ghost.nobody@devoptiq.com"
        r = isolated.get("/auth/current_user_info")
        assert r.status_code == 404
        assert r.get_json()["error"]

    def test_utilisateur_connu_sans_manager(self, app):
        email = "info.solo@devoptiq.com"
        _mk_user(app, email, first_name="Solo", last_name="Nomanager")
        isolated = app.test_client()
        with isolated.session_transaction() as sess:
            sess["user_email"] = email

        r = isolated.get("/auth/current_user_info")
        assert r.status_code == 200
        body = r.get_json()
        assert body["first_name"] == "Solo"
        assert body["last_name"] == "Nomanager"
        assert body["manager_id"] is None
        assert body["manager_first_name"] == ""
        assert body["manager_last_name"] == ""
        assert body["roles"] == []

    def test_utilisateur_connu_avec_manager_et_roles(self, app):
        from Code.models.models import Role, UserRole
        from Code.extensions import db

        manager_id = _mk_user(app, "info.manager@devoptiq.com",
                               first_name="Chief", last_name="Boss")
        user_id = _mk_user(app, "info.subordinate@devoptiq.com",
                            first_name="Junior", last_name="Staff",
                            manager_id=manager_id)

        with app.app_context():
            role = Role.query.filter_by(name="Rôle Info Test").first()
            if role is None:
                role = Role(name="Rôle Info Test")
                db.session.add(role)
                db.session.flush()
            if not UserRole.query.filter_by(user_id=user_id, role_id=role.id).first():
                db.session.add(UserRole(user_id=user_id, role_id=role.id))
            db.session.commit()

        isolated = app.test_client()
        with isolated.session_transaction() as sess:
            sess["user_email"] = "info.subordinate@devoptiq.com"

        r = isolated.get("/auth/current_user_info")
        assert r.status_code == 200
        body = r.get_json()
        assert body["id"] == user_id
        assert body["manager_id"] == manager_id
        assert body["manager_first_name"] == "Chief"
        assert body["manager_last_name"] == "Boss"
        assert "Rôle Info Test" in body["roles"]
