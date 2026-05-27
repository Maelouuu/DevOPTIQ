# tests/test_23_performance_perso.py
"""
API Performance Personnalisée (/performance_perso)

Endpoints couverts :
  GET    /performance_perso/list
  POST   /performance_perso/create
  PUT    /performance_perso/update/<id>
  DELETE /performance_perso/delete/<id>
  GET    /performance_perso/history
  GET    /performance_perso/history/<perf_id>
  DELETE /performance_perso/history/<perf_id>
"""
import json
import pytest

pytestmark = pytest.mark.performance_perso


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create(auth_client, user_id, activity_id, content="Contenu test",
            status="non-validee", date="2024-01-15"):
    return auth_client.post(
        "/performance_perso/create",
        data=json.dumps({
            "user_id": user_id,
            "activity_id": activity_id,
            "content": content,
            "validation_status": status,
            "validation_date": date,
        }),
        content_type="application/json",
    )


# ===========================================================================
# 1. GET /performance_perso/list
# ===========================================================================

class TestListPerf:

    def test_list_returns_200_and_array(self, auth_client):
        r = auth_client.get("/performance_perso/list")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_list_filter_by_user_id(self, auth_client, ids):
        _create(auth_client, ids["user_id"], ids["activity_id"], "Filtre user test")
        r = auth_client.get(f"/performance_perso/list?user_id={ids['user_id']}")
        assert r.status_code == 200
        data = r.get_json()
        assert all(p["user_id"] == ids["user_id"] for p in data)

    def test_list_filter_by_activity_id(self, auth_client, ids):
        r = auth_client.get(f"/performance_perso/list?activity_id={ids['activity_id']}")
        assert r.status_code == 200
        for item in r.get_json():
            assert item["activity_id"] == ids["activity_id"]

    def test_list_unknown_user_returns_empty_array(self, auth_client):
        r = auth_client.get("/performance_perso/list?user_id=999999")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_list_excludes_soft_deleted(self, auth_client, ids):
        """Un enregistrement soft-deleté ne doit pas apparaître dans la liste."""
        create_r = _create(auth_client, ids["user_id"], ids["activity_id"], "A supprimer")
        perf_id = create_r.get_json()["item"]["id"]

        auth_client.delete(f"/performance_perso/delete/{perf_id}")

        r = auth_client.get(f"/performance_perso/list?activity_id={ids['activity_id']}")
        ids_in_list = [p["id"] for p in r.get_json()]
        assert perf_id not in ids_in_list


# ===========================================================================
# 2. POST /performance_perso/create
# ===========================================================================

class TestCreatePerf:

    def test_create_returns_201_or_200_with_item(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Nouvelle perf")
        assert r.status_code in (200, 201)
        body = r.get_json()
        assert body["ok"] is True
        assert "item" in body
        assert body["item"]["content"] == "Nouvelle perf"

    def test_create_default_status_non_validee(self, auth_client, ids):
        r = auth_client.post(
            "/performance_perso/create",
            data=json.dumps({
                "user_id": ids["user_id"],
                "activity_id": ids["activity_id"],
                "content": "Statut par défaut",
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        assert r.get_json()["item"]["validation_status"] == "non-validee"

    def test_create_status_validee_normalisation(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"],
                    "Statut validée", status="validée")
        assert r.get_json()["item"]["validation_status"] == "validee"

    def test_create_status_true_maps_to_validee(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"],
                    "Statut true", status="true")
        assert r.get_json()["item"]["validation_status"] == "validee"

    def test_create_missing_user_id_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/performance_perso/create",
            data=json.dumps({"activity_id": ids["activity_id"], "content": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["ok"] is False

    def test_create_missing_activity_id_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/performance_perso/create",
            data=json.dumps({"user_id": ids["user_id"], "content": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_create_empty_content_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/performance_perso/create",
            data=json.dumps({
                "user_id": ids["user_id"],
                "activity_id": ids["activity_id"],
                "content": "   ",
            }),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["ok"] is False

    def test_create_accepts_contenu_alias(self, auth_client, ids):
        """Le champ 'contenu' est un alias de 'content'."""
        r = auth_client.post(
            "/performance_perso/create",
            data=json.dumps({
                "user_id": ids["user_id"],
                "activity_id": ids["activity_id"],
                "contenu": "Via alias contenu",
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        assert r.get_json()["ok"] is True

    def test_create_item_appears_in_list(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Visible dans liste")
        perf_id = r.get_json()["item"]["id"]

        list_r = auth_client.get(f"/performance_perso/list?user_id={ids['user_id']}")
        ids_in_list = [p["id"] for p in list_r.get_json()]
        assert perf_id in ids_in_list


# ===========================================================================
# 3. PUT /performance_perso/update/<id>
# ===========================================================================

class TestUpdatePerf:

    def _setup(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Avant mise à jour")
        return r.get_json()["item"]["id"]

    def test_update_content_returns_200(self, auth_client, ids):
        perf_id = self._setup(auth_client, ids)
        r = auth_client.put(
            f"/performance_perso/update/{perf_id}",
            data=json.dumps({"content": "Après mise à jour"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["item"]["content"] == "Après mise à jour"

    def test_update_validation_status(self, auth_client, ids):
        perf_id = self._setup(auth_client, ids)
        r = auth_client.put(
            f"/performance_perso/update/{perf_id}",
            data=json.dumps({"validation_status": "validee"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["item"]["validation_status"] == "validee"

    def test_update_no_change_returns_ok(self, auth_client, ids):
        """Mise à jour sans changement → ok=True sans erreur."""
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Immuable")
        perf_id = r.get_json()["item"]["id"]
        item = r.get_json()["item"]

        r2 = auth_client.put(
            f"/performance_perso/update/{perf_id}",
            data=json.dumps({
                "content": item["content"],
                "validation_status": item["validation_status"],
                "validation_date": item["validation_date"],
            }),
            content_type="application/json",
        )
        assert r2.status_code == 200
        assert r2.get_json()["ok"] is True

    def test_update_nonexistent_returns_404(self, auth_client):
        r = auth_client.put(
            "/performance_perso/update/999999",
            data=json.dumps({"content": "X"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_update_contenu_alias(self, auth_client, ids):
        perf_id = self._setup(auth_client, ids)
        r = auth_client.put(
            f"/performance_perso/update/{perf_id}",
            data=json.dumps({"contenu": "Via alias contenu update"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["item"]["content"] == "Via alias contenu update"


# ===========================================================================
# 4. DELETE /performance_perso/delete/<id>
# ===========================================================================

class TestDeletePerf:

    def test_delete_soft_returns_200_ok(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "À supprimer")
        perf_id = r.get_json()["item"]["id"]

        del_r = auth_client.delete(f"/performance_perso/delete/{perf_id}")
        assert del_r.status_code == 200
        assert del_r.get_json()["ok"] is True

    def test_delete_nonexistent_returns_404(self, auth_client):
        r = auth_client.delete("/performance_perso/delete/999999")
        assert r.status_code == 404

    def test_delete_marks_deleted_flag(self, auth_client, ids, app):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Flag deleted")
        perf_id = r.get_json()["item"]["id"]

        auth_client.delete(f"/performance_perso/delete/{perf_id}")

        with app.app_context():
            from Code.models.models import PerformancePersonnalisee
            p = PerformancePersonnalisee.query.get(perf_id)
            assert p is not None
            assert p.deleted is True


# ===========================================================================
# 5. GET /performance_perso/history
# ===========================================================================

class TestHistoryPerf:

    def test_history_list_returns_200(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Pour historique")
        r.get_json()["item"]["id"]

        hist = auth_client.get(
            f"/performance_perso/history?user_id={ids['user_id']}&activity_id={ids['activity_id']}"
        )
        assert hist.status_code == 200
        body = hist.get_json()
        assert "history" in body
        assert isinstance(body["history"], list)

    def test_history_create_event_recorded(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Historique création")
        perf_id = r.get_json()["item"]["id"]

        hist = auth_client.get(f"/performance_perso/history/{perf_id}")
        assert hist.status_code == 200
        events = [row["event"] for row in hist.get_json()["history"]]
        assert "created" in events

    def test_history_update_event_recorded(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Avant update hist")
        perf_id = r.get_json()["item"]["id"]

        auth_client.put(
            f"/performance_perso/update/{perf_id}",
            data=json.dumps({"content": "Après update hist"}),
            content_type="application/json",
        )

        hist = auth_client.get(f"/performance_perso/history/{perf_id}")
        events = [row["event"] for row in hist.get_json()["history"]]
        assert "before_update" in events

    def test_history_delete_event_recorded(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Avant delete hist")
        perf_id = r.get_json()["item"]["id"]

        auth_client.delete(f"/performance_perso/delete/{perf_id}")

        hist = auth_client.get(f"/performance_perso/history/{perf_id}")
        events = [row["event"] for row in hist.get_json()["history"]]
        assert "deleted" in events

    def test_history_by_perf_id_returns_performance_id(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "Ref perf_id")
        perf_id = r.get_json()["item"]["id"]

        hist = auth_client.get(f"/performance_perso/history/{perf_id}")
        assert hist.get_json()["performance_id"] == perf_id

    def test_history_unknown_perf_id_returns_empty(self, auth_client):
        hist = auth_client.get("/performance_perso/history/999999")
        assert hist.status_code == 200
        assert hist.get_json()["history"] == []

    def test_history_delete_purges_records(self, auth_client, ids):
        r = _create(auth_client, ids["user_id"], ids["activity_id"], "À purger")
        perf_id = r.get_json()["item"]["id"]

        # S'assurer qu'il y a au moins un enregistrement d'historique
        hist_before = auth_client.get(f"/performance_perso/history/{perf_id}")
        assert len(hist_before.get_json()["history"]) >= 1

        # Purge
        del_r = auth_client.delete(f"/performance_perso/history/{perf_id}")
        assert del_r.status_code == 200
        assert del_r.get_json()["purged"] is True

        hist_after = auth_client.get(f"/performance_perso/history/{perf_id}")
        assert hist_after.get_json()["history"] == []
