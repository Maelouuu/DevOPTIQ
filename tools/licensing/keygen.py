#!/usr/bin/env python3
"""Génère la paire de clés de licence OptiqFluent (à faire UNE SEULE fois).

    python tools/licensing/keygen.py

- Clé privée  → tools/licensing/license_private.pem  (gitignorée — NE JAMAIS
  committer ni distribuer ; à sauvegarder dans un gestionnaire de secrets)
- Clé publique → Code/license_pubkey.pem  (committée, embarquée dans l'image)

Refuse d'écraser une paire existante : régénérer les clés invaliderait toutes
les licences déjà émises (--force pour assumer).
"""
import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PRIVATE_PATH = os.path.join(HERE, "license_private.pem")
PUBLIC_PATH = os.path.join(REPO, "Code", "license_pubkey.pem")


def main():
    force = "--force" in sys.argv
    if os.path.exists(PRIVATE_PATH) and not force:
        print(f"Refus : {PRIVATE_PATH} existe déjà.")
        print("Régénérer invaliderait toutes les licences émises. Utiliser --force pour assumer.")
        sys.exit(1)

    key = Ed25519PrivateKey.generate()

    with open(PRIVATE_PATH, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    os.chmod(PRIVATE_PATH, 0o600)

    with open(PUBLIC_PATH, "wb") as f:
        f.write(key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    print(f"Clé privée  : {PRIVATE_PATH}  (gitignorée — à sauvegarder en lieu sûr !)")
    print(f"Clé publique : {PUBLIC_PATH}  (à committer)")


if __name__ == "__main__":
    main()
