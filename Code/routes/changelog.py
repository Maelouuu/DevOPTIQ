# Code/routes/changelog.py
import subprocess
import os
import json
import time
from datetime import datetime

from flask import Blueprint, jsonify
from Code.ai_key import get_openai_key
from Code.prompts import get_prompt

changelog_bp = Blueprint('changelog', __name__)

_changelog_cache = {}

def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _curated_file():
    return os.path.join(_repo_root(), 'static', 'changelog_user.json')

def _get_latest_commit_hash():
    try:
        r = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=5,
            cwd=_repo_root()
        )
        return r.stdout.strip() if r.returncode == 0 else 'unknown'
    except Exception:
        return 'unknown'

def _get_recent_commits(n=30):
    try:
        r = subprocess.run(
            ['git', 'log', '--no-merges', f'-{n}', '--format=%s'],
            capture_output=True, text=True, timeout=10,
            cwd=_repo_root()
        )
        if r.returncode != 0:
            return []
        return [line.strip() for line in r.stdout.strip().split('\n') if line.strip()]
    except Exception:
        return []

def _read_curated():
    """Lit changelog_user.json s'il existe. Retourne None sinon."""
    path = _curated_file()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            items = json.load(f)
        if isinstance(items, list) and items:
            return {"items": items}
    except Exception:
        pass
    return None

def _fallback_changelog():
    return {"items": [
        {"icon": "fa-solid fa-sparkles", "title": "Nouvelles fonctionnalités", "desc": "Plusieurs améliorations ont été apportées pour simplifier votre quotidien."},
        {"icon": "fa-solid fa-rocket", "title": "Expérience améliorée", "desc": "La navigation et les interactions ont été optimisées pour une meilleure fluidité."},
        {"icon": "fa-solid fa-shield-halved", "title": "Fiabilité renforcée", "desc": "Corrections diverses pour garantir la stabilité et la sécurité de vos données."}
    ]}

def _generate_with_openai(commits):
    api_key = get_openai_key()
    system_prompt = get_prompt("changelog.system")
    if not api_key or system_prompt is None:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        commits_text = '\n'.join(f'- {c}' for c in commits)
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_CHATBOT_MODEL', 'gpt-4o-mini'),
            messages=[
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': f"Commits récents :\n{commits_text}\n\nGénère le changelog utilisateur."
                }
            ],
            temperature=0.3,
            max_tokens=700
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0]
        return json.loads(raw)
    except Exception as e:
        print(f"[CHANGELOG] Erreur OpenAI : {e}")
        return None


def _format_relative_time(dt):
    """Retourne une chaîne de type 'il y a 2h' à partir d'un datetime UTC."""
    if not dt:
        return ""
    diff = datetime.utcnow() - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return "à l'instant"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"il y a {minutes} min"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"il y a {hours}h"
    else:
        days = int(seconds / 86400)
        return f"il y a {days}j"


_EVENT_LABELS = {
    'activity_created': 'Ajout',
    'activity_updated': 'Modification',
    'activity_deleted': 'Suppression',
    'task_created':     'Ajout',
    'task_updated':     'Modification',
    'task_deleted':     'Suppression',
    'role_created':     'Ajout',
    'role_updated':     'Modification',
    'role_deleted':     'Suppression',
    'tool_created':     'Ajout',
    'tool_updated':     'Modification',
    'tool_deleted':     'Suppression',
    'tool_linked':      'Association',
}

_EVENT_COLORS = {
    'created': 'green',
    'updated': 'orange',
    'deleted': 'red',
    'linked':  'blue',
}


def _event_color(event_type):
    for suffix, color in _EVENT_COLORS.items():
        if event_type.endswith(suffix):
            return color
    return 'gray'


def _format_date(dt):
    if not dt:
        return ""
    months = ['jan.', 'fév.', 'mars', 'avr.', 'mai', 'juin',
              'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
    return f"{dt.day} {months[dt.month - 1]} à {dt.strftime('%H:%M')}"


@changelog_bp.route('/api/recent-activity', methods=['GET'])
def get_recent_activity():
    """Retourne les 20 derniers événements depuis recent_events."""
    try:
        import json as _j
        from Code.models.models import RecentEvent, User

        events = (RecentEvent.query
                  .order_by(RecentEvent.created_at.desc())
                  .limit(20)
                  .all())

        # Cache user names
        user_cache = {}
        for ev in events:
            if ev.user_id and ev.user_id not in user_cache:
                u = User.query.get(ev.user_id)
                user_cache[ev.user_id] = (f"{u.first_name} {u.last_name}" if u else None)

        items = []
        for ev in events:
            detail = None
            if ev.detail:
                try:
                    detail = _j.loads(ev.detail)
                except Exception:
                    pass
            items.append({
                "icon":        ev.icon,
                "label":       ev.label,
                "type":        ev.event_type,
                "event_label": _EVENT_LABELS.get(ev.event_type, 'Événement'),
                "color":       _event_color(ev.event_type),
                "time":        _format_relative_time(ev.created_at),
                "date":        _format_date(ev.created_at),
                "user":        user_cache.get(ev.user_id),
                "detail":      detail,
            })

        return jsonify({"ok": True, "items": items, "empty": len(items) == 0})

    except Exception as e:
        return jsonify({"ok": False, "items": [], "error": str(e)})


@changelog_bp.route('/api/changelog', methods=['GET'])
def get_changelog():
    global _changelog_cache

    # 1. Lire le fichier curated en priorité absolue
    curated = _read_curated()
    if curated:
        return jsonify({'ok': True, **curated})

    # 2. Sinon : génération via OpenAI + cache
    commit_hash = _get_latest_commit_hash()
    cached = _changelog_cache.get(commit_hash)
    if cached and time.time() - cached['ts'] < 3600:
        return jsonify({'ok': True, **cached['data']})

    commits = _get_recent_commits(30)
    data = (_generate_with_openai(commits) if commits else None) or _fallback_changelog()

    _changelog_cache = {commit_hash: {'ts': time.time(), 'data': data}}
    return jsonify({'ok': True, **data})
