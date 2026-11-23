# tests/test_161_modules_branches_rares.py
"""
Branches rares de six modules que la suite n'atteignait pas :

  - Code/socle_activites.py   : manques() sans entité / carto vide
  - Code/routes/competences.py: /managers sans rôle « développeur » → []
  - Code/routes/gestion_compte.py : refus JSON (403), rattachement à un rôle
    disparu ignoré, page de repli quand la liste lève, e-mail déjà pris
  - Code/routes/paliers_routes.py : 401 anonyme (première mesure, calendrier),
    détail d'une session hors périmètre (403), calendrier d'un coordinateur
    (toutes les sessions) avec une session annulée hors tuiles
  - Code/routes/import_hub.py : import de comptes qui CRÉE le rôle manquant

Chaque test crée ses propres objets et les nettoie.
"""
import json
import uuid
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

JSON = {"Accept": "application/json"}


def _uniq():
    return uuid.uuid4().hex[:8]


def _user(app, status="user", prefix="t161"):
    from Code.models.models import User
    from Code.extensions import db
    with app.app_context():
        email = f"{prefix}.{_uniq()}@devoptiq.com"
        u = User(first_name="T161", last_name=_uniq(), email=email,
                 password=generate_password_hash("Test1234!"), status=status)
        db.session.add(u)
        db.session.commit()
        return u.id, email


def _supprimer_users(app, *uids):
    from Code.models.models import User, UserRole
    from Code.extensions import db
    with app.app_context():
        UserRole.query.filter(UserRole.user_id.in_(uids)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(uids)).delete(synchronize_session=False)
        db.session.commit()


def _client_de(app, uid, email):
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        s["user_email"] = email
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Socle d'activités
# ─────────────────────────────────────────────────────────────────────────────

class TestSocleSansPerimetre:

    def test_sans_entite_rien_ne_manque(self, app):
        from Code.socle_activites import manques, _perimetre
        with app.app_context():
            assert _perimetre(None) == []
            assert manques(None) == {}

    def test_carto_vide_rien_ne_manque(self, app, ids):
        from Code.models.models import Entity
        from Code.extensions import db
        from Code.socle_activites import manques
        with app.app_context():
            e = Entity(name=f"Vide T161 {_uniq()}", owner_id=ids["user_id"])
            db.session.add(e)
            db.session.commit()
            try:
                assert manques(e) == {}
            finally:
                db.session.delete(e)
                db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Compétences : liste des développeurs
# ─────────────────────────────────────────────────────────────────────────────

class TestManagersSansRole:

    def test_sans_role_developpeur_liste_vide(self, auth_client, monkeypatch):
        import Code.roles_permanents as rp
        monkeypatch.setattr(rp, "role_dev_competences", lambda *a, **k: None)
        r = auth_client.get("/competences/managers")
        assert r.status_code == 200
        assert r.get_json() == []


# ─────────────────────────────────────────────────────────────────────────────
# Gestion des comptes
# ─────────────────────────────────────────────────────────────────────────────

class TestGestionCompteBranches:

    def test_creation_refusee_en_json_403(self, app):
        uid, email = _user(app, status="user")
        try:
            c = _client_de(app, uid, email)
            r = c.post("/comptes/create", data={"first_name": "A"}, headers=JSON)
            assert r.status_code == 403
            assert r.get_json() == {"ok": False, "code": "error_forbidden_create",
                                    "champ": None}
        finally:
            _supprimer_users(app, uid)

    def test_email_deja_pris_designe_le_champ(self, auth_client):
        r = auth_client.post("/comptes/create", headers=JSON, data={
            "first_name": "Dup", "last_name": "Licat",
            "email": "test@devoptiq.com", "password": "UnMotDePasseSolide!42"})
        assert r.status_code == 400
        assert r.get_json() == {"ok": False, "code": "error_email_exists",
                                "champ": "email"}

    def test_rattachement_a_un_role_disparu_ignore(self, app, auth_client):
        from Code.models.models import UserRole
        from Code.extensions import db
        uid, email = _user(app)
        try:
            with app.app_context():
                db.session.add(UserRole(user_id=uid, role_id=99999991))
                db.session.commit()
            r = auth_client.get("/comptes/")
            assert r.status_code == 200
            assert email.encode() in r.data
        finally:
            _supprimer_users(app, uid)

    def test_liste_qui_leve_rend_une_page_vide(self, app, auth_client, monkeypatch):
        import Code.routes.gestion_compte as gc

        def _leve(_statut):
            raise RuntimeError("panne")

        monkeypatch.setattr(gc, "_famille", _leve)
        r = auth_client.get("/comptes/")
        assert r.status_code == 200
        assert b"test@devoptiq.com" not in r.data


# ─────────────────────────────────────────────────────────────────────────────
# Paliers / calendrier
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sessions_eval(app):
    from Code.models.models import SessionEvaluation
    from Code.extensions import db
    crees = []

    def _fab(user_id, statut="prevue", jours=5):
        with app.app_context():
            s = SessionEvaluation(user_id=user_id, statut=statut,
                                  date_prevue=date.today() + timedelta(days=jours))
            db.session.add(s)
            db.session.commit()
            crees.append(s.id)
            return s.id

    yield _fab
    with app.app_context():
        SessionEvaluation.query.filter(SessionEvaluation.id.in_(crees or [-1])).delete(
            synchronize_session=False)
        db.session.commit()


class TestPaliersBranches:

    @pytest.mark.parametrize("methode,url", [
        ("post", "/paliers/premiere"),
        ("get", "/paliers/calendrier"),
    ])
    def test_anonyme_401(self, app, methode, url):
        r = getattr(app.test_client(), methode)(url, json={})
        assert r.status_code == 401
        assert r.get_json()["error"] == "not_logged_in"

    def test_detail_d_une_session_hors_perimetre_403(self, app, sessions_eval):
        bob, _ = _user(app)
        eve, eve_mail = _user(app)
        try:
            sid = sessions_eval(bob)
            r = _client_de(app, eve, eve_mail).get(f"/paliers/session/{sid}/detail")
            assert r.status_code == 403
            assert r.get_json()["error"] == "forbidden"
        finally:
            _supprimer_users(app, bob, eve)

    def test_coordinateur_voit_tout_et_l_annulee_hors_tuiles(self, app, sessions_eval):
        bob, _ = _user(app)
        coord, coord_mail = _user(app, status="coordinateur")
        try:
            annulee = sessions_eval(bob, statut="annulee", jours=0)
            prevue = sessions_eval(bob, statut="prevue", jours=0)
            r = _client_de(app, coord, coord_mail).get("/paliers/calendrier")
            assert r.status_code == 200
            par_id = {s["id"]: s for s in r.get_json()["sessions"]}
            assert annulee in par_id and prevue in par_id
            assert par_id[annulee]["tuiles"] == []
            assert "mois" in par_id[prevue]["tuiles"]
        finally:
            _supprimer_users(app, bob, coord)


# ─────────────────────────────────────────────────────────────────────────────
# Hub d'import : création du rôle manquant
# ─────────────────────────────────────────────────────────────────────────────

class TestImportComptesCreeLeRole:

    def test_le_role_inconnu_est_cree_et_attribue(self, app, auth_client, ids):
        from Code.models.models import Entity, Role, User, UserRole, ImportRecord
        from Code.extensions import db
        tag = _uniq()
        email = f"t161.import.{tag}@x.fr"
        nom_role = f"Magasinier T161 {tag}"
        with app.app_context():
            e = Entity(name=f"Import T161 {tag}", owner_id=ids["user_id"])
            db.session.add(e)
            db.session.commit()
            eid = e.id
        with auth_client.session_transaction() as s:
            s["active_entity_id"] = eid
        try:
            r = auth_client.post("/api/import/importer", data=json.dumps({
                "parts": [{"type": "users", "lignes": [
                    {"prenom": "Paul", "nom": "Neuf", "email": email,
                     "role": nom_role, "_i": 0}]}],
                "cibles": [eid], "options": {"creer_roles": True}}),
                content_type="application/json")
            assert r.status_code == 200, r.data
            res = r.get_json()["resultats"][0]
            assert res["crees"] == 1
            assert res["roles_crees"] == 1
            assert res["roles_attribues"] == 1
            with app.app_context():
                u = User.query.filter_by(email=email).one()
                role = Role.query.filter_by(name=nom_role).one()
                assert UserRole.query.filter_by(user_id=u.id, role_id=role.id).count() == 1
        finally:
            with auth_client.session_transaction() as s:
                s["active_entity_id"] = ids["entity_id"]
            with app.app_context():
                u = User.query.filter_by(email=email).first()
                if u:
                    UserRole.query.filter_by(user_id=u.id).delete()
                    db.session.delete(u)
                Role.query.filter_by(name=nom_role).delete()
                ImportRecord.query.filter_by(entity_id=eid).delete()
                Entity.query.filter_by(id=eid).delete()
                db.session.commit()
