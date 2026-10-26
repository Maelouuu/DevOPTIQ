-- ===========================================================================
--  JEU DE TEST — Atelier Assemblage
--
--  À coller tel quel dans l'éditeur SQL de Neon, sur la base de l'instance.
--  Tout est dans UNE transaction : en cas d'erreur, rien n'est écrit.
--
--  Pose : 1 entité, 3 rôles, 8 activités renseignées (24 tâches, 7 outils,
--  compétences, savoirs, savoir-faire, aptitudes, HSC), 7 connexions,
--  2 collaborateurs dont un sur DEUX rôles.
--
--  Le compte propriétaire doit déjà exister : le script s'arrête sinon.
--  Rejouer le script sur une base où l'entité existe déjà le fait échouer
--  volontairement — supprimer l'entité d'abord (voir la fin du fichier).
-- ===========================================================================

BEGIN;

-- ── Garde-fous ─────────────────────────────────────────────────────────────
DO $garde$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM users WHERE lower(email) = 'mael.pierre.girardin@icloud.com') THEN
    RAISE EXCEPTION 'Compte propriétaire introuvable : mael.pierre.girardin@icloud.com';
  END IF;
  IF EXISTS (SELECT 1 FROM entities WHERE name = 'Jeu de test — Atelier Assemblage') THEN
    RAISE EXCEPTION 'L''entité « Jeu de test — Atelier Assemblage » existe déjà sur cette base';
  END IF;
END
$garde$;

-- ── Entité (la carto est stockée telle quelle dans optiqcarto_data) ────────
CREATE TEMP TABLE _e (id integer) ON COMMIT DROP;
WITH ins AS (
  INSERT INTO entities (name, description, owner_id, optiqcarto_data, is_active)
  SELECT 'Jeu de test — Atelier Assemblage', 'Entité de démonstration : chaîne d''assemblage complète, de la demande client à la clôture du lot. Données fictives, utilisables librement.', u.id,
         $carto${"bandWidth": 2400, "bands": [{"color": "#e2efd9", "fontSize": 22, "height": 180, "id": 1, "label": "Technicien Méthodes"}, {"color": "#deebf7", "fontSize": 22, "height": 180, "id": 2, "label": "Opérateur Assemblage"}, {"color": "#fff2cc", "fontSize": 22, "height": 180, "id": 3, "label": "Responsable Qualité"}], "collapsedPileIds": [], "connections": [{"color": "#7e891d", "fromId": 101, "fromPortDir": "right", "fromPortT": 0.5, "id": 150, "label": "Cahier des charges", "routing": "orthogonal", "style": "solid", "toId": 102, "toPortDir": "left", "toPortT": 0.5}, {"color": "#7e891d", "fromId": 102, "fromPortDir": "right", "fromPortT": 0.5, "id": 151, "label": "", "routing": "orthogonal", "style": "solid", "toId": 103, "toPortDir": "left", "toPortT": 0.5}, {"color": "#7e891d", "fromId": 103, "fromPortDir": "right", "fromPortT": 0.5, "id": 152, "label": "Gamme + outillages", "routing": "orthogonal", "style": "solid", "toId": 104, "toPortDir": "left", "toPortT": 0.5}, {"color": "#7e891d", "fromId": 104, "fromPortDir": "right", "fromPortT": 0.5, "id": 153, "label": "", "routing": "orthogonal", "style": "solid", "toId": 105, "toPortDir": "left", "toPortT": 0.5}, {"color": "#7e891d", "fromId": 105, "fromPortDir": "right", "fromPortT": 0.5, "id": 154, "label": "", "routing": "orthogonal", "style": "solid", "toId": 106, "toPortDir": "left", "toPortT": 0.5}, {"color": "#7e891d", "fromId": 106, "fromPortDir": "right", "fromPortT": 0.5, "id": 155, "label": "Dossier de contrôle", "routing": "orthogonal", "style": "solid", "toId": 107, "toPortDir": "left", "toPortT": 0.5}, {"color": "#7e891d", "fromId": 107, "fromPortDir": "right", "fromPortT": 0.5, "id": 156, "label": "", "routing": "orthogonal", "style": "solid", "toId": 108, "toPortDir": "left", "toPortT": 0.5}], "defaultRouting": "orthogonal", "groups": [], "nextId": 200, "shapes": [{"color": "#22c55e", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 101, "label": "Analyser le besoin client", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 60, "y": -155}, {"color": "#22c55e", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 102, "label": "Rédiger la gamme de montage", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 340, "y": -155}, {"color": "#22c55e", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 103, "label": "Définir les outillages", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 620, "y": -155}, {"color": "#3b82f6", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 104, "label": "Préparer le poste de travail", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 900, "y": 25}, {"color": "#3b82f6", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 105, "label": "Assembler le sous-ensemble", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 1180, "y": 25}, {"color": "#3b82f6", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 106, "label": "Contrôler visuellement la pièce", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 1460, "y": 25}, {"color": "#f59e0b", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 107, "label": "Valider le dossier de production", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 1740, "y": 205}, {"color": "#f59e0b", "colorVariant": 0, "fontSize": 15, "h": 90, "id": 108, "label": "Clôturer le lot", "strokeColor": "", "subtype": "normal", "textColor": "#ffffff", "type": "process", "validationBadge": false, "validationColor": "#4DB868", "w": 210, "x": 2020, "y": 205}], "showBands": true, "showLegend": false}$carto$,
         false
  FROM users u WHERE lower(u.email) = 'mael.pierre.girardin@icloud.com'
  RETURNING id
)
INSERT INTO _e SELECT id FROM ins;

-- ── Rôles (les bandes de la carto) ─────────────────────────────────────────
CREATE TEMP TABLE _r (nom text PRIMARY KEY, id integer) ON COMMIT DROP;
WITH src(nom) AS (VALUES
       ('Technicien Méthodes'),
       ('Opérateur Assemblage'),
       ('Responsable Qualité')
), ins AS (
  INSERT INTO roles (entity_id, name) SELECT (SELECT id FROM _e), nom FROM src
  RETURNING id, name
)
INSERT INTO _r SELECT name, id FROM ins;

-- ── Outils ─────────────────────────────────────────────────────────────────
CREATE TEMP TABLE _o (nom text PRIMARY KEY, id integer) ON COMMIT DROP;
WITH src(nom, descr) AS (VALUES
       ('ERP SAP', 'Saisie des ordres de fabrication et des mouvements de stock.'),
       ('Logiciel GPAO', 'Ordonnancement et suivi d''avancement des ordres de fabrication.'),
       ('Plan 3D (CAO)', 'Consultation des plans, nomenclatures et vues éclatées.'),
       ('Gabarit de montage', 'Gabarit de positionnement des composants sur le poste.'),
       ('Visseuse dynamométrique', 'Vissage au couple contrôlé, avec remontée des valeurs.'),
       ('Banc de contrôle', 'Contrôle d''étanchéité et de continuité électrique.'),
       ('Tablette atelier', 'Accès aux gammes et saisie des contrôles directement au poste.')
), ins AS (
  INSERT INTO tools (entity_id, name, description)
  SELECT (SELECT id FROM _e), nom, descr FROM src RETURNING id, name
)
INSERT INTO _o SELECT name, id FROM ins;

-- ── Activités ──────────────────────────────────────────────────────────────
CREATE TEMP TABLE _a (nom text PRIMARY KEY, id integer) ON COMMIT DROP;
WITH src(shape_id, nom, descr, duree, delai) AS (VALUES
       ('101', 'Analyser le besoin client', 'Recueillir et qualifier la demande client, vérifier la faisabilité technique et formaliser les exigences d''assemblage.', 90, 240),
       ('102', 'Rédiger la gamme de montage', 'Décomposer l''assemblage en opérations élémentaires ordonnancées, chiffrées en temps et associées à leurs moyens.', 180, 480),
       ('103', 'Définir les outillages', 'Choisir, spécifier et faire approvisionner les outillages et gabarits nécessaires à la gamme de montage.', 120, 2400),
       ('104', 'Préparer le poste de travail', 'Mettre le poste en configuration : composants, outillages, documents et contrôles de sécurité avant lancement de série.', 30, 0),
       ('105', 'Assembler le sous-ensemble', 'Réaliser l''assemblage conformément à la gamme, dans le respect des couples de serrage et des temps alloués.', 45, 0),
       ('106', 'Contrôler visuellement la pièce', 'Vérifier la conformité du sous-ensemble assemblé et isoler les pièces non conformes avant transfert.', 20, 0),
       ('107', 'Valider le dossier de production', 'Vérifier la complétude et la cohérence du dossier avant libération du lot.', 60, 120),
       ('108', 'Clôturer le lot', 'Prononcer la libération du lot et archiver le dossier de production.', 30, 60)
), ins AS (
  INSERT INTO activities (entity_id, shape_id, name, description, is_result,
                          shape_subtype, duration_minutes, delay_minutes)
  SELECT (SELECT id FROM _e), shape_id, nom, descr, false, 'normal', duree, delai
  FROM src RETURNING id, name
)
INSERT INTO _a SELECT name, id FROM ins;

-- ── Rôle garant de chaque activité (déduit de sa bande) ────────────────────
INSERT INTO activity_roles (activity_id, role_id, status)
SELECT a.id, r.id, 'Garant' FROM (VALUES
       ('Analyser le besoin client', 'Technicien Méthodes'),
       ('Rédiger la gamme de montage', 'Technicien Méthodes'),
       ('Définir les outillages', 'Technicien Méthodes'),
       ('Préparer le poste de travail', 'Opérateur Assemblage'),
       ('Assembler le sous-ensemble', 'Opérateur Assemblage'),
       ('Contrôler visuellement la pièce', 'Opérateur Assemblage'),
       ('Valider le dossier de production', 'Responsable Qualité'),
       ('Clôturer le lot', 'Responsable Qualité')
  ) AS v(activite, role)
JOIN _a a ON a.nom = v.activite
JOIN _r r ON r.nom = v.role;

-- ── Connexions entre activités ─────────────────────────────────────────────
INSERT INTO links (entity_id, source_activity_id, target_activity_id, type, description)
SELECT (SELECT id FROM _e), s.id, t.id, 'flux', v.libelle FROM (VALUES
       ('Analyser le besoin client', 'Rédiger la gamme de montage', 'Cahier des charges'),
       ('Rédiger la gamme de montage', 'Définir les outillages', NULL),
       ('Définir les outillages', 'Préparer le poste de travail', 'Gamme + outillages'),
       ('Préparer le poste de travail', 'Assembler le sous-ensemble', NULL),
       ('Assembler le sous-ensemble', 'Contrôler visuellement la pièce', NULL),
       ('Contrôler visuellement la pièce', 'Valider le dossier de production', 'Dossier de contrôle'),
       ('Valider le dossier de production', 'Clôturer le lot', NULL)
  ) AS v(src, dst, libelle)
JOIN _a s ON s.nom = v.src
JOIN _a t ON t.nom = v.dst;

-- ── Tâches ─────────────────────────────────────────────────────────────────
CREATE TEMP TABLE _t (activite text, nom text, id integer) ON COMMIT DROP;
WITH src(activite, nom, descr, rang, duree) AS (VALUES
       ('Analyser le besoin client', 'Réceptionner la demande client', 'Enregistrer la demande et vérifier la présence des pièces jointes.', 1, 15),
       ('Analyser le besoin client', 'Qualifier les exigences techniques', 'Confronter la demande aux capacités réelles de l''atelier.', 2, 45),
       ('Analyser le besoin client', 'Formaliser le cahier des charges', 'Rédiger la synthèse des exigences, validée avec le client.', 3, 30),
       ('Rédiger la gamme de montage', 'Décomposer l''assemblage en opérations', 'Établir la séquence opératoire à partir du plan.', 1, 60),
       ('Rédiger la gamme de montage', 'Chiffrer les temps opératoires', 'Estimer chaque opération et consolider le temps gamme.', 2, 45),
       ('Rédiger la gamme de montage', 'Rédiger les instructions de poste', 'Produire la fiche illustrée remise à l''opérateur.', 3, 60),
       ('Rédiger la gamme de montage', 'Faire valider la gamme', 'Soumettre la gamme à la qualité avant diffusion.', 4, 15),
       ('Définir les outillages', 'Identifier les besoins en outillage', 'Déduire de la gamme les moyens manquants.', 1, 30),
       ('Définir les outillages', 'Spécifier les gabarits', 'Rédiger le cahier des charges des gabarits à réaliser.', 2, 60),
       ('Définir les outillages', 'Lancer l''approvisionnement', 'Créer la demande d''achat et suivre le délai fournisseur.', 3, 30),
       ('Préparer le poste de travail', 'Vérifier la présence des composants', 'Contrôler le kit par rapport à la nomenclature.', 1, 10),
       ('Préparer le poste de travail', 'Installer les outillages', 'Monter le gabarit et régler la visseuse au couple requis.', 2, 15),
       ('Préparer le poste de travail', 'Contrôler la sécurité du poste', 'Vérifier protections, éclairage et dégagements.', 3, 5),
       ('Assembler le sous-ensemble', 'Positionner les composants', 'Placer les pièces dans le gabarit selon la gamme.', 1, 10),
       ('Assembler le sous-ensemble', 'Réaliser les opérations de vissage', 'Serrer au couple dans l''ordre prescrit par la gamme.', 2, 20),
       ('Assembler le sous-ensemble', 'Raccorder le faisceau', 'Connecter et verrouiller les connecteurs.', 3, 10),
       ('Assembler le sous-ensemble', 'Déclarer l''avancement', 'Saisir la quantité produite et les aléas rencontrés.', 4, 5),
       ('Contrôler visuellement la pièce', 'Contrôler l''aspect', 'Vérifier l''absence de rayures, marquages et déformations.', 1, 5),
       ('Contrôler visuellement la pièce', 'Vérifier les points critiques', 'Contrôler les points listés dans le plan de surveillance.', 2, 10),
       ('Contrôler visuellement la pièce', 'Enregistrer le résultat', 'Saisir le contrôle et isoler les non-conformités détectées.', 3, 5),
       ('Valider le dossier de production', 'Vérifier la traçabilité', 'Contrôler la présence de tous les enregistrements du lot.', 1, 30),
       ('Valider le dossier de production', 'Statuer sur les non-conformités', 'Décider retouche, dérogation ou rebut.', 2, 30),
       ('Clôturer le lot', 'Prononcer la libération', 'Valider le lot et déclencher l''expédition.', 1, 15),
       ('Clôturer le lot', 'Archiver le dossier', 'Classer les enregistrements selon la durée de rétention.', 2, 15)
), ins AS (
  INSERT INTO tasks (activity_id, name, description, "order", duration_minutes, delay_minutes)
  SELECT a.id, src.nom, src.descr, src.rang, src.duree, 0
  FROM src JOIN _a a ON a.nom = src.activite
  RETURNING id, name, activity_id
)
INSERT INTO _t SELECT a.nom, ins.name, ins.id FROM ins JOIN _a a ON a.id = ins.activity_id;

-- ── Outils de chaque tâche ─────────────────────────────────────────────────
INSERT INTO task_tools (task_id, tool_id)
SELECT t.id, o.id FROM (VALUES
       ('Analyser le besoin client', 'Réceptionner la demande client', 'ERP SAP'),
       ('Analyser le besoin client', 'Qualifier les exigences techniques', 'Plan 3D (CAO)'),
       ('Analyser le besoin client', 'Formaliser le cahier des charges', 'ERP SAP'),
       ('Analyser le besoin client', 'Formaliser le cahier des charges', 'Plan 3D (CAO)'),
       ('Rédiger la gamme de montage', 'Décomposer l''assemblage en opérations', 'Plan 3D (CAO)'),
       ('Rédiger la gamme de montage', 'Chiffrer les temps opératoires', 'Logiciel GPAO'),
       ('Rédiger la gamme de montage', 'Rédiger les instructions de poste', 'Logiciel GPAO'),
       ('Rédiger la gamme de montage', 'Rédiger les instructions de poste', 'Plan 3D (CAO)'),
       ('Rédiger la gamme de montage', 'Faire valider la gamme', 'ERP SAP'),
       ('Définir les outillages', 'Identifier les besoins en outillage', 'Logiciel GPAO'),
       ('Définir les outillages', 'Spécifier les gabarits', 'Plan 3D (CAO)'),
       ('Définir les outillages', 'Lancer l''approvisionnement', 'ERP SAP'),
       ('Préparer le poste de travail', 'Vérifier la présence des composants', 'Tablette atelier'),
       ('Préparer le poste de travail', 'Vérifier la présence des composants', 'ERP SAP'),
       ('Préparer le poste de travail', 'Installer les outillages', 'Gabarit de montage'),
       ('Préparer le poste de travail', 'Installer les outillages', 'Visseuse dynamométrique'),
       ('Préparer le poste de travail', 'Contrôler la sécurité du poste', 'Tablette atelier'),
       ('Assembler le sous-ensemble', 'Positionner les composants', 'Gabarit de montage'),
       ('Assembler le sous-ensemble', 'Positionner les composants', 'Tablette atelier'),
       ('Assembler le sous-ensemble', 'Réaliser les opérations de vissage', 'Visseuse dynamométrique'),
       ('Assembler le sous-ensemble', 'Raccorder le faisceau', 'Gabarit de montage'),
       ('Assembler le sous-ensemble', 'Déclarer l''avancement', 'ERP SAP'),
       ('Assembler le sous-ensemble', 'Déclarer l''avancement', 'Tablette atelier'),
       ('Contrôler visuellement la pièce', 'Contrôler l''aspect', 'Tablette atelier'),
       ('Contrôler visuellement la pièce', 'Vérifier les points critiques', 'Banc de contrôle'),
       ('Contrôler visuellement la pièce', 'Enregistrer le résultat', 'Tablette atelier'),
       ('Contrôler visuellement la pièce', 'Enregistrer le résultat', 'ERP SAP'),
       ('Valider le dossier de production', 'Vérifier la traçabilité', 'ERP SAP'),
       ('Valider le dossier de production', 'Statuer sur les non-conformités', 'ERP SAP'),
       ('Valider le dossier de production', 'Statuer sur les non-conformités', 'Banc de contrôle'),
       ('Clôturer le lot', 'Prononcer la libération', 'ERP SAP'),
       ('Clôturer le lot', 'Archiver le dossier', 'ERP SAP')
  ) AS v(activite, tache, outil)
JOIN _t t ON t.activite = v.activite AND t.nom = v.tache
JOIN _o o ON o.nom = v.outil;

-- ── Compétences ─────────────────────────────────────────────────────────────
INSERT INTO competencies (activity_id, description)
SELECT a.id, v.descr FROM (VALUES
       ('Analyser le besoin client', 'Analyser une demande client et en extraire des exigences mesurables'),
       ('Analyser le besoin client', 'Évaluer la faisabilité d''un assemblage au regard des moyens de l''atelier'),
       ('Rédiger la gamme de montage', 'Décomposer un assemblage en opérations élémentaires ordonnancées'),
       ('Rédiger la gamme de montage', 'Chiffrer un temps opératoire à partir d''un standard'),
       ('Rédiger la gamme de montage', 'Rédiger une instruction de poste compréhensible sans formation préalable'),
       ('Définir les outillages', 'Spécifier un outillage de montage à partir d''une gamme'),
       ('Définir les outillages', 'Arbitrer entre outillage dédié et moyen standard selon le volume'),
       ('Préparer le poste de travail', 'Mettre un poste d''assemblage en configuration de série'),
       ('Préparer le poste de travail', 'Vérifier la conformité d''un kit de composants'),
       ('Assembler le sous-ensemble', 'Réaliser un assemblage mécanique conforme à une gamme'),
       ('Assembler le sous-ensemble', 'Appliquer un couple de serrage et en vérifier la validité'),
       ('Assembler le sous-ensemble', 'Déclarer un avancement de production dans l''ERP'),
       ('Contrôler visuellement la pièce', 'Réaliser un contrôle visuel sur la base d''un plan de surveillance'),
       ('Contrôler visuellement la pièce', 'Identifier et isoler une non-conformité'),
       ('Valider le dossier de production', 'Vérifier la complétude d''un dossier de production'),
       ('Valider le dossier de production', 'Statuer sur le devenir d''une pièce non conforme'),
       ('Clôturer le lot', 'Prononcer la libération d''un lot de production')
  ) AS v(activite, descr)
JOIN _a a ON a.nom = v.activite;

-- ── Savoirs ─────────────────────────────────────────────────────────────
INSERT INTO savoirs (activity_id, description)
SELECT a.id, v.descr FROM (VALUES
       ('Analyser le besoin client', 'Normes d''assemblage mécanique applicables à l''atelier'),
       ('Analyser le besoin client', 'Structure et contenu d''un cahier des charges fonctionnel'),
       ('Rédiger la gamme de montage', 'Méthodes de chronométrage et temps standards'),
       ('Rédiger la gamme de montage', 'Règles de rédaction des instructions de poste'),
       ('Rédiger la gamme de montage', 'Nomenclature produit et codification des composants'),
       ('Définir les outillages', 'Catalogue des outillages standards de l''atelier'),
       ('Définir les outillages', 'Règles de cotation applicables aux gabarits'),
       ('Préparer le poste de travail', 'Nomenclature des kits et codes composants'),
       ('Préparer le poste de travail', 'Consignes de sécurité au poste d''assemblage'),
       ('Assembler le sous-ensemble', 'Couples de serrage par type de fixation'),
       ('Assembler le sous-ensemble', 'Lecture d''une gamme de montage illustrée'),
       ('Assembler le sous-ensemble', 'Règles de raccordement des connecteurs'),
       ('Contrôler visuellement la pièce', 'Critères d''acceptation visuels de l''atelier'),
       ('Contrôler visuellement la pièce', 'Procédure de traitement des non-conformités'),
       ('Valider le dossier de production', 'Exigences de traçabilité applicables au client'),
       ('Clôturer le lot', 'Règles d''archivage et durées de rétention')
  ) AS v(activite, descr)
JOIN _a a ON a.nom = v.activite;

-- ── Savoir-faire ─────────────────────────────────────────────────────────────
INSERT INTO savoir_faires (activity_id, description)
SELECT a.id, v.descr FROM (VALUES
       ('Analyser le besoin client', 'Conduire un entretien de recueil de besoin'),
       ('Analyser le besoin client', 'Rédiger une exigence technique vérifiable'),
       ('Rédiger la gamme de montage', 'Construire une séquence opératoire à partir d''un plan 3D'),
       ('Rédiger la gamme de montage', 'Illustrer une instruction avec des vues éclatées exploitables'),
       ('Définir les outillages', 'Rédiger une spécification d''outillage exploitable par un fournisseur'),
       ('Définir les outillages', 'Vérifier la conformité d''un gabarit à réception'),
       ('Préparer le poste de travail', 'Régler une visseuse dynamométrique au couple de la gamme'),
       ('Préparer le poste de travail', 'Monter et caler un gabarit de montage'),
       ('Assembler le sous-ensemble', 'Enchaîner les opérations dans le temps de cycle'),
       ('Assembler le sous-ensemble', 'Détecter un serrage non conforme au ressenti'),
       ('Contrôler visuellement la pièce', 'Utiliser un banc de contrôle d''étanchéité'),
       ('Contrôler visuellement la pièce', 'Renseigner une fiche de non-conformité exploitable'),
       ('Valider le dossier de production', 'Instruire une demande de dérogation'),
       ('Clôturer le lot', 'Clôturer un ordre de fabrication dans l''ERP')
  ) AS v(activite, descr)
JOIN _a a ON a.nom = v.activite;

-- ── Aptitudes ─────────────────────────────────────────────────────────────
INSERT INTO aptitudes (activity_id, description)
SELECT a.id, v.descr FROM (VALUES
       ('Analyser le besoin client', 'Rigueur dans la formalisation écrite'),
       ('Rédiger la gamme de montage', 'Capacité à se mettre à la place de l''opérateur'),
       ('Définir les outillages', 'Vision anticipée des contraintes de délai'),
       ('Préparer le poste de travail', 'Attention portée aux détails'),
       ('Assembler le sous-ensemble', 'Dextérité manuelle'),
       ('Assembler le sous-ensemble', 'Endurance posturale'),
       ('Contrôler visuellement la pièce', 'Acuité visuelle'),
       ('Contrôler visuellement la pièce', 'Honnêteté dans la déclaration des écarts'),
       ('Valider le dossier de production', 'Fermeté dans la décision'),
       ('Clôturer le lot', 'Méthode dans le classement')
  ) AS v(activite, descr)
JOIN _a a ON a.nom = v.activite;

-- ── HSC (soft skills) ──────────────────────────────────────────────────────
INSERT INTO softskills (activity_id, habilete, niveau, justification)
SELECT a.id, v.habilete, v.niveau, v.justif FROM (VALUES
       ('Analyser le besoin client', 'Écoute active', '3 (Maîtrise)', 'Le besoin réel est rarement celui qui est formulé en premier.'),
       ('Analyser le besoin client', 'Esprit de synthèse', '2 (Acquisition)', 'La demande arrive dispersée entre mails, plans et appels.'),
       ('Rédiger la gamme de montage', 'Pédagogie', '3 (Maîtrise)', 'L''instruction doit être lisible par un intérimaire dès le premier jour.'),
       ('Rédiger la gamme de montage', 'Précision', '4 (Excellence)', 'Une opération oubliée dans la gamme devient un défaut série.'),
       ('Définir les outillages', 'Anticipation', '3 (Maîtrise)', 'Un gabarit se fabrique en six semaines, la série n''attend pas.'),
       ('Définir les outillages', 'Négociation', '2 (Acquisition)', 'Les arbitrages budgétaires se jouent avec les achats.'),
       ('Préparer le poste de travail', 'Rigueur', '3 (Maîtrise)', 'Un composant manquant découvert en cours de série arrête la ligne.'),
       ('Préparer le poste de travail', 'Autonomie', '2 (Acquisition)', 'La préparation se fait sans encadrement en début de poste.'),
       ('Assembler le sous-ensemble', 'Concentration', '3 (Maîtrise)', 'Le geste est répétitif, la vigilance doit rester constante.'),
       ('Assembler le sous-ensemble', 'Gestion du rythme', '2 (Acquisition)', 'Le temps de cycle est contraint par la cadence de la ligne.'),
       ('Contrôler visuellement la pièce', 'Sens de l''observation', '4 (Excellence)', 'Le défaut échappe à qui regarde sans chercher.'),
       ('Contrôler visuellement la pièce', 'Intégrité', '4 (Excellence)', 'Déclarer un défaut coûte du temps : il faut le déclarer quand même.'),
       ('Valider le dossier de production', 'Impartialité', '4 (Excellence)', 'La décision qualité ne se négocie pas avec la pression délai.'),
       ('Clôturer le lot', 'Sens des responsabilités', '4 (Excellence)', 'La signature de libération engage l''entreprise.')
  ) AS v(activite, habilete, niveau, justif)
JOIN _a a ON a.nom = v.activite;

-- ── Collaborateurs ─────────────────────────────────────────────────────────
--    mot de passe : testtest
CREATE TEMP TABLE _u (email text PRIMARY KEY, id integer) ON COMMIT DROP;
WITH src(prenom, nom, email, age, mdp) AS (VALUES
       ('Inès', 'Lemoine', 'ines.lemoine@example.com', 34, 'scrypt:32768:8:1$FkHz9cHE7EiqOxhg$1aaf7b95a86097aad6ccf4e5beed7e68cd8a4e7d4b24b08db90c65e291e00aaf5ca92680580f070b96ec22b4ca4342e382be8be96dd6e4da2be5e37d92eedee2'),
       ('Rémi', 'Delaunay', 'remi.delaunay@example.com', 45, 'scrypt:32768:8:1$FkHz9cHE7EiqOxhg$1aaf7b95a86097aad6ccf4e5beed7e68cd8a4e7d4b24b08db90c65e291e00aaf5ca92680580f070b96ec22b4ca4342e382be8be96dd6e4da2be5e37d92eedee2')
), ins AS (
  INSERT INTO users (entity_id, first_name, last_name, email, age, password, status)
  SELECT (SELECT id FROM _e), prenom, nom, email, age, mdp, 'user' FROM src
  RETURNING id, email
)
INSERT INTO _u SELECT email, id FROM ins;

-- ── Rôles tenus par chaque collaborateur ───────────────────────────────────
--    Inès Lemoine en tient DEUX : c'est le point de la démonstration.
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id FROM (VALUES
       ('ines.lemoine@example.com', 'Technicien Méthodes'),
       ('ines.lemoine@example.com', 'Opérateur Assemblage'),
       ('remi.delaunay@example.com', 'Responsable Qualité')
  ) AS v(email, role)
JOIN _u u ON u.email = v.email
JOIN _r r ON r.nom = v.role;

COMMIT;

-- ===========================================================================
--  Contrôle (à lancer après le COMMIT)
-- ===========================================================================
-- SELECT a.name AS activite, r.name AS garant,
--        (SELECT count(*) FROM tasks t WHERE t.activity_id = a.id)         AS taches,
--        (SELECT count(*) FROM competencies c WHERE c.activity_id = a.id)  AS competences,
--        (SELECT count(*) FROM softskills s WHERE s.activity_id = a.id)    AS hsc
-- FROM activities a
-- JOIN entities e ON e.id = a.entity_id AND e.name = 'Jeu de test — Atelier Assemblage'
-- LEFT JOIN activity_roles ar ON ar.activity_id = a.id
-- LEFT JOIN roles r ON r.id = ar.role_id
-- ORDER BY a.shape_id;
--
-- SELECT u.first_name, u.last_name, count(ur.role_id) AS nb_roles,
--        string_agg(r.name, ', ') AS roles
-- FROM users u JOIN user_roles ur ON ur.user_id = u.id JOIN roles r ON r.id = ur.role_id
-- WHERE u.email IN ('ines.lemoine@example.com', 'remi.delaunay@example.com')
-- GROUP BY u.id, u.first_name, u.last_name;

-- ===========================================================================
--  Pour tout retirer : jeu_de_test_suppression.sql, dans le meme dossier.
--  Les cascades n'existent que dans l'ORM de l'application, PAS en base :
--  une suppression en SQL doit nommer chaque table, dans l'ordre.
-- ===========================================================================
