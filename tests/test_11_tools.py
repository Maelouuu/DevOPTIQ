# tests/test_11_tools.py
"""
Pages : Gestion des outils (/gestion_outils) + API outils-tâches (/tools)
Couvre : accès page, CRUD complet, remplacement, usages, suppressions partielles.
"""
import pytest
import json

pytestmark = pytest.mark.tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_tool(app, ids, name="Outil Test", description=None):
    """Insère un outil en base et retourne son id."""
    with app.app_context():
        from Code.models.models import Tool
        from Code.extensions import db
        tool = Tool(name=name, entity_id=ids["entity_id"], description=description)
        db.session.add(tool)
        db.session.commit()
        return tool.id


def _delete_tool(app, tool_id):
    """Supprime un outil en base (nettoyage)."""
    with app.app_context():
        from Code.models.models import Tool
        from Code.extensions import db
        t = Tool.query.get(tool_id)
        if t:
            db.session.delete(t)
            db.session.commit()


# ===========================================================================
# 1. Accès à la page HTML
# ===========================================================================

class TestGestionOutilsPage:

    def test_page_accessible_auth(self, auth_client):
        """La page /gestion_outils/ répond 200 lorsqu'on est connecté."""
        r = auth_client.get("/gestion_outils/")
        assert r.status_code == 200

    def test_page_no_auth_returns_redirect_or_200(self, client):
        """Sans session, la page retourne 302 ou 200 (pas de crash)."""
        r = client.get("/gestion_outils/")
        assert r.status_code in (200, 302)


# ===========================================================================
# 2. API GET — liste des outils
# ===========================================================================

class TestListTools:

    def test_list_tools_returns_list(self, auth_client):
        """GET /gestion_outils/api/tools retourne un tableau JSON."""
        r = auth_client.get("/gestion_outils/api/tools")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_list_tools_contains_expected_fields(self, auth_client, app, ids):
        """Chaque outil retourné possède les champs id, name, usages."""
        tid = _create_tool(app, ids, name="Outil Champs Test")
        try:
            r = auth_client.get("/gestion_outils/api/tools")
            assert r.status_code == 200
            data = json.loads(r.data)
            found = next((t for t in data if t["id"] == tid), None)
            assert found is not None
            assert "id" in found
            assert "name" in found
            assert "usages" in found
        finally:
            _delete_tool(app, tid)

    def test_tools_all_endpoint_returns_list(self, auth_client):
        """GET /tools/all retourne aussi un tableau JSON (blueprint tools.py)."""
        r = auth_client.get("/tools/all")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)


# ===========================================================================
# 3. API POST — créer un outil
# ===========================================================================

class TestCreateTool:

    def test_create_tool_success(self, auth_client, app, ids):
        """POST /gestion_outils/api/tools crée un outil et retourne 201."""
        r = auth_client.post(
            "/gestion_outils/api/tools",
            data=json.dumps({"name": "Outil Créé Test", "description": "Desc test"}),
            content_type="application/json",
        )
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "id" in data
        _delete_tool(app, data["id"])

    def test_create_tool_empty_name_returns_400(self, auth_client):
        """Un nom vide doit retourner 400."""
        r = auth_client.post(
            "/gestion_outils/api/tools",
            data=json.dumps({"name": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_create_tool_missing_name_returns_400(self, auth_client):
        """Absence de champ name → 400."""
        r = auth_client.post(
            "/gestion_outils/api/tools",
            data=json.dumps({"description": "Sans nom"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_create_tool_duplicate_returns_409(self, auth_client, app, ids):
        """Créer deux outils avec le même nom → 409 au second."""
        tid = _create_tool(app, ids, name="Outil Doublon")
        try:
            r = auth_client.post(
                "/gestion_outils/api/tools",
                data=json.dumps({"name": "Outil Doublon"}),
                content_type="application/json",
            )
            assert r.status_code == 409
        finally:
            _delete_tool(app, tid)

    def test_create_tool_case_insensitive_duplicate(self, auth_client, app, ids):
        """La vérification de doublon est insensible à la casse."""
        tid = _create_tool(app, ids, name="Outil Majuscule")
        try:
            r = auth_client.post(
                "/gestion_outils/api/tools",
                data=json.dumps({"name": "outil majuscule"}),
                content_type="application/json",
            )
            assert r.status_code == 409
        finally:
            _delete_tool(app, tid)


# ===========================================================================
# 4. API PUT — modifier un outil
# ===========================================================================

class TestUpdateTool:

    def test_update_tool_name(self, auth_client, app, ids):
        """PUT /gestion_outils/api/tools/<id> renomme l'outil."""
        tid = _create_tool(app, ids, name="Outil À Renommer")
        try:
            r = auth_client.put(
                f"/gestion_outils/api/tools/{tid}",
                data=json.dumps({"name": "Outil Renommé"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _delete_tool(app, tid)

    def test_update_tool_description(self, auth_client, app, ids):
        """Modifier uniquement la description fonctionne."""
        tid = _create_tool(app, ids, name="Outil Desc Update")
        try:
            r = auth_client.put(
                f"/gestion_outils/api/tools/{tid}",
                data=json.dumps({"description": "Nouvelle description"}),
                content_type="application/json",
            )
            assert r.status_code == 200
        finally:
            _delete_tool(app, tid)

    def test_update_tool_empty_name_returns_400(self, auth_client, app, ids):
        """Un nom vide dans PUT → 400."""
        tid = _create_tool(app, ids, name="Outil Nom Vide")
        try:
            r = auth_client.put(
                f"/gestion_outils/api/tools/{tid}",
                data=json.dumps({"name": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_tool(app, tid)

    def test_update_tool_not_found(self, auth_client):
        """PUT sur un ID inexistant → 404."""
        r = auth_client.put(
            "/gestion_outils/api/tools/999999",
            data=json.dumps({"name": "Fantôme"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_tool_duplicate_name_returns_409(self, auth_client, app, ids):
        """Renommer avec un nom déjà pris → 409."""
        tid1 = _create_tool(app, ids, name="Outil Nom A")
        tid2 = _create_tool(app, ids, name="Outil Nom B")
        try:
            r = auth_client.put(
                f"/gestion_outils/api/tools/{tid2}",
                data=json.dumps({"name": "Outil Nom A"}),
                content_type="application/json",
            )
            assert r.status_code == 409
        finally:
            _delete_tool(app, tid1)
            _delete_tool(app, tid2)


# ===========================================================================
# 5. API GET — usages d'un outil
# ===========================================================================

class TestToolUsages:

    def test_usages_not_found(self, auth_client):
        """GET /gestion_outils/api/tools/<id>/usages sur ID inexistant → 404."""
        r = auth_client.get("/gestion_outils/api/tools/999999/usages")
        assert r.status_code == 404

    def test_usages_no_tasks(self, auth_client, app, ids):
        """Un outil sans tâches retourne une liste vide."""
        tid = _create_tool(app, ids, name="Outil Sans Tâche")
        try:
            r = auth_client.get(f"/gestion_outils/api/tools/{tid}/usages")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "tool" in data
            assert "usages" in data
            assert data["usages"] == []
        finally:
            _delete_tool(app, tid)

    def test_usages_with_task(self, auth_client, app, ids):
        """Un outil associé à une tâche apparaît dans ses usages."""
        tid = _create_tool(app, ids, name="Outil Avec Tâche")
        try:
            # Associer l'outil à la tâche test via l'API /tools/add
            auth_client.post(
                "/tools/add",
                data=json.dumps({
                    "task_id": ids["task_id"],
                    "existing_tool_ids": [tid],
                }),
                content_type="application/json",
            )
            r = auth_client.get(f"/gestion_outils/api/tools/{tid}/usages")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert len(data["usages"]) >= 1
        finally:
            # Détacher avant de supprimer
            auth_client.post(
                "/tools/delete",
                data=json.dumps({"task_id": ids["task_id"], "tool_id": tid}),
                content_type="application/json",
            )
            _delete_tool(app, tid)


# ===========================================================================
# 6. API POST — remplacer un outil par un autre
# ===========================================================================

class TestReplaceTool:

    def test_replace_tool_missing_replacement_id(self, auth_client, app, ids):
        """POST replace sans replacement_id → 400."""
        tid = _create_tool(app, ids, name="Outil Source Replace")
        try:
            r = auth_client.post(
                f"/gestion_outils/api/tools/{tid}/replace",
                data=json.dumps({}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_tool(app, tid)

    def test_replace_tool_replacement_not_found(self, auth_client, app, ids):
        """POST replace avec replacement_id inexistant → 404."""
        tid = _create_tool(app, ids, name="Outil Source 404")
        try:
            r = auth_client.post(
                f"/gestion_outils/api/tools/{tid}/replace",
                data=json.dumps({"replacement_id": 999999}),
                content_type="application/json",
            )
            assert r.status_code == 404
        finally:
            _delete_tool(app, tid)

    def test_replace_tool_self_returns_400(self, auth_client, app, ids):
        """Remplacer un outil par lui-même → 400."""
        tid = _create_tool(app, ids, name="Outil Auto Replace")
        try:
            r = auth_client.post(
                f"/gestion_outils/api/tools/{tid}/replace",
                data=json.dumps({"replacement_id": tid}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_tool(app, tid)

    def test_replace_tool_success(self, auth_client, app, ids):
        """Remplacement effectif de src par dst sur les tâches liées."""
        tid_src = _create_tool(app, ids, name="Outil Source OK")
        tid_dst = _create_tool(app, ids, name="Outil Dest OK")
        try:
            # Associer src à la tâche test
            auth_client.post(
                "/tools/add",
                data=json.dumps({
                    "task_id": ids["task_id"],
                    "existing_tool_ids": [tid_src],
                }),
                content_type="application/json",
            )
            r = auth_client.post(
                f"/gestion_outils/api/tools/{tid_src}/replace",
                data=json.dumps({"replacement_id": tid_dst}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert "replaced_count" in data
        finally:
            # Nettoyer les associations restantes
            auth_client.post(
                "/tools/delete",
                data=json.dumps({"task_id": ids["task_id"], "tool_id": tid_dst}),
                content_type="application/json",
            )
            _delete_tool(app, tid_src)
            _delete_tool(app, tid_dst)

    def test_replace_tool_source_not_found(self, auth_client):
        """POST replace sur outil source inexistant → 404."""
        r = auth_client.post(
            "/gestion_outils/api/tools/999999/replace",
            data=json.dumps({"replacement_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 404


# ===========================================================================
# 7. API DELETE — supprimer un outil
# ===========================================================================

class TestDeleteTool:

    def test_delete_tool_not_found(self, auth_client):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete("/gestion_outils/api/tools/999999")
        assert r.status_code == 404

    def test_delete_tool_without_usages(self, auth_client, app, ids):
        """Supprimer un outil sans usages → 200 et deleted=True."""
        tid = _create_tool(app, ids, name="Outil Supprimable")
        r = auth_client.delete(f"/gestion_outils/api/tools/{tid}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data.get("deleted") is True

    def test_delete_tool_with_usage_returns_409(self, auth_client, app, ids):
        """Supprimer un outil utilisé sans force_detach → 409."""
        tid = _create_tool(app, ids, name="Outil Utilisé 409")
        try:
            auth_client.post(
                "/tools/add",
                data=json.dumps({
                    "task_id": ids["task_id"],
                    "existing_tool_ids": [tid],
                }),
                content_type="application/json",
            )
            r = auth_client.delete(f"/gestion_outils/api/tools/{tid}")
            assert r.status_code == 409
        finally:
            auth_client.post(
                "/tools/delete",
                data=json.dumps({"task_id": ids["task_id"], "tool_id": tid}),
                content_type="application/json",
            )
            _delete_tool(app, tid)

    def test_delete_tool_force_detach(self, auth_client, app, ids):
        """force_detach=true détache et supprime même si utilisé."""
        tid = _create_tool(app, ids, name="Outil Force Delete")
        auth_client.post(
            "/tools/add",
            data=json.dumps({
                "task_id": ids["task_id"],
                "existing_tool_ids": [tid],
            }),
            content_type="application/json",
        )
        r = auth_client.delete(f"/gestion_outils/api/tools/{tid}?force_detach=true")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data.get("deleted") is True

    def test_delete_tool_partial_by_task_ids(self, auth_client, app, ids):
        """Suppression partielle via task_ids dans le corps → 200."""
        tid = _create_tool(app, ids, name="Outil Partiel Delete")
        auth_client.post(
            "/tools/add",
            data=json.dumps({
                "task_id": ids["task_id"],
                "existing_tool_ids": [tid],
            }),
            content_type="application/json",
        )
        r = auth_client.delete(
            f"/gestion_outils/api/tools/{tid}",
            data=json.dumps({"task_ids": [ids["task_id"]]}),
            content_type="application/json",
        )
        assert r.status_code == 200


# ===========================================================================
# 8. API /tools — ajouter/retirer des outils d'une tâche
# ===========================================================================

class TestToolsTaskAPI:

    def test_add_tool_missing_task_id(self, auth_client):
        """POST /tools/add sans task_id → 400."""
        r = auth_client.post(
            "/tools/add",
            data=json.dumps({"new_tools": ["Mon Outil"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_tool_task_not_found(self, auth_client):
        """POST /tools/add avec task_id inexistant → 404."""
        r = auth_client.post(
            "/tools/add",
            data=json.dumps({"task_id": 999999, "new_tools": ["Outil Fantôme"]}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_add_new_tool_by_name(self, auth_client, ids, app):
        """Créer un outil par son nom et l'associer à une tâche."""
        r = auth_client.post(
            "/tools/add",
            data=json.dumps({
                "task_id": ids["task_id"],
                "new_tools": ["Outil Nouveau Via API"],
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "added_tools" in data
        # Nettoyage
        for t in data["added_tools"]:
            _delete_tool(app, t["id"])

    def test_add_existing_tool_by_id(self, auth_client, ids, app):
        """Associer un outil existant à une tâche via son ID."""
        tid = _create_tool(app, ids, name="Outil Existant Add")
        try:
            r = auth_client.post(
                "/tools/add",
                data=json.dumps({
                    "task_id": ids["task_id"],
                    "existing_tool_ids": [tid],
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert any(t["id"] == tid for t in data["added_tools"])
        finally:
            auth_client.post(
                "/tools/delete",
                data=json.dumps({"task_id": ids["task_id"], "tool_id": tid}),
                content_type="application/json",
            )
            _delete_tool(app, tid)

    def test_add_same_tool_twice_not_duplicated(self, auth_client, ids, app):
        """Associer le même outil deux fois ne crée pas de doublon."""
        tid = _create_tool(app, ids, name="Outil No Doublon Tâche")
        try:
            payload = json.dumps({
                "task_id": ids["task_id"],
                "existing_tool_ids": [tid],
            })
            auth_client.post("/tools/add", data=payload, content_type="application/json")
            r = auth_client.post("/tools/add", data=payload, content_type="application/json")
            assert r.status_code == 200
            data = json.loads(r.data)
            # La 2e fois, added_tools doit être vide (déjà lié)
            assert data["added_tools"] == []
        finally:
            auth_client.post(
                "/tools/delete",
                data=json.dumps({"task_id": ids["task_id"], "tool_id": tid}),
                content_type="application/json",
            )
            _delete_tool(app, tid)

    def test_delete_tool_from_task_missing_fields(self, auth_client):
        """POST /tools/delete sans les champs requis → 400."""
        r = auth_client.post(
            "/tools/delete",
            data=json.dumps({"task_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_delete_tool_from_task_task_not_found(self, auth_client):
        """POST /tools/delete tâche inexistante → 404."""
        r = auth_client.post(
            "/tools/delete",
            data=json.dumps({"task_id": 999999, "tool_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_delete_tool_from_task_tool_not_found(self, auth_client, ids):
        """POST /tools/delete outil inexistant → 404."""
        r = auth_client.post(
            "/tools/delete",
            data=json.dumps({"task_id": ids["task_id"], "tool_id": 999999}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_delete_tool_not_linked_to_task(self, auth_client, ids, app):
        """POST /tools/delete outil non lié à la tâche → 404."""
        tid = _create_tool(app, ids, name="Outil Non Lié Delete")
        try:
            r = auth_client.post(
                "/tools/delete",
                data=json.dumps({"task_id": ids["task_id"], "tool_id": tid}),
                content_type="application/json",
            )
            assert r.status_code == 404
        finally:
            _delete_tool(app, tid)

    def test_delete_tool_from_task_success(self, auth_client, ids, app):
        """Supprimer proprement un outil d'une tâche → 200."""
        tid = _create_tool(app, ids, name="Outil Delete Tâche OK")
        auth_client.post(
            "/tools/add",
            data=json.dumps({
                "task_id": ids["task_id"],
                "existing_tool_ids": [tid],
            }),
            content_type="application/json",
        )
        r = auth_client.post(
            "/tools/delete",
            data=json.dumps({"task_id": ids["task_id"], "tool_id": tid}),
            content_type="application/json",
        )
        assert r.status_code == 200
        _delete_tool(app, tid)
