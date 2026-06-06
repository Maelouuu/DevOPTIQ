// Code/static/js/competencies.js
const _PI_COMP = window.PROPOSE_I18N || {};
function _piComp(k, fb) { return _PI_COMP[k] || fb; }

function fetchActivityDetailsForSkills(activityId) {
  showSpinner();
  fetch(`/activities/${activityId}/details`)
    .then(response => {
      if (!response.ok) {
        hideSpinner();
        throw new Error("fetch failed");
      }
      return response.json();
    })
    .then(activityData => {
      hideSpinner();
      proposeSkills(activityData);
    })
    .catch(error => {
      hideSpinner();
      console.error("Erreur fetchActivityDetailsForSkills:", error);
      alert(_piComp('err_fetch_details', "Impossible de récupérer les détails de l'activité (voir console)."));
    });
}

/**
 * Appelle l'IA pour proposer des compétences (POST /skills/propose),
 * Puis ouvre le modal competencyModal avec checkboxes
 */
function proposeSkills(activityData) {
  showSpinner();
  fetch("/skills/propose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(activityData)
  })
  .then(response => {
    if (!response.ok) {
      return response.text().then(text => {
         throw new Error(`Réponse invalide de /skills/propose: ${text}`);
      });
    }
    return response.json();
  })
  .then(data => {
    hideSpinner();
    if (data.error) {
      console.error("Erreur IA /skills/propose:", data.error);
      return;
    }
    const lines = data.proposals;
    if (!lines || !Array.isArray(lines) || lines.length === 0) {
      alert(_piComp('err_no_proposals', "Aucune proposition retournée."));
      return;
    }
    showProposalsModal(lines, activityData.id);
  })
  .catch(err => {
    hideSpinner();
    console.error("Erreur lors de la proposition de compétences:", err);
    alert(_piComp('err_fetch_competencies', "Impossible d'obtenir des propositions de compétences (voir console)."));
  });
}


/** Ajout direct d'une compétence (via JSON) */
function addCompetency(activityId, description) {
  showSpinner();
  fetch("/skills/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ activity_id: activityId, description: description })
  })
  .then(res => res.json())
  .then(data => {
    hideSpinner();
    if (data.error) {
      console.error("Erreur addCompetency:", data.error);
    } else {
      addCompetencyItemToDOM(activityId, data.id, data.description);
    }
  })
  .catch(error => {
    hideSpinner();
    console.error("Erreur /skills/add:", error);
    alert(_piComp('err_add_competency', "Impossible d'ajouter la compétence (voir console)."));
  });
}


function addCompetencyItemToDOM(activityId, compId, desc) {
  const ul = document.getElementById(`competencies-list-${activityId}`);
  if (!ul) return;
  const safe = desc.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                   .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
  const li = document.createElement("li");
  li.setAttribute("data-comp-id", compId);
  li.className = "sf-item";
  li.innerHTML = `
    <div id="comp-display-${compId}" class="sf-display">
      <span class="sf-text">${safe}</span>
      <button class="icon-btn" onclick="editCompetency(this, ${compId})">
        <i class="fa-solid fa-pencil"></i>
      </button>
      <button class="icon-btn" onclick="deleteCompetency(this, ${compId})">
        <i class="fa-solid fa-trash"></i>
      </button>
    </div>
    <div class="sf-edit-area" id="edit-competency-form-${compId}" style="display:none;">
      <input type="text" class="sf-input" id="edit-competency-desc-${compId}" value="${safe}" />
      <button class="icon-btn" onclick="submitEditCompetency('${compId}')">
        <i class="fa-solid fa-check"></i>
      </button>
      <button class="icon-btn" onclick="hideEditCompetencyForm('${compId}')">
        <i class="fa-solid fa-xmark"></i>
      </button>
    </div>
  `;
  ul.appendChild(li);
}


/**
 * Afficher le formulaire d'édition existant
 */
function editCompetency(buttonElem, compId) {
  const formId = `edit-competency-form-${compId}`;
  const formDiv = document.getElementById(formId);
  if (formDiv) {
    formDiv.style.display = "block";
  }
}

/**
 * Cacher le formulaire d'édition
 */
function hideEditCompetencyForm(compId) {
  const formDiv = document.getElementById(`edit-competency-form-${compId}`);
  if (formDiv) {
    formDiv.style.display = "none";
  }
}


/**
 * Valider la modification
 */
function submitEditCompetency(compId) {
  const inputEl = document.getElementById(`edit-competency-desc-${compId}`);
  if (!inputEl) return;
  const newDesc = inputEl.value.trim();
  if (!newDesc) {
    alert(_piComp('select_one', "Veuillez saisir la description de la compétence"));
    return;
  }
  showSpinner();
  fetch(`/skills/${compId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description: newDesc })
  })
  .then(resp => resp.json())
  .then(data => {
    hideSpinner();
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      // Mettre à jour l'affichage
      const li = document.querySelector(`li[data-comp-id='${compId}']`);
      if (li) {
        const span = li.querySelector(".validated-skill-text");
        if (span) span.textContent = data.description;
        hideEditCompetencyForm(compId);
      }
    }
  })
  .catch(err => {
    hideSpinner();
    console.error("Erreur submitEditCompetency:", err);
  });
}


/**
 * Supprimer la compétence
 */
function deleteCompetency(buttonElem, compId) {
  if (!confirm(_piComp('confirm_delete_competency', "Supprimer cette compétence ?"))) return;
  showSpinner();
  fetch(`/skills/${compId}`, { method: "DELETE" })
  .then(resp => resp.json())
  .then(data => {
    hideSpinner();
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      // Supprimer du DOM
      const li = document.querySelector(`li[data-comp-id='${compId}']`);
      if (li) li.remove();
    }
  })
  .catch(err => {
    hideSpinner();
    console.error("Erreur suppression compétence:", err);
  });
}
