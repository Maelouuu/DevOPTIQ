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

    Le champ EST en minutes : `addRoleRow` lit sa valeur telle quelle
    (`durMin`), la multiplie par la fréquence, puis `fmtH()` convertit pour
    l'affichage. Le calcul est cohérent ; c'est l'en-tête qui mentait.
    """

    def test_le_tableau_de_saisie_annonce_des_MINUTES(self):
        gabarit = _lire("Code/routes/templates/time_dashboard.html")
        entete = gabarit[gabarit.index('id="role-rows"') - 1400:
                         gabarit.index('id="role-rows"')]
        assert "time.col_duration_min" in entete
        assert "time.col_duration_h" not in entete

    def test_les_tableaux_de_LECTURE_gardent_les_heures(self):
        """⚠️ La même clé servait à quatre tableaux, et trois étaient JUSTES :
        ils affichent `fmtH(duration_minutes)`, donc des heures. Renommer la
        clé partout aurait cassé ce qui marchait."""
        js = _lire("static/js/time.js")
        assert js.count("fmtH(it.duration_minutes)") >= 1
        assert js.count("fmtH(r.duration_minutes)") >= 1
        assert "col_duration_h" in js

    @pytest.mark.parametrize("lang,attendu", [("fr", "Durée (min)"),
                                              ("en", "Duration (min)")])
    def test_la_cle_existe_dans_les_deux_langues(self, lang, attendu):
        from Code.translations import t
        assert t("time.col_duration_min", lang=lang) == attendu


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
