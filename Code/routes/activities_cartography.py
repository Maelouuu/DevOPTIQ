from .activities_bp import activities_bp
from flask import jsonify
import os, io, contextlib, traceback
from Code.scripts.extract_visio import process_visio_file, print_summary
from Code.models.models import Entity
from Code.carto_access import can_edit

@activities_bp.route('/update-cartography', methods=['GET'])
def update_cartography():
    try:
        # Récupérer l'entité active
        active_entity = Entity.get_active()

        if not active_entity:
            return jsonify({"error": "Aucune entité active trouvée"}), 400

        # L'import réécrit activités, données et liens de la carto : réservé à
        # qui peut l'enregistrer directement.
        if not can_edit(active_entity):
            return jsonify({"error": "Modification de la cartographie non autorisée"}), 403

        # Vérifier que l'entité a un fichier SVG défini
        if not active_entity.svg_filename:
            return jsonify({
                "error": "Aucune cartographie définie pour cette entité",
                "message": "Veuillez d'abord télécharger un fichier Visio pour cette entité"
            }), 400

        # Construire le chemin complet du fichier
        # Le fichier devrait être dans static/svg/ ou dans Code/
        vsdx_path = None

        # Essayer différents emplacements possibles
        possible_paths = [
            os.path.join("Code", active_entity.svg_filename),
            os.path.join("static", "svg", active_entity.svg_filename),
            active_entity.svg_filename  # Si c'est déjà un chemin complet
        ]

        for path in possible_paths:
            if os.path.exists(path):
                vsdx_path = path
                break

        if not vsdx_path:
            return jsonify({
                "error": f"Fichier de cartographie introuvable: {active_entity.svg_filename}",
                "message": "Le fichier de cartographie n'existe pas sur le serveur"
            }), 404

        print(f"📍 Traitement de la cartographie: {vsdx_path}")

        # Traiter le fichier Visio
        process_visio_file(vsdx_path, entity_id=active_entity.id)

        # Générer le résumé
        summary_output = io.StringIO()
        with contextlib.redirect_stdout(summary_output):
            print_summary()
        summary_text = summary_output.getvalue()

        return jsonify({
            "message": f"Cartographie mise à jour pour l'entité: {active_entity.name}",
            "summary": summary_text,
            "file": active_entity.svg_filename
        }), 200

    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour de la cartographie: {e}")
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "message": "Erreur lors du traitement de la cartographie"
        }), 500
