# -*- coding: utf-8 -*-
"""La fenêtre de bienvenue : QUI la voit, QUAND, et ce qu'elle montre.

⚠️⚠️ **Pourquoi tout cela vit côté serveur.** L'ancienne fenêtre décidait de
s'afficher dans le navigateur, après un `fetch('/api/changelog')`, en comparant
une signature rangée en `localStorage`. Mesuré au banc (`tools/devrun_bienvenue.py`),
ce montage lâchait par TROIS chemins :

  1. **La signature était bâtie sur de la prose TRADUITE** (`title` + début de
     `desc`), or `changelog.py` sert `title_en`/`desc_en` à une session anglaise.
     Les mêmes trois nouveautés donnaient donc deux signatures. Avec
     `DEFAULT_LANG = 'en'` et un écran de connexion qui repose la langue à
     l'anglais, l'écart arrivait tout seul : la fenêtre revenait.
  2. **Le stockage peut refuser d'écrire.** Le `try/catch` avalait l'échec en
     silence, et la fenêtre revenait dans CHAQUE nouvel onglet, sans fin.
  3. **La décision dépendait d'un `fetch`.** Tant qu'il n'avait pas répondu, le
     voile restait `display:flex` (son état au repos en CSS) : une requête en
     erreur laissait l'application entière cliquable NULLE PART, sans que rien
     ne se voie — et les deux pop-ups qui s'enchaînent derrière attendaient
     indéfiniment leur tour.

Ici, le serveur sait déjà tout ce qu'il faut : il tranche avant de rendre la
page. Le gabarit reçoit `montrer` et son contenu, le voile naît `display:none`,
et plus rien ne dépend du réseau.
"""
import hashlib
import json
import os

from Code.permissions import a_le_droit, current_user, famille_statut
from Code.translations import t

# Version du format de signature. La changer fait revoir la fenêtre une fois à
# tout le monde — c'est voulu quand ce qu'elle montre change de nature.
VERSION_SIGNATURE = "b1"


def _fichier_cure():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(racine, 'static', 'changelog_user.json')


def _items_bruts():
    """Les nouveautés telles qu'elles sont ÉCRITES, sans résolution de langue.

    ⚠️ C'est la source de la signature : la lire via `changelog.py` donnerait du
    texte déjà traduit, donc une signature qui change avec la langue — le défaut
    qu'on corrige.
    """
    chemin = _fichier_cure()
    if not os.path.exists(chemin):
        return []
    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            items = json.load(f)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def signature_nouveautes():
    """L'IDENTITÉ des nouveautés en vigueur — indépendante de la langue.

    Chaque nouveauté porte un `id` stable ; à défaut, on prend l'empreinte de
    ses champs français, qui ne bougent pas quand on lit en anglais. Aucune
    nouveauté lisible → signature vide : on ne fait pas revenir la fenêtre pour
    un fichier illisible.

    ⚠️ Quand le fichier curé est absent, `changelog.py` fait GÉNÉRER les
    nouveautés (température 0.3, cache par processus) : leur texte diffère d'une
    instance à l'autre. On ne met donc rien de ce texte dans la signature — ce
    serait remettre la fenêtre à chaque instance servie.
    """
    items = _items_bruts()
    if not items:
        return ""
    morceaux = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cle = str(item.get('id') or '').strip()
        if not cle:
            brut = (str(item.get('title') or '') + '\x1f' + str(item.get('desc') or ''))
            cle = hashlib.sha1(brut.encode('utf-8')).hexdigest()[:10]
        morceaux.append(cle)
    if not morceaux:
        return ""
    return VERSION_SIGNATURE + ':' + '|'.join(morceaux)


# ── Ce que le compte OUVRE ─────────────────────────────────────────────────
#
# ⚠️ Chaque porte est gardée par `a_le_droit`, JAMAIS par une liste de statuts
# en dur : les droits des trois premiers paliers se règlent depuis la page
# Comptes (`permissions.droits_effectifs`), et une liste figée ici recommencerait
# à annoncer des portes fermées le jour où un coordinateur en retire une.
#
# Le quadruplet (droit, clé de libellé, couleur, icône). La couleur est celle
# de l'icône de la page visée dans la nav — même code que le design system —
# et l'icône dit le GESTE, pas la page : c'est ce que le compte peut faire.
PORTES = (
    ("propose_carto",   "welcome.door.propose",   "#0d9488", "fa-paper-plane"),
    ("edit_carto",      "welcome.door.edit",      "#0d9488", "fa-pen-to-square"),
    ("review_carto",    "welcome.door.review",    "#0d9488", "fa-gavel"),
    ("manage_acces",    "welcome.door.access",    "#0891b2", "fa-user-lock"),
    ("acces_rh",        "welcome.door.rh",        "#16a34a", "fa-building-user"),
    ("cree_comptes",    "welcome.door.accounts",  "#e11d48", "fa-user-plus"),
    ("modifie_comptes", "welcome.door.edit_acct", "#e11d48", "fa-users-gear"),
    ("parametres_admin", "welcome.door.admin",    "#6366f1", "fa-sliders"),
)

# Le plancher : ce que TOUT compte connecté peut faire. Ce ne sont pas des
# droits réglables — sans elles, un `user` ouvrirait une fenêtre vide, ce qui
# lui dirait « vous ne pouvez rien » alors qu'il consulte et se suit.
PLANCHER = (
    ("welcome.door.consult", "#7c3aed", "fa-diagram-project"),
    ("welcome.door.skills",  "#2563eb", "fa-layer-group"),
)


def portes_ouvertes(user=None, lang=None):
    """Les portes que CE compte peut franchir, dans l'ordre de l'échelle.

    ⚠️ Deux droits se FONDENT quand ils vont ensemble, et ce n'est pas de la
    coquetterie : éprouvé à l'écran, un administrateur avait dix lignes, et les
    nouveautés — ce qui fait APPARAÎTRE la fenêtre — passaient sous le pli.
    Annoncer « proposer une modification » à qui enregistre directement, ou
    séparer « créer » de « modifier » un compte, n'apprend rien à personne.
    Aucune porte n'est cachée : seule leur FORMULATION se regroupe.
    """
    user = user if user is not None else current_user()
    if user is None:
        return []

    accorde = {droit: a_le_droit(droit, user)
               for droit, _cle, _coul, _ic in PORTES}

    # Enregistrer directement couvre le fait de proposer : on ne dit pas les deux.
    fondus = set()
    if accorde.get("edit_carto"):
        fondus.add("propose_carto")
    # Créer ET modifier des comptes tiennent en une phrase.
    fusion_comptes = accorde.get("cree_comptes") and accorde.get("modifie_comptes")
    if fusion_comptes:
        fondus.add("modifie_comptes")

    ouvertes = [{"libelle": t(cle, lang), "couleur": couleur, "icone": icone}
                for cle, couleur, icone in PLANCHER]
    for droit, cle, couleur, icone in PORTES:
        if not accorde.get(droit) or droit in fondus:
            continue
        if droit == "cree_comptes" and fusion_comptes:
            cle, icone = "welcome.door.accounts_both", "fa-users-gear"
        ouvertes.append({"libelle": t(cle, lang), "couleur": couleur,
                         "icone": icone, "droit": droit})
    return ouvertes


# ⚠️ Les quatre clés sont écrites EN TOUTES LETTRES, et la phrase est résolue
# ici plutôt que dans le gabarit. Assembler la clé (un préfixe, puis le nom du
# palier) marchait, mais une clé assemblée échappe au contrôle de couverture
# de `tests/test_78_i18n_couverture.py` : le jour où un palier s'ajoute, sa
# phrase s'afficherait en clair, sous la forme de la clé brute, sans que rien
# ne le signale. Ce contrôle existe pour rompre ce silence — et il a d'abord
# attrapé la version assemblée, puis le présent commentaire lorsqu'il en
# citait la forme exacte : il lit aussi les commentaires.
PHRASE_PALIER = {
    "user":          "welcome.tier.user",
    "champion":      "welcome.tier.champion",
    "coordinateur":  "welcome.tier.coordinateur",
    "admin":         "welcome.tier.admin",
}


def _palier(user):
    """La famille du compte, pour la phrase d'accueil.

    `users.status` est un texte libre selon les instances : c'est
    `famille_statut` qui le ramène à l'un des quatre paliers, et c'est elle
    qu'il faut lire — pas une comparaison de chaîne.
    """
    return famille_statut(getattr(user, "status", None))


# ── Ce qui ATTEND la personne ──────────────────────────────────────────────

#: Combien de propositions on NOMME avant de dire « et n de plus ». La fenêtre
#: est large, pas haute : trois lignes passent, dix la feraient défiler — et
#: c'est la file d'examen qui est faite pour les lire toutes.
PROPOSITIONS_NOMMEES = 3


def _deux_files(user):
    """Les propositions EN ATTENTE que ce compte peut trancher, les deux files.

    ⚠️⚠️ MÊMES sources que le bandeau de la page Carte (`_examen_en_attente`) :
    `carto_sharing.propositions_a_examiner` ET
    `activite_propositions.propositions_a_examiner`. La fenêtre n'en lisait
    qu'UNE — un coordinateur pouvait donc lire « 2 à arbitrer » ici et « 5 »
    sur le bandeau, pour la même attente. Les deux fonctions rendent [] tout
    de suite pour qui ne tranche pas : le coût reste nul pour les autres
    paliers, et c'est ce qui permet de calculer ceci à chaque page.
    """
    if user is None:
        return [], []
    cartos, fiches = [], []
    try:
        from Code.routes.carto_sharing import propositions_a_examiner as _c
        cartos = list(_c(user))
    except Exception:
        pass
    try:
        from Code.routes.activite_propositions import propositions_a_examiner as _f
        fiches = list(_f(user))
    except Exception:
        pass
    return cartos, fiches


def _quand(cr):
    """L'horodatage de dépôt, quelle que soit la file.

    ⚠️ Les deux modèles ne nomment pas cette colonne pareil : `created_at` pour
    une proposition de carto, `submitted_at` pour une proposition de fiche.
    """
    return getattr(cr, "submitted_at", None) or getattr(cr, "created_at", None)


def propositions_recues(user=None, lang=None):
    """Les propositions qu'on attend de ce compte, NOMMÉES — pas comptées.

    Un chiffre n'apprend rien : il faut ouvrir la file pour savoir ce qu'on
    vient de recevoir. Chaque ligne dit qui a proposé, sur quelle carto, et ce
    que ça touche. La fenêtre rend `{n, lignes, reste, href}` ; `lignes` est
    vide pour qui ne tranche pas, et le gabarit ne rend alors aucune section.
    """
    user = user if user is not None else current_user()
    vide = {"n": 0, "lignes": [], "reste": 0, "cartos": 0,
            "href": "/activities/map"}
    if user is None:
        return vide

    cartos, fiches = _deux_files(user)
    if not cartos and not fiches:
        return vide

    brut = ([(cr, "carto") for cr in cartos] + [(cr, "fiche") for cr in fiches])
    # Le plus ANCIEN d'abord : c'est celui qui attend depuis le plus longtemps.
    brut.sort(key=lambda p: (_quand(p[0]) is None, _quand(p[0])))

    # ⚠️ Les auteurs en UNE requête. `cr.author` dans la boucle ferait un aller
    # par proposition, sur une fenêtre rendue à chaque page.
    noms = {}
    try:
        from Code.models.models import User as _U
        ids = {cr.author_id for cr, _g in brut if cr.author_id}
        if ids:
            for u in _U.query.filter(_U.id.in_(ids)).all():
                noms[u.id] = ((u.first_name or "").strip() + " "
                              + (u.last_name or "").strip()).strip() or u.email
    except Exception:
        pass

    lignes = []
    for cr, genre in brut[:PROPOSITIONS_NOMMEES]:
        if genre == "fiche":
            try:
                from Code.propositions_activite import gestes
                combien = len(gestes(cr))
            except Exception:
                combien = 0
            quoi = t('welcome.props_fiche', lang) % combien
        else:
            quoi = t('welcome.props_carto', lang)
        lignes.append({
            "genre": genre,
            "auteur": noms.get(cr.author_id) or t('welcome.props_anon', lang),
            "carto": (cr.entity.name if cr.entity else ""),
            "quoi": quoi,
        })

    return {"n": len(brut), "lignes": lignes,
            "reste": max(0, len(brut) - len(lignes)),
            "cartos": len({cr.entity_id for cr, _g in brut}),
            "href": "/activities/map"}


def attentes(user=None, lang=None):
    """Ce sur quoi on attend une action de ce compte, ou [].

    ⚠️ Les cartos qu'on vous PROPOSE ne sont pas ici : `entity_share_popup.html`
    s'ouvre juste après celle-ci et les annonce lui-même. Les répéter ferait dire
    deux fois la même chose à deux fenêtres qui s'enchaînent.

    ⚠️ Les propositions À TRANCHER n'y sont plus non plus : elles ont leur
    propre section, qui les NOMME (`propositions_recues`). Une ligne « 5
    propositions à arbitrer » au-dessus d'une section qui les liste redirait la
    même chose deux fois.

    ⚠️ Tout ce qui est ici se paie à CHAQUE page (la fenêtre est rendue même
    fermée, pour que sa réouverture n'ait pas besoin d'une seconde voie de
    rendu). D'où la règle : des COUNT indexés, et rien qui charge une table.
    """
    user = user if user is not None else current_user()
    if user is None:
        return []
    liste = []

    # ── Les décisions tombées sur VOS propositions, pas encore lues ────
    # ⚠️ Les DEUX files, là aussi : seule celle de la carto était comptée, et
    # une décision sur une proposition de FICHE ne s'annonçait donc nulle part
    # ici (sa pop-up dédiée la portait seule).
    n = 0
    for modele in _modeles_propositions():
        try:
            n += (modele.query
                  .filter(modele.author_id == user.id,
                          modele.status.in_(("approved", "rejected")),
                          modele.author_seen_at.is_(None))
                  .count())
        except Exception:
            pass
    if n:
        liste.append({"cle": "decisions", "n": n, "ton": "neutre",
                      "libelle": t('welcome.wait.decisions', lang),
                      "href": "/activities/map"})

    # ── Votre brouillon, pas encore envoyé ─────────────────────────────
    # Le geste le plus facile à oublier : on range trois modifications, on
    # change de page, et personne ne les examinera jamais.
    try:
        from Code.models.models import ActivityChangeRequest
        from Code.propositions_activite import gestes
        brouillons = (ActivityChangeRequest.query
                      .filter(ActivityChangeRequest.author_id == user.id,
                              ActivityChangeRequest.status == "draft")
                      .all())
        n = sum(len(gestes(cr)) for cr in brouillons)
        if n:
            liste.append({"cle": "brouillon", "n": n, "ton": "attention",
                          "libelle": t('welcome.wait.draft', lang),
                          "href": "/activities/view"})
    except Exception:
        pass

    # ── Les séances d'évaluation que VOUS tenez ────────────────────────
    # ⚠️ Un COUNT indexé (`date_prevue`), pas `_sessions_lisibles` : celui-ci
    # charge TOUTES les sessions pour un statut élevé, ce qui n'est pas une
    # requête à faire sur chaque page de l'application.
    try:
        from datetime import date, timedelta
        from Code.models.models import SessionEvaluation
        n = (SessionEvaluation.query
             .filter(SessionEvaluation.developpeur_user_id == user.id,
                     SessionEvaluation.statut == "prevue",
                     SessionEvaluation.date_prevue <= date.today() + timedelta(days=7))
             .count())
        if n:
            liste.append({"cle": "seances", "n": n, "ton": "neutre",
                          "libelle": t('welcome.wait.sessions', lang),
                          "href": "/competences/"})
    except Exception:
        pass

    return liste


def _modeles_propositions():
    """Les deux modèles de proposition, quand ils sont importables."""
    sortie = []
    for chemin in ("CartoChangeRequest", "ActivityChangeRequest"):
        try:
            import Code.models.models as m
            modele = getattr(m, chemin, None)
            if modele is not None:
                sortie.append(modele)
        except Exception:
            pass
    return sortie


# ── Déjà vue, ou non ───────────────────────────────────────────────────────

def signature_vue(user=None):
    """La signature des nouveautés que ce compte a déjà lues, ou None."""
    user = user if user is not None else current_user()
    if user is None:
        return None
    try:
        from Code.extensions import db
        from Code.models.models import WelcomeSeen
        ligne = db.session.get(WelcomeSeen, user.id)
        return ligne.signature if ligne else None
    except Exception:
        # Table absente sur une base ancienne : on ne bloque pas la page pour
        # autant, et on ne montre pas la fenêtre en boucle non plus.
        try:
            from Code.extensions import db
            db.session.rollback()
        except Exception:
            pass
        return None


def marquer_vue(user=None, signature=None):
    """Mémorise que ce compte a vu la fenêtre pour CES nouveautés."""
    from datetime import datetime

    user = user if user is not None else current_user()
    if user is None:
        return False
    if signature is None:
        signature = signature_nouveautes()
    try:
        from Code.extensions import db
        from Code.models.models import WelcomeSeen
        ligne = db.session.get(WelcomeSeen, user.id)
        if ligne is None:
            ligne = WelcomeSeen(user_id=user.id)
            db.session.add(ligne)
        ligne.signature = signature
        ligne.seen_at = datetime.utcnow()
        db.session.commit()
        return True
    except Exception:
        try:
            from Code.extensions import db
            db.session.rollback()
        except Exception:
            pass
        return False


def nouveautes(lang=None):
    """Les nouveautés dans la langue du LECTEUR, pour l'affichage.

    (La signature, elle, se calcule sur les champs non traduits : voir
    `signature_nouveautes`.)
    """
    try:
        from Code.routes.changelog import _read_curated
        cure = _read_curated()
        return (cure or {}).get("items") or []
    except Exception:
        return []


def etat(user=None, lang=None):
    """Tout ce que le gabarit a besoin de savoir, en une lecture.

    ⚠️ Le CONTENU est toujours calculé, `montrer` ne décide que de la visibilité
    à l'arrivée. C'est ce qui permet au bouton de réouverture de ne rien
    re-rendre : sans cela, il faudrait une seconde voie de rendu en JavaScript,
    donc deux jeux de libellés à tenir — et c'est exactement par là que les
    phrases en dur rentrent dans un gabarit bilingue.

    Le coût reste modeste : `propositions_a_examiner` rend [] tout de suite
    pour qui ne tranche pas, et le compte des décisions est un COUNT indexé.
    """
    user = user if user is not None else current_user()
    if user is None:
        return {"montrer": False, "signature": "", "portes": [], "attentes": [],
                "propositions": {"n": 0, "lignes": [], "reste": 0, "cartos": 0,
                                 "href": "/activities/map"},
                "nouveautes": [], "palier": None, "prenom": ""}

    signature = signature_nouveautes()
    deja = signature_vue(user)
    # Rien de neuf depuis la dernière lecture → rien à annoncer. Une signature
    # vide (fichier illisible) ne fait PAS revenir la fenêtre.
    montrer = signature != "" and signature != deja

    palier = _palier(user)
    return {
        "montrer": montrer,
        "signature": signature,
        "portes": portes_ouvertes(user, lang),
        "attentes": attentes(user, lang),
        "propositions": propositions_recues(user, lang),
        "nouveautes": nouveautes(lang),
        "palier": palier,
        "phrase_palier": t(PHRASE_PALIER.get(palier, "welcome.tier.user"), lang),
        "prenom": (getattr(user, "first_name", "") or "").strip(),
    }
