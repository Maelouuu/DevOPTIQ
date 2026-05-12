'use strict';

/* ══════════════════════════════════════════════════
   Activities Map — Mode "mise en évidence des activités externes/hachurées"
   ──────────────────────────────────────────────────
   Toggle qui passe l'ensemble du SVG (bandes, formes, connexions) en gris,
   à l'exception des activités dont l'id figure dans `window.EXTCO_ACTIVITY_IDS`
   (rempli côté serveur depuis l'attribut subtype = 'extco' | 'external' du
   JSON OptiqCarto sauvegardé sur l'entité active).

   Module indépendant : il dépend uniquement de la variable globale
   `window.EXTCO_ACTIVITY_IDS` et de la classe CSS `.carto-activity`
   posée par activities_map.js sur chaque shape interactive.
   ══════════════════════════════════════════════════ */

let _extcoMapActive = false;

function isExtcoMapHighlightActive() {
  return _extcoMapActive;
}

function applyExtcoMapHighlight(svgRoot) {
  if (!svgRoot) return;
  const extcoIds = new Set(
    (window.EXTCO_ACTIVITY_IDS || []).map(v => String(v))
  );
  // Tag les activités à conserver en couleur
  svgRoot.querySelectorAll('.carto-activity').forEach(el => {
    const aid = String(el.dataset.activityId || '');
    if (extcoIds.has(aid)) el.classList.add('extco-keep');
  });
  svgRoot.classList.add('extco-highlight-active');
}

function clearExtcoMapHighlight(svgRoot) {
  if (!svgRoot) return;
  svgRoot.classList.remove('extco-highlight-active');
  svgRoot.querySelectorAll('.extco-keep').forEach(el => el.classList.remove('extco-keep'));
}

// Toggle principal. Retourne le nouvel état actif.
function toggleExtcoMapHighlight(svgRoot) {
  _extcoMapActive = !_extcoMapActive;
  if (_extcoMapActive) applyExtcoMapHighlight(svgRoot);
  else                 clearExtcoMapHighlight(svgRoot);
  return _extcoMapActive;
}

// Nombre d'activités qui seraient mises en évidence (pour le badge UI).
function extcoMapCount() {
  return (window.EXTCO_ACTIVITY_IDS || []).length;
}
