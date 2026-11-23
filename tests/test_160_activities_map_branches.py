# tests/test_160_activities_map_branches.py
"""
Branches restantes de Code/routes/activities_map.py (96 % → visé ~99 %),
laissées de côté par test_15 / 44 / 50 / 64 / 148 :

  - get_active_entity : session périmée → entité marquée is_active en base
  - _map_is_admin / _peut_regler_acces / _examen_en_attente : repli sur
    « non » / None quand le module des droits lève
  - /map : SVG présent, activités hachurées (extco) repérées, carto illisible
  - /svg servi depuis le disque ; /api/svg/<id> servi depuis la base
  - activation d'une entité sans propriétaire (legacy)
  - suppression d'entité : rôle orphelin effacé, échec → 500 + rollback
  - partage : 401 sans connexion, destinataires / remplacement invalides,
    « mettre à jour la mienne » dont la synchro échoue (sync_warning)
  - upload-cartography sans entité active, SVG non relisible pour la base
  - /update-cartography de ce blueprint : MASQUÉ par activities_bp
  - debug/files (dossier présent), cross_carto_matches (cartos illisibles,
    aucune autre carto), reverse_liaisons_map anonyme
  - officialize_liaison : lien entrant dans l'extco, carto source illisible
  - liaison_deoffice(_preview) : 403 hors propriétaire, carto illisible

Chaque test crée ses propres objets et les nettoie.
"""
import io
import json
import uuid

import pytest
from werkzeug.security import generate_password_hash

import Code.routes.activities_map as am

pytestmark = pytest.mark.activities_map


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _nom(prefix="AM160"):
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def _entite(app, owner_id, carto=None, svg_content=None, nom=None, raw=None,
            is_active=False):
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        data = raw if raw is not None else (json.dumps(carto) if carto is not None else None)
        e = Entity(name=nom or _nom(), description="", owner_id=owner_id,
                   optiqcarto_data=data, svg_content=svg_content,
                   is_active=is_active)
        db.session.add(e)
        db.session.commit()
        return e.id


def _activite(app, entity_id, name, shape_id=None, subtype=None):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, shape_id=shape_id,
                       shape_subtype=subtype)
        db.session.add(a)
        db.session.commit()
        return a.id


def _supprimer(app, *entity_ids):
    with app.app_context():
        from Code.models.models import (Entity, Activities, Link, Data,
                                        CrossCartoLiaison, EntityShareOffer)
        from Code.extensions import db
        for eid in entity_ids:
            CrossCartoLiaison.query.filter(
                (CrossCartoLiaison.extco_entity_id == eid)
                | (CrossCartoLiaison.origin_entity_id == eid)
            ).delete(synchronize_session=False)
            Link.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            Data.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            Activities.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            EntityShareOffer.query.filter_by(created_entity_id=eid).delete(
                synchronize_session=False)
            Entity.query.filter_by(id=eid).delete(synchronize_session=False)
        db.session.commit()


def _user(app, email=None, status="user"):
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        email = email or f"am160.{uuid.uuid4().hex[:8]}@devoptiq.com"
        u = User(first_name="Am", last_name="Cent", email=email,
                 password=generate_password_hash("Test1234!"), status=status)
        db.session.add(u)
        db.session.commit()
        return u.id, email


def _supprimer_user(app, uid):
    with app.app_context():
        from Code.models.models import User
        from Code.extensions import db
        User.query.filter_by(id=uid).delete(synchronize_session=False)
        db.session.commit()


@pytest.fixture
def crees(app, auth_client, ids):
    """Entités créées pendant le test : nettoyées, session restaurée."""
    liste = []
    yield liste
    with auth_client.session_transaction() as sess:
        sess["user_id"] = ids["user_id"]
        sess["active_entity_id"] = ids["entity_id"]
    _supprimer(app, *liste)


def _activer(client, eid):
    with client.session_transaction() as sess:
        sess["active_entity_id"] = eid


@pytest.fixture
def dossier_entites(tmp_path, monkeypatch):
    monkeypatch.setattr(am, "ENTITIES_DIR", str(tmp_path))
    return tmp_path


def _leve(*a, **k):
    raise RuntimeError("panne simulée")


# ─────────────────────────────────────────────────────────────────────────────
# Résolution de l'entité active et petits garde-fous
# ─────────────────────────────────────────────────────────────────────────────

class TestEntiteActiveEtGardeFous:

    def test_session_perimee_retombe_sur_l_entite_is_active(self, app, ids, crees):
        eid = _entite(app, ids["user_id"], is_active=True)
        crees.append(eid)
        from flask import session
        with app.test_request_context("/"):
            session["user_id"] = ids["user_id"]
            session["active_entity_id"] = 987654321
            ent = am.get_active_entity()
            assert ent is not None and ent.is_active is True
            assert session["active_entity_id"] == ent.id

    def test_map_is_admin_repli_false_si_les_droits_levent(self, app, monkeypatch):
        import Code.permissions as perm
        monkeypatch.setattr(perm, "is_admin", _leve)
        with app.test_request_context("/"):
            assert am._map_is_admin() is False

    def test_peut_regler_acces_repli_false_si_les_droits_levent(self, app, monkeypatch):
        import Code.carto_access as ca
        monkeypatch.setattr(ca, "can_manage_access", _leve)
        with app.test_request_context("/"):
            assert am._peut_regler_acces() is False

    def test_examen_en_attente_repli_none_si_la_file_leve(self, app, monkeypatch):
        import Code.routes.carto_sharing as cs
        monkeypatch.setattr(cs, "propositions_a_examiner", _leve)
        with app.test_request_context("/"):
            assert am._examen_en_attente() is None

    def test_entite_jumelle_nom_vide_aucune(self, app, ids):
        with app.app_context():
            assert am._entite_jumelle("", ids["user_id"]) is None


# ─────────────────────────────────────────────────────────────────────────────
# Page /map
# ─────────────────────────────────────────────────────────────────────────────

class TestPageCarte:

    def test_svg_present_nomme_le_fichier_courant(self, app, auth_client, ids,
                                                 crees, monkeypatch):
        eid = _entite(app, ids["user_id"])
        crees.append(eid)
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            db.session.get(Entity, eid).svg_filename = "ma_carte.svg"
            db.session.commit()
        _activer(auth_client, eid)
        monkeypatch.setattr(am, "check_svg_exists", lambda _id: (True, "/x/carto.svg"))
        r = auth_client.get("/activities/map")
        assert r.status_code == 200
        assert b'window.CURRENT_SVG = "ma_carte.svg"' in r.data

    def test_activites_hachurees_reperees_par_leur_nom(self, app, auth_client,
                                                      ids, crees):
        carto = {"shapes": [
            {"id": "s1", "label": "Externe AM160", "subtype": "extco"},
            {"id": "s2", "label": "Interne AM160", "subtype": "normal"},
        ], "connections": []}
        eid = _entite(app, ids["user_id"], carto=carto)
        crees.append(eid)
        ext = _activite(app, eid, "Externe AM160", shape_id="s1", subtype="extco")
        _activite(app, eid, "Interne AM160", shape_id="s2")
        _activer(auth_client, eid)
        r = auth_client.get("/activities/map")
        assert r.status_code == 200
        assert f"window.EXTCO_ACTIVITY_IDS = [{ext}]".encode() in r.data

    def test_carto_illisible_n_empeche_pas_la_page(self, app, auth_client, ids, crees):
        eid = _entite(app, ids["user_id"], raw="{pas du json")
        crees.append(eid)
        _activer(auth_client, eid)
        r = auth_client.get("/activities/map")
        assert r.status_code == 200
        assert b"window.EXTCO_ACTIVITY_IDS = []" in r.data


# ─────────────────────────────────────────────────────────────────────────────
# Service des SVG
# ─────────────────────────────────────────────────────────────────────────────

class TestServiceSvg:

    def test_svg_actif_servi_depuis_le_disque(self, app, auth_client, ids,
                                             crees, dossier_entites):
        eid = _entite(app, ids["user_id"])
        crees.append(eid)
        d = dossier_entites / f"entity_{eid}"
        d.mkdir()
        (d / "carto.svg").write_text("<svg id='disque-am160'/>", encoding="utf-8")
        _activer(auth_client, eid)
        r = auth_client.get("/activities/svg")
        assert r.status_code == 200
        assert r.mimetype == "image/svg+xml"
        assert b"disque-am160" in r.data

    def test_api_svg_servi_depuis_la_base(self, app, auth_client, ids, crees,
                                         monkeypatch):
        eid = _entite(app, ids["user_id"], svg_content="<svg id='base-am160'/>")
        crees.append(eid)
        monkeypatch.setattr(am, "check_svg_exists", lambda _id: (False, None))
        r = auth_client.get(f"/activities/api/svg/{eid}")
        assert r.status_code == 200
        assert r.headers["Cache-Control"] == "no-store"
        assert b"base-am160" in r.data

    def test_api_svg_sans_fichier_ni_contenu_404(self, app, auth_client, ids,
                                                crees, monkeypatch):
        eid = _entite(app, ids["user_id"])
        crees.append(eid)
        monkeypatch.setattr(am, "check_svg_exists", lambda _id: (False, None))
        assert auth_client.get(f"/activities/api/svg/{eid}").status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Activation / suppression d'entité
# ─────────────────────────────────────────────────────────────────────────────

class TestActivationSuppression:

    def test_activer_une_entite_legacy_desactive_les_autres_legacy(self, app,
                                                                  auth_client, crees):
        from Code.models.models import Entity
        from Code.extensions import db
        with app.app_context():
            avant = {e.id: e.is_active for e in
                     Entity.query.filter(Entity.owner_id == None).all()}  # noqa: E711
        autre = _entite(app, None, is_active=True)
        cible = _entite(app, None)
        crees.extend([autre, cible])
        try:
            r = auth_client.post(f"/activities/api/entities/{cible}/activate")
            assert r.status_code == 200
            with app.app_context():
                assert db.session.get(Entity, cible).is_active is True
                assert db.session.get(Entity, autre).is_active is False
        finally:
            with app.app_context():
                for eid, etat in avant.items():
                    e = db.session.get(Entity, eid)
                    if e is not None:
                        e.is_active = etat
                db.session.commit()

    def _carto_avec_role(self, app, ids):
        from Code.models.models import Role, activity_roles
        from Code.extensions import db
        eid = _entite(app, ids["user_id"])
        aid = _activite(app, eid, "Act rôle AM160")
        with app.app_context():
            r = Role(name=_nom("RoleAM160"))
            db.session.add(r)
            db.session.flush()
            db.session.execute(activity_roles.insert().values(
                activity_id=aid, role_id=r.id, status="Garant"))
            db.session.commit()
            return eid, r.id

    def test_supprimer_efface_le_role_qui_ne_porte_plus_rien(self, app,
                                                           auth_client, ids, crees):
        from Code.models.models import Role, Entity
        from Code.extensions import db
        eid, rid = self._carto_avec_role(app, ids)
        crees.append(eid)
        r = auth_client.delete(f"/activities/api/entities/{eid}")
        assert r.status_code == 200
        with app.app_context():
            assert db.session.get(Entity, eid) is None
            assert db.session.get(Role, rid) is None

    def test_echec_pendant_la_suppression_500_et_rien_d_efface(self, app,
                                                             auth_client, ids,
                                                             crees, monkeypatch):
        from Code.models.models import Role, Entity
        from Code.extensions import db
        import Code.roles_communs as rc
        eid, rid = self._carto_avec_role(app, ids)
        crees.append(eid)
        monkeypatch.setattr(rc, "est_utilise", _leve)
        r = auth_client.delete(f"/activities/api/entities/{eid}")
        assert r.status_code == 500
        assert "panne simulée" in r.get_json()["error"]
        with app.app_context():
            assert db.session.get(Entity, eid) is not None
            role = db.session.get(Role, rid)
            assert role is not None
            db.session.delete(role)
            db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Partage d'entité
# ─────────────────────────────────────────────────────────────────────────────

class TestPartage:

    @pytest.mark.parametrize("methode,url", [
        ("get", "/activities/api/entities/1/share/candidates"),
        ("post", "/activities/api/entities/1/share"),
        ("post", "/activities/api/share/offers/1/respond"),
    ])
    def test_sans_connexion_401(self, app, methode, url):
        c = app.test_client()
        r = getattr(c, methode)(url, json={})
        assert r.status_code == 401

    def test_destinataires_non_numeriques_400(self, app, auth_client, ids, crees):
        eid = _entite(app, ids["user_id"])
        crees.append(eid)
        r = auth_client.post(f"/activities/api/entities/{eid}/share",
                             json={"user_ids": ["abc"]})
        assert r.status_code == 400
        assert r.get_json()["error"] == "Liste de destinataires invalide"

    def test_entite_a_remplacer_invalide_400(self, app, auth_client, ids, crees):
        eid = _entite(app, ids["user_id"])
        crees.append(eid)
        uid, _ = _user(app)
        try:
            r = auth_client.post(f"/activities/api/entities/{eid}/share",
                                 json={"user_ids": [uid], "replace": {"x": "y"}})
            assert r.status_code == 400
            assert r.get_json()["error"] == "Entité à remplacer invalide"
        finally:
            _supprimer_user(app, uid)

    def test_mise_a_jour_dont_la_synchro_echoue_le_signale(self, app, auth_client,
                                                          ids, crees, monkeypatch):
        from Code.models.models import EntityShareOffer, Entity
        from Code.extensions import db
        import Code.routes.cartography_editor as ce
        nom = _nom("Jumelle")
        cible = _entite(app, ids["user_id"], nom=nom)
        crees.append(cible)
        carto = {"shapes": [{"id": "p1", "type": "process", "label": "A"}],
                 "connections": []}
        with app.app_context():
            o = EntityShareOffer(from_user_id=ids["user_id"], to_user_id=ids["user_id"],
                                 entity_name=nom, description="desc reçue",
                                 optiqcarto_data=json.dumps(carto), status="pending")
            db.session.add(o)
            db.session.commit()
            oid = o.id
        monkeypatch.setattr(ce, "_sync_carto_to_db", _leve)
        try:
            r = auth_client.post(f"/activities/api/share/offers/{oid}/respond",
                                 json={"action": "update"})
            assert r.status_code == 200
            body = r.get_json()
            assert body["action"] == "updated"
            assert body["entity_id"] == cible
            assert body["sync_warning"] == "panne simulée"
            with app.app_context():
                assert db.session.get(Entity, cible).description == "desc reçue"
                assert db.session.get(EntityShareOffer, oid).status == "accepted"
        finally:
            with app.app_context():
                EntityShareOffer.query.filter_by(id=oid).delete()
                db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Upload / routes historiques / debug
# ─────────────────────────────────────────────────────────────────────────────

class TestUploadEtRoutesHistoriques:

    def test_upload_sans_entite_active_400(self, auth_client, monkeypatch):
        monkeypatch.setattr(am, "get_active_entity", lambda: None)
        r = auth_client.post("/activities/upload-cartography", data={},
                             content_type="multipart/form-data")
        assert r.status_code == 400
        assert r.get_json()["error"] == "Aucune entité active"

    def test_upload_svg_non_relisible_n_empeche_pas_l_import(self, app, auth_client,
                                                            ids, crees,
                                                            dossier_entites,
                                                            monkeypatch):
        from Code.models.models import Entity
        from Code.extensions import db
        eid = _entite(app, ids["user_id"])
        crees.append(eid)
        _activer(auth_client, eid)
        monkeypatch.setattr(am, "open", _leve, raising=False)
        monkeypatch.setattr(am, "sync_activities_with_svg",
                            lambda _id, _p: {"total": 0})
        r = auth_client.post("/activities/upload-cartography", data={
            "svg_file": (io.BytesIO(b"<svg/>"), "carte.svg"),
        }, content_type="multipart/form-data")
        assert r.status_code == 200
        with app.app_context():
            e = db.session.get(Entity, eid)
            assert e.svg_filename == "carte.svg"
            assert e.svg_content is None

    def test_update_cartography_de_ce_blueprint_est_masquee(self, app):
        """Deux blueprints déclarent /activities/update-cartography : c'est
        celui d'activities_bp (enregistré avant) qui répond."""
        adapter = app.url_map.bind("localhost")
        endpoint, _ = adapter.match("/activities/update-cartography")
        assert endpoint == "activities.update_cartography"
        with app.test_request_context("/"):
            resp, code = app.view_functions["activities_map_bp.update_cartography"]()
            assert code == 200
            assert resp.get_json()["status"] == "ok"

    def test_debug_files_liste_le_contenu_du_dossier(self, app, auth_client, ids,
                                                    crees, dossier_entites):
        eid = _entite(app, ids["user_id"])
        crees.append(eid)
        d = dossier_entites / f"entity_{eid}"
        d.mkdir()
        (d / "trace.txt").write_text("x")
        r = auth_client.get("/activities/debug/files")
        assert r.status_code == 200
        ligne = next(e for e in r.get_json()["entities"] if e["id"] == eid)
        assert ligne["files_in_dir"] == ["trace.txt"]

    def test_debug_decisions_sans_entite_400(self, auth_client, monkeypatch):
        monkeypatch.setattr(am, "get_active_entity", lambda: None)
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Liaisons inter-cartos
# ─────────────────────────────────────────────────────────────────────────────

EXTCO = {"shapes": [{"id": "x1", "label": "Partagée AM160", "subtype": "extco"}],
         "connections": []}


class TestCorrespondancesInterCartos:

    def test_carto_active_illisible_aucune_correspondance(self, app, auth_client,
                                                          ids, crees):
        eid = _entite(app, ids["user_id"], raw="{cassé")
        crees.append(eid)
        _activer(auth_client, eid)
        r = auth_client.get("/activities/api/cross_carto_matches")
        assert r.get_json() == {"matches": [], "total": 0}

    def test_carto_sans_forme_hachuree_aucune_correspondance(self, app, auth_client,
                                                            ids, crees):
        eid = _entite(app, ids["user_id"],
                      carto={"shapes": [{"id": "a", "label": "Normale"}]})
        crees.append(eid)
        _activer(auth_client, eid)
        r = auth_client.get("/activities/api/cross_carto_matches")
        assert r.get_json() == {"matches": [], "total": 0}

    def test_aucune_autre_carto_aucune_correspondance(self, app, auth_client, crees):
        uid, email = _user(app)
        eid = _entite(app, uid, carto=EXTCO)
        crees.append(eid)
        try:
            with auth_client.session_transaction() as sess:
                sess["user_id"] = uid
                sess["user_email"] = email
                sess["active_entity_id"] = eid
            r = auth_client.get("/activities/api/cross_carto_matches")
            assert r.get_json() == {"matches": [], "total": 0}
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("pwd_at", None)
            _supprimer_user(app, uid)

    def test_autre_carto_illisible_ignoree(self, app, auth_client, ids, crees):
        active = _entite(app, ids["user_id"], carto=EXTCO)
        illisible = _entite(app, ids["user_id"], raw="[[[")
        crees.extend([active, illisible])
        _activer(auth_client, active)
        r = auth_client.get("/activities/api/cross_carto_matches")
        assert r.status_code == 200
        noms = {m.get("entity_id") for m in r.get_json()["matches"]}
        assert illisible not in noms

    def test_reverse_liaisons_map_anonyme_vide(self, app):
        r = app.test_client().get("/activities/api/reverse_liaisons_map")
        assert r.status_code == 200
        assert r.get_json() == {"origins": []}


class TestOfficialisationEtRetrait:

    def _decor(self, app, ids, crees, carto_source=None, raw_source=None):
        from Code.models.models import Link
        from Code.extensions import db
        source = _entite(app, ids["user_id"], carto=carto_source, raw=raw_source)
        origine = _entite(app, ids["user_id"],
                          carto={"shapes": [{"id": "o1", "label": "Origine",
                                             "x": 0, "y": 0, "w": 160, "h": 60}],
                                 "connections": []})
        crees.extend([source, origine])
        extco = _activite(app, source, "Origine", shape_id="x1", subtype="extco")
        amont = _activite(app, source, "Amont AM160", shape_id="a1")
        orig_act = _activite(app, origine, "Origine", shape_id="o1")
        with app.app_context():
            db.session.add(Link(entity_id=source, source_activity_id=amont,
                                target_activity_id=extco, type="flux"))
            db.session.commit()
        return source, origine, extco, orig_act

    def test_lien_entrant_propage_vers_l_origine(self, app, auth_client, ids, crees):
        from Code.models.models import Link
        source, origine, extco, orig_act = self._decor(app, ids, crees,
                                                       raw_source="{illisible")
        _activer(auth_client, source)
        r = auth_client.post("/activities/api/officialize_liaison", json={
            "extco_activity_id": extco, "origin_entity_id": origine,
            "origin_activity_id": orig_act})
        assert r.status_code == 200
        assert r.get_json()["links_created"] == 1
        with app.app_context():
            lk = Link.query.filter_by(entity_id=origine).one()
            assert lk.source_activity_id is None
            assert lk.target_activity_id == orig_act
            assert lk.description == "Amont AM160"

    def _liaison(self, app, extco_eid, extco_aid, orig_eid, orig_aid):
        from Code.models.models import CrossCartoLiaison
        from Code.extensions import db
        with app.app_context():
            li = CrossCartoLiaison(extco_entity_id=extco_eid, extco_activity_id=extco_aid,
                                   origin_entity_id=orig_eid, origin_activity_id=orig_aid)
            db.session.add(li)
            db.session.commit()
            return li.id

    def test_retrait_hors_proprietaire_403(self, app, auth_client, ids, crees):
        source = _entite(app, ids["user_id"])
        etrangere = _entite(app, None)
        crees.extend([source, etrangere])
        a1 = _activite(app, source, "X")
        a2 = _activite(app, etrangere, "Y")
        lid = self._liaison(app, source, a1, etrangere, a2)
        r = auth_client.get(f"/activities/api/liaison_deoffice_preview?liaison_id={lid}")
        assert r.status_code == 403
        r = auth_client.post("/activities/api/liaison_deoffice", json={"liaison_id": lid})
        assert r.status_code == 403

    def test_retrait_avec_carto_d_origine_illisible(self, app, auth_client, ids, crees):
        from Code.models.models import CrossCartoLiaison
        from Code.extensions import db
        source = _entite(app, ids["user_id"])
        origine = _entite(app, ids["user_id"], raw="{illisible")
        crees.extend([source, origine])
        a1 = _activite(app, source, "X")
        a2 = _activite(app, origine, "Y")
        lid = self._liaison(app, source, a1, origine, a2)
        r = auth_client.get(f"/activities/api/liaison_deoffice_preview?liaison_id={lid}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["shapes_to_remove"] == []
        assert body["connections_to_remove"] == 0
        r = auth_client.post("/activities/api/liaison_deoffice", json={"liaison_id": lid})
        assert r.status_code == 200
        with app.app_context():
            assert db.session.get(CrossCartoLiaison, lid) is None
