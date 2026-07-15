# Code/routes/technical_domains.py
# CDC 4 (V1.1) — Domaines de technicité. Une même activité peut être exercée dans des
# contextes techniques différents (Plastic/Metal, Français/Maths…) sans dupliquer l'activité.
# Le niveau technique est un AXE SÉPARÉ du niveau de maîtrise de l'activité.
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from Code.extensions import db
from Code.models.models import (TechnicalDomain, ActivityTechnicalDomain,
    RoleActivityDomainRequirement, UserDomainLevel, Entity)

domains_bp = Blueprint("technical_domains", __name__, url_prefix="/domains")

# Échelle technique (CDC 4.4) — libellés distincts de l'échelle de maîtrise d'activité.
DOMAIN_SCALE = {
    0: {"fr": "Non démontré",     "en": "Not demonstrated"},
    1: {"fr": "Pratique guidée",  "en": "Guided practice"},
    2: {"fr": "Maîtrise autonome", "en": "Autonomous practice"},
    3: {"fr": "Maîtrise complexe", "en": "Advanced technical mastery"},
    4: {"fr": "Référence technique", "en": "Technical expert"},
}


def _lang():
    return session.get("lang", "fr")


def _dname(d, lang=None):
    lang = lang or _lang()
    return (d.name_en if lang == "en" and d.name_en else d.name_fr)


def domain_gap(user_id, role_id, activity_id):
    """True si un domaine requis (rôle × activité) présente un écart pour l'individu
    (niveau démontré < requis). Sert à l'alerte « Technicité » du tableau (CDC 6.3)."""
    reqs = RoleActivityDomainRequirement.query.filter_by(role_id=role_id, activity_id=activity_id).all()
    if not reqs:
        return False
    levels = {u.domain_id: u.demonstrated_level for u in UserDomainLevel.query.filter_by(user_id=user_id).all()}
    for r in reqs:
        if r.required_level is None:
            continue
        dem = levels.get(r.domain_id)
        if dem is None or dem < r.required_level:
            return True
    return False


@domains_bp.route("/scale", methods=["GET"])
def scale():
    lang = _lang()
    return jsonify({"scale": {str(k): v[lang] for k, v in DOMAIN_SCALE.items()}}), 200


@domains_bp.route("/list", methods=["GET"])
def list_domains():
    lang = _lang()
    q = TechnicalDomain.query
    eid = Entity.get_active_id()
    if eid:
        q = q.filter(TechnicalDomain.entity_id == eid)
    return jsonify({"domains": [{"id": d.id, "name": _dname(d, lang), "name_fr": d.name_fr,
                                 "name_en": d.name_en, "description": d.description, "active": bool(d.active)}
                                for d in q.filter(TechnicalDomain.active.isnot(False)).all()]}), 200


@domains_bp.route("/create", methods=["POST"])
def create_domain():
    p = request.get_json(force=True) or {}
    name_fr = (p.get("name_fr") or p.get("name") or "").strip()
    if not name_fr:
        return jsonify({"error": "empty_name"}), 400
    d = TechnicalDomain(entity_id=Entity.get_active_id(), name_fr=name_fr,
                        name_en=(p.get("name_en") or "").strip() or None,
                        description=(p.get("description") or "").strip() or None, active=True)
    db.session.add(d)
    db.session.commit()
    return jsonify({"ok": True, "id": d.id}), 200


@domains_bp.route("/delete/<int:domain_id>", methods=["POST"])
def delete_domain(domain_id):
    d = TechnicalDomain.query.get(domain_id)
    if d:
        d.active = False   # désactivation (conserve l'historique)
        db.session.commit()
    return jsonify({"ok": True}), 200


@domains_bp.route("/activity/<int:activity_id>", methods=["GET"])
def activity_domains(activity_id):
    """Domaines liés à une activité (+ niveau requis par rôle et démontré par user si fournis)."""
    lang = _lang()
    role_id = request.args.get("role_id", type=int)
    user_id = request.args.get("user_id", type=int)
    links = ActivityTechnicalDomain.query.filter_by(activity_id=activity_id).all()
    reqs = {r.domain_id: r.required_level for r in
            RoleActivityDomainRequirement.query.filter_by(role_id=role_id, activity_id=activity_id).all()} if role_id else {}
    ulv = {u.domain_id: u.demonstrated_level for u in
           UserDomainLevel.query.filter_by(user_id=user_id).all()} if user_id else {}
    out = []
    for lk in links:
        d = TechnicalDomain.query.get(lk.domain_id)
        if not d:
            continue
        req, dem = reqs.get(d.id), ulv.get(d.id)
        out.append({"domain_id": d.id, "name": _dname(d, lang),
                    "required_level": req, "required_label": DOMAIN_SCALE.get(req, {}).get(lang) if req is not None else None,
                    "demonstrated_level": dem, "demonstrated_label": DOMAIN_SCALE.get(dem, {}).get(lang) if dem is not None else None,
                    "gap": (dem - req) if (dem is not None and req is not None) else None})
    return jsonify({"activity_id": activity_id, "domains": out}), 200


@domains_bp.route("/activity/<int:activity_id>/link", methods=["POST"])
def link_domain(activity_id):
    p = request.get_json(force=True) or {}
    did = p.get("domain_id")
    if not did:
        return jsonify({"error": "invalid"}), 400
    if p.get("unlink"):
        ActivityTechnicalDomain.query.filter_by(activity_id=activity_id, domain_id=did).delete()
    elif not ActivityTechnicalDomain.query.filter_by(activity_id=activity_id, domain_id=did).first():
        db.session.add(ActivityTechnicalDomain(activity_id=activity_id, domain_id=did))
    db.session.commit()
    return jsonify({"ok": True}), 200


@domains_bp.route("/required", methods=["POST"])
def set_required():
    """Niveau technique requis d'un domaine pour un couple Rôle × Activité."""
    p = request.get_json(force=True) or {}
    rid, aid, did = p.get("role_id"), p.get("activity_id"), p.get("domain_id")
    lvl = p.get("required_level")
    if not (rid and aid and did) or (lvl is not None and lvl not in DOMAIN_SCALE):
        return jsonify({"error": "invalid"}), 400
    row = RoleActivityDomainRequirement.query.filter_by(role_id=rid, activity_id=aid, domain_id=did).first()
    if not row:
        row = RoleActivityDomainRequirement(role_id=rid, activity_id=aid, domain_id=did)
        db.session.add(row)
    row.required_level = lvl
    db.session.commit()
    return jsonify({"ok": True}), 200


@domains_bp.route("/user_level", methods=["POST"])
def set_user_level():
    """Niveau technique démontré d'un individu sur un domaine."""
    p = request.get_json(force=True) or {}
    uid, did = p.get("user_id"), p.get("domain_id")
    lvl = p.get("demonstrated_level")
    if not (uid and did) or (lvl is not None and lvl not in DOMAIN_SCALE):
        return jsonify({"error": "invalid"}), 400
    row = UserDomainLevel.query.filter_by(user_id=uid, domain_id=did).first()
    if not row:
        row = UserDomainLevel(user_id=uid, domain_id=did)
        db.session.add(row)
    row.demonstrated_level = lvl
    row.evidence = (p.get("evidence") or "").strip() or None
    row.evaluated_at = datetime.utcnow()
    row.evaluator_user_id = p.get("evaluator_user_id")
    db.session.commit()
    return jsonify({"ok": True}), 200
