# -*- coding: utf-8 -*-
"""Démarrage de l'application — ce que `create_app()` fait AVANT la 1re requête.

La suite tourne sur `create_app(test_config=…)`, qui saute toute
l'initialisation de la base (le conftest s'en charge). Or c'est ce chemin de
production qui crée le premier administrateur chez un client, purge la
télémétrie, rattrape les colonnes manquantes et survit aux migrations qui
échouent. Rien de tout cela n'était éprouvé.

⚠️ Chaque démarrage se fait sur une base SQLite JETABLE (`tmp_path`) et un
CONFIG_DIR jetable : la base partagée de la suite n'est jamais touchée. Le
`db` global sert plusieurs applications (Flask-SQLAlchemy 3 range une session
par contexte d'application) : on pousse donc toujours le contexte de l'app
démarrée avant de lire sa base.
"""
import smtplib
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from Code.extensions import db


# ── Démarrage isolé ───────────────────────────────────────────────────────

@pytest.fixture()
def demarrer(tmp_path, monkeypatch):
    """Rend une fonction qui démarre une app de PRODUCTION sur une base jetable.

    Les variables passées en argument sont posées avant le démarrage ; la même
    base sert à tous les démarrages d'un test (pour éprouver l'idempotence).
    """
    import Code.app as app_module
    import Code.logstream as logstream

    monkeypatch.setattr(logstream, "init_logstream", lambda: None)
    cfg = tmp_path / "config"
    cfg.mkdir()
    monkeypatch.setattr(app_module, "CONFIG_DIR", str(cfg))
    monkeypatch.setattr(app_module, "CONFIG_ENV_PATH", str(cfg / "optiqfluent.env"))
    for var in ("SETUP_WIZARD", "REQUIRE_LICENSE", "ADMIN_EMAIL", "ADMIN_PASSWORD",
                "ADMIN_FIRST_NAME", "ADMIN_LAST_NAME", "DEMO_SEED", "SECRET_KEY",
                "DB_POOL_SIZE", "DB_MAX_OVERFLOW"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'demarrage.db'}")

    apps = []

    def _go(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        a = app_module.create_app()
        a.config["TESTING"] = True
        apps.append(a)
        return a

    yield _go
    for a in apps:
        with a.app_context():
            db.session.remove()
            db.engine.dispose()


def _capturer_config(monkeypatch):
    """Arrête create_app juste avant `db.init_app` et rend sa configuration.

    Sert aux URL qu'on ne peut pas ouvrir ici (PostgreSQL) : seule la
    transformation de la configuration est éprouvée, pas la connexion.
    """
    import Code.app as app_module
    import Code.logstream as logstream

    class _Arret(Exception):
        pass

    vu = {}

    def _init_app(app):
        vu.update(app.config)
        raise _Arret()

    monkeypatch.setattr(logstream, "init_logstream", lambda: None)
    monkeypatch.delenv("SETUP_WIZARD", raising=False)
    monkeypatch.setattr(app_module.db, "init_app", _init_app)

    def _go():
        with pytest.raises(_Arret):
            app_module.create_app()
        return vu
    return _go


# ── Configuration de la base ──────────────────────────────────────────────

class TestConfigurationBase:

    #     ⚠️ CES DEUX CAS ONT ÉTÉ RENVERSÉS le 25/11. Ils affirmaient que
    # `postgresql://` était laissé TEL QUEL — c'est précisément ce qui a été
    # changé : `postgresql://` seul désignait psycopg2 en SQLAlchemy 2.0 et
    # désigne psycopg (v3) depuis la 2.1, qui n'est pas installé. C'est
    # l'incident du 29/10 qui a mis tout le hub à terre, et le correctif
    # n'avait été porté que dans `hub/` et `pulse/`.
    #     Un cas qui affirme une règle remplacée ne garde plus rien : on le
    # réécrit sur la vérité neuve, on ne le supprime pas.
    def test_url_postgres_heroku_recoit_postgresql_ET_son_pilote(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://u:p@hote:5432/optiq")
        cfg = _capturer_config(monkeypatch)()
        assert cfg["SQLALCHEMY_DATABASE_URI"] == \
            "postgresql+psycopg2://u:p@hote:5432/optiq"

    def test_url_postgresql_recoit_SON_PILOTE(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@hote/optiq")
        cfg = _capturer_config(monkeypatch)()
        assert cfg["SQLALCHEMY_DATABASE_URI"] == \
            "postgresql+psycopg2://u:p@hote/optiq"

    def test_une_url_qui_nomme_deja_son_pilote_n_est_pas_reecrite(self, monkeypatch):
        """⚠️ Réécrire une URL qui nomme son pilote, ce serait décider à la
        place de celui qui l'a posée."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@hote/optiq")
        cfg = _capturer_config(monkeypatch)()
        assert cfg["SQLALCHEMY_DATABASE_URI"] == \
            "postgresql+psycopg://u:p@hote/optiq"

    def test_pool_par_defaut_calibre_neon(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@hote/optiq")
        monkeypatch.delenv("DB_POOL_SIZE", raising=False)
        monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
        opts = _capturer_config(monkeypatch)()["SQLALCHEMY_ENGINE_OPTIONS"]
        assert (opts["pool_size"], opts["max_overflow"]) == (2, 3)
        assert opts["pool_pre_ping"] is True and opts["pool_recycle"] == 300

    def test_pool_reglable_par_environnement(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@hote/optiq")
        monkeypatch.setenv("DB_POOL_SIZE", "10")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "20")
        opts = _capturer_config(monkeypatch)()["SQLALCHEMY_ENGINE_OPTIONS"]
        assert (opts["pool_size"], opts["max_overflow"]) == (10, 20)

    def test_url_externe_sans_options_sqlite(self, monkeypatch):
        """Les `connect_args` SQLite ne doivent jamais partir vers PostgreSQL."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@hote/optiq")
        opts = _capturer_config(monkeypatch)()["SQLALCHEMY_ENGINE_OPTIONS"]
        assert "connect_args" not in opts


# ── Routes de l'app de production ─────────────────────────────────────────

class TestRoutesProduction:

    def test_healthz_repond_ok(self, demarrer):
        r = demarrer().test_client().get("/healthz")
        assert (r.status_code, r.data) == (200, b"ok")

    def test_health_alias_cloud_run(self, demarrer):
        """`/healthz` est intercepté par le frontal *.run.app : `/health` doit répondre."""
        r = demarrer().test_client().get("/health")
        assert (r.status_code, r.data) == (200, b"ok")

    def test_racine_redirige_vers_login(self, demarrer):
        r = demarrer().test_client().get("/", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/login")

    def test_secret_ephemere_sans_secret_key(self, demarrer, capsys):
        a = demarrer()
        assert len(a.secret_key) == 64
        int(a.secret_key, 16)
        assert "SECRET_KEY non définie" in capsys.readouterr().out

    def test_deux_demarrages_sans_secret_key_ont_des_secrets_differents(self, demarrer):
        assert demarrer().secret_key != demarrer().secret_key

    def test_secret_key_fournie_utilisee(self, demarrer):
        assert demarrer(SECRET_KEY="cle-de-prod").secret_key == "cle-de-prod"


# ── Premier compte administrateur ─────────────────────────────────────────

class TestBootstrapAdmin:

    def _users(self, a):
        from Code.models.models import User
        with a.app_context():
            return [(u.email, u.status, u.first_name, u.last_name)
                    for u in User.query.all()]

    def test_admin_cree_sur_base_vierge(self, demarrer):
        a = demarrer(ADMIN_EMAIL="  Admin@Client.FR ", ADMIN_PASSWORD="motdepasse-long")
        assert self._users(a) == [("admin@client.fr", "administrateur", "Admin", "OptiqFluent")]

    def test_admin_peut_se_connecter_avec_son_mot_de_passe(self, demarrer):
        from Code.models.models import User
        from Code.security import verify_password
        a = demarrer(ADMIN_EMAIL="admin@client.fr", ADMIN_PASSWORD="motdepasse-long")
        with a.app_context():
            u = User.query.one()
            assert verify_password(u.password, "motdepasse-long")
            assert u.password != "motdepasse-long"

    def test_admin_nom_personnalise(self, demarrer):
        a = demarrer(ADMIN_EMAIL="a@b.fr", ADMIN_PASSWORD="x" * 12,
                     ADMIN_FIRST_NAME="Jeanne", ADMIN_LAST_NAME="Martin")
        assert self._users(a)[0][2:] == ("Jeanne", "Martin")

    def test_mot_de_passe_initial_retire_du_fichier_de_config(self, demarrer, capsys):
        import Code.app as app_module
        with open(app_module.CONFIG_ENV_PATH, "w") as f:
            f.write("SETUP_DONE=1\nADMIN_EMAIL=a@b.fr\nADMIN_PASSWORD=secret\n")
        demarrer(ADMIN_EMAIL="a@b.fr", ADMIN_PASSWORD="secret-assez-long")
        contenu = open(app_module.CONFIG_ENV_PATH).read()
        assert "ADMIN_PASSWORD" not in contenu
        assert "SETUP_DONE=1" in contenu and "ADMIN_EMAIL=a@b.fr" in contenu
        assert "ADMIN_PASSWORD retiré" in capsys.readouterr().out

    def test_fichier_de_config_sans_mot_de_passe_non_reecrit(self, demarrer, capsys):
        import Code.app as app_module
        with open(app_module.CONFIG_ENV_PATH, "w") as f:
            f.write("SETUP_DONE=1\n")
        demarrer(ADMIN_EMAIL="a@b.fr", ADMIN_PASSWORD="secret-assez-long")
        assert open(app_module.CONFIG_ENV_PATH).read() == "SETUP_DONE=1\n"
        assert "ADMIN_PASSWORD retiré" not in capsys.readouterr().out

    def test_scrub_sans_fichier_de_config_ne_leve_pas(self, tmp_path, monkeypatch):
        import Code.app as app_module
        monkeypatch.setattr(app_module, "CONFIG_ENV_PATH", str(tmp_path / "absent.env"))
        app_module._scrub_admin_password()
        assert not (tmp_path / "absent.env").exists()

    def test_sans_variables_aucun_compte_et_avertissement(self, demarrer, capsys):
        a = demarrer()
        assert self._users(a) == []
        assert "personne ne pourra se connecter" in capsys.readouterr().out

    def test_email_sans_mot_de_passe_aucun_compte(self, demarrer):
        assert self._users(demarrer(ADMIN_EMAIL="a@b.fr")) == []

    def test_aucun_second_admin_si_un_compte_existe(self, demarrer):
        demarrer(ADMIN_EMAIL="premier@b.fr", ADMIN_PASSWORD="secret-assez-long")
        a = demarrer(ADMIN_EMAIL="second@b.fr", ADMIN_PASSWORD="autre-secret-long")
        assert [u[0] for u in self._users(a)] == ["premier@b.fr"]

    def test_echec_creation_admin_ne_bloque_pas_le_demarrage(self, demarrer, monkeypatch, capsys):
        import Code.security as security
        monkeypatch.setattr(security, "hash_password",
                            lambda p: (_ for _ in ()).throw(RuntimeError("hash HS")))
        a = demarrer(ADMIN_EMAIL="a@b.fr", ADMIN_PASSWORD="secret-assez-long")
        assert "[BOOTSTRAP] Création admin: hash HS" in capsys.readouterr().out
        assert self._users(a) == []
        assert a.test_client().get("/health").status_code == 200


# ── Données de démonstration ──────────────────────────────────────────────

class TestDemoSeed:

    def _events(self, a):
        from Code.models.models import RecentEvent
        with a.app_context():
            return RecentEvent.query.order_by(RecentEvent.created_at).all()

    def test_base_client_vierge_par_defaut(self, demarrer):
        assert self._events(demarrer()) == []

    def test_demo_seed_insere_cinq_evenements(self, demarrer):
        evs = self._events(demarrer(DEMO_SEED="1"))
        assert [e.event_type for e in evs] == [
            "activity_created", "activity_updated", "role_updated",
            "tool_created", "tool_linked"]

    def test_demo_seed_details_json_lisibles(self, demarrer):
        import json
        evs = self._events(demarrer(DEMO_SEED="1"))
        details = [json.loads(e.detail) for e in evs]
        assert details[0]["name"] == "Gestion des commandes"
        assert details[1]["changes"][0]["after"] == "Facturation"
        assert details[4] == {"tool": "ERP SAP", "task": "Saisie des commandes"}

    def test_demo_seed_idempotent(self, demarrer):
        demarrer(DEMO_SEED="1")
        assert len(self._events(demarrer(DEMO_SEED="1"))) == 5

    def test_demo_seed_ignore_si_evenements_existants(self, demarrer):
        from Code.models.models import RecentEvent
        a = demarrer()
        with a.app_context():
            db.session.add(RecentEvent(event_type="x", label="réel"))
            db.session.commit()
        assert [e.label for e in self._events(demarrer(DEMO_SEED="1"))] == ["réel"]

    def test_echec_seed_ne_bloque_pas_le_demarrage(self, demarrer, monkeypatch, capsys):
        import json
        real = json.dumps

        def _dumps(obj, **kw):
            if isinstance(obj, dict) and obj.get("name") == "Gestion des commandes":
                raise ValueError("json HS")
            return real(obj, **kw)
        monkeypatch.setattr(json, "dumps", _dumps)
        a = demarrer(DEMO_SEED="1")
        assert "[DB] Seed recent_events: json HS" in capsys.readouterr().out
        monkeypatch.setattr(json, "dumps", real)
        assert self._events(a) == []


# ── Purge de la télémétrie ────────────────────────────────────────────────

class TestPurgeTelemetrie:

    def test_battements_evenements_et_demandes_anciens_purges(self, demarrer):
        from Code.models.models import UsageBeat, UsageEvent, PasswordReset
        a = demarrer()
        now = datetime.utcnow()
        with a.app_context():
            db.session.add_all([
                UsageBeat(user_id=1, ts=now - timedelta(days=91)),
                UsageBeat(user_id=1, ts=now - timedelta(days=89)),
                UsageEvent(path="/vieux", ts=now - timedelta(days=401)),
                UsageEvent(path="/recent", ts=now - timedelta(days=399)),
                PasswordReset(email_hash="vieux", cree_le=now - timedelta(days=91)),
                PasswordReset(email_hash="recent", cree_le=now - timedelta(days=89)),
            ])
            db.session.commit()
        demarrer()
        with a.app_context():
            assert UsageBeat.query.count() == 1
            assert [e.path for e in UsageEvent.query.all()] == ["/recent"]
            assert [p.email_hash for p in PasswordReset.query.all()] == ["recent"]

    def test_echec_purge_ne_bloque_pas_le_demarrage(self, demarrer, monkeypatch, capsys):
        from Code.models import models

        class _Requete:
            def filter(self, *a, **k):
                raise RuntimeError("purge HS")
        monkeypatch.setattr(models.UsageBeat, "query", _Requete())
        a = demarrer()
        assert "[BOOTSTRAP] Purge télémétrie: purge HS" in capsys.readouterr().out
        assert a.test_client().get("/health").status_code == 200


# ── Migrations au démarrage ───────────────────────────────────────────────

class TestMigrationsDemarrage:

    def test_colonne_manquante_rajoutee(self, demarrer, capsys):
        a = demarrer()
        with a.app_context():
            with db.engine.connect() as c:
                c.execute(text("ALTER TABLE activities DROP COLUMN shape_subtype"))
                c.commit()
        capsys.readouterr()
        demarrer()
        assert "[DB] Colonne activities.shape_subtype ajoutée" in capsys.readouterr().out
        from sqlalchemy import inspect
        with a.app_context():
            cols = {c["name"] for c in inspect(db.engine).get_columns("activities")}
        assert "shape_subtype" in cols

    def test_colonnes_presentes_rien_a_ajouter(self, demarrer, capsys):
        demarrer()
        capsys.readouterr()
        demarrer()
        assert "ajoutée" not in capsys.readouterr().out

    def test_colonne_verifiee_manquante_signalee(self, demarrer, monkeypatch, capsys):
        import sqlalchemy
        vrai = sqlalchemy.inspect

        class _Inspecteur:
            def __init__(self, cible):
                self._i = vrai(cible)

            def has_table(self, t):
                return self._i.has_table(t)

            def get_columns(self, t):
                cols = self._i.get_columns(t)
                if t == "entities":
                    cols = [c for c in cols if c["name"] != "statuts_regles"]
                return cols
        monkeypatch.setattr(sqlalchemy, "inspect", lambda cible: _Inspecteur(cible))
        demarrer()
        out = capsys.readouterr().out
        assert "COLONNE MANQUANTE entities.statuts_regles" in out
        assert "COLONNE MANQUANTE entities.is_shared" not in out

    def test_table_attendue_absente_ignoree(self, demarrer, monkeypatch, capsys):
        import sqlalchemy
        vrai = sqlalchemy.inspect

        class _Inspecteur:
            def __init__(self, cible):
                self._i = vrai(cible)

            def has_table(self, t):
                return t != "carto_change_requests" and self._i.has_table(t)

            def get_columns(self, t):
                assert t != "carto_change_requests"
                return self._i.get_columns(t)
        monkeypatch.setattr(sqlalchemy, "inspect", lambda cible: _Inspecteur(cible))
        demarrer()
        assert "COLONNE MANQUANTE" not in capsys.readouterr().out

    def test_verification_impossible_dite_sans_bloquer(self, demarrer, monkeypatch, capsys):
        import sqlalchemy
        monkeypatch.setattr(sqlalchemy, "inspect",
                            lambda cible: (_ for _ in ()).throw(RuntimeError("inspect HS")))
        a = demarrer()
        assert "Vérification des colonnes impossible : inspect HS" in capsys.readouterr().out
        assert a.test_client().get("/health").status_code == 200

    def test_create_all_en_echec_signale(self, demarrer, monkeypatch, capsys):
        monkeypatch.setattr(db, "create_all",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ddl HS")))
        demarrer()
        assert "[DB] create_all warning: ddl HS" in capsys.readouterr().out

    def test_alembic_version_alignee_si_table_presente(self, demarrer, capsys):
        a = demarrer()
        with a.app_context():
            with db.engine.connect() as c:
                c.execute(text("CREATE TABLE IF NOT EXISTS alembic_version "
                               "(version_num VARCHAR(32) NOT NULL)"))
                c.execute(text("INSERT INTO alembic_version VALUES ('ancienne')"))
                c.commit()
        capsys.readouterr()
        demarrer()
        assert "alembic_version → b2c3d4e5f6a7" in capsys.readouterr().out
        with a.app_context():
            with db.engine.connect() as c:
                rows = c.execute(text("SELECT version_num FROM alembic_version")).all()
        assert rows == [("b2c3d4e5f6a7",)]

    def test_statut_garant_normalise(self, demarrer):
        from Code.models.models import Activities, Role
        a = demarrer()
        with a.app_context():
            db.session.add_all([Role(id=900, name="R"), Activities(id=900, name="A")])
            db.session.commit()
            with db.engine.connect() as c:
                c.execute(text("INSERT INTO activity_roles (activity_id, role_id, status) "
                               "VALUES (900, 900, 'garant')"))
                c.commit()
        demarrer()
        with a.app_context():
            with db.engine.connect() as c:
                st = c.execute(text("SELECT status FROM activity_roles "
                                    "WHERE activity_id = 900")).scalar()
        assert st == "Garant"

    def test_langue_des_comptes_historiques_remplie(self, demarrer):
        from Code.models.models import DEFAULT_LANG
        a = demarrer()
        with a.app_context():
            with db.engine.connect() as c:
                c.execute(text("INSERT INTO users (first_name, last_name, email, password, "
                               "status, lang) VALUES ('A', 'B', 'ancien@b.fr', 'x', 'user', '')"))
                c.commit()
        demarrer()
        with a.app_context():
            with db.engine.connect() as c:
                lang = c.execute(text("SELECT lang FROM users "
                                      "WHERE email = 'ancien@b.fr'")).scalar()
        assert lang == DEFAULT_LANG


# ── Reprises de données : succès annoncé, échec avalé ─────────────────────

REPRISES = [
    ("Code.permissions", "migrer_anciens_champions", 2,
     "2 compte(s) champion → coordinateur", "[DB] reprise des statuts: boum"),
    ("Code.roles_permanents", "reprendre_roles_hors_carte", 3,
     "3 rôle(s) hors carte protégé(s)", "[DB] reprise des rôles hors carte: boum"),
    ("Code.roles_communs", "fusionner_doublons", 4,
     "4 rôle(s) en double réuni(s)", "[DB] réunion des rôles: boum"),
    ("Code.entites_uniques", "numeroter_doublons", [(7, "Carto", "Carto (2)")],
     "entité #7 : « Carto » -> « Carto (2) »", "[DB] numérotation des cartos homonymes: boum"),
    ("Code.historique_notes", "reprendre_notes_existantes", 5,
     "5 note(s) reprise(s) dans le registre", "[DB] reprise des notes: boum"),
]


class TestReprisesAuDemarrage:

    @pytest.mark.parametrize("module,fonction,retour,annonce,_err", REPRISES,
                             ids=[r[1] for r in REPRISES])
    def test_reprise_annoncee(self, demarrer, monkeypatch, capsys,
                              module, fonction, retour, annonce, _err):
        import importlib
        monkeypatch.setattr(importlib.import_module(module), fonction, lambda: retour)
        demarrer()
        assert annonce in capsys.readouterr().out

    @pytest.mark.parametrize("module,fonction,_ret,_ann,erreur", REPRISES,
                             ids=[r[1] for r in REPRISES])
    def test_reprise_en_echec_ne_bloque_pas(self, demarrer, monkeypatch, capsys,
                                            module, fonction, _ret, _ann, erreur):
        import importlib

        def _boum():
            raise RuntimeError("boum")
        monkeypatch.setattr(importlib.import_module(module), fonction, _boum)
        a = demarrer()
        assert erreur in capsys.readouterr().out
        assert a.test_client().get("/health").status_code == 200

    def test_homonymes_compte_annonce(self, demarrer, monkeypatch, capsys):
        import Code.entites_uniques as eu
        monkeypatch.setattr(eu, "numeroter_doublons",
                            lambda: [(1, "A", "A (2)"), (2, "A", "A (3)")])
        demarrer()
        assert "2 carto(s) homonyme(s) numérotée(s)" in capsys.readouterr().out


# ── Tables créées une à une : un échec n'arrête pas les suivantes ─────────

TABLES = [
    ("FileBlob", "file_blobs check"),
    ("AppSetting", "app_settings check"),
    ("RecentEvent", "recent_events check"),
    ("WelcomeSeen", "welcome_seen check"),
    ("NoteEvaluation", "notes_evaluation check"),
    ("EntrepriseSettings", "entreprise_settings check"),
    ("CrossCartoLiaison", "cross_carto_liaisons check"),
    ("ResultCapabilityLink", "result_capability_links check"),
    ("ResultDiagnostic", "result_diagnostics check"),
    ("PalierPerformance", "paliers check"),
    ("TechnicalDomain", "V1.1 itér.2 tables"),
]


class TestTablesAuDemarrage:

    @pytest.mark.parametrize("modele,message", TABLES, ids=[t[0] for t in TABLES])
    def test_echec_creation_table_signale(self, demarrer, monkeypatch, capsys,
                                          modele, message):
        from Code.models import models

        def _boum(*a, **k):
            raise RuntimeError("table HS")
        monkeypatch.setattr(getattr(models, modele).__table__, "create", _boum)
        a = demarrer()
        out = capsys.readouterr().out
        assert f"{message}: table HS" in out
        assert "Pool connexions réinitialisé" in out
        assert a.test_client().get("/health").status_code == 200

    def test_echec_tables_panel_signale(self, demarrer, monkeypatch, capsys):
        from Code.models import test_models

        def _boum(*a, **k):
            raise RuntimeError("panel HS")
        monkeypatch.setattr(test_models.TestRun.__table__, "create", _boum)
        demarrer()
        assert "[DB] test panel tables: panel HS" in capsys.readouterr().out


# ── Hooks de requête et contexte des gabarits (app de la suite) ───────────

class TestHooksEtContexte:

    def test_racine_mode_test_redirige_login(self, app):
        r = app.test_client().get("/", follow_redirects=False)
        assert r.status_code == 302 and r.headers["Location"].endswith("/login")

    def test_session_perimee_sur_api_rend_401_json(self, app, ids, monkeypatch):
        from Code import mot_de_passe as mdp
        monkeypatch.setattr(mdp, "session_perimee", lambda u, v: True)
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = ids["user_id"]
        r = c.get("/api/inexistante")
        assert r.status_code == 401
        assert r.get_json() == {"error": "session_perimee"}
        with c.session_transaction() as s:
            assert "user_id" not in s

    def test_session_perimee_sur_json_rend_401(self, app, ids, monkeypatch):
        from Code import mot_de_passe as mdp
        monkeypatch.setattr(mdp, "session_perimee", lambda u, v: True)
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = ids["user_id"]
        assert c.get("/quelque/chose.json").status_code == 401

    def test_session_perimee_sur_page_redirige_login(self, app, ids, monkeypatch):
        from Code import mot_de_passe as mdp
        monkeypatch.setattr(mdp, "session_perimee", lambda u, v: True)
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = ids["user_id"]
        r = c.get("/activities/view", follow_redirects=False)
        assert r.status_code == 302 and "/login" in r.headers["Location"]

    def test_incident_de_lecture_ne_deconnecte_personne(self, app, ids, monkeypatch):
        from Code import mot_de_passe as mdp

        def _boum(u, v):
            raise RuntimeError("lecture HS")
        monkeypatch.setattr(mdp, "session_perimee", _boum)
        c = app.test_client()
        with c.session_transaction() as s:
            s["user_id"] = ids["user_id"]
        c.get("/api/inexistante")
        with c.session_transaction() as s:
            assert s.get("user_id") == ids["user_id"]

    def test_bienvenue_en_echec_ne_montre_rien(self, app, monkeypatch):
        import Code.bienvenue as bienvenue
        monkeypatch.setattr(bienvenue, "etat",
                            lambda **k: (_ for _ in ()).throw(RuntimeError("HS")))
        with app.test_request_context("/"):
            ctx = {}
            app.update_template_context(ctx)
        assert ctx["bienvenue"]["montrer"] is False
        assert ctx["bienvenue"]["portes"] == []

    def test_propose_activites_en_echec_rend_faux(self, app, monkeypatch):
        from Code.models.models import Entity
        monkeypatch.setattr(Entity, "get_active",
                            classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("HS"))))
        with app.test_request_context("/"):
            ctx = {}
            app.update_template_context(ctx)
        assert ctx["propose_activites"] is False

    def test_propose_activites_sans_entite_active(self, app, monkeypatch):
        from Code.models.models import Entity
        monkeypatch.setattr(Entity, "get_active", classmethod(lambda cls: None))
        with app.test_request_context("/"):
            ctx = {}
            app.update_template_context(ctx)
        assert ctx["propose_activites"] is False

    def test_contexte_expose_t_et_langue(self, app):
        with app.test_request_context("/"):
            from flask import session
            session["lang"] = "fr"
            ctx = {}
            app.update_template_context(ctx)
        assert ctx["lang"] == "fr" and callable(ctx["t"])


# ── Filtres Jinja ─────────────────────────────────────────────────────────

class TestFiltresJinja:

    @pytest.mark.parametrize("valeur,attendu", [
        ("Niveau 3", "3"), ("2 (Acquisition)", "2"), ("aucun", "1"), (None, "1"), ("", "1")])
    def test_extract_numeric_level(self, app, valeur, attendu):
        assert app.jinja_env.filters["extract_numeric_level"](valeur) == attendu

    def test_escapejs_echappe_quotes_et_antislash(self, app):
        f = app.jinja_env.filters["escapejs"]
        assert f('l\'a "b" \\c') == 'l\\\'a \\"b\\" \\\\c'

    @pytest.mark.parametrize("vide", [None, ""])
    def test_escapejs_vide(self, app, vide):
        assert app.jinja_env.filters["escapejs"](vide) == ""

    def test_filtre_dans_un_gabarit_autoechappe(self, app):
        """Dans un gabarit, l'auto-échappement HTML passe APRÈS escapejs : la
        quote devient `&#39;`, que le navigateur redécode dans un attribut
        (onclick='…') avant de lire le JavaScript."""
        with app.test_request_context("/"):
            rendu = app.jinja_env.from_string(
                "{{ 'Niveau 4' | extract_numeric_level }}|{{ \"a'b\" | escapejs }}").render()
        assert rendu == "4|a\\&#39;b"


# ── Envoi de mail ─────────────────────────────────────────────────────────

class TestCustomMail:

    def test_connexion_smtp_annonce_localhost(self, monkeypatch):
        import flask_mail
        from Code.app import CustomMail
        smtp = smtplib.SMTP()
        monkeypatch.setattr(flask_mail.Mail, "connect", lambda self: smtp)
        assert CustomMail().connect() is smtp
        assert smtp.local_hostname == "localhost"

    def test_connexion_non_smtp_inchangee(self, monkeypatch):
        import flask_mail
        from Code.app import CustomMail
        sentinelle = object()
        monkeypatch.setattr(flask_mail.Mail, "connect", lambda self: sentinelle)
        assert CustomMail().connect() is sentinelle


# ── Petits modules du socle ───────────────────────────────────────────────

class TestSocle:

    def test_verify_password_methode_inconnue_refuse(self):
        from Code.security import verify_password
        assert verify_password("inconnue$sel$empreinte", "x") is False

    def test_reglage_ia_table_illisible_repli_environnement(self, app, monkeypatch):
        """Table absente / base HS : la clé se lit dans l'environnement."""
        import Code.ai_key as ai_key

        def _boum(*a, **k):
            raise RuntimeError("table absente")
        monkeypatch.setattr(db.session, "get", _boum)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
        assert ai_key._setting("anthropic_api_key") is None
        assert ai_key.get_anthropic_key() == "sk-env"
