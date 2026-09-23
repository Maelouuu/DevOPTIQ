"""Un rôle appartient à l'ENTREPRISE, pas à une carto.

Historiquement `roles.entity_id` cadrait tout : chaque carto créait ses propres
rôles depuis ses bandes, et « Purchasing » existait autant de fois qu'il y avait
de cartos. Conséquences visibles : la page RH changeait de liste quand on
changeait de carto, un collaborateur devait être rattaché au rôle de CHAQUE
carto, et la matrice des accès affichait le même intitulé plusieurs fois.

Un rôle est désormais **commun**, comme un compte : un seul « Purchasing » pour
toute l'entreprise, relié aux activités de toutes les cartos où sa bande existe.
`entity_id` reste renseigné sur la ligne — c'est la carto qui l'a vu naître —
mais plus rien ne filtre dessus.
"""
import unicodedata

from Code.extensions import db
from Code.models.models import (
    Role, UserRole, activity_roles, task_roles,
)

#: Marqueur en BASE, comme les autres reprises : une instance qui redémarre ou
#: se duplique doit lire la même réponse.
CLE_FUSION = "roles_communs"


def normalise(valeur):
    """Minuscules, sans accents, espaces resserrés."""
    texte = unicodedata.normalize("NFKD", str(valeur or ""))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.lower().split())


def index_par_nom():
    """{nom normalisé: rôle} pour toute l'entreprise."""
    index = {}
    for r in Role.query.order_by(Role.id).all():
        index.setdefault(normalise(r.name), r)
    return index


def role_par_nom(nom, creer=True, entity_id=None, hors_carte=False, index=None):
    """Le rôle de ce nom, quel que soit la carto — créé au besoin.

    `index` évite une requête par appel quand on en cherche cinquante d'affilée
    (synchro d'une carto, import d'un fichier) ; il est tenu à jour.
    """
    nom = (nom or "").strip()
    if not nom:
        return None
    cle = normalise(nom)
    if index is not None:
        role = index.get(cle)
    else:
        role = Role.query.filter(db.func.lower(Role.name) == nom.lower()).first()
        if role is None:
            role = next((r for r in Role.query.all() if normalise(r.name) == cle), None)
    if role is not None:
        if hors_carte and not role.hors_carte:
            role.hors_carte = True
        return role
    if not creer:
        return None
    role = Role(name=nom[:100], entity_id=entity_id, hors_carte=bool(hors_carte))
    db.session.add(role)
    db.session.flush()
    if index is not None:
        index[cle] = role
    return role


def est_utilise(role):
    """Le rôle porte-t-il encore quelque chose : un titulaire, une activité,
    une tâche ?"""
    if role is None or not role.id:
        return False
    if UserRole.query.filter_by(role_id=role.id).count():
        return True
    for table in (activity_roles, task_roles):
        n = db.session.execute(
            db.select(db.func.count()).select_from(table)
            .where(table.c.role_id == role.id)).scalar()
        if n:
            return True
    return False


# ── Reprise : un seul rôle par intitulé ─────────────────────────────────────

def _titulaires(role_id):
    return UserRole.query.filter_by(role_id=role_id).count()


def _fusionner_paire(garde, doublon):
    """Reporte tout ce qui pend au `doublon` sur le rôle `garde`, puis
    l'efface. Les tables à clé unique refusent deux fois la même paire : on
    reporte quand la place est libre, on jette la ligne sinon."""
    from Code.models.models import (
        EntityRoleAccess, PlanFormation, RoleActivityDomainRequirement,
        TimeAnalysis, UserActivityPlan,
    )
    from Code.routes.time_extra import TimeRoleAnalysis

    # 1 · Titulaires (user_id, role_id) — on garde le développeur s'il manque.
    for ur in UserRole.query.filter_by(role_id=doublon.id).all():
        deja = UserRole.query.filter_by(user_id=ur.user_id, role_id=garde.id).first()
        uid, mid = ur.user_id, ur.manager_id
        db.session.delete(ur)
        db.session.flush()
        if deja is None:
            db.session.add(UserRole(user_id=uid, role_id=garde.id, manager_id=mid))
        elif deja.manager_id is None and mid is not None:
            deja.manager_id = mid

    # 2 · Activités et tâches — la paire (objet, rôle) est unique.
    for table, colonne in ((activity_roles, activity_roles.c.activity_id),
                           (task_roles, task_roles.c.task_id)):
        lignes = db.session.execute(
            db.select(table).where(table.c.role_id == doublon.id)).mappings().all()
        for ligne in lignes:
            valeurs = dict(ligne)
            objet = valeurs[colonne.name]
            deja = db.session.execute(
                db.select(colonne).where(db.and_(colonne == objet,
                                                 table.c.role_id == garde.id))).first()
            db.session.execute(table.delete().where(
                db.and_(colonne == objet, table.c.role_id == doublon.id)))
            if deja is None:
                valeurs["role_id"] = garde.id
                db.session.execute(table.insert().values(**valeurs))

    # 3 · Le reste : report simple, sauf contrainte d'unicité.
    for modele, uniques in ((EntityRoleAccess, ("entity_id",)),
                            (PlanFormation, ("user_id",)),
                            (RoleActivityDomainRequirement, ("activity_id", "domain_id"))):
        for ligne in modele.query.filter_by(role_id=doublon.id).all():
            filtre = {c: getattr(ligne, c) for c in uniques}
            filtre["role_id"] = garde.id
            if modele.query.filter_by(**filtre).first() is not None:
                db.session.delete(ligne)
            else:
                ligne.role_id = garde.id
    for modele in (TimeAnalysis, TimeRoleAnalysis, UserActivityPlan):
        modele.query.filter_by(role_id=doublon.id).update(
            {"role_id": garde.id}, synchronize_session=False)

    # 4 · Ce que le doublon savait et que le rôle gardé ignore.
    for champ in ("name_fr", "name_en", "mission_generale", "onboarding_plan"):
        if not getattr(garde, champ, None) and getattr(doublon, champ, None):
            setattr(garde, champ, getattr(doublon, champ))
    if doublon.hors_carte:
        garde.hors_carte = True
    db.session.delete(doublon)
    db.session.flush()


def fusionner_doublons(force=False):
    """Un seul rôle par intitulé dans toute l'entreprise.

    Les bases en service portent un rôle par carto : « Purchasing » existe
    autant de fois qu'il y a de cartos qui en ont la bande, chacun avec ses
    titulaires. On garde celui qui en a le plus (à égalité, le plus ancien) et
    on lui reporte tout le reste. Une seule fois.
    """
    from Code.models.models import AppSetting
    if not force:
        try:
            if db.session.get(AppSetting, CLE_FUSION) is not None:
                return 0
        except Exception:
            db.session.rollback()
            return 0

    groupes = {}
    for r in Role.query.order_by(Role.id).all():
        groupes.setdefault(normalise(r.name), []).append(r)

    fusionnes = 0
    for roles in groupes.values():
        if len(roles) < 2:
            continue
        garde = max(roles, key=lambda r: (_titulaires(r.id), -r.id))
        for doublon in roles:
            if doublon.id == garde.id:
                continue
            _fusionner_paire(garde, doublon)
            fusionnes += 1

    if db.session.get(AppSetting, CLE_FUSION) is None:
        db.session.add(AppSetting(key=CLE_FUSION, value="1"))
    db.session.commit()
    return fusionnes
