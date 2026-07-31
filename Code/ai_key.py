# Code/ai_key.py — Clés IA effectives de l'instance (OpenAI et Anthropic/Claude).
#
# Priorité pour chaque clé : réglage en base (app_settings, modifiable à chaud
# depuis Paramètres → section admin) puis variable d'environnement
# (Cloud Run, .env, assistant d'installation).
# ⚠️ Ne plus jamais lire os.getenv("OPENAI_API_KEY"/"ANTHROPIC_API_KEY")
# directement dans une route : toujours passer par ces helpers — et pour
# obtenir un client, passer par Code.ai_client.make_ai_client().

import os

_SETTING_KEY = "openai_api_key"
_SETTING_KEY_ANTHROPIC = "anthropic_api_key"


def _setting(key):
    try:
        from Code.extensions import db
        from Code.models.models import AppSetting
        row = db.session.get(AppSetting, key)
        if row and (row.value or "").strip():
            return row.value.strip()
    except Exception:
        pass  # hors contexte app / table absente → repli env
    return None


def get_openai_key():
    return _setting(_SETTING_KEY) or (os.getenv("OPENAI_API_KEY") or "").strip() or None


def get_anthropic_key():
    return (_setting(_SETTING_KEY_ANTHROPIC)
            or (os.getenv("ANTHROPIC_API_KEY") or "").strip()
            or (os.getenv("ANTHROPIC_KEY") or "").strip()
            or None)


def set_openai_key(value):
    """Enregistre la clé en base (chaîne vide → suppression, retour au repli env)."""
    from Code.extensions import db
    from Code.models.models import AppSetting
    value = (value or "").strip()
    row = db.session.get(AppSetting, _SETTING_KEY)
    if not value:
        if row:
            db.session.delete(row)
    elif row:
        row.value = value
    else:
        db.session.add(AppSetting(key=_SETTING_KEY, value=value))
    db.session.commit()


def mask_key(key):
    if not key:
        return None
    if len(key) <= 12:
        return key[:2] + "•" * 8
    return key[:7] + "•" * 12 + key[-4:]
