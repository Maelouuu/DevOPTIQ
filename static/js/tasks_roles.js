// static/js/tasks_roles.js

document.addEventListener('DOMContentLoaded', function() {
  console.log("tasks_roles.js chargé");
});

/**
* Affiche le formulaire d'ajout de rôles pour la tâche donnée
* et charge la liste des rôles existants depuis le backend (pour le <select>)
*/
function showTaskRoleForm(taskId) {
const form = document.getElementById(`task-role-form-${taskId}`);
if (form) {
  form.style.display = 'block';
  loadExistingRoles(taskId);
}
}

/**
* Cache le formulaire d'ajout de rôles
*/
function hideTaskRoleForm(taskId) {
const form = document.getElementById(`task-role-form-${taskId}`);
if (form) {
  form.style.display = 'none';
}
}

/**
* Charge la liste des rôles existants (pour le <select> "existing-roles-...")
*/
function loadExistingRoles(taskId) {
fetch('/roles/list')
  .then(response => response.json())
  .then(data => {
    const selectElem = document.getElementById('existing-roles-' + taskId);
    if (selectElem) {
      // Vider puis remplir la liste
      selectElem.innerHTML = '';
      data.forEach(role => {
        let option = document.createElement('option');
        option.value = role.id;
        option.text = role.name;
        selectElem.appendChild(option);
      });
    }
  })
  .catch(error => {
    console.error('Erreur lors du chargement des rôles existants:', error);
  });
}

/**
* Ajoute un ou plusieurs rôles à la tâche, avec un statut
*/
function submitTaskRoles(taskId) {
const existingSelect = document.getElementById(`existing-roles-${taskId}`);
const newRolesInput = document.getElementById(`new-roles-${taskId}`);
const statusSelect  = document.getElementById(`role-status-${taskId}`);

const existingRoleIds = Array.from(existingSelect.selectedOptions).map(opt => parseInt(opt.value));
const newRoles = newRolesInput.value
  .split(',')
  .map(r => r.trim())
  .filter(r => r.length > 0);
const chosenStatus = statusSelect.value;

const payload = {
  existing_role_ids: existingRoleIds,
  new_roles: newRoles,
  status: chosenStatus
};

fetch(`/tasks/${taskId}/roles/add`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
  .then(response => {
    if (!response.ok) {
      return response.json().then(err => {
        throw new Error(err.error || "Erreur lors de l'ajout des rôles.");
      });
    }
    return response.json();
  })
  .then(data => {
    console.log("Rôles ajoutés:", data.added_roles);
    hideTaskRoleForm(taskId);
    existingSelect.selectedIndex = -1;
    newRolesInput.value = '';

    // Recharger la liste des rôles
    loadTaskRolesForDisplay(taskId);
  })
  .catch(error => {
    alert(error.message);
    console.error("Erreur lors de la soumission des rôles:", error);
  });
}

/**
* Récupère la liste des rôles existants pour la tâche, et l'affiche dans le DOM
* Support pour l'ancien format (ul) et le nouveau format (badges)
*/
function loadTaskRolesForDisplay(taskId) {
fetch(`/tasks/${taskId}/roles`)
  .then(r => r.json())
  .then(data => {
    // Nouveau format avec badges
    const badgesContainer = document.getElementById(`roles-badges-${taskId}`);
    if (badgesContainer) {
      // Supprimer les anciens badges (garder le bouton d'ajout)
      const existingBadges = badgesContainer.querySelectorAll('.role-badge');
      existingBadges.forEach(badge => badge.remove());

      // Ajouter les nouveaux badges avant le bouton d'ajout
      const addBtn = badgesContainer.querySelector('.add-badge-btn');

      data.roles.forEach(role => {
        let badge = document.createElement('span');
        badge.className = 'role-badge';
        badge.dataset.roleId = role.id;

        // Déterminer la classe du status
        const statusClass = role.status.toLowerCase().replace('é', 'e');

        badge.innerHTML = `
          <i class="fa-solid fa-user"></i> ${role.name}
          <span class="role-status-badge ${statusClass}">${role.status}</span>
          <button class="badge-remove" onclick="deleteRoleFromTask('${taskId}', '${role.id}')">
            <i class="fa-solid fa-xmark"></i>
          </button>
        `;

        if (addBtn) {
          badgesContainer.insertBefore(badge, addBtn);
        } else {
          badgesContainer.appendChild(badge);
        }
      });
      return;
    }

    // Ancien format avec ul (fallback)
    const rolesUl = document.querySelector(`#roles-for-task-${taskId} ul`);
    if (!rolesUl) return;

    rolesUl.innerHTML = '';

    data.roles.forEach(role => {
      let li = document.createElement('li');
      li.innerHTML = `
        ${role.name} (${role.status})
        <button class="icon-btn" onclick="deleteRoleFromTask('${taskId}', '${role.id}')">
          <i class="fa-solid fa-trash"></i>
        </button>
      `;
      rolesUl.appendChild(li);
    });
  })
  .catch(error => {
    console.error("Erreur lors du chargement des rôles pour la tâche " + taskId, error);
  });
}

/**
* Supprime un rôle de la tâche (DELETE /tasks/<taskId>/roles/<roleId>)
*/
function deleteRoleFromTask(taskId, roleId) {
if (!confirm("Confirmez-vous la suppression de ce rôle ?")) return;

fetch(`/tasks/${taskId}/roles/${roleId}`, {
  method: 'DELETE'
})
  .then(response => {
    if (!response.ok) {
      return response.json().then(err => {
        throw new Error(err.error || "Erreur lors de la suppression du rôle.");
      });
    }
    return response.json();
  })
  .then(data => {
    console.log(data.message);
    loadTaskRolesForDisplay(taskId);
  })
  .catch(error => {
    alert(error.message);
    console.error("Erreur lors de la suppression du rôle:", error);
  });
}
