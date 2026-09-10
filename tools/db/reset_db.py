"""Repart d'une base neuve pour l'instance de développement.

Vide entièrement le schéma `public`, le laisse reconstruire par le démarrage
NORMAL de l'application (create_all + migrations à chaud — le même chemin qu'en
production, donc on teste aussi les migrations), puis crée les comptes de départ.

    python tools/db/reset_db.py --url "postgresql://…" --expect-db neondb --yes

⚠️ Trois garde-fous, et ils sont là pour de bonnes raisons :

  * `--expect-db` est OBLIGATOIRE et vérifié contre `current_database()`. Les
    bases DevOPTIQ vivent sur le MÊME endpoint Neon que la base du pilote
    ARaymond : une URL mal recopiée effacerait le travail du client. Le script
    refuse de continuer si le nom ne correspond pas ;
  * sans `--yes`, il montre ce qu'il détruirait et s'arrête ;
  * il exige une sauvegarde (`tools/db/dump_db.py`) sauf `--sans-sauvegarde`.
"""
import argparse
import os
import sys

import psycopg2

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RACINE)

# Comptes de départ de l'instance de développement. Mot de passe volontairement
# trivial : l'instance est privée et sert à travailler, pas à héberger de la
# donnée réelle.
MOT_DE_PASSE = "test"
COMPTES = [
    ("Mael",     "Girardin",  "afdec.enterprise.services@gmail.com", "administrateur"),
    ("Camille",  "Fontaine",  "camille.fontaine@example.com",        "champion"),
    ("Noe",      "Berthier",  "noe.berthier@example.com",            "user"),
    ("Salome",   "Vasseur",   "salome.vasseur@example.com",          "user"),
    ("Timeo",    "Charrier",  "timeo.charrier@example.com",          "user"),
]


def _etat(url):
    """Ce qu'on s'apprête à détruire, pour pouvoir le regarder avant."""
    with psycopg2.connect(url) as cx:
        cx.set_session(readonly=True)
        with cx.cursor() as cur:
            cur.execute("select current_database()")
            base = cur.fetchone()[0]
            cur.execute("""
                select table_name from information_schema.tables
                where table_schema = 'public' and table_type = 'BASE TABLE'""")
            tables = [r[0] for r in cur.fetchall()]
            comptes = {}
            for nom in ("users", "entities", "activities"):
                if nom in tables:
                    cur.execute(f'select count(*) from "{nom}"')
                    comptes[nom] = cur.fetchone()[0]
    return base, tables, comptes


def _vider(url):
    """Le schéma entier part : c'est la seule façon d'être sûr qu'il ne reste
    aucune table d'une version antérieure du modèle."""
    cx = psycopg2.connect(url)
    cx.autocommit = True
    with cx.cursor() as cur:
        cur.execute("drop schema public cascade")
        cur.execute("create schema public")
        cur.execute("grant all on schema public to public")
    cx.close()


def _reconstruire_et_peupler(url):
    """Démarre l'application sur la base vide, puis crée les comptes."""
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("SECRET_KEY", "reset-db")
    # Sans clé, chaque route IA dégrade proprement — inutile ici, et on évite
    # d'envoyer quoi que ce soit à un service externe pendant un reset.
    for cle in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
        os.environ.pop(cle, None)

    from Code.app import create_app
    from Code.extensions import db
    from Code.models.models import User, default_lang_for
    from Code.security import hash_password

    app = create_app()
    with app.app_context():
        crees = []
        for prenom, nom, email, statut in COMPTES:
            u = User(first_name=prenom, last_name=nom, email=email,
                     password=hash_password(MOT_DE_PASSE), status=statut,
                     lang=default_lang_for(email))
            db.session.add(u)
            crees.append((email, statut))
        db.session.commit()

        from sqlalchemy import inspect
        tables = sorted(inspect(db.engine).get_table_names())
    return crees, tables


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("DATABASE_URL"),
                    help="chaîne de connexion (défaut : $DATABASE_URL)")
    ap.add_argument("--expect-db", required=True,
                    help="nom attendu de la base — refuse d'agir si ça ne correspond pas")
    ap.add_argument("--yes", action="store_true",
                    help="exécute vraiment (sans ce drapeau, on ne fait que montrer)")
    ap.add_argument("--sans-sauvegarde", action="store_true",
                    help="passe outre l'exigence de sauvegarde préalable")
    ap.add_argument("--sauvegarde", help="dossier d'une sauvegarde déjà faite")
    args = ap.parse_args()
    if not args.url:
        ap.error("aucune URL : passez --url ou définissez DATABASE_URL")

    base, tables, comptes = _etat(args.url)
    print(f"base visée      : {base}")
    print(f"attendue        : {args.expect_db}")
    if base != args.expect_db:
        print("\n⛔ La base connectée n'est pas celle attendue — rien n'a été touché.\n"
              "   Les bases DevOPTIQ partagent leur endpoint Neon avec celle du\n"
              "   pilote ARaymond : ce contrôle évite d'effacer le travail du client.")
        return 2

    print(f"tables          : {len(tables)}")
    for nom, n in comptes.items():
        print(f"  {nom:12} {n} ligne(s)")

    if not args.sans_sauvegarde:
        manifeste = os.path.join(args.sauvegarde or "", "_manifeste.json")
        if not (args.sauvegarde and os.path.exists(manifeste)):
            print("\n⛔ Aucune sauvegarde indiquée. Faites d'abord :\n"
                  "     python tools/db/dump_db.py --url … --out sauvegardes/<date>\n"
                  "   puis rappelez ce script avec --sauvegarde sauvegardes/<date>\n"
                  "   (ou --sans-sauvegarde si vous assumez la perte).")
            return 2
        print(f"sauvegarde      : {os.path.abspath(args.sauvegarde)}")

    if not args.yes:
        print("\nSimulation : rien n'a été modifié. Ajoutez --yes pour exécuter.")
        print("Comptes qui seraient créés :")
        for prenom, nom, email, statut in COMPTES:
            print(f"  - {prenom + ' ' + nom:20} {email:40} {statut}")
        return 0

    print("\nEffacement du schéma…")
    _vider(args.url)
    print("Reconstruction par le démarrage de l'application…")
    crees, tables = _reconstruire_et_peupler(args.url)

    print(f"\n{len(tables)} tables recréées.")
    print("Comptes créés :")
    for email, statut in crees:
        print(f"  - {email:40} {statut:16} mot de passe : {MOT_DE_PASSE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
