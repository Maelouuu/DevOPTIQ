"""
Couverture avancée de deux endpoints déjà partiellement testés (test_40) :
  - activities_cartography.py → GET /activities/update-cartography (succès + exception)
  - translate_softskills.py   → POST /translate_softskills/translate (client IA mocké :
    succès FR/EN, JSON invalide, JSON non-liste, exception du client)

Le client IA et process_visio_file sont mockés : on ne touche jamais à un vrai
service externe ni à la base partagée (scope=session) via le parseur VSDX réel,
qui manipule des tables globales et polluerait les autres tests.
"""
import os
import pytest
from types import SimpleNamespace

pytestmark = pytest.mark.cartography_translate_advanced


def _set_svg_filename(app, entity_id, value):
    with app.app_context():
        from Code.models.models import Entity
        from Code.extensions import db
        entity = db.session.get(Entity, entity_id)
        entity.svg_filename = value
        db.session.commit()


# ===========================================================================
# GET /activities/update-cartography — chemin succès (200) et exception (500)
# ===========================================================================

class TestUpdateCartographySuccessAndError:

    def test_success_returns_200_with_summary(self, auth_client, ids, app, monkeypatch, tmp_path):
        """Fichier présent + traitement OK → 200 avec message/summary/file."""
        fake_file = tmp_path / "carto_ok.vsdx"
        fake_file.write_bytes(b"fake")
        _set_svg_filename(app, ids["entity_id"], str(fake_file))

        monkeypatch.setattr(
            "Code.routes.activities_cartography.process_visio_file",
            lambda path: None,
        )
        monkeypatch.setattr(
            "Code.routes.activities_cartography.print_summary",
            lambda: print("Résumé fictif de la cartographie"),
        )

        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 200
            body = r.get_json()
            assert "message" in body
            assert "summary" in body
            assert "Résumé fictif" in body["summary"]
            assert body["file"] == str(fake_file)
        finally:
            _set_svg_filename(app, ids["entity_id"], None)

    def test_processing_exception_returns_500(self, auth_client, ids, app, monkeypatch, tmp_path):
        """process_visio_file lève une exception → 500 + message d'erreur."""
        fake_file = tmp_path / "carto_broken.vsdx"
        fake_file.write_bytes(b"fake")
        _set_svg_filename(app, ids["entity_id"], str(fake_file))

        def _boom(path):
            raise ValueError("fichier visio corrompu")

        monkeypatch.setattr(
            "Code.routes.activities_cartography.process_visio_file", _boom
        )

        try:
            r = auth_client.get("/activities/update-cartography")
            assert r.status_code == 500
            body = r.get_json()
            assert "fichier visio corrompu" in body["error"]
            assert "message" in body
        finally:
            _set_svg_filename(app, ids["entity_id"], None)


# ===========================================================================
# POST /translate_softskills/translate — client IA mocké
# ===========================================================================

class _FakeCompletions:
    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc

    def create(self, **kwargs):
        if self._raise_exc:
            raise self._raise_exc
        message = SimpleNamespace(content=self._content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeClient:
    def __init__(self, content=None, raise_exc=None):
        self.chat = SimpleNamespace(
            completions=_FakeCompletions(content=content, raise_exc=raise_exc)
        )


def _patch_client(monkeypatch, content=None, raise_exc=None):
    fake = _FakeClient(content=content, raise_exc=raise_exc)
    monkeypatch.setattr(
        "Code.routes.translate_softskills.get_openai_client",
        lambda: (fake, None),
    )


class TestTranslateSoftskillsWithMockedClient:

    def test_success_fr_maps_niveau_and_includes_outgoing_performance(
        self, auth_client, monkeypatch
    ):
        """Réponse IA valide (liste) → 200, niveau FR mappé, perf 'outgoing' prise en compte."""
        _patch_client(
            monkeypatch,
            content='[{"habilete": "Communication", "niveau": "2"}]',
        )
        r = auth_client.post(
            "/translate_softskills/translate",
            json={
                "user_input": "communication, leadership",
                "activity_data": {
                    "name": "Activité Test",
                    "tasks": [{"description": "Tâche A"}],
                    "constraints": [{"description": "Délai serré"}],
                    "outgoing": [
                        {"performance": {"name": "Qualité", "description": "Taux de succès"}}
                    ],
                },
            },
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["proposals"][0]["niveau"] == "2 (Acquisition)"

    def test_success_en_uses_english_prompt_and_niveau_map(self, auth_client, monkeypatch):
        """lang='en' en session → prompt anglais + mapping de niveau anglais."""
        _patch_client(
            monkeypatch,
            content='[{"skill": "Communication", "niveau": "3"}]',
        )
        with auth_client.session_transaction() as sess:
            sess["lang"] = "en"
        try:
            r = auth_client.post(
                "/translate_softskills/translate",
                json={"user_input": "communication, leadership"},
            )
            assert r.status_code == 200
            body = r.get_json()
            assert body["proposals"][0]["niveau"] == "3 (Proficient)"
        finally:
            with auth_client.session_transaction() as sess:
                sess.pop("lang", None)

    def test_dict_response_is_wrapped_into_list(self, auth_client, monkeypatch):
        """Réponse IA = objet JSON unique (pas une liste) → encapsulé dans une liste."""
        _patch_client(monkeypatch, content='{"habilete": "Rigueur", "niveau": "1"}')
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "rigueur"},
        )
        assert r.status_code == 200
        body = r.get_json()
        assert isinstance(body["proposals"], list)
        assert body["proposals"][0]["habilete"] == "Rigueur"

    def test_non_object_json_returns_400(self, auth_client, monkeypatch):
        """Réponse IA = JSON valide mais ni liste ni objet (ex: nombre) → 400."""
        _patch_client(monkeypatch, content="42")
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "quelque chose"},
        )
        assert r.status_code == 400
        assert "tableau" in r.get_json()["error"].lower()

    def test_invalid_json_returns_400_with_parse_error(self, auth_client, monkeypatch):
        """Réponse IA non-JSON → 400 avec message de parsing."""
        _patch_client(monkeypatch, content="ceci n'est pas du json {")
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "quelque chose"},
        )
        assert r.status_code == 400
        assert "parsing" in r.get_json()["error"].lower()

    def test_client_exception_returns_500(self, auth_client, monkeypatch):
        """Le client IA lève une exception pendant l'appel → 500 + message d'erreur."""
        _patch_client(monkeypatch, raise_exc=RuntimeError("panne réseau IA"))
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "communication"},
        )
        assert r.status_code == 500
        assert "panne réseau IA" in r.get_json()["error"]

    def test_non_digit_niveau_left_untouched(self, auth_client, monkeypatch):
        """Un niveau déjà textuel (non digit) n'est pas réécrit par le mapping."""
        _patch_client(
            monkeypatch,
            content='[{"habilete": "Empathie", "niveau": "Expert"}]',
        )
        r = auth_client.post(
            "/translate_softskills/translate",
            json={"user_input": "empathie"},
        )
        assert r.status_code == 200
        assert r.get_json()["proposals"][0]["niveau"] == "Expert"
