"""Instance jetable pour reproduire un import de paquet .optiqcarto.

Usage : python tools/devrun_carto_check.py [carto.json|carto.optiqcarto]

Crée une base SQLite temporaire, deux comptes (source/cible), injecte la carto
sur le compte source, et sert l'app sur http://127.0.0.1:8123.
  source : source@test.local  / Test1234!
  cible  : cible@test.local   / Test1234!
Outil de mise au point AFDEC — pas embarqué dans l'image client (tools/ est
exclu par .dockerignore).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CARTO = sys.argv[1] if len(sys.argv) > 1 else "tools/provisioning/carto/map_rfq_fluidclip.json"

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

from Code.app import create_app                      # noqa: E402
from Code.extensions import db                       # noqa: E402

app = create_app(test_config={
    "TESTING": False,
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
    "SECRET_KEY": "dev-carto-check",
    "WTF_CSRF_ENABLED": False,
    "MAIL_SUPPRESS_SEND": True,
})

with app.app_context():
    from werkzeug.security import generate_password_hash
    from Code.models.models import Entity, User
    from Code.routes.cartography_editor import _sync_carto_to_db

    db.drop_all()
    db.create_all()

    payload = json.load(open(CARTO, encoding="utf-8"))
    diagram = payload.get("diagram") if payload.get("format") == "optiqcarto/entity" else payload

    src = User(first_name="Source", last_name="Compte", email="source@test.local",
               password=generate_password_hash("Test1234!"), status="admin")
    dst = User(first_name="Cible", last_name="Compte", email="cible@test.local",
               password=generate_password_hash("Test1234!"), status="admin")
    db.session.add_all([src, dst])
    db.session.commit()

    ent = Entity(name="ARaymond — RFQ FluidClip", description="carto de référence",
                 owner_id=src.id, is_active=True,
                 optiqcarto_data=json.dumps(diagram, ensure_ascii=False))
    db.session.add(ent)
    db.session.commit()
    _sync_carto_to_db(ent, diagram)

    print(f"[devrun] base   : {db_path}")
    print(f"[devrun] carto  : {CARTO} — {len(diagram.get('shapes', []))} formes, "
          f"{len(diagram.get('connections', []))} connexions")
    print(f"[devrun] source : source@test.local / Test1234!  (entité {ent.id})")
    print(f"[devrun] cible  : cible@test.local  / Test1234!  (aucune entité)")

app.run(host="127.0.0.1", port=8123, debug=False, use_reloader=False)
