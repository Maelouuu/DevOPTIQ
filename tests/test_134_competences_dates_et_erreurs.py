# tests/test_134_competences_dates_et_erreurs.py
"""Compétences — dates `created_at` stockées en texte (formats hétérogènes), erreur 500
à l'enregistrement et reprise après conflit d'insertion."""
import json
from unittest import mock

import pytest

pytestmark = pytest.mark.competences


@pytest.fixture()
def scene(app, ids):
    """Utilisateur + rôle + activité reliés. Tout est nettoyé."""
    from Code.extensions import db
    from Code.models.models import (Role, User, UserRole, Activities,
                                    CompetencyEvaluation, activity_roles)
    from werkzeug.security import generate_password_hash
    with app.app_context():
        role = Role(name="RoleGap134", entity_id=ids["entity_id"])
        user = User(entity_id=ids["entity_id"], first_name="Gap", last_name="Cent34",
                    email="gap134@test.local", password=generate_password_hash("Pass123!"),
                    status="user")
        act = Activities(entity_id=ids["entity_id"], name="ActGap134", shape_id="gap134")
        db.session.add_all([role, user, act]); db.session.flush()
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="active"))
        db.session.commit()
        d = {"role": role.id, "user": user.id, "act": act.id}
    yield d
    with app.app_context():
        CompetencyEvaluation.query.filter_by(user_id=d["user"]).delete()
        db.session.execute(activity_roles.delete().where(activity_roles.c.role_id == d["role"]))
        UserRole.query.filter_by(user_id=d["user"]).delete()
        Activities.query.filter_by(id=d["act"]).delete()
        User.query.filter_by(id=d["user"]).delete()
        Role.query.filter_by(id=d["role"]).delete()
        db.session.commit()


def _entity(client, ids):
    with client.session_transaction() as s:
        s["active_entity_id"] = ids["entity_id"]


def _poser(app, scene, created_at, eval_number="manager", item_id=None, item_type="activities"):
    from Code.extensions import db
    from Code.models.models import CompetencyEvaluation
    with app.app_context():
        db.session.add(CompetencyEvaluation(
            user_id=scene["user"], activity_id=scene["act"], item_id=item_id,
            item_type=item_type, eval_number=eval_number, note="green"))
        db.session.flush()
        # SQL direct : l'ORM remplacerait un None par le défaut `utcnow`.
        db.session.execute(db.text(
            "UPDATE competency_evaluation SET created_at = :c WHERE user_id = :u"),
            {"c": created_at, "u": scene["user"]})
        db.session.commit()


def _save(client, payload):
    return client.post("/competences/save_user_evaluations", data=json.dumps(payload),
                       content_type="application/json")


class TestDatesEvaluationsParUtilisateur:

    @pytest.mark.parametrize("brut, attendu", [
        ("04/03/2025 10:30", "2025-03-04T10:30:00"),
        ("04/03/2025", "2025-03-04T00:00:00"),
        ("2025-03-04 10:30:00", "2025-03-04T10:30:00"),
        ("n'importe quoi", "n'importe quoi"),
        (None, ""),
    ])
    def test_created_at_texte_est_normalise(self, auth_client, app, scene, ids, brut, attendu):
        _entity(auth_client, ids)
        _poser(app, scene, brut)
        r = auth_client.get(f"/competences/get_user_evaluations_by_user/{scene['user']}")
        assert r.status_code == 200
        lignes = r.get_json()
        assert len(lignes) == 1
        assert lignes[0]["created_at"] == attendu

    def test_utilisateur_sans_evaluation_renvoie_liste_vide(self, auth_client, scene, ids):
        _entity(auth_client, ids)
        r = auth_client.get(f"/competences/get_user_evaluations_by_user/{scene['user']}")
        assert r.get_json() == []


class TestSyntheseGlobalePlate:

    @pytest.mark.parametrize("brut", ["2025-03-04T10:00:00", "04/03/2025"])
    def test_date_affichee_en_jj_mm_aaaa(self, auth_client, app, scene, ids, brut):
        _entity(auth_client, ids)
        _poser(app, scene, brut)
        r = auth_client.get(f"/competences/global_flat_summary/{scene['user']}")
        assert r.status_code == 200
        assert "04/03/2025" in r.get_data(as_text=True)

    def test_date_absente_ne_plante_pas(self, auth_client, app, scene, ids):
        _entity(auth_client, ids)
        _poser(app, scene, None)
        r = auth_client.get(f"/competences/global_flat_summary/{scene['user']}")
        assert r.status_code == 200
        assert "ActGap134" in r.get_data(as_text=True)


class TestEnregistrementErreurs:

    def test_item_id_illisible_donne_500_sans_ecrire(self, auth_client, app, scene):
        from Code.models.models import CompetencyEvaluation
        r = _save(auth_client, {"userId": scene["user"], "evaluations": [
            {"activity_id": scene["act"], "item_id": [1, 2], "item_type": "savoir_faires",
             "eval_number": "1", "note": "green"}]})
        assert r.status_code == 500
        assert r.get_json()["success"] is False
        with app.app_context():
            assert CompetencyEvaluation.query.filter_by(user_id=scene["user"]).count() == 0

    def test_donnees_incompletes_400(self, auth_client, scene):
        assert _save(auth_client, {"userId": scene["user"], "evaluations": []}).status_code == 400
        assert _save(auth_client, {"evaluations": [{"activity_id": 1}]}).status_code == 400

    def test_evaluation_sans_activite_est_ignoree(self, auth_client, app, scene):
        from Code.models.models import CompetencyEvaluation
        r = _save(auth_client, {"userId": scene["user"], "evaluations": [
            {"item_type": "activities", "eval_number": "manager", "note": "green"}]})
        assert r.status_code == 200
        assert r.get_json()["evaluations"] == []
        with app.app_context():
            assert CompetencyEvaluation.query.filter_by(user_id=scene["user"]).count() == 0

    @pytest.mark.parametrize("item_id", [None, 4242])
    def test_conflit_d_insertion_est_rattrape_sans_erreur(self, auth_client, app, scene, item_id):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        reel = db.session.flush
        appels = {"n": 0}

        def flush_qui_echoue_une_fois(*a, **k):
            appels["n"] += 1
            if appels["n"] == 1:
                raise RuntimeError("conflit simulé")
            return reel(*a, **k)

        with mock.patch.object(db.session, "flush", side_effect=flush_qui_echoue_une_fois):
            r = _save(auth_client, {"userId": scene["user"], "evaluations": [
                {"activity_id": scene["act"], "item_id": item_id, "item_type": "activities",
                 "eval_number": "manager", "note": "green"}]})
        assert r.status_code == 200
        assert r.get_json()["success"] is True
        with app.app_context():
            assert CompetencyEvaluation.query.filter_by(user_id=scene["user"]).count() == 0
