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
    Entity, EntityRoleAccess, EntityStatusAccess, Role, UserRole,
)
from Code.permissions import (PALIERS, can_edit_carto, can_propose_carto,
                              can_review_carto, current_user, famille_statut,
                              is_admin, is_coordinator)

#: Les paliers qui ouvrent une carto commune tant que personne n'a réglé.
STATUTS_DEFAUT = ("coordinateur", "admin")

#: ⚠️ Le palier qu'on ne retire pas. Décocher l'administrateur sur une carto
#: qu'il ne possède pas la lui ferait disparaître de la fenêtre d'accès —
#: donc plus aucun écran d'où la lui rendre.
STATUT_VERROU = "admin"


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


def entity_statuts(entity):
    """Les paliers qui ouvrent cette carto."""
    if entity is None:
        return set()
    if not getattr(entity, "statuts_regles", False):
        return set(STATUTS_DEFAUT)
    ouverts = {l.statut for l in
               EntityStatusAccess.query.filter_by(entity_id=entity.id).all()}
    ouverts.add(STATUT_VERROU)
    return ouverts


def set_statut(entity, statut, ouvert):
    """Ouvre ou ferme une carto à un palier. Ne commit pas."""
    if statut not in PALIERS:
        return False
    if statut == STATUT_VERROU and not ouvert:
        return False
    if not getattr(entity, "statuts_regles", False):
        # Premier réglage : on écrit d'abord ce qui valait par défaut, sinon
        # décocher un palier en rouvrirait un autre.
        for p in STATUTS_DEFAUT:
            if EntityStatusAccess.query.filter_by(entity_id=entity.id, statut=p).first() is None:
                db.session.add(EntityStatusAccess(entity_id=entity.id, statut=p))
        entity.statuts_regles = True
    ligne = EntityStatusAccess.query.filter_by(entity_id=entity.id, statut=statut).first()
    if ouvert and ligne is None:
        db.session.add(EntityStatusAccess(entity_id=entity.id, statut=statut))
    elif not ouvert and ligne is not None:
        db.session.delete(ligne)
    return True


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
    # Le palier du compte ouvre la carto quand il y est autorisé — par défaut
    # le coordinateur et l'administrateur, qui règlent les accès et arbitrent
    # les propositions.
    if famille_statut(user.status) in entity_statuts(entity):
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

    Sur une carto commune, seuls coordinateurs et administrateurs écrivent sans
    passer par un examen ; les champions déposent une proposition, et un `user`
    ne fait ni l'un ni l'autre.
    """
    if entity is None:
        return False
    user = user if user is not None else current_user()
    if user is None:
        return False
    if not entity.is_shared:
        return entity.owner_id in (None, user.id)
    # ⚠️ Le tableau des droits (page Comptes) porte une ligne « enregistrer
    # directement » : c'est elle qui décide, sinon la cocher ne produirait
    # rien. Son défaut est exactement l'ancienne règle (coordinateur et
    # administrateur, qui ouvrent toutes les cartos communes).
    return bool(can_edit_carto(user) and can_read(entity, user))


def can_propose(entity, user=None):
    """Le compte peut-il DÉPOSER une proposition sur cette carto ?

    ⚠️ Lire ne donne plus le droit de proposer : c'est précisément ce qui
    sépare `user` de `champion`. Un `user` consulte la carto et rien d'autre.
    """
    if not can_read(entity, user):
        return False
    if can_edit(entity, user):
        return False          # il enregistre directement, il n'a rien à proposer
    return bool(can_propose_carto(user if user is not None else current_user()))


def must_propose(entity, user=None):
    """Vrai quand le compte a accès en lecture mais doit faire valider.

    Conservé sous ce nom : l'éditeur s'en sert pour basculer son bouton
    « Sauvegarder » en « Proposer la modification ».
    """
    return can_propose(entity, user)


def est_lecture_seule(entity, user=None):
    """Vrai quand le compte ne peut NI enregistrer NI proposer.

    C'est l'état d'un `user` : l'éditeur doit alors s'ouvrir sans ses outils,
    pas seulement refuser au moment d'enregistrer.
    """
    return bool(can_read(entity, user)
                and not can_edit(entity, user)
                and not can_propose(entity, user))


def can_review(entity=None, user=None):
    """Le compte valide-t-il les propositions ? Coordinateur et administrateur
    par défaut, selon le tableau des droits (ligne « valider »).

    Sans `entity`, la question est « valide-t-il en général ? » — celle que
    pose la page Carte avant d'afficher son bandeau. Avec une entité, il faut
    en plus qu'elle soit commune ET qu'il puisse l'ouvrir : un champion à qui
    l'on confierait l'examen ne doit pas trancher sur une carto qu'il ne voit
    pas.
    """
    user = user if user is not None else current_user()
    if user is None:
        return False
    if not can_review_carto(user):
        return False
    if entity is None:
        return True
    return bool(entity.is_shared and can_read(entity, user))


def can_manage_access(entity=None, user=None):
    """Le compte règle-t-il qui accède à une carto ?

    Coordinateurs et administrateurs par défaut — un compte ordinaire ne décide
    pas de qui voit la cartographie de l'organisation, même s'il en est le
    propriétaire : rendre sa carto commune, c'est engager tout le monde.

    ⚠️ Passe par le tableau des droits (page RH, section 4) : une entreprise
    peut ouvrir ce réglage au champion. Le défaut reproduit exactement ce qui
    précédait, donc rien ne bouge sans décision explicite.
    """
    from Code.permissions import a_le_droit
    user = user if user is not None else current_user()
    if user is None:
        return False
    return a_le_droit("manage_acces", user)


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
        for r in Role.query.order_by(Role.name).all():
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
        "statuts": sorted(entity_statuts(entity)) if entity is not None else [],
        "can_edit": can_edit(entity, user),
        "must_propose": must_propose(entity, user),
        # ⚠️ Ni enregistrer ni proposer : l'éditeur doit alors s'ouvrir SANS ses
        # outils. Refuser seulement au moment d'enregistrer laisserait un `user`
        # travailler dix minutes avant d'apprendre qu'il n'en a pas le droit.
        "lecture_seule": est_lecture_seule(entity, user),
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
                Role.id.in_(list(role_ids) or [-1])).all()
        }
        for rid in sorted(valides):
            db.session.add(EntityRoleAccess(entity_id=entity.id, role_id=rid))
