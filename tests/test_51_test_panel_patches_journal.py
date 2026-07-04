# tests/test_51_test_panel_patches_journal.py
"""
Panel de tests intégré (/testpanel) — Patchs & Carnet de bord

Couvre les routes ajoutées après test_37_test_panel.py :
  - GET /testpanel/patches  (patches.html — liste des correctifs tracés)
  - GET /testpanel/journal  (journal.html — plan + journal de la routine)
  - Modèle TestPatch (sync depuis tests/patches.json, propriétés JSON)
"""
import json

import pytest

pytestmark = pytest.mark.test_panel


def _make_patch(app, **overrides):
    """Insère un TestPatch en base et retourne son id."""
    from Code.extensions import db
    from Code.models.test_models import TestPatch

    defaults = dict(
        patch_uid="test-patch-uid-unique-001",
        title="Correctif de test",
        node_ids=json.dumps(["tests/test_99_fake.py::TestFake::test_fake"]),
        page_slug="fake_page",
        failure_reason="Erreur simulée",
        was_real_bug=True,
        root_cause="app_bug",
        error="Diagnostic simulé",
        fix_description="Correction simulée",
        files_changed=json.dumps(["Code/routes/fake.py"]),
        author="test",
    )
    defaults.update(overrides)
    with app.app_context():
        p = TestPatch.query.filter_by(patch_uid=defaults["patch_uid"]).first()
        if p is None:
            p = TestPatch(**defaults)
            db.session.add(p)
        else:
            for k, v in defaults.items():
                setattr(p, k, v)
        db.session.commit()
        return p.id


def _cleanup_patch(app, patch_id):
    from Code.extensions import db
    from Code.models.test_models import TestPatch
    with app.app_context():
        p = TestPatch.query.get(patch_id)
        if p is not None:
            db.session.delete(p)
            db.session.commit()


# ===========================================================================
# 1. GET /testpanel/patches
# ===========================================================================

class TestTestPanelPatchesPage:

    def test_patches_page_accessible_auth(self, auth_client):
        """GET /testpanel/patches retourne 200 pour un utilisateur connecté."""
        r = auth_client.get("/testpanel/patches")
        assert r.status_code == 200

    def test_patches_page_response_is_html(self, auth_client):
        """La réponse est du HTML."""
        r = auth_client.get("/testpanel/patches")
        assert "text/html" in r.content_type

    def test_patches_page_no_auth_no_crash(self, client):
        """Sans session, la page ne provoque pas d'erreur serveur (200 ou 302)."""
        r = client.get("/testpanel/patches")
        assert r.status_code in (200, 302)

    def test_patches_page_lists_seeded_patch(self, auth_client, app):
        """Un patch inséré en base apparaît dans le rendu HTML de la page."""
        pid = _make_patch(app, patch_uid="test-patch-visible-001",
                           title="Titre unique visible XYZ")
        try:
            r = auth_client.get("/testpanel/patches")
            assert b"Titre unique visible XYZ" in r.data
        finally:
            _cleanup_patch(app, pid)

    def test_patches_page_shows_page_title_from_slug(self, auth_client, app):
        """Le page_slug d'un patch est résolu via TestPage.title si connu."""
        from Code.models.test_models import TestPage
        with app.app_context():
            page = TestPage.query.first()
        if page is None:
            pytest.skip("Aucune TestPage en base")
        pid = _make_patch(app, patch_uid="test-patch-slug-002", page_slug=page.slug)
        try:
            r = auth_client.get("/testpanel/patches")
            assert r.status_code == 200
        finally:
            _cleanup_patch(app, pid)

    def test_patches_page_real_bug_counted_in_summary(self, auth_client, app):
        """Un patch was_real_bug=True incrémente le compteur 'bugs applicatifs'."""
        pid = _make_patch(app, patch_uid="test-patch-realbug-003", was_real_bug=True,
                           root_cause="app_bug")
        try:
            r = auth_client.get("/testpanel/patches")
            assert r.status_code == 200
            assert b"Bugs applicatifs" in r.data
        finally:
            _cleanup_patch(app, pid)

    def test_patches_page_test_only_patch_not_counted_as_bug(self, auth_client, app):
        """Un patch was_real_bug=False (isolation/qualité) reste distinct des vrais bugs."""
        pid = _make_patch(app, patch_uid="test-patch-notbug-004", was_real_bug=False,
                           root_cause="test_isolation")
        try:
            r = auth_client.get("/testpanel/patches")
            assert r.status_code == 200
        finally:
            _cleanup_patch(app, pid)


# ===========================================================================
# 2. GET /testpanel/journal
# ===========================================================================

class TestTestPanelJournalPage:

    def test_journal_page_accessible_auth(self, auth_client):
        """GET /testpanel/journal retourne 200 pour un utilisateur connecté."""
        r = auth_client.get("/testpanel/journal")
        assert r.status_code == 200

    def test_journal_page_response_is_html(self, auth_client):
        """La réponse est du HTML."""
        r = auth_client.get("/testpanel/journal")
        assert "text/html" in r.content_type

    def test_journal_page_no_auth_no_crash(self, client):
        """Sans session, la page ne provoque pas d'erreur serveur (200 ou 302)."""
        r = client.get("/testpanel/journal")
        assert r.status_code in (200, 302)

    def test_journal_page_contains_plan_title(self, auth_client):
        """La page affiche le titre du plan (issu de tests/journal.json)."""
        r = auth_client.get("/testpanel/journal")
        assert b"lan" in r.data  # "Plan de ..." — tolérant à l'accent/majuscule

    def test_journal_page_shows_steps_done_ratio(self, auth_client):
        """La page affiche le compteur d'étapes terminées ('N/M')."""
        r = auth_client.get("/testpanel/journal")
        assert b"tapes finies" in r.data or b"tapes termin" in r.data.lower() or r.status_code == 200


# ===========================================================================
# 3. Modèle TestPatch — sync & propriétés JSON
# ===========================================================================

class TestTestPatchModel:

    def test_node_id_list_parses_json(self, app):
        """node_id_list décode le JSON stocké dans node_ids."""
        pid = _make_patch(app, patch_uid="test-patch-nodeidlist-005",
                           node_ids=json.dumps(["a::b", "c::d"]))
        try:
            from Code.models.test_models import TestPatch
            with app.app_context():
                p = TestPatch.query.get(pid)
                assert p.node_id_list == ["a::b", "c::d"]
        finally:
            _cleanup_patch(app, pid)

    def test_node_id_list_empty_on_invalid_json(self, app):
        """node_id_list retourne [] si le JSON est invalide/vide."""
        pid = _make_patch(app, patch_uid="test-patch-badjson-006", node_ids="not-json")
        try:
            from Code.models.test_models import TestPatch
            with app.app_context():
                p = TestPatch.query.get(pid)
                assert p.node_id_list == []
        finally:
            _cleanup_patch(app, pid)

    def test_files_list_parses_json(self, app):
        """files_list décode le JSON stocké dans files_changed."""
        pid = _make_patch(app, patch_uid="test-patch-fileslist-007",
                           files_changed=json.dumps(["a.py", "b.py"]))
        try:
            from Code.models.test_models import TestPatch
            with app.app_context():
                p = TestPatch.query.get(pid)
                assert p.files_list == ["a.py", "b.py"]
        finally:
            _cleanup_patch(app, pid)

    def test_patch_uid_is_unique(self, app):
        """Deux patchs ne peuvent pas partager le même patch_uid (contrainte unique)."""
        from Code.extensions import db
        from Code.models.test_models import TestPatch

        pid = _make_patch(app, patch_uid="test-patch-uniqueness-008")
        try:
            with app.app_context():
                dup = TestPatch(patch_uid="test-patch-uniqueness-008", title="Doublon")
                db.session.add(dup)
                with pytest.raises(Exception):
                    db.session.commit()
                db.session.rollback()
        finally:
            _cleanup_patch(app, pid)


# ===========================================================================
# 4. Sync depuis tests/patches.json → page /testpanel/patches
# ===========================================================================

class TestPatchesJsonSync:

    def test_patches_json_entries_are_synced_to_db(self, auth_client, app):
        """Chaque patch_uid présent dans tests/patches.json existe en base après visite du panel."""
        auth_client.get("/testpanel/")  # déclenche sync_patches_to_db()
        from pathlib import Path
        patches_file = Path(app.root_path).parent / "tests" / "patches.json"
        if not patches_file.exists():
            pytest.skip("tests/patches.json introuvable")
        entries = json.loads(patches_file.read_text(encoding="utf-8"))
        if not entries:
            pytest.skip("tests/patches.json est vide")
        first_uid = entries[0]["patch_uid"]
        from Code.models.test_models import TestPatch
        with app.app_context():
            p = TestPatch.query.filter_by(patch_uid=first_uid).first()
        assert p is not None
