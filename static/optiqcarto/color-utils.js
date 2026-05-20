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

function hexToHSL(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (d !== 0) {
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return [h, s, l];
}

function hslToRgb(h, s, l) {
  if (s === 0) { const v = Math.round(l * 255); return [v, v, v]; }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const hue2rgb = (t) => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1/6) return p + (q - p) * 6 * t;
    if (t < 1/2) return q;
    if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
    return p;
  };
  return [
    Math.round(hue2rgb(h + 1/3) * 255),
    Math.round(hue2rgb(h) * 255),
    Math.round(hue2rgb(h - 1/3) * 255),
  ];
}

// Convertit un pastel en couleur vive de même teinte (L=0.45, S≥0.55).
// Cas quasi-gris (s < 0.1) : assombrir seulement, éviter une teinte arbitraire.
function pastelToVivid(hex) {
  const [r, g, b] = hexToRgb(hex);
  const [h, s, l] = hexToHSL(r, g, b);
  if (s < 0.1) return darkenColor(hex, 0.65);
  const [nr, ng, nb] = hslToRgb(h, Math.max(s, 0.55), 0.45);
  return '#' + [nr, ng, nb].map(c => Math.max(0, Math.min(255, c)).toString(16).padStart(2, '0')).join('');
}

// Couleur du texte sur une bande (blanc sur foncé, gris foncé sur clair)
function bandTextColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  const lum = (0.299*r + 0.587*g + 0.114*b) / 255;
  return lum > 0.55 ? '#374151' : '#ffffff';
}

// Couleur de la zone index.
// - lum ≤ 0.7 : couleur assez foncée → utiliser telle quelle
// - lum > 0.7 : pastel ou quasi-blanc → convertir en vivid via HSL
//   (l'ancien fallback gris #94a3b8 pour lum > 0.93 est supprimé :
//    il produisait du gris sur les bandes très claires comme Project #d8ffff)
function bandIndexColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  const lum = (0.299*r + 0.587*g + 0.114*b) / 255;
  if (lum <= 0.7) return hex;
  return pastelToVivid(hex);
}

// Couleur de bordure : même logique que bandIndexColor
function bandBorderColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  const lum = (0.299*r + 0.587*g + 0.114*b) / 255;
  if (lum <= 0.7) return hex;
  return pastelToVivid(hex);
}

// Teinte atténuée (55% vivid + 45% blanc) — variante "moins fidèle" d'une bande
function bandMutedColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  return '#' + [r*0.55+255*0.45, g*0.55+255*0.45, b*0.55+255*0.45]
    .map(c => Math.round(c).toString(16).padStart(2,'0')).join('');
}
