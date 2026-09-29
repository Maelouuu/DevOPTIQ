"""Deux cartos ne peuvent plus porter le même nom.

Le nom d'une carto est ce qui la désigne PARTOUT : le sélecteur d'entité active,
la galerie de la page Partage, les colonnes de la matrice d'accès, le tableau des
compétences de la page RH, la liste des propositions à examiner. Cinq cartos
« FluidClip » — ce que le dépôt de copies avait fabriqué sur le pilote — rendent
tous ces écrans indéchiffrables : rien ne dit laquelle on regarde.

⚠️ La comparaison est NORMALISÉE (minuscules, sans accents, espaces resserrés) :
« FluidClip », « fluidclip » et « Fluid  Clip » désignent la même chose pour un
lecteur humain, et c'est le lecteur qu'on protège. Elle est donc plus stricte
qu'une contrainte UNIQUE en base, qui laisserait passer les trois — d'où
l'absence d'index unique et le passage OBLIGÉ par ce module.

⚠️ Deux formes de numérotation, et c'est voulu :
  · « Nom (2) », « Nom (3) »… quand le code doit trouver un nom libre tout seul
    (dépôt d'une copie, import d'un paquet, clonage) — convention déjà en place ;
  · « Nom 1 », « Nom 2 »… pour la reprise des doublons DÉJÀ en base, où les
    cartos sont de vraies jumelles qu'on numérote d'un bout à l'autre.
"""
import unicodedata
from datetime import datetime

from Code.extensions import db
from Code.models.models import Entity

#: Marqueur en BASE : une instance qui redémarre, se duplique ou se redéploie
#: doit lire la même réponse (même règle que les autres reprises).
CLE_NUMEROTATION = "entites_nom_unique"

#: `entities.name` est un VARCHAR(200).
MAX = 200


def normalise(valeur):
    """Minuscules, sans accents, espaces resserrés."""
    texte = unicodedata.normalize("NFKD", str(valeur or ""))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.lower().split())


def base_nom(nom):
    """« FluidClip (3) » → « FluidClip ».

    Sert à retrouver la carto JUMELLE d'un compte quand on lui propose une copie :
    sa copie porte forcément un autre nom maintenant, mais c'est la même carto.
    ⚠️ On ne retire QUE la forme « (n) » : « Atelier 2 » est peut-être le vrai nom
    d'un second atelier, le deviner ferait disparaître une carto légitime.
    """
    nom = (nom or "").strip()
    if nom.endswith(")"):
        ouvre = nom.rfind(" (")
        if ouvre > 0 and nom[ouvre + 2:-1].isdigit():
            return nom[:ouvre].strip()
    return nom


def noms_pris(sauf_id=None):
    """{nom normalisé} de toutes les cartos, celle qu'on modifie exceptée."""
    q = Entity.query
    if sauf_id:
        q = q.filter(Entity.id != sauf_id)
    return {normalise(e.name) for e in q.all() if e.name}


def nom_libre(nom, sauf_id=None):
    nom = (nom or "").strip()
    return bool(nom) and normalise(nom) not in noms_pris(sauf_id)


def nom_unique(nom, sauf_id=None, defaut="Cartographie"):
    """Le nom demandé s'il est libre, sinon « Nom (2) », « Nom (3) »…

    Pour les chemins AUTOMATIQUES seulement (copie, paquet, clone) : une création
    à la main doit être refusée, pas renommée en douce.
    """
    nom = (nom or "").strip()[:MAX] or defaut
    pris = noms_pris(sauf_id)
    if normalise(nom) not in pris:
        return nom
    i = 2
    while True:
        suffixe = " (%d)" % i
        essai = nom[:MAX - len(suffixe)] + suffixe
        if normalise(essai) not in pris:
            return essai
        i += 1


def _rang(entity):
    """⚠️ Les lignes d'avant la colonne `created_at` la portent à NULL : ce sont
    les plus anciennes, elles passent donc devant."""
    return (entity.created_at or datetime.min, entity.id or 0)


def numeroter_doublons(force=False):
    """Numérote les cartos homonymes DÉJÀ en base, la plus ancienne en « 1 ».

    Une seule fois : rejouée à chaque démarrage, elle renommerait « FluidClip 1 »
    en « FluidClip 1 1 » au premier homonyme suivant. Retourne la liste des
    renommages, pour le journal de démarrage.
    """
    from Code.models.models import AppSetting
    if not force:
        try:
            if db.session.get(AppSetting, CLE_NUMEROTATION) is not None:
                return []
        except Exception:
            db.session.rollback()
            return []

    toutes = Entity.query.all()
    groupes = {}
    for e in toutes:
        groupes.setdefault(normalise(e.name), []).append(e)

    pris = {cle for cle in groupes if cle}
    renommes = []
    for cle, membres in groupes.items():
        if not cle or len(membres) < 2:
            continue
        # Les noms du groupe se libèrent : les membres vont tous en changer.
        pris.discard(cle)
        i = 0
        for e in sorted(membres, key=_rang):
            avant = e.name
            while True:
                i += 1
                suffixe = " %d" % i
                essai = (avant or "").strip()[:MAX - len(suffixe)] + suffixe
                if normalise(essai) not in pris:
                    break
            pris.add(normalise(essai))
            e.name = essai
            renommes.append((e.id, avant, essai))

    if db.session.get(AppSetting, CLE_NUMEROTATION) is None:
        db.session.add(AppSetting(key=CLE_NUMEROTATION, value="1"))
    db.session.commit()
    return renommes
