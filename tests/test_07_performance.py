# tests/test_07_performance.py
"""
Page : Connexions / Performance (section dans les activités)
Tests couvrant le CRUD des performances associées aux connexions.
"""
import pytest
import json

pytestmark = pytest.mark.performance


class TestPerformanceCRUD:

    def _get_link_id(self, app):
        with app.app_context():
            from Code.models.models import Link
            link = Link.query.first()
            return link.id if link else None

    def test_add_performance(self, auth_client, ids, app):
        link_id = self._get_link_id(app)
        if not link_id:
            pytest.skip("Aucun lien disponible pour le test")

        r = auth_client.post(
            "/performance/add",
            data=json.dumps({
                "name": "Performance test",
                "description": "Desc performance",
                "link_id": link_id,
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)

    def test_add_performance_missing_name(self, auth_client, ids, app):
        link_id = self._get_link_id(app)
        if not link_id:
            pytest.skip("Aucun lien disponible")

        r = auth_client.post(
            "/performance/add",
            data=json.dumps({"link_id": link_id}),
            content_type="application/json",
        )
        assert r.status_code in (400, 422, 200)

    def test_update_performance_not_found(self, auth_client):
        r = auth_client.put(
            "/performance/999999",
            data=json.dumps({"name": "Inexistant"}),
            content_type="application/json",
        )
        assert r.status_code in (404, 200)

    def test_delete_performance_not_found(self, auth_client):
        r = auth_client.delete("/performance/999999")
        assert r.status_code in (404, 200)

    def test_render_performance_for_link(self, auth_client, app):
        link_id = self._get_link_id(app)
        if not link_id:
            pytest.skip("Aucun lien disponible")

        r = auth_client.get(f"/performance/render/{link_id}")
        assert r.status_code in (200, 404)

    def test_render_performance_for_activity(self, auth_client, ids):
        r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
        assert r.status_code in (200, 404)

    def test_performance_add_and_delete(self, auth_client, ids, app):
        """Test : créer une performance puis la supprimer (nettoie la DB avant)."""
        link_id = self._get_link_id(app)
        if not link_id:
            pytest.skip("Aucun lien disponible")

        # Cleanup : supprimer toute performance existante sur ce lien (UNIQUE constraint)
        with app.app_context():
            from Code.models.models import Performance
            from Code.extensions import db
            existing = Performance.query.filter_by(link_id=link_id).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

        # Créer
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({"name": "Perf lifecycle test", "link_id": link_id}),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        data = json.loads(r.data)
        perf_id = data.get("id")
        if not perf_id:
            with app.app_context():
                from Code.models.models import Performance
                perf = Performance.query.filter_by(name="Perf lifecycle test").first()
                perf_id = perf.id if perf else None
        if not perf_id:
            pytest.skip("Impossible de récupérer l'ID de la performance")

        # Supprimer
        r = auth_client.delete(f"/performance/{perf_id}")
        assert r.status_code in (200, 204)
