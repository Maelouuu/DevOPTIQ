# OptiqPulse — image minimale (service séparé de l'app principale).
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080 PYTHONUNBUFFERED=1
# 1 worker : l'anti-force-brute et le cache d'engines sont en mémoire ;
# 8 threads suffisent largement pour un dashboard mono-utilisateur.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 90 app:app
