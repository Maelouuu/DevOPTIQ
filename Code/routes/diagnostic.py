# Code/routes/diagnostic.py
# CDC 6 (V1.1) — Diagnostic d'un écart sur un RÉSULTAT + plan d'accompagnement.
# L'évaluation commence par le résultat ; le diagnostic S/SF/HSC ne vient QU'ENSUITE, quand
# un résultat n'est pas tenu au niveau requis. Trois familles de causes ; seule « Capacité à
# agir » justifie un plan de développement individuel (CDC 6.8).
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session
from Code.prompts import get_prompt, prompts_available
from Code.extensions import db
from Code.models.models import (Activities, Data, CompetencyEvaluation, ResultCapabilityLink,
                                ResultDiagnostic, Savoir, SavoirFaire, Softskill)
from Code.routes.propose_common import ai_model, openai_client_or_none
from Code.routes.mastery import (_reference_level, required_level, level_label, MASTERY_SCALE)

diagnostic_bp = Blueprint("diagnostic", __name__, url_prefix="/diagnostic")

# Trois familles de causes (CDC 6.6). Codes internes, jamais affichés tels quels.
FAMILIES = {
    "WORK_ARCHITECTURE": {
        "fr": "Architecture du travail", "en": "Work architecture",
        "desc_fr": "Activités, tâches, enchaînement, responsabilités, flux de données, rythme ou déclenchement.",
        "desc_en": "Activities, tasks, sequencing, responsibilities, data flows, rhythm or triggering."},
    "ABILITY_TO_ACT": {
        "fr": "Capacité à agir", "en": "Ability to act",
        "desc_fr": "Savoirs, savoir-faire, HSC, niveau de maîtrise, disponibilité des ressources, mobilisation.",
        "desc_en": "Knowledge, know-how, soft skills, mastery level, resource availability, mobilisation."},
    "EXECUTION_CONDITIONS": {
        "fr": "Conditions d'exécution", "en": "Execution conditions",
        "desc_fr": "Outils, méthodes, règles, standards, référentiels, environnement d'exécution.",
        "desc_en": "Tools, methods, rules, standards, references, execution environment."},
}
INDIVIDUAL_FAMILY = "ABILITY_TO_ACT"   # seule famille → plan de développement individuel
EVAL_ITEM_TYPE = {"SAVOIR": "savoirs", "SAVOIR_FAIRE": "savoir_faires", "HSC": "hsc"}
CAP_LABEL = {"SAVOIR": {"fr": "Savoir", "en": "Knowledge"},
             "SAVOIR_FAIRE": {"fr": "Savoir-faire", "en": "Know-how"},
             "HSC": {"fr": "HSC", "en": "Soft skill"}}


def _lang():
    return session.get("lang", "fr")


def _gap_status(demonstrated, required, lang):
    """CDC 6.5 : état de l'écart d'un résultat."""
    if demonstrated is None:
        return {"code": "not_assessed", "label": ("Non évalué" if lang == "fr" else "Not assessed")}
    if demonstrated < 2:
        return {"code": "autonomy_not_demonstrated",
                "label": ("Autonomie non démontrée" if lang == "fr" else "Autonomy not demonstrated")}
    if required is not None and demonstrated < required:
        return {"code": "development_gap", "label": ("Écart de développement" if lang == "fr" else "Development gap")}
    return {"code": "met", "label": ("Niveau attendu tenu" if lang == "fr" else "Required level met")}


def _capability_demonstrated(user_id, activity_id, item_type, item_id):
    """Niveau démontré d'un S/SF/HSC = meilleur niveau validé dans les évaluations existantes
    (CompetencyEvaluation.note, item_type 'savoirs'/'savoir_faires'/'hsc')."""
    et = EVAL_ITEM_TYPE.get(item_type)
    if not et:
        return None
    best = None
    for ev in CompetencyEvaluation.query.filter_by(
            user_id=user_id, activity_id=activity_id, item_type=et, item_id=item_id).all():
        try:
            lvl = int(str(ev.note).strip())
        except (TypeError, ValueError):
            continue
        best = lvl if best is None else max(best, lvl)
    return best


def _item_label(item_type, item_id):
    m = {"SAVOIR": Savoir, "SAVOIR_FAIRE": SavoirFaire, "HSC": Softskill}.get(item_type)
    if not m:
        return None
    o = m.query.get(item_id)
    if not o:
        return None
    return o.habilete if item_type == "HSC" else o.description


def _linked_capabilities(user_id, activity_id, data_id, lang):
    """S/SF/HSC reliés à CE résultat (result_capability_links) avec niveau démontré vs requis.
    Les items non reliés au résultat ne polluent pas le diagnostic (CDC 6.7)."""
    out = []
    for lk in ResultCapabilityLink.query.filter_by(activity_id=activity_id, data_id=data_id).all():
        dem = _capability_demonstrated(user_id, activity_id, lk.item_type, lk.item_id)
        out.append({
            "link_id": lk.id, "item_type": lk.item_type,
            "type_label": CAP_LABEL.get(lk.item_type, {}).get(lang, lk.item_type),
            "item_id": lk.item_id, "label": _item_label(lk.item_type, lk.item_id),
            "required_level": lk.required_level, "demonstrated_level": dem,
            "gap": (dem - lk.required_level) if (dem is not None and lk.required_level is not None) else None,
        })
    return out


@diagnostic_bp.route("/families", methods=["GET"])
def families():
    lang = _lang()
    return jsonify({"families": [
        {"code": k, "label": v[lang], "description": v[f"desc_{lang}"]} for k, v in FAMILIES.items()]}), 200


@diagnostic_bp.route("/<int:user_id>/<int:activity_id>/<int:data_id>", methods=["GET"])
def get_diagnostic(user_id, activity_id, data_id):
    """État du diagnostic d'un résultat pour un individu."""
    d = Data.query.get(data_id)
    if not d or d.semantic_nature != "RESULT":
        return jsonify({"error": "not_a_result"}), 400
    lang = _lang()
    role_id = request.args.get("role_id", type=int)
    dem = _reference_level(user_id, activity_id, data_id)
    req = required_level(activity_id, role_id)
    saved = ResultDiagnostic.query.filter_by(user_id=user_id, activity_id=activity_id, data_id=data_id).first()
    fams = json.loads(saved.families) if (saved and saved.families) else []
    return jsonify({
        "result": {"data_id": data_id, "name": d.name,
                   "minimum_performance_text": d.minimum_performance_text or ""},
        "demonstrated_level": dem, "demonstrated_label": level_label(dem, lang),
        "required_level": req, "required_label": level_label(req, lang),
        "status": _gap_status(dem, req, lang),
        "families": fams, "note": (saved.note if saved else ""),
        "capabilities": _linked_capabilities(user_id, activity_id, data_id, lang),
        "individual_family": INDIVIDUAL_FAMILY,
    }), 200


@diagnostic_bp.route("/save", methods=["POST"])
def save_diagnostic():
    """Valide les familles de causes d'un écart (CDC 6.6)."""
    p = request.get_json(force=True) or {}
    uid, aid, did = p.get("user_id"), p.get("activity_id"), p.get("data_id")
    if not (uid and aid and did):
        return jsonify({"error": "invalid_payload"}), 400
    fams = [f for f in (p.get("families") or []) if f in FAMILIES]
    act = Activities.query.get(aid)
    row = ResultDiagnostic.query.filter_by(user_id=uid, activity_id=aid, data_id=did).first()
    if not row:
        row = ResultDiagnostic(user_id=uid, activity_id=aid, data_id=did,
                               entity_id=act.entity_id if act else None)
        db.session.add(row)
    row.families = json.dumps(fams)
    row.note = (p.get("note") or "").strip() or None
    row.validated_by = p.get("validated_by")
    db.session.commit()
    return jsonify({"ok": True, "families": fams}), 200




@diagnostic_bp.route("/plan", methods=["POST"])
def generate_plan():
    """Génère un plan d'accompagnement (CDC 6.8). RÈGLE IMPÉRATIVE : si l'écart ne relève PAS de la
    Capacité à agir (Architecture ou Conditions d'exécution), pas de plan de formation automatique."""
    p = request.get_json(force=True) or {}
    uid, aid, did = p.get("user_id"), p.get("activity_id"), p.get("data_id")
    role_id = p.get("role_id")
    if not (uid and aid and did):
        return jsonify({"error": "invalid_payload"}), 400
    lang = _lang()
    saved = ResultDiagnostic.query.filter_by(user_id=uid, activity_id=aid, data_id=did).first()
    fams = json.loads(saved.families) if (saved and saved.families) else (p.get("families") or [])
    if INDIVIDUAL_FAMILY not in fams:
        return jsonify({"plan": None, "no_individual_plan": True,
                        "message": ("L'écart ne relève pas prioritairement d'un développement individuel."
                                    if lang == "fr" else
                                    "The gap is not primarily an individual development issue.")}), 200
    d = Data.query.get(did)
    dem = _reference_level(uid, aid, did)
    req = required_level(aid, role_id)
    caps = [c for c in _linked_capabilities(uid, aid, did, lang)
            if c["gap"] is None or c["gap"] < 0]   # capacités en écart
    client, err = openai_client_or_none()
    ctx = {
        "result": d.name if d else "", "current_level": dem, "target_level": req,
        "minimum_performance": (d.minimum_performance_text if d else "") or "",
        "capabilities_in_gap": [{"type": c["type_label"], "label": c["label"],
                                 "current": c["demonstrated_level"], "required": c["required_level"]} for c in caps],
    }
    plan_system = get_prompt("diagnostic.plan.system")
    if client is None or plan_system is None:
        return jsonify({"plan": None, "source": err or "no_ai", "context": ctx}), 200
    try:
        resp = client.chat.completions.create(
            model=ai_model(),
            messages=[{"role": "system", "content": plan_system},
                      {"role": "user", "content": "Contexte:\n" + json.dumps(ctx, ensure_ascii=False)
                                                  + "\nRéponds en " + ("français." if lang == "fr" else "English.")}],
            temperature=0.3, response_format={"type": "json_object"})
        raw = json.loads(resp.choices[0].message.content)
        return jsonify({"plan": raw.get("plan") or [], "source": "AI", "context": ctx}), 200
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({"plan": None, "source": "error", "error": str(e), "context": ctx}), 200
