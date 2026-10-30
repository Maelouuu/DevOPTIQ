# tests/test_125_competences_items_gaps.py
"""Compétences — structure de rôle avec savoir-faire / HSC notés, mise à jour d'une note
d'item existante sans doublon, et liste de managers vide sans rôle dédié."""
import json
import pytest

pytestmark = pytest.mark.competences


@pytest.fixture()
def scene(app, ids):
    """Rôle + utilisateur + activité (savoir-faire et HSC) reliés. Tout est nettoyé."""
    from Code.extensions import db
    from Code.models.models import (Role, User, UserRole, Activities, SavoirFaire, Softskill,
                                    CompetencyEvaluation, activity_roles)
    from werkzeug.security import generate_password_hash
    with app.app_context():
        role = Role(name="RoleGap125", entity_id=ids["entity_id"])
        user = User(entity_id=ids["entity_id"], first_name="Gap", last_name="Cent25",
                    email="gap125@test.local", password=generate_password_hash("Pass123!"),
                    status="user")
        act = Activities(entity_id=ids["entity_id"], name="ActGap125", shape_id="gap125")
        db.session.add_all([role, user, act]); db.session.flush()
        sf = SavoirFaire(activity_id=act.id, description="SF gap 125")
        hsc = Softskill(activity_id=act.id, habilete="HSC gap 125", niveau="2 (Acquisition)")
        db.session.add_all([sf, hsc]); db.session.flush()
        db.session.add(UserRole(user_id=user.id, role_id=role.id))
        db.session.execute(activity_roles.insert().values(
            activity_id=act.id, role_id=role.id, status="active"))
        db.session.commit()
        d = {"role": role.id, "user": user.id, "act": act.id, "sf": sf.id, "hsc": hsc.id}
    yield d
    with app.app_context():
        CompetencyEvaluation.query.filter_by(user_id=d["user"]).delete()
        db.session.execute(activity_roles.delete().where(activity_roles.c.role_id == d["role"]))
        UserRole.query.filter_by(user_id=d["user"]).delete()
        SavoirFaire.query.filter_by(id=d["sf"]).delete()
        Softskill.query.filter_by(id=d["hsc"]).delete()
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


class TestCompetencesItems:

    def test_structure_expose_les_notes_des_savoir_faires_et_hsc(self, auth_client, scene, ids):
        _entity(auth_client, ids)
        for item_id, typ, num, note in [(scene["sf"], "savoir_faires", "2", "orange"),
                                        (scene["hsc"], "softskills", "3", "red")]:
            ev = {"activity_id": scene["act"], "item_id": item_id, "item_type": typ,
                  "eval_number": num, "note": note}
            assert _save(auth_client, scene["user"], [ev]).status_code == 200
        r = auth_client.get(f"/competences/role_structure/{scene['user']}/{scene['role']}")
        assert r.status_code == 200
        act = next(a for a in r.get_json()["activities"] if a["id"] == scene["act"])
        assert act["savoir_faires"][0]["evals"]["2"]["note"] == "orange"
        assert act["savoir_faires"][0]["evals"]["1"] == {}
        assert act["hsc"][0]["description"] == "HSC gap 125"
        assert act["hsc"][0]["niveau"] == "2 (Acquisition)"
        assert act["hsc"][0]["evals"]["3"]["note"] == "red"

    def test_note_d_item_existante_est_mise_a_jour_sans_doublon(self, auth_client, app, scene):
        from Code.models.models import CompetencyEvaluation
        ev = {"activity_id": scene["act"], "item_id": scene["sf"], "item_type": "savoir_faires",
              "eval_number": "1", "note": "green"}
        _save(auth_client, scene["user"], [ev])
        r = _save(auth_client, scene["user"], [dict(ev, note="red")])
        assert r.get_json()["evaluations"][0]["note"] == "red"
        with app.app_context():
            rows = CompetencyEvaluation.query.filter_by(
                user_id=scene["user"], item_id=scene["sf"]).all()
            assert [x.note for x in rows] == ["red"]

    def test_note_empty_supprime_la_note_d_un_item(self, auth_client, app, scene):
        from Code.models.models import CompetencyEvaluation
        ev = {"activity_id": scene["act"], "item_id": scene["hsc"], "item_type": "softskills",
              "eval_number": "1", "note": "orange"}
        _save(auth_client, scene["user"], [ev])
        r = _save(auth_client, scene["user"], [dict(ev, note="empty")])
        assert r.get_json()["evaluations"] == []
        with app.app_context():
            assert CompetencyEvaluation.query.filter_by(user_id=scene["user"]).count() == 0

    def test_structure_role_inconnu_404(self, auth_client, scene):
        assert auth_client.get(f"/competences/role_structure/{scene['user']}/999999").status_code == 404

    def test_structure_utilisateur_inconnu_404(self, auth_client, scene):
        assert auth_client.get(f"/competences/role_structure/999999/{scene['role']}").status_code == 404
