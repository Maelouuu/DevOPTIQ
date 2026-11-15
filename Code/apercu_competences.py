# -*- coding: utf-8 -*-
"""La VUE D'ENSEMBLE de la page Compétences : tout ce qu'elle montre, en un
nombre FIXE de requêtes.

Le classement des activités, les marches de performance de chacune, la bande
de toutes les notes et le relief d'une sortie mesurée demandent les MÊMES
données : les sorties de chaque activité, la note qui fait foi sur chacune, et
leurs paliers. Les servir activité par activité, ce serait ~6 requêtes par
activité (`dashboard_rows`) plus une par sortie (`paliers_de`) — le défaut
déjà payé sur le tableau global de la page RH, qui mettait deux minutes et
demie à s'ouvrir.

⚠️ Mêmes règles que partout, et les MÊMES fonctions pour trancher : le niveau
d'une activité est le MINIMUM de ses sorties et NULL tant qu'il en manque une
(NULL ≠ 0) ; celui d'une sortie MESURÉE vient du chiffre relevé en séance, via
`paliers.etat_sortie`. Deux écrans qui comptent avec deux codes finissent par
afficher deux chiffres — c'est écrit en toutes lettres dans ce dépôt, et ça a
déjà coûté une enquête.

⚠️ `get_activity_outputs` ÉCRIT (il matérialise les connexions sortantes en
`Data`) : on ne l'appelle pas depuis une page de lecture. On relit ce qu'il a
déjà matérialisé, avec `output_ids_en_bloc`, qui porte la même règle.
"""
from collections import defaultdict

from Code.models.models import (Activities, Data, PalierPerformance, Role,
                                User, UserRole, activity_roles)
from Code.extensions import db
from Code.paliers import etat_sortie, mesurable
from Code.role_i18n import nom_affiche
from Code.routes.mastery import (categorie_activite, color_for, couverture,
                                 level_label)
from Code.routes.qualify_outputs import output_ids_en_bloc


def _paliers_en_bloc(user_id, data_ids):
    """{data_id: [palier, …]} — toute la progression d'une personne en UNE
    requête, dans l'ordre où `paliers_de` la rend."""
    par_sortie = defaultdict(list)
    if not data_ids:
        return par_sortie
    for p in (PalierPerformance.query
              .filter(PalierPerformance.user_id == user_id,
                      PalierPerformance.data_id.in_(list(data_ids)))
              .order_by(PalierPerformance.rang, PalierPerformance.id).all()):
        par_sortie[p.data_id].append(p)
    return par_sortie


def _requis_en_bloc(role_ids):
    """{(activity_id, role_id): niveau requis} — la table d'association, lue
    d'un coup."""
    requis = {}
    if not role_ids:
        return requis
    lignes = db.session.execute(
        activity_roles.select().where(activity_roles.c.role_id.in_(list(role_ids)))
    ).fetchall()
    for l in lignes:
        requis[(l.activity_id, l.role_id)] = getattr(l, "required_mastery_level", None)
    return requis


def apercu(acteur, user_id):
    """Ce que la vue d'ensemble affiche, pour un collaborateur.

    ⚠️ On ne liste QUE les rôles que l'acteur suit : `encadre()` répond par
    PERSONNE, et un développeur de 2 rôles sur 4 verrait les 4. C'est la règle
    de `roles_suivis`, et elle est la même ici que sur `/mastery/synthese` —
    deux périmètres dans le même écran, c'est la panne « j'ai perdu mes
    données de notation ».
    """
    from Code.competences_globales import _references
    from Code.competences_acces import roles_suivis

    cible = User.query.get(user_id)
    if not cible:
        return None

    suivis = roles_suivis(acteur, user_id)
    liens = UserRole.query.filter_by(user_id=user_id).all()
    role_ids = [ur.role_id for ur in liens
                if suivis is None or ur.role_id in suivis]
    roles = {r.id: r for r in Role.query.filter(Role.id.in_(role_ids)).all()} if role_ids else {}

    requis = _requis_en_bloc(roles.keys())
    act_ids = sorted({a for (a, _r) in requis})
    actes = {a.id: a for a in Activities.query.filter(Activities.id.in_(act_ids)).all()} \
        if act_ids else {}

    sorties_par_act = output_ids_en_bloc(act_ids)
    data_ids = sorted({d for s in sorties_par_act.values() for d in s})
    datas = {d.id: d for d in Data.query.filter(Data.id.in_(data_ids)).all()} if data_ids else {}
    refs = _references([user_id], act_ids)
    paliers = _paliers_en_bloc(user_id, data_ids)

    activites = []
    for aid in act_ids:
        act = actes.get(aid)
        if act is None:
            continue
        # ⚠️ Le requis d'une activité portée par DEUX rôles : le plus exigeant.
        # Prendre le premier venu ferait dépendre le verdict de l'ordre des
        # lignes — et une activité paraîtrait tenue parce qu'un rôle n'exige
        # rien d'elle.
        exigences = [requis[(aid, rid)] for rid in roles
                     if (aid, rid) in requis and requis[(aid, rid)] is not None]
        req = max(exigences) if exigences else None

        sorties = []
        for did in sorted(sorties_par_act.get(aid, ())):
            d = datas.get(did)
            if d is None:
                continue
            if mesurable(d):
                e = etat_sortie(d, user_id, paliers=paliers.get(did, []))
                e["note_main"] = refs.get((user_id, aid, did))
                sorties.append(e)
            else:
                sorties.append({
                    "data_id": did, "nom": d.name, "mesurable": False,
                    "norme": None, "paliers": [], "palier_en_cours": None,
                    "mesure": None, "mesure_le": None, "au_dela": None,
                    "qualifie": None,
                    "niveau": refs.get((user_id, aid, did)),
                    "note_main": refs.get((user_id, aid, did)),
                })

        niveaux = [s["niveau"] for s in sorties]
        notes = [n for n in niveaux if n is not None]
        complet = bool(niveaux) and len(notes) == len(niveaux)
        niveau = min(notes) if (notes and complet) else None
        ligne = {
            "activity_id": aid,
            "activity_name": act.name,
            "n_results": len(sorties),
            "demonstrated_level": niveau,
            "required_level": req,
            "gap": (niveau - req) if (niveau is not None and req is not None) else None,
        }
        # Par quels rôles cette activité est tenue : la vue d'ensemble ouvre
        # l'écran d'évaluation, et celui-ci se cadre TOUJOURS sur un rôle (le
        # niveau attendu vient du rôle, pas de l'activité).
        ligne["role_ids"] = [rid for rid in roles if (aid, rid) in requis]
        ligne["etat"] = categorie_activite(ligne)
        ligne["color"] = color_for(niveau, req)
        ligne["level_label"] = level_label(niveau)
        ligne["sorties"] = sorties
        activites.append(ligne)

    # Le classement : du plus bas au plus haut, et ce qui n'a pas de verdict à
    # la fin — une activité non évaluée n'est pas un zéro, elle n'a pas de
    # rang dans la progression.
    activites.sort(key=lambda a: (a["demonstrated_level"] is None,
                                  a["demonstrated_level"] if a["demonstrated_level"] is not None else 0,
                                  a["activity_name"].lower()))

    compte = {"held": 0, "gap": 0, "todo": 0, "setup": 0}
    for a in activites:
        compte[a["etat"]] += 1
    poses = [a["demonstrated_level"] for a in activites if a["demonstrated_level"] is not None]
    evaluables = [a for a in activites if a["n_results"]]
    complet = bool(evaluables) and len(poses) == len(evaluables)

    return {
        "user_id": user_id,
        "user_name": f"{cible.first_name or ''} {cible.last_name or ''}".strip(),
        "n_roles": len(roles),
        "n_activities": len(activites),
        "n_sorties": sum(a["n_results"] for a in activites),
        "couverture": couverture(activites),
        # ⚠️ DEUX chiffres, et ils ne disent pas la même chose.
        # `niveau` est le VERDICT : le minimum, et NULL tant qu'une activité
        # évaluable n'est pas notée — la règle de tout le module, celle qui
        # refuse de déclarer tenu un collaborateur à moitié noté.
        # `plus_bas` DÉCRIT : le plus bas de ce qui est posé, quoi qu'il
        # manque. C'est lui que la vue d'ensemble montre, sous « ce qui tient
        # tout en bas » — et le compteur « sans verdict » dit juste à côté
        # combien d'activités n'ont pas encore été regardées. Sans cette
        # distinction, l'écran afficherait « — » chez quelqu'un qui a huit
        # activités dont six notées, et ne dirait plus rien du tout.
        "niveau": min(poses) if (poses and complet) else None,
        "plus_bas": min(poses) if poses else None,
        "compte": compte,
        "roles": sorted(({"role_id": r.id, "role_name": nom_affiche(r)}
                         for r in roles.values()),
                        key=lambda r: r["role_name"].lower()),
        "activites": activites,
    }
