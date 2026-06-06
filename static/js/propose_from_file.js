// static/js/propose_from_file.js
(function () {
  const safeShowSpinner = () => (typeof showSpinner === "function" ? showSpinner() : void 0);
  const safeHideSpinner = () => (typeof hideSpinner === "function" ? hideSpinner() : void 0);

  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }

  const SF_GROUPS  = ['Technical Skills', 'Functional Competencies'];
  const HSC_GROUPS = ['Behavioural Competencies', 'Leadership Competencies'];

  // ── Ref file status bar ──────────────────────────────────────────────────────

  async function initRefFileStatus() {
    try {
      const r = await fetch('/propose_from_file/status');
      const d = await r.json();
      document.querySelectorAll('[id^="ref-file-label-"]').forEach(el => {
        if (d.has_file) {
          const stats = d.stats || {};
          const sfCount  = SF_GROUPS.reduce((n, g)  => n + (stats[g] || 0), 0);
          const hscCount = HSC_GROUPS.reduce((n, g) => n + (stats[g] || 0), 0);
          const parts = [];
          if (sfCount)  parts.push(`${sfCount} compétences techniques`);
          if (hscCount) parts.push(`${hscCount} comportementales`);
          const detail = parts.length ? ` — ${parts.join(', ')}` : '';
          el.className = 'ref-file-bar-label has-file';
          el.innerHTML = `<i class="fa-solid fa-file-check"></i> Fichier DCP chargé${detail}`;
        } else {
          el.className = 'ref-file-bar-label no-file';
          el.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Aucun fichier DCP`;
        }
      });
    } catch (_) {}
  }

  // ── Upload modal ─────────────────────────────────────────────────────────────

  function _ensureRefFileModal() {
    let ov = document.getElementById('refFileModalOverlay');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'refFileModalOverlay';
      ov.className = 'modal-overlay-propose';
      ov.style.display = 'none';
      ov.onclick = (e) => { if (e.target === ov) ov.style.display = 'none'; };
      const dlg = document.createElement('div');
      dlg.id = 'refFileModal';
      dlg.className = 'modal-content-propose';
      ov.appendChild(dlg);
      document.body.appendChild(ov);
    }
    return ov;
  }

  function openRefFileModal() {
    const ov  = _ensureRefFileModal();
    const dlg = ov.querySelector('#refFileModal');

    dlg.innerHTML = `
      <div class="modal-header-propose">
        <h3><i class="fa-solid fa-folder-open" style="color:#764ba2"></i> Fichier DCP de référence</h3>
        <button class="modal-close-btn-propose" id="rfCloseBtn"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="modal-body-propose">

        <!-- Fichier actuel (affiché si un fichier est déjà chargé) -->
        <div id="rfCurrentFile" style="display:none; background:#f0fdf4; border:1px solid #86efac;
            border-radius:10px; padding:12px 16px; margin-bottom:16px;
            display:flex; align-items:center; justify-content:space-between; gap:12px;">
          <div>
            <div style="font-weight:700; color:#15803d; margin-bottom:3px; font-size:0.92rem;">
              <i class="fa-solid fa-file-check"></i> Fichier DCP chargé
            </div>
            <div id="rfCurrentDetail" style="font-size:0.8rem; color:#16a34a;"></div>
          </div>
          <button id="rfDeleteBtn" style="flex-shrink:0; background:#fff; border:1.5px solid #fca5a5;
              color:#ef4444; border-radius:7px; padding:5px 12px; cursor:pointer; font-size:0.82rem;
              display:flex; align-items:center; gap:5px; white-space:nowrap; transition:background 0.15s;">
            <i class="fa-solid fa-trash-can"></i> Supprimer
          </button>
        </div>

        <!-- Zone de dépôt -->
        <div id="rfDropZone" style="border:2.5px dashed #c4b5fd; border-radius:14px; background:#faf5ff;
            padding:30px 24px; text-align:center; cursor:pointer; transition:border-color 0.2s, background 0.2s;">
          <i class="fa-solid fa-cloud-arrow-up" style="font-size:2.2rem; color:#a78bfa; display:block; margin-bottom:10px;"></i>
          <p style="font-weight:700; color:#7c3aed; margin:0 0 5px; font-size:0.95rem;">
            Glisser-déposer un fichier Excel ici
          </p>
          <p style="font-size:0.78rem; color:#9ca3af; margin:0 0 18px;">
            Format .xlsx — colonnes attendues : JobText, GrpName, CompName
          </p>
          <button class="btn-propose-from-file" id="rfPickBtn">
            <i class="fa-solid fa-folder-open"></i> Parcourir
          </button>
          <input type="file" id="rfFileInput" accept=".xlsx,.xls" style="display:none" />
          <div id="rfSelectedFile" style="margin-top:12px; font-size:0.85rem; color:#7c3aed; font-weight:600; min-height:20px;"></div>
        </div>

        <div id="rfFeedback" style="margin-top:12px; font-size:0.88rem; min-height:20px;"></div>
      </div>
      <div class="modal-footer-propose">
        <button class="btn-modal-secondary-propose" id="rfCancelBtn">
          <i class="fa-solid fa-xmark"></i> Fermer
        </button>
        <button class="btn-modal-primary-propose" id="rfUploadBtn" disabled>
          <i class="fa-solid fa-floppy-disk"></i> Enregistrer
        </button>
      </div>
    `;

    const fileInput   = dlg.querySelector('#rfFileInput');
    const pickBtn     = dlg.querySelector('#rfPickBtn');
    const selectedLbl = dlg.querySelector('#rfSelectedFile');
    const uploadBtn   = dlg.querySelector('#rfUploadBtn');
    const feedback    = dlg.querySelector('#rfFeedback');
    const dropZone    = dlg.querySelector('#rfDropZone');
    const currentDiv  = dlg.querySelector('#rfCurrentFile');
    const currentDet  = dlg.querySelector('#rfCurrentDetail');
    const deleteBtn   = dlg.querySelector('#rfDeleteBtn');

    // Load and show current file status
    fetch('/propose_from_file/status').then(r => r.json()).then(d => {
      if (d.has_file) {
        const stats = d.stats || {};
        const sfC  = SF_GROUPS.reduce((n, g)  => n + (stats[g] || 0), 0);
        const hscC = HSC_GROUPS.reduce((n, g) => n + (stats[g] || 0), 0);
        currentDet.textContent = `${sfC} compétences techniques, ${hscC} comportementales`;
        currentDiv.style.display = 'flex';
      }
    }).catch(() => {});

    // Drag-and-drop on drop zone
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = '#7c3aed';
      dropZone.style.background  = '#ede9fe';
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.style.borderColor = '#c4b5fd';
      dropZone.style.background  = '#faf5ff';
    });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = '#c4b5fd';
      dropZone.style.background  = '#faf5ff';
      const f = e.dataTransfer.files[0];
      if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) {
        _setSelectedFile(f);
      } else if (f) {
        feedback.innerHTML = '<span style="color:#dc2626"><i class="fa-solid fa-triangle-exclamation"></i> Format non supporté — utilisez un fichier .xlsx</span>';
      }
    });
    dropZone.addEventListener('click', (e) => {
      if (e.target !== pickBtn && !pickBtn.contains(e.target)) fileInput.click();
    });

    function _setSelectedFile(f) {
      selectedLbl.innerHTML = `<i class="fa-solid fa-file-excel" style="color:#16a34a"></i> ${esc(f.name)}`;
      uploadBtn.disabled = false;
      uploadBtn._file = f;
      feedback.innerHTML = '';
    }

    pickBtn.onclick = (e) => { e.stopPropagation(); fileInput.click(); };
    fileInput.onchange = () => { if (fileInput.files[0]) _setSelectedFile(fileInput.files[0]); };

    dlg.querySelector('#rfCloseBtn').onclick  = () => { ov.style.display = 'none'; };
    dlg.querySelector('#rfCancelBtn').onclick = () => { ov.style.display = 'none'; };

    // Delete current file
    deleteBtn.onclick = async () => {
      if (!confirm('Supprimer le fichier DCP chargé ?')) return;
      deleteBtn.disabled = true;
      deleteBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      try {
        await fetch('/propose_from_file/delete', { method: 'DELETE' });
        currentDiv.style.display = 'none';
        selectedLbl.textContent = '';
        uploadBtn.disabled = true;
        feedback.innerHTML = '<span style="color:#6b7280"><i class="fa-solid fa-check"></i> Fichier supprimé.</span>';
        initRefFileStatus();
      } catch (_) {}
      finally {
        deleteBtn.disabled = false;
        deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i> Supprimer';
      }
    };

    // Upload
    uploadBtn.onclick = async () => {
      const f = uploadBtn._file || fileInput.files[0];
      if (!f) return;
      uploadBtn.disabled = true;
      uploadBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Envoi…';
      feedback.innerHTML = '';
      const fd = new FormData();
      fd.append('file', f);
      try {
        const r = await fetch('/propose_from_file/upload', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.ok) {
          const stats = d.stats || {};
          const sfC  = SF_GROUPS.reduce((n, g)  => n + (stats[g] || 0), 0);
          const hscC = HSC_GROUPS.reduce((n, g) => n + (stats[g] || 0), 0);
          feedback.innerHTML = `<span style="color:#22c55e">
            <i class="fa-solid fa-check"></i> Fichier enregistré — ${sfC} compétences techniques, ${hscC} comportementales.
          </span>`;
          uploadBtn.innerHTML = '<i class="fa-solid fa-check"></i> Enregistré';
          currentDet.textContent = `${sfC} compétences techniques, ${hscC} comportementales`;
          currentDiv.style.display = 'flex';
          initRefFileStatus();
          setTimeout(() => { ov.style.display = 'none'; }, 1600);
        } else {
          throw new Error(d.error || 'Erreur inconnue');
        }
      } catch (err) {
        feedback.innerHTML = `<span style="color:#dc2626"><i class="fa-solid fa-triangle-exclamation"></i> ${esc(err.message)}</span>`;
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Enregistrer';
      }
    };

    ov.style.display = 'flex';
  }

  function _noFileWarning() {
    alert('Aucun fichier DCP chargé. Veuillez d\'abord charger un fichier de référence via le bouton « Fichier DCP ».');
    openRefFileModal();
  }

  // ── Propose SF from file ─────────────────────────────────────────────────────

  async function proposeFromFileSF(activityId) {
    safeShowSpinner();
    try {
      const r = await fetch('/propose_from_file/propose_sf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activity_id: activityId }),
      });
      const d = await r.json();
      safeHideSpinner();
      if (d.error === 'no_file') { _noFileWarning(); return; }
      if (d.error) { alert('Erreur : ' + d.error); return; }
      const sfList = Array.isArray(d.proposals_sf) ? d.proposals_sf : [];
      const sList  = Array.isArray(d.proposals_s)  ? d.proposals_s  : [];
      if (typeof showProposedSavoirsFairesModal === 'function') {
        showProposedSavoirsFairesModal(sfList, sList, activityId);
      }
    } catch (err) {
      safeHideSpinner();
      console.error('proposeFromFileSF:', err);
      alert('Impossible d\'obtenir les propositions (voir console).');
    }
  }

  // ── Propose Aptitudes from file ──────────────────────────────────────────────

  function _ensureAptFileModal() {
    let ov = document.getElementById('proposeAptFileModalOverlay');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'proposeAptFileModalOverlay';
      ov.className = 'modal-overlay-propose';
      ov.style.display = 'none';
      ov.onclick = (e) => { if (e.target === ov) ov.style.display = 'none'; };
      const dlg = document.createElement('div');
      dlg.id = 'proposeAptFileModal';
      dlg.className = 'modal-content-propose';
      ov.appendChild(dlg);
      document.body.appendChild(ov);
    }
    return ov;
  }

  async function proposeFromFileAptitudes(activityId) {
    safeShowSpinner();
    try {
      const r = await fetch('/propose_from_file/propose_aptitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activity_id: activityId }),
      });
      const d = await r.json();
      safeHideSpinner();
      if (d.error === 'no_file') { _noFileWarning(); return; }
      if (d.error) { alert('Erreur : ' + d.error); return; }
      _showAptFileModal(Array.isArray(d.proposals) ? d.proposals : [], activityId);
    } catch (err) {
      safeHideSpinner();
      console.error('proposeFromFileAptitudes:', err);
      alert('Impossible d\'obtenir les propositions (voir console).');
    }
  }

  function _showAptFileModal(proposals, activityId) {
    const ov  = _ensureAptFileModal();
    const dlg = ov.querySelector('#proposeAptFileModal');

    const rows = proposals.length
      ? proposals.map(p => `
          <li>
            <label class="proposal-item-propose">
              <input type="checkbox" data-desc="${esc(p)}" checked />
              <span>${esc(p)}</span>
            </label>
          </li>`).join('')
      : `<li style="color:#999;">Aucune proposition disponible</li>`;

    dlg.innerHTML = `
      <div class="modal-header-propose">
        <h3><i class="fa-solid fa-file-lines" style="color:#764ba2"></i> Propositions Aptitudes — Fichier DCP</h3>
        <button class="modal-close-btn-propose" id="aptFCloseBtn"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="modal-body-propose">
        <ul class="proposals-list-propose">${rows}</ul>
      </div>
      <div class="modal-footer-propose">
        <button class="btn-modal-secondary-propose" id="aptFCancelBtn">
          <i class="fa-solid fa-xmark"></i> Annuler
        </button>
        <button class="btn-modal-primary-propose" id="aptFValidateBtn">
          <i class="fa-solid fa-check"></i> Enregistrer
        </button>
      </div>
    `;

    dlg.querySelector('#aptFCloseBtn').onclick  = () => { ov.style.display = 'none'; };
    dlg.querySelector('#aptFCancelBtn').onclick = () => { ov.style.display = 'none'; };

    dlg.querySelector('#aptFValidateBtn').onclick = async () => {
      const checked = dlg.querySelectorAll('input[type="checkbox"]:checked');
      if (!checked.length) { alert('Aucun élément sélectionné.'); return; }
      safeShowSpinner();
      try {
        await Promise.all(Array.from(checked).map(cb =>
          fetch('/aptitudes/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ activity_id: activityId, description: cb.dataset.desc }),
          })
        ));
        if (typeof refreshActivityItems === 'function') refreshActivityItems(activityId);
        if (typeof updateAptitudes === 'function') updateAptitudes(activityId);
        ov.style.display = 'none';
      } catch (err) {
        console.error('Erreur enregistrement aptitudes:', err);
        alert('Erreur lors de l\'enregistrement (voir console).');
      } finally {
        safeHideSpinner();
      }
    };

    ov.style.display = 'flex';
  }

  // ── Propose HSC from file ────────────────────────────────────────────────────

  function _ensureHscFileModal() {
    let ov = document.getElementById('proposeHscFileModalOverlay');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'proposeHscFileModalOverlay';
      ov.className = 'modal-overlay-propose';
      ov.style.display = 'none';
      ov.onclick = (e) => { if (e.target === ov) ov.style.display = 'none'; };
      const dlg = document.createElement('div');
      dlg.id = 'proposeHscFileModal';
      dlg.className = 'modal-content-propose modal-wide';
      ov.appendChild(dlg);
      document.body.appendChild(ov);
    }
    return ov;
  }

  async function proposeFromFileHSC(activityId) {
    safeShowSpinner();
    try {
      const r = await fetch('/propose_from_file/propose_hsc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activity_id: activityId }),
      });
      const d = await r.json();
      safeHideSpinner();
      if (d.error === 'no_file') { _noFileWarning(); return; }
      if (d.error) { alert('Erreur : ' + d.error); return; }
      _showHscFileModal(Array.isArray(d.proposals) ? d.proposals : [], activityId);
    } catch (err) {
      safeHideSpinner();
      console.error('proposeFromFileHSC:', err);
      alert('Impossible d\'obtenir les propositions (voir console).');
    }
  }

  function _showHscFileModal(proposals, activityId) {
    const ov  = _ensureHscFileModal();
    const dlg = ov.querySelector('#proposeHscFileModal');

    const nNum = (niveau) => { const m = String(niveau).match(/(\d)/); return m ? m[1] : '2'; };

    const rows = proposals.map((p, i) => `
      <tr>
        <td class="col-check">
          <input type="checkbox" data-idx="${i}"
            data-habilete="${esc(p.habilete)}"
            data-niveau="${esc(p.niveau)}"
            data-justification="${esc(p.justification || '')}"
            checked />
        </td>
        <td class="col-habilete">${esc(p.habilete)}</td>
        <td class="col-niveau"><span class="badge-niveau badge-niveau-${nNum(p.niveau)}">${esc(p.niveau)}</span></td>
        <td class="col-justification">${esc(p.justification || '')}</td>
      </tr>`).join('');

    dlg.innerHTML = `
      <div class="modal-header-propose">
        <h3><i class="fa-solid fa-file-lines" style="color:#764ba2"></i> Propositions SCA/HSC — Fichier DCP</h3>
        <button class="modal-close-btn-propose" id="hscFCloseBtn"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="modal-body-propose">
        <table class="propose-table">
          <thead>
            <tr>
              <th class="col-check"><input type="checkbox" id="hscFSelectAll" checked></th>
              <th class="col-habilete">Habileté</th>
              <th class="col-niveau">Niveau</th>
              <th class="col-justification">Justification</th>
            </tr>
          </thead>
          <tbody id="hscFBody">${rows || '<tr><td colspan="4" style="color:#999; text-align:center; padding:16px;">Aucune proposition</td></tr>'}</tbody>
        </table>
      </div>
      <div class="modal-footer-propose">
        <button class="btn-modal-secondary-propose" id="hscFCancelBtn">
          <i class="fa-solid fa-xmark"></i> Annuler
        </button>
        <button class="btn-modal-primary-propose" id="hscFValidateBtn">
          <i class="fa-solid fa-check"></i> Enregistrer la sélection
        </button>
      </div>
    `;

    dlg.querySelector('#hscFSelectAll').onchange = (e) => {
      dlg.querySelectorAll('#hscFBody input[type="checkbox"]').forEach(cb => {
        cb.checked = e.target.checked;
        cb.closest('tr').classList.toggle('unchecked', !e.target.checked);
      });
    };

    dlg.querySelectorAll('#hscFBody tr').forEach(tr => {
      tr.addEventListener('click', (e) => {
        if (e.target.tagName === 'INPUT') return;
        const cb = tr.querySelector('input[type="checkbox"]');
        if (!cb) return;
        cb.checked = !cb.checked;
        tr.classList.toggle('unchecked', !cb.checked);
      });
    });

    dlg.querySelector('#hscFCloseBtn').onclick  = () => { ov.style.display = 'none'; };
    dlg.querySelector('#hscFCancelBtn').onclick = () => { ov.style.display = 'none'; };

    dlg.querySelector('#hscFValidateBtn').onclick = async () => {
      const checked = dlg.querySelectorAll('#hscFBody input[type="checkbox"]:checked');
      if (!checked.length) { alert('Veuillez sélectionner au moins une HSC.'); return; }
      safeShowSpinner();
      try {
        await Promise.all(Array.from(checked).map(cb =>
          fetch('/softskills/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              activity_id: activityId,
              habilete: cb.dataset.habilete,
              niveau: cb.dataset.niveau,
              justification: cb.dataset.justification || '',
            }),
          })
        ));
        if (typeof refreshActivityItems === 'function') refreshActivityItems(activityId);
        if (typeof updateSoftskillsList === 'function') updateSoftskillsList(activityId);
        ov.style.display = 'none';
      } catch (err) {
        console.error('Erreur enregistrement HSC:', err);
        alert('Erreur lors de l\'enregistrement (voir console).');
      } finally {
        safeHideSpinner();
      }
    };

    ov.style.display = 'flex';
  }

  // ── Mode management (Standard vs Via fichier DCP) ────────────────────────────

  function getDcpMode() {
    return localStorage.getItem('propose_mode') || 'standard';
  }

  function setDcpMode(mode) {
    localStorage.setItem('propose_mode', mode);
    _updateModeToggleUI(mode);
    applyProposeModeToButtons();
  }

  function _updateModeToggleUI(mode) {
    const btnStd  = document.getElementById('btn-mode-standard');
    const btnFile = document.getElementById('btn-mode-file');
    const desc    = document.getElementById('dcp-mode-desc');
    if (btnStd)  btnStd.classList.toggle('dcp-mode-active',  mode === 'standard');
    if (btnFile) btnFile.classList.toggle('dcp-mode-active', mode === 'file');
    if (desc) {
      desc.textContent = mode === 'standard'
        ? "L'IA génère ses propositions librement en analysant le contexte de l'activité."
        : "L'IA sélectionne les meilleures correspondances parmi les compétences du fichier DCP chargé.";
    }
  }

  function applyProposeModeToButtons() {
    const mode = getDcpMode();
    document.querySelectorAll('[data-propose-type]').forEach(btn => {
      const icon = btn.querySelector('i.fa-solid');
      if (mode === 'file') {
        btn.classList.remove('btn-modal-primary-propose');
        btn.classList.add('btn-propose-from-file');
        if (icon) icon.className = 'fa-solid fa-file-lines';
      } else {
        btn.classList.remove('btn-propose-from-file');
        btn.classList.add('btn-modal-primary-propose');
        if (icon) icon.className = 'fa-solid fa-sparkles';
      }
    });
  }

  function dispatchPropose(type, activityId) {
    const mode = getDcpMode();
    if (mode === 'file') {
      const fileFns = { sf: proposeFromFileSF, aptitudes: proposeFromFileAptitudes, hsc: proposeFromFileHSC };
      if (fileFns[type]) fileFns[type](activityId);
    } else {
      const stdFns = {
        sf:        typeof fetchActivityDetailsForSavoirsFaires === 'function' ? fetchActivityDetailsForSavoirsFaires : null,
        aptitudes: typeof showProposedAptitudes                === 'function' ? showProposedAptitudes                : null,
        hsc:       typeof fetchActivityDetailsForPropose       === 'function' ? fetchActivityDetailsForPropose       : null,
      };
      if (stdFns[type]) stdFns[type](activityId);
    }
  }

  // ── Expose globally ───────────────────────────────────────────────────────────
  window.openRefFileModal         = openRefFileModal;
  window.initRefFileStatus        = initRefFileStatus;
  window.proposeFromFileSF        = proposeFromFileSF;
  window.proposeFromFileAptitudes = proposeFromFileAptitudes;
  window.proposeFromFileHSC       = proposeFromFileHSC;
  window.getDcpMode               = getDcpMode;
  window.setDcpMode               = setDcpMode;
  window.applyProposeModeToButtons = applyProposeModeToButtons;
  window.dispatchPropose          = dispatchPropose;

  // Auto-init
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initRefFileStatus();
      _updateModeToggleUI(getDcpMode());
      applyProposeModeToButtons();
    });
  } else {
    initRefFileStatus();
    _updateModeToggleUI(getDcpMode());
    applyProposeModeToButtons();
  }
})();
