# tests/test_149_cartography_editor_residuel.py
"""
Couverture résiduelle de Code/routes/cartography_editor.py :

  - _sync_carto_to_db : bande sans nom, forme sans libellé, activité retrouvée
    par son NOM (nouveau shape_id), renvoi résolu vers l'activité réelle,
    boucle sur soi ignorée, extrémité inconnue ignorée, choix de losange
    normalisé (yes → Oui), activité hors bande, mise à jour du libellé et du
    choix d'un lien existant, rollback + relance en cas d'échec
  - « Aucune entité active » sur chaque endpoint de l'éditeur (400/403/[])
  - Échecs de synchro : /api/save et /api/import (sync_warning),
    calque appliqué / désactivé (500)
  - Viewer / éditeur : calque de session qui n'appartient pas à l'entité,
    aperçu d'une autre entité, _vsdx_path sans fichier

Chaque test crée ses entités et les supprime : aucune dépendance d'ordre.
"""
import io
import json
import uuid

import pytest

import Code.routes.cartography_editor as ce

pytestmark = pytest.mark.cartography_editor


def _nom(prefix):
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def _entite(app, owner_id, carto=None, **kw):
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        e = Entity(name=_nom("CE149"), description="", owner_id=owner_id,
                   optiqcarto_data=json.dumps(carto) if carto is not None else None, **kw)
        db.session.add(e)
        db.session.commit()
        return e.id


def _supprimer(app, *entity_ids, roles=()):
    with app.app_context():
        from Code.models.models import (Entity, Activities, Link, Role, CartoCalque,
                                        activity_roles)
        from Code.extensions import db
        for eid in entity_ids:
            act_ids = [a.id for a in Activities.query.filter_by(entity_id=eid).all()]
            if act_ids:
                db.session.execute(activity_roles.delete().where(
                    activity_roles.c.activity_id.in_(act_ids)))
            Link.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            CartoCalque.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            Activities.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            Entity.query.filter_by(id=eid).delete(synchronize_session=False)
        for nom in roles:
            for r in Role.query.filter_by(name=nom).all():
                db.session.execute(activity_roles.delete().where(
                    activity_roles.c.role_id == r.id))
                db.session.delete(r)
        db.session.commit()


@pytest.fixture
def actif(app, auth_client, ids):
    """Entité dédiée activée en session ; tout est restauré à la fin."""
    crees = []

    def _fab(carto=None, **kw):
        eid = _entite(app, ids["user_id"], carto=carto, **kw)
        crees.append(eid)
        with auth_client.session_transaction() as sess:
            sess["active_entity_id"] = eid
        return eid

    yield _fab
    with auth_client.session_transaction() as sess:
        sess["active_entity_id"] = ids["entity_id"]
        sess.pop("active_calque_id", None)
        sess.pop("active_calque_name", None)
    _supprimer(app, *crees)


# ─────────────────────────────────────────────────────────────────────────────
# _sync_carto_to_db
# ─────────────────────────────────────────────────────────────────────────────

def _diagramme(bande, lien_ab="via renvoi", choix="yes"):
    return {
        "bands": [{"id": "b0", "label": "", "height": 100},       # -200 → -100, sans nom
                  {"id": "b1", "label": bande, "height": 300}],   # -100 → 200
        "shapes": [
            {"id": "a", "type": "process", "label": "A149", "y": -50, "h": 60},
            {"id": "b", "type": "process", "label": "B149", "y": 900, "h": 60},
            {"id": "c", "type": "process", "label": "C149", "y": 0, "h": 60},
            {"id": "e", "type": "process", "label": "   ", "y": 0, "h": 60},
            {"id": "r", "type": "start-end", "label": "A149"},
            {"id": "r2", "type": "start-end", "label": "Renvoi orphelin"},
            {"id": "d", "type": "decision", "label": "OK ?"},
        ],
        "connections": [
            {"fromId": "r", "toId": "b", "label": lien_ab},   # renvoi → A149 → B149
            {"fromId": "r", "toId": "a"},                      # A149 → A149 : ignorée
            {"fromId": "zz", "toId": "b"},                     # extrémité inconnue
            {"fromId": "r2", "toId": "c"},                     # renvoi non résolu
            {"fromId": "a", "toId": "d"},                      # entrée de losange
            {"fromId": "d", "toId": "c", "choiceLabel": choix},
        ],
    }


class TestSyncCartoResiduel:

    def test_sync_renvois_losanges_bandes_et_rattachement_par_nom(self, app, ids):
        eid = _entite(app, ids["user_id"])
        bande = _nom("Bande149")
        try:
            with app.app_context():
                from Code.models.models import Entity, Activities, Link, activity_roles
                from Code.extensions import db
                # C149 existe déjà (autre shape_id) avec des données : on la garde.
                ancienne = Activities(entity_id=eid, name="C149", shape_id="ancien",
                                      description="données à garder")
                db.session.add(ancienne)
                db.session.commit()
                c_id = ancienne.id

                ce._sync_carto_to_db(db.session.get(Entity, eid), _diagramme(bande))

                acts = {a.name: a for a in Activities.query.filter_by(entity_id=eid).all()}
                assert set(acts) == {"A149", "B149", "C149"}
                assert acts["C149"].id == c_id and acts["C149"].shape_id == "c"
                assert acts["C149"].description == "données à garder"

                liens = {(l.source_activity_id, l.target_activity_id): l
                         for l in Link.query.filter_by(entity_id=eid).all()}
                a, b, c = acts["A149"].id, acts["B149"].id, acts["C149"].id
                assert set(liens) == {(a, b), (a, c)}
                assert liens[(a, b)].description == "via renvoi"
                assert liens[(a, c)].choice_label == "Oui"

                roles = {r.activity_id: r.role_id for r in db.session.execute(
                    activity_roles.select().where(
                        activity_roles.c.activity_id.in_([a, b, c]))).fetchall()}
                assert a in roles and c in roles
                assert b not in roles           # hors de toute bande
                assert roles[a] == roles[c]
        finally:
            _supprimer(app, eid, roles=(bande,))

    def test_resync_met_a_jour_libelle_et_choix_des_liens_existants(self, app, ids):
        eid = _entite(app, ids["user_id"])
        bande = _nom("Bande149")
        try:
            with app.app_context():
                from Code.models.models import Entity, Activities, Link, activity_roles
                from Code.extensions import db
                ce._sync_carto_to_db(db.session.get(Entity, eid), _diagramme(bande))
                acts = {a.name: a.id for a in Activities.query.filter_by(entity_id=eid).all()}
                role_avant = db.session.execute(activity_roles.select().where(
                    activity_roles.c.activity_id == acts["A149"])).fetchone().role_id

                ce._sync_carto_to_db(db.session.get(Entity, eid),
                                     _diagramme(bande, lien_ab="modifié", choix="no"))
                db.session.expire_all()
                liens = {(l.source_activity_id, l.target_activity_id): l
                         for l in Link.query.filter_by(entity_id=eid).all()}
                assert liens[(acts["A149"], acts["B149"])].description == "modifié"
                assert liens[(acts["A149"], acts["C149"])].choice_label == "Non"
                assert len(liens) == 2
                lignes = db.session.execute(activity_roles.select().where(
                    activity_roles.c.activity_id == acts["A149"])).fetchall()
                assert [l.role_id for l in lignes] == [role_avant]
        finally:
            _supprimer(app, eid, roles=(bande,))

    def test_choix_libre_conserve_tel_quel(self, app, ids):
        eid = _entite(app, ids["user_id"])
        bande = _nom("Bande149")
        try:
            with app.app_context():
                from Code.models.models import Entity, Link
                from Code.extensions import db
                ce._sync_carto_to_db(db.session.get(Entity, eid),
                                     _diagramme(bande, choix="Peut-être"))
                choix = {l.choice_label for l in Link.query.filter_by(entity_id=eid).all()}
                assert "Peut-être" in choix
        finally:
            _supprimer(app, eid, roles=(bande,))

    def test_echec_de_synchro_fait_un_rollback_et_relance(self, app, ids, monkeypatch):
        eid = _entite(app, ids["user_id"])
        try:
            with app.app_context():
                from Code.models.models import Entity, Activities
                from Code.extensions import db

                def _boom(entity, diagram):
                    db.session.add(Activities(entity_id=eid, name="Fantôme149"))
                    db.session.flush()
                    raise RuntimeError("diagramme incohérent")
                monkeypatch.setattr(ce, "_do_sync", _boom)
                with pytest.raises(RuntimeError, match="incohérent"):
                    ce._sync_carto_to_db(db.session.get(Entity, eid), {})
                assert Activities.query.filter_by(name="Fantôme149").count() == 0
        finally:
            _supprimer(app, eid)


# ─────────────────────────────────────────────────────────────────────────────
# « Aucune entité active »
# ─────────────────────────────────────────────────────────────────────────────

SANS_ENTITE = [
    ("post", "/cartography/api/save", {"json": {"shapes": []}}, 400, None),
    ("post", "/cartography/api/save-diff", {"json": {"shapes": []}}, 400, None),
    ("get", "/cartography/api/load/inexistante-149", {}, 400, None),
    ("get", "/cartography/api/calques", {}, 200, []),
    ("post", "/cartography/api/calques", {"json": {"name": "x", "state": {}}}, 400, None),
    ("get", "/cartography/api/calques/1", {}, 403, None),
    ("put", "/cartography/api/calques/1", {"json": {"name": "x"}}, 400, None),
    ("delete", "/cartography/api/calques/1", {}, 403, None),
    ("post", "/cartography/api/calques/1/apply", {}, 403, None),
    ("post", "/cartography/api/calques/deactivate", {}, 403, None),
    ("get", "/cartography/api/list", {}, 200, []),
    ("delete", "/cartography/api/delete/x", {}, 400, None),
    ("get", "/cartography/api/vsdx", {}, 400, None),
    ("post", "/cartography/api/vsdx-compare", {}, 400, None),
]


class TestSansEntiteActive:

    @pytest.mark.parametrize("methode,url,kw,code,corps", SANS_ENTITE,
                             ids=[f"{m} {u}" for m, u, *_ in SANS_ENTITE])
    def test_endpoint_sans_entite_active(self, auth_client, monkeypatch,
                                         methode, url, kw, code, corps):
        monkeypatch.setattr(ce, "_get_active_entity", lambda: None)
        r = getattr(auth_client, methode)(url, **kw)
        assert r.status_code == code
        if corps is not None:
            assert r.get_json() == corps
        else:
            assert "error" in r.get_json()

    def test_get_active_entity_sans_utilisateur_renvoie_none(self, app):
        with app.test_request_context():
            assert ce._get_active_entity() is None

    def test_get_active_entity_repli_sur_la_derniere_entite_du_compte(self, app, ids, monkeypatch):
        from Code.models.models import Entity
        monkeypatch.setattr(Entity, "get_active", classmethod(lambda cls, uid=None: None))
        eid = _entite(app, ids["user_id"])
        try:
            with app.test_request_context():
                from flask import session
                session["user_id"] = ids["user_id"]
                assert ce._get_active_entity().id == eid
        finally:
            _supprimer(app, eid)


# ─────────────────────────────────────────────────────────────────────────────
# Échecs de synchro remontés à l'interface
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def synchro_en_panne(monkeypatch):
    def _boom(entity, diagram):
        raise RuntimeError("synchro impossible")
    monkeypatch.setattr(ce, "_sync_carto_to_db", _boom)


class TestEchecsDeSynchro:

    def test_save_enregistre_la_carto_et_signale_l_echec_de_synchro(
            self, app, auth_client, actif, synchro_en_panne):
        eid = actif()
        diagram = {"shapes": [{"id": 1, "type": "process", "label": "X"}], "connections": []}
        r = auth_client.post("/cartography/api/save", json={"diagram": diagram})
        assert r.status_code == 200
        j = r.get_json()
        assert j["ok"] is True and j["sync_warning"] == "synchro impossible"
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            assert json.loads(db.session.get(Entity, eid).optiqcarto_data) == diagram

    def test_import_dans_une_entite_existante_signale_l_echec_de_synchro(
            self, app, auth_client, ids, actif, synchro_en_panne):
        with app.app_context():
            from Code.models.models import Entity
            avant = {e.id: e.is_active for e in Entity.query.filter_by(owner_id=ids["user_id"])}
        eid = actif()
        try:
            paquet = json.dumps({"shapes": [], "connections": [], "bands": [{"id": 1}]})
            r = auth_client.post("/cartography/api/import",
                                 data={"file": (io.BytesIO(paquet.encode()), "c.optiqcarto"),
                                       "entity_id": str(eid)},
                                 content_type="multipart/form-data")
            assert r.status_code == 200
            j = r.get_json()
            assert j["created"] is False
            assert j["entity"]["id"] == eid
            assert j["sync_warning"] == "synchro impossible"
            assert j["counts"] == {"shapes": 0, "connections": 0, "bands": 1}
        finally:
            with app.app_context():
                from Code.models.models import Entity
                from Code.extensions import db
                for e_id, etat in avant.items():
                    e = db.session.get(Entity, e_id)
                    if e is not None:
                        e.is_active = etat
                db.session.commit()

    def test_appliquer_un_calque_en_echec_renvoie_500_sans_l_activer(
            self, app, auth_client, actif, synchro_en_panne):
        eid = actif()
        with app.app_context():
            from Code.models.models import CartoCalque
            from Code.extensions import db
            cal = CartoCalque(entity_id=eid, name="Calque149", state_json='{"shapes": []}')
            db.session.add(cal)
            db.session.commit()
            cal_id = cal.id
        r = auth_client.post(f"/cartography/api/calques/{cal_id}/apply")
        assert r.status_code == 500
        assert r.get_json()["error"] == "synchro impossible"
        with auth_client.session_transaction() as sess:
            assert sess.get("active_calque_id") != cal_id

    def test_desactiver_un_calque_en_echec_renvoie_500(self, auth_client, actif, synchro_en_panne):
        actif(carto={"shapes": []})
        with auth_client.session_transaction() as sess:
            sess["active_calque_id"] = 123
        r = auth_client.post("/cartography/api/calques/deactivate")
        assert r.status_code == 500
        with auth_client.session_transaction() as sess:
            assert "active_calque_id" not in sess

    def test_desactiver_sans_carto_de_base_ne_resynchronise_rien(
            self, auth_client, actif, synchro_en_panne):
        actif()
        r = auth_client.post("/cartography/api/calques/deactivate")
        assert r.status_code == 200
        assert r.get_json() == {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# Viewer / éditeur
# ─────────────────────────────────────────────────────────────────────────────

class TestViewerEditeurResiduel:

    def test_viewer_ignore_un_calque_de_session_d_une_autre_entite(self, app, auth_client, actif):
        autre = actif()
        with app.app_context():
            from Code.models.models import CartoCalque
            from Code.extensions import db
            cal = CartoCalque(entity_id=autre, name="Ailleurs149", state_json="{}")
            db.session.add(cal)
            db.session.commit()
            cal_id = cal.id
        actif(carto={"shapes": []})
        with auth_client.session_transaction() as sess:
            sess["active_calque_id"] = cal_id
            sess["active_calque_name"] = "Ailleurs149"
        r = auth_client.get("/cartography/viewer")
        assert r.status_code == 200
        assert b"Ailleurs149" not in r.data

    def test_editeur_ignore_un_calque_de_session_d_une_autre_entite(self, app, auth_client, actif,
                                                                 monkeypatch):
        autre = actif()
        with app.app_context():
            from Code.models.models import CartoCalque
            from Code.extensions import db
            cal = CartoCalque(entity_id=autre, name="Ailleurs149b", state_json="{}")
            db.session.add(cal)
            db.session.commit()
            cal_id = cal.id
        actif()
        with auth_client.session_transaction() as sess:
            sess["active_calque_id"] = cal_id
        captured = {}
        vrai = ce.render_template

        def _espion(tpl, **ctx):
            captured.update(ctx)
            return vrai(tpl, **ctx)
        monkeypatch.setattr(ce, "render_template", _espion)
        r = auth_client.get("/cartography/editor")
        assert r.status_code == 200
        assert captured["active_calque_id"] is None

    def test_viewer_apercu_d_une_autre_entite(self, app, auth_client, ids, actif):
        actif()
        autre = _entite(app, ids["user_id"], carto={"shapes": []})
        try:
            with app.app_context():
                from Code.models.models import Entity
                from Code.extensions import db
                nom = db.session.get(Entity, autre).name
            r = auth_client.get(f"/cartography/viewer?entity_id={autre}")
            assert r.status_code == 200
            assert nom.encode() in r.data
        finally:
            _supprimer(app, autre)

    def test_vsdx_path_aucun_candidat_existant(self, app, ids):
        eid = _entite(app, ids["user_id"], vsdx_filename="introuvable_149.vsdx")
        try:
            with app.app_context():
                from Code.models.models import Entity
                from Code.extensions import db
                assert ce._vsdx_path(db.session.get(Entity, eid)) is None
        finally:
            _supprimer(app, eid)

    def test_api_vsdx_sans_fichier_renvoie_404(self, auth_client, actif):
        actif(vsdx_filename="introuvable_149.vsdx")
        r = auth_client.get("/cartography/api/vsdx")
        assert r.status_code == 404
