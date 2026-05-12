'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — Utilitaires couleur (aucune dépendance)
   ══════════════════════════════════════════════════ */

function hexToRgb(hex) {
  return [parseInt(hex.slice(1,3),16), parseInt(hex.slice(3,5),16), parseInt(hex.slice(5,7),16)];
}

function bandPastel(hex) {
  const [r,g,b] = hexToRgb(hex);
  return '#' + [r*0.25+255*0.75, g*0.25+255*0.75, b*0.25+255*0.75]
    .map(c => Math.round(c).toString(16).padStart(2,'0')).join('');
}

function bandBgColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  return '#' + [r*0.07+255*0.93, g*0.07+255*0.93, b*0.07+255*0.93]
    .map(c => Math.round(c).toString(16).padStart(2,'0')).join('');
}

function darkenColor(hex, factor = 0.72) {
  const [r,g,b] = hexToRgb(hex);
  return '#' + [r*factor, g*factor, b*factor]
    .map(c => Math.round(c).toString(16).padStart(2,'0')).join('');
}

// Teinte atténuée (55% vivid + 45% blanc) — variante "moins fidèle" d'une bande
function bandMutedColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  return '#' + [r*0.55+255*0.45, g*0.55+255*0.45, b*0.55+255*0.45]
    .map(c => Math.round(c).toString(16).padStart(2,'0')).join('');
}
