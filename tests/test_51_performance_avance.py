# tests/test_51_performance_avance.py
"""
Page : Performance — CRUD strict (/performance)
Tests précis couvrant create/read/update/delete + render, avec assertions
strictes (pas de `status_code in (...)` flou).

Routes couvertes (performance.py) :
  - POST   /performance/add
  - PUT    /performance/<id>
  - DELETE /performance/<id>
  - GET    /performance/render/<link_id>
  - GET    /performance/render_activity/<activity_id>
"""
import pytest
import json

pytestmark = pytest.mark.performance_avance


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _create_fresh_link(app):
    """Crée une Data + Link propres (pas de performance attachée) et retourne link.id."""
    with app.app_context():
        from Code.models.models import Entity, Activities, Data, Link
        from Code.extensions import db
        entity = Entity.query.filter_by(name="Entité Test").first()
        activity = Activities.query.filter_by(name="Activité Test").first()
        data_obj = Data(entity_id=entity.id, name="Data Perf Test", type="nourrissante")
        db.session.add(data_obj)
        db.session.flush()
        link = Link(
            entity_id=entity.id,
            source_data_id=data_obj.id,
            target_activity_id=activity.id,
            type="nourrissante",
        )
        db.session.add(link)
        db.session.commit()
        return link.id


def _cleanup_link(app, link_id):
    """Supprime le lien (et la performance en cascade)."""
    with app.app_context():
        from Code.models.models import Link, Performance
        from Code.extensions import db
        perf = Performance.query.filter_by(link_id=link_id).first()
        if perf:
            db.session.delete(perf)
        link = db.session.get(Link, link_id)
        if link:
            db.session.delete(link)
        db.session.commit()


def _cleanup_perf(app, perf_id):
    """Supprime une performance par son ID si elle existe encore."""
    with app.app_context():
        from Code.models.models import Performance
        from Code.extensions import db
        perf = db.session.get(Performance, perf_id)
        if perf:
            db.session.delete(perf)
            db.session.commit()


# ══════════════════════════════════════════════════════════════════════════════
# 1. POST /performance/add
# ══════════════════════════════════════════════════════════════════════════════

class TestPerformanceAdd:

    def test_create_returns_200(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf ajout strict"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _cleanup_link(app, link_id)

    def test_create_response_has_id(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf id test"}),
                content_type="application/json",
            )
            body = r.get_json()
            assert "id" in body
            assert isinstance(body["id"], int)
        finally:
            _cleanup_link(app, link_id)

    def test_create_response_has_message(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf message test"}),
                content_type="application/json",
            )
            body = r.get_json()
            assert "message" in body
        finally:
            _cleanup_link(app, link_id)

    def test_create_persisted_in_db(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf persistence check"}),
                content_type="application/json",
            )
            perf_id = r.get_json()["id"]
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p is not None
                assert p.name == "Perf persistence check"
        finally:
            _cleanup_link(app, link_id)

    def test_create_with_description(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({
                    "link_id": link_id,
                    "name": "Perf avec desc",
                    "description": "Ma description de performance",
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            perf_id = r.get_json()["id"]
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p.description == "Ma description de performance"
        finally:
            _cleanup_link(app, link_id)

    def test_missing_link_id_returns_400(self, auth_client):
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({"name": "Perf sans lien"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_missing_name_returns_400(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _cleanup_link(app, link_id)

    def test_missing_name_response_has_error(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id}),
                content_type="application/json",
            )
            body = r.get_json()
            assert "error" in body
        finally:
            _cleanup_link(app, link_id)

    def test_empty_body_returns_400(self, auth_client):
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# 2. PUT /performance/<id>
# ══════════════════════════════════════════════════════════════════════════════

class TestPerformanceUpdate:

    def _make_perf(self, auth_client, app, name="Perf à modifier"):
        link_id = _create_fresh_link(app)
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({"link_id": link_id, "name": name}),
            content_type="application/json",
        )
        return link_id, r.get_json()["id"]

    def test_update_returns_200(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            r = auth_client.put(
                f"/performance/{perf_id}",
                data=json.dumps({"name": "Nouveau nom"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _cleanup_link(app, link_id)

    def test_update_response_has_message(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            r = auth_client.put(
                f"/performance/{perf_id}",
                data=json.dumps({"name": "Nom mis à jour"}),
                content_type="application/json",
            )
            body = r.get_json()
            assert "message" in body
        finally:
            _cleanup_link(app, link_id)

    def test_update_name_persists_in_db(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            auth_client.put(
                f"/performance/{perf_id}",
                data=json.dumps({"name": "Nom final DB"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p.name == "Nom final DB"
        finally:
            _cleanup_link(app, link_id)

    def test_update_description_persists(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            auth_client.put(
                f"/performance/{perf_id}",
                data=json.dumps({"description": "Nouvelle description"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p.description == "Nouvelle description"
        finally:
            _cleanup_link(app, link_id)

    def test_update_nonexistent_returns_404(self, auth_client):
        r = auth_client.put(
            "/performance/999999",
            data=json.dumps({"name": "Ghost"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_nonexistent_has_error_field(self, auth_client):
        r = auth_client.put(
            "/performance/999999",
            data=json.dumps({"name": "Ghost"}),
            content_type="application/json",
        )
        body = r.get_json()
        assert "error" in body

    def test_update_strips_whitespace(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            auth_client.put(
                f"/performance/{perf_id}",
                data=json.dumps({"name": "  Espaces  "}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p.name == "Espaces"
        finally:
            _cleanup_link(app, link_id)


# ══════════════════════════════════════════════════════════════════════════════
# 3. DELETE /performance/<id>
# ══════════════════════════════════════════════════════════════════════════════

class TestPerformanceDelete:

    def _make_perf(self, auth_client, app):
        link_id = _create_fresh_link(app)
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({"link_id": link_id, "name": "Perf delete test"}),
            content_type="application/json",
        )
        return link_id, r.get_json()["id"]

    def test_delete_returns_200(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            r = auth_client.delete(f"/performance/{perf_id}")
            assert r.status_code == 200
        finally:
            _cleanup_link(app, link_id)

    def test_delete_response_has_message(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            r = auth_client.delete(f"/performance/{perf_id}")
            body = r.get_json()
            assert "message" in body
        finally:
            _cleanup_link(app, link_id)

    def test_delete_removes_from_db(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            auth_client.delete(f"/performance/{perf_id}")
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p is None
        finally:
            _cleanup_link(app, link_id)

    def test_double_delete_second_returns_404(self, auth_client, app):
        link_id, perf_id = self._make_perf(auth_client, app)
        try:
            auth_client.delete(f"/performance/{perf_id}")
            r2 = auth_client.delete(f"/performance/{perf_id}")
            assert r2.status_code == 404
        finally:
            _cleanup_link(app, link_id)

    def test_delete_nonexistent_returns_404(self, auth_client):
        r = auth_client.delete("/performance/999999")
        assert r.status_code == 404

    def test_delete_nonexistent_has_error_field(self, auth_client):
        r = auth_client.delete("/performance/999999")
        body = r.get_json()
        assert "error" in body


# ══════════════════════════════════════════════════════════════════════════════
# 4. GET /performance/render/<link_id>
# ══════════════════════════════════════════════════════════════════════════════

class TestPerformanceRender:

    def test_render_with_perf_returns_200(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Render test"}),
                content_type="application/json",
            )
            r = auth_client.get(f"/performance/render/{link_id}")
            assert r.status_code == 200
        finally:
            _cleanup_link(app, link_id)

    def test_render_with_perf_contains_name(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf Rendu HTML"}),
                content_type="application/json",
            )
            r = auth_client.get(f"/performance/render/{link_id}")
            assert b"Perf Rendu HTML" in r.data
        finally:
            _cleanup_link(app, link_id)

    def test_render_without_perf_returns_200(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.get(f"/performance/render/{link_id}")
            assert r.status_code == 200
        finally:
            _cleanup_link(app, link_id)

    def test_render_without_perf_contains_add_hint(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.get(f"/performance/render/{link_id}")
            # Doit afficher le bouton d'ajout ou un message d'absence
            body = r.data.decode("utf-8")
            assert "performance" in body.lower()
        finally:
            _cleanup_link(app, link_id)

    def test_render_returns_html_content(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            r = auth_client.get(f"/performance/render/{link_id}")
            assert b"<div" in r.data
        finally:
            _cleanup_link(app, link_id)

    def test_render_activity_returns_200(self, auth_client, ids):
        r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
        assert r.status_code == 200

    def test_render_activity_returns_html(self, auth_client, ids):
        r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
        assert b"<div" in r.data

    def test_render_activity_unknown_id_returns_200(self, auth_client):
        r = auth_client.get("/performance/render_activity/999999")
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 5. Cycle de vie complet : create → update → render → delete
# ══════════════════════════════════════════════════════════════════════════════

class TestPerformanceLifecycle:

    def test_full_lifecycle(self, auth_client, app):
        link_id = _create_fresh_link(app)
        try:
            # Create
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Lifecycle Init", "description": "Desc init"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            perf_id = r.get_json()["id"]

            # Render après création
            r = auth_client.get(f"/performance/render/{link_id}")
            assert r.status_code == 200
            assert b"Lifecycle Init" in r.data

            # Update
            r = auth_client.put(
                f"/performance/{perf_id}",
                data=json.dumps({"name": "Lifecycle Updated", "description": "Desc updated"}),
                content_type="application/json",
            )
            assert r.status_code == 200

            # Render après update
            r = auth_client.get(f"/performance/render/{link_id}")
            assert b"Lifecycle Updated" in r.data

            # Delete
            r = auth_client.delete(f"/performance/{perf_id}")
            assert r.status_code == 200

            # Render après suppression → toujours 200 mais plus de contenu de perf
            r = auth_client.get(f"/performance/render/{link_id}")
            assert r.status_code == 200
            assert b"Lifecycle Updated" not in r.data

        finally:
            _cleanup_link(app, link_id)
