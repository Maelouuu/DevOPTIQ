-- ════════════════════════════════════════════════════════════════════════════
-- LA CHARGE DE TRAVAIL (page RH, section ④) — des analyses DATÉES.
-- À coller dans l'éditeur SQL de Neon.
--
-- Le damier rôle × cartographie ne montre que ce qui est mesuré POUR LE MOIS
-- REGARDÉ. Sur une carto où presque rien n'est daté, il affiche trois cases et
-- une liste de cent rôles « jamais mesuré » : l'écran est juste, il n'a rien à
-- dire. Ce semis lui donne de quoi parler.
--
-- Ce qu'il crée, et pourquoi chaque chose :
--   • des analyses de rôle sur PLUSIEURS MOIS — sans quoi le sélecteur de
--     période n'a qu'une entrée et la notion de période ne se voit pas ;
--   • des poids très INÉGAUX — l'échelle de couleur va de « 25 % d'un temps
--     plein » à « plus de 150 % » : avec des charges voisines, toutes les
--     cases sortent de la même teinte et le damier ne dit rien ;
--   • des TITULAIRES situés sur la carto, pour que la ligne d'un rôle porte
--     ses gens et que « qui performe » se lise ;
--   • et des rôles LAISSÉS sans mesure, volontairement : la zone « sans
--     mesure pour ce mois » est ce qui dit qu'il reste du travail. Une carto
--     où tout est pesé ne la montre jamais.
--
-- ⚠️ `neondb` (officielle AFDEC), `devoptiq_sandbox` (staging) et
--    `optiqfluent_pilot` (pilote ARaymond) vivent sur le MÊME endpoint Neon.
--    LANCEZ D'ABORD LA REQUÊTE 1 : elle dit dans quelle base vous êtes.
--
-- ⚠️ Des données FACTICES. À ne semer que sur une carto de démonstration —
--    « Palier test » et ses semblables — jamais sur la carto d'un client.
-- ════════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 1 — OÙ SUIS-JE, ET QUE PÈSE DÉJÀ CHAQUE CARTO ? (lecture seule)
--
-- Relevez l'`id` de la carto à remplir : c'est lui qu'on donne au bloc, pas
-- son nom. Deux cartos peuvent très bien s'appeler « Palier test » et
-- « palier test 2 » — un fragment de nom ne les départage pas.
-- ─────────────────────────────────────────────────────────────────────────
SELECT current_database()                                    AS base,
       e.id                                                  AS carto_id,
       e.name                                                AS carto,
       (SELECT count(*) FROM activities a
         WHERE a.entity_id = e.id)                           AS activites,
       (SELECT count(DISTINCT ar.role_id) FROM activity_roles ar
          JOIN activities a ON a.id = ar.activity_id
         WHERE a.entity_id = e.id)                           AS roles_portes,
       -- Ce qui manque vraiment : des analyses de rôle qui portent un mois.
       (SELECT count(*) FROM time_role_analysis ra
         WHERE ra.periode IS NOT NULL
           AND EXISTS (SELECT 1 FROM time_role_line rl
                         JOIN activities a ON a.id = rl.activity_id
                        WHERE rl.role_analysis_id = ra.id
                          AND a.entity_id = e.id))           AS analyses_datees,
       (SELECT count(*) FROM time_role_analysis ra
         WHERE ra.periode IS NULL
           AND EXISTS (SELECT 1 FROM time_role_line rl
                         JOIN activities a ON a.id = rl.activity_id
                        WHERE rl.role_analysis_id = ra.id
                          AND a.entity_id = e.id))           AS analyses_sans_date,
       (SELECT count(*) FROM user_roles ur WHERE ur.entity_id = e.id) AS titulaires_situes
FROM entities e
ORDER BY e.id;


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 2 — SEMER. Un seul bloc, atomique : s'il échoue, rien n'est écrit.
--
--   • `carto_id`  : l'identifiant relevé à la requête 1.
--   • `n_mois`    : combien de mois en arrière, le mois courant compris.
--   • `n_roles`   : combien de rôles mesurer. Les autres restent « sans
--                   mesure », et c'est voulu — voir l'en-tête.
--   • `purger`    : à `true`, efface d'abord les analyses de rôle de cette
--                   carto. À n'employer que sur une carto de démonstration.
--
-- ⚠️ IL REFUSE DE REJOUER. Un second passage empilerait une deuxième analyse
--    par (rôle, mois) : le damier n'en retient qu'une — la plus récente —
--    mais la liste des analyses de la page Temps, elle, les montre toutes, et
--    on ne sait plus laquelle est la vraie. `purger := true` pour recommencer.
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  carto_id  int     := 0;        -- ←←← L'IDENTIFIANT DE LA CARTO
  n_mois    int     := 4;        -- ←←← mois à couvrir (courant compris)
  n_roles   int     := 9;        -- ←←← rôles à mesurer
  purger    boolean := false;    -- ←←← true = on efface d'abord
  carto_nom text;
  n_act     int;
  n_dispo   int;
  deja      int;
  plein_min numeric;
  cal_j     int;
  cal_s     int;
  n_ra      int := 0;
  n_li      int := 0;
  n_tit     int := 0;
BEGIN
  -- 1. La carto existe-t-elle, et porte-t-elle de quoi mesurer ?
  SELECT e.name INTO carto_nom FROM entities e WHERE e.id = carto_id;
  IF carto_nom IS NULL THEN
    RAISE EXCEPTION 'Aucune carto #% dans cette base — lancez la requête 1.', carto_id;
  END IF;

  SELECT count(*) INTO n_act FROM activities WHERE entity_id = carto_id;
  IF n_act = 0 THEN
    RAISE EXCEPTION 'La carto #% (%) n''a aucune activité : rien à mesurer.',
                    carto_id, carto_nom;
  END IF;

  -- ⚠️ Seuls les rôles qui PORTENT une activité de CETTE carto. Un rôle est
  --    commun à l'entreprise ; mesuré sur les activités d'une autre carto, il
  --    irait grossir la colonne de l'autre et pas celle qu'on remplit.
  SELECT count(DISTINCT ar.role_id) INTO n_dispo
    FROM activity_roles ar
    JOIN activities a ON a.id = ar.activity_id
   WHERE a.entity_id = carto_id;
  IF n_dispo = 0 THEN
    RAISE EXCEPTION 'Aucun rôle ne porte d''activité sur la carto #% (%) : '
                    'le damier n''aurait aucune ligne à montrer.',
                    carto_id, carto_nom;
  END IF;

  -- 2. Purge, ou refus de rejouer.
  IF purger THEN
    DELETE FROM time_role_line rl USING time_role_analysis ra
     WHERE ra.id = rl.role_analysis_id
       AND EXISTS (SELECT 1 FROM time_role_line x
                     JOIN activities a ON a.id = x.activity_id
                    WHERE x.role_analysis_id = ra.id AND a.entity_id = carto_id);
    DELETE FROM time_role_analysis ra
     WHERE NOT EXISTS (SELECT 1 FROM time_role_line x
                        WHERE x.role_analysis_id = ra.id);
  ELSE
    SELECT count(*) INTO deja
      FROM time_role_analysis ra
     WHERE ra.periode IS NOT NULL
       AND EXISTS (SELECT 1 FROM time_role_line rl
                     JOIN activities a ON a.id = rl.activity_id
                    WHERE rl.role_analysis_id = ra.id AND a.entity_id = carto_id);
    IF deja > 0 THEN
      RAISE EXCEPTION 'La carto #% (%) porte déjà % analyse(s) de rôle datée(s). '
                      'Relancer empilerait des doublons : mettre purger := true '
                      'pour repartir de zéro.', carto_id, carto_nom, deja;
    END IF;
  END IF;

  -- 3. Le calendrier de travail. Sans lui la page lit son repli, et « 36 %
  --    d'un temps plein » ne se rapporte à rien de réglé.
  INSERT INTO entreprise_settings
         (work_hours_per_day, work_days_per_week, work_weeks_per_year, entity_id)
  SELECT 7, 5, 45, carto_id
   WHERE NOT EXISTS (SELECT 1 FROM entreprise_settings s WHERE s.entity_id = carto_id);

  -- 3 bis. Le temps plein de CETTE carto, en minutes : c'est de lui que la
  --        durée de chaque ligne se déduit (voir ci-dessous).
  SELECT COALESCE(s.work_days_per_week, 5)::int,
         COALESCE(s.work_weeks_per_year, 45)::int,
         COALESCE(s.work_hours_per_day, 7)
           * COALESCE(s.work_days_per_week, 5)
           * COALESCE(s.work_weeks_per_year, 45) * 60
    INTO cal_j, cal_s, plein_min
    FROM entreprise_settings s WHERE s.entity_id = carto_id LIMIT 1;
  cal_j := COALESCE(NULLIF(cal_j, 0), 5);
  cal_s := COALESCE(NULLIF(cal_s, 0), 45);
  plein_min := COALESCE(NULLIF(plein_min, 0), 7 * 5 * 45 * 60);

  -- 4. Les analyses, un mois après l'autre.
  --
  -- ⚠️⚠️ ON VISE UNE PART DE TEMPS PLEIN, et on en DÉDUIT la durée — l'inverse
  --    de ce qu'on ferait spontanément. Mesuré sur un premier jet qui posait
  --    des durées « plausibles » : les parts sortaient entre 0 et 49 %, alors
  --    que l'échelle de couleur du damier va de 25 % à plus de 150 %. Toutes
  --    les cases tombaient dans les deux premières teintes, et la couleur —
  --    qui est TOUTE l'information du tableau — ne disait plus rien.
  --    La raison est arithmétique : la RÉCURRENCE écrase tout le reste. Entre
  --    « journalier » et « annuel » il y a un facteur 225 (5 j × 45 sem.), que
  --    nulle durée raisonnable ne rattrape. Une ligne annuelle pèse donc zéro
  --    quoi qu'on y mette.
  --    D'où : une cible par rang (160 % … 6 %, les six teintes couvertes), une
  --    récurrence par rang, et la durée = cible × temps plein ÷ (facteur de
  --    récurrence × fréquence × nombre de lignes). Le damier est lisible sur
  --    N'IMPORTE QUELLE carto, quels que soient son calendrier et le nombre
  --    d'activités de ses rôles.
  --
  -- ⚠️ Et `trimestriel` / `annuel` sont ÉCARTÉS : à cible égale ils
  --    demanderaient des durées absurdes (504 h en une fois). Trois
  --    récurrences suffisent à varier sans mentir.
  WITH vises AS (
    SELECT ar.role_id,
           (row_number() OVER (ORDER BY count(*) DESC, ar.role_id))::int AS rang
      FROM activity_roles ar
      JOIN activities a ON a.id = ar.activity_id AND a.entity_id = carto_id
     GROUP BY ar.role_id
     ORDER BY count(*) DESC, ar.role_id
     LIMIT n_roles
  ), mois AS (
    SELECT k,
           to_char(date_trunc('month', now()) - (k || ' months')::interval,
                   'YYYY-MM') AS periode
      FROM generate_series(0, GREATEST(n_mois, 1) - 1) AS k
  ), creees AS (
    INSERT INTO time_role_analysis (role_id, name, periode, created_at)
    SELECT v.role_id,
           'Charge · ' || to_char(date_trunc('month', now())
                                  - (m.k || ' months')::interval, 'MM/YYYY'),
           m.periode,
           now() - (m.k || ' months')::interval
      FROM vises v CROSS JOIN mois m
    RETURNING id AS ra_id, role_id, periode
  ), lignes AS (
    -- Jusqu'à six activités par analyse, prises dans celles que le rôle porte
    -- SUR CETTE CARTO.
    SELECT c.ra_id, c.role_id, c.periode, a.id AS act_id,
           (row_number() OVER (PARTITION BY c.ra_id ORDER BY a.id))::int AS j,
           count(*) OVER (PARTITION BY c.ra_id)::int                   AS n_li
      FROM creees c
      JOIN activity_roles ar ON ar.role_id = c.role_id
      JOIN activities a ON a.id = ar.activity_id AND a.entity_id = carto_id
  ), dosees AS (
    SELECT l.*, v.rang,
           -- La part de temps plein visée : les six teintes sont couvertes.
           (ARRAY[1.60, 1.15, 0.90, 0.70, 0.52, 0.36,
                  0.24, 0.14, 0.07])[((v.rang - 1) % 9) + 1]
             -- ± 20 % d'un mois à l'autre : sans quoi le sélecteur de période
             -- montre quatre fois le même damier.
             * (1 + ((substr(l.periode, 6, 2)::int % 3) - 1) * 0.20)  AS cible,
           (ARRAY['journalier','hebdomadaire','mensuel'])[((v.rang - 1) % 3) + 1]
                                                                      AS recur,
           1 + ((v.rang + l.j) % 2)                                   AS freq
      FROM lignes l
      JOIN vises v ON v.role_id = l.role_id
     WHERE l.j <= 6
  ), posees AS (
    -- ⚠️ `delay_minutes` et `nb_people` sont NOT NULL : leur défaut vit dans
    --    le MODÈLE (SQLAlchemy), pas dans le schéma — un INSERT en SQL brut
    --    doit donc les écrire lui-même.
    INSERT INTO time_role_line (role_analysis_id, activity_id, duration_minutes,
                                recurrence, frequency, delay_minutes, nb_people)
    SELECT d.ra_id, d.act_id,
           -- cible × temps plein ÷ (facteur de récurrence × fréquence × lignes)
           GREATEST(5, round(
             plein_min * d.cible
             / (CASE d.recur
                  WHEN 'journalier'   THEN COALESCE(cal_j, 5) * COALESCE(cal_s, 45)
                  WHEN 'hebdomadaire' THEN COALESCE(cal_s, 45)
                  ELSE 12 END)::numeric
             / GREATEST(d.freq, 1) / GREATEST(d.n_li, 1)
           ))::int,
           d.recur, d.freq, 0, 1
      FROM dosees d
    RETURNING 1
  )
  SELECT (SELECT count(*) FROM creees), (SELECT count(*) FROM posees)
    INTO n_ra, n_li;

  -- 5. OÙ les titulaires tiennent ces rôles.
  --
  -- ⚠️ On ne REMPLIT que les attaches VIDES : déplacer celle de quelqu'un
  --    changerait sa charge mesurée, et c'est une décision qui appartient à
  --    la page RH, pas à un semis.
  UPDATE user_roles ur
     SET entity_id = carto_id
   WHERE ur.entity_id IS NULL
     AND EXISTS (SELECT 1 FROM activity_roles ar
                   JOIN activities a ON a.id = ar.activity_id
                  WHERE ar.role_id = ur.role_id AND a.entity_id = carto_id);
  GET DIAGNOSTICS n_tit = ROW_COUNT;

  RAISE NOTICE 'Carto #% (%) : % analyse(s) datée(s) sur % mois, % ligne(s), '
               '% titulaire(s) situé(s). % rôle(s) laissé(s) sans mesure.',
               carto_id, carto_nom, n_ra, n_mois, n_li, n_tit,
               GREATEST(n_dispo - n_roles, 0);
END $$;


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 3 — RELIRE. Ce que le damier va montrer, mois par mois.
--
-- ⚠️ Mettez le même `carto_id` qu'à la requête 2.
-- ─────────────────────────────────────────────────────────────────────────
WITH p AS (SELECT 0 AS carto_id)          -- ←←← L'IDENTIFIANT DE LA CARTO
SELECT ra.periode                                   AS mois,
       r.name                                       AS role,
       count(rl.id)                                 AS activites,
       round(sum(rl.duration_minutes) / 60.0, 1)    AS minutes_par_occurrence_h,
       (SELECT count(*) FROM user_roles ur
         WHERE ur.role_id = r.id AND ur.entity_id = (SELECT carto_id FROM p))
                                                    AS titulaires_situes
  FROM time_role_analysis ra
  JOIN roles r ON r.id = ra.role_id
  JOIN time_role_line rl ON rl.role_analysis_id = ra.id
  JOIN activities a ON a.id = rl.activity_id
 WHERE a.entity_id = (SELECT carto_id FROM p)
   AND ra.periode IS NOT NULL
 GROUP BY ra.periode, r.id, r.name
 ORDER BY ra.periode DESC, 4 DESC;
