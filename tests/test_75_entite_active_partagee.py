# tests/test_75_entite_active_partagee.py
"""
Un compte qui ne POSSÈDE aucune carto doit quand même en ouvrir une.

Symptôme rapporté : « j'ai beau rendre active la carto qu'on lui a partagée,
dès que je me déconnecte et me reconnecte, ça me dit que l'entité n'est pas
active ». Déroutant, parce que ça marchait tant que la session vivait.

La page carte a sa PROPRE résolution d'entité (`activities_map.get_active_entity`)
et son repli filtrait sur `owner_id` :

    Entity.query.filter(Entity.is_active == True,
                        or_(Entity.owner_id == user_id, Entity.owner_id == None))

Un compte qui ne possède rien n'avait donc aucun repli, et la page annonçait
« Aucune entité active » alors que la carto commune lui était ouverte.
`Entity.get_active` (models.py) savait déjà retomber sur les cartos communes ;
cette copie ne l'avait pas suivi — deux implémentations de la même règle.
"""
import pytest


@pytest.fixture
def carto_partagee(app):
    """Un propriétaire, une carto commune ouverte à un rôle, et un compte qui
    tient ce rôle sans rien posséder."""
    from Code.extensions import db
    from Code.models.models import Entity, EntityRoleAccess, Role, User, UserRole

    with app.app_context():
        patron = User(first_name="Pro", last_name="Prio75", email="p75@x.tld",
                      password="x", status="champion")
        sans_rien = User(first_name="Noe", last_name="Sans75", email="n75@x.tld",
                         password="x", status="user")
        etranger = User(first_name="Eta", last_name="Nger75", email="e75@x.tld",
                        password="x", status="user")
        db.session.add_all([patron, sans_rien, etranger])
        db.session.commit()

        ent = Entity(name="Commune 75", owner_id=patron.id, is_shared=True)
        db.session.add(ent)
        db.session.commit()

        role = Role(entity_id=ent.id, name="Bande 75")
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=sans_rien.id, role_id=role.id))
        db.session.add(EntityRoleAccess(entity_id=ent.id, role_id=role.id))
        db.session.commit()

        ids = {"patron": patron.id, "sans_rien": sans_rien.id,
               "etranger": etranger.id, "entite": ent.id, "role": role.id}

    yield ids

    with app.app_context():
        EntityRoleAccess.query.filter_by(entity_id=ids["entite"]).delete()
        UserRole.query.filter_by(role_id=ids["role"]).delete()
        Role.query.filter_by(id=ids["role"]).delete()
        Entity.query.filter_by(id=ids["entite"]).delete()
        User.query.filter(User.id.in_(
            [ids["patron"], ids["sans_rien"], ids["etranger"]])).delete()
        db.session.commit()


def _session_neuve(client, user_id, email):
    """Comme une reconnexion : plus aucune entité active en session."""
    with client.session_transaction() as s:
        s.clear()
        s["user_id"] = user_id
        s["user_email"] = email


class TestRepliSurLaCartoCommune:

    def test_la_page_carte_retrouve_la_carto_partagee(self, app, client, carto_partagee):
        """Le cœur du défaut : session vide, aucune entité possédée."""
        from Code.routes.activities_map import get_active_entity

        _session_neuve(client, carto_partagee["sans_rien"], "n75@x.tld")
        with client.application.test_request_context():
            from flask import session as sess
            sess["user_id"] = carto_partagee["sans_rien"]
            entity = get_active_entity()
            assert entity is not None, (
                "un compte sans carto à lui n'avait aucun repli : la page "
                "annonçait « Aucune entité active »")
            assert entity.id == carto_partagee["entite"]
            # Et la session est recalée, pour que la suite du parcours suive.
            assert sess.get("active_entity_id") == carto_partagee["entite"]

    def test_un_compte_sans_droit_n_obtient_rien(self, app, client, carto_partagee):
        """Le repli ne doit pas OUVRIR la carto à qui n'y a pas accès : l'accès
        est restreint à un rôle, et ce compte ne le tient pas."""
        from Code.routes.activities_map import get_active_entity

        with client.application.test_request_context():
            from flask import session as sess
            sess["user_id"] = carto_partagee["etranger"]
            entity = get_active_entity()
            assert entity is None or entity.id != carto_partagee["entite"]

    def test_les_deux_resolutions_disent_la_meme_chose(self, app, carto_partagee):
        """⚠️ La page carte et `Entity.get_active` sont deux implémentations de
        la même règle. Qu'elles divergent est précisément ce qui a produit le
        bug : on le vérifie plutôt que de l'espérer."""
        from Code.models.models import Entity
        from Code.routes.activities_map import get_active_entity

        with app.test_request_context():
            from flask import session as sess
            for uid in (carto_partagee["sans_rien"], carto_partagee["patron"]):
                sess.clear()
                sess["user_id"] = uid
                page = get_active_entity()
                sess.pop("active_entity_id", None)
                modele = Entity.get_active(uid)
                assert (page.id if page else None) == (modele.id if modele else None)


class TestNettoyageInterface:
    """Deux éléments retirés à la demande — les vérifier évite qu'ils
    reviennent par un copier-coller."""

    def test_la_page_partage_a_quitte_la_barre_de_navigation(self, app, client,
                                                             carto_partagee):
        _session_neuve(client, carto_partagee["patron"], "p75@x.tld")
        html = client.get("/gestion_rh/").data.decode("utf-8")
        assert 'href="/share/"' not in html

    def test_le_bouton_importer_une_carto_a_disparu(self, app, client, carto_partagee):
        """L'API d'import reste (provisionnement, tests) ; c'est le bouton de la
        pop-up Gestion des entités qui est retiré."""
        _session_neuve(client, carto_partagee["patron"], "p75@x.tld")
        html = client.get("/activities/map").data.decode("utf-8")
        assert "wizard-import-carto-btn" not in html
        assert "wizard-import-carto-file" not in html
