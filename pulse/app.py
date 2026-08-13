# OptiqPulse — dashboard privé de suivi des utilisateurs DevOPTIQ/OptiqFluent.
# Service web autonome (Cloud Run dédié), séparé de l'app : il se branche en
# LECTURE sur la base Neon de chaque instance suivie (env PULSE_DBS[_B64]).
# Accès verrouillé : un seul compte (PULSE_USER / PULSE_PASSWORD[_HASH]).

import hmac
import os
import secrets
import time
from datetime import timedelta
from functools import wraps

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash

import aggregates

_HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(_HERE, "templates"),
            static_folder=os.path.join(_HERE, "static"))
app.secret_key = os.getenv("PULSE_SECRET_KEY") or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=12)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.getenv("PULSE_INSECURE_COOKIE") != "1")

PULSE_USER = os.getenv("PULSE_USER", "Mael_Girardin")
# Mot de passe : env PULSE_PASSWORD (clair, pratique pour la rotation) ou
# PULSE_PASSWORD_HASH (pbkdf2 werkzeug). Défaut baké : « testtest ».
_DEFAULT_HASH = ("pbkdf2:sha256:600000$9Qza0VOKPsgnMmah$"
                 "9941d508368cfd0acff7115beb3189a6fd655862c9796426ea47d4e9b3760907")

# Anti-force-brute mémoire : 8 essais / 15 min par IP (échelle mono-instance).
_ATTEMPTS = {}
_MAX_TRIES, _LOCK_WINDOW_S = 8, 900


def _check_credentials(username, password):
    if not hmac.compare_digest(username or "", PULSE_USER):
        return False
    plain = os.getenv("PULSE_PASSWORD")
    if plain:
        return hmac.compare_digest(password or "", plain)
    ref = os.getenv("PULSE_PASSWORD_HASH") or _DEFAULT_HASH
    return check_password_hash(ref, password or "")


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
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


@app.after_request
def _headers(resp):
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@app.route("/healthz")
def healthz():
    return {"ok": True, "sources": len(aggregates.load_sources())}


@app.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?")
        ip = ip.split(",")[0].strip()
        if _rate_limited(ip):
            error = "Trop de tentatives — réessayez dans quelques minutes."
        elif _check_credentials(request.form.get("username", "").strip(),
                                request.form.get("password", "")):
            session.clear()
            session.permanent = True
            session["auth"] = True
            return redirect(url_for("dashboard"))
        else:
            _ATTEMPTS.setdefault(ip, []).append(time.time())
            error = "Identifiant ou mot de passe incorrect."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    sources = [s["name"] for s in aggregates.load_sources()]
    return render_template("dashboard.html", sources=sources)


def _selected_windows(range_key):
    sources = aggregates.load_sources()
    sel = request.args.get("src", "all")
    if sel != "all":
        sources = [s for s in sources if s["name"] == sel]
    start = aggregates.range_start(range_key)
    return [(s["name"], aggregates.load_window(s, start)) for s in sources]


@app.route("/api/overview")
@login_required
def api_overview():
    range_key = request.args.get("range", "7d")
    if range_key not in aggregates.RANGES:
        abort(400)
    windows = _selected_windows(range_key)
    return jsonify(aggregates.summarize(windows, range_key))


@app.route("/api/journey")
@login_required
def api_journey():
    range_key = request.args.get("range", "7d")
    src = request.args.get("src", "")
    try:
        user_id = int(request.args.get("user", ""))
    except ValueError:
        abort(400)
    source = next((s for s in aggregates.load_sources() if s["name"] == src),
                  None)
    if source is None or range_key not in aggregates.RANGES:
        abort(400)
    window = aggregates.load_window(source, aggregates.range_start(range_key))
    return jsonify({
        "user": user_id, "source": src,
        "journey": aggregates.user_journey(window, user_id),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
