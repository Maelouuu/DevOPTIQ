# -*- coding: utf-8 -*-
"""Un développeur de compétences l'est PAR RÔLE, pas par personne.

Le scénario est celui rapporté par le client, au mot près :

    « Je suis développeur de compétences pour 2 rôles pour une personne qui
      en a 4. Or quand je vais sur l'évaluation, je vois les 4 rôles alors
      que je ne suis censé pouvoir en évaluer que 2. »

C'était exact, et ce n'était pas qu'un affichage : `encadre()` répond vrai
dès qu'il existe UN rattachement, quel que soit le rôle, et `peut_noter`
s'appuyait dessus. Il voyait les quatre — et il pouvait les NOTER.

⚠️ Deux routes n'avaient AUCUN contrôle, découvertes en tirant le fil :
`/mastery/activity/<u>/<a>` (le niveau de n'importe qui, preuves comprises)
et `/mastery/required` (le niveau attendu d'un rôle, qui est une décision).
"""
import pytest

from Code.extensions import db

MDP = "Motdepasse123!"


@pytest.fixture(autouse=True)
def _session_rendue(client):
    """`client` est partagé : on rend la session telle qu'on l'a trouvée."""
    with client.session_transaction() as s:
        avant = dict(s)
    yield
    with client.session_transaction() as s:
        s.clear()
        s.update(avant)


@pytest.fixture()
def monde(app):
    """Une personne, QUATRE rôles, un développeur attaché à DEUX."""
    from Code.models.models import (Activities, Data, Entity, Role, User,
                                    UserRole, activity_roles)
    from Code.security import hash_password

    with app.app_context():
        ent = Entity(name="T104 Entité")
        db.session.add(ent)
        db.session.flush()

        def compte(prenom, statut):
            u = User(first_name=prenom, last_name="T104",
                     email="t104.%s@devoptiq.com" % prenom.lower(),
                     password=hash_password(MDP), status=statut)
            db.session.add(u)
            db.session.flush()
            return u

        dev = compte("Dev", "user")
        autre = compte("Autre", "user")
        coord = compte("Coord", "coordinateur")
        cible = compte("Cible", "user")

        roles, acts, datas = [], [], []
        for i in range(4):
            r = Role(name="T104 Rôle %d" % i, entity_id=ent.id)
            db.session.add(r)
            db.session.flush()
            a = Activities(name="T104 Activité %d" % i, entity_id=ent.id)
            db.session.add(a)
            db.session.flush()
            db.session.execute(activity_roles.insert().values(
                activity_id=a.id, role_id=r.id, status="Garant",
                required_mastery_level=3))
            d = Data(entity_id=ent.id, name="T104 Résultat %d" % i, type="flux",
                     producer_activity_id=a.id, semantic_nature="RESULT")
            db.session.add(d)
            db.session.flush()
            # ⚠️ Le développeur ne suit que les DEUX premiers.
            db.session.add(UserRole(user_id=cible.id, role_id=r.id,
                                    manager_id=dev.id if i < 2 else None))
            roles.append(r.id)
            acts.append(a.id)
            datas.append(d.id)
        db.session.commit()
        m = {"ent": ent.id, "dev": dev.id, "autre": autre.id, "coord": coord.id,
             "cible": cible.id, "roles": roles, "acts": acts, "datas": datas}
    yield m
    with app.app_context():
        from Code.models.models import (Activities, CompetencyEvaluation, Data,
                                        Entity, Role, User, UserRole,
                                        activity_roles)
        CompetencyEvaluation.query.filter(
            CompetencyEvaluation.activity_id.in_(m["acts"])).delete(synchronize_session=False)
        db.session.execute(activity_roles.delete().where(
            activity_roles.c.role_id.in_(m["roles"])))
        Data.query.filter(Data.producer_activity_id.in_(m["acts"])).delete(
            synchronize_session=False)
        UserRole.query.filter(UserRole.role_id.in_(m["roles"])).delete(
            synchronize_session=False)
        Activities.query.filter(Activities.id.in_(m["acts"])).delete(
            synchronize_session=False)
        Role.query.filter(Role.id.in_(m["roles"])).delete(synchronize_session=False)
        User.query.filter(User.email.like("t104.%")).delete(synchronize_session=False)
        Entity.query.filter_by(id=m["ent"]).delete(synchronize_session=False)
        db.session.commit()


def _as(client, app, uid):
    from Code.models.models import User
    with app.app_context():
        mail = db.session.get(User, uid).email
    with client.session_transaction() as s:
        s.clear()
        s["user_id"] = uid
        s["user_email"] = mail
        s["lang"] = "fr"


def _noter(client, uid, aid, did, role_id, niveau=2):
    charge = {"user_id": uid, "activity_id": aid, "data_id": did,
              "evaluator": "2", "mastery_level": niveau}
    if role_id is not None:
        charge["role_id"] = role_id
    return client.post("/mastery/evaluate", json=charge)


class TestCeQuIlVOIT:

    def test_il_ne_voit_que_les_deux_roles_qu_il_suit(self, client, app, monde):
        """Le constat du client, au mot près."""
        _as(client, app, monde["dev"])
        r = client.get("/mastery/synthese/%d" % monde["cible"])
        assert r.status_code == 200
        vus = {x["role_id"] for x in r.get_json()["roles"]}
        assert vus == set(monde["roles"][:2]), vus

    def test_la_personne_voit_les_quatre_siens(self, client, app, monde):
        _as(client, app, monde["cible"])
        r = client.get("/mastery/synthese/%d" % monde["cible"])
        assert {x["role_id"] for x in r.get_json()["roles"]} == set(monde["roles"])

    def test_un_coordinateur_voit_tout(self, client, app, monde):
        _as(client, app, monde["coord"])
        r = client.get("/mastery/synthese/%d" % monde["cible"])
        assert {x["role_id"] for x in r.get_json()["roles"]} == set(monde["roles"])

    def test_le_lien_GLOBAL_couvre_tous_les_roles(self, client, app, monde):
        """⚠️ `None` (aucune restriction) et une liste vide ne disent pas la
        même chose : les confondre rouvrirait le défaut dans l'autre sens, en
        cachant les rôles d'un développeur global."""
        from Code.models.models import User
        with app.app_context():
            db.session.get(User, monde["cible"]).manager_id = monde["dev"]
            db.session.commit()
        try:
            _as(client, app, monde["dev"])
            r = client.get("/mastery/synthese/%d" % monde["cible"])
            assert {x["role_id"] for x in r.get_json()["roles"]} == set(monde["roles"])
        finally:
            with app.app_context():
                db.session.get(User, monde["cible"]).manager_id = None
                db.session.commit()

    def test_un_tiers_ne_voit_rien(self, client, app, monde):
        _as(client, app, monde["autre"])
        assert client.get("/mastery/synthese/%d" % monde["cible"]).status_code == 403


class TestCeQuIlPEUT:

    def test_il_note_le_role_qu_il_suit(self, client, app, monde):
        _as(client, app, monde["dev"])
        r = _noter(client, monde["cible"], monde["acts"][0], monde["datas"][0],
                   monde["roles"][0])
        assert r.status_code == 200, r.data[:200]

    def test_il_ne_note_PAS_les_deux_autres(self, client, app, monde):
        """Le cœur du défaut : il pouvait noter les quatre."""
        _as(client, app, monde["dev"])
        r = _noter(client, monde["cible"], monde["acts"][3], monde["datas"][3],
                   monde["roles"][3])
        assert r.status_code == 403
        assert r.get_json()["reason"] == "not_the_developer_for_this_role"

    def test_omettre_le_role_ne_contourne_rien(self, client, app, monde):
        """⚠️ Sans rôle, le contrôle retomberait sur la règle par personne :
        l'omettre suffirait. La route l'exige."""
        _as(client, app, monde["dev"])
        r = _noter(client, monde["cible"], monde["acts"][3], monde["datas"][3], None)
        assert r.status_code == 400
        assert r.get_json()["reason"] == "role_required"

    def test_ni_presenter_un_role_qu_il_suit_pour_une_autre_activite(
            self, client, app, monde):
        """⚠️ Le rôle doit porter CETTE activité : sinon on note l'activité
        d'un rôle qu'on ne suit pas, en montrant celui qu'on suit."""
        _as(client, app, monde["dev"])
        r = _noter(client, monde["cible"], monde["acts"][3], monde["datas"][3],
                   monde["roles"][0])
        assert r.status_code == 404
        assert r.get_json()["error"] == "association_not_found"

    def test_le_tableau_d_un_role_non_suivi_est_refuse(self, client, app, monde):
        _as(client, app, monde["dev"])
        ok = client.get("/mastery/dashboard/%d/%d" % (monde["cible"], monde["roles"][0]))
        non = client.get("/mastery/dashboard/%d/%d" % (monde["cible"], monde["roles"][3]))
        assert ok.status_code == 200
        assert non.status_code == 403


class TestLesDeuxRoutesSansAucunControle:

    def test_la_fiche_d_une_activite_etait_ouverte_a_tous(self, client, app, monde):
        """⚠️ `/mastery/activity/<u>/<a>` n'avait AUCUN contrôle : tout compte
        connecté lisait le niveau de n'importe qui, preuves comprises."""
        _as(client, app, monde["autre"])
        r = client.get("/mastery/activity/%d/%d?role_id=%d"
                       % (monde["cible"], monde["acts"][0], monde["roles"][0]))
        assert r.status_code == 403

    def test_mais_le_developpeur_la_lit_sur_SON_role(self, client, app, monde):
        _as(client, app, monde["dev"])
        r = client.get("/mastery/activity/%d/%d?role_id=%d"
                       % (monde["cible"], monde["acts"][0], monde["roles"][0]))
        assert r.status_code == 200

    def test_le_niveau_attendu_etait_posable_par_n_importe_qui(
            self, client, app, monde):
        """⚠️ `/mastery/required` non plus : le niveau attendu d'un rôle est
        une décision, et n'importe quel compte connecté la posait."""
        _as(client, app, monde["autre"])
        r = client.post("/mastery/required", json={
            "activity_id": monde["acts"][0], "role_id": monde["roles"][0],
            "required_mastery_level": 4})
        assert r.status_code == 403

    def test_le_developpeur_du_role_le_pose(self, client, app, monde):
        _as(client, app, monde["dev"])
        r = client.post("/mastery/required", json={
            "activity_id": monde["acts"][0], "role_id": monde["roles"][0],
            "required_mastery_level": 4})
        assert r.status_code == 200

    def test_et_le_coordinateur_aussi(self, client, app, monde):
        _as(client, app, monde["coord"])
        r = client.post("/mastery/required", json={
            "activity_id": monde["acts"][3], "role_id": monde["roles"][3],
            "required_mastery_level": 2})
        assert r.status_code == 200
