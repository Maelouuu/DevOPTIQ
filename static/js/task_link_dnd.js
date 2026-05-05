// static/js/task_link_dnd.js
// Drag-and-drop des connexions (lignes de tableaux) vers les slots de tâches
(function () {
  let dragData = null;
  let tooltip = null;
  let tooltipTarget = null;

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
    // Révéler les zones de drop
    document.body.classList.add('dnd-active');
    hideTooltip();
  });

  // ─── DRAG END ───
  document.addEventListener('dragend', function (e) {
    const row = e.target.closest('tr[data-link-id]');
    if (row) row.classList.remove('conn-dragging');
    document.querySelectorAll('.task-conn-slot.drag-over').forEach(s => s.classList.remove('drag-over'));
    document.body.classList.remove('dnd-active');
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
    // Retirer drag-over des autres slots
    document.querySelectorAll('.task-conn-slot.drag-over').forEach(s => {
      if (s !== slot) s.classList.remove('drag-over');
    });
    slot.classList.add('drag-over');
  });

  // ─── DRAG LEAVE ───
  document.addEventListener('dragleave', function (e) {
    const slot = e.target.closest('.task-conn-slot');
    if (!slot) return;
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
    document.body.classList.remove('dnd-active');

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

  // ─── CLICK sur un slot avec connexion → popup ───
  document.addEventListener('click', function (e) {
    // Clic sur bouton supprimer → ignorer
    if (e.target.closest('.pill-remove')) return;

    const slot = e.target.closest('.task-conn-slot.has-conn');
    if (slot) {
      if (tooltipTarget === slot) {
        // Deuxième clic sur même slot → fermer
        hideTooltip();
        return;
      }
      const pill = slot.querySelector('.task-conn-pill');
      if (!pill) return;

      const span = pill.querySelector('span');
      const fullText = span ? span.title : '';
      if (!fullText) return;

      const direction = slot.dataset.direction;
      const dirLabel = direction === 'incoming' ? '← Entrante' : 'Sortante →';
      const typeClass = span ? span.className : '';
      const typeLabel = typeClass.includes('declenchante') ? 'Déclenchante' : typeClass.includes('nourrissante') ? 'Nourrissante' : '';

      showTooltip(slot, dirLabel + (typeLabel ? ' · ' + typeLabel : '') + '\n' + fullText);
      return;
    }

    // Clic ailleurs → fermer
    hideTooltip();
  });

  // ─── TOOLTIP ───
  function showTooltip(targetSlot, text) {
    hideTooltip();

    tooltip = document.createElement('div');
    tooltip.className = 'conn-slot-tooltip';
    tooltip.textContent = text;
    document.body.appendChild(tooltip);
    tooltipTarget = targetSlot;

    // Positionner au-dessus du slot
    const rect = targetSlot.getBoundingClientRect();
    const tw = Math.min(260, rect.width + 80);
    tooltip.style.width = tw + 'px';

    // Position après rendu pour avoir les dimensions
    requestAnimationFrame(() => {
      const th = tooltip.offsetHeight;
      let left = rect.left + rect.width / 2 - tw / 2;
      let top = rect.top + window.scrollY - th - 10;

      // Garder dans le viewport
      left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
      if (top < window.scrollY + 4) top = rect.bottom + window.scrollY + 10;

      tooltip.style.left = left + 'px';
      tooltip.style.top = top + 'px';
    });
  }

  function hideTooltip() {
    if (tooltip) { tooltip.remove(); tooltip = null; }
    tooltipTarget = null;
  }

  // ─── RENDER PILL ───
  function renderPill(slot, linkId, direction, dataName, connType, taskId) {
    const existing = slot.querySelector('.task-conn-pill');
    if (existing) existing.remove();

    const pill = document.createElement('div');
    pill.className = 'task-conn-pill';
    pill.dataset.linkId = linkId;
    pill.dataset.direction = direction;

    const typeClass = (connType || '').toLowerCase()
      .replace(/é/g, 'e').replace(/è/g, 'e').replace(/\s/g, '');

    const label = document.createElement('span');
    label.className = typeClass || '';
    label.title = dataName; // texte complet pour la popup
    // Texte tronqué dans la pill
    label.textContent = dataName.length > 22 ? dataName.slice(0, 22) + '…' : dataName;

    const btn = document.createElement('button');
    btn.className = 'pill-remove';
    btn.title = 'Supprimer';
    btn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    btn.onclick = (ev) => {
      ev.stopPropagation();
      removeTaskLinkAssignment(linkId, direction, taskId);
    };

    pill.appendChild(label);
    pill.appendChild(btn);
    slot.appendChild(pill);
    slot.classList.add('has-conn');
  }

  // ─── SUPPRESSION ASSIGNMENT (global) ───
  window.removeTaskLinkAssignment = function (linkId, direction, taskId) {
    hideTooltip();
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
