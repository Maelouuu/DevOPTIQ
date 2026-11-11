# tests/test_137_pilote_quatre_corrections.py
"""Les quatre corrections retenues sur les retours du pilote indien.

#25 le texte qui déborde de son fond blanc · #19 le texte qui ne tient pas
dans la forme · #30 l'index introuvable · #22 l'import qui ne dit pas ce
qu'il laisse dehors.

⚠️ Ces cas lisent des fichiers de `static/` et des gabarits : tous deux sont
PRÉSENTS dans l'arbre d'image (la purge bytecode ne retire que les `.py` de
`Code/`). Les libellés, eux, se lisent dans `TRANSLATIONS` et jamais dans le
texte de `Code/translations.py`, qui n'y existe plus.

⚠️ Et une clé absente de l'anglais retombe SILENCIEUSEMENT sur le français :
un contrôle qui passerait par `t()` ne garderait rien. On lit donc
`TRANSLATIONS['en']` directement.
"""
import io
import os
import re

import pytest

from Code.translations import TRANSLATIONS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITOR_JS = os.path.join(ROOT, "static", "optiqcarto", "editor.js")
CARTO_CSS = os.path.join(ROOT, "static", "optiqcarto", "style.css")
IMPORT_JS = os.path.join(ROOT, "static", "js", "import_hub.js")
IMPORT_CSS = os.path.join(ROOT, "static", "import_hub.css")
T_EDITEUR = os.path.join(ROOT, "Code", "routes", "templates", "cartography_editor.html")
T_VIEWER = os.path.join(ROOT, "Code", "routes", "templates", "cartography_viewer.html")
T_IMPORT = os.path.join(ROOT, "Code", "routes", "templates", "import_hub_modal.html")


def _lire(chemin):
    with io.open(chemin, encoding="utf-8") as fh:
        return fh.read()


def _sans_commentaires_js(src):
    """⚠️ Un contrôle qui cherche une chaîne s'attrape sur le COMMENTAIRE qui
    l'explique — c'est arrivé cinq fois dans ce dépôt. On les retire."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"^\s*//.*$", "", src, flags=re.M)


def _sans_commentaires_css(src):
    return re.sub(r"/\*.*?\*/", "", src, flags=re.S)


def _corps(src, debut, fin):
    """Le texte entre deux bornes — jamais un motif ouvert : une regex non
    gourmande a déjà emporté 1 840 lignes de CSS dans ce dépôt."""
    i = src.index(debut)
    j = src.index(fin, i)
    return src[i:j]


def _bloc_js(chemin, debut, fin):
    """⚠️ On découpe sur la source BRUTE puis on retire les commentaires — pas
    l'inverse : plusieurs bornes SONT des commentaires, et les retirer d'abord
    les ferait disparaître (le découpage lèverait alors une ValueError)."""
    return _sans_commentaires_js(_corps(_lire(chemin), debut, fin))


def _les_deux(cle):
    return TRANSLATIONS["fr"].get(cle), TRANSLATIONS["en"].get(cle)


# ═══════════════════════════════════════════════════════════════════════════
#  #25 — l'étiquette de flèche débordait de son propre fond blanc
# ═══════════════════════════════════════════════════════════════════════════
class TestLEtiquetteNeDeborderPlus:
    """Le fond était dimensionné à 6 px par caractère pour un texte rendu en
    14 px. Mesuré au navigateur : 7,94 px. Les lettres qui dépassaient
    n'avaient donc plus rien derrière elles et tombaient sur le trait."""

    def test_AUCUNE_largeur_de_texte_n_est_estimee_au_caractere(self):
        """⚠️ Ce cliquet a trouvé DEUX autres sites que celui signalé : la
        pop-up de placement des losanges et le curseur qui pose les étiquettes
        le long des flèches estimaient eux aussi au nombre de caractères."""
        js = _sans_commentaires_js(_lire(EDITOR_JS))
        assert "maxLineLen * 6" not in js
        assert not re.search(r"\.length\)*\s*\*\s*6", js), (
            "une largeur de texte est de nouveau estimée au nombre de caractères"
        )
        assert js.count("mesurerTexte(") >= 3

    def test_la_police_de_mesure_SUIT_celle_du_rendu(self):
        """Une mesure faite dans une autre police ne mesure rien."""
        js = _lire(EDITOR_JS)
        police = re.search(r"const POLICE_ETIQUETTE = '([^']+)'", js).group(1)
        # le bloc qui DESSINE l'étiquette, pas le fichier entier
        dessin = _corps(js, "for (const { c, lx, ly, angle, lw, lh,", "gConns.appendChild(lg);")
        taille = re.search(r"'font-size': '(\d+)'", dessin).group(1)
        graisse = re.search(r"'font-weight': '(\d+)'", dessin).group(1)
        assert taille + "px" in police, (
            "la police de mesure (%s) ne porte pas la taille du rendu (%s)" % (police, taille)
        )
        assert police.startswith(graisse + " "), (
            "la police de mesure (%s) ne porte pas la graisse du rendu (%s)" % (police, graisse)
        )

    def test_le_fond_porte_une_MARGE(self):
        """Même à la bonne largeur, sans marge la première et la dernière
        lettre touchent le bord et le trait passe au ras des jambages."""
        js = _sans_commentaires_js(_lire(EDITOR_JS))
        bloc = _corps(js, "const labelLines = c.label.split", "let lx, ly, angle = 0;")
        assert "MARGE_ETIQUETTE * 2" in bloc
        assert re.search(r"const MARGE_ETIQUETTE\s*=\s*(\d+)", js)

    def test_l_interligne_ne_passe_plus_SOUS_la_police(self):
        """13 pour une police de 14 : les deux lignes d'une étiquette sur deux
        lignes se chevauchaient."""
        js = _lire(EDITOR_JS)
        bloc = _corps(js, "const labelLines = c.label.split", "let lx, ly, angle = 0;")
        inter = int(re.search(r"const lineH = (\d+);", bloc).group(1))
        dessin = _corps(js, "for (const { c, lx, ly, angle, lw, lh,", "gConns.appendChild(lg);")
        taille = int(re.search(r"'font-size': '(\d+)'", dessin).group(1))
        assert inter >= taille, (
            "interligne %d pour une police de %d : les lignes se chevauchent" % (inter, taille)
        )


# ═══════════════════════════════════════════════════════════════════════════
#  #19 — le texte ne tenait pas dans la forme, et il disparaissait
# ═══════════════════════════════════════════════════════════════════════════
class TestLeTexteTientDansLaForme:

    def test_il_n_est_plus_coupe_EN_SILENCE(self):
        """`wrapText` finissait par `.slice(0, 4)` : au-delà de quatre lignes,
        la fin du libellé n'existait simplement plus à l'écran."""
        js = _sans_commentaires_js(_lire(EDITOR_JS))
        assert "wrapText(s.label" not in js, (
            "le libellé d'une forme repasse par wrapText, qui tronque à 4 lignes"
        )
        assert "_couperAvecEllipse" in js
        ellipse = _corps(js, "function _couperAvecEllipse", "function ajusterTexteForme")
        # \u26a0\ufe0f Pas \u00ab l'ellipse appara\u00eet quelque part \u00bb : elle sert aussi \u00e0 MESURER
        # la place qu'elle prendra. Ce qui compte, c'est qu'elle soit POS\u00c9E sur
        # la derni\u00e8re ligne \u2014 sans quoi la coupe redevient muette.
        assert re.search(r"lignes\[lignes\.length - 1\] = [^;]*'\u2026'", ellipse), (
            "la troncature ne pose pas d'ellipse sur la derni\u00e8re ligne"
        )

    def test_la_HAUTEUR_est_verifiee(self):
        """Elle était calculée… puis ignorée : quatre lignes à 18 px font
        95 px dans une forme qui en fait 90."""
        corps = _bloc_js(EDITOR_JS, "function ajusterTexteForme", "/* ══")
        assert re.search(r"zoneH\s*=\s*Math\.max\(0,\s*s\.h", corps), (
            "la hauteur utile ne vient plus de celle de la forme"
        )
        bornes = re.findall(r"Math\.floor\(([^/]+)/", corps)
        assert bornes, "plus aucune borne sur le nombre de lignes"
        for b in bornes:
            assert b.strip() == "zoneH", (
                "une borne de lignes ne vient pas de la hauteur de la forme : %r" % b
            )

    def test_la_police_se_REDUIT_sans_jamais_grossir(self):
        corps = _bloc_js(EDITOR_JS, "function ajusterTexteForme", "/* ══")
        assert "taille -= 1" in corps, "la police ne décroît pas"
        assert "Math.min(POLICE_MIN" in corps, (
            "le plancher peut GROSSIR une police réglée plus petite à la main"
        )

    def test_le_losange_a_une_largeur_PAR_LIGNE(self):
        """0,52·w est la largeur à MI-HAUTEUR : les lignes du haut et du bas
        avaient moins de place et sortaient sur les côtés."""
        js = _sans_commentaires_js(_lire(EDITOR_JS))
        assert "s.w * 0.52" not in js, "le losange est de nouveau mesuré à mi-hauteur"
        util = _corps(js, "function _largeurUtile", "function _decouperDansForme")
        assert "s.type !== 'decision'" in util
        assert re.search(r"\(i\s*-\s*\(n\s*-\s*1\)\s*/\s*2\)", util), (
            "_largeurUtile ne calcule plus l'écart de la ligne au centre : "
            "toutes les lignes retrouvent la même largeur"
        )
        assert "s.h" in util, "la largeur ne tient plus compte de la hauteur du losange"

    def test_la_taille_RENDUE_est_celle_de_la_pose(self):
        js = _sans_commentaires_js(_lire(EDITOR_JS))
        assert "'font-size': pose.taille," in js
        assert "'font-size': s.fontSize," not in js, (
            "la forme est rendue à la taille STOCKÉE : la réduction ne se voit pas"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  #30 — l'index des activités existait, il était introuvable
# ═══════════════════════════════════════════════════════════════════════════
class TestLIndexDevientTrouvable:

    @pytest.mark.parametrize("gabarit", [T_EDITEUR, T_VIEWER])
    def test_le_champ_existe_dans_LES_DEUX_gabarits(self, gabarit):
        """⚠️ editor.js câble sans garde : un id absent d'un gabarit lève une
        TypeError qui interrompt TOUTE l'init, chargement de la carto
        compris."""
        html = _lire(gabarit)
        assert 'id="cmap-search"' in html
        assert 'id="cmap-count"' in html

    def test_la_recherche_ecoute_la_FRAPPE_et_pas_la_perte_de_focus(self):
        js = _lire(EDITOR_JS)
        cable = [l for l in js.splitlines() if "getElementById('cmap-search')" in l]
        assert len(cable) == 1
        assert "'input'" in cable[0], (
            "branchée sur « change », elle ne filtrerait rien pendant la frappe"
        )

    def test_elle_MASQUE_au_lieu_de_re_rendre(self):
        """`render()` reconstruit déjà la liste : la redessiner à chaque frappe
        ferait perdre le curseur du champ qu'on tape."""
        js = _sans_commentaires_js(_lire(EDITOR_JS))
        corps = _corps(js, "function _filtrerIndex", "function renderCanvasMap")
        assert ".hidden = " in corps
        assert "render()" not in corps

    def test_une_section_vide_se_masque_aussi(self):
        js = _sans_commentaires_js(_lire(EDITOR_JS))
        corps = _corps(js, "function _filtrerIndex", "function renderCanvasMap")
        assert "left-section-label" in corps, (
            "on lirait « Formes » suivi de rien quand tout est filtré"
        )

    def test_le_filtre_se_repose_apres_chaque_reconstruction(self):
        corps = _bloc_js(EDITOR_JS, "function renderCanvasMap", "/* ══")
        assert "_filtrerIndex();" in corps, (
            "taper puis déplacer une forme rendrait de nouveau tout visible"
        )

    def test_le_masquage_masque_VRAIMENT(self):
        """⚠️ `[hidden]` est une règle du navigateur : une classe d'auteur qui
        pose un `display` l'emporte."""
        css = _sans_commentaires_css(_lire(CARTO_CSS))
        regle = re.search(r"([^{}]*\[hidden\][^{}]*)\{([^}]*)\}", css)
        assert regle, "aucune règle [hidden] déclarée à la main"
        cibles, corps = regle.group(1), regle.group(2)
        assert ".cmap-item[hidden]" in cibles
        assert ".left-section-label[hidden]" in cibles
        assert "display: none" in corps

    def test_l_index_est_remonte_AVANT_la_legende(self):
        """Une légende se lit une fois, un index sert à chaque recherche."""
        html = _lire(T_EDITEUR)
        assert html.index("canvas-map-list") < html.index("editor.legend_title"), (
            "l'index est de nouveau sous la légende, là où le pilote ne l'a pas trouvé"
        )

    @pytest.mark.parametrize("cle", [
        "editor.cmap_search", "editor.cmap_total", "editor.cmap_total_1",
        "editor.cmap_sur", "editor.cmap_vide",
    ])
    def test_les_libelles_existent_dans_LES_DEUX_langues(self, cle):
        fr, en = _les_deux(cle)
        assert fr and en, "%s manque (fr=%r, en=%r)" % (cle, fr, en)
        assert fr != en, "%s n'est pas traduit" % cle

    def test_les_libelles_a_nombre_portent_leur_marqueur(self):
        """`_L` substitue {0}, {1}… : un libellé sans marqueur afficherait le
        texte sans son nombre, et personne ne le verrait."""
        for cle, marqueurs in (("editor.cmap_total", ["{0}"]),
                               ("editor.cmap_sur", ["{0}", "{1}"])):
            for lang in ("fr", "en"):
                val = TRANSLATIONS[lang][cle]
                for m in marqueurs:
                    assert m in val, "%s [%s] = %r : %s manque" % (cle, lang, val, m)


# ═══════════════════════════════════════════════════════════════════════════
#  #22 — l'import n'annonçait pas ce qu'il laissait dehors
# ═══════════════════════════════════════════════════════════════════════════
class TestLImportNommeCeQuilLaisse:

    def test_il_demande_confirmation_quand_il_reste_des_lignes(self):
        js = _sans_commentaires_js(_lire(IMPORT_JS))
        corps = _corps(js, "async function importer()", "function clic(e)")
        assert "laissesDeCote()" in corps
        assert re.search(r"if \(reste\.lignes\)\s*\{\s*S\.confirme = reste", corps), (
            "l'avertissement ne dépend plus de ce qui reste à rattacher"
        )

    def test_la_confirmation_ne_se_redemande_PAS_au_second_clic(self):
        js = _sans_commentaires_js(_lire(IMPORT_JS))
        corps = _corps(js, "async function importer()", "function clic(e)")
        assert "if (!S.confirme)" in corps, "la confirmation reviendrait sans fin"
        assert "S.confirme = null;" in corps

    def test_elle_NOMME_les_lignes_au_lieu_de_les_compter(self):
        corps = _bloc_js(IMPORT_JS, "function blocConfirme()", "// Ce qu'on montre pour une feuille")
        assert re.search(r"montres\.map\([^)]*esc\(", corps), (
            "la confirmation ne liste plus les noms, elle se contente de compter"
        )
        assert "CONFIRME_NOMMES" in corps, "une carto entière tiendrait dans la fenêtre"

    def test_seules_les_TACHES_ont_un_rattachement_a_faire(self):
        """Un rôle ou un outil n'a pas d'activité à retrouver."""
        js = _sans_commentaires_js(_lire(IMPORT_JS))
        corps = _corps(js, "function laissesDeCote()", "function blocConfirme()")
        assert "p.type !== 'taches'" in corps
        assert "'a_rattacher'" in corps

    def test_elle_ne_BLOQUE_pas_l_import(self):
        """Refuser 60 tâches parce que 3 ne s'apparient pas serait un recul."""
        js = _sans_commentaires_js(_lire(IMPORT_JS))
        pied = _corps(js, "if (S.ecran === 'revue' && S.confirme) {",
                      "} else if (S.ecran === 'revue' && S.rapport) {")
        assert "data-action=\"importer\"" in pied
        # le seul motif d'extinction est l'envoi en cours, pas ce qui reste
        assert "S.occupe === 'import' ? ' disabled' : ''" in pied

    def test_on_peut_revenir_a_la_liste(self):
        js = _sans_commentaires_js(_lire(IMPORT_JS))
        assert "case 'cf-annuler': S.confirme = null;" in js

    @pytest.mark.parametrize("cle", [
        "imph.cf_titre", "imph.cf_sous", "imph.cf_plus",
        "imph.cf_garder", "imph.cf_revenir", "imph.cf_importer",
    ])
    def test_les_libelles_existent_dans_LES_DEUX_langues(self, cle):
        fr, en = _les_deux(cle)
        assert fr and en, "%s manque (fr=%r, en=%r)" % (cle, fr, en)
        assert fr != en, "%s n'est pas traduit" % cle

    @pytest.mark.parametrize("cle", ["imph.cf_titre", "imph.cf_plus", "imph.cf_garder"])
    def test_les_libelles_a_nombre_portent_leurs_DEUX_formes(self, cle):
        """⚠️ « 0 rôle » en français, « 0 roles » en anglais : `P()` attend
        « singulier|pluriel », et `{n}` pour le nombre."""
        for lang in ("fr", "en"):
            val = TRANSLATIONS[lang][cle]
            assert "|" in val, "%s [%s] = %r : une seule forme" % (cle, lang, val)
            for forme in val.split("|"):
                assert "{n}" in forme, "%s [%s] : « %s » n'affiche pas le nombre" % (cle, lang, forme)

    @pytest.mark.parametrize("cle", [
        "cf_titre", "cf_sous", "cf_plus", "cf_garder", "cf_revenir", "cf_importer",
    ])
    def test_ils_sont_INJECTES_dans_le_catalogue_du_navigateur(self, cle):
        """Une clé non injectée s'affiche TELLE QUELLE : l'accesseur rend la
        clé quand elle manque, il ne lève rien."""
        html = _lire(T_IMPORT)
        assert re.search(r"\b%s:\s*\{\{ t\('imph\.%s'\)" % (cle, cle), html), (
            "imph.%s n'est pas injectée dans IMPH_I18N" % cle
        )

    def test_l_habillage_est_l_AMBRE_de_l_avertissement(self):
        """Pas le rose-violet de l'IA : c'est un avertissement, pas une
        proposition — et c'est l'ambre de la tuile « à rattacher »."""
        css = _sans_commentaires_css(_lire(IMPORT_CSS))
        bloc = _corps(css, ".imh-confirme {", ".imh-rapport {")
        assert "--imh-warn" in bloc
        assert "--imh-ia-a" not in bloc and "--imh-ia-b" not in bloc
