/* debug_decisions.js — Diagnostic losanges : drop VSDX → 3 analyses parallèles */
(function () {
  'use strict';

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
    _renderScore();
    _renderActiveTab();
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

      const decisions = shapes
        .filter(s => s._type === 'decision' || s.type === 'decision')
        .map(d => ({
          id: d.id,
          label: d.label || '',
          outgoing: connections.filter(c => c.fromId === d.id).map(c => ({
            conn_id: c.id || '', to_id: c.toId || '',
            to_label: (byId[c.toId] || {}).label || '',
            conn_label: c.label || '', badge: c.label || '',
          })),
          incoming: connections.filter(c => c.toId === d.id).map(c => ({
            conn_id: c.id || '', from_id: c.fromId || '',
            from_label: (byId[c.fromId] || {}).label || '',
            conn_label: c.label || '', badge: '',
          })),
        }));

      return { decisions, total_shapes: shapes.length, total_connections: connections.length, errors: [] };
    } catch (e) {
      return { decisions: [], errors: [e.message], total_shapes: 0 };
    }
  }

  // ── AI analysis ────────────────────────────────────────────────────────
  async function _runAI() {
    if (!_file) { _setStatus('Déposez d\'abord un fichier VSDX.', true); return; }
    const btn = _id('dd-ai-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Analyse IA…'; }

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
    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');

    const tMap = {}, aMap = {};
    tDec.forEach(d => { tMap[norm(d.label)] = d; });
    aDec.forEach(d => { aMap[norm(d.label)] = d; });

    const outStr = (list, lk) =>
      (list || []).map(c => `${c[lk] || c.conn_id || '?'}${c.badge ? ` [${c.badge}]` : ''}`).join(' | ');

    const seen = new Set();
    const rows = vDec.map(vd => {
      const key = norm(vd.label);
      seen.add(key);
      const td = tMap[key], ad = aMap[key];
      return {
        vsdx_label: vd.label,
        tool_label: td?.label || '',
        ai_label:   ad?.label || '',
        vsdx_ins:   outStr(vd.incoming,  'from_label'),
        vsdx_outs:  outStr(vd.outgoing,  'to_label'),
        tool_outs:  outStr(td?.outgoing, 'to_label'),
        ai_outs:    aDec.length ? outStr(ad?.outgoing, 'to_label') : undefined,
        status:     td ? (ad ? 'OK×3' : 'OK×2') : 'MANQUANT',
      };
    });

    // Tool-only
    tDec.filter(td => !seen.has(norm(td.label))).forEach(td => {
      const key = norm(td.label);
      const ad = aMap[key];
      rows.push({
        vsdx_label: '',
        tool_label: td.label,
        ai_label:   ad?.label || '',
        vsdx_ins:   '', vsdx_outs: '',
        tool_outs:  outStr(td.outgoing, 'to_label'),
        ai_outs:    aDec.length ? outStr(ad?.outgoing, 'to_label') : undefined,
        status:     'OUTIL_SEUL',
      });
    });

    return rows;
  }

  // ── Score ──────────────────────────────────────────────────────────────
  function _renderScore() {
    const el = _id('dd-score');
    if (!el || (!_vsdxData && !_toolData)) return;

    const vDec = _vsdxData?.decisions || [];
    const tDec = _toolData?.decisions || [];
    const aDec = _aiData?.decisions   || [];

    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');
    const vSet = new Set(vDec.map(d => norm(d.label)));
    const tSet = new Set(tDec.map(d => norm(d.label)));
    const matched = [...vSet].filter(l => tSet.has(l)).length;
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
      case 'vsdx':    _renderSource(_vsdxData?.decisions, 'VSDX brut (Python)'); break;
      case 'tool':    _renderSource(_toolData?.decisions, 'Outil JS (VsdxImporter)'); break;
      case 'ai':      _renderAITab(); break;
    }
  }

  function _renderCompare() {
    const el = _id('dd-tab-content');
    if (!el) return;

    const vDec = _vsdxData?.decisions || [];
    const tDec = _toolData?.decisions || [];
    const aDec = _aiData?.decisions   || [];
    const hasAI = aDec.length > 0;

    if (vDec.length === 0 && tDec.length === 0) {
      el.innerHTML = '<p class="dd-empty">Aucun losange détecté. Essayez un VSDX contenant des losanges.</p>';
      return;
    }

    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');
    const tMap = {}, aMap = {};
    tDec.forEach(d => { tMap[norm(d.label)] = d; });
    aDec.forEach(d => { aMap[norm(d.label)] = d; });

    const vLabels = new Set(vDec.map(d => norm(d.label)));
    const rows = vDec.map(vd => ({ vd, td: tMap[norm(vd.label)], ad: aMap[norm(vd.label)] }));
    tDec.filter(td => !vLabels.has(norm(td.label)))
        .forEach(td => rows.push({ vd: null, td, ad: aMap[norm(td.label)], toolOnly: true }));

    const aiHead = hasAI ? `<th>Sorties IA ${_aiData._source ? `<span class="dd-src-badge">${_esc(_aiData._source)}</span>` : ''}</th>` : '';

    let html = `<table class="dd-table"><thead><tr>
      <th>Losange VSDX</th><th>Losange Outil</th>${aiHead}
      <th>Entrées VSDX</th><th>Sorties VSDX</th><th>Sorties Outil</th>
    </tr></thead><tbody>`;

    for (const { vd, td, ad, toolOnly } of rows) {
      const cls = toolOnly ? 'dd-row-tool-only' : (!td ? 'dd-row-miss' : '');
      const vL  = vd ? (_esc(vd.label) || '<em>sans label</em>') : '—';
      const tL  = td ? (_esc(td.label) || '<em>sans label</em>') : `<span class="dd-miss">Non trouvé</span>`;
      const vIns  = vd  ? _chips(vd.incoming, 'from_label') : '';
      const vOuts = vd  ? _chips(vd.outgoing,  'to_label')  : '';
      const tOuts = td  ? _chips(td.outgoing,  'to_label')  : '<span class="dd-miss">—</span>';
      const aiTd  = hasAI ? `<td>${ad ? _chips(ad.outgoing, 'to_label') : '<span class="dd-miss">—</span>'}</td>` : '';

      html += `<tr class="${cls}">
        <td>${toolOnly ? '<span class="dd-miss">—</span>' : vL}</td>
        <td>${toolOnly ? `<span class="dd-tag-tool">${_esc(td?.label)}</span>` : tL}</td>
        ${aiTd}
        <td>${vIns || '—'}</td><td>${vOuts || '—'}</td><td>${tOuts}</td>
      </tr>`;
    }

    html += '</tbody></table>';
    el.innerHTML = html;
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

  function _chips(list, lk) {
    if (!list?.length) return '';
    return list.map(c => {
      const badge = c.badge ? ` <em>${_esc(c.badge)}</em>` : '';
      return `<span class="dd-conn ${c.badge ? 'dd-badge-yes' : ''}">${_esc(c[lk] || c.conn_id || '?')}${badge}</span>`;
    }).join('');
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
