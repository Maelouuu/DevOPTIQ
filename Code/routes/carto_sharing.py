"""Partage d'une cartographie : accès par rôle, et modifications proposées.

Deux mécanismes, un seul écran côté interface :

* **l'accès** — une carto peut devenir COMMUNE, et on l'ouvre à des rôles.
  Personne n'est nommé : qui reçoit le rôle demain y accède sans qu'on y
  revienne. Aucun rôle coché = ouverte à tous les comptes ;
* **les modifications** — sur une carto commune, un compte ordinaire dépose une
  proposition ; un champion ou un administrateur l'applique ou la refuse. La
  proposition appliquée écrit sur la carto commune, donc sur ce que TOUT LE
  MONDE voit : il n'y a rien à propager, c'est la même ligne.

Le diagramme proposé est recopié dans la proposition. Sans cette copie, une
proposition renverrait à un état qui a pu bouger entre son dépôt et son examen.
"""
import json
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from Code.carto_access import (
    access_summary, can_edit, can_manage_access, can_read, can_review, set_access,
)
from Code.extensions import db
from Code.models.models import CartoChangeRequest, Entity, User
from Code.permissions import current_user, is_admin, is_champion

carto_sharing_bp = Blueprint("carto_sharing", __name__, url_prefix="/cartography")


def _nom_compte(u):
    if not u:
        return "—"
    return f"{u.first_name} {u.last_name}".strip() or u.email


def _connecte():
    return current_user() if session.get("user_id") else None


def _diagram(donnees):
    try:
        return json.loads(donnees) if donnees else None
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────
# ACCÈS À UNE CARTO
# ─────────────────────────────────────────────

@carto_sharing_bp.route("/api/access/<int:entity_id>")
def get_access(entity_id):
    """État de partage d'une carto : commune ou non, rôles ouverts, mes droits."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    entity = db.session.get(Entity, entity_id)
    if not entity or not can_read(entity, user):
        return jsonify({"error": "Entité introuvable"}), 404

    return jsonify(access_summary(entity, user))


@carto_sharing_bp.route("/api/access/<int:entity_id>", methods=["POST"])
def post_access(entity_id):
    """Règle qui accède à la carto. Réservé aux champions et administrateurs."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    entity = db.session.get(Entity, entity_id)
    if not entity or not can_read(entity, user):
        return jsonify({"error": "Entité introuvable"}), 404
    if not can_manage_access(entity, user):
        return jsonify({"error": "Réservé aux champions et administrateurs",
                        "code": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    partage = bool(data.get("is_shared"))
    try:
        role_ids = [int(x) for x in (data.get("role_ids") or [])]
    except (TypeError, ValueError):
        return jsonify({"error": "Liste de rôles invalide"}), 400

    set_access(entity, partage, role_ids)
    db.session.commit()
    return jsonify({"status": "ok", **access_summary(entity, user)})


# ─────────────────────────────────────────────
# MODIFICATIONS PROPOSÉES
# ─────────────────────────────────────────────

def _resume_changement(avant, apres):
    """Ce qui change entre deux diagrammes, en langage de carto.

    On compare des FORMES et des FLÈCHES, pas du JSON : un examinateur veut
    savoir « 2 activités ajoutées, 1 renommée », pas lire un diff.
    """
    def index(diag):
        formes, liens = {}, set()
        for s in (diag or {}).get("shapes", []) or []:
            formes[str(s.get("id"))] = s
        for c in (diag or {}).get("connections", []) or []:
            liens.add((str(c.get("fromId")), str(c.get("toId"))))
        return formes, liens

    fa, la = index(avant)
    fb, lb = index(apres)

    ajoutees = [fb[i] for i in fb.keys() - fa.keys()]
    retirees = [fa[i] for i in fa.keys() - fb.keys()]
    renommees, deplacees = [], []
    for i in fa.keys() & fb.keys():
        a, b = fa[i], fb[i]
        if (a.get("label") or "") != (b.get("label") or ""):
            renommees.append({"from": a.get("label") or "", "to": b.get("label") or ""})
        elif a.get("x") != b.get("x") or a.get("y") != b.get("y"):
            deplacees.append(b.get("label") or "")

    def nom(s):
        return s.get("label") or s.get("name") or "—"

    return {
        "added": [nom(s) for s in ajoutees],
        "removed": [nom(s) for s in retirees],
        "renamed": renommees,
        "moved": deplacees,
        "links_added": len(lb - la),
        "links_removed": len(la - lb),
        "counts": {
            "shapes_before": len(fa), "shapes_after": len(fb),
            "links_before": len(la), "links_after": len(lb),
        },
    }


def _en_json(cr, user, avec_resume=False):
    out = {
        "id": cr.id,
        "entity_id": cr.entity_id,
        "entity_name": cr.entity.name if cr.entity else None,
        "author": _nom_compte(cr.author),
        "author_id": cr.author_id,
        "is_mine": bool(user and cr.author_id == user.id),
        "title": cr.title or "",
        "message": cr.message or "",
        "status": cr.status,
        "created_at": cr.created_at.isoformat() if cr.created_at else None,
        "reviewed_at": cr.reviewed_at.isoformat() if cr.reviewed_at else None,
        "reviewer": _nom_compte(cr.reviewer) if cr.reviewer_id else None,
        "review_comment": cr.review_comment or "",
    }
    if avec_resume:
        # Référence = ce que l'auteur avait sous les yeux quand il a proposé.
        # Sans base_diagram, on compare à la carto telle qu'elle est aujourd'hui.
        base = _diagram(cr.base_diagram)
        if base is None and cr.entity is not None:
            base = _diagram(cr.entity.optiqcarto_data)
        out["summary"] = _resume_changement(base, _diagram(cr.diagram))
    return out


@carto_sharing_bp.route("/api/changes")
def list_changes():
    """Propositions visibles : les miennes, plus celles que j'ai à examiner."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    q = CartoChangeRequest.query
    entity_id = request.args.get("entity_id", type=int)
    if entity_id:
        q = q.filter(CartoChangeRequest.entity_id == entity_id)
    statut = (request.args.get("status") or "").strip().lower()
    if statut in ("pending", "approved", "rejected"):
        q = q.filter(CartoChangeRequest.status == statut)

    arbitre = is_admin(user) or is_champion(user)
    if not arbitre:
        q = q.filter(CartoChangeRequest.author_id == user.id)

    demandes = q.order_by(CartoChangeRequest.created_at.desc()).limit(200).all()
    visibles = [cr for cr in demandes
                if cr.author_id == user.id or can_read(cr.entity, user)]
    return jsonify({
        "requests": [_en_json(cr, user) for cr in visibles],
        "can_review": arbitre,
        "pending": sum(1 for cr in visibles
                       if cr.status == "pending" and cr.author_id != user.id),
    })


@carto_sharing_bp.route("/api/changes/<int:req_id>")
def get_change(req_id):
    """Détail d'une proposition, avec le résumé de ce qu'elle change."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    cr = db.session.get(CartoChangeRequest, req_id)
    if not cr:
        return jsonify({"error": "Proposition introuvable"}), 404
    if cr.author_id != user.id and not can_review(cr.entity, user):
        return jsonify({"error": "Proposition introuvable"}), 404

    detail = _en_json(cr, user, avec_resume=True)
    detail["can_review"] = bool(can_review(cr.entity, user) and cr.status == "pending")
    return jsonify(detail)


@carto_sharing_bp.route("/api/changes", methods=["POST"])
def create_change():
    """Dépose une modification sur une carto commune, en attente d'examen."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    data = request.get_json(silent=True) or {}
    entity_id = data.get("entity_id")
    entity = db.session.get(Entity, int(entity_id)) if entity_id else None
    if entity is None:
        entity = Entity.get_active()
    if entity is None or not can_read(entity, user):
        return jsonify({"error": "Entité introuvable"}), 404
    if not entity.is_shared:
        return jsonify({"error": "Cette carto n'est pas commune : elle s'enregistre "
                                 "directement.", "code": "not_shared"}), 400

    diagram = data.get("diagram")
    if not isinstance(diagram, dict):
        return jsonify({"error": "Diagramme manquant"}), 400

    cr = CartoChangeRequest(
        entity_id=entity.id,
        author_id=user.id,
        title=(data.get("title") or "").strip()[:200] or None,
        message=(data.get("message") or "").strip() or None,
        diagram=json.dumps(diagram, ensure_ascii=False),
        # Référence de comparaison : la carto telle qu'elle est au moment du dépôt.
        base_diagram=entity.optiqcarto_data,
    )
    db.session.add(cr)
    db.session.commit()
    return jsonify({"status": "ok", "request": _en_json(cr, user)}), 201


@carto_sharing_bp.route("/api/changes/<int:req_id>/approve", methods=["POST"])
def approve_change(req_id):
    """Applique la proposition à la carto commune — donc à tous ses lecteurs."""
    from Code.routes.cartography_editor import _sync_carto_to_db

    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    cr = db.session.get(CartoChangeRequest, req_id)
    if not cr:
        return jsonify({"error": "Proposition introuvable"}), 404
    if not can_review(cr.entity, user):
        return jsonify({"error": "Réservé aux champions et administrateurs",
                        "code": "forbidden"}), 403
    if cr.status != "pending":
        return jsonify({"error": "Proposition déjà traitée"}), 409

    entity = cr.entity
    diagram = _diagram(cr.diagram)
    if diagram is None:
        return jsonify({"error": "Diagramme illisible"}), 400

    entity.optiqcarto_data = cr.diagram
    cr.status = "approved"
    cr.reviewer_id = user.id
    cr.reviewed_at = datetime.utcnow()
    cr.review_comment = (request.get_json(silent=True) or {}).get("comment") or None
    db.session.commit()

    avertissement = None
    try:
        _sync_carto_to_db(entity, diagram)
    except Exception as exc:            # la carto est enregistrée, la dérivation non
        import traceback
        traceback.print_exc()
        avertissement = str(exc)

    return jsonify({"status": "ok", "entity_id": entity.id,
                    "sync_warning": avertissement})


@carto_sharing_bp.route("/api/changes/<int:req_id>/reject", methods=["POST"])
def reject_change(req_id):
    """Refuse la proposition. La carto commune n'est pas touchée."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    cr = db.session.get(CartoChangeRequest, req_id)
    if not cr:
        return jsonify({"error": "Proposition introuvable"}), 404
    if not can_review(cr.entity, user):
        return jsonify({"error": "Réservé aux champions et administrateurs",
                        "code": "forbidden"}), 403
    if cr.status != "pending":
        return jsonify({"error": "Proposition déjà traitée"}), 409

    cr.status = "rejected"
    cr.reviewer_id = user.id
    cr.reviewed_at = datetime.utcnow()
    cr.review_comment = ((request.get_json(silent=True) or {}).get("comment") or "").strip() or None
    db.session.commit()
    return jsonify({"status": "ok"})


@carto_sharing_bp.route("/api/changes/<int:req_id>", methods=["DELETE"])
def withdraw_change(req_id):
    """L'auteur retire sa proposition tant qu'elle n'a pas été examinée."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    cr = db.session.get(CartoChangeRequest, req_id)
    if not cr or cr.author_id != user.id:
        return jsonify({"error": "Proposition introuvable"}), 404
    if cr.status != "pending":
        return jsonify({"error": "Proposition déjà traitée"}), 409

    db.session.delete(cr)
    db.session.commit()
    return jsonify({"status": "ok"})
