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


class _CartoJetable:
    """Une carto a soi, active le temps du cas, avec `n` activites NON
    chiffrees. ⚠️ Sur sa PROPRE carto : toucher aux analyses du decor commun
    laisse des objets morts dans la session partagee, et l'echec se lit trois
    tests plus loin dans une route sans rapport."""

    def __init__(self, client, ids, n):
        self.client, self.ids, self.n = client, ids, n

    def __enter__(self):
        from Code.models.models import Activities, Entity
        self.ent = Entity(name="TM-105-JETABLE-%d" % id(self),
                          owner_id=self.ids["user_id"])
        db.session.add(self.ent)
        db.session.commit()
        self.actes = [Activities(name="TM-105-a%d" % i, entity_id=self.ent.id)
                      for i in range(self.n)]
        db.session.add_all(self.actes)
        db.session.commit()
        with self.client.session_transaction() as sess:
            self.avant = sess.get("active_entity_id")
            sess["active_entity_id"] = self.ent.id
        return self

    def __exit__(self, *_):
        from Code.models.models import Activities, Entity
        # ⚠️ On REPOSE une entite, on ne se contente pas de retirer la clef :
        # `auth_client` la met avec `setdefault`, donc il ne la corrigerait
        # pas, et `Entity.get_active` retomberait sur « sa premiere entite » —
        # qui n'est pas forcement celle du decor commun. Un fichier joue plus
        # loin lirait alors la mauvaise carto, et l'echec se lirait chez lui.
        with self.client.session_transaction() as sess:
            sess["active_entity_id"] = (self.avant if self.avant is not None
                                        else self.ids["entity_id"])
        for a in self.actes:
            db.session.delete(db.session.get(Activities, a.id))
        db.session.delete(db.session.get(Entity, self.ent.id))
        db.session.commit()
        return False


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
        for cible in ('id="tm-l-projet"', 'id="tm-l-activite"',
                      'id="tm-l-role"', 'id="tm-l-faiblesse"'):
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

    def test_les_cinq_recurrences(self, app):
        """⚠️ CINQ depuis le 05/11/2026 : le pilote estime des charges
        trimestrielles (« In Time Management - quaterly recurrence is not
        available »). Le trimestre compte 4 periodes par an, en calendrier
        CIVIL comme ses voisines ici."""
        from Code.routes.time_view import annuel_minutes
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 47}
        assert annuel_minutes(10, "journalier", p) == 10 * 5 * 47
        assert annuel_minutes(10, "hebdomadaire", p) == 10 * 47
        assert annuel_minutes(10, "mensuel", p) == 120
        assert annuel_minutes(10, "trimestriel", p) == 40
        assert annuel_minutes(10, "annuel", p) == 10

    def test_une_recurrence_inconnue_ne_multiplie_rien(self, app):
        """Plutot que de choisir un facteur au hasard : une valeur inattendue
        doit se voir dans le resultat, pas s'y fondre."""
        from Code.routes.time_view import annuel_minutes
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 47}
        # ⚠️ « trimestriel » servait ICI d'exemple de recurrence inconnue : il
        # est reconnu depuis le 05/11/2026. On prend une valeur qui n'a aucune
        # chance d'etre implementee, sinon le decor du test decide du sujet.
        assert annuel_minutes(10, "lunaire", p) == 10
        assert annuel_minutes(10, "", p) == 10

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
        bloc = js[js.index("function annuelMinutes"):][:760]
        assert "startsWith('jour')"  in bloc and "q * dpw * wpy" in bloc
        assert "startsWith('hebdo')" in bloc and "q * wpy" in bloc
        assert "startsWith('trimestr')" in bloc and "q * 4" in bloc
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

    def test_le_rail_MONTRE_les_analyses_les_portes_en_creent_une(self):
        """Le rail ouvrait l'ecran de saisie VIERGE — ce que fait deja
        « + Nouvelle analyse », a dix centimetres au-dessus — alors que
        chaque tuile porte le NOMBRE d'analyses de son type. On vient le plus
        souvent ici pour relire : il deplie le groupe et l'amene sous les yeux.

        ⚠️ Pas `[data-analyse]` tout court : `#tm-travail` porte cet attribut
        (c'est lui qui teinte l'icone de la barre), on lui poserait un
        ecouteur qui le rouvrirait sur lui-meme."""
        js = _lire("static/js/time.js")
        assert "$$('.tm-porte')" in js
        assert "$$('.tm-rail-t')" in js
        assert "$$('.tm-porte, .tm-rail-t')" not in js
        assert "$$('[data-analyse]')" not in js
        # Le rail passe par `montrerGroupe`, qui deplie et designe le groupe.
        rail = js[js.index("$$('.tm-rail-t')"):]
        rail = rail[:rail.index(";")]
        assert "montrerGroupe" in rail
        assert "ouvrirAnalyse" not in rail
        assert "function montrerGroupe(" in js


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

    def test_la_liste_est_plafonnee_cote_SERVEUR(self, auth_client, ids):
        """Une carto de six cents activites n'a pas a les envoyer toutes.

        ⚠️ La liste des trois noms a quitte la carte avec la maquette
        « l'ordre de grandeur » : c'est le BOUTON qui porte l'action, et il
        nomme ce qu'il ouvre (cas suivant). Le plafond, lui, reste — il
        protege la reponse, pas l'affichage.

        ⚠️ Sur le COMPORTEMENT : une version qui lisait la source de
        `time_view` passait ici et rougissait a CHAQUE execution dans l'arbre
        d'image, compile en bytecode."""
        with _CartoJetable(auth_client, ids, 62):
            couv = _tdb(auth_client)["couverture"]
            assert couv["total"] == 62
            assert couv["chiffrees"] == 0
            assert len(couv["a_chiffrer"]) == 60, len(couv["a_chiffrer"])

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
    def test_aucune_phrase_ne_designe_une_carte_par_sa_POSITION(self, lang):
        """« ci-contre » / « opposite » : faux des que l'ecran se replie en
        une seule colonne — c'est-a-dire sous 1000 px.

        \u26a0\ufe0f La regle valait pour deux clefs ; elle vaut pour TOUTES.
        « ci-dessus » est en revanche juste : les cartes s'empilent dans
        l'ordre du document, ce qui est au-dessus le reste."""
        from Code.translations import TRANSLATIONS
        for cle, phrase in TRANSLATIONS[lang].items():
            if not cle.startswith("time."):
                continue
            bas = str(phrase).lower()
            assert "ci-contre" not in bas and "opposite" not in bas, (cle, phrase)


_N_ROLE_105 = [0]


@pytest.fixture
def role_jetable():
    """Un rôle à soi. ⚠️ Les rôles sont COMMUNS à l'entreprise : un nom fixe
    entre en collision avec celui d'un autre fichier de tests."""
    from Code.models.models import Entity, Role
    _N_ROLE_105[0] += 1
    r = Role(name="TM-105-role-%d" % _N_ROLE_105[0],
             entity_id=Entity.query.first().id)
    db.session.add(r)
    db.session.commit()
    rid = r.id
    yield rid
    obj = db.session.get(Role, rid)
    if obj is not None:
        db.session.delete(obj)
        db.session.commit()


class TestOuvrirUneAnalysePourLaModifier:
    """« Lorsque l'on clique sur une analyse, on ne peut y apporter de
    modifications, il faut pouvoir. De plus on peut supprimer une analyse mais
    pas à l'intérieur de celle-ci un élément : cela oblige, si erreur, à
    supprimer l'analyse et refaire au complet. »

    Exact, et pour trois des quatre types : seule l'analyse d'ACTIVITÉ avait
    un `PATCH`. Le projet ne savait que se renommer, le rôle non plus, et la
    faiblesse ne se relisait même pas.
    """

    def test_un_projet_se_modifie_SANS_se_dupliquer(self, auth_client, ids):
        r = auth_client.post("/temps/api/project", json={
            "name": "TM-PROJ-105", "lines": [
                {"activity_id": ids["activity_id"], "duration": 30,
                 "duration_unit": "minutes", "delay": 0, "delay_unit": "minutes",
                 "nb_people": 1}]})
        pid = json.loads(r.data)["project_id"]
        combien = lambda: len(json.loads(
            auth_client.get("/temps/api/projects").data)["items"])
        avant = combien()
        try:
            r = auth_client.put("/temps/api/project/%d" % pid, json={
                "name": "TM-PROJ-105 corrigé", "lines": [
                    {"activity_id": ids["activity_id"], "duration": 120,
                     "duration_unit": "minutes", "delay": 0,
                     "delay_unit": "minutes", "nb_people": 2}]})
            assert r.status_code == 200, r.data
            d = json.loads(auth_client.get("/temps/api/project/%d" % pid).data)
            assert d["project"]["name"] == "TM-PROJ-105 corrigé"
            assert len(d["lines"]) == 1
            assert d["lines"][0]["duration_minutes"] == 120
            assert d["lines"][0]["nb_people"] == 2
            assert combien() == avant, "le projet a été dupliqué"
        finally:
            auth_client.delete("/temps/api/project/%d" % pid)

    def test_retirer_une_ligne_ne_supprime_pas_l_analyse(self, auth_client, ids):
        """Le cœur du reproche : corriger une erreur ne doit pas obliger à
        tout refaire."""
        r = auth_client.post("/temps/api/project", json={
            "name": "TM-PROJ-105b", "lines": [
                {"activity_id": ids["activity_id"], "duration": 30,
                 "duration_unit": "minutes", "nb_people": 1},
                {"activity_id": ids["activity_id"], "duration": 60,
                 "duration_unit": "minutes", "nb_people": 1}]})
        pid = json.loads(r.data)["project_id"]
        try:
            auth_client.put("/temps/api/project/%d" % pid, json={
                "name": "TM-PROJ-105b", "lines": [
                    {"activity_id": ids["activity_id"], "duration": 30,
                     "duration_unit": "minutes", "nb_people": 1}]})
            d = json.loads(auth_client.get("/temps/api/project/%d" % pid).data)
            assert d["ok"] and len(d["lines"]) == 1
        finally:
            auth_client.delete("/temps/api/project/%d" % pid)

    def test_un_role_se_modifie_lignes_comprises(self, auth_client, ids, role_jetable):
        r = auth_client.post("/temps/api/role_analysis", json={
            "role_id": role_jetable, "name": "TM-ROLE-105",
            "lines": [{"activity_id": ids["activity_id"], "duration": 30,
                       "recurrence": "journalier", "frequency": 1}]})
        rid = json.loads(r.data)["id"]
        try:
            r = auth_client.patch("/temps/api/role_analysis/%d" % rid, json={
                "name": "TM-ROLE-105 corrigé",
                "lines": [{"activity_id": ids["activity_id"], "duration": 90,
                           "recurrence": "mensuel", "frequency": 2}]})
            assert r.status_code == 200, r.data
            d = json.loads(auth_client.get("/temps/api/role_analysis/%d" % rid).data)
            assert d["role"]["name"] == "TM-ROLE-105 corrigé"
            assert len(d["lines"]) == 1
            assert d["lines"][0]["duration_minutes"] == 90
            assert d["lines"][0]["recurrence"] == "mensuel"
            assert d["lines"][0]["frequency"] == 2
        finally:
            auth_client.delete("/temps/api/role_analysis/%d" % rid)

    def test_renommer_un_role_SANS_toucher_a_ses_lignes(self, auth_client, ids,
                                                        role_jetable):
        """⚠️ `lines` absent ne doit RIEN toucher : le renommage en place
        existait avant, il ne doit pas se mettre à vider l'analyse."""
        r = auth_client.post("/temps/api/role_analysis", json={
            "role_id": role_jetable, "name": "TM-ROLE-105c",
            "lines": [{"activity_id": ids["activity_id"], "duration": 30,
                       "recurrence": "journalier", "frequency": 1}]})
        rid = json.loads(r.data)["id"]
        try:
            auth_client.patch("/temps/api/role_analysis/%d" % rid,
                              json={"name": "TM-ROLE-105c bis"})
            d = json.loads(auth_client.get("/temps/api/role_analysis/%d" % rid).data)
            assert d["role"]["name"] == "TM-ROLE-105c bis"
            assert len(d["lines"]) == 1, d["lines"]
        finally:
            auth_client.delete("/temps/api/role_analysis/%d" % rid)

    def test_une_faiblesse_se_relit_avec_ses_parametres(self, auth_client, ids):
        """Elle ne se relisait pas du tout : aucune route ne la rendait."""
        auth_client.post("/temps/api/weakness", json={
            "mode": "activity", "activity_id": ids["activity_id"],
            "recurrence": "hebdomadaire", "frequency": 2,
            "duration_std": 60, "duration_unit": "minutes",
            # ⚠️ Au-dessus de la duree : un delai inferieur est un etat
            # impossible, et le serveur le remonte (`delai_plancher`).
            "delay_std": 90, "delay_unit": "minutes",
            "L_work_added": 45, "L_unit": "minutes",
            "M_wait_added": 120, "M_unit": "minutes",
            "N_prob_denom": 3, "weakness": "TM-FW-105", "save": True})
        from Code.models.models import TimeWeakness
        w = TimeWeakness.query.filter_by(weakness="TM-FW-105").first()
        try:
            d = json.loads(auth_client.get("/temps/api/weakness/%d" % w.id).data)
            it = d["item"]
            assert it["weakness"] == "TM-FW-105"
            assert it["recurrence"] == "hebdomadaire" and it["frequency"] == 2
            assert it["duration_std"] == 60 and it["delay_std"] == 90
            assert it["L_work_added"] == 45 and it["M_wait_added"] == 120
            assert it["N_prob_denom"] == 3
            assert it["mode"] == "activity"
            assert "calc" in d and d["calc"]["U"] > 0
        finally:
            auth_client.delete("/temps/api/weakness/%d" % w.id)

    def test_une_faiblesse_se_modifie_et_garde_son_identifiant(self, auth_client, ids):
        """⚠️ Son id ne bouge pas : l'écran qui vient de l'ouvrir la retrouve
        au même endroit, et la liste ne se met pas à montrer un doublon."""
        from Code.models.models import TimeWeakness
        auth_client.post("/temps/api/weakness", json={
            "mode": "activity", "activity_id": ids["activity_id"],
            "recurrence": "hebdomadaire", "frequency": 1,
            "duration_std": 60, "duration_unit": "minutes",
            "delay_std": 0, "delay_unit": "minutes",
            "L_work_added": 30, "L_unit": "minutes",
            "M_wait_added": 0, "M_unit": "minutes",
            "N_prob_denom": 2, "weakness": "TM-FW-105b", "save": True})
        w = TimeWeakness.query.filter_by(weakness="TM-FW-105b").first()
        wid = w.id
        try:
            r = auth_client.put("/temps/api/weakness/%d" % wid, json={
                "mode": "activity", "activity_id": ids["activity_id"],
                "recurrence": "mensuel", "frequency": 1,
                "duration_std": 60, "duration_unit": "minutes",
                "delay_std": 0, "delay_unit": "minutes",
                "L_work_added": 90, "L_unit": "minutes",
                "M_wait_added": 0, "M_unit": "minutes",
                "N_prob_denom": 2, "weakness": "TM-FW-105b corrigé"})
            assert r.status_code == 200, r.data
            assert json.loads(r.data)["id"] == wid
            d = json.loads(auth_client.get("/temps/api/weakness/%d" % wid).data)["item"]
            assert d["weakness"] == "TM-FW-105b corrigé"
            assert d["L_work_added"] == 90 and d["recurrence"] == "mensuel"
            assert TimeWeakness.query.filter(
                TimeWeakness.weakness.like("TM-FW-105b%")).count() == 1
        finally:
            for x in TimeWeakness.query.filter(
                    TimeWeakness.weakness.like("TM-FW-105b%")).all():
                db.session.delete(x)
            db.session.commit()

    def test_l_ecran_sait_qu_il_MODIFIE(self):
        """Sans ce repère on ne sait pas si « Enregistrer » crée une analyse
        de plus ou remplace celle qu'on vient d'ouvrir."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert 'id="tm-mod"' in g and 'id="tm-mod-sortir"' in g
        js = _lire("static/js/time.js")
        assert "let edition = null;" in js
        assert "function ouvrirPourModifier" in js
        for appel in ("chargerProjet", "chargerActivite", "chargerRole", "chargerFaiblesse"):
            assert ("function %s" % appel) in js, appel

    def test_une_ligne_CHARGEE_est_recalculee(self):
        """⚠️ Relevé au banc : un projet enregistré à 10,5 h se rouvrait en
        affichant « 0.0h ». Les durées étaient justes — mais le total lit
        `.cell-chg[data-minutes]`, que SEUL `recalc()` renseigne, et il
        n'était appelé que par le pré-remplissage."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("function addProjectRow"):][:2600]
        assert "recalc();\n    } else {" in bloc, bloc[-700:]
        role = js[js.index("function addRoleRow"):][:2200]
        assert "if (duration) recalc(); else prefillDuration();" in role


class TestLaListeTientALEcran:
    """« Avec des données les listes deviennent vite très verbeuses et pas du
    tout agréables. » Mesuré : dix-huit lignes empilées, chacune avec son
    accordéon, ses badges et sa ligne de méta — neuf cents pixels de
    défilement pour retrouver une analyse.
    """

    @pytest.mark.parametrize("quoi", ["projet", "activite", "role", "faiblesse"])
    def test_une_section_repliable_par_type(self, quoi):
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert ('data-grp="%s"' % quoi) in g
        assert ('data-plier="%s"' % quoi) in g
        assert ('id="tm-l-%s"' % quoi) in g
        assert ('id="tm-g-n-%s"' % quoi) in g

    def test_elles_sont_FERMEES_au_depart(self):
        """Le compte dans l'en-tête suffit à savoir s'il y a quelque chose à
        ouvrir ; les dix-huit lignes, non."""
        css = _lire("static/time.css")
        assert ".tm-grp-corps { display: none;" in css
        assert ".tm-grp.is-ouvert .tm-grp-corps { display: block; }" in css
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert 'class="tm-grp is-ouvert"' not in g

    def test_l_etat_des_sections_survit_au_rechargement(self):
        js = _lire("static/js/time.js")
        assert "optiq.temps.groupes" in js
        # ⚠️ Un navigateur peut refuser le stockage : chaque accès en try/catch.
        bloc = js[js.index("function groupesOuverts"):][:460]
        assert "catch" in bloc

    def test_une_ligne_OUVRE_son_analyse(self):
        js = _lire("static/js/time.js")
        assert "ouvrirPourModifier(l.dataset.type" in js
        # Et au clavier : ce qui s'ouvre au clic s'ouvre à Entrée.
        assert "e.key === 'Enter'" in js

    def test_les_trois_anciens_rendus_ont_disparu(self):
        """Trois listes, trois accordéons, trois renommages en place — et
        pourtant « on ne peut pas modifier une analyse »."""
        js = _lire("static/js/time.js")
        for mort in ("refreshProjectList", "refreshActivityWorkloadList",
                     "refreshRoleAnalyses", "acc-item", "proj-name-input"):
            assert mort not in js, mort

    def test_les_deux_boutons_de_l_entete_ne_sont_plus_des_btn_nus(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        # ⚠️ Jusqu'à la FIN du bloc, pas 600 signes : une porte de plus dans
        # l'en-tête poussait le bouton primaire hors de la tranche, et le cas
        # tombait sans qu'il y ait le moindre défaut.
        i = g.index('class="tm-entete-actions"')
        entete = g[i:g.index("</div>", g.index("tm-btn-nouvelle", i))]
        assert 'class="tm-b tm-b--doux"' in entete
        assert 'class="tm-b tm-b--prim"' in entete
        assert 'class="btn' not in entete, entete


# ══════════════════════════════════════════════════════════════════════════
#  La saisie : direction A (les quatre types) et C (les trois temps)
#
#  « Ils sont vraiment trop blanc gris et écrit en petit. » Mesuré avant de
#  redessiner : `body.pg` porte `zoom: .8`, donc un libellé écrit 12,5 px
#  arrivait à 10 px sous les yeux, et une aide à 12 px à 9,6 px — SOUS le
#  plancher de 11 px de l'échelle typographique du design system.
# ══════════════════════════════════════════════════════════════════════════

class TestLesTroisTemps:
    """Le formulaire Faiblesse posait dix champs à plat. Il pose trois
    questions, et rien ne le disait."""

    def test_les_trois_temps_sont_numerotes(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert g.count('class="tm-tps-n"') == 3, g.count('tm-tps-n')
        assert g.count('class="tm-tps-q"') == 3
        for n in ("1", "2", "3"):
            assert '>%s</span>' % n in g, n

    def test_les_trois_questions_existent_dans_les_deux_langues(self):
        """⚠️ On lit les DICTIONNAIRES, pas `t()` : une clé absente de
        l'anglais retombe silencieusement sur le français."""
        from Code.translations import TRANSLATIONS
        cles = ["time.fw_t1_q", "time.fw_t2_q", "time.fw_t3_q"]
        for langue in ("fr", "en"):
            manquantes = [c for c in cles if c not in TRANSLATIONS[langue]]
            assert not manquantes, (langue, manquantes)
        identiques = [c for c in cles
                      if TRANSLATIONS["fr"][c] == TRANSLATIONS["en"][c]]
        assert not identiques, identiques

    def test_les_trois_PHRASES_des_temps_ont_disparu(self):
        """Elles décrivaient ce que l'écran montre déjà : la question et les
        champs disent tout. Trois lignes de gris en moins, dans un formulaire
        qu'on venait justement de dégager."""
        from Code.translations import TRANSLATIONS
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "tm-tps-p" not in g
        for cle in ("time.fw_t1_p", "time.fw_t2_p", "time.fw_t3_p"):
            for lg in ("fr", "en"):
                assert cle not in TRANSLATIONS[lg], (cle, lg)

    def test_TOUS_les_id_du_formulaire_survivent(self):
        """⚠️ C'est le contrat : `time.js` écrit par id et bascule
        `#fw-global` / `#fw-tasks` selon le mode. On a changé l'ordre et le
        récit, jamais le contrat."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        for cle in ("fw-activity", "fw-rec", "fw-freq", "fw-global", "fw-dur",
                    "fw-dur-unit", "fw-del", "fw-del-unit", "fw-del-note",
                    "fw-tasks", "fw-task-rows", "fw-task-sum", "fw-k", "fw-n",
                    "fw-l", "fw-l-unit", "fw-m", "fw-m-unit", "btn-fw-save",
                    "fw-feedback"):
            assert 'id="%s"' % cle in g, cle
        assert g.count('name="fw-mode"') == 2

    def test_les_bilans_partiels_sont_MASQUES_au_repos(self):
        """Un bilan à zéro se lit comme un résultat."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        for ident in ("fw-bilan-2", "fw-bilan-3"):
            i = g.index('id="%s"' % ident)
            debut = g.rfind("<div", 0, i)
            assert "hidden" in g[debut:i], ident

    def test_les_bilans_suivent_la_convention_de_CE_fichier(self):
        """⚠️ Deux conventions coexistent dans l'application : `{x}`, résolue
        par `fmtPhrase` dans `time.js`, et `[[x]]`, celle de `acp.*` et
        `chat.*`. Une clé qui prend la mauvaise affiche son marqueur TEL QUEL,
        et rien ne lève d'erreur."""
        from Code.translations import TRANSLATIONS
        for cle, marqueurs in (("time.fw_bilan_2", ("{degrade}", "{normal}")),
                               ("time.fw_bilan_3", ("{n}", "{travail}", "{retard}"))):
            for langue in ("fr", "en"):
                valeur = TRANSLATIONS[langue][cle]
                for m in marqueurs:
                    assert m in valeur, (cle, langue, m)
                assert "[[" not in valeur, (cle, langue)

    def test_les_libelles_des_temps_sont_injectes_dans_TIME_I18N(self):
        """Sans injection, `tl()` sert son repli — ici une chaîne vide, donc
        un bilan qui ne s'affiche jamais."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        for cle in ("fw_bilan_2", "fw_bilan_3"):
            assert "%s:" % cle in g, cle
            assert "t('time.%s')|tojson" % cle in g, cle


class TestLePanneauNeSommePlusDeuxNatures:
    """⚠️⚠️ Le défaut de fond. Le panneau collé à droite écrivait `U + V` sous
    un seul libellé « Coût annuel » — du travail refait ET du temps d'horloge
    dans un même nombre — alors que `time_view.py` dit l'inverse en toutes
    lettres (« DEUX natures, jamais additionnées […] les sommer donnait 84 %
    de la charge pour 5 % réels ») et que le tableau de bord de l'accueil les
    sépare depuis le 03/11. Deux écrans de la même page disaient deux choses.
    """

    def test_les_cinq_chiffres_sont_NOMMES(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        for ident in ("tm-fw-an", "tm-fw-retard", "tm-fw-occ", "tm-fw-delai",
                      "tm-fw-mois"):
            assert 'id="%s"' % ident in g, ident

    def test_le_navigateur_n_additionne_plus_le_travail_et_l_attente(self):
        js = _lire("static/js/time.js")
        bloc = js[js.index("updateKpi('tm-fw-an'"):][:460]
        assert "m['U'] || 0" in bloc, bloc
        assert "+ (m['V']" not in bloc, bloc
        assert "+ (m['X']" not in bloc, bloc
        assert "tm-fw-retard" in bloc and "m['V']" in bloc, bloc

    def test_les_libelles_ne_nomment_plus_une_somme(self):
        from Code.translations import TRANSLATIONS
        for cle in ("time.tm_fw_an", "time.tm_fw_mois", "time.tm_fw_occ",
                    "time.tm_fw_retard", "time.tm_fw_delai", "time.tm_fw_titre"):
            for langue in ("fr", "en"):
                assert cle in TRANSLATIONS[langue], (cle, langue)
        assert "refait" in TRANSLATIONS["fr"]["time.tm_fw_an"]
        assert "redone" in TRANSLATIONS["en"]["time.tm_fw_an"]

    def test_les_DEUX_routes_rendent_un_calc_de_MEME_forme(self, app, auth_client):
        """⚠️ L'une reconstruisait `calc` avec une liste de clés figée, l'autre
        renvoie `cout_faiblesse` tel quel. Le bilan du temps 2 marchait donc à
        la réouverture d'une analyse et PAS pendant la saisie — vérifié à
        l'écran avant d'être corrigé.
        """
        from Code.extensions import db
        from Code.models.models import Activities, Entity

        with app.app_context():
            ent = Entity(name="T105 calc commun")
            db.session.add(ent)
            db.session.flush()
            act = Activities(name="T105 activite calc", entity_id=ent.id)
            db.session.add(act)
            db.session.commit()
            aid, eid = act.id, ent.id

        corps = {"activity_id": aid, "mode": "activity",
                 "recurrence": "hebdomadaire", "frequency": 2,
                 "duration_std": 120, "duration_unit": "minutes",
                 "delay_std": 120, "delay_unit": "minutes",
                 "weakness": "T105", "prob_percent": 20,
                 "work_added": 10, "work_unit": "minutes",
                 "wait_added": 5, "wait_unit": "minutes", "save": True}
        try:
            r = auth_client.post("/temps/api/weakness", json=corps)
            assert r.status_code == 200, r.data
            j = r.get_json()
            calc = j.get("calc") or {}
            # ⚠️ `L` (travail refait) et `H` (exécutions de l'année)
            # nourrissent le SCHÉMA : ils doivent exister des DEUX
            # côtés, sinon il marche à la réouverture d'une analyse
            # et pas pendant la saisie.
            for cle in ("B", "C", "L", "H", "U", "V", "Y", "AA"):
                assert cle in calc, (cle, sorted(calc))
            wid = j.get("id")
            if wid:
                r2 = auth_client.get("/temps/api/weakness/%d" % wid)
                assert r2.status_code == 200, r2.data
                calc2 = r2.get_json().get("calc") or {}
                assert set(calc) == set(calc2), (
                    "les deux routes rendent des `calc` de formes differentes : "
                    "%r" % (set(calc) ^ set(calc2),))
        finally:
            with app.app_context():
                from Code.models.models import TimeWeakness
                TimeWeakness.query.filter_by(activity_id=aid).delete()
                Activities.query.filter_by(id=aid).delete()
                e = db.session.get(Entity, eid)
                if e is not None:
                    db.session.delete(e)
                db.session.commit()


class TestLaCouleurDuTypeEtLaTypographie:
    """Direction A : les quatre couleurs existaient déjà comme jetons et ne
    servaient qu'aux portes de l'accueil."""

    def test_les_quatre_types_posent_leur_couleur(self):
        """⚠️ On cherche DANS le bloc neuf. `css.index` sur toute la feuille
        tombait sur une règle préexistante — `#tm-travail[data-analyse="role"]
        .tm-barre-ic`, plus haut — et le cas restait VERT en cassant la règle
        qu'il croyait garder (vérifié).
        """
        css = _lire("static/time.css")
        bloc = css[css.index("DIRECTION A"):]
        for type_, jeton in (("projet", "--tm-projet"), ("activite", "--tm-activite"),
                             ("role", "--tm-role"), ("faiblesse", "--tm-faiblesse")):
            regle = '#tm-travail[data-analyse="%s"]' % type_
            i = bloc.find(regle + " ")
            assert i > 0, "la règle de couleur de %s manque au bloc" % type_
            ligne = bloc[i:bloc.index("\n", i)]
            assert "--tm-c" in ligne and jeton in ligne, (type_, ligne)

    def test_la_typographie_de_la_SAISIE_passe_le_plancher(self):
        """⚠️ `body.pg` porte `zoom: .8` : ce qu'on écrit ici est rendu à 80 %.
        Le plancher de l'échelle du design system est 11 px RÉELS — donc
        13,75 px écrits. Les éléments qu'on LIT doivent le passer.
        """
        import re
        css = _lire("static/time.css")
        bloc = css[css.index("DIRECTION A"):]
        tailles = {}
        for sel, cle in ((".sc-field > label", "label"),
                         (".tm-saisie .input", "valeur"),
                         (".tm-saisie .field-hint", "aide")):
            i = bloc.find(sel)
            assert i > 0, sel
            m = re.search(r"font-size:\s*([0-9.]+)px", bloc[i:i + 400])
            assert m, sel
            tailles[cle] = float(m.group(1))
        assert tailles["label"] >= 13.75, tailles
        assert tailles["valeur"] >= 13.75, tailles
        # L'aide est secondaire : elle remonte sans forcément passer le
        # plancher, mais plus jamais à 12 px (9,6 réels).
        assert tailles["aide"] >= 13.0, tailles

    def test_le_titre_du_panneau_suit_le_type(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert g.count('class="tm-res-tete tm-res-bloc"') == 4, g
        assert "t('time.tm_fw_titre')" in g

    def test_aucune_regle_neuve_ne_lit_l_accent_de_la_RACINE(self):
        """⚠️ `--pg-accent-soft` et ses frères sont déclarés sur `:root`, où
        `--pg-accent` vaut encore le gris par défaut : ils rendent du GRIS sur
        toute l'application."""
        import re
        css = _lire("static/time.css")
        bloc = re.sub(r"/\*.*?\*/", "", css[css.index("DIRECTION A"):], flags=re.S)
        for jeton in ("--pg-accent-soft", "--pg-accent-softer",
                      "--pg-accent-border", "--pg-accent-glow"):
            assert jeton not in bloc, jeton


class TestLaBandeColoree:
    """⚠️ Ce qui avait été livré d'abord n'était PAS la direction A : un filet
    de 3 px sur la carte, et des règles sur `.subcard` que les écrans Projet,
    Activité et Rôle N'ONT PAS — ils sont faits d'un `.form-grid` nu. Trois
    écrans sur quatre restaient donc blancs, et l'utilisateur a renvoyé une
    capture identique à l'avant. La couleur doit entrer par une SURFACE.
    """

    def test_la_bande_porte_la_couleur_du_type(self):
        css = _lire("static/time.css")
        i = css.index("LA BANDE")
        bloc = css[i:]
        j = bloc.index(".tm-barre {")
        regle = bloc[j:bloc.index("}", j)]
        assert "linear-gradient" in regle, regle
        assert "var(--tm-c)" in regle, regle
        assert "border-radius" in regle, regle

    def test_la_bande_dit_A_QUOI_SERT_l_analyse(self):
        """« Activité » tout seul ne distingue pas un écran de saisie d'un
        titre de page."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert 'id="tm-barre-sub"' in g
        js = _lire("static/js/time.js")
        assert "tl('sub_' + type" in js, "le sous-titre n'est pas rempli"

        from Code.translations import TRANSLATIONS
        for type_ in ("projet", "activite", "role", "faiblesse"):
            cle = "time.sub_%s" % type_
            for langue in ("fr", "en"):
                assert cle in TRANSLATIONS[langue], (cle, langue)
            assert TRANSLATIONS["fr"][cle] != TRANSLATIONS["en"][cle], cle

        g2 = _lire("Code/routes/templates/time_dashboard.html")
        for type_ in ("projet", "activite", "role", "faiblesse"):
            assert "sub_%s:" % type_ in g2, type_

    def test_la_zone_de_saisie_est_TEINTEE_y_compris_sans_sous_carte(self):
        """⚠️ LE cliquet de l'omission. `.form-grid` est la SEULE structure des
        écrans Projet, Activité et Rôle : absente de cette liste de sélecteurs,
        trois écrans sur quatre restent blancs — c'est exactement ce qui est
        arrivé, et l'utilisateur a renvoyé une capture identique à l'avant.

        ⚠️⚠️ Il a fallu TROIS écritures pour qu'il garde quelque chose :
          1. ancré sur le texte du commentaire qui explique la règle — or ce
             commentaire cite `.form-grid`, donc il lisait sa propre
             explication et restait VERT en retirant le sélecteur ;
          2. ancré sur un bout de corps (`6%`) que `.tm-tps-mode` partage, donc
             il regardait la mauvaise règle.
        On cherche la règle qui teinte les SOUS-CARTES, et on exige que
        `.form-grid` partage sa liste de sélecteurs.
        """
        import re
        css = re.sub(r"/\*.*?\*/", "", _lire("static/time.css"), flags=re.S)

        regles = [(sel.strip(), corps)
                  for sel, corps in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]
        teintes = [(sel, corps) for sel, corps in regles
                   if "#tm-travail" in sel and ".subcard" in sel
                   and "background" in corps and "--tm-c" in corps]
        assert teintes, "aucune règle ne teinte la zone de saisie"

        sel, corps = teintes[0]
        assert ".form-grid" in sel, (
            "la zone de saisie des écrans SANS sous-carte (Projet, Activité, "
            "Rôle) n'est pas teintée — sélecteurs : %r" % sel)
        assert "border-left" in corps, corps

    def test_le_bouton_primaire_prend_la_couleur_du_TYPE(self):
        """⚠️ Il lisait `--pg-accent` — l'accent de la PAGE, ambre pour Temps —
        d'où un bouton orange au bas d'un formulaire violet. Et son ombre
        lisait `--pg-accent-glow`, l'un des quatre dérivés qui rendent du GRIS
        sur `:root`."""
        css = _lire("static/time.css")
        i = css.index("#tm-travail .btn.success")
        regle = css[i:css.index("}", i)]
        assert "var(--tm-c)" in regle, regle
        assert "--pg-accent" not in regle, regle

    def test_le_panneau_de_droite_porte_la_couleur(self):
        css = _lire("static/time.css")
        i = css.index("#tm-travail .tm-res-tete.is-actif")
        regle = css[i:css.index("}", i)]
        assert "var(--tm-c)" in regle, regle
        assert "#tm-travail .tm-res-bloc .tm-grand { color: var(--tm-c); }" in css

    def test_la_pastille_ne_disparait_pas_dans_la_bande(self):
        """⚠️ Elle reprenait la couleur du type EN APLAT : sur une bande de la
        même couleur, elle s'effaçait. Il faut la même spécificité que la règle
        par type (#id + attribut + classe), déclarée plus bas."""
        css = _lire("static/time.css")
        i = css.index("#tm-travail .tm-barre .tm-barre-ic")
        regle = css[i:css.index("}", i)]
        assert "rgba(255, 255, 255" in regle, regle
        # Et elle doit venir APRÈS la règle par type, sinon elle ne gagne pas.
        assert i > css.index('#tm-travail[data-analyse="faiblesse"] .tm-barre-ic')


def test_aucune_balise_ne_s_affiche_en_clair():
    """⚠️ Deux descriptions portaient des `<em>` et étaient rendues SANS
    `| safe` : les balises s'affichaient TELLES QUELLES à l'écran. L'une
    datait d'avant, l'autre a été écrite le 03/11 — et le défaut ne s'est vu
    que sur une capture.

    RATCHET : retirer un `| safe` d'une clé qui porte une balise fait virer ce
    test au ROUGE.
    """
    import re
    from Code.translations import TRANSLATIONS
    g = _lire("Code/routes/templates/time_dashboard.html")
    rendu = re.compile(r"\{\{\s*t\('([a-z0-9_.]+)'\)\s*(\|\s*safe\s*)?\}\}")
    fautifs = []
    for m in rendu.finditer(g):
        cle, sauf = m.group(1), m.group(2)
        valeur = TRANSLATIONS["fr"].get(cle, "")
        if "<" in valeur and not sauf:
            fautifs.append(cle)
    assert not fautifs, (
        "ces libellés portent des balises et sont rendus sans `| safe` : "
        "elles s'afficheront en clair — %r" % (fautifs,))


# ══════════════════════════════════════════════════════════════════════════
#  L'AIDE D'UN CHAMP VIT DERRIÈRE UN « i »
# ══════════════════════════════════════════════════════════════════════════

AIDES_DU_FORMULAIRE = (
    "time.fw_hint_std_dur", "time.fw_hint_std_del", "time.fw_hint_desc",
    "time.fw_hint_extra", "time.fw_hint_delay", "time.fw_hint_freq",
    "time.fw_hint_prob", "time.fw_hint_mode",
)


def _css_propre():
    """⚠️ Commentaires retirés : un cliquet qui cherche une chaîne doit borner
    sa zone ET retirer les commentaires, sinon il lit sa propre explication.
    Le piège a mordu cinq fois dans ce dépôt."""
    import re
    return re.sub(r"/\*.*?\*/", "", _lire("static/time.css"), flags=re.S)


def _regle(css, selecteur):
    i = css.index(selecteur)
    return css[i:css.index("}", i)]


class TestLAideVitDerriereUnI:
    """« Au lieu d'écrire pour chaque saisie son explication au-dessous en
    petit, mets tout dans des i. » Six aides sous six champs du formulaire,
    puis dix sous dix chiffres des résultats : c'est la moitié de ce qui
    chargeait l'écran, pour du texte qu'on lit une fois."""

    def test_chaque_aide_passe_par_la_macro(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        for cle in AIDES_DU_FORMULAIRE:
            assert "aide('%s')" % cle in g, cle

    def test_plus_une_seule_aide_ECRITE_sous_un_champ(self):
        """⚠️ `#fw-del-note` survit, et c'est voulu : il dit POURQUOI la valeur
        a bougé toute seule. Ce n'est pas l'explication d'un champ, c'est une
        réaction à ce qu'on vient de taper — la cacher derrière un « i »
        cacherait une correction que l'utilisateur doit voir."""
        import re
        g = _lire("Code/routes/templates/time_dashboard.html")
        zone = g[g.index('id="subtab-faiblesse"'):g.index('id="fw-results-section"')]
        restantes = re.findall(r'class="field-hint[^"]*"', zone)
        assert len(restantes) == 1, (
            "il reste %d aide(s) écrite(s) sous un champ : %r"
            % (len(restantes), restantes))
        assert 'id="fw-del-note"' in zone

    def test_la_macro_rend_le_texte_SAFE(self):
        """⚠️ Sans `| safe`, les `<em>` de deux aides et les entités de deux
        autres s'afficheraient EN CLAIR — le défaut relevé le 07/11 sur une
        capture, ici pour huit libellés d'un coup."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        i = g.index("{% macro aide(cle)")
        j = g.index("{%- endmacro %}", i)
        assert "| safe" in g[i:j], g[i:j]

    def test_aucune_aide_ne_passe_par_un_ATTRIBUT_title(self):
        """⚠️ L'info-bulle du système sortirait par-dessus la nôtre, une
        seconde plus tard et sans sa mise en forme — et elle n'existe pas au
        clavier. Elle affichait de surcroît ses entités en clair : `&ldquo;`
        n'est pas décodé dans un attribut échappé."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "tm-tps-aide" not in g
        assert "title=\"{{ t('time.fw_hint" not in g

    def test_le_texte_reste_dans_l_arbre_d_accessibilite(self):
        """⚠️ `display: none` l'en retirerait : l'aide n'existerait plus que
        pour la souris."""
        corps = _regle(_css_propre(), ".tm-i-txt {")
        assert "clip" in corps, corps
        assert "display: none" not in corps, corps

    def test_la_bulle_ne_MULTIPLIE_pas_par_le_zoom(self):
        """⚠️⚠️ `getBoundingClientRect()` rend DÉJÀ des pixels d'écran. Le
        motif recopié de la page Compétences multiplie la hauteur par le zoom
        avant de la soustraire : mesuré, la bulle se posait 12 px TROP BAS —
        exactement sa hauteur fois (1 − 0,8), donc par-dessus son bouton.
        Seules les coordonnées qu'on ÉCRIT repassent par le zoom."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("function brancherAides"):
                  js.index("function majSchemaFaiblesse")]
        assert "b.height * z" not in bloc
        assert "b.width * z" not in bloc
        assert "/ z + 'px'" in bloc

    def test_la_bulle_ne_vole_pas_le_clic_de_ce_qu_elle_explique(self):
        assert "pointer-events: none" in _regle(_css_propre(), ".tm-bulle {")

    def test_un_i_TIENT_dans_son_libelle(self):
        """⚠⚠ Mesuré avant : un « i » de 17 px dans une ligne de 14,5 px
        débordait de **2,6 px** par le bas, se retrouvait à **0,0 px** du champ
        qui suit — donc il le TOUCHAIT — et était décentré de 3,8 px par
        rapport à son texte. Le libellé qui en porte un est donc une ligne
        FLEX : le badge est centré sur le texte au lieu d'être posé sur la
        ligne de base. Mesuré après : 0 débordement, 0 chevauchement, 0,0 px de
        décentrage, 4,6 px jusqu'au champ."""
        css = _css_propre()
        corps = _regle(css, "#tm-travail label:has(> .tm-i) {")
        assert "flex" in corps and "center" in corps, corps
        assert "vertical-align: -3px" not in css


# ══════════════════════════════════════════════════════════════════════════
#  LA SECTION RÉSULTATS D'UNE FAIBLESSE
# ══════════════════════════════════════════════════════════════════════════

class TestLaSectionResultatsDUneFaiblesse:
    """« On comprend très mal ce que l'on tente de mettre en exergue. »

    Mesure d'avant : quatre groupes de même poids, dix chiffres à 20 px, dix
    explications à 12 px (9,6 px RÉELS sous le `zoom: .8` du corps), et quatre
    accents décoratifs — rose, orange, rouge, violet. Rien ne ressortait, et
    surtout rien ne MONTRAIT le mécanisme.
    """

    def test_TOUS_les_id_que_le_JS_ecrit_survivent(self):
        """Le contrat : `time.js` écrit par id. On a changé le récit, pas le
        contrat."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        for cle in ("S", "T", "U", "V", "W", "X", "Y", "Z", "AA",
                    "fw-base-mois", "fw-results-empty", "fw-results-section"):
            assert 'id="%s"' % cle in g, cle

    def test_les_deux_lignes_du_schema_PARTAGENT_leurs_colonnes(self):
        """⚠️⚠️ Mesuré avec une grille par ligne : la colonne « livré en » de
        la ligne dégradée porte un « i » de plus, donc elle est plus large,
        donc son `1fr` est plus étroit — 720 px contre 743. Deux pistes de
        largeurs différentes ne se comparent pas, et c'est tout le propos d'un
        schéma à l'échelle."""
        css = _css_propre()
        assert "grid-template-columns" in _regle(css, ".fw-chrono {")
        assert "contents" in _regle(css, ".fw-l {")

    def test_le_travail_refait_DECALE_la_livraison(self):
        """⚠️⚠️ RENVERSEMENT du 13/11. `Y` valait `C + M`, et le travail
        refait était marqué à part « parce que le modèle ne le compte pas dans
        la livraison ». C'était faux : `T = C + (L+M)·O` le compte depuis
        toujours. Relevé à l'écran par l'utilisateur — 10 h de travail refait,
        4 h de délai standard, le panneau annonçait 14 h de délai moyen et le
        bilan « le résultat sort en 4 h au lieu de 4 h »."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("function majSchemaFaiblesse"):][:2600]
        assert "const total = C + L + M;" in bloc, bloc[:400]
        assert "pose('fw-sg-l-seg', L)" in bloc, bloc[:900]

    def test_un_segment_NUL_ne_se_dessine_pas(self):
        """⚠️ Le plancher rend visible une attente minuscule (une heure sur
        vingt-cinq) ; sans la classe `est-nul` il dessinerait aussi un segment
        pour une valeur de zéro."""
        css = _css_propre()
        assert "display: none" in _regle(css, ".fw-seg.est-nul {")
        assert "min-width" in _regle(css, ".fw-seg:not(.est-nul) {")
        assert "classList.toggle('est-nul', nul)" in _lire("static/js/time.js")

    def test_UN_SEUL_bloc_porte_la_couleur_du_type(self):
        """⚠️ Trois titres dans la couleur du type, c'est trois blocs de même
        poids — exactement le défaut qu'on venait de corriger. Un écran doit
        avoir UNE chose qu'on vient y lire : ici le coût annuel."""
        css = _css_propre()
        assert "var(--muted)" in _regle(css, ".fw-bloc-t {")
        assert "var(--tm-c)" in _regle(css, ".fw-bloc--an .fw-bloc-t {")

    def test_le_heros_est_PLUS_GRAND_que_le_second(self):
        import re
        css = _css_propre()

        def taille(sel):
            m = re.search(r"font-size:\s*([\d.]+)px", _regle(css, sel))
            assert m, sel
            return float(m.group(1))

        hero = taille(".fw-chif--l .fw-chif-v {")
        second = taille(".fw-chif--m .fw-chif-v {")
        assert hero > second, (hero, second)
        # Et au-dessus du plancher de 11 px RÉELS (le corps porte `zoom: .8`).
        assert second * 0.8 >= 11, second

    def test_la_regle_des_DEUX_NATURES_vit_derriere_le_i_de_SA_section(self):
        """⚠️ `time_view.py` l'interdit en toutes lettres — « DEUX natures,
        jamais additionnées » — et l'écran ne la disait nulle part. Elle vit
        derrière le « i » du titre du coût annuel : c'est cette section qui
        annonce les deux chiffres qu'on serait tenté d'additionner."""
        from Code.translations import TRANSLATIONS
        g = _lire("Code/routes/templates/time_dashboard.html")
        i = g.index("{{ t('time.fw_annual_header') }}")
        assert "aide('time.fw_jamais')" in g[i:i + 140], g[i:i + 180]
        assert "fw-jamais" not in g
        for lg in ("fr", "en"):
            assert TRANSLATIONS[lg].get("time.fw_jamais"), lg

    def test_la_legende_decrit_EXACTEMENT_ce_qui_est_sur_la_piste(self):
        """Une légende qui promet un remplissage absent envoie chercher ce qui
        n'existe pas ; une légende qui en oublie un laisse une couleur sans
        nom. On exige donc l'ÉGALITÉ des deux jeux — c'est ce qui a manqué
        quand le travail refait est passé sur la piste."""
        import re
        g = _lire("Code/routes/templates/time_dashboard.html")
        segments = set(re.findall(r"fw-seg fw-seg--(\w+)", g))
        temoins = set(re.findall(r"fw-pt fw-pt--(\w+)", g))
        assert segments == temoins, (segments, temoins)
        assert "l" in segments, "le travail refait est sur la piste"
        for suffixe in sorted(temoins):
            assert "t('time.fw_leg_%s')" % suffixe in g, suffixe

    def test_l_unite_n_est_plus_ecrite_DEUX_fois(self):
        """⚠️ `fmtH` rend déjà « 24.0h » : le `<span>h</span>` posé à côté
        affichait « 0.8h h ». Vu sur la capture, pas déduit."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "fw-kpi-unit" not in g

    def test_le_schema_LIT_ce_que_le_serveur_renvoie(self, app):
        """⚠️ `L` (travail refait) et `H` (exécutions de l'année) viennent du
        serveur : `delai_plancher` borne `C`, et `H` compte en semaines
        TRAVAILLÉES, pas en calendrier civil. Les recalculer dans le navigateur
        en ferait une seconde implémentation, et deux implémentations d'une
        même règle finissent par diverger."""
        from Code.routes.time_view import cout_faiblesse
        with app.app_context():
            m = cout_faiblesse(120, 1440, "journalier", 1, 60, 300, 1,
                               pct_proba=20)
        assert m["L"] == 60
        assert m["H"] > 0
        assert abs(m["AA"] - m["H"] * 0.20) < 1e-6
        js = _lire("static/js/time.js")
        assert "m['L']" in js and "m['H']" in js

    def test_les_libelles_du_schema_existent_dans_les_DEUX_langues(self):
        from Code.translations import TRANSLATIONS
        for cle in ("fw_sch_titre", "fw_sch_ok", "fw_sch_ko", "fw_sch_livre",
                    "fw_sch_fois", "fw_sch_sur", "fw_leg_b", "fw_leg_a",
                    "fw_leg_m", "fw_chip_l", "fw_chip_m", "fw_an_trav_s",
                    "fw_an_att_s", "fw_jamais", "fw_min_titre"):
            for lg in ("fr", "en"):
                assert TRANSLATIONS[lg].get("time." + cle), (cle, lg)
            assert (TRANSLATIONS["fr"]["time." + cle]
                    != TRANSLATIONS["en"]["time." + cle]), cle

    def test_le_decompte_suit_la_convention_de_CE_fichier(self):
        """⚠️ Deux conventions coexistent : `{x}`, résolue par `fmtPhrase` dans
        `time.js`, et `[[x]]`, celle de `acp.*` et `chat.*`. Une clé qui prend
        la mauvaise affiche son marqueur TEL QUEL, sans que rien ne lève."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            v = TRANSLATIONS[lg]["time.fw_sch_sur"]
            assert "{h}" in v, (lg, v)
            assert "[[" not in v, (lg, v)

    def test_le_decompte_est_INJECTE_dans_TIME_I18N(self):
        """Sans injection, `tl()` sert son repli — ici une chaîne vide, donc un
        décompte qui ne s'affiche jamais."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "fw_sch_sur:" in g
        assert "t('time.fw_sch_sur')|tojson" in g

    def test_le_separateur_decimal_suit_la_LANGUE(self):
        """⚠️ « Based on 45 weeks per year, i.e. 10,4 working months. » — la
        virgule décimale est une convention FRANÇAISE, posée en dur. Vu sur la
        capture anglaise."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("const brut = (sem"):][:260]
        assert "L.lang === 'en'" in bloc, bloc


class TestLeNomSeModifieLaOuOnLeCherche:
    """⚠️ « Je n'ai pas l'impression que l'on puisse modifier le nom d'une
    analyse » — il se modifiait depuis toujours, et les trois routes
    l'écrivent (d'autres cas de ce fichier le tiennent). C'était un défaut
    de DÉCOUVRABILITÉ, et il tenait à deux choses :

    · le champ ne portait qu'un `placeholder`, poussé tout à DROITE d'un
      en-tête par un `spacer` — et ouvert pour modification il est REMPLI,
      donc plus de placeholder non plus : une boîte de texte sans étiquette ;
    · le repère du haut portait un CRAYON et le nom, c'est-à-dire la
      promesse universelle d'un renommage, et la seule chose cliquable à
      côté était la croix qui QUITTE la modification.
    """

    def test_le_nom_porte_un_LIBELLE_et_non_un_simple_placeholder(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        for champ, cle in (("project-name", "time.project_name_label"),
                           ("role-name", "time.role_analysis_label"),
                           ("role-select", "time.role_label")):
            i = g.index('id="%s"' % champ)
            avant = g[max(0, i - 300):i]
            assert ('<label for="%s">' % champ) in avant, champ
            assert cle in avant, (champ, cle)

    def test_le_nom_a_quitte_l_en_tete_pousse_a_droite(self):
        """Un `card-head` dont le seul rôle était d'aligner à droite un champ
        sans étiquette. Le champ prend la première place du formulaire."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        for panneau, suivant in (("subtab-projet", "subtab-activite"),
                                 ("subtab-role", "subtab-faiblesse")):
            bloc = g[g.index('id="%s"' % panneau):g.index('id="%s"' % suivant)]
            assert 'class="tm-nom"' in bloc, panneau
            assert 'class="card-head"' not in bloc, panneau

    def test_le_repere_de_modification_MENE_au_champ_du_nom(self):
        """⚠️ Il MÈNE au champ, il ne porte pas une seconde saisie : le nom
        n'a qu'une source. Deux champs pour une même valeur finiraient par se
        contredire."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert '<button type="button" id="tm-mod-nom"' in g
        assert "t('time.tm_mod_nom')" in g
        js = _lire("static/js/time.js")
        i = js.index("const CHAMP_NOM")
        carte = js[i:js.index("}", i)]
        for type_, champ in (("projet", "#project-name"), ("role", "#role-name"),
                             ("faiblesse", "#fw-k")):
            assert type_ in carte and champ in carte, type_
        j = js.index("$('#tm-mod-nom')?.addEventListener")
        geste = js[j:j + 400]
        assert "champ.focus(" in geste and "champ.select()" in geste, geste

    def test_le_bouton_s_ETEINT_quand_il_n_y_a_pas_de_champ(self):
        """L'analyse d'activité n'a pas de nom : son identité, c'est
        l'activité choisie. Le bouton n'aurait nulle part où mener."""
        js = _lire("static/js/time.js")
        i = js.index("function majBandeauEdition")
        corps = js[i:js.index("  }", i)]
        assert "disabled = !CHAMP_NOM[edition.type]" in corps, corps

    def test_la_croix_garde_la_pastille_et_le_nom_NON(self):
        """⚠️ `.tm-mod button` visait TOUS les boutons du repère : le nom,
        devenu bouton, serait devenu une pastille ronde de 20 px."""
        css = _css_propre()
        # ⚠️ On vise la règle dont le sélecteur est EXACTEMENT
        # `.tm-mod button` : `.tm-barre .tm-mod button { color: #fff }` en
        # est une autre, voulue — c'est elle qui rend le nom lisible sur la
        # bande colorée.
        assert chr(10) + ".tm-mod button {" not in css
        assert "border-radius: 50%" in _regle(css, ".tm-mod #tm-mod-sortir {")
        nom = _regle(css, ".tm-mod > .tm-mod-nom {")
        assert "border-radius" not in nom, nom
        assert "text-overflow: ellipsis" in nom, nom


class TestSousUneHeureOnEcritDesMinutes:
    """⚠️ « Pourquoi les deux barres affichent 0.5h alors que la seconde
    compte l'attente ajoutée ? » — le schéma avait raison, c'est `fmtH` qui
    mentait. Reproduit : une attente d'UNE minute donne C = 30 et Y = 31, et
    les deux sortaient « 0.5h », la puce « + 0.0h », et le segment hachuré
    était bien dessiné — quatre signaux qui se contredisaient.
    """

    def test_fmtH_ecrit_des_MINUTES_sous_une_heure(self):
        js = _lire("static/js/time.js")
        i = js.index("function fmtH(min){")
        corps = js[i:js.index(chr(10) + "  }", i)]
        assert "< 60" in corps, corps
        assert "'min'" in corps, corps
        # Au-dessus de l'heure, rien ne change.
        assert "toFixed(1)+'h'" in corps, corps

    def test_on_arrondit_AVANT_de_choisir_l_unite(self):
        """Sinon 59,6 min sortirait « 60 min » juste à côté d'un « 1.0h »
        qui vaut la même chose."""
        js = _lire("static/js/time.js")
        i = js.index("function fmtH(min){")
        corps = js[i:js.index(chr(10) + "  }", i)]
        assert corps.index("Math.round(min)") < corps.index("< 60"), corps

    def test_une_minute_d_attente_DEPLACE_la_livraison(self, app):
        """La moitié SERVEUR du même fait : les deux bandes disent bien deux
        choses différentes, seul l'affichage les confondait.
        ⚠️ Le décor portait 90 min de travail refait et attendait `Y == C` :
        il encodait le `Y = C + M` d'avant. On regarde l'ÉCART."""
        from Code.routes.time_view import cout_faiblesse
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 48}
        sans = cout_faiblesse(30, 30, "hebdomadaire", 2, 90, 0, 2,
                              params=p, pct_proba=50)
        une = cout_faiblesse(30, 30, "hebdomadaire", 2, 90, 1, 2,
                             params=p, pct_proba=50)
        assert une["Z"] == 1
        assert une["Y"] - sans["Y"] == 1

    def test_les_en_tetes_n_annoncent_plus_des_HEURES(self):
        """La valeur porte désormais son unité : « Pesée (h) » au-dessus de
        « 35 min » redevenait le défaut qu'on venait de corriger. ⚠️ Les
        colonnes de SAISIE, elles, gardent la leur : le nombre y est nu."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            for cle in ("time.col_charge", "time.col_weight"):
                assert "(h)" not in TRANSLATIONS[lg][cle].lower(), (lg, cle)
            assert "(min)" in TRANSLATIONS[lg]["time.col_duration_min"], lg


class TestLesCinqCartesArbitrees:
    """Les cinq cartes du haut, tranchees sur maquette avant d'etre ecrites
    (canvas « Les cartes, une par une »). Ce qui suit garde les regles que
    chacune porte \u2014 pas son habillage."""

    # ───────────────────────────── carte 1 · deux etages
    def test_les_TROIS_rythmes_dont_le_jour_travaille(self):
        """« Par jour travaille » est le rythme qu'on se represente le mieux,
        et il manquait : la carte n'en donnait que deux."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        for ident in ("tm-charge-mois", "tm-charge-sem", "tm-charge-jour"):
            assert 'id="%s"' % ident in g, ident
        js = _lire("static/js/time.js")
        assert "quotidien_min" in js

    def test_le_serveur_envoie_la_charge_par_jour_travaille(self, auth_client):
        d = _tdb(auth_client)
        assert "quotidien_min" in d["charge"], d["charge"]
        c = d["calendrier"]
        if d["charge"]["annuel_min"]:
            attendu = (d["charge"]["annuel_min"]
                       / (float(c["weeks_per_year"]) * float(c["days_per_week"])))
            assert d["charge"]["quotidien_min"] == pytest.approx(attendu)

    def test_la_couverture_se_COMPTE_en_carres(self):
        """Une jauge a moitie pleine se lit « a moitie fait » ; douze carres
        dont six pleins se comptent.
        ⚠️ Le plafond valait 24, et une carto de 45 activites — la taille
        courante — n'avait donc AUCUNE pile. Les carres retrecissent ; c'est
        au-dela de soixante seulement que la barre prend le relais."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert 'id="tm-pile"' in g
        assert "tm-jauge" not in g, "la jauge a cede la place aux carres"
        js = _lire("static/js/time.js")
        # ⚠️ APPLIQUE, pas seulement declare : une constante qui ne sert
        # a rien ne plafonne rien.
        assert "n > PLAFOND_PILE" in js, "au-dela, on n'ose plus compter"
        assert "classList.toggle('est-barre'" in js
        assert "--pile-sq" in js, "la taille d'un carre suit le nombre"
        import re
        m = re.search(r"const PLAFOND_PILE = (\d+);", js)
        assert m, "le plafond doit rester lisible"
        assert int(m.group(1)) >= 45, (
            "une carto de 45 activites doit garder ses carres")

    # ───────────────────────────── carte 2 · la part, et sur quoi
    def test_chaque_barre_nomme_SON_tout(self):
        """⚠️ On n'additionne jamais le travail refait et l'attente ; mais
        sans dire de quoi chacun est un pourcentage, deux barres de tailles
        differentes laissent croire a une seule echelle."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            assert "{h}" in TRANSLATIONS[lg]["time.tm_part_de"], lg
            assert "{p}" in TRANSLATIONS[lg]["time.tm_part_de"], lg

    def test_le_bloc_gris_dit_ce_qu_on_GAGNERAIT(self):
        """Il portait une regle d'arithmetique, qui n'apprenait rien.
        ⚠️ Et le singulier ne se devine pas du pluriel : « si cette faiblesse
        etait levee » n'est pas « si ces 1 faiblesses etaient levees »."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            for cle in ("time.tm_gain", "time.tm_gain_1",
                        "time.tm_gain_att", "time.tm_gain_att_1"):
                assert cle in TRANSLATIONS[lg], (cle, lg)
            assert "{n}" not in TRANSLATIONS[lg]["time.tm_gain_1"]
            assert "{h}" in TRANSLATIONS[lg]["time.tm_gain_att"]
            assert "{h}" not in TRANSLATIONS[lg]["time.tm_gain"], (
                "sans attente, la seconde moitie parlerait de zero")
        js = _lire("static/js/time.js")
        assert "(attente ? 'tm_gain_att' : 'tm_gain')" in js

    # ───────────────────────────── carte 3 · l'ordre de grandeur
    def test_la_moyenne_porte_sur_les_ACTIVITES_mesurees(self, auth_client):
        """⚠️ Jamais sur le nombre d'ANALYSES : une meme activite peut en
        porter plusieurs, et la moyenne tomberait sous la charge reelle
        d'une activite.

        ⚠️ Le cas ne se joue QUE si une activite porte deux analyses :
        ailleurs les deux divisions donnent le meme chiffre, et le controle
        ne garde rien. On le fabrique donc."""
        from Code.models.models import Activities
        depart = _tdb(auth_client)
        temoin = (depart["couverture"]["a_chiffrer"] or depart["par_activite"])
        assert temoin, "la carto active n'a aucune activite"
        modele = db.session.get(
            Activities, temoin[0].get("id") or temoin[0]["activity_id"])
        neuve = Activities(name="TM-105-moyenne-deux-analyses",
                           entity_id=modele.entity_id)
        db.session.add(neuve)
        db.session.commit()
        ids = []
        try:
            for _ in range(2):
                r = auth_client.post("/temps/api/activity_workload", json={
                    "activity_id": neuve.id, "duration": 60,
                    "duration_unit": "minutes", "recurrence": "annuel",
                    "frequency": 1, "nb_people": 1})
                ids.append(json.loads(r.data)["id"])

            d = _tdb(auth_client)
            couv = d["couverture"]
            assert couv["chiffrees"] < len(d["par_activite"]), (
                "le decor doit porter plus d'ANALYSES que d'ACTIVITES mesurees")
            attendu = d["charge"]["annuel_min"] / couv["chiffrees"]
            assert couv["moyenne_min"] == pytest.approx(attendu)
        finally:
            for i in ids:
                auth_client.delete("/temps/api/activity_workload/%d" % i)
            db.session.delete(db.session.get(Activities, neuve.id))
            db.session.commit()

    def test_l_estimation_n_entre_dans_AUCUN_total(self, auth_client):
        """C'est une hypothese : elle est servie a part, et la charge
        annuelle reste celle des activites REELLEMENT mesurees.

        ⚠️ Il faut une activite chiffree ET une activite sans duree pour
        qu'il y ait quelque chose a extrapoler : sans moyenne, ou sur une
        carto entierement chiffree, le controle ne garderait rien. Le decor
        du fichier n'assure ni l'une ni l'autre — on les seme."""
        from Code.models.models import Activities
        depart = _tdb(auth_client)
        temoin = (depart["couverture"]["a_chiffrer"] or depart["par_activite"])
        assert temoin, "la carto active n'a aucune activite"
        modele = db.session.get(
            Activities, temoin[0].get("id") or temoin[0]["activity_id"])
        mesuree = Activities(name="TM-105-estimation-mesuree",
                             entity_id=modele.entity_id)
        vide = Activities(name="TM-105-estimation-sans-duree",
                          entity_id=modele.entity_id)
        db.session.add_all([mesuree, vide])
        db.session.commit()
        wid = None
        try:
            r = auth_client.post("/temps/api/activity_workload", json={
                "activity_id": mesuree.id, "duration": 120,
                "duration_unit": "minutes", "recurrence": "annuel",
                "frequency": 1, "nb_people": 1})
            wid = json.loads(r.data)["id"]

            d = _tdb(auth_client)
            couv = d["couverture"]
            assert couv["chiffrees"], couv
            assert couv["estime_min"], couv
            assert couv["ordre_min"] == pytest.approx(
                d["charge"]["annuel_min"] + couv["estime_min"])
            assert d["charge"]["annuel_min"] < couv["ordre_min"]
        finally:
            if wid:
                auth_client.delete("/temps/api/activity_workload/%d" % wid)
            for a in (mesuree, vide):
                db.session.delete(db.session.get(Activities, a.id))
            db.session.commit()

    def test_sans_rien_de_mesure_il_n_y_a_rien_a_extrapoler(self, auth_client, ids):
        """⚠️ NUL, pas zero : sans moyenne on ne peut rien en tirer, et un
        zero se lirait comme un resultat.

        ⚠️ Sur le COMPORTEMENT, pour la meme raison que le cas du plafond."""
        with _CartoJetable(auth_client, ids, 3):
            couv = _tdb(auth_client)["couverture"]
            assert couv["chiffrees"] == 0
            assert couv["moyenne_min"] is None, couv
            assert couv["estime_min"] is None, couv
            assert couv["ordre_min"] is None, couv
        js = _lire("static/js/time.js")
        assert "couv.ordre_min != null && reste > 0" in js

    def test_un_ordre_de_grandeur_ne_se_donne_pas_a_l_heure_pres(self):
        """« ~ 2 499 h ? » se contredit : le tilde annonce une approximation,
        le chiffre pretend le contraire. Deux chiffres significatifs."""
        js = _lire("static/js/time.js")
        assert "function ordreDeGrandeur(min){" in js
        bloc = js[js.index("function ordreDeGrandeur(min){"):][:420]
        assert "Math.log10" in bloc, bloc
        # et le grand chiffre comme le calcul annoncent le MEME nombre
        assert js.count("ordreDeGrandeur(couv.ordre_min)") == 2

    def test_le_calcul_est_ECRIT_et_il_a_son_singulier(self):
        """« Ce n'est pas une mesure » demandait de croire sur parole."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            for cle in ("time.tm_ordre_calc", "time.tm_ordre_calc_1"):
                p = TRANSLATIONS[lg][cle]
                assert "{m}" in p and "{e}" in p and "{o}" in p, (cle, lg)
            assert "{r}" not in TRANSLATIONS[lg]["time.tm_ordre_calc_1"]
        js = _lire("static/js/time.js")
        assert "reste === 1 ? 'tm_ordre_calc_1' : 'tm_ordre_calc'" in js

    def test_la_charge_s_ecrit_PAREIL_partout_ou_elle_est_citee_en_bloc(self):
        """La carte 1 ecrit « 1 250 » et `fmtH` « 1249.5h » : deux chiffres
        pour la meme grandeur, a deux centimetres l'un de l'autre."""
        js = _lire("static/js/time.js")
        assert "function fmtHr(min){" in js
        for appel in ("fmtHr(an)", "fmtHr(charge)", "fmtHr(total)",
                      "fmtHr(couv.estime_min)", "fmtHr(couv.moyenne_min)"):
            assert appel in js, appel

    # ───────────────────────────── carte 4 · la phrase
    def test_la_phrase_a_ses_TROIS_tournures(self):
        """⚠️ Elle ne s'ecrit jamais d'avance : un role peut depasser le temps
        plein, et il peut n'y en avoir qu'un — « le plus charge » n'aurait
        alors aucun sens."""
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            for cle in ("time.tm_role_ph", "time.tm_role_ph_1",
                        "time.tm_role_ph_sur"):
                assert cle in TRANSLATIONS[lg], (cle, lg)
        js = _lire("static/js/time.js")
        assert "p >= 100 ? 'tm_role_ph_sur'" in js
        assert "roles.length === 1 ? 'tm_role_ph_1' : 'tm_role_ph'" in js

    def test_le_nom_du_role_est_ECHAPPE(self):
        """Il part en innerHTML pour porter son `<b>` : `fmtPhrase` ne fait
        aucun echappement."""
        js = _lire("static/js/time.js")
        assert "nom: '<b>' + echap(top.nom) + '</b>'" in js

    # ───────────────────────────── carte 5 · le cumul
    def test_une_queue_d_UNE_activite_ne_se_reunit_pas(self):
        """Avec six activites pour six teintes, la sixieme devenait
        « + 1 autres » au lieu d'etre nommee."""
        js = _lire("static/js/time.js")
        assert "acts.length <= MAX_SEGMENTS" in js
        from Code.translations import TRANSLATIONS
        for lg in ("fr", "en"):
            assert "time.tm_cumul_autre" in TRANSLATIONS[lg], lg
            assert "{n}" not in TRANSLATIONS[lg]["time.tm_cumul_autre"], lg
        assert "reste.length === 1 ? 'tm_cumul_autre'" in js

    def test_la_phrase_des_trois_premieres_a_QUITTE_la_carte(self):
        """« Les trois premières font 79 % » : la barre le MONTRE, et la phrase
        prenait la place qui manquait à la barre et à sa légende.
        ⚠️ La clef part avec son seul lecteur : laissée au catalogue, elle
        serait une clef morte de plus à trier un jour."""
        from Code.translations import TRANSLATIONS
        js = _lire("static/js/time.js")
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "tm_act_trois" not in js
        assert "tm_act_trois" not in g
        assert "tm-act-pied" not in g
        for lg in ("fr", "en"):
            assert "time.tm_act_trois" not in TRANSLATIONS[lg], lg

    # ───────────────────────────── les deux langues
    def test_le_pourcentage_suit_la_LANGUE(self):
        """L'espace avant le % est une regle FRANCAISE : l'ecran anglais
        ecrivait « 5% of the load » a cote d'un « 4 % »."""
        js = _lire("static/js/time.js")
        assert "function pourCent(n){" in js
        bloc = js[js.index("function pourCent(n){"):][:200]
        assert "L.lang === 'en'" in bloc, bloc
        assert "\\u00a0%" not in js, "plus aucun % colle a la main"

    def test_toute_clef_lue_par_le_JS_est_injectee_et_traduite(self):
        """⚠️ `tl` rend la CLE quand elle manque : une clef oubliee s'affiche
        telle quelle a l'ecran, sans la moindre erreur. C'est ce silence
        qu'on ferme ici."""
        import re
        from Code.translations import TRANSLATIONS
        js = _lire("static/js/time.js")
        gab = _lire("Code/routes/templates/time_dashboard.html")
        # Les commentaires d'abord : un exemple cite n'est pas une lecture.
        net = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
        net = re.sub(r"//[^\n]*", "", net)
        # ⚠️ On ne cherche PAS les seuls appels `tl('x')` : une clef
        # choisie par un ternaire imbrique
        # (`p >= 100 ? 'a' : (n === 1 ? 'b' : 'c')`) y echappe, et la clef
        # oubliee s'affichait telle quelle a l'ecran. Toute chaine du JS qui
        # porte le nom d'une clef `time.*` du catalogue est une lecture.
        # ⚠️ Restreint a la famille de CET ecran : `loading` et `role`
        # coincident avec `time.loading` et `time.role` sans etre des
        # lectures, et un controle qui crie a tort n'est plus lu.
        connues = {c[len("time."):] for c in TRANSLATIONS["fr"]
                   if c.startswith("time.tm_") or c.startswith("time.fw_")}
        lues = {s for s in re.findall(r"'([a-z0-9_]+)'", net) if s in connues}
        lues |= set(re.findall(r"(?:tl|fmtPhrase)\(\s*'([a-z0-9_]+)'", net))
        for base in re.findall(r"'(tm_gain(?:_att)?)'", net):
            lues.update({base, base + "_1"})
        # Celles que le JS construit par concatenation, hors d'atteinte.
        lues -= {"sub_", "ok"}

        paires = dict(re.findall(
            r"^\s+([a-z0-9_]+):\s*\{\{ t\('([a-z0-9_.]+)'\)", gab, re.M))
        manquantes = sorted(c for c in lues if c not in paires)
        assert not manquantes, manquantes
        for nom, cle in paires.items():
            for lg in ("fr", "en"):
                assert cle in TRANSLATIONS[lg], (nom, cle, lg)

    def test_le_gabarit_ne_cite_que_des_clefs_qui_existent(self):
        import re
        from Code.translations import TRANSLATIONS
        gab = _lire("Code/routes/templates/time_dashboard.html")
        for cle in sorted(set(re.findall(r"t\('(time\.[a-z0-9_]+)'\)", gab))):
            for lg in ("fr", "en"):
                assert cle in TRANSLATIONS[lg], (cle, lg)

def _role_jetable(ids):
    """⚠️ Le decor commun ne porte pas de role : chaque cas cree le sien,
    rattache a l'activite du decor. Prendre `Role.query.first()` ferait
    dependre le cas d'un autre fichier joue avant."""
    from Code.models.models import Activities, Role, activity_roles
    ici = db.session.get(Activities, ids["activity_id"])
    role = Role(name="TM-105-jetable-%d" % (Role.query.count() + 1),
                entity_id=ici.entity_id)
    db.session.add(role)
    db.session.commit()
    db.session.execute(activity_roles.insert().values(
        activity_id=ici.id, role_id=role.id, status="Garant"))
    db.session.commit()
    return role


class TestLesRetoursDuTreizeNovembre:
    """Sept reproches releves a l'ecran par l'utilisateur, et ce qu'ils ont
    mis au jour : une contradiction dans le modele de la faiblesse, et une
    analyse de role qui s'enregistrait sans pouvoir jamais s'afficher."""

    # ─────────────────────────── le travail refait decale la livraison
    def test_Y_s_accorde_avec_le_delai_moyen_corrige(self, app):
        """⚠️⚠️ `T` est la moyenne de `C` (cas normal) et de `Y` (cas degrade),
        ponderee par `O` : `T = C + (Y - C)·O`. Ecrit `Y = C + M`, le modele
        se contredisait — et c'est ce que l'utilisateur a vu : 10 h de travail
        refait, 4 h de delai standard, le panneau annoncait 14 h de delai
        moyen pendant que le bilan disait « le resultat sort en 4 h au lieu
        de 4 h »."""
        from Code.routes.time_view import cout_faiblesse
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 45}

        # Les chiffres exacts de la capture : 2 h de duree, 4 h de delai,
        # 10 h de travail refait, aucune attente, 100 %.
        m = cout_faiblesse(120, 240, "journalier", 1, 600, 0, 1,
                           params=p, pct_proba=100)
        assert m["Y"] == 840, "4 h + 10 h = 14 h"
        assert m["T"] == 840

        for L, M, pct in ((600, 0, 100), (90, 30, 50), (0, 45, 25), (240, 240, 80)):
            c = cout_faiblesse(120, 240, "hebdomadaire", 2, L, M,
                               1, params=p, pct_proba=pct)
            assert c["Y"] == c["C"] + L + M, (L, M, pct)
            assert c["T"] == pytest.approx(c["C"] + (c["Y"] - c["C"]) * c["O"]), (L, M, pct)

    def test_le_cumul_annuel_compte_chaque_minute_UNE_fois(self, app):
        """⚠️ `Y` change, pas `U` ni `V` : le correctif du 03/11 tient. Le
        travail refait et l'attente ne s'additionnent jamais dans le total de
        l'accueil, et c'est une autre question que celle de la livraison."""
        from Code.routes.time_view import cout_faiblesse
        p = {"hours_per_day": 7, "days_per_week": 5, "weeks_per_year": 45}
        m = cout_faiblesse(120, 240, "hebdomadaire", 2, 90, 30, 1,
                           params=p, pct_proba=50)
        assert m["U"] == pytest.approx(90 * m["P"])
        assert m["V"] == pytest.approx(30 * m["P"])
        assert m["U"] + m["V"] == pytest.approx((90 + 30) * m["P"])

    # ─────────────────────────── l'analyse de role s'affiche enfin
    def test_les_roles_offerts_sont_ceux_de_la_carto(self, auth_client, ids):
        """⚠️ `Role.query.all()` listait TOUS les roles de l'entreprise :
        depuis qu'ils sont communs (23/09), un role peut n'en tenir aucune
        ici. On choisissait alors un role qui ne tient rien, la table restait
        vide, l'analyse s'enregistrait sans ligne — et le tableau de bord,
        qui ne montre que ce qui porte sur cette carto, n'affichait jamais
        rien. L'ecran disait « enregistree » et il ne se passait rien."""
        from Code.models.models import Activities, Entity, Role, activity_roles
        from Code.routes.time_view import roles_de_la_carto

        ailleurs = Entity(name="TM-105-ROLE-AILLEURS", owner_id=ids["user_id"])
        db.session.add(ailleurs)
        db.session.commit()
        a_ailleurs = Activities(name="TM-105-activite-ailleurs", entity_id=ailleurs.id)
        ici = db.session.get(Activities, ids["activity_id"])
        db.session.add(a_ailleurs)
        db.session.commit()

        r_ici = Role(name="TM-105-role-ici", entity_id=ici.entity_id)
        r_ailleurs = Role(name="TM-105-role-ailleurs", entity_id=ailleurs.id)
        db.session.add_all([r_ici, r_ailleurs])
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=ici.id, role_id=r_ici.id, status="Garant"))
        db.session.execute(activity_roles.insert().values(
            activity_id=a_ailleurs.id, role_id=r_ailleurs.id, status="Garant"))
        db.session.commit()
        try:
            noms = {r.name for r in roles_de_la_carto([ici.id])}
            assert "TM-105-role-ici" in noms
            assert "TM-105-role-ailleurs" not in noms
            # Et une carto sans activite n'offre aucun role.
            assert roles_de_la_carto([]) == []

            # ⚠️ Et c'est bien ce que la PAGE offre : un cas qui n'appelle
            # que l'aide laisserait la route revenir a `Role.query.all()`
            # sans rien dire. On lit le selecteur rendu.
            page = auth_client.get("/temps/").data.decode("utf-8")
            bloc = page[page.index('id="role-select"'):]
            bloc = bloc[:bloc.index("</select>")]
            assert "TM-105-role-ici" in bloc
            assert "TM-105-role-ailleurs" not in bloc
        finally:
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.role_id.in_([r_ici.id, r_ailleurs.id])))
            for o in (r_ici, r_ailleurs, a_ailleurs, ailleurs):
                db.session.delete(db.session.get(type(o), o.id))
            db.session.commit()

    def test_les_activites_d_un_role_sont_CADREES_sur_la_carto(self, auth_client, ids):
        """Un role est commun a l'entreprise : sans ce filtre, une analyse
        pouvait se batir entierement sur les activites d'une AUTRE carto et
        disparaissait aussitot du tableau de bord."""
        from Code.models.models import Activities, Entity, Role, activity_roles

        ailleurs = Entity(name="TM-105-CADRE-AILLEURS", owner_id=ids["user_id"])
        db.session.add(ailleurs)
        db.session.commit()
        ici = db.session.get(Activities, ids["activity_id"])
        a_ailleurs = Activities(name="TM-105-cadre-ailleurs", entity_id=ailleurs.id)
        db.session.add(a_ailleurs)
        db.session.commit()
        role = Role(name="TM-105-role-des-deux", entity_id=ici.entity_id)
        db.session.add(role)
        db.session.commit()
        for a in (ici, a_ailleurs):
            db.session.execute(activity_roles.insert().values(
                activity_id=a.id, role_id=role.id, status="Garant"))
        db.session.commit()
        try:
            r = auth_client.get("/temps/api/role_activities/%d" % role.id)
            assert r.status_code == 200
            rendus = {a["id"] for a in json.loads(r.data)["activities"]}
            assert ici.id in rendus
            assert a_ailleurs.id not in rendus, "l'autre carto n'a rien a faire ici"
        finally:
            db.session.execute(activity_roles.delete().where(
                activity_roles.c.role_id == role.id))
            for o in (role, a_ailleurs, ailleurs):
                db.session.delete(db.session.get(type(o), o.id))
            db.session.commit()

    def test_une_analyse_de_role_SANS_LIGNE_est_refusee(self, auth_client, ids):
        """⚠️ Elle ne pouvait apparaitre nulle part — `any()` sur une liste
        vide est faux. On l'enregistrait quand meme, l'ecran annoncait
        « enregistree », et rien ne se voyait. Un enregistrement silencieux
        qui se felicite est pire qu'un refus."""
        from Code.models.models import TimeRoleAnalysis
        role = _role_jetable(ids)
        avant = TimeRoleAnalysis.query.count()
        r = auth_client.post("/temps/api/role_analysis",
                             json={"role_id": role.id,
                                   "name": "TM-105-vide", "lines": []})
        assert r.status_code == 400, r.data
        assert json.loads(r.data)["code"] == "aucune_ligne"
        assert TimeRoleAnalysis.query.count() == avant, "rien n'est ecrit"

    def test_un_PATCH_qui_VIDERAIT_l_analyse_est_refuse(self, auth_client, ids):
        """Le renommage seul reste possible (`lines` absent ne touche a
        rien) ; une liste VIDE, elle, ferait disparaitre l'analyse du tableau
        de bord sans qu'on l'ait supprimee."""
        from Code.models.models import TimeRoleAnalysis, TimeRoleLine
        role = _role_jetable(ids)
        r = auth_client.post("/temps/api/role_analysis", json={
            "role_id": role.id, "name": "TM-105-patch",
            "lines": [{"activity_id": ids["activity_id"], "duration": 30,
                       "recurrence": "annuel", "frequency": 1}]})
        rid = json.loads(r.data)["id"]
        try:
            vide = auth_client.patch("/temps/api/role_analysis/%d" % rid,
                                     json={"lines": []})
            assert vide.status_code == 400, vide.data
            assert TimeRoleLine.query.filter_by(role_analysis_id=rid).count() == 1
            # Le renommage seul passe toujours.
            ok = auth_client.patch("/temps/api/role_analysis/%d" % rid,
                                   json={"name": "TM-105-renomme"})
            assert ok.status_code == 200, ok.data
            assert db.session.get(TimeRoleAnalysis, rid).name == "TM-105-renomme"
        finally:
            auth_client.delete("/temps/api/role_analysis/%d" % rid)

    # ─────────────────────────── les deux unites d'une meme section
    def test_les_unites_se_lient_dans_UN_SEUL_sens(self):
        """Une duree en heures a cote d'un delai en minutes se lit de travers.
        ⚠️ La PREMIERE regle la seconde, jamais l'inverse : dans les deux sens
        les deux s'annuleraient, et on ne pourrait plus jamais mettre deux
        unites differentes."""
        js = _lire("static/js/time.js")
        i = js.index("[['#fw-dur-unit', '#fw-del-unit'], ['#fw-l-unit', '#fw-m-unit']]")
        bloc = js[i:i + 700]
        assert "b.value = a.value" in bloc, bloc
        assert "a.value = b.value" not in bloc, "le second ne regle pas le premier"
        # ⚠️ Poser `.value` ne declenche rien : sans cet evenement, le calcul
        # de la faiblesse ne repartirait pas.
        assert "dispatchEvent(new Event('change', { bubbles: true }))" in bloc

    # ─────────────────────────── la carte 1
    def test_l_equivalent_temps_plein_a_QUITTE_la_carte_1(self):
        from Code.translations import TRANSLATIONS
        g = _lire("Code/routes/templates/time_dashboard.html")
        js = _lire("static/js/time.js")
        assert 'id="tm-etp"' not in g
        assert "tm_etp" not in js
        for lg in ("fr", "en"):
            assert "time.tm_etp" not in TRANSLATIONS[lg], lg
            assert "time.tm_etp_pl" not in TRANSLATIONS[lg], lg

    def test_le_calendrier_de_travail_est_en_PASTILLES(self):
        """⚠️ Il etait ecrit en 13 px sous le titre — 10,4 px reels sous le
        `zoom: .8` du corps. C'est pourtant la BASE de tous les chiffres de
        la page : changez une des trois valeurs et l'ecran entier bouge."""
        from Code.translations import TRANSLATIONS
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert g.count('class="tm-cal-i"') == 3
        css = _css_propre()
        assert "var(--pg-font-display" in _regle(css, ".tm-cal-i b {")
        for lg in ("fr", "en"):
            for cle in ("tm_cal_sem", "tm_cal_jours", "tm_cal_heures"):
                assert TRANSLATIONS[lg].get("time." + cle), (lg, cle)
        # La ligne d'avant et sa clef sont parties ensemble.
        js = _lire("static/js/time.js")
        assert "tm_base" not in js
        for lg in ("fr", "en"):
            assert "time.tm_base" not in TRANSLATIONS[lg], lg

    def test_la_carte_phare_a_du_RELIEF(self):
        """⚠️ Quatre ombres portees empilees (la lumiere n'en fait pas une
        seule, nette) plus deux aretes internes.
        ⚠️ Pas de `transform` : il ferait de la carte le repere des
        descendants `position: fixed` — les bulles d'aide et le panneau des
        listes sont poses sur le BODY."""
        css = _css_propre()
        regle = _regle(css, ".tm-carte--phare {")
        ombre = [d for d in regle.split(";") if "box-shadow" in d]
        assert ombre, regle
        couches = [c for c in ombre[0].split(",") if "px" in c]
        # Deux aretes internes (le haut eclaire, le bas dans l'epaisseur) et
        # quatre ombres portees : la lumiere n'en fait pas UNE seule, nette.
        assert ombre[0].count("inset ") >= 2, ombre[0]
        assert len(couches) >= 6, couches
        assert "transform" not in regle, regle

    # ─────────────────────────── la carte 4
    def test_l_etat_vide_du_role_est_un_BLOC(self):
        """⚠️ C'etait une ligne grise de 12 px collee en haut a gauche d'une
        carte haute : on la lisait comme un defaut de chargement, et elle ne
        disait pas quoi faire.
        ⚠️ `[hidden]` est une regle du NAVIGATEUR : une classe d'auteur qui
        pose un `display` l'emporte. Sixieme fois que ce piege se presente."""
        from Code.translations import TRANSLATIONS
        g = _lire("Code/routes/templates/time_dashboard.html")
        js = _lire("static/js/time.js")
        assert 'id="tm-role-vide"' in g
        assert "tm-vide-b" in g
        assert "vide.hidden = roles.length > 0" in js
        css = _css_propre()
        assert "display: none" in _regle(css, ".tm-vide[hidden] {")
        for lg in ("fr", "en"):
            for cle in ("tm_vide_role", "tm_vide_role_s", "tm_vide_role_b"):
                assert TRANSLATIONS[lg].get("time." + cle), (lg, cle)

    # ─────────────────────────── la carte 5
    def test_la_rampe_s_ETALE_sur_le_nombre_de_segments(self):
        """⚠️ Figee a six teintes, trois activites n'en prenaient que les
        trois premieres — trois violets voisins, dont on ne distinguait pas
        les segments. On interpole le long de la rampe ENTIERE."""
        js = _lire("static/js/time.js")
        assert "const TEINTES =" not in js, "la liste figee est partie"
        assert "function teintes(n){" in js
        bloc = js[js.index("function teintes(n){"):][:600]
        # Les DEUX bouts : `n - 1` au denominateur et toute la rampe au
        # numerateur. Sans l'un des deux, la rampe ne s'etale pas.
        assert "(n - 1)" in bloc, bloc
        assert "(bouts.length - 1)" in bloc, bloc
        assert len(_lire("static/js/time.js").split("const RAMPE = [")[1]
                   .split("]")[0].split(",")) >= 4

    # ─────────────────────────── les listes deroulantes
    def test_le_SELECT_reste_la_source_de_verite(self):
        """⚠️ Une quinzaine d'endroits lisent `.r-rec select` et ecrivent
        `$('#fw-dur-unit').value` : les reprendre un par un serait quinze
        occasions d'en oublier un. Le `<select>` est masque, jamais retire —
        et la propriete est interceptee SUR L'ELEMENT, jamais sur le
        prototype, qui vaudrait pour toute l'application."""
        js = _lire("static/js/tm_select.js")
        assert "HTMLSelectElement.prototype" in js
        assert "Object.defineProperty(sel, 'value'" in js
        assert "Object.defineProperty(HTMLSelectElement.prototype" not in js
        css = _css_propre()
        assert "display: none" not in _regle(css, ".tms > select {")

    def test_la_liste_emet_LES_DEUX_evenements(self):
        """Un `<select>` natif emet `input` ET `change`, et la page ecoute
        tantot l'un (la table des roles recalcule sur `input` pose sur le
        `<tr>`) tantot l'autre (le calcul de la faiblesse est delegue depuis
        `#subtab-faiblesse`). N'en emettre qu'un casserait l'autre moitie."""
        js = _lire("static/js/tm_select.js")
        i = js.index("function choisir(o, i) {")
        bloc = js[i:i + 900]
        for ev in ("input", "change"):
            assert ("new Event('%s', { bubbles: true })" % ev) in bloc, ev

    def test_le_panneau_fait_la_CONVERSION_DE_ZOOM(self):
        """⚠️ `body.pg` porte `zoom: .8` : un enfant du body en `fixed` voit
        ses coordonnees MULTIPLIEES par ce zoom, alors que
        `getBoundingClientRect()` les rend deja en pixels d'ecran. Sixieme
        fois que ce piege se presente dans cette application."""
        js = _lire("static/js/tm_select.js")
        assert "getComputedStyle(document.body).zoom" in js
        i = js.index("function placer(o) {")
        bloc = js[i:i + 700]
        assert "r.left / z" in bloc, bloc
        assert "r.bottom + 6) / z" in bloc, bloc
        # Et il se referme sur tout ce qui deplace ce qu'il y a dessous —
        # sauf son propre defilement : voir le cliquet dedie plus bas.
        assert "window.addEventListener('scroll', function (e) {" in js
        assert "window.addEventListener('resize', fermer)" in js

    def test_les_lignes_creees_APRES_le_chargement_sont_habillees(self):
        """Les lignes des tableaux et le selecteur d'activite d'une faiblesse
        naissent apres le chargement : un balayage unique n'en verrait
        aucun."""
        js = _lire("static/js/tm_select.js")
        # ⚠️ Celui de la PAGE : il y en a un second sur les options d'un
        # select, et chercher « new MutationObserver » tout court laissait
        # passer un observateur de page debranche.
        assert "observe(document.getElementById('page-temps')" in js
        assert "{ childList: true, subtree: true }" in js

    # ─────────────────────────── les deux langues
    def test_plus_aucun_libelle_de_retour_n_est_ecrit_EN_DUR(self):
        """Six `flashFeedback` portaient leur phrase en francais dans le code :
        elles s'affichaient telles quelles sur l'ecran anglais."""
        from Code.translations import TRANSLATIONS
        js = _lire("static/js/time.js")
        for mort in ("Analyse activit", "Analyse r\u00f4le enregistr",
                     "Projet enregistr", "Erreur d'enregistrement",
                     "Erreur de mise", "'Analyse r\u00f4le'"):
            assert mort not in js, mort
        for lg in ("fr", "en"):
            for cle in ("save_error", "update_error", "saved_project",
                        "saved_activity", "updated_activity", "role_saved",
                        "role_sans_ligne"):
                assert TRANSLATIONS[lg].get("time." + cle), (lg, cle)

    def test_le_bouton_du_calendrier_mene_au_bloc_qui_le_REGLE(self):
        """Il menait « simplement en haut de la page RH » : le bandeau est
        bien la, mais rien ne le designait. ⚠️ Un ancrage HTML ne suffit pas —
        ce bandeau est construit en JS, l'element n'existe pas au
        chargement."""
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert 'href="/gestion_rh/#calendrier"' in g
        rh = _lire("static/js/gestion_rh.js")
        assert "location.hash === '#calendrier'" in rh
        assert "est-pointe" in rh
        assert "est-pointe" in _lire("static/gestion_rh.css")


# ══════════════════════════════════════════════════════════════════════════
#  Le déroulant dessiné : on ne pouvait pas y défiler, et son accent était
#  l'ambre de la page pour les quatre types de formulaire.
#
#  « C'est top, seulement on ne peut pas scroller dedans cela le ferme
#  direct. » · « Si à la place de la touche orange tu peux adapter la couleur
#  à celle des quatre types, genre pour les faiblesses le déroulant sera
#  rouge. »
# ══════════════════════════════════════════════════════════════════════════
class TestLeDeroulantSeDefileEtSuitLeType:

    def test_defiler_DANS_le_panneau_ne_le_referme_PAS(self):
        """⚠️ `scroll` en CAPTURE voyait TOUS les defilements, y compris celui
        du panneau : il se refermait des qu'on y defilait. Et meme tout seul a
        l'ouverture d'une longue liste — `viser()` appelle `scrollIntoView`,
        qui fait defiler le panneau quand l'option choisie est sous le pli, et
        le defilement arrive une image plus tard.
        ⚠️ Le `true` reste : un evenement `scroll` ne REMONTE pas, seule la
        phase de capture le voit."""
        js = _lire("static/js/tm_select.js")
        assert "window.addEventListener('scroll', fermer, true)" not in js
        i = js.index("window.addEventListener('scroll'")
        bloc = js[i:js.index("}, true);", i)]
        assert "ouvert.panneau" in bloc, bloc
        assert "closest('.tms-p')" in bloc, bloc
        assert "fermer();" in bloc, bloc

    def test_le_panneau_garde_le_geste_au_BOUT_de_son_defilement(self):
        """Arrive en bas de SON defilement, il passait la main a la page — qui
        defile, et le referme."""
        # ⚠️ Ancre sur le SAUT DE LIGNE : la declaration du jeton
        # (`.tms, .tms-p { --tms-a: ... }`) contient elle aussi « .tms-p { »,
        # et `_regle` lisait cette regle-la — vert sur le defaut meme.
        regle = _regle(_css_propre(), ".tms-p {" + chr(10))
        assert "overscroll-behavior: contain" in regle, regle
        assert "overflow-y: auto" in regle, regle

    def test_l_accent_du_deroulant_suit_le_TYPE_du_formulaire(self):
        """Les quatre formulaires ont leur couleur (`--tm-c`, posee par
        `#tm-travail[data-analyse]`) ; le deroulant, lui, prenait l'accent de
        la PAGE — l'ambre du role — meme dans le formulaire d'une faiblesse."""
        css = _css_propre()
        assert ".tms, .tms-p { --tms-a: var(--tm-c, var(--pg-accent)); }" in css
        # ⚠️ Zone BORNEE au bloc du deroulant : `var(--pg-accent)` est partout
        # ailleurs dans cette feuille, et un cliquet qui cherche une chaine
        # sans borner sa zone trouve presque toujours un homonyme.
        bloc = css[css.index(".tms, .tms-p { --tms-a"):css.index("td > .tms,")]
        reste = bloc.replace("var(--tm-c, var(--pg-accent))", "")
        assert "var(--pg-accent" not in reste, reste
        for etat in (".tms-b:hover", ".tms-o.est-vise"):
            assert "var(--tms-a)" in _regle(bloc, etat), etat

    def test_le_panneau_recoit_l_accent_CALCULE(self):
        """⚠️ Il est pose sur le BODY : il vit hors de `#tm-travail` et
        n'herite donc pas de `--tm-c`. Sans recopie, un panneau de faiblesse
        s'ouvrait en ambre sous un bouton rouge."""
        js = _lire("static/js/tm_select.js")
        i = js.index("function ouvrir(sel, bouton) {")
        bloc = js[i:js.index("document.body.appendChild(panneau);", i)]
        assert "getPropertyValue('--tms-a')" in bloc, bloc
        assert "panneau.style.setProperty('--tms-a'" in bloc, bloc
