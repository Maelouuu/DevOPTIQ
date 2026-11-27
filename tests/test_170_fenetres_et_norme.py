# -*- coding: utf-8 -*-
"""TROIS SUJETS, un seul fichier : ils tiennent par le même fil — ce que
l'écran d'évaluation DEMANDE, et ce qu'il DEVINE.

- **La fenêtre TECHNICITÉ** devient une TABLE. Ses trois lignes ne s'alignaient
  pas : le nom du domaine était en `flex: 1 1 150px`, donc chaque ligne
  poussait ses deux échelles où elle pouvait — mesuré, le « Requis » partait à
  x = 472 / 513 / 569, **97 px d'écart**. On ne pouvait pas comparer deux
  domaines, ce qui est tout l'objet d'une liste.

- **La fenêtre PLAN** garde sa structure (le besoin à gauche, la capacité à
  droite, un verdict en direct) et change de DENSITÉ : 14 textes sous le
  plancher de 11 px réels, dont les trois étiquettes d'une action à 9,2. Et son
  MOTEUR voit enfin les paliers, les séances et la technicité — trois
  mécanismes arrivés après lui, qu'il ignorait tous les trois.

- **LA NORME** ne se devine plus. Elle est stockée et fait foi
  (`Data.norme_valeur/unite/sens`) ; ce qui ratait, c'est le pré-remplissage :
  il lisait un champ presque toujours vide, et prenait le PREMIER nombre de la
  phrase. Elle se règle désormais là où la phrase s'écrit.
"""
import io
import json
import os
import re

import pytest

pytestmark = pytest.mark.mastery

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS = os.path.join(RACINE, "static", "competences.css")
MDP = "TestPass123!"


def _lire(p):
    return io.open(p, encoding="utf-8").read()


# ⚠️ Comme `test_148` : tout ce qui lit l'ÉCRAN refondu saute là où il n'est
# pas (le pilote ARaymond tourne encore sur l'écran d'avant). La garde est un
# PRÉDICAT SUR LE FICHIER, jamais un drapeau de branche : elle s'éteint d'elle
# même le jour où l'écran arrive, et il n'y a rien à défaire.
ECRAN_REFONDU = "cv2-ecran-eval" in _lire(JS)
SAUT_ECRAN = pytest.mark.skipif(
    not ECRAN_REFONDU, reason="l'écran d'évaluation refondu n'est pas dans cet arbre")


def _sans_commentaires_css(css):
    """⚠️ Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES : il
    s'attrape sinon sur l'explication de la règle qu'il garde — neuf fois dans
    ce dépôt."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _regle(css, selecteur):
    """Le corps d'UNE règle, BORNÉE : un fichier de 4 500 lignes contient
    presque toujours un homonyme de ce qu'on croit garder."""
    return css.split(selecteur, 1)[1].split("}", 1)[0]


def _corps(js, entete):
    return js.split(entete, 1)[1].split("\n  }", 1)[0]


# ══════════════════════════════════════════════════════════════════════
#  1 · LA TECHNICITÉ — une table, et le teal
# ══════════════════════════════════════════════════════════════════════
@SAUT_ECRAN
class TestLaTableSAligne:

    def test_les_etiquettes_sont_ecrites_UNE_fois_en_en_tete(self):
        """⚠️ Elles l'étaient SIX fois — « Requis » et « Démontré » à chaque
        ligne, en 8,4 px réels — et c'est ce qui volait la place des crans."""
        l = _corps(_lire(JS), "  function renderDomList(list, aid, domains) {")
        tete = l.split("insertAdjacentHTML", 1)[1].split(");", 1)[0]
        assert "T('tech_dom')" in tete
        assert "T('tech_requis_role')" in tete and "T('tech_demonstrated')" in tete
        # et plus dans le corps de la boucle
        boucle = l.split("domains.forEach", 1)[1]
        # La clé reste passée aux crans (pour leur `aria-label`), mais le
        # LIBELLÉ ne se réécrit plus par ligne.
        assert "domPas('tech_requis_role'" in boucle
        assert 'class="hd"' not in boucle, "l'en-tête n'est pas répété par ligne"

    def test_c_est_une_GRILLE_a_quatre_colonnes(self):
        """C'est leur alignement qui permet de comparer deux domaines."""
        css = _sans_commentaires_css(_lire(CSS))
        r = _regle(css, "\n.tch-tab {")
        assert "display: grid" in r
        m = re.search(r"grid-template-columns:\s*([^;]+);", r)
        assert m, r
        # ⚠️ On ne découpe PAS à l'espace : `minmax(130px, 1fr)` en porte une,
        # et le cliquet comptait cinq colonnes pour quatre.
        cols = re.sub(r"\(([^)]*)\)", lambda x: "(" + x.group(1).replace(" ", "") + ")",
                      m.group(1)).split()
        assert len(cols) == 4, cols
        # ⚠️ C'est le NOM qui cède : deux échelles de cinq crans ont une
        # largeur fixe, et les rogner les désaligne.
        assert cols[0].startswith("minmax(") and cols[1:] == ["auto", "auto", "auto"]

    def test_la_fenetre_s_elargit_pour_la_table_et_pour_elle_seule(self):
        """Mesuré : la table fait 818 px au plus serré — deux échelles de cinq
        crans alignées ne tiennent pas dans les 720 px du tiroir."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "min(900px, 96vw)" in _regle(css, '\n.cv2-drawer[data-vue="tech"] {')
        js = _lire(JS)
        o = _corps(js, "  function ouvrirTechnicite() {")
        assert "dataset.vue = 'tech'" in o
        # ⚠️ Et `ouvrirDialogue` repose `eval` à chaque ouverture : la largeur
        # ne déborde donc pas sur les deux autres dialogues (configurer,
        # diagnostiquer), qui passent par la même fenêtre.
        d = _corps(js, "  function ouvrirDialogue(titre, avecLaPersonne) {")
        assert "d.dataset.vue = 'eval';" in d

    def test_les_crans_passent_au_dessus_du_plancher(self):
        """⚠️ 20,8 × 16 px RÉELS, chiffre de 8,8 — sous le plancher de 11 de
        l'échelle typographique, à côté d'un cran de notation de 76 px."""
        css = _sans_commentaires_css(_lire(CSS))
        r = _regle(css, "\n.tch-pas button {")
        assert "width: 34px" in r and "height: 28px" in r
        m = re.search(r"font-size:\s*([\d.]+)px", r)
        assert m and float(m.group(1)) >= 13.75, m and m.group(1)
        assert "var(--pg-font-display)" in r, "les chiffres, en Fraunces"

    def test_le_TEAL_est_un_jeton_et_la_fenetre_n_emprunte_plus(self):
        """⚠️ Elle prenait le BLEU de la note qui fait foi et le TILLEUL de ce
        qui est tenu, alors que la technicité est un AXE À PART. Le teal avait
        été écarté le 15/09 « parce qu'il se lit comme du vert » — c'était vrai
        contre le vert FRANC d'alors ; ce qui est tenu est tilleul depuis le
        23/11, et les deux teintes ne se touchent plus."""
        css = _sans_commentaires_css(_lire(CSS))
        for jeton in ("--cv-t-05:", "--cv-t-20:", "--cv-t-50:", "--cv-t-70:"):
            assert jeton in css, jeton
        # les crans ne lisent plus le bleu de la note ni le tilleul du tenu
        for sel in ("\n.tch-pas button.on {", "\n.tch-pas.cible button.on {"):
            r = _regle(css, sel)
            assert "--cv-t-" in r, sel
            assert "--b6" not in r and "--cv-g-" not in r, sel
        # ⚠️ Les VERDICTS gardent prune / tilleul : « en écart » et « tenu »
        # veulent dire la même chose partout, et ce n'est pas un axe.
        assert "var(--cv-r-60)" in _regle(css, "\n.tch-v.ko {")
        assert "var(--cv-g-70)" in _regle(css, "\n.tch-v.ok {")

    def test_un_domaine_NON_SITUE_a_son_verdict(self):
        """⚠️ Sans lui la colonne s'effondre une ligne sur trois — et NULL
        (« pas encore regardé ») n'est pas 0 (« aucun »), encore moins
        « au niveau »."""
        l = _corps(_lire(JS), "  function renderDomList(list, aid, domains) {")
        assert "estNul(d.gap)" in l and "T('tech_nonsitue')" in l
        assert "'tch-v nul'" in l
        css = _sans_commentaires_css(_lire(CSS))
        assert "var(--faint)" in _regle(css, "\n.tch-v.nul {")

    def test_les_libelles_neufs_sont_dans_les_DEUX_langues(self):
        """⚠️ On lit les DICTIONNAIRES : une clé absente de l'anglais retombe
        SILENCIEUSEMENT sur le français — un contrôle qui passerait par `t()`
        ne verrait rien."""
        js = _lire(JS)
        commun = js.split("  const COMMUN = {", 1)[1].split("\n  };", 1)[0]
        for k in ("tech_dom", "tech_nonsitue", "tech_ajouter"):
            d = commun.split(k + ":", 1)
            assert len(d) == 2, "clé absente de COMMUN : " + k
            # ⚠️ BORNÉ À SON ENTRÉE : une fenêtre de 400 signes avalait les
            # clés SUIVANTES, qui portent `en:` — le cliquet restait VERT en
            # retirant l'anglais de celle qu'il garde.
            entree = d[1].split("},", 1)[0]
            assert "fr:" in entree and "en:" in entree, k
        for bloc, mot in ((js.split("    fr: {", 1)[1].split("\n    },", 1)[0], "domaine"),
                          (js.split("    en: {", 1)[1].split("\n    },", 1)[0], "domain")):
            for k in ("tech_cat_1", "tech_cat_n"):
                assert k + ":" in bloc, k
            assert mot in bloc.split("tech_cat_1:", 1)[1][:80]


# ══════════════════════════════════════════════════════════════════════
#  2 · LE PLAN — la densité, et ce qu'il voit
# ══════════════════════════════════════════════════════════════════════
@SAUT_ECRAN
class TestLePlanChangeDeDensite:
    """⚠️ RÉÉCRIT (27/11) : le bandeau n'est plus l'en-tête d'une fenêtre, et
    l'échéancier en peigne a cédé la place à la frise. Ce qui reste vrai, et
    qui est la raison de ces deux cas : UN seul nuit sur la page, et le temps
    se lit en SEMAINES nommées, pas sous un peigne muet."""

    def test_le_bandeau_prend_le_NUIT_des_deux_autres_surfaces(self):
        """⚠️ Trois dégradés sombres différents sur une même page (nuit, bleu,
        violet) se lisent comme un défaut d'impression."""
        css = _sans_commentaires_css(_lire(CSS))
        r = _regle(css, "\n.pl-nuit {")
        assert "var(--nuit-1)" in r and "var(--nuit-2)" in r
        assert "#4c1d95" not in r, "le violet est parti"
        assert ".cv2-ph {" not in css, "l'en-tête de la fenêtre aussi"

    def test_le_temps_porte_ses_SEMAINES(self):
        """⚠️ Le peigne portait une LÉGENDE centrée (« Répartition semaine par
        semaine ») sous 31 barres muettes : on voyait où ça déborde sans
        savoir à quelle semaine. La frise porte un AXE, et ce qui dépasse la
        durée visée y est marqué."""
        js = _lire(JS)
        assert "cv2-echlbl" not in js and "plan_sched" not in js
        assert "function renderSemaines" not in js, "le peigne est parti"
        r = _corps(js, "  function renderFrise(c) {")
        assert 'class="pl-fr-ax"' in r and "T('plan_wk')" in r
        # ⚠️ L'axe est posé sur les semaines RÉELLEMENT couvertes, pas sur la
        # seule durée visée : il décalerait dès que le besoin déborde.
        assert "semMax = Math.max(1, Math.ceil(ech / c.hs))" in r
        assert "w > c.sem ? 'de' : ''" in r, "ce qui dépasse se marque"


class TestLePlanVoitCeQuiEstDejaPlanifie:
    """⚠️⚠️ Le module a été écrit avant trois mécanismes de l'application —
    relevé en cherchant « palier », « domain » et « séance » dans son code :
    ZÉRO occurrence des trois."""

    def test_un_RESULTAT_porte_ses_chiffres(self, client, app, scene):
        """Sans la norme, la mesure et la marche posée, une action ne peut
        parler que d'une progression abstraite — et c'est ce qu'elle faisait."""
        _en_ecart(client, app, scene)
        d = client.get("/plan/%s/%s" % (scene["collab"], scene["role"])).get_json()
        r = d["activites"][0]["results_in_gap"][0]
        for champ in ("mesurable", "norme", "mesure", "palier", "manque"):
            assert champ in r, champ

    def test_une_sortie_MESUREE_fait_parler_l_action_en_CHIFFRES(self):
        """« Amener « Rapport d'essais » à 48 h » se fait ; « tenir
        l'activité en situation réelle » se devine."""
        from Code.routes.plan_formation import _plan_local
        actions = _plan_local([_ecart_mesure()], "fr")
        t = [a for a in actions if a["type"] == "TERRAIN"]
        assert len(t) == 1
        # ⚠️ La MARCHE POSÉE d'abord : c'est l'engagement en cours, et c'est
        # elle qu'on vise maintenant. La norme est la cible finale — elle vit
        # dans l'objectif, avec ce qui a été relevé.
        assert "55 h" in t[0]["titre"], t[0]["titre"]
        assert "70 h" in t[0]["objectif"], t[0]["objectif"]
        assert "48 h" in t[0]["objectif"] and "au plus" in t[0]["objectif"]
        assert "15/12/2026" in t[0]["objectif"], "l'échéance de la marche posée"

    def test_en_anglais_les_memes_chiffres_sans_guillemets_francais(self):
        from Code.routes.plan_formation import _plan_local
        t = [a for a in _plan_local([_ecart_mesure()], "en") if a["type"] == "TERRAIN"][0]
        for champ in ("titre", "objectif", "livrable", "critere"):
            assert "«" not in t[champ] and "»" not in t[champ], (champ, t[champ])
        assert "55 h" in t["titre"] and "at most" in t["objectif"]
        assert "48 h" in t["objectif"] and "2026-12-15" in t["objectif"]

    def test_un_DOMAINE_technique_en_ecart_produit_une_action(self):
        """⚠️ Il n'en produisait AUCUNE : un domaine à −2 ne pesait nulle part
        dans le plan."""
        from Code.routes.plan_formation import _plan_local
        a = _ecart_mesure()
        a["domaines"] = [{"domain_id": 3, "name": "Usinage CN", "gap": -2,
                          "demonstrated_label": "Notions", "required_label": "Maîtrise"}]
        actions = _plan_local([a], "fr")
        dom = [x for x in actions if "Usinage CN" in x["titre"]]
        assert len(dom) == 1
        # ⚠️ FORMATION et non TERRAIN : un domaine technique s'apprend — c'est
        # le terrain sur lequel l'activité se joue, pas l'activité elle-même.
        assert dom[0]["type"] == "FORMATION"
        assert dom[0]["heures"] > 0
        assert "Notions" in dom[0]["objectif"] and "Maîtrise" in dom[0]["objectif"]

    def test_le_repli_ne_DEGENERE_plus(self):
        """⚠️ Mesuré au banc : trois activités en écart rendaient TROIS
        actions, une par activité, toutes « Tenir « X » en situation réelle ».
        Tout le reste dépendait de `result_capability_links`, que seul le
        diagnostic remplit."""
        from Code.routes.plan_formation import _plan_local
        a = _ecart_mesure()
        a["capabilities"] = []
        a["results_in_gap"].append({
            "data_id": 92, "name": "Procès-verbal", "demonstrated_level": 1,
            "demonstrated_label": "En acquisition", "minimum_performance_text": "Signé.",
            "mesurable": False, "norme": None, "mesure": None, "palier": None, "manque": 2})
        actions = _plan_local([a], "fr")
        assert len(actions) == 2, [x["titre"] for x in actions]
        assert len({x["titre"] for x in actions}) == 2, "deux actions distinctes"

    def test_la_porte_d_entree_n_a_PAS_ete_elargie(self, client, app, scene):
        """⚠️⚠️ Une activité entre dans le plan parce que `categorie_activite`
        la dit « gap » — sur sa MAÎTRISE, et rien d'autre. Un écart purement
        TECHNIQUE n'ouvre pas le plan : élargir la porte ferait diverger
        l'écran et le plan sur le mot « écart », ce qui a déjà été corrigé une
        fois (15/09). La technicité ENRICHIT ; elle ne fait pas entrer."""
        import inspect

        from Code.routes import plan_formation as pf
        src = inspect.getsource(pf.contexte_ecart)
        assert 'categorie_activite(row) != "gap"' in src
        # de bout en bout : au niveau requis, rien à combler même avec un
        # domaine en écart
        _au_niveau(client, app, scene)
        d = client.get("/plan/%s/%s" % (scene["collab"], scene["role"])).get_json()
        assert d["activites"] == []

    def test_la_SEANCE_voyage_avec_le_plan(self, client, app, scene):
        """On réglait une durée visée de douze semaines à côté d'un rendez-vous
        déjà pris pour dans trois."""
        from datetime import date, timedelta

        from Code.extensions import db
        from Code.models.models import SessionEvaluation
        _en_ecart(client, app, scene)
        with app.app_context():
            db.session.add(SessionEvaluation(
                user_id=scene["collab"], role_id=scene["role"],
                developpeur_user_id=scene["dev"],
                date_prevue=date.today() + timedelta(days=21), statut="prevue"))
            db.session.commit()
        try:
            d = client.get("/plan/%s/%s" % (scene["collab"], scene["role"])).get_json()
            assert d["seance"] and d["seance"]["jours"] == 21
            assert d["seance"]["semaines"] == 3
            r = client.post("/plan/proposer", data=json.dumps(
                {"user_id": scene["collab"], "role_id": scene["role"]}),
                content_type="application/json").get_json()
            assert r["seance"], "la proposition la porte aussi"
        finally:
            with app.app_context():
                SessionEvaluation.query.filter_by(user_id=scene["collab"]).delete()
                db.session.commit()

    def test_une_seance_reservee_a_un_AUTRE_role_ne_concerne_pas_ce_plan(
            self, client, app, scene):
        """Une séance sans rôle, si — elle peut tout couvrir."""
        from datetime import date, timedelta

        from Code.extensions import db
        from Code.models.models import Role, SessionEvaluation
        _en_ecart(client, app, scene)
        with app.app_context():
            autre = Role(name="Rôle ailleurs 170", entity_id=scene["entity"])
            db.session.add(autre)
            db.session.commit()
            db.session.add(SessionEvaluation(
                user_id=scene["collab"], role_id=autre.id,
                date_prevue=date.today() + timedelta(days=4), statut="prevue"))
            db.session.commit()
            aid = autre.id
        try:
            d = client.get("/plan/%s/%s" % (scene["collab"], scene["role"])).get_json()
            assert d["seance"] is None, d["seance"]
        finally:
            with app.app_context():
                SessionEvaluation.query.filter_by(user_id=scene["collab"]).delete()
                Role.query.filter_by(id=aid).delete()
                db.session.commit()

    def test_les_domaines_sont_lus_par_la_MEME_fonction_que_la_fenetre(self):
        """⚠️ Deux lectures d'un même écart finiraient par donner deux
        verdicts. La route de la fenêtre Technicité délègue, elle aussi."""
        import inspect

        from Code.routes import plan_formation as pf
        from Code.routes import technical_domains as td
        assert hasattr(td, "domaines_de_activite")
        assert "domaines_de_activite" in inspect.getsource(pf._domaines_en_ecart)
        assert "domaines_de_activite(" in inspect.getsource(td.activity_domains)

    def test_l_IA_recoit_les_chiffres_les_domaines_et_la_seance(self):
        """Sans eux, elle ne pouvait proposer qu'une progression abstraite —
        elle ne savait pas qu'une sortie pouvait être mesurée."""
        import inspect

        from Code.routes import plan_formation as pf
        src = inspect.getsource(pf._plan_ia)
        assert '"prochaine_seance"' in src
        assert '"domaines_techniques_en_ecart"' in src
        assert "_resultat_ia(r)" in src
        bloc = pf._resultat_ia(_ecart_mesure()["results_in_gap"][0])
        assert bloc["mesure"]["norme"] == 48
        assert bloc["mesure"]["palier_en_cours"] == 55
        assert bloc["mesure"]["sens"] == "au plus"

    def test_le_prompt_du_plan_apprend_les_trois(self):
        """⚠️ Un prompt vit dans le CATALOGUE, jamais en dur dans une route :
        l'image client le sert chiffré."""
        from Code.prompts.catalog import PROMPTS
        p = PROMPTS["plan_formation.system"]
        assert "'mesure'" in p and "domaines_techniques_en_ecart" in p
        assert "prochaine_seance" in p


# ══════════════════════════════════════════════════════════════════════
#  3 · LA NORME — on ne devine plus QUEL nombre
# ══════════════════════════════════════════════════════════════════════
class TestOnNeDevinePlusQuelNombre:
    """⚠️ Mesuré sur un corpus de 28 indicateurs plausibles : 22 lus juste,
    **6 faux — et les six avaient une seule cause**, « prendre le premier
    nombre de la phrase ». Mesuré après : 27/28, et aucune lecture fausse."""

    @pytest.mark.parametrize("texte,attendu", [
        # un numéro d'étiquette en tête
        ("Indicateur 1 — délai sous 5 jours", (5.0, "j", "moins")),
        # une année
        ("Objectif 2026 — taux de conformité 95 %", (95.0, "%", "plus")),
        # un « n°2 »
        ("KPI n°2 : moins de 48 h", (48.0, "h", "moins")),
        # la borne BASSE d'un intervalle
        ("Délai entre 2 et 5 jours", (5.0, "j", "moins")),
        ("Entre 90 et 95 % de conformité", (95.0, "%", "plus")),
    ])
    def test_le_nombre_PORTE_par_une_unite_l_emporte(self, texte, attendu):
        from Code.paliers import norme_depuis_indicateur
        n = norme_depuis_indicateur(texte)
        assert n is not None, texte
        assert (n["valeur"], n["unite"], n["sens"]) == attendu, (texte, n)

    def test_le_DERNIER_porte_et_non_le_premier(self):
        """Un numéro d'étiquette est en tête, la valeur en fin."""
        from Code.paliers import norme_depuis_indicateur
        n = norme_depuis_indicateur("3 h de préparation, livré en 48 h")
        assert n["valeur"] == 48.0

    @pytest.mark.parametrize("texte", [
        "Volume 1 500 pièces par mois",          # deux nombres, aucun porté
        "Réunion du 15/09/2026 validée",         # trois nombres, aucun porté
    ])
    def test_plusieurs_nombres_sans_unite_ne_proposent_RIEN(self, texte):
        """⚠️ Mieux vaut un champ vide qu'un chiffre faux : c'est lui qui
        décidera du niveau de quelqu'un."""
        from Code.paliers import norme_depuis_indicateur
        assert norme_depuis_indicateur(texte) is None, texte

    def test_un_nombre_SEUL_se_lit_meme_sans_unite(self):
        """Il n'y a rien à choisir, donc rien à deviner."""
        from Code.paliers import norme_depuis_indicateur
        for texte, v in (("12 retouches", 12.0), ("max 3 retouches", 3.0),
                         ("500 euros maximum", 500.0)):
            n = norme_depuis_indicateur(texte)
            assert n is not None and n["valeur"] == v, texte
            assert n["sens"] == "moins", texte

    def test_le_SENS_explicite_l_emporte_toujours(self):
        from Code.paliers import norme_depuis_indicateur
        assert norme_depuis_indicateur("au moins 20 par jour")["sens"] == "plus"
        assert norme_depuis_indicateur("at least 20 units")["sens"] == "plus"
        assert norme_depuis_indicateur("within 2 days")["sens"] == "moins"
        # à défaut : un pourcentage monte, le reste descend
        assert norme_depuis_indicateur("98 %")["sens"] == "plus"
        assert norme_depuis_indicateur("3 semaines")["sens"] == "moins"


class TestLaNormeSeRegleLaOuLaPhraseSEcrit:
    """⚠️ Elle se devinait plus tard, dans l'écran d'évaluation, à partir d'un
    texte libre. Deux défauts mesurés : elle lisait l'indicateur de performance
    d'une connexion sortante — VIDE sur les deux sorties du banc — en ignorant
    « réussi quand… », qui porte le chiffre et que cette fenêtre collecte
    elle-même ; et son parseur prenait le premier nombre. Le second est corrigé
    au-dessus ; le premier est de FOND."""

    def test_la_sortie_PORTE_sa_norme(self, client, app, scene):
        d = client.get("/qualify/outputs/%s" % scene["act"]).get_json()
        o = d["outputs"][0]
        for champ in ("norme_valeur", "norme_unite", "norme_sens", "norme_proposee"):
            assert champ in o, champ

    def test_la_proposition_lit_REUSSI_QUAND_d_abord(self, client, app, scene):
        """C'est le champ que cette fenêtre collecte, et c'est lui qui porte le
        chiffre. L'indicateur de performance vient ensuite."""
        from Code.extensions import db
        from Code.models.models import Data
        with app.app_context():
            d1 = db.session.get(Data, scene["d1"])
            avant = d1.minimum_performance_text
            d1.minimum_performance_text = "Plan d'essais couvert à 100 %."
            db.session.commit()
        try:
            o = next(x for x in client.get("/qualify/outputs/%s" % scene["act"])
                     .get_json()["outputs"] if x["data_id"] == scene["d1"])
            assert o["norme_proposee"]["valeur"] == 100.0
            assert o["norme_proposee"]["unite"] == "%"
            assert o["norme_proposee"]["sens"] == "plus"
        finally:
            with app.app_context():
                db.session.get(Data, scene["d1"]).minimum_performance_text = avant
                db.session.commit()

    def test_enregistrer_POSE_la_norme(self, client, app, scene):
        from Code.extensions import db
        from Code.models.models import Data
        _connecte(client, scene["admin"], "test@devoptiq.com", scene["entity"])
        r = client.post("/qualify/save/%s" % scene["act"], data=json.dumps({"outputs": [
            {"data_id": scene["d1"], "nature": "RESULT", "source": "MANUAL",
             "minimum_performance_text": "Livré vite.",
             "norme_valeur": 48, "norme_unite": "h", "norme_sens": "moins"}]}),
            content_type="application/json")
        assert r.status_code == 200
        with app.app_context():
            d1 = db.session.get(Data, scene["d1"])
            assert (d1.norme_valeur, d1.norme_unite, d1.norme_sens) == (48.0, "h", "moins")
            from Code.paliers import mesurable
            assert mesurable(d1), "la sortie passe en régime MESURÉ"

    def test_la_norme_n_est_PAS_touchee_quand_la_cle_est_absente(self, client, app, scene):
        """⚠️ Même règle que `evidence` dans /mastery/evaluate : un client plus
        ancien, qui ne connaît pas ces champs, effacerait sinon une norme que
        personne n'a retirée."""
        from Code.extensions import db
        from Code.models.models import Data
        _connecte(client, scene["admin"], "test@devoptiq.com", scene["entity"])
        with app.app_context():
            d1 = db.session.get(Data, scene["d1"])
            d1.norme_valeur, d1.norme_unite, d1.norme_sens = 12.0, "j", "moins"
            db.session.commit()
        client.post("/qualify/save/%s" % scene["act"], data=json.dumps({"outputs": [
            {"data_id": scene["d1"], "nature": "RESULT", "source": "MANUAL",
             "minimum_performance_text": "Autre phrase."}]}),
            content_type="application/json")
        with app.app_context():
            assert db.session.get(Data, scene["d1"]).norme_valeur == 12.0

    def test_une_valeur_VIDE_rend_la_sortie_qualitative(self, client, app, scene):
        """Effacer la norme est un CHOIX, pas une suppression : la sortie
        repasse au jugement 0 → 4."""
        from Code.extensions import db
        from Code.models.models import Data
        _connecte(client, scene["admin"], "test@devoptiq.com", scene["entity"])
        with app.app_context():
            d1 = db.session.get(Data, scene["d1"])
            d1.norme_valeur, d1.norme_unite, d1.norme_sens = 12.0, "j", "moins"
            db.session.commit()
        client.post("/qualify/save/%s" % scene["act"], data=json.dumps({"outputs": [
            {"data_id": scene["d1"], "nature": "RESULT", "source": "MANUAL",
             "minimum_performance_text": "x", "norme_valeur": "",
             "norme_unite": "", "norme_sens": "moins"}]}),
            content_type="application/json")
        with app.app_context():
            d1 = db.session.get(Data, scene["d1"])
            assert d1.norme_valeur is None and d1.norme_sens is None

    def test_elle_passe_par_les_MEMES_gardes_que_la_route_des_paliers(self):
        """⚠️ Deux routes qui écrivent les trois mêmes colonnes avec deux
        validateurs finissent par ne plus écrire la même chose."""
        import inspect

        from Code.routes import qualify_outputs as qo
        src = inspect.getsource(qo._poser_norme)
        assert "_lire_norme" in src and "_peut_regler_la_norme" in src
        assert '"norme_valeur" not in it' in src, "la clé absente ne touche à rien"


@SAUT_ECRAN
class TestLEcranNePREREMPLITRien:
    """L'app PROPOSE, la personne POSE. C'est toute la différence avec ce qu'on
    vient de retirer."""

    def test_les_trois_champs_sont_ceux_de_la_fenetre_des_paliers(self):
        js = _lire(JS)
        b = _corps(js, "  function blocNorme(o, p) {")
        assert 'class="pal-champs"' in b
        assert "champUnite(" in b, "l'unité se choisit, elle ne se tape pas"
        assert "T('pal_valeur')" in b and "T('pal_sens')" in b

    def test_la_proposition_est_un_BOUTON_et_non_une_valeur_posee(self):
        js = _lire(JS)
        b = _corps(js, "  function blocNorme(o, p) {")
        # ⚠️ On vise l'EMPLOI, pas la présence du nom : le bouton mis derrière
        # un `false ?` laissait `data-prop` dans la source, et le cliquet
        # restait VERT. C'est la condition qu'on garde.
        assert "${prop ? `<button" in b and "data-prop" in b
        assert "T('conf_prop_ok')" in b
        # la valeur du champ ne vient JAMAIS de la proposition
        champ = b.split("data-v", 1)[1].split("</label>", 1)[0]
        assert "prop" not in champ, champ
        assert "fmtNb(o.norme_valeur)" in champ, "seule la norme ENREGISTRÉE"

    def test_ce_qui_est_ENREGISTRE_l_emporte_sur_la_proposition(self):
        """On ne revient pas sur un chiffre posé par quelqu'un."""
        b = _corps(_lire(JS), "  function blocNorme(o, p) {")
        assert "const prop = a ? null :" in b

    def test_la_ZONE_est_la_LIGNE_et_non_la_fenetre(self):
        """⚠️ `lireUnite` et `brancherUnite` prennent le PREMIER champ qu'ils
        trouvent, et il y a une ligne par sortie : on réglerait l'unité de la
        première pour tout le monde."""
        js = _lire(JS)
        b = _corps(js, "  function brancherNorme(el, o, p) {")
        assert "brancherUnite(el)" in b
        s = _corps(js, "  async function saveQualify() {")
        assert "lireUnite(l)" in s and "lireNb(l, '[data-v]')" in s

    def test_l_etiquette_de_la_phrase_ne_deborde_plus_sur_les_champs(self):
        """⚠️ `.cv2-cf-std label` posait un `display: block` aux trois `<label>`
        de la norme — même spécificité que `.pal-champs label`, donc c'est
        l'ORDRE du fichier qui tranchait — plus une marge et des capitales
        qu'ils n'ont pas demandées."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "\n.cv2-cf-std > label {" in css
        assert "\n.cv2-cf-std label {" not in css

    def test_les_libelles_de_la_norme_sont_dans_les_DEUX_langues(self):
        js = _lire(JS)
        for bloc in (js.split("    fr: {", 1)[1].split("\n    },", 1)[0],
                     js.split("    en: {", 1)[1].split("\n    },", 1)[0]):
            for k in ("conf_norme", "conf_norme_i", "conf_norme_off",
                      "conf_prop", "conf_prop_ok"):
                # ⚠️ La clé doit OUVRIR son entrée : `zz_conf_norme_off:`
                # contient `conf_norme_off:`, et le cliquet restait VERT en
                # renommant la clé qu'il garde.
                assert re.search(r"(?:^|[{,])\s*" + k + r"\s*:", bloc, re.M), k


@SAUT_ECRAN
class TestLaFenetreDeConfigurationEstJOIGNABLE:
    """⚠️⚠️ Elle ne l'était plus. Son SEUL chemin d'accès était le bouton de
    `.ev-vide`, qui ne s'affiche que si l'activité n'a AUCUNE sortie — or
    `activity_mastery` appelle `get_activity_outputs`, qui MATÉRIALISE les
    connexions sortantes : dès qu'une activité a une flèche qui en part, elle a
    des sorties, et le bouton disparaît pour toujours. Depuis « toutes les
    sorties, sans filtre de nature » (nov.), la nature `RESULT` ne sert plus de
    porte, et plus rien n'ouvrait cette fenêtre.

    C'était sans grande conséquence tant qu'elle ne portait que la nature des
    sorties (que personne ne lit) et leur phrase de réussite. Ce ne l'est plus :
    la NORME s'y règle. Trouvé au banc, en allant en poser une."""

    def test_la_rangee_des_reglages_porte_sa_porte(self):
        js = _lire(JS)
        r = _corps(js, "  function reglagesOu(st) {")
        assert "T('conf_open')" in r
        assert "ouvrirConfiguration(state.activity)" in r
        # ⚠️ Pour le DÉVELOPPEUR seulement : configurer une activité engage
        # tout le monde, comme le plan — un collaborateur n'en voit que deux.
        apres = r.split("if (jeSuisLeDev()) {", 1)[1]
        assert "T('conf_open')" in apres

    def test_la_valeur_dit_s_il_faut_l_ouvrir(self):
        """« 2 sorties » aurait répété ce que l'écran montre déjà. Ce qui
        manque, c'est combien n'ont pas de norme chiffrée."""
        r = _corps(_lire(JS), "  function reglagesOu(st) {")
        assert "r.mesurable" in r
        assert "nf('conf_sans_norme'" in r and "T('conf_tout_norme')" in r

    def test_quatre_boutons_repassent_a_DEUX_colonnes(self):
        """⚠️ À trois colonnes, le quatrième restait seul avec deux tiers de
        vide à sa droite. Déclaré APRÈS la règle des trois : à spécificité
        égale, c'est l'ordre du fichier qui tranche."""
        css = _sans_commentaires_css(_lire(CSS))
        i3 = css.index(".ou-reg:has(.cl-rb:nth-child(3))")
        i4 = css.index(".ou-reg:has(.cl-rb:nth-child(4))")
        assert i4 > i3, "la règle des quatre doit venir après celle des trois"
        assert "1fr 1fr" in _regle(css, ".ou-reg:has(.cl-rb:nth-child(4))")

    def test_les_libelles_de_la_porte_sont_dans_les_DEUX_langues(self):
        js = _lire(JS)
        for bloc in (js.split("    fr: {", 1)[1].split("\n    },", 1)[0],
                     js.split("    en: {", 1)[1].split("\n    },", 1)[0]):
            for k in ("conf_open", "conf_sans_norme_1", "conf_sans_norme_n",
                      "conf_tout_norme"):
                assert re.search(r"(?:^|[{,])\s*" + k + r"\s*:", bloc, re.M), k


# ══════════════════════════════════════════════════════════════════════
#  Décor
# ══════════════════════════════════════════════════════════════════════
def _ecart_mesure():
    """Une activité en écart dont le premier résultat est MESURÉ. Les chiffres
    sont ceux de l'écran : norme 48 h au plus, marche posée à 55 h pour le
    15/12, dernière mesure 70 h."""
    return {
        "activity_id": 70, "activity_name": "Valider le prototype", "competence": "",
        "demonstrated_level": 1, "demonstrated_label": "En acquisition",
        "required_level": 3, "required_label": "Maîtrise étendue", "gap": -2,
        "capabilities": [], "domaines": [],
        "results_in_gap": [{
            "data_id": 91, "name": "Rapport d'essais", "demonstrated_level": 1,
            "demonstrated_label": "En acquisition",
            "minimum_performance_text": "Plan d'essais couvert.",
            "mesurable": True, "mesure": 70.0, "manque": 2,
            "norme": {"valeur": 48.0, "unite": "h", "sens": "moins"},
            "palier": {"cible": 55.0, "echeance": "2026-12-15"},
        }],
    }


def _connecte(client, user_id, email, entity_id=None):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user_id
        sess["user_email"] = email
        if entity_id:
            sess["active_entity_id"] = entity_id


def _note(client, user_id, act, data_id, niveau, role_id):
    return client.post("/mastery/evaluate", data=json.dumps({
        "user_id": user_id, "activity_id": act, "data_id": data_id,
        "role_id": role_id, "evaluator": "2", "mastery_level": niveau}),
        content_type="application/json")


def _poser(client, app, scene, niveau):
    from Code.extensions import db
    from Code.models.models import CompetencyEvaluation
    with app.app_context():
        CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
        db.session.commit()
    _connecte(client, scene["dev"], "dev170@devoptiq.com", scene["entity"])
    for did in (scene["d1"], scene["d2"]):
        _note(client, scene["collab"], scene["act"], did, niveau, scene["role"])


def _en_ecart(client, app, scene):
    _poser(client, app, scene, 1)


def _au_niveau(client, app, scene):
    _poser(client, app, scene, 3)


@pytest.fixture(scope="module")
def scene(app, client):
    """⚠️ SA PROPRE carto, avec un `owner_id`. Une entité de test sans
    propriétaire est lisible par TOUT LE MONDE et devient le repli des
    fichiers suivants — et écrire dans l'entité du décor commun laisse
    l'entité ACTIVE ailleurs, ce qui se lit trois fichiers plus loin."""
    from Code.extensions import db
    from Code.models.models import (Activities, CompetencyEvaluation, Data, Entity,
                                    PlanFormation, Role, User, UserRole, activity_roles)
    from Code.security import hash_password

    with app.app_context():
        admin = User.query.filter_by(email="test@devoptiq.com").first()
        admin_id, admin_mail = admin.id, admin.email
        ent = Entity(name="Entité 170", owner_id=admin_id)
        db.session.add(ent)
        db.session.commit()
        dev = User(first_name="Dev", last_name="T170", email="dev170@devoptiq.com",
                   password=hash_password(MDP), status="user")
        collab = User(first_name="Collab", last_name="T170", email="collab170@devoptiq.com",
                      password=hash_password(MDP), status="user")
        db.session.add_all([dev, collab])
        db.session.commit()
        collab.manager_id = dev.id
        role = Role(name="Rôle 170", entity_id=ent.id)
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=collab.id, role_id=role.id, manager_id=dev.id))
        act = Activities(entity_id=ent.id, name="Activité 170")
        db.session.add(act)
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant",
            required_mastery_level=3))
        d1 = Data(entity_id=ent.id, name="Sortie A 170", type="flux",
                  producer_activity_id=act.id, semantic_nature="RESULT",
                  minimum_performance_text="Standard A")
        d2 = Data(entity_id=ent.id, name="Sortie B 170", type="flux",
                  producer_activity_id=act.id, semantic_nature="RESULT",
                  minimum_performance_text="Standard B")
        db.session.add_all([d1, d2])
        db.session.commit()
        cree = {"entity": ent.id, "dev": dev.id, "collab": collab.id, "role": role.id,
                "act": act.id, "d1": d1.id, "d2": d2.id, "admin": admin_id}

    yield cree

    with app.app_context():
        from Code.models.models import SessionEvaluation
        CompetencyEvaluation.query.filter_by(activity_id=cree["act"]).delete()
        PlanFormation.query.filter_by(role_id=cree["role"]).delete()
        SessionEvaluation.query.filter_by(user_id=cree["collab"]).delete()
        Data.query.filter_by(producer_activity_id=cree["act"]).delete()
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id == cree["act"]))
        UserRole.query.filter_by(role_id=cree["role"]).delete()
        Activities.query.filter_by(id=cree["act"]).delete()
        Role.query.filter_by(id=cree["role"]).delete()
        User.query.filter(User.id.in_([cree["dev"], cree["collab"]])).delete(
            synchronize_session=False)
        Entity.query.filter_by(id=cree["entity"]).delete()
        db.session.commit()

    # ⚠️ `client` et `auth_client` sont le MÊME objet, en portée session : une
    # session laissée sur le développeur déconnecterait tous les fichiers
    # suivants. On la rend telle qu'on l'a trouvée.
    with app.app_context():
        ent_test = Entity.query.filter_by(name="Entité Test").first()
        ent_test_id = ent_test.id if ent_test else None
    _connecte(client, admin_id, admin_mail, ent_test_id)


# ══════════════════════════════════════════════════════════════════════
#  4 · LE PLAN EST UNE PAGE, ET DEUX DESSINS
#  ⚠️ C'etait une FENETRE de 800 x 736 px reels dans un ecran de 1600 x 1000
#  — la moitie de la largeur — avec 1 089 px a derouler pour 794 visibles, et
#  le verdict « il manque 74 h » en SIXIEME position de sa colonne de droite.
#  ⚠️⚠️ Et les deux dessins REMPLACENT, ils ne s'ajoutent pas : un premier
#  jet gardait les listes ET ajoutait les images.
# ══════════════════════════════════════════════════════════════════════
GAB = os.path.join(RACINE, "Code", "routes", "templates", "competences_view.html")


def _section_plan(css_brut):
    """La section de la page, BORNÉE : la feuille fait 4 700 lignes et porte
    presque toujours un homonyme de ce qu'on croit garder.

    ⚠️⚠️ On découpe AVANT de retirer les commentaires — le repère de section
    EST un commentaire — et on jette ensuite ce qui RESTE de ce commentaire :
    la coupe tombe en son milieu, donc son `/*` est parti et le nettoyage ne
    le reconnaît plus. Onzième fois que cette famille de piège se présente ;
    le cliquet du gris s'était attrapé sur la phrase qui l'explique."""
    tail = css_brut.split("LE PLAN DE FORMATION — une PAGE", 1)[1]
    return _sans_commentaires_css(tail.split("*/", 1)[1])


@SAUT_ECRAN
class TestLePlanEstUnePage:

    def test_la_fenetre_a_disparu_au_profit_d_un_ECRAN(self):
        js, gab = _lire(JS), _lire(GAB)
        assert "cv2-ecran-plan" in gab, "la page n'est pas dans le gabarit"
        assert "cv2-plan-win" not in gab and "cv2-plan-win" not in js
        assert "cv2-plan-body" not in js and "fermerPlan" not in js
        # elle rejoint la liste des écrans, sinon rien ne la masque
        assert "'#cv2-ecran-plan'" in js.split("const ECRANS", 1)[1].split("]", 1)[0]
        assert "nom !== 'plan'" in js

    def test_le_retour_ramene_D_OU_L_ON_VIENT(self):
        """Le plan s'ouvre depuis la page d'évaluation ET depuis le
        diagnostic : un retour qui tomberait toujours sur la galerie ferait
        refaire deux clics à chaque fois."""
        js = _lire(JS)
        assert "state.planRetour = state.ecran" in js
        r = _corps(js, "  function retourDuPlan() {")
        assert "state.planRetour === 'eval'" in r and "ouvrirEvaluation" in r
        assert "chargerSynthese()" in r

    def test_LES_DEUX_DESSINS_REMPLACENT(self):
        """⚠️ C'est le reproche qui a rouvert cette passe : « cela devient
        presque trop chargé ». La frise prend la place de l'échéancier en
        peigne, des deux chiffres d'entrée du verdict et de la barre de
        répartition ; le classement celle des trois jauges et de la liste de
        détail qui redisait la colonne du chemin."""
        js = _lire(JS)
        for mort in ("function majMix", "function renderSemaines", "cv2-mix",
                     "cv2-semaines", "cv2-semx", 'cv2-barre"', 'cv2-chiffres"',
                     "function curseur(", "cv2-plan-grille"):
            assert mort not in js, mort + " survit"
        css = _sans_commentaires_css(_lire(CSS))
        for mort in (".cv2-mix", ".cv2-semaine", ".cv2-semx", ".cv2-barre {",
                     ".cv2-chiffres", ".cv2-curseur", ".cv2-plan-win"):
            assert mort not in css, mort + " survit dans la feuille"

    def test_la_frise_porte_la_CAPACITE_et_les_semaines(self):
        """⚠️ Les heures et les semaines sont la MÊME grandeur : la longueur
        d'un segment dit ce qu'il coûte ET combien de temps il prend. Le trait
        blanc est la capacité, et ce qui est à sa droite est hachuré."""
        r = _corps(_lire(JS), "  function renderFrise(c) {")
        assert "c.capacite / ech * 100" in r, "la coupe est posée sur la capacité"
        assert "pl-fr-de" in r and "pl-fr-c" in r
        assert "Math.ceil(ech / c.hs)" in r, "l'axe compte des semaines"
        assert "T('plan_wk')" in r

    def test_l_etiquette_de_coupe_ne_sort_pas_du_bandeau(self):
        """⚠️ Le bandeau est en `overflow: hidden` : près du bord, l'étiquette
        centrée serait coupée sans rien signaler."""
        r = _corps(_lire(JS), "  function renderFrise(c) {")
        assert "coupe > 88" in r and "coupe < 7" in r

    def test_le_verdict_ne_porte_qu_UN_chiffre(self):
        """⚠️ Il en portait TROIS. Les deux premiers sont les entrées de la
        soustraction, et la frise les montre déjà : sa longueur totale est le
        besoin, l'étiquette de son trait blanc la capacité."""
        r = _corps(_lire(JS), "  function renderVerdict(c) {")
        assert r.count('class="pl-vn') == 1, "un seul chiffre"
        assert "plan_manque_k" in r and "plan_reste_k" in r

    def test_une_colonne_du_classement_a_un_SOCLE(self):
        """⚠️ À hauteur nulle, le niveau 0 se confondrait avec « pas de niveau
        du tout » — et les deux ne se corrigent pas de la même façon. Une
        activité non évaluée n'entre de toute façon jamais dans un plan."""
        r = _corps(_lire(JS), "  function renderClassement() {")
        assert "Math.max(10, dem * PAS)" in r

    def test_le_requis_est_un_TIRET_pose_sur_la_colonne(self):
        """Une cible se dessine, elle ne se remplit pas — c'est le device de
        la vue d'ensemble, repris pour la même question."""
        r = _corps(_lire(JS), "  function renderClassement() {")
        assert "pl-cl-req" in r and "req * PAS - 2" in r
        css = _sans_commentaires_css(_lire(CSS))
        assert "position: absolute" in _regle(css, "\n.pl-cl-req {")

    def test_le_nom_d_une_activite_a_la_largeur_de_sa_VOIE(self):
        """⚠️ Mesuré : dans la largeur de sa BARRE (62 px) il partait sur
        quatre lignes. Le bouton prend toute la voie, la barre vit dedans."""
        r = _corps(_lire(JS), "  function renderClassement() {")
        assert "larg * 0.88" in r, "le bouton prend la voie"
        css = _sans_commentaires_css(_lire(CSS))
        assert "width: 58%" in _regle(css, "\n.pl-cl-f {")
        # et la zone du nom est BORNÉE, sinon elle pousse la légende
        assert "overflow: hidden" in _regle(css, "\n.pl-cl-x {")

    def test_le_segment_et_la_carte_s_allument_SANS_re_rendu(self):
        """⚠️ Un re-rendu à chaque survol ferait sauter ce qu'on est en train
        de regarder."""
        r = _corps(_lire(JS), "  function eclairer(i) {")
        assert r.count("classList.toggle('hi'") == 2, "la frise ET la carte"
        for interdit in ("innerHTML", "render", "recalculer"):
            assert interdit not in r, r

    def test_le_classement_SUIT_le_defilement(self):
        """⚠️ Mesuré : il s'arrête à 400 px en face d'une colonne d'actions de
        919 — et c'est la référence qu'on garde sous les yeux en lisant la
        liste, pas un en-tête qu'on lit une fois."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "position: sticky" in _regle(css, "\n.pl-bloc--cl {")
        assert "pl-bloc pl-bloc--cl" in _lire(JS)

    def test_le_plancher_typographique_de_la_PAGE(self):
        """11 px RÉELS, soit 13,75 écrits : `body.pg` porte `zoom: .8`.
        ⚠️ Deux exceptions ASSUMÉES et nommées : les heures écrites DANS un
        segment de frise et les repères de son axe — ce sont des graduations,
        pas ce qu'on vient lire."""
        css = _sans_commentaires_css(_lire(CSS))
        sec = _section_plan(_lire(CSS))
        # les graduations et les glyphes de pastille : ce ne sont pas des
        # textes qu'on vient lire, et les grossir casse la boîte qui les tient
        SECONDAIRE = (".pl-fr-s span", ".pl-fr-ax span", ".pl-cl-y span", ".pl-q")
        trop_petit = []
        for m in re.finditer(r"\n(\.[a-z0-9 .>:()\[\]=\"'-]*\{)([^}]*)\}", sec):
            sel, corps = m.group(1), m.group(2)
            if not sel.startswith(".pl-"):
                continue
            t = re.search(r"font-size:\s*([\d.]+)px", corps)
            if t and float(t.group(1)) < 13.75 and not any(x in sel for x in SECONDAIRE):
                trop_petit.append((sel.strip(), t.group(1)))
        assert not trop_petit, trop_petit

    def test_aucune_regle_de_la_page_ne_lit_le_gris_de_la_racine(self):
        """⚠️ Les quatre dérivés sont déclarés sur `:root`, où `--pg-accent`
        vaut encore le gris par défaut : ils rendent du GRIS."""
        sec = _section_plan(_lire(CSS))
        for derive in ("--pg-accent-soft", "--pg-accent-softer",
                       "--pg-accent-border", "--pg-accent-glow"):
            assert derive not in sec, derive

    def test_les_reglages_sont_BORNES(self):
        """⚠️ Une séance dans deux ans ne doit pas écrire une valeur qu'on ne
        peut plus reprendre à la main."""
        js = _lire(JS)
        r = _corps(js, "  function renderReglages(c) {")
        # ⚠️ LES TROIS branches : « au plus juste », la séance, et le pas des
        # deux réglages. Un seul `assert` répété deux fois ne gardait que la
        # première — c'est le cliquet qui est resté vert sur le défaut.
        assert r.count("borner('semaines'") == 2, "« au plus juste » ET la séance"
        assert "p[cle] = borner(cle," in r, "le pas des deux réglages"
        assert "Math.min(BORNES[cle][1]" in js and "Math.max(BORNES[cle][0]" in js

    def test_les_cles_de_la_page_existent_dans_les_DEUX_langues(self):
        """⚠️ L'accesseur rend la CLÉ quand elle manque, jamais un repli
        français : une clé absente s'affiche telle quelle, sans rien lever."""
        js = _lire(JS)
        blocs = dict(re.findall(r"\n    (fr|en): \{(.*?)\n    \},", js, re.S))
        assert set(blocs) == {"fr", "en"}
        NEUVES = ["plan_vise", "plan_hors", "plan_manque_k", "plan_reste_k",
                  "plan_cl_t", "plan_che_t", "plan_cl_dem", "plan_cl_req",
                  "plan_gap_n", "plan_retour", "plan_juste_b", "plan_seance_b"]
        for lang, b in blocs.items():
            dedans = set(re.findall(r"\b([a-z0-9_]+):", b))
            for c in NEUVES:
                assert c in dedans, (lang, c)
        # et l'anglais n'est pas une recopie du français
        for c in NEUVES:
            fr = re.search(r"\b%s: '([^']*)'" % c, blocs["fr"]).group(1)
            en = re.search(r"\b%s: '([^']*)'" % c, blocs["en"]).group(1)
            assert fr != en, c

    def test_les_cles_mortes_sont_parties_avec_leur_dernier_lecteur(self):
        """Une clé qu'on retire en même temps que son seul lecteur ne laisse
        rien derrière elle."""
        js = _lire(JS)
        for c in ("plan_need", "plan_capacity", "plan_need_total", "plan_cap_total",
                  "plan_mix", "plan_target", "plan_deliv", "plan_week_step_1",
                  "plan_juste:", "plan_seance_cal", "plan_gap_intro", "plan_seance:"):
            assert c not in js, c
