# tests/test_120_qualify_outputs_gaps.py
# Trous de couverture de qualify_outputs : 404, flèches vers Data, repli sans nom,
# sortie orpheline conservée, calcul en bloc, validation de /save.
import pytest
from Code.extensions import db
from Code.models.models import Entity, Activities, Link, Data
from Code.routes.qualify_outputs import (
    output_ids_en_bloc, materialize_activity_outputs, _current_output_specs,
    _destinataires, porte_du_travail,
)


@pytest.fixture()
def monde(app):
    with app.app_context():
        ent = Entity(name="QualifGapsEnt")
        db.session.add(ent); db.session.flush()
        a = Activities(entity_id=ent.id, name="Source gaps", shape_id="qg_a")
        b = Activities(entity_id=ent.id, name="Cible gaps", shape_id="qg_b")
        db.session.add_all([a, b]); db.session.flush()
        d_cible = Data(entity_id=ent.id, name="Donnée visée", type="flux")
        db.session.add(d_cible); db.session.commit()
        ids = {"ent": ent.id, "a": a.id, "b": b.id, "d": d_cible.id}
    yield ids
    with app.app_context():
        Data.query.filter(Data.producer_activity_id.in_([ids["a"], ids["b"]])).delete(
            synchronize_session=False)
        Link.query.filter(Link.source_activity_id.in_([ids["a"], ids["b"]])).delete(
            synchronize_session=False)
        Data.query.filter_by(id=ids["d"]).delete()
        Activities.query.filter(Activities.id.in_([ids["a"], ids["b"]])).delete(
            synchronize_session=False)
        Entity.query.filter_by(id=ids["ent"]).delete()
        db.session.commit()


def _lien(m, **kw):
    db.session.add(Link(entity_id=m["ent"], source_activity_id=m["a"], type="flux", **kw))
    db.session.commit()


def _sess(client, ent):
    with client.session_transaction() as s:
        s["active_entity_id"] = ent
        s["lang"] = "fr"


class TestQualifyOutputsGaps:
    def test_outputs_activite_inexistante_404(self, client, monde):
        _sess(client, monde["ent"])
        r = client.get("/qualify/outputs/999999")
        assert r.status_code == 404
        assert r.get_json()["error"] == "activity_not_found"

    def test_analyze_activite_inexistante_404(self, client, monde):
        _sess(client, monde["ent"])
        assert client.post("/qualify/analyze/999999").status_code == 404

    def test_save_activite_inexistante_404(self, client, monde):
        _sess(client, monde["ent"])
        r = client.post("/qualify/save/999999", json={"outputs": []})
        assert r.status_code == 404

    def test_materialize_activite_inexistante_liste_vide(self, app):
        with app.app_context():
            assert materialize_activity_outputs(999999) == []

    def test_fleche_vers_data_nest_pas_materialisee(self, app, monde):
        with app.app_context():
            _lien(monde, target_data_id=monde["d"], description="Vers donnée")
            a = db.session.get(Activities, monde["a"])
            assert _current_output_specs(a) == []

    def test_fleche_sans_libelle_ni_cible_ignoree(self, app, monde):
        with app.app_context():
            _lien(monde, description="   ")
            a = db.session.get(Activities, monde["a"])
            assert _current_output_specs(a) == []
            assert _destinataires(a) == {}

    def test_destinataire_data_utilise_nom_de_la_data(self, app, monde):
        with app.app_context():
            _lien(monde, target_data_id=monde["d"], description="Étiquette")
            a = db.session.get(Activities, monde["a"])
            assert _destinataires(a) == {"étiquette": "Donnée visée"}

    def test_outputs_inclut_data_visee_heritage(self, client, app, monde):
        with app.app_context():
            _lien(monde, target_data_id=monde["d"], description="Étiquette")
        _sess(client, monde["ent"])
        outs = client.get(f"/qualify/outputs/{monde['a']}").get_json()["outputs"]
        assert [o["id"] if "id" in o else o.get("data_id") for o in outs] == [monde["d"]]
        assert outs[0]["vers"] is None

    def test_sortie_orpheline_qualifiee_est_conservee(self, app, monde):
        with app.app_context():
            d = Data(entity_id=monde["ent"], name="Orpheline", type="flux",
                     producer_activity_id=monde["a"], minimum_performance_text="Au moins 2")
            db.session.add(d); db.session.commit()
            noms = [o.name for o in materialize_activity_outputs(monde["a"])]
            assert noms == ["Orpheline"]

    def test_sortie_orpheline_vierge_n_est_pas_conservee(self, app, monde):
        with app.app_context():
            d = Data(entity_id=monde["ent"], name="Vide", type="flux",
                     producer_activity_id=monde["a"])
            db.session.add(d); db.session.commit()
            assert materialize_activity_outputs(monde["a"]) == []

    def test_porte_du_travail_texte_blanc_est_faux(self, app):
        d = Data(name="x", type="flux", minimum_performance_text="   ")
        assert porte_du_travail(d) is False

    def test_en_bloc_liste_vide(self, app):
        with app.app_context():
            assert output_ids_en_bloc([]) == {}
            assert output_ids_en_bloc(None) == {}

    def test_en_bloc_nom_depuis_activite_cible_et_dedoublonnage(self, app, monde):
        with app.app_context():
            _lien(monde, target_activity_id=monde["b"])
            _lien(monde, target_activity_id=monde["b"], description="cible gaps")
            _lien(monde, description="")
            d = Data(entity_id=monde["ent"], name="Cible gaps", type="flux",
                     producer_activity_id=monde["a"])
            db.session.add(d); db.session.commit()
            res = output_ids_en_bloc([monde["a"], monde["b"]])
            assert res[monde["a"]] == {d.id}
            assert res[monde["b"]] == set()

    def test_en_bloc_orpheline_travaillee_et_heritage(self, app, monde):
        with app.app_context():
            _lien(monde, target_data_id=monde["d"])
            o = Data(entity_id=monde["ent"], name="Ancienne", type="flux",
                     producer_activity_id=monde["a"], semantic_nature="RESULT")
            db.session.add(o); db.session.commit()
            res = output_ids_en_bloc([monde["a"]])
            assert res[monde["a"]] == {o.id, monde["d"]}

    def test_save_ignore_id_etranger_et_nature_invalide(self, client, app, monde):
        with app.app_context():
            _lien(monde, target_activity_id=monde["b"], description="Livrable")
        _sess(client, monde["ent"])
        did = client.get(f"/qualify/outputs/{monde['a']}").get_json()["outputs"][0]
        did = did.get("id", did.get("data_id"))
        r = client.post(f"/qualify/save/{monde['a']}", json={"outputs": [
            {"data_id": did, "nature": "N_IMPORTE_QUOI", "minimum_performance_text": "  "},
            {"data_id": 987654, "nature": "RESULT"},
        ]})
        assert r.status_code == 200
        j = r.get_json()
        assert j["saved"] == 1
        with app.app_context():
            d = db.session.get(Data, did)
            assert d.semantic_nature is None
            assert d.minimum_performance_text is None
            assert d.qualification_source is None

    def test_save_requalifier_un_result_avertit(self, client, app, monde):
        with app.app_context():
            _lien(monde, target_activity_id=monde["b"], description="Livrable")
        _sess(client, monde["ent"])
        did = client.get(f"/qualify/outputs/{monde['a']}").get_json()["outputs"][0]
        did = did.get("id", did.get("data_id"))
        client.post(f"/qualify/save/{monde['a']}", json={"outputs": [
            {"data_id": did, "nature": "RESULT", "source": "MANUAL"}]})
        r = client.post(f"/qualify/save/{monde['a']}", json={"outputs": [
            {"data_id": did, "nature": "MEASURE"}]})
        j = r.get_json()
        assert [w["data_id"] for w in j["warnings"]] == [did]
        with app.app_context():
            assert db.session.get(Data, did).qualification_source == "AI"

    def test_save_sans_outputs_enregistre_zero(self, client, monde):
        _sess(client, monde["ent"])
        r = client.post(f"/qualify/save/{monde['a']}", json={})
        assert r.get_json()["saved"] == 0
