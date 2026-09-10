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

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from Code.carto_access import (
    access_summary, can_edit, can_manage_access, can_read, can_review,
    entity_role_ids, set_access, user_role_ids,
)
from Code.extensions import db
from Code.models.models import CartoChangeRequest, Entity, Role, User, UserRole
from Code.permissions import current_user, is_admin, is_champion

carto_sharing_bp = Blueprint("carto_sharing", __name__, url_prefix="/cartography")

# La page vit à la racine (/share) : c'est un lieu, pas une API de la carto.
share_page_bp = Blueprint("share_page", __name__, url_prefix="/share")


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
# APERÇU D'UNE CARTO (vignette)
# ─────────────────────────────────────────────

# Une vignette n'a pas besoin de 400 formes : au-delà, on ne distingue plus rien
# et la page s'alourdit pour rien.
_APERCU_MAX_FORMES = 260


def _apercu_carto(entity):
    """Bandes et formes en coordonnées 0..1, prêtes à dessiner.

    Renvoie None si la carto est vide : la vignette affiche alors un état vide
    explicite plutôt qu'un cadre gris sans explication.
    """
    diagram = _diagram(entity.optiqcarto_data)
    if not diagram:
        return None

    bandes_src = [b for b in (diagram.get("bands") or []) if not b.get("deleted")]
    formes_src = [s for s in (diagram.get("shapes") or [])
                  if s.get("type") != "decision"]
    if not bandes_src and not formes_src:
        return None

    # Les bandes s'empilent depuis y = -200 (repère d'OptiqCarto).
    haut, y = -200.0, -200.0
    bandes = []
    for b in bandes_src:
        h = float(b.get("height") or 0)
        bandes.append({"y": y, "h": h,
                       "color": b.get("color") or "#d1d5db",
                       "label": b.get("label") or ""})
        y += h
    bas = y

    largeur = float(diagram.get("bandWidth") or 0)
    for f in formes_src:
        largeur = max(largeur, float(f.get("x") or 0) + float(f.get("w") or 0))
        bas = max(bas, float(f.get("y") or 0) + float(f.get("h") or 0))
        haut = min(haut, float(f.get("y") or 0))
    largeur = largeur or 1.0
    hauteur = (bas - haut) or 1.0

    def norme(v, origine, etendue):
        return round(max(0.0, min(1.0, (v - origine) / etendue)), 4)

    return {
        "bands": [{"y": norme(b["y"], haut, hauteur),
                   "h": round(b["h"] / hauteur, 4),
                   "color": b["color"]} for b in bandes],
        "shapes": [{"x": norme(float(f.get("x") or 0), 0, largeur),
                    "y": norme(float(f.get("y") or 0), haut, hauteur),
                    "w": round(float(f.get("w") or 0) / largeur, 4),
                    "h": round(float(f.get("h") or 0) / hauteur, 4),
                    "color": f.get("color") or "#94a3b8"}
                   for f in formes_src[:_APERCU_MAX_FORMES]],
        "counts": {"shapes": len(formes_src),
                   "links": len(diagram.get("connections") or []),
                   "bands": len(bandes_src)},
    }


@carto_sharing_bp.route("/api/access/previews")
def get_previews():
    """Vignette + chiffres de chaque carto ouverte au compte."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    from Code.models.models import Activities

    sorties = []
    for e in Entity.accessible(user.id):
        autorises = entity_role_ids(e.id)
        sorties.append({
            "id": e.id,
            "name": e.name,
            "is_shared": bool(e.is_shared),
            "is_owner": e.owner_id in (None, user.id),
            "activities": Activities.query.filter_by(entity_id=e.id).count(),
            "roles_open": len(autorises),
            "open_to_all": bool(e.is_shared and not autorises),
            "preview": _apercu_carto(e),
        })
    return jsonify({"maps": sorties})


# ─────────────────────────────────────────────
# RÔLES ET LEURS TITULAIRES
# ─────────────────────────────────────────────
# Régler l'accès sans pouvoir dire QUI tient le rôle obligeait à faire l'aller-
# retour avec la page Rôles. Les deux moitiés de la même décision vivent donc
# ici, et la page /share les montre côte à côte.

def _fiche_compte(u):
    return {"id": u.id, "name": _nom_compte(u), "email": u.email,
            "status": u.status or "user"}


@carto_sharing_bp.route("/api/access/<int:entity_id>/roles")
def get_roles(entity_id):
    """Rôles de la carto, leurs titulaires, et qui accède au total."""
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    entity = db.session.get(Entity, entity_id)
    if not entity or not can_read(entity, user):
        return jsonify({"error": "Entité introuvable"}), 404

    comptes = User.query.order_by(User.first_name, User.last_name).all()
    par_id = {u.id: u for u in comptes}
    autorises = entity_role_ids(entity.id)

    roles = []
    for r in Role.query.filter_by(entity_id=entity.id).order_by(Role.name).all():
        titulaires = [par_id[ur.user_id]
                      for ur in UserRole.query.filter_by(role_id=r.id).all()
                      if ur.user_id in par_id]
        roles.append({
            "id": r.id, "name": r.name,
            "granted": r.id in autorises,
            "holders": [_fiche_compte(u) for u in
                        sorted(titulaires, key=lambda u: _nom_compte(u).lower())],
        })

    # Qui ouvre la carto, et à quel titre : c'est la vérification d'un coup
    # d'œil qu'on ne pouvait faire nulle part.
    portee = []
    for u in comptes:
        if not can_read(entity, u):
            continue
        if entity.owner_id == u.id:
            motif = "owner"
        elif is_admin(u):
            motif = "admin"
        elif is_champion(u):
            motif = "champion"
        elif not autorises:
            motif = "all"
        else:
            motif = "role"
        noms = [r["name"] for r in roles
                if r["granted"] and any(h["id"] == u.id for h in r["holders"])]
        portee.append({**_fiche_compte(u), "reason": motif, "roles": noms})

    return jsonify({
        **access_summary(entity, user),
        "roles": roles,
        "accounts": [_fiche_compte(u) for u in comptes],
        "reach": portee,
    })


@carto_sharing_bp.route("/api/access/<int:entity_id>/roles/<int:role_id>/holders",
                        methods=["POST"])
def post_role_holders(entity_id, role_id):
    """Ajoute ou retire des titulaires — par PAIRE (compte, rôle).

    ⚠️ Les endpoints de la page RH remplacent TOUS les rôles d'une personne
    (delete puis insert) : les appeler d'ici lui retirerait ses rôles sur les
    autres cartos. On ne touche donc qu'au couple visé.
    """
    user = _connecte()
    if not user:
        return jsonify({"error": "Non connecté"}), 401

    entity = db.session.get(Entity, entity_id)
    if not entity or not can_read(entity, user):
        return jsonify({"error": "Entité introuvable"}), 404
    if not can_manage_access(entity, user):
        return jsonify({"error": "Réservé aux champions et administrateurs",
                        "code": "forbidden"}), 403

    role = Role.query.filter_by(id=role_id, entity_id=entity.id).first()
    if not role:
        return jsonify({"error": "Rôle introuvable"}), 404

    data = request.get_json(silent=True) or {}
    try:
        a_ajouter = {int(x) for x in (data.get("add") or [])}
        a_retirer = {int(x) for x in (data.get("remove") or [])}
    except (TypeError, ValueError):
        return jsonify({"error": "Liste de comptes invalide"}), 400

    for uid in a_ajouter:
        if db.session.get(User, uid) is None:
            continue
        if not UserRole.query.filter_by(user_id=uid, role_id=role.id).first():
            db.session.add(UserRole(user_id=uid, role_id=role.id))
    if a_retirer:
        UserRole.query.filter(UserRole.role_id == role.id,
                              UserRole.user_id.in_(a_retirer)).delete(
            synchronize_session=False)
    db.session.commit()

    titulaires = [db.session.get(User, ur.user_id)
                  for ur in UserRole.query.filter_by(role_id=role.id).all()]
    return jsonify({"status": "ok", "role_id": role.id,
                    "holders": [_fiche_compte(u) for u in titulaires if u]})


# ─────────────────────────────────────────────
# PAGE /share — tout le processus au même endroit
# ─────────────────────────────────────────────

@share_page_bp.route("/")
def share_home():
    """Console de partage : accès, titulaires et propositions sur un seul écran."""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    user = current_user()
    entites = Entity.accessible(user.id) if user else []
    gouverne = can_manage_access(None, user)

    # On arrive souvent depuis la fiche d'une entité de la carte : c'est celle-là
    # qu'on veut voir, pas l'entité active de la session.
    demandee = request.args.get("entity_id", type=int)
    ids = {e.id for e in entites}
    choisie = demandee if demandee in ids else Entity.get_active_id()

    return render_template(
        "share.html",
        entities=[{"id": e.id, "name": e.name,
                   "is_shared": bool(e.is_shared),
                   "is_owner": e.owner_id in (None, user.id)} for e in entites],
        active_entity_id=choisie,
        can_manage=gouverne,
        can_review=bool(user and (is_admin(user) or is_champion(user))),
    )


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
