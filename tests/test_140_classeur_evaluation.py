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
  • UNE piste de cinq crans, pas deux échelles de cinq : le niveau qui fait
    foi EST la piste, et l'auto-évaluation est un repère dessus ;
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

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS = os.path.join(RACINE, "static", "competences.css")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates", "competences_view.html")


def _lire(p):
    return io.open(p, encoding="utf-8").read()


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


class TestLeClasseurEstUnSeulObjet:

    def test_la_page_est_une_colonne_rail_classeur_pied(self):
        js = _lire(JS)
        sk = js.split('<div class="ev-corps">', 1)[1].split("</div>`;", 1)[0]
        for part in ('id="ev-rail"', 'class="cl" id="ev-cl"', 'class="cl-bande"',
                     'id="ev-cl-h"', 'id="ev-ong"', 'id="ev-feuille"', 'id="ev-pied"'):
            assert part in sk, part
        # ⚠️ Les trois colonnes sont parties avec la refonte : la droite
        # redisait les sorties mot pour mot.
        assert "ev-ctx" not in js and "ev-centre" not in js
        css = _sans_commentaires_css(_lire(CSS))
        assert "display: grid; grid-template-columns" not in _regle(css, ".ev-corps {")

    def test_une_seule_ombre_pour_la_bande_les_languettes_et_la_feuille(self):
        """Trois cartes empilées, c'étaient trois contours pour un seul
        sujet. Le classeur est UN objet : un rayon, une ombre, un rognage."""
        css = _sans_commentaires_css(_lire(CSS))
        cl = _regle(css, "\n.cl {")
        assert "border-radius" in cl and "box-shadow" in cl and "overflow: hidden" in cl
        for enfant in ("\n.cl-bande {", "\n.ev-corps .feuille {"):
            assert "box-shadow" not in _regle(css, enfant), enfant

    def test_les_languettes_remplissent_la_bande(self):
        """⚠️ Relevé SUR CAPTURE : à deux sorties, un plafond de 420 px
        laissait un grand vide bleu à droite de la bande."""
        css = _sans_commentaires_css(_lire(CSS))
        os_ = _regle(css, "\n.os {")
        assert "flex: 1 1 0" in os_
        assert "max-width" not in os_
        assert "min-width: 212px" in os_, "sous cette largeur, elles défilent"
        assert "overflow-x: auto" in _regle(css, "\n.cl-ong {")


class TestLesLanguettesPortentLaComparaison:

    def test_chacune_porte_sa_jauge_et_le_trait_de_l_attendu(self):
        """C'est ce qui manquait : un onglet portait un chiffre et rien
        d'autre. Quatre pas et le trait de l'attendu — la convention de toute
        l'application."""
        js = _lire(JS)
        m = _corps(js, "  function majLanguette(b, r, st, req) {")
        assert "for (let lv = 1; lv <= 4; lv++)" in m
        assert "if (req !== null && lv === req + 1) j += '<i></i>';" in m
        assert "<s class=\"${!estNul(off) && off >= lv ? 'f' : ''}\">" in m

    def test_une_sortie_que_personne_n_a_notee_se_voit(self):
        """Elle retient le niveau de l'activité (le MINIMUM) : l'écran ne doit
        pas la confondre avec un zéro."""
        js = _lire(JS)
        m = _corps(js, "  function majLanguette(b, r, st, req) {")
        assert "b.classList.toggle('est-a', estNul(off));" in m
        assert "'j' + (estNul(off) ? ' rien' : '')" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "repeating-linear-gradient" in _regle(css, "\n.os .j.rien {")

    def test_la_feuille_ne_porte_qu_UNE_sortie(self):
        js = _lire(JS)
        m = _corps(js, "  function montrerSortie(st, dataId) {")
        assert "f.innerHTML = '';" in m and "f.appendChild(feuilleSortie(r, st));" in m

    def test_la_sortie_ouverte_survit_au_re_rendu(self):
        """Sinon toute note posée ramènerait à la première sortie."""
        js = _lire(JS)
        s = _corps(js, "  function sortieOuverte(st) {")
        assert "String(r.data_id) === String(state.sortie)" in s
        assert "|| liste[0] || null" in s


class TestUneSeulePiste:

    def test_cinq_crans_et_pas_deux_echelles(self):
        js = _lire(JS)
        assert "function blocNote(" not in js, "les deux blocs sont remplacés"
        n = _corps(js, "  function notaSortie(r, st) {")
        assert n.count("piste(") == 1
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        assert "for (let i = 0; i <= 4; i++)" in p

    def test_le_zero_ne_se_remplit_JAMAIS(self):
        """« Non démontré », c'est une jauge VIDE. Posé, il porte un anneau —
        sinon rien ne distinguerait « 0 » de « rien »."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        assert "if (!estNul(pose) && i >= 1 && i <= pose)" in p
        assert "if (pose === 0 && i === 0) c += ' zero';" in p
        css = _sans_commentaires_css(_lire(CSS))
        assert "inset 0 0 0 2px" in _regle(css, "\n.cran.zero {")
        # …et la mise à jour sur place tient la même règle
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "if (!estNul(off) && i >= 1 && i <= off)" in m

    def test_la_zone_attendue_est_une_SURFACE_et_n_existe_pas_sans_requis(self):
        """« La barre doit entrer dans le vert » se regarde ; un filet de 2 px
        se cherche. Et NULL ≠ 0 : sans requis, pas de zone."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        assert "if (attendu !== null) h += `<span class=\"zone\"" in p
        css = _sans_commentaires_css(_lire(CSS))
        z = _regle(css, "\n.crans .zone {")
        assert "background: var(--v1)" in z and "border: 1px solid var(--v3)" in z

    def test_la_gomme_vit_HORS_des_crans(self):
        """Effacer n'est pas un niveau de plus, et la zone attendue ne doit
        pas l'englober — elle aurait l'air d'un sixième cran."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        i = p.index("</div><button type=\"button\" class=\"gomme\"")
        assert p.index("class=\"zone\"") < i, "la zone vit dans .crans, la gomme non"

    def test_l_auto_evaluation_est_un_repere_sur_la_MEME_piste(self):
        """Un contour posé par-dessus la barre disparaissait dès qu'elle le
        dépassait — et c'est justement ce cas qu'on vient lire."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        assert 'class="soi${estNul(soi) ? \' est-off\' : \'\'}"' in p
        css = _sans_commentaires_css(_lire(CSS))
        s = _regle(css, "\n.crans .soi {")
        assert "repeating-linear-gradient" in s and "z-index: 2" in s

    def test_le_repere_ne_VOLE_PAS_le_clic_du_cran_qu_il_designe(self):
        """⚠️ Relevé au banc : posé par-dessus les crans, il tombe pile au
        milieu de l'un d'eux et INTERCEPTE son clic — le cran sous le repère ne
        se posait plus. Même règle que la bulle de la matrice RH : ce qui
        explique ne vole jamais le clic de ce qu'il explique."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "pointer-events: none" in _regle(css, "\n.crans .soi {")

    def test_un_cran_ne_porte_que_son_chiffre_et_son_nom_au_survol(self):
        """⚠️ Pas d'attribut `title` : l'info-bulle du système sortirait
        par-dessus la nôtre, une seconde plus tard et sans sa couleur."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        assert "data-nom=\"${esc(levelName(i))}\"" in p
        assert "title=" not in p
        css = _sans_commentaires_css(_lire(CSS))
        assert "content: attr(data-nom)" in _regle(css, "\n.cran::after {")
        assert "transition-delay: .5s" in _regle(css, "\n.cran:hover::after {")

    def test_une_sortie_mesuree_se_lit_et_ne_se_clique_pas(self):
        js = _lire(JS)
        assert "const jePosePour = r => (jeSuisLeDev() ? !r.mesurable : true);" in js
        n = _corps(js, "  function notaSortie(r, st) {")
        assert "piste(off, req, soi, !mien)" in n
        css = _sans_commentaires_css(_lire(CSS))
        assert "pointer-events: none" in _regle(css, "\n.piste.lue .cran {")
        assert "display: none" in _regle(css, "\n.piste.lue .gomme {")

    def test_la_note_a_UNE_source_et_la_piste_se_met_a_jour_sur_place(self):
        """⚠️ Réécrire la piste ferait perdre le focus du cran qu'on vient de
        cliquer, et couperait la transition de la marche qui se remplit."""
        js = _lire(JS)
        p = _corps(js, "  function poserNote(r, niveau, st) {")
        assert "state.saisie[r.data_id] = Object.assign({}, avant, { niveau: niveau });" in p
        assert "majNota(z, r, st)" in p and "majLanguette(b, r, st," in p
        assert "innerHTML" not in p, "on bascule des classes, on ne réécrit pas"

    def test_l_enregistrement_lit_l_etat_et_pas_le_DOM(self):
        js = _lire(JS)
        s = js.split("  async function saveEvaluation() {", 1)[1][:400]
        assert "Object.keys(state.saisie" in s
        assert "querySelectorAll" not in s


class TestLesCourbesQuittentLaPage:

    def test_aucune_courbe_dans_la_feuille(self):
        js = _lire(JS)
        f = _corps(js, "  function feuilleSortie(r, st) {")
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
        assert "if (!crb.histo) {" in c
        ouvrir = js.split("async function ouvrirEvaluation(", 1)[1][:900]
        assert "/paliers/historique/" not in ouvrir and "/mastery/historique" not in ouvrir

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
        b = _corps(js, "  function bandeClasseur(st) {")
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
        b = _corps(js, "  function bandeClasseur(st) {")
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
        b = _corps(js, "  function bandeClasseur(st) {")
        assert "prochaineEcheance(st)" in b
        assert "chip('amb', 'fa-calendar-days', T('cl_seance')" in b


class TestLeRailDesActivites:

    def test_c_est_une_ligne_de_pastilles_pas_une_colonne(self):
        """218 px pris à la largeur de ce qu'on vient lire, pour une liste
        qu'on parcourt une fois."""
        js = _lire(JS)
        r = _corps(js, "  function remplirActivites() {")
        assert "el.className = 'rh'" in r
        css = _sans_commentaires_css(_lire(CSS))
        rail = _regle(css, "\n.ev-rail {")
        assert "display: flex" in rail
        # ⚠️ Vingt activités ne tiennent pas sur une ligne : la liste défile
        # DANS le rail, et la page ne défile jamais à l'horizontale.
        assert "overflow-x: auto" in _regle(css, "\n.ev-rail-l {")

    def test_une_activite_pas_encore_configuree_se_distingue(self):
        js = _lire(JS)
        r = _corps(js, "  function remplirActivites() {")
        assert "cat === 'setup' ? ' c'" in r
        assert "niv === null ? ' x'" in r

    def test_le_bandeau_de_situation_filtre_toujours(self):
        js = _lire(JS)
        f = _corps(js, "  function rendreFiltres() {")
        assert "$('#ev-rail-f')" in f
        assert "state.filtre = state.filtre === b.dataset.f ? null : b.dataset.f;" in f


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
        cles = ["cl_tenu", "cl_min_1", "cl_min_n", "cl_reste_1", "cl_reste_n",
                "cl_courbes", "cl_seance", "cl_mes", "cl_main", "cl_rien",
                "cl_tech_0", "cl_tech_1", "cl_tech_n",
                "cl_tech_ecart_1", "cl_tech_ecart_n",
                "grv_mesure", "nota_foi", "nota_mes", "nota_vous",
                "nota_vous_auto", "nota_rien", "nota_att", "nota_cette",
                "nota_zero", "nota_mes_ok", "nota_mes_ko", "pr_k", "pr_vide",
                "crb_titre", "crb_niveaux", "crb_niveaux_d", "crb_valeurs",
                "crb_valeurs_d", "crb_sans_mes", "crb_choisir",
                "h_titre", "h_vide", "h_glob", "h_glob_d", "h_sous", "h_au",
                "h_sans_glob", "h_jamais", "h_une_note", "h_une_note_d"]
        for k in cles:
            assert (k + ":") in fr, "FR " + k
            assert (k + ":") in en, "EN " + k

    def test_le_pluriel_du_classeur_ne_se_devine_pas(self):
        """« 1 reste à noter » et « 2 restent à noter » ne s'accordent pas de
        la même façon : `nf()` essaie la forme qui EXISTE."""
        js = _lire(JS)
        for c in ("cl_min", "cl_reste", "cl_tech", "cl_tech_ecart"):
            assert ("%s_1:" % c) in js and ("%s_n:" % c) in js, c

    def test_la_fenetre_porte_son_titre_traduit(self):
        html = _lire(GABARIT)
        bloc = html.split('id="cv2-crb-win"', 1)[1].split("</aside>", 1)[0]
        assert 'data-i18n="crb_titre"' in bloc
