/**
 * gestion_compte_new.js
 * Gestion des comptes utilisateurs - Version refaite
 */

// Variable globale pour stocker les données Excel
let excelData = [];

// ========================================
// GESTION DES ONGLETS
// ========================================

function switchTab(tabId) {
    // Masquer tous les onglets
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });

    // Désactiver tous les boutons
    document.querySelectorAll('.tab-nav-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Activer l'onglet sélectionné
    document.getElementById(tabId).classList.add('active');

    // Activer le bouton correspondant
    event.target.closest('.tab-nav-button').classList.add('active');
}

// ========================================
// DRAG & DROP EXCEL
// ========================================

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('excelFileInput');

// Clic sur la zone = ouvrir le sélecteur de fichiers
dropZone.addEventListener('click', () => {
    fileInput.click();
});

// Drag over
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

// Drag leave
dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

// Drop
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileUpload(files[0]);
    }
});

// Sélection via input
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
    }
});

// Traiter le fichier uploadé
function handleFileUpload(file) {
    const fileName = file.name;
    const fileExtension = fileName.split('.').pop().toLowerCase();

    // Vérifier l'extension
    if (!['xlsx', 'xls', 'csv'].includes(fileExtension)) {
        alert('Format de fichier non supporté. Veuillez utiliser .xlsx, .xls ou .csv');
        return;
    }

    // Lire le fichier
    const reader = new FileReader();

    reader.onload = function(e) {
        try {
            // Parse Excel file using SheetJS (si disponible)
            if (typeof XLSX !== 'undefined') {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                const jsonData = XLSX.utils.sheet_to_json(firstSheet, { header: 1 });

                excelData = parseExcelData(jsonData);
                displayPreview(excelData);
            } else {
                // Fallback pour CSV simple
                const text = e.target.result;
                const lines = text.split('\n');
                const csvData = lines.map(line => line.split(','));
                excelData = parseExcelData(csvData);
                displayPreview(excelData);
            }
        } catch (error) {
            console.error('Erreur lors de la lecture du fichier:', error);
            alert('Erreur lors de la lecture du fichier. Vérifiez le format.');
        }
    };

    // Lire selon le type de fichier
    if (fileExtension === 'csv') {
        reader.readAsText(file);
    } else {
        reader.readAsArrayBuffer(file);
    }
}

// Parser les données Excel
function parseExcelData(rawData) {
    if (rawData.length < 2) {
        alert('Le fichier ne contient pas assez de données.');
        return [];
    }

    const headers = rawData[0];
    const rows = rawData.slice(1);

    const parsed = rows.filter(row => row.length > 0 && row[0]).map(row => {
        return {
            prenom: row[0] || '',
            nom: row[1] || '',
            email: row[2] || '',
            age: row[3] || '',
            mot_de_passe: row[4] || '',
            role: row[5] || '',
            statut: row[6] || 'user'
        };
    });

    return parsed;
}

// Afficher la prévisualisation
function displayPreview(data) {
    if (data.length === 0) {
        alert('Aucune donnée valide trouvée dans le fichier.');
        return;
    }

    const previewZone = document.getElementById('previewZone');
    const previewTable = document.getElementById('previewTable');

    let html = '<div class="users-table-container"><table class="users-table">';
    html += '<thead><tr>';
    html += '<th>Prénom</th><th>Nom</th><th>Email</th><th>Âge</th><th>Mot de passe</th><th>Rôle</th><th>Statut</th>';
    html += '</tr></thead><tbody>';

    data.forEach(user => {
        html += '<tr>';
        html += `<td>${user.prenom}</td>`;
        html += `<td>${user.nom}</td>`;
        html += `<td>${user.email}</td>`;
        html += `<td>${user.age}</td>`;
        html += `<td>******</td>`;
        html += `<td>${user.role}</td>`;
        html += `<td><span class="badge badge-user">${user.statut}</span></td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';

    previewTable.innerHTML = html;
    previewZone.style.display = 'block';
}

// Confirmer l'import
function confirmImport() {
    if (excelData.length === 0) {
        alert('Aucune donnée à importer.');
        return;
    }

    // Envoyer les données au serveur
    fetch('/comptes/import_excel', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ users: excelData })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`Import réussi ! ${data.imported} utilisateur(s) importé(s).`);
            location.reload();
        } else {
            alert(`Erreur lors de l'import : ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        alert('Erreur lors de l\'envoi des données au serveur.');
    });
}

// Annuler l'import
function cancelImport() {
    excelData = [];
    document.getElementById('previewZone').style.display = 'none';
    document.getElementById('excelFileInput').value = '';
}

// ========================================
// MODAL FORMAT EXCEL
// ========================================

function showFormatModal() {
    document.getElementById('formatModal').classList.add('active');
}

function closeFormatModal() {
    document.getElementById('formatModal').classList.remove('active');
}

// ========================================
// FILTRES UTILISATEURS
// ========================================

function filterUsers() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;
    const roleFilter = document.getElementById('roleFilter').value;

    const rows = document.querySelectorAll('.user-row');

    rows.forEach(row => {
        const name = row.getAttribute('data-name').toLowerCase();
        const status = row.getAttribute('data-status');
        const role = row.getAttribute('data-role');

        const matchesSearch = name.includes(searchTerm);
        const matchesStatus = !statusFilter || status === statusFilter;
        const matchesRole = !roleFilter || role === roleFilter;

        if (matchesSearch && matchesStatus && matchesRole) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// ========================================
// GESTION DES MANAGERS
// ========================================

function toggleManagerSubordinates(managerId) {
    const subordinatesDiv = document.getElementById(`subordinates-${managerId}`);
    const icon = document.getElementById(`icon-manager-${managerId}`);

    if (subordinatesDiv.style.display === 'none' || subordinatesDiv.style.display === '') {
        subordinatesDiv.style.display = 'block';
        icon.classList.add('rotated');
    } else {
        subordinatesDiv.style.display = 'none';
        icon.classList.remove('rotated');
    }
}

function showAddCollaboratorModal(managerId, managerName) {
    document.getElementById('modalManagerId').value = managerId;
    document.getElementById('managerNameDisplay').textContent = managerName;
    document.getElementById('addCollaboratorModal').classList.add('active');
}

function closeAddCollaboratorModal() {
    document.getElementById('addCollaboratorModal').classList.remove('active');
}

// Fermer les modals en cliquant en dehors
document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
});

// ========================================
// CHARGEMENT SHEETJS (optionnel)
// ========================================

// Charger SheetJS dynamiquement si besoin
function loadSheetJS() {
    if (typeof XLSX === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdn.sheetjs.com/xlsx-0.20.0/package/dist/xlsx.full.min.js';
        document.head.appendChild(script);
    }
}

// ========================================
// AFFICHAGE DES RÔLES SUPPLÉMENTAIRES
// ========================================

function showAllRoles(event, userId) {
    event.preventDefault();
    const button = event.target;
    const roles = button.getAttribute('data-roles').split(',');

    // Créer une popup simple
    const popup = document.createElement('div');
    popup.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        min-width: 300px;
    `;

    let html = '<h3 style="margin-top: 0; color: #333;">Tous les rôles</h3>';
    html += '<div style="display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0;">';
    roles.forEach(role => {
        html += `<span class="badge badge-role">${role}</span>`;
    });
    html += '</div>';
    html += '<button onclick="closeRolesPopup()" style="width: 100%; padding: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">Fermer</button>';

    popup.innerHTML = html;
    popup.id = 'roles-popup';

    // Overlay
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 9999;
    `;
    overlay.id = 'roles-overlay';
    overlay.onclick = closeRolesPopup;

    document.body.appendChild(overlay);
    document.body.appendChild(popup);
}

function closeRolesPopup() {
    const popup = document.getElementById('roles-popup');
    const overlay = document.getElementById('roles-overlay');
    if (popup) popup.remove();
    if (overlay) overlay.remove();
}

// Charger au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    loadSheetJS();
});
