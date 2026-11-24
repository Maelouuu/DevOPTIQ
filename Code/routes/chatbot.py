# Code/routes/chatbot.py
# Blueprint Flask — Assistant OPTIQ Chatbot (saisie de tâches)

import os
import json
from flask import Blueprint, request, jsonify, session
from Code.prompts import get_prompt, prompts_available
from Code.ai_key import get_openai_key
from sqlalchemy import or_
from openai import OpenAI

from Code.extensions import db
from Code.models.models import (
    Activities, Task, Link, Data, Tool, Entity, Performance,
    Constraint, Savoir, SavoirFaire, Aptitude,
    Softskill, Competency,
)

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

# ---------------------------------------------------------------------------
# Prompts système OPTIQ — FR et EN
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Prompts additionnels — spécifiques au mode de conversation
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# Construction du contexte riche pour le prompt
# ---------------------------------------------------------------------------
# ⚠️ Les intitulés du bloc de contexte suivent la LANGUE. Le correctif du
# 23/11 avait retiré l'amorce française écrite dans le navigateur ; ce bloc-ci
# restait, et il est renvoyé à chaque tour de la conversation.
# ⚠️ Des NOMS, pas des indices : la liste `sections` vit trente lignes plus bas,
# et un tableau positionnel se décalerait en silence dès qu'on insère une
# section — le modèle recevrait des intitulés faux sans que rien ne le dise.
ETIQ = {
    "fr": {
        "tete": "=== CONTEXTE COMPLET DE L'ACTIVITÉ (OPTIQ) ===",
        "nom": "Nom", "desc": "Description / finalité",
        "taches": "── TÂCHES DÉJÀ SAISIES ──",
        "entrantes": "── CONNEXIONS ENTRANTES (données / activités en amont) ──",
        "sortantes": "── CONNEXIONS SORTANTES (données / activités en aval) ──",
        "contraintes": "── CONTRAINTES (règles non négociables) ──",
        "competences": "── COMPÉTENCES REQUISES ──",
        "savoirs": "── SAVOIRS (connaissances théoriques) ──",
        "savoir_faire": "── SAVOIR-FAIRE (compétences pratiques) ──",
        "hsc": "── HSC — HABILETÉS SOCIO-COGNITIVES ──",
        "aptitudes": "── APTITUDES ──",
        "outils": "── OUTILS DISPONIBLES DANS LE RÉFÉRENTIEL (utilise ces noms exacts) ──",
    },
    "en": {
        "tete": "=== FULL ACTIVITY CONTEXT (OPTIQ) ===",
        "nom": "Name", "desc": "Description / purpose",
        "taches": "── TASKS ALREADY ENTERED ──",
        "entrantes": "── INCOMING CONNECTIONS (upstream data / activities) ──",
        "sortantes": "── OUTGOING CONNECTIONS (downstream data / activities) ──",
        "contraintes": "── CONSTRAINTS (non-negotiable rules) ──",
        "competences": "── REQUIRED COMPETENCIES ──",
        "savoirs": "── KNOWLEDGE (theory) ──",
        "savoir_faire": "── PRACTICAL SKILLS ──",
        "hsc": "── SCA — SOCIO-COGNITIVE ABILITIES ──",
        "aptitudes": "── PHYSICAL ABILITIES ──",
        "outils": "── TOOLS AVAILABLE IN THE CATALOGUE (use these exact names) ──",
    },
}
VIDE = {
    "fr": {"rien": "(non renseigné)", "rien_e": "(non renseignée)", "aucune": "(aucune)",
           "aucune_tache": "(aucune tâche saisie)", "aucun_outil": "(aucun outil dans le référentiel)",
           "outils": "outils", "niv": "niv.", "depuis": "depuis", "perf": "perf"},
    "en": {"rien": "(not provided)", "rien_e": "(not provided)", "aucune": "(none)",
           "aucune_tache": "(no task entered yet)", "aucun_outil": "(no tool in the catalogue)",
           "outils": "tools", "niv": "level", "depuis": "from", "perf": "perf"},
}


def _build_context(activity: dict, lang: str = "fr") -> str:
    lang = "en" if lang == "en" else "fr"
    E = ETIQ[lang]
    V = VIDE[lang]

    def fmt_list(lst, empty=None):
        empty = empty if empty is not None else V["rien"]
        if not lst:
            return f"    - {empty}"
        return "\n".join(f"    - {x}" for x in lst)

    def fmt_conn(lst):
        if not lst:
            return f"    - {V['aucune']}"
        return "\n".join(
            f"    - [{c.get('type', '?')}] {c.get('data_name', '?')} "
            f"({V['depuis']} : {c.get('source_name', '?')})"
            for c in lst
        )

    def fmt_conn_out(lst):
        if not lst:
            return f"    - {V['aucune']}"
        return "\n".join(
            f"    - {c.get('data_name', '?')} → {c.get('target_name', '?')}"
            + (f" [{V['perf']} : {c['performance']['name']}]" if c.get('performance') else "")
            for c in lst
        )

    def fmt_tasks(lst):
        if not lst:
            return f"    - {V['aucune_tache']}"
        lines = []
        for t in lst:
            tools = ", ".join(t.get("tools", [])) if t.get("tools") else "—"
            lines.append(f"    - {t['name']} ({V['outils']} : {tools})")
        return "\n".join(lines)

    def fmt_hsc(lst):
        if not lst:
            return f"    - {V['aucune']}"
        return "\n".join(
            f"    - {h.get('habilete', '?')} [{V['niv']} {h.get('niveau', '?')}]"
            + (f" — {h['justification']}" if h.get('justification') else "")
            for h in lst
        )

    def fmt_tools(lst):
        if not lst:
            return f"    - {V['aucun_outil']}"
        return "\n".join(f"    - {t}" for t in lst)

    sections = [
        E["tete"],
        f"{E['nom']} : {activity.get('name') or V['rien']}",
        f"{E['desc']} : {activity.get('description') or V['rien_e']}",
        "",
        E["taches"],
        fmt_tasks(activity.get("tasks", [])),
        "",
        E["entrantes"],
        fmt_conn(activity.get("incoming", [])),
        "",
        E["sortantes"],
        fmt_conn_out(activity.get("outgoing", [])),
        "",
        E["contraintes"],
        fmt_list(activity.get("contraintes")),
        "",
        E["competences"],
        fmt_list(activity.get("competences")),
        "",
        E["savoirs"],
        fmt_list(activity.get("savoirs")),
        "",
        E["savoir_faire"],
        fmt_list(activity.get("savoir_faires")),
        "",
        E["hsc"],
        fmt_hsc(activity.get("hsc", [])),
        "",
        E["aptitudes"],
        fmt_list(activity.get("aptitudes")),
        "",
        E["outils"],
        fmt_tools(activity.get("available_tools", [])),
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

    # Outils disponibles pour l'entité active
    available_tools = [t.name for t in Tool.for_active_entity().order_by(Tool.name).all()]

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
        'available_tools': available_tools,
    }

    return jsonify(context)


# ---------------------------------------------------------------------------
# Endpoint inject — création des tâches validées en base
# ---------------------------------------------------------------------------

@chatbot_bp.post('/inject')
def inject_tasks():
    """
    Corps attendu :
      {
        "activity_id": int,
        "tasks": [
          {
            "label": str,
            "tools": [str],           # noms d'outils (existants ou nouveaux)
            "outgoing_link": {        # optionnel
              "data_name": str,
              "data_type": str,       # "nourrissante" | "descendante" | "remontante"
              "target_activity_name": str   # optionnel
            }
          }
        ]
      }
    Crée les tâches, résout/crée les outils, et crée les liens sortants si demandé.
    """
    data        = request.get_json(force=True) or {}
    activity_id = data.get('activity_id')
    tasks_in    = data.get('tasks', [])

    if not activity_id:
        return jsonify({'error': 'activity_id requis'}), 400

    activity = Activities.query.get(activity_id)
    if not activity:
        return jsonify({'error': 'Activité introuvable'}), 404

    entity_id = activity.entity_id
    created   = []

    try:
        for i, t in enumerate(tasks_in):
            label = (t.get('label') or '').strip()
            if not label:
                continue

            # ── Créer la tâche ────────────────────────────────────
            task = Task(
                name=label,
                description='',
                order=i + 1,
                activity_id=activity_id,
            )
            db.session.add(task)
            db.session.flush()  # pour avoir task.id

            # ── Résoudre / créer les outils ──────────────────────
            for tool_name in (t.get('tools') or []):
                tool_name = tool_name.strip()
                if not tool_name:
                    continue
                tool = Tool.query.filter(
                    Tool.entity_id == entity_id,
                    db.func.lower(Tool.name) == tool_name.lower(),
                ).first()
                if not tool:
                    tool = Tool(name=tool_name, entity_id=entity_id)
                    db.session.add(tool)
                    db.session.flush()
                if tool not in task.tools:
                    task.tools.append(tool)

            # ── Créer la connexion sortante si demandée ───────────
            ol = t.get('outgoing_link') or {}
            data_name = (ol.get('data_name') or '').strip()
            if data_name:
                data_type = (ol.get('data_type') or 'nourrissante').strip()
                target_act_name = (ol.get('target_activity_name') or '').strip()

                # Trouver ou créer le Data
                data_obj = Data.query.filter(
                    Data.entity_id == entity_id,
                    db.func.lower(Data.name) == data_name.lower(),
                ).first()
                if not data_obj:
                    data_obj = Data(
                        entity_id=entity_id,
                        name=data_name,
                        type=data_type,
                    )
                    db.session.add(data_obj)
                    db.session.flush()

                # Trouver l'activité cible (si précisée)
                target_activity_id = None
                if target_act_name:
                    target_act = Activities.query.filter(
                        Activities.entity_id == entity_id,
                        db.func.lower(Activities.name) == target_act_name.lower(),
                    ).first()
                    if target_act:
                        target_activity_id = target_act.id

                # Créer le Link si pas déjà existant
                existing_link = Link.query.filter_by(
                    entity_id=entity_id,
                    source_activity_id=activity_id,
                    source_data_id=data_obj.id,
                ).first()
                if not existing_link:
                    link = Link(
                        entity_id=entity_id,
                        source_activity_id=activity_id,
                        source_data_id=data_obj.id,
                        target_activity_id=target_activity_id,
                        type=data_type,
                        description=data_name,
                    )
                    db.session.add(link)
                    db.session.flush()

            created.append({'id': task.id, 'name': task.name})

        db.session.commit()
        return jsonify({'created': created, 'count': len(created)}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Endpoint chat — entièrement stateless (contexte + historique côté client)
# ---------------------------------------------------------------------------

@chatbot_bp.post('/chat')
def chat():
    """
    Corps attendu :
      {
        "activity": { ... },     # contexte complet de l'activité
        "history":  [ ... ],     # historique [{role, content}, ...] (max 14 derniers)
        "message":  "..."        # message de l'utilisateur
      }
    """
    data    = request.get_json(force=True) or {}
    activity = data.get('activity', {})
    history  = data.get('history', [])
    message  = (data.get('message') or '').strip()
    mode     = (data.get('mode') or 'creer').strip()
    # ⚠️ Le DÉMARRAGE d'une conversation n'a pas de tour utilisateur. Il en
    # avait un : `chatbot.js` construisait un message d'amorce EN FRANÇAIS
    # (« Mode création activé. Je souhaite créer les tâches… »), si bien qu'un
    # modèle servi par un prompt système ANGLAIS répondait quand même en
    # français — le retour « AI assistance is not in english » du pilote. Et
    # c'était un prompt écrit dans le navigateur, ce que le catalogue chiffré
    # interdit. La consigne d'ouverture vit déjà dans `chatbot.mode_*.<lang>`.
    demarrage = bool(data.get('demarrage'))

    lang = session.get('lang', 'fr')
    plang = 'en' if lang == 'en' else 'fr'

    if not message and not demarrage:
        return jsonify({'error': 'Empty message' if plang == 'en'
                                 else 'Message vide'}), 400
    mode_key = 'mode_ameliorer' if mode == 'ameliorer' else 'mode_creer'
    sys_prompt = get_prompt(f'chatbot.system.{plang}')
    mode_prompt = get_prompt(f'chatbot.{mode_key}.{plang}')
    if not sys_prompt or not mode_prompt:
        err_msg = ('AI assistant unavailable (prompts not loaded on this instance).'
                   if lang == 'en' else
                   "Assistant IA indisponible (prompts non chargés sur cette instance).")
        return jsonify({'error': err_msg}), 503

    context_block = _build_context(activity, plang)
    recent = history[-14:] if len(history) > 14 else history

    messages = [
        {'role': 'system', 'content': sys_prompt + mode_prompt},
        {'role': 'system', 'content': context_block},
        *recent,
    ]
    if not demarrage:
        messages.append({'role': 'user', 'content': message})

    try:
        api_key = get_openai_key()
        if not api_key:
            err_msg = ('AI key not configured on this instance.' if lang == 'en'
                       else "Clé IA non renseignée sur cette instance.")
            return jsonify({'error': err_msg, 'ai_unavailable': True}), 503
        from Code.ai_client import make_ai_client
        client, model, _err = make_ai_client()
        model = os.getenv('OPENAI_CHATBOT_MODEL') or model
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
        lang = session.get('lang', 'fr')
        err_msg = f'OpenAI API error: {str(e)}' if lang == 'en' else f'Erreur API OpenAI : {str(e)}'
        return jsonify({'error': err_msg}), 500

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
