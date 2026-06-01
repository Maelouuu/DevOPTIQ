/* debug_decisions.js — Diagnostic losanges : drop VSDX → 3 analyses parallèles */
(function () {
  'use strict';

  // ── Ground truth (extracted manually from losange_oui_non.xlsx) ────────
  // Keys use the badge text on the arrow (lowercase), not the destination label.
  // Labeled diamonds use "diamond_label|badge" to avoid collisions; unlabeled use badge alone.
  const _GROUND_TRUTH = {
    // Standard (labeled)
    'standard|quotation to prepare': 'Oui',
    'standard|client specifications document': 'Non',
    'standard|customer requirements document linked to an invitation for tender': 'Non',

    // New Customer / Quotation (labeled)
    'new customer / quotation|customer status': 'Non',
    'new customer / quotation|credit check': 'Non',
    'new customer / quotation|credit status': 'Oui',

    // Installation Not Completed (labeled)
    'installation not completed|report of installation not completed': 'Oui',
    'installation not completed|decision to be implemented': 'Non',
    'installation not completed|non-conformity – dissatisfaction – issues encountered': 'Non',

    // ── Unlabeled diamonds — keyed by badge text only ──────────────────────

    // Technical Study diamond (id 1361)
    'technical concept': 'Oui',
    'technical solution proposal': 'Non',
    'customer requirements document for bar feeder specific adaptation': 'Non',

    // Installation in Progress (id 1434) — single exit, already Oui by rule
    'availability of missing spare parts for bar feeder technician': 'Oui',

    // Overdue payments (id 1343)
    'overdue payments': 'Oui',
    'status of the overdue payment': 'Non',
    'payment': 'Non',

    // Counter Sales (id 1442) — single exit, already Oui by rule
    'counter customer account opening request': 'Oui',

    // Order Registration — specific project (id 1178)
    'specific project order': 'Oui',
    'delivery lead time': 'Non',
    'order recorded – request for additional technical information on customer\'s cnc lathe - estimated bar feeder delivery date': 'Oui',

    // Order Registration — bar feeder (id 1460)
    'request for additional information': 'Oui',
    'additional information': 'Non',
    'order confirmation and clarification on lead times and diamete': 'Non',

    // Order Verification (id 1384)
    'account opening request': 'Oui',
    'status of orders': 'Oui',
    'order approved': 'Non',

    // Bar Feeder Inventory diamond (id 1164)
    'bar feeder to be adapted': 'Oui',
    'adaptation planning': 'Non',
    'estimated bar feeder availability date': 'Non',
    'bar feeder to be planned by customer': 'Non',

    // Hot-line diamond (id 1481)
    'request for after-sales service intervention': 'Oui',
    'request for bar feeder reinstallation to be planned': 'Oui',

    // Bar Feeder assembly diamond (id 1465)
    'bar feeder availability': 'Oui',
    'bar feeder refurbishment order': 'Oui',
    'bar feeder to be modified': 'Oui',
    'bar feeder adaptation order': 'Oui',
    'bar feeder to be refurbished': 'Oui',
    'parts manufacturing order': 'Oui',
    'end of parts manufacturing': 'Non',
    'manufacturing to be planned': 'Non',
    'parts to be prepared': 'Non',
    'accessory parts requirements': 'Non',
  };

  // ── State ──────────────────────────────────────────────────────────────
  let _file      = null;
  let _vsdxData  = null;   // Python extractor
  let _toolData  = null;   // VsdxImporter JS
  let _aiData    = null;   // OpenAI / Claude
  let _activeTab = 'compare';

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

    document.querySelectorAll('.dd-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        _activeTab = btn.dataset.tab;
        document.querySelectorAll('.dd-tab').forEach(b =>
          b.classList.toggle('dd-tab-active', b === btn)
        );
        _renderActiveTab();
      });
    });

    _setupDropZone();

    _id('dd-file-input')?.addEventListener('change', e => {
      if (e.target.files.length > 0) _loadFile(e.target.files[0]);
    });

    _id('dd-ai-btn')?.addEventListener('click', _runAI);
    _id('dd-reset-btn')?.addEventListener('click', _resetAll);
    _id('dd-export-json-btn')?.addEventListener('click', _exportJSON);
    _id('dd-export-csv-btn')?.addEventListener('click', _exportCSV);
  });

  // ── Drop zone ──────────────────────────────────────────────────────────
  function _setupDropZone() {
    const zone = _id('dd-dropzone');
    if (!zone) return;
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dd-dz-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dd-dz-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('dd-dz-over');
      const f = e.dataTransfer.files[0];
      if (f) _loadFile(f);
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

    const dz = _id('dd-dropzone');
    if (dz) {
      dz.innerHTML = `<span class="dd-dz-loaded">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="#22c55e"><path d="M8 1L15 8L8 15L1 8Z"/></svg>
        <strong>${_esc(file.name)}</strong>
        <span class="dd-dz-size">${(file.size / 1024).toFixed(1)} Ko</span>
      </span>`;
    }

    const panel = _id('dd-panel');
    const toggle = _id('dd-toggle-btn');
    if (panel && !panel.classList.contains('dd-open')) {
      panel.classList.add('dd-open');
      toggle?.classList.add('dd-toggle-active');
      const lbl = toggle?.querySelector('.dd-toggle-label');
      if (lbl) lbl.textContent = 'Fermer';
    }

    _showExportBtns(false);
    _runAllAnalyses();
  }

  // ── Run VSDX + Tool analyses ───────────────────────────────────────────
  async function _runAllAnalyses() {
    _setStatus('Analyse VSDX + Outil en cours…');
    _id('dd-score')?.replaceChildren();
    _id('dd-tab-content').innerHTML = '<p class="dd-empty">Analyse en cours…</p>';

    const [vsdxResult, toolResult] = await Promise.all([
      _runPythonExtractor(),
      _runJsImporter(),
    ]);

    _vsdxData = vsdxResult;
    _toolData = toolResult;

    _clearStatus();
    try { _renderScore(); } catch (e) { console.error('[dd] renderScore:', e); }
    try {
      _renderActiveTab();
    } catch (e) {
      console.error('[dd] renderActiveTab:', e);
      const el = _id('dd-tab-content');
      if (el) el.innerHTML = `<p class="dd-empty" style="color:#f87171">Erreur d'affichage : ${_esc(e.message)}<br><small>Voir la console navigateur.</small></p>`;
    }
    _showExportBtns(true);
  }

  // ── Python extractor ───────────────────────────────────────────────────
  async function _runPythonExtractor() {
    try {
      const fd = new FormData();
      fd.append('vsdx', _file);
      const res = await fetch('/activities/api/debug-decisions/analyze-file', { method: 'POST', body: fd });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      return json.vsdx || { decisions: [], errors: ['Réponse inattendue'], total_shapes: 0 };
    } catch (e) {
      return { decisions: [], errors: [e.message], total_shapes: 0, total_connectors: 0 };
    }
  }

  // ── JS importer ────────────────────────────────────────────────────────
  async function _runJsImporter() {
    try {
      if (typeof VsdxImporter === 'undefined')
        return { decisions: [], errors: ['VsdxImporter non chargé'], total_shapes: 0 };

      const ab  = await _file.arrayBuffer();
      const zip = await JSZip.loadAsync(ab);
      const imp = new VsdxImporter(zip);
      const res = await imp.parse(() => Promise.resolve('keep'), { spliceDecisions: true });
      if (!res) return { decisions: [], errors: ['Import annulé'], total_shapes: 0 };

      const { shapes = [], connections = [] } = res;
      const byId = {};
      shapes.forEach(s => { byId[s.id] = s; });

      // Build reverse map appId → visioId for position lookup
      const appToVisio = {};
      Object.entries(imp._shapeIdMap || {}).forEach(([v, a]) => { appToVisio[a] = String(v); });
      const pinAbs = imp.shapePinAbs || {};
      const getAbs = id => pinAbs[appToVisio[id]] || null;

      const decisions = shapes
        .filter(s => s._type === 'decision' || s.type === 'decision')
        .map(d => {
          const outgoing = connections.filter(c => c.fromId === d.id).map(c => ({
            conn_id: c.id || '', to_id: c.toId || '',
            to_label: (byId[c.toId] || {}).label || '',
            conn_label: c.label || '', badge: c.label || '',
          })).filter(c => c.to_label || c.badge);

          const incoming = connections.filter(c => c.toId === d.id).map(c => ({
            conn_id: c.id || '', from_id: c.fromId || '',
            from_label: (byId[c.fromId] || {}).label || '',
            conn_label: c.label || '', badge: '',
          }));

          // Single outgoing → always Oui (no branching possible)
          if (outgoing.length === 1) {
            outgoing[0].inferred_badge = 'Oui';
          }

          // Geometric Oui/Non inference using Visio absolute positions
          const dAbs = outgoing.length !== 1 ? getAbs(d.id) : null;
          if (dAbs) {
            const dx = dAbs.pinX, dy = dAbs.pinY;
            const inVecs = incoming.map(c => {
              const s = getAbs(c.from_id);
              if (!s) return null;
              const vx = dx - s.pinX, vy = dy - s.pinY;
              const ln = Math.hypot(vx, vy);
              return ln > 1e-6 ? [vx / ln, vy / ln] : null;
            }).filter(Boolean);

            if (inVecs.length) {
              let fx = inVecs.reduce((s, v) => s + v[0], 0) / inVecs.length;
              let fy = inVecs.reduce((s, v) => s + v[1], 0) / inVecs.length;
              const fl = Math.hypot(fx, fy);
              if (fl > 1e-6) {
                fx /= fl; fy /= fl;
                outgoing.forEach(c => {
                  const t = getAbs(c.to_id);
                  if (!t) { c.inferred_badge = ''; return; }
                  const ox = t.pinX - dx, oy = t.pinY - dy;
                  const ol = Math.hypot(ox, oy);
                  if (ol < 1e-6) { c.inferred_badge = ''; return; }
                  const dot = Math.max(-1, Math.min(1, (ox / ol) * fx + (oy / ol) * fy));
                  c.inferred_badge = Math.acos(dot) * 180 / Math.PI < 45 ? 'Oui' : 'Non';
                });
              }
            }
          }

          return { id: d.id, label: d.label || '', outgoing, incoming };
        });

      return { decisions, total_shapes: shapes.length, total_connections: connections.length, errors: [] };
    } catch (e) {
      return { decisions: [], errors: [e.message], total_shapes: 0 };
    }
  }

  // ── AI analysis ────────────────────────────────────────────────────────
  async function _runAI() {
    if (!_file) { _setStatus('Déposez d\'abord un fichier VSDX.', true); return; }
    const btn = _id('dd-ai-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="dd-spinner"></span>Analyse IA…';
    }

    try {
      const fd = new FormData();
      fd.append('vsdx', _file);
      const res  = await fetch('/activities/api/debug-decisions/analyze-file/ai', { method: 'POST', body: fd });
      const json = await res.json();
      if (json.error) throw new Error(json.error);
      _aiData = json.data || { decisions: [] };
      _aiData._source = json.source || 'ia';

      // Refresh score + comparison with AI column
      _renderScore();
      // Switch to compare tab to show AI column immediately
      document.querySelector('.dd-tab[data-tab="compare"]')?.click();
    } catch (e) {
      _setStatus('IA : ' + e.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = '✦ Analyse IA'; }
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
    _showExportBtns(false);
  }

  // ── Export ─────────────────────────────────────────────────────────────
  function _exportJSON() {
    const payload = {
      file: _file?.name || 'inconnu',
      exported_at: new Date().toISOString(),
      vsdx:  _vsdxData,
      tool:  _toolData,
      ai:    _aiData,
      comparison: _buildComparisonRows(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    _download(blob, `diagnostic_losanges_${_slug(_file?.name)}.json`);
  }

  function _exportCSV() {
    const rows = _buildComparisonRows();
    const hasAI = rows.some(r => r.ai_outs !== undefined);

    const headers = ['Losange VSDX', 'Losange Outil', hasAI ? 'Losange IA' : null,
                     'Entrées VSDX', 'Sorties VSDX (badge)', 'Sorties Outil (badge)',
                     hasAI ? 'Sorties IA (badge)' : null, 'Statut']
                    .filter(Boolean);

    const lines = [headers.map(_csvCell).join(';')];
    for (const r of rows) {
      const line = [
        r.vsdx_label, r.tool_label, hasAI ? (r.ai_label || '') : null,
        r.vsdx_ins, r.vsdx_outs, r.tool_outs,
        hasAI ? (r.ai_outs || '') : null, r.status,
      ].filter((_, i) => headers[i] !== undefined).map(_csvCell).join(';');
      lines.push(line);
    }
    const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    _download(blob, `diagnostic_losanges_${_slug(_file?.name)}.csv`);
  }

  function _buildComparisonRows() {
    const vDec = _vsdxData?.decisions || [];
    const tDec = _toolData?.decisions || [];
    const aDec = _aiData?.decisions   || [];

    const { map: vtMap, unmatched: tOnly } = _matchDecisions(vDec, tDec);
    const { map: vaMap }                   = _matchDecisions(vDec, aDec);

    const outStr = (list, lk) => {
      const synId = id => { const s = String(id || ''); return (s.startsWith('__sp') || /^\d+$/.test(s)) ? '' : s; };
      return (list || []).map(c => {
        const lbl = c[lk] || synId(c.conn_id) || '';
        return lbl ? `${lbl}${c.badge ? ` [${c.badge}]` : ''}` : '';
      }).filter(Boolean).join(' | ');
    };

    const rows = vDec.map((vd, vi) => {
      const td = vtMap.get(vi), ad = vaMap.get(vi);
      return {
        vsdx_label: vd.label,
        tool_label: td?.label ?? '',
        ai_label:   ad?.label ?? '',
        vsdx_ins:   outStr(vd.incoming,  'from_label'),
        vsdx_outs:  outStr(vd.outgoing,  'to_label'),
        tool_outs:  outStr(td?.outgoing, 'to_label'),
        ai_outs:    aDec.length ? outStr(ad?.outgoing, 'to_label') : undefined,
        status:     td ? (ad ? 'OK×3' : 'OK×2') : 'MANQUANT',
      };
    });

    tOnly.forEach(td => rows.push({
      vsdx_label: '',
      tool_label: td.label,
      ai_label:   '',
      vsdx_ins: '', vsdx_outs: '',
      tool_outs: outStr(td.outgoing, 'to_label'),
      ai_outs:   aDec.length ? '' : undefined,
      status:    'OUTIL_SEUL',
    }));

    return rows;
  }

  // ── Score ──────────────────────────────────────────────────────────────
  function _renderScore() {
    const el = _id('dd-score');
    if (!el || (!_vsdxData && !_toolData)) return;

    const vDec = _vsdxData?.decisions || [];
    const tDec = _toolData?.decisions || [];
    const aDec = _aiData?.decisions   || [];

    const { map: vtMapScore } = _matchDecisions(vDec, tDec);
    const matched = vtMapScore.size;
    const total   = Math.max(vDec.length, tDec.length);

    let vBadged = 0, tBadged = 0;
    vDec.forEach(d => d.outgoing.forEach(c => { if (c.badge) vBadged++; }));
    tDec.forEach(d => d.outgoing.forEach(c => { if (c.badge) tBadged++; }));

    const shapeScore = total > 0 ? Math.round(matched / total * 100) : 100;
    const badgeScore = vBadged > 0 ? Math.round(Math.min(tBadged, vBadged) / vBadged * 100) : (tBadged === 0 ? 100 : 0);
    const global = Math.round((shapeScore + badgeScore) / 2);
    const col = global === 100 ? '#22c55e' : global >= 70 ? '#f59e0b' : '#ef4444';

    const aiChip = aDec.length > 0
      ? `<div class="dd-score-item">
           <span class="dd-score-num" style="color:#6366f1">${aDec.length}</span>
           <span class="dd-score-lbl">Losanges<br>IA <span class="dd-src-badge">${_esc(_aiData._source || 'ia')}</span></span>
         </div>` : '';

    el.innerHTML = `
      <div class="dd-score-grid">
        <div class="dd-score-item">
          <span class="dd-score-num" style="color:${col}">${global}%</span>
          <span class="dd-score-lbl">Score<br>VSDX↔Outil</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${vDec.length}</span>
          <span class="dd-score-lbl">Losanges<br>VSDX brut</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${tDec.length}</span>
          <span class="dd-score-lbl">Losanges<br>Outil JS</span>
        </div>
        ${aiChip}
        <div class="dd-score-item">
          <span class="dd-score-num">${matched}/${total}</span>
          <span class="dd-score-lbl">Labels<br>reconnus</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${vBadged} / ${tBadged}</span>
          <span class="dd-score-lbl">Badges Oui/Non<br>VSDX / Outil</span>
        </div>
      </div>
      ${(_vsdxData?.errors?.length ? `<p class="dd-errs">VSDX: ${_vsdxData.errors.join(', ')}</p>` : '')}
      ${(_toolData?.errors?.length ? `<p class="dd-errs">Outil: ${_toolData.errors.join(', ')}</p>` : '')}`;
  }

  // ── Tab rendering ──────────────────────────────────────────────────────
  function _renderActiveTab() {
    switch (_activeTab) {
      case 'compare': _renderCompare(); break;
      case 'oui-non': _renderOuiNon(); break;
      case 'vsdx':    _renderSource(_vsdxData?.decisions, 'VSDX brut (Python)'); break;
      case 'tool':    _renderSource(_toolData?.decisions, 'Outil JS (VsdxImporter)'); break;
      case 'ai':      _renderAITab(); break;
    }
  }

  function _renderCompare() {
    const el = _id('dd-tab-content');
    if (!el) return;

    const vDec = (_vsdxData?.decisions || []).filter(d => d && typeof d === 'object');
    const tDec = (_toolData?.decisions || []).filter(d => d && typeof d === 'object');
    const aDec = (_aiData?.decisions   || []).filter(d => d && typeof d === 'object');
    const hasAI = aDec.length > 0;

    if (vDec.length === 0 && tDec.length === 0) {
      el.innerHTML = '<p class="dd-empty">Aucun losange détecté. Essayez un VSDX contenant des losanges.</p>';
      return;
    }

    const { map: vtMap, unmatched: tOnly } = _matchDecisions(vDec, tDec);
    const { map: vaMap } = hasAI ? _matchDecisions(vDec, aDec) : { map: new Map() };

    const rows = vDec.map((vd, vi) => ({ vd, td: vtMap.get(vi) || null, ad: vaMap.get(vi) || null }));
    tOnly.forEach(td => rows.push({ vd: null, td, ad: null, toolOnly: true }));

    const aiHead = hasAI ? `<th>Sorties IA ${_aiData._source ? `<span class="dd-src-badge">${_esc(_aiData._source)}</span>` : ''}</th>` : '';

    let html = `<table class="dd-table"><thead><tr>
      <th>Losange VSDX</th><th>Losange Outil</th>${aiHead}
      <th>Entrées VSDX</th><th>Entrées Outil</th><th>Sorties VSDX</th><th>Sorties Outil</th>
    </tr></thead><tbody>`;

    for (const { vd, td, ad, toolOnly } of rows) {
      const cls = toolOnly ? 'dd-row-tool-only' : (!td ? 'dd-row-miss' : '');
      const vL  = vd ? (_esc(vd.label) || '<em>sans label</em>') : '—';
      const tL  = td ? (_esc(td.label) || '<em>sans label</em>') : `<span class="dd-miss">Non trouvé</span>`;
      const vIns  = vd  ? _chips(vd.incoming, 'from_label') : '';
      const tIns  = td  ? _chips(td.incoming, 'from_label') : '<span class="dd-miss">—</span>';
      const vOuts = vd  ? _chips(vd.outgoing,  'to_label')  : '';
      const tOuts = td  ? _chips(td.outgoing,  'to_label')  : '<span class="dd-miss">—</span>';
      const aiTd  = hasAI ? `<td>${ad ? _chips(ad.outgoing, 'to_label') : '<span class="dd-miss">—</span>'}</td>` : '';

      html += `<tr class="${cls}">
        <td>${toolOnly ? '<span class="dd-miss">—</span>' : vL}</td>
        <td>${toolOnly ? `<span class="dd-tag-tool">${_esc(td?.label)}</span>` : tL}</td>
        ${aiTd}
        <td>${vIns || '—'}</td><td>${tIns}</td><td>${vOuts || '—'}</td><td>${tOuts}</td>
      </tr>`;
    }

    html += '</tbody></table>';
    el.innerHTML = html;
  }

  function _renderOuiNon() {
    const el = _id('dd-tab-content');
    if (!el) return;

    const vDec = (_vsdxData?.decisions || []).filter(d => d?.outgoing);
    const tDec = (_toolData?.decisions || []).filter(d => d?.outgoing);

    if (!vDec.length) {
      el.innerHTML = '<p class="dd-empty">Lancez d\'abord une analyse VSDX.</p>';
      return;
    }

    const { map: vtMap } = _matchDecisions(vDec, tDec);
    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');

    // GT lookup: tries label|badge, then badge alone, then label|to_label, then to_label alone
    const getRef = (dLabel, vo) => {
      const dk = norm(dLabel);
      const badge = norm(vo.badge || vo.conn_label || '');
      const toLab = norm(vo.to_label || '');
      for (const ck of [badge, toLab]) {
        if (!ck) continue;
        if (dk && _GROUND_TRUTH[dk + '|' + ck] !== undefined) return _GROUND_TRUTH[dk + '|' + ck];
        if (_GROUND_TRUTH[ck] !== undefined) return _GROUND_TRUTH[ck];
      }
      return null;
    };

    // Accord counters: vsdx↔ref and tool↔ref
    let vTotal = 0, vOk = 0, tTotal = 0, tOk = 0;

    const bHtml = b => b === 'Oui'
      ? `<span class="dd-oui-non-badge dd-badge-oui">Oui</span>`
      : b === 'Non'
        ? `<span class="dd-oui-non-badge dd-badge-non">Non</span>`
        : '<span class="dd-miss">—</span>';

    const accHtml = (algo, ref) => {
      if (!algo || !ref) return '·';
      return algo === ref ? '<span class="dd-accord-ok">✓</span>' : '<span class="dd-accord-ko">✗</span>';
    };

    let html = `<table class="dd-table"><thead><tr>
      <th>Losange</th><th>Connexion sortante</th>
      <th>Référence <span class="dd-src-badge">xlsx</span></th>
      <th>VSDX <span class="dd-src-badge">géo</span></th>
      <th>Outil JS <span class="dd-src-badge">géo</span></th>
      <th>VSDX ok</th><th>Outil ok</th>
    </tr></thead><tbody>`;

    vDec.forEach((vd, vi) => {
      const td = vtMap.get(vi);
      const vOuts = vd.outgoing.filter(c => c.to_label || c.badge);
      const dLabel = vd.label || '';
      const dLabelEsc = _esc(dLabel) || '<em class="dd-miss">sans label</em>';

      if (!vOuts.length) {
        html += `<tr><td>${dLabelEsc}</td><td colspan="6" class="dd-miss">—</td></tr>`;
        return;
      }

      vOuts.forEach((vo, i) => {
        // Display the badge (arrow label) — clearer than destination shape name
        const connLabel = vo.badge || vo.conn_label || vo.to_label || '?';
        const vb  = vo.inferred_badge || '';
        const ref = getRef(dLabel, vo);

        let tb = '';
        if (td) {
          // Match Tool JS outgoing by badge or to_label
          const tm = (td.outgoing || []).find(o =>
            norm(o.badge || o.conn_label || '') === norm(vo.badge || vo.conn_label || '') ||
            norm(o.to_label) === norm(vo.to_label)
          );
          if (tm) tb = tm.inferred_badge || '';
        }

        if (vb && ref) { vTotal++; if (vb === ref) vOk++; }
        if (tb && ref) { tTotal++; if (tb === ref) tOk++; }

        const rowErr = (vb && ref && vb !== ref) || (tb && ref && tb !== ref);

        html += `<tr class="${rowErr ? 'dd-row-miss' : ''}">
          ${i === 0 ? `<td rowspan="${vOuts.length}">${dLabelEsc}</td>` : ''}
          <td>${_esc(connLabel)}</td>
          <td>${ref ? bHtml(ref) : '<span class="dd-miss">—</span>'}</td>
          <td>${bHtml(vb)}</td><td>${bHtml(tb)}</td>
          <td>${accHtml(vb, ref)}</td><td>${accHtml(tb, ref)}</td>
        </tr>`;
      });
    });

    html += '</tbody></table>';

    const pct = (ok, tot) => tot > 0 ? `<strong>${ok}/${tot}</strong> (${Math.round(ok / tot * 100)}%)` : '<em>n/a</em>';
    const scoreHtml = `<p class="dd-oui-non-score">
      Précision VSDX↔Référence : ${pct(vOk, vTotal)} &nbsp;|&nbsp;
      Précision Outil JS↔Référence : ${pct(tOk, tTotal)}
    </p>`;

    el.innerHTML = scoreHtml + html;
  }

  function _renderSource(decisions, srcName) {
    const el = _id('dd-tab-content');
    if (!el) return;
    if (!decisions || decisions.length === 0) {
      el.innerHTML = `<p class="dd-empty">Aucun losange dans « ${_esc(srcName)} ».</p>`;
      return;
    }
    let html = `<table class="dd-table"><thead><tr>
      <th>Losange</th><th>Entrées</th><th>Sorties</th>
    </tr></thead><tbody>`;
    for (const d of decisions) {
      html += `<tr>
        <td>${_esc(d.label) || '<em>sans label</em>'}</td>
        <td>${_chips(d.incoming, 'from_label') || '—'}</td>
        <td>${_chips(d.outgoing, 'to_label')   || '—'}</td>
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
    const src = _aiData._source ? ` <span class="dd-src-badge">${_esc(_aiData._source)}</span>` : '';
    const hdr = `<p class="dd-ai-header">Résultat IA${src}</p>`;
    // renderSource overwrites innerHTML, so we prepend after
    _renderSource(_aiData.decisions, 'IA');
    el.insertAdjacentHTML('afterbegin', hdr);
  }

  // ── Helpers ────────────────────────────────────────────────────────────
  function _showExportBtns(show) {
    ['dd-export-json-btn', 'dd-export-csv-btn'].forEach(id => {
      const el = _id(id);
      if (el) el.style.display = show ? '' : 'none';
    });
  }

  // Matching bipartite glouton : score = label(20) + outgoing-target(8 chacun) + incoming-source(5 chacun)
  function _matchDecisions(srcDec, tgtDec) {
    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');
    const candidates = [];
    srcDec.forEach((sd, si) => {
      tgtDec.forEach((td, ti) => {
        let score = 0;
        const sLabel = norm(sd.label), tLabel = norm(td.label);
        if (sLabel && sLabel === tLabel) score += 20;
        const sOut = new Set((sd.outgoing || []).map(c => norm(c.to_label)).filter(Boolean));
        const tOut = new Set((td.outgoing || []).map(c => norm(c.to_label)).filter(Boolean));
        sOut.forEach(l => { if (tOut.has(l)) score += 8; });
        const sIn  = new Set((sd.incoming || []).map(c => norm(c.from_label)).filter(Boolean));
        const tIn  = new Set((td.incoming || []).map(c => norm(c.from_label)).filter(Boolean));
        sIn.forEach(l => { if (tIn.has(l)) score += 5; });
        if (score > 0) candidates.push({ si, ti, score });
      });
    });
    candidates.sort((a, b) => b.score - a.score);
    const usedS = new Set(), usedT = new Set();
    const map = new Map();
    for (const { si, ti } of candidates) {
      if (!usedS.has(si) && !usedT.has(ti)) {
        map.set(si, tgtDec[ti]);
        usedS.add(si);
        usedT.add(ti);
      }
    }
    // Fallback séquentiel : paire les restants sans score en ordre (ex: losanges vides)
    const remS = srcDec.map((_, i) => i).filter(i => !usedS.has(i));
    const remT = tgtDec.map((_, i) => i).filter(i => !usedT.has(i));
    const lim = Math.min(remS.length, remT.length);
    for (let i = 0; i < lim; i++) { map.set(remS[i], tgtDec[remT[i]]); usedT.add(remT[i]); }
    const unmatched = tgtDec.filter((_, ti) => !usedT.has(ti));
    return { map, unmatched };
  }

  function _chips(list, lk) {
    if (!list?.length) return '';
    return list.map(c => {
      const rawId = String(c.conn_id || '');
      const isSynthetic = rawId.startsWith('__sp') || /^\d+$/.test(rawId);
      const label = c[lk] || (isSynthetic ? '' : rawId) || '';
      const explicit = c.badge || '';
      const inferred = explicit ? '' : (c.inferred_badge || '');
      if (!label && !explicit && !inferred) return '';
      const badgeHtml = explicit
        ? ` <em>${_esc(explicit)}</em>`
        : (inferred ? ` <em class="dd-b-inf">${_esc(inferred)}</em>` : '');
      const cls = explicit ? 'dd-badge-yes' : (inferred ? 'dd-badge-inf' : '');
      return `<span class="dd-conn ${cls}">${_esc(label || '?')}${badgeHtml}</span>`;
    }).filter(Boolean).join('');
  }

  function _setStatus(msg, err = false) {
    const el = _id('dd-status');
    if (!el) return;
    el.textContent = msg;
    el.className = 'dd-status' + (err ? ' dd-status-err' : '');
    el.style.display = '';
  }
  function _clearStatus() {
    const el = _id('dd-status');
    if (el) el.style.display = 'none';
  }

  function _download(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function _slug(name) {
    return (name || 'export').replace(/[^a-z0-9]/gi, '_').replace(/__+/g, '_').slice(0, 40);
  }
  function _csvCell(v) {
    const s = String(v ?? '');
    return s.includes(';') || s.includes('"') || s.includes('\n')
      ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function _id(id)  { return document.getElementById(id); }
  function _esc(s)  { return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
})();
