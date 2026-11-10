# -*- coding: utf-8 -*-
"""L'AXE PARTAGÉ et l'HISTORIQUE — ce que l'écran d'évaluation promet.

Chaque sortie avait SA carte, et les deux régimes en avaient deux très
différentes : « pas encore notée » ne ressemblait en rien à « déjà notée ».
C'est ce qui rendait l'écran brouillon. Ce fichier garde la structure qui
remplace les deux :

  • UNE rangée par sortie, la même graduation, la même zone attendue —
    la différence se lit DANS la piste, plus dans la mise en page ;
  • la zone attendue est une SURFACE, et il n'y en a pas quand le rôle n'a
    fixé aucun niveau requis (NULL ≠ 0, règle du module) ;
  • une sortie MESURÉE n'a pas de crans à cliquer pour le développeur : son
    niveau vient du chiffre relevé en séance ;
  • le NUMÉRO relie les deux cartes — la rangée le porte, et c'est lui qui
    termine la courbe de cette sortie dans l'historique ;
  • la courbe GLOBALE se dessine SOUS les autres : là où elle en rejoint une,
    on voit la plus basse portée par elle. C'est la règle du minimum, dessinée.
"""
import io
import os
import re

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS = os.path.join(RACINE, "static", "competences.css")


def _lire(p):
    return io.open(p, encoding="utf-8").read()


def _corps(js, entete):
    return js.split(entete, 1)[1].split("\n  }", 1)[0]


def _sans_commentaires_css(css):
    """⚠️ Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES : il
    s'attrape sinon lui-même sur l'explication de la règle qu'il garde — c'est
    arrivé cinq fois dans ce dépôt."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


class TestLAxeRemplaceLesDeuxCartes:

    def test_le_centre_monte_un_axe_et_pas_une_pile_de_cartes(self):
        js = _lire(JS)
        c = _corps(js, "  function remplirCentre(st) {")
        assert "box.appendChild(axePartage(st));" in c
        assert "st.results.forEach(r => box.appendChild(carteSortie" not in c, \
            "les cartes empilées sont ce qu'on vient de remplacer"
        assert "box.appendChild(carteHistorique(st));" in c

    def test_une_rangee_par_sortie_dans_le_meme_axe(self):
        js = _lire(JS)
        a = _corps(js, "  function axePartage(st) {")
        assert "st.results.forEach((r, i) => box.appendChild(rangeeSortie(r, st, i)));" in a
        assert "cv2-rg cv2-rg--t" in a, "la graduation est une rangée du même axe"

    def test_la_zone_attendue_n_existe_pas_sans_niveau_requis(self):
        """⚠️ NULL ≠ 0 : un rôle qui n'a fixé aucun attendu n'a pas de cible,
        et une bande verte posée à 0 dirait que tout est au niveau."""
        js = _lire(JS)
        r = _corps(js, "  function rangeeSortie(r, st, i) {")
        assert "const req = estNul(st.required_level) ? null : st.required_level;" in r
        assert "${req === null ? '' : '<div class=\"p-zone\"></div>'}" in r
        a = _corps(js, "  function axePartage(st) {")
        assert "if (req !== null) {" in a, "pas de pastille ATTENDU non plus"

    def test_une_sortie_mesuree_n_a_pas_de_crans_pour_le_developpeur(self):
        """Son niveau vient du chiffre relevé en séance. Une échelle à côté
        dirait deux choses d'une seule. L'auto-évaluation, elle, reste
        permise : c'est un repère que le collaborateur se donne."""
        js = _lire(JS)
        r = _corps(js, "  function rangeeSortie(r, st, i) {")
        assert "const modifiable = dev ? !r.mesurable : true;" in r
        i = r.index("if (modifiable) {")
        assert "class=\"p-c\"" in r[i:], "les crans se dessinent DANS cette garde"

    def test_les_points_blancs_de_la_piste_ont_disparu(self):
        """⚠️ Ils posaient l'historique SUR la barre — à l'endroit où l'on
        vient lire une seule chose : le niveau tenu aujourd'hui. L'historique
        a sa carte."""
        js, css = _lire(JS), _lire(CSS)
        assert "class=\"p-t" not in js
        assert ".p-t{" not in css and ".p-t " not in css


class TestLeNumeroRelieLesDeuxCartes:

    def test_la_rangee_porte_son_numero(self):
        js = _lire(JS)
        r = _corps(js, "  function rangeeSortie(r, st, i) {")
        assert "class=\"rg-num\">${i + 1}<" in r

    def test_le_dernier_point_de_la_courbe_porte_LE_MEME(self):
        """« On ne comprend pas bien que les différents points sont les
        niveaux des sorties individuellement. » Le numéro est la réponse."""
        js = _lire(JS)
        f = js.split("  function friseSvg(h, req) {", 1)[1].split("\n  }\n", 1)[0]
        assert "class=\"hi-num\"" in f
        assert "text-anchor=\"middle\">${o.num}" in f


class TestLaCourbeGlobale:

    def test_elle_se_dessine_SOUS_les_courbes_de_sortie(self):
        """Là où elle en rejoint une, on voit la plus basse portée par un
        large ruban : la règle du minimum se regarde au lieu de s'écrire."""
        js = _lire(JS)
        f = js.split("  function friseSvg(h, req) {", 1)[1].split("\n  }\n", 1)[0]
        i_glob = f.index("class=\"hi-glob\"")
        i_lignes = f.index("class=\"hi-l hi-l--")
        assert i_glob < i_lignes, "dessinée après, elle passerait par-dessus"

    def test_un_SEGMENT_porte_l_etat_de_son_point_d_arrivee(self):
        """Une courbe qui passe de 1 à 3 change de famille en chemin, là où
        elle franchit l'attendu. D'une seule couleur, elle dirait que la
        sortie a toujours été au niveau."""
        js = _lire(JS)
        f = js.split("  function friseSvg(h, req) {", 1)[1].split("\n  }\n", 1)[0]
        assert "hi-l--${fam(p[k].niveau)}" in f

    def test_la_legende_dit_quand_il_n_y_a_PAS_de_niveau_d_activite(self):
        js = _lire(JS)
        lg = _corps(js, "  function legendeHistorique(c, h, req) {")
        assert "h.global.length" in lg and "h_sans_glob" in lg


class TestLesReglesDeStyle:

    def test_aucune_regle_neuve_ne_lit_l_accent_doux_de_la_racine(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur `:root`,
        où `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS.
        Les mélanges s'écrivent SUR PLACE."""
        css = _sans_commentaires_css(_lire(CSS))
        bloc = css.split(".cv2-axe, .cv2-histo, .cv2-det {", 1)[1]
        for v in ("--pg-accent-soft", "--pg-accent-softer",
                  "--pg-accent-border", "--pg-accent-glow"):
            assert v not in bloc, v

    def test_la_piste_laisse_PASSER_la_bande_verte(self):
        """⚠️ Peint des deux côtés, le même dégradé ne tombe pas au même
        endroit (la bande est plus large que la piste) : on voyait une couture,
        et le bout arrondi de la piste ressortait comme un défaut."""
        css = _sans_commentaires_css(_lire(CSS))
        fond = css.split(".p-fond {", 1)[1].split("}", 1)[0]
        assert "transparent var(--xr)" in fond
        vide = css.split(".cv2-rg[data-lv=\"x\"] .p-fond {", 1)[1].split("}", 1)[0]
        assert "var(--xr, 100%) 100% no-repeat" in vide, \
            "la hachure s'arrête elle aussi à l'attendu, sinon elle couvre la bande"

    def test_la_frise_ne_met_pas_son_SVG_a_l_echelle(self):
        """⚠️ Un SVG en `width:100%` rapetisse ses TEXTES avec lui, et la taille
        calculée reste celle du repère du viewBox — la mesure ne le voit pas.
        Le viewBox est taillé sur la place disponible ; sous la largeur
        minimale, c'est la frise qui défile."""
        js, css = _lire(JS), _sans_commentaires_css(_lire(CSS))
        f = js.split("  function friseSvg(h, req) {", 1)[1].split("\n  }\n", 1)[0]
        assert "Math.max(Math.round(hote ? hote.clientWidth : 0) || FR_MINI, FR_MINI)" in f
        s = css.split(".hi-s {", 1)[1].split("}", 1)[0]
        assert "overflow-x: auto" in s


class TestLesLibellesSontDansLesDeuxLangues:

    def test_les_cles_de_l_axe_et_de_l_historique(self):
        """⚠️ Une clé absente d'une langue ne lève RIEN : elle retombe
        silencieusement sur le français, ou s'affiche telle quelle. On lit
        donc les DICTIONNAIRES, pas le rendu."""
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        cles = ["ax_col_sorties", "ax_col_tenu", "ax_attendu", "ax_detail",
                "ax_se_dit", "ax_je_me_dis", "ax_pas_notee", "ax_effacer",
                "ax_reprendre", "ax_reussi", "ax_sans_norme",
                "ax_en_attente_1", "ax_en_attente_n",
                "h_titre", "h_vide", "h_glob", "h_glob_d", "h_sous", "h_au",
                "h_sans_glob", "h_jamais", "h_une_note", "h_une_note_d", "h_niveau"]
        for k in cles:
            assert (k + ":") in fr, "FR " + k
            assert (k + ":") in en, "EN " + k

    def test_la_frise_porte_une_date_COURTE(self):
        """Dix dates en « 07/10/2026 » se chevaucheraient. La date entière
        reste dans l'info-bulle du point."""
        js = _lire(JS)
        assert "function dateCourte(iso)" in js
        f = js.split("  function friseSvg(h, req) {", 1)[1].split("\n  }\n", 1)[0]
        assert "dateCourte(j)" in f
        assert "fmtDate(h.dates[q.t])" in f, "l'info-bulle garde la date entière"
