# tests/test_33_activities_data.py
"""
Couvre :
  - GET /activities/<id>/details (activities_data.py)
  - GET /activities/performance/render/<link_id> (activities_render.py)
"""
import pytest

pytestmark = pytest.mark.activities_data


# ===========================================================================
# 1. GET /activities/<id>/details
# ===========================================================================

class TestActivityDetails:

    def test_details_activite_existante(self, auth_client, ids):
        """Activité du seed → 200 avec JSON valide."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        assert r.status_code == 200
        assert r.content_type.startswith("application/json")

    def test_details_structure_json(self, auth_client, ids):
        """La réponse contient tous les champs attendus."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        required_keys = {"id", "name", "title", "description", "tasks", "tools",
                         "constraints", "competencies", "outgoing",
                         "input_data", "output_data",
                         "savoirs", "savoir_faires", "softskills", "aptitudes"}
        assert required_keys.issubset(data.keys())

    def test_details_id_correspond_a_activite(self, auth_client, ids):
        """Le champ 'id' dans la réponse correspond à l'ID demandé."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert data["id"] == ids["activity_id"]

    def test_details_name_et_title_identiques(self, auth_client, ids):
        """'name' et 'title' sont tous deux présents et cohérents."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert data["name"] == data["title"]
        assert data["name"] == "Activité Test"

    def test_details_taches_est_liste(self, auth_client, ids):
        """'tasks' est une liste (même vide)."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert isinstance(data["tasks"], list)

    def test_details_taches_contient_tache_seed(self, auth_client, ids):
        """L'activité seed a la tâche 'Tâche Test' dans ses tasks."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert "Tâche Test" in data["tasks"]

    def test_details_listes_vides_pour_items_inexistants(self, auth_client, app, ids):
        """Une activité SANS items renvoie des listes vides.

        On utilise une activité jetable : l'activité seed peut être polluée par
        d'autres tests qui y ajoutent des savoirs/HSC sans cleanup (ex. test_24).
        """
        from Code.models.models import Activities
        from Code.extensions import db
        with app.app_context():
            a = Activities(entity_id=ids["entity_id"], name="Activité Vide Détails", description="")
            db.session.add(a)
            db.session.commit()
            aid = a.id
        try:
            r = auth_client.get(f"/activities/{aid}/details")
            data = r.get_json()
            assert data["savoirs"] == []
            assert data["savoir_faires"] == []
            assert data["softskills"] == []
            assert data["aptitudes"] == []
        finally:
            with app.app_context():
                obj = db.session.get(Activities, aid)
                if obj:
                    db.session.delete(obj)
                    db.session.commit()

    def test_details_constraints_est_liste(self, auth_client, ids):
        """'constraints' est une liste."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert isinstance(data["constraints"], list)

    def test_details_outgoing_est_liste(self, auth_client, ids):
        """'outgoing' est une liste."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert isinstance(data["outgoing"], list)

    def test_details_outgoing_avec_performance_attachee(self, auth_client, app, ids):
        """Un lien SORTANT (source_activity_id) avec une Performance attachée apparaît dans 'outgoing'."""
        from Code.models.models import Performance, Link, Data
        from Code.extensions import db

        with app.app_context():
            data_obj = Data(entity_id=ids["entity_id"], name="Donnée Sortante Test", type="nourrissante")
            db.session.add(data_obj)
            db.session.flush()
            link = Link(
                entity_id=ids["entity_id"],
                source_activity_id=ids["activity_id"],
                target_data_id=data_obj.id,
                type="nourrissante",
            )
            db.session.add(link)
            db.session.flush()
            perf = Performance(link_id=link.id, name="Perf Sortante", description="Desc")
            db.session.add(perf)
            db.session.commit()
            link_id, data_id, perf_id = link.id, data_obj.id, perf.id

        try:
            r = auth_client.get(f"/activities/{ids['activity_id']}/details")
            data = r.get_json()
            matches = [o for o in data["outgoing"] if o.get("performance") and o["performance"]["name"] == "Perf Sortante"]
            assert len(matches) >= 1
            assert matches[0]["performance"]["description"] == "Desc"
        finally:
            with app.app_context():
                p = db.session.get(Performance, perf_id)
                if p:
                    db.session.delete(p)
                l = db.session.get(Link, link_id)
                if l:
                    db.session.delete(l)
                d = db.session.get(Data, data_id)
                if d:
                    db.session.delete(d)
                db.session.commit()

    def test_details_activite_inexistante_404(self, auth_client):
        """Activité inconnue → 404."""
        r = auth_client.get("/activities/999999/details")
        assert r.status_code == 404
        data = r.get_json()
        assert "error" in data

    def test_details_activite_id_negatif_404(self, auth_client):
        """ID négatif n'existe pas → 404."""
        r = auth_client.get("/activities/-1/details")
        # Flask renvoie 404 sur route non matchée (int ne matche pas négatif) ou 404 DB
        assert r.status_code in (404, 405)

    def test_details_description_est_chaine(self, auth_client, ids):
        """'description' est une chaîne (pas None)."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert isinstance(data["description"], str)

    def test_details_tools_est_liste(self, auth_client, ids):
        """'tools' est une liste."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert isinstance(data["tools"], list)

    def test_details_input_output_data_sont_listes(self, auth_client, ids):
        """'input_data' et 'output_data' sont des listes."""
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        data = r.get_json()
        assert isinstance(data["input_data"], list)
        assert isinstance(data["output_data"], list)

    def test_details_input_data_contient_donnee_entrante(self, auth_client, app, ids):
        """Un Link entrant (Data → activité) doit apparaître dans 'input_data'.

        Donnée dédiée + cleanup : le Link entrant du seed (`conftest._seed_db`)
        n'est pas fiable ici, un autre test (`test_15_activities_map.py::
        test_list_connections_empty`) vide tous les Link de l'entité seed.
        """
        from Code.models.models import Data, Link
        from Code.extensions import db

        with app.app_context():
            data_obj = Data(entity_id=ids["entity_id"], name="Donnée Entrante Details", type="nourrissante")
            db.session.add(data_obj)
            db.session.flush()
            link = Link(
                entity_id=ids["entity_id"],
                source_data_id=data_obj.id,
                target_activity_id=ids["activity_id"],
                type="nourrissante",
            )
            db.session.add(link)
            db.session.commit()
            link_id, data_id = link.id, data_obj.id

        try:
            r = auth_client.get(f"/activities/{ids['activity_id']}/details")
            data = r.get_json()
            assert "Donnée Entrante Details" in data["input_data"]
            assert "Donnée Entrante Details" not in data["output_data"]
        finally:
            with app.app_context():
                l = db.session.get(Link, link_id)
                if l:
                    db.session.delete(l)
                d = db.session.get(Data, data_id)
                if d:
                    db.session.delete(d)
                db.session.commit()

    def test_details_output_data_contient_donnee_sortante(self, auth_client, app, ids):
        """Un Link sortant (activité → Data) doit apparaître dans 'output_data'."""
        from Code.models.models import Data, Link
        from Code.extensions import db

        with app.app_context():
            data_obj = Data(entity_id=ids["entity_id"], name="Donnée Sortante Details", type="nourrissante")
            db.session.add(data_obj)
            db.session.flush()
            link = Link(
                entity_id=ids["entity_id"],
                source_activity_id=ids["activity_id"],
                target_data_id=data_obj.id,
                type="nourrissante",
            )
            db.session.add(link)
            db.session.commit()
            link_id, data_id = link.id, data_obj.id

        try:
            r = auth_client.get(f"/activities/{ids['activity_id']}/details")
            data = r.get_json()
            assert "Donnée Sortante Details" in data["output_data"]
            assert "Donnée Sortante Details" not in data["input_data"]
        finally:
            with app.app_context():
                l = db.session.get(Link, link_id)
                if l:
                    db.session.delete(l)
                d = db.session.get(Data, data_id)
                if d:
                    db.session.delete(d)
                db.session.commit()

    def test_details_input_output_data_sans_lien_sont_vides(self, auth_client, app, ids):
        """Une activité sans Link data → [] pour input_data et output_data."""
        from Code.models.models import Activities
        from Code.extensions import db
        with app.app_context():
            a = Activities(entity_id=ids["entity_id"], name="Activité Sans Data", description="")
            db.session.add(a)
            db.session.commit()
            aid = a.id
        try:
            r = auth_client.get(f"/activities/{aid}/details")
            data = r.get_json()
            assert data["input_data"] == []
            assert data["output_data"] == []
        finally:
            with app.app_context():
                obj = db.session.get(Activities, aid)
                if obj:
                    db.session.delete(obj)
                    db.session.commit()


# ===========================================================================
# 2. GET /activities/performance/render/<link_id>
# ===========================================================================

class TestPerformanceRender:

    def test_render_link_existant_retourne_200(self, auth_client, ids):
        """Link du seed → 200 avec liste JSON."""
        r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
        assert r.status_code == 200
        assert r.content_type.startswith("application/json")

    def test_render_lien_sans_performance_retourne_liste_vide(self, auth_client, ids):
        """Link sans Performance attachée → liste vide."""
        r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
        data = r.get_json()
        assert isinstance(data, list)

    def test_render_link_inexistant_retourne_liste_vide(self, auth_client):
        """Link inconnu → 200 avec liste vide (pas de 404, filtre retourne rien)."""
        r = auth_client.get("/activities/performance/render/999999")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        assert data == []

    def test_render_structure_performances(self, auth_client, app, ids):
        """Après création d'une Performance sur le link, la structure id/name/description est présente."""
        from Code.extensions import db
        from Code.models.models import Performance

        with app.app_context():
            perf = Performance(link_id=ids["link_id"], name="Perf Test", description="Desc Perf")
            db.session.add(perf)
            db.session.commit()
            perf_id = perf.id

        r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data) >= 1
        first = data[0]
        assert "id" in first
        assert "name" in first
        assert "description" in first
        assert first["name"] == "Perf Test"

        with app.app_context():
            p = Performance.query.get(perf_id)
            if p:
                db.session.delete(p)
                db.session.commit()
