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
  * sur une carto commune, un compte ordinaire PROPOSE, un champion ou un
    administrateur applique — et ce qui est appliqué vaut pour tout le monde,
    puisque c'est la même ligne.
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

    champion = _mk_user(app, "t66.champion@devoptiq.com", "champion")
    admin = _mk_user(app, "t66.admin@devoptiq.com", "administrateur")
    porteur = _mk_user(app, "t66.porteur@devoptiq.com", "user")
    etranger = _mk_user(app, "t66.etranger@devoptiq.com", "user")

    with app.app_context():
        ent = Entity.query.filter_by(name="Carto commune T66").first()
        if ent is None:
            ent = Entity(name="Carto commune T66", owner_id=champion)
            db.session.add(ent)
        ent.owner_id = champion
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
        if not UserRole.query.filter_by(user_id=porteur, role_id=roles["T66 Métier"]).first():
            db.session.add(UserRole(user_id=porteur, role_id=roles["T66 Métier"]))
        UserRole.query.filter_by(user_id=etranger).delete()
        EntityRoleAccess.query.filter_by(entity_id=ent.id).delete()
        db.session.commit()

        return {"entity_id": ent.id, "champion": champion, "admin": admin,
                "porteur": porteur, "etranger": etranger,
                "role_metier": roles["T66 Métier"],
                "role_support": roles["T66 Support"]}


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

    def test_champion_reconnu_sous_ses_anciens_libelles(self):
        """Une instance déjà en service porte l'ancien mot : personne ne perd ses droits."""
        from Code.permissions import is_champion_status
        for valeur in ("champion", "manager", "Gestionnaire de compétences",
                       "gestionnaire de comp", "Competency Manager"):
            assert is_champion_status(valeur), valeur

    def test_rh_et_user_ne_sont_pas_champions(self):
        from Code.permissions import is_champion_status, is_admin_status
        for valeur in ("user", "rh", "", None):
            assert not is_champion_status(valeur)
            assert not is_admin_status(valeur)

    def test_la_valeur_canonique_tient_dans_la_colonne(self):
        """users.status est un VARCHAR(20) : un libellé long y arriverait tronqué."""
        from Code.permissions import CHAMPION_STATUS
        assert len(CHAMPION_STATUS) <= 20


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
            assert can_read(ent, db.session.get(User, scene["champion"]))
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

    def test_un_champion_voit_toutes_les_cartos_communes(self, app, scene):
        """Il en règle l'accès et arbitre les propositions : il doit pouvoir l'ouvrir."""
        from Code.carto_access import can_read
        from Code.extensions import db
        from Code.models.models import Entity, User
        autre_champion = _mk_user(app, "t66.champion2@devoptiq.com", "champion")
        _regler_acces(app, scene["entity_id"], True, [scene["role_support"]])
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert can_read(ent, db.session.get(User, autre_champion))
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
        _as(client, scene["champion"], "t66.champion@devoptiq.com")
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

    def test_un_champion_ouvre_et_referme_l_acces(self, app, client, scene):
        _as(client, scene["champion"], "t66.champion@devoptiq.com")
        res = client.post(f"/cartography/api/access/{scene['entity_id']}",
                          json={"is_shared": True, "role_ids": [scene["role_support"]]})
        assert res.status_code == 200
        data = res.get_json()
        assert data["is_shared"] is True
        assert data["open_to_all"] is False
        assert [r["id"] for r in data["roles"] if r["granted"]] == [scene["role_support"]]

    def test_repasser_en_prive_efface_les_roles_autorises(self, app, client, scene):
        from Code.models.models import EntityRoleAccess
        _as(client, scene["champion"], "t66.champion@devoptiq.com")
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
        _as(client, scene["champion"], "t66.champion@devoptiq.com")
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
            assert can_edit(ent, db.session.get(User, scene["champion"]))
            assert not must_propose(ent, db.session.get(User, scene["champion"]))

    def test_sur_une_carto_commune_un_compte_ordinaire_propose(self, app, scene):
        from Code.carto_access import can_edit, must_propose
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            porteur = db.session.get(User, scene["porteur"])
            assert not can_edit(ent, porteur)
            assert must_propose(ent, porteur)

    def test_champion_et_admin_ecrivent_sans_examen(self, app, scene):
        from Code.carto_access import can_edit
        from Code.extensions import db
        from Code.models.models import Entity, User
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            ent = db.session.get(Entity, scene["entity_id"])
            assert can_edit(ent, db.session.get(User, scene["champion"]))
            assert can_edit(ent, db.session.get(User, scene["admin"]))

    def test_l_enregistrement_direct_est_refuse_cote_serveur(self, app, client, scene):
        """Le masquage de l'interface n'est pas une sécurité : /api/save refuse aussi."""
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        res = client.post("/cartography/api/save", json={"diagram": DIAGRAM})
        assert res.status_code == 403
        assert res.get_json()["code"] == "must_propose"

    def test_un_champion_enregistre_normalement(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
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

        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        res = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "title": "Trois activités",
            "message": "J'ajoute la suite du flux.", "diagram": _diagramme_modifie()})
        assert res.status_code == 201

        with app.app_context():
            assert db.session.get(Entity, scene["entity_id"]).optiqcarto_data == avant

    def test_on_ne_propose_pas_sur_une_carto_privee(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], False)
        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        res = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": DIAGRAM})
        assert res.status_code == 400
        assert res.get_json()["code"] == "not_shared"

    def test_le_resume_dit_ce_qui_change(self, app, client, scene):
        """L'examinateur doit lire des activités et des flèches, pas du JSON."""
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        detail = client.get(f"/cartography/api/changes/{rid}").get_json()
        resume = detail["summary"]
        assert "Partage Rôle C" in resume["added"]
        assert resume["removed"] == []
        assert {"from": "Partage Rôle A", "to": "Partage Rôle A bis"} in resume["renamed"]
        assert resume["links_added"] == 1
        assert detail["can_review"] is True

    def test_un_compte_ordinaire_ne_voit_que_ses_propres_propositions(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie()})

        autre = _mk_user(app, "t66.autre@devoptiq.com", "user")
        _as(client, autre, "t66.autre@devoptiq.com", scene["entity_id"])
        data = client.get(f"/cartography/api/changes?entity_id={scene['entity_id']}").get_json()
        assert data["can_review"] is False
        assert all(r["is_mine"] for r in data["requests"])

    def test_un_compte_ordinaire_n_arbitre_pas(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
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
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
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
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        assert client.post(f"/cartography/api/changes/{rid}/reject", json={}).status_code == 200
        assert client.post(f"/cartography/api/changes/{rid}/approve", json={}).status_code == 409

    def test_refuser_laisse_la_carto_intacte(self, app, client, scene):
        from Code.extensions import db
        from Code.models.models import Entity
        _regler_acces(app, scene["entity_id"], True)
        with app.app_context():
            avant = db.session.get(Entity, scene["entity_id"]).optiqcarto_data

        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": {"shapes": [], "connections": []},
        }).get_json()["request"]["id"]

        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
        res = client.post(f"/cartography/api/changes/{rid}/reject",
                          json={"comment": "hors sujet"})
        assert res.status_code == 200
        with app.app_context():
            assert db.session.get(Entity, scene["entity_id"]).optiqcarto_data == avant

    def test_l_auteur_retire_sa_proposition_tant_qu_elle_attend(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]
        assert client.delete(f"/cartography/api/changes/{rid}").status_code == 200
        assert client.get(f"/cartography/api/changes/{rid}").status_code == 404

    def test_personne_d_autre_ne_retire_une_proposition(self, app, client, scene):
        _regler_acces(app, scene["entity_id"], True)
        _as(client, scene["porteur"], "t66.porteur@devoptiq.com", scene["entity_id"])
        rid = client.post("/cartography/api/changes", json={
            "entity_id": scene["entity_id"], "diagram": _diagramme_modifie(),
        }).get_json()["request"]["id"]

        _as(client, scene["champion"], "t66.champion@devoptiq.com", scene["entity_id"])
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
