# OptiqPulse — lecture des bases des instances + agrégations.
# Chaque instance d'app (base Neon) expose usage_events / usage_beats / users ;
# ici on lit en SEULE LECTURE et on agrège en Python (volumes faibles : quelques
# milliers de lignes/jour) — 100 % portable, donc testable sur SQLite.

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

PARIS = ZoneInfo("Europe/Paris")

# Présence : un battement toutes les ~60 s onglet visible.
ONLINE_WINDOW_MIN = 3          # « en ligne » = battement dans les 3 dernières minutes
GAP_CAP_S = 90                 # delta max compté entre 2 battements (au-delà : absence)
LONE_BEAT_S = 30               # crédit nominal d'un battement isolé

RANGES = {"today": 1, "7d": 7, "30d": 30, "90d": 90}

# Libellés FR des pages (préfixes réels des blueprints de l'app).
_PAGE_LABELS = [
    (r"^/activities/map", "Cartographie"),
    (r"^/cartography", "Éditeur de cartographie"),
    (r"^/activities/view", "Liste des activités"),
    (r"^/activities/\d+", "Fiche activité"),
    (r"^/activities", "Activités (API)"),
    (r"^/roles_view", "Page Rôles"),
    (r"^/roles", "Rôles (API)"),
    (r"^/competences", "Compétences"),
    (r"^/projection", "Projection métier"),
    (r"^/temps", "Temps"),
    (r"^/comptes", "Comptes"),
    (r"^/gestion_rh", "Gestion RH"),
    (r"^/tools", "Outils"),
    (r"^/parametres", "Paramètres"),
    (r"^/login", "Connexion"),
    (r"^/logout", "Déconnexion"),
    (r"^/api/chatbot", "Chatbot IA"),
    (r"^/api/import", "Import IA"),
    (r"^/export", "Export"),
    (r"^/testpanel", "Panel de tests"),
    (r"^/tasks", "Tâches"),
    (r"^/savoir_faires", "Savoir-faire"),
    (r"^/savoirs", "Savoirs"),
    (r"^/aptitudes", "Aptitudes"),
    (r"^/(softskills|skills|translate_softskills)", "HSC"),
    (r"^/qualify", "Qualification des sorties"),
    (r"^/mastery", "Évaluation des résultats"),
    (r"^/diagnostic", "Diagnostic d'écart"),
    (r"^/domains", "Domaines techniques"),
    (r"^/cadence", "Cadence"),
    (r"^/hsc", "Positionnement HSC"),
    (r"^/setup", "Assistant d'installation"),
    (r"^/$", "Accueil"),
]
_PAGE_LABELS = [(re.compile(p), l) for p, l in _PAGE_LABELS]


def page_label(path):
    for rx, label in _PAGE_LABELS:
        if rx.match(path or ""):
            return label
    return path or "?"


def load_sources():
    """Instances suivies : env PULSE_DBS (JSON [{name,url}]) ou PULSE_DBS_B64
    (même JSON en base64 — évite tout escaping dans gcloud/CI)."""
    raw = os.getenv("PULSE_DBS", "").strip()
    if not raw:
        b64 = os.getenv("PULSE_DBS_B64", "").strip()
        if b64:
            raw = base64.b64decode(b64).decode("utf-8")
    if not raw:
        return []
    items = json.loads(raw)
    out = []
    for it in items:
        url = (it.get("url") or "").strip()
        if not url:
            continue
        if url.startswith("postgres://"):  # Neon donne parfois l'ancien schéma
            url = "postgresql://" + url[len("postgres://"):]
        out.append({"name": it.get("name") or "Instance", "url": url})
    return out


_ENGINES = {}


def _engine(url):
    eng = _ENGINES.get(url)
    if eng is None:
        eng = create_engine(url, pool_size=2, max_overflow=2, pool_pre_ping=True,
                            pool_recycle=280)
        _ENGINES[url] = eng
    return eng


def _utc(dt):
    """Les timestamps sont stockés naïfs en UTC par l'app."""
    if dt is None:
        return None
    if isinstance(dt, str):  # SQLite renvoie des chaînes
        dt = datetime.fromisoformat(dt.split("+")[0])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def range_start(range_key, now=None):
    now = now or datetime.now(timezone.utc)
    if range_key == "today":
        local = now.astimezone(PARIS)
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.astimezone(timezone.utc)
    days = RANGES.get(range_key, 7)
    return now - timedelta(days=days)


def load_window(source, start_utc):
    """Lit users + events + beats d'une instance depuis start_utc.
    Renvoie {"ok": bool, "error": str|None, users, events, beats}."""
    out = {"ok": True, "error": None, "users": {}, "events": [], "beats": []}
    try:
        eng = _engine(source["url"])
        with eng.connect() as conn:
            rows = conn.execute(text(
                "SELECT id, first_name, last_name, email FROM users"))
            for r in rows:
                name = f"{(r[1] or '').strip()} {(r[2] or '').strip()}".strip()
                out["users"][r[0]] = {"name": name or (r[3] or f"user {r[0]}"),
                                      "email": r[3] or ""}
            rows = conn.execute(text(
                "SELECT ts, user_id, session_key, kind, method, path, endpoint,"
                " status, duration_ms FROM usage_events WHERE ts >= :s"
                " ORDER BY ts"), {"s": start_utc.replace(tzinfo=None)})
            out["events"] = [{
                "ts": _utc(r[0]), "user_id": r[1], "session_key": r[2],
                "kind": r[3], "method": r[4], "path": r[5] or "",
                "endpoint": r[6], "status": r[7], "duration_ms": r[8],
            } for r in rows]
            rows = conn.execute(text(
                "SELECT ts, user_id, session_key, path FROM usage_beats"
                " WHERE ts >= :s ORDER BY session_key, ts"),
                {"s": start_utc.replace(tzinfo=None)})
            out["beats"] = [{
                "ts": _utc(r[0]), "user_id": r[1], "session_key": r[2],
                "path": r[3] or "",
            } for r in rows]
    except Exception as e:
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _beat_spans(beats):
    """Deltas de présence entre battements consécutifs d'une même session.
    Rend des tranches (user_id, path, start_ts, seconds) attribuées à la page
    du battement de départ."""
    spans = []
    by_session = {}
    for b in beats:
        key = b["session_key"] or f"u{b['user_id']}"
        by_session.setdefault(key, []).append(b)
    for sess in by_session.values():
        sess.sort(key=lambda b: b["ts"])
        for prev, cur in zip(sess, sess[1:]):
            gap = (cur["ts"] - prev["ts"]).total_seconds()
            secs = gap if 0 < gap <= GAP_CAP_S else LONE_BEAT_S
            spans.append((prev["user_id"], prev["path"], prev["ts"], secs))
        spans.append((sess[-1]["user_id"], sess[-1]["path"], sess[-1]["ts"],
                      LONE_BEAT_S))
    return spans


def _minute_presence(beats):
    """minute (datetime UTC arrondi) → set de user_id présents. Chaque battement
    marque sa minute et la suivante (couvre la dérive du période 60 s)."""
    presence = {}
    for b in beats:
        m = b["ts"].replace(second=0, microsecond=0)
        for mm in (m, m + timedelta(minutes=1)):
            presence.setdefault(mm, set()).add(b["user_id"])
    return presence


def summarize(windows, range_key, now=None):
    """Agrège une liste de (source_name, window) en un payload dashboard.
    Les identités utilisateur sont préfixées par l'instance (pas de collision
    d'ids entre bases)."""
    now = now or datetime.now(timezone.utc)
    errors = [{"source": name, "error": w["error"]}
              for name, w in windows if not w["ok"]]
    live = [(name, w) for name, w in windows if w["ok"]]

    def uname(name, w, uid):
        info = w["users"].get(uid)
        return info["name"] if info else f"utilisateur {uid}"

    # --- En ligne maintenant -------------------------------------------------
    online = []
    online_keys = set()
    cutoff = now - timedelta(minutes=ONLINE_WINDOW_MIN)
    for name, w in live:
        last = {}
        for b in w["beats"]:
            if b["ts"] >= cutoff:
                cur = last.get(b["user_id"])
                if cur is None or b["ts"] > cur["ts"]:
                    last[b["user_id"]] = b
        for uid, b in last.items():
            online_keys.add((name, uid))
            online.append({
                "user": uname(name, w, uid), "source": name,
                "path": b["path"], "label": page_label(b["path"]),
                "since_min": max(0, int((now - b["ts"]).total_seconds() // 60)),
            })
    online.sort(key=lambda o: o["since_min"])

    # --- Séries temporelles (jours Europe/Paris) -----------------------------
    daily = {}
    hourly = {}
    pages_views = {}
    pages_time = {}
    per_user = {}
    all_minutes = {}

    def day_of(ts):
        return ts.astimezone(PARIS).strftime("%Y-%m-%d")

    for name, w in live:
        for e in w["events"]:
            d = daily.setdefault(day_of(e["ts"]), {
                "users": set(), "views": 0, "actions": 0, "seconds": 0.0})
            if e["user_id"] is not None:
                d["users"].add((name, e["user_id"]))
            if e["kind"] == "view":
                d["views"] += 1
                pages_views[e["path"]] = pages_views.get(e["path"], 0) + 1
            else:
                d["actions"] += 1
            h = e["ts"].astimezone(PARIS).strftime("%H")
            hh = hourly.setdefault(h, {"users": set(), "views": 0})
            if e["user_id"] is not None:
                hh["users"].add((name, e["user_id"]))
            if e["kind"] == "view":
                hh["views"] += 1
            if e["user_id"] is not None:
                u = per_user.setdefault((name, e["user_id"]), {
                    "views": 0, "actions": 0, "seconds": 0.0,
                    "sessions": set(), "last_seen": e["ts"], "paths": {}})
                u["views" if e["kind"] == "view" else "actions"] += 1
                if e["session_key"]:
                    u["sessions"].add(e["session_key"])
                u["last_seen"] = max(u["last_seen"], e["ts"])

        for uid, path, ts, secs in _beat_spans(w["beats"]):
            daily.setdefault(day_of(ts), {
                "users": set(), "views": 0, "actions": 0, "seconds": 0.0,
            })["seconds"] += secs
            pages_time[path] = pages_time.get(path, 0) + secs
            u = per_user.setdefault((name, uid), {
                "views": 0, "actions": 0, "seconds": 0.0,
                "sessions": set(), "last_seen": ts, "paths": {}})
            u["seconds"] += secs
            u["last_seen"] = max(u["last_seen"], ts)
            u["paths"][path] = u["paths"].get(path, 0) + secs

        for minute, uids in _minute_presence(w["beats"]).items():
            all_minutes.setdefault(minute, set()).update(
                (name, uid) for uid in uids)

    # Pic de connectés simultanés — global et par jour
    peak = 0
    peak_by_day = {}
    for minute, keys in all_minutes.items():
        n = len(keys)
        peak = max(peak, n)
        d = day_of(minute)
        peak_by_day[d] = max(peak_by_day.get(d, 0), n)

    # Série journalière continue (jours sans activité inclus)
    days_out = []
    n_days = 1 if range_key == "today" else RANGES.get(range_key, 7)
    today_local = now.astimezone(PARIS).date()
    for i in range(n_days - 1, -1, -1):
        d = (today_local - timedelta(days=i)).strftime("%Y-%m-%d")
        row = daily.get(d, {"users": set(), "views": 0, "actions": 0,
                            "seconds": 0.0})
        days_out.append({
            "date": d, "users": len(row["users"]), "views": row["views"],
            "actions": row["actions"], "minutes": round(row["seconds"] / 60),
            "peak": peak_by_day.get(d, 0),
        })

    active_days = [r for r in days_out if r["users"] > 0]
    avg_users = (round(sum(r["users"] for r in active_days) / len(active_days), 1)
                 if active_days else 0)
    total_seconds = sum(r["seconds"] for r in daily.values())
    total_views = sum(r["views"] for r in days_out)
    total_actions = sum(r["actions"] for r in days_out)
    uniq_users = set()
    for name, w in live:
        for e in w["events"]:
            if e["user_id"] is not None:
                uniq_users.add((name, e["user_id"]))
        for b in w["beats"]:
            uniq_users.add((name, b["user_id"]))

    def top_pages(counter, is_time):
        agg = {}
        for path, v in counter.items():
            label = page_label(path)
            agg[label] = agg.get(label, 0) + v
        rows = sorted(agg.items(), key=lambda kv: -kv[1])[:12]
        return [{"label": l,
                 "value": round(v / 60) if is_time else v} for l, v in rows]

    users_out = []
    for (name, uid), u in per_user.items():
        w = dict(live).get(name)
        top = sorted(u["paths"].items(), key=lambda kv: -kv[1])[:3]
        users_out.append({
            "key": f"{name}::{uid}", "source": name, "user_id": uid,
            "name": uname(name, w, uid) if w else f"utilisateur {uid}",
            "email": (w["users"].get(uid) or {}).get("email", "") if w else "",
            "online": (name, uid) in online_keys,
            "last_seen": u["last_seen"].isoformat(),
            "minutes": round(u["seconds"] / 60),
            "views": u["views"], "actions": u["actions"],
            "sessions": len(u["sessions"]),
            "top_pages": [page_label(p) for p, _ in top],
        })
    users_out.sort(key=lambda r: (not r["online"], r["last_seen"]), reverse=False)
    users_out.sort(key=lambda r: r["last_seen"], reverse=True)
    users_out.sort(key=lambda r: not r["online"])

    hours_out = [{"hour": f"{h:02d}", **{
        "users": len(hourly.get(f"{h:02d}", {"users": set()})["users"]),
        "views": hourly.get(f"{h:02d}", {"views": 0})["views"],
    }} for h in range(24)]

    return {
        "generated_at": now.isoformat(),
        "range": range_key,
        "errors": errors,
        "online": online,
        "tiles": {
            "online_now": len(online_keys),
            "peak": peak,
            "avg_daily_users": avg_users,
            "unique_users": len(uniq_users),
            "total_minutes": round(total_seconds / 60),
            "views": total_views,
            "actions": total_actions,
        },
        "daily": days_out,
        "hourly": hours_out,
        "pages_views": top_pages(pages_views, is_time=False),
        "pages_time": top_pages(pages_time, is_time=True),
        "users": users_out,
    }


def user_journey(window, user_id, limit=400):
    """Parcours chronologique d'un utilisateur : événements + temps par page
    (depuis les battements), du plus récent au plus ancien."""
    if not window["ok"]:
        return []
    time_by_page = {}
    for uid, path, ts, secs in _beat_spans(window["beats"]):
        if uid == user_id:
            time_by_page[path] = time_by_page.get(path, 0) + secs
    rows = []
    for e in window["events"]:
        if e["user_id"] != user_id:
            continue
        rows.append({
            "ts": e["ts"].astimezone(PARIS).isoformat(),
            "kind": e["kind"], "method": e["method"], "path": e["path"],
            "label": page_label(e["path"]), "status": e["status"],
            "duration_ms": e["duration_ms"],
            "page_minutes": (round(time_by_page.get(e["path"], 0) / 60)
                             if e["kind"] == "view" else None),
        })
    rows.sort(key=lambda r: r["ts"], reverse=True)
    return rows[:limit]
