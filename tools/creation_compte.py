#!/usr/bin/env python3
"""
Création d'un utilisateur AFDEC / DevOPTIQ depuis le terminal (Neon Postgres).

Prérequis:
- Python 3.10+
- pip install psycopg[binary] werkzeug

Utilisation:
- Définir DATABASE_URL dans l'environnement:
  Windows PowerShell:
      setx DATABASE_URL "postgresql://.../db?sslmode=require"
  Puis relancer le terminal
- Lancer:
      python tools/create_user_cli.py
"""

from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from pathlib import Path


import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash


# ==========================================================
# CONFIG
# ==========================================================
ENV_DATABASE_URL = "DATABASE_URL"


# ==========================================================
# DATA
# ==========================================================
@dataclass
class UserInput:
    first_name: str
    last_name: str
    email: str
    password_plain: str
    status: str
    entity_id: int
    role_id: Optional[int]  # None = pas d'association de rôle
    manager_id: Optional[int] = None
    age: Optional[int] = None


# ==========================================================
# PROMPTS
# ==========================================================
def prompt_required(label: str) -> str:
    while True:
        v = input(f"{label}: ").strip()
        if v:
            return v
        print("❌ Champ obligatoire.")


def prompt_optional_str(label: str) -> Optional[str]:
    v = input(f"{label} (optionnel - Entrée pour vide): ").strip()
    return v or None


def prompt_optional_int(label: str) -> Optional[int]:
    v = input(f"{label} (optionnel - Entrée pour vide): ").strip()
    if v == "":
        return None
    try:
        return int(v)
    except ValueError:
        print("❌ Entier attendu (ou Entrée pour laisser vide).")
        return prompt_optional_int(label)


def prompt_password() -> str:
    while True:
        pwd = getpass.getpass("Mot de passe (optionnel: Entrée pour générer un mdp aléatoire ? NON) : ").strip()
        if pwd:
            return pwd
        print("❌ Mot de passe vide (obligatoire).")


def prompt_choice_indexed(
    title: str,
    options: List[str],
    default_index: Optional[int] = None,
    allow_none: bool = False,
) -> Optional[int]:
    """
    Affiche une liste 1..N.
    Retourne l'index 0-based sélectionné, ou None si allow_none et Entrée.
    """
    print(f"\n{title}")
    for i, opt in enumerate(options, start=1):
        marker = ""
        if default_index is not None and (i - 1) == default_index:
            marker = " (défaut)"
        print(f"  {i}. {opt}{marker}")
    if allow_none:
        print("  Entrée = aucun")

    prompt = "Choix"
    if default_index is not None:
        prompt += f" [{default_index + 1}]"
    prompt += ": "

    v = input(prompt).strip()

    if v == "":
        if allow_none:
            return None
        if default_index is not None:
            return default_index
        print("❌ Choix obligatoire.")
        return prompt_choice_indexed(title, options, default_index, allow_none)

    try:
        num = int(v)
    except ValueError:
        print("❌ Merci de saisir un numéro.")
        return prompt_choice_indexed(title, options, default_index, allow_none)

    if not (1 <= num <= len(options)):
        print("❌ Numéro hors limites.")
        return prompt_choice_indexed(title, options, default_index, allow_none)

    return num - 1


# ==========================================================
# DB
# ==========================================================
def get_database_url() -> str:
    # Charge automatiquement le .env à la racine du projet (DevOPTIQ/.env)
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)

    url = os.environ.get(ENV_DATABASE_URL)
    if not url:
        print(f"❌ Variable d'environnement {ENV_DATABASE_URL} manquante.")
        print(f"   Vérifie que {env_path} contient une ligne :")
        print('     DATABASE_URL=postgresql://.../db?sslmode=require')
        sys.exit(1)

    return url



def connect() -> psycopg.Connection:
    return psycopg.connect(get_database_url(), row_factory=dict_row)


def fetch_roles(conn: psycopg.Connection) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM roles ORDER BY LOWER(name) ASC;")
        return list(cur.fetchall())


def fetch_entities(conn: psycopg.Connection) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM entities ORDER BY id ASC;")
        return list(cur.fetchall())


def user_exists(conn: psycopg.Connection, email: str) -> Optional[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email=%s LIMIT 1;", (email,))
        row = cur.fetchone()
        return int(row["id"]) if row else None


def apply_mode_if_exists(conn: psycopg.Connection, existing_id: int, mode: str) -> None:
    """
    mode:
      - stop: raise
      - update: nothing here (handled in update path)
      - recreate: delete user_roles + user
    """
    if mode == "recreate":
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_roles WHERE user_id=%s;", (existing_id,))
            cur.execute("DELETE FROM users WHERE id=%s;", (existing_id,))


def create_user(conn: psycopg.Connection, data: UserInput) -> int:
    pwd_hash = generate_password_hash(data.password_plain)  # scrypt:... (comme ton app)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (first_name, last_name, age, email, password, manager_id, status, entity_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id;
            """,
            (
                data.first_name,
                data.last_name,
                data.age,
                data.email,
                pwd_hash,
                data.manager_id,
                data.status,
                data.entity_id,
            ),
        )
        return int(cur.fetchone()["id"])


def update_user(conn: psycopg.Connection, user_id: int, data: UserInput) -> int:
    pwd_hash = generate_password_hash(data.password_plain)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE users
            SET first_name=%s,
                last_name=%s,
                password=%s,
                status=%s,
                entity_id=%s,
                manager_id=%s,
                age=%s
            WHERE id=%s
            RETURNING id;
            """,
            (
                data.first_name,
                data.last_name,
                pwd_hash,
                data.status,
                data.entity_id,
                data.manager_id,
                data.age,
                user_id,
            ),
        )
        return int(cur.fetchone()["id"])


def attach_role(conn: psycopg.Connection, user_id: int, role_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_roles (user_id, role_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (user_id, role_id),
        )


# ==========================================================
# MAIN
# ==========================================================
def main() -> None:
    print("=== Création de compte utilisateur AFDEC (Neon) ===\n")

    first_name = prompt_required("Prénom")
    last_name = prompt_required("Nom")
    email = prompt_required("Email")
    password_plain = prompt_password()

    # status (numéroté)
    status_options = ["administrateur", "user", "rh", "actif", "inactif"]
    default_status_index = status_options.index("user")
    status_idx = prompt_choice_indexed("Status", status_options, default_index=default_status_index)
    status = status_options[int(status_idx)]

    manager_id = prompt_optional_int("Manager ID")
    age = prompt_optional_int("Âge")

    # mode si existe
    mode_options = [
        "stop (ne rien faire si email existe)",
        "update (mettre à jour l'utilisateur existant)",
        "recreate (supprimer puis recréer proprement)",
    ]
    mode_idx = prompt_choice_indexed("Si email existe déjà, action ?", mode_options, default_index=0)
    mode_map = {0: "stop", 1: "update", 2: "recreate"}
    mode = mode_map[int(mode_idx)]

    try:
        with connect() as conn:
            roles = fetch_roles(conn)
            entities = fetch_entities(conn)

            # entity obligatoire (numérotée)
            if not entities:
                raise RuntimeError("Aucune entité trouvée dans la table entities.")
            entity_names = [e["name"] for e in entities]
            entity_idx = prompt_choice_indexed("Entité (obligatoire)", entity_names, default_index=0, allow_none=False)
            entity_id = int(entities[int(entity_idx)]["id"])

            # rôle optionnel (numéroté)
            role_id: Optional[int] = None
            if roles:
                role_names = [r["name"] for r in roles]
                role_choice = prompt_choice_indexed("Rôle à associer (optionnel)", role_names, allow_none=True)
                if role_choice is not None:
                    role_id = int(roles[int(role_choice)]["id"])
            else:
                print("\n⚠️ Aucun rôle trouvé dans roles. On continue sans association.")

            data = UserInput(
                first_name=first_name,
                last_name=last_name,
                email=email,
                password_plain=password_plain,
                status=status,
                entity_id=entity_id,
                role_id=role_id,
                manager_id=manager_id,
                age=age,
            )

            with conn.transaction():
                existing_id = user_exists(conn, email)
                if existing_id:
                    if mode == "stop":
                        raise RuntimeError(f"Un utilisateur existe déjà avec cet email (id={existing_id}).")
                    if mode == "recreate":
                        apply_mode_if_exists(conn, existing_id, mode="recreate")
                        user_id = create_user(conn, data)
                    else:  # update
                        user_id = update_user(conn, existing_id, data)
                else:
                    user_id = create_user(conn, data)

                if role_id is not None:
                    attach_role(conn, user_id, role_id)

        print("\n✅ OK — Compte prêt")
        print(f"User ID : {user_id}")
        print(f"Email   : {email}")
        print(f"Status  : {status}")
        print(f"Entity  : {entity_id}")
        if role_id is None:
            print("Rôle    : (aucun)")
        else:
            role_name = next((r["name"] for r in roles if int(r["id"]) == role_id), "???")
            print(f"Rôle    : {role_name}")

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
