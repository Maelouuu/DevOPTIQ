# -*- coding: utf-8 -*-
"""LE PALIER DE SOUMISSION : une carto ne part à l'examen que COMPLÈTE.

« Sur une carto de cent activités, si on dépose une demande dès qu'on met un
truc, on va faire des centaines de demandes pour remplir la carto. » Le
reproche porte sur le coordinateur : c'est lui qui arbitre, et un arbitre noyé
n'arbitre plus. Une première version se soumet donc d'un bloc.

**La règle** : chaque activité de la carto porte un GARANT, au moins une
TÂCHE et au moins un OUTIL. Sans exception — c'est ce qui rend le palier
lisible : il ne se négocie pas activité par activité.

⚠️ **« Chaque activité » veut dire chaque activité que la carto TIENT.** Deux
sortes de lignes d'`activities` ne sont pas du travail d'ici, et les exiger
rendrait le palier inatteignable — donc inutile :

  · un **RÉSULTAT** (`is_result`, la forme « Résultat » de la carte) est une
    SORTIE, pas un travail : il n'a ni garant, ni tâche, ni outil par nature ;
  · une activité **`external` / `extco`** appartient à une AUTRE carto. La
    règle n'est pas inventée ici : `activities_map` écarte déjà ces deux
    sous-types quand il cherche « la vraie activité » (`shape_subtype.notin_
    (['external', 'extco'])`). Deux définitions du périmètre finiraient par
    donner deux comptes.

  ℹ️ Un RENVOI, lui, n'a même pas de ligne : `_sync_carto_to_db` ne crée
  d'activité que pour les formes de `_ACTIVITY_TYPES`.

⚠️ **Le palier se libère TOUT SEUL.** Une fois la carto complète il ne gêne
plus : corriger une seule tâche passe le contrôle, puisque le contrôle est
« la carto est complète ». Il n'y a donc PAS de « première version » à
marquer, ni de drapeau à tenir — ce serait un état de plus dont on pourrait
se tromper, et qui resterait faux une fois mal posé.

⚠️⚠️ **Ce qui est mesuré, c'est la carto PLUS LE BROUILLON.** Sur une carto
commune, tout ce que le champion écrit est détourné dans son brouillon
(`ecriture.porte` → 202) et n'atteint jamais la base. Mesuré sur la base
seule, le palier annoncerait « 0 activité complète » quel que soit le travail
fourni, et ne se franchirait jamais. On SIMULE donc le brouillon —
`propositions_activite.simuler` rejoue les vraies routes puis annule.

⚠️ Le coût ne grandit pas avec la carto : quatre requêtes, aucune liste d'ids
en paramètre (une carto du pilote porte 601 activités). La simulation, elle,
coûte un rejeu — c'est pourquoi elle n'est PAS calculée au rendu de chaque
page, mais à la demande : quand on ouvre la fenêtre, et à l'envoi.
"""
from Code.extensions import db

# Au-delà, « et n autres » : on ouvre une liste de travail, pas un rapport.
# ⚠️ 15 était trop court : sur une carto d'une quarantaine d'activités dont
# un tiers est rempli, on en nommait 15 sur 26 — la liste disait « et 11
# autres » sans dire lesquelles, et on ne pouvait pas finir le travail
# depuis l'écran. Elle défile désormais dans sa propre boîte, et chaque nom
# ouvre son activité : 60 est la taille d'un plan de travail, pas d'un
# rapport. La borne reste, elle : une carto du pilote porte 601 activités.
NOMMEES = 60

# L'ordre est celui dans lequel on les annonce — et celui dans lequel on les
# remplit : désigner le garant, écrire les tâches, puis outiller les tâches.
EXIGENCES = ("garant", "tache", "outil")

# Les sous-types qui désignent une activité d'une AUTRE carto.
HORS_CARTO = ("external", "extco")


def _perimetre(entity):
    """Les activités que la carto TIENT : [(id, nom)], triées par nom.

    ⚠️ Le tri vit ICI et nulle part ailleurs : `manques` rend un dict, dont
    l'ordre d'insertion est celui-ci, et l'écran le reprend tel quel. Un tri
    « le plus incomplet d'abord » ferait sauter la liste à chaque tâche
    ajoutée ; on parcourt une liste stable, comme celle de la page Activités.
    """
    from Code.models.models import Activities
    if entity is None:
        return []
    q = (Activities.query
         .filter(Activities.entity_id == entity.id,
                 db.or_(Activities.is_result.is_(False),
                        Activities.is_result.is_(None)),
                 db.or_(Activities.shape_subtype.is_(None),
                        Activities.shape_subtype.notin_(HORS_CARTO)))
         .order_by(Activities.name.asc(), Activities.id.asc()))
    return [(a.id, a.name) for a in q.all()]


def manques(entity):
    """{activity_id: (nom, [codes manquants])} — lu EN BASE, en 4 requêtes.

    ⚠️ Les requêtes sont cadrées par un JOIN sur l'entité, jamais par un
    `IN (…)` d'identifiants : une carto du pilote en porte six cents, et le
    coût d'une liste de paramètres grandit avec elle (sans compter la borne
    de SQLite).
    """
    from Code.models.models import Activities, Task, activity_roles, task_tools
    perim = _perimetre(entity)
    if not perim:
        return {}

    # ⚠️ `LOWER(status)` : l'import carto a longtemps écrit « garant » en
    # minuscule et la page Rôles cherchait « Garant » — un rôle garant
    # d'après la carte n'apparaissait alors NULLE PART. Les lectures
    # comparent en minuscules depuis.
    garants = {r[0] for r in db.session.query(activity_roles.c.activity_id)
               .join(Activities, Activities.id == activity_roles.c.activity_id)
               .filter(Activities.entity_id == entity.id,
                       db.func.lower(activity_roles.c.status) == 'garant')}

    taches = {r[0] for r in db.session.query(Task.activity_id)
              .join(Activities, Activities.id == Task.activity_id)
              .filter(Activities.entity_id == entity.id).distinct()}

    # ⚠️ Un outil n'appartient PAS à une activité : c'est le catalogue de la
    # carto, et il se rattache à une TÂCHE (`task_tools`). « Au moins un
    # outil » veut donc dire : au moins une tâche de cette activité est
    # outillée. Une activité sans tâche n'a aucun outil, par construction.
    outils = {r[0] for r in db.session.query(Task.activity_id)
              .join(Activities, Activities.id == Task.activity_id)
              .join(task_tools, task_tools.c.task_id == Task.id)
              .filter(Activities.entity_id == entity.id).distinct()}

    out = {}
    for aid, nom in perim:
        absent = []
        if aid not in garants:
            absent.append("garant")
        if aid not in taches:
            absent.append("tache")
        if aid not in outils:
            absent.append("outil")
        out[aid] = (nom, absent)
    return out


def _rendre(m):
    """Le socle, tel que l'écran le lit."""
    incompletes = [(aid, nom, absent) for aid, (nom, absent) in m.items() if absent]
    total = len(m)
    return {
        "total": total,
        "pretes": total - len(incompletes),
        "complet": not incompletes,
        "manque": {code: sum(1 for _, _, a in incompletes if code in a)
                   for code in EXIGENCES},
        "activites": [{"id": aid, "nom": nom, "manque": absent}
                      for aid, nom, absent in incompletes[:NOMMEES]],
        "reste": max(0, len(incompletes) - NOMMEES),
        "rejeu": None,
    }


def etat(user, entity):
    """Le socle tel qu'il SERA si le brouillon du compte s'applique.

    ⚠️ Un geste qui ne s'applique plus (une tâche supprimée entre-temps, par
    exemple) ne se mesure pas : on le DIT (`rejeu`) et le socle est déclaré
    incomplet. Mesurer « ce que les gestes d'avant donnent » laisserait croire
    à un envoi possible que `rejouer` refuserait de toute façon.
    """
    from Code.propositions_activite import (EchecDeRejeu, brouillon, gestes,
                                            simuler)
    cr = brouillon(user, entity) if (user is not None and entity is not None) else None
    if cr is None or not gestes(cr):
        return _rendre(manques(entity))
    try:
        return simuler(cr, lambda: _rendre(manques(entity)))
    except EchecDeRejeu as exc:
        et = _rendre(manques(entity))
        et["complet"] = False
        et["rejeu"] = {"rang": exc.rang + 1, "raison": str(exc.raison or "")}
        return et
