from flask import Blueprint, request, jsonify, session
import os
from Code.extensions import db
from Code.models.models import Role

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/roles')

ONBOARDING_PROMPT_FR = """
Vous êtes un expert en développement des habiletés sociocognitives (HSC) et en accompagnement professionnel.
Votre mission est de générer un plan d'onboarding exclusivement axé sur les HSC suivantes : {hsc_list}.
Le plan devra comporter quatre parties distinctes :

1) **Module de formation/entraînement** :
   - Proposez une ou plusieurs formations courtes, chacune durant entre 0,5 et 2 jours, sans dépasser un total de 3 jours.
   - La formation doit porter uniquement sur le développement des HSC listées.
   - Précisez pour chaque formation les objectifs, la durée, la Méthode (en utilisant le terme "Méthode" sans ajouter "enseignement") et des critères d'évaluation objectifs pouvant être mesurés à la fin de la formation et dans les semaines suivantes.

2) **Retour d'Expérience (REX)** :
   - Décrivez une session de REX personnalisée qui s'appuie sur les HSC listées, en expliquant comment animer la session et en donnant des exemples concrets d'analyse des situations vécues pour améliorer ces HSC.

3) **Coaching d'Équipe** :
   - Donnez des conseils précis pour un coaching d'équipe visant à soutenir le développement des HSC du rôle.
   - Concentrez-vous sur des stratégies pour renforcer la coopération, l'auto-organisation et l'adaptation, en lien avec les HSC fournies.

4) **Parcours d'Apprentissage Autonome** :
   - Proposez un parcours d'apprentissage autonome incluant des exemples concrets de contenus de micro-formations en ligne, des exercices pratiques et des quiz, spécifiquement conçus pour développer les HSC listées.

Assurez-vous que le plan se centre uniquement sur les HSC mentionnées dans la liste et n'intègre aucune autre compétence ou soft skill.
Répondez sous forme de texte structuré avec des titres clairs pour chaque partie.
"""

ONBOARDING_PROMPT_EN = """
You are an expert in the development of Socio-Cognitive Abilities (SCA) and professional support.
Your mission is to generate an onboarding plan exclusively focused on the following SCA: {hsc_list}.
The plan must include four distinct parts:

1) **Training / Practice Module**:
   - Propose one or more short training sessions, each lasting between 0.5 and 2 days, not exceeding 3 days in total.
   - Training must focus exclusively on developing the listed SCA.
   - For each session, specify the objectives, duration, Method (use the term "Method" without adding "teaching") and objective evaluation criteria that can be measured at the end of training and in the following weeks.

2) **Experience Review (REX)**:
   - Describe a personalised experience review session based on the listed SCA, explaining how to facilitate the session and giving concrete examples of analysing real situations to improve these SCA.

3) **Team Coaching**:
   - Provide specific advice for team coaching aimed at supporting the development of the role's SCA.
   - Focus on strategies to strengthen cooperation, self-organisation and adaptation, in connection with the provided SCA.

4) **Independent Learning Path**:
   - Propose an independent learning path including concrete examples of online micro-training content, practical exercises and quizzes, specifically designed to develop the listed SCA.

Ensure the plan focuses only on the SCA mentioned in the list and does not include any other competency or soft skill.
Respond in structured text with clear headings for each part.
"""


@onboarding_bp.route('/<int:role_id>/onboarding/generate', methods=['POST'])
def generate_onboarding(role_id):
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "Role not found"}), 404

    data = request.get_json() or {}
    hsc_list = data.get("hsc_list", [])

    lang = session.get('lang', 'fr')
    prompt_template = ONBOARDING_PROMPT_EN if lang == 'en' else ONBOARDING_PROMPT_FR
    prompt = prompt_template.format(hsc_list=hsc_list)

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
