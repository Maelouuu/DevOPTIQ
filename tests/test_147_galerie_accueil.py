# -*- coding: utf-8 -*-
"""L'ÉCRAN D'ACCUEIL de la page Compétences : une carte par collaborateur.

La page s'ouvrait sur une phrase dans un cadre pointillé. Mesuré à
1600 × 1000 : **726 px de vide**, **38 % de la largeur utilisée**, et la barre
des collaborateurs qui passait de **214 × 253 à gauche à 1373 × 67 en haut**
dès qu'on choisissait quelqu'un — ce n'était plus le même objet.

Tranchée sur maquette (trois organisations à l'échelle réelle), direction
« la galerie » : une carte par collaborateur, avec le profil qu'on retrouvera
en grand dans son dossier. Ce fichier garde ce que la structure promet :

  • la carte dit EXACTEMENT ce que dit le dossier — c'est sa vignette, pas un
    second calcul du même niveau ;
  • un coût FIXE : `apercu` par personne, ce serait une dizaine de requêtes
    chacune, le défaut qui mettait le tableau global de la page RH à deux
    minutes et demie ;
  • le périmètre des RÔLES reste celui de `roles_suivis` : un développeur de
    2 rôles sur 4 ne voit pas les 4 ;
  • et la galerie ne SERT que les gens que la page liste déjà.
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


# ⚠️ Même garde que `test_109`, `test_140` et `test_145` : le pilote tourne
# encore sur l'écran d'avant, et un contrôle qui rougit toujours n'est plus
# lu. Elle se rallume toute seule le jour où l'écran arrive.
ECRAN_REFONDU = "renderGalerie" in _lire(JS)
pytestmark = pytest.mark.skipif(
    not ECRAN_REFONDU, reason="la galerie d'accueil n'est pas dans cet arbre")


def _sans_commentaires_css(css):
    """⚠️ Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES : il
    s'attrape sinon lui-même sur l'explication de la règle qu'il garde."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _sans_commentaires_js(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"^\s*//.*$", "", js, flags=re.M)


def _corps(js, entete):
    return js.split(entete, 1)[1].split("\n  }", 1)[0]


def _regle(css, entete):
    return css.split(entete, 1)[1].split("}", 1)[0]


_N = [0]


@pytest.fixture
def equipe(app, ids):
    """Un développeur, TROIS collaborateurs, et le cas qui compte : l'un
    d'eux tient deux rôles et n'est suivi que sur un seul.

    ⚠️ Décor propre à ce fichier, retiré en sortant : la base est commune à
    toute la suite, et les rôles le sont à l'entreprise depuis le 23/09 — un
    nom fixe fait collision dès que deux cas tournent.
    """
    from Code.models.models import (Activities, CompetencyEvaluation, Data, Link,
                                    PalierPerformance, Role, User, UserRole,
                                    activity_roles)
    from Code.security import hash_password
    _N[0] += 1
    n = _N[0]
    with app.app_context():
        def compte(p, nom):
            return User(first_name=p, last_name=nom,
                        email="%s.t146.%d@test" % (p.lower(), n),
                        password=hash_password("Test1234!"), status="user")

        dev = compte("Dev", "T146")
        a = compte("Ana", "T146")      # rattachement GLOBAL : tous ses rôles
        b = compte("Bob", "T146")      # rattachement PAR RÔLE : un seul
        c = compte("Cam", "T146")      # rien noté du tout
        db.session.add_all([dev, a, b, c])
        db.session.commit()
        a.manager_id = dev.id
        db.session.commit()

        r1 = Role(name="T146 Suivi %d" % n, entity_id=ids["entity_id"])
        r2 = Role(name="T146 Hors %d" % n, entity_id=ids["entity_id"])
        db.session.add_all([r1, r2])
        db.session.commit()
        db.session.add_all([
            UserRole(user_id=a.id, role_id=r1.id, manager_id=dev.id),
            # ⚠️ Bob tient DEUX rôles et le développeur n'en suit qu'un : sans
            # ce cas, la restriction de `roles_suivis` ne peut pas se démentir.
            UserRole(user_id=b.id, role_id=r1.id, manager_id=dev.id),
            UserRole(user_id=b.id, role_id=r2.id),
            UserRole(user_id=c.id, role_id=r1.id, manager_id=dev.id),
        ])
        db.session.commit()

        # ⚠️ Les noms sont choisis pour que l'ordre ALPHABÉTIQUE contredise
        # l'ordre des écarts : « Alpha » est à −1 de sa cible, « Zoulou » à
        # −3. Sans cette contradiction, un tri par nom rendrait le même
        # résultat que le tri par écart et le cliquet ne garderait rien.
        act1 = Activities(name="T146 Alpha %d" % n, entity_id=ids["entity_id"])
        act2 = Activities(name="T146 Zoulou %d" % n, entity_id=ids["entity_id"])
        hors = Activities(name="T146 Hors champ %d" % n, entity_id=ids["entity_id"])
        # Une activité dont les sorties ne sont PAS matérialisées : c'est le
        # seul décor où « la galerie n'écrit rien » peut se démentir.
        neuve = Activities(name="T146 Neuve %d" % n, entity_id=ids["entity_id"])
        aval = Activities(name="T146 Aval %d" % n, entity_id=ids["entity_id"])
        db.session.add_all([act1, act2, hors, neuve, aval])
        db.session.commit()
        for acte, req in ((act1, 3), (act2, 4), (neuve, 2)):
            db.session.execute(activity_roles.insert().values(
                activity_id=acte.id, role_id=r1.id, status="Garant",
                required_mastery_level=req))
        db.session.execute(activity_roles.insert().values(
            activity_id=hors.id, role_id=r2.id, status="Garant",
            required_mastery_level=2))
        for acte, lbl in ((act1, "Durée %d"), (act2, "Dossier %d"),
                          (hors, "Ailleurs %d"), (neuve, "Jamais lue %d")):
            db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=acte.id,
                                target_activity_id=aval.id, description=lbl % n,
                                type="flux"))
        db.session.commit()

        from Code.routes.qualify_outputs import get_activity_outputs
        mes = get_activity_outputs(act1.id)[0]
        mes.norme_valeur, mes.norme_unite, mes.norme_sens = 48.0, "h", "moins"
        jug = get_activity_outputs(act2.id)[0]
        get_activity_outputs(hors.id)
        db.session.add(PalierPerformance(
            user_id=a.id, activity_id=act1.id, data_id=mes.id, role_id=r1.id,
            rang=1, cible_valeur=48.0, statut="atteint", mesure_valeur=46.0,
            evalue_le=datetime.utcnow(), niveau_atteint=2))
        db.session.add(CompetencyEvaluation(
            user_id=a.id, activity_id=act2.id, item_type="activity_results",
            item_id=jug.id, eval_number="2", note="", mastery_level=1))
        db.session.add(CompetencyEvaluation(
            user_id=b.id, activity_id=act2.id, item_type="activity_results",
            item_id=jug.id, eval_number="2", note="", mastery_level=3))
        db.session.commit()
        info = {"dev": dev.id, "a": a.id, "b": b.id, "c": c.id,
                "r1": r1.id, "r2": r2.id, "act1": act1.id, "act2": act2.id,
                "hors": hors.id, "neuve": neuve.id, "entity_id": ids["entity_id"]}
    yield info
    with app.app_context():
        for uid in (info["a"], info["b"], info["c"]):
            for x in PalierPerformance.query.filter_by(user_id=uid).all():
                db.session.delete(x)
            for x in CompetencyEvaluation.query.filter_by(user_id=uid).all():
                db.session.delete(x)
        db.session.commit()


@pytest.fixture
def comme_dev(auth_client, equipe):
    """⚠️ `auth_client` est partagé en portée session : on rend la session
    telle qu'on l'a trouvée, sinon les fichiers suivants se retrouvent
    connectés sous une autre identité."""
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")
        sess["user_id"] = equipe["dev"]
    yield
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


def _galerie(client):
    r = client.get("/mastery/galerie")
    assert r.status_code == 200, r.data
    return json.loads(r.data)


def _carte(d, uid):
    return next(c for c in d["gens"] if c["user_id"] == uid)


# ════════════════════════════════════════════════════════════════════════
#  La carte est la VIGNETTE du dossier, pas un second calcul
# ════════════════════════════════════════════════════════════════════════
class TestLaCarteDitCeQueDitLeDossier:

    def test_les_memes_chiffres_que_l_apercu_personne_par_personne(
            self, auth_client, equipe, comme_dev):
        """Deux calculs d'un même niveau finiraient par afficher deux
        chiffres — c'est une enquête qu'on a déjà payée dans ce dépôt."""
        d = _galerie(auth_client)
        for uid in (equipe["a"], equipe["b"], equipe["c"]):
            c = _carte(d, uid)
            r = auth_client.get("/mastery/apercu/%d" % uid)
            assert r.status_code == 200, r.data
            ap = json.loads(r.data)
            assert c["couverture"] == ap["couverture"], uid
            assert c["compte"] == ap["compte"], uid
            assert c["n_activities"] == ap["n_activities"], uid

    def test_les_axes_du_radar_sont_ceux_du_dossier(self, auth_client, equipe, comme_dev):
        """Mêmes activités, même requis, même niveau démontré : la vignette
        doit avoir la forme de l'original."""
        d = _galerie(auth_client)
        for uid in (equipe["a"], equipe["b"], equipe["c"]):
            ap = json.loads(auth_client.get("/mastery/apercu/%d" % uid).data)
            attendu = sorted((x["activity_id"], x["required_level"],
                              x["demonstrated_level"]) for x in ap["activites"])
            rendu = sorted((x["activity_id"], x["required_level"],
                            x["demonstrated_level"]) for x in _carte(d, uid)["axes"])
            assert rendu == attendu, uid

    def test_les_axes_sont_tries_par_ECART_croissant(self, auth_client, equipe, comme_dev):
        """Le MÊME tri que `synthese.profil`, que le radar du dossier dessine :
        l'écart le plus criant d'abord, ce qui n'en a pas à la fin."""
        c = _carte(_galerie(auth_client), equipe["a"])
        ecarts = []
        for x in c["axes"]:
            if x["demonstrated_level"] is None or x["required_level"] is None:
                ecarts.append(99)
            else:
                ecarts.append(x["demonstrated_level"] - x["required_level"])
        assert ecarts == sorted(ecarts), ecarts

    def test_NULL_n_est_pas_ZERO(self, auth_client, equipe, comme_dev):
        """Une activité que personne n'a notée n'a pas de niveau — elle n'en a
        pas un qui vaut zéro. Le radar ne doit pas la poser au centre."""
        c = _carte(_galerie(auth_client), equipe["c"])
        assert all(x["demonstrated_level"] is None for x in c["axes"])
        assert c["n_evaluated"] == 0

    def test_la_couverture_ne_compte_que_les_activites_EVALUEES(
            self, auth_client, equipe, comme_dev):
        """Compter une activité non évaluée comme un zéro confondrait « pas
        démontré » et « pas encore regardé »."""
        c = _carte(_galerie(auth_client), equipe["c"])
        assert c["couverture"] is None, "rien d'évalué : pas de taux, pas un zéro"


# ════════════════════════════════════════════════════════════════════════
#  Le périmètre
# ════════════════════════════════════════════════════════════════════════
class TestLePerimetre:

    def test_un_developpeur_PAR_ROLE_ne_voit_que_SON_role(
            self, auth_client, equipe, comme_dev):
        """`encadre()` répond par PERSONNE : un développeur de 2 rôles sur 4
        verrait les 4. C'est la règle de `roles_suivis`, et la galerie
        l'applique comme le dossier."""
        c = _carte(_galerie(auth_client), equipe["b"])
        vus = {x["activity_id"] for x in c["axes"]}
        assert equipe["hors"] not in vus, "l'activité du rôle non suivi ne doit pas paraître"
        assert equipe["act1"] in vus and equipe["act2"] in vus

    def test_la_galerie_sert_les_MEMES_gens_que_le_contexte(
            self, auth_client, equipe, comme_dev):
        """Une carte que la liste ne porte pas serait une carte qu'aucun clic
        n'ouvre : les deux lisent `collaborateurs_de`."""
        d = _galerie(auth_client)
        ctx = json.loads(auth_client.get("/competences/contexte").data)
        assert ([c["user_id"] for c in d["gens"]]
                == [u["id"] for u in ctx["collaborateurs"]])
        assert d["est_dev"] is ctx["est_dev"]

    def test_sans_connexion_401(self, app, equipe):
        """⚠️ Un client NEUF : `client` et `auth_client` sont le même objet en
        portée session, et il arrive connecté."""
        anon = app.test_client()
        assert anon.get("/mastery/galerie").status_code == 401

    def test_les_totaux_sont_la_somme_des_cartes(self, auth_client, equipe, comme_dev):
        d = _galerie(auth_client)
        for k in ("held", "gap", "todo", "setup"):
            assert d["totaux"][k] == sum(c["compte"][k] for c in d["gens"]), k


# ════════════════════════════════════════════════════════════════════════
#  Le coût
# ════════════════════════════════════════════════════════════════════════
class TestLeCoutNeGrandditPasAvecLEffectif:

    def test_trois_collaborateurs_de_plus_ne_coutent_pas_une_requete_de_plus(
            self, app, equipe):
        """`apercu` par personne, ce serait une dizaine de requêtes chacune.
        Dix personnes, cent requêtes, à ~15 ms l'aller vers Neon.

        ⚠️ On compte des REQUÊTES, pas des secondes : la suite tourne sur
        SQLite, où tout est dans le processus et où le défaut est invisible au
        chronomètre."""
        from Code.apercu_competences import galerie
        from Code.competences_acces import collaborateurs_de
        from Code.models.models import User, UserRole
        from Code.security import hash_password

        def compter():
            n = [0]

            def top(conn, cur, stmt, params, ctx, many):
                n[0] += 1

            with app.test_request_context():
                moi = db.session.get(User, equipe["dev"])
                gens, _ = collaborateurs_de(moi)
                event.listen(db.engine, "before_cursor_execute", top)
                try:
                    galerie(moi, gens)
                finally:
                    event.remove(db.engine, "before_cursor_execute", top)
            return n[0]

        avant = compter()
        with app.app_context():
            renforts = []
            for i in range(3):
                u = User(first_name="Renf%d" % i, last_name="T146",
                         email="renf%d.t146.%d@test" % (i, _N[0]),
                         password=hash_password("Test1234!"), status="user")
                db.session.add(u)
                db.session.commit()
                u.manager_id = equipe["dev"]
                db.session.add(UserRole(user_id=u.id, role_id=equipe["r1"],
                                        manager_id=equipe["dev"]))
                db.session.commit()
                renforts.append(u.id)
        try:
            apres = compter()
            assert apres == avant, (
                "le coût a grandi avec l'effectif : %d requêtes pour 3 personnes, "
                "%d pour 6" % (avant, apres))
        finally:
            with app.app_context():
                for uid in renforts:
                    for ur in UserRole.query.filter_by(user_id=uid).all():
                        db.session.delete(ur)
                    u = db.session.get(User, uid)
                    if u is not None:
                        db.session.delete(u)
                db.session.commit()

    def test_la_galerie_n_ECRIT_rien(self, app, auth_client, equipe, comme_dev):
        """⚠️ `get_activity_outputs` matérialise les connexions sortantes en
        `Data` : on ne l'appelle pas depuis une page de lecture. La galerie
        relit ce qu'il a déjà posé."""
        from Code.models.models import Data
        with app.app_context():
            avant = Data.query.count()
        _galerie(auth_client)
        with app.app_context():
            assert Data.query.count() == avant


# ════════════════════════════════════════════════════════════════════════
#  La règle de `roles_suivis`, en bloc
# ════════════════════════════════════════════════════════════════════════
class TestSuivisEnBloc:

    def test_le_bloc_dit_la_MEME_chose_que_roles_suivis(self, app, equipe):
        """⚠️ `None` veut dire « aucune restriction », une liste VIDE « il n'en
        suit aucun ». Les confondre rouvrirait le défaut qu'on ferme."""
        from Code.apercu_competences import _suivis_en_bloc
        from Code.competences_acces import roles_suivis
        from Code.models.models import User
        with app.app_context():
            moi = db.session.get(User, equipe["dev"])
            ids = [equipe["a"], equipe["b"], equipe["c"], equipe["dev"]]
            bloc = _suivis_en_bloc(moi, ids)
            for uid in ids:
                un = roles_suivis(moi, uid)
                if un is None:
                    assert bloc[uid] is None, uid
                else:
                    assert bloc[uid] is not None and sorted(bloc[uid]) == sorted(un), uid


# ════════════════════════════════════════════════════════════════════════
#  L'écran
# ════════════════════════════════════════════════════════════════════════
class TestLEcran:

    def test_la_galerie_vit_HORS_de_la_barre_des_collaborateurs(self):
        """Les cartes SONT la liste : une barre de noms au-dessus d'une grille
        des mêmes noms serait deux portes pour un seul geste."""
        g = _lire(GABARIT)
        assert 'id="cv2-ecran-galerie"' in g
        avant = g.split('<div class="cv2-layout">', 1)[0]
        assert 'id="cv2-ecran-galerie"' in avant, (
            "la galerie doit être déclarée avant `.cv2-layout`, pas dedans")

    def test_le_cadre_pointille_n_est_plus_l_ecran_d_accueil(self):
        """Il ne sert plus qu'à l'état vide : aucun développeur rattaché, ou
        une lecture qui a échoué."""
        g = _lire(GABARIT)
        bloc = g.split('id="cv2-placeholder"', 1)[0].rsplit("<div", 1)[1]
        assert "hidden" in bloc, "le cadre pointillé doit naître masqué"

    def test_le_bouton_de_RETOUR_existe_dans_le_gabarit(self):
        """⚠️ Ce fichier câble ses ids SANS garde : un id absent lève une
        TypeError qui interrompt la suite de l'initialisation."""
        assert 'id="cv2-vers-galerie"' in _lire(GABARIT)

    def test_la_recherche_ecoute_input_et_pas_change(self):
        """⚠️ `change` n'arrive qu'à la perte du focus : le champ ne filtrerait
        rien pendant la frappe, sans la moindre erreur pour le dire."""
        js = _sans_commentaires_js(_lire(JS))
        bloc = js.split("const q = $('#gal-q');", 1)[1].split("filtrerGalerie();", 1)[0]
        assert "addEventListener('input'" in bloc
        assert "'change'" not in bloc

    def test_la_recherche_MASQUE_au_lieu_de_re_rendre(self):
        """Réécrire la grille à chaque frappe ferait perdre le curseur du champ
        qu'on tape."""
        corps = _corps(_lire(JS), "function filtrerGalerie() {")
        assert "hidden" in corps
        assert "innerHTML" not in corps

    def test_le_masquage_de_la_recherche_est_DECLARE(self):
        """⚠️ `[hidden]` est une règle du NAVIGATEUR : une classe d'auteur qui
        pose un `display` l'emporte, et la recherche ne masquerait rien."""
        css = _sans_commentaires_css(_lire(CSS))
        assert ".gal-c[hidden]" in css
        assert "display: none" in _regle(css, ".gal-c[hidden] {")

    def test_la_vignette_ne_porte_PAS_d_etiquettes(self):
        """À 150 px, neuf noms d'activité en 10,5 px ne tiennent pas : c'est la
        FORME qui se lit d'un coup d'œil."""
        js = _lire(JS)
        bloc = js.split("const etiquettes = ", 1)[1][:80]
        assert "mini ?" in bloc and "''" in bloc

    def test_le_requis_passe_en_FANTOME_sur_une_vignette(self):
        """Il est le même pour tout le monde — c'est la carto qui l'impose —
        donc rempli il devient la forme dominante et toutes les cartes se
        ressemblent trait pour trait."""
        js = _sans_commentaires_js(_lire(JS))
        assert "cv2-r-req--g" in js
        css = _sans_commentaires_css(_lire(CSS))
        regle = _regle(css, ".cv2-r-req--g {")
        assert "fill: none" in regle, "un requis rempli redeviendrait la forme dominante"

    def test_la_vignette_et_le_grand_radar_sortent_de_la_MEME_fonction(self):
        """Deux traçages d'un même profil finiraient par ne plus dire la même
        chose."""
        js = _sans_commentaires_js(_lire(JS))
        assert js.count("function radarSVG(") == 1
        assert "radarSVG(vus, { mini: true" in js

    def test_la_carte_est_BORNEE_en_largeur(self):
        """Mesuré : étirée à `1fr`, une carte de 560 px laissait son contenu
        occuper la moitié de sa largeur."""
        css = _sans_commentaires_css(_lire(CSS))
        regle = _regle(css, ".gal-grille {")
        assert "auto-fit" in regle, "`auto-fill` garde des colonnes vides"
        assert "460px" in regle, "la piste doit être plafonnée"
        assert "justify-content: center" in regle

    def test_aucune_regle_de_la_galerie_ne_lit_l_accent_doux_de_la_racine(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur `:root`,
        où `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS.
        Les mélanges s'écrivent SUR PLACE."""
        # ⚠️ Le repère de section est lui-même un COMMENTAIRE, et il cite les
        # quatre jetons pour dire de ne pas les employer. Découper dessus puis
        # retirer les commentaires ne suffit pas : le texte reprend AU MILIEU
        # du commentaire, dont la fin survit au nettoyage. On coupe donc après
        # le `*/` de l'en-tête. Sixième fois que ce piège se présente ici.
        bloc = _lire(CSS).split("LA GALERIE D'ACCUEIL", 1)[-1].split("*/", 1)[-1]
        bloc = _sans_commentaires_css(bloc)
        for jeton in ("--pg-accent-soft", "--pg-accent-softer",
                      "--pg-accent-border", "--pg-accent-glow"):
            assert jeton not in bloc, jeton

    def test_les_libelles_existent_dans_les_DEUX_langues(self):
        """⚠️ On lit les DICTIONNAIRES, pas `T()` : une clé absente de l'anglais
        retombe silencieusement sur le français."""
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("    en: {", 1)[0]
        en = js.split("    en: {", 1)[1]
        for cle in ("g_team", "g_back", "g_open", "g_search", "g_nores",
                    "g_profil", "g_noted_1", "g_noted_n", "g_no_act"):
            assert (cle + ":") in fr, "FR : " + cle
            assert (cle + ":") in en, "EN : " + cle

    def test_la_galerie_ne_retient_PAS_le_rendu_le_temps_d_une_lecture(self):
        """C'est la leçon de `/panel`, qui attendait 25 s puis annonçait une
        panne : le squelette part d'abord, les chiffres arrivent ensuite."""
        corps = _corps(_lire(JS), "async function ouvrirGalerie() {")
        assert corps.index("montrerEcran('galerie')") < corps.index("api('/mastery/galerie')")
