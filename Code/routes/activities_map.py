# Code/routes/activities_map.py
"""
Cartographie des activités avec gestion multi-entités.
Import des connexions depuis fichiers VSDX.
WIZARD UNIFIÉ SVG + VSDX.
"""
import os
import re
import json
import shutil
import xml.etree.ElementTree as ET
import tempfile
import uuid
from typing import Dict

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    send_file,
    session
)

from sqlalchemy import or_
from sqlalchemy.orm.attributes import flag_modified

from Code.extensions import db
from Code.models.models import Activities, Entity, Link, Data, Task, Role, CrossCartoLiaison, activity_roles, task_roles, task_tools

from Code.routes.vsdx_conection_parser import (
    parse_vsdx_connections,
    validate_connections_against_activities
)
from Code.routes.vsdx_decision_extractor import extract_decisions_from_vsdx
from Code.routes.propose_common import openai_client_or_none


# ============================================================
# Blueprint
# ============================================================
activities_map_bp = Blueprint(
    "activities_map_bp",
    __name__,
    url_prefix="/activities"
)

# ============================================================
# CHEMINS - Calculés une seule fois au chargement
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
ENTITIES_DIR = os.path.join(STATIC_DIR, "entities")
OLD_SVG_PATH = os.path.join(STATIC_DIR, "img", "carto_activities.svg")

# IMPORTANT: Créer le dossier entities au chargement du module
os.makedirs(ENTITIES_DIR, exist_ok=True)
print(f"[CARTO] ENTITIES_DIR créé/vérifié: {ENTITIES_DIR}")


# ============================================================
# HELPERS
# ============================================================
def get_entity_dir(entity_id):
    """Retourne le chemin du dossier d'une entité."""
    return os.path.join(ENTITIES_DIR, f"entity_{entity_id}")


def get_entity_svg_path(entity_id):
    """Retourne le chemin du fichier SVG pour une entité."""
    return os.path.join(get_entity_dir(entity_id), "carto.svg")


def get_entity_vsdx_path(entity_id):
    """Retourne le chemin du fichier VSDX pour une entité."""
    return os.path.join(get_entity_dir(entity_id), "connections.vsdx")


def ensure_entity_dir(entity_id):
    """Crée le dossier d'une entité s'il n'existe pas."""
    entity_dir = get_entity_dir(entity_id)
    os.makedirs(entity_dir, exist_ok=True)
    print(f"[CARTO] Dossier entité créé/vérifié: {entity_dir}")
    return entity_dir


def check_svg_exists(entity_id):
    """Vérifie si un SVG existe pour l'entité (filesystem ou base de données)."""
    svg_path = get_entity_svg_path(entity_id)

    # 1. Fichier présent sur disque
    if os.path.exists(svg_path):
        print(f"[CARTO] SVG trouvé sur disque pour entité {entity_id}: {svg_path}")
        return True, svg_path

    # 2. Scan du dossier entité pour tout fichier .svg (fallback nom différent)
    entity_dir = get_entity_dir(entity_id)
    if os.path.isdir(entity_dir):
        svgs = sorted(f for f in os.listdir(entity_dir) if f.endswith('.svg'))
        if svgs:
            found_path = os.path.join(entity_dir, svgs[0])
            print(f"[CARTO] SVG trouvé (scan) pour entité {entity_id}: {found_path}")
            return True, found_path

    # 3. Fallback DB : contenu SVG stocké en base (filesystem éphémère sur cloud)
    entity = Entity.query.get(entity_id)
    if entity and entity.svg_content:
        try:
            ensure_entity_dir(entity_id)
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(entity.svg_content)
            print(f"[CARTO] SVG restauré depuis DB pour entité {entity_id}")
            return True, svg_path
        except Exception as e:
            print(f"[CARTO] Erreur restauration SVG depuis DB: {e}")

    print(f"[CARTO] Aucun SVG trouvé pour entité {entity_id}")
    return False, None


def check_vsdx_exists(entity_id):
    """Vérifie si un VSDX a été uploadé pour l'entité (fichier ou nom stocké en DB)."""
    vsdx_path = get_entity_vsdx_path(entity_id)
    if os.path.exists(vsdx_path):
        return True, vsdx_path
    # Fallback : vérifier si un nom de fichier VSDX est enregistré en DB
    entity = Entity.query.get(entity_id)
    if entity and entity.vsdx_filename:
        # Le fichier a été uploadé par le passé (connexions importées en DB)
        return True, vsdx_path
    return False, vsdx_path


def get_active_entity():
    """
    Récupère l'entité active.
    Priorité : session → is_active en DB → première entité de l'utilisateur.
    Synchronise toujours la session avec ce qui est trouvé.
    """
    user_id = session.get('user_id')
    entity_id = session.get('active_entity_id')

    # 1. Session valide → récupérer sans filtre strict owner_id
    if entity_id:
        entity = Entity.query.get(entity_id)
        if entity:
            # Vérification souple : valide si owner_id est None ou correspond à user
            if not user_id or entity.owner_id is None or entity.owner_id == user_id:
                return entity

    if not user_id:
        return None

    # 2. Chercher l'entité marquée is_active=True en DB (avec ou sans owner_id)
    from sqlalchemy import or_
    active_db = Entity.query.filter(
        Entity.is_active == True,
        or_(Entity.owner_id == user_id, Entity.owner_id == None)
    ).first()
    if active_db:
        session['active_entity_id'] = active_db.id
        return active_db

    # 3. Dernière entité de l'utilisateur (avec ou sans owner_id)
    latest = Entity.query.filter(
        or_(Entity.owner_id == user_id, Entity.owner_id == None)
    ).order_by(Entity.id.desc()).first()
    if latest:
        session['active_entity_id'] = latest.id
        return latest

    return None


def get_active_entity_id():
    """Récupère l'ID de l'entité active."""
    entity = get_active_entity()
    return entity.id if entity else None


def _normalize_link_type(raw):
    """Normalise le type de connexion pour la BDD."""
    if not raw:
        return None
    t = str(raw).strip().lower()
    mapping = {
        "t link": "déclenchante",
        "trigger": "déclenchante",
        "déclenchante": "déclenchante",
        "n link": "nourrissante",
        "nourrissante": "nourrissante",
    }
    return mapping.get(t)


# ============================================================
# PAGE CARTOGRAPHIE
# ============================================================
@activities_map_bp.route("/map")
def activities_map_page():
    user_id = session.get('user_id')
    active_entity_id = get_active_entity_id()
    active_entity = get_active_entity()
    
    svg_exists = False
    vsdx_exists = False
    current_svg = None
    current_vsdx = None
    activities = []
    shape_activity_map = {}
    
    if active_entity:
        # Vérifier les fichiers avec fallback
        svg_exists, svg_path = check_svg_exists(active_entity.id)
        vsdx_exists, vsdx_path = check_vsdx_exists(active_entity.id)
        
        if svg_exists:
            current_svg = active_entity.svg_filename or "carto.svg"
        if vsdx_exists:
            current_vsdx = active_entity.vsdx_filename or "connections.vsdx"
        
        # Log pour debug
        print(f"[CARTO] Entité {active_entity.id}: SVG={svg_exists} ({svg_path}), VSDX={vsdx_exists}")
        
        activities = sorted(
            Activities.query.filter_by(entity_id=active_entity.id).all(),
            key=lambda a: (a.name or '').lower()
        )
        
        shape_activity_map = {
            str(act.shape_id): act.id
            for act in activities
            if act.shape_id
        }
    
    # Liste des entités du user
    all_entities = []
    if user_id:
        entities = Entity.query.filter_by(owner_id=user_id).order_by(Entity.name).all()
        all_entities = []
        for e in entities:
            e_svg_exists, _ = check_svg_exists(e.id)
            e_vsdx_exists, _ = check_vsdx_exists(e.id)
            all_entities.append({
                "id": e.id,
                "name": e.name,
                "description": e.description or "",
                "svg_filename": e.svg_filename,
                "vsdx_filename": e.vsdx_filename,
                "is_active": (e.id == active_entity_id),
                "activities_count": Activities.query.filter_by(entity_id=e.id).count(),
                "svg_exists": e_svg_exists,
                "vsdx_exists": e_vsdx_exists
            })
    
    active_entity_dict = None
    if active_entity:
        active_entity_dict = {
            "id": active_entity.id,
            "name": active_entity.name,
            "description": active_entity.description or "",
            "svg_filename": active_entity.svg_filename,
            "vsdx_filename": active_entity.vsdx_filename,
            "is_active": True
        }
    
    # Carto OptiqCarto — persistée en base (colonne ajoutée en migration)
    has_optiqcarto = bool(active_entity and getattr(active_entity, 'optiqcarto_data', None))

    # IDs des activités hachurées (subtype 'extco') ou en forme stade (subtype
    # 'external') — utilisées par le bouton "Externes" pour griser le reste de
    # la carto. On reconstruit la liste depuis le JSON OptiqCarto pour ne pas
    # dépendre d'un champ SQL supplémentaire sur Activities.
    extco_activity_ids = []
    if active_entity and getattr(active_entity, 'optiqcarto_data', None):
        try:
            import json as _json
            carto = _json.loads(active_entity.optiqcarto_data)
            extco_labels = {
                (s.get('label') or '').strip()
                for s in carto.get('shapes', [])
                if s.get('subtype') in ('extco', 'external')
            }
            extco_labels.discard('')
            if extco_labels:
                extco_activity_ids = [
                    act.id for act in activities
                    if (act.name or '').strip() in extco_labels
                ]
        except Exception as _e:
            print(f"[CARTO] extco extract error: {_e}")

    # Active calque from session (set by cartography editor)
    active_calque_id = session.get('active_calque_id')

    return render_template(
        "activities_map.html",
        svg_exists=svg_exists,
        vsdx_exists=vsdx_exists,
        current_svg=current_svg,
        current_vsdx=current_vsdx,
        shape_activity_map=shape_activity_map,
        activities=activities,
        active_entity=active_entity_dict,
        all_entities=all_entities,
        has_optiqcarto=has_optiqcarto,
        extco_activity_ids=extco_activity_ids,
        active_calque_id=active_calque_id,
    )



@activities_map_bp.route("/map/api/activities")
def map_api_activities():
    """Returns the activities list for the active entity (used to refresh after calque switch)."""
    entity = get_active_entity()
    if not entity:
        return jsonify([])
    acts = Activities.query.filter_by(entity_id=entity.id).order_by(Activities.id).all()
    return jsonify([{"id": a.id, "name": a.name or ""} for a in acts])


# ============================================================
# SERVIR LE SVG DE L'ENTITÉ ACTIVE
# ============================================================
@activities_map_bp.route("/svg")
def serve_svg():
    """Sert le fichier SVG de l'entité active (filesystem ou DB)."""
    active_entity = get_active_entity()

    if not active_entity:
        return jsonify({"error": "Aucune entité active"}), 404

    # check_svg_exists gère automatiquement la restauration depuis la DB
    svg_exists, svg_path = check_svg_exists(active_entity.id)

    if not svg_exists or not svg_path:
        # Dernier recours : servir directement depuis DB sans passer par le disque
        if active_entity.svg_content:
            from flask import Response
            print(f"[CARTO] Serving SVG depuis DB (direct) pour entité {active_entity.id}")
            return Response(active_entity.svg_content, mimetype='image/svg+xml',
                            headers={"Cache-Control": "no-store"})
        print(f"[CARTO] SVG non trouvé pour l'entité {active_entity.id}")
        return jsonify({"error": "SVG non trouvé pour cette entité"}), 404

    print(f"[CARTO] Serving SVG pour entité {active_entity.id}: {svg_path}")
    return send_file(svg_path, mimetype='image/svg+xml', max_age=0)


# ============================================================
# SERVIR LE SVG D'UNE ENTITÉ QUELCONQUE (sans toucher la session)
# ============================================================
@activities_map_bp.route("/api/svg/<int:entity_id>")
def serve_entity_svg(entity_id):
    """Sert le SVG d'une entité par son ID sans modifier la session active."""
    from flask import Response as FlaskResponse
    entity = Entity.query.get(entity_id)
    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404

    svg_exists, svg_path = check_svg_exists(entity_id)

    if svg_exists and svg_path:
        return send_file(svg_path, mimetype='image/svg+xml', max_age=0)

    if entity.svg_content:
        return FlaskResponse(entity.svg_content, mimetype='image/svg+xml',
                             headers={"Cache-Control": "no-store"})

    return jsonify({"error": "SVG non trouvé pour cette entité"}), 404


# ============================================================
# API ENTITÉS
# ============================================================
@activities_map_bp.route("/api/entities", methods=["GET"])
def list_entities():
    user_id = session.get('user_id')
    active_entity_id = get_active_entity_id()
    
    if not user_id:
        return jsonify([])
    
    entities = Entity.query.filter_by(owner_id=user_id).order_by(Entity.name).all()
    
    result = []
    for e in entities:
        result.append({
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "is_active": (e.id == active_entity_id),
            "activities_count": Activities.query.filter_by(entity_id=e.id).count(),
            "optiqcarto_exists": bool(e.optiqcarto_data),
        })
    
    return jsonify(result)


@activities_map_bp.route("/api/entities/<int:entity_id>/details", methods=["GET"])
def get_entity_details(entity_id):
    """Récupère les détails d'une entité."""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401
    
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    
    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404
    
    svg_exists, svg_path = check_svg_exists(entity_id)
    vsdx_exists, vsdx_path = check_vsdx_exists(entity_id)
    
    return jsonify({
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "svg_exists": svg_exists,
        "vsdx_exists": vsdx_exists,
        "current_svg": entity.svg_filename if svg_exists else None,
        "current_vsdx": entity.vsdx_filename or ("connections.vsdx" if vsdx_exists else None),
        "activities_count": Activities.query.filter_by(entity_id=entity_id).count(),
        "connections_count": Link.query.filter_by(entity_id=entity_id).count()
    })


@activities_map_bp.route("/api/entities", methods=["POST"])
def create_entity():
    data = request.get_json()
    
    if not data or not data.get("name"):
        return jsonify({"error": "Nom requis"}), 400
    
    user_id = session.get('user_id')
    
    # Désactiver les autres entités avant de créer la nouvelle
    Entity.query.filter_by(owner_id=user_id).update({'is_active': False})

    entity = Entity(
        name=data["name"],
        description=data.get("description", ""),
        owner_id=user_id,
        is_active=True
    )
    db.session.add(entity)
    db.session.commit()

    session['active_entity_id'] = entity.id

    # Créer le dossier immédiatement
    entity_dir = ensure_entity_dir(entity.id)
    print(f"[CARTO] Nouvelle entité créée et activée: {entity.id} -> {entity_dir}")

    return jsonify({
        "status": "ok",
        "redirect_url": "/cartography/editor",
        "entity": {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "is_active": True
        }
    })


@activities_map_bp.route("/api/entities/<int:entity_id>/activate", methods=["POST"])
def activate_entity(entity_id):
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"error": "Non connecté"}), 401

    entity = Entity.query.get(entity_id)

    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404

    # Vérification souple : accepter si owner_id est None ou correspond
    if entity.owner_id is not None and entity.owner_id != user_id:
        return jsonify({"error": "Entité non trouvée"}), 404

    # Désactiver toutes les autres entités de l'utilisateur en DB
    Entity.query.filter_by(owner_id=user_id).update({'is_active': False})
    # Couvrir aussi les entités sans owner_id (données legacy)
    if entity.owner_id is None:
        Entity.query.filter(Entity.owner_id == None, Entity.id != entity_id).update({'is_active': False})
    entity.is_active = True
    db.session.commit()

    # Mettre aussi à jour la session (double garantie)
    session['active_entity_id'] = entity.id
    print(f"[CARTO] Entité activée: {entity.id} ({entity.name})")

    return jsonify({
        "status": "ok",
        "message": f"Entité '{entity.name}' activée"
    })


@activities_map_bp.route("/api/entities/<int:entity_id>", methods=["DELETE"])
def delete_entity(entity_id):
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401
    
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    
    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404
    
    entity_name = entity.name
    
    # Supprimer le dossier de l'entité
    entity_dir = get_entity_dir(entity_id)
    if os.path.exists(entity_dir):
        shutil.rmtree(entity_dir)
        print(f"[CARTO] Dossier supprimé: {entity_dir}")

    try:
        # Suppression EXHAUSTIVE dans l'ordre enfants → parents, pour ne JAMAIS violer une
        # clé étrangère (Neon/PostgreSQL applique les FK ; SQLite non). On couvre toutes les
        # tables qui référencent l'entité, ses activités, rôles, données, liens, tâches, outils
        # et domaines techniques. ⚠️ Toute NOUVELLE table liée à l'un de ces objets doit être
        # ajoutée ici (c'est l'omission de `competencies`/S/SF/HSC qui provoquait l'erreur).
        from Code.models.models import (
            Tool, Competency, Softskill, Savoir, SavoirFaire, Aptitude, Constraint,
            CompetencyEvaluation, ResultCapabilityLink, ResultDiagnostic,
            ActivityTechnicalDomain, RoleActivityDomainRequirement, UserDomainLevel,
            TechnicalDomain, HscLevelDescriptor, Performance, TaskLinkAssignment,
            TimeProject, TimeProjectLine, TimeRoleAnalysis, TimeRoleLine,
            TimeWeakness, TimeAnalysis, CartoCalque, UserRole, User,
        )

        sel = lambda stmt: db.session.execute(stmt).scalars().all()

        def _del(model, column, ids):
            if ids:
                model.query.filter(column.in_(ids)).delete(synchronize_session=False)

        def _adel(table, column, ids):
            if ids:
                db.session.execute(table.delete().where(column.in_(ids)))

        # ── Rassembler les identifiants liés à l'entité ──
        act_ids  = sel(db.select(Activities.id).where(Activities.entity_id == entity_id))
        role_ids = sel(db.select(Role.id).where(Role.entity_id == entity_id))
        tool_ids = sel(db.select(Tool.id).where(Tool.entity_id == entity_id))
        dom_ids  = sel(db.select(TechnicalDomain.id).where(TechnicalDomain.entity_id == entity_id))
        task_ids = sel(db.select(Task.id).where(Task.activity_id.in_(act_ids))) if act_ids else []
        data_ids = set(sel(db.select(Data.id).where(Data.entity_id == entity_id)))
        if act_ids:
            data_ids.update(sel(db.select(Data.id).where(Data.producer_activity_id.in_(act_ids))))
        data_ids = list(data_ids)
        # Liens de l'entité OU référençant ses activités/données (y compris cross-entité)
        link_conds = [Link.entity_id == entity_id]
        if act_ids:
            link_conds += [Link.source_activity_id.in_(act_ids), Link.target_activity_id.in_(act_ids)]
        if data_ids:
            link_conds += [Link.source_data_id.in_(data_ids), Link.target_data_id.in_(data_ids)]
        link_ids = sel(db.select(Link.id).where(or_(*link_conds)))
        tra_ids  = sel(db.select(TimeRoleAnalysis.id).where(TimeRoleAnalysis.role_id.in_(role_ids))) if role_ids else []
        tp_ids   = sel(db.select(TimeProject.id).where(TimeProject.entity_id == entity_id))
        liaison_ids = sel(db.select(CrossCartoLiaison.id).where(or_(
            CrossCartoLiaison.extco_entity_id == entity_id,
            CrossCartoLiaison.origin_entity_id == entity_id)))

        # ── Tables d'association ──
        _adel(task_tools, task_tools.c.task_id, task_ids)
        _adel(task_roles, task_roles.c.task_id, task_ids)
        _adel(task_roles, task_roles.c.role_id, role_ids)
        _adel(activity_roles, activity_roles.c.activity_id, act_ids)
        _adel(activity_roles, activity_roles.c.role_id, role_ids)
        _del(UserRole, UserRole.role_id, role_ids)

        # ── Enfants des liens (avant les liens) ──
        _del(Performance, Performance.link_id, link_ids)
        _del(TaskLinkAssignment, TaskLinkAssignment.link_id, link_ids)
        _del(TaskLinkAssignment, TaskLinkAssignment.task_id, task_ids)
        # Liens propagés cross-carto (dans d'autres entités) puis les liaisons
        if liaison_ids:
            Link.query.filter(Link.cross_carto_liaison_id.in_(liaison_ids)).delete(synchronize_session=False)
        _del(Link, Link.id, link_ids)
        _del(CrossCartoLiaison, CrossCartoLiaison.id, liaison_ids)

        # ── Enfants référençant activités / données ──
        _del(ResultCapabilityLink, ResultCapabilityLink.activity_id, act_ids)
        _del(ResultCapabilityLink, ResultCapabilityLink.data_id, data_ids)
        _del(ResultCapabilityLink, ResultCapabilityLink.entity_id, [entity_id])
        _del(ResultDiagnostic, ResultDiagnostic.activity_id, act_ids)
        _del(ResultDiagnostic, ResultDiagnostic.data_id, data_ids)
        _del(ResultDiagnostic, ResultDiagnostic.entity_id, [entity_id])
        _del(CompetencyEvaluation, CompetencyEvaluation.activity_id, act_ids)
        _del(Competency, Competency.activity_id, act_ids)
        _del(Softskill, Softskill.activity_id, act_ids)
        _del(Savoir, Savoir.activity_id, act_ids)
        _del(SavoirFaire, SavoirFaire.activity_id, act_ids)
        _del(Aptitude, Aptitude.activity_id, act_ids)
        _del(Constraint, Constraint.activity_id, act_ids)
        _del(TimeProjectLine, TimeProjectLine.activity_id, act_ids)
        _del(TimeRoleLine, TimeRoleLine.activity_id, act_ids)
        _del(TimeWeakness, TimeWeakness.activity_id, act_ids)
        _del(TimeWeakness, TimeWeakness.task_id, task_ids)
        _del(TimeAnalysis, TimeAnalysis.activity_id, act_ids)
        _del(TimeAnalysis, TimeAnalysis.task_id, task_ids)
        _del(TimeAnalysis, TimeAnalysis.role_id, role_ids)

        # ── Domaines techniques (enfants avant domaines) ──
        _del(ActivityTechnicalDomain, ActivityTechnicalDomain.activity_id, act_ids)
        _del(ActivityTechnicalDomain, ActivityTechnicalDomain.domain_id, dom_ids)
        _del(RoleActivityDomainRequirement, RoleActivityDomainRequirement.activity_id, act_ids)
        _del(RoleActivityDomainRequirement, RoleActivityDomainRequirement.role_id, role_ids)
        _del(RoleActivityDomainRequirement, RoleActivityDomainRequirement.domain_id, dom_ids)
        _del(UserDomainLevel, UserDomainLevel.domain_id, dom_ids)

        # ── Analyses de temps (projets / rôles) ──
        _del(TimeRoleLine, TimeRoleLine.role_analysis_id, tra_ids)
        _del(TimeRoleAnalysis, TimeRoleAnalysis.id, tra_ids)
        _del(TimeProjectLine, TimeProjectLine.project_id, tp_ids)
        _del(TimeProject, TimeProject.id, tp_ids)

        # ── Tâches, puis données (Data.producer_activity_id → activities) ──
        _del(Task, Task.activity_id, act_ids)
        _del(Data, Data.id, data_ids)
        Data.query.filter_by(entity_id=entity_id).delete(synchronize_session=False)

        # ── Objets principaux de l'entité ──
        Activities.query.filter_by(entity_id=entity_id).delete(synchronize_session=False)
        _del(Role, Role.id, role_ids)
        _del(Tool, Tool.id, tool_ids)
        _del(TechnicalDomain, TechnicalDomain.id, dom_ids)
        HscLevelDescriptor.query.filter_by(entity_id=entity_id).delete(synchronize_session=False)
        CartoCalque.query.filter_by(entity_id=entity_id).delete(synchronize_session=False)

        # ── Utilisateurs : on DÉTACHE de l'entité (on ne supprime pas les comptes) ──
        User.query.filter_by(entity_id=entity_id).update(
            {User.entity_id: None}, synchronize_session=False)

        # ── Entité ──
        Entity.query.filter_by(id=entity_id).delete(synchronize_session=False)
        db.session.commit()
        
        if session.get('active_entity_id') == entity_id:
            first = Entity.query.filter_by(owner_id=user_id).first()
            if first:
                session['active_entity_id'] = first.id
            else:
                session.pop('active_entity_id', None)
        
        return jsonify({"status": "ok", "message": f"'{entity_name}' supprimée"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@activities_map_bp.route("/api/entities/<int:entity_id>", methods=["PATCH"])
def update_entity(entity_id):
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401
    
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    
    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404
    
    data = request.get_json()
    
    if data.get("name"):
        entity.name = data["name"]
    if "description" in data:
        entity.description = data["description"]
    
    db.session.commit()
    
    return jsonify({
        "status": "ok",
        "entity": {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description
        }
    })


# ============================================================
# EXTRACTION DES ACTIVITÉS DEPUIS LE SVG
# ============================================================
def extract_activities_from_svg(svg_path):
    """Parse un fichier SVG Visio et extrait les activités."""
    activities = []
    seen_names = set()
    
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        SVG_NS = "http://www.w3.org/2000/svg"
        VISIO_NS = "http://schemas.microsoft.com/visio/2003/SVGExtensions/"
        
        for elem in root.iter():
            mid = elem.get(f"{{{VISIO_NS}}}mID")
            if not mid:
                continue
            
            layer = elem.get(f"{{{VISIO_NS}}}layerMember", "")
            if layer != "1":
                continue
            
            text_content = None
            for text_elem in elem.iter(f"{{{SVG_NS}}}text"):
                t = "".join(text_elem.itertext()).strip()
                if t and len(t) > 2:
                    text_content = t
                    break
            
            if not text_content or len(text_content) > 80:
                continue
            
            if text_content.lower() not in seen_names:
                seen_names.add(text_content.lower())
                activities.append({"shape_id": mid, "name": text_content})
        
        print(f"[CARTO] Activités extraites du SVG: {len(activities)}")
        
    except Exception as e:
        print(f"[CARTO] Erreur extraction SVG: {e}")
    
    return activities


def sync_activities_with_svg(entity_id, svg_path):
    """Synchronise les activités en base avec celles du SVG."""
    stats = {
        "added": 0,
        "renamed": 0,
        "unchanged": 0,
        "deleted": 0,
        "total": 0
    }
    
    svg_activities = extract_activities_from_svg(svg_path)
    stats["total"] = len(svg_activities)
    
    if not svg_activities:
        return stats
    
    svg_shape_map = {str(a["shape_id"]): a["name"] for a in svg_activities}
    svg_shape_ids = set(svg_shape_map.keys())
    
    existing = Activities.query.filter_by(entity_id=entity_id).all()
    existing_map = {str(a.shape_id): a for a in existing if a.shape_id}
    existing_ids = set(existing_map.keys())
    
    # Nouvelles activités
    for shape_id in (svg_shape_ids - existing_ids):
        name = svg_shape_map[shape_id]

        # Éviter les doublons : si une activité du même nom existe déjà sans shape_id
        # (ex : créée via import Excel), on lui assigne le shape_id plutôt que de créer un doublon
        existing_by_name = Activities.query.filter(
            Activities.entity_id == entity_id,
            db.func.lower(Activities.name) == name.lower(),
            Activities.shape_id.is_(None)
        ).first()

        if existing_by_name:
            existing_by_name.shape_id = shape_id
            stats["unchanged"] += 1
            print(f"[CARTO] Activité existante reliée au SVG : '{name}' (shape_id={shape_id})")
        else:
            new_act = Activities(
                entity_id=entity_id,
                shape_id=shape_id,
                name=name,
                description=""
            )
            db.session.add(new_act)
            stats["added"] += 1
    
    # Renommages
    for shape_id in (svg_shape_ids & existing_ids):
        svg_name = svg_shape_map[shape_id]
        db_act = existing_map[shape_id]
        
        if db_act.name != svg_name:
            db_act.name = svg_name
            stats["renamed"] += 1
        else:
            stats["unchanged"] += 1
    
    # Suppressions
    for shape_id in (existing_ids - svg_shape_ids):
        db_act = existing_map[shape_id]
        
        Link.query.filter(
            (Link.source_activity_id == db_act.id) | 
            (Link.target_activity_id == db_act.id)
        ).delete(synchronize_session=False)
        
        db.session.delete(db_act)
        stats["deleted"] += 1
    
    db.session.commit()
    print(f"[CARTO] Sync: +{stats['added']} ~{stats['renamed']} -{stats['deleted']}")
    
    return stats


# ============================================================
# WIZARD - UPLOAD CARTOGRAPHIE UNIFIÉ
# ============================================================
@activities_map_bp.route("/upload-cartography", methods=["POST"])
def upload_cartography():
    """Upload unifié SVG et/ou VSDX pour une entité."""
    
    entity_id = request.form.get("entity_id")
    
    if entity_id:
        entity_id = int(entity_id)
        user_id = session.get('user_id')
        entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
        
        if not entity:
            return jsonify({"error": "Entité non trouvée"}), 404
    else:
        entity = get_active_entity()
        if not entity:
            return jsonify({"error": "Aucune entité active"}), 400
        entity_id = entity.id
    
    mode = request.form.get("mode", "new")
    keep_svg = request.form.get("keep_svg", "false").lower() == "true"
    keep_vsdx = request.form.get("keep_vsdx", "false").lower() == "true"
    clear_connections = request.form.get("clear_connections", "false").lower() == "true"
    
    svg_file = request.files.get("svg_file")
    vsdx_file = request.files.get("vsdx_file")
    
    stats = {
        "activities": 0,
        "connections": 0,
        "svg_updated": False,
        "vsdx_updated": False,
        "svg_kept": False,
        "vsdx_kept": False,
        "sync": None
    }
    
    try:
        entity_dir = ensure_entity_dir(entity_id)
        print(f"[CARTO] Upload pour entité {entity_id} dans {entity_dir}")
        print(f"[CARTO] Mode: {mode}, keep_svg: {keep_svg}, keep_vsdx: {keep_vsdx}")
        
        # Chemins des fichiers
        svg_path = get_entity_svg_path(entity_id)
        vsdx_path = get_entity_vsdx_path(entity_id)
        
        # === GESTION DU SVG ===
        if svg_file and svg_file.filename:
            # Nouveau fichier SVG uploadé
            if not svg_file.filename.lower().endswith(".svg"):
                return jsonify({"error": "Format SVG requis"}), 400

            svg_file.save(svg_path)
            print(f"[CARTO] SVG sauvegardé: {svg_path} ({os.path.exists(svg_path)})")

            # IMPORTANT: Sauvegarder le nom original ET le contenu en base
            # Le contenu en DB permet de restaurer le fichier si le filesystem éphémère est vidé
            entity.svg_filename = svg_file.filename
            try:
                with open(svg_path, 'r', encoding='utf-8') as f:
                    entity.svg_content = f.read()
                print(f"[CARTO] Contenu SVG sauvegardé en DB pour entité {entity_id}")
            except Exception as e:
                print(f"[CARTO] Avertissement: impossible de lire SVG pour stockage DB: {e}")
            db.session.commit()
            
            sync_stats = sync_activities_with_svg(entity_id, svg_path)
            stats["sync"] = sync_stats
            stats["activities"] = sync_stats.get("total", 0)
            stats["svg_updated"] = True
            
        elif keep_svg:
            # Garder le SVG existant - vérifier qu'il existe
            if os.path.exists(svg_path):
                print(f"[CARTO] SVG conservé: {svg_path}")
                stats["svg_kept"] = True
                stats["activities"] = Activities.query.filter_by(entity_id=entity_id).count()
            else:
                print(f"[CARTO] ATTENTION: keep_svg=true mais fichier inexistant: {svg_path}")
                
        elif mode == "new":
            # Mode création sans SVG et sans keep_svg -> erreur
            return jsonify({"error": "SVG requis pour nouvelle cartographie"}), 400
        
        # Comptage des activités si pas déjà fait
        if not stats["activities"]:
            stats["activities"] = Activities.query.filter_by(entity_id=entity_id).count()
        
        # === GESTION DU VSDX ===
        if vsdx_file and vsdx_file.filename:
            # Nouveau fichier VSDX uploadé
            if not vsdx_file.filename.lower().endswith(".vsdx"):
                return jsonify({"error": "Format VSDX requis"}), 400
            
            vsdx_file.save(vsdx_path)
            print(f"[CARTO] VSDX sauvegardé: {vsdx_path} ({os.path.exists(vsdx_path)})")

            # IMPORTANT: Sauvegarder le nom original en base
            entity.vsdx_filename = vsdx_file.filename
            db.session.commit()
            
            # Parser et importer les connexions
            connections, errors = parse_vsdx_connections(vsdx_path)
            
            if connections:
                activities = Activities.query.filter_by(entity_id=entity_id).all()
                act_map = {a.name: a.id for a in activities}
                
                valid, invalid, missing = validate_connections_against_activities(connections, act_map)
                
                if clear_connections:
                    Link.query.filter_by(entity_id=entity_id).delete()
                
                imported = 0
                for conn in valid:
                    src_id = conn['source_activity_id']
                    tgt_id = conn['target_activity_id']
                    
                    exists = Link.query.filter_by(
                        entity_id=entity_id,
                        source_activity_id=src_id,
                        target_activity_id=tgt_id
                    ).first()
                    
                    if exists:
                        continue
                    
                    data_id = None
                    if conn.get('data_name'):
                        data = Data.query.filter_by(
                            entity_id=entity_id,
                            name=conn['data_name']
                        ).first()
                        
                        if not data:
                            data = Data(
                                entity_id=entity_id,
                                name=conn['data_name'],
                                type=_normalize_link_type(conn.get("data_type")) or "nourrissante"
                            )
                            db.session.add(data)
                            db.session.flush()
                        
                        data_id = data.id
                    
                    link = Link(
                        entity_id=entity_id,
                        source_activity_id=src_id,
                        target_activity_id=tgt_id,
                        source_data_id=data_id,
                        type=_normalize_link_type(conn.get("data_type")) or "nourrissante",
                        description=conn.get("data_name")
                    )
                    
                    db.session.add(link)
                    imported += 1
                
                db.session.commit()
                stats["connections"] = imported
                stats["vsdx_updated"] = True
                stats["invalid_connections"] = len(invalid)
                stats["missing_activities"] = missing
                
                print(f"[CARTO] Connexions importées: {imported}, invalides: {len(invalid)}")
        
        elif keep_vsdx:
            # Garder le VSDX existant - vérifier qu'il existe
            if os.path.exists(vsdx_path):
                print(f"[CARTO] VSDX conservé: {vsdx_path}")
                stats["vsdx_kept"] = True
            else:
                print(f"[CARTO] ATTENTION: keep_vsdx=true mais fichier inexistant: {vsdx_path}")
        
        # Comptage final des connexions
        if not stats["connections"]:
            stats["connections"] = Link.query.filter_by(entity_id=entity_id).count()
        
        return jsonify({
            "status": "ok",
            "message": "Cartographie mise à jour",
            "stats": stats
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"[CARTO] Erreur upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# PREVIEW CONNEXIONS
# ============================================================
@activities_map_bp.route("/preview-connections", methods=["POST"])
def preview_connections():
    """Analyse un fichier VSDX et retourne un aperçu des connexions."""
    
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".vsdx"):
        return jsonify({"error": "Format VSDX requis"}), 400

    entity_id = request.form.get("entity_id")
    if entity_id:
        entity_id = int(entity_id)
        user_id = session.get('user_id')
        entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
        if not entity:
            return jsonify({"error": "Entité non trouvée"}), 404
    else:
        entity = get_active_entity()
        if not entity:
            return jsonify({"error": "Aucune entité active"}), 400
        entity_id = entity.id

    with tempfile.NamedTemporaryFile(delete=False, suffix='.vsdx') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        connections, errors = parse_vsdx_connections(tmp_path)

        if errors:
            return jsonify({"status": "error", "errors": errors}), 400

        activities = Activities.query.filter_by(entity_id=entity_id).all()
        act_map = {a.name: a.id for a in activities}

        valid, invalid, missing = validate_connections_against_activities(connections, act_map)

        return jsonify({
            "status": "ok",
            "total_connections": len(connections),
            "valid_connections": len(valid),
            "invalid_connections": len(invalid),
            "connections": [
                {
                    "source": c['source_name'],
                    "target": c['target_name'],
                    "data_name": c.get('data_name'),
                    "data_type": c.get('data_type'),
                    "valid": c['source_name'] in act_map and c['target_name'] in act_map
                }
                for c in connections
            ],
            "missing_activities": missing
        })

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ============================================================
# CONNEXIONS - CRUD
# ============================================================
@activities_map_bp.route("/list-connections")
def list_connections():
    entity = get_active_entity()
    
    if not entity:
        return jsonify({"connections": []})
    
    activities = Activities.query.filter_by(entity_id=entity.id).all()
    act_names = {a.id: a.name for a in activities}
    
    links = Link.query.filter_by(entity_id=entity.id).all()
    
    result = []
    for link in links:
        data_name = None
        if link.source_data_id:
            data = Data.query.get(link.source_data_id)
            if data:
                data_name = data.name
        
        result.append({
            "id": link.id,
            "source": act_names.get(link.source_activity_id, "?"),
            "target": act_names.get(link.target_activity_id, "?"),
            "data_name": data_name or link.description,
            "data_type": link.type
        })
    
    return jsonify({"status": "ok", "count": len(result), "connections": result})


@activities_map_bp.route("/delete-connection/<int:link_id>", methods=["DELETE"])
def delete_connection(link_id):
    link = Link.query.get(link_id)
    if not link:
        return jsonify({"error": "Connexion non trouvée"}), 404
    
    db.session.delete(link)
    db.session.commit()
    
    return jsonify({"status": "ok"})


@activities_map_bp.route("/clear-connections", methods=["DELETE"])
def clear_connections():
    entity = get_active_entity()
    if not entity:
        return jsonify({"status": "ok", "deleted": 0})
    
    deleted = Link.query.filter_by(entity_id=entity.id).delete()
    db.session.commit()
    
    return jsonify({"status": "ok", "deleted": deleted})


# ============================================================
# RE-SYNC
# ============================================================
@activities_map_bp.route("/resync", methods=["POST"])
def resync_activities():
    entity = get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400
    
    svg_exists, svg_path = check_svg_exists(entity.id)
    
    if not svg_exists or not svg_path:
        return jsonify({"error": "SVG non trouvé"}), 404
    
    try:
        stats = sync_activities_with_svg(entity.id, svg_path)
        return jsonify({"status": "ok", "sync": stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@activities_map_bp.route("/update-cartography")
def update_cartography():
    return jsonify({"status": "ok", "message": "Cartographie rechargée"}), 200


# ============================================================
# DEBUG - Route pour vérifier les fichiers
# ============================================================
@activities_map_bp.route("/debug/files")
def debug_files():
    """Route de debug pour vérifier l'état des fichiers."""
    result = {
        "entities_dir": ENTITIES_DIR,
        "entities_dir_exists": os.path.exists(ENTITIES_DIR),
        "old_svg_path": OLD_SVG_PATH,
        "old_svg_exists": os.path.exists(OLD_SVG_PATH),
        "entities": []
    }
    
    user_id = session.get('user_id')
    if user_id:
        entities = Entity.query.filter_by(owner_id=user_id).all()
        for e in entities:
            svg_exists, svg_path = check_svg_exists(e.id)
            vsdx_exists, vsdx_path = check_vsdx_exists(e.id)
            entity_dir = get_entity_dir(e.id)
            
            # Lister les fichiers dans le dossier de l'entité
            files_in_dir = []
            if os.path.exists(entity_dir):
                files_in_dir = os.listdir(entity_dir)
            
            result["entities"].append({
                "id": e.id,
                "name": e.name,
                "svg_filename_in_db": e.svg_filename,
                "vsdx_filename_in_db": getattr(e, 'vsdx_filename', 'CHAMP_INEXISTANT'),
                "entity_dir": entity_dir,
                "entity_dir_exists": os.path.exists(entity_dir),
                "files_in_dir": files_in_dir,
                "svg_path": svg_path,
                "svg_exists": svg_exists,
                "vsdx_path": vsdx_path,
                "vsdx_exists": vsdx_exists
            })
    
    return jsonify(result)

# ============================================================
# API : CORRESPONDANCES CROSS-CARTO
# ============================================================

@activities_map_bp.route("/api/cross_carto_matches", methods=["GET"])
def cross_carto_matches():
    """
    Retourne les formes hachurées (extco) de la carto active dont le nom correspond
    à une forme NON hachurée dans une autre carto de l'utilisateur (liaison inter-carto).
    """
    user_id = session.get('user_id')
    active_entity_id = get_active_entity_id()

    if not active_entity_id or not user_id:
        return jsonify({"matches": [], "total": 0}), 200

    active_entity = Entity.query.get(active_entity_id)
    if not active_entity or not active_entity.optiqcarto_data:
        return jsonify({"matches": [], "total": 0}), 200

    try:
        active_carto = json.loads(active_entity.optiqcarto_data)
    except (json.JSONDecodeError, TypeError):
        return jsonify({"matches": [], "total": 0}), 200

    # Seules les formes hachurées (extco) de la carto active sont des liaisons potentielles
    extco_shapes = [
        s for s in active_carto.get('shapes', [])
        if s.get('subtype') == 'extco' and (s.get('label') or '').strip()
    ]
    if not extco_shapes:
        return jsonify({"matches": [], "total": 0}), 200

    # lookup: label.lower() → shape_id
    extco_by_name = {
        (s.get('label') or '').strip().lower(): str(s['id'])
        for s in extco_shapes
    }

    other_entities = Entity.query.filter(
        Entity.owner_id == user_id,
        Entity.id != active_entity_id
    ).all()

    if not other_entities:
        return jsonify({"matches": [], "total": 0}), 200

    # shape_id (extco dans carto active) → liste d'entités où une activité non-hachurée porte le même nom
    matched = {}

    for entity in other_entities:
        non_extco = {}  # name.lower() → {"activity_id": db_id, "activity_name": str}

        if entity.optiqcarto_data:
            try:
                other_carto = json.loads(entity.optiqcarto_data)
                other_shape_ids = []
                other_shape_names = {}  # shape_id → label
                for s in other_carto.get('shapes', []):
                    if s.get('subtype') != 'extco':
                        label = (s.get('label') or '').strip()
                        if label:
                            sid = str(s['id'])
                            other_shape_ids.append(sid)
                            other_shape_names[sid] = label
                # Lookup DB activity IDs for these shapes
                if other_shape_ids:
                    for act in Activities.query.filter(
                        Activities.entity_id == entity.id,
                        Activities.shape_id.in_(other_shape_ids)
                    ).all():
                        name_l = (act.name or '').strip().lower()
                        if name_l:
                            non_extco[name_l] = {"activity_id": act.id, "activity_name": act.name}
                # Shapes présents dans la carto mais pas encore en DB
                for sid, label in other_shape_names.items():
                    name_l = label.lower()
                    if name_l and name_l not in non_extco:
                        non_extco[name_l] = {"activity_id": None, "activity_name": label}
            except (json.JSONDecodeError, TypeError):
                pass
        else:
            # Pas de carto JSON : activités DB traitées comme non-hachurées
            for act in Activities.query.filter(
                Activities.entity_id == entity.id,
                Activities.shape_id.isnot(None)
            ).all():
                if act.name:
                    name_l = act.name.strip().lower()
                    non_extco[name_l] = {"activity_id": act.id, "activity_name": act.name}

        for name_lower, shape_id in extco_by_name.items():
            if name_lower in non_extco:
                info = non_extco[name_lower]
                matched.setdefault(shape_id, []).append({
                    "entity_id":    entity.id,
                    "entity_name":  entity.name,
                    "activity_id":  info["activity_id"],
                    "activity_name": info["activity_name"],
                })

    # Lookup DB activity IDs pour les formes extco de la carto active
    extco_shape_ids = [str(s['id']) for s in extco_shapes]
    extco_acts = Activities.query.filter(
        Activities.entity_id == active_entity_id,
        Activities.shape_id.in_(extco_shape_ids)
    ).all()
    extco_activity_map = {act.shape_id: act.id for act in extco_acts}

    matches = []
    for s in extco_shapes:
        sid = str(s['id'])
        if sid in matched:
            matches.append({
                "shape_id":       sid,
                "activity_id":    extco_activity_map.get(sid),   # DB ID pour officialisation
                "activity_name":  (s.get('label') or '').strip(),
                "matched_entities": matched[sid],
            })

    return jsonify({
        "matches": matches,
        "active_entity_id": active_entity_id,
        "total": len(matches)
    }), 200


@activities_map_bp.route("/api/liaison_matches", methods=["GET"])
def liaison_matches():
    """
    Pour une activité hachurée (donnée par son nom), trouve dans toutes les autres
    cartos de l'user les activités avec le même nom qui NE SONT PAS hachurées.
    Retourne : [{ entity_id, entity_name, activity_id, activity_name }]
    """
    name      = (request.args.get('name') or '').strip().lower()
    user_id   = session.get('user_id')
    active_id = get_active_entity_id()

    if not name or not user_id:
        return jsonify({"matches": [], "total": 0}), 200

    other_entities = Entity.query.filter(
        Entity.owner_id == user_id,
        Entity.id != active_id
    ).all()

    # Une seule entrée par entité même si plusieurs activités du même nom
    # existent (renvoi + activité réelle partagent le même nom dans la carto).
    matches = []
    for entity in other_entities:
        act = Activities.query.filter(
            Activities.entity_id == entity.id,
            db.func.lower(Activities.name) == name,
            db.or_(
                Activities.shape_subtype.is_(None),
                Activities.shape_subtype.notin_(['external', 'extco']),
            )
        ).first()
        if act:
            # Check if liaison already officialized
            extco_act = Activities.query.filter(
                Activities.entity_id == active_id,
                db.func.lower(Activities.name) == name,
                Activities.shape_subtype == 'extco'
            ).first()
            existing_liaison = None
            if extco_act:
                existing_liaison = CrossCartoLiaison.query.filter_by(
                    extco_entity_id=active_id,
                    extco_activity_id=extco_act.id,
                    origin_entity_id=entity.id,
                    origin_activity_id=act.id,
                    is_active=True
                ).first()
            matches.append({
                "entity_id":          entity.id,
                "entity_name":        entity.name,
                "activity_id":        act.id,
                "activity_name":      act.name,
                "has_active_liaison": existing_liaison is not None,
                "display_label":      existing_liaison.display_label if existing_liaison else None,
                "liaison_id":         existing_liaison.id if existing_liaison else None,
            })

    return jsonify({"matches": matches, "total": len(matches)}), 200


@activities_map_bp.route("/api/reverse_liaisons_map", methods=["GET"])
def reverse_liaisons_map():
    """Retourne toutes les activités de l'entité active qui sont des origines dans des liaisons.
    Format: {origins: [{origin_activity_name, liaisons: [{entity_id, entity_name, activity_name, extco_shape_id}]}]}"""
    user_id   = session.get('user_id')
    active_id = get_active_entity_id()

    if not user_id or not active_id:
        return jsonify({"origins": []}), 200

    # Find all liaisons where the active entity is the origin
    liaisons = CrossCartoLiaison.query.filter_by(
        origin_entity_id=active_id,
        is_active=True
    ).all()

    if not liaisons:
        return jsonify({"origins": []}), 200

    # Group by origin activity
    from collections import defaultdict
    by_origin = defaultdict(list)
    for liaison in liaisons:
        extco_entity = Entity.query.filter_by(id=liaison.extco_entity_id, owner_id=user_id).first()
        extco_act    = Activities.query.get(liaison.extco_activity_id)
        origin_act   = Activities.query.get(liaison.origin_activity_id)
        if extco_entity and extco_act and origin_act:
            by_origin[origin_act.name].append({
                "entity_id":      extco_entity.id,
                "entity_name":    extco_entity.name,
                "activity_name":  extco_act.name,
                "extco_shape_id": extco_act.shape_id,
                "liaison_id":     liaison.id,
            })

    origins = [
        {"origin_activity_name": name, "liaisons": liaisons_list}
        for name, liaisons_list in by_origin.items()
    ]

    return jsonify({"origins": origins}), 200


@activities_map_bp.route("/api/reverse_liaisons", methods=["GET"])
def reverse_liaisons():
    """Pour une activité d'origine (par nom), retourne les liaisons inverses
    où cette activité est l'origine référencée par une activité hachurée d'une autre carto."""
    name      = (request.args.get('name') or '').strip().lower()
    user_id   = session.get('user_id')
    active_id = get_active_entity_id()

    if not name or not user_id or not active_id:
        return jsonify({"matches": [], "total": 0}), 200

    origin_act = Activities.query.filter(
        Activities.entity_id == active_id,
        db.func.lower(Activities.name) == name,
        db.or_(
            Activities.shape_subtype.is_(None),
            Activities.shape_subtype.notin_(['external', 'extco'])
        )
    ).first()

    if not origin_act:
        return jsonify({"matches": [], "total": 0}), 200

    liaisons = CrossCartoLiaison.query.filter_by(
        origin_activity_id=origin_act.id,
        is_active=True
    ).all()

    matches = []
    for liaison in liaisons:
        extco_entity = Entity.query.filter_by(id=liaison.extco_entity_id, owner_id=user_id).first()
        extco_act    = Activities.query.get(liaison.extco_activity_id)
        if extco_entity and extco_act:
            matches.append({
                "entity_id":       extco_entity.id,
                "entity_name":     extco_entity.name,
                "activity_id":     extco_act.id,
                "activity_name":   extco_act.name,
                "extco_shape_id":  extco_act.shape_id,
                "liaison_id":      liaison.id,
                "display_label":   liaison.display_label,
            })

    return jsonify({"matches": matches}), 200


@activities_map_bp.route("/api/officialize_liaison", methods=["POST"])
def officialize_liaison():
    """Officialise une liaison entre une activité hachurée (extco) et son original.
    Propage les connexions de l'extco vers l'activité d'origine."""
    user_id = session.get("user_id")
    active_entity_id = get_active_entity_id()
    if not user_id or not active_entity_id:
        return jsonify({"error": "Non autorisé"}), 403

    data = request.get_json(force=True) or {}
    extco_activity_id = data.get("extco_activity_id")
    origin_entity_id = data.get("origin_entity_id")
    origin_activity_id = data.get("origin_activity_id")
    display_label = data.get("display_label") or None

    if not extco_activity_id or not origin_entity_id or not origin_activity_id:
        return jsonify({"error": "Paramètres manquants"}), 400

    extco_act = Activities.query.filter_by(id=extco_activity_id, entity_id=active_entity_id).first()
    if not extco_act:
        return jsonify({"error": "Activité hachurée introuvable"}), 404

    origin_entity = Entity.query.filter_by(id=origin_entity_id, owner_id=user_id).first()
    if not origin_entity:
        return jsonify({"error": "Entité d'origine introuvable"}), 404

    origin_act = Activities.query.filter_by(id=origin_activity_id, entity_id=origin_entity_id).first()
    if not origin_act:
        return jsonify({"error": "Activité d'origine introuvable"}), 404

    existing = CrossCartoLiaison.query.filter_by(
        extco_entity_id=active_entity_id,
        extco_activity_id=extco_activity_id,
        origin_entity_id=origin_entity_id,
        origin_activity_id=origin_activity_id,
        is_active=True
    ).first()
    if existing:
        return jsonify({"ok": True, "message": "Liaison déjà officialisée", "already_exists": True}), 200

    liaison = CrossCartoLiaison(
        extco_entity_id=active_entity_id,
        extco_activity_id=extco_activity_id,
        origin_entity_id=origin_entity_id,
        origin_activity_id=origin_activity_id,
        is_active=True,
        display_label=display_label,
    )
    db.session.add(liaison)
    db.session.flush()

    active_entity = Entity.query.get(active_entity_id)
    active_entity_name = active_entity.name if active_entity else "Entité liée"

    extco_links = Link.query.filter(
        Link.entity_id == active_entity_id,
        or_(
            Link.source_activity_id == extco_activity_id,
            Link.target_activity_id == extco_activity_id
        ),
        Link.cross_carto_liaison_id.is_(None)
    ).all()

    act_ids = set()
    for lk in extco_links:
        if lk.source_activity_id and lk.source_activity_id != extco_activity_id:
            act_ids.add(lk.source_activity_id)
        if lk.target_activity_id and lk.target_activity_id != extco_activity_id:
            act_ids.add(lk.target_activity_id)

    act_names = {}
    if act_ids:
        for a in Activities.query.filter(Activities.id.in_(list(act_ids))).all():
            act_names[a.id] = a.name

    created = 0
    for lk in extco_links:
        if lk.source_activity_id == extco_activity_id:
            other_name = act_names.get(lk.target_activity_id, lk.description or "?")
            db.session.add(Link(
                entity_id=origin_entity_id,
                source_activity_id=origin_activity_id,
                target_activity_id=None,
                type=lk.type,
                description=other_name,
                cross_carto_liaison_id=liaison.id,
                cross_carto_label=active_entity_name
            ))
        else:
            other_name = act_names.get(lk.source_activity_id, lk.description or "?")
            db.session.add(Link(
                entity_id=origin_entity_id,
                source_activity_id=None,
                target_activity_id=origin_activity_id,
                type=lk.type,
                description=other_name,
                cross_carto_liaison_id=liaison.id,
                cross_carto_label=active_entity_name
            ))
        created += 1

    db.session.commit()

    # Injecter les formes liées dans l'OptiqCarto de l'entité d'origine
    _inject_extco_shapes_in_origin_carto(
        origin_entity=origin_entity,
        origin_act=origin_act,
        extco_links=extco_links,
        extco_activity_id=extco_activity_id,
        act_names=act_names,
        source_label=active_entity_name,
        active_entity=active_entity,
    )

    return jsonify({"ok": True, "links_created": created}), 200


@activities_map_bp.route("/api/liaison_deoffice_preview", methods=["GET"])
def liaison_deoffice_preview():
    """Aperçu de ce qui sera supprimé lors de la dé-officialisation d'une liaison."""
    user_id    = session.get("user_id")
    liaison_id = request.args.get("liaison_id", type=int)
    if not user_id or not liaison_id:
        return jsonify({"error": "Paramètres manquants"}), 400

    liaison = CrossCartoLiaison.query.get(liaison_id)
    if not liaison:
        return jsonify({"error": "Liaison introuvable"}), 404

    origin_entity = Entity.query.filter_by(id=liaison.origin_entity_id, owner_id=user_id).first()
    extco_entity  = Entity.query.filter_by(id=liaison.extco_entity_id, owner_id=user_id).first()
    if not origin_entity or not extco_entity:
        return jsonify({"error": "Non autorisé"}), 403

    shapes_to_remove, conns_to_remove = [], 0
    if origin_entity.optiqcarto_data:
        try:
            carto = json.loads(origin_entity.optiqcarto_data)
            source_label = extco_entity.name
            removed_ids = {
                s.get('id') for s in carto.get('shapes', [])
                if s.get('crossCartoImport') and s.get('crossCartoSource') == source_label
            }
            for s in carto.get('shapes', []):
                if s.get('id') in removed_ids:
                    shapes_to_remove.append(s.get('label') or '?')
            conns_to_remove = sum(
                1 for c in carto.get('connections', [])
                if c.get('fromId') in removed_ids or c.get('toId') in removed_ids
            )
        except Exception:
            pass

    db_links_count = Link.query.filter_by(cross_carto_liaison_id=liaison_id).count()

    return jsonify({
        "origin_entity_name":  origin_entity.name,
        "extco_entity_name":   extco_entity.name,
        "shapes_to_remove":    shapes_to_remove,
        "connections_to_remove": conns_to_remove,
        "db_links_to_remove":  db_links_count,
    }), 200


@activities_map_bp.route("/api/liaison_deoffice", methods=["POST"])
def liaison_deoffice():
    """Dé-officialise une liaison : supprime formes injectées + liens DB + enregistrement liaison."""
    user_id = session.get("user_id")
    data = request.get_json(force=True) or {}
    liaison_id = data.get("liaison_id")
    if not user_id or not liaison_id:
        return jsonify({"error": "Paramètres manquants"}), 400

    liaison = CrossCartoLiaison.query.get(liaison_id)
    if not liaison:
        return jsonify({"error": "Liaison introuvable"}), 404

    origin_entity = Entity.query.filter_by(id=liaison.origin_entity_id, owner_id=user_id).first()
    extco_entity  = Entity.query.filter_by(id=liaison.extco_entity_id, owner_id=user_id).first()
    if not origin_entity or not extco_entity:
        return jsonify({"error": "Non autorisé"}), 403

    # 1. Supprimer les formes injectées dans la carto d'origine
    if origin_entity.optiqcarto_data:
        try:
            carto = json.loads(origin_entity.optiqcarto_data)
            _cleanup_extco_injections(carto, extco_entity.name)
            origin_entity.optiqcarto_data = json.dumps(carto, ensure_ascii=False)
            flag_modified(origin_entity, 'optiqcarto_data')
        except Exception:
            pass

    # 2. Supprimer les liens DB propagés
    Link.query.filter_by(cross_carto_liaison_id=liaison_id).delete(synchronize_session=False)

    # 3. Supprimer l'enregistrement liaison
    db.session.delete(liaison)
    db.session.commit()

    return jsonify({"ok": True}), 200


def _cleanup_extco_injections(carto: dict, source_label: str) -> set:
    """Supprime les formes injectées cross-carto (crossCartoImport=True, crossCartoSource==source_label)
    et leurs connexions. Retourne les IDs des formes supprimées."""
    shapes      = carto.get('shapes', [])
    connections = carto.get('connections', [])
    removed_ids = {
        s.get('id')
        for s in shapes
        if s.get('crossCartoImport') and s.get('crossCartoSource') == source_label
    }
    if removed_ids:
        carto['shapes']      = [s for s in shapes if s.get('id') not in removed_ids]
        carto['connections'] = [
            c for c in connections
            if c.get('fromId') not in removed_ids and c.get('toId') not in removed_ids
        ]
    return removed_ids


def _inject_extco_shapes_in_origin_carto(
    origin_entity, origin_act, extco_links, extco_activity_id, act_names, source_label,
    active_entity=None,
):
    """Injecte dans la carto d'origine les formes liées à l'activité extco officialisée.

    - Choisit les côtés libres sur l'activité d'origine (évite les côtés déjà câblés)
    - Détecte les collisions et décale les formes pour éviter tout chevauchement
    - Copie type/couleur/taille depuis la carto source ; textColor blanc, fontSize correct
    - Label de flèche = label original de la connexion source (pas le nom d'entité)
    - crossCartoSource = source_label → rendu comme sous-label italique dans l'éditeur
    """
    try:
        carto_raw = origin_entity.optiqcarto_data
        if not carto_raw:
            return

        carto = json.loads(carto_raw) if isinstance(carto_raw, str) else carto_raw
        _cleanup_extco_injections(carto, source_label)   # retire les anciennes formes injectées
        shapes      = list(carto.get('shapes', []))
        connections = list(carto.get('connections', []))
        next_id     = int(carto.get('nextId', 1000))

        # Trouver la forme d'origine
        origin_sid   = str(origin_act.shape_id) if origin_act.shape_id else None
        origin_shape = next(
            (s for s in shapes if str(s.get('id', '')) == origin_sid), None
        ) if origin_sid else None
        if not origin_shape:
            return

        ox  = float(origin_shape.get('x', 100))
        oy  = float(origin_shape.get('y', 100))
        ow  = float(origin_shape.get('w', 160))
        oh  = float(origin_shape.get('h', 60))
        origin_raw_id = origin_shape.get('id')
        oid_str = str(origin_raw_id)

        # Charger la carto source pour copier propriétés des formes et labels connexions
        source_shapes_by_sid = {}
        source_conn_labels   = {}   # (from_sid_str, to_sid_str) → label
        extco_source_sid     = None

        if active_entity and active_entity.optiqcarto_data:
            try:
                src = json.loads(active_entity.optiqcarto_data)
                for s in src.get('shapes', []):
                    source_shapes_by_sid[str(s.get('id', ''))] = s
                for c in src.get('connections', []):
                    fid = str(c.get('fromId', ''))
                    tid = str(c.get('toId', ''))
                    source_conn_labels[(fid, tid)] = c.get('label', '') or ''
            except Exception:
                pass

        extco_act_obj = Activities.query.filter_by(id=extco_activity_id).first()
        if extco_act_obj and extco_act_obj.shape_id:
            extco_source_sid = str(extco_act_obj.shape_id)

        # Map activity_id → source carto shape_id (str)
        other_ids = set()
        for lk in extco_links:
            if lk.source_activity_id and lk.source_activity_id != extco_activity_id:
                other_ids.add(lk.source_activity_id)
            if lk.target_activity_id and lk.target_activity_id != extco_activity_id:
                other_ids.add(lk.target_activity_id)

        act_shape_sid = {}
        if other_ids:
            for act in Activities.query.filter(Activities.id.in_(list(other_ids))).all():
                if act.shape_id:
                    act_shape_sid[act.id] = str(act.shape_id)

        # ── Déterminer les côtés déjà utilisés sur l'activité d'origine ──────
        shapes_by_id = {str(s.get('id', '')): s for s in shapes}

        def _direction_side(dx, dy):
            """Côté de sortie sur la base du vecteur directionnel."""
            if abs(dx) >= abs(dy):
                return 'right' if dx >= 0 else 'left'
            return 'bottom' if dy >= 0 else 'top'

        OPP = {'left': 'right', 'right': 'left', 'top': 'bottom', 'bottom': 'top'}
        used_in_sides  = set()   # côtés d'entrée déjà utilisés sur origin
        used_out_sides = set()   # côtés de sortie déjà utilisés sur origin

        for c in connections:
            fid = str(c.get('fromId', '')); tid = str(c.get('toId', ''))
            if tid == oid_str:
                src_s = shapes_by_id.get(fid)
                if src_s:
                    dx = (ox+ow/2) - (float(src_s.get('x',0)) + float(src_s.get('w',0))/2)
                    dy = (oy+oh/2) - (float(src_s.get('y',0)) + float(src_s.get('h',0))/2)
                    used_in_sides.add(OPP[_direction_side(dx, dy)])
            elif fid == oid_str:
                tgt_s = shapes_by_id.get(tid)
                if tgt_s:
                    dx = (float(tgt_s.get('x',0)) + float(tgt_s.get('w',0))/2) - (ox+ow/2)
                    dy = (float(tgt_s.get('y',0)) + float(tgt_s.get('h',0))/2) - (oy+oh/2)
                    used_out_sides.add(_direction_side(dx, dy))

        def _choose_side(used, priority):
            for s in priority:
                if s not in used:
                    return s
            return priority[0]

        in_side  = _choose_side(used_in_sides,  ['left', 'top', 'bottom', 'right'])
        out_side = _choose_side(used_out_sides, ['right', 'top', 'bottom', 'left'])
        # Éviter que in_side == out_side (confusion visuelle)
        if in_side == out_side:
            alt_in = [s for s in ['left', 'top', 'bottom', 'right'] if s != out_side]
            in_side = alt_in[0]

        # ── Collision detection ───────────────────────────────────────────────
        # Buffer pour les formes déjà présentes + nouvelles ajoutées au fur et à mesure
        # On ajoute +26px de hauteur pour le sous-label italique en bas des formes extco
        all_for_coll = [
            {'x': s.get('x',0), 'y': s.get('y',0),
             'w': s.get('w',0),
             'h': float(s.get('h',0)) + (26 if s.get('subtype') == 'extco' else 0)}
            for s in shapes
        ]

        def _overlaps(ax, ay, aw, ah, margin=14):
            r1x2, r1y2 = ax + aw + margin, ay + ah + 26 + margin  # +26 pour sous-label
            for s in all_for_coll:
                if (ax - margin < float(s['x']) + float(s['w']) and
                    r1x2 > float(s['x']) - margin and
                    ay - margin < float(s['y']) + float(s['h']) and
                    r1y2 > float(s['y']) - margin):
                    return True
            return False

        def _nudge_free(base_x, base_y, sw, sh, side):
            """Décale progressivement le long de l'axe perpendiculaire au côté."""
            x, y = base_x, base_y
            step = sh + 40 if side in ('left', 'right') else sw + 40
            for attempt in range(24):
                if not _overlaps(x, y, sw, sh):
                    return x, y
                delta = (attempt // 2 + 1) * step
                sign  = 1 if attempt % 2 == 0 else -1
                if side in ('left', 'right'):
                    y = base_y + sign * delta
                else:
                    x = base_x + sign * delta
            return base_x, base_y

        MARGIN_H, MARGIN_V = 110, 80

        def _base_xy(side, slot, n, sw, sh):
            GAP = 40   # espacement entre slots (plus grand pour éviter chevauchements labels)
            if side == 'left':
                bx = ox - sw - MARGIN_H
                by = oy + oh/2 - (n*(sh+GAP)-GAP)/2 + slot*(sh+GAP)
            elif side == 'right':
                bx = ox + ow + MARGIN_H
                by = oy + oh/2 - (n*(sh+GAP)-GAP)/2 + slot*(sh+GAP)
            elif side == 'top':
                bx = ox + ow/2 - (n*(sw+GAP)-GAP)/2 + slot*(sw+GAP)
                by = oy - sh - MARGIN_V
            else:  # bottom
                bx = ox + ow/2 - (n*(sw+GAP)-GAP)/2 + slot*(sw+GAP)
                by = oy + oh + MARGIN_V
            return bx, by

        existing_labels = {s.get('label', '').strip().lower() for s in shapes}
        new_shapes_list, new_conns_list = [], []

        def _process_group(group_links, side, is_incoming):
            nonlocal next_id
            filtered = []
            for lk in group_links:
                aid  = lk.source_activity_id if is_incoming else lk.target_activity_id
                name = (act_names.get(aid) or '').strip()
                if name and name.lower() not in existing_labels:
                    filtered.append((lk, aid, name))

            n = len(filtered)
            for slot, (lk, aid, other_name) in enumerate(filtered):
                sid_str = act_shape_sid.get(aid, '')
                src_shp = source_shapes_by_sid.get(sid_str, {})
                sw = float(src_shp.get('w', ow))
                sh = float(src_shp.get('h', oh))

                bx, by = _base_xy(side, slot, n, sw, sh)
                fx, fy = _nudge_free(bx, by, sw, sh, side)

                new_sid = next_id; next_id += 1

                shape = {
                    'id':             new_sid,
                    'type':           src_shp.get('type', 'process'),
                    'subtype':        'extco',
                    'label':          other_name,
                    'x': fx, 'y': fy,
                    'w': sw, 'h': sh,
                    'color':          src_shp.get('color', '#94a3b8'),
                    'textColor':      '#ffffff',
                    'fontSize':       float(src_shp.get('fontSize', 18)),
                    'strokeColor':    src_shp.get('strokeColor', ''),
                    'validationBadge': False,
                    'validationColor': '#4DB868',
                    'colorVariant':   0,
                    'crossCartoImport': True,
                    'crossCartoSource': source_label,
                }
                existing_labels.add(other_name.lower())
                all_for_coll.append({'x': fx, 'y': fy, 'w': sw, 'h': sh + 26})
                new_shapes_list.append(shape)

                # Label de la flèche = label original depuis la carto source
                if is_incoming:
                    src_key = (sid_str, extco_source_sid) if extco_source_sid else None
                else:
                    src_key = (extco_source_sid, sid_str) if extco_source_sid else None
                conn_label = (source_conn_labels.get(src_key) if src_key else None) or (lk.description or None)

                cid = next_id; next_id += 1
                from_id = new_sid      if is_incoming else origin_raw_id
                to_id   = origin_raw_id if is_incoming else new_sid
                new_conns_list.append({
                    'id':      cid,
                    'fromId':  from_id,
                    'toId':    to_id,
                    'label':   conn_label,
                    'color':   '#64748b',
                    'style':   'dashed',
                    'routing': 'smooth',
                })

        incoming_lks = [lk for lk in extco_links
                        if lk.target_activity_id == extco_activity_id and lk.source_activity_id]
        outgoing_lks = [lk for lk in extco_links
                        if lk.source_activity_id == extco_activity_id and lk.target_activity_id]

        _process_group(incoming_lks, in_side,  is_incoming=True)
        _process_group(outgoing_lks, out_side, is_incoming=False)

        if not new_shapes_list:
            return

        carto['shapes']      = shapes + new_shapes_list
        carto['connections'] = connections + new_conns_list
        carto['nextId']      = next_id
        origin_entity.optiqcarto_data = json.dumps(carto, ensure_ascii=False)
        flag_modified(origin_entity, 'optiqcarto_data')
        db.session.commit()

    except Exception:
        pass


# ============================================================
# DEBUG DÉCISIONS — Comparaison VSDX / Outil / IA
# ============================================================

def _tool_decisions_from_entity(entity) -> Dict:
    """
    Extracts decision nodes + their connections from:
    1. entity.optiqcarto_data JSON (shapes + connections)
    2. DB Link records with choice_label
    Returns {decisions: [...], total_shapes, total_connections}
    """
    import json

    decisions = []
    total_shapes = 0
    total_connections = 0

    # ── Source 1 : OptiqCarto JSON ──────────────────────────────
    if entity.optiqcarto_data:
        try:
            carto = json.loads(entity.optiqcarto_data)
        except (ValueError, TypeError):
            carto = {}

        shapes = carto.get('shapes', [])
        connections = carto.get('connections', [])
        total_shapes = len(shapes)
        total_connections = len(connections)

        shape_by_id = {s['id']: s for s in shapes}
        decision_ids = {s['id'] for s in shapes if s.get('_type') == 'decision'}

        for did in decision_ids:
            shape = shape_by_id[did]
            outgoing = []
            incoming = []
            for c in connections:
                if c.get('fromId') == did:
                    tgt = shape_by_id.get(c.get('toId'), {})
                    outgoing.append({
                        'conn_id': c.get('id', ''),
                        'to_id': c.get('toId', ''),
                        'to_label': tgt.get('label', ''),
                        'conn_label': c.get('label', ''),
                        'badge': c.get('label', '') or '',
                    })
                elif c.get('toId') == did:
                    src = shape_by_id.get(c.get('fromId'), {})
                    incoming.append({
                        'conn_id': c.get('id', ''),
                        'from_id': c.get('fromId', ''),
                        'from_label': src.get('label', ''),
                        'conn_label': c.get('label', ''),
                        'badge': '',
                    })
            decisions.append({
                'id': did,
                'label': shape.get('label', ''),
                'outgoing': outgoing,
                'incoming': incoming,
            })

    # ── Source 2 : DB Links (choice_label) ─────────────────────
    db_links = Link.query.filter_by(entity_id=entity.id).all()
    acts = {a.id: a.name for a in Activities.query.filter_by(entity_id=entity.id).all()}

    # Find decisions that appear in DB via choice_label
    decision_act_ids = set()
    for lk in db_links:
        if lk.choice_label:
            decision_act_ids.add(lk.source_activity_id)

    for act_id in decision_act_ids:
        act_name = acts.get(act_id, f'act#{act_id}')
        outgoing = []
        for lk in db_links:
            if lk.source_activity_id == act_id and lk.choice_label:
                tgt_name = acts.get(lk.target_activity_id, '')
                outgoing.append({
                    'conn_id': f'db_{lk.id}',
                    'to_id': str(lk.target_activity_id or ''),
                    'to_label': tgt_name,
                    'conn_label': lk.description or '',
                    'badge': lk.choice_label or '',
                })
        # Only add if not already tracked from optiqcarto_data
        existing_labels = [d['label'] for d in decisions]
        if act_name not in existing_labels:
            decisions.append({
                'id': f'db_{act_id}',
                'label': act_name,
                'source': 'db',
                'outgoing': outgoing,
                'incoming': [],
            })

    return {
        'decisions': decisions,
        'total_shapes': total_shapes,
        'total_connections': total_connections,
    }


def _read_vsdx_page_xml(vsdx_path: str) -> str:
    """Returns the first page XML content from a VSDX archive."""
    import zipfile as _zf
    with _zf.ZipFile(vsdx_path, 'r') as zf:
        page_files = sorted(
            f for f in zf.namelist()
            if f.startswith('visio/pages/page') and f.endswith('.xml')
        )
        if not page_files:
            raise ValueError('Aucune page dans le VSDX')
        return zf.read(page_files[0]).decode('utf-8', errors='replace')


def _ai_extract_decisions(vsdx_result: Dict, context_name: str = '') -> Dict:
    """
    Envoie un résumé compact des losanges déjà extraits à OpenAI pour validation.
    Plus fiable que le XML brut car compact et structuré.
    """
    import json as _json

    decisions = vsdx_result.get('decisions', [])

    # Résumé compact lisible par l'IA
    lines = [
        f"Fichier : {context_name}",
        f"Total shapes : {vsdx_result.get('total_shapes', 0)}  |  "
        f"Total connecteurs : {vsdx_result.get('total_connectors', 0)}",
        f"Losanges détectés algorithmiquement : {len(decisions)}",
        "",
    ]
    for d in decisions:
        label = d.get('label') or '(sans label)'
        master = d.get('master_name', '?')
        splice = ' [splice]' if d.get('splice') else ''
        lines.append(f'• ID {d["id"]} "{label}" [{master}]{splice}')
        for c in d.get('incoming', []):
            lines.append(f'    ← "{c.get("from_label", "?")}"')
        for c in d.get('outgoing', []):
            badge = f' [badge:{c["badge"]}]' if c.get('badge') else ''
            lines.append(f'    → "{c.get("to_label", "?")}"{badge}')

    summary = '\n'.join(lines)

    system_prompt = (
        "Tu es un expert en analyse de diagrammes de flux Visio. "
        "On te soumet les losanges extraits automatiquement d'un fichier VSDX. "
        "Ta mission : valider et restituer fidèlement ces données — sans rien inventer.\n\n"
        "RÈGLES STRICTES :\n"
        "- Conserve exactement les labels et connexions fournis, sans les modifier.\n"
        "- Ne déduis PAS de badges Oui/Non : mets badge='' pour toutes les connexions "
        "sauf si un badge est explicitement indiqué dans les données d'entrée (ex: [badge:Oui]).\n"
        "- Ne crée pas de connexions absentes des données d'entrée.\n"
        "- Si les données sont correctes, retourne-les telles quelles.\n\n"
        "Réponds UNIQUEMENT en JSON valide, sans texte avant ni après :\n"
        '{"decisions": [{"id": "...", "label": "...", '
        '"incoming": [{"from_id": "", "from_label": ""}], '
        '"outgoing": [{"to_id": "", "to_label": "", "badge": ""}]}]}'
    )

    client, err = openai_client_or_none()
    if not client:
        return {"source": "error", "error": err, "data": {"decisions": []}}

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_CHATBOT_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": summary},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return {"source": "openai", "data": _json.loads(m.group(0))}
        return {"source": "openai", "data": {"decisions": []}, "raw": raw}
    except Exception as e:
        return {"source": "error", "error": str(e), "data": {"decisions": []}}

@activities_map_bp.route("/api/debug-decisions/env-check", methods=["GET"])
def api_debug_env_check():
    """Diagnostic temporaire — liste les noms des vars d'env disponibles."""
    import os as _os
    keys = sorted(_os.environ.keys())
    openai_key = _os.environ.get("OPENAI_API_KEY", "")
    return jsonify({
        "openai_api_key_present": bool(openai_key),
        "openai_api_key_prefix": openai_key[:8] + "..." if openai_key else None,
        "all_env_var_names": keys,
    })


@activities_map_bp.route("/api/debug-decisions/analyze-file", methods=["POST"])
def api_debug_analyze_file():
    """
    Accepts a VSDX file upload (multipart field 'vsdx').
    Returns raw VSDX extraction result.
    The 'tool' result is computed in the browser via VsdxImporter.
    The 'ai' result is fetched separately via /analyze-file/ai.
    """
    vsdx_file = request.files.get('vsdx')
    if not vsdx_file or not vsdx_file.filename:
        return jsonify({"error": "Aucun fichier fourni"}), 400
    if not vsdx_file.filename.lower().endswith('.vsdx'):
        return jsonify({"error": "Le fichier doit être un .vsdx"}), 400

    with tempfile.NamedTemporaryFile(suffix='.vsdx', delete=False) as tmp:
        vsdx_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        vsdx_data = extract_decisions_from_vsdx(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return jsonify({"vsdx": vsdx_data})


@activities_map_bp.route("/api/debug-decisions/analyze-file/ai", methods=["POST"])
def api_debug_analyze_file_ai():
    """
    Accepts a VSDX file upload (multipart field 'vsdx').
    Sends the first page XML to Claude/OpenAI for decision extraction.
    """
    vsdx_file = request.files.get('vsdx')
    if not vsdx_file or not vsdx_file.filename:
        return jsonify({"error": "Aucun fichier fourni"}), 400
    if not vsdx_file.filename.lower().endswith('.vsdx'):
        return jsonify({"error": "Le fichier doit être un .vsdx"}), 400

    with tempfile.NamedTemporaryFile(suffix='.vsdx', delete=False) as tmp:
        vsdx_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        vsdx_result = extract_decisions_from_vsdx(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    result = _ai_extract_decisions(vsdx_result, vsdx_file.filename)
    return jsonify(result)


# Keep old entity-based endpoints for backward compatibility
@activities_map_bp.route("/api/debug-decisions", methods=["GET"])
def api_debug_decisions():
    """Legacy: VSDX-extracted decisions from entity's stored file."""
    entity = get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    vsdx_data: Dict = {'decisions': [], 'total_shapes': 0, 'total_connectors': 0, 'errors': []}
    vsdx_exists, vsdx_path = check_vsdx_exists(entity.id)
    if vsdx_exists and os.path.exists(vsdx_path):
        vsdx_data = extract_decisions_from_vsdx(vsdx_path)

    return jsonify({
        "entity_id": entity.id,
        "entity_name": entity.name,
        "has_vsdx": vsdx_exists and os.path.exists(vsdx_path),
        "vsdx": vsdx_data,
    })


@activities_map_bp.route("/api/debug-decisions/ai", methods=["POST"])
def api_debug_decisions_ai():
    """Legacy: AI analysis of entity's stored VSDX."""
    import json as _json

    entity = get_active_entity()
    if not entity:
        return jsonify({"error": "Aucune entité active"}), 400

    vsdx_exists, vsdx_path = check_vsdx_exists(entity.id)
    if not vsdx_exists or not os.path.exists(vsdx_path):
        return jsonify({"error": "Pas de fichier VSDX pour cette entité"}), 404

    try:
        xml_content = _read_vsdx_page_xml(vsdx_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    result = _ai_extract_decisions(xml_content, entity.name)
    return jsonify(result)



    return jsonify({"error": "Aucune clé IA configurée (ANTHROPIC_KEY ou OPENAI_API_KEY)"}), 503
