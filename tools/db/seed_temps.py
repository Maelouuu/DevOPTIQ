"""Remplir la page Temps d'une carto avec des données plausibles.

    python tools/db/seed_temps.py --url "postgresql://…" --carto test
    python tools/db/seed_temps.py --url "…" --carto test --purge --yes

Une page qui s'ouvre vide ne se juge pas : on ne voit ni les barres par rôle,
ni le repère du temps plein, ni la part des faiblesses. Ce script fabrique de
quoi REGARDER l'écran — à partir des activités et des rôles qui existent
vraiment dans la carto visée, jamais d'activités inventées.

⚠️ **Rien n'est écrit sans `--yes`.** Sans lui, le script dit ce qu'il ferait
et s'arrête. `--purge` efface d'abord TOUTES les données Temps de cette carto
(analyses d'activité, de rôle, faiblesses, projets) — à n'employer que sur une
carto de mise au point.

⚠️ **L'URL ne s'écrit JAMAIS dans un fichier** : elle se passe en argument.

⚠️ **Toutes les activités ne sont pas chiffrées, volontairement.** La carte
« ce qui n'est pas chiffré » est la seule qui dise que le total annoncé ne
porte pas sur toute la carto : si tout est mesuré, on ne la voit jamais, et on
ne sait pas qu'elle existe.
"""
import argparse
import random
import unicodedata
from datetime import datetime, timedelta

import psycopg2


def norm(valeur):
    texte = unicodedata.normalize("NFKD", str(valeur or ""))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.lower().split())


def _colonne_existe(cur, table, colonne):
    cur.execute("""SELECT 1 FROM information_schema.columns
                   WHERE table_name = %s AND column_name = %s""", (table, colonne))
    return cur.fetchone() is not None


# ── Ce qu'on sème ──────────────────────────────────────────────────────────
RECURRENCES = ["journalier", "hebdomadaire", "mensuel", "hebdomadaire", "annuel"]

FAIBLESSES = [
    # (libellé, récurrence, fréquence, 1/N, travail ajouté, attente ajoutée)
    ("Données d'entrée incomplètes", "hebdomadaire", 2, 3, 45, 240),
    ("Interlocuteur indisponible", "hebdomadaire", 1, 4, 20, 1440),
    ("Référence erronée à corriger", "journalier", 1, 12, 15, 0),
    ("Validation qui tarde", "mensuel", 1, 2, 30, 2880),
]

PROJETS = ["Refonte du catalogue", "Campagne de renégociation"]


def _duree(cur, colonnes, act_id, defaut):
    """La durée de la fiche si elle existe, sinon une valeur plausible."""
    if "duration_minutes" not in colonnes:
        return defaut
    cur.execute("SELECT duration_minutes FROM activities WHERE id = %s", (act_id,))
    v = (cur.fetchone() or [None])[0]
    return float(v) if v else defaut


def _delai(cur, colonnes, act_id, defaut):
    if "delay_minutes" not in colonnes:
        return defaut
    cur.execute("SELECT delay_minutes FROM activities WHERE id = %s", (act_id,))
    v = (cur.fetchone() or [None])[0]
    return float(v) if v else defaut


def _carto(cur, nom, entity_id):
    cur.execute("SELECT id, name FROM entities ORDER BY id")
    toutes = cur.fetchall()
    if entity_id:
        vues = [e for e in toutes if e[0] == entity_id]
    else:
        cible = norm(nom)
        vues = [e for e in toutes if cible in norm(e[1])]
    if not vues:
        print("Aucune carto ne correspond. Celles de cette base :")
        for eid, n in toutes:
            print("   #%-5s %s" % (eid, n))
        raise SystemExit(2)
    if len(vues) > 1:
        print("Plusieurs cartos correspondent — précisez avec --entity-id :")
        for eid, n in vues:
            print("   #%-5s %s" % (eid, n))
        raise SystemExit(2)
    return vues[0]


def _etat(cur, eid):
    cur.execute("SELECT id FROM activities WHERE entity_id = %s", (eid,))
    ids = [r[0] for r in cur.fetchall()]
    if not ids:
        return {"activites": 0, "analyses": 0, "roles": 0, "faiblesses": 0, "projets": 0}
    cur.execute("SELECT count(*) FROM time_analysis WHERE type = 'activity' "
                "AND activity_id = ANY(%s)", (ids,))
    analyses = cur.fetchone()[0]
    cur.execute("SELECT count(DISTINCT ra.id) FROM time_role_analysis ra "
                "JOIN time_role_line rl ON rl.role_analysis_id = ra.id "
                "WHERE rl.activity_id = ANY(%s)", (ids,))
    roles = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM time_weakness WHERE activity_id = ANY(%s)", (ids,))
    faib = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM time_project WHERE entity_id = %s", (eid,))
    projets = cur.fetchone()[0]
    return {"activites": len(ids), "analyses": analyses, "roles": roles,
            "faiblesses": faib, "projets": projets}


def _purger(cur, eid):
    cur.execute("SELECT id FROM activities WHERE entity_id = %s", (eid,))
    ids = [r[0] for r in cur.fetchall()]
    if ids:
        cur.execute("DELETE FROM time_weakness WHERE activity_id = ANY(%s)", (ids,))
        cur.execute("DELETE FROM time_analysis WHERE activity_id = ANY(%s)", (ids,))
        cur.execute("""DELETE FROM time_role_analysis WHERE id IN (
                         SELECT DISTINCT role_analysis_id FROM time_role_line
                         WHERE activity_id = ANY(%s))""", (ids,))
    cur.execute("DELETE FROM time_project WHERE entity_id = %s", (eid,))


def semer(cur, eid, nom, ecrire):
    colonnes = {c for c in ("duration_minutes", "delay_minutes")
                if _colonne_existe(cur, "activities", c)}
    cur.execute("SELECT id, name FROM activities WHERE entity_id = %s ORDER BY id", (eid,))
    activites = cur.fetchall()
    if not activites:
        print("Cette carto n'a aucune activité : rien à semer.")
        raise SystemExit(2)

    # Déterministe : rejouer le script sur la même carto donne la même forme.
    alea = random.Random(norm(nom))
    maintenant = datetime.utcnow()
    bilan = {"analyses": 0, "roles": 0, "faiblesses": 0, "projets": 0, "laissees": 0}

    # ── Analyses d'activité : trois sur cinq, pas plus ────────────────────
    for i, (act_id, _) in enumerate(activites):
        if i % 5 >= 3:
            bilan["laissees"] += 1
            continue
        duree = _duree(cur, colonnes, act_id, [30, 45, 60, 90, 120][i % 5])
        rec = RECURRENCES[i % len(RECURRENCES)]
        freq = 1 + (i % 3)
        personnes = 1 + (i % 2)
        bilan["analyses"] += 1
        if ecrire:
            cur.execute("""INSERT INTO time_analysis
                (type, activity_id, task_id, duration, recurrence, frequency,
                 nb_people, delay, impact_unit)
                VALUES ('activity', %s, NULL, %s, %s, %s, %s, NULL, 'minutes')""",
                        (act_id, int(duree), rec, freq, personnes))

    # ── Analyses de rôle : celles qui portent vraiment des activités ──────
    cur.execute("""SELECT r.id, r.name, count(*) FROM roles r
                   JOIN activity_roles ar ON ar.role_id = r.id
                   JOIN activities a ON a.id = ar.activity_id
                   WHERE a.entity_id = %s
                   GROUP BY r.id, r.name HAVING count(*) >= 2
                   ORDER BY count(*) DESC LIMIT 4""", (eid,))
    for role_id, role_nom, _n in cur.fetchall():
        cur.execute("""SELECT a.id FROM activities a
                       JOIN activity_roles ar ON ar.activity_id = a.id
                       WHERE ar.role_id = %s AND a.entity_id = %s ORDER BY a.id""",
                    (role_id, eid))
        siennes = [r[0] for r in cur.fetchall()]
        bilan["roles"] += 1
        if not ecrire:
            continue
        cur.execute("""INSERT INTO time_role_analysis (role_id, name, created_at)
                       VALUES (%s, %s, %s) RETURNING id""",
                    (role_id, "Charge d'un %s" % role_nom.lower(), maintenant))
        ra_id = cur.fetchone()[0]
        for j, act_id in enumerate(siennes):
            duree = _duree(cur, colonnes, act_id, [25, 40, 75][j % 3])
            cur.execute("""INSERT INTO time_role_line
                (role_analysis_id, activity_id, recurrence, frequency,
                 duration_minutes, delay_minutes, nb_people)
                VALUES (%s, %s, %s, %s, %s, 0, 1)""",
                        (ra_id, act_id, RECURRENCES[j % 3], 1 + (j % 2), duree))

    # ── Faiblesses : quatre, de coûts très inégaux ────────────────────────
    cibles = [activites[k][0] for k in
              sorted(alea.sample(range(len(activites)), min(4, len(activites))))]
    for (libelle, rec, freq, denom, travail, attente), act_id in zip(FAIBLESSES, cibles):
        bilan["faiblesses"] += 1
        if ecrire:
            cur.execute("""INSERT INTO time_weakness
                (activity_id, task_id, duration_std_minutes, delay_std_minutes,
                 recurrence, frequency, weakness, work_added_qty, work_added_unit,
                 wait_added_qty, wait_added_unit, prob_denom, created_at)
                VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, 'minutes', %s, 'minutes', %s, %s)""",
                        (act_id, _duree(cur, colonnes, act_id, 60),
                         _delai(cur, colonnes, act_id, 0), rec, freq, libelle,
                         travail, attente, denom, maintenant))

    # ── Projets : ponctuels, ils ne pèsent pas dans la charge annuelle ────
    for p, titre in enumerate(PROJETS):
        lignes = activites[p * 3:p * 3 + 3] or activites[:3]
        bilan["projets"] += 1
        if not ecrire:
            continue
        cur.execute("""INSERT INTO time_project (name, entity_id, created_at)
                       VALUES (%s, %s, %s) RETURNING id""",
                    (titre, eid, maintenant - timedelta(days=3 + p * 6)))
        pid = cur.fetchone()[0]
        for act_id, _ in lignes:
            cur.execute("""INSERT INTO time_project_line
                (project_id, activity_id, duration_minutes, delay_minutes, nb_people)
                VALUES (%s, %s, %s, %s, 2)""",
                        (pid, act_id, _duree(cur, colonnes, act_id, 60),
                         _delai(cur, colonnes, act_id, 0)))

    # ── Le calendrier de travail : sans lui, la page lit son repli ────────
    cur.execute("SELECT id FROM entreprise_settings WHERE entity_id = %s", (eid,))
    if cur.fetchone() is None:
        bilan["calendrier"] = "créé (7 h/j, 5 j/sem, 45 sem/an)"
        if ecrire:
            cur.execute("""INSERT INTO entreprise_settings
                (work_hours_per_day, work_days_per_week, work_weeks_per_year, entity_id)
                VALUES (7, 5, 45, %s)""", (eid,))
    else:
        bilan["calendrier"] = "déjà réglé — laissé tel quel"
    return bilan


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="URL PostgreSQL (jamais dans un fichier)")
    ap.add_argument("--carto", help="nom de la carto (fragment suffit)")
    ap.add_argument("--entity-id", type=int, help="son identifiant, si le nom est ambigu")
    ap.add_argument("--purge", action="store_true",
                    help="efface d'abord TOUTES les données Temps de cette carto")
    ap.add_argument("--yes", action="store_true", help="écrire pour de bon")
    a = ap.parse_args()
    if not a.carto and not a.entity_id:
        ap.error("--carto ou --entity-id")

    cnx = psycopg2.connect(a.url)
    cnx.autocommit = False
    cur = cnx.cursor()
    try:
        eid, nom = _carto(cur, a.carto, a.entity_id)
        print("── Carto #%s « %s »" % (eid, nom))
        avant = _etat(cur, eid)
        print("   avant : %(activites)d activités · %(analyses)d analyses d'activité · "
              "%(roles)d analyses de rôle · %(faiblesses)d faiblesses · %(projets)d projets"
              % avant)

        if a.purge:
            print("   ⚠️  purge : toutes les données Temps de cette carto")
            if a.yes:
                _purger(cur, eid)

        bilan = semer(cur, eid, nom, a.yes)
        print("   semé  : %(analyses)d analyses d'activité · %(roles)d analyses de rôle · "
              "%(faiblesses)d faiblesses · %(projets)d projets" % bilan)
        print("   laissé NON chiffré : %d activités — c'est voulu, sinon la carte "
              "« ce qui n'est pas chiffré » ne se voit jamais" % bilan["laissees"])
        print("   calendrier de travail : %s" % bilan["calendrier"])

        if not a.yes:
            cnx.rollback()
            print("\n   --dry-run : RIEN n'a été écrit. Ajoutez --yes pour appliquer.")
            return
        cnx.commit()
        apres = _etat(cur, eid)
        print("\n   après : %(analyses)d analyses d'activité · %(roles)d analyses de rôle · "
              "%(faiblesses)d faiblesses · %(projets)d projets" % apres)
        print("   ✓ écrit")
    except Exception:
        cnx.rollback()
        raise
    finally:
        cur.close()
        cnx.close()


if __name__ == "__main__":
    main()
