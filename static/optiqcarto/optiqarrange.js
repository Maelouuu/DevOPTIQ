/*
 * optiqarrange.js — Agencement automatique « à grande liberté », contraint aux bandes.
 *
 * Le bouton « Agencement auto » : on RÉ-ORDONNE librement les formes (X et rang), mais
 * chaque forme reste DANS SA BANDE d'origine (Y contraint à la bande), garde ses données
 * et ses connexions. Objectif : flux gauche→droite lisible, sans chevauchement.
 *
 * Algorithme (layered / Sugiyama contraint bandes) :
 *   1) casse les cycles (DFS) → DAG « avant » + liste des flèches RETOUR ;
 *   2) rang (colonne) = plus-long-chemin sur le DAG, puis resserrement (arêtes courtes) ;
 *   3) dans chaque bande, ordre des formes par barycentre des voisins (réduit les
 *      croisements), empilées en rangées SANS chevauchement ;
 *   4) coordonnées : X = colonne, Y = bande + rangée.
 *
 * Sortie : { pos: Map(id → {x,y,rank}), backEdges: Set("from|to"), ranks: Map(id→rank) }.
 * Le routage (dont les flèches retour par un canal dédié) est fait ensuite côté éditeur.
 */
(function (root) {
  'use strict';

  const DEF = { colGap: 90, rowGap: 42, bandPad: 26, tightenPasses: 8, orderPasses: 6 };

  const cx = s => s.x + s.w / 2;

  function bandRanges(bands, y0) {
    let y = (y0 == null ? -200 : y0); const r = [];
    for (const b of bands) { if (b && b.deleted) continue; const h = b.height || 200; r.push({ id: b.id, y0: y, y1: y + h, h }); y += h; }
    return r;
  }
  function bandOf(s, ranges) {
    const mid = s.y + s.h / 2;
    for (const r of ranges) if (mid >= r.y0 && mid < r.y1) return r;
    return ranges.length ? (mid < ranges[0].y0 ? ranges[0] : ranges[ranges.length - 1]) : null;
  }

  function buildAdj(shapes, conns) {
    const ids = new Set(shapes.map(s => s.id));
    const out = new Map(), inc = new Map();
    shapes.forEach(s => { out.set(s.id, []); inc.set(s.id, []); });
    for (const c of conns) {
      if (!ids.has(c.fromId) || !ids.has(c.toId) || c.fromId === c.toId) continue;
      out.get(c.fromId).push(c.toId); inc.get(c.toId).push(c.fromId);
    }
    return { out, inc };
  }

  // DFS itératif : back-edge = arête vers un nœud GRIS (sur la pile). Renvoie {keep, back}.
  function breakCycles(shapes, out) {
    const W = 0, G = 1, B = 2, color = new Map(shapes.map(s => [s.id, W]));
    const keep = [], back = new Set();
    for (const s of shapes) {
      if (color.get(s.id) !== W) continue;
      const st = [[s.id, 0]]; color.set(s.id, G);
      while (st.length) {
        const fr = st[st.length - 1], node = fr[0], kids = out.get(node);
        if (fr[1] < kids.length) {
          const to = kids[fr[1]++], c2 = color.get(to);
          if (c2 === W) { keep.push([node, to]); color.set(to, G); st.push([to, 0]); }
          else if (c2 === B) keep.push([node, to]);
          else back.add(node + '|' + to);            // back-edge (cycle)
        } else { color.set(node, B); st.pop(); }
      }
    }
    return { keep, back };
  }

  function longestPath(shapes, keep) {
    const indeg = new Map(shapes.map(s => [s.id, 0])), adj = new Map(shapes.map(s => [s.id, []]));
    for (const [f, t] of keep) { adj.get(f).push(t); indeg.set(t, indeg.get(t) + 1); }
    const rank = new Map(shapes.map(s => [s.id, 0])), q = [];
    for (const s of shapes) if (indeg.get(s.id) === 0) q.push(s.id);
    let qi = 0;
    while (qi < q.length) { const u = q[qi++]; for (const v of adj.get(u)) { if (rank.get(v) < rank.get(u) + 1) rank.set(v, rank.get(u) + 1); indeg.set(v, indeg.get(v) - 1); if (indeg.get(v) === 0) q.push(v); } }
    return rank;
  }

  // Resserre les rangs : chaque nœud tiré vers la médiane de ses voisins (DAG), borné par
  // max(pred)+1 et min(succ)-1 → arêtes courtes, colonnes compactes.
  function tighten(shapes, keep, rank, passes) {
    const preds = new Map(shapes.map(s => [s.id, []])), succs = new Map(shapes.map(s => [s.id, []]));
    for (const [f, t] of keep) { succs.get(f).push(t); preds.get(t).push(f); }
    const median = a => { if (!a.length) return null; const b = a.slice().sort((x, y) => x - y); const m = b.length >> 1; return b.length % 2 ? b[m] : Math.round((b[m - 1] + b[m]) / 2); };
    for (let p = 0; p < passes; p++) for (const s of shapes) {
      const id = s.id;
      const lo = preds.get(id).length ? Math.max(...preds.get(id).map(u => rank.get(u))) + 1 : 0;
      const hiA = succs.get(id).map(v => rank.get(v));
      const hi = hiA.length ? Math.min(...hiA) - 1 : Infinity;
      const nb = [...preds.get(id).map(u => rank.get(u)), ...succs.get(id).map(v => rank.get(v))];
      let want = median(nb); if (want == null) continue;
      want = Math.max(lo, Math.min(hi === Infinity ? want : hi, want));
      if (want >= lo && want !== rank.get(id)) rank.set(id, want);
    }
    return rank;
  }

  function arrange(shapes, connections, bands, options) {
    const opt = Object.assign({}, DEF, options || {});
    if (!shapes.length) return { pos: new Map(), backEdges: new Set(), ranks: new Map() };
    const { out, inc } = buildAdj(shapes, connections);
    const { keep, back } = breakCycles(shapes, out);
    let rank = longestPath(shapes, keep);
    rank = tighten(shapes, keep, rank, opt.tightenPasses);

    // formes isolées : rang selon X d'origine (ne pas entasser en colonne 0)
    const conn = id => out.get(id).length || inc.get(id).length;
    const xs = shapes.map(s => s.x), minX = Math.min(...xs), maxX = Math.max(...xs);
    let maxRank = 0; for (const s of shapes) if (conn(s.id)) maxRank = Math.max(maxRank, rank.get(s.id));
    for (const s of shapes) if (!conn(s.id)) rank.set(s.id, Math.round((maxX > minX ? (s.x - minX) / (maxX - minX) : 0) * maxRank));

    // compacte la numérotation des rangs
    const usedR = [...new Set(shapes.map(s => rank.get(s.id)))].sort((a, b) => a - b);
    const remap = new Map(usedR.map((r, i) => [r, i]));
    for (const s of shapes) rank.set(s.id, remap.get(rank.get(s.id)));
    maxRank = usedR.length - 1;

    // largeur régulière de chaque colonne
    const colW = new Array(maxRank + 1).fill(0);
    for (const s of shapes) colW[rank.get(s.id)] = Math.max(colW[rank.get(s.id)], s.w);
    const colX = new Array(maxRank + 1).fill(0);
    let acc = 0; for (let r = 0; r <= maxRank; r++) { colX[r] = acc + colW[r] / 2; acc += colW[r] + opt.colGap; }

    const ranges = bandRanges(bands);
    const bandById = new Map(ranges.map(r => [r.id, r]));
    const shapeBand = new Map(); for (const s of shapes) { const b = bandOf(s, ranges); shapeBand.set(s.id, b ? b.id : null); }

    // ── Ordre vertical dans chaque bande : barycentre des voisins (réduit croisements) ──
    // position = valeur continue triée ; on itère sweeps avant/arrière.
    const posY = new Map(shapes.map(s => [s.id, s.y])); // init : Y d'origine
    const nbrs = id => [...out.get(id), ...inc.get(id)];
    for (let p = 0; p < opt.orderPasses; p++) {
      for (const s of shapes) {
        const ns = nbrs(s.id); if (!ns.length) continue;
        const m = ns.reduce((a, n) => a + posY.get(n), 0) / ns.length;
        posY.set(s.id, m); // barycentre (sera reprojeté dans la bande)
      }
    }

    // ── Placement : par bande, par rang, empilage sans chevauchement ordonné par posY ──
    const byBand = new Map();
    for (const s of shapes) { const k = shapeBand.get(s.id) ?? '_'; (byBand.get(k) || byBand.set(k, []).get(k)).push(s); }
    const pos = new Map();
    for (const [bid, arr] of byBand) {
      const band = bandById.get(bid);
      // groupe par rang
      const byRank = new Map();
      for (const s of arr) { const r = rank.get(s.id); (byRank.get(r) || byRank.set(r, []).get(r)).push(s); }
      // nombre de rangées nécessaires = max formes sur un même rang dans la bande
      let maxRows = 1; for (const [, g] of byRank) maxRows = Math.max(maxRows, g.length);
      const usable = band ? band.h - 2 * opt.bandPad : 400;
      const rowH = maxRows > 1 ? usable / maxRows : 0;
      for (const [r, g] of byRank) {
        g.sort((a, b) => posY.get(a.id) - posY.get(b.id)); // ordre vertical stable
        g.forEach((s, row) => {
          const x = colX[r] - s.w / 2;
          let y;
          if (band) {
            const center = maxRows > 1 ? band.y0 + opt.bandPad + rowH * (row + 0.5) : band.y0 + band.h / 2;
            y = center - s.h / 2;
          } else y = s.y;
          pos.set(s.id, { x, y, rank: r });
        });
      }
    }
    return { pos, backEdges: back, ranks: rank };
  }

  const api = { arrange, bandRanges };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.OptiqArrange = api;
})(typeof window !== 'undefined' ? window : globalThis);
