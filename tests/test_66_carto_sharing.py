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
        from Code.models.models import EntityStatusAccess
        ent = db.session.get(Entity, scene["entity_id"])
        if ent is not None:
            ent.is_shared = False
            ent.statuts_regles = False
            EntityRoleAccess.query.filter_by(entity_id=ent.id).delete()
            EntityStatusAccess.query.filter_by(entity_id=ent.id).delete()
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

    def test_un_role_ne_de_l_ailleurs_ouvre_la_carto(self, app, client, scene, ids):
        """Un rôle appartient à l'entreprise : celui né sur une autre carto
        ouvre celle-ci comme les siens."""
        from Code.extensions import db
        from Code.models.models import Role
        with app.app_context():
            ailleurs = Role.query.filter(Role.entity_id != scene["entity_id"]).first()
            if ailleurs is None:
                ailleurs = Role(entity_id=ids["entity_id"], name="T66 Ailleurs")
                db.session.add(ailleurs)
                db.session.commit()
            ailleurs_id = ailleurs.id
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com")
        res = client.post(f"/cartography/api/access/{scene['entity_id']}",
                          json={"is_shared": True, "role_ids": [ailleurs_id]})
        assert res.status_code == 200
        d = res.get_json()
        assert d["open_to_all"] is False
        assert any(r["id"] == ailleurs_id and r["granted"] for r in d["roles"])


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

    def test_un_role_retire_de_la_carte_ne_part_que_s_il_ne_sert_plus(self, app, scene):
        """Le rôle est commun à l'entreprise : retirer sa bande ne l'efface
        pas tant qu'il porte quelque chose. Celui que plus personne ne tient
        part, et son accès avec lui — sinon une clé étrangère orpheline
        bloquerait la suppression."""
        from Code.extensions import db
        from Code.models.models import EntityRoleAccess, Entity, Role
        from Code.routes.cartography_editor import _sync_carto_to_db

        _regler_acces(app, scene["entity_id"], True,
                      [scene["role_metier"], scene["role_support"]])
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            sans_bande = json.loads(json.dumps(DIAGRAM))
            sans_bande["bands"] = [{"id": "b9", "label": "T66 Autre", "height": 200}]
            _sync_carto_to_db(ent, sans_bande)
            db.session.commit()
            # « T66 Métier » a des titulaires : il reste, et son accès aussi.
            assert db.session.get(Role, scene["role_metier"]) is not None
            assert EntityRoleAccess.query.filter_by(
                role_id=scene["role_metier"]).count() == 1
            # « T66 Support » ne sert plus à personne : il part avec son accès.
            assert db.session.get(Role, scene["role_support"]) is None
            assert EntityRoleAccess.query.filter_by(
                role_id=scene["role_support"]).count() == 0


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

def _source(*chemin):
    """Le texte d'un fichier statique — ou un saut si l'arbre n'en a pas
    (image bytecode-only : voir tools/repet_image.sh)."""
    import io
    import os
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fichier = os.path.join(racine, *chemin)
    if not os.path.exists(fichier):
        pytest.skip("%s absent (arbre bytecode)" % "/".join(chemin))
    return io.open(fichier, encoding="utf-8").read()


def _corps_de(source, signature, longueur=1600):
    debut = source.index(signature)
    return source[debut:debut + longueur]


class TestApercuAvantApres:
    """Un résumé écrit dit « 2 activités déplacées » ; il ne dit pas si le
    résultat tient debout. L'examinateur doit pouvoir REGARDER — les vraies
    cartos, pas des schémas reconstruits (static/js/carto_comparaison.js)."""

    def test_les_formes_touchees_sont_marquees_du_bon_cote(self):
        """Retiré sur l'AVANT, ajouté sur l'APRÈS, modifié des deux côtés — on
        suit l'œil d'une carte à l'autre."""
        from Code.routes.carto_sharing import _marques_du_changement

        avant = {"shapes": [{"id": "reste", "x": 0, "y": 0, "w": 50, "h": 30},
                            {"id": "part", "x": 90, "y": 0, "w": 50, "h": 30},
                            {"id": "bouge", "x": 180, "y": 0, "w": 50, "h": 30}]}
        apres = {"shapes": [{"id": "reste", "x": 0, "y": 0, "w": 50, "h": 30},
                            {"id": "bouge", "x": 300, "y": 0, "w": 50, "h": 30},
                            {"id": "neuve", "x": 400, "y": 0, "w": 50, "h": 30}]}
        m_av, m_ap = _marques_du_changement(avant, apres)
        assert m_av["part"] == "removed"
        assert m_ap["neuve"] == "added"
        assert m_av["bouge"] == m_ap["bouge"] == "changed"
        assert "reste" not in m_av and "reste" not in m_ap

    def test_chaque_cote_entoure_ses_propres_formes(self):
        """Le composant lit les marques DU côté qu'il dessine."""
        js = _source("static", "js", "carto_comparaison.js")
        corps = _corps_de(js, "function surligner(")
        assert "(o.marques || {})[q]" in corps
        assert "data-shape-fill" in corps

    def test_le_cadrage_est_commun_aux_deux_cartos(self):
        """⚠️ Deux cartes cadrées chacune sur son contenu se comparent mal :
        déplacer UNE forme fait paraître que toute la carto a bougé. Le
        composant réunit les bornes des deux et les impose aux deux viewers."""
        js = _source("static", "js", "carto_comparaison.js")
        corps = _corps_de(js, "function cadrerEnsemble(")
        assert "Math.min(" in corps and "Math.max(" in corps
        assert ".fit(b)" in corps
        editeur = _source("static", "optiqcarto", "editor.js")
        assert "window.cartoViewport" in editeur
        assert "fit: (bornes) => fitView(bornes," in editeur

    def test_la_vignette_de_galerie_reste_sans_halo(self, app):
        """La galerie de la page Partage garde son SVG, sans couleurs d'examen."""
        from Code.routes.carto_sharing import _svg_depuis_diagramme

        diag = {"bands": [], "bandWidth": 300, "connections": [],
                "shapes": [{"id": "x", "x": 0, "y": 0, "w": 40, "h": 20}]}
        with app.app_context():
            svg = _svg_depuis_diagramme(diag)
        for couleur in ("#dc2626", "#16a34a", "#d97706"):
            assert couleur not in svg

    def test_l_apercu_est_refuse_a_qui_n_a_rien_a_y_voir(self, app, client):
        """Ni l'auteur ni un arbitre : 404 — comme le reste de l'API."""
        r = client.get("/cartography/changes/999999/apercu/avant")
        assert r.status_code in (401, 404)


class TestApercuEnGrand:
    """Le grand format : les MÊMES viewers, agrandis — et une bascule avant /
    après instantanée, qui garde le zoom.

    ⚠️ Ces défauts ne se voient QU'À L'ÉCRAN (un empilement CSS, un iframe
    recréé) : aucune requête n'échoue. D'où des contrôles sur les sources.
    """

    def test_agrandir_ne_recharge_rien(self):
        """Chaque bascule recréait un iframe — une demi-seconde à recharger la
        carto à chaque fois. On agrandit désormais en CSS les deux viewers déjà
        chargés : aucune iframe n'est créée en grand format."""
        js = _source("static", "js", "carto_comparaison.js")
        for signature in ("function agrandir(", "function montrer("):
            corps = _corps_de(js, signature, 900)
            assert "iframe" not in corps.lower().split("function", 2)[1], signature
            assert "createElement" not in corps.split("function", 2)[1], signature

    def test_la_bascule_garde_le_cadrage(self):
        """Comparer, c'est regarder le MÊME endroit des deux cartes."""
        js = _source("static", "js", "carto_comparaison.js")
        corps = _corps_de(js, "function montrer(", 900)
        assert ".set(api(avant).get())" in corps

    def test_la_vue_masquee_garde_sa_taille(self):
        """`display: none` retirerait sa taille au viewer masqué : il ne se
        cadrerait plus, et la bascule le montrerait vide."""
        css = _source("static", "carto_comparaison.css")
        assert "visibility: hidden" in css
        bloc = css[css.index('.cmp[data-mode="loupe"][data-vue="avant"]'):]
        bloc = bloc[:bloc.index("}")]
        assert "display: none" not in bloc

    def test_le_grand_format_couvre_la_fenetre(self):
        """⚠️ Une animation en `transform` conservée après coup fait de la fiche
        d'examen de l'éditeur le repère des éléments fixes : le grand format y
        restait enfermé. Elle ne conserve plus rien une fois jouée."""
        css = _source("static", "carto_comparaison.css")
        bloc = css[css.index('.cmp[data-mode="loupe"] {'):]
        bloc = bloc[:bloc.index("}")]
        assert "position: fixed" in bloc
        style = _source("static", "optiqcarto", "style.css")
        assert "#review-modal .gov-card { animation-fill-mode: backwards; }" in style

    def test_un_clic_dans_la_comparaison_ne_quitte_pas_la_page(self):
        """Les viewers de la comparaison préviennent leur page à chaque clic sur
        une forme (`shape-click`), comme celui de la page Carte — qui part alors
        vers la fiche de l'activité. Vérifié à l'écran : sans ce filtre, cliquer
        « Clarify RFI Scope » en grand format quittait la page Carte."""
        js = _source("static", "js", "activities_map.js")
        debut = js.index('window.addEventListener("message", function(e) {')
        corps = js[debut:debut + 1400]
        assert '#cex iframe' in corps
        assert corps.index('#cex iframe') < corps.index('shape-click')

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

    @pytest.mark.parametrize("outil", ["etat_statuts.py", "etat_entites.py"])
    def test_l_outil_d_inventaire_n_ecrit_rien(self, outil):
        """Il tourne sur la base d'un CLIENT : il ne doit pas pouvoir écrire."""
        import io as _io
        import os
        import pytest as _pytest
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin = os.path.join(racine, "tools", "db", outil)
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

    def test_l_inventaire_des_roles_normalise_comme_l_application(self):
        """Il annonce quels rôles seront RÉUNIS : s'il ne rapproche pas les
        noms de la même façon que `roles_communs`, il annonce autre chose que
        ce qui se passera au démarrage."""
        import importlib.util
        import os

        import pytest as _pytest
        from Code.roles_communs import normalise

        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chemin = os.path.join(racine, "tools", "db", "etat_entites.py")
        if not os.path.exists(chemin):
            _pytest.skip("tools/ absent (arbre d'image)")
        spec = importlib.util.spec_from_file_location("etat_entites", chemin)
        outil = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(outil)
        for nom in ("Qualité", "qualite", "  Qualité  ", "Chef d'atelier",
                    "Market Analysis / Communication", "Support  client",
                    "chef-d-atelier", "", None):
            assert outil.norm(nom) == normalise(nom), nom


class TestLaMatriceDesAcces:
    """« Qui ouvre quelles cartos » — un rôle en ligne, une carto en colonne.

    Le réglage carto par carto existait déjà ; ce qui manquait, c'est la vue
    d'ensemble et les deux gestes qui vont avec : cocher une colonne (tous les
    rôles sur cette carto), cocher une ligne (ce rôle sur toutes les cartos).
    """

    URL = "/cartography/api/access/matrice"

    @pytest.fixture()
    def carto(self, app, scene):
        """Sa PROPRE carto et ses propres rôles : le décor du module est
        remanié par les tests de ménage (une bande retirée emporte son rôle),
        et une matrice bâtie dessus dépendrait de l'ordre d'exécution."""
        from Code.extensions import db
        from Code.models.models import Entity, EntityRoleAccess, Role
        with app.app_context():
            ent = Entity.query.filter_by(name="Carto matrice T66").first()
            if ent is None:
                ent = Entity(name="Carto matrice T66", owner_id=scene["coordinateur"])
                db.session.add(ent)
                db.session.commit()
            ent.is_shared = False
            roles = {}
            for nom in ("T66M Un", "T66M Deux"):
                r = Role.query.filter_by(entity_id=ent.id, name=nom).first()
                if r is None:
                    r = Role(entity_id=ent.id, name=nom)
                    db.session.add(r)
                    db.session.commit()
                roles[nom] = r.id
            EntityRoleAccess.query.filter_by(entity_id=ent.id).delete()
            db.session.commit()
            decor = {"id": ent.id, "un": roles["T66M Un"], "deux": roles["T66M Deux"]}
        yield decor
        with app.app_context():
            from Code.extensions import db
            from Code.models.models import EntityStatusAccess
            EntityStatusAccess.query.filter_by(entity_id=decor["id"]).delete()
            EntityRoleAccess.query.filter_by(entity_id=decor["id"]).delete()
            Role.query.filter(Role.id.in_([decor["un"], decor["deux"]])).delete(
                synchronize_session=False)
            Entity.query.filter_by(id=decor["id"]).delete()
            db.session.commit()

    def test_un_user_ne_voit_pas_la_matrice(self, app, client, scene):
        """Réservée à qui règle l'accès : le masquage du bouton ne suffit pas."""
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        assert client.get(self.URL).status_code == 403
        r = client.post(self.URL, json={"cases": [
            {"role_id": scene["role_metier"], "entity_id": scene["entity_id"], "on": True}]})
        assert r.status_code == 403

    def test_chaque_role_n_a_qu_une_ligne(self, app, client, scene, carto):
        """Un rôle est commun à l'entreprise : une ligne, quel que soit le
        nombre de cartos qui en portent la bande."""
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        d = client.get(self.URL).get_json()
        assert carto["id"] in [c["id"] for c in d["cartos"]]
        ids = [r["id"] for r in d["roles"]]
        assert ids.count(carto["un"]) == 1
        assert len(ids) == len(set(ids))

    def test_cocher_une_case_rend_la_carto_commune(self, app, client, scene, carto):
        """⚠️ Une carto PRIVÉE ignore les rôles : y donner un accès sans la
        rendre commune enregistrerait un réglage qui ne produit rien."""
        from Code.extensions import db
        from Code.models.models import Entity
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        d = client.post(self.URL, json={"cases": [
            {"role_id": carto["un"], "entity_id": carto["id"], "on": True}]}).get_json()
        assert carto["id"] in d["rendues_communes"]
        with app.app_context():
            assert db.session.get(Entity, carto["id"]).is_shared is True
        ligne = next(r for r in d["roles"] if r["id"] == carto["un"])
        assert carto["id"] in ligne["cartos"]

    def test_une_colonne_se_coche_d_un_coup(self, app, client, scene, carto):
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        d = client.get(self.URL).get_json()
        cases = [{"role_id": r["id"], "entity_id": carto["id"], "on": True}
                 for r in d["roles"]]
        d = client.post(self.URL, json={"cases": cases}).get_json()
        col = next(c for c in d["cartos"] if c["id"] == carto["id"])
        assert col["n_roles"] == len(d["roles"]) and col["ouverte_a_tous"] is False

    def test_on_n_ecrit_que_les_cases_envoyees(self, app, client, scene, carto):
        """⚠️ Jamais la table entière : une case absente de l'envoi ne doit pas
        fermer un accès que personne n'a décidé de fermer."""
        _regler_acces(app, carto["id"], True, [carto["un"], carto["deux"]])
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        d = client.post(self.URL, json={"cases": [
            {"role_id": carto["un"], "entity_id": carto["id"], "on": False}]}).get_json()
        deux = next(r for r in d["roles"] if r["id"] == carto["deux"])
        un = next(r for r in d["roles"] if r["id"] == carto["un"])
        assert carto["id"] in deux["cartos"]
        assert carto["id"] not in un["cartos"]

    def test_une_carto_hors_de_portee_est_ignoree(self, app, client, scene, carto):
        """Un identifiant venu du navigateur n'ouvre jamais une carto qu'on ne
        règle pas : la case est écartée en silence, rien n'est écrit."""
        from Code.extensions import db
        from Code.models.models import Entity, EntityRoleAccess
        with app.app_context():
            autre = Entity.query.filter_by(name="Carto d'un autre T66").first()
            if autre is None:
                autre = Entity(name="Carto d'un autre T66", owner_id=scene["etranger"])
                db.session.add(autre)
                db.session.commit()
            autre_id = autre.id
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        client.post(self.URL, json={"cases": [
            {"role_id": carto["un"], "entity_id": autre_id, "on": True}]})
        with app.app_context():
            assert EntityRoleAccess.query.filter_by(entity_id=autre_id).count() == 0
            Entity.query.filter_by(id=autre_id).delete()
            db.session.commit()

    def test_le_bouton_n_est_offert_qu_a_qui_regle_l_acces(self, app, client, scene):
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        html = client.get("/activities/map").get_data(as_text=True)
        assert 'id="btn-carto-acces"' not in html
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", scene["entity_id"])
        html = client.get("/activities/map").get_data(as_text=True)
        assert 'id="btn-carto-acces"' in html and 'id="cacc"' in html


class TestLAccesParStatut:
    """La deuxième matrice de la fenêtre d'accès : un PALIER par ligne.

    Un rôle dit ce qu'on fait dans l'organisation ; un statut dit ce qu'on est
    dans l'application. Les deux ouvrent une carto, et l'écran les sépare.
    """

    URL = "/cartography/api/access/matrice"

    @pytest.fixture()
    def carto(self, app, scene):
        """Une carto d'un AUTRE compte : chez soi, on entre toujours.

        ⚠️ Son propre champion : `TestRepriseDesComptes` rejoue la bascule des
        anciens libellés (force=True) et promeut tout champion en coordinateur.
        Celui du décor commun n'en est donc plus un quand on arrive ici.
        """
        from Code.extensions import db
        from Code.models.models import (Entity, EntityRoleAccess,
                                        EntityStatusAccess, Role)
        champion = _mk_user(app, "t66s.champion@devoptiq.com", "champion")
        with app.app_context():
            ent = Entity.query.filter_by(name="Carto statuts T66").first()
            if ent is None:
                ent = Entity(name="Carto statuts T66", owner_id=scene["etranger"])
                db.session.add(ent)
                db.session.commit()
            ent.owner_id = scene["etranger"]
            ent.is_shared = True
            ent.statuts_regles = False
            r = Role.query.filter_by(entity_id=ent.id, name="T66S Fermé").first()
            if r is None:
                r = Role(entity_id=ent.id, name="T66S Fermé")
                db.session.add(r)
                db.session.commit()
            # Un rôle que PERSONNE ne tient : sans cela, la carto reste ouverte
            # à tous et le palier ne déciderait de rien.
            EntityStatusAccess.query.filter_by(entity_id=ent.id).delete()
            EntityRoleAccess.query.filter_by(entity_id=ent.id).delete()
            db.session.add(EntityRoleAccess(entity_id=ent.id, role_id=r.id))
            db.session.commit()
            decor = {"id": ent.id, "role": r.id, "champion": champion}
        yield decor
        with app.app_context():
            EntityStatusAccess.query.filter_by(entity_id=decor["id"]).delete()
            EntityRoleAccess.query.filter_by(entity_id=decor["id"]).delete()
            Role.query.filter_by(id=decor["role"]).delete()
            Entity.query.filter_by(id=decor["id"]).delete()
            db.session.commit()

    def _lit(self, app, entity_id, user_id):
        from Code.carto_access import can_read
        from Code.extensions import db
        from Code.models.models import Entity, User
        with app.app_context():
            return can_read(db.session.get(Entity, entity_id),
                            db.session.get(User, user_id))

    def test_par_defaut_le_coordinateur_et_l_admin_entrent(self, app, scene, carto):
        """Le défaut demandé : coordinateur et administrateur sur toutes les
        cartos, les autres paliers uniquement par leur rôle."""
        assert self._lit(app, carto["id"], scene["coordinateur"])
        assert self._lit(app, carto["id"], scene["admin"])
        assert not self._lit(app, carto["id"], carto["champion"])
        assert not self._lit(app, carto["id"], scene["porteur"])

    def test_cocher_un_palier_ouvre_la_carto(self, app, client, scene, carto):
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        r = client.post(self.URL, json={"cases_statut": [
            {"statut": "champion", "entity_id": carto["id"], "on": True}]})
        assert r.status_code == 200
        assert self._lit(app, carto["id"], carto["champion"])
        assert not self._lit(app, carto["id"], scene["porteur"])

    def test_decocher_un_palier_la_referme(self, app, client, scene, carto):
        _as(client, scene["admin"], "t66.admin@devoptiq.com", carto["id"])
        client.post(self.URL, json={"cases_statut": [
            {"statut": "coordinateur", "entity_id": carto["id"], "on": False}]})
        assert not self._lit(app, carto["id"], scene["coordinateur"])
        assert self._lit(app, carto["id"], scene["admin"])

    def test_l_administrateur_ne_se_decoche_pas(self, app, client, scene, carto):
        """⚠️ Se retirer une carto qu'on ne possède pas, ce serait la perdre de
        la fenêtre d'accès — donc plus aucun écran d'où se la rendre."""
        _as(client, scene["admin"], "t66.admin@devoptiq.com", carto["id"])
        d = client.post(self.URL, json={"cases_statut": [
            {"statut": "admin", "entity_id": carto["id"], "on": False}]}).get_json()
        ligne = next(s for s in d["statuts"] if s["cle"] == "admin")
        assert carto["id"] in ligne["cartos"] and ligne["verrou"] is True
        assert self._lit(app, carto["id"], scene["admin"])

    def test_la_matrice_porte_les_quatre_paliers(self, app, client, scene, carto):
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        d = client.get(self.URL).get_json()
        assert [s["cle"] for s in d["statuts"]] == ["user", "champion",
                                                    "coordinateur", "admin"]
        coches = {s["cle"] for s in d["statuts"] if carto["id"] in s["cartos"]}
        assert coches == {"coordinateur", "admin"}

    def test_on_n_ecrit_que_les_cases_envoyees(self, app, client, scene, carto):
        """⚠️ Le premier réglage doit d'abord GRAVER le défaut : sans cela,
        décocher un palier rouvrirait l'autre."""
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        d = client.post(self.URL, json={"cases_statut": [
            {"statut": "user", "entity_id": carto["id"], "on": True}]}).get_json()
        coches = {s["cle"] for s in d["statuts"] if carto["id"] in s["cartos"]}
        assert coches == {"user", "coordinateur", "admin"}

    def test_cocher_un_palier_rend_la_carto_commune(self, app, client, scene, carto):
        """Une carto privée ignore ses réglages d'accès : la cocher la rend
        commune, comme pour un rôle."""
        from Code.extensions import db
        from Code.models.models import Entity
        with app.app_context():
            ent = db.session.get(Entity, carto["id"])
            ent.is_shared = False
            ent.owner_id = scene["coordinateur"]
            db.session.commit()
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        d = client.post(self.URL, json={"cases_statut": [
            {"statut": "champion", "entity_id": carto["id"], "on": True}]}).get_json()
        assert carto["id"] in d["rendues_communes"]

    def test_un_palier_inconnu_est_ignore(self, app, client, scene, carto):
        _as(client, scene["coordinateur"], "t66.coord@devoptiq.com", carto["id"])
        r = client.post(self.URL, json={"cases_statut": [
            {"statut": "patron", "entity_id": carto["id"], "on": True}]})
        assert r.status_code == 200
        assert [s["cle"] for s in r.get_json()["statuts"]] == [
            "user", "champion", "coordinateur", "admin"]

    def test_un_user_ne_regle_pas_les_statuts(self, app, client, scene, carto):
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", carto["id"])
        r = client.post(self.URL, json={"cases_statut": [
            {"statut": "user", "entity_id": carto["id"], "on": True}]})
        assert r.status_code == 403
        assert not self._lit(app, carto["id"], scene["porteur"])


class TestLaReunionDesRoles:
    """`fusionner_doublons()` — la reprise qui ramène une base en service au
    modèle « un rôle par intitulé ».

    ⚠️ Elle n'était jouée par aucun test : sur staging, elle tombait à l'import
    (`Code/routes/time_extra.py` redéclarait cinq tables de `models.py`), le
    message partait dans les journaux et les doublons restaient.
    """

    def test_le_doublon_rend_tout_ce_qu_il_portait(self, app, scene):
        from Code.extensions import db
        from Code.models.models import (Activities, Role, UserRole,
                                        activity_roles)
        from Code.roles_communs import fusionner_doublons

        with app.app_context():
            garde = Role(entity_id=scene["entity_id"], name="T66F Qualité")
            doublon = Role(entity_id=scene["entity_id"], name="t66f  qualite")
            db.session.add_all([garde, doublon])
            db.session.commit()
            acte = Activities(name="T66F activité", entity_id=scene["entity_id"])
            db.session.add(acte)
            db.session.commit()
            db.session.add(UserRole(user_id=scene["porteur"], role_id=garde.id))
            db.session.add(UserRole(user_id=scene["etranger"], role_id=doublon.id))
            db.session.execute(activity_roles.insert().values(
                activity_id=acte.id, role_id=doublon.id, status="Garant"))
            db.session.commit()
            garde_id, doublon_id, acte_id = garde.id, doublon.id, acte.id

        with app.app_context():
            assert fusionner_doublons(force=True) >= 1

        with app.app_context():
            # ⚠️ Le rôle gardé est celui qui a le PLUS de titulaires : ici les
            # deux en ont un, donc le plus ancien (id le plus petit).
            assert db.session.get(Role, doublon_id) is None
            assert db.session.get(Role, garde_id) is not None
            titulaires = {ur.user_id for ur in
                          UserRole.query.filter_by(role_id=garde_id).all()}
            assert titulaires == {scene["porteur"], scene["etranger"]}
            lien = db.session.execute(db.select(activity_roles).where(
                activity_roles.c.activity_id == acte_id)).mappings().all()
            assert [l["role_id"] for l in lien] == [garde_id]

            # Ménage
            UserRole.query.filter_by(role_id=garde_id).delete()
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.role_id == garde_id))
            Role.query.filter_by(id=garde_id).delete()
            Activities.query.filter_by(id=acte_id).delete()
            db.session.commit()

    def test_elle_ne_se_joue_qu_une_fois(self, app):
        """Le marqueur vit en BASE : une instance qui redémarre, se duplique ou
        se redéploie doit lire la même réponse."""
        from Code.extensions import db
        from Code.models.models import AppSetting
        from Code.roles_communs import CLE_FUSION, fusionner_doublons

        with app.app_context():
            if db.session.get(AppSetting, CLE_FUSION) is None:
                db.session.add(AppSetting(key=CLE_FUSION, value="1"))
                db.session.commit()
            assert fusionner_doublons() == 0
