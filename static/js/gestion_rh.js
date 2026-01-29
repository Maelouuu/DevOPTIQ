/* ════════════════════════════════════════════════════════════════════════════
   GESTION RH – JavaScript
   Design System "Minimal Editorial" – Thème Marron
════════════════════════════════════════════════════════════════════════════ */

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `grh-toast ${type}`;
    toast.innerHTML = `<i class="fa-solid ${type === 'error' ? 'fa-circle-exclamation' : 'fa-check-circle'}"></i> ${message}`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function getInitials(firstName, lastName) {
    return ((firstName || '')[0] || '') + ((lastName || '')[0] || '');
}

function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════
let allRoles = [];
let fullCollabData = [];
let managerAllCollabs = [];
let managerAllRoles = [];
let managerActiveFilter = 'all';
let selectedManagerId = null;
let selectedManagerName = '';

// ═══════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    // Load roles first, then collaborators
    fetch('/gestion_rh/roles')
        .then(res => res.json())
        .then(data => {
            allRoles = data;
            populateRoleFilter();
            loadCollaborateurs();
        });

    initParamListeners();
    initRoleListeners();
    initCollabListeners();
    initManagerSection();
    initModalListeners();
});

// ═══════════════════════════════════════════════════════════════
// SECTION 1 : PARAMÈTRES ENTREPRISE
// ═══════════════════════════════════════════════════════════════
function initParamListeners() {
    document.querySelectorAll('.grh-param-row').forEach(row => {
        const key = row.dataset.key;
        const valueEl = row.querySelector('.grh-param-value');
        const editBtn = row.querySelector('.edit-param-btn');
        const actionsEl = row.querySelector('.grh-param-actions');

        editBtn.addEventListener('click', () => {
            const currentValue = valueEl.textContent.trim();
            valueEl.innerHTML = `<input type="number" value="${currentValue === '—' ? '' : currentValue}" class="grh-param-input">`;
            editBtn.style.display = 'none';

            const saveBtn = document.createElement('button');
            saveBtn.className = 'btn btn-sm btn-primary';
            saveBtn.textContent = 'Enregistrer';

            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn btn-sm btn-outline';
            cancelBtn.textContent = 'Annuler';

            saveBtn.addEventListener('click', async () => {
                const input = valueEl.querySelector('input');
                const newValue = input.value;
                const formData = new FormData();
                formData.append('key', key);
                formData.append('value', newValue);
                await fetch('/gestion_rh/update_single_setting', { method: 'POST', body: formData });
                valueEl.textContent = newValue || '—';
                editBtn.style.display = '';
                saveBtn.remove();
                cancelBtn.remove();
                showToast('Paramètre mis à jour');
            });

            cancelBtn.addEventListener('click', () => {
                valueEl.textContent = currentValue;
                editBtn.style.display = '';
                saveBtn.remove();
                cancelBtn.remove();
            });

            actionsEl.appendChild(saveBtn);
            actionsEl.appendChild(cancelBtn);
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// SECTION 2 : GESTION DES RÔLES
// ═══════════════════════════════════════════════════════════════
function initRoleListeners() {
    // Toggle create form
    document.getElementById('show-create-role').addEventListener('click', () => {
        document.getElementById('create-role-form').classList.remove('hidden');
    });

    document.getElementById('cancel-create-role').addEventListener('click', () => {
        document.getElementById('create-role-form').classList.add('hidden');
        document.getElementById('new-role-name').value = '';
    });

    // Submit create role
    document.getElementById('submit-create-role').addEventListener('click', async () => {
        const nameInput = document.getElementById('new-role-name');
        const name = nameInput.value.trim();
        if (!name) return;

        const formData = new FormData();
        formData.append('name', name);
        await fetch('/gestion_rh/role', { method: 'POST', body: formData });
        showToast('Rôle créé');
        setTimeout(() => location.reload(), 800);
    });

    // Edit & delete role buttons
    document.querySelectorAll('.grh-role-row').forEach(row => {
        const roleId = row.dataset.roleId;
        const nameEl = row.querySelector('.grh-role-name');
        const editBtn = row.querySelector('.edit-role-btn');
        const deleteBtn = row.querySelector('.delete-role-btn');

        // Delete
        deleteBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirm('Supprimer ce rôle ?')) return;
            const res = await fetch(`/gestion_rh/delete_role/${roleId}`, { method: 'POST' });
            if (res.ok) {
                row.remove();
                showToast('Rôle supprimé');
            }
        });

        // Edit
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const currentName = nameEl.textContent.trim();
            nameEl.innerHTML = `<input type="text" value="${currentName}" class="grh-role-input">`;
            editBtn.style.display = 'none';
            deleteBtn.style.display = 'none';

            const saveBtn = document.createElement('button');
            saveBtn.className = 'btn btn-sm btn-primary';
            saveBtn.textContent = 'Enregistrer';

            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn btn-sm btn-outline';
            cancelBtn.textContent = 'Annuler';

            saveBtn.addEventListener('click', async () => {
                const input = nameEl.querySelector('input');
                const newName = input.value.trim();
                if (!newName) return;

                const formData = new FormData();
                formData.append('id', roleId);
                formData.append('name', newName);
                await fetch('/gestion_rh/role', { method: 'POST', body: formData });
                nameEl.textContent = newName;
                editBtn.style.display = '';
                deleteBtn.style.display = '';
                saveBtn.remove();
                cancelBtn.remove();
                showToast('Rôle modifié');
            });

            cancelBtn.addEventListener('click', () => {
                nameEl.textContent = currentName;
                editBtn.style.display = '';
                deleteBtn.style.display = '';
                saveBtn.remove();
                cancelBtn.remove();
            });

            row.querySelector('.grh-role-actions').appendChild(saveBtn);
            row.querySelector('.grh-role-actions').appendChild(cancelBtn);
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// SECTION 3 : COLLABORATEURS
// ═══════════════════════════════════════════════════════════════
function populateRoleFilter() {
    const select = document.getElementById('filter-role');
    while (select.options.length > 1) select.remove(1);
    allRoles.forEach(role => {
        const option = document.createElement('option');
        option.value = role.name;
        option.textContent = capitalize(role.name);
        select.appendChild(option);
    });
}

function initCollabListeners() {
    document.getElementById('search-collab').addEventListener('input', loadCollaborateurs);
    document.getElementById('filter-role').addEventListener('change', loadCollaborateurs);
}

async function loadCollaborateurs() {
    const search = document.getElementById('search-collab').value;
    const role = document.getElementById('filter-role').value;

    const res = await fetch(`/gestion_rh/collaborateurs?search=${encodeURIComponent(search)}&role=${encodeURIComponent(role)}`);
    fullCollabData = await res.json();
    renderCollaborateurs(false);
}

function renderCollaborateurs(showAll = false) {
    const container = document.getElementById('collaborateur-list');
    container.innerHTML = '';
    const data = showAll ? fullCollabData : fullCollabData.slice(0, 4);

    data.forEach(user => {
        const initials = getInitials(user.name.split(' ')[0], user.name.split(' ').slice(1).join(' '));
        const rolesText = user.roles.length ? user.roles.map(r => capitalize(r)).join(', ') : 'Aucun rôle';

        const div = document.createElement('div');
        div.className = 'grh-collab-item';
        div.innerHTML = `
            <div class="grh-collab-header">
                <div class="grh-collab-avatar">${initials}</div>
                <div class="grh-collab-info">
                    <div class="grh-collab-name">
                        ${user.name}
                        <button class="edit-name-btn" title="Modifier le nom">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                    </div>
                    <div class="grh-collab-roles-summary">${rolesText}</div>
                </div>
                <i class="fa-solid fa-chevron-down grh-collab-toggle"></i>
            </div>
            <div class="grh-collab-edit">
                <div class="grh-role-checkboxes" id="collab-roles-${user.id}"></div>
                <div class="grh-collab-save-row">
                    <button class="btn btn-sm btn-secondary save-collab-roles" data-user-id="${user.id}">Enregistrer les rôles</button>
                </div>
            </div>
        `;

        // Toggle expand
        div.querySelector('.grh-collab-header').addEventListener('click', (e) => {
            if (e.target.closest('.edit-name-btn')) return;
            div.classList.toggle('expanded');
        });

        // Edit name
        div.querySelector('.edit-name-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            editCollaboratorName(user.id, user.name);
        });

        // Render role checkboxes
        const roleContainer = div.querySelector(`#collab-roles-${user.id}`);
        allRoles.forEach(r => {
            const isActive = user.roles.includes(r.name);
            const label = document.createElement('label');
            label.className = `grh-checkbox-label ${isActive ? 'active' : ''}`;
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = r.id;
            cb.checked = isActive;

            cb.addEventListener('change', () => {
                if (cb.checked) {
                    label.classList.remove('removed');
                    label.classList.add('active');
                } else if (user.roles.includes(r.name)) {
                    label.classList.remove('active');
                    label.classList.add('removed');
                } else {
                    label.classList.remove('active', 'removed');
                }
            });

            label.appendChild(cb);
            label.appendChild(document.createTextNode(capitalize(r.name)));
            roleContainer.appendChild(label);
        });

        // Save roles
        div.querySelector('.save-collab-roles').addEventListener('click', async () => {
            const selectedRoles = Array.from(roleContainer.querySelectorAll('input:checked')).map(c => c.value);
            const formData = new FormData();
            formData.append('user_id', user.id);
            selectedRoles.forEach(id => formData.append('role_ids[]', id));
            await fetch('/gestion_rh/collaborateur_roles', { method: 'POST', body: formData });
            showToast('Rôles mis à jour');
            loadCollaborateurs();
            if (selectedManagerId) loadManagerCollabs();
        });

        container.appendChild(div);
    });

    // Toggle button
    const toggleBtn = document.getElementById('toggle-collab-view');
    if (toggleBtn) {
        if (showAll) {
            toggleBtn.innerHTML = '<i class="fa-solid fa-chevron-up"></i> Réduire la liste';
        } else {
            toggleBtn.innerHTML = '<i class="fa-solid fa-chevron-down"></i> Afficher tous les collaborateurs';
        }
        toggleBtn.onclick = () => renderCollaborateurs(!showAll);
        toggleBtn.style.display = fullCollabData.length > 4 ? '' : 'none';
    }
}

function editCollaboratorName(userId, currentName) {
    const newName = prompt('Modifier le nom du collaborateur :', currentName);
    if (newName === null || newName.trim() === '' || newName.trim() === currentName) return;

    fetch('/gestion_rh/update_collaborator_name', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, name: newName.trim() })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast('Nom mis à jour');
            loadCollaborateurs();
        } else {
            showToast('Erreur lors de la mise à jour', 'error');
        }
    })
    .catch(() => showToast('Erreur réseau', 'error'));
}

// ═══════════════════════════════════════════════════════════════
// SECTION 4 : AFFECTATION DES COLLABORATEURS
// ═══════════════════════════════════════════════════════════════
function initManagerSection() {
    const managerSelect = document.getElementById('manager-select');

    // Load managers (users with role "manager")
    fetch('/gestion_rh/users_with_role?role=manager')
        .then(res => res.json())
        .then(users => {
            users.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.id;
                opt.textContent = `${u.first_name} ${u.last_name}`;
                managerSelect.appendChild(opt);
            });
        });

    // On manager change → load all collabs
    managerSelect.addEventListener('change', () => {
        selectedManagerId = managerSelect.value ? parseInt(managerSelect.value) : null;
        selectedManagerName = managerSelect.options[managerSelect.selectedIndex]?.textContent || '';
        if (selectedManagerId) {
            loadManagerCollabs();
        } else {
            document.getElementById('manager-assignment-container').innerHTML =
                '<div class="grh-no-results">Sélectionnez un manager pour voir les collaborateurs</div>';
            document.getElementById('manager-role-filter').innerHTML = '';
        }
    });
}

async function loadManagerCollabs() {
    try {
        const res = await fetch('/gestion_rh/all_collaborators_with_manager');
        const data = await res.json();
        managerAllCollabs = data.users || [];
        managerAllRoles = data.roles || [];
        managerActiveFilter = 'all';
        renderManagerRoleFilter();
        renderManagerCollabList();
    } catch (err) {
        console.error('Erreur chargement collaborateurs manager:', err);
    }
}

function renderManagerRoleFilter() {
    const bar = document.getElementById('manager-role-filter');
    if (!bar) return;

    let html = '';
    html += `<span class="role-filter-badge ${managerActiveFilter === 'all' ? 'active' : ''}" data-filter="all">Tous</span>`;
    html += `<span class="role-filter-badge ${managerActiveFilter === 'assigned' ? 'active' : ''}" data-filter="assigned">Affectés</span>`;
    managerAllRoles.forEach(r => {
        html += `<span class="role-filter-badge ${managerActiveFilter === String(r.id) ? 'active' : ''}" data-filter="${r.id}">${capitalize(r.name)}</span>`;
    });
    bar.innerHTML = html;

    bar.querySelectorAll('.role-filter-badge').forEach(badge => {
        badge.addEventListener('click', () => {
            managerActiveFilter = badge.dataset.filter;
            renderManagerRoleFilter();
            renderManagerCollabList();
        });
    });
}

function isAssignedToManager(collab, managerId) {
    // Check if any role has this manager assigned
    if (collab.roles && collab.roles.length > 0) {
        return collab.roles.some(r => r.manager_id === managerId);
    }
    // Fallback to global manager_id
    return collab.manager_id === managerId;
}

function getAssignmentStatus(collab, managerId) {
    // Returns 'full', 'partial', or 'none'
    if (!collab.roles || collab.roles.length === 0) {
        return collab.manager_id === managerId ? 'full' : 'none';
    }
    const assignedCount = collab.roles.filter(r => r.manager_id === managerId).length;
    if (assignedCount === 0) {
        // Check global fallback
        return collab.manager_id === managerId ? 'full' : 'none';
    }
    if (assignedCount === collab.roles.length) return 'full';
    return 'partial';
}

function renderManagerCollabList() {
    const container = document.getElementById('manager-assignment-container');

    // Filter
    let filtered = managerAllCollabs;
    if (managerActiveFilter === 'assigned') {
        filtered = filtered.filter(c => isAssignedToManager(c, selectedManagerId));
    } else if (managerActiveFilter !== 'all') {
        const roleId = parseInt(managerActiveFilter);
        filtered = filtered.filter(c => c.roles && c.roles.some(r => r.id === roleId));
    }

    if (filtered.length === 0) {
        container.innerHTML = '<div class="grh-no-results">Aucun collaborateur trouvé</div>';
        return;
    }

    // Sort: assigned first
    filtered.sort((a, b) => {
        const aStatus = getAssignmentStatus(a, selectedManagerId);
        const bStatus = getAssignmentStatus(b, selectedManagerId);
        const order = { full: 0, partial: 1, none: 2 };
        if (order[aStatus] !== order[bStatus]) return order[aStatus] - order[bStatus];
        return `${a.first_name} ${a.last_name}`.localeCompare(`${b.first_name} ${b.last_name}`);
    });

    container.innerHTML = filtered.map(c => {
        const initials = getInitials(c.first_name, c.last_name);
        const status = getAssignmentStatus(c, selectedManagerId);

        // Build role tags showing assignment status per role
        let rolesHtml = '';
        if (c.roles && c.roles.length > 0) {
            rolesHtml = c.roles.map(r => {
                const isRoleAssigned = r.manager_id === selectedManagerId;
                return `<span class="grh-assign-role-tag ${isRoleAssigned ? 'assigned' : 'unassigned'}">${capitalize(r.name)}</span>`;
            }).join('');
        } else {
            rolesHtml = '<span style="color:#94a3b8; font-size:11px;">Aucun rôle</span>';
        }

        let dotHtml = '';
        if (status === 'full') {
            dotHtml = '<span class="grh-assign-dot"></span>';
        } else if (status === 'partial') {
            dotHtml = '<span class="grh-assign-dot partial"></span>';
        }

        return `
            <div class="grh-assign-item ${status === 'none' ? 'unassigned' : ''}" data-user-id="${c.id}" onclick="openAssignModal(${c.id})">
                ${dotHtml}
                <div class="grh-assign-avatar">${initials}</div>
                <div class="grh-assign-info">
                    <div class="grh-assign-name">${c.first_name} ${c.last_name}</div>
                    <div class="grh-assign-roles">${rolesHtml}</div>
                </div>
                <button class="grh-assign-btn" title="Gérer l'affectation">
                    <i class="fa-solid fa-link"></i>
                </button>
            </div>
        `;
    }).join('');
}

// ═══════════════════════════════════════════════════════════════
// MODAL AFFECTATION (avec sélection par rôle)
// ═══════════════════════════════════════════════════════════════
function openAssignModal(userId) {
    const user = managerAllCollabs.find(u => u.id === userId);
    if (!user) return;

    const initials = getInitials(user.first_name, user.last_name);
    const fullName = `${user.first_name} ${user.last_name}`;

    document.getElementById('modal-assign-title').textContent = fullName;

    const body = document.getElementById('modal-assign-body');
    let rolesHtml = '';
    if (user.roles && user.roles.length > 0) {
        rolesHtml = user.roles.map(r => `<span class="grh-assign-role-badge">${capitalize(r.name)}</span>`).join('');
    } else {
        rolesHtml = '<span style="color:#94a3b8; font-size:12px; font-style:italic;">Aucun rôle</span>';
    }

    // Build role selection checkboxes
    let roleSelectHtml = '';
    if (user.roles && user.roles.length > 0) {
        const allAssigned = user.roles.every(r => r.manager_id === selectedManagerId);
        const noneAssigned = user.roles.every(r => r.manager_id !== selectedManagerId);

        roleSelectHtml = `
            <div class="grh-modal-section-title">
                <i class="fa-solid fa-list-check"></i>
                Sélectionner les rôles à affecter
                <button class="grh-modal-select-all" id="modal-toggle-all">
                    ${allAssigned ? 'Tout désélectionner' : 'Tout sélectionner'}
                </button>
            </div>
            <div class="grh-modal-role-select" id="modal-role-select">
                ${user.roles.map(r => {
                    const isRoleAssigned = r.manager_id === selectedManagerId;
                    return `
                        <label class="grh-modal-role-item ${isRoleAssigned ? 'selected' : ''}" data-role-id="${r.id}">
                            <input type="checkbox" value="${r.id}" ${isRoleAssigned ? 'checked' : ''}>
                            <span class="role-label">${capitalize(r.name)}</span>
                            <span class="role-status ${isRoleAssigned ? 'assigned' : 'not-assigned'}">
                                ${isRoleAssigned ? 'Affecté' : 'Non affecté'}
                            </span>
                        </label>
                    `;
                }).join('')}
            </div>
        `;
    }

    body.innerHTML = `
        <div class="grh-assign-collab-info">
            <div class="grh-assign-collab-avatar">${initials}</div>
            <div class="grh-assign-collab-details">
                <h4>${fullName}</h4>
                <div class="grh-assign-collab-roles-list">${rolesHtml}</div>
            </div>
        </div>
        ${roleSelectHtml}
        <div class="grh-assign-actions">
            <button class="grh-assign-action-btn" id="modal-assign-btn">
                <div class="grh-assign-action-icon">
                    <i class="fa-solid fa-link"></i>
                </div>
                <div class="grh-assign-action-text">
                    <strong>Affecter les rôles sélectionnés</strong>
                    <span>Affecter ce collaborateur à ${selectedManagerName} pour les rôles cochés</span>
                </div>
            </button>
            <button class="grh-assign-action-btn danger" id="modal-unassign-btn">
                <div class="grh-assign-action-icon">
                    <i class="fa-solid fa-link-slash"></i>
                </div>
                <div class="grh-assign-action-text">
                    <strong>Retirer les rôles sélectionnés</strong>
                    <span>Retirer l'affectation pour les rôles cochés</span>
                </div>
            </button>
        </div>
    `;

    // Bind checkbox visual toggle
    body.querySelectorAll('.grh-modal-role-item').forEach(item => {
        const cb = item.querySelector('input[type="checkbox"]');
        cb.addEventListener('change', () => {
            item.classList.toggle('selected', cb.checked);
            updateModalButtons(userId);
        });
    });

    // Toggle all
    const toggleAllBtn = body.querySelector('#modal-toggle-all');
    if (toggleAllBtn) {
        toggleAllBtn.addEventListener('click', () => {
            const checkboxes = body.querySelectorAll('#modal-role-select input[type="checkbox"]');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => {
                cb.checked = !allChecked;
                cb.closest('.grh-modal-role-item').classList.toggle('selected', !allChecked);
            });
            toggleAllBtn.textContent = allChecked ? 'Tout sélectionner' : 'Tout désélectionner';
            updateModalButtons(userId);
        });
    }

    // Bind assign button
    body.querySelector('#modal-assign-btn').addEventListener('click', () => {
        const selectedRoleIds = getSelectedModalRoleIds();
        if (selectedRoleIds.length === 0) {
            showToast('Sélectionnez au moins un rôle', 'error');
            return;
        }
        assignToManager(userId, selectedManagerId, selectedRoleIds);
    });

    // Bind unassign button
    body.querySelector('#modal-unassign-btn').addEventListener('click', () => {
        const selectedRoleIds = getSelectedModalRoleIds();
        if (selectedRoleIds.length === 0) {
            showToast('Sélectionnez au moins un rôle', 'error');
            return;
        }
        unassignFromManager(userId, selectedRoleIds);
    });

    updateModalButtons(userId);
    document.getElementById('modal-assign').classList.remove('hidden');
}

function getSelectedModalRoleIds() {
    const checkboxes = document.querySelectorAll('#modal-role-select input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => parseInt(cb.value));
}

function updateModalButtons(userId) {
    const assignBtn = document.querySelector('#modal-assign-btn');
    const unassignBtn = document.querySelector('#modal-unassign-btn');
    if (!assignBtn || !unassignBtn) return;

    const selectedRoleIds = getSelectedModalRoleIds();
    const user = managerAllCollabs.find(u => u.id === userId);
    if (!user) return;

    // Check if any selected role is not yet assigned
    const hasUnassigned = selectedRoleIds.some(rid => {
        const role = user.roles.find(r => r.id === rid);
        return role && role.manager_id !== selectedManagerId;
    });

    // Check if any selected role is already assigned
    const hasAssigned = selectedRoleIds.some(rid => {
        const role = user.roles.find(r => r.id === rid);
        return role && role.manager_id === selectedManagerId;
    });

    assignBtn.disabled = selectedRoleIds.length === 0 || !hasUnassigned;
    unassignBtn.disabled = selectedRoleIds.length === 0 || !hasAssigned;
}

function closeAssignModal() {
    document.getElementById('modal-assign').classList.add('hidden');
}

function initModalListeners() {
    document.getElementById('modal-assign-close').addEventListener('click', closeAssignModal);
    document.getElementById('modal-assign-backdrop').addEventListener('click', closeAssignModal);
}

async function assignToManager(userId, managerId, roleIds) {
    try {
        const res = await fetch('/gestion_rh/assign_manager_simple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                manager_id: managerId,
                role_ids: roleIds || null
            })
        });
        const data = await res.json();
        if (data.success) {
            // Update local state
            const user = managerAllCollabs.find(u => u.id === userId);
            if (user && roleIds) {
                user.roles.forEach(r => {
                    if (roleIds.includes(r.id)) {
                        r.manager_id = managerId;
                    }
                });
            } else if (user) {
                user.manager_id = managerId;
                user.roles.forEach(r => { r.manager_id = managerId; });
            }
            closeAssignModal();
            renderManagerCollabList();
            const count = roleIds ? roleIds.length : 'tous les';
            showToast(`${count} rôle(s) affecté(s) à ${selectedManagerName}`);
        } else {
            showToast(data.message || 'Erreur', 'error');
        }
    } catch (err) {
        console.error('Erreur affectation:', err);
        showToast("Erreur lors de l'affectation", 'error');
    }
}

async function unassignFromManager(userId, roleIds) {
    try {
        const res = await fetch('/gestion_rh/assign_manager_simple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                manager_id: null,
                role_ids: roleIds || null
            })
        });
        const data = await res.json();
        if (data.success) {
            // Update local state
            const user = managerAllCollabs.find(u => u.id === userId);
            if (user && roleIds) {
                user.roles.forEach(r => {
                    if (roleIds.includes(r.id)) {
                        r.manager_id = null;
                    }
                });
                // If all roles are unassigned, also clear global
                if (user.roles.every(r => r.manager_id === null)) {
                    user.manager_id = null;
                }
            } else if (user) {
                user.manager_id = null;
                user.roles.forEach(r => { r.manager_id = null; });
            }
            closeAssignModal();
            renderManagerCollabList();
            showToast('Affectation retirée');
        } else {
            showToast(data.message || 'Erreur', 'error');
        }
    } catch (err) {
        console.error('Erreur désaffectation:', err);
        showToast('Erreur lors de la désaffectation', 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// EXPOSE GLOBAL
// ═══════════════════════════════════════════════════════════════
window.openAssignModal = openAssignModal;
window.assignToManager = assignToManager;
window.unassignFromManager = unassignFromManager;
