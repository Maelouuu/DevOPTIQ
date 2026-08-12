# Petit Agenda 🌿

Agenda-carnet pensé pour une utilisatrice unique : pages Aujourd'hui / Semaine / Mois / Notes,
gardes d'infirmière en 12h (jour et nuit), anniversaires récurrents, rappels, photo par mois.

C'est une **PWA** (Progressive Web App) : 100 % statique, aucune base de données, aucun serveur.
Toutes les données restent dans le téléphone (`localStorage`), l'app fonctionne hors-ligne
grâce au service worker.

## Structure

```
petit-agenda/
├── index.html            # coquille de l'app + symboles SVG
├── css/app.css           # tout le style (fonds qui tournent par page)
├── js/app.js             # état, rendus, interactions, illustrations des 12 mois
├── sw.js                 # service worker (cache hors-ligne)
├── manifest.webmanifest  # manifeste PWA (icône, plein écran)
├── fonts/                # Baloo 2, Nunito, Caveat (woff2, servis en local)
└── img/                  # icônes de l'app (180/192/512)
```

## Mettre en ligne (une seule fois)

L'app est un simple dossier statique — n'importe quel hébergeur statique gratuit convient :

**Option la plus simple — Netlify Drop :**
1. Va sur https://app.netlify.com/drop (compte gratuit).
2. Glisse-dépose le dossier `petit-agenda/` entier.
3. Tu obtiens une URL du type `https://xxxx.netlify.app` — c'est tout.
   (Tu peux renommer le sous-domaine dans les réglages du site, ex. `petit-agenda-lea`.)

**Autres options :** Vercel (drag & drop aussi), GitHub Pages (repo public),
ou n'importe quel serveur qui sert des fichiers statiques en HTTPS.
⚠️ HTTPS obligatoire : le service worker (mode hors-ligne) ne s'active qu'en HTTPS.

## Installer sur l'iPhone (2 minutes)

1. Ouvrir l'URL dans **Safari** (pas Chrome).
2. Toucher le bouton **Partager** (le carré avec la flèche).
3. Choisir **« Sur l'écran d'accueil »** puis **Ajouter**.
4. L'icône « Petit Agenda » apparaît : l'app s'ouvre en plein écran,
   sans barre d'adresse, et fonctionne sans connexion.

## Mises à jour

Re-déployer les fichiers au même endroit suffit. Au lancement suivant, le service worker
récupère la nouvelle version en arrière-plan (elle est visible au lancement d'après).
Penser à incrémenter `CACHE` dans `sw.js` (`petit-agenda-v2`, `v3`…) à chaque déploiement.

## Données

- Tout est dans `localStorage` sous la clé `petit-agenda-v1` (une app installée sur
  l'écran d'accueil garde son stockage, il n'est pas soumis au nettoyage 7 jours de Safari).
- Export / import de sauvegarde JSON : icône ⚙ en haut de la page Notes.
- Le prénom affiché sur l'écran d'accueil se règle au même endroit.
- La photo de chaque mois se change via le petit appareil photo sur la page Mois
  (les 12 illustrations de l'étang servent de visuel par défaut, une par saison).
