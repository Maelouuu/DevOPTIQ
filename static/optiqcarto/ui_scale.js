'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — une seule taille, mise à l'échelle
   ══════════════════════════════════════════════════
   La barre d'outils était dessinée en pixels fixes. Sur un portable elle
   DÉBORDAIT : « Panneau » et « Propriétés » sont ancrés aux deux bouts, le
   contenu du milieu passait dessous (mesuré : 68 px de chevauchement de chaque
   côté à 1180 px de large). Sur un 27 pouces, à l'inverse, elle occupait une
   bande étroite au milieu d'un grand vide.

   On pose donc UN facteur, `--ui-k`, proportionnel à la largeur de la fenêtre,
   et la barre s'y conforme (voir style.css). Le rendu garde la même proportion
   d'un écran à l'autre au lieu d'une taille absolue.

   Pourquoi `zoom` et pas `transform: scale()` : un `transform` crée un bloc
   conteneur pour les descendants `position: fixed` — les menus déroulants de la
   barre se retrouveraient ancrés au mauvais repère. `zoom` met à l'échelle la
   mise en page elle-même, et les menus restent sous leur bouton. */

(function () {
  // Largeur à laquelle la barre est à sa taille nominale (k = 1). En deçà elle
  // rétrécit, au-delà elle grandit — dans des bornes raisonnables.
  const LARGEUR_DE_REFERENCE = 1400;
  const K_MIN = 0.70;   // ~1000 px : la barre tient encore sans chevaucher
  const K_MAX = 1.25;   // au-delà, une barre d'outils devient encombrante

  function appliquer() {
    const k = Math.min(K_MAX, Math.max(K_MIN, window.innerWidth / LARGEUR_DE_REFERENCE));
    document.documentElement.style.setProperty('--ui-k', k.toFixed(3));
  }

  appliquer();
  window.addEventListener('resize', appliquer, { passive: true });
})();
