# tests/test_06_softskills.py
"""
Page : HSC / Habiletés Socio-Cognitives (section dans les activités)
Couvre : ajout (création + upsert), modification, suppression, rendu partiel,
cas limites (champs manquants, cross-activity, introuvable) et erreurs DB.
"""
import pytest
import json

pytestmark = pytest.mark.softskills


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_softskill(app, activity_id, habilete="À modifier", niveau="2", justification=""):
    from Code.models.models import Softskill
    from Code.extensions import db
    with app.app_context():
        ss = Softskill(
            habilete=habilete,
            niveau=niveau,
            justification=justification,
            activity_id=activity_id,
        )
        db.session.add(ss)
        db.session.commit()
        return ss.id


def _delete_softskill(app, ss_id):
    from Code.models.models import Softskill
    from Code.extensions import db
    with app.app_context():
        ss = Softskill.query.get(ss_id)
        if ss:
            db.session.delete(ss)
            db.session.commit()


def _create_other_activity(app, ids):
    from Code.models.models import Activities
    from Code.extensions import db
    with app.app_context():
        a = Activities(entity_id=ids["entity_id"], name="Autre Activité Softskills")
        db.session.add(a)
        db.session.commit()
        return a.id


def _delete_activity(app, activity_id):
    from Code.models.models import Activities
    from Code.extensions import db
    with app.app_context():
        a = Activities.query.get(activity_id)
        if a:
            db.session.delete(a)
            db.session.commit()


# ===========================================================================
# 1. Ajout — POST /softskills/add
# ===========================================================================

class TestSoftskillsAdd:

    def test_add_softskill_creates_new(self, auth_client, ids, app):
        """Nouveau couple (habileté, activité) → 201 + objet retourné."""
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({
                "habilete": "Communication",
                "niveau": "3",
                "justification": "Justification test",
                "activity_id": ids["activity_id"],
            }),
            content_type="application/json",
        )
        assert r.status_code == 201
        body = json.loads(r.data)
        assert body["habilete"] == "Communication"
        assert body["niveau"] == "3"
        assert body["justification"] == "Justification test"
        assert body["activity_id"] == ids["activity_id"]
        _delete_softskill(app, body["id"])

    def test_add_softskill_missing_fields_returns_400(self, auth_client, ids):
        """Sans habilete/niveau → 400 avec message d'erreur explicite."""
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({"activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert "obligatoires" in data["error"]

    def test_add_softskill_upserts_existing(self, auth_client, ids, app):
        """Même (habileté, activité), casse différente → 200, met à jour l'existant."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="empathie", niveau="1")
        try:
            r = auth_client.post(
                "/softskills/add",
                data=json.dumps({
                    "habilete": "Empathie",
                    "niveau": "4",
                    "justification": "Mise à jour",
                    "activity_id": ids["activity_id"],
                }),
                content_type="application/json",
            )
            assert r.status_code == 200
            body = json.loads(r.data)
            assert body["id"] == ss_id
            assert body["habilete"] == "Empathie"
            assert body["niveau"] == "4"
            assert body["justification"] == "Mise à jour"
        finally:
            _delete_softskill(app, ss_id)

    def test_add_softskill_db_error_rolls_back_and_returns_500(self, auth_client, ids, monkeypatch):
        """Exception au commit → rollback + 500 avec le message d'erreur."""
        from Code.extensions import db

        def _boom():
            raise RuntimeError("commit-boom-softskill-add")

        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            r = auth_client.post(
                "/softskills/add",
                data=json.dumps({
                    "habilete": "Va échouer",
                    "niveau": "1",
                    "activity_id": ids["activity_id"],
                }),
                content_type="application/json",
            )
        finally:
            monkeypatch.undo()
        assert r.status_code == 500
        assert "commit-boom-softskill-add" in json.loads(r.data)["error"]


# ===========================================================================
# 2. Modification — PUT /softskills/<activity_id>/<ss_id>
# ===========================================================================

class TestSoftskillsUpdate:

    def test_update_softskill_success(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"])
        try:
            r = auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"habilete": "Modifié", "niveau": "3", "justification": "j"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            body = json.loads(r.data)
            assert body["id"] == ss_id
            assert body["habilete"] == "Modifié"
            assert body["niveau"] == "3"
            assert body["justification"] == "j"
        finally:
            _delete_softskill(app, ss_id)

    def test_update_softskill_missing_fields_returns_400(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"])
        try:
            r = auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"habilete": "", "niveau": ""}),
                content_type="application/json",
            )
            assert r.status_code == 400
            data = json.loads(r.data)
            assert "obligatoires" in data["error"]
        finally:
            _delete_softskill(app, ss_id)

    def test_update_softskill_not_found_returns_404(self, auth_client, ids):
        r = auth_client.put(
            f"/softskills/{ids['activity_id']}/999999",
            data=json.dumps({"habilete": "x", "niveau": "1"}),
            content_type="application/json",
        )
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "Softskill introuvable"

    def test_update_softskill_cross_activity_returns_404(self, auth_client, ids, app):
        """Softskill existant mais rattaché à une autre activité → 404."""
        other_activity_id = _create_other_activity(app, ids)
        ss_id = _create_softskill(app, other_activity_id)
        try:
            r = auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"habilete": "x", "niveau": "1"}),
                content_type="application/json",
            )
            assert r.status_code == 404
            assert json.loads(r.data)["error"] == "Softskill introuvable"
        finally:
            _delete_softskill(app, ss_id)
            _delete_activity(app, other_activity_id)

    def test_update_softskill_db_error_rolls_back_and_returns_500(self, auth_client, ids, app, monkeypatch):
        from Code.extensions import db

        ss_id = _create_softskill(app, ids["activity_id"])

        def _boom():
            raise RuntimeError("commit-boom-softskill-update")

        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            r = auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"habilete": "x", "niveau": "1"}),
                content_type="application/json",
            )
        finally:
            monkeypatch.undo()
            _delete_softskill(app, ss_id)
        assert r.status_code == 500
        assert "commit-boom-softskill-update" in json.loads(r.data)["error"]


# ===========================================================================
# 3. Suppression — DELETE /softskills/<activity_id>/<ss_id>
# ===========================================================================

class TestSoftskillsDelete:

    def test_delete_softskill_success(self, auth_client, ids, app):
        ss_id = _create_softskill(app, ids["activity_id"], habilete="À supprimer")
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        assert r.status_code == 200
        assert json.loads(r.data)["message"] == "Softskill deleted"

        from Code.models.models import Softskill
        with app.app_context():
            assert Softskill.query.get(ss_id) is None

    def test_delete_softskill_not_found_returns_404(self, auth_client, ids):
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/999999")
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "Softskill not found"

    def test_delete_softskill_cross_activity_returns_404(self, auth_client, ids, app):
        """Softskill existant mais rattaché à une autre activité → 404 Mismatch."""
        other_activity_id = _create_other_activity(app, ids)
        ss_id = _create_softskill(app, other_activity_id)
        try:
            r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
            assert r.status_code == 404
            assert json.loads(r.data)["error"] == "Mismatch activity_id"
        finally:
            _delete_softskill(app, ss_id)
            _delete_activity(app, other_activity_id)

    def test_delete_softskill_db_error_rolls_back_and_returns_500(self, auth_client, ids, app, monkeypatch):
        from Code.extensions import db

        ss_id = _create_softskill(app, ids["activity_id"])

        def _boom():
            raise RuntimeError("commit-boom-softskill-delete")

        monkeypatch.setattr(db.session, "commit", _boom)
        try:
            r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        finally:
            monkeypatch.undo()
            _delete_softskill(app, ss_id)
        assert r.status_code == 500
        assert "commit-boom-softskill-delete" in json.loads(r.data)["error"]


# ===========================================================================
# 4. Rendu partiel — GET /softskills/<activity_id>/render
# ===========================================================================

class TestSoftskillsRenderPartial:

    def test_render_softskills_found(self, auth_client, ids):
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert r.content_type.startswith("text/html")

    def test_render_softskills_activity_not_found_returns_404(self, auth_client):
        r = auth_client.get("/softskills/999999/render")
        assert r.status_code == 404
        assert json.loads(r.data)["error"] == "Activité non trouvée"
