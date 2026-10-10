/* ════════════════════════════════════════════════════════════════════
   La page Carte : une rangée de tuiles, le dessin, la liste.

   Trois gestes, et rien d'autre : replier les réglages, recadrer le dessin,
   replier la liste. Le reste de la page (fenêtres d'entités, d'import,
   d'accès, d'examen) vit dans activities_map.js — ce fichier ne touche
   qu'au cadre.

   ⚠️ Le PLEIN ÉCRAN a été retiré : agrandir la fenêtre ne sert presque
   jamais sur cette page, alors que RECADRER — remettre le dessin au milieu
   de la zone d'affichage — est le geste qu'on fait sans arrêt.

   ⚠️ Et on RECADRE après avoir replié la liste. Elle POUSSE le dessin (elle
   ne le recouvre pas) : replier change donc la largeur de la zone
   d'affichage, et sans recadrage on gagnerait 300 px de vide à droite au
   lieu d'un dessin plus grand — or c'est exactement pour ça qu'on replie.
   ════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const CLE_TIROIR  = 'optiq_carto_tiroir';    // replié ou non, d'une visite à l'autre
  const CLE_REGLAGE = 'optiq_carto_reglages';  // idem pour les réglages
  const DUREE_REPLI = 380;                     // la transition du tiroir, en ms
  const scene = document.getElementById('carto-scene');
  if (!scene) return;

  const L = (cle) => (window.MAP_I18N || {})[cle] || cle;

  document.body.classList.add('a-carto-scene');

  function lire(cle) {
    try { return localStorage.getItem(cle); } catch (e) { return null; }
  }
  function ecrire(cle, val) {
    try { localStorage.setItem(cle, val); } catch (e) { /* stockage refusé */ }
  }

  // ── Recadrer ───────────────────────────────────────────────────────
  function recentrer() {
    const frame = document.getElementById('carto-viewer-frame');
    if (frame && frame.contentWindow) {
      try { frame.contentWindow.postMessage({ type: 'fit-view' }, '*'); } catch (e) { /* iframe pas prête */ }
    }
  }

  // ── Le tiroir ──────────────────────────────────────────────────────
  const btnPanneau = document.getElementById('cs-panneau');
  const languette = document.getElementById('cs-languette');
  let _recadre = null;

  function poserTiroir(replie, memoriser) {
    scene.classList.toggle('is-replie', replie);
    if (btnPanneau) {
      const lib = L(replie ? 'sc_panneau_ouvrir' : 'sc_panneau_fermer');
      btnPanneau.title = lib;
      btnPanneau.setAttribute('aria-label', lib);
      btnPanneau.setAttribute('aria-expanded', String(!replie));
      btnPanneau.classList.toggle('is-on', replie);
    }
    if (languette) languette.setAttribute('aria-hidden', String(!replie));
    if (memoriser) {
      ecrire(CLE_TIROIR, replie ? '1' : '0');
      // ⚠️ APRÈS la transition : plus tôt, le viewer se cadrerait sur une
      // largeur qui n'est pas encore la bonne.
      clearTimeout(_recadre);
      _recadre = setTimeout(recentrer, DUREE_REPLI);
    }
  }

  // ── Les réglages ───────────────────────────────────────────────────
  // « Les boutons prennent trop de place » : les quatre tuiles de réglage se
  // rangent derrière un chevron. ⚠️ Le repli n'emporte QUE les réglages :
  // ouvrir l'éditeur et recadrer restent toujours à un clic.
  const actions = document.getElementById('cs-actions');
  const btnPlier = document.getElementById('cs-plier');

  function poserReglages(plie, memoriser) {
    if (!actions) return;
    actions.classList.toggle('is-plie', plie);
    if (btnPlier) {
      const lib = L(plie ? 'sc_actions_deplier' : 'sc_actions_plier');
      btnPlier.title = lib;
      btnPlier.setAttribute('aria-label', lib);
      btnPlier.setAttribute('aria-expanded', String(!plie));
      const ic = btnPlier.querySelector('i');
      // Le chevron montre où va le contenu : les tuiles sont à GAUCHE de la
      // poignée, elles se replient donc vers la gauche.
      if (ic) ic.className = plie ? 'fa-solid fa-chevron-left' : 'fa-solid fa-chevron-right';
    }
    if (memoriser) ecrire(CLE_REGLAGE, plie ? '1' : '0');
  }

  // ── Branchements ───────────────────────────────────────────────────
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-cs]');
    if (!el || !scene.contains(el)) return;
    const quoi = el.dataset.cs;
    if (quoi === 'panneau') return poserTiroir(!scene.classList.contains('is-replie'), true);
    if (quoi === 'actions') return poserReglages(!actions.classList.contains('is-plie'), true);
    if (quoi === 'fit') return recentrer();
  });

  // Raccourcis — ⚠️ jamais pendant une saisie : la recherche d'activité est à
  // deux centimètres, et « c » y servirait à écrire, pas à recadrer.
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (t.closest('input, textarea, select, [contenteditable]'))) return;
    // Une fenêtre ouverte par-dessus a la priorité : ses propres raccourcis,
    // et Échap doit la fermer.
    if (document.querySelector('.popup:not(.hidden), .modal:not(.hidden), #imh:not([hidden])')) return;
    const k = e.key.toLowerCase();
    if (k === 'c') { e.preventDefault(); recentrer(); }
    else if (k === 'l') { e.preventDefault(); poserTiroir(!scene.classList.contains('is-replie'), true); }
    else if (k === 'b') { e.preventDefault(); poserReglages(!actions.classList.contains('is-plie'), true); }
  });

  // ── La hauteur de la scène se MESURE ───────────────────────────────
  // Ce qui la surmonte (barre de navigation et sa marge) n'a pas de hauteur
  // fixe : une constante devinée remettait la page à défiler de 28 px.
  function ajusterHauteur() {
    const haut = Math.max(0, Math.round(scene.getBoundingClientRect().top));
    scene.style.setProperty('--cs-top', haut + 'px');
  }

  let _t = null;
  window.addEventListener('resize', () => {
    clearTimeout(_t);
    _t = setTimeout(ajusterHauteur, 80);
  });

  // ── État initial ───────────────────────────────────────────────────
  poserTiroir(lire(CLE_TIROIR) === '1', false);
  poserReglages(lire(CLE_REGLAGE) === '1', false);
  ajusterHauteur();

  // ⚠️ L'entrée en scène PART d'une opacité nulle : dans un onglet en
  // arrière-plan le navigateur met l'animation en pause, et la rangée
  // resterait invisible jusqu'au retour dessus.
  if (document.visibilityState === 'visible') {
    scene.classList.add('cs-entre');
    setTimeout(() => scene.classList.remove('cs-entre'), 900);
  }
})();
