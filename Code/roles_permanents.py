"""Les rôles qui existent TOUJOURS, quelle que soit la cartographie.

Les rôles d'une entité viennent des bandes de sa carto, et `_sync_carto_to_db`
supprime ceux qui n'y figurent plus. C'est le bon comportement pour les rôles
métier — la carte fait foi — mais il rendait un rôle d'organisation impossible
à tenir : créé à la main, il disparaissait au prochain enregistrement.

C'est ce qui cassait la section « Affectation » de la page RH. Elle cherchait
un rôle nommé littéralement `manager` (`Role.query.filter_by(name='manager')`) :
sans lui, la liste revenait vide et la section semblait morte. Et quand on le
créait, la synchro de la carto l'effaçait.

**Développeur de compétences** est donc un rôle à part :

  * il est créé d'office pour chaque entité, sans qu'on ait à y penser ;
  * `_sync_carto_to_db` ne le supprime JAMAIS, même absent des bandes ;
  * ses titulaires sont ceux qui accèdent à la sélection de collaborateurs ;
  * il reste un rôle ordinaire pour tout le reste — on en nomme d'autres
    titulaires quand on veut, et un développeur peut lui-même être le
    collaborateur d'un autre développeur.

⚠️ `manager` est l'ancien nom. On le reconnaît au lieu de le renier : les bases
déjà en service en portent, avec leurs titulaires et leurs évaluations. Le
rebaptiser d'autorité ferait perdre ces rattachements à la première lecture.
"""
import unicodedata

from Code.extensions import db
from Code.models.models import Role

#: Nom canonique, celui qu'on crée aujourd'hui.
ROLE_DEV_COMPETENCES = "Développeur de compétences"

#: Ce qu'on accepte comme désignant le même rôle, sur les bases anciennes.
#: Comparé sous forme normalisée (minuscules, sans accents).
_HERITES = (
    "manager",
    "gestionnaire de competences",
    "competency manager",
    "skills developer",
    "competency developer",
)


def _normalise(valeur):
    """Minuscules, sans accents, espaces resserrés — pour comparer des noms
    saisis par des humains dans deux langues."""
    texte = unicodedata.normalize("NFKD", str(valeur or ""))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.lower().split())


def est_dev_competences(nom):
    """Ce nom de rôle désigne-t-il le développeur de compétences ?"""
    n = _normalise(nom)
    return bool(n) and (n == _normalise(ROLE_DEV_COMPETENCES) or n in _HERITES)


def est_permanent(nom):
    """Ce rôle survit-il à une carto qui ne le mentionne pas ?"""
    return est_dev_competences(nom)


def role_dev_competences(entity_id, creer=True):
    """Le rôle « Développeur de compétences » de cette entité.

    Cherche d'abord le nom canonique, puis les noms hérités — on ne veut pas
    fabriquer un doublon à côté d'un `manager` qui a déjà des titulaires.
    """
    if entity_id is None:
        # Sans entité active on ne peut rien cadrer — et surtout rien créer, au
        # risque de semer des rôles orphelins. On se contente de retrouver un
        # rôle existant, comme le faisait le code d'origine : des appels (la
        # liste des managers de la page Compétences) arrivent encore sans
        # entité en session, et leur retirer ce repli les rendrait muets.
        for r in Role.query.all():
            if est_dev_competences(r.name):
                return r
        return None

    candidats = [r for r in Role.query.filter_by(entity_id=entity_id).all()
                 if est_dev_competences(r.name)]
    if candidats:
        # ⚠️ Quand le nom canonique ET un héritage coexistent — le cas d'une base
        # où le rôle vient d'être créé à côté d'un vieux « manager » — c'est
        # celui qui a des TITULAIRES qui fait foi. Préférer le canonique
        # d'office renverrait une liste vide en laissant croire que personne
        # n'est développeur de compétences, alors que les rattachements sont là.
        from Code.models.models import UserRole
        canonique = _normalise(ROLE_DEV_COMPETENCES)

        def poids(r):
            titulaires = UserRole.query.filter_by(role_id=r.id).count() if r.id else 0
            return (titulaires, 1 if _normalise(r.name) == canonique else 0)

        return max(candidats, key=poids)

    if not creer:
        return None
    role = Role(entity_id=entity_id, name=ROLE_DEV_COMPETENCES,
                name_fr=ROLE_DEV_COMPETENCES, name_en="Competency developer")
    db.session.add(role)
    db.session.flush()                   # l'appelant a besoin de son id
    return role


def assurer_roles_permanents(entity_id):
    """À appeler quand on affiche une entité : elle doit avoir ses rôles.

    Ne commit pas — l'appelant décide quand valider, et un simple affichage ne
    doit pas écrire tout seul dans une transaction qu'il ne maîtrise pas.
    """
    return [role_dev_competences(entity_id)] if entity_id is not None else []
