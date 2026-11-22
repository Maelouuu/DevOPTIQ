# -*- coding: utf-8 -*-
"""Page Temps — les trois défauts relevés par l'audit du 03-05/10/2026.

Chacun a été REPRODUIT avant d'être corrigé, avec les chiffres du rapport.
"""
import io
import json
import os

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(chemin):
    return io.open(os.path.join(RACINE, chemin), encoding="utf-8").read()


class TestLUniteDeLaDureeDuRole:
    """R04 / H13 / F36 — « saisir 60 dans Durée (h) donne 1,0 h ».

    Le champ était en minutes et l'en-tête annonçait des heures : le calcul
    était juste, c'est l'en-tête qui mentait.

    ⚠️ **La règle a changé de forme le 22/11, pas de fond.** L'unité se
    CHOISIT désormais (minutes / heures / jours), comme pour le projet et
    l'activité. Donc : l'en-tête n'annonce PLUS d'unité du tout — il en
    annoncerait une au-dessus d'un sélecteur qui en propose trois — et la
    conversion doit exister, au SERVEUR, parce que la colonne s'appelle
    `duration_minutes`. Ce qui reste interdit est le même qu'avant : un
    en-tête qui dit une unité que la saisie ne respecte pas.
    """

    def test_l_en_tete_de_saisie_n_annonce_AUCUNE_unite(self):
        gabarit = _lire("Code/routes/templates/time_dashboard.html")
        entete = gabarit[gabarit.index('id="role-rows"') - 1800:
                         gabarit.index('id="role-rows"')]
        assert "time.col_duration'" in entete or 'time.col_duration"' in entete
        assert "time.col_duration_min" not in entete
        assert "time.col_duration_h" not in entete
        # Et la colonne qui porte le choix est bien là.
        assert "time.col_unit" in entete

    def test_le_champ_est_CONVERTI_par_le_serveur(self):
        """⚠️ C'est LE point du correctif : la route lisait
        `float(ln['duration'])` tel quel, et le client lui envoyait un
        `duration_unit: 'minutes'` que personne ne lisait. Offrir les heures
        à l'écran sans toucher à la route aurait enregistré « 2 heures »
        comme deux MINUTES, en silence — même famille que les `<option>` sans
        `value` du 03/11."""
        from Code.routes.time_view import _duree_ligne_role
        assert _duree_ligne_role({"duration": 2, "duration_unit": "heures"}) == 120
        assert _duree_ligne_role({"duration": 1, "duration_unit": "jours"}) == 1440
        assert _duree_ligne_role({"duration": 30, "duration_unit": "minutes"}) == 30
        # ⚠️ Le défaut reste MINUTES : tous les appels d'avant n'envoyaient
        # rien, et ils saisissaient bien des minutes.
        assert _duree_ligne_role({"duration": 30}) == 30

    def test_l_ecran_envoie_l_unite_CHOISIE(self):
        """Un `duration_unit` écrit en dur rendait le sélecteur décoratif."""
        js = _lire("static/js/time.js")
        assert "duration_unit: 'minutes'" not in js
        assert "'.r-du select'" in js

    def test_la_pesee_affichee_convertit_aussi(self):
        """La colonne « Pesée » est lue pendant la saisie : sans conversion
        elle annoncerait 2 min pour 2 heures, à côté d'un total juste."""
        js = _lire("static/js/time.js")
        d = js.index("function addRoleRow")
        role = js[d:js.index("function recalcRoleTotals", d)]
        recalc = role[role.index("function recalc()"):]
        assert "toMinutes(tr.querySelector('.r-dur').value, du.value)" in recalc, recalc


class TestLApercuDeLActivite:
    """R05 / H14 / T17 — 30 min × 2 × 3 affichait « 0.0 h » et enregistrait
    3,0 h. L'aperçu n'était recalculé que sur le changement d'ACTIVITÉ."""

    def test_les_trois_champs_rafraichissent_l_apercu(self):
        js = _lire("static/js/time.js")
        assert "majApercuActivite" in js
        bloc = js[js.index("majApercuActivite"):][:1200]
        for champ in ("#act-duration", "#act-frequency", "#act-people"):
            assert champ in bloc, champ
        assert "addEventListener('input'" in bloc


class TestLaFrequenceDeLaFaiblesse:
    """R08 / T19 / F37 — « fréquence 1 et fréquence 2 donnent le même total
    annuel ». `freq` était lue, stockée, et n'entrait dans aucun calcul."""

    def _calcule(self, auth_client, ids, freq):
        r = auth_client.post("/temps/api/weakness", json={
            "mode": "activity",
            "activity_id": ids["activity_id"],
            "recurrence": "hebdomadaire",
            "frequency": freq,
            "duration_std": 60, "duration_unit": "minutes",
            "delay_std": 0, "delay_unit": "minutes",
            "L_work_added": 30, "L_unit": "minutes",
            "M_wait_added": 60, "M_unit": "minutes",
            "N_prob_denom": 2,
            "save": False,
        })
        assert r.status_code == 200, r.get_data(as_text=True)[:200]
        return json.loads(r.data)["calc"]

    def test_doubler_la_frequence_double_les_occurrences(self, auth_client, ids):
        """Le scénario EXACT du rapport : hebdomadaire, 60 min, 1 chance sur 2,
        30 min de surcroît, 60 min d'attente."""
        un = self._calcule(auth_client, ids, 1)
        deux = self._calcule(auth_client, ids, 2)
        assert deux["P"] == pytest.approx(un["P"] * 2), (
            "la fréquence ne change toujours rien au nombre d'occurrences")

    def test_et_donc_le_surcroit_annuel(self, auth_client, ids):
        un = self._calcule(auth_client, ids, 1)
        deux = self._calcule(auth_client, ids, 2)
        assert deux["U"] == pytest.approx(un["U"] * 2)
        assert deux["V"] == pytest.approx(un["V"] * 2)

    def test_une_frequence_absente_ou_nulle_vaut_UNE_fois(self, auth_client, ids):
        """⚠️ `max(1, freq)` : une fréquence 0 ne doit pas effacer la
        faiblesse, elle n'a simplement pas été renseignée."""
        un = self._calcule(auth_client, ids, 1)
        zero = self._calcule(auth_client, ids, 0)
        assert zero["P"] == pytest.approx(un["P"])

class TestLeMensuelDitSaBase:
    """A — « le mensuel ne vaut pas l'annuel ÷ 12 ».

    Les deux chiffres étaient JUSTES : `W = U / (Sa / 4,34524)` divise par le
    nombre de MOIS TRAVAILLÉS. Avec 32 semaines par an cela fait 7,36 mois, et
    8 h ÷ 7,36 donne bien 1,09 — exactement ce que le rapport avait relevé.
    Le calcul ne bouge pas : c'est le libellé qui mentait, en disant « en
    moyenne sur l'année », ce qui se lit « ÷ 12 ».
    """

    @pytest.mark.parametrize("lang", ["fr", "en"])
    def test_le_libelle_dit_mois_TRAVAILLE(self, lang):
        from Code.translations import t
        entete = t("time.fw_monthly_header", lang=lang).lower()
        assert ("travaillé" in entete) or ("working" in entete), entete

    @pytest.mark.parametrize("lang", ["fr", "en"])
    def test_et_la_base_de_calcul_est_affichable(self, lang):
        """⚠️ Un libellé ne suffit pas : on doit pouvoir REFAIRE le calcul.
        La phrase porte les semaines par an et les mois travaillés."""
        from Code.translations import t
        phrase = t("time.fw_base_mois", lang=lang)
        assert "{sem}" in phrase and "{mois}" in phrase, phrase

    def test_le_calcul_lui_meme_n_a_pas_bouge(self, auth_client, ids):
        """⚠️ Les analyses déjà enregistrées gardent leur valeur : on corrige
        ce que l'écran DIT, pas ce qu'il compte."""
        r = auth_client.post("/temps/api/weakness", json={
            "mode": "activity", "activity_id": ids["activity_id"],
            "recurrence": "hebdomadaire", "frequency": 1,
            "duration_std": 60, "duration_unit": "minutes",
            "delay_std": 0, "delay_unit": "minutes",
            "L_work_added": 30, "L_unit": "minutes",
            "M_wait_added": 60, "M_unit": "minutes",
            "N_prob_denom": 2, "save": False,
        })
        assert r.status_code == 200
        d = json.loads(r.data)
        calc, sem = d["calc"], d["params"]["weeks_per_year"]
        assert calc["W"] == pytest.approx(calc["U"] / (sem / 4.34524))


class TestLaDureeSaisieNEstPasEcrasee:
    """R06 / T16 — « les deux premiers essais ont fini à 0 h ; contre-test,
    activité choisie AVANT la durée, ça marche ».

    `onchange` de l'activité remplissait durée et délai avec les valeurs par
    défaut, SANS regarder si on avait déjà tapé. Taper 30 puis choisir
    l'activité remettait 0 — d'où les projets enregistrés à 0 h.
    """

    def test_les_trois_onglets_respectent_la_saisie(self):
        js = _lire("static/js/time.js")
        assert "marqueSaisie" in js
        assert js.count("intact(") >= 4, js.count("intact(")

    def test_c_est_la_SAISIE_qui_est_marquee_pas_la_valeur(self):
        """⚠️ « Touché » et « non vide » ne sont pas la même chose : une durée
        volontairement mise à 0 est un choix, et doit le rester."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("function marqueSaisie"):][:420]
        assert "dataset.saisi" in bloc
        assert "addEventListener('input'" in bloc


class TestUneLigneDeMessageNEstPasUneSaisie:
    """Erreur relevee dans la console de staging le 13/10 :
    « Cannot read properties of null (reading 'value') » — time.js:788,
    dans `recalcRoleTotals`.

    `loadRoleActivities` pose un <tr> d'un SEUL <td> quand le role n'a aucune
    activite (ou que le chargement echoue) ; `recalcRoleTotals` bouclait sur
    toutes les lignes de #role-rows et y lisait `.r-rec select`, absent de
    celle-la. Consequence : les quatre compteurs du role ne se mettaient plus
    jamais a jour, et la console se remplissait a chaque passage sur l'onglet.
    """

    def test_le_total_saute_les_lignes_sans_selecteur(self):
        js = _lire("static/js/time.js")
        bloc = js[js.index("function recalcRoleTotals"):][:600]
        assert "if (!recSel) return;" in bloc, bloc[:300]

    def test_l_enregistrement_les_saute_AUSSI(self):
        """Le meme piege, et celui-la part en BASE : une ligne de message n'a
        pas d'activite a enregistrer."""
        js = _lire("static/js/time.js")
        bloc = js[js.index("#btn-role-save"):][:400]
        assert ".filter(tr=>tr.querySelector('.r-rec select'))" in bloc, bloc[:300]

    def test_le_message_lui_meme_suit_la_langue(self):
        """Il etait ecrit en dur en francais dans le JS — invisible pour
        test_78, qui ne lit que les gabarits."""
        from Code.translations import t
        fr = t("time.role_no_activity", lang="fr")
        en = t("time.role_no_activity", lang="en")
        assert fr != "time.role_no_activity" and en != "time.role_no_activity"
        assert fr != en, (fr, en)
        js = _lire("static/js/time.js")
        assert "Aucune activit\u00e9 pour ce r\u00f4le.</td>" not in js
