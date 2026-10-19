# -*- coding: utf-8 -*-
"""Qui a le droit d'ÉCRIRE — une seule porte, pour toute l'application.

⚠️ Relevé le 11/10/2026 : **39 fichiers de routes portaient des écritures et
AUCUN contrôle d'accès** — `tasks.py` (5 routes), `gestion_outils.py` (4),
`roles.py`, `savoirs`, `savoir_faires`, `aptitudes`, `softskills`,
`constraints`, `propose_from_file.py`, `time_view.py` (14)… et aucun
`before_request` global ne les couvrait. Un compte `user` créait des tâches,
réécrivait la description d'un outil du catalogue partagé et pouvait remplacer
le fichier de référence DCP de toute l'organisation. Le tableau des droits
disait pourtant, depuis le début, que `user` **consulte et ne modifie rien**.

⚠️ **Une porte CENTRALE, et pas une garde par route.** Trente-neuf fichiers
corrigés un par un, c'est trente-neuf occasions d'en oublier un — et surtout
la quarantième route écrite demain serait ouverte à nouveau. Ici le défaut est
fermé par CLASSE : tout ce qui écrit est refusé, sauf ce qui est nommé
ci-dessous.

⚠️ **Donc la liste des exemptions est le cœur du fichier.** Elle est explicite
et commentée : une ligne non justifiée est un trou. Elle ne contient que deux
familles — ce qui n'est pas une donnée métier (langue, télémétrie,
connexion), et ce qui porte DÉJÀ un contrôle plus fin que « sait écrire »
(noter quelqu'un, modifier son propre compte, proposer une modification de
carto). Ces routes-là gardent leur propre garde : la porte centrale ne la
remplace pas, elle s'efface devant.
"""
from flask import jsonify, redirect, request, session

from Code.permissions import a_le_droit, current_user

METHODES_ECRITURE = {"POST", "PUT", "PATCH", "DELETE"}

# Le droit qui ouvre l'écriture des données métier. C'est le même que celui
# d'enregistrer une carto : activités, tâches, outils, rôles et compétences
# SONT les données d'une carto.
DROIT_ECRITURE = "edit_carto"

# ── Ouvert à tout le monde, connecté ou non ────────────────────────────────
# Rien de métier ne s'écrit ici.
SANS_COMPTE = (
    "/login",                 # se connecter
    "/logout",
    "/reset",                 # mot de passe oublié
    "/forgot",
    "/setup",                 # assistant de première installation
    "/pulse",                 # télémétrie d'audience, aucune donnée métier
    "/static",
)

# ── Déjà gardé ailleurs, plus finement ────────────────────────────────────
# ⚠️ Cette liste n'est pas une liste de confiance : c'est la liste des routes
# qui portent DÉJÀ leur propre contrôle, et dont la règle est plus fine que
# « sait écrire ». La porte centrale s'efface devant elles — elle ne les
# remplace pas, et les y ajouter n'enlève aucun contrôle.
#
# ⚠️ Elle a été écrite d'après ce que la porte a RÉELLEMENT refusé en rejouant
# la suite (66 refus, journalisés avec le statut du compte), pas d'après ce
# qu'on imaginait : trois des familles ci-dessous n'avaient pas été prévues.
# Toute nouvelle ligne se justifie de la même façon — en nommant la garde qui
# prend le relais.
TOUT_COMPTE = (
    # Chacun choisit sa langue et son mot de passe.
    "/parametres/set_language",
    "/parametres/change_password",
    # Paramètres : les sections d'administration ont leur propre garde
    # (`parametres_admin`), et elle est PLUS stricte que celle-ci.
    "/parametres",
    # Page Comptes : `_can_edit_account`, `can_create_accounts`, et le refus de
    # se promouvoir au-dessus de soi. Rien de tout cela ne tient dans un droit
    # d'écriture unique.
    "/comptes",
    # Page RH : `can_access_rh`, plus la règle du développeur par rôle.
    "/gestion_rh",
    # S'auto-évaluer : `competences_acces.peut_noter` décide qui note qui — on
    # ne se décerne pas le niveau qui fait foi.
    "/mastery",
    # Plan de formation : le développeur de compétences est désigné par un
    # RATTACHEMENT (`users.manager_id`), pas par un statut. Un compte `user`
    # peut donc légitimement écrire ici, et `peut_lire` / `encadre` en décident.
    "/plan",
    # Paliers de performance : poser une cible ou trancher une mesure passe par
    #  avec le ROLE — bien plus fin qu un droit d ecriture unique,
    # et c est le rattachement qui designe le developpeur de competences.
    "/paliers",
    # Cartographie : `can_edit`, `can_propose`, `can_review`, `can_manage_access`
    # — et c'est `/api/save` qui distingue « proposez » (champion) de
    # « lecture seule » (user). La porte centrale écraserait cette nuance.
    "/cartography/api",
    # Entités : activer, partager, supprimer SA carto. La propriété est
    # vérifiée route par route (404 sinon).
    "/activities/api/entities",
    "/activities/api/share",
    # Propositions sur les donnees d'une activite : `can_propose` pour deposer,
    # `can_review` pour trancher — exactement les regles de la cartographie, et
    # bien plus fines qu'un droit d'ecriture unique. C'est d'ailleurs CETTE
    # porte qui y detourne les gestes refuses (voir `_detourner`).
    "/api/propositions",
    # Import : `_peut()` arbitre par nature de données (une carto pour qui
    # l'écrit, des comptes pour qui les crée).
    "/api/import",
    "/api/import-full",
    # Le panel de tests ne touche pas aux données de l'application : il joue
    # pytest sur une base jetable. (Son absence d'authentification est un
    # sujet à part, déjà écrit dans CLAUDE.md.)
    "/testpanel",
)


def _exempte(chemin):
    return chemin.startswith(TOUT_COMPTE)


def _hors_compte(chemin):
    return chemin.startswith(SANS_COMPTE)


MOTIF = {
    "non_connecte": ("non connecté", 401),
    "lecture_seule": ("lecture seule", 403),
}

# ⚠️ Un verdict qui n'est PAS un refus : le geste est détourné vers une
# proposition. Voir `_detourner` plus bas, et `Code/propositions_activite.py`.
VERDICT_PROPOSITION = "proposition"


def _refus(code):
    """Un refus LISIBLE — en JSON pour une API, par la page de connexion pour
    une navigation. ⚠️ Rendre du HTML à un `fetch()` ne lui apprend rien : le
    JS afficherait « erreur inattendue » au lieu du motif."""
    texte, statut = MOTIF[code]
    navigation = (request.accept_mimetypes.accept_html
                  and not request.is_json
                  and request.headers.get("X-Requested-With") != "XMLHttpRequest"
                  and "/api" not in request.path)
    if code == "non_connecte" and navigation:
        return redirect("/login")
    return jsonify({"error": texte, "code": code}), statut


def _peut_ecrire():
    """Le compte peut-il écrire les données de la carto sur laquelle il
    travaille ?

    ⚠️ PAS seulement `a_le_droit('edit_carto')`. Sur une carto PRIVÉE, son
    propriétaire fait ce qu'il veut quel que soit son statut — c'est la règle
    de `carto_access.can_edit`, et la porte doit dire exactement la même
    chose. Mesuré avant livraison sur le pilote : deux comptes ARaymond (un
    `champion` propriétaire de sa carto, un `user`) auraient perdu le droit
    d'écrire chez eux. Une porte qui contredit la règle qu'elle fait
    respecter est un deuxième avis, pas une porte.

    Sans carto active, l'écriture ne vise aucune cartographie : on retombe
    alors sur le droit de statut.
    """
    from Code.carto_access import can_edit
    from Code.models.models import Entity
    try:
        entite = Entity.get_active()
    except Exception:
        entite = None
    if entite is not None:
        return bool(can_edit(entite))
    return bool(a_le_droit(DROIT_ECRITURE))


def _peut_proposer(chemin, methode):
    """Ce compte doit-il PROPOSER ce geste au lieu de se le voir refuser ?

    ⚠️ C'était le trou : `_peut_ecrire` consulte `can_edit`, qui rend faux
    pour un champion sur une carto COMMUNE — il se faisait donc refuser l'ajout
    d'une tâche avec le code `lecture_seule`, le motif réservé à `user`. Il
    pouvait proposer une modification de la CARTE, et rien de ce qu'elle porte.

    Les deux conditions, et seulement elles : le chemin est de ceux qu'on sait
    rejouer, et `can_propose` dit oui sur la carto active — la même règle que
    pour la cartographie, donc la même ligne du tableau des droits.
    """
    from Code.carto_access import can_propose
    from Code.models.models import Entity
    from Code.propositions_activite import chemin_propasable, route_existe
    if not chemin_propasable(chemin) or not route_existe(chemin, methode):
        return False
    try:
        entite = Entity.get_active()
    except Exception:
        return False
    return bool(entite is not None and can_propose(entite))


def porte(chemin, methode, en_test=False):
    """Le verdict, isolé de Flask — pour qu'il soit testable tel quel.

    Rend `None` si l'écriture passe, sinon le CODE du refus.
    """
    if methode not in METHODES_ECRITURE:
        return None
    chemin = chemin or "/"
    if _hors_compte(chemin) or _exempte(chemin):
        return None
    if current_user() is None:
        # ⚠️ Règle 2 — l'écriture SANS COMPTE. Elle est bien réelle : mesuré le
        # 11/10/2026, porte retirée, `POST /tasks/add` sans aucun compte
        # rendait 201 et écrivait la tâche en base.
        #
        # ⚠️ Et elle s'efface sous TESTING, volontairement. La suite fabrique
        # 115 clients anonymes (`app.test_client()`) pour s'isoler de la
        # session partagée, pas pour éprouver l'anonymat : les reprendre un par
        # un noierait la correction dans le bruit. Le refus anonyme est donc
        # vérifié par `tests/test_102_porte_ecriture.py`, qui appelle CETTE
        # fonction directement avec `en_test=False`.
        #
        # ⚠️ Conséquence à ne pas oublier : passer la suite ne prouve PAS que
        # l'anonyme est fermé. Seul ce fichier de tests le prouve.
        return None if en_test else "non_connecte"
    if _peut_ecrire():
        return None
    # ⚠️ Avant de refuser : ce geste se PROPOSE-t-il ? Un champion sur une
    # carto commune n'écrit pas, mais il n'est pas en lecture seule pour
    # autant — c'est exactement ce qui sépare `champion` de `user`.
    if _peut_proposer(chemin, methode):
        return VERDICT_PROPOSITION
    # Règle 1 — connecté, mais sans le droit d'écrire. C'est le défaut que
    # l'audit a relevé : un compte `user` créait des tâches et réécrivait la
    # description d'un outil partagé.
    return "lecture_seule"


def _detourner():
    """Range le geste dans le brouillon du compte, et le dit au navigateur.

    ⚠️ **202, pas 200.** Le geste n'est PAS appliqué : répondre comme une
    écriture réussie ferait rafraîchir la liste à l'écran, qui montrerait
    alors la base inchangée — on croirait avoir perdu sa saisie. Le code
    `proposition` est ce que `static/js/activite_propositions.js` attend pour
    dire que c'est parti à l'examen.
    """
    from Code.models.models import Entity
    from Code.propositions_activite import ajouter_geste, lire_geste

    geste = lire_geste(request.path, request.method,
                       request.get_json(silent=True))
    if geste is None:                       # on ne sait pas rejouer : on refuse
        return _refus("lecture_seule")
    cr, n = ajouter_geste(current_user(), Entity.get_active(), geste)
    return jsonify({
        "code": "proposition",
        "proposition_id": cr.id,
        "n": n,
        "op": geste["op"],
        "objet": geste.get("objet"),
        "activite": geste.get("activite"),
    }), 202


def installer_porte_ecriture(app):
    """Branche la porte. Appelée une fois, à la création de l'application."""

    @app.before_request
    def _porte_ecriture():
        verdict = porte(request.path, request.method,
                        en_test=bool(app.config.get("TESTING")))
        if verdict is None:
            return None
        if verdict == VERDICT_PROPOSITION:
            return _detourner()
        import os
        if os.environ.get("OPTIQ_TRACE_PORTE"):
            u = current_user()
            with open(os.environ["OPTIQ_TRACE_PORTE"], "a") as f:
                f.write("%s\t%s\t%s\t%s\n" % (
                    verdict, request.method, request.path,
                    (u.status if u else "-")))
        return _refus(verdict)
