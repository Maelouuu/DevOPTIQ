/*******************************************************
 * Gestion des SAVOIRS pour la page Activités
 *******************************************************/

// =============
// Ajouter savoir
// =============
function showAddSavoirForm(activityId) {
    const form = document.getElementById("add-savoir-form-" + activityId);
    if (form) form.style.display = "block";
}

function hideAddSavoirForm(activityId) {
    const form = document.getElementById("add-savoir-form-" + activityId);
    if (form) form.style.display = "none";

    const input = document.getElementById("add-savoir-input-" + activityId);
    if (input) input.value = "";
}

function submitAddSavoir(activityId) {
    const input = document.getElementById("add-savoir-input-" + activityId);
    if (!input) return;

    const desc = input.value.trim();
    if (!desc) {
        alert(_CR('need_description'));
        return;
    }

    fetch(`/savoirs/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: desc, activity_id: activityId })
    })
    .then(r => r.json())
    .then(async data => {
        if (data.error) {
            alert(data.error);
        } else {
            hideAddSavoirForm(activityId);
            if (typeof refreshActivityItems === "function") {
                await refreshActivityItems(activityId);
            }
        }
    })
    .catch(err => {
        console.error("Erreur POST /savoirs/add:", err);
        alert(_CR('err_add'));
    });
}


// ====================
// ÉDITER un savoir
// ====================
function editSavoir(savoirId) {
    const displayDiv = document.getElementById(`sv-display-${savoirId}`);
    const editDiv = document.getElementById(`sv-edit-area-${savoirId}`);
    const input = document.getElementById(`edit-savoir-input-${savoirId}`);

    if (!displayDiv || !editDiv || !input) {
        console.error("editSavoir: éléments manquants", savoirId);
        return;
    }

    displayDiv.style.display = "none";
    editDiv.style.display = "flex";
    input.focus();
}


// ====================
// Annuler édition
// ====================
function hideEditSavoir(savoirId) {
    const displayDiv = document.getElementById(`sv-display-${savoirId}`);
    const editDiv = document.getElementById(`sv-edit-area-${savoirId}`);

    if (!displayDiv || !editDiv) return;

    displayDiv.style.display = "flex";
    editDiv.style.display = "none";
}


// ====================
// Valider modification
// ====================
function submitEditSavoir(activityId, savoirId) {
    const input = document.getElementById(`edit-savoir-input-${savoirId}`);
    if (!input) return;

    const newDesc = input.value.trim();
    if (!newDesc) {
        alert(_CR('need_description'));
        return;
    }

    fetch(`/savoirs/${activityId}/${savoirId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: newDesc })
    })
    .then(r => r.json())
    .then(async data => {
        if (data.error) {
            alert(data.error);
        } else {
            // On rafraîchit la zone de l'activité
            if (typeof refreshActivityItems === "function") {
                await refreshActivityItems(activityId);
            }
        }
    })
    .catch(err => {
        console.error("Erreur PUT /savoirs/<activity>/<id>:", err);
        alert(_CR('err_update'));
    });
}


// ====================
// Supprimer un savoir
// ====================
function deleteSavoir(activityId, savoirId) {
    if (!confirm("Supprimer ce savoir ?")) return;

    fetch(`/savoirs/${activityId}/${savoirId}`, { method: "DELETE" })
        .then(r => r.json())
        .then(async data => {
            if (data.error) {
                alert(data.error);
            } else {
                if (typeof refreshActivityItems === "function") {
                    await refreshActivityItems(activityId);
                }
            }
        })
        .catch(err => {
            console.error("Erreur DELETE /savoirs/<activity>/<id>:", err);
            alert(_CR('err_delete'));
        });
}


// ====================
// Expose global
// ====================
window.showAddSavoirForm = showAddSavoirForm;
window.hideAddSavoirForm = hideAddSavoirForm;
window.submitAddSavoir = submitAddSavoir;

window.editSavoir = editSavoir;
window.submitEditSavoir = submitEditSavoir;
window.hideEditSavoir = hideEditSavoir;

window.deleteSavoir = deleteSavoir;
