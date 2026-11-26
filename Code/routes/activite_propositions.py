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

from Code.carto_access import can_fill, can_review
from Code.extensions import db
from Code.models.models import ActivityChangeRequest, Entity, User
from Code.propositions_activite import (EchecDeRejeu, refs_du_corps,
                                        brouillon, gestes, rejouer,
                                        retirer_geste)
from Code.socle_activites import etat as socle_etat
from Code.socle_activites import renvoyer as socle_renvoyer_etat
from Code.socle_activites import soumettre as socle_soumettre_etat
from Code.socle_activites import valider as socle_valider_etat

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
        # ⚠️ `vise` porte les RANGS que ce geste référence, pas des
        # identifiants : c'est ce qui permet à l'écran de ranger « outiller »
        # sous la tâche en attente qu'il outille, plutôt qu'en vrac.
        out["gestes"] = [{"op": g.get("op"), "objet": g.get("objet"),
                          "activite": g.get("activite"),
                          "activity_id": g.get("activity_id"),
                          "vise": sorted(refs_du_corps(g.get("corps")))}
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


# ── LE SOCLE : le premier remplissage, et sa validation ──────────────────
#
# ⚠️ Le socle n'est PAS une proposition : il n'y a aucun geste à rejouer. La
# saisie est déjà en base (voir `Code/socle_activites.py`), et ce qu'on
# soumet, c'est l'état de la carto. Ces routes vivent ici parce que c'est le
# même écran et le même examinateur, pas parce que c'est le même objet.

@acp_bp.route("/socle")
def get_socle():
    """Où en est le premier remplissage de la carto active.

    ⚠️ Une LECTURE : quatre requêtes, sans simulation depuis que la saisie du
    champion s'écrit directement. C'est la page Activités qui l'affiche à
    chaque rendu — et elle la reçoit du serveur, pas d'un `fetch` : un
    panneau qui apparaît une image plus tard se lit comme un défaut.
    """
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    return jsonify(socle_etat(Entity.get_active(), user))


@acp_bp.route("/socle/soumettre", methods=["POST"])
def socle_soumettre():
    """Le champion déclare le remplissage fini : le coordinateur est saisi."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    entite = Entity.get_active()
    # ⚠️ Celui qui REMPLIT soumet, et lui seul : un compte qui n'a pas écrit
    # une ligne n'a pas à déclarer le travail d'un autre terminé.
    if not can_fill(entite, user):
        return jsonify({"error": "Réservé à qui remplit la carto",
                        "code": "forbidden"}), 403
    ok, code = socle_soumettre_etat(entite, user,
                                    (request.get_json(silent=True) or {}).get("message"))
    if not ok:
        return jsonify({"error": "Soumission refusée", "code": code,
                        "socle": socle_etat(entite, user)}), 409
    return jsonify({"ok": True, "socle": socle_etat(entite, user)}), 201


@acp_bp.route("/socle/valider", methods=["POST"])
def socle_valider():
    """Le coordinateur valide : le socle vaut pour tous ceux qui ouvrent la carto."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    entite = _carto_a_examiner(user)
    if entite is None:
        return jsonify({"error": "Réservé aux coordinateurs",
                        "code": "forbidden"}), 403
    ok, code = socle_valider_etat(entite, user,
                                  (request.get_json(silent=True) or {}).get("commentaire"))
    if not ok:
        return jsonify({"error": "Validation refusée", "code": code}), 409
    return jsonify({"ok": True, "entity_id": entite.id})


@acp_bp.route("/socle/renvoyer", methods=["POST"])
def socle_renvoyer():
    """Le coordinateur rend la main : on repart en saisie, avec son mot."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    entite = _carto_a_examiner(user)
    if entite is None:
        return jsonify({"error": "Réservé aux coordinateurs",
                        "code": "forbidden"}), 403
    ok, code = socle_renvoyer_etat(entite, user,
                                   (request.get_json(silent=True) or {}).get("commentaire"))
    if not ok:
        return jsonify({"error": "Renvoi refusé", "code": code}), 409
    return jsonify({"ok": True, "entity_id": entite.id})


def _carto_a_examiner(user):
    """La carto que ce compte tranche : celle de l'URL, sinon l'active.

    ⚠️ `can_review` est exigé sur l'entité, pas « en général » : un champion
    à qui l'on confierait l'examen ne doit pas trancher sur une carto qu'il
    ne voit pas.
    """
    demande = (request.get_json(silent=True) or {}).get("entity_id")
    entite = (db.session.get(Entity, demande) if isinstance(demande, int)
              else Entity.get_active())
    return entite if (entite is not None and can_review(entite, user)) else None


@acp_bp.route("/envoyer", methods=["POST"])
def envoyer():
    """Le brouillon part à l'examen.

    ⚠️ Plus de contrôle du PALIER ici, et ce n'est pas un oubli : un brouillon
    ne peut PAS exister pendant le premier remplissage — la saisie s'y écrit
    directement, il n'y a rien à accumuler. Le palier garde désormais la
    seule porte qui le concerne, `POST /socle/soumettre`. Un contrôle mort
    ment sur ce qu'il garde.
    """
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401
    entite = Entity.get_active()
    cr = brouillon(user, entite)
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
