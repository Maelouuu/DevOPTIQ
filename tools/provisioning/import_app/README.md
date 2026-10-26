# Jeu de test — import depuis l'application

Les deux fichiers de ce dossier posent le jeu de test **sans ligne de commande
et sans toucher à la base** : tout passe par les écrans d'import de l'app. C'est
la même entité que `plans/jeu_de_test.json`, par l'autre chemin.

| Fichier | Où le déposer |
|---|---|
| `jeu_de_test_assemblage.optiqcarto` | **Gestion des entités → Importer une carto** |
| `jeu_de_test.xlsx` | feuilles *Tâches* et *Outils* → **page Carte**, fenêtre d'import ; feuille *Collaborateurs* → **page Comptes** |

## Marche à suivre

1. **La carto.** Gestion des entités → Importer une carto →
   `jeu_de_test_assemblage.optiqcarto`. Crée l'entité « Jeu de test — Atelier
   Assemblage », ses 8 activités, ses 3 rôles et ses 7 connexions, et la rend
   active. Les rôles sortent des bandes, comme après un import Visio.
2. **Le contenu.** Page Carte → fenêtre d'import → `jeu_de_test.xlsx`. Les
   feuilles *Tâches* et *Outils* sont reconnues telles quelles : 24 tâches,
   7 outils, 17 compétences, et le rôle garant de chaque activité.
3. **Les comptes.** Page Comptes → fenêtre d'import → le **même** classeur,
   feuille *Collaborateurs*. Deux comptes, mot de passe `testtest`.
4. **Le deuxième rôle d'Inès.** Gestion RH → Inès Lemoine → cocher
   **Opérateur Assemblage** en plus de **Technicien Méthodes**.

L'étape 4 est manuelle parce que la feuille des comptes ne porte qu'un rôle par
ligne, et qu'un même e-mail ne peut pas apparaître deux fois. C'est aussi la
seule chose qui distingue ce chemin du plan de provisionnement.

> La feuille *Collaborateurs* est **volontairement écartée** si on la dépose sur
> la page Carte : créer un compte engage toute l'instance, ça ne se fait que
> depuis la page Comptes. L'écran le dit et renvoie au bon endroit.

## Ce que ce chemin ne pose pas

Savoirs, savoir-faire, aptitudes et HSC : aucun écran ne les importe
aujourd'hui. Ils sont dans `../data/jeu_de_test_contenu.json` et seul le plan de
provisionnement les écrit. Par ici, il faut les saisir à la main sur les fiches
activité — ou ne pas les poser du tout, le reste suffit à la démonstration.

## Régénérer les fichiers

Les deux fichiers dérivent de `../carto/jeu_de_test_assemblage.json` et
`../data/jeu_de_test_contenu.json` : modifier la source, puis regénérer. Le
paquet `.optiqcarto` est le JSON de carto enveloppé dans
`{format, version, entity, diagram}` — l'import accepte aussi le diagramme brut,
mais sans l'enveloppe l'entité n'a ni nom ni description.
