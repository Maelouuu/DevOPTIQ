#!/usr/bin/env python3
"""Émet une licence OptiqFluent signée.

    python tools/licensing/make_license.py --licensee "ACME SAS" --days 31
    python tools/licensing/make_license.py --licensee "ACME SAS" --expires 2026-08-31

Produit tools/licensing/out/optiqfluent-<slug>.lic (à livrer au client), et
affiche l'équivalent base64 pour la variable d'env OPTIQFLUENT_LICENSE.
Prolonger = ré-émettre avec une nouvelle date et remplacer le fichier chez le
client (pris en compte sans redémarrage).
"""
import argparse
import base64
import json
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from Code.licensing import canonical_payload_bytes  # noqa: E402

from cryptography.hazmat.primitives.serialization import load_pem_private_key  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PRIVATE_PATH = os.path.join(HERE, "license_private.pem")
OUT_DIR = os.path.join(HERE, "out")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--licensee", required=True, help="Nom du client (raison sociale)")
    ap.add_argument("--expires", help="Date d'expiration YYYY-MM-DD")
    ap.add_argument("--days", type=int, help="Durée en jours à partir d'aujourd'hui")
    args = ap.parse_args()

    if bool(args.expires) == bool(args.days):
        ap.error("préciser soit --expires YYYY-MM-DD, soit --days N")
    expires = date.fromisoformat(args.expires) if args.expires \
        else date.today() + timedelta(days=args.days)
    if expires <= date.today():
        ap.error("la date d'expiration doit être dans le futur")

    if not os.path.exists(PRIVATE_PATH):
        sys.exit(f"Clé privée absente ({PRIVATE_PATH}) — exécuter d'abord tools/licensing/keygen.py")
    with open(PRIVATE_PATH, "rb") as f:
        key = load_pem_private_key(f.read(), password=None)

    payload = {
        "product": "OptiqFluent",
        "licensee": args.licensee,
        "issued_at": date.today().isoformat(),
        "expires_at": expires.isoformat(),
    }
    doc = {
        "payload": payload,
        "signature": base64.b64encode(key.sign(canonical_payload_bytes(payload))).decode(),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.licensee.lower()).strip("-") or "client"
    out_path = os.path.join(OUT_DIR, f"optiqfluent-{slug}.lic")
    raw = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
    with open(out_path, "wb") as f:
        f.write(raw)

    print(f"Licence émise : {out_path}")
    print(f"  Client  : {args.licensee}")
    print(f"  Expire  : {expires.isoformat()}")
    print()
    print("Variante variable d'environnement (OPTIQFLUENT_LICENSE) :")
    print(base64.b64encode(raw).decode())


if __name__ == "__main__":
    main()
