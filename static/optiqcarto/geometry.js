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

// Visual hover ports: 24 grid points for activity shapes (7 top/bottom, 5 left/right)
function getPorts(s) {
  const cx = s.x + s.w / 2, cy = s.y + s.h / 2;
  const h = s.type === 'process' ? 7 : 0;

  if (s.type === 'process' || s.type === 'special') {
    const base = {};
    for (let i = 1; i <= 7; i++) {
      const tx = (i - 1) / 6;  // 0..1 corners included
      base[`top-${i}`]    = { x: s.x + s.w * tx, y: s.y - h,         dir: 'top',    t: tx };
      base[`bottom-${i}`] = { x: s.x + s.w * tx, y: s.y + s.h + h,   dir: 'bottom', t: tx };
    }
    for (let i = 1; i <= 5; i++) {
      const ty = (i - 0.5) / 5;  // 10%..90% between corners
      base[`left-${i}`]  = { x: s.x - h,         y: s.y + s.h * ty, dir: 'left',  t: ty };
      base[`right-${i}`] = { x: s.x + s.w + h,   y: s.y + s.h * ty, dir: 'right', t: ty };
    }
    return base;
  }

  return {
    top:    { x: cx,            y: s.y - h,         dir: 'top'    },
    bottom: { x: cx,            y: s.y + s.h + h,   dir: 'bottom' },
    left:   { x: s.x - h,       y: cy,               dir: 'left'   },
    right:  { x: s.x + s.w + h, y: cy,               dir: 'right'  },
  };
}

// Snap ports for connection drag — matches visual grid
function getDetailedPorts(s) {
  const h = s.type === 'process' ? 7 : 0;
  const { x, y, w, h: sh } = s;

  if (s.type === 'start-end') {
    return [
      { x: x + w*0.25, y: y - h,       dir: 'top',    t: 0.25 },
      { x: x + w*0.50, y: y - h,       dir: 'top',    t: 0.50 },
      { x: x + w*0.75, y: y - h,       dir: 'top',    t: 0.75 },
      { x: x + w + h,  y: y + sh*0.33, dir: 'right',  t: 0.33 },
      { x: x + w + h,  y: y + sh*0.67, dir: 'right',  t: 0.67 },
      { x: x + w*0.75, y: y + sh + h,  dir: 'bottom', t: 0.75 },
      { x: x + w*0.50, y: y + sh + h,  dir: 'bottom', t: 0.50 },
      { x: x + w*0.25, y: y + sh + h,  dir: 'bottom', t: 0.25 },
      { x: x - h,      y: y + sh*0.67, dir: 'left',   t: 0.67 },
      { x: x - h,      y: y + sh*0.33, dir: 'left',   t: 0.33 },
    ];
  }

  // 24 snap ports — corners included on top/bottom, between corners on sides
  const ports = [];
  for (let i = 1; i <= 7; i++) {
    const tx = (i - 1) / 6;
    ports.push({ x: x + w * tx, y: y - h,      dir: 'top',    t: tx });
    ports.push({ x: x + w * tx, y: y + sh + h, dir: 'bottom', t: tx });
  }
  for (let i = 1; i <= 5; i++) {
    const ty = (i - 0.5) / 5;
    ports.push({ x: x - h,     y: y + sh * ty, dir: 'left',  t: ty });
    ports.push({ x: x + w + h, y: y + sh * ty, dir: 'right', t: ty });
  }
  return ports;
}

function hitShape(s, px, py) {
  return px >= s.x && px <= s.x + s.w && py >= s.y && py <= s.y + s.h;
}

function _cardinalPort(shape, dir) {
  const h = shape.type === 'process' ? 7 : 0;
  const cx = shape.x + shape.w / 2, cy = shape.y + shape.h / 2;
  if (dir === 'right')  return { x: shape.x + shape.w + h, y: cy, dir: 'right' };
  if (dir === 'left')   return { x: shape.x - h,            y: cy, dir: 'left'  };
  if (dir === 'bottom') return { x: cx, y: shape.y + shape.h + h,  dir: 'bottom' };
  return                       { x: cx, y: shape.y - h,             dir: 'top'   };
}

function bestExitPort(from, to) {
  const dx = (to.x + to.w / 2) - (from.x + from.w / 2);
  const dy = (to.y + to.h / 2) - (from.y + from.h / 2);
  if (Math.abs(dx) >= Math.abs(dy)) return _cardinalPort(from, dx >= 0 ? 'right' : 'left');
  return _cardinalPort(from, dy >= 0 ? 'bottom' : 'top');
}

function bestEntryPort(shape, fromPort) {
  const opp = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' };
  return _cardinalPort(shape, opp[fromPort.dir]);
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

// tipPad : longueur d'approche DROITE garantie avant la pointe.
// La tête de flèche fait ~16 px : si le dernier coude est arrondi trop près du bout,
// la pointe se pose sur la courbe → elle « tourne ». En bornant le rayon du DERNIER
// coude on force un segment droit ≥ tipPad avant la pointe, quel que soit le moteur
// de routage (interne, libavoid, VSDX). 0 = comportement historique inchangé.
function polylineToPath(pts, R, tipPad = 0) {
  if (pts.length < 2) return '';
  let d = `M ${pts[0].x},${pts[0].y}`;
  const lastCorner = pts.length - 2;
  for (let i = 1; i < pts.length - 1; i++) {
    const p = pts[i - 1], c = pts[i], n = pts[i + 1];
    const d1 = Math.hypot(c.x - p.x, c.y - p.y);
    const d2 = Math.hypot(n.x - c.x, n.y - c.y);
    let r  = Math.min(R, d1 / 2, d2 / 2);
    // Coude juste avant la pointe : garder ≥ tipPad de droite dans le dernier segment
    // → la tête de flèche (~16 px) se pose toujours sur du droit, jamais sur un virage.
    if (tipPad > 0 && i === lastCorner) r = Math.min(r, Math.max(0, d2 - tipPad));
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
    // H→H : UN seul décrochement (Z propre : sortir → traverser une fois → entrer) au lieu
    // d'un escalier à deux décrochements. Le décroché vertical est près de la source ;
    // bundleOffset sépare les connexions parallèles.
    if (Math.abs(dy12) < 2) return [fp, p1, p2, tp];
    const jogX = p1.x + bundleOffset + (userOffset.dx || 0);
    return [fp, { x: jogX, y: fp.y }, { x: jogX, y: tp.y }, tp];
  } else {
    // V→V : idem, UN seul décrochement horizontal (Z propre) au lieu d'un escalier.
    if (Math.abs(dx12) < 2) return [fp, p1, p2, tp];
    const jogY = p1.y + bundleOffset + (userOffset.dy || 0);
    return [fp, { x: fp.x, y: jogY }, { x: tp.x, y: jogY }, tp];
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

/* ══════════════════════════════════════════════════
   AGENCEMENT AUTOMATIQUE DES FLÈCHES (auto-layout)
   Objectif : reproduire, en un clic, le travail manuel minutieux d'un
   diagramme Visio « parfait » : ports optimaux (côtés qui se font face,
   répartis pour ne pas se croiser), routage orthogonal qui contourne les
   formes, et séparation des flèches parallèles. Fonctions pures & testables.
   ══════════════════════════════════════════════════ */

const _OPP_DIR = { right: 'left', left: 'right', top: 'bottom', bottom: 'top' };

// Ordre de repli d'une pointe de losange : sa direction, puis les 2 perpendiculaires,
// puis l'opposée. Sert à réattribuer une pointe LIBRE la plus proche quand la pointe
// préférée est déjà prise (exclusivité : une pointe = une seule flèche).
const _TIP_FALLBACK = {
  top:    ['top', 'right', 'left', 'bottom'],
  right:  ['right', 'bottom', 'top', 'left'],
  bottom: ['bottom', 'left', 'right', 'top'],
  left:   ['left', 'top', 'bottom', 'right'],
};

// Avance un point d'une distance dans une direction cardinale.
function _advancePt(p, dir, dist) {
  if (dir === 'right')  return { x: p.x + dist, y: p.y };
  if (dir === 'left')   return { x: p.x - dist, y: p.y };
  if (dir === 'bottom') return { x: p.x, y: p.y + dist };
  return { x: p.x, y: p.y - dist }; // top
}

// Garantit une approche DROITE d'au moins minLen avant la pointe (ou après la
// sortie) : la flèche rentre/sort perpendiculairement à la forme sur une petite
// distance → sa tête n'est jamais posée sur un virage. N'ajuste que des points
// intérieurs (jamais les ports), et ne crée jamais d'oblique. Cas typique : la
// séparation en voies a rapproché le segment de la forme et raccourci le stub.
function _straightApproach(pts, dir, minLen, atStart) {
  const n = pts.length;
  if (n < 4 || !dir) return pts; // besoin d'un coude intérieur déplaçable
  const ei = atStart ? 0 : n - 1;       // port (fixe)
  const ni = atStart ? 1 : n - 2;       // voisin du port
  const ci = atStart ? 2 : n - 3;       // coude avant le voisin (doit rester intérieur)
  if (ci <= 0 || ci >= n - 1) return pts;
  const end = pts[ei], nbr = pts[ni];
  const horiz = (dir === 'left' || dir === 'right'); // approche le long de x
  const along = horiz ? Math.abs(nbr.y - end.y) < 1.5 : Math.abs(nbr.x - end.x) < 1.5;
  if (!along) return pts; // dernier segment non perpendiculaire au côté → on ne touche pas
  const cur = horiz ? Math.abs(nbr.x - end.x) : Math.abs(nbr.y - end.y);
  if (cur >= minLen) return pts;
  const tgt = _advancePt(end, dir, minLen); // point extérieur à minLen sur l'axe d'approche
  const p = pts.map(q => ({ x: q.x, y: q.y }));
  if (horiz) { p[ni].x = tgt.x; p[ci].x = tgt.x; }
  else       { p[ni].y = tgt.y; p[ci].y = tgt.y; }
  return p;
}

// Un segment orthogonal A→B traverse-t-il l'INTÉRIEUR strict du rectangle R ?
// (toucher un bord est autorisé — sinon on ne pourrait jamais longer une forme)
function _segCrossesRect(ax, ay, bx, by, R) {
  const rx1 = R.x, ry1 = R.y, rx2 = R.x + R.w, ry2 = R.y + R.h;
  const E = 0.5;
  if (Math.abs(ay - by) < 0.5) { // horizontal, y = ay
    if (ay <= ry1 + E || ay >= ry2 - E) return false;
    const x1 = Math.min(ax, bx), x2 = Math.max(ax, bx);
    return x1 < rx2 - E && x2 > rx1 + E;
  }
  // vertical, x = ax
  if (ax <= rx1 + E || ax >= rx2 - E) return false;
  const y1 = Math.min(ay, by), y2 = Math.max(ay, by);
  return y1 < ry2 - E && y2 > ry1 + E;
}

// Min-heap binaire (file de priorité) — remplace le balayage linéaire de l'open
// set : chaque extraction du minimum est en O(log n) au lieu de O(n). C'est ce
// qui rend l'A* assez rapide pour lever les limites et router proprement les
// grosses cartos (sans quoi les longues flèches abandonnaient et traversaient
// les formes).
function _MinHeap() {
  const a = [];
  const up = i => { while (i > 0) { const p = (i - 1) >> 1; if (a[p].f <= a[i].f) break; [a[p], a[i]] = [a[i], a[p]]; i = p; } };
  const down = i => {
    for (;;) { let l = 2 * i + 1, r = l + 1, s = i;
      if (l < a.length && a[l].f < a[s].f) s = l;
      if (r < a.length && a[r].f < a[s].f) s = r;
      if (s === i) break; [a[s], a[i]] = [a[i], a[s]]; i = s; }
  };
  return {
    get size() { return a.length; },
    push(n) { a.push(n); up(a.length - 1); },
    pop() { const top = a[0], last = a.pop(); if (a.length) { a[0] = last; down(0); } return top; },
  };
}

// Réduit un tableau de coordonnées triées à ~max valeurs en fusionnant celles
// qui sont proches (quantification par seaux). Les coordonnées « protégées »
// (entrées/sorties) sont toujours conservées exactement. Sûr : la grille ne sert
// qu'à proposer des points de virage — les obstacles sont testés sur les vrais
// rectangles, donc une grille plus grossière ne crée jamais de croisement (au
// pire elle rate un couloir étroit → l'A* échoue et on garde le repli).
function _thinCoords(arr, keep, max) {
  if (arr.length <= max) return arr;
  const lo = arr[0], hi = arr[arr.length - 1];
  const bucket = Math.max(1, (hi - lo) / max);
  const s = new Set();
  for (const v of arr) s.add(Math.round(v / bucket) * bucket);
  for (const v of keep) s.add(v);
  return [...s].sort((a, b) => a - b);
}

// Un tracé orthogonal traverse-t-il l'intérieur d'un des obstacles ? (sert de
// filet de sécurité pour rattraper un stub ou un segment résiduel qui frôlerait
// une forme.)
function pathCrossesObstacles(pts, obstacles) {
  if (!pts || pts.length < 2) return false;
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    for (const o of obstacles) if (_segCrossesRect(a.x, a.y, b.x, b.y, o)) return true;
  }
  return false;
}

// Routage orthogonal évitant les obstacles (A* sur une grille de « lignes
// intéressantes » façon Hightower/draw.io). Coût = longueur + pénalité de virage.
// fp/tp = { x, y, dir }  ;  obstacles = [{x,y,w,h}] (hors formes des 2 extrémités).
// Renvoie [fp, ...coudes, tp] parfaitement orthogonal, ou null si aucun chemin.
function routeOrthogonalAStar(fp, tp, obstacles, opts) {
  opts = opts || {};
  const MARGIN = opts.margin != null ? opts.margin : 16;
  const STUB   = opts.stub   != null ? opts.stub   : 28; // approche droite mini avant la pointe
  const BEND   = opts.bend   != null ? opts.bend   : 20;
  const NODE_CAP = opts.nodeCap != null ? opts.nodeCap : 40000; // grille bornée (heap ⇒ abordable)
  const AXIS_CAP = Math.floor(Math.sqrt(NODE_CAP));

  const s0 = _advancePt(fp, fp.dir, STUB);
  const e0 = _advancePt(tp, tp.dir, STUB);

  // Rectangles obstacles élargis, limités à la zone utile (bbox + marge)
  const bx1 = Math.min(s0.x, e0.x) - 500, bx2 = Math.max(s0.x, e0.x) + 500;
  const by1 = Math.min(s0.y, e0.y) - 500, by2 = Math.max(s0.y, e0.y) + 500;
  const rects = [];
  for (const o of (obstacles || [])) {
    const r = { x: o.x - MARGIN, y: o.y - MARGIN, w: o.w + 2 * MARGIN, h: o.h + 2 * MARGIN };
    if (r.x + r.w < bx1 || r.x > bx2 || r.y + r.h < by1 || r.y > by2) continue;
    rects.push(r);
  }

  // Lignes de grille : bords des obstacles élargis + points d'entrée/sortie
  const xsSet = new Set(), ysSet = new Set();
  const q = v => Math.round(v * 2) / 2;
  const addX = v => xsSet.add(q(v)), addY = v => ysSet.add(q(v));
  addX(s0.x); addX(e0.x); addX(fp.x); addX(tp.x);
  addY(s0.y); addY(e0.y); addY(fp.y); addY(tp.y);
  for (const r of rects) { addX(r.x); addX(r.x + r.w); addY(r.y); addY(r.y + r.h); }
  let xs = [...xsSet].sort((a, b) => a - b);
  let ys = [...ysSet].sort((a, b) => a - b);
  // Trop de lignes → on grossit la grille au lieu d'abandonner (les longues
  // flèches des grosses cartos ne traversent plus les formes).
  const keepX = [q(s0.x), q(e0.x), q(fp.x), q(tp.x)];
  const keepY = [q(s0.y), q(e0.y), q(fp.y), q(tp.y)];
  if (xs.length > AXIS_CAP) xs = _thinCoords(xs, keepX, AXIS_CAP);
  if (ys.length > AXIS_CAP) ys = _thinCoords(ys, keepY, AXIS_CAP);

  const xi = new Map(xs.map((v, i) => [v, i]));
  const yi = new Map(ys.map((v, i) => [v, i]));
  const sX = xi.get(q(s0.x)), sY = yi.get(q(s0.y));
  const gX = xi.get(q(e0.x)), gY = yi.get(q(e0.y));
  if (sX == null || sY == null || gX == null || gY == null) return null;

  function ptInside(x, y) {
    for (const r of rects)
      if (x > r.x + 0.5 && x < r.x + r.w - 0.5 && y > r.y + 0.5 && y < r.y + r.h - 0.5) return true;
    return false;
  }
  function edgeClear(ax, ay, bx, by) {
    for (const r of rects) if (_segCrossesRect(ax, ay, bx, by, r)) return false;
    return true;
  }

  const goalKey = gX * 100000 + gY;
  const H = (ix, iy) => Math.abs(xs[ix] - xs[gX]) + Math.abs(ys[iy] - ys[gY]);
  const heap = _MinHeap();
  const gScore = new Map();
  const closed = new Set();
  const startKey = sX * 100000 + sY;
  heap.push({ xi: sX, yi: sY, g: 0, f: H(sX, sY), dir: fp.dir, prev: null, key: startKey });
  gScore.set(startKey, 0);

  let goal = null, guard = 0;
  const MAXITER = 400000;
  while (heap.size && guard++ < MAXITER) {
    const best = heap.pop();
    if (best.key === goalKey) { goal = best; break; }
    if (closed.has(best.key)) continue;
    if (best.g > (gScore.get(best.key) ?? Infinity)) continue; // entrée périmée (lazy delete)
    closed.add(best.key);
    const cx = xs[best.xi], cy = ys[best.yi];
    const neigh = [];
    if (best.xi + 1 < xs.length) neigh.push([best.xi + 1, best.yi, 'right']);
    if (best.xi - 1 >= 0)        neigh.push([best.xi - 1, best.yi, 'left']);
    if (best.yi + 1 < ys.length) neigh.push([best.xi, best.yi + 1, 'bottom']);
    if (best.yi - 1 >= 0)        neigh.push([best.xi, best.yi - 1, 'top']);
    for (const [nx, ny, ndir] of neigh) {
      const k = nx * 100000 + ny;
      if (closed.has(k)) continue;
      const px = xs[nx], py = ys[ny];
      if ((nx !== gX || ny !== gY) && ptInside(px, py)) continue;
      if (!edgeClear(cx, cy, px, py)) continue;
      const g = best.g + Math.abs(px - cx) + Math.abs(py - cy) + (best.dir && best.dir !== ndir ? BEND : 0);
      if (g >= (gScore.get(k) ?? Infinity)) continue;
      gScore.set(k, g);
      heap.push({ xi: nx, yi: ny, g, f: g + H(nx, ny), dir: ndir, prev: best, key: k });
    }
  }
  if (!goal) return null;

  const grid = [];
  for (let n = goal; n; n = n.prev) grid.unshift({ x: xs[n.xi], y: ys[n.yi] });
  return simplifyPath([{ x: fp.x, y: fp.y }, ...grid, { x: tp.x, y: tp.y }]);
}

// Attribue à chaque connexion les côtés (ports) optimaux + leur position (t)
// répartie le long du côté pour minimiser les croisements.
// nodesById[id] = {x,y,w,h}  ;  connections = [{id, fromId, toId}]
// Renvoie [{connId, fromDir, fromT, toDir, toT}] (aligné sur connections).
function autoAssignPorts(nodesById, connections) {
  const pushG = (map, key, val) => { let a = map.get(key); if (!a) { a = []; map.set(key, a); } a.push(val); };
  const info = [];
  for (const c of connections) {
    const a = nodesById[c.fromId], b = nodesById[c.toId];
    if (!a || !b || c.fromId === c.toId) { info.push(null); continue; }
    const ac = { x: a.x + a.w / 2, y: a.y + a.h / 2 };
    const bc = { x: b.x + b.w / 2, y: b.y + b.h / 2 };
    const sepR = b.x - (a.x + a.w), sepL = a.x - (b.x + b.w);
    const sepB = b.y - (a.y + a.h), sepT = a.y - (b.y + b.h);
    const hSep = Math.max(sepR, sepL), vSep = Math.max(sepB, sepT);
    const dx = bc.x - ac.x, dy = bc.y - ac.y;
    let fromDir;
    if (hSep >= 0 && (hSep >= vSep || vSep < 0))      fromDir = dx >= 0 ? 'right' : 'left';
    else if (vSep >= 0)                               fromDir = dy >= 0 ? 'bottom' : 'top';
    else fromDir = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top');
    info.push({ connId: c.id, fromDir, toDir: _OPP_DIR[fromDir], fromT: 0.5, toT: 0.5,
                _from: c.fromId, _to: c.toId, _a: a, _b: b, _oFrom: bc, _oTo: ac,
                _aDec: a.type === 'decision', _bDec: b.type === 'decision' });
  }
  // ── Candidats « ligne droite » ────────────────────────────────────
  // Une flèche peut être droite si les formes se font face avec un
  // recouvrement perpendiculaire (ideal = coordonnée commune des 2 ports).
  // Décisions : port fixé sur la pointe du losange → on aligne l'autre dessus.
  const clampT = t => Math.max(0.08, Math.min(0.92, t));
  for (const it of info) {
    if (!it) continue;
    const horiz = it.fromDir === 'left' || it.fromDir === 'right';
    const a = it._a, b = it._b;
    const aLo = horiz ? a.y : a.x, aHi = horiz ? a.y + a.h : a.x + a.w;
    const bMin = horiz ? b.y : b.x, bMax = horiz ? b.y + b.h : b.x + b.w;
    const aTip = (aLo + aHi) / 2, bTip = (bMin + bMax) / 2;
    let ideal = null;
    if (it._aDec && it._bDec) { if (Math.abs(aTip - bTip) < 2) ideal = aTip; }
    else if (it._aDec) { if (aTip >= bMin - 2 && aTip <= bMax + 2) ideal = aTip; }
    else if (it._bDec) { if (bTip >= aLo - 2 && bTip <= aHi + 2) ideal = bTip; }
    else {
      const lo = Math.max(aLo, bMin), hi = Math.min(aHi, bMax);
      if (hi - lo >= 14) ideal = (lo + hi) / 2;
    }
    it._ideal = ideal; it._horiz = horiz;
    it._aLo = aLo; it._aHi = aHi; it._bMin = bMin; it._bMax = bMax;
  }
  // Compte des CANDIDATS DROITS par côté : une flèche ne s'aligne que si aucune
  // autre flèche droite ne partage le même côté (une diagonale ne bloque pas).
  const straightOnSide = new Map();
  for (const it of info) if (it && it._ideal != null) {
    straightOnSide.set(it._from + '|' + it.fromDir, (straightOnSide.get(it._from + '|' + it.fromDir) || 0) + 1);
    straightOnSide.set(it._to   + '|' + it.toDir,   (straightOnSide.get(it._to   + '|' + it.toDir)   || 0) + 1);
  }
  for (const it of info) if (it && it._ideal != null) {
    if ((straightOnSide.get(it._from + '|' + it.fromDir) || 0) <= 1 &&
        (straightOnSide.get(it._to   + '|' + it.toDir)   || 0) <= 1) {
      it.fromT = clampT((it._ideal - it._aLo) / (it._aHi - it._aLo || 1));
      it.toT   = clampT((it._ideal - it._bMin) / (it._bMax - it._bMin || 1));
      it._aligned = true;
    }
  }

  // ── Répartition des flèches NON alignées ──────────────────────────
  // Groupées par côté, triées par la position de l'autre extrémité →
  // elles s'éventent sans se croiser, en évitant les flèches déjà alignées.
  const groups = new Map();
  for (const it of info) {
    if (!it || it._aligned) continue;
    pushG(groups, it._from + '|' + it.fromDir, { it, end: 'from', dir: it.fromDir, other: it._oFrom });
    pushG(groups, it._to   + '|' + it.toDir,   { it, end: 'to',   dir: it.toDir,   other: it._oTo });
  }
  for (const arr of groups.values()) {
    const axis = (arr[0].dir === 'top' || arr[0].dir === 'bottom') ? 'x' : 'y';
    arr.sort((p, r) => p.other[axis] - r.other[axis]);
    const n = arr.length;
    arr.forEach((e, i) => {
      const t = n <= 1 ? 0.5 : (i + 1) / (n + 1);
      if (e.end === 'from') e.it.fromT = t; else e.it.toT = t;
    });
  }

  // ── Exclusivité des pointes de losange (un point = un seul branchement) ──
  // Un losange se branche par ses 4 pointes. Le routeur interne peut poser 2 flèches
  // sur la même pointe (ex. 2 sorties vers la droite) → superposition. On réattribue
  // ici : chaque flèche d'un losange reçoit une pointe DISTINCTE, au plus proche de sa
  // direction naturelle. Au-delà de 4 flèches (rare) le partage reste propre.
  const decEnds = new Map();
  for (const it of info) {
    if (!it) continue;
    if (it._aDec) pushG(decEnds, it._from, { it, end: 'from', other: it._oFrom, node: it._a });
    if (it._bDec) pushG(decEnds, it._to,   { it, end: 'to',   other: it._oTo,   node: it._b });
  }
  for (const arr of decEnds.values()) {
    const node = arr[0].node;
    const cx = node.x + node.w / 2, cy = node.y + node.h / 2;
    for (const e of arr) {
      const dx = e.other.x - cx, dy = e.other.y - cy;
      e._pref = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top');
    }
    // Ordre déterministe (pointe préférée puis id) pour une attribution stable.
    const order = { top: 0, right: 1, bottom: 2, left: 3 };
    arr.sort((p, r) => (order[p._pref] - order[r._pref]) || (p.it.connId - r.it.connId));
    const used = new Set();
    for (const e of arr) {
      const dir = _TIP_FALLBACK[e._pref].find(d => !used.has(d)) || e._pref;
      used.add(dir);
      if (e.end === 'from') { e.it.fromDir = dir; e.it.fromT = 0.5; }
      else                  { e.it.toDir   = dir; e.it.toT   = 0.5; }
    }
  }

  // ── Garantie FINALE d'exclusivité sur les formes normales ───────────────
  // Un point d'accroche « aligné » (tir droit) et une flèche répartie peuvent
  // atterrir au même t sur un même côté (ex. deux à t≈0.5) → superposition. On
  // regroupe TOUTES les extrémités par (forme, côté) et, dès qu'un côté en porte
  // ≥2, on ré-écarte leurs t en positions distinctes (ordre = position de l'autre
  // extrémité, pour ne pas se croiser). Un côté à 1 seule flèche garde son t aligné.
  const sideEnds = new Map();
  for (const it of info) {
    if (!it) continue;
    if (!it._aDec) pushG(sideEnds, it._from + '|' + it.fromDir, { it, end: 'from', other: it._oFrom, node: it._a });
    if (!it._bDec) pushG(sideEnds, it._to   + '|' + it.toDir,   { it, end: 'to',   other: it._oTo,   node: it._b });
  }
  for (const arr of sideEnds.values()) {
    const dir = arr[0].end === 'from' ? arr[0].it.fromDir : arr[0].it.toDir;
    const axis = (dir === 'top' || dir === 'bottom') ? 'x' : 'y';
    const node = arr[0].node;
    const lo = axis === 'y' ? node.y : node.x;
    const hi = axis === 'y' ? node.y + node.h : node.x + node.w;
    const span = hi - lo || 1;
    // On ALIGNE chaque port sur la projection de sa cible sur le côté → la flèche
    // vise sa cible presque en ligne droite (moins de virages → moins de croisements
    // près de la forme, là où ils naissent). Puis on garantit un écart minimal pour
    // que deux flèches ne se superposent pas (exclusivité conservée).
    for (const e of arr) e._tt = clampT((e.other[axis] - lo) / span);
    arr.sort((p, r) => p._tt - r._tt);
    const n = arr.length;
    const gap = Math.min(1 / (n + 1), 0.84 / (n - 1));
    let prev = -Infinity;
    for (const e of arr) { let t = e._tt; if (t < prev + gap) t = prev + gap; e._t = t; prev = t; }
    const over = prev - 0.92;
    if (over > 0) for (const e of arr) e._t = Math.max(0.08, e._t - over);
    for (const e of arr) { if (e.end === 'from') e.it.fromT = e._t; else e.it.toT = e._t; }
  }

  return info.map(it => it ? { connId: it.connId, fromDir: it.fromDir, fromT: it.fromT, toDir: it.toDir, toT: it.toT } : null);
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

// Export pour tests Node (sans effet dans le navigateur : `module` n'existe pas)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    polylineToPath, orthogonalPts, avoidShapes, simplifyPath, orthogonalArrow,
    routeOrthogonalAStar, autoAssignPorts, _segCrossesRect, _advancePt,
    pathCrossesObstacles, _straightApproach,
  };
}
