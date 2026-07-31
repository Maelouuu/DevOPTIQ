import os

workers = int(os.getenv("WEB_CONCURRENCY", "2"))
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
timeout = 120
# preload : create_app() (donc create_all + migrations idempotentes) s'exécute
# UNE fois dans le master avant le fork des workers — sinon chaque worker
# rejouerait l'init DB en parallèle (course au premier démarrage). Sans risque
# de partage de connexions : l'init se termine par db.engine.dispose().
preload_app = True
