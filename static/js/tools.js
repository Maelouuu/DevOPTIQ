// tools.js - Gestion des outils

function showToolForm(taskId) {
  document.getElementById('tool-form-' + taskId).style.display = 'block';
  fetch('/tools/all')
  .then(response => response.json())
  .then(data => {
    const selectElem = document.getElementById('existing-tools-' + taskId);
    selectElem.innerHTML = "";
    data.forEach(tool => {
      const option = document.createElement('option');
      option.value = tool.id;
      option.text = tool.name;
      selectElem.appendChild(option);
    });
  })
  .catch(error => {
    alert("Erreur lors du chargement des outils existants: " + error.message);
  });
}

function hideToolForm(taskId) {
  document.getElementById('tool-form-' + taskId).style.display = 'none';
}

function submitTools(taskId) {
  const selectElem = document.getElementById('existing-tools-' + taskId);
  const newToolsInput = document.getElementById('new-tools-' + taskId);
  const existingToolIds = Array.from(selectElem.selectedOptions).map(opt => parseInt(opt.value));
  const newTools = newToolsInput.value.split(",").map(item => item.trim()).filter(item => item.length > 0);
  const payload = {
    task_id: parseInt(taskId),
    existing_tool_ids: existingToolIds,
    new_tools: newTools
  };
  fetch('/tools/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(response => response.json())
  .then(data => {
    const badgesContainer = document.getElementById('tools-badges-' + taskId);
    if (!badgesContainer) { hideToolForm(taskId); return; }

    // Trouver le bouton "+" d'ajout pour insérer avant lui
    const addBtn = badgesContainer.querySelector('.add-badge-btn');

    data.added_tools.forEach(tool => {
      const span = document.createElement('span');
      span.className = 'tool-badge';
      span.setAttribute('data-tool-id', tool.id);
      span.innerHTML = `<i class="fa-solid fa-wrench"></i> ${tool.name}
        <button class="badge-remove" onclick="deleteToolFromTask('${taskId}', '${tool.id}')">
          <i class="fa-solid fa-xmark"></i>
        </button>`;
      if (addBtn) {
        badgesContainer.insertBefore(span, addBtn);
      } else {
        badgesContainer.appendChild(span);
      }
    });

    selectElem.selectedIndex = -1;
    newToolsInput.value = "";
    hideToolForm(taskId);
  })
  .catch(error => {
    alert(error.message);
  });
}

function deleteToolFromTask(taskId, toolId) {
  if (!confirm("Confirmez-vous la suppression de cet outil ?")) return;
  fetch('/tools/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task_id: parseInt(taskId),
      tool_id: parseInt(toolId)
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      alert("Erreur : " + data.error);
      return;
    }
    const badgesContainer = document.getElementById('tools-badges-' + taskId);
    if (!badgesContainer) return;
    const badge = badgesContainer.querySelector(`span[data-tool-id="${toolId}"]`);
    if (badge) badge.remove();
  })
  .catch(error => {
    alert(error.message);
  });
}
