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

from sqlalchemy import or_
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
    from flask import session
    
    active_entity = Entity.get_active()
    active_entity_id = session.get('active_entity_id')
    
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
    
    all_entities = Entity.for_user().all()
    
    active_entity_dict = None
    if active_entity:
        active_entity_dict = {
            "id": active_entity.id,
            "name": active_entity.name,
            "description": active_entity.description or "",
            "svg_filename": active_entity.svg_filename,
            "is_active": True  # Par définition, c'est l'entité active
        }
    
    all_entities_list = [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description or "",
            "svg_filename": e.svg_filename,
            "is_active": (e.id == active_entity_id)  # Basé sur la session
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
    from flask import session
    
    user_id = session.get('user_id')
    active_entity_id = session.get('active_entity_id')
    
    if not user_id:
        return jsonify([])  # Pas connecté = pas d'entités
    
    # STRICT: Seulement les entités de l'utilisateur
    entities = Entity.query.filter_by(owner_id=user_id).order_by(Entity.name).all()
    
    return jsonify([
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "svg_filename": e.svg_filename,
            "is_active": (e.id == active_entity_id),
            "activities_count": Activities.query.filter_by(entity_id=e.id).count()
        }
        for e in entities
    ])


@activities_map_bp.route("/api/entities", methods=["POST"])
def create_entity():
    from flask import session
    
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
    """Active une entité pour l'utilisateur courant (stocké dans la session)."""
    from flask import session
    
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401
    
    # STRICT: Vérifier que l'entité appartient à l'utilisateur
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    
    if not entity:
        return jsonify({"error": "Entité non trouvée ou non autorisée"}), 404
    
    try:
        # Stocker l'entité active dans la session
        session['active_entity_id'] = entity.id
        
        return jsonify({
            "status": "ok",
            "message": f"Entité '{entity.name}' activée"
        })
        
    except Exception as e:
        print(f"[ACTIVATE] Erreur: {e}")
        return jsonify({"error": str(e)}), 500


@activities_map_bp.route("/api/entities/<int:entity_id>", methods=["DELETE"])
def delete_entity(entity_id):
    from flask import session
    
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401
    
    # STRICT: Vérifier que l'entité appartient à l'utilisateur
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    
    if not entity:
        return jsonify({"error": "Entité non trouvée ou non autorisée"}), 404
    
    activities_count = Activities.query.filter_by(entity_id=entity_id).count()
    
    entity_dir = os.path.join(ENTITIES_DIR, f"entity_{entity_id}")
    if os.path.exists(entity_dir):
        shutil.rmtree(entity_dir)
    
    entity_name = entity.name
    
    try:
        db.session.delete(entity)
        db.session.commit()
        
        # Si l'entité supprimée était l'active, en choisir une autre
        if session.get('active_entity_id') == entity_id:
            first = Entity.query.filter_by(owner_id=user_id).first()
            if first:
                session['active_entity_id'] = first.id
            else:
                session.pop('active_entity_id', None)
        
        return jsonify({
            "status": "ok",
            "message": f"Entité '{entity_name}' supprimée ({activities_count} activités supprimées)"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@activities_map_bp.route("/api/entities/<int:entity_id>", methods=["PATCH"])
def update_entity(entity_id):
    from flask import session
    
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Non connecté"}), 401
    
    # STRICT: Vérifier que l'entité appartient à l'utilisateur
    entity = Entity.query.filter_by(id=entity_id, owner_id=user_id).first()
    
    if not entity:
        return jsonify({"error": "Entité non trouvée ou non autorisée"}), 404
    
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
    """
    Synchronise INTELLIGEMMENT les activités en base avec celles du SVG.
    
    Logique basée sur le shape_id (identifiant unique Visio) :
    - shape_id dans SVG mais pas en base → CRÉER
    - shape_id existe en base avec nom différent → RENOMMER (garder les données)
    - shape_id en base mais pas dans SVG → SIGNALER comme supprimé
    """
    stats = {
        "added": 0,
        "renamed": 0,
        "unchanged": 0,
        "deleted_warning": 0,
        "skipped": 0,
        "total_in_svg": 0,
        "renamed_list": [],      # Liste des renommages effectués
        "deleted_list": [],      # Liste des activités potentiellement supprimées
        "errors": []
    }
    
    print(f"[SYNC] Démarrage pour entity_id={entity_id}")
    
    svg_activities = extract_activities_from_svg(svg_path)
    stats["total_in_svg"] = len(svg_activities)
    
    if not svg_activities:
        print("[SYNC] Aucune activité extraite!")
        return stats
    
    # Créer un dictionnaire shape_id -> name depuis le SVG
    svg_shape_map = {str(act["shape_id"]): act["name"] for act in svg_activities}
    svg_shape_ids = set(svg_shape_map.keys())
    
    # Récupérer les activités existantes pour cette entité
    existing_activities = Activities.query.filter_by(entity_id=entity_id).all()
    existing_shape_map = {str(a.shape_id): a for a in existing_activities if a.shape_id}
    existing_shape_ids = set(existing_shape_map.keys())
    
    print(f"[SYNC] SVG: {len(svg_shape_ids)} activités | Base: {len(existing_shape_ids)} activités")
    
    # === 1. NOUVELLES ACTIVITÉS (dans SVG mais pas en base) ===
    new_shape_ids = svg_shape_ids - existing_shape_ids
    for shape_id in new_shape_ids:
        name = svg_shape_map[shape_id]
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
            db.session.commit()
            stats["added"] += 1
            print(f"[SYNC] ✓ AJOUTÉ: {name} (shape_id={shape_id})")
        except Exception as e:
            db.session.rollback()
            stats["skipped"] += 1
            stats["errors"].append(f"{name}: {str(e)[:100]}")
            print(f"[SYNC] ❌ ERREUR ajout '{name}': {e}")
    
    # === 2. ACTIVITÉS EXISTANTES - vérifier les renommages ===
    common_shape_ids = svg_shape_ids & existing_shape_ids
    for shape_id in common_shape_ids:
        svg_name = svg_shape_map[shape_id]
        db_activity = existing_shape_map[shape_id]
        
        if db_activity.name != svg_name:
            # Renommage détecté !
            old_name = db_activity.name
            db_activity.name = svg_name
            try:
                db.session.commit()
                stats["renamed"] += 1
                stats["renamed_list"].append({
                    "old": old_name,
                    "new": svg_name,
                    "shape_id": shape_id
                })
                print(f"[SYNC] ✏️ RENOMMÉ: '{old_name}' → '{svg_name}'")
            except Exception as e:
                db.session.rollback()
                print(f"[SYNC] ❌ ERREUR renommage: {e}")
        else:
            stats["unchanged"] += 1
    
    # === 3. ACTIVITÉS SUPPRIMÉES (en base mais plus dans SVG) ===
    deleted_shape_ids = existing_shape_ids - svg_shape_ids
    for shape_id in deleted_shape_ids:
        db_activity = existing_shape_map[shape_id]
        stats["deleted_warning"] += 1
        stats["deleted_list"].append({
            "id": db_activity.id,
            "name": db_activity.name,
            "shape_id": shape_id
        })
        print(f"[SYNC] ⚠️ SUPPRIMÉ DU SVG: '{db_activity.name}' (shape_id={shape_id})")
    
    print(f"[SYNC] Terminé: +{stats['added']} ajoutées, ✏️{stats['renamed']} renommées, ⚠️{stats['deleted_warning']} supprimées du SVG")
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
        "problem_description": None,
        "database_type": "unknown"
    }
    
    # Détecter le type de base de données
    try:
        db.session.execute(text("SELECT version()"))
        result["database_type"] = "postgresql"
    except:
        result["database_type"] = "sqlite"
    
    # Vérifier les index sur activities
    try:
        if result["database_type"] == "postgresql":
            indexes = db.session.execute(text("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'activities'
            """)).fetchall()
        else:
            indexes = db.session.execute(text("""
                SELECT name, sql 
                FROM sqlite_master 
                WHERE type='index' AND tbl_name='activities' AND sql IS NOT NULL
            """)).fetchall()
        
        for row in indexes:
            name, sql = row[0], row[1]
            result["indexes"].append({"name": name, "sql": sql})
            
            # Détecter un index UNIQUE sur shape_id seul
            if sql and "shape_id" in sql.lower():
                # Si c'est un index sur shape_id sans entity_id
                if "ix_activities_shape_id" in name.lower():
                    result["problem_detected"] = True
                    result["problem_description"] = f"Index UNIQUE sur shape_id seul détecté: {name}"
                elif "unique" in sql.lower() and "entity_id" not in sql.lower():
                    result["problem_detected"] = True
                    result["problem_description"] = f"Index UNIQUE sur shape_id seul: {name}"
                    
    except Exception as e:
        result["index_error"] = str(e)[:200]
    
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
        result["entity_error"] = str(e)[:200]
    
    return jsonify(result)


@activities_map_bp.route("/api/drop-bad-index", methods=["POST"])
def drop_bad_index():
    """Force la suppression de l'index ix_activities_shape_id."""
    from sqlalchemy import text
    import time
    
    result = {
        "status": "pending",
        "attempts": [],
        "final_check": None
    }
    
    # Essayer plusieurs fois
    for attempt in range(5):
        try:
            db.session.execute(text("DROP INDEX IF EXISTS ix_activities_shape_id"))
            db.session.commit()
            result["attempts"].append(f"Tentative {attempt + 1}: SUCCESS")
            result["status"] = "ok"
            break
        except Exception as e:
            db.session.rollback()
            result["attempts"].append(f"Tentative {attempt + 1}: {str(e)[:80]}")
            time.sleep(0.5)  # Attendre un peu avant de réessayer
    
    # Vérifier si l'index existe encore
    try:
        check = db.session.execute(text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'activities' AND indexname = 'ix_activities_shape_id'
        """)).fetchone()
        
        if check:
            result["final_check"] = "ÉCHEC - L'index existe toujours!"
            result["status"] = "failed"
        else:
            result["final_check"] = "OK - L'index a été supprimé"
            result["status"] = "ok"
    except Exception as e:
        result["final_check"] = f"Erreur vérification: {str(e)[:80]}"
    
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
        # 1. Supprimer l'ancien index problématique
        try:
            db.session.execute(text("DROP INDEX IF EXISTS ix_activities_shape_id"))
            db.session.commit()
            result["actions"].append("DROP ix_activities_shape_id: OK")
        except Exception as e:
            db.session.rollback()
            result["actions"].append(f"DROP ix_activities_shape_id: {str(e)[:100]}")
        
        # 2. Vérifier les index existants (PostgreSQL)
        try:
            indexes = db.session.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE tablename = 'activities' AND indexname LIKE '%shape%'
            """)).fetchall()
            result["existing_indexes"] = [row[0] for row in indexes]
        except Exception as e:
            result["existing_indexes"] = f"Erreur: {str(e)[:100]}"
        
        # 3. Créer le nouvel index si nécessaire
        try:
            # Vérifier si l'index correct existe
            check = db.session.execute(text("""
                SELECT 1 FROM pg_indexes 
                WHERE tablename = 'activities' AND indexname = 'ix_activities_entity_shape'
            """)).fetchone()
            
            if not check:
                db.session.execute(text("""
                    CREATE UNIQUE INDEX ix_activities_entity_shape 
                    ON activities(entity_id, shape_id)
                    WHERE shape_id IS NOT NULL
                """))
                db.session.commit()
                result["actions"].append("CREATE ix_activities_entity_shape: OK")
            else:
                result["actions"].append("ix_activities_entity_shape existe déjà")
        except Exception as e:
            db.session.rollback()
            result["errors"].append(f"CREATE index: {str(e)[:150]}")
        
        # 4. Vérification finale
        try:
            final_indexes = db.session.execute(text("""
                SELECT indexname, indexdef FROM pg_indexes 
                WHERE tablename = 'activities' AND indexname LIKE '%shape%'
            """)).fetchall()
            result["final_indexes"] = [{"name": row[0], "def": row[1]} for row in final_indexes]
        except Exception as e:
            result["final_indexes"] = f"Erreur: {str(e)[:100]}"
            
    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e)[:200])
        db.session.rollback()
    
    return jsonify(result)