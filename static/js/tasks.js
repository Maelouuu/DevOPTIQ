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
    initFilePicker(document.getElementById(`task-fp-${activityId}`));
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
  fpReset(document.getElementById(`task-fp-${activityId}`));
}

function submitTask(activityId) {
  const nameInput = document.getElementById(`task-name-${activityId}`);
  const descInput = document.getElementById(`task-desc-${activityId}`);
  if (!nameInput || !descInput) return;

  const taskName = nameInput.value.trim();
  const taskDesc = descInput.value.trim();
  const taskFile = fpGetPath(document.getElementById(`task-fp-${activityId}`));

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
      description: taskDesc,
      file_path: taskFile
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

function showEditTaskForm(activityId, taskId, currentName, currentDesc, currentFile) {
  const formDiv = document.getElementById(`edit-task-form-${taskId}`);
  const nameInput = document.getElementById(`edit-task-name-${taskId}`);
  const descInput = document.getElementById(`edit-task-desc-${taskId}`);
  if (formDiv && nameInput && descInput) {
    formDiv.style.display = 'block';
    nameInput.value = currentName || "";
    descInput.value = currentDesc || "";
    const picker = document.getElementById(`edit-task-fp-${taskId}`);
    initFilePicker(picker);
    fpSetPath(picker, currentFile || "");
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
  const newFile = fpGetPath(document.getElementById(`edit-task-fp-${taskId}`));

  if (!newName) {
    alert("Le nom de la tâche est requis.");
    return;
  }

  fetch(`/tasks/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: newName, description: newDesc, file_path: newFile })
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
    // Init file picker du formulaire
    const picker = document.getElementById(`new-tool-fp-${taskId}`);
    if (picker) initFilePicker(picker);
  }
}

function hideToolForm(taskId) {
  const form = document.getElementById(`tool-form-${taskId}`);
  if (form) {
    form.style.display = 'none';
    // Reset le picker
    const picker = document.getElementById(`new-tool-fp-${taskId}`);
    if (picker) fpReset(picker);
    const nameIn = document.getElementById(`new-tool-name-${taskId}`);
    if (nameIn) nameIn.value = "";
  }
}

// Liste des outils à cocher : classée par nom, celles déjà rattachées à la
// tâche sont cochées et signalées. Un <select multiple> obligeait à un
// ctrl+clic pour en prendre plusieurs et ne montrait pas l'existant.
function loadExistingTools(taskId) {
  const hote = document.getElementById(`existing-tools-${taskId}`);
  if (!hote) return;
  hote.innerHTML = '<p class="tool-picker-loading">…</p>';

  const dejaLies = new Set(
    [...document.querySelectorAll(`#tools-badges-${taskId} .tool-badge`)]
      .map(b => String(b.dataset.toolId)));

  fetch('/tools/all')
    .then(resp => resp.json())
    .then(data => {
      const outils = (data || []).slice().sort((a, b) =>
        (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }));
      if (!outils.length) {
        hote.innerHTML = `<p class="tool-picker-empty">${_toolI18n('empty')}</p>`;
        return;
      }
      hote.innerHTML = outils.map(tool => {
        const lie = dejaLies.has(String(tool.id));
        return `<label class="tool-pick${lie ? ' tool-pick--linked' : ''}${tool.file_path ? ' tool-pick--file' : ''}">
          <input type="checkbox" value="${tool.id}"${lie ? ' checked disabled' : ''}>
          <i class="fa-solid ${tool.file_path ? 'fa-file-lines' : 'fa-wrench'}"></i>
          <span class="tool-pick-name">${_toolEsc(tool.name || '')}</span>
          ${lie ? `<span class="tool-pick-flag">${_toolI18n('linked')}</span>` : ''}
        </label>`;
      }).join('');
    })
    .catch(err => {
      console.error("Erreur loadExistingTools:", err);
      hote.innerHTML = `<p class="tool-picker-empty">${_toolI18n('error')}</p>`;
    });
}

function _toolEsc(v) {
  return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function _toolI18n(cle) {
  const L = window.TASK_I18N || {};
  const defauts = {
    empty: 'Aucun outil enregistré.', linked: 'déjà lié',
    error: 'Chargement impossible.',
    card_title: "Fiche de l'outil", card_name: "Nom de l'outil",
    card_desc: 'Description', card_file: "Fichier de l'outil",
    card_open: 'Ouvrir', card_remove: 'Retirer le fichier',
    card_save: 'Enregistrer', card_cancel: 'Annuler',
    card_saved: 'Outil enregistré.',
    card_shared: "Cet outil est partagé : le nom, la description et le fichier valent pour toutes les tâches qui l'utilisent.",
    drag_or: 'Glisser un fichier ici ou parcourir',
    fp_hint: 'Déposez la notice, la procédure… (optionnel)',
    fp_remove: 'Supprimer le fichier',
  };
  return L[cle] || defauts[cle];
}

/* =====================================================
   FICHE OUTIL — un fichier peut être joint APRÈS coup
   =====================================================
   Le dépôt du formulaire « + outil » ne concerne que l'outil qu'on est en
   train de créer : sans cette fiche, un outil déjà enregistré ne pouvait
   plus recevoir sa notice. */

function openToolCard(taskId, toolId, ev) {
  // Le badge porte aussi le lien du fichier et la croix de détachement.
  if (ev && ev.target.closest('.badge-remove, .tool-badge-file')) return;
  if (ev) ev.stopPropagation();

  fetch('/tools/all')
    .then(r => r.json())
    .then(outils => {
      const outil = (outils || []).find(o => String(o.id) === String(toolId));
      if (!outil) { alert(_toolI18n('error')); return; }
      _renderToolCard(taskId, outil);
    })
    .catch(() => alert(_toolI18n('error')));
}

function _renderToolCard(taskId, outil) {
  document.getElementById('tool-card-overlay')?.remove();

  const lien = outil.file_path
    ? `<a class="tool-card-link" href="/utils/serve-file?path=${encodeURIComponent(outil.file_path)}" target="_blank">
         <i class="fa-solid fa-up-right-from-square"></i> ${_toolI18n('card_open')}</a>`
    : '';

  const ov = document.createElement('div');
  ov.id = 'tool-card-overlay';
  ov.className = 'tool-card-overlay';
  ov.innerHTML = `
    <div class="tool-card" role="dialog" aria-modal="true">
      <div class="tool-card-head">
        <i class="fa-solid ${outil.file_path ? 'fa-file-lines' : 'fa-wrench'}"></i>
        <h3>${_toolI18n('card_title')}</h3>
        <button class="tool-card-close" type="button" title="${_toolI18n('card_cancel')}">
          <i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="tool-card-body">
        <label class="tool-card-label" for="tool-card-name">${_toolI18n('card_name')}</label>
        <input type="text" id="tool-card-name" class="task-input" value="${_toolEsc(outil.name || '')}">

        <label class="tool-card-label" for="tool-card-desc">${_toolI18n('card_desc')}</label>
        <textarea id="tool-card-desc" class="task-input" rows="2">${_toolEsc(outil.description || '')}</textarea>

        <label class="tool-card-label">
          <i class="fa-solid fa-paperclip"></i> ${_toolI18n('card_file')} ${lien}
        </label>
        <div class="fp-wrap" id="tool-card-fp">
          <div class="fp-zone">
            <span class="fp-spinner" style="display:none"><i class="fa-solid fa-spinner fa-spin"></i></span>
            <i class="fa-solid fa-cloud-arrow-up fp-icon"></i>
            <p class="fp-text">${_toolI18n('drag_or')}</p>
            <p class="fp-hint">${_toolI18n('fp_hint')}</p>
          </div>
          <div class="fp-selected hidden">
            <i class="fa-solid fa-file-circle-check fp-ok-icon"></i>
            <span class="fp-fname"></span>
            <button type="button" class="fp-clear" title="${_toolI18n('fp_remove')}"><i class="fa-solid fa-xmark"></i></button>
          </div>
          <input type="file" class="fp-input">
          <input type="hidden" class="fp-path">
        </div>
        <p class="tool-card-note"><i class="fa-solid fa-circle-info"></i> ${_toolI18n('card_shared')}</p>
      </div>
      <div class="tool-card-actions">
        <button class="btn-action-primary btn-sm" id="tool-card-save">
          <i class="fa-solid fa-check"></i> ${_toolI18n('card_save')}</button>
        <button class="btn-action-secondary btn-sm" id="tool-card-cancel">
          <i class="fa-solid fa-xmark"></i> ${_toolI18n('card_cancel')}</button>
      </div>
    </div>`;
  document.body.appendChild(ov);

  const picker = ov.querySelector('#tool-card-fp');
  initFilePicker(picker);
  fpSetPath(picker, outil.file_path || '');

  const fermer = () => ov.remove();
  ov.querySelector('.tool-card-close').addEventListener('click', fermer);
  ov.querySelector('#tool-card-cancel').addEventListener('click', fermer);
  ov.addEventListener('click', e => { if (e.target === ov) fermer(); });
  document.addEventListener('keydown', function esc(e) {
    if (e.key === 'Escape') { fermer(); document.removeEventListener('keydown', esc); }
  });

  ov.querySelector('#tool-card-save').addEventListener('click', async () => {
    const nom = ov.querySelector('#tool-card-name').value.trim();
    if (!nom) { alert(_toolI18n('card_name')); return; }
    try {
      const r = await fetch(`/gestion_outils/api/tools/${outil.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: nom,
          description: ov.querySelector('#tool-card-desc').value.trim(),
          file_path: fpGetPath(picker),
        }),
      });
      const d = await r.json();
      if (!r.ok) { alert(d.error || _toolI18n('error')); return; }
      fermer();
      _refreshTaskActivity(taskId);   // le badge suit le fichier
    } catch { alert(_toolI18n('error')); }
  });
}

function _refreshTaskActivity(taskId) {
  const li = document.getElementById(`task-${taskId}`);
  if (li) {
    const activityId = li.getAttribute("data-activity-id");
    if (activityId) { updateTasks(activityId); return; }
  }
  location.reload();
}

/* submitToolsNew : gère la sélection d'outils existants + création d'un outil avec fichier */
async function submitToolsNew(taskId) {
  const existingSelect = document.getElementById(`existing-tools-${taskId}`);
  const nameIn         = document.getElementById(`new-tool-name-${taskId}`);
  const picker         = document.getElementById(`new-tool-fp-${taskId}`);

  const existing_tool_ids = existingSelect
    ? [...existingSelect.querySelectorAll('input[type=checkbox]')]
        .filter(c => c.checked && !c.disabled).map(c => parseInt(c.value))
    : [];

  const newName  = nameIn ? nameIn.value.trim() : "";
  const filePath = picker ? fpGetPath(picker) : "";

  // Construire le payload new_tools (compatibilité backend existant)
  // new_tools est un tableau de strings OU d'objets selon l'API
  // L'API /tools/add actuelle accepte { task_id, existing_tool_ids, new_tools: [string] }
  // On va d'abord créer l'outil via l'API gestion_outils si fichier, sinon passer via new_tools

  if (!existing_tool_ids.length && !newName) {
    alert("Sélectionnez un outil existant ou saisissez le nom d'un nouvel outil.");
    return;
  }

  // Si un nouveau nom est fourni, créer l'outil avec le fichier éventuel
  let new_tool_ids = [];
  if (newName) {
    try {
      const r = await fetch("/gestion_outils/api/tools", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, file_path: filePath || null }),
      });
      const d = await r.json();
      if (!r.ok) { alert(d.error || "Impossible de créer l'outil."); return; }
      new_tool_ids.push(d.id);
    } catch { alert("Erreur réseau (création outil)."); return; }
  }

  // Lier tous les outils à la tâche
  const all_ids = [...existing_tool_ids, ...new_tool_ids];
  if (!all_ids.length) { hideToolForm(taskId); return; }

  try {
    const res = await fetch('/tools/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: parseInt(taskId), existing_tool_ids: all_ids, new_tools: [] })
    });
    const data = await res.json();
    if (data.error) { alert("Erreur : " + data.error); return; }
    hideToolForm(taskId);
    _refreshTaskActivity(taskId);
  } catch (err) {
    console.error("Erreur submitToolsNew:", err);
  }
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