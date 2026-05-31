/* debug_decisions.js — Section de comparaison losanges VSDX / Outil / IA */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);

  // ── State ──────────────────────────────────────────────────────────────
  let _vsdxData = null;
  let _toolData = null;
  let _aiData   = null;
  let _activeTab = 'compare';

  // ── Init ───────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    const toggle = $('dd-toggle-btn');
    const panel  = $('dd-panel');
    if (!toggle || !panel) return;

    toggle.addEventListener('click', () => {
      const open = panel.classList.toggle('dd-open');
      toggle.classList.toggle('dd-toggle-active', open);
      const lbl = toggle.querySelector('.dd-toggle-label');
      if (lbl) lbl.textContent = open ? 'Fermer' : 'Ouvrir';
      if (open && !_vsdxData) loadData();
    });

    // Tab buttons
    document.querySelectorAll('.dd-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        _activeTab = btn.dataset.tab;
        document.querySelectorAll('.dd-tab').forEach(b => b.classList.toggle('dd-tab-active', b === btn));
        renderActiveTab();
      });
    });

    $('dd-refresh-btn')?.addEventListener('click', () => {
      _vsdxData = null; _toolData = null; _aiData = null;
      loadData();
    });

    $('dd-ai-btn')?.addEventListener('click', loadAI);
  });

  // ── Data loading ───────────────────────────────────────────────────────
  async function loadData() {
    setStatus('Chargement…');
    try {
      const res = await fetch('/activities/api/debug-decisions');
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      _vsdxData = json.vsdx;
      _toolData = json.tool;

      if (!json.has_vsdx) {
        setStatus('Aucun fichier VSDX disponible pour cette entité.');
        return;
      }
      clearStatus();
      renderScore();
      renderActiveTab();
    } catch (e) {
      setStatus('Erreur : ' + e.message, true);
    }
  }

  async function loadAI() {
    const btn = $('dd-ai-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Analyse IA…'; }
    try {
      const res = await fetch('/activities/api/debug-decisions/ai', { method: 'POST' });
      const json = await res.json();
      if (json.error) throw new Error(json.error);
      _aiData = json.data;
      $('dd-tab-ai')?.click();
    } catch (e) {
      setStatus('IA : ' + e.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '✦ Analyse IA (Claude)'; }
    }
  }

  // ── Score ──────────────────────────────────────────────────────────────
  function renderScore() {
    const scoreEl = $('dd-score');
    if (!scoreEl || !_vsdxData || !_toolData) return;

    const vDec = _vsdxData.decisions || [];
    const tDec = _toolData.decisions || [];

    if (vDec.length === 0) {
      scoreEl.innerHTML = '<span class="dd-score-val dd-score-grey">Aucun losange détecté dans le VSDX</span>';
      return;
    }

    // Match by label (normalised)
    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');
    const vLabels = new Set(vDec.map(d => norm(d.label)));
    const tLabels = new Set(tDec.map(d => norm(d.label)));
    const matched = [...vLabels].filter(l => tLabels.has(l)).length;

    // Count outgoing with badge in VSDX vs tool
    let vBadged = 0, tBadged = 0;
    vDec.forEach(d => d.outgoing.forEach(c => { if (c.badge) vBadged++; }));
    tDec.forEach(d => d.outgoing.forEach(c => { if (c.badge) tBadged++; }));

    const shapeScore = vDec.length > 0 ? Math.round(matched / vDec.length * 100) : 100;
    const badgeScore = vBadged > 0 ? Math.round(Math.min(tBadged, vBadged) / vBadged * 100) : (tBadged === 0 ? 100 : 0);
    const total = Math.round((shapeScore + badgeScore) / 2);

    const color = total === 100 ? '#22c55e' : total >= 70 ? '#f59e0b' : '#ef4444';

    scoreEl.innerHTML = `
      <div class="dd-score-grid">
        <div class="dd-score-item">
          <span class="dd-score-num" style="color:${color}">${total}%</span>
          <span class="dd-score-lbl">Score global</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${matched}/${vDec.length}</span>
          <span class="dd-score-lbl">Losanges reconnus</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${tBadged}/${vBadged}</span>
          <span class="dd-score-lbl">Badges Oui/Non</span>
        </div>
        <div class="dd-score-item">
          <span class="dd-score-num">${_vsdxData.total_shapes || '?'}</span>
          <span class="dd-score-lbl">Formes VSDX</span>
        </div>
      </div>`;
  }

  // ── Tab rendering ──────────────────────────────────────────────────────
  function renderActiveTab() {
    switch (_activeTab) {
      case 'compare': renderCompare(); break;
      case 'vsdx':    renderSource('dd-tab-content', _vsdxData?.decisions, 'VSDX'); break;
      case 'tool':    renderSource('dd-tab-content', _toolData?.decisions, 'Outil'); break;
      case 'ai':      renderAITab(); break;
    }
  }

  function renderCompare() {
    const el = $('dd-tab-content');
    if (!el) return;
    if (!_vsdxData || !_toolData) { el.innerHTML = '<p class="dd-empty">Données non chargées.</p>'; return; }

    const vDec = _vsdxData.decisions || [];
    const tDec = _toolData.decisions || [];
    const norm = s => (s || '').toLowerCase().trim().replace(/\s+/g, ' ');
    const tByLabel = {};
    tDec.forEach(d => { tByLabel[norm(d.label)] = d; });

    if (vDec.length === 0) {
      el.innerHTML = '<p class="dd-empty">Aucun losange détecté dans le VSDX brut.</p>';
      return;
    }

    let html = '<table class="dd-table"><thead><tr>'
      + '<th>Losange VSDX</th><th>Losange Outil</th><th>Entrées</th><th>Sorties VSDX</th><th>Sorties Outil</th>'
      + '</tr></thead><tbody>';

    for (const vd of vDec) {
      const td = tByLabel[norm(vd.label)];
      const found = !!td;
      const rowCls = found ? '' : 'dd-row-miss';

      const vOuts = (vd.outgoing || []).map(c =>
        `<span class="dd-conn ${c.badge ? 'dd-badge-yes' : ''}">${esc(c.to_label || c.to_id)} ${c.badge ? `<em>${c.badge}</em>` : ''}</span>`
      ).join('');

      const tOuts = td ? (td.outgoing || []).map(c =>
        `<span class="dd-conn ${c.badge ? 'dd-badge-yes' : ''}">${esc(c.to_label || c.to_id)} ${c.badge ? `<em>${c.badge}</em>` : ''}</span>`
      ).join('') : '<span class="dd-miss">—</span>';

      const vIns = (vd.incoming || []).map(c =>
        `<span class="dd-conn">${esc(c.from_label || c.from_id)}</span>`
      ).join('');

      html += `<tr class="${rowCls}">
        <td>${esc(vd.label) || '<em>sans label</em>'}</td>
        <td>${found ? esc(td.label) : '<span class="dd-miss">Non trouvé</span>'}</td>
        <td>${vIns || '—'}</td>
        <td>${vOuts || '—'}</td>
        <td>${tOuts}</td>
      </tr>`;
    }

    html += '</tbody></table>';
    el.innerHTML = html;
  }

  function renderSource(containerId, decisions, srcName) {
    const el = $(containerId);
    if (!el) return;
    if (!decisions || decisions.length === 0) {
      el.innerHTML = `<p class="dd-empty">Aucun losange dans la source "${srcName}".</p>`;
      return;
    }

    let html = '<table class="dd-table"><thead><tr>'
      + '<th>Losange</th><th>Entrées</th><th>Sorties</th>'
      + '</tr></thead><tbody>';

    for (const d of decisions) {
      const ins = (d.incoming || []).map(c =>
        `<span class="dd-conn">${esc(c.from_label || c.from_id)}</span>`
      ).join('') || '—';
      const outs = (d.outgoing || []).map(c =>
        `<span class="dd-conn ${c.badge ? 'dd-badge-yes' : ''}">${esc(c.to_label || c.to_id)}${c.badge ? ` <em>${c.badge}</em>` : ''}</span>`
      ).join('') || '—';

      html += `<tr><td>${esc(d.label) || '<em>sans label</em>'}</td><td>${ins}</td><td>${outs}</td></tr>`;
    }

    html += '</tbody></table>';
    el.innerHTML = html;
  }

  function renderAITab() {
    const el = $('dd-tab-content');
    if (!el) return;
    if (!_aiData) {
      el.innerHTML = '<p class="dd-empty">Cliquez sur "Analyse IA (Claude)" pour lancer l\'analyse.</p>';
      return;
    }
    renderSource('dd-tab-content', _aiData.decisions, 'IA');
  }

  // ── Helpers ────────────────────────────────────────────────────────────
  function setStatus(msg, error = false) {
    const el = $('dd-status');
    if (!el) return;
    el.textContent = msg;
    el.className = 'dd-status' + (error ? ' dd-status-err' : '');
    el.style.display = '';
  }
  function clearStatus() {
    const el = $('dd-status');
    if (el) el.style.display = 'none';
  }
  function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
})();
