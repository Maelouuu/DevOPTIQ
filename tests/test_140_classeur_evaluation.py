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

    def test_la_page_est_une_colonne_classeur_pied(self):
        js = _lire(JS)
        sk = js.split('<div class="ev-corps">', 1)[1].split("</div>`;", 1)[0]
        # ⚠️ Le RAIL des activités est parti : une ligne de pastilles au-dessus
        # du classeur, pour une liste qu'on parcourt une fois. On change
        # d'activité avec les flèches de la bande, là où on lit son nom.
        assert 'id="ev-rail"' not in sk
        for part in ('class="cl" id="ev-cl"', 'class="cl-bande"',
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
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        assert "if (!estNul(pose) && i <= pose) c += ' f'" in p
        assert "i >= 1" not in p, "le 0 est un cran comme les autres"
        assert "' zero'" not in p
        css = _sans_commentaires_css(_lire(CSS))
        assert ".cran.zero" not in css, "l'anneau n'a plus d'objet"
        # …et la mise à jour sur place tient la même règle
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "if (!estNul(off) && i <= off) {" in m

    def test_la_pastille_dit_QUEL_niveau_on_vient_de_poser(self):
        """Un cran rempli ne dit pas lequel on a choisi : la pastille le pose
        sur SON cran, avec son bec, au lieu d'obliger à lire le mot à l'autre
        bout de la ligne."""
        js = _lire(JS)
        p = _corps(js, "  function piste(pose, attendu, soi, lue) {")
        assert "const pic = (!estNul(pose) && i === pose)" in p
        assert 'class="pic">${esc(levelName(i))}' in p
        # ⚠️ Elle SE DÉPLACE : deux pastilles diraient deux niveaux.
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "if (p && i !== off) p.remove();" in m
        css = _sans_commentaires_css(_lire(CSS))
        pic = _regle(css, "\n.cran .pic {")
        assert "pointer-events: none" in pic, \
            "ce qui explique ne vole jamais le clic de ce qu'il explique"
        assert "border-top-color" in _regle(css, "\n.cran .pic::after {"), "le bec"

    def test_l_auto_evaluation_passe_SOUS_la_piste(self):
        """Le dessus est pris par la pastille du niveau choisi, et les deux
        tombent sur le même cran dès qu'on se situe là où l'on est noté."""
        css = _sans_commentaires_css(_lire(CSS))
        av = _regle(css, "\n.crans .soi::after {")
        bf = _regle(css, "\n.crans .soi::before {")
        assert "bottom: -5px" in av and "top: -5px" not in av
        assert "top: calc(100% +" in bf
        # de la place des DEUX côtés, sinon la pastille mord sur l'en-tête
        assert "margin: 42px 0 26px" in _regle(css, "\n.piste {")
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
        b = _corps(js, "  function bandeClasseur(st) {")
        assert "nf('cl_min'" not in b
        assert "cl_reste" in b, "ce qui reste à noter est la seule chose actionnable"
        assert "levelName(niv)" not in b

    def test_le_verdict_ne_redit_plus_la_piste_verte(self):
        """⚠️ `nota_mes_ko` reste : il dit ce qui FERA monter le niveau. C'est
        le _ok qui était du bruit — la piste est verte et la pastille dit
        « qualifié »."""
        js = _lire(JS)
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "nota_mes_ok" not in m
        assert "nota_mes_ko" in m

    def test_le_filtre_part_avec_le_rail_qu_il_filtrait(self):
        """Un filtre qui n'a plus de liste à filtrer ne filtre rien. ⚠️ Celui
        de la VUE D'ENSEMBLE (`renderBilan`) est un AUTRE écran : il garde ses
        quatre tuiles, et elles s'y affichent même à zéro."""
        js = _lire(JS)
        assert "function rendreFiltres" not in js
        assert "ev-f--" not in js, "les tuiles du rail sont parties avec lui"
        b = _corps(js, "  function renderBilan(box, compte, onFiltre) {")
        for c in ("'held'", "'gap'", "'todo'", "'setup'"):
            assert c in b, c


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
        b = _corps(js, "  function bandeClasseur(st) {")
        # la nav vient APRÈS le niveau tenu dans le DOM : c'est le même bord
        assert b.index('class="cl-niv"') < b.index('id="ev-nav"')
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
                  ".cl.est-sort-d", "prefers-reduced-motion"):
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
        cles = ["cl_tenu", "cl_reste_1", "cl_reste_n",
                "cl_courbes", "cl_seance", "cl_mes", "cl_main", "cl_rien",
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

    def test_le_pluriel_du_classeur_ne_se_devine_pas(self):
        """« 1 reste à noter » et « 2 restent à noter » ne s'accordent pas de
        la même façon : `nf()` essaie la forme qui EXISTE."""
        js = _lire(JS)
        for c in ("cl_reste", "cl_tech", "cl_tech_ecart"):
            assert ("%s_1:" % c) in js and ("%s_n:" % c) in js, c

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
        assert 'class="nota-vd" data-vd' in n
        m = _corps(js, "  function majNota(z, r, st) {")
        assert "z.querySelector('[data-vd]').innerHTML = vd;" in m
        assert "accordBadge(" in m

    def test_l_echelle_se_range_au_bout_de_SA_piste(self):
        """L'explication des cinq paliers vivait dans l'en-tête parti : elle
        se range où elle sert."""
        js = _lire(JS)
        n = _corps(js, "  function notaSortie(r, st) {")
        assert "z.querySelector('.piste').appendChild(boutonInfo(T('pal_echelle_t')" in n

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
