/* ============================================================
   OPTIQ — Import de tâches (CSV / JSON / Excel)
   ============================================================ */

(function () {
  'use strict';

  // ── État ──────────────────────────────────────────────────
  let currentFmt       = 'csv';
  let lastResults      = [];   // résultats de validation

  // ── Références DOM ────────────────────────────────────────
  const overlay    = () => document.getElementById('import-tasks-overlay');
  const step1      = () => document.getElementById('import-step-1');
  const step2      = () => document.getElementById('import-step-2');
  const textarea   = () => document.getElementById('import-textarea');
  const fileInput  = () => document.getElementById('import-file-input');
  const fileName   = () => document.getElementById('import-file-name');
  const parseErr   = () => document.getElementById('import-parse-error');
  const stepLabel  = () => document.getElementById('import-step-label');
  const summaryBar = () => document.getElementById('import-summary-bar');
  const tableBody  = () => document.getElementById('import-table-body');
  const injectBtn  = () => document.getElementById('import-inject-btn');
  const injectWarn = () => document.getElementById('import-inject-warning');
  const injectCount= () => document.getElementById('import-inject-count');

  // ── Ouverture / Fermeture ─────────────────────────────────
  window.openImportModal = function () {
    _reset();
    overlay().classList.add('active');
    document.body.style.overflow = 'hidden';
  };

  window.closeImportModal = function () {
    overlay().classList.remove('active');
    document.body.style.overflow = '';
  };

  // Fermer en cliquant l'overlay
  document.addEventListener('DOMContentLoaded', function () {
    const ov = overlay();
    if (!ov) return;
    ov.addEventListener('click', function (e) {
      if (e.target === ov) closeImportModal();
    });
  });

  function _reset() {
    currentFmt  = 'csv';
    lastResults = [];
    if (textarea())  textarea().value = '';
    if (fileName())  fileName().textContent = '';
    if (parseErr())  parseErr().textContent = '';
    _setFmtUI('csv');
    _showStep(1);
  }

  // ── Sélection du format ────────────────────────────────────
  window.setImportFmt = function (fmt) {
    currentFmt = fmt;
    _setFmtUI(fmt);
  };

  function _setFmtUI(fmt) {
    document.getElementById('fmt-btn-csv')?.classList.toggle('active', fmt === 'csv');
    document.getElementById('fmt-btn-json')?.classList.toggle('active', fmt === 'json');
    const hintCsv  = document.getElementById('import-hint-csv');
    const hintJson = document.getElementById('import-hint-json');
    if (hintCsv)  hintCsv.style.display  = fmt === 'csv'  ? '' : 'none';
    if (hintJson) hintJson.style.display  = fmt === 'json' ? '' : 'none';
  }

  // ── Navigation entre étapes ───────────────────────────────
  function _showStep(n) {
    step1().style.display = n === 1 ? '' : 'none';
    step2().style.display = n === 2 ? '' : 'none';
    stepLabel().textContent = n === 1
      ? 'Étape 1 — Chargement des données'
      : 'Étape 2 — Résultats de validation';
  }

  window.backToImportStep1 = function () {
    _showStep(1);
  };

  // ── Drag & Drop ────────────────────────────────────────────
  window.handleImportDrop = function (e) {
    e.preventDefault();
    const dz = document.getElementById('import-dropzone');
    if (dz) dz.classList.remove('drag-over');
    const file = e.dataTransfer?.files?.[0];
    if (file) _loadFile(file);
  };

  // ── Sélection fichier ─────────────────────────────────────
  window.handleImportFile = function (e) {
    const file = e.target.files?.[0];
    if (file) _loadFile(file);
    // reset input pour permettre re-sélection du même fichier
    e.target.value = '';
  };

  function _loadFile(file) {
    const name = file.name.toLowerCase();
    if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
      _loadExcel(file);
    } else {
      const reader = new FileReader();
      reader.onload = function (e) {
        const content = e.target.result;
        textarea().value = content;
        if (fileName()) fileName().textContent = file.name;
        // Auto-detect format
        if (name.endsWith('.json')) {
          currentFmt = 'json';
          _setFmtUI('json');
        } else {
          currentFmt = 'csv';
          _setFmtUI('csv');
        }
      };
      reader.readAsText(file, 'UTF-8');
    }
  }

  function _loadExcel(file) {
    if (typeof XLSX === 'undefined') {
      if (parseErr()) parseErr().textContent = 'Librairie XLSX non disponible. Utilisez CSV ou JSON.';
      return;
    }
    const reader = new FileReader();
    reader.onload = function (e) {
      try {
        const wb  = XLSX.read(e.target.result, { type: 'array' });
        const ws  = wb.Sheets[wb.SheetNames[0]];
        const csv = XLSX.utils.sheet_to_csv(ws);
        textarea().value = csv;
        if (fileName()) fileName().textContent = file.name + ' (converti en CSV)';
        currentFmt = 'csv';
        _setFmtUI('csv');
      } catch (err) {
        if (parseErr()) parseErr().textContent = 'Erreur lecture Excel : ' + err.message;
      }
    };
    reader.readAsArrayBuffer(file);
  }

  // ── Téléchargement du modèle ──────────────────────────────
  window.downloadImportTemplate = function () {
    let content, filename, type;

    if (currentFmt === 'json') {
      content = JSON.stringify([
        {
          nom: 'Saisir la demande client',
          activite: 'Nom de l\'activité',
          description: 'Description optionnelle',
          outils: ['SAP', 'Excel'],
          entree: { nom: 'Bon de commande', type: 'nourrissante' },
          sortie: { nom: 'Demande traitée', type: 'nourrissante', activite_cible: 'Activité suivante' },
        },
        {
          nom: 'Valider la commande',
          activite: 'Nom de l\'activité',
          description: '',
          outils: ['SAP'],
          entree: null,
          sortie: { nom: 'Commande validée', type: 'descendante', activite_cible: '' },
        },
      ], null, 2);
      filename = 'modele_import_taches.json';
      type     = 'application/json';
    } else {
      const rows = [
        'nom_tache,activite,description,outils,entree_nom,entree_type,sortie_nom,sortie_type,sortie_activite_cible',
        'Saisir la demande client,Nom de l\'activité,Description optionnelle,SAP;Excel,Bon de commande,nourrissante,Demande traitée,nourrissante,Activité suivante',
        'Valider la commande,Nom de l\'activité,,SAP,,,Commande validée,descendante,',
      ];
      content  = rows.join('\n');
      filename = 'modele_import_taches.csv';
      type     = 'text/csv;charset=utf-8;';
    }

    const blob = new Blob(['\ufeff' + content], { type });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Analyse (appel API validate) ──────────────────────────
  window.analyzeImportData = function () {
    const content = textarea()?.value?.trim();
    if (parseErr()) parseErr().textContent = '';

    if (!content) {
      if (parseErr()) parseErr().textContent = 'Aucun contenu à analyser.';
      return;
    }

    const analyzeBtn = document.querySelector('#import-step-1 .import-btn-primary');
    if (analyzeBtn) {
      analyzeBtn.disabled = true;
      analyzeBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyse…';
    }

    fetch('/api/import-tasks/validate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ format: currentFmt, content }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          if (parseErr()) parseErr().textContent = data.error;
          return;
        }
        lastResults = data.results;
        _renderResults(data.results, data.summary);
        _showStep(2);
      })
      .catch(err => {
        if (parseErr()) parseErr().textContent = 'Erreur réseau : ' + err.message;
      })
      .finally(() => {
        if (analyzeBtn) {
          analyzeBtn.disabled = false;
          analyzeBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass-chart"></i> Analyser';
        }
      });
  };

  // ── Rendu de la table de résultats ────────────────────────
  function _renderResults(results, summary) {
    // Summary bar
    summaryBar().innerHTML = `
      <div class="import-summary-inner">
        <span class="import-sum-pill ok">
          <i class="fa-solid fa-check"></i> ${summary.ok} tâche${summary.ok > 1 ? 's' : ''} OK
        </span>
        ${summary.warning > 0 ? `
          <span class="import-sum-pill warning">
            <i class="fa-solid fa-triangle-exclamation"></i>
            ${summary.warning} avertissement${summary.warning > 1 ? 's' : ''}
          </span>` : ''}
        ${summary.error > 0 ? `
          <span class="import-sum-pill error">
            <i class="fa-solid fa-circle-xmark"></i>
            ${summary.error} erreur${summary.error > 1 ? 's' : ''} bloquante${summary.error > 1 ? 's' : ''}
          </span>` : ''}
        <span class="import-sum-total">${summary.total} ligne${summary.total > 1 ? 's' : ''} au total</span>
      </div>
    `;

    // Table body
    const tbody = tableBody();
    tbody.innerHTML = '';

    results.forEach(r => {
      // Ligne principale
      const tr = document.createElement('tr');
      tr.className = 'import-data-row ' + r.status;

      const actIcon  = r.activity_id
        ? '<i class="fa-solid fa-check import-cell-ok"></i>'
        : '<i class="fa-solid fa-xmark import-cell-err"></i>';

      const toolsHtml = r.outils && r.outils.length
        ? r.outils.map(t => `<span class="import-tool-pill">${_esc(t)}</span>`).join('')
        : '<span class="import-empty">—</span>';

      const entreeHtml = r.entree
        ? `<span class="import-conn-name">${_esc(r.entree.nom)}</span>
           <span class="import-conn-type">${_esc(r.entree.type)}</span>`
        : '<span class="import-empty">—</span>';

      const sortieHtml = r.sortie
        ? `<span class="import-conn-name">${_esc(r.sortie.nom)}</span>
           <span class="import-conn-type">${_esc(r.sortie.type)}</span>
           ${r.sortie.activite_cible
             ? `<span class="import-conn-target">→ ${_esc(r.sortie.activite_cible)}</span>`
             : ''}`
        : '<span class="import-empty">—</span>';

      const statusHtml = r.status === 'ok'
        ? '<span class="import-status-pill ok"><i class="fa-solid fa-check"></i> OK</span>'
        : r.status === 'warning'
          ? '<span class="import-status-pill warning"><i class="fa-solid fa-triangle-exclamation"></i> Avert.</span>'
          : '<span class="import-status-pill error"><i class="fa-solid fa-xmark"></i> Erreur</span>';

      tr.innerHTML = `
        <td class="col-row">${r.row}</td>
        <td class="col-task">${_esc(r.nom_tache || '—')}</td>
        <td class="col-activity">${actIcon} ${_esc(r.activite || '—')}</td>
        <td class="col-tools">${toolsHtml}</td>
        <td class="col-in">${entreeHtml}</td>
        <td class="col-out">${sortieHtml}</td>
        <td class="col-status">${statusHtml}</td>
      `;
      tbody.appendChild(tr);

      // Ligne d'issues (erreurs + avertissements)
      const issues = [...(r.errors || []).map(e => ({ type: 'error', msg: e })),
                      ...(r.warnings || []).map(w => ({ type: 'warning', msg: w }))];
      if (issues.length) {
        const trIssues = document.createElement('tr');
        trIssues.className = 'import-issues-row';
        const td = document.createElement('td');
        td.colSpan = 7;
        td.innerHTML = issues.map(issue =>
          `<span class="import-issue-item ${issue.type}">
             <i class="fa-solid ${issue.type === 'error' ? 'fa-circle-xmark' : 'fa-triangle-exclamation'}"></i>
             ${_esc(issue.msg)}
           </span>`
        ).join('');
        trIssues.appendChild(td);
        tbody.appendChild(trIssues);
      }
    });

    // Bouton injecter
    const validCount = results.filter(r => r.status !== 'error').length;
    if (injectCount()) injectCount().textContent = validCount;

    if (!summary.can_inject) {
      injectBtn().disabled = true;
      injectBtn().classList.add('disabled');
      if (injectWarn()) injectWarn().textContent =
        `${summary.error} erreur${summary.error > 1 ? 's' : ''} bloquante${summary.error > 1 ? 's' : ''} — corrigez le fichier source avant d'injecter`;
    } else {
      injectBtn().disabled = false;
      injectBtn().classList.remove('disabled');
      if (injectWarn()) injectWarn().textContent = '';
    }
  }

  // ── Injection ─────────────────────────────────────────────
  window.executeImport = function () {
    if (!lastResults.length) return;

    const btn = injectBtn();
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Injection…';

    fetch('/api/import-tasks/inject', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ results: lastResults }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Erreur — réessayer';
          if (injectWarn()) injectWarn().textContent = data.error;
          return;
        }
        // Succès
        btn.innerHTML = `<i class="fa-solid fa-check"></i> ${data.count} tâche${data.count > 1 ? 's' : ''} ajoutée${data.count > 1 ? 's' : ''} !`;
        btn.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';

        if (injectWarn()) injectWarn().textContent = '';

        // Afficher le résumé de succès dans la summary bar
        summaryBar().innerHTML = `
          <div class="import-summary-inner import-success">
            <i class="fa-solid fa-circle-check"></i>
            <strong>${data.count} tâche${data.count > 1 ? 's' : ''} importée${data.count > 1 ? 's' : ''} avec succès !</strong>
            La page va se rafraîchir…
          </div>
        `;

        setTimeout(() => location.reload(), 1800);
      })
      .catch(err => {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Erreur — réessayer';
        if (injectWarn()) injectWarn().textContent = 'Erreur réseau : ' + err.message;
      });
  };

  // ── Utilitaires ───────────────────────────────────────────
  function _esc(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

})();
