/* ════════════════════════════════════════════════════════════════════
   La page Carte comme une SCÈNE : la carto prend toute la place.

   Trois gestes, et rien d'autre : replier la liste, passer en plein écran,
   recentrer. Le reste de la page (fenêtres d'entités, d'import, d'accès,
   d'examen) vit dans activities_map.js — ce fichier ne touche qu'au cadre.

   ⚠️ On ne RECENTRE PAS la carto quand le tiroir se replie ou qu'on passe en
   plein écran. L'utilisateur vient peut-être de zoomer sur une zone précise :
   lui reprendre son cadrage pour « bien faire » lui fait perdre ce qu'il
   regardait. La zone visible s'agrandit, le point de vue ne bouge pas —
   c'est ce que fait n'importe quel outil de dessin. Recentrer reste un
   geste, et il a son bouton.
   ════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const CLE_TIROIR = 'optiq_carto_tiroir';   // replié ou non, d'une visite à l'autre
  const scene = document.getElementById('carto-scene');
  if (!scene) return;

  const L = (cle) => (window.MAP_I18N || {})[cle] || cle;

  document.body.classList.add('a-carto-scene');

  // ── Le tiroir ──────────────────────────────────────────────────────
  const btnPanneau = document.getElementById('cs-panneau');
  const languette = document.getElementById('cs-languette');

  function lire(cle) {
    try { return localStorage.getItem(cle); } catch (e) { return null; }
  }
  function ecrire(cle, val) {
    try { localStorage.setItem(cle, val); } catch (e) { /* stockage refusé */ }
  }

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
    if (memoriser) ecrire(CLE_TIROIR, replie ? '1' : '0');
  }

  function basculerTiroir() {
    poserTiroir(!scene.classList.contains('is-replie'), true);
  }

  // ── Plein écran ────────────────────────────────────────────────────
  const btnPlein = document.getElementById('cs-plein');

  function basculerPlein() {
    // ⚠️ `requestFullscreen` peut être refusé (permission, iframe) : on rend
    // une promesse qu'il faut attraper, sinon la console se remplit d'erreurs
    // non gérées sur un simple refus.
    if (document.fullscreenElement) {
      (document.exitFullscreen() || Promise.resolve()).catch(() => {});
    } else if (scene.requestFullscreen) {
      (scene.requestFullscreen() || Promise.resolve()).catch(() => {});
    }
  }

  function majPlein() {
    const dedans = document.fullscreenElement === scene;
    if (!btnPlein) return;
    const lib = L(dedans ? 'sc_quitter_plein' : 'sc_plein');
    btnPlein.title = lib;
    btnPlein.setAttribute('aria-label', lib);
    btnPlein.classList.toggle('is-on', dedans);
    const ic = btnPlein.querySelector('i');
    if (ic) ic.className = dedans ? 'fa-solid fa-compress' : 'fa-solid fa-expand';
  }

  // ── Recentrer ──────────────────────────────────────────────────────
  function recentrer() {
    const frame = document.getElementById('carto-viewer-frame');
    if (frame && frame.contentWindow) {
      try { frame.contentWindow.postMessage({ type: 'fit-view' }, '*'); } catch (e) { /* iframe pas prête */ }
    }
  }

  // ── Branchements ───────────────────────────────────────────────────
  document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-cs]');
    if (!el || !scene.contains(el)) return;
    const quoi = el.dataset.cs;
    if (quoi === 'panneau') return basculerTiroir();
    if (quoi === 'plein') return basculerPlein();
    if (quoi === 'fit') return recentrer();
  });

  document.addEventListener('fullscreenchange', () => { majPlein(); ajusterHauteur(); });

  // Raccourcis — ⚠️ jamais pendant une saisie : la recherche d'activité est à
  // deux centimètres, et « f » y servirait à écrire, pas à ouvrir l'écran.
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (t.closest('input, textarea, select, [contenteditable]'))) return;
    // Une fenêtre ouverte par-dessus a la priorité : ses propres raccourcis,
    // et Échap doit la fermer, pas sortir du plein écran.
    if (document.querySelector('.popup:not(.hidden), .modal:not(.hidden), #imh:not([hidden])')) return;
    const k = e.key.toLowerCase();
    if (k === 'f') { e.preventDefault(); basculerPlein(); }
    else if (k === 'c') { e.preventDefault(); recentrer(); }
    else if (k === 'l') { e.preventDefault(); basculerTiroir(); }
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
  majPlein();
  ajusterHauteur();

  // ⚠️ L'entrée en scène PART d'une opacité nulle : dans un onglet en
  // arrière-plan le navigateur met l'animation en pause, et la page resterait
  // blanche jusqu'au retour dessus. On ne la pose que si l'onglet est visible.
  if (document.visibilityState === 'visible') {
    scene.classList.add('cs-entre');
    setTimeout(() => scene.classList.remove('cs-entre'), 900);
  }
})();
