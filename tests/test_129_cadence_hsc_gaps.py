# tests/test_129_cadence_hsc_gaps.py
"""
Compléments Cadences (/cadence) et descripteurs HSC (/hsc) :
  - détails de cadence vides, cadence spéciale ignorée par l'analyse, libellés EN
  - descripteurs globaux (entité NULL), isolation entre entités, repli EN → FR
"""
import json
import pytest

pytestmark = pytest.mark.cadence


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _lang(client, lang):
    with client.session_transaction() as sess:
        sess["lang"] = lang


@pytest.fixture
def activite(app, ids):
    from Code.models.models import Activities
    from Code.extensions import db
    with app.app_context():
        a = Activities(entity_id=ids["entity_id"], name="Activité Gap129", description="")
        db.session.add(a)
        db.session.commit()
        aid = a.id
    yield aid
    with app.app_context():
        a = db.session.get(Activities, aid)
        if a:
            db.session.delete(a)
            db.session.commit()


@pytest.fixture
def donnee_liee(app, ids, activite):
    from Code.models.models import Data, Link
    from Code.extensions import db
    with app.app_context():
        d = Data(entity_id=ids["entity_id"], name="Donnée Gap129", type="nourrissante")
        db.session.add(d)
        db.session.commit()
        lk = Link(entity_id=ids["entity_id"], source_data_id=d.id,
                  target_activity_id=activite, type="nourrissante")
        db.session.add(lk)
        db.session.commit()
        did, lid = d.id, lk.id
    yield did
    with app.app_context():
        for model, i in ((Link, lid), (Data, did)):
            o = db.session.get(model, i)
            if o:
                db.session.delete(o)
        db.session.commit()


class TestCadenceGaps:

    def test_details_blancs_stockes_a_null(self, auth_client, app, activite):
        r = _post(auth_client, f"/cadence/activity/{activite}",
                  {"cadence_code": "DAILY", "cadence_details": "   "})
        assert r.status_code == 200
        with app.app_context():
            from Code.models.models import Activities
            a = Activities.query.get(activite)
            assert a.cadence_code == "DAILY"
            assert a.cadence_details is None

    def test_code_invalide_ne_modifie_pas_l_activite(self, auth_client, app, activite):
        _post(auth_client, f"/cadence/activity/{activite}", {"cadence_code": "WEEKLY"})
        r = _post(auth_client, f"/cadence/activity/{activite}", {"cadence_code": "NOPE"})
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid_code"
        with app.app_context():
            from Code.models.models import Activities
            assert Activities.query.get(activite).cadence_code == "WEEKLY"

    def test_codes_libelles_en_anglais(self, auth_client):
        _lang(auth_client, "en")
        try:
            d = {c["code"]: c for c in auth_client.get("/cadence/codes").get_json()["cadences"]}
            assert d["DAILY"]["label"] == "Daily"
            assert d["EVENT"]["badge"] == "E"
            assert len(d) == 9
        finally:
            _lang(auth_client, "fr")

    def test_cadence_speciale_ignoree_par_l_analyse(self, auth_client, app, activite, donnee_liee):
        _post(auth_client, f"/cadence/activity/{activite}", {"cadence_code": "CONTINUOUS"})
        _post(auth_client, f"/cadence/data/{donnee_liee}", {"update_cadence_code": "EVENT"})
        ws = auth_client.get("/cadence/consistency").get_json()["warnings"]
        assert [w for w in ws if w["source_data_id"] == donnee_liee] == []

    def test_consistency_message_en_anglais(self, auth_client, activite, donnee_liee):
        _post(auth_client, f"/cadence/activity/{activite}", {"cadence_code": "DAILY"})
        _post(auth_client, f"/cadence/data/{donnee_liee}", {"update_cadence_code": "YEARLY"})
        _lang(auth_client, "en")
        try:
            ws = auth_client.get("/cadence/consistency").get_json()["warnings"]
            w = [x for x in ws if x["source_data_id"] == donnee_liee][0]
            assert w["data_cadence"] == "Yearly"
            assert w["activity_cadence"] == "Daily"
            assert w["finding"].startswith("Data")
        finally:
            _lang(auth_client, "fr")

    def test_donnee_cadence_effacee_avec_null(self, auth_client, app, donnee_liee):
        _post(auth_client, f"/cadence/data/{donnee_liee}",
              {"update_cadence_code": "MONTHLY", "max_age_hours": 24})
        r = _post(auth_client, f"/cadence/data/{donnee_liee}", {"update_cadence_code": None})
        assert r.status_code == 200
        with app.app_context():
            from Code.models.models import Data
            d = Data.query.get(donnee_liee)
            assert d.update_cadence_code is None
            assert d.max_age_hours is None


@pytest.fixture
def nettoyage_hsc(app):
    noms = []
    yield noms
    with app.app_context():
        from Code.models.models import HscLevelDescriptor
        from Code.extensions import db
        for n in noms:
            HscLevelDescriptor.query.filter_by(hsc_name=n).delete()
        db.session.commit()


class TestHscDescriptorsGaps:

    def test_descripteur_global_visible(self, auth_client, app, nettoyage_hsc):
        from Code.models.models import HscLevelDescriptor
        from Code.extensions import db
        nom = "HSC Global Gap129"
        nettoyage_hsc.append(nom)
        with app.app_context():
            db.session.add(HscLevelDescriptor(entity_id=None, hsc_name=nom, level=3,
                                              descriptor_fr="Global FR"))
            db.session.commit()
        _lang(auth_client, "fr")
        ds = auth_client.get(f"/hsc/descriptors/{nom}").get_json()["descriptors"]
        assert [d["descriptor"] for d in ds] == ["Global FR"]

    def test_descripteur_autre_entite_invisible(self, auth_client, app, ids, nettoyage_hsc):
        from Code.models.models import HscLevelDescriptor, Entity
        from Code.extensions import db
        nom = "HSC Autre Entite Gap129"
        nettoyage_hsc.append(nom)
        with app.app_context():
            autre = Entity(name="Entité Autre Gap129")
            db.session.add(autre)
            db.session.commit()
            autre_id = autre.id
            db.session.add(HscLevelDescriptor(entity_id=autre_id, hsc_name=nom, level=1,
                                              descriptor_fr="Secret"))
            db.session.commit()
        try:
            ds = auth_client.get(f"/hsc/descriptors/{nom}").get_json()["descriptors"]
            assert ds == []
        finally:
            with app.app_context():
                HscLevelDescriptor.query.filter_by(hsc_name=nom).delete()
                e = db.session.get(Entity, autre_id)
                if e:
                    db.session.delete(e)
                db.session.commit()

    def test_repli_fr_si_anglais_absent_et_tri_par_niveau(self, auth_client, nettoyage_hsc):
        nom = "HSC Repli Gap129"
        nettoyage_hsc.append(nom)
        _post(auth_client, "/hsc/descriptors", {"hsc_name": nom, "level": 4, "descriptor_fr": "Niveau 4 FR"})
        _post(auth_client, "/hsc/descriptors",
              {"hsc_name": nom, "level": 2, "descriptor_fr": "N2 FR", "descriptor_en": "L2 EN"})
        _lang(auth_client, "en")
        try:
            ds = auth_client.get(f"/hsc/descriptors/{nom}").get_json()["descriptors"]
        finally:
            _lang(auth_client, "fr")
        assert [d["level"] for d in ds] == [2, 4]
        assert ds[0]["descriptor"] == "L2 EN"
        assert ds[1]["descriptor"] == "Niveau 4 FR"

    def test_upsert_champ_vide_efface_et_champ_absent_conserve(self, auth_client, nettoyage_hsc):
        nom = "HSC Upsert Gap129"
        nettoyage_hsc.append(nom)
        _post(auth_client, "/hsc/descriptors",
              {"hsc_name": nom, "level": 1, "descriptor_fr": "A", "development_focus_fr": "B"})
        _post(auth_client, "/hsc/descriptors", {"hsc_name": nom, "level": 1, "descriptor_fr": ""})
        _lang(auth_client, "fr")
        d = auth_client.get(f"/hsc/descriptors/{nom}").get_json()["descriptors"][0]
        assert d["descriptor"] is None
        assert d["development_focus"] == "B"
