// Code/static/js/constraints.js

function showAddConstraintForm(activityId) {
  document.getElementById("add-constraint-form-" + activityId).style.display = "block";
  // Init le file-picker si pas encore fait
  const picker = document.getElementById("add-fp-" + activityId);
  if (picker) initFilePicker(picker);
}

function hideAddConstraintForm(activityId) {
  document.getElementById("add-constraint-form-" + activityId).style.display = "none";
  const inputElem = document.getElementById("add-constraint-input-" + activityId);
  if (inputElem) inputElem.value = "";
  const picker = document.getElementById("add-fp-" + activityId);
  if (picker) fpReset(picker);
}

// Soumission de l'ajout
function submitAddConstraint(activityId) {
  const inputElem = document.getElementById("add-constraint-input-" + activityId);
  if (!inputElem) return;
  const desc = inputElem.value.trim();
  if (!desc) {
    alert("Veuillez saisir une description de contrainte.");
    return;
  }
  const picker   = document.getElementById("add-fp-" + activityId);
  const filePath = picker ? fpGetPath(picker) : "";

  fetch(`/constraints/${activityId}/add`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description: desc, file_path: filePath || null })
  })
  .then(resp => resp.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      hideAddConstraintForm(activityId);
      updateConstraints(activityId);
    }
  })
  .catch(err => {
    console.error("Erreur lors de l'ajout de la contrainte :", err);
  });
}

// Rafraîchit le bloc des contraintes (HTML partiel)
function updateConstraints(activityId) {
  fetch(`/constraints/${activityId}/render`)
    .then(response => {
      if (!response.ok) throw new Error("Erreur lors du rafraîchissement des contraintes.");
      return response.text();
    })
    .then(html => {
      document.getElementById("constraints-container-" + activityId).innerHTML = html;
      // Init les file-pickers des formulaires d'édition fraîchement injectés
      document.querySelectorAll(
        "#constraints-container-" + activityId + " .fp-wrap"
      ).forEach(initFilePicker);
      hideAddConstraintForm(activityId);
    })
    .catch(err => {
      console.error("Erreur lors du rafraîchissement des contraintes :", err);
      alert(err.message);
    });
}

/* ============== ÉDITION ET SUPPRESSION ============== */

function showEditConstraintForm(btnElem) {
  const constraintStr = btnElem.getAttribute("data-constraint");
  let constraintObj;
  try {
    constraintObj = JSON.parse(constraintStr);
  } catch (e) {
    console.error("Erreur parse JSON:", e, constraintStr);
    alert("Impossible de lire la contrainte.");
    return;
  }

  const constraintId = constraintObj.id;
  const formDiv = document.getElementById("edit-constraint-form-" + constraintId);
  const inputEl = document.getElementById("edit-constraint-input-" + constraintId);
  const picker  = document.getElementById("edit-fp-" + constraintId);

  if (formDiv && inputEl) {
    formDiv.style.display = "block";
    inputEl.value = constraintObj.description || "";
    // Pré-remplir le file picker si un fichier existant
    if (picker) {
      initFilePicker(picker);
      if (constraintObj.file_path) {
        fpSetPath(picker, constraintObj.file_path);
      } else {
        fpReset(picker);
      }
    }
  }
}

function hideEditConstraintForm(constraintId) {
  const formDiv = document.getElementById("edit-constraint-form-" + constraintId);
  if (formDiv) formDiv.style.display = "none";
}

function submitEditConstraint(activityId, constraintId) {
  const inputElem = document.getElementById("edit-constraint-input-" + constraintId);
  if (!inputElem) return;
  const newDesc = inputElem.value.trim();
  if (!newDesc) {
    alert("Veuillez saisir une description.");
    return;
  }
  const picker   = document.getElementById("edit-fp-" + constraintId);
  const filePath = picker ? fpGetPath(picker) : null;

  fetch(`/constraints/${activityId}/${constraintId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description: newDesc, file_path: filePath })
  })
  .then(resp => resp.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      updateConstraints(activityId);
    }
  })
  .catch(err => {
    console.error("Erreur lors de la modification de la contrainte :", err);
  });
}

function deleteConstraint(activityId, constraintId) {
  if (!confirm("Confirmez-vous la suppression de cette contrainte ?")) return;
  fetch(`/constraints/${activityId}/${constraintId}`, { method: "DELETE" })
  .then(resp => resp.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      updateConstraints(activityId);
    }
  })
  .catch(err => {
    console.error("Erreur lors de la suppression de la contrainte :", err);
  });
}
