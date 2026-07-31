from flask import Blueprint, request, jsonify, current_app, session
from Code.prompts import get_prompt, prompts_available
import json
import re
from .propose_common import openai_client_or_none

bp_propose_aptitudes = Blueprint("propose_aptitudes", __name__)




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


def build_activity_summary(activity):
    parts = []
    desc = activity.get("description", "")
    if desc:
        parts.append(desc)

    tools = activity.get("tools") or activity.get("outils") or []
    if tools:
        tool_strs = [str(t) for t in tools]
        parts.append(f"Outils : {', '.join(tool_strs)}")

    constraints = activity.get("constraints") or []
    if constraints:
        c_strs = [str(c) for c in constraints]
        parts.append(f"Contraintes : {', '.join(c_strs)}")

    tasks = activity.get("tasks") or []
    if tasks:
        for i, t in enumerate(tasks, 1):
            if isinstance(t, dict):
                parts.append(f"T{i}: {t.get('description', str(t))}")
            else:
                parts.append(f"T{i}: {t}")

    outgoing = activity.get("outgoing") or []
    for o in outgoing:
        perf = o.get("performance")
        if perf:
            parts.append(f"Performance : {perf.get('name', '')} - {perf.get('description', '')}")

    return "\n".join(parts) if parts else "Non renseigné"


@bp_propose_aptitudes.route("/propose_aptitudes/propose", methods=["POST"])
def propose_aptitudes():
    try:
        activity = request.get_json(force=True) or {}
        client, err = openai_client_or_none()
        if client is None:
            return jsonify({"proposals": {}, "source": err}), 200

        activity_name = activity.get("name") or activity.get("title") or "Activité sans nom"
        activity_summary = build_activity_summary(activity)
        competences_text = activity.get("competences_text") or "Non renseigné"
        savoirs_text = activity.get("savoirs_text") or "Non renseigné"
        savoir_faire_text = activity.get("savoir_faire_text") or "Non renseigné"
        hsc_context = activity.get("hsc_context") or "Non renseigné"

        prompt = get_prompt(
            "propose.aptitudes.inclusion_scoring",
            activity_name=activity_name,
            activity_summary=activity_summary,
            competences_text=competences_text,
            savoirs_text=savoirs_text,
            savoir_faire_text=savoir_faire_text,
            hsc_context=hsc_context,
        )
        if prompt is None:
            return jsonify({"proposals": {}, "source": "prompts-unavailable"}), 200

        lang = session.get('lang', 'fr')
        lang_instr = "Respond in English (risque, leviers, profils fields)." if lang == 'en' else "Réponds en français (champs risque, leviers, profils)."
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Tu es un expert en analyse du travail, prevention sante/securite et inclusion. Tu reponds UNIQUEMENT en JSON valide, sans markdown ni texte supplementaire. {lang_instr}"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()
        cleaned = clean_json_response(text)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as e:
            current_app.logger.warning(f"[INCLUSION SCORING JSON FAIL] {e} | TEXT={cleaned[:300]}")
            return jsonify({"proposals": {}, "error": f"Erreur parsing JSON: {str(e)}"}), 200

        return jsonify({"proposals": result}), 200

    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"proposals": {}, "error": str(e)}), 200


@bp_propose_aptitudes.route("/propose_aptitudes/feasibility", methods=["POST"])
def propose_feasibility():
    try:
        data = request.get_json(force=True) or {}
        client, err = openai_client_or_none()
        if client is None:
            return jsonify({"result": {}, "source": err}), 200

        activity_name = data.get("activity_name") or "Activité sans nom"
        inclusion_scoring_json = data.get("inclusion_scoring_json") or "{}"
        if isinstance(inclusion_scoring_json, dict):
            inclusion_scoring_json = json.dumps(inclusion_scoring_json, ensure_ascii=False, indent=2)

        profil = data.get("profil_fonctionnel") or {}
        vision = profil.get("vision", "inconnu")
        audition = profil.get("audition", "inconnu")
        motricite_fine = profil.get("motricite_fine", "inconnu")
        mobilite_posture = profil.get("mobilite_posture", "inconnu")
        endurance = profil.get("endurance", "inconnu")
        sensibilite_env = profil.get("sensibilite_env", "inconnu")
        commentaire_court = data.get("commentaire_court") or ""

        assistive_products = data.get("assistive_products") or []
        if isinstance(assistive_products, list):
            assistive_products_text = "\n".join(f"- {p}" for p in assistive_products) if assistive_products else "Aucune aide renseignée"
        else:
            assistive_products_text = str(assistive_products)

        prompt = get_prompt(
            "propose.aptitudes.handicap_icf",
            activity_name=activity_name,
            inclusion_scoring_json=inclusion_scoring_json,
            vision=vision,
            audition=audition,
            motricite_fine=motricite_fine,
            mobilite_posture=mobilite_posture,
            endurance=endurance,
            sensibilite_env=sensibilite_env,
            commentaire_court=commentaire_court,
            assistive_products_text=assistive_products_text,
        )
        if prompt is None:
            return jsonify({"result": {}, "source": "prompts-unavailable"}), 200

        lang2 = session.get('lang', 'fr')
        lang_instr2 = "Respond in English (text fields)." if lang2 == 'en' else "Réponds en français (champs texte)."
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Tu es un expert prevention et inclusion. Tu reponds UNIQUEMENT en JSON valide, sans markdown ni texte supplementaire. {lang_instr2}"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = resp.choices[0].message.content.strip()
        cleaned = clean_json_response(text)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as e:
            current_app.logger.warning(f"[FEASIBILITY JSON FAIL] {e} | TEXT={cleaned[:300]}")
            return jsonify({"result": {}, "error": f"Erreur parsing JSON: {str(e)}"}), 200

        return jsonify({"result": result}), 200

    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"result": {}, "error": str(e)}), 200
