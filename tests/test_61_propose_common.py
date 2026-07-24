# tests/test_61_propose_common.py
# Couverture de Code/routes/propose_common.py — utilitaires partagés par les
# routes propose_savoirs/propose_savoir_faires/propose_softskills/propose_aptitudes
# (construction du contexte IA + fallback déterministe sans clé API).
import os
import pytest
from Code.routes.propose_common import (
    build_activity_context,
    dummy_from_context,
    openai_client_or_none,
)


class TestBuildActivityContext:
    def test_includes_title_and_description(self):
        ctx = build_activity_context({"title": "Usiner la pièce", "description": "Perçage et fraisage"})
        assert "Titre: Usiner la pièce" in ctx
        assert "Description: Perçage et fraisage" in ctx

    def test_falls_back_to_name_when_title_absent(self):
        ctx = build_activity_context({"name": "Contrôle qualité"})
        assert "Titre: Contrôle qualité" in ctx

    def test_lists_inputs_outputs_tools_constraints_tasks(self):
        ctx = build_activity_context({
            "title": "A",
            "input_data": ["Plan"],
            "output_data": ["Pièce finie"],
            "tools": ["Tour"],
            "constraints": ["Tolérance ±0.1mm"],
            "tasks": ["Régler la machine"],
        })
        assert "- Plan" in ctx
        assert "- Pièce finie" in ctx
        assert "- Tour" in ctx
        assert "- Tolérance ±0.1mm" in ctx
        assert "- Régler la machine" in ctx

    def test_outils_key_used_as_tools_fallback(self):
        ctx = build_activity_context({"title": "A", "outils": ["Fraiseuse"]})
        assert "- Fraiseuse" in ctx

    def test_empty_lists_render_as_dash(self):
        ctx = build_activity_context({"title": "A"})
        dash_lines = [line for line in ctx.splitlines() if line.strip() == "-"]
        # 5 sections listées (entrée/sortie/outils/contraintes/tâches), toutes vides ici
        assert len(dash_lines) == 5


class TestDummyFromContext:
    def test_savoir_uses_connaitre_prefix(self):
        items = dummy_from_context("Titre: Usiner la pièce", kind="savoir")
        assert len(items) == 3
        assert all(i.startswith("Connaître") for i in items)
        assert all("Usiner la pièce" in i for i in items)

    def test_savoir_faire_uses_appliquer_prefix(self):
        items = dummy_from_context("Titre: Usiner la pièce", kind="savoir_faire")
        assert all(i.startswith("Appliquer") for i in items)

    def test_hsc_uses_developper_prefix(self):
        items = dummy_from_context("Titre: Usiner la pièce", kind="hsc")
        assert all(i.startswith("Développer") for i in items)

    def test_unknown_kind_defaults_to_savoir_prefix(self):
        items = dummy_from_context("Titre: Usiner la pièce", kind="autre")
        assert all(i.startswith("Connaître") for i in items)

    def test_missing_title_line_omits_activity_mention(self):
        items = dummy_from_context("# Activité\nDescription: rien", kind="savoir")
        assert all("«" not in i for i in items)


class TestOpenaiClientOrNone:
    def test_missing_api_key_returns_none_with_reason(self, app, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with app.app_context():
            client, reason = openai_client_or_none()
        assert client is None
        assert "OPENAI_API_KEY" in reason

    def test_present_api_key_returns_client(self, app, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
        with app.app_context():
            client, reason = openai_client_or_none()
        assert client is not None
        assert reason is None
