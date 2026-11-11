-- ===========================================================================
--  JEU DE TEST — suppression
--
--  Retire l'entité, ses activités et tout ce qui y pend, plus les deux
--  comptes de test. À lancer avant de rejouer jeu_de_test.sql.
--
--  ⚠️ L'ordre compte. Les cascades de DevOPTIQ vivent dans l'ORM
--  (SQLAlchemy), pas dans le schéma : en base, presque toutes les clés
--  étrangères sont en NO ACTION. Supprimer l'entité en premier échoue.
-- ===========================================================================

BEGIN;

-- Ce qui pend aux tâches, puis les tâches
DELETE FROM task_tools WHERE task_id IN (
  SELECT t.id FROM tasks t WHERE t.activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage'));
DELETE FROM tasks WHERE activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage');

-- Ce qui pend aux activités
DELETE FROM activity_roles WHERE activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage');
DELETE FROM competencies WHERE activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage');
DELETE FROM savoirs WHERE activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage');
DELETE FROM savoir_faires WHERE activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage');
DELETE FROM aptitudes WHERE activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage');
DELETE FROM softskills WHERE activity_id IN (SELECT a.id FROM activities a JOIN entities e ON e.id = a.entity_id
                 WHERE e.name = 'Jeu de test — Atelier Assemblage');
DELETE FROM links WHERE entity_id IN (SELECT id FROM entities WHERE name = 'Jeu de test — Atelier Assemblage');

-- Les activités
DELETE FROM activities WHERE entity_id IN (SELECT id FROM entities WHERE name = 'Jeu de test — Atelier Assemblage');

-- Les comptes de test (user_roles NE part PAS en cascade)
DELETE FROM user_roles WHERE user_id IN (
  SELECT id FROM users WHERE email IN ('ines.lemoine@example.com', 'remi.delaunay@example.com'));
DELETE FROM users WHERE email IN ('ines.lemoine@example.com', 'remi.delaunay@example.com');

-- Rôles, outils, puis l'entité
DELETE FROM roles WHERE entity_id IN (SELECT id FROM entities WHERE name = 'Jeu de test — Atelier Assemblage');
DELETE FROM tools WHERE entity_id IN (SELECT id FROM entities WHERE name = 'Jeu de test — Atelier Assemblage');
DELETE FROM entities WHERE name = 'Jeu de test — Atelier Assemblage';

COMMIT;
