// main.js – Fonctions globales et gestion modale proposition IA

if (!window.OPTIQ_MAIN_LOADED) {
  window.OPTIQ_MAIN_LOADED = true;

  window.currentActivityId = null;
  window.currentType = "";

  window.toggleDetails = function (detailsId, headerElem) {
    const detailsElem = document.getElementById(detailsId);
    const iconElem = headerElem.querySelector('.toggle-icon');
    const currentDisplay = window.getComputedStyle(detailsElem).display;

    if (currentDisplay === "none") {
      detailsElem.style.display = "block";
      iconElem.textContent = "▼";
    } else {
      detailsElem.style.display = "none";
      iconElem.textContent = "▶";
    }
  };

  function getProposeUrl(type) {
    return `/propose_${type}/propose`;
  }

  window.getActivityData = function (activityId) {
    const detailsElem = document.getElementById(`details-${activityId}`);
    return detailsElem ? detailsElem.innerText : "";
  };

  window.showProposalModal = function (activityId, proposals, type) {
    window.currentType = type;
    window.currentActivityId = activityId;
    $("#proposal-title").text(`Propositions ${type}`);
    $("#proposal-list").html("");
    proposals.forEach(p => {
      $("#proposal-list").append(`<li><input type='checkbox' value="${p}"> ${p}</li>`);
    });
    $("#proposal-modal").show();
  };

  window.validateProposal = function () {
    const selected = [];
    $("#proposal-list input:checked").each((_, el) => selected.push(el.value));

    selected.forEach(val => {
      fetch(`/${window.currentType}/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activity_id: window.currentActivityId, name: val }),
      });
    });

    alert(_CRf('added_ok', { n: selected.length, t: window.currentType }));
    window.closeProposalModal();
    location.reload();
  };

  window.closeProposalModal = function () {
    $("#proposal-modal").hide();
  };

  window.proposeSavoirs = function (activityId) {
    const text = window.getActivityData(activityId);
    fetch(getProposeUrl("savoirs"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activity_data: { name: "", description: text, tasks: "", tools: "" } })
    })
    .then(resp => resp.json())
    .then(data => window.showProposalModal(activityId, data.proposals, "savoirs"))
    .catch(err => console.error("Erreur proposition Savoirs :", err));
  };

  window.proposeSavoirFaires = function (activityId) {
    const text = window.getActivityData(activityId);
    fetch(getProposeUrl("savoir_faires"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activity_data: { name: "", description: text, tasks: "", tools: "" } })
    })
    .then(resp => resp.json())
    .then(data => window.showProposalModal(activityId, data.proposals, "savoir_faires"))
    .catch(err => console.error("Erreur proposition Savoir-Faire :", err));
  };

  window.proposeAptitudes = function (activityId) {
    const text = window.getActivityData(activityId);
    fetch(getProposeUrl("aptitudes"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activity_data: { name: "", description: text, tasks: "", tools: "" } })
    })
    .then(resp => resp.json())
    .then(data => window.showProposalModal(activityId, data.proposals, "aptitudes"))
    .catch(err => console.error("Erreur proposition Aptitudes :", err));
  };
}

document.addEventListener("DOMContentLoaded", function () {
  const cartoButton = document.getElementById("update-cartography-button");

  if (cartoButton) {
    cartoButton.addEventListener("click", function () {
      showSpinner();

      fetch("/activities/update-cartography")
        .then((response) => response.json())
        .then((data) => {
          hideSpinner();
          if (data.error) {
            alert(_CR('err') + " : " + data.error);
          } else {
            alert(data.message + "\n\n" + _CR('summary') + "\n" + data.summary);
            // Ajoute cette ligne pour recharger la page automatiquement après la mise à jour
            location.reload(); 
          }
        })
        .catch((err) => {
          hideSpinner();
          console.error("Erreur update-cartography:", err);
          alert(_CR('err_carto_update'));
        });
    });
  }
});
