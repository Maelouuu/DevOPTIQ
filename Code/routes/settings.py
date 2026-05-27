# Code/routes/settings.py

from flask import Blueprint, render_template, session, request, jsonify
from Code.translations import TRANSLATIONS

settings_bp = Blueprint(
    'settings',
    __name__,
    url_prefix='/parametres',
    template_folder='templates',
)

_ALLOWED_LANGS = set(TRANSLATIONS.keys())


@settings_bp.route('/')
def settings_page():
    return render_template('settings.html')


@settings_bp.route('/set_language', methods=['POST'])
def set_language():
    data = request.get_json(silent=True) or {}
    lang = data.get('lang', 'fr')
    if lang not in _ALLOWED_LANGS:
        return jsonify({'ok': False, 'error': 'Langue non supportée'}), 400
    session['lang'] = lang
    return jsonify({'ok': True, 'lang': lang})
