# -*- coding: utf-8 -*-
"""L'ÉCRAN des paliers : le calendrier, la clôture en bloc, et les deux régimes.

Le moteur est tenu par `test_108` ; ici on garde ce que l'écran promet :

  • le calendrier montre TOUS les collaborateurs qu'on suit, pas seulement
    celui qui est ouvert — sinon un rendez-vous ne se voit qu'en ayant
    d'abord choisi la bonne personne, et on le manque ;
  • une session se clôt en UNE transaction : trois appels laisseraient une
    session « prévue » dont la moitié des paliers sont tranchés ;
  • une sortie MESURÉE n'a pas de note à saisir, une sortie sans norme garde
    la sienne — et les deux cohabitent dans la même fenêtre.
"""
import io
import json
import os
import re
from datetime import date, timedelta

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(RACINE, "static", "js", "competences_v2.js")
CSS = os.path.join(RACINE, "static", "competences.css")
SQL = os.path.join(RACINE, "tools", "db", "seed_competences.sql")
GABARIT = os.path.join(RACINE, "Code", "routes", "templates", "competences_view.html")


def _relief(js):
    """Le corps de `reliefSvg` — il se termine à la fonction suivante."""
    return js.split("  function reliefSvg(r) {", 1)[1].split("  // Le bilan dit", 1)[0]


def _lire(p):
    return io.open(p, encoding="utf-8").read()


# ⚠️ Ces cas relisent des SOURCES (JS, CSS, SQL, gabarit). L'arbre d'image est
# compilé en bytecode mais garde `static/` et les gabarits ; seul le dossier
# `tools/` en est retiré. Le cas qui lit le SQL se saute donc là-bas, comme la
# fixture `pulse_app` — un contrôle qui rougit toujours n'est plus lu.
SQL_ABSENT = not os.path.exists(SQL)


_N = [0]


@pytest.fixture
def bob(app, ids):
    """Bob, son développeur, son rôle, son activité et la sortie mesurée.

    ⚠️ Le décor est RECRÉÉ ici plutôt qu'importé de `test_108` : une fixture
    partagée entre deux fichiers ferait dépendre l'un de l'ordre de l'autre,
    et la base est commune à toute la suite. Les noms portent un compteur
    pour la même raison — les rôles sont COMMUNS à l'entreprise depuis le
    23/09, un nom fixe fait collision dès que deux cas tournent.
    """
    from Code.models.models import (Activities, Data, Link, Role, User, UserRole,
                                    activity_roles)
    from Code.security import hash_password
    _N[0] += 1
    n = _N[0]
    with app.app_context():
        dev = User(first_name="Dev", last_name="T109", email="dev.t109.%d@test" % n,
                   password=hash_password("Test1234!"), status="user")
        b = User(first_name="Bob", last_name="T108", email="bob.t109.%d@test" % n,
                 password=hash_password("Test1234!"), status="user")
        db.session.add_all([dev, b])
        db.session.commit()

        role = Role(name="T109 Rédacteur %d" % n, entity_id=ids["entity_id"])
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=b.id, role_id=role.id, manager_id=dev.id))

        act = Activities(name="T109 Documenter %d" % n, entity_id=ids["entity_id"])
        aval = Activities(name="T109 Aval %d" % n, entity_id=ids["entity_id"])
        db.session.add_all([act, aval])
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant",
            required_mastery_level=2))
        db.session.add(Link(entity_id=ids["entity_id"], source_activity_id=act.id,
                            target_activity_id=aval.id,
                            description="Documentation T109 %d" % n, type="flux"))
        db.session.commit()

        from Code.routes.qualify_outputs import get_activity_outputs
        sortie = get_activity_outputs(act.id)[0]
        sortie.norme_valeur, sortie.norme_unite, sortie.norme_sens = 48.0, "h", "moins"
        db.session.commit()
        info = {"dev_id": dev.id, "bob_id": b.id, "role_id": role.id,
                "activity_id": act.id, "data_id": sortie.id}
    yield info
    with app.app_context():
        from Code.models.models import PalierPerformance, SessionEvaluation
        # ⚠️ Objet par objet, jamais `delete(synchronize_session=False)` : la
        # session est partagée par toute la suite, et des objets morts y
        # ressortent trois fichiers plus loin, sur le commit d'une route sans
        # rapport (« 'NoneType' object has no attribute '__dict__' »).
        for m in (PalierPerformance, SessionEvaluation):
            for x in m.query.filter_by(user_id=info["bob_id"]).all():
                db.session.delete(x)
        db.session.commit()


@pytest.fixture
def comme_dev(auth_client, bob):
    """On agit en développeur de compétences de Bob — et on rend la session
    telle qu'on l'a trouvée : `auth_client` est partagé en portée session."""
    with auth_client.session_transaction() as sess:
        avant = sess.get("user_id")
        sess["user_id"] = bob["dev_id"]
    yield
    with auth_client.session_transaction() as sess:
        if avant is None:
            sess.pop("user_id", None)
        else:
            sess["user_id"] = avant


def _poser(client, bob, cible, jours, session_id=None):
    corps = {"user_id": bob["bob_id"], "data_id": bob["data_id"],
             "role_id": bob["role_id"], "cible": cible,
             "echeance": (date.today() + timedelta(days=jours)).isoformat()}
    if session_id:
        corps["session_id"] = session_id
    r = client.post("/paliers/palier", json=corps)
    assert r.status_code == 200, r.data
    # ⚠️ Le DERNIER palier, pas `palier_en_cours` : celui-là rend le PREMIER
    # encore ouvert, donc toujours le même quand on en pose deux de suite.
    return json.loads(r.data)["etat"]["paliers"][-1]["id"]


def _session(client, bob, jours, objet=None):
    r = client.post("/paliers/session", json={
        "user_id": bob["bob_id"], "role_id": bob["role_id"],
        "date_prevue": (date.today() + timedelta(days=jours)).isoformat(),
        "objet": objet})
    assert r.status_code == 200, r.data
    return json.loads(r.data)["session"]["id"]


class TestLeCalendrier:
    """Il ne se cadre PAS sur un collaborateur."""

    def test_il_porte_le_nom_et_le_role_de_chacun(self, auth_client, bob, comme_dev):
        sid = _session(auth_client, bob, 12, "Point de mi-parcours")
        _poser(auth_client, bob, 96, 12, sid)
        r = auth_client.get("/paliers/calendrier")
        assert r.status_code == 200
        d = json.loads(r.data)
        ligne = next(s for s in d["sessions"] if s["id"] == sid)
        # Sans le nom, une case de calendrier ne dit pas DE QUI il s'agit.
        assert ligne["nom"] == "Bob T108"
        assert ligne["role"]
        assert ligne["a_trancher"] == 1
        assert ligne["objet"] == "Point de mi-parcours"

    def test_une_echeance_depassee_est_en_retard_et_comptee(self, auth_client, bob, comme_dev):
        sid = _session(auth_client, bob, -4)
        _poser(auth_client, bob, 96, -4, sid)
        d = json.loads(auth_client.get("/paliers/calendrier").data)
        ligne = next(s for s in d["sessions"] if s["id"] == sid)
        assert ligne["en_retard"] is True
        assert d["compteurs"]["en_retard"] >= 1

    def test_une_session_TENUE_n_est_plus_en_retard(self, auth_client, bob, comme_dev):
        sid = _session(auth_client, bob, -4)
        pid = _poser(auth_client, bob, 96, -4, sid)
        auth_client.post("/paliers/session/%d/cloturer" % sid,
                         json={"mesures": [{"palier_id": pid, "mesure": 88}]})
        d = json.loads(auth_client.get("/paliers/calendrier").data)
        ligne = next(s for s in d["sessions"] if s["id"] == sid)
        assert ligne["statut"] == "tenue"
        assert ligne["en_retard"] is False, "une session tenue n'est pas en retard"

    def test_on_ne_voit_PAS_les_sessions_de_quelqu_un_qu_on_ne_suit_pas(
            self, app, auth_client, bob, comme_dev):
        """⚠️ Le calendrier est large, pas ouvert. Un développeur voit les
        rendez-vous de SES collaborateurs — pas ceux de toute l'entreprise."""
        from Code.models.models import Role, SessionEvaluation, User, UserRole
        from Code.security import hash_password
        sid_mien = _session(auth_client, bob, 9)
        with app.app_context():
            etranger = User(first_name="Zoe", last_name="T109",
                            email="zoe.t109@test", password=hash_password("Test1234!"),
                            status="user")
            db.session.add(etranger)
            db.session.commit()
            role = Role.query.get(bob["role_id"])
            db.session.add(UserRole(user_id=etranger.id, role_id=role.id))
            s = SessionEvaluation(user_id=etranger.id, role_id=role.id,
                                  date_prevue=date.today() + timedelta(days=9),
                                  statut="prevue")
            db.session.add(s)
            db.session.commit()
            sid_etranger, zid = s.id, etranger.id
        try:
            d = json.loads(auth_client.get("/paliers/calendrier").data)
            vus = {s["id"] for s in d["sessions"]}
            assert sid_mien in vus
            assert sid_etranger not in vus, "Zoe n'est rattachée à personne"
        finally:
            with app.app_context():
                for s in SessionEvaluation.query.filter_by(user_id=zid).all():
                    db.session.delete(s)
                for ur in UserRole.query.filter_by(user_id=zid).all():
                    db.session.delete(ur)
                u = User.query.get(zid)
                if u:
                    db.session.delete(u)
                db.session.commit()

    def test_le_cout_ne_grandit_pas_avec_le_nombre_de_sessions(self, auth_client, bob, comme_dev):
        """⚠️ Pas `peut_lire` dans une boucle : il relit l'utilisateur et compte
        ses rattachements à CHAQUE appel. Cinquante sessions feraient cent
        requêtes pour une page qui s'ouvre à chaque visite."""
        from sqlalchemy import event
        _session(auth_client, bob, 3)
        n = [0]

        def compter(*a, **k):
            n[0] += 1

        event.listen(db.engine, "before_cursor_execute", compter)
        try:
            auth_client.get("/paliers/calendrier")
            avec_une = n[0]
            for j in range(5, 11):
                _session(auth_client, bob, j)
            n[0] = 0
            auth_client.get("/paliers/calendrier")
            avec_sept = n[0]
        finally:
            event.remove(db.engine, "before_cursor_execute", compter)
        assert avec_sept <= avec_une, (avec_une, avec_sept)


class TestClotureEnBloc:

    def test_les_verdicts_se_calculent_et_la_session_passe_a_tenue(
            self, auth_client, bob, comme_dev):
        sid = _session(auth_client, bob, 0)
        p1 = _poser(auth_client, bob, 96, 0, sid)
        r = auth_client.post("/paliers/session/%d/cloturer" % sid, json={
            "mesures": [{"palier_id": p1, "mesure": 88, "preuve": "Deux relances"}],
            "note": "Le fond y est."})
        assert r.status_code == 200, r.data
        d = json.loads(r.data)
        assert d["session"]["statut"] == "tenue"
        assert d["verdicts"][0]["statut"] == "atteint"
        assert d["manques"] == []
        # Le niveau DÉDUIT revient avec le verdict : l'écran n'a pas à le
        # recalculer de son côté, et ne peut donc pas diverger.
        assert d["verdicts"][0]["niveau"] == 1

    def test_un_palier_manque_ressort_dans_manques(self, auth_client, bob, comme_dev):
        sid = _session(auth_client, bob, 0)
        p1 = _poser(auth_client, bob, 48, 0, sid)
        d = json.loads(auth_client.post("/paliers/session/%d/cloturer" % sid, json={
            "mesures": [{"palier_id": p1, "mesure": 70}]}).data)
        assert d["verdicts"][0]["statut"] == "manque"
        assert len(d["manques"]) == 1, "c'est lui qui ouvre l'analyse des savoirs"

    def test_on_ne_tranche_QUE_les_paliers_de_cette_session(self, auth_client, bob, comme_dev):
        """⚠️ Les identifiants viennent du navigateur."""
        from Code.models.models import PalierPerformance
        sid_a = _session(auth_client, bob, 0)
        sid_b = _session(auth_client, bob, 20)
        p_a = _poser(auth_client, bob, 96, 0, sid_a)
        p_b = _poser(auth_client, bob, 72, 20, sid_b)
        d = json.loads(auth_client.post("/paliers/session/%d/cloturer" % sid_a, json={
            "mesures": [{"palier_id": p_a, "mesure": 88},
                        {"palier_id": p_b, "mesure": 10}]}).data)
        assert [v["palier_id"] for v in d["verdicts"]] == [p_a]
        assert PalierPerformance.query.get(p_b).mesure_valeur is None

    def test_une_mesure_illisible_n_ecrit_RIEN(self, auth_client, bob, comme_dev):
        """Une transaction, ou rien : sinon la session reste à moitié tranchée
        et plus personne ne sait ce qui a été fait."""
        from Code.models.models import PalierPerformance, SessionEvaluation
        sid = _session(auth_client, bob, 0)
        p1 = _poser(auth_client, bob, 96, 0, sid)
        p2 = _poser(auth_client, bob, 72, 0, sid)
        r = auth_client.post("/paliers/session/%d/cloturer" % sid, json={
            "mesures": [{"palier_id": p1, "mesure": 88},
                        {"palier_id": p2, "mesure": "beaucoup"}]})
        assert r.status_code == 400
        db.session.rollback()
        assert SessionEvaluation.query.get(sid).statut == "prevue"
        assert PalierPerformance.query.get(p1).mesure_valeur is None

    def test_un_compte_qui_ne_suit_pas_ce_role_ne_cloture_pas(
            self, app, client, auth_client, bob, comme_dev):
        from Code.models.models import SessionEvaluation, User
        from Code.security import hash_password
        sid = _session(auth_client, bob, 0)
        p1 = _poser(auth_client, bob, 96, 0, sid)
        with app.app_context():
            tiers = User(first_name="Tiers", last_name="T109", email="tiers.t109@test",
                         password=hash_password("Test1234!"), status="user")
            db.session.add(tiers)
            db.session.commit()
            tid = tiers.id
        try:
            autre = app.test_client()
            with autre.session_transaction() as sess:
                sess["user_id"] = tid
            r = autre.post("/paliers/session/%d/cloturer" % sid,
                           json={"mesures": [{"palier_id": p1, "mesure": 10}]})
            assert r.status_code == 403
            assert SessionEvaluation.query.get(sid).statut == "prevue"
        finally:
            with app.app_context():
                u = User.query.get(tid)
                if u:
                    db.session.delete(u)
                db.session.commit()


class TestLeDetailDUneSession:

    def test_chaque_ligne_porte_sa_sortie_son_activite_et_son_sens(
            self, auth_client, bob, comme_dev):
        sid = _session(auth_client, bob, 5)
        _poser(auth_client, bob, 96, 5, sid)
        d = json.loads(auth_client.get("/paliers/session/%d/detail" % sid).data)
        ligne = d["paliers"][0]
        # Sans l'activité, on ne sait pas de quel travail on parle ; sans le
        # sens, « mieux » n'a pas de définition.
        assert ligne["activite"] and ligne["sortie"]
        assert ligne["sens"] == "moins"
        assert ligne["unite"] == "h"
        assert ligne["norme"] == 48.0
        assert d["session"]["nom"] == "Bob T108"


class TestLesDeuxRegimesCohabitent:
    """Une sortie porte une NORME, ou elle n'en porte pas. C'est le seul
    critère, et il décide de tout ce que l'écran affiche."""

    def test_le_dispatch_existe_et_passe_par_la_norme(self):
        js = _lire(JS)
        assert "function carteSortie(" in js
        assert "r.mesurable && r.performance" in js, \
            "c'est la NORME qui décide, pas la nature de la sortie"

    def test_une_sortie_mesuree_n_a_pas_de_note_a_saisir(self, auth_client, bob, comme_dev):
        """Le niveau vient du chiffre relevé en session. Une échelle 0→4 à
        côté dirait deux choses d'une seule."""
        sid = _session(auth_client, bob, 0)
        p1 = _poser(auth_client, bob, 48, 0, sid)
        auth_client.post("/paliers/session/%d/cloturer" % sid,
                         json={"mesures": [{"palier_id": p1, "mesure": 47}]})
        d = json.loads(auth_client.get(
            "/mastery/activity/%d/%d?role_id=%d"
            % (bob["bob_id"], bob["activity_id"], bob["role_id"])).data)
        r = d["results"][0]
        assert r["mesurable"] is True
        assert r["demonstrated_level"] == 2, "le niveau est DÉDUIT de la mesure"
        assert r["performance"]["qualifie"] is True
        js = _lire(JS)
        assert "const aSaisir = st.results.some(r => !r.mesurable);" in js, \
            "« Enregistrer » ne doit s'afficher que s'il y a quelque chose à saisir"

    def test_une_sortie_SANS_norme_garde_son_echelle(self, app, auth_client, bob, comme_dev):
        from Code.models.models import Data
        with app.app_context():
            d = Data.query.get(bob["data_id"])
            d.norme_valeur = d.norme_unite = d.norme_sens = None
            db.session.commit()
        r = json.loads(auth_client.get(
            "/mastery/activity/%d/%d?role_id=%d"
            % (bob["bob_id"], bob["activity_id"], bob["role_id"])).data)["results"][0]
        assert r["mesurable"] is False
        assert r["performance"] is None


class TestLAuDelaResteDansLeReel:
    """⚠️ « Un pas de plus que la norme » peut tomber HORS de ce que la
    grandeur permet : une norme de 2 jours avec un pas de 4 donne « −2 j »,
    un taux de 100 % donne « 120 % ». On ne l'affiche pas — et on n'invente
    pas non plus un autre seuil pour le remplacer."""

    def test_le_garde_fou_existe_et_borne_les_deux_sens(self):
        js = _lire(JS)
        assert "function plausible(" in js
        corps = js.split("function plausible(", 1)[1].split("\n  }", 1)[0]
        assert "return v > 0" in corps, "une durée négative n'existe pas"
        assert "100" in corps and "%" in corps, "un taux ne dépasse pas 100 %"
        # ⚠️ Il ne se branche plus sur `perf.marge` mais sur `perf.au_dela`,
        # le seuil que le serveur calcule — le rail n'en déduit plus aucun.
        assert "plausible(au, sens, n.unite)" in js, "le garde-fou doit être BRANCHÉ"

    def test_il_ne_touche_PAS_au_niveau_rendu_par_le_serveur(self, auth_client, bob, comme_dev):
        """Le garde-fou est un affichage. Le niveau, lui, reste celui du
        moteur : sinon deux implémentations d'un même verdict divergeraient."""
        from Code.paliers import niveau_depuis_mesure, pas_de_progression
        assert pas_de_progression([96, 72, 48], 48, "moins") == 24
        assert niveau_depuis_mesure(24, 48, "moins", 96, marge=24) == 3


class TestLesLibellesExistentDansLesDeuxLangues:

    def test_toute_cle_lue_par_l_ecran_est_dans_les_deux_catalogues(self):
        """⚠️ Une clé absente en EN ne lève RIEN : l'accesseur rend la clé
        elle-même, et l'écran anglais affiche « pal_atteint »."""
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        # ⚠️ Le catalogue écrit parfois DEUX clés sur une ligne : chercher
        # seulement en début de ligne en rendait 231 sur 300, et le contrôle
        # de parité ne portait alors que sur les deux tiers.
        cle = lambda bloc: set(re.findall(r"(?:^\s+|,\s+)([a-z0-9_]+):\s*['\"]", bloc, re.M))
        cles_fr, cles_en = cle(fr), cle(en)
        assert len(cles_fr) > 280, "le catalogue doit être garni (%d)" % len(cles_fr)
        assert cles_fr - cles_en == set(), "manquent en anglais"
        assert cles_en - cles_fr == set(), "manquent en français"

        # Les clés que le nouvel écran lit vraiment, prises dans le code.
        lues = set(re.findall(r"\bTv?\('((?:pal|ses|ev)_[a-z0-9_]+)'", js))
        assert len(lues) > 60, "on doit en relever beaucoup (%d)" % len(lues)
        assert lues - cles_fr == set(), "lues mais jamais déclarées"



class TestLeStyleSuitLaPageEtPasLaRacine:

    def test_aucune_regle_neuve_ne_lit_les_derives_gris(self):
        """⚠️ `--pg-accent-soft` et ses trois frères sont déclarés sur `:root`,
        où `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS
        sur toute l'application. Les mélanges s'écrivent DANS la règle."""
        css = _lire(CSS)
        section = css.split("LES PALIERS DE PERFORMANCE", 1)[1]
        regles = [l for l in section.splitlines()
                  if not l.strip().startswith(("/*", "*", "--")) and "⚠️" not in l]
        for derive in ("--pg-accent-soft", "--pg-accent-softer",
                       "--pg-accent-border", "--pg-accent-glow"):
            fautives = [l for l in regles if derive in l]
            assert fautives == [], (derive, fautives[:2])

    def test_les_deux_boutons_gardent_le_rapport_inverse(self):
        """Le vocabulaire décidé sur la page Temps : l'action pose une
        pastille PASTEL sur un fond vif, le réglage une pastille VIVE sur un
        fond clair. Deux formes qui se distinguent sans se disputer."""
        css = _lire(CSS)
        assert ".pal-b--doux .pal-b-ic { background: var(--pg-accent); color: #fff; }" in css
        assert ".pal-b--prim .pal-b-ic { background: rgba(255, 255, 255, .22)" in css
        assert ".pal-b--prim::after" in css, "l'éclat qui traverse au survol"
        assert "prefers-reduced-motion" in css.split("LES PALIERS DE PERFORMANCE", 1)[1]


@pytest.mark.skipif(SQL_ABSENT, reason="tools/ est retiré de l'arbre d'image")
class TestLeSemisSQL:
    """Il part chez un client, collé dans l'éditeur de Neon."""

    def test_il_refuse_de_doubler_un_semis_deja_fait(self):
        """⚠️ Rejoué, il empilerait une seconde progression sur la première —
        six marches au lieu de trois. Il refuse plutôt que de doubler."""
        sql = _lire(SQL)
        assert "IF NOT purger AND EXISTS (SELECT 1 FROM paliers_performance" in sql
        assert "RAISE EXCEPTION" in sql.split("Déjà semé", 1)[1][:900]

    def test_il_s_arrete_si_personne_ne_tient_de_role(self):
        """Sans titulaire il n'y a personne à évaluer — et on ne fabrique pas
        de collaborateurs pour remplir un écran."""
        sql = _lire(SQL)
        bloc = sql.split("Qui tient un rôle sur cette carto", 1)[1][:900]
        assert "RAISE EXCEPTION" in bloc

    def test_il_laisse_des_sorties_SANS_norme(self):
        sql = _lire(SQL)
        assert "CONTINUE WHEN (i_act % 5) IN (0, 4);" in sql, \
            "deux activités sur cinq restent jugées à la main"

    def test_les_quatre_parcours_tournent_sur_un_compteur_de_paires(self):
        """⚠️ Sur la somme des deux rangs, avec deux personnes et deux sorties,
        cette somme ne prend que trois valeurs sur quatre — et c'est
        « qualifié · avancé » qui n'apparaissait jamais."""
        sql = _lire(SQL)
        assert "v_scenar := i_paire % 4;" in sql
        assert "i_paire := i_paire + 1;" in sql

class TestEvaluerEstUnePage:
    """⚠️ Le tiroir fait 720 px, et `body.pg` porte `zoom: .8` : **576 px
    réels** pour une échelle de paliers, un graphe et un historique. Tout y
    était comprimé. L'évaluation est une PAGE ; le tiroir garde les deux
    dialogues courts — configurer, diagnostiquer."""

    def test_le_gabarit_porte_les_deux_ecrans_pleine_largeur(self):
        g = _lire(GABARIT)
        assert 'id="cv2-ecran-eval"' in g
        assert 'id="cv2-ecran-seance"' in g
        # ⚠️ HORS de `.cv2-layout` : dedans, ils partageraient la largeur avec
        # la barre des collaborateurs, et les trois colonnes n'y tiendraient pas.
        avant, apres = g.split('id="cv2-ecran-eval"', 1)
        assert avant.count("</div>") > avant.count('<div class="cv2-layout"'), \
            "l'écran doit être sorti de .cv2-layout"

    def test_un_role_ouvre_DIRECTEMENT_la_page(self):
        """⚠️ L'écran « liste des activités du rôle » ne décidait de rien : on
        y cliquait « Évaluer » sur une ligne, et c'est tout. La colonne de
        gauche de la page fait la même chose sans aller-retour."""
        js = _lire(JS)
        assert "function ouvrirEvaluation(" in js
        assert "function showEvaluation(" not in js
        corps = js.split("async function ouvrirRole(r) {", 1)[1].split("\n  }", 1)[0]
        assert "ouvrirEvaluation(" in corps, "le rôle ouvre la page"
        assert "montrerEcran('role')" not in js
        for mort in ("function ligneActivite(", "function metaActivite(",
                     "function celluleTech("):
            assert mort not in js, mort

    def test_la_page_efface_la_barre_laterale_et_le_bandeau(self):
        js = _lire(JS)
        corps = js.split("function pleineLargeur(", 1)[1].split("\n  }", 1)[0]
        assert ".cv2-layout" in corps and "page-banner" in corps
        css = _lire(CSS)
        assert "body.a-cv2-page .pg-container" in css, \
            "le conteneur est plafonné à 1200 px — 960 réels au zoom .8"

    def test_la_page_ne_fait_qu_UN_aller_retour(self):
        """Le relief se dessine depuis les paliers que `/mastery/activity`
        porte déjà. `/paliers/historique` n'en rendait qu'un sous-ensemble (les
        seuls évalués) : une requête dont personne ne lit la réponse, c'est du
        temps pris à l'ouverture de la page."""
        js = _lire(JS)
        bloc = js.split("async function ouvrirEvaluation(", 1)[1][:900]
        assert "/mastery/activity/" in bloc
        assert "/paliers/historique/" not in bloc
        assert "Promise.all" not in bloc
        assert "state.histo" not in js, "plus de série à tenir en mémoire"

    def test_le_tiroir_ne_porte_plus_que_les_dialogues(self):
        js = _lire(JS)
        assert "function ouvrirDialogue(" in js
        # Le diagnostic l'ouvre lui-même, et son retour le REFERME : il n'y a
        # plus d'évaluation à rebâtir derrière.
        diag = js.split("async function showDiagnostic() {", 1)[1][:400]
        assert "ouvrirDialogue(" in diag
        assert "label: T('back'), on: closeDrawer" in js


class TestUnSeulEndroitPoseUneMesure:
    """Le calendrier dit QUAND et QUOI ; la séance TRANCHE. Deux écrans de
    saisie finiraient par ne plus dire la même chose du même geste."""

    def test_le_calendrier_ne_saisit_plus_rien(self):
        js = _lire(JS)
        detail = js.split("function rendreDetail(d) {", 1)[1].split("\n  }\n", 1)[0]
        assert "data-m" not in detail, "plus de champ de mesure dans le calendrier"
        assert "data-tenir" in detail, "il mène à la séance"
        assert "function cloturer(sid, z)" not in js, "la clôture vit dans la séance"

    def test_la_seance_recalcule_le_verdict_mais_ne_l_ecrit_pas(self):
        """⚠️ UNE comparaison, pour montrer d'avance ce que le serveur dira —
        pas une seconde règle. C'est `trancher()` qui écrit le verdict."""
        js = _lire(JS)
        corps = js.split("function verdictLocal(p) {", 1)[1].split("\n  }", 1)[0]
        assert "SENS_MOINS ? v <= p.cible : v >= p.cible" in corps
        # La clôture envoie les mesures, jamais un statut.
        clore = js.split("async function cloturerSeance() {", 1)[1].split("\n  }", 1)[0]
        assert "mesures" in clore and "statut" not in clore

    def test_le_detail_porte_la_progression_entiere(self, auth_client, bob, comme_dev):
        """Sans elle, l'écran de séance pose un chiffre sans montrer d'où il
        vient ni s'il reste une marche après."""
        sid = _session(auth_client, bob, 3)
        _poser(auth_client, bob, 96, -20)
        _poser(auth_client, bob, 72, 3, sid)
        d = json.loads(auth_client.get("/paliers/session/%d/detail" % sid).data)
        prog = d["paliers"][0]["progression"]
        assert prog is not None
        assert len(prog["paliers"]) == 2, "les DEUX marches, pas seulement celle du jour"
        assert prog["norme"]["valeur"] == 48.0

    def test_la_saisie_ne_rerend_pas_la_page_a_chaque_frappe(self):
        """⚠️ Réécrire la page à chaque touche ferait perdre le curseur du
        champ qu'on est en train de taper — le piège déjà rencontré sur les
        cartes du plan de formation."""
        js = _lire(JS)
        corps = js.split("    const lire = () => {", 1)[1].split("    };", 1)[0]
        assert "renderSeance()" not in corps
        assert "rendreVerdict(p)" in corps and "rendreFile()" in corps


class TestCeQuiEstEvalueNeDitPlusJamaisEvaluee:
    """⚠️ Une sortie MESURÉE n'écrit aucune `CompetencyEvaluation` : son
    niveau vient du palier tranché en séance. L'activité s'affichait donc
    « jamais évaluée » juste à côté de son niveau tout neuf."""

    def test_la_date_suit_le_dernier_palier_tranche(self, app, auth_client, bob, comme_dev):
        # dashboard_rows lit session["lang"] : hors requete, il leve.
        from Code.routes.mastery import dashboard_rows
        ctx = app.test_request_context(); ctx.push()
        sid = _session(auth_client, bob, 0)
        pid = _poser(auth_client, bob, 96, 0, sid)
        avant = [r for r in dashboard_rows(bob["bob_id"], bob["role_id"])
                 if r["activity_id"] == bob["activity_id"]][0]
        assert avant["last_evaluation"] is None
        auth_client.post("/paliers/session/%d/cloturer" % sid,
                         json={"mesures": [{"palier_id": pid, "mesure": 88}]})
        apres = [r for r in dashboard_rows(bob["bob_id"], bob["role_id"])
                 if r["activity_id"] == bob["activity_id"]][0]
        ctx.pop()
        assert apres["last_evaluation"] is not None
        assert apres["demonstrated_level"] == 1

    def test_le_cout_ne_grandit_pas_avec_le_nombre_d_activites(self, app, auth_client, bob, comme_dev):
        """Une requête pour TOUTES les activités du rôle, pas une par activité."""
        from sqlalchemy import event
        from Code.models.models import Activities, activity_roles
        from Code.routes.mastery import dashboard_rows
        n = [0]

        def compter(*a, **k):
            n[0] += 1

        ctx = app.test_request_context(); ctx.push()
        dashboard_rows(bob["bob_id"], bob["role_id"])
        event.listen(db.engine, "before_cursor_execute", compter)
        try:
            n[0] = 0
            dashboard_rows(bob["bob_id"], bob["role_id"])
            avec_une = n[0]
        finally:
            event.remove(db.engine, "before_cursor_execute", compter)
        neuves = []
        with app.app_context():
            for i in range(3):
                a = Activities(name="T109 extra %d-%d" % (_N[0], i),
                               entity_id=db.session.get(Activities, bob["activity_id"]).entity_id)
                db.session.add(a)
                db.session.commit()
                db.session.execute(activity_roles.insert().values(
                    activity_id=a.id, role_id=bob["role_id"], status="Garant"))
                neuves.append(a.id)
            db.session.commit()
        try:
            event.listen(db.engine, "before_cursor_execute", compter)
            n[0] = 0
            dashboard_rows(bob["bob_id"], bob["role_id"])
            avec_quatre = n[0]
            event.remove(db.engine, "before_cursor_execute", compter)
            # Trois activités de plus coûtent leurs propres lectures, mais la
            # recherche des paliers, elle, reste à UNE requête.
            assert avec_quatre - avec_une <= 3 * 12, (avec_une, avec_quatre)
        finally:
            ctx.pop()
            with app.app_context():
                db.session.execute(activity_roles.delete().where(
                    activity_roles.c.activity_id.in_(neuves)))
                for i in neuves:
                    a = db.session.get(Activities, i)
                    if a:
                        db.session.delete(a)
                db.session.commit()


class TestLePlurielNeSeDevinePas:
    """⚠️ Les clés de pluriel ne suivent pas toutes la même convention dans
    ce catalogue — `_1`/`_n` ici, `_pl` là, la forme nue ailleurs. Une clé
    absente ne lève RIEN : elle s'affiche telle quelle (« ev_nb_act_n »
    relevé à l'écran)."""

    def test_l_aide_essaie_les_trois_conventions(self):
        js = _lire(JS)
        corps = js.split("  function nf(c, n, u) {", 1)[1].split("\n  }", 1)[0]
        assert "'_1'" in corps and "'_n'" in corps and "'_pl'" in corps
        assert "T(x) !== x" in corps, "on ne retient que la clé qui EXISTE"

    def test_toute_cle_construite_par_nf_existe(self):
        import re as _re
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        cle = lambda b: set(_re.findall(r"(?:^\s+|,\s+)([a-z0-9_]+):\s*['\"]", b, _re.M))
        cles = cle(fr)
        bases = set(_re.findall(r"\bnf\('([a-z0-9_]+)'", js))
        assert len(bases) >= 4, "on doit en relever plusieurs (%d)" % len(bases)
        for b in bases:
            formes = {b, b + "_1", b + "_n", b + "_pl"} & cles
            assert len(formes) >= 2, (b, formes)

class TestLeCalendrierEstUnePage:

    def test_le_gabarit_porte_les_quatre_ecrans(self):
        """⚠️ Enfermé dans une pop-up, le calendrier avait 1180 px — 944
        réels au zoom .8 — pour un mois ET la séance choisie. C'est une vue,
        pas un dialogue."""
        g = _lire(GABARIT)
        for ident in ("cv2-ecran-synthese", "cv2-ecran-eval",
                      "cv2-ecran-seance", "cv2-ecran-cal"):
            assert 'id="%s"' % ident in g, ident
        for parti in ("cv2-cal-win", "cv2-ecran-role", "cv2-btn-cal",
                      "cv2-btn-plan", "cv2-fil-role", "cv2-lignes"):
            assert parti not in g, parti
        js = _lire(JS)
        # ⚠️ `editor.js` a montré ce que coûte un id câblé sans garde : une
        # TypeError interrompt TOUTE la suite de l'init. `#cv2-retour` a
        # justement survécu une version de trop et cassé le démarrage.
        for mort in ("#cv2-retour", "#cv2-btn-cal", "#cv2-btn-plan",
                     "#cv2-fil-role", "#cv2-cal-close"):
            assert mort not in js, mort

    def test_il_se_rend_dans_son_ecran_et_pas_dans_une_fenetre(self):
        js = _lire(JS)
        corps = js.split("function rendreCal() {", 1)[1].split("\n  }", 1)[0]
        assert "#cv2-ecran-cal" in corps
        assert "cv2-cal-body" not in corps
        # Il sait d'où l'on vient : le retour ne doit pas tomber au hasard.
        assert "cal.retour" in js

    def test_une_seule_porte_mene_a_la_seance(self):
        js = _lire(JS)
        detail = js.split("function rendreDetail(d) {", 1)[1].split("\n  }\n", 1)[0]
        assert "data-tenir" in detail
        assert "data-m" not in detail


class TestLeProfilSeDessineDesQuUneCibleExiste:
    """⚠️ Le radar ne traçait QUE les activités évaluées : un collaborateur
    qu'on vient d'affecter n'avait aucun profil. On trace le REQUIS de toutes
    celles qui en portent un, et le démontré se remplit par-dessus."""

    def test_un_axe_existe_des_qu_il_y_a_QUELQUE_CHOSE_a_y_porter(self):
        """⚠️ Filtré sur le seul requis, le profil de quelqu'un dont aucun
        rôle n'a fixé de cible restait VIDE — en affichant « le profil se
        dessine à partir de trois activités » alors qu'il en avait trois."""
        js = _lire(JS)
        corps = js.split("  function renderProfil(d) {", 1)[1].split("\n  }", 1)[0]
        assert "|| !estNul(a.demonstrated_level));" in corps
        assert "const axes = avecCible;" not in js
        # Et le message dit la vraie condition.
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        assert "trois activités évaluées ou dotées d'un niveau attendu" in fr

    def test_le_requis_sans_cible_ne_se_ferme_pas_a_zero(self):
        """Un axe dont aucun rôle n'a fixé la cible dirait « rien n'est exigé
        ici » — la même distinction que pour le démontré (NULL ≠ 0)."""
        js = _lire(JS)
        corps = js.split("  function radarSVG(axes) {", 1)[1].split("\n  }", 1)[0]
        assert "const coucheReq = couche('required_level'" in corps
        assert "cv2-r-req-part" in corps
        assert "poly(req)" not in corps, "plus de polygone fermé sur le requis"
        assert ".cv2-r-req-part {" in _lire(CSS)

    def test_la_surface_demontree_ne_se_ferme_que_si_tout_est_mesure(self):
        """Là où il n'y a pas de mesure, il n'y a pas de trait : fermer le
        polygone sur un sommet absent le ferait passer par zéro, c'est-à-dire
        par « non démontré » — ce que tout le module distingue."""
        js = _lire(JS)
        corps = js.split("const tout = axes.every(", 1)[1][:900]
        assert "cv2-r-dem-part" in corps, "les morceaux de polyligne"
        assert "polyline" in corps
        css = _lire(CSS)
        assert ".cv2-r-dem-part" in css

    def test_un_axe_sans_mesure_n_a_pas_de_point(self):
        js = _lire(JS)
        corps = js.split("const points = axes.map((a, i) => {", 1)[1][:300]
        assert "estNul(a.demonstrated_level)) return ''" in corps


class TestLesExplicationsSontDerriereUnI:
    """Écrites en clair, elles occupaient la place de ce qu'on vient lire."""

    def test_les_deux_paves_ont_disparu_de_la_page(self):
        js = _lire(JS)
        assert "gras(T('ev_min_de'))" not in js, "la règle du minimum passe en « i »"
        assert "ev-carte--leg" not in js, "le pavé de l'échelle 0→4 aussi"
        assert "function boutonInfo(" in js
        assert "boutonInfo(T('ev_min_t')" in js
        assert "boutonInfo(T('pal_echelle_t')" in js

    def test_le_quatre_s_explique_enfin(self):
        """« jamais déduite, elle se pose » ne voulait rien dire."""
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        ligne = [l for l in fr.splitlines() if "pal_comment_4:" in l][0]
        assert "Expertise" in ligne and "main" in ligne

    def test_la_bulle_se_pose_sur_son_bouton_malgre_le_zoom(self):
        """⚠️ `body.pg` porte `zoom: .8` : un enfant du body en
        `position: fixed` voit ses coordonnées MULTIPLIÉES par ce zoom, alors
        que `getBoundingClientRect()` les rend déjà en pixels d'écran.
        Quatrième fois que ce piège mord dans cette application."""
        js = _lire(JS)
        corps = js.split("  function brancherInfo(", 1)[1].split("\n  }", 1)[0]
        assert "getComputedStyle(document.body).zoom" in corps
        assert "/ z + 'px'" in corps


class TestLEnTeteNeCouvrePlusLaNavigation:

    def test_il_sort_du_sticky_global(self):
        """⚠️ `header { position: sticky; top: 0; z-index: 30 }` vaut pour
        TOUTE la feuille. Mes en-têtes de page SONT des `<header>` : même
        z-index que la barre de navigation, et comme ils viennent après dans
        le document, ils passaient par-dessus elle."""
        css = _lire(CSS)
        assert "header { position: sticky; top: 0; z-index: 30; }" in css
        # ⚠️ La règle de dégagement est celle qui porte la DÉCLARATION sur une
        # ligne, pas l'ouverture multi-lignes de la première passe de style.
        regle = [l for l in css.splitlines()
                 if l.startswith(".ev-tete, .sq-tete {") and "z-index" in l]
        assert regle, "les deux en-têtes doivent se dégager de cette règle"
        assert "position: relative" in regle[0] and "z-index: 1;" in regle[0]

    def test_une_seule_largeur_pour_toute_la_page(self):
        css = _lire(CSS)
        assert "body.pg.page--competences .pg-container { max-width: 1760px; }" in css


class TestLAccueilNEstPlusNu:

    def test_les_quatre_compteurs_s_affichent_meme_a_zero(self):
        """Trois compteurs absents sur quatre laissaient la page nue, et
        « 0 en écart » est une information, pas un vide."""
        js = _lire(JS)
        assert "if (onFiltre && !compte[cle] && state.filtre !== cle) return;" in js

    def test_la_vue_d_ensemble_porte_les_prochaines_seances(self):
        js = _lire(JS)
        g = _lire(GABARIT)
        assert 'id="cv2-seances"' in g
        assert "function rendreSeances(" in js
        corps = js.split("async function rendreSeances() {", 1)[1].split("\n  }", 1)[0]
        assert "x.user_id === state.cible" in corps, "les siennes, pas celles de tous"
        assert "x.statut === 'prevue'" in corps


class TestLeMotEvaluerRemplaceTrancher:
    """« Trancher » est un mot de métier ; le bouton doit dire ce qu'il fait."""

    def test_aucun_libelle_visible_ne_dit_plus_trancher(self):
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        # ⚠️ On ne lit que la VALEUR — le nom de clé `pal_trancher` reste, seul
        # le libellé affiché devait changer — et on cherche le MOT entier :
        # « un palier franchi » contient « ranch ».
        import re as _re
        motifs = {"fr": _re.compile(r"[Tt]ranch(er|é|és|e|ez)\b"),
                  "en": _re.compile(r"[Ss]ettl(e|ed|ing)\b")}
        for bloc, langue in ((fr, "fr"), (en, "en")):
            fautifs = [l.strip() for l in bloc.splitlines()
                       if ":" in l and motifs[langue].search(l.split(":", 1)[1])]
            assert fautifs == [], fautifs
        assert "pal_trancher: 'Évaluer ce palier'" in js

class TestLEnregistrementTrouveSesCartes:
    """⚠️⚠️ Le défaut le plus grave de la passe : « ça dit que c'est
    enregistré, mais en rechargeant, rien ». `saveEvaluation` cherchait ses
    cartes dans `#cv2-drawer-body` — le TIROIR, d'où l'évaluation est partie
    le 14/10. Il n'en trouvait AUCUNE, la boucle ne tournait pas, et le
    « Enregistré » tombait quand même. Mesuré au banc : 2 cartes dans
    `#ev-centre`, 0 dans le tiroir."""

    def test_il_lit_la_colonne_du_milieu_et_pas_le_tiroir(self):
        js = _lire(JS)
        corps = js.split("  async function saveEvaluation() {", 1)[1].split("\n  }", 1)[0]
        assert "#ev-centre .cv2-res" in corps
        assert "cv2-drawer-body" not in corps

    def test_il_n_annonce_pas_un_succes_sans_rien_ecrire(self):
        """Un enregistrement qui ne trouve rien à écrire ne dit plus
        « Enregistré » : c'est ce silence qui a coûté les notes."""
        js = _lire(JS)
        corps = js.split("  async function saveEvaluation() {", 1)[1].split("\n  }", 1)[0]
        assert "if (!cards.length)" in corps
        assert "ecrites" in corps
        assert "toast(ecrites ? T('saved') : T('save_rien'));" in corps


class TestLeCalendrierFiltreEtPoseLesDates:

    def test_l_appartenance_a_une_tuile_vient_du_SERVEUR(self, auth_client, bob, comme_dev):
        """⚠️ Les quatre prédicats (en retard, cette semaine, ce mois, tenues
        cette année) sont écrits UNE fois, dans la boucle qui incrémente les
        compteurs. Refaits en JS, le chiffre de la tuile et les cases qu'elle
        met en avant finiraient par désigner deux ensembles.

        ⚠️ Écrit sur le COMPORTEMENT, pas en relisant la source : un test qui
        lit un `.py` passe ici et rougit à CHAQUE exécution sur l'instance,
        dont l'arbre est compilé en bytecode.
        """
        en_retard = _session(auth_client, bob, -9)
        a_venir = _session(auth_client, bob, 300)
        d = json.loads(auth_client.get("/paliers/calendrier").data)
        par_id = {s["id"]: s for s in d["sessions"]}

        assert "en_retard" in par_id[en_retard]["tuiles"]
        assert par_id[a_venir]["tuiles"] == [], "une séance lointaine n'est dans aucune tuile"

        # Le compteur d'une tuile EST le nombre de séances qu'elle marque :
        # c'est l'invariant qui empêche le chiffre et les cases de diverger.
        for cle, n in d["compteurs"].items():
            marquees = [s for s in d["sessions"] if cle in s["tuiles"]]
            assert len(marquees) == n, "%s : %d marquées pour %d annoncées" % (
                cle, len(marquees), n)

        js = _lire(JS)
        assert "(ses.tuiles || []).indexOf(cle) >= 0" in js
        # Aucun des quatre prédicats n'est reconstruit côté navigateur.
        assert "getDay() === 1" not in js

    def test_les_tuiles_sont_des_boutons_qui_filtrent(self, auth_client):
        js = _lire(JS)
        corps = js.split("  function tuileCal(cle, lbl, teinte) {", 1)[1].split("\n  }", 1)[0]
        assert "<button" in corps and 'data-f="${cle}"' in corps
        assert "aria-pressed" in corps
        # Recliquer la tuile allumée l'éteint : sans ça on ne revient pas à tout.
        f = js.split("  function filtrerCal(cle) {", 1)[1].split("\n  }", 1)[0]
        assert "cal.filtre === cle ? null : cle" in f

    def test_le_filtre_met_en_avant_sans_jamais_masquer(self):
        """Une case qui disparaîtrait laisserait un trou dans le mois : on ne
        saurait plus quel jour on lit."""
        css = _lire(CSS)
        assert ".cal-case.est-eteint" in css
        assert "display: none" not in css.split(".cal-case.est-eteint", 1)[1][:120]

    def test_une_case_du_mois_pose_la_date_du_formulaire(self):
        js = _lire(JS)
        assert "function poserJour(iso)" in js
        corps = js.split("  function poserJour(iso) {", 1)[1].split("\n  }", 1)[0]
        assert "champ.value = iso" in corps and "cal.vise = iso" in corps
        # ⚠️ Le formulaire ouvert l'emporte sur le chargement d'une session :
        # sinon cliquer un jour déjà occupé quitterait la planification.
        m = js.split("z.querySelectorAll('[data-jour]')", 1)[1][:420]
        assert "#cal-detail [data-d]" in m and "poserJour" in m

    def test_seul_qui_peut_planifier_voit_une_case_cliquable(self):
        js = _lire(JS)
        assert "const planif = !!(state.estDev && state.roleId && state.cible);" in js
        assert "planif\n          ? `<button" in js or "planif ? `<button" in js


class TestLeNiveauAttenduQuitteLEvaluation:
    """Trois objets dans un même écran — l'activité à gauche, ses sorties au
    milieu, la cible du RÔLE à droite — et on ne savait plus lequel on notait.
    Le niveau attendu se règle là où les rôles se regardent."""

    def test_il_n_est_plus_dans_la_colonne_de_droite(self):
        js = _lire(JS)
        assert "function cibleRequise(" not in js
        assert "ev_attendu" not in js
        corps = js.split("  function remplirContexte(st) {", 1)[1].split("\n  }\n", 1)[0]
        assert "cv2-cible" not in corps

    def test_il_se_regle_dans_le_detail_d_un_role(self):
        js = _lire(JS)
        corps = js.split("  function barresRole(role) {", 1)[1].split("\n  }\n", 1)[0]
        assert "cv2-bar-req" in corps and "data-act" in corps
        assert "const peutRegler = jeSuisLeDev();" in js
        # ⚠️ Le réglage recharge la synthèse ENTIÈRE : la couleur, le compteur
        # « en écart » et le radar en dépendent, et les redresser à la main
        # donnerait une seconde règle pour un seul verdict.
        h = js.split("hote.querySelectorAll('.cv2-bar-req [data-lv]')", 1)[1][:1100]
        assert "'/mastery/required'" in h and "await chargerSynthese();" in h

    def test_la_phrase_de_la_technicite_a_disparu(self):
        js = _lire(JS)
        assert "ev_tech_d" not in js
        assert "contexte technique, pas la ma" not in js


class TestLesDeuxColonnesSeDistinguent:

    def test_chacune_porte_son_numero_et_ce_qu_elle_montre(self):
        js = _lire(JS)
        assert '<span class="num">1</span>' in js and '<span class="num">2</span>' in js
        assert "T('ev_col_sor')" in js and "T('ev_col_sor_d')" in js
        # ⚠️ `remplirCentre` VIDE `#ev-centre` : un en-tête écrit dans le
        # gabarit de la page serait effacé au premier remplissage.
        corps = js.split("  function remplirCentre(st) {", 1)[1][:400]
        assert "ev-centre-h" in corps

    def test_le_gabarit_de_la_page_ne_le_redit_pas(self):
        js = _lire(JS)
        sk = js.split('<main class="ev-centre" id="ev-centre"', 1)[1][:80]
        assert "ev-centre-h" not in sk


class TestLEvolutionSeFermeParLeBas:
    """Une fois l'historique déplié, le bouton qui a OUVERT la section se
    retrouve en plein milieu : il faut le chercher pour refermer."""

    def test_un_bouton_ferme_la_section_depuis_son_pied(self):
        js = _lire(JS)
        corps = js.split("  function basculerHisto(card, r) {", 1)[1].split("\n  }", 1)[0]
        assert "pal-evo-fin" in corps
        assert "fa-chevron-up" in corps
        # ⚠️ En DERNIER enfant : `.pal-form` vient après l'historique, et une
        # marche posée pendant la lecture glisserait un formulaire SOUS lui.
        assert "card.appendChild(bas);" in corps

    def test_il_part_quand_la_section_se_referme(self):
        js = _lire(JS)
        corps = js.split("  function basculerHisto(card, r) {", 1)[1].split("\n  }", 1)[0]
        avant = corps.split("card.dataset.evo = '';", 1)[0]
        assert ".pal-evo-fin" in avant, "le repli doit le retirer"

    def test_il_a_son_style(self):
        css = _lire(CSS)
        assert ".pal-evo-fin {" in css


class TestLesLibellesNeufsExistentDansLesDeuxLangues:

    def test_les_dix_cles_posees_sont_dans_les_deux_catalogues(self):
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        for k in ("ev_col_sor", "ev_col_sor_d", "save_rien", "p_regler_req",
                  "ses_f_on", "ses_f_off", "ses_f_tout", "ses_f_actif",
                  "ses_f_actif_n", "ses_clic_jour", "ses_poser_le"):
            assert ("%s:" % k) in fr, "manque en FR : %s" % k
            assert ("%s:" % k) in en, "manque en EN : %s" % k

    def test_le_pluriel_du_bandeau_ne_se_devine_pas(self):
        """« 1 session(s) » n'est pas une tournure, c'est un aveu."""
        js = _lire(JS)
        assert "session(s)" not in js
        assert "nf('ses_f_actif'" in js

import os as _os
_SRC_LISIBLE = _os.path.exists("Code/paliers.py")


class TestDepasserLaNormeFaitMonterLeNiveau:
    """⚠️⚠️ Le défaut signalé par le client, et son effet domino.

    « La norme est fixée à 95 %, pourtant une marche à 98 % mesurée à 99 %
    nous laisse à 2. » Exact. `pas_de_progression` ne regardait que les
    marches EN DEÇÀ de la norme : sur 67 → 81 → 95 → 98 il rendait 14 et
    plaçait l'au-delà à **109 %** — une valeur qui n'existe pas sur un
    pourcentage. Le niveau d'une activité étant le MINIMUM de ses sorties et
    celui d'un rôle le minimum de ses activités, l'erreur redescendait
    jusqu'au verdict « apte / pas apte ».
    """

    def test_une_marche_posee_au_dela_EST_le_seuil(self):
        from Code.paliers import seuil_au_dela
        # Le cas du client, au chiffre près.
        assert seuil_au_dela([67, 81, 95, 98], 95, "plus") == 98
        # Et dans l'autre sens, où « mieux » veut dire « moins ».
        assert seuil_au_dela([20, 14, 10, 6], 10, "moins") == 6

    def test_la_PREMIERE_marche_au_dela_fait_la_frontiere(self):
        """Les suivantes vont plus loin encore ; elles ne déplacent pas le
        moment où l'on passe de « tenu » à « dépassé »."""
        from Code.paliers import seuil_au_dela
        assert seuil_au_dela([95, 98, 99], 95, "plus") == 98

    def test_sans_marche_au_dela_on_retombe_sur_le_pas(self):
        """La règle d'avant reste la bonne quand personne n'a rien posé plus
        loin : 96 → 72 → 48 donne un pas de 24, donc un au-delà à 24."""
        from Code.paliers import seuil_au_dela
        assert seuil_au_dela([96, 72, 48], 48, "moins") == 24
        assert seuil_au_dela([48], 48, "moins") is None

    def test_le_niveau_monte_a_3_quand_la_marche_au_dela_est_franchie(self):
        from Code.paliers import niveau_depuis_mesure
        # ⚠️ Le seuil EXPLICITE l'emporte sur celui qu'on déduit d'un pas :
        # sans cela, `marge=14` aurait placé l'au-delà à 109 % et rendu 2.
        assert niveau_depuis_mesure(99, 95, "plus", 67, marge=14, au_dela=98) == 3
        assert niveau_depuis_mesure(96, 95, "plus", 67, marge=14, au_dela=98) == 2

    def test_le_domino_va_jusqu_au_ROLE(self, app, auth_client, bob, comme_dev):
        """Une sortie qui passe à 3 fait passer l'activité à 3, et le rôle
        cesse d'être « en écart » quand il exigeait 3."""
        from Code.models.models import Data, activity_roles
        from Code.extensions import db

        # Le niveau attendu du rôle : 3.
        r = auth_client.post("/mastery/required", json={
            "activity_id": bob["activity_id"], "role_id": bob["role_id"],
            "required_mastery_level": 3})
        assert r.status_code == 200, r.data

        with app.app_context():
            d = db.session.get(Data, bob["data_id"])
            d.norme_valeur, d.norme_unite, d.norme_sens = 95, "%", "plus"
            db.session.commit()

        # 67 → 81 → 95 (la norme) → 98 (au-delà), chacune mesurée au-dessus.
        for cible, mesure in ((67, 70.4), (81, 85.1), (95, 97), (98, 99)):
            pid = _poser(auth_client, bob, cible, 10)
            rr = auth_client.post("/paliers/palier/%d/trancher" % pid,
                                  json={"mesure": mesure, "role_id": bob["role_id"]})
            assert rr.status_code == 200, rr.data

        etat = json.loads(auth_client.get(
            "/mastery/activity/%d/%d?role_id=%d"
            % (bob["bob_id"], bob["activity_id"], bob["role_id"])).data)
        sortie = etat["results"][0]
        assert sortie["performance"]["au_dela"] == 98
        assert sortie["demonstrated_level"] == 3, "la sortie a dépassé la norme"
        assert etat["global_level"] == 3, "l'activité suit sa sortie"
        assert etat["gap"] == 0, "le rôle exigeait 3 : il n'est plus en écart"


class TestLeRailEstUneLIGNE:
    """⚠️ « La courbe UI casse. » Le drapeau de norme était un `inline-block`
    avec sa marge, et les marches sans drapeau un bloc vide de 22 px : la
    marche flaguée descendait de ~5 px et le rail formait un décroché."""

    def test_toutes_les_marches_partagent_la_meme_bande_de_titre(self):
        js = _lire(JS)
        assert "pal-drapeau-vide" not in js, "plus de bloc vide à la hauteur devinée"
        assert '<div class="pal-marque">${marque}</div>' in js
        css = _lire(CSS)
        regle = [l for l in css.splitlines() if l.strip().startswith("height: 26px;")
                 and "align-items: center" in l]
        assert regle, ".pal-marque doit porter une hauteur FIXE"
        assert ".pal-drapeau { margin-bottom: 0; }" in css

    def test_un_seul_drapeau_de_norme(self):
        """`mieux()` répond « atteint » : TOUTE marche à partir de la norme le
        portait, et 95 comme 98 s'annonçaient « norme de l'entreprise »."""
        js = _lire(JS)
        corps = js.split("  function construireRail(perf) {", 1)[1].split("\n  }", 1)[0]
        assert "let norme_vue = false;" in corps
        assert "estNorme = atteintNorme && !norme_vue" in corps
        assert "pal_audela_tag" in js, "la marche au-delà porte sa propre marque"

    def test_le_seuil_dessine_vient_du_SERVEUR(self):
        """Le rail traçait l'au-delà depuis `marge` ; il aurait montré 109 %
        quand le niveau se jouait sur 98 %."""
        js = _lire(JS)
        corps = js.split("  function construireRail(perf) {", 1)[1].split("\n  }", 1)[0]
        assert "perf.au_dela" in corps
        assert "n.valeur + perf.marge" not in corps
        src = _lire("Code/paliers.py") if _SRC_LISIBLE else ""
        if src:
            assert '"au_dela": au_dela,' in src

    def test_la_mesure_se_lit_autant_que_la_cible(self):
        js = _lire(JS)
        assert "pal_mesure_k" in js
        css = _lire(CSS)
        # ⚠️ `.pal-pas .pal-m` est déclarée deux fois : c'est la DERNIÈRE
        # qui gagne, et c'est donc elle qu'il faut lire.
        bloc = css.rsplit(".pal-pas .pal-m {", 1)[1].split("}", 1)[0]
        assert "border-radius: 999px" in bloc, "une pastille, pas une ligne grise"
        assert ".pal-pas .pal-m b { font-size: 15px" in css


class TestOnPeutDonnerUneNormeApresCoup:
    """⚠️ Boucle fermée : une sortie née sans norme ne pouvait PLUS jamais en
    recevoir. On notait 0→4 à la main, on revenait, et c'était tout — aucun
    écran ne proposait de poser le standard de l'entreprise."""

    def test_la_carte_a_la_main_porte_la_porte_vers_les_paliers(self):
        js = _lire(JS)
        corps = js.split("  function resultCard(r, requis) {", 1)[1].split("\n  }\n", 1)[0]
        # ⚠️ `data-poser-norme>` et pas `data-poser-norme` : le sélecteur de la
        # liaison (`[data-poser-norme]`) vit dans le même corps, et il suffisait
        # à faire passer le contrôle alors que le BOUTON avait disparu.
        assert "data-poser-norme>" in corps, "le bouton lui-même doit porter l'attribut"
        assert "pal_definir_norme" in corps
        # ⚠️ Et c'est la PREMIÈRE MESURE qui s'ouvre, pas la seule norme :
        # poser la norme bascule la sortie en régime mesuré, et la note à la
        # main qu'on lit juste au-dessus cesse alors d'être saisissable.
        assert "formPremiere(card.querySelector('.pal-form'), r)" in js
        assert "formNorme(card.querySelector('.pal-form'), r)" not in js

    def test_poser_la_norme_fait_basculer_la_sortie(self, app, auth_client, bob, comme_dev):
        """La même route sert aux deux : une sortie jugée à la main devient
        mesurable dès qu'elle porte un chiffre attendu."""
        # ⚠️ Le décor de `bob` naît AVEC une norme : on la retire d'abord,
        # sinon on part du cas qu'on veut justement atteindre.
        r0 = auth_client.post("/paliers/norme/%d" % bob["data_id"], json={"valeur": None})
        assert r0.status_code == 200, r0.data
        avant = json.loads(auth_client.get(
            "/mastery/activity/%d/%d?role_id=%d"
            % (bob["bob_id"], bob["activity_id"], bob["role_id"])).data)
        assert avant["results"][0]["mesurable"] is False

        r = auth_client.post("/paliers/norme/%d" % bob["data_id"],
                             json={"valeur": 48, "unite": "h", "sens": "moins"})
        assert r.status_code == 200, r.data

        apres = json.loads(auth_client.get(
            "/mastery/activity/%d/%d?role_id=%d"
            % (bob["bob_id"], bob["activity_id"], bob["role_id"])).data)
        assert apres["results"][0]["mesurable"] is True
        assert apres["results"][0]["performance"]["norme"]["valeur"] == 48


class TestMoinsDePhrasesPosees:

    def test_la_colonne_1_ne_decrit_plus_ce_que_l_ecran_fait(self):
        js = _lire(JS)
        assert "ev_col_act_d" not in js

    def test_les_deux_explications_attendent_derriere_un_i(self):
        js = _lire(JS)
        assert "boutonInfo(T('ev_col_sor'), T('ev_col_sor_d'))" in js
        assert "boutonInfo(T('ses_verdicts_t'), T('ses_verdicts_calc'))" in js

    def test_le_verdict_s_explique_au_lieu_de_s_affirmer(self):
        """« Les verdicts se calculent, ils ne se cochent pas » ne disait ni
        ce qu'est un verdict, ni ce qu'on attend du lecteur."""
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        ligne = [l for l in fr.splitlines() if "ses_verdicts_calc:" in l][0]
        assert len(ligne) > 160, "la phrase doit expliquer le geste et sa conséquence"
        assert "mesur" in ligne and "cible" in ligne

    def test_l_aide_du_calendrier_se_range_a_cote_du_champ(self):
        js = _lire(JS)
        assert '<div class="cal-d-date">' in js
        css = _lire(CSS)
        assert ".cal-d-date { display: flex;" in css


class TestLesDeuxNotesSeTiennent:
    """« Cette section n'est vraiment pas très belle. » Deux rectangles gris
    empilés, chacun avec son petit en-tête : on ne voyait pas que c'est UNE
    décision regardée de deux côtés."""

    def test_elles_partagent_un_seul_cadre(self):
        js = _lire(JS)
        assert '<div class="cv2-notes">${officielle}${auto}</div>' in js
        css = _lire(CSS)
        assert ".cv2-notes .cv2-nt + .cv2-nt { border-top:" in css
        assert ".cv2-notes .cv2-nt--off { border-left-color: var(--pg-accent); }" in css

    def test_la_preuve_est_un_bouton_pas_un_lien_souligne(self):
        js = _lire(JS)
        assert 'class="cv2-preuve-btn' in js and "fa-paperclip" in js
        css = _lire(CSS)
        bloc = css.rsplit("\n.cv2-preuve-btn {", 1)[1].split("}", 1)[0]
        assert "border-radius: 999px" in bloc and "border: 1px solid" in bloc


class TestLeRelief:
    """⚠️ « Visuellement tout est à la même hauteur alors que le niveau
    augmente. » Le rail posait les marches côte à côte : rien n'y montrait la
    montée. Le relief les porte sur deux axes RÉELS — le temps en abscisse, la
    valeur en ordonnée — et il remplace le rail dans la carte d'une sortie
    mesurée. Le rail reste à la SÉANCE, où la question est « quelle marche
    suis-je en train de mesurer », pas « comment cela a progressé ».
    """

    def test_la_carte_mesuree_porte_le_relief_et_non_le_rail(self):
        js = _lire(JS)
        corps = js.split("  function carteMesuree(r) {", 1)[1].split("\n  }", 1)[0]
        assert "reliefSvg(r)" in corps and "bilanRelief(perf)" in corps
        assert "railHtml(" not in corps, "le rail ne vit plus dans la carte"
        # …mais il vit toujours à la séance : c'est une AUTRE question.
        assert 'class="sq-rail">${railHtml(' in js

    def test_l_axe_vertical_est_ordonne_par_MERITE(self):
        """Une durée compte à rebours, un taux à l'endroit : dans les deux cas
        MONTER veut dire progresser. Sans cela, une sortie où l'on gagne du
        temps dessinerait une courbe qui descend — et la moitié des cartes se
        liraient à l'envers de l'autre moitié."""
        js = _lire(JS)
        corps = _relief(js)
        assert "const merite = v => (sens === SENS_MOINS ? -v : v);" in corps
        assert "merite(v) - mmin" in corps

    def test_le_trace_est_DROIT_entre_deux_mesures(self):
        """Rien n'a été relevé entre deux séances : une courbe lissée
        inventerait ce qu'on ne sait pas."""
        js = _lire(JS)
        corps = _relief(js)
        assert "<polyline points=" in corps
        for courbe in (" C ", " Q ", " S ", "bezier"):
            assert courbe not in corps, "aucune courbe entre deux points : %s" % courbe

    def test_ce_qui_n_est_pas_mesure_est_creux_et_pointille(self):
        js = _lire(JS)
        corps = _relief(js)
        assert 'stroke-dasharray="2 5"' in corps, "la projection est en pointillé"
        assert 'stroke-dasharray="2.6 2.4"' in corps, "l'anneau non mesuré est creux"

    def test_un_FANTOME_n_est_jamais_une_mesure(self):
        """⚠️ `construireRail` recopie la dernière mesure sur le seuil
        d'au-delà pour que le RAIL le montre franchi. Dans le relief, cette
        copie dessinait un SECOND point au même relevé, à une date où personne
        n'a rien mesuré, et le tracé partait à plat vers la droite. Mesuré au
        banc : deux « 0,8 % » pour trois séances."""
        js = _lire(JS)
        corps = _relief(js)
        assert "const estMes = s => !s.fantome" in corps
        assert "s.fantome ? (s.echeance || null)" in corps, \
            "un fantôme n'emprunte pas la date de la mesure qu'il recopie"

    def test_un_SEUL_norme_franchie(self):
        """Même piège que le drapeau du rail : `mieux()` répond « atteint »,
        donc toute marche à partir de la norme se disait franchie."""
        js = _lire(JS)
        corps = _relief(js)
        assert "const vert = s.statut === 'atteint' && yN !== null && s.estNorme;" in corps

    def test_les_boites_sont_testees_avec_une_MARGE(self):
        """Les boîtes sont ESTIMÉES — rien n'est dans le document pendant la
        construction du SVG. Sans marge, deux étiquettes que le calcul croit
        voisines se touchent au rendu : mesuré au banc, « 8 essais » et
        « 9,2 essais » se recouvraient de 1,7 px."""
        js = _lire(JS)
        assert "const MARGE_X = 3, MARGE_Y = 2;" in js
        corps = js.split("  function placeur() {", 1)[1].split("\n  }", 1)[0]
        assert "b.x2 + MARGE_X <= o.x1" in corps and "b.y2 + MARGE_Y <= o.y1" in corps

    def test_la_gouttiere_de_gauche_s_adapte_a_l_unite(self):
        """⚠️ Une unité longue débordait du cadre : « 14.4 essais » sortait
        24 px à GAUCHE du viewBox, donc invisible."""
        js = _lire(JS)
        corps = _relief(js)
        assert "G.X0 = Math.max(62, Math.round(gut) + 16);" in corps
        assert "G.PX0 = Math.max(RL.PX0, G.X0 + 100);" in corps

    def test_aucune_etiquette_ne_sort_du_cadre_a_droite(self):
        """L'écart minimal tient les étiquettes entre elles, pas contre les
        BORDS. « target 2 j · to be measured », centré sur la dernière marche,
        sortait de 19 px — trouvé en relisant l'écran ANGLAIS, où les libellés
        sont plus longs."""
        js = _lire(JS)
        assert "function glisser(b) {" in js
        corps = _relief(js)
        assert "let dx = glisser(b);" in corps
        assert "P.poser(bouger(b, dx))" in corps
        # Glisser, oui — mais pas au point de désigner la mauvaise marche.
        assert "Math.abs(dx) > Math.max(26, dmin * 0.4)" in corps

    def test_l_ordre_de_pose_decide_de_ce_qui_disparait(self):
        """Quand la place manque, ce qui saute est la décoration — jamais le
        chiffre relevé. La norme et les mesures sont FORCÉES, la mention de
        zone passe en dernier et par `poser()`."""
        js = _lire(JS)
        corps = _relief(js)
        i_norme = corps.index("P.forcer(boiteTexte(G.X0 - 14, yN + 4")
        i_zone = corps.index("rel_zone")
        assert i_norme < i_zone, "la norme se pose avant la mention de zone"
        assert "P.forcer(o.b);" in corps, "le chiffre relevé ne se jette pas"
        assert "P.poser(b)" in corps[i_zone - 400:i_zone + 400], \
            "la mention de zone cède la place"

    def test_c_est_une_CIBLE_qui_cede_la_place_jamais_un_releve(self):
        """L'ordre de pose des étiquettes du bas n'est pas l'ordre des
        marches. Relevé au banc sur une sortie dont la marche 4 avait été
        tranchée avant la 3 : « cible 4 j · 15/10 » — la mesure la plus
        RÉCENTE — sautait au profit d'une échéance à venir."""
        js = _lire(JS)
        corps = _relief(js)
        assert "const ordreBas = mes.slice().reverse()" in corps
        assert "ordreBas.forEach(i => {" in corps
        assert "rail.forEach((s, i) => {\n      if (mode.bas === 'rare'" not in corps

    def test_sans_aucune_mesure_le_relief_est_COURT(self):
        """Il n'y a rien à tracer : le relief plein laissait trois cents pixels
        de vide sous une norme et une cible."""
        js = _lire(JS)
        corps = _relief(js)
        assert "? { H: 300," in corps and ": { H: 198," in corps
        assert 'viewBox="0 0 828 \' + G.H + \'"' in corps

    def test_le_bilan_remplace_dix_lignes_d_historique(self):
        js = _lire(JS)
        corps = js.split("  function bilanRelief(perf) {", 1)[1].split("\n  }", 1)[0]
        for cle in ("rel_tenues", "rel_repris", "rel_gagne", "rel_suivi", "rel_detail"):
            assert cle in corps, cle
        # ⚠️ Un gain se dit autrement selon le sens : on « reprend » du temps,
        # on « gagne » des points.
        assert "sens === SENS_MOINS ? 'rel_repris' : 'rel_gagne'" in corps

    def test_le_lien_du_detail_est_cable_AVEC_une_garde(self):
        """Il n'existe pas sur une sortie sans palier ni norme : un câblage
        sans garde couperait toute la suite de l'init de la carte — c'est le
        piège du contrat DOM de l'éditeur de carto."""
        js = _lire(JS)
        assert "if (q('[data-evol]')) q('[data-evol]').onclick" in js
        assert "function basculerHisto(card, r) {" in js
        assert "function blocGraphe(" not in js, "le relief EST le graphe"

    def test_les_libelles_du_relief_sont_dans_les_deux_catalogues(self):
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        for k in ("rel_bas", "rel_a_mesurer", "rel_seuil", "rel_norme", "rel_zone",
                  "rel_franchie", "rel_tenues", "rel_repris", "rel_gagne",
                  "rel_suivi", "rel_detail", "rel_detail_off", "rel_aria"):
            assert ("%s:" % k) in fr, "manque en FR : %s" % k
            assert ("%s:" % k) in en, "manque en EN : %s" % k

    def test_les_polices_sont_ecrites_sur_chaque_texte(self):
        """⚠️ Un SVG n'hérite PAS des polices de la feuille."""
        js = _lire(JS)
        assert "const FD = 'Fraunces, Georgia, serif';" in js
        assert 'font-family="\' + FD + \'"' in _relief(js)

    def test_le_css_du_relief_n_appelle_pas_le_gris_de_la_racine(self):
        """`--pg-accent-soft` et ses frères sont déclarés sur `:root`, où
        `--pg-accent` vaut encore le gris par défaut."""
        css = _lire(CSS)
        bloc = css.split("LE RELIEF, et le détail", 1)[1].split("\n.pal-histo {", 1)[0]
        for mort in ("--pg-accent-soft", "--pg-accent-softer",
                     "--pg-accent-border", "--pg-accent-glow"):
            assert mort not in bloc, mort


class TestLaPremiereMesureSePoseEnUneFois:
    """⚠️ Le trou signalé : on réglait la norme, la carte basculait en régime
    mesuré, et il n'existait plus aucun endroit où saisir ce qu'on avait
    relevé. La sortie restait « Non évalué » pendant que l'activité affichait
    encore l'ancienne note à la main. Une norme sans mesure ne dit rien de
    personne : les deux se posent ENSEMBLE.
    """

    def _sortie_nue(self, bob):
        """La sortie de Bob, débarrassée de sa norme et de ses paliers."""
        from Code.models.models import Data, PalierPerformance
        for p in PalierPerformance.query.filter_by(
                user_id=bob["bob_id"], data_id=bob["data_id"]).all():
            db.session.delete(p)
        d = db.session.get(Data, bob["data_id"])
        d.norme_valeur = d.norme_unite = d.norme_sens = None
        db.session.commit()
        return d

    def test_norme_et_mesure_dans_UNE_transaction(self, auth_client, bob, comme_dev):
        from Code.models.models import Data
        self._sortie_nue(bob)
        r = auth_client.post("/paliers/premiere", json={
            "user_id": bob["bob_id"], "data_id": bob["data_id"],
            "role_id": bob["role_id"], "valeur": 48, "unite": "h",
            "sens": "moins", "mesure": 60})
        assert r.status_code == 200, r.data
        j = json.loads(r.data)
        assert j["norme_deja_posee"] is False
        d = db.session.get(Data, bob["data_id"])
        assert d.norme_valeur == 48 and d.norme_unite == "h"
        # ⚠️ La première lecture dit OÙ ON PART : sa cible est la mesure
        # elle-même. Lui donner la norme pour cible rendrait « 0 · Non
        # démontré » à quelqu'un qui fait le travail.
        assert len(j["etat"]["paliers"]) == 1
        assert j["etat"]["paliers"][0]["cible"] == 60
        assert j["etat"]["paliers"][0]["mesure"] == 60
        assert j["etat"]["niveau"] == 1, "il produit, pas encore au niveau attendu"

    def test_une_mesure_qui_tient_deja_la_norme_vaut_2_pas_3(
            self, auth_client, bob, comme_dev):
        """⚠️ Avec la mesure pour cible, un premier relevé meilleur que la
        norme fabriquait un « palier au-delà » et se décernait 3 : 40 h pour
        une norme de 48 h rendait « Maîtrise étendue » dès le premier jour,
        là où le même chiffre vaut 2 par le chemin normal. Dépasser la norme
        est une marche qu'on DÉCIDE de poser."""
        self._sortie_nue(bob)
        r = auth_client.post("/paliers/premiere", json={
            "user_id": bob["bob_id"], "data_id": bob["data_id"],
            "role_id": bob["role_id"], "valeur": 48, "unite": "h",
            "sens": "moins", "mesure": 40})
        j = json.loads(r.data)
        assert j["etat"]["niveau"] == 2
        assert j["etat"]["paliers"][0]["cible"] == 48, "la cible s'arrête à la norme"
        assert j["etat"]["paliers"][0]["mesure"] == 40

    def test_la_norme_DEJA_posee_ne_se_redemande_pas(self, auth_client, bob, comme_dev):
        """Elle vit sur la sortie, pas sur la personne : qui prend un rôle
        déjà tenu ailleurs en hérite."""
        from Code.models.models import Data, PalierPerformance
        for p in PalierPerformance.query.filter_by(
                user_id=bob["bob_id"], data_id=bob["data_id"]).all():
            db.session.delete(p)
        db.session.commit()
        d = db.session.get(Data, bob["data_id"])
        assert d.norme_valeur is not None, "le décor pose déjà la norme"
        avant = d.norme_valeur
        r = auth_client.post("/paliers/premiere", json={
            "user_id": bob["bob_id"], "data_id": bob["data_id"],
            "role_id": bob["role_id"], "mesure": 70,
            "valeur": 999})          # ignorée : elle existe déjà
        assert r.status_code == 200, r.data
        assert json.loads(r.data)["norme_deja_posee"] is True
        assert db.session.get(Data, bob["data_id"]).norme_valeur == avant

    def test_sans_mesure_rien_n_est_ecrit(self, auth_client, bob, comme_dev):
        """Une norme écrite sans sa mesure laisserait exactement l'écran
        qu'on vient de corriger."""
        from Code.models.models import Data
        self._sortie_nue(bob)
        r = auth_client.post("/paliers/premiere", json={
            "user_id": bob["bob_id"], "data_id": bob["data_id"],
            "role_id": bob["role_id"], "valeur": 48, "sens": "moins"})
        assert r.status_code == 400
        assert json.loads(r.data)["error"] == "invalid_measure"
        db.session.expire_all()
        assert db.session.get(Data, bob["data_id"]).norme_valeur is None

    def test_le_role_est_obligatoire(self, auth_client, bob, comme_dev):
        r = auth_client.post("/paliers/premiere", json={
            "user_id": bob["bob_id"], "data_id": bob["data_id"], "mesure": 60})
        assert r.status_code == 400
        assert json.loads(r.data)["reason"] == "role_required"

    def test_un_compte_qui_ne_suit_pas_ce_role_ne_mesure_pas(self, auth_client, bob):
        from Code.models.models import User
        tiers = User(first_name="Tiers", last_name="Premiere",
                     email="tiers.premiere@test.local", status="user")
        tiers.password = "x"
        db.session.add(tiers)
        db.session.commit()
        with auth_client.session_transaction() as sess:
            avant = sess.get("user_id")
            sess["user_id"] = tiers.id
        try:
            r = auth_client.post("/paliers/premiere", json={
                "user_id": bob["bob_id"], "data_id": bob["data_id"],
                "role_id": bob["role_id"], "mesure": 60})
            assert r.status_code == 403, r.data
        finally:
            with auth_client.session_transaction() as sess:
                sess["user_id"] = avant
            db.session.delete(db.session.get(User, tiers.id))
            db.session.commit()


class TestLEcranPoseLesTroisElements:

    def test_le_formulaire_demande_les_trois(self):
        js = _lire(JS)
        corps = js.split("  function formPremiere(zone, r) {", 1)[1].split("\n  }", 1)[0]
        assert "/paliers/premiere" in corps
        assert "pal_mesure_q" in corps, "ce qu'on a relevé"
        assert "pal_norme_deja" in corps, "la norme déjà posée se rappelle"
        assert "pal_niveau_suivra" in corps, "le niveau se montre AVANT de valider"

    def test_l_apercu_du_niveau_n_est_PAS_une_seconde_regle(self):
        """Avec une seule marche il n'y a que deux issues. C'est le serveur
        qui tranche : l'écran montre d'avance, il ne décide pas."""
        js = _lire(JS)
        corps = js.split("  function formPremiere(zone, r) {", 1)[1].split("\n  }", 1)[0]
        assert "const lvl = mieux(m, v, sens) ? 2 : 1;" in corps
        assert "niveau_depuis_mesure" not in js, "la règle reste au serveur"

    def test_une_sortie_sans_palier_propose_la_premiere_mesure(self):
        js = _lire(JS)
        corps = js.split("  function carteMesuree(r) {", 1)[1].split("\n  }", 1)[0]
        assert "const vierge = !(perf.paliers || []).length;" in corps
        assert "data-premiere" in corps
        # ⚠️ Et tant que rien n'est mesuré, c'est la note posée à la main qui
        # se lit — la carte disait « Non évalué » pendant que l'activité
        # affichait encore 4.
        assert "const lu = expert ? 4 : (estNul(niv) ? perf.niveau_pose : niv);" in corps
        assert "pal_niveau_pose" in corps
        # ⚠️ Et dans l'AUTRE sens : l'expertise posée est le niveau qui
        # compte, la déduction plafonnant à 3. La carte affichait
        # « 1 · En acquisition » pendant que l'activité lisait 4.
        assert "pal_exp_mesure" in corps, "le niveau mesuré reste lisible à côté"

    def test_l_expertise_se_pose_depuis_la_carte(self):
        js = _lire(JS)
        assert "async function poserExpertise(r, oui) {" in js
        corps = js.split("  async function poserExpertise(r, oui) {", 1)[1].split("\n  }", 1)[0]
        assert "mastery_level: oui ? 4 : null" in corps
        assert "data-exp" in js

    def test_l_unite_se_choisit_dans_une_liste(self):
        """%, jours et heures reviennent à chaque sortie : les retaper est une
        corvée, et deux orthographes de la même grandeur se liraient comme
        deux unités."""
        js = _lire(JS)
        assert "const UNITES = ['%', 'j', 'h'];" in js
        assert "function champUnite(courante) {" in js
        # Le champ libre reste, pour tout le reste.
        assert "pal_unite_autre" in js
        for f in ("formNorme", "formPremiere"):
            corps = js.split("  function %s(zone, r) {" % f, 1)[1].split("\n  }", 1)[0]
            assert "champUnite(" in corps, f
        css = _lire(CSS)
        assert ".pal-unite {" in css

    def test_les_libelles_de_la_premiere_mesure_sont_dans_les_deux_langues(self):
        js = _lire(JS)
        fr = js.split("    fr: {", 1)[1].split("\n    },", 1)[0]
        en = js.split("    en: {", 1)[1].split("\n    },", 1)[0]
        for k in ("pal_premiere", "pal_premiere_d", "pal_premiere_ok",
                  "pal_norme_deja", "pal_mesure_q", "pal_mesure_manque",
                  "pal_niveau_suivra", "pal_niveau_pose", "pal_unite_autre",
                  "pal_u_pct", "pal_u_j", "pal_u_h", "pal_exp_poser",
                  "pal_exp_retirer", "pal_exp_posee", "pal_exp_d",
                  "pal_exp_mesure", "rel_tenues_1", "rel_suivi_1",
                  "pal_exp_ok", "pal_exp_off"):
            assert ("%s:" % k) in fr, "manque en FR : %s" % k
            assert ("%s:" % k) in en, "manque en EN : %s" % k
