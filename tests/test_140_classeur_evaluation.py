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
  • LES DEUX COURBES ont quitté la page : la frise des niveaux et le relief en
    unités réelles vivent dans une fenêtre, avec le détail des séances. La
    feuille dit l'ÉTAT, la fenêtre dit l'HISTOIRE ;
  • et l'historique ne se charge QUE là, une seule fois : il ne pèse plus sur
    l'ouverture d'une activité, où personne ne l'avait demandé.
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
        assert "border: 1px solid rgba(255, 255, 255, .2)" in rb
        assert "color: #e3ecfd" in rb
        assert "background" in _regle(css, "\n.cl-rb:hover {")
        # l'icône garde sa pastille, et elle n'a de sens que sur du sombre
        assert "rgba(255, 255, 255, .17)" in _regle(css, "\n.ev-retour > i, .cl-rb > i, .gb > i {")

    def test_la_rangee_de_reglages_est_une_GRILLE(self):
        """⚠️ À quatre pastilles pour 520 px de colonne (mesuré : 544 px de
        contenu), le flex en laissait trois sur une ligne et une toute seule
        en dessous — ça se lit comme un débordement, pas comme une
        disposition."""
        css = _sans_commentaires_css(_lire(CSS))
        r = _regle(css, "\n.ou-reg {")
        assert "display: grid" in r
        assert "repeat(2, minmax(0, 1fr))" in r

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
        m = _corps(js, "  function majBassin(st) {")
        assert "d.textContent = combien[v] === 1 ? String(i + 1) : '';" in m
        assert "d.textContent = String(v)" not in m, "le numéro, jamais le niveau"

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


class TestLeBassinPorteLaComparaison:
    """La règle du minimum se REGARDE au lieu de s'écrire : l'eau monte au
    niveau de l'activité, chaque sortie porte son repère, et l'eau s'arrête au
    repère le plus bas."""

    def test_un_repere_par_sortie_a_la_hauteur_de_son_niveau(self):
        js = _lire(JS)
        b = _corps(js, "  function bassinHtml(st) {")
        assert '(st.results || []).forEach(r => {' in b
        assert 'data-mk=' in b
        # ⚠️ Le gabarit ne porte AUCUN libellé : la pastille est remplie par
        # `majBassin`, parce que son contenu dépend de ce que les AUTRES
        # sorties font, pas d'elle seule.
        assert '<span class="z"></span>' in b
        m = _corps(js, "  function majBassin(st) {")
        assert "m.style.bottom = basY(v) + 'px';" in m

    def test_une_sortie_NON_NOTEE_n_a_pas_de_repere_a_zero(self):
        """⚠️ NULL ≠ 0, et c'est la distinction que tout le module tient. Elle
        n'a pas de repère du tout — et l'eau devient HACHURÉE, parce que
        l'activité n'a alors aucun niveau : un trait plein dirait un verdict
        que personne n'a rendu."""
        js = _lire(JS)
        m = _corps(js, "  function majBassin(st) {")
        assert "m.classList.toggle('est-off', estNul(v));" in m
        assert "if (estNul(v)) return;" in m
        assert "estNul(niv) ? 'hach'" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "display: none" in _regle(css, "\n.bassin .mk.est-off {")
        assert "repeating-linear-gradient" in _regle(css, "\n.bassin .eau.hach {")

    def test_celle_qui_RETIENT_l_eau_porte_un_anneau(self):
        """C'est la réponse à la seule question que le bassin pose."""
        js = _lire(JS)
        m = _corps(js, "  function majBassin(st) {")
        assert "m.classList.toggle('est-bas'" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "box-shadow" in _regle(css, "\n.bassin .mk.est-bas .et {")

    def test_UNE_pastille_par_NIVEAU_et_pas_par_sortie(self):
        """⚠️⚠️ Deux tentatives ont échoué avant celle-ci, et les deux pour la
        même raison — on ne regarde pas un bassin pour y lire une liste.

        EMPILÉES vers le haut, les pastilles se chevauchaient de 2 px et deux
        d'entre elles sortaient du bassin (mesuré à quatre sorties au même
        niveau). CÔTE À CÔTE et réduites à leur numéro, elles ne disaient plus
        rien du tout — « je ne comprends pas les 4 bulles vertes ».

        Seule à son niveau, une sortie porte son NOM avec son numéro : c'est
        le cas courant, et c'est ce que la maquette montrait. À plusieurs, la
        ligne porte le COMPTE, et le détail est sur les cartes de droite.
        """
        js = _lire(JS)
        m = _corps(js, "  function majBassin(st) {")
        assert "const porte = premier[v].r.data_id === r.data_id;" in m
        assert "m.classList.toggle('est-muet', !porte);" in m
        assert "m.classList.toggle('est-seul', combien[v] === 1);" in m
        assert "z.textContent = combien[v] === 1 ? r.name : nf('ou_n_sorties', combien[v]);" in m
        css = _sans_commentaires_css(_lire(CSS))
        et = _regle(css, "\n.bassin .mk .et {")
        assert "left: 16px" in et and "top: -33px" in et, "une seule rangée"
        assert "display: none" in _regle(css, "\n.bassin .mk.est-muet .et {")
        # ⚠️ Et pas de DISQUE sur la pastille de groupe : il y dirait un
        # numéro de carte, et c'est justement ce qu'on ne peut plus désigner.
        assert "display: none" in _regle(css, "\n.bassin .mk:not(.est-seul) .et b {")

    def test_les_noms_SURVIVENT_a_la_pastille_de_groupe(self):
        """Une pastille qui ne dit plus que « 4 sorties » ne doit pas effacer
        l'information pour qui lit l'écran autrement."""
        js = _lire(JS)
        m = _corps(js, "  function majBassin(st) {")
        assert ".map(x => x.name).join(', ');" in m
        assert "setAttribute('aria-label', noms)" in m
        assert ".title = noms;" in m

    def test_le_niveau_affiche_est_un_APERCU_pas_une_seconde_regle(self):
        """⚠️ Le serveur reste la source — l'écran se recharge après
        l'enregistrement. Mais il ne connaît pas la note qu'on vient de poser,
        et c'est justement elle qu'on veut voir bouger l'eau."""
        js = _lire(JS)
        n = _corps(js, "  function niveauActivite(st) {")
        assert "if (!v.length || v.some(estNul)) return null;" in n, "NULL ≠ 0"
        assert "Math.min.apply(null, v)" in n, "le MINIMUM, jamais la moyenne"
        s = js.split("  async function saveEvaluation() {", 1)[1][:1400]
        assert "await refreshDashboard();" in s and "await ouvrirEvaluation(" in s

    def test_le_bassin_se_met_a_jour_SUR_PLACE(self):
        """⚠️ L'eau MONTE quand on pose une note, et c'est ce mouvement qui
        fait comprendre la règle. Réécrit, le bassin sauterait d'un niveau à
        l'autre."""
        js = _lire(JS)
        m = _corps(js, "  function majBassin(st) {")
        assert "innerHTML" not in m, "on déplace, on ne réécrit pas"
        css = _sans_commentaires_css(_lire(CSS))
        assert "transition: height" in _regle(css, "\n.bassin .eau {")
        assert "transition: bottom" in _regle(css, "\n.bassin .mk {")

    def test_ce_qui_reste_a_noter_se_dit_SOUS_le_bassin(self):
        """La bande du classeur le portait ; c'est la seule chose actionnable
        de ce bloc, elle suit le bassin qu'elle explique."""
        js = _lire(JS)
        m = _corps(js, "  function majBassin(st) {")
        assert "nf('ou_manque', manque)" in m
        assert "note.classList.toggle('hidden', !manque);" in m


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
        assert "majBassin(st);" in p and "majNiveauTenu(st);" in p
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
        m = _corps(js, "  function majBassin(st) {")
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

    def test_aucune_courbe_dans_la_feuille(self):
        js = _lire(JS)
        f = _corps(js, "  function carteSortie(r, st, i) {")
        a = _corps(js, "  function ardoiseSortie(r, st, form) {")
        for mort in ("reliefSvg", "friseSvg", "cv2-histo", "pal-relief"):
            assert mort not in f and mort not in a, mort

    def test_la_fenetre_porte_DEUX_schemas_et_un_seul_est_actif(self):
        """Les données ne se lisent pas de la même façon : une échelle commune
        pour COMPARER les sorties, l'unité réelle pour suivre UNE sortie."""
        js = _lire(JS)
        o = _corps(js, "  function rendreOngletsCrb(st) {")
        assert "['niveaux'," in o and "['valeurs'," in o
        assert "T('crb_niveaux')" in o and "T('crb_valeurs')" in o
        # ⚠️ Sans sortie mesurée il n'y a pas de valeur à tracer : la
        # languette le DIT au lieu d'ouvrir un écran vide.
        assert "mes.length > 0" in o and "T('crb_sans_mes')" in o
        assert "b.disabled = !actif;" in o

    def test_les_niveaux_portent_la_frise_les_valeurs_le_relief(self):
        js = _lire(JS)
        c = js.split("  async function rendreCourbes(st) {", 1)[1].split("\n  }", 1)[0]
        assert "friseSvg(h, req, c.querySelector('.hi-s'))" in c
        v = _corps(js, "  function rendreValeurs(st, box) {")
        assert "reliefSvg(r)" in v and "bilanRelief(r.performance)" in v

    def test_le_selecteur_n_existe_que_s_il_y_a_de_quoi_choisir(self):
        """Une rangée d'un seul bouton est un titre déguisé."""
        js = _lire(JS)
        v = _corps(js, "  function rendreValeurs(st, box) {")
        assert "if (mes.length > 1) {" in v

    def test_l_historique_ne_se_charge_QUE_la_et_une_fois(self):
        js = _lire(JS)
        assert js.count("/mastery/historique/") == 1
        c = js.split("  async function rendreCourbes(st) {", 1)[1].split("\n  }", 1)[0]
        assert "if (!crb.histo || crb.cle !== cle) {" in c
        ouvrir = js.split("async function ouvrirEvaluation(", 1)[1][:900]
        assert "/paliers/historique/" not in ouvrir and "/mastery/historique" not in ouvrir

    def test_le_cache_porte_une_CLE_et_pas_le_dernier_venu(self):
        """⚠⚠ Mesuré au banc : `crb.histo` ne portait aucune clé. Ouvert une
        fois, il restait affiché pour TOUTE autre personne et toute autre
        activité — Lina et Theo lisaient la frise de Noe. Et là où le premier
        historique était vide, tout le reste l'était aussi : c'est le
        « aucune note posée pour le moment » signalé, vu de l'autre côté.
        """
        js = _lire(JS)
        assert "histo: null, cle: null" in js
        c = js.split("  async function rendreCourbes(st) {", 1)[1].split("\n  }", 1)[0]
        assert "const cle = `${state.cible}/${st.activity_id}/${state.roleId}`;" in c
        assert "crb.cle = cle;" in c
        # la sortie retenue pour le relief appartient elle aussi à UNE activité
        o = _corps(js, "  function ouvrirCourbes(vue, dataId) {")
        assert "crb.sortie = null;" in o
    def test_la_fenetre_est_declaree_et_se_ferme(self):
        html = _lire(GABARIT)
        assert 'id="cv2-crb-win"' in html and 'id="cv2-crb-ong"' in html
        assert 'id="cv2-crb-body"' in html and 'id="cv2-crb-close"' in html
        js = _lire(JS)
        assert "$('#cv2-crb-close').onclick = fermerCourbes;" in js
        assert "if ($('#cv2-crb-win').classList.contains('open')) fermerCourbes();" in js
        # ⚠️ Le voile est partagé par les TROIS fenêtres : le retirer dès
        # qu'une se ferme laisserait les deux autres posées sans voile.
        f = _corps(js, "  function fermerCourbes() {")
        assert "'#cv2-plan-win'" in f and "'#cv2-drawer'" in f
        d = _corps(js, "  function closeDrawer() {")
        assert "'#cv2-crb-win'" in d

    def test_UNE_seule_porte_vers_les_courbes(self):
        """⚠️ Relevé sur capture : le bouton s'affichait des DEUX côtés sur une
        sortie mesurée — sur la bande ET sur l'ardoise. Deux portes pour un
        seul sujet."""
        js = _lire(JS)
        assert js.count("ouvrirCourbes(") == 2, \
            "la déclaration, la pastille de la bande, et rien d'autre"
        a = _corps(js, "  function ardoiseSortie(r, st, form) {")
        assert "ouvrirCourbes" not in a
        b = _corps(js, "  function reglagesOu(st) {")
        assert "T('cl_courbes')" in b

    def test_le_detail_des_seances_accompagne_les_courbes(self):
        js = _lire(JS)
        v = _corps(js, "  function rendreValeurs(st, box) {")
        assert "const b = card.querySelector('[data-evol]');" in v
        assert "if (b) b.onclick = () => basculerHisto(card, r);" in v
        # ⚠️ `.pal-pied` n'existe plus : un `querySelector` qui rend `null`
        # aurait coupé toute la suite sans rien dire.
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
        assert b.index('id="ev-nav"') < b.index('class="ou-tete"')
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
        assert "T('pal_norme_tag')" in a
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


class TestLaCourbeGlobale:

    def test_elle_se_dessine_SOUS_les_courbes_de_sortie(self):
        """Là où elle en rejoint une, on voit la plus basse portée par un
        large ruban : la règle du minimum se regarde au lieu de s'écrire."""
        js = _lire(JS)
        f = js.split("  function friseSvg(h, req, hote) {", 1)[1].split("\n  }\n", 1)[0]
        assert f.index("class=\"hi-glob\"") < f.index("class=\"hi-l hi-l--")

    def test_un_SEGMENT_porte_l_etat_de_son_point_d_arrivee(self):
        """Une courbe qui passe de 1 à 3 change de famille en chemin, là où
        elle franchit l'attendu."""
        js = _lire(JS)
        f = js.split("  function friseSvg(h, req, hote) {", 1)[1].split("\n  }\n", 1)[0]
        assert "hi-l--${fam(p[k].niveau)}" in f

    def test_le_numero_relie_la_frise_aux_languettes(self):
        js = _lire(JS)
        f = js.split("  function friseSvg(h, req, hote) {", 1)[1].split("\n  }\n", 1)[0]
        assert "class=\"hi-num\"" in f and "text-anchor=\"middle\">${o.num}" in f

    def test_la_frise_porte_une_date_COURTE(self):
        js = _lire(JS)
        assert "function dateCourte(iso)" in js
        f = js.split("  function friseSvg(h, req, hote) {", 1)[1].split("\n  }\n", 1)[0]
        assert "dateCourte(j)" in f
        assert "fmtDate(h.dates[q.t])" in f, "l'info-bulle garde la date entière"


class TestLesReglesDeStyle:

    def test_aucune_regle_neuve_ne_lit_l_accent_doux_de_la_racine(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur `:root`,
        où `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS.
        Les mélanges s'écrivent SUR PLACE."""
        css = _sans_commentaires_css(_lire(CSS))
        bloc = css.split("\n.ev-corps, .cv2-crb-win {", 1)[1]
        for v in ("--pg-accent-soft", "--pg-accent-softer",
                  "--pg-accent-border", "--pg-accent-glow"):
            assert v not in bloc, v

    def test_la_frise_ne_met_pas_son_SVG_a_l_echelle(self):
        """⚠️ Un SVG en `width:100%` rapetisse ses TEXTES avec lui, et la
        taille calculée reste celle du repère du viewBox."""
        js = _lire(JS)
        f = js.split("  function friseSvg(h, req, hote) {", 1)[1].split("\n  }\n", 1)[0]
        assert "Math.max(Math.round(hote ? hote.clientWidth : 0) || FR_MINI, FR_MINI)" in f
        css = _sans_commentaires_css(_lire(CSS))
        assert "overflow-x: auto" in _regle(css, "\n.hi-s {")

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
        cles = ["cl_tenu", "cl_courbes", "cl_seance",
                "ou_titre", "ou_notez", "ou_comp", "ou_collab", "ou_role",
                "ou_act", "ou_attendu", "ou_manque_1", "ou_manque_n",
                "ou_ecart", "ou_au_niveau", "ou_au_dessus",
                "so_main", "so_mesuree",
                "nt_foi", "nt_mienne", "nt_mesure", "nt_auto", "nt_auto_moi",
                "nt_rien",
                "cl_tech_0", "cl_tech_1", "cl_tech_n",
                "cl_tech_ecart_1", "cl_tech_ecart_n",
                "grv_mesure", "cl_prec", "cl_suiv",
                "nota_zero", "nota_mes_ko", "pr_k", "pr_vide",
                "crb_titre", "crb_niveaux", "crb_niveaux_d", "crb_valeurs",
                "crb_valeurs_d", "crb_sans_mes", "crb_choisir",
                "h_titre", "h_vide", "h_glob", "h_glob_d", "h_sous", "h_au",
                "h_sans_glob", "h_jamais", "h_une_note", "h_une_note_d"]
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

    def test_la_fenetre_porte_son_titre_traduit(self):
        html = _lire(GABARIT)
        bloc = html.split('id="cv2-crb-win"', 1)[1].split("</aside>", 1)[0]
        assert 'data-i18n="crb_titre"' in bloc


class TestLArdoisePorteLeFondDeLEnTete:

    def test_les_deux_surfaces_sombres_ont_le_MEME_fond(self):
        """Deux bleus différents sur le même écran se lisaient comme un défaut
        d'impression. ⚠️ Ce sont DEUX déclarations — l'en-tête écrit son
        dégradé, l'ardoise lit le jeton : si l'une change, l'autre doit
        suivre, et c'est ce cliquet qui le dit."""
        css = _sans_commentaires_css(_lire(CSS))
        tete = _regle(css, "\n.ev-tete, .sq-tete {")
        lignes = [l for l in _regle(css, "\n.ev-corps, .cv2-crb-win {").splitlines()
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
        r = _regle(css, "\n.ev-retour, .cl-rb, .gb {")
        assert "border-radius: 999px" in r
        i = _regle(css, "\n.ev-retour > i, .cl-rb > i, .gb > i {")
        assert "border-radius: 50%" in i and "width: 26px" in i
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
