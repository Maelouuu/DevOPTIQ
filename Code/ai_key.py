# Code/ai_key.py — Clé OpenAI effective de l'instance.
#
# Priorité : réglage en base (app_settings.openai_api_key, modifiable à chaud
# depuis Paramètres → section admin) puis variable d'environnement
# OPENAI_API_KEY (Cloud Run, .env, assistant d'installation).
# ⚠️ Ne plus jamais lire os.getenv("OPENAI_API_KEY") directement dans une
# route : toujours passer par get_openai_key().

import os

_SETTING_KEY = "openai_api_key"


def get_openai_key():
    try:
        from Code.extensions import db
        from Code.models.models import AppSetting
        row = db.session.get(AppSetting, _SETTING_KEY)
        if row and (row.value or "").strip():
            return row.value.strip()
    except Exception:
        pass  # hors contexte app / table absente → repli env
    return (os.getenv("OPENAI_API_KEY") or "").strip() or None


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
