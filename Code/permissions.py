"""Droits transverses : qui est administrateur, qui peut créer des comptes.

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

# Valeur canonique proposée dans les listes déroulantes de la page Comptes.
# C'est « manager » : la valeur retenue par la distribution client, où le libellé
# affiché est déjà « Gestionnaire de compétences » / « Competency manager ».
# Courte à dessein — elle doit tenir dans users.status (VARCHAR(20)).
COMPETENCY_MANAGER_STATUS = "manager"


def norm_status(raw):
    """minuscules, sans accents, séparateurs unifiés."""
    s = unicodedata.normalize("NFD", raw or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[\s_\-]+", " ", s).strip()


def is_admin_status(raw):
    return norm_status(raw) in ADMIN_STATUSES


def is_competency_manager_status(raw):
    """Vrai pour « gestionnaire de compétences » et ses variantes.

    Couvre : la valeur canonique `manager`, le libellé complet écrit à la main,
    sa troncature à 20 caractères (« gestionnaire de comp »), et les
    formulations anglaises (« competency manager », « skills manager »).
    """
    st = norm_status(raw)
    if not st:
        return False
    if st == COMPETENCY_MANAGER_STATUS:
        return True
    if st.startswith("gestionnaire"):
        return True
    if "manager" in st and any(k in st for k in ("competency", "competence", "skill")):
        return True
    return False


def can_create_accounts_status(raw):
    return is_admin_status(raw) or is_competency_manager_status(raw)


def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def is_admin(user=None):
    user = user if user is not None else current_user()
    return bool(user and is_admin_status(user.status))


def can_create_accounts(user=None):
    user = user if user is not None else current_user()
    return bool(user and can_create_accounts_status(user.status))


def can_edit_account(target_user_id, user=None):
    """Hors administrateurs, chacun ne peut modifier QUE son propre compte."""
    user = user if user is not None else current_user()
    if not user:
        return False
    return is_admin(user) or user.id == int(target_user_id)
