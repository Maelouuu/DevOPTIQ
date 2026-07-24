# Code/routes/propose_savoir_faires.py
from flask import Blueprint, request, jsonify, current_app, session
from Code.prompts import get_prompt, prompts_available
from .propose_common import build_activity_context, openai_client_or_none, dummy_from_context

bp_propose_sf = Blueprint("propose_savoir_faires", __name__)




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
        header = get_prompt(f"propose.savoir_faires.header.{'en' if lang == 'en' else 'fr'}")
        if header is None:
            return jsonify({"proposals": dummy_from_context(ctx, "savoir_faire"),
                            "source": "prompts-unavailable"}), 200
        ctx_label = "CONTEXT" if lang == 'en' else "CONTEXTE"
        prompt = f"""{header}

=== {ctx_label} ===
{ctx}
"""
        system_msg = get_prompt(f"propose.system.{'en' if lang == 'en' else 'fr'}")
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
