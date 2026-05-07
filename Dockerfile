# Dockerfile — AFDEC / Flask → Cloud Run
FROM python:3.12-slim

# ==========================================================
# 1) Dépendances système (LibreOffice + outils nécessaires)
# ==========================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        fonts-dejavu \
        build-essential \
        curl \
        unzip \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Fix locale UTF-8 (nécessaire pour LibreOffice)
ENV LANG=fr_FR.UTF-8
ENV LANGUAGE=fr_FR:fr
ENV LC_ALL=fr_FR.UTF-8
RUN sed -i '/fr_FR.UTF-8/s/^# //g' /etc/locale.gen || true

# ==========================================================
# 2) Répertoire de travail
# ==========================================================
WORKDIR /app

# ==========================================================
# 3) Dépendances Python (Flask, SQLAlchemy, dotenv, etc.)
# ==========================================================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

# ==========================================================
# 4) Code source
# ==========================================================
COPY . .

# ==========================================================
# 5) Cloud Run utilise la variable d'environnement PORT
# ==========================================================
ENV PORT=8080

# ==========================================================
# 6) Lancement Gunicorn (production)
# ==========================================================
RUN chmod +x startup.sh
CMD ["/bin/sh", "startup.sh"]
