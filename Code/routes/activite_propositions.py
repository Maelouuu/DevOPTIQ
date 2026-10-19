# -*- coding: utf-8 -*-
"""Les propositions sur les données d'une activité — dépôt, examen, décision.

Le pendant de `carto_sharing.py` pour les tâches, outils et compétences. Les
règles d'accès sont les MÊMES (`carto_access.can_propose` / `can_review`) :
c'est la même carto, et le tableau des droits ne doit pas dire deux choses du
même palier selon l'écran qu'on regarde.

⚠️ Ce blueprint ÉCRIT, et la porte centrale (`Code/ecriture.py`) le laisse
passer : il figure dans sa liste d'exemptions parce qu'il porte sa propre
garde, plus fine. Elle est appliquée ici, route par route.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from Code.carto_access import can_review
from Code.extensions import db
from Code.models.models import ActivityChangeRequest, Entity, User
from Code.propositions_activite import (EchecDeRejeu, brouillon, gestes,
                                        rejouer, retirer_geste)

acp_bp = Blueprint("activite_propositions", __name__, url_prefix="/api/propositions")


def _connecte():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def _nom(u):
    if not u:
        return ""
    return ("%s %s" % (u.first_name or "", u.last_name or "")).strip() or (u.email or "")


def _en_json(cr, user, avec_gestes=False):
    out = {
        "id": cr.id,
        "entity_id": cr.entity_id,
        "entity_name": cr.entity.name if cr.entity else None,
        "activity_id": cr.activity_id,
        "title": cr.title or "",
        "message": cr.message or "",
        "author": _nom(cr.author),
        "author_id": cr.author_id,
        "is_mine": bool(user and cr.author_id == user.id),
        "status": cr.status,
        "n": len(gestes(cr)),
        "created_at": cr.created_at.isoformat() if cr.created_at else None,
        "submitted_at": cr.submitted_at.isoformat() if cr.submitted_at else None,
        "reviewed_at": cr.reviewed_at.isoformat() if cr.reviewed_at else None,
        "reviewer": _nom(cr.reviewer) if cr.reviewer_id else None,
        "review_comment": cr.review_comment or "",
    }
    if avec_gestes:
        # ⚠️ On ne renvoie PAS le corps de la requête : il porte des
        # identifiants et des chemins qui ne disent rien à un lecteur, et le
        # libellé se compose à l'écran, dans SA langue.
        out["gestes"] = [{"op": g.get("op"), "objet": g.get("objet"),
                          "activite": g.get("activite"),
                          "activity_id": g.get("activity_id")}
                         for g in gestes(cr)]
    return out


# ── Le brouillon de celui qui propose ─────────────────────────────────────

@acp_bp.route("/brouillon")
def get_brouillon():
    """Ce que le compte a accumulé sur la carto active, pas encore envoyé."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    entite = Entity.get_active()
    cr = brouillon(user, entite)
    if cr is None:
        return jsonify({"brouillon": None, "n": 0})
    return jsonify({"brouillon": _en_json(cr, user, avec_gestes=True), "n": len(gestes(cr))})


@acp_bp.route("/brouillon/<int:rang>", methods=["DELETE"])
def del_geste(rang):
    """Retire un geste du brouillon — on se relit avant d'envoyer."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    cr = brouillon(user, Entity.get_active())
    if cr is None or not retirer_geste(cr, rang):
        return jsonify({"error": "Geste introuvable"}), 404
    return jsonify({"ok": True})


@acp_bp.route("/brouillon", methods=["DELETE"])
def vider_brouillon():
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    cr = brouillon(user, Entity.get_active())
    if cr is not None:
        db.session.delete(cr)
        db.session.commit()
    return jsonify({"ok": True})


@acp_bp.route("/envoyer", methods=["POST"])
def envoyer():
    """Le brouillon part à l'examen."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    cr = brouillon(user, Entity.get_active())
    if cr is None or not gestes(cr):
        return jsonify({"error": "Rien à envoyer", "code": "vide"}), 400
    data = request.get_json(silent=True) or {}
    cr.message = (data.get("message") or "").strip() or None
    cr.status = "pending"
    cr.submitted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "proposition": _en_json(cr, user)}), 201


# ── Ce qui attend une décision ────────────────────────────────────────────

def propositions_a_examiner(user):
    """Les propositions EN ATTENTE que ce compte peut trancher, toutes cartos.

    Source unique du compteur et de la liste — comme pour la carto, le chiffre
    annoncé et ce qui s'ouvre ne peuvent pas diverger. Ses propres
    propositions n'y figurent pas : on ne s'alerte pas soi-même.
    """
    if user is None or not can_review(None, user):
        return []
    demandes = (ActivityChangeRequest.query
                .filter(ActivityChangeRequest.status == "pending",
                        ActivityChangeRequest.author_id != user.id)
                .order_by(ActivityChangeRequest.submitted_at.asc())
                .all())
    return [cr for cr in demandes if can_review(cr.entity, user)]


@acp_bp.route("/a_examiner")
def list_a_examiner():
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    demandes = propositions_a_examiner(user)
    return jsonify({
        "requests": [_en_json(cr, user, avec_gestes=True) for cr in demandes],
        "n": len(demandes),
        "cartos": len({cr.entity_id for cr in demandes}),
    })


@acp_bp.route("/miennes")
def list_miennes():
    """Mes propositions envoyées — pour les relire et les retirer."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    demandes = (ActivityChangeRequest.query
                .filter(ActivityChangeRequest.author_id == user.id,
                        ActivityChangeRequest.status != "draft")
                .order_by(ActivityChangeRequest.id.desc())
                .limit(50).all())
    return jsonify({"requests": [_en_json(cr, user, avec_gestes=True) for cr in demandes]})


@acp_bp.route("/<int:req_id>")
def get_proposition(req_id):
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    cr = db.session.get(ActivityChangeRequest, req_id)
    if not cr or cr.status == "draft":
        return jsonify({"error": "Proposition introuvable"}), 404
    if cr.author_id != user.id and not can_review(cr.entity, user):
        return jsonify({"error": "Proposition introuvable"}), 404
    detail = _en_json(cr, user, avec_gestes=True)
    detail["can_review"] = bool(can_review(cr.entity, user) and cr.status == "pending")
    return jsonify(detail)


def _annoncer_a_l_auteur(cr, valideur):
    """La décision part à l'auteur. On ne s'annonce pas la sienne."""
    cr.author_seen_at = datetime.utcnow() if valideur.id == cr.author_id else None


@acp_bp.route("/<int:req_id>/approve", methods=["POST"])
def approve(req_id):
    """Applique les gestes à la carto — donc à tous ceux qui l'ouvrent.

    ⚠️ Tout ou rien : `rejouer` neutralise les commits des routes appelées et
    valide une seule fois. Une proposition à moitié appliquée ne se rattrape
    pas — personne ne saurait dire où elle s'est arrêtée.
    """
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    cr = db.session.get(ActivityChangeRequest, req_id)
    if not cr or cr.status == "draft":
        return jsonify({"error": "Proposition introuvable"}), 404
    if not can_review(cr.entity, user):
        return jsonify({"error": "Réservé aux coordinateurs", "code": "forbidden"}), 403
    if cr.status != "pending":
        return jsonify({"error": "Proposition déjà traitée"}), 409

    # ⚠️ Le rejeu travaille sur la carto de la PROPOSITION, pas sur celle que
    # le valideur a rendue active : il tranche depuis la page Carte, souvent sur une
    # autre entité que la sienne.
    avant = session.get("active_entity_id")
    session["active_entity_id"] = cr.entity_id
    try:
        n = rejouer(cr, user)
    except EchecDeRejeu as echec:
        session["active_entity_id"] = avant
        return jsonify({
            "error": "Un geste n'a pas pu être appliqué",
            "code": "rejeu",
            "rang": echec.rang,
            "op": (echec.geste or {}).get("op"),
            "objet": (echec.geste or {}).get("objet"),
            "raison": echec.raison,
        }), 409
    finally:
        if session.get("active_entity_id") != avant:
            session["active_entity_id"] = avant

    cr.status = "approved"
    cr.reviewer_id = user.id
    cr.reviewed_at = datetime.utcnow()
    cr.review_comment = ((request.get_json(silent=True) or {}).get("comment") or "").strip() or None
    _annoncer_a_l_auteur(cr, user)
    db.session.commit()
    return jsonify({"ok": True, "n": n, "entity_id": cr.entity_id})


@acp_bp.route("/<int:req_id>/reject", methods=["POST"])
def reject(req_id):
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    cr = db.session.get(ActivityChangeRequest, req_id)
    if not cr or cr.status == "draft":
        return jsonify({"error": "Proposition introuvable"}), 404
    if not can_review(cr.entity, user):
        return jsonify({"error": "Réservé aux coordinateurs", "code": "forbidden"}), 403
    if cr.status != "pending":
        return jsonify({"error": "Proposition déjà traitée"}), 409
    cr.status = "rejected"
    cr.reviewer_id = user.id
    cr.reviewed_at = datetime.utcnow()
    cr.review_comment = ((request.get_json(silent=True) or {}).get("comment") or "").strip() or None
    _annoncer_a_l_auteur(cr, user)
    db.session.commit()
    return jsonify({"ok": True})


@acp_bp.route("/<int:req_id>", methods=["DELETE"])
def withdraw(req_id):
    """L'auteur retire sa proposition tant qu'elle n'a pas été examinée."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    cr = db.session.get(ActivityChangeRequest, req_id)
    if not cr or cr.author_id != user.id:
        return jsonify({"error": "Proposition introuvable"}), 404
    if cr.status not in ("draft", "pending"):
        return jsonify({"error": "Proposition déjà traitée"}), 409
    db.session.delete(cr)
    db.session.commit()
    return jsonify({"ok": True})


# ── L'annonce de la décision à l'auteur ───────────────────────────────────

@acp_bp.route("/decisions")
def mes_decisions():
    """Les décisions prises sur MES propositions, que je n'ai pas encore lues."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    decisions = (ActivityChangeRequest.query
                 .filter(ActivityChangeRequest.author_id == user.id,
                         ActivityChangeRequest.status.in_(("approved", "rejected")),
                         ActivityChangeRequest.author_seen_at.is_(None))
                 .order_by(ActivityChangeRequest.reviewed_at.asc())
                 .all())
    return jsonify({"decisions": [_en_json(cr, user, avec_gestes=True) for cr in decisions]})


@acp_bp.route("/decisions/vues", methods=["POST"])
def decisions_vues():
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    ids = [int(i) for i in ids if str(i).isdigit()][:50]
    n = 0
    if ids:
        # ⚠️ Seulement celles dont on est l'AUTEUR : les ids viennent du
        # navigateur, ils ne suffisent jamais à écrire sur la ligne d'un autre.
        for cr in (ActivityChangeRequest.query
                   .filter(ActivityChangeRequest.id.in_(ids),
                           ActivityChangeRequest.author_id == user.id).all()):
            cr.author_seen_at = datetime.utcnow()
            n += 1
        db.session.commit()
    return jsonify({"ok": True, "n": n})
