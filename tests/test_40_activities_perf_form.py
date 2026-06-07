# tests/test_40_activities_perf_form.py
"""
Couverture des routes performance via activities_bp (Code/routes/activities_form.py) :
  - POST   /activities/performance/add    → upsert : crée si absent, met à jour si présent
  - PUT    /activities/performance/<id>   → mise à jour par ID de performance
  - DELETE /activities/performance/<id>  → suppression par ID de performance

Ces routes sont distinctes de performance_bp (/performance/...) par leur préfixe
/activities/ et leur comportement upsert sur POST.
"""
import json
import pytest

pytestmark = pytest.mark.activities_perf_form


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_link(app, entity_id, activity_id, label="Lien-Form"):
    """Crée un Data + Link isolés ; retourne link_id."""
    with app.app_context():
        from Code.models.models import Data, Link
        from Code.extensions import db
        d = Data(entity_id=entity_id, name=f"Data-{label}", type="nourrissante")
        db.session.add(d)
        db.session.flush()
        lnk = Link(
            entity_id=entity_id,
            source_data_id=d.id,
            target_activity_id=activity_id,
            type="nourrissante",
        )
        db.session.add(lnk)
        db.session.commit()
        return lnk.id


def _create_link_with_perf(app, entity_id, activity_id, perf_name="Perf-Init", label="Lien-Perf"):
    """Crée Data + Link + Performance ; retourne (link_id, perf_id)."""
    with app.app_context():
        from Code.models.models import Data, Link, Performance
        from Code.extensions import db
        d = Data(entity_id=entity_id, name=f"Data-{label}", type="nourrissante")
        db.session.add(d)
        db.session.flush()
        lnk = Link(
            entity_id=entity_id,
            source_data_id=d.id,
            target_activity_id=activity_id,
            type="nourrissante",
        )
        db.session.add(lnk)
        db.session.flush()
        perf = Performance(link_id=lnk.id, name=perf_name, description="Init")
        db.session.add(perf)
        db.session.commit()
        return lnk.id, perf.id


def _cleanup(app, link_id):
    """Supprime Performance (si existe) + Link + Data associé."""
    with app.app_context():
        from Code.models.models import Link, Performance, Data
        from Code.extensions import db
        lnk = Link.query.get(link_id)
        if lnk:
            p = Performance.query.filter_by(link_id=link_id).first()
            if p:
                db.session.delete(p)
                db.session.flush()
            did = lnk.source_data_id
            db.session.delete(lnk)
            db.session.flush()
            if did:
                d = Data.query.get(did)
                if d:
                    db.session.delete(d)
            db.session.commit()


def _cleanup_link_only(app, link_id):
    """Supprime Link + Data sans toucher à la Performance (déjà supprimée)."""
    with app.app_context():
        from Code.models.models import Link, Data
        from Code.extensions import db
        lnk = Link.query.get(link_id)
        if lnk:
            did = lnk.source_data_id
            db.session.delete(lnk)
            db.session.flush()
            if did:
                d = Data.query.get(did)
                if d:
                    db.session.delete(d)
            db.session.commit()


def _post_add(client, link_id, name, description=""):
    return client.post(
        "/activities/performance/add",
        data=json.dumps({"link_id": link_id, "name": name, "description": description}),
        content_type="application/json",
    )


def _put_perf(client, perf_id, name, description=""):
    return client.put(
        f"/activities/performance/{perf_id}",
        data=json.dumps({"name": name, "description": description}),
        content_type="application/json",
    )


# ===========================================================================
# 1. POST /activities/performance/add  (upsert)
# ===========================================================================

class TestActivitiesPerformanceAdd:

    def test_add_creates_performance_returns_201(self, auth_client, ids, app):
        """Premier POST sur un link vide → 201 + id entier dans la réponse."""
        lnk = _create_link(app, ids["entity_id"], ids["activity_id"], "Add-Create")
        try:
            r = _post_add(auth_client, lnk, "Perf Création", "Test desc")
            assert r.status_code == 201
            data = r.get_json()
            assert isinstance(data.get("id"), int)
        finally:
            _cleanup(app, lnk)

    def test_add_performance_is_persisted(self, auth_client, ids, app):
        """La Performance créée est bien en base après le POST."""
        lnk = _create_link(app, ids["entity_id"], ids["activity_id"], "Add-Persist")
        try:
            r = _post_add(auth_client, lnk, "Perf Persistée")
            perf_id = r.get_json().get("id")
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p is not None
                assert p.name == "Perf Persistée"
                assert p.link_id == lnk
        finally:
            _cleanup(app, lnk)

    def test_add_without_description_returns_201(self, auth_client, ids, app):
        """POST sans champ 'description' → 201 (champ optionnel)."""
        lnk = _create_link(app, ids["entity_id"], ids["activity_id"], "Add-NoDesc")
        try:
            r = _post_add(auth_client, lnk, "Perf Sans Desc")
            assert r.status_code == 201
        finally:
            _cleanup(app, lnk)

    def test_add_upserts_when_performance_exists(self, auth_client, ids, app):
        """Second POST sur le même link → 200 (mise à jour) au lieu d'un 409."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Perf Initiale", "Add-Upsert"
        )
        try:
            r = _post_add(auth_client, lnk, "Perf Remplacée")
            assert r.status_code == 200
            data = r.get_json()
            assert isinstance(data.get("id"), int)
            assert data["id"] == perf_id
        finally:
            _cleanup(app, lnk)

    def test_add_upsert_updates_name_in_db(self, auth_client, ids, app):
        """Après upsert, le nouveau nom est bien stocké en base."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Ancien Nom", "Add-Upsert-Name"
        )
        try:
            _post_add(auth_client, lnk, "Nouveau Nom")
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p.name == "Nouveau Nom"
        finally:
            _cleanup(app, lnk)

    def test_add_response_contains_message(self, auth_client, ids, app):
        """La réponse contient un champ 'message'."""
        lnk = _create_link(app, ids["entity_id"], ids["activity_id"], "Add-Msg")
        try:
            r = _post_add(auth_client, lnk, "Perf Msg")
            assert "message" in r.get_json()
        finally:
            _cleanup(app, lnk)


# ===========================================================================
# 2. PUT /activities/performance/<id>
# ===========================================================================

class TestActivitiesPerformanceUpdate:

    def test_update_returns_200(self, auth_client, ids, app):
        """PUT sur une performance existante → 200."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Perf Upd Init", "Upd-200"
        )
        try:
            r = _put_perf(auth_client, perf_id, "Nom modifié", "Desc modifiée")
            assert r.status_code == 200
        finally:
            _cleanup(app, lnk)

    def test_update_persists_new_values(self, auth_client, ids, app):
        """Après PUT, le nom et la description sont mis à jour en base."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Ancien", "Upd-Persist"
        )
        try:
            _put_perf(auth_client, perf_id, "Nouveau Nom", "Nouvelle Desc")
            with app.app_context():
                from Code.models.models import Performance
                p = Performance.query.get(perf_id)
                assert p.name == "Nouveau Nom"
                assert p.description == "Nouvelle Desc"
        finally:
            _cleanup(app, lnk)

    def test_update_nonexistent_returns_404(self, auth_client):
        """PUT sur un ID inexistant → 404."""
        r = _put_perf(auth_client, 999999, "Ghost", "")
        assert r.status_code == 404
        assert "error" in r.get_json()

    def test_update_response_contains_message(self, auth_client, ids, app):
        """La réponse contient un champ 'message'."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Perf Msg Upd", "Upd-Msg"
        )
        try:
            r = _put_perf(auth_client, perf_id, "Perf avec message", "")
            assert "message" in r.get_json()
        finally:
            _cleanup(app, lnk)


# ===========================================================================
# 3. DELETE /activities/performance/<id>
# ===========================================================================

class TestActivitiesPerformanceDelete:

    def test_delete_returns_200(self, auth_client, ids, app):
        """DELETE sur une performance existante → 200."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Perf Del", "Del-200"
        )
        try:
            r = auth_client.delete(f"/activities/performance/{perf_id}")
            assert r.status_code == 200
        finally:
            _cleanup_link_only(app, lnk)

    def test_delete_removes_from_db(self, auth_client, ids, app):
        """Après DELETE, la Performance n'existe plus en base."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Perf Del DB", "Del-DB"
        )
        try:
            auth_client.delete(f"/activities/performance/{perf_id}")
            with app.app_context():
                from Code.models.models import Performance
                assert Performance.query.get(perf_id) is None
        finally:
            _cleanup_link_only(app, lnk)

    def test_delete_nonexistent_returns_404(self, auth_client):
        """DELETE sur un ID inexistant → 404."""
        r = auth_client.delete("/activities/performance/999999")
        assert r.status_code == 404
        assert "error" in r.get_json()

    def test_delete_response_contains_message(self, auth_client, ids, app):
        """La réponse de suppression contient un champ 'message'."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Perf Del Msg", "Del-Msg"
        )
        try:
            r = auth_client.delete(f"/activities/performance/{perf_id}")
            assert "message" in r.get_json()
        finally:
            _cleanup_link_only(app, lnk)

    def test_delete_is_not_idempotent(self, auth_client, ids, app):
        """Premier DELETE → 200 ; second DELETE sur le même ID → 404."""
        lnk, perf_id = _create_link_with_perf(
            app, ids["entity_id"], ids["activity_id"], "Perf Del Idem", "Del-Idem"
        )
        try:
            r1 = auth_client.delete(f"/activities/performance/{perf_id}")
            r2 = auth_client.delete(f"/activities/performance/{perf_id}")
            assert r1.status_code == 200
            assert r2.status_code == 404
        finally:
            _cleanup_link_only(app, lnk)
