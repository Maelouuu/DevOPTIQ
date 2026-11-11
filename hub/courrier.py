# -*- coding: utf-8 -*-
"""Le courrier de l'adresse d'envoi, et ce que les demandes de reset racontent.

Deux sources, volontairement séparées : elles ne tombent pas en panne ensemble,
et l'écran doit pouvoir montrer l'une quand l'autre manque.

1. **Les chiffres** (`stats_reset`) — lecture SEULE de `password_resets` sur la
   base de chaque instance, par le même chemin que `pulse/` : les URL sont
   découvertes dans les specs Cloud Run par le workflow, jamais recopiées dans
   un secret. L'agrégation est 100 % Python, donc jouable sur SQLite en test.

   ⚠️ **Cette table ne porte que des EMPREINTES** de l'adresse saisie et de
   l'IP. On peut donc dire combien de demandes, quand, lesquelles ont abouti, et
   pour quel COMPTE (`user_id` est en clair) — jamais quelle adresse un inconnu
   a essayée. C'est voulu : une lecture de la base ne doit pas rendre la liste
   des adresses que quelqu'un a essayées. Rien ici ne doit sortir un hash.

   ⚠️ **Une instance peut ne pas avoir la table** : la réinitialisation n'est
   arrivée que sur staging et le pilote, `nouveau-point` a des dizaines de
   commits de retard. C'est un ÉTAT à afficher (« fonctionnalité absente »), pas
   une erreur à avaler.

2. **La boîte** (`boite`) — IMAP sur l'adresse d'envoi. C'est là qu'arrivent les
   REJETS, et c'est le seul endroit où l'on apprend qu'un mail de reset n'est
   PAS arrivé : les chiffres du point 1 disent qu'une demande a été faite, pas
   qu'elle a été reçue. Sans identifiants, cette moitié s'éteint proprement.
"""
import base64
import email
import imaplib
import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header

from sqlalchemy import create_engine, text


# ── Les bases suivies ─────────────────────────────────────────────────────
# Même forme que PULSE_DBS : [{name, url}], en clair ou en base64 (le base64
# évite tout échappement dans gcloud et toute fuite dans les journaux de CI).

def load_sources():
    brut = os.getenv("HUB_DBS", "").strip()
    if not brut:
        b64 = os.getenv("HUB_DBS_B64", "").strip()
        if b64:
            try:
                brut = base64.b64decode(b64).decode("utf-8")
            except Exception:
                return []
    if not brut:
        return []
    try:
        items = json.loads(brut)
    except Exception:
        return []
    out = []
    for it in items:
        url = (it.get("url") or "").strip()
        if not url:
            continue
        if url.startswith("postgres://"):      # Neon donne parfois l'ancien schéma
            url = "postgresql://" + url[len("postgres://"):]
        # ⚠️ Le pilote est NOMMÉ, jamais laissé au défaut de SQLAlchemy.
        # `postgresql://` seul désignait psycopg2 en 2.0 et désigne psycopg
        # (v3) depuis 2.1 : l'image du hub, construite sur une fourchette,
        # a pris 2.1.6 et chaque lecture est morte sur
        # « No module named 'psycopg' ». Invisible en local, où le venv est
        # resté en 2.0.45. Les versions sont épinglées à côté, mais une URL
        # qui dit son pilote ne dépend plus de ce que pip a installé.
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        out.append({"name": it.get("name") or "Instance", "url": url})
    return out


_MOTEURS = {}


def _moteur(url):
    eng = _MOTEURS.get(url)
    if eng is None:
        eng = create_engine(url, pool_size=2, max_overflow=2,
                            pool_pre_ping=True, pool_recycle=280)
        _MOTEURS[url] = eng
    return eng


def _lecture_seule(cx, url):
    """⚠️ Un filet, pas une politesse : ce code ouvre la base d'un CLIENT.

    Rien ici n'écrit, mais une faute de frappe dans un futur `text(...)` ne doit
    pas pouvoir toucher les données du pilote. Réservé à PostgreSQL — SQLite,
    qui sert aux tests, ne connaît pas cette instruction.
    """
    if url.startswith("postgresql"):
        cx.exec_driver_sql("SET TRANSACTION READ ONLY")


def _jour(valeur):
    """La date du jour d'une ligne. SQLite rend des chaînes, PostgreSQL des
    datetime : les deux passent ici."""
    if valeur is None:
        return None
    if isinstance(valeur, str):
        try:
            valeur = datetime.fromisoformat(valeur.split("+")[0])
        except ValueError:
            return None
    return valeur.date().isoformat()


# ── Les chiffres ──────────────────────────────────────────────────────────

def stats_une_base(url, jours=30, maintenant=None):
    """Les demandes de réinitialisation d'UNE instance, sur `jours` jours.

    Rend toujours un dictionnaire : `present` dit si la table existe, `erreur`
    pourquoi la lecture a échoué. Jamais d'exception vers l'appelant — une
    instance muette ne doit pas effacer les deux autres de l'écran.
    """
    vide = {"present": False, "erreur": None, "total": 0, "abouties": 0,
            "abandonnees": 0, "inconnues": 0, "comptes": [], "serie": [],
            "jours": jours}
    maintenant = maintenant or datetime.utcnow()
    depuis = maintenant - timedelta(days=jours)
    try:
        eng = _moteur(url)
        with eng.connect() as cx:
            _lecture_seule(cx, url)
            lignes = cx.execute(text(
                "SELECT r.user_id, r.cree_le, r.utilise_le, r.expire_le "
                "FROM password_resets r WHERE r.cree_le >= :depuis "
                "ORDER BY r.cree_le"), {"depuis": depuis}).fetchall()
            # Les noms des comptes concernés, en UNE requête : un SELECT par
            # ligne ferait autant d'allers à Neon que de demandes.
            ids = sorted({l[0] for l in lignes if l[0] is not None})
            noms = {}
            if ids:
                marques = ", ".join(":i%d" % n for n in range(len(ids)))
                params = {"i%d" % n: v for n, v in enumerate(ids)}
                for uid, prenom, nom, mail, langue in cx.execute(text(
                        "SELECT id, first_name, last_name, email, lang "
                        "FROM users WHERE id IN (%s)" % marques), params):
                    noms[uid] = {
                        "nom": (" ".join(x for x in (prenom, nom) if x)
                                or mail or "compte %s" % uid),
                        "email": mail or "",
                        "langue": (langue or "").strip().lower() or "?",
                    }
    except Exception as e:
        msg = str(e)
        # « relation "password_resets" does not exist » (PostgreSQL) ou
        # « no such table » (SQLite) : la fonctionnalité n'est pas déployée là.
        if re.search(r"password_resets.*does not exist|no such table", msg, re.I):
            return dict(vide, present=False)
        return dict(vide, present=False, erreur=msg.split("\n")[0][:200])

    serie = OrderedDict()
    for n in range(jours, -1, -1):
        serie[(maintenant - timedelta(days=n)).date().isoformat()] = 0

    par_compte = {}
    total = abouties = inconnues = 0
    for user_id, cree_le, utilise_le, _expire in lignes:
        total += 1
        j = _jour(cree_le)
        if j in serie:
            serie[j] += 1
        if utilise_le is not None:
            abouties += 1
        if user_id is None:
            inconnues += 1
            continue
        c = par_compte.setdefault(user_id, {"demandes": 0, "abouties": 0,
                                            "derniere": None})
        c["demandes"] += 1
        if utilise_le is not None:
            c["abouties"] += 1
        j_iso = _jour(cree_le)
        if j_iso and (c["derniere"] is None or j_iso > c["derniere"]):
            c["derniere"] = j_iso

    comptes = []
    for uid, c in par_compte.items():
        fiche = noms.get(uid) or {"nom": "compte %s" % uid, "email": "",
                                  "langue": "?"}
        comptes.append(dict(fiche, user_id=uid, **c))
    # Celui qui redemande le plus souvent d'abord : c'est lui qui a un problème.
    comptes.sort(key=lambda c: (-c["demandes"], c["nom"]))

    return {"present": True, "erreur": None, "total": total,
            "abouties": abouties, "abandonnees": total - abouties,
            "inconnues": inconnues, "comptes": comptes,
            "serie": [{"jour": j, "n": n} for j, n in serie.items()],
            "jours": jours}


def stats_reset(sources=None, jours=30, maintenant=None):
    """Les chiffres de toutes les instances suivies, en parallèle.

    ⚠️ En séquence, trois bases Neon froides font trois fois ~1 s : la page
    attendrait pour rien, puisque les lectures sont indépendantes.
    """
    from concurrent.futures import ThreadPoolExecutor
    sources = sources if sources is not None else load_sources()
    if not sources:
        return []
    with ThreadPoolExecutor(max_workers=max(1, len(sources))) as pool:
        resultats = list(pool.map(
            lambda s: dict(stats_une_base(s["url"], jours, maintenant),
                           nom=s["name"]),
            sources))
    return resultats


# ── La boîte de réception ─────────────────────────────────────────────────

_REJET_DE = re.compile(r"mailer-daemon|postmaster|mail delivery", re.I)
_REJET_SUJET = re.compile(
    r"undeliver|delivery status|delivery failure|mail delivery|returned mail|"
    r"address not found|adresse introuvable|échec de (?:la )?remise", re.I)
_AUTO_SUJET = re.compile(
    r"automatic reply|auto(?:matic)?[- ]?reply|out of office|"
    r"réponse automatique|absence du bureau", re.I)


def _texte(valeur):
    """Un en-tête MIME rendu lisible. Un sujet mal encodé ne doit pas faire
    tomber la lecture de toute la boîte."""
    if not valeur:
        return ""
    try:
        return str(make_header(decode_header(valeur)))
    except Exception:
        return valeur


def _nature(expediteur, sujet):
    if _REJET_DE.search(expediteur) or _REJET_SUJET.search(sujet):
        return "rejet"
    if _AUTO_SUJET.search(sujet):
        return "auto"
    return "reponse"


def boite(limite=25, serveur=None, env=None):
    """Les derniers messages reçus sur l'adresse d'envoi, les rejets d'abord.

    ⚠️ **Lecture stricte.** `select(readonly=True)` et `BODY.PEEK` : rien n'est
    marqué comme lu, rien n'est déplacé, rien n'est supprimé. Et seuls les
    EN-TÊTES sont téléchargés — ni corps, ni pièces jointes : on cherche à
    savoir ce qui est revenu, pas à lire le courrier de quelqu'un.

    ⚠️ Les identifiants sont lus avec `or` et jamais par le défaut de `getenv` :
    une variable d'environnement PRÉSENTE ET VIDE rend `""`, et `getenv` ne
    regarde alors jamais son défaut. C'est le défaut qui a fait croire pendant
    des mois que l'envoi de mail était configuré.
    """
    env = env if env is not None else os.environ
    user = (env.get("HUB_IMAP_USER") or "").strip()
    mdp = (env.get("HUB_IMAP_PASSWORD") or "").strip()
    hote = (serveur or env.get("HUB_IMAP_SERVER") or "imap.gmail.com").strip()
    if not (user and mdp):
        return {"configure": False, "adresse": user, "erreur": None,
                "messages": [], "compte": {}}

    messages = []
    cx = None
    try:
        cx = imaplib.IMAP4_SSL(hote, 993)
        cx.login(user, mdp)
        cx.select("INBOX", readonly=True)
        typ, data = cx.search(None, "ALL")
        if typ != "OK":
            raise RuntimeError("recherche IMAP refusée : %s" % typ)
        ids = (data[0] or b"").split()
        for ident in reversed(ids[-max(1, limite):]):
            typ, morceaux = cx.fetch(
                ident, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE TO)])")
            if typ != "OK":
                continue
            brut = b"".join(m[1] for m in morceaux
                            if isinstance(m, tuple) and m[1])
            tete = email.message_from_bytes(brut)
            expediteur = _texte(tete.get("From"))
            sujet = _texte(tete.get("Subject")) or "(sans objet)"
            messages.append({
                "de": expediteur,
                "sujet": sujet,
                "date": _texte(tete.get("Date")),
                "nature": _nature(expediteur, sujet),
            })
    except Exception as e:
        return {"configure": True, "adresse": user,
                "erreur": str(e).split("\n")[0][:200],
                "messages": [], "compte": {}}
    finally:
        if cx is not None:
            try:
                cx.logout()
            except Exception:
                pass

    # Les rejets d'abord : c'est la seule nature sur laquelle on agit.
    rang = {"rejet": 0, "reponse": 1, "auto": 2}
    messages.sort(key=lambda m: rang.get(m["nature"], 9))
    compte = {"rejet": 0, "reponse": 0, "auto": 0}
    for m in messages:
        compte[m["nature"]] = compte.get(m["nature"], 0) + 1
    return {"configure": True, "adresse": user, "erreur": None,
            "messages": messages, "compte": compte}


# ── Cache ─────────────────────────────────────────────────────────────────
# ⚠️ Une lecture IMAP demande deux à quatre secondes, et la page est rouverte
# souvent. Le cache est court : on vient y voir ce qui arrive MAINTENANT.

_CACHE = {}
_TTL = {"reset": 90, "boite": 120}


def _horloge():
    return datetime.now(timezone.utc).timestamp()


def cache(cle, calcul, force=False):
    entree = _CACHE.get(cle)
    if entree and not force and _horloge() - entree[0] < _TTL.get(cle, 60):
        return entree[1]
    valeur = calcul()
    _CACHE[cle] = (_horloge(), valeur)
    return valeur
