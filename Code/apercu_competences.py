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


def _paliers_multi(user_ids, data_ids):
    """{(user_id, data_id): [palier, …]} — la progression de PLUSIEURS
    personnes en UNE requête, dans l'ordre où `paliers_de` la rend.

    ⚠️ Une requête par personne, c'est le défaut que tout ce fichier existe
    pour éviter : la galerie d'accueil les lit toutes d'un coup.
    """
    par_sortie = defaultdict(list)
    if not user_ids or not data_ids:
        return par_sortie
    for p in (PalierPerformance.query
              .filter(PalierPerformance.user_id.in_(list(user_ids)),
                      PalierPerformance.data_id.in_(list(data_ids)))
              .order_by(PalierPerformance.rang, PalierPerformance.id).all()):
        par_sortie[(p.user_id, p.data_id)].append(p)
    return par_sortie


def _paliers_en_bloc(user_id, data_ids):
    """{data_id: [palier, …]} — toute la progression d'une personne en UNE
    requête, dans l'ordre où `paliers_de` la rend."""
    multi = _paliers_multi([user_id], data_ids)
    par_sortie = defaultdict(list)
    for (uid, did), lst in multi.items():
        if uid == user_id:
            par_sortie[did] = lst
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


def _activites_du(user_id, act_ids, roles, requis, actes, sorties_par_act,
                  datas, refs, paliers):
    """Une ligne par activité, pour UNE personne — dans l'ordre d'`act_ids`.

    ⚠️ Extrait d'`apercu` pour que la GALERIE d'accueil et la vue d'ensemble
    comptent avec le MÊME code. Une carte d'accueil est la vignette du dossier
    qu'elle ouvre : deux calculs d'un même niveau finiraient par afficher deux
    chiffres, et c'est une enquête qu'on a déjà payée ici.

    `paliers` est indexé par `data_id` : la progression de CETTE personne.
    """
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
    return activites


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

    activites = _activites_du(user_id, act_ids, roles, requis, actes,
                              sorties_par_act, datas, refs, paliers)

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


# ══ La GALERIE d'accueil ════════════════════════════════════════════════
# Une carte par collaborateur, chacune avec le profil qu'on retrouvera en
# grand dans son dossier. Tout ce qui suit sert à la servir en un nombre FIXE
# de requêtes : `apercu` par personne, ce serait une dizaine chacune — dix
# personnes, cent requêtes, à ~15 ms l'aller vers Neon.


def _suivis_en_bloc(acteur, user_ids):
    """{user_id: None | [role_id, …]} — la règle de `roles_suivis`, en BLOC.

    `None` veut dire « aucune restriction » ; une liste VIDE veut dire « il
    n'en suit aucun ». Les confondre rouvrirait le défaut que `roles_suivis`
    ferme — un développeur de 2 rôles sur 4 qui en voit 4.

    ⚠️ L'appeler par personne referait deux requêtes chacune : on lit les
    comptes et les rattachements par rôle une fois pour toutes.
    """
    from Code.competences_acces import _statut_eleve
    if acteur is None:
        return {uid: [] for uid in user_ids}
    if _statut_eleve(acteur):
        return {uid: None for uid in user_ids}
    gens = ({u.id: u for u in User.query.filter(User.id.in_(list(user_ids))).all()}
            if user_ids else {})
    par_role = defaultdict(list)
    for ur in UserRole.query.filter_by(manager_id=acteur.id).all():
        par_role[ur.user_id].append(ur.role_id)
    out = {}
    for uid in user_ids:
        u = gens.get(uid)
        if uid == acteur.id or (u is not None and u.manager_id == acteur.id):
            out[uid] = None
        else:
            out[uid] = par_role.get(uid, [])
    return out


def galerie(acteur, gens):
    """Une carte par collaborateur : son profil, sa couverture, ses compteurs.

    `gens` est la liste d'objets `User` à montrer — celle que la page sert
    déjà (`/competences/contexte`), donc celle que l'acteur a le droit de
    lire. Le périmètre des RÔLES, lui, reste celui de `roles_suivis`.

    ⚠️ Les axes du mini radar sont ceux de CETTE personne, triés par écart
    croissant — exactement `synthese.profil`, que le radar du dossier dessine.
    Une carte est la vignette du dossier qu'elle ouvre : des axes communs à
    tout le monde donneraient deux graphes différents de la même personne.
    """
    from Code.competences_globales import _references

    user_ids = [u.id for u in gens]
    suivis = _suivis_en_bloc(acteur, user_ids)

    # Les rôles tenus, puis les activités de ces rôles : deux requêtes pour
    # tout le monde, pas deux par personne.
    roles_de = defaultdict(list)
    if user_ids:
        for ur in UserRole.query.filter(UserRole.user_id.in_(user_ids)).all():
            s = suivis.get(ur.user_id)
            if s is None or ur.role_id in s:
                roles_de[ur.user_id].append(ur.role_id)
    tous_roles = sorted({rid for lst in roles_de.values() for rid in lst})
    roles = ({r.id: r for r in Role.query.filter(Role.id.in_(tous_roles)).all()}
             if tous_roles else {})

    requis = _requis_en_bloc(tous_roles)
    act_ids = sorted({a for (a, _r) in requis})
    actes = ({a.id: a for a in Activities.query.filter(Activities.id.in_(act_ids)).all()}
             if act_ids else {})
    sorties_par_act = output_ids_en_bloc(act_ids)
    data_ids = sorted({d for s in sorties_par_act.values() for d in s})
    datas = ({d.id: d for d in Data.query.filter(Data.id.in_(data_ids)).all()}
             if data_ids else {})
    refs = _references(user_ids, act_ids)
    paliers = _paliers_multi(user_ids, data_ids)

    # Une passe pour ranger les paliers par personne : les reparcourir tous à
    # chaque collaborateur ferait grandir le coût avec le carré de l'effectif.
    pal_de = defaultdict(dict)
    for (uid, did), lst in paliers.items():
        pal_de[uid][did] = lst

    cartes, totaux = [], {"held": 0, "gap": 0, "todo": 0, "setup": 0}
    for u in gens:
        mes_roles = {rid: roles[rid] for rid in roles_de.get(u.id, []) if rid in roles}
        mes_acts = sorted({a for (a, rid) in requis if rid in mes_roles})
        lignes = _activites_du(u.id, mes_acts, mes_roles, requis, actes,
                               sorties_par_act, datas, refs, pal_de.get(u.id, {}))
        compte = {"held": 0, "gap": 0, "todo": 0, "setup": 0}
        for a in lignes:
            compte[a["etat"]] += 1
            totaux[a["etat"]] += 1
        # Le MÊME tri que `synthese.profil` : l'écart le plus criant d'abord,
        # ce qui n'a pas d'écart à la fin. C'est l'ordre des axes du radar du
        # dossier — la vignette doit avoir la même forme que l'original.
        axes = [{"activity_id": a["activity_id"],
                 "activity_name": a["activity_name"],
                 "required_level": a["required_level"],
                 "demonstrated_level": a["demonstrated_level"]}
                for a in sorted(lignes,
                                key=lambda a: ((a["gap"] if a["gap"] is not None else 99),
                                               a["activity_name"].lower()))]
        poses = [a["demonstrated_level"] for a in lignes
                 if a["demonstrated_level"] is not None]
        cartes.append({
            "user_id": u.id,
            "first_name": u.first_name or "",
            "last_name": u.last_name or "",
            "roles": sorted((nom_affiche(r) for r in mes_roles.values()),
                            key=lambda n: n.lower()),
            "n_activities": len(lignes),
            "n_evaluated": len(poses),
            "couverture": couverture(lignes),
            "compte": compte,
            "axes": axes,
        })
    return {"gens": cartes, "totaux": totaux}
