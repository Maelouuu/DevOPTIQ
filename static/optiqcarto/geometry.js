'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — Géométrie & chemins SVG (aucune dépendance)
   Fonctions pures : ne lisent ni n'écrivent le DOM ni l'état global.
   ══════════════════════════════════════════════════ */

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

/* ── Ports ──────────────────────────────────────── */

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

function hitShape(s, px, py) {
  return px >= s.x && px <= s.x + s.w && py >= s.y && py <= s.y + s.h;
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

/* ── Chemins SVG ────────────────────────────────── */

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
function orthogonalPts(fp, tp, bundleOffset = 0, userOffset = { dx: 0, dy: 0 }) {
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
    return [fp, p1, { x: p2.x + (userOffset.dx || 0), y: p1.y + (userOffset.dy || 0) }, p2, tp];
  } else if (!isH(fdir) && isH(tdir)) {
    return [fp, p1, { x: p1.x + (userOffset.dx || 0), y: p2.y + (userOffset.dy || 0) }, p2, tp];
  } else if (isH(fdir)) {
    // H→H : décaler le segment horizontal du milieu pour séparer les bundles parallèles
    if (Math.abs(dy12) < 2) return [fp, p1, p2, tp];
    const SAFE = 52;
    const rawMid = (p1.y + p2.y) / 2;
    const safeMid = Math.abs(rawMid - fp.y) < SAFE ? fp.y + Math.sign(dy12 || 1) * SAFE : rawMid;
    const midY = safeMid + bundleOffset + (userOffset.dy || 0);
    return [fp, p1, { x: p1.x, y: midY }, { x: p2.x, y: midY }, p2, tp];
  } else {
    // V→V : décaler le segment vertical du milieu pour séparer les bundles parallèles
    if (Math.abs(dx12) < 2) return [fp, p1, p2, tp];
    const SAFE = 52;
    const rawMid = (p1.x + p2.x) / 2;
    const safeMid = Math.abs(rawMid - fp.x) < SAFE ? fp.x + Math.sign(dx12 || 1) * SAFE : rawMid;
    const midX = safeMid + bundleOffset + (userOffset.dx || 0);
    return [fp, p1, { x: midX, y: p1.y }, { x: midX, y: p2.y }, p2, tp];
  }
}

// Évite les formes : reroute les segments qui traversent une shape (6 passes max)
// Choisit intelligemment le côté de détour en testant lequel est le plus dégagé
function avoidShapes(pts, shapes, fromId, toId) {
  if (!shapes || shapes.length === 0) return pts;
  const PAD = 20;
  const R   = PAD + 10;

  // Les décisions (losanges) sont des nœuds de routage : leur bounding-box
  // dépasse leur silhouette visuelle, ce qui génère de faux blocages et des
  // chemins complexes. On les exclut des obstacles pour les deux fonctions.
  function isObstacle(s) {
    return s.id !== fromId && s.id !== toId && s.type !== 'decision';
  }

  function firstBlocker(p1, p2) {
    if (Math.abs(p1.y - p2.y) < 2) {
      const y = p1.y, x1 = Math.min(p1.x, p2.x), x2 = Math.max(p1.x, p2.x);
      for (const s of shapes) {
        if (!isObstacle(s)) continue;
        if (y > s.y - PAD && y < s.y + s.h + PAD && x1 < s.x + s.w + PAD && x2 > s.x - PAD) return s;
      }
    } else if (Math.abs(p1.x - p2.x) < 2) {
      const x = p1.x, y1 = Math.min(p1.y, p2.y), y2 = Math.max(p1.y, p2.y);
      for (const s of shapes) {
        if (!isObstacle(s)) continue;
        if (x > s.x - PAD && x < s.x + s.w + PAD && y1 < s.y + s.h + PAD && y2 > s.y - PAD) return s;
      }
    }
    return null;
  }

  function isClear(coord, isHoriz, rangeA, rangeB, blocker) {
    for (const s of shapes) {
      if (!isObstacle(s) || s.id === blocker.id) continue;
      if (isHoriz) {
        if (coord > s.y - PAD && coord < s.y + s.h + PAD && rangeA < s.x + s.w + PAD && rangeB > s.x - PAD) return false;
      } else {
        if (coord > s.x - PAD && coord < s.x + s.w + PAD && rangeA < s.y + s.h + PAD && rangeB > s.y - PAD) return false;
      }
    }
    return true;
  }

  // Direction globale de la connexion (pour éviter les détours rétrogrades)
  const netDx = pts[pts.length - 1].x - pts[0].x;
  const netDy = pts[pts.length - 1].y - pts[0].y;

  let result = pts.map(p => ({ ...p }));
  for (let iter = 0; iter < 4; iter++) {
    let changed = false;
    const next = [result[0]];
    const last = result.length - 1;
    for (let i = 0; i + 1 < result.length; i++) {
      const p1 = result[i], p2 = result[i + 1];
      const segLen = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      // Ne pas détourer les segments très courts ni le dernier segment (évite les crochets terminaux)
      if (segLen < 35 || i === last - 1) { next.push(p2); continue; }
      const blocker = firstBlocker(p1, p2);
      if (!blocker) { next.push(p2); continue; }
      changed = true;
      if (Math.abs(p1.y - p2.y) < 2) { // horizontal → détour haut ou bas
        const aboveY = blocker.y - R, belowY = blocker.y + blocker.h + R;
        const xa = Math.min(p1.x, p2.x), xb = Math.max(p1.x, p2.x);
        const clearA = isClear(aboveY, true, xa, xb, blocker);
        const clearB = isClear(belowY, true, xa, xb, blocker);
        // Préférer le côté qui s'éloigne le moins de la direction générale
        let ry;
        if (clearA && !clearB) ry = aboveY;
        else if (!clearA && clearB) ry = belowY;
        else {
          // Biais vers le côté dans le sens du flux vertical
          const biasAbove = netDy < 0 ? -200 : 200; // favoriser la direction globale
          ry = (Math.abs(p1.y - aboveY) + biasAbove) <= (Math.abs(p1.y - belowY)) ? aboveY : belowY;
        }
        next.push({ x: p1.x, y: ry }, { x: p2.x, y: ry }, p2);
      } else { // vertical → détour gauche ou droite
        const leftX = blocker.x - R, rightX = blocker.x + blocker.w + R;
        const ya = Math.min(p1.y, p2.y), yb = Math.max(p1.y, p2.y);
        const clearL = isClear(leftX, false, ya, yb, blocker);
        const clearR = isClear(rightX, false, ya, yb, blocker);
        let rx;
        if (clearL && !clearR) rx = leftX;
        else if (!clearL && clearR) rx = rightX;
        else {
          const biasLeft = netDx < 0 ? -200 : 200;
          rx = (Math.abs(p1.x - leftX) + biasLeft) <= (Math.abs(p1.x - rightX)) ? leftX : rightX;
        }
        next.push({ x: rx, y: p1.y }, { x: rx, y: p2.y }, p2);
      }
    }
    result = next;
    if (!changed) break;
  }
  return result;
}

// Simplifie un chemin orthogonal : merge colinéaires, supprime mini U-shapes (boucles)
function simplifyPath(pts) {
  if (pts.length < 3) return pts;
  // Supprime les doublons
  let r = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const p = pts[i], q = r[r.length - 1];
    if (Math.abs(p.x - q.x) > 0.5 || Math.abs(p.y - q.y) > 0.5) r.push({ ...p });
  }
  // Merge segments colinéaires (même axe, même sens)
  let changed = true;
  while (changed && r.length > 2) {
    changed = false;
    const nxt = [r[0]];
    for (let i = 1; i < r.length - 1; i++) {
      const a = nxt[nxt.length - 1], b = r[i], c = r[i + 1];
      if ((Math.abs(a.y - b.y) < 1 && Math.abs(b.y - c.y) < 1) ||
          (Math.abs(a.x - b.x) < 1 && Math.abs(b.x - c.x) < 1)) { changed = true; continue; }
      nxt.push(b);
    }
    nxt.push(r[r.length - 1]);
    r = nxt;
  }
  // Supprime les mini U-shapes : segment A→B → bump court → segment C→D même axe
  changed = true;
  while (changed && r.length > 3) {
    changed = false;
    const nxt = [r[0]]; let i = 1;
    while (i < r.length) {
      const a = nxt[nxt.length - 1];
      if (i + 2 < r.length) {
        const b = r[i], c = r[i + 1], d = r[i + 2];
        const bumpLen = Math.hypot(c.x - b.x, c.y - b.y);
        const legH = Math.abs(b.y - a.y) < 1 && Math.abs(d.y - c.y) < 1;
        const legV = Math.abs(b.x - a.x) < 1 && Math.abs(d.x - c.x) < 1;
        if (bumpLen < 22 && (legH || legV)) {
          // Remplace a→b→c→d par un coude simple vers d
          nxt.push(legH ? { x: d.x, y: a.y } : { x: a.x, y: d.y });
          nxt.push(d); i += 3; changed = true; continue;
        }
      }
      nxt.push(r[i]); i++;
    }
    r = nxt;
  }
  return r;
}

// Flèche orthogonale (angles droits, style Visio)
function orthogonalArrow(fp, tp) {
  return polylineToPath(orthogonalPts(fp, tp), 8);
}

/* ── Retour à la ligne ──────────────────────────── */

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
