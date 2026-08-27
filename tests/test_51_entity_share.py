# tests/test_51_entity_share.py
"""
Partage d'une entité entre comptes — /activities/api/entities/<id>/share

Une entité n'appartient qu'à son propriétaire (Entity.get_active est strict sur
owner_id) : partager signifie en DÉPOSER UNE COPIE chez chaque destinataire.

Tout le monde peut partager. Ce qui change avec le statut, c'est le consentement
du destinataire : un administrateur dépose directement, un compte ordinaire ne
fait que proposer (EntityShareOffer) — la copie n'existe qu'après acceptation.
"""
import json

import pytest
from werkzeug.security import generate_password_hash

pytestmark = pytest.mark.activities_map


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


DIAGRAM = {
    "shapes": [
        {"id": "p1", "type": "process", "label": "Partage Activité A",
         "x": 100, "y": 0, "w": 120, "h": 60},
        {"id": "p2", "type": "process", "label": "Partage Activité B",
         "x": 400, "y": 0, "w": 120, "h": 60},
    ],
    "bands": [{"id": "b1", "label": "Bande Partage", "height": 200}],
    "connections": [{"fromId": "p1", "toId": "p2", "label": "flux"}],
}


def _mk_user(app, email, status):
    from Code.models.models import User
    from Code.extensions import db
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(first_name="P", last_name=email.split("@")[0], email=email,
                     password=generate_password_hash("Test1234!"), status=status)
            db.session.add(u)
        u.status = status
        db.session.commit()
        return u.id


def _as(client, user_id, email):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_email"] = email


@pytest.fixture(scope="module")
def cast(app):
    from Code.models.models import Entity
    from Code.extensions import db
    owner = _mk_user(app, "share.admin@devoptiq.com", "administrateur")
    dest1 = _mk_user(app, "share.dest1@devoptiq.com", "user")
    dest2 = _mk_user(app, "share.dest2@devoptiq.com", "user")
    simple = _mk_user(app, "share.simple@devoptiq.com", "user")
    with app.app_context():
        ent = Entity.query.filter_by(name="Entité à partager", owner_id=owner).first()
        if ent is None:
            ent = Entity(name="Entité à partager", description="source",
                         owner_id=owner, vsdx_filename="src.vsdx")
            db.session.add(ent)
        ent.optiqcarto_data = json.dumps(DIAGRAM, ensure_ascii=False)
        db.session.commit()
        eid = ent.id
    return {"owner": owner, "dest1": dest1, "dest2": dest2,
            "simple": simple, "entity_id": eid}


# ── Droits ────────────────────────────────────────────────────────────────────

def test_un_non_proprietaire_ne_voit_pas_les_destinataires(app, client, cast):
    """Le partage est ouvert à tous, mais seulement pour SES entités."""
    _as(client, cast["simple"], "share.simple@devoptiq.com")
    res = client.get(f"/activities/api/entities/{cast['entity_id']}/share/candidates")
    assert res.status_code == 404


def test_un_non_proprietaire_ne_peut_pas_partager(app, client, cast):
    _as(client, cast["simple"], "share.simple@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [cast["dest1"]]})
    assert res.status_code == 404


def test_un_admin_ne_partage_que_ses_propres_entites(app, client, cast):
    """L'entité doit appartenir à l'admin connecté, pas à un autre compte."""
    autre_admin = _mk_user(app, "share.admin2@devoptiq.com", "administrateur")
    _as(client, autre_admin, "share.admin2@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [cast["dest1"]]})
    assert res.status_code == 404


# ── Liste des destinataires ───────────────────────────────────────────────────

def test_les_candidats_excluent_le_proprietaire(app, client, cast):
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.get(f"/activities/api/entities/{cast['entity_id']}/share/candidates")
    assert res.status_code == 200
    body = res.get_json()
    assert body["entity"]["name"] == "Entité à partager"
    assert cast["owner"] not in [u["id"] for u in body["users"]]
    assert cast["dest1"] in [u["id"] for u in body["users"]]


# ── Partage ───────────────────────────────────────────────────────────────────

def test_le_partage_depose_une_copie_complete(app, client, cast):
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [cast["dest1"], cast["dest2"]]})
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert len(body["shared"]) == 2
    assert body["failed"] == []

    with app.app_context():
        from Code.models.models import Entity, Activities
        for item in body["shared"]:
            copie = Entity.query.get(item["entity_id"])
            assert copie.owner_id == item["user_id"]
            assert copie.name == "Entité à partager"
            assert copie.vsdx_filename == "src.vsdx"
            assert json.loads(copie.optiqcarto_data) == DIAGRAM
            # les activités sont dérivées comme après un import Visio
            noms = {a.name for a in Activities.query.filter_by(entity_id=copie.id).all()}
            assert {"Partage Activité A", "Partage Activité B"} <= noms
        # l'originale n'a pas bougé
        src = Entity.query.get(cast["entity_id"])
        assert src.owner_id == cast["owner"]


def test_le_second_partage_ne_remplace_pas_le_premier(app, client, cast):
    """Deux envois au même compte → deux entités, la seconde suffixée."""
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [cast["dest1"]]})
    nom = res.get_json()["shared"][0]["entity_name"]
    assert nom == "Entité à partager (2)"
    with app.app_context():
        from Code.models.models import Entity
        n = Entity.query.filter_by(owner_id=cast["dest1"]).count()
        assert n >= 2


def test_le_destinataire_voit_son_entite(app, client, cast):
    _as(client, cast["dest2"], "share.dest2@devoptiq.com")
    res = client.get("/activities/api/entities")
    noms = [e["name"] for e in res.get_json()]
    assert "Entité à partager" in noms


def test_les_candidats_signalent_une_copie_deja_deposee(app, client, cast):
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    body = client.get(f"/activities/api/entities/{cast['entity_id']}/share/candidates").get_json()
    dest2 = next(u for u in body["users"] if u["id"] == cast["dest2"])
    assert dest2["already_has"] is True


# ── Robustesse ────────────────────────────────────────────────────────────────

def test_partage_sans_destinataire(app, client, cast):
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": []})
    assert res.status_code == 400


def test_partage_a_soi_meme_ignore(app, client, cast):
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [cast["owner"]]})
    assert res.status_code == 400


def test_partage_vers_un_compte_inexistant(app, client, cast):
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [999999]})
    assert res.status_code == 200
    body = res.get_json()
    assert body["shared"] == []
    assert len(body["failed"]) == 1


# ── Partage par un compte NON admin : proposition, puis consentement ──────────

@pytest.fixture(scope="module")
def offreur(app):
    """Un compte ordinaire, propriétaire de sa propre entité."""
    from Code.models.models import Entity
    from Code.extensions import db
    uid = _mk_user(app, "share.offreur@devoptiq.com", "user")
    with app.app_context():
        ent = Entity.query.filter_by(name="Carto proposée", owner_id=uid).first()
        if ent is None:
            ent = Entity(name="Carto proposée", description="proposée",
                         owner_id=uid, vsdx_filename="offre.vsdx")
            db.session.add(ent)
        ent.optiqcarto_data = json.dumps(DIAGRAM, ensure_ascii=False)
        db.session.commit()
        return {"user_id": uid, "entity_id": ent.id}


def _offres_en_attente(app, user_id):
    from Code.models.models import EntityShareOffer
    with app.app_context():
        return EntityShareOffer.query.filter_by(to_user_id=user_id, status='pending').all()


def test_un_compte_ordinaire_peut_lister_les_destinataires(app, client, offreur):
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    res = client.get(f"/activities/api/entities/{offreur['entity_id']}/share/candidates")
    assert res.status_code == 200
    body = res.get_json()
    assert body["direct"] is False          # il PROPOSE, il ne dépose pas
    assert offreur["user_id"] not in [u["id"] for u in body["users"]]


def test_un_admin_a_le_depot_direct(app, client, cast):
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    body = client.get(
        f"/activities/api/entities/{cast['entity_id']}/share/candidates").get_json()
    assert body["direct"] is True


def test_le_partage_non_admin_ne_cree_rien_tout_de_suite(app, client, offreur, cast):
    from Code.models.models import Entity
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    res = client.post(f"/activities/api/entities/{offreur['entity_id']}/share",
                      json={"user_ids": [cast["dest1"]]})
    assert res.status_code == 200
    body = res.get_json()
    assert body["direct"] is False
    assert body["shared"] == []
    assert len(body["pending"]) == 1

    with app.app_context():
        assert Entity.query.filter_by(owner_id=cast["dest1"], name="Carto proposée").first() is None
    assert any(o.entity_name == "Carto proposée" for o in _offres_en_attente(app, cast["dest1"]))


def test_renvoyer_la_meme_proposition_n_empile_pas(app, client, offreur, cast):
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    client.post(f"/activities/api/entities/{offreur['entity_id']}/share",
                json={"user_ids": [cast["dest1"]]})
    offres = [o for o in _offres_en_attente(app, cast["dest1"])
              if o.entity_name == "Carto proposée"]
    assert len(offres) == 1


def test_le_destinataire_voit_la_proposition(app, client, offreur, cast):
    _as(client, cast["dest1"], "share.dest1@devoptiq.com")
    body = client.get("/activities/api/share/offers").get_json()
    proposee = [o for o in body["offers"] if o["entity_name"] == "Carto proposée"]
    assert len(proposee) == 1
    assert proposee[0]["from"]


def test_refuser_ne_cree_aucune_entite(app, client, offreur, cast):
    from Code.models.models import Entity, EntityShareOffer
    _as(client, cast["dest1"], "share.dest1@devoptiq.com")
    offre_id = [o for o in client.get("/activities/api/share/offers").get_json()["offers"]
                if o["entity_name"] == "Carto proposée"][0]["id"]

    res = client.post(f"/activities/api/share/offers/{offre_id}/respond",
                      json={"action": "decline"})
    assert res.status_code == 200
    assert res.get_json()["action"] == "declined"

    with app.app_context():
        assert Entity.query.filter_by(owner_id=cast["dest1"], name="Carto proposée").first() is None
        assert EntityShareOffer.query.get(offre_id).status == "declined"
    # et la proposition disparaît de la liste
    restantes = client.get("/activities/api/share/offers").get_json()["offers"]
    assert all(o["id"] != offre_id for o in restantes)


def test_repondre_deux_fois_est_refuse(app, client, offreur, cast):
    from Code.models.models import EntityShareOffer
    with app.app_context():
        offre = (EntityShareOffer.query
                 .filter_by(to_user_id=cast["dest1"], status="declined").first())
        offre_id = offre.id
    _as(client, cast["dest1"], "share.dest1@devoptiq.com")
    res = client.post(f"/activities/api/share/offers/{offre_id}/respond",
                      json={"action": "accept"})
    assert res.status_code == 409


def test_accepter_cree_l_entite_et_ses_activites(app, client, offreur, cast):
    from Code.models.models import Entity, Activities
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    client.post(f"/activities/api/entities/{offreur['entity_id']}/share",
                json={"user_ids": [cast["dest2"]]})

    _as(client, cast["dest2"], "share.dest2@devoptiq.com")
    offre_id = [o for o in client.get("/activities/api/share/offers").get_json()["offers"]
                if o["entity_name"] == "Carto proposée"][0]["id"]
    res = client.post(f"/activities/api/share/offers/{offre_id}/respond",
                      json={"action": "accept"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["action"] == "accepted"

    with app.app_context():
        copie = Entity.query.get(body["entity_id"])
        assert copie.owner_id == cast["dest2"]
        assert copie.vsdx_filename == "offre.vsdx"
        noms = {a.name for a in Activities.query.filter_by(entity_id=copie.id).all()}
        assert {"Partage Activité A", "Partage Activité B"} <= noms


def test_on_ne_repond_pas_a_la_proposition_d_un_autre(app, client, offreur, cast):
    from Code.models.models import EntityShareOffer
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    client.post(f"/activities/api/entities/{offreur['entity_id']}/share",
                json={"user_ids": [cast["dest1"]]})
    with app.app_context():
        offre_id = (EntityShareOffer.query
                    .filter_by(to_user_id=cast["dest1"], status="pending").first().id)

    _as(client, cast["dest2"], "share.dest2@devoptiq.com")
    res = client.post(f"/activities/api/share/offers/{offre_id}/respond",
                      json={"action": "accept"})
    assert res.status_code == 404


def test_action_invalide_refusee(app, client, offreur, cast):
    from Code.models.models import EntityShareOffer
    with app.app_context():
        offre_id = (EntityShareOffer.query
                    .filter_by(to_user_id=cast["dest1"], status="pending").first().id)
    _as(client, cast["dest1"], "share.dest1@devoptiq.com")
    res = client.post(f"/activities/api/share/offers/{offre_id}/respond",
                      json={"action": "peut-etre"})
    assert res.status_code == 400


def test_les_candidats_signalent_une_proposition_en_attente(app, client, offreur, cast):
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    body = client.get(
        f"/activities/api/entities/{offreur['entity_id']}/share/candidates").get_json()
    dest1 = next(u for u in body["users"] if u["id"] == cast["dest1"])
    assert dest1["pending"] is True


def test_les_offres_exigent_une_session(app, client):
    with client.session_transaction() as sess:
        sess.pop("user_id", None)
    assert client.get("/activities/api/share/offers").status_code == 401


# ── Le destinataire possède déjà cette entité ────────────────────────────────

DIAGRAM_ANCIEN = {
    "shapes": [
        {"id": "p1", "type": "process", "label": "Partage Activité A",
         "x": 100, "y": 0, "w": 120, "h": 60},
        {"id": "p9", "type": "process", "label": "Activité disparue",
         "x": 700, "y": 0, "w": 120, "h": 60},
    ],
    "bands": [{"id": "b1", "label": "Bande Partage", "height": 200}],
    "connections": [],
}


@pytest.fixture(scope="module")
def jumeau(app):
    """Un compte qui possède déjà « Carto proposée », dans une version plus ancienne."""
    from Code.models.models import Entity
    from Code.extensions import db
    from Code.routes.cartography_editor import _sync_carto_to_db
    uid = _mk_user(app, "share.jumeau@devoptiq.com", "user")
    with app.app_context():
        ent = Entity.query.filter_by(name="Carto proposée", owner_id=uid).first()
        if ent is None:
            ent = Entity(name="Carto proposée", owner_id=uid)
            db.session.add(ent)
        ent.optiqcarto_data = json.dumps(DIAGRAM_ANCIEN, ensure_ascii=False)
        db.session.commit()
        _sync_carto_to_db(ent, DIAGRAM_ANCIEN)
        db.session.commit()
        return {"user_id": uid, "entity_id": ent.id}


def _offre_pour(client, email, user_id, offreur, nom="Carto proposée"):
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    client.post(f"/activities/api/entities/{offreur['entity_id']}/share",
                json={"user_ids": [user_id]})
    _as(client, user_id, email)
    offres = client.get("/activities/api/share/offers").get_json()["offers"]
    return next(o for o in offres if o["entity_name"] == nom)


def test_l_offre_signale_l_entite_du_meme_nom_et_l_ecart(app, client, offreur, jumeau):
    offre = _offre_pour(client, "share.jumeau@devoptiq.com", jumeau["user_id"], offreur)
    assert offre["existing"] is not None
    assert offre["existing"]["id"] == jumeau["entity_id"]
    assert offre["existing"]["differs"] is True


def test_mettre_a_jour_remplace_la_carto_sans_creer_d_entite(app, client, offreur, jumeau):
    from Code.models.models import Entity, Activities
    offre = _offre_pour(client, "share.jumeau@devoptiq.com", jumeau["user_id"], offreur)

    with app.app_context():
        avant = Entity.query.filter_by(owner_id=jumeau["user_id"]).count()

    res = client.post(f"/activities/api/share/offers/{offre['id']}/respond",
                      json={"action": "update"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["action"] == "updated"
    assert body["entity_id"] == jumeau["entity_id"]

    with app.app_context():
        # aucune entité de plus : c'est la sienne qui a changé
        assert Entity.query.filter_by(owner_id=jumeau["user_id"]).count() == avant
        cible = Entity.query.get(jumeau["entity_id"])
        assert json.loads(cible.optiqcarto_data) == DIAGRAM
        noms = {a.name for a in Activities.query.filter_by(entity_id=cible.id).all()}
        assert {"Partage Activité A", "Partage Activité B"} <= noms
        assert "Activité disparue" not in noms


def test_une_carto_identique_est_signalee_comme_telle(app, client, offreur, jumeau):
    """Après la mise à jour, la même proposition n'a plus d'écart à annoncer."""
    offre = _offre_pour(client, "share.jumeau@devoptiq.com", jumeau["user_id"], offreur)
    assert offre["existing"]["differs"] is False


def test_mettre_a_jour_sans_entite_du_meme_nom_est_refuse(app, client, offreur, cast):
    """Le destinataire n'a rien de ce nom : il n'y a rien à mettre à jour."""
    from Code.models.models import Entity
    from Code.extensions import db
    neuf = _mk_user(app, "share.sansjumeau@devoptiq.com", "user")
    with app.app_context():
        for e in Entity.query.filter_by(owner_id=neuf).all():
            db.session.delete(e)
        db.session.commit()

    offre = _offre_pour(client, "share.sansjumeau@devoptiq.com", neuf, offreur)
    res = client.post(f"/activities/api/share/offers/{offre['id']}/respond",
                      json={"action": "update"})
    assert res.status_code == 400


# ── L'admin choisit : dépôt d'autorité ou proposition ────────────────────────

def test_un_admin_peut_demander_l_accord(app, client, cast):
    """Avec mode=offer, l'admin ne dépose plus : il propose, comme les autres."""
    from Code.models.models import EntityShareOffer
    receveur = _mk_user(app, "share.accord@devoptiq.com", "user")
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [receveur], "mode": "offer"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["direct"] is False
    assert body["shared"] == []
    assert len(body["pending"]) == 1
    with app.app_context():
        from Code.models.models import Entity
        assert Entity.query.filter_by(owner_id=receveur).count() == 0
        assert EntityShareOffer.query.filter_by(
            to_user_id=receveur, status='pending').count() == 1


def test_un_compte_ordinaire_ne_peut_pas_forcer(app, client, offreur, cast):
    """mode=direct depuis un compte non admin reste une simple proposition."""
    receveur = _mk_user(app, "share.pasforce@devoptiq.com", "user")
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    res = client.post(f"/activities/api/entities/{offreur['entity_id']}/share",
                      json={"user_ids": [receveur], "mode": "direct"})
    body = res.get_json()
    assert body["direct"] is False
    assert body["shared"] == []
    assert len(body["pending"]) == 1


def test_un_depot_d_autorite_laisse_une_notification(app, client, cast):
    from Code.models.models import Entity
    receveur = _mk_user(app, "share.notifie@devoptiq.com", "user")
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [receveur], "mode": "direct"})
    assert res.get_json()["direct"] is True

    with app.app_context():
        assert Entity.query.filter_by(owner_id=receveur).count() == 1

    _as(client, receveur, "share.notifie@devoptiq.com")
    offres = client.get("/activities/api/share/offers").get_json()["offers"]
    assert len(offres) == 1
    notice = offres[0]
    assert notice["kind"] == "notice"
    assert notice["entity_name"] == "Entité à partager"
    assert notice["from"]
    return notice


def test_une_notification_s_acquitte_et_disparait(app, client, cast):
    receveur = _mk_user(app, "share.acquitte@devoptiq.com", "user")
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                json={"user_ids": [receveur], "mode": "direct"})

    _as(client, receveur, "share.acquitte@devoptiq.com")
    notice = client.get("/activities/api/share/offers").get_json()["offers"][0]
    res = client.post(f"/activities/api/share/offers/{notice['id']}/respond",
                      json={"action": "acknowledge"})
    assert res.status_code == 200
    assert res.get_json()["action"] == "acknowledged"
    assert client.get("/activities/api/share/offers").get_json()["offers"] == []


def test_on_n_accepte_pas_une_notification(app, client, cast):
    """L'entité est déjà là : accepter n'aurait aucun sens (et ferait un doublon)."""
    receveur = _mk_user(app, "share.refusnotice@devoptiq.com", "user")
    _as(client, cast["owner"], "share.admin@devoptiq.com")
    client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                json={"user_ids": [receveur], "mode": "direct"})

    _as(client, receveur, "share.refusnotice@devoptiq.com")
    notice = client.get("/activities/api/share/offers").get_json()["offers"][0]
    res = client.post(f"/activities/api/share/offers/{notice['id']}/respond",
                      json={"action": "accept"})
    assert res.status_code == 409


def test_on_n_acquitte_pas_une_proposition(app, client, offreur, cast):
    receveur = _mk_user(app, "share.pasacquit@devoptiq.com", "user")
    _as(client, offreur["user_id"], "share.offreur@devoptiq.com")
    client.post(f"/activities/api/entities/{offreur['entity_id']}/share",
                json={"user_ids": [receveur]})

    _as(client, receveur, "share.pasacquit@devoptiq.com")
    offre = client.get("/activities/api/share/offers").get_json()["offers"][0]
    assert offre["kind"] == "offer"
    res = client.post(f"/activities/api/share/offers/{offre['id']}/respond",
                      json={"action": "acknowledge"})
    assert res.status_code == 400
