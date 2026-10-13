# -*- coding: utf-8 -*-
"""Qui note qui, sur la page Compétences — source unique.

⚠️ `POST /mastery/evaluate` n'avait **AUCUN contrôle** : n'importe quel compte
connecté pouvait écrire n'importe quel niveau sur n'importe qui, y compris se
décerner un niveau officiel. C'était sans grande conséquence tant que seuls les
développeurs de compétences ouvraient l'écran ; ça n'en a plus dès que les
collaborateurs y viennent s'auto-évaluer.

Deux notes, deux portées (CDC 3.6) :

- **auto-évaluation** (`eval_number = '0'`) — chacun la pose sur SOI, personne
  d'autre. C'est un repère partagé, jamais un niveau officiel.
- **niveau validé** (`'1'` garant, `'2'` développeur de compétences) — posé par
  le développeur de compétences du collaborateur, ou par un coordinateur ou un
  administrateur. C'est LUI qui fait foi dans les synthèses.

Le masquage dans l'interface n'est pas une sécurité : les routes refusent.
"""
from Code.models.models import User, UserRole
from Code.permissions import NIVEAU_COORDINATEUR, niveau_status

AUTO = "0"
VALIDANTS = ("1", "2")


def _statut_eleve(user):
    """Coordinateur et administrateur arbitrent partout : ce sont eux qui
    règlent l'accès aux cartos communes et qui créent les comptes.

    ⚠️ Cette règle disait « champion ou administrateur ». Depuis les quatre
    paliers, le mot « champion » nomme le palier du DESSOUS — celui qui propose
    sans valider — et l'ancien arbitre s'appelle coordinateur. Restée telle
    quelle, elle donnait à un champion le droit de lire et de NOTER tout le
    monde (jusqu'à se décerner le niveau qui fait foi), et le retirait au
    coordinateur, qui ne voyait plus que ses propres collaborateurs.
    """
    if user is None:
        return False
    return niveau_status(user.status) >= NIVEAU_COORDINATEUR


def encadre(dev_id, collaborateur_id):
    """`dev_id` est-il développeur de compétences de `collaborateur_id` ?

    Deux rattachements coexistent — global (`users.manager_id`) et par rôle
    (`user_roles.manager_id`). En ignorer un ferait dépendre le droit de la
    façon dont l'affectation a été faite.
    """
    if dev_id is None or collaborateur_id is None:
        return False
    u = User.query.get(collaborateur_id)
    if u is not None and u.manager_id == dev_id:
        return True
    return UserRole.query.filter_by(user_id=collaborateur_id, manager_id=dev_id).count() > 0


def encadre_pour_role(dev_id, collaborateur_id, role_id):
    """`dev_id` développe-t-il ce collaborateur SUR CE RÔLE ?

    ⚠️ C'est la question qu'il fallait poser. `encadre()` répond vrai dès
    qu'il existe UN rattachement, quel qu'il soit : un développeur attaché à
    deux rôles sur quatre voyait les quatre — et pouvait les noter.

    Le lien GLOBAL (`users.manager_id`) couvre tous les rôles de la personne,
    présents et à venir ; le lien PAR RÔLE ne couvre que le sien. C'est la
    distinction que `_dissoudre_lien_global` maintient depuis le début côté
    écriture, et qui n'était lue nulle part côté lecture.
    """
    if dev_id is None or collaborateur_id is None or role_id is None:
        return False
    u = User.query.get(collaborateur_id)
    if u is not None and u.manager_id == dev_id:
        return True
    return UserRole.query.filter_by(user_id=collaborateur_id,
                                    role_id=role_id,
                                    manager_id=dev_id).count() > 0


def roles_suivis(acteur, collaborateur_id):
    """Les rôles de ce collaborateur que l'acteur suit — ou `None` pour
    « tous », quand rien ne les restreint.

    `None` et une liste VIDE ne disent pas la même chose : l'un veut dire
    « aucune restriction », l'autre « il n'en suit aucun ». Les confondre
    rouvrirait exactement le défaut qu'on ferme.
    """
    if acteur is None:
        return []
    if acteur.id == collaborateur_id or _statut_eleve(acteur):
        return None
    u = User.query.get(collaborateur_id)
    if u is not None and u.manager_id == acteur.id:
        return None
    return [ur.role_id for ur in UserRole.query.filter_by(
        user_id=collaborateur_id, manager_id=acteur.id).all()]


def peut_noter(acteur, cible_id, evaluateur, role_id=None):
    """L'acteur peut-il écrire cette évaluation ? Renvoie (ok, motif)."""
    if acteur is None:
        return False, "not_logged_in"
    evaluateur = str(evaluateur)
    if evaluateur == AUTO:
        # S'auto-évaluer pour quelqu'un d'autre n'a aucun sens : la note dirait
        # ce que CETTE personne pense d'elle-même.
        return (acteur.id == cible_id), "self_only"
    if evaluateur not in VALIDANTS:
        return False, "unknown_evaluator"
    if _statut_eleve(acteur):
        return True, "ok"
    # ⚠️ Avec un rôle, c'est le rôle qui tranche. Sans rôle on retombe sur la
    # règle par personne — et c'est pour ça que les routes qui ÉCRIVENT
    # exigent le rôle : l'omettre suffirait sinon à contourner le contrôle.
    if role_id is not None:
        if encadre_pour_role(acteur.id, cible_id, role_id):
            return True, "ok"
        return False, "not_the_developer_for_this_role"
    if encadre(acteur.id, cible_id):
        return True, "ok"
    return False, "not_the_developer"


def peut_lire(acteur, cible_id, role_id=None):
    """On lit son propre dossier, celui de ses collaborateurs, et — pour un
    coordinateur ou un administrateur — celui de tout le monde.

    Avec un `role_id`, la lecture est bornée à ce rôle : un développeur de
    deux rôles sur quatre n'ouvre pas les deux autres.
    """
    if acteur is None:
        return False
    if acteur.id == cible_id or _statut_eleve(acteur):
        return True
    if role_id is not None:
        return encadre_pour_role(acteur.id, cible_id, role_id)
    return encadre(acteur.id, cible_id)
