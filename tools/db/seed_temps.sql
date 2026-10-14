-- ════════════════════════════════════════════════════════════════════════════
-- Remplir la page Temps d'une carto — à coller dans l'éditeur SQL de Neon.
--
-- Même contenu que `tools/db/seed_temps.py`, sans avoir à récupérer l'URL de
-- la base : on exécute là où l'on est déjà connecté.
--
-- ⚠️ `neondb` (officielle AFDEC), `devoptiq_sandbox` (staging) et
--    `optiqfluent_pilot` (pilote ARaymond) vivent sur le MÊME endpoint Neon.
--    LANCEZ D'ABORD LA REQUÊTE 1 : elle dit dans quelle base vous êtes.
-- ════════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 1 — OÙ SUIS-JE, ET QU'EST-CE QU'IL Y A DEDANS ? (lecture seule)
-- ─────────────────────────────────────────────────────────────────────────
SELECT current_database()                                   AS base,
       e.id                                                 AS carto_id,
       e.name                                               AS carto,
       (SELECT count(*) FROM activities a
         WHERE a.entity_id = e.id)                          AS activites,
       (SELECT count(*) FROM time_analysis t
          JOIN activities a ON a.id = t.activity_id
         WHERE a.entity_id = e.id AND t.type = 'activity')   AS deja_chiffrees,
       (SELECT count(*) FROM time_weakness w
          JOIN activities a ON a.id = w.activity_id
         WHERE a.entity_id = e.id)                          AS faiblesses,
       (SELECT count(*) FROM time_project p
         WHERE p.entity_id = e.id)                          AS projets
FROM entities e
ORDER BY e.id;


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 2 — SEMER. Un seul bloc, atomique : s'il échoue, rien n'est écrit.
--
--   • `carto_nom` : un fragment du nom suffit, mais il doit désigner UNE
--     seule carto — sinon le bloc s'arrête et vous le dit.
--   • `purger`    : à `true`, efface d'abord TOUTES les données Temps de
--     cette carto. À n'employer que sur une carto de mise au point.
--
-- ⚠️ Trois activités sur cinq seulement sont chiffrées, VOLONTAIREMENT : la
--    carte « ce qui n'est pas chiffré » est la seule qui dise que le total
--    affiché ne porte pas sur toute la carto. Si tout est mesuré, on ne la
--    voit jamais, et on ne sait pas qu'elle existe.
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  carto_nom  text    := 'test';     -- ←←← LE NOM DE LA CARTO
  purger     boolean := false;      -- ←←← true = on efface d'abord
  eid        int;
  combien    int;
  n_act      int;
BEGIN
  -- 1. Retrouver la carto, et UNE SEULE.
  SELECT count(*) INTO combien FROM entities e
   WHERE lower(e.name) LIKE '%' || lower(carto_nom) || '%';
  IF combien = 0 THEN
    RAISE EXCEPTION 'Aucune carto ne contient « % » — lancez la requête 1.', carto_nom;
  ELSIF combien > 1 THEN
    RAISE EXCEPTION '% cartos contiennent « % » : précisez le nom.', combien, carto_nom;
  END IF;
  SELECT e.id INTO eid FROM entities e
   WHERE lower(e.name) LIKE '%' || lower(carto_nom) || '%';

  SELECT count(*) INTO n_act FROM activities WHERE entity_id = eid;
  IF n_act = 0 THEN
    RAISE EXCEPTION 'La carto #% n''a aucune activité : rien à semer.', eid;
  END IF;

  -- 2. Purge éventuelle.
  IF purger THEN
    DELETE FROM time_weakness w USING activities a
      WHERE a.id = w.activity_id AND a.entity_id = eid;
    DELETE FROM time_analysis t USING activities a
      WHERE a.id = t.activity_id AND a.entity_id = eid;
    DELETE FROM time_role_analysis ra WHERE ra.id IN (
      SELECT DISTINCT rl.role_analysis_id FROM time_role_line rl
        JOIN activities a ON a.id = rl.activity_id WHERE a.entity_id = eid);
    DELETE FROM time_project WHERE entity_id = eid;
  END IF;

  -- 3. Le calendrier de travail. Sans lui la page lit son repli, et les
  --    heures annuelles ne correspondent à rien de réglé.
  INSERT INTO entreprise_settings
         (work_hours_per_day, work_days_per_week, work_weeks_per_year, entity_id)
  SELECT 7, 5, 45, eid
   WHERE NOT EXISTS (SELECT 1 FROM entreprise_settings s WHERE s.entity_id = eid);

  -- 4. Analyses d'activité : trois sur cinq, pas plus.
  INSERT INTO time_analysis
         (type, activity_id, task_id, duration, recurrence, frequency,
          nb_people, delay, impact_unit)
  SELECT 'activity', x.id, NULL,
         round(x.duree)::int,
         (ARRAY['journalier','hebdomadaire','mensuel','hebdomadaire','annuel'])[(x.i % 5) + 1],
         1 + (x.i % 3), 1 + (x.i % 2), NULL, 'minutes'
    FROM (SELECT a.id,
                 COALESCE(NULLIF(a.duration_minutes, 0), 60) AS duree,
                 (row_number() OVER (ORDER BY a.id))::int - 1 AS i
            FROM activities a WHERE a.entity_id = eid) x
   WHERE x.i % 5 < 3;

  -- 5. Analyses de rôle : les rôles qui portent vraiment des activités.
  WITH vises AS (
    SELECT r.id, r.name
      FROM roles r
      JOIN activity_roles ar ON ar.role_id = r.id
      JOIN activities a ON a.id = ar.activity_id AND a.entity_id = eid
     GROUP BY r.id, r.name
    HAVING count(*) >= 2
     ORDER BY count(*) DESC
     LIMIT 4
  ), nouvelles AS (
    INSERT INTO time_role_analysis (role_id, name, created_at)
    SELECT v.id, 'Charge d''un ' || lower(v.name), now()
      FROM vises v
    RETURNING id AS ra_id, role_id
  ), lignes AS (
    SELECT n.ra_id, a.id AS act_id,
           COALESCE(NULLIF(a.duration_minutes, 0), 45) AS duree,
           (row_number() OVER (PARTITION BY n.ra_id ORDER BY a.id))::int - 1 AS j
      FROM nouvelles n
      JOIN activity_roles ar ON ar.role_id = n.role_id
      JOIN activities a ON a.id = ar.activity_id AND a.entity_id = eid
  )
  INSERT INTO time_role_line
         (role_analysis_id, activity_id, recurrence, frequency,
          duration_minutes, delay_minutes, nb_people)
  SELECT l.ra_id, l.act_id,
         (ARRAY['journalier','hebdomadaire','mensuel'])[(l.j % 3) + 1],
         1 + (l.j % 2), l.duree, 0, 1
    FROM lignes l;

  -- 6. Faiblesses : quatre, de coûts très inégaux — et réparties sur la
  --    carto, pas toutes sur les quatre premières activités.
  INSERT INTO time_weakness
         (activity_id, task_id, duration_std_minutes, delay_std_minutes,
          recurrence, frequency, weakness, work_added_qty, work_added_unit,
          wait_added_qty, wait_added_unit, prob_denom, created_at)
  SELECT a.id, NULL,
         COALESCE(NULLIF(a.duration_minutes, 0), 60),
         COALESCE(a.delay_minutes, 0),
         p.rec, p.freq, p.libelle,
         p.travail, 'minutes', p.attente, 'minutes', p.denom, now()
    FROM (VALUES
            (1, 'Données d''entrée incomplètes', 'hebdomadaire', 2,  3, 45,  240),
            (2, 'Interlocuteur indisponible',    'hebdomadaire', 1,  4, 20, 1440),
            (3, 'Référence erronée à corriger',  'journalier',   1, 12, 15,    0),
            (4, 'Validation qui tarde',          'mensuel',      1,  2, 30, 2880)
         ) AS p(k, libelle, rec, freq, denom, travail, attente)
    JOIN (SELECT a2.id, a2.duration_minutes, a2.delay_minutes,
                 (row_number() OVER (ORDER BY a2.id))::int AS rn
            FROM activities a2 WHERE a2.entity_id = eid) a
      ON a.rn = 1 + (p.k - 1) * GREATEST(1, n_act / 4);

  -- 7. Deux projets. Ponctuels : ils ne pèsent pas dans la charge annuelle.
  WITH projets AS (
    INSERT INTO time_project (name, entity_id, created_at)
    SELECT v.titre, eid, now() - make_interval(days => v.k * 3)
      FROM (VALUES (1, 'Refonte du catalogue'),
                   (2, 'Campagne de renégociation')) AS v(k, titre)
    RETURNING id AS pid
  ), ordonnes AS (
    SELECT pid, (row_number() OVER (ORDER BY pid))::int AS k FROM projets
  )
  INSERT INTO time_project_line
         (project_id, activity_id, duration_minutes, delay_minutes, nb_people)
  SELECT o.pid, a.id,
         COALESCE(NULLIF(a.duration_minutes, 0), 60),
         COALESCE(a.delay_minutes, 0), 2
    FROM ordonnes o
    JOIN (SELECT a2.id, a2.duration_minutes, a2.delay_minutes,
                 (row_number() OVER (ORDER BY a2.id))::int AS rn
            FROM activities a2 WHERE a2.entity_id = eid) a
      ON a.rn BETWEEN (o.k - 1) * 3 + 1 AND (o.k - 1) * 3 + 3;

  RAISE NOTICE 'Carto #% (%) : semé sur % activités.', eid, carto_nom, n_act;
END $$;


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 3 — contrôle : relancez la REQUÊTE 1, les compteurs doivent avoir
-- bougé sur la ligne de votre carto (et sur elle seule).
-- ─────────────────────────────────────────────────────────────────────────
