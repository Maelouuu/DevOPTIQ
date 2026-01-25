# Code/routes/activities_map.py
"""
Cartographie des activités avec gestion multi-entités.
Import des connexions depuis fichiers VSDX.
WIZARD UNIFIÉ SVG + VSDX.
"""
import os
import shutil
import xml.etree.ElementTree as ET
import tempfile

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    send_file,
    session
)

from Code.extensions import db
from Code.models.models import Activities, Entity, Link, Data

from Code.routes.vsdx_conection_parser import (
    parse_vsdx_connections,
    validate_connections_against_activities
)


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
    """Vérifie si un SVG existe pour l'entité."""
    svg_path = get_entity_svg_path(entity_id)
    if os.path.exists(svg_path):
        return True, svg_path
    # Ne plus utiliser le fallback OLD_SVG_PATH pour éviter d'afficher la mauvaise cartographie
    return False, None


def check_vsdx_exists(entity_id):
    """Vérifie si un VSDX existe pour l'entité."""
    vsdx_path = get_entity_vsdx_path(entity_id)
    return os.path.exists(vsdx_path), vsdx_path


def get_active_entity():
    """Récupère l'entité active depuis la session."""
    entity_id = session.get('active_entity_id')
    if not entity_id:
        return None
    return Entity.query.get(entity_id)


def get_active_entity_id():
    """Récupère l'ID de l'entité active depuis la session."""
    return session.get('active_entity_id')


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
            # Utiliser le nom stocké en base ou le nom par défaut
            current_vsdx = getattr(active_entity, 'vsdx_filename', None) or "connections.vsdx"
        
        # Log pour debug
        print(f"[CARTO] Entité {active_entity.id}: SVG={svg_exists} ({svg_path}), VSDX={vsdx_exists}")
        
        activities = Activities.query.filter_by(
            entity_id=active_entity.id
        ).order_by(Activities.id).all()
        
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
                "vsdx_filename": getattr(e, 'vsdx_filename', None),
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
            "vsdx_filename": getattr(active_entity, 'vsdx_filename', None),
            "is_active": True
        }
    
    return render_template(
        "activities_map.html",
        svg_exists=svg_exists,
        vsdx_exists=vsdx_exists,
        current_svg=current_svg,
        current_vsdx=current_vsdx,
        shape_activity_map=shape_activity_map,
        activities=activities,
        active_entity=active_entity_dict,
        all_entities=all_entities
    )


# ============================================================
# SERVIR LE SVG DE L'ENTITÉ ACTIVE
# ============================================================
@activities_map_bp.route("/svg")
def serve_svg():
    """Sert le fichier SVG de l'entité active."""
    active_entity = get_active_entity()
    
    if not active_entity:
        return jsonify({"error": "Aucune entité active"}), 404
    
    svg_exists, svg_path = check_svg_exists(active_entity.id)
    
    if not svg_exists or not svg_path:
        print(f"[CARTO] SVG non trouvé pour l'entité {active_entity.id}")
        return jsonify({"error": "SVG non trouvé pour cette entité"}), 404

    print(f"[CARTO] Serving SVG pour entité {active_entity.id}: {svg_path}")
    print(f"[CARTO] Nombre d'activités de cette entité: {Activities.query.filter_by(entity_id=active_entity.id).count()}")
    
    return send_file(
        svg_path, 
        mimetype='image/svg+xml',
        max_age=0
    )


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
        svg_exists, _ = check_svg_exists(e.id)
        vsdx_exists, _ = check_vsdx_exists(e.id)
        result.append({
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "svg_filename": e.svg_filename,
            "vsdx_filename": getattr(e, 'vsdx_filename', None),
            "is_active": (e.id == active_entity_id),
            "activities_count": Activities.query.filter_by(entity_id=e.id).count(),
            "svg_exists": svg_exists,
            "vsdx_exists": vsdx_exists
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
        "current_vsdx": getattr(entity, 'vsdx_filename', None) or ("connections.vsdx" if vsdx_exists else None),
        "activities_count": Activities.query.filter_by(entity_id=entity_id).count(),
        "connections_count": Link.query.filter_by(entity_id=entity_id).count()
    })


@activities_map_bp.route("/api/entities", methods=["POST"])
def create_entity():
    data = request.get_json()
    
    if not data or not data.get("name"):
        return jsonify({"error": "Nom requis"}), 400
    
    user_id = session.get('user_id')
    
    entity = Entity(
        name=data["name"],
        description=data.get("description", ""),
        owner_id=user_id,
        is_active=False
    )
    db.session.add(entity)
    db.session.commit()
    
    # Créer le dossier immédiatement
    entity_dir = ensure_entity_dir(entity.id)
    print(f"[CARTO] Nouvelle entité créée: {entity.id} -> {entity_dir}")
    
    return jsonify({
        "status": "ok",
        "entity": {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "is_active": False
        }
    })


@activities_map_bp.route("/api/entities/<int:entity_id>/activate", methods=["POST"])
def activate_entity(entity_id):
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401
    
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    
    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404
    
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
        db.session.delete(entity)
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
            
            # IMPORTANT: Sauvegarder le nom original en base
            entity.svg_filename = svg_file.filename
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
            
            # IMPORTANT: Sauvegarder le nom original en base (si le champ existe)
            if hasattr(entity, 'vsdx_filename'):
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