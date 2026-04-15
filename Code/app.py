# Code/app.py

import os
import sys
from dotenv import load_dotenv

load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from flask import Flask, redirect, url_for
from flask_migrate import Migrate
from Code.extensions import db, mail

import smtplib
from flask_mail import Mail


class CustomMail(Mail):
    def connect(self):
        connection = super().connect()
        if isinstance(connection, smtplib.SMTP):
            connection.local_hostname = "localhost"
        return connection


def create_app():
    static_folder = os.path.join(parent_dir, "static")
    app = Flask(__name__, static_folder=static_folder)

    app.config["DEBUG"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = True

    # -----------------------------
    # 1) Base de données
    # -----------------------------
    db_url = os.getenv("DATABASE_URL")

    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        # Pool de connexions limité pour Neon (free tier = max ~20 connexions)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 2,
            "max_overflow": 3,
        }
    else:
        instance_path = os.path.join(os.path.dirname(__file__), "instance")
        os.makedirs(instance_path, exist_ok=True)
        db_path = os.path.join(instance_path, "optiq.db")
        # IMPORTANT: Timeout augmenté pour SQLite
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}?timeout=30"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Configuration SQLite pour éviter "database is locked"
    if not db_url:  # Seulement pour SQLite
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "connect_args": {
                "timeout": 30,
                "check_same_thread": False,
            }
        }

    # -----------------------------
    # 2) Mail
    # -----------------------------
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "afdec.enterprise.services@gmail.com")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "awdkerghqvuwjhel")

    mail.init_app(app)
    db.init_app(app)

    migrate = Migrate(app, db)

    # --------- filtres jinja ----------
    import re

    def extract_numeric_level(value):
        match = re.search(r"\d", value or "")
        return match.group(0) if match else "1"

    app.jinja_env.filters["extract_numeric_level"] = extract_numeric_level

    def escapejs_filter(value):
        if not value:
            return ""
        out = value.replace("\\", "\\\\")
        out = out.replace("'", "\\'")
        out = out.replace('"', '\\"')
        return out

    app.jinja_env.filters["escapejs"] = escapejs_filter

    # -----------------------------
    # Blueprints
    # -----------------------------
    from Code.routes.activities import activities_bp
    app.register_blueprint(activities_bp)

    from Code.routes.tools import tools_bp
    app.register_blueprint(tools_bp)

    from Code.routes.skills import skills_bp
    app.register_blueprint(skills_bp)

    from Code.routes.roles import roles_bp
    app.register_blueprint(roles_bp)

    from Code.routes.roles_view import roles_view_bp
    app.register_blueprint(roles_view_bp)

    from Code.routes.onboarding import onboarding_bp
    app.register_blueprint(onboarding_bp)

    from Code.routes.tasks import tasks_bp
    app.register_blueprint(tasks_bp)

    from Code.routes.performance import performance_bp
    app.register_blueprint(performance_bp)

    from Code.routes.constraints import constraints_bp
    app.register_blueprint(constraints_bp)

    from Code.routes.propose_softskills import bp_propose_softskills
    app.register_blueprint(bp_propose_softskills)

    from Code.routes.translate_softskills import translate_softskills_bp
    app.register_blueprint(translate_softskills_bp)

    from Code.routes.softskills import softskills_crud_bp
    app.register_blueprint(softskills_crud_bp)

    from Code.routes.savoirs import savoirs_bp
    app.register_blueprint(savoirs_bp)

    from Code.routes.savoir_faires import savoir_faires_bp
    app.register_blueprint(savoir_faires_bp)

    from Code.routes.aptitudes import aptitudes_bp
    app.register_blueprint(aptitudes_bp)

    from Code.routes.connexion_routes import auth_bp
    app.register_blueprint(auth_bp)

    from Code.routes.competences import competences_bp
    app.register_blueprint(competences_bp)

    from Code.routes.propose_savoirs import bp_propose_savoirs
    app.register_blueprint(bp_propose_savoirs)

    from Code.routes.propose_savoir_faires import bp_propose_sf
    app.register_blueprint(bp_propose_sf)

    from Code.routes.propose_aptitudes import bp_propose_aptitudes
    app.register_blueprint(bp_propose_aptitudes)

    from Code.routes.time_view import time_bp
    app.register_blueprint(time_bp)

    from Code.routes.gestion_compte import gestion_compte_bp
    app.register_blueprint(gestion_compte_bp)

    from Code.routes.routes_password import auth_password_bp
    app.register_blueprint(auth_password_bp)

    from Code.routes.gestion_rh import gestion_rh_bp
    app.register_blueprint(gestion_rh_bp)

    from Code.routes.projection_metier import projection_metier_bp
    app.register_blueprint(projection_metier_bp)

    from Code.routes.gestion_outils import bp_tools
    app.register_blueprint(bp_tools)

    from Code.routes.performance_personnalisee import performance_perso_bp
    app.register_blueprint(performance_perso_bp)

    from Code.routes.competences_plan import competences_plan_bp
    app.register_blueprint(competences_plan_bp)

    from Code.routes.activity_items_api import activity_items_api_bp
    app.register_blueprint(activity_items_api_bp)

    from Code.routes.plan_storage import plan_storage_bp
    app.register_blueprint(plan_storage_bp)

    from Code.routes.activities_map import activities_map_bp
    app.register_blueprint(activities_map_bp)

    from Code.routes.task_link_assignments import task_links_bp
    app.register_blueprint(task_links_bp)

    from Code.routes.chatbot import chatbot_bp
    app.register_blueprint(chatbot_bp)

    from Code.routes.import_tasks import import_tasks_bp
    app.register_blueprint(import_tasks_bp)

    from Code.routes.import_full import import_full_bp
    app.register_blueprint(import_full_bp)

    from Code.routes.changelog import changelog_bp
    app.register_blueprint(changelog_bp)

    from Code.routes.export import export_bp
    app.register_blueprint(export_bp)

    # Auto-migration au démarrage (nécessaire sur les serveurs cloud avec filesystem éphémère)
    # Les blueprints sont enregistrés avant pour garantir que tous les modèles sont chargés
    with app.app_context():
        try:
            from flask_migrate import upgrade as db_upgrade
            db_upgrade()
            print("[DB] Migrations appliquées avec succès")
        except Exception as e:
            print(f"[DB] Avertissement migration (ignoré): {e}")

        # Ajout sécurisé des colonnes file_path (compatible SQLite et PostgreSQL)
        try:
            from sqlalchemy import text as _text
            for _tbl, _col in [("tools", "file_path"), ("constraints", "file_path")]:
                try:
                    db.session.execute(_text(f"ALTER TABLE {_tbl} ADD COLUMN {_col} VARCHAR(512)"))
                    db.session.commit()
                    print(f"[DB] Colonne {_tbl}.{_col} ajoutée")
                except Exception:
                    db.session.rollback()  # colonne déjà présente
        except Exception as e:
            print(f"[DB] file_path migration check: {e}")

        # Création table file_blobs (stockage binaire des fichiers liés — persistant)
        try:
            from Code.models.models import FileBlob
            FileBlob.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table file_blobs prête")
        except Exception as e:
            print(f"[DB] file_blobs check: {e}")

        # Création table recent_events (journal d'activité pour la popup d'accueil)
        try:
            from Code.models.models import RecentEvent
            RecentEvent.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table recent_events prête")
        except Exception as e:
            print(f"[DB] recent_events check: {e}")

    # secret key
    app.secret_key = os.getenv("SECRET_KEY", "devoptiq-secret")

    @app.route("/healthz")
    def healthz():
        return "ok", 200

    @app.route("/")
    def home():
        return redirect(url_for("auth.login"))

    # Fermer proprement les connexions après chaque requête
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    return app


app = create_app()

if __name__ == "__main__":
    # IMPORTANT: use_reloader=False pour éviter "database is locked" avec SQLite
    # Le reloader crée 2 processus qui accèdent à la DB simultanément
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), use_reloader=False)
