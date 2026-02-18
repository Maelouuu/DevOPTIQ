// static/js/task_link_dnd.js
// Drag-and-drop des connexions (lignes de tableaux) vers les slots de tâches
(function () {
  let dragData = null;

  // ─── DRAG START sur une ligne de connexion ───
  document.addEventListener('dragstart', function (e) {
    const row = e.target.closest('tr[data-link-id]');
    if (!row) return;

    dragData = {
      link_id: row.dataset.linkId,
      direction: row.dataset.direction,
      data_name: row.dataset.dataName,
      conn_type: row.dataset.connType
    };

    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('text/plain', row.dataset.linkId);
    row.classList.add('conn-dragging');
  });

  // ─── DRAG END ───
  document.addEventListener('dragend', function (e) {
    const row = e.target.closest('tr[data-link-id]');
    if (row) row.classList.remove('conn-dragging');
    // Nettoyer drag-over sur tous les slots
    document.querySelectorAll('.task-conn-slot.drag-over').forEach(s => s.classList.remove('drag-over'));
    dragData = null;
  });

  // ─── DRAG OVER sur un slot de tâche ───
  document.addEventListener('dragover', function (e) {
    if (!dragData) return;
    const slot = e.target.closest('.task-conn-slot');
    if (!slot) return;

    const slotDir = slot.classList.contains('task-conn-incoming') ? 'incoming' : 'outgoing';
    if (slotDir !== dragData.direction) return;

    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    slot.classList.add('drag-over');
  });

  // ─── DRAG LEAVE ───
  document.addEventListener('dragleave', function (e) {
    const slot = e.target.closest('.task-conn-slot');
    if (!slot) return;
    // Ne pas retirer la classe si on entre dans un enfant
    if (slot.contains(e.relatedTarget)) return;
    slot.classList.remove('drag-over');
  });

  // ─── DROP ───
  document.addEventListener('drop', function (e) {
    if (!dragData) return;
    const slot = e.target.closest('.task-conn-slot');
    if (!slot) return;

    const slotDir = slot.classList.contains('task-conn-incoming') ? 'incoming' : 'outgoing';
    if (slotDir !== dragData.direction) return;

    e.preventDefault();
    slot.classList.remove('drag-over');

    const taskId = parseInt(slot.dataset.taskId, 10);
    const activityId = parseInt(slot.dataset.activityId, 10);
    const linkId = parseInt(dragData.link_id, 10);
    const direction = dragData.direction;
    const dataName = dragData.data_name;
    const connType = dragData.conn_type;

    fetch('/task-links/assign', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ link_id: linkId, task_id: taskId, direction: direction, activity_id: activityId })
    })
      .then(r => r.json())
      .then(resp => {
        if (resp.ok) renderPill(slot, linkId, direction, dataName, connType, taskId);
        else console.error('Erreur assignation:', resp.error);
      })
      .catch(err => console.error('Erreur assignation connexion:', err));

    dragData = null;
  });

  // ─── RENDER PILL ───
  function renderPill(slot, linkId, direction, dataName, connType, taskId) {
    // Supprimer pill existante
    const existing = slot.querySelector('.task-conn-pill');
    if (existing) existing.remove();

    const pill = document.createElement('div');
    pill.className = 'task-conn-pill';
    pill.dataset.linkId = linkId;
    pill.dataset.direction = direction;

    const typeClass = (connType || '').toLowerCase()
      .replace('é', 'e').replace('è', 'e').replace(' ', '');

    const label = document.createElement('span');
    label.className = typeClass || '';
    label.title = dataName;
    label.textContent = dataName.length > 18 ? dataName.slice(0, 18) + '…' : dataName;

    const btn = document.createElement('button');
    btn.className = 'pill-remove';
    btn.title = 'Supprimer';
    btn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    btn.onclick = () => removeTaskLinkAssignment(linkId, direction, taskId);

    pill.appendChild(label);
    pill.appendChild(btn);
    slot.appendChild(pill);
    slot.classList.add('has-conn');
  }

  // ─── SUPPRESSION ASSIGNMENT (global) ───
  window.removeTaskLinkAssignment = function (linkId, direction, taskId) {
    fetch('/task-links/' + linkId + '/' + direction, { method: 'DELETE' })
      .then(r => r.json())
      .then(resp => {
        if (resp.ok) {
          const slot = document.querySelector(
            '.task-conn-slot[data-task-id="' + taskId + '"][data-direction="' + direction + '"]'
          );
          if (slot) {
            const pill = slot.querySelector('.task-conn-pill');
            if (pill) pill.remove();
            slot.classList.remove('has-conn');
          }
        }
      })
      .catch(err => console.error('Erreur suppression assignment:', err));
  };
})();
