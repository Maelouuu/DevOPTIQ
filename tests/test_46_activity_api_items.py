# tests/test_46_activity_api_items.py
"""
Routes couvertes :
  - activity_items_api.py  → GET /your_api/activity_items/<activity_id>
      Retourne les savoirs, savoir-faires et soft-skills (hsc) liés à une activité.
  - activities_render.py   → GET /activities/performance/render/<link_id>
      Retourne en JSON les Performance associées à un lien.
"""
import json
import pytest

pytestmark = pytest.mark.activity_api_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_savoir(app, activity_id, description="Savoir Test"):
    with app.app_context():
        from Code.models.models import Savoir
        from Code.extensions import db
        s = Savoir(description=description, activity_id=activity_id)
        db.session.add(s)
        db.session.commit()
        return s.id


def _create_savoir_faire(app, activity_id, description="Savoir-faire Test"):
    with app.app_context():
        from Code.models.models import SavoirFaire
        from Code.extensions import db
        sf = SavoirFaire(description=description, activity_id=activity_id)
        db.session.add(sf)
        db.session.commit()
        return sf.id


def _create_softskill(app, activity_id, habilete="Rigueur", niveau="3"):
    with app.app_context():
        from Code.models.models import Softskill
        from Code.extensions import db
        sk = Softskill(habilete=habilete, niveau=niveau, activity_id=activity_id)
        db.session.add(sk)
        db.session.commit()
        return sk.id


def _create_performance(app, link_id, name="Perf Test", description="Desc perf"):
    with app.app_context():
        from Code.models.models import Performance
        from Code.extensions import db
        # Performance has unique constraint on link_id — delete existing first
        existing = Performance.query.filter_by(link_id=link_id).first()
        if existing:
            db.session.delete(existing)
            db.session.flush()
        p = Performance(link_id=link_id, name=name, description=description)
        db.session.add(p)
        db.session.commit()
        return p.id


def _delete_by_id(app, model_cls, obj_id):
    with app.app_context():
        from Code.extensions import db
        obj = model_cls.query.get(obj_id)
        if obj:
            db.session.delete(obj)
            db.session.commit()


# ===========================================================================
# 1. API /your_api/activity_items/<activity_id>
# ===========================================================================

class TestActivityItemsAPI:
    """Endpoint activity_items_api.py — /your_api/activity_items/<id>"""

    def test_returns_json_structure(self, auth_client, ids):
        """La réponse contient bien les clés savoirs, savoir_faire et hsc."""
        r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "savoirs" in data
        assert "savoir_faire" in data
        assert "hsc" in data

    def test_empty_activity_returns_empty_lists(self, app, ids):
        """Une activité sans items renvoie trois listes vides."""
        with app.app_context():
            from Code.models.models import Activities
            from Code.extensions import db
            act = Activities(entity_id=ids["entity_id"], name="Activité Vide Items", description="Test")
            db.session.add(act)
            db.session.commit()
            new_id = act.id

        from flask import current_app
        with app.test_client() as c:
            with app.app_context():
                from Code.models.models import User, Entity
                u = User.query.filter_by(email="test@devoptiq.com").first()
                e = Entity.query.get(ids["entity_id"])
            with c.session_transaction() as sess:
                sess["user_id"] = u.id
                sess["user_email"] = u.email
                sess["active_entity_id"] = e.id
            r = c.get(f"/your_api/activity_items/{new_id}")

        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["savoirs"] == []
        assert data["savoir_faire"] == []
        assert data["hsc"] == []

        with app.app_context():
            from Code.models.models import Activities
            from Code.extensions import db
            a = Activities.query.get(new_id)
            if a:
                db.session.delete(a)
                db.session.commit()

    def test_nonexistent_activity_returns_empty_lists(self, auth_client):
        """Un activity_id inexistant ne plante pas — retourne des listes vides."""
        r = auth_client.get("/your_api/activity_items/999999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["savoirs"] == []
        assert data["savoir_faire"] == []
        assert data["hsc"] == []

    def test_savoir_appears_in_response(self, auth_client, app, ids):
        """Un Savoir lié à l'activité doit apparaître dans la liste savoirs."""
        sid = _create_savoir(app, ids["activity_id"], "Savoir Visible")
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            names = [s["name"] for s in data["savoirs"]]
            assert "Savoir Visible" in names
        finally:
            with app.app_context():
                from Code.models.models import Savoir
                _delete_by_id(app, Savoir, sid)

    def test_savoir_item_has_id_and_name(self, auth_client, app, ids):
        """Chaque item savoir possède les champs id et name."""
        sid = _create_savoir(app, ids["activity_id"], "Savoir Champs")
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            data = json.loads(r.data)
            item = next((s for s in data["savoirs"] if s["id"] == sid), None)
            assert item is not None
            assert "id" in item
            assert "name" in item
        finally:
            with app.app_context():
                from Code.models.models import Savoir
                _delete_by_id(app, Savoir, sid)

    def test_savoir_faire_appears_in_response(self, auth_client, app, ids):
        """Un SavoirFaire lié à l'activité doit apparaître dans savoir_faire."""
        sfid = _create_savoir_faire(app, ids["activity_id"], "Savoir-faire Visible")
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            names = [sf["name"] for sf in data["savoir_faire"]]
            assert "Savoir-faire Visible" in names
        finally:
            with app.app_context():
                from Code.models.models import SavoirFaire
                _delete_by_id(app, SavoirFaire, sfid)

    def test_softskill_appears_in_hsc_with_formatted_name(self, auth_client, app, ids):
        """Un Softskill avec niveau est formaté 'Habilete (Niveau)' dans hsc."""
        skid = _create_softskill(app, ids["activity_id"], habilete="Créativité", niveau="2")
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            names = [h["name"] for h in data["hsc"]]
            assert any("Créativité" in n for n in names)
            assert any("(2)" in n for n in names)
        finally:
            with app.app_context():
                from Code.models.models import Softskill
                _delete_by_id(app, Softskill, skid)

    def test_softskill_without_niveau_has_plain_name(self, auth_client, app, ids):
        """Un Softskill sans niveau est affiché sans parenthèses dans hsc."""
        skid = _create_softskill(app, ids["activity_id"], habilete="Autonomie", niveau="")
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            names = [h["name"] for h in data["hsc"]]
            assert any("Autonomie" in n and "(" not in n for n in names)
        finally:
            with app.app_context():
                from Code.models.models import Softskill
                _delete_by_id(app, Softskill, skid)

    def test_multiple_items_all_returned(self, auth_client, app, ids):
        """Plusieurs savoirs pour la même activité sont tous retournés."""
        sid1 = _create_savoir(app, ids["activity_id"], "Savoir Multiple A")
        sid2 = _create_savoir(app, ids["activity_id"], "Savoir Multiple B")
        try:
            r = auth_client.get(f"/your_api/activity_items/{ids['activity_id']}")
            data = json.loads(r.data)
            ids_returned = [s["id"] for s in data["savoirs"]]
            assert sid1 in ids_returned
            assert sid2 in ids_returned
        finally:
            with app.app_context():
                from Code.models.models import Savoir
                _delete_by_id(app, Savoir, sid1)
                _delete_by_id(app, Savoir, sid2)

    def test_endpoint_accessible_without_auth(self, client, ids):
        """L'endpoint ne requiert pas d'authentification — retourne 200."""
        r = client.get(f"/your_api/activity_items/{ids['activity_id']}")
        assert r.status_code == 200


# ===========================================================================
# 2. GET /activities/performance/render/<link_id>
# ===========================================================================

class TestPerformanceRender:
    """Endpoint activities_render.py — /activities/performance/render/<link_id>"""

    def test_returns_json_list(self, auth_client, ids):
        """La réponse est un tableau JSON."""
        r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)

    def test_no_performance_returns_empty_list(self, auth_client, app, ids):
        """Un lien sans performance retourne une liste vide."""
        with app.app_context():
            from Code.models.models import Performance
            from Code.extensions import db
            Performance.query.filter_by(link_id=ids["link_id"]).delete()
            db.session.commit()

        r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_performance_appears_in_response(self, auth_client, app, ids):
        """Une Performance liée au lien est bien retournée."""
        pid = _create_performance(app, ids["link_id"], name="Perf Render", description="Desc render")
        try:
            r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
            assert r.status_code == 200
            data = json.loads(r.data)
            assert len(data) >= 1
            perf = next((p for p in data if p["id"] == pid), None)
            assert perf is not None
        finally:
            with app.app_context():
                from Code.models.models import Performance
                _delete_by_id(app, Performance, pid)

    def test_performance_item_has_required_fields(self, auth_client, app, ids):
        """Chaque entrée a les champs id, name, description."""
        pid = _create_performance(app, ids["link_id"], name="Perf Champs", description="Desc champs")
        try:
            r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
            data = json.loads(r.data)
            item = next((p for p in data if p["id"] == pid), None)
            assert item is not None
            assert "id" in item
            assert "name" in item
            assert "description" in item
        finally:
            with app.app_context():
                from Code.models.models import Performance
                _delete_by_id(app, Performance, pid)

    def test_nonexistent_link_returns_empty_list(self, auth_client):
        """Un link_id inexistant retourne une liste vide (pas de 404)."""
        r = auth_client.get("/activities/performance/render/999999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_performance_name_matches(self, auth_client, app, ids):
        """Le nom de la performance retournée correspond à celui sauvegardé."""
        pid = _create_performance(app, ids["link_id"], name="Nom Précis", description="")
        try:
            r = auth_client.get(f"/activities/performance/render/{ids['link_id']}")
            data = json.loads(r.data)
            item = next((p for p in data if p["id"] == pid), None)
            assert item is not None
            assert item["name"] == "Nom Précis"
        finally:
            with app.app_context():
                from Code.models.models import Performance
                _delete_by_id(app, Performance, pid)
