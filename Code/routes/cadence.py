# Code/routes/cadence.py
# CDC 5 (V1.1) — Cadences et cohérence des rythmes. Rend visibles les cycles différents des
# activités et signale les risques liés à la fréquence de mise à jour des données. L'analyse est
# en LECTURE SEULE : elle retourne des points de vigilance + une question OPTIQ, jamais de correction.
from flask import Blueprint, request, jsonify, session
from Code.extensions import db
from Code.models.models import Activities, Data, Link, Entity

cadence_bp = Blueprint("cadence", __name__, url_prefix="/cadence")

# Codes internes → libellés + badge (CDC 5.2). Le "rank" = fréquence relative (haut = fréquent) ;
# None = cadence spéciale (événementielle, projet, autre) non comparable directement.
CADENCES = {
    "EVENT":     {"fr": "Événementielle", "en": "Event-driven", "badge": "E", "rank": None},
    "CONTINUOUS": {"fr": "Continue",      "en": "Continuous",   "badge": "C", "rank": 100},
    "DAILY":     {"fr": "Journalière",    "en": "Daily",        "badge": "D", "rank": 90},
    "WEEKLY":    {"fr": "Hebdomadaire",   "en": "Weekly",       "badge": "W", "rank": 70},
    "MONTHLY":   {"fr": "Mensuelle",      "en": "Monthly",      "badge": "M", "rank": 50},
    "QUARTERLY": {"fr": "Trimestrielle",  "en": "Quarterly",    "badge": "Q", "rank": 30},
    "YEARLY":    {"fr": "Annuelle",       "en": "Yearly",       "badge": "Y", "rank": 10},
    "PROJECT":   {"fr": "Projet / jalon", "en": "Project / milestone", "badge": "P", "rank": None},
    "OTHER":     {"fr": "Autre",          "en": "Other",        "badge": "?", "rank": None},
}


def _lang():
    return session.get("lang", "fr")


@cadence_bp.route("/codes", methods=["GET"])
def codes():
    lang = _lang()
    return jsonify({"cadences": [{"code": k, "label": v[lang], "badge": v["badge"]} for k, v in CADENCES.items()]}), 200


@cadence_bp.route("/activity/<int:activity_id>", methods=["POST"])
def set_activity_cadence(activity_id):
    a = Activities.query.get(activity_id)
    if not a:
        return jsonify({"error": "not_found"}), 404
    p = request.get_json(force=True) or {}
    code = p.get("cadence_code")
    if code is not None and code not in CADENCES:
        return jsonify({"error": "invalid_code"}), 400
    a.cadence_code = code
    a.cadence_details = (p.get("cadence_details") or "").strip() or None
    db.session.commit()
    return jsonify({"ok": True}), 200


@cadence_bp.route("/data/<int:data_id>", methods=["POST"])
def set_data_cadence(data_id):
    d = Data.query.get(data_id)
    if not d:
        return jsonify({"error": "not_found"}), 404
    p = request.get_json(force=True) or {}
    code = p.get("update_cadence_code")
    if code is not None and code not in CADENCES:
        return jsonify({"error": "invalid_code"}), 400
    d.update_cadence_code = code
    d.max_age_hours = p.get("max_age_hours")
    db.session.commit()
    return jsonify({"ok": True}), 200


@cadence_bp.route("/consistency", methods=["GET"])
def consistency():
    """Analyse « Cohérence des rythmes » (CDC 5.5-5.6) — LECTURE SEULE. Détecte les écarts de
    rythme : une donnée mise à jour moins souvent que l'activité aval qui la consomme, etc.
    Vocabulaire imposé : « point de vigilance », « question à vérifier » (jamais « erreur »)."""
    lang = _lang()
    eid = Entity.get_active_id()
    lq = Link.query.filter(Link.source_data_id.isnot(None), Link.target_activity_id.isnot(None))
    if eid:
        lq = lq.filter(Link.entity_id == eid)
    warnings = []
    for lk in lq.all():
        d = Data.query.get(lk.source_data_id)
        a = Activities.query.get(lk.target_activity_id)
        if not d or not a:
            continue
        drank = CADENCES.get(d.update_cadence_code or "", {}).get("rank")
        arank = CADENCES.get(a.cadence_code or "", {}).get("rank")
        if drank is None or arank is None:
            continue
        if drank < arank:   # donnée moins fréquente que l'activité aval
            warnings.append({
                "source_data_id": d.id, "data_name": d.name,
                "target_activity_id": a.id, "activity_name": a.name,
                "data_cadence": CADENCES[d.update_cadence_code][lang],
                "activity_cadence": CADENCES[a.cadence_code][lang],
                "severity": "watch",
                "finding": (f"La donnée « {d.name} » est mise à jour {CADENCES[d.update_cadence_code][lang].lower()} "
                            f"alors que l'activité « {a.name} » fonctionne {CADENCES[a.cadence_code][lang].lower()}."
                            if lang == "fr" else
                            f"Data “{d.name}” is updated {CADENCES[d.update_cadence_code]['en'].lower()} "
                            f"while activity “{a.name}” operates {CADENCES[a.cadence_code]['en'].lower()}."),
                "optiq_question": ("Comment les évolutions significatives sont-elles captées entre deux mises à jour ?"
                                   if lang == "fr" else
                                   "How are significant changes captured between two updates?"),
            })
    return jsonify({"warnings": warnings, "count": len(warnings)}), 200
