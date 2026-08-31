# tests/test_25_competences_plan.py
"""
Routes : Plan de Compétences (/competences_plan)

Modules couverts :
  competences_plan.py  →  /competences_plan/save_prerequis
                           /competences_plan/get_prerequis/<uid>/<aid>
                           /competences_plan/generate_plan
  plan_storage.py      →  /competences_plan/save_plan
                           /competences_plan/get_plan/<uid>/<aid>

Note : les tables prerequis_comment et training_plan sont créées à la volée par
_ensure_tables_exist() dans competences_plan.py.
La table user_activity_plans est créée dans le fixture de ce module.
"""
import json
import pytest

pytestmark = pytest.mark.competences_plan


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeChatCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content=None, raise_exc=None):
        self.completions = _FakeChatCompletions(content, raise_exc)


class _FakeAiClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = _FakeChat(content, raise_exc)


def _mock_llm(monkeypatch, content=None, raise_exc=None, model="gpt-4o-mini"):
    monkeypatch.setattr("Code.routes.competences_plan.get_openai_key", lambda: "sk-fake-test-key")
    fake_client = _FakeAiClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr("Code.ai_client.make_ai_client", lambda: (fake_client, model, None))


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def create_user_activity_plans_table(app):
    """Crée la table user_activity_plans si elle n'existe pas (SQLite test)."""
    with app.app_context():
        from sqlalchemy import text
        from Code.extensions import db
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS user_activity_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_id INTEGER NOT NULL,
                role_id INTEGER,
                content TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """))
        db.session.commit()


# ===========================================================================
# 1. POST /competences_plan/save_prerequis — Sauvegarde des prérequis
# ===========================================================================

class TestSavePrequis:

    def _payload(self, ids, comments=None):
        return json.dumps({
            "user_id": ids["user_id"],
            "activity_id": ids["activity_id"],
            "comments": comments or [],
        })

    def test_save_prerequis_returns_ok(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/save_prerequis",
            data=self._payload(ids),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_save_prerequis_with_comments(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/save_prerequis",
            data=self._payload(ids, comments=[
                {"item_type": "savoir", "item_id": 1, "comment": "Déjà maîtrisé"},
            ]),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_save_prerequis_multiple_comments(self, auth_client, ids):
        comments = [
            {"item_type": "savoir", "item_id": 1, "comment": "OK"},
            {"item_type": "savoir_faire", "item_id": 2, "comment": "À renforcer"},
            {"item_type": "hsc", "item_id": 3, "comment": ""},
        ]
        r = auth_client.post(
            "/competences_plan/save_prerequis",
            data=self._payload(ids, comments=comments),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_save_prerequis_replaces_previous(self, auth_client, ids):
        """Un second save doit remplacer les commentaires précédents (upsert)."""
        auth_client.post(
            "/competences_plan/save_prerequis",
            data=self._payload(ids, comments=[
                {"item_type": "savoir", "item_id": 1, "comment": "Première version"},
            ]),
            content_type="application/json",
        )
        auth_client.post(
            "/competences_plan/save_prerequis",
            data=self._payload(ids, comments=[
                {"item_type": "savoir", "item_id": 1, "comment": "Deuxième version"},
            ]),
            content_type="application/json",
        )
        r = auth_client.get(
            f"/competences_plan/get_prerequis/{ids['user_id']}/{ids['activity_id']}"
        )
        comments = r.get_json()
        assert all(c["comment"] != "Première version" for c in comments)

    def test_save_prerequis_empty_comments_clears_all(self, auth_client, ids):
        """Sauvegarder une liste vide doit effacer les commentaires précédents."""
        auth_client.post(
            "/competences_plan/save_prerequis",
            data=self._payload(ids, comments=[
                {"item_type": "savoir", "item_id": 1, "comment": "À effacer"},
            ]),
            content_type="application/json",
        )
        auth_client.post(
            "/competences_plan/save_prerequis",
            data=self._payload(ids, comments=[]),
            content_type="application/json",
        )
        r = auth_client.get(
            f"/competences_plan/get_prerequis/{ids['user_id']}/{ids['activity_id']}"
        )
        assert r.get_json() == []


# ===========================================================================
# 2. GET /competences_plan/get_prerequis/<uid>/<aid> — Lecture des prérequis
# ===========================================================================

class TestGetPrerequisites:

    def test_get_returns_list(self, auth_client, ids):
        r = auth_client.get(
            f"/competences_plan/get_prerequis/{ids['user_id']}/{ids['activity_id']}"
        )
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_get_unknown_user_returns_empty_list(self, auth_client, ids):
        r = auth_client.get(
            f"/competences_plan/get_prerequis/999999/{ids['activity_id']}"
        )
        assert r.status_code == 200
        assert r.get_json() == []

    def test_get_after_save_returns_saved_comments(self, auth_client, ids):
        auth_client.post(
            "/competences_plan/save_prerequis",
            data=json.dumps({
                "user_id": ids["user_id"],
                "activity_id": ids["activity_id"],
                "comments": [
                    {"item_type": "aptitude", "item_id": 5, "comment": "Bon niveau"},
                ],
            }),
            content_type="application/json",
        )
        r = auth_client.get(
            f"/competences_plan/get_prerequis/{ids['user_id']}/{ids['activity_id']}"
        )
        data = r.get_json()
        assert any(c["item_type"] == "aptitude" for c in data)

    def test_get_returns_expected_fields(self, auth_client, ids):
        """Chaque item doit avoir item_type, item_id et comment."""
        auth_client.post(
            "/competences_plan/save_prerequis",
            data=json.dumps({
                "user_id": ids["user_id"],
                "activity_id": ids["activity_id"],
                "comments": [
                    {"item_type": "savoir_faire", "item_id": 7, "comment": "Niveau suffisant"},
                ],
            }),
            content_type="application/json",
        )
        r = auth_client.get(
            f"/competences_plan/get_prerequis/{ids['user_id']}/{ids['activity_id']}"
        )
        data = r.get_json()
        assert len(data) >= 1
        first = data[0]
        assert "item_type" in first
        assert "item_id" in first
        assert "comment" in first


# ===========================================================================
# 3. POST /competences_plan/generate_plan — Génération de plan (dummy sans API)
# ===========================================================================

class TestGeneratePlan:

    def _payload(self, ids):
        return json.dumps({
            "user_id": ids["user_id"],
            "role_id": 1,
            "activity_id": ids["activity_id"],
            "payload_contexte": {
                "role": {"name": "Rôle Test"},
                "activity": {"name": "Activité Test"},
                "evaluations": {},
                "prerequis_comments": [],
            },
        })

    def test_generate_plan_returns_ok_true(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_generate_plan_returns_plan_key(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        body = r.get_json()
        assert "plan" in body
        assert isinstance(body["plan"], dict)

    def test_generate_plan_dummy_has_type_field(self, auth_client, ids):
        """Sans OPENAI_API_KEY, le plan dummy est renvoyé avec un champ 'type'."""
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        plan = r.get_json()["plan"]
        assert "type" in plan

    def test_generate_plan_dummy_has_axes(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        plan = r.get_json()["plan"]
        assert "axes" in plan
        assert isinstance(plan["axes"], list)

    def test_generate_plan_with_empty_contexte(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=json.dumps({
                "user_id": ids["user_id"],
                "role_id": 1,
                "activity_id": ids["activity_id"],
                "payload_contexte": {},
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_generate_plan_no_prompt_header_returns_503(self, auth_client, ids, monkeypatch):
        monkeypatch.setattr("Code.routes.competences_plan.get_prompt", lambda key: None)
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        assert r.status_code == 503
        assert r.get_json()["ok"] is False

    def test_generate_plan_missing_field_falls_back_with_warning(self, auth_client):
        """Un payload incomplet (KeyError dans le bloc principal) doit renvoyer un plan
        dummy annoté plutôt qu'une 500."""
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=json.dumps({"user_id": 1}),
            content_type="application/json",
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert "warning" in body
        assert body["plan"]["meta"]["source"] == "error_fallback"

    def test_generate_plan_with_ai_success_returns_parsed_plan(self, auth_client, ids, monkeypatch):
        content = json.dumps({"type": "PLAN_IA", "axes": [{"intitule": "Axe IA"}]})
        _mock_llm(monkeypatch, content=content)
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        assert r.status_code == 200
        plan = r.get_json()["plan"]
        assert plan["type"] == "PLAN_IA"
        assert plan["axes"] == [{"intitule": "Axe IA"}]

    def test_generate_plan_with_ai_wrapped_json_is_extracted(self, auth_client, ids, monkeypatch):
        """Le modèle a entouré le JSON de texte libre : on l'extrait via regex."""
        content = 'Voici le plan demandé :\n{"type": "PLAN_WRAPPED", "axes": []}'
        _mock_llm(monkeypatch, content=content)
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.get_json()["plan"]["type"] == "PLAN_WRAPPED"

    def test_generate_plan_with_ai_unparseable_content_falls_back_dummy(self, auth_client, ids, monkeypatch):
        _mock_llm(monkeypatch, content="Ceci n'est pas du JSON du tout.")
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        assert r.status_code == 200
        plan = r.get_json()["plan"]
        assert plan["meta"]["source"] == "fallback_parse_error"

    def test_generate_plan_with_ai_exception_falls_back_dummy(self, auth_client, ids, monkeypatch):
        _mock_llm(monkeypatch, raise_exc=RuntimeError("boom-ia"))
        r = auth_client.post(
            "/competences_plan/generate_plan",
            data=self._payload(ids),
            content_type="application/json",
        )
        assert r.status_code == 200
        plan = r.get_json()["plan"]
        assert plan["meta"]["source"] == "fallback_exception"
        assert "boom-ia" in plan["meta"]["error"]


# ===========================================================================
# 4. POST /competences_plan/save_plan — Enregistrement d'un plan personnalisé
# ===========================================================================

class TestSavePlan:

    def test_save_plan_creates_new_entry(self, auth_client, ids, app):
        """Premier enregistrement pour un couple (user, activity) inexistant → created=True."""
        uid = ids["user_id"] + 100
        aid = ids["activity_id"] + 100
        with app.app_context():
            from sqlalchemy import text
            from Code.extensions import db
            db.session.execute(text(
                "DELETE FROM user_activity_plans WHERE user_id=:u AND activity_id=:a"
            ), {"u": uid, "a": aid})
            db.session.commit()

        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({"user_id": uid, "activity_id": aid, "role_id": None,
                             "plan": {"title": "Mon plan", "steps": ["Étape 1"]}, "force": False}),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        body = r.get_json()
        assert body["ok"] is True
        assert body.get("created") is True

    def test_save_plan_returns_plan_id(self, auth_client, ids, app):
        uid = ids["user_id"] + 1000
        aid = ids["activity_id"] + 1000
        with app.app_context():
            from sqlalchemy import text
            from Code.extensions import db
            db.session.execute(text(
                "DELETE FROM user_activity_plans WHERE user_id=:u AND activity_id=:a"
            ), {"u": uid, "a": aid})
            db.session.commit()

        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({
                "user_id": uid,
                "activity_id": aid,
                "role_id": None,
                "plan": {"data": "test"},
                "force": False,
            }),
            content_type="application/json",
        )
        assert r.status_code in (200, 201)
        body = r.get_json()
        assert "plan_id" in body

    def test_save_plan_conflict_returns_409_without_force(self, auth_client, ids, app):
        """Sauvegarder deux fois le même (user, activity) sans force → 409."""
        uid = ids["user_id"] + 2000
        aid = ids["activity_id"] + 2000

        with app.app_context():
            from sqlalchemy import text
            from Code.extensions import db
            db.session.execute(text(
                "DELETE FROM user_activity_plans WHERE user_id=:u AND activity_id=:a"
            ), {"u": uid, "a": aid})
            db.session.commit()

        payload = json.dumps({
            "user_id": uid,
            "activity_id": aid,
            "role_id": None,
            "plan": {"step": "v1"},
            "force": False,
        })
        auth_client.post("/competences_plan/save_plan", data=payload, content_type="application/json")
        r2 = auth_client.post("/competences_plan/save_plan", data=payload, content_type="application/json")
        assert r2.status_code == 409
        body = r2.get_json()
        assert body["ok"] is False
        assert body.get("exists") is True

    def test_save_plan_force_true_replaces_existing(self, auth_client, ids, app):
        """force=True doit mettre à jour une entrée existante sans erreur."""
        uid = ids["user_id"] + 3000
        aid = ids["activity_id"] + 3000

        with app.app_context():
            from sqlalchemy import text
            from Code.extensions import db
            db.session.execute(text(
                "DELETE FROM user_activity_plans WHERE user_id=:u AND activity_id=:a"
            ), {"u": uid, "a": aid})
            db.session.commit()

        first = json.dumps({"user_id": uid, "activity_id": aid, "role_id": None, "plan": {"v": 1}, "force": False})
        auth_client.post("/competences_plan/save_plan", data=first, content_type="application/json")

        second = json.dumps({"user_id": uid, "activity_id": aid, "role_id": None, "plan": {"v": 2}, "force": True})
        r = auth_client.post("/competences_plan/save_plan", data=second, content_type="application/json")

        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert body.get("replaced") is True

    def test_save_plan_missing_user_id_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({"activity_id": ids["activity_id"], "plan": {}}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert r.get_json()["ok"] is False

    def test_save_plan_missing_activity_id_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({"user_id": ids["user_id"], "plan": {}}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_save_plan_missing_plan_returns_400(self, auth_client, ids):
        r = auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({"user_id": ids["user_id"], "activity_id": ids["activity_id"]}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ===========================================================================
# 5. GET /competences_plan/get_plan/<uid>/<aid> — Récupération d'un plan
# ===========================================================================

class TestGetPlan:

    def test_get_plan_unknown_returns_404(self, auth_client):
        r = auth_client.get("/competences_plan/get_plan/999999/999999")
        assert r.status_code == 404
        assert r.get_json()["ok"] is False

    def test_get_plan_after_save_returns_ok(self, auth_client, ids, app):
        uid = ids["user_id"] + 4000
        aid = ids["activity_id"] + 4000

        with app.app_context():
            from sqlalchemy import text
            from Code.extensions import db
            db.session.execute(text(
                "DELETE FROM user_activity_plans WHERE user_id=:u AND activity_id=:a"
            ), {"u": uid, "a": aid})
            db.session.commit()

        auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({"user_id": uid, "activity_id": aid, "role_id": None, "plan": {"key": "val"}, "force": False}),
            content_type="application/json",
        )

        r = auth_client.get(f"/competences_plan/get_plan/{uid}/{aid}")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert "plan" in body

    def test_get_plan_returns_correct_content(self, auth_client, ids, app):
        uid = ids["user_id"] + 5000
        aid = ids["activity_id"] + 5000

        with app.app_context():
            from sqlalchemy import text
            from Code.extensions import db
            db.session.execute(text(
                "DELETE FROM user_activity_plans WHERE user_id=:u AND activity_id=:a"
            ), {"u": uid, "a": aid})
            db.session.commit()

        plan_data = {"title": "Plan de formation Q1", "weeks": 8}
        auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({"user_id": uid, "activity_id": aid, "role_id": None, "plan": plan_data, "force": False}),
            content_type="application/json",
        )

        r = auth_client.get(f"/competences_plan/get_plan/{uid}/{aid}")
        assert r.get_json()["plan"] == plan_data

    def test_get_plan_has_meta_fields(self, auth_client, ids, app):
        uid = ids["user_id"] + 6000
        aid = ids["activity_id"] + 6000

        with app.app_context():
            from sqlalchemy import text
            from Code.extensions import db
            db.session.execute(text(
                "DELETE FROM user_activity_plans WHERE user_id=:u AND activity_id=:a"
            ), {"u": uid, "a": aid})
            db.session.commit()

        auth_client.post(
            "/competences_plan/save_plan",
            data=json.dumps({"user_id": uid, "activity_id": aid, "role_id": 42, "plan": {}, "force": False}),
            content_type="application/json",
        )

        r = auth_client.get(f"/competences_plan/get_plan/{uid}/{aid}")
        meta = r.get_json().get("meta", {})
        assert "updated_at" in meta
        assert "created_at" in meta
