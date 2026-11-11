# tests/test_118_competences_gaps.py
"""Compétences — branches peu couvertes : évaluations d'activité entière (item_id NULL),
activité manquante ignorée, dates en texte, structure de rôle avec notes, synthèse à plat."""
import json
import pytest
from datetime import datetime

pytestmark = pytest.mark.competences


@pytest.fixture()
def scene(app, ids):
    """Entité active + rôle + utilisateur + activité reliée au rôle. Tout est nettoyé."""
    from Code.extensions import db
    from Code.models.models import (Role, User, UserRole, Activities, Savoir,
                                    CompetencyEvaluation, activity_roles)
    from werkzeug.security import generate_password_hash
    with app.app_context():
        role = Role(name="RoleGap118", entity_id=ids["entity_id"])
        user = User(entity_id=ids["entity_id"], first_name="Gap", last_name="Cent18",
                    email="gap118@test.local", password=generate_password_hash("Pass123!"),
                    status="user")
        act = Activities(entity_id=ids["entity_id"], name="ActGap118", shape_id="gap118")
        db.session.add_all([role, user, act]); db.session.flush()
        sv = Savoir(activity_id=act.id, description="Savoir gap 118")
        db.session.add(sv); db.session.flush()
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="active"))
        db.session.commit()
        d = {"role": role.id, "user": user.id, "act": act.id, "savoir": sv.id}
    yield d
    with app.app_context():
        CompetencyEvaluation.query.filter_by(user_id=d["user"]).delete()
        db.session.execute(activity_roles.delete().where(activity_roles.c.role_id == d["role"]))
        UserRole.query.filter_by(user_id=d["user"]).delete()
        Savoir.query.filter_by(id=d["savoir"]).delete()
        Activities.query.filter_by(id=d["act"]).delete()
        User.query.filter_by(id=d["user"]).delete()
        Role.query.filter_by(id=d["role"]).delete()
        db.session.commit()


def _entity(client, ids):
    with client.session_transaction() as s:
        s["active_entity_id"] = ids["entity_id"]


def _save(client, uid, evals):
    return client.post("/competences/save_user_evaluations",
                       data=json.dumps({"userId": uid, "evaluations": evals}),
                       content_type="application/json")


def _count(app, uid, **flt):
    from Code.models.models import CompetencyEvaluation
    with app.app_context():
        return CompetencyEvaluation.query.filter_by(user_id=uid, **flt).count()


class TestSaveEvaluationsActivite:

    def test_evaluation_sans_activity_id_est_ignoree(self, auth_client, app, scene):
        r = _save(auth_client, scene["user"], [{"item_id": 1, "item_type": "savoirs",
                                                "eval_number": 1, "note": "green"}])
        assert r.status_code == 200
        assert r.get_json()["evaluations"] == []
        assert _count(app, scene["user"]) == 0

    def test_note_activite_entiere_cree_puis_met_a_jour_sans_doublon(self, auth_client, app, scene):
        ev = {"activity_id": scene["act"], "item_id": None, "item_type": "activities",
              "eval_number": "garant", "note": "green"}
        assert _save(auth_client, scene["user"], [ev]).get_json()["evaluations"][0]["note"] == "green"
        r = _save(auth_client, scene["user"], [dict(ev, note="red")])
        assert r.get_json()["evaluations"][0]["note"] == "red"
        assert _count(app, scene["user"], item_type="activities") == 1

    def test_note_empty_supprime_evaluation_activite(self, auth_client, app, scene):
        ev = {"activity_id": scene["act"], "item_id": None, "item_type": "activities",
              "eval_number": "manager", "note": "orange"}
        _save(auth_client, scene["user"], [ev])
        r = _save(auth_client, scene["user"], [dict(ev, note="empty")])
        assert r.get_json()["evaluations"] == []
        assert _count(app, scene["user"], item_type="activities") == 0

    def test_note_empty_sur_evaluation_inexistante_ne_cree_rien(self, auth_client, app, scene):
        r = _save(auth_client, scene["user"], [{"activity_id": scene["act"], "item_id": None,
                                                "item_type": "activities", "eval_number": "rh",
                                                "note": "empty"}])
        assert r.status_code == 200 and r.get_json()["evaluations"] == []
        assert _count(app, scene["user"]) == 0


class TestEvaluationsParUtilisateur:

    def _insert(self, app, scene, created_at):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            db.session.add(CompetencyEvaluation(
                user_id=scene["user"], activity_id=scene["act"], item_id=scene["savoir"],
                item_type="savoirs", eval_number="1", note="green", created_at=created_at))
            db.session.commit()

    def test_sans_entite_active_retourne_les_evaluations(self, auth_client, app, scene):
        self._insert(app, scene, datetime(2026, 1, 2, 3, 4, 5))
        with auth_client.session_transaction() as s:
            s.pop("active_entity_id", None)
        r = auth_client.get(f"/competences/get_user_evaluations_by_user/{scene['user']}")
        assert r.status_code == 200
        assert r.get_json()[0]["created_at"] == "2026-01-02T03:04:05"

    def test_evaluations_filtrees_par_entite_active(self, auth_client, app, scene, ids):
        self._insert(app, scene, datetime(2026, 1, 2))
        _entity(auth_client, ids)
        r = auth_client.get(f"/competences/get_user_evaluations_by_user/{scene['user']}")
        assert [e["item_id"] for e in r.get_json()] == [scene["savoir"]]


class TestRoleStructureEtSynthese:

    def _notes(self, app, scene):
        from Code.extensions import db
        from Code.models.models import CompetencyEvaluation
        with app.app_context():
            db.session.add_all([
                CompetencyEvaluation(user_id=scene["user"], activity_id=scene["act"],
                                     item_id=scene["savoir"], item_type="savoirs",
                                     eval_number="1", note="green"),
                CompetencyEvaluation(user_id=scene["user"], activity_id=scene["act"],
                                     item_id=None, item_type="activities",
                                     eval_number="garant", note="orange"),
                CompetencyEvaluation(user_id=scene["user"], activity_id=scene["act"],
                                     item_id=None, item_type="activities",
                                     eval_number="manager", note="green",
                                     created_at=datetime(2026, 3, 4)),
            ])
            db.session.commit()

    def test_structure_distingue_notes_d_item_et_d_activite(self, auth_client, app, scene, ids):
        self._notes(app, scene)
        _entity(auth_client, ids)
        r = auth_client.get(f"/competences/role_structure/{scene['user']}/{scene['role']}")
        assert r.status_code == 200
        j = r.get_json()
        act = next(a for a in j["activities"] if a["id"] == scene["act"])
        assert act["savoirs"][0]["evals"]["1"]["note"] == "green"
        assert act["savoirs"][0]["evals"]["2"] == {}
        syn = next(s for s in j["synthese"] if s["activity_id"] == scene["act"])
        assert syn["evals"]["garant"]["note"] == "orange"
        assert syn["evals"]["rh"] == {}

    def test_global_summary_utilisateur_inconnu_404(self, auth_client):
        assert auth_client.get("/competences/global_summary/999999").status_code == 404

    def test_global_flat_summary_utilisateur_inconnu_404(self, auth_client):
        assert auth_client.get("/competences/global_flat_summary/999999").status_code == 404

    def test_global_flat_summary_affiche_la_date_de_la_note_manager(self, auth_client, app, scene, ids):
        self._notes(app, scene)
        _entity(auth_client, ids)
        r = auth_client.get(f"/competences/global_flat_summary/{scene['user']}")
        assert r.status_code == 200
        assert "ActGap118" in r.get_data(as_text=True)
        assert "04/03/2026" in r.get_data(as_text=True)
