# Optiq Hub — image minimale (service séparé de l'app, comme OptiqPulse).
#
# ⚠️ La documentation (docs/) est copiée dans hub/_docs AVANT le build par le
# workflow : le .dockerignore de la racine exclut docs/, et le contexte de
# build est hub/ pour rester indépendant de l'image applicative.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080 PYTHONUNBUFFERED=1
# 1 worker : le cache d'état des instances vit en mémoire, et les sondes
# partent déjà en parallèle dans un pool de threads.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 90 app:app
