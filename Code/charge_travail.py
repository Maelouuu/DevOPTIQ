# -*- coding: utf-8 -*-
"""LA CHARGE DE TRAVAIL : le poids d'un rôle, celui d'une personne, le plafond.

Le poids d'un rôle est mesuré sur la page Temps (une analyse de rôle : ses
activités, leurs durées, leurs rythmes). Ce module le rend LISIBLE côté
ressources humaines : qui porte combien, et où ça déborde.

⚠️ **Le poids d'une personne est la SOMME des poids de ses rôles.** C'est la
règle demandée, et c'est la conservatrice : le poids d'un rôle est le travail
que ce rôle exige de qui le tient. On ne le DIVISE pas par le nombre de
titulaires — ce serait inventer un partage que personne n'a décidé. La ligne
d'un rôle affiche donc son nombre de titulaires : la question se voit.

⚠️ **Le plafond est 80 % d'un temps plein** (`PART_PLAFOND`) : on ne planifie
personne à 100 % de son année. C'est un plafond de PRÉVENTION — l'écran avertit,
il ne refuse jamais : la décision d'affecter quelqu'un appartient à qui affecte.

⚠️ **Tout est cadré par une PÉRIODE** (`Code/periode.py`). Une analyse de temps
n'est pas vraie pour l'éternité : un rôle mesuré en janvier peut avoir changé en
novembre. Un rôle sans analyse pour la période regardée est « non mesuré » —
JAMAIS zéro, et l'écran dit en quel mois il l'a été pour la dernière fois.

⚠️ **Le calendrier est celui de l'entité ACTIVE** (`get_calendar_params`), même
quand le tableau traverse plusieurs cartos : c'est celui avec lequel
`_role_summary` annualise déjà, donc les chiffres d'ici et ceux de la page Temps
ne peuvent pas diverger. L'écran nomme l'entité dont il lit le calendrier.

⚠️ **Le coût ne grandit pas avec l'effectif** : un nombre FIXE de requêtes,
quelles que soient les personnes, les rôles et les analyses. `_role_summary`
appelé en boucle, lui, demanderait `get_calendar_params()` et une requête par
ligne — c'est le défaut qui mettait le tableau des compétences à deux minutes
et demie.
"""

from sqlalchemy.orm import selectinload

from Code.extensions import db
from Code.models.models import (
    Activities, Entity, Role, User, UserRole,
    TimeRoleAnalysis,
)

#: Le plafond de prévention : 80 % d'un temps plein.
PART_PLAFOND = 0.80


# ═══════════════════════════════════════════════════════════════════════════
#  Le décor : tout ce qu'il faut pour peser, chargé UNE fois
# ═══════════════════════════════════════════════════════════════════════════

def _decor():
    """Les caches de lecture : durées d'activité, entité de chaque activité.

    ⚠️ `_line_duration` retombe sur `activity_duration_minutes(id)` quand la
    ligne ne porte pas sa durée — une requête PAR LIGNE. On la lui donne.
    """
    durees, entites = {}, {}
    for a in db.session.query(Activities.id, Activities.duration_minutes,
                              Activities.entity_id).all():
        durees[a.id] = float(a.duration_minutes or 0)
        entites[a.id] = a.entity_id
    noms_entites = {e.id: e.name for e in db.session.query(Entity.id, Entity.name).all()}
    return durees, entites, noms_entites


def _entite_de(analyse, entites):
    """La carto sur laquelle porte une analyse de rôle.

    ⚠️ Les lignes d'une analyse viennent toutes de la MÊME carto :
    `/temps/api/role_activities` les filtre sur l'entité active. On lit donc
    celle de la première ligne. Une analyse bâtie autrement compterait pour
    sa première carto — et comme l'écran NOMME l'entité, l'anomalie se voit.
    """
    for ln in analyse.lines:
        e = entites.get(ln.activity_id)
        if e:
            return e
    return None


def periodes_disponibles():
    """Les mois pour lesquels au moins un rôle est mesuré, du plus récent.

    ⚠️ Les analyses de RÔLE seulement : c'est le seul poids que ce tableau
    lit. Offrir les mois d'une faiblesse ferait choisir une période où la
    colonne des rôles serait vide.
    """
    lignes = (db.session.query(TimeRoleAnalysis.periode)
              .filter(TimeRoleAnalysis.periode.isnot(None))
              .distinct().all())
    return sorted({p[0] for p in lignes if p[0]}, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════
#  Peser
# ═══════════════════════════════════════════════════════════════════════════

def _mesures(periode, durees, entites, noms_entites, params):
    """Une mesure par (rôle, carto) pour cette période.

    ⚠️ La PLUS RÉCENTE quand il y en a plusieurs pour le même couple : deux
    analyses du même rôle sur la même carto et le même mois sont deux
    tentatives, pas deux charges — les additionner compterait le travail deux
    fois.
    """
    from Code.routes.time_view import _role_summary

    retenues = {}
    # ⚠️ Les LIGNES en bloc : `R.lines` est une relation paresseuse, donc une
    # requête par analyse — mesuré, le coût grandissait de 12 à 16 requêtes
    # pour quatre analyses de plus. C'est exactement le défaut que ce module
    # est fait d'éviter.
    for R in (TimeRoleAnalysis.query
              .options(selectinload(TimeRoleAnalysis.lines))
              .filter(TimeRoleAnalysis.periode == periode)
              .order_by(TimeRoleAnalysis.id.asc()).all()):
        if not R.role_id or not R.lines:
            continue
        cle = (R.role_id, _entite_de(R, entites))
        retenues[cle] = R

    out = {}
    for (role_id, entite_id), R in retenues.items():
        resume = _role_summary(R, params=params, durees=durees)
        out.setdefault(role_id, []).append({
            "analyse_id": R.id,
            "nom": (getattr(R, "name", None) or "").strip(),
            "entite_id": entite_id,
            "entite": noms_entites.get(entite_id) or "",
            "periode": R.periode,
            "n_activites": len(R.lines),
            "annuel_min": resume["annual_minutes"],
        })
    # Dans chaque rôle, la carto la plus lourde d'abord : c'est l'ordre dans
    # lequel on compare « qui performe ».
    for v in out.values():
        v.sort(key=lambda m: -m["annuel_min"])
    return out


def _derniers_mois():
    """Le dernier mois où chaque rôle a été mesuré — même hors période.

    Sans lui, « non mesuré » ne distingue pas un rôle qu'on n'a jamais pesé
    d'un rôle pesé le mois dernier, et les deux ne demandent pas le même
    geste.
    """
    out = {}
    for rid, per in (db.session.query(TimeRoleAnalysis.role_id,
                                      TimeRoleAnalysis.periode)
                     .filter(TimeRoleAnalysis.periode.isnot(None)).all()):
        if rid and (rid not in out or per > out[rid]):
            out[rid] = per
    return out


def charge(periode=None):
    """Le poids de chaque rôle et de chaque personne, pour un mois.

    Rend aussi les périodes disponibles, le plafond, et le calendrier qui a
    servi — l'écran doit pouvoir dire d'où viennent ses chiffres.
    """
    from Code.role_i18n import nom_affiche
    from Code.routes.time_view import get_calendar_params, heures_plein_temps

    params = get_calendar_params()
    plein_min = heures_plein_temps(params) * 60.0
    plafond_min = plein_min * PART_PLAFOND

    periodes = periodes_disponibles()
    if periode not in periodes:
        periode = periodes[0] if periodes else None

    durees, entites, noms_entites = _decor()
    par_role = _mesures(periode, durees, entites, noms_entites, params) if periode else {}
    derniers = _derniers_mois()

    roles = Role.query.all()
    # ⚠️ UNE seule lecture de `user_roles`, pour les deux index : la lire deux
    # fois, c'est une requête de plus pour la même chose.
    liens = UserRole.query.all()
    titulaires, roles_de = {}, {}
    for ur in liens:
        titulaires.setdefault(ur.role_id, []).append(ur.user_id)
        roles_de.setdefault(ur.user_id, []).append(ur.role_id)
    comptes = {u.id: u for u in User.query.order_by(User.last_name, User.first_name).all()}

    def _nom(u):
        return ("%s %s" % (u.first_name or "", u.last_name or "")).strip() or u.email

    # ── Les rôles ────────────────────────────────────────────────────────
    roles_json = []
    poids_role = {}
    for r in roles:
        mes = par_role.get(r.id) or []
        total = sum(m["annuel_min"] for m in mes)
        poids_role[r.id] = total if mes else None
        roles_json.append({
            "id": r.id,
            "nom": nom_affiche(r),
            "mesure": bool(mes),
            "annuel_min": total if mes else None,
            # La part d'un temps plein : c'est elle qui se lit, pas les minutes.
            "part": (total / plein_min) if (mes and plein_min) else None,
            "mesures": mes,
            "derniere_periode": derniers.get(r.id),
            "titulaires": [{"id": i, "nom": _nom(comptes[i])}
                           for i in titulaires.get(r.id, []) if i in comptes],
        })
    # Le plus lourd d'abord ; les non mesurés en fin de liste — un rôle sans
    # mesure n'a pas de rang dans un classement de poids.
    roles_json.sort(key=lambda x: (x["annuel_min"] is None,
                                   -(x["annuel_min"] or 0), x["nom"].lower()))

    # ── Les personnes ────────────────────────────────────────────────────
    noms_roles = {r["id"]: r["nom"] for r in roles_json}

    personnes = []
    for u in comptes.values():
        siens = []
        total, sans = 0.0, 0
        for rid in roles_de.get(u.id, []):
            if rid not in noms_roles:
                continue
            p = poids_role.get(rid)
            if p is None:
                sans += 1
            else:
                total += p
            siens.append({"id": rid, "nom": noms_roles[rid], "annuel_min": p})
        siens.sort(key=lambda x: (x["annuel_min"] is None, -(x["annuel_min"] or 0)))
        personnes.append({
            "id": u.id,
            "nom": _nom(u),
            "email": u.email,
            "n_roles": len(siens),
            # ⚠️ NUL quand AUCUN de ses rôles n'est mesuré : zéro se lirait
            # « cette personne n'a rien à faire ».
            "annuel_min": total if (siens and sans < len(siens)) else None,
            "part_plafond": (total / plafond_min) if (plafond_min and siens and sans < len(siens)) else None,
            "sans_mesure": sans,
            "roles": siens,
        })
    personnes.sort(key=lambda x: (x["annuel_min"] is None,
                                  -(x["annuel_min"] or 0), x["nom"].lower()))

    entite_calendrier = None
    try:
        eid = Entity.get_active_id()
        entite_calendrier = noms_entites.get(eid)
    except Exception:
        pass

    return {
        "ok": True,
        "periode": periode,
        "periodes": periodes,
        "calendrier": params,
        "entite_calendrier": entite_calendrier,
        "plein_temps_min": plein_min,
        "plafond_min": plafond_min,
        "part_plafond": PART_PLAFOND,
        "roles": roles_json,
        "personnes": personnes,
    }


def verdict_ajout(charge_payload, user_id, role_id):
    """Ce que l'ajout d'un rôle ferait à la charge d'une personne.

    ⚠️ Le MÊME calcul que l'écran affiche, servi depuis la même source : le
    navigateur n'a pas à le refaire, et deux implémentations d'un même
    verdict finissent par diverger (c'est la leçon de `dashboard_rows`).
    """
    plafond = charge_payload.get("plafond_min") or 0
    gens = {p["id"]: p for p in charge_payload.get("personnes", [])}
    roles = {r["id"]: r for r in charge_payload.get("roles", [])}
    moi, role = gens.get(user_id), roles.get(role_id)
    if not moi or not role or not plafond:
        return None
    ajout = role.get("annuel_min")
    if ajout is None:
        return None          # un rôle non mesuré n'ajoute rien de connu
    avant = moi.get("annuel_min") or 0.0
    apres = avant + ajout
    return {
        "avant_min": avant, "ajout_min": ajout, "apres_min": apres,
        "plafond_min": plafond,
        "part_avant": avant / plafond, "part_apres": apres / plafond,
        "depasse": apres > plafond,
        "deja": avant > plafond,
    }
