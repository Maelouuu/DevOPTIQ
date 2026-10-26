# Jeu de test — import depuis l'application

Le classeur de ce dossier pose **le contenu** du jeu de test par les écrans
d'import de l'app, sans ligne de commande. La **cartographie**, elle, ne peut
pas entrer par là : voir plus bas.

| Fichier | Où le déposer |
|---|---|
| `jeu_de_test.xlsx` | feuilles *Tâches* et *Outils* → **page Carte**, fenêtre d'import ; feuille *Collaborateurs* → **page Comptes** |
| `jeu_de_test_assemblage.optiqcarto` | nulle part dans l'interface aujourd'hui — voir « La carto » |

## La carto : aucun écran ne l'importe

L'app n'accepte qu'un **`.vsdx`** (éditeur → « Importer depuis Visio »). Le
paquet `.optiqcarto` a son API (`POST /cartography/api/import`, qui fonctionne)
et son code côté navigateur (`wireCartoImport` dans `static/js/activities_map.js`),
mais **le bouton a été retiré de la pop-up Gestion des entités** le 14/09/2026,
à la demande, comme nettoyage d'interface — `tests/test_75_entite_active_partagee.py`
veille à ce qu'il ne revienne pas par copier-coller.

Trois façons d'avoir la carto, donc :

- **`../sql/jeu_de_test.sql`** dans l'éditeur SQL de Neon — pose tout d'un coup,
  carto comprise, et c'est la seule voie qui écrit aussi savoirs, savoir-faire,
  aptitudes et HSC ;
- **`../plans/jeu_de_test.json`** avec `provision.py`, si on a accès à la base
  depuis un poste ;
- **la dessiner dans l'éditeur** : 3 bandes, 8 activités, 7 flèches — un quart
  d'heure, et le classeur ci-dessous fait le reste.

Remettre le bouton serait cinq lignes de gabarit, le reste est encore là. C'est
une décision d'interface, pas technique.

## Le contenu : le classeur

1. **Tâches et outils.** Page Carte → fenêtre d'import → `jeu_de_test.xlsx`.
   Les deux feuilles sont reconnues telles quelles, sans passer par l'étape IA :
   24 tâches, 7 outils, 17 compétences, et le rôle garant de chaque activité.
   Suppose que les activités existent déjà, avec les mêmes libellés.
2. **Les comptes.** Page Comptes → fenêtre d'import → le **même** classeur,
   feuille *Collaborateurs*. Deux comptes, mot de passe `testtest`.
3. **Le deuxième rôle d'Inès.** Gestion RH → Inès Lemoine → cocher
   **Opérateur Assemblage** en plus de **Technicien Méthodes**.

L'étape 3 est manuelle : la feuille des comptes ne porte qu'un rôle par ligne,
et un même e-mail ne peut pas y figurer deux fois.

> La feuille *Collaborateurs* est **volontairement écartée** si on la dépose sur
> la page Carte : créer un compte engage toute l'instance, ça ne se fait que
> depuis la page Comptes. L'écran le dit et renvoie au bon endroit.

## Ce que ce chemin ne pose pas

Savoirs, savoir-faire, aptitudes et HSC : aucun écran ne les importe. Ils sont
dans `../data/jeu_de_test_contenu.json`, et seuls le script SQL et le plan de
provisionnement les écrivent.

## Régénérer les fichiers

Les deux dérivent de `../carto/jeu_de_test_assemblage.json` et
`../data/jeu_de_test_contenu.json`. Les colonnes du classeur reprennent les
synonymes reconnus par `Code/routes/import_hub.py` — c'est ce qui permet la
lecture directe, sans étape IA.
