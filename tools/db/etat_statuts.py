"""Ce que la bascule vers les QUATRE paliers changerait sur une base — SANS RIEN ÉCRIRE.

    python tools/db/etat_statuts.py --url "postgresql://…"

À passer AVANT de déployer le code des quatre paliers sur une instance déjà en
service. Il répond aux trois questions qui décident de la manœuvre :

  1. **Qui porte quel statut aujourd'hui**, sur la forme normalisée — parce que
     `users.status` est un texte libre : « manager », « Gestionnaire de
     compétences », sa troncature à 20 caractères, « Competency Manager »
     désignent tous le MÊME rôle, l'arbitre d'hier.

  2. **Ce que la reprise ferait**, compte par compte. `migrer_anciens_champions()`
     monte les arbitres d'hier au palier `coordinateur` : sans elle ils se
     réveilleraient avec le seul droit de DÉPOSER les propositions qu'ils
     validaient la veille.

  3. ⚠️ **Combien de cartos sont COMMUNES.** C'est là que se joue la seule perte
     de droit réelle pour un compte ordinaire : sur une carto commune, un `user`
     ne propose plus (c'est ce qui le sépare du `champion`). Sur une carto
     PRIVÉE, rien ne change — `can_edit` rend la main au propriétaire quel que
     soit son statut, donc chacun continue d'éditer la sienne.

Lecture seule : aucune requête d'écriture, aucune transaction validée.
"""
import argparse
import os
import re
import sys
import unicodedata

import psycopg2


ADMIN = {"admin", "administrateur", "administrator"}


def norm(raw):
    """La même normalisation que `Code/permissions.norm_status`."""
    s = unicodedata.normalize("NFD", raw or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[\s_\-]+", " ", s).strip()


def est_admin(raw):
    return norm(raw) in ADMIN


def est_arbitre_d_hier(raw):
    """Tous les libellés qui désignaient CELUI QUI VALIDE, avant la bascule.

    ⚠️ « champion » en fait partie : le mot a changé de sens. Il nommait
    l'arbitre ; il nomme désormais le palier au-dessous, qui propose sans
    valider.
    """
    st = norm(raw)
    if not st:
        return False
    if st in ("coordinateur", "coordinator", "manager", "champion"):
        return True
    if st.startswith("coordinateur") or st.startswith("coordinator"):
        return True
    if st.startswith("gestionnaire"):
        return True
    return "manager" in st and any(
        k in st for k in ("competency", "competence", "skill"))


def palier_apres(raw):
    """Le palier qu'aura ce compte APRÈS le premier démarrage du nouveau code.

    ⚠️ Il n'y a pas de branche « reste champion » : sur une base d'AVANT la
    bascule, le mot « champion » désigne l'arbitre, et la reprise le monte
    coordinateur. Un compte nommé champion au NOUVEAU sens ne peut exister
    qu'après cette reprise — donc pas sur la base qu'on inventorie ici.
    """
    if est_admin(raw):
        return "admin"
    if est_arbitre_d_hier(raw):
        return "coordinateur"      # repris par migrer_anciens_champions()
    return "user"


def _table_existe(cur, nom):
    cur.execute("SELECT to_regclass(%s)", (nom,))
    return cur.fetchone()[0] is not None


def _colonne_existe(cur, table, colonne):
    cur.execute("""SELECT 1 FROM information_schema.columns
                   WHERE table_name = %s AND column_name = %s""",
                (table, colonne))
    return cur.fetchone() is not None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("DATABASE_URL"),
                    help="chaîne de connexion (défaut : $DATABASE_URL)")
    ap.add_argument("--details", action="store_true",
                    help="lister les comptes un par un")
    args = ap.parse_args()
    if not args.url:
        ap.error("aucune URL : passez --url ou définissez DATABASE_URL")

    con = psycopg2.connect(args.url.strip().strip('"').strip("'"),
                           connect_timeout=30)
    con.set_session(readonly=True)          # garde-fou : rien ne peut s'écrire
    cur = con.cursor()

    cur.execute("SELECT current_database()")
    base = cur.fetchone()[0]
    print("Base : %s\n" % base)

    cur.execute("SELECT id, email, status FROM users ORDER BY id")
    comptes = cur.fetchall()

    avant, apres, bouges = {}, {}, []
    for uid, email, statut in comptes:
        brut = statut or "(vide)"
        avant[brut] = avant.get(brut, 0) + 1
        cible = palier_apres(statut)
        apres[cible] = apres.get(cible, 0) + 1
        if norm(statut) != cible and est_arbitre_d_hier(statut):
            bouges.append((uid, email, brut, cible))

    print("── Statuts ÉCRITS en base aujourd'hui ──")
    for v, n in sorted(avant.items(), key=lambda kv: -kv[1]):
        print("   %-34s %3d compte(s)" % (v, n))

    print("\n── Paliers APRÈS la bascule ──")
    for p in ("admin", "coordinateur", "champion", "user"):
        print("   %-34s %3d compte(s)" % (p, apres.get(p, 0)))

    print("\n── Ce que la reprise RÉÉCRIRAIT (%d compte(s)) ──" % len(bouges))
    if not bouges:
        print("   aucun — rien à reprendre sur cette base")
    for uid, email, brut, cible in bouges:
        print("   #%-5s %-42s %s → %s" % (uid, email, brut, cible))

    # ── Le seul droit réellement perdu par un compte ordinaire ──
    if _table_existe(cur, "entities"):
        cur.execute("SELECT count(*) FROM entities")
        total = cur.fetchone()[0]
        if _colonne_existe(cur, "entities", "is_shared"):
            cur.execute("SELECT count(*) FROM entities WHERE is_shared")
            communes = cur.fetchone()[0]
        else:
            communes = 0
            print("\n   (colonne entities.is_shared absente : le code déployé "
                  "ici est antérieur aux cartos communes)")
        print("\n── Cartographies ──")
        print("   %d au total, dont %d COMMUNE(S)" % (total, communes))
        if communes == 0:
            print("   → aucune carto commune : un compte `user` ne perd RIEN sur")
            print("     l'édition. Le propriétaire d'une carto privée garde tous")
            print("     ses droits, quel que soit son statut.")
        else:
            print("   → sur ces %d carto(s), un compte `user` ne pourra plus"
                  % communes)
            print("     PROPOSER de modification. Le passer `champion` le lui rend.")

    if args.details:
        print("\n── Tous les comptes ──")
        for uid, email, statut in comptes:
            print("   #%-5s %-42s %-28s → %s"
                  % (uid, email, statut or "(vide)", palier_apres(statut)))

    con.rollback()
    con.close()


if __name__ == "__main__":
    main()
