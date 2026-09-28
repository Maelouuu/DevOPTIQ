# tests/test_87_fiche_compte.py
"""
La fiche d'un compte (page Comptes) : ce que le serveur garantit.

⚠️ Le défaut de fond : la fiche ne portait qu'UN rôle, choisi parmi ceux de la
carto ACTIVE, et `update_user` remplaçait « le » rôle de la personne
(`UserRole…first()`). Pour quelqu'un qui tenait un rôle sur une autre carto,
corriger son nom envoyait un rôle vide — et ce rôle était SUPPRIMÉ, avec
l'accès à la carto qu'il ouvrait. Les rôles bougent désormais PAR PAIRE
(`roles_ajout` / `roles_retrait`), et seulement ceux que la fiche nomme.

La fiche envoie aussi en arrière-plan : une erreur revient en JSON, avec le
champ en cause, pour s'afficher sous lui sans perdre la saisie.
"""
import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.gestion_compte

JSON = {"Accept": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email="test@devoptiq.com").first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = umail
        sess["active_entity_id"] = ids["entity_id"]
        sess["lang"] = "fr"


def _mk_user(email, status, prenom="T87"):
    from Code.extensions import db
    from Code.models.models import User
    u = User.query.filter_by(email=email).first()
    if u is None:
        u = User(first_name=prenom, last_name=email.split("@")[0], email=email,
                 password=generate_password_hash("Test1234!"), status=status)
        db.session.add(u)
    u.status = status
    db.session.commit()
    return u.id


def _as(client, uid, email):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = email
        sess["lang"] = "fr"


@pytest.fixture(scope="module")
def monde(app):
    """Un admin, une cible qui tient un rôle sur une carto COMMUNE et un autre
    sur une carto PRIVÉE que l'admin n'ouvre pas."""
    from Code.extensions import db
    from Code.models.models import Entity, Role, UserRole

    with app.app_context():
        admin = _mk_user("t87.admin@devoptiq.com", "administrateur")
        proprio = _mk_user("t87.proprio@devoptiq.com", "coordinateur")
        cible = _mk_user("t87.cible@devoptiq.com", "user", prenom="Cible")
        dev = _mk_user("t87.dev@devoptiq.com", "user", prenom="Dev")
        simple = _mk_user("t87.simple@devoptiq.com", "user", prenom="Simple")
        # Un coordinateur qui n'ouvre PAS la carto privée : les rôles qu'il peut
        # attribuer s'arrêtent aux cartos qu'il voit.
        coord2 = _mk_user("t87.coord2@devoptiq.com", "coordinateur", prenom="Coord")

        commune = Entity(name="T87 Carto commune", owner_id=proprio, is_shared=True)
        privee = Entity(name="T87 Carto privée", owner_id=proprio, is_shared=False)
        db.session.add_all([commune, privee])
        db.session.commit()
        r1 = Role(name="T87 Méthodes", entity_id=commune.id)
        r2 = Role(name="T87 Qualité", entity_id=commune.id)
        r3 = Role(name="T87 Atelier", entity_id=privee.id)
        db.session.add_all([r1, r2, r3])
        db.session.commit()
        # Le rôle de la carto commune porte un développeur de compétences :
        # il ne doit pas disparaître quand on retouche la fiche.
        db.session.add(UserRole(user_id=cible, role_id=r1.id, manager_id=dev))
        db.session.add(UserRole(user_id=cible, role_id=r3.id))
        db.session.commit()
        m = {"admin": admin, "proprio": proprio, "cible": cible, "dev": dev,
             "simple": simple, "coord2": coord2,
             "commune": commune.id, "privee": privee.id,
             "r1": r1.id, "r2": r2.id, "r3": r3.id}
    yield m

    with app.app_context():
        from Code.models.models import User
        UserRole.query.filter(UserRole.role_id.in_([m["r1"], m["r2"], m["r3"]])).delete(
            synchronize_session=False)
        Role.query.filter(Role.id.in_([m["r1"], m["r2"], m["r3"]])).delete(
            synchronize_session=False)
        for eid in (m["commune"], m["privee"]):
            e = db.session.get(Entity, eid)
            if e:
                e.is_shared = False
                db.session.delete(e)
        cree = User.query.filter_by(email="t87.nouveau@devoptiq.com").first()
        if cree:
            UserRole.query.filter_by(user_id=cree.id).delete()
            db.session.delete(cree)
        db.session.commit()


def _roles_de(app, uid):
    from Code.models.models import UserRole
    with app.app_context():
        return {ur.role_id: ur.manager_id for ur in UserRole.query.filter_by(user_id=uid).all()}


def _fiche(m, **extra):
    corps = {"first_name": "Cible", "last_name": "Corrigée",
             "email": "t87.cible@devoptiq.com", "age": ""}
    corps.update(extra)
    return corps


class TestLesRolesBougentParPaire:

    def test_corriger_un_nom_ne_retire_aucun_role(self, app, client, monde):
        """⚠️ LE défaut : l'ancienne fiche envoyait `role_id` vide pour
        quelqu'un dont le rôle n'était pas sur la carto active."""
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        avant = _roles_de(app, monde["cible"])
        rep = client.post(f"/comptes/update/{monde['cible']}", data=_fiche(monde, role_id=""))
        assert rep.status_code == 302 and "msg=updated" in rep.headers["Location"]
        assert _roles_de(app, monde["cible"]) == avant

    def test_retirer_et_ajouter_ne_touche_que_ce_qui_est_nomme(self, app, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        client.post(f"/comptes/update/{monde['cible']}", headers=JSON, data={
            **_fiche(monde), "roles_ajout": [str(monde["r2"])]})
        roles = _roles_de(app, monde["cible"])
        assert set(roles) == {monde["r1"], monde["r2"], monde["r3"]}
        assert roles[monde["r1"]] == monde["dev"]      # le développeur est resté

        client.post(f"/comptes/update/{monde['cible']}", headers=JSON, data={
            **_fiche(monde), "roles_retrait": [str(monde["r2"])]})
        assert set(_roles_de(app, monde["cible"])) == {monde["r1"], monde["r3"]}

    def test_un_role_inconnu_est_refuse_et_rien_ne_bouge(self, app, client, monde):
        """Une fiche refusée n'écrit RIEN, pas même le nom."""
        _as(client, monde["coord2"], "t87.coord2@devoptiq.com")
        rep = client.post(f"/comptes/update/{monde['coord2']}", headers=JSON, data={
            "first_name": "Coord", "last_name": "Jamais", "email": "t87.coord2@devoptiq.com",
            "roles_ajout": ["999999"]})
        assert rep.status_code == 400
        assert rep.get_json() == {"ok": False, "code": "error_role_unknown", "champ": "roles"}
        assert _roles_de(app, monde["coord2"]) == {}
        with app.app_context():
            from Code.extensions import db
            from Code.models.models import User
            assert db.session.get(User, monde["coord2"]).last_name != "Jamais"

    def test_un_administrateur_peut_tout_attribuer(self, app, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        rep = client.post(f"/comptes/update/{monde['cible']}", headers=JSON, data={
            **_fiche(monde), "roles_ajout": [str(monde["r2"])], "roles_retrait": [str(monde["r2"])]})
        assert rep.get_json()["ok"] is True
        # Ajouter et retirer le MÊME rôle dans une fiche : l'ajout l'emporte,
        # on ne retire pas ce qu'on vient de donner.
        assert monde["r2"] in _roles_de(app, monde["cible"])
        client.post(f"/comptes/update/{monde['cible']}", headers=JSON, data={
            **_fiche(monde), "roles_retrait": [str(monde["r2"])]})

    def test_on_ne_se_donne_pas_de_role(self, app, client, monde):
        """Un rôle ouvre des cartos : se l'attribuer depuis sa propre fiche,
        c'est s'ouvrir un accès."""
        _as(client, monde["simple"], "t87.simple@devoptiq.com")
        rep = client.post(f"/comptes/update/{monde['simple']}", headers=JSON, data={
            "first_name": "Simple", "last_name": "T87", "email": "t87.simple@devoptiq.com",
            "roles_ajout": [str(monde["r1"])]})
        assert rep.status_code == 403
        assert rep.get_json()["code"] == "error_forbidden_roles"
        assert _roles_de(app, monde["simple"]) == {}


class TestLeNiveauDAcces:

    def test_un_admin_ne_change_pas_son_propre_niveau(self, app, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        client.post(f"/comptes/update/{monde['admin']}", headers=JSON, data={
            "first_name": "T87", "last_name": "admin", "email": "t87.admin@devoptiq.com",
            "status": "user"})
        with app.app_context():
            from Code.extensions import db
            from Code.models.models import User
            assert db.session.get(User, monde["admin"]).status == "administrateur"

    def test_un_admin_change_celui_des_autres(self, app, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        client.post(f"/comptes/update/{monde['cible']}", headers=JSON, data={
            **_fiche(monde), "status": "champion"})
        with app.app_context():
            from Code.extensions import db
            from Code.models.models import User
            assert db.session.get(User, monde["cible"]).status == "champion"


class TestLaFicheResteOuverte:
    """Les réponses de la fiche : JSON, avec le champ à désigner."""

    def test_un_email_deja_pris(self, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        rep = client.post(f"/comptes/update/{monde['cible']}", headers=JSON,
                          data=_fiche(monde, email="t87.admin@devoptiq.com"))
        assert rep.status_code == 400
        assert rep.get_json() == {"ok": False, "code": "error_email_exists", "champ": "email"}

    def test_un_mot_de_passe_trop_court(self, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        rep = client.post(f"/comptes/update/{monde['cible']}", headers=JSON,
                          data=_fiche(monde, password="abc"))
        assert rep.get_json()["champ"] == "password"

    def test_un_succes(self, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        rep = client.post(f"/comptes/update/{monde['cible']}", headers=JSON, data=_fiche(monde))
        assert rep.status_code == 200
        assert rep.get_json() == {"ok": True, "code": "updated", "champ": None}


class TestLaCreation:

    def test_plusieurs_roles_d_un_coup(self, app, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        rep = client.post("/comptes/create", headers=JSON, data={
            "first_name": "Nouveau", "last_name": "T87", "email": "t87.nouveau@devoptiq.com",
            "password": "Test1234!", "status": "user",
            "roles_ajout": [str(monde["r1"]), str(monde["r2"])]})
        assert rep.get_json()["ok"] is True
        with app.app_context():
            from Code.models.models import User
            uid = User.query.filter_by(email="t87.nouveau@devoptiq.com").first().id
        assert set(_roles_de(app, uid)) == {monde["r1"], monde["r2"]}

    def test_rien_n_est_cree_a_moitie(self, app, client, monde):
        """Un rôle refusé : ni compte, ni rôle — un compte sans les rôles
        demandés laisserait croire que tout est en place."""
        _as(client, monde["coord2"], "t87.coord2@devoptiq.com")
        rep = client.post("/comptes/create", headers=JSON, data={
            "first_name": "Moitié", "last_name": "T87", "email": "t87.moitie@devoptiq.com",
            "password": "Test1234!", "status": "user", "roles_ajout": ["999999"]})
        assert rep.status_code == 400
        with app.app_context():
            from Code.models.models import User
            assert User.query.filter_by(email="t87.moitie@devoptiq.com").first() is None

    def test_on_ne_cree_pas_au_dessus_de_soi(self, client, monde):
        _as(client, monde["proprio"], "t87.proprio@devoptiq.com")
        rep = client.post("/comptes/create", headers=JSON, data={
            "first_name": "Trop", "last_name": "Haut", "email": "t87.haut@devoptiq.com",
            "password": "Test1234!", "status": "administrateur"})
        assert rep.status_code == 403
        assert rep.get_json()["champ"] == "status"


class TestLaPage:

    def test_la_fiche_liste_les_roles_tenus(self, client, monde):
        _as(client, monde["admin"], "t87.admin@devoptiq.com")
        html = client.get("/comptes/").get_data(as_text=True)
        assert "T87 Qualité" in html and "window.ACC_ROLES" in html

    def test_le_catalogue_propose_les_roles_de_l_entreprise(self, client, monde):
        """Un rôle appartient à l'entreprise : la fiche les propose tous, quelle
        que soit la carto où sa bande existe."""
        import json
        _as(client, monde["coord2"], "t87.coord2@devoptiq.com")
        html = client.get("/comptes/").get_data(as_text=True)
        debut = html.index("window.ACC_ROLES = ") + len("window.ACC_ROLES = ")
        catalogue = json.loads(html[debut:html.index(";\n", debut)])
        ids = {r["id"] for r in catalogue}
        assert {monde["r1"], monde["r2"], monde["r3"]} <= ids
