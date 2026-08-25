# tests/test_51_entity_share.py
"""
Partage d'une entité entre comptes — /activities/api/entities/<id>/share

Une entité n'appartient qu'à son propriétaire (Entity.get_active est strict sur
owner_id) : partager signifie en DÉPOSER UNE COPIE chez chaque destinataire.
Réservé aux administrateurs.
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

def test_un_non_admin_ne_peut_pas_lister_les_destinataires(app, client, cast):
    _as(client, cast["simple"], "share.simple@devoptiq.com")
    res = client.get(f"/activities/api/entities/{cast['entity_id']}/share/candidates")
    assert res.status_code == 403


def test_un_non_admin_ne_peut_pas_partager(app, client, cast):
    _as(client, cast["simple"], "share.simple@devoptiq.com")
    res = client.post(f"/activities/api/entities/{cast['entity_id']}/share",
                      json={"user_ids": [cast["dest1"]]})
    assert res.status_code == 403


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
