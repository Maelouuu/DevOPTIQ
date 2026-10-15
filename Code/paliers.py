# -*- coding: utf-8 -*-
"""Les PALIERS DE PERFORMANCE — la règle, en un seul endroit.

La norme de l'entreprise sur une sortie est un nombre : « fournir la doc sous
48 h ». Un collaborateur qui arrive ne l'atteint pas d'emblée ; son
développeur de compétences lui pose des marches — 96 h sous 30 jours, puis
72 h sous 15 jours, puis la norme. Chaque échéance est une session : la
performance est mesurée, et le palier est atteint ou manqué.

⚠️ **Le niveau 0→4 se DÉDUIT de la mesure**, il ne se saisit pas en parallèle.
Deux notes pour une même chose finiraient par se contredire, et c'est le
chiffre mesuré qui fait foi. La correspondance tient le vocabulaire déjà en
place dans le module :

    mesure pire que le premier palier .......... 0  Non démontré
    un palier franchi, pas encore la norme ..... 1  En acquisition
    la norme ATTEINTE .......................... 2  Autonome / compétent  ← qualifié
    la norme DÉPASSÉE .......................... 3  Maîtrise étendue      ← avancé

⚠️ Le niveau **4 (Expertise) n'est jamais déduit** : aucun seuil chiffré ne le
définit honnêtement, c'est un jugement. Il reste posé à la main.

⚠️ Et `SEUIL_AUTONOMIE = 2` garde exactement son sens : sous la norme de
l'entreprise, le collaborateur est en écart. Tout l'aval (couleurs, couverture,
radar, tableau RH) continue de fonctionner sans rien changer.
"""
from datetime import date, datetime

from Code.extensions import db
from Code.models.models import Data, PalierPerformance, SessionEvaluation

# Le sens de la mesure : une durée se bat à la baisse, un taux à la hausse.
MOINS = "moins"
PLUS = "plus"
SENS = (MOINS, PLUS)

STATUTS_PALIER = ("en_cours", "atteint", "manque")
STATUTS_SESSION = ("prevue", "tenue", "annulee")

# Ce que l'atteinte de la norme vaut sur l'échelle de maîtrise.
NIVEAU_QUALIFIE = 2
NIVEAU_AVANCE = 3


def mesurable(d):
    """Une sortie est mesurable quand l'entreprise lui a posé une norme
    chiffrée. Sinon elle reste jugée à la main — « Cahier des charges validé »
    n'a pas de durée."""
    return d is not None and d.norme_valeur is not None and d.norme_sens in SENS


def atteint(mesure, cible, sens):
    """La mesure atteint-elle la cible ? C'est le SENS qui le décide, et c'est
    pour ça qu'il est stocké : sans lui, « mieux » n'a pas de définition."""
    if mesure is None or cible is None:
        return False
    return mesure <= cible if sens == MOINS else mesure >= cible


def _mieux_que(a, b, sens):
    """Strictement meilleur."""
    if a is None or b is None:
        return False
    return a < b if sens == MOINS else a > b


def pas_de_progression(cibles, norme_valeur, norme_sens):
    """Le dernier PAS avant la norme — la marche que le développeur a posée
    juste avant d'aligner le collaborateur sur l'attendu.

    Pour 96 → 72 → 48, c'est 24. C'est ce pas qui sert de marge au-delà de la
    norme : « un palier de mieux que l'attendu ». On ne choisit pas un seuil,
    on reprend celui qui a déjà été décidé.
    """
    if norme_valeur is None or norme_sens not in SENS:
        return None
    # Les cibles qui sont encore EN DEÇÀ de la norme — les marches, pas l'arrivée.
    marches = [c for c in cibles if c is not None
               and not atteint(c, norme_valeur, norme_sens)]
    if not marches:
        return None
    # La plus proche de la norme : la dernière avant l'arrivée.
    proche = min(marches, key=lambda c: abs(c - norme_valeur))
    pas = abs(proche - norme_valeur)
    return pas or None


def seuil_au_dela(cibles, norme_valeur, norme_sens, marge=None):
    """À partir de quelle valeur la norme est DÉPASSÉE, pas seulement tenue.

    ⚠️ Une marche posée AU-DELÀ de la norme est ce seuil, et rien d'autre.
    `pas_de_progression` ne regardait que les marches EN DEÇÀ : sur 67 → 81 →
    95 (norme) → 98, il rendait 14 et plaçait l'au-delà à **109 %** — une
    valeur qui n'existe pas sur un pourcentage. Mesuré à 99 %, le
    collaborateur restait donc à « qualifié » alors qu'il venait de franchir
    la marche que son développeur avait posée exprès au-dessus de l'attendu.
    Et comme le niveau d'une activité est le MINIMUM de ses sorties, l'erreur
    redescendait sur l'activité puis sur le rôle : une personne déclarée
    inapte parce qu'un seuil avait été deviné au lieu d'être lu.

    À défaut de marche au-delà, on retombe sur le pas de progression — la
    règle d'avant, qui reste la bonne quand personne n'a rien posé plus loin.
    """
    if norme_valeur is None or norme_sens not in SENS:
        return None
    # La PREMIÈRE marche strictement au-delà : c'est celle que le développeur
    # a posée comme « mieux que l'attendu ». Les suivantes vont plus loin
    # encore, elles ne déplacent pas la frontière.
    au_dela = [c for c in cibles if c is not None
               and _mieux_que(c, norme_valeur, norme_sens)]
    if au_dela:
        return min(au_dela, key=lambda c: abs(c - norme_valeur))
    if marge is None:
        marge = pas_de_progression(cibles, norme_valeur, norme_sens)
    if not marge:
        return None
    return (norme_valeur - marge) if norme_sens == MOINS else (norme_valeur + marge)


def niveau_depuis_mesure(mesure, norme_valeur, norme_sens, premiere_cible=None,
                         marge=None, au_dela=None):
    """Le niveau 0→4 déduit d'une mesure. NULL si rien n'est mesuré.

    `premiere_cible` est la marche la plus basse de la progression : en
    dessous d'elle, on n'a rien démontré du tout. Sans elle, on ne peut pas
    distinguer « il progresse » de « il n'y est pas », et tout ce qui est sous
    la norme tomberait au même niveau.

    `marge` est le pas de progression (cf. `pas_de_progression`). Un pas de
    mieux que la norme = maîtrise étendue. ⚠️ Sans marge, on ne déduit PAS
    « avancé » : à une heure près d'une norme de 48 h, elle est tenue, pas
    dépassée — et on n'invente pas un seuil pour pouvoir en afficher un.
    """
    if mesure is None or norme_valeur is None or norme_sens not in SENS:
        return None
    if atteint(mesure, norme_valeur, norme_sens):
        # Le seuil EXPLICITE l'emporte sur celui qu'on déduit d'un pas.
        if au_dela is None and marge:
            au_dela = (norme_valeur - marge) if norme_sens == MOINS else (norme_valeur + marge)
        if au_dela is not None and atteint(mesure, au_dela, norme_sens):
            return NIVEAU_AVANCE
        return NIVEAU_QUALIFIE
    if premiere_cible is not None and not atteint(mesure, premiere_cible, norme_sens):
        return 0
    return 1


def paliers_de(user_id, data_id, role_id=None):
    """La progression d'un collaborateur sur une sortie, dans l'ordre."""
    q = PalierPerformance.query.filter_by(user_id=user_id, data_id=data_id)
    if role_id:
        q = q.filter_by(role_id=role_id)
    return q.order_by(PalierPerformance.rang, PalierPerformance.id).all()


def derniere_mesure(paliers):
    """La dernière performance RÉELLEMENT mesurée, et quand.

    ⚠️ On lit le dernier palier ÉVALUÉ, pas le dernier créé : poser la marche
    suivante ne remet pas en cause ce qui a été mesuré, et le niveau ne doit
    pas retomber à « non évalué » entre deux sessions.
    """
    evalues = [p for p in paliers if p.mesure_valeur is not None and p.evalue_le]
    if not evalues:
        return None, None
    dernier = max(evalues, key=lambda p: (p.evalue_le, p.id))
    return dernier.mesure_valeur, dernier.evalue_le


def etat_sortie(d, user_id, role_id=None):
    """Tout ce qu'un écran doit savoir d'une sortie MESURABLE, pour un
    collaborateur : sa norme, sa progression, sa dernière mesure, son niveau.
    """
    paliers = paliers_de(user_id, d.id, role_id)
    mesure, quand = derniere_mesure(paliers)
    premiere = paliers[0].cible_valeur if paliers else None
    cibles = [p.cible_valeur for p in paliers]
    marge = pas_de_progression(cibles, d.norme_valeur, d.norme_sens)
    au_dela = seuil_au_dela(cibles, d.norme_valeur, d.norme_sens, marge)
    niveau = niveau_depuis_mesure(mesure, d.norme_valeur, d.norme_sens, premiere,
                                  marge, au_dela)
    en_cours = next((p for p in paliers if p.statut == "en_cours"), None)
    return {
        "data_id": d.id,
        "nom": d.name,
        "mesurable": True,
        "norme": {"valeur": d.norme_valeur, "unite": d.norme_unite or "",
                  "sens": d.norme_sens},
        "mesure": mesure,
        "mesure_le": quand.isoformat() if quand else None,
        "marge": marge,
        # ⚠️ L'écran dessine la marche « au-delà » à partir de CE seuil, pas
        # d'un calcul à lui : deux implémentations d'une même frontière
        # finissent par dire deux choses — ici, le rail aurait montré 109 %
        # quand le niveau se jouait sur 98 %.
        "au_dela": au_dela,
        "niveau": niveau,
        "qualifie": niveau is not None and niveau >= NIVEAU_QUALIFIE,
        "palier_en_cours": _json_palier(en_cours) if en_cours else None,
        "paliers": [_json_palier(p) for p in paliers],
    }


def _json_palier(p):
    return {
        "id": p.id, "rang": p.rang,
        "cible": p.cible_valeur,
        "echeance": p.echeance.isoformat() if p.echeance else None,
        "statut": p.statut,
        "mesure": p.mesure_valeur,
        "evalue_le": p.evalue_le.isoformat() if p.evalue_le else None,
        "preuve": p.preuve or "",
        "session_id": p.session_id,
    }


def prochain_rang(user_id, data_id, role_id=None):
    paliers = paliers_de(user_id, data_id, role_id)
    return (max(p.rang for p in paliers) + 1) if paliers else 1


def proposer_cible(d, user_id, role_id=None):
    """La marche suivante, proposée — jamais imposée.

    Rien ne remplace le jugement du développeur de compétences : il connaît la
    personne. Mais partir d'une page blanche à chaque palier est pénible, et
    la règle est simple — on coupe en deux ce qui reste à parcourir jusqu'à la
    norme, et on s'arrête à la norme.
    """
    if not mesurable(d):
        return None
    paliers = paliers_de(user_id, d.id, role_id)
    if not paliers:
        # Premier palier : le double de la norme pour une durée, la moitié
        # pour un taux. C'est un point de départ, pas une vérité.
        return d.norme_valeur * 2 if d.norme_sens == MOINS else d.norme_valeur / 2
    depart = paliers[-1].mesure_valeur
    if depart is None:
        depart = paliers[-1].cible_valeur
    if atteint(depart, d.norme_valeur, d.norme_sens):
        return d.norme_valeur
    cible = depart + (d.norme_valeur - depart) / 2.0
    return round(cible, 2)


def trancher(palier, mesure, evaluateur_id=None, preuve=None, quand=None):
    """Poser la mesure d'un palier et en tirer le verdict.

    ⚠️ Le verdict n'est pas saisi, il se CALCULE : on compare la mesure à la
    cible, dans le sens de la norme. Un verdict saisi à la main pourrait
    contredire le chiffre affiché juste à côté.
    """
    d = db.session.get(Data, palier.data_id)
    sens = d.norme_sens if d is not None else MOINS
    palier.mesure_valeur = mesure
    palier.evalue_le = quand or datetime.utcnow()
    palier.evaluateur_user_id = evaluateur_id
    if preuve is not None:
        palier.preuve = (preuve or "").strip() or None
    palier.statut = "atteint" if atteint(mesure, palier.cible_valeur, sens) else "manque"
    return palier.statut


def sessions_de(user_id, role_id=None, a_venir_seulement=False):
    q = SessionEvaluation.query.filter_by(user_id=user_id)
    if role_id:
        q = q.filter_by(role_id=role_id)
    if a_venir_seulement:
        q = q.filter(SessionEvaluation.statut == "prevue",
                     SessionEvaluation.date_prevue >= date.today())
    return q.order_by(SessionEvaluation.date_prevue, SessionEvaluation.id).all()


def json_session(s, n_paliers=None):
    return {
        "id": s.id, "user_id": s.user_id, "role_id": s.role_id,
        "date_prevue": s.date_prevue.isoformat() if s.date_prevue else None,
        "statut": s.statut,
        "tenue_le": s.tenue_le.isoformat() if s.tenue_le else None,
        "objet": s.objet or "",
        "note": s.note or "",
        "n_paliers": n_paliers if n_paliers is not None else len(s.paliers or []),
        "en_retard": bool(s.statut == "prevue" and s.date_prevue
                          and s.date_prevue < date.today()),
    }
