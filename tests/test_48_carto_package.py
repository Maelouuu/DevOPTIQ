# tests/test_48_carto_package.py
"""
Paquet de cartographie (.optiqcarto) — /cartography/api/export & /api/import

Ce paquet sert à porter une carto CORRIGÉE À LA MAIN d'un compte à l'autre :
redonner le .vsdx d'origine ré-introduirait les défauts d'import que
l'utilisateur vient justement de reprendre. On vérifie donc surtout que le
diagramme ressort à l'identique et que l'entité est bien recréée côté cible.
"""
import io
import json

import pytest

pytestmark = pytest.mark.cartography_editor


# Le client de test est partagé par TOUTE la suite (fixture de portée session).
# Ces tests changent de compte connecté : sans restauration, les modules
# suivants héritent d'une session non-admin et échouent.
@pytest.fixture(scope='module', autouse=True)
def _restaurer_la_session(app, client, ids):
    yield
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email='test@devoptiq.com').first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['user_email'] = umail
        sess['active_entity_id'] = ids['entity_id']


DIAGRAM = {
    "shapes": [
        {"id": "s1", "type": "process", "label": "Réception RFQ",
         "x": 100, "y": 0, "w": 120, "h": 60},
        {"id": "s2", "type": "process", "label": "Chiffrage",
         "x": 400, "y": 0, "w": 120, "h": 60},
        {"id": "s3", "type": "decision", "label": "B1/B5",
         "x": 300, "y": 0, "w": 60, "h": 60},
    ],
    "bands": [{"id": "b1", "label": "Commerce", "height": 200}],
    "connections": [
        # deux branches d'une même fourche : même point de départ, tronc commun
        {"id": 901, "fromId": "s1", "toId": "s2", "label": "offre",
         "fromPortDir": "right", "toPortDir": "left", "fromPortT": 0.5,
         "customPath": [{"x": 220, "y": 30}, {"x": 320, "y": 30}, {"x": 400, "y": 30}],
         "bundleId": "f0", "trunkFrom": 1},
        {"id": 902, "fromId": "s1", "toId": "s3", "label": "",
         "fromPortDir": "right", "toPortDir": "left", "fromPortT": 0.5,
         "customPath": [{"x": 220, "y": 30}, {"x": 320, "y": 30}, {"x": 300, "y": 30}],
         "bundleId": "f0", "trunkFrom": 1},
    ],
    "bandWidth": 1400,
}


def _login(client, app, email):
    with app.app_context():
        from Code.models.models import User
        user = User.query.filter_by(email=email).first()
        uid, umail = user.id, user.email
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_email"] = umail
        sess.pop("active_entity_id", None)
    return uid


@pytest.fixture(scope="module")
def source_entity(app, ids):
    """Entité de départ (le compte qui a corrigé la carto) avec un diagramme."""
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        entity = Entity.query.get(ids["entity_id"])
        entity.owner_id = ids["user_id"]
        entity.vsdx_filename = "Map_RFQ.vsdx"
        entity.optiqcarto_data = json.dumps(DIAGRAM, ensure_ascii=False)
        db.session.commit()
        return {"id": entity.id, "name": entity.name}


@pytest.fixture(scope="module")
def target_user(app):
    """Second compte : celui à qui on remet le fichier."""
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        from werkzeug.security import generate_password_hash
        email = "cible.paquet@devoptiq.com"
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                first_name="Cible", last_name="Paquet", email=email,
                password=generate_password_hash("TestPass123!"), status="user",
            )
            db.session.add(user)
            db.session.commit()
        return {"id": user.id, "email": user.email}


# ── Export ────────────────────────────────────────────────────────────────────

def test_export_renvoie_un_paquet_complet(app, client, ids, source_entity):
    _login(client, app, "test@devoptiq.com")
    with client.session_transaction() as sess:
        sess["active_entity_id"] = source_entity["id"]

    res = client.get("/cartography/api/export")
    assert res.status_code == 200
    assert "attachment" in res.headers.get("Content-Disposition", "")
    assert ".optiqcarto" in res.headers.get("Content-Disposition", "")

    pkg = json.loads(res.data.decode("utf-8"))
    assert pkg["format"] == "optiqcarto/entity"
    assert pkg["entity"]["name"] == source_entity["name"]
    assert pkg["entity"]["vsdx_filename"] == "Map_RFQ.vsdx"
    assert pkg["diagram"] == DIAGRAM


def test_export_sans_carto_renvoie_404(app, client, ids, source_entity):
    _login(client, app, "test@devoptiq.com")
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        vide = Entity(name="Entité sans carto", owner_id=ids["user_id"])
        db.session.add(vide)
        db.session.commit()
        vide_id = vide.id
    with client.session_transaction() as sess:
        sess["active_entity_id"] = vide_id

    res = client.get("/cartography/api/export")
    assert res.status_code == 404


def test_export_refuse_une_entite_d_un_autre_compte(app, client, source_entity, target_user):
    _login(client, app, target_user["email"])
    res = client.get(f"/cartography/api/export?entity_id={source_entity['id']}")
    assert res.status_code == 400  # aucune entité active pour ce compte


# ── Import ────────────────────────────────────────────────────────────────────

def _upload(client, payload, filename="carto.optiqcarto", **form):
    data = {"file": (io.BytesIO(json.dumps(payload).encode("utf-8")), filename)}
    data.update(form)
    return client.post("/cartography/api/import", data=data,
                       content_type="multipart/form-data")


def test_import_recree_entite_et_carto_sur_un_autre_compte(app, client, source_entity, target_user):
    # 1. le compte source exporte
    _login(client, app, "test@devoptiq.com")
    with client.session_transaction() as sess:
        sess["active_entity_id"] = source_entity["id"]
    pkg = json.loads(client.get("/cartography/api/export").data.decode("utf-8"))

    # 2. le compte cible importe le fichier
    uid = _login(client, app, target_user["email"])
    res = _upload(client, pkg)
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True and body["created"] is True
    assert body["counts"]["shapes"] == 3
    assert body["counts"]["connections"] == 2
    assert body["redirect_url"] == "/cartography/editor"

    new_id = body["entity"]["id"]
    assert new_id != source_entity["id"]

    with app.app_context():
        from Code.models.models import Entity, Activities
        entity = Entity.query.get(new_id)
        assert entity.owner_id == uid
        assert entity.vsdx_filename == "Map_RFQ.vsdx"
        # le diagramme est identique au bit près : c'est tout l'intérêt du paquet
        assert json.loads(entity.optiqcarto_data) == DIAGRAM
        # les activités ont été dérivées comme après un import Visio
        noms = {a.name for a in Activities.query.filter_by(entity_id=new_id).all()}
        assert {"Réception RFQ", "Chiffrage"} <= noms

    # 3. l'entité importée est devenue l'entité courante
    with client.session_transaction() as sess:
        assert sess["active_entity_id"] == new_id


def test_import_preserve_les_multiliens(app, client, target_user):
    """Le tronc partagé d'une fourche doit survivre au transport."""
    _login(client, app, target_user["email"])
    res = _upload(client, {"format": "optiqcarto/entity", "version": 1,
                           "entity": {"name": "Fourche"}, "diagram": DIAGRAM})
    conns = None
    with app.app_context():
        from Code.models.models import Entity
        entity = Entity.query.get(res.get_json()["entity"]["id"])
        conns = json.loads(entity.optiqcarto_data)["connections"]
    a, b = conns[0], conns[1]
    assert a["bundleId"] == b["bundleId"] == "f0"
    assert a["customPath"][0] == b["customPath"][0]
    assert a["customPath"][1] == b["customPath"][1]


def test_import_ne_reutilise_pas_un_nom_deja_pris(app, client, target_user):
    _login(client, app, target_user["email"])
    pkg = {"format": "optiqcarto/entity", "version": 1,
           "entity": {"name": "Carto Homonyme"}, "diagram": DIAGRAM}
    first = _upload(client, pkg).get_json()
    second = _upload(client, pkg).get_json()
    assert first["entity"]["name"] == "Carto Homonyme"
    assert second["entity"]["name"] == "Carto Homonyme (2)"
    assert first["entity"]["id"] != second["entity"]["id"]


def test_import_accepte_un_diagramme_brut(app, client, target_user):
    """Le JSON renvoyé par /api/load (sans enveloppe) doit aussi passer."""
    _login(client, app, target_user["email"])
    res = _upload(client, DIAGRAM, filename="brut.json", name="Depuis JSON brut")
    assert res.status_code == 200
    assert res.get_json()["entity"]["name"] == "Depuis JSON brut"


def test_import_remplace_une_entite_existante(app, client, target_user):
    _login(client, app, target_user["email"])
    cible = _upload(client, {"format": "optiqcarto/entity", "version": 1,
                             "entity": {"name": "À remplacer"},
                             "diagram": {"shapes": [], "bands": [], "connections": []}}).get_json()
    eid = cible["entity"]["id"]

    res = _upload(client, {"format": "optiqcarto/entity", "version": 1,
                           "entity": {"name": "ignoré"}, "diagram": DIAGRAM},
                  entity_id=str(eid))
    body = res.get_json()
    assert body["created"] is False
    assert body["entity"]["id"] == eid
    with app.app_context():
        from Code.models.models import Entity
        assert len(json.loads(Entity.query.get(eid).optiqcarto_data)["shapes"]) == 3


def test_import_refuse_une_entite_d_un_autre_compte(app, client, source_entity, target_user):
    _login(client, app, target_user["email"])
    res = _upload(client, {"format": "optiqcarto/entity", "version": 1,
                           "entity": {"name": "x"}, "diagram": DIAGRAM},
                  entity_id=str(source_entity["id"]))
    assert res.status_code == 404


# ── Robustesse ────────────────────────────────────────────────────────────────

def test_import_sans_fichier(app, client, target_user):
    _login(client, app, target_user["email"])
    res = client.post("/cartography/api/import", data={}, content_type="multipart/form-data")
    assert res.status_code == 400


def test_import_fichier_illisible(app, client, target_user):
    _login(client, app, target_user["email"])
    res = client.post(
        "/cartography/api/import",
        data={"file": (io.BytesIO(b"ceci n'est pas du JSON"), "x.optiqcarto")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_import_json_sans_cartographie(app, client, target_user):
    _login(client, app, target_user["email"])
    res = _upload(client, {"hello": "world"})
    assert res.status_code == 400
    assert "cartographie" in res.get_json()["error"].lower()


def test_export_et_import_exigent_une_session(app, client):
    with client.session_transaction() as sess:
        sess.clear()
    assert client.get("/cartography/api/export").status_code == 403
    assert client.post("/cartography/api/import").status_code == 403


# ── Losange inséré dans le flux (import VSDX : la flèche est coupée dessus) ───
# L'import pose désormais le losange EN NOEUD : A → losange → B1/B2. Le modèle
# métier, lui, ne connaît que des activités : _do_sync doit retrouver A → B.

DIAGRAM_DECISION = {
    "shapes": [
        {"id": "a1", "type": "process", "label": "Analyser la demande",
         "x": 100, "y": 0, "w": 120, "h": 60},
        {"id": "d1", "type": "decision", "label": "Faisable ?",
         "x": 300, "y": 10, "w": 40, "h": 40},
        {"id": "b1", "type": "process", "label": "Chiffrer",
         "x": 500, "y": 0, "w": 120, "h": 60},
        {"id": "b2", "type": "process", "label": "Refuser la demande",
         "x": 500, "y": 120, "w": 120, "h": 60},
    ],
    "bands": [{"id": "b", "label": "Commerce", "height": 300}],
    "connections": [
        {"id": 801, "fromId": "a1", "toId": "d1", "label": ""},
        {"id": 802, "fromId": "d1", "toId": "b1", "label": "Oui"},
        {"id": 803, "fromId": "d1", "toId": "b2", "label": "Non"},
    ],
    "bandWidth": 1400,
}


def test_un_losange_dans_le_flux_garde_le_lien_metier(app, client, ids):
    """A → losange → B doit produire les liens A → B (le losange n'est pas une activité)."""
    # les tests precedents laissent la session sur un autre compte
    with app.app_context():
        from Code.models.models import User
        seed = User.query.filter_by(email='test@devoptiq.com').first()
        uid, umail = seed.id, seed.email
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['user_email'] = umail
        sess['active_entity_id'] = ids['entity_id']

    res = client.post('/cartography/api/save', json={'diagram': DIAGRAM_DECISION})
    assert res.status_code == 200

    with app.app_context():
        from Code.models.models import Activities, Link
        ent_id = ids['entity_id']
        acts = {a.name: a for a in Activities.query.filter_by(entity_id=ent_id).all()}
        assert 'Analyser la demande' in acts
        assert 'Chiffrer' in acts
        # le losange n'est pas une activité
        assert 'Faisable ?' not in acts

        liens = Link.query.filter(
            Link.source_activity_id == acts['Analyser la demande'].id).all()
        cibles = {l.target_activity_id for l in liens}
        assert acts['Chiffrer'].id in cibles, "le lien A → B est perdu quand un losange coupe la flèche"
        assert acts['Refuser la demande'].id in cibles
        # le libellé de la décision est absorbé comme choix Oui/Non
        vers_chiffrer = next(l for l in liens if l.target_activity_id == acts['Chiffrer'].id)
        assert (vers_chiffrer.choice_label or '').lower() in ('oui', 'yes', '')
