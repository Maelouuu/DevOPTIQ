"""Droits transverses : les QUATRE statuts de compte et ce qu'ils permettent.

Une échelle, pas une liste : chaque palier ajoute aux droits du précédent.

    user  <  champion  <  coordinateur  <  admin

| Statut         | Carto                         | Page RH | Paramètres     |
|----------------|-------------------------------|---------|----------------|
| `user`         | **lecture seule**             | non     | langue seule   |
| `champion`     | + **propose** des modifs      | non     | langue seule   |
| `coordinateur` | + **modifie** et **arbitre**  | **oui** | langue seule   |
| `admin`        | tout                          | oui     | **tout**       |

⚠️ **« champion » a CHANGÉ DE SENS.** Jusqu'ici il désignait celui qui arbitre
les propositions et règle l'accès aux cartos — c'est désormais le
**coordinateur**. Le mot « champion » nomme le palier au-dessous, qui propose
sans pouvoir valider. Tous les libellés historiques de l'arbitre (`manager`,
« Gestionnaire de compétences », sa troncature, les variantes anglaises) sont
donc reconnus comme **coordinateur**, et les comptes existants sont renommés au
démarrage (`migrer_anciens_champions`) : personne ne perd ses droits parce que
le mot a bougé.

`User.status` est un texte libre, saisi ou provisionné différemment selon les
instances (accents, casse, tirets, anglais/français) — et la colonne est un
VARCHAR(20), donc un libellé long comme « Gestionnaire de compétences » y arrive
tronqué. On reconnaît donc une FAMILLE de statuts sur une forme normalisée,
plutôt qu'une liste de valeurs exactes.
"""
import re
import unicodedata

from flask import session

from Code.extensions import db
from Code.models.models import User

# 'admin' et 'administrateur' coexistent historiquement en base.
ADMIN_STATUSES = {"admin", "administrateur", "administrator"}

# Valeurs canoniques proposées dans les listes déroulantes de la page Comptes.
# Courtes à dessein — elles doivent tenir dans users.status (VARCHAR(20)).
CHAMPION_STATUS = "champion"
COORDINATOR_STATUS = "coordinateur"

# Nom historique, conservé : il a toujours désigné l'arbitre, c'est-à-dire le
# coordinateur d'aujourd'hui.
COMPETENCY_MANAGER_STATUS = COORDINATOR_STATUS

# Les paliers, du plus restreint au plus étendu.
NIVEAU_USER = 0
NIVEAU_CHAMPION = 1
NIVEAU_COORDINATEUR = 2
NIVEAU_ADMIN = 3


def norm_status(raw):
    """minuscules, sans accents, séparateurs unifiés."""
    s = unicodedata.normalize("NFD", raw or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[\s_\-]+", " ", s).strip()


def is_admin_status(raw):
    return norm_status(raw) in ADMIN_STATUSES


def is_coordinator_status(raw):
    """Vrai pour « coordinateur » et pour tous les libellés de l'ANCIEN arbitre.

    Couvre : `coordinateur` / `coordinator`, l'ancienne valeur `manager`, le
    libellé complet écrit à la main (« Gestionnaire de compétences »), sa
    troncature à 20 caractères (« gestionnaire de comp ») et les formulations
    anglaises (« competency manager », « skills manager »).

    ⚠️ PAS `champion` : ce mot désigne maintenant le palier au-dessous. Les
    comptes qui le portent encore au sens ancien sont renommés au démarrage.
    """
    st = norm_status(raw)
    if not st:
        return False
    if st in (COORDINATOR_STATUS, "coordinator", "manager"):
        return True
    if st.startswith("coordinateur") or st.startswith("coordinator"):
        return True
    if st.startswith("gestionnaire"):
        return True
    if "manager" in st and any(k in st for k in ("competency", "competence", "skill")):
        return True
    return False


def is_champion_status(raw):
    """Vrai pour le palier « champion » — celui qui PROPOSE sans valider."""
    return norm_status(raw) == CHAMPION_STATUS


# Ancien nom, appelé depuis les gabarits : il a toujours désigné l'arbitre,
# c'est-à-dire le coordinateur d'aujourd'hui.
is_competency_manager_status = is_coordinator_status


def niveau_status(raw):
    """Le palier d'un libellé de statut, sur l'échelle user → admin."""
    if is_admin_status(raw):
        return NIVEAU_ADMIN
    if is_coordinator_status(raw):
        return NIVEAU_COORDINATEUR
    if is_champion_status(raw):
        return NIVEAU_CHAMPION
    return NIVEAU_USER


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def niveau(user=None):
    user = user if user is not None else current_user()
    return niveau_status(user.status) if user else -1


# ── Les quatre paliers ──────────────────────────────────────────────────────

def is_admin(user=None):
    return niveau(user) >= NIVEAU_ADMIN


def is_coordinator(user=None):
    """Coordinateur OU administrateur — le palier qui tranche.

    On lit « au moins coordinateur » : un administrateur peut tout ce que peut
    un coordinateur. Les appelants qui veulent EXACTEMENT un coordinateur
    comparent `niveau(user) == NIVEAU_COORDINATEUR`.
    """
    return niveau(user) >= NIVEAU_COORDINATEUR


def is_champion(user=None):
    """Champion OU au-dessus — le palier qui peut au moins proposer."""
    return niveau(user) >= NIVEAU_CHAMPION


# ── Ce que chaque palier ouvre ──────────────────────────────────────────────

def can_propose_carto(user=None):
    """Déposer une proposition de modification. À partir de champion.

    ⚠️ Un `user` ne propose PAS : il consulte. C'est ce qui distingue les deux
    premiers paliers, et l'éditeur doit s'ouvrir en lecture seule pour lui.
    """
    return niveau(user) >= NIVEAU_CHAMPION


def can_edit_carto(user=None):
    """Enregistrer directement sur une carto commune. À partir de coordinateur."""
    return niveau(user) >= NIVEAU_COORDINATEUR


def can_review_carto(user=None):
    """Valider ou refuser une proposition. À partir de coordinateur."""
    return niveau(user) >= NIVEAU_COORDINATEUR


def can_access_rh(user=None):
    """Ouvrir la page Gestion RH. À partir de coordinateur."""
    return niveau(user) >= NIVEAU_COORDINATEUR


def can_see_admin_settings(user=None):
    """Les sections d'administration des Paramètres. Administrateurs seuls.

    ⚠️ La PAGE Paramètres, elle, reste ouverte à tous : chacun doit pouvoir
    choisir la langue de son interface.
    """
    return is_admin(user)


def can_create_accounts_status(raw):
    return niveau_status(raw) >= NIVEAU_COORDINATEUR


def can_create_accounts(user=None):
    return niveau(user) >= NIVEAU_COORDINATEUR


def can_edit_account(target_user_id, user=None):
    """Hors administrateurs, chacun ne peut modifier QUE son propre compte."""
    user = user if user is not None else current_user()
    if not user:
        return False
    return is_admin(user) or user.id == int(target_user_id)


# ── Reprise des comptes existants ───────────────────────────────────────────

def migrer_anciens_champions():
    """Les arbitres d'hier deviennent « coordinateur ».

    ⚠️ Sans cette reprise, le changement de sens du mot « champion » RETIRERAIT
    des droits à des comptes en service : celui qui validait les propositions se
    retrouverait à ne plus pouvoir que les déposer. On la joue au DÉMARRAGE,
    avant de servir la moindre requête, pour qu'il n'existe aucune fenêtre
    pendant laquelle la base et le code ne disent pas la même chose.

    Idempotente : elle ne touche que les libellés de l'ancien arbitre, et
    `coordinateur` n'en fait pas partie. Renvoie le nombre de comptes repris.
    """
    repris = 0
    for u in User.query.all():
        st = norm_status(u.status)
        if not st:
            continue
        # `champion` au sens ANCIEN, plus les libellés historiques.
        ancien_arbitre = st == "champion" or is_coordinator_status(u.status)
        if ancien_arbitre and st != COORDINATOR_STATUS:
            u.status = COORDINATOR_STATUS
            repris += 1
    if repris:
        db.session.commit()
    return repris
