/* ============================================================================
   OptiqFluent — Test Panel  ·  Shared client logic
   - TP.run(scope)        live test-execution drawer (structured, not raw term)
   - TP.lineChart(...)    success-rate SVG line chart
   - TP.escapeHtml(...)
   ========================================================================== */
(function () {
  const TP = {};
  window.TP = TP;

  TP.escapeHtml = function (s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  };

  /* ── Live run drawer ─────────────────────────────────────────────────── */
  let evt = null;

  function el(id) { return document.getElementById(id); }

  function ensureDrawer() {
    if (el('tp-run-overlay')) return;
    const ov = document.createElement('div');
    ov.className = 'run-overlay';
    ov.id = 'tp-run-overlay';
    ov.innerHTML = `
      <div class="run-panel" role="dialog" aria-modal="true">
        <div class="run-top">
          <i class="fa-solid fa-flask-vial" style="color:var(--pink)"></i>
          <h3 id="tp-run-title">Exécution des tests</h3>
          <button class="x" id="tp-run-close" aria-label="Fermer">&times;</button>
        </div>
        <div class="run-prog">
          <div class="pbar"><span id="tp-run-bar"></span></div>
          <div class="pmeta">
            <span class="k ok"><i class="fa-solid fa-check"></i> <span id="tp-run-pass">0</span></span>
            <span class="k ko"><i class="fa-solid fa-xmark"></i> <span id="tp-run-fail">0</span></span>
            <span class="k sk"><i class="fa-solid fa-forward"></i> <span id="tp-run-skip">0</span></span>
            <span class="k tot">Progression <span id="tp-run-pct">0</span>%</span>
          </div>
        </div>
        <div class="run-live" id="tp-run-live"></div>
        <div class="run-summary" id="tp-run-summary"></div>
        <div class="run-foot">
          <details>
            <summary><i class="fa-solid fa-terminal"></i>&nbsp; Sortie brute (pytest)</summary>
            <div class="run-term" id="tp-run-term"></div>
          </details>
        </div>
      </div>`;
    document.body.appendChild(ov);
    el('tp-run-close').addEventListener('click', closeDrawer);
    ov.addEventListener('click', (e) => { if (e.target === ov) closeDrawer(); });
  }

  function closeDrawer() {
    if (evt) { evt.close(); evt = null; }
    const ov = el('tp-run-overlay');
    if (ov) ov.classList.remove('open');
    document.body.style.overflow = '';
  }

  TP.run = function (scope, label) {
    ensureDrawer();
    const ov = el('tp-run-overlay');
    ov.classList.add('open');
    document.body.style.overflow = 'hidden';
    el('tp-run-title').textContent = label || 'Exécution des tests';
    el('tp-run-live').innerHTML = '';
    el('tp-run-term').innerHTML = '';
    el('tp-run-summary').className = 'run-summary';
    el('tp-run-summary').innerHTML = '';
    let pass = 0, fail = 0, skip = 0;
    el('tp-run-pass').textContent = '0';
    el('tp-run-fail').textContent = '0';
    el('tp-run-skip').textContent = '0';
    el('tp-run-pct').textContent = '0';
    el('tp-run-bar').style.width = '0%';

    let url = '/testpanel/run/all';
    if (scope.startsWith('page:')) url = '/testpanel/run/page/' + scope.slice(5);
    else if (scope.startsWith('case:')) url = '/testpanel/run/case/' + scope.slice(5);

    fetch(url, { method: 'POST' })
      .then(r => r.json())
      .then(d => stream(d.run_id))
      .catch(() => { el('tp-run-live').innerHTML = '<div class="empty">Impossible de lancer le run.</div>'; });

    const RX = /^(tests\/\S+?)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b/;
    const PCT = /\[\s*(\d+)%\]/;

    function stream(runId) {
      const live = el('tp-run-live');
      const term = el('tp-run-term');
      if (evt) evt.close();
      evt = new EventSource('/testpanel/stream/' + runId);
      evt.onmessage = function (e) {
        const line = JSON.parse(e.data);
        if (line === '[DONE]') { evt.close(); evt = null; finish(runId, pass, fail, skip); return; }

        // raw terminal
        const tl = document.createElement('div');
        tl.className = line.includes('PASSED') ? 'l-pass'
          : (line.includes('FAILED') || line.includes('ERROR')) ? 'l-fail'
          : line.startsWith('$') ? 'l-dim' : '';
        tl.textContent = line;
        term.appendChild(tl);
        term.scrollTop = term.scrollHeight;

        // structured parse
        const m = line.match(RX);
        if (m) {
          const node = m[1], status = m[2];
          const short = node.split('::').slice(1).join(' › ') || node;
          let cls = 'pass', ic = 'fa-circle-check';
          if (status === 'FAILED' || status === 'ERROR') { cls = 'fail'; ic = 'fa-circle-xmark'; fail++; }
          else if (status === 'SKIPPED' || status === 'XFAIL') { cls = 'skip'; ic = 'fa-circle-minus'; skip++; }
          else { pass++; }
          const row = document.createElement('div');
          row.className = 'live-row ' + cls;
          row.innerHTML = '<span class="ic"><i class="fa-solid ' + ic + '"></i></span>'
            + '<span class="nm">' + TP.escapeHtml(short) + '</span>'
            + '<span class="badge b-' + (cls === 'pass' ? 'pass' : cls === 'fail' ? 'fail' : 'amber') + '">' + status + '</span>';
          live.appendChild(row);
          live.scrollTop = live.scrollHeight;
          el('tp-run-pass').textContent = pass;
          el('tp-run-fail').textContent = fail;
          el('tp-run-skip').textContent = skip;
        }
        const pm = line.match(PCT);
        if (pm) { el('tp-run-bar').style.width = pm[1] + '%'; el('tp-run-pct').textContent = pm[1]; }
      };
      evt.onerror = function () { /* keep open; server may still be writing */ };
    }

    function finish(runId, p, f, s) {
      el('tp-run-bar').style.width = '100%';
      el('tp-run-pct').textContent = '100';
      fetch('/testpanel/run/' + runId + '/status').then(r => r.json()).then(d => {
        const total = d.total != null ? d.total : (p + f + s);
        const pct = d.pct != null ? d.pct : (total ? Math.round(100 * p / total) : 0);
        const ok = (d.passed != null ? d.total - d.passed : f) === 0;
        const sum = el('tp-run-summary');
        sum.className = 'run-summary show' + (ok ? '' : ' ko');
        sum.innerHTML = '<i class="fa-solid ' + (ok ? 'fa-circle-check' : 'fa-triangle-exclamation') + '" style="font-size:18px"></i>'
          + '<b>' + (ok ? 'Tous les tests passent' : (d.total - d.passed) + ' test(s) en échec') + '</b>'
          + '<span class="muted">· ' + (d.passed != null ? d.passed : p) + '/' + total + ' · ' + pct + '%</span>'
          + '<button class="btn btn-pink btn-sm" style="margin-left:auto" onclick="location.reload()">'
          + '<i class="fa-solid fa-rotate"></i> Rafraîchir le panel</button>';
      }).catch(() => {});
    }
  };

  /* ── Success-rate line chart (SVG) ───────────────────────────────────── */
  TP.lineChart = function (container, points, opts) {
    opts = opts || {};
    if (!points || !points.length) {
      container.innerHTML = '<div class="empty">Aucun run sur cette période</div>';
      return;
    }
    const W = Math.max(320, container.clientWidth || 680), H = opts.height || 220;
    const PAD = { t: 18, r: 56, b: 30, l: 38 };
    const cw = W - PAD.l - PAD.r, ch = H - PAD.t - PAD.b, n = points.length;
    const xs = points.map((_, i) => PAD.l + (n === 1 ? cw / 2 : i * cw / (n - 1)));
    const ys = points.map(p => PAD.t + ch - (p.pct / 100) * ch);
    const line = xs.map((x, i) => (i ? 'L' : 'M') + x.toFixed(1) + ',' + ys[i].toFixed(1)).join(' ');
    const fill = line + ' L' + xs[n - 1].toFixed(1) + ',' + (PAD.t + ch) + ' L' + PAD.l + ',' + (PAD.t + ch) + ' Z';
    let grid = '';
    [0, 25, 50, 75, 100].forEach(v => {
      const y = (PAD.t + ch - v / 100 * ch).toFixed(1);
      grid += '<line x1="' + PAD.l + '" y1="' + y + '" x2="' + (PAD.l + cw) + '" y2="' + y + '" stroke="#eef0f5"/>'
        + '<text x="' + (PAD.l - 8) + '" y="' + (+y + 4) + '" text-anchor="end" font-size="10" fill="#94a3b8">' + v + '</text>';
    });
    const step = Math.max(1, Math.ceil(n / 7));
    let xlab = '';
    points.forEach((p, i) => {
      if (i % step && i !== n - 1) return;
      xlab += '<text x="' + xs[i].toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="10" fill="#94a3b8">' + TP.escapeHtml(p.t) + '</text>';
    });
    const dots = points.map((p, i) => {
      const c = p.pct >= 95 ? '#16a34a' : p.pct >= 75 ? '#d97706' : '#dc2626';
      const counts = (p.passed != null && p.total != null) ? ' (' + p.passed + '/' + p.total + ')' : '';
      return '<circle cx="' + xs[i].toFixed(1) + '" cy="' + ys[i].toFixed(1) + '" r="4" fill="' + c + '" stroke="#fff" stroke-width="2"><title>'
        + TP.escapeHtml(p.t) + ' — ' + p.pct + '%' + counts + '</title></circle>';
    }).join('');
    container.innerHTML = '<svg width="' + W + '" height="' + H + '" style="display:block;overflow:visible">'
      + '<defs><linearGradient id="tpg" x1="0" y1="0" x2="0" y2="1">'
      + '<stop offset="0%" stop-color="rgba(236,72,153,.18)"/><stop offset="100%" stop-color="rgba(236,72,153,0)"/></linearGradient></defs>'
      + grid
      + '<path d="' + fill + '" fill="url(#tpg)"/>'
      + '<path d="' + line + '" fill="none" stroke="#ec4899" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
      + dots + xlab + '</svg>';
  };
})();
