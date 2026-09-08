// Code/static/js/aptitudes.js

/**
 * Récupère les détails d'une activité (via /activities/<id>/details),
 * puis enchaîne sur la proposition d'aptitudes IA.
 */


function showAddAptitudeForm(activityId) {
    document.getElementById("add-aptitude-form-" + activityId).style.display = "block";
  }
  
  function hideAddAptitudeForm(activityId) {
    document.getElementById("add-aptitude-form-" + activityId).style.display = "none";
    const inputElem = document.getElementById("add-aptitude-input-" + activityId);
    if (inputElem) inputElem.value = "";
  }
  
  //J'ai une erreur ici l'alert +data.error et le catch recoivent une erreur surement problème de chemin.
  function submitAddAptitude(activityId) {
    const inputElem = document.getElementById("add-aptitude-input-" + activityId);
    if (!inputElem) return;
    const desc = inputElem.value.trim();
    if (!desc) {
        alert(_CR('need_description'));
        return;
    }

    fetch(`/aptitudes/add`, { // Correctement à `/aptitudes/add`
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
            description: desc, 
            activity_id: activityId  // Assurez-vous de passer l'activity_id
        })
    })
    .then(resp => {
        if (!resp.ok) {
            throw new Error(`Erreur lors de la soumission : ${resp.statusText}`);
        }
        return resp.json();
    })
    .then(data => {
        if (data.error) {
            alert(_CR('err') + ' : ' + data.error);
        } else {
            updateAptitudes(activityId);
        }
    })
    .catch(err => {
        console.error("Erreur ajout aptitude :", err);
    });
}


  /**************************************
 * RAFFRAICHIR LA LISTE PARTIELLEMENT
 **************************************/
function updateAptitudesList(activityId) {
  showSpinner();
  fetch(`/aptitudes/${activityId}/render`)
    .then(resp => {
      if (!resp.ok) throw new Error("Erreur lors du rafraîchissement des aptitudes");
      return resp.text();
    })
    .then(html => {
      hideSpinner();
      const container = document.getElementById("aptitude-list-" + activityId);
      if (container) {
        container.innerHTML = html;
      }
    })
    .catch(err => {
      hideSpinner();
      console.error("Erreur updateAptitudesList:", err);
      alert(_CR('err_refresh') + ' ' + err.message);
    });
}



  function updateAptitudes(activityId) {
    fetch(`/aptitudes/${activityId}/render`)
      .then(response => {
        if (!response.ok) throw new Error("Erreur lors du rafraîchissement des aptitudes.");
        return response.text();
      })
      .then(html => {
        const parentDiv = document.querySelector(`#aptitudes-container-${activityId}`);
        parentDiv.innerHTML = html;
      })
      .catch(err => {
        console.error("Erreur updateAptitudes :", err);
        alert(err.message);
      });
  }
  
  /* Édition */

  function editAptitude(aptitudeId, activityId) {
    const descElem = document.getElementById(`aptitude-desc-${aptitudeId}`);
    const editInput = document.getElementById(`edit-aptitude-input-${aptitudeId}`);
    const editBtn = document.getElementById(`submit-edit-aptitude-${aptitudeId}`);
  
    descElem.style.display = "none";
    editInput.style.display = "inline-block";
    editBtn.style.display = "inline-block";
    editInput.value = descElem.innerText.trim();
  }


  function submitEditAptitude(activityId, aptitudeId) {
    const inputEl = document.getElementById("edit-aptitude-input-" + aptitudeId);
    if (!inputEl) return;
    const newDesc = inputEl.value.trim();
    if (!newDesc) {
      alert(_CR('need_description'));
      return;
    }
  
    fetch(`/aptitudes/${activityId}/${aptitudeId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: newDesc })
    })
      .then(resp => resp.json())
      .then(data => {
        if (data.error) {
          alert(_CR('err_update') + ' ' + data.error);
        } else {
          updateAptitudes(activityId);
        }
      })
      .catch(err => {
        console.error("Erreur edit aptitude :", err);
        alert(err.message);
      });
  }


  function showEditAptitudeForm(btnElem) {
    const apStr = btnElem.getAttribute("data-aptitude");
    let apObj;
    try {
      apObj = JSON.parse(apStr);
    } catch (e) {
      console.error("Erreur parse JSON:", e, apStr);
      alert("Impossible de lire l'aptitude.");
      return;
    }
    const formDiv = document.getElementById("edit-aptitude-form-" + apObj.id);
    const inputEl = document.getElementById("edit-aptitude-input-" + apObj.id);
  
    if (formDiv && inputEl) {
      formDiv.style.display = "block";
      inputEl.value = apObj.description || "";
    }
  }
  
  function hideEditAptitudeForm(aptitudeId) {
    const formDiv = document.getElementById("edit-aptitude-form-" + aptitudeId);
    if (formDiv) {
      formDiv.style.display = "none";
    }
  }
  
  function deleteAptitude(activityId, aptitudeId) {
    if (!confirm("Supprimer cette aptitude ?")) return;
    
    fetch(`/aptitudes/${activityId}/${aptitudeId}`, { method: "DELETE" })
      .then(resp => resp.json())
      .then(data => {
        if (data.error) {
          alert(_CR('err') + ' : ' + data.error);
        } else {
          updateAptitudes(activityId);
        }
      })
      .catch(err => {
        console.error("Erreur suppression aptitude :", err);
      });
  }
  