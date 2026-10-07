# tests/test_100_performance_items_gaps.py
"""
Routes : /performance (cas limites) et /your_api/activity_items (libellé HSC).

Chaque test crée ses propres données jetables et les supprime : la base est
partagée (scope=session), rien ne doit fuir.
"""
import json

import pytest

pytestmark = pytest.mark.performance


def _json(client, method, url, payload):
    return getattr(client, method)(
        url, data=json.dumps(payload), content_type="application/json"
    )


@pytest.fixture
def lien_jetable(app, ids):
    """Lien dédié (sans performance) supprimé en fin de test."""
    from Code.extensions import db
    from Code.models.models import Link, Performance
    with app.app_context():
        lk = Link(source_activity_id=ids["activity_id"],
                  target_activity_id=ids["activity_id"], type="Lien jetable")
        db.session.add(lk)
        db.session.commit()
        lid = lk.id
    yield lid
    with app.app_context():
        Performance.query.filter_by(link_id=lid).delete()
        Link.query.filter_by(id=lid).delete()
        db.session.commit()


class TestPerformanceCasLimites:

    def test_add_name_blanc_refuse(self, auth_client, lien_jetable):
        r = _json(auth_client, "post", "/performance/add",
                  {"link_id": lien_jetable, "name": "   "})
        assert r.status_code == 400

    def test_add_sans_link_id_refuse(self, auth_client):
        r = _json(auth_client, "post", "/performance/add", {"name": "X"})
        assert r.status_code == 400

    def test_add_corps_vide_refuse(self, auth_client):
        r = _json(auth_client, "post", "/performance/add", {})
        assert r.status_code == 400

    def test_add_nettoie_les_espaces(self, auth_client, lien_jetable, app):
        r = _json(auth_client, "post", "/performance/add",
                  {"link_id": lien_jetable, "name": "  Délai  ",
                   "description": " courte "})
        assert r.status_code == 200
        with app.app_context():
            from Code.models.models import Performance
            p = Performance.query.get(r.get_json()["id"])
            assert (p.name, p.description) == ("Délai", "courte")

    def test_update_champ_absent_conserve_la_valeur(self, auth_client, lien_jetable, app):
        pid = _json(auth_client, "post", "/performance/add",
                    {"link_id": lien_jetable, "name": "Nom", "description": "Desc"}
                    ).get_json()["id"]
        r = _json(auth_client, "put", f"/performance/{pid}", {"name": " Nouveau "})
        assert r.status_code == 200
        with app.app_context():
            from Code.models.models import Performance
            p = Performance.query.get(pid)
            assert (p.name, p.description) == ("Nouveau", "Desc")

    def test_update_description_seule(self, auth_client, lien_jetable, app):
        pid = _json(auth_client, "post", "/performance/add",
                    {"link_id": lien_jetable, "name": "Nom", "description": "Desc"}
                    ).get_json()["id"]
        r = _json(auth_client, "put", f"/performance/{pid}", {"description": "Autre"})
        assert r.status_code == 200
        with app.app_context():
            from Code.models.models import Performance
            p = Performance.query.get(pid)
            assert (p.name, p.description) == ("Nom", "Autre")

    def test_update_inexistant_404(self, auth_client):
        r = _json(auth_client, "put", "/performance/999999", {"name": "x"})
        assert r.status_code == 404

    def test_delete_supprime_en_base(self, auth_client, lien_jetable, app):
        pid = _json(auth_client, "post", "/performance/add",
                    {"link_id": lien_jetable, "name": "À supprimer"}).get_json()["id"]
        assert auth_client.delete(f"/performance/{pid}").status_code == 200
        with app.app_context():
            from Code.models.models import Performance
            assert Performance.query.get(pid) is None
        assert auth_client.delete(f"/performance/{pid}").status_code == 404

    def test_render_link_sans_performance_propose_l_ajout(self, auth_client, lien_jetable):
        r = auth_client.get(f"/performance/render/{lien_jetable}")
        assert r.status_code == 200
        assert f"showAddPerfForm('{lien_jetable}')" in r.get_data(as_text=True)

    def test_render_link_avec_performance_affiche_le_nom(self, auth_client, lien_jetable):
        _json(auth_client, "post", "/performance/add",
              {"link_id": lien_jetable, "name": "Perf Visible"})
        r = auth_client.get(f"/performance/render/{lien_jetable}")
        assert "Perf Visible" in r.get_data(as_text=True)

    def test_render_activity_sans_lien_200(self, auth_client):
        r = auth_client.get("/performance/render_activity/999999")
        assert r.status_code == 200


class TestActivityItemsLibelleHsc:

    @pytest.fixture
    def hsc(self, app, ids):
        from Code.extensions import db
        from Code.models.models import Softskill
        with app.app_context():
            avec = Softskill(habilete="Écoute", niveau="2 (Acquisition)",
                             activity_id=ids["activity_id"])
            sans = Softskill(habilete="Rigueur", niveau="  ",
                             activity_id=ids["activity_id"])
            db.session.add_all([avec, sans])
            db.session.commit()
            sid = (avec.id, sans.id)
        yield sid
        with app.app_context():
            Softskill.query.filter(Softskill.id.in_(sid)).delete(synchronize_session=False)
            db.session.commit()

    def test_libelle_habilete_et_niveau(self, auth_client, ids, hsc):
        data = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        noms = {h["id"]: h["name"] for h in data["hsc"]}
        assert noms[hsc[0]] == "Écoute (2 (Acquisition))"

    def test_niveau_blanc_donne_l_habilete_seule(self, auth_client, ids, hsc):
        data = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
        noms = {h["id"]: h["name"] for h in data["hsc"]}
        assert noms[hsc[1]] == "Rigueur"

    def test_savoir_faire_remonte_sa_description(self, auth_client, ids, app):
        from Code.extensions import db
        from Code.models.models import SavoirFaire
        with app.app_context():
            sf = SavoirFaire(description="SF items jetable", activity_id=ids["activity_id"])
            db.session.add(sf)
            db.session.commit()
            sid = sf.id
        try:
            data = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
            assert {"id": sid, "name": "SF items jetable"} in data["savoir_faire"]
        finally:
            with app.app_context():
                SavoirFaire.query.filter_by(id=sid).delete()
                db.session.commit()

    def test_items_d_une_autre_activite_exclus(self, auth_client, ids, app):
        from Code.extensions import db
        from Code.models.models import Activities, Savoir
        with app.app_context():
            autre = Activities(name="Activité items autre", entity_id=ids["entity_id"])
            db.session.add(autre)
            db.session.commit()
            aid = autre.id
            sv = Savoir(description="Savoir autre act", activity_id=aid)
            db.session.add(sv)
            db.session.commit()
            svid = sv.id
        try:
            data = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}").get_json()
            assert svid not in [s["id"] for s in data["savoirs"]]
        finally:
            with app.app_context():
                Savoir.query.filter_by(id=svid).delete()
                Activities.query.filter_by(id=aid).delete()
                db.session.commit()
