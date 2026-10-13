# -*- coding: utf-8 -*-
"""Page Temps — la refonte : on arrive, on choisit, on saisit.

Mesure d'avant, qui a decide de la refonte : quatre onglets cote a cote
(quatre modeles mentaux sans rien qui les relie), vingt-six champs dans
l'onglet Role pour six chiffres dont deux que rien ne distinguait, tout a
0,0 h a l'arrivee, 1180 px utilises sur 1920, et les analyses enregistrees
isolees en bas de chaque onglet.
"""
import io
import json
import os

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(chemin):
    return io.open(os.path.join(RACINE, chemin), encoding="utf-8").read()


def _tdb(client):
    r = client.get("/temps/api/tableau_de_bord")
    assert r.status_code == 200, r.data
    d = json.loads(r.data)
    assert d["ok"], d
    return d


class TestLaPageOuvreSurCeQuOnSait:
    """Elle s'ouvrait sur un formulaire vierge a 0,0 h : ce qui ressemble a un
    resultat vide, et qui ne disait ni ce qui avait ete mesure ni ce qui
    restait a mesurer."""

    def test_l_ecran_d_accueil_est_celui_qui_s_affiche(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert 'id="tm-accueil" class="tm-ecran is-actif"' in g
        # Les deux autres sont dans le document, mais pas actifs.
        for ecran in ("tm-choix", "tm-travail"):
            assert ('id="%s" class="tm-ecran"' % ecran) in g, ecran

    def test_il_n_y_a_plus_d_onglets(self):
        """Le coeur du probleme : quatre analyses cote a cote, sans mode
        d'emploi, et un vocabulaire different dans chacune."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert 'class="subtabs"' not in g
        assert 'data-subtab=' not in g
        js = _lire("static/js/time.js")
        assert "$$('.subtab')" not in js

    def test_les_analyses_enregistrees_vivent_sur_l_accueil(self):
        """Elles etaient en bas de CHAQUE onglet : le travail deja fait ne se
        voyait qu'en entrant dans la saisie."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        accueil = g[g.index('id="tm-accueil"'):g.index('id="tm-choix"')]
        for cible in ('id="project-list"', 'id="activity-list"',
                      'id="role-list"', 'id="tm-faiblesse-list"'):
            assert cible in accueil, cible


class TestLesQuatrePortes:
    """Un mot (« Projet », « Rôle »…) ne dit pas quand s'en servir."""

    @pytest.mark.parametrize("quoi", ["projet", "activite", "role", "faiblesse"])
    def test_chaque_porte_dit_QUAND_et_donne_un_exemple(self, quoi):
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert ('data-analyse="%s"' % quoi) in g
        assert ("time.tm_quand_%s" % quoi) in g
        assert ("time.tm_ex_%s" % quoi) in g

    @pytest.mark.parametrize("lang", ["fr", "en"])
    def test_et_ces_phrases_existent_dans_les_deux_langues(self, lang):
        from Code.translations import t
        for quoi in ("projet", "activite", "role", "faiblesse"):
            for forme in ("quand", "ex"):
                cle = "time.tm_%s_%s" % (forme, quoi)
                assert t(cle, lang=lang) != cle, cle


class TestLeResultatEstColleALaSaisie:
    """On remplissait jusqu'a vingt-six champs sans jamais voir un chiffre, et
    il fallait defiler jusqu'en bas pour en trouver six."""

    def test_un_bloc_de_resultat_par_analyse(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        for quoi in ("projet", "activite", "role", "faiblesse"):
            assert ('data-pour="%s"' % quoi) in g, quoi

    def test_le_panneau_porte_les_ids_que_le_JS_ecrit(self):
        """⚠️ `updateKpi` ecrit par ID : deplacer un compteur ne casse rien
        TANT QUE l'id survit. C'est ce qui rend la refonte sure — et c'est
        exactement ce qu'un renommage distrait emporterait."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        for ident in ("kpi-proj-charge", "kpi-proj-nb", "kpi-proj-dur", "kpi-proj-del",
                      "act-total", "tm-act-an", "tm-act-mois",
                      "kpi-role-annual", "kpi-role-monthly",
                      "kpi-role-d", "kpi-role-w", "kpi-role-m", "kpi-role-a",
                      "tm-fw-an", "tm-fw-mois", "tm-fw-occ"):
            assert ('id="%s"' % ident) in g, ident

    def test_le_bouton_calculer_de_la_faiblesse_n_existe_plus(self):
        """Le resultat ne se merite plus par un clic : il vit pendant la
        saisie. La formule, elle, reste celle du SERVEUR — appelee en differe,
        pas reecrite dans le navigateur."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "btn-fw-calc" not in g
        js = _lire("static/js/time.js")
        assert "function calculFaiblesse" in js
        bloc = js[js.index("function calculFaiblesse"):][:420]
        assert "setTimeout" in bloc and "sendWeakness(false, true)" in bloc


class TestUneSeuleRegleDAnnualisation:
    """Elle etait ecrite dans `_role_summary` ET dans le navigateur ; le
    tableau de bord en aurait fait une troisieme."""

    def test_les_quatre_recurrences(self, app):
        from Code.routes.time_view import annuel_minutes
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 47}
        assert annuel_minutes(10, "journalier", p) == 10 * 5 * 47
        assert annuel_minutes(10, "hebdomadaire", p) == 10 * 47
        assert annuel_minutes(10, "mensuel", p) == 120
        assert annuel_minutes(10, "annuel", p) == 10

    def test_une_recurrence_inconnue_ne_multiplie_rien(self, app):
        """Plutot que de choisir un facteur au hasard : une valeur inattendue
        doit se voir dans le resultat, pas s'y fondre."""
        from Code.routes.time_view import annuel_minutes
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 47}
        assert annuel_minutes(10, "trimestriel", p) == 10

    def test_le_resume_d_un_role_rend_EXACTEMENT_la_meme_chose(self, app):
        """⚠️ On confronte les deux implementations sur des chiffres, pas sur
        le texte de la source : `Code/**.py` est compile dans l'image, un test
        qui le relit y echoue a chaque execution (le piege de `repet_image`).
        """
        from types import SimpleNamespace
        from Code.routes.time_view import _role_summary, annuel_minutes, get_calendar_params

        lignes = [SimpleNamespace(activity_id=None, duration_minutes=30,
                                  recurrence="journalier", frequency=2),
                  SimpleNamespace(activity_id=None, duration_minutes=45,
                                  recurrence="hebdomadaire", frequency=1),
                  SimpleNamespace(activity_id=None, duration_minutes=90,
                                  recurrence="mensuel", frequency=3),
                  SimpleNamespace(activity_id=None, duration_minutes=120,
                                  recurrence="annuel", frequency=1)]
        resume = _role_summary(SimpleNamespace(lines=lignes))
        p = get_calendar_params()
        attendu = (annuel_minutes(60, "journalier", p)
                   + annuel_minutes(45, "hebdomadaire", p)
                   + annuel_minutes(270, "mensuel", p)
                   + annuel_minutes(120, "annuel", p))
        assert resume["annual_minutes"] == pytest.approx(attendu)
        assert resume["monthly_minutes"] == pytest.approx(attendu / 12.0)

    def test_et_le_navigateur_applique_les_MEMES_facteurs(self):
        """⚠️ Deux implementations d'une meme regle finissent par diverger :
        celle du navigateur est confrontee a celle du serveur, facteur par
        facteur."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("function annuelMinutes"):][:620]
        assert "startsWith('jour')"  in bloc and "q * dpw * wpy" in bloc
        assert "startsWith('hebdo')" in bloc and "q * wpy" in bloc
        assert "startsWith('mens')"  in bloc and "q * 12" in bloc
        # Et le calcul du role ne la reecrit plus a cote.
        role = js[js.index("function recalcRoleTotals"):][:1100]
        assert "dpw*wpy" not in role, role


class TestLeTableauDeBord:

    def test_il_repond_en_UNE_requete_avec_tout_ce_que_l_ecran_montre(self, auth_client):
        d = _tdb(auth_client)
        for cle in ("calendrier", "plein_temps_min", "charge", "faiblesses",
                    "couverture", "par_role", "par_activite", "projets"):
            assert cle in d, cle

    def test_la_charge_annuelle_suit_la_recurrence(self, auth_client, ids):
        r = auth_client.post("/temps/api/activity_workload", json={
            "activity_id": ids["activity_id"], "duration": 60,
            "duration_unit": "minutes", "recurrence": "hebdomadaire",
            "frequency": 2, "nb_people": 1})
        wid = json.loads(r.data)["id"]
        try:
            d = _tdb(auth_client)
            sem = d["calendrier"]["weeks_per_year"]
            ligne = [a for a in d["par_activite"] if a["id"] == wid][0]
            assert ligne["par_periode_min"] == 120
            assert ligne["annuel_min"] == pytest.approx(120 * sem)
        finally:
            auth_client.delete("/temps/api/activity_workload/%d" % wid)

    def test_l_equivalent_temps_plein_est_NUL_et_non_zero_sans_mesure(self, auth_client, ids):
        """⚠️ « 0 equivalent temps plein » se lit comme un resultat ; une
        absence doit se lire comme une absence. C'est la distinction que tout
        le module Competences tient deja (NULL ≠ 0).

        ⚠️ Sur sa PROPRE carto, vide. Une premiere version mettait en pause
        les analyses existantes en touchant les objets de la session
        partagee : les tests suivants heritaient d'une session dont le flush
        tombait en « 'NoneType' object has no attribute '__dict__' », et
        l'echec se lisait trois tests plus loin, dans une route sans rapport.
        """
        from Code.models.models import Entity
        vide = Entity(name="TM-CARTO-VIDE-105", description="refonte Temps",
                      owner_id=ids["user_id"])
        db.session.add(vide)
        db.session.commit()
        try:
            with auth_client.session_transaction() as sess:
                avant = sess.get("active_entity_id")
                sess["active_entity_id"] = vide.id
            d = _tdb(auth_client)
            assert d["couverture"]["total"] == 0
            assert d["charge"]["annuel_min"] == 0
            assert d["charge"]["etp"] is None
            assert d["faiblesses"]["part"] is None
        finally:
            with auth_client.session_transaction() as sess:
                if avant is None:
                    sess.pop("active_entity_id", None)
                else:
                    sess["active_entity_id"] = avant
            db.session.delete(db.session.get(Entity, vide.id))
            db.session.commit()

    def test_la_couverture_compte_des_ACTIVITES_pas_des_analyses(self, auth_client, ids):
        """Deux analyses sur la meme activite, c'est UNE activite chiffree."""
        avant = _tdb(auth_client)["couverture"]["chiffrees"]
        faits = []
        for _ in range(2):
            r = auth_client.post("/temps/api/activity_workload", json={
                "activity_id": ids["activity_id"], "duration": 30,
                "duration_unit": "minutes", "recurrence": "annuel",
                "frequency": 1, "nb_people": 1})
            faits.append(json.loads(r.data)["id"])
        try:
            apres = _tdb(auth_client)["couverture"]["chiffrees"]
            assert apres - avant <= 1, (avant, apres)
        finally:
            for i in faits:
                auth_client.delete("/temps/api/activity_workload/%d" % i)


class TestLAttenteNEstPasDuTravail:
    """⚠️ Le defaut que le banc a montre, et qu'aucun test n'aurait trouve :
    la carte additionnait le travail refait et l'attente, puis comparait le
    total a la charge de TRAVAIL. Mesure : 61 h de travail refait contre
    984 h d'attente, et l'ecran annoncait « 84 % de la charge » pour 5 %
    reels. Une activite qui attend deux jours la reponse d'un fournisseur ne
    coute deux jours de travail a personne.
    """

    def _poser(self, auth_client, ids, attente):
        return auth_client.post("/temps/api/weakness", json={
            "mode": "activity", "activity_id": ids["activity_id"],
            "recurrence": "hebdomadaire", "frequency": 1,
            "duration_std": 60, "duration_unit": "minutes",
            "delay_std": 0, "delay_unit": "minutes",
            "L_work_added": 30, "L_unit": "minutes",
            "M_wait_added": attente, "M_unit": "minutes",
            "N_prob_denom": 2, "weakness": "ATTENTE-TEST", "save": True})

    def test_les_deux_natures_sont_rendues_separement(self, auth_client, ids):
        assert self._poser(auth_client, ids, 2880).status_code == 200
        try:
            f = _tdb(auth_client)["faiblesses"]
            assert "travail_min" in f and "attente_min" in f
            # 30 min de travail refait, 2880 d'attente : l'attente domine.
            assert f["attente_min"] > f["travail_min"] * 10
        finally:
            self._nettoyer(auth_client)

    def test_la_part_de_la_charge_ne_compte_QUE_le_travail(self, auth_client, ids):
        # ⚠️ Le test apporte sa PROPRE charge mesuree : une version anterieure
        # se sautait quand il n'y en avait pas, et un test qui se saute ne
        # prouve rien — surtout celui-la, qui tient le defaut du jour.
        r = auth_client.post("/temps/api/activity_workload", json={
            "activity_id": ids["activity_id"], "duration": 120,
            "duration_unit": "minutes", "recurrence": "hebdomadaire",
            "frequency": 1, "nb_people": 1})
        wid = json.loads(r.data)["id"]
        assert self._poser(auth_client, ids, 2880).status_code == 200
        try:
            d = _tdb(auth_client)
            f, charge = d["faiblesses"], d["charge"]["annuel_min"]
            assert charge > 0, d["charge"]
            assert f["attente_min"] > 0, f
            assert f["part"] == pytest.approx(f["travail_min"] / charge)
            # Et surtout : PAS la somme des deux.
            assert f["part"] != pytest.approx((f["travail_min"] + f["attente_min"]) / charge)
        finally:
            self._nettoyer(auth_client)
            auth_client.delete("/temps/api/activity_workload/%d" % wid)

    def test_le_classement_suit_le_travail_refait(self, auth_client, ids):
        """Sans cela, une faiblesse qui ne coute aucun travail mais fait
        attendre trois jours arrive en tete de liste.

        ⚠️ On lit l'ORDRE rendu, pas la ligne de tri dans la source : ce
        fichier est compile dans l'image, et un test qui le relit y echoue a
        chaque execution."""
        from Code.models.models import TimeWeakness
        for libelle, travail, attente in (("ATTENTE-TEST-qui-attend", 5, 2880),
                                          ("ATTENTE-TEST-qui-coute", 120, 10)):
            r = auth_client.post("/temps/api/weakness", json={
                "mode": "activity", "activity_id": ids["activity_id"],
                "recurrence": "hebdomadaire", "frequency": 1,
                "duration_std": 60, "duration_unit": "minutes",
                "delay_std": 0, "delay_unit": "minutes",
                "L_work_added": travail, "L_unit": "minutes",
                "M_wait_added": attente, "M_unit": "minutes",
                "N_prob_denom": 1, "weakness": libelle, "save": True})
            assert r.status_code == 200, r.data
        try:
            noms = [f["nom"] for f in _tdb(auth_client)["faiblesses"]["items"]
                    if f["nom"].startswith("ATTENTE-TEST-")]
            assert noms[0] == "ATTENTE-TEST-qui-coute", noms
        finally:
            for w in (TimeWeakness.query
                      .filter(TimeWeakness.weakness.like("ATTENTE-TEST-%")).all()):
                db.session.delete(w)
            db.session.commit()

    def test_le_mode_par_taches_ne_compte_pas_DEUX_FOIS(self, auth_client, ids):
        """⚠️ Le mode « par taches » ecrit une ligne PAR TACHE plus une ligne
        de total (task_id nul). Les compter toutes doublerait le cout de
        chaque faiblesse detaillee."""
        from Code.models.models import Task, TimeWeakness
        t1 = Task(name="TACHE-FW-1", activity_id=ids["activity_id"])
        t2 = Task(name="TACHE-FW-2", activity_id=ids["activity_id"])
        db.session.add_all([t1, t2])
        db.session.commit()
        r = auth_client.post("/temps/api/weakness", json={
            "mode": "tasks", "activity_id": ids["activity_id"],
            "recurrence": "hebdomadaire", "frequency": 1,
            "delay_std": 0, "delay_unit": "minutes",
            "L_work_added": 30, "L_unit": "minutes",
            "M_wait_added": 0, "M_unit": "minutes",
            "N_prob_denom": 1, "weakness": "ATTENTE-TEST",
            "tasks": [{"task_id": t1.id, "duration_std": 20, "duration_unit": "minutes"},
                      {"task_id": t2.id, "duration_std": 40, "duration_unit": "minutes"}],
            "save": True})
        assert r.status_code == 200, r.data
        try:
            lignes = TimeWeakness.query.filter_by(weakness="ATTENTE-TEST").count()
            assert lignes == 3, lignes          # deux taches + un total
            items = _tdb(auth_client)["faiblesses"]["items"]
            miennes = [f for f in items if f["nom"] == "ATTENTE-TEST"]
            assert len(miennes) == 1, miennes
        finally:
            self._nettoyer(auth_client)
            for t in (t1, t2):
                db.session.delete(db.session.get(Task, t.id))
            db.session.commit()

    def test_supprimer_une_faiblesse_emporte_ses_lignes_de_tache(self, auth_client, ids):
        """Sans cela elles restent en base sans rien qui les rattache."""
        from Code.models.models import Task, TimeWeakness
        t1 = Task(name="TACHE-FW-3", activity_id=ids["activity_id"])
        db.session.add(t1)
        db.session.commit()
        auth_client.post("/temps/api/weakness", json={
            "mode": "tasks", "activity_id": ids["activity_id"],
            "recurrence": "annuel", "frequency": 1,
            "delay_std": 0, "delay_unit": "minutes",
            "L_work_added": 10, "L_unit": "minutes",
            "M_wait_added": 0, "M_unit": "minutes",
            "N_prob_denom": 1, "weakness": "ATTENTE-TEST",
            "tasks": [{"task_id": t1.id, "duration_std": 20, "duration_unit": "minutes"}],
            "save": True})
        total = TimeWeakness.query.filter_by(weakness="ATTENTE-TEST", task_id=None).first()
        assert total is not None
        r = auth_client.delete("/temps/api/weakness/%d" % total.id)
        assert r.status_code == 200, r.data
        assert TimeWeakness.query.filter_by(weakness="ATTENTE-TEST").count() == 0
        db.session.delete(db.session.get(Task, t1.id))
        db.session.commit()

    def _nettoyer(self, auth_client):
        from Code.models.models import TimeWeakness
        for w in TimeWeakness.query.filter_by(weakness="ATTENTE-TEST").all():
            db.session.delete(w)
        db.session.commit()


class TestLesQuatreAnalysesSAtteignentDepuisLAccueil:
    """« On pourrait peut-etre retrouver nos 4 types via la page d'accueil, et
    pas obligatoirement en passant par la creation d'une analyse. »

    La seule porte etait « + Nouvelle analyse » — un bouton qui annonce une
    CREATION, alors qu'on vient souvent relire ce qui existe.
    """

    @pytest.mark.parametrize("quoi", ["projet", "activite", "role", "faiblesse"])
    def test_une_tuile_par_analyse_sur_l_accueil(self, quoi):
        g = _lire("Code/routes/templates/time_dashboard.html")
        accueil = g[g.index('id="tm-accueil"'):g.index('id="tm-choix"')]
        assert ('class="tm-rail-t tm-r-%s" data-analyse="%s"' % (quoi, quoi)) in accueil
        assert ('id="tm-n-%s"' % quoi) in accueil, quoi

    def test_les_tuiles_portent_le_nombre_de_ce_qui_est_enregistre(self):
        js = _lire("static/js/time.js")
        for ident in ("tm-n-projet", "tm-n-activite", "tm-n-role", "tm-n-faiblesse"):
            assert ("'%s'" % ident) in js, ident

    def test_le_rail_ET_les_portes_ouvrent_la_meme_chose(self):
        """⚠️ Pas `[data-analyse]` tout court : `#tm-travail` porte cet
        attribut (c'est lui qui teinte l'icone de la barre), on lui poserait
        un ecouteur qui le rouvrirait sur lui-meme."""
        js = _lire("static/js/time.js")
        assert "$$('.tm-porte, .tm-rail-t')" in js
        assert "$$('[data-analyse]')" not in js


class TestLaCarteDiLeQuiManque:
    """« Je n'ai ni compris ce que c'etait, ni ce qu'il fallait y faire une
    fois clique sur Chiffrer les suivantes. »

    Elle annoncait « 12 activites sur 12 », « Le total ci-contre ne porte que
    sur 0 activites » — un compte sans objet, une phrase qui designe une carte
    voisine par sa POSITION (fausse des que l'ecran se replie en colonne) et
    un « 0 activites » au pluriel — puis ouvrait un formulaire generique dont
    la liste deroulante portait TOUTES les activites.
    """

    def test_le_tableau_de_bord_NOMME_ce_qui_manque(self, auth_client, ids):
        couv = _tdb(auth_client)["couverture"]
        assert "a_chiffrer" in couv
        manquent = couv["a_chiffrer"]
        assert len(manquent) == couv["total"] - couv["chiffrees"], couv
        for a in manquent:
            assert a["nom"] and isinstance(a["id"], int), a

    def test_une_activite_chiffree_quitte_la_liste(self, auth_client, ids):
        """⚠️ Sur SON activite, creee pour l'occasion : la base est partagee,
        et un autre fichier a pu chiffrer celle du decor commun entre-temps —
        le test passait seul et tombait en suite complete."""
        from Code.models.models import Activities
        # ⚠️ La carto est celle que le SERVEUR considere active — pas
        # `Entity.get_active_id()`, qui lit la session Flask et n'a pas de
        # reponse hors requete. On la deduit de ce que le tableau de bord
        # vient de rendre.
        depart = _tdb(auth_client)
        temoin = (depart["couverture"]["a_chiffrer"] or depart["par_activite"])
        assert temoin, "la carto active n'a aucune activite"
        modele = db.session.get(Activities, temoin[0].get("id") or temoin[0]["activity_id"])
        neuve = Activities(name="TM-ACT-105-a-chiffrer", entity_id=modele.entity_id)
        db.session.add(neuve)
        db.session.commit()
        wid = None
        try:
            avant = {a["id"] for a in _tdb(auth_client)["couverture"]["a_chiffrer"]}
            assert neuve.id in avant, avant

            r = auth_client.post("/temps/api/activity_workload", json={
                "activity_id": neuve.id, "duration": 30,
                "duration_unit": "minutes", "recurrence": "annuel",
                "frequency": 1, "nb_people": 1})
            wid = json.loads(r.data)["id"]
            apres = {a["id"] for a in _tdb(auth_client)["couverture"]["a_chiffrer"]}
            assert neuve.id not in apres, apres
        finally:
            if wid:
                auth_client.delete("/temps/api/activity_workload/%d" % wid)
            db.session.delete(db.session.get(Activities, neuve.id))
            db.session.commit()

    def test_la_liste_est_plafonnee(self):
        """Une carto de six cents activites n'a pas a les envoyer toutes pour
        remplir une carte qui en montre trois."""
        src_js = _lire("static/js/time.js")
        assert "manquent.slice(0, 3)" in src_js
        assert "tm_couv_autres" in src_js

    def test_le_bouton_NOMME_l_activite_qu_il_ouvre(self):
        js = _lire("static/js/time.js")
        assert "tm_couv_btn_nom" in js
        assert "ouvrirAnalyse('activite', manquent[0].id)" in js

    def test_et_l_ouvrir_la_pre_choisit(self):
        """⚠️ Et remet le champ a l'etat NON SAISI : `intact()` refuse sinon
        de poser la duree de la fiche, et on arrive sur un zero."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("function ouvrirAnalyse"):][:900]
        assert "sel.value = String(activityId)" in bloc
        assert "delete c.dataset.saisi" in bloc
        assert "refreshActivityDefaults()" in bloc

    @pytest.mark.parametrize("lang", ["fr", "en"])
    def test_le_cas_ou_RIEN_n_est_chiffre_a_sa_propre_phrase(self, lang):
        """« ne porte que sur 0 activites » ne veut rien dire, et au pluriel
        en plus."""
        from Code.translations import t
        phrase = t("time.tm_couv_aucune", lang=lang)
        assert phrase != "time.tm_couv_aucune"
        assert "0" not in phrase, phrase
        js = _lire("static/js/time.js")
        assert "if (!couv.chiffrees) cbase.textContent = tl('tm_couv_aucune'" in js

    @pytest.mark.parametrize("lang", ["fr", "en"])
    def test_la_phrase_ne_designe_plus_une_carte_par_sa_POSITION(self, lang):
        """« ci-contre » / « opposite » : faux des que l'ecran se replie en
        une seule colonne — c'est-a-dire sous 1000 px."""
        from Code.translations import t
        for cle in ("time.tm_couv_base", "time.tm_couv_base_une"):
            phrase = t(cle, lang=lang).lower()
            assert "ci-contre" not in phrase and "opposite" not in phrase, (cle, phrase)
