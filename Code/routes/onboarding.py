from flask import Blueprint, request, jsonify, session
from Code.prompts import get_prompt, prompts_available
import os
from Code.extensions import db
from Code.models.models import Role

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/roles')




@onboarding_bp.route('/<int:role_id>/onboarding/generate', methods=['POST'])
def generate_onboarding(role_id):
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "Role not found"}), 404

    data = request.get_json() or {}
    hsc_list = data.get("hsc_list", [])

    lang = session.get('lang', 'fr')
    prompt = get_prompt(f"onboarding.plan.{'en' if lang == 'en' else 'fr'}", hsc_list=hsc_list)
    if prompt is None:
        err_msg = "AI unavailable (prompts not loaded)." if lang == 'en' else "IA indisponible (prompts non chargés)."
        return jsonify({"error": err_msg}), 500

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        err_msg = "OpenAI key missing (OPENAI_API_KEY)." if lang == 'en' else "Clé OpenAI manquante (OPENAI_API_KEY)."
        return jsonify({"error": err_msg}), 500

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_content = (
            "You are a specialist in SCA development and professional support."
            if lang == 'en'
            else "Vous êtes un assistant spécialisé en développement des HSC et en accompagnement professionnel."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1500
        )
        onboarding_plan = response.choices[0].message.content.strip()

        role.onboarding_plan = onboarding_plan
        db.session.commit()

        success_msg = "Onboarding plan generated successfully" if lang == 'en' else "Plan d'onboarding généré avec succès"
        return jsonify({
            "message": success_msg,
            "onboarding_plan": onboarding_plan
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/<int:role_id>/onboarding', methods=['GET'])
def get_onboarding(role_id):
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "Role not found"}), 404
    if not role.onboarding_plan:
        lang = session.get('lang', 'fr')
        err_msg = "No onboarding plan generated for this role." if lang == 'en' else "Aucun plan d'onboarding généré pour ce rôle."
        return jsonify({"error": err_msg}), 404
    return jsonify({"onboarding_plan": role.onboarding_plan}), 200
