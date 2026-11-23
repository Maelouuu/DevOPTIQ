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
import re

from flask import current_app, session

from Code.extensions import db


# ── Désigner ce qui n'existe pas encore ───────────────────────────────────
#
# ⚠️⚠️ Le palier de soumission exige au moins un OUTIL par activité, et un
# outil se rattache à une TÂCHE. Sur une activité vierge, le champion crée
# donc la tâche (geste 0) puis veut l'outiller — mais la tâche n'existe pas en
# base : elle n'a aucun identifiant. Le palier était **infranchissable**, et
# c'est ce que l'usage a montré (« comment j'associe un outil à une tâche si
# elle n'apparaît pas »).
#
# ⚠️ Et on ne peut PAS écrire l'identifiant que la simulation vient de
# produire : il naît d'un `flush` annulé juste après, et le vrai rejeu, à
# l'approbation, en donnera un autre. Un geste qui le porterait viserait une
# ligne au hasard.
#
# Un geste désigne donc le RANG du geste qui crée l'objet — `b:0` — et le
# rejeu le résout par ce qu'il vient réellement d'écrire.
REF = re.compile(r"^b:(\d+)$")


def rang_de_la_ref(valeur):
    """Le rang visé par une référence locale, ou None si ce n'en est pas une."""
    if not isinstance(valeur, str):
        return None
    m = REF.match(valeur.strip())
    return int(m.group(1)) if m else None


def ref_vers(rang):
    return "b:%d" % rang


def refs_du_corps(corps):
    """Les rangs référencés par ce corps, quelle que soit la clé."""
    rangs = set()
    if not isinstance(corps, dict):
        return rangs
    for valeur in corps.values():
        if isinstance(valeur, list):
            for element in valeur:
                rang = rang_de_la_ref(element)
                if rang is not None:
                    rangs.add(rang)
            continue
        rang = rang_de_la_ref(valeur)
        if rang is not None:
            rangs.add(rang)
    return rangs


def _reecrire_refs(corps, decaler):
    """Rend une copie du corps dont chaque référence passe par `decaler`.

    `decaler(rang)` rend le nouveau rang, ou None pour laisser la valeur
    telle quelle.
    """
    if not isinstance(corps, dict):
        return corps
    neuf = {}
    for cle, valeur in corps.items():
        if isinstance(valeur, list):
            neuf[cle] = [_une_ref(v, decaler) for v in valeur]
        else:
            neuf[cle] = _une_ref(valeur, decaler)
    return neuf


def _une_ref(valeur, decaler):
    rang = rang_de_la_ref(valeur)
    if rang is None:
        return valeur
    neuf = decaler(rang)
    return valeur if neuf is None else ref_vers(neuf)


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
    # ⚠️ `/tools/add` et `/tools/delete` RATTACHENT (ou détachent) un outil à
    # une TÂCHE — ils ne touchent pas au catalogue. Ils manquaient à cette
    # liste : un champion se faisait refuser l'outillage d'une tâche avec
    # `lecture_seule`, le motif réservé à `user`. Même famille que l'oubli du
    # garant (« Unable to set the garentor », pilote du 29/10) — et c'est
    # bloquant depuis le 22/11, puisque le PALIER de soumission exige au moins
    # un outil par activité : sans ces deux routes il serait infranchissable.
    "tools": "tool",
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
    # ⚠️ Le GARANT d'une activité, et LUI SEUL, parmi les routes `/roles` :
    # mettre tout `/roles` dans `_SEGMENTS` rendrait proposable la SUPPRESSION
    # d'un rôle, qui emporte ses titulaires et ses liens dans TOUTES les cartos
    # et qui est réservée à l'administrateur. Désigner le garant, en revanche,
    # est une donnée d'activité comme les autres : c'était un oubli de la
    # liste, et le retour « Unable to set the garentor » du pilote.
    if chemin.startswith("/roles/garant/activity/"):
        return True
    # ⚠️ L'assistant IA crée des TÂCHES — avec leurs outils et parfois un lien
    # sortant. C'est donc une écriture de données d'activité comme une autre,
    # et elle se propose. Sans cette ligne, un champion se voyait répondre
    # « lecture seule » par le chatbot (relevé chez le pilote), alors qu'il a
    # le droit de proposer la même tâche à la main.
    if chemin == "/api/chatbot/inject":
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


def lire_geste(chemin, methode, corps, deja=None):
    """Décrit le geste : quelle opération, sur quel objet, dans quelle activité.

    Rend `None` quand le chemin n'est pas de ceux qu'on propose — la porte
    refuse alors comme avant.

    `deja` est la liste des gestes DÉJÀ rangés dans le brouillon : elle sert à
    retrouver l'activité d'un geste qui vise un objet encore en attente
    (« outiller la tâche du geste 0 »). Sans elle, ce geste n'aurait aucune
    activité et se rangerait « hors activité » — là où le champion ne le
    retrouverait pas.
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
    # ⚠️ `/roles/garant/activity/<id>` : `bouts[0]` vaut « roles », qui n'est
    # pas dans `_SEGMENTS` — sans ce cas la famille retombait sur « donnee » et
    # le coordinateur lisait « Ajouter la donnée » pour une désignation de
    # garant.
    garant = bouts[:2] == ["roles", "garant"]
    if garant:
        famille = "garant"
    # ⚠️ L'assistant IA injecte des TÂCHES : son chemin commence par « api »,
    # donc `_SEGMENTS` ne le reconnaît pas et la famille retombait sur
    # « donnee » — le coordinateur aurait lu « Ajouter la donnée » pour une
    # fournée de tâches.
    if chemin == "/api/chatbot/inject":
        famille = "task"

    verbe = {"POST": "add", "PUT": "update", "PATCH": "update",
             "DELETE": "delete"}.get(methode, "update")
    if garant:
        verbe = "designer"

    # Les rôles d'une tâche sont un geste à part : ce n'est ni la tâche ni son
    # texte qui changent, c'est QUI la fait.
    if famille == "task" and "roles" in bouts:
        verbe = "role_add" if methode == "POST" else "role_del"
    if famille == "tool" and bouts[-1] == "replace":
        verbe = "replace"
    # ⚠️ `POST /tools/delete` DÉTACHE : le verbe se lit sur le chemin, pas sur
    # la méthode, sinon le coordinateur lisait « Ajouter l'outil » pour un
    # retrait.
    if famille == "tool" and bouts[-1] == "delete":
        verbe = "delete"

    # ⚠️ Un OUTIL n'appartient à aucune activité : c'est le catalogue de la
    # carto. Le corps d'une création peut pourtant en porter une (il part du
    # panneau d'une tâche) — la retenir ferait paraître « Ajouter l'outil X »
    # sous une fiche qui ne le porte pas.
    # ⚠️ SAUF quand on le rattache à une TÂCHE (`/tools/add`, `/tools/delete`,
    # qui portent un `task_id`) : là le geste concerne bien la fiche de son
    # activité, et c'est sous elle qu'on vient le relire.
    if famille == "tool":
        activity_id = _activite_de_la_tache(_entier(corps.get("task_id")))
    else:
        activity_id = _entier(corps.get("activity_id"))
    if activity_id is None:
        activity_id = _activite_du_chemin(famille, bouts)
    if activity_id is None:
        activity_id = _activite_dun_geste_vise(corps, deja)

    return {
        "op": "%s.%s" % (famille, verbe),
        "chemin": chemin,
        "methode": methode,
        "corps": corps,
        "activity_id": activity_id,
        "activite": _nom_activite(activity_id),
        "objet": _nom_objet(famille, bouts, corps),
    }


def _activite_dun_geste_vise(corps, deja):
    """L'activité du geste que celui-ci référence, s'il en vise un.

    Outiller une tâche encore en attente, c'est travailler sur l'activité de
    cette tâche : le geste doit se relire sous la MÊME fiche, sinon il part
    « hors activité » et le champion ne le retrouve nulle part.
    """
    if not deja:
        return None
    for rang in sorted(refs_du_corps(corps)):
        if 0 <= rang < len(deja):
            vise = deja[rang].get("activity_id")
            if vise:
                return vise
    return None


def _activite_de_la_tache(task_id):
    """L'activité d'une tâche, ou None. Sert aux gestes qui outillent."""
    from Code.models.models import Task
    if not task_id:
        return None
    t = db.session.get(Task, task_id)
    return t.activity_id if t else None


def _activite_du_chemin(famille, bouts):
    """L'activité visée, quand le corps ne la nomme pas.

    ⚠️ Un OUTIL n'appartient à aucune activité : c'est le catalogue de la
    carto. Sa proposition est donc rattachée à la carto seule — lui inventer
    une activité ferait apparaître le geste sous une fiche qui ne le porte pas.
    """
    from Code.models.models import Task
    if famille == "tool":
        return None
    if famille == "garant":
        # /roles/garant/activity/<activity_id>
        return _entier(bouts[-1])
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
    if famille == "garant":
        # Le corps ne porte qu'un `role_id` : on nomme le RÔLE, jamais son
        # identifiant — la proposition doit rester lisible si le rôle est
        # renommé d'ici l'examen.
        from Code.models.models import Role
        role = db.session.get(Role, _entier(corps.get("role_id")))
        return role.name if role else None
    # ⚠️ L'assistant IA injecte une FOURNÉE : ses libellés sont dans
    # `tasks[].label`, et aucun `name` ne traîne à la racine du corps. Sans ce
    # cas la proposition se lisait « Ajouter la tâche — », et le coordinateur
    # devait ouvrir le JSON pour savoir laquelle.
    fournee = corps.get("tasks")
    if isinstance(fournee, list) and fournee:
        libelles = [str(t.get("label") or "").strip()
                    for t in fournee if isinstance(t, dict)]
        libelles = [n for n in libelles if n]
        if libelles:
            return (libelles[0][:200] if len(libelles) == 1
                    else "%s +%d" % (libelles[0][:180], len(libelles) - 1))
    for cle in ("name", "description", "nom"):
        valeur = (corps.get(cle) or "").strip() if isinstance(corps.get(cle), str) else ""
        if valeur:
            return valeur[:200]
    # ⚠️ `/tools/add` ne porte NI `name` NI identifiant dans son chemin : les
    # outils arrivent par `new_tools` (des noms) et `existing_tool_ids` (des
    # identifiants). Sans ce cas la proposition se lisait « Ajouter l'outil
    # — », et le coordinateur devait deviner lequel.
    if famille == "tool":
        nom = _nom_des_outils(corps)
        if nom:
            return nom
    return _nom_en_base(famille, bouts)


def _nom_des_outils(corps):
    """Les outils nommés par un geste de rattachement, « X » ou « X +2 »."""
    from Code.models.models import Tool
    noms = [str(n).strip() for n in (corps.get("new_tools") or [])
            if isinstance(n, (str,)) and str(n).strip()]
    for tid in (corps.get("existing_tool_ids") or []):
        outil = db.session.get(Tool, _entier(tid))
        if outil is not None:
            noms.append(outil.name)
    if not noms:
        outil = db.session.get(Tool, _entier(corps.get("tool_id")))
        if outil is not None:
            noms.append(outil.name)
    if not noms:
        return None
    return noms[0][:200] if len(noms) == 1 else "%s +%d" % (noms[0][:180], len(noms) - 1)


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
    """Retire un geste du brouillon. Le brouillon vidé est supprimé.

    ⚠️⚠️ Un geste peut en VISER un autre par son rang (`b:0`) : retirer la
    tâche emporte donc les outils qu'on lui avait rattachés — ils ont perdu
    leur sujet, et le rejeu buterait dessus à l'approbation. Et les rangs de
    ce qui RESTE se décalent : sans renumérotation, « outiller la tâche du
    geste 3 » se mettrait à désigner le geste 2, c'est-à-dire n'importe quoi.
    """
    liste = gestes(cr)
    if rang < 0 or rang >= len(liste):
        return False

    # Ce qui tombe : le geste visé, et de proche en proche tout ce qui le
    # référence (un outil posé sur une tâche posée sur…).
    condamnes = {rang}
    change = True
    while change:
        change = False
        for i, geste in enumerate(liste):
            if i in condamnes:
                continue
            if refs_du_corps(geste.get("corps")) & condamnes:
                condamnes.add(i)
                change = True

    restants = [g for i, g in enumerate(liste) if i not in condamnes]
    if not restants:
        db.session.delete(cr)
        db.session.commit()
        return True

    # Les rangs se resserrent : on écrit la table ancien → nouveau une fois,
    # et chaque référence la suit.
    nouveau = {}
    for i in range(len(liste)):
        if i not in condamnes:
            nouveau[i] = len(nouveau)
    for geste in restants:
        geste["corps"] = _reecrire_refs(geste.get("corps"),
                                        lambda r: nouveau.get(r))

    cr.actions = json.dumps(restants, ensure_ascii=False)
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


def _appliquer_gestes(liste):
    """Rejoue les gestes dans la session COURANTE, sans rien valider.

    Le corps commun de `rejouer` (qui valide) et de `simuler` (qui annule) :
    deux boucles de rejeu finiraient par ne plus appliquer la même chose, et
    l'écran annoncerait une carto que l'envoi refuserait.

    ⚠️ On appelle la VUE directement, jamais par le client de test : les
    `before_request` ne tirent donc pas, et c'est nécessaire — la porte
    d'écriture détournerait les gestes du champion vers son propre brouillon,
    en boucle.
    """
    app = current_app._get_current_object()
    adaptateur = app.url_map.bind("localhost")
    memoire = dict(session)
    # ⚠️ Ce que CE rejeu vient d'écrire, rang par rang. Les identifiants ne
    # survivent pas d'un rejeu à l'autre (la simulation annule tout) : une
    # référence `b:0` ne peut se résoudre qu'ici, et seulement ici.
    nes = {}
    for rang, geste in enumerate(liste):
        chemin = geste.get("chemin") or ""
        methode = (geste.get("methode") or "POST").upper()
        corps = geste.get("corps") if isinstance(geste.get("corps"), dict) else {}
        corps = _resoudre_refs(corps, nes, rang, geste)
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
            ne = _id_cree(reponse)
        statut = _statut(reponse)
        if statut >= 400:
            raise EchecDeRejeu(rang, geste, "HTTP %s" % statut)
        if ne is not None:
            nes[rang] = ne


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

    vrai_commit = _neutraliser_commits()
    try:
        _appliquer_gestes(liste)
    except Exception:
        db.session.commit = vrai_commit
        db.session.rollback()
        raise
    db.session.commit = vrai_commit
    db.session.commit()
    return len(liste)


def simuler(cr, mesurer):
    """Ce que le brouillon DONNERAIT s'il s'appliquait — sans rien écrire.

    Rend la valeur de `mesurer()`, appelée une fois les gestes rejoués.

    ⚠️ On rejoue les vraies routes, puis on ANNULE. C'est la seule façon de
    n'avoir qu'une idée de ce qu'« ajouter une tâche » veut dire : une mesure
    qui relirait les gestes à sa façon finirait par annoncer une carto
    complète que l'envoi refuse — ou l'inverse.

    ⚠️ L'annulation est dans un `finally` : une simulation qui laisse une
    ligne derrière elle a écrit sans qu'on le lui demande. Et elle remet la
    session en état AVANT que l'appelant ne mesure à nouveau sur la base —
    après une vue qui a levé, la session refuse toute requête tant qu'on n'a
    pas annulé.

    ⚠️ `EchecDeRejeu` REMONTE : un geste qui ne s'applique plus ne se mesure
    pas, il se dit. L'appelant tranche (et l'envoi butera dessus de toute
    façon).
    """
    liste = gestes(cr) if cr is not None else []
    if not liste:
        return mesurer()
    vrai_commit = _neutraliser_commits()
    try:
        _appliquer_gestes(liste)
        return mesurer()
    finally:
        db.session.commit = vrai_commit
        db.session.rollback()


def _resoudre_refs(corps, nes, rang, geste):
    """Remplace les `b:N` du corps par ce que le geste N vient d'écrire.

    ⚠️ Un rang qui n'a RIEN produit lève : laisser passer la chaîne « b:0 »
    la ferait arriver jusqu'à `int()` dans la route visée, et le rejeu
    s'arrêterait sur une pile Python au lieu d'un motif lisible. Un geste qui
    vise un objet jamais créé ne s'applique pas, et il faut le dire.
    """
    rangs = refs_du_corps(corps)
    if not rangs:
        return corps
    for vise in rangs:
        if vise not in nes:
            raise EchecDeRejeu(rang, geste, "ref: b:%d" % vise)
    return _reecrire_refs_valeurs(corps, nes)


def _reecrire_refs_valeurs(corps, nes):
    neuf = {}
    for cle, valeur in corps.items():
        if isinstance(valeur, list):
            neuf[cle] = [_valeur_resolue(v, nes) for v in valeur]
        else:
            neuf[cle] = _valeur_resolue(valeur, nes)
    return neuf


def _valeur_resolue(valeur, nes):
    rang = rang_de_la_ref(valeur)
    return valeur if rang is None else nes[rang]


def _id_cree(reponse):
    """L'identifiant que cette réponse annonce avoir créé, ou None."""
    corps = reponse[0] if isinstance(reponse, tuple) else reponse
    try:
        donnees = corps.get_json(silent=True)
    except Exception:
        return None
    if not isinstance(donnees, dict):
        return None
    valeur = donnees.get("id")
    return valeur if isinstance(valeur, int) else None


def _statut(reponse):
    """Le code HTTP d'une vue, qu'elle rende un tuple, une Response ou du texte."""
    if isinstance(reponse, tuple):
        for element in reponse[1:]:
            if isinstance(element, int):
                return element
        return 200
    return int(getattr(reponse, "status_code", 200) or 200)
