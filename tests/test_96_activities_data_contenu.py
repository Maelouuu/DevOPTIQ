# tests/test_96_activities_data_contenu.py
"""
Couvre le CONTENU de GET /activities/<id>/details (activities_data.py) :
agrégation des outils, contraintes, compétences, savoirs / savoir-faire /
softskills / aptitudes, et lien sortant sans performance.
Chaque test crée sa propre activité jetable, supprimée en fin de test.
"""
import pytest

pytestmark = pytest.mark.activities_data


@pytest.fixture
def activite_jetable(app, ids):
    from Code.extensions import db
    from Code.models.models import (
        Activities, Task, Tool, Constraint, Competency, Savoir, SavoirFaire,
        Aptitude, Softskill, Link,
    )

    with app.app_context():
        a = Activities(entity_id=ids["entity_id"], name="Activité Détails 96",
                       description="Desc 96")
        db.session.add(a)
        db.session.commit()
        aid = a.id
    yield aid
    with app.app_context():
        for model in (Constraint, Competency, Savoir, SavoirFaire, Aptitude, Softskill):
            model.query.filter_by(activity_id=aid).delete()
        Link.query.filter_by(source_activity_id=aid).delete()
        for t in Task.query.filter_by(activity_id=aid).all():
            t.tools = []
            db.session.delete(t)
        db.session.flush()
        Tool.query.filter(Tool.name.like("Outil96-%")).delete(synchronize_session=False)
        obj = db.session.get(Activities, aid)
        if obj:
            db.session.delete(obj)
        db.session.commit()


class TestDetailsContenu:

    def test_outils_agreges_dedoublonnes_et_tries(self, auth_client, app, ids, activite_jetable):
        from Code.extensions import db
        from Code.models.models import Task, Tool

        with app.app_context():
            tb = Tool(entity_id=ids["entity_id"], name="Outil96-B")
            ta = Tool(entity_id=ids["entity_id"], name="Outil96-A")
            t1 = Task(name="T1", activity_id=activite_jetable, order=1)
            t2 = Task(name="T2", activity_id=activite_jetable, order=2)
            t1.tools = [tb, ta]
            t2.tools = [tb]
            db.session.add_all([tb, ta, t1, t2])
            db.session.commit()
        data = auth_client.get(f"/activities/{activite_jetable}/details").get_json()
        assert sorted(data["tools"]) == ["Outil96-A", "Outil96-B"]
        assert len(data["tools"]) == 2
        assert data["tasks"] == ["T1", "T2"]

    def test_contraintes_et_competences_sont_des_objets_description(
            self, auth_client, app, activite_jetable):
        from Code.extensions import db
        from Code.models.models import Constraint, Competency

        with app.app_context():
            db.session.add_all([
                Constraint(description="Contrainte 96", activity_id=activite_jetable),
                Competency(description="Compétence 96", activity_id=activite_jetable),
            ])
            db.session.commit()
        data = auth_client.get(f"/activities/{activite_jetable}/details").get_json()
        assert data["constraints"] == [{"description": "Contrainte 96"}]
        assert data["competencies"] == [{"description": "Compétence 96"}]

    def test_savoirs_savoir_faires_aptitudes_ordre_par_id(
            self, auth_client, app, activite_jetable):
        from Code.extensions import db
        from Code.models.models import Savoir, SavoirFaire, Aptitude

        with app.app_context():
            for model in (Savoir, SavoirFaire, Aptitude):
                db.session.add(model(description="Premier", activity_id=activite_jetable))
                db.session.flush()
                db.session.add(model(description="Second", activity_id=activite_jetable))
            db.session.commit()
        data = auth_client.get(f"/activities/{activite_jetable}/details").get_json()
        for cle in ("savoirs", "savoir_faires", "aptitudes"):
            assert [i["description"] for i in data[cle]] == ["Premier", "Second"], cle
            assert data[cle][0]["id"] < data[cle][1]["id"], cle
            assert data[cle][0]["name"] is None, cle

    def test_softskill_nom_et_description_viennent_de_habilete(
            self, auth_client, app, activite_jetable):
        from Code.extensions import db
        from Code.models.models import Softskill

        with app.app_context():
            db.session.add(Softskill(habilete="Écoute", niveau="2 (Acquisition)",
                                     activity_id=activite_jetable))
            db.session.commit()
        data = auth_client.get(f"/activities/{activite_jetable}/details").get_json()
        assert len(data["softskills"]) == 1
        item = data["softskills"][0]
        assert item["id"] is not None
        assert item["name"] == "Écoute"
        assert item["description"] == "Écoute"

    def test_lien_sortant_sans_performance_donne_performance_none(
            self, auth_client, app, ids, activite_jetable):
        from Code.extensions import db
        from Code.models.models import Link

        with app.app_context():
            db.session.add(Link(entity_id=ids["entity_id"],
                                source_activity_id=activite_jetable,
                                target_activity_id=ids["activity_id"],
                                type="nourrissante"))
            db.session.commit()
        data = auth_client.get(f"/activities/{activite_jetable}/details").get_json()
        assert data["outgoing"] == [{"performance": None}]

    def test_description_et_nom_de_l_activite(self, auth_client, activite_jetable):
        data = auth_client.get(f"/activities/{activite_jetable}/details").get_json()
        assert data["name"] == "Activité Détails 96"
        assert data["description"] == "Desc 96"
        assert data["tasks"] == [] and data["tools"] == []
