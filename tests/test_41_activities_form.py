# tests/test_41_activities_form.py
"""
Routes : activities_form.py (blueprint activities_bp, préfixe /activities)
  - POST   /activities/performance/add    — créer OU mettre à jour une performance (via link_id)
  - PUT    /activities/performance/<id>   — modifier une performance par son id
  - DELETE /activities/performance/<id>  — supprimer une performance par son id

Note : ces routes coexistent avec /performance/... (blueprint performance_bp).
Elles délèguent aux helpers add_performance / update_performance / delete_performance
définis dans activities_performance.py.
"""
import json
import pytest

pytestmark = pytest.mark.activities_form


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_link(app, ids, tag=""):
    """Crée un Data + Link isolé (sans performance) et retourne (link_id, data_id)."""
    with app.app_context():
        from Code.models.models import Data, Link
        from Code.extensions import db
        d = Data(entity_id=ids["entity_id"], name=f"Data-AF{tag}", type="nourrissante")
        db.session.add(d)
        db.session.flush()
        lnk = Link(
            entity_id=ids["entity_id"],
            source_data_id=d.id,
            target_activity_id=ids["activity_id"],
            type="nourrissante",
        )
        db.session.add(lnk)
        db.session.commit()
        return lnk.id, d.id


def _make_perf(app, link_id, name="PerfFormTest"):
    """Crée une Performance pour link_id et retourne perf_id."""
    with app.app_context():
        from Code.models.models import Performance
        from Code.extensions import db
        p = Performance(link_id=link_id, name=name, description="Desc formulaire")
        db.session.add(p)
        db.session.commit()
        return p.id


def _teardown(app, link_id=None, data_id=None):
    """Supprime Performance(s), Link et Data associés (ordre FK)."""
    with app.app_context():
        from Code.models.models import Performance, Link, Data
        from Code.extensions import db
        if link_id:
            for p in Performance.query.filter_by(link_id=link_id).all():
                db.session.delete(p)
            db.session.flush()
            lnk = Link.query.get(link_id)
            if lnk:
                db.session.delete(lnk)
                db.session.flush()
        if data_id:
            d = Data.query.get(data_id)
            if d:
                db.session.delete(d)
        db.session.commit()


# ===========================================================================
# 1. POST /activities/performance/add
# ===========================================================================

class TestActivitiesPerformanceAdd:

    def test_creates_performance_returns_201(self, auth_client, ids, app):
        """Nouveau lien sans performance → POST crée et retourne 201."""
        link_id, data_id = _make_link(app, ids, "add01")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf Add 01", "description": "Desc add"}),
                content_type="application/json",
            )
            assert r.status_code == 201
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_response_contains_id_field(self, auth_client, ids, app):
        """La réponse 201 expose un champ 'id' de type entier."""
        link_id, data_id = _make_link(app, ids, "add02")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf Add 02"}),
                content_type="application/json",
            )
            data = json.loads(r.data)
            assert "id" in data
            assert isinstance(data["id"], int)
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_response_contains_message_field(self, auth_client, ids, app):
        """La réponse contient un champ 'message' non vide."""
        link_id, data_id = _make_link(app, ids, "add03")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf Add 03"}),
                content_type="application/json",
            )
            data = json.loads(r.data)
            assert "message" in data
            assert data["message"]
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_existing_performance_updates_returns_200(self, auth_client, ids, app):
        """Lien ayant déjà une performance → POST met à jour et retourne 200."""
        link_id, data_id = _make_link(app, ids, "add04")
        _make_perf(app, link_id, "Perf Initiale Add04")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf Mise à Jour Add04"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_update_response_has_message(self, auth_client, ids, app):
        """La réponse de mise à jour (200) contient un champ 'message'."""
        link_id, data_id = _make_link(app, ids, "add05")
        _make_perf(app, link_id, "Perf Init Add05")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf MàJ Add05"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "message" in data
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_missing_link_id_causes_error(self, auth_client):
        """Payload sans link_id → accès dict échoue → réponse d'erreur (4xx/5xx)."""
        r = auth_client.post(
            "/activities/performance/add",
            data=json.dumps({"name": "Sans link"}),
            content_type="application/json",
        )
        assert r.status_code in (400, 500)

    def test_missing_name_causes_error(self, auth_client, ids, app):
        """Payload sans name → accès dict échoue → réponse d'erreur (4xx/5xx)."""
        link_id, data_id = _make_link(app, ids, "add07")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id}),
                content_type="application/json",
            )
            assert r.status_code in (400, 500)
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_performance_persisted_in_db(self, auth_client, ids, app):
        """Après POST 201, la performance est bien présente en DB avec le bon nom."""
        link_id, data_id = _make_link(app, ids, "add08")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf DB Check"}),
                content_type="application/json",
            )
            assert r.status_code == 201
            perf_id = json.loads(r.data)["id"]
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p is not None
                assert p.name == "Perf DB Check"
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_description_optional(self, auth_client, ids, app):
        """Payload sans description → 201 (description vaut '')."""
        link_id, data_id = _make_link(app, ids, "add09")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Perf No Desc"}),
                content_type="application/json",
            )
            assert r.status_code == 201
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)


# ===========================================================================
# 2. PUT /activities/performance/<perf_id>
# ===========================================================================

class TestActivitiesPerformanceUpdate:

    def test_update_existing_returns_200(self, auth_client, ids, app):
        """PUT sur une performance existante → 200."""
        link_id, data_id = _make_link(app, ids, "upd01")
        perf_id = _make_perf(app, link_id, "Perf Upd01")
        try:
            r = auth_client.put(
                f"/activities/performance/{perf_id}",
                data=json.dumps({"name": "Nom Modifié", "description": "Desc modifiée"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_update_response_has_message(self, auth_client, ids, app):
        """La réponse PUT contient un champ 'message' non vide."""
        link_id, data_id = _make_link(app, ids, "upd02")
        perf_id = _make_perf(app, link_id, "Perf Upd02")
        try:
            r = auth_client.put(
                f"/activities/performance/{perf_id}",
                data=json.dumps({"name": "Nom Upd02"}),
                content_type="application/json",
            )
            data = json.loads(r.data)
            assert "message" in data
            assert data["message"]
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_update_nonexistent_returns_404(self, auth_client):
        """PUT sur ID inexistant → 404 avec champ 'error'."""
        r = auth_client.put(
            "/activities/performance/999999",
            data=json.dumps({"name": "Fantôme"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_missing_name_causes_error(self, auth_client, ids, app):
        """PUT sans champ name → KeyError → réponse d'erreur (4xx/5xx)."""
        link_id, data_id = _make_link(app, ids, "upd04")
        perf_id = _make_perf(app, link_id, "Perf Upd04")
        try:
            r = auth_client.put(
                f"/activities/performance/{perf_id}",
                data=json.dumps({"description": "Description seule, pas de name"}),
                content_type="application/json",
            )
            assert r.status_code in (400, 500)
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_update_persists_new_name_in_db(self, auth_client, ids, app):
        """La modification de nom est effectivement sauvegardée en base."""
        link_id, data_id = _make_link(app, ids, "upd05")
        perf_id = _make_perf(app, link_id, "Avant modif")
        try:
            auth_client.put(
                f"/activities/performance/{perf_id}",
                data=json.dumps({"name": "Après modif", "description": ""}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p.name == "Après modif"
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_update_description_optional(self, auth_client, ids, app):
        """PUT sans clé 'description' → description = '' → 200 (data.get tolère l'absence)."""
        link_id, data_id = _make_link(app, ids, "upd06")
        perf_id = _make_perf(app, link_id, "Perf Upd06")
        try:
            r = auth_client.put(
                f"/activities/performance/{perf_id}",
                data=json.dumps({"name": "Nom sans desc"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)

    def test_update_nonexistent_has_error_field(self, auth_client):
        """La réponse 404 contient un champ 'error'."""
        r = auth_client.put(
            "/activities/performance/999999",
            data=json.dumps({"name": "Rien"}),
            content_type="application/json",
        )
        data = json.loads(r.data)
        assert "error" in data


# ===========================================================================
# 3. DELETE /activities/performance/<perf_id>
# ===========================================================================

class TestActivitiesPerformanceDelete:

    def test_delete_existing_returns_200(self, auth_client, ids, app):
        """DELETE sur une performance existante → 200."""
        link_id, data_id = _make_link(app, ids, "del01")
        perf_id = _make_perf(app, link_id, "Perf Del01")
        r = auth_client.delete(f"/activities/performance/{perf_id}")
        assert r.status_code == 200
        _teardown(app, link_id=link_id, data_id=data_id)

    def test_delete_response_has_message(self, auth_client, ids, app):
        """La réponse DELETE contient un champ 'message' non vide."""
        link_id, data_id = _make_link(app, ids, "del02")
        perf_id = _make_perf(app, link_id, "Perf Del02")
        r = auth_client.delete(f"/activities/performance/{perf_id}")
        data = json.loads(r.data)
        assert "message" in data
        assert data["message"]
        _teardown(app, link_id=link_id, data_id=data_id)

    def test_delete_nonexistent_returns_404(self, auth_client):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete("/activities/performance/999999")
        assert r.status_code == 404

    def test_delete_nonexistent_has_error_field(self, auth_client):
        """La réponse 404 pour une suppression invalide contient un champ 'error'."""
        r = auth_client.delete("/activities/performance/999999")
        data = json.loads(r.data)
        assert "error" in data

    def test_delete_removes_from_db(self, auth_client, ids, app):
        """Après DELETE, la performance est absente de la base."""
        link_id, data_id = _make_link(app, ids, "del05")
        perf_id = _make_perf(app, link_id, "Perf Del05")
        auth_client.delete(f"/activities/performance/{perf_id}")
        with app.app_context():
            from Code.models.models import Performance
            assert Performance.query.get(perf_id) is None
        _teardown(app, link_id=link_id, data_id=data_id)

    def test_double_delete_second_returns_404(self, auth_client, ids, app):
        """Supprimer deux fois la même performance → le 2ème DELETE retourne 404."""
        link_id, data_id = _make_link(app, ids, "del06")
        perf_id = _make_perf(app, link_id, "Perf Del06")
        auth_client.delete(f"/activities/performance/{perf_id}")
        r = auth_client.delete(f"/activities/performance/{perf_id}")
        assert r.status_code == 404
        _teardown(app, link_id=link_id, data_id=data_id)

    def test_delete_then_readd_creates_new_201(self, auth_client, ids, app):
        """Supprimer puis re-créer une performance pour le même lien → 201."""
        link_id, data_id = _make_link(app, ids, "del07")
        perf_id = _make_perf(app, link_id, "Perf à supprimer puis recréer")
        auth_client.delete(f"/activities/performance/{perf_id}")
        try:
            r = auth_client.post(
                "/activities/performance/add",
                data=json.dumps({"link_id": link_id, "name": "Recréée"}),
                content_type="application/json",
            )
            assert r.status_code == 201
        finally:
            _teardown(app, link_id=link_id, data_id=data_id)
