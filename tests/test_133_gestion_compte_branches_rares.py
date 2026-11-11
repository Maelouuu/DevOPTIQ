# tests/test_133_gestion_compte_branches_rares.py
"""
Page : Gestion des comptes (/comptes) — dernières branches d'erreur
Couvre : droits (corps non-dict), e-mail manquant (création/mise à jour),
         échec d'écriture du mot de passe, échec SQL à la mise à jour.
"""
import uuid
from unittest import mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.gestion_compte

JSON = {"Accept": "application/json"}


def _email():
    return f"b133-{uuid.uuid4().hex[:8]}@devoptiq.test"


def _mk_user(app, ids):
    from Code.models.models import User
    from Code.extensions import db
    from werkzeug.security import generate_password_hash
    with app.app_context():
        u = User(first_name="B", last_name="133", email=_email(),
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


class TestDroitsCorpsInvalide:
    def test_droits_corps_liste_refuse_400(self, auth_client):
        r = auth_client.post("/comptes/droits", json={"droits": ["x"]})
        assert r.status_code == 400
        assert r.get_json()["error"] == "Tableau attendu"

    def test_droits_sans_cle_refuse_400(self, auth_client):
        r = auth_client.post("/comptes/droits", json={})
        assert r.status_code == 400


class TestEmailManquant:
    def test_create_sans_email_json(self, auth_client):
        r = auth_client.post("/comptes/create", headers=JSON, data={
            "first_name": "A", "last_name": "B", "email": "  ",
            "password": "Secret123"})
        assert r.status_code == 400
        assert r.get_json()["code"] == "error_missing_email"

    def test_update_sans_email_json(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            r = auth_client.post(f"/comptes/update/{uid}", headers=JSON, data={
                "first_name": "A", "last_name": "B", "email": ""})
            assert r.status_code == 400
            assert r.get_json()["code"] == "error_missing_email"
        finally:
            _rm_user(app, uid)


class TestEchecEcritureMotDePasse:
    def test_set_password_poser_leve_500(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            with mock.patch("Code.routes.gestion_compte.mdp.poser",
                            side_effect=RuntimeError("boom")):
                r = auth_client.post(f"/comptes/set_password/{uid}",
                                     json={"password": "nouveau123"})
            assert r.status_code == 500
            assert r.get_json() == {"ok": False, "error": "boom"}
        finally:
            _rm_user(app, uid)

    def test_set_password_non_enregistre_500(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            with mock.patch("Code.routes.gestion_compte.mdp.poser", return_value=False):
                r = auth_client.post(f"/comptes/set_password/{uid}",
                                     json={"password": "nouveau123"})
            assert r.status_code == 500
            assert r.get_json()["ok"] is False
        finally:
            _rm_user(app, uid)


class TestEchecSqlMiseAJour:
    def test_update_commit_echoue_500(self, app, auth_client, ids):
        uid = _mk_user(app, ids)
        try:
            with mock.patch("Code.routes.gestion_compte.db.session.commit",
                            side_effect=SQLAlchemyError("db down")):
                r = auth_client.post(f"/comptes/update/{uid}", headers=JSON, data={
                    "first_name": "Nouveau", "last_name": "Nom", "email": _email()})
            assert r.status_code == 500
            assert r.get_json()["code"] == "error_update"
        finally:
            _rm_user(app, uid)
