# Code/prompts/__init__.py — Accès centralisé aux prompts IA OptiqFluent.
#
# Les textes des prompts (une partie du savoir-faire AFDEC) ne vivent plus dans
# le code des routes. Résolution, dans l'ordre :
#   1. Dépôt source / dev : Code/prompts/catalog.py (dict PROMPTS, en clair).
#   2. Image client : catalog.py est EXCLU du build (.dockerignore) ; seul le
#      bundle chiffré Code/prompts/prompts.enc est embarqué. La clé Fernet
#      arrive par la variable d'env PROMPTS_KEY ou par la licence signée
#      (champ prompts_key du payload).
#   3. Ni catalogue, ni bundle déchiffrable → get_prompt() rend None : chaque
#      route dégrade alors comme si aucune clé IA n'était configurée.
#
# Interpolation : placeholders [[nom]] remplacés par get_prompt(key, nom=...).
# (PAS str.format : les prompts contiennent des accolades JSON.)

import os
import threading

_ENC_PATH = os.path.join(os.path.dirname(__file__), "prompts.enc")

_lock = threading.Lock()
_store = None  # None = pas encore chargé ; dict (peut être vide) ensuite


def _license_prompts_key():
    try:
        from flask import current_app
        state = current_app.config.get("LICENSE_STATE") or {}
        info = state.get("info") or {}
        return info.get("prompts_key")
    except Exception:
        return None


def _try_load():
    """Charge le catalogue clair, sinon le bundle chiffré. Rend un dict ou None."""
    try:
        from Code.prompts.catalog import PROMPTS
        return dict(PROMPTS)
    except ImportError:
        pass

    if not os.path.isfile(_ENC_PATH):
        print("[PROMPTS] Ni catalogue ni bundle chiffré — fonctions IA dégradées")
        return None
    key = os.getenv("PROMPTS_KEY") or _license_prompts_key()
    if not key:
        print("[PROMPTS] Bundle chiffré présent mais aucune clé "
              "(PROMPTS_KEY ou licence) — fonctions IA dégradées")
        return None
    try:
        import json
        from cryptography.fernet import Fernet
        with open(_ENC_PATH, "rb") as f:
            data = Fernet(key.encode()).decrypt(f.read())
        store = json.loads(data)
        print(f"[PROMPTS] Bundle chiffré chargé ({len(store)} prompts)")
        return store
    except Exception as e:
        print(f"[PROMPTS] Déchiffrement du bundle impossible : {e}")
        return None


def prompts_available():
    return _get_store() is not None


def _get_store():
    global _store
    if _store is not None:
        return _store or None
    with _lock:
        if _store is None:
            loaded = _try_load()
            if loaded is None:
                # Échec non mémorisé : on retente au prochain appel — une clé
                # peut apparaître après coup (licence renouvelée à chaud).
                return None
            _store = loaded
    return _store or None


def get_prompt(key, **variables):
    """Rend le prompt `key` avec ses [[placeholders]] remplacés, ou None."""
    store = _get_store()
    if store is None:
        return None
    template = store.get(key)
    if template is None:
        print(f"[PROMPTS] Prompt manquant : {key}")
        return None
    for name, value in variables.items():
        template = template.replace(f"[[{name}]]", str(value))
    return template
