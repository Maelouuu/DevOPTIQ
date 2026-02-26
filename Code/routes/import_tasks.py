# Code/routes/import_tasks.py
# Blueprint Flask — Import de tâches depuis CSV / JSON / Excel

import csv
import io
import json
from collections import defaultdict

from flask import Blueprint, request, jsonify

from Code.extensions import db
from Code.models.models import Activities, Task, Tool, Data, Link

import_tasks_bp = Blueprint('import_tasks', __name__, url_prefix='/api/import-tasks')

VALID_DATA_TYPES = {'nourrissante', 'descendante', 'remontante', 'déclenchante'}
DEFAULT_DATA_TYPE = 'nourrissante'


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _normalize_row(row: dict) -> dict:
    """Strip whitespace from all keys and values."""
    return {k.strip().lower(): (v or '').strip() for k, v in row.items()}


def _parse_csv(text: str) -> list:
    reader = csv.DictReader(io.StringIO(text.strip()))
    return [_normalize_row(r) for r in reader]


def _parse_json_content(text: str) -> list:
    data = json.loads(text.strip())
    if not isinstance(data, list):
        raise ValueError("Le JSON doit être un tableau d'objets")
    rows = []
    for item in data:
        entree = item.get('entree') or {}
        sortie = item.get('sortie') or {}
        outils = item.get('outils') or []
        if isinstance(outils, list):
            outils = ';'.join(str(o) for o in outils)
        rows.append({
            'nom_tache':             str(item.get('nom',             '')).strip(),
            'activite':              str(item.get('activite',         '')).strip(),
            'description':           str(item.get('description',      '')).strip(),
            'outils':                outils,
            'entree_nom':            str(entree.get('nom',            '')).strip(),
            'entree_type':           str(entree.get('type',           '')).strip().lower(),
            'sortie_nom':            str(sortie.get('nom',            '')).strip(),
            'sortie_type':           str(sortie.get('type',           '')).strip().lower(),
            'sortie_activite_cible': str(sortie.get('activite_cible', '')).strip(),
        })
    return rows


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_rows(rows: list) -> list:
    activities = Activities.for_active_entity().all()
    act_map = {a.name.strip().lower(): a for a in activities}

    results = []
    for i, row in enumerate(rows):
        errors   = []
        warnings = []

        nom            = row.get('nom_tache', '').strip()
        activite_name  = row.get('activite', '').strip()
        description    = row.get('description', '').strip()
        outils_raw     = row.get('outils', '').strip()
        entree_nom     = row.get('entree_nom', '').strip()
        entree_type    = row.get('entree_type', '').strip().lower()
        sortie_nom     = row.get('sortie_nom', '').strip()
        sortie_type    = row.get('sortie_type', '').strip().lower()
        sortie_cible   = row.get('sortie_activite_cible', '').strip()

        # Nom tâche obligatoire
        if not nom:
            errors.append("Nom de tâche manquant")

        # Activité obligatoire et doit exister
        activity_obj = None
        if not activite_name:
            errors.append("Activité non spécifiée")
        else:
            activity_obj = act_map.get(activite_name.lower())
            if not activity_obj:
                errors.append(f"Activité introuvable : « {activite_name} »")

        # Outils
        outils = [o.strip() for o in outils_raw.split(';') if o.strip()]

        # Validation type entrée
        if entree_nom:
            if entree_type and entree_type not in VALID_DATA_TYPES:
                warnings.append(
                    f"Type d'entrée « {entree_type} » invalide — "
                    f"« {DEFAULT_DATA_TYPE} » sera utilisé"
                )
                entree_type = DEFAULT_DATA_TYPE
            elif not entree_type:
                entree_type = DEFAULT_DATA_TYPE

        # Validation type sortie
        if sortie_nom:
            if sortie_type and sortie_type not in VALID_DATA_TYPES:
                warnings.append(
                    f"Type de sortie « {sortie_type} » invalide — "
                    f"« {DEFAULT_DATA_TYPE} » sera utilisé"
                )
                sortie_type = DEFAULT_DATA_TYPE
            elif not sortie_type:
                sortie_type = DEFAULT_DATA_TYPE

        # Activité cible sortie (warning si introuvable)
        sortie_cible_obj = None
        if sortie_cible:
            sortie_cible_obj = act_map.get(sortie_cible.lower())
            if not sortie_cible_obj:
                warnings.append(
                    f"Activité cible « {sortie_cible} » introuvable — "
                    f"connexion créée sans lien d'activité"
                )

        status = 'error' if errors else ('warning' if warnings else 'ok')

        results.append({
            'row':         i + 1,
            'nom_tache':   nom,
            'activite':    activite_name,
            'activity_id': activity_obj.id if activity_obj else None,
            'description': description,
            'outils':      outils,
            'entree': {'nom': entree_nom, 'type': entree_type} if entree_nom else None,
            'sortie': {
                'nom':              sortie_nom,
                'type':             sortie_type,
                'activite_cible':   sortie_cible,
                'activity_id_cible': sortie_cible_obj.id if sortie_cible_obj else None,
            } if sortie_nom else None,
            'errors':   errors,
            'warnings': warnings,
            'status':   status,
        })

    return results


# ---------------------------------------------------------------------------
# Endpoint : validation
# ---------------------------------------------------------------------------

@import_tasks_bp.post('/validate')
def validate_import():
    data    = request.get_json(force=True) or {}
    fmt     = data.get('format', 'csv')
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'Contenu vide'}), 400

    try:
        rows = _parse_json_content(content) if fmt == 'json' else _parse_csv(content)
    except Exception as e:
        return jsonify({'error': f'Erreur de parsing : {str(e)}'}), 400

    if not rows:
        return jsonify({'error': 'Aucune ligne trouvée dans le fichier'}), 400

    results = _validate_rows(rows)
    nb_ok   = sum(1 for r in results if r['status'] == 'ok')
    nb_warn = sum(1 for r in results if r['status'] == 'warning')
    nb_err  = sum(1 for r in results if r['status'] == 'error')

    return jsonify({
        'results': results,
        'summary': {
            'total':      len(results),
            'ok':         nb_ok,
            'warning':    nb_warn,
            'error':      nb_err,
            'can_inject': nb_err == 0,
        },
    })


# ---------------------------------------------------------------------------
# Endpoint : injection
# ---------------------------------------------------------------------------

@import_tasks_bp.post('/inject')
def inject_import():
    data    = request.get_json(force=True) or {}
    results = data.get('results', [])

    if not results:
        return jsonify({'error': 'Aucune donnée à injecter'}), 400

    valid = [r for r in results if r.get('status') != 'error' and r.get('activity_id')]
    if not valid:
        return jsonify({'error': 'Aucune ligne valide à injecter'}), 400

    first_act = Activities.query.get(valid[0]['activity_id'])
    if not first_act:
        return jsonify({'error': 'Activité introuvable'}), 400

    entity_id = first_act.entity_id
    created   = []

    try:
        tasks_by_activity = defaultdict(list)
        for r in valid:
            tasks_by_activity[r['activity_id']].append(r)

        for activity_id, act_rows in tasks_by_activity.items():
            max_order = (
                db.session.query(db.func.max(Task.order))
                .filter_by(activity_id=activity_id)
                .scalar() or 0
            )

            for i, row in enumerate(act_rows):
                # ── Créer la tâche ────────────────────────────────────
                task = Task(
                    name=row['nom_tache'],
                    description=row.get('description', ''),
                    order=max_order + i + 1,
                    activity_id=activity_id,
                )
                db.session.add(task)
                db.session.flush()

                # ── Outils ───────────────────────────────────────────
                for tool_name in (row.get('outils') or []):
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

                # ── Connexion entrante ────────────────────────────────
                if row.get('entree'):
                    e = row['entree']
                    data_obj = Data.query.filter(
                        Data.entity_id == entity_id,
                        db.func.lower(Data.name) == e['nom'].lower(),
                    ).first()
                    if not data_obj:
                        data_obj = Data(
                            entity_id=entity_id,
                            name=e['nom'],
                            type=e['type'],
                        )
                        db.session.add(data_obj)
                        db.session.flush()
                    if not Link.query.filter_by(
                        entity_id=entity_id,
                        target_activity_id=activity_id,
                        source_data_id=data_obj.id,
                    ).first():
                        db.session.add(Link(
                            entity_id=entity_id,
                            source_data_id=data_obj.id,
                            target_activity_id=activity_id,
                            type=e['type'],
                            description=e['nom'],
                        ))
                        db.session.flush()

                # ── Connexion sortante ────────────────────────────────
                if row.get('sortie'):
                    s = row['sortie']
                    data_obj = Data.query.filter(
                        Data.entity_id == entity_id,
                        db.func.lower(Data.name) == s['nom'].lower(),
                    ).first()
                    if not data_obj:
                        data_obj = Data(
                            entity_id=entity_id,
                            name=s['nom'],
                            type=s['type'],
                        )
                        db.session.add(data_obj)
                        db.session.flush()
                    if not Link.query.filter_by(
                        entity_id=entity_id,
                        source_activity_id=activity_id,
                        source_data_id=data_obj.id,
                    ).first():
                        db.session.add(Link(
                            entity_id=entity_id,
                            source_activity_id=activity_id,
                            source_data_id=data_obj.id,
                            target_activity_id=s.get('activity_id_cible'),
                            type=s['type'],
                            description=s['nom'],
                        ))
                        db.session.flush()

                created.append({
                    'activite': row['activite'],
                    'tache':    row['nom_tache'],
                })

        db.session.commit()
        return jsonify({'created': created, 'count': len(created)}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
