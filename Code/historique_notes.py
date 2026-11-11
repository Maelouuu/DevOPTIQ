# -*- coding: utf-8 -*-
"""L'HISTORIQUE DES NOTES — une courbe par sortie, et celle de l'activité.

⚠️⚠️ CE QUI MANQUAIT DANS LA BASE, ET QUI EST COMBLÉ ICI.

Une sortie n'a que deux manières d'être notée, et toutes deux doivent laisser
une trace datée :

  - une sortie MESURÉE garde tout depuis toujours. Chaque palier est une ligne
    qui porte sa cible et son échéance AVANT, sa mesure et son verdict APRÈS.
    ⚠️ Mais un palier ne stockait PAS de niveau : on le recalculait à chaque
    lecture, avec les seuils d'AUJOURD'HUI. Poser plus tard une marche au-delà
    de la norme relisait alors tout le passé avec la nouvelle frontière, et
    l'historique changeait rétroactivement sans que personne n'ait rien
    touché. `PalierPerformance.niveau_atteint` fige désormais le verdict du
    jour ; on ne retombe sur la déduction que pour les lignes d'avant.

  - une sortie JUGÉE À LA MAIN n'avait AUCUN historique. `/mastery/evaluate`
    écrase la ligne `CompetencyEvaluation` à chaque enregistrement : la note
    précédente disparaît, seule sa date survit. Sa « courbe » était un point.
    `NoteEvaluation` est le REGISTRE qui manquait : un événement par écriture,
    en ajout seul. L'état courant reste dans `CompetencyEvaluation` — lu
    partout, et c'est bien — l'histoire vit dans le registre.

⚠️ LE NIVEAU DE L'ACTIVITÉ n'existe QUE là où TOUTES les sorties portent une
note — c'est la règle du module (le MINIMUM, et NULL tant qu'il en manque une :
NULL ≠ 0). Le grand chiffre de l'écran dit « — » au même moment, et la frise
ne doit pas inventer un niveau que la carte du dessus refuse d'afficher.

⚠️ Et le niveau d'une sortie SE CONSERVE d'une date à l'autre : il vaut jusqu'à
l'événement suivant. Sans ce report, la colonne du jour ne porterait que la
sortie qu'on vient de noter — la globale sauterait à SA valeur, et elle
annoncerait 4 pour une activité qui vaut 2.
"""
from datetime import datetime

from Code.extensions import db
from Code.models.models import CompetencyEvaluation, NoteEvaluation
from Code.paliers import (mesurable, niveau_depuis_mesure, paliers_de,
                          pas_de_progression, seuil_au_dela)
from Code.routes.qualify_outputs import get_activity_outputs

RESULT_ITEM_TYPE = "activity_results"
# Seuls Garant et Manager posent le niveau qui fait foi (CDC 3.6) : une
# auto-évaluation n'entre jamais dans l'historique officiel.
VALIDANTS = ("1", "2")
CLE_REPRISE = "notes_evaluation_reprise"


def _jour(x):
    """Une date, qu'on nous donne un Date ou un DateTime."""
    if x is None:
        return None
    return x.date() if isinstance(x, datetime) else x


def _points_mesuree(d, user_id, role_id):
    """Un point par palier RÉELLEMENT mesuré, dans l'ordre des dates.

    ⚠️ Le niveau vient du palier quand il le porte. La déduction ne sert plus
    que de repli pour les lignes tranchées avant que la colonne existe : sans
    ce repli, tout l'historique d'avant tomberait d'un coup.
    """
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
        n = p.niveau_atteint
        if n is None:
            n = niveau_depuis_mesure(p.mesure_valeur, d.norme_valeur, d.norme_sens,
                                     premiere, marge, au_dela)
        if n is not None:
            pts.append({"jour": quand, "niveau": n, "mesure": p.mesure_valeur,
                        "source": "palier"})
    return pts


def _evenements(user_id, activity_id, data_id):
    """Le registre des notes posées à la main, dans l'ordre.

    ⚠️ Pas de filtre de rôle : une note vaut pour (collaborateur, activité,
    sortie, évaluateur), exactement comme la ligne d'état courant. Filtrer sur
    le rôle ferait disparaître l'historique d'une personne qui change de rôle.
    """
    q = (NoteEvaluation.query
         .filter(NoteEvaluation.user_id == user_id,
                 NoteEvaluation.activity_id == activity_id,
                 NoteEvaluation.data_id == data_id,
                 NoteEvaluation.eval_number.in_(VALIDANTS))
         .order_by(NoteEvaluation.posee_le, NoteEvaluation.id))
    return [{"jour": _jour(e.posee_le), "niveau": e.niveau, "mesure": None,
             "source": e.source} for e in q.all() if e.posee_le is not None]


def _points_sortie(d, user_id, activity_id, role_id):
    """La chronologie d'UNE sortie, les deux sources réunies."""
    bruts = []
    if mesurable(d):
        bruts += _points_mesuree(d, user_id, role_id)
    # Sur une sortie mesurée, la main ne pose que l'EXPERTISE (la déduction
    # plafonne à 3) ou son effacement : les deux doivent entrer dans la
    # chronologie, sinon elle s'arrête à la dernière mesure.
    bruts += _evenements(user_id, activity_id, d.id)

    # ⚠️ Deux écritures le MÊME jour ne font pas deux points : c'est l'état du
    # jour qui compte, donc la dernière. Sinon la courbe rebrousse chemin sur
    # une abscisse unique. Le tri est STABLE, et les événements à la main sont
    # ajoutés après les paliers : à égalité de jour, la main l'emporte — c'est
    # la règle de `activity_mastery`, où l'expertise posée gagne.
    par_jour = {}
    for p in sorted(bruts, key=lambda p: p["jour"]):
        par_jour[p["jour"]] = p
    return [par_jour[j] for j in sorted(par_jour)]


def historique_activite(user_id, activity_id, role_id=None):
    """Une courbe par sortie, plus celle du niveau de l'activité.

    Les dates sont l'UNION de toutes celles qui portent un événement : chaque
    point dit l'index de sa date, pour que l'écran n'ait rien à recouper.
    """
    sorties = get_activity_outputs(activity_id)
    brut = []
    for i, d in enumerate(sorties):
        pts = _points_sortie(d, user_id, activity_id, role_id)
        brut.append({"data_id": d.id, "num": i + 1, "nom": d.name,
                     "mesurable": mesurable(d),
                     "unite": (d.norme_unite or "") if mesurable(d) else "",
                     "_pts": pts})

    # ⚠️ Un effacement (niveau NULL) est un vrai événement : il ne se dessine
    # pas — il n'y a pas de point à tracer — mais il DATE la fin du report.
    jours = sorted({p["jour"] for s in brut for p in s["_pts"]})
    index = {j: k for k, j in enumerate(jours)}

    sorties_json = []
    for s in brut:
        sorties_json.append({
            "data_id": s["data_id"], "num": s["num"], "nom": s["nom"],
            "mesurable": s["mesurable"], "unite": s["unite"],
            # Les deux régimes gardent désormais une histoire : le drapeau
            # reste, et il vaut vrai des deux côtés.
            "tracable": True,
            "points": [{"t": index[p["jour"]], "niveau": p["niveau"],
                        "mesure": p["mesure"]}
                       for p in s["_pts"] if p["niveau"] is not None],
        })

    # ── LA COURBE GLOBALE ────────────────────────────────────────────────
    vu, glob = {}, []
    for k, j in enumerate(jours):
        for s in brut:
            for p in s["_pts"]:
                if p["jour"] != j:
                    continue
                if p["niveau"] is None:
                    vu.pop(s["data_id"], None)   # note retirée : elle ne pèse plus
                else:
                    vu[s["data_id"]] = p["niveau"]
        if len(vu) == len(brut) and brut:
            glob.append({"t": k, "niveau": min(vu.values())})

    return {
        "activity_id": activity_id, "role_id": role_id,
        "dates": [j.isoformat() for j in jours],
        "sorties": sorties_json,
        "global": glob,
        "complet": bool(brut) and len(vu) == len(brut),
        "sans_note": [s["nom"] for s in brut
                      if not any(p["niveau"] is not None for p in s["_pts"])],
        # ⚠️ Les sorties dont TOUT l'historique vient de la reprise : avant le
        # registre, seule la dernière note était gardée. Leur courbe commence
        # donc à cette reprise, et l'écran le dit au lieu de laisser croire
        # qu'elles n'ont été notées qu'une fois. La mention disparaît d'elle-
        # même dès qu'une note est posée après.
        "avant_registre": [s["nom"] for s in brut
                           if s["_pts"] and all(p["source"] == "reprise"
                                                for p in s["_pts"])],
    }


def reprendre_notes_existantes(force=False):
    """Recopie UNE FOIS l'état courant dans le registre.

    Sans elle, les notes déjà posées n'auraient aucun point : la frise perdrait
    le seul qu'elle savait montrer. Ces lignes portent `source='reprise'` — on
    ne présente pas une recopie comme une note qu'on aurait vue poser ce
    jour-là, et c'est ce qui permet à l'écran de dire d'où part l'historique.

    ⚠️ Le marqueur vit en BASE, pas en mémoire : une instance qui redémarre,
    se duplique ou se redéploie doit lire la même réponse. Rejouée à chaque
    démarrage, la reprise ajouterait une ligne de plus à chaque fois.
    """
    from Code.models.models import AppSetting
    if not force:
        try:
            if db.session.get(AppSetting, CLE_REPRISE) is not None:
                return 0
        except Exception:
            db.session.rollback()
            return 0

    deja = {(n.user_id, n.activity_id, n.data_id, n.eval_number)
            for n in NoteEvaluation.query.filter_by(source="reprise").all()}
    n = 0
    for ev in CompetencyEvaluation.query.filter_by(item_type=RESULT_ITEM_TYPE).all():
        if ev.mastery_level is None or ev.evaluated_at is None or ev.item_id is None:
            continue
        cle = (ev.user_id, ev.activity_id, ev.item_id, ev.eval_number)
        if cle in deja:
            continue
        deja.add(cle)
        db.session.add(NoteEvaluation(
            user_id=ev.user_id, activity_id=ev.activity_id, data_id=ev.item_id,
            role_id=None, eval_number=ev.eval_number, niveau=ev.mastery_level,
            evidence=ev.evidence, evaluator_user_id=ev.evaluator_user_id,
            posee_le=ev.evaluated_at, source="reprise"))
        n += 1

    if db.session.get(AppSetting, CLE_REPRISE) is None:
        db.session.add(AppSetting(key=CLE_REPRISE, value="1"))
    db.session.commit()
    return n
