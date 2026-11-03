# -*- coding: utf-8 -*-
"""Une liste de petites choses qui n'allaient pas, relevées à l'usage.

Elles n'ont pas de sujet commun — ce sont des écrans différents — mais elles
ont toutes la même forme : un détail qui ment, ou qui n'est pas possible.
Chacune a son cliquet ici, et chacun a été vérifié ROUGE avant d'être gardé.

Ce qui tient ailleurs, et qu'on ne redit pas :
  • le rail de l'accueil de la page Temps → `test_105::test_le_rail_MONTRE…`
  • la flèche sans libellé ne produit plus de sortie → `test_51`
"""
import io
import os

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(rel):
    return io.open(os.path.join(RACINE, *rel.split("/")), encoding="utf-8").read()


# ════════════════════════════════════════════════════════════════════════
#  Les unités de durée
# ════════════════════════════════════════════════════════════════════════
class TestLesUnitesDeDuree:
    """« On a j pour jour mais cela doit être day sur la version anglaise. »

    Deux défauts distincts derrière ce symptôme : l'écran Temps d'une activité
    écrivait ses unités EN DUR, et la page Temps envoyait au serveur le texte
    de l'option — donc le mot anglais, que le serveur lit comme des minutes.
    """

    def test_les_selecteurs_de_la_fiche_activite_passent_par_le_catalogue(self):
        g = _lire("Code/routes/templates/activity_time_new.html")
        # Les deux sélecteurs de l'onglet « Durée globale » : six options.
        assert g.count("{{ t('acttime.unit_day') }}") >= 4, g.count("unit_day")
        assert ">j</option>" not in g
        assert ">min</option>" not in g

    def test_le_jour_se_dit_day_en_anglais(self):
        from Code.translations import t
        assert t("acttime.unit_day", "en") == "day"
        assert t("acttime.unit_day", "fr") == "j"
        assert t("time.unit_days", "en") == "day"
        assert t("time.unit_hours", "en") == "hrs"

    def test_les_unites_de_la_page_temps_sont_abregees(self):
        """« Mettre min hrs day au lieu du nom complet. »"""
        from Code.translations import t
        for langue, attendu in (("fr", ("min", "h", "j")),
                                ("en", ("min", "hrs", "day"))):
            rendu = (t("time.unit_minutes", langue), t("time.unit_hours", langue),
                     t("time.unit_days", langue))
            assert rendu == attendu, (langue, rendu)

    def test_chaque_option_dunite_porte_sa_valeur(self):
        """⚠️ Le défaut de fond. Sans attribut `value`, la valeur d'une option
        EST son texte : en anglais, choisir « hours » envoyait « hours », que
        `UNIT_TO_MIN.get(…, 1)` lit comme des MINUTES. Toute la page Temps
        comptait soixante fois trop peu, en silence, dans cette langue.
        """
        g = _lire("Code/routes/templates/time_dashboard.html")
        assert "<option>{{ t('time.unit_minutes') }}</option>" not in g
        assert g.count("<option value=\"minutes\">{{ t('time.unit_minutes') }}</option>") == 5
        assert g.count("<option value=\"heures\">{{ t('time.unit_hours') }}</option>") == 5
        assert g.count("<option value=\"jours\">{{ t('time.unit_days') }}</option>") == 5

    def test_les_valeurs_envoyees_restent_celles_que_le_serveur_connait(self):
        from Code.routes.time_view import UNIT_TO_MIN
        g = _lire("Code/routes/templates/time_dashboard.html")
        for cle in UNIT_TO_MIN:
            assert ('<option value="%s">' % cle) in g, cle


# ════════════════════════════════════════════════════════════════════════
#  Les contraintes passent SOUS les connexions
# ════════════════════════════════════════════════════════════════════════
def test_les_contraintes_sont_sous_les_connexions():
    """Côte à côte (2fr / 1fr), chaque libellé de connexion se repliait sur
    deux ou trois lignes et une contrainte sur quatre ou cinq. L'une sous
    l'autre, les deux ont toute la largeur de la carte."""
    css = _lire("static/activities_list.css")
    i = css.index(".overview-side-by-side {")
    regle = css[i:css.index("}", i)]
    assert "grid-template-columns: minmax(0, 1fr)" in regle, regle
    assert "2fr 1fr" not in regle, regle


# ════════════════════════════════════════════════════════════════════════
#  Le rôle d'une tâche, dans la langue de l'écran
# ════════════════════════════════════════════════════════════════════════
class TestLeRoleDUneTacheSeLitDansLaLangueDeLEcran:
    """« On choisit Doer / Approver en anglais, et ça repasse en français une
    fois validé. »

    La valeur STOCKÉE est la chaîne française : c'est elle que le serveur
    renvoie et elle qui porte la classe CSS du badge. Seul l'AFFICHAGE suit
    la langue — la même règle que les niveaux HSC.
    """

    FICHIERS = ("static/js/tasks.js", "static/js/tasks_roles.js")

    @pytest.mark.parametrize("fichier", FICHIERS)
    def test_le_badge_passe_par_le_traducteur(self, fichier):
        js = _lire(fichier)
        assert "${roleStatusLabel(role.status)}</span>" in js
        assert "${role.status}</span>" not in js

    @pytest.mark.parametrize("fichier", FICHIERS)
    def test_le_traducteur_est_declare_dans_les_deux_fichiers(self, fichier):
        """⚠️ `tasks_roles.js` est chargé APRÈS `tasks.js` et redéfinit cinq de
        ses fonctions : c'est lui qui gagne au rendu. Corriger un seul des deux
        laisse la moitié du défaut. Et `function`, pas `const` : un `const`
        répété dans deux fichiers de la même portée lève une SyntaxError."""
        js = _lire(fichier)
        assert "function roleStatusLabel(" in js
        assert "const roleStatusLabel" not in js

    def test_les_quatre_libelles_sont_injectes(self):
        g = _lire("Code/routes/templates/tasks_partial.html")
        for cle in ("role_doer", "role_advisor", "role_approver", "role_resource"):
            assert ("%s:" % cle) in g, cle
            assert ("t('task.%s')|tojson" % cle) in g, cle

    def test_la_valeur_stockee_reste_francaise(self):
        """Elle porte la classe CSS du badge, et des lignes sont déjà en base."""
        g = _lire("Code/routes/templates/tasks_partial.html")
        for valeur in ("Réalisateur", "Conseil", "Approbateur", "Ressource"):
            assert ('<option value="%s">' % valeur) in g, valeur


# ════════════════════════════════════════════════════════════════════════
#  Supprimer un rôle : l'administrateur, et lui seul
# ════════════════════════════════════════════════════════════════════════
class TestSupprimerUnRoleEstReserveALAdministrateur:
    """Un rôle est commun à l'entreprise : le supprimer emporte ses
    titulaires, ses liens aux activités et aux tâches de TOUTES les cartos, et
    l'accès qu'il ouvrait. Renommer reste permis — c'est réversible."""

    @pytest.fixture
    def role_jetable(self, app, ids):
        from Code.models.models import Role
        with app.app_context():
            r = Role(name="T128 Jetable", entity_id=ids["entity_id"])
            db.session.add(r)
            db.session.commit()
            rid = r.id
        yield rid
        with app.app_context():
            x = db.session.get(Role, rid)
            if x is not None:
                db.session.delete(x)
                db.session.commit()

    def _en_tant_que(self, app, client, statut):
        from Code.models.models import User
        from Code.security import hash_password
        with app.app_context():
            u = User(first_name="T128", last_name=statut,
                     email="t128.%s@test" % statut,
                     password=hash_password("Test1234!"), status=statut)
            db.session.add(u)
            db.session.commit()
            uid = u.id
        with client.session_transaction() as s:
            s["user_id"] = uid
        return uid

    def test_un_coordinateur_ne_supprime_pas_un_role(self, app, ids, role_jetable):
        from Code.models.models import Role
        c = app.test_client()
        self._en_tant_que(app, c, "coordinateur")
        r = c.delete("/roles/%d" % role_jetable)
        assert r.status_code == 403, r.data
        with app.app_context():
            assert db.session.get(Role, role_jetable) is not None

    def test_un_administrateur_le_supprime(self, app, ids, role_jetable):
        from Code.models.models import Role
        c = app.test_client()
        self._en_tant_que(app, c, "admin")
        r = c.delete("/roles/%d" % role_jetable)
        assert r.status_code == 200, r.data
        with app.app_context():
            assert db.session.get(Role, role_jetable) is None

    def test_le_bouton_nest_rendu_que_pour_un_administrateur(self):
        g = _lire("Code/routes/templates/roles_view.html")
        i = g.index('onclick="deleteRole(')
        avant = g[:i]
        assert "{% if peut_supprimer %}" in avant[-400:], avant[-400:]

    def test_le_renommage_reste_ouvert(self):
        """Le masquage n'est pas une sécurité, mais l'inverse non plus : on ne
        ferme pas une action réversible en fermant l'autre."""
        src = _lire("Code/routes/roles.py")
        i = src.index("def update_role")
        corps = src[i:src.index("def delete_role")]
        assert "is_admin()" not in corps, corps


# ════════════════════════════════════════════════════════════════════════
#  Le droit de MODIFIER un compte
# ════════════════════════════════════════════════════════════════════════
class TestLeDroitDeModifierUnCompte:
    """« On a mis le créer, pas le modifier. » Il existe depuis le 27/10 —
    voici son cliquet, et le libellé qui disait « hors statut » alors que le
    statut se change depuis la fiche depuis le 28/10.
    """

    def test_le_defaut_est_admin_et_coordinateur(self):
        from Code.permissions import DROITS_DEFAUT
        ligne = DROITS_DEFAUT["modifie_comptes"]
        assert ligne["user"] is False
        assert ligne["champion"] is False
        assert ligne["coordinateur"] is True

    def test_la_colonne_admin_est_toujours_ouverte(self):
        from Code.permissions import droits_effectifs
        assert droits_effectifs()["modifie_comptes"]["admin"] is True

    def test_le_tableau_sert_la_ligne(self, auth_client):
        r = auth_client.get("/comptes/droits")
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert "modifie_comptes" in d["droits"], sorted(d["droits"])
        assert d["droits"]["modifie_comptes"]["admin"] is True

    def test_le_libelle_ne_dit_plus_hors_statut(self):
        from Code.translations import t
        assert "statut" not in t("droit.modifie_comptes", "fr").lower()
        assert "status" not in t("droit.modifie_comptes", "en").lower()

    def test_lecran_affiche_la_ligne(self):
        js = _lire("static/js/gestion_compte_new.js")
        assert "'modifie_comptes'" in js
        g = _lire("Code/routes/templates/gestion_compte_new.html")
        assert "droit_modifie_comptes:" in g


# ════════════════════════════════════════════════════════════════════════
#  Page Temps — les lignes d'une analyse de rôle sont celles du rôle
# ════════════════════════════════════════════════════════════════════════
class TestLesLignesDUneAnalyseDeRole:
    """« On ne doit pas pouvoir rajouter de lignes : ce sont celles du rôle.
    Et on ne peut pas non plus supprimer d'activités, elles sont définies par
    le rôle. »

    On pouvait ajouter une ligne avec un sélecteur portant TOUTE la carto :
    une analyse de rôle se retrouvait avec des activités que le rôle ne tient
    pas, et sans celles qu'il tient.
    """

    def test_plus_de_bouton_dajout_de_ligne(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        js = _lire("static/js/time.js")
        assert "btn-role-add-line" not in g
        assert "btn-role-add-line" not in js

    def test_plus_de_colonne_actions_ni_de_bouton_de_suppression(self):
        js = _lire("static/js/time.js")
        i = js.index("function addRoleRow(")
        corps = js[i:js.index("function recalcRoleTotals(")]
        assert "r-del" not in corps, corps
        assert "r-actions" not in corps, corps

    def test_lactivite_est_un_libelle_pas_un_selecteur(self):
        js = _lire("static/js/time.js")
        i = js.index("function addRoleRow(")
        corps = js[i:js.index("function recalcRoleTotals(")]
        assert "buildRoleActivitySelect" not in corps, corps
        assert "nomActivite(activityId)" in corps
        assert "dataset.activityId" in corps
        assert "buildRoleActivitySelect" not in js

    def test_lenregistrement_lit_lidentifiant_de_la_ligne(self):
        js = _lire("static/js/time.js")
        assert "activity_id: parseInt(tr.dataset.activityId" in js
        assert "tr.querySelector('.r-act select')" not in js

    def test_les_recurrences_ne_sont_plus_ecrites_en_dur(self):
        """Elles s'affichaient en français dans l'interface anglaise."""
        js = _lire("static/js/time.js")
        for mot in ("Journalier</option>", "Hebdomadaire</option>",
                    "Mensuel</option>", "Annuel</option>"):
            assert mot not in js, mot
        g = _lire("Code/routes/templates/time_dashboard.html")
        for cle in ("rec_daily", "rec_weekly", "rec_monthly", "rec_yearly"):
            assert ("%s:" % cle) in g, cle


# ════════════════════════════════════════════════════════════════════════
#  Page Temps — la faiblesse
# ════════════════════════════════════════════════════════════════════════
class TestLaFaiblesse:

    def _poster(self, client, aid, **extra):
        corps = {"mode": "activity", "activity_id": aid, "recurrence": "annuel",
                 "frequency": 1, "duration_std": 60, "delay_std": 120,
                 "L_work_added": 10, "M_wait_added": 5}
        corps.update(extra)
        return client.post("/temps/api/weakness", json=corps).get_json()

    # ── la probabilité, en pourcentage ────────────────────────────────
    def test_la_probabilite_se_saisit_en_pourcentage(self, auth_client, ids):
        """« 1 sur N » demandait de penser à l'envers, et un cas sur trois ne
        s'écrivait pas : 3 rend 33,3 %, jamais 30 %."""
        j = self._poster(auth_client, ids["activity_id"], N_prob_pct=20)
        assert j["calc"]["O"] == pytest.approx(0.20)
        j = self._poster(auth_client, ids["activity_id"], N_prob_pct=30)
        assert j["calc"]["O"] == pytest.approx(0.30)

    def test_le_denominateur_reste_accepte(self, auth_client, ids):
        """Des appels anciens l'envoient encore ; quand les deux arrivent, le
        POURCENTAGE gagne."""
        j = self._poster(auth_client, ids["activity_id"], N_prob_denom=4)
        assert j["calc"]["O"] == pytest.approx(0.25)
        j = self._poster(auth_client, ids["activity_id"], N_prob_denom=4,
                         N_prob_pct=50)
        assert j["calc"]["O"] == pytest.approx(0.50)

    def test_le_pourcentage_se_relit_tel_quel(self, app, auth_client, ids):
        from Code.models.models import TimeWeakness
        self._poster(auth_client, ids["activity_id"], N_prob_pct=30,
                     weakness="T128-PCT", save=True)
        with app.app_context():
            w = TimeWeakness.query.filter_by(weakness="T128-PCT").first()
            assert w is not None
            try:
                assert w.prob_percent == pytest.approx(30.0)
                # Le denominateur reste ecrit, arrondi, pour les anciens lecteurs.
                assert w.prob_denom == 3
                it = auth_client.get("/temps/api/weakness/%d" % w.id).get_json()["item"]
                assert it["N_prob_pct"] == pytest.approx(30.0)
            finally:
                db.session.delete(w)
                db.session.commit()

    def test_une_ligne_davant_la_colonne_rend_son_denominateur(self):
        """1/N en est la traduction exacte : il n'y a rien à deviner."""
        from Code.routes.time_view import _pct_stocke

        class Faux(object):
            prob_percent = None
            prob_denom = 4
        assert _pct_stocke(Faux()) == pytest.approx(25.0)

    def test_le_champ_est_un_pourcentage_a_lecran(self):
        g = _lire("Code/routes/templates/time_dashboard.html")
        i = g.index('id="fw-n"')
        champ = g[i - 200:i + 200]
        assert 'max="100"' in champ, champ
        assert '>%<' in champ, champ
        from Code.translations import t
        assert "1 sur N" not in t("time.fw_hint_prob", "fr")
        assert "1 in N" not in t("time.fw_hint_prob", "en")

    # ── le délai ne tombe pas sous la durée ───────────────────────────
    def test_le_delai_standard_ne_tombe_pas_sous_la_duree(self, auth_client, ids):
        """« On ne peut pas avoir moins de temps pour faire une activité
        qu'elle n'en demande au minimum. »"""
        j = self._poster(auth_client, ids["activity_id"], duration_std=60,
                         delay_std=10)
        assert j["B_minutes"] == 60
        assert j["C_minutes"] == 60

    def test_un_delai_au_dessus_de_la_duree_nest_pas_touche(self, auth_client, ids):
        j = self._poster(auth_client, ids["activity_id"], duration_std=60,
                         delay_std=180)
        assert j["C_minutes"] == 180

    def test_la_borne_sapplique_aussi_a_lecriture(self, app, auth_client, ids):
        from Code.models.models import TimeWeakness
        self._poster(auth_client, ids["activity_id"], duration_std=60,
                     delay_std=10, weakness="T128-BORNE", save=True)
        with app.app_context():
            w = TimeWeakness.query.filter_by(weakness="T128-BORNE").first()
            try:
                assert w.delay_std_minutes == 60
            finally:
                db.session.delete(w)
                db.session.commit()

    def test_lecran_borne_le_champ_a_la_sortie(self):
        """⚠️ À la SORTIE, pas pendant la frappe : effacer « 120 » pour taper
        « 90 » passerait sinon par un « 1 » imposé."""
        js = _lire("static/js/time.js")
        assert "function borneDelaiStandard()" in js
        i = js.index("['#fw-del', '#fw-del-unit'")
        ligne = js[i:js.index("\n", i + 80)]
        assert "'change'" in ligne, ligne
        assert "'input'" not in ligne, ligne

    # ── le coût annuel du retard ──────────────────────────────────────
    def test_le_cout_annuel_du_retard_ne_compte_que_lattente(self, auth_client, ids):
        """Avec (L + M), le travail refait entrait DEUX FOIS dans le total de
        l'accueil (U + V), et la carte « attente » annonçait du travail."""
        j = self._poster(auth_client, ids["activity_id"], N_prob_pct=100,
                         L_work_added=10, M_wait_added=5)
        c = j["calc"]
        assert c["U"] == pytest.approx(10 * c["P"])
        assert c["V"] == pytest.approx(5 * c["P"])
        assert c["V"] != pytest.approx(15 * c["P"])

    def test_le_mensuel_suit_lannuel(self, auth_client, ids):
        c = self._poster(auth_client, ids["activity_id"], N_prob_pct=100,
                         L_work_added=10, M_wait_added=5)["calc"]
        assert c["X"] < c["W"] * 1.01   # l'attente (5) pèse moins que le travail (10)

    def test_le_total_de_laccueil_ne_compte_le_travail_quune_fois(self):
        """`annuel_min` vaut U + V : avec V = (L + M) · P il valait
        2·L·P + M·P — le travail deux fois."""
        from Code.routes.time_view import cout_faiblesse
        m = cout_faiblesse(60, 120, "annuel", 1, 10, 5, 1)
        assert m["U"] + m["V"] == pytest.approx(15 * m["P"])

    def test_les_deux_libelles_renommes(self):
        from Code.translations import t
        assert "without work" not in t("time.fw_hint_delay", "en")
        assert "blocking the next activities" in t("time.fw_hint_delay", "en")
        assert t("time.fw_std_delay", "en") == "Standard lead time"
        assert "Standard lead time + average delay" in t("time.fw_desc_avg_del", "en")

    def test_la_phrase_du_retard_annuel_dit_lattente_seule(self):
        from Code.translations import t
        for langue in ("fr", "en"):
            phrase = t("time.fw_desc_delay_annual", langue)
            assert "travail + attente" not in phrase
            assert "work + wait" not in phrase


# ════════════════════════════════════════════════════════════════════════
#  Page Compétences — les cartes du bas
# ════════════════════════════════════════════════════════════════════════
class TestLesCartesDeRoleDuBas:
    """Elles REDISAIENT la liste « par rôle » posée à côté du radar : même
    liste, même ordre, même geste. Les compteurs et le bouton du plan qu'elles
    portaient en plus vivent sur la page d'évaluation, celle-là même qu'un
    clic ouvre."""

    def test_le_gabarit_na_plus_de_cartes(self):
        g = _lire("Code/routes/templates/competences_view.html")
        assert 'id="cv2-rolecards"' not in g
        assert "cv2-roles-lbl" not in g

    def test_letat_vide_subsiste(self):
        """Sans lui, quelqu'un sans aucun rôle n'aurait rien du tout."""
        g = _lire("Code/routes/templates/competences_view.html")
        assert 'id="cv2-sans-role"' in g
        js = _lire("static/js/competences_v2.js")
        assert "T('no_roles')" in js

    def test_le_constructeur_de_carte_est_parti(self):
        js = _lire("static/js/competences_v2.js")
        assert "function carteRole(" not in js
        assert "cv2-rolecard" not in js

    def test_la_liste_par_role_ouvre_toujours_le_role(self):
        js = _lire("static/js/competences_v2.js")
        assert "function barreRole(" in js
        assert "cv2-parrole-l" in js

    def test_le_plan_reste_atteignable_depuis_la_page_devaluation(self):
        js = _lire("static/js/competences_v2.js")
        assert "data-plan>" in js
        assert "bp.onclick = () => ouvrirPlan();" in js


# ════════════════════════════════════════════════════════════════════════
#  Page Compétences — la norme vient de la liste des activités
# ════════════════════════════════════════════════════════════════════════
class TestLaNormeVientDeLaListeDesActivites:
    """« Enlever la définition de la norme quand elles ne sont pas encore
    notées. La norme de l'entreprise est récupérée par ce que l'on a noté dans
    la page liste des activités. »

    Ce qu'on y note, c'est l'indicateur de performance d'une connexion
    sortante (colonne « Performance »). On le LIT ; on ne le redemande pas.
    """

    @pytest.mark.parametrize("texte,attendu", [
        ("≤ 48 h", (48.0, "h", "moins")),
        ("95 % de conformité", (95.0, "%", "plus")),
        ("sous 5 jours", (5.0, "j", "moins")),
        ("at least 90 %", (90.0, "%", "plus")),
        ("within 2 days", (2.0, "j", "moins")),
        ("max 3 retouches", (3.0, "", "moins")),
        ("1,5 jour", (1.5, "j", "moins")),
    ])
    def test_on_lit_la_norme_dans_lindicateur(self, texte, attendu):
        from Code.paliers import norme_depuis_indicateur
        n = norme_depuis_indicateur(texte)
        assert n is not None, texte
        assert (n["valeur"], n["unite"], n["sens"]) == attendu, (texte, n)

    @pytest.mark.parametrize("texte", ["Dossier complet", "", None, "conforme"])
    def test_un_indicateur_illisible_ne_propose_rien(self, texte):
        """On ne devine pas un chiffre : mieux vaut ne rien proposer."""
        from Code.paliers import norme_depuis_indicateur
        assert norme_depuis_indicateur(texte) is None

    def test_la_porte_napparait_quune_fois_la_sortie_notee(self):
        """Poser la norme bascule la sortie en régime mesuré : offerte sur une
        sortie que personne n'a regardée, elle demandait d'arbitrer un chiffre
        attendu avant d'avoir jamais jugé la chose."""
        js = _lire("static/js/competences_v2.js")
        i = js.index("function resultCard(")
        corps = js[i:js.index("  function majValeur(")]
        assert "const estNote = !estNul(maNote);" in corps
        assert "${dev && estNote ? `<div class=\"fi-porte\">" in corps
        assert "${dev ? `<div class=\"fi-porte\">" not in corps

    def test_la_fiche_montre_lindicateur_a_defaut_de_repere(self):
        js = _lire("static/js/competences_v2.js")
        i = js.index("function resultCard(")
        corps = js[i:js.index("  function majValeur(")]
        assert "r.minimum_performance_text || r.indicateur" in corps
        assert "T('pal_indic')" in corps

    def test_la_premiere_mesure_reprend_lindicateur(self):
        js = _lire("static/js/competences_v2.js")
        i = js.index("function formPremiere(")
        corps = js[i:js.index("  function formNorme(")]
        assert "r.norme_suggeree" in corps
        assert "pal_norme_vient" in corps

    def test_les_trois_libelles_existent_dans_les_deux_langues(self):
        js = _lire("static/js/competences_v2.js")
        for cle in ("pal_indic", "pal_indic_ou", "pal_norme_vient"):
            assert js.count("%s:" % cle) == 2, cle

    def test_lindicateur_dune_sortie_vient_de_la_connexion(self, app, ids):
        from Code.models.models import Activities, Link, Performance
        from Code.routes.qualify_outputs import (indicateurs_de_sortie,
                                                 get_activity_outputs)
        with app.app_context():
            a = Activities(name="T128 Produire", entity_id=ids["entity_id"])
            b = Activities(name="T128 Aval", entity_id=ids["entity_id"])
            db.session.add_all([a, b])
            db.session.commit()
            lk = Link(entity_id=ids["entity_id"], source_activity_id=a.id,
                      target_activity_id=b.id, description="Rapport T128",
                      type="flux")
            db.session.add(lk)
            db.session.commit()
            db.session.add(Performance(name="≤ 48 h", link_id=lk.id))
            db.session.commit()
            try:
                indics = indicateurs_de_sortie(a.id)
                assert indics == {"rapport t128": "≤ 48 h"}, indics
                # Et la sortie correspondante porte bien ce nom.
                noms = {d.name for d in get_activity_outputs(a.id)}
                assert noms == {"Rapport T128"}, noms
            finally:
                from Code.models.models import Data
                for d in Data.query.filter_by(producer_activity_id=a.id).all():
                    db.session.delete(d)
                for p in Performance.query.filter_by(link_id=lk.id).all():
                    db.session.delete(p)
                db.session.delete(lk)
                db.session.delete(a)
                db.session.delete(b)
                db.session.commit()

    def test_la_fiche_dactivite_sert_lindicateur_et_la_norme_proposee(self, app, ids):
        """Le payload de l'écran d'évaluation porte les deux : l'écran ne doit
        pas aller les chercher ailleurs ni les deviner."""
        from Code.routes.mastery import activity_mastery
        from Code.models.models import (Activities, Data, Link, Performance,
                                        User, UserRole, Role)
        from Code.security import hash_password
        with app.app_context():
            u = User(first_name="T128", last_name="Eval",
                     email="t128.eval@test", password=hash_password("Test1234!"),
                     status="user")
            a = Activities(name="T128 Rediger", entity_id=ids["entity_id"])
            b = Activities(name="T128 Relire", entity_id=ids["entity_id"])
            db.session.add_all([u, a, b])
            db.session.commit()
            lk = Link(entity_id=ids["entity_id"], source_activity_id=a.id,
                      target_activity_id=b.id, description="Note T128",
                      type="flux")
            db.session.add(lk)
            db.session.commit()
            db.session.add(Performance(name="95 %", description="de conformité",
                                       link_id=lk.id))
            db.session.commit()
            try:
                # ⚠️ `level_label` lit `session['lang']` : la fonction veut un
                # contexte de REQUÊTE, pas seulement un contexte applicatif.
                with app.test_request_context():
                    etat = activity_mastery(u.id, a.id)
                sortie = etat["results"][0]
                assert sortie["name"] == "Note T128"
                assert sortie["indicateur"] == "95 % de conformité"
                assert sortie["norme_suggeree"]["valeur"] == 95.0
                assert sortie["norme_suggeree"]["sens"] == "plus"
            finally:
                for d in Data.query.filter_by(producer_activity_id=a.id).all():
                    db.session.delete(d)
                for p in Performance.query.filter_by(link_id=lk.id).all():
                    db.session.delete(p)
                db.session.delete(lk)
                db.session.delete(a)
                db.session.delete(b)
                db.session.delete(u)
                db.session.commit()


# ════════════════════════════════════════════════════════════════════════
#  Une flèche sans libellé — la version EN BLOC doit dire la même chose
# ════════════════════════════════════════════════════════════════════════
def test_la_version_en_bloc_applique_la_meme_regle(app, ids):
    """⚠️ `output_ids_en_bloc` sert le tableau global de la page RH, et
    `get_activity_outputs` la page Compétences. Deux règles donneraient deux
    chiffres pour la même personne.

    ⚠️ Le décor porte une `Data` PORTANT LE NOM DE LA DESTINATION, comme la
    règle d'avant en a semé dans les bases déjà en service. Sans cette ligne
    le cas ne prouve rien : la version en bloc ne retient que des `Data` qui
    existent, et celle-là n'aurait jamais été créée.
    """
    from Code.models.models import Activities, Data, Link
    from Code.routes.qualify_outputs import (get_activity_outputs,
                                             output_ids_en_bloc)
    with app.app_context():
        a = Activities(name="T128 Bloc", entity_id=ids["entity_id"])
        b = Activities(name="T128 Bloc aval", entity_id=ids["entity_id"])
        db.session.add_all([a, b])
        db.session.commit()
        liens = [
            Link(entity_id=ids["entity_id"], source_activity_id=a.id,
                 target_activity_id=b.id, description="Dossier T128", type="flux"),
            Link(entity_id=ids["entity_id"], source_activity_id=a.id,
                 target_activity_id=b.id, description=None, type="flux"),
        ]
        db.session.add_all(liens)
        # La fausse sortie d'hier : le nom de l'activité destinataire, et
        # personne n'y a travaillé (ni nature, ni repère de réussite).
        db.session.add(Data(entity_id=ids["entity_id"], name=b.name, type="flux",
                            producer_activity_id=a.id))
        db.session.commit()
        try:
            par_activite = {d.name for d in get_activity_outputs(a.id)}
            ids_bloc = output_ids_en_bloc([a.id])[a.id]
            en_bloc = {d.name for d in Data.query.filter(Data.id.in_(ids_bloc)).all()} \
                if ids_bloc else set()
            assert par_activite == {"Dossier T128"}, par_activite
            assert en_bloc == par_activite, (par_activite, en_bloc)
        finally:
            for d in Data.query.filter_by(producer_activity_id=a.id).all():
                db.session.delete(d)
            for lk in liens:
                db.session.delete(lk)
            db.session.delete(a)
            db.session.delete(b)
            db.session.commit()
