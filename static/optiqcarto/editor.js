'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — Éditeur SVG
   Dépendances chargées avant ce fichier :
     color-utils.js  — utilitaires couleur purs
     geometry.js     — géométrie & chemins SVG purs
     vsdx_importer.js
   ══════════════════════════════════════════════════ */

// Localisation : lit window.OPTIQ_I18N injecté par Flask, fallback = clé brute
const _L = (key, ...subs) => {
  const s = (window.OPTIQ_I18N && window.OPTIQ_I18N[key]) || key;
  return subs.length ? s.replace(/\{(\d+)\}/g, (_, i) => subs[i] ?? '') : s;
};

function getBandForY(midY) {
  let y = -200;
  for (const band of state.bands) {
    if (band.deleted) continue; // cohérent avec renderBands qui saute aussi les bandes supprimées
    if (midY >= y && midY < y + band.height) return band;
    y += band.height;
  }
  return null;
}

function updateShapeColor(s) {
  if (s.type === 'decision') { s.color = '#9ca3af'; s.textColor = bandTextColor('#9ca3af'); return; }
  if (s.type === 'start-end') return; // Renvoi : couleur gérée par _updateRenvoiColor
  if (s.subtype === 'extco') return; // Activité hachurée : couleur gérée manuellement uniquement
  const band = getBandForY(s.y + s.h / 2);
  if (!band) return;
  s.color = s.colorVariant === 1 ? bandMutedColor(band.color) : band.color;
  s.textColor = bandTextColor(s.color); // blanc ou noir selon luminance du fond
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

  // Idempotency: abort if R2 (label = actB, connected to actA) already exists
  const actBLabel = (actB.label || '').trim().toLowerCase();
  if (state.shapes.some(s =>
      s.type === 'start-end' && s.id !== renvoi.id &&
      (s.label || '').trim().toLowerCase() === actBLabel &&
      state.connections.some(c => c.fromId === s.id && c.toId === actA.id)
  )) return;

  // Connexion originale actB → renvoi (vient d'être créée juste avant l'appel)
  const origConn = state.connections.find(c => c.fromId === fromShapeId && c.toId === toShapeId);

  // Créer R2 à gauche de A — écart calculé pour que le label de connexion soit visible
  const R2W = SHAPE_DEFAULTS['start-end'].w;
  const R2H = SHAPE_DEFAULTS['start-end'].h;
  const _connLabel = origConn ? (origConn.label || '') : '';
  const _labelPx   = Math.max(80, _connLabel.length * 7 + 90); // 7px/char + corners + margin
  const r2x = Math.max(INDEX_W_SVG + 4, Math.round(actA.x - R2W - _labelPx));
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
      routing:  'orthogonal',
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
    { id:  0, label: 'Client',                                                               color: '#FFFFFF', fontSize: 11, height: 100 },
    { id:  1, label: 'Analyse de Marché & Communication',                                    color: '#C00000', fontSize: 11, height: 220, deleted: true },
    { id:  2, label: 'Vente & Suivi commercial',                                             color: '#FF0000', fontSize: 11, height: 220 },
    { id:  3, label: 'Gestion Administrative & Financière',                                  color: '#92D050', fontSize: 11, height: 220 },
    { id:  4, label: 'Négociation & Relations Fournisseurs',                                 color: '#4F6228', fontSize: 11, height: 220, deleted: true },
    { id:  5, label: 'Coordination & Suivi de Projet',                                      color: '#95B3D7', fontSize: 11, height: 220 },
    { id:  6, label: 'Conception Produit & Ingénierie',                                     color: '#548DD4', fontSize: 11, height: 220 },
    { id:  7, label: 'Organisation Industrielle & Méthodes (hors production directe)',       color: '#365F91', fontSize: 11, height: 220, deleted: true },
    { id:  8, label: 'Satisfaction Client & Amélioration Continue',                          color: '#FFFF00', fontSize: 11, height: 220, deleted: true },
    { id:  9, label: 'Contrôle qualité & Mesure (Métrologie)',                              color: '#5F497A', fontSize: 11, height: 220, deleted: true },
    { id: 10, label: 'Fabrication & Réalisation Produit (opérations directes)',              color: '#0070C0', fontSize: 11, height: 220 },
    { id: 11, label: 'Organisation & Planification du Travail',                              color: '#FF9900', fontSize: 11, height: 220 },
    { id: 12, label: 'Analyse Technique & Résolution de Problèmes',                          color: '#984806', fontSize: 11, height: 220 },
    { id: 13, label: 'Logistique & Gestion des Flux Physiques',                              color: '#CC9900', fontSize: 11, height: 220 },
    { id: 14, label: 'Pilotage Stratégique & Opérationnel (macro)',                          color: '#D9D9D9', fontSize: 11, height: 220 },
    { id: 15, label: 'Gestion des Compétences & des Talents',                                color: '#92D050', fontSize: 11, height: 220, deleted: true },
    { id: 16, label: 'Fournisseur',                                                          color: '#FFFFFF', fontSize: 11, height: 100 },
  ];
}

const SHAPE_DEFAULTS = {
  process:   { label: 'Activité',      color: '#22c55e', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 130, h: 90,  fontSize: 18, subtype: 'normal' },
  'start-end': { label: 'Renvoi',      color: '#ffffff', textColor: '#000000', validationBadge: false, validationColor: '#4DB868', w: 90,  h: 90,  fontSize: 13, subtype: 'normal' },
  special:   { label: 'Sous-activité', color: '#f59e0b', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 130, h: 90,  fontSize: 13, subtype: 'normal' },
  decision:  { label: 'Décision',      color: '#9ca3af', textColor: '#ffffff', validationBadge: false, validationColor: '#4DB868', w: 100, h: 100, fontSize: 13, subtype: 'normal', decisionYesDir: null },
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
let lassoMode  = false;
let lassoDrag  = null; // { startSX, startSY, curSX, curSY }
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
let bandResizeShapeStarts = []; // [{shape, startY}] for shapes below the resized band
let bandResizeMinHeight   = 60; // computed from band content at start of resize
let edgeScrollVX = 0, edgeScrollVY = 0;
let edgeScrollRaf = null;
// Délai d'immobilité avant que le défilement par les bords s'active (évite les
// déplacements involontaires en passant la souris vers le menu du haut).
let edgeDwellTimer = null;
let edgePendingVX = 0, edgePendingVY = 0;
let spaceDown = false;
let labelEditing = null;        // { shapeId }
let portDrag = null;            // { fromShapeId, fromPort:{x,y,dir} } — drag depuis un port
let connEndDrag = null;     // { connId, which:'from'|'to', curX, curY, snapShapeId, snapDir }
let bendDrag = null;        // legacy — kept for undo compat
let segDrag  = null;        // legacy — kept for undo compat
let cornerDrag = null;     // { connId, ptIdx, startX, startY, startPts }
let cornerSnapPreview = false; // true quand l'angle du coin draggé ≈ 180° (177–183°)
let addCornerMode = false;
let addCornerConnId = null;
let labelDrag = null;       // { connId, startLx, startLy, startX, startY }
let markerIds = new Map();      // "color-style" → markerId
const hatchIds = new Set();     // pattern IDs déjà créés dans les defs
let leftPanelOpen = false;
let propsOpen = false;
let isDirty = false;
let _autoSaveTimerId = null;
let _autoSaveToastInterval = null;
let activeCalqueId = null;
let _calqueIsNew = false;
let _baseStateForDiff = null;
let _calqueList = [];
let selectedGroup = null;
let groupHighlightId = null;
let expandedGroups = new Set();
let collapsedPiles = new Set(); // IDs of pile groups collapsed on canvas
// extco activity_id → { id, display_label, origin_entity_name }
let _liaisonByActivityId = {};
// ID de la forme à mettre en évidence (zoom-to-activity) — null = aucune
let _haloShapeId = null;

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
const gLasso    = document.getElementById('g-lasso');
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
  if (window.__miniReady) renderMinimap();   // mini-carte (outil) — voir bloc MINIMAP
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
  return tx < fx; // block only when target is strictly left of source
}

// Returns the X coordinate of a specific port on a shape (falls back to center X)
function _portX(shapeId, dir, t) {
  const s = state.shapes.find(s => s.id === shapeId);
  if (!s) return null;
  if (dir) {
    const p = getDetailedPorts(s).find(p => p.dir === dir && (t === undefined || Math.abs(p.t - t) < 0.02));
    if (p) return p.x;
  }
  return s.x + s.w / 2;
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

// Ports de connexion d'un groupe : même ÉCART que ceux d'une activité
// (pas le même nombre). L'espacement suit SHAPE_DEFAULTS.process, la quantité
// est proportionnelle à la taille du groupe. Coordonnées alignées sur spreadPort
// (_halo = 0 pour un groupe), pour que le point dessiné = point d'ancrage réel.
function getGroupDetailedPorts(grpOrBounds) {
  const b = grpOrBounds && grpOrBounds.shapeIds ? getGroupBounds(grpOrBounds) : grpOrBounds;
  if (!b) return [];
  const STEP_X = SHAPE_DEFAULTS.process.w / 6; // écart top/bottom d'une activité (~21.7)
  const STEP_Y = SHAPE_DEFAULTS.process.h / 5; // écart left/right d'une activité (18)
  const nX = Math.max(1, Math.round(b.w / STEP_X));
  const nY = Math.max(1, Math.round(b.h / STEP_Y));
  const ports = [];
  for (let i = 0; i <= nX; i++) {
    const t = i / nX; // coins inclus (comme top/bottom d'une activité)
    ports.push({ x: b.x + b.w * t, y: b.y,        dir: 'top',    t });
    ports.push({ x: b.x + b.w * t, y: b.y + b.h,  dir: 'bottom', t });
  }
  for (let i = 1; i <= nY; i++) {
    const t = (i - 0.5) / nY; // en retrait des coins (comme left/right d'une activité)
    ports.push({ x: b.x,         y: b.y + b.h * t, dir: 'left',  t });
    ports.push({ x: b.x + b.w,   y: b.y + b.h * t, dir: 'right', t });
  }
  return ports;
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

/* ══════════════════════════════════════════════════
   DÉCISION — logique géométrique O/N
   ══════════════════════════════════════════════════ */

// Connections whose computed path passes within the diamond's circumscribed radius.
// Requires renderConnections() to have run first (populates _computedOrthopts).
function _nearbyConnections(diamond) {
  const cx = diamond.x + diamond.w / 2, cy = diamond.y + diamond.h / 2;
  const thresh = Math.hypot(diamond.w / 2, diamond.h / 2) + 8;
  return state.connections.filter(c => {
    const pts = c._computedOrthopts;
    if (!pts || pts.length < 2) return false;
    for (let i = 0; i < pts.length - 1; i++) {
      const ax = pts[i].x, ay = pts[i].y, bx = pts[i+1].x, by = pts[i+1].y;
      const abx = bx - ax, aby = by - ay;
      const len2 = abx*abx + aby*aby;
      if (len2 < 4) continue;
      const t = Math.max(0, Math.min(1, ((cx-ax)*abx + (cy-ay)*aby) / len2));
      if (Math.hypot(cx - (ax+t*abx), cy - (ay+t*aby)) < thresh) return true;
    }
    return false;
  });
}

// After decisionYesDir changes: tag each nearby connection with choiceLabel ('Oui'/'Non')
// so it persists in the saved JSON and syncs to Link.choice_label via _do_sync.
function _syncChoiceLabels(diamond) {
  const nearby = _nearbyConnections(diamond);
  for (const c of nearby) c.choiceLabel = null;
  if (!diamond.decisionYesDir || nearby.length === 0) return;
  if (nearby.length === 1) { nearby[0].choiceLabel = 'Oui'; return; }
  const CW90 = { right: 'down', down: 'left', left: 'up', up: 'right' };
  const noDir = CW90[diamond.decisionYesDir];
  const cx = diamond.x + diamond.w / 2, cy = diamond.y + diamond.h / 2;
  for (const c of nearby) {
    const pts = c._computedOrthopts;
    if (!pts || pts.length < 2) continue;
    let minDist = Infinity, closestIdx = 0;
    for (let i = 0; i < pts.length; i++) {
      const d = Math.hypot(cx - pts[i].x, cy - pts[i].y);
      if (d < minDist) { minDist = d; closestIdx = i; }
    }
    const nextIdx = closestIdx + 1 < pts.length ? closestIdx + 1 : closestIdx - 1;
    if (nextIdx < 0 || nextIdx === closestIdx) continue;
    const dx = pts[nextIdx].x - pts[closestIdx].x, dy = pts[nextIdx].y - pts[closestIdx].y;
    const exitDir = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'down' : 'up');
    if (exitDir === diamond.decisionYesDir) c.choiceLabel = 'Oui';
    else if (exitDir === noDir)             c.choiceLabel = 'Non';
  }
}

// Small O/N badge on each connection line, at the exit point from the nearest diamond.
function _renderChoiceBadgesOnConns() {
  for (const conn of state.connections) {
    if (!conn.choiceLabel) continue;
    const pts = conn._computedOrthopts;
    if (!pts || pts.length < 2) continue;
    let bestDiamond = null, bestDist = Infinity;
    for (const s of state.shapes) {
      if (s.type !== 'decision') continue;
      const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
      for (const p of pts) {
        const d = Math.hypot(cx - p.x, cy - p.y);
        if (d < bestDist) { bestDist = d; bestDiamond = s; }
      }
    }
    if (!bestDiamond || bestDist > Math.hypot(bestDiamond.w/2, bestDiamond.h/2) + 20) continue;
    const dcx = bestDiamond.x + bestDiamond.w / 2, dcy = bestDiamond.y + bestDiamond.h / 2;
    let minDist = Infinity, closestIdx = 0;
    for (let i = 0; i < pts.length; i++) {
      const d = Math.hypot(dcx - pts[i].x, dcy - pts[i].y);
      if (d < minDist) { minDist = d; closestIdx = i; }
    }
    const exitIdx = closestIdx + 1 < pts.length ? closestIdx + 1 : closestIdx > 0 ? closestIdx - 1 : closestIdx;
    const bx = pts[exitIdx].x, by = pts[exitIdx].y;
    const isYes = conn.choiceLabel === 'Oui';
    const bg = isYes ? '#22c55e' : '#f97316', bd = isYes ? '#16a34a' : '#ea580c';
    const badgeG = el('g', { 'pointer-events': 'none' }, gConns);
    el('circle', { cx: bx, cy: by, r: '8', fill: bg, stroke: bd, 'stroke-width': '1.5' }, badgeG);
    el('text', { x: String(bx), y: String(by), 'text-anchor': 'middle', 'dominant-baseline': 'middle', fill: '#ffffff', 'font-size': '8', 'font-family': 'Segoe UI, sans-serif', 'font-weight': '700' }, badgeG).textContent = isYes ? 'O' : 'N';
  }
}

// Garantit que le premier ET le dernier segment sont le long de l'AXE de leur port,
// pour que la tête de flèche pointe pile dans le côté de la forme. Le port est
// recalculé par spreadPort (t dérivé) et ne coïncide pas toujours avec la fin du
// tracé → le dernier segment peut finir PERPENDICULAIRE à l'axe du port (ex. segment
// horizontal dans un port « bottom ») → le marqueur SVG s'oriente le long de ce
// segment → la pointe « pivote » de 90°. On repositionne le dernier coude pour que
// l'approche finale suive l'axe du port (copie : l'état sauvegardé n'est pas touché).
function _alignPortApproach(pts, fdir, tdir) {
  if (!pts || pts.length < 3) return pts;
  const out = pts.map(p => ({ x: p.x, y: p.y }));
  const n = out.length;
  const fix = (portIdx, adjIdx, p2Idx, dir) => {
    const port = out[portIdx], adj = out[adjIdx], p2 = out[p2Idx];
    const vert = (dir === 'top' || dir === 'bottom');
    // segment port→adj déjà le long de l'axe du port ?
    if (vert ? Math.abs(adj.x - port.x) < 1.5 : Math.abs(adj.y - port.y) < 1.5) return;
    // Éviter un dernier segment dégénéré (le coude collerait au port).
    if (vert ? Math.abs(p2.y - port.y) < 4 : Math.abs(p2.x - port.x) < 4) return;
    // Reposer le coude : port→adj le long de l'axe du port, p2→adj perpendiculaire.
    if (vert) { adj.x = port.x; adj.y = p2.y; }
    else      { adj.y = port.y; adj.x = p2.x; }
  };
  fix(n - 1, n - 2, n - 3, tdir);        // pointe (porte le marqueur → priorité)
  if (n >= 4) fix(0, 1, 2, fdir);        // sortie : seulement si son coude est distinct
  return out;                            // de celui de la pointe (sinon ils se battent)
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
    if (s) {
      // Si la forme est dans un groupe fermé (pile), router vers les bords du groupe
      const parentGrp = state.groups && state.groups.find(g => g.isPile && collapsedPiles.has(g.id) && g.shapeIds.includes(s.id));
      if (parentGrp) {
        const b = getGroupBounds(parentGrp);
        if (b) {
          const bw = 140, bh = 72;
          return { id: parentGrp.id,
                   x: (b.x + b.w / 2) - bw / 2, y: (b.y + b.h / 2) - bh / 2,
                   w: bw, h: bh, _halo: 0, _type: 'group' };
        }
      }
      return { id: s.id, x: s.x, y: s.y, w: s.w, h: s.h, _halo: s.type === 'process' ? 7 : 0, _type: s.type };
    }
    const grp = state.groups && state.groups.find(g => g.id === eid);
    if (grp) { const b = getGroupBounds(grp); if (b) return { id: grp.id, x: b.x, y: b.y, w: b.w, h: b.h, _halo: 0, _type: 'group' }; }
    return null;
  }

  for (const c of state.connections) {
    const from = _resolveEp(c.fromId);
    const to   = _resolveEp(c.toId);
    if (!from || !to) continue;
    // Ignorer les connexions internes à une pile fermée
    if (from._type === 'group' && to._type === 'group' && from.id === to.id) continue;
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
    // Auto-spread : répartit sur ce côté TOUTES les connexions qui l'utilisent —
    // entrantes ET sortantes (unifiedUsage) — pour qu'aucune flèche n'atterrisse sur
    // le même point qu'une autre (un point de connexion = un seul branchement). Avant,
    // on ne comptait que les sortantes (fromUsage) → 2 flèches entrantes se posaient
    // toutes deux au centre (t=0.5) et se superposaient.
    const key = `${ep.id}-${dir}`;
    const users = unifiedUsage[key] || [];
    const idx = users.findIndex(u => u.connId === connId && u.end === end);
    const n   = users.length;
    const t   = (idx < 0 || n <= 1) ? 0.5 : (idx + 1) / (n + 1);
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
    // Masquer les connexions internes à un groupe fermé (les deux extrémités dans le même groupe)
    if (from._type === 'group' && to._type === 'group' && from.id === to.id) continue;

    const dx = (to.x + to.w/2) - (from.x + from.w/2);
    const dy = (to.y + to.h/2) - (from.y + from.h/2);
    const fdir = c.fromPortDir || (Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top'));
    const tdir = c.toPortDir || OPP[fdir]; // indépendant si défini explicitement

    const fp = spreadPort(from, fdir, c.id, 'from', c.fromPortT);
    const tp = spreadPort(to,   tdir, c.id, 'to',   c.toPortT);
    const routing = 'orthogonal';

    // Routing orthogonal pur avec évitement des formes (toutes connexions, y compris importées)
    let orthopts, d, _usedFp = fp, _usedTp = tp;
    {
      const fk2 = `${c.fromId}-${fdir}`;
      const fUsers2 = fromUsage[fk2] || [];
      const fIdx2 = fUsers2.indexOf(c.id);
      const fN2 = fUsers2.length;
      const bundleOffset = fN2 > 1 ? (fIdx2 - (fN2 - 1) / 2) * 14 : 0;
      if (c.userPts && c.userPts.length >= 1) {
        orthopts = [fp, ...c.userPts, tp];
      } else {
        const userOffset = c.bendOffset || { dx: 0, dy: 0 };
        orthopts = orthogonalPts(fp, tp, bundleOffset, userOffset);
        // Skip obstacle avoidance while dragging a corner (expensive + causes jitter)
        if (!cornerDrag || cornerDrag.connId !== c.id) {
          orthopts = avoidShapes(orthopts, state.shapes, c.fromId, c.toId);
          orthopts = simplifyPath(orthopts);
        }
      }
      c._computedOrthopts = orthopts;
      // Enregistrer les segments pour pénaliser les labels des connexions suivantes
      for (let _pi = 0; _pi < orthopts.length - 1; _pi++)
        placedPaths.push({ ax: orthopts[_pi].x, ay: orthopts[_pi].y, bx: orthopts[_pi+1].x, by: orthopts[_pi+1].y, connId: c.id });
      // Snap-to-straight preview : dessiner le tracé SANS le coin en cours de suppression
      let displayOrthopts = orthopts;
      if (cornerSnapPreview && cornerDrag && cornerDrag.connId === c.id) {
        const si = cornerDrag.ptIdx;
        displayOrthopts = orthopts.filter((_, idx) => idx !== si);
        if (displayOrthopts.length < 2) displayOrthopts = orthopts;
      }
      // Aligne les segments d'extrémité sur l'axe des ports → la tête pointe droit
      // dans la forme (fini les pointes qui pivotent sur un micro-jog terminal).
      displayOrthopts = _alignPortApproach(displayOrthopts, fp.dir, tp.dir);
      // tipPad = 18 : approche droite garantie avant la tête (~16 px) → la pointe
      // ne se pose jamais sur un virage (« padding » demandé pour les pointes).
      d = polylineToPath(displayOrthopts, 12, 18);
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
      'stroke-width': isSel ? '4.5' : '3',
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
        // Orientation figée par l'agencement auto (parallèle au segment) si dispo,
        // sinon direction dominante de la flèche.
        angle = (c.labelOffset.a !== undefined) ? c.labelOffset.a : (arrowMajorH ? 0 : -90);
      } else {
        // Segment préféré : dans la direction dominante, on privilégie le segment
        // le plus PROCHE DE LA POINTE (fin de flèche) suffisamment long, pour que le
        // label se pose près du bout ; à défaut le plus long dominant, puis le plus long.
        let longestSeg = 0, longestLen = 0, longestForcedSeg = -1, longestForcedLen = 0, lastForcedSeg = -1;
        for (let i = 0; i < orthopts.length - 1; i++) {
          const pa = orthopts[i], pb = orthopts[i + 1];
          const l = Math.hypot(pb.x - pa.x, pb.y - pa.y);
          const segH = Math.abs(pb.y - pa.y) < 2;
          if (l > longestLen) { longestLen = l; longestSeg = i; }
          if (segH === arrowMajorH && l > longestForcedLen) { longestForcedLen = l; longestForcedSeg = i; }
          if (segH === arrowMajorH && l >= 55) lastForcedSeg = i;
        }
        const preferSeg = lastForcedSeg >= 0 ? lastForcedSeg
                        : (longestForcedSeg >= 0 ? longestForcedSeg : longestSeg);

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
      // Poignées de coin — une par vertex intermédiaire, déplaçable librement en X et Y
      if (routing === 'orthogonal' && orthopts.length >= 3) {
        for (let ci = 1; ci <= orthopts.length - 2; ci++) {
          const pt = orthopts[ci];
          const hs = 6; // demi-taille du losange
          const isSnapping = cornerSnapPreview && cornerDrag &&
                             cornerDrag.connId === c.id && cornerDrag.ptIdx === ci;
          el('rect', {
            x: String(pt.x - hs), y: String(pt.y - hs),
            width: String(hs * 2), height: String(hs * 2),
            rx: '2',
            fill: isSnapping ? 'rgba(239,68,68,0.12)' : '#ffffff',
            stroke: isSnapping ? '#ef4444' : '#1f7a54',
            'stroke-width': '2.5',
            'stroke-dasharray': isSnapping ? '3,2' : 'none',
            transform: `rotate(45,${pt.x},${pt.y})`,
            cursor: 'move',
            'data-conn-corner': String(c.id), 'data-pt-idx': String(ci),
            style: 'pointer-events:all',
          }, gConns);
          // Delete button — small × circle at top-right of diamond
          const dr = Math.max(5, 5 / vpScale);
          const dcx = pt.x + hs + dr * 0.8;
          const dcy = pt.y - hs - dr * 0.8;
          el('circle', {
            cx: String(dcx), cy: String(dcy), r: String(dr),
            fill: '#ef4444', stroke: '#fff', 'stroke-width': '1.5',
            cursor: 'pointer',
            'data-conn-del-corner': String(c.id), 'data-del-pt-idx': String(ci),
            style: 'pointer-events:all',
          }, gConns);
          txt('×', {
            x: String(dcx), y: String(dcy),
            'text-anchor': 'middle', 'dominant-baseline': 'middle',
            fill: '#fff', 'font-size': String(Math.max(8, 8 / vpScale)),
            'font-weight': '700', 'pointer-events': 'none',
          }, gConns);
        }
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
  _renderChoiceBadgesOnConns();
}

/* ══════════════════════════════════════════════════
   RENDER — SHAPES
   ══════════════════════════════════════════════════ */

function _drawHaloForShape(shape, parent) {
  const pad = 18;
  const cx = shape.x + shape.w / 2;
  const cy = shape.y + shape.h / 2;
  const rx0 = shape.w / 2 + pad;
  const ry0 = shape.h / 2 + pad;
  // Ensure blur filter exists in defs
  const defs = canvas.querySelector('defs');
  if (defs && !document.getElementById('_halo-glow-filter')) {
    const flt = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
    flt.setAttribute('id', '_halo-glow-filter');
    flt.setAttribute('x', '-60%'); flt.setAttribute('y', '-60%');
    flt.setAttribute('width', '220%'); flt.setAttribute('height', '220%');
    const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
    blur.setAttribute('stdDeviation', '6'); blur.setAttribute('result', 'blur');
    const merge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
    const n1 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
    n1.setAttribute('in', 'blur');
    const n2 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
    n2.setAttribute('in', 'SourceGraphic');
    merge.appendChild(n1); merge.appendChild(n2);
    flt.appendChild(blur); flt.appendChild(merge);
    defs.appendChild(flt);
  }
  function mkAnim(attr, vals, dur) {
    const a = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
    a.setAttribute('attributeName', attr);
    a.setAttribute('values', vals);
    a.setAttribute('dur', dur + 's');
    a.setAttribute('repeatCount', 'indefinite');
    return a;
  }
  // Outer glow ring
  const outer = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
  outer.setAttribute('cx', cx); outer.setAttribute('cy', cy);
  outer.setAttribute('rx', rx0 + 5); outer.setAttribute('ry', ry0 + 5);
  outer.setAttribute('fill', 'none');
  outer.setAttribute('stroke', '#ec4899');
  outer.setAttribute('stroke-width', '10');
  outer.setAttribute('pointer-events', 'none');
  outer.setAttribute('filter', 'url(#_halo-glow-filter)');
  outer.appendChild(mkAnim('stroke-opacity', '0.7;0.1;0.7', 1.6));
  outer.appendChild(mkAnim('rx', `${rx0+5};${rx0+13};${rx0+5}`, 1.6));
  outer.appendChild(mkAnim('ry', `${ry0+5};${ry0+13};${ry0+5}`, 1.6));
  parent.appendChild(outer);
  // Sharp inner ring
  const inner = document.createElementNS('http://www.w3.org/2000/svg', 'ellipse');
  inner.setAttribute('cx', cx); inner.setAttribute('cy', cy);
  inner.setAttribute('rx', rx0); inner.setAttribute('ry', ry0);
  inner.setAttribute('fill', 'none');
  inner.setAttribute('stroke', '#ec4899');
  inner.setAttribute('stroke-width', '3');
  inner.setAttribute('pointer-events', 'none');
  inner.appendChild(mkAnim('stroke-opacity', '1;0.4;1', 1.6));
  inner.appendChild(mkAnim('rx', `${rx0};${rx0+8};${rx0}`, 1.6));
  inner.appendChild(mkAnim('ry', `${ry0};${ry0+8};${ry0}`, 1.6));
  parent.appendChild(inner);
}

function renderShapes() {
  gShapes.innerHTML = '';

  // Build set of shapes hidden by a collapsed pile
  const hiddenByPile = new Set();
  for (const grp of (state.groups || [])) {
    if (grp.isPile && collapsedPiles.has(grp.id)) {
      grp.shapeIds.forEach(id => hiddenByPile.add(id));
    }
  }

  // Halo de mise en évidence (zoom-to-activity depuis le parent)
  if (_haloShapeId !== null) {
    const hs = state.shapes.find(s => s.id === _haloShapeId);
    if (hs) _drawHaloForShape(hs, gShapes);
  }

  for (const s of state.shapes) {
    if (hiddenByPile.has(s.id)) continue; // hidden inside collapsed pile
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

      // Directional O/N badges — anchored to the 4 tips of the diamond
      const TIP = {
        right: { x: s.x + s.w + 16, y: s.y + s.h / 2 },
        down:  { x: s.x + s.w / 2,  y: s.y + s.h + 16 },
        left:  { x: s.x - 16,        y: s.y + s.h / 2 },
        up:    { x: s.x + s.w / 2,   y: s.y - 16 },
      };
      const CW90 = { right: 'down', down: 'left', left: 'up', up: 'right' };
      if (s.decisionYesDir) {
        const noDir = CW90[s.decisionYesDir];
        const nearbyCount = _nearbyConnections(s).length;
        const yp = TIP[s.decisionYesDir];
        const yg = el('g', { 'data-type': 'decision-dir-badge', 'data-shape-id': String(s.id), cursor: 'pointer' }, g);
        el('circle', { cx: yp.x, cy: yp.y, r: '10', fill: '#22c55e', stroke: '#16a34a', 'stroke-width': '1.5' }, yg);
        el('text', { x: String(yp.x), y: String(yp.y), 'text-anchor': 'middle', 'dominant-baseline': 'middle', fill: '#ffffff', 'font-size': '9', 'font-family': 'Segoe UI, sans-serif', 'font-weight': '700', 'pointer-events': 'none' }, yg).textContent = 'O';
        if (nearbyCount !== 1) {
          const np = TIP[noDir];
          const ng = el('g', { 'data-type': 'decision-dir-badge', 'data-shape-id': String(s.id), cursor: 'pointer' }, g);
          el('circle', { cx: np.x, cy: np.y, r: '10', fill: '#f97316', stroke: '#ea580c', 'stroke-width': '1.5' }, ng);
          el('text', { x: String(np.x), y: String(np.y), 'text-anchor': 'middle', 'dominant-baseline': 'middle', fill: '#ffffff', 'font-size': '9', 'font-family': 'Segoe UI, sans-serif', 'font-weight': '700', 'pointer-events': 'none' }, ng).textContent = 'N';
        }
      } else {
        const hx = s.x + s.w + 10, hy = s.y - 10;
        const hg = el('g', { 'data-type': 'decision-dir-badge', 'data-shape-id': String(s.id), 'data-export-hidden': '1', cursor: 'pointer' }, g);
        el('circle', { cx: hx, cy: hy, r: '9', fill: '#ffffff', stroke: '#d1d5db', 'stroke-width': '1.5' }, hg);
        el('text', { x: String(hx), y: String(hy), 'text-anchor': 'middle', 'dominant-baseline': 'middle', fill: '#9ca3af', 'font-size': '9', 'font-family': 'Segoe UI, sans-serif', 'font-weight': '700', 'pointer-events': 'none' }, hg).textContent = '?';
      }
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

    // ── Liaison sub-label (below extco shapes) — badge fond blanc + contour couleur ──
    if (s.subtype === 'extco') {
      const liaison = _liaisonByActivityId[String(s.id)];
      const subLabelText = liaison
        ? (liaison.display_label || liaison.origin_entity_name || '')
        : (s.crossCartoSource || '');
      if (subLabelText) {
        const fz    = Math.max(9, Math.min(12, (s.fontSize || 18) * 0.65));
        const padX  = 7, padY = 3;
        const approxW = subLabelText.length * fz * 0.60;
        const bw    = Math.max(approxW + padX * 2, 40);
        const bh    = fz + padY * 2;
        const bx    = s.x + s.w / 2 - bw / 2;
        const by    = s.y + s.h + 5;   // 5px gap → la flèche s'arrête avant le contour
        const bc    = s.color || '#94a3b8';
        // Rectangle fond blanc + contour couleur activité
        el('rect', {
          x: String(bx), y: String(by),
          width: String(bw), height: String(bh),
          rx: '3',
          fill: '#ffffff',
          stroke: bc,
          'stroke-width': '1.5',
          'pointer-events': 'none',
        }, g);
        txt(subLabelText, {
          x: String(s.x + s.w / 2),
          y: String(by + bh / 2),
          'text-anchor': 'middle',
          'dominant-baseline': 'middle',
          fill: bc,
          'font-size': String(fz),
          'font-family': 'Segoe UI, system-ui, sans-serif',
          'font-weight': '600',
          'pointer-events': 'none',
        }, g);
      }
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
    if (isHover && !portDrag && !window.OPTIQCARTO_READONLY && selectedConn === null) {
      // Taille fixe en pixels écran : 10px quelle que soit le zoom
      const ps = 10 / vpScale;
      const sw = 1.5 / vpScale;
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

function cornerAngleDeg(prev, corner, next) {
  const ax = prev.x - corner.x, ay = prev.y - corner.y;
  const bx = next.x - corner.x, by = next.y - corner.y;
  const la = Math.hypot(ax, ay), lb = Math.hypot(bx, by);
  if (la < 0.001 || lb < 0.001) return 0;
  const dot = Math.max(-1, Math.min(1, (ax * bx + ay * by) / (la * lb)));
  return Math.acos(dot) * 180 / Math.PI;
}

function closestPointOnSegment(a, b, p) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  if (len2 < 0.001) return { x: a.x, y: a.y };
  const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2));
  return { x: a.x + t * dx, y: a.y + t * dy };
}

function insertCornerOnConn(conn, cx, cy) {
  const pts = conn._computedOrthopts || [];
  if (pts.length < 2) return;
  let bestSeg = -1, bestDist = Infinity, bestPt = null;
  for (let i = 0; i < pts.length - 1; i++) {
    const cp = closestPointOnSegment(pts[i], pts[i + 1], { x: cx, y: cy });
    const d = Math.hypot(cp.x - cx, cp.y - cy);
    if (d < bestDist) { bestDist = d; bestSeg = i; bestPt = cp; }
  }
  if (bestSeg < 0) return;
  if (!conn.userPts) conn.userPts = pts.slice(1, -1).map(p => ({ x: p.x, y: p.y }));
  conn.userPts.splice(bestSeg, 0, { x: bestPt.x, y: bestPt.y });
}

function mergeOverlappingCorners(conn) {
  if (!conn.userPts || conn.userPts.length < 2) return;
  const THRESH = 14;
  let changed = true;
  while (changed) {
    changed = false;
    for (let i = 0; i < conn.userPts.length - 1; i++) {
      const a = conn.userPts[i], b = conn.userPts[i + 1];
      if (Math.hypot(a.x - b.x, a.y - b.y) < THRESH) {
        conn.userPts.splice(i, 2, { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
        changed = true; break;
      }
    }
  }
  if (conn.userPts.length === 0) conn.userPts = null;
}

// Ensure all segments in conn.userPts are either purely horizontal or purely vertical.
// Inserts an intermediate corner whenever an oblique segment is detected.
function _orthogonalizeUserPts(conn) {
  if (!conn.userPts || conn.userPts.length === 0) return;
  const pts = conn.userPts;
  let changed = true;
  const MAX_PASS = 20;
  let pass = 0;
  while (changed && pass++ < MAX_PASS) {
    changed = false;
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1];
      if (Math.abs(a.x - b.x) > 1 && Math.abs(a.y - b.y) > 1) {
        // Oblique segment: insert a corner to break it into H + V
        pts.splice(i + 1, 0, { x: b.x, y: a.y });
        changed = true;
        break;
      }
    }
  }
}

// Grow the majority band so the given shape is fully contained, shifting lower content.
function _fitShapeIntoBand(s) {
  const majorBand = getBandForY(s.y + s.h / 2);
  if (!majorBand) return;

  // Compute the top Y of majorBand in SVG coordinates
  let bandTopY = -200;
  for (const b of state.bands) {
    if (b.deleted) continue;
    if (b.id === majorBand.id) break;
    bandTopY += b.height;
  }
  const bandBottomY = bandTopY + majorBand.height;
  const shapeBottom = s.y + s.h;

  if (shapeBottom <= bandBottomY) return; // Already contained, nothing to do

  const delta = Math.ceil(shapeBottom - bandBottomY) + 10; // 10px padding
  majorBand.height += delta;

  // Shift all shapes whose center was below the old band bottom
  for (const other of state.shapes) {
    if (other.id === s.id) continue;
    if ((other.y + other.h / 2) > bandBottomY) other.y += delta;
  }

  // Shift conn.userPts below the old band bottom
  for (const conn of state.connections) {
    if (!conn.userPts) continue;
    for (const pt of conn.userPts) {
      if (pt.y > bandBottomY) pt.y += delta;
    }
  }
}

function renderHandles() {
  gHandles.innerHTML = '';

  for (const id of selectedShapes) {
    const s = state.shapes.find(x => x.id === id);
    if (!s) continue;
    // Outer glow ring
    el('rect', {
      x: s.x - 9, y: s.y - 9,
      width: s.w + 18, height: s.h + 18,
      rx: '17', ry: '17',
      fill: 'none',
      stroke: 'rgba(59,130,246,0.28)',
      'stroke-width': '7',
      'pointer-events': 'none',
    }, gHandles);
    // Inner selection rect
    el('rect', {
      x: s.x - 5, y: s.y - 5,
      width: s.w + 10, height: s.h + 10,
      rx: '14', ry: '14',
      fill: 'rgba(59,130,246,0.06)',
      stroke: '#3b82f6',
      'stroke-width': '2.5',
      'stroke-dasharray': '7,3',
      'pointer-events': 'none',
    }, gHandles);
  }

  // Indicateurs de port (snap halo) lors du drag depuis un port bleu OU drag d'extrémité de connexion
  const snapDrag = portDrag || connEndDrag;
  if (snapDrag) {
    const curX  = portDrag ? portDrag.curX  : connEndDrag.curX;
    const curY  = portDrag ? portDrag.curY  : connEndDrag.curY;
    const snapId = portDrag ? portDrag.snapShapeId : connEndDrag.snapShapeId;
    const snapDir = portDrag ? portDrag.snapDir    : connEndDrag.snapDir;
    const snapT   = portDrag ? portDrag.snapT      : connEndDrag.snapT;
    const skipId  = portDrag ? portDrag.fromShapeId : null;

    const SHOW_R = 120;
    for (const s of state.shapes) {
      if (skipId !== null && s.id === skipId) continue;
      const distToShape = Math.hypot(curX - (s.x + s.w/2), curY - (s.y + s.h/2));
      if (distToShape > SHOW_R + Math.max(s.w, s.h)) continue;
      const dPorts = getDetailedPorts(s);
      for (const pt of dPorts) {
        const isSnap = s.id === snapId &&
                       pt.dir === snapDir &&
                       Math.abs(pt.t - snapT) < 0.01;
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
    // Ports des groupes (mêmes points de branchement que les activités)
    for (const grp of (state.groups || [])) {
      if (skipId !== null && grp.id === skipId) continue;
      const b = getGroupBounds(grp);
      if (!b) continue;
      const gcx = b.x + b.w / 2, gcy = b.y + b.h / 2;
      if (Math.hypot(curX - gcx, curY - gcy) > SHOW_R + Math.max(b.w, b.h)) continue;
      for (const pt of getGroupDetailedPorts(b)) {
        const isSnap = grp.id === snapId &&
                       pt.dir === snapDir &&
                       Math.abs(pt.t - snapT) < 0.01;
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

    const isCollapsedPile = grp.isPile && collapsedPiles.has(grp.id);

    const grpG = el('g', {
      class: 'group-container',
      'data-group-id': String(grp.id),
    }, gGroups);
    grpG.style.cursor = isCollapsedPile ? 'move' : 'pointer';

    if (grp.isPile) {
      const isCollapsed = collapsedPiles.has(grp.id);

      // When collapsed: compact card stack; when expanded: full bounding box
      let bx = gx, by = gy, bw = gw, bh = gh;
      if (isCollapsed) {
        bw = 140; bh = 72;
        bx = (gx + gw / 2) - bw / 2;
        by = (gy + gh / 2) - bh / 2;
      }

      // Stacked card effect for piles
      for (const [dx, dy] of [[8, 8], [4, 4]]) {
        el('rect', {
          x: bx + dx, y: by + dy, width: bw, height: bh, rx: 14, ry: 14,
          fill: 'rgba(124,58,237,0.04)',
          stroke: 'rgba(124,58,237,0.3)',
          'stroke-width': '1',
          'pointer-events': 'none',
        }, grpG);
      }
      el('rect', {
        x: bx, y: by, width: bw, height: bh, rx: 14, ry: 14,
        fill: isSel ? 'rgba(124,58,237,0.1)' : (isHL ? 'rgba(124,58,237,0.08)' : 'rgba(124,58,237,0.05)'),
        stroke: isSel || isHL ? '#9f7aea' : color,
        'stroke-width': isSel || isHL ? '2' : '1.5',
        'stroke-dasharray': '8,5',
      }, grpG);

      // Pile label badge — toggles collapse on click
      const chevron = isCollapsed ? '▸' : '▾';
      const pileLabel = (grp.label || 'Pile') + '  ' + chevron + '  ' + shapes.length;
      const lblW = Math.min(160, pileLabel.length * 7.5 + 16);
      const badgeX = bx + 10;
      const badgeY = by - 18;

      const badgeG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      badgeG.style.cursor = 'pointer';
      el('rect', { x: badgeX, y: badgeY, width: lblW, height: 18, rx: 6, fill: '#7c3aed', opacity: '0.92' }, badgeG);
      const bt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      bt.setAttribute('x', String(badgeX + lblW / 2));
      bt.setAttribute('y', String(badgeY + 12));
      bt.setAttribute('text-anchor', 'middle');
      bt.setAttribute('fill', '#ffffff');
      bt.setAttribute('font-size', '10');
      bt.setAttribute('font-weight', '700');
      bt.setAttribute('font-family', 'Segoe UI, sans-serif');
      bt.setAttribute('pointer-events', 'none');
      bt.textContent = pileLabel;
      badgeG.appendChild(bt);
      grpG.appendChild(badgeG);

      badgeG.addEventListener('click', e => {
        e.stopPropagation();
        if (collapsedPiles.has(grp.id)) collapsedPiles.delete(grp.id);
        else collapsedPiles.add(grp.id);
        render();
      });
    } else {
      el('rect', {
        x: gx, y: gy, width: gw, height: gh, rx: 18, ry: 18,
        fill: isHL ? 'rgba(252,205,255,0.06)' : (isSel ? 'rgba(179,160,255,0.07)' : 'rgba(179,160,255,0.03)'),
        stroke: isHL ? '#fccdff' : color,
        'stroke-width': isSel || isHL ? '2' : '1.5',
        'stroke-dasharray': '8,5',
      }, grpG);

      // Badge label for regular groups
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
    }

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

function updateMultiselectBadge() {
  const badge = document.getElementById('multiselect-badge');
  const countEl = document.getElementById('multiselect-count');
  if (!badge) return;
  if (selectedShapes.size > 1) {
    if (countEl) countEl.textContent = String(selectedShapes.size);
    badge.style.display = 'flex';
  } else {
    badge.style.display = 'none';
  }
}

function render() {
  renderBands();
  renderLegend();
  renderGroups();
  renderConnections();
  renderShapes();
  renderHandles();
  renderCanvasMap();
  applyGroupHighlight();
  updateMultiselectBadge();
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

  // Formes (exclude shapes that belong to pile groups — they appear under Groupes)
  const pileShapeIds = new Set(
    (state.groups || []).filter(g => g.isPile).flatMap(g => g.shapeIds)
  );
  const nonPileShapes = state.shapes.filter(s => !pileShapeIds.has(s.id));
  if (nonPileShapes.length > 0) {
    const sl = document.createElement('div');
    sl.className = 'left-section-label';
    sl.innerHTML = '<i class="fa-solid fa-shapes"></i> Formes';
    list.appendChild(sl);

    const sorted = [...nonPileShapes].sort((a, b) =>
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
  state.collapsedPileIds = [...collapsedPiles]; // persistance de l'état ouvert/fermé
  history = history.slice(0, histIndex + 1);
  history.push(JSON.stringify(state));
  histIndex = history.length - 1;
  if (!isDirty) {
    isDirty = true;
    _scheduleAutoSave();
  }
}

function _restoreCollapsedPiles() {
  if (state.collapsedPileIds) {
    collapsedPiles = new Set(state.collapsedPileIds.map(Number));
  } else {
    // Aucune donnée sauvegardée : toutes les piles sont fermées par défaut
    collapsedPiles = new Set((state.groups || []).filter(g => g.isPile).map(g => g.id));
  }
}

function undo() {
  if (histIndex <= 0) return;
  histIndex--;
  state = JSON.parse(history[histIndex]);
  _restoreCollapsedPiles();
  clearSelection();
  render();
  updateProps();
  showToast(_L('editor.toast.undo'));
}

function redo() {
  if (histIndex >= history.length - 1) return;
  histIndex++;
  state = JSON.parse(history[histIndex]);
  _restoreCollapsedPiles();
  clearSelection();
  render();
  updateProps();
  showToast(_L('editor.toast.redo'));
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
   LASSO (BOX SELECT)
   ══════════════════════════════════════════════════ */

function setLassoMode(active) {
  lassoMode = active;
  const btn = document.getElementById('btn-lasso-select');
  if (btn) btn.classList.toggle('active', active);
  if (!active && lassoDrag) _cancelLasso();
}

function _cancelLasso() {
  lassoDrag = null;
  if (gLasso) gLasso.innerHTML = '';
}

function _updateLassoRect() {
  if (!lassoDrag || !gLasso) return;
  const r  = canvas.getBoundingClientRect();
  const lx = Math.min(lassoDrag.startSX, lassoDrag.curSX) - r.left;
  const ly = Math.min(lassoDrag.startSY, lassoDrag.curSY) - r.top;
  const lw = Math.abs(lassoDrag.curSX - lassoDrag.startSX);
  const lh = Math.abs(lassoDrag.curSY - lassoDrag.startSY);
  gLasso.innerHTML = '';
  if (lw < 3 && lh < 3) return;
  el('rect', {
    x: lx, y: ly, width: lw, height: lh,
    fill: 'rgba(59,130,246,0.07)',
    stroke: '#3b82f6',
    'stroke-width': '1.5',
    'stroke-dasharray': '5,4',
    rx: '3', ry: '3',
    'pointer-events': 'none',
  }, gLasso);
}

function _finalizeLasso() {
  if (!lassoDrag) return;
  const { x: wx1, y: wy1 } = screenToSVG(
    Math.min(lassoDrag.startSX, lassoDrag.curSX),
    Math.min(lassoDrag.startSY, lassoDrag.curSY)
  );
  const { x: wx2, y: wy2 } = screenToSVG(
    Math.max(lassoDrag.startSX, lassoDrag.curSX),
    Math.max(lassoDrag.startSY, lassoDrag.curSY)
  );
  for (const s of state.shapes) {
    if (s.x >= wx1 && s.y >= wy1 && (s.x + s.w) <= wx2 && (s.y + s.h) <= wy2) {
      selectedShapes.add(s.id);
    }
  }
  _cancelLasso();
  setLassoMode(false);
  if (selectedShapes.size > 0 && !propsOpen) setPropsOpen(true);
  render();
  updateProps();
}

/* ══════════════════════════════════════════════════
   PILES
   ══════════════════════════════════════════════════ */

function createPile() {
  if (selectedShapes.size < 2) {
    showToast('Select at least 2 shapes to create a pile.');
    return;
  }
  const selIds = [...selectedShapes];

  // Collect connections from selected shapes to shapes OUTSIDE the selection
  const connsToTarget = {};   // targetId → [{ fromId, label }]
  for (const fromId of selIds) {
    for (const conn of state.connections) {
      if (conn.fromId === fromId && !selIds.includes(conn.toId) && conn.toId != null) {
        if (!connsToTarget[conn.toId]) connsToTarget[conn.toId] = [];
        connsToTarget[conn.toId].push({ fromId, label: conn.label || '' });
      }
    }
  }

  const targetIds = Object.keys(connsToTarget);

  if (targetIds.length === 0) {
    showToast('Pile prerequisite not met: selected shapes must all connect to a common target.');
    return;
  }
  if (targetIds.length > 1) {
    showToast(`Pile prerequisite not met: shapes connect to ${targetIds.length} different targets — they must all connect to the same shape.`);
    return;
  }

  const targetId = parseInt(targetIds[0]);
  const entries  = connsToTarget[targetIds[0]];

  // Check every selected shape has a connection to target
  const connectedFromIds = new Set(entries.map(e => e.fromId));
  for (const id of selIds) {
    if (!connectedFromIds.has(id)) {
      showToast('Pile prerequisite not met: not all selected shapes have a connection to the common target.');
      return;
    }
  }

  // Check all connections share the same label
  const uniqueLabels = [...new Set(entries.map(e => e.label))];
  if (uniqueLabels.length > 1) {
    showToast(`Pile prerequisite not met: connections to the target must all carry the same label (found: ${uniqueLabels.map(l => '"' + (l || '(empty)') + '"').join(', ')}).`);
    return;
  }

  if (!state.groups) state.groups = [];
  const id = state.nextId++;
  collapsedPiles.add(id); // fermée par défaut
  state.groups.push({
    id,
    label: uniqueLabels[0] || 'Pile',
    shapeIds: selIds,
    color: '#7c3aed',
    isPile: true,
    pileTargetId: targetId,
  });
  clearSelection();
  selectedGroup = id;
  snapshot();
  render();
  showToast('Pile created.');
}

/* ══════════════════════════════════════════════════
   EDGE AUTO-SCROLL
   ══════════════════════════════════════════════════ */

const EDGE_SCROLL_ZONE  = 40;   // px from canvas edge
const EDGE_SCROLL_SPEED =  6;   // max px/frame at the very edge
const EDGE_DWELL_MS     = 1000; // la souris doit rester immobile ~1s avant activation

function _clearEdgeDwell() {
  if (edgeDwellTimer) { clearTimeout(edgeDwellTimer); edgeDwellTimer = null; }
}

function _edgeScrollStep() {
  if (edgeScrollVX === 0 && edgeScrollVY === 0) { edgeScrollRaf = null; return; }
  vpX += edgeScrollVX;
  vpY += edgeScrollVY;
  applyViewport();
  edgeScrollRaf = requestAnimationFrame(_edgeScrollStep);
}

function _updateEdgeScroll(clientX, clientY) {
  // Auto-scroll au bord réservé à l'OUTIL (éditeur). En lecture seule (viewer),
  // approcher la souris d'un bord ne doit PAS déplacer la carto.
  if (window.OPTIQCARTO_READONLY || isPanning) {
    edgeScrollVX = 0; edgeScrollVY = 0; _clearEdgeDwell(); return;
  }
  const r = canvas.getBoundingClientRect();
  const dL = clientX - r.left, dR = r.right  - clientX;
  const dT = clientY - r.top,  dB = r.bottom - clientY;
  const Z  = EDGE_SCROLL_ZONE, S = EDGE_SCROLL_SPEED;
  const vx = dL < Z ? +Math.round((Z - dL) / Z * S)
           : dR < Z ? -Math.round((Z - dR) / Z * S) : 0;
  const vy = dT < Z ? +Math.round((Z - dT) / Z * S)
           : dB < Z ? -Math.round((Z - dB) / Z * S) : 0;

  // Hors zone → on coupe tout.
  if (vx === 0 && vy === 0) {
    edgeScrollVX = 0; edgeScrollVY = 0; _clearEdgeDwell(); return;
  }

  // Dans la zone, mais la souris vient de bouger → on (ré)arme le délai
  // d'immobilité. Le défilement ne démarre qu'après EDGE_DWELL_MS sans mouvement.
  edgeScrollVX = 0; edgeScrollVY = 0;        // pause tant que ça bouge
  edgePendingVX = vx; edgePendingVY = vy;
  _clearEdgeDwell();
  edgeDwellTimer = setTimeout(() => {
    edgeDwellTimer = null;
    edgeScrollVX = edgePendingVX; edgeScrollVY = edgePendingVY;
    if ((edgeScrollVX !== 0 || edgeScrollVY !== 0) && !edgeScrollRaf)
      edgeScrollRaf = requestAnimationFrame(_edgeScrollStep);
  }, EDGE_DWELL_MS);
}

canvas.addEventListener('mouseleave', () => { edgeScrollVX = 0; edgeScrollVY = 0; _clearEdgeDwell(); });

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
      if (s) {
        // En mode connexion, les formes bleues (extco liées) envoient connexion-shape-click
        const origLabel = (s._cxOrig && s.label) || s.label;
        if (_cxActive && _cxMatchedIds.has(String(s.id))) {
          try { window.parent.postMessage({ type: 'connexion-shape-click', activityName: origLabel }, '*'); } catch(_) {}
        } else {
          try { window.parent.postMessage({ t: 'shape-click', label: origLabel, shapeId: s.id, shapeType: s.type, subtype: s.subtype || 'normal' }, '*'); } catch(_) {}
        }
      }
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
      portDrag = { fromShapeId, fromPort: getPorts(shape)[portName], curX: 0, curY: 0, snapShapeId: null, snapDir: null, snapT: 0.5 };
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
    // Compute bottom Y of the resized band at start time
    const bandIdx = state.bands.findIndex(bi => bi.id === bandHeightResizingId);
    let bandBottomY = -200;
    for (let j = 0; j <= bandIdx; j++) {
      if (!state.bands[j].deleted) bandBottomY += state.bands[j].height;
    }
    // Store start Y of all shapes below this band so we can shift them
    bandResizeShapeStarts = state.shapes
      .filter(s => !s.deleted && (s.y + s.h / 2) > bandBottomY)
      .map(s => ({ shape: s, startY: s.y }));
    // Compute minimum height: must contain all shapes whose midpoint is inside this band
    const bandTopY = bandBottomY - bandHeightStartValue;
    let minH = 60;
    for (const s of state.shapes) {
      if (s.deleted) continue;
      const midY = s.y + s.h / 2;
      if (midY > bandTopY && midY <= bandBottomY)
        minH = Math.max(minH, (s.y + s.h) - bandTopY + 24);
    }
    bandResizeMinHeight = minH;
    canvas.style.cursor = 'ns-resize';
    return;
  }
  /* ── Select tool ── */
  if (tool === 'select') {
    // ── Lasso (box select) mode ──
    if (lassoMode) {
      const shapeEl = e.target.closest('[data-type="shape"]');
      if (shapeEl) {
        // Shift-click or plain click on shape while lasso is on → add to selection
        selectShape(parseInt(shapeEl.getAttribute('data-id')), true, false);
        render(); updateProps();
      } else {
        lassoDrag = { startSX: e.clientX, startSY: e.clientY, curSX: e.clientX, curSY: e.clientY };
      }
      return;
    }

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

    // Mode ajout d'angle — clic sur la flèche pour insérer un corner
    if (addCornerMode) {
      addCornerMode = false;
      canvas.style.cursor = '';
      document.getElementById('btn-add-corner')?.classList.remove('active');
      const connHit = e.target.closest('[data-type="conn"]');
      if (connHit) {
        const cid = parseInt(connHit.getAttribute('data-id'));
        if (cid === addCornerConnId) {
          const conn = state.connections.find(c => c.id === cid);
          if (conn) {
            const { x, y } = screenToSVG(e.clientX, e.clientY);
            insertCornerOnConn(conn, x, y);
            snapshot(); render(); updateProps();
          }
        }
      }
      addCornerConnId = null;
      return;
    }

    // Suppression d'un coin de connexion via le bouton ×
    const delCornerEl = e.target.closest('[data-conn-del-corner]');
    if (delCornerEl) {
      const cid    = parseInt(delCornerEl.getAttribute('data-conn-del-corner'));
      const ptIdx  = parseInt(delCornerEl.getAttribute('data-del-pt-idx'));
      const conn   = state.connections.find(c => c.id === cid);
      if (conn) {
        if (!conn.userPts) {
          const pts = conn._computedOrthopts || [];
          conn.userPts = pts.slice(1, -1).map(p => ({ x: p.x, y: p.y }));
        }
        if (ptIdx >= 1 && ptIdx - 1 < conn.userPts.length) {
          conn.userPts.splice(ptIdx - 1, 1);
          if (conn.userPts.length === 0) conn.userPts = null;
        }
        snapshot(); render();
      }
      return;
    }

    // Drag d'un coin de connexion — déplacement libre en X et Y
    const cornerEl = e.target.closest('[data-conn-corner]');
    if (cornerEl) {
      const cid   = parseInt(cornerEl.getAttribute('data-conn-corner'));
      let   ptIdx = parseInt(cornerEl.getAttribute('data-pt-idx'));
      const { x, y } = screenToSVG(e.clientX, e.clientY);
      const conn = state.connections.find(c => c.id === cid);
      if (!conn) return;
      const pts = conn._computedOrthopts || [];
      if (ptIdx < 1 || ptIdx >= pts.length - 1) return;
      if (!conn.userPts) conn.userPts = pts.slice(1, -1).map(p => ({ x: p.x, y: p.y }));

      // Pre-expand: insert helper corners when dragged corner is adjacent to src or dst.
      // This guarantees all angles stay at 90° during drag.
      const N = pts.length;
      const needPrevHelper = ptIdx === 1;
      const needNextHelper = ptIdx === N - 2;

      let srcToCornerIsH = false, cornerToDstIsH = false;
      if (needPrevHelper || needNextHelper) {
        srcToCornerIsH = Math.abs(pts[1].x - pts[0].x) > Math.abs(pts[1].y - pts[0].y);
        cornerToDstIsH = Math.abs(pts[N-1].x - pts[N-2].x) > Math.abs(pts[N-1].y - pts[N-2].y);
        if (needPrevHelper) {
          const A = srcToCornerIsH
            ? { x: pts[ptIdx].x, y: pts[0].y }
            : { x: pts[0].x,     y: pts[ptIdx].y };
          conn.userPts.splice(ptIdx - 1, 0, A);
          ptIdx++; // dragged corner shifted right
        }
        if (needNextHelper) {
          const origCorner = pts[needPrevHelper ? ptIdx - 1 : N - 2];
          const B = cornerToDstIsH
            ? { x: origCorner.x, y: pts[N-1].y }
            : { x: pts[N-1].x,   y: origCorner.y };
          conn.userPts.splice(ptIdx, 0, B);
        }
      }

      // Rebuild startPts from expanded userPts
      const newStartPts = [pts[0], ...conn.userPts.map(p => ({ x: p.x, y: p.y })), pts[N-1]];

      cornerSnapPreview = false;
      cornerDrag = {
        connId: cid, ptIdx,
        startX: x, startY: y,
        startPts: newStartPts,
        needPrevHelper, needNextHelper,
        srcToCornerIsH, cornerToDstIsH,
        noSnap: needPrevHelper || needNextHelper,
      };
      canvas.style.cursor = 'move';
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

    // Decision direction badge click — cycle direction of O/N on diamond shape
    const dirBadgeEl = e.target.closest('[data-type="decision-dir-badge"]');
    if (dirBadgeEl) {
      const sid = parseInt(dirBadgeEl.getAttribute('data-shape-id'));
      const shape = state.shapes.find(s => s.id === sid);
      if (shape && shape.type === 'decision') {
        const dirs = [null, 'right', 'down', 'left', 'up'];
        const cur = shape.decisionYesDir ?? null;
        const idx = dirs.indexOf(cur);
        shape.decisionYesDir = dirs[(idx + 1) % dirs.length];
        _syncChoiceLabels(shape);
        snapshot();
        render();
      }
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

    // Drag d'une pile fermée → déplace toutes ses formes ensemble
    const collapsedGrpTarget = e.target.closest('[data-group-id]');
    if (collapsedGrpTarget) {
      const gid = parseInt(collapsedGrpTarget.getAttribute('data-group-id'));
      const grp = state.groups && state.groups.find(g => g.id === gid);
      if (grp && grp.isPile && collapsedPiles.has(gid)) {
        selectedGroup = gid;
        selectedShapes.clear(); selectedConn = null; selectedBand = null;
        dragData = {
          mx: x, my: y,
          moved: false,
          pileGroupId: gid,
          shapes: grp.shapeIds.map(id => {
            const s = state.shapes.find(s => s.id === id);
            const b = s ? getBandForY(s.y + s.h / 2) : null;
            return s ? { id, ox: s.x, oy: s.y, bandId: b ? b.id : null } : null;
          }).filter(Boolean),
        };
        isDragging = true;
        // Ne pas appeler render() ici : le DOM serait reconstruit avant le click event,
        // ce qui empêcherait le toggle de la pile par clic simple.
        updateProps();
        if (!propsOpen) setPropsOpen(true);
        return;
      }
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
          const b = getBandForY(s.y + s.h / 2);
          return { id, ox: s.x, oy: s.y, bandId: b ? b.id : null };
        }),
      };
      isDragging = true;
      render();
      updateProps();
      return;
    }

    // Start panning; deselect only on mouseup if the mouse didn't actually move
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
          showToast(_L('editor.toast.backward_arrow'));
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
            decisionBranch: null,
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
  _updateEdgeScroll(e.clientX, e.clientY);

  /* ── Lasso drag ── */
  if (lassoDrag) {
    lassoDrag.curSX = e.clientX;
    lassoDrag.curSY = e.clientY;
    _updateLassoRect();
    return;
  }

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
      const newHeight = Math.max(bandResizeMinHeight, Math.round(bandHeightStartValue + dy));
      const delta = newHeight - bandHeightStartValue;
      b.height = newHeight;
      for (const { shape, startY } of bandResizeShapeStarts) {
        shape.y = startY + delta;
      }
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
    portDrag.curX = x;
    portDrag.curY = y;
    portDrag.snapShapeId = null;
    portDrag.snapDir     = null;
    portDrag.snapT       = 0.5;
    portDrag.snapX       = null;
    portDrag.snapY       = null;

    const SNAP_R = 55;
    let bestDist = SNAP_R, bestId = null, bestPt = null;
    for (const s of state.shapes) {
      if (s.id === portDrag.fromShapeId) continue;
      for (const pt of getDetailedPorts(s)) {
        const d = Math.hypot(x - pt.x, y - pt.y);
        if (d < bestDist) { bestDist = d; bestId = s.id; bestPt = pt; }
      }
    }
    for (const grp of (state.groups || [])) {
      if (grp.id === portDrag.fromShapeId) continue;
      for (const pt of getGroupDetailedPorts(grp)) {
        const d = Math.hypot(x - pt.x, y - pt.y);
        if (d < bestDist) { bestDist = d; bestId = grp.id; bestPt = pt; }
      }
    }
    if (bestId !== null && bestPt) {
      portDrag.snapShapeId = bestId;
      portDrag.snapDir     = bestPt.dir;
      portDrag.snapT       = bestPt.t;
      portDrag.snapX       = bestPt.x;
      portDrag.snapY       = bestPt.y;
    }

    gOverlay.innerHTML = '';
    const fp = portDrag.fromPort;
    const tx = (portDrag.snapShapeId !== null && portDrag.snapX != null) ? portDrag.snapX : x;
    const ty = (portDrag.snapShapeId !== null && portDrag.snapY != null) ? portDrag.snapY : y;
    el('path', {
      d: `M ${fp.x},${fp.y} L ${tx},${ty}`,
      fill: 'none', stroke: '#3b82f6',
      'stroke-width': `${Math.max(1, 2 / vpScale)}`,
      'stroke-dasharray': `${Math.max(4, 7 / vpScale)},${Math.max(3, 5 / vpScale)}`,
      'pointer-events': 'none',
    }, gOverlay);
    renderHandles();
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

  /* ── Drag d'un coin de connexion (X et Y libres) ── */
  if (cornerDrag) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    const conn = state.connections.find(c => c.id === cornerDrag.connId);
    if (!conn || !conn.userPts) return;
    const dx   = x - cornerDrag.startX;
    const dy   = y - cornerDrag.startY;
    const sp   = cornerDrag.startPts; // snapshot des orthopts au début du drag
    const i    = cornerDrag.ptIdx;    // index dans orthopts (1..N-2)
    const N    = sp.length;

    const newX = sp[i].x + dx;
    const newY = sp[i].y + dy;

    // Déplacer le coin draggé (userPts[i-1])
    conn.userPts[i - 1] = { x: newX, y: newY };

    // Propagation aux coins adjacents pour maintenir l'orthogonalité
    const prevIsH = i > 0 &&
      Math.abs(sp[i - 1].x - sp[i].x) > Math.abs(sp[i - 1].y - sp[i].y);
    const nextIsH = i < N - 1 &&
      Math.abs(sp[i + 1].x - sp[i].x) > Math.abs(sp[i + 1].y - sp[i].y);

    // Segment précédent horizontal → propager Y au coin précédent
    if (prevIsH && i - 2 >= 0) {
      conn.userPts[i - 2] = { x: sp[i - 1].x, y: newY };
    }
    // Segment précédent vertical → propager X au coin précédent
    if (!prevIsH && i - 2 >= 0) {
      conn.userPts[i - 2] = { x: newX, y: sp[i - 1].y };
    }
    // Segment suivant horizontal → propager Y au coin suivant
    if (nextIsH && i < N - 2) {
      conn.userPts[i] = { x: sp[i + 1].x, y: newY };
    }
    // Segment suivant vertical → propager X au coin suivant
    if (!nextIsH && i < N - 2) {
      conn.userPts[i] = { x: newX, y: sp[i + 1].y };
    }

    // Analytically override helper positions to guarantee right angles even when
    // the direction detection above is ambiguous (degenerate initial positions).
    if (cornerDrag.needPrevHelper) {
      // A is at userPts[i-2]; fp is sp[0]
      conn.userPts[i - 2] = cornerDrag.srcToCornerIsH
        ? { x: newX,      y: sp[0].y }
        : { x: sp[0].x,   y: newY    };
    }
    if (cornerDrag.needNextHelper) {
      // B is at userPts[i]; tp is sp[N-1]
      conn.userPts[i] = cornerDrag.cornerToDstIsH
        ? { x: newX,      y: sp[N - 1].y }
        : { x: sp[N - 1].x, y: newY      };
    }

    // Snap-to-straight : angle ≈ 180° (177–183°) → preview suppression
    // Disabled when helpers were auto-inserted (noSnap) to avoid false positives.
    if (!cornerDrag.noSnap) {
      const up = conn.userPts;
      const prevPt = (i - 2 >= 0 && up[i - 2]) ? up[i - 2] : sp[0];
      const nextPt = (i <= up.length - 1 && up[i])  ? up[i]  : sp[N - 1];
      const angle  = cornerAngleDeg(prevPt, { x: newX, y: newY }, nextPt);
      cornerSnapPreview = angle >= 177 && angle <= 183;
    }

    render();
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
    let bestDist = SNAP_R, bestId = null, bestPt = null;
    for (const s of state.shapes) {
      for (const pt of getDetailedPorts(s)) {
        const d = Math.hypot(x - pt.x, y - pt.y);
        if (d < bestDist) { bestDist = d; bestId = s.id; bestPt = pt; }
      }
    }
    for (const grp of (state.groups || [])) {
      for (const pt of getGroupDetailedPorts(grp)) {
        const d = Math.hypot(x - pt.x, y - pt.y);
        if (d < bestDist) { bestDist = d; bestId = grp.id; bestPt = pt; }
      }
    }
    if (bestId !== null && bestPt) {
      connEndDrag.snapShapeId = bestId;
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
  const portTarget  = !hoverTarget ? e.target.closest('[data-port]') : null;
  let newHover = hoverTarget
    ? parseInt(hoverTarget.getAttribute('data-id'))
    : (portTarget ? parseInt(portTarget.getAttribute('data-shape-id')) : null);
  // Fallback: expand detection to border/stroke area so ports stay visible near edges
  if (newHover === null && !portDrag && !isDragging) {
    const { x: hx, y: hy } = screenToSVG(e.clientX, e.clientY);
    const BORDER = 12;
    for (let i = state.shapes.length - 1; i >= 0; i--) {
      const s = state.shapes[i];
      if (hx >= s.x - BORDER && hx <= s.x + s.w + BORDER &&
          hy >= s.y - BORDER && hy <= s.y + s.h + BORDER) {
        newHover = s.id;
        break;
      }
    }
  }
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
  edgeScrollVX = 0; edgeScrollVY = 0;

  /* ── Fin du lasso ── */
  if (lassoDrag) {
    _finalizeLasso();
    return;
  }

  /* ── Fin du drag d'un label ── */
  if (labelDrag) {
    labelDrag = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    snapshot();
    render();
    return;
  }

  /* ── Fin du drag d'un coin ── */
  if (cornerDrag) {
    const conn = state.connections.find(c => c.id === cornerDrag.connId);
    if (conn) {
      if (cornerSnapPreview) {
        // Remove dragged corner + any auto-inserted helpers around it
        const nPrev = cornerDrag.needPrevHelper ? 1 : 0;
        const nNext = cornerDrag.needNextHelper ? 1 : 0;
        const removeStart = cornerDrag.ptIdx - 1 - nPrev;
        const removeCount = 1 + nPrev + nNext;
        if (conn.userPts && removeStart >= 0 && removeStart < conn.userPts.length) {
          conn.userPts.splice(removeStart, removeCount);
          if (conn.userPts.length === 0) conn.userPts = null;
          else _orthogonalizeUserPts(conn); // ensure remaining segments stay 90°
        }
      } else {
        mergeOverlappingCorners(conn);
      }
    }
    cornerSnapPreview = false;
    cornerDrag = null;
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
        // Compare actual port X positions to avoid false positives on vertical connections
        const _fromPx = _portX(which === 'from' ? snapShapeId : conn.fromId,
                                which === 'from' ? snapDir     : conn.fromPortDir,
                                which === 'from' ? snapT       : conn.fromPortT);
        const _toPx   = _portX(which === 'to'   ? snapShapeId : conn.toId,
                                which === 'to'   ? snapDir     : conn.toPortDir,
                                which === 'to'   ? snapT       : conn.toPortT);
        const _isBackwards = (_fromPx !== null && _toPx !== null)
          ? _toPx < _fromPx
          : wouldBeBackwards(newFromId, newToId);
        if (_isBackwards) {
          showToast(_L('editor.toast.backward_arrow'));
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
          // Le point d'ancrage a changé : reset du coude manuel pour éviter les angles non-90°
          conn.bendOffset = null;
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
    bandResizeShapeStarts = [];
    bandResizeMinHeight   = 60;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    snapshot();
    return;
  }

  /* ── Fin du drag depuis un port ── */
  if (portDrag) {
    const { x, y } = screenToSVG(e.clientX, e.clientY);
    let target = null;
    let toPortDir = null, toPortT = null;

    if (portDrag.snapShapeId !== null && portDrag.snapShapeId !== undefined) {
      const snapShape = state.shapes.find(s => s.id === portDrag.snapShapeId);
      if (snapShape) {
        target = snapShape;
      } else {
        const snapGroup = state.groups && state.groups.find(g => g.id === portDrag.snapShapeId);
        const gb = snapGroup && getGroupBounds(snapGroup);
        target = gb ? { ...gb, id: snapGroup.id } : null;
      }
      toPortDir = portDrag.snapDir;
      toPortT   = portDrag.snapT;
    } else {
      const shapeHit = shapeAtPoint(x, y);
      const groupHit = !shapeHit && state.groups && state.groups.find(g => {
        const b = getGroupBounds(g);
        return b && x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h;
      });
      target = shapeHit || (groupHit ? { ...getGroupBounds(groupHit), id: groupHit.id } : null);
    }

    if (target && target.id !== portDrag.fromShapeId) {
      const fp = portDrag.fromPort;
      // Autoriser plusieurs connexions entre mêmes shapes si ports différents
      const exists = state.connections.some(
        c => c.fromId === portDrag.fromShapeId &&
             c.toId   === target.id &&
             c.fromPortDir === fp.dir
      );
      if (!exists) {
        // Compare actual port X positions rather than shape centers
        const _toPx = portDrag.snapShapeId
          ? (() => { const _s = state.shapes.find(s => s.id === portDrag.snapShapeId); const _p = _s && getDetailedPorts(_s).find(p => p.dir === portDrag.snapDir && Math.abs(p.t - portDrag.snapT) < 0.02); return _p ? _p.x : (_s ? _s.x + _s.w / 2 : null); })()
          : (target.x + target.w / 2);
        if (_toPx !== null && _toPx < portDrag.fromPort.x) {
          showToast(_L('editor.toast.backward_arrow'));
        } else {
          const fromShape = state.shapes.find(s => s.id === portDrag.fromShapeId);
          const conn = {
            id: state.nextId++,
            fromId: portDrag.fromShapeId,
            toId: target.id,
            fromPortDir: fp.dir,
            fromPortT:   fp.t !== undefined ? fp.t : undefined,
            style: 'solid',
            routing: state.defaultRouting || 'smooth',
            color: fromShape ? fromShape.color : '#9ca3af',
            label: '',
          };
          if (toPortDir) { conn.toPortDir = toPortDir; conn.toPortT = toPortT; }
          state.connections.push(conn);
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
    const panDidMove = panStart && panStart.moved;
    panStart = null;
    canvas.style.cursor = spaceDown ? 'grab' : '';
    // Click on empty area (no pan movement) → deselect
    if (!panDidMove) {
      const hadSelection = selectedBand !== null || selectedGroup !== null || selectedShapes.size > 0 || selectedConn !== null;
      clearSelection();
      if (hadSelection) { if (propsOpen) setPropsOpen(false); render(); updateProps(); }
    }
  }
  if (isDragging) {
    isDragging = false;
    if (dragData) {
      if (dragData.moved) {
        for (const { id, bandId: prevBandId } of dragData.shapes) {
          const s = state.shapes.find(s => s.id === id);
          if (s) {
            const newBand = getBandForY(s.y + s.h / 2);
            // Only sync band color when shape moved to a different band
            if (prevBandId === null || !newBand || prevBandId !== newBand.id) {
              updateShapeColor(s);
            }
            // Grow the majority band to fully contain the shape if it straddles two bands
            _fitShapeIntoBand(s);
          }
          // Les tracés manuels deviennent incohérents quand la shape source/cible bouge
          for (const conn of state.connections) {
            if (conn.fromId === id || conn.toId === id) conn.userPts = null;
          }
        }
        snapshot();
        render();
      } else if (dragData.pileGroupId != null) {
        // Clic sans mouvement sur pile fermée → ouvre/ferme la pile
        const gid = dragData.pileGroupId;
        if (collapsedPiles.has(gid)) collapsedPiles.delete(gid);
        else collapsedPiles.add(gid);
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
    if (c.userPts) {
      // Double-clic sur connexion avec tracé manuel → réinitialise le tracé
      c.userPts = null;
      snapshot(); render();
      showToast(_L('editor.toast.path_reset'));
    } else {
      const v = prompt(_L('editor.prompt.conn_label'), c.label || '');
      if (v !== null) { c.label = v.trim(); snapshot(); render(); }
    }
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
    if (s.type === 'start-end') {
      _updateRenvoiColor(s);
      // Regression fix: auto-link wasn't created when label was set after connection
      for (const conn of state.connections) {
        if (conn.toId === s.id) { _checkRenvoiAutoLink(conn.fromId, s.id); break; }
      }
    }
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
    // Liaison label — visible only for extco shapes that have an active liaison
    const liaisonRow = document.getElementById('prop-liaison-row');
    if (liaisonRow) {
      const liaison = s.subtype === 'extco' ? _liaisonByActivityId[String(s.id)] : null;
      liaisonRow.style.display = liaison ? '' : 'none';
      if (liaison) {
        const liaisonInput = document.getElementById('prop-liaison-label');
        if (liaisonInput) liaisonInput.value = liaison.display_label || '';
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
    const rSmooth = document.getElementById('conn-routing-smooth');
    const rOrtho  = document.getElementById('conn-routing-ortho');
    if (rSmooth) rSmooth.checked = (c.routing || 'smooth') === 'smooth';
    if (rOrtho)  rOrtho.checked  = c.routing === 'orthogonal';
    document.getElementById('conn-color').value = c.color || '#9ca3af';
    document.getElementById('conn-label').value = c.label || '';
    const addCornerGroup = document.getElementById('add-corner-group');
    if (addCornerGroup) addCornerGroup.style.display = c.routing === 'orthogonal' ? '' : 'none';
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
  // Bouton "Ajouter un angle"
  document.getElementById('btn-add-corner')?.addEventListener('click', () => {
    const c = state.connections.find(c => c.id === selectedConn);
    if (!c || c.routing !== 'orthogonal') return;
    addCornerMode = !addCornerMode;
    addCornerConnId = addCornerMode ? selectedConn : null;
    canvas.style.cursor = addCornerMode
      ? 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'20\' height=\'20\'%3E%3Crect x=\'7\' y=\'7\' width=\'6\' height=\'6\' fill=\'%23111827\' transform=\'rotate(45 10 10)\'/%3E%3C/svg%3E") 10 10, crosshair'
      : '';
    document.getElementById('btn-add-corner')?.classList.toggle('active', addCornerMode);
  });

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
    for (const id of selectedShapes) { const s = state.shapes.find(s => s.id === id); if (s) { s.color = v; s.textColor = bandTextColor(v); } }
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

  // Liaison label — PATCH to API on change (debounced)
  let _liaisonLabelTimer = null;
  document.getElementById('prop-liaison-label')?.addEventListener('input', e => {
    const id = [...selectedShapes][0];
    if (!id) return;
    const liaison = _liaisonByActivityId[String(id)];
    if (!liaison) return;
    // Optimistic update in-memory
    liaison.display_label = e.target.value.trim() || null;
    render();
    clearTimeout(_liaisonLabelTimer);
    _liaisonLabelTimer = setTimeout(async () => {
      const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
      try {
        await fetch(`${apiBase}/api/liaisons/${liaison.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ display_label: liaison.display_label }),
        });
      } catch (_) {}
    }, 600);
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
   MINIMAP (mini-carte de navigation — OUTIL uniquement)
   Aperçu réduit de la carto + cadre déplaçable qui pilote
   le cadrage du canvas (drag = pan). Le cadre reflète le zoom.
   ══════════════════════════════════════════════════ */
const MINI_W = 200, MINI_H = 144, MINI_PAD = 8;
let _mini = null;
let _miniSig = '';
window.__miniReady = true;   // applyViewport peut désormais appeler renderMinimap()

function _miniBounds() {
  if (!state.shapes.length) return null;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of state.shapes) {
    minX = Math.min(minX, s.x); minY = Math.min(minY, s.y);
    maxX = Math.max(maxX, s.x + s.w); maxY = Math.max(maxY, s.y + s.h);
  }
  if (state.showBands && state.bands.length > 0) minX = Math.min(minX, 0);
  const padW = (maxX - minX) * 0.04 + 20, padH = (maxY - minY) * 0.04 + 20;
  return { minX: minX - padW, minY: minY - padH, maxX: maxX + padW, maxY: maxY + padH };
}

function _buildMinimap() {
  const parent = (canvas && canvas.parentElement) || document.body;
  if (getComputedStyle(parent).position === 'static') parent.style.position = 'relative';
  const wrap = document.createElement('div');
  wrap.id = 'carto-minimap';
  wrap.title = '';
  wrap.innerHTML =
    `<div class="mini-header" title="Glissez pour déplacer la mini-carte">
       <span class="mini-grip"></span><span class="mini-title">Mini-carte</span>
     </div>
     <svg width="${MINI_W}" height="${MINI_H}" viewBox="0 0 ${MINI_W} ${MINI_H}"
          title="Glissez le cadre pour vous déplacer, ou les coins pour zoomer">
       <rect class="mini-bg" x="0" y="0" width="${MINI_W}" height="${MINI_H}" rx="9"/>
       <g id="mini-content"></g>
       <rect id="mini-frame" class="mini-frame" x="0" y="0" width="10" height="10" rx="2"/>
       <circle class="mini-handle" data-c="nw" r="5"/>
       <circle class="mini-handle" data-c="ne" r="5"/>
       <circle class="mini-handle" data-c="sw" r="5"/>
       <circle class="mini-handle" data-c="se" r="5"/>
     </svg>`;
  parent.appendChild(wrap);
  _mini = {
    wrap, svg: wrap.querySelector('svg'),
    content: wrap.querySelector('#mini-content'),
    frame: wrap.querySelector('#mini-frame'),
    handles: Array.from(wrap.querySelectorAll('.mini-handle')),
    header: wrap.querySelector('.mini-header'),
    bbox: null, ms: 1, offX: 0, offY: 0,
  };
  _attachMinimapDrag();
  _attachMinimapReposition(_mini.header);
  window.addEventListener('resize', () => { if (_mini && _mini.bbox) _updateMinimapFrame(); });
}

function _drawMiniShapes(b) {
  const cw = (b.maxX - b.minX) || 1, ch = (b.maxY - b.minY) || 1;
  const availW = MINI_W - MINI_PAD * 2, availH = MINI_H - MINI_PAD * 2;
  const ms = Math.min(availW / cw, availH / ch);
  _mini.ms = ms;
  _mini.offX = MINI_PAD + (availW - cw * ms) / 2;
  _mini.offY = MINI_PAD + (availH - ch * ms) / 2;
  _mini.bbox = b;
  const parts = [];
  for (const s of state.shapes) {
    const x = _mini.offX + (s.x - b.minX) * ms;
    const y = _mini.offY + (s.y - b.minY) * ms;
    const w = Math.max(1.2, s.w * ms), h = Math.max(1.2, s.h * ms);
    const fill = s.type === 'special' ? '#f9a8d4' : (s.type === 'start-end' ? '#c7d2fe' : '#94a3b8');
    parts.push(`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="1.5" fill="${fill}"/>`);
  }
  _mini.content.innerHTML = parts.join('');
}

function _updateMinimapFrame() {
  if (!_mini || !_mini.bbox || !canvas) return;
  const r = canvas.getBoundingClientRect();
  const { minX, minY } = _mini.bbox, ms = _mini.ms, offX = _mini.offX, offY = _mini.offY;
  const worldLeft = -vpX / vpScale, worldTop = -vpY / vpScale;
  const worldW = r.width / vpScale, worldH = r.height / vpScale;
  const fx = offX + (worldLeft - minX) * ms;
  const fy = offY + (worldTop - minY) * ms;
  const fw = Math.max(6, worldW * ms), fh = Math.max(6, worldH * ms);
  _mini.frame.setAttribute('x', fx.toFixed(1));
  _mini.frame.setAttribute('y', fy.toFixed(1));
  _mini.frame.setAttribute('width',  fw.toFixed(1));
  _mini.frame.setAttribute('height', fh.toFixed(1));
  // Poignées de redimensionnement aux 4 coins du cadre
  const corners = { nw: [fx, fy], ne: [fx + fw, fy], sw: [fx, fy + fh], se: [fx + fw, fy + fh] };
  for (const h of (_mini.handles || [])) {
    const c = corners[h.dataset.c];
    if (c) { h.setAttribute('cx', c[0].toFixed(1)); h.setAttribute('cy', c[1].toFixed(1)); }
  }
}

function renderMinimap() {
  if (window.OPTIQCARTO_READONLY) return;   // mini-carte = OUTIL uniquement
  if (!_mini) _buildMinimap();
  const b = _miniBounds();
  if (!b) { _mini.wrap.style.display = 'none'; _miniSig = ''; return; }
  _mini.wrap.style.display = '';
  const sig = state.shapes.length + '|' + b.minX.toFixed(0) + ',' + b.minY.toFixed(0)
            + ',' + b.maxX.toFixed(0) + ',' + b.maxY.toFixed(0) + '|' + (state.showBands ? 'b' : '');
  if (sig !== _miniSig) { _miniSig = sig; _drawMiniShapes(b); }
  _updateMinimapFrame();
}

function _centerCanvasOnMini(mx, my) {
  if (!_mini || !_mini.bbox) return;
  const { minX, minY } = _mini.bbox, ms = _mini.ms, offX = _mini.offX, offY = _mini.offY;
  const wx = (mx - offX) / ms + minX, wy = (my - offY) / ms + minY;
  const r = canvas.getBoundingClientRect();
  vpX = r.width / 2 - wx * vpScale;
  vpY = r.height / 2 - wy * vpScale;
  applyViewport();
}

function _attachMinimapDrag() {
  let mode = null;        // 'move' | 'resize'
  let centerW = null;     // centre du cadre figé pendant un resize (coords monde)
  const toLocal = (e) => {
    const rect = _mini.svg.getBoundingClientRect();
    return { mx: e.clientX - rect.left, my: e.clientY - rect.top };
  };
  const miniToWorld = (mx, my) => ({
    wx: (mx - _mini.offX) / _mini.ms + _mini.bbox.minX,
    wy: (my - _mini.offY) / _mini.ms + _mini.bbox.minY,
  });

  // Poignées de coin → redimensionnement (zoom) autour du centre du cadre
  for (const h of _mini.handles) {
    h.addEventListener('mousedown', (e) => {
      if (!_mini.bbox) return;
      mode = 'resize';
      _mini.wrap.classList.add('dragging');
      const r = canvas.getBoundingClientRect();
      centerW = {
        x: (-vpX / vpScale) + (r.width  / vpScale) / 2,
        y: (-vpY / vpScale) + (r.height / vpScale) / 2,
      };
      e.preventDefault(); e.stopPropagation();
    });
  }

  // Corps de la mini-carte → déplacement (pan)
  _mini.svg.addEventListener('mousedown', (e) => {
    if (e.target.classList && e.target.classList.contains('mini-handle')) return;
    mode = 'move';
    _mini.wrap.classList.add('dragging');
    const { mx, my } = toLocal(e);
    _centerCanvasOnMini(mx, my);
    e.preventDefault(); e.stopPropagation();
  });

  window.addEventListener('mousemove', (e) => {
    if (!mode || !_mini.bbox) return;
    const { mx, my } = toLocal(e);
    if (mode === 'move') { _centerCanvasOnMini(mx, my); return; }
    // resize : la distance coin↔centre fixe la taille du cadre → donc le zoom
    if (!centerW) return;
    const r = canvas.getBoundingClientRect();
    const aspect = r.width / r.height;
    const { wx, wy } = miniToWorld(mx, my);
    const ax = Math.abs(wx - centerW.x), ay = Math.abs(wy - centerW.y);
    const halfW = Math.max(40, ax, ay * aspect);   // demi-largeur visible (monde)
    let newScale = r.width / (2 * halfW);
    newScale = Math.max(0.05, Math.min(4, newScale));
    vpScale = newScale;
    vpX = r.width  / 2 - centerW.x * vpScale;
    vpY = r.height / 2 - centerW.y * vpScale;
    applyViewport();
  });

  window.addEventListener('mouseup', () => {
    if (mode) { mode = null; centerW = null; _mini.wrap.classList.remove('dragging'); }
  });
}

// Déplacement de la mini-carte elle-même (drag sur son en-tête) — la placer
// où l'on veut dans l'éditeur.
function _attachMinimapReposition(header) {
  let drag = null;
  header.addEventListener('mousedown', (e) => {
    const wrap = _mini.wrap;
    const parent = wrap.offsetParent || document.body;
    const wr = wrap.getBoundingClientRect();
    const pr = parent.getBoundingClientRect();
    // Bascule d'un ancrage right/bottom vers left/top pour pouvoir déplacer.
    wrap.style.left = (wr.left - pr.left) + 'px';
    wrap.style.top  = (wr.top  - pr.top)  + 'px';
    wrap.style.right = 'auto';
    wrap.style.bottom = 'auto';
    drag = {
      sx: e.clientX, sy: e.clientY,
      ox: wr.left - pr.left, oy: wr.top - pr.top,
      pw: pr.width, ph: pr.height, ww: wr.width, wh: wr.height,
    };
    _mini.wrap.classList.add('moving');
    e.preventDefault(); e.stopPropagation();
  });
  window.addEventListener('mousemove', (e) => {
    if (!drag) return;
    let nl = drag.ox + (e.clientX - drag.sx);
    let nt = drag.oy + (e.clientY - drag.sy);
    nl = Math.max(0, Math.min(drag.pw - drag.ww, nl));
    nt = Math.max(0, Math.min(drag.ph - drag.wh, nt));
    _mini.wrap.style.left = nl + 'px';
    _mini.wrap.style.top  = nt + 'px';
  });
  window.addEventListener('mouseup', () => {
    if (drag) { drag = null; _mini.wrap.classList.remove('moving'); }
  });
}

/* ══════════════════════════════════════════════════
   EXPORT — BANDE LÉGENDE STATIQUE
   ══════════════════════════════════════════════════ */

const EXPORT_LEGEND_H = 190;

function _buildExportLegend(legendY, bw) {
  const g    = el('g', { id: 'g-export-legend' });
  const IDX  = INDEX_W_SVG;
  const PINK = '#ec4899';
  const DARK = '#374151';
  const GRAY = '#6b7280';
  const ff   = 'Segoe UI, sans-serif';

  // Background
  el('rect', { x: 0, y: legendY, width: bw, height: EXPORT_LEGEND_H, fill: '#f9fafb' }, g);

  // Index column (pink, same style as bands)
  el('rect', { x: 0, y: legendY, width: IDX, height: EXPORT_LEGEND_H, fill: PINK }, g);
  el('line', { x1: IDX, y1: legendY, x2: IDX, y2: legendY + EXPORT_LEGEND_H,
    stroke: darkenColor(PINK, 0.72), 'stroke-width': '3' }, g);
  const tg = el('g', { transform: `rotate(-90, ${IDX / 2}, ${legendY + EXPORT_LEGEND_H / 2})` }, g);
  txt('LÉGENDE', {
    x: IDX / 2, y: legendY + EXPORT_LEGEND_H / 2,
    'text-anchor': 'middle', 'dominant-baseline': 'middle',
    fill: '#ffffff', 'font-size': '13', 'font-family': ff, 'font-weight': '700', 'letter-spacing': '1',
  }, tg);
  el('line', { x1: 0, y1: legendY + EXPORT_LEGEND_H, x2: bw, y2: legendY + EXPORT_LEGEND_H,
    stroke: darkenColor(PINK, 0.72), 'stroke-width': '3' }, g);

  // Layout constants
  const X0  = IDX + 32;
  const TY  = legendY + 20;    // section title
  const SY  = legendY + 38;    // shape top
  const SH  = 44;              // shape height
  const SW  = 110;             // shape width
  const GAP = 22;              // gap between samples
  const LBY = SY + SH + 11;   // bold label below shape
  const D1Y = LBY + 13;       // description line 1
  const D2Y = D1Y + 12;       // description line 2

  // Helper: label + description below a shape at column cx
  function shapeCaption(cx, label, d1, d2) {
    txt(label, {
      x: cx + SW / 2, y: LBY, 'text-anchor': 'middle',
      fill: DARK, 'font-size': '8.5', 'font-family': ff, 'font-weight': '700',
    }, g);
    txt(d1, {
      x: cx + SW / 2, y: D1Y, 'text-anchor': 'middle',
      fill: GRAY, 'font-size': '7.5', 'font-family': ff,
    }, g);
    if (d2) txt(d2, {
      x: cx + SW / 2, y: D2Y, 'text-anchor': 'middle',
      fill: GRAY, 'font-size': '7.5', 'font-family': ff,
    }, g);
  }

  // ── Section 1 : Types de formes ──────────────────────────────────────────
  txt('Types de formes', {
    x: X0, y: TY, fill: DARK, 'font-size': '10.5', 'font-weight': '700', 'font-family': ff,
  }, g);

  const shapeItems = [
    { label: 'Activité',       d1: 'Activité principale',     d2: 'de l\'entité',           color: '#96afcf', draw: 'rect'        },
    { label: 'Sous-activité',  d1: 'Variante atténuée',       d2: 'd\'une activité',         color: '#b5c9de', draw: 'rect-variant' },
    { label: 'Act. externe',   d1: 'Activité confiée à une',  d2: 'organisation externe',    color: '#e2e8f0', draw: 'rect-round'  },
    { label: 'Décision',       d1: 'Bifurcation oui / non',   d2: null,                      color: '#9ca3af', draw: 'diamond'     },
    { label: 'Renvoi',         d1: 'Référence vers',          d2: 'une autre activité',      color: '#f4f4f5', draw: 'circle'      },
  ];

  let cx = X0;
  for (const item of shapeItems) {
    const tc = bandTextColor(item.color);
    if (item.draw === 'rect') {
      el('rect', { x: cx, y: SY, width: SW, height: SH, rx: 3,
        fill: item.color, stroke: darkenColor(item.color, 0.65), 'stroke-width': '1.5' }, g);
      txt(item.label, { x: cx + SW / 2, y: SY + SH / 2,
        'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: tc, 'font-size': '8', 'font-family': ff, 'font-weight': '600' }, g);
    } else if (item.draw === 'rect-variant') {
      el('rect', { x: cx, y: SY, width: SW, height: SH, rx: 3,
        fill: item.color, stroke: darkenColor(item.color, 0.65),
        'stroke-width': '1.5', 'stroke-dasharray': '5,3' }, g);
      txt(item.label, { x: cx + SW / 2, y: SY + SH / 2,
        'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: tc, 'font-size': '8', 'font-family': ff, 'font-weight': '600' }, g);
    } else if (item.draw === 'rect-round') {
      el('rect', { x: cx, y: SY, width: SW, height: SH, rx: 14,
        fill: item.color, stroke: '#94a3b8', 'stroke-width': '1.5' }, g);
      txt(item.label, { x: cx + SW / 2, y: SY + SH / 2,
        'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: DARK, 'font-size': '7.5', 'font-family': ff, 'font-weight': '600' }, g);
    } else if (item.draw === 'diamond') {
      const dcx = cx + SW / 2, dcy = SY + SH / 2;
      el('polygon', {
        points: `${dcx},${SY} ${cx + SW},${dcy} ${dcx},${SY + SH} ${cx},${dcy}`,
        fill: item.color, stroke: '#6b7280', 'stroke-width': '1.5' }, g);
    } else if (item.draw === 'circle') {
      const r = SH / 2;
      el('circle', { cx: cx + r, cy: SY + r, r,
        fill: item.color, stroke: '#9ca3af', 'stroke-width': '1.5' }, g);
    }
    shapeCaption(cx, item.label, item.d1, item.d2);
    cx += SW + GAP;
  }

  // Vertical separator between the two sections
  cx += 16;
  el('line', { x1: cx, y1: legendY + 8, x2: cx, y2: legendY + EXPORT_LEGEND_H - 8,
    stroke: '#d1d5db', 'stroke-width': '1' }, g);
  cx += 20;

  // ── Section 2 : Types de liaisons ────────────────────────────────────────
  txt('Types de liaisons', {
    x: cx, y: TY, fill: DARK, 'font-size': '10.5', 'font-weight': '700', 'font-family': ff,
  }, g);

  const LW  = 88;  // arrow line length
  const L1Y = SY + 8;
  const L2Y = SY + SH - 8;

  // Solid → Déclenchante
  el('line', { x1: cx, y1: L1Y, x2: cx + LW, y2: L1Y, stroke: DARK, 'stroke-width': '2' }, g);
  el('polygon', { points: `${cx+LW},${L1Y} ${cx+LW-8},${L1Y-4} ${cx+LW-8},${L1Y+4}`, fill: DARK }, g);
  txt('Déclenchante', {
    x: cx + LW + 10, y: L1Y + 4, fill: DARK, 'font-size': '9', 'font-family': ff, 'font-weight': '700',
  }, g);
  txt('Démarre ou déclenche l\'activité cible', {
    x: cx + LW + 10, y: L1Y + 16, fill: GRAY, 'font-size': '7.5', 'font-family': ff,
  }, g);

  // Dashed → Nourrissante
  el('line', { x1: cx, y1: L2Y, x2: cx + LW, y2: L2Y,
    stroke: DARK, 'stroke-width': '2', 'stroke-dasharray': '8,4' }, g);
  el('polygon', { points: `${cx+LW},${L2Y} ${cx+LW-8},${L2Y-4} ${cx+LW-8},${L2Y+4}`, fill: DARK }, g);
  txt('Nourrissante', {
    x: cx + LW + 10, y: L2Y + 4, fill: DARK, 'font-size': '9', 'font-family': ff, 'font-weight': '700',
  }, g);
  txt('Nourrit, complète ou peut bloquer', {
    x: cx + LW + 10, y: L2Y + 16, fill: GRAY, 'font-size': '7.5', 'font-family': ff,
  }, g);

  return g;
}

/* ══════════════════════════════════════════════════
   EXPORT SVG
   ══════════════════════════════════════════════════ */

function _stripExportHidden(root) {
  root.querySelectorAll('[data-export-hidden="1"]').forEach(el => el.remove());
}

function exportSVG() {
  if (state.shapes.length === 0) { showToast(_L('editor.toast.no_shapes_export')); return; }

  const bw      = state.bandWidth || 3200;
  const legendY = -200 - EXPORT_LEGEND_H;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of state.shapes) {
    minX = Math.min(minX, s.x - 10);
    minY = Math.min(minY, s.y - 10);
    maxX = Math.max(maxX, s.x + s.w + 10);
    maxY = Math.max(maxY, s.y + s.h + 20);
  }
  const pad = 50;
  minX = Math.min(minX, 0) - pad;       // ensure x=0 (band origin) is always visible
  minY = Math.min(minY, legendY) - pad; // extend upward to include legend band
  maxX += pad; maxY += pad;
  const W = maxX - minX, H = maxY - minY;

  const svgNS = 'http://www.w3.org/2000/svg';
  const exportSVGEl = document.createElementNS(svgNS, 'svg');
  exportSVGEl.setAttribute('xmlns', svgNS);
  exportSVGEl.setAttribute('width', W);
  exportSVGEl.setAttribute('height', H);
  exportSVGEl.setAttribute('viewBox', `${minX} ${minY} ${W} ${H}`);

  const defs = canvas.querySelector('defs').cloneNode(true);
  exportSVGEl.appendChild(defs);

  // Legend band (static, always the same, placed above the first carto band)
  exportSVGEl.appendChild(_buildExportLegend(legendY, bw));

  // Clone content groups (bands, connections, shapes — no handles/overlay)
  for (const gId of ['g-bands', 'g-legend', 'g-connections', 'g-shapes']) {
    const clone = document.getElementById(gId).cloneNode(true);
    _stripExportHidden(clone);
    exportSVGEl.appendChild(clone);
  }

  const svgStr = new XMLSerializer().serializeToString(exportSVGEl);
  const blob = new Blob([svgStr], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'carto_optiq.svg';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  showToast(_L('editor.toast.svg_done'));
}

function exportPDF() {
  if (state.shapes.length === 0) { showToast(_L('editor.toast.no_shapes_export')); return; }

  const bw      = state.bandWidth || 3200;
  const legendY = -200 - EXPORT_LEGEND_H;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of state.shapes) {
    minX = Math.min(minX, s.x - 10);
    minY = Math.min(minY, s.y - 10);
    maxX = Math.max(maxX, s.x + s.w + 10);
    maxY = Math.max(maxY, s.y + s.h + 20);
  }
  const pad = 50;
  minX = Math.min(minX, 0) - pad;
  minY = Math.min(minY, legendY) - pad;
  maxX += pad; maxY += pad;
  const W = maxX - minX, H = maxY - minY;

  const svgNS = 'http://www.w3.org/2000/svg';
  const exportEl = document.createElementNS(svgNS, 'svg');
  exportEl.setAttribute('xmlns', svgNS);
  // For PDF: fixed A4 landscape dimensions in mm (297mm − 2×5mm margins = 287mm × 200mm).
  // The viewBox scales ALL content (carto + legend) to fit exactly on one page.
  exportEl.setAttribute('width',  '287mm');
  exportEl.setAttribute('height', '200mm');
  exportEl.setAttribute('viewBox', `${minX} ${minY} ${W} ${H}`);
  exportEl.setAttribute('preserveAspectRatio', 'xMinYMin meet');

  const defs = canvas.querySelector('defs').cloneNode(true);
  exportEl.appendChild(defs);
  exportEl.appendChild(_buildExportLegend(legendY, bw));
  for (const gId of ['g-bands', 'g-legend', 'g-connections', 'g-shapes']) {
    const clone = document.getElementById(gId).cloneNode(true);
    _stripExportHidden(clone);
    exportEl.appendChild(clone);
  }

  const svgStr = new XMLSerializer().serializeToString(exportEl);
  const encoded = encodeURIComponent(svgStr);
  const win = window.open('', '_blank');
  if (!win) { showToast(_L('editor.toast.popup_blocked')); return; }
  win.document.write(`<!DOCTYPE html><html><head><title>OptiqCarto — Export PDF</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:287mm; height:200mm; overflow:hidden; background:#fff; }
  img { display:block; width:287mm; height:200mm; }
  @media print {
    @page { margin:5mm; size:A4 landscape; }
    html, body { width:287mm; height:200mm; overflow:hidden; background:#fff; }
    img { display:block; width:287mm; height:200mm; page-break-inside:avoid; }
  }
</style></head><body>
<img src="data:image/svg+xml;charset=utf-8,${encoded}">
<script>
  var img = document.querySelector('img');
  img.onload = function() { setTimeout(function() { window.print(); }, 200); };
  img.onerror = function() { document.body.innerHTML += '<p style="color:red;padding:20px">Erreur de rendu SVG</p>'; };
</script>
</body></html>`);
  win.document.close();
  showToast(_L('editor.toast.pdf_done'));
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
    showToast(_L('editor.toast.group_min'));
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
  showToast(_L('editor.toast.group_created'));
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
  showToast(_L('editor.toast.new_carto'));
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

  if (activeCalqueId) return _saveCalque(apiBase);

  _showSavePopup('saving');

  try {
    state.collapsedPileIds = [...collapsedPiles]; // persister l'état ouvert/fermé
    const res  = await fetch(`${apiBase}/api/save`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ diagram: state }),
    });
    const data = await res.json();
    if (data.ok) {
      isDirty = false;
      clearTimeout(_autoSaveTimerId);
      _showSavePopup('done');
      if (data.sync_warning) setTimeout(() => showToast(_L('editor.toast.sync_error') + data.sync_warning, 'warn'), 1600);
      // After saving Master, offer to propagate to other calques
      _offerMasterPropagation(apiBase);
      return true;
    } else {
      _hideSavePopup();
      showToast(_L('editor.toast.error_prefix') + (data.error || _L('editor.toast.error_unknown')));
      return false;
    }
  } catch (err) {
    _hideSavePopup();
    showToast(_L('editor.toast.save_network_error'));
    return false;
  }
}

async function _offerMasterPropagation(apiBase) {
  let calques = [];
  try {
    const r = await fetch(`${apiBase}/api/calques`);
    calques = await r.json();
  } catch (_) { return; }
  if (!Array.isArray(calques) || calques.length === 0) return;

  // Build modal
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9998;display:flex;align-items:center;justify-content:center';
  const rows = calques.map(c => `
    <label style="display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;cursor:pointer;hover:background:#f8fafc">
      <input type="checkbox" class="calque-propagate-cb" data-id="${c.id}" checked
        style="width:16px;height:16px;accent-color:#ec4899;cursor:pointer">
      <span style="font-size:0.88rem;color:#1e293b">${c.name}</span>
    </label>`).join('');
  overlay.innerHTML = `
    <div style="background:#fff;border-radius:14px;padding:24px;min-width:340px;max-width:460px;box-shadow:0 8px 32px rgba(0,0,0,0.22)">
      <h3 style="margin:0 0 6px;font-size:1rem;font-weight:700;color:#1e293b">
        <i class="fa-solid fa-layer-group" style="color:#ec4899;margin-right:6px"></i>
        ${_L('editor.master_propagate_title')}
      </h3>
      <p style="margin:0 0 14px;font-size:0.82rem;color:#64748b">${_L('editor.master_propagate_desc')}</p>
      <div style="border:1.5px solid #e2e8f0;border-radius:10px;padding:6px 4px;margin-bottom:16px;max-height:220px;overflow-y:auto">${rows}</div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button id="_prop-skip" style="padding:7px 16px;border:1.5px solid #e2e8f0;border-radius:8px;background:#fff;cursor:pointer;font-size:0.85rem">${_L('editor.master_propagate_skip')}</button>
        <button id="_prop-apply" style="padding:7px 16px;border:none;border-radius:8px;background:linear-gradient(135deg,#ec4899,#be185d);color:#fff;cursor:pointer;font-size:0.85rem;font-weight:600">
          <i class="fa-solid fa-bolt"></i> ${_L('editor.master_propagate_apply')}
        </button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  overlay.querySelector('#_prop-skip').addEventListener('click', () => document.body.removeChild(overlay));
  overlay.querySelector('#_prop-apply').addEventListener('click', async () => {
    const checked = [...overlay.querySelectorAll('.calque-propagate-cb:checked')].map(cb => parseInt(cb.dataset.id));
    document.body.removeChild(overlay);
    if (checked.length === 0) return;
    let ok = 0, fail = 0;
    await Promise.all(checked.map(async id => {
      try {
        const r = await fetch(`${apiBase}/api/calques/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state }),
        });
        const d = await r.json();
        if (d.ok) ok++; else fail++;
      } catch (_) { fail++; }
    }));
    showToast(ok + ' ' + _L('editor.master_propagate_done') + (fail ? ` (${fail} échecs)` : ''));
  });
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

/* ── Auto-save & unsaved-changes guard ──────────────── */

function _scheduleAutoSave() {
  if (window.OPTIQCARTO_READONLY) return;
  clearTimeout(_autoSaveTimerId);
  _autoSaveTimerId = setTimeout(_triggerAutoSave, 10 * 60 * 1000);
}

function _triggerAutoSave() {
  if (!isDirty || window.OPTIQCARTO_READONLY) return;
  _showAutoSaveToast();
}

function _showAutoSaveToast() {
  const toast = document.getElementById('autosave-toast');
  const secsEl = document.getElementById('autosave-secs');
  if (!toast) return;
  let remaining = 30;
  if (secsEl) secsEl.textContent = remaining;
  toast.style.display = 'flex';

  function done(save) {
    clearInterval(_autoSaveToastInterval);
    _autoSaveToastInterval = null;
    toast.style.display = 'none';
    if (save && isDirty) saveJSON().then(() => {});
    else _scheduleAutoSave();
  }

  clearInterval(_autoSaveToastInterval);
  _autoSaveToastInterval = setInterval(() => {
    remaining--;
    if (secsEl) secsEl.textContent = remaining;
    if (remaining <= 0) done(true);
  }, 1000);

  const skipBtn = document.getElementById('autosave-btn-skip');
  const nowBtn  = document.getElementById('autosave-btn-now');
  if (skipBtn) skipBtn.onclick = () => done(false);
  if (nowBtn)  nowBtn.onclick  = () => done(true);
}

function _showUnsavedModal() {
  return new Promise(resolve => {
    const modal = document.getElementById('unsaved-modal');
    if (!modal) { resolve('discard'); return; }
    modal.style.display = 'flex';

    function cleanup(result) {
      modal.style.display = 'none';
      document.removeEventListener('keydown', onKey);
      resolve(result);
    }
    function onKey(e) {
      if ((e.key === 's' || e.key === 'S') && (e.ctrlKey || e.metaKey)) {
        e.preventDefault(); e.stopPropagation(); cleanup('save');
      }
      if (e.key === 'Escape') cleanup('cancel');
    }
    document.addEventListener('keydown', onKey);
    document.getElementById('unsaved-btn-save').onclick    = () => cleanup('save');
    document.getElementById('unsaved-btn-discard').onclick = () => cleanup('discard');
    document.getElementById('unsaved-btn-cancel').onclick  = () => cleanup('cancel');
    modal.onclick = e => { if (e.target === modal) cleanup('cancel'); };
  });
}

/* ── Calques ──────────────────────────────────────── */

async function _loadLiaisons() {
  if (window.OPTIQCARTO_READONLY) return;
  const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
  try {
    const res = await fetch(`${apiBase}/api/liaisons`);
    const list = await res.json();
    _liaisonByActivityId = {};
    for (const l of (Array.isArray(list) ? list : [])) {
      // Key by editor shape_id (string) so render can do O(1) lookup via s.id
      if (l.extco_shape_id != null) _liaisonByActivityId[String(l.extco_shape_id)] = l;
    }
  } catch (_) {}
}

async function _transitionState(newState) {
  const canvasWrap = document.getElementById('canvas-wrap');
  if (canvasWrap) {
    canvasWrap.style.transition = 'opacity 0.3s ease';
    canvasWrap.style.opacity = '0';
    await new Promise(r => setTimeout(r, 300));
  }
  state = JSON.parse(JSON.stringify(newState));
  if (!state.bandWidth) state.bandWidth = 3200;
  if (!state.groups) state.groups = [];
  if (state.connections && state.shapes) {
    const allIds = new Set([
      ...state.shapes.map(s => String(s.id)),
      ...(state.groups || []).map(g => String(g.id)),
    ]);
    state.connections = state.connections.filter(
      c => allIds.has(String(c.fromId)) && allIds.has(String(c.toId))
    );
  }
  _restoreCollapsedPiles();
  history = [JSON.stringify(state)]; histIndex = 0;
  await _loadLiaisons();
  render(); updateProps();
  if (canvasWrap) {
    await new Promise(r => setTimeout(r, 20));
    canvasWrap.style.opacity = '1';
  }
}

function _calcDiffPercent(baseState, calState) {
  function getElements(s) {
    const elems = {};
    (s.bands || []).forEach(b => { if (!b.deleted) elems['band_' + b.id] = JSON.stringify(b); });
    (s.shapes || []).forEach(sh => { elems['shape_' + sh.id] = JSON.stringify(sh); });
    (s.connections || []).forEach(c => { elems['conn_' + c.id] = JSON.stringify(c); });
    (s.groups || []).forEach(g => { elems['group_' + g.id] = JSON.stringify(g); });
    return elems;
  }
  const baseElems = getElements(baseState);
  const calElems  = getElements(calState);
  const allKeys = new Set([...Object.keys(baseElems), ...Object.keys(calElems)]);
  if (allKeys.size === 0) return 0;
  let diff = 0;
  for (const k of allKeys) {
    if (!baseElems[k] || !calElems[k] || baseElems[k] !== calElems[k]) diff++;
  }
  return diff / allKeys.size;
}

function _showCalDiffWarning(diffPct) {
  return new Promise(resolve => {
    const modal = document.getElementById('cal-diff-modal');
    const desc  = document.getElementById('cal-diff-desc');
    if (!modal) { resolve(true); return; }
    if (desc) desc.textContent = `${Math.round(diffPct * 100)} % des éléments de la carto classique sont modifiés ou absents dans ce calque. Êtes-vous sûr ? Si la divergence est trop importante, il peut être plus judicieux de créer une nouvelle entité avec une nouvelle cartographie.`;
    modal.style.display = 'flex';
    function cleanup(result) {
      modal.style.display = 'none';
      resolve(result);
    }
    document.getElementById('cal-diff-confirm').onclick = () => cleanup(true);
    document.getElementById('cal-diff-cancel').onclick  = () => cleanup(false);
    modal.onclick = e => { if (e.target === modal) cleanup(false); };
  });
}

async function _loadCalqueList() {
  const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
  try {
    const data  = await fetch(`${apiBase}/api/calques`).then(r => r.json());
    _calqueList = Array.isArray(data) ? data : (data.calques || []);
  } catch (_) { _calqueList = []; }
  renderCalqueListUI();
}

function renderCalqueListUI() {
  const list  = document.getElementById('cal-list');
  const empty = document.getElementById('cal-empty');
  if (!list) return;
  list.innerHTML = '';
  if (empty) empty.style.display = 'none';

  // Always show Master as first entry
  const masterItem = document.createElement('div');
  masterItem.className = 'cal-item cal-item-master' + (activeCalqueId === null ? ' active' : '');
  masterItem.innerHTML = `<i class="fa-solid fa-star" style="font-size:10px;opacity:0.7;flex-shrink:0"></i><span class="cal-item-name">Master</span>`;
  masterItem.addEventListener('click', async () => {
    const section = document.getElementById('cal-section');
    if (section) section.classList.remove('open');
    if (activeCalqueId !== null) await _deactivateCalque();
  });
  list.appendChild(masterItem);

  if (_calqueList.length === 0) return;

  _calqueList.forEach(cal => {
    const item = document.createElement('div');
    item.className = 'cal-item' + (activeCalqueId === cal.id ? ' active' : '');
    item.dataset.id = cal.id;
    item.innerHTML = `<span class="cal-item-name">${cal.name}</span><button class="cal-item-del" title="Supprimer ce calque"><i class="fa-solid fa-trash"></i></button>`;
    item.querySelector('.cal-item-name').addEventListener('click', async () => {
      const section = document.getElementById('cal-section');
      if (section) section.classList.remove('open');
      await _switchCalque(cal.id);
    });
    item.querySelector('.cal-item-del').addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm(_L('editor.confirm.delete_layer').replace('{name}', cal.name))) return;
      const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
      await fetch(`${apiBase}/api/calques/${cal.id}`, { method: 'DELETE' });
      if (activeCalqueId === cal.id) await _deactivateCalque();
      else await _loadCalqueList();
    });
    list.appendChild(item);
  });
}

function _updateCalqueBadge(name) {
  const badge     = document.getElementById('calque-badge');
  const badgeName = document.getElementById('calque-badge-name');
  if (!badge) return;
  if (name) {
    if (badgeName) badgeName.textContent = name;
    badge.style.display = 'flex';
  } else {
    badge.style.display = 'none';
  }
}

async function _switchCalque(calqueId) {
  if (calqueId === activeCalqueId) {
    await _deactivateCalque();
    return;
  }
  if (isDirty) {
    const result = await _showUnsavedModal();
    if (result === 'save') {
      const ok = await saveJSON();
      if (!ok) return;
    } else if (result === 'cancel') {
      return;
    } else {
      isDirty = false;
    }
  }
  await _activateCalque(calqueId);
}

async function _activateCalque(calqueId) {
  const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
  try {
    const res  = await fetch(`${apiBase}/api/calques/${calqueId}`);
    const data = await res.json();
    if (data.error) { showToast(_L('editor.toast.layer_load_error') + data.error); return; }
    activeCalqueId = calqueId;
    _calqueIsNew   = false;
    await _transitionState(data);
    isDirty = false;
    const cal = _calqueList.find(c => c.id === calqueId);
    _updateCalqueBadge(cal ? cal.name : 'Calque');
    renderCalqueListUI();
    // Sync DB + session with calque state
    fetch(`${apiBase}/api/calques/${calqueId}/apply`, { method: 'POST' }).catch(() => {});
  } catch (_) {
    showToast(_L('editor.toast.layer_network_error'));
  }
}

async function _deactivateCalque() {
  if (isDirty) {
    const result = await _showUnsavedModal();
    if (result === 'save') {
      const ok = await saveJSON();
      if (!ok) return;
    } else if (result === 'cancel') {
      return;
    } else {
      isDirty = false;
    }
  }
  activeCalqueId    = null;
  _calqueIsNew      = false;
  _baseStateForDiff = null;
  _updateCalqueBadge(null);
  renderCalqueListUI();
  const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
  // Restore DB to base carto state
  fetch(`${apiBase}/api/calques/deactivate`, { method: 'POST' }).catch(() => {});
  if (window.OPTIQCARTO_HAS_CARTO && window.OPTIQCARTO_DEFAULT_NAME) {
    try {
      const res  = await fetch(`${apiBase}/api/load/${encodeURIComponent(window.OPTIQCARTO_DEFAULT_NAME)}`);
      const data = await res.json();
      if (data && !data.error) {
        await _transitionState(data);
        isDirty = false;
      }
    } catch (_) {}
  }
}

async function _createCalque(name) {
  _baseStateForDiff = JSON.parse(JSON.stringify(state));
  _calqueIsNew      = true;
  const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';
  try {
    const res  = await fetch(`${apiBase}/api/calques`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ name, state }),
    });
    const data = await res.json();
    if (data.error) { showToast(_L('editor.toast.layer_create_error') + data.error); return; }
    activeCalqueId = data.id;
    await _loadCalqueList();
    _updateCalqueBadge(name);
    showToast(_L('editor.toast.layer_created').replace('{name}', name));
  } catch (_) {
    showToast(_L('editor.toast.layer_create_net_error'));
  }
}

async function _saveCalque(apiBase) {
  if (!activeCalqueId) return false;
  if (_calqueIsNew && _baseStateForDiff) {
    const diffPct = _calcDiffPercent(_baseStateForDiff, state);
    if (diffPct > 0.5) {
      const confirmed = await _showCalDiffWarning(diffPct);
      if (!confirmed) return false;
    }
    _calqueIsNew      = false;
    _baseStateForDiff = null;
  }
  _showSavePopup('saving');
  try {
    const res  = await fetch(`${apiBase}/api/calques/${activeCalqueId}`, {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ state }),
    });
    const data = await res.json();
    if (data.ok) {
      isDirty = false;
      clearTimeout(_autoSaveTimerId);
      _showSavePopup('done');
      return true;
    } else {
      _hideSavePopup();
      showToast(_L('editor.toast.error_prefix') + (data.error || _L('editor.toast.error_unknown')));
      return false;
    }
  } catch (_) {
    _hideSavePopup();
    showToast(_L('editor.toast.save_network_error'));
    return false;
  }
}

function initCalqueSection() {
  const section = document.getElementById('cal-section');
  const trigger = document.getElementById('btn-cal-toggle');
  if (!section || !trigger) return;

  trigger.addEventListener('click', e => {
    e.stopPropagation();
    const wasOpen = section.classList.contains('open');
    section.classList.toggle('open');
    if (!wasOpen) _loadCalqueList();
  });

  document.addEventListener('click', e => {
    if (!section.contains(e.target)) section.classList.remove('open');
  });

  const btnNew    = document.getElementById('btn-cal-new');
  const newRow    = document.getElementById('cal-new-row');
  const newInput  = document.getElementById('cal-new-input');
  const newConfirm = document.getElementById('cal-new-confirm');
  const newCancel = document.getElementById('cal-new-cancel');

  if (btnNew) btnNew.addEventListener('click', e => {
    e.stopPropagation();
    if (newRow) { newRow.style.display = 'flex'; if (newInput) { newInput.value = ''; newInput.focus(); } }
  });
  if (newCancel) newCancel.addEventListener('click', e => {
    e.stopPropagation();
    if (newRow) newRow.style.display = 'none';
  });
  if (newConfirm) newConfirm.addEventListener('click', async e => {
    e.stopPropagation();
    const name = newInput ? newInput.value.trim() : '';
    if (!name) { showToast(_L('editor.toast.layer_name_required')); return; }
    if (newRow) newRow.style.display = 'none';
    section.classList.remove('open');
    await _createCalque(name);
  });
  if (newInput) newInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') newConfirm && newConfirm.click();
    if (e.key === 'Escape') newCancel && newCancel.click();
  });

  const badgeDeact = document.getElementById('calque-badge-deactivate');
  if (badgeDeact) badgeDeact.addEventListener('click', async () => {
    await _deactivateCalque();
  });
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
      if (data.error) { showToast(_L('editor.toast.error_prefix') + data.error); return; }
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
      // Migration: reset deleted flag si toutes les bandes sont marquées supprimées
      if (state.bands && state.bands.length > 0 && state.bands.every(b => b.deleted)) {
        state.bands.forEach(b => { b.deleted = false; });
      }
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
      showToast(_L('editor.toast.loaded_prefix') + name);
    });

    item.querySelector('.load-delete').addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm(_L('editor.confirm.delete_carto').replace('{name}', name))) return;
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

// Nudge chaque losange de décision sur l'axe de flux de ses voisins CONNECTÉS
// Aère la carto : sépare les formes qui se chevauchent ou sont trop serrées
// (relaxation par paires). Objectif : « dénouer » les zones complexes et laisser de
// la place aux flèches/labels, SANS tout réarranger — seules les paires en dessous de
// minGap bougent (une carto déjà aérée n'est pas touchée), l'ordre relatif gauche/
// droite/haut/bas est préservé, et les formes groupées sont laissées intactes (on ne
// casse pas un groupe). C'est le « on sacrifie un peu la disposition d'origine pour
// gagner en lisibilité » demandé. Renvoie true si au moins une forme a bougé.
function _declutterShapes(minGap = 30, iters = 16) {
  const grouped = new Set();
  if (state.groups) for (const g of state.groups) (g.shapeIds || []).forEach(id => grouped.add(id));
  const nodes = state.shapes.filter(s => !grouped.has(s.id));
  if (nodes.length < 2) return false;
  const m = minGap / 2;
  let anyMoved = false;
  for (let it = 0; it < iters; it++) {
    let moved = false;
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j];
      const ox = Math.min(a.x + a.w + m, b.x + b.w + m) - Math.max(a.x - m, b.x - m);
      const oy = Math.min(a.y + a.h + m, b.y + b.h + m) - Math.max(a.y - m, b.y - m);
      if (ox <= 0 || oy <= 0) continue; // pas de chevauchement (marge incluse)
      // Repousse sur l'axe de moindre pénétration → déplacement minimal.
      if (ox <= oy) { const p = ox / 2 + 0.5, d = (a.x + a.w / 2) <= (b.x + b.w / 2) ? -1 : 1; a.x += d * p; b.x -= d * p; }
      else          { const p = oy / 2 + 0.5, d = (a.y + a.h / 2) <= (b.y + b.h / 2) ? -1 : 1; a.y += d * p; b.y -= d * p; }
      moved = true; anyMoved = true;
    }
    if (!moved) break;
  }
  if (anyMoved) for (const s of nodes) { s.x = Math.round(s.x); s.y = Math.round(s.y); }
  return anyMoved;
}

// (pré-routage). Un losange se branche par ses 4 pointes (milieux de côtés) : pour
// que les flèches le touchent bien droit (et qu'il ne paraisse pas « décalé »), son
// centre doit s'aligner sur ses voisins — X sur les voisins verticaux, Y sur les
// horizontaux. Déplacement borné (jamais de téléportation). Médiane = robuste aux
// cas où deux branches divergent. Renvoie true si au moins un losange a bougé.
function _alignDecisionsToNeighbors(maxShift = 80) {
  const byId = {}; for (const s of state.shapes) byId[s.id] = s;
  const median = arr => { const a = arr.slice().sort((x, y) => x - y); const m = a.length >> 1;
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2; };
  let moved = false;
  for (const D of state.shapes) {
    if (D.type !== 'decision') continue;
    const Dcx = D.x + D.w / 2, Dcy = D.y + D.h / 2;
    const cxVotes = [], cyVotes = [];
    for (const c of state.connections) {
      let N = null;
      if (c.fromId === D.id) N = byId[c.toId];
      else if (c.toId === D.id) N = byId[c.fromId];
      if (!N) continue;
      const Ncx = N.x + N.w / 2, Ncy = N.y + N.h / 2;
      // Relation dominante : plus verticale → la flèche entre/sort par une pointe
      // haut/bas → aligner le X du losange ; sinon aligner le Y.
      if (Math.abs(Ncy - Dcy) >= Math.abs(Ncx - Dcx)) cxVotes.push(Ncx);
      else cyVotes.push(Ncy);
    }
    if (cxVotes.length) {
      const shift = Math.max(-maxShift, Math.min(maxShift, median(cxVotes) - Dcx));
      if (Math.abs(shift) > 0.5) { D.x = Math.round(D.x + shift); moved = true; }
    }
    if (cyVotes.length) {
      const shift = Math.max(-maxShift, Math.min(maxShift, median(cyVotes) - Dcy));
      if (Math.abs(shift) > 0.5) { D.y = Math.round(D.y + shift); moved = true; }
    }
  }
  return moved;
}

// Demande à l'utilisateur comment reconstruire la carto importée :
//  • 'auto'    → notre agencement automatique (routage propre, très lisible)
//  • 'classic' → reconstruction fidèle à la disposition Visio d'origine (pixel)
// Renvoie une Promise('auto' | 'classic').
function _askVsdxLayoutMode() {
  return new Promise(resolve => {
    const ov = document.createElement('div');
    ov.className = 'modal-overlay';
    ov.style.zIndex = '10001';
    ov.innerHTML = `
      <div class="modal-card" style="max-width:460px;border-top:3px solid var(--pink)">
        <div class="modal-header"><h2 style="color:var(--pink)">
          <i class="fa-solid fa-wand-magic-sparkles" style="margin-right:8px;opacity:.9"></i>Reconstruire la cartographie</h2></div>
        <div class="modal-body" style="display:flex;flex-direction:column;gap:12px">
          <p style="font-size:13px;color:var(--text-muted);margin:0;line-height:1.6">
            Comment veux-tu reconstruire cette cartographie&nbsp;?</p>
          <button id="_vsdx-auto" class="btn-ok" style="width:100%;text-align:left;display:flex;gap:11px;align-items:flex-start;padding:13px 15px;border-radius:11px">
            <i class="fa-solid fa-wand-magic-sparkles" style="margin-top:2px"></i>
            <span><strong>Agencement automatique</strong> <span style="opacity:.7">(recommandé)</span><br>
            <span style="font-size:12px;opacity:.85">Routage propre et lisible via notre moteur : moins de croisements, pointes droites, losanges bien placés.</span></span>
          </button>
          <button id="_vsdx-classic" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.12);color:var(--text-muted);border-radius:11px;padding:13px 15px;font-size:13px;cursor:pointer;text-align:left;display:flex;gap:11px;align-items:flex-start;font-family:inherit;width:100%">
            <i class="fa-solid fa-clone" style="margin-top:2px"></i>
            <span><strong>Reconstruction classique</strong><br>
            <span style="font-size:12px;opacity:.8">Fidèle à la disposition Visio d'origine (pixel).</span></span>
          </button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    ov.querySelector('#_vsdx-auto').onclick    = () => { ov.remove(); resolve('auto'); };
    ov.querySelector('#_vsdx-classic').onclick = () => { ov.remove(); resolve('classic'); };
  });
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
  if (!window.JSZip) { showToast(_L('editor.toast.jszip_error')); return; }

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

  try {
    const result = await vsdxParse(file, setStatus, onOrphans, false);
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

    render();
    _alignImportedShapes(state.shapes, state.connections); // snap near-aligned shapes to H/V

    // Choix utilisateur : agencement auto (routage propre) OU reconstruction fidèle
    // à Visio. Sur une carto sans flèche, rien à agencer → classique d'office.
    document.getElementById('vsdx-dialog').classList.add('hidden');
    let mode = 'classic';
    if (state.connections.length) mode = await _askVsdxLayoutMode();

    if (mode === 'auto') {
      // Agencement automatique : remplace les tracés Visio bruts par un routage propre
      // (libavoid sur les grandes cartos, interne sinon) → moins de croisements,
      // pointes droites (padding), losanges bien branchés sur les pointes.
      const hint = connections.length > 60 ? 'Grande cartographie (' + connections.length + ' flèches) — quelques secondes…' : '';
      _showLayoutLoading(true, hint);
      await _yieldPaint();
      try { await _computeAutoLayout(); }
      catch (e) { console.warn('[VSDX] agencement auto ignoré :', e && e.message); }
      _showLayoutLoading(false);
    } else {
      // Classique (fidèle Visio) : les tracés exacts importés (customPath) deviennent
      // les points de passage RENDUS (userPts) au lieu d'un re-routage orthogonal.
      for (const c of state.connections)
        if (c.customPath && c.customPath.length >= 3) c.userPts = c.customPath.slice(1, -1);
    }
    render();
    history = [JSON.stringify(state)]; histIndex = 0; // baseline = carto reconstruite
    fitView(); updateProps();

    document.getElementById('vsdx-dialog').classList.add('hidden');
    setStatus('');
    renderBandsTbList();  // rafra\u00eechir le dropdown avec les bandes import\u00e9es
    const nCustom = connections.filter(c => c.customPath).length;
    console.log(`[VSDX] ${shapes.length} formes, ${connections.length} connexions, ${nCustom} chemins Visio exacts, ${groups.length} groupes`);
    showToast(_L('editor.toast.vsdx_done').replace('{shapes}', shapes.length).replace('{conns}', connections.length).replace('{bands}', bands.length));

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

function _confirmBandDelete(band, shapes) {
  return new Promise(resolve => {
    const list = shapes.map(s => `<span style="display:block;padding:1px 0">• ${s.label || 'Forme sans nom'}</span>`).join('');
    const ov = document.createElement('div');
    ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;z-index:9500;backdrop-filter:blur(2px)';
    ov.innerHTML = `
      <div style="background:#1a2030;border:1px solid rgba(255,255,255,0.09);border-radius:20px;padding:28px 32px;min-width:340px;max-width:460px;box-shadow:0 32px 80px rgba(0,0,0,0.6)">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <i class="fa-solid fa-triangle-exclamation" style="color:#f59e0b;font-size:18px"></i>
          <span style="font-size:15px;font-weight:700;color:#e2e8f0">Supprimer « ${band.label || 'Bande'} » ?</span>
        </div>
        <p style="font-size:12.5px;color:#94a3b8;margin:0 0 12px">Cette bande contient <strong style="color:#e2e8f0">${shapes.length} forme(s)</strong> qui seront également supprimées :</p>
        <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:10px 14px;max-height:150px;overflow-y:auto;margin-bottom:20px;font-size:11.5px;color:#cbd5e1;line-height:1.7">${list}</div>
        <div style="display:flex;gap:10px;justify-content:flex-end">
          <button id="_bdc-cancel" style="padding:8px 20px;border-radius:10px;border:1px solid rgba(255,255,255,0.12);background:transparent;color:#94a3b8;font-size:13px;cursor:pointer">Annuler</button>
          <button id="_bdc-confirm" style="padding:8px 20px;border-radius:10px;border:none;background:#ec4899;color:#fff;font-size:13px;font-weight:600;cursor:pointer">Supprimer quand même</button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    ov.querySelector('#_bdc-cancel').onclick  = () => { ov.remove(); resolve(false); };
    ov.querySelector('#_bdc-confirm').onclick = () => { ov.remove(); resolve(true); };
  });
}

// Post-import alignment: snap nearly-aligned connected shapes to exact H/V alignment
// and clear manual paths for straightened connections.
function _alignImportedShapes(shapes, conns) {
  const THRESH = 18; // px — shapes within this offset are considered "meant to align"

  // Accumulate alignment votes per shape
  const snapCxVotes = new Map(); // id → [cx values to average]
  const snapCyVotes = new Map();

  for (const c of conns) {
    const from = shapes.find(s => s.id === c.fromId);
    const to   = shapes.find(s => s.id === c.toId);
    if (!from || !to) continue;

    const fcx = from.x + from.w / 2, fcy = from.y + from.h / 2;
    const tcx = to.x   + to.w   / 2, tcy = to.y   + to.h   / 2;
    const dxAbs = Math.abs(fcx - tcx);
    const dyAbs = Math.abs(fcy - tcy);

    if (dxAbs <= THRESH && dxAbs < dyAbs) {
      // Nearly vertical: align X centers
      const mid = (fcx + tcx) / 2;
      for (const id of [from.id, to.id]) {
        if (!snapCxVotes.has(id)) snapCxVotes.set(id, []);
        snapCxVotes.get(id).push(mid);
      }
    } else if (dyAbs <= THRESH && dyAbs < dxAbs) {
      // Nearly horizontal: align Y centers
      const mid = (fcy + tcy) / 2;
      for (const id of [from.id, to.id]) {
        if (!snapCyVotes.has(id)) snapCyVotes.set(id, []);
        snapCyVotes.get(id).push(mid);
      }
    }
  }

  // Apply consensus snaps
  for (const s of shapes) {
    const vx = snapCxVotes.get(s.id);
    if (vx && vx.length > 0) {
      const avg = vx.reduce((a, b) => a + b, 0) / vx.length;
      s.x = Math.round(avg - s.w / 2);
    }
    const vy = snapCyVotes.get(s.id);
    if (vy && vy.length > 0) {
      const avg = vy.reduce((a, b) => a + b, 0) / vy.length;
      s.y = Math.round(avg - s.h / 2);
    }
  }

  // Clear manual paths for connections that are now perfectly aligned
  for (const c of conns) {
    const from = shapes.find(s => s.id === c.fromId);
    const to   = shapes.find(s => s.id === c.toId);
    if (!from || !to) continue;
    const dxAbs = Math.abs((from.x + from.w / 2) - (to.x + to.w / 2));
    const dyAbs = Math.abs((from.y + from.h / 2) - (to.y + to.h / 2));
    if (dxAbs <= 2 || dyAbs <= 2) {
      c.userPts    = null;
      c.customPath = null;
    }
  }
}

async function _deleteBand(idx) {
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
    const confirmed = await _confirmBandDelete(band, shapesInBand);
    if (!confirmed) return false;
    const ids = new Set(shapesInBand.map(s => s.id));
    state.shapes = state.shapes.filter(s => !ids.has(s.id));
    state.connections = state.connections.filter(c => !ids.has(c.fromId) && !ids.has(c.toId));
  }
  // Shift shapes below the deleted band upward to keep them in their bands
  for (const s of state.shapes) {
    if (!s.deleted && (s.y + s.h / 2) > bandYEnd) s.y -= band.height;
  }
  // Also shift manual arrow corners below the deleted band
  for (const conn of state.connections) {
    if (!conn.userPts) continue;
    for (const pt of conn.userPts) {
      if (pt.y > bandYEnd) pt.y -= band.height;
    }
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
    btn.addEventListener('click', async ev => {
      ev.stopPropagation();
      if (await _deleteBand(parseInt(ev.target.dataset.i))) {
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
  list.querySelectorAll('.band-delete').forEach(e => e.addEventListener('click', async ev => {
    if (await _deleteBand(parseInt(ev.target.dataset.i))) {
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
    showToast(_L('editor.toast.band_deleted'));
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
  const btn = document.getElementById('btn-left-panel-open');
  if (btn) btn.classList.toggle('active', open);
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
  const btn = document.getElementById('btn-right-panel-open');
  if (btn) btn.classList.toggle('active', open);
  if (open) {
    // Auto-pan so the selected shape (non-arrow) remains visible when panel opens
    if (selectedShapes.size > 0) {
      const PANEL_W = 244;
      const cRect = canvas.getBoundingClientRect();
      const visibleRight = cRect.width - PANEL_W - 16;
      for (const id of selectedShapes) {
        const s = state.shapes.find(s => s.id === id);
        if (!s) break;
        const shapeRightScreen = (s.x + s.w) * vpScale + vpX;
        if (shapeRightScreen > visibleRight) {
          vpX -= shapeRightScreen - visibleRight;
          applyViewport();
        }
        break; // Only adjust for the first selected shape
      }
    }
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

function _updatePanelBtn() { /* dock supprimé — no-op */ }

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
   CARTO DIAGNOSTICIAN — vérification de cohérence
   ══════════════════════════════════════════════════ */

function _showCheckPanel(issues) {
  document.getElementById('_carto-check-panel')?.remove();

  const iconByType = {
    isolated:  { icon: 'fa-circle-nodes',        color: '#f59e0b' },
    renvoi:    { icon: 'fa-circle-dot',           color: '#F4B8D0' },
    outofband: { icon: 'fa-up-right-from-square', color: '#6DD98A' },
    duplicate: { icon: 'fa-copy',                 color: '#4DB868' },
  };

  const panel = document.createElement('div');
  panel.id = '_carto-check-panel';
  panel.style.cssText = [
    'position:fixed;top:72px;right:12px;width:340px',
    'max-height:calc(100vh - 84px)',
    'background:#1A231D;border:1px solid rgba(77,184,104,0.22)',
    'border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.6)',
    'z-index:5000;display:flex;flex-direction:column;overflow:hidden',
  ].join(';');

  const hdr = `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid rgba(77,184,104,0.12);flex-shrink:0">
      <span style="font-size:13.5px;font-weight:700;color:#D6EDD9;display:flex;align-items:center;gap:8px">
        <i class="fa-solid fa-magnifying-glass-chart" style="color:#4DB868"></i> Diagnostic carto
      </span>
      <button id="_ccp-close" style="background:none;border:none;color:#567460;font-size:20px;cursor:pointer;line-height:1;padding:0 4px" title="Fermer">×</button>
    </div>`;

  let body;
  if (issues.length === 0) {
    body = `<div style="padding:28px 18px;text-align:center">
      <i class="fa-solid fa-circle-check" style="font-size:30px;color:#4DB868;display:block;margin-bottom:12px"></i>
      <div style="font-size:13px;font-weight:600;color:#D6EDD9">Aucun problème détecté</div>
      <div style="font-size:11.5px;color:#567460;margin-top:6px">La cartographie est cohérente</div>
    </div>`;
  } else {
    const rows = issues.map((issue, i) => {
      const ic = iconByType[issue.type] || { icon: 'fa-exclamation-circle', color: '#f59e0b' };
      return `<div style="display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid rgba(77,184,104,0.06)">
        <i class="fa-solid ${ic.icon}" style="color:${ic.color};font-size:13px;flex-shrink:0"></i>
        <span style="flex:1;font-size:11.5px;color:#D6EDD9;line-height:1.4">${issue.msg}</span>
        <button class="_ccp-goto" data-i="${i}" style="padding:4px 10px;border-radius:6px;border:1px solid rgba(77,184,104,0.22);background:transparent;color:#4DB868;font-size:11px;cursor:pointer;white-space:nowrap;flex-shrink:0">Voir →</button>
      </div>`;
    }).join('');

    body = `<div style="overflow-y:auto;flex:1">
      <div style="padding:10px 14px 4px;font-size:10.5px;color:#567460;font-weight:600;text-transform:uppercase;letter-spacing:0.05em">${issues.length} problème(s) trouvé(s)</div>
      ${rows}
    </div>`;
  }

  panel.innerHTML = hdr + body;
  document.body.appendChild(panel);

  panel.querySelector('#_ccp-close').onclick = () => panel.remove();

  panel.querySelectorAll('._ccp-goto').forEach(btn => {
    btn.addEventListener('click', () => {
      const issue = issues[parseInt(btn.dataset.i)];
      if (issue?.shape) focusOnShape(issue.shape);
    });
  });
}

function runCartoCheck() {
  if (state.shapes.length === 0) { showToast(_L('editor.toast.no_shapes_check')); return; }

  const issues = [];

  const connectedIds = new Set();
  state.connections.forEach(c => { connectedIds.add(c.fromId); connectedIds.add(c.toId); });

  const activityShapes = state.shapes.filter(s => s.type === 'process' || s.type === 'special');
  const activityLabelsLower = new Set(
    activityShapes.map(s => (s.label || '').trim().toLowerCase()).filter(Boolean)
  );

  // Band Y ranges (bands start at y = -200)
  const bandRanges = [];
  if (state.bands && state.bands.length > 0) {
    let bandY = -200;
    for (const band of state.bands) {
      if (!band.deleted) {
        bandRanges.push({ y: bandY, yEnd: bandY + band.height });
        bandY += band.height;
      }
    }
  }

  // 1. Activités sans connexion
  for (const s of activityShapes) {
    if (!connectedIds.has(s.id)) {
      issues.push({ type: 'isolated', shape: s, msg: `« ${s.label || 'Sans nom'} » n'a aucune connexion` });
    }
  }

  // 2. Renvois sans activité correspondante
  for (const s of state.shapes.filter(s => s.type === 'start-end')) {
    const label = (s.label || '').trim();
    if (!label || !activityLabelsLower.has(label.toLowerCase())) {
      issues.push({ type: 'renvoi', shape: s, msg: `Renvoi « ${label || 'Sans nom'} » sans activité correspondante` });
    }
  }

  // 3. Activités hors bande
  if (bandRanges.length > 0) {
    for (const s of activityShapes) {
      const midY = s.y + s.h / 2;
      if (!bandRanges.some(b => midY >= b.y && midY < b.yEnd)) {
        issues.push({ type: 'outofband', shape: s, msg: `« ${s.label || 'Sans nom'} » est hors de toute bande` });
      }
    }
  }

  // 4. Noms en double
  const labelGroups = {};
  for (const s of activityShapes) {
    const label = (s.label || '').trim();
    if (label) {
      if (!labelGroups[label]) labelGroups[label] = [];
      labelGroups[label].push(s);
    }
  }
  for (const [label, shapes] of Object.entries(labelGroups)) {
    if (shapes.length > 1) {
      shapes.forEach(s => issues.push({ type: 'duplicate', shape: s, msg: `Nom en doublon : « ${label} »` }));
    }
  }

  _showCheckPanel(issues);
}


/* ══════════════════════════════════════════════════
   ARCHITECTE — placement automatique des labels de flèches
   ══════════════════════════════════════════════════ */

function architectLabels(commit) {
  // 1. Label orientation MUST match the segment direction
  // 2. Label box must fit within segment with clearance from both ends
  // 3. Adaptive corner clearance — reduces for longer labels so they can still be placed
  // 4. Three passes: (a) matching direction from arrowhead, (b) all directions from arrowhead,
  //    (c) all segments longest-first with minimum clearance (last resort)

  const CORNER_BASE = 42;  // base clearance from label edge to segment endpoint
  const CORNER_MIN  = 12;  // minimum clearance (for very long labels)
  const SHAPE_M   = 14;
  const LABEL_GAP = 8;
  const CHAR_W    = 6.5;
  const LINE_H    = 13;
  const STEP_PX   = 6;

  const placed = [];
  const ARROW_CLEAR = 5; // marge min entre la boîte du label et une AUTRE flèche

  // Segments de toutes les flèches (pour qu'aucun label ne se pose sur une autre flèche)
  const allSegs = [];
  for (const cc of state.connections) {
    const pp = cc._computedOrthopts;
    if (!pp || pp.length < 2) continue;
    for (let i = 0; i < pp.length - 1; i++)
      allSegs.push({ connId: cc.id, ax: pp[i].x, ay: pp[i].y, bx: pp[i + 1].x, by: pp[i + 1].y });
  }

  function labelSize(c) {
    const lines = (c.label || '').split('\n');
    const lw = Math.max(24, Math.max(...lines.map(l => l.length)) * CHAR_W + 10);
    const lh = LINE_H * lines.length + (lines.length > 1 ? 4 : 0);
    return { lw, lh };
  }

  function hits(cx, cy, bw, bh, curId) {
    const hw = bw / 2, hh = bh / 2;
    for (const sh of state.shapes) {
      if (cx + hw > sh.x - SHAPE_M && cx - hw < sh.x + sh.w + SHAPE_M &&
          cy + hh > sh.y - SHAPE_M && cy - hh < sh.y + sh.h + SHAPE_M)
        return true;
    }
    for (const p of placed) {
      if (cx + hw > p.cx - p.hw - LABEL_GAP && cx - hw < p.cx + p.hw + LABEL_GAP &&
          cy + hh > p.cy - p.hh - LABEL_GAP && cy - hh < p.cy + p.hh + LABEL_GAP)
        return true;
    }
    // Ne pas chevaucher une AUTRE flèche : distance du bord de la boîte au segment
    for (const seg of allSegs) {
      if (seg.connId === curId) continue; // sa propre flèche → OK, le label s'y pose
      const abx = seg.bx - seg.ax, aby = seg.by - seg.ay;
      const len2 = abx * abx + aby * aby;
      if (len2 < 1) continue;
      const t = Math.max(0, Math.min(1, ((cx - seg.ax) * abx + (cy - seg.ay) * aby) / len2));
      const px = seg.ax + t * abx, py = seg.ay + t * aby;
      const bdx = Math.max(0, Math.abs(cx - px) - hw);
      const bdy = Math.max(0, Math.abs(cy - py) - hh);
      if (Math.hypot(bdx, bdy) < ARROW_CLEAR) return true;
    }
    return false;
  }

  const TIP_GAP = 12;    // espace lisible entre la pointe/source et le bord du label
  const CORNER_M = 16;   // marge par rapport a un coude (angle)

  // Essaie de poser le label sur le segment [pa,pb] au plus pres de pb (cote pointe).
  // marginB = marge cote pb (pointe/coude), marginA = marge cote pa (source/coude).
  function tryOnSegment(c, pa, pb, lw, lh, marginA, marginB) {
    const dx = pb.x - pa.x, dy = pb.y - pa.y, len = Math.hypot(dx, dy);
    if (len < 1) return null;
    const isH = Math.abs(dy) < Math.abs(dx);
    const bw = isH ? lw : lh, bh = isH ? lh : lw;
    const alongHalf = lw / 2;
    const tMax = 1 - (alongHalf + marginB) / len;
    const tMin = (alongHalf + marginA) / len;
    if (tMax < tMin) return null;              // segment trop court pour ce label
    for (let t = tMax; t >= tMin - 1e-6; t -= STEP_PX / len) {
      const cx = pa.x + dx * t, cy = pa.y + dy * t;
      if (!hits(cx, cy, bw, bh, c.id)) return { x: cx, y: cy, a: isH ? 0 : -90, hw: bw / 2, hh: bh / 2 };
    }
    return null;
  }

  for (const c of state.connections) {
    if (!(c.label || '').trim()) continue;
    const pts = c._computedOrthopts;
    if (!pts || pts.length < 2) { delete c.labelOffset; continue; }
    const { lw, lh } = labelSize(c);
    const last = pts.length - 2; // dernier segment (cote pointe)
    let res = null;

    // Segment le plus proche de la POINTE d'abord : sur CHAQUE segment on tente les
    // marges de coude pleines PUIS des marges minimales, AVANT de reculer vers la
    // source. Ainsi le label reste au plus près de la pointe tout en respectant ses
    // restrictions (jamais sur une forme, une autre flèche ou un autre label). L'ancien
    // ordre (tous les segments en strict, puis tous en relâché) posait le label loin de
    // la pointe sur un segment bien dégagé plutôt que près d'elle avec une marge réduite.
    for (let si = last; si >= 0 && !res; si--) {
      const marginB = (si === last) ? TIP_GAP : CORNER_M;   // pb = pointe ou coude
      const marginA = (si === 0)    ? TIP_GAP : CORNER_M;   // pa = source ou coude
      res = tryOnSegment(c, pts[si], pts[si + 1], lw, lh, marginA, marginB)
         || tryOnSegment(c, pts[si], pts[si + 1], lw, lh, 6, 6);
    }

    if (res) {
      c.labelOffset = { x: res.x, y: res.y, a: res.a };
      placed.push({ cx: res.x, cy: res.y, hw: res.hw, hh: res.hh });
    } else {
      delete c.labelOffset;
    }
  }

  if (commit !== false) { snapshot(); render(); }
}

function _labelOnSeg(conn, seg) {
  if (!(conn.label || '').trim() || !conn.labelOffset) return false;
  const { pa, pb } = seg;
  const { x, y } = conn.labelOffset;
  return x >= Math.min(pa.x, pb.x) - 35 && x <= Math.max(pa.x, pb.x) + 35 &&
         y >= Math.min(pa.y, pb.y) - 35 && y <= Math.max(pa.y, pb.y) + 35;
}

// Choisit la direction du détour (-1 = haut/gauche, +1 = bas/droite) en fonction
// de l'espace disponible (moins de formes = meilleur côté).
function _chooseDetourDir(isH, segPos, os, oe, offset) {
  const PAD = 8;
  function countHits(sign) {
    let n = 0;
    const d = sign * offset;
    if (isH) {
      const yMin = Math.min(segPos, segPos + d) - PAD;
      const yMax = Math.max(segPos, segPos + d) + PAD;
      for (const s of state.shapes) {
        if (s.x < oe + PAD && s.x + s.w > os - PAD && s.y < yMax && s.y + s.h > yMin) n++;
      }
    } else {
      const xMin = Math.min(segPos, segPos + d) - PAD;
      const xMax = Math.max(segPos, segPos + d) + PAD;
      for (const s of state.shapes) {
        if (s.y < oe + PAD && s.y + s.h > os - PAD && s.x < xMax && s.x + s.w > xMin) n++;
      }
    }
    return n;
  }
  return countHits(-1) <= countHits(+1) ? -1 : +1;
}

function architectArrows(silent) {
  const CLOSE       = 9;   // distance perpendiculaire max pour considérer deux segments superposés
  const MIN_OVERLAP = 20;  // longueur minimale de chevauchement à corriger (px)
  const GAP         = 14;  // marge avant/après la zone de détour
  const OFFSET      = 30;  // profondeur du détour perpendiculaire (px)

  // Réinitialiser les détours précédents (appel frais = résultat reproductible)
  for (const c of state.connections) {
    if (c._archDetoured) { delete c.userPts; delete c._archDetoured; }
  }
  // Re-render pour obtenir des _computedOrthopts propres AVANT l'analyse
  render();

  const allSegs = [];
  for (const c of state.connections) {
    const pts = c._computedOrthopts;
    if (!pts || pts.length < 2) continue;
    for (let i = 0; i < pts.length - 1; i++) {
      const pa = pts[i], pb = pts[i + 1];
      const len = Math.hypot(pb.x - pa.x, pb.y - pa.y);
      if (len < 1) continue;
      const isH = Math.abs(pb.y - pa.y) < Math.abs(pb.x - pa.x);
      allSegs.push({ connId: c.id, segIdx: i, pa, pb, len, isH, fullPts: pts });
    }
  }

  const toFix = [];
  const fixed = new Set();

  for (let i = 0; i < allSegs.length; i++) {
    for (let j = i + 1; j < allSegs.length; j++) {
      const sa = allSegs[i], sb = allSegs[j];
      if (sa.connId === sb.connId) continue;
      if (sa.isH !== sb.isH) continue;

      let oStart, oEnd;
      if (sa.isH) {
        if (Math.abs(sa.pa.y - sb.pa.y) > CLOSE) continue;
        const aMin = Math.min(sa.pa.x, sa.pb.x), aMax = Math.max(sa.pa.x, sa.pb.x);
        const bMin = Math.min(sb.pa.x, sb.pb.x), bMax = Math.max(sb.pa.x, sb.pb.x);
        oStart = Math.max(aMin, bMin); oEnd = Math.min(aMax, bMax);
        if (oEnd - oStart < MIN_OVERLAP) continue;
      } else {
        if (Math.abs(sa.pa.x - sb.pa.x) > CLOSE) continue;
        const aMin = Math.min(sa.pa.y, sa.pb.y), aMax = Math.max(sa.pa.y, sa.pb.y);
        const bMin = Math.min(sb.pa.y, sb.pb.y), bMax = Math.max(sb.pa.y, sb.pb.y);
        oStart = Math.max(aMin, bMin); oEnd = Math.min(aMax, bMax);
        if (oEnd - oStart < MIN_OVERLAP) continue;
      }

      if (fixed.has(sa.connId) && fixed.has(sb.connId)) continue;
      let chosen, chosenSeg;
      if (fixed.has(sa.connId)) {
        chosen = state.connections.find(c => c.id === sb.connId); chosenSeg = sb;
      } else if (fixed.has(sb.connId)) {
        chosen = state.connections.find(c => c.id === sa.connId); chosenSeg = sa;
      } else {
        const connA = state.connections.find(c => c.id === sa.connId);
        const connB = state.connections.find(c => c.id === sb.connId);
        if (!connA || !connB) continue;
        const hasA = _labelOnSeg(connA, sa), hasB = _labelOnSeg(connB, sb);
        if (hasA && !hasB) { chosen = connB; chosenSeg = sb; }
        else if (hasB && !hasA) { chosen = connA; chosenSeg = sa; }
        else {
          const la = (connA.label || '').length, lb = (connB.label || '').length;
          if (la <= lb) { chosen = connA; chosenSeg = sa; } else { chosen = connB; chosenSeg = sb; }
        }
      }
      if (!chosen) continue;
      fixed.add(chosen.id);
      toFix.push({ conn: chosen, seg: chosenSeg, oStart, oEnd });
    }
  }

  if (toFix.length === 0) {
    if (!silent) showToast(_L('editor.toast.no_arrow_overlap') || 'Aucune superposition détectée');
    return 0;
  }

  for (const { conn, seg, oStart, oEnd } of toFix) {
    const { segIdx, fullPts, isH } = seg;
    const pa = fullPts[segIdx], pb = fullPts[segIdx + 1];

    // Coordonnée du segment à dévier (Y pour horizontal, X pour vertical)
    // CRITIQUE : utiliser la position réelle du segment choisi, pas une moyenne
    const segPos = isH ? pa.y : pa.x;

    // Délimiter la zone de détour à l'intérieur du segment
    const segMin = isH ? Math.min(pa.x, pb.x) : Math.min(pa.y, pb.y);
    const segMax = isH ? Math.max(pa.x, pb.x) : Math.max(pa.y, pb.y);
    const os = Math.max(segMin + 6, oStart - GAP);
    const oe = Math.min(segMax - 6, oEnd + GAP);
    if (os >= oe) continue;

    // Choisir le meilleur côté pour le détour (éviter les formes)
    const sign = _chooseDetourDir(isH, segPos, os, oe, OFFSET);

    // Construire le chemin complet avec 4 points de détour insérés
    const newPts = [];
    for (let k = 0; k < fullPts.length; k++) {
      newPts.push({ x: fullPts[k].x, y: fullPts[k].y });
      if (k === segIdx) {
        if (isH) {
          newPts.push({ x: os, y: segPos });
          newPts.push({ x: os, y: segPos + sign * OFFSET });
          newPts.push({ x: oe, y: segPos + sign * OFFSET });
          newPts.push({ x: oe, y: segPos });
        } else {
          newPts.push({ x: segPos,                y: os });
          newPts.push({ x: segPos + sign * OFFSET, y: os });
          newPts.push({ x: segPos + sign * OFFSET, y: oe });
          newPts.push({ x: segPos,                y: oe });
        }
      }
    }
    conn.userPts = newPts.slice(1, -1);
    conn._archDetoured = true; // marqueur pour réinitialisation au prochain appel

    // Déplacer le label au milieu du segment de détour
    if ((conn.label || '').trim()) {
      if (isH)
        conn.labelOffset = { x: (os + oe) / 2, y: segPos + sign * OFFSET };
      else
        conn.labelOffset = { x: segPos + sign * OFFSET, y: (os + oe) / 2 };
    }
  }

  if (!silent) { showToast(toFix.length + ' ' + (_L('editor.toast.arrows_fixed') || 'flèche(s) décalée(s)')); snapshot(); render(); }
  return toFix.length;
}

/* ══════════════════════════════════════════════════
   AGENCEMENT AUTOMATIQUE — le bouton « tout ranger »
   Enchaîne : ports optimaux → routage orthogonal contournant les formes →
   séparation des flèches parallèles → placement des labels près de la pointe.
   Un seul appel = un diagramme « façon Visio » sans réglage manuel.
   ══════════════════════════════════════════════════ */
let _autoLayoutBusy = false;

// Cœur de l'agencement automatique : ré-assigne ports + tracés de TOUTES les
// connexions et recentre les losanges, EN PLACE dans `state`. Aucune UI/preview ici
// → réutilisable par le bouton « Agencement auto » (avec preview avant/après) ET par
// l'import VSDX (application directe lors de la reconstruction de la carto).
async function _computeAutoLayout(opts) {
  opts = opts || {};
  const declutter = opts.declutter !== false; // aération activée par défaut
  const nConn = state.connections.length;

  // Aère les zones trop serrées (formes qui se chevauchent) : « dénoue » les endroits
  // complexes et laisse respirer flèches + labels. Ne touche que ce qui est trop serré
  // → l'essence de la carto est préservée. Désactivable via opts.declutter=false.
  if (declutter) _declutterShapes();

  // Recentre ensuite les losanges de décision sur leurs voisins connectés → les
  // flèches les toucheront pile sur les pointes (fini les losanges « décalés »).
  // Fait avant de figer nodesById pour que le routage parte des bonnes positions.
  _alignDecisionsToNeighbors();

  {
    const nodesById = {};
    for (const s of state.shapes) nodesById[s.id] = { x: s.x, y: s.y, w: s.w, h: s.h, type: s.type };
    if (state.groups) for (const g of state.groups) {
      const b = getGroupBounds(g);
      if (b) nodesById[g.id] = { x: b.x, y: b.y, w: b.w, h: b.h, type: 'group' };
    }

    // repartir propre (on repart des tracés vierges : userPts + chemins Visio bruts)
    for (const c of state.connections) { c.userPts = null; c.customPath = null; c.bendOffset = null; delete c._archDetoured; delete c.labelOffset; }

    // 1) Choix du moteur selon la TAILLE (mesuré en navigateur sur cartos réalistes) :
    //   • < LIB_MIN flèches  → routeur INTERNE : instantané et déjà excellent (≈0
    //     croisement) sur les petites cartos ; inutile de payer libavoid.
    //   • LIB_MIN..LIB_MAX   → libavoid : routage GLOBAL + nudging → bien moins de
    //     croisements que l'interne dès que ça devient dense (ex. 165 flèches :
    //     ~17 croisements vs ~76 pour l'interne), et rapide (<1 s à 165, ~4 s à 230).
    //   • > LIB_MAX          → routeur interne : libavoid devient trop lent sur les
    //     cartos pathologiques ; l'interne reste instantané.
    // Repli automatique sur l'interne si le worker échoue ou dépasse le timeout.
    const LIB_MIN = 40, LIB_MAX = 260;
    let usedLib = false;
    if (window.OPTIQCARTO_USE_LIBAVOID && window.OPTIQCARTO_LIBAVOID_WORKER && nConn >= LIB_MIN && nConn <= LIB_MAX) {
      try {
        const plain = state.connections.map(c => ({ id: c.id, fromId: c.fromId, toId: c.toId }));
        // Timeout adaptatif : généreux pour laisser finir les grandes cartos réelles
        // (rapides), borné pour couper les cas denses pathologiques → repli interne.
        const timeoutMs = Math.min(20000, 6000 + nConn * 80);
        const results = await _routeViaWorker(nodesById, plain, timeoutMs);
        if (results && results.length) {
          const byId = {}; for (const r of results) byId[r.connId] = r;
          for (const c of state.connections) {
            const r = byId[c.id]; if (!r) continue;
            c.fromPortDir = r.fromDir; c.fromPortT = r.fromT;
            c.toPortDir = r.toDir; c.toPortT = r.toT; c.userPts = r.userPts;
          }
          usedLib = true;
        }
      } catch (e) { console.warn('[OptiqCarto] libavoid worker indisponible/timeout, routeur interne :', e && e.message); usedLib = false; }
    }

    // 2) Routeur orthogonal interne (rapide, propre) : grosses cartos + repli.
    if (!usedLib) {
      const ports = autoAssignPorts(nodesById, state.connections);
      const pByConn = {}; for (const p of ports) if (p) pByConn[p.connId] = p;
      for (const c of state.connections) {
        const p = pByConn[c.id]; if (!p) continue;
        c.fromPortDir = p.fromDir; c.fromPortT = p.fromT; c.toPortDir = p.toDir; c.toPortT = p.toT;
      }
      render();
      let _routed = 0;
      for (const c of state.connections) {
        const pts = c._computedOrthopts;
        if (!pts || pts.length < 2) continue;
        const fp = { x: pts[0].x, y: pts[0].y, dir: c.fromPortDir || 'right' };
        const last = pts[pts.length - 1];
        const tp = { x: last.x, y: last.y, dir: c.toPortDir || 'left' };
        const skipMembers = new Set();
        if (state.groups) for (const g of state.groups) {
          if (g.id === c.fromId || g.id === c.toId) (g.shapeIds || []).forEach(id => skipMembers.add(id));
        }
        const obstacles = [];
        for (const s of state.shapes) {
          if (s.id === c.fromId || s.id === c.toId) continue;
          if (skipMembers.has(s.id)) continue;
          if (s.type === 'decision') obstacles.push({ x: s.x + s.w * 0.22, y: s.y + s.h * 0.22, w: s.w * 0.56, h: s.h * 0.56 });
          else obstacles.push({ x: s.x, y: s.y, w: s.w, h: s.h });
        }
        let route = null;
        try { route = routeOrthogonalAStar(fp, tp, obstacles); } catch (_) { route = null; }
        // Repli : grille plus fine (moins de quantification) pour les rares flèches
        // que la grille grossie n'a pas su router.
        if (!route) { try { route = routeOrthogonalAStar(fp, tp, obstacles, { nodeCap: 90000 }); } catch (_) { route = null; } }
        // Filet de sécurité : si le tracé frôle encore une forme (stub ou segment
        // résiduel), on le nettoie par détour ; sinon on garde le tracé A* tel quel.
        if (route && route.length >= 2 && pathCrossesObstacles(route, obstacles)) {
          try { route = simplifyPath(avoidShapes(route, state.shapes, c.fromId, c.toId)); } catch (_) {}
        }
        if (route && route.length >= 2) { const mids = route.slice(1, -1).map(p => ({ x: p.x, y: p.y })); c.userPts = mids.length ? mids : null; }
        // Rendre la main régulièrement : l'UI et le spinner restent vivants même
        // sur une très grosse carto (le calcul reste sur le thread principal).
        if ((++_routed % 40) === 0) await _yieldPaint();
      }
      render();
      _separateLanes();
    }

    render();
    _straightenTips(); // pointes toujours droites (jamais un angle dans la tête)
    render();
    // NB : on ne déplace PAS les losanges après routage. Les flèches se branchent déjà
    // pile sur leurs pointes (spreadPort renvoie les sommets, et le worker libavoid y
    // accroche exactement, une pointe = une flèche). Bouger un losange après coup
    // désaxe son dernier segment (userPts figés) → « ne finit plus sur la flèche ».
    // Le recentrage se fait AVANT routage via _alignDecisionsToNeighbors().
    architectLabels(false); // labels près de la pointe
    render();
  }
}

// Bouton « Agencement auto » : calcule l'agencement puis propose un aperçu
// avant/après (rien n'est appliqué tant que l'utilisateur n'a pas confirmé).
async function autoLayoutArrows() {
  if (window.OPTIQCARTO_READONLY || _autoLayoutBusy) return;
  if (!state.connections || state.connections.length === 0) {
    showToast(_L('editor.toast.no_arrows') || 'Aucune flèche à agencer');
    return;
  }
  _autoLayoutBusy = true;

  // Sauvegarde de l'état AVANT + visuel avant (rien n'est appliqué sans confirmation)
  const beforeJSON = JSON.stringify(state);
  const beforeSVG = _snapshotCartoSVG();

  const nConn = state.connections.length;
  // Grosse carto : le calcul dure quelques secondes → on prévient l'utilisateur
  // (jamais figé grâce au worker + au chrono).
  const bigHint = nConn > 60 ? 'Grande cartographie (' + nConn + ' flèches) — quelques secondes…' : '';
  _showLayoutLoading(true, bigHint);
  await _yieldPaint(); // laisse le navigateur peindre le spinner avant de calculer

  // Recalcule l'agencement depuis l'état AVANT, avec ou sans aération. Renvoie le SVG
  // « après » et mémorise le JSON à appliquer. Réutilisé par le toggle de la modale.
  let declutter = true, afterJSON = null;
  async function computeAfter() {
    state = JSON.parse(beforeJSON); _restoreCollapsedPiles();
    await _computeAutoLayout({ declutter });
    afterJSON = JSON.stringify(state);
    const svg = _snapshotCartoSVG();
    state = JSON.parse(beforeJSON); _restoreCollapsedPiles(); render();
    return svg;
  }

  try {
    const afterSVG = await computeAfter();
    _showLayoutLoading(false);
    _showBeforeAfterModal(beforeSVG, afterSVG, () => {
      state = JSON.parse(afterJSON); _restoreCollapsedPiles(); clearSelection(); render(); snapshot();
      showToast((_L('editor.toast.arrows_arranged') || 'Flèches agencées automatiquement'));
    }, {
      declutter,
      onToggle: async (val) => { declutter = val; return await computeAfter(); },
    });
  } catch (err) {
    console.error('[OptiqCarto] agencement auto :', err);
    state = JSON.parse(beforeJSON); _restoreCollapsedPiles(); render();
    _showLayoutLoading(false);
    showToast('Erreur pendant l\'agencement');
  } finally {
    _autoLayoutBusy = false;
  }
}

/* ── Client du Web Worker libavoid (routage hors thread principal) ── */
let _lvWorker = null, _lvReqId = 0;
const _lvPending = {};
function _getLvWorker() {
  if (_lvWorker) return _lvWorker;
  const url = window.OPTIQCARTO_LIBAVOID_WORKER;
  if (!url || typeof Worker === 'undefined') return null;
  try {
    const w = new Worker(url, { type: 'module' });
    w.onmessage = (e) => {
      const d = e.data || {}; const p = _lvPending[d.id];
      if (!p) return; delete _lvPending[d.id];
      if (d.ok) p.resolve(d.results); else p.reject(new Error(d.error || 'worker'));
    };
    // Échec de chargement du worker (404 .mjs, MIME, CSP, WASM bloqué…) : on rejette
    // TOUTES les requêtes en attente immédiatement → repli instantané sur le routeur
    // interne (sinon on attendrait le timeout complet). Le worker cassé est jeté.
    w.onerror = (ev) => {
      console.warn('[OptiqCarto] worker error', ev && ev.message);
      for (const k of Object.keys(_lvPending)) {
        const p = _lvPending[k]; delete _lvPending[k];
        try { p.reject(new Error('worker onerror')); } catch (_) {}
      }
      try { w.terminate(); } catch (_) {}
      if (_lvWorker === w) _lvWorker = null;
    };
    _lvWorker = w;
  } catch (e) { console.warn('[OptiqCarto] worker indispo', e && e.message); _lvWorker = null; }
  return _lvWorker;
}
function _routeViaWorker(nodesById, connections, timeoutMs) {
  return new Promise((resolve, reject) => {
    const w = _getLvWorker();
    if (!w) { reject(new Error('no worker')); return; }
    const id = ++_lvReqId;
    const timer = setTimeout(() => {
      delete _lvPending[id];
      try { w.terminate(); } catch (_) {}
      _lvWorker = null; // recréé au prochain appel
      reject(new Error('timeout'));
    }, timeoutMs || 25000);
    _lvPending[id] = {
      resolve: (r) => { clearTimeout(timer); resolve(r); },
      reject: (e) => { clearTimeout(timer); reject(e); },
    };
    w.postMessage({ id, nodesById, connections });
  });
}

// Laisse le navigateur peindre (2 frames) avant un calcul lourd
function _yieldPaint() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }

// Overlay de chargement plein écran
let _layoutLoadingTimer = null;
function _showLayoutLoading(show, hint) {
  let el = document.getElementById('carto-layout-loading');
  if (show) {
    if (!el) {
      el = document.createElement('div');
      el.id = 'carto-layout-loading';
      el.innerHTML = '<div class="cll-box"><div class="cll-spin"></div>' +
        '<div class="cll-txt">Agencement des flèches…</div>' +
        '<div class="cll-sub"></div><div class="cll-time"></div></div>';
      document.body.appendChild(el);
    }
    const sub = el.querySelector('.cll-sub');
    if (sub) sub.textContent = hint || '';
    el.style.display = 'flex';
    // Compteur de temps écoulé : sur une grosse carto le calcul dure quelques
    // secondes — le chrono montre que ça travaille (jamais figé).
    const t0 = performance.now();
    const timeEl = el.querySelector('.cll-time');
    if (_layoutLoadingTimer) clearInterval(_layoutLoadingTimer);
    const tick = () => { if (timeEl) timeEl.textContent = ((performance.now() - t0) / 1000).toFixed(1) + ' s'; };
    tick();
    _layoutLoadingTimer = setInterval(tick, 100);
  } else if (el) {
    el.style.display = 'none';
    if (_layoutLoadingTimer) { clearInterval(_layoutLoadingTimer); _layoutLoadingTimer = null; }
  }
}

// Bornes du contenu (formes + tracés) pour cadrer un aperçu
function _cartoContentBounds() {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of state.shapes) { minX = Math.min(minX, s.x); minY = Math.min(minY, s.y); maxX = Math.max(maxX, s.x + s.w); maxY = Math.max(maxY, s.y + s.h); }
  for (const c of state.connections) { const p = c._computedOrthopts; if (!p) continue; for (const pt of p) { minX = Math.min(minX, pt.x); minY = Math.min(minY, pt.y); maxX = Math.max(maxX, pt.x); maxY = Math.max(maxY, pt.y); } }
  if (!isFinite(minX)) return null;
  const pad = 45;
  return { x: minX - pad, y: minY - pad, w: (maxX - minX) + 2 * pad, h: (maxY - minY) + 2 * pad };
}

// Snapshot SVG autonome de la carto (pour l'aperçu avant/après) : clone du canvas
// sans le transform du viewport, cadré sur le contenu, sans poignées de sélection.
function _snapshotCartoSVG() {
  const b = _cartoContentBounds();
  const clone = canvas.cloneNode(true);
  clone.removeAttribute('id');
  const rg = clone.querySelector('#root-group'); if (rg) rg.removeAttribute('transform');
  ['g-handles', 'g-ui', 'g-overlay', 'g-lasso'].forEach(id => { const el = clone.querySelector('#' + id); if (el) el.innerHTML = ''; });
  if (b) clone.setAttribute('viewBox', `${b.x} ${b.y} ${b.w} ${b.h}`);
  clone.removeAttribute('width'); clone.removeAttribute('height');
  clone.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  clone.style.width = '100%'; clone.style.height = '100%'; clone.style.display = 'block'; clone.style.background = '#f6f8fb';
  return clone;
}

// Modale de comparaison avant / après avec Appliquer / Annuler
function _showBeforeAfterModal(beforeSVG, afterSVG, onApply, opts) {
  opts = opts || {};
  document.getElementById('carto-ba-modal')?.remove();
  const m = document.createElement('div');
  m.id = 'carto-ba-modal';
  // Toggle « aérer » : donne la possibilité de laisser l'agencement DÉPLACER un peu
  // les formes (dénouer/espacer) ou de garder les positions d'origine.
  const toggleHtml = opts.onToggle ?
    ('<label class="ba-toggle" style="display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--text-muted);cursor:pointer;margin-right:auto">' +
       '<input type="checkbox" id="ba-declutter" ' + (opts.declutter ? 'checked' : '') + ' style="width:15px;height:15px;cursor:pointer">' +
       'Aérer les formes trop serrées (déplacer un peu pour dénouer)</label>') : '';
  m.innerHTML =
    '<div class="ba-card">' +
      '<div class="ba-head"><i class="fa-solid fa-wand-magic-sparkles"></i> Comparer l\'agencement</div>' +
      '<div class="ba-panels">' +
        '<div class="ba-col"><div class="ba-tag ba-tag--before">Avant</div><div class="ba-view" id="ba-before"></div></div>' +
        '<div class="ba-col"><div class="ba-tag ba-tag--after">Après</div><div class="ba-view" id="ba-after"></div></div>' +
      '</div>' +
      '<div class="ba-actions">' +
        toggleHtml +
        '<button class="ba-btn ba-btn--cancel" id="ba-cancel">Annuler</button>' +
        '<button class="ba-btn ba-btn--apply" id="ba-apply"><i class="fa-solid fa-check"></i> Appliquer</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(m);
  m.querySelector('#ba-before').appendChild(beforeSVG);
  m.querySelector('#ba-after').appendChild(afterSVG);
  const close = () => m.remove();
  m.querySelector('#ba-cancel').addEventListener('click', close);
  m.querySelector('#ba-apply').addEventListener('click', () => { close(); if (onApply) onApply(); });
  const declEl = m.querySelector('#ba-declutter');
  if (declEl && opts.onToggle) {
    let baBusy = false;
    declEl.addEventListener('change', async () => {
      if (baBusy) { declEl.checked = !declEl.checked; return; }
      baBusy = true; declEl.disabled = true;
      const view = m.querySelector('#ba-after');
      view.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:13px">Recalcul…</div>';
      try { const newSVG = await opts.onToggle(declEl.checked); view.innerHTML = ''; view.appendChild(newSVG); }
      catch (_) {}
      baBusy = false; declEl.disabled = false;
    });
  }
  m.addEventListener('mousedown', (e) => { if (e.target === m) close(); });
  document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); } });
}

// Garantit que CHAQUE flèche rentre (et sort) tout droit sur au moins MIN_TIP px
// (la tête de flèche fait ~21 px → jamais posée sur un virage). Corrige les stubs
// raccourcis par la séparation en voies. Ne bouge que des points intérieurs.
function _straightenTips() {
  const MIN_TIP = 26;
  for (const c of state.connections) {
    const pts = c._computedOrthopts;
    if (!pts || pts.length < 4) continue;
    let np = _straightApproach(pts, c.fromPortDir, MIN_TIP, true);
    np = _straightApproach(np, c.toPortDir, MIN_TIP, false);
    if (np !== pts) c.userPts = np.slice(1, -1).map(p => ({ x: p.x, y: p.y }));
  }
}

// Sépare les flèches parallèles en VOIES nettes (au lieu de bosses) : décale les
// segments intérieurs qui se superposent dans un même couloir, chacun sur sa
// propre ligne espacée. Ne touche que les segments intérieurs (jamais ceux
// collés à un port) → le tracé reste orthogonal automatiquement (seuls les coins
// partagés bougent). Vérifie qu'aucune voie ne traverse une forme.
function _separateLanes() {
  const GAP = 16, CLOSE = 11, MIN_OVER = 26, SAFE_M = 6;

  // Rectangles obstacles (petite marge : les voies peuvent longer une forme)
  const rects = state.shapes
    .filter(s => s.type !== 'decision')
    .map(s => ({ x: s.x - SAFE_M, y: s.y - SAFE_M, w: s.w + 2 * SAFE_M, h: s.h + 2 * SAFE_M }));
  const crossesObstacle = (isH, coord, lo, hi) => {
    const ax = isH ? lo : coord, ay = isH ? coord : lo;
    const bx = isH ? hi : coord, by = isH ? coord : hi;
    for (const r of rects) if (_segCrossesRect(ax, ay, bx, by, r)) return true;
    return false;
  };

  // Collecte des segments intérieurs (les deux extrémités sont des userPts)
  const segs = [];
  for (const c of state.connections) {
    const pts = c._computedOrthopts;
    if (!c.userPts || !pts || pts.length < 4) continue;
    for (let i = 1; i <= pts.length - 3; i++) {
      const a = pts[i], b = pts[i + 1];
      const isH = Math.abs(a.y - b.y) < 1.5, isV = Math.abs(a.x - b.x) < 1.5;
      if (!isH && !isV) continue;
      const len = isH ? Math.abs(b.x - a.x) : Math.abs(b.y - a.y);
      if (len < MIN_OVER) continue;
      segs.push({
        c, isH, coord: isH ? a.y : a.x,
        lo: isH ? Math.min(a.x, b.x) : Math.min(a.y, b.y),
        hi: isH ? Math.max(a.x, b.x) : Math.max(a.y, b.y),
        uA: i - 1, uB: i,
      });
    }
  }

  // Regroupement en faisceaux (même axe, coord proche, plages qui se recouvrent)
  const used = new Array(segs.length).fill(false);
  for (let i = 0; i < segs.length; i++) {
    if (used[i]) continue;
    const bundle = [segs[i]]; used[i] = true;
    for (let j = i + 1; j < segs.length; j++) {
      if (used[j]) continue;
      const t = segs[j];
      if (t.isH !== segs[i].isH || Math.abs(t.coord - segs[i].coord) > CLOSE) continue;
      if (bundle.some(m => Math.min(m.hi, t.hi) - Math.max(m.lo, t.lo) > MIN_OVER)) { bundle.push(t); used[j] = true; }
    }
    if (new Set(bundle.map(b => b.c.id)).size < 2) continue; // besoin de ≥2 flèches distinctes

    const base = bundle.reduce((s, b) => s + b.coord, 0) / bundle.length;
    bundle.sort((a, b) => (a.coord - b.coord) || (a.c.id - b.c.id));
    const n = bundle.length;
    bundle.forEach((seg, rank) => {
      const newCoord = base + (rank - (n - 1) / 2) * GAP;
      if (Math.abs(newCoord - seg.coord) < 0.5) return;
      if (crossesObstacle(seg.isH, newCoord, seg.lo, seg.hi)) return; // sécurité : pas à travers une forme
      const up = seg.c.userPts;
      if (seg.isH) { if (up[seg.uA]) up[seg.uA].y = newCoord; if (up[seg.uB]) up[seg.uB].y = newCoord; }
      else        { if (up[seg.uA]) up[seg.uA].x = newCoord; if (up[seg.uB]) up[seg.uB].x = newCoord; }
    });
  }

  // Nettoyage : fusionne les points devenus colinéaires après décalage
  for (const c of state.connections) {
    if (!c.userPts || !c._computedOrthopts) continue;
    const pts = c._computedOrthopts;
    const full = simplifyPath([pts[0], ...c.userPts, pts[pts.length - 1]]);
    c.userPts = full.length > 2 ? full.slice(1, -1) : null;
  }
}


/* ══════════════════════════════════════════════════
   CRÉATION PLURIELLE — ajout de N formes par bande
   ══════════════════════════════════════════════════ */

let _bulkPanelHovered = false;

function _showBulkPanel(shapeType, shapeSubtype, wrap, anchorBtn) {
  document.getElementById('_bulk-side-panel')?.remove();
  const dropdown = wrap.querySelector('.shape-sub-dropdown');
  if (!dropdown) return;
  const dropRect = dropdown.getBoundingClientRect();
  const btnRect  = anchorBtn.getBoundingClientRect();

  const previewClassMap = { process: 'normal', special: 'special', 'start-end': 'renvoi', decision: 'decision' };
  const subtypeClass    = shapeSubtype === 'external' ? 'external' : shapeSubtype === 'extco' ? 'extco' : (previewClassMap[shapeType] || 'normal');
  const labelMap = { process: 'Activité', special: 'Sous-activité', 'start-end': 'Renvoi', decision: 'Décision' };
  const shapeName = (shapeSubtype === 'external' ? 'Activité externe' : shapeSubtype === 'extco' ? 'Ext. entreprise' : labelMap[shapeType]) || shapeType;

  const panel = document.createElement('div');
  panel.id = '_bulk-side-panel';
  // Align top with the hovered button, flush against the dropdown (no gap)
  panel.style.cssText = [
    `position:fixed;top:${btnRect.top}px;left:${dropRect.right + 1}px`,
    'background:#1A231D;border:1px solid rgba(77,184,104,0.22)',
    'border-radius:14px;padding:6px;min-width:160px',
    'box-shadow:0 8px 24px rgba(0,0,0,0.5);z-index:500',
  ].join(';');

  panel.innerHTML = `
    <div style="padding:6px 10px 8px;font-size:10px;color:#567460;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;display:flex;align-items:center;gap:6px">
      <span class="shape-sub-preview shape-sub-preview--${subtypeClass}"></span>${shapeName}
    </div>
    <div style="height:1px;background:rgba(77,184,104,0.12);margin:0 4px 4px"></div>
    <button id="_bulk-open-modal" style="display:flex;align-items:center;gap:8px;width:100%;padding:7px 10px;border-radius:9px;border:1px solid transparent;background:transparent;color:rgba(214,237,217,0.85);cursor:pointer;font-size:11px;font-family:inherit;white-space:nowrap;text-align:left;transition:background 0.15s,border-color 0.15s,color 0.15s">
      <i class="fa-solid fa-layer-group" style="font-size:12px;color:#4DB868;flex-shrink:0"></i>
      <span>Création plurielle</span>
    </button>`;

  document.body.appendChild(panel);

  const openBtn = panel.querySelector('#_bulk-open-modal');
  openBtn.addEventListener('mouseenter', () => {
    openBtn.style.background = 'rgba(77,184,104,0.15)';
    openBtn.style.borderColor = 'rgba(77,184,104,0.22)';
    openBtn.style.color = '#6DD98A';
  });
  openBtn.addEventListener('mouseleave', () => {
    openBtn.style.background = 'transparent';
    openBtn.style.borderColor = 'transparent';
    openBtn.style.color = 'rgba(214,237,217,0.85)';
  });

  openBtn.addEventListener('click', () => {
    panel.remove();
    _bulkPanelHovered = false;
    wrap.classList.remove('open');
    _openBulkModal(shapeType, shapeSubtype, shapeName, subtypeClass);
  });

  panel.addEventListener('mouseenter', () => { _bulkPanelHovered = true; });
  panel.addEventListener('mouseleave', e => {
    _bulkPanelHovered = false;
    const to = e.relatedTarget;
    if (to && wrap.contains(to)) return;
    panel.remove();
    setTimeout(() => wrap.classList.remove('open'), 180);
  });
}

function _openBulkModal(shapeType, shapeSubtype, shapeName, previewClass) {
  document.getElementById('_bulk-modal')?.remove();

  // Inject custom scrollbar styles once
  if (!document.getElementById('_bulk-modal-styles')) {
    const st = document.createElement('style');
    st.id = '_bulk-modal-styles';
    st.textContent = `
      ._bulk-band-list::-webkit-scrollbar { width: 3px; }
      ._bulk-band-list::-webkit-scrollbar-track { background: transparent; }
      ._bulk-band-list::-webkit-scrollbar-thumb { background: rgba(77,184,104,0.3); border-radius: 3px; }
      ._bulk-band-list::-webkit-scrollbar-thumb:hover { background: rgba(77,184,104,0.55); }
      ._bs-btn { display:flex;align-items:center;justify-content:center;width:30px;height:30px;border:none;background:transparent;color:#4DB868;font-size:18px;cursor:pointer;font-family:inherit;line-height:1;transition:background 0.12s,color 0.12s;border-radius:6px;flex-shrink:0; }
      ._bs-btn:hover { background:rgba(77,184,104,0.15);color:#6DD98A; }
    `;
    document.head.appendChild(st);
  }

  const activeBands = state.bands.filter(b => !b.deleted);
  if (activeBands.length === 0) { showToast(_L('editor.toast.no_bands')); return; }

  const bandRows = activeBands.map(band => {
    const realIdx = state.bands.indexOf(band);
    return `<div style="display:flex;align-items:center;gap:10px;padding:10px 2px;border-bottom:1px solid rgba(77,184,104,0.07)">
      <span style="width:18px;height:18px;border-radius:4px;background:${band.color};flex-shrink:0;display:inline-block;box-shadow:0 1px 4px rgba(0,0,0,0.3)"></span>
      <span style="flex:1;font-size:12px;color:#D6EDD9;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${band.label || ''}">${band.label || '(sans nom)'}</span>
      <div style="display:flex;align-items:center;gap:0;border:1px solid rgba(77,184,104,0.22);border-radius:8px;overflow:hidden;background:rgba(77,184,104,0.06);flex-shrink:0">
        <button class="_bs-btn _bs-dec" data-bi="${realIdx}">−</button>
        <span class="_bulk-val" data-bi="${realIdx}" style="min-width:26px;text-align:center;font-size:13px;color:#D6EDD9;font-weight:600;user-select:none;padding:0 2px">1</span>
        <button class="_bs-btn _bs-inc" data-bi="${realIdx}">+</button>
      </div>
    </div>`;
  }).join('');

  const overlay = document.createElement('div');
  overlay.id = '_bulk-modal';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;z-index:9000;backdrop-filter:blur(2px)';
  overlay.innerHTML = `
    <div style="background:#1A231D;border:1px solid rgba(77,184,104,0.22);border-radius:20px;padding:28px 32px;min-width:420px;max-width:500px;box-shadow:0 32px 80px rgba(0,0,0,0.6)">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:20px">
        <span class="shape-sub-preview shape-sub-preview--${previewClass}" style="flex-shrink:0;transform:scale(1.5);transform-origin:left center"></span>
        <div>
          <div style="font-size:15px;font-weight:700;color:#D6EDD9">${_L('editor.bulk.title_prefix')}${shapeName}</div>
          <div style="font-size:11.5px;color:#567460;margin-top:3px">${_L('editor.bulk.count_hint')}</div>
        </div>
      </div>
      <div style="margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid rgba(77,184,104,0.1)">
        <div style="font-size:10.5px;color:#567460;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:7px">${_L('editor.bulk.text_section')}</div>
        <input id="_bulk-name-input" type="text" placeholder="${_L('editor.bulk.name_placeholder')}"
          style="width:100%;box-sizing:border-box;background:rgba(77,184,104,0.08);border:1px solid rgba(77,184,104,0.22);border-radius:8px;color:#D6EDD9;font-size:12.5px;font-family:inherit;padding:8px 12px;outline:none;transition:border-color 0.15s,background 0.15s">
        <label style="display:flex;align-items:center;gap:7px;margin-top:8px;cursor:pointer;font-size:11.5px;color:#567460;user-select:none">
          <input type="checkbox" id="_bulk-autonumber" style="accent-color:#4DB868;width:13px;height:13px">
          ${_L('editor.bulk.autonumber')}
        </label>
      </div>
      <div class="_bulk-band-list" style="max-height:240px;overflow-y:auto;margin-bottom:24px;scrollbar-width:thin;scrollbar-color:rgba(77,184,104,0.3) transparent">
        ${bandRows}
      </div>
      <div style="display:flex;gap:10px;justify-content:flex-end">
        <button id="_bulk-cancel" style="padding:10px 24px;border-radius:11px;border:1px solid rgba(77,184,104,0.22);background:transparent;color:#567460;font-size:13px;cursor:pointer;font-family:inherit;transition:background 0.15s,color 0.15s">${_L('btn.cancel')}</button>
        <button id="_bulk-ok" style="padding:10px 24px;border-radius:11px;border:none;background:#4DB868;color:#0E1610;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;transition:filter 0.15s">${_L('editor.bulk.btn_create')}</button>
      </div>
    </div>`;

  document.body.appendChild(overlay);
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  overlay.querySelector('#_bulk-cancel').onclick = () => overlay.remove();
  overlay.querySelector('#_bulk-ok').addEventListener('mouseenter', e => { e.target.style.filter = 'brightness(1.12)'; });
  overlay.querySelector('#_bulk-ok').addEventListener('mouseleave', e => { e.target.style.filter = ''; });

  const nameInput = overlay.querySelector('#_bulk-name-input');
  nameInput.addEventListener('focus', () => { nameInput.style.borderColor = '#4DB868'; nameInput.style.background = 'rgba(77,184,104,0.15)'; });
  nameInput.addEventListener('blur',  () => { nameInput.style.borderColor = 'rgba(77,184,104,0.22)'; nameInput.style.background = 'rgba(77,184,104,0.08)'; });

  // Stepper +/- logic
  const vals = {}; // bandIdx → current value
  activeBands.forEach(band => { vals[state.bands.indexOf(band)] = 1; });

  overlay.querySelectorAll('._bs-dec').forEach(btn => {
    btn.addEventListener('click', () => {
      const bi = parseInt(btn.dataset.bi);
      vals[bi] = Math.max(0, (vals[bi] || 0) - 1);
      overlay.querySelector(`._bulk-val[data-bi="${bi}"]`).textContent = vals[bi];
    });
  });
  overlay.querySelectorAll('._bs-inc').forEach(btn => {
    btn.addEventListener('click', () => {
      const bi = parseInt(btn.dataset.bi);
      vals[bi] = Math.min(30, (vals[bi] || 0) + 1);
      overlay.querySelector(`._bulk-val[data-bi="${bi}"]`).textContent = vals[bi];
    });
  });

  overlay.querySelector('#_bulk-ok').onclick = () => {
    const baseName   = nameInput.value.trim();
    const autoNumber = overlay.querySelector('#_bulk-autonumber').checked;
    const counts = [];
    for (const [bi, count] of Object.entries(vals)) {
      if (count > 0) counts.push({ bandIdx: parseInt(bi), count });
    }
    overlay.remove();
    if (counts.length > 0) _createBulkShapes(shapeType, shapeSubtype, counts, baseName, autoNumber);
    else showToast(_L('editor.toast.no_shapes_create'));
  };
}

function _createBulkShapes(shapeType, shapeSubtype, counts, baseName = '', autoNumber = true) {
  const def = SHAPE_DEFAULTS[shapeType];
  if (!def) return;

  const SW  = def.w, SH = def.h;
  const GAP = 18;
  const X0  = INDEX_W_SVG + 24;

  let totalCreated = 0, totalFailed = 0, globalIdx = 1;

  for (const { bandIdx, count } of counts) {
    const band = state.bands[bandIdx];
    if (!band || band.deleted) continue;

    // Band Y range
    let bandY = -200;
    for (let j = 0; j < bandIdx; j++) {
      if (!state.bands[j].deleted) bandY += state.bands[j].height;
    }
    const bandYEnd = bandY + band.height;

    // Existing shapes in this band (used for collision)
    const placed = state.shapes.filter(s => {
      const midY = s.y + s.h / 2;
      return midY >= bandY && midY < bandYEnd;
    });

    // Build candidate Y rows: distribute vertically in band
    const usableH = band.height - GAP * 2;
    const maxRows  = Math.max(1, Math.floor(usableH / (SH + GAP)));
    const rows = [];
    for (let r = 0; r < maxRows; r++) {
      const y = Math.round(bandY + GAP + r * (SH + GAP));
      if (y + SH <= bandYEnd - 4) rows.push(y);
    }
    if (rows.length === 0) rows.push(Math.round(bandY + (band.height - SH) / 2));

    // Scan grid left → right, cycling rows
    function overlaps(x, y) {
      for (const s of placed) {
        if (x < s.x + s.w + GAP / 2 && x + SW + GAP / 2 > s.x &&
            y < s.y + s.h + GAP / 2 && y + SH + GAP / 2 > s.y) return true;
      }
      return false;
    }

    const maxX  = (state.bandWidth || 3200) - SW - GAP;
    const xStep = SW + GAP;
    let created = 0;

    outer:
    for (let xi = 0; X0 + xi * xStep <= maxX; xi++) {
      const x = X0 + xi * xStep;
      for (const y of rows) {
        if (created >= count) break outer;
        if (!overlaps(x, y)) {
          const label = baseName
            ? (autoNumber ? `${baseName} ${globalIdx}` : baseName)
            : '';
          const s = {
            id: state.nextId++,
            type: shapeType,
            x, y, w: SW, h: SH,
            label,
            color: band.color,
            textColor: def.textColor,
            strokeColor: '',
            validationBadge: false,
            validationColor: def.validationColor || '#4DB868',
            fontSize: def.fontSize || 14,
            colorVariant: 0,
            subtype: shapeSubtype || def.subtype || 'normal',
          };
          state.shapes.push(s);
          updateShapeColor(s);
          placed.push(s);
          created++;
          totalCreated++;
          globalIdx++;
        }
      }
    }

    totalFailed += count - created;
  }

  if (totalCreated > 0) { snapshot(); render(); }

  if (totalFailed > 0)
    showToast(_L('editor.toast.bulk_partial').replace('{count}', totalCreated).replace('{failed}', totalFailed));
  else
    showToast(_L('editor.toast.bulk_created').replace('{count}', totalCreated));
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
      btn.addEventListener('click', () => showToast(_L('editor.toast.drag_to_canvas')));
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

  // Hover dropdown sur le bouton Activité (immédiat) + panneau Création plurielle (1s)
  const processWrap = document.getElementById('process-shape-wrap');
  if (processWrap) {
    let hideTimer = null;
    let bulkTimer = null;

    processWrap.addEventListener('mouseenter', () => {
      clearTimeout(hideTimer);
      processWrap.classList.add('open');
    });
    processWrap.addEventListener('mouseleave', e => {
      // Stay open if mouse moved into the bulk side panel
      if (_bulkPanelHovered) return;
      const to = e.relatedTarget;
      const bulkPanel = document.getElementById('_bulk-side-panel');
      if (bulkPanel && to && bulkPanel.contains(to)) return;
      clearTimeout(bulkTimer);
      hideTimer = setTimeout(() => {
        processWrap.classList.remove('open');
        document.getElementById('_bulk-side-panel')?.remove();
        _bulkPanelHovered = false;
      }, 180);
    });

    // 1-second hover on individual shape buttons → show bulk panel aligned to hovered button
    processWrap.querySelectorAll('.shape-sub-btn').forEach(btn => {
      btn.addEventListener('mouseenter', () => {
        clearTimeout(bulkTimer);
        // Close any existing bulk panel when moving to a different button
        document.getElementById('_bulk-side-panel')?.remove();
        _bulkPanelHovered = false;
        bulkTimer = setTimeout(() => {
          _showBulkPanel(btn.dataset.shapeType, btn.dataset.shapeSubtype, processWrap, btn);
        }, 1000);
      });
      btn.addEventListener('mouseleave', () => {
        clearTimeout(bulkTimer);
      });
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
        showToast(_L('editor.toast.routing_updated').replace('{routing}', routing === 'smooth' ? _L('editor.conn_curve') : _L('editor.conn_orthogonal')));
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
    _fitShapeIntoBand(s); // grow band if shape overflows its bottom edge
    selectShape(s.id, false, false);
    snapshot(); render(); updateProps();
    showToast(_L('editor.toast.shape_added'));
  });

  // Panel collapse
  document.getElementById('btn-close-left-panel').addEventListener('click', () => setLeftPanelOpen(false));
  document.getElementById('btn-close-props').addEventListener('click', () => setPropsOpen(false));
  document.getElementById('btn-left-panel-open').addEventListener('click', () => setLeftPanelOpen(!leftPanelOpen));
  document.getElementById('btn-right-panel-open').addEventListener('click', () => setPropsOpen(!propsOpen));

  // Grouper
  document.getElementById('btn-group-create').addEventListener('click', createGroup);

  // Pile
  document.getElementById('btn-add-pile')?.addEventListener('click', createPile);

  // Lasso (box select)
  document.getElementById('btn-lasso-select')?.addEventListener('click', () => setLassoMode(!lassoMode));

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
  document.getElementById('btn-architect').addEventListener('click', runCartoCheck);
  // btn-place-labels : bouton unique et clair → agencement automatique complet
  document.getElementById('btn-place-labels')?.addEventListener('click', autoLayoutArrows);
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

  // Calques
  initCalqueSection();

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

  // Avertissement modification non enregistrées (navigation browser)
  if (!window.OPTIQCARTO_READONLY) {
    window.addEventListener('beforeunload', e => {
      if (isDirty) { e.preventDefault(); e.returnValue = ''; }
    });
    const backBtn = document.getElementById('btn-back-floating');
    if (backBtn) {
      backBtn.addEventListener('click', async e => {
        if (!isDirty) return;
        e.preventDefault();
        const href = backBtn.getAttribute('href') || '/activities/map';
        const result = await _showUnsavedModal();
        if (result === 'save') {
          const ok = await saveJSON();
          if (ok) window.location.href = href;
        } else if (result === 'discard') {
          isDirty = false;
          window.location.href = href;
        }
      });
    }
  }

  // Auto-load cartography from DB if one exists
  if (window.OPTIQCARTO_HAS_CARTO && window.OPTIQCARTO_DEFAULT_NAME) {
    const apiBase = window.OPTIQCARTO_API_BASE || '/cartography';

    function _applyLoadedState(data) {
      if (!data || data.error) return;
      state = data;
      if (typeof resetHighlightExtco === 'function') resetHighlightExtco();
      if (!state.bandWidth) state.bandWidth = 3200;
      if (!state.groups) state.groups = [];
      if (state.bands && state.bands.length > 0 && state.bands.every(b => b.deleted)) {
        state.bands.forEach(b => { b.deleted = false; });
      }
      if (state.connections && state.shapes) {
        const allIds = new Set([
          ...state.shapes.map(s => String(s.id)),
          ...(state.groups || []).map(g => String(g.id)),
        ]);
        state.connections = state.connections.filter(
          c => allIds.has(String(c.fromId)) && allIds.has(String(c.toId))
        );
      }
      _restoreCollapsedPiles();
      history = [JSON.stringify(state)]; histIndex = 0;
      isDirty = false;
      render(); updateProps(); fitView();
      try { window.parent.postMessage({ type: 'carto-state-ready' }, '*'); } catch(_) {}
    }

    if (window.OPTIQCARTO_ACTIVE_CALQUE) {
      // Restore active calque state
      fetch(`${apiBase}/api/calques/${window.OPTIQCARTO_ACTIVE_CALQUE}`)
        .then(r => r.json())
        .then(data => {
          if (data && !data.error) {
            activeCalqueId = window.OPTIQCARTO_ACTIVE_CALQUE;
            _calqueIsNew   = false;
            _applyLoadedState(data);
            _loadCalqueList().then(() => {
              const cal = _calqueList.find(c => c.id === activeCalqueId);
              _updateCalqueBadge(cal ? cal.name : 'Calque');
              renderCalqueListUI();
            });
          } else {
            // Fallback to base carto if calque not found
            fetch(`${apiBase}/api/load/${encodeURIComponent(window.OPTIQCARTO_DEFAULT_NAME)}`)
              .then(r => r.json()).then(_applyLoadedState).catch(() => {});
          }
        })
        .catch(() => {
          fetch(`${apiBase}/api/load/${encodeURIComponent(window.OPTIQCARTO_DEFAULT_NAME)}`)
            .then(r => r.json()).then(_applyLoadedState).catch(() => {});
        });
    } else {
      fetch(`${apiBase}/api/load/${encodeURIComponent(window.OPTIQCARTO_DEFAULT_NAME)}`)
        .then(r => r.json())
        .then(_applyLoadedState)
        .catch(() => {});
    }
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

function initDock() { /* dock supprimé */ }


document.addEventListener('DOMContentLoaded', init);

/* ══════════════════════════════════════════════════
   MODE CONNEXION INTER-CARTO (viewer readonly)
   Colore en bleu les extco liées, en vert les origines
   officialisées, grise le reste.
   ══════════════════════════════════════════════════ */

let _cxMatchedIds = new Set(); // shape IDs extco → bleu
let _cxOriginIds  = new Set(); // shape IDs origines → vert
let _cxActive     = false;

const _CX_DIM_FILL   = '#e2e8f0';
const _CX_DIM_STROKE = '#cbd5e1';
const _CX_BLUE_FILL  = '#3b82f6';
const _CX_BLUE_STR   = '#1d4ed8';
const _CX_GREEN_FILL = '#22c55e';
const _CX_GREEN_STR  = '#15803d';

function _cxApply() {
  for (const s of state.shapes || []) {
    const sid = String(s.id);
    if (s._cxOrig === undefined) s._cxOrig = { color: s.color, strokeColor: s.strokeColor };
    if (_cxMatchedIds.has(sid)) {
      s.color = _CX_BLUE_FILL; s.strokeColor = _CX_BLUE_STR;
    } else if (_cxOriginIds.has(sid)) {
      s.color = _CX_GREEN_FILL; s.strokeColor = _CX_GREEN_STR;
    } else {
      s.color = _CX_DIM_FILL; s.strokeColor = _CX_DIM_STROKE;
    }
  }
  for (const b of state.bands || []) {
    if (b._cxOrig === undefined) b._cxOrig = b.color;
    b.color = _CX_DIM_FILL;
  }
  for (const c of state.connections || []) {
    if (c._cxOrig === undefined) c._cxOrig = c.color;
    c.color = _CX_DIM_FILL;
  }
}

function _cxRestore() {
  for (const s of state.shapes || []) {
    if (s._cxOrig !== undefined) { s.color = s._cxOrig.color; s.strokeColor = s._cxOrig.strokeColor; delete s._cxOrig; }
  }
  for (const b of state.bands || []) {
    if (b._cxOrig !== undefined) { b.color = b._cxOrig; delete b._cxOrig; }
  }
  for (const c of state.connections || []) {
    if (c._cxOrig !== undefined) { c.color = c._cxOrig; delete c._cxOrig; }
  }
}

// Écoute les messages postMessage depuis la page parente (activities_map).
window.addEventListener('message', function(e) {
  if (!e.data || typeof e.data !== 'object') return;

  if (e.data.type === 'connexion-highlight') {
    _cxMatchedIds = new Set((e.data.matchedShapeIds || []).map(String));
    _cxOriginIds  = new Set((e.data.originShapeIds  || []).map(String));
    _cxActive = true;
    _cxRestore();
    _cxApply();
    render();
  }

  if (e.data.type === 'connexion-mode') {
    if (e.data.active) {
      _cxActive = true;
    } else {
      _cxActive = false;
      _cxMatchedIds.clear(); _cxOriginIds.clear();
      _cxRestore();
      render();
    }
  }

  if (e.data.type === 'connexion-reset') {
    _cxActive = false;
    _cxMatchedIds.clear(); _cxOriginIds.clear();
    _cxRestore();
    render();
  }

  // Après reload-liaisons, les highlights doivent être ré-envoyés par la page parente.

  if (e.data.type === 'toggle-extco') {
    if (typeof toggleHighlightExtco === 'function') toggleHighlightExtco();
    try { e.source.postMessage({ type: 'extco-state', active: typeof isHighlightExtcoActive === 'function' ? isHighlightExtcoActive() : false }, e.origin || '*'); } catch(_) {}
  }
  if (e.data.type === 'get-extco-state') {
    try { e.source.postMessage({ type: 'extco-state', active: typeof isHighlightExtcoActive === 'function' ? isHighlightExtcoActive() : false }, e.origin || '*'); } catch(_) {}
  }

  // Recentrer la carto sur toutes les formes (depuis le bouton icône de la page map)
  if (e.data.type === 'fit-view') {
    fitView();
  }

  // Zoom sur une activité + halo lumineux (depuis la prévisualisation cross-carto)
  if (e.data.type === 'zoom-to-activity') {
    const name = (e.data.activityName || '').trim().toLowerCase();
    if (!name) return;
    _haloShapeId = null;
    // Chercher forme par label exact puis par inclusion
    let target = state.shapes.find(s => (s.label || '').trim().toLowerCase() === name);
    if (!target) target = state.shapes.find(s => {
      const sl = (s.label || '').trim().toLowerCase();
      return sl.includes(name) || name.includes(sl);
    });
    if (!target) return;
    _haloShapeId = target.id;
    // Centrer et zoomer sur la forme
    const cx = target.x + target.w / 2;
    const cy = target.y + target.h / 2;
    const cvs = canvas.getBoundingClientRect();
    vpScale = Math.max(0.6, vpScale); // au moins 120% affiché
    vpX = cvs.width  / 2 - cx * vpScale;
    vpY = cvs.height / 2 - cy * vpScale;
    applyViewport();
    render();
  }
});
