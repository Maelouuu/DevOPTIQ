# -*- coding: utf-8 -*-
"""Les gabarits sont bien formés — les défauts qu'aucun autre test ne voit.

⚠️ Un commentaire HTML dont on a retiré la première ligne laisse sa fin
AFFICHÉE en clair : « on y donne les statuts, on doit y lire ce qu'ils
ouvrent. --> » s'est retrouvé en haut de la page RH après un nettoyage de
lignes. Rien ne plantait, aucun test de traduction ne le relevait (la phrase
n'est dans aucun catalogue, et n'a pas d'accent) : seul un œil le voyait.
"""
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARITS = os.path.join(RACINE, "Code", "routes", "templates")


def _gabarits():
    """Tous les gabarits .html, y compris ceux des sous-dossiers (`ui/`,
    `test_panel/`…) : un `os.listdir` à plat les laissait hors de portée de
    CE contrôle-là — silencieusement, comme le défaut qu'il existe pour
    attraper."""
    if not os.path.isdir(GABARITS):
        return []
    trouves = []
    for racine, _dirs, noms in os.walk(GABARITS):
        for nom in noms:
            if nom.endswith(".html"):
                trouves.append(os.path.relpath(os.path.join(racine, nom), GABARITS))
    return sorted(trouves)


def test_il_y_a_des_gabarits_a_relire():
    """Garde-fou de volume : si le dossier bouge, les contrôles ne liraient
    plus rien et passeraient au vert en silence."""
    if not os.path.isdir(GABARITS):
        pytest.skip("gabarits absents (arbre d'image)")
    assert len(_gabarits()) > 40


@pytest.mark.parametrize("nom", _gabarits())
def test_chaque_commentaire_html_est_ferme_et_ouvert(nom):
    import io
    src = io.open(os.path.join(GABARITS, nom), encoding="utf-8").read()
    # Les commentaires Jinja ({# … #}) peuvent contenir « --> » librement.
    src = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    ouverts = src.count("<!--")
    fermes = src.count("-->")
    assert ouverts == fermes, (
        "%s : %d « <!-- » pour %d « --> » — un morceau de commentaire "
        "s'affiche en clair" % (nom, ouverts, fermes))
