# tests/test_15_activities_map.py
"""
Page : Cartographie des activités (/activities/map)
Couvre : page principale, API entités (CRUD, activation), SVG/VSDX serving,
         connexions (liste/suppression/effacement), resync, cross-carto,
         upload cartographie, cas limites et sécurité.
"""
import io
import json
import pytest

pytestmark = pytest.mark.activities_map

# ── SVG minimal valide pour les tests d'upload ────────────────────────────────
MINIMAL_SVG = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
  <rect x="50" y="50" width="100" height="60" fill="#eee"/>
  <text x="100" y="85">Test Activite</text>
</svg>"""


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _set_owner(app, ids):
    """S'assure que l'entité test a bien owner_id = user de test."""
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        entity = Entity.query.get(ids["entity_id"])
        if entity and entity.owner_id != ids["user_id"]:
            entity.owner_id = ids["user_id"]
            db.session.commit()


def _set_active_session(client, ids):
    """Force active_entity_id dans la session Flask de test."""
    with client.session_transaction() as sess:
        sess["user_id"] = ids["user_id"]
        sess["active_entity_id"] = ids["entity_id"]


def _create_entity(app, user_id, name="Entité MapTest"):
    """Crée une entité en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        e = Entity(name=name, description="Entité pour test map", owner_id=user_id)
        db.session.add(e)
        db.session.commit()
        return e.id


def _delete_entity(app, entity_id):
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        e = Entity.query.get(entity_id)
        if e:
            db.session.delete(e)
            db.session.commit()


def _create_link(app, ids):
    """Crée une connexion activité→activité pour l'entité test et retourne son id."""
    with app.app_context():
        from Code.models.models import Link, Activities
        from Code.extensions import db
        acts = Activities.query.filter_by(entity_id=ids["entity_id"]).all()
        if len(acts) < 2:
            # Créer une deuxième activité si nécessaire
            a2 = Activities(entity_id=ids["entity_id"], name="Activité Map2", description="")
            db.session.add(a2)
            db.session.flush()
            acts = Activities.query.filter_by(entity_id=ids["entity_id"]).all()
        link = Link(
            entity_id=ids["entity_id"],
            source_activity_id=acts[0].id,
            target_activity_id=acts[-1].id,
            type="nourrissante",
        )
        db.session.add(link)
        db.session.commit()
        return link.id


# ── Module fixture : propriété entité + session auth ─────────────────────────

@pytest.fixture(scope="module", autouse=True)
def _setup_module(app, client, ids):
    """Configure la session et l'ownership de l'entité avant les tests du module."""
    with app.app_context():
        from Code.models.models import User, Entity
        from Code.extensions import db
        user = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.get(ids["entity_id"])
        entity.owner_id = user.id
        db.session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = ids["user_id"]
        sess["active_entity_id"] = ids["entity_id"]

    yield


# ===========================================================================
# 1. Page principale /activities/map
# ===========================================================================

class TestActivitiesMapPage:

    def test_page_accessible_auth(self, auth_client):
        """GET /activities/map répond 200 pour un utilisateur authentifié."""
        r = auth_client.get("/activities/map")
        assert r.status_code == 200

    def test_page_contains_entity_section(self, auth_client):
        """La page inclut une section entité (carte ou wizard)."""
        r = auth_client.get("/activities/map")
        assert r.status_code == 200
        # Vérifie qu'une référence aux entités est présente dans le HTML
        assert b"ntit" in r.data  # "Entité" ou "entités"

    def test_page_unauthenticated_no_crash(self, client):
        """GET /activities/map sans session ne génère pas d'erreur 500."""
        # Vider la session pour simuler un visiteur non connecté
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/activities/map")
        assert r.status_code in (200, 302)

    def test_page_debug_files_auth(self, auth_client, ids):
        """GET /activities/debug/files répond 200 et retourne un JSON valide."""
        # Restore session after previous test may have cleared it
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/debug/files")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "entities_dir" in data

    def test_update_cartography_route(self, auth_client):
        """GET /activities/update-cartography répond 200."""
        r = auth_client.get("/activities/update-cartography")
        assert r.status_code == 200


# ===========================================================================
# 2. API Entités — liste et détails
# ===========================================================================

class TestEntityAPIRead:

    def test_list_entities_auth(self, auth_client, ids):
        """GET /activities/api/entities retourne une liste JSON avec l'entité test."""
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/api/entities")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        assert any(e["id"] == ids["entity_id"] for e in data)

    def test_list_entities_no_auth(self, client):
        """GET /activities/api/entities sans session retourne une liste vide."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/activities/api/entities")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_entity_details_auth(self, auth_client, ids):
        """GET /activities/api/entities/<id>/details retourne les détails de l'entité."""
        _set_active_session(auth_client, ids)
        r = auth_client.get(f"/activities/api/entities/{ids['entity_id']}/details")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["id"] == ids["entity_id"]
        assert "activities_count" in data
        assert "connections_count" in data

    def test_entity_details_not_found(self, auth_client, ids):
        """GET /activities/api/entities/99999/details retourne 404 si inconnue."""
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/api/entities/99999/details")
        assert r.status_code == 404

    def test_entity_details_no_auth(self, client):
        """GET /activities/api/entities/<id>/details sans session retourne 401."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/activities/api/entities/1/details")
        assert r.status_code == 401


# ===========================================================================
# 3. API Entités — création
# ===========================================================================

class TestEntityAPICreate:

    def test_create_entity_ok(self, auth_client, ids):
        """POST /activities/api/entities crée une entité et retourne son id."""
        _set_active_session(auth_client, ids)
        r = auth_client.post(
            "/activities/api/entities",
            data=json.dumps({"name": "Nouvelle Entité Test", "description": "Desc auto"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"
        assert "entity" in data
        new_id = data["entity"]["id"]
        assert new_id is not None
        # Nettoyage
        _delete_entity(auth_client.application, new_id)

    def test_create_entity_missing_name(self, auth_client, ids):
        """POST /activities/api/entities sans nom retourne 400."""
        _set_active_session(auth_client, ids)
        r = auth_client.post(
            "/activities/api/entities",
            data=json.dumps({"description": "Pas de nom"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_create_entity_empty_body(self, auth_client, ids):
        """POST /activities/api/entities avec body vide retourne 400."""
        _set_active_session(auth_client, ids)
        r = auth_client.post(
            "/activities/api/entities",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ===========================================================================
# 4. API Entités — activation, mise à jour, suppression
# ===========================================================================

class TestEntityAPIMutations:

    def test_activate_entity_ok(self, app, auth_client, ids):
        """POST /activities/api/entities/<id>/activate change l'entité active."""
        new_eid = _create_entity(app, ids["user_id"], name="Entité À Activer")
        _set_active_session(auth_client, ids)
        r = auth_client.post(f"/activities/api/entities/{new_eid}/activate")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"
        _delete_entity(app, new_eid)

    def test_activate_entity_not_found(self, auth_client, ids):
        """POST /activities/api/entities/99999/activate retourne 404."""
        _set_active_session(auth_client, ids)
        r = auth_client.post("/activities/api/entities/99999/activate")
        assert r.status_code == 404

    def test_activate_entity_no_auth(self, client):
        """POST /activities/api/entities/<id>/activate sans session retourne 401."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.post("/activities/api/entities/1/activate")
        assert r.status_code == 401

    def test_update_entity_name(self, app, auth_client, ids):
        """PATCH /activities/api/entities/<id> renomme l'entité."""
        new_eid = _create_entity(app, ids["user_id"], name="Entité Avant PATCH")
        _set_active_session(auth_client, ids)
        r = auth_client.patch(
            f"/activities/api/entities/{new_eid}",
            data=json.dumps({"name": "Entité Après PATCH"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["entity"]["name"] == "Entité Après PATCH"
        _delete_entity(app, new_eid)

    def test_update_entity_not_found(self, auth_client, ids):
        """PATCH /activities/api/entities/99999 retourne 404."""
        _set_active_session(auth_client, ids)
        r = auth_client.patch(
            "/activities/api/entities/99999",
            data=json.dumps({"name": "Ghost"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_entity_no_auth(self, client):
        """PATCH /activities/api/entities/<id> sans session retourne 401."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.patch(
            "/activities/api/entities/1",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 401

    def test_delete_entity_ok(self, app, auth_client, ids):
        """DELETE /activities/api/entities/<id> supprime l'entité."""
        new_eid = _create_entity(app, ids["user_id"], name="Entité À Supprimer")
        _set_active_session(auth_client, ids)
        r = auth_client.delete(f"/activities/api/entities/{new_eid}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"

    def test_delete_entity_not_found(self, auth_client, ids):
        """DELETE /activities/api/entities/99999 retourne 404."""
        _set_active_session(auth_client, ids)
        r = auth_client.delete("/activities/api/entities/99999")
        assert r.status_code == 404

    def test_delete_entity_no_auth(self, client):
        """DELETE /activities/api/entities/<id> sans session retourne 401."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.delete("/activities/api/entities/1")
        assert r.status_code == 401


# ===========================================================================
# 5. SVG — serving
# ===========================================================================

class TestSVGServing:

    def test_serve_svg_no_file_returns_404(self, auth_client, ids):
        """GET /activities/svg retourne 404 si aucun SVG n'existe pour l'entité."""
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/svg")
        # L'entité test n'a pas de SVG ; on attend 404
        assert r.status_code == 404

    def test_serve_svg_no_active_entity(self, client):
        """GET /activities/svg sans entité active retourne 404."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/activities/svg")
        assert r.status_code == 404

    def test_serve_entity_svg_not_found(self, auth_client, ids):
        """GET /activities/api/svg/99999 retourne 404 si entité inconnue."""
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/api/svg/99999")
        assert r.status_code == 404

    def test_serve_entity_svg_no_svg(self, auth_client, ids):
        """GET /activities/api/svg/<id> retourne 404 si l'entité n'a pas de SVG."""
        _set_active_session(auth_client, ids)
        r = auth_client.get(f"/activities/api/svg/{ids['entity_id']}")
        assert r.status_code == 404

    def test_serve_entity_svg_from_db(self, app, auth_client, ids):
        """GET /activities/api/svg/<id> sert le SVG depuis DB si svg_content est défini."""
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            entity = Entity.query.get(ids["entity_id"])
            entity.svg_content = MINIMAL_SVG.decode("utf-8")
            db.session.commit()

        _set_active_session(auth_client, ids)
        r = auth_client.get(f"/activities/api/svg/{ids['entity_id']}")
        assert r.status_code == 200
        assert b"svg" in r.data.lower()

        # Nettoyage
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            entity = Entity.query.get(ids["entity_id"])
            entity.svg_content = None
            db.session.commit()


# ===========================================================================
# 6. Connexions — liste, suppression, effacement
# ===========================================================================

class TestConnectionAPI:

    def test_list_connections_empty(self, auth_client, ids):
        """GET /activities/list-connections retourne une liste vide si aucune connexion."""
        _set_active_session(auth_client, ids)
        # Vider les connexions de l'entité test avant ce test
        with auth_client.application.app_context():
            from Code.models.models import Link
            from Code.extensions import db
            Link.query.filter_by(entity_id=ids["entity_id"]).delete()
            db.session.commit()
        r = auth_client.get("/activities/list-connections")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"
        assert data["connections"] == []

    def test_list_connections_with_data(self, app, auth_client, ids):
        """GET /activities/list-connections retourne les connexions existantes."""
        link_id = _create_link(app, ids)
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/list-connections")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["count"] >= 1
        assert any(c["id"] == link_id for c in data["connections"])

    def test_delete_connection_ok(self, app, auth_client, ids):
        """DELETE /activities/delete-connection/<id> supprime la connexion."""
        link_id = _create_link(app, ids)
        _set_active_session(auth_client, ids)
        r = auth_client.delete(f"/activities/delete-connection/{link_id}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"

    def test_delete_connection_not_found(self, auth_client, ids):
        """DELETE /activities/delete-connection/99999 retourne 404."""
        _set_active_session(auth_client, ids)
        r = auth_client.delete("/activities/delete-connection/99999")
        assert r.status_code == 404

    def test_clear_connections(self, app, auth_client, ids):
        """DELETE /activities/clear-connections supprime toutes les connexions de l'entité."""
        _create_link(app, ids)
        _set_active_session(auth_client, ids)
        r = auth_client.delete("/activities/clear-connections")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"
        assert data["deleted"] >= 0

    def test_clear_connections_no_entity(self, client):
        """DELETE /activities/clear-connections sans entité active retourne 200 avec deleted=0."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.delete("/activities/clear-connections")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["deleted"] == 0


# ===========================================================================
# 7. Upload cartographie
# ===========================================================================

class TestUploadCartography:

    def test_upload_svg_ok(self, auth_client, ids):
        """POST /activities/upload-cartography avec SVG valide retourne status ok."""
        _set_active_session(auth_client, ids)
        svg_io = io.BytesIO(MINIMAL_SVG)
        r = auth_client.post(
            "/activities/upload-cartography",
            data={
                "entity_id": ids["entity_id"],
                "mode": "new",
                "svg_file": (svg_io, "test.svg"),
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"

    def test_upload_wrong_extension(self, auth_client, ids):
        """POST /activities/upload-cartography avec un PNG retourne 400."""
        _set_active_session(auth_client, ids)
        r = auth_client.post(
            "/activities/upload-cartography",
            data={
                "entity_id": ids["entity_id"],
                "mode": "new",
                "svg_file": (io.BytesIO(b"fake"), "image.png"),
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_upload_mode_new_no_svg(self, auth_client, ids):
        """POST /activities/upload-cartography en mode 'new' sans SVG retourne 400."""
        _set_active_session(auth_client, ids)
        r = auth_client.post(
            "/activities/upload-cartography",
            data={"entity_id": ids["entity_id"], "mode": "new"},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_upload_entity_not_found(self, auth_client, ids):
        """POST /activities/upload-cartography avec entity_id invalide retourne 404."""
        _set_active_session(auth_client, ids)
        svg_io = io.BytesIO(MINIMAL_SVG)
        r = auth_client.post(
            "/activities/upload-cartography",
            data={
                "entity_id": 99999,
                "mode": "new",
                "svg_file": (svg_io, "test.svg"),
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 404

    def test_upload_wrong_vsdx_extension(self, auth_client, ids):
        """POST /activities/upload-cartography avec VSDX invalide (mauvaise ext) retourne 400."""
        _set_active_session(auth_client, ids)
        svg_io = io.BytesIO(MINIMAL_SVG)
        r = auth_client.post(
            "/activities/upload-cartography",
            data={
                "entity_id": ids["entity_id"],
                "mode": "update",
                "keep_svg": "true",
                "vsdx_file": (io.BytesIO(b"fake"), "connections.zip"),
            },
            content_type="multipart/form-data",
        )
        assert r.status_code == 400


# ===========================================================================
# 8. Resync
# ===========================================================================

class TestResync:

    def test_resync_no_svg(self, auth_client, ids):
        """POST /activities/resync sans SVG retourne 404."""
        _set_active_session(auth_client, ids)
        # S'assurer qu'aucun SVG n'est présent (pas de svg_content)
        with auth_client.application.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            entity = Entity.query.get(ids["entity_id"])
            entity.svg_content = None
            entity.svg_filename = None
            db.session.commit()
        r = auth_client.post("/activities/resync")
        assert r.status_code == 404

    def test_resync_no_entity(self, client):
        """POST /activities/resync sans entité active retourne 400."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.post("/activities/resync")
        assert r.status_code == 400


# ===========================================================================
# 9. Cross-carto matches
# ===========================================================================

class TestCrossCartoMatches:

    def test_cross_carto_no_auth(self, client):
        """GET /activities/api/cross_carto_matches sans session retourne matches vide."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/activities/api/cross_carto_matches")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["matches"] == []

    def test_cross_carto_auth_no_matches(self, auth_client, ids):
        """GET /activities/api/cross_carto_matches retourne 200 avec structure valide."""
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/api/cross_carto_matches")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "matches" in data
        assert "total" in data

    def test_cross_carto_returns_list(self, auth_client, ids):
        """GET /activities/api/cross_carto_matches retourne une liste de correspondances."""
        _set_active_session(auth_client, ids)
        r = auth_client.get("/activities/api/cross_carto_matches")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data["matches"], list)


# ===========================================================================
# 10. Preview connexions VSDX
# ===========================================================================

class TestPreviewConnections:

    def test_preview_no_file(self, auth_client, ids):
        """POST /activities/preview-connections sans fichier retourne 400."""
        _set_active_session(auth_client, ids)
        r = auth_client.post(
            "/activities/preview-connections",
            data={},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400

    def test_preview_wrong_extension(self, auth_client, ids):
        """POST /activities/preview-connections avec un SVG retourne 400 (VSDX requis)."""
        _set_active_session(auth_client, ids)
        r = auth_client.post(
            "/activities/preview-connections",
            data={"file": (io.BytesIO(b"fake"), "diagram.svg")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
