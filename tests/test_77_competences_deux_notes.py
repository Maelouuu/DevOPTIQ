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


def _connecte(client, user_id, email):
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user_id
        sess["user_email"] = email
        sess["lang"] = "fr"


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


class _FakeMessagePlan:
    def __init__(self, content):
        self.content = content


class _FakeChoicePlan:
    def __init__(self, content):
        self.message = _FakeMessagePlan(content)


class _FakeCompletionPlan:
    def __init__(self, content):
        self.choices = [_FakeChoicePlan(content)]


class _FakeOpenAIClientPlan:
    """Simule le SDK OpenAI pour couvrir /plan/proposer avec une clé IA
    disponible — sans appel réseau réel."""
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

        class _Completions:
            def create(_self, **kwargs):
                if self._raise_exc is not None:
                    raise self._raise_exc
                return _FakeCompletionPlan(self._content)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class TestPlanDeFormationErreursEtSuppression:
    """Validations d'entrée, suppression du plan, et proposition avec clé IA
    disponible — chemins non exercés par TestPlanDeFormation ci-dessus."""

    def _en_ecart(self, client, app, scene):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            CompetencyEvaluation.query.filter_by(activity_id=scene["act"]).delete()
            db.session.commit()
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        for did in (scene["d1"], scene["d2"]):
            _note(client, scene["collab"], scene["act"], did, "2", 2, scene["role"])

    def test_lire_un_role_inexistant_est_404(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.get(f"/plan/{scene['collab']}/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "role_not_found"

    def test_proposer_sans_role_id_est_400(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.post("/plan/proposer", data=json.dumps({"user_id": scene["collab"]}),
                         content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_enregistrer_sans_user_id_est_400(self, client, scene):
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.post("/plan/enregistrer", data=json.dumps({"role_id": scene["role"]}),
                         content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_payload"

    def test_enregistrer_pour_un_utilisateur_inexistant_est_404(self, client, scene):
        _connecte(client, scene["admin"], "test@devoptiq.com")
        r = client.post("/plan/enregistrer", data=json.dumps({
            "user_id": 999999, "role_id": scene["role"],
            "parametres": {}, "actions": []}), content_type="application/json")
        assert r.status_code == 404
        assert r.get_json()["error"] == "not_found"

    def test_enregistrer_pour_un_role_inexistant_est_404(self, client, scene):
        _connecte(client, scene["admin"], "test@devoptiq.com")
        r = client.post("/plan/enregistrer", data=json.dumps({
            "user_id": scene["collab"], "role_id": 999999,
            "parametres": {}, "actions": []}), content_type="application/json")
        assert r.status_code == 404
        assert r.get_json()["error"] == "not_found"

    def test_supprimer_efface_le_plan_enregistre(self, client, app, scene):
        from Code.models.models import PlanFormation
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        client.post("/plan/enregistrer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"],
            "parametres": {"heures_semaine": 5, "semaines": 6}, "actions": []}),
            content_type="application/json")
        with app.app_context():
            assert PlanFormation.query.filter_by(
                user_id=scene["collab"], role_id=scene["role"]).first() is not None

        r = client.delete(f"/plan/{scene['collab']}/{scene['role']}")
        assert r.status_code == 200
        assert r.get_json() == {"ok": True}
        with app.app_context():
            assert PlanFormation.query.filter_by(
                user_id=scene["collab"], role_id=scene["role"]).first() is None

    def test_supprimer_un_plan_deja_absent_reste_ok(self, client, scene):
        """Idempotent : rien à effacer n'est pas une erreur."""
        _connecte(client, scene["dev"], "dev77@devoptiq.com")
        r = client.delete(f"/plan/{scene['collab']}/{scene['role']}")
        assert r.status_code == 200
        assert r.get_json() == {"ok": True}

    def test_un_tiers_ne_peut_pas_supprimer_le_plan_d_un_autre(self, client, scene):
        _connecte(client, scene["tiers"], "tiers77@devoptiq.com")
        r = client.delete(f"/plan/{scene['collab']}/{scene['role']}")
        assert r.status_code == 403

    def test_avec_cle_IA_le_plan_vient_du_modele(self, client, app, scene, monkeypatch):
        """Avec un client IA disponible, le contenu proposé vient du modèle —
        pas du repli local — et la source l'indique."""
        self._en_ecart(client, app, scene)
        contenu = json.dumps({"actions": [{
            "titre": "Reprendre un dossier en binôme", "type": "TERRAIN",
            "activite": "Activité Test 77", "objectif": "Fiabiliser le résultat",
            "heures": 14, "livrable": "", "critere": "Zéro écart au standard"}]})
        monkeypatch.setattr(
            "Code.routes.plan_formation.openai_client_or_none",
            lambda: (_FakeOpenAIClientPlan(content=contenu), None))

        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["source"] == "AI"
        assert d["actions"][0]["activity_id"] == scene["act"]
        assert d["actions"][0]["heures"] == 14
        assert d["actions"][0]["type"] == "TERRAIN"

    def test_avec_cle_IA_une_erreur_retombe_sur_le_repli(self, client, app, scene, monkeypatch):
        """Le modèle plante : la source le dit, mais le collaborateur reçoit
        quand même un plan — le repli local ne dépend pas de l'IA."""
        self._en_ecart(client, app, scene)
        monkeypatch.setattr(
            "Code.routes.plan_formation.openai_client_or_none",
            lambda: (_FakeOpenAIClientPlan(raise_exc=RuntimeError("boom")), None))

        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["source"] == "error"
        assert d["actions"], "le repli doit tout de même produire un plan"

    def test_avec_cle_IA_une_charge_non_numerique_ne_casse_pas_le_plan(
            self, client, app, scene, monkeypatch):
        """Le modèle répond une charge qui n'est pas un nombre : l'action est
        quand même gardée, bornée au minimum plutôt que rejetée."""
        self._en_ecart(client, app, scene)
        contenu = json.dumps({"actions": [{
            "titre": "Reprendre un dossier en binôme", "type": "TERRAIN",
            "activite": "Activité Test 77", "objectif": "Fiabiliser le résultat",
            "heures": "beaucoup", "livrable": "", "critere": ""}]})
        monkeypatch.setattr(
            "Code.routes.plan_formation.openai_client_or_none",
            lambda: (_FakeOpenAIClientPlan(content=contenu), None))

        r = client.post("/plan/proposer", data=json.dumps({
            "user_id": scene["collab"], "role_id": scene["role"]}),
            content_type="application/json")
        assert r.status_code == 200
        d = r.get_json()
        assert d["source"] == "AI"
        assert d["actions"][0]["heures"] == 1


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
