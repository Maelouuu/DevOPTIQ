# -*- coding: utf-8 -*-
"""Proposer une modification sur une ACTIVITÉ — tâches, outils, compétences.

Le même principe que la cartographie, pour l'autre moitié des données : un
champion ne peut pas écrire directement sur une carto commune, il DÉPOSE ce
qu'il veut changer, et un coordinateur applique ou refuse. Appliqué, cela vaut
pour tout le monde — c'est la même ligne en base, il n'y a rien à propager.

⚠️ **Ce n'était pas « rien » avant : c'était un mur.** `Code/ecriture.py`
consulte `carto_access.can_edit`, qui rend faux pour un champion sur une carto
commune. Un champion se faisait donc refuser l'ajout d'une tâche avec le code
`lecture_seule` — le motif réservé à `user`. Il pouvait proposer une
modification de la CARTE et rien de ce qu'elle porte.

⚠️ **Une proposition d'activité n'est PAS un instantané**, contrairement à
celle de la carto. Une carto est un diagramme : on en recopie l'état complet
et on compare deux images. Une fiche d'activité n'a pas d'état global — la
page fait des appels CRUD atomiques, et il n'existe aucun brouillon. Une
proposition est donc une suite de GESTES, rejoués dans l'ordre à
l'application. Transporter un instantané aurait demandé de réécrire la page
entière pour qu'elle travaille sur une copie.

⚠️ **On stocke la requête TELLE QUELLE** (chemin, méthode, corps). Rejouer,
c'est alors rappeler la vraie route : zéro duplication de la logique métier,
et ce qui est appliqué est exactement ce que le champion aurait écrit. Les
champs de lecture (`op`, `objet`) ne servent qu'à l'affichage.

⚠️ **Le libellé se rebâtit à la LECTURE**, jamais à l'écriture. Le champion
propose dans sa langue, le coordinateur lit dans la sienne : un libellé figé
afficherait « Ajouter la tâche… » à un anglophone. C'est la leçon déjà apprise
sur le journal d'activité récente (`changelog._libelle_evenement`).
"""
import json

from flask import current_app, session

from Code.extensions import db


# ── Ce qui se propose, et ce qui reste refusé ─────────────────────────────
#
# ⚠️ Une liste EXPLICITE, pas un « tout sauf ». Détourner une écriture qu'on
# n'a pas prévue, c'est promettre un examen pour un geste que le rejeu ne
# saura peut-être pas refaire. Hors de cette liste, la porte refuse comme
# avant — ce qui est le comportement sûr.
#
# Chaque entrée : (préfixe du chemin, méthode) → code d'opération. Le code sert
# à écrire la phrase lue par le coordinateur, et à rien d'autre.
_SEGMENTS = {
    "tasks": "task",
    "gestion_outils": "tool",
    "skills": "skill",
    "savoirs": "savoir",
    "savoir_faires": "savoirfaire",
    "aptitudes": "aptitude",
    "softskills": "hsc",
    "constraints": "contrainte",
}

# Ce qui, dans ces blueprints, n'écrit RIEN : un appel à l'IA qui propose des
# libellés. Le champion doit pouvoir s'en servir pour préparer sa proposition.
PASSE_TOUJOURS = (
    "/skills/propose",
    "/utils/upload-file",   # dépose un fichier, ne touche aucune activité
)


def route_existe(chemin, methode):
    """La route se resout-elle pour cette methode ?

    ⚠️ Sans cette question, un POST vers une URL qui n'accepte que PUT
    devenait une proposition — acceptee, examinee, puis IMPOSSIBLE a
    appliquer : `rejouer` ne retrouve aucune vue. On ne promet un examen que
    pour un geste qu'on saura rejouer ; sinon la porte refuse comme avant, et
    Flask dit ce qu'il a toujours dit.
    """
    from flask import current_app
    try:
        current_app.url_map.bind("localhost").match(chemin, method=methode)
        return True
    except Exception:
        return False


def chemin_propasable(chemin):
    """Ce chemin fait-il partie de ce qu'on sait proposer ?"""
    if not chemin:
        return False
    if chemin.startswith(PASSE_TOUJOURS):
        return False
    bouts = [b for b in chemin.split("/") if b]
    if not bouts:
        return False
    if bouts[0] in _SEGMENTS:
        return True
    # Deux formulaires de la fiche activité vivent sous /activities.
    return chemin.startswith(("/activities/constraints/", "/activities/data/"))


def _entier(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _nom_activite(activity_id):
    from Code.models.models import Activities
    a = db.session.get(Activities, activity_id) if activity_id else None
    return a.name if a else None


def lire_geste(chemin, methode, corps):
    """Décrit le geste : quelle opération, sur quel objet, dans quelle activité.

    Rend `None` quand le chemin n'est pas de ceux qu'on propose — la porte
    refuse alors comme avant.
    """
    if not chemin_propasable(chemin):
        return None
    corps = corps if isinstance(corps, dict) else {}
    bouts = [b for b in chemin.split("/") if b]
    tete = bouts[0]

    if tete == "activities":
        tete = bouts[1]              # /activities/constraints/add
    famille = _SEGMENTS.get(tete)
    if famille is None:
        famille = "contrainte" if tete == "constraints" else "donnee"

    verbe = {"POST": "add", "PUT": "update", "PATCH": "update",
             "DELETE": "delete"}.get(methode, "update")

    # Les rôles d'une tâche sont un geste à part : ce n'est ni la tâche ni son
    # texte qui changent, c'est QUI la fait.
    if famille == "task" and "roles" in bouts:
        verbe = "role_add" if methode == "POST" else "role_del"
    if famille == "tool" and bouts[-1] == "replace":
        verbe = "replace"

    # ⚠️ Un OUTIL n'appartient à aucune activité : c'est le catalogue de la
    # carto. Le corps d'une création peut pourtant en porter une (il part du
    # panneau d'une tâche) — la retenir ferait paraître « Ajouter l'outil X »
    # sous une fiche qui ne le porte pas.
    activity_id = None if famille == "tool" else _entier(corps.get("activity_id"))
    if activity_id is None:
        activity_id = _activite_du_chemin(famille, bouts)

    return {
        "op": "%s.%s" % (famille, verbe),
        "chemin": chemin,
        "methode": methode,
        "corps": corps,
        "activity_id": activity_id,
        "activite": _nom_activite(activity_id),
        "objet": _nom_objet(famille, bouts, corps),
    }


def _activite_du_chemin(famille, bouts):
    """L'activité visée, quand le corps ne la nomme pas.

    ⚠️ Un OUTIL n'appartient à aucune activité : c'est le catalogue de la
    carto. Sa proposition est donc rattachée à la carto seule — lui inventer
    une activité ferait apparaître le geste sous une fiche qui ne le porte pas.
    """
    from Code.models.models import Task
    if famille == "tool":
        return None
    if famille == "task":
        tid = _entier(bouts[1]) if len(bouts) > 1 else None
        t = db.session.get(Task, tid) if tid else None
        return t.activity_id if t else None
    # savoirs / savoir_faires / aptitudes / softskills / constraints :
    # l'URL de modification est /<famille>/<activity_id>/<item_id>.
    return _entier(bouts[1]) if len(bouts) > 2 else None


def _nom_objet(famille, bouts, corps):
    """Le NOM lisible de ce qu'on touche — jamais un identifiant.

    ⚠️ Comme pour l'historique des imports : l'objet peut être renommé ou
    supprimé d'ici l'examen, et la proposition doit rester lisible.
    """
    for cle in ("name", "description", "nom"):
        valeur = (corps.get(cle) or "").strip() if isinstance(corps.get(cle), str) else ""
        if valeur:
            return valeur[:200]
    return _nom_en_base(famille, bouts)


def _nom_en_base(famille, bouts):
    from Code.models.models import (Aptitude, Competency, Savoir, SavoirFaire,
                                    Softskill, Task, Tool)
    modeles = {"task": Task, "tool": Tool, "skill": Competency,
               "savoir": Savoir, "savoirfaire": SavoirFaire,
               "aptitude": Aptitude, "hsc": Softskill}
    modele = modeles.get(famille)
    if modele is None:
        return None
    # L'identifiant est le dernier segment numérique du chemin.
    for bout in reversed(bouts):
        ident = _entier(bout)
        if ident is None:
            continue
        objet = db.session.get(modele, ident)
        if objet is None:
            continue
        return (getattr(objet, "name", None)
                or getattr(objet, "description", None) or None)
    return None


# ── Le brouillon : on accumule, puis on envoie ────────────────────────────

def brouillon(user, entity, creer=False):
    """La proposition EN COURS de ce compte sur cette carto, ou None.

    ⚠️ **Un lot, pas un geste par proposition.** Corriger une fiche, c'est
    cinq ou six clics ; une proposition par clic noierait le coordinateur et
    lui demanderait six décisions pour un seul travail. Le champion accumule,
    relit, puis envoie — et c'est aussi ce qui rend le refus utile : on refuse
    une intention, pas une touche de clavier.
    """
    from Code.models.models import ActivityChangeRequest
    if user is None or entity is None:
        return None
    cr = (ActivityChangeRequest.query
          .filter_by(entity_id=entity.id, author_id=user.id, status="draft")
          .order_by(ActivityChangeRequest.id.desc())
          .first())
    if cr is None and creer:
        cr = ActivityChangeRequest(entity_id=entity.id, author_id=user.id,
                                   status="draft", actions="[]")
        db.session.add(cr)
    return cr


def gestes(cr):
    try:
        lus = json.loads(cr.actions or "[]")
    except (TypeError, ValueError):
        return []
    return lus if isinstance(lus, list) else []


def ajouter_geste(user, entity, geste):
    """Range le geste dans le brouillon du compte. Rend (proposition, rang)."""
    cr = brouillon(user, entity, creer=True)
    liste = gestes(cr)
    liste.append(geste)
    cr.actions = json.dumps(liste, ensure_ascii=False)
    # Le titre suit ce qu'on touche : une proposition qui ne vise qu'une
    # activité le dit, sinon elle annonce le nombre de fiches.
    noms = {g.get("activite") for g in liste if g.get("activite")}
    cr.activity_id = (liste[-1].get("activity_id")
                      if len({g.get("activity_id") for g in liste
                              if g.get("activity_id")}) == 1 else None)
    cr.title = (list(noms)[0][:200] if len(noms) == 1 else None)
    db.session.commit()
    return cr, len(liste)


def retirer_geste(cr, rang):
    """Retire un geste du brouillon. Le brouillon vidé est supprimé."""
    liste = gestes(cr)
    if rang < 0 or rang >= len(liste):
        return False
    liste.pop(rang)
    if not liste:
        db.session.delete(cr)
        db.session.commit()
        return True
    cr.actions = json.dumps(liste, ensure_ascii=False)
    db.session.commit()
    return True


# ── Rejouer : on rappelle les vraies routes, en UNE transaction ───────────

class EchecDeRejeu(Exception):
    """Un geste n'a pas pu être rejoué. Porte le rang et la raison."""

    def __init__(self, rang, geste, raison):
        super().__init__(raison)
        self.rang = rang
        self.geste = geste
        self.raison = raison


def _neutraliser_commits():
    """Remplace `commit` par `flush` le temps du rejeu.

    ⚠️ Chaque route appelée fait son propre `commit()`. Rejoués tels quels,
    cinq gestes donnent cinq transactions : si le troisième échoue, les deux
    premiers sont déjà écrits et la proposition se retrouve à moitié
    appliquée, sans que personne ne puisse dire où elle s'est arrêtée. On
    applique donc TOUT ou RIEN. Le motif est celui de
    `tools/provisioning/provision.py`, pour la même raison.
    """
    vrai = db.session.commit
    db.session.commit = db.session.flush
    return vrai


def rejouer(cr, acteur):
    """Applique les gestes de la proposition. Lève `EchecDeRejeu` au premier
    qui échoue, après avoir tout annulé.

    ⚠️ On rappelle les VRAIES routes plutôt que de réécrire ce qu'elles font :
    une seconde implémentation de « ajouter une tâche » finirait par diverger
    de la première, et c'est la divergence qu'on cherche à éviter en faisant
    valider par quelqu'un.
    """
    liste = gestes(cr)
    if not liste:
        return 0

    app = current_app._get_current_object()
    adaptateur = app.url_map.bind("localhost")
    memoire = dict(session)
    vrai_commit = _neutraliser_commits()
    try:
        for rang, geste in enumerate(liste):
            chemin = geste.get("chemin") or ""
            methode = (geste.get("methode") or "POST").upper()
            corps = geste.get("corps") if isinstance(geste.get("corps"), dict) else {}
            try:
                point, args = adaptateur.match(chemin, method=methode)
            except Exception as exc:
                raise EchecDeRejeu(rang, geste, "route: %s" % exc)
            vue = app.view_functions.get(point)
            if vue is None:
                raise EchecDeRejeu(rang, geste, "route inconnue")
            with app.test_request_context(chemin, method=methode, json=corps):
                # ⚠️ Les routes lisent la session (entité active, langue) : sans
                # la recopier, le rejeu travaillerait hors de toute carto.
                session.update(memoire)
                try:
                    reponse = vue(**args)
                except Exception as exc:
                    raise EchecDeRejeu(rang, geste, str(exc))
            statut = _statut(reponse)
            if statut >= 400:
                raise EchecDeRejeu(rang, geste, "HTTP %s" % statut)
    except Exception:
        db.session.commit = vrai_commit
        db.session.rollback()
        raise
    db.session.commit = vrai_commit
    db.session.commit()
    return len(liste)


def _statut(reponse):
    """Le code HTTP d'une vue, qu'elle rende un tuple, une Response ou du texte."""
    if isinstance(reponse, tuple):
        for element in reponse[1:]:
            if isinstance(element, int):
                return element
        return 200
    return int(getattr(reponse, "status_code", 200) or 200)
