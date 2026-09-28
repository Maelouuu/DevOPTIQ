# -*- coding: utf-8 -*-
"""Le tableau GLOBAL des compétences (page RH) : chaque personne × chacun de ses
rôles, sur toutes les cartos — ou sur une seule, si on filtre.

Mêmes règles que la page Compétences, et les MÊMES fonctions pour trancher :
- niveau d'une activité = MINIMUM de ses résultats, NULL tant qu'un résultat
  n'est pas évalué (NULL ≠ 0) ;
- niveau d'un rôle = MINIMUM de ses activités, et seulement si toutes celles
  qui ont des résultats sont évaluées ;
- couleur (`color_for`), état d'une activité (`categorie_activite`) et
  couverture (`couverture`) viennent de `Code/routes/mastery.py`. Deux écrans
  qui comptent avec deux codes finissent par afficher deux chiffres.

⚠️ Pourquoi pas `dashboard_rows` en boucle : il fait ~6 requêtes par activité
et par personne. Soixante personnes, deux rôles, quinze activités : dix mille
requêtes, à ~15 ms l'aller vers Neon — deux minutes et demie pour ouvrir la
page. Ici, un nombre FIXE de requêtes, quel que soit l'effectif.

⚠️ `get_activity_outputs` ÉCRIT (il matérialise les connexions sortantes en
`Data`) : on ne l'appelle pas depuis une page de lecture. On relit ce qu'il a
déjà matérialisé — les résultats qualifiés, seuls lus par l'évaluation, sont
toujours conservés par lui (`materialize_activity_outputs`).
"""
from collections import defaultdict
from datetime import datetime

from Code.extensions import db
from Code.models.models import (Activities, CompetencyEvaluation, Data, Entity,
                                Link, Role, User, UserRole, activity_roles)
from Code.routes.mastery import (RESULT_ITEM_TYPE, VALIDATING, categorie_activite,
                                 color_for, couverture, level_label)
from Code.routes.qualify_outputs import _norm

ETATS = ("held", "gap", "todo", "setup")


def _resultats(act_ids):
    """{activity_id: {data_id, …}} — les RÉSULTATS tels que `activity_mastery`
    les voit, sans rien écrire.

    `materialize_activity_outputs` indexe les `Data` d'une activité par nom
    normalisé (le dernier l'emporte) et garde toujours celles qui sont
    qualifiées ; `get_activity_outputs` y ajoute les `Data` visées par un lien
    sortant (`Link.target_data_id`) qui n'y sont pas déjà. Même lecture ici.
    """
    if not act_ids:
        return {}
    index = defaultdict(dict)
    for d in (Data.query.filter(Data.producer_activity_id.in_(act_ids))
              .order_by(Data.id).all()):
        index[d.producer_activity_id][_norm(d.name)] = d
    out = {a: {d.id for d in index[a].values() if d.semantic_nature == "RESULT"}
           for a in act_ids}

    vises = defaultdict(set)
    for lk in Link.query.filter(Link.source_activity_id.in_(act_ids),
                                Link.target_data_id.isnot(None)).all():
        vises[lk.source_activity_id].add(lk.target_data_id)
    tous = set().union(*vises.values()) if vises else set()
    if tous:
        nature = {d.id: d.semantic_nature
                  for d in Data.query.filter(Data.id.in_(tous)).all()}
        for a, ids in vises.items():
            deja = {d.id for d in index[a].values()}
            out[a] |= {i for i in ids if i not in deja and nature.get(i) == "RESULT"}
    return out


def _references(user_ids, act_ids):
    """{(user, activité, résultat): niveau} — la note qui FAIT FOI.

    Celle d'un garant ou d'un développeur de compétences (`VALIDATING`), la plus
    récente — exactement `mastery._reference_eval`. L'auto-évaluation n'y entre
    jamais : c'est un repère, pas un résultat.
    """
    if not user_ids or not act_ids:
        return {}
    meilleure = {}
    for ev in (CompetencyEvaluation.query
               .filter(CompetencyEvaluation.user_id.in_(user_ids),
                       CompetencyEvaluation.activity_id.in_(act_ids),
                       CompetencyEvaluation.item_type == RESULT_ITEM_TYPE)
               .order_by(CompetencyEvaluation.id).all()):
        if ev.eval_number not in VALIDATING or ev.mastery_level is None:
            continue
        cle = (ev.user_id, ev.activity_id, ev.item_id)
        best = meilleure.get(cle)
        if best is None or (ev.evaluated_at or datetime.min) >= (best.evaluated_at or datetime.min):
            meilleure[cle] = ev
    return {cle: ev.mastery_level for cle, ev in meilleure.items()}


def _ligne(uid, act_id, requis, resultats, refs):
    """Une activité pour une personne — les champs que lisent `categorie_activite`
    et `couverture`, calculés comme `activity_mastery`."""
    niveaux = [refs.get((uid, act_id, d)) for d in resultats]
    notes = [n for n in niveaux if n is not None]
    complet = len(notes) == len(niveaux)
    niveau = min(notes) if (notes and complet) else None
    return {
        "activity_id": act_id,
        "n_results": len(resultats),
        "demonstrated_level": niveau,
        "required_level": requis,
        "gap": (niveau - requis) if (niveau is not None and requis is not None) else None,
    }


def _synthese_role(lignes):
    """Le résumé d'un rôle — la règle de `mastery.synthese`, sur les mêmes lignes."""
    compte = dict.fromkeys(ETATS, 0)
    niveaux, requis, retards = [], [], 0
    for r in lignes:
        compte[categorie_activite(r)] += 1
        if r["demonstrated_level"] is not None:
            niveaux.append(r["demonstrated_level"])
        if r["required_level"] is not None:
            requis.append(r["required_level"])
        if r["gap"] is not None and r["gap"] < 0:
            retards += 1
    evaluables = [r for r in lignes if r["n_results"]]
    complet = bool(evaluables) and len(niveaux) == len(evaluables)
    niveau = min(niveaux) if (niveaux and complet) else None
    req = min(requis) if requis else None
    return {
        "level": niveau, "level_label": level_label(niveau),
        "required_level": req, "required_label": level_label(req),
        "color": color_for(niveau, req),
        "gap": (niveau - req) if (niveau is not None and req is not None) else None,
        "counts": compte,
        "n_activities": len(lignes),
        "n_evaluated": len(niveaux),
        "n_gap": retards,
        "couverture": couverture(lignes),
    }


def _lisibles(moi):
    """Les comptes dont `moi` peut lire le dossier : tout le monde pour un
    coordinateur ou un administrateur, sinon lui-même et ceux qu'il encadre.

    ⚠️ La règle de `competences_acces.peut_lire`, mais en BLOC : l'appeler par
    personne referait deux requêtes chacune.
    """
    from Code.competences_acces import _statut_eleve
    if _statut_eleve(moi):
        return None                   # pas de restriction
    ids = {moi.id}
    ids |= {u.id for u in User.query.filter_by(manager_id=moi.id).all()}
    ids |= {ur.user_id for ur in UserRole.query.filter_by(manager_id=moi.id).all()}
    return ids


def tableau_global(moi, entity_id=None):
    """Tout ce que dessine le bloc « Compétences » de la page RH, en un appel.

    `entity_id` restreint à une carto ; il doit être l'une des cartos que `moi`
    peut ouvrir, sinon on l'ignore (l'identifiant vient du navigateur).
    """
    from Code.role_i18n import nom_affiche

    ouvrables = Entity.accessible(moi.id)
    cartos = sorted(ouvrables, key=lambda e: (e.name or "").lower())
    if entity_id and any(e.id == entity_id for e in cartos):
        visees = [e for e in cartos if e.id == entity_id]
    else:
        entity_id = None
        visees = cartos
    nom_carto = {e.id: e.name for e in visees}

    # Un rôle est commun à l'entreprise : ce qui le rattache à une carto, ce
    # sont ses ACTIVITÉS.
    par_role = defaultdict(list)
    if nom_carto:
        for act_id, role_id, requis in db.session.execute(
                db.select(activity_roles.c.activity_id, activity_roles.c.role_id,
                          activity_roles.c.required_mastery_level)
                .select_from(activity_roles.join(
                    Activities, Activities.id == activity_roles.c.activity_id))
                .where(Activities.entity_id.in_(list(nom_carto)))).all():
            par_role[role_id].append((act_id, requis))
    roles = (Role.query.filter(Role.id.in_(list(par_role))).all()
             if par_role else [])
    # Un rôle sans activité n'a rien à évaluer (le développeur de compétences,
    # une bande vide) : une colonne entière de cases vides n'apprend rien.
    roles = [r for r in roles if par_role.get(r.id)]

    lisibles = _lisibles(moi)
    tenus = defaultdict(list)                       # user_id → [role_id]
    if roles:
        for ur in (UserRole.query.filter(UserRole.role_id.in_([r.id for r in roles]))
                   .order_by(UserRole.role_id).all()):
            if lisibles is None or ur.user_id in lisibles:
                tenus[ur.user_id].append(ur.role_id)
    gens = (User.query.filter(User.id.in_(list(tenus))).all() if tenus else [])

    act_ids = sorted({a for r in roles for a, _ in par_role[r.id]})
    resultats = _resultats(act_ids)
    refs = _references([u.id for u in gens], act_ids)

    # Les colonnes : les rôles tenus par au moins une personne.
    tenus_par_qqn = {rid for rids in tenus.values() for rid in rids}
    colonnes = [{"id": r.id, "name": nom_affiche(r),
                 "n_activities": len(par_role[r.id])}
                for r in roles if r.id in tenus_par_qqn]
    groupes = [{"carto_id": entity_id,
                "carto": nom_carto.get(entity_id, "") if entity_id else "",
                "roles": sorted(colonnes, key=lambda x: x["name"].lower())}] if colonnes else []

    personnes, totaux = [], dict.fromkeys(ETATS, 0)
    for u in gens:
        par_role_u, uniques, vues = {}, [], set()
        compte_u = dict.fromkeys(ETATS, 0)
        for rid in tenus[u.id]:
            lignes = [_ligne(u.id, a, req, resultats.get(a, set()), refs)
                      for a, req in par_role[rid]]
            s = _synthese_role(lignes)
            par_role_u[str(rid)] = s
            for k in ETATS:
                compte_u[k] += s["counts"][k]
            # Une activité portée par deux rôles ne compte qu'une fois dans la
            # couverture de la personne — la règle du profil de `synthese`.
            for li in lignes:
                if li["activity_id"] not in vues:
                    vues.add(li["activity_id"])
                    uniques.append(li)
        for k in ETATS:
            totaux[k] += compte_u[k]
        personnes.append({
            "id": u.id,
            "prenom": u.first_name or "", "nom": u.last_name or "",
            "email": u.email,
            "roles": par_role_u,
            "counts": compte_u,
            "couverture": couverture(uniques),
            "n_evaluated": sum(1 for li in uniques if li["demonstrated_level"] is not None),
            "n_activities": len(uniques),
        })
    personnes.sort(key=lambda p: ((p["nom"] or "").lower(), (p["prenom"] or "").lower()))

    return {
        "entity_id": entity_id,
        "cartos": [{"id": e.id, "name": e.name} for e in cartos],
        "colonnes": groupes,
        "personnes": personnes,
        "totaux": totaux,
    }
