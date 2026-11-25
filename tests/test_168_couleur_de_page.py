# -*- coding: utf-8 -*-
"""Chaque page rend SA couleur, dérivés compris.

Les quatre dérivés de l'accent (`--pg-accent-soft`, `-softer`, `-border`,
`-glow`) étaient déclarés sur `:root` SEUL, où `--pg-accent` vaut encore le
gris par défaut `#64748b`. Une propriété personnalisée est substituée là où
elle est DÉCLARÉE, pas là où elle est employée : le gris était donc déjà cuit
dans leur valeur quand elle héritait aux dix pages.

Mesuré au navigateur avant le correctif, page Activités : `--pg-accent` valait
bien `#7c3aed`, mais `--pg-accent-soft` rendait
`color-mix(in srgb, #64748b 10%, #ffffff)`, et **272 éléments** de la page
rendaient exactement cette teinte grise. 212 lectures de ces quatre jetons
dans 8 feuilles lisaient donc un gris en croyant lire la couleur de la page.

Après : les neuf pages rendent leur propre teinte, et **0 élément sur 6821**
rend encore l'ancien gris.

⚠️ Le piège se reproduirait en silence à la première page ajoutée : le
sélecteur poserait `--pg-accent` sans les dérivés, et rien ne crierait. D'où
le cliquet ci-dessous, qui compare les DEUX listes de sélecteurs.
"""
import io
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEUILLE = os.path.join(RACINE, "static", "ui-theme.css")

DERIVES = ("--pg-accent-soft", "--pg-accent-softer",
           "--pg-accent-border", "--pg-accent-glow")


def _sans_commentaires(css):
    """⚠️ Les commentaires de cette feuille CITENT les jetons qu'ils
    expliquent : les lire ferait passer un cliquet pour sa propre explication.
    C'est la même famille que les clés i18n construites et que le `<section>`
    écrit dans un commentaire de la doc technique."""
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def _regles(css):
    """[(selecteurs, corps)] des règles de premier niveau."""
    out = []
    for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", css):
        out.append((m.group(1).strip(), m.group(2)))
    return out


@pytest.fixture(scope="module")
def css():
    if not os.path.exists(FEUILLE):
        pytest.skip("ui-theme.css absent (arbre d'image ?)")
    return _sans_commentaires(io.open(FEUILLE, encoding="utf-8").read())


def _selecteurs(css, propriete):
    """Les sélecteurs des règles qui DÉCLARENT cette propriété."""
    vus = set()
    for sel, corps in _regles(css):
        if re.search(r"(^|[;\s])" + re.escape(propriete) + r"\s*:", corps):
            vus |= {s.strip() for s in sel.split(",") if s.strip()}
    return vus


class TestLesDerivesSuiventLaCouleurDeLaPage:

    def test_la_feuille_pose_bien_les_dix_couleurs(self, css):
        """⚠️ Garde-fou de volume : si les repères changent et que l'analyse
        ne trouve plus rien, les deux cas suivants passeraient au vert en ne
        lisant RIEN."""
        porteurs = _selecteurs(css, "--pg-accent")
        assert len(porteurs) >= 20, (
            "seulement %d selecteurs posent --pg-accent : l'analyse ne lit "
            "plus la feuille, les cliquets suivants ne gardent rien"
            % len(porteurs))

    @pytest.mark.parametrize("derive", DERIVES)
    def test_chaque_porteur_de_l_accent_porte_AUSSI_le_derive(self, css, derive):
        """C'est tout le correctif : un sélecteur qui pose `--pg-accent` sans
        poser ses dérivés les laisse au gris de `:root`, sans rien signaler."""
        porteurs = _selecteurs(css, "--pg-accent")
        avec = _selecteurs(css, derive)
        manquants = sorted(porteurs - avec)
        assert not manquants, (
            "ces selecteurs posent --pg-accent sans poser %s : ils rendront "
            "le GRIS par defaut de :root — %s" % (derive, manquants))

    def test_le_derive_se_calcule_bien_DEPUIS_l_accent(self, css):
        """Sans `var(--pg-accent)` dans sa valeur, un dérivé serait une
        couleur figée et le correctif n'aurait plus d'objet."""
        for sel, corps in _regles(css):
            for d in DERIVES:
                m = re.search(re.escape(d) + r"\s*:([^;]*)", corps)
                if m:
                    assert "var(--pg-accent)" in m.group(1), (
                        "%s ne derive pas de --pg-accent dans « %s »"
                        % (d, sel[:60]))

    def test_aucun_derive_n_est_declare_SEUL_sur_la_racine(self, css):
        """Le défaut d'origine, exactement : déclaré sur `:root` sans l'être
        aussi sur les classes de page, le dérivé hérite le gris déjà
        substitué."""
        racine_seule = []
        for d in DERIVES:
            porteurs = _selecteurs(css, d)
            if porteurs == {":root"}:
                racine_seule.append(d)
        assert not racine_seule, (
            "declare(s) sur :root SEUL — c'est le defaut d'origine : %s"
            % racine_seule)


class TestLesPagesRendentLeurCouleur:
    """Le pendant comportemental : les pages servies portent bien leur classe,
    donc la règle les atteint. Le rendu lui-même a été mesuré au navigateur
    (0 element gris sur 6821) ; ici on garde ce qui se verifie sans lui."""

    PAGES = {
        "page--activities": "#7c3aed",
        "page--roles": "#059669",
        "page--competences": "#2563eb",
        "page--time": "#d97706",
        "page--accounts": "#e11d48",
        "page--rh": "#16a34a",
        "page--tools": "#ea580c",
        "page--settings": "#6366f1",
        "page--share": "#c026d3",
    }

    def test_chaque_classe_de_page_a_sa_couleur_et_ses_derives(self, css):
        for classe, couleur in self.PAGES.items():
            porteurs = _selecteurs(css, "--pg-accent")
            assert "." + classe in porteurs, (
                "%s ne pose pas --pg-accent" % classe)
            assert couleur in css, (
                "la couleur %s de %s a disparu de la feuille"
                % (couleur, classe))
            for d in DERIVES:
                assert "." + classe in _selecteurs(css, d), (
                    "%s ne pose pas %s" % (classe, d))

    def test_la_classe_est_bien_POSEE_par_un_gabarit(self):
        """Une classe listée ici mais qu'aucun gabarit ne pose ne protège
        rien. ⚠️ `page--carto` n'y est PAS : la page Carte est hors du design
        system clair, elle a son identité propre."""
        gab = os.path.join(RACINE, "Code", "routes", "templates")
        if not os.path.isdir(gab):
            pytest.skip("gabarits absents")
        posees = set()
        lus = 0
        for r, d, fs in os.walk(gab):
            for f in fs:
                if not f.endswith(".html"):
                    continue
                lus += 1
                s = io.open(os.path.join(r, f), encoding="utf-8").read()
                posees |= set(re.findall(r"page--[a-z]+", s))
        if lus < 20:
            pytest.skip("seulement %d gabarits lus" % lus)
        orphelines = sorted(set(self.PAGES) - posees)
        assert not orphelines, (
            "classes listees mais posees par aucun gabarit : %s" % orphelines)
