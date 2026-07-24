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


def create_app(test_config=None):
    static_folder = os.path.join(parent_dir, "static")
    app = Flask(__name__, static_folder=static_folder)

    # Jamais de debug par défaut : stack traces interdites chez un client.
    _debug = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.config["DEBUG"] = _debug
    app.config["PROPAGATE_EXCEPTIONS"] = _debug

    # -----------------------------
    # 1) Base de données
    # -----------------------------
    db_url = os.getenv("DATABASE_URL")

    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
        # Défauts calibrés Neon free tier (max ~20 connexions) ; un Postgres
        # local/dédié peut monter via DB_POOL_SIZE / DB_MAX_OVERFLOW.
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": int(os.getenv("DB_POOL_SIZE", "2")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "3")),
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
    # Aucun identifiant par défaut : chaque instance (client compris) fournit son
    # propre compte d'envoi via l'environnement (compte Google + mot de passe
    # d'application, cf. distribution/.env.example). Sans config → envoi désactivé.
    _mail_user = os.getenv("MAIL_USERNAME")
    _mail_pwd  = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_SERVER"]         = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"]           = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"]        = True
    app.config["MAIL_USERNAME"]       = _mail_user
    app.config["MAIL_PASSWORD"]       = _mail_pwd
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", _mail_user)
    app.config["MAIL_CONFIGURED"]     = bool(_mail_user and _mail_pwd)
    if not app.config["MAIL_CONFIGURED"]:
        print("[MAIL] MAIL_USERNAME/MAIL_PASSWORD absents — envoi d'emails désactivé "
              "(reset de mot de passe indisponible)")

    # Appliquer la config de test APRÈS les defaults (override complet)
    if test_config:
        app.config.update(test_config)

    mail.init_app(app)
    db.init_app(app)

    # Importer les modèles test panel ici pour que db.create_all() les connaisse
    from Code.models import test_models  # noqa: F401

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

    # ── Contexte de traduction (injecte t() et lang dans tous les templates) ──
    from Code.translations import t as _t

    @app.context_processor
    def inject_translation():
        from flask import session as _sess
        lang = _sess.get('lang', 'fr') if _sess else 'fr'
        return {'t': _t, 'lang': lang}

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

    from Code.routes.propose_from_file import propose_from_file_bp
    app.register_blueprint(propose_from_file_bp)

    from Code.routes.time_view import time_bp
    app.register_blueprint(time_bp)

    from Code.routes.gestion_compte import gestion_compte_bp
    app.register_blueprint(gestion_compte_bp)

    from Code.routes.routes_password import auth_password_bp
    app.register_blueprint(auth_password_bp)

    from Code.routes.gestion_rh import gestion_rh_bp
    app.register_blueprint(gestion_rh_bp)

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

    from Code.routes.cartography_editor import cartography_editor_bp
    app.register_blueprint(cartography_editor_bp)

    from Code.routes.settings import settings_bp
    app.register_blueprint(settings_bp)

    from Code.routes.test_panel import test_panel_bp
    app.register_blueprint(test_panel_bp)

    from Code.routes.projection_metier import projection_metier_bp
    app.register_blueprint(projection_metier_bp)

    from Code.routes.qualify_outputs import qualify_bp
    app.register_blueprint(qualify_bp)

    from Code.routes.result_capabilities import result_cap_bp
    app.register_blueprint(result_cap_bp)

    from Code.routes.mastery import mastery_bp
    app.register_blueprint(mastery_bp)

    from Code.routes.diagnostic import diagnostic_bp
    app.register_blueprint(diagnostic_bp)

    from Code.routes.technical_domains import domains_bp
    app.register_blueprint(domains_bp)

    from Code.routes.cadence import cadence_bp
    app.register_blueprint(cadence_bp)

    from Code.routes.hsc_positioning import hsc_bp
    app.register_blueprint(hsc_bp)

    from Code.routes.ui_routes import ui_bp
    app.register_blueprint(ui_bp)

    # En mode test, on saute l'init DB — le conftest gère create_all/seed.
    if test_config is not None:
        app.config.update(test_config)
        app.secret_key = test_config.get("SECRET_KEY", "test-secret")

        @app.route("/healthz")
        def healthz():
            return "ok", 200

        @app.route("/")
        def home():
            return redirect(url_for("auth.login"))

        @app.teardown_appcontext
        def shutdown_session(exception=None):
            db.session.remove()

        return app

    with app.app_context():
        from sqlalchemy import text as _text

        def _safe_add_column(table, col, col_type):
            try:
                with db.engine.connect() as _conn:
                    _conn.execute(_text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    _conn.commit()
                    print(f"[DB] Colonne {table}.{col} ajoutée")
            except Exception:
                pass  # colonne déjà présente — normal

        # 1. Créer les tables manquantes (idempotent, pas de verrou DDL)
        try:
            db.create_all()
            print("[DB] Tables vérifiées/créées via create_all")
        except Exception as e:
            print(f"[DB] create_all warning: {e}")

        # 2. Colonnes manquantes — ALTER TABLE instantané, ignore si déjà présente
        _safe_add_column("tools", "file_path", "VARCHAR(512)")
        _safe_add_column("constraints", "file_path", "VARCHAR(512)")
        _safe_add_column("entities", "svg_content", "TEXT")
        _safe_add_column("entities", "vsdx_filename", "VARCHAR(255)")
        _safe_add_column("entities", "optiqcarto_data", "TEXT")
        _safe_add_column("recent_events", "detail", "TEXT")
        _safe_add_column("recent_events", "user_id", "INTEGER")
        _safe_add_column("activities", "shape_subtype", "VARCHAR(50)")
        _safe_add_column("links", "cross_carto_liaison_id", "INTEGER")
        _safe_add_column("links", "cross_carto_label", "VARCHAR(200)")
        _safe_add_column("cross_carto_liaisons", "display_label", "VARCHAR(200)")
        _safe_add_column("links", "choice_label", "VARCHAR(10)")
        # V1.1 — CDC 1 : qualification sémantique des données de sortie
        _safe_add_column("data", "semantic_nature", "VARCHAR(20)")
        _safe_add_column("data", "minimum_performance_text", "TEXT")
        _safe_add_column("data", "qualification_source", "VARCHAR(10)")
        _safe_add_column("data", "qualification_updated_at", "TIMESTAMP")
        # V1.1 — CDC 1/§8 : ancrage d'une sortie matérialisée à son activité productrice
        _safe_add_column("data", "producer_activity_id", "INTEGER")
        # V1.1 — CDC 3 : niveaux de maîtrise (requis rôle × activité, démontré individu)
        _safe_add_column("activity_roles", "required_mastery_level", "INTEGER")
        _safe_add_column("competency_evaluation", "mastery_level", "INTEGER")
        _safe_add_column("competency_evaluation", "evidence", "TEXT")
        _safe_add_column("competency_evaluation", "evaluated_at", "TIMESTAMP")
        _safe_add_column("competency_evaluation", "evaluator_user_id", "INTEGER")
        # V1.1 — CDC 5 : cadences activité + fraîcheur données
        _safe_add_column("activities", "cadence_code", "VARCHAR(20)")
        _safe_add_column("activities", "cadence_details", "TEXT")
        _safe_add_column("data", "update_cadence_code", "VARCHAR(20)")
        _safe_add_column("data", "max_age_hours", "INTEGER")
        # Traduction des noms de rôles (caches FR/EN, affichage selon la langue)
        _safe_add_column("roles", "name_fr", "VARCHAR(200)")
        _safe_add_column("roles", "name_en", "VARCHAR(200)")
        # Paramètres entreprise : les tables historiques n'avaient pas entity_id
        _safe_add_column("entreprise_settings", "entity_id", "INTEGER")

        # users.password : les hashes modernes (~162 car. en scrypt) dépassaient
        # une colonne créée étroite avant l'élargissement du modèle → l'UPDATE
        # échouait en PostgreSQL et l'ancien mot de passe restait actif.
        try:
            with db.engine.connect() as _conn:
                _conn.execute(_text("ALTER TABLE users ALTER COLUMN password TYPE VARCHAR(255)"))
                _conn.commit()
                print("[DB] Colonne users.password élargie à VARCHAR(255)")
        except Exception:
            pass  # SQLite (longueur non contraignante) ou déjà au bon type

        # 3. Tables supplémentaires
        try:
            from Code.models.models import FileBlob
            FileBlob.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table file_blobs prête")
        except Exception as e:
            print(f"[DB] file_blobs check: {e}")

        try:
            from Code.models.test_models import TestPage, TestCase, TestRun, TestResult
            for model in (TestPage, TestCase, TestRun, TestResult):
                model.__table__.create(db.engine, checkfirst=True)
            print("[DB] Tables test panel prêtes")
        except Exception as e:
            print(f"[DB] test panel tables: {e}")

        try:
            from Code.models.models import RecentEvent
            RecentEvent.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table recent_events prête")
        except Exception as e:
            print(f"[DB] recent_events check: {e}")

        try:
            from Code.models.models import EntrepriseSettings
            EntrepriseSettings.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table entreprise_settings prête")
        except Exception as e:
            print(f"[DB] entreprise_settings check: {e}")

        try:
            from Code.models.models import CrossCartoLiaison
            CrossCartoLiaison.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table cross_carto_liaisons prête")
        except Exception as e:
            print(f"[DB] cross_carto_liaisons check: {e}")

        try:
            from Code.models.models import ResultCapabilityLink
            ResultCapabilityLink.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table result_capability_links prête")
        except Exception as e:
            print(f"[DB] result_capability_links check: {e}")

        try:
            from Code.models.models import ResultDiagnostic
            ResultDiagnostic.__table__.create(db.engine, checkfirst=True)
            print("[DB] Table result_diagnostics prête")
        except Exception as e:
            print(f"[DB] result_diagnostics check: {e}")

        try:
            from Code.models.models import (TechnicalDomain, ActivityTechnicalDomain,
                RoleActivityDomainRequirement, UserDomainLevel, HscLevelDescriptor)
            for _m in (TechnicalDomain, ActivityTechnicalDomain, RoleActivityDomainRequirement,
                       UserDomainLevel, HscLevelDescriptor):
                _m.__table__.create(db.engine, checkfirst=True)
            print("[DB] Tables V1.1 itér.2 (domaines + HSC) prêtes")
        except Exception as e:
            print(f"[DB] V1.1 itér.2 tables: {e}")

        # 4. Marquer les migrations Alembic comme appliquées (sans les exécuter)
        # db_upgrade() est intentionnellement absent : il attend un verrou PostgreSQL
        # pendant 10+ minutes si la colonne existe déjà → worker timeout → crash infini.
        try:
            with db.engine.connect() as _conn:
                _conn.execute(_text("DELETE FROM alembic_version"))
                _conn.execute(_text(
                    "INSERT INTO alembic_version (version_num) VALUES ('b2c3d4e5f6a7')"
                ))
                _conn.commit()
                print("[DB] alembic_version → b2c3d4e5f6a7")
        except Exception as e:
            print(f"[DB] alembic_version: {e}")

        # 5. Seed données de démonstration recent_events (opt-in : DEMO_SEED=1 —
        # une instance client démarre sur une base réellement vierge)
        try:
            import json as _json_seed
            from datetime import datetime as _datetime, timedelta
            from Code.models.models import RecentEvent as _RE
            if os.getenv("DEMO_SEED", "0") == "1" and _RE.query.count() == 0:
                _now = _datetime.utcnow()
                _seeds = [
                    _RE(event_type='activity_created',
                        icon='fa-solid fa-diagram-project',
                        label='Activité créée : Gestion des commandes',
                        created_at=_now - timedelta(days=3, hours=2),
                        detail=_json_seed.dumps({"name": "Gestion des commandes",
                                                  "description": "Traitement et suivi des commandes clients"}, ensure_ascii=False)),
                    _RE(event_type='activity_updated',
                        icon='fa-solid fa-pen-to-square',
                        label='Activité modifiée : Facturation',
                        created_at=_now - timedelta(days=2, hours=5),
                        detail=_json_seed.dumps({"changes": [
                            {"field": "Nom", "before": "Factures clients", "after": "Facturation"},
                            {"field": "Description", "before": "Émission des factures", "after": "Création, validation et envoi des factures clients"}
                        ]}, ensure_ascii=False)),
                    _RE(event_type='role_updated',
                        icon='fa-solid fa-pen-to-square',
                        label='Rôle modifié : Responsable Qualité',
                        created_at=_now - timedelta(hours=18),
                        detail=_json_seed.dumps({"changes": [
                            {"field": "Mission", "before": "Contrôle qualité", "after": "Assurer la conformité des processus aux standards ISO"}
                        ]}, ensure_ascii=False)),
                    _RE(event_type='tool_created',
                        icon='fa-solid fa-toolbox',
                        label='Outil créé : CRM Salesforce',
                        created_at=_now - timedelta(hours=6),
                        detail=_json_seed.dumps({"name": "CRM Salesforce",
                                                  "description": "Gestion de la relation client"}, ensure_ascii=False)),
                    _RE(event_type='tool_linked',
                        icon='fa-solid fa-link',
                        label='Outil associé : ERP SAP',
                        created_at=_now - timedelta(minutes=45),
                        detail=_json_seed.dumps({"tool": "ERP SAP", "task": "Saisie des commandes"}, ensure_ascii=False)),
                ]
                for _s in _seeds:
                    db.session.add(_s)
                db.session.commit()
                print("[DB] Données de démonstration recent_events insérées")
        except Exception as e:
            db.session.rollback()
            print(f"[DB] Seed recent_events: {e}")
        finally:
            db.session.remove()

        # 6. Bootstrap du premier compte : base sans aucun utilisateur (installation
        # neuve chez un client) + ADMIN_EMAIL/ADMIN_PASSWORD fournis → création
        # d'un administrateur. Ne fait rien dès qu'un utilisateur existe.
        try:
            from Code.models.models import User as _User
            from Code.security import hash_password as _hash_password
            _admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
            _admin_pwd = os.getenv("ADMIN_PASSWORD")
            if _User.query.count() == 0:
                if _admin_email and _admin_pwd:
                    db.session.add(_User(
                        first_name=os.getenv("ADMIN_FIRST_NAME", "Admin"),
                        last_name=os.getenv("ADMIN_LAST_NAME", "OptiqFluent"),
                        email=_admin_email,
                        password=_hash_password(_admin_pwd),
                        status="administrateur",
                    ))
                    db.session.commit()
                    print(f"[BOOTSTRAP] Compte administrateur créé : {_admin_email}")
                else:
                    print("[BOOTSTRAP] Aucun utilisateur en base et ADMIN_EMAIL/"
                          "ADMIN_PASSWORD absents — personne ne pourra se connecter. "
                          "Définir ces variables pour créer le premier compte.")
        except Exception as e:
            db.session.rollback()
            print(f"[BOOTSTRAP] Création admin: {e}")

        # 7. Réinitialiser le pool — toutes les connexions du startup sont fermées
        # avant que le worker commence à traiter les requêtes HTTP
        db.engine.dispose()
        print("[DB] Pool connexions réinitialisé")

    # Secret key : jamais de valeur par défaut publique (cookies forgeables).
    # Sans SECRET_KEY, on génère un secret aléatoire éphémère : l'app démarre,
    # mais les sessions sautent à chaque redémarrage → la définir en production.
    _secret = os.getenv("SECRET_KEY")
    if not _secret:
        import secrets as _secrets
        _secret = _secrets.token_hex(32)
        print("[SECURITY] SECRET_KEY non définie — secret aléatoire éphémère généré "
              "(sessions invalidées à chaque redémarrage). Définir SECRET_KEY en production.")
    app.secret_key = _secret

    # Licence signée à expiration (active uniquement si REQUIRE_LICENSE=1 —
    # baké dans l'image distribuée aux clients, inactif en dev/tests)
    from Code.licensing import init_license_enforcement
    init_license_enforcement(app)

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
    app.run(debug=app.config["DEBUG"], host="0.0.0.0",
            port=int(os.getenv("PORT", 8080)), use_reloader=False)
