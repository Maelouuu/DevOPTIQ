/**
 * activities_tabs.js
 * Gestion des onglets et de l'affichage des activités
 */

/**
 * Toggle l'affichage du contenu d'une activité
 */
function toggleActivity(activityId) {
    const content = document.getElementById(`content-${activityId}`);
    const icon = document.getElementById(`icon-${activityId}`);
    const container = document.querySelector(`[data-activity-id="${activityId}"]`);

    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        icon.textContent = '▼';
    } else {
        content.style.display = 'none';
        icon.textContent = '▶';
    }
}

// ── État du split-view par activité ──
const splitState = {};  // { activityId: { left: tabId, right: tabId } }

/**
 * Ouvre un onglet spécifique et masque les autres.
 * Si un split-view est actif, le quitter d'abord.
 */
function openTab(event, tabId, activityId) {
    // Quitter le split-view si actif
    if (splitState[activityId]) {
        exitSplitView(activityId);
    }

    // Masquer tous les contenus d'onglets pour cette activité
    const allTabContents = document.querySelectorAll(`#content-${activityId} .tab-content`);
    allTabContents.forEach(content => {
        content.classList.remove('active');
        content.classList.remove('split-active-left', 'split-active-right');
    });

    // Désactiver tous les boutons d'onglets pour cette activité
    const allTabButtons = document.querySelectorAll(`#content-${activityId} .tab-button`);
    allTabButtons.forEach(button => {
        button.classList.remove('active');
    });

    // Afficher l'onglet sélectionné
    const selectedTab = document.getElementById(tabId);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Activer le bouton d'onglet cliqué
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    }
}

// ── Split-View : Drag & Drop ──

let draggedTabId = null;
let draggedActivityId = null;

function initSplitViewDragDrop() {
    document.addEventListener('dragstart', function(e) {
        const btn = e.target.closest('.tab-button[draggable="true"]');
        if (!btn) return;
        draggedTabId = btn.dataset.tabId;
        draggedActivityId = btn.dataset.activityId;
        btn.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', draggedTabId);

        // Afficher la drop zone pour cette activité (après un léger délai pour ne pas interférer)
        setTimeout(() => {
            const dropZone = document.getElementById(`split-drop-zone-${draggedActivityId}`);
            if (dropZone) {
                dropZone.style.display = 'flex';
            }
        }, 100);
    });

    document.addEventListener('dragend', function(e) {
        const btn = e.target.closest('.tab-button[draggable="true"]');
        if (btn) btn.classList.remove('dragging');

        // Cacher toutes les drop zones
        document.querySelectorAll('.split-drop-zone').forEach(dz => {
            dz.style.display = 'none';
            dz.classList.remove('drag-over');
        });
        draggedTabId = null;
        draggedActivityId = null;
    });

    // Drop zone events (délégation)
    document.addEventListener('dragover', function(e) {
        const dropZone = e.target.closest('.split-drop-zone');
        if (dropZone) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            dropZone.classList.add('drag-over');
        }
        // Permettre aussi le drop sur un split-panel existant
        const panel = e.target.closest('.split-panel');
        if (panel) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            panel.classList.add('drag-over-panel');
        }
    });

    document.addEventListener('dragleave', function(e) {
        const dropZone = e.target.closest('.split-drop-zone');
        if (dropZone) {
            dropZone.classList.remove('drag-over');
        }
        const panel = e.target.closest('.split-panel');
        if (panel) {
            panel.classList.remove('drag-over-panel');
        }
    });

    document.addEventListener('drop', function(e) {
        const dropZone = e.target.closest('.split-drop-zone');
        const panel = e.target.closest('.split-panel');

        if (dropZone) {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const activityId = draggedActivityId;
            const droppedTabId = draggedTabId;

            if (!activityId || !droppedTabId) return;

            // Trouver l'onglet actuellement actif
            const activeBtn = document.querySelector(`#content-${activityId} .tab-button.active`);
            const activeTabId = activeBtn ? activeBtn.dataset.tabId : null;

            if (activeTabId && activeTabId !== droppedTabId) {
                enterSplitView(activityId, activeTabId, droppedTabId);
            }
        } else if (panel && splitState[draggedActivityId]) {
            // Drop sur un panel existant → remplacer ce panel
            e.preventDefault();
            panel.classList.remove('drag-over-panel');
            const activityId = draggedActivityId;
            const droppedTabId = draggedTabId;
            const side = panel.classList.contains('split-left') ? 'left' : 'right';

            if (!activityId || !droppedTabId) return;

            const state = splitState[activityId];
            const otherSide = side === 'left' ? 'right' : 'left';

            // Ne pas remplacer par le même onglet
            if (state[otherSide] === droppedTabId || state[side] === droppedTabId) return;

            replaceSplitPanel(activityId, side, droppedTabId);
        }
    });
}

/**
 * Active le split-view : affiche deux onglets côte à côte
 */
function enterSplitView(activityId, leftTabId, rightTabId) {
    // Sauvegarder l'état
    splitState[activityId] = { left: leftTabId, right: rightTabId };

    const contentArea = document.getElementById(`content-${activityId}`);

    // Masquer tous les tab-content d'abord
    contentArea.querySelectorAll('.tab-content').forEach(tc => {
        tc.classList.remove('active', 'split-active-left', 'split-active-right');
    });

    // Cacher la drop zone
    const dropZone = document.getElementById(`split-drop-zone-${activityId}`);
    if (dropZone) dropZone.style.display = 'none';

    // Trouver les labels des onglets
    const leftBtn = contentArea.querySelector(`.tab-button[data-tab-id="${leftTabId}"]`);
    const rightBtn = contentArea.querySelector(`.tab-button[data-tab-id="${rightTabId}"]`);
    const leftLabel = leftBtn ? leftBtn.dataset.tabLabel : 'Gauche';
    const rightLabel = rightBtn ? rightBtn.dataset.tabLabel : 'Droite';

    // Supprimer un ancien split-container s'il existe
    const oldSplit = contentArea.querySelector('.split-view-container');
    if (oldSplit) oldSplit.remove();

    // Créer le conteneur split
    const splitContainer = document.createElement('div');
    splitContainer.className = 'split-view-container active';
    splitContainer.innerHTML = `
        <div class="split-panel split-left" data-tab-id="${leftTabId}">
            <div class="split-panel-header">
                <span>${leftLabel}</span>
                <button class="split-close-btn" onclick="closeSplitPanel('${activityId}', 'left')" title="Fermer">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="split-panel-content" id="split-left-content-${activityId}"></div>
        </div>
        <div class="split-divider"></div>
        <div class="split-panel split-right" data-tab-id="${rightTabId}">
            <div class="split-panel-header">
                <span>${rightLabel}</span>
                <button class="split-close-btn" onclick="closeSplitPanel('${activityId}', 'right')" title="Fermer">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="split-panel-content" id="split-right-content-${activityId}"></div>
        </div>
    `;

    // Insérer le split-container après les tabs
    const tabsContainer = contentArea.querySelector('.tabs-container');
    tabsContainer.insertAdjacentElement('afterend', splitContainer);

    // Déplacer les tab-content dans les panels
    const leftContent = document.getElementById(leftTabId);
    const rightContent = document.getElementById(rightTabId);

    if (leftContent) {
        document.getElementById(`split-left-content-${activityId}`).appendChild(leftContent);
        leftContent.classList.add('split-active-left');
    }
    if (rightContent) {
        document.getElementById(`split-right-content-${activityId}`).appendChild(rightContent);
        rightContent.classList.add('split-active-right');
    }

    // Mettre à jour les boutons d'onglets
    contentArea.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tabId === leftTabId || btn.dataset.tabId === rightTabId) {
            btn.classList.add('active');
        }
    });
}

/**
 * Remplace le contenu d'un panel split par un autre onglet
 */
function replaceSplitPanel(activityId, side, newTabId) {
    const state = splitState[activityId];
    if (!state) return;

    const contentArea = document.getElementById(`content-${activityId}`);
    const splitContainer = contentArea.querySelector('.split-view-container');
    if (!splitContainer) return;

    // Remettre l'ancien tab-content à sa place
    const oldTabId = state[side];
    const oldContent = document.getElementById(oldTabId);
    if (oldContent) {
        oldContent.classList.remove('split-active-left', 'split-active-right');
        // Remettre dans le content area principal (après le split-container)
        contentArea.appendChild(oldContent);
    }

    // Mettre le nouveau contenu dans le panel
    const panelContent = document.getElementById(`split-${side}-content-${activityId}`);
    const newContent = document.getElementById(newTabId);
    const panel = splitContainer.querySelector(`.split-${side}`);

    if (panelContent && newContent) {
        panelContent.appendChild(newContent);
        newContent.classList.add(side === 'left' ? 'split-active-left' : 'split-active-right');
    }

    // Mettre à jour le label du header
    const btn = contentArea.querySelector(`.tab-button[data-tab-id="${newTabId}"]`);
    const label = btn ? btn.dataset.tabLabel : '';
    if (panel) {
        const headerSpan = panel.querySelector('.split-panel-header span');
        if (headerSpan) headerSpan.textContent = label;
        panel.dataset.tabId = newTabId;
    }

    // Mettre à jour l'état
    state[side] = newTabId;

    // Mettre à jour les boutons actifs
    contentArea.querySelectorAll('.tab-button').forEach(b => {
        b.classList.remove('active');
        if (b.dataset.tabId === state.left || b.dataset.tabId === state.right) {
            b.classList.add('active');
        }
    });
}

/**
 * Ferme un panel du split-view, l'autre reprend toute la largeur
 */
function closeSplitPanel(activityId, side) {
    const state = splitState[activityId];
    if (!state) return;

    const contentArea = document.getElementById(`content-${activityId}`);
    const otherSide = side === 'left' ? 'right' : 'left';
    const remainingTabId = state[otherSide];

    // Remettre les deux tab-content dans le contentArea principal
    const leftContent = document.getElementById(state.left);
    const rightContent = document.getElementById(state.right);

    if (leftContent) {
        leftContent.classList.remove('split-active-left', 'split-active-right');
        contentArea.appendChild(leftContent);
    }
    if (rightContent) {
        rightContent.classList.remove('split-active-left', 'split-active-right');
        contentArea.appendChild(rightContent);
    }

    // Supprimer le conteneur split
    const splitContainer = contentArea.querySelector('.split-view-container');
    if (splitContainer) splitContainer.remove();

    // Quitter l'état split
    delete splitState[activityId];

    // Ouvrir l'onglet restant normalement
    openTab(null, remainingTabId, activityId);

    // Mettre le bon bouton actif
    const btn = contentArea.querySelector(`.tab-button[data-tab-id="${remainingTabId}"]`);
    if (btn) btn.classList.add('active');
}

/**
 * Quitte le split-view et restaure le mode onglet normal
 */
function exitSplitView(activityId) {
    const state = splitState[activityId];
    if (!state) return;

    const contentArea = document.getElementById(`content-${activityId}`);

    // Remettre les tab-content dans le contentArea
    const leftContent = document.getElementById(state.left);
    const rightContent = document.getElementById(state.right);

    if (leftContent) {
        leftContent.classList.remove('split-active-left', 'split-active-right');
        contentArea.appendChild(leftContent);
    }
    if (rightContent) {
        rightContent.classList.remove('split-active-left', 'split-active-right');
        contentArea.appendChild(rightContent);
    }

    // Supprimer le conteneur split
    const splitContainer = contentArea.querySelector('.split-view-container');
    if (splitContainer) splitContainer.remove();

    delete splitState[activityId];
}

/**
 * Ouvre automatiquement une activité et un onglet spécifique
 * Utile pour les liens profonds depuis d'autres pages
 */
function openActivityTab(activityId, tabName) {
    // Ouvrir l'activité si elle est fermée
    const content = document.getElementById(`content-${activityId}`);
    const icon = document.getElementById(`icon-${activityId}`);
    const activityContainer = document.querySelector(`[data-activity-id="${activityId}"]`);

    if (content && (content.style.display === 'none' || content.style.display === '')) {
        content.style.display = 'block';
        if (icon) {
            icon.textContent = '▼';
        }
    }

    // Ouvrir l'onglet spécifique
    const tabId = `${tabName}-${activityId}`;
    openTab(null, tabId, activityId);

    // Scroller jusqu'à l'activité
    if (activityContainer) {
        activityContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/**
 * Initialisation au chargement de la page
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialiser le drag & drop pour le split-view
    initSplitViewDragDrop();

    // Vérifier s'il y a un hash dans l'URL pour ouvrir une activité spécifique
    const hash = window.location.hash;
    if (hash) {
        const match = hash.match(/#activity-(\d+)(?:-(.+))?/);
        if (match) {
            const activityId = match[1];
            const tabName = match[2] || 'overview';

            // Attendre un court instant pour que le DOM soit complètement chargé
            setTimeout(() => {
                openActivityTab(activityId, tabName);
            }, 100);
        }
    }
});

/**
 * Fonction pour ouvrir/fermer tous les détails d'activités
 */
function toggleAllActivities(expand = true) {
    const allActivities = document.querySelectorAll('.activity-container');

    allActivities.forEach(container => {
        const activityId = container.getAttribute('data-activity-id');
        const content = document.getElementById(`content-${activityId}`);
        const icon = document.getElementById(`icon-${activityId}`);

        if (content && icon) {
            if (expand) {
                content.style.display = 'block';
                icon.textContent = '▼';
            } else {
                content.style.display = 'none';
                icon.textContent = '▶';
            }
        }
    });
}

// Exposer les fonctions globalement
window.toggleActivity = toggleActivity;
window.openTab = openTab;
window.openActivityTab = openActivityTab;
window.toggleAllActivities = toggleAllActivities;
window.enterSplitView = enterSplitView;
window.closeSplitPanel = closeSplitPanel;
window.replaceSplitPanel = replaceSplitPanel;
