"""Les cartos et les rôles d'une base, tels qu'ils sont — SANS RIEN ÉCRIRE.

    python tools/db/etat_entites.py --url "postgresql://…"
    python tools/db/etat_entites.py --url "…" --nom purchase

Deux questions auxquelles seule la base répond :

  1. **« Cette carto est un fantôme, je ne peux pas la supprimer. »** Une entité
     dont `owner_id` est NULL, ou pointe vers un compte effacé, s'affichait dans
     la liste sans jamais pouvoir être supprimée : la route cherchait
     `Entity(id=…, owner_id=moi)` et ne trouvait rien. C'est corrigé dans le
     code ; cet inventaire dit si la base en porte, et combien d'entités
     partagent le même nom.

  2. **Ce que la mise en commun des rôles va réunir.** Les rôles sont désormais
     communs à l'entreprise (une ligne par nom). `fusionner_doublons()` réunit
     au démarrage les doublons d'hier ; on voit ici lesquels, et lequel sera
     gardé (celui qui a le plus de titulaires, puis le plus petit id).

Lecture seule : `set_session(readonly=True)`, aucune transaction validée.
"""
import argparse
import os
import unicodedata

import psycopg2


def norm(valeur):
    """La même normalisation que `Code.roles_communs.normalise`.

    ⚠️ Recopiée à l'identique, pas réécrite : c'est elle qui décide quels rôles
    seront réunis. Un tiret n'est PAS un séparateur ici — « chef-d-atelier » et
    « chef d atelier » restent deux noms. `test_66` compare les deux versions.
    """
    texte = unicodedata.normalize("NFKD", str(valeur or ""))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.lower().split())


def _table_existe(cur, nom):
    cur.execute("SELECT to_regclass(%s)", (nom,))
    return cur.fetchone()[0] is not None


def _colonne_existe(cur, table, colonne):
    cur.execute("""SELECT 1 FROM information_schema.columns
                   WHERE table_name = %s AND column_name = %s""",
                (table, colonne))
    return cur.fetchone() is not None


def _entites(cur):
    commune = "is_shared" if _colonne_existe(cur, "entities", "is_shared") else "FALSE"
    cur.execute("""
        SELECT e.id, e.name, e.owner_id, u.email, COALESCE(%s, FALSE)
        FROM entities e LEFT JOIN users u ON u.id = e.owner_id
        ORDER BY lower(e.name), e.id
    """ % commune)
    return cur.fetchall()


def _cartos(cur, filtre):
    lignes = _entites(cur)
    if filtre:
        cible = norm(filtre)
        lignes = [l for l in lignes if cible in norm(l[1])]

    print("── Cartographies (%d) ──" % len(lignes))
    par_nom = {}
    orphelines = []
    for eid, nom, owner_id, email, commune in lignes:
        par_nom.setdefault(norm(nom), []).append(eid)
        marque = []
        if owner_id is None:
            marque.append("SANS PROPRIÉTAIRE")
            orphelines.append(eid)
        elif email is None:
            marque.append("propriétaire #%s EFFACÉ" % owner_id)
            orphelines.append(eid)
        if commune:
            marque.append("commune")
        print("   #%-5s %-44s %-34s %s"
              % (eid, (nom or "")[:44], (email or "—")[:34], " · ".join(marque)))

    doublons = {n: ids for n, ids in par_nom.items() if len(ids) > 1}
    print("\n── Noms portés par PLUSIEURS cartos (%d) ──" % len(doublons))
    if not doublons:
        print("   aucun")
    for nom, ids in sorted(doublons.items()):
        print("   %-44s %s" % (nom[:44], ", ".join("#%s" % i for i in ids)))

    print("\n── Cartos sans propriétaire joignable (%d) ──" % len(orphelines))
    if not orphelines:
        print("   aucune")
    else:
        print("   %s" % ", ".join("#%s" % i for i in orphelines))
        print("   → elles s'affichaient sans pouvoir être supprimées : la route")
        print("     exigeait d'en être propriétaire. Le code courant les rend")
        print("     supprimables par un administrateur.")


def _roles(cur):
    if not _table_existe(cur, "roles"):
        return
    hors_carte = _colonne_existe(cur, "roles", "hors_carte")
    cur.execute("""
        SELECT r.id, r.name, r.entity_id, %s,
               (SELECT count(*) FROM user_roles ur WHERE ur.role_id = r.id)
        FROM roles r ORDER BY lower(r.name), r.id
    """ % ("r.hors_carte" if hors_carte else "FALSE"))
    lignes = cur.fetchall()

    par_nom = {}
    for rid, nom, eid, hc, titulaires in lignes:
        par_nom.setdefault(norm(nom), []).append((rid, eid, bool(hc), titulaires))

    doublons = {n: v for n, v in par_nom.items() if len(v) > 1}
    print("\n── Rôles : %d ligne(s) pour %d nom(s) distinct(s) ──"
          % (len(lignes), len(par_nom)))
    print("── À RÉUNIR au premier démarrage (%d nom(s)) ──" % len(doublons))
    if not doublons:
        print("   aucun — les rôles sont déjà communs")
    for nom, v in sorted(doublons.items()):
        garde = sorted(v, key=lambda x: (-x[3], x[0]))[0]
        autres = [x for x in v if x[0] != garde[0]]
        print("   %-38s garde #%-5s (%d titulaire(s)) ← %s"
              % (nom[:38], garde[0], garde[3],
                 ", ".join("#%s (%d)" % (x[0], x[3]) for x in autres)))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("DATABASE_URL"),
                    help="chaîne de connexion (défaut : $DATABASE_URL)")
    ap.add_argument("--nom", default="",
                    help="ne lister que les cartos dont le nom contient ceci")
    args = ap.parse_args()
    if not args.url:
        ap.error("aucune URL : passez --url ou définissez DATABASE_URL")

    con = psycopg2.connect(args.url.strip().strip('"').strip("'"),
                           connect_timeout=30)
    con.set_session(readonly=True)          # garde-fou : rien ne peut s'écrire
    cur = con.cursor()

    cur.execute("SELECT current_database()")
    print("Base : %s\n" % cur.fetchone()[0])

    _cartos(cur, args.nom)
    _roles(cur)

    con.rollback()
    con.close()


if __name__ == "__main__":
    main()
