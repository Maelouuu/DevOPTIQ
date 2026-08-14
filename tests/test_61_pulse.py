"""
Tests OptiqPulse — suivi des utilisateurs.

1. Instrumentation de l'app (Code/routes/pulse_track.py) : pages vues, actions
   et battements écrits en base ; endpoints « bruit » ignorés ; télémétrie
   désactivée par défaut sous TESTING (pas de pollution de la suite).
2. Agrégations du service pulse/ (aggregates.py) sur SQLite : en ligne, pic de
   simultanés, temps par page, séries journalières, parcours.
3. App Flask pulse : login unique, protection des APIs, overview de bout en bout.
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PULSE_DIR = os.path.join(REPO, "pulse")
sys.path.insert(0, PULSE_DIR)

import aggregates  # noqa: E402  (pulse/aggregates.py)


# ---------------------------------------------------------------------------
# 1. Instrumentation dans l'app principale
# ---------------------------------------------------------------------------

class TestInstrumentation:

    def test_disabled_by_default_under_testing(self, app, auth_client):
        from Code.models.models import UsageEvent
        with app.app_context():
            before = UsageEvent.query.count()
        auth_client.get("/activities/view")
        with app.app_context():
            assert UsageEvent.query.count() == before

    def test_view_action_beat_recorded(self, app, auth_client):
        from Code.models.models import UsageBeat, UsageEvent
        app.config["PULSE_FORCE"] = True
        try:
            auth_client.get("/activities/view")
            auth_client.post("/pulse/beat", json={"path": "/activities/view"})
            with app.app_context():
                ev = (UsageEvent.query.filter_by(path="/activities/view",
                                                 kind="view")
                      .order_by(UsageEvent.id.desc()).first())
                assert ev is not None
                assert ev.user_id is not None
                assert ev.session_key
                assert ev.method == "GET"
                assert ev.status == 200
                assert ev.duration_ms is not None and ev.duration_ms >= 0
                beat = UsageBeat.query.order_by(UsageBeat.id.desc()).first()
                assert beat is not None
                assert beat.user_id == ev.user_id
                assert beat.path == "/activities/view"
        finally:
            app.config["PULSE_FORCE"] = False
            with app.app_context():
                from Code.extensions import db
                UsageEvent.query.delete()
                UsageBeat.query.delete()
                db.session.commit()

    def test_noise_endpoints_never_logged(self, app, auth_client):
        from Code.models.models import UsageEvent
        app.config["PULSE_FORCE"] = True
        try:
            auth_client.get("/static/optiq.css")
            auth_client.get("/parametres/admin/logs")
            auth_client.post("/pulse/beat", json={})
            with app.app_context():
                noisy = UsageEvent.query.filter(
                    sa.or_(UsageEvent.path.like("/static%"),
                           UsageEvent.path.like("/pulse%"),
                           UsageEvent.path.like("/parametres/admin/logs%"))
                ).count()
                assert noisy == 0
        finally:
            app.config["PULSE_FORCE"] = False
            with app.app_context():
                from Code.extensions import db
                UsageEvent.query.delete()
                db.session.commit()

    def test_beat_requires_login_but_never_errors(self, app):
        from Code.models.models import UsageBeat
        app.config["PULSE_FORCE"] = True
        try:
            with app.app_context():
                before = UsageBeat.query.count()
            anon = app.test_client()          # client NON authentifié
            r = anon.post("/pulse/beat", json={"path": "/x"})
            assert r.status_code == 204
            with app.app_context():
                assert UsageBeat.query.count() == before
        finally:
            app.config["PULSE_FORCE"] = False


# ---------------------------------------------------------------------------
# 2. Agrégations du service pulse/
# ---------------------------------------------------------------------------

@pytest.fixture()
def pulse_source(tmp_path):
    """Base SQLite imitant une instance : 2 utilisateurs, Alice en ligne
    (battements jusqu'à il y a 1 min), Bob parti il y a 6 min ; recouvrement
    de présence entre -8 et -6 min → pic de 2 simultanés.
    L'heure de référence est capturée ICI (pas à l'import du module) : la
    fenêtre « en ligne » fait 3 min, une suite complète qui met plus de
    2 min à atteindre ce module rendrait Alice hors ligne (faux échec
    d'isolation constaté sur staging, suite à 1694 tests)."""
    NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    db_path = tmp_path / "instance.db"
    eng = sa.create_engine(f"sqlite:///{db_path}")
    with eng.begin() as c:
        c.exec_driver_sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, first_name TEXT,"
            " last_name TEXT, email TEXT)")
        c.exec_driver_sql(
            "CREATE TABLE usage_events (id INTEGER PRIMARY KEY, ts TIMESTAMP,"
            " user_id INTEGER, session_key TEXT, kind TEXT, method TEXT,"
            " path TEXT, endpoint TEXT, status INTEGER, duration_ms INTEGER)")
        c.exec_driver_sql(
            "CREATE TABLE usage_beats (id INTEGER PRIMARY KEY, ts TIMESTAMP,"
            " user_id INTEGER, session_key TEXT, path TEXT)")
        c.exec_driver_sql(
            "INSERT INTO users VALUES (1,'Alice','Martin','alice@x.fr'),"
            " (2,'Bob','Durand','bob@x.fr')")

        def add_beat(ts, uid, sess, path):
            c.execute(sa.text("INSERT INTO usage_beats (ts, user_id,"
                              " session_key, path) VALUES (:t,:u,:s,:p)"),
                      {"t": ts.replace(tzinfo=None), "u": uid, "s": sess,
                       "p": path})

        for mins in range(9, 0, -1):          # -9 … -1 min
            add_beat(NOW - timedelta(minutes=mins), 1, "sa1",
                     "/activities/view")
        for mins in (8, 7, 6):                # -8 … -6 min
            add_beat(NOW - timedelta(minutes=mins), 2, "sb1", "/competences/")

        def add_event(ts, uid, sess, kind, method, path, status=200):
            c.execute(sa.text(
                "INSERT INTO usage_events (ts, user_id, session_key, kind,"
                " method, path, endpoint, status, duration_ms)"
                " VALUES (:t,:u,:s,:k,:m,:p,NULL,:st,42)"),
                {"t": ts.replace(tzinfo=None), "u": uid, "s": sess, "k": kind,
                 "m": method, "p": path, "st": status})

        add_event(NOW - timedelta(minutes=9), 1, "sa1", "view", "GET",
                  "/activities/view")
        add_event(NOW - timedelta(minutes=5), 1, "sa1", "view", "GET",
                  "/activities/view")
        add_event(NOW - timedelta(minutes=4), 1, "sa1", "action", "POST",
                  "/tasks/add", 302)
        add_event(NOW - timedelta(minutes=8), 2, "sb1", "view", "GET",
                  "/competences/")
    eng.dispose()
    return {"name": "Test", "url": f"sqlite:///{db_path}", "now": NOW}


def _window(pulse_source, days=7):
    return aggregates.load_window(pulse_source,
                                  pulse_source["now"] - timedelta(days=days))


class TestAggregates:

    def test_load_window(self, pulse_source):
        w = _window(pulse_source)
        assert w["ok"] and w["error"] is None
        assert w["users"][1]["name"] == "Alice Martin"
        assert len(w["beats"]) == 12
        assert len(w["events"]) == 4
        assert w["events"][0]["ts"].tzinfo is not None

    def test_summarize_tiles_and_online(self, pulse_source):
        s = aggregates.summarize([("Test", _window(pulse_source))], "7d",
                                 now=pulse_source["now"])
        assert s["errors"] == []
        # Alice a battu il y a 1 min → en ligne ; Bob (6 min) → hors ligne
        assert s["tiles"]["online_now"] == 1
        assert s["online"][0]["user"] == "Alice Martin"
        assert s["online"][0]["label"] == "Liste des activités"
        # Recouvrement -8/-6 min → 2 simultanés
        assert s["tiles"]["peak"] == 2
        assert s["tiles"]["unique_users"] == 2
        assert s["tiles"]["views"] == 3
        assert s["tiles"]["actions"] == 1
        # Alice ≈ 8 gaps × 60 s + 30 s ; Bob ≈ 2 × 60 + 30 → ~11 min au total
        assert 9 <= s["tiles"]["total_minutes"] <= 13

    def test_summarize_daily_and_pages(self, pulse_source):
        s = aggregates.summarize([("Test", _window(pulse_source))], "7d",
                                 now=pulse_source["now"])
        assert len(s["daily"]) == 7
        today = s["daily"][-1]
        assert today["users"] == 2
        assert today["views"] == 3
        assert today["peak"] == 2
        views = {p["label"]: p["value"] for p in s["pages_views"]}
        assert views["Liste des activités"] == 2
        assert views["Compétences"] == 1
        times = {p["label"]: p["value"] for p in s["pages_time"]}
        assert times["Liste des activités"] >= 7   # ~8,5 min

    def test_summarize_users_and_journey(self, pulse_source):
        w = _window(pulse_source)
        s = aggregates.summarize([("Test", w)], "7d", now=pulse_source["now"])
        assert [u["name"] for u in s["users"]][0] == "Alice Martin"
        alice = s["users"][0]
        assert alice["online"] is True
        assert alice["views"] == 2 and alice["actions"] == 1
        assert alice["sessions"] == 1
        assert "Liste des activités" in alice["top_pages"]

        j = aggregates.user_journey(w, 1)
        assert len(j) == 3
        assert j[0]["ts"] >= j[-1]["ts"]          # plus récent d'abord
        kinds = {r["kind"] for r in j}
        assert kinds == {"view", "action"}
        first_view = next(r for r in j if r["kind"] == "view")
        assert first_view["page_minutes"] >= 7

    def test_source_error_is_graceful(self):
        bad = {"name": "Morte", "url": "sqlite:///nonexistent/dir/x.db"}
        now = datetime.now(timezone.utc)
        w = aggregates.load_window(bad, now - timedelta(days=7))
        assert w["ok"] is False and w["error"]
        s = aggregates.summarize([("Morte", w)], "7d", now=now)
        assert s["errors"][0]["source"] == "Morte"
        assert s["tiles"]["online_now"] == 0

    def test_page_labels(self):
        assert aggregates.page_label("/activities/map") == "Cartographie"
        assert aggregates.page_label("/activities/12/details") == "Fiche activité"
        assert aggregates.page_label("/temps/vue") == "Temps"
        assert aggregates.page_label("/chemin/inconnu") == "/chemin/inconnu"


# ---------------------------------------------------------------------------
# 3. App Flask du service pulse/
# ---------------------------------------------------------------------------

@pytest.fixture()
def pulse_app(pulse_source, monkeypatch):
    monkeypatch.setenv("PULSE_DBS", json.dumps(
        [{"name": pulse_source["name"], "url": pulse_source["url"]}]))
    monkeypatch.setenv("PULSE_INSECURE_COOKIE", "1")
    monkeypatch.delenv("PULSE_PASSWORD", raising=False)
    monkeypatch.delenv("PULSE_PASSWORD_HASH", raising=False)
    spec = importlib.util.spec_from_file_location(
        "pulse_service_app", os.path.join(PULSE_DIR, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.app.config["TESTING"] = True
    return mod.app


class TestPulseApp:

    def test_everything_locked_without_login(self, pulse_app):
        c = pulse_app.test_client()
        assert c.get("/").status_code == 302
        assert c.get("/api/overview").status_code == 401
        assert c.get("/api/journey?src=Test&user=1").status_code == 401
        assert c.get("/healthz").status_code == 200
        assert c.get("/health").status_code == 200
        assert "Disallow: /" in c.get("/robots.txt").get_data(as_text=True)

    def test_login_wrong_then_right(self, pulse_app):
        c = pulse_app.test_client()
        r = c.post("/login", data={"username": "Mael_Girardin",
                                   "password": "mauvais"})
        assert r.status_code == 200
        assert "incorrect" in r.get_data(as_text=True)
        r = c.post("/login", data={"username": "Mael_Girardin",
                                   "password": "testtest"})
        assert r.status_code == 302
        assert c.get("/").status_code == 200

    def test_rate_limit(self, pulse_app):
        c = pulse_app.test_client()
        for _ in range(8):
            c.post("/login", data={"username": "x", "password": "y"})
        r = c.post("/login", data={"username": "Mael_Girardin",
                                   "password": "testtest"})
        assert "Trop de tentatives" in r.get_data(as_text=True)

    def test_overview_end_to_end(self, pulse_app):
        c = pulse_app.test_client()
        c.post("/login", data={"username": "Mael_Girardin",
                               "password": "testtest"})
        r = c.get("/api/overview?range=7d")
        assert r.status_code == 200
        data = r.get_json()
        # Les battements de la fixture sont relatifs à l'heure réelle :
        # Alice (battement il y a ~1 min) est vue en ligne de bout en bout.
        assert data["tiles"]["online_now"] == 1
        assert data["tiles"]["peak"] == 2
        assert len(data["daily"]) == 7
        assert data["users"][0]["name"] == "Alice Martin"

        r = c.get("/api/journey?src=Test&user=1&range=7d")
        assert r.status_code == 200
        assert len(r.get_json()["journey"]) == 3

        assert c.get("/api/overview?range=zzz").status_code == 400
        assert c.get("/api/journey?src=Inconnue&user=1").status_code == 400
