/* debug_decisions.js — Diagnostic losanges : drop VSDX → 3 analyses parallèles */
(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────────
  let _file       = null;   // File object currently loaded
  let _vsdxData   = null;   // Python extractor result
  let _toolData   = null;   // VsdxImporter (JS) result
  let _aiData     = null;   // Claude/OpenAI result
  let _activeTab  = 'compare';

  // ── Init ───────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    const toggle = _id('dd-toggle-btn');
    const panel  = _id('dd-panel');
    if (!toggle || !panel) return;

    toggle.addEventListener('click', () => {
      const open = panel.classList.toggle('dd-open');
      toggle.classList.toggle('dd-toggle-active', open);
      const lbl = toggle.querySelector('.dd-toggle-label');
      if (lbl) lbl.textContent = open ? 'Fermer' : 'Ouvrir';
    });

    // Tab buttons
    document.querySelectorAll('.dd-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        _activeTab = btn.dataset.tab;
        document.querySelectorAll('.dd-tab').forEach(b =>
          b.classList.toggle('dd-tab-active', b === btn)
        );
        _renderActiveTab();
      });
    });

    // Drop zone
    _setupDropZone();

    // File input fallback
    const fileInput = _id('dd-file-input');
    if (fileInput) {
      fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) _loadFile(fileInput.files[0]);
      });
    }

    // AI button
    _id('dd-ai-btn')?.addEventListener('click', _runAI);

    // Reset button
    _id('dd-reset-btn')?.addEventListener('click', _resetAll);
  });

  // ── Drop zone ──────────────────────────────────────────────────────────
  function _setupDropZone() {
    const zone = _id('dd-dropzone');
    if (!zone) return;

    zone.addEventListener('dragover', e => {
      e.preventDefault();
      zone.classList.add('dd-dz-over');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('dd-dz-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('dd-dz-over');
      const file = e.dataTransfer.files[0];
      if (file) _loadFile(file);
    });
    zone.addEventListener('click', () => _id('dd-file-input')?.click());
  }

  // ── Load file ──────────────────────────────────────────────────────────
  function _loadFile(file) {
    if (!file.name.toLowerCase().endsWith('.vsdx')) {
      _setStatus('Le fichier doit être un .vsdx', true);
      return;
    }
    _file = file;
    _vsdxData = null; _toolData = null; _aiData = null;

    // Show filename in drop zone
    const dz = _id('dd-dropzone');
    if (dz) {
      dz.innerHTML = `<span class="dd-dz-loaded">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="#22c55e"><path d="M8 1L15 8L8 15L1 8Z"/></svg>
        <strong>${_esc(file.name)}</strong>
        <span class="dd-dz-size">${(file.size / 1024).toFixed(1)} Ko</span>
      </span>`;
    }

    // Open panel if closed
    const panel = _id('dd-panel');
    const toggle = _id('dd-toggle-btn');
    if (panel && !panel.classList.contains('dd-open')) {
      panel.classList.add('dd-open');
      toggle?.classList.add('dd-toggle-active');
      const lbl = toggle?.querySelector('.dd-toggle-label');
      if (lbl) lbl.textContent = 'Fermer';
    }

    _runAllAnalyses();
  }

  // ── Run all analyses ───────────────────────────────────────────────────
  async function _runAllAnalyses() {
    _setStatus('Analyse en cours…');
    _id('dd-score')?.replaceChildren();
    _id('dd-tab-content').innerHTML = '<p class="dd-empty">Analyse en cours…</p>';

    // Run Python extractor + JS importer in parallel
    const [vsdxResult, toolResult] = await Promise.all([
      _runPythonExtractor(),
      _runJsImporter(),
    ]);

    _vsdxData = vsdxResult;
    _toolData = toolResult;

    _clearStatus();
    _renderScore();
    _renderActiveTab();
  }

  // ── Python extractor (backend) ─────────────────────────────────────────
  async function _runPythonExtractor() {
    try {
      const fd = new FormData();
      fd.append('vsdx', _file);
      const res = await fetch('/activities/api/debug-decisions/analyze-file', {
        method: 'POST', body: fd
      });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      return json.vsdx || { decisions: [], errors: ['Réponse inattendue'] };
    } catch (e) {
      return { decisions: [], errors: [e.message], total_shapes: 0, total_connectors: 0 };
    }
  }

  // ── JS importer (VsdxImporter) ─────────────────────────────────────────
  async function _runJsImporter() {
    try {
      if (typeof VsdxImporter === 'undefined') {
        return { decisions: [], errors: ['VsdxImporter non disponible'], total_shapes: 0 };
      }

      const arrayBuffer = await _file.arrayBuffer();
      const zip = await JSZip.loadAsync(arrayBuffer);
      const importer = new VsdxImporter(zip);

      // parse() with a no-op orphan handler
      const result = await importer.parse(() => Promise.resolve('keep'));
      if (!result) return { decisions: [], errors: ['Import annulé'], total_shapes: 0 };

      const { shapes = [], connections = [] } = result;
      const decisionShapes = shapes.filter(s => s._type === 'decision' || s.type === 'decision');
      const shapeById = {};
      shapes.forEach(s => { shapeById[s.id] = s; });

      const decisions = decisionShapes.map(d => {
        const outgoing = connections
          .filter(c => c.fromId === d.id)
          .map(c => ({
            conn_id: c.id || '',
            to_id:   c.toId  || '',
            to_label: (shapeById[c.toId] || {}).label || '',
            conn_label: c.label || '',
            badge: c.label || '',
          }));
        const incoming = connections
          .filter(c => c.toId === d.id)
          .map(c => ({
            conn_id:    c.id || '',
            from_id:    c.fromId || '',
            from_label: (shapeById[c.fromId] || {}).label || '',
            conn_label: c.label || '',
            badge: '',
          }));
        return {
          id:    d.id,
          label: d.label || '',
          outgoing,
          incoming,
        };
      });

      return {
        decisions,
        total_shapes:      shapes.length,
        total_connections: connections.length,
        errors: [],
      };
    } catch (e) {
      return { decisions: [], errors: [e.message], total_shapes: 0 };
    }
  }

  // ── AI analysis ────────────────────────────────────────────────────────
  async function _runAI() {
    if (!_file) {
      _setStatus('Déposez d\'abord un fichier VSDX.', true);
      return;
    }
    const btn = _id('dd-ai-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Analyse IA…'; }

    try {
      const fd = new FormData();
      fd.append('vsdx', _file);
      const res = await fetch('/activities/api/debug-decisions/analyze-file/ai', {
        method: 'POST', body: fd
      });
      const json = await res.json();
      if (json.error) throw new Error(json.error);
      _aiData = json.data || { decisions: [] };
      _aiData._source = json.source || 'ia';

      // Switch to AI tab
      document.querySelector('.dd-tab[data-tab="ai"]')?.click();
    } catch (e) {
      _setStatus('IA : ' + e.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '✦ Analyse IA'; }
    }
  }

  // ── Reset ──────────────────────────────────────────────────────────────
  function _resetAll() {
    _file = null; _vsdxData = null; _toolData = null; _aiData = null;
    const dz = _id('dd-dropzone');
    if (dz) {
      dz.innerHTML = `
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" class="dd-dz-icon">
          <path d="M14 2L26 14L14 26L2 14Z" stroke="#9ca3af" stroke-width="1.8" fill="none"/>
        </svg>
        <span class="dd-dz-hint">Déposez votre fichier <strong>.vsdx</strong> ici</span>
        <span class="dd-dz-or">ou <span class="dd-dz-browse">choisissez un fichier</span></span>`;
    }
    _id('dd-score')?.replaceChildren();
    _id('dd-tab-content').innerHTML = '<p class="dd-empty">Déposez un fichier VSDX pour démarrer l\'analyse.</p>';
    _clearStatus();
  }

  // ── Score ──────────────────────────────────────────────────────────────
  function _renderScore() {
    const el = _id('dd-score');
    if (!el) return;

    const vDec = (_vsdxData?.decisions) || [];
    const tDec = (_toolData?.decisions) || [];

    if (vDec.length === 0 && tDec.length === 0) {
      el.innerHTML = '<span class="dd-score-grey">Aucun losange détecté dans les deux sources.</span>';
      return;
    }

    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');
    const vLabels = new Set(vDec.map(d => norm(d.label)));
    const tLabels = new Set(tDec.map(d => norm(d.label)));
    const matched = [...vLabels].filter(l => tLabels.has(l)).length;
    const total = Math.max(vDec.length, tDec.length);

    let vBadged = 0, tBadged = 0;
    vDec.forEach(d => d.outgoing.forEach(c => { if (c.badge) vBadged++; }));
    tDec.forEach(d => d.outgoing.forEach(c => { if (c.badge) tBadged++; }));

    const shapeScore = total > 0 ? Math.round(matched / total * 100) : 100;
    const badgeScore = vBadged > 0 ? Math.round(Math.min(tBadged, vBadged) / vBadged * 100) : (tBadged === 0 ? 100 : 0);
    const globalScore = Math.round((shapeScore + badgeScore) / 2);
    const color = globalScore === 100 ? '#22c55e' : globalScore >= 70 ? '#f59e0b' : '#ef4444';

    el.innerHTML = `
      <div class="dd-score-grid">
        <div class="dd-score-item">
          <span class="dd-score-num" style="color:${color}">${globalScore}%</span>
          <span class="dd-score-lbl">Score global<br>VSDX↔Outil</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${vDec.length}</span>
          <span class="dd-score-lbl">Losanges<br>VSDX brut</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${tDec.length}</span>
          <span class="dd-score-lbl">Losanges<br>Outil JS</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${matched}/${total}</span>
          <span class="dd-score-lbl">Labels<br>reconnus</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${vBadged} / ${tBadged}</span>
          <span class="dd-score-lbl">Badges Oui/Non<br>VSDX / Outil</span>
        </div>
        ${_vsdxData?.total_shapes ? `<div class="dd-score-item">
          <span class="dd-score-num">${_vsdxData.total_shapes}</span>
          <span class="dd-score-lbl">Formes<br>VSDX totales</span>
        </div>` : ''}
      </div>
      ${_vsdxData?.errors?.length ? `<p class="dd-errs">VSDX : ${_vsdxData.errors.join(', ')}</p>` : ''}
      ${_toolData?.errors?.length ? `<p class="dd-errs">Outil : ${_toolData.errors.join(', ')}</p>` : ''}`;
  }

  // ── Tab rendering ──────────────────────────────────────────────────────
  function _renderActiveTab() {
    switch (_activeTab) {
      case 'compare': _renderCompare(); break;
      case 'vsdx':   _renderSource(_vsdxData?.decisions, 'VSDX brut (Python)'); break;
      case 'tool':   _renderSource(_toolData?.decisions, 'Outil JS (VsdxImporter)'); break;
      case 'ai':     _renderAITab(); break;
    }
  }

  function _renderCompare() {
    const el = _id('dd-tab-content');
    if (!el) return;

    const vDec = _vsdxData?.decisions || [];
    const tDec = _toolData?.decisions || [];

    if (vDec.length === 0 && tDec.length === 0) {
      el.innerHTML = '<p class="dd-empty">Aucun losange détecté. Essayez un fichier VSDX contenant des losanges.</p>';
      return;
    }

    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');
    const tByLabel = {};
    tDec.forEach(d => { tByLabel[norm(d.label)] = d; });

    // Build rows from vsdx decisions
    const rows = vDec.map(vd => {
      const td = tByLabel[norm(vd.label)];
      return { vd, td, found: !!td };
    });

    // Add tool-only decisions (not in VSDX)
    const vLabels = new Set(vDec.map(d => norm(d.label)));
    tDec.filter(td => !vLabels.has(norm(td.label))).forEach(td => {
      rows.push({ vd: null, td, found: false, toolOnly: true });
    });

    let html = `<table class="dd-table">
      <thead><tr>
        <th>Losange VSDX</th>
        <th>Losange Outil</th>
        <th>Entrées VSDX</th>
        <th>Sorties VSDX</th>
        <th>Sorties Outil</th>
      </tr></thead><tbody>`;

    for (const { vd, td, found, toolOnly } of rows) {
      const cls = toolOnly ? 'dd-row-tool-only' : (!found ? 'dd-row-miss' : '');

      const vLabel = vd ? (_esc(vd.label) || '<em>sans label</em>') : '—';
      const tLabel = td ? (_esc(td.label) || '<em>sans label</em>') : `<span class="dd-miss">Non trouvé</span>`;

      const vIns = vd ? _connChips(vd.incoming, 'from_label') : '';
      const vOuts = vd ? _connChips(vd.outgoing, 'to_label') : '';
      const tOuts = td ? _connChips(td.outgoing, 'to_label') : '<span class="dd-miss">—</span>';

      html += `<tr class="${cls}">
        <td>${toolOnly ? '<span class="dd-miss">—</span>' : vLabel}</td>
        <td>${toolOnly ? `<span class="dd-tag-tool">${_esc(td.label)}</span>` : tLabel}</td>
        <td>${vIns || '—'}</td>
        <td>${vOuts || '—'}</td>
        <td>${tOuts}</td>
      </tr>`;
    }

    html += '</tbody></table>';

    if (rows.length === 0) {
      html = '<p class="dd-empty">Aucun losange dans les données.</p>';
    }

    el.innerHTML = html;
  }

  function _renderSource(decisions, srcName) {
    const el = _id('dd-tab-content');
    if (!el) return;
    if (!decisions || decisions.length === 0) {
      el.innerHTML = `<p class="dd-empty">Aucun losange dans « ${_esc(srcName)} ».</p>`;
      return;
    }

    let html = `<table class="dd-table">
      <thead><tr>
        <th>Losange</th><th>Entrées</th><th>Sorties</th>
      </tr></thead><tbody>`;

    for (const d of decisions) {
      const ins  = _connChips(d.incoming, 'from_label') || '—';
      const outs = _connChips(d.outgoing, 'to_label')   || '—';
      html += `<tr>
        <td>${_esc(d.label) || '<em>sans label</em>'}</td>
        <td>${ins}</td>
        <td>${outs}</td>
      </tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
  }

  function _renderAITab() {
    const el = _id('dd-tab-content');
    if (!el) return;
    if (!_aiData) {
      el.innerHTML = `<p class="dd-empty">Cliquez sur <strong>Analyse IA</strong> après avoir chargé un fichier VSDX.</p>`;
      return;
    }
    const src = _aiData._source ? ` <span class="dd-src-badge">${_aiData._source}</span>` : '';
    el.innerHTML = `<p class="dd-ai-header">Résultat IA${src}</p>`;
    _renderSource(_aiData.decisions, 'IA');
    // Append after renderSource rewrites innerHTML - use append instead
    const hdr = document.createElement('p');
    hdr.className = 'dd-ai-header';
    hdr.innerHTML = `Résultat IA${src}`;
    el.prepend(hdr);
  }

  // ── Helpers ────────────────────────────────────────────────────────────
  function _connChips(list, labelKey) {
    if (!list || !list.length) return '';
    return list.map(c => {
      const badge = c.badge ? `<em>${_esc(c.badge)}</em>` : '';
      return `<span class="dd-conn ${c.badge ? 'dd-badge-yes' : ''}">${_esc(c[labelKey] || c.conn_id || '?')}${badge}</span>`;
    }).join('');
  }

  function _setStatus(msg, error = false) {
    const el = _id('dd-status');
    if (!el) return;
    el.textContent = msg;
    el.className = 'dd-status' + (error ? ' dd-status-err' : '');
    el.style.display = '';
  }
  function _clearStatus() {
    const el = _id('dd-status');
    if (el) el.style.display = 'none';
  }
  function _id(id) { return document.getElementById(id); }
  function _esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
})();
