# Code/routes/propose_savoir_faires.py
from flask import Blueprint, request, jsonify, current_app, session
from .propose_common import build_activity_context, openai_client_or_none, dummy_from_context

bp_propose_sf = Blueprint("propose_savoir_faires", __name__)

PROMPT_HEADER_SAVOIR_FAIRES_FR = """
Analyse les informations d’activité ci-dessous et propose uniquement des SAVOIR-FAIRE
concrets et opérationnels, formulés par verbes d’action.

Règles :
- Chaque item commence par un verbe d’action (Utiliser, Maîtriser, Vérifier, Rédiger, Structurer, Appliquer, Contrôler, Analyser, Consolider, Documenter…)
- Précise toujours sur quoi ou avec quoi le savoir-faire s’exerce (procédure, outil, norme, donnée, contrainte, rôle…)
- Les savoir-faire doivent être spécifiques et contextualisés, pas vagues ni génériques.
- Ne répète pas les tâches textuellement, déduis l’apprentissage concret nécessaire.
- Limite la réponse à 3 à 7 items maximum.
- Sortie attendue : liste à puces, une ligne par savoir-faire.
- Réponds en français.
"""

PROMPT_HEADER_SAVOIR_FAIRES_EN = """
Analyse the activity information below and propose only concrete and operational PRACTICAL SKILLS,
phrased as action verbs.

Rules:
- Each item starts with an action verb (Use, Master, Verify, Draft, Structure, Apply, Control, Analyse, Consolidate, Document…)
- Always specify what or with what the practical skill is exercised (procedure, tool, standard, data, constraint, role…)
- Practical skills must be specific and contextualised, not vague or generic.
- Do not repeat tasks verbatim; derive the concrete learning required.
- Limit the response to 3 to 7 items maximum.
- Expected output: bullet list, one line per practical skill.
- Respond in English.
"""

PROMPT_HEADER_SAVOIR_FAIRES = PROMPT_HEADER_SAVOIR_FAIRES_FR

@bp_propose_sf.route("/propose_savoir_faires/propose", methods=["POST"])
def propose_savoir_faires():
    try:
        activity = request.get_json(force=True) or {}
        ctx = build_activity_context(activity)

        client, err = openai_client_or_none()
        if client is None:
            # ✅ pas de clé → on renvoie un fallback 200
            return jsonify({"proposals": dummy_from_context(ctx, "savoir_faire"), "source": err}), 200

        lang = session.get('lang', 'fr')
        header = PROMPT_HEADER_SAVOIR_FAIRES_EN if lang == 'en' else PROMPT_HEADER_SAVOIR_FAIRES_FR
        ctx_label = "CONTEXT" if lang == 'en' else "CONTEXTE"
        prompt = f"""{header}

=== {ctx_label} ===
{ctx}
"""
        system_msg = (
            "You are a precise and concise HR/training assistant."
            if lang == 'en'
            else "Tu es un assistant RH/formation, précis et concis."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()

        lines = [l.strip("-• ").strip() for l in text.splitlines() if l.strip()]
        lines = [l for l in lines if l]

        return jsonify({"proposals": lines}), 200

    except Exception as e:
        current_app.logger.exception(e)
        # ⚠️ en dernier recours seulement
        lang = session.get('lang', 'fr')
        err_msg = "Practical skill not determined (server error)" if lang == 'en' else "Savoir-faire non déterminé (erreur serveur)"
        return jsonify({"proposals": [err_msg], "error": str(e)}), 200
