# -*- coding: utf-8 -*-
"""LE SOCLE : le premier remplissage d'une carto, et le palier qui le clôt.

Une carto neuve n'apporte que son diagramme : des activités, et ce qui entre
et sort de chacune. Tout le reste — le garant, les tâches, les outils, les
compétences — reste à écrire, et c'est des centaines d'écritures. Sur une
carto COMMUNE, chacune partirait en demande au coordinateur : « sur une carto
de cent activités, on va faire des centaines de demandes pour la remplir ».
Un arbitre noyé n'arbitre plus.

**Deux régimes, et c'est `Entity.socle_etat` qui dit lequel s'applique.**

  'saisie'   le remplissage est ouvert. Qui peut PROPOSER écrit DIRECTEMENT
             (`carto_access.can_fill`), sans demande et sans brouillon : la
             saisie est standard, elle se voit dans les listes de la page
             Activités comme n'importe quelle donnée. Rien n'est officiel
             pour autant, et la page le dit — une fois, en tête, pas sur
             chaque champ.
  'soumis'   un champion a déclaré le remplissage fini. Plus personne ne le
             touche : le coordinateur examine un état FIXE.
  'valide'   le coordinateur a validé, et cela vaut pour tous ceux qui
             ouvrent la carto. On repasse au régime normal : une
             modification, une demande (`Code/propositions_activite.py`).

**LE PALIER** — ce qu'il faut pour soumettre : chaque activité de la carto
porte un GARANT, au moins une TÂCHE et au moins un OUTIL. Sans exception —
c'est ce qui le rend lisible : il ne se négocie pas activité par activité.

⚠️ **« Chaque activité » veut dire chaque activité que la carto TIENT.** Deux
sortes de lignes d'`activities` ne sont pas du travail d'ici, et les exiger
rendrait le palier inatteignable — donc inutile :

  · un **RÉSULTAT** (`is_result`, la forme « Résultat » de la carte) est une
    SORTIE, pas un travail : il n'a ni garant, ni tâche, ni outil par nature ;
  · une activité **`external` / `extco`** appartient à une AUTRE carto. La
    règle n'est pas inventée ici : `activities_map` écarte déjà ces deux
    sous-types quand il cherche « la vraie activité ». Deux définitions du
    périmètre finiraient par donner deux comptes.

  ℹ️ Un RENVOI, lui, n'a même pas de ligne : `_sync_carto_to_db` ne crée
  d'activité que pour les formes de `_ACTIVITY_TYPES`.

⚠️ **Le palier se mesure EN BASE, et c'est ce qui le rend simple.** Il a
d'abord vécu avec un brouillon : la saisie du champion était détournée
(`ecriture.porte` → 202) et n'atteignait jamais la base, donc le palier
devait SIMULER le brouillon — rejouer les vraies routes puis annuler — pour
ne pas annoncer « 0 activité complète » quel que soit le travail fourni. La
saisie étant désormais directe pendant la phase 'saisie', il n'y a plus rien
à simuler : quatre requêtes, aucune liste d'identifiants en paramètre (une
carto du pilote porte 601 activités). Assez peu cher pour que la page
Activités l'affiche à chaque rendu.
"""
from datetime import datetime

from Code.extensions import db

ETAT_SAISIE = "saisie"
ETAT_SOUMIS = "soumis"
ETAT_VALIDE = "valide"
ETATS = (ETAT_SAISIE, ETAT_SOUMIS, ETAT_VALIDE)

# ⚠️ Le marqueur vit en BASE, pas en mémoire : une instance qui redémarre, se
# duplique ou se redéploie doit lire la même réponse.
CLE_REPRISE = "socle_cartos_existantes"

# Au-delà, « et n autres » : on ouvre une liste de travail, pas un rapport.
# ⚠️ 15 était trop court : sur une carto d'une quarantaine d'activités dont
# un tiers est rempli, on en nommait 15 sur 26 — la liste disait « et 11
# autres » sans dire lesquelles, et on ne pouvait pas finir le travail depuis
# l'écran. 60 est la taille d'un plan de travail ; la borne reste, elle, une
# carto du pilote porte 601 activités.
NOMMEES = 60

# L'ordre est celui dans lequel on les annonce — et celui dans lequel on les
# remplit : désigner le garant, écrire les tâches, puis outiller les tâches.
EXIGENCES = ("garant", "tache", "outil")

# Les sous-types qui désignent une activité d'une AUTRE carto.
HORS_CARTO = ("external", "extco")


# ── Le périmètre et le palier ─────────────────────────────────────────────

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


def palier(entity):
    """Où en est le remplissage, tel que l'écran le lit."""
    m = manques(entity)
    incompletes = [(aid, nom, absent) for aid, (nom, absent) in m.items() if absent]
    total = len(m)
    return {
        "total": total,
        "pretes": total - len(incompletes),
        # ⚠️ Une carto SANS activité n'est pas complète : elle n'a rien à
        # soumettre. Sans ce cas, une carto vide passerait le palier et le
        # coordinateur validerait du néant.
        "complet": bool(total) and not incompletes,
        "manque": {code: sum(1 for _, _, a in incompletes if code in a)
                   for code in EXIGENCES},
        "activites": [{"id": aid, "nom": nom, "manque": absent}
                      for aid, nom, absent in incompletes[:NOMMEES]],
        "reste": max(0, len(incompletes) - NOMMEES),
    }


# ── L'état du socle ───────────────────────────────────────────────────────

def etat_brut(entity):
    """La valeur de la colonne, défaut compris. Jamais None."""
    if entity is None:
        return ETAT_VALIDE
    valeur = getattr(entity, "socle_etat", None)
    return valeur if valeur in ETATS else ETAT_SAISIE


def en_saisie(entity):
    """La carto est-elle en cours de premier remplissage ?

    ⚠️ Seulement si elle est COMMUNE. Sur une carto privée, son propriétaire
    écrit de toute façon et personne n'a rien à valider : le socle n'y veut
    rien dire, et le faire parler ouvrirait un panneau devant quelqu'un qui
    n'a personne à qui soumettre.
    """
    return bool(entity is not None and entity.is_shared
                and etat_brut(entity) == ETAT_SAISIE)


def en_examen(entity):
    """Le socle est soumis : plus personne ne touche aux données."""
    return bool(entity is not None and entity.is_shared
                and etat_brut(entity) == ETAT_SOUMIS)


def _nom(user):
    if user is None:
        return ""
    plein = ("%s %s" % (user.first_name or "", user.last_name or "")).strip()
    return plein or (user.email or "")


def etat(entity, user=None):
    """Tout ce que le panneau de la page Activités lit, en une lecture.

    ⚠️ `actif` est le seul drapeau que le gabarit regarde : une carto privée,
    ou une carto dont le socle est validé, n'a pas de panneau — et ne paie
    donc pas les quatre requêtes du palier.
    """
    from Code.carto_access import can_fill, can_review
    from Code.models.models import User
    etat_courant = etat_brut(entity)
    commune = bool(entity is not None and entity.is_shared)
    actif = bool(commune and etat_courant != ETAT_VALIDE)
    out = {
        "etat": etat_courant,
        "commune": commune,
        "actif": actif,
        "entity_id": entity.id if entity is not None else None,
        "carto": entity.name if entity is not None else "",
        "par": "",
        "le": None,
        "message": "",
        "retour": getattr(entity, "socle_retour", None) or "" if entity is not None else "",
        "je_remplis": False,
        "je_valide": False,
        "palier": None,
    }
    if not actif:
        return out

    out["je_remplis"] = bool(can_fill(entity, user))
    out["je_valide"] = bool(can_review(entity, user))
    out["message"] = getattr(entity, "socle_message", None) or ""
    quand = getattr(entity, "socle_le", None)
    out["le"] = quand.isoformat() if quand else None
    auteur = (db.session.get(User, entity.socle_par_id)
              if getattr(entity, "socle_par_id", None) else None)
    out["par"] = _nom(auteur)
    out["palier"] = palier(entity)
    return out


# ── Les trois transitions ─────────────────────────────────────────────────

def soumettre(entity, user, message=None):
    """Le champion déclare le remplissage fini. Rend (ok, code).

    ⚠️ LE PALIER est appliqué ICI, pas seulement par le bouton de l'écran :
    une carto à moitié remplie soumise à l'examen est précisément ce qui noie
    le coordinateur, et un bouton éteint n'est pas une sécurité.
    """
    if entity is None or not entity.is_shared:
        return False, "pas_commune"
    if etat_brut(entity) != ETAT_SAISIE:
        return False, "deja_soumis"
    if not palier(entity)["complet"]:
        return False, "palier"
    entity.socle_etat = ETAT_SOUMIS
    entity.socle_par_id = user.id if user is not None else None
    entity.socle_le = datetime.utcnow()
    entity.socle_message = (message or "").strip() or None
    # Une nouvelle soumission efface le retour de la précédente : le mot du
    # coordinateur portait sur un état qu'on vient de corriger.
    entity.socle_retour = None
    db.session.commit()
    return True, None


def valider(entity, user, retour=None):
    """Le coordinateur valide : le socle devient officiel pour tout le monde.

    ⚠️ Accepté depuis 'saisie' AUSSI, et c'est voulu : un coordinateur qui
    remplit sa propre carto n'a personne à qui soumettre, et attendre une
    soumission qui ne viendra jamais le laisserait coincé en saisie. Le palier
    reste exigé — ce qui devient officiel doit être complet.
    """
    if entity is None or not entity.is_shared:
        return False, "pas_commune"
    if etat_brut(entity) == ETAT_VALIDE:
        return False, "deja_valide"
    if not palier(entity)["complet"]:
        return False, "palier"
    entity.socle_etat = ETAT_VALIDE
    entity.socle_le = datetime.utcnow()
    entity.socle_retour = (retour or "").strip() or None
    db.session.commit()
    return True, None


def renvoyer(entity, user, retour=None):
    """Le coordinateur rend la main : on repart en saisie, avec son mot.

    ⚠️ Le mot du coordinateur est ce qui rend le refus utile — sans lui, le
    champion ne sait pas ce qu'il doit reprendre. Il est donc EXIGÉ.
    """
    if entity is None or not entity.is_shared:
        return False, "pas_commune"
    if etat_brut(entity) != ETAT_SOUMIS:
        return False, "pas_soumis"
    mot = (retour or "").strip()
    if not mot:
        return False, "sans_mot"
    entity.socle_etat = ETAT_SAISIE
    entity.socle_le = datetime.utcnow()
    entity.socle_retour = mot
    db.session.commit()
    return True, None


def a_examiner(user):
    """Les cartos dont le socle attend une décision de ce compte.

    Source unique du compteur et de la liste, comme pour les propositions :
    le chiffre annoncé et ce qui s'ouvre ne peuvent pas diverger.
    """
    from Code.carto_access import can_review
    from Code.models.models import Entity
    if user is None or not can_review(None, user):
        return []
    cartos = (Entity.query
              .filter(Entity.is_shared.is_(True),
                      Entity.socle_etat == ETAT_SOUMIS)
              .order_by(Entity.socle_le.asc())
              .all())
    return [e for e in cartos if can_review(e, user)]


# ── La reprise, une fois ──────────────────────────────────────────────────

def reprendre_cartos_existantes(force=False):
    """Les cartos DÉJÀ en base passent à 'valide'. Rend le nombre repris.

    ⚠️⚠️ Sans elle, cette livraison ouvrirait l'écriture DIRECTE à tout
    champion sur des données déjà officielles : le défaut de la colonne est
    'saisie', et toutes les lignes existantes l'héritent. C'est un recul du
    contrôle d'accès, pas une nouveauté.

    ⚠️⚠️ Et elle ne se joue QU'UNE FOIS. Rejouée à chaque démarrage, elle
    validerait le socle de chaque carto qu'on est en train de remplir : on
    aurait ouvert la saisie le matin et le redéploiement du soir la
    refermerait. C'est exactement le défaut de `migrer_anciens_champions`,
    qui promouvait tout champion nommé APRÈS la reprise.

    ⚠️ Les cartos PRIVÉES sont reprises aussi. Le socle y dort — leur
    propriétaire écrit de toute façon — mais si l'une devient commune demain,
    elle ne doit pas rouvrir l'écriture directe sur ce qu'elle porte déjà.
    """
    from Code.models.models import AppSetting, Entity
    if not force:
        try:
            if db.session.get(AppSetting, CLE_REPRISE) is not None:
                return 0
        except Exception:
            db.session.rollback()
            return 0

    n = (Entity.query
         .filter(db.or_(Entity.socle_etat.is_(None),
                        Entity.socle_etat != ETAT_VALIDE))
         .update({"socle_etat": ETAT_VALIDE}, synchronize_session=False))
    if db.session.get(AppSetting, CLE_REPRISE) is None:
        db.session.add(AppSetting(key=CLE_REPRISE, value="1"))
    db.session.commit()
    return int(n or 0)
