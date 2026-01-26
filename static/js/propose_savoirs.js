// Code/static/js/propose_savoirs.js

/**
 * Analyse l'activité, appelle /propose_savoir/propose (non fourni ici)
 * et affiche le résultat dans un modal => checkboxes => /savoirs/add
 * 
 */


function fetchActivityDetailsForSavoirs(activityId) {
    showSpinner();
    fetch(`/activities/${activityId}/details`)
      .then(response => {
        if (!response.ok) {
          hideSpinner();
          throw new Error("Erreur lors de la récupération des détails de l'activité");
        }
        return response.json();
      })
      .then(activityData => {
        hideSpinner();
        proposeSavoirs(activityData);  
      })
      .catch(error => {
        hideSpinner();
        console.error("Erreur fetchActivityDetailsForSavoirs:", error);
        alert("Impossible de récupérer les détails de l'activité pour Proposer Savoirs");
      });
  }
  
  /**
   * Appelle l'IA pour proposer des savoirs (POST /savoirs/propose_savoirs),
   * Puis ouvre le modal savoirModal avec les options proposées.
   */
  function proposeSavoirs(activityData) {
    showSpinner();
    fetch("/propose_savoirs/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(activityData)
    })
    .then(async response => {
      if (!response.ok) {
        const text = await response.text();
          throw new Error(`Réponse invalide de /propose_savoirs/propose: ${text}`);
      }
      return response.json();
    })
    .then(data => {
      hideSpinner();
      console.log(data);
      if (data.error) {
        console.error("Erreur IA /savoirs/propose_savoirs:", data.error);
        alert("Erreur proposition Savoirs : " + data.error);
        return;
      }
      const lines = data.proposals;
      if (!lines || !Array.isArray(lines)) {
        alert("Aucune proposition retournée.");
        return;
      }
      showProposedSavoirs(lines, activityData.id);
      
    })
    .catch(err => {
      hideSpinner();
      console.error("Erreur lors de la proposition de savoirs:", err);
      alert("Impossible d'obtenir des propositions de savoirs (voir console).");
    });
  }
  



  function showProposedSavoirs(proposals, activityId) {
    let overlay = document.getElementById('proposeSavoirsModalOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'proposeSavoirsModalOverlay';
      overlay.className = 'modal-overlay-propose';
      overlay.onclick = (e) => { if(e.target === overlay) overlay.style.display = 'none'; };

      const modal = document.createElement('div');
      modal.id = 'proposeSavoirsModal';
      modal.className = 'modal-content-propose';
      overlay.appendChild(modal);
      document.body.appendChild(overlay);
    }

    const modal = overlay.querySelector('#proposeSavoirsModal');
    modal.innerHTML = `
      <div class="modal-header-propose">
        <h3><i class="fa-solid fa-sparkles"></i> Propositions de savoirs</h3>
        <button class="modal-close-btn-propose" id="closeSavoirsModalBtn">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div class="modal-body-propose">
        <ul id="proposedSavoirsList" class="proposals-list-propose"></ul>
      </div>
      <div class="modal-footer-propose">
        <button class="btn-modal-secondary-propose" id="cancelProposedSavoirsBtn">
          <i class="fa-solid fa-xmark"></i> Annuler
        </button>
        <button class="btn-modal-primary-propose" id="validateProposedSavoirsBtn">
          <i class="fa-solid fa-check"></i> Enregistrer
        </button>
      </div>
    `;

    const listEl = modal.querySelector('#proposedSavoirsList');
    listEl.innerHTML = "";
    proposals.forEach((p) => {
      const li = document.createElement('li');
      const escaped = String(p).replace(/'/g, "\\'").replace(/"/g, '&quot;');
      li.innerHTML = `
        <label class="proposal-item-propose">
          <input type="checkbox" data-description="${escaped}" checked />
          <span>${p}</span>
        </label>
      `;
      listEl.appendChild(li);
    });

    overlay.style.display = 'flex';
  

    // Boutons de fermeture
    modal.querySelector('#closeSavoirsModalBtn').onclick = () => {
      overlay.style.display = 'none';
    };
    modal.querySelector('#cancelProposedSavoirsBtn').onclick = () => {
      overlay.style.display = 'none';
    };
    

    // Bouton d'Enregistrement
    modal.querySelector('#validateProposedSavoirsBtn').onclick = () => {
        const selected = listEl.querySelectorAll('input[type="checkbox"]:checked');
        if (!selected.length) {
            alert("Aucun savoir sélectionné.");
            return;
        }
        showSpinner();
        let addPromises = [];
        selected.forEach(ch => {
            const description = ch.getAttribute('data-description');
            let p = fetch('/savoirs/add', {
                method: 'POST',
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    description,
                    activity_id: activityId
                })
            })
            .then(r => r.json())
            .then(d => {
                if (d.error) {
                console.error("Erreur ajout Savoirs:", d.error);
                }
            })
            .catch(err => {
                console.error("Erreur /savoirs/add:", err);
            });
            addPromises.push(p);
        });
               
        Promise.all(addPromises).then(() => {
            hideSpinner();
            overlay.style.display = 'none';
            updateSavoirs(activityId);
        })
        .catch(err => {
            hideSpinner();
            alert("Erreur lors de l'ajout des savoirs.");
            console.error(err);
        });
    };
    
}


  