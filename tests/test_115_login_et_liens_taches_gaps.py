# tests/test_115_login_et_liens_taches_gaps.py
"""Branches d'échec de /login (rattrapage de la langue) et de ensure_table()."""
import uuid

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture
def compte_sans_langue(app, ids):
    """Compte jetable dont la langue est vide (compte antérieur à la colonne)."""
    from Code.extensions import db
    from Code.models.models import User

    email = f"sanslangue-{uuid.uuid4().hex[:8]}@devoptiq.com"
    with app.app_context():
        u = User(entity_id=ids["entity_id"], first_name="Sans", last_name="Langue",
                 email=email, password=generate_password_hash("TestPass123!"),
                 status="admin")
        db.session.add(u)
        db.session.commit()
        uid = u.id
        db.session.execute(db.text("UPDATE users SET lang = '' WHERE id = :i"), {"i": uid})
        db.session.commit()
    yield email
    with app.app_context():
        User.query.filter_by(id=uid).delete()
        db.session.commit()


class TestLoginLangueRattrapage:

    def test_login_reste_valide_si_la_sauvegarde_de_la_langue_echoue(
            self, app, compte_sans_langue, monkeypatch):
        from Code.extensions import db

        c = app.test_client()
        monkeypatch.setattr(db.session, "commit",
                            lambda: (_ for _ in ()).throw(RuntimeError("commit-boom-lang")))
        r = c.post("/login", data={"email": compte_sans_langue, "password": "TestPass123!"})
        monkeypatch.undo()
        db.session.rollback()

        assert r.status_code == 302
        assert "/login" not in r.headers["Location"]
        with c.session_transaction() as s:
            assert s["user_email"] == compte_sans_langue
            assert s["lang"]

    def test_login_renseigne_la_langue_du_compte_quand_elle_manque(
            self, app, compte_sans_langue):
        from Code.models.models import User

        c = app.test_client()
        r = c.post("/login", data={"email": compte_sans_langue, "password": "TestPass123!"})
        assert r.status_code == 302
        with app.app_context():
            assert User.query.filter_by(email=compte_sans_langue).first().lang


class TestEnsureTableLiens:

    def test_ensure_table_avale_l_erreur_de_creation_sans_memoriser_le_succes(self, app, monkeypatch):
        from Code.routes import task_link_assignments as m
        from Code.models.models import TaskLinkAssignment

        def _boom(*a, **k):
            raise RuntimeError("create-boom")

        monkeypatch.setattr(m, "_table_ensured", False)
        monkeypatch.setattr(TaskLinkAssignment.__table__, "create", _boom, raising=False)
        with app.app_context():
            m.ensure_table()
        assert m._table_ensured is False
