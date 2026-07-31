# Code/routes/setup_wizard.py — Assistant d'installation OptiqFluent (/setup).
#
# Actif uniquement au premier démarrage (SETUP_WIZARD=1 + aucune config écrite,
# cf. Code/app.py). Guide l'installateur : licence → base de données → clé
# OpenAI → mail (optionnel) → compte administrateur, teste chaque valeur,
# écrit le fichier de configuration sur le volume client puis redémarre le
# conteneur. Le démarrage suivant utilise la mécanique normale (create_all,
# migrations, bootstrap admin depuis ADMIN_EMAIL/ADMIN_PASSWORD).

import os
import re
import signal
import smtplib
import sys
import threading
import time

from flask import Blueprint, jsonify, render_template, request

setup_bp = Blueprint("setup", __name__, url_prefix="/setup",
                     template_folder="templates")


def _config_dir():
    from Code.app import CONFIG_DIR
    return CONFIG_DIR


def _config_env_path():
    from Code.app import CONFIG_ENV_PATH
    return CONFIG_ENV_PATH


def _license_status():
    """État de la licence déjà présente (montée via ./license), le cas échéant."""
    if os.getenv("REQUIRE_LICENSE", "0") != "1":
        return {"required": False, "valid": True}
    from Code.licensing import verify_license, LicenseError
    from datetime import date
    try:
        info = verify_license()
        return {"required": True,
                "valid": date.today() <= info["expires_at"],
                "licensee": info["licensee"],
                "expires_at": info["expires_at"].isoformat()}
    except LicenseError as e:
        return {"required": True, "valid": False, "error": str(e)}


@setup_bp.route("/")
@setup_bp.route("")
def setup_home():
    return render_template(
        "setup_wizard.html",
        license_status=_license_status(),
        db_default=os.getenv("DATABASE_URL", ""),
        mail_server_default=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    )


@setup_bp.route("/ping")
def ping():
    return jsonify({"setup": True})


@setup_bp.route("/api/license", methods=["POST"])
def api_license():
    """Valide un contenu de licence collé/déposé et l'enregistre sur le volume."""
    content = (request.get_json(force=True) or {}).get("content", "").strip()
    if not content:
        return jsonify({"ok": False, "error": "Contenu de licence vide."})
    from Code.licensing import verify_license_bytes, LicenseError
    from datetime import date
    try:
        info = verify_license_bytes(content.encode("utf-8"))
    except LicenseError as e:
        return jsonify({"ok": False, "error": str(e)})
    if date.today() > info["expires_at"]:
        return jsonify({"ok": False,
                        "error": f"Licence expirée le {info['expires_at']}."})
    try:
        os.makedirs(_config_dir(), exist_ok=True)
        lic_path = os.path.join(_config_dir(), "optiqfluent.lic")
        with open(lic_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        return jsonify({"ok": False, "error": f"Écriture impossible ({e}) — "
                        "le volume ./config est-il bien monté ?"})
    # Prise en compte immédiate pour la suite de la session d'installation
    os.environ["LICENSE_PATH"] = lic_path
    return jsonify({"ok": True, "licensee": info["licensee"],
                    "expires_at": info["expires_at"].isoformat()})


@setup_bp.route("/api/test-db", methods=["POST"])
def api_test_db():
    url = (request.get_json(force=True) or {}).get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL de connexion vide."})
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    try:
        from sqlalchemy import create_engine, text
        connect_args = {"connect_timeout": 8} if url.startswith("postgresql") else {}
        engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@setup_bp.route("/api/test-openai", methods=["POST"])
def api_test_openai():
    key = (request.get_json(force=True) or {}).get("key", "").strip()
    if not key:
        return jsonify({"ok": False, "error": "Clé vide."})
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, timeout=15)
        client.models.list()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@setup_bp.route("/api/test-mail", methods=["POST"])
def api_test_mail():
    p = request.get_json(force=True) or {}
    server = (p.get("server") or "smtp.gmail.com").strip()
    try:
        port = int(p.get("port") or 587)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Port invalide."})
    username, password = (p.get("username") or "").strip(), p.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "error": "Adresse et mot de passe requis."})
    try:
        with smtplib.SMTP(server, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(username, password)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _quote(value):
    """Valeur au format dotenv (double quotes, échappement)."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


@setup_bp.route("/api/finish", methods=["POST"])
def api_finish():
    p = request.get_json(force=True) or {}
    db_url = (p.get("database_url") or "").strip()
    openai_key = (p.get("openai_key") or "").strip()
    admin = p.get("admin") or {}
    admin_email = (admin.get("email") or "").strip().lower()
    admin_password = admin.get("password") or ""
    mail = p.get("mail") or {}

    if not db_url:
        return jsonify({"ok": False, "error": "URL de base de données manquante."})
    if not re.match(r"[^@]+@[^@]+\.[^@]+", admin_email):
        return jsonify({"ok": False, "error": "Email administrateur invalide."})
    if len(admin_password) < 8:
        return jsonify({"ok": False, "error":
                        "Mot de passe administrateur trop court (8 caractères minimum)."})
    if os.getenv("REQUIRE_LICENSE", "0") == "1" and not _license_status()["valid"]:
        return jsonify({"ok": False, "error":
                        "Aucune licence valide — revenir à l'étape Licence."})

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    import secrets
    lines = [
        "# Configuration OptiqFluent — générée par l'assistant d'installation.",
        "# Supprimer ce fichier puis redémarrer relance l'assistant.",
        "SETUP_DONE=1",
        f"DATABASE_URL={_quote(db_url)}",
        f"SECRET_KEY={_quote(secrets.token_hex(32))}",
    ]
    if openai_key:
        lines.append(f"OPENAI_API_KEY={_quote(openai_key)}")
    if (mail.get("username") or "").strip() and mail.get("password"):
        lines += [
            f"MAIL_SERVER={_quote((mail.get('server') or 'smtp.gmail.com').strip())}",
            f"MAIL_PORT={_quote(mail.get('port') or 587)}",
            f"MAIL_USERNAME={_quote(mail['username'].strip())}",
            f"MAIL_PASSWORD={_quote(mail['password'])}",
        ]
    lines += [
        f"ADMIN_EMAIL={_quote(admin_email)}",
        f"ADMIN_PASSWORD={_quote(admin_password)}",
    ]
    if (admin.get("first_name") or "").strip():
        lines.append(f"ADMIN_FIRST_NAME={_quote(admin['first_name'].strip())}")
    if (admin.get("last_name") or "").strip():
        lines.append(f"ADMIN_LAST_NAME={_quote(admin['last_name'].strip())}")
    lic_path = os.path.join(_config_dir(), "optiqfluent.lic")
    if os.path.isfile(lic_path):
        lines.append(f"LICENSE_PATH={_quote(lic_path)}")

    try:
        os.makedirs(_config_dir(), exist_ok=True)
        with open(_config_env_path(), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        return jsonify({"ok": False, "error": f"Écriture impossible ({e}) — "
                        "le volume ./config est-il bien monté ?"})

    restarting = _schedule_restart()
    return jsonify({"ok": True, "restarting": restarting})


def _schedule_restart():
    """Redémarre le serveur pour appliquer la configuration.

    Sous gunicorn, SIGTERM au master (parent du worker) → le conteneur
    s'arrête proprement et la politique de redémarrage docker le relance,
    cette fois configuré. Hors gunicorn (tests, flask run) : pas de restart.
    """
    if os.getenv("SETUP_NO_RESTART") == "1" or "gunicorn" not in sys.modules:
        return False

    def _later():
        time.sleep(1.5)
        os.kill(os.getppid(), signal.SIGTERM)

    threading.Thread(target=_later, daemon=True).start()
    return True
