# -*- coding: utf-8 -*-
"""Optiq Hub — point d'entrée unique de l'écosystème DevOPTIQ / OptiqFluent.

Une page par sujet (instances, infrastructure, documentation, outils, CI) :
un hub sert à retrouver vite, pas à faire défiler un fourre-tout.

Accès verrouillé par compte unique : le hub nomme les bases, les secrets et
les instances internes.
"""
import concurrent.futures as futures
import hmac
import os
import secrets
import socket
import time
import urllib.error
import urllib.request
from datetime import timedelta
from functools import wraps

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash

import inventaire
import panel_client

_HERE = os.path.dirname(os.path.abspath(__file__))
_DOCS = os.path.join(_HERE, "_docs")

app = Flask(__name__, template_folder=os.path.join(_HERE, "templates"),
            static_folder=os.path.join(_HERE, "static"))
app.secret_key = os.getenv("HUB_SECRET_KEY") or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=12)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.getenv("HUB_INSECURE_COOKIE") != "1")

HUB_USER = os.getenv("HUB_USER", "Mael_Girardin")
_DEFAULT_HASH = ("pbkdf2:sha256:600000$9Qza0VOKPsgnMmah$"
                 "9941d508368cfd0acff7115beb3189a6fd655862c9796426ea47d4e9b3760907")

# Le hub n'est plus à une seule personne. Chaque compte porte un HASH, jamais un
# mot de passe en clair : le dépôt n'a pas à contenir de quoi se connecter.
# Chacun reste remplaçable par une variable d'environnement, pour qu'on puisse
# tourner un mot de passe sans toucher au code ni redéployer une image modifiée.
_COMPTES = (
    (HUB_USER, "HUB_PASSWORD", "HUB_PASSWORD_HASH", _DEFAULT_HASH),
    ("Hubert_Grandjean", "HUB_PASSWORD_HG", "HUB_PASSWORD_HASH_HG",
     "pbkdf2:sha256:600000$V8nNjOiw2deXzKRt$"
     "9e57de85d70d352a66b2b3fcc2acc9806ce1afed6813b0f8a4e21790bdb31bba"),
)

_ATTEMPTS = {}
_MAX_TRIES, _LOCK_WINDOW_S = 8, 900


def _check_credentials(username, password):
    """⚠️ On compare TOUS les comptes, sans court-circuit sur le nom.

    Sortir dès que l'identifiant ne correspond pas rend la réponse plus rapide
    pour un nom inconnu que pour un nom connu : de quoi énumérer les comptes au
    chronomètre. On vérifie donc chaque ligne jusqu'au bout.
    """
    trouve = False
    for nom, var_clair, var_hash, defaut in _COMPTES:
        bon_nom = hmac.compare_digest(username or "", nom)
        clair = os.getenv(var_clair)
        if clair:
            bon_mdp = hmac.compare_digest(password or "", clair)
        else:
            bon_mdp = check_password_hash(os.getenv(var_hash) or defaut,
                                          password or "")
        trouve = trouve or (bon_nom and bon_mdp)
    return trouve


def _rate_limited(ip):
    now = time.time()
    tries = [t for t in _ATTEMPTS.get(ip, []) if now - t < _LOCK_WINDOW_S]
    _ATTEMPTS[ip] = tries
    return len(tries) >= _MAX_TRIES


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("auth"):
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("login", suite=request.path))
        return fn(*args, **kwargs)
    return wrapper


@app.after_request
def _headers(resp):
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


_TOILES = os.path.join(_HERE, "static", "toiles")
_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".avif")


def toiles_disponibles():
    """Nom de fichier de la toile de chaque section, quand elle existe.

    Relu à chaque rendu : déposer une image la met en ligne au redéploiement
    suivant, sans toucher au code. Une section sans fichier garde la bannière
    peinte — c'est le repli, jamais une page cassée.
    """
    trouvees = {}
    try:
        fichiers = os.listdir(_TOILES)
    except OSError:
        return trouvees
    for f in fichiers:
        base, ext = os.path.splitext(f)
        if ext.lower() in _EXTENSIONS:
            trouvees.setdefault(base, f)
    return trouvees


@app.context_processor
def _commun():
    """`inv`, `page_active` et les toiles disponibles, dans tous les gabarits."""
    return {"inv": inventaire, "page_active": request.endpoint,
            "toiles": toiles_disponibles()}


# ── État des instances ────────────────────────────────────────────────────
# Sondé côté serveur : le navigateur ne peut pas interroger un autre domaine.
_CACHE = {"ts": 0.0, "etats": {}}
_TTL_S = 25


# Un service Cloud Run redescend à zéro instance : la première requête doit
# attendre son réveil. Mesuré : 15,2 s pour devoptiq-staging (démarrage lourd —
# create_all + migrations à chaud, --cpu 2), 8,9 s pour optiqfluent-staging.
# En deçà, la sonde déclarait « injoignable » des services parfaitement en ligne.
_DELAI_SONDE_S = 28


def _sonder(instance):
    url = instance["url"].rstrip("/") + instance.get("sonde", "/")
    debut = time.perf_counter()
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "OptiqHub/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_DELAI_SONDE_S) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code            # le service répond : c'est ce qui compte
    except (socket.timeout, TimeoutError):
        # Le service dort, il ne casse pas : on ne crie pas à la panne.
        return {"etat": "en veille", "code": None,
                "ms": int((time.perf_counter() - debut) * 1000)}
    except Exception as exc:
        if isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
            return {"etat": "en veille", "code": None,
                    "ms": int((time.perf_counter() - debut) * 1000)}
        return {"etat": "injoignable", "code": None, "ms": None}
    ms = int((time.perf_counter() - debut) * 1000)
    etat = "en ligne" if code < 400 else ("dégradé" if code < 500 else "en erreur")
    return {"etat": etat, "code": code, "ms": ms}


def etats_instances(force=False):
    if not force and time.time() - _CACHE["ts"] < _TTL_S and _CACHE["etats"]:
        return _CACHE["etats"]
    etats = {}
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        travaux = {pool.submit(_sonder, i): i["cle"] for i in inventaire.INSTANCES}
        for f in futures.as_completed(travaux):
            try:
                etats[travaux[f]] = f.result()
            except Exception:
                etats[travaux[f]] = {"etat": "injoignable", "code": None, "ms": None}
    _CACHE.update(ts=time.time(), etats=etats)
    return etats


# ── Connexion ─────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    erreur = None
    suite = request.args.get("suite") or request.form.get("suite") or "/"
    if not suite.startswith("/"):
        suite = "/"
    if request.method == "POST":
        ip = request.headers.get("X-Forwarded-For",
                                 request.remote_addr or "?").split(",")[0].strip()
        if _rate_limited(ip):
            erreur = "Trop de tentatives. Réessayez dans un quart d'heure."
        elif _check_credentials(request.form.get("username"), request.form.get("password")):
            session.clear()
            session.permanent = True
            session["auth"] = True
            return redirect(suite)
        else:
            _ATTEMPTS.setdefault(ip, []).append(time.time())
            erreur = "Identifiants incorrects."
    return render_template("login.html", erreur=erreur, suite=suite)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Pages ─────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def accueil():
    return render_template("accueil.html", etats=etats_instances())


@app.route("/instances")
@login_required
def instances():
    return render_template("instances.html", etats=etats_instances())


@app.route("/infrastructure")
@login_required
def infrastructure():
    return render_template("infrastructure.html", etats=etats_instances())


@app.route("/documentation")
@login_required
def documentation():
    return render_template("documentation.html")


@app.route("/outils")
@login_required
def outils():
    return render_template("outils.html")


# ── Module Panel de tests ─────────────────────────────────────────────────
# Remplace l'ancienne page /tests, qui déclenchait la suite via GitHub Actions
# et exigeait un jeton personnel : l'instance embarque désormais la suite et
# la rejoue elle-même, sans service tiers ni secret.
# Le panel vit dans l'application (c'est elle qui possède les fichiers de test
# et qui sait les exécuter). Le hub en republie les données sous son domaine :
# le navigateur ne peut pas appeler l'instance directement, faute de CORS.

@app.route("/panel")
@login_required
def panel():
    # ⚠️ La route n'interroge PLUS l'instance. Elle le faisait pour deux
    # nombres (cas et pages) et bloquait le rendu du HTML le temps d'un appel
    # inter-services — 25 s d'attente, puis un dépassement de délai, puis une
    # page qui s'affichait en annonçant « l'instance ne répond pas ». Le
    # squelette part immédiatement ; les chiffres arrivent par `/api/panel/*`.
    return render_template("panel.html", url_panel=panel_client.url_panel())


@app.route("/panel/<slug>")
@login_required
def panel_page(slug):
    donnees = panel_client.page(slug)
    if donnees.get("erreur"):
        abort(502)
    return render_template("panel_page.html", page=donnees,
                           url_panel=panel_client.url_panel())


@app.route("/api/panel/pages")
@login_required
def api_panel_pages():
    return jsonify(panel_client.pages())


@app.route("/api/panel/runs")
@login_required
def api_panel_runs():
    """L'historique des exécutions, republié sous le domaine du hub."""
    return jsonify(panel_client.runs(request.args.get("limit", 20, type=int)))


@app.route("/api/panel/etat")
@login_required
def api_panel_etat():
    """Sert surtout à retrouver une exécution DÉJÀ en cours : en rouvrant la
    page pendant que la suite tourne, on ne voyait rien et on relançait."""
    return jsonify(panel_client.etat())


@app.route("/api/panel/page/<slug>")
@login_required
def api_panel_page(slug):
    return jsonify(panel_client.page(slug))


@app.route("/api/panel/lancer", methods=["POST"])
@login_required
def api_panel_lancer():
    portee = (request.get_json(silent=True) or {}).get("portee", "all")
    ok, charge = panel_client.lancer(portee)
    return jsonify(dict(charge, ok=ok)), (200 if ok else 502)


@app.route("/api/panel/run/<int:run_id>")
@login_required
def api_panel_run(run_id):
    return jsonify(panel_client.statut(run_id))


@app.route("/ci")
@login_required
def ci():
    return render_template("ci.html")


@app.route("/api/etat")
@login_required
def api_etat():
    return jsonify(etats_instances(force=request.args.get("force") == "1"))


# ── Documents servis ──────────────────────────────────────────────────────
@app.route("/doc")
@login_required
def doc_technique():
    return send_from_directory(_DOCS, "doc_technique.html")


@app.route("/guide")
@login_required
def guide():
    return send_from_directory(_DOCS, "guide.html")


@app.route("/doc/refonte")
@login_required
def doc_refonte():
    chemin = os.path.join(_DOCS, "refonte_competences_v1_1.md")
    if not os.path.exists(chemin):
        abort(404)
    with open(chemin, encoding="utf-8") as f:
        return render_template("markdown.html", titre="Refonte Compétences V1.1",
                               contenu=f.read())


@app.route("/assets/<path:chemin>")
@login_required
def assets(chemin):
    """Médias du guide (docs/assets/…) : le guide y renvoie en relatif."""
    return send_from_directory(os.path.join(_DOCS, "assets"), chemin)


@app.route("/health")
def health():
    # /health et PAS /healthz : ce dernier est intercepté par le frontend
    # Google sur *.run.app (404 avant d'atteindre le conteneur).
    return "ok", 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", 8080)), debug=True)
