# -*- coding: utf-8 -*-
"""Plan de formation — amener un collaborateur au niveau requis d'un rôle (CDC 6.8).

Le partage des rôles entre le calcul et l'IA est volontaire :

- **L'IA propose le CONTENU** : quelles actions, dans quel ordre, avec quelle
  charge estimée en heures. C'est ce qu'elle sait faire.
- **Le calcul décide si ça TIENT** : heures disponibles par semaine × durée
  visée = une capacité ; la somme des charges = un besoin. Le verdict est
  arithmétique, instantané, et se recalcule à chaque mouvement de curseur —
  sans rappeler l'IA. Un curseur qui attendrait trois secondes une réponse
  réseau ne serait pas un curseur.

Sans clé IA, `_plan_local()` construit un plan à partir des capacités en écart
relevées en base. Il n'invente rien qui ne soit déjà dans le référentiel : des
actions plus sèches, mais vraies.
"""
import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session

from Code.competences_acces import peut_lire, peut_noter
from Code.extensions import db
from Code.models.models import Activities, PlanFormation, Role, User
from Code.permissions import current_user
from Code.prompts import get_prompt
from Code.routes.mastery import (activity_mastery, dashboard_rows, level_label,
                                 required_level)
from Code.routes.propose_common import ai_model, openai_client_or_none

plan_bp = Blueprint("plan_formation", __name__, url_prefix="/plan")

# Familles d'action. Le CDC tient qu'un écart se comble d'abord EN SITUATION :
# la formation formelle vient en appui, pas l'inverse.
TYPES = {
    "TERRAIN":        {"fr": "Situation de travail", "en": "Work situation"},
    "ACCOMPAGNEMENT": {"fr": "Accompagnement",       "en": "Coaching"},
    "FORMATION":      {"fr": "Formation",            "en": "Training"},
}

# Charge de repli, en heures, pour UN pas de niveau sur une capacité. Sert
# uniquement quand l'IA n'est pas disponible : c'est un ordre de grandeur
# assumé, pas une science — et l'utilisateur le corrige action par action.
CHARGE_PAR_PAS = {"TERRAIN": 12, "ACCOMPAGNEMENT": 4, "FORMATION": 7}

PARAMETRES_DEFAUT = {"heures_semaine": 4, "semaines": 12}


def _lang():
    return session.get("lang", "fr")


def _libelle_type(code, lang=None):
    return TYPES.get(code, {}).get(lang or _lang(), code)


# ── Le besoin : où le collaborateur est en retard sur ce rôle ────────────────
def contexte_ecart(user_id, role_id):
    """Ce que le plan doit combler. Aucune IA ici : que de la base."""
    activites = []
    for row in dashboard_rows(user_id, role_id):
        if row["gap"] is None or row["gap"] >= 0:
            continue
        st = activity_mastery(user_id, row["activity_id"], role_id)
        req = st["required_level"]
        resultats = [{
            "data_id": r["data_id"], "name": r["name"],
            "demonstrated_level": r["demonstrated_level"],
            "minimum_performance_text": r["minimum_performance_text"],
        } for r in st["results"]
            if r["demonstrated_level"] is not None and req is not None
            and r["demonstrated_level"] < req]
        activites.append({
            "activity_id": row["activity_id"], "activity_name": row["activity_name"],
            "competence": row["competence"],
            "demonstrated_level": row["demonstrated_level"],
            "demonstrated_label": row["demonstrated_label"],
            "required_level": req, "required_label": row["required_label"],
            "gap": row["gap"],
            "results_in_gap": resultats,
            "capabilities": _capacites_en_ecart(user_id, row["activity_id"], resultats),
        })
    activites.sort(key=lambda a: (a["gap"], a["activity_name"].lower()))
    return activites


def _capacites_en_ecart(user_id, activity_id, resultats):
    """Savoirs / savoir-faire / HSC reliés aux résultats en écart.

    Le diagnostic V1.1 relie chaque RÉSULTAT à ses capacités : c'est cette
    liste-là qu'un plan doit travailler, pas un catalogue de formations.
    """
    try:
        from Code.routes.diagnostic import _linked_capabilities
    except Exception:
        return []
    vues, sortie = set(), []
    for r in resultats:
        try:
            for c in _linked_capabilities(user_id, activity_id, r["data_id"], _lang()):
                cle = (c.get("type_label"), c.get("label"))
                if cle in vues:
                    continue
                vues.add(cle)
                if c.get("gap") is None or c.get("gap") < 0:
                    sortie.append(c)
        except Exception:                      # le diagnostic bouge, le plan tient
            current_app.logger.debug("capacites indisponibles", exc_info=True)
    return sortie


# ── Le contenu : l'IA propose, le repli se débrouille ────────────────────────
def _plan_local(activites, lang):
    """Plan bâti sans IA, depuis les capacités en écart relevées en base.

    Une action par capacité à combler, plus une mise en situation par activité :
    c'est maigre, mais chaque ligne correspond à quelque chose de réel. Mieux
    qu'un plan générique qui aurait l'air complet.
    """
    actions, n = [], 0
    for a in activites:
        pas = max(1, abs(a["gap"] or 1))
        for c in a["capabilities"][:4]:
            n += 1
            manque = pas if c.get("gap") is None else max(1, abs(c["gap"]))
            actions.append({
                "id": f"L{n}",
                "titre": (f"Combler : {c.get('label') or c.get('type_label')}" if lang == "fr"
                          else f"Close the gap on: {c.get('label') or c.get('type_label')}"),
                "type": "FORMATION",
                "activity_id": a["activity_id"],
                "objectif": (f"{c.get('type_label')} — {c.get('label') or ''}").strip(" —"),
                "heures": CHARGE_PAR_PAS["FORMATION"] * manque,
                "livrable": "", "critere": "",
            })
        n += 1
        actions.append({
            "id": f"L{n}",
            "titre": (f"Tenir « {a['activity_name']} » en situation réelle" if lang == "fr"
                      else f"Perform “{a['activity_name']}” in real conditions"),
            "type": "TERRAIN",
            "activity_id": a["activity_id"],
            "objectif": (f"Atteindre {a['required_label']}" if lang == "fr"
                         else f"Reach {a['required_label']}"),
            "heures": CHARGE_PAR_PAS["TERRAIN"] * pas,
            "livrable": "", "critere": a["results_in_gap"][0]["minimum_performance_text"]
            if a["results_in_gap"] else "",
        })
    return actions


def _plan_ia(activites, parametres, lang):
    """Renvoie (actions, source). `source` dit d'où vient le contenu — l'écran
    l'affiche : on ne fait pas passer un repli local pour une proposition IA."""
    client, err = openai_client_or_none()
    systeme = get_prompt("plan_formation.system")
    if client is None or systeme is None:
        return _plan_local(activites, lang), (err or "no_ai")
    contexte = {
        "langue": "français" if lang == "fr" else "English",
        "heures_par_semaine": parametres.get("heures_semaine"),
        "semaines_visees": parametres.get("semaines"),
        "activites": [{
            "activite": a["activity_name"],
            "competence": a["competence"],
            "niveau_actuel": a["demonstrated_label"],
            "niveau_vise": a["required_label"],
            "ecart": a["gap"],
            "resultats_en_ecart": [{"nom": r["name"], "standard": r["minimum_performance_text"]}
                                   for r in a["results_in_gap"]],
            "capacites_en_ecart": [{"type": c.get("type_label"), "libelle": c.get("label")}
                                   for c in a["capabilities"]],
        } for a in activites],
    }
    try:
        resp = client.chat.completions.create(
            model=ai_model(),
            messages=[{"role": "system", "content": systeme},
                      {"role": "user", "content": json.dumps(contexte, ensure_ascii=False)}],
            temperature=0.3, response_format={"type": "json_object"})
        brut = json.loads(resp.choices[0].message.content)
    except Exception as e:
        current_app.logger.exception(e)
        return _plan_local(activites, lang), "error"

    noms = {a["activity_name"]: a["activity_id"] for a in activites}
    actions = []
    for i, it in enumerate(brut.get("actions") or [], start=1):
        try:
            heures = int(round(float(it.get("heures") or 0)))
        except (TypeError, ValueError):
            heures = 0
        actions.append({
            "id": f"A{i}",
            "titre": (it.get("titre") or "").strip(),
            "type": it.get("type") if it.get("type") in TYPES else "FORMATION",
            "activity_id": noms.get(it.get("activite")),
            "objectif": (it.get("objectif") or "").strip(),
            # Une action sans charge ne peut pas être ordonnancée : on la borne
            # plutôt que de la laisser à zéro, ce qui la rendrait « gratuite ».
            "heures": min(200, max(1, heures)),
            "livrable": (it.get("livrable") or "").strip(),
            "critere": (it.get("critere") or "").strip(),
        })
    actions = [a for a in actions if a["titre"]]
    return (actions or _plan_local(activites, lang)), ("AI" if actions else "empty")


# ── Routes ───────────────────────────────────────────────────────────────────
def _charger(user_id, role_id):
    return PlanFormation.query.filter_by(user_id=user_id, role_id=role_id).first()


def _serialiser(plan, activites, source=None):
    return {
        "parametres": (json.loads(plan.parametres) if (plan and plan.parametres)
                       else dict(PARAMETRES_DEFAUT)),
        "actions": json.loads(plan.actions) if (plan and plan.actions) else [],
        "source": (plan.source if plan else None) if source is None else source,
        "updated_at": plan.updated_at.isoformat() if (plan and plan.updated_at) else None,
        "activites": activites,
        "types": {k: _libelle_type(k) for k in TYPES},
    }


@plan_bp.route("/<int:user_id>/<int:role_id>", methods=["GET"])
def lire(user_id, role_id):
    """Le plan enregistré, et l'écart qu'il doit combler."""
    if not peut_lire(current_user(), user_id):
        return jsonify({"error": "forbidden"}), 403
    if not Role.query.get(role_id):
        return jsonify({"error": "role_not_found"}), 404
    return jsonify(_serialiser(_charger(user_id, role_id), contexte_ecart(user_id, role_id))), 200


@plan_bp.route("/proposer", methods=["POST"])
def proposer():
    """Propose des actions. N'enregistre rien : on regarde avant de garder."""
    p = request.get_json(force=True) or {}
    user_id, role_id = p.get("user_id"), p.get("role_id")
    if not (user_id and role_id):
        return jsonify({"error": "invalid_payload"}), 400
    # Proposer un plan de développement pour quelqu'un, c'est le noter : même
    # porte, même clé.
    ok, motif = peut_noter(current_user(), user_id, "2")
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    activites = contexte_ecart(user_id, role_id)
    if not activites:
        return jsonify({"actions": [], "source": "no_gap", "activites": []}), 200
    parametres = p.get("parametres") or dict(PARAMETRES_DEFAUT)
    actions, source = _plan_ia(activites, parametres, _lang())
    return jsonify({"actions": actions, "source": source, "activites": activites}), 200


@plan_bp.route("/enregistrer", methods=["POST"])
def enregistrer():
    p = request.get_json(force=True) or {}
    user_id, role_id = p.get("user_id"), p.get("role_id")
    if not (user_id and role_id):
        return jsonify({"error": "invalid_payload"}), 400
    ok, motif = peut_noter(current_user(), user_id, "2")
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    if not (User.query.get(user_id) and Role.query.get(role_id)):
        return jsonify({"error": "not_found"}), 404

    plan = _charger(user_id, role_id)
    if plan is None:
        plan = PlanFormation(user_id=user_id, role_id=role_id)
        db.session.add(plan)
    plan.parametres = json.dumps(p.get("parametres") or PARAMETRES_DEFAUT, ensure_ascii=False)
    plan.actions = json.dumps(p.get("actions") or [], ensure_ascii=False)
    plan.source = (p.get("source") or "LOCAL")[:10]
    acteur = current_user()
    plan.auteur_id = acteur.id if acteur else None
    plan.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_serialiser(plan, contexte_ecart(user_id, role_id))), 200


@plan_bp.route("/<int:user_id>/<int:role_id>", methods=["DELETE"])
def supprimer(user_id, role_id):
    ok, motif = peut_noter(current_user(), user_id, "2")
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    plan = _charger(user_id, role_id)
    if plan is not None:
        db.session.delete(plan)
        db.session.commit()
    return jsonify({"ok": True}), 200
