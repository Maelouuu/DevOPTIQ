# tests/test_136_rh_dev_scope_gaps.py
"""
Page : Gestion RH — erreurs de `/role_cartos`, `/role_dev` et `/dev_scope`
(rôle/compte/développeur introuvable, auto-suivi, accès refusé).

Données jetables (entité + comptes + rôle) nettoyées après chaque test :
la base est partagée (scope=session).
"""
import pytest

from Code.extensions import db
from Code.models.models import Entity, Role, User, UserRole

pytestmark = pytest.mark.gestion_rh

INEXISTANT = 987654


@pytest.fixture
def decor(app, auth_client):
    with app.app_context():
        ent = Entity(name="Entité 136 RH")
        db.session.add(ent)
        db.session.flush()
        role = Role(name="Rôle 136", entity_id=ent.id)
        dev = User(email="dev136@example.com", first_name="Dev", last_name="Cent",
                   entity_id=ent.id, password="x")
        collab = User(email="collab136@example.com", first_name="Col", last_name="Lab",
                      entity_id=ent.id, password="x")
        db.session.add_all([role, dev, collab])
        db.session.flush()
        db.session.add(UserRole(user_id=collab.id, role_id=role.id))
        db.session.commit()
        d = {"ent": ent.id, "role": role.id, "dev": dev.id, "collab": collab.id}
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
        ids_u = [d["dev"], d["collab"]]
        UserRole.query.filter(UserRole.user_id.in_(ids_u)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(ids_u)).update({"manager_id": None}, synchronize_session=False)
        db.session.commit()
        User.query.filter(User.id.in_(ids_u)).delete(synchronize_session=False)
        Role.query.filter_by(entity_id=d["ent"]).delete()
        Entity.query.filter_by(id=d["ent"]).delete()
        db.session.commit()


class TestRoleCartos:
    def test_get_role_inconnu_renvoie_404(self, auth_client, decor):
        r = auth_client.get(f"/gestion_rh/role_cartos/{INEXISTANT}")
        assert r.status_code == 404
        assert r.get_json()["error"] == "Rôle introuvable"

    def test_post_role_inconnu_renvoie_404(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/role_cartos",
                             json={"role_id": INEXISTANT, "entity_ids": []})
        assert r.status_code == 404
        assert r.get_json()["error"] == "Rôle introuvable"

    def test_post_sans_role_id_renvoie_404(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/role_cartos", json={"entity_ids": []})
        assert r.status_code == 404

    def test_anonyme_refuse(self, client, decor):
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get(f"/gestion_rh/role_cartos/{decor['role']}")
        assert r.status_code in (302, 401, 403)


class TestRoleDev:
    def test_compte_ne_tenant_pas_le_role_renvoie_404(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/role_dev",
                             json={"user_id": decor["dev"], "role_id": decor["role"],
                                   "dev_id": None})
        assert r.status_code == 404
        assert "ne tient pas ce rôle" in r.get_json()["error"]

    def test_developpeur_introuvable_renvoie_404(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/role_dev",
                             json={"user_id": decor["collab"], "role_id": decor["role"],
                                   "dev_id": INEXISTANT})
        assert r.status_code == 404
        assert r.get_json()["error"] == "Développeur introuvable"

    def test_auto_suivi_refuse(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/role_dev",
                             json={"user_id": decor["collab"], "role_id": decor["role"],
                                   "dev_id": decor["collab"]})
        assert r.status_code == 400

    def test_pose_puis_retire_le_developpeur(self, app, auth_client, decor):
        r = auth_client.post("/gestion_rh/role_dev",
                             json={"user_id": decor["collab"], "role_id": decor["role"],
                                   "dev_id": decor["dev"]})
        assert r.status_code == 200
        with app.app_context():
            lien = UserRole.query.filter_by(user_id=decor["collab"],
                                            role_id=decor["role"]).first()
            assert lien.manager_id == decor["dev"]
        r = auth_client.post("/gestion_rh/role_dev",
                             json={"user_id": decor["collab"], "role_id": decor["role"],
                                   "dev_id": None})
        assert r.status_code == 200
        with app.app_context():
            lien = UserRole.query.filter_by(user_id=decor["collab"],
                                            role_id=decor["role"]).first()
            assert lien.manager_id is None


class TestDevScope:
    def test_utilisateur_introuvable_renvoie_404(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/dev_scope",
                             json={"user_id": INEXISTANT, "dev_id": decor["dev"]})
        assert r.status_code == 404
        assert r.get_json()["error"] == "Utilisateur introuvable"

    def test_sans_user_id_renvoie_404(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/dev_scope", json={"dev_id": decor["dev"]})
        assert r.status_code == 404

    def test_developpeur_introuvable_renvoie_404(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/dev_scope",
                             json={"user_id": decor["collab"], "dev_id": INEXISTANT})
        assert r.status_code == 404
        assert r.get_json()["error"] == "Développeur introuvable"

    def test_auto_suivi_refuse(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/dev_scope",
                             json={"user_id": decor["collab"], "dev_id": decor["collab"]})
        assert r.status_code == 400

    def test_role_non_tenu_renvoie_404_avec_liste(self, auth_client, decor):
        r = auth_client.post("/gestion_rh/dev_scope",
                             json={"user_id": decor["collab"], "dev_id": decor["dev"],
                                   "role_ids": [INEXISTANT]})
        assert r.status_code == 404
        assert r.get_json()["roles"] == [INEXISTANT]

    def test_portee_globale_pose_le_lien_sur_tous_les_roles(self, app, auth_client, decor):
        r = auth_client.post("/gestion_rh/dev_scope",
                             json={"user_id": decor["collab"], "dev_id": decor["dev"]})
        assert r.status_code == 200
        body = r.get_json()
        assert body["dev_id"] == decor["dev"]
        assert body["roles"] == [{"id": decor["role"], "dev_id": decor["dev"]}]

    def test_portee_par_role_dissout_le_lien_global(self, auth_client, decor):
        auth_client.post("/gestion_rh/dev_scope",
                         json={"user_id": decor["collab"], "dev_id": decor["dev"]})
        r = auth_client.post("/gestion_rh/dev_scope",
                             json={"user_id": decor["collab"], "dev_id": decor["dev"],
                                   "role_ids": [decor["role"]]})
        assert r.status_code == 200
        body = r.get_json()
        assert body["dev_id"] is None
        assert body["roles"] == [{"id": decor["role"], "dev_id": decor["dev"]}]

    def test_portee_liste_vide_retire_le_developpeur_des_roles(self, auth_client, decor):
        auth_client.post("/gestion_rh/dev_scope",
                         json={"user_id": decor["collab"], "dev_id": decor["dev"],
                               "role_ids": [decor["role"]]})
        r = auth_client.post("/gestion_rh/dev_scope",
                             json={"user_id": decor["collab"], "dev_id": decor["dev"],
                                   "role_ids": []})
        assert r.status_code == 200
        assert r.get_json()["roles"] == [{"id": decor["role"], "dev_id": None}]
