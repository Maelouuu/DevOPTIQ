# -*- coding: utf-8 -*-
"""LA CHARGE DE TRAVAIL — branches résiduelles, et leurs voisines.

Ce que `test_171` laissait de côté :
- `charge()` face à une analyse VIDE, sans rôle, ou dont les lignes pointent
  des activités disparues ; une durée prise sur l'ACTIVITÉ quand la ligne
  n'en porte pas ; un lien `user_roles` vers un rôle qui n'existe plus ;
- `verdict_ajout()` quand il n'y a rien à dire (personne ou rôle inconnus,
  pas de plafond) ;
- `mois_de()` sans moment ;
- les gardes des routes RH qui règlent l'attache, les cartos d'un rôle et le
  développeur (paramètres invalides, compte sans droit RH, anonyme) ;
- les lignes sans activité dans les modifications d'analyses de temps ;
- les replis défensifs du plan de formation.

⚠️ Chaque test bâtit ses données sur sa PROPRE carto (le `_Decor` de
`test_171`) ou sur des comptes à lui, et les détruit en sortant.
"""
import importlib.util
import os
import sys

import pytest

from Code.extensions import db

_ICI = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "_t171_decor", os.path.join(_ICI, "test_171_charge_travail.py"))
_t171 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_t171)
_Decor = _t171._Decor

PREFIXE = "t172."


def _role_de(payload, role_id):
    return next(r for r in payload["roles"] if r["id"] == role_id)


def _personne_de(payload, user_id):
    return next(p for p in payload["personnes"] if p["id"] == user_id)


# ═══════════════════════════════════════════════════════════════════════════
#  charge() — les analyses qu'on ne pèse pas, et celles qu'on pèse autrement
# ═══════════════════════════════════════════════════════════════════════════

class TestChargeAnalysesAtypiques:

    def test_une_analyse_sans_ligne_ne_mesure_pas_le_role(self, auth_client, ids):
        """Une analyse vide n'est pas un poids nul : le rôle reste NON mesuré."""
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("V")
            d.analyse("V", "2031-03", n=0)
            p = charge("2031-03")
            assert p["periode"] == "2031-03"
            r = _role_de(p, d.roles["V"].id)
            assert r["mesure"] is False
            assert r["annuel_min"] is None
            assert r["mesures"] == []

    def test_des_lignes_vers_des_activites_disparues_n_ont_pas_de_carto(
            self, auth_client, ids):
        """La mesure existe, mais ne désigne aucune carto : elle compte dans
        la somme du rôle et n'apparaît dans aucune colonne par carto."""
        from Code.charge_travail import charge
        from Code.models.models import TimeRoleAnalysis, TimeRoleLine
        with _Decor(auth_client, ids) as d:
            d.role("V")
            R = TimeRoleAnalysis(role_id=d.roles["V"].id, name="CH172 fantôme",
                                 periode="2031-05")
            db.session.add(R)
            db.session.flush()
            db.session.add(TimeRoleLine(role_analysis_id=R.id,
                                        activity_id=987654321,
                                        recurrence="journalier", frequency=1,
                                        duration_minutes=30.0))
            db.session.commit()
            d.analyses.append(R)
            qui = d.personne("Fan", (("V", d.ent),))
            p = charge("2031-05")
            r = _role_de(p, d.roles["V"].id)
            assert r["mesure"] is True
            assert [m["entite_id"] for m in r["mesures"]] == [None]
            assert r["mesures"][0]["entite"] == ""
            # Rattachée à une carto où le rôle n'est pas mesuré : NUL, pas zéro.
            moi = _personne_de(p, qui.id)
            assert moi["roles"][0]["annuel_min"] is None
            assert moi["roles"][0]["cartos"] == []
            assert moi["annuel_min"] is None

    def test_une_ligne_sans_duree_prend_celle_de_l_activite(self, auth_client, ids):
        """`_role_summary` reçoit les durées en bloc : la ligne vide retombe sur
        la durée de l'activité (60 min), sans requête par ligne."""
        from Code.charge_travail import charge
        with _Decor(auth_client, ids) as d:
            d.role("Z")
            d.role("S")
            d.analyse("Z", "2031-06", n=2, duree=0)
            d.analyse("S", "2031-06", n=2, duree=60)
            p = charge("2031-06")
            z = _role_de(p, d.roles["Z"].id)["annuel_min"]
            s = _role_de(p, d.roles["S"].id)["annuel_min"]
            assert z is not None and z > 0
            assert z == pytest.approx(s)

    def test_un_lien_vers_un_role_disparu_n_est_pas_compte(self, auth_client, ids):
        from Code.charge_travail import charge
        from Code.models.models import UserRole
        with _Decor(auth_client, ids) as d:
            d.role("V")
            d.analyse("V", "2031-07", n=2)
            qui = d.personne("Orph", ("V",))
            fantome = UserRole(user_id=qui.id, role_id=987654320)
            db.session.add(fantome)
            db.session.commit()
            p = charge("2031-07")
            moi = _personne_de(p, qui.id)
            assert [x["id"] for x in moi["roles"]] == [d.roles["V"].id]
            assert moi["n_roles"] == 1
            assert moi["sans_mesure"] == 0


# ═══════════════════════════════════════════════════════════════════════════
#  verdict_ajout() — rien à dire
# ═══════════════════════════════════════════════════════════════════════════

class TestVerdictAjoutSansObjet:

    def _payload(self):
        return {"plafond_min": 1000.0,
                "personnes": [{"id": 1, "annuel_min": 100.0}],
                "roles": [{"id": 7, "annuel_min": 50.0, "mesures": []}]}

    def test_personne_inconnue(self):
        from Code.charge_travail import verdict_ajout
        assert verdict_ajout(self._payload(), 2, 7) is None

    def test_role_inconnu(self):
        from Code.charge_travail import verdict_ajout
        assert verdict_ajout(self._payload(), 1, 8) is None

    def test_sans_plafond(self):
        from Code.charge_travail import verdict_ajout
        p = self._payload()
        p["plafond_min"] = 0
        assert verdict_ajout(p, 1, 7) is None

    def test_role_non_mesure(self):
        from Code.charge_travail import verdict_ajout
        p = self._payload()
        p["roles"][0]["annuel_min"] = None
        assert verdict_ajout(p, 1, 7) is None

    def test_cas_nominal_calcule_les_parts(self):
        from Code.charge_travail import verdict_ajout
        v = verdict_ajout(self._payload(), 1, 7)
        assert v["apres_min"] == 150.0
        assert v["part_apres"] == pytest.approx(0.15)
        assert v["depasse"] is False and v["deja"] is False


# ═══════════════════════════════════════════════════════════════════════════
#  periode.mois_de()
# ═══════════════════════════════════════════════════════════════════════════

class TestMoisDe:

    def test_sans_moment_rend_le_defaut(self):
        from Code.periode import mois_de
        assert mois_de(None) is None
        assert mois_de(None, "2030-01") == "2030-01"

    def test_un_moment_rend_son_mois_rembourre(self):
        from datetime import datetime
        from Code.periode import mois_de
        assert mois_de(datetime(2026, 3, 9)) == "2026-03"


# ═══════════════════════════════════════════════════════════════════════════
#  Les gardes des routes RH
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def compte_user(app):
    """Un compte `user` À SOI (aucun droit RH) et son client dédié."""
    from Code.models.models import User, WelcomeSeen
    from Code.security import hash_password
    with app.app_context():
        u = User(first_name="T172", last_name="usr", email=PREFIXE + "usr@x.com",
                 password=hash_password("Motdepasse123!"), status="user")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
    yield c, uid
    with app.app_context():
        db.session.rollback()
        WelcomeSeen.query.filter_by(user_id=uid).delete(synchronize_session=False)
        User.query.filter_by(id=uid).delete(synchronize_session=False)
        db.session.commit()


class TestRoutesRHGardes:

    @pytest.mark.parametrize("url,corps", [
        ("/gestion_rh/role_carto", {"user_id": 1, "role_id": 1, "entity_id": None}),
        ("/gestion_rh/role_cartos", {"role_id": 1, "entity_ids": []}),
        ("/gestion_rh/role_dev", {"user_id": 1, "role_id": 1, "dev_id": None}),
        ("/gestion_rh/dev_scope", {"user_id": 1, "dev_id": None, "role_ids": None}),
    ])
    def test_un_compte_sans_droit_RH_est_refuse(self, compte_user, url, corps):
        """⚠️ Le refus vient de la porte du blueprint (`_ecriture_reservee_rh`),
        AVANT la garde propre à la route : celle-ci reste en défense."""
        c, _ = compte_user
        r = c.post(url, json=corps)
        assert r.status_code == 403, r.get_data(as_text=True)[:200]
        assert r.get_json()["code"] == "lecture_seule"

    @pytest.mark.parametrize("url", ["/gestion_rh/role_carto",
                                     "/gestion_rh/role_dev"])
    def test_un_anonyme_est_renvoye_a_la_connexion(self, app, url):
        r = app.test_client().post(url, json={"user_id": 1, "role_id": 1})
        assert r.status_code == 401
        assert r.get_json()["code"] == "non_connecte"

    def test_role_carto_parametres_non_numeriques(self, auth_client):
        r = auth_client.post("/gestion_rh/role_carto",
                             json={"user_id": "abc", "role_id": None})
        assert r.status_code == 400
        assert "invalides" in r.get_json()["error"]

    def test_role_carto_carto_non_numerique(self, auth_client, ids):
        from Code.models.models import UserRole
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", (("Q", d.ent),))
            r = auth_client.post("/gestion_rh/role_carto",
                                 json={"user_id": qui.id, "role_id": d.roles["Q"].id,
                                       "entity_id": "pas-un-id"})
            assert r.status_code == 400
            assert r.get_json()["error"] == "Carto invalide"
            db.session.expire_all()
            lien = UserRole.query.filter_by(user_id=qui.id,
                                            role_id=d.roles["Q"].id).first()
            assert lien.entity_id == d.ent.id, "un refus ne déplace rien"

    def test_role_carto_chaine_null_detache(self, auth_client, ids):
        from Code.models.models import UserRole
        with _Decor(auth_client, ids) as d:
            d.role("Q")
            qui = d.personne("Un", (("Q", d.ent),))
            r = auth_client.post("/gestion_rh/role_carto",
                                 json={"user_id": qui.id, "role_id": d.roles["Q"].id,
                                       "entity_id": "null"})
            assert r.status_code == 200
            db.session.expire_all()
            assert UserRole.query.filter_by(
                user_id=qui.id, role_id=d.roles["Q"].id).first().entity_id is None


# ═══════════════════════════════════════════════════════════════════════════
#  Analyses de temps : une modification ne glisse pas de ligne sans activité
# ═══════════════════════════════════════════════════════════════════════════

class TestModificationsSansActivite:

    def test_put_projet_ligne_sans_activite_refusee(self, auth_client, ids):
        from Code.models.models import TimeProject, TimeProjectLine
        p = TimeProject(name="T172 projet", entity_id=ids["entity_id"],
                        periode="2031-08")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        try:
            r = auth_client.put("/temps/api/project/%d" % pid,
                                json={"name": "T172 renommé",
                                      "lines": [{"activity_id": ""}]})
            assert r.status_code == 400
            assert r.get_json()["code"] == "ligne_sans_activite"
            db.session.expire_all()
            assert TimeProjectLine.query.filter_by(project_id=pid).count() == 0
        finally:
            db.session.rollback()
            obj = db.session.get(TimeProject, pid)
            if obj:
                db.session.delete(obj)
                db.session.commit()

    def test_patch_analyse_de_role_ligne_sans_activite_refusee(self, auth_client, ids):
        from Code.models.models import TimeRoleLine
        with _Decor(auth_client, ids) as d:
            d.role("P")
            R = d.analyse("P", "2031-09", n=2)
            r = auth_client.patch("/temps/api/role_analysis/%d" % R.id,
                                  json={"lines": [{"activity_id": None}]})
            assert r.status_code == 400
            assert r.get_json()["code"] == "ligne_sans_activite"
            db.session.expire_all()
            assert TimeRoleLine.query.filter_by(role_analysis_id=R.id).count() == 2


# ═══════════════════════════════════════════════════════════════════════════
#  Plan de formation : les replis défensifs
# ═══════════════════════════════════════════════════════════════════════════

class TestPlanFormationReplis:

    def test_chiffre_vide_et_entier_et_decimal(self):
        from Code.routes.plan_formation import _chiffre
        assert _chiffre(None) == ""
        assert _chiffre(48.0) == "48"
        assert _chiffre(2.5) == "2.5"

    def test_jour_vide_invalide_et_les_deux_langues(self):
        from Code.routes.plan_formation import _jour
        assert _jour(None) == ""
        assert _jour("") == ""
        assert _jour("pas une date") == "pas une date"
        assert _jour("2026-11-05T10:00:00") == "05/11/2026"
        assert _jour("2026-11-05T10:00:00", en=True) == "2026-11-05"

    def test_domaines_indisponibles_rendent_une_liste_vide(self, app, monkeypatch):
        import Code.routes.technical_domains as td
        from Code.routes.plan_formation import _domaines_en_ecart

        def boum(*a, **k):
            raise RuntimeError("technicité en travaux")
        monkeypatch.setattr(td, "domaines_de_activite", boum)
        with app.test_request_context("/"):
            assert _domaines_en_ecart(1, 1, 1) == []

    def test_diagnostic_non_importable_rend_une_liste_vide(self, app, monkeypatch):
        from Code.routes.plan_formation import _capacites_en_ecart
        monkeypatch.setitem(sys.modules, "Code.routes.diagnostic", None)
        with app.test_request_context("/"):
            assert _capacites_en_ecart(1, 1, [{"data_id": 1, "name": "x"}]) == []


# ═══════════════════════════════════════════════════════════════════════════
#  Socle des activités : les refus des trois transitions, et la file d'examen
# ═══════════════════════════════════════════════════════════════════════════

class _Carto:
    """Une entité en mémoire : les transitions refusent AVANT toute écriture."""

    def __init__(self, is_shared=True, socle_etat=None):
        self.is_shared, self.socle_etat = is_shared, socle_etat


class TestSocleTransitionsRefusees:

    @pytest.mark.parametrize("nom", ["soumettre", "valider", "renvoyer"])
    def test_sans_carto_ou_carto_privee(self, nom):
        import Code.socle_activites as socle
        fn = getattr(socle, nom)
        assert fn(None, None) == (False, "pas_commune")
        assert fn(_Carto(is_shared=False), None) == (False, "pas_commune")

    def test_soumettre_une_carto_deja_soumise(self):
        from Code.socle_activites import ETAT_SOUMIS, ETAT_VALIDE, soumettre
        assert soumettre(_Carto(socle_etat=ETAT_SOUMIS), None) == (False, "deja_soumis")
        assert soumettre(_Carto(socle_etat=ETAT_VALIDE), None) == (False, "deja_soumis")

    def test_valider_une_carto_deja_validee(self):
        from Code.socle_activites import ETAT_VALIDE, valider
        assert valider(_Carto(socle_etat=ETAT_VALIDE), None) == (False, "deja_valide")

    def test_renvoyer_sans_mot_est_refuse(self):
        from Code.socle_activites import ETAT_SOUMIS, renvoyer
        c = _Carto(socle_etat=ETAT_SOUMIS)
        assert renvoyer(c, None, "   ") == (False, "sans_mot")
        assert c.socle_etat == ETAT_SOUMIS, "un refus ne change pas l'état"


class TestSocleFileDExamen:

    def test_sans_compte_la_file_est_vide(self):
        from Code.socle_activites import a_examiner
        assert a_examiner(None) == []

    def test_un_administrateur_voit_les_cartos_soumises_et_elles_seules(self, app, ids):
        from Code.models.models import Entity, User
        from Code.socle_activites import ETAT_SAISIE, ETAT_SOUMIS, a_examiner
        with app.app_context():
            soumise = Entity(name="T172 socle soumis", owner_id=ids["user_id"],
                             is_shared=True, socle_etat=ETAT_SOUMIS)
            en_saisie = Entity(name="T172 socle saisie", owner_id=ids["user_id"],
                               is_shared=True, socle_etat=ETAT_SAISIE)
            db.session.add_all([soumise, en_saisie])
            db.session.commit()
            sid, eid = soumise.id, en_saisie.id
            try:
                admin = db.session.get(User, ids["user_id"])
                with app.test_request_context("/"):
                    vus = [e.id for e in a_examiner(admin)]
                assert sid in vus
                assert eid not in vus
            finally:
                db.session.rollback()
                Entity.query.filter(Entity.id.in_([sid, eid])).delete(
                    synchronize_session=False)
                db.session.commit()

    def test_un_compte_user_n_examine_rien(self, app, compte_user):
        from Code.models.models import User
        from Code.socle_activites import a_examiner
        _, uid = compte_user
        with app.app_context(), app.test_request_context("/"):
            assert a_examiner(db.session.get(User, uid)) == []
