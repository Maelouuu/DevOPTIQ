# -*- coding: utf-8 -*-
"""Pont vers GitHub Actions : lancer la suite de tests et lire les résultats.

Pourquoi passer par la CI plutôt que par l'application déployée : `.dockerignore`
exclut `tests/` de l'image, l'app en ligne n'embarque donc PAS la suite et ne
peut pas lancer pytest. Le workflow `tests.yml` l'exécute sur un runner, et le
hub le déclenche puis suit son avancement.

Sans jeton (`HUB_GITHUB_TOKEN`), tout se dégrade proprement : la lecture des
exécutions passe en anonyme si le dépôt est public, et le lancement est refusé
avec un message qui dit quoi configurer — jamais une erreur muette.
"""
import json
import os
import urllib.error
import urllib.request

DEPOT = os.getenv("HUB_GITHUB_REPO", "Maelouuu/DevOPTIQ")
WORKFLOW = os.getenv("HUB_TESTS_WORKFLOW", "tests.yml")
BRANCHE = os.getenv("HUB_TESTS_REF", "staging")
API = "https://api.github.com"


def jeton():
    return (os.getenv("HUB_GITHUB_TOKEN") or "").strip()


def _appel(chemin, methode="GET", corps=None):
    req = urllib.request.Request(API + chemin, method=methode)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "OptiqHub/1.0")
    t = jeton()
    if t:
        req.add_header("Authorization", "Bearer " + t)
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, donnees, timeout=20) as r:
        brut = r.read()
        return r.status, (json.loads(brut) if brut else {})


def _etat_lisible(run):
    """Traduit statut + conclusion GitHub en un mot affichable."""
    statut = run.get("status")
    if statut in ("queued", "waiting", "requested", "pending"):
        return "en attente"
    if statut == "in_progress":
        return "en cours"
    return {"success": "succès", "failure": "échec", "cancelled": "annulé",
            "timed_out": "expiré", "skipped": "ignoré",
            "startup_failure": "échec"}.get(run.get("conclusion"), "terminé")


def executions(limite=8):
    """Dernières exécutions du workflow de tests."""
    try:
        _, d = _appel(f"/repos/{DEPOT}/actions/workflows/{WORKFLOW}/runs?per_page={limite}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"erreur": "workflow_absent", "runs": []}
        return {"erreur": "http_%d" % e.code, "runs": []}
    except Exception:
        return {"erreur": "reseau", "runs": []}

    runs = []
    for r in d.get("workflow_runs", []):
        runs.append({
            "id": r.get("id"),
            "numero": r.get("run_number"),
            "etat": _etat_lisible(r),
            "statut": r.get("status"),
            "conclusion": r.get("conclusion"),
            "branche": r.get("head_branch"),
            "commit": (r.get("head_sha") or "")[:8],
            "titre": (r.get("display_title") or "").strip(),
            "declenche": r.get("event"),
            "debut": r.get("run_started_at"),
            "fin": r.get("updated_at"),
            "url": r.get("html_url"),
        })
    return {"erreur": None, "runs": runs}


def lancer(filtre=""):
    """Déclenche le workflow. Renvoie (ok, message)."""
    if not jeton():
        return False, ("Jeton GitHub absent : posez le secret HUB_GITHUB_TOKEN "
                       "(droit Actions en écriture) puis relancez le déploiement du hub.")
    try:
        code, _ = _appel(
            f"/repos/{DEPOT}/actions/workflows/{WORKFLOW}/dispatches",
            methode="POST",
            corps={"ref": BRANCHE, "inputs": {"filtre": filtre or ""}},
        )
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, "Jeton refusé par GitHub (droit « Actions : write » requis)."
        if e.code == 404:
            return False, f"Workflow {WORKFLOW} introuvable sur la branche {BRANCHE}."
        if e.code == 422:
            return False, "GitHub refuse le déclenchement : le workflow doit exister sur la branche visée."
        return False, "GitHub a répondu %d." % e.code
    except Exception:
        return False, "GitHub injoignable depuis le hub."
    if code == 204:
        return True, "Exécution demandée. Elle apparaît dans la liste sous quelques secondes."
    return False, "Réponse inattendue de GitHub (%s)." % code
