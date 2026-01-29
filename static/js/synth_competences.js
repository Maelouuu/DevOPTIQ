/* ════════════════════════════════════════════════════════════════════════════
   FICHIER À PLACER DANS : static/js/synth_competences.js
════════════════════════════════════════════════════════════════════════════ */

/* ════════════════════════════════════════════════════════════════════════════
   SYNTH_COMPETENCES.JS - Gestion modulaire des compétences
   
   Architecture:
   - État global centralisé
   - Système de modales empilables
   - Navigation fluide entre les vues
════════════════════════════════════════════════════════════════════════════ */

// ═══════════════════════════════════════════════════════════════
// ÉTAT GLOBAL
// ═══════════════════════════════════════════════════════════════
const AppState = {
    managerId: null,
    managerName: '',
    allCollaborators: [],   // Tous les collaborateurs de l'entité
    allRoles: [],           // Tous les rôles de l'entité (pour le filtre)
    activeRoleFilter: 'all', // Filtre rôle actif
    collaborators: [],      // Collaborateurs affectés au manager (legacy compat)
    selectedCollabId: null,
    selectedCollabName: '',
    roles: [],
    currentRoleId: null,
    currentRoleName: '',
    currentActivityId: null,
    currentActivityName: '',
    currentActivityData: null,
    evaluations: [],
    pendingChanges: []
};

// ═══════════════════════════════════════════════════════════════
// INITIALISATION
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 Initialisation de la page Compétences...');
    
    // Charger le manager connecté
    await loadCurrentManager();
    
    // Initialiser les événements
    initEventListeners();
    initModalListeners();
    initTabListeners();
    
    console.log('✅ Page initialisée');
});

// ═══════════════════════════════════════════════════════════════
// CHARGEMENT DES DONNÉES
// ═══════════════════════════════════════════════════════════════
async function loadCurrentManager() {
    try {
        // Récupérer l'utilisateur connecté et le manager approprié
        const res = await fetch('/competences/current_user_manager');

        if (!res.ok) {
            throw new Error('Erreur lors de la récupération du manager');
        }

        const data = await res.json();

        if (data.error) {
            throw new Error(data.error);
        }

        AppState.managerId = data.manager_id;
        AppState.managerName = data.manager_name;

        document.getElementById('manager-name').textContent = AppState.managerName;

        // Charger les collaborateurs de ce manager
        await loadCollaborators(AppState.managerId);
    } catch (err) {
        console.error('Erreur chargement manager:', err);
        showToast('Erreur lors du chargement du manager: ' + err.message, 'error');
    }
}

async function loadCollaborators(managerId) {
    try {
        const res = await fetch('/competences/all_collaborators');
        const data = await res.json();
        AppState.allCollaborators = data.users || [];
        AppState.allRoles = data.roles || [];
        // Compat: filtrer les collaborateurs affectés au manager
        AppState.collaborators = AppState.allCollaborators.filter(u => u.manager_id === managerId);

        renderRoleFilterBar();
        renderCollaboratorsList();
    } catch (err) {
        console.error('Erreur chargement collaborateurs:', err);
    }
}

async function loadUserRoles(userId) {
    showLoader('Chargement des rôles...');
    try {
        const res = await fetch(`/competences/get_user_roles/${userId}`);
        const data = await res.json();
        AppState.roles = data.roles || [];
        
        // Charger aussi les évaluations
        await loadUserEvaluations(userId);
        
        renderRolesGrid();
        hideLoader();
    } catch (err) {
        console.error('Erreur chargement rôles:', err);
        hideLoader();
        showToast('Erreur lors du chargement des rôles', 'error');
    }
}

async function loadUserEvaluations(userId) {
    try {
        const res = await fetch(`/competences/get_user_evaluations_by_user/${userId}`);
        AppState.evaluations = await res.json();
    } catch (err) {
        console.error('Erreur chargement évaluations:', err);
    }
}

async function loadRoleStructure(userId, roleId) {
    showLoader('Chargement du rôle...');
    try {
        const res = await fetch(`/competences/role_structure/${userId}/${roleId}`);
        const data = await res.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        AppState.currentRoleId = roleId;
        AppState.currentRoleName = data.role_name;
        
        hideLoader();
        return data;
    } catch (err) {
        console.error('Erreur chargement structure rôle:', err);
        hideLoader();
        showToast('Erreur lors du chargement', 'error');
        return null;
    }
}

// ═══════════════════════════════════════════════════════════════
// RENDU DES COMPOSANTS
// ═══════════════════════════════════════════════════════════════
function renderRoleFilterBar() {
    const bar = document.getElementById('role-filter-bar');
    if (!bar) return;

    let html = `<span class="role-filter-badge ${AppState.activeRoleFilter === 'all' ? 'active' : ''}" data-role-id="all">Tous</span>`;
    html += `<span class="role-filter-badge ${AppState.activeRoleFilter === 'assigned' ? 'active' : ''}" data-role-id="assigned">Affectés</span>`;
    AppState.allRoles.forEach(r => {
        html += `<span class="role-filter-badge ${AppState.activeRoleFilter === String(r.id) ? 'active' : ''}" data-role-id="${r.id}">${capitalize(r.name)}</span>`;
    });
    bar.innerHTML = html;
}

function renderCollaboratorsList() {
    const list = document.getElementById('collaborator-list');
    const emptyMsg = document.getElementById('no-collab-msg');

    // Filtrer selon le filtre actif
    let filtered = AppState.allCollaborators;
    if (AppState.activeRoleFilter === 'assigned') {
        filtered = filtered.filter(c => c.manager_id === AppState.managerId);
    } else if (AppState.activeRoleFilter !== 'all') {
        const roleId = parseInt(AppState.activeRoleFilter);
        filtered = filtered.filter(c => c.roles && c.roles.some(r => r.id === roleId));
    }

    if (filtered.length === 0) {
        list.innerHTML = '';
        emptyMsg.classList.remove('hidden');
        return;
    }

    emptyMsg.classList.add('hidden');

    // Trier : affectés en premier
    filtered.sort((a, b) => {
        const aAssigned = a.manager_id === AppState.managerId ? 0 : 1;
        const bAssigned = b.manager_id === AppState.managerId ? 0 : 1;
        if (aAssigned !== bAssigned) return aAssigned - bAssigned;
        return `${a.first_name} ${a.last_name}`.localeCompare(`${b.first_name} ${b.last_name}`);
    });

    list.innerHTML = filtered.map(c => {
        const initials = getInitials(c.first_name, c.last_name);
        const isAssigned = c.manager_id === AppState.managerId;
        const isActive = c.id === AppState.selectedCollabId;
        return `
            <li class="collab-item ${isActive ? 'active' : ''} ${!isAssigned ? 'collab-unassigned' : ''}" data-id="${c.id}" data-name="${c.first_name} ${c.last_name}">
                <div class="collab-item-wrapper">
                    <div class="collab-item-info">
                        ${isAssigned ? '<span class="collab-assigned-dot"></span>' : ''}
                        <div class="collab-avatar">${initials}</div>
                        <span class="collab-name">${c.first_name} ${c.last_name}</span>
                    </div>
                    <button class="collab-assign-btn" onclick="event.stopPropagation(); openAssignModal(${c.id})" title="Gérer l'affectation">
                        <i class="fa-solid fa-link"></i>
                    </button>
                </div>
            </li>
        `;
    }).join('');
}

function renderRolesGrid() {
    const grid = document.getElementById('roles-grid');
    const emptyState = document.getElementById('empty-state');
    
    if (!AppState.selectedCollabId) {
        grid.innerHTML = '';
        grid.classList.add('hidden');
        emptyState.classList.remove('hidden');
        return;
    }
    
    emptyState.classList.add('hidden');
    grid.classList.remove('hidden');
    
    if (AppState.roles.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1;">
                <div class="empty-state-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                </div>
                <h2>Aucun rôle attribué</h2>
                <p>Ce collaborateur n'a pas encore de rôles assignés.</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = AppState.roles.map(role => `
        <div class="role-card" data-role-id="${role.id}" data-role-name="${role.name}">
            <div class="role-card-header">
                <div class="role-card-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                        <circle cx="8.5" cy="7" r="4"/>
                        <polyline points="17,11 19,13 23,9"/>
                    </svg>
                </div>
                <div class="role-card-arrow">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9,18 15,12 9,6"/>
                    </svg>
                </div>
            </div>
            <h3 class="role-card-title">${capitalize(role.name)}</h3>
            <div class="role-card-meta">
                <span class="role-card-stat">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="7" height="7"/>
                        <rect x="14" y="3" width="7" height="7"/>
                        <rect x="14" y="14" width="7" height="7"/>
                        <rect x="3" y="14" width="7" height="7"/>
                    </svg>
                    Activités liées
                </span>
            </div>
        </div>
    `).join('');
}

function renderModalRole(data) {
    // Titre
    document.getElementById('modal-role-title').textContent = capitalize(data.role_name);
    
    // Liste des activités
    const activitiesList = document.getElementById('modal-activities-list');
    
    if (data.activities.length === 0) {
        activitiesList.innerHTML = `
            <p class="text-muted" style="grid-column: 1/-1; text-align: center; padding: 20px;">
                Aucune activité définie pour ce rôle.
            </p>
        `;
    } else {
        activitiesList.innerHTML = data.activities.map((act, idx) => `
            <div class="activity-card" data-activity-id="${act.id}" data-activity-name="${act.name}">
                <div class="activity-card-num">${idx + 1}</div>
                <span class="activity-card-name">${act.name}</span>
                <svg class="activity-card-arrow" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="9,18 15,12 9,6"/>
                </svg>
            </div>
        `).join('');
    }
    
    // Tableau synthèse
    const syntheseBody = document.getElementById('modal-synthese-body');
    syntheseBody.innerHTML = data.synthese.map(row => {
        const competencies = row.competencies && row.competencies.length > 0 
            ? `<br><small class="text-muted">Compétences : ${row.competencies.join(', ')}</small>` 
            : '';
        
        return `
            <tr>
                <td>${row.activity_name}${competencies}</td>
                <td class="eval-cell ${row.evals.garant?.note || ''}"
                    data-type="activities"
                    data-eval="garant"
                    data-activity="${row.activity_id}">
                    ${row.evals.garant?.note ? formatDate(row.evals.garant?.created_at) : ''}
                </td>
                <td class="eval-cell ${row.evals.manager?.note || ''}"
                    data-type="activities"
                    data-eval="manager"
                    data-activity="${row.activity_id}">
                    ${row.evals.manager?.note ? formatDate(row.evals.manager?.created_at) : ''}
                </td>
                <td class="eval-cell ${row.evals.rh?.note || ''}"
                    data-type="activities"
                    data-eval="rh"
                    data-activity="${row.activity_id}">
                    ${row.evals.rh?.note ? formatDate(row.evals.rh?.created_at) : ''}
                </td>
            </tr>
        `;
    }).join('');
    
    // Stocker les données pour usage ultérieur
    AppState.currentRoleData = data;
}

function renderModalActivity(activityData) {
    document.getElementById('modal-activity-title').textContent = activityData.name;
    
    // Configurer les data attributes pour le container prérequis
    const prerequisContainer = document.getElementById('prerequis-container');
    prerequisContainer.dataset.activityId = activityData.id;
    prerequisContainer.dataset.roleId = AppState.currentRoleId;
    
    // Render Savoirs
    const savoirsTbody = document.getElementById('savoirs-tbody');
    if (activityData.savoirs.length === 0) {
        savoirsTbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;">Aucun savoir défini</td></tr>';
    } else {
        savoirsTbody.innerHTML = activityData.savoirs.map(s => `
            <tr>
                <td>${s.description}</td>
                ${['1','2','3'].map(k => `
                    <td class="eval-cell ${s.evals[k]?.note || ''}"
                        data-id="${s.id}"
                        data-type="savoirs"
                        data-eval="${k}"
                        data-activity="${activityData.id}">
                        ${s.evals[k]?.note ? `<span class="note-date">${formatDate(s.evals[k]?.created_at)}</span>` : ''}
                    </td>
                `).join('')}
            </tr>
        `).join('');
    }
    
    // Render Savoir-Faire
    const sfTbody = document.getElementById('savoir-faires-tbody');
    if (activityData.savoir_faires.length === 0) {
        sfTbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;">Aucun savoir-faire défini</td></tr>';
    } else {
        sfTbody.innerHTML = activityData.savoir_faires.map(sf => `
            <tr>
                <td>${sf.description}</td>
                ${['1','2','3'].map(k => `
                    <td class="eval-cell ${sf.evals[k]?.note || ''}"
                        data-id="${sf.id}"
                        data-type="savoir_faires"
                        data-eval="${k}"
                        data-activity="${activityData.id}">
                        ${sf.evals[k]?.note ? `<span class="note-date">${formatDate(sf.evals[k]?.created_at)}</span>` : ''}
                    </td>
                `).join('')}
            </tr>
        `).join('');
    }
    
    // Render HSC
    const hscTbody = document.getElementById('hsc-tbody');
    if (activityData.hsc.length === 0) {
        hscTbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;">Aucune HSC définie</td></tr>';
    } else {
        hscTbody.innerHTML = activityData.hsc.map(h => `
            <tr>
                <td>${h.description} <small class="text-muted">(${h.niveau})</small></td>
                ${['1','2','3'].map(k => `
                    <td class="eval-cell ${h.evals[k]?.note || ''}"
                        data-id="${h.id}"
                        data-type="softskills"
                        data-eval="${k}"
                        data-activity="${activityData.id}">
                        ${h.evals[k]?.note ? `<span class="note-date">${formatDate(h.evals[k]?.created_at)}</span>` : ''}
                    </td>
                `).join('')}
            </tr>
        `).join('');
    }
    
    // Render Prérequis table (vide pour l'instant)
    renderPrerequisTable(activityData);
    
    // Render Performances (si la fonction existe)
    if (typeof renderPerformancesForActivity === 'function') {
        renderPerformancesForActivity(activityData.id);
    } else {
        renderPerformancesDefault(activityData.id);
    }
    
    // Reset to first tab
    switchTab('performances');
    
    // Stocker les données
    AppState.currentActivityId = activityData.id;
    AppState.currentActivityName = activityData.name;
    AppState.currentActivityData = activityData;
}

function renderPrerequisTable(activityData) {
    const tbody = document.getElementById('prerequis-tbody');
    const items = [];
    
    // Ajouter tous les items
    activityData.savoirs.forEach(s => {
        items.push({ id: s.id, type: 'savoir', typeLabel: 'Savoir', description: s.description });
    });
    activityData.savoir_faires.forEach(sf => {
        items.push({ id: sf.id, type: 'savoir_faire', typeLabel: 'Savoir-Faire', description: sf.description });
    });
    activityData.hsc.forEach(h => {
        items.push({ id: h.id, type: 'hsc', typeLabel: 'HSC', description: `${h.description} (${h.niveau})` });
    });
    
    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align:center;">Aucun item à commenter</td></tr>';
        return;
    }
    
    tbody.innerHTML = items.map(item => `
        <tr data-item-type="${item.type}" data-item-id="${item.id}">
            <td>${item.description}</td>
            <td><span class="type-badge ${item.type}">${item.typeLabel}</span></td>
            <td>
                <textarea class="prerequis-comment" 
                          placeholder="Commentaire du manager..."
                          data-item-type="${item.type}"
                          data-item-id="${item.id}"></textarea>
            </td>
        </tr>
    `).join('');
    
    // Activer les boutons
    enablePrerequisButtons();
}

function renderPerformancesDefault(activityId) {
    const container = document.getElementById('perf-container');
    container.innerHTML = `
        <div class="perf-section">
            <div class="perf-section-header">
                <div class="perf-section-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20V10"/>
                        <path d="M18 20V4"/>
                        <path d="M6 20v-4"/>
                    </svg>
                    Performance générale
                </div>
            </div>
            <div class="perf-section-content">
                <p class="perf-empty">Chargement des performances...</p>
            </div>
        </div>
        
        <div class="perf-section">
            <div class="perf-section-header">
                <div class="perf-section-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
                        <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
                    </svg>
                    Performances personnalisées
                </div>
            </div>
            <div class="perf-section-content">
                <p class="perf-empty">Chargement...</p>
            </div>
        </div>
    `;
    
    // Charger les vraies performances
    loadPerformanceGeneral(activityId);
}

async function loadPerformanceGeneral(activityId) {
    try {
        const res = await fetch(`/competences/general_performance/${activityId}`);
        const data = await res.json();
        
        const container = document.querySelector('#perf-container .perf-section:first-child .perf-section-content');
        
        if (data.content) {
            container.innerHTML = `
                <div class="perf-item">
                    <div class="perf-item-content">${data.content}</div>
                </div>
            `;
        } else {
            container.innerHTML = '<p class="perf-empty">Aucune performance générale définie pour cette activité.</p>';
        }
    } catch (err) {
        console.error('Erreur chargement perf générale:', err);
    }
}

function renderPlanModal(plan) {
    const body = document.getElementById('modal-plan-body');
    
    // Type badge
    let typeClass = 'plan-type-formation';
    if (plan.type?.includes('ACCOMPAGNEMENT')) typeClass = 'plan-type-accompagnement';
    if (plan.type?.includes('MAINTIEN')) typeClass = 'plan-type-maintien';
    
    let html = `<div class="plan-type-badge ${typeClass}">${plan.type || 'Plan'}</div>`;
    
    // Contexte
    if (plan.contexte_synthetique) {
        html += `
            <div class="plan-contexte">
                <h4>Contexte</h4>
                <p><strong>Activité :</strong> ${plan.contexte_synthetique.activite || '—'}</p>
                ${plan.contexte_synthetique.performances_cibles?.length ? 
                    `<p><strong>Performances cibles :</strong> ${plan.contexte_synthetique.performances_cibles.join(', ')}</p>` : ''}
            </div>
        `;
    }
    
    // Axes
    if (plan.axes && plan.axes.length > 0) {
        plan.axes.forEach((axe, idx) => {
            html += `
                <div class="plan-axe">
                    <div class="plan-axe-header">
                        <h4>Axe ${idx + 1} : ${axe.intitule}</h4>
                    </div>
                    <div class="plan-axe-body">
                        ${axe.justification ? `
                            <div class="plan-axe-section">
                                <h5>Justification</h5>
                                <p>${axe.justification}</p>
                            </div>
                        ` : ''}
                        
                        ${axe.objectifs_pedagogiques?.length ? `
                            <div class="plan-axe-section">
                                <h5>Objectifs pédagogiques</h5>
                                <ul>${axe.objectifs_pedagogiques.map(o => `<li>${o}</li>`).join('')}</ul>
                            </div>
                        ` : ''}
                        
                        ${axe.parcours?.length ? axe.parcours.map(p => `
                            <div class="plan-axe-section">
                                <h5>Parcours : ${p.option || 'Standard'}</h5>
                                ${p.methodes?.length ? `<p><strong>Méthodes :</strong> ${p.methodes.join(', ')}</p>` : ''}
                                ${p.duree_estimee_heures ? `<p><strong>Durée estimée :</strong> ${p.duree_estimee_heures}h</p>` : ''}
                                ${p.livrables_attendus?.length ? `<p><strong>Livrables :</strong> ${p.livrables_attendus.join(', ')}</p>` : ''}
                            </div>
                        `).join('') : ''}
                        
                        ${axe.jalons?.length ? `
                            <div class="plan-axe-section">
                                <h5>Jalons</h5>
                                <ul>${axe.jalons.map(j => `<li>Semaine ${j.semaine} : ${j.verif}</li>`).join('')}</ul>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
    }
    
    // Synthèse
    if (plan.synthese_charge) {
        html += `
            <div class="plan-synthese">
                <h4>Synthèse</h4>
                ${plan.synthese_charge.duree_totale_estimee_heures ? 
                    `<p><strong>Durée totale :</strong> ${plan.synthese_charge.duree_totale_estimee_heures}h</p>` : ''}
                ${plan.synthese_charge.impact_organisation ? 
                    `<p><strong>Impact organisation :</strong> ${plan.synthese_charge.impact_organisation}</p>` : ''}
                ${plan.synthese_charge.recommandation_globale ? 
                    `<p><strong>Recommandation :</strong> ${plan.synthese_charge.recommandation_globale}</p>` : ''}
            </div>
        `;
    }
    
    body.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════
function initEventListeners() {
    // Clic sur un filtre de rôle
    document.getElementById('role-filter-bar')?.addEventListener('click', (e) => {
        const badge = e.target.closest('.role-filter-badge');
        if (!badge) return;
        AppState.activeRoleFilter = badge.dataset.roleId;
        renderRoleFilterBar();
        renderCollaboratorsList();
    });

    // Clic sur un collaborateur
    document.getElementById('collaborator-list').addEventListener('click', async (e) => {
        // Ignorer si clic sur le bouton d'affectation
        if (e.target.closest('.collab-assign-btn')) return;

        const item = e.target.closest('.collab-item');
        if (!item) return;

        // Mettre à jour l'état actif
        document.querySelectorAll('.collab-item').forEach(el => el.classList.remove('active'));
        item.classList.add('active');

        AppState.selectedCollabId = parseInt(item.dataset.id);
        AppState.selectedCollabName = item.dataset.name;

        // Mettre à jour le sous-titre
        document.getElementById('selected-collab-name').textContent = AppState.selectedCollabName;

        // Activer les boutons
        document.getElementById('toggle-summary').disabled = false;
        document.getElementById('save-competencies-button').disabled = false;

        // Charger les rôles
        await loadUserRoles(AppState.selectedCollabId);
    });
    
    // Clic sur une carte de rôle
    document.getElementById('roles-grid').addEventListener('click', async (e) => {
        const card = e.target.closest('.role-card');
        if (!card) return;
        
        const roleId = parseInt(card.dataset.roleId);
        const roleName = card.dataset.roleName;
        
        const data = await loadRoleStructure(AppState.selectedCollabId, roleId);
        if (data) {
            renderModalRole(data);
            openModal('role');
        }
    });
    
    // Bouton enregistrer
    document.getElementById('save-competencies-button').addEventListener('click', saveAllEvaluations);
    
    // Bouton synthèse globale
    document.getElementById('toggle-summary').addEventListener('click', toggleGlobalSummary);
}

function initModalListeners() {
    // Fermeture des modales
    document.querySelectorAll('[data-action="close-modal"]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modal = btn.closest('.modal');
            if (modal) closeModal(modal.id.replace('modal-', ''));
        });
    });

    // Fermeture modal assign
    document.querySelector('[data-action="close-assign"]')?.addEventListener('click', () => {
        closeModal('assign');
    });
    
    document.querySelectorAll('[data-action="close-all-modals"]').forEach(btn => {
        btn.addEventListener('click', () => closeAllModals());
    });
    
    // Backdrop click
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', () => {
            const modal = backdrop.closest('.modal');
            if (modal) closeModal(modal.id.replace('modal-', ''));
        });
    });
    
    // Navigation retour
    document.querySelector('[data-action="back-to-role"]')?.addEventListener('click', () => {
        closeModal('activity');
    });
    
    document.querySelector('[data-action="back-to-activity"]')?.addEventListener('click', () => {
        closeModal('plan');
    });
    
    document.querySelector('[data-action="close-plan-modal"]')?.addEventListener('click', () => {
        closeModal('plan');
    });
    
    // Clic sur une activité dans la modal rôle
    document.getElementById('modal-activities-list').addEventListener('click', (e) => {
        const card = e.target.closest('.activity-card');
        if (!card) return;
        
        const activityId = parseInt(card.dataset.activityId);
        const activityName = card.dataset.activityName;
        
        // Trouver les données de l'activité
        const activityData = AppState.currentRoleData?.activities.find(a => a.id === activityId);
        if (activityData) {
            renderModalActivity(activityData);
            openModal('activity');
        }
    });
    
    // Clics sur les cellules d'évaluation
    document.addEventListener('click', (e) => {
        const cell = e.target.closest('.eval-cell');
        if (!cell) return;
        
        // Ignorer si dans la section synthèse globale (lecture seule)
        if (cell.closest('#global-summary-section')) return;
        
        cycleEvaluation(cell);
    });
    
    // Prérequis actions
    document.querySelector('[data-action="load-prerequis"]')?.addEventListener('click', loadPrerequisComments);
    document.querySelector('[data-action="save-prerequis"]')?.addEventListener('click', savePrerequisComments);
    document.querySelector('[data-action="generate-plan"]')?.addEventListener('click', generatePlan);
    
    // Boutons enregistrer dans les modales
    document.getElementById('save-role-evals')?.addEventListener('click', saveEvaluationsFromModal);
    document.getElementById('save-savoirs-evals')?.addEventListener('click', saveEvaluationsFromModal);
}

function initTabListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// MODALS MANAGEMENT
// ═══════════════════════════════════════════════════════════════
function openModal(modalName) {
    const modal = document.getElementById(`modal-${modalName}`);
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalName) {
    const modal = document.getElementById(`modal-${modalName}`);
    if (modal) {
        modal.classList.add('hidden');
        
        // Restaurer le scroll si plus aucune modal ouverte
        const openModals = document.querySelectorAll('.modal:not(.hidden)');
        if (openModals.length === 0) {
            document.body.style.overflow = '';
        }
    }
}

function closeAllModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.classList.add('hidden');
    });
    document.body.style.overflow = '';
}

// ═══════════════════════════════════════════════════════════════
// TABS MANAGEMENT
// ═══════════════════════════════════════════════════════════════
function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    
    // Update panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.dataset.panel === tabName);
    });
}

// ═══════════════════════════════════════════════════════════════
// EVALUATIONS
// ═══════════════════════════════════════════════════════════════
function cycleEvaluation(cell) {
    const currentNote = cell.classList.contains('green') ? 'green' :
                        cell.classList.contains('orange') ? 'orange' :
                        cell.classList.contains('red') ? 'red' : '';
    
    const notes = ['', 'red', 'orange', 'green'];
    const currentIdx = notes.indexOf(currentNote);
    const nextNote = notes[(currentIdx + 1) % notes.length];
    
    // Mettre à jour visuellement
    cell.classList.remove('green', 'orange', 'red');
    if (nextNote) {
        cell.classList.add(nextNote);
    }
    
    // Enregistrer le changement
    AppState.pendingChanges.push({
        activity_id: parseInt(cell.dataset.activity),
        item_id: cell.dataset.id ? parseInt(cell.dataset.id) : null,
        item_type: cell.dataset.type || null,
        eval_number: cell.dataset.eval,
        note: nextNote || 'empty'
    });
}

async function saveAllEvaluations() {
    if (AppState.pendingChanges.length === 0) {
        showToast('Aucune modification à enregistrer', 'warning');
        return;
    }
    
    await saveEvaluationsToServer();
}

async function saveEvaluationsFromModal() {
    if (AppState.pendingChanges.length === 0) {
        showToast('Aucune modification à enregistrer', 'warning');
        return;
    }
    
    await saveEvaluationsToServer();
}

async function saveEvaluationsToServer() {
    showLoader('Enregistrement...');
    
    try {
        const res = await fetch('/competences/save_user_evaluations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                userId: AppState.selectedCollabId,
                evaluations: AppState.pendingChanges
            })
        });
        
        const data = await res.json();
        
        if (data.success) {
            AppState.pendingChanges = [];
            showToast('Évaluations enregistrées avec succès', 'success');
        } else {
            throw new Error(data.message || 'Erreur lors de l\'enregistrement');
        }
    } catch (err) {
        console.error('Erreur sauvegarde:', err);
        showToast('Erreur lors de l\'enregistrement', 'error');
    }
    
    hideLoader();
}

// ═══════════════════════════════════════════════════════════════
// PREREQUIS & PLAN
// ═══════════════════════════════════════════════════════════════
function enablePrerequisButtons() {
    document.querySelector('[data-action="save-prerequis"]').disabled = false;
    document.querySelector('[data-action="generate-plan"]').disabled = false;
}

async function loadPrerequisComments() {
    const activityId = AppState.currentActivityId;
    const userId = AppState.selectedCollabId;
    
    if (!activityId || !userId) return;
    
    try {
        const res = await fetch(`/competences_plan/get_prerequis/${userId}/${activityId}`);
        const comments = await res.json();
        
        // Remplir les textareas
        comments.forEach(c => {
            const textarea = document.querySelector(
                `.prerequis-comment[data-item-type="${c.item_type}"][data-item-id="${c.item_id}"]`
            );
            if (textarea) {
                textarea.value = c.comment || '';
            }
        });
        
        showToast('Commentaires chargés', 'success');
    } catch (err) {
        console.error('Erreur chargement prérequis:', err);
        showToast('Erreur lors du chargement', 'error');
    }
}

async function savePrerequisComments() {
    const activityId = AppState.currentActivityId;
    const userId = AppState.selectedCollabId;
    
    if (!activityId || !userId) return;
    
    const comments = [];
    document.querySelectorAll('.prerequis-comment').forEach(textarea => {
        if (textarea.value.trim()) {
            comments.push({
                item_type: textarea.dataset.itemType,
                item_id: parseInt(textarea.dataset.itemId),
                comment: textarea.value.trim()
            });
        }
    });
    
    showLoader('Enregistrement des commentaires...');
    
    try {
        const res = await fetch('/competences_plan/save_prerequis', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                activity_id: activityId,
                comments: comments
            })
        });
        
        const data = await res.json();
        
        if (data.ok) {
            showToast('Commentaires enregistrés', 'success');
        } else {
            throw new Error('Erreur lors de l\'enregistrement');
        }
    } catch (err) {
        console.error('Erreur sauvegarde prérequis:', err);
        showToast('Erreur lors de l\'enregistrement', 'error');
    }
    
    hideLoader();
}

async function generatePlan() {
    const activityId = AppState.currentActivityId;
    const roleId = AppState.currentRoleId;
    const userId = AppState.selectedCollabId;
    
    if (!activityId || !roleId || !userId) return;
    
    // Sauvegarder d'abord les commentaires
    await savePrerequisComments();
    
    showLoader('Génération du plan en cours...');
    
    try {
        // Construire le payload de contexte
        const prerequisComments = [];
        document.querySelectorAll('.prerequis-comment').forEach(textarea => {
            if (textarea.value.trim()) {
                prerequisComments.push({
                    item_type: textarea.dataset.itemType,
                    item_id: parseInt(textarea.dataset.itemId),
                    comment: textarea.value.trim()
                });
            }
        });
        
        const payload = {
            user_id: userId,
            role_id: roleId,
            activity_id: activityId,
            payload_contexte: {
                role: { id: roleId, name: AppState.currentRoleName },
                activity: AppState.currentActivityData,
                prerequis_comments: prerequisComments
            }
        };
        
        const res = await fetch('/competences_plan/generate_plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if (data.ok && data.plan) {
            renderPlanModal(data.plan);
            openModal('plan');
            showToast('Plan généré avec succès', 'success');
        } else {
            throw new Error(data.error || 'Erreur lors de la génération');
        }
    } catch (err) {
        console.error('Erreur génération plan:', err);
        showToast('Erreur lors de la génération du plan', 'error');
    }
    
    hideLoader();
}

// ═══════════════════════════════════════════════════════════════
// GLOBAL SUMMARY
// ═══════════════════════════════════════════════════════════════
async function toggleGlobalSummary() {
    const section = document.getElementById('global-summary-section');
    const btn = document.getElementById('toggle-summary');
    
    if (section.classList.contains('hidden')) {
        // Charger et afficher
        showLoader('Chargement de la synthèse...');
        
        try {
            const res = await fetch(`/competences/global_summary/${AppState.selectedCollabId}`);
            
            // Vérifier si la réponse est OK
            if (!res.ok) {
                throw new Error(`Erreur serveur: ${res.status} ${res.statusText}`);
            }
            
            const html = await res.text();
            
            // Vérifier si on a reçu du contenu valide
            if (!html || html.includes('Service unavailable') || html.includes('error')) {
                throw new Error('Le serveur n\'a pas pu générer la synthèse');
            }
            
            section.innerHTML = html;
            section.classList.remove('hidden');
            btn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
                Masquer la synthèse
            `;
        } catch (err) {
            console.error('Erreur chargement synthèse:', err);
            showToast('Erreur lors du chargement de la synthèse. Veuillez réessayer.', 'error');
            
            // Afficher un message dans la section
            section.innerHTML = `
                <div class="empty-state" style="padding: 40px;">
                    <div class="empty-state-icon" style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="1.5">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="12" y1="8" x2="12" y2="12"/>
                            <line x1="12" y1="16" x2="12.01" y2="16"/>
                        </svg>
                    </div>
                    <h2 style="color: #dc2626;">Erreur de chargement</h2>
                    <p>Impossible de charger la synthèse globale. Le serveur est peut-être temporairement indisponible.</p>
                    <button class="btn btn-outline" onclick="document.getElementById('global-summary-section').classList.add('hidden'); document.getElementById('toggle-summary').innerHTML = '<svg width=\\'18\\' height=\\'18\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'currentColor\\' stroke-width=\\'2\\'><path d=\\'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z\\'/><polyline points=\\'14,2 14,8 20,8\\'/><line x1=\\'16\\' y1=\\'13\\' x2=\\'8\\' y2=\\'13\\'/><line x1=\\'16\\' y1=\\'17\\' x2=\\'8\\' y2=\\'17\\'/><polyline points=\\'10,9 9,9 8,9\\'/></svg> Synthèse globale';">
                        Fermer
                    </button>
                </div>
            `;
            section.classList.remove('hidden');
        }
        
        hideLoader();
    } else {
        // Masquer
        section.classList.add('hidden');
        btn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14,2 14,8 20,8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10,9 9,9 8,9"/>
            </svg>
            Synthèse globale
        `;
    }
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════
function getInitials(firstName, lastName) {
    return `${(firstName || '')[0] || ''}${(lastName || '')[0] || ''}`.toUpperCase();
}

function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    } catch {
        return '';
    }
}

function showLoader(text = 'Chargement...') {
    const loader = document.getElementById('page-loader');
    const loaderText = loader.querySelector('.loader-text');
    if (loaderText) loaderText.textContent = text;
    loader.classList.remove('hidden');
}

function hideLoader() {
    document.getElementById('page-loader').classList.add('hidden');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            ${type === 'success' ? '<polyline points="20,6 9,17 4,12"/>' :
              type === 'error' ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>' :
              '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'}
        </svg>
        ${message}
    `;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 4000);
}

// ═══════════════════════════════════════════════════════════════
// ASSIGNMENT MODAL
// ═══════════════════════════════════════════════════════════════
function openAssignModal(userId) {
    const user = AppState.allCollaborators.find(u => u.id === userId);
    if (!user) return;

    const isAssigned = user.manager_id === AppState.managerId;
    const initials = getInitials(user.first_name, user.last_name);
    const fullName = `${user.first_name} ${user.last_name}`;

    document.getElementById('modal-assign-title').textContent = fullName;

    const body = document.getElementById('modal-assign-body');
    let rolesHtml = '';
    if (user.roles && user.roles.length > 0) {
        rolesHtml = user.roles.map(r => `<span class="assign-role-badge">${capitalize(r.name)}</span>`).join('');
    } else {
        rolesHtml = '<span style="color:#94a3b8; font-size:12px; font-style:italic;">Aucun rôle</span>';
    }

    let actionsHtml = '';
    if (isAssigned) {
        actionsHtml = `
            <button class="assign-action-btn danger" onclick="unassignCollaborator(${user.id})">
                <div class="assign-action-icon">
                    <i class="fa-solid fa-link-slash"></i>
                </div>
                <div class="assign-action-text">
                    <strong>Retirer l'affectation</strong>
                    <span>Ce collaborateur ne sera plus assigné à ${AppState.managerName}</span>
                </div>
            </button>
        `;
    } else {
        actionsHtml = `
            <button class="assign-action-btn" onclick="assignCollaborator(${user.id}, ${AppState.managerId})">
                <div class="assign-action-icon">
                    <i class="fa-solid fa-link"></i>
                </div>
                <div class="assign-action-text">
                    <strong>Affecter à ${AppState.managerName}</strong>
                    <span>Ce collaborateur sera assigné globalement au manager</span>
                </div>
            </button>
        `;
    }

    body.innerHTML = `
        <div class="assign-collab-info">
            <div class="assign-collab-avatar">${initials}</div>
            <div class="assign-collab-details">
                <h3>${fullName}</h3>
                <div class="assign-collab-roles">${rolesHtml}</div>
            </div>
        </div>
        <div class="assign-actions">
            ${actionsHtml}
        </div>
    `;

    openModal('assign');
}

async function assignCollaborator(userId, managerId) {
    try {
        const res = await fetch('/competences/assign_collaborator', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, manager_id: managerId })
        });
        const data = await res.json();
        if (data.success) {
            // Mettre à jour l'état local
            const user = AppState.allCollaborators.find(u => u.id === userId);
            if (user) user.manager_id = managerId;
            AppState.collaborators = AppState.allCollaborators.filter(u => u.manager_id === AppState.managerId);
            closeModal('assign');
            renderCollaboratorsList();
            showToast('Collaborateur affecté avec succès', 'success');
        } else {
            showToast(data.message || 'Erreur', 'error');
        }
    } catch (err) {
        console.error('Erreur affectation:', err);
        showToast('Erreur lors de l\'affectation', 'error');
    }
}

async function unassignCollaborator(userId) {
    try {
        const res = await fetch('/competences/assign_collaborator', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, manager_id: null })
        });
        const data = await res.json();
        if (data.success) {
            const user = AppState.allCollaborators.find(u => u.id === userId);
            if (user) user.manager_id = null;
            AppState.collaborators = AppState.allCollaborators.filter(u => u.manager_id === AppState.managerId);
            closeModal('assign');
            renderCollaboratorsList();
            showToast('Affectation retirée', 'success');
        } else {
            showToast(data.message || 'Erreur', 'error');
        }
    } catch (err) {
        console.error('Erreur désaffectation:', err);
        showToast('Erreur lors de la désaffectation', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// EXPOSE GLOBAL (pour compatibilité avec autres scripts)
// ═══════════════════════════════════════════════════════════════
window.AppState = AppState;
window.showLoader = showLoader;
window.hideLoader = hideLoader;
window.showToast = showToast;
window.openModal = openModal;
window.closeModal = closeModal;
window.saveEvaluationsFromModal = saveEvaluationsFromModal;
window.openAssignModal = openAssignModal;
window.assignCollaborator = assignCollaborator;
window.unassignCollaborator = unassignCollaborator;