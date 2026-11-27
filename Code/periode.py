# -*- coding: utf-8 -*-
"""La PÉRIODE d'une analyse de temps : le mois qu'elle décrit.

⚠️ Une analyse de temps n'est pas vraie pour l'éternité. Une charge
fluctue — on réorganise, on outille, on change de rythme — et un poids de
rôle relevé en janvier ne dit rien de celui de novembre. Chaque analyse
porte donc le MOIS auquel elle correspond, et c'est lui qui permet de lire
« le poids de ce rôle en novembre » plutôt que « un jour, à une date qu'on
ne sait plus ».

**Format : « YYYY-MM », VARCHAR(7).** Choisi parce qu'il se trie
LEXICALEMENT (donc en SQL, sans conversion), qu'il traverse les deux
dialectes tel quel, et qu'un mois n'est pas une date : stocker le 1er du
mois en TIMESTAMP inviterait à y lire un jour qui n'a aucun sens ici.

⚠️ **Jamais NULL après la reprise.** Les quatre routes posent le mois
courant quand le client n'en envoie pas, et une modification GARDE le mois
en place quand la clé est absente : une analyse sans période ne pourrait
figurer dans aucun tableau, et disparaîtrait de l'écran sans que personne
ne l'ait retirée.

⚠️ **L'affichage ne vit pas ici.** Le navigateur formate « 2026-11 » avec
`Intl` dans la langue de la page : douze noms de mois par langue dans le
catalogue seraient douze occasions de divergence, pour ce qu'une
bibliothèque standard fait déjà.
"""

import re
from datetime import datetime

from Code.extensions import db

#: « 2026-11 » — quatre chiffres, un tiret, deux chiffres.
FORME = re.compile(r"^(\d{4})-(\d{1,2})")

#: Longueur de la colonne, et de ce que les routes acceptent.
LONGUEUR = 7


def mois_courant():
    """Le mois d'aujourd'hui, « YYYY-MM »."""
    a = datetime.utcnow()
    return "%04d-%02d" % (a.year, a.month)


def lire_periode(valeur, defaut=None):
    """« 2026-11 » quoi qu'on reçoive, sinon `defaut`.

    Accepte le mois seul, une date entière (« 2026-11-05 » — c'est ce que
    rend un `<input type="date">`), et un mois non rembourré (« 2026-1 »).
    ⚠️ Tout le reste rend `defaut` : la valeur vient du navigateur, et un
    mois inventé rangerait une analyse dans une période qui n'existe pas.
    """
    if valeur is None:
        return defaut
    m = FORME.match(str(valeur).strip())
    if not m:
        return defaut
    annee, mois = int(m.group(1)), int(m.group(2))
    if not (1 <= mois <= 12) or not (1970 <= annee <= 2999):
        return defaut
    return "%04d-%02d" % (annee, mois)


def mois_de(moment, defaut=None):
    """Le mois d'un `datetime`, ou `defaut` s'il n'y en a pas."""
    if moment is None:
        return defaut
    return "%04d-%02d" % (moment.year, moment.month)


def reprendre_periodes():
    """Pose la période des analyses d'AVANT la colonne, depuis `created_at`.

    Sans elle, chaque analyse déjà en base sortirait de tous les tableaux par
    période — et le nouvel écran paraîtrait vide sur une instance en service,
    ce qui se lit comme une perte de données.

    ⚠️ `created_at` n'est pas une devinette : c'est le mois où l'analyse a
    été enregistrée, c'est-à-dire exactement ce que le formulaire va
    pré-remplir à partir de maintenant.

    ⚠️ `TimeAnalysis` (l'analyse d'ACTIVITÉ) n'a PAS de `created_at` : il n'y
    a rien à en déduire, ses lignes d'avant restent sans période et aucun
    écran ne prétend le contraire.

    ⚠️ Aucun marqueur en base, et c'est voulu : le filtre `periode IS NULL`
    rend la reprise idempotente par construction, et rien dans l'application
    ne peut ramener une période à NULL (voir l'en-tête du module). Rejouée,
    elle ne touche donc plus rien — contrairement à une reprise qui
    PROMEUT, laquelle doit se garder d'un marqueur.

    Rend le nombre de lignes reprises.
    """
    from Code.models.models import TimeProject, TimeRoleAnalysis, TimeWeakness

    n = 0
    for modele in (TimeProject, TimeRoleAnalysis, TimeWeakness):
        for ligne in modele.query.filter(modele.periode.is_(None)).all():
            p = mois_de(getattr(ligne, "created_at", None))
            if p:
                ligne.periode = p
                n += 1
    if n:
        db.session.commit()
    return n
