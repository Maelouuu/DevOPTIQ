# -*- coding: utf-8 -*-
"""LA VUE D'ENSEMBLE de la page Compétences : le classement et les marches.

Elle ne portait que le radar et la liste des rôles : on y lisait la FORME d'un
profil, jamais ce qui le retient. Tranchée sur maquette, à l'échelle. Ce
fichier garde ce que la structure promet :

  • le CLASSEMENT des activités, de la plus basse à la plus haute, et les
    MARCHES de celle qu'on choisit — deux choses qui ne se voyaient qu'en
    ouvrant l'écran d'évaluation, une activité à la fois ;
  • toutes les notes d'un coup, une ligne par activité, une cellule par
    sortie : le seul endroit où l'on voit D'OÙ vient le minimum ;
  • le relief d'une sortie mesurée, et la prochaine séance ;
  • DEUX chiffres qui ne disent pas la même chose — `niveau` tranche (le
    minimum, NULL tant qu'il manque une note), `plus_bas` décrit ;
  • et un coût FIXE : servir chaque activité séparément, c'est le défaut qui
    mettait le tableau global de la page RH à deux minutes et demie.
"""
import io
import json
import os
import re
from datetime import datetime

import pytest
from sqlalchemy import event

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS = os.path.join(RACINE, "static", "competences.css")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates", "competences_view.html")


def _lire(p):
    return io.open(p, encoding="utf-8").read()


# ⚠️ Même garde que `test_109` et `test_140` : le pilote tourne encore sur
# l'écran d'avant, et un contrôle qui rougit toujours n'est plus lu. Elle se
# rallume toute seule le jour où l'écran arrive.
ECRAN_REFONDU = "renderOeil" in _lire(JS)
pytestmark = pytest.mark.skipif(
    not ECRAN_REFONDU, reason="la vue d'ensemble refondue n'est pas dans cet arbre")


def _corps(js, entete):
    return js.split(entete, 1)[1].split("\n  }", 1)[0]


def _sans_commentaires_css(css):
    """⚠️ Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES : il
    s'attrape sinon lui-même sur l'explication de la règle qu'il garde."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _regle(css, entete):
    return css.split(entete, 1)[1].split("}", 1)[0]


def _bloc(css, entete, marqueur):
    """Le corps de l'at-règle `entete` QUI PORTE `marqueur`.

    ⚠️ `@media (max-width: 1100px)` et `prefers-reduced-motion` ouvrent
    chacun plusieurs blocs dans cette feuille : prendre « le premier » fait
    lire un bloc qui ne parle pas du sujet, et le cliquet passe au vert sans
    rien garder. Mesuré — deux cas sont tombés là-dessus."""
    for part in css.split(entete)[1:]:
        corps = part.split("\n}", 1)[0]
        if marqueur in corps:
            return corps
    raise AssertionError(entete + " ne porte nulle part " + marqueur)


def _sans_commentaires_js(js):
    """Même raison que pour le CSS : un cliquet qui cherche une chaîne
    s'attrape sinon sur le commentaire qui explique ce qu'il garde."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", js, flags=re.S)


_N = [0]


@pytest.fixture
def monde(app, ids):
    """Un collaborateur, son développeur, et de quoi montrer les CINQ états.

    ⚠️ Le décor est propre à ce fichier et il part en sortant : la base est
    commune à toute la suite, et les rôles le sont à l'entreprise depuis le
    23/09 — un nom fixe fait collision dès que deux cas tournent.
    """
    from Code.models.models import (Activities, CompetencyEvaluation, Data, Link,
                                    PalierPerformance, Role, User, UserRole,
                                    activity_roles)
    from Code.security import hash_password
    _N[0] += 1
    n = _N[0]
    with app.app_context():
        dev = User(first_name="Dev", last_name="T145", email="dev.t145.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        col = User(first_name="Col", last_name="T145", email="col.t145.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        tiers = User(first_name="Tiers", last_name="T145", email="tiers.t145.%d@test" % n,
                     password=hash_password("Test1234!"), status="user")
        db.session.add_all([dev, col, tiers])
        db.session.commit()

        r1 = Role(name="T145 Principal %d" % n, entity_id=ids["entity_id"])
        r2 = Role(name="T145 Second %d" % n, entity_id=ids["entity_id"])
        db.session.add_all([r1, r2])
        db.session.commit()
        db.session.add_all([UserRole(user_id=col.id, role_id=r1.id, manager_id=dev.id),
                            UserRole(user_id=col.id, role_id=r2.id, manager_id=dev.id)])

        noms = ["Mesurer %d", "Juger %d", "Attendre %d", "Vide %d"]
        actes = [Activities(name=t % n, entity_id=ids["entity_id"]) for t in noms]
        aval = Activities(name="T145 Aval %d" % n, entity_id=ids["entity_id"])
        db.session.add_all(actes + [aval])
        db.session.commit()
        for a, req in zip(actes, (3, 2, 2, 2)):
            db.session.execute(activity_roles.insert().values(
                activity_id=a.id, role_id=r1.id, status="Garant",
                required_mastery_level=req))
        # ⚠️ La MÊME activité portée par un second rôle, plus exigeant : le
        # requis retenu doit être le plus exigeant des deux.
        db.session.execute(activity_roles.insert().values(
            activity_id=actes[1].id, role_id=r2.id, status="Garant",
            required_mastery_level=4))
        # Trois activités portent une sortie ; la quatrième n'en a aucune.
        for a, lbl in zip(actes[:3], ("Durée %d", "Dossier %d", "Plus tard %d")):
            db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=a.id,
                                target_activity_id=aval.id, description=lbl % n,
                                type="flux"))
        # ⚠️ « Juger » porte une SECONDE sortie, qui restera sans note : c'est
        # le seul décor où la règle du minimum peut se démentir — une activité
        # à moitié notée ne doit pas avoir de verdict (NULL ≠ 0).
        db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=actes[1].id,
                            target_activity_id=aval.id, description="Annexe %d" % n,
                            type="flux"))
        db.session.commit()

        from Code.routes.qualify_outputs import get_activity_outputs
        sorties = {a.id: get_activity_outputs(a.id) for a in actes}
        # 1 · une sortie MESURÉE : son niveau vient du chiffre relevé.
        mes = sorties[actes[0].id][0]
        mes.norme_valeur, mes.norme_unite, mes.norme_sens = 48.0, "h", "moins"
        # ⚠️ `evalue_le` est OBLIGATOIRE : `derniere_mesure` ne retient que les
        # paliers réellement ÉVALUÉS — poser la marche suivante ne doit pas
        # faire retomber le niveau à « non évalué » entre deux sessions. Sans
        # cette date, la sortie n'a pas de mesure et donc pas de niveau.
        db.session.add(PalierPerformance(
            user_id=col.id, activity_id=actes[0].id, data_id=mes.id, role_id=r1.id,
            rang=1, cible_valeur=48.0, statut="atteint", mesure_valeur=46.0,
            evalue_le=datetime.utcnow(), niveau_atteint=2))
        # 2 · une sortie JUGÉE à la main, notée 1.
        jug = sorties[actes[1].id][0]
        db.session.add(CompetencyEvaluation(
            user_id=col.id, activity_id=actes[1].id, item_type="activity_results",
            item_id=jug.id, eval_number="2", note="", mastery_level=1))
        # 3 · une sortie que personne n'a notée : NULL, pas zéro.
        db.session.commit()
        info = {"dev": dev.id, "col": col.id, "tiers": tiers.id,
                "r1": r1.id, "r2": r2.id,
                "mesuree": actes[0].id, "jugee": actes[1].id,
                "attendue": actes[2].id, "vide": actes[3].id,
                "data_mes": mes.id, "data_jug": jug.id,
                "entity_id": ids["entity_id"]}
    yield info
    with app.app_context():
        for x in PalierPerformance.query.filter_by(user_id=info["col"]).all():
            db.session.delete(x)
        for x in CompetencyEvaluation.query.filter_by(user_id=info["col"]).all():
            db.session.delete(x)
        db.session.commit()


@pytest.fixture
def comme_dev(auth_client, monde):
    """⚠️ `auth_client` est partagé en portée session : on rend la session
    telle qu'on l'a trouvée, sinon tous les fichiers suivants se retrouvent
    connectés sous une autre identité."""
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")
        sess["user_id"] = monde["dev"]
    yield
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


def _apercu(client, monde):
    r = client.get("/mastery/apercu/%d" % monde["col"])
    assert r.status_code == 200, r.data
    return json.loads(r.data)


def _par_nom(d, debut):
    return next(a for a in d["activites"] if a["activity_name"].startswith(debut))


# ════════════════════════════════════════════════════════════════════════
#  Ce que l'aperçu sert — les mêmes règles que partout
# ════════════════════════════════════════════════════════════════════════
class TestCeQueLApercuSert:

    def test_une_sortie_MESUREE_tient_son_niveau_de_la_mesure(self, auth_client, monde, comme_dev):
        """Pas d'une note : on relève un chiffre, l'application le compare à
        la cible, et c'est le verdict qui fait le niveau."""
        a = _par_nom(_apercu(auth_client, monde), "Mesurer")
        s = a["sorties"][0]
        assert s["mesurable"] is True
        assert s["niveau"] == 2, "la norme atteinte vaut 2"
        assert s["note_main"] is None, "personne n'a posé de note à la main"
        assert len(s["paliers"]) == 1

    def test_le_niveau_d_une_activite_est_le_MINIMUM_de_ses_sorties(self, auth_client, monde, comme_dev):
        a = _par_nom(_apercu(auth_client, monde), "Mesurer")
        assert [s["niveau"] for s in a["sorties"]] == [2]
        assert a["demonstrated_level"] == 2

    def test_une_sortie_NON_NOTEE_empeche_le_verdict(self, auth_client, monde, comme_dev):
        """⚠️ NULL ≠ 0 : elle n'est pas un zéro, elle empêche de TRANCHER.

        « Juger » porte deux sorties : l'une notée 1, l'autre que personne n'a
        regardée. Un minimum PARTIEL donnerait 1 — et l'activité paraîtrait
        jugée alors qu'on n'a vu que la moitié de ce qu'elle produit.
        """
        a = _par_nom(_apercu(auth_client, monde), "Juger")
        niv = sorted((s["niveau"] for s in a["sorties"]),
                     key=lambda v: (v is None, v))
        assert niv == [1, None], "une notée, une pas encore"
        assert a["demonstrated_level"] is None, "pas de verdict sur une moitié"

    def test_une_activite_pas_encore_regardee_est_A_EVALUER(self, auth_client, monde, comme_dev):
        a = _par_nom(_apercu(auth_client, monde), "Attendre")
        assert a["sorties"][0]["niveau"] is None
        assert a["etat"] == "todo", "à évaluer, pas « en écart »"

    def test_une_activite_SANS_SORTIE_se_distingue_de_celle_qu_on_n_a_pas_notee(
            self, auth_client, monde, comme_dev):
        """Les deux absences ne se corrigent pas de la même façon : l'une se
        note, l'autre se configure."""
        a = _par_nom(_apercu(auth_client, monde), "Vide")
        assert a["sorties"] == [] and a["n_results"] == 0
        assert a["etat"] == "setup"

    def test_DEUX_chiffres_qui_ne_disent_pas_la_meme_chose(self, auth_client, monde, comme_dev):
        """`niveau` TRANCHE — le minimum, et NULL tant qu'une activité
        évaluable n'est pas notée. `plus_bas` DÉCRIT : le plus bas de ce qui
        est posé, quoi qu'il manque. Sans la seconde, l'écran afficherait
        « — » chez quelqu'un qui a des activités notées et ne dirait plus
        rien du tout."""
        d = _apercu(auth_client, monde)
        assert d["niveau"] is None, "une activité évaluable n'est pas notée"
        assert d["plus_bas"] == 2, "le plus bas de ce qui est posé"

    def test_le_classement_va_du_plus_bas_au_plus_haut(self, auth_client, monde, comme_dev):
        """⚠️ Et les sans-verdict à la FIN : une activité non évaluée n'a pas
        de rang dans la progression, elle n'est pas « en bas »."""
        d = _apercu(auth_client, monde)
        niv = [a["demonstrated_level"] for a in d["activites"]]
        poses = [n for n in niv if n is not None]
        assert poses == sorted(poses)
        assert all(n is None for n in niv[len(poses):]), "les sans-verdict en dernier"

    def test_le_requis_d_une_activite_portee_par_DEUX_roles_est_le_plus_exigeant(
            self, auth_client, monde, comme_dev):
        """Prendre le premier venu ferait dépendre le verdict de l'ordre des
        lignes — et une activité paraîtrait tenue parce qu'un rôle n'exige
        rien d'elle."""
        a = _par_nom(_apercu(auth_client, monde), "Juger")
        assert a["required_level"] == 4
        assert sorted(a["role_ids"]) == sorted([monde["r1"], monde["r2"]])

    def test_les_compteurs_comptent_les_memes_etats_que_l_ecran(self, auth_client, monde, comme_dev):
        d = _apercu(auth_client, monde)
        assert sum(d["compte"].values()) == len(d["activites"])
        # « Mesurer » 2 pour un requis de 3 → en écart ; « Juger » et
        # « Attendre » → à évaluer ; « Vide » → à configurer.
        assert d["compte"] == {"held": 0, "gap": 1, "todo": 2, "setup": 1}

    def test_on_ne_voit_que_les_roles_que_l_on_SUIT(self, app, client, monde):
        """⚠️ `encadre()` répond par PERSONNE : un développeur de 2 rôles sur
        4 voyait les 4. C'est la règle de `roles_suivis`, et elle doit être la
        même ici que sur la synthèse — deux périmètres dans le même écran,
        c'est la panne « j'ai perdu mes données de notation »."""
        from Code.models.models import UserRole
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = monde["dev"]
        with app.app_context():
            ur = UserRole.query.filter_by(user_id=monde["col"], role_id=monde["r2"]).first()
            ur.manager_id = monde["tiers"]
            db.session.commit()
        d = json.loads(c.get("/mastery/apercu/%d" % monde["col"]).data)
        assert [r["role_id"] for r in d["roles"]] == [monde["r1"]]

    def test_sans_droit_de_lire_la_route_REFUSE(self, app, monde):
        """Elle porte les niveaux d'une personne et ses mesures de séance."""
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = monde["tiers"]
        assert c.get("/mastery/apercu/%d" % monde["col"]).status_code == 403


# ════════════════════════════════════════════════════════════════════════
#  Le coût — fixe, quelle que soit la taille du périmètre
# ════════════════════════════════════════════════════════════════════════
class TestLeCout:

    def test_le_cout_ne_GRANDIT_pas_avec_le_nombre_d_activites(self, app, monde):
        """⚠️ On compte des REQUÊTES, pas des secondes : la suite tourne sur
        SQLite, où tout est dans le processus et où le défaut est invisible au
        chronomètre. Servir chaque activité séparément, c'est ~6 requêtes par
        activité plus une par sortie — le défaut qui mettait le tableau global
        de la page RH à deux minutes et demie."""
        from Code.apercu_competences import apercu
        from Code.models.models import Activities, Link, User, activity_roles

        def compter():
            n = [0]

            def top(conn, cur, stmt, params, ctx, many):
                n[0] += 1
            with app.test_request_context():
                moi = db.session.get(User, monde["dev"])
                event.listen(db.engine, "before_cursor_execute", top)
                try:
                    apercu(moi, monde["col"])
                finally:
                    event.remove(db.engine, "before_cursor_execute", top)
            return n[0]

        avant = compter()
        with app.app_context():
            from Code.routes.qualify_outputs import get_activity_outputs
            aval = Activities(name="T145 Aval bis", entity_id=monde["entity_id"])
            db.session.add(aval)
            db.session.commit()
            for i in range(6):
                a = Activities(name="T145 Renfort %d" % i, entity_id=monde["entity_id"])
                db.session.add(a)
                db.session.commit()
                db.session.execute(activity_roles.insert().values(
                    activity_id=a.id, role_id=monde["r1"], status="Garant",
                    required_mastery_level=2))
                db.session.add(Link(entity_id=monde["entity_id"], source_activity_id=a.id,
                                    target_activity_id=aval.id,
                                    description="Renfort %d" % i, type="flux"))
                db.session.commit()
                # ⚠️ Des sorties MESURÉES : c'est leur progression qui coûte
                # une requête chacune si on la relit sortie par sortie. Avec
                # des sorties jugées à la main, le défaut ne se verrait pas.
                s = get_activity_outputs(a.id)[0]
                s.norme_valeur, s.norme_unite, s.norme_sens = 10.0, "j", "moins"
            db.session.commit()
        apres = compter()
        assert apres == avant, "six activités de plus, et pas une requête de plus"


# ════════════════════════════════════════════════════════════════════════
#  L'écran
# ════════════════════════════════════════════════════════════════════════
class TestLEcran:

    def test_la_page_porte_les_QUATRE_sections(self):
        html = _lire(GABARIT)
        bloc = html.split('id="cv2-ecran-synthese"', 1)[1].split("</section>", 1)[0]
        for part in ('id="vo-nuit"', 'id="cv2-profil"', 'id="vo-notes"',
                     'id="vo-relief"', 'id="cv2-seances"'):
            assert part in bloc, part
        # ⚠️ Le bandeau de situation est parti AVEC son seul appelant : ses
        # quatre tuiles sont devenues le panneau du grand chiffre, à côté de
        # ce qu'elles expliquent.
        assert 'id="cv2-bilan"' not in html
        assert "function renderBilan" not in _lire(JS)

    def test_DEUX_lectures_en_PARALLELE(self):
        """La synthèse porte les rôles et le profil, l'aperçu porte les
        sorties et leurs paliers. En série, c'est deux allers vers la base
        pour une page qui se rouvre à chaque changement de collaborateur."""
        js = _lire(JS)
        c = _corps(js, "  async function chargerSynthese() {")
        assert "await Promise.all([" in c
        assert "/mastery/synthese/" in c and "/mastery/apercu/" in c

    def test_un_echec_de_l_apercu_n_EMPORTE_PAS_la_page(self):
        """C'est la leçon de `/panel`, qui retenait son HTML le temps d'un
        appel inter-services et annonçait ensuite une panne."""
        js = _lire(JS)
        c = _corps(js, "  async function chargerSynthese() {")
        assert "state.apercu = ap.__error ? null : ap;" in c
        for f in ("renderOeil", "renderNotes", "renderRelief"):
            vide = _corps(js, "  function %s(ap) {" % f)
            assert "classList.add('hidden')" in vide, f

    def test_le_classement_distingue_le_ZERO_du_NON_EVALUE(self):
        """⚠️ Zéro veut dire « non démontré » ; non évalué veut dire qu'on n'a
        pas regardé. Le socle de 10 px fait que le niveau 0 se VOIE — à
        hauteur nulle il se confondrait avec « pas de barre du tout »."""
        js = _lire(JS)
        assert "const CL_SOCLE = 10" in js
        c = _corps(js, "  function classement(ap) {")
        assert "estNul(niv) ? 'q'" in c
        assert "vide ? '—' : '?'" in c, "sans sortie, et pas encore notée"
        css = _sans_commentaires_css(_lire(CSS))
        assert "repeating-linear-gradient" in _regle(css, "\n.esc .st .bar.q {")

    def test_la_barre_porte_la_couleur_SEMANTIQUE_de_l_activite(self):
        """Celle que le serveur calcule (CDC 3.5) et qu'elle a partout
        ailleurs : deux implémentations d'un même verdict finissent par
        diverger."""
        js = _lire(JS)
        c = _corps(js, "  function classement(ap) {")
        assert "{ green: 'g', orange: 'a', red: 'r' }[a.color]" in c
        css = _sans_commentaires_css(_lire(CSS))
        for t in ("g", "a", "r"):
            assert "linear-gradient" in _regle(css, "\n.esc .st .bar.%s {" % t), t

    def test_les_marches_REUTILISENT_le_rail_de_l_ecran_d_evaluation(self):
        """Une sortie mesurée se lit de la même façon partout, ou elle se lit
        deux fois. Seules ses encres changent — elle est posée sur un panneau
        sombre."""
        js = _lire(JS)
        m = _corps(js, "  function marches(ap) {")
        assert "railHtml(s)" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "color: #fff" in _regle(css, "\n.mpan .pal-pas .pal-v {")
        # l'encre « tenu » telle qu'elle se pose sur un fond sombre
        assert "var(--cv-g-40)" in _regle(css, "\n.mpan .pal-pas--atteint .pal-v, "
                                               ".mpan .pal-pas--atteint .pal-s {")

    def test_cliquer_une_activite_change_les_marches(self):
        js = _lire(JS)
        c = _corps(js, "  function classement(ap) {")
        assert "state.voAct = a.activity_id; state.voMarche = 0;" in c
        assert "classement(ap); marches(ap);" in c

    def test_le_panneau_des_marches_ne_porte_qu_UNE_sortie(self):
        """⚠️ Elles étaient toutes empilées. Mesuré sur une activité à quatre
        sorties de quatre marches : le panneau faisait **847 px**, le bloc de
        nuit devenait quatre fois plus haut que le classement d'à côté, et les
        rails se marchaient dessus. Une à la fois, et des flèches pour passer
        à la suivante — 244 px après.
        """
        js = _lire(JS)
        m = _corps(js, "  function marches(ap) {")
        assert "const s = mes[state.voMarche];" in m
        assert "mes.forEach(" not in m, "une seule, pas toutes"
        assert "state.voMarche += sens" in m
        # ⚠️ Même règle que la navigation entre activités : une flèche qui ne
        # mène nulle part n'est pas un bouton. Pas de bouclage.
        assert "if (state.voMarche > 0) nav.appendChild(fleche(-1));" in m
        assert "if (state.voMarche < mes.length - 1) nav.appendChild(fleche(1));" in m
        assert "(state.voMarche + 1) + ' / ' + mes.length" in m
        css = _sans_commentaires_css(_lire(CSS))
        assert "min-height" in _regle(css, "\n.mpan {"), \
            "sans plancher, passer de quatre marches à une fait sauter le bloc"

    def test_la_pastille_de_norme_ne_REDIT_pas_le_drapeau_du_rail(self):
        """« NORME DE L'ENTREPRISE » s'affichait deux fois, à deux lignes
        d'écart. Elle ne garde que ce qu'elle seule porte : la valeur et son
        sens."""
        js = _lire(JS)
        m = _corps(js, "  function marches(ap) {")
        assert "T('pal_norme_tag')" not in m
        assert "const signe = s.norme.sens === SENS_MOINS ? '≤ ' : '≥ ';" in m

    def test_la_MESURE_a_son_propre_fond_sur_le_panneau_sombre(self):
        """⚠️ C'est une PASTILLE, pas une ligne de texte : lui donner une
        encre blanche sans toucher à son fond, c'était du blanc sur du vert
        pâle — quatre rectangles clairs et vides à l'écran, mesuré."""
        css = _sans_commentaires_css(_lire(CSS))
        for sel in ("\n.mpan .pal-pas .pal-m {",
                    "\n.mpan .pal-pas--atteint .pal-m {",
                    "\n.mpan .pal-pas--manque .pal-m {"):
            assert "background:" in _regle(css, sel), sel

    def test_la_barre_des_collaborateurs_passe_EN_HAUT(self):
        """⚠️ En colonne elle prenait 268 px à la page qui en a le plus
        besoin : le bloc de nuit y porte DEUX colonnes, et le panneau des
        marches débordait. Les autres écrans n'ont pas de barre du tout."""
        js = _lire(JS)
        e = _corps(js, "  function montrerEcran(nom) {")
        assert "l.classList.toggle('est-large', nom === 'synthese');" in e
        css = _sans_commentaires_css(_lire(CSS))
        assert "flex-direction: column" in _regle(css, "\n.cv2-layout.est-large {")
        assert "flex-direction: row" in _regle(css, "\n.cv2-layout.est-large .cv2-collab {")

    def test_le_relief_est_le_MEME_que_celui_de_la_fenetre_des_courbes(self):
        """Deux tracés d'une même progression finiraient par ne plus dire la
        même chose."""
        js = _lire(JS)
        r = _corps(js, "  function renderRelief(ap) {")
        assert "reliefSvg({ name: s.nom, performance: s })" in r
        assert "bilanRelief(s)" in r
        # ⚠️ Le sélecteur n'existe que s'il y a de quoi choisir : une rangée
        # d'un seul bouton est un titre déguisé.
        assert "if (mes.length > 1) {" in r

    def test_une_sortie_MESUREE_se_voit_dans_la_bande(self):
        """Son niveau ne vient pas d'une note mais d'un chiffre relevé en
        séance, et les deux ne se corrigent pas de la même façon."""
        js = _lire(JS)
        n = _corps(js, "  function renderNotes(ap) {")
        assert "s.mesurable && s.norme ? ' mes' : ''" in n
        css = _sans_commentaires_css(_lire(CSS))
        assert "inset 0 0 0 2px" in _regle(css, "\n.heat .hc.mes {")

    def test_la_bande_porte_sa_LEGENDE(self):
        """Elle a son propre dégradé — elle montre des SORTIES, pas des
        activités, et la couleur n'y veut pas dire la même chose que sur les
        barres du classement."""
        js = _lire(JS)
        n = _corps(js, "  function renderNotes(ap) {")
        for k in ("vo_leg_sous", "vo_leg_atteint", "vo_leg_mesure", "vo_leg_rien"):
            assert k in n, k

    def test_le_bloc_de_nuit_est_UN_objet(self):
        """Le relief du vocabulaire maison : quatre ombres portées empilées,
        plus deux arêtes internes."""
        css = _sans_commentaires_css(_lire(CSS))
        nuit = _regle(css, "\n.vo-nuit {")
        assert nuit.count("rgba(15, 22, 49") >= 4
        assert "inset 0 1px 0" in nuit and "inset 0 -2px 0" in nuit

    def test_les_libelles_existent_dans_les_DEUX_langues(self):
        """⚠️ Une clé absente d'une langue ne lève RIEN : elle retombe
        silencieusement sur le français, ou s'affiche telle quelle."""
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        cles = ["vo_couv", "vo_tout_en_bas", "vo_classement", "vo_marches",
                "vo_sortie_suiv", "vo_sortie_prec", "ou_n_sorties_1", "ou_n_sorties_n",
                "vo_ouvrir", "vo_sans_marche", "vo_sans_sortie", "vo_au_plus",
                "vo_au_moins", "vo_notes", "vo_notees", "vo_aucune_sortie",
                "vo_leg_sous", "vo_leg_atteint", "vo_leg_mesure", "vo_leg_rien",
                "vo_bouge", "vo_pas_qualifie"]
        for k in cles:
            assert (k + ":") in fr, "FR " + k
            assert (k + ":") in en, "EN " + k

    def test_le_pluriel_ne_se_devine_pas(self):
        js = _lire(JS)
        for c in ("vo_roles", "vo_acts", "vo_sorties", "ou_n_sorties"):
            assert ("%s_1:" % c) in js and ("%s_n:" % c) in js, c

    def test_une_valeur_ABSENTE_s_annonce_de_nouveau(self):
        """⚠️ RENVERSEMENT de la règle d'avant (« rien à annoncer ne s'annonce
        pas »). Elle venait d'une rangée de QUATRE pastilles où la valeur
        partageait la ligne du nom : « Technicité **aucun domaine** » se lisait
        comme un verdict, et ces 75 px faisaient passer la rangée sur deux
        lignes. Les boutons ne sont plus que trois, et la valeur a SA ligne :
        elle tient, et elle dit quelque chose — on sait qu'il n'y a rien sans
        avoir à ouvrir."""
        js = _lire(JS)
        m = _corps(js, "  function majChipTech() {")
        assert "T('cl_tech_0')" in m
        assert "c.querySelector('.val')" in m, "la valeur n'est plus le <b>"
        css = _sans_commentaires_css(_lire(CSS))
        # un bouton dont la valeur est vide ne laisse pas une ligne blanche
        assert "display: none" in _regle(css, "\n.cl-rb .tx .val:empty {")


class TestLEspacementDesCartes:
    """⚠⚠ DEUX COLONNES, pas deux rangées. En grille, la hauteur d'une
    rangée est celle de sa carte la plus haute : le profil fait deux fois la
    carte des notes, et « Prochaines séances » attendait donc 190 px sous la
    carte qu'elle suit — un trou qui ne se lit comme rien. Une grille ne sait
    pas faire ce tassement : chaque colonne est une PILE."""

    def test_les_cartes_sont_en_colonnes_pas_en_rangees(self):
        g = _lire(GABARIT)
        assert 'class="vo-cols"' in g
        assert g.count('class="vo-col"') == 2
        assert "vo-gr" not in g, "les rangées ne reviennent pas"
        for carte, col in (("cv2-profil", 0), ("vo-notes", 1), ("cv2-seances", 1)):
            avant = g.split('id="%s"' % carte, 1)[0]
            assert avant.count('class="vo-col"') == col + 1, carte

    def test_le_relief_est_une_BANDE_hors_des_colonnes(self):
        """⚠️ Mesuré : dans les 680 px réels d'une colonne, le SVG (828 unités
        de viewBox) se rendait à 0,78 et ses libellés tombaient entre 6,6 et
        10,2 px RÉELS — sous le plancher de 11. Et c'est ce qui permet au
        détail des séances de s'ouvrir à côté : le partager dans une colonne
        aurait ramené les libellés à 4 px."""
        g = _lire(GABARIT)
        apres = g.split('id="vo-relief"', 1)[0]
        assert apres.count('class="vo-col"') == 2, "la bande vient APRÈS les deux colonnes"
        assert "vo-bande" in g.split('id="vo-relief"', 1)[0][-220:]

    def test_le_bouton_du_detail_des_seances_est_CABLE(self):
        """⚠⚠ Il était rendu par `bilanRelief` et branché NULLE PART : sur la
        vue d'ensemble, « Le détail des séances » ne faisait rien. Seule
        `rendreValeurs`, dans la fenêtre des courbes, le câblait."""
        corps = _corps(_lire(JS), "  function renderRelief(ap) {")
        assert "[data-evol]" in corps, "le bouton doit être retrouvé"
        assert "basculerHisto(" in corps, "et branché"

    def test_le_detail_s_ouvre_A_COTE_et_pas_en_dessous(self):
        """La page a de la place à droite — mesuré, la colonne des notes
        était 358 px plus courte que celle du relief."""
        corps = _corps(_lire(JS), "  function renderRelief(ap) {")
        assert "pal-evo-duo" in corps and "pal-evo-g" in corps
        assert "pal-evo-cote" in corps
        css = _sans_commentaires_css(_lire(CSS))
        regle = _regle(css, '.pal-evo-cote[data-evo="1"] .pal-evo-duo {')
        assert "grid-template-columns" in regle
        assert regle.count("minmax(") == 2, "deux colonnes, pas une"

    def test_changer_de_sortie_REFERME_le_panneau(self):
        """⚠️ `innerHTML` vide les enfants, PAS l'attribut : changer de sortie
        pendant que le détail est ouvert laissait `data-evo="1"` sur une bande
        sans panneau — deux colonnes dont la seconde est vide, et un relief
        rétréci pour rien."""
        corps = _corps(_lire(JS), "  function renderRelief(ap) {")
        assert "z.dataset.evo = ''" in corps

    def test_le_detail_n_a_plus_qu_UNE_disposition(self):
        """La seconde, EMPILÉE, n'existait que pour la fenêtre des courbes —
        1 060 px, où partager le relief ramenait ses libellés sous 6 px. La
        fenêtre partie, le seul appelant est cette bande, qui construit
        toujours son couple : la branche était injoignable, et un code mort
        sous cliquet fige ce que personne ne rend.
        ⚠️ Son bouton de fermeture par le bas part avec elle : à côté, celui
        qui a ouvert ne bouge pas d'un pixel."""
        js = _lire(JS)
        bascule = _corps(js, "  function basculerHisto(card, r) {")
        assert "pal-evo-fin" not in bascule, "pas de second bouton à côté"
        assert "pal-evo-fin" not in _lire(CSS), "la règle part avec son porteur"
        assert "} else {" not in bascule, "une seule disposition"
        # …et le repère de repli garde sa garde : `.pal-pied` n'existe plus.
        assert "card.querySelector('.pal-bilan') || card.lastElementChild" in bascule

    def test_un_SEUL_ecart_separe_toutes_les_cartes(self):
        """Il en vivait trois : le `gap` de la grille, la marge basse du
        profil, la marge haute des séances. « Que ça fasse propre », c'est
        le même dans les deux sens."""
        css = _sans_commentaires_css(_lire(CSS))
        for sel in ("\n#cv2-ecran-synthese {", "\n.vo-cols {", "\n.vo-col {"):
            assert "gap: var(--vo-gap)" in _regle(css, sel), sel
        assert "flex-direction: column" in _regle(css, "\n.vo-col {")
        assert "margin-bottom" not in _regle(css, "\n.cv2-profil {")
        assert "margin: 0;" in _regle(css, "\n.cv2-seances {")


# ══════════════════════════════════════════════════════════════════════════
# LE LIEN — du NIVEAU de la barre choisie jusqu'au panneau
#
# « Dans le rendu de la flèche on a que la pointe dans l'app, c'est dommage ;
# on perd donc aussi l'animation qui faisait son charme. » Le reproche était
# exact et il visait une décision écrite : la maquette « L'entre-deux »
# comparait cinq mouvements à l'échelle réelle et retenait LE LIEN (« il se
# trace du niveau de la barre jusqu'au panneau, puis la pointe se pose ») —
# et seule la POINTE a été livrée, un triangle de bordure posé à un `top`
# fixe, au prétexte qu'un trait demanderait de mesurer la grille.
#
# Il la demande en effet. C'est le prix du trait, et il est payé ici.
# ══════════════════════════════════════════════════════════════════════════
class TestLeLienEstUnTrace:

    def test_la_pointe_SEULE_ne_survit_pas_au_mode_large(self):
        """⚠️ Le triangle statique ne vit plus QUE dans le repli en colonne,
        où il garde son sens. En mode large il redoublerait la pointe du
        lien, posée elle sur la pastille du panneau — deux pointes pour une
        arrivée."""
        css = _sans_commentaires_css(_lire(CSS))
        # ⚠️ On COMPTE, on ne borne pas : `@media (max-width: 1100px)` ouvre
        # CINQ blocs dans cette feuille, et couper au premier faisait lire
        # une zone située 1 400 lignes avant le lien — le cliquet passait au
        # vert sans rien garder. Mesuré en remettant le défaut.
        assert css.count(".vo-mp::before") == 1, "la pointe seule est restée"
        etroit = _bloc(css, "@media (max-width: 1100px) {", ".vo-lane")
        assert ".vo-mp::before" in etroit, "sa seule place est le repli"
        assert "\n.ln-trace {" in css and "@keyframes ln-tracer" in css

    def test_la_gouttiere_est_une_COLONNE_de_la_grille(self):
        """Un `gap` n'est pas une boîte : le lien a besoin d'une colonne pour
        s'y dessiner. ⚠️ Et elle coûte 36 px au classement — le `gap` de
        20 px disparaît, la colonne du lien en prend 56."""
        css = _sans_commentaires_css(_lire(CSS))
        r = _regle(css, "\n.vo-duo {")
        assert "minmax(0, 1fr) 56px 420px" in r
        assert "gap: 0" in r
        assert '<div class="vo-lane" id="vo-lane"' in _lire(JS)

    def test_les_DEUX_points_sont_mesures_sur_la_carte(self):
        """Le haut de la barre choisie, la pastille du panneau. C'est tout ce
        que le lien demande — et c'est ce qui fait qu'il PART de quelque
        part, au lieu de flotter à un `top` de 82 px."""
        c = _corps(_sans_commentaires_js(_lire(JS)), "  function geoLien() {")
        assert "'#vo-esc .st.on .bar'" in c, "le haut de la barre CHOISIE"
        assert "'#vo-sujet .vo-pt'" in c, "la pastille du panneau"
        assert "getBoundingClientRect" in c

    def test_la_mesure_DIVISE_par_le_zoom_du_corps(self):
        """⚠️⚠️ `getBoundingClientRect()` rend des pixels d'ÉCRAN — le
        `zoom: .8` de `body.pg` y est appliqué. Seules les coordonnées qu'on
        ÉCRIT repassent par lui : on divise, et on ne multiplie NULLE PART.
        Même correctif que la bulle du « i », qui se posait sur son propre
        bouton."""
        c = _corps(_sans_commentaires_js(_lire(JS)), "  function geoLien() {")
        assert "getComputedStyle(document.body).zoom" in c
        assert "/ z" in c, "on divise à l'écriture"
        assert "* z" not in c, "et on ne multiplie nulle part"

    def test_une_gouttiere_sans_hauteur_ne_dessine_RIEN(self):
        """⚠️ Volet replié, onglet jamais peint, parent masqué : tout rend des
        rects NULS. On ne dessine alors rien plutôt qu'un tracé à des
        coordonnées non finies — c'est le piège payé sur `fitView` de
        l'éditeur, où un facteur nul avait fini en `<rect x="Infinity">`."""
        js = _sans_commentaires_js(_lire(JS))
        g = _corps(js, "  function geoLien() {")
        assert "isFinite" in g and "return null" in g
        p = _corps(js, "  function poserLien() {")
        assert "if (!g) { lane.innerHTML = ''; return; }" in p

    def test_la_longueur_du_trace_vient_du_NAVIGATEUR(self):
        """Un tracé se dessine par son POINTILLÉ, et seul le navigateur
        connaît la longueur réelle d'une bézier."""
        p = _corps(_sans_commentaires_js(_lire(JS)), "  function poserLien() {")
        assert "getTotalLength()" in p
        assert "setProperty('--len'" in p
        css = _sans_commentaires_css(_lire(CSS))
        assert "stroke-dashoffset: var(--len)" in _regle(css, "@keyframes ln-tracer {")

    def test_la_lueur_garde_SON_pointille(self):
        """⚠️ Un éclat court qui défile : on ne lui pose que la LONGUEUR,
        jamais le `stroke-dasharray` du tracé — qui le ferait courir sur tout
        le chemin d'un coup."""
        js = _sans_commentaires_js(_lire(JS))
        p = _corps(js, "  function poserLien() {")
        bloc = p.split(".ln-glint", 1)[1]
        assert "setProperty('--len'" in bloc
        assert "strokeDasharray" not in bloc
        css = _sans_commentaires_css(_lire(CSS))
        assert "stroke-dasharray: 20 9999" in _regle(css, "\n.ln-glint {")

    def test_le_lien_se_rejoue_a_CHAQUE_changement_d_activite(self):
        """⚠️ `marches()` est le seul endroit qui change d'activité, et le
        nœud est RECONSTRUIT : une animation CSS ne se rejoue pas sur un
        élément qu'on laisse en place. Les DEUX sorties de la fonction le
        reposent — sans activité, la gouttière doit se vider."""
        js = _sans_commentaires_js(_lire(JS))
        m = _corps(js, "  function marches(ap) {")
        assert "if (!a) { poserLien(); return; }" in m, "la sortie sans activité"
        assert m.rstrip().endswith("poserLien();"), "et la sortie normale"
        assert "lane.innerHTML = lienHtml(g);" in js

    def test_le_lien_se_recalcule_quand_la_GRILLE_bouge(self):
        """⚠️ DEUX déclencheurs : `resize` dit que la FENÊTRE a changé,
        l'observateur dit que la grille a changé sans elle. Et il est gardé
        dans une variable — sans référence vive, le navigateur peut le
        ramasser, et le lien resterait au cadrage du premier rendu."""
        js = _sans_commentaires_js(_lire(JS))
        assert "const OBS_LIEN" in js and "new ResizeObserver" in js
        assert "window.addEventListener('resize', poserLien)" in js
        assert "document.fonts.ready.then(poserLien)" in js

    def test_le_lien_ne_vole_pas_le_clic(self):
        """Ce qui explique ne prend jamais le clic de ce qu'il explique : la
        barre d'à côté et le panneau se cliquent à travers la gouttière."""
        css = _sans_commentaires_css(_lire(CSS))
        assert "pointer-events: none" in _regle(css, "\n.vo-lane {")

    def test_la_barre_choisie_ne_porte_plus_SA_pointe(self):
        """⚠️ La sienne partait de son BAS, qui ne dit rien ; le lien part de
        son HAUT, c'est-à-dire de son NIVEAU. Deux pointes à 160 px l'une de
        l'autre, toutes deux « vers le panneau », ne désignaient plus rien."""
        css = _sans_commentaires_css(_lire(CSS))
        assert ".esc .st.on::after" not in css
        assert "\n.ln-src {" in css, "c'est la pastille du lien qui marque le départ"

    def test_le_MOUVEMENT_s_arrete_mais_pas_le_lien(self):
        """Sous `prefers-reduced-motion`, le trait reste — c'est lui qui relie
        les deux colonnes ; seul son mouvement s'arrête. La lueur, qui n'est
        QUE du mouvement, ne se dessine pas."""
        css = _sans_commentaires_css(_lire(CSS))
        bloc = _bloc(css, "@media (prefers-reduced-motion: reduce) {", ".ln-glint")
        assert "animation: none" in bloc, "le mouvement s'arrête"
        assert "stroke-dashoffset: 0" in bloc, "mais le trait se pose entier"
        assert ".ln-glint { display: none" in bloc, "la lueur n'est QUE du mouvement"

    def test_en_COLONNE_le_lien_s_efface_et_la_pointe_regarde_en_bas(self):
        """⚠️ Sous 1100 px RÉELS (les requêtes média ignorent le `zoom: .8` du
        corps) les deux colonnes s'empilent : la gouttière n'est plus entre
        elles, et un trait tiré de gauche à droite ne relierait plus rien."""
        css = _sans_commentaires_css(_lire(CSS))
        bloc = _bloc(css, "@media (max-width: 1100px) {", ".vo-lane")
        assert ".vo-lane { display: none; }" in bloc
        assert ".vo-mp::before" in bloc
        # la pointe du repli doit se suffire à elle-même : la règle du mode
        # large dont elle héritait n'existe plus.
        assert 'content: ""' in bloc and "border-style: solid" in bloc

