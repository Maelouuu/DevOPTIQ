// Code/static/js/constraints.js

function showAddConstraintForm(activityId) {
  document.getElementById("add-constraint-form-" + activityId).style.display = "block";
}

function hideAddConstraintForm(activityId) {
  document.getElementById("add-constraint-form-" + activityId).style.display = "none";
  const inputElem = document.getElementById("add-constraint-input-" + activityId);
  if (inputElem) inputElem.value = "";
  const fpElem = document.getElementById("add-constraint-filepath-" + activityId);
  if (fpElem) fpElem.value = "";
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
  const fpElem = document.getElementById("add-constraint-filepath-" + activityId);
  const filePath = fpElem ? fpElem.value.trim() : "";

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
      // (1) Fermer le formulaire et vider le champ
      hideAddConstraintForm(activityId);

      // (2) Rafraîchir l’affichage des contraintes
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
      if (!response.ok) {
        throw new Error("Erreur lors du rafraîchissement des contraintes.");
      }
      return response.text();
    })
    .then(html => {
      // On remplace le HTML du conteneur
      document.getElementById("constraints-container-" + activityId).innerHTML = html;

      // BONUS : Forcer la fermeture du formulaire et le reset du champ
      // si jamais l'utilisateur l'avait laissé ouvert
      hideAddConstraintForm(activityId);
    })
    .catch(err => {
      console.error("Erreur lors du rafraîchissement des contraintes :", err);
      alert(err.message);
    });
}

/* ============== ÉDITION ET SUPPRESSION ============== */

function showEditConstraintForm(btnElem) {
  // On récupère l'objet JSON
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
  const fpEl    = document.getElementById("edit-constraint-filepath-" + constraintId);

  if (formDiv && inputEl) {
    formDiv.style.display = "block";
    inputEl.value = constraintObj.description || "";
    if (fpEl) fpEl.value = constraintObj.file_path || "";
  }
}

function hideEditConstraintForm(constraintId) {
  const formDiv = document.getElementById("edit-constraint-form-" + constraintId);
  if (formDiv) {
    formDiv.style.display = "none";
  }
}

function submitEditConstraint(activityId, constraintId) {
  const inputElem = document.getElementById("edit-constraint-input-" + constraintId);
  if (!inputElem) return;
  const newDesc = inputElem.value.trim();
  if (!newDesc) {
    alert("Veuillez saisir une description.");
    return;
  }
  const fpElem   = document.getElementById("edit-constraint-filepath-" + constraintId);
  const filePath = fpElem ? fpElem.value.trim() : null;

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
      // Après modification, on recharge le bloc
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
      // Après suppression, on recharge le bloc
      updateConstraints(activityId);
    }
  })
  .catch(err => {
    console.error("Erreur lors de la suppression de la contrainte :", err);
  });
}
