# Code/routes/propose_savoirs.py
from flask import Blueprint, request, jsonify, current_app, session
from .propose_common import build_activity_context, openai_client_or_none, dummy_from_context

bp_propose_savoirs = Blueprint("propose_savoirs", __name__)

PROMPT_HEADER_SAVOIRS_FR = """
Analyse les informations de l’activité ci-dessous ainsi que la liste des savoir-faire associés.
Propose uniquement des SAVOIRS (connaissances) nécessaires pour tenir l’activité.

Règles :
- Les savoirs sont des connaissances à acquérir (règles, normes, principes, bases techniques, méthodologies, procédures, réglementations, référentiels…). Ne les formule pas comme des verbes d’action.
- Distingue-toi des savoir-faire : n’exprime pas une action, mais la connaissance sous-jacente (ex.: « Règles de nomenclature catalogue », « Procédure interne de transfert », « Principes de faisabilité technique »).
- Appuie-toi sur les éléments de l’activité (contraintes, outils, données, performances, rôles, environnement, risques) ET sur les savoir-faire fournis pour dériver les connaissances nécessaires.
- Complète par des savoirs TRANSVERSES requis par le contexte (SST, RGPD, qualité/traçabilité, sécurité de l’information, environnement, etc.).
- Priorise la précision et la contextualisation : cite normes/référentiels quand ils sont connus/mentionnés.
- 3 à 8 items maximum.
- Sortie attendue : liste à puces, 1 ligne par savoir (formulation nominale, sans verbe d’action).
- Réponds en français.
"""

PROMPT_HEADER_SAVOIRS_EN = """
Analyse the activity information below along with the list of associated practical skills.
Propose only the KNOWLEDGE items necessary to carry out the activity.

Rules:
- Knowledge items are things to learn (rules, standards, principles, technical fundamentals, methodologies, procedures, regulations, reference frameworks…). Do not phrase them as action verbs.
- Distinguish from practical skills: express the underlying knowledge, not an action (e.g. "Catalogue naming rules", "Internal transfer procedure", "Technical feasibility principles").
- Draw on activity elements (constraints, tools, data, performances, roles, environment, risks) AND the provided practical skills to derive the necessary knowledge.
- Add TRANSVERSAL knowledge required by the context (OHS, GDPR, quality/traceability, information security, environment, etc.).
- Prioritise precision and contextualisation: cite standards/frameworks when known or mentioned.
- 3 to 8 items maximum.
- Expected output: bullet list, 1 line per knowledge item (nominal phrasing, no action verb).
- Respond in English.
"""

PROMPT_HEADER_SAVOIRS = PROMPT_HEADER_SAVOIRS_FR

@bp_propose_savoirs.route("/propose_savoirs/propose", methods=["POST"])
def propose_savoirs():
    try:
        payload = request.get_json(force=True) or {}
        activity = dict(payload)
        savoir_faires = payload.get("savoir_faires") or []

        ctx = build_activity_context(activity)
        sf_block = "- " + "\n- ".join(savoir_faires) if savoir_faires else "-"

        client, err = openai_client_or_none()
        if client is None:
            # ✅ fallback sans clé
            return jsonify({"proposals": dummy_from_context(ctx, "savoir"), "source": err}), 200

        lang = session.get('lang', 'fr')
        header = PROMPT_HEADER_SAVOIRS_EN if lang == 'en' else PROMPT_HEADER_SAVOIRS_FR
        if lang == 'en':
            prompt = f"""{header}

=== ACTIVITY CONTEXT ===
{ctx}

=== ASSOCIATED PRACTICAL SKILLS ===
{sf_block}
"""
        else:
            prompt = f"""{header}

=== CONTEXTE ACTIVITÉ ===
{ctx}

=== SAVOIR-FAIRE ASSOCIÉS ===
{sf_block}
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
        lang = session.get('lang', 'fr')
        err_msg = "Knowledge not determined (server error)" if lang == 'en' else "Savoir non déterminé (erreur serveur)"
        return jsonify({"proposals": [err_msg], "error": str(e)}), 200
