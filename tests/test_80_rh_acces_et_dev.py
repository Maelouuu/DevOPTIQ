# tests/test_80_rh_acces_et_dev.py
"""
Page Gestion RH : un rôle sur PLUSIEURS cartos, et un développeur par RÔLE.

Deux manœuvres que la page ne savait pas faire, chacune pour une raison
différente :

⚠️ **Ouvrir une carto à un rôle se faisait carto par carto.** Il fallait
changer l'entité en haut de page, cocher, recommencer — cinq cartos, cinq
allers-retours — et il n'existait AUCUN endroit d'où voir ce qu'un rôle ouvre
au total. `set_access` (page Partage) n'accepte que les rôles DE l'entité
réglée, ce qui est juste là-bas : on y règle une carto et on coche parmi SES
bandes. Ici on part du rôle. `can_read` s'en accommode depuis toujours — il
compare les rôles du compte aux rôles autorisés sans jamais demander à quelle
entité ces rôles appartiennent.

⚠️ **Le développeur de compétences par rôle EXISTAIT en base et n'était posé
par aucun écran.** `user_roles.manager_id` porte ce lien, `encadre()` le lit
déjà — mais la page envoyait `role_ids: null`, c'est-à-dire « le même
développeur pour tous les rôles ». Celui qui suit quelqu'un sur « Qualité » ne
le suit pourtant pas forcément sur « Logistique ».

Deux pièges de cet écran, vérifiés ici parce qu'ils décident de qui voit quoi :
  · une carto PRIVÉE ignore les rôles — la cocher doit la rendre commune,
    sinon on enregistre un accès qui ne produit rien ;
  · une carto commune SANS aucun rôle autorisé est ouverte à TOUS. Y poser le
    premier rôle la RESTREINT : cocher peut retirer l'accès à des gens qui
    l'avaient.
"""
import pytest

pytestmark = pytest.mark.gestion_rh


# ── Le décor ────────────────────────────────────────────────────────────────
@pytest.fixture
def scene(app):
    """Un coordinateur, deux cartos à lui, un rôle, deux collaborateurs."""
    from Code.extensions import db
    from Code.models.models import Entity, Role, User, UserRole
    from Code.security import hash_password

    cree = {"users": [], "entities": [], "roles": [], "liens": []}
    with app.app_context():
        def compte(mail, statut):
            u = User.query.filter_by(email=mail).first()
            if u is None:
                u = User(first_name="T80", last_name=mail.split(".")[1],
                         email=mail, password=hash_password("Motdepasse123!"),
                         status=statut)
                db.session.add(u)
                db.session.commit()
            u.status = statut
            db.session.commit()
            cree["users"].append(u.id)
            return u.id

        coord = compte("t80.coord@devoptiq.com", "coordinateur")
        dev = compte("t80.dev@devoptiq.com", "user")
        collab = compte("t80.collab@devoptiq.com", "user")

        def carto(nom, partagee):
            # ⚠️ `owner_id` obligatoire : une entité sans propriétaire est
            # lisible par TOUT LE MONDE et deviendrait le repli « aucune entité
            # active » des fichiers suivants (la base est partagée).
            e = Entity.query.filter_by(name=nom).first()
            if e is None:
                e = Entity(name=nom, owner_id=coord)
                db.session.add(e)
                db.session.commit()
            e.owner_id = coord
            e.is_shared = partagee
            db.session.commit()
            cree["entities"].append(e.id)
            return e.id

        carto_a = carto("T80 Carto A", True)
        carto_b = carto("T80 Carto B", False)

        r = Role.query.filter_by(name="T80 Métier", entity_id=carto_a).first()
        if r is None:
            r = Role(name="T80 Métier", entity_id=carto_a)
            db.session.add(r)
            db.session.commit()
        cree["roles"].append(r.id)

        r2 = Role.query.filter_by(name="T80 Second", entity_id=carto_a).first()
        if r2 is None:
            r2 = Role(name="T80 Second", entity_id=carto_a)
            db.session.add(r2)
            db.session.commit()
        cree["roles"].append(r2.id)

        for rid in (r.id, r2.id):
            lien = UserRole.query.filter_by(user_id=collab, role_id=rid).first()
            if lien is None:
                lien = UserRole(user_id=collab, role_id=rid)
                db.session.add(lien)
                db.session.commit()
            cree["liens"].append((collab, rid))

        donnees = {"coord": coord, "dev": dev, "collab": collab,
                   "carto_a": carto_a, "carto_b": carto_b,
                   "role": r.id, "role2": r2.id}

    yield donnees

    # ⚠️ Ménage : une carto laissée COMMUNE et ouverte à tous devient le repli
    # des fichiers suivants, et une ligne d'accès orpheline fausse leurs
    # comptages.
    with app.app_context():
        from Code.models.models import EntityRoleAccess
        EntityRoleAccess.query.filter(
            EntityRoleAccess.role_id.in_(cree["roles"])).delete(
                synchronize_session=False)
        for uid, rid in cree["liens"]:
            UserRole.query.filter_by(user_id=uid, role_id=rid).delete()
        for rid in cree["roles"]:
            Role.query.filter_by(id=rid).delete()
        for eid in cree["entities"]:
            Entity.query.filter_by(id=eid).delete()
        for uid in cree["users"]:
            User.query.filter_by(id=uid).delete()
        db.session.commit()


def _en_tant_que(client, app, uid):
    from Code.extensions import db
    from Code.models.models import User
    with app.app_context():
        u = db.session.get(User, uid)
        mail = u.email
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = uid
        sess["user_email"] = mail
        sess["lang"] = "fr"


# ══════════════════════════════════════════════════════════════════════
#  1 · Un rôle, plusieurs cartos
# ══════════════════════════════════════════════════════════════════════
class TestUnRoleSurPlusieursCartos:

    def test_la_liste_dit_ce_que_le_role_ouvre_deja(self, app, client, scene):
        _en_tant_que(client, app, scene["coord"])
        d = client.get("/gestion_rh/role_cartos/%d" % scene["role"]).get_json()
        assert d["role"]["id"] == scene["role"]
        par_id = {c["id"]: c for c in d["cartos"]}
        assert scene["carto_a"] in par_id and scene["carto_b"] in par_id
        assert par_id[scene["carto_a"]]["ouverte"] is False
        assert par_id[scene["carto_b"]]["commune"] is False

    def test_une_seule_manoeuvre_ouvre_DEUX_cartos(self, app, client, scene):
        """Le cœur de la demande : plus besoin de changer d'entité à chaque fois."""
        from Code.carto_access import entity_role_ids
        _en_tant_que(client, app, scene["coord"])
        r = client.post("/gestion_rh/role_cartos", json={
            "role_id": scene["role"],
            "entity_ids": [scene["carto_a"], scene["carto_b"]]})
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert sorted(d["ouvertes"]) == sorted([scene["carto_a"], scene["carto_b"]])
        with app.app_context():
            assert scene["role"] in entity_role_ids(scene["carto_a"])
            assert scene["role"] in entity_role_ids(scene["carto_b"])

    def test_une_carto_privee_devient_commune_et_on_le_DIT(self, app, client, scene):
        """⚠️ `can_read` rend la main au propriétaire d'une carto privée AVANT
        de consulter les rôles : y poser un rôle sans la rendre commune
        enregistrerait un accès qui ne produit rien."""
        from Code.extensions import db
        from Code.models.models import Entity
        _en_tant_que(client, app, scene["coord"])
        d = client.post("/gestion_rh/role_cartos", json={
            "role_id": scene["role"],
            "entity_ids": [scene["carto_b"]]}).get_json()
        assert d["rendues_communes"] == [scene["carto_b"]]
        with app.app_context():
            assert db.session.get(Entity, scene["carto_b"]).is_shared is True

    def test_decocher_referme(self, app, client, scene):
        from Code.carto_access import entity_role_ids
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/role_cartos", json={
            "role_id": scene["role"],
            "entity_ids": [scene["carto_a"], scene["carto_b"]]})
        d = client.post("/gestion_rh/role_cartos", json={
            "role_id": scene["role"], "entity_ids": [scene["carto_a"]]}).get_json()
        assert d["fermees"] == [scene["carto_b"]]
        with app.app_context():
            assert scene["role"] in entity_role_ids(scene["carto_a"])
            assert scene["role"] not in entity_role_ids(scene["carto_b"])

    def test_regler_un_role_ne_touche_pas_les_AUTRES_roles(self, app, client, scene):
        """Sans cette précaution, régler un rôle effacerait le travail fait sur
        les autres : on réécrit la ligne de CE rôle, pas la liste entière."""
        from Code.carto_access import entity_role_ids
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/role_cartos", json={
            "role_id": scene["role2"], "entity_ids": [scene["carto_a"]]})
        client.post("/gestion_rh/role_cartos", json={
            "role_id": scene["role"], "entity_ids": [scene["carto_a"]]})
        with app.app_context():
            autorises = entity_role_ids(scene["carto_a"])
        assert scene["role2"] in autorises, "l'autre rôle a été effacé"
        assert scene["role"] in autorises

    def test_l_ecran_annonce_la_carto_ouverte_a_TOUS(self, app, client, scene):
        """⚠️ Une carto commune sans aucun rôle autorisé est ouverte à tout le
        monde. Y poser le premier rôle la RESTREINT — cocher retire alors
        l'accès à des gens qui l'avaient. L'écran doit pouvoir le dire."""
        _en_tant_que(client, app, scene["coord"])
        d = client.get("/gestion_rh/role_cartos/%d" % scene["role"]).get_json()
        a = next(c for c in d["cartos"] if c["id"] == scene["carto_a"])
        assert a["sans_filtre"] is True and a["n_roles"] == 0

    def test_un_user_ne_regle_rien(self, app, client, scene):
        """Le masquage n'est pas une sécurité : la route refuse aussi."""
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            db.session.get(User, scene["coord"]).status = "user"
            db.session.commit()
        try:
            _en_tant_que(client, app, scene["coord"])
            assert client.get("/gestion_rh/role_cartos/%d"
                              % scene["role"]).status_code == 403
            assert client.post("/gestion_rh/role_cartos", json={
                "role_id": scene["role"],
                "entity_ids": [scene["carto_b"]]}).status_code == 403
        finally:
            with app.app_context():
                db.session.get(User, scene["coord"]).status = "coordinateur"
                db.session.commit()

    def test_une_carto_qu_on_ne_gere_pas_est_refusee(self, app, client, scene):
        """On ne touche QUE les cartos dont l'appelant règle l'accès."""
        from Code.extensions import db
        from Code.models.models import Entity, User
        from Code.security import hash_password
        with app.app_context():
            autre = User(first_name="T80", last_name="Etranger",
                         email="t80.etranger@devoptiq.com",
                         password=hash_password("Motdepasse123!"), status="user")
            db.session.add(autre)
            db.session.commit()
            e = Entity(name="T80 Carto d'un autre", owner_id=autre.id,
                       is_shared=False)
            db.session.add(e)
            db.session.commit()
            eid, aid = e.id, autre.id
        try:
            _en_tant_que(client, app, scene["coord"])
            d = client.post("/gestion_rh/role_cartos", json={
                "role_id": scene["role"], "entity_ids": [eid]}).get_json()
            assert eid in d["refusees"]
            assert eid not in d["ouvertes"]
            with app.app_context():
                assert db.session.get(Entity, eid).is_shared is False
        finally:
            with app.app_context():
                Entity.query.filter_by(id=eid).delete()
                User.query.filter_by(id=aid).delete()
                db.session.commit()


# ══════════════════════════════════════════════════════════════════════
#  2 · Un développeur de compétences PAR RÔLE
# ══════════════════════════════════════════════════════════════════════
class TestDeveloppeurParRole:

    def test_on_pose_un_developpeur_sur_UN_role(self, app, client, scene):
        from Code.extensions import db
        from Code.models.models import UserRole
        _en_tant_que(client, app, scene["coord"])
        r = client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role"],
            "dev_id": scene["dev"]})
        assert r.status_code == 200, r.get_json()
        with app.app_context():
            lien = UserRole.query.filter_by(user_id=scene["collab"],
                                            role_id=scene["role"]).first()
            autre = UserRole.query.filter_by(user_id=scene["collab"],
                                             role_id=scene["role2"]).first()
        assert lien.manager_id == scene["dev"]
        assert autre.manager_id is None, (
            "le second rôle ne doit PAS hériter du développeur — c'est tout "
            "l'objet de l'affectation par rôle")

    def test_on_le_retire(self, app, client, scene):
        from Code.models.models import UserRole
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role"],
            "dev_id": scene["dev"]})
        client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role"], "dev_id": None})
        with app.app_context():
            lien = UserRole.query.filter_by(user_id=scene["collab"],
                                            role_id=scene["role"]).first()
        assert lien.manager_id is None

    def test_deux_roles_deux_developpeurs(self, app, client, scene):
        """La raison d'être de la manœuvre : celui qui suit quelqu'un sur un
        rôle ne le suit pas forcément sur l'autre."""
        from Code.models.models import UserRole
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role"],
            "dev_id": scene["dev"]})
        client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role2"],
            "dev_id": scene["coord"]})
        with app.app_context():
            liens = {ur.role_id: ur.manager_id for ur in
                     UserRole.query.filter_by(user_id=scene["collab"]).all()}
        assert liens[scene["role"]] == scene["dev"]
        assert liens[scene["role2"]] == scene["coord"]

    def test_un_role_que_la_personne_ne_tient_pas_est_refuse(self, app, client, scene):
        """Le lien qui porterait l'information n'existe pas : mieux vaut le
        dire que d'enregistrer dans le vide."""
        _en_tant_que(client, app, scene["coord"])
        r = client.post("/gestion_rh/role_dev", json={
            "user_id": scene["dev"], "role_id": scene["role"],
            "dev_id": scene["coord"]})
        assert r.status_code == 404

    def test_on_ne_se_suit_pas_soi_meme(self, app, client, scene):
        _en_tant_que(client, app, scene["coord"])
        r = client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role"],
            "dev_id": scene["collab"]})
        assert r.status_code == 400

    def test_un_user_ne_pose_aucun_developpeur(self, app, client, scene):
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            db.session.get(User, scene["coord"]).status = "user"
            db.session.commit()
        try:
            _en_tant_que(client, app, scene["coord"])
            assert client.post("/gestion_rh/role_dev", json={
                "user_id": scene["collab"], "role_id": scene["role"],
                "dev_id": scene["dev"]}).status_code == 403
        finally:
            with app.app_context():
                db.session.get(User, scene["coord"]).status = "coordinateur"
                db.session.commit()

    def test_le_developpeur_par_role_est_bien_celui_qui_ENCADRE(self, app, scene):
        """⚠️ Le lien ne sert à rien s'il n'ouvre aucun droit. `encadre()` lit
        les DEUX rattachements — global et par rôle — et c'est lui qui décide
        qui peut noter qui sur la page Compétences."""
        from Code.competences_acces import encadre
        from Code.extensions import db
        from Code.models.models import UserRole
        with app.app_context():
            lien = UserRole.query.filter_by(user_id=scene["collab"],
                                            role_id=scene["role"]).first()
            lien.manager_id = scene["dev"]
            db.session.commit()
            assert encadre(scene["dev"], scene["collab"]) is True
            lien.manager_id = None
            db.session.commit()
            assert encadre(scene["dev"], scene["collab"]) is False


# ══════════════════════════════════════════════════════════════════════
#  3 · La PORTÉE d'un développeur : sur tous ses rôles, ou sur certains
# ══════════════════════════════════════════════════════════════════════
# ⚠️ Le défaut de fond que ces cas ferment : `encadre()` lit les DEUX
# rattachements. Tant que `users.manager_id` est posé, il couvre TOUS les
# rôles — donc « restreindre à un rôle » ne produisait RIEN, et l'écran
# affichait une restriction qui n'existait pas.

class TestLaPorteeDUnDeveloppeur:

    def _etat(self, app, scene):
        from Code.extensions import db
        from Code.models.models import User, UserRole
        with app.app_context():
            u = db.session.get(User, scene["collab"])
            liens = {ur.role_id: ur.manager_id for ur in
                     UserRole.query.filter_by(user_id=scene["collab"]).all()}
            return u.manager_id, liens

    def test_tous_ses_roles_pose_le_lien_global_ET_chaque_role(self, app, client, scene):
        """Le lien global couvre aussi les rôles reçus PLUS TARD : c'est ce qui
        distingue « tous ses rôles » d'une liste qui les nommerait tous."""
        _en_tant_que(client, app, scene["coord"])
        r = client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": scene["dev"], "role_ids": None})
        assert r.status_code == 200, r.get_json()
        glob, liens = self._etat(app, scene)
        assert glob == scene["dev"]
        assert liens[scene["role"]] == scene["dev"]
        assert liens[scene["role2"]] == scene["dev"]

    def test_restreindre_a_un_role_DISSOUT_le_lien_global(self, app, client, scene):
        """⚠️ Le cas qui ne marchait pas. Sans dissolution, le lien global
        continuait de couvrir le second rôle : l'écran disait « 1 rôle sur 2 »
        et le droit disait « les deux »."""
        from Code.competences_acces import encadre
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": scene["dev"], "role_ids": None})
        r = client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": scene["dev"],
            "role_ids": [scene["role"]]})
        assert r.status_code == 200, r.get_json()
        glob, liens = self._etat(app, scene)
        assert glob is None, "le lien global aurait couvert les deux rôles"
        assert liens[scene["role"]] == scene["dev"]
        assert liens[scene["role2"]] is None
        with app.app_context():
            assert encadre(scene["dev"], scene["collab"]) is True

    def test_restreindre_n_efface_pas_l_AUTRE_developpeur(self, app, client, scene):
        """On règle la portée d'UN développeur ; celui du rôle voisin ne
        bouge pas, sinon régler l'un déferait le travail fait sur l'autre."""
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role2"],
            "dev_id": scene["coord"]})
        client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": scene["dev"],
            "role_ids": [scene["role"]]})
        glob, liens = self._etat(app, scene)
        assert liens[scene["role"]] == scene["dev"]
        assert liens[scene["role2"]] == scene["coord"]
        assert glob is None

    def test_on_retire_le_developpeur_de_partout(self, app, client, scene):
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": scene["dev"], "role_ids": None})
        r = client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": None, "role_ids": None})
        assert r.status_code == 200
        glob, liens = self._etat(app, scene)
        assert glob is None
        assert set(liens.values()) == {None}

    def test_poser_un_developpeur_PAR_ROLE_dissout_aussi_le_lien_global(
            self, app, client, scene):
        """⚠️ Vérifié ROUGE sur le code d'avant : `/role_dev` écrivait le rôle
        et laissait le lien global en place, qui recouvrait tout."""
        _en_tant_que(client, app, scene["coord"])
        client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": scene["dev"], "role_ids": None})
        r = client.post("/gestion_rh/role_dev", json={
            "user_id": scene["collab"], "role_id": scene["role"], "dev_id": None})
        assert r.status_code == 200
        glob, liens = self._etat(app, scene)
        assert glob is None, "sinon le développeur retiré suivait encore ce rôle"
        assert liens[scene["role"]] is None
        assert liens[scene["role2"]] == scene["dev"], (
            "ce que le lien global couvrait doit être repris rôle par rôle, "
            "sinon on retirerait le développeur du second rôle par surprise")

    def test_un_role_que_la_personne_ne_tient_pas_est_refuse(self, app, client, scene):
        _en_tant_que(client, app, scene["coord"])
        r = client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["dev"], "dev_id": scene["coord"],
            "role_ids": [scene["role"]]})
        assert r.status_code == 404

    def test_on_ne_se_suit_pas_soi_meme(self, app, client, scene):
        _en_tant_que(client, app, scene["coord"])
        r = client.post("/gestion_rh/dev_scope", json={
            "user_id": scene["collab"], "dev_id": scene["collab"],
            "role_ids": None})
        assert r.status_code == 400

    def test_un_user_ne_regle_aucune_portee(self, app, client, scene):
        """Le masquage n'est pas une sécurité : la route refuse aussi."""
        from Code.extensions import db
        from Code.models.models import User
        with app.app_context():
            db.session.get(User, scene["coord"]).status = "user"
            db.session.commit()
        try:
            _en_tant_que(client, app, scene["coord"])
            r = client.post("/gestion_rh/dev_scope", json={
                "user_id": scene["collab"], "dev_id": scene["dev"],
                "role_ids": None})
            assert r.status_code == 403
        finally:
            with app.app_context():
                db.session.get(User, scene["coord"]).status = "coordinateur"
                db.session.commit()
