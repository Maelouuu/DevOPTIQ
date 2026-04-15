# Code/routes/changelog.py
import subprocess
import os
import json
import time
from datetime import datetime

from flask import Blueprint, jsonify

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
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
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
                    'content': (
                        "Tu es le rédacteur des notes de version d'une application web professionnelle de gestion "
                        "de processus métier appelée OPTIQ.\n"
                        "Tu reçois des messages de commits git et tu dois les transformer en annonces concrètes "
                        "et positives pour des utilisateurs non-techniques.\n\n"
                        "RÈGLES :\n"
                        "- 3 à 5 points maximum, regroupés par thème\n"
                        "- Langue : français uniquement, ton positif et concret\n"
                        "- JAMAIS mentionner : ORM, SQL, CSS, hash, token, migration, backend, bug, refactoring\n"
                        "- Décris le bénéfice : 'vous pouvez désormais…', 'la page X affiche maintenant…'\n"
                        "- Chaque point : titre court (≤5 mots) + description (1-2 phrases)\n"
                        "- icon : une classe Font Awesome existante (ex: 'fa-solid fa-diagram-project')\n"
                        "  Choisis des icônes précises et pertinentes pour chaque fonctionnalité\n"
                        "- Réponds UNIQUEMENT en JSON strict (pas de markdown) :\n"
                        '  {"items": [{"icon":"fa-solid fa-...","title":"...","desc":"..."}, ...]}'
                    )
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


@changelog_bp.route('/api/recent-activity', methods=['GET'])
def get_recent_activity():
    """
    Retourne les derniers événements depuis recent_events.
    Si la table est vide (premier démarrage), fallback sur les derniers
    enregistrements de chaque modèle principal, triés par ID DESC.
    """
    try:
        from Code.models.models import RecentEvent, Activities, Task, Role, Tool
        from flask import session

        events = (RecentEvent.query
                  .order_by(RecentEvent.created_at.desc())
                  .limit(20)
                  .all())

        if events:
            items = []
            for ev in events:
                detail = None
                if ev.detail:
                    try:
                        import json as _j
                        detail = _j.loads(ev.detail)
                    except Exception:
                        pass
                items.append({
                    "icon": ev.icon,
                    "label": ev.label,
                    "type": ev.event_type,
                    "time": _format_relative_time(ev.created_at),
                    "detail": detail,
                })
            return jsonify({"ok": True, "items": items})

        # ── Fallback : table vide → on reconstruit depuis les modèles ──
        entity_id = session.get('active_entity_id')
        items = []

        _DEFS = [
            (Activities, 'fa-solid fa-diagram-project', 'Activité', 'entity_id'),
            (Role,       'fa-solid fa-user-tie',        'Rôle',     'entity_id'),
            (Tool,       'fa-solid fa-toolbox',         'Outil',    'entity_id'),
            (Task,       'fa-solid fa-list-check',      'Tâche',    None),
        ]
        for Model, icon, label_prefix, eid_col in _DEFS:
            q = Model.query
            if entity_id and eid_col:
                q = q.filter(getattr(Model, eid_col) == entity_id)
            rows = q.order_by(Model.id.desc()).limit(5).all()
            for row in rows:
                desc = getattr(row, 'description', None) or getattr(row, 'onboarding_plan', None) or ""
                items.append({
                    "icon": icon,
                    "label": f"{label_prefix} : {row.name}",
                    "type": "existing",
                    "time": "",
                    "detail": {"name": row.name, "description": desc},
                })

        # Garder les 15 premiers pour ne pas surcharger
        items = items[:15]
        return jsonify({"ok": True, "items": items})

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
