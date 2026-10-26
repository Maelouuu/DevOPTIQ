# Jeu de test — par l'éditeur SQL

Deux scripts à coller dans l'éditeur SQL de Neon, sur la base de l'instance.
C'est la **voie complète** : elle pose tout, y compris ce qu'aucun écran
d'import ne sait écrire (savoirs, savoir-faire, aptitudes, HSC).

| Fichier | Rôle |
|---|---|
| `jeu_de_test.sql` | pose l'entité, la carto, les rôles, les 8 activités renseignées et les 2 comptes |
| `jeu_de_test_suppression.sql` | retire tout, pour rejouer |

## Marche à suivre

1. Neon → projet `afdec-db` → **SQL Editor** → sélectionner la base de
   l'instance visée (`devoptiq_sandbox` pour staging). **Vérifier le nom de la
   base** : les trois vivent sur le même endpoint.
2. Coller `jeu_de_test.sql` et exécuter. Tout est dans une transaction : en cas
   d'erreur, rien n'est écrit.
3. Dans l'app, se connecter en propriétaire et basculer sur l'entité
   « Jeu de test — Atelier Assemblage ».

Le script **s'arrête de lui-même** si le compte propriétaire n'existe pas, ou
si l'entité est déjà là. Pour rejouer : `jeu_de_test_suppression.sql` d'abord.

Des requêtes de contrôle sont en commentaire à la fin de `jeu_de_test.sql`.

## Ce que ça pose

3 rôles, 8 activités de la demande client à la clôture du lot, 24 tâches,
7 outils, 17 compétences, 16 savoirs, 14 savoir-faire, 10 aptitudes, 14 HSC,
7 connexions. **Inès Lemoine tient deux rôles** et garantit 6 activités ;
Rémi Delaunay en tient un. Mot de passe des deux comptes : `testtest`.

## Deux pièges du schéma

- **Les cascades n'existent que dans l'ORM.** En base, presque toutes les clés
  étrangères sont en `NO ACTION` : supprimer l'entité en premier échoue sur
  `activities_entity_id_fkey`. D'où l'ordre explicite du script de suppression.
- **`user_roles` ne part pas avec le compte.** Il faut le vider avant de
  supprimer les utilisateurs.

## Régénérer

Les deux fichiers dérivent de `../carto/jeu_de_test_assemblage.json` et
`../data/jeu_de_test_contenu.json` — les mêmes sources que le plan de
provisionnement et que les fichiers d'import. Modifier la source, puis
regénérer ; la carto part telle quelle dans `entities.optiqcarto_data`.

Validé sur PostgreSQL 16 : pose, relecture par l'application, suppression,
puis nouvelle pose sur base nettoyée.
