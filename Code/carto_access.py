"""Qui voit, qui modifie, qui arbitre une cartographie.

Source unique de vérité du partage de carto. Historiquement une entité
n'appartenait qu'à son propriétaire et « partager » voulait dire en déposer une
COPIE chez chacun : chaque compte repartait avec sa version, plus rien ne les
reliait, et une correction devait être refaite autant de fois qu'il y avait de
copies.

Le modèle est désormais :

* une carto **commune** (``Entity.is_shared``) est une SEULE ligne, travaillée
  par plusieurs comptes — ce qui est validé est vu par tout le monde sans rien
  propager ;
* l'accès se donne à des **rôles**, jamais à des comptes : qui reçoit le rôle
  demain accède à la carto sans qu'on y revienne. Aucun rôle coché = ouverte à
  tous les comptes ;
* une carto qu'un compte crée pour lui reste **privée** (``is_shared`` faux) et
  n'obéit à rien de tout ça ;
* trois statuts : ``user`` (propose), ``champion`` (arbitre et règle les accès),
  ``admin`` (tout).
"""
from sqlalchemy import or_

from Code.extensions import db
from Code.models.models import (
    Entity, EntityRoleAccess, Role, UserRole,
)
from Code.permissions import current_user, is_admin, is_champion


# ── Rôles d'un compte ───────────────────────────────────────────────────────

def user_role_ids(user_id):
    """Ids des rôles portés par ce compte, toutes entités confondues."""
    if not user_id:
        return set()
    lignes = UserRole.query.filter_by(user_id=user_id).all()
    return {ur.role_id for ur in lignes}


def entity_role_ids(entity_id):
    """Rôles explicitement autorisés sur cette carto (vide = ouverte à tous)."""
    lignes = EntityRoleAccess.query.filter_by(entity_id=entity_id).all()
    return {a.role_id for a in lignes}


# ── Lecture ─────────────────────────────────────────────────────────────────

def can_read(entity, user=None):
    """Le compte peut-il ouvrir cette carto ?"""
    if entity is None:
        return False
    user = user if user is not None else current_user()
    if user is None:
        return False
    if entity.owner_id in (None, user.id):
        return True
    if not entity.is_shared:
        return False
    # Champions et administrateurs voient toutes les cartos communes : ce sont
    # eux qui en règlent l'accès et qui arbitrent les propositions.
    if is_admin(user) or is_champion(user):
        return True
    autorises = entity_role_ids(entity.id)
    if not autorises:
        return True          # commune sans restriction = tous les comptes
    return bool(autorises & user_role_ids(user.id))


def readable_entities(user=None):
    """Entités que ce compte peut ouvrir, triées par nom.

    Renvoie une LISTE (le filtrage par rôle ne s'exprime pas proprement en SQL
    sur tous les dialectes, et le nombre d'entités par instance est petit).
    """
    user = user if user is not None else current_user()
    if user is None:
        return []
    candidates = (Entity.query
                  .filter(or_(Entity.owner_id == user.id,
                              Entity.owner_id.is_(None),
                              Entity.is_shared.is_(True)))
                  .order_by(Entity.name)
                  .all())
    return [e for e in candidates if can_read(e, user)]


def readable_entity(entity_id, user=None):
    """L'entité si le compte peut l'ouvrir, sinon None."""
    if not entity_id:
        return None
    entity = db.session.get(Entity, int(entity_id))
    return entity if can_read(entity, user) else None


# ── Écriture ────────────────────────────────────────────────────────────────

def can_edit(entity, user=None):
    """Le compte peut-il enregistrer directement sur cette carto ?

    Sur une carto commune, seuls champions et administrateurs écrivent sans
    passer par un examen ; les autres déposent une proposition.
    """
    if entity is None:
        return False
    user = user if user is not None else current_user()
    if user is None:
        return False
    if not entity.is_shared:
        return entity.owner_id in (None, user.id)
    return bool(is_admin(user) or is_champion(user))


def must_propose(entity, user=None):
    """Vrai quand le compte a accès en lecture mais doit faire valider."""
    return bool(can_read(entity, user) and not can_edit(entity, user))


def can_review(entity=None, user=None):
    """Le compte examine-t-il les propositions ? (champion ou administrateur)"""
    user = user if user is not None else current_user()
    if user is None:
        return False
    if entity is not None and not entity.is_shared:
        return False
    return bool(is_admin(user) or is_champion(user))


def can_manage_access(entity=None, user=None):
    """Le compte règle-t-il qui accède à une carto ?

    Réservé aux champions et administrateurs — un compte ordinaire ne décide
    pas de qui voit la cartographie de l'organisation, même s'il en est le
    propriétaire : rendre sa carto commune, c'est engager tout le monde.
    """
    user = user if user is not None else current_user()
    if user is None:
        return False
    return bool(is_admin(user) or is_champion(user))


# ── Description pour les gabarits et les API ────────────────────────────────

def access_summary(entity, user=None):
    """Ce que l'interface a besoin de savoir sur une carto, d'un coup."""
    user = user if user is not None else current_user()
    gere = can_manage_access(entity, user)
    # La liste des rôles ne sert qu'à celui qui règle l'accès. L'éditeur reçoit
    # ce résumé dans sa page : inutile d'y verser vingt rôles pour rien.
    roles = []
    autorises = entity_role_ids(entity.id) if entity is not None else set()
    if entity is not None and gere:
        for r in Role.query.filter_by(entity_id=entity.id).order_by(Role.name).all():
            roles.append({
                "id": r.id,
                "name": r.name,
                "granted": r.id in autorises,
                "holders": UserRole.query.filter_by(role_id=r.id).count(),
            })
    return {
        "entity_id": entity.id if entity else None,
        "entity_name": entity.name if entity else None,
        "is_shared": bool(entity and entity.is_shared),
        "is_owner": bool(entity and user and entity.owner_id == user.id),
        "open_to_all": bool(entity and entity.is_shared and not autorises),
        "can_edit": can_edit(entity, user),
        "must_propose": must_propose(entity, user),
        "can_review": can_review(entity, user),
        "can_manage_access": gere,
        "roles": roles,
    }


def set_access(entity, is_shared, role_ids):
    """Applique l'état de partage. Ne commit pas."""
    entity.is_shared = bool(is_shared)
    EntityRoleAccess.query.filter_by(entity_id=entity.id).delete()
    if entity.is_shared:
        valides = {
            r.id for r in Role.query.filter(
                Role.entity_id == entity.id,
                Role.id.in_(list(role_ids) or [-1])).all()
        }
        for rid in sorted(valides):
            db.session.add(EntityRoleAccess(entity_id=entity.id, role_id=rid))
