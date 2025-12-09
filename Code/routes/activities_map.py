# Code/routes/activities_map.py
"""
Cartographie des activités avec gestion multi-entités.
"""
import os
import shutil
import datetime
import re
import xml.etree.ElementTree as ET

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    send_file
)

from Code.extensions import db
from Code.models.models import Activities, Entity


# ============================================================
# Blueprint
# ============================================================
activities_map_bp = Blueprint(
    "activities_map_bp",
    __name__,
    url_prefix="/activities"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
ENTITIES_DIR = os.path.join(STATIC_DIR, "entities")
OLD_SVG_PATH = os.path.join(STATIC_DIR, "img", "carto_activities.svg")


def get_entity_svg_path(entity_id):
    return os.path.join(ENTITIES_DIR, f"entity_{entity_id}", "carto.svg")


def ensure_entity_dir(entity_id):
    entity_dir = os.path.join(ENTITIES_DIR, f"entity_{entity_id}")
    os.makedirs(entity_dir, exist_ok=True)
    return entity_dir


# ============================================================
# PAGE CARTOGRAPHIE
# ============================================================
@activities_map_bp.route("/map")
def activities_map_page():
    active_entity = Entity.get_active()
    
    svg_exists = False
    if active_entity:
        svg_path = get_entity_svg_path(active_entity.id)
        svg_exists = os.path.exists(svg_path)
        if not svg_exists and os.path.exists(OLD_SVG_PATH):
            svg_exists = True
    
    if active_entity:
        rows = Activities.query.filter_by(entity_id=active_entity.id).order_by(Activities.id).all()
    else:
        rows = []
    
    shape_activity_map = {
        str(act.shape_id): act.id
        for act in rows
        if act.shape_id is not None
    }
    
    all_entities = Entity.query.order_by(Entity.name).all()
    
    active_entity_dict = None
    if active_entity:
        active_entity_dict = {
            "id": active_entity.id,
            "name": active_entity.name,
            "description": active_entity.description or "",
            "svg_filename": active_entity.svg_filename,
            "is_active": active_entity.is_active
        }
    
    all_entities_list = [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description or "",
            "svg_filename": e.svg_filename,
            "is_active": e.is_active
        }
        for e in all_entities
    ]
    
    return render_template(
        "activities_map.html",
        svg_exists=svg_exists,
        shape_activity_map=shape_activity_map,
        activities=rows,
        active_entity=active_entity_dict,
        all_entities=all_entities_list
    )


# ============================================================
# SERVIR LE SVG
# ============================================================
@activities_map_bp.route("/svg")
def serve_svg():
    active_entity = Entity.get_active()
    
    if not active_entity:
        return jsonify({"error": "Aucune entité active"}), 404
    
    svg_path = get_entity_svg_path(active_entity.id)
    
    if not os.path.exists(svg_path) and os.path.exists(OLD_SVG_PATH):
        svg_path = OLD_SVG_PATH
    
    if not os.path.exists(svg_path):
        return jsonify({"error": "SVG non trouvé"}), 404
    
    return send_file(svg_path, mimetype='image/svg+xml')


# ============================================================
# API ENTITÉS
# ============================================================
@activities_map_bp.route("/api/entities", methods=["GET"])
def list_entities():
    entities = Entity.query.order_by(Entity.name).all()
    return jsonify([
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "svg_filename": e.svg_filename,
            "is_active": e.is_active,
            "activities_count": Activities.query.filter_by(entity_id=e.id).count()
        }
        for e in entities
    ])


@activities_map_bp.route("/api/entities", methods=["POST"])
def create_entity():
    data = request.get_json()
    
    if not data or not data.get("name"):
        return jsonify({"error": "Nom requis"}), 400
    
    entity = Entity(
        name=data["name"],
        description=data.get("description", ""),
        is_active=False
    )
    db.session.add(entity)
    db.session.commit()
    
    ensure_entity_dir(entity.id)
    
    return jsonify({
        "status": "ok",
        "entity": {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "is_active": entity.is_active
        }
    })


@activities_map_bp.route("/api/entities/<int:entity_id>/activate", methods=["POST"])
def activate_entity(entity_id):
    """Active une entité (désactive les autres)."""
    entity = Entity.query.get(entity_id)
    
    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404
    
    try:
        # IMPORTANT: Ne PAS utiliser Entity.query.update() qui bloque SQLite
        # À la place, on récupère et modifie chaque entité individuellement
        all_entities = Entity.query.all()
        
        for e in all_entities:
            if e.id == entity_id:
                e.is_active = True
            else:
                e.is_active = False
        
        db.session.commit()
        
        return jsonify({
            "status": "ok",
            "message": f"Entité '{entity.name}' activée"
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"[ACTIVATE] Erreur: {e}")
        return jsonify({"error": str(e)}), 500


@activities_map_bp.route("/api/entities/<int:entity_id>", methods=["DELETE"])
def delete_entity(entity_id):
    entity = Entity.query.get(entity_id)
    
    if not entity:
        return jsonify({"error": "Entité non trouvée"}), 404
    
    activities_count = Activities.query.filter_by(entity_id=entity_id).count()
    
    entity_dir = os.path.join(ENTITIES_DIR, f"entity_{entity_id}")
    if os.path.exists(entity_dir):
        shutil.rmtree(entity_dir)
    
    entity_name = entity.name
    
    try:
        db.session.delete(entity)
        db.session.commit()
        
        if not Entity.get_active():
            first = Entity.query.first()
            if first:
                first.is_active = True
                db.session.commit()
        
        return jsonify({
            "status": "ok",
            "message": f"Entité '{entity_name}' supprimée ({activities_count} activités supprimées)"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@activities_map_bp.route("/api/entities/<int:entity_id>", methods=["PATCH"])
def update_entity(entity_id):
    entity = Entity.query.get(entity_id)
    
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
    """
    Parse un fichier SVG Visio et extrait les activités valides.
    
    LOGIQUE:
    - Les VRAIES activités sont sur le layer 1 (v:layerMember="1")
    - Ce sont les rectangles colorés principaux de la cartographie
    - Le nom de l'activité est le TEXTE à l'intérieur de la forme
    
    Layers Visio:
    - Layer 1: Activités principales (rectangles colorés) ✓
    - Layer 2: Noms des swimlanes (légendes)
    - Layer 6: Activités client/fournisseur (flags)
    - Layer 8: Cercles de retour (références)
    - Layer 9: Documents/Résultats (données)
    - Layer 10: Déclencheurs (flags)
    """
    activities = []
    seen_names = set()
    
    print(f"[EXTRACT] Parsing SVG: {svg_path}")
    
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        # Namespaces
        SVG_NS = "http://www.w3.org/2000/svg"
        VISIO_NS = "http://schemas.microsoft.com/visio/2003/SVGExtensions/"
        
        # Chercher tous les éléments avec v:mID
        for elem in root.iter():
            mid = elem.get(f"{{{VISIO_NS}}}mID")
            if not mid:
                continue
            
            # FILTRE PRINCIPAL: Seulement le layer 1 (activités principales)
            layer = elem.get(f"{{{VISIO_NS}}}layerMember", "")
            if layer != "1":
                continue
            
            # Chercher le TEXTE à l'intérieur de l'élément
            text_content = None
            for text_elem in elem.iter(f"{{{SVG_NS}}}text"):
                t = "".join(text_elem.itertext()).strip()
                if t and len(t) > 2:
                    text_content = t
                    break  # Prendre le premier texte significatif
            
            # Si pas de texte, ignorer
            if not text_content:
                continue
            
            # Ignorer les textes trop longs (descriptions)
            if len(text_content) > 80:
                continue
            
            # Éviter les doublons par nom
            if text_content.lower() not in seen_names:
                seen_names.add(text_content.lower())
                activities.append({
                    "shape_id": mid,
                    "name": text_content
                })
                print(f"[EXTRACT] ✓ Activité: shape_id={mid}, name={text_content}")
        
        print(f"[EXTRACT] Total activités extraites: {len(activities)}")
        
    except Exception as e:
        print(f"[EXTRACT] Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    return activities


def sync_activities_with_svg(entity_id, svg_path):
    """Synchronise les activités en base avec celles du SVG."""
    stats = {
        "added": 0,
        "existing": 0,
        "skipped": 0,
        "total_in_svg": 0
    }
    
    print(f"[SYNC] Démarrage pour entity_id={entity_id}")
    
    svg_activities = extract_activities_from_svg(svg_path)
    stats["total_in_svg"] = len(svg_activities)
    
    if not svg_activities:
        print("[SYNC] Aucune activité extraite!")
        return stats
    
    # Shape IDs existants pour CETTE entité
    existing = Activities.query.filter_by(entity_id=entity_id).all()
    existing_shape_ids = {str(a.shape_id) for a in existing if a.shape_id}
    existing_names = {a.name.lower() for a in existing}
    
    for act_data in svg_activities:
        shape_id = str(act_data["shape_id"])
        name = act_data["name"]
        
        # Vérifier si existe déjà pour cette entité
        if shape_id in existing_shape_ids or name.lower() in existing_names:
            stats["existing"] += 1
            continue
        
        try:
            new_activity = Activities(
                entity_id=entity_id,
                shape_id=shape_id,
                name=name,
                description="",
                is_result=False,
                duration_minutes=0,
                delay_minutes=0
            )
            db.session.add(new_activity)
            # Commit immédiat pour chaque activité (évite les gros rollbacks)
            db.session.commit()
            stats["added"] += 1
            print(f"[SYNC] ✓ Ajouté: {name}")
            
            # Mettre à jour les sets pour éviter les doublons
            existing_shape_ids.add(shape_id)
            existing_names.add(name.lower())
            
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            print(f"[SYNC] ❌ ERREUR pour '{name}' (shape_id={shape_id}): {error_msg}")
            stats["skipped"] += 1
            # Stocker le détail de l'erreur
            if "errors" not in stats:
                stats["errors"] = []
            stats["errors"].append(f"{name}: {error_msg[:100]}")
    
    print(f"[SYNC] Terminé: {stats['added']} ajoutées, {stats['existing']} existantes, {stats['skipped']} ignorées")
    return stats


# ============================================================
# UPLOAD CARTOGRAPHIE
# ============================================================
@activities_map_bp.route("/upload-carto", methods=["POST"])
def upload_carto():
    """Upload une nouvelle cartographie SVG."""
    print("[UPLOAD] Début upload")
    
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    
    file = request.files["file"]
    
    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide"}), 400
    
    filename_lower = file.filename.lower()
    
    if not filename_lower.endswith(".svg"):
        return jsonify({"error": "Format SVG requis"}), 400
    
    active_entity = Entity.get_active()
    
    if not active_entity:
        return jsonify({"error": "Aucune entité active"}), 400
    
    print(f"[UPLOAD] Entité: {active_entity.name} (id={active_entity.id})")
    
    try:
        entity_dir = ensure_entity_dir(active_entity.id)
        svg_path = os.path.join(entity_dir, "carto.svg")
        
        file.save(svg_path)
        print(f"[UPLOAD] Fichier sauvegardé: {svg_path}")
        
        active_entity.svg_filename = "carto.svg"
        db.session.commit()
        
        # Synchroniser les activités
        sync_stats = sync_activities_with_svg(active_entity.id, svg_path)
        
        return jsonify({
            "status": "ok",
            "message": f"Cartographie mise à jour",
            "sync": sync_stats
        })
        
    except Exception as e:
        print(f"[UPLOAD] Erreur: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# RE-SYNCHRONISATION MANUELLE
# ============================================================
@activities_map_bp.route("/resync", methods=["POST"])
def resync_activities():
    """Re-synchronise les activités depuis le SVG existant."""
    active_entity = Entity.get_active()
    
    if not active_entity:
        return jsonify({"error": "Aucune entité active"}), 400
    
    svg_path = get_entity_svg_path(active_entity.id)
    
    if not os.path.exists(svg_path) and os.path.exists(OLD_SVG_PATH):
        svg_path = OLD_SVG_PATH
    
    if not os.path.exists(svg_path):
        return jsonify({"error": "SVG non trouvé"}), 404
    
    try:
        sync_stats = sync_activities_with_svg(active_entity.id, svg_path)
        
        return jsonify({
            "status": "ok",
            "message": f"Re-synchronisation terminée",
            "sync": sync_stats
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@activities_map_bp.route("/update-cartography")
def update_cartography():
    return jsonify({"status": "ok", "message": "Cartographie rechargée"}), 200


# ============================================================
# DIAGNOSTIC BASE DE DONNÉES (pour débug)
# ============================================================
@activities_map_bp.route("/api/diagnostic")
def diagnostic_db():
    """Route de diagnostic pour vérifier les index et les activités."""
    from sqlalchemy import text
    
    result = {
        "indexes": [],
        "entities": [],
        "problem_detected": False,
        "problem_description": None
    }
    
    # Vérifier les index sur activities
    try:
        indexes = db.session.execute(text("""
            SELECT name, sql 
            FROM sqlite_master 
            WHERE type='index' AND tbl_name='activities' AND sql IS NOT NULL
        """)).fetchall()
        
        for name, sql in indexes:
            result["indexes"].append({"name": name, "sql": sql})
            
            # Détecter un index UNIQUE sur shape_id seul
            if sql and "UNIQUE" in sql.upper() and "shape_id" in sql.lower():
                if "entity_id" not in sql.lower() or (
                    "shape_id" in sql.lower() and 
                    "entity_id, shape_id" not in sql.lower() and
                    "entity_id,shape_id" not in sql.lower()
                ):
                    # Vérifier si c'est l'ancien format problématique
                    if "ix_activities_shape_id" in name or (
                        "shape_id" in sql and "entity_id" not in sql
                    ):
                        result["problem_detected"] = True
                        result["problem_description"] = f"Index UNIQUE sur shape_id seul: {name}"
    except Exception as e:
        result["index_error"] = str(e)
    
    # Vérifier les entités et leurs activités
    try:
        entities = Entity.query.all()
        for e in entities:
            count = Activities.query.filter_by(entity_id=e.id).count()
            result["entities"].append({
                "id": e.id,
                "name": e.name,
                "is_active": e.is_active,
                "activities_count": count
            })
    except Exception as e:
        result["entity_error"] = str(e)
    
    return jsonify(result)


@activities_map_bp.route("/api/fix-index", methods=["POST"])
def fix_shape_id_index():
    """Corrige l'index UNIQUE sur shape_id pour permettre les doublons entre entités."""
    from sqlalchemy import text
    
    result = {
        "status": "ok",
        "actions": [],
        "errors": []
    }
    
    try:
        # Supprimer l'ancien index problématique s'il existe
        try:
            db.session.execute(text("DROP INDEX IF EXISTS ix_activities_shape_id"))
            result["actions"].append("Supprimé: ix_activities_shape_id")
        except Exception as e:
            result["actions"].append(f"Pas d'index ix_activities_shape_id à supprimer")
        
        # Vérifier si l'index correct existe
        existing = db.session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='ix_activities_entity_shape'
        """)).fetchone()
        
        if not existing:
            # Créer l'index correct
            db.session.execute(text("""
                CREATE UNIQUE INDEX ix_activities_entity_shape 
                ON activities(entity_id, shape_id)
                WHERE shape_id IS NOT NULL
            """))
            result["actions"].append("Créé: ix_activities_entity_shape sur (entity_id, shape_id)")
        else:
            result["actions"].append("L'index ix_activities_entity_shape existe déjà")
        
        db.session.commit()
        
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))
        db.session.rollback()
    
    return jsonify(result)