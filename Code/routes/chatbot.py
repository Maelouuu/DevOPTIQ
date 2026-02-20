# Code/routes/chatbot.py
# Blueprint Flask — Assistant OPTIQ Chatbot (saisie de tâches)

import os
import uuid
import json
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from openai import OpenAI

from Code.extensions import db
from Code.models.models import (
    Activities, Task, Link, Data, Performance,
    Constraint, Savoir, SavoirFaire, Aptitude,
    Softskill, Competency,
)

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
   Utilise les connexions entrantes/sortantes fournies pour vérifier.
6) "Ça dépend" → déclencher protocole :
   a) "Ça dépend de quoi ? (entrée / traitement / résultat / niveau d'exigence)"
   b) Définir une condition de bascule + tronc commun + max 2 branches (≤3 tâches chacune).
   c) Si le résultat final change → recommander une autre activité.
7) IMPORTANT : utilise le CONTEXTE COMPLET fourni (savoirs, savoir-faire, HSC, aptitudes,
   contraintes, compétences, connexions) pour :
   - Valider la cohérence des tâches proposées
   - Challenger intelligemment ("tu mentionnes X savoir-faire, quelle tâche le mobilise ?")
   - Détecter des oublis ("les contraintes indiquent Y, est-ce couvert par tes tâches ?")

=== DIALOGUE ===
- 1 à 3 questions courtes max par tour.
- Séquence : Challenge → Reformulation OPTIQ → "Tu confirmes ?"
- Mettre à jour les tâches proposées à chaque tour.
- Exploite intelligemment le contexte : si des savoirs/HSC/contraintes sont définis,
  assure-toi que les tâches les couvrent (sans inventer ce qui n'est pas fourni).

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


# ---------------------------------------------------------------------------
# Construction du contexte riche pour le prompt
# ---------------------------------------------------------------------------
def _build_context(activity: dict) -> str:
    def fmt_list(lst, empty="(non renseigné)"):
        if not lst:
            return f"    - {empty}"
        return "\n".join(f"    - {x}" for x in lst)

    def fmt_conn(lst):
        if not lst:
            return "    - (aucune)"
        return "\n".join(
            f"    - [{c.get('type', '?')}] {c.get('data_name', '?')} "
            f"(depuis : {c.get('source_name', '?')})"
            for c in lst
        )

    def fmt_conn_out(lst):
        if not lst:
            return "    - (aucune)"
        return "\n".join(
            f"    - {c.get('data_name', '?')} → {c.get('target_name', '?')}"
            + (f" [perf : {c['performance']['name']}]" if c.get('performance') else "")
            for c in lst
        )

    def fmt_tasks(lst):
        if not lst:
            return "    - (aucune tâche saisie)"
        lines = []
        for t in lst:
            tools = ", ".join(t.get("tools", [])) if t.get("tools") else "—"
            lines.append(f"    - {t['name']} (outils : {tools})")
        return "\n".join(lines)

    def fmt_hsc(lst):
        if not lst:
            return "    - (aucune)"
        return "\n".join(
            f"    - {h.get('habilete', '?')} [niv. {h.get('niveau', '?')}]"
            + (f" — {h['justification']}" if h.get('justification') else "")
            for h in lst
        )

    sections = [
        "=== CONTEXTE COMPLET DE L'ACTIVITÉ (OPTIQ) ===",
        f"Nom : {activity.get('name', '(non renseigné)')}",
        f"Description / finalité : {activity.get('description') or '(non renseignée)'}",
        "",
        "── TÂCHES DÉJÀ SAISIES ──",
        fmt_tasks(activity.get("tasks", [])),
        "",
        "── CONNEXIONS ENTRANTES (données / activités en amont) ──",
        fmt_conn(activity.get("incoming", [])),
        "",
        "── CONNEXIONS SORTANTES (données / activités en aval) ──",
        fmt_conn_out(activity.get("outgoing", [])),
        "",
        "── CONTRAINTES (règles non négociables) ──",
        fmt_list(activity.get("contraintes")),
        "",
        "── COMPÉTENCES REQUISES ──",
        fmt_list(activity.get("competences")),
        "",
        "── SAVOIRS (connaissances théoriques) ──",
        fmt_list(activity.get("savoirs")),
        "",
        "── SAVOIR-FAIRE (compétences pratiques) ──",
        fmt_list(activity.get("savoir_faires")),
        "",
        "── HSC — HABILETÉS SOCIO-COGNITIVES ──",
        fmt_hsc(activity.get("hsc", [])),
        "",
        "── APTITUDES ──",
        fmt_list(activity.get("aptitudes")),
    ]

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Endpoint : récupérer le contexte complet d'une activité depuis la DB
# ---------------------------------------------------------------------------
@chatbot_bp.get('/activity/<int:activity_id>/context')
def get_activity_context(activity_id):
    """
    Récupère toutes les données disponibles pour une activité :
    tâches, connexions, savoirs, SF, HSC, aptitudes, contraintes, compétences.
    """
    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({'error': 'Activité introuvable'}), 404

    # Tâches avec leurs outils
    tasks_data = []
    for task in sorted(activity.tasks, key=lambda t: (t.order is None, t.order)):
        tasks_data.append({
            'name': task.name,
            'tools': [tool.name for tool in task.tools],
        })

    # Connexions entrantes
    incoming_links = db.session.query(Link).filter(
        or_(
            Link.target_activity_id == activity_id,
            Link.target_data_id == activity_id,
        )
    ).all()

    incoming_list = []
    for link in incoming_links:
        data_name = _resolve_data_name(link)
        source_name = _resolve_source_name(link)
        d_type = _resolve_data_type(link)
        incoming_list.append({
            'type': d_type,
            'data_name': data_name,
            'source_name': source_name,
        })

    # Connexions sortantes
    outgoing_links = db.session.query(Link).filter(
        or_(
            Link.source_activity_id == activity_id,
            Link.source_data_id == activity_id,
        )
    ).all()

    outgoing_list = []
    for link in outgoing_links:
        data_name = _resolve_data_name(link, outgoing=True)
        target_name = _resolve_target_name(link)
        d_type = _resolve_data_type(link, outgoing=True)
        perf = link.performance
        outgoing_list.append({
            'type': d_type,
            'data_name': data_name,
            'target_name': target_name,
            'performance': {'name': perf.name} if perf else None,
        })

    context = {
        'name': activity.name,
        'description': activity.description or '',
        'tasks': tasks_data,
        'incoming': incoming_list,
        'outgoing': outgoing_list,
        'contraintes': [c.description for c in activity.constraints],
        'competences': [c.description for c in activity.competencies],
        'savoirs': [s.description for s in activity.savoirs],
        'savoir_faires': [sf.description for sf in activity.savoir_faires],
        'hsc': [
            {
                'habilete': sk.habilete,
                'niveau': sk.niveau,
                'justification': sk.justification or '',
            }
            for sk in activity.softskills
        ],
        'aptitudes': [a.description for a in activity.aptitudes],
    }

    return jsonify(context)


# ---------------------------------------------------------------------------
# Endpoints session / chat
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
        return jsonify({'error': "Session inconnue. Merci de relancer l'assistant."}), 404
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

    sess['history'].append({'role': 'user', 'content': message})
    sess['history'].append({'role': 'assistant', 'content': result.get('assistant_message', '')})

    return jsonify(result)


# ---------------------------------------------------------------------------
# Fonctions utilitaires (résolution noms depuis les Links)
# ---------------------------------------------------------------------------

def _resolve_data_name(link, outgoing=False):
    data_id = link.target_data_id if outgoing else link.source_data_id
    if data_id:
        d = Data.query.get(data_id)
        if d:
            return d.name
    return link.description or '[Data inconnue]'


def _resolve_source_name(link):
    if link.source_activity_id:
        act = Activities.query.get(link.source_activity_id)
        return act.name if act else '[Activité inconnue]'
    if link.source_data_id:
        d = Data.query.get(link.source_data_id)
        return d.name if d else '[Data inconnue]'
    return '[Source ?]'


def _resolve_target_name(link):
    if link.target_activity_id:
        act = Activities.query.get(link.target_activity_id)
        return act.name if act else '[Activité inconnue]'
    if link.target_data_id:
        d = Data.query.get(link.target_data_id)
        return d.name if d else '[Data inconnue]'
    return '[Cible ?]'


def _resolve_data_type(link, outgoing=False):
    data_id = link.target_data_id if outgoing else link.source_data_id
    if data_id:
        d = Data.query.get(data_id)
        if d and d.type:
            return d.type
    return link.type or '[type ?]'
