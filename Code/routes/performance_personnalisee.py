# Code/routes/performance_personnalisee.py
from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy import text, or_
from Code.extensions import db
from Code.models.models import PerformancePersonnalisee

performance_perso_bp = Blueprint("performance_perso", __name__, url_prefix="/performance_perso")

# ---------------- Utils ----------------
def iso_today():
    return datetime.utcnow().strftime("%Y-%m-%d")

def _ts(x):
    try:
        return x.isoformat()
    except Exception:
        return x

def to_dict(p: PerformancePersonnalisee):
    return {
        "id": p.id,
        "user_id": p.user_id,
        "activity_id": p.activity_id,
        "content": p.content or "",
        "validation_status": p.validation_status,
        "validation_date": p.validation_date,
        "created_at": _ts(p.created_at),
        "updated_at": _ts(p.updated_at),
        "deleted": bool(getattr(p, "deleted", False)),
    }

# ---------- Schéma historique (DDL idempotente) ----------
def ensure_history_schema():
    """
    Crée la table d'historique si elle n'existe pas.
    """
    db.session.execute(text("""
        CREATE TABLE IF NOT EXISTS performance_personnalisee_historique (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          performance_id INTEGER,
          user_id INTEGER,
          activity_id INTEGER,
          content TEXT,
          -- compat ancien schéma
          contenu TEXT,
          validation_status TEXT,
          validation_date TEXT,
          event TEXT,
          changed_at TEXT DEFAULT (datetime('now'))
        )
    """))

def insert_history_snapshot_session(perf: PerformancePersonnalisee, *, content: str, status: str, vdate: str, event: str):
    """
    Insert d'historique dans la même transaction.
    """
    db.session.execute(
        text("""
            INSERT INTO performance_personnalisee_historique
              (performance_id, user_id, activity_id, content, validation_status, validation_date, event, changed_at)
            VALUES
              (:performance_id, :user_id, :activity_id, :content, :validation_status, :validation_date, :event, datetime('now'))
        """),
        {
            "performance_id": perf.id,
            "user_id": perf.user_id,
            "activity_id": perf.activity_id,
            "content": content or "",
            "validation_status": status,
            "validation_date": vdate,
            "event": event,
        }
    )

# ---------------- Endpoints ----------------
@performance_perso_bp.route("/list", methods=["GET"])
def list_perf():
    user_id = request.args.get("user_id", type=int)
    activity_id = request.args.get("activity_id", type=int)

    q = PerformancePersonnalisee.query
    if user_id:
        q = q.filter(PerformancePersonnalisee.user_id == user_id)
    if activity_id:
        q = q.filter(PerformancePersonnalisee.activity_id == activity_id)

    try:
        q = q.filter(or_(PerformancePersonnalisee.deleted.is_(False), PerformancePersonnalisee.deleted.is_(None)))
    except Exception:
        pass

    items = q.order_by(PerformancePersonnalisee.updated_at.desc()).all()
    return jsonify([to_dict(p) for p in items])

@performance_perso_bp.route("/create", methods=["POST"])
def create_perf():
    data = request.get_json(force=True) or {}
    user_id = int(data.get("user_id") or 0)
    activity_id = int(data.get("activity_id") or 0)
    content = (data.get("content") or data.get("contenu") or "").strip()

    raw_status = (data.get("validation_status") or "non-validee").strip().lower()
    mapping = {
        "validee": "validee", "validée": "validee", "true": "validee", "1": "validee", "oui": "validee",
        "non-validee": "non-validee", "non validée": "non-validee", "false": "non-validee", "0": "non-validee", "non": "non-validee"
    }
    validation_status = mapping.get(raw_status, "non-validee")
    validation_date = (data.get("validation_date") or iso_today()).strip()

    if not user_id or not activity_id:
        return jsonify({"ok": False, "error": "user_id et activity_id requis"}), 400
    if not content:
        return jsonify({"ok": False, "error": "content requis"}), 400

    ensure_history_schema()

    p = PerformancePersonnalisee(
        user_id=user_id,
        activity_id=activity_id,
        content=content,
        validation_status=validation_status,
        validation_date=validation_date,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        deleted=False
    )
    db.session.add(p)
    db.session.flush()  # pour p.id

    insert_history_snapshot_session(p, content=content, status=validation_status, vdate=validation_date, event="created")

    db.session.commit()
    return jsonify({"ok": True, "item": to_dict(p)})

@performance_perso_bp.route("/update/<int:perf_id>", methods=["PUT"])
def update_perf(perf_id):
    try:
        ensure_history_schema()

        p = PerformancePersonnalisee.query.get(perf_id)
        if p is None:
            # 404 explicite : un get_or_404 lèverait NotFound, capturée plus bas
            # par le `except Exception` et transformée à tort en 500.
            return jsonify({"ok": False, "error": "not_found"}), 404
        data = request.get_json(force=True) or {}

        prev_content = p.content or ""
        prev_status  = p.validation_status
        prev_vdate   = p.validation_date

        new_content = prev_content
        if "contenu" in data and "content" not in data:
            data["content"] = data["contenu"]
        if "content" in data:
            new_content = (str(data["content"]) or "").strip()

        new_status = prev_status
        if "validation_status" in data:
            raw = str(data["validation_status"]).strip().lower()
            mapping = {
                "validee": "validee", "validée": "validee", "true": "validee", "1": "validee", "oui": "validee",
                "non-validee": "non-validee", "non validée": "non-validee", "false": "non-validee", "0": "non-validee", "non": "non-validee"
            }
            new_status = mapping.get(raw, prev_status)

        new_vdate = prev_vdate
        if "validation_date" in data:
            new_vdate = (data["validation_date"] or None)
        elif ("validation_status" in data) and (new_status != prev_status) and not new_vdate:
            new_vdate = iso_today()

        changed = (new_content != prev_content) or (new_status != prev_status) or (new_vdate != prev_vdate)
        if not changed:
            return jsonify({"ok": True, "item": to_dict(p)})

        insert_history_snapshot_session(p, content=prev_content, status=prev_status, vdate=prev_vdate, event="before_update")

        p.content = new_content
        p.validation_status = new_status
        p.validation_date = new_vdate
        p.updated_at = datetime.utcnow().isoformat()

        db.session.commit()

        return jsonify({"ok": True, "item": to_dict(p)})

    except Exception as e:
        print("[update_perf] unexpected error:", e)
        db.session.rollback()
        return jsonify({"ok": False, "error": "update_failed"}), 500

@performance_perso_bp.route("/delete/<int:perf_id>", methods=["DELETE"])
def delete_perf(perf_id):
    ensure_history_schema()
    p = PerformancePersonnalisee.query.get_or_404(perf_id)

    insert_history_snapshot_session(
        p,
        content=(p.content or ""),
        status=p.validation_status,
        vdate=p.validation_date,
        event="deleted"
    )

    p.deleted = True
    p.updated_at = datetime.utcnow().isoformat()
    db.session.commit()

    return jsonify({"ok": True})

@performance_perso_bp.route("/history", methods=["GET"])
def history_perf():
    """Historique de toutes les perfs d'un couple (user_id, activity_id)."""
    ensure_history_schema()
    user_id = request.args.get("user_id", type=int)
    activity_id = request.args.get("activity_id", type=int)

    res = db.session.execute(text("""
        SELECT performance_id,
               COALESCE(content, contenu) AS content,
               validation_status,
               validation_date,
               event,
               changed_at
        FROM performance_personnalisee_historique
        WHERE user_id = :uid AND activity_id = :aid
        ORDER BY changed_at DESC, id DESC
    """), {"uid": user_id, "aid": activity_id})

    rows = [dict(row) for row in res.mappings()]
    return jsonify({"history": rows})

@performance_perso_bp.route("/history/<int:perf_id>", methods=["GET"])
def history_by_perf(perf_id: int):
    """Historique détaillé pour UNE performance."""
    ensure_history_schema()

    res = db.session.execute(text("""
        SELECT performance_id,
               COALESCE(content, contenu) AS content,
               validation_status,
               validation_date,
               event,
               changed_at
        FROM performance_personnalisee_historique
        WHERE performance_id = :pid
        ORDER BY changed_at DESC, id DESC
    """), {"pid": perf_id})

    rows = [dict(row) for row in res.mappings()]
    return jsonify({"performance_id": perf_id, "history": rows})

@performance_perso_bp.route("/history/<int:perf_id>", methods=["DELETE"])
def delete_history_by_perf(perf_id: int):
    ensure_history_schema()
    db.session.execute(
        text("DELETE FROM performance_personnalisee_historique WHERE performance_id = :pid"),
        {"pid": perf_id}
    )
    db.session.commit()
    return jsonify({"ok": True, "performance_id": perf_id, "purged": True})

