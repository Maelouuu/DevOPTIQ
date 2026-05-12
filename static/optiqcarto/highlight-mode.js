'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — Mode "mise en évidence des activités hachurées"
   ──────────────────────────────────────────────────
   Toggle qui passe toute la carto (bandes, formes, connexions) en gris
   à l'exception des activités hachurées (subtype 'extco') qui gardent
   leur couleur. Permet de repérer visuellement les activités externes
   à l'entreprise sur une carto dense.

   Dépend de l'état global `state` et de la fonction `render` (éditeur).
   Stocke les couleurs d'origine sur `_origColor` / `_origStrokeColor`
   pour pouvoir restaurer fidèlement à la désactivation.
   ══════════════════════════════════════════════════ */

let highlightExtcoActive = false;

const DIM_SHAPE_FILL   = '#cbd5e1'; // gris bleuté clair (bg shapes)
const DIM_SHAPE_STROKE = '#94a3b8'; // gris bleuté foncé (halo)
const DIM_BAND         = '#cbd5e1';
const DIM_CONN         = '#94a3b8';

function isHighlightExtcoActive() {
  return highlightExtcoActive;
}

function toggleHighlightExtco() {
  highlightExtcoActive = !highlightExtcoActive;
  if (highlightExtcoActive) _dimEverythingExceptExtco();
  else                      _restoreOriginalColors();
  _syncButtonState();
  if (typeof render === 'function') render();
}

function _dimEverythingExceptExtco() {
  if (typeof state === 'undefined') return;
  for (const s of state.shapes || []) {
    if (s.subtype === 'extco') continue; // garde la couleur des hachurées
    if (s._origColor === undefined) {
      s._origColor       = s.color;
      s._origStrokeColor = s.strokeColor;
    }
    s.color       = DIM_SHAPE_FILL;
    s.strokeColor = DIM_SHAPE_STROKE;
  }
  for (const b of state.bands || []) {
    if (b._origColor === undefined) b._origColor = b.color;
    b.color = DIM_BAND;
  }
  for (const c of state.connections || []) {
    if (c._origColor === undefined) c._origColor = c.color;
    c.color = DIM_CONN;
  }
}

function _restoreOriginalColors() {
  if (typeof state === 'undefined') return;
  for (const s of state.shapes || []) {
    if (s._origColor !== undefined) {
      s.color       = s._origColor;
      s.strokeColor = s._origStrokeColor;
      delete s._origColor;
      delete s._origStrokeColor;
    }
  }
  for (const b of state.bands || []) {
    if (b._origColor !== undefined) { b.color = b._origColor; delete b._origColor; }
  }
  for (const c of state.connections || []) {
    if (c._origColor !== undefined) { c.color = c._origColor; delete c._origColor; }
  }
}

function _syncButtonState() {
  const btn = document.getElementById('btn-connect-tool');
  if (btn) btn.classList.toggle('active', highlightExtcoActive);
}

// Réinitialise la sauvegarde de couleurs sur les éléments. À appeler après
// un load/import qui remplace le state — les `_origColor` éventuellement
// présents dans le JSON sauvegardé n'ont plus de sens.
function resetHighlightExtco() {
  highlightExtcoActive = false;
  if (typeof state !== 'undefined') {
    for (const s of state.shapes || [])     { delete s._origColor; delete s._origStrokeColor; }
    for (const b of state.bands || [])      { delete b._origColor; }
    for (const c of state.connections || []) { delete c._origColor; }
  }
  _syncButtonState();
}
