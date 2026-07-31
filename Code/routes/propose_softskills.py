# Code/routes/propose_softskills.py
import json
import re
from flask import Blueprint, request, jsonify, current_app, session
from Code.prompts import get_prompt, prompts_available
from .propose_common import (
    ai_model,
    openai_client_or_none,
    dummy_from_context,
)

bp_propose_softskills = Blueprint("propose_softskills", __name__)



# Legacy alias kept for any internal reference




# --------------------------------------------------------------------
# OUTILS : extraction JSON propre
# --------------------------------------------------------------------
def clean_json_response(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())

    start_bracket = text.find('[')
    start_brace = text.find('{')

    if start_bracket == -1 and start_brace == -1:
        return text

    if start_bracket == -1:
        start = start_brace
    elif start_brace == -1:
        start = start_bracket
    else:
        start = min(start_bracket, start_brace)

    if text[start] == '[':
        end = text.rfind(']')
    else:
        end = text.rfind('}')

    if end == -1 or end < start:
        return text

    return text[start:end+1]


def make_enumeration(prefix, items):
    lines = []
    for i, it in enumerate(items, start=1):
        if isinstance(it, dict):
            desc = it.get("description", str(it))
            lines.append(f"{prefix}{i}: {desc}")
        else:
            lines.append(f"{prefix}{i}: {it}")
    return "\n".join(lines) if lines else f"(Aucune {prefix.strip()})"


# --------------------------------------------------------------------
# ROUTE PRINCIPALE
# --------------------------------------------------------------------
@bp_propose_softskills.route("/propose_softskills/propose", methods=["POST"])
def propose_softskills():
    try:
        activity = request.get_json(force=True) or {}

        client, err = openai_client_or_none()
        lang = session.get('lang', 'fr')
        if client is None or not prompts_available():
            default_level = "2 (Developing)" if lang == 'en' else "2 (Acquisition)"
            default_justif = "Proposal generated without AI (OpenAI key missing)." if lang == 'en' else "Proposition générée sans IA (clé OpenAI absente)."
            proposals = [
                {
                    "habilete": item,
                    "niveau": default_level,
                    "justification": default_justif,
                }
                for item in dummy_from_context("", "hsc")
            ]
            return jsonify({"proposals": proposals, "source": err}), 200

        activity_name = activity.get("name") or activity.get("title") or ("Activity" if lang == 'en' else "Activité sans nom")

        tasks_list = activity.get("tasks") or []
        constraints_list = activity.get("constraints") or []
        outgoing_list = activity.get("outgoing") or []

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

        lang = session.get('lang', 'fr')
        if lang == 'en':
            perf_text = "\n".join(perf_lines) if perf_lines else "(No performances recorded)"
            prompt = get_prompt(
                "propose.softskills.header.en",
                activity_name=activity_name,
                perf_text=perf_text,
                tasks_text=tasks_text,
                constraints_text=constraints_text,
                x50_766_hsc=get_prompt("referential.x50_766.en") or "",
            )
            system_msg = (
                "You are an HR expert in Socio-Cognitive Abilities (SCA) XP X50-766. "
                "You MUST respond only in valid JSON. No text outside JSON, no markdown."
            )
        else:
            perf_text = "\n".join(perf_lines) if perf_lines else "(Aucune performance renseignée)"
            prompt = get_prompt(
                "propose.softskills.header.fr",
                activity_name=activity_name,
                perf_text=perf_text,
                tasks_text=tasks_text,
                constraints_text=constraints_text,
                x50_766_hsc=get_prompt("referential.x50_766.fr") or "",
            )
            system_msg = (
                "Tu es un assistant RH expert en habiletés sociocognitives X50-766. "
                "Tu DOIS répondre uniquement en JSON valide. "
                "Jamais de texte extérieur, jamais de markdown."
            )

        resp = client.chat.completions.create(
            model=ai_model(),
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
        )

        text = resp.choices[0].message.content.strip()
        cleaned_text = clean_json_response(text)

        proposals = []
        parsed_ok = False

        try:
            data = json.loads(cleaned_text)
            if isinstance(data, dict):
                data = [data]

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

            for item in data:
                raw_niveau = item.get("niveau", "2")
                if isinstance(raw_niveau, str):
                    num = re.findall(r"\d", raw_niveau)
                    raw_niveau = num[0] if num else "2"
                elif isinstance(raw_niveau, int):
                    raw_niveau = str(raw_niveau)

                default_lvl = "2 (Developing)" if lang == 'en' else "2 (Acquisition)"
                level = niveau_map.get(raw_niveau, default_lvl)

                proposals.append({
                    "habilete": item.get("habilete", "Ability" if lang == 'en' else "Habileté"),
                    "niveau": level,
                    "justification": item.get("justification", ""),
                })

            parsed_ok = True

        except Exception as e:
            current_app.logger.warning(f"[HSC JSON FAIL] {e} | TEXT={cleaned_text[:200]}")

        fallback_level = "2 (Developing)" if lang == 'en' else "2 (Acquisition)"
        if not parsed_ok or not proposals:
            lines = [
                l.strip("-•* ").strip()
                for l in text.splitlines()
                if l.strip() and not l.strip().startswith("```")
            ]
            for line in lines:
                if len(line) > 3:
                    proposals.append({
                        "habilete": line[:100],
                        "niveau": fallback_level,
                        "justification": "",
                    })

        if not proposals:
            if lang == 'en':
                proposals = [{"habilete": "Professional Communication", "niveau": fallback_level, "justification": "Basic ability required for the activity."}]
            else:
                proposals = [{"habilete": "Communication professionnelle", "niveau": fallback_level, "justification": "Habileté de base requise pour l'activité."}]

        return jsonify({"proposals": proposals}), 200

    except Exception as e:
        current_app.logger.exception(e)
        lang = session.get('lang', 'fr')
        return jsonify({
            "proposals": [
                {
                    "habilete": "Ability not determined (server error)." if lang == 'en' else "Habileté non déterminée (erreur serveur).",
                    "niveau": "2 (Developing)" if lang == 'en' else "2 (Acquisition)",
                    "justification": "",
                }
            ],
            "error": str(e),
        }), 200
