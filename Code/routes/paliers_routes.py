# -*- coding: utf-8 -*-
"""Les routes des PALIERS DE PERFORMANCE et des SESSIONS D'ÉVALUATION.

La règle vit dans `Code/paliers.py` ; ici il n'y a que des portes et de la
sérialisation. ⚠️ Chacune passe par `peut_lire` / `peut_noter` : poser une
cible ou trancher une mesure décide de la carrière de quelqu'un, et le
masquage dans l'écran n'est jamais une sécurité.
"""
from datetime import date, datetime

from flask import Blueprint, jsonify, request

from Code.competences_acces import peut_lire, peut_noter
from Code.extensions import db
from Code.models.models import (Activities, Data, PalierPerformance,
                                SessionEvaluation, activity_roles)
from Code.paliers import (SENS, STATUTS_SESSION, etat_sortie, json_session,
                          mesurable, prochain_rang, proposer_cible, trancher)
from Code.permissions import current_user
from Code.routes.qualify_outputs import get_activity_outputs

paliers_bp = Blueprint("paliers", __name__, url_prefix="/paliers")


def _date(txt):
    try:
        return datetime.strptime((txt or "").strip()[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _role_porte(activity_id, role_id):
    """⚠️ Le rôle doit porter CETTE activité : sinon on poserait une cible sur
    l'activité d'un rôle qu'on ne suit pas, en présentant celui qu'on suit."""
    return db.session.execute(db.select(activity_roles.c.activity_id).where(
        (activity_roles.c.activity_id == activity_id)
        & (activity_roles.c.role_id == role_id))).first() is not None


# ═══════════════════════════ LA NORME ═══════════════════════════
@paliers_bp.route("/norme/<int:data_id>", methods=["POST"])
def poser_norme(data_id):
    """Ce que l'ENTREPRISE attend de cette sortie. Ne regarde personne : la
    norme ne dépend pas de qui fait le travail."""
    acteur = current_user()
    if acteur is None:
        return jsonify({"error": "not_logged_in"}), 401
    d = db.session.get(Data, data_id)
    if d is None:
        return jsonify({"error": "unknown_output"}), 404
    # Régler la norme engage toute l'organisation : réservé à qui encadre.
    from Code.competences_acces import _statut_eleve
    from Code.models.models import UserRole
    encadre_qqn = UserRole.query.filter_by(manager_id=acteur.id).count() > 0
    if not (_statut_eleve(acteur) or encadre_qqn):
        return jsonify({"error": "forbidden"}), 403

    p = request.get_json(force=True) or {}
    if p.get("valeur") in (None, ""):
        # ⚠️ Effacer la norme REND la sortie qualitative : elle repasse au
        # jugement 0→4. C'est un choix légitime, pas une suppression.
        d.norme_valeur = d.norme_unite = d.norme_sens = None
        db.session.commit()
        return jsonify({"ok": True, "mesurable": False}), 200
    try:
        valeur = float(p["valeur"])
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_value"}), 400
    sens = (p.get("sens") or "moins").strip().lower()
    if sens not in SENS:
        return jsonify({"error": "invalid_direction"}), 400
    d.norme_valeur = valeur
    d.norme_unite = (p.get("unite") or "").strip()[:20] or None
    d.norme_sens = sens
    db.session.commit()
    return jsonify({"ok": True, "mesurable": True,
                    "norme": {"valeur": d.norme_valeur, "unite": d.norme_unite or "",
                              "sens": d.norme_sens}}), 200


# ═══════════════════════════ L'ÉTAT ═══════════════════════════
@paliers_bp.route("/activite/<int:user_id>/<int:activity_id>", methods=["GET"])
def etat_activite(user_id, activity_id):
    """La progression d'un collaborateur sur TOUTES les sorties d'une activité.

    Les non mesurables sont rendues aussi, marquées comme telles : l'écran
    doit pouvoir dire « celle-ci se juge à la main », pas les taire.
    """
    role_id = request.args.get("role_id", type=int)
    if not peut_lire(current_user(), user_id, role_id=role_id):
        return jsonify({"error": "forbidden"}), 403
    sorties = []
    for d in get_activity_outputs(activity_id):
        if mesurable(d):
            e = etat_sortie(d, user_id, role_id)
            e["proposition"] = proposer_cible(d, user_id, role_id)
            sorties.append(e)
        else:
            sorties.append({"data_id": d.id, "nom": d.name, "mesurable": False,
                            "norme": None, "paliers": [], "niveau": None})
    return jsonify({"ok": True, "activity_id": activity_id, "user_id": user_id,
                    "role_id": role_id, "sorties": sorties}), 200


@paliers_bp.route("/historique/<int:user_id>/<int:activity_id>", methods=["GET"])
def historique(user_id, activity_id):
    """Les points du graphe : chaque mesure, dans le temps, par sortie.

    ⚠️ Seuls les paliers RÉELLEMENT évalués font un point. Une cible posée
    n'est pas une mesure, et la tracer dessinerait une progression qui n'a
    pas eu lieu.
    """
    role_id = request.args.get("role_id", type=int)
    if not peut_lire(current_user(), user_id, role_id=role_id):
        return jsonify({"error": "forbidden"}), 403
    series = []
    for d in get_activity_outputs(activity_id):
        if not mesurable(d):
            continue
        q = PalierPerformance.query.filter_by(user_id=user_id, data_id=d.id)
        if role_id:
            q = q.filter_by(role_id=role_id)
        points = [{"date": p.evalue_le.isoformat(), "mesure": p.mesure_valeur,
                   "cible": p.cible_valeur, "statut": p.statut, "rang": p.rang}
                  for p in q.order_by(PalierPerformance.evalue_le).all()
                  if p.evalue_le and p.mesure_valeur is not None]
        series.append({"data_id": d.id, "nom": d.name,
                       "norme": d.norme_valeur, "unite": d.norme_unite or "",
                       "sens": d.norme_sens, "points": points})
    return jsonify({"ok": True, "series": series}), 200


# ═══════════════════════════ LES PALIERS ═══════════════════════════
@paliers_bp.route("/palier", methods=["POST"])
def creer_palier():
    """Poser la marche suivante : une cible, une échéance."""
    p = request.get_json(force=True) or {}
    uid, did, rid = p.get("user_id"), p.get("data_id"), p.get("role_id")
    if not (uid and did and rid):
        return jsonify({"error": "invalid_payload", "reason": "role_required"}), 400
    ok, motif = peut_noter(current_user(), uid, "2", role_id=rid)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    d = db.session.get(Data, did)
    if d is None or not mesurable(d):
        return jsonify({"error": "not_measurable"}), 400
    aid = d.producer_activity_id
    if aid is None or not _role_porte(aid, rid):
        return jsonify({"error": "association_not_found"}), 404
    try:
        cible = float(p["cible"])
    except (TypeError, ValueError, KeyError):
        return jsonify({"error": "invalid_value"}), 400

    palier = PalierPerformance(
        user_id=uid, activity_id=aid, data_id=did, role_id=rid,
        rang=prochain_rang(uid, did, rid), cible_valeur=cible,
        echeance=_date(p.get("echeance")), statut="en_cours",
        session_id=p.get("session_id"))
    db.session.add(palier)
    db.session.commit()
    return jsonify({"ok": True, "etat": etat_sortie(d, uid, rid)}), 200


@paliers_bp.route("/palier/<int:pid>/trancher", methods=["POST"])
def trancher_palier(pid):
    """La session a eu lieu : on pose la mesure, le verdict se calcule."""
    palier = db.session.get(PalierPerformance, pid)
    if palier is None:
        return jsonify({"error": "unknown"}), 404
    ok, motif = peut_noter(current_user(), palier.user_id, "2", role_id=palier.role_id)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    p = request.get_json(force=True) or {}
    try:
        mesure = float(p["mesure"])
    except (TypeError, ValueError, KeyError):
        return jsonify({"error": "invalid_value"}), 400
    statut = trancher(palier, mesure, evaluateur_id=(current_user() or None) and current_user().id,
                      preuve=p.get("preuve"))
    db.session.commit()
    d = db.session.get(Data, palier.data_id)
    return jsonify({"ok": True, "statut": statut,
                    "etat": etat_sortie(d, palier.user_id, palier.role_id)}), 200


@paliers_bp.route("/palier/<int:pid>", methods=["DELETE"])
def supprimer_palier(pid):
    palier = db.session.get(PalierPerformance, pid)
    if palier is None:
        return jsonify({"error": "unknown"}), 404
    ok, motif = peut_noter(current_user(), palier.user_id, "2", role_id=palier.role_id)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    uid, did, rid = palier.user_id, palier.data_id, palier.role_id
    db.session.delete(palier)
    db.session.commit()
    d = db.session.get(Data, did)
    return jsonify({"ok": True, "etat": etat_sortie(d, uid, rid) if d else None}), 200


# ═══════════════════════════ LES SESSIONS ═══════════════════════════
@paliers_bp.route("/sessions/<int:user_id>", methods=["GET"])
def lister_sessions(user_id):
    role_id = request.args.get("role_id", type=int)
    if not peut_lire(current_user(), user_id, role_id=role_id):
        return jsonify({"error": "forbidden"}), 403
    q = SessionEvaluation.query.filter_by(user_id=user_id)
    if role_id:
        q = q.filter_by(role_id=role_id)
    sessions = q.order_by(SessionEvaluation.date_prevue, SessionEvaluation.id).all()
    ids = [s.id for s in sessions]
    compte = {}
    if ids:
        for pal in PalierPerformance.query.filter(PalierPerformance.session_id.in_(ids)).all():
            compte[pal.session_id] = compte.get(pal.session_id, 0) + 1
    return jsonify({"ok": True,
                    "sessions": [json_session(s, compte.get(s.id, 0)) for s in sessions],
                    "aujourdhui": date.today().isoformat()}), 200


@paliers_bp.route("/session", methods=["POST"])
def planifier_session():
    p = request.get_json(force=True) or {}
    uid, rid = p.get("user_id"), p.get("role_id")
    if not (uid and rid):
        return jsonify({"error": "invalid_payload", "reason": "role_required"}), 400
    ok, motif = peut_noter(current_user(), uid, "2", role_id=rid)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    quand = _date(p.get("date_prevue"))
    if quand is None:
        return jsonify({"error": "invalid_date"}), 400
    acteur = current_user()
    s = SessionEvaluation(user_id=uid, role_id=rid,
                          developpeur_user_id=acteur.id if acteur else None,
                          date_prevue=quand, statut="prevue",
                          objet=(p.get("objet") or "").strip()[:200] or None)
    db.session.add(s)
    db.session.commit()
    return jsonify({"ok": True, "session": json_session(s, 0)}), 200


@paliers_bp.route("/session/<int:sid>", methods=["POST"])
def majsession(sid):
    """Tenir, annuler, replanifier. ⚠️ Un seul endroit : trois routes pour
    trois verbes finiraient par appliquer trois contrôles différents."""
    s = db.session.get(SessionEvaluation, sid)
    if s is None:
        return jsonify({"error": "unknown"}), 404
    ok, motif = peut_noter(current_user(), s.user_id, "2", role_id=s.role_id)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    p = request.get_json(force=True) or {}
    statut = (p.get("statut") or "").strip().lower()
    if statut and statut not in STATUTS_SESSION:
        return jsonify({"error": "invalid_status"}), 400
    if statut:
        s.statut = statut
        s.tenue_le = datetime.utcnow() if statut == "tenue" else None
    if p.get("date_prevue"):
        quand = _date(p["date_prevue"])
        if quand is None:
            return jsonify({"error": "invalid_date"}), 400
        s.date_prevue = quand
    if "note" in p:
        s.note = (p.get("note") or "").strip() or None
    if "objet" in p:
        s.objet = (p.get("objet") or "").strip()[:200] or None
    db.session.commit()
    return jsonify({"ok": True, "session": json_session(s)}), 200


@paliers_bp.route("/session/<int:sid>", methods=["DELETE"])
def supprimer_session(sid):
    s = db.session.get(SessionEvaluation, sid)
    if s is None:
        return jsonify({"error": "unknown"}), 404
    ok, motif = peut_noter(current_user(), s.user_id, "2", role_id=s.role_id)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    # ⚠️ Les paliers rattachés SURVIVENT, détachés : ils portent des mesures,
    # et supprimer un rendez-vous n'efface pas ce qui a été constaté.
    for pal in PalierPerformance.query.filter_by(session_id=sid).all():
        pal.session_id = None
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True, "deleted": True}), 200
