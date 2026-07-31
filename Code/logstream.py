# Code/logstream.py — Capture de la sortie serveur pour la console admin.
#
# Duplique stdout/stderr (prints [DB], [LICENSE], tracebacks…) et le logging
# Python vers un fichier tampon, que la page Paramètres (section admin) lit en
# quasi-direct. Multi-workers : tous écrivent dans le même fichier (append).
# Le fichier est plafonné : au-delà de MAX_BYTES il est tronqué en gardant la
# fin (les consommateurs détectent la troncature via un offset > taille).

import logging
import os
import sys
import tempfile
import threading

LOG_PATH = os.path.join(tempfile.gettempdir(), "optiqfluent-server.log")
MAX_BYTES = 2 * 1024 * 1024
KEEP_BYTES = 1 * 1024 * 1024

_lock = threading.Lock()
_initialized = False


class _Tee:
    def __init__(self, original):
        self._original = original

    def write(self, data):
        try:
            self._original.write(data)
        except Exception:
            pass
        if data:
            _append(data)

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._original, name)


def _append(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8", "replace")
    with _lock:
        try:
            with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
                f.write(data)
            if os.path.getsize(LOG_PATH) > MAX_BYTES:
                with open(LOG_PATH, "rb") as f:
                    f.seek(-KEEP_BYTES, os.SEEK_END)
                    tail = f.read()
                with open(LOG_PATH, "wb") as f:
                    f.write(tail)
        except OSError:
            pass


class _FileHandler(logging.Handler):
    def emit(self, record):
        try:
            _append(self.format(record) + "\n")
        except Exception:
            pass


def init_logstream():
    """À appeler une fois au démarrage de l'app (idempotent par process)."""
    global _initialized
    if _initialized:
        return
    _initialized = True
    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr)
    handler = _FileHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    logging.getLogger().addHandler(handler)


def tail(offset=0, max_bytes=64 * 1024):
    """Contenu depuis `offset`. Retourne (texte, nouvel_offset, taille)."""
    try:
        size = os.path.getsize(LOG_PATH)
    except OSError:
        return "", 0, 0
    if offset > size:   # fichier tronqué entre deux lectures
        offset = 0
    start = max(offset, size - max_bytes) if offset == 0 else offset
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            f.seek(start)
            data = f.read(max_bytes)
    except OSError:
        return "", offset, size
    return data, start + len(data.encode("utf-8", "replace")), size
