// Code/static/js/translate_softskills.js

function openTranslateSoftskillsModal(activityId) {
  window.translateSoftskillsActivityId = activityId;
  // Reset to input view
  const inputView = document.getElementById('translateInputView');
  const resultsView = document.getElementById('translateResultsView');
  const submitBtn = document.getElementById('translateSubmitBtn');
  if (inputView) inputView.style.display = '';
  if (resultsView) { resultsView.style.display = 'none'; resultsView.innerHTML = ''; }
  if (submitBtn) {
    submitBtn.style.display = '';
    submitBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Traduire';
    submitBtn.onclick = submitSoftskillsTranslation;
  }
  const inputElem = document.getElementById('translateSoftskillsInput');
  if (inputElem) inputElem.value = '';

  document.getElementById('translateSoftskillsOverlay').style.display = 'flex';
}

function closeTranslateSoftskillsModal() {
  document.getElementById('translateSoftskillsOverlay').style.display = 'none';
  window.translateSoftskillsActivityId = null;
}

function _escapeHtmlT(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function _getNiveauNumT(niveau) {
  const m = String(niveau).match(/(\d)/);
  return m ? m[1] : "2";
}

function submitSoftskillsTranslation() {
  const activityId = window.translateSoftskillsActivityId;
  if (!activityId) {
    alert("Erreur : activityId introuvable.");
    return;
  }

  const userInputElem = document.getElementById('translateSoftskillsInput');
  const userInput = (userInputElem?.value || "").trim();
  if (!userInput) {
    alert("Veuillez saisir quelque chose dans le champ des soft skills.");
    return;
  }

  const savedActivityId = activityId;

  // Show loading in modal body
  const inputView = document.getElementById('translateInputView');
  const resultsView = document.getElementById('translateResultsView');
  const submitBtn = document.getElementById('translateSubmitBtn');

  inputView.style.display = 'none';
  resultsView.style.display = '';
  resultsView.innerHTML = `
    <div class="modal-loading">
      <div class="spinner-ring"></div>
      <span>Analyse en cours...</span>
    </div>
  `;
  if (submitBtn) submitBtn.style.display = 'none';

  // (1) Fetch activity details
  fetch(`/activities/${savedActivityId}/details`)
    .then(resp => {
      if (!resp.ok) throw new Error("Erreur lors de la récupération du contexte.");
      return resp.json();
    })
    .then(activityData => {
      if (activityData.error) throw new Error(activityData.error);

      const payload = {
        user_input: userInput,
        activity_data: {
          name: activityData.name,
          tasks: activityData.tasks || [],
          constraints: activityData.constraints || [],
          outgoing: activityData.outgoing || []
        }
      };

      return fetch('/translate_softskills/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    })
    .then(resp => {
      if (!resp.ok) throw new Error("Réponse non OK de /translate_softskills/translate");
      return resp.json();
    })
    .then(data => {
      if (data.error) throw new Error(data.error);
      const proposals = data.proposals;
      if (!proposals || !Array.isArray(proposals) || proposals.length === 0) {
        throw new Error("L'IA n'a renvoyé aucune HSC.");
      }

      // Render table
      showTranslateResults(proposals, savedActivityId);
    })
    .catch(err => {
      console.error("Erreur traduction HSC:", err);
      resultsView.innerHTML = `
        <div style="text-align:center; padding:30px; color:#dc2626;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size:1.5rem; margin-bottom:10px; display:block;"></i>
          <p>${_escapeHtmlT(err.message)}</p>
        </div>
      `;
      // Show a "Retour" button
      if (submitBtn) {
        submitBtn.style.display = '';
        submitBtn.innerHTML = '<i class="fa-solid fa-arrow-left"></i> Retour';
        submitBtn.onclick = () => {
          inputView.style.display = '';
          resultsView.style.display = 'none';
          submitBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Traduire';
          submitBtn.onclick = submitSoftskillsTranslation;
        };
      }
    });
}

function showTranslateResults(proposals, activityId) {
  const resultsView = document.getElementById('translateResultsView');
  const submitBtn = document.getElementById('translateSubmitBtn');

  let tableRows = '';
  proposals.forEach((p, idx) => {
    const nNum = _getNiveauNumT(p.niveau);
    tableRows += `
      <tr>
        <td class="col-check">
          <input type="checkbox" data-idx="${idx}"
                 data-habilete="${_escapeHtmlT(p.habilete)}"
                 data-niveau="${_escapeHtmlT(p.niveau)}"
                 data-justification="${_escapeHtmlT(p.justification || '')}"
                 checked />
        </td>
        <td class="col-habilete">${_escapeHtmlT(p.habilete)}</td>
        <td class="col-niveau">
          <span class="badge-niveau badge-niveau-${nNum}">${_escapeHtmlT(p.niveau)}</span>
        </td>
        <td class="col-justification">${_escapeHtmlT(p.justification || '')}</td>
      </tr>
    `;
  });

  resultsView.innerHTML = `
    <table class="propose-table">
      <thead>
        <tr>
          <th class="col-check"><input type="checkbox" id="translate-select-all" checked></th>
          <th class="col-habilete">Habileté</th>
          <th class="col-niveau">Niveau</th>
          <th class="col-justification">Justification</th>
        </tr>
      </thead>
      <tbody id="translateResultsBody">${tableRows}</tbody>
    </table>
  `;

  // Row click toggle
  resultsView.querySelectorAll('#translateResultsBody tr').forEach(tr => {
    tr.addEventListener('click', (e) => {
      if (e.target.tagName === 'INPUT') return;
      const cb = tr.querySelector('input[type="checkbox"]');
      cb.checked = !cb.checked;
      tr.classList.toggle('unchecked', !cb.checked);
      updateTranslateSelectAll();
    });
  });

  function updateTranslateSelectAll() {
    const all = resultsView.querySelectorAll('#translateResultsBody input[type="checkbox"]');
    const checked = resultsView.querySelectorAll('#translateResultsBody input[type="checkbox"]:checked');
    const selectAll = resultsView.querySelector('#translate-select-all');
    selectAll.checked = all.length === checked.length;
    selectAll.indeterminate = checked.length > 0 && checked.length < all.length;
  }

  resultsView.querySelector('#translate-select-all').addEventListener('change', (e) => {
    const isChecked = e.target.checked;
    resultsView.querySelectorAll('#translateResultsBody input[type="checkbox"]').forEach(cb => {
      cb.checked = isChecked;
      cb.closest('tr').classList.toggle('unchecked', !isChecked);
    });
  });

  // Change submit button to "Enregistrer"
  if (submitBtn) {
    submitBtn.style.display = '';
    submitBtn.innerHTML = '<i class="fa-solid fa-check"></i> Enregistrer la sélection';
    submitBtn.onclick = () => {
      const selected = resultsView.querySelectorAll('#translateResultsBody input[type="checkbox"]:checked');
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
        })
        .then(r => r.json())
        .catch(err => console.error("Erreur /softskills/add:", err));
      });

      Promise.all(addPromises)
        .then(() => {
          hideSpinner();
          closeTranslateSoftskillsModal();
          if (typeof updateSoftskillsList === "function") {
            updateSoftskillsList(activityId);
          }
          if (typeof refreshActivityItems === "function") {
            refreshActivityItems(activityId);
          }
        });
    };
  }
}
