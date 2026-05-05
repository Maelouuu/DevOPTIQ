/**
 * IMPORT GLOBAL IA — Frontend
 * Gère le workflow complet : upload → analyse IA → validation → injection
 */

(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────
  let currentFile = null;
  let analysisResult = null;   // réponse complète de /api/import-full/analyze
  let dbActivities = [];       // [{id, name}] pour les selects unmatched

  // ── DOM refs ───────────────────────────────────────────────────
  const overlay     = document.getElementById('import-full-overlay');
  const closeBtn    = document.getElementById('if-close-btn');
  const triggerBtn  = document.getElementById('btn-import-full');

  // Screens
  const screens = {
    1: document.getElementById('if-screen-1'),
    2: document.getElementById('if-screen-2'),
    3: document.getElementById('if-screen-3'),
    4: document.getElementById('if-screen-4'),
  };

  // Upload
  const dropzone    = document.getElementById('if-dropzone');
  const fileInput   = document.getElementById('if-file-input');
  const filePreview = document.getElementById('if-file-preview');
  const fileName    = document.getElementById('if-file-name');
  const fileSize    = document.getElementById('if-file-size');
  const fileRemove  = document.getElementById('if-file-remove');
  const analyzeBtn  = document.getElementById('if-analyze-btn');
  const cancelBtn1  = document.getElementById('if-cancel-1');

  // Loading steps
  const procRead    = document.getElementById('proc-read');
  const procMatch   = document.getElementById('proc-match');
  const procStruct  = document.getElementById('proc-struct');

  // Review
  const sumMatched    = document.getElementById('if-sum-matched');
  const sumUnmatched  = document.getElementById('if-sum-unmatched');
  const sumTasks      = document.getElementById('if-sum-tasks');
  const aiNotes       = document.getElementById('if-ai-notes');
  const aiNotesText   = document.getElementById('if-ai-notes-text');
  const matchedList   = document.getElementById('if-matched-list');
  const unmatchedList = document.getElementById('if-unmatched-list');
  const badgeMatched  = document.getElementById('tab-badge-matched');
  const badgeUnmatched = document.getElementById('tab-badge-unmatched');
  const injectBtn     = document.getElementById('if-inject-btn');
  const injectPreview = document.getElementById('if-inject-preview');
  const backBtn3      = document.getElementById('if-back-3');

  // Result
  const resultSuccess    = document.getElementById('if-result-success');
  const resultError      = document.getElementById('if-result-error');
  const resultErrorMsg   = document.getElementById('if-result-error-msg');
  const resultStats      = document.getElementById('if-result-stats');
  const retryBtn         = document.getElementById('if-retry-btn');
  const doneBtn          = document.getElementById('if-done-btn');

  // Templates
  const tplMatched   = document.getElementById('tpl-matched-group');
  const tplUnmatched = document.getElementById('tpl-unmatched-group');

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    if (!overlay) return; // page sans le modal

    // Trigger
    if (triggerBtn) triggerBtn.addEventListener('click', openModal);

    // Close
    closeBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });

    // Upload zone
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('drag-over');
    });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      const f = e.dataTransfer.files[0];
      if (f) setFile(f);
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) setFile(fileInput.files[0]);
    });

    fileRemove.addEventListener('click', (e) => { e.stopPropagation(); clearFile(); });

    analyzeBtn.addEventListener('click', runAnalysis);
    cancelBtn1.addEventListener('click', closeModal);
    backBtn3.addEventListener('click', resetToStep1);
    injectBtn.addEventListener('click', runInject);
    retryBtn.addEventListener('click', resetToStep1);
    doneBtn.addEventListener('click', closeModal);

    // Tabs
    document.querySelectorAll('.if-tab').forEach(tab => {
      tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
  }

  // ── Modal lifecycle ────────────────────────────────────────────
  function openModal() {
    overlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    overlay.classList.add('hidden');
    document.body.style.overflow = '';
  }

  function resetToStep1() {
    clearFile();
    analysisResult = null;
    dbActivities = [];
    matchedList.innerHTML = '';
    unmatchedList.innerHTML = '';
    goToScreen(1);
  }

  // ── File handling ──────────────────────────────────────────────
  function setFile(f) {
    const allowed = ['.xlsx', '.xls', '.xlsm'];
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
      showToast('Format non supporté. Utilisez .xlsx, .xls ou .xlsm', 'error');
      return;
    }
    currentFile = f;
    fileName.textContent = f.name;
    fileSize.textContent = formatSize(f.size);
    dropzone.classList.add('hidden');
    filePreview.classList.remove('hidden');
    analyzeBtn.disabled = false;
  }

  function clearFile() {
    currentFile = null;
    fileInput.value = '';
    dropzone.classList.remove('hidden');
    filePreview.classList.add('hidden');
    analyzeBtn.disabled = true;
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' o';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' Ko';
    return (bytes / (1024 * 1024)).toFixed(1) + ' Mo';
  }

  // ── Stepper ────────────────────────────────────────────────────
  function goToScreen(n) {
    Object.values(screens).forEach((s, i) => {
      s.classList.remove('active');
    });
    screens[n].classList.add('active');
    updateStepper(n);
  }

  function updateStepper(activeStep) {
    document.querySelectorAll('.if-step').forEach((step, i) => {
      const stepN = i + 1;
      step.classList.remove('active', 'done');
      const line = step.nextElementSibling;
      if (line && line.classList.contains('if-step-line')) {
        line.classList.remove('done');
      }
      if (stepN < activeStep) {
        step.classList.add('done');
        const dot = step.querySelector('.if-step-dot');
        dot.innerHTML = '<i class="fa-solid fa-check"></i>';
        if (line) line.classList.add('done');
      } else if (stepN === activeStep) {
        step.classList.add('active');
        const dot = step.querySelector('.if-step-dot');
        dot.innerHTML = `<span>${stepN}</span>`;
      } else {
        const dot = step.querySelector('.if-step-dot');
        dot.innerHTML = `<span>${stepN}</span>`;
      }
    });
  }

  // ── Loading steps animation ───────────────────────────────────
  function animateLoadingSteps() {
    const steps = [procRead, procMatch, procStruct];
    steps.forEach(s => { s.classList.remove('active', 'done'); });
    procRead.classList.add('active');

    return new Promise(resolve => {
      setTimeout(() => {
        procRead.classList.remove('active');
        procRead.classList.add('done');
        procRead.innerHTML = '<i class="fa-solid fa-check"></i> Lecture du fichier Excel';
        procMatch.classList.add('active');
      }, 800);
      setTimeout(() => {
        procMatch.classList.remove('active');
        procMatch.classList.add('done');
        procMatch.innerHTML = '<i class="fa-solid fa-check"></i> Matching des activités';
        procStruct.classList.add('active');
      }, 1800);
      setTimeout(() => {
        procStruct.classList.remove('active');
        procStruct.classList.add('done');
        procStruct.innerHTML = '<i class="fa-solid fa-check"></i> Structuration des données';
        resolve();
      }, 2800);
    });
  }

  // ── Analyse ────────────────────────────────────────────────────
  async function runAnalysis() {
    if (!currentFile) return;

    goToScreen(2);

    // Réinitialiser loading steps
    [procRead, procMatch, procStruct].forEach(s => {
      s.classList.remove('active', 'done');
    });
    procRead.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Lecture du fichier Excel';
    procMatch.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Matching des activités';
    procStruct.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Structuration des données';

    // Lancer l'animation et l'appel API en parallèle
    const animPromise = animateLoadingSteps();

    const formData = new FormData();
    formData.append('file', currentFile);

    let data;
    try {
      const resp = await fetch('/api/import-full/analyze', {
        method: 'POST',
        body: formData,
      });
      data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.error || 'Erreur serveur');
      }
    } catch (err) {
      // Attendre au moins la fin de l'animation pour cohérence UX
      await animPromise;
      showErrorScreen(err.message || 'Erreur lors de l\'analyse');
      return;
    }

    // Attendre que l'animation soit terminée
    await animPromise;

    analysisResult = data;
    dbActivities = data.db_activities || [];

    buildReviewScreen(data);
    goToScreen(3);
  }

  // ── Build review ───────────────────────────────────────────────
  function buildReviewScreen(data) {
    const analysis = data.analysis || {};
    const stats = data.stats || {};
    const matched = analysis.matched_groups || [];
    const unmatched = analysis.unmatched_groups || [];

    // Summary
    sumMatched.textContent = matched.length;
    sumUnmatched.textContent = unmatched.length;
    sumTasks.textContent = stats.total_tasks || 0;
    badgeMatched.textContent = matched.length;
    badgeUnmatched.textContent = unmatched.length;

    // Notes IA
    const notes = analysis.analysis_notes;
    if (notes) {
      aiNotesText.textContent = notes;
      aiNotes.classList.remove('hidden');
    } else {
      aiNotes.classList.add('hidden');
    }

    // Build matched cards
    matchedList.innerHTML = '';
    matched.forEach(group => {
      const card = buildMatchedCard(group);
      matchedList.appendChild(card);
    });

    // Build unmatched cards
    unmatchedList.innerHTML = '';
    unmatched.forEach(group => {
      const card = buildUnmatchedCard(group);
      unmatchedList.appendChild(card);
    });

    // Switch to matched tab by default
    switchTab('matched');

    // Update inject preview
    updateInjectPreview();
  }

  // ── Matched card ───────────────────────────────────────────────
  function buildMatchedCard(group) {
    const tpl = tplMatched.content.cloneNode(true);
    const card = tpl.querySelector('.if-group-card');

    card.querySelector('.if-group-activity-name').textContent = group.activity_name_excel;
    card.querySelector('.if-group-match-name').textContent = '→ ' + group.activity_name_db;

    const badge = card.querySelector('.if-group-confidence-badge');
    const conf = group.confidence || 'medium';
    badge.textContent = { high: 'Sûr', medium: 'Probable', low: 'Incertain' }[conf] || conf;
    badge.classList.add('confidence-' + conf);

    const tasks = group.tasks || [];
    card.querySelector('.if-group-tasks-count').textContent = tasks.length + ' tâche' + (tasks.length > 1 ? 's' : '');

    const reason = group.match_reason || '';
    if (reason) card.querySelector('.if-match-reason').textContent = reason;

    // Store data on card
    card.dataset.activityId = group.activity_id;
    card.dataset.guarantor = group.guarantor || '';

    // Afficher le garant si présent
    if (group.guarantor) {
      const gEl = card.querySelector('.if-group-guarantor');
      if (gEl) {
        gEl.querySelector('.if-guarantor-name').textContent = group.guarantor;
        gEl.classList.remove('hidden');
      }
    }

    // Build tasks table
    const tbody = card.querySelector('.if-tasks-tbody');
    buildTaskRows(tbody, tasks);

    // Toggle
    const toggle = card.querySelector('.if-group-toggle');
    const body = card.querySelector('.if-group-body');
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      body.classList.toggle('hidden');
      toggle.classList.toggle('open');
    });
    // Click header also toggles
    card.querySelector('.if-group-header').addEventListener('click', (e) => {
      if (e.target.closest('.if-group-checkbox-label') || e.target.closest('.if-group-toggle')) return;
      body.classList.toggle('hidden');
      toggle.classList.toggle('open');
    });

    // Checkbox toggle
    const checkbox = card.querySelector('.if-group-select');
    checkbox.addEventListener('change', updateInjectPreview);

    return card;
  }

  // ── Unmatched card ─────────────────────────────────────────────
  function buildUnmatchedCard(group) {
    const tpl = tplUnmatched.content.cloneNode(true);
    const card = tpl.querySelector('.if-group-card');

    card.querySelector('.if-group-activity-name').textContent = group.activity_name_excel;
    const tasks = group.tasks || [];
    card.querySelector('.if-group-tasks-count').textContent = tasks.length + ' tâche' + (tasks.length > 1 ? 's' : '');

    const reason = group.reason || '';
    if (reason) card.querySelector('.if-unmatched-reason').textContent = reason;

    // Populate activity select
    const select = card.querySelector('.if-activity-select');
    dbActivities.forEach(act => {
      const opt = document.createElement('option');
      opt.value = act.id;
      opt.textContent = act.name;
      select.appendChild(opt);
    });
    select.addEventListener('change', updateInjectPreview);

    // Possible matches
    const possibleMatches = group.possible_matches || [];
    if (possibleMatches.length > 0) {
      const pmSection = card.querySelector('.if-possible-matches');
      pmSection.classList.remove('hidden');
      const pmList = card.querySelector('.if-pm-list');
      possibleMatches.forEach(pm => {
        const btn = document.createElement('button');
        btn.className = 'if-pm-item';
        btn.textContent = pm.activity_name;
        btn.title = 'Similarité : ' + (pm.similarity || '?');
        btn.addEventListener('click', () => {
          select.value = pm.activity_id;
          select.dispatchEvent(new Event('change'));
        });
        pmList.appendChild(btn);
      });
    }

    card.dataset.guarantor = group.guarantor || '';

    // Afficher le garant si présent
    if (group.guarantor) {
      const gEl = card.querySelector('.if-group-guarantor');
      if (gEl) {
        gEl.querySelector('.if-guarantor-name').textContent = group.guarantor;
        gEl.classList.remove('hidden');
      }
    }

    // Build tasks table
    const tbody = card.querySelector('.if-tasks-tbody');
    buildTaskRows(tbody, tasks);

    // Toggle
    const toggle = card.querySelector('.if-group-toggle');
    const body = card.querySelector('.if-group-body');
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      body.classList.toggle('hidden');
      toggle.classList.toggle('open');
    });
    card.querySelector('.if-group-header').addEventListener('click', (e) => {
      if (e.target.closest('.if-group-toggle')) return;
      body.classList.toggle('hidden');
      toggle.classList.toggle('open');
    });

    return card;
  }

  // ── Build task rows ────────────────────────────────────────────
  function buildTaskRows(tbody, tasks) {
    tbody.innerHTML = '';
    tasks.forEach(task => {
      const tr = document.createElement('tr');

      // Nom
      const tdName = document.createElement('td');
      tdName.innerHTML = `<span class="if-task-name">${esc(task.name || '')}</span>`;
      tr.appendChild(tdName);

      // Outils
      const tdTools = document.createElement('td');
      const tools = (task.tools || []).filter(Boolean);
      if (tools.length) {
        const wrap = document.createElement('div');
        wrap.className = 'if-task-tools';
        tools.forEach(t => {
          const tag = document.createElement('span');
          tag.className = 'if-tag if-tag-tool';
          tag.textContent = t;
          wrap.appendChild(tag);
        });
        tdTools.appendChild(wrap);
      } else {
        tdTools.innerHTML = '<span class="if-task-empty">—</span>';
      }
      tr.appendChild(tdTools);

      // Doer
      const tdDoer = document.createElement('td');
      tdDoer.textContent = task.doer || '—';
      tr.appendChild(tdDoer);

      // Compétences
      const tdSkills = document.createElement('td');
      const skills = (task.skills || []).filter(Boolean);
      if (skills.length) {
        const wrap = document.createElement('div');
        wrap.className = 'if-task-skills';
        skills.forEach(s => {
          const tag = document.createElement('span');
          tag.className = 'if-tag if-tag-skill';
          tag.textContent = s;
          wrap.appendChild(tag);
        });
        tdSkills.appendChild(wrap);
      } else {
        tdSkills.innerHTML = '<span class="if-task-empty">—</span>';
      }
      tr.appendChild(tdSkills);

      tbody.appendChild(tr);
    });
  }

  // ── Tabs ───────────────────────────────────────────────────────
  function switchTab(tabName) {
    document.querySelectorAll('.if-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.tab === tabName);
    });
    document.querySelectorAll('.if-tab-content').forEach(c => {
      c.classList.toggle('active', c.id === 'if-tab-' + tabName);
    });
  }

  // ── Inject preview ─────────────────────────────────────────────
  function updateInjectPreview() {
    const matchedCards = matchedList.querySelectorAll('.if-group-card');
    let countMatched = 0;
    matchedCards.forEach(card => {
      const cb = card.querySelector('.if-group-select');
      if (cb && cb.checked) countMatched++;
    });

    const unmatchedCards = unmatchedList.querySelectorAll('.if-group-card');
    let countUnmatched = 0;
    unmatchedCards.forEach(card => {
      const sel = card.querySelector('.if-activity-select');
      if (sel && sel.value) countUnmatched++;
    });

    const total = countMatched + countUnmatched;
    if (total === 0) {
      injectPreview.textContent = 'Aucun groupe sélectionné';
      injectBtn.disabled = true;
    } else {
      injectPreview.textContent = `${total} groupe${total > 1 ? 's' : ''} à importer`;
      injectBtn.disabled = false;
    }
  }

  // ── Inject ─────────────────────────────────────────────────────
  async function runInject() {
    const groups = collectGroupsToInject();
    if (!groups.length) {
      showToast('Aucun groupe sélectionné', 'error');
      return;
    }

    injectBtn.disabled = true;
    injectBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Importation…';

    try {
      const resp = await fetch('/api/import-full/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groups }),
      });
      const data = await resp.json();

      if (!resp.ok) throw new Error(data.error || 'Erreur serveur');

      showSuccessScreen(data.stats || {});
    } catch (err) {
      showErrorScreen(err.message);
    } finally {
      injectBtn.disabled = false;
      injectBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Importer les données validées';
    }
  }

  function collectGroupsToInject() {
    const groups = [];

    // Matched (cochés)
    matchedList.querySelectorAll('.if-group-card').forEach(card => {
      const cb = card.querySelector('.if-group-select');
      if (!cb || !cb.checked) return;

      const activityId = parseInt(card.dataset.activityId);
      if (!activityId) return;

      const tasks = collectTasksFromCard(card);
      groups.push({
        activity_id: activityId,
        guarantor: card.dataset.guarantor || '',
        tasks,
      });
    });

    // Unmatched (assignés)
    unmatchedList.querySelectorAll('.if-group-card').forEach(card => {
      const sel = card.querySelector('.if-activity-select');
      if (!sel || !sel.value) return;

      const activityId = parseInt(sel.value);
      if (!activityId) return;

      const tasks = collectTasksFromCard(card);
      groups.push({
        activity_id: activityId,
        guarantor: card.dataset.guarantor || '',
        tasks,
      });
    });

    return groups;
  }

  function collectTasksFromCard(card) {
    // Récupérer les tâches depuis les données de l'analyse
    // On les stocke dans le DOM via data-group-index au moment du build
    const groupIndex = card.dataset.groupIndex;
    if (groupIndex !== undefined && analysisResult) {
      const analysis = analysisResult.analysis || {};
      const all = [...(analysis.matched_groups || []), ...(analysis.unmatched_groups || [])];
      const group = all[parseInt(groupIndex)];
      if (group) return group.tasks || [];
    }

    // Fallback : parcourir le tableau HTML
    const tasks = [];
    card.querySelectorAll('.if-tasks-tbody tr').forEach(tr => {
      const cells = tr.querySelectorAll('td');
      if (!cells[0]) return;
      const name = cells[0].querySelector('.if-task-name')?.textContent?.trim() || '';
      if (!name) return;

      const tools = [];
      cells[1]?.querySelectorAll('.if-tag-tool').forEach(tag => tools.push(tag.textContent.trim()));

      const doer = cells[2]?.textContent?.trim() || '';
      const skills = [];
      cells[3]?.querySelectorAll('.if-tag-skill').forEach(tag => skills.push(tag.textContent.trim()));

      tasks.push({ name, tools, doer: doer === '—' ? '' : doer, skills });
    });
    return tasks;
  }

  // ── Success / Error screens ────────────────────────────────────
  function showSuccessScreen(stats) {
    resultSuccess.classList.remove('hidden');
    resultError.classList.add('hidden');
    retryBtn.classList.add('hidden');

    resultStats.innerHTML = '';
    const items = [
      { num: stats.tasks_created || 0,        label: 'Tâches créées' },
      { num: stats.tools_created || 0,         label: 'Outils ajoutés' },
      { num: stats.roles_created || 0,         label: 'Rôles créés' },
      { num: stats.competencies_created || 0,  label: 'Compétences' },
      { num: stats.activities_updated || 0,    label: 'Activités mises à jour' },
    ];
    items.forEach(item => {
      const div = document.createElement('div');
      div.className = 'if-result-stat';
      div.innerHTML = `
        <span class="if-result-stat-num">${item.num}</span>
        <span class="if-result-stat-label">${item.label}</span>
      `;
      resultStats.appendChild(div);
    });

    goToScreen(4);
  }

  function showErrorScreen(msg) {
    resultSuccess.classList.add('hidden');
    resultError.classList.remove('hidden');
    resultErrorMsg.textContent = msg || 'Une erreur inattendue s\'est produite.';
    retryBtn.classList.remove('hidden');
    goToScreen(4);
  }

  // ── Collect tasks : amélioration avec data-group-index ─────────
  // On stocke l'index dans le card pour retrouver les données
  function buildMatchedCardWithIndex(group, index) {
    const card = buildMatchedCard(group);
    card.dataset.groupIndex = index;
    return card;
  }
  function buildUnmatchedCardWithIndex(group, index) {
    const card = buildUnmatchedCard(group);
    card.dataset.groupIndex = index;
    return card;
  }

  // Réécrire buildReviewScreen pour stocker les index
  function buildReviewScreen(data) {
    const analysis = data.analysis || {};
    const stats = data.stats || {};
    const matched = analysis.matched_groups || [];
    const unmatched = analysis.unmatched_groups || [];

    sumMatched.textContent = matched.length;
    sumUnmatched.textContent = unmatched.length;
    sumTasks.textContent = stats.total_tasks || 0;
    badgeMatched.textContent = matched.length;
    badgeUnmatched.textContent = unmatched.length;

    const notes = analysis.analysis_notes;
    if (notes) {
      aiNotesText.textContent = notes;
      aiNotes.classList.remove('hidden');
    } else {
      aiNotes.classList.add('hidden');
    }

    matchedList.innerHTML = '';
    matched.forEach((group, i) => {
      const card = buildMatchedCardWithIndex(group, i);
      matchedList.appendChild(card);
    });

    unmatchedList.innerHTML = '';
    const offset = matched.length;
    unmatched.forEach((group, i) => {
      const card = buildUnmatchedCardWithIndex(group, offset + i);
      unmatchedList.appendChild(card);
    });

    switchTab('matched');
    updateInjectPreview();
  }

  // ── Utils ──────────────────────────────────────────────────────
  function esc(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function showToast(msg, type = 'info') {
    // Simple toast using existing style (si pas de système de toast, alert en fallback)
    console.warn('[ImportFull]', type, msg);
    // Tenter d'utiliser un éventuel système de notification existant
    if (window.showNotification) {
      window.showNotification(msg, type);
    }
  }

  // ── Boot ───────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
