# Code/routes/translate_softskills.py
import os
import json
import re
from flask import Blueprint, request, jsonify, current_app, session
from Code.ai_key import get_openai_key
from Code.prompts import get_prompt, prompts_available

translate_softskills_bp = Blueprint('translate_softskills_bp', __name__, url_prefix='/translate_softskills')








def get_openai_client():
    api_key = get_openai_key()
    if not api_key:
        return None, "Clé IA non renseignée."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        return client, None
    except Exception as e:
        return None, str(e)


def clean_json_response(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text


def make_enumeration(prefix, items):
    lines = []
    for i, it in enumerate(items, start=1):
        if isinstance(it, dict):
            desc = it.get("description", str(it))
            lines.append(f"{prefix}{i}: {desc}")
        else:
            lines.append(f"{prefix}{i}: {it}")
    return "\n".join(lines) if lines else f"(Aucune {prefix.strip()})"


@translate_softskills_bp.route('/translate', methods=['POST'])
def translate_softskills():
    data = request.get_json() or {}
    user_input = data.get("user_input", "").strip()
    activity_data = data.get("activity_data", {})

    if not user_input:
        return jsonify({"error": "Aucun texte saisi pour la traduction."}), 400

    activity_name = activity_data.get("name", "Activité sans nom")
    tasks_list = activity_data.get("tasks", [])
    constraints_list = activity_data.get("constraints", [])
    outgoing_list = activity_data.get("outgoing", [])

    tasks_text = make_enumeration("T", tasks_list)
    constraints_text = make_enumeration("C", constraints_list)

    perf_lines = []
    perf_idx = 1
    for o in outgoing_list:
        if isinstance(o, dict):
            perf = o.get("performance")
            if perf:
                name = perf.get("name", "")
                desc = perf.get("description", "")
                perf_lines.append(f"P{perf_idx}: {name} - {desc}")
                perf_idx += 1
    perf_text = "\n".join(perf_lines) if perf_lines else "(Aucune performance)"

    lang = session.get('lang', 'fr')
    if lang == 'en':
        prompt = get_prompt(
            "translate.hsc.en",
            user_input=user_input,
            activity_name=activity_name,
            tasks_text=tasks_text,
            constraints_text=constraints_text,
            perf_text=perf_text,
            x50_766_hsc=get_prompt("referential.x50_766.en") or "",
        )
        system_msg = "You are a specialist in Socio-Cognitive Abilities (SCA) XP X50-766. You MUST respond only in valid JSON, without markdown or additional text."
    else:
        prompt = get_prompt(
            "translate.hsc.fr",
            user_input=user_input,
            activity_name=activity_name,
            tasks_text=tasks_text,
            constraints_text=constraints_text,
            perf_text=perf_text,
            x50_766_hsc=get_prompt("referential.x50_766.fr") or "",
        )
        system_msg = "Tu es un assistant spécialisé en habiletés socio-cognitives X50-766. Tu réponds UNIQUEMENT en JSON valide, sans markdown ni texte supplémentaire."

    client, err = get_openai_client()
    if client is None:
        return jsonify({"error": err}), 500
    if prompt is None:
        return jsonify({"error": "Prompts IA non chargés sur cette instance."}), 500

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1200
        )
        ai_text = response.choices[0].message.content.strip()
        cleaned_text = clean_json_response(ai_text)

        try:
            proposals = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            current_app.logger.error(f"JSON parse error: {e}. Raw text: {ai_text[:500]}")
            return jsonify({"error": f"Erreur de parsing JSON: {str(e)}"}), 400

        if not isinstance(proposals, list):
            if isinstance(proposals, dict):
                proposals = [proposals]
            else:
                return jsonify({"error": "Le JSON renvoyé n'est pas un tableau d'objets."}), 400

        if lang == 'en':
            niveau_map = {
                "1": "1 (Basic)",
                "2": "2 (Developing)",
                "3": "3 (Proficient)",
                "4": "4 (Highly Proficient)"
            }
        else:
            niveau_map = {
                "1": "1 (Aptitude)",
                "2": "2 (Acquisition)",
                "3": "3 (Maîtrise)",
                "4": "4 (Excellence)"
            }

        for p in proposals:
            niveau = p.get("niveau", "2")
            if isinstance(niveau, int) or (isinstance(niveau, str) and niveau.isdigit()):
                p["niveau"] = niveau_map.get(str(niveau), "2 (Acquisition)")

        return jsonify({"proposals": proposals}), 200

    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"error": str(e)}), 500
