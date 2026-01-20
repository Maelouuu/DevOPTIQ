# Refonte de la page Liste des Activités

## Vue d'ensemble

La page "Liste des activités" a été entièrement refaite avec un design moderne et épuré, en s'inspirant du style utilisé dans les autres pages de l'application (gestion compte, gestion RH, etc.).

## Changements principaux

### 1. Design moderne
- **Nouveau CSS** : `activities_list.css` avec des couleurs douces et un style cohérent
- **Palette de couleurs** :
  - Primaire : Dégradé violet (#667eea → #764ba2)
  - Accents : Bleu (#3498db), Vert (#27ae60), Rouge (#e74c3c)
  - Fond : Gris clair (#f4f6f8)
- **Typographie** : Segoe UI, tailles cohérentes et lisibles (16px de base)
- **Espacement** : Marges et paddings généreux pour une meilleure lisibilité

### 2. Système d'onglets
Au lieu d'une énorme section déroulante, chaque activité est organisée en **6 onglets** :

1. **Vue d'ensemble** : Informations générales, contraintes, temps estimé
2. **Connexions** : Connexions entrantes et sortantes avec performances
3. **Tâches** : Tâches associées à l'activité
4. **Compétences** : Compétences requises
5. **Savoirs & SF** : Savoirs, savoir-faire et aptitudes
6. **HSC** : Habiletés socio-cognitives

### 3. Navigation améliorée
- **Boutons de contrôle global** : "Tout déplier" / "Tout replier"
- **Transitions fluides** : Animations CSS pour une expérience agréable
- **Deep linking** : Support des URLs avec ancres pour ouvrir directement une activité/onglet
  - Exemple : `#activity-123-connections` ouvre l'activité 123 sur l'onglet Connexions

### 4. Composants visuels améliorés
- **Badges colorés** : Pour les types de données (déclenchante, nourrissante)
- **Tableaux stylisés** : Headers avec dégradé, lignes survolables
- **Icônes Font Awesome** : Partout pour une meilleure compréhension visuelle
- **Messages vides** : Affichage élégant quand il n'y a pas de données

## Fichiers créés/modifiés

### Nouveaux fichiers
1. `/static/activities_list.css` - CSS complet pour la refonte
2. `/static/js/activities_tabs.js` - Gestion des onglets et interactions
3. `/Code/routes/templates/activity_card_new.html` - Nouveau template avec onglets

### Fichiers modifiés
1. `/Code/routes/templates/display_list.html` - Mise à jour pour utiliser le nouveau design

## Compatibilité

- ✅ Tous les templates inclus existants fonctionnent (`tasks_partial.html`, `activity_competencies.html`, etc.)
- ✅ Tous les scripts JS existants sont conservés
- ✅ Responsive design pour mobile/tablette
- ✅ Compatible avec tous les navigateurs modernes

## Utilisation

### Pour revenir à l'ancien design
Il suffit de modifier `display_list.html` et remplacer :
```html
{% include "activity_card_new.html" %}
```
par :
```html
{% include "activity_card.html" %}
```

### Pour ouvrir une activité spécifique via URL
```
/activities#activity-123-overview    → Ouvre l'activité 123, onglet Vue d'ensemble
/activities#activity-456-connections → Ouvre l'activité 456, onglet Connexions
```

### API JavaScript publique
```javascript
// Ouvrir/fermer une activité
toggleActivity(activityId);

// Ouvrir un onglet spécifique
openActivityTab(activityId, tabName);

// Déplier/replier toutes les activités
toggleAllActivities(true);  // Déplier tout
toggleAllActivities(false); // Replier tout
```

## Prochaines améliorations possibles

1. **Filtre de recherche** : Rechercher dans les activités par nom, description, etc.
2. **Tri personnalisé** : Trier par nom, date, complexité, etc.
3. **Vue compacte/étendue** : Toggle pour basculer entre vue détaillée et vue liste
4. **Favoris** : Marquer des activités comme favorites
5. **Export** : Exporter la liste en PDF ou Excel

## Notes techniques

- Le CSS utilise Flexbox et Grid pour une mise en page moderne
- Les transitions CSS sont utilisées pour fluidifier l'expérience
- Le JavaScript est vanilla (pas de framework) pour la légèreté
- Les couleurs respectent les standards d'accessibilité WCAG AA
