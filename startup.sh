#!/bin/sh
set -e

echo "[STARTUP] Setup DB (migrations + colonnes)..."
python -c "
from Code.app import create_app
create_app()
print('[STARTUP] DB setup terminé.')
"

echo "[STARTUP] Lancement gunicorn (SKIP_DB_SETUP=1)..."
export SKIP_DB_SETUP=1
exec gunicorn \
  -w 2 \
  -b 0.0.0.0:8080 \
  --timeout 120 \
  Code.app:app
