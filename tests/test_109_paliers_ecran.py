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
        assert "perf.marge && plausible(" in js, "le garde-fou doit être BRANCHÉ"

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

    def test_le_gabarit_ouvre_la_fenetre_du_calendrier(self):
        g = _lire(GABARIT)
        for ident in ("cv2-cal-win", "cv2-cal-close", "cv2-cal-body", "cv2-btn-cal"):
            assert ident in g, ident
        js = _lire(JS)
        # ⚠️ `editor.js` a montré ce que coûte un id câblé sans garde : une
        # TypeError interrompt TOUTE la suite de l'init.
        for ident in ("#cv2-cal-close", "#cv2-cal-body", "#cv2-btn-cal"):
            assert ident in js, ident


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
