# -*- coding: utf-8 -*-
"""L'HISTORIQUE DES NOTES — une courbe par sortie, et celle de l'activité.

⚠️⚠️ DEUX RÉGIMES, DEUX PROFONDEURS D'HISTORIQUE, et l'écran doit le dire :

  - une sortie MESURÉE garde tout. Chaque palier est une LIGNE qui porte sa
    cible et son échéance AVANT, sa mesure et son verdict APRÈS — c'est ce qui
    en fait un point d'historique. On relit donc la progression séance par
    séance. ⚠️ Mais un palier ne stocke PAS de niveau : le niveau de chaque
    date se RECALCULE depuis la mesure, avec les seuils d'aujourd'hui (la
    norme est la norme, elle ne change pas rétroactivement de sens).

  - une sortie JUGÉE À LA MAIN n'a qu'UN point. `/mastery/evaluate` fait un
    upsert sur (collaborateur, activité, sortie, évaluateur) : la note
    précédente est ÉCRASÉE, et seule sa date (`evaluated_at`) survit. Sa
    « courbe » est donc un point, et l'écran ne doit pas faire croire à une
    progression qu'on n'a pas gardée. `tracable` le dit, sortie par sortie.

⚠️ LE NIVEAU DE L'ACTIVITÉ n'existe QUE là où TOUTES les sorties portent une
note — c'est la règle du module (le MINIMUM, et NULL tant qu'il en manque une :
NULL ≠ 0). Le grand chiffre de l'écran dit « — » au même moment, et la frise
ne doit pas inventer un niveau que la carte du dessus refuse d'afficher.

⚠️ Et le niveau d'une sortie SE CONSERVE d'une date à l'autre : il vaut jusqu'à
la note suivante. Sans ce report, la colonne du jour ne porterait que la sortie
qu'on vient de noter — la globale sauterait à SA valeur, et elle annoncerait 4
pour une activité qui vaut 2.
"""
from datetime import datetime

from Code.models.models import CompetencyEvaluation
from Code.paliers import (NIVEAU_EXPERTISE, mesurable, niveau_depuis_mesure,
                          paliers_de, pas_de_progression, seuil_au_dela)
from Code.routes.qualify_outputs import get_activity_outputs

RESULT_ITEM_TYPE = "activity_results"
# Seuls Garant et Manager posent le niveau qui fait foi (CDC 3.6) : une
# auto-évaluation n'entre jamais dans l'historique officiel.
VALIDANTS = ("1", "2")


def _jour(x):
    """Une date, qu'on nous donne un Date ou un DateTime."""
    if x is None:
        return None
    return x.date() if isinstance(x, datetime) else x


def _points_mesuree(d, user_id, role_id):
    """Un point par palier RÉELLEMENT mesuré, dans l'ordre des dates."""
    paliers = paliers_de(user_id, d.id, role_id)
    cibles = [p.cible_valeur for p in paliers]
    premiere = cibles[0] if cibles else None
    marge = pas_de_progression(cibles, d.norme_valeur, d.norme_sens)
    au_dela = seuil_au_dela(cibles, d.norme_valeur, d.norme_sens, marge)
    pts = []
    for p in paliers:
        quand = _jour(p.evalue_le)
        if p.mesure_valeur is None or quand is None:
            continue
        n = niveau_depuis_mesure(p.mesure_valeur, d.norme_valeur, d.norme_sens,
                                 premiere, marge, au_dela)
        if n is not None:
            pts.append({"jour": quand, "niveau": n, "mesure": p.mesure_valeur})
    pts.sort(key=lambda p: p["jour"])
    return pts


def _eval_validee(user_id, activity_id, data_id):
    """La note qui fait foi — la dernière posée par un Garant ou un Manager.

    Même règle que `mastery._reference_eval` ; elle est redite ici parce que
    ce module ne peut pas importer la route (c'est la route qui l'importe).
    """
    best = None
    for ev in CompetencyEvaluation.query.filter_by(
            user_id=user_id, activity_id=activity_id,
            item_type=RESULT_ITEM_TYPE, item_id=data_id).all():
        if ev.eval_number in VALIDANTS and ev.mastery_level is not None:
            quand = ev.evaluated_at or datetime.min
            if best is None or quand >= (best.evaluated_at or datetime.min):
                best = ev
    return best


def _points_sortie(d, user_id, activity_id, role_id):
    """Les points d'UNE sortie, et si son régime garde vraiment un historique."""
    ev = _eval_validee(user_id, activity_id, d.id)
    if mesurable(d):
        pts = _points_mesuree(d, user_id, role_id)
        # ⚠️ L'EXPERTISE posée à la main l'emporte sur la déduction, qui
        # plafonne à 3 : c'est la règle de `activity_mastery`, et l'historique
        # mentirait s'il s'arrêtait à la dernière mesure.
        if ev is not None and ev.mastery_level == NIVEAU_EXPERTISE:
            quand = _jour(ev.evaluated_at)
            if quand is not None:
                pts = [p for p in pts if p["jour"] < quand]
                pts.append({"jour": quand, "niveau": NIVEAU_EXPERTISE, "mesure": None})
        return pts, True
    if ev is None or _jour(ev.evaluated_at) is None:
        return [], False
    return [{"jour": _jour(ev.evaluated_at), "niveau": ev.mastery_level,
             "mesure": None}], False


def historique_activite(user_id, activity_id, role_id=None):
    """Une courbe par sortie, plus celle du niveau de l'activité.

    Les dates sont l'UNION de toutes celles qui portent une note : chaque
    point dit l'index de sa date, pour que l'écran n'ait rien à recouper.
    """
    sorties = get_activity_outputs(activity_id)
    brut = []
    for i, d in enumerate(sorties):
        pts, tracable = _points_sortie(d, user_id, activity_id, role_id)
        brut.append({"data_id": d.id, "num": i + 1, "nom": d.name,
                     "mesurable": mesurable(d), "tracable": tracable,
                     "unite": (d.norme_unite or "") if mesurable(d) else "",
                     "_pts": pts})

    jours = sorted({p["jour"] for s in brut for p in s["_pts"]})
    index = {j: k for k, j in enumerate(jours)}

    sorties_json = []
    for s in brut:
        sorties_json.append({
            "data_id": s["data_id"], "num": s["num"], "nom": s["nom"],
            "mesurable": s["mesurable"], "tracable": s["tracable"],
            "unite": s["unite"],
            "points": [{"t": index[p["jour"]], "niveau": p["niveau"],
                        "mesure": p["mesure"]} for p in s["_pts"]],
        })

    # ── LA COURBE GLOBALE ────────────────────────────────────────────────
    # Report du dernier niveau connu de chaque sortie, et rien tant qu'il en
    # manque une : l'activité n'a pas de niveau, on n'en dessine pas.
    vu, glob = {}, []
    for k, j in enumerate(jours):
        for s in brut:
            for p in s["_pts"]:
                if p["jour"] == j:
                    vu[s["data_id"]] = p["niveau"]
        if len(vu) == len(brut) and brut:
            glob.append({"t": k, "niveau": min(vu.values())})

    return {
        "activity_id": activity_id, "role_id": role_id,
        "dates": [j.isoformat() for j in jours],
        "sorties": sorties_json,
        "global": glob,
        "complet": bool(brut) and len(vu) == len(brut),
        # Sortie par sortie, ce qui n'a qu'une note parce que son régime n'en
        # garde pas davantage : l'écran le dit au lieu de laisser croire.
        "sans_note": [s["nom"] for s in brut if not s["_pts"]],
        "une_seule_note": [s["nom"] for s in brut
                           if s["_pts"] and not s["tracable"]],
    }
