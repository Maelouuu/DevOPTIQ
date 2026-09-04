# -*- coding: utf-8 -*-
"""Pont vers le panel de tests de l'instance staging.

Le navigateur ne peut pas interroger l'application depuis le hub (deux
domaines, aucun en-tête CORS) : c'est donc le hub qui appelle, côté serveur,
et qui republie le résultat sous son propre domaine.

L'exécution réelle a lieu SUR l'instance : elle embarque la suite et la lance
dans un sous-processus, sur une base SQLite jetable — jamais sur la base de
l'application. Aucun jeton, aucun service tiers.
"""
import json
import os
import urllib.error
import urllib.request

import inventaire

DELAI = 25          # s — le catalogue (70 pages) demande plus qu'un ping


def _base():
    """URL de l'instance qui héberge le panel (staging).

    PANEL_BASE permet de viser une autre instance — une app lancée en local
    pendant la mise au point, par exemple.
    """
    forcee = os.environ.get("PANEL_BASE", "").strip()
    if forcee:
        return forcee.rstrip("/")
    for i in inventaire.INSTANCES:
        if i["cle"] == "staging":
            return i["url"].rstrip("/")
    return ""


def _appel(chemin, methode="GET", delai=DELAI):
    url = _base() + chemin
    req = urllib.request.Request(url, method=methode,
                                 headers={"User-Agent": "OptiqHub/1.0",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            brut = r.read()
            return json.loads(brut) if brut else {}
    except urllib.error.HTTPError as e:
        return {"erreur": "http_%d" % e.code}
    except Exception:
        return {"erreur": "injoignable"}


def etat():
    """Ce que le hub doit savoir avant de proposer un lancement."""
    return _appel("/testpanel/api/etat")


def pages():
    """Catalogue des pages de tests avec leur fiabilité."""
    return _appel("/testpanel/api/pages", delai=40)


def page(slug):
    return _appel("/testpanel/api/page/" + slug, delai=30)


def lancer(portee="all"):
    """Démarre une exécution. `portee` : 'all' ou 'page:<slug>'.

    Renvoie (ok, charge). L'instance répond immédiatement avec un `run_id` ;
    la suite tourne en tâche de fond et se suit via `statut()`.
    """
    if portee.startswith("page:"):
        chemin = "/testpanel/run/page/" + portee[5:]
    else:
        chemin = "/testpanel/run/all"
    d = _appel(chemin, methode="POST", delai=30)
    if d.get("erreur"):
        messages = {
            "injoignable": "L'instance staging ne répond pas — elle démarre "
                           "peut-être à froid, réessayez dans une minute.",
            "http_404": "Le panel de tests n'est pas actif sur cette instance.",
        }
        return False, {"message": messages.get(d["erreur"],
                                               "L'instance a répondu : %s." % d["erreur"])}
    if not d.get("run_id"):
        return False, {"message": "Réponse inattendue de l'instance."}
    return True, {"run_id": d["run_id"]}


def statut(run_id):
    return _appel("/testpanel/run/%d/status" % int(run_id), delai=20)


def url_panel():
    """Le panel d'origine, pour les écrans que le hub ne reprend pas."""
    return _base() + "/testpanel/"
