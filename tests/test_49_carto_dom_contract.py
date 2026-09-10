# tests/test_49_carto_dom_contract.py
"""
Contrat DOM entre editor.js et ses deux gabarits.

editor.js câble ses boutons sans garde :

    document.getElementById('btn-x').addEventListener(...)

Un id absent d'un gabarit lève donc une TypeError qui interrompt TOUT le reste
de l'initialisation — y compris le chargement de la carto. Le symptôme est
silencieux pour l'utilisateur : la page Cartographie affiche un cadre gris et
vide, alors que les données sont bien en base. C'est arrivé avec
« btn-export-carto », présent dans l'éditeur mais pas dans le viewer.

Le viewer est en lecture seule : il déclare des boutons vides (« stubs ») dont
le seul rôle est de satisfaire ce câblage. Ce test vérifie que la liste reste
complète des deux côtés.
"""
import os
import re

import pytest

pytestmark = pytest.mark.cartography_editor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITOR_JS = os.path.join(ROOT, "static", "optiqcarto", "editor.js")
TEMPLATES = [
    os.path.join(ROOT, "Code", "routes", "templates", "cartography_editor.html"),
    os.path.join(ROOT, "Code", "routes", "templates", "cartography_viewer.html"),
]

# document.getElementById('x').addEventListener  → déréférencement direct, sans
# `?.` ni test préalable : l'id DOIT exister dans le gabarit.
UNGUARDED = re.compile(
    r"""document\.getElementById\(\s*['"]([\w-]+)['"]\s*\)\s*\.addEventListener"""
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_les_gabarits_declarent_tous_les_ids_cables_sans_garde():
    ids = set(UNGUARDED.findall(_read(EDITOR_JS)))
    assert ids, "aucun câblage détecté — le motif recherché a changé"

    manquants = {}
    for path in TEMPLATES:
        html = _read(path)
        absents = sorted(i for i in ids if f'id="{i}"' not in html)
        if absents:
            manquants[os.path.basename(path)] = absents

    assert not manquants, (
        "ids câblés sans garde dans editor.js mais absents du gabarit :\n"
        + "\n".join(f"  {tpl} → {', '.join(v)}" for tpl, v in manquants.items())
        + "\nAjouter un bouton vide (stub) dans le gabarit, comme les autres."
    )


def test_le_viewer_expose_le_stub_export_carto():
    """Régression directe du cas rencontré : viewer figé sur un cadre gris."""
    html = _read(TEMPLATES[1])
    assert 'id="btn-export-carto"' in html


# ══════════════════════════════════════════════════════════════════════════
# Échelle de l'habillage — la barre d'outils déborde ou flotte selon l'écran
# ══════════════════════════════════════════════════════════════════════════
# La barre est ancrée à gauche ET à droite ; son contenu du milieu était dessiné
# en pixels fixes. Sur un portable il passait SOUS « Panneau » et « Propriétés »
# (mesuré : 68 px de chevauchement de chaque côté à 1180 px de large) ; sur un
# 27 pouces il occupait une bande étroite au milieu d'un grand vide. Un facteur
# unique, `--ui-k`, tient les deux bouts.

UI_SCALE_JS = os.path.join(ROOT, "static", "optiqcarto", "ui_scale.js")
STYLE_CSS = os.path.join(ROOT, "static", "optiqcarto", "style.css")


def test_les_deux_gabarits_chargent_le_facteur_d_echelle():
    for chemin in TEMPLATES:
        assert "optiqcarto/ui_scale.js" in _read(chemin), os.path.basename(chemin)


def test_le_facteur_est_borne_et_recalcule_au_redimensionnement():
    js = _read(UI_SCALE_JS)
    assert "--ui-k" in js
    assert "innerWidth" in js
    assert "addEventListener('resize'" in js
    # Sans bornes, une fenêtre étroite réduirait la barre jusqu'à l'illisible.
    assert "K_MIN" in js and "K_MAX" in js


def test_le_zoom_porte_sur_les_ENFANTS_de_la_barre():
    """Zoomer #toolbar lui-même réduirait aussi sa largeur : ancrée left/right,
    elle ne tiendrait plus toute la fenêtre."""
    css = _read(STYLE_CSS)
    assert "#toolbar > * { zoom: var(--ui-k); }" in css
    assert "--toolbar-h: calc(60px * var(--ui-k));" in css
    assert re.search(r"^#toolbar \{[^}]*zoom:", css, re.M) is None


def test_la_mini_map_ne_se_pose_pas_sur_la_pastille_de_zoom():
    """Les deux occupaient le coin bas-droit du canevas et se chevauchaient.
    Elles partagent le même bord droit, la mini map juste au-dessus."""
    css = _read(STYLE_CSS)
    assert "--corner-gap:" in css and "--zoom-pill-h:" in css
    mini = re.search(r"#carto-minimap \{[^}]*\}", css, re.S)
    assert mini, "#carto-minimap introuvable"
    bloc = mini.group(0)
    assert "right: var(--corner-gap);" in bloc
    assert "var(--zoom-pill-h)" in bloc, "la mini map doit se placer AU-DESSUS de la pastille"
