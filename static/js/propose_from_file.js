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
        <p style="color:#555; margin-bottom:14px;">
          Chargez un fichier Excel (.xlsx) contenant les compétences de référence.<br>
          <span style="font-size:0.82rem; color:#888;">Colonnes attendues : ObjectID, JobId, JobText, GrpName, CompName, Required Score</span>
        </p>
        <div id="rfCurrentStatus" style="margin-bottom:14px; font-size:0.88rem; color:#764ba2;">
          <i class="fa-solid fa-circle-notch fa-spin"></i> Chargement…
        </div>
        <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
          <input type="file" id="rfFileInput" accept=".xlsx,.xls" style="display:none" />
          <button class="btn-propose-from-file" id="rfPickBtn">
            <i class="fa-solid fa-upload"></i> Choisir un fichier
          </button>
          <span id="rfFileName" style="font-size:0.88rem; color:#555;"></span>
        </div>
        <div id="rfFeedback" style="margin-top:12px; font-size:0.88rem;"></div>
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

    // Load current status
    fetch('/propose_from_file/status').then(r => r.json()).then(d => {
      const el = dlg.querySelector('#rfCurrentStatus');
      if (d.has_file) {
        const stats = d.stats || {};
        const sfC  = SF_GROUPS.reduce((n, g)  => n + (stats[g] || 0), 0);
        const hscC = HSC_GROUPS.reduce((n, g) => n + (stats[g] || 0), 0);
        el.innerHTML = `<i class="fa-solid fa-file-check"></i> Fichier actuel : ${sfC} compétences techniques, ${hscC} comportementales`;
      } else {
        el.innerHTML = `<span style="color:#aaa"><i class="fa-solid fa-inbox"></i> Aucun fichier chargé</span>`;
      }
    }).catch(() => { dlg.querySelector('#rfCurrentStatus').innerHTML = ''; });

    const fileInput = dlg.querySelector('#rfFileInput');
    const pickBtn   = dlg.querySelector('#rfPickBtn');
    const nameLbl   = dlg.querySelector('#rfFileName');
    const uploadBtn = dlg.querySelector('#rfUploadBtn');
    const feedback  = dlg.querySelector('#rfFeedback');

    pickBtn.onclick  = () => fileInput.click();
    dlg.querySelector('#rfCloseBtn').onclick  = () => { ov.style.display = 'none'; };
    dlg.querySelector('#rfCancelBtn').onclick = () => { ov.style.display = 'none'; };

    fileInput.onchange = () => {
      const f = fileInput.files[0];
      if (f) { nameLbl.textContent = f.name; uploadBtn.disabled = false; feedback.innerHTML = ''; }
    };

    uploadBtn.onclick = async () => {
      const f = fileInput.files[0];
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
          initRefFileStatus();
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

  // ── Expose globally ───────────────────────────────────────────────────────────
  window.openRefFileModal         = openRefFileModal;
  window.initRefFileStatus        = initRefFileStatus;
  window.proposeFromFileSF        = proposeFromFileSF;
  window.proposeFromFileAptitudes = proposeFromFileAptitudes;
  window.proposeFromFileHSC       = proposeFromFileHSC;

  // Auto-init status bar on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRefFileStatus);
  } else {
    initRefFileStatus();
  }
})();
