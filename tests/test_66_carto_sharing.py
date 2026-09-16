# tests/test_66_carto_sharing.py
"""
Partage d'une carto par RÔLE, et modifications proposées.

Le modèle historique recopiait l'entité chez chaque destinataire : chacun
repartait avec sa version, plus rien ne les reliait. Ici une carto COMMUNE est
UNE ligne travaillée par plusieurs comptes :

  * l'accès s'ouvre à des RÔLES, jamais à des comptes — qui reçoit le rôle
    demain entre sans qu'on revienne sur l'écran d'accès ; aucun rôle coché =
    ouverte à tous ;
  * une carto privée n'obéit à rien de tout ça ;
  * sur une carto commune, quatre paliers : un `user` CONSULTE, un `champion`
    PROPOSE, un `coordinateur` ou un `admin` APPLIQUE — et ce qui est appliqué
    vaut pour tout le monde, puisque c'est la même ligne.
"""
import json

import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.carto_sharing


DIAGRAM = {
    "shapes": [
        {"id": "s1", "type": "process", "label": "Partage Rôle A",
         "x": 100, "y": 0, "w": 120, "h": 60},
        {"id": "s2", "type": "process", "label": "Partage Rôle B",
         "x": 400, "y": 0, "w": 120, "h": 60},
    ],
    "bands": [{"id": "b1", "label": "Bande Partage Rôle", "height": 200}],
    "connections": [{"fromId": "s1", "toId": "s2", "label": "flux"}],
}


# Le client de test est partagé par toute la suite : on rend la session d'origine.
@pytest.fixture(scope="module", autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email="test@devoptiq.com").first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_email"] = umail
        sess["active_entity_id"] = ids["entity_id"]


def _mk_user(app, email, status):
    from Code.extensions import db
    from Code.models.models import User
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(first_name="T66", last_name=email.split("@")[0], email=email,
                     password=generate_password_hash("Test1234!"), status=status)
            db.session.add(u)
        u.status = status
        db.session.commit()
        return u.id


def _as(client, user_id, email, entity_id=None):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_email"] = email
        if entity_id is not None:
            sess["active_entity_id"] = entity_id


@pytest.fixture(scope="module")
def scene(app):
    """Une carto, deux rôles, et un compte par statut."""
    from Code.extensions import db
    from Code.models.models import Entity, EntityRoleAccess, Role, UserRole

    coordinateur = _mk_user(app, "t66.coord@devoptiq.com", "coordinateur")
    champion = _mk_user(app, "t66.champion@devoptiq.com", "champion")
    admin = _mk_user(app, "t66.admin@devoptiq.com", "administrateur")
    porteur = _mk_user(app, "t66.porteur@devoptiq.com", "user")
    etranger = _mk_user(app, "t66.etranger@devoptiq.com", "user")

    with app.app_context():
        ent = Entity.query.filter_by(name="Carto commune T66").first()
        if ent is None:
            ent = Entity(name="Carto commune T66", owner_id=coordinateur)
            db.session.add(ent)
        ent.owner_id = coordinateur
        ent.optiqcarto_data = json.dumps(DIAGRAM, ensure_ascii=False)
        ent.is_shared = False
        db.session.commit()

        roles = {}
        for nom in ("T66 Métier", "T66 Support"):
            r = Role.query.filter_by(entity_id=ent.id, name=nom).first()
            if r is None:
                r = Role(entity_id=ent.id, name=nom)
                db.session.add(r)
                db.session.commit()
            roles[nom] = r.id

        # `porteur` tient le rôle Métier ; `etranger` n'en tient aucun.
        for uid in (porteur, champion):
            if not UserRole.query.filter_by(
                    user_id=uid, role_id=roles["T66 Métier"]).first():
                db.session.add(UserRole(user_id=uid, role_id=roles["T66 Métier"]))
        UserRole.query.filter_by(user_id=etranger).delete()
        EntityRoleAccess.query.filter_by(entity_id=ent.id).delete()
        db.session.commit()

        scene = {"entity_id": ent.id, "coordinateur": coordinateur,
                 "champion": champion, "admin": admin,
                 "porteur": porteur, "etranger": etranger,
                 "role_metier": roles["T66 Métier"],
                 "role_support": roles["T66 Support"]}

    yield scene

    # ⚠️ La base est PARTAGÉE entre tous les fichiers. Ce module laisse la
    # carto « commune, ouverte à tous » selon le dernier cas joué — et une carto
    # ouverte à tous devient le REPLI « aucune entité active » des autres
    # fichiers : `test_75` retrouvait celle-ci au lieu de la sienne. On rend la
    # carto privée en partant.
    with app.app_context():
        ent = db.session.get(Entity, scene["entity_id"])
        if ent is not None:
            ent.is_shared = False
            EntityRoleAccess.query.filter_by(entity_id=ent.id).delete()
            db.session.commit()


def _regler_acces(app, entity_id, partage, role_ids=()):
    from Code.carto_access import set_access
    from Code.extensions import db
    from Code.models.models import Entity
    with app.app_context():
        ent = db.session.get(Entity, entity_id)
        set_access(ent, partage, role_ids)
        db.session.commit()


# ══════════════════════════════════════════════════════════════════════════
# 1. Statuts
# ══════════════════════════════════════════════════════════════════════════

class TestStatuts:

    def test_l_arbitre_est_reconnu_sous_ses_anciens_libelles(self):
        """⚠️ « champion » a CHANGÉ DE SENS : il désignait celui qui arbitre,
        c'est désormais le coordinateur. Tous les libellés historiques de
        l'arbitre doivent donc être lus comme « coordinateur » — sinon des
        comptes en service perdraient leur droit de valider au premier
        démarrage du nouveau code."""
        from Code.permissions import is_coordinator_status
        for valeur in ("coordinateur", "Coordinateur", "coordinator", "manager",
                       "Gestionnaire de compétences", "gestionnaire de comp",
                       "Competency Manager"):
            assert is_coordinator_status(valeur), valeur

    def test_le_mot_champion_designe_le_palier_qui_propose(self):
        from Code.permissions import is_champion_status, is_coordinator_status
        assert is_champion_status("champion")
        assert not is_coordinator_status("champion"), (
            "« champion » ne doit plus donner le droit d'arbitrer")

    def test_ni_user_ni_vide_ne_sont_quoi_que_ce_soit(self):
        from Code.permissions import (is_admin_status, is_champion_status,
                                      is_coordinator_status)
        for valeur in ("user", "rh", "", None):
            assert not is_champion_status(valeur)
            assert not is_coordinator_status(valeur)
            assert not is_admin_status(valeur)

    def test_l_echelle_est_ordonnee(self):
        """Chaque palier ajoute aux droits du précédent : c'est ce qui permet
        d'écrire « au moins coordinateur » sans énumérer les statuts."""
        from Code.permissions import niveau_status
        assert (niveau_status("user") < niveau_status("champion")
                < niveau_status("coordinateur") < niveau_status("admin"))

    def test_les_valeurs_canoniques_tiennent_dans_la_colonne(self):
        """users.status est un VARCHAR(20) : un libellé long y arriverait tronqué."""
        from Code.permissions import CHAMPION_STATUS, COORDINATOR_STATUS
        assert len(CHAMPION_STATUS) <= 20
        assert len(COORDINATOR_STATUS) <= 20


# ══════════════════════════════════════════════════════════════════════════
# 2. Qui voit la carto
# ══════════════════════════════════════════════════════════════════════════

class TestLecture:

    def test_une_carto_privee_ne_se_voit_que_chez_son_proprietaire(self, app, scene):
        from Code.carto_access import can_read
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], False)
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert can_read(ent, db.session.get(User, scene["coordinateur"]))
            assert not can_read(ent, db.session.get(User, scene["porteur"]))
            assert not can_read(ent, db.session.get(User, scene["etranger"]))

    def test_une_carto_commune_sans_role_est_ouverte_a_tous(self, app, scene):
        from Code.carto_access import can_read
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            for uid in (scene["porteur"], scene["etranger"]):
                assert can_read(ent, db.session.get(User, uid))

    def test_un_role_coche_referme_l_acces_sur_ses_porteurs(self, app, scene):
        from Code.carto_access import can_read
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], True, [scene["role_metier"]])
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert can_read(ent, db.session.get(User, scene["porteur"]))
            assert not can_read(ent, db.session.get(User, scene["etranger"]))

    def test_recevoir_le_role_donne_l_acces_sans_repasser_par_l_ecran(self, app, scene):
        """Tout l'intérêt de passer par les rôles : rien à refaire pour le nouveau venu."""
        from Code.carto_access import can_read
        from Code.extensions import db
        from Code.models.models import Entity, User, UserRole
        _regler_acces(app, scene["entity_id"], True, [scene["role_metier"]])
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            nouveau = db.session.get(User, scene["etranger"])
            assert not can_read(ent, nouveau)
            db.session.add(UserRole(user_id=scene["etranger"], role_id=scene["role_metier"]))
            db.session.commit()
            assert can_read(ent, db.session.get(User, scene["etranger"]))
            UserRole.query.filter_by(user_id=scene["etranger"]).delete()
            db.session.commit()

    def test_un_coordinateur_voit_toutes_les_cartos_communes(self, app, scene):
        """Il en règle l'accès et arbitre les propositions : il doit pouvoir l'ouvrir."""
        from Code.carto_access import can_read
        from Code.extensions import db
        from Code.models.models import Entity, User
        autre_coord = _mk_user(app, "t66.coord2@devoptiq.com", "coordinateur")
        _regler_acces(app, scene["entity_id"], True, [scene["role_support"]])
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert can_read(ent, db.session.get(User, autre_coord))
            assert can_read(ent, db.session.get(User, scene["admin"]))

    def test_la_liste_des_entites_inclut_les_cartos_communes(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com")
        res = client.get("/activities/api/entities")
        assert res.status_code == 200
        ligne = next((e for e in res.get_json() if e["id"] == scene["entity_id"]), None)
        assert ligne is not None
        assert ligne["is_shared"] is True
        assert ligne["is_owner"] is False

    def test_une_carto_privee_reste_absente_de_la_liste(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], False)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com")
        res = client.get("/activities/api/entities")
        assert all(e["id"] != scene["entity_id"] for e in res.get_json())


# ══════════════════════════════════════════════════════════════════════════
# 3. Régler l'accès
# ══════════════════════════════════════════════════════════════════════════

class TestReglageDeLAcces:

    def test_l_ecran_liste_les_roles_et_leurs_porteurs(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True, [scene["role_metier"]])
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com")
        res = client.get(f"/cartography/api/access/{scene['entity_id']}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["is_shared"] is True
        metier = next(r for r in data["roles"] if r["id"] == scene["role_metier"])
        assert metier["granted"] is True
        assert metier["holders"] >= 1
        support = next(r for r in data["roles"] if r["id"] == scene["role_support"])
        assert support["granted"] is False

    def test_un_compte_ordinaire_ne_regle_pas_l_acces(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com")
        res = client.post(f"/cartography/api/access/{scene['entity_id']}",
                          json={"is_shared": False, "role_ids": []})
        assert res.status_code == 403
        assert res.get_json()["code"] == "forbidden"

    def test_un_coordinateur_ouvre_et_referme_l_acces(self, app, client, scene):
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com")
        res = client.post(f"/cartography/api/access/{scene['entity_id']}",
                          json={"is_shared": True, "role_ids": [scene["role_support"]]})
        assert res.status_code == 200
        data = res.get_json()
        assert data["is_shared"] is True
        assert data["open_to_all"] is False
        assert [r["id"] for r in data["roles"] if r["granted"]] == [scene["role_support"]]

    def test_repasser_en_prive_efface_les_roles_autorises(self, app, client, scene):
        from Code.models.models import EntityRoleAccess
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com")
        client.post(f"/cartography/api/access/{scene['entity_id']}",
                    json={"is_shared": True, "role_ids": [scene["role_metier"]]})
        client.post(f"/cartography/api/access/{scene['entity_id']}",
                    json={"is_shared": False, "role_ids": []})
        with app.app_context():
            assert EntityRoleAccess.query.filter_by(entity_id=scene["entity_id"]).count() == 0

    def test_un_role_d_une_autre_carto_est_ignore(self, app, client, scene, ids):
        """On ne doit pas pouvoir ouvrir une carto au rôle d'une AUTRE carto."""
        from Code.extensions import db
        from Code.models.models import Role
        with app.app_context():
            intrus = Role.query.filter(Role.entity_id != scene["entity_id"]).first()
            if intrus is None:
                intrus = Role(entity_id=ids["entity_id"], name="T66 Intrus")
                db.session.add(intrus)
                db.session.commit()
            intrus_id = intrus.id
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com")
        res = client.post(f"/cartography/api/access/{scene['entity_id']}",
                          json={"is_shared": True, "role_ids": [intrus_id]})
        assert res.status_code == 200
        assert res.get_json()["open_to_all"] is True   # rien de valide n'a été retenu


# ══════════════════════════════════════════════════════════════════════════
# 4. Écriture : appliquer ou proposer
# ══════════════════════════════════════════════════════════════════════════

class TestEcriture:

    def test_le_proprietaire_ecrit_sur_sa_carto_privee(self, app, scene):
        from Code.carto_access import can_edit, must_propose
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], False)
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert can_edit(ent, db.session.get(User, scene["coordinateur"]))
            assert not must_propose(ent, db.session.get(User, scene["coordinateur"]))

    def test_sur_une_carto_commune_un_compte_ordinaire_propose(self, app, scene):
        from Code.carto_access import can_edit, must_propose
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            porteur = db.session.get(User, scene["porteur"])
            assert not can_edit(ent, porteur)
            # ⚠️ Lire ne donne plus le droit de proposer : c'est ce qui sépare
        # `user` de `champion`. Un porteur de rôle ordinaire CONSULTE.
        assert not must_propose(ent, porteur)

    def test_coordinateur_et_admin_ecrivent_sans_examen(self, app, scene):
        from Code.carto_access import can_edit
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert can_edit(ent, db.session.get(User, scene["coordinateur"]))
            assert can_edit(ent, db.session.get(User, scene["admin"]))

    def test_l_enregistrement_direct_est_refuse_cote_serveur(self, app, client, scene):
        """Le masquage de l'interface n'est pas une sécurité : /api/save refuse aussi."""
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        res = client.post("/cartography/api/save", json={"diagram": DIAGRAM})
        assert res.status_code == 403
        assert res.get_json()["code"] == "must_propose"

    def test_un_coordinateur_enregistre_normalement(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        res = client.post("/cartography/api/save", json={"diagram": DIAGRAM})
        assert res.status_code == 200
        assert res.get_json()["ok"] is True


# ══════════════════════════════════════════════════════════════════════════
# 5. Modifications proposées
# ══════════════════════════════════════════════════════════════════════════

def _diagramme_modifie():
    d = json.loads(json.dumps(DIAGRAM))
    d["shapes"].append({"id": "s3", "type": "process", "label": "Partage Rôle C",
                        "x": 700, "y": 0, "w": 120, "h": 60})
    d["shapes"][0]["label"] = "Partage Rôle A bis"
    d["connections"].append({"fromId": "s2", "toId": "s3", "label": "suite"})
    return d


class TestPropositions:

    def test_proposer_ne_touche_pas_la_carto(self, app, client, scene):
        from Code.extensions import db
        from Code.models.models import Entity
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            avant = db.session.get(Entity, scene["entity_id"]).optiqcarto_data

        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        res = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "title": "Trois activités",
            "message": "J'ajoute la suite du flux.", "diagram": _diagramme_modifie()})
        assert res.status_code == 201

        with app.app_context():
            assert db.session.get(Entity, scene["entity_id"]).optiqcarto_data == avant

    def test_on_ne_propose_pas_sur_une_carto_privee(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], False)
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        res = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": DIAGRAM})
        assert res.status_code == 400
        assert res.get_json()["code"] == "not_shared"

    def test_le_resume_dit_ce_qui_change(self, app, client, scene):
        """L'examinateur doit lire des activités et des flèches, pas du JSON."""
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        detail = client.get(f"/cartography/api/changes/{rid}").get_json()
        resume = detail["summary"]
        assert "Partage Rôle C" in resume["added"]
        assert resume["removed"] == []
        assert {"from": "Partage Rôle A", "to": "Partage Rôle A bis"} in resume["renamed"]
        assert resume["links_added"] == 1
        assert detail["can_review"] is True

    def test_un_compte_ordinaire_ne_voit_que_ses_propres_propositions(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie()})

        autre = _mk_user(app, "t66.autre@devoptiq.com", "user")
        _as(client, autre, "t66.autre@devoptiq.com", scene["entity_id"])
        data = client.get(f"/cartography/api/changes?entity_id={scene['entity_id']}").get_json()
        assert data["can_review"] is False
        assert all(r["is_mine"] for r in data["requests"])

    def test_un_champion_n_arbitre_pas_ses_propres_propositions(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        autre = _mk_user(app, "t66.autre2@devoptiq.com", "user")
        _as(client, autre, "t66.autre2@devoptiq.com", scene["entity_id"])
        assert client.post(f"/cartography/api/changes/{rid}/approve").status_code in (403, 404)

    def test_appliquer_ecrit_sur_la_carto_commune(self, app, client, scene):
        """Appliquée, la modification vaut pour tous : c'est la MÊME ligne d'entité."""
        from Code.extensions import db
        from Code.models.models import Activities, Entity
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        res = client.post(f"/cartography/api/changes/{rid}/approve", json={})
        assert res.status_code == 200

        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            carto = json.loads(ent.optiqcarto_data)
            assert any(s["id"] == "s3" for s in carto["shapes"])
            # Les activités sont dérivées, comme après un enregistrement normal.
            noms = {a.name for a in Activities.query.filter_by(entity_id=ent.id).all()}
            assert "Partage Rôle C" in noms

    def test_une_proposition_ne_se_tranche_qu_une_fois(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        assert client.post(f"/cartography/api/changes/{rid}/reject", json={}).status_code == 200
        assert client.post(f"/cartography/api/changes/{rid}/approve", json={}).status_code == 409

    def test_refuser_laisse_la_carto_intacte(self, app, client, scene):
        from Code.extensions import db
        from Code.models.models import Entity
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            avant = db.session.get(Entity, scene["entity_id"]).optiqcarto_data

        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": {"shapes": [], "connections": []},
        }).get_json()["request"]["id"]

        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        res = client.post(f"/cartography/api/changes/{rid}/reject",
                          json={"comment": "hors sujet"})
        assert res.status_code == 200
        with app.app_context():
            assert db.session.get(Entity, scene["entity_id"]).optiqcarto_data == avant

    def test_l_auteur_retire_sa_proposition_tant_qu_elle_attend(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]
        assert client.delete(f"/cartography/api/changes/{rid}").status_code == 200
        assert client.get(f"/cartography/api/changes/{rid}").status_code == 404

    def test_personne_d_autre_ne_retire_une_proposition(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        assert client.delete(f"/cartography/api/changes/{rid}").status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 6. Ménage
# ══════════════════════════════════════════════════════════════════════════

class TestMenage:

    def test_un_role_supprime_de_la_carte_emporte_son_acces(self, app, scene):
        """Sinon une clé étrangère orpheline bloquerait la suppression du rôle."""
        from Code.extensions import db
        from Code.models.models import EntityRoleAccess, Entity, Role
        from Code.routes.cartography_editor import _sync_carto_to_db

        _regler_acces(app, scene["entity_id"], True, [scene["role_metier"]])
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            # Une carto sans la bande « T66 Métier » : le rôle disparaît.
            sans_bande = json.loads(json.dumps(DIAGRAM))
            sans_bande["bands"] = [{"id": "b9", "label": "T66 Support", "height": 200}]
            _sync_carto_to_db(ent, sans_bande)
            db.session.commit()
            assert Role.query.filter_by(entity_id=ent.id, name="T66 Métier").first() is None
            assert EntityRoleAccess.query.filter_by(role_id=scene["role_metier"]).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# 7. Activer une carto commune
# ══════════════════════════════════════════════════════════════════════════

class TestActivation:

    def test_activer_une_carto_commune_tient_au_rechargement(self, app, client, scene):
        """La page carte a SA propre résolution d'entité active : elle rejetait une
        carto d'un autre propriétaire, et l'écran repartait aussitôt sur une autre."""
        from Code.routes.activities_map import get_active_entity_id
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com")

        res = client.post(f"/activities/api/entities/{scene['entity_id']}/activate")
        assert res.status_code == 200

        with client.session_transaction() as sess:
            assert sess["active_entity_id"] == scene["entity_id"]
            donnees = dict(sess)
        with app.test_request_context():
            from flask import session as fsess
            fsess.update(donnees)
            assert get_active_entity_id() == scene["entity_id"]

    def test_activer_ne_repeint_pas_le_drapeau_du_proprietaire(self, app, client, scene):
        """`is_active` est un reliquat : le poser sur la carto d'un autre compte
        changerait SON entité par défaut."""
        from Code.extensions import db
        from Code.models.models import Entity
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            db.session.get(Entity, scene["entity_id"]).is_active = False
            db.session.commit()

        _as(client, scene["porteur"], "t66.porteur@devoptiq.com")
        client.post(f"/activities/api/entities/{scene['entity_id']}/activate")
        with app.app_context():
            assert db.session.get(Entity, scene["entity_id"]).is_active is False

    def test_une_carto_privee_ne_s_active_pas_chez_un_autre(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], False)
        _as(client, scene["etranger"], "t66.etranger@devoptiq.com")
        res = client.post(f"/activities/api/entities/{scene['entity_id']}/activate")
        assert res.status_code == 404

class TestApercuAvantApres:
    """Un résumé écrit dit « 2 activités déplacées » ; il ne dit pas si le
    résultat tient debout. L'examinateur doit pouvoir REGARDER."""

    @staticmethod
    def _marques(avant, apres):
        from Code.routes.carto_sharing import _marques_du_changement
        return _marques_du_changement(avant, apres)

    def test_le_cadrage_est_commun_aux_deux_images(self, app):
        """⚠️ Deux vignettes recadrées chacune sur son contenu se comparent mal :
        déplacer UNE forme fait paraître que toute la carto a bougé."""
        import re
        from Code.routes.carto_sharing import _cadre_commun, _svg_depuis_diagramme

        avant = {"bands": [{"id": 1, "height": 200, "color": "#abc"}], "bandWidth": 900,
                 "shapes": [{"id": "a", "x": 10, "y": 10, "w": 80, "h": 40},
                            {"id": "b", "x": 200, "y": 10, "w": 80, "h": 40}],
                 "connections": []}
        apres = {"bands": avant["bands"], "bandWidth": 900,
                 "shapes": [dict(avant["shapes"][0]),
                            {"id": "b", "x": 2000, "y": 900, "w": 80, "h": 40}],
                 "connections": []}
        cadre = _cadre_commun(avant, apres)
        with app.app_context():
            va = _svg_depuis_diagramme(avant, cadre=cadre)
            vb = _svg_depuis_diagramme(apres, cadre=cadre)
        vue = lambda svg: re.search(r'viewBox="([^"]+)"', svg).group(1)
        assert vue(va) == vue(vb)

    def test_les_formes_touchees_sont_surlignees_du_bon_cote(self, app):
        """Retiré en rouge sur l'AVANT, ajouté en vert sur l'APRÈS, modifié en
        ambre des deux côtés — on suit l'œil d'une image à l'autre."""
        from Code.routes.carto_sharing import _svg_depuis_diagramme

        avant = {"bands": [], "bandWidth": 500, "connections": [],
                 "shapes": [{"id": "reste", "x": 0, "y": 0, "w": 50, "h": 30},
                            {"id": "part", "x": 90, "y": 0, "w": 50, "h": 30},
                            {"id": "bouge", "x": 180, "y": 0, "w": 50, "h": 30}]}
        apres = {"bands": [], "bandWidth": 500, "connections": [],
                 "shapes": [{"id": "reste", "x": 0, "y": 0, "w": 50, "h": 30},
                            {"id": "bouge", "x": 300, "y": 0, "w": 50, "h": 30},
                            {"id": "neuve", "x": 400, "y": 0, "w": 50, "h": 30}]}
        m_av, m_ap = self._marques(avant, apres)
        assert m_av["part"] == "removed"
        assert m_ap["neuve"] == "added"
        assert m_av["bouge"] == m_ap["bouge"] == "changed"
        assert "reste" not in m_av and "reste" not in m_ap

        with app.app_context():
            va = _svg_depuis_diagramme(avant, marques=m_av)
            vb = _svg_depuis_diagramme(apres, marques=m_ap)
        assert 'stroke="#dc2626"' in va and 'stroke="#dc2626"' not in vb
        assert 'stroke="#16a34a"' in vb and 'stroke="#16a34a"' not in va
        assert 'stroke="#d97706"' in va and 'stroke="#d97706"' in vb

    def test_la_vignette_de_galerie_reste_sans_halo(self, app):
        """Le même moteur sert les deux usages : la galerie ne doit pas hériter
        des couleurs de l'examen."""
        from Code.routes.carto_sharing import _svg_depuis_diagramme

        diag = {"bands": [], "bandWidth": 300, "connections": [],
                "shapes": [{"id": "x", "x": 0, "y": 0, "w": 40, "h": 20}]}
        with app.app_context():
            svg = _svg_depuis_diagramme(diag)
        for couleur in ("#dc2626", "#16a34a", "#d97706"):
            assert couleur not in svg

    def test_l_apercu_est_refuse_a_qui_n_a_rien_a_y_voir(self, app, client):
        """Ni l'auteur ni un arbitre : 404 — comme le reste de l'API."""
        r = client.get("/cartography/api/changes/999999/apercu/avant.svg")
        assert r.status_code in (401, 404)

    def test_seuls_avant_et_apres_sont_acceptes(self, app, client):
        r = client.get("/cartography/api/changes/1/apercu/autrechose.svg")
        assert r.status_code in (401, 404)

class TestApercuEnGrand:
    """Deux défauts signalés à l'usage, tous deux dans l'agrandissement.

    ⚠️ Ils ne se voient QU'À L'ÉCRAN : un empilement CSS et une différence de
    moteur de rendu ne font échouer aucune requête.
    """

    def test_la_loupe_passe_au_dessus_de_la_fenetre_d_examen(self):
        """`.gov-loupe` était à 9600, `.gov-modal` à 10002 : l'agrandissement
        s'ouvrait DERRIÈRE la pop-up et ne se découvrait qu'en la fermant."""
        import io
        import os
        import re

        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin = os.path.join(racine, "static", "optiqcarto", "style.css")
        if not os.path.exists(chemin):
            import pytest
            pytest.skip("feuille de style absente (arbre bytecode)")
        css = io.open(chemin, encoding="utf-8").read()

        def z(selecteur):
            bloc = re.search(re.escape(selecteur) + r"\s*\{(.*?)\}", css, re.S)
            assert bloc, "règle %s introuvable" % selecteur
            val = re.search(r"z-index:\s*(\d+)", bloc.group(1))
            assert val, "pas de z-index dans %s" % selecteur
            return int(val.group(1))

        assert z(".gov-loupe") > z(".gov-modal"), (
            "l'agrandissement doit passer AU-DESSUS de la fenêtre d'examen")

    def test_en_grand_on_charge_le_viewer_pas_la_vignette(self):
        """La vignette SVG sert à COMPARER (légère, cadrée à l'identique) ;
        l'agrandir ne montrerait qu'une reconstitution. En grand, on ouvre le
        viewer d'OptiqCarto, qui rend ce que rend l'éditeur."""
        import io
        import os

        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin = os.path.join(racine, "static", "optiqcarto", "carto_sharing.js")
        if not os.path.exists(chemin):
            import pytest
            pytest.skip("script absent (arbre bytecode)")
        js = io.open(chemin, encoding="utf-8").read()

        debut = js.index("function agrandir(")
        corps = js[debut:debut + 1600]
        assert "/changes/${id}/apercu/${quel}" in corps
        assert "<iframe" in corps
        assert "apercu/${quel}.svg" not in corps, (
            "la loupe ne doit plus agrandir la vignette reconstruite")

    def test_le_diagramme_d_une_proposition_est_servi_tel_quel(self, app, client):
        """Le viewer charge ce JSON : c'est le même format que /api/load, donc
        le même rendu."""
        r = client.get("/cartography/api/changes/999999/diagramme/apres")
        assert r.status_code in (401, 404)

    def test_seuls_avant_et_apres_ouvrent_le_viewer(self, app, client):
        r = client.get("/cartography/changes/1/apercu/autrechose")
        assert r.status_code in (401, 404)


class TestLesQuatrePaliers:
    """Ce que chaque palier peut faire d'une carto commune — le cœur du modèle."""

    def test_un_user_ne_peut_ni_ecrire_ni_proposer(self, app, client, scene):
        """⚠️ Le palier le plus restreint CONSULTE. L'interface le masque, mais
        le masquage n'est pas une sécurité : les deux routes refusent."""
        _regler_acces(app, scene["entity_id"], True, [scene["role_metier"]])
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])

        res = client.post("/cartography/api/save",
                          json={"diagram": DIAGRAM})
        assert res.status_code == 403
        assert res.get_json().get("code") == "lecture_seule", (
            "on ne dit pas « proposez » à quelqu'un qui n'en a pas le droit")

        res = client.post("/cartography/api/changes",
                          json={"entity_id": scene["entity_id"], "diagram": DIAGRAM})
        assert res.status_code == 403

    def test_un_champion_propose_mais_n_enregistre_pas(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True, [])
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])

        res = client.post("/cartography/api/save", json={"diagram": DIAGRAM})
        assert res.status_code == 403
        assert res.get_json().get("code") == "must_propose"

        res = client.post("/cartography/api/changes",
                          json={"entity_id": scene["entity_id"], "diagram": DIAGRAM})
        assert res.status_code in (200, 201), res.get_json()

    def test_un_champion_n_arbitre_pas(self, app, scene):
        from Code.carto_access import can_review
        from Code.extensions import db
        from Code.models.models import Entity, User
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert not can_review(ent, db.session.get(User, scene["champion"]))
            assert can_review(ent, db.session.get(User, scene["coordinateur"]))

    def test_un_champion_ne_regle_pas_l_acces(self, app, scene):
        """Ouvrir une carto à toute l'organisation engage tout le monde : cela
        reste au coordinateur."""
        from Code.carto_access import can_manage_access
        from Code.extensions import db
        from Code.models.models import Entity, User
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert not can_manage_access(ent, db.session.get(User, scene["champion"]))
            assert can_manage_access(ent, db.session.get(User, scene["coordinateur"]))

    def test_l_editeur_s_ouvre_en_lecture_seule_pour_un_user(self, app, scene):
        """⚠️ Refuser seulement à l'enregistrement laisserait un `user`
        travailler dix minutes avant d'apprendre qu'il n'en a pas le droit."""
        from Code.carto_access import access_summary
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], True, [scene["role_metier"]])
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            vu = access_summary(ent, db.session.get(User, scene["porteur"]))
            assert vu["lecture_seule"] is True
            assert vu["can_edit"] is False and vu["must_propose"] is False

            vu = access_summary(ent, db.session.get(User, scene["champion"]))
            assert vu["lecture_seule"] is False and vu["must_propose"] is True

            vu = access_summary(ent, db.session.get(User, scene["coordinateur"]))
            assert vu["lecture_seule"] is False and vu["can_edit"] is True


class TestRepriseDesComptes:
    """Les arbitres d'hier doivent devenir coordinateurs, sans intervention."""

    def test_les_anciens_libelles_sont_repris(self, app):
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import COORDINATOR_STATUS, migrer_anciens_champions

        ids = []
        with app.app_context():
            for i, libelle in enumerate(("champion", "manager",
                                         "Gestionnaire de compétences")):
                u = User(first_name="T66", last_name="Reprise%d" % i,
                         email="t66.reprise%d@devoptiq.com" % i,
                         password="x", status=libelle)
                db.session.add(u)
            db.session.commit()
            # ⚠️ `force` : la reprise s'est déjà jouée au DÉMARRAGE de
            # l'application de test, et elle ne se rejoue pas toute seule (c'est
            # tout l'objet du cas suivant). Sans ce forçage on n'éprouverait
            # plus la reprise, seulement son marqueur.
            migrer_anciens_champions(force=True)
            for i in range(3):
                u = User.query.filter_by(
                    email="t66.reprise%d@devoptiq.com" % i).first()
                ids.append(u.id)
                assert u.status == COORDINATOR_STATUS, (
                    "%s aurait dû devenir coordinateur" % u.status)
        try:
            # Idempotente : un second passage ne change plus rien.
            with app.app_context():
                assert migrer_anciens_champions(force=True) == 0
        finally:
            with app.app_context():
                for i in ids:
                    u = db.session.get(User, i)
                    if u:
                        db.session.delete(u)
                db.session.commit()

    def test_un_user_n_est_pas_promu(self, app):
        """La reprise monte les ARBITRES d'un cran, pas tout le monde."""
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import migrer_anciens_champions

        with app.app_context():
            u = User(first_name="T66", last_name="Simple",
                     email="t66.simple@devoptiq.com", password="x", status="user")
            db.session.add(u)
            db.session.commit()
            uid = u.id
        try:
            with app.app_context():
                migrer_anciens_champions(force=True)
                assert db.session.get(User, uid).status == "user"
        finally:
            with app.app_context():
                u = db.session.get(User, uid)
                if u:
                    db.session.delete(u)
                    db.session.commit()

    def test_un_champion_NOUVEAU_n_est_jamais_promu_au_redemarrage(self, app):
        """⚠️ Le cas qui manquait, et qui vidait le palier de sa raison d'être.

        La reprise lit « champion » au sens ANCIEN — l'arbitre. Jouée à CHAQUE
        démarrage, elle promouvait `coordinateur` tout champion créé depuis :
        on nommait quelqu'un champion pour qu'il propose sans valider, et le
        redéploiement suivant lui donnait le droit de valider. Le palier
        n'existait donc que jusqu'au prochain démarrage.

        Un marqueur en base (`app_settings`) tranche : la reprise appartient au
        passé, le mot ne veut plus dire que sa nouvelle définition.
        """
        from Code.extensions import db
        from Code.models.models import User
        from Code.permissions import (CHAMPION_STATUS, migrer_anciens_champions,
                                      niveau_status, NIVEAU_CHAMPION)

        with app.app_context():
            u = User(first_name="T66", last_name="Neuf",
                     email="t66.champion.neuf@devoptiq.com",
                     password="x", status=CHAMPION_STATUS)
            db.session.add(u)
            db.session.commit()
            uid = u.id
        try:
            with app.app_context():
                # Trois « démarrages » de plus : la base a déjà été reprise.
                for _ in range(3):
                    assert migrer_anciens_champions() == 0
                u = db.session.get(User, uid)
                assert u.status == CHAMPION_STATUS, (
                    "un champion nommé APRÈS la reprise est devenu « %s »"
                    % u.status)
                assert niveau_status(u.status) == NIVEAU_CHAMPION
        finally:
            with app.app_context():
                u = db.session.get(User, uid)
                if u:
                    db.session.delete(u)
                    db.session.commit()

    def test_le_marqueur_de_reprise_est_pose_en_base(self, app):
        """Un drapeau en mémoire repartirait à zéro à chaque démarrage, et à
        chaque instance : le marqueur doit vivre dans la base migrée."""
        from Code.extensions import db
        from Code.models.models import AppSetting
        from Code.permissions import CLE_REPRISE

        with app.app_context():
            assert db.session.get(AppSetting, CLE_REPRISE) is not None, (
                "la reprise doit laisser sa trace en base, sinon elle se rejoue")

    def test_l_outil_d_inventaire_predit_exactement_la_reprise(self):
        """`tools/db/etat_statuts.py` sert à décider AVANT de déployer sur une
        instance en service : il annonce le palier que chaque compte aura.

        ⚠️ S'il prédit autre chose que ce que le code fera, l'inventaire ment —
        et c'est sur cet inventaire qu'on décide de toucher, ou non, aux comptes
        d'un client. Les deux implémentations doivent donc s'accorder sur TOUS
        les libellés rencontrés en base.
        """
        import importlib.util
        import os

        import pytest as _pytest
        from Code.permissions import (COORDINATOR_STATUS, is_admin_status,
                                      is_coordinator_status, norm_status)

        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin = os.path.join(racine, "tools", "db", "etat_statuts.py")
        if not os.path.exists(chemin):
            # `tools/` est exclu de l'image : ce cas n'a rien à vérifier là-bas.
            _pytest.skip("tools/ absent (arbre d'image)")
        spec = importlib.util.spec_from_file_location("etat_statuts", chemin)
        outil = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(outil)

        libelles = [
            "admin", "administrateur", "Administrator", "ADMIN",
            "champion", "Champion",
            "coordinateur", "Coordinateur", "coordinator",
            "manager", "Manager",
            "Gestionnaire de compétences", "gestionnaire de comp",
            "Competency Manager", "Skills Manager",
            "user", "User", "rh", "", None, "n'importe quoi",
        ]
        for libelle in libelles:
            # Ce que l'APPLICATION fera : la reprise monte l'arbitre d'hier au
            # palier coordinateur, le reste garde son libellé.
            if is_admin_status(libelle):
                attendu = "admin"
            elif norm_status(libelle) == "champion" or is_coordinator_status(libelle):
                # ⚠️ « champion » compris : sur une base d'AVANT la bascule, le
                # mot désigne l'arbitre. C'est tout l'objet de la reprise.
                attendu = COORDINATOR_STATUS
            else:
                attendu = "user"
            assert outil.palier_apres(libelle) == attendu, (
                "« %s » : l'outil annonce %s, le code fera %s"
                % (libelle, outil.palier_apres(libelle), attendu))

        # Et la normalisation doit être la MÊME des deux côtés.
        for libelle in libelles:
            assert outil.norm(libelle) == norm_status(libelle), libelle

    def test_l_outil_d_inventaire_n_ecrit_rien(self):
        """Il tourne sur la base d'un CLIENT : il ne doit pas pouvoir écrire."""
        import io as _io
        import os
        import pytest as _pytest
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin = os.path.join(racine, "tools", "db", "etat_statuts.py")
        if not os.path.exists(chemin):
            _pytest.skip("tools/ absent (arbre d'image)")
        src = _io.open(chemin, encoding="utf-8").read()
        assert "set_session(readonly=True)" in src, (
            "la connexion doit être ouverte en lecture seule")
        assert "commit()" not in src, "l'outil ne doit rien valider"
        for verbe in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "DROP "):
            assert verbe not in src.upper(), (
                "l'outil contient « %s » — il doit rester en lecture"
                % verbe.strip())
