"""Restauration d'une base DevOPTIQ depuis une sauvegarde `dump_db.py`.

    python tools/db/restore_db.py --url "postgresql://…" \
        --expect-db neondb --from sauvegardes/neondb-2026-09-10 --dry-run
    … puis la même commande avec --yes

Le SCHÉMA doit déjà exister : on ne restaure que des DONNÉES. C'est voulu —
laisser l'application construire son schéma au démarrage (`create_all` +
migrations à chaud) garantit qu'on repart sur le schéma que le code attend
AUJOURD'HUI, pas sur celui du jour de la sauvegarde.

Quatre choses que ce script fait et qu'un simple INSERT en boucle ne ferait
pas :

  * **Il retire les 78 clés étrangères puis les remet.** Charger dans l'ordre
    des dépendances est impossible ici : `entities` et `users` se référencent
    mutuellement (SQLAlchemy le signale lui-même — « unresolvable foreign key
    dependency »). Remettre les contraintes à la fin VALIDE au passage tout ce
    qui a été chargé : si une référence est cassée, on le sait à ce moment-là,
    et la transaction entière est annulée.
  * **Il repositionne les séquences.** Sans ça, le prochain enregistrement
    créé dans l'application tomberait sur une clé primaire déjà prise — panne
    silencieuse et déroutante, plusieurs jours après la restauration.
  * **Il n'écrit que les colonnes présentes des DEUX côtés.** Le schéma bouge
    entre une sauvegarde et sa restauration ; les colonnes apparues depuis
    prennent leur valeur par défaut, celles qui ont disparu sont ignorées — et
    le rapport les nomme, une par une.
  * **Tout tient dans UNE transaction.** PostgreSQL sait annuler du DDL : en
    cas d'échec à la 50ᵉ table, la base est rendue telle qu'elle était.

⚠️ `--expect-db` est obligatoire et comparé à `current_database()`. Le 10/09
la base du bac à sable et la base officielle s'appelaient toutes deux
`neondb` : le garde-fou passait des deux côtés et ne protégeait de rien. Un
nom distinct est ce qui rend la vérification réelle.
"""
import argparse
import base64
import glob
import json
import os
import sys

import psycopg2
from psycopg2 import extras

MARQUE_BINAIRE = "__b64__"


# ---------------------------------------------------------------------------
# Lecture de la sauvegarde
# ---------------------------------------------------------------------------

def _lire_sauvegarde(dossier):
    if not os.path.isdir(dossier):
        raise SystemExit("dossier introuvable : %s" % dossier)
    tables = {}
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.json"))):
        nom = os.path.basename(chemin)[:-5]
        if nom.startswith("_"):
            continue
        with open(chemin, encoding="utf-8") as f:
            tables[nom] = json.load(f)
    manifeste = {}
    chemin_m = os.path.join(dossier, "_manifeste.json")
    if os.path.exists(chemin_m):
        with open(chemin_m, encoding="utf-8") as f:
            manifeste = json.load(f)
    return tables, manifeste


def _valeur(v):
    """Retransforme ce que le JSON a aplati."""
    if isinstance(v, dict) and MARQUE_BINAIRE in v:
        return psycopg2.Binary(base64.b64decode(v[MARQUE_BINAIRE]))
    if isinstance(v, (dict, list)):
        # Colonne json/jsonb : psycopg2 sait l'adapter, pas le dict nu.
        return extras.Json(v)
    return v


# ---------------------------------------------------------------------------
# Lecture du schéma cible
# ---------------------------------------------------------------------------

def _schema(cur):
    cur.execute("""
        SELECT table_name, column_name
          FROM information_schema.columns
         WHERE table_schema = 'public'
         ORDER BY table_name, ordinal_position
    """)
    colonnes = {}
    for t, c in cur.fetchall():
        colonnes.setdefault(t, []).append(c)
    return colonnes


def _cles_etrangeres(cur):
    cur.execute("""
        SELECT c.relname, con.conname, pg_get_constraintdef(con.oid)
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
         WHERE con.contype = 'f'
         ORDER BY c.relname, con.conname
    """)
    return cur.fetchall()


def _contraintes_unicite(cur):
    """Les contraintes UNIQUE / PRIMARY KEY de la base cible, par table."""
    cur.execute("""
        SELECT c.relname, con.conname,
               ARRAY(SELECT att.attname
                       FROM unnest(con.conkey) k
                       JOIN pg_attribute att ON att.attrelid = con.conrelid
                                            AND att.attnum = k)
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
         WHERE con.contype IN ('u', 'p')
         ORDER BY 1, 2
    """)
    par_table = {}
    for table, nom, colonnes in cur.fetchall():
        par_table.setdefault(table, []).append((nom, list(colonnes)))
    return par_table


def _conflits_unicite(cur, sauvegarde, ignorees):
    """La sauvegarde respecte-t-elle les contraintes d'unicité d'AUJOURD'HUI ?

    Une contrainte ajoutée après coup ne rend pas les anciennes données
    conformes : la base du 10/09 portait sept adresses e-mail en double, alors
    que `users.email` est désormais UNIQUE. Sans ce contrôle, on ne l'apprenait
    qu'au milieu du chargement, par une exception brute.
    """
    contraintes = _contraintes_unicite(cur)
    conflits = []
    for table, lignes in sorted(sauvegarde.items()):
        if table in ignorees or not lignes:
            continue
        for nom, colonnes in contraintes.get(table, []):
            if not all(c in lignes[0] for c in colonnes):
                continue
            vus, doubles = {}, {}
            for l in lignes:
                cle = tuple(l.get(c) for c in colonnes)
                if any(v is None for v in cle):
                    continue                      # NULL n'entre pas en conflit
                if cle in vus:
                    doubles.setdefault(cle, [vus[cle]]).append(l.get("id"))
                else:
                    vus[cle] = l.get("id")
            if doubles:
                conflits.append((table, nom, colonnes, doubles))
    return conflits
def _colonnes_a_sequence(cur):
    # pg_get_serial_sequence() résout le nom dans le search_path et trébuche
    # sur les tables système : on lit le défaut de colonne, sans ambiguïté.
    cur.execute("""
        SELECT c.relname, a.attname
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0
                             AND NOT a.attisdropped
          JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
         WHERE c.relkind = 'r'
           AND pg_get_expr(d.adbin, d.adrelid) LIKE 'nextval%'
         ORDER BY 1, 2
    """)
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def _rapport(sauvegarde, cible, ignorees):
    absentes, ecarts = [], []
    total = 0
    for table, lignes in sorted(sauvegarde.items()):
        if table in ignorees:
            continue
        if table not in cible:
            if lignes:
                absentes.append((table, len(lignes)))
            continue
        total += len(lignes)
        if lignes:
            dans_sauve = set(lignes[0])
            dans_cible = set(cible[table])
            perdues = sorted(dans_sauve - dans_cible)
            defaut = sorted(dans_cible - dans_sauve)
            if perdues or defaut:
                ecarts.append((table, perdues, defaut))

    print("lignes à charger : %d" % total)
    videes = sorted(set(cible) - set(sauvegarde))
    if videes:
        print("\ntables de la base qui seront VIDÉES (absentes de la sauvegarde) :")
        for t in videes:
            print("   %s" % t)
    if ignorees:
        print("\ntables écartées à la demande (--skip) :")
        for t in sorted(ignorees):
            n = len(sauvegarde.get(t, []))
            print("   %-34s %d ligne(s) non restaurée(s)" % (t, n))
    if absentes:
        print("\ntables de la sauvegarde SANS équivalent dans le schéma — non restaurées :")
        for t, n in absentes:
            print("   %-34s %d ligne(s) perdue(s)" % (t, n))
    if ecarts:
        print("\nécarts de colonnes :")
        for t, perdues, defaut in ecarts:
            print("   %s" % t)
            if perdues:
                print("      ignorées (disparues du schéma) : %s" % ", ".join(perdues))
            if defaut:
                print("      laissées au défaut (ajoutées depuis) : %s" % ", ".join(defaut))
    return total


# ---------------------------------------------------------------------------
# Restauration
# ---------------------------------------------------------------------------

def restaurer(url, attendu, dossier, ignorees, simuler):
    sauvegarde, manifeste = _lire_sauvegarde(dossier)
    if manifeste:
        print("sauvegarde : base « %s », %s" %
              (manifeste.get("base", "?"), manifeste.get("date", "?")))
    print("dossier    : %s" % os.path.abspath(dossier))
    print()

    cx = psycopg2.connect(url)
    cx.autocommit = False
    try:
        with cx.cursor() as cur:
            cur.execute("SELECT current_database()")
            base = cur.fetchone()[0]
            if base != attendu:
                raise SystemExit(
                    "REFUS : connecté à « %s », --expect-db dit « %s ».\n"
                    "        Rien n'a été touché." % (base, attendu))
            print("base cible : %s  ✓ (--expect-db)" % base)
            print()

            cible = _schema(cur)
            if not cible:
                raise SystemExit(
                    "REFUS : aucune table dans le schéma public.\n"
                    "        Ce script restaure des DONNÉES : laissez d'abord\n"
                    "        l'application démarrer pour construire le schéma.")

            total = _rapport(sauvegarde, cible, ignorees)

            conflits = _conflits_unicite(cur, sauvegarde, ignorees)
            if conflits:
                print("\nCONFLITS D'UNICITÉ — la sauvegarde ne respecte pas les")
                print("contraintes actuelles (elles ont été ajoutées après coup) :")
                for table, nom, colonnes, doubles in conflits:
                    print("   %s (%s sur %s) — %d valeur(s) en double :"
                          % (table, nom, ", ".join(colonnes), len(doubles)))
                    for cle, ids in sorted(doubles.items(), key=lambda kv: str(kv[0]))[:10]:
                        print("      %s → ids %s"
                              % (" / ".join(str(v) for v in cle), ids))

            if simuler:
                print("\n--dry-run : rien n'a été écrit.")
                cx.rollback()
                return

            if conflits:
                raise SystemExit(
                    "\nREFUS : le chargement échouerait à mi-parcours.\n"
                    "        Corrigez la sauvegarde (copie corrigée, jamais sur\n"
                    "        place) avant de relancer. Rien n'a été touché.")

            fks = _cles_etrangeres(cur)
            print("\nretrait de %d clés étrangères…" % len(fks))
            for table, nom, _ in fks:
                cur.execute('ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (table, nom))

            print("vidage de %d tables…" % len(cible))
            cur.execute("TRUNCATE %s" % ", ".join('"%s"' % t for t in cible))

            print("chargement…")
            charge = 0
            for table in sorted(sauvegarde):
                if table in ignorees or table not in cible:
                    continue
                lignes = sauvegarde[table]
                if not lignes:
                    continue
                cols = [c for c in cible[table] if c in lignes[0]]
                if not cols:
                    continue
                valeurs = [tuple(_valeur(l.get(c)) for c in cols) for l in lignes]
                extras.execute_values(
                    cur,
                    'INSERT INTO "%s" (%s) VALUES %%s'
                    % (table, ", ".join('"%s"' % c for c in cols)),
                    valeurs, page_size=500)
                charge += len(lignes)
                print("   %-34s %6d" % (table, len(lignes)))

            print("\nremise des %d clés étrangères (valide les données)…" % len(fks))
            for table, nom, definition in fks:
                cur.execute('ALTER TABLE "%s" ADD CONSTRAINT "%s" %s'
                            % (table, nom, definition))

            sequences = _colonnes_a_sequence(cur)
            print("repositionnement de %d séquences…" % len(sequences))
            for table, colonne in sequences:
                if table not in cible:
                    continue
                # Les identifiants viennent du catalogue (pas d'une saisie) et
                # sont interpolés ; le nom de séquence, lui, passe en paramètre.
                cur.execute(
                    'SELECT setval(pg_get_serial_sequence(%s, %s), '
                    'COALESCE((SELECT MAX("{col}") FROM "{tbl}"), 0) + 1, false)'
                    .format(col=colonne, tbl=table),
                    (table, colonne))

        cx.commit()
        print("\n%d lignes restaurées. Transaction validée." % charge)
    except Exception:
        cx.rollback()
        print("\nÉCHEC — transaction annulée, la base est restée telle qu'elle était.",
              file=sys.stderr)
        raise
    finally:
        cx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("DATABASE_URL"),
                    help="chaîne de connexion (défaut : $DATABASE_URL)")
    ap.add_argument("--expect-db", required=True,
                    help="nom attendu de la base : comparé à current_database()")
    ap.add_argument("--from", dest="dossier", required=True,
                    help="dossier de sauvegarde produit par dump_db.py")
    ap.add_argument("--skip", action="append", default=[], metavar="TABLE",
                    help="table à ne pas restaurer (répétable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="affiche le rapport sans rien écrire")
    ap.add_argument("--yes", action="store_true",
                    help="confirme l'écriture (obligatoire hors --dry-run)")
    args = ap.parse_args()

    if not args.url:
        ap.error("aucune URL : passez --url ou définissez DATABASE_URL")
    if not args.dry_run and not args.yes:
        ap.error("écriture destructive : ajoutez --yes, ou --dry-run pour voir")

    restaurer(args.url, args.expect_db, args.dossier, set(args.skip), args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
