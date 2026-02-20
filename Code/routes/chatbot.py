# Code/routes/chatbot.py
# Blueprint Flask — Assistant OPTIQ Chatbot (saisie de tâches)

import os
import uuid
import json
from flask import Blueprint, request, jsonify
from openai import OpenAI

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

# ---------------------------------------------------------------------------
# Sessions en mémoire (session_id -> {history, activity})
# ---------------------------------------------------------------------------
_SESSIONS: dict = {}

# ---------------------------------------------------------------------------
# Prompt système OPTIQ
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
Tu es "Assistant OPTIQ — Saisie de tâches".
Tu es un intervieweur rigoureux, bienveillant et orienté livrables.
Ton but : aider l'utilisateur à décrire les TÂCHES d'une activité OPTIQ
de façon claire et exploitable dans une application.

=== DÉFINITIONS OPTIQ ===
- Activité : ensemble cohérent d'actions produisant 1 à 3 résultats / valeurs ajoutées.
- Tâche : "QUE fait-on ?" — action observable, résultat intermédiaire.
  Interdit : mode opératoire (clics, menus, micro-étapes, "puis/ensuite…").
- Outil : logiciel, formulaire, gabarit, machine, document de référence.

=== RÈGLES STRICTES ===
1) PAS de mode opératoire. Si l'utilisateur dit "je clique sur…" ou "j'ouvre le menu…"
   → reformuler au niveau tâche ("Saisir la demande dans SAP").
2) 5 à 8 tâches MAXIMUM (3-4 si activité simple).
   Si trop → regrouper et faire choisir les essentielles.
3) Une tâche = UN seul verbe d'action principal.
   "analyser ET négocier" → proposer 2 tâches séparées.
4) Chaque tâche contribue à un résultat de l'activité. Sinon → hors-scope.
5) Chaînage : vérifier la cohérence entrée → tâche → sortie / amont / aval.
6) "Ça dépend" → déclencher protocole :
   a) "Ça dépend de quoi ? (entrée / traitement / résultat / niveau d'exigence)"
   b) Définir une condition de bascule + tronc commun + max 2 branches (≤3 tâches chacune).
   c) Si le résultat final change → recommander une autre activité.

=== DIALOGUE ===
- 1 à 3 questions courtes max par tour.
- Séquence : Challenge → Reformulation OPTIQ → "Tu confirmes ?"
- Mettre à jour les tâches proposées à chaque tour.

=== FORMAT DE RÉPONSE ===
Tu DOIS répondre UNIQUEMENT en JSON valide, rien d'autre en dehors du JSON.
Schéma obligatoire :
{
  "assistant_message": "message conversationnel en français (markdown autorisé)",
  "status": "need_more_info" | "ready_for_validation" | "validated",
  "tasks": [
    {
      "label": "Verbe d'action + objet (court, niveau tâche)",
      "tools": ["outil1"],
      "flags": {
        "too_detailed": false,
        "contains_how": false,
        "contains_two_tasks": false,
        "out_of_scope": false
      },
      "rewrite_suggestion": "suggestion si problème, sinon chaîne vide"
    }
  ],
  "quality_checks": [
    { "issue": "description du problème", "severity": "info|warning|blocker", "fix": "action corrective" }
  ],
  "next_questions": ["question courte"],
  "branches": [
    { "condition": "Si…", "impact": "impact sur les tâches", "task_variants": ["tâche variante"] }
  ]
}
"""


def _build_context(activity: dict) -> str:
    def fmt(lst):
        if not lst:
            return "    - (non renseigné)"
        return "\n".join(f"    - {x}" for x in lst)

    return (
        f"CONTEXTE ACTIVITÉ (OPTIQ)\n"
        f"- Nom : {activity.get('name', '(non renseigné)')}\n"
        f"- Description / finalité : {activity.get('description', '(non renseigné)')}\n"
        f"- Données entrantes (amont) :\n{fmt(activity.get('inputs'))}\n"
        f"- Données sortantes (aval) :\n{fmt(activity.get('outputs'))}\n"
        f"- Tâches déjà saisies :\n{fmt(activity.get('existing_tasks'))}"
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@chatbot_bp.post('/session/new')
def new_session():
    sid = str(uuid.uuid4())
    _SESSIONS[sid] = {'history': [], 'activity': {}}
    return jsonify({'session_id': sid})


@chatbot_bp.post('/session/context')
def set_context():
    data = request.get_json(force=True) or {}
    sid = data.get('session_id')
    if not sid or sid not in _SESSIONS:
        return jsonify({'error': 'Session inconnue'}), 404
    _SESSIONS[sid]['activity'] = data.get('activity', {})
    return jsonify({'ok': True})


@chatbot_bp.post('/chat')
def chat():
    data = request.get_json(force=True) or {}
    sid = data.get('session_id')
    message = (data.get('message') or '').strip()

    if not sid or sid not in _SESSIONS:
        return jsonify({'error': 'Session inconnue. Merci de relancer l\'assistant.'}), 404
    if not message:
        return jsonify({'error': 'Message vide'}), 400

    sess = _SESSIONS[sid]
    context_block = _build_context(sess.get('activity', {}))

    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'system', 'content': context_block},
        *sess['history'][-14:],
        {'role': 'user', 'content': message},
    ]

    try:
        client = OpenAI()
        model = os.getenv('OPENAI_CHATBOT_MODEL', 'gpt-4o-mini')
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={'type': 'json_object'},
            temperature=0.2,
            max_tokens=1400,
        )
        raw = resp.choices[0].message.content
        result = json.loads(raw)
    except Exception as e:
        return jsonify({'error': f'Erreur API OpenAI : {str(e)}'}), 500

    # Mettre à jour l'historique
    sess['history'].append({'role': 'user', 'content': message})
    sess['history'].append({'role': 'assistant', 'content': result.get('assistant_message', '')})

    return jsonify(result)
