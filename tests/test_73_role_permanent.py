# tests/test_73_role_permanent.py
"""
Le développeur de compétences doit SURVIVRE à la cartographie.

Deux défauts se tenaient la main et rendaient la section « Affectation » de la
page RH muette :

  * elle cherchait un rôle nommé littéralement `manager`
    (`Role.query.filter_by(name='manager')`) — absent, la liste revenait vide
    et la section semblait morte ;
  * et quand on créait ce rôle à la main, `_sync_carto_to_db` l'effaçait au
    premier enregistrement de la carto, puisqu'aucune bande ne portait ce nom.

Aucun test ne pouvait le voir : les deux moitiés vivent dans des fichiers
différents, et chacune prise isolément a l'air correcte.
"""
import json

import pytest


class TestReconnaissanceDuNom:
    """Les bases en service portent « manager ». Le renier ferait perdre leurs
    titulaires et leurs évaluations à la première lecture."""

    @pytest.mark.parametrize("nom", [
        "Développeur de compétences",
        "developpeur de competences",
        "DÉVELOPPEUR DE COMPÉTENCES",
        "manager",
        "Manager",
        "  manager  ",
        "Gestionnaire de compétences",
        "Competency manager",
    ])
    def test_ces_noms_designent_le_meme_role(self, nom):
        from Code.roles_permanents import est_dev_competences
        assert est_dev_competences(nom)

    @pytest.mark.parametrize("nom", ["", None, "Technicien", "Chef de projet",
                                     "manageur du dimanche", "developpeur"])
    def test_ces_noms_ne_le_designent_pas(self, nom):
        from Code.roles_permanents import est_dev_competences
        assert not est_dev_competences(nom)


class TestCreationAutomatique:

    def test_il_est_cree_a_la_demande(self, app):
        from Code.extensions import db
        from Code.models.models import Entity, User
        from Code.roles_permanents import ROLE_DEV_COMPETENCES, role_dev_competences

        with app.app_context():
            u = User(first_name="T", last_name="73a", email="t73a@x.tld",
                     password="x", status="user")
            db.session.add(u)
            db.session.commit()
            e = Entity(name="Entité 73a", owner_id=u.id)
            db.session.add(e)
            db.session.commit()

            # Un seul pour toute l'entreprise : on part d'une base sans lui.
            from Code.models.models import Role
            from Code.roles_permanents import est_dev_competences
            for r in Role.query.all():
                if est_dev_competences(r.name):
                    db.session.delete(r)
            db.session.commit()

            role = role_dev_competences(e.id)
            db.session.commit()
            assert role is not None
            assert role.name == ROLE_DEV_COMPETENCES
            assert role.entity_id == e.id

            # Deux appels ne font pas deux rôles — ni pour une AUTRE carto.
            assert role_dev_competences(e.id).id == role.id
            autre = Entity(name="Entité 73a bis", owner_id=u.id)
            db.session.add(autre)
            db.session.commit()
            assert role_dev_competences(autre.id).id == role.id

    def test_un_manager_existant_est_REPRIS_pas_double(self, app):
        """Créer un doublon à côté d'un `manager` qui a déjà des titulaires
        perdrait ces rattachements sans rien dire."""
        from Code.extensions import db
        from Code.models.models import Entity, Role, User
        from Code.roles_permanents import est_dev_competences, role_dev_competences

        with app.app_context():
            u = User(first_name="T", last_name="73b", email="t73b@x.tld",
                     password="x", status="user")
            db.session.add(u)
            db.session.commit()
            e = Entity(name="Entité 73b", owner_id=u.id)
            db.session.add(e)
            db.session.commit()
            for r in Role.query.all():
                if est_dev_competences(r.name):
                    db.session.delete(r)
            ancien = Role(entity_id=e.id, name="manager")
            db.session.add(ancien)
            db.session.commit()

            trouve = role_dev_competences(e.id)
            assert trouve.id == ancien.id
            assert sum(1 for r in Role.query.all() if est_dev_competences(r.name)) == 1


    def test_quand_les_deux_coexistent_c_est_celui_qui_a_des_titulaires(self, app):
        """Défaut trouvé par la suite complète : la création automatique pose le
        nom canonique À CÔTÉ d'un vieux « manager ». Préférer le canonique
        d'office renvoyait une liste VIDE en laissant croire que personne n'est
        développeur de compétences, alors que les rattachements sont là."""
        from Code.extensions import db
        from Code.models.models import Entity, Role, User, UserRole
        from Code.roles_permanents import ROLE_DEV_COMPETENCES, role_dev_competences

        with app.app_context():
            u = User(first_name="T", last_name="73e", email="t73e@x.tld",
                     password="x", status="user")
            db.session.add(u)
            db.session.commit()
            e = Entity(name="Entité 73e", owner_id=u.id)
            db.session.add(e)
            db.session.commit()

            from Code.roles_permanents import est_dev_competences
            for r in Role.query.all():
                if est_dev_competences(r.name):
                    db.session.delete(r)
            ancien = Role(entity_id=e.id, name="manager")
            neuf = Role(entity_id=e.id, name=ROLE_DEV_COMPETENCES)
            db.session.add_all([ancien, neuf])
            db.session.commit()
            db.session.add(UserRole(user_id=u.id, role_id=ancien.id))
            db.session.commit()

            assert role_dev_competences(e.id).id == ancien.id, (
                "c'est le rôle qui porte les titulaires qui doit répondre")

            # Sans titulaire nulle part, le nom canonique l'emporte.
            UserRole.query.filter_by(role_id=ancien.id).delete()
            db.session.commit()
            assert role_dev_competences(e.id).id == neuf.id


class TestSurvieALaSynchroCarto:
    """Le cœur du défaut : la carto fait foi pour les rôles métier, mais pas
    pour celui-ci."""

    def test_il_survit_a_un_enregistrement_de_carto_qui_l_ignore(self, app):
        from Code.extensions import db
        from Code.models.models import Entity, Role, User
        from Code.roles_permanents import role_dev_competences
        from Code.routes.cartography_editor import _sync_carto_to_db

        with app.app_context():
            u = User(first_name="T", last_name="73c", email="t73c@x.tld",
                     password="x", status="user")
            db.session.add(u)
            db.session.commit()
            e = Entity(name="Entité 73c", owner_id=u.id)
            db.session.add(e)
            db.session.commit()

            permanent = role_dev_competences(e.id)
            metier = Role(entity_id=e.id, name="Bande métier 73c")
            db.session.add(metier)
            db.session.commit()
            id_permanent, id_metier = permanent.id, metier.id

            # Une carto dont AUCUNE bande ne porte ces noms.
            diagram = {"bands": [{"id": 1, "label": "Autre bande", "height": 200}],
                       "shapes": [], "connections": [], "bandWidth": 900}
            e.optiqcarto_data = json.dumps(diagram)
            _sync_carto_to_db(e, diagram)
            db.session.commit()

            assert db.session.get(Role, id_permanent) is not None, (
                "le développeur de compétences a été effacé par la synchro : "
                "la section Affectation redeviendrait muette")
            assert db.session.get(Role, id_metier) is None, (
                "un rôle métier absent de la carte doit, lui, disparaître — "
                "sinon la carte ne fait plus foi")


class TestEndpointRH:

    def test_la_liste_des_developpeurs_ne_depend_plus_du_nom_manager(self, app, client):
        """L'appel historique `?role=manager` doit continuer de fonctionner ET
        cesser de renvoyer une liste vide quand le rôle n'existe pas encore."""
        from Code.extensions import db
        from Code.models.models import Entity, User

        with app.app_context():
            u = User(first_name="T", last_name="73d", email="t73d@x.tld",
                     password="x", status="administrateur")
            db.session.add(u)
            db.session.commit()
            e = Entity(name="Entité 73d", owner_id=u.id, is_active=True)
            db.session.add(e)
            db.session.commit()
            uid, eid = u.id, e.id

        with client.session_transaction() as s:
            s["user_id"] = uid
            s["user_email"] = "t73d@x.tld"
            s["active_entity_id"] = eid

        r = client.get("/gestion_rh/users_with_role?role=manager")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

        with app.app_context():
            from Code.roles_permanents import role_dev_competences
            assert role_dev_competences(eid, creer=False) is not None, (
                "l'appel aurait dû créer le rôle permanent au passage")
