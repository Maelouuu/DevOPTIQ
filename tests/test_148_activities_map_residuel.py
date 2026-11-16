# tests/test_148_activities_map_residuel.py
"""
Couverture résiduelle de Code/routes/activities_map.py — les branches que
test_15 / test_42 / test_44 / test_50 / test_64 laissaient de côté :

  - check_svg_exists : SVG trouvé par scan du dossier, restauration DB en échec
  - /api/svg : dernier recours « SVG servi directement depuis la base »
  - _inject_extco_shapes_in_origin_carto : choix des côtés (côtés déjà câblés,
    tous câblés, entrée = sortie), placement haut/bas, évitement de collision,
    rien à injecter, carto illisible
  - /preview-connections (chemin nominal), /list-connections (pas d'entité,
    nom de la donnée source), /resync (succès, échec 500), /update-cartography
  - extract_activities_from_svg (fichier illisible), sync_activities_with_svg
    (rattachement par nom, nom inchangé)
  - _deposer_copie / _remplacer_entite : échec de synchro remonté en message
  - _read_vsdx_page_xml, endpoints debug-decisions (temp non supprimable,
    VSDX legacy présent)

Chaque test crée ses propres entités et les nettoie : aucune dépendance
à l'ordre d'exécution.
"""
import io
import json
import os
import uuid
import zipfile
from types import SimpleNamespace

import pytest

import Code.routes.activities_map as am

pytestmark = pytest.mark.activities_map


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _nom(prefix):
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def _entite(app, owner_id, carto=None, svg_content=None, nom=None):
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        e = Entity(name=nom or _nom("AM148"), description="", owner_id=owner_id,
                   optiqcarto_data=json.dumps(carto) if carto is not None else None,
                   svg_content=svg_content)
        db.session.add(e)
        db.session.commit()
        return e.id


def _supprimer(app, *entity_ids):
    with app.app_context():
        from Code.models.models import Entity, Activities, Link, Data
        from Code.extensions import db
        for eid in entity_ids:
            Link.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            Data.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            Activities.query.filter_by(entity_id=eid).delete(synchronize_session=False)
            Entity.query.filter_by(id=eid).delete(synchronize_session=False)
        db.session.commit()


@pytest.fixture
def actif(app, auth_client, ids):
    """Fabrique une entité dédiée, l'active en session, restaure à la fin."""
    crees = []

    def _fab(**kw):
        eid = _entite(app, ids["user_id"], **kw)
        crees.append(eid)
        with auth_client.session_transaction() as sess:
            sess["active_entity_id"] = eid
        return eid

    yield _fab
    with auth_client.session_transaction() as sess:
        sess["active_entity_id"] = ids["entity_id"]
    _supprimer(app, *crees)


@pytest.fixture
def dossier_entites(tmp_path, monkeypatch):
    """Isole le dossier des entités : aucun fichier ne touche static/entities."""
    monkeypatch.setattr(am, "ENTITIES_DIR", str(tmp_path))
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# check_svg_exists / serve_svg
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckSvgExistsResiduel:

    def test_svg_trouve_par_scan_du_dossier_quand_le_nom_differe(self, app, dossier_entites):
        d = dossier_entites / "entity_987654"
        d.mkdir()
        (d / "b_autre.svg").write_text("<svg/>")
        (d / "a_premier.svg").write_text("<svg/>")
        (d / "notes.txt").write_text("x")
        with app.app_context():
            ok, chemin = am.check_svg_exists(987654)
        assert ok is True
        assert chemin == str(d / "a_premier.svg")

    def test_restauration_db_en_echec_renvoie_absent(self, app, ids, dossier_entites, monkeypatch):
        eid = _entite(app, ids["user_id"], svg_content="<svg>db</svg>")
        try:
            def _boom(_eid):
                raise OSError("disque en lecture seule")
            monkeypatch.setattr(am, "ensure_entity_dir", _boom)
            with app.app_context():
                ok, _ = am.check_svg_exists(eid)
            assert ok is False
        finally:
            _supprimer(app, eid)

    def test_restauration_db_reecrit_le_fichier_sur_disque(self, app, ids, dossier_entites):
        eid = _entite(app, ids["user_id"], svg_content="<svg>restaure</svg>")
        try:
            with app.app_context():
                ok, chemin = am.check_svg_exists(eid)
            assert ok is True
            assert open(chemin, encoding="utf-8").read() == "<svg>restaure</svg>"
        finally:
            _supprimer(app, eid)

    def test_serve_svg_sert_directement_depuis_la_base_si_le_disque_echoue(
            self, auth_client, actif, monkeypatch):
        actif(svg_content="<svg>direct-db</svg>")
        monkeypatch.setattr(am, "check_svg_exists", lambda _eid: (False, None))
        r = auth_client.get("/activities/svg")
        assert r.status_code == 200
        assert r.mimetype == "image/svg+xml"
        assert b"direct-db" in r.data
        assert r.headers.get("Cache-Control") == "no-store"

    def test_serve_svg_sans_svg_ni_contenu_db_renvoie_404(self, auth_client, actif, monkeypatch):
        actif()
        monkeypatch.setattr(am, "check_svg_exists", lambda _eid: (False, None))
        r = auth_client.get("/activities/svg")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# _inject_extco_shapes_in_origin_carto — géométrie
# ─────────────────────────────────────────────────────────────────────────────

ORIGINE = {"id": 1, "label": "Origine", "x": 500, "y": 500, "w": 160, "h": 60}
EXTCO_ID = 99_999_001   # activité extco fictive : pas de shape_id en base


def _forme(sid, label, x, y, w=160, h=60, **kw):
    return dict(id=sid, label=label, x=x, y=y, w=w, h=h, **kw)


def _lien(src, tgt, desc=None):
    return SimpleNamespace(source_activity_id=src, target_activity_id=tgt, description=desc)


def _injecter(app, ids, carto, liens, noms, active_carto=None):
    """Lance l'injection sur une entité d'origine dédiée, retourne la carto finale."""
    eid = _entite(app, ids["user_id"], carto=carto)
    src_id = _entite(app, ids["user_id"], carto=active_carto) if active_carto else None
    try:
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            origine = db.session.get(Entity, eid)
            source = db.session.get(Entity, src_id) if src_id else None
            am._inject_extco_shapes_in_origin_carto(
                origine, SimpleNamespace(shape_id=1), liens, EXTCO_ID, noms,
                "Carto Source", active_entity=source,
            )
            db.session.expire_all()
            return json.loads(db.session.get(Entity, eid).optiqcarto_data)
    finally:
        _supprimer(app, *(i for i in (eid, src_id) if i))


def _injectees(carto):
    return [s for s in carto["shapes"] if s.get("crossCartoImport")]


class TestInjectionExtcoCotes:

    def test_entree_et_sortie_sur_le_meme_cote_sont_separees(self, app, ids):
        # Entrée déjà câblée à gauche, sortie déjà câblée à droite :
        # les deux choix tombent sur « top » → l'entrée bascule à gauche.
        carto = {
            "nextId": 100,
            "shapes": [ORIGINE,
                       _forme(2, "Gauche", 100, 500),
                       _forme(3, "Droite", 900, 500)],
            "connections": [{"id": 10, "fromId": 2, "toId": 1},
                            {"id": 11, "fromId": 1, "toId": 3}],
        }
        liens = [_lien(501, EXTCO_ID), _lien(EXTCO_ID, 502)]
        final = _injecter(app, ids, carto, liens, {501: "Amont X", 502: "Aval Y"})
        par_label = {s["label"]: s for s in _injectees(final)}
        # Entrée : côté gauche (x < origine)
        assert par_label["Amont X"]["x"] < ORIGINE["x"]
        # Sortie : côté haut (y au-dessus de l'origine, x centré)
        assert par_label["Aval Y"]["y"] < ORIGINE["y"]
        assert par_label["Aval Y"]["x"] == ORIGINE["x"]

    def test_tous_les_cotes_d_entree_pris_retombe_sur_le_premier(self, app, ids):
        carto = {
            "nextId": 100,
            "shapes": [ORIGINE,
                       _forme(2, "G", 100, 500), _forme(3, "D", 900, 500),
                       _forme(4, "H", 500, 100), _forme(5, "B", 500, 900)],
            "connections": [{"id": 10, "fromId": s, "toId": 1} for s in (2, 3, 4, 5)]
                           + [{"id": 20, "fromId": 77, "toId": 1}],   # source inconnue
        }
        final = _injecter(app, ids, carto, [_lien(501, EXTCO_ID)], {501: "Amont Z"})
        (forme,) = _injectees(final)
        # priorité d'entrée ['left', …] → gauche malgré l'occupation
        assert forme["x"] < ORIGINE["x"]
        assert forme["subtype"] == "extco"
        assert forme["crossCartoSource"] == "Carto Source"

    def test_sortie_placee_en_bas_quand_droite_et_haut_sont_pris(self, app, ids):
        carto = {
            "nextId": 100,
            "shapes": [ORIGINE, _forme(3, "D", 900, 500), _forme(4, "H", 500, 100)],
            "connections": [{"id": 11, "fromId": 1, "toId": 3},
                            {"id": 12, "fromId": 1, "toId": 4},
                            {"id": 13, "fromId": 1, "toId": 88}],   # cible inconnue
        }
        final = _injecter(app, ids, carto, [_lien(EXTCO_ID, 502, "flux sortant")],
                          {502: "Aval B"})
        (forme,) = _injectees(final)
        assert forme["y"] > ORIGINE["y"] + ORIGINE["h"]
        conn = next(c for c in final["connections"] if c["toId"] == forme["id"])
        assert conn["fromId"] == 1
        assert conn["label"] == "flux sortant"   # repli sur la description du lien
        assert conn["style"] == "dashed"

    def test_forme_decalee_quand_la_place_est_occupee(self, app, ids):
        # Position de base à gauche : x = 500-160-110 = 230, y = 500.
        carto = {
            "nextId": 100,
            "shapes": [ORIGINE, _forme(9, "Obstacle", 230, 500)],
            "connections": [],
        }
        final = _injecter(app, ids, carto, [_lien(501, EXTCO_ID)], {501: "Amont C"})
        (forme,) = _injectees(final)
        assert forme["x"] == 230
        assert forme["y"] != 500, "la forme injectée chevauche l'obstacle"

    def test_forme_decalee_horizontalement_en_haut(self, app, ids):
        # Sortie forcée en haut (droite déjà prise) ; base : x=500, y=500-60-80=360.
        carto = {
            "nextId": 100,
            "shapes": [ORIGINE, _forme(3, "D", 900, 500), _forme(9, "Obstacle", 500, 360)],
            "connections": [{"id": 11, "fromId": 1, "toId": 3}],
        }
        final = _injecter(app, ids, carto, [_lien(EXTCO_ID, 502)], {502: "Aval H"})
        (forme,) = _injectees(final)
        assert forme["y"] == 360
        assert forme["x"] != 500

    def test_proprietes_et_label_copies_depuis_la_carto_source(self, app, ids, monkeypatch):
        # Les activités 501 / extco ont un shape_id dans la carto source.
        class _Q:
            def __init__(self, rows):
                self._rows = rows
            def filter_by(self, **kw):
                return _Q([r for r in self._rows if r.id == kw.get("id")])
            def filter(self, *a):
                return self
            def first(self):
                return self._rows[0] if self._rows else None
            def all(self):
                return self._rows
            def delete(self, **kw):
                return 0

        rows = [SimpleNamespace(id=EXTCO_ID, shape_id="s-ext"),
                SimpleNamespace(id=501, shape_id="s-501")]
        monkeypatch.setattr(am.Activities, "query", _Q(rows))
        source = {
            "shapes": [{"id": "s-501", "type": "decision", "w": 90, "h": 40,
                        "color": "#123456", "fontSize": 12}],
            "connections": [{"fromId": "s-501", "toId": "s-ext", "label": "bon de commande"}],
        }
        carto = {"nextId": 100, "shapes": [ORIGINE], "connections": []}
        final = _injecter(app, ids, carto, [_lien(501, EXTCO_ID, "desc ignorée")],
                          {501: "Amont P"}, active_carto=source)
        (forme,) = _injectees(final)
        assert (forme["type"], forme["w"], forme["h"], forme["color"], forme["fontSize"]) \
            == ("decision", 90.0, 40.0, "#123456", 12.0)
        conn = next(c for c in final["connections"] if c["fromId"] == forme["id"])
        assert conn["label"] == "bon de commande"
        assert final["nextId"] == 102

    def test_rien_a_injecter_si_le_nom_existe_deja(self, app, ids):
        carto = {"nextId": 100, "shapes": [ORIGINE, _forme(2, "Deja La", 0, 0)],
                 "connections": []}
        final = _injecter(app, ids, carto, [_lien(501, EXTCO_ID)], {501: "deja la"})
        assert _injectees(final) == []
        assert final["nextId"] == 100

    def test_anciennes_injections_de_la_meme_source_sont_remplacees(self, app, ids):
        ancienne = _forme(50, "Amont X", 0, 0, crossCartoImport=True,
                          crossCartoSource="Carto Source")
        carto = {"nextId": 100, "shapes": [ORIGINE, ancienne],
                 "connections": [{"id": 51, "fromId": 50, "toId": 1}]}
        final = _injecter(app, ids, carto, [_lien(501, EXTCO_ID)], {501: "Amont X"})
        injectees = _injectees(final)
        assert len(injectees) == 1 and injectees[0]["id"] != 50
        assert all(c["id"] != 51 for c in final["connections"])

    def test_carto_illisible_n_explose_pas(self, app):
        origine = SimpleNamespace(optiqcarto_data="{pas du json")
        with app.app_context():
            assert am._inject_extco_shapes_in_origin_carto(
                origine, SimpleNamespace(shape_id=1), [], EXTCO_ID, {}, "S") is None
        assert origine.optiqcarto_data == "{pas du json"

    def test_origine_sans_forme_correspondante_ne_change_rien(self, app, ids):
        carto = {"nextId": 100, "shapes": [_forme(7, "Autre", 0, 0)], "connections": []}
        final = _injecter(app, ids, carto, [_lien(501, EXTCO_ID)], {501: "Amont"})
        assert final == carto


# ─────────────────────────────────────────────────────────────────────────────
# Connexions, resync
# ─────────────────────────────────────────────────────────────────────────────

class TestConnexionsResiduel:

    def test_preview_connections_chemin_nominal(self, app, auth_client, actif, monkeypatch):
        eid = actif()
        with app.app_context():
            from Code.models.models import Activities
            from Code.extensions import db
            db.session.add_all([Activities(entity_id=eid, name="Achat", description=""),
                                Activities(entity_id=eid, name="Stock", description="")])
            db.session.commit()
        conns = [
            {"source_name": "Achat", "target_name": "Stock",
             "data_name": "Bon", "data_type": "nourrissante"},
            {"source_name": "Achat", "target_name": "Fantome",
             "data_name": None, "data_type": None},
        ]
        monkeypatch.setattr(am, "parse_vsdx_connections", lambda p: (conns, []))
        r = auth_client.post("/activities/preview-connections",
                             data={"file": (io.BytesIO(b"PK"), "x.vsdx")},
                             content_type="multipart/form-data")
        assert r.status_code == 200
        j = r.get_json()
        assert (j["total_connections"], j["valid_connections"], j["invalid_connections"]) \
            == (2, 1, 1)
        assert [c["valid"] for c in j["connections"]] == [True, False]
        assert "Fantome" in j["missing_activities"]

    def test_preview_connections_erreurs_de_parse_400(self, auth_client, actif, monkeypatch):
        actif()
        monkeypatch.setattr(am, "parse_vsdx_connections", lambda p: ([], ["page vide"]))
        r = auth_client.post("/activities/preview-connections",
                             data={"file": (io.BytesIO(b"PK"), "x.vsdx")},
                             content_type="multipart/form-data")
        assert r.status_code == 400
        assert r.get_json()["errors"] == ["page vide"]

    def test_list_connections_sans_entite_active_renvoie_liste_vide(self, auth_client, monkeypatch):
        monkeypatch.setattr(am, "get_active_entity", lambda: None)
        r = auth_client.get("/activities/list-connections")
        assert r.status_code == 200
        assert r.get_json() == {"connections": []}

    def test_list_connections_affiche_le_nom_de_la_donnee_source(self, app, auth_client, actif):
        eid = actif()
        with app.app_context():
            from Code.models.models import Activities, Data, Link
            from Code.extensions import db
            a = Activities(entity_id=eid, name="Cible", description="")
            d = Data(entity_id=eid, name="Facture fournisseur", type="nourrissante")
            db.session.add_all([a, d])
            db.session.flush()
            db.session.add(Link(entity_id=eid, source_data_id=d.id,
                                target_activity_id=a.id, type="nourrissante",
                                description="ignorée"))
            db.session.add(Link(entity_id=eid, source_data_id=987654321,
                                target_activity_id=a.id, type="pilotage",
                                description="repli description"))
            db.session.commit()
        j = auth_client.get("/activities/list-connections").get_json()
        assert j["count"] == 2
        noms = sorted(c["data_name"] for c in j["connections"])
        assert noms == ["Facture fournisseur", "repli description"]
        assert all(c["source"] == "?" and c["target"] == "Cible" for c in j["connections"])

    def test_resync_succes_renvoie_les_stats(self, auth_client, actif, tmp_path, monkeypatch):
        actif()
        svg = tmp_path / "c.svg"
        svg.write_text("<svg/>")
        monkeypatch.setattr(am, "check_svg_exists", lambda _eid: (True, str(svg)))
        monkeypatch.setattr(am, "sync_activities_with_svg",
                            lambda eid, p: {"added": 3, "renamed": 0, "deleted": 0})
        r = auth_client.post("/activities/resync")
        assert r.status_code == 200
        assert r.get_json() == {"status": "ok",
                                "sync": {"added": 3, "renamed": 0, "deleted": 0}}

    def test_resync_erreur_de_synchro_renvoie_500(self, auth_client, actif, tmp_path, monkeypatch):
        actif()
        monkeypatch.setattr(am, "check_svg_exists", lambda _eid: (True, str(tmp_path / "c.svg")))

        def _boom(eid, p):
            raise RuntimeError("svg corrompu")
        monkeypatch.setattr(am, "sync_activities_with_svg", _boom)
        r = auth_client.post("/activities/resync")
        assert r.status_code == 500
        assert r.get_json()["error"] == "svg corrompu"


# ─────────────────────────────────────────────────────────────────────────────
# Extraction / synchro SVG Visio
# ─────────────────────────────────────────────────────────────────────────────

SVG_VISIO = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:v="http://schemas.microsoft.com/visio/2003/SVGExtensions/">
  <g v:mID="11" v:layerMember="1"><text>Facturer</text></g>
  <g v:mID="12" v:layerMember="1"><text>Encaisser</text></g>
</svg>"""


class TestSyncSvgResiduel:

    def test_extract_fichier_illisible_renvoie_liste_vide(self, tmp_path):
        assert am.extract_activities_from_svg(str(tmp_path / "absent.svg")) == []

    def test_sync_rattache_l_activite_existante_par_nom(self, app, ids, tmp_path):
        eid = _entite(app, ids["user_id"])
        svg = tmp_path / "c.svg"
        svg.write_text(SVG_VISIO, encoding="utf-8")
        try:
            with app.app_context():
                from Code.models.models import Activities
                from Code.extensions import db
                existante = Activities(entity_id=eid, name="FACTURER", description="import excel")
                db.session.add(existante)
                db.session.commit()
                aid = existante.id

                stats = am.sync_activities_with_svg(eid, str(svg))
                assert stats["added"] == 1      # Encaisser
                assert stats["unchanged"] == 1  # Facturer rattachée
                acts = Activities.query.filter_by(entity_id=eid).all()
                assert len(acts) == 2
                assert db.session.get(Activities, aid).shape_id == "11"

                # Deuxième passage : rien ne bouge, tout est « inchangé »
                stats2 = am.sync_activities_with_svg(eid, str(svg))
                assert (stats2["added"], stats2["deleted"]) == (0, 0)
                assert stats2["unchanged"] + stats2["renamed"] == 2
                assert Activities.query.filter_by(entity_id=eid).count() == 2
        finally:
            _supprimer(app, eid)


# ─────────────────────────────────────────────────────────────────────────────
# Dépôt / remplacement de carto : échec de synchro
# ─────────────────────────────────────────────────────────────────────────────

class TestCopieCartoEchecSynchro:

    @pytest.fixture
    def synchro_en_panne(self, monkeypatch):
        import Code.routes.cartography_editor as ce

        def _boom(entity, diagram):
            raise RuntimeError("synchro impossible")
        monkeypatch.setattr(ce, "_sync_carto_to_db", _boom)

    def test_deposer_copie_remonte_l_erreur_de_synchro(self, app, ids, synchro_en_panne):
        src = _entite(app, ids["user_id"], carto={"shapes": [], "connections": []})
        copie_id = None
        try:
            with app.app_context():
                from Code.models.models import Entity
                from Code.extensions import db
                source = db.session.get(Entity, src)
                copie, erreur = am._deposer_copie(source, ids["user_id"], nom=_nom("Copie148"))
                copie_id = copie.id
                assert erreur == "synchro impossible"
                assert copie.optiqcarto_data == source.optiqcarto_data
                assert copie.is_active is False
        finally:
            _supprimer(app, *(i for i in (src, copie_id) if i))

    def test_remplacer_entite_remonte_l_erreur_de_synchro(self, app, ids, synchro_en_panne):
        src = _entite(app, ids["user_id"], carto={"shapes": [{"id": 1}], "connections": []})
        cible_id = _entite(app, ids["user_id"])
        try:
            with app.app_context():
                from Code.models.models import Entity
                from Code.extensions import db
                source = db.session.get(Entity, src)
                source.description = "desc source"
                cible = db.session.get(Entity, cible_id)
                nouveau = _nom("Renommee148")
                res, erreur = am._remplacer_entite(cible, source, nom=nouveau)
                assert erreur == "synchro impossible"
                assert res.name == nouveau
                assert res.description == "desc source"
                assert json.loads(res.optiqcarto_data)["shapes"] == [{"id": 1}]
        finally:
            _supprimer(app, src, cible_id)

    def test_carto_json_illisible_renvoie_none(self):
        assert am._carto_json("{oops") is None
        assert am._carto_json(None) is None
        assert am._carto_json('{"a": 1}') == {"a": 1}


# ─────────────────────────────────────────────────────────────────────────────
# Debug décisions
# ─────────────────────────────────────────────────────────────────────────────

def _vsdx(tmp_path, pages):
    chemin = tmp_path / "f.vsdx"
    with zipfile.ZipFile(chemin, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        for nom, contenu in pages.items():
            zf.writestr(nom, contenu)
    return str(chemin)


class TestDebugDecisionsResiduel:

    def test_read_vsdx_page_xml_prend_la_premiere_page_triee(self, tmp_path):
        p = _vsdx(tmp_path, {"visio/pages/page2.xml": "<deux/>",
                             "visio/pages/page1.xml": "<un/>",
                             "visio/pages/pages.xml.rels": "<x/>"})
        assert am._read_vsdx_page_xml(p) == "<un/>"

    def test_read_vsdx_page_xml_sans_page_leve_valueerror(self, tmp_path):
        p = _vsdx(tmp_path, {"visio/document.xml": "<d/>"})
        with pytest.raises(ValueError, match="Aucune page"):
            am._read_vsdx_page_xml(p)

    @pytest.fixture
    def unlink_en_echec(self, monkeypatch):
        vus = []

        def _refus(p):
            vus.append(p)
            raise OSError("fichier verrouillé")
        monkeypatch.setattr(am.os, "unlink", _refus)
        return vus

    def test_analyze_file_tolere_un_temp_non_supprimable(self, auth_client, monkeypatch, unlink_en_echec):
        monkeypatch.setattr(am, "extract_decisions_from_vsdx", lambda p: {"decisions": ["d1"]})
        r = auth_client.post("/activities/api/debug-decisions/analyze-file",
                             data={"vsdx": (io.BytesIO(b"PK"), "a.vsdx")},
                             content_type="multipart/form-data")
        assert r.status_code == 200
        assert r.get_json() == {"vsdx": {"decisions": ["d1"]}}
        assert len(unlink_en_echec) == 1
        os.remove(unlink_en_echec[0]) if os.path.exists(unlink_en_echec[0]) else None

    def test_analyze_file_ai_tolere_un_temp_non_supprimable(self, auth_client, monkeypatch, unlink_en_echec):
        monkeypatch.setattr(am, "extract_decisions_from_vsdx", lambda p: {"decisions": []})
        monkeypatch.setattr(am, "_ai_extract_decisions",
                            lambda res, nom: {"ai": True, "nom": nom})
        r = auth_client.post("/activities/api/debug-decisions/analyze-file/ai",
                             data={"vsdx": (io.BytesIO(b"PK"), "b.vsdx")},
                             content_type="multipart/form-data")
        assert r.status_code == 200
        assert r.get_json() == {"ai": True, "nom": "b.vsdx"}
        assert len(unlink_en_echec) == 1
        os.remove(unlink_en_echec[0]) if os.path.exists(unlink_en_echec[0]) else None

    def test_debug_decisions_legacy_lit_le_vsdx_de_l_entite(self, auth_client, actif, tmp_path, monkeypatch):
        eid = actif()
        f = tmp_path / "connections.vsdx"
        f.write_bytes(b"PK")
        monkeypatch.setattr(am, "check_vsdx_exists", lambda _eid: (True, str(f)))
        monkeypatch.setattr(am, "extract_decisions_from_vsdx",
                            lambda p: {"decisions": [{"label": "OK ?"}], "total_shapes": 4})
        r = auth_client.get("/activities/api/debug-decisions")
        assert r.status_code == 200
        j = r.get_json()
        assert j["entity_id"] == eid
        assert j["has_vsdx"] is True
        assert j["vsdx"]["total_shapes"] == 4
