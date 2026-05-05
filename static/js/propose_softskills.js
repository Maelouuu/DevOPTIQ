// Code/static/js/propose_softskills.js

function fetchActivityDetailsForPropose(activityId) {
  showSpinner();
  fetch(`/activities/${activityId}/details`)
    .then(r => {
      if (!r.ok) {
        hideSpinner();
        throw new Error("Erreur /activities/details");
      }
      return r.json();
    })
    .then(data => {
      hideSpinner();
      proposeSoftskills(data);
    })
    .catch(err => {
      hideSpinner();
      console.error("Erreur fetchActivityDetailsForPropose:", err);
      alert("Impossible de récupérer les détails pour Proposer HSC");
    });
}

function proposeSoftskills(activityData) {
  showSpinner();
  fetch('/propose_softskills/propose', {
    method: 'POST',
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(activityData)
  })
  .then(r => {
    if (!r.ok) {
      hideSpinner();
      throw new Error("Erreur /propose_softskills/propose");
    }
    return r.json();
  })
  .then(resp => {
    hideSpinner();
    if (resp.error) {
      alert("Erreur proposition HSC : " + resp.error);
      return;
    }
    if (!resp.proposals || !Array.isArray(resp.proposals)) {
      alert("Réponse inattendue : 'proposals' manquant.");
      return;
    }
    showProposedSoftskills(resp.proposals, activityData.id);
  })
  .catch(err => {
    hideSpinner();
    console.error("Erreur proposeSoftskills:", err);
    alert("Erreur proposeSoftskills");
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getNiveauNum(niveau) {
  const m = String(niveau).match(/(\d)/);
  return m ? m[1] : "2";
}

function ensureHSCModal() {
  let overlay = document.getElementById("proposeHSCModalOverlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "proposeHSCModalOverlay";
    overlay.className = "modal-overlay-propose";
    overlay.style.display = "none";
    overlay.onclick = (e) => { if (e.target === overlay) overlay.style.display = 'none'; };

    const modal = document.createElement("div");
    modal.id = "proposeHSCModal";
    modal.className = "modal-content-propose modal-wide";
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
  }
  return overlay;
}

function showProposedSoftskills(hscProposals, activityId) {
  const overlay = ensureHSCModal();
  const modal = overlay.querySelector('#proposeHSCModal');

  modal.innerHTML = `
    <div class="modal-header-propose">
      <h3><i class="fa-solid fa-brain"></i> Propositions de HSC</h3>
      <button class="modal-close-btn-propose" id="closeHSCModalBtn">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    <div class="modal-body-propose">
      <table class="propose-table" id="hscProposalsTable">
        <thead>
          <tr>
            <th class="col-check"><input type="checkbox" id="hsc-select-all" checked></th>
            <th class="col-habilete">Habileté</th>
            <th class="col-niveau">Niveau</th>
            <th class="col-justification">Justification</th>
          </tr>
        </thead>
        <tbody id="hscProposalsBody"></tbody>
      </table>
    </div>
    <div class="modal-footer-propose">
      <button class="btn-modal-secondary-propose" id="cancelHSCBtn">
        <i class="fa-solid fa-xmark"></i> Annuler
      </button>
      <button class="btn-modal-primary-propose" id="validateHSCBtn">
        <i class="fa-solid fa-check"></i> Enregistrer la sélection
      </button>
    </div>
  `;

  const tbody = modal.querySelector('#hscProposalsBody');

  hscProposals.forEach((p, idx) => {
    const nNum = getNiveauNum(p.niveau);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="col-check">
        <input type="checkbox" data-idx="${idx}"
               data-habilete="${escapeHtml(p.habilete)}"
               data-niveau="${escapeHtml(p.niveau)}"
               data-justification="${escapeHtml(p.justification || '')}"
               checked />
      </td>
      <td class="col-habilete">${escapeHtml(p.habilete)}</td>
      <td class="col-niveau">
        <span class="badge-niveau badge-niveau-${nNum}">${escapeHtml(p.niveau)}</span>
      </td>
      <td class="col-justification">${escapeHtml(p.justification || '')}</td>
    `;
    tr.addEventListener('click', (e) => {
      if (e.target.tagName === 'INPUT') return;
      const cb = tr.querySelector('input[type="checkbox"]');
      cb.checked = !cb.checked;
      tr.classList.toggle('unchecked', !cb.checked);
      updateSelectAll();
    });
    tbody.appendChild(tr);
  });

  function updateSelectAll() {
    const all = modal.querySelectorAll('#hscProposalsBody input[type="checkbox"]');
    const checked = modal.querySelectorAll('#hscProposalsBody input[type="checkbox"]:checked');
    const selectAll = modal.querySelector('#hsc-select-all');
    selectAll.checked = all.length === checked.length;
    selectAll.indeterminate = checked.length > 0 && checked.length < all.length;
  }

  modal.querySelector('#hsc-select-all').addEventListener('change', (e) => {
    const isChecked = e.target.checked;
    modal.querySelectorAll('#hscProposalsBody input[type="checkbox"]').forEach(cb => {
      cb.checked = isChecked;
      cb.closest('tr').classList.toggle('unchecked', !isChecked);
    });
  });

  modal.querySelector('#closeHSCModalBtn').onclick = () => { overlay.style.display = 'none'; };
  modal.querySelector('#cancelHSCBtn').onclick = () => { overlay.style.display = 'none'; };

  modal.querySelector('#validateHSCBtn').onclick = () => {
    const selected = modal.querySelectorAll('#hscProposalsBody input[type="checkbox"]:checked');
    if (!selected.length) {
      alert("Veuillez sélectionner au moins une HSC.");
      return;
    }

    showSpinner();
    const addPromises = Array.from(selected).map(cb => {
      return fetch('/softskills/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          activity_id: activityId,
          habilete: cb.getAttribute('data-habilete'),
          niveau: cb.getAttribute('data-niveau'),
          justification: cb.getAttribute('data-justification') || ""
        })
      }).then(r => r.json()).catch(err => {
        console.error("Erreur lors de l'ajout de la softskill :", err);
      });
    });

    Promise.all(addPromises)
      .then(() => {
        hideSpinner();
        overlay.style.display = 'none';
        if (typeof refreshActivityItems === "function") {
          refreshActivityItems(activityId);
        }
        if (typeof updateSoftskillsList === "function") {
          updateSoftskillsList(activityId);
        }
      });
  };

  overlay.style.display = 'flex';
}
