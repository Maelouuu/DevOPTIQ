# tests/test_06_softskills.py
"""
API : Softskills / HSC — Habiletés Socio-Cognitives (/softskills)
Couvre : ajout (avec upsert insensible à la casse sur `habilete`), mise à
         jour, suppression et rendu HTML des softskills associées à une
         activité.
"""
import json
import pytest

pytestmark = pytest.mark.softskills


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_softskill(app, activity_id, habilete="Softskill Fixture", niveau="2", justification=""):
    with app.app_context():
        from Code.models.models import Softskill
        from Code.extensions import db
        ss = Softskill(habilete=habilete, niveau=niveau, justification=justification, activity_id=activity_id)
        db.session.add(ss)
        db.session.commit()
        return ss.id


def _delete_softskill(app, ss_id):
    with app.app_context():
        from Code.models.models import Softskill
        from Code.extensions import db
        ss = Softskill.query.get(ss_id)
        if ss:
            db.session.delete(ss)
            db.session.commit()


# ===========================================================================
# 1. POST /softskills/add — ajouter (ou upserter) une softskill
# ===========================================================================

class TestAddSoftskill:

    def test_add_softskill_valid_returns_201(self, auth_client, ids, app):
        """POST /softskills/add avec données valides → 201 + id + champs."""
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
        data = json.loads(r.data)
        assert data["habilete"] == "Communication"
        assert data["niveau"] == "3"
        assert data["justification"] == "Justification test"
        assert data["activity_id"] == ids["activity_id"]
        _delete_softskill(app, data["id"])

    def test_add_softskill_missing_habilete_returns_400(self, auth_client, ids):
        """habilete absent → 400."""
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({"niveau": "2", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "error" in json.loads(r.data)

    def test_add_softskill_missing_niveau_returns_400(self, auth_client, ids):
        """niveau absent → 400."""
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({"habilete": "Rigueur", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_softskill_missing_activity_id_returns_400(self, auth_client):
        """activity_id absent → 400."""
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({"habilete": "Autonomie", "niveau": "1"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_softskill_empty_json_body_returns_400(self, auth_client):
        """Corps JSON vide {} → 400."""
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_add_softskill_persists_in_db(self, auth_client, ids, app):
        """Après création, la softskill est retrouvable en base."""
        r = auth_client.post(
            "/softskills/add",
            data=json.dumps({"habilete": "Softskill Persistée", "niveau": "4", "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 201
        ss_id = json.loads(r.data)["id"]
        with app.app_context():
            from Code.models.models import Softskill
            ss = Softskill.query.get(ss_id)
            assert ss is not None
            assert ss.habilete == "Softskill Persistée"
            assert ss.niveau == "4"
            assert ss.activity_id == ids["activity_id"]
        _delete_softskill(app, ss_id)

    def test_add_softskill_duplicate_habilete_same_case_upserts_returns_200(self, auth_client, ids, app):
        """Même habilete + activité déjà existante → mise à jour (200), pas de doublon créé."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Créativité", niveau="1")
        try:
            r = auth_client.post(
                "/softskills/add",
                data=json.dumps({"habilete": "Créativité", "niveau": "5", "activity_id": ids["activity_id"]}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["id"] == ss_id
            assert data["niveau"] == "5"
            with app.app_context():
                from Code.models.models import Softskill
                count = Softskill.query.filter_by(activity_id=ids["activity_id"], habilete="Créativité").count()
                assert count == 1
        finally:
            _delete_softskill(app, ss_id)

    def test_add_softskill_duplicate_habilete_different_case_upserts(self, auth_client, ids, app):
        """La détection de doublon est insensible à la casse sur `habilete`."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="ecoute active", niveau="2")
        try:
            r = auth_client.post(
                "/softskills/add",
                data=json.dumps({"habilete": "ECOUTE ACTIVE", "niveau": "3", "activity_id": ids["activity_id"]}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["id"] == ss_id
        finally:
            _delete_softskill(app, ss_id)

    def test_add_softskill_same_habilete_different_activity_creates_new(self, auth_client, ids, app):
        """Même habilete mais activité différente → nouvelle ligne (201), pas d'upsert."""
        from Code.models.models import Entity, Activities
        from Code.extensions import db
        with app.app_context():
            other_activity = Activities(entity_id=ids["entity_id"], name="Autre Activité Softskill")
            db.session.add(other_activity)
            db.session.commit()
            other_activity_id = other_activity.id

        ss_id = _create_softskill(app, ids["activity_id"], habilete="Leadership", niveau="2")
        new_id = None
        try:
            r = auth_client.post(
                "/softskills/add",
                data=json.dumps({"habilete": "Leadership", "niveau": "3", "activity_id": other_activity_id}),
                content_type="application/json",
            )
            assert r.status_code == 201
            new_id = json.loads(r.data)["id"]
            assert new_id != ss_id
        finally:
            _delete_softskill(app, ss_id)
            if new_id:
                _delete_softskill(app, new_id)
            with app.app_context():
                a = Activities.query.get(other_activity_id)
                if a:
                    db.session.delete(a)
                    db.session.commit()


# ===========================================================================
# 2. PUT /softskills/<activity_id>/<ss_id> — modifier une softskill
# ===========================================================================

class TestUpdateSoftskill:

    def test_update_softskill_valid_returns_200(self, auth_client, ids, app):
        """PUT avec nouvelles valeurs → 200 + champs mis à jour."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="À modifier", niveau="2")
        try:
            r = auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"habilete": "Modifié", "niveau": "3", "justification": "Car oui"}),
                content_type="application/json",
            )
            assert r.status_code == 200
            data = json.loads(r.data)
            assert data["habilete"] == "Modifié"
            assert data["niveau"] == "3"
            assert data["justification"] == "Car oui"
            assert data["id"] == ss_id
        finally:
            _delete_softskill(app, ss_id)

    def test_update_softskill_persists_change(self, auth_client, ids, app):
        """La modification est persistée en base."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Avant", niveau="1")
        try:
            auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"habilete": "Après", "niveau": "4"}),
                content_type="application/json",
            )
            with app.app_context():
                from Code.models.models import Softskill
                ss = Softskill.query.get(ss_id)
                assert ss.habilete == "Après"
                assert ss.niveau == "4"
        finally:
            _delete_softskill(app, ss_id)

    def test_update_softskill_missing_habilete_returns_400(self, auth_client, ids, app):
        """habilete absent → 400."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Softskill Update", niveau="2")
        try:
            r = auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"niveau": "3"}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_softskill(app, ss_id)

    def test_update_softskill_whitespace_only_returns_400(self, auth_client, ids, app):
        """habilete composé d'espaces → 400."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Softskill WS", niveau="2")
        try:
            r = auth_client.put(
                f"/softskills/{ids['activity_id']}/{ss_id}",
                data=json.dumps({"habilete": "   ", "niveau": "2"}),
                content_type="application/json",
            )
            assert r.status_code == 400
        finally:
            _delete_softskill(app, ss_id)

    def test_update_softskill_wrong_ss_id_returns_404(self, auth_client, ids):
        """ss_id inexistant → 404."""
        r = auth_client.put(
            f"/softskills/{ids['activity_id']}/999999",
            data=json.dumps({"habilete": "Modif", "niveau": "2"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_softskill_wrong_activity_id_returns_404(self, auth_client, ids, app):
        """ss_id existant mais activité incorrecte → 404 (mismatch activity_id)."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Softskill Mauvaise Activité", niveau="2")
        try:
            r = auth_client.put(
                f"/softskills/999999/{ss_id}",
                data=json.dumps({"habilete": "Modif", "niveau": "2"}),
                content_type="application/json",
            )
            assert r.status_code == 404
        finally:
            _delete_softskill(app, ss_id)


# ===========================================================================
# 3. DELETE /softskills/<activity_id>/<ss_id> — supprimer une softskill
# ===========================================================================

class TestDeleteSoftskill:

    def test_delete_softskill_valid_returns_200(self, auth_client, ids, app):
        """DELETE sur softskill existante → 200 + message."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="À supprimer", niveau="1")
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "message" in data

    def test_delete_softskill_removes_from_db(self, auth_client, ids, app):
        """Après suppression, la softskill n'existe plus en base."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Softskill Supprimée Vérifiée", niveau="1")
        auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        with app.app_context():
            from Code.models.models import Softskill
            assert Softskill.query.get(ss_id) is None

    def test_delete_softskill_not_found_returns_404(self, auth_client, ids):
        """DELETE sur ID inexistant → 404."""
        r = auth_client.delete(f"/softskills/{ids['activity_id']}/999999")
        assert r.status_code == 404
        assert "error" in json.loads(r.data)

    def test_delete_softskill_wrong_activity_returns_404(self, auth_client, ids, app):
        """ss_id valide mais activité incorrecte → 404 (mismatch activity_id)."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Softskill Mauvaise Act Delete", niveau="1")
        try:
            r = auth_client.delete(f"/softskills/999999/{ss_id}")
            assert r.status_code == 404
        finally:
            _delete_softskill(app, ss_id)

    def test_delete_softskill_idempotent_returns_404_on_second_call(self, auth_client, ids, app):
        """Supprimer deux fois la même softskill → 404 au deuxième appel."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Softskill Double Suppression", niveau="1")
        auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        r2 = auth_client.delete(f"/softskills/{ids['activity_id']}/{ss_id}")
        assert r2.status_code == 404


# ===========================================================================
# 4. GET /softskills/<activity_id>/render — fragment HTML
# ===========================================================================

class TestRenderSoftskills:

    def test_render_softskills_valid_activity_returns_200(self, auth_client, ids):
        """GET /softskills/<id>/render sur activité valide → 200 HTML."""
        r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
        assert r.status_code == 200
        assert b"<" in r.data

    def test_render_softskills_invalid_activity_returns_404(self, auth_client):
        """GET /softskills/999999/render → 404."""
        r = auth_client.get("/softskills/999999/render")
        assert r.status_code == 404

    def test_render_softskills_contains_seeded_content(self, auth_client, ids, app):
        """Le rendu HTML inclut une softskill créée au préalable."""
        ss_id = _create_softskill(app, ids["activity_id"], habilete="Softskill Rendu Test", niveau="2")
        try:
            r = auth_client.get(f"/softskills/{ids['activity_id']}/render")
            assert r.status_code == 200
            assert b"Softskill Rendu Test" in r.data
        finally:
            _delete_softskill(app, ss_id)
