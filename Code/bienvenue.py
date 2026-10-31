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

def attentes(user=None, lang=None):
    """Ce sur quoi on attend une action de ce compte, ou [].

    ⚠️ Les cartos qu'on vous PROPOSE ne sont pas ici : `entity_share_popup.html`
    s'ouvre juste après celle-ci et les annonce lui-même. Les répéter ferait dire
    deux fois la même chose à deux fenêtres qui s'enchaînent.
    """
    user = user if user is not None else current_user()
    if user is None:
        return []
    liste = []

    # Les propositions à trancher — MÊME source que le bandeau de la page Carte
    # (`propositions_a_examiner`), pour que les deux chiffres ne divergent pas.
    try:
        from Code.routes.carto_sharing import propositions_a_examiner
        n = len(propositions_a_examiner(user))
        if n:
            liste.append({"cle": "arbitrer", "n": n, "ton": "attention",
                          "libelle": t('welcome.wait.review', lang),
                          "href": "/activities/map"})
    except Exception:
        pass

    # Les décisions tombées sur VOS propositions, pas encore lues.
    try:
        from Code.models.models import CartoChangeRequest
        n = (CartoChangeRequest.query
             .filter(CartoChangeRequest.author_id == user.id,
                     CartoChangeRequest.status.in_(("approved", "rejected")),
                     CartoChangeRequest.author_seen_at.is_(None))
             .count())
        if n:
            liste.append({"cle": "decisions", "n": n, "ton": "neutre",
                          "libelle": t('welcome.wait.decisions', lang),
                          "href": "/activities/map"})
    except Exception:
        pass

    return liste


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
        "nouveautes": nouveautes(lang),
        "palier": palier,
        "phrase_palier": t(PHRASE_PALIER.get(palier, "welcome.tier.user"), lang),
        "prenom": (getattr(user, "first_name", "") or "").strip(),
    }
