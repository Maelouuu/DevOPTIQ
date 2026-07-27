# Code/routes/skills.py

from flask import Blueprint, request, jsonify, session
from Code.ai_key import get_openai_key
from Code.prompts import get_prompt, prompts_available
import os
import openai
import re
from Code.extensions import db
from Code.models.models import Competency

skills_bp = Blueprint('skills', __name__, url_prefix='/skills')

@skills_bp.route('/propose', methods=['POST'])
def propose_skills():
    """
    Génère EXACTEMENT 3 propositions de compétences. 
    Si l'IA renvoie tout sur une ligne, on fait un fallback 
    pour découper en 3 phrases.
    """
    data = request.get_json() or {}
    activity_name = data.get("name", "Activité sans nom")
    input_data_value = data.get("input_data", "")
    output_data = data.get("output_data", "")

    if isinstance(output_data, dict):
        output_data_value = output_data.get("text", "")
    else:
        output_data_value = output_data

    # Tâches
    tasks_data = data.get("tasks", [])
    tasks_list = []
    for t in tasks_data:
        if isinstance(t, dict):
            tasks_list.append(t.get("name", ""))
        else:
            tasks_list.append(str(t))
    tasks_list = [t.strip() for t in tasks_list if t.strip()]
    if not tasks_list:
        return jsonify({"error": "Au moins une tâche est requise pour proposer des compétences."}), 400
    tasks_str = ", ".join(tasks_list)

    # Connexions sortantes
    outgoing_data = data.get("outgoing", [])
    outgoing_list = []
    for conn in outgoing_data:
        if isinstance(conn, dict):
            val = conn.get("target_name", conn.get("data_name", "")).strip()
            outgoing_list.append(val)
        else:
            outgoing_list.append(str(conn).strip())
    outgoing_list = [x for x in outgoing_list if x]
    outgoing_str = ", ".join(outgoing_list) if outgoing_list else "Aucune connexion sortante"

    # Outils
    tools_data = data.get("tools", [])
    tools_list = []
    for t in tools_data:
        if isinstance(t, dict):
            tools_list.append(t.get("name", "").strip())
        else:
            tools_list.append(str(t).strip())
    tools_list = [x for x in tools_list if x]
    tools_str = ", ".join(tools_list) if tools_list else "Aucun outil"

    # --- PROMPT ---
    lang = session.get('lang', 'fr')
    lang_instr = "Write the 3 competency proposals in English." if lang == 'en' else "Rédigez les 3 propositions en français."
    prompt = get_prompt(
        "skills.competencies",
        lang_instr=lang_instr,
        activity_name=activity_name,
        input_data=input_data_value,
        output_data=output_data_value,
        tasks=tasks_str,
        outgoing=outgoing_str,
        tools=tools_str,
    )
    if prompt is None:
        return jsonify({"error": "Prompts IA non chargés sur cette instance."}), 500

    # --- OpenAI API KEY ---
    openai.api_key = get_openai_key()
    if not openai.api_key:
        return jsonify({"error": "Clé IA non renseignée."}), 500

    # --- NOUVEAU CLIENT OPENAI ---
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai.api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",    # modèle compatible nouvelle API
            messages=[
                {"role": "system", "content": get_prompt("skills.system")},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=600
        )

        raw_text = response.choices[0].message.content.strip()

        # Séparation simple
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

        # Fallback
        if len(lines) < 3:
            splitted = re.split(r'\.\s+', raw_text)
            splitted = [s.strip() for s in splitted if s.strip()]
            if len(splitted) > len(lines):
                lines = splitted
        
        # Max 3 lignes
        lines = lines[:3]

        return jsonify({"proposals": lines}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@skills_bp.route('/add', methods=['POST'])
def add_competency():
    """
    Ajoute une compétence dans la table 'competencies'.
    JSON attendu : { "activity_id": <int>, "description": <str> }
    """
    data = request.get_json() or {}
    activity_id = data.get("activity_id")
    description = data.get("description", "").strip()
    if not activity_id or not description:
        return jsonify({"error": "activity_id and description are required"}), 400

    comp = Competency(activity_id=activity_id, description=description)
    try:
        db.session.add(comp)
        db.session.commit()
        return jsonify({
            "id": comp.id,
            "activity_id": comp.activity_id,
            "description": comp.description
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@skills_bp.route('/<int:competency_id>', methods=['PUT'])
def update_competency(competency_id):
    """
    Met à jour une compétence existante.
    JSON attendu : { "description": <str> }
    """
    data = request.get_json() or {}
    new_desc = data.get("description", "").strip()
    if not new_desc:
        return jsonify({"error": "description is required"}), 400

    comp = Competency.query.get(competency_id)
    if not comp:
        return jsonify({"error": "Competency not found"}), 404

    try:
        comp.description = new_desc
        db.session.commit()
        return jsonify({
            "id": comp.id,
            "description": comp.description
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@skills_bp.route('/<int:competency_id>', methods=['DELETE'])
def delete_competency(competency_id):
    comp = Competency.query.get(competency_id)
    if not comp:
        return jsonify({"error": "Competency not found"}), 404
    try:
        db.session.delete(comp)
        db.session.commit()
        return jsonify({"message": "Competency deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
