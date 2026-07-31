# Code/routes/propose_savoirs.py
from flask import Blueprint, request, jsonify, current_app, session
from Code.prompts import get_prompt, prompts_available
from .propose_common import build_activity_context, openai_client_or_none, dummy_from_context

bp_propose_savoirs = Blueprint("propose_savoirs", __name__)




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
        header = get_prompt(f"propose.savoirs.header.{'en' if lang == 'en' else 'fr'}")
        if header is None:
            return jsonify({"proposals": dummy_from_context(ctx, "savoir"),
                            "source": "prompts-unavailable"}), 200
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
        lang = session.get('lang', 'fr')
        err_msg = "Knowledge not determined (server error)" if lang == 'en' else "Savoir non déterminé (erreur serveur)"
        return jsonify({"proposals": [err_msg], "error": str(e)}), 200
