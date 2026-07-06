// Web Worker : exécute le routage libavoid HORS du thread principal → l'UI ne
// gèle jamais pendant le calcul (le thread principal peut animer un spinner et
// imposer un timeout). Reçoit {id, nodesById, connections}, renvoie {id, results}.
import { AvoidLib } from './libavoid.mjs';

let A = null, loading = null;
function ensure() {
  if (A) return Promise.resolve(A);
  if (!loading) {
    const wasmUrl = new URL('./libavoid.wasm', import.meta.url).href;
    loading = AvoidLib.load(wasmUrl).then(() => { A = AvoidLib.getInstance(); return A; });
  }
  return loading;
}

// ── Routage (identique à l'adaptateur principal) ───────────────────────────
// N.B. libavoid est réservé aux cartos ≤ ~120 flèches (le coût est super-linéaire
// en nombre de flèches) ; au-delà, l'éditeur bascule sur le routeur interne.
function routeAll(A, nodesById, connections) {
  const RP = A.RoutingParameter, RO = A.RoutingOption;
  const ORTHO = A.RouterFlag.OrthogonalRouting.value;
  const router = new A.Router(ORTHO);
  router.setRoutingParameter(RP.shapeBufferDistance, 12);
  router.setRoutingParameter(RP.idealNudgingDistance, 18);
  router.setRoutingParameter(RP.segmentPenalty, 250);
  router.setRoutingParameter(RP.anglePenalty, 250);
  router.setRoutingParameter(RP.crossingPenalty, 600);
  router.setRoutingParameter(RP.fixedSharedPathPenalty, 200);
  router.setRoutingOption(RO.nudgeOrthogonalSegmentsConnectedToShapes, true);
  router.setRoutingOption(RO.nudgeOrthogonalTouchingColinearSegments, true);
  router.setRoutingOption(RO.nudgeSharedPathsWithCommonEndPoint, true);
  router.setRoutingOption(RO.performUnifyingNudgingPreprocessingStep, true);

  const pool = [];
  const P = (x, y) => { const p = new A.Point(x, y); pool.push(p); return p; };
  const rectPoly = (x, y, w, h) => { const r = new A.Rectangle(P(x, y), P(x + w, y + h)); pool.push(r); return r; };

  const shapeRefs = {};
  for (const id in nodesById) {
    const n = nodesById[id];
    if (!(n.w > 0) || !(n.h > 0)) continue; // ignore les formes dégénérées
    const sr = new A.ShapeRef(router, rectPoly(n.x, n.y, n.w, n.h));
    if (n.type === 'decision') {
      const tips = [[0.5, 0, 1], [0.5, 1, 2], [0, 0.5, 4], [1, 0.5, 8]];
      for (const [xo, yo, d] of tips) { const pin = new A.ShapeConnectionPin(sr, 1, xo, yo, true, 0, d); pin.setExclusive(false); }
    } else {
      const pin = new A.ShapeConnectionPin(sr, 1, 0.5, 0.5, true, 0, 15); pin.setExclusive(false);
    }
    shapeRefs[id] = sr;
  }

  const conns = [];
  for (const c of connections) {
    if (c.fromId === c.toId || !shapeRefs[c.fromId] || !shapeRefs[c.toId]) continue;
    const ce1 = new A.ConnEnd(shapeRefs[c.fromId], 1); pool.push(ce1);
    const ce2 = new A.ConnEnd(shapeRefs[c.toId], 1); pool.push(ce2);
    const cr = new A.ConnRef(router, ce1, ce2);
    conns.push({ connId: c.id, cr, from: nodesById[c.fromId], to: nodesById[c.toId] });
  }

  router.processTransaction();

  function endInfo(node, p0, p1) {
    const w = node.w || 1, h = node.h || 1;
    const dx = p1.x - p0.x, dy = p1.y - p0.y;
    let dir;
    if (Math.abs(dx) >= Math.abs(dy)) dir = dx >= 0 ? 'right' : 'left';
    else dir = dy >= 0 ? 'bottom' : 'top';
    let t;
    if (dir === 'right' || dir === 'left') t = (p1.y - node.y) / h;
    else t = (p1.x - node.x) / w;
    return { dir, t: Math.max(0, Math.min(1, t)) };
  }
  function snapDecisionEnd(pts, node, atStart) {
    const dir = atStart ? endInfo(node, pts[0], pts[1]).dir
                        : endInfo(node, pts[pts.length - 1], pts[pts.length - 2]).dir;
    const cx = node.x + node.w / 2, cy = node.y + node.h / 2;
    let tip;
    if (dir === 'left')       tip = { x: node.x, y: cy };
    else if (dir === 'right') tip = { x: node.x + node.w, y: cy };
    else if (dir === 'top')   tip = { x: cx, y: node.y };
    else                      tip = { x: cx, y: node.y + node.h };
    const horiz = dir === 'left' || dir === 'right';
    const endIdx = atStart ? 0 : pts.length - 1;
    const nbrIdx = atStart ? 1 : pts.length - 2;
    if (horiz) pts[nbrIdx].y = tip.y; else pts[nbrIdx].x = tip.x;
    pts[endIdx] = { x: tip.x, y: tip.y };
  }

  const results = [];
  for (const { connId, cr, from, to } of conns) {
    const pl = cr.displayRoute();
    const pts = [];
    for (let i = 0; i < pl.size(); i++) { const pt = pl.at(i); pts.push({ x: pt.x, y: pt.y }); }
    if (pts.length < 2) continue;
    if (from.type === 'decision') snapDecisionEnd(pts, from, true);
    if (to.type === 'decision')   snapDecisionEnd(pts, to, false);
    const fi = endInfo(from, pts[0], pts[1]);
    const ti = endInfo(to, pts[pts.length - 1], pts[pts.length - 2]);
    const mids = pts.slice(1, -1).map(p => ({ x: p.x, y: p.y }));
    results.push({ connId, fromDir: fi.dir, fromT: fi.t, toDir: ti.dir, toT: ti.t, userPts: mids.length ? mids : null });
  }

  try { router.delete(); } catch (_) {}
  for (const h of pool) { try { h.delete(); } catch (_) {} }
  return results;
}

onmessage = async (e) => {
  const { id, nodesById, connections } = e.data || {};
  try {
    const lib = await ensure();
    const t0 = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const results = routeAll(lib, nodesById, connections);
    const t1 = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    postMessage({ id, ok: true, results, timing: Math.round(t1 - t0) });
  } catch (err) {
    postMessage({ id, ok: false, error: String((err && err.message) || err) });
  }
};
