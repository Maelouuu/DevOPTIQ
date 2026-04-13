# Code/routes/changelog.py
import subprocess
import os
import json
import time

from flask import Blueprint, jsonify

changelog_bp = Blueprint('changelog', __name__)

# Cache in-memory : { commit_hash: { 'ts': float, 'data': dict } }
_changelog_cache = {}

def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

def _fallback_changelog():
    return {"items": [
        {"icon": "✨", "title": "Nouvelles fonctionnalités", "desc": "Plusieurs améliorations ont été apportées à l'application pour simplifier votre quotidien."},
        {"icon": "🚀", "title": "Expérience améliorée", "desc": "La navigation et les interactions ont été optimisées pour une meilleure fluidité."},
        {"icon": "🔒", "title": "Fiabilité renforcée", "desc": "Corrections diverses pour garantir la stabilité et la sécurité de vos données."}
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
                        "Tu reçois des messages de commits git (techniques) et tu dois les transformer en annonces "
                        "de nouveautés positives et claires pour des utilisateurs non-techniques (responsables, managers, RH).\n\n"
                        "RÈGLES STRICTES :\n"
                        "- Regroupe les commits en 3 à 6 points maximum\n"
                        "- Langue : français uniquement\n"
                        "- Ton : positif, simple, orienté bénéfice utilisateur\n"
                        "- NE JAMAIS mentionner : ORM, SQL, CSS, hash, token, migration, backend, bug technique, "
                        "refactoring, fix spécificité, debug, console.log, etc.\n"
                        "- Reformule en avantages concrets : 'vous pouvez maintenant…', 'la page X affiche…', etc.\n"
                        "- Chaque point : un titre court (≤5 mots) + une description (1-2 phrases)\n"
                        "- Choisis un emoji pertinent par point\n"
                        "- Réponds UNIQUEMENT en JSON strict (pas de markdown) :\n"
                        '  {"items": [{"icon":"emoji","title":"...","desc":"..."}, ...]}'
                    )
                },
                {
                    'role': 'user',
                    'content': f"Commits récents :\n{commits_text}\n\nGénère le changelog utilisateur."
                }
            ],
            temperature=0.35,
            max_tokens=700
        )
        raw = response.choices[0].message.content.strip()
        # Nettoyer d'éventuels blocs markdown
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1]
            raw = raw.rsplit('```', 1)[0]
        return json.loads(raw)
    except Exception as e:
        print(f"[CHANGELOG] Erreur OpenAI : {e}")
        return None


@changelog_bp.route('/api/changelog', methods=['GET'])
def get_changelog():
    global _changelog_cache

    commit_hash = _get_latest_commit_hash()

    # Retourner le cache si valide (même commit, moins d'1 heure)
    cached = _changelog_cache.get(commit_hash)
    if cached and time.time() - cached['ts'] < 3600:
        return jsonify({'ok': True, **cached['data']})

    commits = _get_recent_commits(30)
    if not commits:
        data = _fallback_changelog()
    else:
        data = _generate_with_openai(commits) or _fallback_changelog()

    _changelog_cache = {commit_hash: {'ts': time.time(), 'data': data}}
    return jsonify({'ok': True, **data})
