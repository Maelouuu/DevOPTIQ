# tests/test_116_gestion_compte_gaps.py
"""
Page : Gestion des comptes (/comptes) — branches d'erreur
Couvre : âge invalide (création/mise à jour), rôle inconnu, e-mail déjà pris à la
         mise à jour, mot de passe trop court, set_password, réponses JSON.
"""
import uuid

import pytest

pytestmark = pytest.mark.gestion_compte

JSON = {"Accept": "application/json"}


def _email():
    return f"gap-{uuid.uuid4().hex[:8]}@devoptiq.test"


def _mk_user(app, ids, email=None):
    from Code.models.models import User
    from Code.extensions import db
    from werkzeug.security import generate_password_hash
    with app.app_context():
        u = User(first_name="Gap", last_name="Test", email=email or _email(),
                 password=generate_password_hash("secret1"), status="user",
                 entity_id=ids["entity_id"])
        db.session.add(u)
        db.session.commit()
        return u.id


def _rm_user(app, uid):
    from Code.models.models import User, UserRole
    from Code.extensions import db
    with app.app_context():
        UserRole.query.filter_by(user_id=uid).delete()
        u = db.session.get(User, uid)
        if u:
            db.session.delete(u)
        db.session.commit()


def _exists(app, email):
    from Code.models.models import User
    with app.app_context():
        return User.query.filter_by(email=email).first() is not None


class TestCreateErreurs:
    def test_create_age_invalide_json_champ_age(self, app, auth_client):
        email = _email()
        r = auth_client.post("/comptes/create", headers=JSON, data={
            "first_name": "A", "last_name": "B", "email": email,
            "password": "Secret123", "age": "abc"})
        assert r.status_code == 400
        body = r.get_json()
        assert body["code"] == "error_invalid_age"
        assert body["champ"] == "age"
        assert not _exists(app, email)

    def test_create_role_inconnu_ne_cree_rien(self, app, auth_client):
        email = _email()
        r = auth_client.post("/comptes/create", headers=JSON, data={
            "first_name": "A", "last_name": "B", "email": email,
            "password": "Secret123", "roles_ajout": ["99999999"]})
        assert r.status_code == 400
        assert r.get_json()["code"] == "error_role_unknown"
        assert not _exists(app, email)

    def test_create_ids_de_roles_non_numeriques_ignores(self, app, auth_client):
        email = _email()
        r = auth_client.post("/comptes/create", headers=JSON, data={
            "first_name": "A", "last_name": "B", "email": email,
            "password": "Secret123", "roles_ajout": ["x", ""]})
        try:
            assert r.status_code == 200
            assert r.get_json()["ok"] is True
        finally:
            from Code.models.models import User
            with app.app_context():
                u = User.query.filter_by(email=email).first()
                uid = u.id if u else None
            if uid:
                _rm_user(app, uid)

    def test_create_sans_json_redirige_avec_message(self, auth_client):
        r = auth_client.post("/comptes/create", data={
            "first_name": "", "last_name": "B", "email": _email(),
            "password": "Secret123"})
        assert r.status_code == 302
        assert "error_missing_name" in r.headers["Location"]


class TestUpdateErreurs:
    def test_update_age_invalide(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            r = auth_client.post(f"/comptes/update/{uid}", headers=JSON, data={
                "first_name": "G", "last_name": "T", "email": _email(),
                "age": "vingt"})
            assert r.status_code == 400
            assert r.get_json()["code"] == "error_invalid_age"
        finally:
            _rm_user(app, uid)

    def test_update_email_deja_pris(self, app, auth_client, ids):
        a, b = _mk_user(app, ids), _mk_user(app, ids)
        try:
            from Code.models.models import User
            with app.app_context():
                pris = User.query.get(b).email
            r = auth_client.post(f"/comptes/update/{a}", headers=JSON, data={
                "first_name": "G", "last_name": "T", "email": pris})
            assert r.status_code == 400
            assert r.get_json()["code"] == "error_email_exists"
        finally:
            _rm_user(app, a)
            _rm_user(app, b)

    def test_update_mot_de_passe_trop_court(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            from Code.models.models import User
            with app.app_context():
                email = User.query.get(uid).email
            r = auth_client.post(f"/comptes/update/{uid}", headers=JSON, data={
                "first_name": "G", "last_name": "T", "email": email,
                "password": "123"})
            assert r.status_code == 400
            assert r.get_json()["code"] == "error_missing_password"
        finally:
            _rm_user(app, uid)

    def test_update_retrait_role_inconnu(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            from Code.models.models import User
            with app.app_context():
                email = User.query.get(uid).email
            r = auth_client.post(f"/comptes/update/{uid}", headers=JSON, data={
                "first_name": "G", "last_name": "T", "email": email,
                "roles_retrait": ["99999999"]})
            assert r.status_code == 400
            assert r.get_json()["code"] == "error_role_unknown"
        finally:
            _rm_user(app, uid)

    def test_update_nom_vide_json_champ_first_name(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            r = auth_client.post(f"/comptes/update/{uid}", headers=JSON, data={
                "first_name": "", "last_name": "T", "email": _email()})
            assert r.status_code == 400
            assert r.get_json()["champ"] == "first_name"
        finally:
            _rm_user(app, uid)


class TestSetPassword:
    def test_set_password_trop_court(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            r = auth_client.post(f"/comptes/set_password/{uid}", json={"password": "abc"})
            assert r.status_code == 400
            assert r.get_json()["ok"] is False
        finally:
            _rm_user(app, uid)

    def test_set_password_ok_et_persiste(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            r = auth_client.post(f"/comptes/set_password/{uid}", json={"password": "nouveau123"})
            assert r.status_code == 200
            assert r.get_json() == {"ok": True}
            from Code.models.models import User
            from Code.security import verify_password
            with app.app_context():
                assert verify_password(User.query.get(uid).password, "nouveau123")
        finally:
            _rm_user(app, uid)

    def test_set_password_sans_corps(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            r = auth_client.post(f"/comptes/set_password/{uid}")
            assert r.status_code == 400
        finally:
            _rm_user(app, uid)

    def test_set_password_anonyme_refuse(self, app, client, ids):
        uid = _mk_user(app, ids)
        try:
            with client.session_transaction() as s:
                s.clear()
            r = client.post(f"/comptes/set_password/{uid}", json={"password": "nouveau123"})
            assert r.status_code in (302, 401, 403)
        finally:
            _rm_user(app, uid)
