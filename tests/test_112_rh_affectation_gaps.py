# tests/test_112_rh_affectation_gaps.py
"""
Gestion RH : routes d'affectation en lot et listes de rôles restées sans test
(`/gestion_rh/assign_manager`, `/gestion_rh/roles`, `/gestion_rh/users_by_roles`).

Chaque test crée ses propres comptes jetables et les supprime : la base est
partagée par toute la suite.
"""
import pytest

pytestmark = pytest.mark.gestion_rh


@pytest.fixture
def duo(app):
    """Un développeur et un collaborateur dotés d'un rôle jetable."""
    from Code.extensions import db
    from Code.models.models import Role, User, UserRole
    from Code.security import hash_password

    with app.app_context():
        dev = User(first_name="T112", last_name="Dev", email="t112.dev@devoptiq.com",
                   password=hash_password("Motdepasse123!"), status="user")
        collab = User(first_name="T112", last_name="Collab", email="t112.collab@devoptiq.com",
                      password=hash_password("Motdepasse123!"), status="user")
        role = Role(name="T112 Rôle")
        db.session.add_all([dev, collab, role])
        db.session.commit()
        db.session.add(UserRole(user_id=collab.id, role_id=role.id))
        db.session.commit()
        ids = {"dev": dev.id, "collab": collab.id, "role": role.id}

    yield ids

    with app.app_context():
        UserRole.query.filter_by(role_id=ids["role"]).delete()
        Role.query.filter_by(id=ids["role"]).delete()
        User.query.filter(User.id.in_([ids["dev"], ids["collab"]])).delete(synchronize_session=False)
        db.session.commit()


class TestAssignManagerEnLot:
    def test_manager_manquant_renvoie_400(self, auth_client, duo):
        r = auth_client.post("/gestion_rh/assign_manager", json={
            "assignments": [{"user_id": duo["collab"], "role_id": duo["role"]}]})
        assert r.status_code == 400
        assert r.get_json()["error"] == "Paramètres manquants"

    def test_liste_vide_renvoie_400(self, auth_client, duo):
        r = auth_client.post("/gestion_rh/assign_manager", json={
            "manager_id": duo["dev"], "assignments": []})
        assert r.status_code == 400

    def test_affecte_le_manager_a_chaque_collaborateur(self, app, auth_client, duo):
        from Code.models.models import User
        r = auth_client.post("/gestion_rh/assign_manager", json={
            "manager_id": duo["dev"],
            "assignments": [{"user_id": duo["collab"], "role_id": duo["role"]}]})
        assert r.status_code == 200
        assert r.get_json() == {"success": True}
        with app.app_context():
            assert User.query.get(duo["collab"]).manager_id == duo["dev"]

    def test_utilisateur_inconnu_ignore_sans_erreur(self, app, auth_client, duo):
        from Code.models.models import User
        r = auth_client.post("/gestion_rh/assign_manager", json={
            "manager_id": duo["dev"],
            "assignments": [{"user_id": 99999999, "role_id": duo["role"]},
                            {"user_id": duo["collab"], "role_id": duo["role"]}]})
        assert r.status_code == 200
        with app.app_context():
            assert User.query.get(duo["collab"]).manager_id == duo["dev"]


class TestListesDeRoles:
    def test_roles_triés_par_nom(self, auth_client, duo):
        r = auth_client.get("/gestion_rh/roles")
        assert r.status_code == 200
        noms = [x["name"] for x in r.get_json()]
        assert "T112 Rôle" in noms
        assert noms == sorted(noms)

    def test_users_by_roles_regroupe_les_titulaires(self, auth_client, duo):
        r = auth_client.get(f"/gestion_rh/users_by_roles?roles={duo['role']}")
        assert r.status_code == 200
        lignes = r.get_json()
        assert len(lignes) == 1
        assert lignes[0]["id"] == duo["collab"]
        assert lignes[0]["roles"] == ["T112 Rôle"]

    def test_users_by_roles_sans_parametre_est_vide(self, auth_client, duo):
        r = auth_client.get("/gestion_rh/users_by_roles")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_users_by_roles_ignore_les_valeurs_non_numeriques(self, auth_client, duo):
        r = auth_client.get(f"/gestion_rh/users_by_roles?roles=abc,{duo['role']},x")
        assert r.status_code == 200
        assert [u["id"] for u in r.get_json()] == [duo["collab"]]

    def test_users_by_roles_role_inconnu_est_vide(self, auth_client, duo):
        r = auth_client.get("/gestion_rh/users_by_roles?roles=99999999")
        assert r.get_json() == []
