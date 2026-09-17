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


# ── Ce que chaque palier ouvre — RÉGLABLE ───────────────────────────────────
#
# L'échelle (`user < champion < coordinateur < admin`) ne bouge pas : c'est la
# grammaire du produit. Ce qui se règle, c'est ce que CHAQUE palier ouvre —
# parce qu'une entreprise n'a pas les mêmes usages qu'une autre. Chez l'une,
# tout le monde propose ; chez l'autre, seul un coordinateur touche à la carto.
#
# ⚠️ **Le tableau par défaut EST le comportement d'hier.** Une instance qui n'a
# jamais rien réglé ne change pas de comportement en prenant ce code : sans
# ligne en base, on rend exactement ces valeurs. C'est la seule façon de livrer
# un réglage sans surprendre les instances en service.
#
# ⚠️ **La colonne `admin` est verrouillée à VRAI et ne se règle pas.** Se
# retirer l'accès aux Paramètres, c'est perdre l'écran depuis lequel on le
# remettrait : la porte se refermerait de l'intérieur, sans poignée. Un
# administrateur peut donc toujours tout rouvrir.

CLE_DROITS = "droits_par_palier"

PALIERS = ("user", "champion", "coordinateur", "admin")

DROITS_DEFAUT = {
    # proposer une modification de carto
    "propose_carto":      {"user": False, "champion": True,  "coordinateur": True},
    # enregistrer directement sur une carto commune
    "edit_carto":         {"user": False, "champion": False, "coordinateur": True},
    # valider ou refuser une proposition
    "review_carto":       {"user": False, "champion": False, "coordinateur": True},
    # régler qui accède à une carto commune
    "manage_acces":       {"user": False, "champion": False, "coordinateur": True},
    # ouvrir la page Gestion RH
    "acces_rh":           {"user": False, "champion": False, "coordinateur": True},
    # créer des comptes depuis la page Comptes
    "cree_comptes":       {"user": False, "champion": False, "coordinateur": True},
    # ⚠️ sections d'administration des Paramètres : clé IA, URL de la base,
    # console serveur. Ouvrir cette porte donne la clé IA de l'entreprise.
    "parametres_admin":   {"user": False, "champion": False, "coordinateur": False},
}


def _reglages_stockes():
    """Ce qui est écrit en base, ou {} — jamais d'exception vers l'appelant.

    ⚠️ **Aucun cache applicatif ici, volontairement.** Une première version
    gardait la valeur dans `flask.g` pour éviter une dizaine de lectures par
    page. C'était un piège : `g` vit aussi longtemps que le CONTEXTE, et un
    contexte peut durer bien plus qu'une requête — la suite de tests en garde
    un ouvert du début à la fin, si bien que le tout premier réglage lu y
    restait figé pour toute la session.

    La lecture n'a pas besoin de ce cache : `db.session.get()` sur une clé
    primaire passe par la carte d'identité de SQLAlchemy, donc un seul aller
    en base par SESSION — c'est-à-dire par requête, exactement la granularité
    qu'on voulait, et sans la garder plus longtemps que la requête.
    """
    from flask import has_app_context
    if not has_app_context():
        return {}
    try:
        from Code.models.models import AppSetting
        row = db.session.get(AppSetting, CLE_DROITS)
        if row and row.value:
            import json
            brut = json.loads(row.value)
            if isinstance(brut, dict):
                return brut
    except Exception:
        # Table absente (base neuve), JSON abîmé : on retombe sur les valeurs
        # par défaut plutôt que de refuser tous les droits — un réglage illisible
        # ne doit pas verrouiller l'application.
        try:
            db.session.rollback()
        except Exception:
            pass
    return {}


def droits_effectifs():
    """Le tableau complet, défauts + réglages, colonne admin verrouillée."""
    stockes = _reglages_stockes()
    table = {}
    for droit, defaut in DROITS_DEFAUT.items():
        ligne = {p: bool(defaut.get(p, False)) for p in PALIERS if p != "admin"}
        pose = stockes.get(droit) or {}
        for palier in list(ligne):
            if palier in pose:
                ligne[palier] = bool(pose[palier])
        ligne["admin"] = True          # verrouillé — voir plus haut
        table[droit] = ligne
    return table


def a_le_droit(droit, user=None):
    """Ce compte a-t-il ce droit, d'après le tableau en vigueur ?"""
    user = user if user is not None else current_user()
    if user is None:
        return False
    if is_admin(user):
        return True
    n = niveau(user)
    palier = ("user" if n <= NIVEAU_USER
              else "champion" if n == NIVEAU_CHAMPION
              else "coordinateur")
    return bool(droits_effectifs().get(droit, {}).get(palier, False))


def enregistrer_droits(table):
    """Écrit le tableau. Ne garde que ce qui DIFFÈRE du défaut.

    ⚠️ Enregistrer la table entière figerait les défauts : le jour où le produit
    change un réglage d'origine, les instances qui n'y avaient jamais touché
    garderaient l'ancien sans le savoir. On ne stocke que les écarts.
    """
    import json
    from Code.models.models import AppSetting

    ecarts = {}
    for droit, defaut in DROITS_DEFAUT.items():
        pose = (table or {}).get(droit) or {}
        ligne = {}
        for palier in PALIERS:
            if palier == "admin":
                continue           # verrouillé : jamais stocké
            if palier in pose and bool(pose[palier]) != bool(defaut.get(palier, False)):
                ligne[palier] = bool(pose[palier])
        if ligne:
            ecarts[droit] = ligne

    row = db.session.get(AppSetting, CLE_DROITS)
    if row is None:
        row = AppSetting(key=CLE_DROITS)
        db.session.add(row)
    row.value = json.dumps(ecarts, ensure_ascii=False)
    db.session.commit()
    return ecarts


# ── Ce que chaque palier ouvre ──────────────────────────────────────────────

def can_propose_carto(user=None):
    """Déposer une proposition de modification. Champion par défaut.

    ⚠️ Un `user` ne propose PAS tant que personne n'a réglé le contraire : c'est
    ce qui distingue les deux premiers paliers, et l'éditeur s'ouvre en lecture
    seule pour lui.
    """
    return a_le_droit("propose_carto", user)


def can_edit_carto(user=None):
    """Enregistrer directement sur une carto commune. Coordinateur par défaut."""
    return a_le_droit("edit_carto", user)


def can_review_carto(user=None):
    """Valider ou refuser une proposition. Coordinateur par défaut."""
    return a_le_droit("review_carto", user)


def can_access_rh(user=None):
    """Ouvrir la page Gestion RH. Coordinateur par défaut."""
    return a_le_droit("acces_rh", user)


def can_see_admin_settings(user=None):
    """Les sections d'administration des Paramètres. Administrateurs par défaut.

    ⚠️ La PAGE Paramètres, elle, reste ouverte à tous : chacun doit pouvoir
    choisir la langue de son interface. Ce droit-ci ne porte que sur les
    sections d'administration — clé IA, URL de la base, console serveur.
    """
    return a_le_droit("parametres_admin", user)


def can_create_accounts_status(raw):
    return niveau_status(raw) >= NIVEAU_COORDINATEUR


def can_create_accounts(user=None):
    return a_le_droit("cree_comptes", user)


def can_edit_account(target_user_id, user=None):
    """Hors administrateurs, chacun ne peut modifier QUE son propre compte."""
    user = user if user is not None else current_user()
    if not user:
        return False
    return is_admin(user) or user.id == int(target_user_id)


# ── Reprise des comptes existants ───────────────────────────────────────────

# Marqueur posé en base une fois la reprise faite. Il vit dans `app_settings`,
# c'est-à-dire DANS la base migrée : une instance qui redémarre, se duplique ou
# se redéploie lit le même marqueur, alors qu'un drapeau en mémoire repartirait
# à zéro à chaque démarrage.
CLE_REPRISE = "statuts_quatre_paliers"


def _reprise_deja_faite():
    from Code.models.models import AppSetting
    try:
        return db.session.get(AppSetting, CLE_REPRISE) is not None
    except Exception:
        # Table absente (base neuve, migration pas encore jouée) : on laissera
        # la reprise s'exécuter, elle ne trouvera rien à reprendre.
        db.session.rollback()
        return False


def _marquer_reprise():
    from Code.models.models import AppSetting
    if db.session.get(AppSetting, CLE_REPRISE) is None:
        db.session.add(AppSetting(key=CLE_REPRISE, value="1"))
    db.session.commit()


def migrer_anciens_champions(force=False):
    """Les arbitres d'hier deviennent « coordinateur ». UNE SEULE FOIS.

    ⚠️ Sans cette reprise, le changement de sens du mot « champion » RETIRERAIT
    des droits à des comptes en service : celui qui validait les propositions se
    retrouverait à ne plus pouvoir que les déposer. On la joue au DÉMARRAGE,
    avant de servir la moindre requête, pour qu'il n'existe aucune fenêtre
    pendant laquelle la base et le code ne disent pas la même chose.

    ⚠️ **Et elle ne doit surtout pas se rejouer.** Elle lit `champion` au sens
    ANCIEN — l'arbitre. Rejouée à chaque démarrage, elle promouvait
    `coordinateur` tout champion créé DEPUIS, c'est-à-dire exactement le palier
    qu'on venait d'introduire : on nommait quelqu'un « champion » pour qu'il
    propose sans valider, et le redéploiement suivant lui donnait le droit de
    valider. Un marqueur en base tranche : après la reprise, le mot ne veut plus
    dire que sa nouvelle définition.

    Renvoie le nombre de comptes repris (0 si la reprise a déjà eu lieu).
    """
    if not force and _reprise_deja_faite():
        return 0
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
    _marquer_reprise()
    return repris
