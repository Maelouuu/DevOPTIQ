# tests/test_128_rh_gaps.py
"""
Page : Gestion RH — branches restantes (`users_with_role`, `assign_manager_simple`
par rôle, `/api/competences`, paramètres affichés sur la page d'accueil).

Données jetables (entité + utilisateurs + rôle) nettoyées après chaque test :
la base est partagée (scope=session).
"""
import pytest

from Code.extensions import db
from Code.models.models import Entity, EntrepriseSettings, Role, User, UserRole

pytestmark = pytest.mark.gestion_rh


@pytest.fixture
def decor(app, auth_client):
    with app.app_context():
        ent = Entity(name="Entité 128 RH")
        db.session.add(ent)
        db.session.flush()
        role = Role(name="Rôle 128", entity_id=ent.id)
        chef = User(email="chef128@example.com", first_name="Chef", last_name="Cent",
                    entity_id=ent.id, password="x")
        collab = User(email="collab128@example.com", first_name="Col", last_name="Lab",
                      entity_id=ent.id, password="x")
        db.session.add_all([role, chef, collab])
        db.session.flush()
        db.session.add(UserRole(user_id=collab.id, role_id=role.id))
        db.session.commit()
        d = {"ent": ent.id, "role": role.id, "chef": chef.id, "collab": collab.id}
    with auth_client.session_transaction() as sess:
        ancienne = sess.get("active_entity_id")
        sess["active_entity_id"] = d["ent"]
    yield d
    with auth_client.session_transaction() as sess:
        if ancienne is None:
            sess.pop("active_entity_id", None)
        else:
            sess["active_entity_id"] = ancienne
    with app.app_context():
        ids_u = [d["chef"], d["collab"]]
        UserRole.query.filter(UserRole.user_id.in_(ids_u)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(ids_u)).update({"manager_id": None}, synchronize_session=False)
        db.session.commit()
        User.query.filter(User.id.in_(ids_u)).delete(synchronize_session=False)
        EntrepriseSettings.query.filter_by(entity_id=d["ent"]).delete()
        Role.query.filter_by(entity_id=d["ent"]).delete()
        Entity.query.filter_by(id=d["ent"]).delete()
        db.session.commit()


class TestUsersWithRole:
    def test_role_inconnu_renvoie_liste_vide(self, auth_client, decor):
        r = auth_client.get("/gestion_rh/users_with_role?role=Inexistant128")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_role_existant_liste_ses_titulaires(self, auth_client, decor):
        r = auth_client.get("/gestion_rh/users_with_role?role=Rôle 128")
        assert [u["id"] for u in r.get_json()] == [decor["collab"]]

    def test_role_d_une_autre_entite_n_est_pas_visible(self, app, auth_client, decor):
        with app.app_context():
            autre = Entity(name="Entité 128 bis")
            db.session.add(autre)
            db.session.flush()
            db.session.add(Role(name="Rôle autre 128", entity_id=autre.id))
            db.session.commit()
            aid = autre.id
        try:
            r = auth_client.get("/gestion_rh/users_with_role?role=Rôle autre 128")
            assert r.get_json() == []
        finally:
            with app.app_context():
                Role.query.filter_by(entity_id=aid).delete()
                Entity.query.filter_by(id=aid).delete()
                db.session.commit()

    def test_manager_cree_le_role_permanent_dev_competences(self, app, auth_client, decor):
        r = auth_client.get("/gestion_rh/users_with_role?role=manager")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)
        with app.app_context():
            from Code.roles_permanents import role_dev_competences
            assert role_dev_competences(decor["ent"]) is not None


class TestAssignManagerSimpleParRole:
    def test_par_role_ne_touche_que_les_roles_cites(self, app, auth_client, decor):
        r = auth_client.post("/gestion_rh/assign_manager_simple", json={
            "user_id": decor["collab"], "manager_id": decor["chef"],
            "role_ids": [decor["role"]]})
        assert r.status_code == 200
        with app.app_context():
            ur = UserRole.query.filter_by(user_id=decor["collab"], role_id=decor["role"]).first()
            assert ur.manager_id == decor["chef"]
            assert User.query.get(decor["collab"]).manager_id is None

    def test_par_role_autre_role_laisse_le_manager_intact(self, app, auth_client, decor):
        r = auth_client.post("/gestion_rh/assign_manager_simple", json={
            "user_id": decor["collab"], "manager_id": decor["chef"],
            "role_ids": [99999999]})
        assert r.status_code == 200
        with app.app_context():
            ur = UserRole.query.filter_by(user_id=decor["collab"], role_id=decor["role"]).first()
            assert ur.manager_id is None

    def test_global_pose_aussi_le_manager_sur_les_roles(self, app, auth_client, decor):
        r = auth_client.post("/gestion_rh/assign_manager_simple", json={
            "user_id": decor["collab"], "manager_id": decor["chef"]})
        assert r.status_code == 200
        with app.app_context():
            assert User.query.get(decor["collab"]).manager_id == decor["chef"]
            ur = UserRole.query.filter_by(user_id=decor["collab"], role_id=decor["role"]).first()
            assert ur.manager_id == decor["chef"]


class TestApiCompetencesAcces:
    def test_sans_session_renvoie_401_ou_redirection(self, app):
        c = app.test_client()
        r = c.get("/gestion_rh/api/competences")
        assert r.status_code in (401, 302)

    def test_connecte_admin_renvoie_du_json(self, auth_client, decor):
        r = auth_client.get("/gestion_rh/api/competences")
        assert r.status_code == 200
        assert r.is_json


class TestAccueilParametres:
    def test_accueil_repond_200_avec_parametres_enregistres(self, app, auth_client, decor):
        with app.app_context():
            db.session.add(EntrepriseSettings(entity_id=decor["ent"]))
            db.session.commit()
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200
