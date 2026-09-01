# -*- coding: utf-8 -*-
"""Optiq Hub — point d'entrée unique de l'écosystème DevOPTIQ / OptiqFluent.

Regroupe ce qui était éparpillé : les instances en ligne (avec leur état réel),
la documentation (servie ici, plus de fichier à retrouver), OptiqPulse, et le
catalogue des commandes qui s'exécutent en local.

Accès verrouillé par un compte unique : le hub nomme les bases, les secrets et
les instances internes — ce n'est pas une page publique.
"""
import concurrent.futures as futures
import hmac
import os
import secrets
import time
import urllib.error
import urllib.request
from datetime import timedelta
from functools import wraps

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash

import inventaire

_HERE = os.path.dirname(os.path.abspath(__file__))
_DOCS = os.path.join(_HERE, "_docs")

app = Flask(__name__, template_folder=os.path.join(_HERE, "templates"),
            static_folder=os.path.join(_HERE, "static"))
app.secret_key = os.getenv("HUB_SECRET_KEY") or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=12)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.getenv("HUB_INSECURE_COOKIE") != "1")

HUB_USER = os.getenv("HUB_USER", "Mael_Girardin")
# Défaut baké « testtest », comme OptiqPulse : le hub ne contient aucun secret,
# et poser HUB_PASSWORD suffit à le durcir sans reconstruire l'image.
_DEFAULT_HASH = ("pbkdf2:sha256:600000$9Qza0VOKPsgnMmah$"
                 "9941d508368cfd0acff7115beb3189a6fd655862c9796426ea47d4e9b3760907")

_ATTEMPTS = {}
_MAX_TRIES, _LOCK_WINDOW_S = 8, 900


def _check_credentials(username, password):
    if not hmac.compare_digest(username or "", HUB_USER):
        return False
    plain = os.getenv("HUB_PASSWORD")
    if plain:
        return hmac.compare_digest(password or "", plain)
    return check_password_hash(os.getenv("HUB_PASSWORD_HASH") or _DEFAULT_HASH,
                               password or "")


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


# ── État des instances ────────────────────────────────────────────────────
# Sondé côté serveur : le navigateur ne peut pas interroger un autre domaine,
# et c'est de toute façon au hub de savoir si un service répond.
_CACHE = {"ts": 0.0, "etats": {}}
_TTL_S = 25


def _sonder(instance):
    url = instance["url"].rstrip("/") + instance.get("sonde", "/")
    debut = time.perf_counter()
    req = urllib.request.Request(url, method="GET",
                                 headers={"User-Agent": "OptiqHub/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code            # le service répond, c'est ce qui compte
    except Exception:
        return {"etat": "injoignable", "code": None, "ms": None}
    ms = int((time.perf_counter() - debut) * 1000)
    # 2xx/3xx = debout. 5xx = le service tourne mais rend une erreur.
    etat = "en ligne" if code < 400 else ("dégradé" if code < 500 else "en erreur")
    return {"etat": etat, "code": code, "ms": ms}


def etats_instances(force=False):
    if not force and time.time() - _CACHE["ts"] < _TTL_S and _CACHE["etats"]:
        return _CACHE["etats"]
    etats = {}
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        travaux = {pool.submit(_sonder, i): i["cle"] for i in inventaire.INSTANCES}
        for f in futures.as_completed(travaux):
            cle = travaux[f]
            try:
                etats[cle] = f.result()
            except Exception:
                etats[cle] = {"etat": "injoignable", "code": None, "ms": None}
    _CACHE.update(ts=time.time(), etats=etats)
    return etats


# ── Routes ────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    erreur = None
    suite = request.args.get("suite") or request.form.get("suite") or "/"
    if not suite.startswith("/"):
        suite = "/"
    if request.method == "POST":
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
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


@app.route("/")
@login_required
def accueil():
    return render_template("hub.html", inv=inventaire, etats=etats_instances())


@app.route("/api/etat")
@login_required
def api_etat():
    return jsonify(etats_instances(force=request.args.get("force") == "1"))


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
    """Le plan V1.1 est en Markdown : rendu tel quel dans une page lisible."""
    chemin = os.path.join(_DOCS, "refonte_competences_v1_1.md")
    if not os.path.exists(chemin):
        abort(404)
    with open(chemin, encoding="utf-8") as f:
        return render_template("markdown.html", titre="Refonte Compétences V1.1",
                               contenu=f.read())


@app.route("/assets/<path:chemin>")
@login_required
def assets(chemin):
    """Images et vidéos du guide (docs/assets/…), servies telles quelles."""
    return send_from_directory(os.path.join(_DOCS, "assets"), chemin)


@app.route("/health")
def health():
    # /health et PAS /healthz : ce dernier est intercepté par le frontend
    # Google sur *.run.app (404 avant d'atteindre le conteneur).
    return "ok", 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", 8080)), debug=True)
