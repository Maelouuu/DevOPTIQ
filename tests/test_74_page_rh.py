# tests/test_74_page_rh.py
"""
La page RH refondue : un seul appel, et il dit la vérité.

Deux défauts la rendaient inutilisable, tous deux invisibles depuis leur propre
fichier :

  * la liste des collaborateurs filtrait sur `User.entity_id` — une colonne que
    la page des Comptes ne remplit JAMAIS. Elle revenait donc vide sur toutes
    les instances, et la page semblait cassée alors que les comptes étaient là ;
  * la section Affectation cherchait un rôle nommé littéralement « manager »
    (voir tests/test_73_role_permanent.py).

La page appelait aussi DIX endpoints qui se recoupaient, dont deux se
contredisaient sur qui est collaborateur. Il n'y en a plus qu'un.
"""
import json

import pytest


@pytest.fixture
def scene(app):
    """Une entité avec sa carto, trois comptes, un rôle permanent, une
    proposition en attente."""
    from Code.extensions import db
    from Code.models.models import CartoChangeRequest, Entity, Role, User, UserRole
    from Code.roles_permanents import role_dev_competences

    with app.app_context():
        champ = User(first_name="Cam", last_name="Fon74", email="c74@x.tld",
                     password="x", status="champion")
        simple = User(first_name="Noe", last_name="Ber74", email="n74@x.tld",
                      password="x", status="user")
        tiers = User(first_name="Sal", last_name="Vas74", email="s74@x.tld",
                     password="x", status="user")
        db.session.add_all([champ, simple, tiers])
        db.session.commit()

        ent = Entity(name="Entité 74", owner_id=champ.id, is_shared=True)
        db.session.add(ent)
        db.session.commit()

        metier = Role(entity_id=ent.id, name="Bande 74")
        db.session.add(metier)
        dev = role_dev_competences(ent.id)
        db.session.commit()
        db.session.add(UserRole(user_id=champ.id, role_id=dev.id))
        db.session.add(CartoChangeRequest(
            entity_id=ent.id, author_id=simple.id, status="pending",
            title="Proposition 74", message="",
            diagram=json.dumps({"shapes": []}), base_diagram=json.dumps({"shapes": []})))
        db.session.commit()

        ids = {"champ": champ.id, "simple": simple.id, "tiers": tiers.id,
               "entite": ent.id, "dev": dev.id, "metier": metier.id}

    yield ids

    with app.app_context():
        CartoChangeRequest.query.filter_by(entity_id=ids["entite"]).delete()
        UserRole.query.filter(UserRole.role_id.in_([ids["dev"], ids["metier"]])).delete()
        Role.query.filter(Role.id.in_([ids["dev"], ids["metier"]])).delete()
        Entity.query.filter_by(id=ids["entite"]).delete()
        User.query.filter(User.id.in_(
            [ids["champ"], ids["simple"], ids["tiers"]])).delete()
        db.session.commit()


def _connecte(client, ids, qui="champ"):
    with client.session_transaction() as s:
        s["user_id"] = ids[qui]
        s["user_email"] = {"champ": "c74@x.tld", "simple": "n74@x.tld",
                           "tiers": "s74@x.tld"}[qui]
        s["active_entity_id"] = ids["entite"]


class TestTableau:

    def test_il_faut_etre_connecte(self, client):
        # ⚠️ Le client de test est partagé par toute la suite : sans ce
        # nettoyage, on hérite de la session d'un voisin et l'appel réussit —
        # le test passerait seul et mentirait dans la suite complète.
        with client.session_transaction() as sess:
            sess.clear()
        assert client.get("/gestion_rh/api/tableau").status_code == 401

    def test_tous_les_comptes_sont_des_collaborateurs(self, client, scene):
        """⚠️ Le cœur du défaut : la liste filtrait sur `User.entity_id`, jamais
        renseignée — elle revenait donc VIDE partout."""
        from Code.extensions import db
        from Code.models.models import User

        _connecte(client, scene)
        d = client.get("/gestion_rh/api/tableau").get_json()

        emails = {p["email"] for p in d["personnes"]}
        assert {"c74@x.tld", "n74@x.tld", "s74@x.tld"} <= emails
        # Aucun de ces comptes n'a d'entity_id : c'est justement le piège.
        with client.application.app_context():
            for e in ("c74@x.tld", "n74@x.tld", "s74@x.tld"):
                assert User.query.filter_by(email=e).first().entity_id is None

    def test_le_role_permanent_est_signale_comme_tel(self, client, scene):
        """L'interface doit dire qu'il ne se supprime pas, au lieu de proposer
        une corbeille qui échouera."""
        _connecte(client, scene)
        d = client.get("/gestion_rh/api/tableau").get_json()

        permanents = [r for r in d["roles"] if r["permanent"]]
        assert len(permanents) == 1
        assert permanents[0]["id"] == scene["dev"]
        assert permanents[0]["titulaires"] == [scene["champ"]]
        metier = next(r for r in d["roles"] if r["id"] == scene["metier"])
        assert metier["permanent"] is False

    def test_les_propositions_en_attente_sont_la(self, client, scene):
        _connecte(client, scene)
        d = client.get("/gestion_rh/api/tableau").get_json()
        assert len(d["propositions"]) == 1
        assert d["propositions"][0]["titre"] == "Proposition 74"
        assert "Noe" in d["propositions"][0]["auteur"]

    def test_un_titulaire_du_role_permanent_peut_affecter(self, client, scene):
        _connecte(client, scene, "champ")
        d = client.get("/gestion_rh/api/tableau").get_json()
        assert d["moi"]["est_dev"] is True
        assert d["droits"]["affecte"] is True

    def test_un_compte_ordinaire_ne_regle_pas_l_acces(self, client, scene):
        """Le masquage n'est pas une sécurité, mais l'écran doit tout de même
        dire la vérité sur ce qu'on peut y faire."""
        _connecte(client, scene, "tiers")
        d = client.get("/gestion_rh/api/tableau").get_json()
        assert d["droits"]["gere_acces"] is False
        assert d["droits"]["affecte"] is False

    def test_l_entite_demandee_est_celle_qu_on_obtient(self, client, scene):
        _connecte(client, scene)
        d = client.get(
            f"/gestion_rh/api/tableau?entity_id={scene['entite']}").get_json()
        assert d["entite"]["id"] == scene["entite"]
        assert d["entite"]["is_shared"] is True

    def test_aucun_role_coche_veut_dire_ouverte_a_tous(self, client, scene):
        """Un « ∞ » ne dit pas combien de personnes sont concernées ; la page
        annonce « ouverte à tous » en s'appuyant sur ce champ."""
        _connecte(client, scene)
        d = client.get("/gestion_rh/api/tableau").get_json()
        assert d["entite"]["open_to_all"] is True
        assert all(r["ouvre_carto"] is False for r in d["roles"])


class TestPageRendue:

    def test_la_page_charge_et_porte_ses_trois_blocs(self, client, scene):
        _connecte(client, scene)
        r = client.get("/gestion_rh/")
        assert r.status_code == 200
        html = r.data.decode("utf-8")
        for bloc in ("bloc-personnes", "bloc-roles", "bloc-propositions"):
            assert f'id="{bloc}"' in html
        assert "grh-topbar" in html

    def test_le_fichier_dcp_a_quitte_la_page_rh(self, client, scene):
        """Un référentiel de compétences est un RÉGLAGE, pas une donnée RH."""
        _connecte(client, scene)
        html = client.get("/gestion_rh/").data.decode("utf-8")
        assert "dcp" not in html.lower()
        assert "openRefFileModal" not in html

class TestLienAvecLaPageCompetences:
    """⚠️ Le MÊME piège que la liste des collaborateurs de la page RH, dans un
    autre fichier : `User.query.filter_by(manager_id=…, entity_id=…)`.

    `users.entity_id` n'est renseigné NULLE PART — la page des Comptes ne
    l'écrit pas. Avec une entité active, aucun compte ne correspondait : on
    désignait quelqu'un comme développeur de compétences dans la page RH, et la
    page Compétences répondait « Aucun collaborateur ». Deux écrans, une seule
    règle, deux implémentations.
    """

    def test_le_collaborateur_affecte_apparait_dans_competences(self, client, scene):
        from Code.extensions import db
        from Code.models.models import User

        _connecte(client, scene)

        # On affecte, exactement comme le fait la page RH.
        r = client.post("/gestion_rh/assign_manager_simple", json={
            "user_id": scene["simple"], "manager_id": scene["champ"], "role_ids": None})
        assert r.status_code == 200 and r.get_json()["success"] is True

        # Aucun de ces comptes n'a d'entity_id : c'est justement le piège.
        with client.application.app_context():
            assert db.session.get(User, scene["simple"]).entity_id is None

        r = client.get(f"/competences/collaborators/{scene['champ']}")
        assert r.status_code == 200
        ids = [c["id"] for c in r.get_json()]
        assert scene["simple"] in ids, (
            "le collaborateur affecté dans la page RH doit apparaître dans la "
            "page Compétences")

    def test_l_affectation_par_role_compte_aussi(self, client, scene):
        """Deux rattachements coexistent : `users.manager_id` (global) et
        `user_roles.manager_id` (par rôle). En ignorer un ferait disparaître des
        collaborateurs selon la façon dont ils ont été affectés."""
        from Code.extensions import db
        from Code.models.models import UserRole

        _connecte(client, scene)
        with client.application.app_context():
            ur = UserRole(user_id=scene["tiers"], role_id=scene["metier"],
                          manager_id=scene["champ"])
            db.session.add(ur)
            db.session.commit()
        try:
            r = client.get(f"/competences/collaborators/{scene['champ']}")
            ids = [c["id"] for c in r.get_json()]
            assert scene["tiers"] in ids
        finally:
            with client.application.app_context():
                UserRole.query.filter_by(user_id=scene["tiers"],
                                         role_id=scene["metier"]).delete()
                db.session.commit()

    def test_la_liste_des_developpeurs_n_est_plus_vide(self, client, scene):
        """`/competences/managers` filtrait AUSSI sur `User.entity_id`."""
        from Code.extensions import db
        from Code.models.models import UserRole

        _connecte(client, scene)
        r = client.get("/competences/managers")
        assert r.status_code == 200
        ids = [m["id"] for m in r.get_json()]
        assert scene["champ"] in ids, (
            "le titulaire du rôle permanent doit figurer parmi les "
            "développeurs de compétences")
