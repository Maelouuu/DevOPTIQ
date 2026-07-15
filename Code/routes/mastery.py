# Code/routes/mastery.py
# CDC 3 (V1.1) — Niveaux de maîtrise. Trois notions DISTINCTES :
#  - standard minimal de l'activité (Data.minimum_performance_text, cf. P1) ;
#  - niveau REQUIS par le rôle (activity_roles.required_mastery_level) ;
#  - niveau DÉMONTRÉ par l'individu (CompetencyEvaluation.mastery_level, par RÉSULTAT).
# Règles OPTIQ : niveau global d'activité = MINIMUM des résultats (jamais de moyenne) ;
# NULL (non évalué) ≠ 0 (non démontré) ; une meilleure performance n'augmente pas le niveau.
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from Code.extensions import db
from Code.models.models import (Activities, Data, CompetencyEvaluation, activity_roles)
from Code.routes.qualify_outputs import get_activity_outputs

mastery_bp = Blueprint("mastery", __name__, url_prefix="/mastery")

# Échelle de maîtrise de l'activité (CDC 3.2). NULL = non évalué (pas un niveau).
MASTERY_SCALE = {
    0: {"fr": "Non démontré",         "en": "Not demonstrated"},
    1: {"fr": "En acquisition",       "en": "Developing"},
    2: {"fr": "Autonome / compétent", "en": "Proficient / autonomous"},
    3: {"fr": "Maîtrise étendue",     "en": "Advanced mastery"},
    4: {"fr": "Expertise",            "en": "Expert"},
}
# Évaluateurs (CDC 3.6) — codes stockés dans eval_number.
EVALUATORS = {"0": "self", "1": "garant", "2": "manager", "3": "hr"}
VALIDATING = {"1", "2"}   # seuls Garant/Manager valident le niveau de référence
RESULT_ITEM_TYPE = "activity_results"


def _lang():
    return session.get("lang", "fr")


def level_label(lvl, lang=None):
    lang = lang or _lang()
    if lvl is None:
        return "Non évalué" if lang == "fr" else "Not assessed"
    return MASTERY_SCALE.get(lvl, {}).get(lang, "")


def _reference_level(user_id, activity_id, data_id):
    """Niveau démontré de RÉFÉRENCE d'un résultat = dernier niveau validé par un Garant ou
    Manager. L'auto-évaluation reste visible mais ne valide pas seule (CDC 3.6)."""
    q = CompetencyEvaluation.query.filter_by(
        user_id=user_id, activity_id=activity_id, item_type=RESULT_ITEM_TYPE, item_id=data_id)
    best = None
    for ev in q.all():
        if ev.eval_number in VALIDATING and ev.mastery_level is not None:
            if best is None or (ev.evaluated_at or datetime.min) >= (best.evaluated_at or datetime.min):
                best = ev
    return best.mastery_level if best else None


def _self_level(user_id, activity_id, data_id):
    ev = CompetencyEvaluation.query.filter_by(
        user_id=user_id, activity_id=activity_id, item_type=RESULT_ITEM_TYPE,
        item_id=data_id, eval_number="0").first()
    return ev.mastery_level if ev else None


def required_level(activity_id, role_id):
    if not role_id:
        return None
    row = db.session.execute(db.select(activity_roles.c.required_mastery_level).where(
        (activity_roles.c.activity_id == activity_id) & (activity_roles.c.role_id == role_id))).first()
    return row[0] if row else None


def color_for(demonstrated, required):
    """Couleur CALCULÉE (CDC 3.5) depuis le niveau démontré et l'écart au requis."""
    if demonstrated is None:
        return "grey"          # non évalué
    if demonstrated < 2:
        return "red"           # autonomie non démontrée
    if required is not None and demonstrated < required:
        return "orange"        # écart de développement
    return "green"             # niveau attendu tenu


def activity_mastery(user_id, activity_id, role_id=None):
    """État complet d'évaluation d'une activité pour un individu (base de l'écran P6)."""
    results = [d for d in get_activity_outputs(activity_id) if d.semantic_nature == "RESULT"]
    per_result, levels, complete = [], [], True
    for d in results:
        ref = _reference_level(user_id, activity_id, d.id)
        per_result.append({
            "data_id": d.id, "name": d.name,
            "minimum_performance_text": d.minimum_performance_text or "",
            "self_level": _self_level(user_id, activity_id, d.id),
            "demonstrated_level": ref,
            "demonstrated_label": level_label(ref),
        })
        if ref is None:
            complete = False
        else:
            levels.append(ref)
    # niveau global = MINIMUM des résultats ; NULL si un résultat n'est pas encore évalué
    global_level = min(levels) if (levels and complete) else None
    req = required_level(activity_id, role_id)
    return {
        "activity_id": activity_id, "role_id": role_id,
        "required_level": req, "required_label": level_label(req),
        "global_level": global_level, "global_label": level_label(global_level),
        "gap": (global_level - req) if (global_level is not None and req is not None) else None,
        "color": color_for(global_level, req),
        "n_results": len(results),
        "n_at_required": sum(1 for l in levels if req is None or l >= req),
        "complete": complete,
        "results": per_result,
    }


@mastery_bp.route("/dashboard/<int:user_id>/<int:role_id>", methods=["GET"])
def dashboard(user_id, role_id):
    """Tableau principal (CDC 6.3) : activités du rôle, avec pour chacune niveau requis,
    niveau démontré (min des résultats), écart, résultats au requis, dernière évaluation."""
    from Code.models.models import Role, Competency, Entity
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "role_not_found"}), 404
    q = db.session.query(Activities).join(
        activity_roles, activity_roles.c.activity_id == Activities.id).filter(
        activity_roles.c.role_id == role_id)
    active_entity_id = Entity.get_active_id()
    if active_entity_id:
        q = q.filter(Activities.entity_id == active_entity_id)
    rows = []
    for act in q.all():
        st = activity_mastery(user_id, act.id, role_id)
        comp = Competency.query.filter_by(activity_id=act.id).first()
        # dernière validation Garant/Manager parmi les résultats de l'activité
        last = None
        for ev in CompetencyEvaluation.query.filter_by(
                user_id=user_id, activity_id=act.id, item_type=RESULT_ITEM_TYPE).all():
            if ev.eval_number in VALIDATING and ev.evaluated_at:
                last = max(last, ev.evaluated_at) if last else ev.evaluated_at
        try:
            from Code.routes.technical_domains import domain_gap
            tech_alert = domain_gap(user_id, role_id, act.id)
        except Exception:
            tech_alert = False
        rows.append({
            "activity_id": act.id, "activity_name": act.name,
            "competence": comp.description if comp else None,
            "required_level": st["required_level"], "required_label": st["required_label"],
            "demonstrated_level": st["global_level"], "demonstrated_label": st["global_label"],
            "gap": st["gap"], "color": st["color"],
            "n_results": st["n_results"], "n_at_required": st["n_at_required"],
            "complete": st["complete"], "technicity_alert": tech_alert,
            "last_evaluation": last.isoformat() if last else None,
        })
    rows.sort(key=lambda r: r["activity_name"].lower())
    return jsonify({"user_id": user_id, "role_id": role_id, "role_name": role.name,
                    "activities": rows}), 200


@mastery_bp.route("/scale", methods=["GET"])
def scale():
    lang = _lang()
    return jsonify({
        "mastery": {str(k): v[lang] for k, v in MASTERY_SCALE.items()},
        "not_assessed": ("Non évalué" if lang == "fr" else "Not assessed"),
    }), 200


@mastery_bp.route("/required", methods=["POST"])
def set_required():
    """Fixe le niveau requis d'un couple Rôle × Activité (CDC 3.4)."""
    p = request.get_json(force=True) or {}
    aid, rid, lvl = p.get("activity_id"), p.get("role_id"), p.get("required_mastery_level")
    if not (aid and rid):
        return jsonify({"error": "invalid_payload"}), 400
    if lvl is not None and lvl not in MASTERY_SCALE:
        return jsonify({"error": "invalid_level"}), 400
    row = db.session.execute(db.select(activity_roles.c.activity_id).where(
        (activity_roles.c.activity_id == aid) & (activity_roles.c.role_id == rid))).first()
    if not row:
        return jsonify({"error": "association_not_found"}), 404
    db.session.execute(activity_roles.update().where(
        (activity_roles.c.activity_id == aid) & (activity_roles.c.role_id == rid)
    ).values(required_mastery_level=lvl))
    db.session.commit()
    return jsonify({"ok": True, "required_mastery_level": lvl}), 200


@mastery_bp.route("/activity/<int:user_id>/<int:activity_id>", methods=["GET"])
def get_activity(user_id, activity_id):
    if not Activities.query.get(activity_id):
        return jsonify({"error": "activity_not_found"}), 404
    role_id = request.args.get("role_id", type=int)
    return jsonify(activity_mastery(user_id, activity_id, role_id)), 200


@mastery_bp.route("/evaluate", methods=["POST"])
def evaluate():
    """Enregistre le niveau démontré d'un RÉSULTAT pour un individu (upsert par
    user × activity × result × évaluateur). Payload : {user_id, activity_id, data_id,
    evaluator('0'..'3'), mastery_level(0..4|null), evidence}."""
    p = request.get_json(force=True) or {}
    uid, aid, did = p.get("user_id"), p.get("activity_id"), p.get("data_id")
    evaluator = str(p.get("evaluator", "0"))
    if not (uid and aid and did) or evaluator not in EVALUATORS:
        return jsonify({"error": "invalid_payload"}), 400
    lvl = p.get("mastery_level")
    if lvl is not None and lvl not in MASTERY_SCALE:
        return jsonify({"error": "invalid_level"}), 400
    d = Data.query.get(did)
    if not d or d.semantic_nature != "RESULT":
        return jsonify({"error": "not_a_result"}), 400
    ev = CompetencyEvaluation.query.filter_by(
        user_id=uid, activity_id=aid, item_type=RESULT_ITEM_TYPE, item_id=did, eval_number=evaluator).first()
    now = datetime.utcnow()
    if not ev:
        ev = CompetencyEvaluation(
            user_id=uid, activity_id=aid, item_type=RESULT_ITEM_TYPE, item_id=did,
            eval_number=evaluator, note="")
        db.session.add(ev)
    ev.mastery_level = lvl
    ev.evidence = (p.get("evidence") or "").strip() or None
    ev.evaluated_at = now
    ev.evaluator_user_id = p.get("evaluator_user_id")
    db.session.commit()
    role_id = p.get("role_id")
    return jsonify({"ok": True, "state": activity_mastery(uid, aid, role_id)}), 200
