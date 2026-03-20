# Code/routes/import_full.py
# Blueprint Flask — Import global IA depuis Excel
# Analyse le fichier avec GPT-4o, mappe activités/tâches, propose une review

import io
import os
import json
import tempfile

import openpyxl
from flask import Blueprint, request, jsonify, session
from openai import OpenAI
from sqlalchemy import func

from Code.extensions import db
from Code.models.models import (
    Activities, Task, Tool, Role, Competency,
    Entity, activity_roles, task_roles,
)

import_full_bp = Blueprint('import_full', __name__, url_prefix='/api/import-full')


# ---------------------------------------------------------------------------
# Lecture du fichier Excel — parse robuste avec merged cells propagées
# ---------------------------------------------------------------------------

def _parse_excel_bytes(data: bytes) -> list:
    """
    Lit le fichier Excel et retourne une liste de groupes :
    [
        {
            "activity_name": str,       # valeur de la colonne 'Semi finish' (propagée)
            "department": str,
            "guarantor": str,
            "tasks": [
                {
                    "name": str,
                    "tools": [str],
                    "doer": str,
                    "approver": str,
                    "skills": [str],
                    "commentary": str,
                }
            ]
        },
        ...
    ]
    """
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)

    # Chercher la feuille principale (Activity list ou similaire)
    target_sheet = None
    for name in wb.sheetnames:
        if 'activity' in name.lower() or 'activit' in name.lower():
            target_sheet = wb[name]
            break
    if not target_sheet:
        target_sheet = wb.active

    ws = target_sheet

    # Identifier les headers (première ligne non vide)
    header_row = None
    for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
        if any(v for v in row):
            header_row = [str(v).strip().lower() if v else '' for v in row]
            break

    if not header_row:
        return []

    # Mapping colonnes
    col_map = {}
    keywords = {
        'id': ['id'],
        'department': ['department', 'dept'],
        'activity': ['semi finish', 'semi-finish', 'activity', 'activit'],
        'guarantor': ['guarantor', 'garant'],
        'task': ['task', 'tâche'],
        'tool': ['tool', 'outil'],
        'doer': ['doer', 'executor', 'executant'],
        'approver': ['approver', 'approbateur', 'checker'],
        'skills': ['skills', 'knowledge', 'competenc', 'savoir'],
        'commentary': ['comment', 'commentaire', 'note'],
    }
    for col_idx, header in enumerate(header_row):
        for key, kws in keywords.items():
            if any(kw in header for kw in kws) and key not in col_map:
                col_map[key] = col_idx

    # Lire toutes les lignes (après la header)
    raw_rows = []
    header_row_idx = None
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)):
        if any(v for v in row):
            if header_row_idx is None and any(
                str(v or '').lower().strip() in ('id', 'task', 'tool', 'doer', 'department', 'semi finish')
                for v in row
            ):
                header_row_idx = i
                continue
            if header_row_idx is not None:
                raw_rows.append(list(row))

    def _get(row, key, default=''):
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return default
        val = row[idx]
        return str(val).strip() if val is not None else default

    def _split_csv(s: str) -> list:
        return [x.strip() for x in s.replace(';', ',').split(',') if x.strip()]

    # Propager les valeurs des merged cells (activity_name, department, guarantor)
    groups = []
    current_group = None
    last_activity = ''
    last_department = ''
    last_guarantor = ''

    for row in raw_rows:
        activity_name = _get(row, 'activity')
        department = _get(row, 'department')
        guarantor = _get(row, 'guarantor')
        task_name = _get(row, 'task')
        tools_raw = _get(row, 'tool')
        doer = _get(row, 'doer')
        approver = _get(row, 'approver')
        skills_raw = _get(row, 'skills')
        commentary = _get(row, 'commentary')

        # Propagation des merged cells
        if activity_name:
            last_activity = activity_name
        else:
            activity_name = last_activity

        if department:
            last_department = department
        else:
            department = last_department

        if guarantor:
            last_guarantor = guarantor
        else:
            guarantor = last_guarantor

        # Ignorer les lignes sans nom d'activité
        if not activity_name:
            continue

        # Nouvelle activité ou continuation ?
        if current_group is None or current_group['activity_name'] != activity_name:
            current_group = {
                'activity_name': activity_name,
                'department': department,
                'guarantor': guarantor,
                'tasks': [],
            }
            groups.append(current_group)

        # Ajouter la tâche si elle existe
        if task_name:
            current_group['tasks'].append({
                'name': task_name,
                'tools': _split_csv(tools_raw),
                'doer': doer,
                'approver': approver,
                'skills': _split_csv(skills_raw),
                'commentary': commentary,
            })
        elif tools_raw:
            # Ligne avec outils supplémentaires pour la tâche précédente
            if current_group['tasks']:
                extra_tools = _split_csv(tools_raw)
                for t in extra_tools:
                    if t not in current_group['tasks'][-1]['tools']:
                        current_group['tasks'][-1]['tools'].append(t)

    # Filtrer les groupes vides
    return [g for g in groups if g['tasks'] or g['activity_name']]


# ---------------------------------------------------------------------------
# Prompt GPT-4o pour l'analyse et le matching
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """\
Tu es un assistant d'import de données OPTIQ.
Tu reçois :
1. Une liste de groupes issus d'un fichier Excel (activités + tâches)
2. La liste des activités déjà présentes dans la base de données OPTIQ (avec leurs IDs)

Ton travail :
- Pour chaque groupe Excel, trouver l'activité correspondante dans la base (matching fuzzy, insensible à la casse)
- Si plusieurs correspondances possibles, choisir la plus probable
- Si aucune correspondance évidente, indiquer "unmatched" avec des alternatives si possible
- Rester factuel : ne pas inventer de tâches, ne pas reformuler les noms

Réponds UNIQUEMENT en JSON valide, sans texte autour.

Format de réponse :
{
  "matched_groups": [
    {
      "activity_name_excel": "...",
      "activity_id": 42,
      "activity_name_db": "...",
      "confidence": "high" | "medium" | "low",
      "match_reason": "Explication courte du matching",
      "tasks": [/* liste des tâches telles quelles */]
    }
  ],
  "unmatched_groups": [
    {
      "activity_name_excel": "...",
      "reason": "Pourquoi aucune correspondance",
      "possible_matches": [
        {"activity_id": 3, "activity_name": "...", "similarity": "high" | "medium"}
      ],
      "tasks": [/* liste des tâches */]
    }
  ],
  "analysis_notes": "Observations générales sur la qualité du fichier"
}
"""


def _call_openai_analysis(excel_groups: list, db_activities: list) -> dict:
    payload = {
        "excel_groups": excel_groups,
        "db_activities": db_activities,
    }
    user_msg = json.dumps(payload, ensure_ascii=False)

    client = OpenAI()
    model = os.getenv('OPENAI_CHATBOT_MODEL', 'gpt-4o-mini')

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': ANALYSIS_PROMPT},
            {'role': 'user', 'content': user_msg},
        ],
        response_format={'type': 'json_object'},
        temperature=0.1,
        max_tokens=4000,
    )
    return json.loads(resp.choices[0].message.content)


# ---------------------------------------------------------------------------
# Endpoint : analyse du fichier Excel
# ---------------------------------------------------------------------------

@import_full_bp.post('/analyze')
def analyze_excel():
    """
    Reçoit un fichier Excel en multipart/form-data.
    Analyse les données et les mappe aux activités de l'entité active via GPT-4o.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Fichier vide'}), 400

    allowed_ext = ('.xlsx', '.xls', '.xlsm')
    if not any(file.filename.lower().endswith(ext) for ext in allowed_ext):
        return jsonify({'error': 'Format non supporté — utilisez .xlsx, .xls ou .xlsm'}), 400

    entity_id = session.get('active_entity_id')
    if not entity_id:
        return jsonify({'error': 'Aucune entité active — sélectionnez une entité dans la cartographie'}), 400

    # Lire le fichier
    try:
        file_bytes = file.read()
        excel_groups = _parse_excel_bytes(file_bytes)
    except Exception as e:
        return jsonify({'error': f'Erreur lecture Excel : {str(e)}'}), 400

    if not excel_groups:
        return jsonify({'error': 'Aucune donnée trouvée dans le fichier'}), 400

    # Récupérer les activités de l'entité active
    activities = Activities.query.filter_by(entity_id=entity_id).order_by(Activities.name).all()
    db_activities = [{'id': a.id, 'name': a.name} for a in activities]

    if not db_activities:
        return jsonify({
            'error': 'Aucune activité dans cette entité. '
                     'Importez d\'abord votre cartographie SVG.'
        }), 400

    # Analyse IA
    try:
        analysis = _call_openai_analysis(excel_groups, db_activities)
    except Exception as e:
        return jsonify({'error': f'Erreur analyse IA : {str(e)}'}), 500

    # Statistiques
    matched = analysis.get('matched_groups', [])
    unmatched = analysis.get('unmatched_groups', [])
    total_tasks = sum(len(g.get('tasks', [])) for g in matched + unmatched)
    matched_tasks = sum(len(g.get('tasks', [])) for g in matched)

    return jsonify({
        'status': 'ok',
        'analysis': analysis,
        'stats': {
            'total_groups_excel': len(excel_groups),
            'matched_activities': len(matched),
            'unmatched_activities': len(unmatched),
            'total_tasks': total_tasks,
            'matched_tasks': matched_tasks,
            'unmatched_tasks': total_tasks - matched_tasks,
        },
        'db_activities': db_activities,
    })


# ---------------------------------------------------------------------------
# Endpoint : injection des données validées
# ---------------------------------------------------------------------------

@import_full_bp.post('/inject')
def inject_full():
    """
    Reçoit les groupes validés par l'utilisateur et les injecte en base.
    Corps attendu :
    {
      "groups": [
        {
          "activity_id": int,
          "guarantor": str,         // optionnel
          "tasks": [
            {
              "name": str,
              "tools": [str],
              "doer": str,           // optionnel
              "approver": str,       // optionnel
              "skills": [str],       // optionnel
            }
          ]
        }
      ]
    }
    """
    data = request.get_json(force=True) or {}
    groups = data.get('groups', [])

    if not groups:
        return jsonify({'error': 'Aucun groupe à injecter'}), 400

    entity_id = session.get('active_entity_id')
    if not entity_id:
        return jsonify({'error': 'Aucune entité active'}), 400

    stats = {
        'tasks_created': 0,
        'tools_created': 0,
        'roles_created': 0,
        'competencies_created': 0,
        'activities_updated': 0,
    }

    try:
        for group in groups:
            activity_id = group.get('activity_id')
            if not activity_id:
                continue

            activity = Activities.query.get(activity_id)
            if not activity or activity.entity_id != entity_id:
                continue

            guarantor_name = (group.get('guarantor') or '').strip()
            tasks_in = group.get('tasks', [])

            # ── Garant de l'activité ──────────────────────────────────────
            if guarantor_name:
                role = _get_or_create_role(guarantor_name, entity_id, stats)
                _link_role_to_activity(role, activity, 'garant')

            # ── Tâches ───────────────────────────────────────────────────
            max_order = (
                db.session.query(func.max(Task.order))
                .filter_by(activity_id=activity_id)
                .scalar() or 0
            )

            for i, task_in in enumerate(tasks_in):
                task_name = (task_in.get('name') or '').strip()
                if not task_name:
                    continue

                task = Task(
                    name=task_name,
                    description=task_in.get('commentary', '') or '',
                    order=max_order + i + 1,
                    activity_id=activity_id,
                )
                db.session.add(task)
                db.session.flush()
                stats['tasks_created'] += 1

                # Outils
                for tool_name in (task_in.get('tools') or []):
                    tool_name = tool_name.strip()
                    if not tool_name:
                        continue
                    tool = _get_or_create_tool(tool_name, entity_id, stats)
                    if tool not in task.tools:
                        task.tools.append(tool)

                # Rôle Doer → task_roles avec status='executant'
                doer_name = (task_in.get('doer') or '').strip()
                if doer_name:
                    doer_role = _get_or_create_role(doer_name, entity_id, stats)
                    _link_role_to_task(doer_role, task, 'executant')

                # Rôle Approver → task_roles avec status='approbateur'
                approver_name = (task_in.get('approver') or '').strip()
                if approver_name:
                    approver_role = _get_or_create_role(approver_name, entity_id, stats)
                    _link_role_to_task(approver_role, task, 'approbateur')

                # Compétences/Savoirs → Competency
                for skill in (task_in.get('skills') or []):
                    skill = skill.strip()
                    if not skill:
                        continue
                    existing = Competency.query.filter_by(
                        activity_id=activity_id,
                        description=skill,
                    ).first()
                    if not existing:
                        db.session.add(Competency(
                            activity_id=activity_id,
                            description=skill,
                        ))
                        stats['competencies_created'] += 1

            stats['activities_updated'] += 1

        db.session.commit()
        return jsonify({'status': 'ok', 'stats': stats}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Helpers DB
# ---------------------------------------------------------------------------

def _get_or_create_tool(name: str, entity_id: int, stats: dict) -> Tool:
    tool = Tool.query.filter(
        Tool.entity_id == entity_id,
        func.lower(Tool.name) == name.lower(),
    ).first()
    if not tool:
        tool = Tool(name=name, entity_id=entity_id)
        db.session.add(tool)
        db.session.flush()
        stats['tools_created'] += 1
    return tool


def _get_or_create_role(name: str, entity_id: int, stats: dict) -> Role:
    role = Role.query.filter(
        Role.entity_id == entity_id,
        func.lower(Role.name) == name.lower(),
    ).first()
    if not role:
        role = Role(name=name, entity_id=entity_id)
        db.session.add(role)
        db.session.flush()
        stats['roles_created'] += 1
    return role


def _link_role_to_activity(role: Role, activity: Activities, status: str):
    exists = db.session.execute(
        activity_roles.select().where(
            activity_roles.c.activity_id == activity.id,
            activity_roles.c.role_id == role.id,
        )
    ).first()
    if not exists:
        db.session.execute(
            activity_roles.insert().values(
                activity_id=activity.id,
                role_id=role.id,
                status=status,
            )
        )
        db.session.flush()


def _link_role_to_task(role: Role, task: Task, status: str):
    exists = db.session.execute(
        task_roles.select().where(
            task_roles.c.task_id == task.id,
            task_roles.c.role_id == role.id,
        )
    ).first()
    if not exists:
        db.session.execute(
            task_roles.insert().values(
                task_id=task.id,
                role_id=role.id,
                status=status,
            )
        )
        db.session.flush()
