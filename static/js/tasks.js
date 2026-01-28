/*******************************************************
 * FICHIER : Code/static/js/tasks.js
 * Description :
 *    Gère les Tâches (CRUD), l'association d'Outils,
 *    l'association de Rôles, le reorder, etc.
 *    Désormais, on utilise un rendu partiel "tasks_partial.html"
 *    pour rafraîchir le bloc HTML des tâches après chaque opération.
 ******************************************************/

/* =====================================================
   FONCTIONS GLOBALES POUR LE RENDU PARTIEL
   ===================================================== */

/**
 * updateTasks(activityId)
 * Va chercher le HTML partiel sur /tasks/<activityId>/render
 * et remplace le bloc "tasks-section-<activityId>"
 * Ensuite, réinitialise le drag & drop via SortableJS.
 * Et charge dynamiquement les rôles pour chaque tâche.
 */
function updateTasks(activityId) {
  fetch(`/tasks/${activityId}/render`)
    .then(resp => {
      if (!resp.ok) {
        throw new Error("Impossible de rafraîchir la liste des tâches");
      }
      return resp.text();
    })
    .then(html => {
      const container = document.getElementById(`tasks-section-${activityId}`);
      if (container) {
        container.innerHTML = html;
        // Réinitialiser le drag & drop sur la liste des tâches
        const taskList = container.querySelector(`#tasks-list-${activityId}`);
        if (taskList) {
          new Sortable(taskList, {
            animation: 150,
            handle: '.task-drag-handle',  // Utilise l'icône grip comme poignée
            onEnd: function (evt) {
              var newOrder = [];
              taskList.querySelectorAll('li[data-task-id]').forEach(function(li) {
                newOrder.push(li.getAttribute('data-task-id'));
              });
              // Envoyer le nouvel ordre vers le serveur
              fetch(`/tasks/${activityId}/tasks/reorder`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order: newOrder })
              })
              .then(function(response) { return response.json(); })
              .then(function(data) {
                if (data.error) { alert("Erreur réordonnancement : " + data.error); }
              })
              .catch(function(err) { console.error("Erreur lors du réordonnancement : ", err); });
            }
          });
        }
        // Charger dynamiquement les rôles pour chaque tâche
        const taskItems = container.querySelectorAll('li[data-task-id]');
        taskItems.forEach(li => {
          const taskId = li.getAttribute('data-task-id');
          loadTaskRolesForDisplay(taskId);
        });
      } else {
        console.warn(`Aucun conteneur #tasks-section-${activityId} trouvé dans le DOM.`);
      }
    })
    .catch(err => {
      console.error("Erreur updateTasks:", err);
      alert(err.message);
    });
}

/* =====================================================
   FONCTIONS POUR L'AJOUT / EDIT / SUPPRESSION DE TÂCHES
   ===================================================== */

function showTaskForm(activityId) {
  const formDiv = document.getElementById(`task-form-${activityId}`);
  if (formDiv) {
    formDiv.style.display = 'block';
  }
}

function hideTaskForm(activityId) {
  const formDiv = document.getElementById(`task-form-${activityId}`);
  if (formDiv) {
    formDiv.style.display = 'none';
  }
  const nameInput = document.getElementById(`task-name-${activityId}`);
  const descInput = document.getElementById(`task-desc-${activityId}`);
  if (nameInput) nameInput.value = "";
  if (descInput) descInput.value = "";
}

function submitTask(activityId) {
  const nameInput = document.getElementById(`task-name-${activityId}`);
  const descInput = document.getElementById(`task-desc-${activityId}`);
  if (!nameInput || !descInput) return;

  const taskName = nameInput.value.trim();
  const taskDesc = descInput.value.trim();

  if (!taskName) {
    alert("Le nom de la tâche est requis.");
    return;
  }

  fetch('/tasks/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      activity_id: activityId,
      name: taskName,
      description: taskDesc
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      hideTaskForm(activityId);
      updateTasks(activityId);
    }
  })
  .catch(error => {
    console.error("Erreur lors de l'ajout de la tâche:", error);
    alert("Impossible d'ajouter la tâche.");
  });
}

function showEditTaskForm(activityId, taskId, currentName, currentDesc) {
  const formDiv = document.getElementById(`edit-task-form-${taskId}`);
  const nameInput = document.getElementById(`edit-task-name-${taskId}`);
  const descInput = document.getElementById(`edit-task-desc-${taskId}`);
  if (formDiv && nameInput && descInput) {
    formDiv.style.display = 'block';
    nameInput.value = currentName || "";
    descInput.value = currentDesc || "";
  }
}

function hideEditTaskForm(taskId) {
  const formDiv = document.getElementById(`edit-task-form-${taskId}`);
  if (formDiv) {
    formDiv.style.display = 'none';
  }
}

function submitEditTask(activityId, taskId) {
  const nameInput = document.getElementById(`edit-task-name-${taskId}`);
  const descInput = document.getElementById(`edit-task-desc-${taskId}`);
  if (!nameInput || !descInput) return;

  const newName = nameInput.value.trim();
  const newDesc = descInput.value.trim();

  if (!newName) {
    alert("Le nom de la tâche est requis.");
    return;
  }

  fetch(`/tasks/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: newName, description: newDesc })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      updateTasks(activityId);
    }
  })
  .catch(error => {
    console.error("Erreur lors de la modification de la tâche:", error);
    alert("Impossible de modifier la tâche.");
  });
}

function deleteTask(activityId, taskId) {
  if (!confirm("Confirmez-vous la suppression de cette tâche ?")) return;

  fetch(`/tasks/${taskId}`, {
    method: 'DELETE'
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      updateTasks(activityId);
    }
  })
  .catch(error => {
    console.error("Erreur lors de la suppression de la tâche:", error);
    alert("Impossible de supprimer la tâche.");
  });
}

/* =====================================================
   REORDER
   ===================================================== */
function reorderTasks(activityId, newOrderArray) {
  fetch(`/tasks/${activityId}/tasks/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ order: newOrderArray })
  })
  .then(resp => resp.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      updateTasks(activityId);
    }
  })
  .catch(err => {
    console.error("Erreur reorderTasks:", err);
  });
}

/* =====================================================
   GESTION DES OUTILS (tools)
   ===================================================== */

function showToolForm(taskId) {
  const form = document.getElementById(`tool-form-${taskId}`);
  if (form) {
    form.style.display = 'block';
    loadExistingTools(taskId);
  }
}

function hideToolForm(taskId) {
  const form = document.getElementById(`tool-form-${taskId}`);
  if (form) {
    form.style.display = 'none';
  }
}

function loadExistingTools(taskId) {
  fetch('/tools/all')
    .then(resp => resp.json())
    .then(data => {
      const select = document.getElementById(`existing-tools-${taskId}`);
      if (!select) return;
      select.innerHTML = "";
      data.forEach(tool => {
        const opt = document.createElement('option');
        opt.value = tool.id;
        opt.textContent = tool.name;
        select.appendChild(opt);
      });
    })
    .catch(err => {
      console.error("Erreur loadExistingTools:", err);
    });
}

function submitTools(taskId) {
  const existingSelect = document.getElementById(`existing-tools-${taskId}`);
  const newToolsInput = document.getElementById(`new-tools-${taskId}`);
  if (!existingSelect || !newToolsInput) return;

  const selectedOptions = [...existingSelect.options].filter(opt => opt.selected);
  const existing_tool_ids = selectedOptions.map(opt => parseInt(opt.value));

  const newToolsStr = newToolsInput.value.trim();
  let new_tools = [];
  if (newToolsStr) {
    new_tools = newToolsStr.split(',').map(s => s.trim()).filter(s => s);
  }

  fetch('/tools/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_id: parseInt(taskId),
      existing_tool_ids: existing_tool_ids,
      new_tools: new_tools
    })
  })
  .then(resp => resp.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      // On cherche l'activitéId pour updateTasks
      const li = document.getElementById(`task-${taskId}`);
      if (li) {
        const activityId = li.getAttribute("data-activity-id");
        if (activityId) {
          updateTasks(activityId);
        } else {
          location.reload();
        }
      } else {
        location.reload();
      }
    }
  })
  .catch(err => {
    console.error("Erreur submitTools:", err);
  });
}

/* =====================================================
   GESTION DES RÔLES (task_roles)
   ===================================================== */

function showTaskRoleForm(taskId) {
  const form = document.getElementById(`task-role-form-${taskId}`);
  if (form) {
    form.style.display = 'block';
    loadRolesForTaskForm(taskId);
  }
}

function hideTaskRoleForm(taskId) {
  const form = document.getElementById(`task-role-form-${taskId}`);
  if (form) {
    form.style.display = 'none';
  }
}

function loadRolesForTaskForm(taskId) {
  fetch('/roles/list')
    .then(resp => resp.json())
    .then(data => {
      const select = document.getElementById(`existing-roles-${taskId}`);
      if (!select) return;
      select.innerHTML = "";
      data.forEach(role => {
        const opt = document.createElement('option');
        opt.value = role.id;
        opt.textContent = role.name;
        select.appendChild(opt);
      });
    })
    .catch(err => {
      console.error("Erreur loadRolesForTaskForm:", err);
    });
}

function submitTaskRoles(taskId) {
  const existingSelect = document.getElementById(`existing-roles-${taskId}`);
  const newRolesInput = document.getElementById(`new-roles-${taskId}`);
  const statusSelect = document.getElementById(`role-status-${taskId}`);
  if (!existingSelect || !newRolesInput || !statusSelect) return;

  const selectedOptions = [...existingSelect.options].filter(opt => opt.selected);
  const existing_role_ids = selectedOptions.map(opt => parseInt(opt.value));

  const newRolesStr = newRolesInput.value.trim();
  let new_roles = [];
  if (newRolesStr) {
    new_roles = newRolesStr.split(',').map(s => s.trim()).filter(s => s);
  }

  const chosen_status = statusSelect.value;

  fetch(`/tasks/${taskId}/roles/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      existing_role_ids: existing_role_ids,
      new_roles: new_roles,
      status: chosen_status
    })
  })
  .then(resp => resp.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      const li = document.getElementById(`task-${taskId}`);
      if (li) {
        const activityId = li.getAttribute("data-activity-id");
        if (activityId) {
          updateTasks(activityId);
        } else {
          location.reload();
        }
      } else {
        location.reload();
      }
    }
  })
  .catch(err => {
    console.error("Erreur submitTaskRoles:", err);
  });
}

function loadTaskRolesForDisplay(taskId) {
  fetch(`/tasks/${taskId}/roles`)
    .then(resp => resp.json())
    .then(data => {
      if (data.error) {
        console.error("Erreur loadTaskRolesForDisplay:", data.error);
        return;
      }

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
      const rolesUL = document.querySelector(`#roles-for-task-${taskId} ul`);
      if (!rolesUL) return;
      rolesUL.innerHTML = "";
      data.roles.forEach(role => {
        const li = document.createElement('li');
        li.textContent = `${role.name} (${role.status})`;
        // Bouton pour retirer ce rôle
        const btn = document.createElement('button');
        btn.innerHTML = "X";
        btn.className = "icon-btn";
        btn.onclick = () => {
          deleteRoleFromTask(taskId, role.id);
        };
        li.appendChild(btn);
        rolesUL.appendChild(li);
      });
    })
    .catch(err => {
      console.error("Erreur loadTaskRolesForDisplay:", err);
    });
}

function deleteRoleFromTask(taskId, roleId) {
  if (!confirm("Supprimer ce rôle de la tâche ?")) return;
  fetch(`/tasks/${taskId}/roles/${roleId}`, {
    method: 'DELETE'
  })
  .then(resp => resp.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
    } else {
      const li = document.getElementById(`task-${taskId}`);
      if (li) {
        const activityId = li.getAttribute("data-activity-id");
        if (activityId) {
          updateTasks(activityId);
        } else {
          location.reload();
        }
      } else {
        location.reload();
      }
    }
  })
  .catch(err => {
    console.error("Erreur deleteRoleFromTask:", err);
  });
}