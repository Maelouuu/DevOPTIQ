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
from Code.models.models import (Activities, Data, CompetencyEvaluation, UserRole, activity_roles)
from Code.competences_acces import peut_noter
from Code.permissions import current_user
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


def _reference_eval(user_id, activity_id, data_id):
    """Évaluation de RÉFÉRENCE d'un résultat = dernière validée par un Garant ou
    Manager. L'auto-évaluation reste visible mais ne valide pas seule (CDC 3.6)."""
    q = CompetencyEvaluation.query.filter_by(
        user_id=user_id, activity_id=activity_id, item_type=RESULT_ITEM_TYPE, item_id=data_id)
    best = None
    for ev in q.all():
        if ev.eval_number in VALIDATING and ev.mastery_level is not None:
            if best is None or (ev.evaluated_at or datetime.min) >= (best.evaluated_at or datetime.min):
                best = ev
    return best


def _reference_level(user_id, activity_id, data_id):
    best = _reference_eval(user_id, activity_id, data_id)
    return best.mastery_level if best else None


def _self_eval(user_id, activity_id, data_id):
    """L'auto-évaluation du collaborateur (eval_number '0'). Elle est VISIBLE des
    deux côtés et ne vaut jamais niveau officiel."""
    return CompetencyEvaluation.query.filter_by(
        user_id=user_id, activity_id=activity_id, item_type=RESULT_ITEM_TYPE,
        item_id=data_id, eval_number="0").first()


def _self_level(user_id, activity_id, data_id):
    ev = _self_eval(user_id, activity_id, data_id)
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
    per_result, levels, autos, complete = [], [], [], True
    for d in results:
        ev = _reference_eval(user_id, activity_id, d.id)
        ref = ev.mastery_level if ev else None
        auto = _self_eval(user_id, activity_id, d.id)
        per_result.append({
            "data_id": d.id, "name": d.name,
            "minimum_performance_text": d.minimum_performance_text or "",
            "self_level": auto.mastery_level if auto else None,
            "self_label": level_label(auto.mastery_level if auto else None),
            "self_evidence": (auto.evidence if auto else None) or "",
            "demonstrated_level": ref,
            "demonstrated_label": level_label(ref),
            # ⚠️ La preuve était ENREGISTRÉE mais jamais renvoyée : l'écran la
            # rouvrait vide et le prochain enregistrement l'effaçait.
            "evidence": (ev.evidence if ev else None) or "",
        })
        if ref is None:
            complete = False
        else:
            levels.append(ref)
        if auto is not None and auto.mastery_level is not None:
            autos.append(auto.mastery_level)
    # niveau global = MINIMUM des résultats ; NULL si un résultat n'est pas encore évalué
    global_level = min(levels) if (levels and complete) else None
    # L'auto-évaluation suit la MÊME règle du minimum, mais ne vaut jamais niveau
    # officiel : c'est un repère, pour le collaborateur comme pour son
    # développeur de compétences (CDC 3.6).
    self_global = min(autos) if (autos and len(autos) == len(results)) else None
    req = required_level(activity_id, role_id)
    return {
        "self_global_level": self_global, "self_global_label": level_label(self_global),
        "n_self_evaluated": len(autos),
        "activity_id": activity_id, "role_id": role_id,
        "required_level": req, "required_label": level_label(req),
        "global_level": global_level, "global_label": level_label(global_level),
        "gap": (global_level - req) if (global_level is not None and req is not None) else None,
        "color": color_for(global_level, req),
        "n_results": len(results),
        # Combien de résultats sont ÉVALUÉS : sans ce chiffre, un niveau global
        # vide ne se distingue pas d'une activité qu'on n'a pas commencée.
        "n_evaluated": len(levels),
        "n_at_required": sum(1 for l in levels if req is None or l >= req),
        "complete": complete,
        "results": per_result,
    }


def dashboard_rows(user_id, role_id):
    """Les lignes d'activité d'un couple (collaborateur, rôle).

    Extrait de la route pour que la SYNTHÈSE tous rôles s'appuie exactement sur
    le même calcul : deux implémentations donneraient deux chiffres, et c'est
    précisément ce que la vue d'ensemble ne doit pas faire.
    """
    from Code.models.models import Competency, Entity
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
            from Code.routes.technical_domains import domain_status
            tech = domain_status(user_id, role_id, act.id)
        except Exception:
            tech = "none"
        rows.append({
            "activity_id": act.id, "activity_name": act.name,
            "competence": comp.description if comp else None,
            "required_level": st["required_level"], "required_label": st["required_label"],
            "demonstrated_level": st["global_level"], "demonstrated_label": st["global_label"],
            "gap": st["gap"], "color": st["color"],
            "n_results": st["n_results"], "n_evaluated": st["n_evaluated"],
            "n_at_required": st["n_at_required"],
            "complete": st["complete"], "technicity": tech, "technicity_alert": tech == "gap",
            "last_evaluation": last.isoformat() if last else None,
            "self_level": st["self_global_level"], "self_label": st["self_global_label"],
        })
    rows.sort(key=lambda r: r["activity_name"].lower())
    return rows


@mastery_bp.route("/dashboard/<int:user_id>/<int:role_id>", methods=["GET"])
def dashboard(user_id, role_id):
    """Tableau principal (CDC 6.3) : activités du rôle, avec pour chacune niveau requis,
    niveau démontré (min des résultats), écart, résultats au requis, dernière évaluation."""
    from Code.models.models import Role
    from Code.competences_acces import peut_lire
    role = Role.query.get(role_id)
    if not role:
        return jsonify({"error": "role_not_found"}), 404
    if not peut_lire(current_user(), user_id):
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"user_id": user_id, "role_id": role_id, "role_name": role.name,
                    "activities": dashboard_rows(user_id, role_id)}), 200


def couverture(rows):
    """Part du niveau requis réellement tenue, en pourcentage.

    ⚠️ Calculée sur les seules activités ÉVALUÉES. Compter une activité non
    évaluée comme un zéro reviendrait à confondre « pas démontré » et « pas
    encore regardé » — la distinction que tout le module tient par ailleurs
    (NULL ≠ 0). Le nombre d'activités évaluées est renvoyé à côté pour que le
    pourcentage se lise avec sa base.

    Un dépassement ne compense pas un manque : on plafonne chaque activité à son
    requis (`min`), sinon un expert sur une activité masquerait une lacune sur
    une autre.
    """
    tenu = vise = 0
    for r in rows:
        req, dem = r["required_level"], r["demonstrated_level"]
        if req is None or not req or dem is None:
            continue
        vise += req
        tenu += min(dem, req)
    return round(tenu / vise * 100) if vise else None


def categorie_activite(row):
    """Les quatre états d'une activité, tels que l'écran les compte. Écrits ICI
    et pas dans le JS : la synthèse par rôle et la liste détaillée doivent
    trancher pareil, sinon les chiffres du haut contredisent les lignes du bas."""
    if not row["n_results"]:
        return "setup"
    dem = row["demonstrated_level"]
    if dem is None:
        return "todo"
    if dem < 2:
        return "gap"
    req = row["required_level"]
    if req is not None and dem < req:
        return "gap"
    return "held"


@mastery_bp.route("/synthese/<int:user_id>", methods=["GET"])
def synthese(user_id):
    """Vue d'ensemble d'un collaborateur : TOUS ses rôles d'un coup.

    On entrait directement dans le détail d'un rôle, sans jamais voir où la
    personne en est globalement. Le niveau d'un rôle suit la même règle que
    celui d'une activité — le MINIMUM, jamais la moyenne : un rôle n'est pas
    tenu à moitié.

    La note qui compte est celle du développeur de compétences. L'auto-évaluation
    est renvoyée à côté, comme repère, jamais comme résultat.
    """
    from Code.models.models import Role, User
    from Code.competences_acces import peut_lire

    cible = User.query.get(user_id)
    if not cible:
        return jsonify({"error": "user_not_found"}), 404
    if not peut_lire(current_user(), user_id):
        return jsonify({"error": "forbidden"}), 403

    roles, profil = [], []
    for ur in UserRole.query.filter_by(user_id=user_id).all():
        role = Role.query.get(ur.role_id)
        if role is None:
            continue
        rows = dashboard_rows(user_id, role.id)
        compte = {"held": 0, "gap": 0, "todo": 0, "setup": 0}
        niveaux, autos, requis, retards = [], [], [], []
        for r in rows:
            compte[categorie_activite(r)] += 1
            if r["demonstrated_level"] is not None:
                niveaux.append(r["demonstrated_level"])
            if r["self_level"] is not None:
                autos.append(r["self_level"])
            if r["required_level"] is not None:
                requis.append(r["required_level"])
            if r["gap"] is not None and r["gap"] < 0:
                retards.append(r)
            # Le PROFIL : un axe par activité, pour le graphe de la vue
            # d'ensemble. Les niveaux bruts, pas des pourcentages — un radar sert
            # à voir une forme, et la forme du requis doit se superposer à celle
            # du démontré.
            profil.append({
                "activity_id": r["activity_id"], "activity_name": r["activity_name"],
                "role_id": role.id, "role_name": role.name,
                "required_level": r["required_level"],
                "demonstrated_level": r["demonstrated_level"],
                "self_level": r["self_level"], "gap": r["gap"],
            })
        # Niveau du rôle : le minimum, et seulement si TOUT est évalué — sinon
        # un rôle à moitié noté paraîtrait meilleur qu'il n'est.
        evaluables = [r for r in rows if r["n_results"]]
        complet = bool(evaluables) and len(niveaux) == len(evaluables)
        niveau = min(niveaux) if (niveaux and complet) else None
        req = min(requis) if requis else None
        roles.append({
            "role_id": role.id, "role_name": role.name,
            "n_activities": len(rows),
            "counts": compte,
            "level": niveau, "level_label": level_label(niveau),
            "self_level": (min(autos) if (autos and len(autos) == len(evaluables)) else None),
            "required_level": req, "required_label": level_label(req),
            "color": color_for(niveau, req),
            "gap": (niveau - req) if (niveau is not None and req is not None) else None,
            "n_gap": len(retards),
            "n_evaluated": len(niveaux),
            "couverture": couverture(rows),
            # De quoi proposer un plan sans recharger : les activités en retard.
            "gap_activities": [{"activity_id": r["activity_id"], "activity_name": r["activity_name"],
                                "demonstrated_level": r["demonstrated_level"],
                                "required_level": r["required_level"], "gap": r["gap"]}
                               for r in retards],
        })
    roles.sort(key=lambda r: r["role_name"].lower())
    total = {"held": 0, "gap": 0, "todo": 0, "setup": 0}
    for r in roles:
        for k in total:
            total[k] += r["counts"][k]
    # Une activité peut être portée par plusieurs rôles : sur le profil global
    # elle ne compte qu'une fois, sinon la forme du graphe dirait surtout
    # combien de rôles se partagent la même activité.
    unique, vues = [], set()
    for a in profil:
        if a["activity_id"] in vues:
            continue
        vues.add(a["activity_id"])
        unique.append(a)
    unique.sort(key=lambda a: ((a["gap"] if a["gap"] is not None else 99),
                               a["activity_name"].lower()))
    return jsonify({
        "user_id": user_id,
        "user_name": f"{cible.first_name or ''} {cible.last_name or ''}".strip(),
        "roles": roles, "totals": total,
        "n_activities": sum(r["n_activities"] for r in roles),
        "n_activities_uniques": len(unique),
        "couverture": couverture(unique),
        "profil": unique,
    }), 200


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
    # ⚠️ Cette route n'avait AUCUN contrôle : tout compte connecté pouvait poser
    # n'importe quel niveau sur n'importe qui — y compris se décerner un niveau
    # officiel. Le masquage dans l'écran n'est pas une sécurité.
    ok, motif = peut_noter(current_user(), uid, evaluator)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
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
