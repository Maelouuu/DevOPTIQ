# tests/test_119_carto_sharing_gaps.py
"""
Page : Partage de cartos — branches défensives de Code/routes/carto_sharing.py
(accès anonyme, entité inconnue, corps invalide, vignette SVG).
Tests isolés : les helpers purs sont appelés directement, les routes HTTP
utilisent un client dédié (aucune session partagée avec le reste de la suite).
"""
import json

import pytest

pytestmark = pytest.mark.carto_sharing


@pytest.fixture
def anon(app):
    return app.test_client()


def _post(c, url, payload):
    return c.post(url, data=json.dumps(payload), content_type="application/json")


class TestHelpersPurs:

    def test_nom_compte_absent(self):
        from Code.routes.carto_sharing import _nom_compte
        assert _nom_compte(None) == "—"

    def test_nom_compte_sans_nom_retombe_sur_email(self):
        from types import SimpleNamespace
        from Code.routes.carto_sharing import _nom_compte
        u = SimpleNamespace(first_name="", last_name="", email="x@y.z")
        assert _nom_compte(u) == "x@y.z"

    def test_nom_compte_complet(self):
        from types import SimpleNamespace
        from Code.routes.carto_sharing import _nom_compte
        u = SimpleNamespace(first_name="Ada", last_name="Lovelace", email="a@b.c")
        assert _nom_compte(u) == "Ada Lovelace"

    @pytest.mark.parametrize("brut", [None, "", "{pas du json", 42])
    def test_diagram_invalide_ou_vide_donne_none(self, brut):
        from Code.routes.carto_sharing import _diagram
        assert _diagram(brut) is None

    def test_diagram_valide(self):
        from Code.routes.carto_sharing import _diagram
        assert _diagram('{"shapes": []}') == {"shapes": []}


class TestPointsDuLien:

    def test_chemin_utilisateur_prioritaire(self):
        from Code.routes.carto_sharing import _points_du_lien
        conn = {"userPts": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
        assert _points_du_lien(conn, {}) == [(1, 2), (3, 4)]

    def test_points_incomplets_ignores_puis_repli_sur_les_boites(self):
        from Code.routes.carto_sharing import _points_du_lien
        conn = {"userPts": [{"x": 1, "y": None}, {"x": 2, "y": 2}],
                "fromId": "a", "toId": "b"}
        boites = {"a": (0, 0, 10, 10), "b": (100, 0, 10, 10)}
        assert _points_du_lien(conn, boites) == [(5.0, 5.0), (105.0, 5.0)]

    def test_extremite_inconnue_donne_liste_vide(self):
        from Code.routes.carto_sharing import _points_du_lien
        assert _points_du_lien({"fromId": "a", "toId": "zz"},
                               {"a": (0, 0, 1, 1)}) == []


class TestSvgDepuisDiagramme:

    def test_diagramme_vide_donne_none(self):
        from Code.routes.carto_sharing import _svg_depuis_diagramme
        assert _svg_depuis_diagramme({"shapes": [], "bands": []}) is None

    def test_bandes_supprimees_ignorees(self):
        from Code.routes.carto_sharing import _svg_depuis_diagramme
        assert _svg_depuis_diagramme(
            {"bands": [{"id": "b", "height": 100, "deleted": True}]}) is None

    def test_decision_rendue_en_losange_et_lien_en_polyligne(self):
        from Code.routes.carto_sharing import _svg_depuis_diagramme
        svg = _svg_depuis_diagramme({
            "bands": [{"id": "b", "height": 200}],
            "shapes": [
                {"id": "d", "type": "decision", "x": 0, "y": 0, "w": 80, "h": 60},
                {"id": "p", "type": "process", "x": 300, "y": 0, "w": 80, "h": 60},
            ],
            "connections": [{"fromId": "d", "toId": "p"}],
        })
        assert "<polygon" in svg
        assert "<polyline" in svg
        assert "<rect" in svg

    def test_forme_sans_taille_non_dessinee(self):
        from Code.routes.carto_sharing import _svg_depuis_diagramme
        svg = _svg_depuis_diagramme({"shapes": [
            {"id": "z", "type": "decision", "x": 0, "y": 0, "w": 0, "h": 0}]})
        assert "<polygon" not in svg


class TestRoutesAnonymes:

    @pytest.mark.parametrize("url", [
        "/cartography/api/access/1",
        "/cartography/api/access/matrice",
    ])
    def test_get_anonyme_401(self, anon, url):
        r = anon.get(url)
        assert r.status_code == 401
        assert r.get_json()["error"] == "Non connecté"

    def test_post_access_anonyme_401(self, anon):
        assert _post(anon, "/cartography/api/access/1", {}).status_code == 401

    def test_post_matrice_anonyme_401(self, anon):
        assert _post(anon, "/cartography/api/access/matrice", {"cases": []}).status_code == 401

    def test_thumbnail_anonyme_401(self, anon):
        assert anon.get("/cartography/api/access/1/thumbnail.svg").status_code == 401


class TestRoutesEntiteInconnue:

    def test_get_access_entite_inconnue_404(self, auth_client):
        assert auth_client.get("/cartography/api/access/99999999").status_code == 404

    def test_post_access_entite_inconnue_404(self, auth_client):
        r = _post(auth_client, "/cartography/api/access/99999999", {"is_shared": True})
        assert r.status_code == 404

    def test_thumbnail_entite_inconnue_404(self, auth_client):
        assert auth_client.get(
            "/cartography/api/access/99999999/thumbnail.svg").status_code == 404
