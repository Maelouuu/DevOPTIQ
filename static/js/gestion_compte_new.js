/**
 * gestion_compte_new.js
 */

let excelData = [];

// ── ONGLETS ─────────────────────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabId = btn.dataset.tab;
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
        document.getElementById(tabId).classList.add('active');
        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');
    });
});

// ── DRAG & DROP EXCEL ────────────────────────────────────────────────────────

const dropZone   = document.getElementById('dropZone');
const fileInput  = document.getElementById('excelFileInput');

if (dropZone) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
    });
}

if (fileInput) {
    fileInput.addEventListener('change', e => {
        if (e.target.files.length > 0) handleFileUpload(e.target.files[0]);
    });
}

function handleFileUpload(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls', 'csv'].includes(ext)) {
        alert('Format non supporté. Utilisez .xlsx, .xls ou .csv');
        return;
    }
    const reader = new FileReader();
    reader.onload = e => {
        try {
            if (typeof XLSX !== 'undefined') {
                const data = new Uint8Array(e.target.result);
                const wb   = XLSX.read(data, { type: 'array' });
                const ws   = wb.Sheets[wb.SheetNames[0]];
                const json = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '', blankrows: false });
                excelData  = parseExcelData(json);
            } else {
                excelData = parseExcelData(e.target.result.split('\n').map(l => l.split(',')));
            }
            displayPreview(excelData);
        } catch(err) {
            console.error(err);
            alert('Erreur de lecture du fichier.');
        }
    };
    ext === 'csv' ? reader.readAsText(file) : reader.readAsArrayBuffer(file);
}

function parseExcelData(raw) {
    if (!raw.length) { alert('Fichier vide.'); return []; }
    const first    = raw[0];
    const keywords = ['prenom','prénom','nom','email','age','âge','mot de passe','password','role','rôle','statut'];
    const isHeader = first.some(c => typeof c === 'string' && keywords.includes(c.toLowerCase().trim()));
    const rows     = isHeader ? raw.slice(1) : raw;
    return rows
        .filter(r => r && r.length > 0 && (r[0] || r[2]))
        .map(r => ({
            prenom:      String(r[0] || '').trim(),
            nom:         String(r[1] || '').trim(),
            email:       String(r[2] || '').trim(),
            age:         r[3] || '',
            mot_de_passe:String(r[4] || '').trim(),
            role:        String(r[5] || '').trim(),
            statut:      String(r[6] || 'user').trim()
        }));
}

function displayPreview(data) {
    if (!data.length) { alert('Aucune donnée valide trouvée.'); return; }
    const previewTable = document.getElementById('previewTable');
    let html = '<table><thead><tr><th>Prénom</th><th>Nom</th><th>Email</th><th>Âge</th><th>Mot de passe</th><th>Rôle</th><th>Statut</th></tr></thead><tbody>';
    data.forEach(u => {
        html += `<tr><td>${u.prenom}</td><td>${u.nom}</td><td>${u.email}</td><td>${u.age}</td><td>••••••</td><td>${u.role}</td><td><span class="badge badge-user">${u.statut}</span></td></tr>`;
    });
    html += '</tbody></table>';
    previewTable.innerHTML = html;
    document.getElementById('previewZone').style.display = 'block';
}

function confirmImport() {
    if (!excelData.length) { alert('Aucune donnée à importer.'); return; }
    fetch('/comptes/import_excel', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ users: excelData })
    })
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(d => {
        if (d.success) {
            showToast(`${d.imported} utilisateur(s) importé(s)`, 'ok');
            setTimeout(() => location.reload(), 1200);
        } else {
            showToast(`Erreur : ${d.message}`, 'err');
        }
    })
    .catch(err => showToast('Erreur serveur : ' + err.message, 'err'));
}

function cancelImport() {
    excelData = [];
    document.getElementById('previewZone').style.display = 'none';
    document.getElementById('excelFileInput').value = '';
}

// ── MODALS ───────────────────────────────────────────────────────────────────

function showFormatModal()        { openModal('formatModal'); }
function closeFormatModal()       { closeModal('formatModal'); }
function closeAddCollaboratorModal() { closeModal('addCollaboratorModal'); }

function openModal(id) {
    const m = document.getElementById(id);
    if (m) { m.classList.remove('hidden'); m.setAttribute('aria-hidden', 'false'); }
}
function closeModal(id) {
    const m = document.getElementById(id);
    if (m) { m.classList.add('hidden'); m.setAttribute('aria-hidden', 'true'); }
}

// Close on backdrop click
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', e => {
        if (e.target === modal) modal.classList.add('hidden');
    });
});

// ── FILTRES ──────────────────────────────────────────────────────────────────

function filterUsers() {
    const search = (document.getElementById('searchInput')?.value || '').toLowerCase();
    const status = document.getElementById('statusFilter')?.value || '';
    const role   = document.getElementById('roleFilter')?.value   || '';
    document.querySelectorAll('.user-row').forEach(row => {
        const matchName   = row.dataset.name.toLowerCase().includes(search);
        const matchStatus = !status || row.dataset.status === status;
        const matchRole   = !role   || row.dataset.role === role;
        row.style.display = (matchName && matchStatus && matchRole) ? '' : 'none';
    });
}

// ── MANAGERS ─────────────────────────────────────────────────────────────────

function toggleManagerSubordinates(managerId) {
    const div  = document.getElementById(`subordinates-${managerId}`);
    const icon = document.getElementById(`icon-manager-${managerId}`);
    const open = div.style.display === 'none' || div.style.display === '';
    div.style.display = open ? 'block' : 'none';
    icon.classList.toggle('rotated', open);
}

function showAddCollaboratorModal(managerId, managerName) {
    document.getElementById('modalManagerId').value     = managerId;
    document.getElementById('managerNameDisplay').textContent = managerName;
    openModal('addCollaboratorModal');
}

// ── RÔLES SUPPLÉMENTAIRES ────────────────────────────────────────────────────

function showAllRoles(event, userId) {
    event.preventDefault();
    const roles  = event.currentTarget.dataset.roles.split(',');
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(59,10,31,.45);z-index:9999;display:flex;align-items:center;justify-content:center;';
    overlay.id = 'roles-overlay';
    const box = document.createElement('div');
    box.style.cssText = 'background:#fff;border-radius:12px;padding:24px;min-width:280px;max-width:400px;box-shadow:0 8px 32px rgba(157,23,77,.2);';
    box.innerHTML = `<h3 style="margin:0 0 14px;color:#3b0a1f;font-size:.95rem;">Tous les rôles</h3>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;">${roles.map(r => `<span class="badge badge-role">${r}</span>`).join('')}</div>
      <button onclick="closeRolesPopup()" style="width:100%;padding:9px;background:#9d174d;color:#fff;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:.84rem;">Fermer</button>`;
    overlay.appendChild(box);
    overlay.addEventListener('click', e => { if (e.target === overlay) closeRolesPopup(); });
    document.body.appendChild(overlay);
}

function closeRolesPopup() {
    document.getElementById('roles-overlay')?.remove();
}

// ── SUPPRESSION ──────────────────────────────────────────────────────────────

let deleteUserId = null;

function confirmDelete(userId, userName) {
    deleteUserId = userId;
    document.getElementById('deleteUserName').textContent = userName;
    openModal('deleteConfirmModal');
}

function closeDeleteModal() {
    deleteUserId = null;
    closeModal('deleteConfirmModal');
}

function executeDelete() {
    if (!deleteUserId) return;
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/comptes/delete/${deleteUserId}`;
    document.body.appendChild(form);
    form.submit();
}

// ── TOAST ────────────────────────────────────────────────────────────────────

function showToast(msg, type = '') {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.className   = 'toast' + (type ? ' toast-' + type : '');
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 3200);
}

// ── INIT ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Charger SheetJS dynamiquement
    if (typeof XLSX === 'undefined') {
        const s = document.createElement('script');
        s.src   = 'https://cdn.sheetjs.com/xlsx-0.20.0/package/dist/xlsx.full.min.js';
        document.head.appendChild(s);
    }

    // Lire les paramètres URL pour activer le bon onglet et afficher un toast
    const params = new URLSearchParams(window.location.search);
    const tabParam = params.get('tab');
    const msgParam = params.get('msg');

    if (tabParam) {
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(b => {
            b.classList.remove('active');
            b.setAttribute('aria-selected', 'false');
        });
        const targetPane = document.getElementById(tabParam);
        const targetBtn  = document.querySelector(`.tab-btn[data-tab="${tabParam}"]`);
        if (targetPane) targetPane.classList.add('active');
        if (targetBtn)  { targetBtn.classList.add('active'); targetBtn.setAttribute('aria-selected', 'true'); }
    }

    const toastMessages = {
        created: 'Utilisateur créé avec succès.',
        updated: 'Modifications enregistrées.',
        deleted: 'Utilisateur supprimé.'
    };
    if (msgParam && toastMessages[msgParam]) {
        setTimeout(() => showToast(toastMessages[msgParam], 'ok'), 80);
    }

    // Nettoyer l'URL pour éviter un re-toast au rafraîchissement
    if (tabParam || msgParam) {
        const clean = window.location.pathname;
        window.history.replaceState({}, '', clean);
    }
});
