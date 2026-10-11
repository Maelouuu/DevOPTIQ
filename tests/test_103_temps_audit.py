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
