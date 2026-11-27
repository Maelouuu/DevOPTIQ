# -*- coding: utf-8 -*-
"""LE CLASSEUR — l'écran d'évaluation, et les courbes en fenêtre.

Chaque sortie avait SA carte, et les deux régimes en avaient deux très
différentes : « pas encore notée » ne ressemblait en rien à « déjà notée ».
L'axe partagé (10/11) les a mises sur la même rangée ; le classeur (11/11) en
fait les LANGUETTES d'un classeur, et sort les courbes de l'écran où l'on note.
Ce fichier garde ce que la structure promet :

  • bande + languettes + feuille ne font qu'UN objet — trois cartes empilées,
    c'étaient trois contours pour un seul sujet ;
  • la comparaison entre sorties se lit SUR LES LANGUETTES (jauge en quatre
    pas, trait de l'attendu), et la feuille ne porte qu'UNE sortie ;
  • DEUX notes, toujours : celle qui fait foi et ce que le collaborateur se
    donne, sur la MÊME échelle et alignées au pixel — compressée en un repère
    posé sous les crans de la première, la seconde ne se lisait plus comme une
    note ;
  • le 0 ne se remplit JAMAIS — « non démontré », c'est une jauge vide ;
  • une sortie MESURÉE se lit, elle ne se clique pas : son niveau vient du
    chiffre relevé en séance ;
  • LES COURBES ont quitté la page, puis la fenêtre a suivi : « elles sont
    déjà accessibles ». Le relief en unités réelles se lit sur la vue
    d'ensemble ; la frise des niveaux, elle, n'avait que cette fenêtre et
    s'en va avec — c'est le prix de la suppression, et il est écrit.
"""
import io
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS = os.path.join(RACINE, "static", "competences.css")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates", "competences_view.html")


def _lire(p):
    return io.open(p, encoding="utf-8").read()


# ⚠️ Tout ce fichier lit l'ÉCRAN d'évaluation refondu. Le pilote ARaymond
# tourne encore sur l'écran d'avant : la page Compétences est la SEULE chose que
# le report lui a laissée de côté, le temps qu'elle soit au niveau. Un contrôle
# qui rougit toujours n'est plus lu — celui-ci se rallume tout seul le jour où
# l'écran arrive, sans rien à défaire.
ECRAN_REFONDU = "cv2-ecran-eval" in _lire(JS)
pytestmark = pytest.mark.skipif(
    not ECRAN_REFONDU,
    reason="l'écran d'évaluation refondu n'est pas dans cet arbre")


def _corps(js, entete):
    return js.split(entete, 1)[1].split("\n  }", 1)[0]


def _sans_commentaires_css(css):
    """⚠️ Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES : il
    s'attrape sinon lui-même sur l'explication de la règle qu'il garde — c'est
    arrivé six fois dans ce dépôt."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _sans_commentaires_js(js):
    """Même piège côté JS : le contrôle des chevrons français s'est attrapé
    sur le commentaire qui l'explique."""
    return re.sub(r"^\s*//.*$", "", js, flags=re.M)


def _regle(css, selecteur):
    """Le corps d'UNE règle, bornée. ⚠️ Et on borne : un fichier de 3 500
    lignes contient presque toujours un homonyme de ce qu'on croit garder."""
    return css.split(selecteur, 1)[1].split("}", 1)[0]


class TestOuVousEtesEtLesSortiesCoteACote:
    """⚠️ Le classeur ne montrait qu'UNE sortie à la fois, derrière des
    languettes : on ne voyait jamais ensemble les deux chiffres dont le plus
    bas EST le niveau de l'activité — et c'est pourtant la règle de tout le
    module. Tranché sur maquette, à l'échelle : un bloc de NUIT à gauche (la
    chaîne, ce qu'on note, le bassin), une carte par sortie à droite.
    """

    def test_la_page_est_deux_colonnes(self):
        js = _lire(JS)
        sk = js.split('<div class="ev-corps">', 1)[1].split("</div>`;", 1)[0]
        # ⚠️ Le RAIL des activités est parti : une ligne de pastilles pour une
        # liste qu'on parcourt une fois. On change d'activité avec les flèches.
        assert 'id="ev-rail"' not in sk
        for part in ('class="ev-deux" id="ev-deux"', 'class="ev-ou" id="ev-ou"',
                     'id="ev-sorties"', 'id="ev-pied"'):
            assert part in sk, part
        # ⚠️ Le bandeau d'identité d'avant a disparu DANS le bloc de nuit : il
        # redisait le nom de la personne et le niveau du rôle à dix
        # centimètres de la chaîne qui les porte.
        assert '<header class="ev-tete">' not in sk
        # …mais la classe reste déclarée : la séance et le calendrier s'en
        # servent toujours.
        assert '<header class="ev-tete">' in js
        css = _sans_commentaires_css(_lire(CSS))
        assert "grid-template-columns: 560px minmax(0, 1fr)" in _regle(css, "\n.ev-deux {")

    def test_le_bloc_de_nuit_est_UN_objet(self):
        """Le relief du vocabulaire maison : quatre ombres portées empilées,
        plus deux arêtes internes — le haut éclairé, le bas dans
        l'épaisseur."""
        css = _sans_commentaires_css(_lire(CSS))
        ou = _regle(css, "\n.ev-ou {")
        assert "border-radius" in ou and "box-shadow" in ou
        assert ou.count("rgba(15, 22, 49") >= 4, "les quatre ombres portées"
        assert "inset 0 1px 0" in ou and "inset 0 -2px 0" in ou

    def test_les_pastilles_de_reglage_sont_de_VERRE(self):
        """⚠️⚠️ `.cl-rb` a disparu AVEC le bloc du classeur : seule la règle
        de son ICÔNE avait survécu, dans la section des boutons. Les pastilles
        sont donc retombées sur le bouton blanc par défaut — et leur pastille
        d'icône, taillée pour un fond sombre (`rgba(255,255,255,.17)` sur
        `#fff`), est devenue blanche sur blanc : quatre pâtés blancs à glyphe
        invisible sur la carte de nuit.

        Supprimer une section de feuille, c'est emporter ce qui s'y trouvait
        pour d'autres.
        """
        css = _sans_commentaires_css(_lire(CSS))
        rb = _regle(css, "\n.cl-rb {")
        assert "rgba(255, 255, 255, .12)" in rb, "du verre, pas un bouton blanc"
        assert "border: 1px solid rgba(255, 255, 255, .22)" in rb
        assert "color: #fff" in rb
        assert "background" in _regle(css, "\n.cl-rb:hover {")
        # ⚠️ La pastille est désormais un `.ic` et non plus un `> i` : le
        # bouton porte deux lignes (son nom, puis CE QU'IL CONTIENT), il est
        # donc sorti du groupe des pilules. Elle n'a de sens que sur du sombre.
        assert "rgba(255, 255, 255, .18)" in _regle(css, "\n.cl-rb .ic {")

    def test_la_rangee_de_reglages_est_une_GRILLE(self):
        """⚠️ C'était un FLEX : à quatre pastilles pour 520 px de colonne
        (mesuré : 544 px de contenu), il en laissait trois sur une ligne et
        une toute seule en dessous — ça se lit comme un débordement, pas comme
        une disposition.

        ⚠️ RÉÉCRIT (27/11) : elles sont QUATRE depuis que « Configurer
        l'activité » a retrouvé une porte — sa fenêtre était devenue
        injoignable, et c'est là que la norme se règle. La bascule se fait sur
        le NOMBRE d'éléments, comme `.wp-portes` : deux colonnes à deux ou
        quatre (deux rangées pleines), trois à trois. `auto-fit` ne sait pas
        la faire — il compte des pixels, pas des enfants."""
        css = _sans_commentaires_css(_lire(CSS))
        r = _regle(css, "\n.ou-reg {")
        assert "display: grid" in r
        assert "grid-template-columns: 1fr 1fr" in r
        assert "1fr 1fr 1.15fr" in _regle(
            css, "\n.ou-reg:has(.cl-rb:nth-child(3)) {")
        assert "1fr 1fr" in _regle(css, "\n.ou-reg:has(.cl-rb:nth-child(4)) {")
        js = _lire(JS)
        b = _corps(js, "  function reglagesOu(st) {")
        assert b.count("chip(") == 4, "technicité, séance, plan, configurer"
        assert "ouvrirCourbes" not in b

    def test_le_bloc_de_nuit_SUIT_le_defilement(self):
        """C'est le bassin qui porte la comparaison entre les sorties : il doit
        rester sous les yeux pendant qu'on note dans la colonne de droite."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "position: sticky" in _regle(css, "\n.ev-ou {")
        # ⚠️ En colonne unique il n'a plus rien à suivre, et collé il
        # masquerait la carte qu'on vient lire.
        # ⚠️ On vise le bloc étroit QUI PARLE DE LUI : la feuille en porte
        # plusieurs au même point de bascule, et un `rsplit` prenait le
        # dernier venu — l'ajout de la vue d'ensemble l'a montré.
        etroit = next(b for b in css.split("@media (max-width: 1100px) {")[1:]
                      if ".ev-ou" in b.split("\n}")[0])
        assert "position: static" in etroit

    def test_toutes_les_sorties_sont_VISIBLES(self):
        """C'est la raison d'être de la refonte : les deux chiffres dont le
        plus bas fait le niveau se lisent ensemble."""
        js = _lire(JS)
        r = _corps(js, "  function remplirSorties(st) {")
        assert "(st.results || []).forEach((r, i) => z.appendChild(carteSortie(r, st, i)));" in r
        for mort in ("function languettes(", "function majLanguette(",
                     "function montrerSortie(", "function sortieOuverte("):
            assert mort not in js, mort

    def test_le_NUMERO_relie_la_carte_a_son_repere(self):
        """Sans lui, rien ne dirait quelle pastille du bassin appartient à
        quelle sortie.

        ⚠️ Et c'est bien le NUMÉRO qu'elle porte, jamais le niveau : celui-ci
        redirait ce que la HAUTEUR du repère dit déjà, et couperait le seul
        lien entre le bassin et la carte de droite. Relevé sur capture.
        ⚠️ Le numéro s'écrit dans `majBassin` et non dans le gabarit : il ne
        s'affiche que si la sortie est SEULE à son niveau, et cela dépend des
        autres sorties.
        """
        js = _lire(JS)
        c = _corps(js, "  function carteSortie(r, st, i) {")
        assert 'class="so-n">${i + 1}' in c
        m = _corps(js, "  function majPiste(st) {")
        assert "<b class=\"${tenu ? 'v' : ''}\">${i + 1}</b>" in m, \
            "la ligne de la piste porte le NUMÉRO de la carte, jamais le niveau"

    def test_les_deux_regimes_prennent_la_MEME_forme(self):
        """Un rail de couleur dit lequel, un disque dit le niveau : c'est leur
        ressemblance qui rend la différence lisible."""
        js = _lire(JS)
        c = _corps(js, "  function carteSortie(r, st, i) {")
        assert "'so' + (mesuree ? ' lue' : ' pose')" in c
        assert "T(mesuree ? 'so_mesuree' : 'so_main')" in c
        css = _sans_commentaires_css(_lire(CSS))
        assert "width: 5px" in _regle(css, "\n.so::before {")
        assert "linear-gradient" in _regle(css, "\n.so.pose::before {")
        assert "linear-gradient" in _regle(css, "\n.so.lue::before {")


class TestLaPistePorteLaComparaison:
    """⚠️ LA CUVE VERTICALE EST ABANDONNÉE — c'est l'arbitrage de la quatrième
    passe, tranché sur prototype à l'échelle réelle. On y perd la métaphore de
    l'eau qui monte ; on y gagne 90 px de hauteur et surtout la LECTURE : la
    jauge va de gauche à droite, comme toutes les autres jauges de l'app.

    ⚠️ Et c'est ce qui CORRIGE le bassin. Son défaut n'était pas la métaphore
    mais les NOMS DES SORTIES, qui étaient DEDANS : deux libellés anglais de
    cinquante signes s'y chevauchaient et s'y tronquaient — « sur le graphe en
    bas on comprend rien ». Ils sont désormais SOUS la piste, une ligne
    chacun, en entier.
    """

    def test_la_cuve_verticale_n_existe_plus(self):
        js, css = _lire(JS), _lire(CSS)
        nu = _sans_commentaires_js(js)
        for mort in ("bassinHtml", "majBassin", "basY", "basPas", "data-basniv"):
            assert mort not in nu, "js : " + mort
        for mort in (".bassin", ".bas-niv", ".ou-tete", ".ou-comp"):
            assert mort not in _sans_commentaires_css(css), "css : " + mort

    def test_les_NOMS_des_sorties_sont_HORS_du_graphe(self):
        """C'est LE correctif. Dans la piste il n'y a que des chiffres ; les
        noms vivent dans la liste du dessous, avec le numéro qui relie chaque
        sortie à sa carte de droite."""
        js = _lire(JS)
        p = _corps(js, "  function pisteHtml(st) {")
        assert "r.name" not in p and "results" not in p, "la piste ne porte aucun nom"
        m = _corps(js, "  function majPiste(st) {")
        assert "esc(x.name)" in m and "class=\"nm\"" in m
        assert "${i + 1}" in m, "le numéro relie la ligne à sa carte"

    def test_NULL_n_est_PAS_zero(self):
        """Une activité dont une sortie n'est pas notée n'a PAS de niveau : sa
        piste est HACHURÉE jusqu'au plus bas de ce qu'on sait, pas remplie à
        zéro — qui voudrait dire « non démontré »."""
        js = _lire(JS)
        m = _corps(js, "  function majPiste(st) {")
        assert "estNul(niv) ? 'hach'" in m
        assert "PST(estNul(niv) ? bas : niv)" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "repeating-linear-gradient" in _regle(css, "\n.pst-r.hach {")
        # ⚠️ Et un SOCLE dès qu'un niveau est posé : à largeur nulle, le
        # niveau 0 se confondrait avec « pas de niveau du tout ».
        assert "min-width: 10px" in _regle(css, "\n.pst-r.bleu, .pst-r.vert {")

    def test_la_regle_du_MINIMUM_se_VOIT(self):
        """Celle qui retient le niveau est mise en avant : c'est ici que la
        règle se regarde au lieu de s'expliquer."""
        js = _lire(JS)
        m = _corps(js, "  function majPiste(st) {")
        assert "const porte = !nu && v === (estNul(niv) ? bas : niv);" in m
        # ⚠️ On vérifie l'EMPLOI, pas la présence du nom : remplacé par un
        # `false ? ' est-bas'`, le cliquet restait vert sur la branche morte.
        assert "${porte ? ' est-bas' : ''}" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "box-shadow" in _regle(css, "\n.lgs .s.est-bas {")

    def test_le_trait_de_l_ATTENDU_tombe_SUR_sa_graduation(self):
        """⚠️ Mesuré : en `space-between`, ce sont les SPANS qui sont répartis,
        pas leurs centres — le « 3 » tombait à 291 px quand le trait, lui, est
        à 75 % de la voie, soit 293. Les deux sont posés à la même fraction et
        centrés sur ce point."""
        js = _lire(JS)
        p = _corps(js, "  function pisteHtml(st) {")
        assert "left:${PST(req)}%" in p and 'style="left:${PST(i)}%"' in p
        css = _sans_commentaires_css(_lire(CSS))
        assert "translateX(-1px)" in _regle(css, "\n.pst-a {")
        assert "translateX(-50%)" in _regle(css, "\n.pst-g span {")
        assert "space-between" not in _regle(css, "\n.pst-g {")

    def test_la_piste_se_met_a_jour_SUR_PLACE(self):
        """Elle S'ÉTEND quand on pose une note, et c'est ce mouvement qui fait
        comprendre la règle. Réécrite, elle sauterait d'un niveau à l'autre."""
        js = _lire(JS)
        m = _corps(js, "  function majPiste(st) {")
        assert "r.style.width" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "transition: width" in _regle(css, "\n.pst-r {")

    def test_ce_qui_reste_a_noter_se_dit_SOUS_la_piste(self):
        js = _lire(JS)
        m = _corps(js, "  function majPiste(st) {")
        assert "nf('ou_manque', manque)" in m
        b = _corps(js, "  function remplirOu(st) {")
        assert b.index("data-bnote") > b.index("ev-lgs")


class TestLeVerdictEstEnTETE:
    """Le niveau de l'activité et son écart se lisaient DEUX fois : en 48 px
    au-dessus du bassin, puis 295 px plus bas sur la ligne d'eau. Ils sont
    posés une seule fois, à côté du nom de l'activité — en tête, et c'est le
    premier chiffre qu'on lit en arrivant."""

    def test_le_niveau_vit_a_UN_seul_endroit(self):
        js = _lire(JS)
        b = _corps(js, "  function remplirOu(st) {")
        assert b.count("data-niv") == 1
        # ⚠️ `[data-niv]` garde SON contrat : il porte le chiffre ET le « /4 »,
        # parce que `majNiveauTenu` y écrit sans réécrire le bloc de nuit.
        assert "<b data-niv>" in b
        m = _corps(js, "  function majNiveauTenu(st) {")
        assert "'<i>/4</i>'" in m

    def test_le_verdict_est_a_cote_du_nom_de_l_activite(self):
        js = _lire(JS)
        b = _corps(js, "  function remplirOu(st) {")
        tete = b.split('class="bas-h"', 1)[1].split("</div>\n        </div>", 1)[0]
        assert "a.activity_name" in tete and "data-niv" in tete and "data-ecart" in tete

    def test_la_pastille_d_ecart_ne_passe_JAMAIS_a_la_ligne(self):
        """« below target · −2 » fait 92 px en anglais contre 70 en français :
        sur deux lignes, la rangée grandit sous le nom de l'activité."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "white-space: nowrap" in _regle(css, "\n.bas-e {")
        assert "flex: none" in _regle(css, "\n.bas-d {")

    def test_le_chiffre_prend_la_couleur_du_VERDICT(self):
        """Tilleul quand le niveau est tenu, estompé quand il n'y a pas de
        niveau : le chiffre et la piste disent la même chose."""
        js = _lire(JS)
        m = _corps(js, "  function majPiste(st) {")
        assert "d.classList.toggle('est-vert', vert)" in m
        assert "d.classList.toggle('est-vide', estNul(niv))" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "var(--cv-g-20)" in _regle(css, "\n.bas-d.est-vert .bas-v b {")

    def test_le_bloc_ne_lit_aucun_DERIVE_de_l_accent(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur `:root`,
        où `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS.
        Les mélanges s'écrivent SUR PLACE."""
        css = _sans_commentaires_css(_lire(CSS))
        bloc = css.split("\n   LE VERDICT EN T", 1)[1].split("\n/* ", 1)[0] \
            if "\n   LE VERDICT EN T" in css else ""
        for v in ("--pg-accent-soft", "--pg-accent-softer",
                  "--pg-accent-border", "--pg-accent-glow"):
            assert v not in _regle(css, "\n.bas-e {"), v
            assert v not in _regle(css, "\n.pst-r {"), v

    def test_UNE_seule_etiquette_en_capitales_dans_tout_le_bloc(self):
        """Il en portait HUIT, plus nombreuses que ce qu'elles étiquetaient.
        ⚠️ Les trois de la chaîne tombent à l'ŒIL et restent dans
        l'`aria-label` : un lecteur d'écran ne la lit pas d'un coup d'œil."""
        js = _lire(JS)
        b = _corps(js, "  function remplirOu(st) {")
        assert b.count("bas-k") == 1
        assert "ou-lbl" not in b and "ou_titre" not in b
        c = _corps(js, "  function chaineHtml(st, nivAct) {")
        assert 'class="k"' not in c, "les étiquettes de la chaîne sont tombées"
        # ⚠️ L'étiquette doit Être DANS l'`aria-label`, pas seulement exister :
        # vidée de son contenu, la flèche laissait le cliquet vert.
        assert "`aria-label=\"${esc(T(cle) + ' : ' + nom)}\"`" in js, \
            "…et elles restent pour un lecteur d'écran"

    def test_la_competence_passe_derriere_un_i(self):
        """Elle occupait un paragraphe de trois lignes avec sa propre
        étiquette : c'est le motif de la maison — une phrase passe derrière un
        « i », elle ne disparaît pas."""
        js = _lire(JS)
        b = _corps(js, "  function remplirOu(st) {")
        assert "boutonInfo(T('ou_comp'), a.competence)" in b
        assert "ou-comp" not in b


class TestLesDeuxNotes:
    """⚠️ Il y en a TOUJOURS deux : celle qui FAIT FOI, et ce que le
    collaborateur se donne.

    Le classeur (11/11) avait compressé la seconde en un REPÈRE posé sous les
    crans de la première : un point et un libellé, sur la piste de l'autre.
    On ne la lisait plus comme une note — et c'est le reproche qui a rouvert
    ce bloc. Elle redevient une note à part entière : la MÊME échelle, alignée
    AU PIXEL sur la première, parce que c'est cet alignement qui se lit comme
    un accord ou un écart.
    """

    def test_DEUX_blocs_de_note_et_pas_un_repere(self):
        js = _lire(JS)
        n = _corps(js, "  function notaSortie(r, st) {")
        assert "nt nt--foi" in n and "nt nt--auto" in n
        # le repère d'autrefois n'a laissé AUCUNE trace
        assert 'class="soi' not in js
        assert ".crans .soi" not in _lire(CSS)

    def test_l_ordre_ne_bouge_JAMAIS_celle_qui_fait_foi_d_abord(self):
        """Quel que soit le regard : on sait toujours laquelle on lit."""
        js = _lire(JS)
        n = _corps(js, "  function notaSortie(r, st) {")
        assert n.index("z.appendChild(f)") < n.index("z.appendChild(a)")

    def test_celle_qui_est_la_votre_se_CLIQUE_l_autre_est_POSEE(self):
        """Le développeur pose celle qui fait foi, le collaborateur la sienne.
        Celle qui n'est pas la vôtre est une graduation de <span> : rien ne
        s'y clique, et rien ne doit en avoir l'air."""
        js = _lire(JS)
        n = _corps(js, "  function notaSortie(r, st) {")
        assert "const maFoi = dev && !mesuree;" in n
        assert "const monAuto = !dev;" in n
        assert "brancherCrans(f, r, st);" in n
        assert "brancherCrans(a, r, st);" in n
        # ⚠️ Le régime décide de la FORME, des deux côtés : la mienne est une
        # piste, l'autre une graduation. Deux pistes empilées, c'est ce que le
        # classeur avait précisément retiré — et c'est ce que le collaborateur
        # voyait tant que la note qui fait foi restait une piste verrouillée.
        assert "maFoi ? piste(off, req, false) : graduation(off)" in n
        assert "monAuto ? piste(soi, req, false) : graduation(soi)" in n
        g = _corps(js, "  function graduation(niveau) {")
        assert '<button' not in g and 'class="gc' in g

    def test_les_deux_notes_s_alignent_AU_PIXEL(self):
        """Même nombre de colonnes, même espacement — et surtout le MÊME BOUT.

        ⚠️ La piste porte une gomme et le « i » de l'échelle ; la graduation
        n'avait rien. Mesuré au banc : 4,5 px d'écart au deuxième cran, 18 au
        cinquième, pour deux notes dont c'est justement l'alignement qu'on
        vient lire. Elle rend donc des JUMEAUX masqués plutôt qu'une largeur
        recopiée à la main, qui dériverait le jour où l'un des deux change —
        et avec les MÊMES classes : `ev-i` retire la bordure du « i », donc
        un jumeau sans elle restait 1 px trop large.
        """
        js = _lire(JS)
        g = _corps(js, "  function graduation(niveau) {")
        assert '<span class="gomme" aria-hidden="true">' in g
        assert '<span class="cv2-i ev-i" aria-hidden="true">' in g
        css = _sans_commentaires_css(_lire(CSS))
        crans, gcs = _regle(css, "\n.crans {"), _regle(css, "\n.gcs {")
        assert "gap: 11px" in crans and "gap: 11px" in gcs
        j = _regle(css, "\n.grad > .gomme, .grad > .cv2-i {")
        assert "visibility: hidden" in j and "pointer-events: none" in j
        assert ".grad > .cv2-i" in _regle(css, "\n.piste > .cv2-i, .grad > .cv2-i {") \
            or "margin-left: 11px" in _regle(css, "\n.piste > .cv2-i, .grad > .cv2-i {")

    def test_une_graduation_porte_la_couleur_de_SA_note(self):
        """Le collaborateur lit la note qui fait foi en graduation : elle doit
        rester BLEUE. L'identité se tient partout, ou elle ne tient nulle
        part."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "--cv-auto-deep" in _regle(css, "\n.gc.on {")
        assert "var(--b8)" in _regle(css, "\n.nt--foi .gc.on {")

    def test_la_gomme_d_une_piste_LUE_tient_la_largeur(self):
        """⚠️ Retirée du flux, la piste devenait plus large que la graduation
        d'en dessous — et c'est justement leur alignement qu'on vient lire."""
        css = _sans_commentaires_css(_lire(CSS))
        g = _regle(css, "\n.piste.lue .gomme {")
        assert "visibility: hidden" in g and "display: none" not in g

    def test_l_identite_se_tient_PARTOUT(self):
        """Celle qui fait foi en bleu, celle qu'on se donne en violet — y
        compris quand c'est le collaborateur qui pose la sienne sur une piste.
        Sinon la même note changerait de couleur selon qui la regarde."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "color: var(--b8)" in _regle(css, "\n.nt-k.foi {")
        assert "color: var(--cv-auto-deep)" in _regle(css, "\n.nt-k.auto {")
        assert "--cv-auto-deep" in _regle(css, "\n.nt--auto .cran.f {")
        assert "--cv-auto-deep" in _regle(css, "\n.nt--auto .cran .pic {")

    def test_une_sortie_MESUREE_porte_le_rail_a_la_place_de_la_piste(self):
        """Son niveau vient du chiffre relevé en séance : il ne se pose pas,
        donc il n'y a rien à cliquer. Mais elle a bien ses DEUX notes —
        l'auto-évaluation reste permise, c'est un repère que le collaborateur
        se donne, et l'écart avec la mesure se parle en séance."""
        js = _lire(JS)
        assert "const jePosePour = r => (jeSuisLeDev() ? !r.mesurable : true);" in js
        n = _corps(js, "  function notaSortie(r, st) {")
        assert "mesuree ? railHtml(r.performance)" in n
        assert "nt nt--auto" in n
        css = _sans_commentaires_css(_lire(CSS))
        assert "pointer-events: none" in _regle(css, "\n.piste.lue .cran {")

    def test_le_verdict_d_accord_est_HORS_des_deux_blocs(self):
        """Posé dans celui du bas, il se lisait comme un commentaire de
        l'auto-évaluation — or il parle de l'ÉCART, donc des deux."""
        js = _lire(JS)
        n = _corps(js, "  function notaSortie(r, st) {")
        assert n.index("z.appendChild(a)") < n.index("v.className = 'nota-vd'")

    def test_chaque_note_dit_ce_qu_elle_VAUT(self):
        js = _lire(JS)
        v = _corps(js, "  function valeurNote(niveau) {")
        assert "T('nt_rien')" in v and "levelName(niveau)" in v
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "majValeur(foi, off)" in m and "majValeur(au, soi)" in m

    def test_les_cles_des_deux_notes_existent_dans_les_DEUX_langues(self):
        js = _lire(JS)
        for c in ("nt_foi", "nt_mienne", "nt_mesure", "nt_auto",
                  "nt_auto_moi", "nt_rien"):
            assert js.count("      " + c + ":") == 2, c

    # ── Ce qui ne change pas : la piste elle-même ────────────────────────

    def test_cinq_crans_et_une_seule_piste_par_note(self):
        js = _lire(JS)
        assert "function blocNote(" not in js, "les deux blocs sont remplacés"
        p = _corps(js, "  function piste(pose, attendu, lue) {")
        assert "for (let i = 0; i <= 4; i++)" in p

    def test_le_zero_se_remplit_COMME_LES_AUTRES(self):
        """⚠️ RENVERSEMENT de la règle du 11/11 (« le 0 ne se remplit jamais »).
        Elle venait de la jauge à quatre pas, où le niveau 0 est une jauge
        VIDE. Sur une piste qui porte un cran « 0 », elle laissait un trou
        blanc à gauche d'une barre qui part à 1 — on le lisait comme un
        défaut, pas comme un sens.

        La distinction NULL ≠ 0 tient toujours, et mieux : rien de posé, rien
        de rempli ; 0 posé, le seul cran 0 — un cran plein se voit de loin, un
        anneau se cherche.
        """
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, lue) {")
        assert "if (!estNul(pose) && i <= pose) c += ' f'" in p
        assert "i >= 1" not in p, "le 0 est un cran comme les autres"
        assert "' zero'" not in p
        css = _sans_commentaires_css(_lire(CSS))
        assert ".cran.zero" not in css, "l'anneau n'a plus d'objet"
        # …et la mise à jour sur place tient la même règle
        m = _corps(js, "  function majPiste(bloc, niveau, attendu) {")
        assert "if (!estNul(niveau) && i <= niveau) {" in m

    def test_la_pastille_dit_QUEL_niveau_on_vient_de_poser(self):
        """Un cran rempli ne dit pas lequel on a choisi : la pastille le pose
        sur SON cran, avec son bec, au lieu d'obliger à lire le mot à l'autre
        bout de la ligne."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, lue) {")
        assert "const pic = (!estNul(pose) && i === pose)" in p
        assert 'class="pic">${esc(levelName(i))}' in p
        # ⚠️ Elle SE DÉPLACE : deux pastilles diraient deux niveaux.
        m = _corps(js, "  function majPiste(bloc, niveau, attendu) {")
        assert "if (p && i !== niveau) p.remove();" in m
        css = _sans_commentaires_css(_lire(CSS))
        pic = _regle(css, "\n.cran .pic {")
        assert "pointer-events: none" in pic, \
            "ce qui explique ne vole jamais le clic de ce qu'il explique"
        assert "border-top-color" in _regle(css, "\n.cran .pic::after {"), "le bec"

    def test_la_zone_attendue_est_une_SURFACE_et_n_existe_pas_sans_requis(self):
        """« La barre doit entrer dans le vert » se regarde ; un filet de 2 px
        se cherche. Et NULL ≠ 0 : sans requis, pas de zone."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, lue) {")
        assert 'if (attendu !== null) h += `<span class="zone"' in p
        css = _sans_commentaires_css(_lire(CSS))
        z = _regle(css, "\n.crans .zone {")
        assert "background: var(--v1)" in z and "border: 1px solid var(--v3)" in z

    def test_la_gomme_vit_HORS_des_crans(self):
        """Effacer n'est pas un niveau de plus, et la zone attendue ne doit
        pas l'englober — elle aurait l'air d'un sixième cran."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, lue) {")
        i = p.index('</div><button type="button" class="gomme"')
        assert p.index('class="zone"') < i, "la zone vit dans .crans, la gomme non"

    def test_un_cran_ne_porte_que_son_chiffre_et_son_nom_au_survol(self):
        """⚠️ Pas d'attribut `title` : l'info-bulle du système sortirait
        par-dessus la nôtre, une seconde plus tard et sans sa couleur."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, lue) {")
        assert 'data-nom="${esc(levelName(i))}"' in p
        assert "title=" not in p
        css = _sans_commentaires_css(_lire(CSS))
        assert "content: attr(data-nom)" in _regle(css, "\n.cran::after {")
        assert "transition-delay: .5s" in _regle(css, "\n.cran:hover::after {")

    def test_la_note_a_UNE_source_et_la_piste_se_met_a_jour_sur_place(self):
        """⚠️ Réécrire la piste ferait perdre le focus du cran qu'on vient de
        cliquer, et couperait la transition de la marche qui se remplit."""
        js = _lire(JS)
        p = _corps(js, "  function poserNote(r, niveau, st) {")
        assert "state.saisie[r.data_id] = Object.assign({}, avant, { niveau: niveau });" in p
        assert "majNota(z, r, st)" in p and "majDisque(carte, r, st);" in p
        assert "majPiste(st);" in p and "majNiveauTenu(st);" in p
        assert "innerHTML" not in p, "on bascule des classes, on ne réécrit pas"

    def test_l_enregistrement_lit_l_etat_et_pas_le_DOM(self):
        js = _lire(JS)
        s = js.split("  async function saveEvaluation() {", 1)[1][:400]
        assert "Object.keys(state.saisie" in s
        assert "querySelectorAll" not in s


class TestCeQuiEtaitDIT_DEUX_FOIS:
    """Quatre libellés disaient ce qu'un autre élément de l'écran disait déjà,
    souvent plus gros et à deux centimètres. Chacun est parti."""

    def test_le_bandeau_ne_recompte_plus_les_activites_evaluees(self):
        js = _lire(JS)
        assert "ev_evaluees" not in js, "le rail porte déjà le compte et l'état"

    def test_la_bande_ne_garde_que_ce_qui_RESTE_a_faire(self):
        """« Maîtrise étendue · le minimum de ses 2 sorties » redisait le grand
        chiffre juste au-dessus, et la règle que le « i » explique déjà."""
        js = _lire(JS)
        b = _corps(js, "  function remplirOu(st) {")
        assert "nf('cl_min'" not in b
        assert "levelName(niv)" not in b, "le grand chiffre suffit"
        m = _corps(js, "  function majPiste(st) {")
        assert "ou_manque" in m, "ce qui reste à noter est la seule chose actionnable"

    def test_le_verdict_ne_redit_plus_la_piste_verte(self):
        """⚠️ `nota_mes_ko` reste : il dit ce qui FERA monter le niveau. C'est
        le _ok qui était du bruit — la piste est verte et la pastille dit
        « qualifié »."""
        js = _lire(JS)
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "nota_mes_ok" not in m
        assert "nota_mes_ko" in m

    def test_le_filtre_part_avec_le_rail_qu_il_filtrait(self):
        """Un filtre qui n'a plus de liste à filtrer ne filtre rien. ⚠️ Les
        quatre compteurs de la VUE D'ENSEMBLE, eux, restent : ils sont
        devenus le PANNEAU du grand chiffre, à côté de ce qu'ils expliquent,
        et ils s'y affichent toujours même à zéro."""
        js = _lire(JS)
        assert "function rendreFiltres" not in js
        assert "ev-f--" not in js, "les tuiles du rail sont parties avec lui"
        o = _corps(js, "  function renderOeil(ap) {")
        for c in ("'held'", "'gap'", "'todo'", "'setup'"):
            assert c in o, c


class TestLesCourbesQuittentLaPage:
    """« Les courbes on supprime, elles sont déjà accessibles, donc la pop-up
    à deux pages des courbes ça dégage. »

    ⚠️ Les deux schémas n'étaient PAS accessibles de la même façon : le relief
    des VALEURS se lit sur la vue d'ensemble, la frise des NIVEAUX n'existait
    QUE là. Elle s'en va donc avec la fenêtre — ce n'est pas un oubli, c'est
    le prix de la suppression, et il est écrit.
    """

    def test_la_fenetre_n_existe_plus_nulle_part(self):
        html, js, css = _lire(GABARIT), _lire(JS), _lire(CSS)
        for mort in ("cv2-crb-win", "crb-ong", "crb-vide", "crb-relief"):
            assert mort not in html, "gabarit : " + mort
            assert mort not in css, "css : " + mort
        # ⚠️ Sur le JS SANS COMMENTAIRES : le commentaire qui explique le
        # retrait NOMME ce qui est retiré, et le cliquet s'attrapait sur sa
        # propre explication — c'est la neuvième fois dans ce dépôt.
        nu = _sans_commentaires_js(js)
        for mort in ("ouvrirCourbes", "fermerCourbes", "rendreCourbes",
                     "rendreValeurs", "rendreOngletsCrb", "rendreNiveaux"):
            assert mort not in nu, "js : " + mort

    def test_la_frise_des_niveaux_part_AVEC_elle(self):
        """Elle n'avait qu'un lieu. Son code, ses styles et ses dix clés
        partent ensemble : une clé qu'on retire en même temps que son seul
        lecteur ne laisse rien derrière elle, et une clé absente s'affiche
        TELLE QUELLE sans rien lever."""
        js, css = _lire(JS), _lire(CSS)
        nu = _sans_commentaires_js(js)
        for mort in ("friseSvg", "legendeHistorique", "dateCourte", "FR_MINI"):
            assert mort not in nu, "js : " + mort
        for mort in (".hi-", ".cv2-histo"):
            assert mort not in css, "css : " + mort
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        for mort in ("h_titre", "h_glob", "h_sous", "crb_titre", "crb_niveaux",
                     "cl_courbes"):
            assert (mort + ":") not in fr, "catalogue : " + mort

    def test_le_relief_reste_sur_la_vue_d_ensemble(self):
        """Ce que la suppression ne doit PAS emporter : le relief en unités
        réelles, son sélecteur de sortie et le détail des séances vivent dans
        la bande de la vue d'ensemble — c'est de là qu'ils étaient « déjà
        accessibles », et c'est ce qui rend la fenêtre superflue."""
        js, css = _lire(JS), _lire(CSS)
        assert "box.innerHTML = reliefSvg({ name: s.nom, performance: s });" in js
        assert "pick.className = 'crb-pick';" in js
        assert ".crb-pick" in css and ".crb-p {" in css
        # ⚠️ Une rangée d'un seul bouton est un titre déguisé.
        assert "if (mes.length > 1) {" in js

    def test_aucune_courbe_dans_la_feuille(self):
        js = _lire(JS)
        f = _corps(js, "  function carteSortie(r, st, i) {")
        a = _corps(js, "  function ardoiseSortie(r, st, form) {")
        for mort in ("reliefSvg", "friseSvg", "cv2-histo", "pal-relief"):
            assert mort not in f and mort not in a, mort

    def test_le_detail_des_seances_survit_et_reste_cable(self):
        """⚠️ Il avait déjà été rendu et CÂBLÉ NULLE PART une fois — mesuré au
        banc, `b.onclick === null`. Le retrait de la fenêtre ne doit pas le
        débrancher une seconde fois.
        ⚠️ Et `.pal-pied` n'existe plus : un `querySelector` qui rend `null`
        couperait toute la suite sans rien dire."""
        js = _lire(JS)
        assert "basculerHisto(z, { name: s.nom, performance: s })" in js
        h = _corps(js, "  function basculerHisto(card, r) {")
        assert "card.querySelector('.pal-bilan') || card.lastElementChild" in h


class TestLesDeuxReglagesQuittentLaPage:

    def test_la_technicite_est_une_pastille_qui_ouvre_un_dialogue(self):
        """C'est un AUTRE axe que la maîtrise, et c'est un réglage : il n'a
        pas à occuper une colonne de l'écran où l'on note."""
        js = _lire(JS)
        b = _corps(js, "  function reglagesOu(st) {")
        assert "T('ev_tech')" in b and "ouvrirTechnicite()" in b
        t = _corps(js, "  function ouvrirTechnicite() {")
        assert "ouvrirDialogue(T('ev_tech'), true)" in t
        assert "cv2-domlist" in t and "cv2-domadd" in t

    def test_les_domaines_ont_UNE_source(self):
        """La pastille et le dialogue la relisent tous deux — deux
        chargements finiraient par afficher deux comptes du même réglage."""
        js = _lire(JS)
        l = _corps(js, "  async function loadTech(zone) {")
        assert "state.tech = { domains:" in l and "majChipTech();" in l
        assert "const chargerTech = () => loadTech(null);" in js
        t = _corps(js, "  function ouvrirTechnicite() {")
        assert "api(" not in t, "le dialogue relit l'état, il ne recharge pas"

    def test_la_prochaine_seance_est_une_pastille_ambre(self):
        js = _lire(JS)
        b = _corps(js, "  function reglagesOu(st) {")
        assert "prochaineEcheance(st)" in b
        assert "chip(ech ? 'amb' : '', 'fa-calendar-days'" in b
        assert "T(ech ? 'cl_seance' : 'ses_cal')" in b, \
            "une pastille d'avertissement allumée en permanence n'avertit plus"


class TestLaNavigationParFleches:

    def test_le_rail_des_activites_n_existe_plus(self):
        """Une ligne de pastilles au-dessus du classeur, pour une liste qu'on
        parcourt une fois : une surface de plus pour un geste qu'on fait deux
        fois. Les flèches vivent là où on lit le nom de l'activité."""
        js = _lire(JS)
        css = _sans_commentaires_css(_lire(CSS))
        for mort in ("function remplirActivites", "ev-rail", "'rh'"):
            assert mort not in js, mort
        for mort in (".ev-rail", ".rh ", ".ev-f"):
            assert mort not in css, mort

    def test_une_fleche_seulement_si_elle_MENE_quelque_part(self):
        """⚠️ Un bouton qui ne mène nulle part n'est pas un bouton : la
        gauche n'existe que passé la première activité, la droite que tant
        qu'il en reste une. Une seule activité : pas de navigation du tout."""
        js = _lire(JS)
        nav = _corps(js, "  function majNav() {")
        assert "if (i > 0) z.appendChild(fleche(-1, state.rows[i - 1]));" in nav
        assert "if (i < n - 1) z.appendChild(fleche(1, state.rows[i + 1]));" in nav
        assert "i < 0 || n < 2" in nav

    def test_le_compte_dit_ou_l_on_est(self):
        """Le rail portait « 6 activités ». Sans le compte, rien ne dirait
        qu'il y en a d'autres."""
        js = _lire(JS)
        nav = _corps(js, "  function majNav() {")
        assert "(i + 1) + ' / ' + n" in nav

    def test_la_fleche_dit_OU_elle_mene(self):
        """Une flèche nue ne dit même pas comment s'appelle l'activité d'à
        côté. Et le libellé passe par le catalogue, dans les deux langues."""
        js = _lire(JS)
        nav = _corps(js, "  function majNav() {")
        assert "T(sens > 0 ? 'cl_suiv' : 'cl_prec')" in nav
        assert "cible.activity_name" in nav
        assert "b.title = lbl; b.setAttribute('aria-label', lbl);" in nav

    def test_elle_vit_sur_la_bande_a_droite_du_niveau_tenu(self):
        js = _lire(JS)
        b = _corps(js, "  function remplirOu(st) {")
        # ⚠️ Elle vit en TÊTE du bloc de nuit, à droite du retour : c'est
        # la ligne qui dit où l'on est, pas celle qui dit ce qu'on note.
        assert b.index('class="ou-h"') < b.index('id="ev-nav"')
        assert b.index('id="ev-nav"') < b.index('class="fil"')
        assert "majNav();" in b
        css = _sans_commentaires_css(_lire(CSS))
        assert "border-left" in _regle(css, "\n.cl-nav {")

    def test_changer_d_activite_GLISSE(self):
        """⚠️ Sans mouvement, changer d'activité se lit comme un
        rechargement de page. Et on ne passe pas par l'attente : `showBusy`
        remplacerait le classeur par une roue, ce qui couperait le glissé."""
        js = _lire(JS)
        o = _corps(js, "  async function ouvrirEvaluation(row, sens) {")
        assert "state.glisse = sens || 0;" in o
        assert "est-sort-d' : 'est-sort-g'" in o
        assert "else showBusy(null, '#cv2-ecran-eval');" in o
        css = _sans_commentaires_css(_lire(CSS))
        for k in ("@keyframes cl-ent-d", "@keyframes cl-ent-g",
                  ".ev-deux.est-sort-d", "prefers-reduced-motion"):
            assert k in css, k

    def test_la_classe_d_animation_ne_reste_pas_collee(self):
        """⚠️ Un `animation-fill-mode: both` laisse son `transform`
        appliqué, et un élément transformé devient le repère des descendants
        `position: fixed` — le piège déjà payé sur la fiche d'examen."""
        js = _lire(JS)
        g = _corps(js, "  function glisserEntree() {")
        assert "addEventListener('animationend'" in g
        assert "classList.remove(c)" in g

    def test_un_echec_reseau_ne_laisse_pas_le_classeur_efface(self):
        js = _lire(JS)
        o = _corps(js, "  async function ouvrirEvaluation(row, sens) {")
        assert "if (sortant) sortant.classList.remove('est-sort-d', 'est-sort-g');" in o


class TestLArdoise:

    def test_ce_qui_est_DONNE_ne_se_regle_pas_ici(self):
        """La norme vient de la colonne Performance de la LISTE DES
        ACTIVITÉS : cet écran la MONTRE."""
        js = _lire(JS)
        a = _corps(js, "  function ardoiseSortie(r, st, form) {")
        assert "T('pal_norme')" in a
        assert "T('ax_reussi')" in a and "T('pal_indic')" in a
        assert "T('pal_norme_off')" in a
        assert "T('fi_requis')" in a, "le requis du rôle est donné, lui aussi"

    def test_le_releve_entre_DANS_la_pastille(self):
        """« mesuré 46 h le 12 oct. » était une ligne grise de plus sous
        chaque sortie."""
        js = _lire(JS)
        a = _corps(js, "  function ardoiseSortie(r, st, form) {")
        assert "Tv('grv_mesure', { x: nombre(perf.mesure) + u })" in a
        assert "perf.qualifie ? '' : ' ko'" in a

    def test_le_standard_se_CITE_avec_un_q(self):
        """⚠️ Les chevrons sont une convention FRANÇAISE : le navigateur pose
        les guillemets de la langue du document tout seul."""
        js = _lire(JS)
        a = _sans_commentaires_js(_corps(js, "  function ardoiseSortie(r, st, form) {"))
        assert "<q>${esc(std)}</q>" in a
        assert "«" not in a
        css = _sans_commentaires_css(_lire(CSS))
        assert "quotes:" in _regle(css, "\n.grav .v q {")


class TestLesReglesDeStyle:

    def test_aucune_regle_neuve_ne_lit_l_accent_doux_de_la_racine(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur `:root`,
        où `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS.
        Les mélanges s'écrivent SUR PLACE."""
        css = _sans_commentaires_css(_lire(CSS))
        bloc = css.split("\n.ev-corps {\n", 1)[1]
        for v in ("--pg-accent-soft", "--pg-accent-softer",
                  "--pg-accent-border", "--pg-accent-glow"):
            assert v not in bloc, v

    def test_les_points_de_bascule_sont_en_px_REELS(self):
        """⚠️ `body.pg` porte `zoom: .8` et les requêtes média IGNORENT ce
        zoom : 1180 px écrits = 944 px réels."""
        css = _lire(CSS)
        bloc = css.split("LE CLASSEUR — la page d'évaluation", 1)[1]
        assert "@media (max-width: 1180px)" in bloc
        assert "zoom" in bloc, "la règle doit dire pourquoi ce seuil-là"


class TestLesLibellesSontDansLesDeuxLangues:

    def test_les_cles_du_classeur_et_des_courbes(self):
        """⚠️ Une clé absente d'une langue ne lève RIEN : elle retombe
        silencieusement sur le français, ou s'affiche telle quelle. On lit
        donc les DICTIONNAIRES, pas le rendu."""
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        cles = ["cl_seance",
                "ou_notez", "ou_comp", "ou_collab", "ou_role",
                "ou_act", "ou_attendu", "ou_manque_1", "ou_manque_n",
                "ou_ecart", "ou_au_niveau", "ou_au_dessus",
                "so_main", "so_mesuree",
                "nt_foi", "nt_mienne", "nt_mesure", "nt_auto", "nt_auto_moi",
                "nt_rien",
                "cl_tech_0", "cl_tech_1", "cl_tech_n",
                "cl_tech_ecart_1", "cl_tech_ecart_n",
                "grv_mesure", "cl_prec", "cl_suiv",
                "nota_zero", "nota_mes_ko", "pr_k", "pr_vide",
                "cl_tech_0"]
        for k in cles:
            assert (k + ":") in fr, "FR " + k
            assert (k + ":") in en, "EN " + k

    def test_le_pluriel_ne_se_devine_pas(self):
        """« 1 sortie pas encore notée » et « 2 sorties pas encore notées » ne
        s'accordent pas de la même façon : `nf()` essaie la forme qui EXISTE.
        ⚠️ Et une clé absente ne lève rien — elle s'affiche telle quelle."""
        js = _lire(JS)
        for c in ("ou_manque", "cl_tech", "cl_tech_ecart"):
            assert ("%s_1:" % c) in js and ("%s_n:" % c) in js, c

    def test_les_cles_du_classeur_sont_parties_avec_lui(self):
        """⚠️ Une clé qu'on retire en même temps que son seul lecteur ne
        laisse rien derrière elle. La bande, les languettes et le bandeau
        d'identité en portaient neuf : elles n'ont plus personne pour les
        lire, et un catalogue qui garde des clés mortes finit par cacher
        celles qui comptent."""
        js = _lire(JS)
        for mort in ("cl_reste_1", "cl_reste_n", "cl_mes:", "cl_main:",
                     "cl_rien:", "ev_nb_act", "ev_suivi_par", "ev_niv_role"):
            assert mort not in js, mort


class TestLArdoisePorteLeFondDeLEnTete:

    def test_les_deux_surfaces_sombres_ont_le_MEME_fond(self):
        """Deux bleus différents sur le même écran se lisaient comme un défaut
        d'impression. ⚠️ Ce sont DEUX déclarations — l'en-tête écrit son
        dégradé, l'ardoise lit le jeton : si l'une change, l'autre doit
        suivre, et c'est ce cliquet qui le dit."""
        css = _sans_commentaires_css(_lire(CSS))
        tete = _regle(css, "\n.ev-tete, .sq-tete {")
        lignes = [l for l in _regle(css, "\n.ev-corps {\n").splitlines()
                  if "--nuit:" in l]
        assert lignes, "le jeton --nuit porte le fond de l'en-tête"
        deg = lignes[0].split("--nuit:", 1)[1].strip().rstrip(";")
        assert deg in tete, "l'ardoise ne porte plus le fond de l'en-tête"
        assert "var(--nuit)" in _regle(css, "\n.grav {")
        # l'ancienne ardoise avait ses deux bleus à elle
        assert "--ard1" not in css and "--ard2" not in css


class TestLaNotationNeGardeQueLaPisteEtLeVerdict:

    def test_nota_k_et_nota_d_sont_partis(self):
        """`nota-k` annonçait le régime et redisait l'attendu, que la zone
        verte de la piste DESSINE. `nota-d` écrivait le niveau en 52 px — une
        TROISIÈME fois, après la languette et la bande."""
        js = _sans_commentaires_js(_lire(JS))
        css = _sans_commentaires_css(_lire(CSS))
        for mort in ("nota-k", "nota-d", "nota-g", "data-gros", "data-mot"):
            assert mort not in js, mort
            assert mort not in css, mort
        for cle in ("nota_foi", "nota_mes:", "nota_vous", "nota_rien",
                    "nota_att", "nota_cette"):
            assert cle not in js, cle

    def test_le_verdict_SURVIT(self):
        """⚠️ Il parle de l'ÉCART entre les deux notes : il n'est écrit nulle
        part ailleurs, et il se lit à côté de la piste qui les porte."""
        js = _lire(JS)
        n = _corps(js, "  function notaSortie(r, st) {")
        assert "v.className = 'nota-vd'" in n and "v.dataset.vd = ''" in n
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "z.querySelector('[data-vd]').innerHTML = vd;" in m
        assert "accordBadge(" in m

    def test_l_echelle_se_range_au_bout_de_SA_piste(self):
        """L'explication des cinq paliers vivait dans l'en-tête parti : elle
        se range où elle sert."""
        js = _lire(JS)
        n = _corps(js, "  function notaSortie(r, st) {")
        assert "f.querySelector('.piste').appendChild(boutonInfo(T('pal_echelle_t')" in n

    def test_la_bulle_de_l_echelle_ne_se_pose_pas_SUR_son_bouton(self):
        """⚠️ `getBoundingClientRect()` rend DÉJÀ des pixels d'écran : seules
        les coordonnées qu'on ÉCRIT repassent par le `zoom: .8` du corps.
        Multiplier la hauteur avant de la soustraire posait la bulle SUR son
        propre « i », son bas 18 px sous le haut du bouton — mesuré au banc,
        et c'est le correctif déjà appliqué à la page Temps le 08/11."""
        js = _lire(JS)
        b = _corps(js, "  function brancherInfo(bouton, titre, texte) {")
        assert "b.height * z" not in b and "b.width * z" not in b
        assert "const dessus = r.top - b.height - 8;" in b
        # …mais les coordonnées ÉCRITES, elles, se divisent bien
        assert "/ z + 'px'" in b

    def test_la_piste_est_BORNEE(self):
        """⚠️ Cinq crans étalés sur les 1 700 px de la feuille ne sont plus
        une échelle, ce sont cinq panneaux."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "max-width" in _regle(css, "\n.piste {")


class TestUnSeulVocabulaireDeBoutons:

    def test_tout_ce_qui_AGIT_est_une_pilule(self):
        """Trois formes cohabitaient : des pilules à pastille ronde
        (l'en-tête, les formulaires), des rectangles arrondis à icône nue (la
        bande, l'ardoise), et le bouton de retour."""
        css = _sans_commentaires_css(_lire(CSS))
        r = _regle(css, "\n.ev-retour, .gb {")
        assert "border-radius: 999px" in r
        i = _regle(css, "\n.ev-retour > i, .gb > i {")
        assert "border-radius: 50%" in i and "width: 26px" in i
        # ⚠️ `.cl-rb` est sorti du groupe : ce n'est plus une pilule mais un
        # bouton à deux lignes, et sa pastille est un `.ic`. Le laisser dedans
        # lui aurait donné un rayon de 999 px pour un contenu de deux lignes.
        assert ".cl-rb" not in r
        # sans libellé, le bouton EST le disque : les flèches de navigation
        assert "border-radius: 50%" in _regle(css, "\n.cl-nav-b {")

    def test_le_retour_porte_une_icone_comme_les_autres(self):
        """Il dessinait son chevron en SVG : il ne pouvait pas recevoir la
        pastille ronde que portent les autres familles — et le rembourrage
        gauche de la pilule, calculé POUR cette pastille, collait le chevron
        au bord. ⚠️ TROIS écrans en portent un (l'évaluation, la séance, le
        calendrier) : ils partagent la classe, donc la correction aussi."""
        js = _lire(JS)
        bouts = js.split('class="ev-retour"')[1:]
        assert len(bouts) == 3, "évaluation, séance, calendrier"
        for b in bouts:
            assert '<i class="fa-solid fa-chevron-left">' in b[:240], b[:90]
            assert "<svg" not in b[:240], b[:90]

    def test_les_crans_gardent_leur_RECTANGLE(self):
        """⚠️ Ce sont les graduations d'une échelle, pas des actions : une
        règle se lit, elle ne s'actionne pas. Ils ne reçoivent du vocabulaire
        commun que le soin, jamais la forme."""
        css = _sans_commentaires_css(_lire(CSS))
        c = _regle(css, "\n.cran {")
        assert "border-radius: 14px" in c
        assert "999px" not in c


class TestLaPorteDuRole:
    """⚠️ Le maillon du RÔLE est une PORTE : il ramène à la vue d'ensemble,
    ouverte sur le détail de CE rôle — une ligne par activité, avec sa cible.
    On n'y venait que par un point du radar, et il n'existait aucun chemin
    depuis l'écran où l'on note."""

    def test_le_maillon_du_role_ouvre_la_vue_d_ensemble_SUR_CE_ROLE(self):
        js = _lire(JS)
        ch = _corps(js, "  function chaineHtml(st, nivAct) {")
        assert "data-aller-role" in ch
        assert "state.roleId ? porte(" in ch, "sans rôle, pas de porte"
        ou = _corps(js, "  function remplirOu(st) {")
        assert "state.voRole = state.roleId; chargerSynthese();" in ou

    def test_la_demande_ne_SURVIT_pas_a_son_arrivee(self):
        """Gardée, elle rouvrirait les barres à chaque changement de
        collaborateur — et le radar ne se verrait plus jamais."""
        js = _lire(JS)
        p = _corps(js, "  function renderProfil(d) {")
        assert "state.voRole = null;" in p
        assert p.index("state.voRole = null;") < p.index("if (vr) ouvrirBarres(box, vr);")
        # ⚠️ APRÈS `animerProfil`, qui remet la zone sur le radar.
        assert p.index("animerProfil(box, vus, d);") < p.index("if (state.voRole) {")

    def test_le_maillon_est_un_BOUTON_donc_il_reprend_sa_police(self):
        """Un <button> s'affiche dans la police et l'encre du SYSTÈME : au
        milieu d'une chaîne de trois maillons, il aurait été le seul."""
        css = _sans_commentaires_css(_lire(CSS))
        b = _regle(css, "\nbutton.mail {")
        assert "font: inherit" in b and "color: inherit" in b and "cursor: pointer" in b

    def test_le_libelle_de_la_porte_existe_dans_les_DEUX_langues(self):
        js = _lire(JS)
        for langue in ("    fr: {", "    en: {"):
            d = js.split(langue, 1)[1].split("\n    },", 1)[0]
            assert "ou_voir_role:" in d, langue


# ══════════════════════════════════════════════════════════════════════════
