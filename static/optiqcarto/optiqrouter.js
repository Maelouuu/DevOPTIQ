/*
 * optiqrouter.js — Routeur de flèches « par canaux / voies » (prototype).
 *
 * Problème : router chaque flèche INDÉPENDAMMENT (A* par flèche + rustines) accumule
 * de petites erreurs qui, à 243 flèches, deviennent un plat de spaghetti. Ici on
 * traite TOUTES les flèches ensemble, façon plan de métro :
 *   1) ports ORDONNÉS : sur chaque côté d'une forme, les flèches sont ordonnées selon
 *      leur destination → pas de croisement près de la forme ;
 *   2) routage orthogonal (A* de geometry.js, évite les formes) ;
 *   3) nudging GLOBAL : les segments parallèles proches sont rangés en VOIES nettes,
 *      ordonnées pour réduire les croisements (jamais superposés).
 *
 * Entrée : shapes [{id,x,y,w,h,type}], connections [{id,fromId,toId,...}]
 * Sortie : écrit sur chaque connexion fromPortDir/fromPortT/toPortDir/toPortT/userPts
 *          (même surface que _computeAutoLayout → rendu par renderConnections).
 *
 * Dépend de geometry.js (routeOrthogonalAStar). Aucune modif de editor.js.
 */
(function (root) {
  'use strict';

  const DEF = {
    stub: 16,        // approche droite hors du port
    lane: 13,        // écart entre deux voies parallèles
    groupTol: 30,    // deux segments parallèles à ≤ groupTol px = même canal
    overlapMin: 22,  // recouvrement min pour être dans le même faisceau
    minSeg: 18,      // longueur min d'un segment pour être nudgé
  };

  const center = s => ({ x: s.x + s.w / 2, y: s.y + s.h / 2 });

  function portPoint(s, dir, t) {
    t = (t == null ? 0.5 : t);
    const h = s.type === 'process' ? 7 : 0;
    if (dir === 'top')    return { x: s.x + s.w * t, y: s.y - h,        dir };
    if (dir === 'bottom') return { x: s.x + s.w * t, y: s.y + s.h + h,  dir };
    if (dir === 'left')   return { x: s.x - h,        y: s.y + s.h * t, dir };
    return { x: s.x + s.w + h, y: s.y + s.h * t, dir };
  }

  // ── 1) Ports ordonnés ────────────────────────────────────────────────────
  // Côté choisi par l'axe dominant ; sur chaque côté, flèches ordonnées par la
  // coordonnée perpendiculaire de l'AUTRE extrémité → attaches sans croisement local.
  function assignPorts(shapes, conns) {
    const byId = {}; shapes.forEach(s => (byId[s.id] = s));
    const bins = {};
    const push = (id, side, o) => { (bins[id + '|' + side] = bins[id + '|' + side] || []).push(o); };
    for (const c of conns) {
      const a = byId[c.fromId], b = byId[c.toId];
      if (!a || !b || c.fromId === c.toId) { c._skip = true; continue; }
      c._skip = false;
      const ac = center(a), bc = center(b);
      const dx = bc.x - ac.x, dy = bc.y - ac.y;
      let fs, ts;
      if (Math.abs(dx) >= Math.abs(dy)) { fs = dx >= 0 ? 'right' : 'left'; ts = dx >= 0 ? 'left' : 'right'; }
      else { fs = dy >= 0 ? 'bottom' : 'top'; ts = dy >= 0 ? 'top' : 'bottom'; }
      c.fromPortDir = fs; c.toPortDir = ts;
      const fkey = (fs === 'left' || fs === 'right') ? bc.y : bc.x;
      const tkey = (ts === 'left' || ts === 'right') ? ac.y : ac.x;
      push(c.fromId, fs, { c, end: 'from', key: fkey });
      push(c.toId, ts, { c, end: 'to', key: tkey });
    }
    for (const k in bins) {
      const arr = bins[k]; arr.sort((a, b) => a.key - b.key);
      const n = arr.length;
      arr.forEach((o, i) => { const t = (i + 1) / (n + 1); if (o.end === 'from') o.c.fromPortT = t; else o.c.toPortT = t; });
    }
  }

  // ── 2) Routage orthogonal (A* partagé, évite les formes) ──────────────────
  function routeArrows(shapes, conns) {
    const byId = {}; shapes.forEach(s => (byId[s.id] = s));
    const obstacles = shapes.map(s => ({ x: s.x, y: s.y, w: s.w, h: s.h, id: s.id }));
    for (const c of conns) {
      if (c._skip) continue;
      const a = byId[c.fromId], b = byId[c.toId];
      const fp = portPoint(a, c.fromPortDir, c.fromPortT);
      const tp = portPoint(b, c.toPortDir, c.toPortT);
      const obs = [];
      for (const o of obstacles) {
        if (o.id === c.fromId || o.id === c.toId) continue;
        const s = byId[o.id];
        if (s.type === 'decision') obs.push({ x: o.x + o.w * 0.22, y: o.y + o.h * 0.22, w: o.w * 0.56, h: o.h * 0.56 });
        else obs.push(o);
      }
      let pts = null;
      try { pts = routeOrthogonalAStar(fp, tp, obs); } catch (_) {}
      if (!pts) { try { pts = routeOrthogonalAStar(fp, tp, obs, { nodeCap: 90000 }); } catch (_) {} }
      if (!pts || pts.length < 2) pts = [{ x: fp.x, y: fp.y }, { x: tp.x, y: tp.y }];
      c._route = pts.map(p => ({ x: p.x, y: p.y }));
    }
  }

  // ── 3) Nudging global : segments parallèles → voies nettes ────────────────
  function globalNudge(conns, opt) {
    const segs = [];
    for (const c of conns) {
      const pts = c._route; if (!pts || pts.length < 3) continue;
      // segments INTÉRIEURS uniquement (on ne bouge pas les stubs collés aux ports)
      for (let i = 1; i <= pts.length - 3; i++) {
        const a = pts[i], b = pts[i + 1];
        const isH = Math.abs(a.y - b.y) < 1.5, isV = Math.abs(a.x - b.x) < 1.5;
        if (!isH && !isV) continue;
        const len = isH ? Math.abs(b.x - a.x) : Math.abs(b.y - a.y);
        if (len < opt.minSeg) continue;
        segs.push({ pts, i, isH,
          coord: isH ? a.y : a.x,
          lo: isH ? Math.min(a.x, b.x) : Math.min(a.y, b.y),
          hi: isH ? Math.max(a.x, b.x) : Math.max(a.y, b.y) });
      }
    }
    const used = new Array(segs.length).fill(false);
    for (let i = 0; i < segs.length; i++) {
      if (used[i]) continue;
      const bundle = [segs[i]]; used[i] = true;
      for (let j = i + 1; j < segs.length; j++) {
        if (used[j]) continue;
        const t = segs[j];
        if (t.isH !== segs[i].isH || Math.abs(t.coord - segs[i].coord) > opt.groupTol) continue;
        if (bundle.some(m => Math.min(m.hi, t.hi) - Math.max(m.lo, t.lo) > opt.overlapMin)) { bundle.push(t); used[j] = true; }
      }
      if (bundle.length < 2) continue;
      // ordre des voies = par la position perpendiculaire des VOISINS (réduit les croisements)
      bundle.sort((a, b) => laneKey(a) - laneKey(b));
      const base = bundle.reduce((s, x) => s + x.coord, 0) / bundle.length;
      const n = bundle.length;
      bundle.forEach((seg, rank) => {
        const nc = base + (rank - (n - 1) / 2) * opt.lane;
        if (seg.isH) { seg.pts[seg.i].y = nc; seg.pts[seg.i + 1].y = nc; }
        else { seg.pts[seg.i].x = nc; seg.pts[seg.i + 1].x = nc; }
      });
    }
    // reporte _route → userPts
    for (const c of conns) {
      if (c._skip) continue;
      const p = c._route;
      c.userPts = (p && p.length > 2) ? p.slice(1, -1).map(q => ({ x: q.x, y: q.y })) : null;
    }
  }

  // Clé d'ordre d'une voie : moyenne des coords perpendiculaires des points voisins
  // (là d'où le segment vient et où il va). Segments « plus à gauche/haut » → voie basse.
  function laneKey(seg) {
    const pts = seg.pts, i = seg.i;
    const before = pts[i - 1], after = pts[i + 2] || pts[i + 1];
    if (seg.isH) return ((before ? before.x : pts[i].x) + (after ? after.x : pts[i + 1].x)) / 2;
    return ((before ? before.y : pts[i].y) + (after ? after.y : pts[i + 1].y)) / 2;
  }

  function routeAll(shapes, conns, options) {
    const opt = Object.assign({}, DEF, options || {});
    assignPorts(shapes, conns);
    routeArrows(shapes, conns);
    globalNudge(conns, opt);
  }

  const api = { routeAll, assignPorts };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.OptiqRouter = api;
})(typeof window !== 'undefined' ? window : globalThis);
