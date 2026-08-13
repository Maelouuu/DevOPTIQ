# Télémétrie OptiqPulse — instrumentation passive de l'app.
# Rien n'est affiché ici : les tables usage_events / usage_beats sont lues par
# le service externe OptiqPulse (pulse/), qui se branche en lecture sur la base
# Neon de chaque instance. Toute erreur d'écriture est avalée : la télémétrie
# ne doit JAMAIS casser ou ralentir une réponse au point d'être visible.

import os
import time
import uuid
from datetime import datetime

from flask import Blueprint, current_app, g, request, session

from Code.extensions import db
from Code.models.models import UsageBeat, UsageEvent

pulse_bp = Blueprint('pulse', __name__, url_prefix='/pulse')

# Chemins « bruit » jamais journalisés : télémétrie elle-même, statiques,
# santé, polling de la console serveur (2 s).
_SKIP_PREFIXES = ('/pulse/', '/static/', '/favicon', '/healthz',
                  '/parametres/admin/logs')


def _enabled():
    if current_app.config.get('PULSE_FORCE'):
        return True
    if current_app.testing:
        return False
    return os.getenv('PULSE_DISABLED', '0') != '1'


def _session_key():
    # Clé de session de télémétrie : posée au premier passage d'un utilisateur
    # connecté, indépendante de l'id utilisateur (distingue deux navigateurs).
    key = session.get('pulse_sid')
    if not key and 'user_id' in session:
        key = uuid.uuid4().hex
        session['pulse_sid'] = key
    return key


def _write(table, values):
    # Connexion Core dédiée : on ne touche pas à la session ORM de la requête
    # (pas de commit d'état étranger, pas d'autoflush parasite).
    try:
        with db.engine.begin() as conn:
            conn.execute(table.insert(), [values])
        return True
    except Exception:
        return False


def init_tracking(app):
    """Branche la journalisation sur toutes les requêtes de l'app."""

    @app.before_request
    def _pulse_start():
        g._pulse_t0 = time.perf_counter()

    @app.after_request
    def _pulse_log(response):
        try:
            if not _enabled():
                return response
            path = request.path or '/'
            if path.startswith(_SKIP_PREFIXES):
                return response
            user_id = session.get('user_id')
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                kind = 'action'
            elif (request.method == 'GET' and response.status_code < 400
                  and 'text/html' in (response.content_type or '')):
                kind = 'view'
            else:
                return response
            # Le login (pas encore de session) est journalisé sans user_id :
            # Pulse y lit les tentatives de connexion.
            duration_ms = None
            t0 = getattr(g, '_pulse_t0', None)
            if t0 is not None:
                duration_ms = int((time.perf_counter() - t0) * 1000)
            _write(UsageEvent.__table__, {
                'ts': datetime.utcnow(),
                'user_id': user_id,
                'session_key': _session_key(),
                'kind': kind,
                'method': request.method[:8],
                'path': path[:300],
                'endpoint': (request.endpoint or '')[:120] or None,
                'status': response.status_code,
                'duration_ms': duration_ms,
            })
        except Exception:
            pass
        return response


@pulse_bp.route('/beat', methods=['POST'])
def beat():
    """Battement de présence envoyé par static/js/pulse.js (~60 s, onglet
    visible). 204 systématique : jamais d'erreur côté client."""
    try:
        if _enabled() and 'user_id' in session:
            data = request.get_json(silent=True) or {}
            _write(UsageBeat.__table__, {
                'ts': datetime.utcnow(),
                'user_id': session['user_id'],
                'session_key': _session_key(),
                'path': (data.get('path') or '')[:300] or None,
            })
    except Exception:
        pass
    return ('', 204)
