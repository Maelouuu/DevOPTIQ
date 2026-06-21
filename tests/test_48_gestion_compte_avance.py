# tests/test_48_gestion_compte_avance.py
"""
Page : Gestion des Comptes — Avancé (/comptes)
Couvre les lacunes de test_18 :
  - POST /comptes/set_password/<id>      → complètement non testé
  - POST /comptes/create (validations)   → cas limites non couverts
"""
import json
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

pytestmark = pytest.mark.gestion_compte_avance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_role(app, ids, name="Rôle Avancé Test"):
    with app.app_context():
        from Code.models.models import Role
        from Code.extensions import db
        existing = Role.query.filter_by(name=name, entity_id=ids["entity_id"]).first()
        if existing:
            return existing.id
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


def _create_user(app, ids, email, first="Avancé", last="Test"):
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        existing = User.query.filter_by(email=email).first()
        if existing:
            return existing.id
        u = User(
            entity_id=ids["entity_id"],
            first_name=first,
            last_name=last,
            email=email,
            password=generate_password_hash("Pass123!"),
            status="user",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _delete_user(app, user_id):
    with app.app_context():
        from Code.models.models import User, UserRole
        from Code.extensions import db
        UserRole.query.filter_by(user_id=user_id).delete()
        u = User.query.get(user_id)
        if u:
            db.session.delete(u)
        db.session.commit()


def _get_user_password_hash(app, user_id):
    with app.app_context():
        from Code.models.models import User
        u = User.query.get(user_id)
        return u.password if u else None


# ===========================================================================
# 1. POST /comptes/set_password/<id> — changer le mot de passe d'un user
# ===========================================================================

class TestSetPassword:

    def test_set_password_success(self, auth_client, ids, app):
        """POST /comptes/set_password/<id> avec un mot de passe valide → 200, ok=True."""
        uid = _create_user(app, ids, "setpwd.ok@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": "NouveauPass1!"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("ok") is True
        finally:
            _delete_user(app, uid)

    def test_set_password_actually_updates_hash(self, auth_client, ids, app):
        """Après set_password, le nouveau mot de passe est bien hashé en base."""
        uid = _create_user(app, ids, "setpwd.hash@devoptiq.com")
        original_hash = _get_user_password_hash(app, uid)
        try:
            auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": "NouveauPass2!"}),
                content_type="application/json",
            )
            new_hash = _get_user_password_hash(app, uid)
            # Le hash doit avoir changé
            assert new_hash != original_hash
            # Et le nouveau hash doit correspondre au nouveau mot de passe
            assert check_password_hash(new_hash, "NouveauPass2!")
        finally:
            _delete_user(app, uid)

    def test_set_password_too_short_returns_400(self, auth_client, ids, app):
        """Mot de passe < 6 caractères → 400, ok=False."""
        uid = _create_user(app, ids, "setpwd.short@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": "abc"}),
                content_type="application/json",
            )
            assert r.status_code == 400
            data = json.loads(r.data)
            assert data.get("ok") is False
            assert "6" in (data.get("error") or "")
        finally:
            _delete_user(app, uid)

    def test_set_password_exactly_5_chars_returns_400(self, auth_client, ids, app):
        """5 caractères (limite inférieure stricte) → 400."""
        uid = _create_user(app, ids, "setpwd.5chars@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": "abcde"}),
                content_type="application/json",
            )
            assert r.status_code == 400
            data = json.loads(r.data)
            assert data.get("ok") is False
        finally:
            _delete_user(app, uid)

    def test_set_password_exactly_6_chars_succeeds(self, auth_client, ids, app):
        """6 caractères (limite basse acceptable) → 200, ok=True."""
        uid = _create_user(app, ids, "setpwd.6chars@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": "abcdef"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data.get("ok") is True
        finally:
            _delete_user(app, uid)

    def test_set_password_empty_string_returns_400(self, auth_client, ids, app):
        """Mot de passe vide → 400, ok=False."""
        uid = _create_user(app, ids, "setpwd.empty@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
            data = json.loads(r.data)
            assert data.get("ok") is False
        finally:
            _delete_user(app, uid)

    def test_set_password_missing_field_returns_400(self, auth_client, ids, app):
        """Payload JSON sans le champ 'password' → 400."""
        uid = _create_user(app, ids, "setpwd.missing@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({}),
                content_type="application/json",
            )
            assert r.status_code == 400
            data = json.loads(r.data)
            assert data.get("ok") is False
        finally:
            _delete_user(app, uid)

    def test_set_password_user_not_found_returns_404(self, auth_client):
        """set_password sur un ID inexistant → 404."""
        r = auth_client.post(
            "/comptes/set_password/999999",
            data=json.dumps({"password": "NouveauPass!"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_set_password_no_body_returns_400(self, auth_client, ids, app):
        """POST sans corps JSON → 400 (password vide après strip)."""
        uid = _create_user(app, ids, "setpwd.nobody@devoptiq.com")
        try:
            r = auth_client.post(f"/comptes/set_password/{uid}")
            assert r.status_code == 400
            data = json.loads(r.data)
            assert data.get("ok") is False
        finally:
            _delete_user(app, uid)

    def test_set_password_whitespace_only_returns_400(self, auth_client, ids, app):
        """Mot de passe composé uniquement d'espaces → 400 (stripped = '')."""
        uid = _create_user(app, ids, "setpwd.spaces@devoptiq.com")
        try:
            r = auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": "      "}),
                content_type="application/json",
            )
            assert r.status_code == 400
            data = json.loads(r.data)
            assert data.get("ok") is False
        finally:
            _delete_user(app, uid)

    def test_set_password_does_not_change_on_failure(self, auth_client, ids, app):
        """En cas d'échec (mot de passe trop court), le hash en base ne change pas."""
        uid = _create_user(app, ids, "setpwd.nochange@devoptiq.com")
        original_hash = _get_user_password_hash(app, uid)
        try:
            auth_client.post(
                f"/comptes/set_password/{uid}",
                data=json.dumps({"password": "ab"}),
                content_type="application/json",
            )
            new_hash = _get_user_password_hash(app, uid)
            assert new_hash == original_hash
        finally:
            _delete_user(app, uid)


# ===========================================================================
# 2. POST /comptes/create — validations non couvertes par test_18
# ===========================================================================

class TestCreateUserValidation:

    def test_create_missing_first_name_redirects_with_error(self, auth_client, ids, app):
        """Sans first_name → redirect avec msg=error_missing_name."""
        role_id = _create_role(app, ids, name="Rôle Validation Missing Name")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "",
                    "last_name": "Test",
                    "email": "missing.fname@devoptiq.com",
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
            assert b"error_missing_name" in r.data or "error_missing_name" in r.headers.get("Location", "")
        finally:
            _delete_role(app, role_id)

    def test_create_missing_last_name_redirects_with_error(self, auth_client, ids, app):
        """Sans last_name → redirect avec msg=error_missing_name."""
        role_id = _create_role(app, ids, name="Rôle Validation Missing LName")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Prénom",
                    "last_name": "",
                    "email": "missing.lname@devoptiq.com",
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
            assert b"error_missing_name" in r.data or "error_missing_name" in r.headers.get("Location", "")
        finally:
            _delete_role(app, role_id)

    def test_create_missing_email_redirects_with_error(self, auth_client, ids, app):
        """Sans email → redirect avec msg=error_missing_email."""
        role_id = _create_role(app, ids, name="Rôle Validation Missing Email")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Prénom",
                    "last_name": "Nom",
                    "email": "",
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
            assert b"error_missing_email" in r.data or "error_missing_email" in r.headers.get("Location", "")
        finally:
            _delete_role(app, role_id)

    def test_create_password_too_short_redirects_with_error(self, auth_client, ids, app):
        """Mot de passe < 6 caractères → redirect avec msg=error_missing_password."""
        role_id = _create_role(app, ids, name="Rôle Validation Short Pwd")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Prénom",
                    "last_name": "Nom",
                    "email": "short.pwd@devoptiq.com",
                    "password": "abc",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
            assert b"error_missing_password" in r.data or "error_missing_password" in r.headers.get("Location", "")
        finally:
            _delete_role(app, role_id)

    def test_create_empty_password_redirects_with_error(self, auth_client, ids, app):
        """Mot de passe vide → redirect avec msg=error_missing_password."""
        role_id = _create_role(app, ids, name="Rôle Validation Empty Pwd")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Prénom",
                    "last_name": "Nom",
                    "email": "empty.pwd@devoptiq.com",
                    "password": "",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
            assert b"error_missing_password" in r.data or "error_missing_password" in r.headers.get("Location", "")
        finally:
            _delete_role(app, role_id)

    def test_create_missing_role_id_redirects_with_error(self, auth_client):
        """Sans role_id → redirect avec msg=error_missing_role."""
        r = auth_client.post(
            "/comptes/create",
            data={
                "first_name": "Prénom",
                "last_name": "Nom",
                "email": "missing.role@devoptiq.com",
                "password": "Pass123!",
                "role_id": "",
                "status": "user",
            },
        )
        assert r.status_code == 302
        assert b"error_missing_role" in r.data or "error_missing_role" in r.headers.get("Location", "")

    def test_create_invalid_role_id_redirects_with_error(self, auth_client):
        """role_id non-numérique → redirect avec msg=error_missing_role."""
        r = auth_client.post(
            "/comptes/create",
            data={
                "first_name": "Prénom",
                "last_name": "Nom",
                "email": "invalid.role@devoptiq.com",
                "password": "Pass123!",
                "role_id": "abc",
                "status": "user",
            },
        )
        assert r.status_code == 302
        assert b"error_missing_role" in r.data or "error_missing_role" in r.headers.get("Location", "")

    def test_create_duplicate_email_redirects_with_error(self, auth_client, ids):
        """Email déjà utilisé → redirect avec msg=error_email_exists."""
        r = auth_client.post(
            "/comptes/create",
            data={
                "first_name": "Prénom",
                "last_name": "Nom",
                "email": "test@devoptiq.com",  # email du seed
                "password": "Pass123!",
                "role_id": "1",
                "status": "user",
            },
        )
        assert r.status_code == 302
        assert b"error_email_exists" in r.data or "error_email_exists" in r.headers.get("Location", "")

    def test_create_user_not_created_on_validation_failure(self, auth_client, ids, app):
        """Sur un échec de validation (email manquant), aucun utilisateur n'est créé."""
        role_id = _create_role(app, ids, name="Rôle No Create Check")
        email_to_check = "should.not.exist@devoptiq.com"
        try:
            auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Prénom",
                    "last_name": "Nom",
                    "email": "",  # manquant
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            with app.app_context():
                from Code.models.models import User
                u = User.query.filter_by(email=email_to_check).first()
                assert u is None
        finally:
            _delete_role(app, role_id)

    def test_create_success_msg_in_redirect(self, auth_client, ids, app):
        """Un create valide redirige avec msg=created."""
        role_id = _create_role(app, ids, name="Rôle Msg Created")
        try:
            r = auth_client.post(
                "/comptes/create",
                data={
                    "first_name": "Msg",
                    "last_name": "Created",
                    "email": "msg.created.check@devoptiq.com",
                    "password": "Pass123!",
                    "role_id": str(role_id),
                    "status": "user",
                },
            )
            assert r.status_code == 302
            location = r.headers.get("Location", "")
            assert "created" in location
        finally:
            with app.app_context():
                from Code.models.models import User, UserRole
                from Code.extensions import db
                u = User.query.filter_by(email="msg.created.check@devoptiq.com").first()
                if u:
                    UserRole.query.filter_by(user_id=u.id).delete()
                    db.session.delete(u)
                    db.session.commit()
            _delete_role(app, role_id)
