#!/usr/bin/env python3
"""Chiffre le catalogue de prompts IA en bundle pour l'image client.

    python tools/prompts/encrypt_prompts.py            # clé auto (créée ou relue)
    PROMPTS_KEY=... python tools/prompts/encrypt_prompts.py

Lit Code/prompts/catalog.py (exclu de l'image Docker) et écrit
Code/prompts/prompts.enc (embarqué dans l'image). La clé Fernet est relue/écrite
dans tools/prompts/prompts_key.txt (gitignoré — à sauvegarder comme la clé de
licence). Donner cette clé au client via le champ prompts_key de sa licence
(tools/licensing/make_license.py --prompts-key ...) ou via l'env PROMPTS_KEY.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cryptography.fernet import Fernet  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
KEY_PATH = os.path.join(HERE, "prompts_key.txt")
ENC_PATH = os.path.join(REPO, "Code", "prompts", "prompts.enc")


def main():
    from Code.prompts.catalog import PROMPTS

    key = os.environ.get("PROMPTS_KEY")
    if not key and os.path.exists(KEY_PATH):
        key = open(KEY_PATH).read().strip()
        print(f"Clé relue depuis {KEY_PATH}")
    if not key:
        key = Fernet.generate_key().decode()
        with open(KEY_PATH, "w") as f:
            f.write(key)
        os.chmod(KEY_PATH, 0o600)
        print(f"Nouvelle clé générée → {KEY_PATH} (gitignoré — à sauvegarder !)")

    data = json.dumps(PROMPTS, ensure_ascii=False).encode("utf-8")
    with open(ENC_PATH, "wb") as f:
        f.write(Fernet(key.encode()).encrypt(data))

    print(f"Bundle chiffré : {ENC_PATH} ({len(PROMPTS)} prompts)")
    print("Clé à livrer au client (licence --prompts-key, ou env PROMPTS_KEY) :")
    print(key)


if __name__ == "__main__":
    main()
