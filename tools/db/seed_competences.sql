-- ════════════════════════════════════════════════════════════════════════════
-- Remplir la page Compétences d'une carto — à coller dans l'éditeur SQL de Neon.
--
-- Pose des NORMES sur les sorties, des PALIERS de progression et les SESSIONS
-- d'évaluation qui les tranchent. Même carto que `tools/db/seed_temps.sql` :
-- on donne le même `carto_id`.
--
-- ⚠️ `neondb` (officielle AFDEC), `devoptiq_sandbox` (staging) et
--    `optiqfluent_pilot` (pilote ARaymond) vivent sur le MÊME endpoint Neon.
--    LANCEZ D'ABORD LA REQUÊTE 1 : elle dit dans quelle base vous êtes.
--
-- ⚠️ Les normes posées ici sont FICTIVES (des durées, des taux, des comptes).
--    Elles servent à voir l'écran, pas à décrire le métier : sur une vraie
--    carto, c'est le développeur de compétences qui les fixe, sortie par
--    sortie, depuis la fenêtre d'évaluation.
-- ════════════════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 1 — OÙ SUIS-JE, ET QU'EST-CE QU'IL Y A DEDANS ? (lecture seule)
--
-- Relevez l'`id` de la carto à remplir — c'est lui qu'on donne au bloc, pas
-- son nom : deux cartos peuvent très bien s'appeler « test » et « TEST ADMIN
-- Finance », et un fragment de nom ne les départage pas.
--
-- `titulaires` est la colonne qui décide : SANS personne tenant un rôle de
-- cette carto, il n'y a personne à évaluer et le bloc s'arrête sans rien
-- écrire. On ne fabrique pas de collaborateurs.
-- ─────────────────────────────────────────────────────────────────────────
SELECT current_database()                                    AS base,
       e.id                                                  AS carto_id,
       e.name                                                AS carto,
       (SELECT count(*) FROM activities a
         WHERE a.entity_id = e.id)                           AS activites,
       (SELECT count(*) FROM data d JOIN activities a ON a.id = d.producer_activity_id
         WHERE a.entity_id = e.id)                           AS sorties,
       (SELECT count(*) FROM data d JOIN activities a ON a.id = d.producer_activity_id
         WHERE a.entity_id = e.id AND d.norme_valeur IS NOT NULL)
                                                             AS sorties_avec_norme,
       (SELECT count(DISTINCT ur.user_id)
          FROM user_roles ur
          JOIN activity_roles ar ON ar.role_id = ur.role_id
          JOIN activities a ON a.id = ar.activity_id
         WHERE a.entity_id = e.id)                           AS titulaires,
       (SELECT count(*) FROM paliers_performance p
          JOIN activities a ON a.id = p.activity_id
         WHERE a.entity_id = e.id)                           AS paliers,
       (SELECT count(*) FROM sessions_evaluation s
          JOIN user_roles ur ON ur.user_id = s.user_id AND ur.role_id = s.role_id
          JOIN activity_roles ar ON ar.role_id = s.role_id
          JOIN activities a ON a.id = ar.activity_id
         WHERE a.entity_id = e.id)                           AS sessions
FROM entities e
ORDER BY e.id;


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 2 — SEMER. Un seul bloc, atomique : s'il échoue, rien n'est écrit.
--
--   • `carto_id` : l'identifiant relevé à la requête 1.
--   • `purger`   : à `true`, efface d'abord les paliers, les sessions et les
--                  normes de CETTE carto. À n'employer que sur une carto de
--                  mise au point.
--
-- ⚠️ Deux activités sur cinq restent SANS norme, VOLONTAIREMENT. C'est la
--    cohabitation des deux régimes — l'échelle des paliers d'un côté, la note
--    0→4 posée à la main de l'autre — qu'il faut voir dans la même fenêtre.
--    Une carto où tout est mesuré ne montre jamais la moitié de l'écran.
--
-- ⚠️ Quatre parcours différents sont semés, pour que les quatre états que
--    l'écran doit savoir montrer soient présents EN MÊME TEMPS : en cours,
--    qualifié-et-au-delà, palier manqué, échéance dépassée.
-- ─────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  carto_id  int  := 2;          -- ← À RENSEIGNER (requête 1)
  purger    bool := false;      -- ← true efface d'abord ce qui existe

  v_carto   record;
  v_act     record;
  v_sortie  record;
  v_gens    record;
  v_norme   numeric;
  v_unite   text;
  v_sens    text;
  v_scenar  int;
  v_rang    int;
  v_cible   numeric;
  v_mesure  numeric;
  v_jours   int;
  v_statut  text;
  v_ses     int;
  v_dev     int;
  n_act     int := 0;
  n_norme   int := 0;
  n_pal     int := 0;
  n_ses     int := 0;
  i_act     int := 0;
  i_gens    int := 0;
  i_paire   int := 0;
BEGIN
  SELECT id, name INTO v_carto FROM entities WHERE id = carto_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Aucune carto d''identifiant % — relancez la requête 1.', carto_id;
  END IF;

  -- ── Qui tient un rôle sur cette carto ? ──────────────────────────────
  IF NOT EXISTS (SELECT 1 FROM user_roles ur
                   JOIN activity_roles ar ON ar.role_id = ur.role_id
                   JOIN activities a ON a.id = ar.activity_id
                  WHERE a.entity_id = carto_id) THEN
    RAISE EXCEPTION 'Personne ne tient de rôle sur « % » : rien à évaluer. '
                    'Affectez d''abord des collaborateurs depuis la page RH.', v_carto.name;
  END IF;

  -- ── Déjà semé ? ──────────────────────────────────────────────────────
  -- ⚠️ Ce bloc n'est PAS idempotent, et il ne peut pas l'être : rejoué, il
  -- empilerait une seconde progression sur la première — six marches au lieu
  -- de trois, et un historique qui ne veut plus rien dire. Il REFUSE donc
  -- plutôt que de doubler. Fusionner silencieusement serait pire encore :
  -- des paliers fictifs se mêleraient à de vraies évaluations.
  IF NOT purger AND EXISTS (SELECT 1 FROM paliers_performance p
                              JOIN activities a ON a.id = p.activity_id
                             WHERE a.entity_id = carto_id) THEN
    RAISE EXCEPTION 'La carto « % » porte déjà des paliers. '
                    'Pour recommencer : mettez `purger := true` (cela efface ce '
                    'qui est là). Pour garder l''existant : ne relancez pas ce bloc.',
                    v_carto.name;
  END IF;

  -- ── Purge ────────────────────────────────────────────────────────────
  IF purger THEN
    DELETE FROM paliers_performance p
     USING activities a WHERE a.id = p.activity_id AND a.entity_id = carto_id;
    DELETE FROM sessions_evaluation s
     WHERE s.role_id IN (SELECT DISTINCT ar.role_id FROM activity_roles ar
                           JOIN activities a ON a.id = ar.activity_id
                          WHERE a.entity_id = carto_id);
    UPDATE data d SET norme_valeur = NULL, norme_unite = NULL, norme_sens = NULL
      FROM activities a
     WHERE a.id = d.producer_activity_id AND a.entity_id = carto_id;
    RAISE NOTICE 'Purge faite sur « % ».', v_carto.name;
  END IF;

  -- ── 1. Matérialiser les sorties, EXACTEMENT comme l'application ──────
  -- Une sortie d'activité EST une flèche sortante de la carte : son nom est
  -- le libellé de la flèche, à défaut le nom de l'activité visée. Une flèche
  -- qui vise une donnée n'a rien à matérialiser — cette donnée EST déjà la
  -- sortie. (Code/routes/qualify_outputs.py::_current_output_specs)
  INSERT INTO data (entity_id, name, type, producer_activity_id)
  SELECT DISTINCT ON (lk.source_activity_id, lower(btrim(nom)))
         carto_id, btrim(nom), coalesce(lk.type, 'flux'), lk.source_activity_id
    FROM (
      SELECT l.id, l.source_activity_id, l.type,
             coalesce(nullif(btrim(l.description), ''), ta.name) AS nom
        FROM links l
        JOIN activities src ON src.id = l.source_activity_id
        LEFT JOIN activities ta ON ta.id = l.target_activity_id
       WHERE src.entity_id = carto_id AND l.target_data_id IS NULL
    ) lk
   WHERE btrim(coalesce(lk.nom, '')) <> ''
     AND NOT EXISTS (SELECT 1 FROM data d
                      WHERE d.producer_activity_id = lk.source_activity_id
                        AND lower(btrim(d.name)) = lower(btrim(lk.nom)))
   ORDER BY lk.source_activity_id, lower(btrim(nom)), lk.id;

  -- ── 2. Poser les normes, sur trois activités sur cinq ────────────────
  FOR v_act IN
    SELECT a.id, a.name FROM activities a
     WHERE a.entity_id = carto_id
       AND EXISTS (SELECT 1 FROM data d WHERE d.producer_activity_id = a.id)
       AND EXISTS (SELECT 1 FROM activity_roles ar WHERE ar.activity_id = a.id)
     ORDER BY a.id
  LOOP
    i_act := i_act + 1;
    CONTINUE WHEN (i_act % 5) IN (0, 4);      -- deux sur cinq restent à la main
    n_act := n_act + 1;

    FOR v_sortie IN
      SELECT d.id, d.name, row_number() OVER (ORDER BY d.id) AS n
        FROM data d WHERE d.producer_activity_id = v_act.id ORDER BY d.id
    LOOP
      -- Trois grandeurs qui se lisent sans explication : un délai, un taux,
      -- un compte. Le sens change avec la grandeur — c'est lui qui définit
      -- « mieux », et c'est pour ça qu'il est stocké.
      CASE (v_sortie.n % 3)
        WHEN 1 THEN v_norme := 10; v_unite := 'j';       v_sens := 'moins';
        WHEN 2 THEN v_norme := 95; v_unite := '%';       v_sens := 'plus';
        ELSE        v_norme := 5;  v_unite := 'j';       v_sens := 'moins';
      END CASE;
      UPDATE data SET norme_valeur = v_norme, norme_unite = v_unite, norme_sens = v_sens
       WHERE id = v_sortie.id;
      n_norme := n_norme + 1;

      -- ── 3. Une progression par titulaire du rôle ─────────────────────
      i_gens := 0;
      FOR v_gens IN
        SELECT DISTINCT ur.user_id, ur.role_id, ur.manager_id
          FROM user_roles ur
          JOIN activity_roles ar ON ar.role_id = ur.role_id
         WHERE ar.activity_id = v_act.id
         ORDER BY ur.user_id
      LOOP
        i_gens  := i_gens + 1;
        i_paire := i_paire + 1;
        v_dev := coalesce(v_gens.manager_id,
                          (SELECT u.manager_id FROM users u WHERE u.id = v_gens.user_id));
        -- ⚠️ Les quatre parcours tournent sur un compteur de PAIRES
        -- (personne × sortie), pas sur la somme des deux rangs : avec deux
        -- personnes et deux sorties, cette somme ne prenait que trois valeurs
        -- sur quatre — et c'est « qualifié · avancé », la fin heureuse de
        -- l'histoire, qui n'apparaissait jamais à l'écran.
        v_scenar := i_paire % 4;
        v_rang := 0;

        -- Les marches partent du double de la norme (ou de 70 % pour un taux)
        -- et se rapprochent : c'est la règle de `proposer_cible`.
        FOR v_rang IN 1..3 LOOP
          CONTINUE WHEN v_scenar = 2 AND v_rang = 2;   -- parcours court
          IF v_sens = 'moins' THEN
            v_cible := CASE v_rang WHEN 1 THEN v_norme * 2
                                   WHEN 2 THEN v_norme * 1.4
                                   ELSE v_norme END;
          ELSE
            v_cible := CASE v_rang WHEN 1 THEN round(v_norme * 0.7)
                                   WHEN 2 THEN round(v_norme * 0.85)
                                   ELSE v_norme END;
          END IF;

          -- Ce qui a été mesuré, et quand. NULL = palier encore en cours.
          v_mesure := NULL;
          v_jours  := -40 + (v_rang - 1) * 16;
          IF v_rang < 3 THEN
            v_mesure := CASE WHEN v_sens = 'moins' THEN v_cible * 0.95 ELSE v_cible * 1.05 END;
          ELSE
            CASE v_scenar
              -- en cours, échéance à venir
              WHEN 0 THEN v_mesure := NULL;            v_jours := 12;
              -- qualifié, et un palier AU-DELÀ de la norme
              WHEN 1 THEN v_mesure := CASE WHEN v_sens = 'moins' THEN v_norme * 0.45
                                                                 ELSE v_norme * 1.02 END;
                          v_jours := -6;
              -- palier MANQUÉ : c'est lui qui ouvre l'analyse des savoirs
              WHEN 2 THEN v_mesure := CASE WHEN v_sens = 'moins' THEN v_norme * 1.8
                                                                 ELSE v_norme * 0.6 END;
                          v_jours := -4;
              -- échéance DÉPASSÉE, rien n'a encore été relevé
              ELSE        v_mesure := NULL;            v_jours := -3;
            END CASE;
          END IF;
          v_cible  := round(v_cible, 1);
          v_mesure := round(v_mesure, 1);

          IF v_mesure IS NULL THEN
            v_statut := 'en_cours';
          ELSIF (v_sens = 'moins' AND v_mesure <= v_cible)
             OR (v_sens = 'plus'  AND v_mesure >= v_cible) THEN
            v_statut := 'atteint';
          ELSE
            v_statut := 'manque';
          END IF;

          -- Une session par échéance et par personne : c'est elle qui nourrit
          -- le calendrier, et c'est elle qu'on clôt pour trancher.
          SELECT s.id INTO v_ses FROM sessions_evaluation s
           WHERE s.user_id = v_gens.user_id AND s.role_id = v_gens.role_id
             AND s.date_prevue = (CURRENT_DATE + v_jours);
          IF NOT FOUND THEN
            INSERT INTO sessions_evaluation
              (user_id, role_id, developpeur_user_id, date_prevue, statut, tenue_le, created_at)
            VALUES (v_gens.user_id, v_gens.role_id, v_dev, CURRENT_DATE + v_jours,
                    CASE WHEN v_mesure IS NULL THEN 'prevue' ELSE 'tenue' END,
                    CASE WHEN v_mesure IS NULL THEN NULL
                         ELSE (now() + (v_jours || ' days')::interval) END,
                    now())
            RETURNING id INTO v_ses;
            n_ses := n_ses + 1;
          END IF;

          INSERT INTO paliers_performance
            (user_id, activity_id, data_id, role_id, rang, cible_valeur, echeance,
             statut, mesure_valeur, evalue_le, evaluateur_user_id, session_id, created_at)
          VALUES (v_gens.user_id, v_act.id, v_sortie.id, v_gens.role_id, v_rang,
                  v_cible, CURRENT_DATE + v_jours, v_statut, v_mesure,
                  CASE WHEN v_mesure IS NULL THEN NULL
                       ELSE (now() + (v_jours || ' days')::interval) END,
                  CASE WHEN v_mesure IS NULL THEN NULL ELSE v_dev END,
                  v_ses, now());
          n_pal := n_pal + 1;
        END LOOP;
      END LOOP;
    END LOOP;
  END LOOP;

  RAISE NOTICE 'Carto « % » : % activités mesurées, % normes posées, % paliers, % sessions.',
               v_carto.name, n_act, n_norme, n_pal, n_ses;
END $$;


-- ─────────────────────────────────────────────────────────────────────────
-- REQUÊTE 3 — RELIRE CE QUI A ÉTÉ ÉCRIT (lecture seule)
--
-- Une par ligne : qui, sur quelle sortie, où il en est. `niveau_attendu` est
-- ce que l'application DÉDUIRA de la dernière mesure — 2 dès que la norme
-- est atteinte, 3 un palier au-delà. Si l'écran affiche autre chose, c'est
-- là qu'il faut regarder.
-- ─────────────────────────────────────────────────────────────────────────
SELECT u.first_name || ' ' || u.last_name       AS personne,
       a.name                                   AS activite,
       d.name                                   AS sortie,
       d.norme_valeur || ' ' || coalesce(d.norme_unite, '') AS norme,
       d.norme_sens                             AS mieux_c_est,
       count(*)                                 AS paliers,
       -- ⚠️ La DERNIÈRE mesure, pas la plus grande : sur une durée, la plus
       -- grande est la PIRE — on lirait l'inverse de la progression.
       (array_agg(p.mesure_valeur ORDER BY p.rang DESC)
          FILTER (WHERE p.evalue_le IS NOT NULL))[1]          AS derniere_mesure,
       bool_or(p.statut = 'manque')             AS un_palier_manque,
       bool_or(p.statut = 'en_cours')           AS un_palier_en_cours
FROM paliers_performance p
JOIN activities a ON a.id = p.activity_id
JOIN data d       ON d.id = p.data_id
JOIN users u      ON u.id = p.user_id
WHERE a.entity_id = 2                            -- ← le même carto_id
GROUP BY u.first_name, u.last_name, a.name, d.name,
         d.norme_valeur, d.norme_unite, d.norme_sens
ORDER BY personne, activite, sortie;
