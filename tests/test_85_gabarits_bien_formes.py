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


# ══════════════════════════════════════════════════════════════════════════
#  Les feuilles de style tiennent debout
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Une règle CSS qu'on n'a pas fermée n'est pas une faute locale : le
# navigateur AVALE tout ce qui suit dans le bloc resté ouvert, et la page perd
# sa mise en forme ENTIÈRE. C'est arrivé le 2026-10-29 sur `hub/static/hub.css`
# — une règle de palette insérée avant `.page--ci{…`, qui tient sur DEUX
# lignes : la seconde ligne et l'accolade manquaient, et tout le hub s'est
# affiché en HTML nu (liens soulignés, icônes noires, police par défaut).
#
# ⚠️ Et le test qui aurait dû le voir cherchait la PRÉSENCE d'une chaîne
# (« `.page--courrier` est bien là »), pas la VALIDITÉ du fichier. Une
# insertion se vérifie sur la structure, exactement comme l'équilibre des
# `<div>` et des commentaires plus haut.

CSS_APP = os.path.join(RACINE, "static")
CSS_HUB = os.path.join(RACINE, "hub", "static")


def _feuilles(dossier):
    if not os.path.isdir(dossier):
        return []
    trouves = []
    for racine, _dirs, noms in os.walk(dossier):
        for nom in noms:
            if nom.endswith(".css"):
                trouves.append(os.path.join(racine, nom))
    return sorted(trouves)


def _analyser_css(src):
    """Rend (écart, incidents) : l'écart d'accolades, et les règles ouvertes
    DANS une autre règle.

    Les commentaires et les chaînes sont retirés d'abord — une accolade dans
    un `content: "{"` ou une `url(...)` n'est pas une accolade de structure.
    Seules les at-règles (`@media`, `@supports`) ont le droit d'en contenir
    d'autres.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', '""', src)

    profondeur, ligne = 0, 1
    ouverts, incidents, selecteur = [], [], []
    for ch in src:
        if ch == "\n":
            ligne += 1
        if ch == "{":
            sel = "".join(selecteur).strip().split("\n")[-1].strip()
            if profondeur > 0 and ouverts and not ouverts[-1][1].startswith("@"):
                incidents.append((ligne, sel, ouverts[-1][0], ouverts[-1][1]))
            ouverts.append((ligne, sel))
            profondeur += 1
            selecteur = []
        elif ch == "}":
            profondeur -= 1
            if ouverts:
                ouverts.pop()
            selecteur = []
        else:
            selecteur.append(ch)
    return profondeur, incidents


def test_il_y_a_des_feuilles_a_relire():
    """Garde-fou de volume, comme pour les gabarits."""
    if not os.path.isdir(CSS_APP):
        pytest.skip("static/ absent (arbre d'image)")
    assert len(_feuilles(CSS_APP)) > 10


@pytest.mark.parametrize("chemin", _feuilles(CSS_APP) + _feuilles(CSS_HUB))
def test_chaque_feuille_de_style_ferme_ses_regles(chemin):
    import io
    src = io.open(chemin, encoding="utf-8").read()
    ecart, incidents = _analyser_css(src)
    nom = os.path.relpath(chemin, RACINE)
    assert ecart == 0, (
        "%s : %d accolade(s) %s — tout ce qui suit la règle restée ouverte "
        "est avalé, et la page perd sa mise en forme entière"
        % (nom, abs(ecart), "non fermée(s)" if ecart > 0 else "en trop"))
    assert not incidents, "\n".join(
        "%s:%d — la règle « %s » s'ouvre DANS « %s » (ligne %d), qui n'a "
        "jamais été fermée" % (nom, l, sel or "?", psel or "?", pl)
        for l, sel, pl, psel in incidents)
