# Dockerfile — AFDEC / OptiqFluent (Flask) → Cloud Run ou on-premise client
FROM python:3.12-slim

# ==========================================================
# 1) Dépendances système
#    (LibreOffice retiré : aucun usage dans le code — ~1,5 Go gagné.
#     Exports Excel/HTML = openpyxl/python-docx, purs Python.)
# ==========================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        unzip \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Locale UTF-8 (C.UTF-8 : disponible sans le paquet locales)
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

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

# Le bundle de prompts chiffré doit avoir été généré AVANT le build
# (python tools/prompts/encrypt_prompts.py) : le catalogue en clair est exclu
# par .dockerignore — sans bundle, toutes les fonctions IA seraient dégradées.
RUN test -f Code/prompts/prompts.enc || \
    (echo "ERREUR: Code/prompts/prompts.enc absent — lancer tools/prompts/encrypt_prompts.py avant le build" && exit 1)

# ==========================================================
# 4a) Suite de tests — nos instances seulement
#     Le panel /testpanel lit les fichiers pour recenser les cas et les
#     rejoue dans un sous-processus (base SQLite jetable, jamais celle de
#     l'app). Il lui faut donc les SOURCES : sans elles le panel affiche
#     zéro test. L'image client, elle, n'en embarque aucune.
#     Interne : --build-arg WITH_TESTS=1
# ==========================================================
ARG WITH_TESTS=0
RUN if [ "$WITH_TESTS" != "1" ]; then rm -rf /app/tests; fi

# ==========================================================
# 4b) Anti-inspection : bytecode uniquement
#     Compile tout en .pyc (layout legacy, importable sans .py) puis supprime
#     les sources Python de l'image. Dissuasion, pas protection absolue :
#     le vrai verrou reste le contrat + la licence + les prompts chiffrés.
#     gunicorn.conf.py est conservé (lu en source par Gunicorn au démarrage).
#     tests/ aussi quand il est embarqué : pytest collecte des .py, pas des
#     .pyc, et le panel analyse les sources pour recenser les cas.
# ==========================================================
RUN python -m compileall -b -q -x '(^|/)tests/' /app && \
    find /app -name "*.py" ! -path "/app/gunicorn.conf.py" ! -path "/app/tests/*" -delete && \
    (find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true)

# ==========================================================
# 5) Cloud Run utilise la variable d'environnement PORT
# ==========================================================
ENV PORT=8080

# Licence signée obligatoire par défaut (image distribuée aux clients).
# Nos propres déploiements peuvent passer REQUIRE_LICENSE=0 dans leur config
# d'environnement (Cloud Run) — le contrat client interdit ce contournement.
ENV REQUIRE_LICENSE=1

# Panel de tests : outillage interne AFDEC, hors image client (les tests sont
# de toute façon exclus du build). Réactivable via env sur nos déploiements.
ENV TESTPANEL_ENABLED=0

# ==========================================================
# 6) Lancement Gunicorn (production)
# ==========================================================
RUN chmod +x startup.sh
CMD ["/bin/sh", "startup.sh"]
