# -*- coding: utf-8 -*-
"""Page : Gestion RH (/gestion_rh) — couverture résiduelle de gestion_rh.py.

Ce que la suite ne touchait pas encore :
  * les replis défensifs de la page d'accueil (table de paramètres, rôle
    permanent, lecture des paramètres, erreur de rendu) ;
  * l'import CSV de rôles avec doublon (contrainte unique entité/nom) ;
  * l'échec d'écriture d'un paramètre isolé (500 honnête, pas de faux succès) ;
  * les listes sans entité active (`/users_with_role`, `/all_collaborators_with_manager`) ;
  * un collaborateur de l'entité qui TIENT des rôles dans la liste des affectations ;
  * le retrait par rôle (manager nul) qui ne touche pas aux autres rôles ;
  * le repli de `/api/tableau` sur la première entité ouvrable ;
  * la dissolution du lien global qui ne réécrit pas un lien de rôle déjà posé.

Chaque test crée ses comptes/rôles jetables et les supprime en sortant.
"""
import io
import json
import uuid

import pytest

from Code.extensions import db

pytestmark = pytest.mark.gestion_rh


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def decor(app, auth_client, ids):
    """Deux rôles et deux comptes (un collaborateur, un développeur) rattachés
    à l'entité du seed, entité forcée active."""
    from Code.models.models import Role, User, UserRole
    from Code.security import hash_password
    tag = _uid()
    with auth_client.session_transaction() as sess:
        avant = sess.get("active_entity_id")
        sess["active_entity_id"] = ids["entity_id"]
    with app.app_context():
        r1 = Role(entity_id=ids["entity_id"], name=f"T151 Qualité {tag}")
        r2 = Role(entity_id=ids["entity_id"], name=f"T151 Logistique {tag}")
        collab = User(first_name="T151", last_name=f"Collab{tag}",
                      email=f"t151.collab.{tag}@devoptiq.com", entity_id=ids["entity_id"],
                      password=hash_password("Motdepasse123!"), status="user")
        dev = User(first_name="T151", last_name=f"Dev{tag}",
                   email=f"t151.dev.{tag}@devoptiq.com", entity_id=ids["entity_id"],
                   password=hash_password("Motdepasse123!"), status="user")
        db.session.add_all([r1, r2, collab, dev])
        db.session.flush()
        db.session.add_all([UserRole(user_id=collab.id, role_id=r1.id),
                            UserRole(user_id=collab.id, role_id=r2.id)])
        db.session.commit()
        d = {"r1": r1.id, "r2": r2.id, "collab": collab.id, "dev": dev.id,
             "r1_name": r1.name}
    yield d
    with app.app_context():
        db.session.rollback()
        UserRole.query.filter(UserRole.user_id.in_([d["collab"], d["dev"]])).delete(
            synchronize_session=False)
        User.query.filter(User.id.in_([d["collab"], d["dev"]])).update(
            {"manager_id": None}, synchronize_session=False)
        User.query.filter(User.id.in_([d["collab"], d["dev"]])).delete(
            synchronize_session=False)
        Role.query.filter(Role.id.in_([d["r1"], d["r2"]])).delete(synchronize_session=False)
        db.session.commit()
    with auth_client.session_transaction() as sess:
        sess["active_entity_id"] = avant if avant is not None else ids["entity_id"]


@pytest.fixture()
def sans_entite_active(auth_client, ids):
    with auth_client.session_transaction() as sess:
        avant = sess.pop("active_entity_id", None)
    yield
    with auth_client.session_transaction() as sess:
        sess["active_entity_id"] = avant if avant is not None else ids["entity_id"]


# ── Page d'accueil : les replis défensifs ──────────────────────────────────

class TestAccueilReplis:

    def test_creation_de_table_qui_echoue_n_empeche_pas_la_page(self, auth_client, monkeypatch):
        from Code.models.models import EntrepriseSettings

        def _refus(*a, **k):
            raise RuntimeError("droits insuffisants sur le schéma")

        monkeypatch.setattr(EntrepriseSettings.__table__, "create", _refus)
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200

    def test_role_permanent_non_cree_n_empeche_pas_la_page(self, auth_client, monkeypatch):
        import Code.roles_permanents as rp

        def _refus(*a, **k):
            raise RuntimeError("rôle permanent impossible")

        monkeypatch.setattr(rp, "assurer_roles_permanents", _refus)
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200

    def test_parametres_illisibles_page_rendue_sans_parametres(self, auth_client, monkeypatch):
        from Code.routes import gestion_rh

        def _refus(*a, **k):
            raise RuntimeError("entreprise_settings illisible")

        monkeypatch.setattr(gestion_rh, "_get_settings_row", _refus)
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200

    def test_erreur_de_rendu_rend_500_avec_le_message(self, auth_client, monkeypatch):
        from Code.routes import gestion_rh

        def _refus(*a, **k):
            raise RuntimeError("gabarit cassé T151")

        monkeypatch.setattr(gestion_rh, "render_template", _refus)
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 500
        assert b"gabarit cass" in r.data

    def test_sans_entite_active_la_page_liste_tous_les_comptes(self, auth_client, sans_entite_active):
        r = auth_client.get("/gestion_rh/")
        assert r.status_code == 200


# ── Paramètres : échec d'écriture ──────────────────────────────────────────

class TestParametreIsoleEchec:

    def test_echec_d_ecriture_rend_500_et_success_faux(self, auth_client, monkeypatch):
        from Code.routes import gestion_rh

        def _refus(*a, **k):
            raise RuntimeError("base en lecture seule")

        monkeypatch.setattr(gestion_rh, "_get_settings_row", _refus)
        cle = gestion_rh.SETTING_KEYS[0]
        r = auth_client.post("/gestion_rh/update_single_setting",
                             data={"key": cle, "value": "7"})
        assert r.status_code == 500
        j = r.get_json()
        assert j["success"] is False
        assert "lecture seule" in j["error"]


# ── Import CSV de rôles : doublons ─────────────────────────────────────────

class TestImportRolesDoublons:

    def test_doublon_ignore_et_les_suivants_importes(self, app, auth_client, ids):
        from Code.models.models import Role
        tag = _uid()
        a, b = f"T151 Import A {tag}", f"T151 Import B {tag}"
        with auth_client.session_transaction() as sess:
            sess["active_entity_id"] = ids["entity_id"]
        contenu = f"{a}\n{a}\n\n  \n{b}\n".encode("utf-8")
        try:
            r = auth_client.post("/gestion_rh/import_roles",
                                 data={"role_file": (io.BytesIO(contenu), f"t151_{tag}.csv")},
                                 content_type="multipart/form-data")
            assert r.status_code == 302
            with app.app_context():
                assert Role.query.filter_by(name=a, entity_id=ids["entity_id"]).count() == 1
                assert Role.query.filter_by(name=b, entity_id=ids["entity_id"]).count() == 1
        finally:
            import os
            from Code.routes.gestion_rh import UPLOAD_FOLDER
            depose = os.path.join(UPLOAD_FOLDER, f"t151_{tag}.csv")
            if os.path.exists(depose):
                os.remove(depose)
            with app.app_context():
                Role.query.filter(Role.name.in_([a, b])).delete(synchronize_session=False)
                db.session.commit()

    def test_fichier_non_csv_n_importe_rien(self, app, auth_client):
        from Code.models.models import Role
        nom = f"T151 Pas CSV {_uid()}"
        r = auth_client.post("/gestion_rh/import_roles",
                             data={"role_file": (io.BytesIO(nom.encode()), "roles.txt")},
                             content_type="multipart/form-data")
        assert r.status_code == 302
        with app.app_context():
            assert Role.query.filter_by(name=nom).count() == 0


# ── Listes sans entité active ──────────────────────────────────────────────

class TestListesSansEntiteActive:

    def test_users_with_role_cherche_le_role_dans_toute_la_base(self, auth_client, decor,
                                                               sans_entite_active):
        r = auth_client.get("/gestion_rh/users_with_role", query_string={"role": decor["r1_name"]})
        assert r.status_code == 200
        assert decor["collab"] in [u["id"] for u in r.get_json()]

    def test_users_with_role_inconnu_liste_vide(self, auth_client, sans_entite_active):
        r = auth_client.get("/gestion_rh/users_with_role",
                            query_string={"role": f"T151 inexistant {_uid()}"})
        assert r.get_json() == []

    def test_all_collaborators_sans_entite_liste_tous_les_comptes(self, auth_client, decor,
                                                                 sans_entite_active):
        r = auth_client.get("/gestion_rh/all_collaborators_with_manager")
        assert r.status_code == 200
        ids_vus = [u["id"] for u in r.get_json()["users"]]
        assert decor["collab"] in ids_vus and decor["dev"] in ids_vus


# ── Liste des affectations : un collaborateur qui tient des rôles ──────────

class TestCollaborateursAvecRoles:

    def test_les_roles_tenus_sont_listes_avec_leur_developpeur(self, app, auth_client, decor):
        from Code.models.models import UserRole
        with app.app_context():
            UserRole.query.filter_by(user_id=decor["collab"], role_id=decor["r1"]).update(
                {"manager_id": decor["dev"]})
            db.session.commit()
        r = auth_client.get("/gestion_rh/all_collaborators_with_manager")
        assert r.status_code == 200
        moi = next(u for u in r.get_json()["users"] if u["id"] == decor["collab"])
        roles = {x["id"]: x for x in moi["roles"]}
        assert set(roles) == {decor["r1"], decor["r2"]}
        assert roles[decor["r1"]]["manager_id"] == decor["dev"]
        assert roles[decor["r2"]]["manager_id"] is None
        assert "comp_color" in roles[decor["r1"]]


# ── Retrait par rôle ───────────────────────────────────────────────────────

class TestRetraitParRole:

    def test_retirer_sur_un_role_laisse_l_autre_intact(self, app, auth_client, decor):
        from Code.models.models import UserRole
        with app.app_context():
            UserRole.query.filter_by(user_id=decor["collab"]).update({"manager_id": decor["dev"]})
            db.session.commit()
        r = auth_client.post("/gestion_rh/assign_manager_simple",
                             data=json.dumps({"user_id": decor["collab"], "manager_id": None,
                                              "role_ids": [decor["r1"]]}),
                             content_type="application/json")
        assert r.status_code == 200
        with app.app_context():
            liens = {ur.role_id: ur.manager_id
                     for ur in UserRole.query.filter_by(user_id=decor["collab"]).all()}
        assert liens == {decor["r1"]: None, decor["r2"]: decor["dev"]}


# ── /api/tableau : repli sur la première entité ouvrable ───────────────────

class TestTableauRepliEntite:

    def test_entite_active_hors_perimetre_retombe_sur_la_premiere_ouvrable(self, auth_client):
        with auth_client.session_transaction() as sess:
            avant = sess.get("active_entity_id")
            sess["active_entity_id"] = 99999999
        try:
            r = auth_client.get("/gestion_rh/api/tableau")
            assert r.status_code == 200
            j = r.get_json()
            assert j["entite"] is not None
            assert j["entite"]["id"] == j["entites"][0]["id"]
            with auth_client.session_transaction() as sess:
                assert sess["active_entity_id"] == j["entite"]["id"]
        finally:
            with auth_client.session_transaction() as sess:
                sess["active_entity_id"] = avant

    def test_role_permanent_en_echec_n_empeche_pas_le_tableau(self, auth_client, monkeypatch):
        import Code.roles_permanents as rp

        def _refus(*a, **k):
            raise RuntimeError("rôle permanent impossible")

        monkeypatch.setattr(rp, "assurer_roles_permanents", _refus)
        r = auth_client.get("/gestion_rh/api/tableau")
        assert r.status_code == 200
        assert "personnes" in r.get_json()

    def test_calendrier_illisible_rend_un_calendrier_vide(self, auth_client, monkeypatch):
        from Code.routes import gestion_rh

        def _refus(*a, **k):
            raise RuntimeError("entreprise_settings illisible")

        monkeypatch.setattr(gestion_rh, "_get_settings_row", _refus)
        r = auth_client.get("/gestion_rh/api/tableau")
        assert r.status_code == 200
        assert r.get_json()["calendrier"] == {}


# ── Dissolution du lien global ─────────────────────────────────────────────

class TestDissolutionLienGlobal:

    def test_un_lien_de_role_deja_pose_n_est_pas_ecrase(self, app, auth_client, decor):
        """Le développeur global est reporté sur les rôles SANS développeur ;
        un rôle qui a déjà le sien le garde."""
        from Code.models.models import User, UserRole
        from Code.security import hash_password
        with app.app_context():
            autre = User(first_name="T151", last_name="Autre", password=hash_password("x"),
                         email=f"t151.autre.{_uid()}@devoptiq.com", status="user")
            db.session.add(autre)
            db.session.flush()
            autre_id = autre.id
            db.session.get(User, decor["collab"]).manager_id = decor["dev"]
            UserRole.query.filter_by(user_id=decor["collab"], role_id=decor["r2"]).update(
                {"manager_id": autre_id})
            db.session.commit()
        try:
            r = auth_client.post("/gestion_rh/role_dev",
                                 data=json.dumps({"user_id": decor["collab"],
                                                  "role_id": decor["r1"], "dev_id": None}),
                                 content_type="application/json")
            assert r.status_code == 200, r.data
            with app.app_context():
                db.session.expire_all()
                assert db.session.get(User, decor["collab"]).manager_id is None
                liens = {ur.role_id: ur.manager_id
                         for ur in UserRole.query.filter_by(user_id=decor["collab"]).all()}
            assert liens == {decor["r1"]: None, decor["r2"]: autre_id}
        finally:
            with app.app_context():
                UserRole.query.filter_by(manager_id=autre_id).update({"manager_id": None})
                User.query.filter_by(id=autre_id).delete()
                db.session.commit()

    def test_fonction_sans_lien_global_ne_fait_rien(self, app):
        from Code.models.models import User
        from Code.routes.gestion_rh import _dissoudre_lien_global
        with app.app_context():
            assert _dissoudre_lien_global(None) is False
            assert _dissoudre_lien_global(User(first_name="x", last_name="y",
                                               email="x@y", password="z")) is False


# ── Accès : un compte sans le droit RH ─────────────────────────────────────

class TestAccesSansDroitRh:

    def test_compte_user_renvoye_a_l_accueil(self, app, decor):
        """Un compte `user` connecté n'ouvre pas la page RH : renvoi vers
        l'accueil (et non vers /login, qui signalerait une session refusée)."""
        from Code import mot_de_passe as mdp
        from Code.models.models import User
        with app.app_context():
            empreinte = mdp.empreinte_session(db.session.get(User, decor["collab"]))
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = decor["collab"]
            sess["pwd_at"] = empreinte
        r = c.get("/gestion_rh/")
        assert r.status_code == 302
        assert r.headers["Location"] in ("/", "http://localhost/")
