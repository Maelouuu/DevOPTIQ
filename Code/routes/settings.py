# Code/routes/settings.py

import os
from functools import wraps

from flask import Blueprint, render_template, session, request, jsonify

from Code.translations import TRANSLATIONS
from Code.ai_key import get_openai_key, set_openai_key, mask_key

settings_bp = Blueprint(
    'settings',
    __name__,
    url_prefix='/parametres',
    template_folder='templates',
)

_ALLOWED_LANGS = set(TRANSLATIONS.keys())

# Les statuts 'admin' et 'administrateur' coexistent historiquement en base
_ADMIN_STATUSES = {"admin", "administrateur"}


def _is_admin():
    uid = session.get('user_id')
    if not uid:
        return False
    try:
        from Code.extensions import db
        from Code.models.models import User
        user = db.session.get(User, uid)
        return bool(user and (user.status or "").lower() in _ADMIN_STATUSES)
    except Exception:
        return False


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _is_admin():
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        return f(*args, **kwargs)
    return wrapper


def _masked_db_url():
    """URL de la base avec le mot de passe masqué."""
    url = os.getenv("DATABASE_URL") or ""
    if not url:
        return "(base SQLite locale)"
    import re
    return re.sub(r'(://[^:/@]+):[^@]*@', r'\1:••••••@', url)


@settings_bp.route('/')
def settings_page():
    return render_template('settings.html', is_admin=_is_admin())


@settings_bp.route('/set_language', methods=['POST'])
def set_language():
    data = request.get_json(silent=True) or {}
    lang = data.get('lang', 'fr')
    if lang not in _ALLOWED_LANGS:
        return jsonify({'ok': False, 'error': 'Langue non supportée'}), 400
    session['lang'] = lang
    return jsonify({'ok': True, 'lang': lang})


# ────────────────────────── Section admin ──────────────────────────

@settings_bp.route('/admin/overview')
@admin_required
def admin_overview():
    key = get_openai_key()
    return jsonify({
        'ok': True,
        'openai_key_set': bool(key),
        'openai_key_masked': mask_key(key),
        'db_url_masked': _masked_db_url(),
    })


@settings_bp.route('/admin/openai-key/reveal', methods=['POST'])
@admin_required
def admin_reveal_key():
    return jsonify({'ok': True, 'key': get_openai_key() or ""})


@settings_bp.route('/admin/openai-key', methods=['POST'])
@admin_required
def admin_save_key():
    data = request.get_json(silent=True) or {}
    key = (data.get('key') or "").strip()
    if key and not key.startswith("sk-"):
        return jsonify({'ok': False,
                        'error': "Format inattendu : une clé OpenAI commence par « sk- »."}), 400
    set_openai_key(key)
    effective = get_openai_key()
    return jsonify({'ok': True, 'openai_key_set': bool(effective),
                    'openai_key_masked': mask_key(effective)})


@settings_bp.route('/admin/logs')
@admin_required
def admin_logs():
    from Code.logstream import tail
    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    data, new_offset, size = tail(offset)
    return jsonify({'ok': True, 'data': data, 'offset': new_offset, 'size': size})
