# -*- coding: utf-8 -*-
"""Branches défensives restées muettes après le passage à 99 %.

Chaque cas force UNE branche que la suite n'avait jamais empruntée : la table
`task_link_assignments` illisible, une date d'évaluation saisie à la française,
un compte `user` qui frappe aux routes d'affectation RH, une IA qui annonce
plus de trois résultats, un prompt système retiré du catalogue…

Données dédiées, préfixe `T169`, nettoyées en fin de test ; chaque test a son
propre client : rien ne dépend de l'ordre d'exécution.
"""
import json

import pytest
from sqlalchemy import text

from Code.extensions import db

PREFIXE = "T169"


def _client(app, uid, entity_id=None):
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
        if entity_id is not None:
            s["active_entity_id"] = entity_id
    return c


@pytest.fixture()
def decor(app):
    """Une carto à soi (admin de la suite), une activité, un rôle qui la porte,
    et un compte `user` sans droit RH."""
    from Code.models.models import Activities, Entity, Role, User, activity_roles
    from Code.security import hash_password

    with app.app_context():
        admin = User.query.filter_by(email="test@devoptiq.com").first()
        e = Entity(name=PREFIXE + " carto", owner_id=admin.id)
        db.session.add(e)
        db.session.flush()
        usr = User(first_name=PREFIXE, last_name="user", email="t169.user@x.com",
                   password=hash_password("Motdepasse123!"), status="user",
                   entity_id=e.id)
        act = Activities(entity_id=e.id, name=PREFIXE + " activité")
        role = Role(entity_id=e.id, name=PREFIXE + " rôle")
        db.session.add_all([usr, act, role])
        db.session.flush()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant"))
        db.session.commit()
        ids = dict(admin=admin.id, usr=usr.id, entity_id=e.id,
                   activity_id=act.id, role_id=role.id)

    yield ids

    with app.app_context():
        from Code.models.models import (CompetencyEvaluation, Data, Link,
                                        UserRole, WelcomeSeen)
        db.session.rollback()
        CompetencyEvaluation.query.filter(
            CompetencyEvaluation.activity_id == ids["activity_id"]).delete(
            synchronize_session=False)
        Link.query.filter(Link.entity_id == ids["entity_id"]).delete(
            synchronize_session=False)
        Data.query.filter(Data.entity_id == ids["entity_id"]).delete(
            synchronize_session=False)
        UserRole.query.filter(UserRole.user_id == ids["usr"]).delete(
            synchronize_session=False)
        WelcomeSeen.query.filter(WelcomeSeen.user_id == ids["usr"]).delete(
            synchronize_session=False)
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.role_id == ids["role_id"]))
        Role.query.filter(Role.id == ids["role_id"]).delete(synchronize_session=False)
        Activities.query.filter(Activities.id == ids["activity_id"]).delete(
            synchronize_session=False)
        User.query.filter(User.id == ids["usr"]).delete(synchronize_session=False)
        Entity.query.filter(Entity.id == ids["entity_id"]).delete(
            synchronize_session=False)
        db.session.commit()


def _execute_qui_bute_sur_tla(monkeypatch):
    """`db.session.execute` lève dès que la requête lit `task_link_assignments`."""
    vrai = db.session.execute

    def faux(stmt, *a, **k):
        if "task_link_assignments" in str(stmt) and "SELECT" in str(stmt).upper():
            raise RuntimeError("table illisible")
        return vrai(stmt, *a, **k)

    monkeypatch.setattr(db.session, "execute", faux)


# ── Table des connexions tâche ↔ flèche illisible ────────────────────────

class TestConnexionsTachesIllisibles:

    def test_rendu_des_taches_survit_a_une_table_tla_illisible(self, app, decor, monkeypatch):
        _execute_qui_bute_sur_tla(monkeypatch)
        c = _client(app, decor["admin"], decor["entity_id"])
        r = c.get("/tasks/%d/render" % decor["activity_id"])
        assert r.status_code == 200

    def test_fiche_activite_survit_a_ensure_table_qui_leve(self, app, decor, monkeypatch):
        import Code.routes.task_link_assignments as tla

        def boum():
            raise RuntimeError("DDL refusé")

        monkeypatch.setattr(tla, "ensure_table", boum)
        c = _client(app, decor["admin"], decor["entity_id"])
        r = c.get("/activities/view?activity_id=%d" % decor["activity_id"])
        assert r.status_code == 200
        assert (PREFIXE + " activité").encode() in r.data

    def test_fiche_activite_survit_a_une_lecture_tla_qui_leve(self, app, decor, monkeypatch):
        _execute_qui_bute_sur_tla(monkeypatch)
        c = _client(app, decor["admin"], decor["entity_id"])
        r = c.get("/activities/view?activity_id=%d" % decor["activity_id"])
        assert r.status_code == 200


# ── Dates d'évaluation en texte libre ────────────────────────────────────

def _evaluation(app, decor, created_at):
    from Code.models.models import CompetencyEvaluation
    with app.app_context():
        db.session.add(CompetencyEvaluation(
            user_id=decor["admin"], activity_id=decor["activity_id"],
            item_id=None, item_type="activities", eval_number="1",
            note="green", created_at=created_at))
        db.session.commit()


class TestDatesEvaluationTexte:

    def test_date_illisible_rendue_telle_quelle(self, app, decor):
        _evaluation(app, decor, "pas une date")
        c = _client(app, decor["admin"], decor["entity_id"])
        r = c.get("/competences/get_user_evaluations_by_user/%d" % decor["admin"])
        assert r.status_code == 200
        lignes = [e for e in r.get_json() if e["activity_id"] == decor["activity_id"]]
        assert [e["created_at"] for e in lignes] == ["pas une date"]

    def test_date_francaise_convertie_en_iso(self, app, decor):
        _evaluation(app, decor, "25/11/2026")
        c = _client(app, decor["admin"], decor["entity_id"])
        r = c.get("/competences/get_user_evaluations_by_user/%d" % decor["admin"])
        lignes = [e for e in r.get_json() if e["activity_id"] == decor["activity_id"]]
        assert lignes[0]["created_at"] == "2026-11-25T00:00:00"

    def test_synthese_plate_tolere_une_date_vide(self, app, decor):
        from Code.models.models import UserRole
        with app.app_context():
            db.session.add(UserRole(user_id=decor["admin"], role_id=decor["role_id"]))
            db.session.commit()
        try:
            _evaluation(app, decor, "")
            c = _client(app, decor["admin"], decor["entity_id"])
            r = c.get("/competences/global_flat_summary/%d" % decor["admin"])
            assert r.status_code == 200
            assert (PREFIXE + " activité").encode() in r.data
        finally:
            with app.app_context():
                UserRole.query.filter_by(user_id=decor["admin"],
                                         role_id=decor["role_id"]).delete()
                db.session.commit()


# ── Affectations RH : un compte `user` est refusé ────────────────────────

class TestAffectationsRhRefusees:

    @pytest.mark.parametrize("chemin", ["/gestion_rh/role_cartos",
                                        "/gestion_rh/role_dev",
                                        "/gestion_rh/dev_scope"])
    def test_user_sans_droit_rh_recoit_403(self, app, decor, chemin):
        c = _client(app, decor["usr"], decor["entity_id"])
        r = c.post(chemin, json={"role_id": decor["role_id"], "user_id": decor["usr"]})
        assert r.status_code == 403


# ── Sorties : doublons de libellé, trop de résultats ─────────────────────

def _deux_fleches_meme_libelle(app, decor):
    from Code.models.models import Activities, Link
    with app.app_context():
        cible = Activities(entity_id=decor["entity_id"], name=PREFIXE + " aval")
        db.session.add(cible)
        db.session.flush()
        for _ in range(2):
            db.session.add(Link(entity_id=decor["entity_id"],
                                source_activity_id=decor["activity_id"],
                                target_activity_id=cible.id,
                                description="Pièce T169", type="sortante"))
        db.session.commit()
        return cible.id


def _supprimer_activite(app, aid):
    from Code.models.models import Activities, Link
    with app.app_context():
        Link.query.filter(Link.target_activity_id == aid).delete(synchronize_session=False)
        Activities.query.filter(Activities.id == aid).delete(synchronize_session=False)
        db.session.commit()


class TestSortiesQualifiees:

    def test_deux_fleches_au_meme_libelle_font_une_seule_sortie(self, app, decor):
        from Code.models.models import Activities
        from Code.routes.qualify_outputs import _current_output_specs
        aval = _deux_fleches_meme_libelle(app, decor)
        try:
            with app.app_context():
                specs = _current_output_specs(db.session.get(Activities, decor["activity_id"]))
            assert [s[0] for s in specs] == ["Pièce T169"]
        finally:
            _supprimer_activite(app, aval)

    def test_lecture_en_bloc_deduplique_aussi(self, app, decor):
        from Code.models.models import Data
        from Code.routes.qualify_outputs import output_ids_en_bloc
        aval = _deux_fleches_meme_libelle(app, decor)
        try:
            with app.app_context():
                d = Data(entity_id=decor["entity_id"], name="Pièce T169", type="sortante",
                         producer_activity_id=decor["activity_id"])
                db.session.add(d)
                db.session.commit()
                res = output_ids_en_bloc([decor["activity_id"]])
                assert res[decor["activity_id"]] == {d.id}
        finally:
            _supprimer_activite(app, aval)

    def test_plus_de_trois_resultats_avertit_sur_la_granularite(self, app, decor, monkeypatch):
        from Code.models.models import Data, Link
        with app.app_context():
            dids = []
            for i in range(4):
                d = Data(entity_id=decor["entity_id"], name="%s sortie %d" % (PREFIXE, i),
                         type="sortante")
                db.session.add(d)
                db.session.flush()
                db.session.add(Link(entity_id=decor["entity_id"],
                                    source_activity_id=decor["activity_id"],
                                    target_data_id=d.id, type="sortante"))
                dids.append(d.id)
            db.session.commit()
        contenu = json.dumps({"outputs": [
            {"data_id": did, "suggested_nature": "RESULT"} for did in dids]})

        class _Msg:
            content = contenu

        class _Choice:
            message = _Msg()

        class _Rep:
            choices = [_Choice()]

        class _Compl:
            def create(self, **k):
                return _Rep()

        class _Chat:
            completions = _Compl()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr("Code.routes.qualify_outputs.openai_client_or_none",
                            lambda: (_Client(), None))
        monkeypatch.setattr("Code.routes.qualify_outputs.get_prompt",
                            lambda *a, **k: "système")
        c = _client(app, decor["admin"], decor["entity_id"])
        with c.session_transaction() as s:
            s["lang"] = "fr"
        r = c.post("/qualify/analyze/%d" % decor["activity_id"])
        assert r.status_code == 200
        corps = r.get_json()
        assert corps["source"] == "AI"
        assert "granularité" in corps["warning"]


# ── Aptitudes : prompt SYSTÈME retiré du catalogue ───────────────────────

class TestPromptSystemeAbsent:

    @pytest.fixture()
    def ia(self, monkeypatch):
        appels = []

        class _Compl:
            def create(self, **k):
                appels.append(k)
                raise AssertionError("l'IA ne doit pas être appelée")

        class _Chat:
            completions = _Compl()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr("Code.routes.propose_aptitudes.openai_client_or_none",
                            lambda: (_Client(), None))
        monkeypatch.setattr("Code.routes.propose_aptitudes.get_prompt",
                            lambda cle, **k: None if ".system." in cle else "prompt")
        return appels

    def test_propose_sans_prompt_systeme(self, app, ia):
        r = app.test_client().post("/propose_aptitudes/propose", json={"name": "A"})
        assert r.get_json() == {"proposals": {}, "source": "prompts-unavailable"}
        assert ia == []

    def test_feasibility_sans_prompt_systeme(self, app, ia):
        r = app.test_client().post("/propose_aptitudes/feasibility",
                                   json={"activity_name": "A"})
        assert r.get_json() == {"result": {}, "source": "prompts-unavailable"}
        assert ia == []


# ── Fenêtre de bienvenue : base qui refuse même l'annulation ─────────────

class TestBienvenueBaseRetive:

    @pytest.fixture()
    def base_retive(self, monkeypatch):
        def boum(*a, **k):
            raise RuntimeError("base indisponible")
        monkeypatch.setattr(db.session, "get", boum)
        monkeypatch.setattr(db.session, "rollback", boum)

    def test_signature_vue_rend_none(self, app, decor, base_retive):
        from Code.bienvenue import signature_vue
        from Code.models.models import User
        with app.app_context():
            u = User.query.get(decor["usr"])
            assert signature_vue(u) is None

    def test_marquer_vue_rend_false(self, app, decor, base_retive):
        from Code.bienvenue import marquer_vue
        from Code.models.models import User
        with app.app_context():
            u = User.query.get(decor["usr"])
            assert marquer_vue(u, signature="x") is False


# ── Aperçu des compétences : entrées dégénérées ──────────────────────────

class TestApercuEntreesDegenerees:

    def test_suivis_sans_acteur_ne_suit_personne(self, app):
        from Code.apercu_competences import _suivis_en_bloc
        with app.app_context():
            assert _suivis_en_bloc(None, [1, 2]) == {1: [], 2: []}

    def test_suivis_pour_un_admin_sans_restriction(self, app):
        from Code.apercu_competences import _suivis_en_bloc
        from Code.models.models import User
        with app.app_context():
            admin = User.query.filter_by(email="test@devoptiq.com").first()
            assert _suivis_en_bloc(admin, [7, 8]) == {7: None, 8: None}

    def test_activite_absente_et_donnee_absente_ignorees(self, app, decor):
        from Code.apercu_competences import _activites_du
        from Code.models.models import Activities
        with app.test_request_context():
            act = db.session.get(Activities, decor["activity_id"])
            lignes = _activites_du(
                decor["admin"], [999999, act.id], [decor["role_id"]], {},
                {act.id: act}, {act.id: {888888}}, {}, {}, {})
        assert [l["activity_id"] for l in lignes] == [decor["activity_id"]]
        assert lignes[0]["n_results"] == 0


# ── Petits helpers purs ──────────────────────────────────────────────────

class TestHelpersPurs:

    def test_reecrire_refs_laisse_un_corps_non_dict(self):
        from Code.propositions_activite import _reecrire_refs
        assert _reecrire_refs(["b:0"], lambda r: r + 1) == ["b:0"]

    def test_simuler_sans_brouillon_mesure_directement(self):
        from Code.propositions_activite import simuler
        assert simuler(None, lambda: 42) == 42

    def test_id_cree_sur_reponse_non_dict(self, app):
        from flask import jsonify
        from Code.propositions_activite import _id_cree
        with app.test_request_context():
            assert _id_cree(jsonify([1, 2])) is None
            assert _id_cree((jsonify({"id": 5}), 201)) == 5

    def test_capacites_sans_module_diagnostic(self, monkeypatch):
        import sys
        from Code.routes.plan_formation import _capacites_en_ecart
        monkeypatch.setitem(sys.modules, "Code.routes.diagnostic", None)
        assert _capacites_en_ecart(1, 1, [{"data_id": 1}]) == []

    def test_dashboard_sans_domaines_de_technicite(self, app, decor, monkeypatch):
        import Code.routes.technical_domains as td
        from Code.routes.mastery import dashboard_rows

        def boum(*a, **k):
            raise RuntimeError("domaines indisponibles")

        monkeypatch.setattr(td, "domain_status", boum)
        with app.test_request_context():
            from flask import session
            session["user_id"] = decor["admin"]
            rows = dashboard_rows(decor["admin"], decor["role_id"])
        assert [r["activity_id"] for r in rows] == [decor["activity_id"]]
        assert rows[0]["technicity"] == "none"
        assert rows[0]["technicity_alert"] is False
