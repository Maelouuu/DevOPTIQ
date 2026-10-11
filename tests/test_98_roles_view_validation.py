# tests/test_98_roles_view_validation.py
"""
Routes : /roles_view — niveau de validation (tables optionnelles) et
résilience de la page quand le calcul de couleur d'un titulaire échoue.

Chaque test crée ses propres tables/lignes jetables et les supprime en fin de
test : la base est partagée (scope=session), rien ne doit fuir.
"""
import contextlib

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.roles_view

URL = "/roles_view/validation_level/{uid}/{rid}"


@contextlib.contextmanager
def _table(app, name, ddl, rows=()):
    """Crée la table `name`, y insère `rows` (liste de dicts), la supprime à la sortie."""
    from Code.extensions import db
    with app.app_context():
        db.session.execute(text(f"DROP TABLE IF EXISTS {name}"))
        db.session.execute(text(ddl))
        for row in rows:
            cols = ", ".join(row)
            params = ", ".join(f":{c}" for c in row)
            db.session.execute(text(f"INSERT INTO {name} ({cols}) VALUES ({params})"), row)
        db.session.commit()
    try:
        yield
    finally:
        with app.app_context():
            db.session.execute(text(f"DROP TABLE IF EXISTS {name}"))
            db.session.commit()


class TestValidationLevel:

    def test_sans_table_de_validation_renvoie_null(self, auth_client):
        r = auth_client.get(URL.format(uid=987001, rid=987002))
        assert r.status_code == 200
        assert r.get_json() == {"level": None}

    def test_table_user_role_validations_renvoie_le_niveau(self, app, auth_client):
        ddl = ("CREATE TABLE user_role_validations "
               "(user_id INTEGER, role_id INTEGER, level INTEGER)")
        with _table(app, "user_role_validations", ddl,
                    [{"user_id": 987011, "role_id": 987012, "level": 3}]):
            r = auth_client.get(URL.format(uid=987011, rid=987012))
        assert r.get_json() == {"level": 3}

    def test_couple_absent_de_la_table_renvoie_null(self, app, auth_client):
        ddl = ("CREATE TABLE user_role_validations "
               "(user_id INTEGER, role_id INTEGER, level INTEGER)")
        with _table(app, "user_role_validations", ddl,
                    [{"user_id": 987021, "role_id": 987022, "level": 2}]):
            r = auth_client.get(URL.format(uid=987021, rid=987099))
        assert r.get_json() == {"level": None}

    def test_table_role_validations_avec_colonnes_alternatives(self, app, auth_client):
        ddl = ("CREATE TABLE role_validations "
               "(users_id INTEGER, role_id INTEGER, validation_level TEXT)")
        with _table(app, "role_validations", ddl,
                    [{"users_id": 987031, "role_id": 987032, "validation_level": "expert"}]):
            r = auth_client.get(URL.format(uid=987031, rid=987032))
        assert r.get_json() == {"level": "expert"}

    def test_table_sans_colonne_de_niveau_renvoie_null(self, app, auth_client):
        ddl = "CREATE TABLE role_validations (user_id INTEGER, role_id INTEGER, note INTEGER)"
        with _table(app, "role_validations", ddl,
                    [{"user_id": 987041, "role_id": 987042, "note": 5}]):
            r = auth_client.get(URL.format(uid=987041, rid=987042))
        assert r.get_json() == {"level": None}

    def test_table_sans_colonne_role_renvoie_null(self, app, auth_client):
        ddl = "CREATE TABLE role_validations (user_id INTEGER, level INTEGER)"
        with _table(app, "role_validations", ddl,
                    [{"user_id": 987051, "level": 4}]):
            r = auth_client.get(URL.format(uid=987051, rid=1))
        assert r.get_json() == {"level": None}

    def test_user_role_validations_prioritaire_sur_role_validations(self, app, auth_client):
        d1 = ("CREATE TABLE user_role_validations "
              "(user_id INTEGER, role_id INTEGER, level INTEGER)")
        d2 = "CREATE TABLE role_validations (user_id INTEGER, role_id INTEGER, level INTEGER)"
        with _table(app, "user_role_validations", d1,
                    [{"user_id": 987061, "role_id": 987062, "level": 1}]), \
             _table(app, "role_validations", d2,
                    [{"user_id": 987061, "role_id": 987062, "level": 9}]):
            r = auth_client.get(URL.format(uid=987061, rid=987062))
        assert r.get_json() == {"level": 1}

    def test_identifiant_non_numerique_renvoie_404(self, auth_client):
        assert auth_client.get("/roles_view/validation_level/abc/1").status_code == 404


class TestPageTitulairesResilience:

    def test_echec_du_calcul_de_couleur_laisse_la_page_en_200(
            self, app, auth_client, ids, monkeypatch):
        from Code.extensions import db
        from Code.models.models import Role, UserRole
        import Code.competency_color as cc

        with app.app_context():
            role = Role(name="Rôle Titulaire Résilience", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.commit()
            rid = role.id
            db.session.add(UserRole(user_id=ids["user_id"], role_id=rid))
            db.session.commit()

        def _boom(*a, **k):
            raise RuntimeError("calcul indisponible")

        monkeypatch.setattr(cc, "user_competency_hex", _boom)
        try:
            r = auth_client.get("/roles_view/")
            assert r.status_code == 200
            assert "Rôle Titulaire Résilience".encode() in r.data
        finally:
            with app.app_context():
                UserRole.query.filter_by(user_id=ids["user_id"], role_id=rid).delete()
                Role.query.filter_by(id=rid).delete()
                db.session.commit()
