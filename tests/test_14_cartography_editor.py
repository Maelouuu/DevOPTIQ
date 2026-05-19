# tests/test_14_cartography_editor.py
"""
Page : Éditeur OptiqCarto (/cartography)
Couvre : pages viewer/editor, API save/load/list/delete/save-diff,
         synchronisation DB (activités, rôles, liens), cas limites VSDX.
"""
import io
import json
import pytest

pytestmark = pytest.mark.cartography_editor

# ── Diagrammes de référence ───────────────────────────────────────────────────

EMPTY_DIAGRAM = {"shapes": [], "bands": [], "connections": []}

DIAGRAM_ONE_ACTIVITY = {
    "shapes": [
        {"id": "s1", "type": "process", "label": "Activité Carto",
         "x": 100, "y": 0, "w": 120, "h": 60},
    ],
    "bands":  [{"id": "b1", "label": "Bande Test", "height": 180}],
    "connections": [],
}

DIAGRAM_TWO_CONNECTED = {
    "shapes": [
        {"id": "s1", "type": "process", "label": "Source Carto",
         "x": 100, "y": 0, "w": 120, "h": 60},
        {"id": "s2", "type": "process", "label": "Cible Carto",
         "x": 300, "y": 0, "w": 120, "h": 60},
    ],
    "bands":  [{"id": "b1", "label": "Bande Conn", "height": 180}],
    "connections": [{"fromId": "s1", "toId": "s2", "label": "flux test"}],
}


# ── Helpers DB ────────────────────────────────────────────────────────────────

def _set_owner(app, ids):
    """Set owner_id so _get_active_entity() can resolve the test entity."""
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        entity = Entity.query.get(ids["entity_id"])
        if entity and entity.owner_id != ids["user_id"]:
            entity.owner_id = ids["user_id"]
            db.session.commit()


def _set_carto(app, ids, data):
    """Force-set optiqcarto_data without triggering DB sync."""
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        entity = Entity.query.get(ids["entity_id"])
        entity.optiqcarto_data = json.dumps(data) if data is not None else None
        db.session.commit()


def _get_carto(app, ids):
    with app.app_context():
        from Code.models.models import Entity
        entity = Entity.query.get(ids["entity_id"])
        if entity and entity.optiqcarto_data:
            return json.loads(entity.optiqcarto_data)
        return None


def _clear_shape_activities(app, ids):
    """Delete all activities with shape_id for the test entity (clean slate for sync tests)."""
    with app.app_context():
        from Code.models.models import Activities, activity_roles
        from Code.extensions import db
        acts = Activities.query.filter_by(entity_id=ids["entity_id"]).filter(
            Activities.shape_id.isnot(None)
        ).all()
        if acts:
            ids_to_del = [a.id for a in acts]
            db.session.execute(
                activity_roles.delete().where(activity_roles.c.activity_id.in_(ids_to_del))
            )
            for a in acts:
                db.session.delete(a)
            db.session.commit()


# ── Module-level fixture : re-auth + entity ownership ─────────────────────────

@pytest.fixture(scope="module", autouse=True)
def _setup_module(app, client, ids):
    """Re-authenticate client (session may have been cleared by test_01 logout)
    and ensure the test entity has owner_id so cartography routes work."""
    with app.app_context():
        from Code.models.models import User, Entity
        from Code.extensions import db
        user   = User.query.filter_by(email="test@devoptiq.com").first()
        entity = Entity.query.get(ids["entity_id"])
        entity.owner_id = ids["user_id"]
        db.session.commit()
        u_id   = user.id
        u_mail = user.email
        e_id   = entity.id

    with client.session_transaction() as sess:
        sess["user_id"]         = u_id
        sess["user_email"]      = u_mail
        sess["active_entity_id"] = e_id

    yield

    # Cleanup: remove carto data so other tests are not polluted
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        entity = Entity.query.get(ids["entity_id"])
        if entity:
            entity.optiqcarto_data = None
            db.session.commit()


# ===========================================================================
# 1. Accès sans authentification (client vierge)
# ===========================================================================

class TestCartographyNoAuth:
    """Toutes les routes refusent les requêtes sans session."""

    @pytest.fixture
    def anon(self, app):
        return app.test_client()

    def test_viewer_returns_403(self, anon):
        r = anon.get("/cartography/viewer")
        assert r.status_code == 403

    def test_editor_redirects_to_login(self, anon):
        r = anon.get("/cartography/editor")
        assert r.status_code == 302

    def test_api_save_returns_403(self, anon):
        r = anon.post("/cartography/api/save", json=EMPTY_DIAGRAM)
        assert r.status_code == 403

    def test_api_load_returns_403(self, anon):
        r = anon.get("/cartography/api/load/test")
        assert r.status_code == 403

    def test_api_list_returns_403(self, anon):
        r = anon.get("/cartography/api/list")
        assert r.status_code == 403

    def test_api_delete_returns_403(self, anon):
        r = anon.delete("/cartography/api/delete/test")
        assert r.status_code == 403

    def test_api_vsdx_returns_403(self, anon):
        r = anon.get("/cartography/api/vsdx")
        assert r.status_code == 403

    def test_api_save_diff_returns_403(self, anon):
        r = anon.post("/cartography/api/save-diff", json=EMPTY_DIAGRAM)
        assert r.status_code == 403

    def test_api_vsdx_compare_returns_403(self, anon):
        r = anon.post("/cartography/api/vsdx-compare", data={})
        assert r.status_code == 403


# ===========================================================================
# 2. Pages HTML (authentifié)
# ===========================================================================

class TestCartographyPages:
    """Les pages editor et viewer sont accessibles à un utilisateur authentifié."""

    def test_editor_page_returns_200(self, auth_client):
        r = auth_client.get("/cartography/editor")
        assert r.status_code == 200

    def test_viewer_page_returns_200(self, auth_client):
        r = auth_client.get("/cartography/viewer")
        assert r.status_code == 200

    def test_editor_page_contains_cartography_content(self, auth_client):
        r = auth_client.get("/cartography/editor")
        html = r.data.decode()
        assert any(kw in html.lower() for kw in ("cartography", "optiqcarto", "editor", "carto"))


# ===========================================================================
# 3. API save
# ===========================================================================

class TestCartoApiSave:
    """Sauvegarde de diagramme : persistance JSON + synchronisation DB."""

    def test_save_empty_diagram_returns_ok(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/save", json=EMPTY_DIAGRAM)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_save_returns_entity_name_in_response(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/save", json=EMPTY_DIAGRAM)
        assert "name" in r.get_json()

    def test_save_persists_json_to_db(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=EMPTY_DIAGRAM)
        assert _get_carto(app, ids) is not None

    def test_save_accepts_diagram_wrapper_format(self, auth_client, app, ids):
        """Format {diagram: {...}} est équivalent au JSON direct."""
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/save", json={"diagram": EMPTY_DIAGRAM})
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_save_creates_activity_in_db(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=DIAGRAM_ONE_ACTIVITY)
        with app.app_context():
            from Code.models.models import Activities
            act = Activities.query.filter_by(
                entity_id=ids["entity_id"], shape_id="s1"
            ).first()
        assert act is not None
        assert act.name == "Activité Carto"

    def test_save_creates_role_in_db(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=DIAGRAM_ONE_ACTIVITY)
        with app.app_context():
            from Code.models.models import Role
            role = Role.query.filter_by(
                entity_id=ids["entity_id"], name="Bande Test"
            ).first()
        assert role is not None

    def test_save_creates_link_between_activities(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=DIAGRAM_TWO_CONNECTED)
        with app.app_context():
            from Code.models.models import Activities, Link
            src = Activities.query.filter_by(entity_id=ids["entity_id"], shape_id="s1").first()
            tgt = Activities.query.filter_by(entity_id=ids["entity_id"], shape_id="s2").first()
            lnk = None
            if src and tgt:
                lnk = Link.query.filter_by(
                    entity_id=ids["entity_id"],
                    source_activity_id=src.id,
                    target_activity_id=tgt.id,
                ).first()
        assert src is not None and tgt is not None
        assert lnk is not None
        assert lnk.description == "flux test"

    def test_save_updates_activity_label_on_re_save(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=DIAGRAM_ONE_ACTIVITY)
        renamed = {
            "shapes": [{"id": "s1", "type": "process", "label": "Nouveau Nom",
                        "x": 100, "y": 0, "w": 120, "h": 60}],
            "bands":  [{"id": "b1", "label": "Bande Test", "height": 180}],
            "connections": [],
        }
        auth_client.post("/cartography/api/save", json=renamed)
        with app.app_context():
            from Code.models.models import Activities
            act = Activities.query.filter_by(entity_id=ids["entity_id"], shape_id="s1").first()
        assert act is not None
        assert act.name == "Nouveau Nom"

    def test_save_removes_deleted_shape_from_db(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=DIAGRAM_ONE_ACTIVITY)
        auth_client.post("/cartography/api/save", json=EMPTY_DIAGRAM)
        with app.app_context():
            from Code.models.models import Activities
            act = Activities.query.filter_by(entity_id=ids["entity_id"], shape_id="s1").first()
        assert act is None

    def test_save_special_type_marked_as_result(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        diagram = {
            "shapes": [{"id": "s3", "type": "special", "label": "Résultat",
                        "x": 100, "y": 0, "w": 120, "h": 60}],
            "bands": [],
            "connections": [],
        }
        auth_client.post("/cartography/api/save", json=diagram)
        with app.app_context():
            from Code.models.models import Activities
            act = Activities.query.filter_by(entity_id=ids["entity_id"], shape_id="s3").first()
        assert act is not None
        assert act.is_result is True


# ===========================================================================
# 4. API load
# ===========================================================================

class TestCartoApiLoad:
    """Chargement de diagramme depuis la base."""

    def test_load_returns_404_when_no_data(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        r = auth_client.get("/cartography/api/load/any_name")
        assert r.status_code == 404

    def test_load_returns_stored_diagram(self, auth_client, app, ids):
        _set_carto(app, ids, EMPTY_DIAGRAM)
        r = auth_client.get("/cartography/api/load/any_name")
        assert r.status_code == 200
        assert "shapes" in r.get_json()

    def test_load_name_parameter_is_ignored(self, auth_client, app, ids):
        """Le paramètre name dans l'URL n'est pas filtrant : charge toujours la carto de l'entité."""
        _set_carto(app, ids, EMPTY_DIAGRAM)
        r1 = auth_client.get("/cartography/api/load/foo")
        r2 = auth_client.get("/cartography/api/load/bar")
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_load_returns_full_diagram_structure(self, auth_client, app, ids):
        _set_carto(app, ids, DIAGRAM_ONE_ACTIVITY)
        r = auth_client.get("/cartography/api/load/test")
        data = r.get_json()
        assert "shapes" in data
        assert "bands" in data
        assert "connections" in data


# ===========================================================================
# 5. API list
# ===========================================================================

class TestCartoApiList:
    """Listage des diagrammes disponibles pour l'entité."""

    def test_list_empty_when_no_carto_data(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        r = auth_client.get("/cartography/api/list")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_list_contains_one_entry_when_data_exists(self, auth_client, app, ids):
        _set_carto(app, ids, EMPTY_DIAGRAM)
        r = auth_client.get("/cartography/api/list")
        assert r.status_code == 200
        names = r.get_json()
        assert isinstance(names, list)
        assert len(names) == 1

    def test_list_entry_is_entity_name(self, auth_client, app, ids):
        _set_carto(app, ids, EMPTY_DIAGRAM)
        r = auth_client.get("/cartography/api/list")
        names = r.get_json()
        with app.app_context():
            from Code.models.models import Entity
            entity = Entity.query.get(ids["entity_id"])
            expected = entity.name or f"entity_{entity.id}"
        assert names[0] == expected


# ===========================================================================
# 6. API delete
# ===========================================================================

class TestCartoApiDelete:
    """Suppression du diagramme sauvegardé."""

    def test_delete_returns_ok(self, auth_client, app, ids):
        _set_carto(app, ids, EMPTY_DIAGRAM)
        r = auth_client.delete("/cartography/api/delete/anything")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_delete_clears_optiqcarto_data(self, auth_client, app, ids):
        _set_carto(app, ids, EMPTY_DIAGRAM)
        auth_client.delete("/cartography/api/delete/anything")
        assert _get_carto(app, ids) is None

    def test_delete_when_no_data_is_idempotent(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        r = auth_client.delete("/cartography/api/delete/anything")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


# ===========================================================================
# 7. API save-diff
# ===========================================================================

class TestCartoApiSaveDiff:
    """Calcul des suppressions prévues avant une sauvegarde."""

    def test_save_diff_empty_when_no_stored_carto(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/save-diff", json=EMPTY_DIAGRAM)
        assert r.status_code == 200
        data = r.get_json()
        assert data["removed_activities"] == []
        assert data["removed_roles"] == []

    def test_save_diff_detects_removed_activity(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        # Save diagram → optiqcarto_data set + activity created in DB
        auth_client.post("/cartography/api/save", json=DIAGRAM_ONE_ACTIVITY)
        # Diff against empty → activity detected as removed
        r = auth_client.post("/cartography/api/save-diff", json=EMPTY_DIAGRAM)
        assert r.status_code == 200
        assert "Activité Carto" in r.get_json()["removed_activities"]

    def test_save_diff_detects_removed_role(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=DIAGRAM_ONE_ACTIVITY)
        r = auth_client.post("/cartography/api/save-diff", json=EMPTY_DIAGRAM)
        assert "Bande Test" in r.get_json()["removed_roles"]

    def test_save_diff_no_removal_when_shapes_match(self, auth_client, app, ids):
        _clear_shape_activities(app, ids)
        _set_carto(app, ids, None)
        auth_client.post("/cartography/api/save", json=DIAGRAM_ONE_ACTIVITY)
        # Same diagram → nothing removed
        r = auth_client.post("/cartography/api/save-diff", json=DIAGRAM_ONE_ACTIVITY)
        data = r.get_json()
        assert "Activité Carto" not in data.get("removed_activities", [])


# ===========================================================================
# 8. API VSDX
# ===========================================================================

class TestCartoApiVsdx:
    """Accès au fichier VSDX et comparaison VSDX ↔ carto."""

    @pytest.fixture(scope="class", autouse=True)
    def _clear_vsdx(self, app, ids):
        with app.app_context():
            from Code.models.models import Entity
            from Code.extensions import db
            entity = Entity.query.get(ids["entity_id"])
            if entity:
                entity.vsdx_filename = None
                db.session.commit()

    def test_vsdx_returns_404_when_no_file(self, auth_client):
        r = auth_client.get("/cartography/api/vsdx")
        assert r.status_code == 404

    def test_vsdx_compare_returns_404_when_no_carto(self, auth_client, app, ids):
        _set_carto(app, ids, None)
        r = auth_client.post("/cartography/api/vsdx-compare", data={})
        assert r.status_code == 404

    def test_vsdx_compare_returns_400_when_no_file_in_request(self, auth_client, app, ids):
        _set_carto(app, ids, EMPTY_DIAGRAM)
        r = auth_client.post("/cartography/api/vsdx-compare", data={})
        assert r.status_code == 400
        assert "fichier" in r.get_json().get("error", "").lower()

    def test_vsdx_compare_returns_400_for_invalid_extension(self, auth_client, app, ids):
        _set_carto(app, ids, EMPTY_DIAGRAM)
        r = auth_client.post(
            "/cartography/api/vsdx-compare",
            data={"file": (io.BytesIO(b"not-a-vsdx"), "diagram.pdf")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert "invalide" in r.get_json().get("error", "").lower()
