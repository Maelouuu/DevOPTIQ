# -*- coding: utf-8 -*-
"""LES DEUX FENÊTRES DE L'ÉCRAN D'ÉVALUATION — technicité et plan de formation.

« La pop-up de technicité est vraiment laide, reprends-la, pareil pour la
formation. » Les deux reproches ne portaient pas sur la même chose :

  • la TECHNICITÉ était un formulaire nu — un nom, DEUX MENUS DÉROULANTS DU
    SYSTÈME, une pastille d'écart. Rien ne disait ce QU'EST un domaine
    technique ni pourquoi on en poserait un, et le `<select>` était le seul
    endroit de cette page où l'on pose un niveau autrement qu'avec des crans ;

  • le PLAN, lui, a une structure juste qui ne bouge pas (les étapes à gauche,
    les curseurs et l'échéancier à droite). Ce qui n'allait pas, c'est la
    DENSITÉ : les trois micro-champs d'une étape étaient écrits en 13 px, soit
    10,4 px RÉELS sous le `zoom: .8` du corps, et le panneau de droite n'avait
    que 258 px pour un verdict qu'on vient lire.
"""
import io
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS = os.path.join(RACINE, "static", "competences.css")


def _lire(p):
    return io.open(p, encoding="utf-8").read()


# ⚠️ Tout ce fichier lit l'ÉCRAN d'évaluation refondu. Le pilote ARaymond
# tourne encore sur l'écran d'avant : un contrôle qui rougit toujours n'est
# plus lu, et celui-ci se rallume tout seul le jour où l'écran arrive.
ECRAN_REFONDU = "cv2-ecran-eval" in _lire(JS)
pytestmark = pytest.mark.skipif(
    not ECRAN_REFONDU,
    reason="l'écran d'évaluation refondu n'est pas dans cet arbre")


def _corps(js, entete):
    return js.split(entete, 1)[1].split("\n  }", 1)[0]


def _sans_commentaires_css(css):
    """⚠️ Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES : il
    s'attrape sinon lui-même sur l'explication de la règle qu'il garde — c'est
    arrivé neuf fois dans ce dépôt."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _regle(css, selecteur):
    """Le corps d'UNE règle, bornée. ⚠️ Et on borne : un fichier de 3 500
    lignes contient presque toujours un homonyme de ce qu'on croit garder."""
    return css.split(selecteur, 1)[1].split("}", 1)[0]


class TestLaFenetreTechnicite:

    def test_elle_dit_d_abord_A_QUOI_CA_SERT(self):
        """Un domaine technique ne se devine pas : ni ce que c'est, ni
        pourquoi on en poserait un, ni qu'il s'agit d'un AUTRE axe que la
        maîtrise. Le panneau est en tilleul — c'est une aide, pas un
        avertissement."""
        js = _lire(JS)
        o = _corps(js, "  function ouvrirTechnicite() {")
        assert 'class="tch-exp"' in o and "gras(T('tech_quoi'))" in o
        css = _sans_commentaires_css(_lire(CSS))
        assert "var(--cv-g-40)" in _regle(css, "\n.tch-exp {")

    def test_les_niveaux_se_posent_avec_des_CRANS(self):
        """⚠️ C'était un `<select>` : le seul endroit de cette page où l'on
        posait un niveau autrement, et un menu déroulant arrive avec ses
        styles système au milieu d'un écran qui n'en a aucun."""
        js = _lire(JS)
        assert "function domSelect(" not in js, "le menu déroulant est parti"
        assert "function domEchelle(" in js
        e = _corps(js, "  function domEchelle(cle, val, cible, onchange) {")
        assert "Object.keys(state.domScale)" in e
        assert "b.onclick = () => onchange(+k);" in e

    def test_CINQ_crans_et_une_gomme_a_l_ecart(self):
        """⚠️ L'échelle technique distingue le niveau 0 (« aucun ») de
        l'absence de niveau (NULL, « pas encore regardé ») — c'est la
        distinction que tout le module tient, et la jauge à quatre pas de la
        maquette ne sait pas l'exprimer. Avec la gomme, chaque valeur du
        modèle est atteignable. Et effacer n'est pas un niveau de plus : la
        gomme vit à l'écart des crans."""
        js = _lire(JS)
        e = _corps(js, "  function domEchelle(cle, val, cible, onchange) {")
        assert "g.className = 'gom';" in e
        assert "g.onclick = () => onchange(null);" in e
        css = _sans_commentaires_css(_lire(CSS))
        assert "margin-left" in _regle(css, "\n.tch-e .pas .gom {")

    def test_le_REQUIS_est_en_creux_et_le_DEMONTRE_en_plein(self):
        """Une cible se dessine, elle ne se remplit pas. C'est le vocabulaire
        de la page, et c'est ce qui distingue les deux échelles d'un coup
        d'œil."""
        js = _lire(JS)
        assert "z.className = 'tch-e' + (cible ? ' cible' : '');" in js
        l = _corps(js, "  function renderDomList(list, aid, domains) {")
        assert "domEchelle('tech_requis_role', d.required_level, true," in l
        assert "domEchelle('tech_demonstrated', d.demonstrated_level, false," in l
        css = _sans_commentaires_css(_lire(CSS))
        assert "background: transparent" in _regle(css, "\n.tch-e.cible .pas button {")
        assert "inset 0 0 0 1.5px" in _regle(css, "\n.tch-e.cible .pas button.on {")

    def test_le_verdict_dit_ce_qu_il_EST(self):
        """« en écart · −2 » ou « tenu », pas un nombre nu : un « +1 » vert ne
        se lit pas comme un verdict.
        ⚠️ Et le SIGNE MOINS (U+2212), pas le trait d'union — le reste de la
        page l'écrit ainsi, et deux glyphes pour le même signe sur le même
        écran donnent l'air d'un défaut d'impression."""
        js = _lire(JS)
        l = _corps(js, "  function renderDomList(list, aid, domains) {")
        assert "Tv('tech_ecart', { n: -d.gap })" in l and "T('tech_tenu')" in l
        assert "−[[n]]" in js, "le signe moins, jamais le trait d'union"
        css = _sans_commentaires_css(_lire(CSS))
        assert "var(--cv-r-60)" in _regle(css, "\n.tch-v.ko {")
        assert "var(--cv-g-70)" in _regle(css, "\n.tch-v.ok {")

    def test_l_ajout_est_RANGE_en_bas_avec_ses_etiquettes(self):
        """C'est là qu'on va quand les domaines existants ne suffisent pas, et
        il ne doit pas se lire comme une ligne de la liste. ⚠️ Ses deux champs
        portent leur étiquette : un `placeholder` disparaît dès qu'on tape."""
        js = _lire(JS)
        a = _corps(js, "  function renderDomAdd(zone, aid, allDomains, linked) {")
        assert "T('tech_lier_t')" in a and "T('tech_creer_t')" in a
        assert "add.className = 'cv2-domadd tch-add';" in a
        assert "pal-b pal-b--prim" in a, "le bouton de la page, pas `btn-sm`"
        css = _sans_commentaires_css(_lire(CSS))
        assert "border" in _regle(css, "\n.tch-add {")

    def test_les_libelles_sont_dans_les_DEUX_langues(self):
        """⚠️ On lit les DICTIONNAIRES : une clé absente d'une langue retombe
        silencieusement sur le français, ou s'affiche telle quelle."""
        js = _lire(JS)
        bloc = js.split("  const COMMUN = {", 1)[1].split("\n  };", 1)[0]
        for k in ("tech_quoi", "tech_les", "tech_requis_role", "tech_lier_t",
                  "tech_creer_t", "tech_tenu", "tech_ecart", "tech_effacer",
                  "tech_note"):
            d = bloc.split(k + ":", 1)
            assert len(d) == 2, "clé absente : " + k
            tete = d[1][:600]
            assert "fr:" in tete and "en:" in tete, "une seule langue : " + k

    def test_rien_de_l_ancienne_fenetre_ne_traine(self):
        js, css = _lire(JS), _sans_commentaires_css(_lire(CSS))
        for mort in (".cv2-domrow", ".cv2-domsel", ".cv2-bloc--tech"):
            assert mort not in css, "css : " + mort
        # ⚠️ `.cv2-emptydom` RESTE : la liste des capacités s'en sert encore.
        assert ".cv2-emptydom" in css
        assert "cv2-emptydom" in js


class TestLaFenetreDuPlan:
    """La structure ne bouge pas — c'est elle qui rend le plan modulable. Ce
    qui change, c'est la densité."""

    def test_la_structure_ne_bouge_PAS(self):
        js = _lire(JS)
        assert "function renderActions(" in js and "function planning(" in js
        r = _corps(js, "  function renderActions(anime) {")
        assert 'class="cv2-etapes-g"' in r, "le regroupement par activité"
        assert "<ol class=\"cv2-etapes\">" in r, "un rail NUMÉROTÉ"
        c = _corps(js, "  function carteEtape(a, i, anime) {")
        assert "<dl class=\"cv2-etape-d\">" in c, "les champs étiquetés"

    def test_les_trois_champs_d_une_etape_ont_leur_air(self):
        """⚠️ 13 px écrits = 10,4 px RÉELS sous le `zoom: .8` du corps, sous le
        plancher de 11 de l'échelle typographique. Ce sont pourtant l'objectif,
        le livrable et le critère de réussite — ce qu'on vient lire."""
        css = _sans_commentaires_css(_lire(CSS))
        d = _regle(css, "\n.cv2-etape-d dd {")
        assert "font-size: 14px" in d
        assert "gap: 9px 16px" in _regle(css, "\n.cv2-etape-d {")

    def test_le_panneau_de_droite_gagne_sa_place(self):
        """Son verdict — besoin, capacité, et la phrase qui dit ce qui manque
        — est ce pour quoi on ouvre la fenêtre. À 258 px il se repliait."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "min(1000px, 95vw)" in _regle(css, "\n.cv2-plan-win {")
        assert "minmax(318px, 1fr)" in _regle(css, "\n.cv2-plan-grille {")
        assert "font-size: 19px" in _regle(css, "\n.cv2-chiffres b {")

    def test_caler_au_plus_juste_ne_lit_plus_le_gris_de_la_racine(self):
        """⚠️ `--pg-accent-border` et `--pg-accent-soft` sont déclarés sur
        `:root`, où `--pg-accent` vaut encore le gris par défaut : le filet et
        le survol de ce bouton étaient GRIS sur une page bleue. Le mélange
        s'écrit SUR PLACE, comme ailleurs dans cette feuille."""
        css = _sans_commentaires_css(_lire(CSS))
        for sel in ("\n.cv2-juste {", "\n.cv2-juste:hover {"):
            r = _regle(css, sel)
            for derive in ("--pg-accent-soft", "--pg-accent-softer",
                           "--pg-accent-border", "--pg-accent-glow"):
                assert derive not in r, sel + " lit " + derive
        assert "color-mix(in srgb, var(--pg-accent)" in _regle(css, "\n.cv2-juste {")
