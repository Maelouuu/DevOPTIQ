#!/bin/sh
# Toute la config (workers, port, timeout) vit dans gunicorn.conf.py —
# ajustable via WEB_CONCURRENCY / PORT sans toucher à l'image.
exec gunicorn -c gunicorn.conf.py Code.app:app
