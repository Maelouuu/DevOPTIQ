# tests/test_106_activities_data_defensif.py
"""
Couvre les branches défensives de GET /activities/<id>/details
(activities_data.py) : modèles de savoirs absents, tri impossible,
échec de lecture des softskills. Aucune donnée n'est écrite en base :
seul le module est patché (monkeypatch, restauré automatiquement).
"""
import pytest

pytestmark = pytest.mark.activities_data


class TestDetailsDefensif:

    def test_details_sans_modeles_savoirs_renvoie_listes_vides(self, auth_client, ids, monkeypatch):
        from Code.routes import activities_data as mod
        monkeypatch.setattr(mod, "Savoir", None)
        monkeypatch.setattr(mod, "SavoirFaire", None)
        monkeypatch.setattr(mod, "Aptitude", None)
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        assert r.status_code == 200
        d = r.get_json()
        assert d["savoirs"] == []
        assert d["savoir_faires"] == []
        assert d["aptitudes"] == []

    def test_details_sans_modeles_savoirs_garde_le_reste(self, auth_client, ids, monkeypatch):
        from Code.routes import activities_data as mod
        monkeypatch.setattr(mod, "Savoir", None)
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        d = r.get_json()
        assert d["id"] == ids["activity_id"]
        assert d["name"] == d["title"]

    def test_details_tri_impossible_ne_casse_pas_la_liste(self, auth_client, ids, monkeypatch):
        from Code.routes import activities_data as mod

        class _Col:
            def asc(self):
                raise RuntimeError("tri indisponible")

        class _Query:
            def filter_by(self, **kw):
                return self

            def order_by(self, *a):
                raise AssertionError("order_by ne doit pas être appelé")

            def all(self):
                class _O:
                    id = 7
                    name = "Nom7"
                    description = ""
                return [_O()]

        class _FauxModele:
            id = _Col()
            query = _Query()

        monkeypatch.setattr(mod, "Savoir", _FauxModele)
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        assert r.status_code == 200
        assert r.get_json()["savoirs"] == [{"id": 7, "name": "Nom7", "description": "Nom7"}]

    def test_details_softskill_en_erreur_donne_liste_vide(self, auth_client, ids, monkeypatch):
        from Code.routes import activities_data as mod

        class _Boom:
            id = None

            class query:
                @staticmethod
                def filter_by(**kw):
                    raise RuntimeError("softskill indisponible")

        monkeypatch.setattr(mod, "Softskill", _Boom)
        r = auth_client.get(f"/activities/{ids['activity_id']}/details")
        assert r.status_code == 200
        assert r.get_json()["softskills"] == []

    def test_details_activite_inexistante_404(self, auth_client):
        r = auth_client.get("/activities/99999999/details")
        assert r.status_code == 404
        assert "error" in r.get_json()
