# -*- coding: utf-8 -*-
"""Import Visio historique : Code/scripts/extract_visio.py (+ /activities/update-cartography).

Le module supprime des activités, des données et VIDE la table `links` : il ne
tourne JAMAIS sur la base partagée de la suite (scope=session). Chaque test
reçoit une application Flask jetable avec sa propre base SQLite en mémoire
(`base_isolee`), et `VisioFile` est remplacé par un faux fichier construit en
mémoire — aucun .vsdx réel n'est lu.

Relevé le 19/11/2026 : l'import n'avait AUCUN périmètre. Lancé depuis
`GET /activities/update-cartography` par n'importe quel compte ayant une entité
active (même en simple lecture), il vidait les liens de TOUTES les entités et
supprimait les activités issues d'un Visio des autres entités. Les classes
`TestPerimetreEntite` et `TestRouteUpdateCartography` tiennent la correction.
"""
import xml.etree.ElementTree as ET

import pytest
from flask import Flask

from Code.extensions import db
from Code.scripts import extract_visio as ev

pytestmark = pytest.mark.vsdx_parsers

NS = "http://schemas.microsoft.com/office/visio/2012/main"


# ---------------------------------------------------------------------------
# Faux objets Visio
# ---------------------------------------------------------------------------

class FakeShape:
    def __init__(self, sid, text, cells=None):
        self.ID = sid
        self.text = text
        root = ET.Element("{%s}Shape" % NS)
        for n, attrs in (cells or {}).items():
            c = ET.SubElement(root, "{%s}Cell" % NS)
            c.set("N", n)
            for k, v in attrs.items():
                c.set(k, v)
        self.xml = root


def activite(sid, text, fill=None):
    cells = {"LayerMember": {"V": "1"}}
    if fill is not None:
        cells["FillPattern"] = {"V": fill}
    return FakeShape(sid, text, cells)


def resultat(sid, text):
    return FakeShape(sid, text, {"LayerMember": {"V": "6"}})


def retour(sid, text):
    return FakeShape(sid, text, {"LayerMember": {"V": "8"}})


def connecteur(sid, text, src, dst, layer="10"):
    cells = {"LayerMember": {"V": layer}}
    if src is not None:
        cells["BeginX"] = {"F": "PAR(PNT(Sheet.%s!Connections.X1,0))" % src}
    if dst is not None:
        cells["EndX"] = {"F": "PAR(PNT(Sheet.%s!Connections.X1,0))" % dst}
    return FakeShape(sid, text, cells)


class FakePage:
    def __init__(self, shapes, name="Page-1"):
        self.name = name
        self.all_shapes = shapes


class FakeVisio:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture()
def base_isolee():
    """Application jetable + base SQLite mémoire propre à ce test."""
    app = Flask("extract_visio_isole")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def faux_vsdx(tmp_path, monkeypatch):
    """Renvoie une fonction (shapes) -> chemin d'un faux .vsdx lu par FakeVisio."""
    chemin = tmp_path / "carto.vsdx"
    chemin.write_bytes(b"pas un vrai visio")
    contenu = {"pages": []}
    monkeypatch.setattr(ev, "VisioFile", lambda path: FakeVisio(contenu["pages"]))

    def _faire(*pages):
        contenu["pages"] = [FakePage(p) for p in pages]
        return str(chemin)
    return _faire


@pytest.fixture(autouse=True)
def _globales_propres():
    yield
    ev._current_entity_id = None
    for lst in (ev.activity_mapping, ev.data_mapping, ev.return_mapping,
                ev.connectors_list, ev.link_summaries, ev.rename_summaries):
        lst.clear()


def _entite(nom):
    from Code.models.models import Entity
    e = Entity(name=nom, description="t155")
    db.session.add(e)
    db.session.commit()
    return e.id


# ---------------------------------------------------------------------------
# Fonctions pures
# ---------------------------------------------------------------------------

class TestFonctionsPures:

    def test_standardize_id_entier(self):
        assert ev.standardize_id(42) == "42"

    def test_standardize_id_chaine_numerique(self):
        assert ev.standardize_id(" 7 ") == "7"

    def test_standardize_id_non_numerique_minuscule(self):
        assert ev.standardize_id(" AbC ") == "abc"

    def test_extract_shape_id_formule_valide(self):
        assert ev.extract_shape_id("PAR(PNT(Sheet.12!Connections.X1,0))") == 12

    def test_extract_shape_id_sans_sheet(self):
        assert ev.extract_shape_id("_WALKGLUE(BegTrigger)") is None

    def test_extract_shape_id_none(self):
        assert ev.extract_shape_id(None) is None

    def test_extract_shape_id_numero_illisible(self):
        assert ev.extract_shape_id("Sheet.xx!Connections") is None

    def test_get_layer_mappe_le_calque(self):
        assert ev.get_layer(activite(1, "A")) == "Activity"

    def test_get_layer_calque_inconnu_rendu_brut(self):
        assert ev.get_layer(FakeShape(1, "x", {"LayerMember": {"V": "3"}})) == "3"

    def test_get_layer_absent(self):
        assert ev.get_layer(FakeShape(1, "x")) is None

    def test_get_fill_pattern_present(self):
        assert ev.get_fill_pattern(activite(1, "A", fill="2")) == "2"

    def test_get_fill_pattern_absent(self):
        assert ev.get_fill_pattern(activite(1, "A")) is None

    def test_analyze_connections_les_deux_bouts(self):
        assert ev.analyze_connections(connecteur(5, "d", 1, 2)) == {"from_id": 1, "to_id": 2}

    def test_analyze_connections_bout_libre(self):
        assert ev.analyze_connections(connecteur(5, "d", 1, None)) == {"from_id": 1, "to_id": None}

    def test_resolve_visio_id_vide(self):
        assert ev.resolve_visio_id(None) == (None, None)

    def test_resolve_visio_id_inconnu(self):
        assert ev.resolve_visio_id(999) == (None, None)


class TestProcessShapeAiguillage:

    def test_calque_ignore_legende(self, monkeypatch):
        appels = []
        monkeypatch.setattr(ev, "add_or_update_activity", lambda *a, **k: appels.append(a))
        ev.process_shape(FakeShape(1, "x", {"LayerMember": {"V": "légende"}}))
        assert appels == []

    def test_sans_calque_ignore(self, monkeypatch):
        appels = []
        monkeypatch.setattr(ev, "add_or_update_activity", lambda *a, **k: appels.append(a))
        ev.process_shape(FakeShape(1, "x"))
        assert appels == []

    def test_calque_non_traite_journalise(self, capsys):
        ev.process_shape(FakeShape(1, "Zone", {"LayerMember": {"V": "4"}}))
        assert "Calque '4' non traité" in capsys.readouterr().out

    def test_calque_non_traite_sans_texte(self, capsys):
        ev.process_shape(FakeShape(1, None, {"LayerMember": {"V": "4"}}))
        assert "'??'" in capsys.readouterr().out

    def test_resultat_aiguille_avec_is_result(self, monkeypatch):
        vus = []
        monkeypatch.setattr(ev, "add_or_update_activity",
                            lambda shape, is_result=False: vus.append(is_result))
        ev.process_shape(resultat(1, "R"))
        assert vus == [True]


# ---------------------------------------------------------------------------
# Écritures en base (base isolée)
# ---------------------------------------------------------------------------

class TestActivites:

    def test_creation_activite(self, base_isolee):
        from Code.models.models import Activities
        ev.add_or_update_activity(activite(3, "  Préparer  "))
        a = Activities.query.filter_by(shape_id="3").one()
        assert (a.name, a.is_result) == ("Préparer", False)
        assert ev.activity_mapping["3"] == a.id

    def test_texte_vide_nom_par_defaut(self, base_isolee):
        from Code.models.models import Activities
        ev.add_or_update_activity(activite(4, None))
        ev.add_or_update_activity(resultat(5, None), is_result=True)
        assert Activities.query.filter_by(shape_id="4").one().name == "Activité sans nom"
        assert Activities.query.filter_by(shape_id="5").one().name == "Résultat sans nom"

    def test_remplissage_non_plein_force_resultat(self, base_isolee):
        from Code.models.models import Activities
        ev.add_or_update_activity(activite(6, "Livrer", fill="2"))
        assert Activities.query.filter_by(shape_id="6").one().is_result is True

    def test_renommage_et_bascule_resultat(self, base_isolee):
        from Code.models.models import Activities
        ev.add_or_update_activity(activite(7, "Ancien"))
        ev.add_or_update_activity(activite(7, "Nouveau"), is_result=True)
        a = Activities.query.filter_by(shape_id="7").one()
        assert (a.name, a.is_result) == ("Nouveau", True)
        assert ("Ancien", "Nouveau") in ev.rename_summaries

    def test_inchangee_rien_a_journaliser(self, base_isolee, capsys):
        ev.add_or_update_activity(activite(8, "Stable"))
        capsys.readouterr()
        ev.add_or_update_activity(activite(8, "Stable"))
        assert "pas de modif" in capsys.readouterr().out
        assert ev.rename_summaries == []


class TestRetoursEtConnecteurs:

    def test_creation_retour(self, base_isolee):
        from Code.models.models import Data
        ev.add_or_update_return(retour(10, "Retour client"))
        d = Data.query.filter_by(shape_id="10").one()
        assert (d.type, d.name) == ("Retour", "Retour client")
        assert ev.return_mapping["10"] == d.id

    def test_retour_sans_texte_ne_plante_pas(self, base_isolee):
        """Avant correction : `shape.text.strip()` sur None → AttributeError."""
        from Code.models.models import Data
        ev.add_or_update_return(retour(11, None))
        assert Data.query.filter_by(shape_id="11").one().name == "Retour sans nom"

    def test_renommage_retour(self, base_isolee):
        from Code.models.models import Data
        ev.add_or_update_return(retour(12, "R1"))
        ev.add_or_update_return(retour(12, "R2"))
        assert Data.query.filter_by(shape_id="12").one().name == "R2"
        assert ("R1", "R2") in ev.rename_summaries

    def test_fusion_des_retours_homonymes(self, base_isolee):
        from Code.models.models import Data
        ev.add_or_update_return(retour(13, "Même"))
        ev.add_or_update_return(retour(14, "Même"))
        restants = Data.query.filter_by(type="Retour", name="Même").all()
        assert [d.shape_id for d in restants] == ["14"]

    def test_connecteur_declenchant_memorise(self, base_isolee):
        from Code.models.models import Data
        ev.store_connector_info(connecteur(20, "Bon de commande", 1, 2), "T link")
        d = Data.query.filter_by(shape_id="20").one()
        assert (d.type, d.layer) == ("déclenchante", "T link")
        c = ev.connectors_list[-1]
        assert (c["from_raw"], c["to_raw"], c["data_id"]) == (1, 2, d.id)

    def test_connecteur_nourrissant_sans_texte(self, base_isolee):
        from Code.models.models import Data
        ev.store_connector_info(connecteur(21, None, 1, 2, layer="9"), "N link")
        d = Data.query.filter_by(shape_id="21").one()
        assert (d.type, d.name) == ("nourrissante", "Donnée sans nom")

    def test_connecteur_renomme(self, base_isolee):
        from Code.models.models import Data
        ev.store_connector_info(connecteur(22, "v1", 1, 2), "T link")
        ev.store_connector_info(connecteur(22, "v2", 1, 2), "T link")
        assert Data.query.filter_by(shape_id="22").one().name == "v2"
        assert ("v1", "v2") in ev.rename_summaries


class TestLiens:

    def test_resolve_retour_vers_activite_homonyme(self, base_isolee):
        ev.add_or_update_activity(activite(1, "Facturer"))
        ev.add_or_update_return(retour(2, "Facturer"))
        assert ev.resolve_visio_id(2) == ("activity", ev.activity_mapping["1"])

    def test_resolve_retour_sans_homonyme_reste_donnee(self, base_isolee):
        ev.add_or_update_return(retour(2, "Orphelin"))
        assert ev.resolve_visio_id(2) == ("data", ev.return_mapping["2"])

    def test_resolve_connecteur_comme_donnee(self, base_isolee):
        ev.store_connector_info(connecteur(9, "flux", 1, 2), "T link")
        assert ev.resolve_visio_id(9) == ("data", ev.data_mapping["9"])

    def test_create_single_link_activite_vers_donnee_puis_doublon(self, base_isolee, capsys):
        from Code.models.models import Link
        ev.add_or_update_activity(activite(1, "A"))
        ev.add_or_update_return(retour(2, "R"))
        aid, did = ev.activity_mapping["1"], ev.return_mapping["2"]
        ev.create_single_link(None, "flux", "déclenchante", "activity", aid, "data", did)
        ev.create_single_link(None, "flux", "déclenchante", "activity", aid, "data", did)
        assert Link.query.filter_by(source_activity_id=aid, target_data_id=did).count() == 1
        assert "Lien déjà existant" in capsys.readouterr().out

    def test_create_single_link_donnee_vers_activite(self, base_isolee):
        from Code.models.models import Link
        ev.add_or_update_activity(activite(1, "A"))
        ev.add_or_update_return(retour(2, "R"))
        aid, did = ev.activity_mapping["1"], ev.return_mapping["2"]
        ev.create_single_link(None, "retour", "nourrissante", "data", did, "activity", aid)
        lk = Link.query.one()
        assert (lk.source_data_id, lk.target_activity_id) == (did, aid)
        assert ev.link_summaries[-1] == ("retour", "nourrissante", "R", "A")

    def test_rebuild_ignore_partiels_boucles_et_inconnus(self, base_isolee, capsys):
        from Code.models.models import Link
        ev.add_or_update_activity(activite(1, "A"))
        ev.connectors_list.extend([
            {"data_id": 1, "data_name": "libre", "data_type": "déclenchante", "from_raw": 1, "to_raw": None},
            {"data_id": 1, "data_name": "boucle", "data_type": "déclenchante", "from_raw": 1, "to_raw": 1},
            {"data_id": 1, "data_name": "fantome", "data_type": "déclenchante", "from_raw": 1, "to_raw": 77},
        ])
        ev.rebuild_links_from_connectors()
        out = capsys.readouterr().out
        assert Link.query.count() == 0
        assert "partiel/boucle => 'libre'" in out
        assert "partiel/boucle => 'boucle'" in out
        assert "impossible => 'fantome'" in out

    def test_get_entity_name_cas_limites(self, base_isolee):
        assert ev.get_entity_name(None, "activity") == "??"
        assert ev.get_entity_name(9999, "activity") == "activité_inconnue"
        assert ev.get_entity_name(9999, "data") == "data_inconnue"
        assert ev.get_entity_name(1, "autre") == "inconnu"

    def test_cleanup_supprime_les_liens_orphelins(self, base_isolee):
        from Code.models.models import Link
        ev.add_or_update_activity(activite(1, "A"))
        aid = ev.activity_mapping["1"]
        db.session.execute(db.text("PRAGMA foreign_keys=OFF"))
        for kw in ({"source_activity_id": 9991, "target_activity_id": aid},
                   {"source_data_id": 9992, "target_activity_id": aid},
                   {"source_activity_id": aid, "target_activity_id": 9993},
                   {"source_activity_id": aid, "target_data_id": 9994}):
            db.session.add(Link(type="déclenchante", description="orph", **kw))
        db.session.add(Link(type="déclenchante", description="sain",
                            source_activity_id=aid, target_activity_id=aid))
        db.session.commit()
        ev.cleanup_orphan_links()
        assert [l.description for l in Link.query.all()] == ["sain"]


class TestProcessVisioFile:

    def test_fichier_introuvable(self, base_isolee, capsys, tmp_path):
        ev.process_visio_file(str(tmp_path / "absent.vsdx"))
        assert "Fichier Visio introuvable" in capsys.readouterr().out

    def test_import_complet_cree_activites_donnees_et_liens(self, base_isolee, faux_vsdx):
        from Code.models.models import Activities, Data, Link
        chemin = faux_vsdx([
            activite(1, "Commander"),
            resultat(2, "Livrer"),
            connecteur(3, "Bon de commande", 1, 2),
            connecteur(4, "Info stock", 2, 1, layer="9"),
            FakeShape(5, "Légende", {"LayerMember": {"V": "Color"}}),
        ])
        ev.process_visio_file(chemin)
        assert {a.name for a in Activities.query.all()} == {"Commander", "Livrer"}
        assert Data.query.count() == 2
        assert {l.description for l in Link.query.all()} == {"Bon de commande", "Info stock"}

    def test_reimport_supprime_les_formes_disparues(self, base_isolee, faux_vsdx):
        from Code.models.models import Activities, Data, Link
        ev.process_visio_file(faux_vsdx([
            activite(1, "A"), activite(2, "B"), connecteur(3, "flux", 1, 2)]))
        ev.process_visio_file(faux_vsdx([activite(1, "A")]))
        assert [a.name for a in Activities.query.all()] == ["A"]
        assert Data.query.count() == 0
        assert Link.query.count() == 0

    def test_print_summary_liens_et_renommages(self, base_isolee, faux_vsdx, capsys):
        ev.process_visio_file(faux_vsdx([activite(1, "A"), activite(2, "B"),
                                         connecteur(3, "flux", 1, 2)]))
        ev.process_visio_file(faux_vsdx([activite(1, "A2"), activite(2, "B"),
                                         connecteur(3, "flux", 1, 2)]))
        capsys.readouterr()
        ev.print_summary()
        out = capsys.readouterr().out
        assert "'flux' (déclenchante) : A2 -> B" in out
        assert "* 'A' => 'A2'" in out
        assert "CONFIRMATION" in out

    def test_print_summary_sans_lien(self, base_isolee, capsys):
        ev.print_summary()
        out = capsys.readouterr().out
        assert "Aucun lien créé" in out
        assert "Renommages" not in out


class TestPerimetreEntite:
    """Un import borné à une entité ne touche à rien d'autre."""

    def _autre_entite_peuplee(self):
        from Code.models.models import Activities, Data, Link
        eid = _entite("Voisine")
        a1 = Activities(name="V1", shape_id="1", entity_id=eid)
        a2 = Activities(name="V2", shape_id="2", entity_id=eid)
        d = Data(name="flux voisin", type="déclenchante", shape_id="3", entity_id=eid)
        db.session.add_all([a1, a2, d])
        db.session.flush()
        db.session.add(Link(type="déclenchante", description="voisin", entity_id=eid,
                            source_activity_id=a1.id, target_activity_id=a2.id))
        db.session.commit()
        return eid

    def test_import_d_une_entite_epargne_la_voisine(self, base_isolee, faux_vsdx):
        from Code.models.models import Activities, Data, Link
        voisine = self._autre_entite_peuplee()
        cible = _entite("Cible")
        ev.process_visio_file(faux_vsdx([activite(9, "Seule")]), entity_id=cible)
        assert Activities.query.filter_by(entity_id=voisine).count() == 2
        assert Data.query.filter_by(entity_id=voisine).count() == 1
        assert Link.query.filter_by(entity_id=voisine).count() == 1

    def test_meme_shape_id_dans_deux_entites_reste_distinct(self, base_isolee, faux_vsdx):
        from Code.models.models import Activities
        voisine = self._autre_entite_peuplee()
        cible = _entite("Cible")
        ev.process_visio_file(faux_vsdx([activite(1, "Mienne")]), entity_id=cible)
        assert Activities.query.filter_by(entity_id=voisine, shape_id="1").one().name == "V1"
        assert Activities.query.filter_by(entity_id=cible, shape_id="1").one().name == "Mienne"

    def test_les_objets_crees_portent_l_entite(self, base_isolee, faux_vsdx):
        from Code.models.models import Activities, Data, Link
        cible = _entite("Cible")
        ev.process_visio_file(faux_vsdx([activite(1, "A"), activite(2, "B"),
                                         retour(4, "R"), connecteur(3, "f", 1, 2)]),
                              entity_id=cible)
        assert {a.entity_id for a in Activities.query.all()} == {cible}
        assert {d.entity_id for d in Data.query.all()} == {cible}
        assert {l.entity_id for l in Link.query.all()} == {cible}

    def test_purge_des_liens_de_l_entite_y_compris_sans_entity_id(self, base_isolee, faux_vsdx):
        """Les liens hérités sans entity_id mais accrochés aux activités de la
        cible sont repris ; ceux de la voisine restent."""
        from Code.models.models import Activities, Link
        voisine = self._autre_entite_peuplee()
        cible = _entite("Cible")
        a = Activities(name="A", shape_id="1", entity_id=cible)
        db.session.add(a)
        db.session.flush()
        db.session.add(Link(type="déclenchante", description="hérité",
                            source_activity_id=a.id, target_activity_id=a.id))
        db.session.commit()
        ev.process_visio_file(faux_vsdx([activite(1, "A")]), entity_id=cible)
        assert [l.description for l in Link.query.all()] == ["voisin"]
        assert Link.query.filter_by(entity_id=voisine).count() == 1

    def test_retour_homonyme_resolu_dans_l_entite_seulement(self, base_isolee, faux_vsdx):
        from Code.models.models import Activities, Link
        voisine = self._autre_entite_peuplee()
        cible = _entite("Cible")
        db.session.add(Activities(name="Partagé", shape_id="50", entity_id=voisine))
        db.session.commit()
        ev.process_visio_file(faux_vsdx([activite(1, "A"), retour(2, "Partagé"),
                                         connecteur(3, "f", 1, 2)]), entity_id=cible)
        lk = Link.query.filter_by(entity_id=cible).one()
        assert lk.target_activity_id is None
        assert lk.target_data_id == ev.return_mapping["2"]

    def test_mode_autonome_reste_global(self, base_isolee, faux_vsdx):
        """Sans entity_id (script lancé à la main), comportement historique."""
        from Code.models.models import Activities
        self._autre_entite_peuplee()
        ev.process_visio_file(faux_vsdx([activite(9, "Seule")]))
        assert [a.name for a in Activities.query.all()] == ["Seule"]


class TestCreateAppAutonome:

    def test_create_app_pointe_sur_instance_locale(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = ev.create_app()
        attendu = tmp_path / "Code" / "instance"
        assert attendu.is_dir()
        assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///%s" % (attendu / "optiq.db")

    def test_create_app_dossier_deja_present(self, tmp_path, monkeypatch):
        (tmp_path / "Code" / "instance").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        assert ev.create_app().config["SQLALCHEMY_TRACK_MODIFICATIONS"] is False


# ---------------------------------------------------------------------------
# Route GET /activities/update-cartography
# ---------------------------------------------------------------------------

@pytest.fixture()
def carto_lecture_seule(app, tmp_path):
    """Carto commune d'un autre compte + un compte `user` qui peut la lire."""
    from Code.models.models import Entity, User
    from Code.security import hash_password
    fichier = tmp_path / "commune.vsdx"
    fichier.write_bytes(b"x")
    with app.app_context():
        owner = User(first_name="T155", last_name="owner", email="t155.owner@devoptiq.com",
                     password=hash_password("Motdepasse123!"), status="admin")
        lecteur = User(first_name="T155", last_name="lecteur", email="t155.lecteur@devoptiq.com",
                       password=hash_password("Motdepasse123!"), status="user")
        db.session.add_all([owner, lecteur])
        db.session.flush()
        e = Entity(name="T155 commune", description="t155", owner_id=owner.id,
                   is_shared=True, svg_filename=str(fichier))
        db.session.add(e)
        db.session.commit()
        faits = {"entity_id": e.id, "lecteur_id": lecteur.id, "owner_id": owner.id}
    yield faits
    with app.app_context():
        Entity.query.filter_by(id=faits["entity_id"]).delete()
        User.query.filter(User.email.like("t155.%")).delete(synchronize_session=False)
        db.session.commit()


class TestRouteUpdateCartography:

    def test_lecteur_seul_recoit_403_et_l_import_ne_tourne_pas(self, app, carto_lecture_seule, monkeypatch):
        appels = []
        monkeypatch.setattr("Code.routes.activities_cartography.process_visio_file",
                            lambda *a, **k: appels.append((a, k)))
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = carto_lecture_seule["lecteur_id"]
            s["active_entity_id"] = carto_lecture_seule["entity_id"]
        r = c.get("/activities/update-cartography")
        assert r.status_code == 403
        assert appels == []

    def test_proprietaire_lance_l_import_borne_a_son_entite(self, app, carto_lecture_seule, monkeypatch):
        appels = []
        monkeypatch.setattr("Code.routes.activities_cartography.process_visio_file",
                            lambda path, entity_id=None: appels.append(entity_id))
        monkeypatch.setattr("Code.routes.activities_cartography.print_summary", lambda: None)
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = carto_lecture_seule["owner_id"]
            s["active_entity_id"] = carto_lecture_seule["entity_id"]
        r = c.get("/activities/update-cartography")
        assert r.status_code == 200
        assert appels == [carto_lecture_seule["entity_id"]]

    def test_sans_connexion_aucune_entite_400(self, app):
        r = app.test_client().get("/activities/update-cartography")
        assert r.status_code == 400
