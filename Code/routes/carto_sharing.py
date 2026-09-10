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

from flask import (Blueprint, Response, jsonify, redirect, render_template,
                   request, session, url_for)

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
# VIGNETTE D'UNE CARTO
# ─────────────────────────────────────────────
# On reconnaît sa cartographie à sa FORME : le dessin des bandes, la trajectoire
# des flèches, la répartition des activités. Une abstraction en barres de couleur
# rendait toutes les cartos identiques. On rend donc la vraie carte, en petit.

# Au-delà, le SVG pèse plus qu'il n'informe : à cette taille on ne distingue
# plus une flèche de plus.
_VIGNETTE_MAX_FORMES = 400
_VIGNETTE_MAX_LIENS = 500
# Un SVG Visio d'origine peut peser plusieurs Mo : au-delà on renonce plutôt
# que de faire ramer la page pour une image de 220 px de large.
_VIGNETTE_MAX_SVG = 3 * 1024 * 1024


def _echap_couleur(valeur, defaut="#94a3b8"):
    """Une couleur de carto part telle quelle dans le SVG : on la borne."""
    v = (valeur or "").strip()
    if len(v) > 24 or any(c in v for c in '<>"\'&'):
        return defaut
    return v or defaut


def _points_du_lien(conn, boites):
    """Le tracé réel de la flèche, ou à défaut la droite entre les deux formes."""
    for cle in ("_computedOrthopts", "userPts", "customPath"):
        pts = conn.get(cle)
        if isinstance(pts, list) and len(pts) >= 2:
            sortie = [(p.get("x"), p.get("y")) for p in pts
                      if isinstance(p, dict) and p.get("x") is not None
                      and p.get("y") is not None]
            if len(sortie) >= 2:
                return sortie
    a = boites.get(str(conn.get("fromId")))
    b = boites.get(str(conn.get("toId")))
    if a and b:
        return [(a[0] + a[2] / 2, a[1] + a[3] / 2), (b[0] + b[2] / 2, b[1] + b[3] / 2)]
    return []


def _svg_vignette(entity):
    """SVG de la carto, ou None si l'entité n'a rien à montrer."""
    diagram = _diagram(entity.optiqcarto_data)
    if not diagram:
        # Cartos importées avant `optiqcarto_data` : le SVG Visio est tout ce
        # qu'on a, et c'est déjà la carte d'origine.
        brut = entity.svg_content or ""
        if brut.strip().startswith("<") and len(brut) <= _VIGNETTE_MAX_SVG:
            return brut
        return None

    bandes = [b for b in (diagram.get("bands") or []) if not b.get("deleted")]
    formes = list(diagram.get("shapes") or [])
    if not bandes and not formes:
        return None

    # Les bandes s'empilent depuis y = -200 (repère d'OptiqCarto).
    y, rubans = -200.0, []
    for b in bandes:
        h = float(b.get("height") or 0)
        rubans.append((y, h, _echap_couleur(b.get("color"), "#d1d5db")))
        y += h

    boites = {}
    x0, y0 = 0.0, (-200.0 if bandes else None)
    x1, y1 = float(diagram.get("bandWidth") or 0), y
    for f in formes:
        fx, fy = float(f.get("x") or 0), float(f.get("y") or 0)
        fw, fh = float(f.get("w") or 0), float(f.get("h") or 0)
        boites[str(f.get("id"))] = (fx, fy, fw, fh)
        x0, y0 = min(x0, fx), (fy if y0 is None else min(y0, fy))
        x1, y1 = max(x1, fx + fw), max(y1, fy + fh)
    if y0 is None:
        y0 = 0.0
    marge = max(40.0, (x1 - x0) * 0.02)
    x0, y0, x1, y1 = x0 - marge, y0 - marge, x1 + marge, y1 + marge
    largeur, hauteur = max(1.0, x1 - x0), max(1.0, y1 - y0)

    # Un trait de vignette doit rester visible : on l'exprime en fraction de la
    # largeur totale, sinon il disparaît sur les grandes cartos.
    trait = max(1.5, largeur / 700.0)

    parts = [f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{largeur:.1f}" '
             f'height="{hauteur:.1f}" fill="#f7f9fc"/>']
    for by, bh, couleur in rubans:
        parts.append(f'<rect x="{x0:.1f}" y="{by:.1f}" width="{largeur:.1f}" '
                     f'height="{max(1.0, bh):.1f}" fill="{couleur}" opacity="0.45"/>')

    for c in (diagram.get("connections") or [])[:_VIGNETTE_MAX_LIENS]:
        pts = _points_du_lien(c, boites)
        if len(pts) < 2:
            continue
        chemin = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        parts.append(f'<polyline points="{chemin}" fill="none" '
                     f'stroke="{_echap_couleur(c.get("color"), "#64748b")}" '
                     f'stroke-width="{trait:.2f}" stroke-opacity="0.7" '
                     f'stroke-linejoin="round" stroke-linecap="round"/>')

    for f in formes[:_VIGNETTE_MAX_FORMES]:
        fx, fy, fw, fh = boites[str(f.get("id"))]
        if fw <= 0 or fh <= 0:
            continue
        couleur = _echap_couleur(f.get("color"))
        if f.get("type") == "decision":
            cx, cy = fx + fw / 2, fy + fh / 2
            parts.append(f'<polygon points="{cx:.1f},{fy:.1f} {fx + fw:.1f},{cy:.1f} '
                         f'{cx:.1f},{fy + fh:.1f} {fx:.1f},{cy:.1f}" fill="{couleur}"/>')
        else:
            rayon = min(fw, fh) * (0.5 if f.get("type") == "start-end" else 0.14)
            parts.append(f'<rect x="{fx:.1f}" y="{fy:.1f}" width="{fw:.1f}" '
                         f'height="{fh:.1f}" rx="{rayon:.1f}" fill="{couleur}"/>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{x0:.1f} {y0:.1f} {largeur:.1f} {hauteur:.1f}" '
            f'preserveAspectRatio="xMidYMid meet">' + "".join(parts) + "</svg>")


@carto_sharing_bp.route("/api/access/<int:entity_id>/thumbnail.svg")
def get_thumbnail(entity_id):
    """La carto en image, pour la galerie de la page Partage."""
    user = _connecte()
    if not user:
        return ("", 401)

    entity = db.session.get(Entity, entity_id)
    if not entity or not can_read(entity, user):
        return ("", 404)

    svg = _svg_vignette(entity)
    if not svg:
        return ("", 404)
    reponse = Response(svg, mimetype="image/svg+xml")
    # Privée : une carto commune n'est pas publique pour autant.
    reponse.headers["Cache-Control"] = "private, max-age=120"
    return reponse


@carto_sharing_bp.route("/api/access/previews")
def get_previews():
    """Chiffres de chaque carto ouverte au compte (l'image vient de thumbnail.svg)."""
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
            "has_thumbnail": _svg_vignette(e) is not None,
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
