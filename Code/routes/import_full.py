# Code/routes/import_full.py
# Blueprint Flask — Import global IA depuis Excel
# Matching algorithmique (difflib) + OpenAI optionnel en enrichissement

import io
import os
import json
import re
from difflib import SequenceMatcher

import openpyxl
from flask import Blueprint, request, jsonify, session
from Code.ai_key import get_openai_key
# ⚠️ Cette route ne rend pas que des données : `analysis_notes`, les motifs
# d'appariement et les erreurs sont AFFICHÉS tels quels dans la fenêtre. Ils
# étaient en dur en français — un anglophone lisait « Analyse terminée : 4
# activité(s)… » au milieu d'une interface anglaise.
from Code.translations import t
from Code.prompts import get_prompt, prompts_available
from sqlalchemy import func

from Code.extensions import db
from Code.models.models import (
    Activities, Task, Tool, Role, Competency,
    Entity, activity_roles, task_roles,
)

import_full_bp = Blueprint('import_full', __name__, url_prefix='/api/import-full')


# La colonne « Skills » sert aussi à dire qu'il n'y a RIEN à savoir faire :
# « No Special skills required », « - », « n/a ». Enregistrées telles quelles,
# ces mentions devenaient des compétences portant la phrase elle-même (même
# règle que `tools/provisioning/provision.py`, pour les outils aussi).
_MENTION_VIDE = {'-', '--', '/', 'x', 'n/a', 'na', 'none', 'nil', 'aucune', 'aucun',
                 'néant', 'neant', 'rien', 'nothing'}
_SANS = re.compile(r"^\W*(no|not|non|aucun|aucune|pas|sans)\b.*\b(skill|competenc|compétenc|"
                   r"tool|outil|logiciel|software)", re.IGNORECASE)


def est_mention_vide(libelle) -> bool:
    texte = str(libelle or '').strip()
    return (not texte) or texte.lower() in _MENTION_VIDE or bool(_SANS.match(texte))


# ---------------------------------------------------------------------------
# Lecture du fichier Excel — parse robuste avec merged cells propagées
# ---------------------------------------------------------------------------

def _parse_excel_bytes(data: bytes) -> list:
    """
    Lit le fichier Excel et retourne une liste de groupes par activité.
    Gère les merged cells en propagant les valeurs manquantes.
    """
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)

    # Chercher la feuille principale
    target_sheet = None
    for name in wb.sheetnames:
        if 'activity' in name.lower() or 'activit' in name.lower():
            target_sheet = wb[name]
            break
    if not target_sheet:
        target_sheet = wb.active

    ws = target_sheet

    # Identifier les headers (première ligne non vide avec des mots-clés reconnus)
    header_row = None
    header_row_num = None
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=10, values_only=True), 1):
        row_s = [str(v or '').strip().lower() for v in row]
        if any(kw in ' '.join(row_s) for kw in (
            'task', 'tool', 'activity', 'semi finish', 'department', 'doer',
            # mots-clés français
            'activit', 'tâche', 'tache', 'outil', 'garant', 'savoir',
        )):
            header_row = row_s
            header_row_num = i
            break

    if not header_row:
        return []

    # Mapping colonnes → index
    col_map = {}
    kw_map = {
        'id':         ['id'],
        'department': ['department', 'dept'],
        'activity':   ['semi finish', 'semi-finish', 'activity', 'activit'],
        'guarantor':  ['guarantor', 'garant'],
        'task':       ['task', 'tâche'],
        'tool':       ['tool', 'outil'],
        'doer':       ['doer', 'executor', 'réalisateur', 'realisateur'],
        'approver':   ['approver', 'checker', 'approbateur'],
        'skills':     ['skills', 'knowledge', 'competenc', 'savoir'],
        'commentary': ['comment', 'commentaire', 'note'],
    }
    for col_idx, header in enumerate(header_row):
        for key, kws in kw_map.items():
            if any(kw in header for kw in kws) and key not in col_map:
                col_map[key] = col_idx

    def _get(row, key, default=''):
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return default
        val = row[idx]
        return str(val).strip() if val is not None else default

    def _split_csv(s: str) -> list:
        return [x.strip() for x in s.replace(';', ',').split(',') if x.strip()]

    # Lire les lignes de données (après le header)
    groups = []
    current_group = None
    last_activity = ''
    last_department = ''
    last_guarantor = ''

    for row in ws.iter_rows(min_row=header_row_num + 1, max_row=ws.max_row, values_only=True):
        row = list(row)

        activity_name = _get(row, 'activity')
        department = _get(row, 'department')
        guarantor = _get(row, 'guarantor')
        task_name = _get(row, 'task')
        tools_raw = _get(row, 'tool')
        doer = _get(row, 'doer')
        approver = _get(row, 'approver')
        skills_raw = _get(row, 'skills')
        commentary = _get(row, 'commentary')

        # Propager les merged cells
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

        if not activity_name:
            continue

        # Nouvelle activité ou continuation
        if current_group is None or current_group['activity_name'] != activity_name:
            current_group = {
                'activity_name': activity_name,
                'department': department,
                'guarantor': guarantor,
                'tasks': [],
            }
            groups.append(current_group)

        if task_name:
            current_group['tasks'].append({
                'name': task_name,
                'tools': _split_csv(tools_raw),
                'doer': doer,
                'approver': approver,
                'skills': _split_csv(skills_raw),
                'commentary': commentary,
            })
        elif tools_raw and current_group['tasks']:
            # Outils supplémentaires sur la ligne suivante (merged cells)
            for t in _split_csv(tools_raw):
                if t not in current_group['tasks'][-1]['tools']:
                    current_group['tasks'][-1]['tools'].append(t)

    return [g for g in groups if g['tasks']]


def grouper_lignes(lignes: list) -> list:
    """Regroupe des lignes DÉJÀ lues ({activity, department, guarantor, task,
    tool, doer, approver, skills, commentary}) en groupes par activité.

    Même règle que `_parse_excel_bytes` — cellules fusionnées propagées, outils
    et compétences séparés par « , » ou « ; » — mais sans rien savoir du
    fichier : le hub d'import lit xlsx ET csv, et l'IA peut avoir choisi les
    colonnes.
    """
    def _split(v):
        return [x.strip() for x in str(v or '').replace(';', ',').split(',')
                if not est_mention_vide(x)]

    groups, courant = [], None
    derniere = {'activity': '', 'department': '', 'guarantor': ''}
    for l in lignes:
        val = {k: str(l.get(k) or '').strip() for k in (
            'activity', 'department', 'guarantor', 'task', 'tool',
            'doer', 'approver', 'skills', 'commentary')}
        for k in ('activity', 'department', 'guarantor'):
            if val[k]:
                derniere[k] = val[k]
            else:
                val[k] = derniere[k]
        if not val['activity']:
            continue
        if courant is None or courant['activity_name'] != val['activity']:
            courant = {'activity_name': val['activity'], 'department': val['department'],
                       'guarantor': val['guarantor'], 'tasks': []}
            groups.append(courant)
        if val['task']:
            courant['tasks'].append({
                'name': val['task'], 'tools': _split(val['tool']),
                'doer': val['doer'], 'approver': val['approver'],
                'skills': _split(val['skills']), 'commentary': val['commentary'],
            })
        elif val['tool'] and courant['tasks']:
            for t_ in _split(val['tool']):
                if t_ not in courant['tasks'][-1]['tools']:
                    courant['tasks'][-1]['tools'].append(t_)
    return [g for g in groups if g['tasks']]


# ---------------------------------------------------------------------------
# Matching algorithmique (aucune dépendance externe)
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    return s.strip().lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _algorithmic_match(excel_groups: list, db_activities: list) -> dict:
    """
    Matching pur algorithmique :
    1. Correspondance exacte (casse ignorée)
    2. Correspondance par inclusion (l'un contient l'autre)
    3. Correspondance fuzzy via SequenceMatcher (seuil 0.60)
    """
    matched_groups = []
    unmatched_groups = []

    for group in excel_groups:
        excel_name = group['activity_name']
        excel_norm = _normalize(excel_name)

        best_act = None
        best_score = 0.0
        best_reason = ''

        for act in db_activities:
            db_norm = _normalize(act['name'])

            # 1. Exact
            if excel_norm == db_norm:
                best_act = act
                best_score = 1.0
                best_reason = t('impf.match_exact')
                break

            # 2. Inclusion
            if excel_norm in db_norm or db_norm in excel_norm:
                score = 0.88
                if score > best_score:
                    best_act = act
                    best_score = score
                    best_reason = t('impf.match_partial')
                continue

            # 3. Fuzzy
            score = _similarity(excel_name, act['name'])
            if score > best_score:
                best_act = act
                best_score = score
                best_reason = t('impf.match_approx').replace('{score}', f'{score:.0%}')

        if best_act and best_score >= 0.90:
            # Correspondance sûre uniquement → section "Mappé"
            matched_groups.append({
                'activity_name_excel': excel_name,
                'activity_id': best_act['id'],
                'activity_name_db': best_act['name'],
                'confidence': 'high',
                'match_reason': best_reason,
                'guarantor': group.get('guarantor', ''),
                'tasks': group['tasks'],
            })
        else:
            # Probable, incertain ou sans correspondance → section "À résoudre"
            scored = sorted(
                db_activities,
                key=lambda a: _similarity(excel_name, a['name']),
                reverse=True,
            )
            possible = [
                {
                    'activity_id': a['id'],
                    'activity_name': a['name'],
                    'similarity': 'medium' if _similarity(excel_name, a['name']) >= 0.5 else 'low',
                }
                for a in scored[:3]
            ]
            if best_act and best_score >= 0.75:
                reason = t('impf.reason_probable').replace('{score}', f'{best_score:.0%}')
            elif best_act and best_score >= 0.60:
                reason = t('impf.reason_uncertain').replace('{score}', f'{best_score:.0%}')
            else:
                reason = (
                    t('impf.reason_best').replace('{score}', f'{best_score:.0%}')
                    if best_act else t('impf.reason_none')
                )
            unmatched_groups.append({
                'activity_name_excel': excel_name,
                'reason': reason,
                'possible_matches': possible,
                'guarantor': group.get('guarantor', ''),
                'tasks': group['tasks'],
            })

    notes = (t('impf.notes')
             .replace('{matched}', str(len(matched_groups)))
             .replace('{unmatched}', str(len(unmatched_groups))))
    return {
        'matched_groups': matched_groups,
        'unmatched_groups': unmatched_groups,
        'analysis_notes': notes,
    }


# ---------------------------------------------------------------------------
# Enrichissement OpenAI optionnel (uniquement pour les non-matchés)
# ---------------------------------------------------------------------------



def _try_openai_enrich(unmatched_groups: list, db_activities: list) -> dict | None:
    """Tente un enrichissement IA pour les non-matchés. Retourne None si indisponible."""
    api_key = get_openai_key()
    enrich_prompt = get_prompt("import.enrich")
    if not api_key or not unmatched_groups or enrich_prompt is None:
        return None

    try:
        from openai import OpenAI
        payload = {
            'unmatched': [
                {'activity_name_excel': g['activity_name_excel']}
                for g in unmatched_groups
            ],
            'db_activities': db_activities,
        }
        from Code.ai_client import make_ai_client
        client, model, _err = make_ai_client()
        model = os.getenv('OPENAI_CHATBOT_MODEL') or model
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': enrich_prompt},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={'type': 'json_object'},
            temperature=0.1,
            max_tokens=800,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print(f'[ImportFull] OpenAI enrichissement ignoré : {e}')
        return None


# ---------------------------------------------------------------------------
# Endpoint : analyse
# ---------------------------------------------------------------------------

@import_full_bp.post('/analyze')
def analyze_excel():
    """
    Reçoit un fichier Excel, analyse algorithmiquement les activités,
    enrichit optionnellement avec OpenAI pour les non-matchés.
    """
    if 'file' not in request.files:
        return jsonify({'error': t('impf.err_no_file')}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': t('impf.err_empty_file')}), 400

    allowed = ('.xlsx', '.xls', '.xlsm')
    if not any(file.filename.lower().endswith(e) for e in allowed):
        return jsonify({'error': t('impf.err_bad_format')}), 400

    entity_id = session.get('active_entity_id')
    if not entity_id:
        return jsonify({'error': t('impf.err_no_entity')}), 400

    # Parse Excel
    try:
        excel_groups = _parse_excel_bytes(file.read())
    except Exception as e:
        return jsonify({'error': t('impf.err_read').replace('{detail}', str(e))}), 400

    if not excel_groups:
        return jsonify({'error': t('impf.err_no_data')}), 400

    resultat = analyser_groupes(excel_groups, entity_id)
    if resultat is None:
        return jsonify({'error': t('impf.err_no_activity')}), 400
    return jsonify(resultat)


def analyser_groupes(excel_groups: list, entity_id: int):
    """Apparie des groupes d'activités aux activités de la carto (algorithme,
    puis IA pour les restes). None si la carto n'a aucune activité."""
    activities = Activities.query.filter_by(entity_id=entity_id).order_by(Activities.name).all()
    db_activities = [{'id': a.id, 'name': a.name} for a in activities]
    if not db_activities:
        return None

    # 1. Matching algorithmique (toujours)
    analysis = _algorithmic_match(excel_groups, db_activities)

    # 2. Enrichissement IA optionnel pour les non-matchés (silencieux si quota dépassé)
    if analysis['unmatched_groups']:
        ai_result = _try_openai_enrich(analysis['unmatched_groups'], db_activities)
        if ai_result:
            resolved_names = {r['activity_name_excel'] for r in ai_result.get('resolved', [])}
            resolved_map = {r['activity_name_excel']: r for r in ai_result.get('resolved', [])}

            still_unmatched = []
            for grp in analysis['unmatched_groups']:
                name = grp['activity_name_excel']
                if name in resolved_map:
                    r = resolved_map[name]
                    ai_conf = r.get('confidence', 'medium')
                    if ai_conf == 'high':
                        # Seulement les correspondances sûres de l'IA vont dans "Mappé"
                        analysis['matched_groups'].append({
                            'activity_name_excel': name,
                            'activity_id': r['activity_id'],
                            'activity_name_db': r['activity_name_db'],
                            'confidence': 'high',
                            'match_reason': r.get('match_reason', t('impf.ai_resolved')),
                            'guarantor': grp.get('guarantor', ''),
                            'tasks': grp['tasks'],
                        })
                    else:
                        # Suggestion IA non sûre → reste dans "À résoudre" avec la suggestion en tête
                        ai_suggestion = {
                            'activity_id': r['activity_id'],
                            'activity_name': r['activity_name_db'],
                            'similarity': ai_conf,
                        }
                        existing_possible = list(grp.get('possible_matches', []))
                        ids_present = {p['activity_id'] for p in existing_possible}
                        if r['activity_id'] not in ids_present:
                            existing_possible = [ai_suggestion] + existing_possible
                        still_unmatched.append({
                            **grp,
                            'reason': (t('impf.ai_suggestion')
                                       .replace('{conf}', str(ai_conf))
                                       .replace('{reason}', r.get('match_reason',
                                                                  t('impf.ai_resolved')))),
                            'possible_matches': existing_possible[:3],
                        })
                else:
                    still_unmatched.append(grp)

            analysis['unmatched_groups'] = still_unmatched
            analysis['analysis_notes'] = (
                t('impf.notes_ai')
                .replace('{matched}', str(len(analysis["matched_groups"])))
                .replace('{unmatched}', str(len(analysis["unmatched_groups"])))
            )

    # Statistiques
    matched = analysis['matched_groups']
    unmatched = analysis['unmatched_groups']
    total_tasks = sum(len(g['tasks']) for g in matched + unmatched)
    matched_tasks = sum(len(g['tasks']) for g in matched)

    return {
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
    }


# ---------------------------------------------------------------------------
# Endpoint : injection
# ---------------------------------------------------------------------------

@import_full_bp.post('/inject')
def inject_full():
    """
    Reçoit les groupes validés et les injecte en base.
    """
    data = request.get_json(force=True) or {}
    groups = data.get('groups', [])

    if not groups:
        return jsonify({'error': t('impf.err_no_group')}), 400

    entity_id = session.get('active_entity_id')
    if not entity_id:
        return jsonify({'error': 'Aucune entité active'}), 400
    # ⚠️ Cette route écrit : elle exige le droit d'écrire dans la carto, comme
    # l'import de la page Carte (`/api/import`). Lire la carto ne suffit pas.
    from Code.carto_access import can_edit
    if not can_edit(db.session.get(Entity, entity_id)):
        return jsonify({'error': t('imph.err_droits')}), 403

    try:
        stats = injecter_groupes(groups, entity_id)
        db.session.commit()
        return jsonify({'status': 'ok', 'stats': stats}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def injecter_groupes(groups: list, entity_id: int) -> dict:
    """Crée tâches, outils, rôles et compétences des groupes validés, dans
    l'entité donnée. Ne commit pas : l'appelant décide."""
    stats = {
        'tasks_created': 0,
        'tools_created': 0,
        'roles_created': 0,
        'competencies_created': 0,
        'activities_updated': 0,
    }
    for group in groups:
        activity_id = group.get('activity_id')
        if not activity_id:
            continue

        activity = Activities.query.get(activity_id)
        if not activity or activity.entity_id != entity_id:
            continue

        guarantor_name = (group.get('guarantor') or '').strip()

        # ── Garant ───────────────────────────────────────────────────
        if guarantor_name:
            role = _get_or_create_role(guarantor_name, entity_id, stats)
            _link_role_to_activity(role, activity, 'Garant')

        # ── Tâches ───────────────────────────────────────────────────
        max_order = (
            db.session.query(func.max(Task.order))
            .filter_by(activity_id=activity_id)
            .scalar() or 0
        )

        for i, task_in in enumerate(group.get('tasks', [])):
            task_name = (task_in.get('name') or '').strip()
            if not task_name:
                continue

            # Éviter les doublons : vérifier si la tâche existe déjà pour cette activité
            existing_task = Task.query.filter(
                Task.activity_id == activity_id,
                func.lower(Task.name) == task_name.lower()
            ).first()
            if existing_task:
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
                if est_mention_vide(tool_name):
                    continue
                tool = _get_or_create_tool(tool_name, entity_id, stats)
                if tool not in task.tools:
                    task.tools.append(tool)

            # Doer
            doer_name = (task_in.get('doer') or '').strip()
            if doer_name:
                doer_role = _get_or_create_role(doer_name, entity_id, stats)
                _link_role_to_task(doer_role, task, 'executant')

            # Approbateur
            approver_name = (task_in.get('approver') or '').strip()
            if approver_name:
                approver_role = _get_or_create_role(approver_name, entity_id, stats)
                _link_role_to_task(approver_role, task, 'approbateur')

            # Compétences
            for skill in (task_in.get('skills') or []):
                skill = skill.strip()
                if est_mention_vide(skill):
                    continue
                exists = Competency.query.filter_by(
                    activity_id=activity_id,
                    description=skill,
                ).first()
                if not exists:
                    db.session.add(Competency(activity_id=activity_id, description=skill))
                    stats['competencies_created'] += 1

        stats['activities_updated'] += 1
    return stats


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
    from Code.roles_communs import role_par_nom
    role = role_par_nom(name, creer=False)
    if not role:
        role = role_par_nom(name, entity_id=entity_id, hors_carte=True)
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
