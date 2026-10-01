# -*- coding: utf-8 -*-
"""Plan de formation — routes /plan/* et construction du contenu (IA / repli).

`test_77` couvre le parcours nominal (lecture, proposition locale, enregistrement,
droits du collaborateur). Ici : ce qui reste — suppression, charges invalides,
rôle ou utilisateur inconnu, accès anonyme, lecture IA simulée (bornes, repli),
et les fonctions pures `_critere` / `_plan_local`.

Données dédiées (suffixe 93) et nettoyées en fin de module.
"""
import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.mastery


@pytest.fixture(scope="module")
def scene(app):
    from Code.extensions import db
    from Code.models.models import (Activities, Data, Entity, Role, User, UserRole,
                                    activity_roles)
    from Code.security import hash_password

    with app.app_context():
        entity = Entity.query.filter_by(name="Entité Test").first()
        cible = User(first_name="Cible", last_name="Test93", email="cible93@devoptiq.com",
                     password=hash_password("TestPass123!"), status="user")
        db.session.add(cible)
        role = Role(name="Rôle Test 93", entity_id=entity.id)
        act = Activities(entity_id=entity.id, name="Activité Test 93")
        db.session.add_all([role, act])
        db.session.commit()
        db.session.add(UserRole(user_id=cible.id, role_id=role.id))
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant", required_mastery_level=3))
        d1 = Data(entity_id=entity.id, name="Résultat 93", type="flux",
                  producer_activity_id=act.id, semantic_nature="RESULT",
                  minimum_performance_text="Standard 93")
        db.session.add(d1)
        db.session.commit()
        cree = {"entity": entity.id, "cible": cible.id, "role": role.id,
                "act": act.id, "d1": d1.id}

    yield cree

    with app.app_context():
        from Code.models.models import CompetencyEvaluation, PlanFormation
        CompetencyEvaluation.query.filter_by(activity_id=cree["act"]).delete()
        PlanFormation.query.filter_by(role_id=cree["role"]).delete()
        UserRole.query.filter_by(role_id=cree["role"]).delete()
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id == cree["act"]))
        Data.query.filter_by(producer_activity_id=cree["act"]).delete()
        for modele, ident in ((Activities, cree["act"]), (Role, cree["role"]),
                              (User, cree["cible"])):
            obj = db.session.get(modele, ident)
            if obj:
                db.session.delete(obj)
        db.session.commit()


def _post(c, url, payload):
    return c.post(url, data=json.dumps(payload), content_type="application/json")


def _met_en_ecart(c, scene, niveau=2):
    r = _post(c, "/mastery/evaluate", {
        "user_id": scene["cible"], "activity_id": scene["act"], "data_id": scene["d1"],
        "evaluator": "2", "mastery_level": niveau, "role_id": scene["role"],
        "evidence": ""})
    assert r.status_code == 200, r.data


def _ia_simulee(monkeypatch, contenu):
    """Remplace le client IA par un faux qui renvoie `contenu` (str ou exception)."""
    from Code.routes import plan_formation as pf

    def create(**kw):
        if isinstance(contenu, Exception):
            raise contenu
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=contenu))])

    faux = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(pf, "openai_client_or_none", lambda: (faux, None))
    monkeypatch.setattr(pf, "get_prompt", lambda k: "système")


ACTIVITES = [{"activity_id": 1, "activity_name": "Chiffrer", "competence": "C",
              "demonstrated_label": "Initié", "required_label": "Maîtrise", "gap": -2,
              "results_in_gap": [{"name": "Devis", "minimum_performance_text": "Marge < 3 %"},
                                 {"name": "Sans standard", "minimum_performance_text": ""}],
              "capabilities": [{"item_type": "SAVOIR", "label": "Calcul de marge",
                                "type_label": "Savoir", "gap": -1, "resultat": "Devis"}]}]


class TestFonctionsPures:

    def test_critere_formate_en_francais(self):
        from Code.routes.plan_formation import _critere
        assert _critere("Devis", "Marge < 3 %") == "« Devis » : Marge < 3 %"

    def test_critere_formate_en_anglais(self):
        from Code.routes.plan_formation import _critere
        assert _critere("Quote", "Margin < 3%", en=True) == "“Quote”: Margin < 3%"

    def test_critere_sans_resultat_rend_le_standard_seul(self):
        from Code.routes.plan_formation import _critere
        assert _critere("", "Standard") == "Standard"

    def test_critere_sans_standard_rend_vide(self):
        from Code.routes.plan_formation import _critere
        assert _critere("Devis", None) == ""

    def test_plan_local_une_action_par_capacite_plus_une_mise_en_situation(self):
        from Code.routes.plan_formation import _plan_local
        actions = _plan_local(ACTIVITES, "fr")
        assert [a["type"] for a in actions] == ["FORMATION", "TERRAIN"]
        assert actions[0]["titre"] == "Se former : Calcul de marge"
        assert actions[0]["heures"] == 7          # 7 h × un pas de niveau (gap capacité -1)
        assert actions[1]["heures"] == 24         # 12 h × 2 pas (gap activité -2)

    def test_plan_local_livrable_et_critere_portes_par_la_mise_en_situation(self):
        from Code.routes.plan_formation import _plan_local
        terrain = _plan_local(ACTIVITES, "fr")[-1]
        assert terrain["livrable"] == "Devis, Sans standard"
        assert terrain["critere"] == "« Devis » : Marge < 3 %"   # pas de ligne sans standard

    def test_plan_local_en_anglais(self):
        from Code.routes.plan_formation import _plan_local
        actions = _plan_local(ACTIVITES, "en")
        assert actions[0]["titre"] == "Learn: Calcul de marge"
        assert actions[1]["titre"] == "Perform “Chiffrer” in real conditions"

    def test_plan_local_sans_activite_est_vide(self):
        from Code.routes.plan_formation import _plan_local
        assert _plan_local([], "fr") == []


class TestAccesEtValidation:

    def test_lecture_sans_session_est_403(self, client, scene):
        with client.session_transaction() as sess:
            sess.clear()
        assert client.get(f"/plan/{scene['cible']}/{scene['role']}").status_code == 403

    def test_proposer_sans_session_est_403(self, client, scene):
        with client.session_transaction() as sess:
            sess.clear()
        r = _post(client, "/plan/proposer", {"user_id": scene["cible"], "role_id": scene["role"]})
        assert r.status_code == 403
        assert r.get_json()["reason"] == "not_logged_in"

    def test_enregistrer_sans_session_est_403(self, client, scene):
        with client.session_transaction() as sess:
            sess.clear()
        r = _post(client, "/plan/enregistrer",
                  {"user_id": scene["cible"], "role_id": scene["role"], "actions": []})
        assert r.status_code == 403

    def test_supprimer_sans_session_est_403(self, client, scene):
        with client.session_transaction() as sess:
            sess.clear()
        r = client.delete(f"/plan/{scene['cible']}/{scene['role']}")
        assert r.status_code == 403

    def test_lecture_role_inexistant_404(self, auth_client, scene):
        r = auth_client.get(f"/plan/{scene['cible']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "role_not_found"

    def test_lecture_sans_plan_rend_les_parametres_par_defaut(self, auth_client, scene):
        d = auth_client.get(f"/plan/{scene['cible']}/{scene['role']}").get_json()
        assert d["actions"] == []
        assert d["source"] is None and d["updated_at"] is None
        assert d["parametres"] == {"heures_semaine": 4, "semaines": 12}
        assert set(d["types"]) == {"TERRAIN", "ACCOMPAGNEMENT", "FORMATION"}

    def test_proposer_sans_role_est_400(self, auth_client, scene):
        r = _post(auth_client, "/plan/proposer", {"user_id": scene["cible"]})
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_enregistrer_sans_utilisateur_est_400(self, auth_client, scene):
        r = _post(auth_client, "/plan/enregistrer", {"role_id": scene["role"]})
        assert r.status_code == 400

    def test_enregistrer_role_inexistant_est_404(self, auth_client, scene):
        r = _post(auth_client, "/plan/enregistrer",
                  {"user_id": scene["cible"], "role_id": 999999, "actions": []})
        assert r.status_code == 404
        assert r.get_json()["error"] == "not_found"

    def test_proposer_sans_ecart_rend_no_gap(self, auth_client, scene):
        r = _post(auth_client, "/plan/proposer",
                  {"user_id": scene["cible"], "role_id": scene["role"]})
        assert r.status_code == 200
        assert r.get_json() == {"actions": [], "source": "no_gap", "activites": []}


class TestEnregistrementEtSuppression:

    def test_la_source_est_tronquee_a_10_caracteres(self, auth_client, scene):
        r = _post(auth_client, "/plan/enregistrer", {
            "user_id": scene["cible"], "role_id": scene["role"], "actions": [],
            "source": "UNE_SOURCE_BEAUCOUP_TROP_LONGUE"})
        assert r.status_code == 200
        assert r.get_json()["source"] == "UNE_SOURCE"
        client_delete = auth_client.delete(f"/plan/{scene['cible']}/{scene['role']}")
        assert client_delete.status_code == 200

    def test_source_par_defaut_est_LOCAL_et_auteur_renseigne(self, auth_client, app, scene, ids):
        from Code.models.models import PlanFormation
        _post(auth_client, "/plan/enregistrer",
              {"user_id": scene["cible"], "role_id": scene["role"], "actions": []})
        with app.app_context():
            plan = PlanFormation.query.filter_by(
                user_id=scene["cible"], role_id=scene["role"]).first()
            assert plan.source == "LOCAL"
            assert plan.auteur_id == ids["user_id"]
            assert plan.updated_at is not None
        auth_client.delete(f"/plan/{scene['cible']}/{scene['role']}")

    def test_enregistrer_conserve_les_accents(self, auth_client, app, scene):
        from Code.models.models import PlanFormation
        _post(auth_client, "/plan/enregistrer", {
            "user_id": scene["cible"], "role_id": scene["role"],
            "actions": [{"id": "A1", "titre": "Reprendre un chiffrage été", "heures": 3}]})
        with app.app_context():
            plan = PlanFormation.query.filter_by(
                user_id=scene["cible"], role_id=scene["role"]).first()
            assert "été" in plan.actions        # pas de é : ensure_ascii=False
        auth_client.delete(f"/plan/{scene['cible']}/{scene['role']}")

    def test_supprimer_efface_le_plan(self, auth_client, app, scene):
        from Code.models.models import PlanFormation
        _post(auth_client, "/plan/enregistrer",
              {"user_id": scene["cible"], "role_id": scene["role"], "actions": []})
        r = auth_client.delete(f"/plan/{scene['cible']}/{scene['role']}")
        assert r.status_code == 200 and r.get_json() == {"ok": True}
        with app.app_context():
            assert PlanFormation.query.filter_by(
                user_id=scene["cible"], role_id=scene["role"]).count() == 0
        d = auth_client.get(f"/plan/{scene['cible']}/{scene['role']}").get_json()
        assert d["actions"] == [] and d["source"] is None

    def test_supprimer_un_plan_absent_reste_ok(self, auth_client, scene):
        r = auth_client.delete(f"/plan/{scene['cible']}/{scene['role']}")
        assert r.status_code == 200 and r.get_json() == {"ok": True}


class TestPropositionIA:

    def test_ia_valide_les_actions_sont_bornees_et_typees(self, auth_client, scene, monkeypatch):
        _met_en_ecart(auth_client, scene)
        _ia_simulee(monkeypatch, json.dumps({"actions": [
            {"titre": " Binôme ", "type": "TERRAIN", "activite": "Activité Test 93",
             "heures": 500, "objectif": "o", "livrable": "l", "critere": "c"},
            {"titre": "Cours", "type": "INCONNU", "activite": "Autre", "heures": "abc"},
            {"titre": "", "type": "TERRAIN", "heures": 5},
        ]}))
        r = _post(auth_client, "/plan/proposer",
                  {"user_id": scene["cible"], "role_id": scene["role"]})
        d = r.get_json()
        assert d["source"] == "AI"
        a1, a2 = d["actions"]                       # l'action sans titre est écartée
        assert (a1["id"], a1["titre"], a1["heures"], a1["activity_id"]) == \
            ("A1", "Binôme", 200, scene["act"])     # plafonnée à 200 h
        assert a2["type"] == "FORMATION"            # type inconnu → FORMATION
        assert a2["heures"] == 1                    # charge illisible → bornée à 1
        assert a2["activity_id"] is None

    def test_ia_sans_action_retombe_sur_le_plan_local(self, auth_client, scene, monkeypatch):
        _met_en_ecart(auth_client, scene)
        _ia_simulee(monkeypatch, json.dumps({"actions": []}))
        d = _post(auth_client, "/plan/proposer",
                  {"user_id": scene["cible"], "role_id": scene["role"]}).get_json()
        assert d["source"] == "empty"
        assert d["actions"] and d["actions"][0]["id"].startswith("L")

    def test_ia_en_erreur_retombe_sur_le_plan_local(self, auth_client, scene, monkeypatch):
        _met_en_ecart(auth_client, scene)
        _ia_simulee(monkeypatch, RuntimeError("réseau"))
        d = _post(auth_client, "/plan/proposer",
                  {"user_id": scene["cible"], "role_id": scene["role"]}).get_json()
        assert d["source"] == "error"
        assert any(a["type"] == "TERRAIN" for a in d["actions"])

    def test_ia_json_invalide_retombe_sur_le_plan_local(self, auth_client, scene, monkeypatch):
        _met_en_ecart(auth_client, scene)
        _ia_simulee(monkeypatch, "pas du json")
        d = _post(auth_client, "/plan/proposer",
                  {"user_id": scene["cible"], "role_id": scene["role"]}).get_json()
        assert d["source"] == "error"

    def test_proposer_ne_persiste_rien(self, auth_client, app, scene):
        from Code.models.models import PlanFormation
        _met_en_ecart(auth_client, scene)
        _post(auth_client, "/plan/proposer",
              {"user_id": scene["cible"], "role_id": scene["role"]})
        with app.app_context():
            assert PlanFormation.query.filter_by(
                user_id=scene["cible"], role_id=scene["role"]).count() == 0
