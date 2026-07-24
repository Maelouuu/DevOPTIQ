# Code/licensing.py — Licence d'utilisation OptiqFluent signée à expiration.
#
# Principe : AFDEC signe (clé privée Ed25519, jamais distribuée) un petit JSON
# {licencié, produit, date d'expiration}. L'app embarque uniquement la clé
# publique (Code/license_pubkey.pem) et vérifie la signature + la date.
# Prolonger la licence = livrer un nouveau fichier .lic (aucun rebuild d'image).
#
# L'enforcement n'est actif que si REQUIRE_LICENSE=1 (baké dans l'image client
# via le Dockerfile). En dev local et dans les tests, rien ne change.
#
# Outils côté AFDEC : tools/licensing/keygen.py (paire de clés, une seule fois)
# et tools/licensing/make_license.py (émission d'une licence signée).

import base64
import json
import os
from datetime import date

from flask import render_template, request

_PUBKEY_PATH = os.path.join(os.path.dirname(__file__), "license_pubkey.pem")

# Chemins toujours servis, licence valide ou non
_EXEMPT_PREFIXES = ("/healthz", "/license", "/static/")


class LicenseError(Exception):
    pass


def _read_license_raw():
    """Licence via env (base64) ou fichier. Retourne (bytes, mtime|None)."""
    b64 = os.getenv("OPTIQFLUENT_LICENSE")
    if b64:
        try:
            return base64.b64decode(b64), None
        except Exception as e:
            raise LicenseError(f"OPTIQFLUENT_LICENSE illisible (base64 attendu) : {e}")
    path = os.getenv("LICENSE_PATH", "/app/license/optiqfluent.lic")
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read(), os.path.getmtime(path)
    raise LicenseError(
        "Aucune licence trouvée : définir OPTIQFLUENT_LICENSE (contenu base64) "
        f"ou déposer le fichier de licence dans {path} (variable LICENSE_PATH)."
    )


def canonical_payload_bytes(payload):
    """Représentation canonique signée — partagée avec make_license.py."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def verify_license():
    """Vérifie signature + structure. Retourne les infos de licence.

    Lève LicenseError si absente, malformée, mal signée ou sans date valide.
    (L'expiration est comparée à chaque requête, pas seulement ici.)
    """
    if not os.path.isfile(_PUBKEY_PATH):
        raise LicenseError(
            "Clé publique de licence absente (Code/license_pubkey.pem). "
            "Côté AFDEC : exécuter tools/licensing/keygen.py avant le build."
        )
    raw, mtime = _read_license_raw()
    try:
        doc = json.loads(raw)
        payload = doc["payload"]
        signature = base64.b64decode(doc["signature"])
    except LicenseError:
        raise
    except Exception as e:
        raise LicenseError(f"Fichier de licence malformé : {e}")

    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.exceptions import InvalidSignature
    with open(_PUBKEY_PATH, "rb") as f:
        pubkey = load_pem_public_key(f.read())
    try:
        pubkey.verify(signature, canonical_payload_bytes(payload))
    except InvalidSignature:
        raise LicenseError("Signature de licence invalide.")

    try:
        expires = date.fromisoformat(payload["expires_at"])
    except Exception:
        raise LicenseError("Licence sans date d'expiration valide (expires_at).")

    return {
        "licensee": payload.get("licensee", "?"),
        "product": payload.get("product", "OptiqFluent"),
        "issued_at": payload.get("issued_at"),
        "expires_at": expires,
        "mtime": mtime,
    }


def init_license_enforcement(app):
    if os.getenv("REQUIRE_LICENSE", "0") != "1":
        app.config["LICENSE_STATE"] = {"enforced": False}
        return

    state = {"enforced": True, "info": None, "error": None}
    app.config["LICENSE_STATE"] = state

    def _revalidate():
        try:
            state["info"] = verify_license()
            state["error"] = None
        except LicenseError as e:
            state["info"] = None
            state["error"] = str(e)

    _revalidate()
    if state["error"]:
        print(f"[LICENSE] ⚠ {state['error']}")
    else:
        info = state["info"]
        if date.today() > info["expires_at"]:
            print(f"[LICENSE] ⚠ Licence EXPIRÉE depuis le {info['expires_at']} "
                  f"({info['licensee']}) — accès bloqué jusqu'au renouvellement")
        else:
            print(f"[LICENSE] Licence valide — {info['licensee']}, expire le {info['expires_at']}")

    def _is_valid_today():
        info = state["info"]
        if info is not None and date.today() <= info["expires_at"]:
            return True
        # Invalide ou expirée : retenter une lecture — un fichier .lic renouvelé
        # (ou une variable d'env mise à jour) est pris en compte sans redémarrage.
        _revalidate()
        info = state["info"]
        return info is not None and date.today() <= info["expires_at"]

    @app.before_request
    def _license_gate():
        if request.path.startswith(_EXEMPT_PREFIXES):
            return None
        if _is_valid_today():
            return None
        info = state["info"]
        return render_template(
            "license_blocked.html",
            error=state["error"],
            expires_at=info["expires_at"] if info else None,
            licensee=info["licensee"] if info else None,
        ), 403

    @app.route("/license")
    def license_status():
        info = state["info"]
        valid = info is not None and date.today() <= info["expires_at"]
        return {
            "product": "OptiqFluent",
            "valid": valid,
            "licensee": info["licensee"] if info else None,
            "expires_at": info["expires_at"].isoformat() if info else None,
            "error": None if valid else (state["error"] or "Licence expirée."),
        }, (200 if valid else 403)
