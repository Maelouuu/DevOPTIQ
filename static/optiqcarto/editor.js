'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — Éditeur SVG
   ══════════════════════════════════════════════════ */

const _API = (typeof window !== 'undefined' && window.OPTIQCARTO_API_BASE) || '';

/* ══════════════════════════════════════════════════
   COLOR UTILITIES
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
function getBandForY(midY) {
  let y = -200;
  for (const band of state.bands) {
    if (midY >= y && midY < y + band.height) return band;
    y += band.height;
  }
  return null;
}
// Teinte atténuée (55% vivid + 45% blanc) — variante "moins fidèle" d'une bande
function bandMutedColor(hex) {
  const [r,g,b] = hexToRgb(hex);
  return '#' + [r*0.55+255*0.45, g*0.55+255*0.45, b*0.55+255*0.45]
    .map(c => Math.round(c).toString(16).padStart(2,'0')).join('');
}

function updateShapeColor(s) {
  if (s.type === 'decision') { s.color = '#9ca3af'; return; }
  const band = getBandForY(s.y + s.h / 2);
  if (!band) return;
  s.color = s.colorVariant === 1 ? bandMutedColor(band.color) : band.color;
  if (s.type === 'process' && !s.customStroke) {
    s.strokeColor = darkenColor(band.color, 0.65);
  }
  state.connections.forEach(c => { if (c.fromId === s.id) c.color = s.color; });
}

// ── Défauts par type de forme ─────────────────────
const SHAPE_DEFAULTS = {
  process:   { label: 'Activité',      color: '#22c55e', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 130, h: 90,  fontSize: 18, subtype: 'normal' },
  'start-end': { label: 'Début / Fin', color: '#3b82f6', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 130, h: 64,  fontSize: 14, subtype: 'normal' },
  special:   { label: 'Sous-activité', color: '#f59e0b', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 170, h: 76,  fontSize: 13, subtype: 'normal' },
  decision:  { label: 'Décision',      color: '#9ca3af', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 100, h: 100, fontSize: 13, subtype: 'normal' },
};

// Losange arrondi (pour la forme Décision)
function roundedDiamond(x, y, w, h, r) {
  const cx = x + w/2, cy = y + h/2;
  const len = Math.hypot(w/2, h/2);
  const rx = r * (w/2) / len;
  const ry = r * (h/2) / len;
  return `M ${cx-rx},${y+ry}` +
    ` Q ${cx},${y} ${cx+rx},${y+ry}` +
    ` L ${x+w-rx},${cy-ry}` +
    ` Q ${x+w},${cy} ${x+w-rx},${cy+ry}` +
    ` L ${cx+rx},${y+h-ry}` +
    ` Q ${cx},${y+h} ${cx-rx},${y+h-ry}` +
    ` L ${x+rx},${cy+ry}` +
    ` Q ${x},${cy} ${x+rx},${cy-ry}` +
    ` Z`;
}

const HINTS = {
  select:    'Clic = sélectionner · Glisser = déplacer · Double-clic = éditer texte · Suppr = supprimer',
  connect:   'Cliquez sur la forme source, puis sur la forme destination · Échap = annuler',
  process:   'Cliquez sur le canevas pour placer l\'activité',
  'start-end': 'Cliquez sur le canevas pour placer l\'ellipse',
  special:   'Cliquez sur le canevas pour placer la sous-activité',
};

// ── État principal ────────────────────────────────
let state = {
  shapes: [],
  connections: [],
  groups: [],   // { id, label, shapeIds:[], color:'#b3a0ff' }
  bands: [
    { id: 1, label: 'Niveau 1', color: '#22c55e', fontSize: 22, height: 180 },
    { id: 2, label: 'Niveau 2', color: '#3b82f6', fontSize: 22, height: 180 },
    { id: 3, label: 'Niveau 3', color: '#f59e0b', fontSize: 22, height: 180 },
  ],
  showBands: true,
  showLegend: false,
  nextId: 100,
  bandWidth: 1600,
  defaultRouting: 'orthogonal',
};

let history = [JSON.stringify(state)];
let histIndex = 0;

// ── Viewport ──────────────────────────────────────
// vpScale=0.5 → affichage "100%" (×200 dans la status bar)
let vpX = 0, vpY = 280, vpScale = 0.5;

// ── Interaction ───────────────────────────────────
let tool = 'select';
let selectedShapes = new Set();
let selectedConn = null;
let selectedBand = null;        // id de la bande sélectionnée
let connecting = null;          // { fromId }
let hoverShapeId = null;        // pour affichage ports
let isDragging = false;
let dragData = null;            // { shapes: [{id,ox,oy}], mx, my }
let isPanning = false;
let panStart = null;            // { sx, sy, vpX, vpY }
let isResizingBandWidth = false;
let isResizingBandHeight = false;
let bandHeightResizingId = null;
let bandHeightStartY = 0;
let bandHeightStartValue = 0;
let spaceDown = false;
let labelEditing = null;        // { shapeId }
let portDrag = null;            // { fromShapeId, fromPort:{x,y,dir} } — drag depuis un port
let connEndDrag = null;     // { connId, which:'from'|'to', curX, curY, snapShapeId, snapDir }
let markerIds = new Map();      // "color-style" → markerId
const hatchIds = new Set();     // pattern IDs déjà créés dans les defs
let leftPanelOpen = false;
let propsOpen = false;
let selectedGroup = null;
let groupHighlightId = null;
let expandedGroups = new Set();

// ── Refs DOM ──────────────────────────────────────
const canvas    = document.getElementById('canvas');
const rootGroup = document.getElementById('root-group');
const gBands    = document.getElementById('g-bands');
const gLegend   = document.getElementById('g-legend');
const gGroups   = document.getElementById('g-groups');
const gConns    = document.getElementById('g-connections');
const gShapes   = document.getElementById('g-shapes');
const gHandles  = document.getElementById('g-handles');
const gUI       = document.getElementById('g-ui');
const gOverlay  = document.getElementById('g-overlay');
const statusZoom = document.getElementById('status-zoom');
const labelEd   = document.getElementById('label-editor');

/* ══════════════════════════════════════════════════
   COORD TRANSFORMS
   ══════════════════════════════════════════════════ */

function screenToSVG(sx, sy) {
  const r = canvas.getBoundingClientRect();
  return {
    x: (sx - r.left - vpX) / vpScale,
    y: (sy - r.top  - vpY) / vpScale,
  };
}

function applyViewport() {
  rootGroup.setAttribute('transform', `translate(${vpX},${vpY}) scale(${vpScale})`);
  // vpScale 0.5 = "100%", 1.0 = "200%" (×200 pour que le défaut 50% s'affiche 100%)
  statusZoom.textContent = Math.round(vpScale * 200) + '%';
}

/* ══════════════════════════════════════════════════
   SVG HELPERS
   ══════════════════════════════════════════════════ */

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

function txt(text, attrs = {}, parent) {
  const e = el('text', attrs, parent);
  e.textContent = text;
  return e;
}

/* ══════════════════════════════════════════════════
   ARROWHEAD MARKERS (dynamiques par couleur)
   ══════════════════════════════════════════════════ */

function ensureMarker(color) {
  if (markerIds.has(color)) return markerIds.get(color);
  const id = 'ah_' + color.replace('#', '');
  const defs = canvas.querySelector('defs');
  const marker = el('marker', {
    id,
    viewBox: '0 0 12 12',
    refX: '10',
    refY: '6',
    markerWidth: '7',
    markerHeight: '7',
    orient: 'auto-start-reverse',
  }, defs);
  el('path', { d: 'M1,1 L11,6 L1,11 Z', fill: color, stroke: 'none' }, marker);
  markerIds.set(color, id);
  return id;
}

function ensureHatchPattern(vividHex) {
  const id = 'hatch_' + vividHex.replace('#', '');
  if (hatchIds.has(id)) return id;
  const pastelHex = bandPastel(vividHex);
  const defs = canvas.querySelector('defs');
  const pattern = el('pattern', {
    id, width: '10', height: '10',
    patternUnits: 'userSpaceOnUse',
    patternTransform: 'rotate(45)',
  }, defs);
  el('rect', { width: '10', height: '10', fill: pastelHex }, pattern);
  el('line', { x1: '0', y1: '0', x2: '0', y2: '10',
    stroke: vividHex, 'stroke-width': '3.5', opacity: '0.65' }, pattern);
  hatchIds.add(id);
  return id;
}

/* ══════════════════════════════════════════════════
   SHAPE GEOMETRY & PATHS
   ══════════════════════════════════════════════════ */

function getPorts(s) {
  const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
  // Les process ont une auréole de 7px → les flèches s'arrêtent au bord de l'auréole
  const h = s.type === 'process' ? 7 : 0;
  return {
    top:    { x: cx,            y: s.y - h,         dir: 'top'    },
    bottom: { x: cx,            y: s.y + s.h + h,   dir: 'bottom' },
    left:   { x: s.x - h,       y: cy,               dir: 'left'   },
    right:  { x: s.x + s.w + h, y: cy,               dir: 'right'  },
  };
}

// 10 ports répartis sur le contour — utilisés pour le snap lors du drag d'extrémité
function getDetailedPorts(s) {
  const h = s.type === 'process' ? 7 : 0;
  const { x, y, w, h: sh } = s;
  return [
    { x: x + w*0.25, y: y - h,      dir: 'top',    t: 0.25 },
    { x: x + w*0.50, y: y - h,      dir: 'top',    t: 0.50 },
    { x: x + w*0.75, y: y - h,      dir: 'top',    t: 0.75 },
    { x: x + w + h,  y: y + sh*0.33, dir: 'right',  t: 0.33 },
    { x: x + w + h,  y: y + sh*0.67, dir: 'right',  t: 0.67 },
    { x: x + w*0.75, y: y + sh + h, dir: 'bottom', t: 0.75 },
    { x: x + w*0.50, y: y + sh + h, dir: 'bottom', t: 0.50 },
    { x: x + w*0.25, y: y + sh + h, dir: 'bottom', t: 0.25 },
    { x: x - h,      y: y + sh*0.67, dir: 'left',   t: 0.67 },
    { x: x - h,      y: y + sh*0.33, dir: 'left',   t: 0.33 },
  ];
}

function getGroupBounds(grp) {
  const PAD = 22, LABEL_H = 24;
  const shapes = state.shapes.filter(s => grp.shapeIds.includes(s.id));
  if (shapes.length === 0) return null;
  const xs = shapes.flatMap(s => [s.x, s.x + s.w]);
  const ys = shapes.flatMap(s => [s.y, s.y + s.h]);
  const gx = Math.min(...xs) - PAD;
  const gy = Math.min(...ys) - PAD - LABEL_H;
  const gw = Math.max(...xs) - Math.min(...xs) + PAD * 2;
  const gh = Math.max(...ys) - Math.min(...ys) + PAD * 2 + LABEL_H;
  return { x: gx, y: gy, w: gw, h: gh };
}

function getGroupPorts(grp) {
  const b = getGroupBounds(grp);
  if (!b) return null;
  const cx = b.x + b.w / 2, cy = b.y + b.h / 2;
  return {
    top:    { x: cx,         y: b.y,         dir: 'top'    },
    bottom: { x: cx,         y: b.y + b.h,   dir: 'bottom' },
    left:   { x: b.x,         y: cy,          dir: 'left'   },
    right:  { x: b.x + b.w,  y: cy,          dir: 'right'  },
  };
}

function bestExitPort(from, to) {
  const dx = (to.x + to.w / 2) - (from.x + from.w / 2);
  const dy = (to.y + to.h / 2) - (from.y + from.h / 2);
  const p = getPorts(from);
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? p.right : p.left;
  return dy >= 0 ? p.bottom : p.top;
}

function bestEntryPort(shape, fromPort) {
  const opp = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' };
  return getPorts(shape)[opp[fromPort.dir]];
}

function hitShape(s, px, py) {
  return px >= s.x && px <= s.x + s.w && py >= s.y && py <= s.y + s.h;
}

function shapeAtPoint(px, py) {
  // Iterate reverse to hit top-most first
  for (let i = state.shapes.length - 1; i >= 0; i--) {
    if (hitShape(state.shapes[i], px, py)) return state.shapes[i];
  }
  return null;
}

function wavyPath(x, y, w, h, rx = 12, amp = 9) {
  // Rounded top, straight sides, wavy bottom
  return [
    `M ${x + rx},${y}`,
    `H ${x + w - rx}`,
    `Q ${x + w},${y} ${x + w},${y + rx}`,
    `V ${y + h}`,
    `C ${x + w * 0.85},${y + h + amp} ${x + w * 0.65},${y + h + amp} ${x + w * 0.5},${y + h}`,
    `C ${x + w * 0.35},${y + h - amp} ${x + w * 0.15},${y + h - amp} ${x},${y + h}`,
    `V ${y + rx}`,
    `Q ${x},${y} ${x + rx},${y}`,
    'Z',
  ].join(' ');
}

function cpFromPort(port, tension) {
  switch (port.dir) {
    case 'right':  return [port.x + tension, port.y];
    case 'left':   return [port.x - tension, port.y];
    case 'bottom': return [port.x, port.y + tension];
    case 'top':    return [port.x, port.y - tension];
    default:       return [port.x, port.y];
  }
}

function bezierArrow(fp, tp, tensionFactor = 1) {
  const len = Math.hypot(tp.x - fp.x, tp.y - fp.y);
  const t = Math.min(len * 0.45, 180) * tensionFactor;
  const [c1x, c1y] = cpFromPort(fp, t);
  const [c2x, c2y] = cpFromPort(tp, t);
  return `M ${fp.x},${fp.y} C ${c1x},${c1y} ${c2x},${c2y} ${tp.x},${tp.y}`;
}

// Point exact à t=0.5 sur la courbe de bézier cubique
function bezierMidpoint(fp, tp) {
  const len = Math.hypot(tp.x - fp.x, tp.y - fp.y);
  const tension = Math.min(len * 0.45, 180);
  const [c1x, c1y] = cpFromPort(fp, tension);
  const [c2x, c2y] = cpFromPort(tp, tension);
  return {
    x: 0.125*fp.x + 0.375*c1x + 0.375*c2x + 0.125*tp.x,
    y: 0.125*fp.y + 0.375*c1y + 0.375*c2y + 0.125*tp.y,
  };
}

function polylineToPath(pts, R) {
  if (pts.length < 2) return '';
  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const p = pts[i - 1], c = pts[i], n = pts[i + 1];
    const d1 = Math.hypot(c.x - p.x, c.y - p.y);
    const d2 = Math.hypot(n.x - c.x, n.y - c.y);
    const r  = Math.min(R, d1 / 2, d2 / 2);
    if (r < 0.5) { d += ` L ${c.x},${c.y}`; continue; }
    const v1x = (c.x - p.x) / d1, v1y = (c.y - p.y) / d1;
    const v2x = (n.x - c.x) / d2, v2y = (n.y - c.y) / d2;
    d += ` L ${c.x - v1x * r},${c.y - v1y * r}`;
    d += ` Q ${c.x},${c.y} ${c.x + v2x * r},${c.y + v2y * r}`;
  }
  const last = pts[pts.length - 1];
  d += ` L ${last.x},${last.y}`;
  return d;
}

// Calcule les waypoints orthogonaux (réutilisé par arrow + label fitting)
// bundleOffset : décalage perpendiculaire pour séparer les flèches parallèles du même bundle
function orthogonalPts(fp, tp, bundleOffset = 0) {
  const STEP = 38;
  const DV = { right:[1,0], left:[-1,0], bottom:[0,1], top:[0,-1] };
  const isH = d => d === 'right' || d === 'left';
  const fdir = fp.dir, tdir = tp.dir;

  // ── Ligne droite si les ports sont déjà alignés ──────────────
  // Horizontal : même Y ± 4px, deux directions horizontales opposées
  if (isH(fdir) && isH(tdir) && Math.abs(fp.y - tp.y) <= 4) {
    return [fp, tp];
  }
  // Vertical : même X ± 4px, deux directions verticales opposées
  if (!isH(fdir) && !isH(tdir) && Math.abs(fp.x - tp.x) <= 4) {
    return [fp, tp];
  }

  const fv = DV[fdir], tv = DV[tdir];
  const p1 = { x: fp.x + fv[0]*STEP, y: fp.y + fv[1]*STEP };
  const p2 = { x: tp.x + tv[0]*STEP, y: tp.y + tv[1]*STEP };
  const dx12 = p2.x - p1.x, dy12 = p2.y - p1.y;
  if (Math.abs(dx12) < 2 && Math.abs(dy12) < 2) {
    return [fp, p1, p2, tp];
  } else if (isH(fdir) && !isH(tdir)) {
    return [fp, p1, { x: p2.x, y: p1.y }, p2, tp];
  } else if (!isH(fdir) && isH(tdir)) {
    return [fp, p1, { x: p1.x, y: p2.y }, p2, tp];
  } else if (isH(fdir)) {
    // H→H : décaler le segment horizontal du milieu pour séparer les bundles parallèles
    if (Math.abs(dy12) < 2) return [fp, p1, p2, tp];
    const SAFE = 52;
    const rawMid = (p1.y + p2.y) / 2;
    const safeMid = Math.abs(rawMid - fp.y) < SAFE ? fp.y + Math.sign(dy12 || 1) * SAFE : rawMid;
    const midY = safeMid + bundleOffset;
    return [fp, p1, { x: p1.x, y: midY }, { x: p2.x, y: midY }, p2, tp];
  } else {
    // V→V : décaler le segment vertical du milieu pour séparer les bundles parallèles
    if (Math.abs(dx12) < 2) return [fp, p1, p2, tp];
    const SAFE = 52;
    const rawMid = (p1.x + p2.x) / 2;
    const safeMid = Math.abs(rawMid - fp.x) < SAFE ? fp.x + Math.sign(dx12 || 1) * SAFE : rawMid;
    const midX = safeMid + bundleOffset;
    return [fp, p1, { x: midX, y: p1.y }, { x: midX, y: p2.y }, p2, tp];
  }
}

// Flèche orthogonale (angles droits, style Visio)
function orthogonalArrow(fp, tp) {
  return polylineToPath(orthogonalPts(fp, tp), 8);
}

// ── Les lignes croisées se superposent librement (pas de bridges) ──

/* ══════════════════════════════════════════════════
   TEXT WRAP
   ══════════════════════════════════════════════════ */

function wrapText(text, maxChars, maxLines = 4) {
  if (!text) return [];
  const result = [];
  const hardLines = text.split('\n');
  for (const hard of hardLines) {
    if (result.length >= maxLines) break;
    if (hard === '') { result.push(''); continue; }
    const words = hard.split(' ');
    let cur = '';
    for (const w of words) {
      if (result.length >= maxLines) break;
      const candidate = cur ? cur + ' ' + w : w;
      if (candidate.length > maxChars && cur) { result.push(cur); cur = w; }
      else cur = candidate;
    }
    if (cur && result.length < maxLines) result.push(cur);
  }
  return result.slice(0, maxLines);
}

/* ══════════════════════════════════════════════════
   RENDER — BANDS
   ══════════════════════════════════════════════════ */

const INDEX_W_SVG = 140; // Largeur SVG de la zone index des bandes (suit le pan/zoom)

function renderBands() {
  gBands.innerHTML = '';
  gUI.innerHTML = '';

  if (!state.showBands || state.bands.length === 0) return;

  let y = -200;
  const bw = state.bandWidth;

  for (const band of state.bands) {
    const isSel = selectedBand === band.id;
    const g = el('g', {}, gBands);
    const pastel = bandPastel(band.color);
    const bgColor = bandBgColor(band.color);

    // Fond de la bande → très pâle pour faire ressortir les formes
    el('rect', { x: 0, y, width: bw, height: band.height, fill: bgColor }, g);

    // ── Zone index (gauche, vivid) ────
    el('rect', {
      x: 0, y, width: INDEX_W_SVG, height: band.height,
      fill: isSel ? darkenColor(band.color, 0.78) : band.color,
      'data-band-index': band.id,
      cursor: 'pointer',
    }, g);

    // Séparateur droit de la zone index
    el('line', {
      x1: INDEX_W_SVG, y1: y, x2: INDEX_W_SVG, y2: y + band.height,
      stroke: band.color,
      'stroke-width': '3',
      'pointer-events': 'none',
    }, g);

    // Label de la bande dans la zone index — vertical, toujours blanc sur vivid
    txt((band.label || '').toUpperCase(), {
      x: INDEX_W_SVG / 2,
      y: y + band.height / 2,
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      fill: '#ffffff',
      'font-size': Math.min(band.fontSize || 22, INDEX_W_SVG * 0.55),
      'font-family': 'Segoe UI, sans-serif',
      'font-weight': '700',
      'letter-spacing': '2',
      'pointer-events': 'none',
      transform: `rotate(-90, ${INDEX_W_SVG / 2}, ${y + band.height / 2})`,
    }, g);

    // Bordure basse → vivid (la bande colorée visible)
    el('line', {
      x1: 0, y1: y + band.height, x2: bw, y2: y + band.height,
      stroke: band.color, 'stroke-width': '3', 'pointer-events': 'none',
    }, g);

    // Poignée invisible de resize hauteur (sur/autour du trait bas)
    el('rect', {
      x: INDEX_W_SVG, y: y + band.height - 5,
      width: bw - INDEX_W_SVG, height: 10,
      fill: 'transparent',
      cursor: 'ns-resize',
      'data-type': 'band-height-resizer',
      'data-band-height-id': band.id,
    }, g);

    y += band.height;
  }

  // ── Contrôles UI (non-données carto) ──────────────────────
  const firstY = -200;
  const totalH = y - firstY;

  // Poignée de redimensionnement (droite)
  const rg = el('g', { 'data-type': 'band-resizer', cursor: 'ew-resize' }, gUI);
  el('rect', { x: bw - 8, y: firstY, width: 16, height: totalH, fill: 'rgba(59,130,246,0.05)' }, rg);
  el('line', {
    x1: bw, y1: firstY, x2: bw, y2: y,
    stroke: 'rgba(59,130,246,0.45)', 'stroke-width': '2', 'stroke-dasharray': '5,4', 'pointer-events': 'none',
  }, rg);
  const midY = firstY + totalH / 2;
  [-14, -7, 0, 7, 14].forEach(dy => {
    el('circle', { cx: bw, cy: midY + dy, r: '2.5', fill: 'rgba(59,130,246,0.55)', 'pointer-events': 'none' }, rg);
  });

  // Bouton "Ajouter une bande" (bas) — toute la largeur de la bande
  const ag = el('g', { 'data-type': 'add-band', cursor: 'pointer' }, gUI);
  el('rect', {
    x: 0, y: y + 10, width: bw, height: 36, rx: '6', ry: '6',
    fill: 'rgba(0,0,0,0.04)',
    stroke: 'rgba(0,0,0,0.18)', 'stroke-width': '1.5', 'stroke-dasharray': '6,4',
  }, ag);
  txt('＋  Ajouter une bande', {
    x: bw / 2,
    y: y + 10 + 18,
    'text-anchor': 'middle', 'dominant-baseline': 'middle',
    fill: 'rgba(0,0,0,0.35)', 'font-size': '14',
    'font-family': 'Segoe UI, sans-serif', 'font-weight': '600', 'pointer-events': 'none',
  }, ag);
}


/* ══════════════════════════════════════════════════
   RENDER — LEGEND
   ══════════════════════════════════════════════════ */

function renderLegend() {
  gLegend.innerHTML = ''; // légende SVG vide — la légende est dans le left-panel HTML
}

/* ══════════════════════════════════════════════════
   RENDER — CONNECTIONS
   ══════════════════════════════════════════════════ */

function renderConnections() {
  gConns.innerHTML = '';

  // Pré-calcul du port spread (répartition des connexions sur chaque côté)
  const OPP = { right:'left', left:'right', top:'bottom', bottom:'top' };
  // fromUsage : connexions sortantes par (shapeId-dir) — pour bundleOffset seulement
  const fromUsage = {};
  // unifiedUsage : TOUTES les connexions (entrantes + sortantes) par (shapeId-dir)
  // → garantit qu'aucun point n'est partagé entre une flèche entrante et sortante
  const unifiedUsage = {};

  function _resolveEp(eid) {
    const s = state.shapes.find(s => s.id === eid);
    if (s) return { id: s.id, x: s.x, y: s.y, w: s.w, h: s.h, _halo: s.type === 'process' ? 7 : 0, _type: s.type };
    const grp = state.groups && state.groups.find(g => g.id === eid);
    if (grp) { const b = getGroupBounds(grp); if (b) return { id: grp.id, x: b.x, y: b.y, w: b.w, h: b.h, _halo: 0, _type: 'group' }; }
    return null;
  }

  for (const c of state.connections) {
    const from = _resolveEp(c.fromId);
    const to   = _resolveEp(c.toId);
    if (!from || !to) continue;
    const dx = (to.x + to.w/2) - (from.x + from.w/2);
    const dy = (to.y + to.h/2) - (from.y + from.h/2);
    const fdir = c.fromPortDir || (Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top'));
    const tdir = c.toPortDir || OPP[fdir];
    const fk = `${c.fromId}-${fdir}`, tk = `${c.toId}-${tdir}`;
    // fromUsage : sortantes uniquement (pour bundleOffset)
    if (!fromUsage[fk]) fromUsage[fk] = [];
    fromUsage[fk].push(c.id);
    // unifiedUsage : entrantes + sortantes mélangées (pour point physique unique)
    if (!unifiedUsage[fk]) unifiedUsage[fk] = [];
    unifiedUsage[fk].push({ connId: c.id, end: 'from' });
    if (!unifiedUsage[tk]) unifiedUsage[tk] = [];
    unifiedUsage[tk].push({ connId: c.id, end: 'to' });
  }

  // spreadPort utilise unifiedUsage → un point de connexion = une seule flèche (in OU out)
  function spreadPort(ep, dir, connId, end, explicitT) {
    const h = ep._halo || 0;
    const cx = ep.x + ep.w / 2, cy = ep.y + ep.h / 2;
    // Decision diamond: always connect to the exact tip (no spread)
    if (ep._type === 'decision') {
      switch (dir) {
        case 'left':   return { x: ep.x,         y: cy,          dir: 'left'   };
        case 'right':  return { x: ep.x + ep.w,  y: cy,          dir: 'right'  };
        case 'top':    return { x: cx,            y: ep.y,        dir: 'top'    };
        case 'bottom': return { x: cx,            y: ep.y + ep.h, dir: 'bottom' };
      }
    }
    const key = `${ep.id}-${dir}`;
    const users = unifiedUsage[key] || [];
    const idx = users.findIndex(u => u.connId === connId && u.end === end);
    const n = users.length;
    // Utilise le t explicite (port choisi manuellement) sinon auto-spread
    const t = explicitT !== undefined ? explicitT : (n <= 1 ? 0.5 : (idx + 1) / (n + 1));
    switch (dir) {
      case 'left':   return { x: ep.x - h,           y: ep.y + ep.h * t, dir: 'left'   };
      case 'right':  return { x: ep.x + ep.w + h,    y: ep.y + ep.h * t, dir: 'right'  };
      case 'top':    return { x: ep.x + ep.w * t,    y: ep.y - h,        dir: 'top'    };
      case 'bottom': return { x: ep.x + ep.w * t,    y: ep.y + ep.h + h, dir: 'bottom' };
    }
  }

  for (const c of state.connections) {
    const from = _resolveEp(c.fromId);
    const to   = _resolveEp(c.toId);
    if (!from || !to) continue;

    const dx = (to.x + to.w/2) - (from.x + from.w/2);
    const dy = (to.y + to.h/2) - (from.y + from.h/2);
    const fdir = c.fromPortDir || (Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top'));
    const tdir = c.toPortDir || OPP[fdir]; // indépendant si défini explicitement

    const fp = spreadPort(from, fdir, c.id, 'from', c.fromPortT);
    const tp = spreadPort(to,   tdir, c.id, 'to',   c.toPortT);
    const routing = c.routing || 'smooth';
    // Varier la tension selon l'index dans le bundle pour séparer les courbes parallèles
    const fk2 = `${c.fromId}-${fdir}`;
    const fUsers2 = fromUsage[fk2] || [];
    const fIdx2 = fUsers2.indexOf(c.id);
    const fN2 = fUsers2.length;
    const tensionFactor = fN2 > 1 ? 0.7 + 0.6 * (fIdx2 / (fN2 - 1)) : 1;
    // Décaler le segment du milieu pour éviter la superposition des flèches parallèles
    const bundleOffset = fN2 > 1 ? (fIdx2 - (fN2 - 1) / 2) * 14 : 0;
    const orthopts = orthogonalPts(fp, tp, bundleOffset);
    const d  = routing === 'orthogonal' ? polylineToPath(orthopts, 8) : bezierArrow(fp, tp, tensionFactor);
    const isSel = selectedConn === c.id;
    const color = isSel ? '#1f7a54' : c.color;
    const mId = ensureMarker(color);

    // Zone de clic invisible (plus large)
    el('path', {
      d, fill: 'none', stroke: 'transparent', 'stroke-width': '14',
      'data-id': c.id, 'data-type': 'conn', cursor: 'pointer',
    }, gConns);

    // Chemin visible
    el('path', {
      d, fill: 'none',
      stroke: color,
      'stroke-width': isSel ? '3' : '2',
      'stroke-dasharray': c.style === 'dashed' ? '9,6' : 'none',
      'marker-end': `url(#${mId})`,
      'data-id': c.id, 'data-type': 'conn', cursor: 'pointer',
      'pointer-events': 'none',
    }, gConns);

    // Label : placé sur le segment le plus long où le texte tient en entier
    if (c.label) {
      const lw = c.label.length * 6;
      const lh = 13;
      let lx, ly, angle;
      // Utiliser les pts déjà calculés (routing orthogonal) ou les calculer pour bezier
      const labelPts = routing === 'orthogonal' ? orthopts : orthogonalPts(fp, tp, bundleOffset);
      const segments = [];
      for (let i = 0; i < labelPts.length - 1; i++) {
        const a = labelPts[i], b = labelPts[i + 1];
        const dx = b.x - a.x, dy = b.y - a.y;
        const len = Math.hypot(dx, dy);
        const isHoriz = Math.abs(dy) < Math.abs(dx);
        segments.push({ mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2, len, isHoriz });
      }
      // Sélection du meilleur segment :
      // 1. Le segment doit être assez long pour que la flèche continue 5px de chaque côté du texte
      // 2. Parmi les segments valides, préférer celui avec le moins de formes autour (moins chargé)
      // 3. En cas d'égalité de clutter, préférer le plus long
      const SEG_MARGIN = 5;
      const fitting = segments.filter(s => s.len >= lw + SEG_MARGIN * 2);
      const candidates = fitting.length > 0 ? fitting : segments;
      function clutterScore(seg) {
        const RADIUS = 50;
        return state.shapes.filter(s =>
          Math.abs(s.x + s.w/2 - seg.mx) < s.w/2 + RADIUS &&
          Math.abs(s.y + s.h/2 - seg.my) < s.h/2 + RADIUS
        ).length;
      }
      const best = candidates.reduce((a, b) => {
        const sa = clutterScore(a) * 10000 - a.len;
        const sb = clutterScore(b) * 10000 - b.len;
        return sb < sa ? b : a;
      });
      lx = best.mx; ly = best.my;
      angle = best.isHoriz ? 0 : -90;
      // Ajustement si le label chevauche une forme → on décale légèrement
      const hw = angle !== 0 ? lh / 2 : lw / 2;
      const hh = angle !== 0 ? lw / 2 : lh / 2;
      const MARGIN = 6;
      for (let attempt = 0; attempt < 6; attempt++) {
        const lleft = lx - hw - MARGIN, lright = lx + hw + MARGIN;
        const ltop  = ly - hh - MARGIN, lbot   = ly + hh + MARGIN;
        let hit = null;
        for (const s of state.shapes) {
          if (lright < s.x || lleft > s.x + s.w) continue;
          if (lbot   < s.y || ltop  > s.y + s.h) continue;
          hit = s; break;
        }
        if (!hit) break;
        // Pousser dans la direction opposée au centre de la forme qui chevauche
        const scx = hit.x + hit.w / 2, scy = hit.y + hit.h / 2;
        const pushX = lx - scx, pushY = ly - scy;
        const pushLen = Math.hypot(pushX, pushY) || 1;
        lx += (pushX / pushLen) * 20;
        ly += (pushY / pushLen) * 20;
      }
      const lg = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      lg.setAttribute('transform', `translate(${lx},${ly}) rotate(${angle})`);
      lg.setAttribute('pointer-events', 'none');
      el('rect', {
        x: -lw/2, y: -lh/2, width: lw, height: lh,
        rx: '0', fill: 'rgba(255,255,255,0.96)',
      }, lg);
      txt(c.label, {
        x: 0, y: 0,
        'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: color, 'font-size': '11', 'font-family': 'Segoe UI, sans-serif',
        'font-weight': '600',
      }, lg);
      gConns.appendChild(lg);
    }

    // Poignées d'extrémité (visibles quand la connexion est sélectionnée)
    if (isSel) {
      for (const [pt, which] of [[fp, 'from'], [tp, 'to']]) {
        el('circle', {
          cx: String(pt.x), cy: String(pt.y), r: '8',
          fill: '#1f7a54', stroke: '#ffffff', 'stroke-width': '2.5',
          cursor: 'grab',
          'data-conn-id': String(c.id), 'data-conn-end': which,
          style: 'pointer-events:all',
        }, gConns);
      }
    }
  }
}

/* ══════════════════════════════════════════════════
   RENDER — SHAPES
   ══════════════════════════════════════════════════ */

function renderShapes() {
  gShapes.innerHTML = '';

  for (const s of state.shapes) {
    const isSel   = selectedShapes.has(s.id);
    const isHover = hoverShapeId === s.id;
    const g = el('g', {
      'data-id': s.id, 'data-type': 'shape',
      class: 'shape-group',
      cursor: tool === 'connect' ? 'crosshair' : 'pointer',
    }, gShapes);

    // Shadow filter
    const filterAttr = isSel ? 'url(#f-shadow-sel)' : 'url(#f-shadow)';

    // ── Draw shape ──────────────────────────────
    let shapeEl;

    if (s.type === 'process') {
      const isExternal = s.subtype === 'external';
      const isExtCo    = s.subtype === 'extco';
      const haloGap = 7;
      const shapeRx = (isExternal || isExtCo) ? s.h / 2 : 16;
      // Auréole
      el('rect', {
        x: s.x - haloGap, y: s.y - haloGap,
        width: s.w + haloGap * 2, height: s.h + haloGap * 2,
        rx: shapeRx + haloGap, ry: shapeRx + haloGap,
        fill: 'none',
        stroke: s.strokeColor || darkenColor(s.color, 0.65),
        'stroke-width': '2.5',
        'pointer-events': 'none',
      }, g);
      const shapeFill = isExtCo ? `url(#${ensureHatchPattern(s.color)})` : s.color;
      shapeEl = el('rect', {
        x: s.x, y: s.y, width: s.w, height: s.h,
        rx: shapeRx, ry: shapeRx,
        fill: shapeFill,
        filter: filterAttr,
        'data-shape-fill': '1',
      }, g);
      el('rect', {
        x: s.x + 1, y: s.y + 1, width: s.w - 2, height: s.h * 0.55,
        rx: shapeRx - 1, ry: shapeRx - 1,
        fill: 'url(#shape-shine)',
        'pointer-events': 'none',
      }, g);
    } else if (s.type === 'start-end') {
      shapeEl = el('ellipse', {
        cx: s.x + s.w / 2, cy: s.y + s.h / 2,
        rx: s.w / 2, ry: s.h / 2,
        fill: s.color,
        filter: filterAttr,
        'data-shape-fill': '1',
      }, g);
      el('ellipse', {
        cx: s.x + s.w / 2, cy: s.y + s.h * 0.35,
        rx: s.w * 0.38, ry: s.h * 0.28,
        fill: 'url(#shape-shine)',
        'pointer-events': 'none',
      }, g);
    } else if (s.type === 'decision') {
      const dPath = roundedDiamond(s.x, s.y, s.w, s.h, 14);
      shapeEl = el('path', {
        d: dPath,
        fill: s.color,
        filter: filterAttr,
        'data-shape-fill': '1',
      }, g);
      // Shine : triangle supérieur arrondi
      const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
      const len = Math.hypot(s.w/2, s.h/2);
      const rx14 = 14 * (s.w/2) / len, ry14 = 14 * (s.h/2) / len;
      const shinePath = `M ${cx-rx14},${s.y+ry14}` +
        ` Q ${cx},${s.y} ${cx+rx14},${s.y+ry14}` +
        ` L ${s.x+s.w-rx14},${cy-ry14}` +
        ` Q ${s.x+s.w},${cy} ${cx},${cy}` +
        ` L ${cx-rx14},${s.y+ry14} Z`;
      el('path', {
        d: shinePath,
        fill: 'url(#shape-shine)',
        'pointer-events': 'none',
      }, g);
    } else {
      shapeEl = el('path', {
        d: wavyPath(s.x, s.y, s.w, s.h),
        fill: s.color,
        filter: filterAttr,
        'data-shape-fill': '1',
      }, g);
      el('path', {
        d: wavyPath(s.x, s.y, s.w, s.h * 0.52),
        fill: 'url(#shape-shine)',
        'pointer-events': 'none',
        opacity: '0.7',
      }, g);
    }

    // ── Label ────────────────────────────────────
    if (s.label) {
      // Diamond gets a tighter text zone (inscribed square ~ 0.5 of w)
      const textZoneW = s.type === 'decision' ? s.w * 0.52 : s.w;
      const maxChars = Math.max(4, Math.floor(textZoneW / (s.fontSize * 0.62)));
      const lines = wrapText(s.label, maxChars);
      const lineH = s.fontSize * 1.32;
      const totalH = lines.length * lineH;
      const startY = s.y + s.h / 2 - totalH / 2 + lineH / 2;

      lines.forEach((line, i) => {
        txt(line, {
          x: s.x + s.w / 2,
          y: startY + i * lineH,
          'text-anchor': 'middle',
          'dominant-baseline': 'middle',
          fill: s.textColor,
          'font-size': s.fontSize,
          'font-family': 'Segoe UI, system-ui, sans-serif',
          'font-weight': '700',
          'pointer-events': 'none',
        }, g);
      });
    }

    // ── Validation badge (bottom-right corner) ───
    if (s.validationBadge) {
      const badgeR  = Math.max(12, Math.min(18, s.h * 0.22));
      const badgeX  = s.x + s.w - (s.type === 'decision' ? badgeR * 0.4 : -badgeR * 0.3);
      const badgeY  = s.y + s.h - (s.type === 'decision' ? badgeR * 0.4 : -badgeR * 0.3);
      const bColor  = s.validationColor || '#4DB868';

      // outer white halo
      el('circle', { cx: badgeX, cy: badgeY, r: badgeR + 2.5, fill: '#fff', 'pointer-events': 'none' }, g);
      // colored badge circle
      el('circle', { cx: badgeX, cy: badgeY, r: badgeR, fill: bColor, 'pointer-events': 'none' }, g);
      // shine arc on badge
      el('circle', { cx: badgeX, cy: badgeY - badgeR * 0.2, r: badgeR * 0.55,
        fill: 'rgba(255,255,255,0.18)', 'pointer-events': 'none' }, g);
      // checkmark path (scaled to badge radius)
      const s1 = badgeR * 0.32, s2 = badgeR * 0.52, s3 = badgeR * 0.78;
      const ckPath = `M ${badgeX - s3},${badgeY} L ${badgeX - s1},${badgeY + s2} L ${badgeX + s3},${badgeY - s2}`;
      el('path', {
        d: ckPath,
        fill: 'none',
        stroke: '#ffffff',
        'stroke-width': Math.max(1.5, badgeR * 0.22),
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'pointer-events': 'none',
      }, g);
    }

    // ── Port handles (carrés interactifs, visibles au survol dans tous les modes) ──
    if (isHover && !portDrag) {
      // Taille en SVG inversement proportionnelle au zoom pour rester lisible
      const ps = Math.max(10, Math.round(12 / vpScale));
      const sw = Math.max(1, Math.round(1.5 / vpScale));
      for (const [pName, p] of Object.entries(getPorts(s))) {
        el('rect', {
          x: p.x - ps / 2, y: p.y - ps / 2,
          width: ps, height: ps,
          fill: tool === 'connect' ? '#1f7a54' : '#3b82f6',
          stroke: '#ffffff',
          'stroke-width': sw,
          rx: '2',
          'data-port': pName,
          'data-shape-id': s.id,
          cursor: 'crosshair',
        }, g);
      }
    }

    // ── Connecting source highlight ───────────────
    if (connecting && connecting.fromId === s.id) {
      if (s.type === 'process' || s.type === 'special') {
        el('rect', { x: s.x - 3, y: s.y - 3, width: s.w + 6, height: s.h + 6, rx: '14', fill: 'none', stroke: '#1f7a54', 'stroke-width': '2.5', 'stroke-dasharray': '6,3', 'pointer-events': 'none' }, g);
      } else if (s.type === 'start-end') {
        el('ellipse', { cx: s.x + s.w / 2, cy: s.y + s.h / 2, rx: s.w / 2 + 4, ry: s.h / 2 + 4, fill: 'none', stroke: '#1f7a54', 'stroke-width': '2.5', 'stroke-dasharray': '6,3', 'pointer-events': 'none' }, g);
      } else if (s.type === 'decision') {
        const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
        const p = 4;
        el('path', {
          d: `M ${cx},${s.y - p} L ${s.x + s.w + p},${cy} L ${cx},${s.y + s.h + p} L ${s.x - p},${cy} Z`,
          fill: 'none', stroke: '#1f7a54', 'stroke-width': '2.5', 'stroke-dasharray': '6,3', 'pointer-events': 'none',
        }, g);
      }
    }
  }
}

/* ══════════════════════════════════════════════════
   RENDER — HANDLES (selection)
   ══════════════════════════════════════════════════ */

function renderHandles() {
  gHandles.innerHTML = '';

  for (const id of selectedShapes) {
    const s = state.shapes.find(x => x.id === id);
    if (!s) continue;
    el('rect', {
      x: s.x - 5, y: s.y - 5,
      width: s.w + 10, height: s.h + 10,
      rx: '14', ry: '14',
      fill: 'none',
      stroke: '#3b82f6',
      'stroke-width': '2',
      'stroke-dasharray': '7,4',
      'pointer-events': 'none',
    }, gHandles);
  }

  // Indicateurs de port (10) sur la forme survolée lors du drag d'extrémité de connexion
  if (connEndDrag) {
    // Afficher les 10 ports sur toutes les formes proches (rayon SHOW_R)
    const SHOW_R = 120;
    for (const s of state.shapes) {
      const distToShape = Math.hypot(
        connEndDrag.curX - (s.x + s.w/2),
        connEndDrag.curY - (s.y + s.h/2)
      );
      if (distToShape > SHOW_R + Math.max(s.w, s.h)) continue;
      const dPorts = getDetailedPorts(s);
      for (const pt of dPorts) {
        const isSnap = s.id === connEndDrag.snapShapeId &&
                       pt.dir === connEndDrag.snapDir &&
                       Math.abs(pt.t - connEndDrag.snapT) < 0.01;
        el('circle', {
          cx: String(pt.x), cy: String(pt.y), r: isSnap ? '9' : '5',
          fill: isSnap ? '#22c55e' : 'rgba(34,197,94,0.45)',
          stroke: '#ffffff', 'stroke-width': isSnap ? '2' : '1.5',
          'pointer-events': 'none',
        }, gHandles);
        if (isSnap) {
          el('circle', {
            cx: String(pt.x), cy: String(pt.y), r: '16',
            fill: 'none', stroke: '#22c55e', 'stroke-width': '1.5',
            'stroke-dasharray': '4,3', 'pointer-events': 'none',
            opacity: '0.7',
          }, gHandles);
        }
      }
    }
  }
}

/* ══════════════════════════════════════════════════
   RENDER — GROUPS (containers visuels)
   ══════════════════════════════════════════════════ */

function renderGroups() {
  if (!gGroups) return;
  gGroups.innerHTML = '';
  if (!state.groups || state.groups.length === 0) return;

  for (const grp of state.groups) {
    const shapes = state.shapes.filter(s => grp.shapeIds.includes(s.id));
    if (shapes.length === 0) continue;

    const PAD = 22, LABEL_H = 24;
    const xs = shapes.flatMap(s => [s.x, s.x + s.w]);
    const ys = shapes.flatMap(s => [s.y, s.y + s.h]);
    const gx = Math.min(...xs) - PAD;
    const gy = Math.min(...ys) - PAD - LABEL_H;
    const gw = Math.max(...xs) - Math.min(...xs) + PAD * 2;
    const gh = Math.max(...ys) - Math.min(...ys) + PAD * 2 + LABEL_H;

    const color = grp.color || '#b3a0ff';
    const isSel = selectedGroup === grp.id;
    const isHL  = groupHighlightId === grp.id;

    const grpG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    grpG.setAttribute('class', 'group-container');
    grpG.setAttribute('data-group-id', String(grp.id));
    grpG.style.cursor = 'pointer';
    gGroups.appendChild(grpG);

    el('rect', {
      x: gx, y: gy, width: gw, height: gh, rx: 18, ry: 18,
      fill: isHL ? 'rgba(252,205,255,0.06)' : (isSel ? 'rgba(179,160,255,0.07)' : 'rgba(179,160,255,0.03)'),
      stroke: isHL ? '#fccdff' : color,
      'stroke-width': isSel || isHL ? '2' : '1.5',
      'stroke-dasharray': '8,5',
    }, grpG);

    // Badge label
    const lblW = Math.min(120, (grp.label || 'Groupe').length * 8 + 20);
    el('rect', { x: gx + 12, y: gy + 5, width: lblW, height: LABEL_H - 6, rx: 7, fill: isHL ? '#fccdff' : color, opacity: '0.9' }, grpG);
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    t.setAttribute('x', String(gx + 12 + lblW / 2));
    t.setAttribute('y', String(gy + 17));
    t.setAttribute('text-anchor', 'middle');
    t.setAttribute('fill', isHL ? '#5b0070' : '#ffffff');
    t.setAttribute('font-size', '11');
    t.setAttribute('font-weight', '700');
    t.setAttribute('font-family', 'Segoe UI, sans-serif');
    t.setAttribute('pointer-events', 'none');
    t.textContent = grp.label || 'Groupe';
    grpG.appendChild(t);

    grpG.addEventListener('click', e => {
      e.stopPropagation();
      if (tool !== 'select') return;
      selectedGroup = selectedGroup === grp.id ? null : grp.id;
      selectedShapes.clear(); selectedConn = null; selectedBand = null;
      render(); updateProps();
      if (selectedGroup !== null) setPropsOpen(true);
    });
  }
}

/* ══════════════════════════════════════════════════
   HIGHLIGHT GROUPE (grise tout sauf le groupe ciblé)
   ══════════════════════════════════════════════════ */

function applyGroupHighlight() {
  if (groupHighlightId === null) {
    gOverlay.innerHTML = '';
    // Reset opacities
    gShapes.querySelectorAll('.shape-group').forEach(sg => { sg.style.opacity = ''; });
    gConns.querySelectorAll('path[data-type="conn"]').forEach(p => { p.style.opacity = ''; p.style.stroke = ''; });
    return;
  }
  const grp = state.groups.find(g => g.id === groupHighlightId);
  if (!grp) { groupHighlightId = null; applyGroupHighlight(); return; }

  const inGroup = new Set(grp.shapeIds);
  const inConnGroup = new Set(
    state.connections
      .filter(c => inGroup.has(c.fromId) || inGroup.has(c.toId))
      .map(c => c.id)
  );

  // Dim shapes not in group
  gShapes.querySelectorAll('.shape-group').forEach(sg => {
    const id = parseInt(sg.getAttribute('data-id'));
    sg.style.opacity = inGroup.has(id) ? '1' : '0.07';
  });

  // Dim + recolor connections
  gConns.querySelectorAll('path[data-type="conn"]').forEach(p => {
    const id = parseInt(p.getAttribute('data-id'));
    if (inConnGroup.has(id)) {
      p.style.opacity = '1';
      p.setAttribute('stroke', '#fccdff');
    } else {
      p.style.opacity = '0.07';
    }
  });

  // Tint overlay on highlighted shapes
  gOverlay.innerHTML = '';
  state.shapes.filter(s => inGroup.has(s.id)).forEach(s => {
    if (s.type === 'process' || s.type === 'special') {
      el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: '16', fill: '#fccdff', opacity: '0.22', 'pointer-events': 'none' }, gOverlay);
    } else if (s.type === 'start-end') {
      el('ellipse', { cx: s.x + s.w/2, cy: s.y + s.h/2, rx: s.w/2, ry: s.h/2, fill: '#fccdff', opacity: '0.22', 'pointer-events': 'none' }, gOverlay);
    } else if (s.type === 'decision') {
      const cx = s.x + s.w/2, cy = s.y + s.h/2;
      el('path', { d: `M ${cx},${s.y} L ${s.x+s.w},${cy} L ${cx},${s.y+s.h} L ${s.x},${cy} Z`, fill: '#fccdff', opacity: '0.22', 'pointer-events': 'none' }, gOverlay);
    }
  });
}

/* ══════════════════════════════════════════════════
   RENDER ALL
   ══════════════════════════════════════════════════ */

function render() {
  renderBands();
  renderLegend();
  renderGroups();
  renderConnections();
  renderShapes();
  renderHandles();
  renderCanvasMap();
  applyGroupHighlight();
}

/* ══════════════════════════════════════════════════
   RENDER — CANVAS MAP (left panel live list)
   ══════════════════════════════════════════════════ */

function renderCanvasMap() {
  const list = document.getElementById('canvas-map-list');
  if (!list) return;
  list.innerHTML = '';

  // ── Groupes ─────────────────────────────────────
  if (state.groups && state.groups.length > 0) {
    const gl = document.createElement('div');
    gl.className = 'left-section-label';
    gl.innerHTML = '<i class="fa-solid fa-object-group"></i> Groupes';
    list.appendChild(gl);

    state.groups.forEach(grp => {
      const isHL = groupHighlightId === grp.id;
      const isExp = expandedGroups.has(grp.id);
      const color = grp.color || '#b3a0ff';

      const header = document.createElement('div');
      header.className = 'cmap-group-header' + (isHL ? ' highlighted' : '') + (isExp ? ' open' : '');
      header.innerHTML = `
        <span class="cmap-group-dot" style="background:${color}"></span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${grp.label || 'Groupe'}</span>
        <span class="cmap-group-count">${grp.shapeIds.length}</span>
        <i class="fa-solid fa-chevron-right cmap-group-arrow"></i>`;

      header.addEventListener('click', () => {
        if (groupHighlightId === grp.id) {
          groupHighlightId = null;
        } else {
          groupHighlightId = grp.id;
          fitView();
        }
        render();
      });

      header.querySelector('.cmap-group-arrow').addEventListener('click', e => {
        e.stopPropagation();
        if (expandedGroups.has(grp.id)) expandedGroups.delete(grp.id);
        else expandedGroups.add(grp.id);
        renderCanvasMap();
      });

      list.appendChild(header);

      if (isExp) {
        state.shapes.filter(s => grp.shapeIds.includes(s.id)).forEach(s => {
          const sub = document.createElement('div');
          sub.className = 'cmap-group-subitem';
          sub.innerHTML = `<span class="cmap-color-swatch" style="background:${s.color}"></span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.label || '(sans label)'}</span>`;
          sub.addEventListener('click', () => {
            selectShape(s.id, false, true);
            if (!propsOpen) setPropsOpen(true);
            render(); updateProps();
          });
          list.appendChild(sub);
        });
      }
    });
  }

  // ── Bandes ──────────────────────────────────────
  if (state.bands.length > 0) {
    const bl = document.createElement('div');
    bl.className = 'left-section-label';
    bl.innerHTML = '<i class="fa-solid fa-table-columns"></i> Bandes';
    list.appendChild(bl);

    state.bands.forEach(band => {
      const item = document.createElement('div');
      item.className = 'cmap-item' + (selectedBand === band.id ? ' selected' : '');
      item.innerHTML = `<span class="cmap-color-swatch" style="background:${band.color}"></span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${band.label || '(sans nom)'}</span>`;
      item.addEventListener('click', () => {
        selectedShapes.clear(); selectedConn = null;
        selectedBand = (selectedBand === band.id) ? null : band.id;
        if (selectedBand !== null && !propsOpen) setPropsOpen(true);
        render(); updateProps();
      });
      list.appendChild(item);
    });
  }

  // Formes
  if (state.shapes.length > 0) {
    const sl = document.createElement('div');
    sl.className = 'left-section-label';
    sl.innerHTML = '<i class="fa-solid fa-shapes"></i> Formes';
    list.appendChild(sl);

    const typeIcons = { process: 'fa-square', 'start-end': 'fa-circle', special: 'fa-wave-square', decision: 'fa-diamond' };
    state.shapes.forEach(s => {
      const isSel = selectedShapes.has(s.id);
      const item = document.createElement('div');
      item.className = 'cmap-item' + (isSel ? ' selected' : '');
      item.innerHTML = `<span class="cmap-color-swatch" style="background:${s.color}"></span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.label || '(sans label)'}</span>`;
      item.addEventListener('click', () => {
        selectShape(s.id, false, true);
        if (!propsOpen) setPropsOpen(true);
        render(); updateProps();
      });
      list.appendChild(item);
    });
  }

  // Connexions
  if (state.connections.length > 0) {
    const cl = document.createElement('div');
    cl.className = 'left-section-label';
    cl.innerHTML = '<i class="fa-solid fa-bezier-curve"></i> Connexions';
    list.appendChild(cl);

    state.connections.forEach(c => {
      const isSel = selectedConn === c.id;
      const from = state.shapes.find(s => s.id === c.fromId);
      const to   = state.shapes.find(s => s.id === c.toId);
      const item = document.createElement('div');
      item.className = 'cmap-item' + (isSel ? ' selected' : '');
      const label = c.label || `${from?.label || '?'} → ${to?.label || '?'}`;
      item.innerHTML = `<span class="cmap-color-swatch" style="background:${c.color};border-radius:50%"></span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${label}</span>`;
      item.addEventListener('click', () => {
        selectConn(c.id);
        if (!propsOpen) setPropsOpen(true);
        render(); updateProps();
      });
      list.appendChild(item);
    });
  }
}

/* ══════════════════════════════════════════════════
   HISTORY
   ══════════════════════════════════════════════════ */

function snapshot() {
  history = history.slice(0, histIndex + 1);
  history.push(JSON.stringify(state));
  histIndex = history.length - 1;
}

function undo() {
  if (histIndex <= 0) return;
  histIndex--;
  state = JSON.parse(history[histIndex]);
  clearSelection();
  render();
  updateProps();
  showToast('Annulé');
}

function redo() {
  if (histIndex >= history.length - 1) return;
  histIndex++;
  state = JSON.parse(history[histIndex]);
  clearSelection();
  render();
  updateProps();
  showToast('Rétabli');
}

/* ══════════════════════════════════════════════════
   SELECTION
   ══════════════════════════════════════════════════ */

function clearSelection() {
  selectedShapes.clear();
  selectedConn = null;
  selectedBand = null;
  selectedGroup = null;
}

function selectShape(id, additive = false, triggerAnimation = false) {
  if (!additive) selectedShapes.clear();
  selectedShapes.add(id);
  selectedConn = null;
  selectedBand = null;
  selectedGroup = null;
  if (triggerAnimation) {
    const s = state.shapes.find(s => s.id === id);
    if (s) {
      focusOnShape(s, true);
      requestAnimationFrame(() => animateShapeFloat(id));
    }
  }
}

/* ══════════════════════════════════════════════════
   SELECTION ANIMATION
   ══════════════════════════════════════════════════ */

function focusOnShape(s, animate = true) {
  const r = canvas.getBoundingClientRect();
  const targetScale = Math.min(1.0, Math.min(r.width / (s.w * 1.8), r.height / (s.h * 1.8)));
  const targetX = r.width  / 2 - (s.x + s.w / 2) * targetScale;
  const targetY = r.height / 2 - (s.y + s.h / 2) * targetScale;

  if (!animate) {
    vpX = targetX; vpY = targetY; vpScale = targetScale;
    applyViewport();
    return;
  }

  const startX = vpX, startY = vpY, startScale = vpScale;
  const t0 = performance.now();
  const duration = 400;
  function ease(t) { return t < 0.5 ? 2*t*t : -1 + (4 - 2*t)*t; }

  function frame(now) {
    const raw = Math.min((now - t0) / duration, 1);
    const e = ease(raw);
    vpX = startX + (targetX - startX) * e;
    vpY = startY + (targetY - startY) * e;
    vpScale = startScale + (targetScale - startScale) * e;
    applyViewport();
    if (raw < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

function animateShapeFloat(shapeId) {
  const g = gShapes.querySelector(`[data-id="${shapeId}"]`);
  if (!g) return;
  const at = document.createElementNS('http://www.w3.org/2000/svg', 'animateTransform');
  at.setAttribute('attributeName', 'transform');
  at.setAttribute('type', 'translate');
  at.setAttribute('values', '0,0; 0,-6; 0,0; 0,6; 0,0');
  at.setAttribute('dur', '1.8s');
  at.setAttribute('repeatCount', '2');
  at.setAttribute('additive', 'sum');
  g.appendChild(at);
  setTimeout(() => { if (at.parentNode) at.remove(); }, 3700);
}

function selectConn(id) {
  selectedShapes.clear();
  selectedConn = id;
  selectedBand = null;
  selectedGroup = null;
}

/* ══════════════════════════════════════════════════
   MOUSE EVENTS
   ══════════════════════════════════════════════════ */

canvas.addEventListener('mousedown', onDown);
canvas.addEventListener('mousemove', onMove);
canvas.addEventListener('mouseup',   onUp);
canvas.addEventListener('dblclick',  onDbl);
canvas.addEventListener('wheel',     onWheel, { passive: false });
canvas.addEventListener('contextmenu', e => e.preventDefault());

function onDown(e) {
  e.preventDefault();
  if (labelEditing) commitLabel();

  // Middle-button pan or Space+Left
  if (e.button === 1 || (e.button === 0 && spaceDown)) {
    isPanning = true;
    panStart = { sx: e.clientX, sy: e.clientY, vpX, vpY };
    canvas.style.cursor = 'grabbing';
    return;
  }
  if (e.button !== 0) return;

  const { x, y } = screenToSVG(e.clientX, e.clientY);

  // ── Drag depuis une poignée de port (toujours actif) ─────
  const portEl = e.target.closest('[data-port]');
  if (portEl && !spaceDown) {
    const fromShapeId = parseInt(portEl.getAttribute('data-shape-id'));
    const portName    = portEl.getAttribute('data-port');
    const shape = state.shapes.find(s => s.id === fromShapeId);
    if (shape) {
      portDrag = { fromShapeId, fromPort: getPorts(shape)[portName] };
      canvas.style.cursor = 'crosshair';
    }
    return;
  }

  // ── Clic sur zone index de bande (SVG, suit le pan) ──────
  const bandIndexTarget = e.target.closest('[data-band-index]');
  if (bandIndexTarget) {
    const bid = parseInt(bandIndexTarget.getAttribute('data-band-index'));
    selectedShapes.clear();
    selectedConn = null;
    selectedBand = (selectedBand === bid) ? null : bid;
    if (selectedBand !== null && !propsOpen) setPropsOpen(true);
    render(); updateProps();
    return;
  }

  // ── Contrôles UI bandes (actifs quel que soit l'outil) ──
  const bandResizerTarget = e.target.closest('[data-type="band-resizer"]');
  if (bandResizerTarget) {
    isResizingBandWidth = true;
    canvas.style.cursor = 'ew-resize';
    return;
  }
  const bandHeightTarget = e.target.closest('[data-type="band-height-resizer"]');
  if (bandHeightTarget) {
    isResizingBandHeight = true;
    bandHeightResizingId = parseInt(bandHeightTarget.getAttribute('data-band-height-id'));
    const b = state.bands.find(b => b.id === bandHeightResizingId);
    bandHeightStartY = e.clientY;
    bandHeightStartValue = b ? b.height : 180;
    canvas.style.cursor = 'ns-resize';
    return;
  }
  const addBandTarget = e.target.closest('[data-type="add-band"]');
  if (addBandTarget) {
    state.bands.push({ id: state.nextId++, label: '', color: '#22c55e', fontSize: 22, height: 150 });
    snapshot(); render();
    showToast('Bande ajoutée');
    return;
  }

  /* ── Select tool ── */
  if (tool === 'select') {
    // Drag d'une extrémité de connexion
    const connEndEl = e.target.closest('[data-conn-end]');
    if (connEndEl) {
      const cid  = parseInt(connEndEl.getAttribute('data-conn-id'));
      const which = connEndEl.getAttribute('data-conn-end');
      connEndDrag = { connId: cid, which, curX: x, curY: y, snapShapeId: null, snapDir: null };
      canvas.style.cursor = 'grabbing';
      return;
    }

    // Did we click a connection?
    const connTarget = e.target.closest('[data-type="conn"]');
    if (connTarget) {
      const cid = parseInt(connTarget.getAttribute('data-id'));
      selectConn(cid);
      if (!propsOpen) setPropsOpen(true);
      render();
      updateProps();
      return;
    }

    // Did we click a shape?
    const shapeTarget = e.target.closest('[data-type="shape"]');
    if (shapeTarget) {
      const sid = parseInt(shapeTarget.getAttribute('data-id'));
      selectShape(sid, e.shiftKey, true);
      if (!propsOpen) setPropsOpen(true);

      // Prepare drag
      dragData = {
        mx: x, my: y,
        shapes: [...selectedShapes].map(id => {
          const s = state.shapes.find(s => s.id === id);
          return { id, ox: s.x, oy: s.y };
        }),
      };
      isDragging = true;
      render();
      updateProps();
      return;
    }

    // Click sur zone vide → fermer le panneau props + déselectionner tout
    const hadSelection = selectedBand !== null || selectedGroup !== null || selectedShapes.size > 0 || selectedConn !== null;
    clearSelection();
    if (hadSelection) { if (propsOpen) setPropsOpen(false); render(); updateProps(); }
    isPanning = true;
    panStart = { sx: e.clientX, sy: e.clientY, vpX, vpY, moved: false };
    return;
  }

  /* ── Connect tool ── */
  if (tool === 'connect') {
    const shapeTarget = e.target.closest('[data-type="shape"]');
    const groupTarget = !shapeTarget ? e.target.closest('[data-group-id]') : null;
    const targetEl = shapeTarget || groupTarget;
    if (!targetEl) { connecting = null; render(); return; }

    const sid = shapeTarget
      ? parseInt(shapeTarget.getAttribute('data-id'))
      : parseInt(groupTarget.getAttribute('data-group-id'));

    if (!connecting) {
      connecting = { fromId: sid };
      render();
    } else if (connecting.fromId !== sid) {
      const exists = state.connections.some(c => c.fromId === connecting.fromId && c.toId === sid);
      if (!exists) {
        const fromShape = state.shapes.find(s => s.id === connecting.fromId);
        state.connections.push({
          id: state.nextId++,
          fromId: connecting.fromId,
          toId: sid,
          style: 'solid',
          routing: state.defaultRouting || 'smooth',
          color: fromShape ? fromShape.color : '#9ca3af',
          label: '',
        });
        snapshot();
      }
      connecting = null;
      render();
    }
    return;
  }

  // Les formes sont créées uniquement par drag & drop depuis la barre d'outils
}

function onMove(e) {
  /* ── Band width resizing ── */
  if (isResizingBandWidth) {
    const { x } = screenToSVG(e.clientX, e.clientY);
    state.bandWidth = Math.max(200, Math.round(x));
    render();
    return;
  }

  /* ── Band height resizing ── */
  if (isResizingBandHeight) {
    const dy = (e.clientY - bandHeightStartY) / vpScale;
    const b = state.bands.find(b => b.id === bandHeightResizingId);
    if (b) {
      b.height = Math.max(60, Math.round(bandHeightStartValue + dy));
      render();
    }
    return;
  }

  /* ── Panning ── */
  if (isPanning && panStart) {
    const dx = e.clientX - panStart.sx;
    const dy = e.clientY - panStart.sy;
    if (!panStart.moved && Math.hypot(dx, dy) > 4) {
      panStart.moved = true;
      canvas.style.cursor = 'grabbing';
    }
    vpX = panStart.vpX + dx;
    vpY = panStart.vpY + dy;
    applyViewport();
    return;
  }

  /* ── Port drag — aperçu de la connexion ── */
  if (portDrag) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    gOverlay.innerHTML = '';
    const fp = portDrag.fromPort;
    el('path', {
      d: `M ${fp.x},${fp.y} L ${x},${y}`,
      fill: 'none', stroke: '#3b82f6',
      'stroke-width': `${Math.max(1, 2 / vpScale)}`,
      'stroke-dasharray': `${Math.max(4, 7 / vpScale)},${Math.max(3, 5 / vpScale)}`,
      'pointer-events': 'none',
    }, gOverlay);
    return;
  }

  /* ── Drag d'extrémité de connexion ── */
  if (connEndDrag) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    connEndDrag.curX = x;
    connEndDrag.curY = y;
    connEndDrag.snapShapeId = null;
    connEndDrag.snapDir    = null;
    connEndDrag.snapT      = 0.5;

    const SNAP_R = 55; // rayon de snap en px SVG
    let bestDist = SNAP_R, bestShape = null, bestPt = null;
    for (const s of state.shapes) {
      for (const pt of getDetailedPorts(s)) {
        const d = Math.hypot(x - pt.x, y - pt.y);
        if (d < bestDist) { bestDist = d; bestShape = s; bestPt = pt; }
      }
    }
    if (bestShape && bestPt) {
      connEndDrag.snapShapeId = bestShape.id;
      connEndDrag.snapDir    = bestPt.dir;
      connEndDrag.snapT      = bestPt.t;
    }
    renderHandles();
    return;
  }

  /* ── Dragging shapes ── */
  if (isDragging && dragData) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    const dx = x - dragData.mx;
    const dy = y - dragData.my;
    for (const { id, ox, oy } of dragData.shapes) {
      const s = state.shapes.find(s => s.id === id);
      if (s) { s.x = ox + dx; s.y = oy + dy; }
    }
    render();
    return;
  }

  /* ── Hover tracking (tous les modes — port handles) ── */
  const hoverTarget = e.target.closest('[data-type="shape"]');
  const newHover = hoverTarget ? parseInt(hoverTarget.getAttribute('data-id')) : null;
  if (newHover !== hoverShapeId) {
    hoverShapeId = newHover;
    renderShapes();
    renderHandles();
  }

  /* ── Aperçu outil Connecter ── */
  if (tool === 'connect') {
    gOverlay.innerHTML = '';
    if (connecting) {
      const from = state.shapes.find(s => s.id === connecting.fromId);
      if (from) {
        const { x, y } = screenToSVG(e.clientX, e.clientY);
        const fp = { x: from.x + from.w / 2, y: from.y + from.h / 2, dir: 'right' };
        el('path', {
          d: `M ${fp.x},${fp.y} L ${x},${y}`,
          fill: 'none', stroke: '#1f7a54',
          'stroke-width': `${Math.max(1, 2 / vpScale)}`,
          'stroke-dasharray': `${Math.max(4, 7 / vpScale)},${Math.max(3, 5 / vpScale)}`,
          'pointer-events': 'none',
        }, gOverlay);
      }
    }
  } else if (!connecting) {
    gOverlay.innerHTML = '';
  }
}

function onUp(e) {
  /* ── Fin du drag d'extrémité de connexion ── */
  if (connEndDrag) {
    const { connId, which, snapShapeId, snapDir, snapT } = connEndDrag;
    connEndDrag = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    if (snapShapeId && snapDir) {
      const conn = state.connections.find(c => c.id === connId);
      if (conn) {
        if (which === 'from') {
          // Modifie uniquement l'extrémité source — sans toucher à toPortDir
          conn.fromId      = snapShapeId;
          conn.fromPortDir = snapDir;
          conn.fromPortT   = snapT;
          const src = state.shapes.find(s => s.id === snapShapeId);
          if (src) conn.color = src.color;
        } else {
          // Modifie uniquement l'extrémité cible — sans toucher à fromPortDir/fromId
          conn.toId      = snapShapeId;
          conn.toPortDir = snapDir;   // direction indépendante du côté source
          conn.toPortT   = snapT;
        }
        snapshot();
      }
    }
    render();
    return;
  }

  if (isResizingBandWidth) {
    isResizingBandWidth = false;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    snapshot();
    return;
  }
  if (isResizingBandHeight) {
    isResizingBandHeight = false;
    bandHeightResizingId = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    snapshot();
    return;
  }

  /* ── Fin du drag depuis un port ── */
  if (portDrag) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    const shapeHit = shapeAtPoint(x, y);
    const groupHit = !shapeHit && state.groups && state.groups.find(g => {
      const b = getGroupBounds(g);
      return b && x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h;
    });
    const target = shapeHit || (groupHit ? { ...getGroupBounds(groupHit), id: groupHit.id } : null);
    if (target && target.id !== portDrag.fromShapeId) {
      const fp = portDrag.fromPort;
      const tp = bestEntryPort(target, fp);
      // Autoriser plusieurs connexions entre mêmes shapes si ports différents
      const exists = state.connections.some(
        c => c.fromId === portDrag.fromShapeId &&
             c.toId   === target.id &&
             c.fromPortDir === fp.dir
      );
      if (!exists) {
        const fromShape = state.shapes.find(s => s.id === portDrag.fromShapeId);
        state.connections.push({
          id: state.nextId++,
          fromId: portDrag.fromShapeId,
          toId: target.id,
          fromPortDir: fp.dir,
          style: 'solid',
          routing: state.defaultRouting || 'smooth',
          color: fromShape ? fromShape.color : '#9ca3af',
          label: '',
        });
        snapshot();
      }
    }
    portDrag = null;
    gOverlay.innerHTML = '';
    render();
    canvas.style.cursor = spaceDown ? 'grab' : '';
    return;
  }

  if (isPanning) {
    isPanning = false;
    panStart = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
  }
  if (isDragging) {
    isDragging = false;
    if (dragData) {
      for (const { id } of dragData.shapes) {
        const s = state.shapes.find(s => s.id === id);
        if (s) updateShapeColor(s);
      }
      snapshot();
      render();
      dragData = null;
    }
  }
}

function onDbl(e) {
  const st = e.target.closest('[data-type="shape"]');
  if (st) {
    const sid = parseInt(st.getAttribute('data-id'));
    const s = state.shapes.find(s => s.id === sid);
    if (s) startLabelEdit(s);
    return;
  }
  const ct = e.target.closest('[data-type="conn"]');
  if (ct) {
    const cid = parseInt(ct.getAttribute('data-id'));
    const c = state.connections.find(c => c.id === cid);
    if (!c) return;
    const v = prompt('Label de la flèche :', c.label || '');
    if (v !== null) { c.label = v.trim(); snapshot(); render(); }
  }
}

function onWheel(e) {
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.12 : 0.9;
  const r = canvas.getBoundingClientRect();
  const cx = e.clientX - r.left;
  const cy = e.clientY - r.top;
  vpX = cx + factor * (vpX - cx);
  vpY = cy + factor * (vpY - cy);
  vpScale = Math.max(0.08, Math.min(6, vpScale * factor));
  applyViewport();
}

/* ══════════════════════════════════════════════════
   KEYBOARD
   ══════════════════════════════════════════════════ */

document.addEventListener('keydown', e => {
  const _active = document.activeElement;
  if (labelEditing || _active === labelEd || _active?.tagName === 'INPUT' || _active?.tagName === 'TEXTAREA') return;

  if (e.code === 'Space') {
    e.preventDefault();
    spaceDown = true;
    canvas.style.cursor = 'grab';
  }
  if ((e.key === 'z' || e.key === 'Z') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); undo(); }
  if ((e.key === 'y' || e.key === 'Y') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); redo(); }
  if ((e.key === 's' || e.key === 'S') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); saveJSON(); }
  if ((e.key === 'e' || e.key === 'E') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); exportSVG(); }

  if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); deleteSelected(); }
  if ((e.key === 'g' || e.key === 'G') && !e.ctrlKey && !e.metaKey) { e.preventDefault(); createGroup(); }
  if (e.key === 'Escape') {
    connecting = null; hoverShapeId = null;
    portDrag = null; gOverlay.innerHTML = '';
    groupHighlightId = null;
    applyGroupHighlight();
    setTool('select');
  }
  if (e.key === 'f' || e.key === 'F') fitView();

  // Tool shortcuts
  if (!e.ctrlKey && !e.metaKey) {
    if (e.key === 'v' || e.key === 'V') setTool('select');
    if (e.key === 'c' || e.key === 'C') setTool('connect');
  }
});

document.addEventListener('keyup', e => {
  if (e.code === 'Space') {
    spaceDown = false;
    canvas.style.cursor = '';
  }
});

/* ══════════════════════════════════════════════════
   LABEL EDITING (floating overlay)
   ══════════════════════════════════════════════════ */

function startLabelEdit(s) {
  const r = canvas.getBoundingClientRect();
  const sx = (s.x + s.w / 2) * vpScale + vpX + r.left;
  const sy = (s.y + s.h / 2) * vpScale + vpY + r.top;
  const sw = s.w * vpScale;
  const sh = s.h * vpScale;

  labelEd.value = s.label || '';
  labelEd.style.cssText = `
    display: block;
    left: ${sx}px;
    top: ${sy}px;
    width: ${Math.max(sw, 120)}px;
    font-size: ${s.fontSize * vpScale}px;
  `;
  labelEditing = { shapeId: s.id };
  labelEd.focus();
  labelEd.select();

  labelEd.onkeydown = ev => {
    ev.stopPropagation(); // bloque tous les raccourcis globaux (Delete, Espace, etc.)
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); commitLabel(); }
    if (ev.key === 'Escape') { ev.preventDefault(); labelEditing = null; labelEd.style.display = 'none'; }
  };
  labelEd.onblur = commitLabel;
}

function commitLabel() {
  if (!labelEditing) return;
  const s = state.shapes.find(s => s.id === labelEditing.shapeId);
  if (s) { s.label = labelEd.value.trim(); snapshot(); render(); }
  labelEditing = null;
  labelEd.style.display = 'none';
  labelEd.onblur = null;
}

/* ══════════════════════════════════════════════════
   DELETE
   ══════════════════════════════════════════════════ */

function deleteSelected() {
  if (selectedShapes.size > 0) {
    const ids = [...selectedShapes];
    state.shapes = state.shapes.filter(s => !ids.includes(s.id));
    state.connections = state.connections.filter(
      c => !ids.includes(c.fromId) && !ids.includes(c.toId)
    );
    // Nettoyer les groupes dont les shapes ont été supprimées
    if (state.groups) {
      state.groups.forEach(g => { g.shapeIds = g.shapeIds.filter(id => !ids.includes(id)); });
      state.groups = state.groups.filter(g => g.shapeIds.length > 0);
    }
    clearSelection();
    snapshot(); render(); updateProps();
    setPropsOpen(false);
  } else if (selectedConn !== null) {
    state.connections = state.connections.filter(c => c.id !== selectedConn);
    selectedConn = null;
    snapshot(); render(); updateProps();
    setPropsOpen(false);
  }
}

/* ══════════════════════════════════════════════════
   TOOL MANAGEMENT
   ══════════════════════════════════════════════════ */

function setTool(t) {
  tool = t;
  connecting = null;
  hoverShapeId = null;
  gOverlay.innerHTML = '';

  document.querySelectorAll('[data-tool]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tool === t);
  });

  const cursors = { select: 'default', connect: 'crosshair', process: 'crosshair', 'start-end': 'crosshair', special: 'crosshair' };
  canvas.style.cursor = cursors[t] || 'default';

  render();
}

/* ══════════════════════════════════════════════════
   PROPERTIES PANEL
   ══════════════════════════════════════════════════ */

function updateProps() {
  const nothing  = document.getElementById('prop-nothing');
  const shapeSec = document.getElementById('prop-shape');
  const connSec  = document.getElementById('prop-connection');
  const bandSec  = document.getElementById('prop-band');
  const groupSec = document.getElementById('prop-group');

  nothing.style.display  = 'none';
  shapeSec.style.display = 'none';
  connSec.style.display  = 'none';
  bandSec.style.display  = 'none';
  if (groupSec) groupSec.style.display = 'none';
  const alignSec = document.getElementById('prop-align');
  if (alignSec) alignSec.style.display = 'none';

  // Invariant : selectedGroup ne peut pas coexister avec une sélection de forme/connexion
  if (selectedGroup !== null && (selectedShapes.size > 0 || selectedConn !== null)) selectedGroup = null;

  // ── Groupe sélectionné ────────────────────────────
  if (selectedGroup !== null && groupSec) {
    const grp = state.groups && state.groups.find(g => g.id === selectedGroup);
    if (!grp) { nothing.style.display = ''; return; }
    groupSec.style.display = '';
    document.getElementById('group-label-input').value = grp.label || '';
    document.getElementById('group-color-input').value = grp.color || '#b3a0ff';
    _renderGroupShapesList(grp);
    return;
  }

  if (selectedBand !== null) {
    bandSec.style.display = '';
    const band = state.bands.find(b => b.id === selectedBand);
    if (!band) return;
    document.getElementById('band-label').value     = band.label || '';
    document.getElementById('band-color').value     = band.color || '#22c55e';
    document.getElementById('band-font-size').value = band.fontSize || 22;
    document.getElementById('band-height').value    = band.height;
    const pastelEl = document.getElementById('band-pastel-preview');
    if (pastelEl) pastelEl.style.background = bandPastel(band.color || '#22c55e');
    return;
  }

  if (selectedShapes.size === 0 && selectedConn === null) {
    nothing.style.display = '';
    return;
  }

  if (selectedShapes.size > 0) {
    shapeSec.style.display = '';
    // Alignment panel — visible only when 2+ shapes selected
    if (alignSec) {
      alignSec.style.display = selectedShapes.size >= 2 ? '' : 'none';
      const countEl = document.getElementById('prop-align-count');
      if (countEl) countEl.textContent = selectedShapes.size;
    }
    const id = [...selectedShapes][0];
    const s = state.shapes.find(s => s.id === id);
    if (!s) return;
    document.getElementById('prop-label').value      = s.label    || '';
    document.getElementById('prop-color').value      = s.color;
    document.getElementById('prop-text-color').value = s.textColor;
    document.getElementById('prop-width').value      = s.w;
    document.getElementById('prop-height').value     = s.h;
    document.getElementById('prop-font-size').value  = s.fontSize;
    const strokeGroup = document.getElementById('prop-stroke-group');
    if (strokeGroup) {
      strokeGroup.style.display = s.type === 'process' ? '' : 'none';
      if (s.type === 'process') {
        document.getElementById('prop-stroke-color').value = s.strokeColor || darkenColor(s.color, 0.65);
      }
    }
    document.getElementById('prop-validation-enabled').checked = !!s.validationBadge;
    document.getElementById('prop-validation-color').value  = s.validationColor || '#4DB868';
    document.getElementById('prop-validation-color').disabled  = !s.validationBadge;
    // Subtype (normal / externe) — uniquement pour process
    const subtypeRow = document.getElementById('prop-subtype-row');
    if (subtypeRow) {
      subtypeRow.style.display = s.type === 'process' ? '' : 'none';
      if (s.type === 'process') {
        const sub = s.subtype || 'normal';
        document.getElementById('subtype-btn-normal')?.classList.toggle('active', sub === 'normal');
        document.getElementById('subtype-btn-external')?.classList.toggle('active', sub === 'external');
        document.getElementById('subtype-btn-extco')?.classList.toggle('active', sub === 'extco');
      }
    }
    // Variante couleur (0=fidèle, 1=moins fidèle)
    const band = getBandForY(s.y + s.h / 2);
    const v0El = document.getElementById('variant-btn-0');
    const v1El = document.getElementById('variant-btn-1');
    if (v0El && v1El && s.type !== 'decision') {
      const vRow = document.getElementById('prop-variant-row');
      if (vRow) vRow.style.display = '';
      v0El.classList.toggle('active', (s.colorVariant || 0) === 0);
      v1El.classList.toggle('active', (s.colorVariant || 0) === 1);
      if (band) {
        v0El.style.background = band.color;
        v1El.style.background = bandMutedColor(band.color);
      }
    } else {
      const vRow = document.getElementById('prop-variant-row');
      if (vRow) vRow.style.display = 'none';
    }
    return;
  }

  if (selectedConn !== null) {
    connSec.style.display = '';
    const c = state.connections.find(c => c.id === selectedConn);
    if (!c) return;
    document.getElementById('conn-style-solid').checked  = c.style !== 'dashed';
    document.getElementById('conn-style-dashed').checked = c.style === 'dashed';
    document.getElementById('conn-routing-smooth').checked    = (c.routing || 'smooth') === 'smooth';
    document.getElementById('conn-routing-ortho').checked     = c.routing === 'orthogonal';
    document.getElementById('conn-color').value = c.color;
    document.getElementById('conn-label').value = c.label || '';
  }
}

function _renderGroupShapesList(grp) {
  const container = document.getElementById('group-shapes-list');
  if (!container) return;
  container.innerHTML = '';
  for (const s of state.shapes) {
    const inGroup = grp.shapeIds.includes(s.id);
    const row = document.createElement('div');
    row.className = 'group-shape-row' + (inGroup ? ' in-group' : '');
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.checked = inGroup;
    cb.addEventListener('change', () => {
      if (cb.checked) { if (!grp.shapeIds.includes(s.id)) grp.shapeIds.push(s.id); }
      else grp.shapeIds = grp.shapeIds.filter(id => id !== s.id);
      snapshot(); render();
    });
    const lbl = document.createElement('label');
    lbl.textContent = s.label || `#${s.id}`;
    row.appendChild(cb); row.appendChild(lbl);
    container.appendChild(row);
  }
}

function bindProps() {
  // Shape
  const prop = (id, fn) => {
    const el = document.getElementById(id);
    el.addEventListener('input', e => { fn(e.target.value); render(); });
    el.addEventListener('change', snapshot);
  };

  prop('prop-label', v => {
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) s.label = v; }
  });
  // Bloquer les retours à la ligne au-delà de 4 lignes
  document.getElementById('prop-label')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && e.target.value.split('\n').length >= 4) e.preventDefault();
  });
  prop('prop-color', v => {
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) s.color = v; }
  });
  prop('prop-text-color', v => {
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) s.textColor = v; }
  });
  prop('prop-width', v => {
    const n = Math.max(60, parseInt(v) || 60);
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) s.w = n; }
  });
  prop('prop-height', v => {
    const n = Math.max(40, parseInt(v) || 40);
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) s.h = n; }
  });
  prop('prop-font-size', v => {
    const n = Math.max(8, Math.min(40, parseInt(v) || 13));
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) s.fontSize = n; }
  });
  prop('prop-stroke-color', v => {
    for (const id of selectedShapes) {
      const s = state.shapes.find(s => s.id === id);
      if (s && s.type === 'process') { s.strokeColor = v; s.customStroke = true; }
    }
  });
  prop('prop-validation-color', v => {
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) s.validationColor = v; }
  });
  document.getElementById('prop-validation-enabled').addEventListener('change', e => {
    const colorInput = document.getElementById('prop-validation-color');
    colorInput.disabled = !e.target.checked;
    for (const id of selectedShapes) {
      const s = state.shapes.find(s => s.id === id);
      if (s) {
        s.validationBadge = e.target.checked;
        if (e.target.checked && !s.validationColor) s.validationColor = colorInput.value || '#4DB868';
      }
    }
    snapshot(); render();
  });
  // Subtype activité (normale / externe / extco)
  const subtypeMap = { 'subtype-btn-normal': 'normal', 'subtype-btn-external': 'external', 'subtype-btn-extco': 'extco' };
  Object.entries(subtypeMap).forEach(([btnId, sub]) => {
    document.getElementById(btnId)?.addEventListener('click', () => {
      for (const id of selectedShapes) {
        const s = state.shapes.find(s => s.id === id);
        if (s && s.type === 'process') s.subtype = sub;
      }
      snapshot(); render(); updateProps();
    });
  });

  document.getElementById('prop-delete-shape').addEventListener('click', deleteSelected);

  // Variante couleur (fidèle / moins fidèle)
  ['variant-btn-0', 'variant-btn-1'].forEach((btnId, variantVal) => {
    document.getElementById(btnId)?.addEventListener('click', () => {
      for (const id of selectedShapes) {
        const s = state.shapes.find(s => s.id === id);
        if (s) { s.colorVariant = variantVal; updateShapeColor(s); }
      }
      snapshot(); render(); updateProps();
    });
  });

  // Connection — style trait
  document.querySelectorAll('input[name="conn-style"]').forEach(r => {
    r.addEventListener('change', e => {
      const c = state.connections.find(c => c.id === selectedConn);
      if (c) { c.style = e.target.value; snapshot(); render(); }
    });
  });
  // Connection — routing
  document.querySelectorAll('input[name="conn-routing"]').forEach(r => {
    r.addEventListener('change', e => {
      const c = state.connections.find(c => c.id === selectedConn);
      if (c) { c.routing = e.target.value; snapshot(); render(); }
    });
  });
  // Z-order
  document.getElementById('btn-conn-forward')?.addEventListener('click', () => {
    const idx = state.connections.findIndex(c => c.id === selectedConn);
    if (idx < state.connections.length - 1) {
      [state.connections[idx], state.connections[idx+1]] = [state.connections[idx+1], state.connections[idx]];
      snapshot(); render();
    }
  });
  document.getElementById('btn-conn-backward')?.addEventListener('click', () => {
    const idx = state.connections.findIndex(c => c.id === selectedConn);
    if (idx > 0) {
      [state.connections[idx], state.connections[idx-1]] = [state.connections[idx-1], state.connections[idx]];
      snapshot(); render();
    }
  });

  const cprop = (id, fn) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', e => { fn(e.target.value); render(); });
    el.addEventListener('change', snapshot);
  };
  cprop('conn-color', v => {
    const c = state.connections.find(c => c.id === selectedConn);
    if (c) c.color = v;
  });
  cprop('conn-label', v => {
    const c = state.connections.find(c => c.id === selectedConn);
    if (c) c.label = v;
  });
  document.getElementById('prop-delete-conn').addEventListener('click', deleteSelected);

  // Groupe — nom et couleur
  document.getElementById('group-label-input')?.addEventListener('input', e => {
    const grp = state.groups && state.groups.find(g => g.id === selectedGroup);
    if (grp) { grp.label = e.target.value; render(); }
  });
  document.getElementById('group-label-input')?.addEventListener('change', snapshot);
  document.getElementById('group-color-input')?.addEventListener('input', e => {
    const grp = state.groups && state.groups.find(g => g.id === selectedGroup);
    if (grp) { grp.color = e.target.value; render(); }
  });
  document.getElementById('group-color-input')?.addEventListener('change', snapshot);
  document.getElementById('prop-delete-group')?.addEventListener('click', () => {
    state.groups = (state.groups || []).filter(g => g.id !== selectedGroup);
    selectedGroup = null;
    snapshot(); render(); updateProps();
  });
}

/* ══════════════════════════════════════════════════
   FIT VIEW
   ══════════════════════════════════════════════════ */

function fitView() {
  if (state.shapes.length === 0) {
    vpX = 0; vpY = 280; vpScale = 0.5;
    applyViewport(); return;
  }

  const r = canvas.getBoundingClientRect();
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of state.shapes) {
    minX = Math.min(minX, s.x); minY = Math.min(minY, s.y);
    maxX = Math.max(maxX, s.x + s.w); maxY = Math.max(maxY, s.y + s.h);
  }
  // Inclure la zone index SVG dans le bounding-box quand les bandes sont visibles
  if (state.showBands && state.bands.length > 0) minX = Math.min(minX, 0);

  const pad = 60;
  const dw = maxX - minX + pad * 2;
  const dh = maxY - minY + pad * 2;
  vpScale = Math.min(r.width / dw, r.height / dh, 2);
  vpX = (r.width  - dw * vpScale) / 2 - (minX - pad) * vpScale;
  vpY = (r.height - dh * vpScale) / 2 - (minY - pad) * vpScale;
  applyViewport();
}

/* ══════════════════════════════════════════════════
   EXPORT SVG
   ══════════════════════════════════════════════════ */

function exportSVG() {
  if (state.shapes.length === 0) { showToast('Aucune forme à exporter'); return; }

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of state.shapes) {
    minX = Math.min(minX, s.x - 10);
    minY = Math.min(minY, s.y - 10);
    maxX = Math.max(maxX, s.x + s.w + 10);
    maxY = Math.max(maxY, s.y + s.h + 20); // +20 for wavy bottom
  }
  const pad = 50;
  minX -= pad; minY -= pad; maxX += pad; maxY += pad;
  const W = maxX - minX, H = maxY - minY;

  // Render into clean SVG
  const svgNS = 'http://www.w3.org/2000/svg';
  const exportSVGEl = document.createElementNS(svgNS, 'svg');
  exportSVGEl.setAttribute('xmlns', svgNS);
  exportSVGEl.setAttribute('width', W);
  exportSVGEl.setAttribute('height', H);
  exportSVGEl.setAttribute('viewBox', `${minX} ${minY} ${W} ${H}`);

  // Clone defs
  const defs = canvas.querySelector('defs').cloneNode(true);
  exportSVGEl.appendChild(defs);

  // Clone content groups (bands, legend, connections, shapes only — no handles/overlay)
  for (const gId of ['g-bands', 'g-legend', 'g-connections', 'g-shapes']) {
    exportSVGEl.appendChild(document.getElementById(gId).cloneNode(true));
  }

  const svgStr = new XMLSerializer().serializeToString(exportSVGEl);
  const blob = new Blob([svgStr], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'carto_optiq.svg';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  showToast('SVG exporté ✓');
}

function exportPDF() {
  if (state.shapes.length === 0) { showToast('Aucune forme à exporter'); return; }

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of state.shapes) {
    minX = Math.min(minX, s.x - 10);
    minY = Math.min(minY, s.y - 10);
    maxX = Math.max(maxX, s.x + s.w + 10);
    maxY = Math.max(maxY, s.y + s.h + 20);
  }
  const pad = 50;
  minX -= pad; minY -= pad; maxX += pad; maxY += pad;
  const W = maxX - minX, H = maxY - minY;

  const svgNS = 'http://www.w3.org/2000/svg';
  const exportEl = document.createElementNS(svgNS, 'svg');
  exportEl.setAttribute('xmlns', svgNS);
  exportEl.setAttribute('width', W);
  exportEl.setAttribute('height', H);
  exportEl.setAttribute('viewBox', `${minX} ${minY} ${W} ${H}`);

  const defs = canvas.querySelector('defs').cloneNode(true);
  exportEl.appendChild(defs);
  for (const gId of ['g-bands', 'g-legend', 'g-connections', 'g-shapes']) {
    exportEl.appendChild(document.getElementById(gId).cloneNode(true));
  }

  const svgStr = new XMLSerializer().serializeToString(exportEl);
  const encoded = encodeURIComponent(svgStr);
  const win = window.open('', '_blank');
  if (!win) { showToast('Popup bloquée — autorisez les popups pour ce site'); return; }
  win.document.write(`<!DOCTYPE html><html><head><title>OptiqCarto — Export PDF</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:100%; height:100%; background:#F3F5F2; }
  img { display:block; width:100%; height:auto; }
  @media print {
    html, body { background:#F3F5F2; }
    img { width:100%; height:auto; page-break-inside:avoid; }
    @page { margin:10mm; size:A4 landscape; }
  }
</style></head><body>
<img src="data:image/svg+xml;charset=utf-8,${encoded}">
<script>
  var img = document.querySelector('img');
  img.onload = function() {
    setTimeout(function() { window.print(); }, 200);
  };
  img.onerror = function() { document.body.innerHTML += '<p style="color:red;padding:20px">Erreur de rendu SVG</p>'; };
</script>
</body></html>`);
  win.document.close();
  showToast('Fenêtre PDF ouverte — utilisez Ctrl+P pour sauvegarder en PDF');
}

/* ══════════════════════════════════════════════════
   NOUVELLE CARTOGRAPHIE
   ══════════════════════════════════════════════════ */

function newCarto() {
  const isEmpty = state.shapes.length === 0 && state.connections.length === 0;
  if (isEmpty) { _doNewCarto(); return; }

  const dialog = document.getElementById('new-carto-dialog');
  dialog.classList.remove('hidden');
}

/* ══════════════════════════════════════════════════
   GROUPES — création et highlight
   ══════════════════════════════════════════════════ */

function createGroup() {
  if (selectedShapes.size < 2) {
    showToast('Sélectionnez au moins 2 formes pour créer un groupe');
    return;
  }
  if (!state.groups) state.groups = [];
  const id = state.nextId++;
  state.groups.push({
    id,
    label: 'Groupe',
    shapeIds: [...selectedShapes],
    color: '#b3a0ff',
  });
  clearSelection();
  selectedGroup = id;
  snapshot(); render();
  showToast('Groupe créé — double-cliquez pour renommer');
}

function _doNewCarto() {
  clearSelection();
  state.shapes = [];
  state.connections = [];
  state.groups = [];
  state.bands = [
    { id: 1, label: 'Niveau 1', color: '#22c55e', fontSize: 22, height: 180 },
    { id: 2, label: 'Niveau 2', color: '#3b82f6', fontSize: 22, height: 180 },
    { id: 3, label: 'Niveau 3', color: '#f59e0b', fontSize: 22, height: 180 },
  ];
  state.nextId = 100;
  state.showLegend = false;
  groupHighlightId = null;
  selectedGroup = null;
  expandedGroups.clear();
  vpX = 0; vpY = 0; vpScale = 0.5;
  applyViewport();
  history = [JSON.stringify(state)]; histIndex = 0;
  render();
  updateProps();
  showToast('Nouvelle cartographie créée');
}

/* ══════════════════════════════════════════════════
   SAVE / LOAD JSON
   ══════════════════════════════════════════════════ */

async function saveJSON() {
  const name = window.OPTIQCARTO_DEFAULT_NAME
    || prompt('Nom de la cartographie :', 'ma-carto');
  if (!name) return;
  const res = await fetch(`${_API}/api/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, diagram: state }),
  });
  const data = await res.json();
  if (data.ok) showToast('Sauvegardé ✓');
  else showToast('Erreur : ' + data.error);
}

async function openLoadDialog() {
  const dialog = document.getElementById('load-dialog');
  const list   = document.getElementById('load-list');
  dialog.classList.remove('hidden');

  const files = await fetch(`${_API}/api/list`).then(r => r.json());
  list.innerHTML = '';

  if (files.length === 0) {
    list.innerHTML = '<div class="load-empty"><i class="fa-solid fa-folder-open" style="font-size:28px;opacity:.3;display:block;margin-bottom:12px"></i>Aucune cartographie sauvegardée.</div>';
    return;
  }

  for (const name of files) {
    const item = document.createElement('div');
    item.className = 'load-item';
    item.innerHTML = `<i class="fa-solid fa-diagram-project"></i><span>${name}</span><button class="load-delete" title="Supprimer"><i class="fa-solid fa-trash"></i></button>`;

    item.querySelector('span').addEventListener('click', async () => {
      const data = await fetch(`${_API}/api/load/${encodeURIComponent(name)}`).then(r => r.json());
      if (data.error) { showToast('Erreur : ' + data.error); return; }
      state = data;
      // Migration : champs manquants sur anciens fichiers
      if (!state.bandWidth) state.bandWidth = 1600;
      if (!state.groups) state.groups = [];
      groupHighlightId = null; selectedGroup = null; expandedGroups.clear();
      state.bands.forEach(b => {
        delete b.textColor; // supprimé — couleur texte toujours blanc
        if (!b.color || b.color.startsWith('#f') || b.color.startsWith('#e')) {
          // ancienne valeur pastel → remplacer par couleur vivid par défaut
          if (!b._colorMigrated) b.color = '#22c55e';
        }
        if (!b.fontSize || b.fontSize < 18) b.fontSize = Math.round((b.fontSize || 11) * 2);
      });
      state.shapes.forEach(s => {
        // Doubler la fontSize si c'est une ancienne valeur
        if (!s.fontSize || s.fontSize < 20) s.fontSize = Math.round((s.fontSize || 13) * 2);
      });
      clearSelection();
      history = [JSON.stringify(state)]; histIndex = 0;
      render(); updateProps(); fitView();
      dialog.classList.add('hidden');
      showToast('Chargé : ' + name);
    });

    item.querySelector('.load-delete').addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm(`Supprimer "${name}" ?`)) return;
      await fetch(`${_API}/api/delete/${encodeURIComponent(name)}`, { method: 'DELETE' });
      item.remove();
      if (!list.querySelector('.load-item')) openLoadDialog();
    });

    list.appendChild(item);
  }
}

/* ══════════════════════════════════════════════════
   VSDX AUTO-LAYOUT
   ══════════════════════════════════════════════════ */

// (vsdxAutoLayout supprimé — positionnement Visio utilisé directement)
function _unused_vsdxAutoLayout(shapes, conns, bands, groups) {
  if (shapes.length === 0 || bands.length === 0) return;

  // Layout constants
  const COL_STEP   = 215; // px between columns (widest shape 170 + 45 gap)
  const MAX_SH_W   = 170; // max shape width, used to center in column slot
  const GAP_V      = 40;  // vertical gap between shapes in same (band, col) cell
  const Y_PAD      = 30;  // top/bottom band padding
  const MIN_BAND_H = 170;
  const MAX_STACK  = 5;   // max shapes per (band, col) before overflow into next sub-col

  const SZ = {
    process:     { w: 150, h: 80 },
    'start-end': { w: 130, h: 64 },
    special:     { w: 170, h: 76 },
    decision:    { w: 100, h: 100 },
  };
  const defSz = SZ.process;

  // ── 1. Band membership from Visio-derived screenY ──────────────
  const bandStarts = [];
  { let y = 0; for (const b of bands) { bandStarts.push(y); y += b.height; } }

  function bandIdxOf(s) {
    const midY = s.y + s.h / 2;
    for (let i = 0; i < bands.length; i++) {
      if (midY >= bandStarts[i] && midY < bandStarts[i] + bands[i].height) return i;
    }
    let best = 0, bestD = Infinity;
    for (let i = 0; i < bands.length; i++) {
      const d = Math.abs(midY - (bandStarts[i] + bands[i].height / 2));
      if (d < bestD) { bestD = d; best = i; }
    }
    return best;
  }

  const laneOf = new Map();
  const origX  = new Map();
  const origY  = new Map();
  for (const s of shapes) {
    laneOf.set(s.id, bandIdxOf(s));
    origX.set(s.id, s.x);
    origY.set(s.id, s.y + s.h / 2);
  }

  // ── 2. Build graph — expand group IDs to member shape IDs ──────
  // Bug fix: connections can reference group IDs; we must resolve those
  // to their member shapes so the topology is correct.
  const shapeSet = new Set(shapes.map(s => s.id));
  function resolveIds(id) {
    if (shapeSet.has(id)) return [id];
    const g = (groups || []).find(g => g.id === id);
    return g ? g.shapeIds.filter(sid => shapeSet.has(sid)) : [];
  }

  const out  = new Map(shapes.map(s => [s.id, []]));
  const pred = new Map(shapes.map(s => [s.id, []]));
  const inCt = new Map(shapes.map(s => [s.id, 0]));
  for (const c of conns) {
    for (const fid of resolveIds(c.fromId)) {
      for (const tid of resolveIds(c.toId)) {
        if (fid === tid) continue;
        out.get(fid).push(tid);
        pred.get(tid).push(fid);
        inCt.set(tid, inCt.get(tid) + 1);
      }
    }
  }

  // ── 3. Kahn's BFS — longest-path column assignment ─────────────
  const col   = new Map(shapes.map(s => [s.id, 0]));
  const done  = new Set();
  const tmpIn = new Map(inCt);
  const queue = [];
  for (const s of shapes) if (tmpIn.get(s.id) === 0) queue.push(s.id);
  while (queue.length > 0) {
    const id = queue.shift();
    done.add(id);
    for (const nid of out.get(id)) {
      const nc = col.get(id) + 1;
      if (nc > col.get(nid)) col.set(nid, nc);
      tmpIn.set(nid, tmpIn.get(nid) - 1);
      if (tmpIn.get(nid) === 0) queue.push(nid);
    }
  }

  // ── 4. Cycle members: assign level from first reachable assigned pred ──
  // Kahn leaves cycle members with tmpIn > 0. Resolve iteratively.
  let changed = true;
  while (changed) {
    changed = false;
    for (const s of shapes) {
      if (done.has(s.id)) continue;
      let maxC = -1;
      for (const pid of pred.get(s.id)) {
        if (done.has(pid)) maxC = Math.max(maxC, col.get(pid));
      }
      if (maxC >= 0) { col.set(s.id, maxC + 1); done.add(s.id); changed = true; }
    }
  }

  // ── 5. Fallback: pure-cycle nodes with no external pred ────────
  // Use Visio X position (normalized to column slots) — preserves reading order.
  const minVX = shapes.reduce((m, s) => Math.min(m, origX.get(s.id)), Infinity);
  for (const s of shapes) {
    if (!done.has(s.id)) {
      col.set(s.id, Math.round((origX.get(s.id) - minVX) / COL_STEP));
    }
  }

  // ── 6. Group into (lane, logical-col) cells, sort by origY ─────
  const cells = new Map();
  for (const s of shapes) {
    const key = `${laneOf.get(s.id)},${col.get(s.id)}`;
    if (!cells.has(key)) cells.set(key, []);
    cells.get(key).push(s);
  }
  for (const cell of cells.values()) {
    cell.sort((a, b) => origY.get(a.id) - origY.get(b.id));
  }

  // ── 7. Assign positions — overflow tall cells into sub-columns ──
  // If a (band, col) cell has > MAX_STACK shapes, split into adjacent
  // sub-columns so the band doesn't become impossibly tall.
  // We compute the true column offset per shape first.
  const shapeCol = new Map(); // shapeId → effective visual column index
  for (const [key, cell] of cells) {
    const [, baseCol] = key.split(',').map(Number);
    for (let i = 0; i < cell.length; i++) {
      const subColOffset = Math.floor(i / MAX_STACK);
      shapeCol.set(cell[i].id, baseCol + subColOffset);
    }
  }

  // Remap logical columns to avoid gaps caused by sub-column insertion
  const usedCols = [...new Set([...shapeCol.values()])].sort((a, b) => a - b);
  const colRemap = new Map(usedCols.map((c, i) => [c, i]));

  for (const s of shapes) {
    const laneIdx = laneOf.get(s.id);
    const bStart  = bandStarts[laneIdx];
    const vizCol  = colRemap.get(shapeCol.get(s.id)) ?? 0;

    // Find row within the (lane, vizCol) sub-cell
    const subKey = `${laneIdx},${shapeCol.get(s.id)}`;
    const subCell = cells.get(`${laneIdx},${col.get(s.id)}`) || [];
    // position within the current MAX_STACK slice
    const posInCell = subCell.indexOf(s);
    const rowInSlice = posInCell % MAX_STACK;

    const sz = SZ[s.type] || defSz;
    s.w = sz.w;
    s.h = sz.h;
    s.x = INDEX_W_SVG + 50 + vizCol * COL_STEP + Math.round((MAX_SH_W - sz.w) / 2);
    s.y = bStart + Y_PAD + rowInSlice * (sz.h + GAP_V);
  }

  // ── 8. Band heights: fit actual content ────────────────────────
  let cumY = 0;
  for (let i = 0; i < bands.length; i++) {
    bandStarts[i] = cumY;
    const bShapes = shapes.filter(s => laneOf.get(s.id) === i);
    const maxBot  = bShapes.length === 0
      ? cumY + MIN_BAND_H
      : Math.max(...bShapes.map(s => s.y + s.h));
    bands[i].height = Math.max(MIN_BAND_H, Math.round(maxBot - cumY + Y_PAD));
    for (const s of bShapes) {
      s.y = Math.max(cumY + 8, Math.min(s.y, cumY + bands[i].height - s.h - 8));
    }
    cumY += bands[i].height;
  }

  // ── 9. Port directions from final positions ─────────────────────
  const OPP = { right:'left', left:'right', top:'bottom', bottom:'top' };
  for (const c of conns) {
    const fs = shapes.find(s => s.id === c.fromId);
    const ts = shapes.find(s => s.id === c.toId);
    if (!fs || !ts) continue;
    const dx = (ts.x + ts.w / 2) - (fs.x + fs.w / 2);
    const dy = (ts.y + ts.h / 2) - (fs.y + fs.h / 2);
    c.fromPortDir = Math.abs(dx) >= Math.abs(dy)
      ? (dx >= 0 ? 'right' : 'left')
      : (dy >= 0 ? 'bottom' : 'top');
    c.toPortDir   = OPP[c.fromPortDir];
  }
}

/* ══════════════════════════════════════════════════
   VSDX IMPORT
   ══════════════════════════════════════════════════ */

function openVSDXDialog() {
  const dlg = document.getElementById('vsdx-dialog');
  dlg.classList.remove('hidden');
  const statusEl = document.getElementById('vsdx-status');
  statusEl.style.display = 'none';
  statusEl.textContent = '';
  document.getElementById('vsdx-loading').style.display = 'none';
  const dz = document.getElementById('vsdx-dropzone');
  dz.classList.remove('drag-over');
  dz.style.display = '';
}

function detectVSDXShapeType(masterName, visioType, isEllipse, isDiamond, isSubprocess) {
  // Normalize: lowercase + strip accents (NFD + remove combining marks U+0300–U+036F)
  const mn = (masterName || '')
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[-_/]/g, ' ')
    .replace(/\s+/g, ' ').trim();

  // Decision / diamond — by name first (most specific)
  if (/\b(decision|diamond|gateway|exclusive|parallel|condition|conditional|losange|branchement|rhombus|si grand|si petit|big if|small if)\b/.test(mn)
      || mn === 'conditional' || mn === 'decision') return 'decision';
  // Diamond by geometry: EllipticalArcTo intercalated (Si grand/Si petit pattern)
  if (isDiamond) return 'decision';
  // Off-page connectors (Goto / Ext Ret shapes) → special
  if (/\bgot[ot]+\b|\bext\.?\s*ret\b|\bext\.?\s*return\b|\baller\s+[aà]\b|\bautre\s+carte\b/.test(mn)) return 'special';
  // Start/end / terminator / oval / round shapes (by name or master geometry)
  if (/\b(terminator|oval|ellipse|circle|event|rond|cercle|ronde|circulaire)\b/.test(mn)
      || mn === 'start' || mn === 'end'
      || mn.includes('start end') || mn.includes('debut fin') || mn.includes('start/end')
      || isEllipse) return 'start-end';
  // Sous-activité / subprocess — par géométrie (plusieurs sections = marqueurs internes type Predefined Process)
  if (isSubprocess) return 'special';
  // Subprocess / sous-activité — par nom (FR + EN)
  if (/\b(subprocess|sub process|predefined|processus predefini|activite partielle|sous activite|sous processus|sous tache|tache multiple|multi instance|callout|offpage|off page)\b/.test(mn)) return 'special';
  // Visio Group that is not a swimlane → show as subprocess style
  if (visioType === 'Group') return 'special';
  return 'process';
}

async function importVSDX(file) {
  if (!window.JSZip) { showToast('JSZip non disponible'); return; }

  const statusEl  = document.getElementById('vsdx-status');
  const loadingEl = document.getElementById('vsdx-loading');
  const loadingMsg = document.getElementById('vsdx-loading-msg');
  const dropzone  = document.getElementById('vsdx-dropzone');

  function setStatus(msg, isError) {
    if (isError) {
      // Error: show in status bar, restore dropzone, hide spinner
      loadingEl.style.display = 'none';
      dropzone.style.display = '';
      statusEl.style.display = '';
      statusEl.className = 'vsdx-status error';
      statusEl.textContent = msg;
    } else if (msg) {
      // Progress: update spinner text
      if (loadingMsg) loadingMsg.textContent = msg;
    } else {
      // Done/cleared
      statusEl.style.display = 'none';
      loadingEl.style.display = 'none';
    }
  }

  // Switch dropzone → loading spinner
  dropzone.style.display = 'none';
  statusEl.style.display = 'none';
  loadingEl.style.display = '';
  if (loadingMsg) loadingMsg.textContent = 'Lecture du fichier…';

  try {

    const zip = await JSZip.loadAsync(file);
    const parser = new DOMParser();
    const parseXml = text => parser.parseFromString(text, 'application/xml');

    // DOM helpers (namespace-agnostic via localName)
    function vEl(el, name) {
      for (const c of el.childNodes)
        if (c.nodeType === 1 && c.localName === name) return c;
      return null;
    }
    function vAll(el, name) {
      return Array.from(el.childNodes).filter(c => c.nodeType === 1 && c.localName === name);
    }
    function vDeep(el, name) {
      const q = [el];
      while (q.length) {
        const curr = q.shift();
        if (curr.nodeType !== 1) continue;
        if (curr.localName === name) return curr;
        for (const c of curr.childNodes) if (c.nodeType === 1) q.push(c);
      }
      return null;
    }
    function vCell(el, name) {
      for (const c of el.childNodes)
        if (c.nodeType === 1 && c.localName === 'Cell' && c.getAttribute('N') === name)
          return c.getAttribute('V');
      return null;
    }
    // Recherche aussi dans Section > Row > Cell (format Visio étendu)
    function vCellDeep(el, name) {
      const direct = vCell(el, name);
      if (direct !== null) return direct;
      for (const sec of el.childNodes) {
        if (sec.nodeType !== 1 || sec.localName !== 'Section') continue;
        for (const row of sec.childNodes) {
          if (row.nodeType !== 1 || row.localName !== 'Row') continue;
          for (const cell of row.childNodes)
            if (cell.nodeType === 1 && cell.localName === 'Cell' && cell.getAttribute('N') === name)
              return cell.getAttribute('V');
        }
      }
      return null;
    }
    function vText(el) {
      const t = vDeep(el, 'Text');
      return t ? t.textContent.trim() : '';
    }

    // ── Masters ──────────────────────────────────────────
    setStatus('Analyse des masters…');
    const masterIdToName = {};
    const masterIdToFile = {};
    const masterSizeCache = {};

    try {
      const mastersXml  = await zip.file('visio/masters/masters.xml').async('text');
      const mastersRels = await zip.file('visio/masters/_rels/masters.xml.rels').async('text');
      const mDoc  = parseXml(mastersXml);
      const rDoc  = parseXml(mastersRels);

      const ridToFile = {};
      for (const rel of rDoc.getElementsByTagName('Relationship'))
        ridToFile[rel.getAttribute('Id')] = rel.getAttribute('Target');

      for (const m of mDoc.getElementsByTagName('Master')) {
        const mid = m.getAttribute('ID');
        // NameU = Universal (English), Name = localized. On garde les deux pour la détection.
        const nameU = m.getAttribute('NameU') || '';
        const nameL = m.getAttribute('Name') || '';
        masterIdToName[mid] = nameU || nameL; // prefer English universal name
        const relEl = vDeep(m, 'Rel');
        if (relEl) {
          let rid = null;
          for (const attr of relEl.attributes)
            if (attr.localName === 'id') { rid = attr.value; break; }
          if (rid && ridToFile[rid])
            masterIdToFile[mid] = 'visio/masters/' + ridToFile[rid];
        }
      }
    } catch(e) { console.warn('Masters:', e); }

    const masterInfoCache = {};
    async function getMasterInfo(mid) {
      if (!mid) return { w: 0.9449, h: 0.7087, linePattern: 1 };
      if (masterInfoCache[mid]) return masterInfoCache[mid];
      const fpath = masterIdToFile[mid];
      if (!fpath) return masterInfoCache[mid] = { w: 0.9449, h: 0.7087, linePattern: 1 };
      try {
        const xml = await zip.file(fpath).async('text');
        const doc = parseXml(xml);
        let bw, bh, lp = 1, isEllipse = false, isDiamond = false;
        // Visio geometry: <Row T='LineTo'|'EllipticalArcTo'|'Ellipse'> — NOT element names
        const geomRows = doc.getElementsByTagName('Row');
        const geomSeq = []; // sequence of geometry row types (excluding MoveTo)
        let moveTos = 0;
        for (let ri = 0; ri < geomRows.length; ri++) {
          const t = geomRows[ri].getAttribute('T');
          if (t === 'EllipticalArcTo' || t === 'Ellipse') isEllipse = true;
          if (t === 'LineTo' || t === 'EllipticalArcTo') geomSeq.push(t);
          if (t === 'MoveTo') moveTos++;
        }
        // Diamond: EllipticalArcTo intercalated with LineTo (LineTo follows the last arc)
        // Pattern [L,E,L,L,E,L] = Si petit/Si grand; vs [L,L,L,E,E] = stadium (Résultat X)
        if (isEllipse) {
          const lastArcIdx = geomSeq.lastIndexOf('EllipticalArcTo');
          if (lastArcIdx !== -1 && lastArcIdx < geomSeq.length - 1)
            isDiamond = geomSeq.slice(lastArcIdx + 1).includes('LineTo');
        }
        // Sous-activité (Predefined Process) : plusieurs sections géométriques
        // = forme principale + traits internes (marqueurs latéraux ou fond double)
        let geomSectCount = 0;
        const allSects = doc.getElementsByTagName('Section');
        for (let si = 0; si < allSects.length; si++) {
          if (allSects[si].getAttribute('N') === 'Geometry') geomSectCount++;
        }
        // moveTos >= 3 = au moins 3 sous-chemins (rect + 2 marques) → subprocess
        const isSubprocess = (geomSectCount >= 2 || moveTos >= 3) && !isEllipse && !isDiamond;
        for (const s of doc.getElementsByTagName('Shape')) {
          const w = vCell(s, 'Width'), h = vCell(s, 'Height');
          if (w) bw = parseFloat(w);
          if (h) bh = parseFloat(h);
          const lv = vCellDeep(s, 'LinePattern');
          if (lv) lp = parseInt(lv) || 1;
          if (bw && bh) break;
        }
        return masterInfoCache[mid] = { w: bw || 0.9449, h: bh || 0.7087, linePattern: lp, isEllipse, isDiamond, isSubprocess };
      } catch(e) { return masterInfoCache[mid] = { w: 0.9449, h: 0.7087, linePattern: 1, isEllipse: false, isDiamond: false, isSubprocess: false }; }
    }
    // Compat alias
    async function getMasterSize(mid) { const i = await getMasterInfo(mid); return i; }

    // ── Page XML ─────────────────────────────────────────
    setStatus('Lecture de la page…');
    const pageXml = await zip.file('visio/pages/page1.xml').async('text');
    const pageDoc = parseXml(pageXml);

    // Collect all shapes recursively
    function collectShapes(shapesEl, depth, parentId, acc) {
      for (const s of vAll(shapesEl, 'Shape')) {
        acc.push({ el: s, id: s.getAttribute('ID'), depth, parentId });
        const child = vEl(s, 'Shapes');
        if (child) collectShapes(child, depth + 1, s.getAttribute('ID'), acc);
      }
    }
    const allShapes = [];
    const rootShapesEl = vEl(pageDoc.documentElement, 'Shapes');
    if (rootShapesEl) collectShapes(rootShapesEl, 0, null, allShapes);

    const shapeMap = {};
    for (const item of allShapes) shapeMap[item.id] = item;

    // ── Pre-fetch master info pour toutes les formes ─────────
    setStatus('Analyse des masters…');
    {
      const ids = [...new Set(allShapes.map(({el}) => el.getAttribute('Master')).filter(Boolean))];
      for (const mid of ids) await getMasterInfo(mid);
    }

    // ── Coordonnées absolues (cascade depth 0→N) ─────────────
    // PinX/PinY est relatif au coin bas-gauche du parent pour depth>0.
    // Si le parent n'a pas de Width/Height explicite, on utilise le master.
    const shapePinAbs = {};
    for (const { el: s, id, depth, parentId } of allShapes) {
      const mid   = s.getAttribute('Master');
      const mInfo = masterInfoCache[mid] || { w: 0, h: 0 };
      const px = parseFloat(vCell(s, 'PinX')   || '0');
      const py = parseFloat(vCell(s, 'PinY')   || '0');
      const sw = parseFloat(vCell(s, 'Width')  || '0') || mInfo.w;
      const sh = parseFloat(vCell(s, 'Height') || '0') || mInfo.h;
      if (depth === 0 || !parentId || !shapePinAbs[parentId]) {
        shapePinAbs[id] = { pinX: px, pinY: py, w: sw, h: sh };
      } else {
        const par = shapePinAbs[parentId];
        shapePinAbs[id] = {
          pinX: (par.pinX - par.w / 2) + px,
          pinY: (par.pinY - par.h / 2) + py,
          w: sw, h: sh,
        };
      }
    }

    // ── Connects (scan récursif tout le doc) ─────────────────
    const connectorIds = new Set();
    const connMap = {};
    (function scanConnects(el) {
      for (const c of el.childNodes) {
        if (c.nodeType !== 1) continue;
        if (c.localName === 'Connect') {
          const from = c.getAttribute('FromSheet');
          const to   = c.getAttribute('ToSheet');
          const cell = c.getAttribute('FromCell');
          if (from) {
            connectorIds.add(from);
            if (!connMap[from]) connMap[from] = {};
            if (cell === 'BeginX') connMap[from].source = to;
            else if (cell === 'EndX') connMap[from].target = to;
          }
        } else { scanConnects(c); }
      }
    })(pageDoc.documentElement);

    // ── Identifier les conteneurs (pool/lane/swimlane) ────────
    // = groupes dont le nom contient lane/pool OU largeur > 40% de la page
    const LANE_RE = /\b(lane|swimlane|couloir)\b/;
    const POOL_RE = /\b(pool|cross.?functional)\b/;

    let pageMaxW = 0;
    for (const { id } of allShapes) {
      const abs = shapePinAbs[id];
      if (abs) pageMaxW = Math.max(pageMaxW, abs.w);
    }

    const containerIds = new Set();
    for (const { el: s, id } of allShapes) {
      if (s.getAttribute('Type') !== 'Group') continue;
      const mn  = (masterIdToName[s.getAttribute('Master')] || '').toLowerCase();
      const abs = shapePinAbs[id] || {};
      if (LANE_RE.test(mn) || POOL_RE.test(mn) || (abs.w > pageMaxW * 0.4 && vEl(s, 'Shapes')))
        containerIds.add(id);
    }

    // ── Scale ─────────────────────────────────────────────────
    const SCALE = 130 / 0.9449;
    const FALLBACK_COLORS = ['#22c55e','#3b82f6','#f59e0b','#e85d4a','#8b5cf6',
                             '#06b6d4','#ec4899','#f43f5e','#14b8a6','#a855f7'];
    function isWashedOut(hex) {
      if (!hex || !hex.startsWith('#') || hex.length < 7) return true;
      const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
      return (r*299+g*587+b*114)/1000 > 210;
    }

    // ── Bandes depuis les lanes ───────────────────────────────
    setStatus('Construction des bandes…');
    // Lanes = conteneurs avec hauteur raisonnable ET largeur > 30% page
    const laneList = [];
    for (const { el: s, id } of allShapes) {
      if (!containerIds.has(id)) continue;
      const abs = shapePinAbs[id] || {};
      if (!abs.h || abs.h < 0.3 || abs.h > 25) continue; // pas un sliver ni un pool géant
      if (!abs.w || abs.w < pageMaxW * 0.3)    continue; // doit s'étendre sur la page
      laneList.push({ el: s, id, abs });
    }
    laneList.sort((a, b) => b.abs.pinY - a.abs.pinY); // haut en premier

    // Dédupliquer les lanes trop proches (separators, headers)
    const lanes = [];
    for (const ln of laneList) {
      const prev = lanes[lanes.length - 1];
      if (prev && Math.abs(ln.abs.pinY - prev.abs.pinY) < 0.15) continue;
      lanes.push(ln);
    }

    // topOfDiagram = bord supérieur de la première lane
    let topOfDiagram;
    let leftEdge = 0;
    if (lanes.length > 0) {
      topOfDiagram = lanes[0].abs.pinY + lanes[0].abs.h / 2;
      leftEdge     = Math.min(...lanes.map(l => l.abs.pinX - l.abs.w / 2));
    } else {
      let maxY = 0;
      for (const { id } of allShapes) {
        const abs = shapePinAbs[id];
        if (abs && abs.pinY + abs.h/2 > maxY) maxY = abs.pinY + abs.h/2;
      }
      topOfDiagram = maxY || 42;
    }

    const newBands = [];
    const legendBounds = []; // bounding boxes (absolute Visio coords) of legend lanes
    if (lanes.length > 0) {
      for (let i = 0; i < lanes.length; i++) {
        const { el: s, abs, id: laneId } = lanes[i];
        const bandH = Math.round(Math.max(80, abs.h * SCALE));

        let label = '';
        for (const c of s.childNodes)
          if (c.nodeType === 1 && c.localName === 'Text') { label = c.textContent.trim(); break; }
        // Visio CFF swimlanes store heading in User.visHeadingText cell value (not <Text>)
        if (!label) {
          const userSect = vEl(s, 'Section');
          if (userSect && userSect.getAttribute('N') === 'User') {
            for (const row of vAll(userSect, 'Row')) {
              if (row.getAttribute('N') === 'visHeadingText') {
                const cell = vEl(row, 'Cell');
                if (cell && cell.getAttribute('N') === 'Value') { label = cell.getAttribute('V') || ''; break; }
              }
            }
          }
        }
        // Fallback: check User section anywhere in shape children
        if (!label) {
          for (const sect of s.getElementsByTagName('Section')) {
            if (sect.getAttribute('N') !== 'User') continue;
            for (const row of vAll(sect, 'Row')) {
              if (row.getAttribute('N') === 'visHeadingText') {
                const cell = vEl(row, 'Cell');
                if (cell && cell.getAttribute('N') === 'Value') { label = cell.getAttribute('V') || ''; break; }
              }
            }
            if (label) break;
          }
        }
        if (!label) {
          const childEl = vEl(s, 'Shapes');
          if (childEl) {
            for (const child of vAll(childEl, 'Shape')) {
              if (child.getAttribute('Type') === 'Group') continue;
              const t = vText(child);
              if (t && t.length > 0 && t.length < 100) { label = t; break; }
            }
          }
        }

        let fill = vCell(s, 'FillForegnd');
        if (isWashedOut(fill)) {
          const childEl = vEl(s, 'Shapes');
          if (childEl) {
            for (const child of vAll(childEl, 'Shape')) {
              if (child.getAttribute('Type') === 'Group') continue;
              const cf = vCell(child, 'FillForegnd');
              if (cf && cf.startsWith('#') && !isWashedOut(cf)) { fill = cf; break; }
            }
          }
        }
        // Skip legend swimlanes — store their bounding box for spatial filtering
        if (/l[eé]gende?|legend/i.test(label)) {
          legendBounds.push({
            xMin: abs.pinX - abs.w/2, xMax: abs.pinX + abs.w/2,
            yMin: abs.pinY - abs.h/2, yMax: abs.pinY + abs.h/2,
          });
          continue;
        }
        const bandIdx = newBands.length + 1;
        const color = !isWashedOut(fill) ? fill : FALLBACK_COLORS[bandIdx % FALLBACK_COLORS.length];
        newBands.push({ id: bandIdx, label: label || `Bande ${bandIdx}`, color, fontSize: 22, height: bandH });
      }
    } else {
      newBands.push({ id: 1, label: 'Activités', color: '#22c55e', fontSize: 22, height: 500 });
    }

    // Spatial legend filter: skip shapes whose center falls within a legend lane's bounding box
    function isInLegend(id) {
      if (legendBounds.length === 0) return false;
      const a = shapePinAbs[id];
      if (!a) return false;
      for (const b of legendBounds) {
        if (a.pinX > b.xMin && a.pinX < b.xMax && a.pinY > b.yMin && a.pinY < b.yMax) return true;
      }
      return false;
    }

    // ── Detect Visio Containers (transparent group boxes) ─────
    // These are semi-transparent labeled shapes that visually wrap activities
    // but are NOT XML parents — membership is determined by bounding-box overlap
    const containerGroupIds  = new Set();
    const containerGroupData = []; // { id, label, abs }
    for (const { el: s, id } of allShapes) {
      if (connectorIds.has(id) || containerIds.has(id)) continue;
      // Losanges et ellipses ne sont jamais des conteneurs de groupe
      const mid_cg = s.getAttribute('Master');
      const mInfo_cg = masterInfoCache[mid_cg] || {};
      if (mInfo_cg.isDiamond || mInfo_cg.isEllipse) continue;
      const ft = parseFloat(vCell(s, 'FillForegndTrans') || '0');
      const bt = parseFloat(vCell(s, 'FillBkgndTrans')   || '0');
      if (Math.max(ft, bt) < 0.4) continue; // not transparent enough
      const abs = shapePinAbs[id] || {};
      if (!abs.w || !abs.h || abs.w < 1 || abs.h < 0.5) continue;
      if (abs.w > pageMaxW * 0.9) continue; // full-page wide → lane, not a group container
      const label = vText(s);
      if (!label || label.length > 80) continue;
      containerGroupIds.add(id);
      containerGroupData.push({ id, label, abs }); // id = Visio ID du container
    }

    // ── Activités ─────────────────────────────────────────────
    setStatus('Import des activités…');
    const newShapes  = [];
    const shapeIdMap = {};
    let nextOid      = (Date.now() % 1e7) | 0;
    const totalBandH = newBands.reduce((s, b) => s + b.height, 0);

    for (const { el: s, id } of allShapes) {
      if (connectorIds.has(id))      continue;
      if (containerIds.has(id))      continue;
      if (containerGroupIds.has(id)) continue; // transparent container → becomes a group, not an activity
      if (isInLegend(id))            continue; // skip shapes inside legend lane (spatial filter)

      const mid   = s.getAttribute('Master');
      const vType = s.getAttribute('Type');
      if (!mid && vType !== 'Group') continue;

      const mn = (masterIdToName[mid] || '').toLowerCase();
      if (/\b(connector|dynamic connector|line|arrow)\b/.test(mn)) continue;
      if (/^(title|text|annotation|callout|note|border|background|frame)$/.test(mn)) continue;

      const abs = shapePinAbs[id] || {};
      const vW  = abs.w || 0;
      const vH  = abs.h || 0;
      if (vW < 0.2 || vH < 0.1) continue;
      if (vW > 6   || vH > 4  ) continue;

      const screenX = Math.round((abs.pinX - vW/2 - leftEdge) * SCALE);
      const screenY = Math.max(0, Math.round((topOfDiagram - abs.pinY - vH/2) * SCALE));
      if (screenY > totalBandH + 100) continue; // hors du diagramme

      const screenW = Math.round(vW * SCALE);
      const screenH = Math.round(vH * SCALE);

      const mInfoForType = masterInfoCache[mid] || {};
      const shapeType = detectVSDXShapeType(masterIdToName[mid], vType, mInfoForType.isEllipse, mInfoForType.isDiamond, mInfoForType.isSubprocess);
      const oid = nextOid++;
      shapeIdMap[id] = oid;
      newShapes.push({
        id: oid, type: shapeType, subtype: 'normal',
        x: screenX, y: screenY, w: screenW, h: screenH,
        label:          vText(s),
        color:          shapeType === 'decision' ? '#9ca3af' : '#22c55e',
        textColor:      '#ffffff',
        strokeColor:    '',
        fontSize:       18,
        validationBadge: false,
        validationColor: '#4DB868',
        colorVariant:   0,
      });
    }

    if (newShapes.length === 0) {
      setStatus('Aucune activité trouvée dans ce fichier.', true);
      return;
    }

    // ── Groups from Visio Containers ──────────────────────────
    const newGroups   = [];
    const groupIdMap  = {}; // Visio container ID → app group ID
    for (const { id: visioContId, label, abs } of containerGroupData) {
      // Convert container bounds to screen coordinates
      const cLeft   = (abs.pinX - abs.w/2 - leftEdge) * SCALE;
      const cRight  = (abs.pinX + abs.w/2 - leftEdge) * SCALE;
      const cTop    = Math.max(0, (topOfDiagram - (abs.pinY + abs.h/2)) * SCALE);
      const cBottom = Math.max(0, (topOfDiagram - (abs.pinY - abs.h/2)) * SCALE);
      // Find activities whose center falls inside this container
      const memberIds = newShapes
        .filter(s => {
          const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
          return cx > cLeft && cx < cRight && cy > cTop && cy < cBottom;
        })
        .map(s => s.id);
      if (memberIds.length < 2) continue;
      const gid = nextOid++;
      groupIdMap[visioContId] = gid; // permet de retrouver l'app-ID depuis le Visio-ID
      newGroups.push({ id: gid, label, shapeIds: memberIds, color: '#b3a0ff' });
    }

    // ── Épissage spatial des losanges décorateurs ──────────────
    // Certains losanges Visio n'ont aucun <Connect> et sont posés visuellement
    // sur un connecteur. Pour chaque tel losange D, on cherche les connecteurs
    // A→B dont la droite passe à moins de 0.6 inch du centre de D, puis on
    // remplace A→B par A→D + D→B (avec t ∈ [0.05, 0.95] pour éviter les extrémités).
    {
      const SPLICE_THRESH = 0.6; // inches Visio

      const connSrcSet = new Set(Object.values(connMap).map(e => e.source).filter(Boolean));
      const connTgtSet = new Set(Object.values(connMap).map(e => e.target).filter(Boolean));

      const decisionsToPatch = [];
      for (const [visioId, appId] of Object.entries(shapeIdMap)) {
        const appShape = newShapes.find(s => s.id === appId);
        if (!appShape || appShape.type !== 'decision') continue;
        if (connSrcSet.has(visioId) || connTgtSet.has(visioId)) continue; // déjà connecté
        const abs = shapePinAbs[visioId];
        if (!abs) continue;
        decisionsToPatch.push({ visioId, pinX: abs.pinX, pinY: abs.pinY });
      }

      let synCtr = 0;
      for (const dec of decisionsToPatch) {
        const Dx = dec.pinX, Dy = dec.pinY;
        // Snapshot des entrées réelles (pas les synthétiques déjà créées ce tour)
        const realEntries = Object.entries(connMap).filter(([, e]) => !e._origConnId);
        for (const [connId, ends] of realEntries) {
          const sv = ends.source, tv = ends.target;
          if (!sv || !tv || sv === dec.visioId || tv === dec.visioId) continue;
          const sAbs = shapePinAbs[sv], tAbs = shapePinAbs[tv];
          if (!sAbs || !tAbs) continue;
          const Ax = sAbs.pinX, Ay = sAbs.pinY;
          const Bx = tAbs.pinX, By = tAbs.pinY;
          const ABx = Bx - Ax, ABy = By - Ay;
          const len2 = ABx*ABx + ABy*ABy;
          if (len2 < 1e-9) continue;
          const t = ((Dx - Ax)*ABx + (Dy - Ay)*ABy) / len2;
          if (t < 0.05 || t > 0.95) continue;
          const px = Ax + t*ABx, py = Ay + t*ABy;
          if (Math.hypot(Dx - px, Dy - py) >= SPLICE_THRESH) continue;
          // Épisser : A→B devient A→D puis D→B
          delete connMap[connId];
          connMap[`__sp${synCtr++}`] = { source: sv,          target: dec.visioId };
          connMap[`__sp${synCtr++}`] = { source: dec.visioId, target: tv, _origConnId: connId };
        }
      }
    }

    // ── Connections ───────────────────────────────────────
    const newConns = [];
    for (const [connId, ends] of Object.entries(connMap)) {
      const { source: sv, target: tv } = ends;
      if (!sv || !tv) continue;
      // Résoudre source et cible : forme ordinaire OU groupe Visio container
      const fromId = shapeIdMap[sv] || groupIdMap[sv];
      const toId   = shapeIdMap[tv] || groupIdMap[tv];
      if (!fromId || !toId) continue;
      const srcShape = newShapes.find(s => s.id === fromId)
                    || newGroups.find(g => g.id === fromId);
      // Pour les connecteurs synthétiques (épissage losange), _origConnId pointe
      // vers l'élément Visio original afin de récupérer label + style.
      const connItem = shapeMap[ends._origConnId || connId];
      const connLabel = connItem ? (vText(connItem.el) || '') : '';
      // LinePattern 1=solid, >1 = dashed (cherche dans l'élément puis dans le master)
      const connMid = connItem ? connItem.el.getAttribute('Master') : null;
      const masterLp = connMid ? (await getMasterInfo(connMid)).linePattern : 1;
      const linePatternStr = connItem ? (vCellDeep(connItem.el, 'LinePattern') || String(masterLp)) : '1';
      const isDashed = parseInt(linePatternStr) > 1;
      newConns.push({
        id:       nextOid++,
        fromId,
        toId,
        fromPort: 'right',
        toPort:   'left',
        color:    srcShape ? srcShape.color : '#567460',
        label:    connLabel,
        style:    isDashed ? 'dashed' : 'solid',
        routing:  'orthogonal',
      });
    }

    // ── Supprimer les bandes séparateurs vides (label = chiffre seul) ──
    setStatus('Nettoyage des bandes séparateurs…');
    {
      // Construire les plages Y initiales
      const bRanges = [];
      { let y0 = 0; for (const b of newBands) { bRanges.push({ y0, y1: y0+b.height, band: b }); y0 += b.height; } }
      // Séparateur = label de type "1", "3", "Bande 1", "BANDE 3", "Band 2"…
      // On filtre uniquement par label (des formes peuvent y atterrir par arrondi Visio
      // mais elles seront recadrées par la passe de vérification qui suit)
      const SEP_RE = /^(bands?\s+|band[ae]s?\s+|bande?s?\s+)?\d+\s*$/i;
      const toRemove = bRanges.filter(({ band }) => SEP_RE.test(band.label.trim()));
      // Traitement de bas en haut pour éviter les décalages en cascade
      toRemove.sort((a, b) => b.y0 - a.y0);
      for (const { band, y0: bandStart } of toRemove) {
        const h = band.height;
        newBands.splice(newBands.indexOf(band), 1);
        // Remonter les formes dont le centre est sous cette bande
        for (const s of newShapes) {
          if (s.y + s.h/2 >= bandStart + h) s.y -= h;
        }
      }
      newBands.forEach((b, i) => { b.id = i + 1; });
      // Clamp minimal : aucune forme ne peut avoir Y < 0 après décalage
      for (const s of newShapes) { if (s.y < 0) s.y = 0; }
    }

    // ── Détection des formes orphelines (vides + non connectées) ──────
    {
      const connectedIds = new Set([
        ...newConns.map(c => c.fromId),
        ...newConns.map(c => c.toId),
      ]);
      const orphans = newShapes.filter(s =>
        (!s.label || !s.label.trim()) && !connectedIds.has(s.id)
      );

      if (orphans.length > 0) {
        setStatus(`⚠ ${orphans.length} forme(s) vide(s) non connectée(s) détectée(s).`);
        await new Promise(r => setTimeout(r, 0));

        const choice = await new Promise(resolve => {
          const ov = document.createElement('div');
          ov.className = 'modal-overlay';
          ov.style.zIndex = '10000';
          const types = [...new Set(orphans.map(s =>
            s.type === 'decision' ? 'losange' : s.type === 'start-end' ? 'ellipse' : 'activité'
          ))].join(', ');
          ov.innerHTML = `
            <div class="modal-card" style="max-width:430px;border-top:3px solid var(--pink)">
              <div class="modal-header">
                <h2 style="color:var(--pink)">
                  <i class="fa-solid fa-triangle-exclamation" style="margin-right:8px;opacity:0.9"></i>Fichier incomplet
                </h2>
              </div>
              <div class="modal-body" style="display:flex;flex-direction:column;gap:14px">
                <p style="font-size:13px;color:var(--text-muted);margin:0;line-height:1.6">
                  Ce fichier contient <strong style="color:var(--green-lt)">${orphans.length} forme(s)</strong>
                  sans texte et sans connexion (${types}).<br>
                  <span style="font-size:12px;color:rgba(255,255,255,0.35)">Ces éléments sont probablement des artefacts Visio sans contenu.</span>
                </p>
                <p style="font-size:12px;color:rgba(255,255,255,0.38);margin:0">
                  Voulez-vous nettoyer ces éléments ou fournir un fichier corrigé&nbsp;?
                </p>
                <div style="display:flex;flex-direction:column;gap:7px">
                  <button id="_orph-clean" class="btn-ok" style="width:100%;text-align:left;display:flex;align-items:center;gap:9px;padding:11px 14px;border-radius:10px">
                    <i class="fa-solid fa-broom"></i> Nettoyer et continuer l'import
                  </button>
                  <button id="_orph-keep" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);color:var(--text-muted);border-radius:10px;padding:10px 14px;font-size:12px;font-weight:600;cursor:pointer;text-align:left;display:flex;align-items:center;gap:9px;font-family:inherit;width:100%">
                    <i class="fa-solid fa-forward"></i> Continuer sans nettoyer
                  </button>
                  <button id="_orph-cancel" style="background:transparent;border:none;color:rgba(244,184,208,0.5);padding:8px 14px;font-size:11px;cursor:pointer;text-align:left;display:flex;align-items:center;gap:9px;font-family:inherit;width:100%">
                    <i class="fa-solid fa-xmark"></i> Annuler — je vais corriger mon fichier
                  </button>
                </div>
              </div>
            </div>`;
          document.body.appendChild(ov);
          ov.querySelector('#_orph-clean').onclick  = () => { ov.remove(); resolve('clean'); };
          ov.querySelector('#_orph-keep').onclick   = () => { ov.remove(); resolve('keep'); };
          ov.querySelector('#_orph-cancel').onclick = () => { ov.remove(); resolve('cancel'); };
        });

        if (choice === 'cancel') {
          setStatus('Import annulé. Vous pouvez déposer un fichier corrigé.', true);
          return;
        }
        if (choice === 'clean') {
          const orphanIds = new Set(orphans.map(s => s.id));
          orphans.forEach(s => newShapes.splice(newShapes.indexOf(s), 1));
          // Retirer aussi ces formes des groupes
          for (const g of newGroups) {
            if (g.shapeIds) g.shapeIds = g.shapeIds.filter(id => !orphanIds.has(id));
          }
          setStatus(`${orphans.length} forme(s) nettoyée(s). Poursuite de l'import…`);
          await new Promise(r => setTimeout(r, 0));
        }
      }
    }

    // ── Vérification itérative : sans chevauchement, bandes adaptées ──
    setStatus('Vérification finale (résolution des chevauchements)…');
    await new Promise(r => setTimeout(r, 0));
    {
      const PAD = 12;
      let bandRanges = [];

      function _rebuildRanges() {
        bandRanges = [];
        let y0 = 0;
        for (const band of newBands) { bandRanges.push({ y0, y1: y0+band.height }); y0 += band.height; }
      }
      function _getBandIdx(s) {
        const mid = s.y + s.h/2;
        for (let i = 0; i < bandRanges.length; i++)
          if (mid >= bandRanges[i].y0 && mid < bandRanges[i].y1) return i;
        return -1;
      }
      function _clamp() {
        let y0 = 0;
        for (const band of newBands) {
          for (const s of newShapes) {
            const m = s.y + s.h/2;
            if (m >= y0 && m < y0+band.height) {
              if (s.y < y0+8) s.y = y0+8;
              if (s.y+s.h > y0+band.height-8) s.y = Math.max(y0+8, y0+band.height-8-s.h);
            }
          }
          y0 += band.height;
        }
      }
      function _stretch() {
        let grew = false;
        let y0 = 0;
        for (const band of newBands) {
          const bot = newShapes
            .filter(s => { const m = s.y+s.h/2; return m >= y0 && m < y0+band.height; })
            .reduce((m, s) => Math.max(m, s.y+s.h), 0);
          if (bot + 20 > y0 + band.height) { band.height = Math.round(bot + 20 - y0); grew = true; }
          y0 += band.height;
        }
        return grew;
      }
      function _hasOverlap() {
        for (let i = 0; i < newShapes.length; i++) {
          for (let j = i+1; j < newShapes.length; j++) {
            const a = newShapes[i], b = newShapes[j];
            const ovX = Math.min(a.x+a.w, b.x+b.w) - Math.max(a.x, b.x) + PAD;
            const ovY = Math.min(a.y+a.h, b.y+b.h) - Math.max(a.y, b.y) + PAD;
            if (ovX > 0 && ovY > 0) return true;
          }
        }
        return false;
      }

      _rebuildRanges();

      for (let round = 0; round < 8; round++) {
        // Passe anti-chevauchement (jusqu'à 200 itérations ou stabilité)
        for (let iter = 0; iter < 200; iter++) {
          let moved = false;
          for (let i = 0; i < newShapes.length; i++) {
            for (let j = i+1; j < newShapes.length; j++) {
              const a = newShapes[i], b = newShapes[j];
              const ovX = Math.min(a.x+a.w, b.x+b.w) - Math.max(a.x, b.x) + PAD;
              const ovY = Math.min(a.y+a.h, b.y+b.h) - Math.max(a.y, b.y) + PAD;
              if (ovX <= 0 || ovY <= 0) continue;
              const bandA = _getBandIdx(a), bandB = _getBandIdx(b);
              const sameBand = bandA === bandB && bandA !== -1;
              if (sameBand || ovX <= ovY) {
                const half = ovX / 2;
                if (a.x + a.w/2 <= b.x + b.w/2) { a.x -= half; b.x += half; }
                else { a.x += half; b.x -= half; }
              } else {
                const half = ovY / 2;
                if (a.y + a.h/2 <= b.y + b.h/2) { a.y -= half; b.y += half; }
                else { a.y += half; b.y -= half; }
              }
              a.x = Math.max(INDEX_W_SVG + 4, a.x);
              b.x = Math.max(INDEX_W_SVG + 4, b.x);
              moved = true;
            }
          }
          _clamp();
          if (!moved) break;
        }

        const grew = _stretch();
        _clamp();
        _rebuildRanges();

        // Stable et propre → terminé
        if (!grew && !_hasOverlap()) break;

        // Laisser le navigateur respirer entre les rounds lourds
        await new Promise(r => setTimeout(r, 0));
      }
    }

    // ── Dénouage des bandes denses (minimisation croisements + virages) ──
    // Algo : warm-up barycentre (10 passes) + recuit simulé sur l'ordre X des formes
    setStatus('Analyse des zones denses…');
    await new Promise(r => setTimeout(r, 0));
    {
      // Recalculer les plages Y après vérification
      const bRangesU = [];
      { let y0 = 0; for (const b of newBands) { bRangesU.push({ y0, y1: y0+b.height }); y0 += b.height; } }

      const shapeByIdU = {};
      for (const s of newShapes) shapeByIdU[s.id] = s;

      // X effectif d'un endpoint (forme ou groupe)
      function epX(id) {
        const s = shapeByIdU[id]; if (s) return s.x + s.w/2;
        const g = newGroups && newGroups.find(g => g.id === id);
        if (g) {
          const mem = newShapes.filter(s => g.shapeIds && g.shapeIds.includes(s.id));
          if (mem.length) return mem.reduce((a, t) => a + t.x + t.w/2, 0) / mem.length;
        }
        return null;
      }

      const bandShapesU = newBands.map((b, i) =>
        newShapes.filter(s => { const m = s.y + s.h/2; return m >= bRangesU[i].y0 && m < bRangesU[i].y1; })
      );
      const avgU = newShapes.length / Math.max(newBands.length, 1);
      // Seuil "bande dense" : au-dessus de la moyenne (au moins 3 formes)
      const HEAVY_U = Math.max(3, Math.ceil(avgU));
      const bandWU = Math.max(1400, newShapes.reduce((m, s) => Math.max(m, s.x + s.w), 0) + 300);

      for (let bi = 0; bi < newBands.length; bi++) {
        const inBand = bandShapesU[bi];
        if (inBand.length < HEAVY_U) continue;

        const bandIdsU = new Set(inBand.map(s => s.id));
        // Connexions impliquant au moins une forme de cette bande (les deux extrémités doivent exister)
        const relC = newConns.filter(c =>
          (bandIdsU.has(c.fromId) || bandIdsU.has(c.toId)) &&
          shapeByIdU[c.fromId] && shapeByIdU[c.toId]
        );
        if (relC.length < 2) continue;

        setStatus(`Dénouage "${newBands[bi].label}" — ${inBand.length} formes, ${relC.length} connexions…`);
        await new Promise(r => setTimeout(r, 0));

        // Calcul de la largeur disponible et espacement entre formes
        const PAD_U = INDEX_W_SVG + 20;
        const totalWU = inBand.reduce((a, s) => a + s.w, 0);
        const gapU = Math.max(16, (bandWU - PAD_U - 20 - totalWU) / (inBand.length + 1));

        // Appliquer un ordre (tableau d'indices dans inBand) → met à jour s.x
        function applyOrdU(ord) {
          let cx = PAD_U + gapU;
          for (const idx of ord) { inBand[idx].x = Math.round(cx); cx += inBand[idx].w + gapU; }
        }

        // Coût : croisements (×500) + déplacement horizontal
        function costU() {
          const xs = {};
          for (const c of relC) {
            if (xs[c.fromId] === undefined) xs[c.fromId] = epX(c.fromId);
            if (xs[c.toId]   === undefined) xs[c.toId]   = epX(c.toId);
          }
          let cost = 0;
          for (const c of relC) {
            const fx = xs[c.fromId], tx = xs[c.toId];
            if (fx != null && tx != null) cost += Math.abs(fx - tx);
          }
          for (let i = 0; i < relC.length; i++) {
            for (let j = i + 1; j < relC.length; j++) {
              const fi = xs[relC[i].fromId], ti = xs[relC[i].toId];
              const fj = xs[relC[j].fromId], tj = xs[relC[j].toId];
              if (fi == null || ti == null || fj == null || tj == null) continue;
              if (Math.abs(fi - fj) < 1 || Math.abs(ti - tj) < 1) continue;
              if ((fi < fj) !== (ti < tj)) cost += 500; // pénalité croisement
            }
          }
          return cost;
        }

        // Ordre initial : tri par X courant
        let ordU = inBand.map((_, i) => i).sort((a, b) => inBand[a].x - inBand[b].x);
        applyOrdU(ordU);

        // === Warm-up : barycentre (10 passes) ===
        for (let iter = 0; iter < 10; iter++) {
          const gravs = inBand.map((s, i) => {
            let sum = 0, w = 0;
            for (const c of relC) {
              let othId = null, wt = 1;
              if (c.fromId === s.id) { othId = c.toId;   wt = bandIdsU.has(othId) ? 0.5 : 2; }
              else if (c.toId === s.id) { othId = c.fromId; wt = bandIdsU.has(othId) ? 0.5 : 2; }
              if (othId != null) { const ox = epX(othId); if (ox != null) { sum += ox * wt; w += wt; } }
            }
            return [i, w > 0 ? sum / w : s.x + s.w/2];
          });
          gravs.sort((a, b) => a[1] - b[1]);
          ordU = gravs.map(g => g[0]);
          applyOrdU(ordU);
        }

        // === Recuit simulé : minimise croisements ===
        let curCostU = costU();
        let T = 3000, TMIN = 0.5, COOL = 0.9994;
        const NU = inBand.length;

        while (T > TMIN) {
          const i = (Math.random() * NU) | 0;
          const j = (Math.random() * NU) | 0;
          if (i === j) { T *= COOL; continue; }
          // Échanger les positions dans l'ordre
          [ordU[i], ordU[j]] = [ordU[j], ordU[i]];
          applyOrdU(ordU);
          const nc = costU();
          const delta = nc - curCostU;
          if (delta <= 0 || Math.random() < Math.exp(-delta / T)) {
            curCostU = nc;
          } else {
            [ordU[i], ordU[j]] = [ordU[j], ordU[i]]; // annuler
            applyOrdU(ordU);
          }
          T *= COOL;
        }

        await new Promise(r => setTimeout(r, 0));
      }

      // Clamp X minimal après réordonnancement
      for (const s of newShapes) { if (s.x < INDEX_W_SVG + 4) s.x = INDEX_W_SVG + 4; }
    }

    // ── Assignation des ports (alignement → flèche droite) ───────
    setStatus('Assignation des points de connexion…');
    await new Promise(r => setTimeout(r, 0));
    {
      const OPP_DIR = { right:'left', left:'right', top:'bottom', bottom:'top' };
      const PREFER  = {
        right:  ['right','bottom','top','left'],
        left:   ['left','top','bottom','right'],
        bottom: ['bottom','right','left','top'],
        top:    ['top','left','right','bottom'],
      };
      const ALIGN_PX = 18; // seuil d'alignement pour flèche droite

      const sideUsed = new Map();
      function shapeUsage(id) {
        if (!sideUsed.has(id)) sideUsed.set(id, { right:0, left:0, top:0, bottom:0 });
        return sideUsed.get(id);
      }

      // Mémorise la direction assignée pour chaque paire (A↔B) → même bundle si connexions multiples
      const pairUsed = new Map();

      function resolvePortShape(id) {
        const s = newShapes.find(s => s.id === id);
        if (s) return s;
        const g = newGroups.find(g => g.id === id);
        if (!g) return null;
        const members = newShapes.filter(s => g.shapeIds.includes(s.id));
        if (!members.length) return null;
        const xs = members.flatMap(s => [s.x, s.x+s.w]);
        const ys = members.flatMap(s => [s.y, s.y+s.h]);
        const GPAD = 22, GLBL = 24;
        return { x: Math.min(...xs)-GPAD, y: Math.min(...ys)-GPAD-GLBL,
                 w: Math.max(...xs)-Math.min(...xs)+GPAD*2,
                 h: Math.max(...ys)-Math.min(...ys)+GPAD*2+GLBL, type:'group' };
      }

      function assignPort(conn) {
        const fs = resolvePortShape(conn.fromId);
        const ts = resolvePortShape(conn.toId);
        if (!fs || !ts) return;
        const fcx = fs.x + fs.w/2, fcy = fs.y + fs.h/2;
        const tcx = ts.x + ts.w/2, tcy = ts.y + ts.h/2;
        const dx = tcx - fcx, dy = tcy - fcy;
        const fu = shapeUsage(conn.fromId);
        const tu = shapeUsage(conn.toId);

        // ── Détection d'alignement → flèche droite sans coude ──
        // Alignement horizontal : mêmes centres Y → ports droite/gauche → ligne horizontale
        if (Math.abs(dy) < ALIGN_PX && Math.abs(dx) > 1) {
          const dir = dx >= 0 ? 'right' : 'left';
          fu[dir]++;
          tu[OPP_DIR[dir]]++;
          conn.fromPortDir = dir;
          conn.toPortDir   = OPP_DIR[dir];
          return;
        }
        // Alignement vertical : mêmes centres X → ports haut/bas → ligne verticale
        if (Math.abs(dx) < ALIGN_PX && Math.abs(dy) > 1) {
          const dir = dy >= 0 ? 'bottom' : 'top';
          fu[dir]++;
          tu[OPP_DIR[dir]]++;
          conn.fromPortDir = dir;
          conn.toPortDir   = OPP_DIR[dir];
          return;
        }

        // ── Même paire (A↔B) : forcer le même côté pour bundler les connexions parallèles ──
        // Évite qu'une 2ᵉ connexion entre A et B parte dans la direction inverse (chemin complexe)
        const pairKey = conn.fromId < conn.toId
          ? `${conn.fromId}↔${conn.toId}`
          : `${conn.toId}↔${conn.fromId}`;
        if (pairUsed.has(pairKey)) {
          const prev = pairUsed.get(pairKey);
          // Adapter la direction selon quel bout on traite (from ou to de la connexion mémorisée)
          const dir = prev.firstFromId === conn.fromId ? prev.dir : OPP_DIR[prev.dir];
          fu[dir]++;
          tu[OPP_DIR[dir]]++;
          conn.fromPortDir = dir;
          conn.toPortDir   = OPP_DIR[dir];
          return;
        }

        // ── Cas général : direction naturelle + forte pénalité pour direction inverse ──
        const nat = Math.abs(dx) >= Math.abs(dy)
          ? (dx >= 0 ? 'right' : 'left')
          : (dy >= 0 ? 'bottom' : 'top');
        const backward = OPP_DIR[nat]; // pointe à l'opposé de la cible → à éviter fortement
        const candidates = (fs.type === 'decision' || ts.type === 'decision')
          ? ['right','bottom','left','top'] : PREFER[nat];
        let bestDir = nat, bestScore = Infinity;
        for (const dir of candidates) {
          let score = fu[dir] + tu[OPP_DIR[dir]];
          if (dir === backward) score += 8; // pénalité : direction inverse = dernier recours
          if (score < bestScore) { bestScore = score; bestDir = dir; if (score === 0) break; }
        }
        fu[bestDir]++;
        tu[OPP_DIR[bestDir]]++;
        conn.fromPortDir = bestDir;
        conn.toPortDir   = OPP_DIR[bestDir];

        // Mémoriser pour cohérence si d'autres connexions relient la même paire
        pairUsed.set(pairKey, { dir: bestDir, firstFromId: conn.fromId });
      }

      newConns.filter(c => c.style !== 'dashed').forEach(assignPort);
      newConns.filter(c => c.style === 'dashed').forEach(assignPort);

      // ── Vérification surcharge : côté avec > 3 connexions → redistribuer ──
      // On recompte les connexions par (shapeId, direction) et on réassigne
      // les connexions en excès vers le côté adjacent le moins chargé
      const SIDE_MAX = 3;
      const OPP2 = OPP_DIR;
      const ALL_DIRS = ['right', 'left', 'bottom', 'top'];
      // Compter par (shapeId, dir) pour fromPortDir
      const fromCount = new Map(); // "shapeId-dir" → [conn, ...]
      for (const c of newConns) {
        if (!c.fromPortDir) continue;
        const key = `${c.fromId}-${c.fromPortDir}`;
        if (!fromCount.has(key)) fromCount.set(key, []);
        fromCount.get(key).push(c);
      }
      for (const [key, group] of fromCount) {
        if (group.length <= SIDE_MAX) continue;
        const dashIdx = key.lastIndexOf('-');
        const shapeIdNum = parseInt(key.slice(0, dashIdx));
        const dir = key.slice(dashIdx + 1);
        const fs = resolvePortShape(shapeIdNum);
        if (!fs) continue;
        // Excédent = conns au-delà du max → on essaie de les déplacer sur un autre côté
        const excess = group.slice(SIDE_MAX);
        for (const c of excess) {
          const ts = resolvePortShape(c.toId);
          if (!ts) continue;
          // Choisir le côté le moins utilisé parmi les alternatives (hors côté actuel)
          const altDirs = ALL_DIRS.filter(d => d !== dir && d !== OPP2[dir]);
          let bestAlt = null, bestCnt = Infinity;
          for (const d of altDirs) {
            const cnt = (fromCount.get(`${shapeIdNum}-${d}`) || []).length;
            if (cnt < bestCnt) { bestCnt = cnt; bestAlt = d; }
          }
          if (bestAlt && bestCnt < group.length) {
            // Mettre à jour les maps
            const oldArr = fromCount.get(key);
            oldArr.splice(oldArr.indexOf(c), 1);
            const newKey = `${shapeIdNum}-${bestAlt}`;
            if (!fromCount.has(newKey)) fromCount.set(newKey, []);
            fromCount.get(newKey).push(c);
            c.fromPortDir = bestAlt;
            c.toPortDir   = OPP2[bestAlt];
          }
        }
      }
    }

    // ── Apply to state ────────────────────────────────────
    clearSelection();
    state.shapes      = newShapes;
    state.connections = newConns;
    state.groups      = newGroups;
    state.bands       = newBands;
    state.bandWidth   = Math.max(1400, Math.round(newShapes.reduce((m, s) => Math.max(m, s.x + s.w), 0) + 300));
    state.nextId      = nextOid + 1;

    state.shapes.forEach(s => updateShapeColor(s));
    state.connections.forEach(c => {
      const from = state.shapes.find(s => s.id === c.fromId);
      if (from) c.color = from.color;
    });

    history = [JSON.stringify(state)]; histIndex = 0;
    render(); fitView(); updateProps();

    document.getElementById('vsdx-dialog').classList.add('hidden');
    setStatus('');
    showToast(`Import réussi — ${newShapes.length} activités · ${newConns.length} connexions · ${newBands.length} bandes${newGroups.length ? ` · ${newGroups.length} groupe${newGroups.length>1?'s':''}` : ''}`);

  } catch(err) {
    console.error('VSDX import error:', err);
    setStatus('Erreur : ' + err.message, true);
  }
}

/* ══════════════════════════════════════════════════
   BANDS DIALOG
   ══════════════════════════════════════════════════ */

function openBandsDialog() {
  document.getElementById('bands-dialog').classList.remove('hidden');
  renderBandsList();
}

function renderBandsList() {
  const list = document.getElementById('bands-list');
  list.innerHTML = '';

  state.bands.forEach((band, i) => {
    const row = document.createElement('div');
    row.className = 'band-row';
    row.innerHTML = `
      <input type="color" value="${band.color}" class="bc" data-i="${i}" title="Couleur vivid">
      <input type="text"  value="${band.label}" placeholder="Label…" class="bl" data-i="${i}">
      <input type="number" value="${band.height}" min="60" max="800" step="20" class="bh" data-i="${i}" title="Hauteur (px)">
      <span class="band-label-extra">px</span>
      <button class="band-delete" data-i="${i}" title="Supprimer">×</button>
    `;
    list.appendChild(row);
  });

  list.querySelectorAll('.bc').forEach(e => e.addEventListener('input', ev => {
    state.bands[ev.target.dataset.i].color = ev.target.value; renderBands();
  }));
  list.querySelectorAll('.bl').forEach(e => e.addEventListener('input', ev => {
    state.bands[ev.target.dataset.i].label = ev.target.value; renderBands();
  }));
  list.querySelectorAll('.bh').forEach(e => e.addEventListener('input', ev => {
    state.bands[ev.target.dataset.i].height = parseInt(ev.target.value) || 150; renderBands();
  }));
  list.querySelectorAll('.band-delete').forEach(e => e.addEventListener('click', ev => {
    state.bands.splice(parseInt(ev.target.dataset.i), 1);
    renderBandsList(); renderBands();
  }));
}

/* ══════════════════════════════════════════════════
   TOAST
   ══════════════════════════════════════════════════ */

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._tid);
  t._tid = setTimeout(() => t.classList.remove('show'), 2200);
}

/* ══════════════════════════════════════════════════
   BAND PROPERTIES BINDING
   ══════════════════════════════════════════════════ */

function bindBandProps() {
  const bprop = (id, fn) => {
    const el = document.getElementById(id);
    el.addEventListener('input', e => { fn(e.target.value); render(); });
    el.addEventListener('change', snapshot);
  };
  bprop('band-label', v => { const b = state.bands.find(b => b.id === selectedBand); if (b) b.label = v; });
  bprop('band-color', v => {
    const b = state.bands.find(b => b.id === selectedBand);
    if (!b) return;
    b.color = v;
    const pastelEl = document.getElementById('band-pastel-preview');
    if (pastelEl) pastelEl.style.background = bandPastel(v);
    state.shapes.forEach(s => { if (getBandForY(s.y + s.h / 2)?.id === b.id) updateShapeColor(s); });
  });
  bprop('band-font-size', v => {
    const b = state.bands.find(b => b.id === selectedBand);
    if (b) b.fontSize = Math.max(8, Math.min(24, parseInt(v) || 11));
  });
  bprop('band-height', v => {
    const b = state.bands.find(b => b.id === selectedBand);
    if (b) b.height = Math.max(60, parseInt(v) || 150);
  });
  document.getElementById('prop-delete-band').addEventListener('click', () => {
    if (selectedBand === null) return;
    state.bands = state.bands.filter(b => b.id !== selectedBand);
    selectedBand = null;
    snapshot(); render(); updateProps();
    showToast('Bande supprimée');
  });
}

/* ══════════════════════════════════════════════════
   PANEL COLLAPSE / EXPAND
   ══════════════════════════════════════════════════ */

/* ── StaggeredMenu-style panel open animation ─────────────
   Sequence (faithful to react-bits StaggeredMenu):
   1. Pre-layers (2 green color passes) sweep in with the panel
   2. Panel slides in behind the color layers
   3. Color layers wipe out revealing dark panel
   4. Items rise from below with rotation stagger (yPercent 140 + rotate)
   ─────────────────────────────────────────────────────── */

let _panelAnimCancels = {}; // track cancellation per panel

function _animatePanelOpen(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;

  const isRight = panelId === 'properties';
  const exitDir = isRight ? '102%' : '-102%'; // layers sweep out in the same direction as their initial hidden position

  // Cancel pending timers for this panel
  const prev = _panelAnimCancels[panelId] || [];
  prev.forEach(clearTimeout);
  _panelAnimCancels[panelId] = [];

  const T = id => { _panelAnimCancels[panelId].push(id); };

  // ── 1. Reset pre-layers to covering position (translateX: 0) ──
  const layers = Array.from(panel.querySelectorAll('.panel-prelayer'));
  layers.forEach(l => {
    l.style.transition = 'none';
    l.style.transform = 'translateX(0)';
  });

  // Force reflow
  void panel.offsetWidth;

  // ── 3. After panel slides in (CSS: 0.35s), begin wipe ──
  // Layer 2 (top, solid green) wipes out first
  T(setTimeout(() => {
    if (layers[1]) {
      layers[1].style.transition = 'transform 0.42s cubic-bezier(0.7, 0, 0.95, 1)';
      layers[1].style.transform = `translateX(${exitDir})`;
    }
  }, 300));

  // Layer 1 (lighter green, below) wipes out 65ms later
  T(setTimeout(() => {
    if (layers[0]) {
      layers[0].style.transition = 'transform 0.42s cubic-bezier(0.7, 0, 0.95, 1)';
      layers[0].style.transform = `translateX(${exitDir})`;
    }
  }, 365));

  // ── 4. Items rise with stagger — captured APRÈS updateProps (280ms) ──
  // On capture ici pour éviter que les items soient à opacity:0 AVANT updateProps
  T(setTimeout(() => {
    const items = Array.from(panel.children).filter(
      el => !el.classList.contains('panel-prelayers') && getComputedStyle(el).display !== 'none'
    );
    items.forEach(el => {
      el.style.transition = 'none';
      el.style.transform  = 'translateY(18px)';
      el.style.opacity    = '0';
    });
    void panel.offsetHeight;
    items.forEach((el, i) => {
      const d = i * 45;
      el.style.transition =
        `transform 0.55s cubic-bezier(0.15,0.85,0.45,1) ${d}ms,` +
        `opacity 0.4s ease ${d}ms`;
      el.style.transform = 'none';
      el.style.opacity   = '1';
    });
    const longest = (items.length - 1) * 45 + 550 + 60;
    T(setTimeout(() => {
      items.forEach(el => {
        el.style.transition = '';
        el.style.transform  = '';
        el.style.opacity    = '';
      });
    }, longest));
  }, 280));
}

/* Animation de fermeture (inverse de l'ouverture) */
function _animatePanelClose(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;

  // Annuler les animations d'ouverture en cours
  const prev = _panelAnimCancels[panelId] || [];
  prev.forEach(clearTimeout);
  _panelAnimCancels[panelId] = [];

  // Items : glissent vers le bas + rotation (stagger rapide)
  const items = Array.from(panel.children).filter(
    el => !el.classList.contains('panel-prelayers')
  );
  items.forEach((el, i) => {
    const d = i * 28;
    el.style.transition =
      `transform 0.26s cubic-bezier(0.4,0,1,1) ${d}ms,` +
      `opacity 0.2s ease ${d}ms`;
    el.style.transform = 'translateY(32px) rotate(7deg)';
    el.style.opacity   = '0';
  });

  // Pre-layers reviennent couvrir le panel (simultanément)
  const layers = Array.from(panel.querySelectorAll('.panel-prelayer'));
  if (layers[1]) {
    layers[1].style.transition = 'transform 0.3s cubic-bezier(0.4,0,0.6,1)';
    layers[1].style.transform  = 'translateX(0)';
  }
  setTimeout(() => {
    if (layers[0]) {
      layers[0].style.transition = 'transform 0.3s cubic-bezier(0.4,0,0.6,1)';
      layers[0].style.transform  = 'translateX(0)';
    }
  }, 55);
}

function setLeftPanelOpen(open) {
  leftPanelOpen = open;
  const lp = document.getElementById('left-panel');
  document.getElementById('canvas-wrap').classList.toggle('left-collapsed', !open);
  // Marquer le bouton panneau comme actif
  const panelBtn = document.getElementById('btn-left-panel-open');
  if (panelBtn) panelBtn.classList.toggle('active', open);
  _updatePanelBtn();
  if (open) {
    lp.classList.remove('collapsed');
    _animatePanelOpen('left-panel');
  } else {
    _animatePanelClose('left-panel');
    lp.classList.add('collapsed');
  }
}

function setPropsOpen(open) {
  propsOpen = open;
  const pr = document.getElementById('properties');
  document.getElementById('canvas-wrap').classList.toggle('props-collapsed', !open);
  _updatePanelBtn();
  if (open) {
    pr.classList.remove('collapsed');
    _animatePanelOpen('properties');
  } else {
    _animatePanelClose('properties');
    pr.classList.add('collapsed');
  }
}

function openAllPanels() {
  setLeftPanelOpen(true);
  setPropsOpen(true);
}

function _updatePanelBtn() {
  const allClosed = !leftPanelOpen && !propsOpen;
  document.getElementById('dock-wrap').style.display = allClosed ? 'flex' : 'none';
}

/* ══════════════════════════════════════════════════
   ARCHITECT — auto-layout avec animation
   ══════════════════════════════════════════════════ */

function animateLayout(targets, duration = 700) {
  const init0 = targets.map(({ shape }) => ({ x: shape.x, y: shape.y }));
  const t0 = performance.now();

  function ease(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; }

  function frame(now) {
    const raw = (now - t0) / duration;
    const t = Math.min(raw, 1);
    const e = ease(t);
    targets.forEach(({ shape, tx, ty }, i) => {
      shape.x = init0[i].x + (tx - init0[i].x) * e;
      shape.y = init0[i].y + (ty - init0[i].y) * e;
    });
    render();
    if (t < 1) {
      requestAnimationFrame(frame);
    } else {
      targets.forEach(({ shape, tx, ty }) => { shape.x = tx; shape.y = ty; });
      snapshot();
      render();
    }
  }

  requestAnimationFrame(frame);
}

/* ══════════════════════════════════════════════════
   ALIGNMENT TOOLS
   ══════════════════════════════════════════════════ */

function alignSelectedShapes(mode) {
  if (selectedShapes.size < 2) return;
  const shapes = [...selectedShapes].map(id => state.shapes.find(s => s.id === id)).filter(Boolean);
  if (shapes.length < 2) return;
  snapshot();

  if (mode === 'left') {
    const ref = Math.min(...shapes.map(s => s.x));
    shapes.forEach(s => { s.x = ref; });
  } else if (mode === 'right') {
    const ref = Math.max(...shapes.map(s => s.x + s.w));
    shapes.forEach(s => { s.x = ref - s.w; });
  } else if (mode === 'cx') {
    const ref = shapes.reduce((a, s) => a + s.x + s.w / 2, 0) / shapes.length;
    shapes.forEach(s => { s.x = Math.round(ref - s.w / 2); });
  } else if (mode === 'top') {
    const ref = Math.min(...shapes.map(s => s.y));
    shapes.forEach(s => { s.y = ref; });
  } else if (mode === 'bottom') {
    const ref = Math.max(...shapes.map(s => s.y + s.h));
    shapes.forEach(s => { s.y = ref - s.h; });
  } else if (mode === 'cy') {
    const ref = shapes.reduce((a, s) => a + s.y + s.h / 2, 0) / shapes.length;
    shapes.forEach(s => { s.y = Math.round(ref - s.h / 2); });
  } else if (mode === 'distH') {
    const sorted = [...shapes].sort((a, b) => a.x - b.x);
    const totalW = sorted.reduce((a, s) => a + s.w, 0);
    const span = sorted[sorted.length - 1].x + sorted[sorted.length - 1].w - sorted[0].x;
    const gap = (span - totalW) / (sorted.length - 1);
    let px = sorted[0].x;
    for (const s of sorted) { s.x = Math.round(px); px += s.w + gap; }
  } else if (mode === 'distV') {
    const sorted = [...shapes].sort((a, b) => a.y - b.y);
    const totalH = sorted.reduce((a, s) => a + s.h, 0);
    const span = sorted[sorted.length - 1].y + sorted[sorted.length - 1].h - sorted[0].y;
    const gap = (span - totalH) / (sorted.length - 1);
    let py = sorted[0].y;
    for (const s of sorted) { s.y = Math.round(py); py += s.h + gap; }
  }

  render();
  updateProps();
}

/* ══════════════════════════════════════════════════
   ARCHITECT LAYOUT — optimisation complète async
   ══════════════════════════════════════════════════ */

async function architectLayout() {
  if (state.shapes.length === 0) { showToast('Aucune forme à organiser'); return; }

  // ── Modal de progression ──────────────────────────────────
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;z-index:9000;backdrop-filter:blur(2px)';
  overlay.innerHTML = `
    <div style="background:#1a2030;border:1px solid rgba(255,255,255,0.09);border-radius:20px;padding:30px 36px;min-width:360px;max-width:500px;text-align:center;box-shadow:0 32px 80px rgba(0,0,0,0.6)">
      <div style="font-size:16px;font-weight:700;color:#e2e8f0;margin-bottom:8px">
        <i class="fa-solid fa-wand-magic-sparkles" style="color:#4db868;margin-right:9px"></i>Optimisation en cours…
      </div>
      <div id="arch-status-msg" style="font-size:12px;color:#64748b;margin-bottom:22px;min-height:16px;transition:color 0.2s"></div>
      <div style="background:rgba(255,255,255,0.06);border-radius:8px;height:6px;overflow:hidden">
        <div id="arch-bar" style="height:100%;border-radius:8px;background:linear-gradient(90deg,#22c55e,#4db868);width:0%;transition:width 0.5s ease"></div>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  const archStatus = (msg, pct) => {
    const el = document.getElementById('arch-status-msg');
    const bar = document.getElementById('arch-bar');
    if (el) el.textContent = msg;
    if (bar) bar.style.width = pct + '%';
  };

  await new Promise(r => setTimeout(r, 0));
  snapshot();

  const BAND_Y0 = -200;
  const bands  = state.bands;
  const shapes = state.shapes;
  const conns  = state.connections;
  const groups = state.groups || [];

  try {
    // ── 1. Anti-chevauchement itératif ────────────────────────
    archStatus('Résolution des chevauchements…', 8);
    await new Promise(r => setTimeout(r, 0));
    {
      const PAD = 12;
      let bandRanges = [];

      function _rebuildRanges() {
        bandRanges = [];
        let y0 = BAND_Y0;
        for (const band of bands) { bandRanges.push({ y0, y1: y0 + band.height }); y0 += band.height; }
      }
      function _getBandIdx(s) {
        const mid = s.y + s.h / 2;
        for (let i = 0; i < bandRanges.length; i++)
          if (mid >= bandRanges[i].y0 && mid < bandRanges[i].y1) return i;
        return -1;
      }
      function _clamp() {
        let y0 = BAND_Y0;
        for (const band of bands) {
          for (const s of shapes) {
            const m = s.y + s.h / 2;
            if (m >= y0 && m < y0 + band.height) {
              if (s.y < y0 + 8) s.y = y0 + 8;
              if (s.y + s.h > y0 + band.height - 8) s.y = Math.max(y0 + 8, y0 + band.height - 8 - s.h);
            }
          }
          y0 += band.height;
        }
      }
      function _stretch() {
        let grew = false;
        let y0 = BAND_Y0;
        for (const band of bands) {
          const bot = shapes
            .filter(s => { const m = s.y + s.h / 2; return m >= y0 && m < y0 + band.height; })
            .reduce((m, s) => Math.max(m, s.y + s.h), 0);
          if (bot + 20 > y0 + band.height) { band.height = Math.round(bot + 20 - y0); grew = true; }
          y0 += band.height;
        }
        return grew;
      }
      function _hasOverlap() {
        for (let i = 0; i < shapes.length; i++) {
          for (let j = i + 1; j < shapes.length; j++) {
            const a = shapes[i], b = shapes[j];
            const ovX = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + PAD;
            const ovY = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + PAD;
            if (ovX > 0 && ovY > 0) return true;
          }
        }
        return false;
      }

      _rebuildRanges();
      for (let round = 0; round < 8; round++) {
        for (let iter = 0; iter < 200; iter++) {
          let moved = false;
          for (let i = 0; i < shapes.length; i++) {
            for (let j = i + 1; j < shapes.length; j++) {
              const a = shapes[i], b = shapes[j];
              const ovX = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + PAD;
              const ovY = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + PAD;
              if (ovX <= 0 || ovY <= 0) continue;
              const bandA = _getBandIdx(a), bandB = _getBandIdx(b);
              const sameBand = bandA === bandB && bandA !== -1;
              if (sameBand || ovX <= ovY) {
                const half = ovX / 2;
                if (a.x + a.w / 2 <= b.x + b.w / 2) { a.x -= half; b.x += half; }
                else { a.x += half; b.x -= half; }
              } else {
                const half = ovY / 2;
                if (a.y + a.h / 2 <= b.y + b.h / 2) { a.y -= half; b.y += half; }
                else { a.y += half; b.y -= half; }
              }
              a.x = Math.max(INDEX_W_SVG + 4, a.x);
              b.x = Math.max(INDEX_W_SVG + 4, b.x);
              moved = true;
            }
          }
          _clamp();
          if (!moved) break;
        }
        const grew = _stretch();
        _clamp();
        _rebuildRanges();
        if (!grew && !_hasOverlap()) break;
        await new Promise(r => setTimeout(r, 0));
      }
    }

    // ── 2. Dénouage bandes denses (barycenter + recuit simulé) ─
    archStatus('Analyse des zones denses…', 38);
    await new Promise(r => setTimeout(r, 0));
    {
      const bRangesU = [];
      { let y0 = BAND_Y0; for (const b of bands) { bRangesU.push({ y0, y1: y0 + b.height }); y0 += b.height; } }

      const shapeByIdU = {};
      for (const s of shapes) shapeByIdU[s.id] = s;

      function epX(id) {
        const s = shapeByIdU[id]; if (s) return s.x + s.w / 2;
        const g = groups.find(g => g.id === id);
        if (g) {
          const mem = shapes.filter(s => g.shapeIds && g.shapeIds.includes(s.id));
          if (mem.length) return mem.reduce((a, t) => a + t.x + t.w / 2, 0) / mem.length;
        }
        return null;
      }

      const bandShapesU = bands.map((b, i) =>
        shapes.filter(s => { const m = s.y + s.h / 2; return m >= bRangesU[i].y0 && m < bRangesU[i].y1; })
      );
      const avgU = shapes.length / Math.max(bands.length, 1);
      const HEAVY_U = Math.max(3, Math.ceil(avgU));
      const bandWU = Math.max(1400, shapes.reduce((m, s) => Math.max(m, s.x + s.w), 0) + 300);

      for (let bi = 0; bi < bands.length; bi++) {
        const inBand = bandShapesU[bi];
        if (inBand.length < HEAVY_U) continue;

        const bandIdsU = new Set(inBand.map(s => s.id));
        const relC = conns.filter(c =>
          (bandIdsU.has(c.fromId) || bandIdsU.has(c.toId)) &&
          shapeByIdU[c.fromId] && shapeByIdU[c.toId]
        );
        if (relC.length < 2) continue;

        archStatus(`Dénouage "${bands[bi].label}" — ${inBand.length} formes…`, 38 + (bi / bands.length) * 28);
        await new Promise(r => setTimeout(r, 0));

        const PAD_U = INDEX_W_SVG + 20;
        const totalWU = inBand.reduce((a, s) => a + s.w, 0);
        const gapU = Math.max(16, (bandWU - PAD_U - 20 - totalWU) / (inBand.length + 1));

        function applyOrdU(ord) {
          let cx = PAD_U + gapU;
          for (const idx of ord) { inBand[idx].x = Math.round(cx); cx += inBand[idx].w + gapU; }
        }
        function costU() {
          const xs = {};
          for (const c of relC) {
            if (xs[c.fromId] === undefined) xs[c.fromId] = epX(c.fromId);
            if (xs[c.toId]   === undefined) xs[c.toId]   = epX(c.toId);
          }
          let cost = 0;
          for (const c of relC) {
            const fx = xs[c.fromId], tx = xs[c.toId];
            if (fx != null && tx != null) cost += Math.abs(fx - tx);
          }
          for (let i = 0; i < relC.length; i++) {
            for (let j = i + 1; j < relC.length; j++) {
              const fi = xs[relC[i].fromId], ti = xs[relC[i].toId];
              const fj = xs[relC[j].fromId], tj = xs[relC[j].toId];
              if (fi == null || ti == null || fj == null || tj == null) continue;
              if (Math.abs(fi - fj) < 1 || Math.abs(ti - tj) < 1) continue;
              if ((fi < fj) !== (ti < tj)) cost += 500;
            }
          }
          return cost;
        }

        let ordU = inBand.map((_, i) => i).sort((a, b) => inBand[a].x - inBand[b].x);
        applyOrdU(ordU);

        for (let iter = 0; iter < 10; iter++) {
          const gravs = inBand.map((s, i) => {
            let sum = 0, w = 0;
            for (const c of relC) {
              let othId = null, wt = 1;
              if (c.fromId === s.id) { othId = c.toId;   wt = bandIdsU.has(othId) ? 0.5 : 2; }
              else if (c.toId === s.id) { othId = c.fromId; wt = bandIdsU.has(othId) ? 0.5 : 2; }
              if (othId != null) { const ox = epX(othId); if (ox != null) { sum += ox * wt; w += wt; } }
            }
            return [i, w > 0 ? sum / w : s.x + s.w / 2];
          });
          gravs.sort((a, b) => a[1] - b[1]);
          ordU = gravs.map(g => g[0]);
          applyOrdU(ordU);
        }

        let curCostU = costU();
        let T = 3000, TMIN = 0.5, COOL = 0.9994;
        const NU = inBand.length;
        while (T > TMIN) {
          const i = (Math.random() * NU) | 0;
          const j = (Math.random() * NU) | 0;
          if (i === j) { T *= COOL; continue; }
          [ordU[i], ordU[j]] = [ordU[j], ordU[i]];
          applyOrdU(ordU);
          const nc = costU();
          const delta = nc - curCostU;
          if (delta <= 0 || Math.random() < Math.exp(-delta / T)) {
            curCostU = nc;
          } else {
            [ordU[i], ordU[j]] = [ordU[j], ordU[i]];
            applyOrdU(ordU);
          }
          T *= COOL;
        }
        await new Promise(r => setTimeout(r, 0));
      }
      for (const s of shapes) { if (s.x < INDEX_W_SVG + 4) s.x = INDEX_W_SVG + 4; }
    }

    // ── 3. Assignation des ports ──────────────────────────────
    archStatus('Assignation des points de connexion…', 75);
    await new Promise(r => setTimeout(r, 0));
    {
      const OPP_DIR = { right: 'left', left: 'right', top: 'bottom', bottom: 'top' };
      const PREFER = {
        right:  ['right', 'bottom', 'top', 'left'],
        left:   ['left', 'top', 'bottom', 'right'],
        bottom: ['bottom', 'right', 'left', 'top'],
        top:    ['top', 'left', 'right', 'bottom'],
      };
      const ALIGN_PX = 18;
      const sideUsed = new Map();
      function shapeUsage(id) {
        if (!sideUsed.has(id)) sideUsed.set(id, { right: 0, left: 0, top: 0, bottom: 0 });
        return sideUsed.get(id);
      }
      const pairUsed = new Map();
      const shapeById = {};
      for (const s of shapes) shapeById[s.id] = s;

      function resolvePortShape(id) {
        const s = shapeById[id]; if (s) return s;
        const g = groups.find(g => g.id === id);
        if (!g) return null;
        const members = shapes.filter(s => g.shapeIds.includes(s.id));
        if (!members.length) return null;
        const xs = members.flatMap(s => [s.x, s.x + s.w]);
        const ys = members.flatMap(s => [s.y, s.y + s.h]);
        const GPAD = 22, GLBL = 24;
        return { x: Math.min(...xs) - GPAD, y: Math.min(...ys) - GPAD - GLBL,
                 w: Math.max(...xs) - Math.min(...xs) + GPAD * 2,
                 h: Math.max(...ys) - Math.min(...ys) + GPAD * 2 + GLBL, type: 'group' };
      }

      function assignPort(conn) {
        const fs = resolvePortShape(conn.fromId);
        const ts = resolvePortShape(conn.toId);
        if (!fs || !ts) return;
        const fcx = fs.x + fs.w / 2, fcy = fs.y + fs.h / 2;
        const tcx = ts.x + ts.w / 2, tcy = ts.y + ts.h / 2;
        const dx = tcx - fcx, dy = tcy - fcy;
        const fu = shapeUsage(conn.fromId);
        const tu = shapeUsage(conn.toId);
        if (Math.abs(dy) < ALIGN_PX && Math.abs(dx) > 1) {
          const dir = dx >= 0 ? 'right' : 'left';
          fu[dir]++; tu[OPP_DIR[dir]]++;
          conn.fromPortDir = dir; conn.toPortDir = OPP_DIR[dir]; return;
        }
        if (Math.abs(dx) < ALIGN_PX && Math.abs(dy) > 1) {
          const dir = dy >= 0 ? 'bottom' : 'top';
          fu[dir]++; tu[OPP_DIR[dir]]++;
          conn.fromPortDir = dir; conn.toPortDir = OPP_DIR[dir]; return;
        }
        const pairKey = conn.fromId < conn.toId ? `${conn.fromId}↔${conn.toId}` : `${conn.toId}↔${conn.fromId}`;
        if (pairUsed.has(pairKey)) {
          const prev = pairUsed.get(pairKey);
          const dir = prev.firstFromId === conn.fromId ? prev.dir : OPP_DIR[prev.dir];
          fu[dir]++; tu[OPP_DIR[dir]]++;
          conn.fromPortDir = dir; conn.toPortDir = OPP_DIR[dir]; return;
        }
        const nat = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top');
        const backward = OPP_DIR[nat];
        const candidates = (fs.type === 'decision' || ts.type === 'decision')
          ? ['right', 'bottom', 'left', 'top'] : PREFER[nat];
        let bestDir = nat, bestScore = Infinity;
        for (const dir of candidates) {
          let score = fu[dir] + tu[OPP_DIR[dir]];
          if (dir === backward) score += 8;
          if (score < bestScore) { bestScore = score; bestDir = dir; if (score === 0) break; }
        }
        fu[bestDir]++; tu[OPP_DIR[bestDir]]++;
        conn.fromPortDir = bestDir; conn.toPortDir = OPP_DIR[bestDir];
        pairUsed.set(pairKey, { dir: bestDir, firstFromId: conn.fromId });
      }

      conns.filter(c => c.style !== 'dashed').forEach(assignPort);
      conns.filter(c => c.style === 'dashed').forEach(assignPort);

      // Redistribution surcharge (> 3 connexions sur un même côté)
      const SIDE_MAX = 3;
      const OPP2 = OPP_DIR;
      const ALL_DIRS = ['right', 'left', 'bottom', 'top'];
      const fromCount = new Map();
      for (const c of conns) {
        if (!c.fromPortDir) continue;
        const key = `${c.fromId}-${c.fromPortDir}`;
        if (!fromCount.has(key)) fromCount.set(key, []);
        fromCount.get(key).push(c);
      }
      for (const [key, group] of fromCount) {
        if (group.length <= SIDE_MAX) continue;
        const dashIdx = key.lastIndexOf('-');
        const shapeIdNum = parseInt(key.slice(0, dashIdx));
        const dir = key.slice(dashIdx + 1);
        const fs = resolvePortShape(shapeIdNum);
        if (!fs) continue;
        const excess = group.slice(SIDE_MAX);
        for (const c of excess) {
          const altDirs = ALL_DIRS.filter(d => d !== dir && d !== OPP2[dir]);
          let bestAlt = null, bestCnt = Infinity;
          for (const d of altDirs) {
            const cnt = (fromCount.get(`${shapeIdNum}-${d}`) || []).length;
            if (cnt < bestCnt) { bestCnt = cnt; bestAlt = d; }
          }
          if (bestAlt && bestCnt < group.length) {
            const oldArr = fromCount.get(key);
            oldArr.splice(oldArr.indexOf(c), 1);
            const newKey = `${shapeIdNum}-${bestAlt}`;
            if (!fromCount.has(newKey)) fromCount.set(newKey, []);
            fromCount.get(newKey).push(c);
            c.fromPortDir = bestAlt;
            c.toPortDir   = OPP2[bestAlt];
          }
        }
      }
    }

    // ── 4. Espace pour les étiquettes de flèches ─────────────
    archStatus('Espace pour les étiquettes…', 82);
    await new Promise(r => setTimeout(r, 0));
    {
      // Pour chaque connexion avec une étiquette, s'assurer que le segment
      // principal est assez long pour afficher le texte.
      // Si le gap est insuffisant, on écarte légèrement les deux formes.
      const shapeById2 = {};
      for (const s of shapes) shapeById2[s.id] = s;

      let adjusted = false;
      for (const c of conns) {
        if (!c.label || !c.label.trim() || !c.fromPortDir) continue;
        const fs = shapeById2[c.fromId];
        const ts = shapeById2[c.toId];
        if (!fs || !ts) continue;

        const minLen = c.label.length * 6 + 24; // même heuristique que le rendu

        const dir = c.fromPortDir;
        if (dir === 'right') {
          const gap = ts.x - (fs.x + fs.w);
          if (gap < minLen) {
            const push = Math.ceil((minLen - gap + 4) / 2);
            ts.x = Math.round(ts.x + push);
            fs.x = Math.max(INDEX_W_SVG + 4, Math.round(fs.x - push));
            adjusted = true;
          }
        } else if (dir === 'left') {
          const gap = fs.x - (ts.x + ts.w);
          if (gap < minLen) {
            const push = Math.ceil((minLen - gap + 4) / 2);
            fs.x = Math.round(fs.x + push);
            ts.x = Math.max(INDEX_W_SVG + 4, Math.round(ts.x - push));
            adjusted = true;
          }
        } else if (dir === 'bottom') {
          const gap = ts.y - (fs.y + fs.h);
          if (gap < minLen) {
            const push = Math.ceil((minLen - gap + 4) / 2);
            ts.y = Math.round(ts.y + push);
            fs.y = Math.round(fs.y - push);
            adjusted = true;
          }
        } else if (dir === 'top') {
          const gap = fs.y - (ts.y + ts.h);
          if (gap < minLen) {
            const push = Math.ceil((minLen - gap + 4) / 2);
            fs.y = Math.round(fs.y + push);
            ts.y = Math.round(ts.y - push);
            adjusted = true;
          }
        }
      }

      if (adjusted) {
        // Passe rapide anti-chevauchement pour corriger les nouveaux conflits
        const PAD2 = 12;
        let bRanges2 = [];
        { let y0 = BAND_Y0; for (const b of bands) { bRanges2.push({ y0, y1: y0 + b.height }); y0 += b.height; } }

        for (let iter = 0; iter < 120; iter++) {
          let moved = false;
          for (let i = 0; i < shapes.length; i++) {
            for (let j = i + 1; j < shapes.length; j++) {
              const a = shapes[i], b = shapes[j];
              const ovX = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) + PAD2;
              const ovY = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) + PAD2;
              if (ovX <= 0 || ovY <= 0) continue;
              if (ovX <= ovY) {
                const half = ovX / 2;
                if (a.x + a.w / 2 <= b.x + b.w / 2) { a.x -= half; b.x += half; }
                else { a.x += half; b.x -= half; }
              } else {
                const half = ovY / 2;
                if (a.y + a.h / 2 <= b.y + b.h / 2) { a.y -= half; b.y += half; }
                else { a.y += half; b.y -= half; }
              }
              a.x = Math.max(INDEX_W_SVG + 4, a.x);
              b.x = Math.max(INDEX_W_SVG + 4, b.x);
              moved = true;
            }
          }
          // Clamp dans les bandes
          let y0c = BAND_Y0;
          for (const band of bands) {
            for (const s of shapes) {
              const m = s.y + s.h / 2;
              if (m >= y0c && m < y0c + band.height) {
                if (s.y < y0c + 8) s.y = y0c + 8;
                if (s.y + s.h > y0c + band.height - 8) s.y = Math.max(y0c + 8, y0c + band.height - 8 - s.h);
              }
            }
            y0c += band.height;
          }
          if (!moved) break;
        }
      }
    }

    // ── 5. Couleurs + bandWidth ───────────────────────────────
    archStatus('Finalisation…', 94);
    await new Promise(r => setTimeout(r, 0));

    state.shapes.forEach(s => updateShapeColor(s));
    state.connections.forEach(c => {
      const from = state.shapes.find(s => s.id === c.fromId);
      if (from) c.color = from.color;
    });
    state.bandWidth = Math.max(1400, Math.round(shapes.reduce((m, s) => Math.max(m, s.x + s.w), 0) + 300));

    archStatus('Terminé !', 100);
    await new Promise(r => setTimeout(r, 280));

  } catch (err) {
    console.error('architectLayout error:', err);
  } finally {
    overlay.remove();
  }

  clearSelection();
  render();
  updateProps();
  showToast('Optimisation terminée');
}

/* ══════════════════════════════════════════════════
   INIT
   ══════════════════════════════════════════════════ */

function init() {
  // Toolbar tool buttons — shape tools use drag & drop, other tools use click
  const SHAPE_TOOLS = ['process', 'start-end', 'special', 'decision'];
  document.querySelectorAll('[data-tool]').forEach(btn => {
    if (SHAPE_TOOLS.includes(btn.dataset.tool)) {
      btn.setAttribute('draggable', 'true');
      btn.addEventListener('dragstart', e => {
        e.dataTransfer.effectAllowed = 'copy';
        e.dataTransfer.setData('text/plain', btn.dataset.tool);
        // subtype par défaut = normal pour le bouton principal
        e.dataTransfer.setData('text/shape-subtype', 'normal');
      });
      btn.addEventListener('click', () => showToast('Glissez cette forme sur le canevas'));
    } else if (btn.dataset.tool) {
      btn.addEventListener('click', () => setTool(btn.dataset.tool));
    }
  });

  // Sous-boutons de la dropdown activité (subtype normal / external)
  document.querySelectorAll('.shape-sub-btn[data-shape-type]').forEach(btn => {
    btn.setAttribute('draggable', 'true');
    btn.addEventListener('dragstart', e => {
      e.dataTransfer.effectAllowed = 'copy';
      e.dataTransfer.setData('text/plain', btn.dataset.shapeType);
      e.dataTransfer.setData('text/shape-subtype', btn.dataset.shapeSubtype || 'normal');
    });
  });

  // Hover dropdown sur le bouton Activité (immédiat)
  const processWrap = document.getElementById('process-shape-wrap');
  if (processWrap) {
    let hideTimer = null;
    processWrap.addEventListener('mouseenter', () => {
      clearTimeout(hideTimer);
      processWrap.classList.add('open');
    });
    processWrap.addEventListener('mouseleave', () => {
      hideTimer = setTimeout(() => processWrap.classList.remove('open'), 180);
    });
  }

  // Hover 2s sur Connecter → dropdown choix routage
  const connectWrap = document.getElementById('connect-tool-wrap');
  if (connectWrap) {
    let showTimer = null, hideTimer2 = null;
    function updateRoutingBtns() {
      connectWrap.querySelectorAll('.conn-routing-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.routing === (state.defaultRouting || 'smooth'));
      });
    }
    connectWrap.addEventListener('mouseenter', () => {
      clearTimeout(hideTimer2);
      showTimer = setTimeout(() => connectWrap.classList.add('open'), 1000);
    });
    connectWrap.addEventListener('mouseleave', () => {
      clearTimeout(showTimer);
      hideTimer2 = setTimeout(() => connectWrap.classList.remove('open'), 200);
    });
    connectWrap.querySelectorAll('.conn-routing-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const routing = btn.dataset.routing;
        state.defaultRouting = routing;
        state.connections.forEach(c => { c.routing = routing; });
        updateRoutingBtns();
        connectWrap.classList.remove('open');
        clearTimeout(showTimer);
        snapshot();
        render();
        showToast(`Tracé : ${routing === 'smooth' ? 'courbe' : 'orthogonal'} — toutes les flèches mises à jour`);
      });
    });
    updateRoutingBtns();
  }

  // Drop zone on canvas
  canvas.addEventListener('dragover', e => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  canvas.addEventListener('drop', e => {
    e.preventDefault();
    const shapeType = e.dataTransfer.getData('text/plain');
    if (!SHAPE_DEFAULTS[shapeType]) return;
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    const def = SHAPE_DEFAULTS[shapeType];
    const shapeSubtype = e.dataTransfer.getData('text/shape-subtype') || def.subtype || 'normal';
    const s = {
      id: state.nextId++,
      type: shapeType,
      x: Math.round(x - def.w / 2),
      y: Math.round(y - def.h / 2),
      w: def.w, h: def.h,
      label: shapeSubtype === 'external' ? 'Activité externe' : shapeSubtype === 'extco' ? 'Externe à l\'entreprise' : def.label,
      color: def.color,
      textColor: def.textColor,
      strokeColor: '',
      validationBadge: false,
      validationColor: def.validationColor || '#4DB868',
      fontSize: def.fontSize || 14,
      colorVariant: 0,
      subtype: shapeSubtype,
    };
    state.shapes.push(s);
    updateShapeColor(s);
    selectShape(s.id, false, false);
    snapshot(); render(); updateProps();
    showToast('Forme ajoutée');
  });

  // Panel collapse
  document.getElementById('btn-close-left-panel').addEventListener('click', () => setLeftPanelOpen(false));
  document.getElementById('btn-close-props').addEventListener('click', () => setPropsOpen(false));
  document.getElementById('btn-left-panel-open').addEventListener('click', () => setLeftPanelOpen(!leftPanelOpen));

  // Grouper
  document.getElementById('btn-group-create').addEventListener('click', createGroup);

  document.getElementById('btn-new-carto').addEventListener('click', newCarto);
  document.getElementById('btn-architect').addEventListener('click', architectLayout);
  document.getElementById('btn-undo').addEventListener('click', undo);
  document.getElementById('btn-redo').addEventListener('click', redo);
  document.getElementById('btn-fit').addEventListener('click', fitView);
  document.getElementById('btn-delete').addEventListener('click', deleteSelected);
  document.getElementById('btn-export-svg').addEventListener('click', exportSVG);
  document.getElementById('btn-export-pdf').addEventListener('click', exportPDF);
  document.getElementById('btn-save').addEventListener('click', saveJSON);
  document.getElementById('btn-load').addEventListener('click', openLoadDialog);
  document.getElementById('btn-import-vsdx').addEventListener('click', openVSDXDialog);

  // VSDX dialog
  document.getElementById('vsdx-dialog-close').addEventListener('click', () => {
    document.getElementById('vsdx-dialog').classList.add('hidden');
  });
  document.getElementById('vsdx-dialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
  });

  // File input (browse button)
  document.getElementById('vsdx-file-input').addEventListener('change', e => {
    const f = e.target.files[0];
    if (f) importVSDX(f);
    e.target.value = '';
  });

  // Drag & drop on dropzone
  const dz = document.getElementById('vsdx-dropzone');
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
  dz.addEventListener('drop', e => {
    e.preventDefault();
    dz.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f && (f.name.endsWith('.vsdx') || f.type === 'application/vnd.ms-visio.drawing')) {
      importVSDX(f);
    } else {
      const st = document.getElementById('vsdx-status');
      st.style.display = '';
      st.className = 'vsdx-status error';
      st.textContent = 'Fichier invalide — seul le format .vsdx est accepté.';
    }
  });

  // Folder component
  initFolder();

  // Dock
  initDock();

  // New carto dialog
  document.getElementById('new-carto-dialog-close').addEventListener('click', () => {
    document.getElementById('new-carto-dialog').classList.add('hidden');
  });
  document.getElementById('new-carto-save').addEventListener('click', async () => {
    document.getElementById('new-carto-dialog').classList.add('hidden');
    await saveJSON();
    _doNewCarto();
  });
  document.getElementById('new-carto-confirm').addEventListener('click', () => {
    document.getElementById('new-carto-dialog').classList.add('hidden');
    _doNewCarto();
  });
  document.getElementById('new-carto-dialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
  });

  // Load dialog close
  document.getElementById('load-dialog-close').addEventListener('click', () => {
    document.getElementById('load-dialog').classList.add('hidden');
  });
  document.getElementById('load-dialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
  });
  document.getElementById('bands-dialog').addEventListener('click', e => {
    if (e.target === e.currentTarget) e.currentTarget.classList.add('hidden');
  });

  bindProps();
  bindBandProps();

  // Alignment tools
  document.querySelectorAll('.align-btn[data-align]').forEach(btn => {
    btn.addEventListener('click', () => alignSelectedShapes(btn.dataset.align));
  });

  // Initial render
  applyViewport();
  setTool('select');
  render();
  updateProps();

  // Apply initial collapsed state (no animation)
  document.getElementById('left-panel').classList.add('collapsed');
  document.getElementById('properties').classList.add('collapsed');
  document.getElementById('canvas-wrap').classList.add('left-collapsed');
  document.getElementById('canvas-wrap').classList.add('props-collapsed');
  _updatePanelBtn();

  // Welcome modal
  initWelcome();
}

function initWelcome() {
  const overlay = document.getElementById('welcome-modal');
  if (!overlay) return;
  document.getElementById('btn-welcome-start').addEventListener('click', () => {
    overlay.classList.add('hidden');
    setTimeout(() => {
      overlay.remove();
      _maybeShowMigrationModal();
    }, 400);
  });
}

async function _maybeShowMigrationModal() {
  if (!window.OPTIQCARTO_HAS_VSDX || window.OPTIQCARTO_HAS_CARTO) return;
  const modal = document.getElementById('vsdx-migrate-modal');
  if (modal) modal.classList.remove('hidden');
}

async function _autoLoadCarto() {
  if (!window.OPTIQCARTO_DEFAULT_NAME || !window.OPTIQCARTO_HAS_CARTO) return;
  try {
    const r = await fetch(`${_API}/api/load/${encodeURIComponent(window.OPTIQCARTO_DEFAULT_NAME)}`);
    if (!r.ok) return;
    const data = await r.json();
    if (data.error) return;
    state = data;
    if (!state.bandWidth) state.bandWidth = 1600;
    if (!state.groups) state.groups = [];
    clearSelection();
    history = [JSON.stringify(state)]; histIndex = 0;
    render(); updateProps(); fitView();
  } catch (e) { /* silencieux */ }
}

/* ══════════════════════════════════════════════════
   FOLDER COMPONENT
   ══════════════════════════════════════════════════ */

function initFolder() {
  const section = document.getElementById('file-folder-section');
  const trigger = document.getElementById('btn-folder-toggle');
  if (!section || !trigger) return;

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    section.classList.toggle('open');
  });

  // Click outside → close
  document.addEventListener('click', (e) => {
    if (!section.contains(e.target)) {
      section.classList.remove('open');
    }
  });

  // Close folder when an action button is clicked
  section.querySelectorAll('.folder-action-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setTimeout(() => section.classList.remove('open'), 120);
    });
  });
}

/* ══════════════════════════════════════════════════
   DOCK COMPONENT
   ══════════════════════════════════════════════════ */

function initDock() {
  const dockPanel = document.getElementById('dock-panel');
  if (!dockPanel) return;

  const items = Array.from(dockPanel.querySelectorAll('.dock-item'));
  const BASE_SIZE  = 48;
  const MAX_SIZE   = 72;
  const RANGE      = 90; // px distance from center to start scaling

  function updateMagnification(mouseX, mouseY) {
    const panelRect = dockPanel.getBoundingClientRect();
    items.forEach(item => {
      const itemRect = item.getBoundingClientRect();
      const itemCenterX = itemRect.left + itemRect.width / 2;
      const itemCenterY = itemRect.top  + itemRect.height / 2;
      const dist = Math.hypot(mouseX - itemCenterX, mouseY - itemCenterY);
      const ratio = Math.max(0, 1 - dist / RANGE);
      const size = BASE_SIZE + (MAX_SIZE - BASE_SIZE) * ratio;
      item.style.width  = size + 'px';
      item.style.height = size + 'px';
      item.style.fontSize = Math.round(16 + 8 * ratio) + 'px';
    });
  }

  function resetMagnification() {
    items.forEach(item => {
      item.style.width  = BASE_SIZE + 'px';
      item.style.height = BASE_SIZE + 'px';
      item.style.fontSize = '16px';
    });
  }

  dockPanel.addEventListener('mousemove', e => updateMagnification(e.clientX, e.clientY));
  dockPanel.addEventListener('mouseleave', resetMagnification);

  document.getElementById('dock-left-panel').addEventListener('click', () => setLeftPanelOpen(true));
  document.getElementById('dock-props').addEventListener('click', () => setPropsOpen(true));
  document.getElementById('dock-close').addEventListener('click', () => {
    if (confirm('Fermer OptiqCarto ?')) window.close();
  });

  resetMagnification();
}


document.addEventListener('DOMContentLoaded', () => {
  init();
  _autoLoadCarto();
});
