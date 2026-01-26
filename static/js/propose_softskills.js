// Code/static/js/propose_softskills.js

/**
 * Analyse l'activité, appelle /propose_softskills/propose (non fourni ici)
 * et affiche le résultat dans un modal => checkboxes => /softskills/add
 * 
 * => A titre d'exemple, si ton code actuel s'appelle autrement, 
 *    adapte ou supprime ce fichier. 
 */

function fetchActivityDetailsForPropose(activityId) {
  showSpinner();
  // On appelle /activities/<activityId>/details pour un JSON complet
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
    // On ouvre un modal similaire à la traduction ?
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

function ensureHSCModal() {
  let overlay = document.getElementById("proposeHSCModalOverlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "proposeHSCModalOverlay";
    overlay.className = "modal-overlay-propose";
    overlay.style.display = "none";
    overlay.onclick = (e) => { if(e.target === overlay) overlay.style.display = 'none'; };

    const modal = document.createElement("div");
    modal.id = "proposeHSCModal";
    modal.className = "modal-content-propose";
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
      <h3><i class="fa-solid fa-sparkles"></i> Propositions de HSC</h3>
      <button class="modal-close-btn-propose" id="closeHSCModalBtn">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
    <div class="modal-body-propose">
      <ul id="hscProposalsList" class="proposals-list-propose"></ul>
    </div>
    <div class="modal-footer-propose">
      <button class="btn-modal-secondary-propose" id="cancelHSCBtn">
        <i class="fa-solid fa-xmark"></i> Annuler
      </button>
      <button class="btn-modal-primary-propose" id="validateHSCBtn">
        <i class="fa-solid fa-check"></i> Enregistrer
      </button>
    </div>
  `;

  const listEl = modal.querySelector('#hscProposalsList');
  listEl.innerHTML = "";

  hscProposals.forEach((p, idx) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <label class="proposal-item-propose">
        <input type="checkbox"
               data-idx="${idx}"
               data-habilete="${escapeHtml(p.habilete)}"
               data-niveau="${escapeHtml(p.niveau)}"
               data-justification="${escapeHtml(p.justification || '')}"
               checked />
        <span><strong>${escapeHtml(p.habilete)}</strong> - Niveau: ${escapeHtml(p.niveau)}</span>
      </label>
    `;
    listEl.appendChild(li);
  });

  modal.querySelector('#closeHSCModalBtn').onclick = () => {
    overlay.style.display = 'none';
  };
  modal.querySelector('#cancelHSCBtn').onclick = () => {
    overlay.style.display = 'none';
  };

  modal.querySelector('#validateHSCBtn').onclick = () => {
    const selected = listEl.querySelectorAll('input[type="checkbox"]:checked');
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
