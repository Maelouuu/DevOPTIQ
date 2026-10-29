import os

workers = int(os.getenv("WEB_CONCURRENCY", "2"))
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
timeout = 120
# preload : create_app() (donc create_all + migrations idempotentes) s'exécute
# UNE fois dans le master avant le fork des workers — sinon chaque worker
# rejouerait l'init DB en parallèle (course au premier démarrage). Sans risque
# de partage de connexions : l'init se termine par db.engine.dispose().
preload_app = True

# ⚠️ Sans cela, le lien de réinitialisation part en `http://`. Le TLS s'arrête
# au frontend Google, qui transmet `X-Forwarded-Proto: https` — mais gunicorn
# ne le croit que d'un émetteur listé ici, et son défaut (127.0.0.1) n'est
# jamais l'adresse d'où Cloud Run livre la requête. `url_for(_external=True)`
# lisait donc un schéma http. Le lien fonctionne quand même (tout le TLD `.app`
# est en HSTS préchargé, le navigateur force https avant de partir), mais un
# lien http écrit dans un mail est un signal d'hameçonnage de plus — et celui-ci
# en porte déjà deux (expéditeur Gmail, domaine `*.run.app`).
# Le conteneur n'est joignable QUE par ce frontend ; une installation client qui
# s'expose autrement resserre la valeur par l'environnement.
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")
