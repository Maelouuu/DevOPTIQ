# -*- coding: utf-8 -*-
"""Atelier — le plan de travail personnel du hub, et sa persistance.

L'atelier est une toile infinie : des notes, des listes à cocher, des captures,
des liens, et des MAQUETTES de pages de l'application sur lesquelles on vient
accrocher les fonctionnalités. Tout ça vit dans un seul document JSON par toile.

⚠️ **Le navigateur est la source de vérité pendant qu'on travaille.** La toile
est écrite dans IndexedDB à chaque geste : c'est instantané, ça survit à une
coupure réseau, et ça ne dépend d'aucun secret. Ce module n'est que le MIROIR
durable — il rend la toile lisible depuis un autre poste, et il la garde si le
profil du navigateur disparaît.

⚠️ **Sans `HUB_ATELIER_DB`, l'atelier marche quand même**, entièrement en local.
C'est voulu : un outil de travail qui exige un secret avant d'écrire la première
note n'est pas un outil de travail. La page le dit, propose la sauvegarde par
fichier, et le miroir s'allume le jour où la base est posée.

⚠️ Aucune base d'instance n'est touchée ici. `HUB_DBS_B64` est en LECTURE SEULE
(voir `courrier.py`) ; l'atelier écrit, il lui faut donc une base à lui, nommée
par sa propre variable. Mélanger les deux ferait écrire le hub dans la base d'un
client sur une faute de frappe.
"""
import base64
import json
import os
import re
import threading
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

# Une toile de 24 Mo, c'est déjà des centaines de notes et des dizaines de
# captures. Au-delà, c'est un emballement (boucle d'enregistrement, collage en
# rafale) : mieux vaut refuser que gonfler la base sans fin.
TAILLE_MAX = 24 * 1024 * 1024
# Une capture réduite côté navigateur pèse 100 à 300 Ko. 8 Mo laisse passer une
# image non réduite sans ouvrir la porte à un envoi de plusieurs dizaines de Mo.
PIECE_MAX = 8 * 1024 * 1024

_CLE_OK = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_verrou = threading.Lock()
_moteur = None
_prepare = False


def url_base(env=None):
    """L'URL de la base de l'atelier, pilote nommé, ou `""`.

    ⚠️ Lu avec `or` et jamais par le défaut de `getenv` : une variable
    d'environnement PRÉSENTE ET VIDE rend `""`, et `getenv` ne regarde alors
    jamais son défaut. Même piège que les identifiants IMAP de `courrier.py`.
    """
    env = env if env is not None else os.environ
    url = (env.get("HUB_ATELIER_DB") or "").strip().strip('"').strip("'")
    if not url:
        return ""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # ⚠️ Le pilote est NOMMÉ, jamais laissé au défaut de SQLAlchemy — même
    # raison que dans `courrier.py` : `postgresql://` seul a changé de pilote
    # entre 2.0 et 2.1, et toute lecture est morte sans qu'un commit ne change.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def disponible(env=None):
    return bool(url_base(env))


# ── Schéma ────────────────────────────────────────────────────────────────
# Deux tables, et du TEXT partout : les captures sont gardées en data-URL
# plutôt qu'en binaire pour que le même DDL passe sur PostgreSQL et sur SQLite
# (les tests tournent sur SQLite, et un schéma qui diverge n'est plus testé).

_DDL = (
    """CREATE TABLE IF NOT EXISTS hub_atelier_toile (
         cle      VARCHAR(64) PRIMARY KEY,
         rev      INTEGER NOT NULL,
         maj      VARCHAR(40),
         contenu  TEXT
       )""",
    """CREATE TABLE IF NOT EXISTS hub_atelier_piece (
         id       VARCHAR(64) PRIMARY KEY,
         mime     VARCHAR(80),
         donnees  TEXT,
         cree     VARCHAR(40)
       )""",
)


def _eng(env=None):
    """Le moteur, créé une seule fois. `None` si aucune base n'est configurée."""
    global _moteur, _prepare
    url = url_base(env)
    if not url:
        return None
    with _verrou:
        if _moteur is None:
            _moteur = create_engine(url, pool_size=2, max_overflow=2,
                                    pool_pre_ping=True, pool_recycle=280,
                                    future=True)
        if not _prepare:
            with _moteur.begin() as cx:
                for ddl in _DDL:
                    cx.exec_driver_sql(ddl)
            _prepare = True
    return _moteur


def _oublier():
    """Repart d'un moteur neuf. Sert aux tests, qui changent de base."""
    global _moteur, _prepare
    with _verrou:
        if _moteur is not None:
            try:
                _moteur.dispose()
            except Exception:
                pass
        _moteur, _prepare = None, False


def _maintenant():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── La toile ──────────────────────────────────────────────────────────────

def lire(cle="principale", env=None):
    """La toile enregistrée, ou un miroir vide.

    Rend toujours un dictionnaire. `miroir` dit si une base répond : le
    navigateur doit pouvoir distinguer « rien d'enregistré là-bas » de « pas
    de miroir du tout », pour ne pas écraser une toile locale bien vivante
    avec le vide d'une base injoignable.
    """
    if not _CLE_OK.match(cle or ""):
        return {"miroir": False, "erreur": "clé de toile invalide",
                "rev": 0, "contenu": None}
    try:
        # ⚠️ `_eng` crée le moteur ET joue le DDL : il peut échouer (base
        # injoignable, droits manquants). Dans le try, donc — sinon la page
        # entière rend 500 là où un « miroir indisponible » suffit.
        eng = _eng(env)
        if eng is None:
            return {"miroir": False, "erreur": None, "rev": 0, "contenu": None}
        with eng.connect() as cx:
            ligne = cx.execute(
                text("SELECT rev, contenu, maj FROM hub_atelier_toile "
                     "WHERE cle = :c"), {"c": cle}).fetchone()
    except Exception as e:
        return {"miroir": False, "erreur": str(e).split("\n")[0][:200],
                "rev": 0, "contenu": None}
    if ligne is None:
        return {"miroir": True, "erreur": None, "rev": 0, "contenu": None,
                "maj": None}
    return {"miroir": True, "erreur": None, "rev": int(ligne[0] or 0),
            "contenu": ligne[1], "maj": ligne[2]}


def ecrire(cle, contenu, rev=None, env=None):
    """Enregistre la toile et rend la révision obtenue.

    ⚠️ `rev` n'est pas un verrou, c'est un GARDE-FOU : un seul compte écrit
    ici, mais deux onglets du même navigateur sont vite ouverts. Une écriture
    qui part d'une révision plus ancienne que celle en base est refusée, et
    l'appelant reçoit la version en place pour décider — plutôt qu'une toile
    silencieusement remplacée par un onglet oublié.
    """
    if not _CLE_OK.match(cle or ""):
        return {"ok": False, "erreur": "clé de toile invalide"}
    if not isinstance(contenu, str):
        contenu = json.dumps(contenu, ensure_ascii=False)
    if len(contenu.encode("utf-8")) > TAILLE_MAX:
        return {"ok": False, "erreur": "toile trop lourde (%d Mo max)"
                                       % (TAILLE_MAX // (1024 * 1024))}
    try:
        eng = _eng(env)
        if eng is None:
            return {"ok": False, "miroir": False, "erreur": None}
        with eng.begin() as cx:
            actuel = cx.execute(
                text("SELECT rev FROM hub_atelier_toile WHERE cle = :c"),
                {"c": cle}).fetchone()
            en_place = int(actuel[0]) if actuel else 0
            if rev is not None and int(rev) < en_place:
                return {"ok": False, "conflit": True, "rev": en_place,
                        "erreur": "une version plus récente est enregistrée"}
            neuve = en_place + 1
            params = {"c": cle, "r": neuve, "m": _maintenant(), "t": contenu}
            if actuel:
                cx.execute(text("UPDATE hub_atelier_toile "
                                "SET rev = :r, maj = :m, contenu = :t "
                                "WHERE cle = :c"), params)
            else:
                # Pas d'UPSERT : la syntaxe diffère entre PostgreSQL et SQLite,
                # et le tour UPDATE-puis-INSERT tient dans la transaction.
                cx.execute(text("INSERT INTO hub_atelier_toile "
                                "(cle, rev, maj, contenu) "
                                "VALUES (:c, :r, :m, :t)"), params)
    except Exception as e:
        return {"ok": False, "erreur": str(e).split("\n")[0][:200]}
    return {"ok": True, "miroir": True, "rev": neuve, "erreur": None}


# ── Les pièces (captures collées) ─────────────────────────────────────────
# Une capture est IMMUABLE : on l'envoie une fois, jamais deux. C'est tout
# l'intérêt de les sortir du document — sans ça, chaque enregistrement
# repousserait plusieurs méga-octets d'images inchangées.

def pieces_connues(ids, env=None):
    ids = [i for i in (ids or []) if _CLE_OK.match(str(i or ""))][:400]
    if not ids:
        return []
    marques = ", ".join(":p%d" % n for n in range(len(ids)))
    params = {"p%d" % n: v for n, v in enumerate(ids)}
    try:
        eng = _eng(env)
        if eng is None:
            return []
        with eng.connect() as cx:
            lignes = cx.execute(text("SELECT id FROM hub_atelier_piece "
                                     "WHERE id IN (%s)" % marques), params)
            return [l[0] for l in lignes]
    except Exception:
        return []


def piece_ecrire(ident, mime, donnees, env=None):
    if not _CLE_OK.match(str(ident or "")):
        return {"ok": False, "erreur": "identifiant de pièce invalide"}
    if not isinstance(donnees, str) or not donnees:
        return {"ok": False, "erreur": "pièce vide"}
    if len(donnees.encode("utf-8")) > PIECE_MAX:
        return {"ok": False, "erreur": "pièce trop lourde (%d Mo max)"
                                       % (PIECE_MAX // (1024 * 1024))}
    try:
        eng = _eng(env)
        if eng is None:
            return {"ok": False, "miroir": False, "erreur": None}
        with eng.begin() as cx:
            deja = cx.execute(text("SELECT 1 FROM hub_atelier_piece "
                                   "WHERE id = :i"), {"i": ident}).fetchone()
            if deja:
                return {"ok": True, "deja": True}
            cx.execute(text("INSERT INTO hub_atelier_piece "
                            "(id, mime, donnees, cree) "
                            "VALUES (:i, :m, :d, :c)"),
                       {"i": ident, "m": (mime or "image/png")[:80],
                        "d": donnees, "c": _maintenant()})
    except Exception as e:
        return {"ok": False, "erreur": str(e).split("\n")[0][:200]}
    return {"ok": True, "deja": False}


def piece_lire(ident, env=None):
    if not _CLE_OK.match(str(ident or "")):
        return None
    try:
        eng = _eng(env)
        if eng is None:
            return None
        with eng.connect() as cx:
            ligne = cx.execute(
                text("SELECT mime, donnees FROM hub_atelier_piece "
                     "WHERE id = :i"), {"i": ident}).fetchone()
    except Exception:
        return None
    if ligne is None:
        return None
    return {"id": ident, "mime": ligne[0], "donnees": ligne[1]}


def piece_oublier(ident, env=None):
    """Retire une pièce dont plus aucune toile ne se sert."""
    if not _CLE_OK.match(str(ident or "")):
        return False
    try:
        eng = _eng(env)
        if eng is None:
            return False
        with eng.begin() as cx:
            cx.execute(text("DELETE FROM hub_atelier_piece WHERE id = :i"),
                       {"i": ident})
    except Exception:
        return False
    return True


def etat(env=None):
    """Ce que la page affiche en haut : miroir branché ou non, et sa taille."""
    if not disponible(env):
        return {"miroir": False, "erreur": None, "variable": "HUB_ATELIER_DB"}
    try:
        eng = _eng(env)
        if eng is None:
            return {"miroir": False, "erreur": None, "variable": "HUB_ATELIER_DB"}
        with eng.connect() as cx:
            toiles = cx.execute(
                text("SELECT COUNT(*) FROM hub_atelier_toile")).scalar() or 0
            pieces = cx.execute(
                text("SELECT COUNT(*) FROM hub_atelier_piece")).scalar() or 0
    except Exception as e:
        return {"miroir": False, "erreur": str(e).split("\n")[0][:200],
                "variable": "HUB_ATELIER_DB"}
    return {"miroir": True, "erreur": None, "toiles": int(toiles),
            "pieces": int(pieces), "variable": "HUB_ATELIER_DB"}


# Gardé pour les tests : vérifier qu'une data-URL est bien formée avant de la
# ranger évite de stocker une chaîne qu'aucun navigateur ne saura réafficher.
_DATA_URL = re.compile(r"^data:([\w.+-]+/[\w.+-]+);base64,([A-Za-z0-9+/=\s]+)$")


def data_url_valide(valeur):
    m = _DATA_URL.match(valeur or "")
    if not m:
        return False
    try:
        base64.b64decode(m.group(2), validate=False)
    except Exception:
        return False
    return True
