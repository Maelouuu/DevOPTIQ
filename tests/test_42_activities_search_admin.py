# tests/test_42_activities_search_admin.py
"""
Couverture des routes non testées dans test_27 (activities_view) et test_37 (test_panel) :
  GET  /activities/view/search               → recherche activités par nom (activities_view.py)
  POST /testpanel/admin/clone_entity         → clonage d'entité complète (test_panel.py)
  GET  /testpanel/admin/migrate_entities     → dry-run migration production (test_panel.py)
  POST /testpanel/admin/migrate_entities     → exécution migration production (test_panel.py)
"""
import pytest

pytestmark = pytest.mark.activities_search_admin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_entity(app, name):
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        e = Entity(name=name, description="Entité créée pour les tests clone")
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


# ===========================================================================
# 1. GET /activities/view/search — Recherche d'activités par nom
# ===========================================================================

class TestActivitiesViewSearch:

    def test_search_no_param_returns_empty(self, auth_client):
        """Sans paramètre q, retourne html vide et count=0."""
        r = auth_client.get("/activities/view/search")
        assert r.status_code == 200
        data = r.get_json()
        assert data["html"] == ""
        assert data["count"] == 0

    def test_search_empty_q_returns_empty(self, auth_client):
        """q= (chaîne vide) → html: '', count: 0."""
        r = auth_client.get("/activities/view/search?q=")
        assert r.status_code == 200
        data = r.get_json()
        assert data["html"] == ""
        assert data["count"] == 0

    def test_search_whitespace_q_returns_empty(self, auth_client):
        """q composé uniquement d'espaces (strip()) → html: '', count: 0."""
        r = auth_client.get("/activities/view/search?q=   ")
        assert r.status_code == 200
        data = r.get_json()
        assert data["html"] == ""
        assert data["count"] == 0

    def test_search_nonexistent_term_returns_zero(self, auth_client):
        """Recherche sans correspondance → count: 0, html: ''."""
        r = auth_client.get("/activities/view/search?q=XYZNONEXISTENT99999")
        assert r.status_code == 200
        data = r.get_json()
        assert data["count"] == 0
        assert data["html"] == ""

    def test_search_full_name_match(self, auth_client):
        """Nom exact de l'activité du seed → count ≥ 1."""
        r = auth_client.get("/activities/view/search?q=Activit%C3%A9+Test")
        assert r.status_code == 200
        data = r.get_json()
        assert data["count"] >= 1

    def test_search_partial_name_matches(self, auth_client):
        """Sous-chaîne du nom → count ≥ 1."""
        r = auth_client.get("/activities/view/search?q=Activ")
        assert r.status_code == 200
        data = r.get_json()
        assert data["count"] >= 1

    def test_search_case_insensitive(self, auth_client):
        """Casse différente du nom du seed → même résultat."""
        r_lower = auth_client.get("/activities/view/search?q=activit%C3%A9+test")
        r_upper = auth_client.get("/activities/view/search?q=ACTIVIT%C3%89+TEST")
        assert r_lower.get_json()["count"] == r_upper.get_json()["count"]

    def test_search_response_has_html_key(self, auth_client):
        """La réponse JSON contient toujours 'html'."""
        data = auth_client.get("/activities/view/search?q=test").get_json()
        assert "html" in data

    def test_search_response_has_count_key(self, auth_client):
        """La réponse JSON contient toujours 'count'."""
        data = auth_client.get("/activities/view/search?q=test").get_json()
        assert "count" in data

    def test_search_html_is_string(self, auth_client):
        """La valeur de 'html' est une chaîne de caractères."""
        data = auth_client.get("/activities/view/search?q=Activ").get_json()
        assert isinstance(data["html"], str)

    def test_search_count_is_int(self, auth_client):
        """La valeur de 'count' est un entier."""
        data = auth_client.get("/activities/view/search?q=Activ").get_json()
        assert isinstance(data["count"], int)

    def test_search_html_nonempty_when_count_positive(self, auth_client):
        """Quand count > 0, le html rendu n'est pas vide."""
        data = auth_client.get("/activities/view/search?q=Activ").get_json()
        if data["count"] > 0:
            assert data["html"] != ""

    def test_search_unauthenticated_does_not_crash(self, client):
        """Sans session, la route ne génère pas d'erreur serveur."""
        r = client.get("/activities/view/search?q=test")
        assert r.status_code in (200, 302)


# ===========================================================================
# 1bis. GET /activities/view/search — Recherche insensible aux accents
# ===========================================================================

def _create_activity(app, entity_id, name):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities(entity_id=entity_id, name=name, description="Activité de test accents")
        db.session.add(a)
        db.session.commit()
        return a.id


def _delete_activity(app, activity_id):
    with app.app_context():
        from Code.models.models import Activities
        from Code.extensions import db
        a = Activities.query.get(activity_id)
        if a:
            db.session.delete(a)
            db.session.commit()


class TestActivitiesViewSearchAccentInsensitive:

    def test_unaccented_query_matches_accented_name(self, auth_client, app, ids):
        """Rechercher 'Deja Vu' doit trouver une activité nommée 'Déjà Vù'."""
        aid = _create_activity(app, ids["entity_id"], "Déjà Vù Accent Test")
        try:
            r = auth_client.get("/activities/view/search?q=Deja+Vu+Accent+Test")
            data = r.get_json()
            assert data["count"] >= 1
        finally:
            _delete_activity(app, aid)

    def test_accented_query_matches_unaccented_name(self, auth_client, app, ids):
        """Rechercher 'Eleve' (sans accent) doit trouver 'Élève Sans Accent Test'."""
        aid = _create_activity(app, ids["entity_id"], "Eleve Sans Accent Test")
        try:
            r = auth_client.get("/activities/view/search?q=%C3%89l%C3%A8ve+Sans+Accent+Test")
            data = r.get_json()
            assert data["count"] >= 1
        finally:
            _delete_activity(app, aid)

    def test_accent_insensitive_search_is_case_insensitive_too(self, auth_client, app, ids):
        """La normalisation accents + casse fonctionne combinée (MAJ + accents)."""
        aid = _create_activity(app, ids["entity_id"], "Été Combiné Test")
        try:
            r = auth_client.get("/activities/view/search?q=ETE+COMBINE+TEST")
            data = r.get_json()
            assert data["count"] >= 1
        finally:
            _delete_activity(app, aid)


# ===========================================================================
# 2. POST /testpanel/admin/clone_entity — Clonage d'entité
# ===========================================================================

class TestAdminCloneEntity:

    def test_clone_empty_body_returns_500(self, auth_client):
        """Corps JSON vide → target_id None → TypeError avant le try → 500."""
        r = auth_client.post("/testpanel/admin/clone_entity", json={})
        assert r.status_code == 500

    def test_clone_missing_target_id_returns_500(self, auth_client):
        """Pas de target_id fourni → int(None) lève TypeError → 500."""
        r = auth_client.post(
            "/testpanel/admin/clone_entity",
            json={"source_id": 1},
        )
        assert r.status_code == 500

    def test_clone_source_not_found_returns_json_error(self, auth_client, ids):
        """source_id inexistant → 404 capturée dans try/except → 500 JSON ok: False."""
        r = auth_client.post(
            "/testpanel/admin/clone_entity",
            json={"source_id": 999999, "target_id": ids["entity_id"]},
        )
        assert r.status_code == 500
        data = r.get_json()
        assert data is not None
        assert data["ok"] is False
        assert "error" in data

    def test_clone_target_not_found_returns_json_error(self, auth_client, ids):
        """target_id inexistant → 404 capturée dans try/except → 500 JSON ok: False."""
        r = auth_client.post(
            "/testpanel/admin/clone_entity",
            json={"source_id": ids["entity_id"], "target_id": 999999},
        )
        assert r.status_code == 500
        data = r.get_json()
        assert data is not None
        assert data["ok"] is False

    def test_clone_empty_entity_returns_ok_true(self, auth_client, app):
        """Clone d'une entité vide → 200, ok: True, tous les compteurs à 0."""
        src_id = _create_entity(app, "Clone Source Vide A")
        tgt_id = _create_entity(app, "Clone Target Vide A")
        try:
            r = auth_client.post(
                "/testpanel/admin/clone_entity",
                json={"source_id": src_id, "target_id": tgt_id},
            )
            assert r.status_code == 200
            data = r.get_json()
            assert data["ok"] is True
        finally:
            _delete_entity(app, tgt_id)
            _delete_entity(app, src_id)

    def test_clone_response_has_all_count_keys(self, auth_client, app):
        """La réponse de clonage contient roles, tools, activities, tasks, data_shapes, links."""
        src_id = _create_entity(app, "Clone Source Vide B")
        tgt_id = _create_entity(app, "Clone Target Vide B")
        try:
            r = auth_client.post(
                "/testpanel/admin/clone_entity",
                json={"source_id": src_id, "target_id": tgt_id},
            )
            assert r.status_code == 200
            data = r.get_json()
            for key in ("roles", "tools", "activities", "tasks", "data_shapes", "links"):
                assert key in data, f"Clé manquante dans la réponse : {key}"
        finally:
            _delete_entity(app, tgt_id)
            _delete_entity(app, src_id)

    def test_clone_response_has_source_and_target_names(self, auth_client, app):
        """La réponse inclut les noms des entités source et target."""
        src_id = _create_entity(app, "Clone Src Nom Test")
        tgt_id = _create_entity(app, "Clone Tgt Nom Test")
        try:
            r = auth_client.post(
                "/testpanel/admin/clone_entity",
                json={"source_id": src_id, "target_id": tgt_id},
            )
            data = r.get_json()
            assert data.get("source") == "Clone Src Nom Test"
            assert data.get("target") == "Clone Tgt Nom Test"
        finally:
            _delete_entity(app, tgt_id)
            _delete_entity(app, src_id)

    def test_clone_empty_counts_are_zero(self, auth_client, app):
        """Clone d'entité vide → tous les compteurs sont 0."""
        src_id = _create_entity(app, "Clone Zero Source")
        tgt_id = _create_entity(app, "Clone Zero Target")
        try:
            r = auth_client.post(
                "/testpanel/admin/clone_entity",
                json={"source_id": src_id, "target_id": tgt_id},
            )
            data = r.get_json()
            assert data["roles"] == 0
            assert data["tools"] == 0
            assert data["activities"] == 0
            assert data["tasks"] == 0
            assert data["data_shapes"] == 0
            assert data["links"] == 0
        finally:
            _delete_entity(app, tgt_id)
            _delete_entity(app, src_id)

    def test_clone_error_response_has_trace(self, auth_client, ids):
        """En cas d'erreur capturée, la réponse contient un champ 'trace'."""
        r = auth_client.post(
            "/testpanel/admin/clone_entity",
            json={"source_id": 999999, "target_id": ids["entity_id"]},
        )
        assert r.status_code == 500
        data = r.get_json()
        assert "trace" in data


# ===========================================================================
# 3. GET + POST /testpanel/admin/migrate_entities — Migration production
# ===========================================================================

class TestAdminMigrateEntities:

    def test_migrate_get_without_production_users_returns_404(self, auth_client):
        """GET sans les utilisateurs de prod → 404 car emails absents de la DB."""
        r = auth_client.get("/testpanel/admin/migrate_entities")
        assert r.status_code == 404

    def test_migrate_get_response_has_error_key(self, auth_client):
        """Réponse 404 → JSON avec clé 'error'."""
        r = auth_client.get("/testpanel/admin/migrate_entities")
        data = r.get_json()
        assert data is not None
        assert "error" in data

    def test_migrate_get_error_mentions_user_not_found(self, auth_client):
        """Le message d'erreur indique l'email de l'utilisateur manquant."""
        r = auth_client.get("/testpanel/admin/migrate_entities")
        data = r.get_json()
        assert "User not found" in data["error"]

    def test_migrate_post_without_production_users_returns_404(self, auth_client):
        """POST sans les utilisateurs de prod → 404."""
        r = auth_client.post("/testpanel/admin/migrate_entities")
        assert r.status_code == 404

    def test_migrate_post_response_has_error_key(self, auth_client):
        """POST → 404 JSON avec clé 'error'."""
        r = auth_client.post("/testpanel/admin/migrate_entities")
        data = r.get_json()
        assert data is not None
        assert "error" in data

    def test_migrate_dry_run_and_execute_same_404(self, auth_client):
        """GET et POST renvoient tous les deux 404 en environnement de test."""
        r_get  = auth_client.get("/testpanel/admin/migrate_entities")
        r_post = auth_client.post("/testpanel/admin/migrate_entities")
        assert r_get.status_code == 404
        assert r_post.status_code == 404
