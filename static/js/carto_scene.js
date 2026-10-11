/* ════════════════════════════════════════════════════════════════════
   La page Carte : une rangée de tuiles, le dessin, la liste.

   Trois gestes, et rien d'autre : replier les réglages, recadrer le dessin,
   replier la liste. Le reste de la page (fenêtres d'entités, d'import,
   d'accès, d'examen) vit dans activities_map.js — ce fichier ne touche
   qu'au cadre.

   ⚠️ Le PLEIN ÉCRAN a été retiré : agrandir la fenêtre ne sert presque
   jamais sur cette page, alors que RECADRER — remettre le dessin au milieu
   de la zone d'affichage — est le geste qu'on fait sans arrêt.

   ⚠️ Le zoom s'aligne sur la LARGEUR de la zone d'affichage, jamais sur sa
   hauteur. Une carto est large et se lit de gauche à droite : on lui donne
   toute la largeur, et ce qui dépasse en hauteur se parcourt au glisser.
   Conséquence voulue — le zoom est plus PETIT liste ouverte (zone étroite)
   et plus grand une fois la liste repliée, donc replier fait vraiment
   grandir le dessin. Un cadrage borné par la hauteur, lui, ne bougeait pas
   d'un pixel quand on repliait.
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
    if (!frame || !frame.contentWindow) return;
    try {
      frame.contentWindow.postMessage({ type: 'fit-view', cadrage: 'largeur' }, '*');
    } catch (e) { /* iframe pas prête */ }
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
  const pliable = document.getElementById('cs-pliable');

  // ⚠️ On ne peut pas animer une largeur vers `auto` : on mesure la largeur
  // naturelle des tuiles et on la pose en variable. Tant qu'elle n'est pas
  // mesurée, le repli reste instantané — jamais cassé, juste sans glissé.
  function mesurerPliable() {
    if (!actions || !pliable) return;
    const dedans = pliable.querySelector('.cs-pliable-in');
    if (!dedans) return;
    // La largeur naturelle n'existe que DÉPLIÉ. On retire d'abord `a-mesure`
    // pour que rien ne s'anime pendant la mesure : tout se joue dans la même
    // image, donc rien ne clignote.
    const plie = actions.classList.contains('is-plie');
    actions.classList.remove('a-mesure');
    if (plie) actions.classList.remove('is-plie');
    const w = Math.ceil(dedans.getBoundingClientRect().width);
    if (plie) actions.classList.add('is-plie');
    if (w > 0) {
      actions.style.setProperty('--cs-pliable-w', w + 'px');
      actions.classList.add('a-mesure');
    }
  }

  function poserReglages(plie, memoriser) {
    if (!actions) return;
    actions.classList.toggle('is-plie', plie);
    if (btnPlier) {
      const lib = L(plie ? 'sc_actions_deplier' : 'sc_actions_plier');
      btnPlier.title = lib;
      btnPlier.setAttribute('aria-label', lib);
      btnPlier.setAttribute('aria-expanded', String(!plie));
      // ⚠️ Le chevron TOURNE (règle CSS sur `.is-plie`) au lieu de changer de
      // classe : remplacer une classe ne s'anime pas.
    }
    if (memoriser) ecrire(CLE_REGLAGE, plie ? '1' : '0');
  }

  // ── Branchements ───────────────────────────────────────────────────
  // ⚠️ Le viewer se cadre LUI-MÊME quand il a fini de charger, et il le fait
  // à sa façon (« tout tient »). Sans ce rattrapage, le zoom par défaut
  // n'était pas celui de la page : mesuré 0,1361 à l'ouverture contre 0,2106
  // après un clic sur « recadrer ».
  window.addEventListener('message', (e) => {
    if (e && e.data && e.data.type === 'carto-state-ready') recentrer();
  });

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
    _t = setTimeout(() => { ajusterHauteur(); mesurerPliable(); }, 80);
  });

  // ── État initial ───────────────────────────────────────────────────
  poserTiroir(lire(CLE_TIROIR) === '1', false);
  // ⚠️ Repliés PAR DÉFAUT — une visite sans choix mémorisé s'ouvre sur la
  // carto, pas sur ses réglages. Seul un '0' explicite les déplie.
  const memoReglages = lire(CLE_REGLAGE);
  poserReglages(memoReglages === null ? true : memoReglages === '1', false);
  ajusterHauteur();
  mesurerPliable();
  // ⚠️ Une police qui arrive après coup change la largeur des libellés : la
  // mesure d'avant ne vaudrait plus rien.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(mesurerPliable).catch(() => {});
  }

  // ⚠️ L'entrée en scène PART d'une opacité nulle : dans un onglet en
  // arrière-plan le navigateur met l'animation en pause, et la rangée
  // resterait invisible jusqu'au retour dessus.
  if (document.visibilityState === 'visible') {
    scene.classList.add('cs-entre');
    setTimeout(() => scene.classList.remove('cs-entre'), 900);
  }
})();
