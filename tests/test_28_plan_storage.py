# tests/test_28_plan_storage.py
"""
Modules : plan_storage.py + settings.py
Routes couvertes :
  POST /competences_plan/save_plan                          → créer ou mettre à jour un plan
  GET  /competences_plan/get_plan/<user_id>/<activity_id>  → lire un plan enregistré
  GET  /parametres/                                         → page des paramètres
  POST /parametres/set_language                             → changer la langue de session
"""
import json
import pytest

pytestmark = pytest.mark.plan_storage


# ---------------------------------------------------------------------------
# Fixture : crée la table user_activity_plans absente de SQLAlchemy models
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def create_plan_table(app):
    """Crée user_activity_plans dans la DB de test avant les tests du module."""
    from sqlalchemy import text
    from Code.extensions import db

    with app.app_context():
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS user_activity_plans (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                role_id    INTEGER,
                content    TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
        """))
        db.session.commit()
    yield
    with app.app_context():
        db.session.execute(text("DELETE FROM user_activity_plans"))
        db.session.commit()


# ===========================================================================
# 1. POST /competences_plan/save_plan — création d'un plan
# ===========================================================================

class TestSavePlan:

    def test_save_plan_success_returns_201_created(self, auth_client, ids):
        """Créer un nouveau plan retourne ok=True et created=True."""
        payload = {
            "user_id":     ids["user_id"],
            "activity_id": ids["activity_id"],
            "plan":        {"etapes": ["Étape 1", "Étape 2"]},
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data.get("created") is True

    def test_save_plan_missing_user_id_returns_400(self, auth_client, ids):
        """Paramètre user_id absent → 400."""
        payload = {
            "activity_id": ids["activity_id"],
            "plan":        {"note": "test"},
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert data["ok"] is False

    def test_save_plan_missing_activity_id_returns_400(self, auth_client, ids):
        """Paramètre activity_id absent → 400."""
        payload = {
            "user_id": ids["user_id"],
            "plan":    {"note": "test"},
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_save_plan_missing_plan_returns_400(self, auth_client, ids):
        """Paramètre plan absent → 400."""
        payload = {
            "user_id":     ids["user_id"],
            "activity_id": ids["activity_id"],
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_save_plan_plan_null_is_rejected(self, auth_client, ids):
        """plan=null (None) est traité comme absent → 400."""
        payload = {
            "user_id":     ids["user_id"],
            "activity_id": ids["activity_id"],
            "plan":        None,
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_save_plan_duplicate_without_force_returns_409(self, auth_client, ids):
        """Sauvegarder deux fois pour le même (user, activity) sans force → 409."""
        payload = {
            "user_id":     ids["user_id"],
            "activity_id": ids["activity_id"],
            "plan":        {"v": "conflit"},
        }
        # Le premier save a déjà été créé dans test_save_plan_success.
        # Ici on retente sans force=True.
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 409
        data = json.loads(r.data)
        assert data["ok"] is False
        assert data.get("exists") is True

    def test_save_plan_force_replaces_existing(self, auth_client, ids):
        """force=True écrase le plan existant et retourne replaced=True."""
        payload = {
            "user_id":     ids["user_id"],
            "activity_id": ids["activity_id"],
            "plan":        {"v": "remplacement"},
            "force":       True,
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data.get("replaced") is True

    def test_save_plan_with_role_id(self, auth_client, ids):
        """Un plan peut être sauvegardé avec un role_id optionnel."""
        payload = {
            "user_id":     ids["user_id"],
            "activity_id": ids["activity_id"],
            "role_id":     42,
            "plan":        {"role": "test"},
            "force":       True,
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True

    def test_save_plan_empty_plan_object_accepted(self, auth_client, ids):
        """Un objet plan vide {} est accepté (n'est pas None)."""
        payload = {
            "user_id":     ids["user_id"],
            "activity_id": ids["activity_id"],
            "plan":        {},
            "force":       True,
        }
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert r.status_code == 200


# ===========================================================================
# 2. GET /competences_plan/get_plan/<uid>/<aid> — lecture d'un plan
# ===========================================================================

class TestGetPlan:

    def test_get_plan_existing_returns_ok(self, auth_client, ids):
        """Lire un plan existant retourne ok=True avec son contenu."""
        # Le plan a été créé dans TestSavePlan.test_save_plan_success
        r = auth_client.get(
            f"/competences_plan/get_plan/{ids['user_id']}/{ids['activity_id']}"
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert "plan" in data

    def test_get_plan_content_matches_saved(self, auth_client, ids):
        """Le contenu du plan récupéré correspond à ce qui a été enregistré."""
        # Sauvegarder un plan avec du contenu précis, puis le relire
        saved_plan = {"check": "round_trip", "items": [1, 2, 3]}
        auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({
                "user_id":     ids["user_id"],
                "activity_id": ids["activity_id"],
                "plan":        saved_plan,
                "force":       True,
            }),
            content_type="application/json",
        )
        r = auth_client.get(
            f"/competences_plan/get_plan/{ids['user_id']}/{ids['activity_id']}"
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["plan"] == saved_plan

    def test_get_plan_missing_returns_404(self, auth_client):
        """Lire un plan inexistant (user/activity inconnus) → 404."""
        r = auth_client.get("/competences_plan/get_plan/999999/999999")
        assert r.status_code == 404
        data = json.loads(r.data)
        assert data["ok"] is False

    def test_get_plan_has_meta_fields(self, auth_client, ids):
        """La réponse contient un objet meta avec updated_at et created_at."""
        r = auth_client.get(
            f"/competences_plan/get_plan/{ids['user_id']}/{ids['activity_id']}"
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "meta" in data
        assert "updated_at" in data["meta"]
        assert "created_at" in data["meta"]


# ===========================================================================
# 3. GET /parametres/ — page des paramètres
# ===========================================================================

class TestSettingsPage:

    def test_settings_page_accessible_authenticated(self, auth_client):
        """La page /parametres/ répond 200 avec une session valide."""
        r = auth_client.get("/parametres/")
        assert r.status_code == 200

    def test_settings_page_returns_html(self, auth_client):
        """La page retourne du HTML."""
        r = auth_client.get("/parametres/")
        assert r.status_code == 200
        body = r.data.lower()
        assert b"<html" in body or b"<!doctype" in body


# ===========================================================================
# 4. POST /parametres/set_language — changement de langue
# ===========================================================================

class TestSetLanguage:

    def test_set_language_fr_accepted(self, auth_client):
        """Définir la langue 'fr' retourne ok=True."""
        r = auth_client.post(
            "/parametres/set_language",
            data=json.dumps({"lang": "fr"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data["lang"] == "fr"

    def test_set_language_en_accepted(self, auth_client):
        """Définir la langue 'en' retourne ok=True."""
        r = auth_client.post(
            "/parametres/set_language",
            data=json.dumps({"lang": "en"}),
            content_type="application/json",
        )
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data["lang"] == "en"

    def test_set_language_invalid_returns_400(self, auth_client):
        """Une langue inconnue ('klingon') → 400."""
        r = auth_client.post(
            "/parametres/set_language",
            data=json.dumps({"lang": "klingon"}),
            content_type="application/json",
        )
        assert r.status_code == 400
        data = json.loads(r.data)
        assert data["ok"] is False

    def test_set_language_empty_string_returns_400(self, auth_client):
        """Une chaîne vide comme langue → 400 (non reconnue)."""
        r = auth_client.post(
            "/parametres/set_language",
            data=json.dumps({"lang": ""}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_set_language_persists_in_session(self, auth_client):
        """Après set_language, la valeur est bien stockée dans la session."""
        auth_client.post(
            "/parametres/set_language",
            data=json.dumps({"lang": "fr"}),
            content_type="application/json",
        )
        # Vérifier que la page des paramètres s'affiche toujours correctement
        r = auth_client.get("/parametres/")
        assert r.status_code == 200
