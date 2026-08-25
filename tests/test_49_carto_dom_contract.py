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
