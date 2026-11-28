# -*- coding: utf-8 -*-
"""LA PÉRIODE d'une analyse de temps, et LA CHARGE DE TRAVAIL de la page RH.

Une analyse de temps n'est pas vraie pour l'éternité : une charge fluctue, et
un poids de rôle relevé en janvier ne dit rien de novembre. Chaque analyse
porte donc le MOIS qu'elle décrit — c'est lui qui rend lisible « le poids de
ce rôle en novembre », et c'est de là que vient toute la section ④ de la page
RH : le damier rôle × cartographie, le poids de chaque personne, et le plafond
de prévention à 80 % du temps travaillé de l'année.
"""
import io
import os
import re

import pytest

from Code.extensions import db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(chemin):
    return io.open(os.path.join(RACINE, chemin), encoding="utf-8").read()


def _sans_commentaires_js(js):
    """⚠️ Dixième fois que ce piège se présente : un contrôle qui cherche une
    chaîne s'attrape sur le COMMENTAIRE qui l'explique — et un commentaire
    qui justifie un marqueur le CITE forcément."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"^\s*//.*$", "", js, flags=re.M)


def _sans_commentaires_css(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _sans_commentaires_sql(sql):
    """⚠️ Onzième fois, et en SQL cette fois : les commentaires de ce semis
    CITENT les formes qu'ils interdisent — « round(double precision, integer)
    n'existe pas », le préfixe que la purge cherche. Sans ce nettoyage, un
    cliquet s'attrape sur l'explication du défaut qu'il garde."""
    return re.sub(r"(?m)--.*$", "", sql)


def _appels(sql, nom):
    """Chaque appel à `nom(...)`, parenthèses équilibrées.

    Une expression régulière s'arrête à la PREMIÈRE parenthèse fermante, donc
    elle tronque `round(sum(x) / 60.0, 1)` à `round(sum(x)` — et le contrôle
    ne voit jamais le second argument, celui qui décide.
    """
    out = []
    for m in re.finditer(re.escape(nom) + r"\s*\(", sql):
        prof, i = 0, m.end() - 1
        while i < len(sql):
            if sql[i] == "(":
                prof += 1
            elif sql[i] == ")":
                prof -= 1
                if prof == 0:
                    out.append(sql[m.start():i + 1])
                    break
            i += 1
    return out


def _arguments(appel):
    """Les arguments de premier niveau d'un appel rendu par `_appels`."""
    corps = appel[appel.index("(") + 1:-1]
    args, prof, debut = [], 0, 0
    for i, c in enumerate(corps):
        if c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
        elif c == "," and prof == 0:
            args.append(corps[debut:i])
            debut = i + 1
    args.append(corps[debut:])
    return args


def _section_charge(css_brut):
    """La section ④ SEULE, commentaires retirés.

    ⚠️ On coupe sur le repère AVANT de retirer les commentaires : le repère
    EST un commentaire, et il cite ce qu'il interdit. Puis on repart après la
    fin de ce commentaire, sinon le `/*` disparaît avec le nettoyage et son
    texte retombe dans la zone lue.
    """
    tail = css_brut.split("④ LA CHARGE DE TRAVAIL", 1)[1]
    return _sans_commentaires_css(tail.split("*/", 1)[1])


# ═══════════════════════════════════════════════════════════════════════════
#  Décor : une carto à soi, des rôles, des analyses datées
# ═══════════════════════════════════════════════════════════════════════════

class _Decor:
    """Une carto, des activités, des rôles et des analyses de rôle datées.

    ⚠️ Sur sa PROPRE carto, détruite en sortant : écrire dans celle du décor
    commun s'équilibre peut-être à la ligne près, mais l'entité ACTIVE ne
    revient pas toute seule — et l'échec se lit alors chez un fichier qui ne
    parle pas du même sujet.
    """

    def __init__(self, client, ids, n_act=10):
        self.client, self.ids, self.n_act = client, ids, n_act
        self.roles, self.gens, self.analyses = {}, {}, []

    def __enter__(self):
        from Code.models.models import (Activities, Entity, EntrepriseSettings)
        self.ent = Entity(name="CH171-%d" % id(self), owner_id=self.ids["user_id"])
        self.ent2 = Entity(name="CH171b-%d" % id(self), owner_id=self.ids["user_id"])
        db.session.add_all([self.ent, self.ent2])
        db.session.commit()
        # 47 sem. × 5 j × 7 h = 1 645 h → plafond 80 % = 1 316 h
        self.cal = EntrepriseSettings(entity_id=self.ent.id, work_hours_per_day=7,
                                      work_days_per_week=5, work_weeks_per_year=47)
        db.session.add(self.cal)
        self.actes = {}
        for e in (self.ent, self.ent2):
            self.actes[e.id] = [Activities(name="CH171-a%d-%d" % (e.id, i),
                                           entity_id=e.id, duration_minutes=60)
                                for i in range(self.n_act)]
            db.session.add_all(self.actes[e.id])
        db.session.commit()
        with self.client.session_transaction() as sess:
            self.avant = sess.get("active_entity_id")
            sess["active_entity_id"] = self.ent.id
        return self

    def role(self, nom):
        from Code.models.models import Role
        r = Role(name="CH171-" + nom, entity_id=self.ent.id)
        db.session.add(r)
        db.session.commit()
        self.roles[nom] = r
        return r

    def personne(self, prenom, roles=()):
        from Code.models.models import User, UserRole
        from Code.security import hash_password
        u = User(email="ch171-%s-%d@t.local" % (prenom, id(self)),
                 first_name=prenom, last_name="X", password=hash_password("x"),
                 status="user")
        db.session.add(u)
        db.session.commit()
        # Une entrée est soit « rôle », soit (« rôle », carto) : OÙ la
        # personne le tient. Sans attache, elle porte la somme de toutes les
        # cartos — le comportement d'avant.
        for item in roles:
            nom, ou = item if isinstance(item, tuple) else (item, None)
            db.session.add(UserRole(user_id=u.id, role_id=self.roles[nom].id,
                                    entity_id=ou.id if ou is not None else None))
        db.session.commit()
        self.gens[prenom] = u
        return u

    def analyse(self, role, periode, n=4, duree=60, rec="journalier", freq=1,
                carto=None):
        from Code.models.models import TimeRoleAnalysis, TimeRoleLine
        e = carto or self.ent
        R = TimeRoleAnalysis(role_id=self.roles[role].id, name="CH171 " + role,
                             periode=periode)
        db.session.add(R)
        db.session.flush()
        for i in range(n):
            db.session.add(TimeRoleLine(role_analysis_id=R.id,
                                        activity_id=self.actes[e.id][i].id,
                                        recurrence=rec, frequency=freq,
                                        duration_minutes=float(duree)))
        db.session.commit()
        self.analyses.append(R)
        return R

    def __exit__(self, *_):
        from Code.models.models import (Activities, Entity, EntrepriseSettings,
                                        Role, TimeRoleAnalysis, TimeRoleLine,
                                        User, UserRole)
        with self.client.session_transaction() as sess:
            sess["active_entity_id"] = (self.avant if self.avant is not None
                                        else self.ids["entity_id"])
        for R in self.analyses:
            for ln in TimeRoleLine.query.filter_by(role_analysis_id=R.id).all():
                db.session.delete(ln)
            obj = db.session.get(TimeRoleAnalysis, R.id)
            if obj:
                db.session.delete(obj)
        db.session.commit()
        for u in self.gens.values():
            for ur in UserRole.query.filter_by(user_id=u.id).all():
                db.session.delete(ur)
            db.session.delete(db.session.get(User, u.id))
        for r in self.roles.values():
            obj = db.session.get(Role, r.id)
            if obj:
                db.session.delete(obj)
        for lot in self.actes.values():
            for a in lot:
                obj = db.session.get(Activities, a.id)
                if obj:
                    db.session.delete(obj)
        obj = db.session.get(EntrepriseSettings, self.cal.id)
        if obj:
            db.session.delete(obj)
        for e in (self.ent, self.ent2):
            obj = db.session.get(Entity, e.id)
            if obj:
                db.session.delete(obj)
        db.session.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  LA PÉRIODE — le mois que l'analyse décrit
# ═══════════════════════════════════════════════════════════════════════════

class TestLaPeriodeSeLit:

    def test_le_mois_seul_une_date_entiere_et_un_mois_non_rembourre(self):
        from Code.periode import lire_periode
        assert lire_periode("2026-11") == "2026-11"
        assert lire_periode("2026-11-05") == "2026-11"
        assert lire_periode("2026-1") == "2026-01"

    def test_tout_le_reste_rend_le_DEFAUT_jamais_un_mois_invente(self):
        """⚠️ La valeur vient du navigateur : un mois inventé rangerait une
        analyse dans une période qui n'existe pas."""
        from Code.periode import lire_periode
        for mauvais in (None, "", "bientôt", "2026-13", "2026-00", "11-2026",
                        "99999-01", [], {}):
            assert lire_periode(mauvais, "2026-01") == "2026-01", mauvais

    def test_le_mois_courant_a_la_bonne_forme(self):
        from Code.periode import mois_courant
        assert re.match(r"^\d{4}-\d{2}$", mois_courant())


class TestLaPeriodeSEcritEtSeRelit:

    def test_une_analyse_de_role_SANS_periode_prend_le_mois_courant(self, auth_client, ids):
        from Code.models.models import TimeRoleAnalysis
        from Code.periode import mois_courant
        with _Decor(auth_client, ids) as d:
            d.role("R")
            r = auth_client.post("/temps/api/role_analysis", json={
                "role_id": d.roles["R"].id, "name": "sans periode",
                "lines": [{"activity_id": d.actes[d.ent.id][0].id,
                           "duration": 30, "recurrence": "journalier",
                           "frequency": 1}]})
            assert r.status_code == 200
            rid = r.get_json()["id"]
            d.analyses.append(db.session.get(TimeRoleAnalysis, rid))
            assert db.session.get(TimeRoleAnalysis, rid).periode == mois_courant()

    def test_une_modification_SANS_la_cle_garde_la_periode(self, auth_client, ids):
        """⚠️ Jamais NULL : une analyse sans période ne figurerait dans aucun
        tableau par mois, et disparaîtrait sans que personne ne l'ait retirée."""
        from Code.models.models import TimeRoleAnalysis
        with _Decor(auth_client, ids) as d:
            d.role("R")
            R = d.analyse("R", "2026-03")
            auth_client.patch("/temps/api/role_analysis/%d" % R.id,
                              json={"name": "renommee"})
            db.session.expire_all()
            assert db.session.get(TimeRoleAnalysis, R.id).periode == "2026-03"

    def test_les_quatre_routes_RENDENT_la_periode(self, auth_client, ids):
        with _Decor(auth_client, ids) as d:
            d.role("R")
            R = d.analyse("R", "2026-05")
            j = auth_client.get("/temps/api/role_analysis/%d" % R.id).get_json()
            assert j["role"]["periode"] == "2026-05"
            j = auth_client.get("/temps/api/role_analyses").get_json()
            assert any(x["periode"] == "2026-05" for x in j["items"])

            p = auth_client.post("/temps/api/project", json={
                "name": "CH171 projet", "periode": "2026-04",
                "lines": [{"activity_id": d.actes[d.ent.id][0].id, "duration": 10,
                           "duration_unit": "minutes"}]}).get_json()
            lu = auth_client.get("/temps/api/project/%d" % p["project_id"]).get_json()
            assert lu["project"]["periode"] == "2026-04"
            auth_client.delete("/temps/api/project/%d" % p["project_id"])

            a = auth_client.post("/temps/api/activity_workload", json={
                "activity_id": d.actes[d.ent.id][0].id, "duration": 30,
                "duration_unit": "minutes", "recurrence": "journalier",
                "frequency": 1, "periode": "2026-06"}).get_json()
            lu = auth_client.get("/temps/api/activity_workload/%d" % a["id"]).get_json()
            assert lu["item"]["periode"] == "2026-06"
            auth_client.delete("/temps/api/activity_workload/%d" % a["id"])

            w = auth_client.post("/temps/api/weakness", json={
                "activity_id": d.actes[d.ent.id][0].id, "recurrence": "hebdomadaire",
                "frequency": 1, "duration_std": 30, "delay_std": 60,
                "weakness": "CH171", "periode": "2026-07", "save": True}).get_json()
            assert w["periode"] == "2026-07"

    def test_le_tableau_de_bord_porte_la_periode_de_chaque_analyse(self, auth_client, ids):
        with _Decor(auth_client, ids) as d:
            d.role("R")
            d.analyse("R", "2026-08")
            j = auth_client.get("/temps/api/tableau_de_bord").get_json()
            assert any(x.get("periode") == "2026-08" for x in j["par_role"])


class TestLaRepriseDesAnalysesDAvant:

    def test_elle_pose_la_periode_depuis_created_at_et_ne_rejoue_rien(self, auth_client, ids):
        from datetime import datetime
        from Code.models.models import TimeRoleAnalysis
        from Code.periode import reprendre_periodes
        with _Decor(auth_client, ids) as d:
            d.role("R")
            R = d.analyse("R", None)
            R.created_at = datetime(2025, 2, 17, 9, 0, 0)
            R.periode = None
            db.session.commit()
            assert reprendre_periodes() >= 1
            db.session.expire_all()
            assert db.session.get(TimeRoleAnalysis, R.id).periode == "2025-02"
            # Rejouée, elle ne touche plus rien : `periode IS NULL` la rend
            # idempotente par construction.
            db.session.get(TimeRoleAnalysis, R.id).periode = "2026-09"
            db.session.commit()
            reprendre_periodes()
            db.session.expire_all()
            assert db.session.get(TimeRoleAnalysis, R.id).periode == "2026-09"


# ═══════════════════════════════════════════════════════════════════════════
#  LE POIDS D'UN RÔLE
# ═══════════════════════════════════════════════════════════════════════════

class TestLePoidsDUnRole:

    def _charge(self, periode=None):
        from Code.charge_travail import charge
        return charge(periode)

    def _role(self, d, nom, periode=None):
        c = self._charge(periode)
        return next(r for r in c["roles"] if r["id"] == d.roles[nom].id)

    def test_un_role_mesure_dans_DEUX_cartos_additionne_et_nomme_les_deux(
            self, auth_client, ids):
        """La comparaison « extra entité » : le total pèse l'ensemble, et le
        détail dit ce que chaque carto demande."""
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=4, duree=60, carto=d.ent)
            d.analyse("Q", "2026-11", n=3, duree=30, carto=d.ent2)
            r = self._role(d, "Q", "2026-11")
            assert len(r["mesures"]) == 2
            assert r["annuel_min"] == pytest.approx(
                sum(m["annuel_min"] for m in r["mesures"]))
            assert {m["entite"] for m in r["mesures"]} == {d.ent.name, d.ent2.name}

    def test_deux_analyses_du_MEME_couple_ne_comptent_qu_une_fois(self, auth_client, ids):
        """⚠️ Deux analyses du même rôle, même carto, même mois sont deux
        TENTATIVES, pas deux charges : les additionner compterait le travail
        deux fois. La plus récente l'emporte."""
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=4, duree=60, carto=d.ent)
            seconde = d.analyse("Q", "2026-11", n=4, duree=10, carto=d.ent)
            r = self._role(d, "Q", "2026-11")
            assert len(r["mesures"]) == 1
            assert r["mesures"][0]["analyse_id"] == seconde.id

    def test_un_role_sans_mesure_pour_ce_mois_vaut_NUL_jamais_zero(self, auth_client, ids):
        """⚠️ NULL ≠ 0 : « pas mesuré » et « ne pèse rien » ne se corrigent pas
        de la même façon, et l'écran dit en quel mois il l'a été."""
        with _Decor(auth_client, ids) as d:
            d.role("M")
            d.analyse("M", "2026-10")
            r = self._role(d, "M", "2026-10")
            assert r["mesure"] is True
            # le mois SUIVANT : rien n'a été mesuré
            d.role("Q")
            d.analyse("Q", "2026-11")
            r = self._role(d, "M", "2026-11")
            assert r["mesure"] is False
            assert r["annuel_min"] is None
            assert r["part"] is None
            assert r["derniere_periode"] == "2026-10"

    def test_un_role_JAMAIS_mesure_n_a_pas_de_derniere_periode(self, auth_client, ids):
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11")
            d.role("Jamais")
            r = self._role(d, "Jamais", "2026-11")
            assert r["mesure"] is False and r["derniere_periode"] is None

    def test_les_periodes_offertes_sont_celles_qui_portent_une_analyse(
            self, auth_client, ids):
        from Code.charge_travail import periodes_disponibles
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11")
            d.analyse("Q", "2026-09")
            p = periodes_disponibles()
            assert "2026-11" in p and "2026-09" in p
            assert p == sorted(p, reverse=True)

    def test_le_poids_en_BLOC_donne_le_MEME_chiffre_que_la_page_Temps(
            self, auth_client, ids):
        """⚠️ Une seule implémentation : `_role_summary` est appelé avec ses
        caches ici, sans eux là-bas. Deux versions finiraient par donner deux
        chiffres pour la même analyse."""
        from Code.routes.time_view import _role_summary
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            R = d.analyse("Q", "2026-11", n=4, duree=75, rec="hebdomadaire", freq=2)
            seul = _role_summary(R)["annual_minutes"]
            r = self._role(d, "Q", "2026-11")
            assert r["annuel_min"] == pytest.approx(seul)


# ═══════════════════════════════════════════════════════════════════════════
#  LE POIDS D'UNE PERSONNE, ET LE PLAFOND
# ═══════════════════════════════════════════════════════════════════════════

class TestLePoidsDUnePersonne:

    def _gens(self, d, prenom, periode=None):
        from Code.charge_travail import charge
        c = charge(periode)
        return next(p for p in c["personnes"] if p["id"] == d.gens[prenom].id)

    def test_c_est_la_SOMME_de_ses_roles_chacun_en_ENTIER(self, auth_client, ids):
        """⚠️ Le poids d'un rôle est le travail qu'il exige de qui le tient :
        on ne le divise pas par le nombre de titulaires — ce serait inventer
        un partage que rien dans l'application ne décide."""
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("A")
            d.role("B")
            d.analyse("A", "2026-11", n=4, duree=60)
            d.analyse("B", "2026-11", n=2, duree=30)
            d.personne("Un", ("A", "B"))
            d.personne("Deux", ("A",))          # deux titulaires sur « A »
            c = charge("2026-11")
            ra = next(r for r in c["roles"] if r["id"] == d.roles["A"].id)
            rb = next(r for r in c["roles"] if r["id"] == d.roles["B"].id)
            un = self._gens(d, "Un", "2026-11")
            deux = self._gens(d, "Deux", "2026-11")
            assert un["annuel_min"] == pytest.approx(ra["annuel_min"] + rb["annuel_min"])
            assert deux["annuel_min"] == pytest.approx(ra["annuel_min"])
            assert len(ra["titulaires"]) == 2

    def test_aucun_role_mesure_rend_NUL_jamais_zero(self, auth_client, ids):
        """⚠️ Zéro se lirait « cette personne n'a rien à faire »."""
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11")
            d.role("Sans")
            d.personne("Vide", ("Sans",))
            p = self._gens(d, "Vide", "2026-11")
            assert p["annuel_min"] is None and p["part_plafond"] is None
            assert p["sans_mesure"] == 1 and p["n_roles"] == 1

    def test_un_role_non_mesure_est_COMPTE_a_part_pas_additionne(self, auth_client, ids):
        with _Decor(auth_client, ids) as d:
            d.role("A")
            d.role("Sans")
            d.analyse("A", "2026-11", n=4, duree=60)
            d.personne("Moitie", ("A", "Sans"))
            p = self._gens(d, "Moitie", "2026-11")
            assert p["sans_mesure"] == 1
            assert p["annuel_min"] is not None

    def test_le_plafond_vaut_QUATRE_VINGTS_POUR_CENT_du_temps_plein(
            self, auth_client, ids):
        from Code.charge_travail import PART_PLAFOND, charge
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11")
            c = charge("2026-11")
            assert PART_PLAFOND == 0.80
            assert c["plafond_min"] == pytest.approx(c["plein_temps_min"] * 0.80)
            # ⚠️ Le temps plein se lit sur le calendrier que la réponse
            # PORTE : hors requête, `get_calendar_params` retombe sur la
            # première ligne de `entreprise_settings`, qui n'est pas forcément
            # celle du décor — un chiffre en dur ne tiendrait qu'au hasard de
            # l'ordre des fichiers.
            cal = c["calendrier"]
            assert c["plein_temps_min"] == pytest.approx(
                cal["hours_per_day"] * cal["days_per_week"] * cal["weeks_per_year"] * 60)


class TestLeVerdictDUnAjout:

    def test_il_dit_AVANT_APRES_et_s_il_depasse(self, auth_client, ids):
        from Code.charge_travail import charge, verdict_ajout
        with _Decor(auth_client, ids) as d:
            d.role("Lourd")
            d.role("Leger")
            # journalier × 47 sem × 5 j : 4 × 120 min = 1 880 h/an → au-delà
            d.analyse("Lourd", "2026-11", n=4, duree=120, rec="journalier")
            d.analyse("Leger", "2026-11", n=1, duree=10, rec="mensuel")
            d.personne("Qui", ("Leger",))
            c = charge("2026-11")
            v = verdict_ajout(c, d.gens["Qui"].id, d.roles["Lourd"].id)
            assert v["depasse"] is True
            assert v["deja"] is False
            assert v["apres_min"] == pytest.approx(v["avant_min"] + v["ajout_min"])

    def test_un_role_NON_mesure_n_ajoute_rien_de_connu(self, auth_client, ids):
        from Code.charge_travail import charge, verdict_ajout
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11")
            d.role("Sans")
            d.personne("Qui", ("Q",))
            c = charge("2026-11")
            assert verdict_ajout(c, d.gens["Qui"].id, d.roles["Sans"].id) is None


# ═══════════════════════════════════════════════════════════════════════════
#  CE QUE LE CALCUL NE DOIT PAS FAIRE
# ═══════════════════════════════════════════════════════════════════════════

class TestLeCoutEtLesEffetsDeBord:

    def test_le_cout_ne_grandit_pas_avec_l_effectif(self, auth_client, ids):
        """⚠️ Un nombre FIXE de requêtes : `_role_summary` appelé en boucle
        demanderait `get_calendar_params()` et une requête par ligne — c'est le
        défaut qui mettait le tableau des compétences à deux minutes et demie."""
        from sqlalchemy import event
        from Code.charge_travail import charge

        def compter():
            n = [0]

            def avant(*_a, **_k):
                n[0] += 1
            event.listen(db.engine, "before_cursor_execute", avant)
            try:
                charge("2026-11")
            finally:
                event.remove(db.engine, "before_cursor_execute", avant)
            return n[0]

        with _Decor(auth_client, ids) as d:
            for nom in ("A", "B"):
                d.role(nom)
                d.analyse(nom, "2026-11", n=3)
            d.personne("P1", ("A",))
            avant = compter()
            for nom in ("C", "D", "E", "F"):
                d.role(nom)
                d.analyse(nom, "2026-11", n=3)
            for p in ("P2", "P3", "P4", "P5", "P6"):
                d.personne(p, ("A", "C"))
            apres = compter()
            assert apres == avant, "%d requêtes puis %d" % (avant, apres)

    def test_la_lecture_n_ECRIT_rien(self, auth_client, ids):
        """Une page de lecture ne matérialise rien : le compte des lignes ne
        bouge pas."""
        from Code.models.models import TimeRoleAnalysis, TimeRoleLine
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11")
            avant = (TimeRoleAnalysis.query.count(), TimeRoleLine.query.count())
            charge("2026-11")
            charge(None)
            assert (TimeRoleAnalysis.query.count(), TimeRoleLine.query.count()) == avant


class TestLaPorteDeLaRoute:

    def test_sans_compte_elle_refuse(self, app):
        """⚠️ Le `before_request` du blueprint ne ferme que les ÉCRITURES, et
        ce tableau nomme la charge de chacun."""
        anon = app.test_client()
        r = anon.get("/gestion_rh/api/charge")
        assert r.status_code == 401

    def test_un_compte_sans_acces_RH_est_refuse(self, app, auth_client, ids):
        from Code.models.models import User
        from Code.security import hash_password
        u = User(email="ch171-simple@t.local", first_name="S", last_name="X",
                 password=hash_password("x"), status="user")
        db.session.add(u)
        db.session.commit()
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = u.id
            sess["user_email"] = u.email
        r = c.get("/gestion_rh/api/charge")
        assert r.status_code == 403
        db.session.delete(db.session.get(User, u.id))
        db.session.commit()

    def test_elle_sert_le_payload_a_qui_ouvre_la_page_RH(self, auth_client, ids):
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11")
            j = auth_client.get("/gestion_rh/api/charge?periode=2026-11").get_json()
            assert j["ok"] and j["periode"] == "2026-11"
            assert "plafond_min" in j and "roles" in j and "personnes" in j


# ═══════════════════════════════════════════════════════════════════════════
#  L'ÉCRAN
# ═══════════════════════════════════════════════════════════════════════════

class TestLaSectionEstBranchee:

    def test_le_gabarit_porte_la_section_et_charge_son_script(self):
        h = _lire("Code/routes/templates/gestion_rh.html")
        assert 'id="bloc-charge"' in h
        assert 'id="ch-corps"' in h
        assert "js/rh_charge.js" in h
        assert 'id="grh-ch-win"' in h

    def test_les_cles_lues_par_le_JS_sont_toutes_injectees(self):
        """⚠️ L'accesseur rend la CLÉ quand elle manque — jamais un repli
        français en dur. Une clé oubliée s'affiche donc telle quelle."""
        js = _lire("static/js/rh_charge.js")
        h = _lire("Code/routes/templates/gestion_rh.html")
        lues = set(re.findall(r"[LV]\('(ch_[a-z0-9_]+)'", js))
        lues |= {m + "_1" for m in re.findall(r"nf\('(ch_[a-z0-9_]+)'", js)}
        lues |= {m + "_n" for m in re.findall(r"nf\('(ch_[a-z0-9_]+)'", js)}
        bloc = h.split("window.RHCH_I18N", 1)[1].split("};", 1)[0]
        injectees = set(re.findall(r"(ch_[a-z0-9_]+):", bloc))
        assert lues <= injectees, sorted(lues - injectees)

    def test_les_cles_existent_dans_les_DEUX_langues(self):
        from Code.translations import TRANSLATIONS as T
        fr = {k for k in T["fr"] if k.startswith("rh.ch_")}
        en = {k for k in T["en"] if k.startswith("rh.ch_")}
        assert fr and fr == en
        # et l'anglais n'est pas une recopie du français
        recopies = [k for k in fr if T["fr"][k] == T["en"][k] and len(T["fr"][k]) > 14]
        assert not recopies, recopies

    def test_la_rampe_est_declaree_sur_ROOT_pas_sur_le_bloc(self):
        """⚠️ Une propriété personnalisée ne descend qu'à ses DESCENDANTS. La
        cellule de charge vit dans le bloc des personnes, la fenêtre et
        l'avertissement hors de tout bloc : déclarée sur `#bloc-charge`,
        `--ch-rouge` y était INVALIDE, donc transparent — la pastille d'alerte
        et le bouton « Ajouter quand même » étaient des rectangles vides."""
        css = _sans_commentaires_css(_lire("static/gestion_rh.css"))
        decl = re.search(r":root\s*\{[^}]*--ch-rouge", css)
        assert decl, "la rampe doit vivre sur :root"
        assert not re.search(r"#bloc-charge\s*\{[^}]*--ch-rouge", css)

    def test_le_repli_etroit_de_la_carte_d_une_personne_est_REDIT(self):
        """⚠️ Le `@media (max-width: 900px)` qui la remet sur deux colonnes est
        déclaré neuf cents lignes plus haut : à spécificité égale, c'est la
        DERNIÈRE déclaration qui gagne, et la règle à six colonnes l'écrasait
        aussi en dessous de 900 px."""
        css = _sans_commentaires_css(_lire("static/gestion_rh.css"))
        i = css.index(".grh-person {", css.index("--ch-rouge"))
        apres = css[i:]
        bloc = [b for b in apres.split("@media (max-width: 900px) {")[1:]]
        assert bloc, "le repli doit être redit APRÈS la règle à six colonnes"
        assert "grid-template-columns: auto 1fr" in bloc[0]
        assert "grh-person-ch" in bloc[0]

    def test_aucune_regle_de_la_section_ne_lit_le_gris_de_la_racine(self):
        """Les quatre dérivés de l'accent sont déclarés là où l'accent vaut
        encore le gris par défaut : ils rendent du GRIS."""
        bout = _section_charge(_lire("static/gestion_rh.css"))
        assert not re.findall(r"--pg-accent-(?:soft|softer|border|glow)", bout)

    def test_la_cellule_de_charge_est_posee_VIDE_et_remplie_par_rh_charge(self):
        """Une seule source pour la charge : `gestion_rh.js` n'a pas à
        connaître son calcul, et aucun des deux fichiers n'attend l'autre."""
        g = _lire("static/js/gestion_rh.js")
        c = _lire("static/js/rh_charge.js")
        assert 'class="grh-person-ch" data-ch="${p.id}"' in g
        # ⚠️ Le DISPATCH, pas le nom : celui-ci figure AUSSI dans le
        # commentaire qui explique la couture, et le cliquet restait vert
        # — treizième fois que cette famille mord.
        assert "document.dispatchEvent(new CustomEvent('grh:personnes'))" in g
        assert "document.addEventListener('grh:personnes'" in c

    def test_l_avertissement_est_une_PREVENTION_pas_un_refus(self):
        """La décision d'affecter quelqu'un appartient à qui affecte."""
        c = _lire("static/js/rh_charge.js")
        corps = c.split("function avertir(", 1)[1].split("\n  }", 1)[0]
        assert "ch-al-ok" in corps and "suite()" in corps
        g = _lire("static/js/gestion_rh.js")
        # ⚠️ La carto cochée part AVEC depuis que le poids d'un titulaire suit
        # son attache : le verdict doit porter sur CETTE carto, pas sur la
        # somme de toutes celles du rôle. On vise donc l'appel ET sa suite,
        # sans épingler la signature entière — c'est le GESTE qui compte.
        assert "window.RHCharge.avertir(u, r, el, () => majLien(u, r, true)" in g
        assert "majLien(u, r, true), ou)" in g

    def test_le_defilement_de_l_avertissement_est_INSTANTANE(self):
        """⚠️ Une animation ne progresse pas dans un volet qui ne peint pas —
        mesuré, l'avertissement restait 102 px sous le bord."""
        corps = _lire("static/js/rh_charge.js").split("function avertir(", 1)[1]
        assert "behavior: 'instant'" in corps
        assert "behavior: 'smooth'" not in corps.split("\n  }", 1)[0]


class TestCeQueLeDamierNeMontrePas:

    def test_les_colonnes_sont_les_cartos_REELLEMENT_mesurees(self):
        """⚠️ Neuf rôles pour trois cartos laisseraient les deux tiers des
        cases vides, et un damier creux se lit comme un tableau cassé."""
        js = _lire("static/js/rh_charge.js")
        corps = js.split("function colonnes(", 1)[1].split("\n  }", 1)[0]
        assert "mesures.forEach" in corps
        assert "entites" not in corps.replace("entite_id", "")

    def test_les_roles_sans_mesure_sortent_de_la_matrice(self):
        js = _lire("static/js/rh_charge.js")
        corps = js.split("function rendre(", 1)[1].split("\n  }", 1)[0]
        assert "r.mesure)" in corps and "!r.mesure)" in corps
        assert "zoneSansMesure(sans)" in corps
        # ... et la matrice ne reçoit QUE les mesurés
        assert "damier(mes," in corps

    def test_aucun_role_pese_n_affiche_PAS_un_damier_a_zero_colonne(self):
        """Il resterait trois en-têtes au-dessus de rien, ce qui se lit comme
        un tableau cassé — alors que la vérité a une suite : la page Temps."""
        js = _lire("static/js/rh_charge.js")
        corps = js.split("function rendre(", 1)[1].split("\n  }", 1)[0]
        assert "if (!mes.length) {" in corps
        avant = corps.split("if (!mes.length) {", 1)[1].split("return;", 1)[0]
        assert "ch-vide" in avant and "zoneSansMesure(sans)" in avant


# ═══════════════════════════════════════════════════════════════════════════
#  LE PLAN DE FORMATION : l'écran vide invite, et l'IA montre qu'elle tourne
# ═══════════════════════════════════════════════════════════════════════════

class TestLEcranVideDuPlanInvite:

    def test_l_action_est_EN_PLEIN_dans_le_bloc_vide(self):
        """⚠️ « Aucun plan n'existe encore » et « vous ne pouvez rien faire
        ici » se ressemblaient : un texte gris centré, et pour toute porte une
        pastille discrète au fond d'un pied de page."""
        js = _lire("static/js/competences_v2.js")
        corps = js.split("function blocVide(", 1)[1].split("\n  }\n", 1)[0]
        assert 'class="pl-go"' in corps and "data-pl-prop" in corps
        assert "pl-vide-chs" in corps, "de quoi partir doit être sous les yeux"

    def test_une_seule_porte_le_pied_ne_redit_pas_le_bouton(self):
        js = _lire("static/js/competences_v2.js")
        corps = js.split("    if (!p.activites.length || !p.actions.length) {", 1)[1]
        corps = corps.split("\n    }", 1)[0]
        assert "pied()" not in corps

    def test_l_attente_de_l_IA_montre_le_SQUELETTE_de_la_frise(self):
        """Trois secondes où rien ne bougeait : on cliquait une seconde fois."""
        js = _lire("static/js/competences_v2.js")
        assert "function renderAttenteIA()" in js
        corps = js.split("async function proposerPlan()", 1)[1].split("\n  }", 1)[0]
        assert "renderAttenteIA();" in corps
        att = js.split("function renderAttenteIA()", 1)[1].split("\n  }", 1)[0]
        assert "pl-att-fr" in att and "teteDuPlan()" in att

    def test_l_en_tete_du_plan_n_est_ECRIT_QU_UNE_FOIS(self):
        """Trois états de l'écran — le plan, le vide, l'attente — et c'est lui
        qui dit de qui et de quel rôle on parle."""
        js = _lire("static/js/competences_v2.js")
        assert js.count('<div class="pl-nuit"><div class="pl-h">') == 1

    def test_les_cles_de_l_ecran_vide_existent_dans_les_deux_langues(self):
        js = _lire("static/js/competences_v2.js")
        for cle in ("plan_empty_1", "plan_empty_n", "plan_empty_how", "plan_gen_l"):
            assert js.count(cle + ":") == 2, cle
        # la phrase d'avant parlait de « curseurs » qui n'existent plus
        assert "plan_empty_d" not in js


# ═══════════════════════════════════════════════════════════════════════════
#  OÙ UNE PERSONNE TIENT SON RÔLE — « qui performe »
# ═══════════════════════════════════════════════════════════════════════════

class TestLePoidsSuitLAttache:
    """⚠️ Un rôle est COMMUN à l'entreprise et peut porter des activités dans
    plusieurs cartos. Sans attache, le poids d'un titulaire était la SOMME de
    toutes les cartos — donc le même chiffre pour tous les titulaires du rôle,
    et deux personnes ne se comparaient pas. C'est la question posée :
    « pour un même rôle, la charge de différents champions ».
    """

    def test_sans_attache_c_est_la_SOMME_des_cartos(self):
        """⚠️ Le comportement d'AVANT, à l'identique : c'est ce qui rend la
        colonne sûre sur une instance en service. Rien ne bouge tant que
        personne n'a situé qui que ce soit."""
        from Code.charge_travail import poids_du_role
        poids = {7: 300.0}
        carto = {7: {1: 200.0, 2: 100.0}}
        assert poids_du_role(poids, carto, 7, None) == 300.0

    def test_attachee_c_est_SA_carto_et_elle_seule(self):
        from Code.charge_travail import poids_du_role
        poids = {7: 300.0}
        carto = {7: {1: 200.0, 2: 100.0}}
        assert poids_du_role(poids, carto, 7, 1) == 200.0
        assert poids_du_role(poids, carto, 7, 2) == 100.0

    def test_attachee_la_ou_le_role_n_est_PAS_mesure_rend_NUL(self):
        """⚠️ NUL, pas zéro — même si le rôle est mesuré ailleurs. Elle
        travaille là où personne n'a pesé ce rôle : « on ne sait pas » et
        « rien à faire » ne demandent pas le même geste."""
        from Code.charge_travail import poids_du_role
        assert poids_du_role({7: 300.0}, {7: {1: 300.0}}, 7, 99) is None


class TestDeuxTitulairesDuMemeRoleSeComparent:

    def test_chacun_porte_le_poids_de_SA_carto(self, auth_client, ids):
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=4, duree=60, carto=d.ent)
            d.analyse("Q", "2026-11", n=2, duree=60, carto=d.ent2)
            un = d.personne("Un", (("Q", d.ent),))
            deux = d.personne("Deux", (("Q", d.ent2),))
            p = charge("2026-11")
            gens = {x["id"]: x for x in p["personnes"]}
            a, b = gens[un.id]["annuel_min"], gens[deux.id]["annuel_min"]
            assert a and b and a != b, (
                "deux titulaires du même rôle sur deux cartos doivent porter "
                "des charges DIFFÉRENTES : %s / %s" % (a, b))
            # Et chacune est bien celle de sa carto, pas la moitié du total.
            role = next(r for r in p["roles"] if r["id"] == d.roles["Q"].id)
            par = {m["entite_id"]: m["annuel_min"] for m in role["mesures"]}
            assert a == par[d.ent.id] and b == par[d.ent2.id]
            assert role["annuel_min"] == a + b

    def test_sans_attache_les_DEUX_portent_le_total(self, auth_client, ids):
        """Le filet de sécurité, dans l'autre sens : rien n'a changé pour qui
        n'est pas situé."""
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=4, duree=60, carto=d.ent)
            d.analyse("Q", "2026-11", n=2, duree=60, carto=d.ent2)
            un = d.personne("Un", ("Q",))
            deux = d.personne("Deux", ("Q",))
            p = charge("2026-11")
            gens = {x["id"]: x for x in p["personnes"]}
            role = next(r for r in p["roles"] if r["id"] == d.roles["Q"].id)
            assert gens[un.id]["annuel_min"] == role["annuel_min"]
            assert gens[deux.id]["annuel_min"] == role["annuel_min"]


class TestPersonneNeDisparaitDeSaLigne:
    """⚠️ Le défaut vu à l'écran : attachée à une carto où le rôle n'est pas
    mesuré, une personne ne tombait dans AUCUNE case — ni dans « non situés »,
    puisqu'elle EST située. Elle disparaissait de la ligne de son propre rôle.
    """

    def test_elle_est_posee_dans_la_case_de_SA_carto_meme_sans_mesure(
            self, auth_client, ids):
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("M")
            d.analyse("M", "2026-11", n=3, duree=60, carto=d.ent)  # ent seule
            qui = d.personne("Perdue", (("M", d.ent2),))           # ailleurs
            role = next(r for r in charge("2026-11")["roles"]
                        if r["id"] == d.roles["M"].id)
            place = role["titulaires_carto"].get(str(d.ent2.id)) or []
            assert [t["id"] for t in place] == [qui.id], (
                "une personne située sur une carto sans mesure doit rester "
                "visible dans la case de SA carto")
            assert not role["sans_carto"], "elle EST située : pas « non situé »"

    def test_les_cles_de_titulaires_carto_sont_du_TEXTE(self, auth_client, ids):
        """⚠️ C'est ce que le navigateur compare (`String(entite_id)`) : une
        clé entière ne tomberait sur aucune colonne, en silence."""
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=3, carto=d.ent)
            d.personne("Un", (("Q", d.ent),))
            role = next(r for r in charge("2026-11")["roles"]
                        if r["id"] == d.roles["Q"].id)
            assert all(isinstance(k, str) for k in role["titulaires_carto"])

    def test_sans_carto_ne_porte_QUE_les_non_situes(self, auth_client, ids):
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=3, carto=d.ent)
            situe = d.personne("Situe", (("Q", d.ent),))
            libre = d.personne("Libre", ("Q",))
            role = next(r for r in charge("2026-11")["roles"]
                        if r["id"] == d.roles["Q"].id)
            assert [t["id"] for t in role["sans_carto"]] == [libre.id]
            places = [t["id"] for v in role["titulaires_carto"].values() for t in v]
            assert places == [situe.id]


class TestLeVerdictSuitLaCarto:

    def test_il_annonce_le_poids_de_LA_CARTO_cochee(self, auth_client, ids):
        """⚠️ Sans la carto, l'avertissement annoncerait la somme de toutes
        les cartos du rôle alors que la personne n'en portera qu'une : un
        plafond franchi sur le papier et pas en vrai."""
        from Code.charge_travail import charge, verdict_ajout
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=8, duree=60, carto=d.ent)
            d.analyse("Q", "2026-11", n=2, duree=60, carto=d.ent2)
            qui = d.personne("Un", ())
            p = charge("2026-11")
            role = next(r for r in p["roles"] if r["id"] == d.roles["Q"].id)
            par = {m["entite_id"]: m["annuel_min"] for m in role["mesures"]}
            petit = verdict_ajout(p, qui.id, d.roles["Q"].id, d.ent2.id)
            assert petit["ajout_min"] == par[d.ent2.id]
            tout = verdict_ajout(p, qui.id, d.roles["Q"].id, None)
            assert tout["ajout_min"] == role["annuel_min"]
            assert petit["ajout_min"] < tout["ajout_min"]

    def test_une_carto_sans_mesure_ne_previent_de_RIEN(self, auth_client, ids):
        """On ne prévient pas d'un dépassement qu'on ne sait pas calculer."""
        from Code.charge_travail import charge, verdict_ajout
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            d.analyse("Q", "2026-11", n=8, duree=60, carto=d.ent)
            qui = d.personne("Un", ())
            p = charge("2026-11")
            assert verdict_ajout(p, qui.id, d.roles["Q"].id, d.ent2.id) is None


class TestLaRouteQuiSitue:

    def _poser(self, client, u, r, e):
        return client.post("/gestion_rh/role_carto",
                           json={"user_id": u, "role_id": r, "entity_id": e})

    def test_elle_pose_et_elle_DETACHE(self, auth_client, ids):
        from Code.models.models import UserRole
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", ("Q",))
            rid = d.roles["Q"].id
            assert self._poser(auth_client, qui.id, rid, d.ent.id).status_code == 200
            db.session.expire_all()
            assert UserRole.query.filter_by(
                user_id=qui.id, role_id=rid).first().entity_id == d.ent.id
            # ⚠️ Le retour : sans lui, une attache posée par mégarde ne
            # s'enlèverait plus, et la personne resterait comptée sur une
            # carto où elle ne travaille pas.
            assert self._poser(auth_client, qui.id, rid, None).status_code == 200
            db.session.expire_all()
            assert UserRole.query.filter_by(
                user_id=qui.id, role_id=rid).first().entity_id is None

    def test_une_carto_inconnue_est_REFUSEE(self, auth_client, ids):
        """L'identifiant vient du navigateur : une attache qui ne désigne rien
        ferait sortir la personne de tous les comptages sans rien dire."""
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", ("Q",))
            r = self._poser(auth_client, qui.id, d.roles["Q"].id, 99999999)
            assert r.status_code == 404

    def test_un_role_qu_elle_ne_tient_PAS_est_refuse(self, auth_client, ids):
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", ())
            r = self._poser(auth_client, qui.id, d.roles["Q"].id, d.ent.id)
            assert r.status_code == 404
            assert (r.get_json() or {}).get("code") == "sans_lien"

    def test_elle_est_fermee_a_qui_n_ouvre_pas_la_page_RH(self, app, ids):
        """⚠️ Un client ANONYME : `client` et `auth_client` sont le même objet
        en portée session, et il arrive connecté."""
        c = app.test_client()
        r = c.post("/gestion_rh/role_carto",
                   json={"user_id": 1, "role_id": 1, "entity_id": None})
        assert r.status_code in (401, 403)


class TestCocherRemplitMaisNeDEPLACEPas:
    """⚠️ Cocher un rôle depuis une carto dit « cette personne tient ce
    rôle ». L'attache est un SECOND fait, plus lourd — c'est lui qui décide de
    sa charge mesurée. Un second fait ne s'écrit pas par un geste qui visait
    le premier, surtout depuis la page RH où la carto du bandeau peut n'être
    que celle qu'on regardait.
    """

    def test_un_lien_neuf_est_attache_a_la_carto_du_geste(self, auth_client, ids):
        from Code.models.models import UserRole
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", ())
            r = auth_client.post(
                "/cartography/api/access/%d/roles/%d/holders"
                % (d.ent.id, d.roles["Q"].id), json={"add": [qui.id]})
            assert r.status_code == 200
            db.session.expire_all()
            lien = UserRole.query.filter_by(user_id=qui.id,
                                            role_id=d.roles["Q"].id).first()
            assert lien is not None and lien.entity_id == d.ent.id

    def test_une_attache_DEJA_posee_ne_bouge_pas(self, auth_client, ids):
        from Code.models.models import UserRole
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", (("Q", d.ent2),))
            auth_client.post("/cartography/api/access/%d/roles/%d/holders"
                             % (d.ent.id, d.roles["Q"].id), json={"add": [qui.id]})
            db.session.expire_all()
            lien = UserRole.query.filter_by(user_id=qui.id,
                                            role_id=d.roles["Q"].id).first()
            assert lien.entity_id == d.ent2.id, (
                "cocher depuis une autre carto ne doit pas DÉPLACER une "
                "attache posée : seul /gestion_rh/role_carto la déplace")


class TestSupprimerUneCartoDETACHE:
    """⚠️ `user_roles.entity_id` est une clé étrangère vers `entities` :
    PostgreSQL refuserait la suppression (SQLite non — le défaut ne se verrait
    qu'en production). On détache, on ne retire pas le rôle : la personne le
    tient toujours, on ne sait simplement plus où."""

    def test_la_personne_garde_son_role_sans_sa_carto(self, auth_client, ids):
        from Code.models.models import Entity, UserRole
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", (("Q", d.ent2),))
            rid, eid = d.roles["Q"].id, d.ent2.id
            r = auth_client.delete("/activities/api/entities/%d" % eid)
            assert r.status_code == 200, r.get_data(as_text=True)[:200]
            db.session.expire_all()
            lien = UserRole.query.filter_by(user_id=qui.id, role_id=rid).first()
            assert lien is not None, "le rôle ne doit pas partir avec la carto"
            assert lien.entity_id is None
            assert db.session.get(Entity, eid) is None
            # ⚠️ Le décor ne doit plus toucher à ce qui vient d'être supprimé :
            # lire `.id` sur une instance effacée lève (SQLAlchemy tente de la
            # rafraîchir). On retire la carto ET ses activités de l'inventaire.
            d.actes.pop(eid, None)
            d.ent2 = d.ent


class TestLEcranSitueEtCompare:

    JS = "static/js/rh_charge.js"

    def test_la_case_lit_titulaires_carto_du_SERVEUR(self):
        js = _lire(self.JS)
        assert "titulaires_carto" in js, (
            "le placement vient du serveur : un second calcul de l'attache "
            "dans le navigateur finirait par ne plus dire la même chose")

    def test_une_case_VIDE_porte_quand_meme_ses_titulaires(self):
        """Sinon la personne disparaît de la ligne de son propre rôle."""
        js = _lire(self.JS)
        i = js.index("const pastilles")
        j = js.index("const n = niveau", i)
        assert "pastilles" in js[i:j].split("if (!m)", 1)[-1], (
            "la branche « pas de mesure » doit poser les pastilles")

    def test_la_colonne_non_situes_DISPARAIT_quand_tout_est_situe(self):
        js = _lire(self.JS)
        assert "const libres = roles.some" in js
        # ⚠️ Les deux fragments EXACTS, pas le nom du drapeau : « libres ? »
        # est une SOUS-CHAÎNE de « !libres ? », donc retirer la garde de
        # l'en-tête laissait ce cas au VERT — il ne gardait rien.
        assert "${libres ? `<th" in js, "l'en-tête de la colonne doit suivre"
        assert "${!libres ? '' : `<td" in js, "les cellules doivent suivre"

    def test_le_verdict_prend_la_carto(self):
        js = _lire(self.JS)
        assert "function verdict(userId, roleId, entiteId)" in js
        grh = _lire("static/js/gestion_rh.js")
        assert "RHCharge.avertir(u, r, el" in grh and ", ou)" in grh, (
            "la carto cochée doit partir avec l'avertissement")

    def test_les_libelles_existent_dans_les_DEUX_langues(self):
        from Code.translations import TRANSLATIONS
        for cle in ("rh.ch_holders_free", "rh.ch_where", "rh.ch_where_none",
                    "rh.ch_where_nomes", "rh.ch_where_empty", "rh.ch_nomes_ici"):
            for lang in ("fr", "en"):
                assert TRANSLATIONS[lang].get(cle), "%s manque en %s" % (cle, lang)
            assert TRANSLATIONS["fr"][cle] != TRANSLATIONS["en"][cle], (
                "%s : l'anglais recopie le français" % cle)

    def test_elles_sont_INJECTEES_dans_le_gabarit(self):
        html = _lire("Code/routes/templates/gestion_rh.html")
        for cle in ("ch_holders_free", "ch_where", "ch_where_none",
                    "ch_where_nomes", "ch_where_empty", "ch_nomes_ici"):
            assert cle + ":" in html, (
                "%s n'est pas injectée : l'accesseur rendrait la CLÉ, et rien "
                "ne lève d'erreur" % cle)

    def test_pas_d_espace_avant_le_pourcent_en_anglais(self):
        """Une convention FRANÇAISE, à côté des « 162% » que `pct()` écrit
        déjà sans espace — deux formes du même signe sur un écran."""
        from Code.translations import TRANSLATIONS
        assert " %" not in TRANSLATIONS["en"]["rh.ch_pct_full"]

    def test_la_pastille_de_case_garde_la_taille_du_marqueur(self):
        """⚠️ Essayée à 20 px, elle rendait ses initiales à 8,4 px RÉELS :
        `body.pg` porte `zoom: .8` et le plancher de l'échelle est 11."""
        css = _sans_commentaires_css(_lire("static/gestion_rh.css"))
        i = css.index(".ch-t-av .ch-av")
        bloc = css[i:css.index("}", i)]
        assert "width:" not in bloc and "font-size:" not in bloc, (
            "la pastille de case ne redéfinit ni sa taille ni sa police : "
            "c'est le MÊME marqueur que dans la colonne")

    def test_la_case_a_trois_lignes_monte_son_plancher(self):
        """Un `min-height` trop court déborde EN SILENCE."""
        css = _sans_commentaires_css(_lire("static/gestion_rh.css"))
        i = css.index(".ch-t:has(.ch-t-av)")
        bloc = css[i:css.index("}", i)]
        m = re.search(r"min-height:\s*(\d+)px", bloc)
        assert m and int(m.group(1)) >= 84, (
            "trois lignes (chiffre, compte, pastilles) ne tiennent pas dans "
            "la hauteur d'origine")



# ═══════════════════════════════════════════════════════════════════════════
#  LE MOIS SE CHOISIT DANS UN MINI CALENDRIER, DANS LE FORMULAIRE
# ═══════════════════════════════════════════════════════════════════════════

#: `tools/` est retiré de l'arbre d'image (bytecode seul) : les cas qui lisent
#  un semis y sautent franchement plutôt que de rougir à chaque exécution.
_SEMIS_ABSENT = not os.path.exists(os.path.join(RACINE, "tools", "db",
                                                "seed_charge.sql"))


class TestLeMoisEstUnMiniCalendrier:
    """⚠️ Il vivait dans la BANDE, au nom d'un argument juste — une propriété
    de l'analyse entière, et le seul endroit commun aux quatre types — et
    d'une conséquence fausse : la bande est un BANDEAU DE TITRE, le champ s'y
    lisait comme un réglage d'écran, isolé de ce qu'on remplit.

    Posé en tête de la colonne de saisie, il reste écrit UNE fois (donc
    toujours une seule implémentation, ce qui était tout l'argument) et il
    est DANS le formulaire.
    """

    HTML = "Code/routes/templates/time_dashboard.html"
    JS = "static/js/time.js"
    CSS = "static/time.css"

    def _html_nu(self):
        h = _lire(self.HTML)
        h = re.sub(r"<!--.*?-->", "", h, flags=re.S)
        return re.sub(r"\{#.*?#\}", "", h, flags=re.S)

    def test_le_champ_vit_dans_le_FORMULAIRE_et_plus_dans_la_bande(self):
        h = self._html_nu()
        barre = h.split('<div class="tm-barre">', 1)[1].split("</div>", 1)[0]
        assert "tm-mois" not in barre, (
            "le mois est reparti dans la bande : c'est un bandeau de TITRE, "
            "le champ s'y lit comme un réglage d'écran")
        saisie = h.split('<div class="tm-saisie">', 1)[1]
        assert 'id="tm-mois-b"' in saisie.split('subtab-projet', 1)[0], (
            "il doit être le PREMIER bloc de la colonne de saisie — écrit une "
            "fois, au-dessus des quatre panneaux")

    def test_ni_input_month_ni_deux_menus_deroulants(self):
        """⚠️ Firefox ne rend pas `type=month` et retombe sur un champ texte
        où il faut taper « 2026-11 ». Et deux menus déroulants composaient un
        mois en deux temps, alors qu'un mois se CHOISIT dans une année.

        ⚠️ Les COMMENTAIRES sont retirés d'abord : celui qui explique ce choix
        cite forcément les formes qu'il écarte."""
        h = self._html_nu()
        assert 'type=' + chr(34) + 'month' + chr(34) not in h
        assert 'id="tm-periode-m"' not in h and 'id="tm-periode-a"' not in h

    def test_douze_mois_et_une_annee_qu_on_fait_defiler(self):
        """⚠️ Trois pièges dans un seul cas, tous mesurés en le vérifiant
        rouge :
        · `est-auj` survit dans le COMMENTAIRE qui l'explique — d'où
          `_sans_commentaires_js` (dixième occurrence de cette famille) ;
        · `data-an` est une SOUS-CHAÎNE de `data-analyse`, que ce fichier
          emploie trois fois : on vise les deux flèches et leur sélecteur ;
        · la grille se vérifie sur son APPEL, pas sur un nom qui traîne."""
        js = _sans_commentaires_js(_lire(self.JS))
        assert "{ length: 12 }" in js, "les douze mois d'une année"
        assert 'data-an="-1"' in js and 'data-an="1"' in js, "les deux flèches"
        assert "querySelectorAll('[data-an]')" in js, "et leur câblage"
        assert "cls.push('est-auj')" in js, (
            "le mois COURANT se marque même quand il n'est pas choisi : sans "
            "lui, une année qu'on fait défiler n'a plus aucun point fixe")

    def test_le_panneau_est_pose_DANS_son_champ(self):
        """⚠️ Et jamais sur le body en `fixed` : `body.pg` porte `zoom: .8`,
        et tout élément posé sur le body doit alors convertir ses
        coordonnées — sept fois que ce piège se présente."""
        css = _sans_commentaires_css(_lire(self.CSS))
        i = css.index(".tm-mois-p {")
        bloc = css[i:css.index("}", i)]
        assert "position: absolute" in bloc
        assert "position: fixed" not in bloc
        j = css.index(".tm-mois-w")
        assert "position: relative" in css[j:css.index("}", j)], (
            "sans ancêtre positionné, l'`absolute` remonterait jusqu'au body")

    def test_le_panneau_declare_son_hidden(self):
        """⚠️ `[hidden]` est une règle du NAVIGATEUR : une classe d'auteur qui
        pose un `display` l'emporte. Neuvième fois."""
        css = _sans_commentaires_css(_lire(self.CSS))
        assert ".tm-mois-p[hidden]" in css

    def test_un_clic_dans_le_panneau_ne_le_ferme_pas(self):
        """⚠️ Et la cible d'un clic sur une case est DÉTACHÉE quand
        l'événement remonte (la grille vient d'être réécrite) : `closest()`
        ne trouverait plus rien. On arrête la remontée au panneau."""
        # ⚠️ Sur la LIGNE du panneau, pas sur la fonction : `stopPropagation`
        # y figure aussi pour le bouton et pour Échap, et le cas restait vert
        # en retirant celui qui compte.
        js = _sans_commentaires_js(_lire(self.JS))
        assert "z.addEventListener('click', (e) => e.stopPropagation())" in js

    def test_les_quatre_enregistrements_envoient_toujours_la_periode(self):
        js = _lire(self.JS)
        assert js.count("periode: periodeLue()") == 4

    def test_les_lectures_la_reposent_toujours(self):
        js = _lire(self.JS)
        assert js.count("posePeriode(") >= 6

    def test_les_libelles_existent_dans_les_DEUX_langues(self):
        from Code.translations import TRANSLATIONS
        for cle in ("time.periode_ce_mois", "time.periode_an_prec",
                    "time.periode_an_suiv"):
            for lang in ("fr", "en"):
                assert TRANSLATIONS[lang].get(cle), "%s manque en %s" % (cle, lang)
            assert TRANSLATIONS["fr"][cle] != TRANSLATIONS["en"][cle]

    def test_elles_sont_INJECTEES(self):
        """L'accesseur rend le défaut FRANÇAIS quand la clé manque : une
        injection oubliée ne lève rien, elle affiche du français."""
        h = _lire(self.HTML)
        for cle in ("periode_ce_mois", "periode_an_prec", "periode_an_suiv"):
            assert cle + ":" in h, "%s n'est pas injectée" % cle


@pytest.mark.skipif(_SEMIS_ABSENT, reason="tools/ est retiré de l'arbre d'image")
class TestLesSemisDATENTCeQuIlsCreent:
    """⚠️ Une analyse sans mois ne figure dans AUCUN tableau par période — ni
    le damier de la page RH, ni le sélecteur de la page Temps. Semée sans
    date elle est invisible, et on cherche longtemps pourquoi l'écran reste
    vide. C'est exactement ce qui manquait sur la carto de démonstration.
    """

    def test_seed_temps_pose_une_periode_sur_ses_quatre_tables(self):
        sql = _lire("tools/db/seed_temps.sql")
        assert "mois_courant text :=" in sql, "le mois doit être déclaré"
        for table in ("time_analysis", "time_role_analysis", "time_weakness",
                      "time_project"):
            # ⚠️ `\b` : « time_project » est un PRÉFIXE de
            # « time_project_line », qui n'a pas de période et n'en veut pas.
            m = re.search(r"INSERT INTO " + table + r"\b", sql)
            assert m, "plus d'insertion dans %s" % table
            entete = sql[m.start():sql.index("SELECT", m.start())]
            assert "periode" in entete, (
                "%s est semée SANS mois : elle n'apparaîtra nulle part" % table)
        assert sql.count("mois_courant") >= 5

    def test_seed_charge_vise_une_PART_de_temps_plein(self):
        """⚠️ Et non une durée « plausible ». Mesuré sur un premier jet : les
        parts sortaient entre 0 et 49 % quand l'échelle de couleur va de 25 %
        à plus de 150 % — toutes les cases dans les deux premières teintes,
        et la couleur, qui est toute l'information du damier, ne disait plus
        rien. La récurrence écrase tout : facteur 225 entre « journalier » et
        « annuel », que nulle durée raisonnable ne rattrape."""
        sql = _lire("tools/db/seed_charge.sql")
        assert "plein_min * d.cible" in sql, (
            "la durée se DÉDUIT de la part visée, pas l'inverse")
        assert "'trimestriel'" not in sql and "'annuel'" not in sql, (
            "ces deux récurrences demanderaient des durées absurdes à part "
            "égale (504 h en une fois)")

    def test_seed_charge_REFUSE_de_rejouer(self):
        sql = _sans_commentaires_sql(_lire("tools/db/seed_charge.sql"))
        i = sql.index("ELSIF deja > 0 THEN")
        assert "RAISE EXCEPTION" in sql[i:i + 400], (
            "un second passage empilerait une analyse par (rôle, mois), et "
            "la liste de la page Temps les montrerait toutes")
        assert "purger" in sql

    def test_le_refus_ne_compte_QUE_ce_que_le_semis_a_seme(self):
        """⚠️ Le défaut signalé : une SEULE analyse écrite à la main sur la
        carto fermait le semis, et la seule sortie offerte était
        `purger := true`, qui l'aurait détruite. Le garde-fou protège d'un
        REJEU, pas de l'existence d'une analyse."""
        sql = _sans_commentaires_sql(_lire("tools/db/seed_charge.sql"))
        i = sql.index("SELECT array_agg(DISTINCT ra.id) INTO ra_ids")
        bloc = sql[i:sql.index(";", i)]
        assert "ra.name LIKE marque" in bloc, (
            "sans la marque, le refus compte aussi les analyses faites à la "
            "main et le semis devient infranchissable")
        assert "deja := COALESCE(array_length(ra_ids, 1), 0);" in sql, (
            "le compte du refus doit sortir de ce relevé, et de lui seul")

    def test_la_purge_n_efface_QUE_ce_que_le_semis_a_seme(self):
        """Et elle est BORNÉE : avant, le second DELETE visait « toute
        analyse sans ligne », donc la base entière."""
        sql = _sans_commentaires_sql(_lire("tools/db/seed_charge.sql"))
        for table in ("time_role_line", "time_role_analysis"):
            m = re.search(r"DELETE FROM " + table + r"\b[^;]*;", sql)
            assert m, "plus de suppression dans %s" % table
            assert "ANY(ra_ids)" in m.group(0), (
                "la purge de %s doit se borner aux identifiants relevés, "
                "sinon elle efface ce qu'elle doit épargner" % table)

    def test_les_identifiants_sont_releves_AVANT_la_suppression(self):
        """Une fois les lignes parties, plus rien ne rattache l'analyse à sa
        carto : il faudrait retomber sur « toute analyse sans ligne »."""
        sql = _sans_commentaires_sql(_lire("tools/db/seed_charge.sql"))
        assert (sql.index("INTO ra_ids")
                < sql.index("DELETE FROM time_role_line"))

    def test_la_marque_du_semis_est_ecrite_a_UN_seul_endroit(self):
        """Deux écritures du préfixe finiraient par diverger, et la purge se
        mettrait alors à effacer ce qu'elle doit épargner."""
        sql = _sans_commentaires_sql(_lire("tools/db/seed_charge.sql"))
        m = re.search(r"marque\s+text\s+:=\s+'([^']+)'", sql)
        assert m, "la marque doit être déclarée une fois, en variable"
        assert sql.count("'" + m.group(1) + "'") == 1, (
            "le préfixe est réécrit en dur ailleurs : l'insertion et la "
            "purge peuvent alors ne plus parler du même nom")
        i = sql.index("INSERT INTO time_role_analysis")
        assert "marque ||" in sql[i:i + 400], (
            "l'insertion doit POSER la marque, pas un nom écrit en dur")

    def test_aucun_round_a_deux_arguments_sur_un_FLOTTANT(self):
        """⚠️ `round(double precision, integer)` N'EXISTE PAS en PostgreSQL —
        seule la forme à UN argument accepte un flottant. La requête 3 tombait
        donc sur `duration_minutes`, qui est un `db.Float`. Invisible à l'œil,
        et invisible aussi à un contrôle qui ne jouerait que les deux
        premières requêtes : un semis se prouve requête par requête.

        ⚠️ Les colonnes flottantes se lisent dans `db.metadata`, jamais dans
        le source des modèles : l'arbre d'image n'a pas les `.py`.
        """
        from sqlalchemy import Float

        flottantes = set()
        for table in db.metadata.tables.values():
            for col in table.columns:
                if isinstance(col.type, Float):
                    flottantes.add(col.name)
        assert len(flottantes) >= 5, (
            "aucune colonne flottante relevée : le contrôle ne lirait plus "
            "rien et passerait au vert sans rien vérifier")

        semis = sorted(f for f in os.listdir(os.path.join(RACINE, "tools", "db"))
                       if f.endswith(".sql"))
        assert len(semis) >= 3, "les semis ont disparu : contrôle creux"
        for nom in semis:
            sql = _sans_commentaires_sql(_lire("tools/db/" + nom))
            for appel in _appels(sql, "round"):
                args = _arguments(appel)
                if len(args) < 2:
                    continue                       # round(x) accepte un float
                touche = [c for c in flottantes
                          if re.search(r"\b" + re.escape(c) + r"\b", args[0])]
                if not touche:
                    continue
                assert "::numeric" in args[0], (
                    "%s : %s — %s est un FLOAT, convertir en numeric avant "
                    "d'arrondir" % (nom, " ".join(appel.split())[:60],
                                    touche[0]))

    def test_seed_charge_ne_DEPLACE_aucune_attache(self):
        """Déplacer l'attache de quelqu'un changerait sa charge mesurée :
        c'est une décision de la page RH, pas d'un semis."""
        sql = _lire("tools/db/seed_charge.sql")
        i = sql.index("UPDATE user_roles")
        assert "entity_id IS NULL" in sql[i:i + 400]

    def test_seed_charge_ecrit_les_colonnes_NOT_NULL(self):
        """⚠️ `delay_minutes` et `nb_people` n'ont de défaut que dans le
        MODÈLE : un INSERT en SQL brut doit les écrire lui-même."""
        sql = _lire("tools/db/seed_charge.sql")
        i = sql.index("INSERT INTO time_role_line")
        entete = sql[i:sql.index("SELECT", i)]
        assert "delay_minutes" in entete and "nb_people" in entete
