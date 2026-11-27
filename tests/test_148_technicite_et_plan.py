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


def _taille_effective(css, classe):
    """La `font-size` que le navigateur APPLIQUE à cette classe, en px écrits.

    ⚠️⚠️ Lire la PREMIÈRE règle ne prouve rien : le bloc « LISIBILITÉ DES
    FENÊTRES » redéclare `.cv2-dit` et `.cv2-prop` deux cents lignes plus bas,
    et à spécificité égale c'est la dernière déclarée qui gagne. Le cliquet du
    plancher restait VERT sur un texte rendu à 10,4 px réels — c'est le BANC
    qui l'a trouvé. On prend donc la DERNIÈRE déclaration qui vise la classe.
    """
    vu = None
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sels, corps = m.group(1), m.group(2)
        if not re.search(r"(^|[\s,>+~])" + re.escape(classe) + r"(?![\w-])", sels):
            continue
        t = re.search(r"font-size:\s*([\d.]+)px", corps)
        if t:
            vu = float(t.group(1))
    return vu


class TestLaFenetreTechnicite:

    def test_l_explication_passe_derriere_un_i(self):
        """⚠️ RÉÉCRIT (27/11) : elle était en tête de fenêtre, trois lignes
        pour une règle qu'on lit une fois, et elle prenait la place de la
        table. C'est le motif de la maison — une phrase se range derrière un
        « i », elle ne disparaît pas : les deux clés sont toujours lues.
        ⚠️ Et `brancherInfo` ÉCHAPPE son texte : les marqueurs `[[b]]` s'y
        afficheraient en clair, donc on les retire."""
        js = _lire(JS)
        o = _corps(js, "  function ouvrirTechnicite() {")
        assert 'class="tch-exp"' not in o, "le panneau en tête est parti"
        assert 'class="tch-h"' in o and 'class="cv2-i"' in o
        assert "brancherInfo(" in o
        assert "T('tech_quoi')" in o and "T('tech_note')" in o
        assert "split('[[b]]')" in o, "les marqueurs de gras sont retirés"

    def test_les_niveaux_se_posent_avec_des_CRANS(self):
        """⚠️ C'était un `<select>` : le seul endroit de cette page où l'on
        posait un niveau autrement, et un menu déroulant arrive avec ses
        styles système au milieu d'un écran qui n'en a aucun."""
        js = _lire(JS)
        assert "function domSelect(" not in js, "le menu déroulant est parti"
        # ⚠️ RÉÉCRIT (27/11) : `domEchelle` rendait l'étiquette AVEC les crans.
        # L'étiquette monte en en-tête de table, écrite une fois au lieu de
        # six : la fonction ne rend plus que les crans.
        assert "function domPas(" in js
        e = _corps(js, "  function domPas(cle, val, cible, onchange) {")
        assert "Object.keys(state.domScale)" in e
        assert "b.onclick = () => onchange(+k);" in e
        assert 'class="k"' not in e, "l'étiquette est en en-tête"

    def test_CINQ_crans_et_une_gomme_a_l_ecart(self):
        """⚠️ L'échelle technique distingue le niveau 0 (« aucun ») de
        l'absence de niveau (NULL, « pas encore regardé ») — c'est la
        distinction que tout le module tient, et la jauge à quatre pas de la
        maquette ne sait pas l'exprimer. Avec la gomme, chaque valeur du
        modèle est atteignable. Et effacer n'est pas un niveau de plus : la
        gomme vit à l'écart des crans."""
        js = _lire(JS)
        e = _corps(js, "  function domPas(cle, val, cible, onchange) {")
        assert "g.className = 'gom';" in e
        assert "g.onclick = () => onchange(null);" in e
        css = _sans_commentaires_css(_lire(CSS))
        assert "margin-left" in _regle(css, "\n.tch-pas .gom {")

    def test_le_REQUIS_est_en_creux_et_le_DEMONTRE_en_plein(self):
        """Une cible se dessine, elle ne se remplit pas. C'est le vocabulaire
        de la page, et c'est ce qui distingue les deux échelles d'un coup
        d'œil."""
        js = _lire(JS)
        assert "pas.className = 'tch-pas' + (cible ? ' cible' : '');" in js
        l = _corps(js, "  function renderDomList(list, aid, domains) {")
        assert "domPas('tech_requis_role', d.required_level, true," in l
        assert "domPas('tech_demonstrated', d.demonstrated_level, false," in l
        css = _sans_commentaires_css(_lire(CSS))
        assert "background: transparent" in _regle(css, "\n.tch-pas.cible button {")
        assert "inset 0 0 0 2px" in _regle(css, "\n.tch-pas.cible button.on {")

    def test_le_verdict_dit_ce_qu_il_EST(self):
        """« en écart · −2 » ou « tenu », pas un nombre nu : un « +1 » vert ne
        se lit pas comme un verdict.
        ⚠️ Et le SIGNE MOINS (U+2212), pas le trait d'union — le reste de la
        page l'écrit ainsi, et deux glyphes pour le même signe sur le même
        écran donnent l'air d'un défaut d'impression."""
        js = _lire(JS)
        l = _corps(js, "  function renderDomList(list, aid, domains) {")
        assert "Tv('tech_ecart', { n: -d.gap })" in l and "T('tech_tenu')" in l
        # ⚠️ Et NULL a le SIEN : sans lui la colonne s'effondre une ligne sur
        # trois, et « pas encore regardé » se lirait comme « au niveau ».
        assert "T('tech_nonsitue')" in l
        assert "−[[n]]" in js, "le signe moins, jamais le trait d'union"
        css = _sans_commentaires_css(_lire(CSS))
        assert "var(--cv-r-60)" in _regle(css, "\n.tch-v.ko {")
        assert "var(--cv-g-70)" in _regle(css, "\n.tch-v.ok {")

    def test_l_ajout_est_un_BOUTON_qui_deplie(self):
        """⚠️ RÉÉCRIT (27/11) : la zone était dépliée en permanence et se
        lisait comme une ligne de plus de la liste.
        ⚠️⚠️ Et son libellé était FAUX quand tout était déjà rattaché — le
        ternaire était inversé : on lisait « Rattacher un domaine qui existe »
        au-dessus d'un champ « Nouveau domaine… ». Chaque champ porte le sien,
        et celui qui n'a rien à proposer n'est pas rendu."""
        js = _lire(JS)
        a = _corps(js, "  function renderDomAdd(zone, aid, allDomains, linked) {")
        assert "champs.hidden = true;" in a, "déplié à la demande"
        assert "T('tech_ajouter')" in a, "le bouton nomme ce qu'il fait"
        assert "pal-b pal-b--prim" in a, "le bouton de la page, pas `btn-sm`"
        # le ternaire inversé est parti : chaque étiquette est inconditionnelle
        assert "avail.length ? T('tech_creer_t') : T('tech_lier_t')" not in a
        assert "ch2.innerHTML = `<span>${esc(T('tech_creer_t'))}</span>`;" in a
        css = _sans_commentaires_css(_lire(CSS))
        # ⚠️ `[hidden]` est une règle du NAVIGATEUR : une classe d'auteur qui
        # pose un `display` l'emporte. Huitième fois dans cette application.
        assert ".tch-champs[hidden]" in css

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


class TestLaPageDuPlan:
    """⚠️ RÉÉCRIT (27/11) — le plan a quitté la fenêtre. Elle faisait
    800 × 736 px RÉELS dans un écran de 1600 × 1000, avec 1 089 px à dérouler
    pour 794 visibles. Ce qui reste vrai de la passe de densité, c'est la
    STRUCTURE (le besoin, la capacité, un verdict en direct) et le PLANCHER
    typographique ; ce qui change, c'est où tout cela est posé."""

    def test_la_structure_ne_bouge_PAS(self):
        js = _lire(JS)
        assert "function renderActions(" in js and "function planning(" in js
        r = _corps(js, "  function renderActions(anime) {")
        assert 'class="cv2-etapes-g"' in r, "le regroupement par activité"
        assert '<ol class="cv2-etapes">' in r, "un rail NUMÉROTÉ"

    def test_la_carte_dit_la_MESURE_au_lieu_de_trois_champs_etiquetes(self):
        """⚠️ 248 px, le nom du résultat écrit TROIS fois et trois étiquettes
        en capitales à 9,2 px RÉELS. Le titre est l'action — une fois — la
        ligne qui suit porte la mesure telle que le serveur la rédige, et
        « Réussi quand » attend derrière un « ? ». « Livrable » ne revient
        que quand le titre ne le dit pas déjà."""
        js = _lire(JS)
        c = _corps(js, "  function carteEtape(a, i, anime) {")
        assert "<dl" not in c and "cv2-etape-d" not in c, "les étiquettes sont parties"
        assert 'class="cv2-etape-o"' in c, "la ligne de mesure"
        assert "plan_crit" in c and 'class="pl-q"' in c, "le critère derrière un ?"
        assert "indexOf(liv) < 0" in c, "le livrable ne redit pas le titre"

    def test_le_plancher_des_champs_qui_restent(self):
        """11 px RÉELS, soit 13,75 écrits sous le `zoom: .8` du corps."""
        css = _sans_commentaires_css(_lire(CSS))
        PLANCHER = 13.75
        for sel in ("\n.cv2-etape-t {", "\n.cv2-etape-o {", "\n.pl-ch-s {"):
            r = _regle(css, sel)
            m = re.search(r"font-size:\s*([\d.]+)px", r)
            assert m, sel
            assert float(m.group(1)) >= PLANCHER, (sel, m.group(1))
        # ⚠️ La provenance du plan était rendue à 9,2 px RÉELS : `.cv2-prop`
        # vaut 11,5 px CSS. On lit la taille que le navigateur APPLIQUE — la
        # dernière déclarée — pas la première qu'on croise.
        v = _taille_effective(css, ".cv2-prop")
        assert v and v >= PLANCHER, v
        assert "font-size: 13.75px" in _regle(css, "\n.pl-pied .cv2-prop {")

    def test_le_verdict_est_le_premier_chiffre_de_la_page(self):
        """Son verdict — ce qui manque — est ce pour quoi on ouvre le plan.
        Dans la fenêtre il arrivait en SIXIÈME position de la colonne de
        droite ; il est maintenant dans le bandeau, en 46 px."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "font-size: 46px" in _regle(css, "\n.pl-vn b {")
        js = _lire(JS)
        bandeau = js.split('class="pl-corps"', 1)[1].split("pl-cols", 1)[0]
        assert "pl-frise" in bandeau and "pl-verdict" in bandeau

    def test_rien_de_la_page_ne_lit_le_gris_de_la_racine(self):
        """⚠️ `--pg-accent-border` et `--pg-accent-soft` sont déclarés sur
        `:root`, où `--pg-accent` vaut encore le gris par défaut : le filet et
        le survol d'un bouton y seraient GRIS sur une page bleue."""
        css = _lire(CSS)
        sec = _sans_commentaires_css(
            css.split("LE PLAN DE FORMATION — une PAGE", 1)[1].split("*/", 1)[1])
        for derive in ("--pg-accent-soft", "--pg-accent-softer",
                       "--pg-accent-border", "--pg-accent-glow"):
            assert derive not in sec, derive
