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

// Couleur du texte sur une bande (blanc sur foncé, gris foncé sur clair)
function bandTextColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  const lum = (0.299*r + 0.587*g + 0.114*b) / 255;
  return lum > 0.55 ? '#374151' : '#ffffff';
}

// Couleur de la zone index.
// - lum ≤ 0.7  : couleur assez foncée → utiliser telle quelle
// - lum > 0.93 : quasi-blanc → gris ardoise (fallback lisible)
// - entre les deux : pastel intentionnel (ex: #9dc3e6 bleu pâle, #fdd2cc saumon)
//   → assombrir à 55 % pour obtenir une teinte vivid lisible
function bandIndexColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  const lum = (0.299*r + 0.587*g + 0.114*b) / 255;
  if (lum <= 0.7)  return hex;
  if (lum > 0.93)  return '#94a3b8'; // near-white → gris ardoise
  return darkenColor(hex, 0.55);      // pastel → assombrir
}

// Couleur de bordure : même logique que bandIndexColor
function bandBorderColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  const lum = (0.299*r + 0.587*g + 0.114*b) / 255;
  if (lum <= 0.7)  return hex;
  if (lum > 0.93)  return '#cbd5e1'; // near-white → gris clair
  return darkenColor(hex, 0.55);
}

// Teinte atténuée (55% vivid + 45% blanc) — variante "moins fidèle" d'une bande
function bandMutedColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  return '#' + [r*0.55+255*0.45, g*0.55+255*0.45, b*0.55+255*0.45]
    .map(c => Math.round(c).toString(16).padStart(2,'0')).join('');
}
