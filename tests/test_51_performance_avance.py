# tests/test_51_performance_avance.py
"""
Route : /performance  (Code/routes/performance.py)
Coverage approfondie — test_07 ne comportait que 8 tests avec des assertions trop larges.

Endpoints couverts :
  POST   /performance/add              → création (link_id + name requis)
  PUT    /performance/<id>             → mise à jour partielle
  DELETE /performance/<id>             → suppression
  GET    /performance/render/<link_id>          → fragment HTML (pas JSON)
  GET    /performance/render_activity/<act_id>  → fragment HTML (pas JSON)
"""
import pytest
import json

pytestmark = pytest.mark.performance_avance


# ---------------------------------------------------------------------------
# Helpers DB
# ---------------------------------------------------------------------------

def _mk_link(app, ids):
    """Crée un lien frais (source_activity_id) pour isoler les tests."""
    with app.app_context():
        from Code.models.models import Link
        from Code.extensions import db
        lk = Link(entity_id=ids["entity_id"], source_activity_id=ids["activity_id"], type="perf_test")
        db.session.add(lk)
        db.session.commit()
        return lk.id


def _rm_link(app, link_id):
    """Supprime le lien (cascade supprime la performance associée en DB)."""
    with app.app_context():
        from Code.models.models import Link
        from Code.extensions import db
        lk = Link.query.get(link_id)
        if lk:
            db.session.delete(lk)
            db.session.commit()


def _mk_perf(app, link_id, name="Perf Test", desc=""):
    """Crée une performance sur le lien (unique par lien)."""
    with app.app_context():
        from Code.models.models import Performance
        from Code.extensions import db
        existing = Performance.query.filter_by(link_id=link_id).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
        perf = Performance(link_id=link_id, name=name, description=desc)
        db.session.add(perf)
        db.session.commit()
        return perf.id


# ===========================================================================
# 1. POST /performance/add — création
# ===========================================================================

class TestPerformanceAddValidation:
    """Validation des champs obligatoires."""

    def test_add_missing_link_id_returns_400(self, auth_client):
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({"name": "Test"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_missing_name_returns_400(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": lid}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _rm_link(app, lid)

    def test_add_empty_name_returns_400(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": lid, "name": "  "}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _rm_link(app, lid)

    def test_add_empty_body_returns_400(self, auth_client):
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_error_response_has_error_key(self, auth_client):
        r = auth_client.post(
            "/performance/add",
            data=json.dumps({"name": "Sans lien"}),
            content_type="application/json",
        )
        body = r.get_json()
        assert body is not None
        assert "error" in body


class TestPerformanceAddSuccess:
    """Création valide."""

    def test_add_success_returns_200(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": lid, "name": "Perf créée"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _rm_link(app, lid)

    def test_add_success_response_has_id(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": lid, "name": "Perf avec id"}),
                content_type="application/json",
            )
            body = r.get_json()
            assert "id" in body
            assert isinstance(body["id"], int)
        finally:
            _rm_link(app, lid)

    def test_add_success_response_has_message_key(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            r = auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": lid, "name": "P"}),
                content_type="application/json",
            )
            body = r.get_json()
            assert "message" in body
        finally:
            _rm_link(app, lid)

    def test_add_persists_in_db(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": lid, "name": "Perf persistante"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.filter_by(link_id=lid).first()
                assert p is not None
                assert p.name == "Perf persistante"
        finally:
            _rm_link(app, lid)

    def test_add_with_description_stores_it(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            auth_client.post(
                "/performance/add",
                data=json.dumps({"link_id": lid, "name": "P", "description": "Ma desc"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.filter_by(link_id=lid).first()
                assert p is not None
                assert p.description == "Ma desc"
        finally:
            _rm_link(app, lid)


# ===========================================================================
# 2. PUT /performance/<id> — mise à jour
# ===========================================================================

class TestPerformanceUpdate:

    def test_update_not_found_returns_404(self, auth_client):
        r = auth_client.put(
            "/performance/999999",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_not_found_has_error_key(self, auth_client):
        r = auth_client.put(
            "/performance/999999",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        body = r.get_json()
        assert "error" in body

    def test_update_success_returns_200(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            pid = _mk_perf(app, lid, "Initiale")
            r = auth_client.put(
                f"/performance/{pid}",
                data=json.dumps({"name": "Modifiée"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _rm_link(app, lid)

    def test_update_success_has_message_key(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            pid = _mk_perf(app, lid, "P")
            r = auth_client.put(
                f"/performance/{pid}",
                data=json.dumps({"name": "P2"}),
                content_type="application/json",
            )
            body = r.get_json()
            assert "message" in body
        finally:
            _rm_link(app, lid)

    def test_update_name_persists_in_db(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            pid = _mk_perf(app, lid, "Ancien nom")
            auth_client.put(
                f"/performance/{pid}",
                data=json.dumps({"name": "Nouveau nom"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(pid)
                assert p.name == "Nouveau nom"
        finally:
            _rm_link(app, lid)

    def test_update_description_persists_in_db(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            pid = _mk_perf(app, lid, "N", "Ancienne desc")
            auth_client.put(
                f"/performance/{pid}",
                data=json.dumps({"description": "Nouvelle desc"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(pid)
                assert p.description == "Nouvelle desc"
        finally:
            _rm_link(app, lid)

    def test_update_name_only_does_not_change_description(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            pid = _mk_perf(app, lid, "Nom", "Desc stable")
            auth_client.put(
                f"/performance/{pid}",
                data=json.dumps({"name": "Nom modifié"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(pid)
                assert p.description == "Desc stable"
        finally:
            _rm_link(app, lid)

    def test_update_empty_body_does_not_crash(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            pid = _mk_perf(app, lid, "P stable")
            r = auth_client.put(
                f"/performance/{pid}",
                data=json.dumps({}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _rm_link(app, lid)


# ===========================================================================
# 3. DELETE /performance/<id> — suppression
# ===========================================================================

class TestPerformanceDelete:

    def test_delete_not_found_returns_404(self, auth_client):
        r = auth_client.delete("/performance/999999")
        assert r.status_code == 404

    def test_delete_not_found_has_error_key(self, auth_client):
        r = auth_client.delete("/performance/999999")
        body = r.get_json()
        assert "error" in body

    def test_delete_success_returns_200(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        pid = _mk_perf(app, lid, "A supprimer")
        try:
            r = auth_client.delete(f"/performance/{pid}")
            assert r.status_code == 200
        finally:
            _rm_link(app, lid)

    def test_delete_success_has_message_key(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        pid = _mk_perf(app, lid, "A supprimer avec message")
        try:
            r = auth_client.delete(f"/performance/{pid}")
            body = r.get_json()
            assert "message" in body
        finally:
            _rm_link(app, lid)

    def test_delete_removes_from_db(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        pid = _mk_perf(app, lid, "Supprimée")
        try:
            auth_client.delete(f"/performance/{pid}")
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(pid)
                assert p is None
        finally:
            _rm_link(app, lid)

    def test_delete_twice_returns_404(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        pid = _mk_perf(app, lid, "Double suppression")
        try:
            auth_client.delete(f"/performance/{pid}")
            r = auth_client.delete(f"/performance/{pid}")
            assert r.status_code == 404
        finally:
            _rm_link(app, lid)


# ===========================================================================
# 4. GET /performance/render/<link_id> — rendu HTML
# ===========================================================================

class TestPerformanceRenderByLink:
    """La route retourne du HTML (pas JSON) ; statut toujours 200."""

    def test_render_existing_link_returns_200(self, auth_client, ids):
        r = auth_client.get(f"/performance/render/{ids['link_id']}")
        assert r.status_code == 200

    def test_render_unknown_link_returns_200_with_empty_html(self, auth_client):
        """Un link_id inexistant retourne quand même 200 (fragment HTML vide)."""
        r = auth_client.get("/performance/render/999999")
        assert r.status_code == 200

    def test_render_returns_html_content(self, auth_client, ids):
        r = auth_client.get(f"/performance/render/{ids['link_id']}")
        body = r.data.decode("utf-8")
        assert "<" in body and ">" in body

    def test_render_link_without_performance_mentions_aucune(self, auth_client, app, ids):
        """Si aucune performance sur ce lien, le fragment dit 'Aucune performance'."""
        lid = _mk_link(app, ids)
        try:
            r = auth_client.get(f"/performance/render/{lid}")
            body = r.data.decode("utf-8")
            assert "Aucune performance" in body
        finally:
            _rm_link(app, lid)

    def test_render_link_without_performance_includes_link_id_for_add(self, auth_client, app, ids):
        """Le fragment inclut le link_id pour permettre l'ajout via JS."""
        lid = _mk_link(app, ids)
        try:
            r = auth_client.get(f"/performance/render/{lid}")
            body = r.data.decode("utf-8")
            assert str(lid) in body
        finally:
            _rm_link(app, lid)

    def test_render_link_with_performance_contains_name(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            _mk_perf(app, lid, "Perf Visible dans HTML")
            r = auth_client.get(f"/performance/render/{lid}")
            body = r.data.decode("utf-8")
            assert "Perf Visible dans HTML" in body
        finally:
            _rm_link(app, lid)

    def test_render_link_with_performance_contains_edit_action(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            _mk_perf(app, lid, "Perf éditable")
            r = auth_client.get(f"/performance/render/{lid}")
            body = r.data.decode("utf-8")
            assert "showEditPerfForm" in body or "perf-btn-edit" in body
        finally:
            _rm_link(app, lid)

    def test_render_link_with_performance_contains_delete_action(self, auth_client, app, ids):
        lid = _mk_link(app, ids)
        try:
            _mk_perf(app, lid, "Perf supprimable")
            r = auth_client.get(f"/performance/render/{lid}")
            body = r.data.decode("utf-8")
            assert "deletePerformance" in body or "perf-btn-delete" in body
        finally:
            _rm_link(app, lid)

    def test_render_link_unauthenticated_does_not_crash(self, client, ids):
        """Les routes render ne requièrent pas d'auth — elles retournent du HTML."""
        r = client.get(f"/performance/render/{ids['link_id']}")
        assert r.status_code == 200


# ===========================================================================
# 5. GET /performance/render_activity/<activity_id> — rendu via activité
# ===========================================================================

class TestPerformanceRenderByActivity:

    def test_render_activity_returns_200(self, auth_client, ids):
        r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
        assert r.status_code == 200

    def test_render_activity_returns_html(self, auth_client, ids):
        r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
        body = r.data.decode("utf-8")
        assert "<" in body

    def test_render_activity_no_performance_returns_aucune_text(self, auth_client, ids):
        """L'activité seed n'a pas de performance via source_activity_id."""
        r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
        body = r.data.decode("utf-8")
        assert "Aucune performance" in body

    def test_render_activity_with_performance_contains_name(self, auth_client, app, ids):
        """Crée un lien source_activity_id → performance visible dans render_activity."""
        with app.app_context():
            from Code.models.models import Link, Performance
            from Code.extensions import db
            lk = Link(entity_id=ids["entity_id"], source_activity_id=ids["activity_id"], type="render_act_test")
            db.session.add(lk)
            db.session.flush()
            perf = Performance(link_id=lk.id, name="Perf Activité Source")
            db.session.add(perf)
            db.session.commit()
            lid, pid = lk.id, perf.id

        try:
            r = auth_client.get(f"/performance/render_activity/{ids['activity_id']}")
            body = r.data.decode("utf-8")
            assert "Perf Activité Source" in body
        finally:
            with app.app_context():
                from Code.models.models import Link, Performance
                from Code.extensions import db
                Performance.query.filter_by(id=pid).delete()
                db.session.commit()
                Link.query.filter_by(id=lid).delete()
                db.session.commit()

    def test_render_activity_unknown_id_returns_200(self, auth_client):
        """Même pour une activité inconnue, le rendu HTML est retourné."""
        r = auth_client.get("/performance/render_activity/999999")
        assert r.status_code == 200

    def test_render_activity_unauthenticated_does_not_crash(self, client, ids):
        r = client.get(f"/performance/render_activity/{ids['activity_id']}")
        assert r.status_code == 200
