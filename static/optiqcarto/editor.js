'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — Éditeur SVG
   Dépendances chargées avant ce fichier :
     color-utils.js  — utilitaires couleur purs
     geometry.js     — géométrie & chemins SVG purs
     vsdx_importer.js
   ══════════════════════════════════════════════════ */

function getBandForY(midY) {
  let y = -200;
  for (const band of state.bands) {
    if (midY >= y && midY < y + band.height) return band;
    y += band.height;
  }
  return null;
}

function updateShapeColor(s) {
  if (s.type === 'decision') { s.color = '#9ca3af'; return; }
  if (s.type === 'start-end') return; // Renvoi : couleur gérée par _updateRenvoiColor
  const band = getBandForY(s.y + s.h / 2);
  if (!band) return;
  s.color = s.colorVariant === 1 ? bandMutedColor(band.color) : band.color;
  if (s.type === 'process' && !s.customStroke) {
    s.strokeColor = darkenColor(band.color, 0.65);
  }
  state.connections.forEach(c => { if (c.fromId === s.id) c.color = s.color; });
}

// Renvoi : colorier le cercle selon le nom de l'activité correspondante
function _updateRenvoiColor(s) {
  const label = (s.label || '').trim().toLowerCase();
  if (!label) { s.color = '#ffffff'; s.textColor = '#000000'; return; }
  const match = state.shapes.find(
    o => o.id !== s.id && o.type === 'process' &&
         (o.label || '').trim().toLowerCase() === label
  );
  if (match) { s.color = match.color; s.textColor = '#ffffff'; }
  else        { s.color = '#ffffff';   s.textColor = '#000000'; }
}

// Quand une activité B se connecte à un Renvoi R1 (flèche entrante dans R1) :
// → crée automatiquement un second Renvoi coloré comme B, positionné près de
//   l'activité A (celle que R1 référence via son label), et le connecte à A.
function _checkRenvoiAutoLink(fromShapeId, toShapeId) {
  const actB   = state.shapes.find(s => s.id === fromShapeId); // source = activité
  const renvoi = state.shapes.find(s => s.id === toShapeId);   // cible  = renvoi
  if (!actB || !renvoi) return;
  if (actB.type !== 'process' || renvoi.type !== 'start-end') return;

  const renvoiLabel = (renvoi.label || '').trim().toLowerCase();
  if (!renvoiLabel) return;

  const actA = state.shapes.find(
    s => s.type === 'process' && s.id !== fromShapeId &&
         (s.label || '').trim().toLowerCase() === renvoiLabel
  );
  if (!actA) return;

  // Connexion originale actB → renvoi (vient d'être créée juste avant l'appel)
  const origConn = state.connections.find(c => c.fromId === fromShapeId && c.toId === toShapeId);

  // Créer R2 à gauche de A avec un écart suffisant
  const R2W = SHAPE_DEFAULTS['start-end'].w;
  const R2H = SHAPE_DEFAULTS['start-end'].h;
  const r2x = Math.max(INDEX_W_SVG + 4, Math.round(actA.x - R2W - 80));
  const r2y = Math.round(actA.y + actA.h / 2 - R2H / 2);
  const r2 = {
    id: state.nextId++,
    type: 'start-end',
    x: r2x, y: r2y, w: R2W, h: R2H,
    label:          actB.label || '',
    color:          actB.color,
    textColor:      '#ffffff',
    strokeColor:    '',
    validationBadge: false,
    validationColor: '#4DB868',
    fontSize:       SHAPE_DEFAULTS['start-end'].fontSize,
    colorVariant:   0,
    subtype:        'normal',
  };
  state.shapes.push(r2);

  // Connexion R2 → A — même style et label que la connexion originale
  if (!wouldBeBackwards(r2.id, actA.id) &&
      !state.connections.some(c => c.fromId === r2.id && c.toId === actA.id)) {
    const mirrorConn = {
      id:       state.nextId++,
      fromId:   r2.id,
      toId:     actA.id,
      style:    origConn ? origConn.style  : 'solid',
      routing:  state.defaultRouting || 'smooth',
      color:    actB.color,
      label:    origConn ? origConn.label  : '',
      mirrorConnId: origConn ? origConn.id : null,
    };
    if (origConn) origConn.mirrorConnId = mirrorConn.id;
    state.connections.push(mirrorConn);
  }
}

// ── Défauts par type de forme ─────────────────────
function _defaultBands() {
  return [
    { id:  1, label: 'Analyse de Marché & Communication',                           color: '#FF0000', fontSize: 11, height: 220 },
    { id:  2, label: 'Vente & Suivi commercial',                                    color: '#C00000', fontSize: 11, height: 220 },
    { id:  3, label: 'Gestion Administrative & Financière',                         color: '#00B050', fontSize: 11, height: 220 },
    { id:  4, label: 'Négociation & Relations Fournisseurs',                         color: '#808000', fontSize: 11, height: 220 },
    { id:  5, label: 'Coordination & Suivi de Projet',                              color: '#5B9BD5', fontSize: 11, height: 220 },
    { id:  6, label: 'Conception Produit & Ingénierie',                             color: '#2E74B5', fontSize: 11, height: 220 },
    { id:  7, label: 'Organisation Industrielle & Méthodes (hors production directe)', color: '#1F3864', fontSize: 11, height: 220 },
    { id:  8, label: 'Satisfaction Client & Amélioration Continue',                 color: '#FFFF00', fontSize: 11, height: 220 },
    { id:  9, label: 'Contrôle qualité & Mesure (Métrologie)',                      color: '#7030A0', fontSize: 11, height: 220 },
    { id: 10, label: 'Fabrication & Réalisation Produit (opérations directes)',     color: '#4472C4', fontSize: 11, height: 220 },
    { id: 11, label: 'Organisation & Planification du Travail',                     color: '#ED7D31', fontSize: 11, height: 220 },
    { id: 12, label: 'Analyse Technique & Résolution de Problèmes',                 color: '#843C00', fontSize: 11, height: 220 },
    { id: 13, label: 'Logistique & Gestion des Flux Physiques',                     color: '#375623', fontSize: 11, height: 220 },
    { id: 14, label: 'Pilotage Stratégique & Opérationnel (macro)',                 color: '#D9D9D9', fontSize: 11, height: 220 },
    { id: 15, label: 'Gestion des Compétences & des Talents',                       color: '#92D050', fontSize: 11, height: 220 },
  ];
}

const SHAPE_DEFAULTS = {
  process:   { label: 'Activité',      color: '#22c55e', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 130, h: 90,  fontSize: 18, subtype: 'normal' },
  'start-end': { label: 'Renvoi',      color: '#ffffff', textColor: '#000000', validationBadge: false, validationColor: '#4DB868', w: 90,  h: 90,  fontSize: 13, subtype: 'normal' },
  special:   { label: 'Sous-activité', color: '#f59e0b', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 170, h: 76,  fontSize: 13, subtype: 'normal' },
  decision:  { label: 'Décision',      color: '#9ca3af', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 100, h: 100, fontSize: 13, subtype: 'normal' },
};

const HINTS = {
  select:    'Clic = sélectionner · Glisser = déplacer · Double-clic = éditer texte · Suppr = supprimer',
  connect:   'Cliquez sur la forme source, puis sur la forme destination · Échap = annuler',
  process:   'Cliquez sur le canevas pour placer l\'activité',
  'start-end': 'Cliquez sur le canevas pour placer un renvoi',
  special:   'Cliquez sur le canevas pour placer la sous-activité',
};

// ── État principal ────────────────────────────────
let state = {
  shapes: [],
  connections: [],
  groups: [],   // { id, label, shapeIds:[], color:'#b3a0ff' }
  bands: _defaultBands(),
  showBands: true,
  showLegend: false,
  nextId: 100,
  bandWidth: 3200,
  defaultRouting: 'orthogonal',
};

let history = [JSON.stringify(state)];
let histIndex = 0;

// ── Viewport ──────────────────────────────────────
// vpScale=0.5 → affichage "100%" (×200 dans la status bar)
let vpX = 0, vpY = 280, vpScale = 0.5;
// Sensibilité zoom (% par cran de molette) — persistée en localStorage
let _zoomSens = Math.max(3, Math.min(30, parseFloat(localStorage.getItem('optiqcarto-zoom-sens') || '12')));

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
let bendDrag = null;        // { connId, startX, startY, startOffset:{dx,dy} }
let labelDrag = null;       // { connId, startLx, startLy, startX, startY }
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
  if (statusZoom) statusZoom.textContent = Math.round(vpScale * 200) + '%';
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
   SHAPE GEOMETRY (state-dependent)
   Fonctions pures (getPorts, hitShape, etc.) → geometry.js
   ══════════════════════════════════════════════════ */

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

// Returns true if fromId→toId would be a "backwards" arrow (target is left of source)
function wouldBeBackwards(fromId, toId) {
  function getCX(id) {
    const s = state.shapes.find(s => s.id === id);
    if (s) return s.x + s.w / 2;
    const g = state.groups && state.groups.find(g => g.id === id);
    if (g) { const b = getGroupBounds(g); return b ? b.x + b.w / 2 : null; }
    return null;
  }
  const fx = getCX(fromId), tx = getCX(toId);
  if (fx === null || tx === null) return false;
  return tx < fx - 10; // 10px threshold
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

function shapeAtPoint(px, py) {
  // Iterate reverse to hit top-most first
  for (let i = state.shapes.length - 1; i >= 0; i--) {
    if (hitShape(state.shapes[i], px, py)) return state.shapes[i];
  }
  return null;
}

// ── Les lignes croisées se superposent librement (pas de bridges) ──

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
    if (band.deleted) continue;
    const isSel = selectedBand === band.id;
    const g = el('g', {}, gBands);
    const bgColor = bandBgColor(band.color);

    // Fond de la bande → très pâle pour faire ressortir les formes
    el('rect', { x: 0, y, width: bw, height: band.height, fill: bgColor }, g);

    // ── Zone index (gauche) ────
    // On utilise band.color directement — pas de conversion via bandIndexColor
    // pour éviter que pastelToVivid() produise du gris sur les couleurs peu saturées.
    const idxColor = band.color || '#9ca3af';
    el('rect', {
      x: 0, y, width: INDEX_W_SVG, height: band.height,
      fill: isSel ? darkenColor(idxColor, 0.78) : idxColor,
      'data-band-index': band.id,
      cursor: 'pointer',
    }, g);

    // Séparateur droit de la zone index
    el('line', {
      x1: INDEX_W_SVG, y1: y, x2: INDEX_W_SVG, y2: y + band.height,
      stroke: darkenColor(idxColor, 0.72),
      'stroke-width': '3',
      'pointer-events': 'none',
    }, g);

    // Label multi-ligne de la bande — vertical (rotation -90°)
    {
      const cx = INDEX_W_SVG / 2, cy = y + band.height / 2;
      const fs = Math.min(band.fontSize || 11, 14);
      const charW = fs * 0.65;
      const charsPerLine = Math.max(5, Math.floor((band.height - 24) / charW));
      const lineH = fs * 1.4;
      const words = (band.label || '').split(' ');
      const lines = [];
      let cur = '';
      for (const w of words) {
        const test = cur ? cur + ' ' + w : w;
        if (test.length <= charsPerLine || !cur) { cur = test; }
        else { lines.push(cur); cur = w; }
      }
      if (cur) lines.push(cur);
      const tg = el('g', { transform: `rotate(-90, ${cx}, ${cy})`, 'pointer-events': 'none' }, g);
      const fill = bandTextColor(idxColor);
      lines.forEach((ln, li) => {
        const oy = (li - (lines.length - 1) / 2) * lineH;
        txt(ln.toUpperCase(), {
          x: cx, y: cy + oy,
          'text-anchor': 'middle', 'dominant-baseline': 'middle',
          fill, 'font-size': fs, 'font-family': 'Segoe UI, sans-serif',
          'font-weight': '700', 'letter-spacing': '0.8',
        }, tg);
      });
    }

    // Bordure basse
    el('line', {
      x1: 0, y1: y + band.height, x2: bw, y2: y + band.height,
      stroke: darkenColor(idxColor, 0.72), 'stroke-width': '3', 'pointer-events': 'none',
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

// Snap a point (px,py) to the nearest point on a polyline, with max perpendicular offset.
function snapToPolyline(pts, px, py, maxPerp = 45) {
  let bestDist = Infinity, bestOnSeg = null, bestSegIdx = -1;
  for (let i = 0; i < pts.length - 1; i++) {
    const pa = pts[i], pb = pts[i + 1];
    const dx = pb.x - pa.x, dy = pb.y - pa.y;
    const len2 = dx * dx + dy * dy;
    if (len2 < 1) continue;
    const t = Math.max(0.05, Math.min(0.95, ((px - pa.x) * dx + (py - pa.y) * dy) / len2));
    const ox = pa.x + t * dx, oy = pa.y + t * dy;
    const d = Math.hypot(px - ox, py - oy);
    if (d < bestDist) { bestDist = d; bestOnSeg = { x: ox, y: oy, i }; bestSegIdx = i; }
  }
  if (!bestOnSeg) return { x: px, y: py };
  const pa = pts[bestSegIdx], pb = pts[bestSegIdx + 1];
  const dx = pb.x - pa.x, dy = pb.y - pa.y;
  const slen = Math.hypot(dx, dy);
  if (slen < 1) return bestOnSeg;
  const nx = -dy / slen, ny = dx / slen;
  const perp = (px - bestOnSeg.x) * nx + (py - bestOnSeg.y) * ny;
  const clampedPerp = Math.max(-maxPerp, Math.min(maxPerp, perp));
  return { x: bestOnSeg.x + nx * clampedPerp, y: bestOnSeg.y + ny * clampedPerp };
}

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

  // spreadPort: attache une connexion au bord d'une forme.
  // Si explicitT est fourni (depuis VSDX ou drag manuel), l'utilise directement
  // pour une précision pixel-perfect. Sinon, auto-spread équidistant via fromUsage.
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
    // Explicit T: use it directly (VSDX import or user-set position)
    if (explicitT !== undefined) {
      const t = explicitT;
      switch (dir) {
        case 'left':   return { x: ep.x - h,           y: ep.y + ep.h * t, dir: 'left'   };
        case 'right':  return { x: ep.x + ep.w + h,    y: ep.y + ep.h * t, dir: 'right'  };
        case 'top':    return { x: ep.x + ep.w * t,    y: ep.y - h,        dir: 'top'    };
        case 'bottom': return { x: ep.x + ep.w * t,    y: ep.y + ep.h + h, dir: 'bottom' };
      }
    }
    // Auto-spread: distribute evenly among outgoing connections on this edge
    const key = `${ep.id}-${dir}`;
    const users = fromUsage[key] || [];
    const idx = users.indexOf(connId);
    const n   = users.length;
    const t   = n <= 1 ? 0.5 : (idx + 1) / (n + 1);
    switch (dir) {
      case 'left':   return { x: ep.x - h,           y: ep.y + ep.h * t, dir: 'left'   };
      case 'right':  return { x: ep.x + ep.w + h,    y: ep.y + ep.h * t, dir: 'right'  };
      case 'top':    return { x: ep.x + ep.w * t,    y: ep.y - h,        dir: 'top'    };
      case 'bottom': return { x: ep.x + ep.w * t,    y: ep.y + ep.h + h, dir: 'bottom' };
      default:       return { x: cx, y: cy, dir };
    }
  }

  const placedLabels = []; // bounding boxes des labels déjà placés
  const placedPaths  = []; // segments des connexions déjà rendues (évite labels aux croisements)
  const labelQueue   = []; // labels collectés en passe 1, rendus en passe 2 (toujours au-dessus)

  // ── Passe 1 : chemins de toutes les connexions ────────────────────────────
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

    // Routing orthogonal pur avec évitement des formes (toutes connexions, y compris importées)
    let orthopts, d, _usedFp = fp, _usedTp = tp;
    {
      const fk2 = `${c.fromId}-${fdir}`;
      const fUsers2 = fromUsage[fk2] || [];
      const fIdx2 = fUsers2.indexOf(c.id);
      const fN2 = fUsers2.length;
      const bundleOffset = fN2 > 1 ? (fIdx2 - (fN2 - 1) / 2) * 14 : 0;
      const userOffset = c.bendOffset || { dx: 0, dy: 0 };
      orthopts = orthogonalPts(fp, tp, bundleOffset, userOffset);
      orthopts = avoidShapes(orthopts, state.shapes, c.fromId, c.toId);
      orthopts = simplifyPath(orthopts);
      c._computedOrthopts = orthopts; // used for label drag constraint
      // Enregistrer les segments pour pénaliser les labels des connexions suivantes
      for (let _pi = 0; _pi < orthopts.length - 1; _pi++)
        placedPaths.push({ ax: orthopts[_pi].x, ay: orthopts[_pi].y, bx: orthopts[_pi+1].x, by: orthopts[_pi+1].y, connId: c.id });
      d = polylineToPath(orthopts, 12);
    }
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

    // Label : placement par score — évite les coins, les formes, et les croisements.
    // Toujours SUR la flèche (perp=0), aligné sur la direction dominante (H ou V).
    if (c.label) {
      const labelLines = c.label.split('\n');
      const maxLineLen = Math.max(...labelLines.map(l => l.length));
      const lw = Math.max(20, maxLineLen * 6);
      const lineH = 13;
      const lh = lineH * labelLines.length + (labelLines.length > 1 ? 3 : 0);
      let lx, ly, angle = 0;

      // Déterminer la direction dominante de la flèche (H ou V)
      let totalH = 0, totalV = 0;
      for (let i = 0; i < orthopts.length - 1; i++) {
        totalH += Math.abs(orthopts[i+1].x - orthopts[i].x);
        totalV += Math.abs(orthopts[i+1].y - orthopts[i].y);
      }
      const arrowMajorH = totalH >= totalV;

      if (c.labelOffset) {
        lx = c.labelOffset.x;
        ly = c.labelOffset.y;
        angle = arrowMajorH ? 0 : -90;
      } else {
        // Trouver le segment préféré : le plus long dans la direction dominante
        let longestSeg = 0, longestLen = 0, longestForcedSeg = -1, longestForcedLen = 0;
        for (let i = 0; i < orthopts.length - 1; i++) {
          const pa = orthopts[i], pb = orthopts[i + 1];
          const l = Math.hypot(pb.x - pa.x, pb.y - pa.y);
          const segH = Math.abs(pb.y - pa.y) < 2;
          if (l > longestLen) { longestLen = l; longestSeg = i; }
          if (segH === arrowMajorH && l > longestForcedLen) { longestForcedLen = l; longestForcedSeg = i; }
        }
        const preferSeg = longestForcedSeg >= 0 ? longestForcedSeg : longestSeg;

        // Générer des candidats le long des segments dans la direction dominante.
        // perp=0 UNIQUEMENT : le label est toujours sur la flèche, jamais à côté.
        const CANDS = [];
        for (let i = 0; i < orthopts.length - 1; i++) {
          const pa = orthopts[i], pb = orthopts[i + 1];
          const sdx = pb.x - pa.x, sdy = pb.y - pa.y;
          const slen = Math.hypot(sdx, sdy);
          if (slen < 10) continue;
          const isH = Math.abs(sdy) < Math.abs(sdx);
          if (isH !== arrowMajorH) continue;
          const step = (i === preferSeg) ? 0.06 : 0.18;
          for (let t = step; t <= 1 - step; t += step) {
            CANDS.push({ x: pa.x + sdx * t, y: pa.y + sdy * t, isH, onPref: i === preferSeg });
          }
        }
        // Fallback : tous les segments si aucun dans la direction dominante
        if (CANDS.length === 0) {
          for (let i = 0; i < orthopts.length - 1; i++) {
            const pa = orthopts[i], pb = orthopts[i + 1];
            const sdx = pb.x - pa.x, sdy = pb.y - pa.y;
            if (Math.hypot(sdx, sdy) < 4) continue;
            const isH = Math.abs(sdy) < Math.abs(sdx);
            CANDS.push({ x: pa.x + sdx * 0.5, y: pa.y + sdy * 0.5, isH, onPref: false });
          }
        }
        if (CANDS.length === 0) CANDS.push({ x: (fp.x + tp.x) / 2, y: (fp.y + tp.y) / 2, isH: arrowMajorH, onPref: true });

        function labelScore(cx, cy, isH, onPref) {
          const hw2 = isH ? lw / 2 : lh / 2;
          const hh2 = isH ? lh / 2 : lw / 2;
          const M = 8;
          let s = onPref ? 0 : 6000;
          for (const sh of state.shapes) {
            const ox = Math.max(0, Math.min(cx + hw2 + M, sh.x + sh.w) - Math.max(cx - hw2 - M, sh.x));
            const oy = Math.max(0, Math.min(cy + hh2 + M, sh.y + sh.h) - Math.max(cy - hh2 - M, sh.y));
            s += ox * oy * 20;
          }
          for (const pl of placedLabels) {
            const ox = Math.max(0, Math.min(cx + hw2 + M, pl.lx + pl.hw) - Math.max(cx - hw2 - M, pl.lx - pl.hw));
            const oy = Math.max(0, Math.min(cy + hh2 + M, pl.ly + pl.hh) - Math.max(cy - hh2 - M, pl.ly - pl.hh));
            s += ox * oy * 40;
          }
          // Forte pénalité sur les coins/virages du tracé
          for (let k = 1; k < orthopts.length - 1; k++) {
            const cp = orthopts[k];
            const dc = Math.hypot(cx - cp.x, cy - cp.y);
            if (dc < 40) s += (40 - dc) * 350;
          }
          // Pénalité boîte-segment : interdit si la boîte du label chevauche une autre flèche.
          // Utilise la distance du BORD de la boîte au segment (pas du centre), ce qui
          // garantit qu'aucun label ne s'affiche visuellement sur une autre flèche.
          for (const seg of placedPaths) {
            if (seg.connId === c.id) continue; // propre connexion → on peut s'y poser
            const abx = seg.bx - seg.ax, aby = seg.by - seg.ay;
            const segLen2 = abx*abx + aby*aby;
            if (segLen2 < 1) continue;
            const t2 = Math.max(0, Math.min(1, ((cx - seg.ax)*abx + (cy - seg.ay)*aby) / segLen2));
            const px = seg.ax + t2*abx, py = seg.ay + t2*aby;
            // Distance du bord de la boîte au point le plus proche du segment
            const bdx = Math.max(0, Math.abs(cx - px) - hw2);
            const bdy = Math.max(0, Math.abs(cy - py) - hh2);
            const boxDist = Math.hypot(bdx, bdy);
            if (boxDist < 1) s += 800000;           // chevauchement réel → position interdite
            else if (boxDist < 55) s += (55 - boxDist) * 150;
          }
          return s;
        }

        let bestCand = CANDS[0], bestScore = Infinity;
        for (const cand of CANDS) {
          const score = labelScore(cand.x, cand.y, cand.isH, cand.onPref);
          if (score < bestScore) { bestScore = score; bestCand = cand; }
        }
        lx = bestCand.x; ly = bestCand.y;
        angle = bestCand.isH ? 0 : -90;
      }

      const hw = angle !== 0 ? lh / 2 : lw / 2;
      const hh = angle !== 0 ? lw / 2 : lh / 2;
      placedLabels.push({ lx, ly, hw, hh });
      labelQueue.push({ c, lx, ly, angle, lw, lh, lineH, labelLines, color });
    }

    // Poignées d'extrémité (visibles quand la connexion est sélectionnée)
    if (isSel) {
      for (const [pt, which] of [[_usedFp, 'from'], [_usedTp, 'to']]) {
        el('circle', {
          cx: String(pt.x), cy: String(pt.y), r: '8',
          fill: '#1f7a54', stroke: '#ffffff', 'stroke-width': '2.5',
          cursor: 'grab',
          'data-conn-id': String(c.id), 'data-conn-end': which,
          style: 'pointer-events:all',
        }, gConns);
      }
      // Poignée de coude (ajustement manuel du tracé orthogonal)
      if (routing === 'orthogonal' && orthopts.length >= 4) {
        const midPtIdx = Math.floor((orthopts.length - 1) / 2);
        const bpa = orthopts[midPtIdx], bpb = orthopts[midPtIdx + 1];
        const bpx = (bpa.x + bpb.x) / 2, bpy = (bpa.y + bpb.y) / 2;
        const isHorizSeg = Math.abs(bpb.y - bpa.y) < Math.abs(bpb.x - bpa.x);
        el('circle', {
          cx: String(bpx), cy: String(bpy), r: '6',
          fill: '#ffffff', stroke: '#1f7a54', 'stroke-width': '2',
          cursor: isHorizSeg ? 'ns-resize' : 'ew-resize',
          'data-conn-bend': String(c.id),
          style: 'pointer-events:all',
        }, gConns);
      }
    }
  }

  // ── Passe 2 : labels par-dessus tous les chemins ─────────────────────────
  for (const { c, lx, ly, angle, lw, lh, lineH, labelLines, color } of labelQueue) {
    const lg = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    lg.setAttribute('transform', `translate(${lx},${ly}) rotate(${angle})`);
    lg.setAttribute('data-conn-label-id', String(c.id));
    lg.style.cursor = 'grab';
    el('rect', {
      x: String(-lw / 2), y: String(-lh / 2), width: String(lw), height: String(lh),
      rx: '3', fill: 'rgba(255,255,255,0.96)',
    }, lg);
    if (labelLines.length === 1) {
      txt(c.label, {
        x: '0', y: '0',
        'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: color, 'font-size': '14', 'font-family': 'Segoe UI, sans-serif', 'font-weight': '600',
      }, lg);
    } else {
      const textEl = el('text', { 'text-anchor': 'middle', fill: color, 'font-size': '14', 'font-family': 'Segoe UI, sans-serif', 'font-weight': '600' }, lg);
      labelLines.forEach((line, i) => {
        const ts = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
        ts.setAttribute('x', '0');
        ts.setAttribute('y', String((i - (labelLines.length - 1) / 2) * lineH));
        ts.setAttribute('dominant-baseline', 'middle');
        ts.textContent = line;
        textEl.appendChild(ts);
      });
    }
    gConns.appendChild(lg);
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
      cursor: window.OPTIQCARTO_READONLY ? 'pointer' : (tool === 'connect' ? 'crosshair' : 'pointer'),
    }, gShapes);

    // Shadow filter
    const filterAttr = isSel ? 'url(#f-shadow-sel)' : 'url(#f-shadow)';

    // ── Draw shape ──────────────────────────────
    let shapeEl;

    if (s.type === 'process') {
      const isExternal = s.subtype === 'external';
      const isExtCo    = s.subtype === 'extco';
      const haloGap = 7;
      const shapeRx = isExternal ? s.h / 2 : 16;
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

    // ── Port handles (masqués en lecture seule) ──
    if (isHover && !portDrag && !window.OPTIQCARTO_READONLY) {
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
            selectShape(s.id, false, false);
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

    const sorted = [...state.shapes].sort((a, b) =>
      (a.label || '').localeCompare(b.label || '', 'fr', { sensitivity: 'base' })
    );
    sorted.forEach(s => {
      const isSel = selectedShapes.has(s.id);
      const item = document.createElement('div');
      item.className = 'cmap-item' + (isSel ? ' selected' : '');
      item.innerHTML = `<span class="cmap-color-swatch" style="background:${s.color}"></span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.label || '(sans label)'}</span>`;
      item.addEventListener('click', () => {
        selectShape(s.id, false, false);
        focusOnShape(s, true);
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

    const connSorted = [...state.connections].sort((a, b) => {
      const la = a.label || (state.shapes.find(s => s.id === a.fromId)?.label || '') + ' → ' + (state.shapes.find(s => s.id === a.toId)?.label || '');
      const lb = b.label || (state.shapes.find(s => s.id === b.fromId)?.label || '') + ' → ' + (state.shapes.find(s => s.id === b.toId)?.label || '');
      return la.localeCompare(lb, 'fr', { sensitivity: 'base' });
    });
    connSorted.forEach(c => {
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

  // ── Mode lecture seule : pan + shape-click → postMessage uniquement ──
  if (window.OPTIQCARTO_READONLY) {
    const shapeTarget = e.target.closest('[data-type="shape"]');
    if (shapeTarget) {
      const sid = parseInt(shapeTarget.getAttribute('data-id'));
      const s = state.shapes.find(s => s.id === sid);
      if (s) try { window.parent.postMessage({ t: 'shape-click', label: s.label, shapeId: s.id, shapeType: s.type }, '*'); } catch(_) {}
      return;
    }
    isPanning = true;
    panStart = { sx: e.clientX, sy: e.clientY, vpX, vpY, moved: false };
    return;
  }

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
  /* ── Select tool ── */
  if (tool === 'select') {
    // Drag du label d'une connexion
    const labelEl = e.target.closest('[data-conn-label-id]');
    if (labelEl) {
      const cid = parseInt(labelEl.getAttribute('data-conn-label-id'));
      if (state.connections.find(c => c.id === cid)) {
        labelDrag = { connId: cid };
        canvas.style.cursor = 'grabbing';
      }
      return;
    }

    // Drag d'un coude de connexion (ajustement du tracé)
    const bendEl = e.target.closest('[data-conn-bend]');
    if (bendEl) {
      const cid = parseInt(bendEl.getAttribute('data-conn-bend'));
      const { x, y } = screenToSVG(e.clientX, e.clientY);
      const conn = state.connections.find(c => c.id === cid);
      const startOffset = conn && conn.bendOffset ? { ...conn.bendOffset } : { dx: 0, dy: 0 };
      bendDrag = { connId: cid, startX: x, startY: y, startOffset };
      canvas.style.cursor = 'grabbing';
      return;
    }

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
      selectShape(sid, e.shiftKey, false);
      if (!propsOpen) setPropsOpen(true);

      // Prepare drag
      dragData = {
        mx: x, my: y, moved: false,
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
        if (wouldBeBackwards(connecting.fromId, sid)) {
          showToast('⛔ Une flèche ne peut pas revenir en arrière (flèche → droite seulement)');
        } else {
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
          _checkRenvoiAutoLink(connecting.fromId, sid);
          snapshot();
        }
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

  /* ── Drag d'un label de connexion (contraint au polyline) ── */
  if (labelDrag) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    const conn = state.connections.find(c => c.id === labelDrag.connId);
    if (conn) {
      if (conn._computedOrthopts && conn._computedOrthopts.length >= 2) {
        conn.labelOffset = snapToPolyline(conn._computedOrthopts, x, y, 0);
      } else {
        conn.labelOffset = { x, y };
      }
      render();
    }
    return;
  }

  /* ── Drag d'un coude de connexion ── */
  if (bendDrag) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    const conn = state.connections.find(c => c.id === bendDrag.connId);
    if (conn) {
      conn.bendOffset = {
        dx: bendDrag.startOffset.dx + (x - bendDrag.startX),
        dy: bendDrag.startOffset.dy + (y - bendDrag.startY),
      };
      render();
    }
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
    if (Math.abs(dx) > 1 || Math.abs(dy) > 1) dragData.moved = true;
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
  /* ── Fin du drag d'un label ── */
  if (labelDrag) {
    labelDrag = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    snapshot();
    render();
    return;
  }

  /* ── Fin du drag d'un coude ── */
  if (bendDrag) {
    bendDrag = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    snapshot();
    render();
    return;
  }

  /* ── Fin du drag d'extrémité de connexion ── */
  if (connEndDrag) {
    const { connId, which, snapShapeId, snapDir, snapT } = connEndDrag;
    connEndDrag = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    if (snapShapeId && snapDir) {
      const conn = state.connections.find(c => c.id === connId);
      if (conn) {
        const newFromId = which === 'from' ? snapShapeId : conn.fromId;
        const newToId   = which === 'to'   ? snapShapeId : conn.toId;
        if (wouldBeBackwards(newFromId, newToId)) {
          showToast('⛔ Une flèche ne peut pas revenir en arrière (flèche → droite seulement)');
        } else {
          if (which === 'from') {
            conn.fromId      = snapShapeId;
            conn.fromPortDir = snapDir;
            conn.fromPortT   = snapT;
            const src = state.shapes.find(s => s.id === snapShapeId);
            if (src) conn.color = src.color;
          } else {
            conn.toId      = snapShapeId;
            conn.toPortDir = snapDir;
            conn.toPortT   = snapT;
          }
          snapshot();
        }
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
        if (wouldBeBackwards(portDrag.fromShapeId, target.id)) {
          showToast('⛔ Une flèche ne peut pas revenir en arrière (flèche → droite seulement)');
        } else {
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
        _checkRenvoiAutoLink(portDrag.fromShapeId, target.id);
        snapshot();
        }
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
      if (dragData.moved) {
        // Seulement si mouvement réel : recalculer la couleur de bande
        for (const { id } of dragData.shapes) {
          const s = state.shapes.find(s => s.id === id);
          if (s) updateShapeColor(s);
        }
        snapshot();
        render();
      }
      dragData = null;
    }
  }
}

function onDbl(e) {
  if (window.OPTIQCARTO_READONLY) return;
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
  const step   = _zoomSens / 100;
  const factor = e.deltaY < 0 ? (1 + step) : (1 / (1 + step));
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
  if (s) {
    s.label = labelEd.value.trim();
    if (s.type === 'start-end') _updateRenvoiColor(s);
    snapshot(); render();
  }
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
      if (selectedShapes.size >= 2) {
        alignSec.style.display = '';
        alignSec.style.opacity = '';
        alignSec.style.transform = '';
        alignSec.style.transition = '';
        const countEl = document.getElementById('prop-align-count');
        if (countEl) countEl.textContent = selectedShapes.size;
        alignSec.querySelectorAll('.align-btn').forEach(btn => {
          btn.style.background = 'linear-gradient(160deg,#4DB868 0%,#389E52 100%)';
          btn.style.border = '2px solid #389E52';
          btn.style.color = '#fff';
        });
      } else {
        alignSec.style.display = 'none';
      }
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
    for (const id of selectedShapes) {
      const s = state.shapes.find(s => s.id === id);
      if (!s) continue;
      s.label = v;
      if (s.type === 'start-end') _updateRenvoiColor(s);
    }
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

  // Connection — style trait (propagé au miroir renvoi si présent)
  document.querySelectorAll('input[name="conn-style"]').forEach(r => {
    r.addEventListener('change', e => {
      const c = state.connections.find(c => c.id === selectedConn);
      if (!c) return;
      c.style = e.target.value;
      const mirror = c.mirrorConnId != null && state.connections.find(m => m.id === c.mirrorConnId);
      if (mirror) mirror.style = c.style;
      snapshot(); render();
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
    if (!c) return;
    c.label = v;
    const mirror = c.mirrorConnId != null && state.connections.find(m => m.id === c.mirrorConnId);
    if (mirror) mirror.label = v;
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
  if (typeof resetHighlightExtco === 'function') resetHighlightExtco();
  state.shapes = [];
  state.connections = [];
  state.groups = [];
  state.bands = _defaultBands();
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

function _showSaveWarningModal(diff) {
  return new Promise(resolve => {
    const modal    = document.getElementById('save-warning-modal');
    const listEl   = document.getElementById('swm-removed-list');
    const confirmBtn = document.getElementById('swm-confirm');
    const cancelBtn  = document.getElementById('swm-cancel');
    if (!modal) { resolve(true); return; }

    listEl.innerHTML = '';
    const all = [
      ...(diff.removed_activities || []).map(n => ({ label: n, icon: 'fa-square-check', cat: 'Activité' })),
      ...(diff.removed_roles      || []).map(n => ({ label: n, icon: 'fa-layer-group',   cat: 'Rôle'   })),
    ];
    all.forEach(({ label, icon, cat }) => {
      const li = document.createElement('li');
      li.innerHTML = `<i class="fa-solid ${icon}"></i><span class="swm-cat">${cat}</span>${label}`;
      listEl.appendChild(li);
    });

    modal.classList.remove('hidden');

    const cleanup = () => {
      modal.classList.add('hidden');
      confirmBtn.removeEventListener('click', onConfirm);
      cancelBtn.removeEventListener('click',  onCancel);
    };
    const onConfirm = () => { cleanup(); resolve(true);  };
    const onCancel  = () => { cleanup(); resolve(false); };
    confirmBtn.addEventListener('click', onConfirm);
    cancelBtn.addEventListener('click',  onCancel);
  });
}

async function saveJSON() {
  const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';

  _showSavePopup('saving');

  try {
    const res  = await fetch(`${apiBase}/api/save`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ diagram: state }),
    });
    const data = await res.json();
    if (data.ok) {
      _showSavePopup('done');
      if (data.sync_warning) setTimeout(() => showToast('Erreur sync : ' + data.sync_warning, 'warn'), 1600);
    } else {
      _hideSavePopup();
      showToast('Erreur : ' + (data.error || 'inconnue'));
    }
  } catch (err) {
    _hideSavePopup();
    showToast('Erreur réseau lors de la sauvegarde');
  }
}

function _showSavePopup(state) {
  const overlay = document.getElementById('save-progress-popup');
  if (!overlay) return;
  overlay.style.display = 'flex';
  const saving = document.getElementById('save-popup-saving');
  const done   = document.getElementById('save-popup-done');
  if (saving) saving.style.display = state === 'saving' ? 'flex' : 'none';
  if (done)   done.style.display   = state === 'done'   ? 'flex' : 'none';
  if (state === 'done') setTimeout(_hideSavePopup, 1600);
}

function _hideSavePopup() {
  const overlay = document.getElementById('save-progress-popup');
  if (overlay) overlay.style.display = 'none';
}

async function openLoadDialog() {
  const dialog = document.getElementById('load-dialog');
  const list   = document.getElementById('load-list');
  dialog.classList.remove('hidden');

  const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
  const files = await fetch(apiBase + '/api/list').then(r => r.json());
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
      const data = await fetch(`${apiBase}/api/load/${encodeURIComponent(name)}`).then(r => r.json());
      if (data.error) { showToast('Erreur : ' + data.error); return; }
      state = data;
      if (typeof resetHighlightExtco === 'function') resetHighlightExtco();
      // Supprimer uniquement les connexions dont une extrémité n'existe plus
      if (state.connections && state.shapes) {
        const validIds = new Set([
          ...state.shapes.map(s => s.id),
          ...(state.groups || []).map(g => g.id),
        ]);
        state.connections = state.connections.filter(c => validIds.has(c.fromId) && validIds.has(c.toId));
      }
      // Migration : champs manquants sur anciens fichiers
      if (!state.bandWidth) state.bandWidth = 3200;
      if (!state.groups) state.groups = [];
      groupHighlightId = null; selectedGroup = null; expandedGroups.clear();
      state.bands.forEach(b => {
        delete b.textColor; // supprimé — couleur texte toujours blanc
        if (!b.color) b.color = '#22c55e'; // couleur absente seulement
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
      await fetch(`${apiBase}/api/delete/${encodeURIComponent(name)}`, { method: 'DELETE' });
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
    'start-end': { w: 90,  h: 90  },
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

// After render(), snap each decision diamond's center to the nearest point
// on any rendered connection path (uses _computedOrthopts set by renderConnections).
// Called once after VSDX import so diamonds align pixel-perfectly with arrows
// even when orthogonal routing deviates from the original Visio connector path.
function snapDecisionsToArrows() {
  const THRESH = 130; // px — max distance to consider an arrow "matching"
  let moved = false;
  for (const s of state.shapes) {
    if (s.type !== 'decision') continue;
    const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
    let bestDist = THRESH, bestPx = cx, bestPy = cy;
    for (const c of state.connections) {
      const pts = c._computedOrthopts;
      if (!pts || pts.length < 2) continue;
      for (let i = 0; i < pts.length - 1; i++) {
        const ax = pts[i].x, ay = pts[i].y, bx = pts[i+1].x, by = pts[i+1].y;
        const abx = bx - ax, aby = by - ay;
        const len2 = abx*abx + aby*aby;
        if (len2 < 4) continue;
        const t = Math.max(0, Math.min(1, ((cx - ax)*abx + (cy - ay)*aby) / len2));
        const px = ax + t*abx, py = ay + t*aby;
        const d = Math.hypot(cx - px, cy - py);
        if (d < bestDist) { bestDist = d; bestPx = px; bestPy = py; }
      }
    }
    if (bestDist < THRESH) {
      s.x = Math.round(bestPx - s.w / 2);
      s.y = Math.round(bestPy - s.h / 2);
      moved = true;
    }
  }
  if (moved) renderShapes();
}

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

/* ══════════════════════════════════════════════════
   POST-PROCESSING : routage flèches après import VSDX
   Ports EXACTS (réplication de _resolveEp + spreadPort + bundleOffset).
   Formule : bendOffset.dy = targetMidY - safeMid - bundleOffset → 0px d'erreur.
   Phase 1 — Shape avoidance : contourner les formes intermédiaires.
   Passe finale — Vérification stricte : aucune flèche ne peut traverser
                  un process (activité) ou un start-end (rond).
   ══════════════════════════════════════════════════ */
function reroutePostProcess(shapes, connections) {
  const OPP = { right:'left', left:'right', top:'bottom', bottom:'top' };
  const PAD  = 12; // marge détection et dégagement

  // ── Réplication exacte de _resolveEp ────────────────────────
  function resolveEp(eid) {
    const s = shapes.find(s => s.id === eid);
    if (!s) return null;
    return { id: s.id, x: s.x, y: s.y, w: s.w, h: s.h,
             _halo: s.type === 'process' ? 7 : 0, _type: s.type };
  }

  // ── fromUsage + unifiedUsage (identiques à renderConnections) ─
  const fromUsage = {}, unifiedUsage = {};
  for (const c of connections) {
    const from = resolveEp(c.fromId), to = resolveEp(c.toId);
    if (!from || !to) continue;
    const dx = (to.x + to.w/2) - (from.x + from.w/2);
    const dy = (to.y + to.h/2) - (from.y + from.h/2);
    const fdir = c.fromPortDir || (Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top'));
    const tdir = c.toPortDir || OPP[fdir];
    const fk = `${c.fromId}-${fdir}`, tk = `${c.toId}-${tdir}`;
    if (!fromUsage[fk])    fromUsage[fk] = [];    fromUsage[fk].push(c.id);
    if (!unifiedUsage[fk]) unifiedUsage[fk] = []; unifiedUsage[fk].push({ connId: c.id, end: 'from' });
    if (!unifiedUsage[tk]) unifiedUsage[tk] = []; unifiedUsage[tk].push({ connId: c.id, end: 'to' });
  }

  // ── spreadPort exact (identique à renderConnections) ────────
  function spreadPort(ep, dir, connId, end, explicitT) {
    const h = ep._halo || 0;
    const cx = ep.x + ep.w / 2, cy = ep.y + ep.h / 2;
    if (ep._type === 'decision') {
      switch (dir) {
        case 'left':   return { x: ep.x,        y: cy,          dir: 'left'   };
        case 'right':  return { x: ep.x + ep.w, y: cy,          dir: 'right'  };
        case 'top':    return { x: cx,           y: ep.y,        dir: 'top'    };
        case 'bottom': return { x: cx,           y: ep.y + ep.h, dir: 'bottom' };
      }
    }
    const key = `${ep.id}-${dir}`;
    const users = unifiedUsage[key] || [];
    const idx = users.findIndex(u => u.connId === connId && u.end === end);
    const n = users.length;
    const t = explicitT !== undefined ? explicitT : (n <= 1 ? 0.5 : (idx + 1) / (n + 1));
    switch (dir) {
      case 'left':   return { x: ep.x - h,           y: ep.y + ep.h * t, dir: 'left'   };
      case 'right':  return { x: ep.x + ep.w + h,    y: ep.y + ep.h * t, dir: 'right'  };
      case 'top':    return { x: ep.x + ep.w * t,    y: ep.y - h,        dir: 'top'    };
      case 'bottom': return { x: ep.x + ep.w * t,    y: ep.y + ep.h + h, dir: 'bottom' };
    }
  }

  // ── Construire les infos par connexion H→H ───────────────────
  const infos = [];
  for (const c of connections) {
    if (c.routing !== 'orthogonal') continue;
    const from = resolveEp(c.fromId), to = resolveEp(c.toId);
    if (!from || !to) continue;
    const dx = (to.x + to.w/2) - (from.x + from.w/2);
    const dy = (to.y + to.h/2) - (from.y + from.h/2);
    const fdir = c.fromPortDir || (Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top'));
    const tdir = c.toPortDir || OPP[fdir];
    const fp = spreadPort(from, fdir, c.id, 'from', c.fromPortT);
    const tp = spreadPort(to,   tdir, c.id, 'to',   c.toPortT);

    // bundleOffset exact
    const fk = `${c.fromId}-${fdir}`;
    const fUsers = fromUsage[fk] || [];
    const fIdx = fUsers.indexOf(c.id), fN = fUsers.length;
    const bundleOffset = fN > 1 ? (fIdx - (fN - 1) / 2) * 14 : 0;

    // safeMid = midY sans aucun offset (base de calcul)
    const ptsNat = orthogonalPts(fp, tp, 0, { dx: 0, dy: 0 });
    if (ptsNat.length < 6 || Math.abs(ptsNat[2].y - ptsNat[3].y) > 2) continue;
    const safeMid = ptsNat[2].y;
    const x1 = Math.min(ptsNat[2].x, ptsNat[3].x);
    const x2 = Math.max(ptsNat[2].x, ptsNat[3].x);
    if (x2 - x1 < 4) continue;

    // renderedMidY = safeMid + bundleOffset + bendOffset.dy  (exactement 0px d'erreur)
    const curDy = (c.bendOffset || { dy: 0 }).dy || 0;
    infos.push({ c, safeMid, bundleOffset, x1, x2,
                 renderedMidY: safeMid + bundleOffset + curDy });
  }

  // ── Helpers ──────────────────────────────────────────────────

  // Applique un midY cible avec la formule exacte (0px d'erreur)
  function applyMidY(info, targetMidY) {
    const newDy = targetMidY - info.safeMid - info.bundleOffset;
    info.c.bendOffset = { dx: (info.c.bendOffset || { dx: 0 }).dx || 0, dy: newDy };
    info.renderedMidY = targetMidY;
  }

  // Teste si un midY donné touche une forme intermédiaire (excl. endpoints)
  function hitsAny(midY, x1, x2, fromId, toId) {
    return shapes.some(s => {
      if (s.id === fromId || s.id === toId) return false;
      return midY > s.y - PAD && midY < s.y + s.h + PAD
          && x2   > s.x + PAD && x1   < s.x + s.w - PAD;
    });
  }

  // Teste si un midY touche SPÉCIFIQUEMENT un process ou start-end (les formes "bloquantes")
  function hitsActivity(midY, x1, x2, fromId, toId) {
    return shapes.some(s => {
      if (s.id === fromId || s.id === toId) return false;
      if (s.type !== 'process' && s.type !== 'start-end') return false;
      return midY > s.y - PAD && midY < s.y + s.h + PAD
          && x2   > s.x + PAD && x1   < s.x + s.w - PAD;
    });
  }

  // Trouve la Y la plus proche de refY qui ne touche rien
  // Candidates : bords de toutes les formes potentiellement gênantes
  function findClearY(refY, x1, x2, fromId, toId, strict = false) {
    const testFn = strict ? hitsActivity : hitsAny;
    if (!testFn(refY, x1, x2, fromId, toId)) return refY;
    const cands = [];
    for (const s of shapes) {
      if (s.id === fromId || s.id === toId) continue;
      if (strict && s.type !== 'process' && s.type !== 'start-end') continue;
      if (x2 <= s.x + PAD || x1 >= s.x + s.w - PAD) continue;
      cands.push(s.y - PAD, s.y + s.h + PAD);
    }
    cands.sort((a, b) => Math.abs(a - refY) - Math.abs(b - refY));
    for (const y of cands) {
      if (!testFn(y, x1, x2, fromId, toId)) return y;
    }
    return refY; // pas de position libre → on laisse (on aura tenté)
  }

  // ── Phase 1 : évitement général des formes ───────────────────
  for (const info of infos) {
    const { c, x1, x2, renderedMidY } = info;
    if (!hitsAny(renderedMidY, x1, x2, c.fromId, c.toId)) continue;
    const target = findClearY(renderedMidY, x1, x2, c.fromId, c.toId, false);
    if (target !== renderedMidY) applyMidY(info, target);
  }

  // ── Passe finale : vérification stricte process + start-end ──
  // Règle absolue : aucune flèche ne peut traverser une activité ou un rond.
  // On re-vérifie et on force le contournement même si phase 1 n'a pas suffi.
  for (const info of infos) {
    const { c, x1, x2, renderedMidY } = info;
    if (!hitsActivity(renderedMidY, x1, x2, c.fromId, c.toId)) continue;
    const target = findClearY(renderedMidY, x1, x2, c.fromId, c.toId, true);
    if (target !== renderedMidY) applyMidY(info, target);
  }
}

async function importVSDX(file) {
  if (!window.JSZip) { showToast('JSZip non disponible'); return; }

  const statusEl  = document.getElementById('vsdx-status');
  const loadingEl = document.getElementById('vsdx-loading');
  const loadingMsg = document.getElementById('vsdx-loading-msg');
  const dropzone  = document.getElementById('vsdx-dropzone');

  function setStatus(msg, isError) {
    if (isError) {
      loadingEl.style.display = 'none';
      dropzone.style.display = '';
      statusEl.style.display = '';
      statusEl.className = 'vsdx-status error';
      statusEl.textContent = msg;
    } else if (msg) {
      if (loadingMsg) loadingMsg.textContent = msg;
    } else {
      statusEl.style.display = 'none';
      loadingEl.style.display = 'none';
    }
  }

  dropzone.style.display = 'none';
  statusEl.style.display = 'none';
  loadingEl.style.display = '';
  if (loadingMsg) loadingMsg.textContent = 'Lecture du fichier\u2026';

  // Orphan dialog: runs inside vsdxParse before final layout
  async function onOrphans(orphans) {
    setStatus(`\u26a0 ${orphans.length} forme(s) vide(s) non connect\u00e9e(s) d\u00e9tect\u00e9e(s).`);
    await new Promise(r => setTimeout(r, 0));
    return new Promise(resolve => {
      const ov = document.createElement('div');
      ov.className = 'modal-overlay';
      ov.style.zIndex = '10000';
      const types = [...new Set(orphans.map(s =>
        s.type === 'decision' ? 'losange' : s.type === 'start-end' ? 'ellipse' : 'activit\u00e9'
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
              <span style="font-size:12px;color:rgba(255,255,255,0.35)">Ces \u00e9l\u00e9ments sont probablement des artefacts Visio sans contenu.</span>
            </p>
            <p style="font-size:12px;color:rgba(255,255,255,0.38);margin:0">
              Voulez-vous nettoyer ces \u00e9l\u00e9ments ou fournir un fichier corrig\u00e9&nbsp;?
            </p>
            <div style="display:flex;flex-direction:column;gap:7px">
              <button id="_orph-clean" class="btn-ok" style="width:100%;text-align:left;display:flex;align-items:center;gap:9px;padding:11px 14px;border-radius:10px">
                <i class="fa-solid fa-broom"></i> Nettoyer et continuer l\u2019import
              </button>
              <button id="_orph-keep" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);color:var(--text-muted);border-radius:10px;padding:10px 14px;font-size:12px;font-weight:600;cursor:pointer;text-align:left;display:flex;align-items:center;gap:9px;font-family:inherit;width:100%">
                <i class="fa-solid fa-forward"></i> Continuer sans nettoyer
              </button>
              <button id="_orph-cancel" style="background:transparent;border:none;color:rgba(244,184,208,0.5);padding:8px 14px;font-size:11px;cursor:pointer;text-align:left;display:flex;align-items:center;gap:9px;font-family:inherit;width:100%">
                <i class="fa-solid fa-xmark"></i> Annuler \u2014 je vais corriger mon fichier
              </button>
            </div>
          </div>
        </div>`;
      document.body.appendChild(ov);
      ov.querySelector('#_orph-clean').onclick  = () => { ov.remove(); resolve('clean'); };
      ov.querySelector('#_orph-keep').onclick   = () => { ov.remove(); resolve('keep'); };
      ov.querySelector('#_orph-cancel').onclick = () => { ov.remove(); resolve('cancel'); };
    });
  }

  const debugMode = document.getElementById('vsdx-debug-mode')?.checked || false;

  try {
    const result = await vsdxParse(file, setStatus, onOrphans, debugMode);
    if (!result) {
      setStatus('Import annul\u00e9. Vous pouvez d\u00e9poser un fichier corrig\u00e9.', true);
      return;
    }

    const { bands, shapes, connections, groups, nextOid } = result;
    if (shapes.length === 0) {
      setStatus('Aucune activit\u00e9 trouv\u00e9e dans ce fichier.', true);
      return;
    }

    // Apply to state — do NOT call updateShapeColor: importer already set correct colors
    clearSelection();
    if (typeof resetHighlightExtco === 'function') resetHighlightExtco();
    state.shapes      = shapes;
    state.connections = connections;
    state.groups      = groups;
    state.bands       = bands;   // bandes telles qu'importées depuis le VSDX, rien d'autre
    state.bandWidth   = Math.max(3200, Math.round(shapes.reduce((m, s) => Math.max(m, s.x + s.w), 0) + 300));
    state.nextId      = nextOid + 1;

    // Propagate shape colors to outgoing connections
    state.connections.forEach(c => {
      const from = state.shapes.find(s => s.id === c.fromId);
      if (from) c.color = from.color;
    });

    history = [JSON.stringify(state)]; histIndex = 0;
    render();
    snapDecisionsToArrows(); // centre les losanges sur la flèche la plus proche
    fitView(); updateProps();

    document.getElementById('vsdx-dialog').classList.add('hidden');
    setStatus('');
    renderBandsTbList();  // rafra\u00eechir le dropdown avec les bandes import\u00e9es
    const nCustom = connections.filter(c => c.customPath).length;
    console.log(`[VSDX] ${shapes.length} formes, ${connections.length} connexions, ${nCustom} chemins Visio exacts, ${groups.length} groupes`);
    showToast(`Import r\u00e9ussi \u2014 ${shapes.length} activit\u00e9s \u00b7 ${connections.length} connexions \u00b7 ${bands.length} bandes`);

    // Debug report download
    if (result.debugHtml) {
      const blob = new Blob([result.debugHtml], { type: 'text/html;charset=utf-8' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = (file.name || 'import').replace(/\.vsdx$/i, '') + '_debug.html';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Rapport de d\u00e9bogage t\u00e9l\u00e9charg\u00e9');
    }

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

function _deleteBand(idx) {
  const band = state.bands[idx];
  if (!band || band.deleted) return false;
  // Compute y range of this band (skip deleted bands above it)
  let bandY = -200;
  for (let j = 0; j < idx; j++) {
    if (!state.bands[j].deleted) bandY += state.bands[j].height;
  }
  const bandYEnd = bandY + band.height;
  const shapesInBand = state.shapes.filter(s => {
    const midY = s.y + s.h / 2;
    return midY >= bandY && midY < bandYEnd;
  });
  if (shapesInBand.length > 0) {
    const names = shapesInBand.map(s => `• ${s.label || 'Forme sans nom'}`).join('\n');
    if (!confirm(`Supprimer la bande « ${band.label} » ?\n\nCela supprimera aussi :\n${names}`)) return false;
    const ids = new Set(shapesInBand.map(s => s.id));
    state.shapes = state.shapes.filter(s => !ids.has(s.id));
    state.connections = state.connections.filter(c => !ids.has(c.fromId) && !ids.has(c.toId));
  }
  // Soft-delete : la bande reste dans state.bands mais n'est plus rendue
  band.deleted = true;
  snapshot();
  render();
  return true;
}

function _restoreBand(idx) {
  const band = state.bands[idx];
  if (!band || !band.deleted) return;
  band.deleted = false;
  snapshot();
  render();
}

function renderBandsTbList() {
  const list = document.getElementById('bands-tb-list');
  if (!list) return;
  list.innerHTML = '';
  state.bands.forEach((band, i) => {
    const row = document.createElement('div');
    row.className = 'bands-tb-row' + (band.deleted ? ' deleted' : '');
    if (band.deleted) {
      row.innerHTML = `
        <div class="bands-tb-swatch" style="background:${band.color}"></div>
        <span class="bands-tb-row-label">${band.label || 'Bande ' + (i + 1)}</span>
        <button class="bands-tb-restore" data-i="${i}" title="Restaurer">+</button>`;
    } else {
      row.innerHTML = `
        <div class="bands-tb-swatch" style="background:${band.color}"></div>
        <span class="bands-tb-row-label">${band.label || 'Bande ' + (i + 1)}</span>
        <button class="bands-tb-del" data-i="${i}" title="Masquer">×</button>`;
    }
    list.appendChild(row);
  });
  list.querySelectorAll('.bands-tb-del').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.stopPropagation();
      if (_deleteBand(parseInt(ev.target.dataset.i))) {
        renderBandsTbList();
        renderBandsList();
      }
    });
  });
  list.querySelectorAll('.bands-tb-restore').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.stopPropagation();
      _restoreBand(parseInt(ev.target.dataset.i));
      renderBandsTbList();
      renderBandsList();
    });
  });
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
    if (_deleteBand(parseInt(ev.target.dataset.i))) {
      renderBandsList();
      renderBandsTbList();
    }
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
  // On exclut les éléments display:none (ils n'ont pas d'animation d'entrée et
  // garderaient des styles de fermeture quand ils redeviendraient visibles)
  const items = Array.from(panel.children).filter(
    el => !el.classList.contains('panel-prelayers') && getComputedStyle(el).display !== 'none'
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
        <i class="fa-solid fa-wand-magic-sparkles" style="color:#4db868;margin-right:9px"></i>Architecte IA en cours…
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

  try {
    archStatus('Analyse de la cartographie…', 15);
    await new Promise(r => setTimeout(r, 0));

    const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
    archStatus("Transmission à l'IA…", 30);

    const res = await fetch(`${apiBase}/api/architect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state }),
    });

    archStatus('Traitement IA…', 60);
    const data = await res.json();

    if (data.error) {
      showToast('Architecte IA : ' + data.error);
      return;
    }

    archStatus('Application du layout…', 85);
    await new Promise(r => setTimeout(r, 0));

    for (const pos of (data.positions || [])) {
      const s = state.shapes.find(s => s.id === pos.id);
      if (s) { s.x = Math.round(pos.x); s.y = Math.round(pos.y); }
    }

    state.shapes.forEach(s => updateShapeColor(s));
    state.connections.forEach(c => {
      const from = state.shapes.find(s => s.id === c.fromId);
      if (from) c.color = from.color;
    });
    state.bandWidth = Math.max(1400, Math.round(
      state.shapes.reduce((m, s) => Math.max(m, s.x + s.w), 0) + 300
    ));

    // ── Snap quasi-alignements (post-IA) ──────────────────────
    archStatus('Alignement final…', 97);
    await new Promise(r => setTimeout(r, 0));
    {
      const THRESH_H = 22, THRESH_V = 28;
      for (const c of state.connections) {
        const from = state.shapes.find(s => s.id === c.fromId);
        const to   = state.shapes.find(s => s.id === c.toId);
        if (!from || !to) continue;
        const fromCx = from.x + from.w / 2, fromCy = from.y + from.h / 2;
        const toCx   = to.x   + to.w   / 2, toCy   = to.y   + to.h   / 2;
        if (Math.abs(fromCy - toCy) > 0.5 && Math.abs(fromCy - toCy) <= THRESH_H) {
          const gB = s2 => { let y = -200; for (const b of state.bands) { if (s2.y + s2.h / 2 >= y && s2.y + s2.h / 2 < y + b.height) return b; y += b.height; } return null; };
          if (gB(from) === gB(to)) {
            const avg = Math.round((fromCy + toCy) / 2);
            from.y = avg - Math.round(from.h / 2);
            to.y   = avg - Math.round(to.h   / 2);
          }
        }
        if (Math.abs(fromCx - toCx) > 0.5 && Math.abs(fromCx - toCx) <= THRESH_V) {
          const avg = Math.round((fromCx + toCx) / 2);
          from.x = Math.max(INDEX_W_SVG + 4, avg - Math.round(from.w / 2));
          to.x   = Math.max(INDEX_W_SVG + 4, avg - Math.round(to.w   / 2));
        }
      }
    }

    archStatus("C'est bon !", 100);
    await new Promise(r => setTimeout(r, 280));

  } catch (err) {
    console.error('architectLayout error:', err);
    showToast('Erreur architecte IA : ' + err.message);
    clearSelection();
    render();
    updateProps();
    return;
  } finally {
    overlay.remove();
  }

  clearSelection();
  render();
  updateProps();
  showToast('Optimisation IA terminée');
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
    } else if (btn.dataset.tool === 'connect') {
      // Le bouton Connecter est désormais un toggle "mise en évidence des
      // activités hachurées" (cf. highlight-mode.js). Le mode connexion
      // reste accessible via le raccourci clavier C.
      btn.addEventListener('click', () => {
        if (typeof toggleHighlightExtco === 'function') toggleHighlightExtco();
      });
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

  // ── Popup sensibilité zoom ────────────────────────────────────────────────
  (function() {
    const pill    = document.getElementById('zoom-pill');
    const popup   = document.getElementById('zoom-sensitivity-popup');
    const slider  = document.getElementById('zsens-slider');
    const numInput = document.getElementById('zsens-value');
    if (!pill || !popup || !slider || !numInput) return;

    function _setZoomSens(v) {
      v = Math.max(3, Math.min(30, Math.round(v)));
      _zoomSens = v;
      slider.value  = v;
      numInput.value = v;
      localStorage.setItem('optiqcarto-zoom-sens', String(v));
    }
    _setZoomSens(_zoomSens); // initialise avec la valeur restaurée

    pill.addEventListener('click', e => {
      e.stopPropagation();
      popup.classList.toggle('open');
    });
    slider.addEventListener('input', () => _setZoomSens(slider.value));
    numInput.addEventListener('input', () => _setZoomSens(numInput.value));
    numInput.addEventListener('change', () => _setZoomSens(numInput.value));
    document.addEventListener('click', e => {
      if (!popup.contains(e.target) && e.target !== pill) popup.classList.remove('open');
    });
  })();

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

  // Bands toolbar dropdown
  const bandsTbSection = document.getElementById('bands-tb-section');
  const btnBandsCatalog = document.getElementById('btn-bands-catalog');
  if (bandsTbSection && btnBandsCatalog) {
    btnBandsCatalog.addEventListener('click', e => {
      e.stopPropagation();
      const opening = !bandsTbSection.classList.contains('open');
      if (opening) renderBandsTbList();
      bandsTbSection.classList.toggle('open');
    });
    document.addEventListener('click', e => {
      if (!bandsTbSection.contains(e.target)) bandsTbSection.classList.remove('open');
    });
  }

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

  // Auto-load cartography from DB if one exists
  if (window.OPTIQCARTO_HAS_CARTO && window.OPTIQCARTO_DEFAULT_NAME) {
    const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
    fetch(`${apiBase}/api/load/${encodeURIComponent(window.OPTIQCARTO_DEFAULT_NAME)}`)
      .then(r => r.json())
      .then(data => {
        if (data && !data.error) {
          state = data;
          if (typeof resetHighlightExtco === 'function') resetHighlightExtco();
          if (!state.bandWidth) state.bandWidth = 3200;
          if (!state.groups) state.groups = [];
          if (state.connections && state.shapes) {
            const validIds = new Set([
              ...state.shapes.map(s => s.id),
              ...(state.groups || []).map(g => g.id),
            ]);
            state.connections = state.connections.filter(c => validIds.has(c.fromId) && validIds.has(c.toId));
          }
          history = [JSON.stringify(state)]; histIndex = 0;
          render(); updateProps(); fitView();
        }
      })
      .catch(() => {});
  }

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


document.addEventListener('DOMContentLoaded', init);

// Écoute les messages postMessage depuis la page parente (activities_map).
// Permet d'activer le mode "mise en évidence des activités externes" depuis l'extérieur de l'iframe.
window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.type === 'toggle-extco') {
    if (typeof toggleHighlightExtco === 'function') toggleHighlightExtco();
    try { e.source.postMessage({ type: 'extco-state', active: typeof isHighlightExtcoActive === 'function' ? isHighlightExtcoActive() : false }, e.origin || '*'); } catch(_) {}
  }
  if (e.data.type === 'get-extco-state') {
    try { e.source.postMessage({ type: 'extco-state', active: typeof isHighlightExtcoActive === 'function' ? isHighlightExtcoActive() : false }, e.origin || '*'); } catch(_) {}
  }
});
