# tests/test_153_vsdx_decisions_residuel.py
"""
Page : Import VSDX — extraction des losanges de décision (branches résiduelles).

`test_43_vsdx_parsers.py` couvre les helpers XML et le chemin nominal de
`vsdx_decision_extractor`. Restaient sans test : la page XML illisible, les
formes sans ID, les connexions incomplètes, le rattachement d'un badge
« Oui/Non » par proximité quand une forme n'a pas de coordonnées, les losanges
« posés sur une ligne » sans coordonnées ou au-dessus d'un connecteur déjà
découpé, et les cas dégénérés de l'inférence géométrique Oui/Non (connecteur
de longueur nulle, repli à 90°).

Fonctions pures : aucune base, aucun état partagé.
"""
import pytest

from Code.routes.vsdx_decision_extractor import _infer_oui_non, _parse_page

pytestmark = pytest.mark.vsdx_parsers

_NS = "http://schemas.microsoft.com/office/visio/2012/main"
_MASTERS = {"1": "decision"}


def _forme(sid=None, x=None, y=None, losange=False, texte=None, **cellules):
    attrs = f' ID="{sid}"' if sid is not None else ""
    if losange:
        attrs += ' Master="1"'
    cells = ""
    if x is not None:
        cells += f'<Cell N="PinX" V="{x}"/>'
    if y is not None:
        cells += f'<Cell N="PinY" V="{y}"/>'
    for nom, val in cellules.items():
        cells += f'<Cell N="{nom}" V="{val}"/>'
    txt = f"<Text>{texte}</Text>" if texte is not None else ""
    return f"<Shape{attrs}>{cells}{txt}</Shape>"


def _lien(de, cellule, vers):
    a = f' FromSheet="{de}"' if de else ""
    a += f' FromCell="{cellule}"' if cellule else ""
    a += f' ToSheet="{vers}"' if vers else ""
    return f"<Connect{a}/>"


def _page(formes, liens=()):
    return (f'<PageContents xmlns="{_NS}"><Shapes>{"".join(formes)}</Shapes>'
            f'<Connects>{"".join(liens)}</Connects></PageContents>').encode("utf-8")


def _analyser(xml):
    res = {"decisions": [], "total_shapes": 0, "total_connectors": 0, "errors": []}
    _parse_page(xml, _MASTERS, res)
    return res


def _flux(a, connecteur, b):
    return [_lien(connecteur, "BeginX", a), _lien(connecteur, "EndX", b)]


# ---------------------------------------------------------------------------
# _parse_page — lecture défensive
# ---------------------------------------------------------------------------

class TestParsePageDefensif:

    def test_xml_illisible_est_signale_dans_les_erreurs(self):
        res = _analyser(b"<PageContents><pas ferme>")
        assert len(res["errors"]) == 1
        assert res["errors"][0].startswith("XML parse error")
        assert res["decisions"] == []

    def test_forme_sans_id_est_comptee_mais_ignoree(self):
        res = _analyser(_page([_forme(None, 1, 1, losange=True)]))
        assert res["total_shapes"] == 1
        assert res["decisions"] == []

    def test_connexion_sans_feuille_cible_est_ignoree(self):
        formes = [_forme("A", 0, 0, texte="Début"), _forme("D", 2, 0, losange=True),
                  _forme("B", 4, 0, texte="Fin"), _forme("C1"), _forme("C2")]
        liens = _flux("A", "C1", "D") + _flux("D", "C2", "B") + [_lien("C9", "BeginX", None)]
        res = _analyser(_page(formes, liens))
        assert res["total_connectors"] == 5
        (dec,) = res["decisions"]
        assert [c["to_id"] for c in dec["outgoing"]] == ["B"]
        assert [c["from_id"] for c in dec["incoming"]] == ["A"]


class TestBadgeParProximite:

    def _page_avec_badges(self):
        formes = [
            _forme("A", 0, 0), _forme("D", 2, 0, losange=True), _forme("B", 4, 0),
            _forme("C1"), _forme("C2"), _forme("C3"),
            _forme("BO", texte="Oui"),             # badge sans coordonnées
            _forme("BN", 3, 0.2, texte="Non"),     # badge près du milieu de C2
        ]
        liens = _flux("A", "C1", "D") + _flux("D", "C2", "B") + [_lien("C3", "BeginX", "A")]
        return _analyser(_page(formes, liens))

    def test_badge_proche_du_milieu_est_rattache_au_connecteur(self):
        (dec,) = self._page_avec_badges()["decisions"]
        assert [(c["to_id"], c["badge"]) for c in dec["outgoing"]] == [("B", "Non")]

    def test_badge_sans_coordonnees_n_est_rattache_a_rien(self):
        (dec,) = self._page_avec_badges()["decisions"]
        assert all(c["badge"] != "Oui" for c in dec["incoming"] + dec["outgoing"])


class TestLosangePoseSurUneLigne:

    def test_losange_sans_coordonnees_n_est_pas_decoupe(self):
        formes = [_forme("A", 0, 0), _forme("B", 4, 0), _forme("C1"),
                  _forme("D", losange=True)]
        res = _analyser(_page(formes, _flux("A", "C1", "B")))
        (dec,) = res["decisions"]
        assert dec["splice"] is True
        assert dec["incoming"] == [] and dec["outgoing"] == []

    def test_losange_sur_la_ligne_coupe_le_connecteur_en_deux(self):
        formes = [_forme("A", 0, 0), _forme("B", 4, 0), _forme("C1"),
                  _forme("D", 2, 0.1, losange=True)]
        res = _analyser(_page(formes, _flux("A", "C1", "B")))
        (dec,) = res["decisions"]
        assert [c["from_id"] for c in dec["incoming"]] == ["A"]
        assert [(c["to_id"], c["_orig_conn_id"]) for c in dec["outgoing"]] == [("B", "C1")]
        assert dec["outgoing"][0]["inferred_badge"] == "Oui"

    def test_connecteurs_degeneres_ou_incomplets_sont_ignores(self):
        formes = [
            _forme("A", 0, 0), _forme("B", 4, 0), _forme("E", 2, 0),
            _forme("F", 2, 0),                       # E et F confondus
            _forme("C1"), _forme("C2"), _forme("C3"),
            _forme("D", 2, 3, losange=True),         # loin de toute ligne
        ]
        liens = (_flux("A", "C1", "B") + _flux("E", "C2", "F")
                 + [_lien("C3", "BeginX", "A")])
        (dec,) = _analyser(_page(formes, liens))["decisions"]
        assert dec["incoming"] == [] and dec["outgoing"] == []

    def test_connecteur_deja_decoupe_n_est_pas_redecoupe(self):
        # Un losange sur la ligne, plusieurs losanges hors ligne : ceux traités
        # après le découpage rencontrent le demi-connecteur synthétique, qui ne
        # doit plus jamais être redécoupé.
        hors = [_forme(f"H{i}", 10 + i, 10, losange=True) for i in range(6)]
        formes = [_forme("A", 0, 0), _forme("B", 4, 0), _forme("C1"),
                  _forme("D", 2, 0, losange=True)] + hors
        res = _analyser(_page(formes, _flux("A", "C1", "B")))
        par_id = {d["id"]: d for d in res["decisions"]}
        assert [c["to_id"] for c in par_id["D"]["outgoing"]] == ["B"]
        for i in range(6):
            assert par_id[f"H{i}"]["incoming"] == par_id[f"H{i}"]["outgoing"] == []


# ---------------------------------------------------------------------------
# _infer_oui_non — cas dégénérés
# ---------------------------------------------------------------------------

def _info(**formes):
    out = {}
    for sid, val in formes.items():
        if len(val) == 2:
            out[sid] = {"pin_x": val[0], "pin_y": val[1]}
        else:
            bx, by, ex, ey = val
            out[sid] = {"begin_x": bx, "begin_y": by, "end_x": ex, "end_y": ey}
    return out


class TestInferOuiNonDegenere:

    def test_connecteur_d_origine_de_longueur_nulle_reste_sans_badge(self):
        info = _info(S=(0, 1), D=(1, 1), T=(2, 1), CZ=(2, 2, 2, 2))
        dec = {"id": "D", "incoming": [{"from_id": "S"}],
               "outgoing": [{"to_id": "T"}, {"to_id": "X", "_orig_conn_id": "CZ"}]}
        _infer_oui_non([dec], info)
        assert [c["inferred_badge"] for c in dec["outgoing"]] == ["Oui", ""]

    def test_repli_a_90_degres_quand_aucun_oui_a_45(self):
        # Flux entrant vers +x ; une sortie à 45° tout juste (Non à 45°, Oui au
        # repli 90°), une sortie dégénérée qui reste vide, une sortie arrière.
        info = _info(S=(0, 1), D=(1, 1), R=(-3, 1),
                     C45=(1, 1, 2, 2), CZ=(3, 3, 3, 3))
        dec = {"id": "D", "incoming": [{"from_id": "S"}],
               "outgoing": [{"to_id": "Y", "_orig_conn_id": "C45"},
                            {"to_id": "Z", "_orig_conn_id": "CZ"},
                            {"to_id": "R"}]}
        _infer_oui_non([dec], info)
        assert [c["inferred_badge"] for c in dec["outgoing"]] == ["Oui", "", "Non"]
