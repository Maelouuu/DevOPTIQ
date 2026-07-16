# tests/test_52_entity_deletion.py
# Régression : supprimer une entité ne doit JAMAIS échouer sur une clé étrangère.
# Bug d'origine (Neon/PostgreSQL) : DELETE activities violait competencies_activity_id_fkey
# car la suppression d'entité ne purgeait pas les tables enfants (competencies, S/SF/HSC,
# évaluations, résultats, domaines, temps…). On vérifie ici que TOUT l'arbre est purgé et
# que le compte propriétaire est seulement DÉTACHÉ (pas supprimé).
import pytest
from werkzeug.security import generate_password_hash
from Code.extensions import db
from Code.models.models import (
    Entity, User, Activities, Task, Tool, Role, Data, Link, Performance,
    Competency, Softskill, Savoir, SavoirFaire, Aptitude, Constraint,
    CompetencyEvaluation, ResultCapabilityLink, ResultDiagnostic,
    TechnicalDomain, ActivityTechnicalDomain, RoleActivityDomainRequirement,
    UserDomainLevel, HscLevelDescriptor, TimeProject, TimeProjectLine,
    TimeRoleAnalysis, TimeRoleLine, TimeWeakness, TimeAnalysis, CartoCalque,
    CrossCartoLiaison, UserRole, activity_roles, task_roles, task_tools,
)


@pytest.fixture()
def seeded_entity(app):
    """Entité dédiée avec un exemplaire de CHAQUE table enfant liée à l'entité, ses
    activités, rôles, données, liens, tâches, outils et domaines."""
    with app.app_context():
        owner = User(first_name="Del", last_name="Owner", email="del.owner@t.com",
                     password=generate_password_hash("x"), status="admin")
        db.session.add(owner); db.session.flush()
        ent = Entity(name="EntityToDelete", owner_id=owner.id)
        db.session.add(ent); db.session.flush()
        owner.entity_id = ent.id

        a1 = Activities(entity_id=ent.id, name="A1")
        a2 = Activities(entity_id=ent.id, name="A2")
        db.session.add_all([a1, a2]); db.session.flush()
        tk = Task(name="T", activity_id=a1.id, order=1); db.session.add(tk)
        tl = Tool(entity_id=ent.id, name="Tool1"); db.session.add(tl)
        r = Role(entity_id=ent.id, name="R1"); db.session.add(r); db.session.flush()
        d1 = Data(entity_id=ent.id, name="D1", type="flux")
        d2 = Data(entity_id=ent.id, name="D2", type="flux", producer_activity_id=a1.id)
        db.session.add_all([d1, d2]); db.session.flush()
        lk = Link(entity_id=ent.id, source_activity_id=a1.id, target_activity_id=a2.id, type="flux")
        lk2 = Link(entity_id=ent.id, source_data_id=d1.id, target_activity_id=a2.id, type="nourrissante")
        db.session.add_all([lk, lk2]); db.session.flush()
        db.session.add(Performance(name="P", link_id=lk.id))
        db.session.execute(task_tools.insert().values(task_id=tk.id, tool_id=tl.id))
        db.session.execute(activity_roles.insert().values(activity_id=a1.id, role_id=r.id, status="active"))
        db.session.execute(task_roles.insert().values(task_id=tk.id, role_id=r.id, status="active"))
        db.session.add(UserRole(user_id=owner.id, role_id=r.id))
        for M in (Competency, Savoir, SavoirFaire, Aptitude, Constraint):
            db.session.add(M(description="x", activity_id=a1.id))
        db.session.add(Softskill(habilete="H", niveau="1", activity_id=a1.id))
        db.session.add(CompetencyEvaluation(user_id=owner.id, activity_id=a1.id,
                                            eval_number="2", note="", item_type="activity_results", item_id=d2.id))
        db.session.add(ResultCapabilityLink(entity_id=ent.id, activity_id=a1.id, data_id=d2.id,
                                            item_type="SAVOIR", item_id=1))
        db.session.add(ResultDiagnostic(entity_id=ent.id, user_id=owner.id, activity_id=a1.id, data_id=d2.id))
        dom = TechnicalDomain(entity_id=ent.id, name_fr="Plastique"); db.session.add(dom); db.session.flush()
        db.session.add(ActivityTechnicalDomain(activity_id=a1.id, domain_id=dom.id))
        db.session.add(RoleActivityDomainRequirement(role_id=r.id, activity_id=a1.id, domain_id=dom.id, required_level=2))
        db.session.add(UserDomainLevel(user_id=owner.id, domain_id=dom.id, demonstrated_level=1))
        db.session.add(HscLevelDescriptor(entity_id=ent.id, hsc_name="Rigueur", level=1))
        tp = TimeProject(entity_id=ent.id, name="TP"); db.session.add(tp); db.session.flush()
        db.session.add(TimeProjectLine(project_id=tp.id, activity_id=a1.id))
        tra = TimeRoleAnalysis(role_id=r.id); db.session.add(tra); db.session.flush()
        db.session.add(TimeRoleLine(role_analysis_id=tra.id, activity_id=a1.id, recurrence="daily"))
        db.session.add(TimeWeakness(activity_id=a1.id, task_id=tk.id, recurrence="daily"))
        db.session.add(TimeAnalysis(duration=10, recurrence="daily", frequency=1, type="task",
                                    activity_id=a1.id, task_id=tk.id, role_id=r.id))
        db.session.add(CartoCalque(entity_id=ent.id, name="C", state_json="{}"))
        db.session.add(CrossCartoLiaison(extco_entity_id=ent.id, extco_activity_id=a1.id,
                                         origin_entity_id=ent.id, origin_activity_id=a2.id))
        db.session.commit()
        ids = {"entity_id": ent.id, "owner_id": owner.id, "a1": a1.id, "a2": a2.id,
               "role_id": r.id, "dom_id": dom.id, "d2": d2.id, "link_id": lk.id, "task_id": tk.id}
    yield ids
    # Nettoyage de secours si le test échoue avant la suppression
    with app.app_context():
        if Entity.query.get(ids["entity_id"]):
            User.query.filter_by(id=ids["owner_id"]).delete()
            db.session.commit()


def test_delete_entity_never_fails_on_fk(app, client, seeded_entity):
    ids = seeded_entity
    with client.session_transaction() as s:
        s["user_id"] = ids["owner_id"]
    r = client.delete(f"/activities/api/entities/{ids['entity_id']}")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json().get("status") == "ok"

    with app.app_context():
        # L'entité et tout son arbre ont disparu
        assert Entity.query.get(ids["entity_id"]) is None
        assert Activities.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        for M in (Competency, Softskill, Savoir, SavoirFaire, Aptitude, Constraint):
            assert M.query.filter_by(activity_id=ids["a1"]).count() == 0, M.__name__
        assert CompetencyEvaluation.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert ResultCapabilityLink.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert ResultDiagnostic.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert ActivityTechnicalDomain.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert RoleActivityDomainRequirement.query.filter_by(role_id=ids["role_id"]).count() == 0
        assert UserDomainLevel.query.filter_by(domain_id=ids["dom_id"]).count() == 0
        assert TechnicalDomain.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert HscLevelDescriptor.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert Data.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert Link.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert Performance.query.filter_by(link_id=ids["link_id"]).count() == 0
        assert Task.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert Tool.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert Role.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert UserRole.query.filter_by(role_id=ids["role_id"]).count() == 0
        assert TimeProject.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert TimeProjectLine.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert TimeRoleLine.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert TimeWeakness.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert TimeAnalysis.query.filter_by(activity_id=ids["a1"]).count() == 0
        assert CartoCalque.query.filter_by(entity_id=ids["entity_id"]).count() == 0
        assert CrossCartoLiaison.query.filter_by(origin_entity_id=ids["entity_id"]).count() == 0
        # Le compte propriétaire est CONSERVÉ, seulement détaché de l'entité
        owner = User.query.get(ids["owner_id"])
        assert owner is not None and owner.entity_id is None
        # Nettoyage
        db.session.delete(owner); db.session.commit()
