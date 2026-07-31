# Code/ai_client.py — Client IA unifié de l'application.
#
# Toutes les fonctions IA de l'app parlent l'interface OpenAI
# `chat.completions` — on la conserve, mais le FOURNISSEUR est désormais
# interchangeable :
#   - « anthropic » : Claude, via le point d'accès compatible OpenAI
#     d'Anthropic (https://api.anthropic.com/v1/) — aucune dépendance
#     supplémentaire, même SDK, mêmes appels.
#   - « openai »    : comportement historique (gpt-4o-mini).
#
# Sélection du fournisseur (env AI_PROVIDER, défaut « auto ») :
#   auto      → Claude si une clé Anthropic est disponible, sinon OpenAI.
#               C'est l'interrupteur de migration : on valide la qualité
#               (tools/ai_eval/), on renseigne la clé Claude, c'est basculé —
#               et retirable tout aussi simplement.
#   anthropic → Claude obligatoire (erreur propre si pas de clé).
#   openai    → OpenAI obligatoire.
#
# Modèle : env AI_MODEL, sinon défaut du fournisseur ci-dessous.
# ⚠️ Ne plus jamais écrire model="gpt-4o-mini" en dur dans une route :
# utiliser ai_model() (ou le modèle renvoyé par make_ai_client()).

import os

from Code.ai_key import get_anthropic_key, get_openai_key

ANTHROPIC_OPENAI_BASE = "https://api.anthropic.com/v1/"

DEFAULT_MODELS = {
    # Même gamme coût/latence que gpt-4o-mini côté Claude.
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}

NO_KEY_MSG = "Clé IA non renseignée."


def resolve_provider():
    """Fournisseur effectif ('anthropic' | 'openai') et clé associée."""
    forced = (os.getenv("AI_PROVIDER") or "auto").strip().lower()
    if forced == "anthropic":
        return "anthropic", get_anthropic_key()
    if forced == "openai":
        return "openai", get_openai_key()
    # auto : Claude dès qu'une clé Anthropic existe, sinon OpenAI.
    akey = get_anthropic_key()
    if akey:
        return "anthropic", akey
    return "openai", get_openai_key()


def ai_model(provider=None):
    """Modèle effectif (env AI_MODEL prioritaire, sinon défaut du fournisseur)."""
    forced = (os.getenv("AI_MODEL") or "").strip()
    if forced:
        return forced
    if provider is None:
        provider, _ = resolve_provider()
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openai"])


def make_ai_client(timeout=None):
    """(client, model, err) — client SDK OpenAI pointé sur le bon fournisseur.

    err est un message utilisateur (français) si aucun client ne peut être
    construit ; dans ce cas client et model valent None. Les routes gardent
    leurs fallbacks existants (mêmes messages « Clé IA non renseignée »)."""
    provider, key = resolve_provider()
    if not key:
        return None, None, NO_KEY_MSG
    try:
        from openai import OpenAI
        kwargs = {"api_key": key}
        if provider == "anthropic":
            kwargs["base_url"] = ANTHROPIC_OPENAI_BASE
        if timeout is not None:
            kwargs["timeout"] = timeout
        return OpenAI(**kwargs), ai_model(provider), None
    except Exception as e:  # SDK absent, clé malformée…
        return None, None, str(e)
