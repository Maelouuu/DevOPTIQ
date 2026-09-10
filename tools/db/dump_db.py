"""Sauvegarde complète d'une base DevOPTIQ, en JSON, sans pg_dump.

Neon n'est pas joignable avec `psql` depuis tous les postes, et un poste de
développement n'a pas forcément les outils client PostgreSQL. Ce script ne
dépend que de psycopg2, déjà dans requirements.txt.

    python tools/db/dump_db.py --url "postgresql://…" --out sauvegardes/

Écrit un fichier par table (`<table>.json`) plus un `_manifeste.json` qui note
la date, la base et le nombre de lignes — de quoi vérifier une restauration.
⚠️ À faire AVANT toute remise à zéro : c'est ce qui rend l'opération réversible.
"""
import argparse
import datetime as dt
import decimal
import json
import os
import sys

import psycopg2


def _serialisable(v):
    """JSON ne sait pas écrire une date, un Decimal ni de la mémoire brute."""
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v).decode("utf-8", "replace")
    return v


def dump(url, dossier):
    os.makedirs(dossier, exist_ok=True)
    manifeste = {"date": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                 "tables": {}}

    with psycopg2.connect(url) as cx:
        with cx.cursor() as cur:
            cur.execute("select current_database()")
            manifeste["base"] = cur.fetchone()[0]
            cur.execute("""
                select table_name from information_schema.tables
                where table_schema = 'public' and table_type = 'BASE TABLE'
                order by table_name""")
            tables = [r[0] for r in cur.fetchall()]

        for table in tables:
            with cx.cursor() as cur:
                # Les identifiants viennent du catalogue de la base, pas d'une
                # saisie : on peut les citer sans crainte.
                cur.execute(f'select * from "{table}"')
                colonnes = [d[0] for d in cur.description]
                lignes = [
                    {c: _serialisable(v) for c, v in zip(colonnes, ligne)}
                    for ligne in cur.fetchall()
                ]
            chemin = os.path.join(dossier, f"{table}.json")
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(lignes, f, ensure_ascii=False)
            manifeste["tables"][table] = len(lignes)
            print(f"  {table:34} {len(lignes):>7} ligne(s)")

    with open(os.path.join(dossier, "_manifeste.json"), "w", encoding="utf-8") as f:
        json.dump(manifeste, f, ensure_ascii=False, indent=2)

    total = sum(manifeste["tables"].values())
    print(f"\nbase « {manifeste['base']} » — {len(tables)} tables, {total} lignes")
    print(f"sauvegarde : {os.path.abspath(dossier)}")
    return manifeste


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("DATABASE_URL"),
                    help="chaîne de connexion (défaut : $DATABASE_URL)")
    ap.add_argument("--out", required=True, help="dossier de destination")
    args = ap.parse_args()
    if not args.url:
        ap.error("aucune URL : passez --url ou définissez DATABASE_URL")
    dump(args.url, args.out)


if __name__ == "__main__":
    sys.exit(main())
