-- ═══════════════════════════════════════════════════════════════════════════
--  END_DT — socle de présentation
--  À coller dans l'éditeur SQL de Neon, sur la base du PILOTE.
--  ───────────────────────────────────────────────────────────────────────────
--  Trois requêtes, dans cet ordre :
--    1 · INVENTAIRE   — lecture seule, pour vérifier les noms AVANT d'écrire
--    2 · LE SEMIS     — un seul bloc atomique : tout passe, ou rien
--    3 · RELECTURE    — ce qui a été écrit, et qui peut l'ouvrir
--
--  ⚠️ La carto n'est PAS re-dérivée du diagramme : on COPIE les lignes que
--     `_sync_carto_to_db` a déjà produites pour « jeudi ». Réécrire cette
--     dérivation en SQL en ferait une seconde implémentation, et les deux
--     finiraient par ne plus dire la même chose. Le diagramme lui-même
--     (`optiqcarto_data`) est recopié tel quel : la carto est donc EXACTE.
--
--  ⚠️ Il REFUSE de rejouer. Un second passage empilerait une deuxième copie
--     des activités et des analyses, et l'écran ne voudrait plus rien dire.
--
--  POUR UNE AUTRE SOURCE OU D'AUTRES COMPTES : remplacez les quatre
--  '%jeudi%', et les '%girardin%' / '%grandjean%'. Rien d'autre n'est à
--  toucher — le reste part de ce que la requête 1 a trouvé.
--
--  Éprouvé sur un vrai PostgreSQL 16, schéma monté par le démarrage NORMAL de
--  l'application : un SQL que SQLite accepte et que PostgreSQL refuse ne se
--  verrait qu'une fois sous les yeux du client.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══ 1 · INVENTAIRE ════════════════════════════════════════════════════════
-- Lancez CECI d'abord, et vérifiez trois choses :
--   · la carto source est bien celle à copier, et il n'y en a QU'UNE ;
--   · les deux comptes sont les bons ;
--   · END_DT n'existe pas encore.

SELECT 'carto source'         AS quoi, e.id, e.name AS libelle,
       (SELECT count(*) FROM activities a WHERE a.entity_id = e.id) AS activites,
       (e.optiqcarto_data IS NOT NULL)  AS a_un_diagramme
  FROM entities e
 WHERE lower(e.name) LIKE '%jeudi%'
UNION ALL
SELECT 'END_DT existe deja !', e.id, e.name, NULL, NULL
  FROM entities e
 WHERE lower(trim(e.name)) = 'end_dt'
UNION ALL
SELECT 'compte', u.id,
       u.first_name || ' ' || u.last_name || '  <' || u.email || '>  [' || u.status || ']',
       NULL, NULL
  FROM users u
 WHERE lower(u.first_name || ' ' || u.last_name) LIKE '%girardin%'
    OR lower(u.first_name || ' ' || u.last_name) LIKE '%grandjean%'
 ORDER BY 1, 2;


-- ═══ 2 · LE SEMIS ══════════════════════════════════════════════════════════
-- Un seul bloc : si une ligne échoue, RIEN n'est écrit.
-- Regardez la sortie « Messages » / « Notices » de Neon : le bloc raconte ce
-- qu'il fait, et dit en clair si le partage n'a pas pu être posé.

DO $$
DECLARE
  v_src       integer;
  v_src_nom   text;
  v_new       integer;
  v_mael      integer;
  v_hubert    integer;
  r           record;
  v_act       integer;
  v_i         integer := 0;
  v_dur       double precision;
  v_del       double precision;
  v_proj      integer;
  v_ra        integer;
  v_role      integer;
  v_n         integer;
  v_chiffrees integer := 0;
  v_actes     integer;
  -- Des valeurs PLAUSIBLES, pas aléatoires : une échelle qui se relit.
  v_durees numeric[] := ARRAY[20,45,90,30,180,25,60,15,120,75,40,35];
  v_delais numeric[] := ARRAY[0,120,1440,60,480,0,240,0,2880,360,0,60];
  v_recs   text[]    := ARRAY['journalier','hebdomadaire','mensuel','hebdomadaire',
                              'trimestriel','journalier','mensuel','hebdomadaire'];
BEGIN
  -- ── la carto source ───────────────────────────────────────────────────
  SELECT count(*) INTO v_n FROM entities WHERE lower(name) LIKE '%jeudi%';
  IF v_n = 0 THEN
    RAISE EXCEPTION 'Aucune carto dont le nom contient jeudi. Lancez la requete 1.';
  END IF;
  IF v_n > 1 THEN
    RAISE EXCEPTION 'Plusieurs cartos contiennent jeudi (%). Remplacez le LIKE par le nom exact.', v_n;
  END IF;
  SELECT id, name INTO v_src, v_src_nom FROM entities WHERE lower(name) LIKE '%jeudi%';

  IF (SELECT optiqcarto_data FROM entities WHERE id = v_src) IS NULL THEN
    RAISE EXCEPTION 'La carto #% (%) ne porte aucun diagramme : rien a copier.', v_src, v_src_nom;
  END IF;

  -- ── les deux comptes ──────────────────────────────────────────────────
  SELECT id INTO v_mael FROM users
   WHERE lower(first_name || ' ' || last_name) LIKE '%girardin%' ORDER BY id LIMIT 1;
  SELECT id INTO v_hubert FROM users
   WHERE lower(first_name || ' ' || last_name) LIKE '%grandjean%' ORDER BY id LIMIT 1;
  IF v_mael   IS NULL THEN RAISE EXCEPTION 'Compte Girardin introuvable.';  END IF;
  IF v_hubert IS NULL THEN RAISE EXCEPTION 'Compte Grandjean introuvable.'; END IF;

  -- ── ⚠️ on ne rejoue pas ───────────────────────────────────────────────
  IF EXISTS (SELECT 1 FROM entities WHERE lower(trim(name)) = 'end_dt') THEN
    RAISE EXCEPTION 'END_DT existe deja : un second passage empilerait une deuxieme copie. Supprimez-la pour recommencer.';
  END IF;

  -- ── la carto, copiee a l identique ────────────────────────────────────
  INSERT INTO entities (name, description, owner_id, svg_filename, svg_content,
                        vsdx_filename, optiqcarto_data, is_active, is_shared,
                        statuts_regles)
  SELECT 'END_DT',
         'Socle de presentation - copie de ' || e.name,
         v_mael, e.svg_filename, e.svg_content, e.vsdx_filename, e.optiqcarto_data,
         false, false, false
    FROM entities e WHERE e.id = v_src
  RETURNING id INTO v_new;
  RAISE NOTICE 'END_DT creee : carto #% (copie de #% %)', v_new, v_src, v_src_nom;

  -- ── les activites, avec leur correspondance ancien -> nouveau ─────────
  -- ⚠️ Une par une, et non un INSERT…SELECT : il FAUT la correspondance pour
  --    remapper les connexions et les roles, et `shape_id` ne suffit pas (il
  --    peut etre NUL).
  CREATE TEMP TABLE _map (ancien integer PRIMARY KEY, nouveau integer) ON COMMIT DROP;

  FOR r IN SELECT * FROM activities WHERE entity_id = v_src ORDER BY id LOOP
    v_i := v_i + 1;
    -- La duree de la source si elle en a une, sinon une valeur plausible :
    -- on ne REMPLACE jamais un chiffre que quelqu un a saisi.
    v_dur := COALESCE(NULLIF(r.duration_minutes, 0), v_durees[1 + (v_i % 12)]);
    v_del := COALESCE(NULLIF(r.delay_minutes, 0),    v_delais[1 + (v_i % 12)]);

    INSERT INTO activities (entity_id, shape_id, name, description, is_result,
                            shape_subtype, cadence_code, cadence_details,
                            duration_minutes, delay_minutes)
    VALUES (v_new, r.shape_id, r.name, r.description, r.is_result,
            r.shape_subtype, r.cadence_code, r.cadence_details, v_dur, v_del)
    RETURNING id INTO v_act;

    INSERT INTO _map (ancien, nouveau) VALUES (r.id, v_act);
  END LOOP;

  SELECT count(*) INTO v_actes FROM _map;
  IF v_actes = 0 THEN
    RAISE EXCEPTION 'La carto source n a aucune activite : il n y a rien a presenter.';
  END IF;
  RAISE NOTICE '  % activites copiees', v_actes;

  -- ── les roles portes par ces activites ───────────────────────────────
  -- ⚠️ Les roles sont COMMUNS a l entreprise : on ne les recopie PAS, on
  --    rattache les MEMES aux nouvelles activites.
  INSERT INTO activity_roles (activity_id, role_id, status, required_mastery_level)
  SELECT m.nouveau, ar.role_id, ar.status, ar.required_mastery_level
    FROM activity_roles ar JOIN _map m ON m.ancien = ar.activity_id
   ON CONFLICT DO NOTHING;

  -- ── les connexions ───────────────────────────────────────────────────
  -- ⚠️ Seules les connexions activite -> activite sont copiees. Une connexion
  --    dont un bout est une DONNEE pointerait la Data de l AUTRE carto : on la
  --    laisse, et le prochain enregistrement de la carto dans l editeur la
  --    recreera depuis le diagramme, qui est copie tel quel.
  -- ⚠️ `cross_carto_liaison_id` non plus : il designe une liaison qui
  --    appartient a la carto d origine.
  INSERT INTO links (entity_id, source_activity_id, target_activity_id,
                     source_data_id, target_data_id, type, description,
                     cross_carto_label, choice_label)
  SELECT v_new, ms.nouveau, mt.nouveau, NULL, NULL, l.type, l.description,
         l.cross_carto_label, l.choice_label
    FROM links l
    JOIN _map ms ON ms.ancien = l.source_activity_id
    JOIN _map mt ON mt.ancien = l.target_activity_id
   WHERE l.entity_id = v_src;

  RAISE NOTICE '  % connexions, % rattachements de role',
    (SELECT count(*) FROM links WHERE entity_id = v_new),
    (SELECT count(*) FROM activity_roles ar JOIN _map m ON m.nouveau = ar.activity_id);

  -- ── le partage ───────────────────────────────────────────────────────
  -- ⚠️ `can_read` n ouvre une carto commune que par ROLE ou par PALIER de
  --    statut : il n existe PAS de partage compte par compte. "A nous deux" se
  --    traduit donc par : proprietaire = Mael, plus exactement les roles que
  --    Hubert tient ET qui portent une activite d ICI.
  -- ⚠️ Et si cette intersection est VIDE, la carto reste PRIVEE : une carto
  --    commune sans aucun role autorise est ouverte A TOUS, le contraire de ce
  --    qui est demande.
  -- ⚠️ On n ouvre qu UN role, et c est celui qui a LE MOINS DE TITULAIRES : un
  --    role autorise ouvre la carto a TOUS ceux qui le tiennent, pas au seul
  --    Hubert. "A nous deux" se traduit donc par "le moins de monde d autre",
  --    et le bloc le DIT (la requete 3 nomme ensuite tout le monde).
  -- ⚠️ Le role doit porter une activite d ICI : `_sync_carto_to_db` efface
  --    l acces d un role absent de la carte, donc un role pris ailleurs
  --    s evaporerait au premier enregistrement de la carto dans l editeur.
  SELECT ar.role_id INTO v_role
    FROM activity_roles ar
    JOIN _map m        ON m.nouveau = ar.activity_id
    JOIN user_roles ur ON ur.role_id = ar.role_id AND ur.user_id = v_hubert
   GROUP BY ar.role_id
   ORDER BY (SELECT count(*) FROM user_roles u2 WHERE u2.role_id = ar.role_id),
            ar.role_id
   LIMIT 1;

  IF v_role IS NULL THEN
    RAISE NOTICE '  !! PARTAGE NON POSE : Hubert ne tient aucun role de cette carto.';
    RAISE NOTICE '     La carto reste PRIVEE (Mael, plus les administrateurs).';
    RAISE NOTICE '     Donnez-lui un role de la carto depuis la page RH, puis';
    RAISE NOTICE '     lancez la requete 4, en bas de ce fichier.';
  ELSE
    UPDATE entities SET is_shared = true WHERE id = v_new;
    INSERT INTO entity_role_access (entity_id, role_id, created_at)
    VALUES (v_new, v_role, now())
     ON CONFLICT DO NOTHING;
    SELECT count(*) INTO v_n FROM user_roles WHERE role_id = v_role;
    RAISE NOTICE '  partage : carto commune, ouverte par le role « % » (#%)',
      COALESCE((SELECT name FROM roles WHERE id = v_role), '?'), v_role;
    IF v_n > 1 THEN
      RAISE NOTICE '     !! ce role a % titulaires : % compte(s) autre(s) que Hubert', v_n, v_n - 1;
      RAISE NOTICE '        entreront aussi. La requete 3 les nomme.';
    ELSE
      RAISE NOTICE '     Hubert est son seul titulaire : personne d autre n entre par ce role.';
    END IF;
  END IF;

  -- ── le calendrier de travail (toute la page Temps en depend) ──────────
  -- ⚠️ Sans ligne pour CETTE carto, `get_calendar_params` retombe sur la
  --    PREMIERE ligne de la table, c est-a-dire le calendrier d une autre
  --    entite.
  INSERT INTO entreprise_settings (entity_id, work_hours_per_day,
                                   work_days_per_week, work_weeks_per_year,
                                   work_days_per_year)
  SELECT v_new, 7.5, 5, 45, 225
   WHERE NOT EXISTS (SELECT 1 FROM entreprise_settings WHERE entity_id = v_new);

  -- ═══ LES DONNEES DE TEMPS ══════════════════════════════════════════════

  -- 1 · ANALYSES D ACTIVITE
  -- ⚠️ PAS toutes, volontairement : la carte "ce qui n est pas chiffre" est la
  --    seule qui dise que le total annonce ne porte pas sur toute la carto. Si
  --    tout est mesure, on ne la voit jamais.
  v_i := 0;
  FOR r IN SELECT a.id, a.duration_minutes, a.delay_minutes
             FROM activities a JOIN _map m ON m.nouveau = a.id
            ORDER BY a.id LOOP
    v_i := v_i + 1;
    CONTINUE WHEN (v_i % 5) = 0;          -- une sur cinq reste non chiffree
    INSERT INTO time_analysis (type, activity_id, task_id, duration, recurrence,
                               frequency, delay, nb_people)
    VALUES ('activity', r.id, NULL,
            GREATEST(1, round(COALESCE(r.duration_minutes, 30))::int),
            v_recs[1 + (v_i % 8)],
            1 + (v_i % 3),
            GREATEST(0, round(COALESCE(r.delay_minutes, 0))::int),
            1 + (v_i % 2));
    v_chiffrees := v_chiffrees + 1;
  END LOOP;
  RAISE NOTICE '  % analyses d activite (sur % activites)', v_chiffrees, v_actes;

  -- 2 · PROJETS — deux, avec leurs lignes
  FOR v_i IN 1..2 LOOP
    INSERT INTO time_project (entity_id, name, created_at)
    VALUES (v_new,
            CASE v_i WHEN 1 THEN 'Lancement d une nouvelle reference'
                     ELSE 'Revue annuelle des fournisseurs' END,
            now() - ((v_i * 9) || ' days')::interval)
    RETURNING id INTO v_proj;

    INSERT INTO time_project_line (project_id, activity_id, duration_minutes,
                                   delay_minutes, nb_people)
    SELECT v_proj, t.id, COALESCE(t.duration_minutes, 30),
           COALESCE(t.delay_minutes, 0), 1 + (v_i % 2)
      FROM (SELECT a.id, a.duration_minutes, a.delay_minutes
              FROM activities a JOIN _map m ON m.nouveau = a.id
             ORDER BY a.id OFFSET (v_i - 1) * 3 LIMIT 3) t;
  END LOOP;
  RAISE NOTICE '  2 projets';

  -- 3 · ANALYSES DE ROLE — les deux roles qui portent le plus d activites
  -- ⚠️ Les lignes d une analyse de role sont les activites DE CE ROLE : c est
  --    le role qui definit son perimetre, et l ecran n en propose pas d autres.
  -- ⚠️ Le tableau de bord cadre une analyse de role par ses LIGNES : celles-ci
  --    pointent END_DT, donc l analyse ne paraitra pas sur "jeudi", meme si le
  --    role est commun aux deux.
  -- ⚠️ Et on prend TOUTES les activites du role (plafond 20, pour qu un
  --    formulaire reste lisible) : plafonner plus bas couperait sa charge en
  --    deux, et les deux analyses se retrouveraient toutes les deux SOUS le
  --    temps plein — la variante la moins parlante de la carte des roles. Avec
  --    leur perimetre reel, le role le plus charge le DEPASSE.
  v_i := 0;
  FOR v_role IN
      SELECT ar.role_id
        FROM activity_roles ar JOIN _map m ON m.nouveau = ar.activity_id
       GROUP BY ar.role_id ORDER BY count(*) DESC, ar.role_id LIMIT 2
  LOOP
    v_i := v_i + 1;
    INSERT INTO time_role_analysis (role_id, name, created_at)
    VALUES (v_role,
            'Charge de ' || COALESCE((SELECT name FROM roles WHERE id = v_role), 'ce role'),
            now() - ((v_i * 4) || ' days')::interval)
    RETURNING id INTO v_ra;

    INSERT INTO time_role_line (role_analysis_id, activity_id, recurrence,
                                frequency, duration_minutes, delay_minutes, nb_people)
    SELECT v_ra, t.id, v_recs[1 + (t.rn % 8)], 1 + (t.rn % 3),
           COALESCE(t.duration_minutes, 30), COALESCE(t.delay_minutes, 0), 1
      FROM (SELECT a.id, a.duration_minutes, a.delay_minutes,
                   (row_number() OVER (ORDER BY a.id))::int AS rn
              FROM activities a
              JOIN _map m ON m.nouveau = a.id
             WHERE EXISTS (SELECT 1 FROM activity_roles ar
                            WHERE ar.activity_id = a.id AND ar.role_id = v_role)
             ORDER BY a.id LIMIT 20) t;
  END LOOP;
  RAISE NOTICE '  % analyses de role', v_i;

  -- 4 · FAIBLESSES — trois, de couts tres inegaux
  -- ⚠️ `work_added` est du TRAVAIL refait, `wait_added` du temps d HORLOGE :
  --    l application ne les additionne jamais. Trois cas differents pour que la
  --    carte "ce que coute le retard" se lise — une qui coute surtout du
  --    travail, une surtout de l attente, une qui ne fait pas attendre.
  -- ⚠️ Le delai standard ne tombe pas sous la duree de travail
  --    (`delai_plancher`) : l ecran le bornerait a l enregistrement, donc on
  --    n ecrit pas un etat qu il refuserait.
  v_i := 0;
  FOR r IN SELECT a.id, a.duration_minutes, a.delay_minutes
             FROM activities a JOIN _map m ON m.nouveau = a.id
            ORDER BY a.id OFFSET 1 LIMIT 3 LOOP
    v_i := v_i + 1;
    INSERT INTO time_weakness (activity_id, task_id, duration_std_minutes,
                               delay_std_minutes, recurrence, frequency, weakness,
                               work_added_qty, work_added_unit,
                               wait_added_qty, wait_added_unit,
                               prob_denom, created_at)
    VALUES (r.id, NULL,
            COALESCE(NULLIF(r.duration_minutes, 0), 30),
            GREATEST(COALESCE(NULLIF(r.delay_minutes, 0), 120),
                     COALESCE(NULLIF(r.duration_minutes, 0), 30)),
            CASE v_i WHEN 1 THEN 'hebdomadaire' WHEN 2 THEN 'mensuel' ELSE 'journalier' END,
            CASE v_i WHEN 1 THEN 3 WHEN 2 THEN 1 ELSE 1 END,
            CASE v_i WHEN 1 THEN 'Donnees techniques manquantes'
                     WHEN 2 THEN 'Fournisseur qui ne repond pas'
                     ELSE 'Reference article erronee' END,
            CASE v_i WHEN 1 THEN 45 WHEN 2 THEN 20 ELSE 15 END, 'minutes',
            CASE v_i WHEN 1 THEN 180 WHEN 2 THEN 2880 ELSE 0 END, 'minutes',
            CASE v_i WHEN 1 THEN 2 WHEN 2 THEN 3 ELSE 10 END,
            now() - ((v_i * 2) || ' days')::interval);
  END LOOP;
  RAISE NOTICE '  3 faiblesses';

  -- `prob_percent` est arrive le 03/11 : present si l instance a redemarre avec
  -- le code courant. On ne presume pas, on regarde.
  IF EXISTS (SELECT 1 FROM information_schema.columns
              WHERE table_name = 'time_weakness' AND column_name = 'prob_percent') THEN
    EXECUTE 'UPDATE time_weakness SET prob_percent = 100.0 / GREATEST(1, prob_denom)
              WHERE prob_percent IS NULL
                AND activity_id IN (SELECT nouveau FROM _map)';
  END IF;

  RAISE NOTICE 'TERMINE. END_DT = carto #%', v_new;
END $$;


-- ═══ 3 · RELECTURE ═════════════════════════════════════════════════════════

SELECT e.id, e.name, e.is_shared,
       (SELECT count(*) FROM activities a WHERE a.entity_id = e.id)          AS activites,
       (SELECT count(*) FROM links l WHERE l.entity_id = e.id)               AS connexions,
       (SELECT count(*) FROM entity_role_access x WHERE x.entity_id = e.id)  AS roles_ouverts,
       (SELECT count(*) FROM time_analysis t WHERE t.type = 'activity'
          AND t.activity_id IN (SELECT id FROM activities WHERE entity_id = e.id)) AS ana_activite,
       (SELECT count(*) FROM time_project p WHERE p.entity_id = e.id)        AS projets,
       (SELECT count(DISTINCT rl.role_analysis_id) FROM time_role_line rl
          WHERE rl.activity_id IN (SELECT id FROM activities WHERE entity_id = e.id)) AS ana_role,
       (SELECT count(*) FROM time_weakness w
          WHERE w.activity_id IN (SELECT id FROM activities WHERE entity_id = e.id)) AS faiblesses,
       (SELECT count(*) FROM entreprise_settings s WHERE s.entity_id = e.id)  AS calendrier
  FROM entities e
 WHERE lower(trim(e.name)) = 'end_dt';

-- Qui peut l'ouvrir PAR SON ROLE (le propriétaire et les administrateurs
-- entrent de toute façon) :
SELECT DISTINCT u.first_name || ' ' || u.last_name AS compte, u.email, u.status
  FROM entity_role_access era
  JOIN user_roles ur ON ur.role_id = era.role_id
  JOIN users u       ON u.id = ur.user_id
 WHERE era.entity_id = (SELECT id FROM entities WHERE lower(trim(name)) = 'end_dt')
 ORDER BY 1;


-- ═══ 4 · SI LE PARTAGE N'A PAS ÉTÉ POSÉ ════════════════════════════════════
-- (Les notices l'auront dit.) Donnez d'abord à Hubert un rôle de END_DT depuis
-- la page RH, puis décommentez et lancez ceci :
--
-- DO $$
-- DECLARE v_e integer; v_h integer; v_r integer; n integer;
-- BEGIN
--   SELECT id INTO v_e FROM entities WHERE lower(trim(name)) = 'end_dt';
--   SELECT id INTO v_h FROM users
--    WHERE lower(first_name || ' ' || last_name) LIKE '%grandjean%' ORDER BY id LIMIT 1;
--   -- le role qu il tient avec LE MOINS de titulaires (meme regle qu au semis)
--   SELECT ar.role_id INTO v_r
--     FROM activity_roles ar
--     JOIN activities a  ON a.id = ar.activity_id AND a.entity_id = v_e
--     JOIN user_roles ur ON ur.role_id = ar.role_id AND ur.user_id = v_h
--    GROUP BY ar.role_id
--    ORDER BY (SELECT count(*) FROM user_roles u2 WHERE u2.role_id = ar.role_id),
--             ar.role_id
--    LIMIT 1;
--   IF v_r IS NULL THEN
--     RAISE EXCEPTION 'Toujours aucun role commun : la carto resterait ouverte a tous.';
--   END IF;
--   INSERT INTO entity_role_access (entity_id, role_id, created_at)
--   VALUES (v_e, v_r, now()) ON CONFLICT DO NOTHING;
--   UPDATE entities SET is_shared = true WHERE id = v_e;
--   SELECT count(*) INTO n FROM user_roles WHERE role_id = v_r;
--   RAISE NOTICE 'ouverte par le role #% (% titulaires)', v_r, n;
-- END $$;
