# tests/test_117_activities_view_liens_gaps.py
"""
Module : activities_view.py — résolution des noms de liens dans _build_activity_data
Chaque test crée ses propres activités/liens et les supprime : aucune dépendance
à l'ordre d'exécution ni au seed partagé.
"""
import pytest

pytestmark = pytest.mark.activities_view


@pytest.fixture
def scene(app, ids):
    """Deux activités jetables + une donnée, nettoyées après le test."""
    from Code.extensions import db
    from Code.models.models import Activities, Data, Link

    created = {"links": [], "acts": [], "data": []}
    with app.app_context():
        a = Activities(entity_id=ids["entity_id"], name="LiensGap Source")
        b = Activities(entity_id=ids["entity_id"], name="LiensGap Cible")
        d = Data(entity_id=ids["entity_id"], name="LiensGap Donnée", type="nourrissante")
        db.session.add_all([a, b, d])
        db.session.commit()
        created["acts"] = [a.id, b.id]
        created["data"] = [d.id]
        created["a"], created["b"], created["d"] = a.id, b.id, d.id

    def add_link(**kw):
        with app.app_context():
            lk = Link(entity_id=ids["entity_id"], type=kw.pop("type", "nourrissante"), **kw)
            db.session.add(lk)
            db.session.commit()
            created["links"].append(lk.id)
            return lk.id

    created["add_link"] = add_link
    yield created

    with app.app_context():
        Link.query.filter(Link.id.in_(created["links"])).delete(synchronize_session=False)
        Data.query.filter(Data.id.in_(created["data"])).delete(synchronize_session=False)
        Activities.query.filter(Activities.id.in_(created["acts"])).delete(synchronize_session=False)
        db.session.commit()


def _build(app, act_id):
    from Code.models.models import Activities
    from Code.routes.activities_view import _build_activity_data
    with app.test_request_context():
        return _build_activity_data([Activities.query.get(act_id)])[0]


class TestResolutionNomsLiens:

    def test_source_activite_hors_page_est_resolue_par_son_nom(self, app, scene):
        """Un lien entrant dont la source est une autre activité affiche son nom."""
        scene["add_link"](source_activity_id=scene["a"], target_activity_id=scene["b"])
        data = _build(app, scene["b"])
        assert [c["source_name"] for c in data["incoming"]] == ["LiensGap Source"]

    def test_cible_activite_hors_page_est_resolue_par_son_nom(self, app, scene):
        """Un lien sortant vers une autre activité affiche le nom de la cible."""
        scene["add_link"](source_activity_id=scene["a"], target_activity_id=scene["b"])
        data = _build(app, scene["a"])
        assert [c["target_name"] for c in data["outgoing"]] == ["LiensGap Cible"]

    def test_donnee_source_donne_son_nom_de_flux(self, app, scene):
        """Un lien entrant issu d'une donnée expose le nom de cette donnée."""
        scene["add_link"](source_data_id=scene["d"], target_activity_id=scene["a"])
        data = _build(app, scene["a"])
        assert data["incoming"][0]["data_name"] == "LiensGap Donnée"
        assert data["incoming"][0]["source_name"] == "LiensGap Donnée"

    def test_donnee_cible_donne_son_nom_de_cible(self, app, scene):
        """Un lien sortant vers une donnée expose son nom comme cible."""
        scene["add_link"](source_activity_id=scene["a"], target_data_id=scene["d"])
        data = _build(app, scene["a"])
        assert data["outgoing"][0]["target_name"] == "LiensGap Donnée"

    def test_source_inconnue_sans_label(self, app, scene):
        """Sans source ni label cross-carto, la source vaut « [Source ?] »."""
        scene["add_link"](target_activity_id=scene["a"], description="note libre")
        data = _build(app, scene["a"])
        assert data["incoming"][0]["source_name"] == "[Source ?]"
        assert data["incoming"][0]["data_name"] == "note libre"

    def test_cible_inconnue_sans_label(self, app, scene):
        """Sans cible ni label cross-carto, la cible vaut « [Cible ?] »."""
        scene["add_link"](source_activity_id=scene["a"])
        data = _build(app, scene["a"])
        assert data["outgoing"][0]["target_name"] == "[Cible ?]"
        assert data["outgoing"][0]["data_name"] == "[Data inconnue]"

    def test_flux_cross_carto_entrant(self, app, scene):
        """Un lien cross-carto entrant : source préfixée du label, flux « externe »."""
        scene["add_link"](target_activity_id=scene["a"], cross_carto_label="Carto2",
                          description="Dossier")
        data = _build(app, scene["a"])
        assert data["incoming"][0]["source_name"] == "[Carto2] Dossier"
        assert data["incoming"][0]["data_name"] == "Flux externe"
        assert data["incoming"][0]["cross_carto_label"] == "Carto2"

    def test_flux_cross_carto_sortant(self, app, scene):
        """Un lien cross-carto sortant : cible préfixée du label."""
        scene["add_link"](source_activity_id=scene["a"], cross_carto_label="Carto2",
                          description="Retour")
        data = _build(app, scene["a"])
        assert data["outgoing"][0]["target_name"] == "[Carto2] Retour"

    def test_id_de_donnee_orphelin_nomme_sans_planter(self, app, scene):
        """Une donnée disparue n'empêche pas la construction : description en repli."""
        from Code.extensions import db
        from Code.models.models import Data
        lid = scene["add_link"](source_data_id=scene["d"], target_activity_id=scene["a"],
                                description="repli")
        with app.app_context():
            Data.query.filter_by(id=scene["d"]).delete()
            db.session.commit()
        scene["data"].clear()
        with app.app_context():
            from Code.models.models import Link
            Link.query.filter_by(id=lid).update({"source_data_id": 987654}, synchronize_session=False)
            db.session.commit()
        data = _build(app, scene["a"])
        assert data["incoming"][0]["data_name"] == "repli"
        assert data["incoming"][0]["source_name"] == "[Data inconnue]"
