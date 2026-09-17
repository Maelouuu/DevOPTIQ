# -*- coding: utf-8 -*-
"""Page Compétences — deux notes, synthèse tous rôles, plan de formation.

Trois sujets, un seul fichier parce qu'ils ne se comprennent qu'ensemble :

- **Qui note qui.** `POST /mastery/evaluate` n'avait AUCUN contrôle : tout compte
  connecté pouvait poser n'importe quel niveau sur n'importe qui, y compris se
  décerner le niveau qui fait foi. Sans conséquence tant que seuls les
  développeurs de compétences ouvraient l'écran ; plus du tout dès que les
  collaborateurs y viennent s'auto-évaluer.
- **Ce qui fait foi.** Le niveau validé par le développeur est le résultat ;
  l'auto-évaluation est un repère (CDC 3.6). La synthèse ne doit jamais faire
  remonter la seconde à la place du premier.
- **Le plan de formation.** Le besoin vient de l'écart réel relevé en base ; sans
  clé IA il se construit quand même, à partir des capacités en écart.
"""
import json

import pytest

pytestmark = pytest.mark.mastery

MDP = "TestPass123!"


# ── Décor : un développeur, deux collaborateurs, un rôle, une activité ───────
@pytest.fixture(scope="module")
def scene(app, client):
    from Code.extensions import db
    from Code.models.models import (Activities, CompetencyEvaluation, Data, Entity,
                                    Role, User, UserRole, activity_roles)
    from Code.security import hash_password

    cree = {}
    with app.app_context():
        entity = Entity.query.filter_by(name="Entité Test").first()
        _ENTITE_TEST["id"] = entity.id
        dev = User(first_name="Dev", last_name="Test77", email="dev77@devoptiq.com",
                   password=hash_password(MDP), status="user")
        collab = User(first_name="Collab", last_name="Test77", email="collab77@devoptiq.com",
                      password=hash_password(MDP), status="user")
        tiers = User(first_name="Tiers", last_name="Test77", email="tiers77@devoptiq.com",
                     password=hash_password(MDP), status="user")
        db.session.add_all([dev, collab, tiers])
        db.session.commit()
        collab.manager_id = dev.id
        role = Role(name="Rôle Test 77", entity_id=entity.id)
        db.session.add(role)
        db.session.commit()
        db.session.add(UserRole(user_id=collab.id, role_id=role.id, manager_id=dev.id))

        act = Activities(entity_id=entity.id, name="Activité Test 77")
        db.session.add(act)
        db.session.commit()
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="Garant", required_mastery_level=3))
        d1 = Data(entity_id=entity.id, name="Résultat A 77", type="flux",
                  producer_activity_id=act.id, semantic_nature="RESULT",
                  minimum_performance_text="Standard A")
        d2 = Data(entity_id=entity.id, name="Résultat B 77", type="flux",
                  producer_activity_id=act.id, semantic_nature="RESULT",
                  minimum_performance_text="Standard B")
        db.session.add_all([d1, d2])
        db.session.commit()
        admin = User.query.filter_by(email="test@devoptiq.com").first()
        cree = {"entity": entity.id, "dev": dev.id, "collab": collab.id,
                "tiers": tiers.id, "role": role.id, "act": act.id,
                "d1": d1.id, "d2": d2.id, "admin": admin.id}

    yield cree

    # ⚠️ `auth_client` et `client` sont le MÊME objet, en portée session : ce
    # fichier remet la session à zéro à chaque test, ce qui déconnecterait tous
    # les tests suivants qui comptent sur `auth_client`. On la lui rend.
    with app.app_context():
        entity = Entity.query.filter_by(name="Entité Test").first()
        admin = User.query.filter_by(email="test@devoptiq.com").first()
        admin_id, admin_mail, ent_id = admin.id, admin.email, entity.id
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = admin_id
        sess["user_email"] = admin_mail
        sess["active_entity_id"] = ent_id

    with app.app_context():
        from Code.models.models import PlanFormation
        CompetencyEvaluation.query.filter_by(activity_id=cree["act"]).delete()
        PlanFormation.query.filter_by(role_id=cree["role"]).delete()
        UserRole.query.filter_by(role_id=cree["role"]).delete()
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.activity_id == cree["act"]))
        Data.query.filter_by(producer_activity_id=cree["act"]).delete()
        for modele, ident in ((Activities, cree["act"]), (Role, cree["role"])):
            obj = db.session.get(modele, ident)
            if obj:
                db.session.delete(obj)
        for uid in (cree["dev"], cree["collab"], cree["tiers"]):
            u = db.session.get(User, uid)
            if u:
                u.manager_id = None
                db.session.delete(u)
        db.session.commit()


# Rempli par la fixture `scene` : la carto sur laquelle ce fichier travaille.
_ENTITE_TEST = {"id": None}


def _connecte(client, user_id, email, entity_id=None):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user_id
        sess["user_email"] = email
        sess["lang"] = "fr"
        # ⚠️ Sans carto ACTIVE, `Entity.get_active` retombe sur « la
        # première entité du compte » — donc sur ce qu'un AUTRE fichier de
        # tests a créé entre-temps, la base étant partagée. La synthèse étant
        # cadrée par la carto active, les résultats devenaient dépendants de
        # l'ORDRE : verts seuls, rouges dans la suite complète.
        eid = entity_id if entity_id is not None else _ENTITE_TEST["id"]
        if eid:
            sess["active_entity_id"] = eid


def _note(client, user_id, activity_id, data_id, evaluateur, niveau, role_id=None, preuve=""):
    return client.post("/mastery/evaluate", data=json.dumps({
        "user_id": user_id, "activity_id": activity_id, "data_id": data_id,
        "evaluator": evaluateur, "mastery_level": niveau, "role_id": role_id,
        "evidence": preuve}), content_type="application/json")


# ═══════════════════════════════════════════════════════════════════════════
class TestQuiNoteQui:
    """⚠️ Aucun de ces refus n'existait : la route acceptait tout."""

    def test_le_collaborateur_pose_sa_propre_auto_evaluation(self, client, scene):
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        r = _note(client, scene["collab"], scene["act"], scene["d1"], "0", 2, scene["role"])
        assert r.status_code == 200

    def test_il_ne_peut_pas_se_decerner_le_niveau_qui_fait_foi(self, client, scene):
        """Le cas qui compte : sans contrôle, chacun se déclarait expert."""
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        r = _note(client, scene["collab"], scene["act"], scene["d1"], "2", 4, scene["role"])
        assert r.status_code == 403
        assert r.get_json()["reason"] == "not_the_developer"

    def test_il_ne_peut_pas_s_auto_evaluer_a_la_place_d_un_autre(self, client, scene):
        """Une auto-évaluation dit ce que CETTE personne pense d'elle-même :
        la poser pour quelqu'un d'autre n'a pas de sens."""
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        r = _note(client, scene["tiers"], scene["act"], scene["d1"], "0", 4, scene["role"])
        assert r.status_code == 403
        assert r.get_json()["reason"] == "self_only"

    def test_le_developpeur_pose_le_niveau_de_son_collaborateur(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = _note(client, scene["collab"], scene["act"], scene["d1"], "2", 3, scene["role"])
        assert r.status_code == 200

    def test_il_ne_note_pas_quelqu_un_qu_il_n_encadre_pas(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = _note(client, scene["tiers"], scene["act"], scene["d1"], "2", 3, scene["role"])
        assert r.status_code == 403

    def test_l_admin_note_tout_le_monde(self, client, scene):
        """Champion et administrateur arbitrent partout : sinon ils ne
        pourraient pas reprendre un dossier laissé en plan.

        ⚠️ On ouvre la session de l'admin nous-mêmes plutôt que de prendre
        `auth_client` : c'est le MÊME objet client, dont ce fichier remet la
        session à zéro à chaque test. S'appuyer dessus ici, c'est dépendre de
        l'ordre d'exécution."""
        _connecte(client, scene["admin"], "test@devoptiq.com")
        r = _note(client, scene["tiers"], scene["act"], scene["d1"], "2", 2, scene["role"])
        assert r.status_code == 200

    def test_le_rattachement_PAR_ROLE_ouvre_le_meme_droit(self, client, app, scene):
        """Deux rattachements coexistent — global et par rôle. Faire dépendre le
        droit de l'un des deux ferait dépendre le droit de la FAÇON dont
        l'affectation a été faite."""
        from Code.extensions import db
        from Code.models.models import Role, UserRole

        with app.app_context():
            r2 = Role(name="Rôle Test 77 bis", entity_id=scene["entity"])
            db.session.add(r2)
            db.session.commit()
            db.session.add(UserRole(user_id=scene["tiers"], role_id=r2.id, manager_id=scene["dev"]))
            db.session.commit()
            r2_id = r2.id
        try:
            _connecte(client, scene["dev"], "dev77@devoptiq.com")
            rep = _note(client, scene["tiers"], scene["act"], scene["d1"], "2", 2, scene["role"])
            assert rep.status_code == 200
        finally:
            with app.app_context():
                UserRole.query.filter_by(role_id=r2_id).delete()
                obj = db.session.get(Role, r2_id)
                if obj:
                    db.session.delete(obj)
                db.session.commit()


# ═══════════════════════════════════════════════════════════════════════════
class TestCeQuiFaitFoi:

    def test_l_auto_evaluation_ne_remonte_jamais_comme_resultat(self, client, app, scene):
        """Le collaborateur se donne 4, son développeur 2 : le niveau de
        l'activité est 2. L'auto-évaluation reste lisible à côté."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        for did in (scene["d1"], scene["d2"]):
            _note(client, scene["collab"], scene["act"], did, "0", 4, scene["role"])
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        for did in (scene["d1"], scene["d2"]):
            _note(client, scene["collab"], scene["act"], did, "2", 2, scene["role"])

        st = client.get(f"/mastery/activity/{scene['collab']}/{scene['act']}"
                        f"?role_id={scene['role']}").get_json()
        assert st["global_level"] == 2
        assert st["self_global_level"] == 4
        assert st["results"][0]["self_level"] == 4
        assert st["results"][0]["demonstrated_level"] == 2

    def test_le_minimum_vaut_aussi_pour_l_auto_evaluation(self, client, app, scene):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        _note(client, scene["collab"], scene["act"], scene["d1"], "0", 4, scene["role"])
        _note(client, scene["collab"], scene["act"], scene["d2"], "0", 1, scene["role"])
        st = client.get(f"/mastery/activity/{scene['collab']}/{scene['act']}"
                        f"?role_id={scene['role']}").get_json()
        assert st["self_global_level"] == 1          # le minimum, jamais la moyenne

    def test_une_auto_evaluation_partielle_ne_donne_pas_de_niveau(self, client, app, scene):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        _note(client, scene["collab"], scene["act"], scene["d1"], "0", 3, scene["role"])
        st = client.get(f"/mastery/activity/{scene['collab']}/{scene['act']}"
                        f"?role_id={scene['role']}").get_json()
        assert st["self_global_level"] is None
        assert st["n_self_evaluated"] == 1

    def test_la_preuve_de_chacun_reste_la_sienne(self, client, app, scene):
        """Les deux notes portent chacune leur preuve : celle du collaborateur
        ne doit pas écraser celle de son développeur, ni l'inverse."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        _note(client, scene["collab"], scene["act"], scene["d1"], "0", 3, scene["role"],
              preuve="Je tiens le poste depuis six mois.")
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        _note(client, scene["collab"], scene["act"], scene["d1"], "2", 2, scene["role"],
              preuve="Deux dossiers repris en revue.")
        st = client.get(f"/mastery/activity/{scene['collab']}/{scene['act']}"
                        f"?role_id={scene['role']}").get_json()
        res = next(r for r in st["results"] if r["data_id"] == scene["d1"])
        assert res["evidence"] == "Deux dossiers repris en revue."
        assert res["self_evidence"] == "Je tiens le poste depuis six mois."


# ═══════════════════════════════════════════════════════════════════════════
class TestSynthese:
    """La vue d'ensemble : tous les rôles d'un coup, avant d'entrer dans le
    détail. Elle n'existait pas — on tombait directement dans un rôle."""

    def test_elle_rend_les_roles_avec_leurs_compteurs(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.get(f"/mastery/synthese/{scene['collab']}")
        assert r.status_code == 200
        d = r.get_json()
        role = next(x for x in d["roles"] if x["role_id"] == scene["role"])
        assert role["n_activities"] == 1
        assert set(role["counts"]) == {"held", "gap", "todo", "setup"}
        assert d["totals"]["held"] + d["totals"]["gap"] \
            + d["totals"]["todo"] + d["totals"]["setup"] == d["n_activities"]

    def test_le_niveau_du_role_est_le_minimum_et_exige_tout_evalue(self, client, app, scene):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation

        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        _note(client, scene["collab"], scene["act"], scene["d1"], "2", 3, scene["role"])
        role = _role(client, scene)
        assert role["level"] is None                 # un seul résultat sur deux

        _note(client, scene["collab"], scene["act"], scene["d2"], "2", 2, scene["role"])
        role = _role(client, scene)
        assert role["level"] == 2                    # le minimum
        assert role["gap"] == -1                     # requis 3
        assert role["n_gap"] == 1
        assert role["gap_activities"][0]["activity_id"] == scene["act"]

    def test_un_tiers_ne_lit_pas_le_dossier(self, client, scene):
        _connecte(client, scene["tiers"], "tiers77@devoptiq.com")
        assert client.get(f"/mastery/synthese/{scene['collab']}").status_code == 403

    def test_chacun_lit_le_sien(self, client, scene):
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        assert client.get(f"/mastery/synthese/{scene['collab']}").status_code == 200

    def test_le_tableau_d_un_role_est_ferme_de_la_meme_facon(self, client, scene):
        """Deux portes sur la même donnée : elles se verrouillent ensemble."""
        _connecte(client, scene["tiers"], "tiers77@devoptiq.com")
        assert client.get(
            f"/mastery/dashboard/{scene['collab']}/{scene['role']}").status_code == 403


def _role(client, scene):
    d = client.get(f"/mastery/synthese/{scene['collab']}").get_json()
    return next(x for x in d["roles"] if x["role_id"] == scene["role"])


# ═══════════════════════════════════════════════════════════════════════════
class TestContexte:
    """Un seul appel décide du mode de la page."""

    def test_le_developpeur_est_reconnu_avec_ses_collaborateurs(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        d = client.get("/competences/contexte").get_json()
        assert d["est_dev"] is True
        assert scene["collab"] in [c["id"] for c in d["collaborateurs"]]
        assert d["dev"]["id"] == scene["dev"]

    def test_le_collaborateur_voit_SON_developpeur(self, client, scene):
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        d = client.get("/competences/contexte").get_json()
        assert d["est_dev"] is False
        assert d["dev"]["id"] == scene["dev"]
        assert d["collaborateurs"] == []

    def test_sans_session_c_est_401(self, client):
        with client.session_transaction() as sess:
            sess.clear()
        assert client.get("/competences/contexte").status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
class TestPlanDeFormation:

    def _en_ecart(self, client, app, scene):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        for did in (scene["d1"], scene["d2"]):
            _note(client, scene["collab"], scene["act"], did, "2", 2, scene["role"])

    def test_le_contexte_ne_retient_que_les_activites_en_retard(self, client, app, scene):
        self._en_ecart(client, app, scene)
        d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
        assert [a["activity_id"] for a in d["activites"]] == [scene["act"]]
        assert d["activites"][0]["gap"] == -1
        assert d["parametres"]["heures_semaine"] > 0

    def test_sans_ecart_il_n_y_a_rien_a_combler(self, client, app, scene):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        for did in (scene["d1"], scene["d2"]):
            _note(client, scene["collab"], scene["act"], did, "2", 3, scene["role"])
        d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
        assert d["activites"] == []

    def test_sans_cle_IA_un_plan_se_construit_quand_meme(self, client, app, scene):
        """⚠️ La suite tourne SANS clé IA (conftest les retire). C'est donc le
        repli qui est exercé ici — et c'est le chemin qui doit tenir : il ne
        propose que ce qui est réellement en base, sans inventer de module."""
        self._en_ecart(client, app, scene)
        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["actions"], "le repli doit produire au moins une action"
        for a in d["actions"]:
            assert a["titre"]
            assert a["heures"] >= 1          # une action sans charge ne s'ordonnance pas
            assert a["type"] in ("TERRAIN", "ACCOMPAGNEMENT", "FORMATION")
        assert any(a["type"] == "TERRAIN" for a in d["actions"]), \
            "un écart se comble d'abord en situation de travail (CDC)"

    def test_il_s_enregistre_et_se_relit(self, client, app, scene):
        self._en_ecart(client, app, scene)
        actions = [{"id": "A1", "titre": "Reprendre deux chiffrages en binôme",
                    "type": "TERRAIN", "activity_id": scene["act"],
                    "objectif": "Atteindre Maîtrise étendue", "heures": 18,
                    "livrable": "", "critere": "Écart de marge < 3 %"}]
        params = {"heures_semaine": 6, "semaines": 8}
        r = client.post("/plan/enregistrer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"],
            "parametres": params, "actions": actions, "source": "LOCAL"}),
            content_type="application/json")
        assert r.status_code == 200

        d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
        assert d["parametres"] == params
        assert d["actions"][0]["heures"] == 18
        assert d["source"] == "LOCAL"

    def test_il_n_y_a_qu_UN_plan_par_couple(self, client, app, scene):
        """On reprend un plan, on ne l'empile pas : sinon la relecture ne sait
        plus lequel fait foi."""
        from Code.models.models import PlanFormation
        self._en_ecart(client, app, scene)
        for h in (4, 9):
            client.post("/plan/enregistrer", data=json.dumps({
                "user_id": scene["collab"], "role_id": scene["role"],
                "parametres": {"heures_semaine": h, "semaines": 10}, "actions": []}),
                content_type="application/json")
        with app.app_context():
            assert PlanFormation.query.filter_by(
                user_id=scene["collab"], role_id=scene["role"]).count() == 1
        d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
        assert d["parametres"]["heures_semaine"] == 9

    def test_le_collaborateur_ne_se_fabrique_pas_son_plan(self, client, scene):
        """Proposer un plan de développement pour quelqu'un, c'est le noter :
        même porte, même clé."""
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        assert r.status_code == 403
        r = client.post("/plan/enregistrer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"],
            "parametres": {}, "actions": []}), content_type="application/json")
        assert r.status_code == 403

    def test_il_peut_en_revanche_le_LIRE(self, client, scene):
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        assert client.get(f"/plan/{scene['collab']}/{scene['role']}").status_code == 200

    def test_un_tiers_ne_lit_rien(self, client, scene):
        _connecte(client, scene["tiers"], "tiers77@devoptiq.com")
        assert client.get(f"/plan/{scene['collab']}/{scene['role']}").status_code == 403

    def test_la_table_du_plan_existe_vraiment(self, app):
        """⚠️ `training_plan` et `user_activity_plans` ont chacune coûté un 500
        en production parce que rien ne les créait sur une base neuve. Celle-ci
        a un modèle : `create_all` la rend partout."""
        from Code.extensions import db
        from Code.models.models import PlanFormation
        with app.app_context():
            assert db.inspect(db.engine).has_table(PlanFormation.__tablename__)

    def test_role_inexistant_sur_lire_donne_404(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.get(f"/plan/{scene['collab']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "role_not_found"

    def test_payload_invalide_sur_proposer_et_enregistrer(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.post("/plan/proposer", data=json.dumps({"user_id": scene["collab"]}),
                         content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"
        r = client.post("/plan/enregistrer", data=json.dumps({"role_id": scene["role"]}),
                         content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_enregistrer_avec_utilisateur_ou_role_inexistant_404(self, client, scene):
        """Un admin est habilité quelle que soit la cible : seul le 404
        « ressource absente » doit rester à tester ici, pas le 403."""
        _connecte(client, scene["admin"], "test@devoptiq.com")
        r = client.post("/plan/enregistrer", data=json.dumps({
            "user_id": 999999, "role_id": scene["role"],
            "parametres": {}, "actions": []}), content_type="application/json")
        assert r.status_code == 404
        assert r.get_json()["error"] == "not_found"
        r = client.post("/plan/enregistrer", data=json.dumps({
            "user_id": scene["collab"], "role_id": 999999,
            "parametres": {}, "actions": []}), content_type="application/json")
        assert r.status_code == 404

    def test_supprimer_est_reserve_a_qui_note(self, client, scene):
        _connecte(client, scene["collab"], "collab77@devoptiq.com")
        r = client.delete(f"/plan/{scene['collab']}/{scene['role']}")
        assert r.status_code == 403

    def test_supprimer_efface_le_plan_enregistre(self, client, app, scene):
        from Code.models.models import PlanFormation
        self._en_ecart(client, app, scene)
        client.post("/plan/enregistrer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"],
            "parametres": {"heures_semaine": 5, "semaines": 6}, "actions": []}),
            content_type="application/json")
        r = client.delete(f"/plan/{scene['collab']}/{scene['role']}")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True
        with app.app_context():
            assert PlanFormation.query.filter_by(
                user_id=scene["collab"], role_id=scene["role"]).first() is None

    def test_supprimer_un_plan_absent_ne_plante_pas(self, client, scene):
        """Rien à effacer n'est pas une erreur : idempotent."""
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.delete(f"/plan/{scene['collab']}/{scene['role']}")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_les_capacites_en_ecart_apparaissent_et_se_dedupliquent(self, client, app, scene):
        """Un même savoir-faire relié à DEUX résultats en écart ne doit
        apparaître qu'UNE fois — et nourrit le plan de repli local."""
        from Code.extensions import db
        from Code.models.models import ResultCapabilityLink, SavoirFaire
        self._en_ecart(client, app, scene)
        with app.app_context():
            sf = SavoirFaire(activity_id=scene["act"], description="Régler la machine 77")
            db.session.add(sf)
            db.session.commit()
            sf_id = sf.id
            for did in (scene["d1"], scene["d2"]):
                db.session.add(ResultCapabilityLink(
                    entity_id=scene["entity"], activity_id=scene["act"], data_id=did,
                    item_type="SAVOIR_FAIRE", item_id=sf_id, required_level=2, source="MANUAL"))
            db.session.commit()
        try:
            d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
            caps = d["activites"][0]["capabilities"]
            assert len(caps) == 1, "le même savoir-faire relié à 2 résultats ne compte qu'une fois"
            assert caps[0]["type_label"]
            assert caps[0]["label"] == "Régler la machine 77"

            r = client.post("/plan/proposer", data=json.dumps({
                "user_id": scene["collab"], "role_id": scene["role"]}),
                content_type="application/json")
            actions = r.get_json()["actions"]
            assert any("Régler la machine 77" in a["titre"] for a in actions), (
                "le repli local doit produire une action pour la capacité en écart")
        finally:
            with app.app_context():
                ResultCapabilityLink.query.filter_by(activity_id=scene["act"]).delete()
                SavoirFaire.query.filter_by(activity_id=scene["act"]).delete()
                db.session.commit()

    def _ia(self, monkeypatch, content=None, raise_exc=None):
        class _Msg:
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, content):
                self.message = _Msg(content)

        class _Completions:
            def __init__(self, content, raise_exc):
                self._content, self._raise_exc = content, raise_exc

            def create(self, **kw):
                if self._raise_exc is not None:
                    raise self._raise_exc
                return type("R", (), {"choices": [_Choice(self._content)]})()

        class _Chat:
            def __init__(self, content, raise_exc):
                self.completions = _Completions(content, raise_exc)

        class _Client:
            def __init__(self, content, raise_exc):
                self.chat = _Chat(content, raise_exc)

        fake = _Client(content, raise_exc)
        monkeypatch.setattr("Code.routes.plan_formation.openai_client_or_none",
                             lambda: (fake, None))

    def test_avec_cle_IA_le_plan_vient_du_modele(self, client, app, scene, monkeypatch):
        self._en_ecart(client, app, scene)
        contenu = json.dumps({"actions": [
            {"titre": "Reprendre 2 chiffrages en binôme", "type": "TERRAIN",
             "activite": "Activité Test 77", "objectif": "Fiabiliser la marge",
             "heures": 9000, "livrable": "Compte-rendu", "critere": "Écart < 3 %"},
            {"titre": "Type inconnu retombe en formation", "type": "BALLET",
             "activite": "Activité inconnue", "objectif": "", "heures": 0,
             "livrable": "", "critere": ""},
            {"titre": "", "type": "FORMATION", "activite": "", "objectif": "",
             "heures": 5, "livrable": "", "critere": ""},
        ]})
        self._ia(monkeypatch, content=contenu)
        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        d = r.get_json()
        assert d["source"] == "AI"
        # l'action au titre vide est filtrée : il n'en reste que 2.
        assert len(d["actions"]) == 2
        a1, a2 = d["actions"]
        assert a1["activity_id"] == scene["act"]
        assert a1["heures"] == 200, "une charge doit être bornée à 200h"
        assert a2["type"] == "FORMATION", "un type hors catalogue retombe sur FORMATION"
        assert a2["activity_id"] is None, "une activité qui ne matche aucun nom reste orpheline"
        assert a2["heures"] == 1, "une charge nulle ne peut pas être gratuite : bornée à 1h"

    def test_avec_cle_IA_une_charge_non_numerique_ne_fait_pas_planter(self, client, app, scene, monkeypatch):
        """`heures` texte, illisible : on ne plante pas, on la traite comme
        absente (0, puis bornée à 1) plutôt que de perdre l'action entière."""
        self._en_ecart(client, app, scene)
        contenu = json.dumps({"actions": [
            {"titre": "Charge illisible", "type": "FORMATION",
             "activite": "Activité Test 77", "objectif": "", "heures": "beaucoup",
             "livrable": "", "critere": ""},
        ]})
        self._ia(monkeypatch, content=contenu)
        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        d = r.get_json()
        assert d["source"] == "AI"
        assert d["actions"][0]["heures"] == 1

    def test_capacites_en_ecart_survit_a_une_erreur_du_diagnostic(self, client, app, scene, monkeypatch):
        """Le diagnostic est un module qui bouge ; s'il lève, le plan ne doit
        pas planter — juste ignorer les capacités de ce résultat-là."""
        from Code.extensions import db
        from Code.models.models import ResultCapabilityLink, SavoirFaire
        self._en_ecart(client, app, scene)
        with app.app_context():
            sf = SavoirFaire(activity_id=scene["act"], description="Capacité qui casse")
            db.session.add(sf)
            db.session.commit()
            sf_id = sf.id
            db.session.add(ResultCapabilityLink(
                entity_id=scene["entity"], activity_id=scene["act"], data_id=scene["d1"],
                item_type="SAVOIR_FAIRE", item_id=sf_id, required_level=2, source="MANUAL"))
            db.session.commit()

        def _casse(*a, **kw):
            raise RuntimeError("diagnostic indisponible")
        monkeypatch.setattr("Code.routes.diagnostic._linked_capabilities", _casse)
        try:
            r = client.get(f"/plan/{scene['collab']}/{scene['role']}")
            assert r.status_code == 200
            assert r.get_json()["activites"][0]["capabilities"] == []
        finally:
            with app.app_context():
                ResultCapabilityLink.query.filter_by(activity_id=scene["act"]).delete()
                SavoirFaire.query.filter_by(activity_id=scene["act"]).delete()
                db.session.commit()

    def test_avec_cle_IA_une_exception_retombe_sur_le_repli(self, client, app, scene, monkeypatch):
        self._en_ecart(client, app, scene)
        self._ia(monkeypatch, raise_exc=RuntimeError("boom"))
        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        d = r.get_json()
        assert d["source"] == "error"
        assert d["actions"], "l'exception ne doit pas laisser l'écran sans proposition"

    def test_IA_sans_actions_exploitables_retombe_aussi_sur_le_repli(self, client, app, scene, monkeypatch):
        self._en_ecart(client, app, scene)
        self._ia(monkeypatch, content=json.dumps({"actions": [{"titre": "", "heures": 1}]}))
        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        d = r.get_json()
        assert d["source"] == "empty"
        assert d["actions"], "aucune action exploitable côté IA : le repli local prend le relais"


class TestCouvertureEtProfil:
    """La vue d'ensemble apporte deux choses que rien ne donnait : un taux de
    couverture, et le profil qui sert de base au graphe."""

    def _pose(self, client, app, scene, n1, n2):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        if n1 is not None:
            _note(client, scene["collab"], scene["act"], scene["d1"], "2", n1, scene["role"])
        if n2 is not None:
            _note(client, scene["collab"], scene["act"], scene["d2"], "2", n2, scene["role"])
        return client.get(f"/mastery/synthese/{scene['collab']}").get_json()

    def test_le_requis_tenu_donne_cent_pour_cent(self, client, app, scene):
        d = self._pose(client, app, scene, 3, 3)     # requis 3
        assert _role_de(d, scene)["couverture"] == 100
        assert d["couverture"] == 100

    def test_un_niveau_sous_le_requis_fait_baisser_le_taux(self, client, app, scene):
        d = self._pose(client, app, scene, 2, 2)     # 2 tenu sur 3 requis
        assert _role_de(d, scene)["couverture"] == 67

    def test_un_depassement_ne_compense_pas(self, client, app, scene):
        """⚠️ Chaque activité est plafonnée à SON requis. Sans ce plafond, un
        expert sur une activité masquerait une lacune sur une autre — et un
        collaborateur pourrait afficher 100 % en étant en écart quelque part."""
        from Code.extensions import db
        from Code.models.models import Activities, Data, activity_roles
        with app.app_context():
            entity_id = scene["entity"]
            autre = Activities(entity_id=entity_id, name="Activité Plafond 77")
            db.session.add(autre)
            db.session.commit()
            db.session.execute(activity_roles.insert().values(
                activity_id=autre.id, role_id=scene["role"], status="Garant",
                required_mastery_level=2))
            d3 = Data(entity_id=entity_id, name="Résultat C 77", type="flux",
                      producer_activity_id=autre.id, semantic_nature="RESULT")
            db.session.add(d3)
            db.session.commit()
            aid, did = autre.id, d3.id
        try:
            self._pose(client, app, scene, 1, 1)          # 1/3 sur la première
            _note(client, scene["collab"], aid, did, "2", 4, scene["role"])  # 4 pour un requis de 2
            d = client.get(f"/mastery/synthese/{scene['collab']}").get_json()
            # 1 (plafonné à 3) + 2 (plafonné à 2) sur 3 + 2 requis = 60 %.
            assert _role_de(d, scene)["couverture"] == 60
        finally:
            with app.app_context():
                from Code.models.models import CompetencyEvaluation
                CompetencyEvaluation.query.filter_by(activity_id=aid).delete()
                db.session.execute(activity_roles.delete().where(
                    activity_roles.c.activity_id == aid))
                Data.query.filter_by(producer_activity_id=aid).delete()
                obj = db.session.get(Activities, aid)
                if obj:
                    db.session.delete(obj)
                db.session.commit()

    def test_une_activite_non_evaluee_ne_compte_pas_comme_un_zero(self, client, app, scene):
        """⚠️ La distinction que tout le module tient : NULL ≠ 0. Une activité
        qu'on n'a pas encore regardée n'est pas une activité ratée — elle sort
        du calcul, et le nombre d'évaluées est renvoyé pour lire le taux."""
        d = self._pose(client, app, scene, 3, None)   # un seul résultat noté
        role = _role_de(d, scene)
        assert role["level"] is None                  # l'activité n'est pas évaluée
        assert role["couverture"] is None             # donc rien à couvrir encore
        assert role["n_evaluated"] == 0

    def test_le_profil_porte_un_axe_par_activite(self, client, app, scene):
        d = self._pose(client, app, scene, 2, 2)
        axe = next(a for a in d["profil"] if a["activity_id"] == scene["act"])
        assert axe["required_level"] == 3
        assert axe["demonstrated_level"] == 2
        assert axe["role_name"] == "Rôle Test 77"
        assert d["n_activities_uniques"] == len({a["activity_id"] for a in d["profil"]})

    def test_une_activite_portee_par_deux_roles_ne_compte_qu_une_fois(self, client, app, scene):
        """Sinon la forme du graphe dirait surtout combien de rôles se
        partagent la même activité."""
        from Code.extensions import db
        from Code.models.models import Role, UserRole, activity_roles
        with app.app_context():
            r2 = Role(name="Rôle Doublon 77", entity_id=scene["entity"])
            db.session.add(r2)
            db.session.commit()
            db.session.add(UserRole(user_id=scene["collab"], role_id=r2.id,
                                    manager_id=scene["dev"]))
            db.session.execute(activity_roles.insert().values(
                activity_id=scene["act"], role_id=r2.id, status="Garant",
                required_mastery_level=2))
            db.session.commit()
            r2_id = r2.id
        try:
            _connecte(client, scene["dev"], "dev77@devoptiq.com")
            d = client.get(f"/mastery/synthese/{scene['collab']}").get_json()
            vus = [a for a in d["profil"] if a["activity_id"] == scene["act"]]
            assert len(vus) == 1
            assert d["n_activities"] > d["n_activities_uniques"]
        finally:
            with app.app_context():
                UserRole.query.filter_by(role_id=r2_id).delete()
                db.session.execute(activity_roles.delete().where(
                    activity_roles.c.role_id == r2_id))
                obj = db.session.get(Role, r2_id)
                if obj:
                    db.session.delete(obj)
                db.session.commit()


def _role_de(d, scene):
    return next(x for x in d["roles"] if x["role_id"] == scene["role"])


class TestLePlanSuitLEcran:
    """⚠️ L'écran et le plan ne s'accordaient pas sur le mot « écart ».

    L'écran compte une activité « en écart » dès que le niveau démontré est
    sous 2 — l'autonomie n'est pas démontrée, requis ou pas. Le plan, lui,
    filtrait sur `gap < 0`, or `gap` est NUL quand le rôle n'a fixé aucun niveau
    requis. Résultat : le bouton « Plan de formation » s'affichait, et la fenêtre
    répondait « aucun écart sur ce rôle ».
    """

    @pytest.fixture
    def sans_requis(self, app, scene):
        """Le même rôle, mais sans niveau requis sur l'activité."""
        from Code.extensions import db
        from Code.models.models import activity_roles
        with app.app_context():
            db.session.execute(activity_roles.update().where(
                (activity_roles.c.activity_id == scene["act"])
                & (activity_roles.c.role_id == scene["role"])
            ).values(required_mastery_level=None))
            db.session.commit()
        yield
        with app.app_context():
            db.session.execute(activity_roles.update().where(
                (activity_roles.c.activity_id == scene["act"])
                & (activity_roles.c.role_id == scene["role"])
            ).values(required_mastery_level=3))
            db.session.commit()

    def test_sous_le_seuil_d_autonomie_sans_requis_le_plan_voit_l_ecart(
            self, client, app, scene, sans_requis):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        for did in (scene["d1"], scene["d2"]):
            _note(client, scene["collab"], scene["act"], did, "2", 1, scene["role"])

        # L'écran : le tableau du rôle la classe « en écart » (niveau 1 < 2).
        rows = client.get(
            f"/mastery/dashboard/{scene['collab']}/{scene['role']}").get_json()["activities"]
        ligne = next(r for r in rows if r["activity_id"] == scene["act"])
        assert ligne["demonstrated_level"] == 1
        assert ligne["gap"] is None, "aucun requis : l'écart chiffré n'existe pas"

        # Le plan doit voir le MÊME écart, avec le seuil d'autonomie pour cible.
        d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
        assert [a["activity_id"] for a in d["activites"]] == [scene["act"]]
        cible = d["activites"][0]
        assert cible["required_level"] == 2, "à défaut de requis, la cible est l'autonomie"
        assert cible["gap"] == -1

    def test_une_activite_NON_EVALUEE_n_entre_jamais_dans_un_plan(
            self, client, app, scene):
        """Un plan ne se bâtit que sur du mesuré : une activité qu'on n'a pas
        regardée n'est pas une activité en retard."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
        assert d["activites"] == []

        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        assert r.get_json()["source"] == "no_gap"
        assert r.get_json()["actions"] == []

    def test_une_evaluation_PARTIELLE_non_plus(self, client, app, scene):
        """Le niveau d'une activité n'existe que si TOUS ses résultats sont
        évalués : à moitié notée, elle n'est pas encore jugeable."""
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        _note(client, scene["collab"], scene["act"], scene["d1"], "2", 1, scene["role"])
        d = client.get(f"/plan/{scene['collab']}/{scene['role']}").get_json()
        assert d["activites"] == []


class TestPerimetreDeLaSynthese:
    """⚠️ « Pourquoi j'ai perdu mes données relatives à la notation ? »

    Rien n'était perdu : l'écran mélangeait DEUX PÉRIMÈTRES.
      · `synthese` listait TOUS les rôles du collaborateur, toutes cartos
        confondues (`UserRole.query.filter_by(user_id=…)`, sans entité) ;
      · `dashboard_rows` filtre les activités sur l'entité ACTIVE.
    Changer de carto active — ce que fait le sélecteur de la page RH, et la page
    Cartographie — affichait donc les rôles d'une carto avec les activités d'une
    autre : zéro partout, « — du requis tenu », et l'impression que tout avait
    disparu.

    Un rôle qui ne PEUT PAS porter d'activité n'a rien à faire sur cet écran.
    """

    def _entite(self, app, nom):
        """Une carto de travail, AVEC un propriétaire.

        ⚠️ Sans `owner_id`, `can_read` la rend lisible par TOUT LE MONDE
        (`entity.owner_id in (None, user.id)`) : elle entrait alors dans le repli
        « aucune entité active » d'autres fichiers de tests et faisait tomber
        `test_75`. La base est partagée — une donnée laissée sans maître circule.
        """
        from Code.extensions import db
        from Code.models.models import Entity, User
        with app.app_context():
            e = Entity.query.filter_by(name=nom).first()
            if not e:
                proprio = User.query.filter_by(email="test@devoptiq.com").first()
                e = Entity(name=nom, owner_id=proprio.id if proprio else None)
                db.session.add(e)
                db.session.commit()
            return e.id

    def test_un_role_d_une_autre_carto_ne_s_affiche_pas_a_zero(self, app, auth_client, ids):
        """Le cas exact du signalement : la carto active n'est pas celle du rôle."""
        from Code.extensions import db
        from Code.models.models import Activities, Role, User, UserRole
        from Code.models.models import activity_roles

        autre = self._entite(app, "t77-autre-carto")
        with app.app_context():
            u = User.query.filter_by(email="test@devoptiq.com").first()
            role = Role(name="t77-role-ailleurs", entity_id=ids["entity_id"])
            db.session.add(role)
            db.session.commit()
            act = Activities(name="t77-activite", entity_id=ids["entity_id"])
            db.session.add(act)
            db.session.commit()
            db.session.execute(activity_roles.insert().values(
                activity_id=act.id, role_id=role.id, status="Garant"))
            db.session.add(UserRole(user_id=u.id, role_id=role.id))
            db.session.commit()
            uid, rid, aid = u.id, role.id, act.id

        try:
            # 1. Sur la BONNE carto, le rôle porte bien son activité.
            with auth_client.session_transaction() as sess:
                sess["active_entity_id"] = ids["entity_id"]
            d = auth_client.get("/mastery/synthese/%d" % uid).get_json()
            mien = next((r for r in d["roles"] if r["role_id"] == rid), None)
            assert mien and mien["n_activities"] == 1, (
                "sur sa propre carto, le rôle doit porter son activité")

            # 2. Depuis une AUTRE carto active, le rôle garde SES activités.
            #    ⚠️ C'est le cœur du signalement : il s'affichait à « 0 activité »
            #    parce que les activités, elles, étaient filtrées sur la carto
            #    active. Les masquer n'était pas la réponse — un rôle porte ses
            #    activités, quelle que soit la carto qu'on regarde par ailleurs.
            with auth_client.session_transaction() as sess:
                sess["active_entity_id"] = autre
            d = auth_client.get("/mastery/synthese/%d" % uid).get_json()
            ailleurs = next((r for r in d["roles"] if r["role_id"] == rid), None)
            assert ailleurs is not None, "le rôle ne doit pas disparaître"
            assert ailleurs["n_activities"] == 1, (
                "un rôle ne doit JAMAIS tomber à 0 activité parce qu'une autre "
                "carto est active — c'est ce qui fait croire à une perte")
        finally:
            with app.app_context():
                db.session.execute(activity_roles.delete().where(
                    activity_roles.c.role_id == rid))
                UserRole.query.filter_by(role_id=rid).delete()
                a = db.session.get(Activities, aid)
                if a:
                    db.session.delete(a)
                r = db.session.get(Role, rid)
                if r:
                    db.session.delete(r)
                db.session.commit()
            with auth_client.session_transaction() as sess:
                sess["active_entity_id"] = ids["entity_id"]

    def test_les_totaux_suivent_les_roles_affiches(self, app, auth_client, ids):
        """Le compte d'activités ne doit jamais additionner des rôles qu'on
        n'affiche pas : deux chiffres pour un même écran, c'est ce que la vue
        d'ensemble existe pour éviter."""
        uid = None
        from Code.models.models import User
        with app.app_context():
            uid = User.query.filter_by(email="test@devoptiq.com").first().id
        with auth_client.session_transaction() as sess:
            sess["active_entity_id"] = ids["entity_id"]
        d = auth_client.get("/mastery/synthese/%d" % uid).get_json()
        assert d["n_activities"] == sum(r["n_activities"] for r in d["roles"])
