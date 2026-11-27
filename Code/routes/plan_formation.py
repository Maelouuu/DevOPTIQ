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

Sans clé IA, `_plan_local()` construit un plan à partir de ce que la base
contient déjà. Il n'invente rien : des actions plus sèches, mais vraies.

⚠️⚠️ **Ce module a été écrit avant trois mécanismes de l'application**, et il
les ignorait tous les trois — relevé en cherchant « palier », « domain » et
« séance » : zéro occurrence. Conséquences mesurées au banc : sur un rôle à
trois activités en écart, le repli rendait **trois actions**, une par activité,
toutes « Tenir « X » en situation réelle » — parce qu'il ne savait travailler
que les `result_capability_links`, que seul le diagnostic remplit. Il voit
désormais :

- **les PALIERS de performance** : quand une sortie est mesurée, l'action parle
  en chiffres (ce qui a été relevé, la marche posée, la norme) au lieu d'une
  progression abstraite ;
- **les SÉANCES d'évaluation** : on fixait « 12 semaines » à côté d'un
  rendez-vous déjà pris pour dans trois ;
- **la TECHNICITÉ** : un domaine technique à −2 ne produisait AUCUNE action.

⚠️ Ce qui n'a PAS changé : la porte d'entrée. Une activité entre dans le plan
parce que `categorie_activite()` la dit « gap » — c'est-à-dire sur sa MAÎTRISE,
et rien d'autre. Un écart purement technique n'ouvre donc pas le plan : élargir
la porte ferait diverger l'écran et le plan sur le mot « écart », ce qui a déjà
été corrigé une fois (15/09). La technicité ENRICHIT les activités déjà en
écart ; elle ne les fait pas entrer.
"""
import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session

from Code.competences_acces import peut_lire, peut_noter
from Code.extensions import db
from Code.models.models import Activities, PlanFormation, Role, User
from Code.permissions import current_user
from Code.prompts import get_prompt
from Code.routes.mastery import (activity_mastery, categorie_activite, dashboard_rows,
                                 level_label, required_level)
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

# Seuil d'autonomie du CDC : sous 2, l'activité n'est pas tenue seule, même
# si le rôle n'a fixé aucun niveau requis.
SEUIL_AUTONOMIE = 2

PARAMETRES_DEFAUT = {"heures_semaine": 4, "semaines": 12}


def _lang():
    return session.get("lang", "fr")


def _chiffre(v):
    """« 48 » et non « 48.0 » : une norme s'écrit comme on la dit."""
    if v is None:
        return ""
    f = float(v)
    return str(int(f)) if abs(f - int(f)) < 1e-9 else ("%g" % f)


def _jour(iso, en=False):
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d" if en else "%d/%m/%Y")
    except (TypeError, ValueError):
        return iso


# Le sens d'une norme, en mots : « au plus 48 h » se lit, « moins 48 h » non.
SENS_MOT = {"moins": {"fr": "au plus", "en": "at most"},
            "plus": {"fr": "au moins", "en": "at least"}}


def _prochaine_seance(user_id, role_id):
    """La prochaine séance d'évaluation prévue, s'il y en a une.

    ⚠️ Le plan ignorait les rendez-vous : on réglait une durée visée de douze
    semaines à côté d'une séance déjà fixée pour dans trois. C'est elle qui
    décide de la date à laquelle les chiffres seront relevés.
    ⚠️ On ne retient pas une séance réservée à un AUTRE rôle : elle ne
    concerne pas ce plan. Une séance sans rôle, si — elle peut tout couvrir.
    """
    from datetime import date

    from Code.models.models import SessionEvaluation
    aujourd_hui = date.today()
    s = (SessionEvaluation.query
         .filter(SessionEvaluation.user_id == user_id,
                 SessionEvaluation.statut == "prevue",
                 SessionEvaluation.date_prevue >= aujourd_hui,
                 db.or_(SessionEvaluation.role_id.is_(None),
                        SessionEvaluation.role_id == role_id))
         .order_by(SessionEvaluation.date_prevue.asc())
         .first())
    if s is None:
        return None
    jours = (s.date_prevue - aujourd_hui).days
    return {"id": s.id, "date": s.date_prevue.isoformat(), "jours": jours,
            # Arrondi au SUPÉRIEUR : caler la durée sur six jours, c'est une
            # semaine, pas zéro.
            "semaines": max(1, -(-jours // 7))}


def _domaines_en_ecart(activity_id, role_id, user_id):
    """Les domaines techniques de l'activité où la personne est en dessous.

    ⚠️ Lu par la MÊME fonction que la fenêtre Technicité
    (`domaines_de_activite`) : deux lectures d'un même écart finiraient par
    donner deux verdicts.
    """
    try:
        from Code.routes.technical_domains import domaines_de_activite
        return [d for d in domaines_de_activite(activity_id, role_id, user_id, _lang())
                if d.get("gap") is not None and d["gap"] < 0]
    except Exception:                          # la technicité bouge, le plan tient
        current_app.logger.debug("domaines indisponibles", exc_info=True)
        return []


def _libelle_type(code, lang=None):
    return TYPES.get(code, {}).get(lang or _lang(), code)


# ── Le besoin : où le collaborateur est en retard sur ce rôle ────────────────
def contexte_ecart(user_id, role_id):
    """Ce que le plan doit combler. Aucune IA ici : que de la base.

    ⚠️ **Un plan ne se bâtit que sur du MESURÉ.** Une activité non évaluée n'est
    pas en écart — elle n'est pas regardée. `categorie_activite()` ne rend "gap"
    que pour une activité dont le niveau est posé et insuffisant : c'est la
    seule porte d'entrée ici.

    ⚠️ Cette fonction filtrait sur `gap < 0`, or `gap` est NUL quand le rôle n'a
    pas fixé de niveau requis. Une activité évaluée à 1 sans requis était donc
    comptée « en écart » par l'écran (l'autonomie n'est pas démontrée sous 2) et
    ignorée par le plan : le bouton s'affichait, la fenêtre répondait « aucun
    écart sur ce rôle ». Les deux tranchent maintenant avec le MÊME code.
    """
    activites = []
    for row in dashboard_rows(user_id, role_id):
        if categorie_activite(row) != "gap":
            continue
        st = activity_mastery(user_id, row["activity_id"], role_id)
        # Sans niveau requis, la cible est le seuil d'autonomie (2) : c'est ce
        # qui rend l'activité « en écart » en premier lieu.
        req = st["required_level"] if st["required_level"] is not None else SEUIL_AUTONOMIE
        resultats = []
        for r in st["results"]:
            if r["demonstrated_level"] is None or r["demonstrated_level"] >= req:
                continue
            perf = r.get("performance") or {}
            pal = perf.get("palier_en_cours") or None
            resultats.append({
                "data_id": r["data_id"], "name": r["name"],
                "demonstrated_level": r["demonstrated_level"],
                "demonstrated_label": r["demonstrated_label"],
                "minimum_performance_text": r["minimum_performance_text"],
                # ⚠️ Ce que le plan ignorait : la sortie est-elle MESURÉE, où
                # en est-elle, et quelle marche est déjà posée. Sans ces trois
                # champs, l'action ne peut parler que d'une progression
                # abstraite — et c'est ce qu'elle faisait.
                "mesurable": bool(r.get("mesurable")),
                "norme": perf.get("norme") or None,
                "mesure": perf.get("mesure"),
                "palier": ({"cible": pal.get("cible"), "echeance": pal.get("echeance")}
                           if pal else None),
                "manque": req - r["demonstrated_level"],
            })
        activites.append({
            "activity_id": row["activity_id"], "activity_name": row["activity_name"],
            "competence": row["competence"],
            "demonstrated_level": row["demonstrated_level"],
            "demonstrated_label": row["demonstrated_label"],
            "required_level": req, "required_label": level_label(req),
            # L'écart affiché suit la cible retenue — et vaut donc quelque chose
            # même quand le rôle n'a pas fixé de niveau requis.
            "gap": row["demonstrated_level"] - req,
            "results_in_gap": resultats,
            "capabilities": _capacites_en_ecart(user_id, row["activity_id"], resultats),
            # Le contexte technique de l'activité : un AUTRE axe que la
            # maîtrise, mais un écart réel, et il ne produisait rien.
            "domaines": _domaines_en_ecart(row["activity_id"], role_id, user_id),
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
                    # Le résultat qui réclame cette capacité : c'est lui qui dit
                    # POURQUOI l'action existe.
                    c["resultat"] = r["name"]
                    sortie.append(c)
        except Exception:                      # le diagnostic bouge, le plan tient
            current_app.logger.debug("capacites indisponibles", exc_info=True)
    return sortie


# ── Le contenu : l'IA propose, le repli se débrouille ────────────────────────
# Nature d'action par famille de capacité, pour le plan construit SANS IA. Un
# savoir s'apprend ; un savoir-faire s'exerce, mieux avec quelqu'un à côté ;
# une HSC se travaille en accompagnement. Ce n'est pas un catalogue inventé :
# c'est la règle OPTIQ appliquée à ce que la base contient déjà.
NATURE_PAR_CAPACITE = {"SAVOIR": "FORMATION", "SAVOIR_FAIRE": "ACCOMPAGNEMENT",
                       "HSC": "ACCOMPAGNEMENT"}

_TITRE_CAPACITE = {
    "FORMATION":      {"fr": "Se former : {x}", "en": "Learn: {x}"},
    "ACCOMPAGNEMENT": {"fr": "S'exercer avec un appui : {x}", "en": "Practise with support: {x}"},
}


def _resultat_ia(r):
    """Un résultat tel que l'IA le reçoit. ⚠️ Les CHIFFRES y sont : sans eux
    elle ne pouvait proposer qu'une progression abstraite, parce qu'elle ne
    savait pas qu'une sortie pouvait être mesurée."""
    bloc = {"nom": r["name"], "standard": r["minimum_performance_text"]}
    if not r.get("mesurable"):
        return bloc
    norme = r.get("norme") or {}
    pal = r.get("palier") or {}
    bloc["mesure"] = {
        "derniere_mesure": r.get("mesure"),
        "norme": norme.get("valeur"),
        "unite": norme.get("unite") or "",
        "sens": "au plus" if norme.get("sens") == "moins" else "au moins",
        "palier_en_cours": pal.get("cible"),
        "echeance": pal.get("echeance"),
    }
    return bloc


def _critere(resultat, standard, en=False):
    if not (resultat and standard):
        return standard or ""
    return f"“{resultat}”: {standard}" if en else f"« {resultat} » : {standard}"


def _action_resultat(a, r, n, en):
    """Une action de TERRAIN visant UN résultat en écart.

    ⚠️⚠️ C'est ce qui corrige la dégénérescence du repli. Il n'émettait, par
    activité, qu'une seule action — « Tenir « X » en situation réelle » — parce
    que tout le reste dépendait de `result_capability_links`, que seul le
    diagnostic remplit : mesuré au banc, trois activités en écart donnaient
    trois actions, et aucune ne disait sur quoi travailler. Le plan parle
    désormais de RÉSULTATS, qui sont la chaîne du module.

    ⚠️ Et quand le résultat est MESURÉ, il parle en CHIFFRES : la marche déjà
    posée (ou la norme à défaut), ce qui a été relevé, et l'échéance. « Amener
    « Rapport d'essais » à 48 h » se fait ; « tenir l'activité » se devine.
    """
    manque = max(1, r.get("manque") or 1)
    norme = r.get("norme") or {}
    unite = norme.get("unite") or ""
    pal = r.get("palier") or {}
    # La marche posée d'abord : c'est l'engagement en cours. La norme ensuite —
    # c'est la cible finale, et il n'y a rien d'autre quand rien n'est posé.
    vise = pal.get("cible") if pal.get("cible") is not None else norme.get("valeur")

    if r.get("mesurable") and vise is not None:
        titre = (f"Bring “{r['name']}” to {_chiffre(vise)} {unite}".strip() if en
                 else f"Amener « {r['name']} » à {_chiffre(vise)} {unite}".strip())
        bouts = []
        if r.get("mesure") is not None:
            bouts.append((f"measured {_chiffre(r['mesure'])} {unite}" if en
                          else f"mesuré {_chiffre(r['mesure'])} {unite}").strip())
        if norme.get("valeur") is not None:
            mot = SENS_MOT.get(norme.get("sens"), {}).get("en" if en else "fr", "")
            bouts.append((f"standard {mot} {_chiffre(norme['valeur'])} {unite}" if en
                          else f"norme {mot} {_chiffre(norme['valeur'])} {unite}").strip())
        if pal.get("echeance"):
            bouts.append((f"due {_jour(pal['echeance'], en)}" if en
                          else f"échéance {_jour(pal['echeance'])}"))
        objectif = " · ".join(x for x in bouts if x)
    else:
        titre = (f"Produce “{r['name']}” at the expected standard" if en
                 else f"Produire « {r['name']} » au standard attendu")
        objectif = ((f"From “{r.get('demonstrated_label') or '—'}” to “{a['required_label']}”" if en
                     else f"Passer de « {r.get('demonstrated_label') or '—'} » "
                          f"à « {a['required_label']} »"))
    return {
        "id": f"L{n}",
        "titre": titre,
        "type": "TERRAIN",
        "activity_id": a["activity_id"],
        "objectif": objectif,
        "heures": CHARGE_PAR_PAS["TERRAIN"] * manque,
        "livrable": r["name"],
        "critere": _critere(r["name"], r.get("minimum_performance_text"), en),
    }


def _action_domaine(a, d, n, en):
    """Un domaine technique en écart. ⚠️ FORMATION et non TERRAIN : un domaine
    technique s'apprend — c'est le terrain sur lequel l'activité se joue, pas
    l'activité elle-même."""
    manque = max(1, abs(d.get("gap") or 1))
    return {
        "id": f"L{n}",
        "titre": (f"Raise the technical level: {d['name']}" if en
                  else f"Monter en technicité : {d['name']}"),
        "type": "FORMATION",
        "activity_id": a["activity_id"],
        "objectif": ((f"Technical domain of “{a['activity_name']}” · "
                      f"{d.get('demonstrated_label') or '—'} → {d.get('required_label') or '—'}") if en
                     else (f"Domaine technique de « {a['activity_name']} » · "
                           f"{d.get('demonstrated_label') or '—'} → {d.get('required_label') or '—'}")),
        "heures": CHARGE_PAR_PAS["FORMATION"] * manque,
        "livrable": "", "critere": "",
    }


def _plan_local(activites, lang):
    """Plan bâti sans IA, depuis ce que la base contient déjà.

    Trois sources, dans cet ordre : les capacités en écart quand le diagnostic
    a tourné, les domaines techniques en écart, puis les RÉSULTATS en écart —
    un par un, avec leurs chiffres quand ils sont mesurés.

    ⚠️ Chaque champ doit AJOUTER quelque chose au titre. La première version
    écrivait « Combler : Arbitrage » puis « Objectif : HSC — Arbitrage » : deux
    fois la même information, et nulle part ce qu'il fallait faire ni à quoi on
    verrait que c'est fait.
    """
    en = lang != "fr"
    actions, n = [], 0
    for a in activites:
        pas = max(1, abs(a["gap"] or 1))
        for c in a["capabilities"][:4]:
            n += 1
            manque = pas if c.get("gap") is None else max(1, abs(c["gap"]))
            nature = NATURE_PAR_CAPACITE.get(c.get("item_type"), "FORMATION")
            libelle = c.get("label") or c.get("type_label") or ""
            resultat = c.get("resultat") or ""
            actions.append({
                "id": f"L{n}",
                "titre": _TITRE_CAPACITE[nature]["en" if en else "fr"].format(x=libelle),
                "type": nature,
                "activity_id": a["activity_id"],
                "objectif": ((f"{c.get('type_label')} required by “{resultat}”" if en
                              else f"{c.get('type_label')} que demande « {resultat} »")
                             if resultat else ""),
                "heures": CHARGE_PAR_PAS[nature] * manque,
                # ⚠️ Pas de critère ici : le standard du résultat se vérifie EN
                # SITUATION, sur l'action de terrain qui suit. Le recopier sur
                # chaque capacité répétait la même ligne trois fois — et
                # prétendait qu'une formation suffit à le tenir.
                "livrable": "", "critere": "",
            })
        # ⚠️ Plafonné à TROIS domaines : au-delà le plan parlerait plus de
        # contexte technique que de l'activité, et ce n'est pas lui l'écart
        # qui a ouvert la porte.
        for d in (a.get("domaines") or [])[:3]:
            n += 1
            actions.append(_action_domaine(a, d, n, en))
        resultats = a["results_in_gap"]
        for r in resultats:
            n += 1
            actions.append(_action_resultat(a, r, n, en))
        if not resultats:
            # Une activité en écart a normalement au moins un résultat sous la
            # cible (le niveau global EST leur minimum) — mais on ne laisse pas
            # une activité sans aucune action parce qu'un cas de bord existe.
            n += 1
            actions.append({
                "id": f"L{n}",
                "titre": (f"Perform “{a['activity_name']}” in real conditions" if en
                          else f"Tenir « {a['activity_name']} » en situation réelle"),
                "type": "TERRAIN",
                "activity_id": a["activity_id"],
                "objectif": (f"Move from “{a['demonstrated_label']}” to “{a['required_label']}”" if en
                             else f"Passer de « {a['demonstrated_label']} » "
                                  f"à « {a['required_label']} »"),
                "heures": CHARGE_PAR_PAS["TERRAIN"] * pas,
                "livrable": "", "critere": "",
            })
    return actions


def _plan_ia(activites, parametres, lang, seance=None):
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
        # ⚠️ La séance déjà fixée : c'est la date à laquelle les chiffres
        # seront relevés, donc la seule échéance réelle du plan.
        "prochaine_seance": (seance or {}).get("date"),
        "activites": [{
            "activite": a["activity_name"],
            "competence": a["competence"],
            "niveau_actuel": a["demonstrated_label"],
            "niveau_vise": a["required_label"],
            "ecart": a["gap"],
            "resultats_en_ecart": [_resultat_ia(r) for r in a["results_in_gap"]],
            "capacites_en_ecart": [{"type": c.get("type_label"), "libelle": c.get("label")}
                                   for c in a["capabilities"]],
            "domaines_techniques_en_ecart": [
                {"nom": d["name"], "niveau_actuel": d.get("demonstrated_label"),
                 "niveau_requis": d.get("required_label")}
                for d in (a.get("domaines") or [])],
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


def _serialiser(plan, activites, source=None, seance=None):
    return {
        "seance": seance,
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
    if not peut_lire(current_user(), user_id, role_id=role_id):
        return jsonify({"error": "forbidden"}), 403
    if not Role.query.get(role_id):
        return jsonify({"error": "role_not_found"}), 404
    return jsonify(_serialiser(_charger(user_id, role_id),
                               contexte_ecart(user_id, role_id),
                               seance=_prochaine_seance(user_id, role_id))), 200


@plan_bp.route("/proposer", methods=["POST"])
def proposer():
    """Propose des actions. N'enregistre rien : on regarde avant de garder."""
    p = request.get_json(force=True) or {}
    user_id, role_id = p.get("user_id"), p.get("role_id")
    if not (user_id and role_id):
        return jsonify({"error": "invalid_payload"}), 400
    # Proposer un plan de développement pour quelqu'un, c'est le noter : même
    # porte, même clé.
    ok, motif = peut_noter(current_user(), user_id, "2", role_id=role_id)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    activites = contexte_ecart(user_id, role_id)
    if not activites:
        return jsonify({"actions": [], "source": "no_gap", "activites": []}), 200
    parametres = p.get("parametres") or dict(PARAMETRES_DEFAUT)
    seance = _prochaine_seance(user_id, role_id)
    actions, source = _plan_ia(activites, parametres, _lang(), seance)
    return jsonify({"actions": actions, "source": source, "activites": activites,
                    "seance": seance}), 200


@plan_bp.route("/enregistrer", methods=["POST"])
def enregistrer():
    p = request.get_json(force=True) or {}
    user_id, role_id = p.get("user_id"), p.get("role_id")
    if not (user_id and role_id):
        return jsonify({"error": "invalid_payload"}), 400
    ok, motif = peut_noter(current_user(), user_id, "2", role_id=role_id)
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
    return jsonify(_serialiser(plan, contexte_ecart(user_id, role_id),
                               seance=_prochaine_seance(user_id, role_id))), 200


@plan_bp.route("/<int:user_id>/<int:role_id>", methods=["DELETE"])
def supprimer(user_id, role_id):
    ok, motif = peut_noter(current_user(), user_id, "2", role_id=role_id)
    if not ok:
        return jsonify({"error": "forbidden", "reason": motif}), 403
    plan = _charger(user_id, role_id)
    if plan is not None:
        db.session.delete(plan)
        db.session.commit()
    return jsonify({"ok": True}), 200
