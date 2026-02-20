// static/js/gestion_outils.js

/* ── Références DOM ────────────────────────────────────────── */
const toolsContainer = document.getElementById("toolsContainer");
const toast          = document.getElementById("toast");
const toolsCount     = document.getElementById("toolsCount");

// Modale édition
const editModal      = document.getElementById("editModal");
const editModalTitle = document.getElementById("editModalTitle");
const editLabel      = document.getElementById("editLabel");
const editInput      = document.getElementById("editInput");
const saveEditBtn    = document.getElementById("saveEditBtn");
const cancelEditBtn  = document.getElementById("cancelEditBtn");
const cancelEditBtn2 = document.getElementById("cancelEditBtn2");

// Modale usages (vue seule)
const usageModal      = document.getElementById("usageModal");
const usageModalTitle = document.getElementById("usageModalTitle");
const usageModalBody  = document.getElementById("usageModalBody");
const closeUsageModal  = document.getElementById("closeUsageModal");
const closeUsageModal2 = document.getElementById("closeUsageModal2");

// Modale manage (gestion unifiée)
const manageModal       = document.getElementById("manageModal");
const manageModalTitle  = document.getElementById("manageModalTitle");
const manageModalBody   = document.getElementById("manageModalBody");
const manageModalFooter = document.getElementById("manageModalFooter");
const closeManageModal  = document.getElementById("closeManageModal");

// Création
const createToolBtn = document.getElementById("createToolBtn");
const newToolName   = document.getElementById("newToolName");
const newToolDesc   = document.getElementById("newToolDesc");

// Recherche
const toolSearch  = document.getElementById("toolSearch");
const searchClear = document.getElementById("searchClear");
const searchCount = document.getElementById("searchCount");

let toolsCache   = [];
let editContext  = { toolId: null, field: null };
let manageTarget = null;      // outil en cours de gestion
let manageUsages = [];        // usages chargés pour la modale manage

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  loadTools();

  createToolBtn.addEventListener("click", createTool);
  newToolName.addEventListener("keydown", e => { if (e.key === "Enter") createTool(); });

  // Usages modal
  closeUsageModal?.addEventListener("click",  () => toggleModal(usageModal, false));
  closeUsageModal2?.addEventListener("click", () => toggleModal(usageModal, false));

  // Manage modal close
  closeManageModal?.addEventListener("click", () => toggleModal(manageModal, false));

  // Édition
  cancelEditBtn?.addEventListener("click",  () => toggleModal(editModal, false));
  cancelEditBtn2?.addEventListener("click", () => toggleModal(editModal, false));
  saveEditBtn.addEventListener("click", saveEdit);
  editInput.addEventListener("keydown", e => { if (e.key === "Enter") saveEdit(); });

  // Recherche
  toolSearch?.addEventListener("input", onSearch);
  searchClear?.addEventListener("click", () => {
    toolSearch.value = "";
    onSearch();
    toolSearch.focus();
  });

  // Esc
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      [editModal, usageModal, manageModal].forEach(m => {
        if (m && !m.classList.contains("hidden")) toggleModal(m, false);
      });
    }
  });
});

/* ── Toast ─────────────────────────────────────────────────── */
function showToast(msg, type = "ok") {
  toast.textContent = msg;
  toast.className   = `toast show ${type}`;
  setTimeout(() => (toast.className = "toast"), 2600);
}

/* ── Recherche ─────────────────────────────────────────────── */
function onSearch() {
  const q = (toolSearch.value || "").trim().toLowerCase();
  const cards = [...document.querySelectorAll(".tool-card")];
  let visible = 0;

  cards.forEach(card => {
    const name = (card.dataset.name || "").toLowerCase();
    const desc = (card.dataset.desc || "").toLowerCase();
    const show = !q || name.includes(q) || desc.includes(q);
    card.style.display = show ? "" : "none";
    if (show) visible++;
  });

  // Bouton clear
  if (searchClear) searchClear.classList.toggle("hidden", !q);

  // Compteur
  if (searchCount) {
    if (q && cards.length) {
      searchCount.textContent = `${visible} / ${cards.length} outil${cards.length > 1 ? "s" : ""}`;
      searchCount.classList.remove("hidden");
    } else {
      searchCount.classList.add("hidden");
    }
  }
}

/* ── Chargement ──────────────────────────────────────────────  */
async function loadTools() {
  toolsContainer.innerHTML = `
    <div class="tools-loading">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <p>Chargement des outils…</p>
    </div>`;
  try {
    const res = await fetch("/gestion_outils/api/tools");
    if (!res.ok) throw new Error();
    toolsCache = await res.json();
    renderTools();
  } catch {
    toolsContainer.innerHTML = `
      <div class="tools-error">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <p>Impossible de charger la liste des outils.</p>
      </div>`;
  }
}

/* ── Rendu cartes ────────────────────────────────────────────  */
function renderTools() {
  if (toolsCount) {
    toolsCount.innerHTML = `<span class="stat-val">${toolsCache.length}</span><span class="stat-lbl">outil${toolsCache.length > 1 ? "s" : ""}</span>`;
  }

  if (!toolsCache.length) {
    toolsContainer.innerHTML = `
      <div class="tools-empty">
        <i class="fa-solid fa-box-open"></i>
        <p>Aucun outil pour le moment. Créez votre premier outil ci-dessus.</p>
      </div>`;
    return;
  }

  toolsContainer.innerHTML = "";

  toolsCache.forEach(tool => {
    const card  = document.createElement("div");
    card.className   = "tool-card";
    card.dataset.id  = tool.id;
    card.dataset.name = (tool.name || "").toLowerCase();
    card.dataset.desc = (tool.description || "").toLowerCase();

    const count = tool.usages.length;
    const desc  = (tool.description || "").trim();

    card.innerHTML = `
      <div class="tool-card__header">
        <span class="tool-card__name" title="${escapeHTML(tool.name)}">${escapeHTML(tool.name)}</span>
        <button class="icon-btn" data-edit="name" title="Modifier le nom">
          <i class="fa-solid fa-pencil"></i>
        </button>
      </div>

      <div class="tool-card__desc">
        <span class="${desc ? "" : "placeholder"}">${desc ? escapeHTML(desc) : "Aucune description"}</span>
        <button class="icon-btn" data-edit="description" title="Modifier la description">
          <i class="fa-solid fa-pencil"></i>
        </button>
      </div>

      <div class="tool-card__meta">
        <button class="badge ${count ? "badge-brown" : "badge-gray"} badge-clickable"
                data-action="see-usage"
                title="${count ? "Voir les activités utilisant cet outil" : "Aucun usage"}">
          <i class="fa-solid fa-link" style="font-size:.7rem;"></i>
          ${count} usage${count > 1 ? "s" : ""}
        </button>
      </div>

      <div class="tool-card__actions">
        <button class="btn btn-danger btn-small" data-action="manage">
          <i class="fa-solid fa-gear"></i> Gérer / Supprimer
        </button>
      </div>
    `;

    toolsContainer.appendChild(card);
  });

  toolsContainer.onclick = onCardClick;

  // Re-appliquer la recherche si active
  if (toolSearch?.value.trim()) onSearch();
}

function onCardClick(e) {
  const btn = e.target.closest("button");
  if (!btn) return;

  const card = btn.closest(".tool-card");
  const id   = parseInt(card?.dataset?.id || "0", 10);
  if (!id) return;

  // Édition via crayon
  if (btn.dataset.edit) {
    const tool = toolsCache.find(t => t.id === id);
    openEditModal(tool, btn.dataset.edit);
    return;
  }

  const action = btn.dataset.action;
  const tool   = toolsCache.find(t => t.id === id);

  if (action === "see-usage") return openUsage(tool);
  if (action === "manage")    return openManage(tool);
}

/* ── Édition ─────────────────────────────────────────────── */
function openEditModal(tool, field) {
  editContext = { toolId: tool.id, field };
  const isName = field === "name";
  editModalTitle.innerHTML = `<i class="fa-solid fa-pencil"></i> ${isName ? "Modifier le nom" : "Modifier la description"}`;
  editLabel.textContent    = isName ? "Nom de l'outil" : "Description";
  editInput.value          = (tool[field] || "").trim();
  toggleModal(editModal, true);
  setTimeout(() => editInput.focus(), 50);
}

async function saveEdit() {
  const { toolId, field } = editContext;
  if (!toolId || !field) return toggleModal(editModal, false);
  const newVal = editInput.value.trim();
  if (field === "name" && !newVal) return showToast("Le nom ne peut pas être vide.", "warn");

  const ok = await updateTool(toolId, field, newVal);
  if (ok) {
    const tool = toolsCache.find(t => t.id === toolId);
    if (tool) tool[field] = newVal;
    toggleModal(editModal, false);
    if (field === "name") await loadTools(); else renderTools();
  }
}

async function updateTool(id, field, value) {
  try {
    const body = {}; body[field] = value;
    const res  = await fetch(`/gestion_outils/api/tools/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { showToast(data.error || "Échec de la mise à jour.", "error"); return false; }
    showToast("Modifié avec succès.");
    return true;
  } catch {
    showToast("Erreur réseau.", "error");
    return false;
  }
}

/* ── Création ────────────────────────────────────────────── */
async function createTool() {
  const name = newToolName.value.trim();
  const desc = newToolDesc.value.trim();
  if (!name) { showToast("Renseigne un nom d'outil.", "warn"); newToolName.focus(); return; }

  createToolBtn.disabled  = true;
  createToolBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Ajout…';
  try {
    const res  = await fetch("/gestion_outils/api/tools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc }),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || "Échec de création.", "error"); return; }
    newToolName.value = "";
    newToolDesc.value = "";
    showToast(`Outil « ${name} » ajouté.`);
    await loadTools();
  } catch {
    showToast("Erreur réseau.", "error");
  } finally {
    createToolBtn.disabled  = false;
    createToolBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Ajouter';
  }
}

/* ── Création d'outil dans la modale ────────────────────── */
async function createToolInModal() {
  const nameInput = document.getElementById("modalNewToolName");
  const descInput = document.getElementById("modalNewToolDesc");
  const btn       = document.getElementById("modalCreateToolBtn");
  const name = (nameInput?.value || "").trim();
  const desc = (descInput?.value || "").trim();
  if (!name) { showToast("Renseigne un nom d'outil.", "warn"); nameInput?.focus(); return; }

  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
  try {
    const res  = await fetch("/gestion_outils/api/tools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc }),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || "Échec de création.", "error"); return; }

    // Ajouter au cache local
    const newTool = { id: data.id ?? data.tool_id, name, description: desc, usages: [] };
    if (newTool.id) toolsCache.push(newTool);

    // Mettre à jour le select de remplacement s'il est visible
    const sel = document.getElementById("replacementSelectNew");
    if (sel && newTool.id) {
      const opt = document.createElement("option");
      opt.value = newTool.id;
      opt.textContent = escapeHTML(name);
      sel.appendChild(opt);
    }

    if (nameInput) nameInput.value = "";
    if (descInput) descInput.value = "";
    showToast(`Outil « ${name} » créé.`);
  } catch {
    showToast("Erreur réseau.", "error");
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-plus"></i> Créer'; }
  }
}

/* ── Modal USAGES (vue seule) ────────────────────────────── */
function openUsage(tool) {
  usageModalTitle.innerHTML = `<i class="fa-solid fa-eye"></i> Usages de « ${escapeHTML(tool.name)} »`;
  usageModalBody.innerHTML  = `<div class="loading-soft"><i class="fa-solid fa-spinner fa-spin"></i> Chargement…</div>`;
  toggleModal(usageModal, true);

  fetch(`/gestion_outils/api/tools/${tool.id}/usages`)
    .then(r => r.json())
    .then(data => {
      const usages = data.usages || [];
      if (!usages.length) {
        usageModalBody.innerHTML = `<div class="empty-soft">Aucun usage pour cet outil.</div>`;
      } else {
        usageModalBody.innerHTML = `<ul class="usage-ul">${
          usages.map(u => `<li><strong>${escapeHTML(u.activity_name)}</strong> → ${escapeHTML(u.task_name)}</li>`).join("")
        }</ul>`;
      }
    })
    .catch(() => {
      usageModalBody.innerHTML = `<div class="error-soft">Erreur de chargement.</div>`;
    });
}

/* ── Modal MANAGE ─────────────────────────────────────────── */
async function openManage(tool) {
  manageTarget = tool;
  manageModalTitle.innerHTML = `<i class="fa-solid fa-screwdriver-wrench"></i> Gérer « ${escapeHTML(tool.name)} »`;

  // Chargement
  manageModalBody.innerHTML   = `<div class="loading-soft"><i class="fa-solid fa-spinner fa-spin"></i> Chargement des usages…</div>`;
  manageModalFooter.innerHTML = `<button class="btn btn-ghost" id="cancelManageBtn0">Annuler</button>`;
  document.getElementById("cancelManageBtn0")?.addEventListener("click", () => toggleModal(manageModal, false));
  toggleModal(manageModal, true);

  try {
    const res    = await fetch(`/gestion_outils/api/tools/${tool.id}/usages`);
    const data   = await res.json();
    manageUsages = data.usages || [];
    renderManageStep1();
  } catch {
    manageModalBody.innerHTML = `<div class="error-soft">Impossible de charger les usages.</div>`;
  }
}

/* ── Step 1 : Sélection + options ────────────────────────── */
function renderManageStep1() {
  const tool     = manageTarget;
  const usages   = manageUsages;
  const noUsages = usages.length === 0;

  const allOpts = toolsCache
    .filter(t => t.id !== tool.id)
    .map(t => `<option value="${t.id}">${escapeHTML(t.name)}</option>`)
    .join("");

  // Section usages avec checkboxes visuelles
  let usageSection = "";
  if (noUsages) {
    usageSection = `<div class="chk-no-usage">
      <i class="fa-solid fa-circle-check"></i>
      Cet outil n'est utilisé dans aucune tâche — suppression directe possible.
    </div>`;
  } else {
    const items = usages.map(u => `
      <label class="usage-check-item will-keep">
        <i class="fa-solid fa-circle-check chk-icon"></i>
        <input type="checkbox" class="task-check" value="${u.task_id}" checked>
        <span><strong>${escapeHTML(u.activity_name)}</strong> → ${escapeHTML(u.task_name)}</span>
      </label>`).join("");
    usageSection = `
      <label class="usage-check-item select-all-row will-keep">
        <i class="fa-solid fa-circle-check chk-icon"></i>
        <input type="checkbox" id="selectAllTasks" checked>
        <span style="font-weight:700;color:var(--brown);">Tout sélectionner / désélectionner</span>
      </label>
      <div class="usage-checkbox-list">${items}</div>`;
  }

  // Légende keep / delete
  const legend = noUsages ? "" : `
    <div class="chk-legend">
      <span class="chk-legend-item keep"><i class="fa-solid fa-circle-check"></i> Coché = conservé</span>
      <span class="chk-legend-item del"><i class="fa-solid fa-circle-xmark"></i> Décoché = supprimé</span>
    </div>`;

  // Section création dans la modale
  const createSection = `
    <div class="manage-section">
      <div class="modal-divider"></div>
      <div class="modal-section-title" style="margin-bottom:6px;">
        <i class="fa-solid fa-plus-circle"></i> Créer un nouvel outil
      </div>
      <div class="modal-create-inline">
        <div class="modal-create-row">
          <input type="text" id="modalNewToolName" class="input" placeholder="Nom de l'outil *" />
          <input type="text" id="modalNewToolDesc" class="input" placeholder="Description (optionnelle)" />
          <button class="btn btn-brown btn-small" id="modalCreateToolBtn">
            <i class="fa-solid fa-plus"></i> Créer
          </button>
        </div>
      </div>
    </div>`;

  // Contenu complet du body
  manageModalBody.innerHTML = `
    <div class="manage-section">
      <div class="modal-section-title" style="margin-bottom:4px;">
        <i class="fa-solid fa-list-check"></i> Usages (${usages.length})
      </div>
      ${legend}
      ${usageSection}
    </div>

    ${noUsages ? "" : `
    <div class="manage-section">
      <div class="modal-divider"></div>
      <div class="modal-section-title" style="margin-bottom:8px;">
        <i class="fa-solid fa-arrows-rotate"></i> Remplacer par un autre outil
      </div>
      <div class="replace-row">
        <select id="replacementSelectNew" class="select select--full">
          <option value="">— Choisir l'outil de remplacement —</option>
          ${allOpts}
        </select>
      </div>
    </div>
    `}

    <div class="manage-section">
      ${!noUsages ? '<div class="modal-divider"></div>' : ""}
      <div class="modal-section-title modal-section-title--danger" style="margin-bottom:6px;">
        <i class="fa-solid fa-trash"></i>
        ${noUsages ? "Supprimer l'outil" : "Détacher & supprimer"}
      </div>
      <p class="modal-hint">
        ${noUsages
          ? "Aucun usage : l'outil sera supprimé immédiatement."
          : "Détache l'outil des tâches décochées, puis supprime l'outil si plus aucun usage ne reste."}
      </p>
    </div>

    ${createSection}
  `;

  // Footer
  manageModalFooter.innerHTML = `
    <button class="btn btn-ghost" id="cancelManageBtn"><i class="fa-solid fa-xmark"></i> Annuler</button>
    ${noUsages ? "" : `<button class="btn btn-brown btn-small" id="previewReplaceBtn"><i class="fa-solid fa-arrows-rotate"></i> Aperçu remplacement</button>`}
    <button class="btn btn-danger btn-small" id="deleteSelBtn">
      <i class="fa-solid fa-trash"></i> ${noUsages ? "Supprimer" : "Détacher & supprimer"}
    </button>
  `;

  // Listeners footer
  document.getElementById("cancelManageBtn")?.addEventListener("click", () => toggleModal(manageModal, false));
  document.getElementById("previewReplaceBtn")?.addEventListener("click", showReplaceConfirmation);
  document.getElementById("deleteSelBtn")?.addEventListener("click", () => doDeleteSelection(noUsages));

  // Bouton créer dans la modale
  document.getElementById("modalCreateToolBtn")?.addEventListener("click", createToolInModal);
  document.getElementById("modalNewToolName")?.addEventListener("keydown", e => {
    if (e.key === "Enter") createToolInModal();
  });

  // Select-all avec mise à jour visuelle
  const selectAll = document.getElementById("selectAllTasks");
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      document.querySelectorAll(".task-check").forEach(cb => {
        cb.checked = selectAll.checked;
        _updateChkVisual(cb);
      });
      _updateChkVisual(selectAll);
    });
    document.querySelectorAll(".task-check").forEach(cb => {
      cb.addEventListener("change", () => {
        _updateChkVisual(cb);
        syncSelectAll();
      });
    });
  }
}

/* ── Visuel checkbox (keep / delete) ────────────────────── */
function _updateChkVisual(cb) {
  const label = cb.closest(".usage-check-item");
  if (!label) return;
  const icon = label.querySelector(".chk-icon");
  label.classList.toggle("will-keep",   cb.checked);
  label.classList.toggle("will-delete", !cb.checked);
  if (icon) {
    icon.className = cb.checked
      ? "fa-solid fa-circle-check chk-icon"
      : "fa-solid fa-circle-xmark chk-icon";
  }
}

function syncSelectAll() {
  const all     = document.querySelectorAll(".task-check");
  const checked = document.querySelectorAll(".task-check:checked");
  const sa      = document.getElementById("selectAllTasks");
  if (!sa) return;
  sa.checked       = all.length === checked.length;
  sa.indeterminate = checked.length > 0 && checked.length < all.length;
  // Mettre à jour le visuel de la ligne "tout sélectionner"
  _updateChkVisual(sa);
}

// Retourne les task_ids DÉCOCHÉS — ce sont eux qui sont ciblés par l'action
function getTargetTaskIds() {
  return Array.from(document.querySelectorAll(".task-check:not(:checked)"))
    .map(cb => parseInt(cb.value, 10));
}

/* ── Step 2 : Confirmation remplacement ─────────────────── */
function showReplaceConfirmation() {
  const replacementId = parseInt(document.getElementById("replacementSelectNew")?.value || "0", 10);
  if (!replacementId) return showToast("Choisis un outil de remplacement.", "warn");

  const targetIds = getTargetTaskIds(); // décochés = ciblés par le remplacement
  if (targetIds.length === 0) return showToast("Décoche au moins un usage à remplacer.", "warn");

  const replacementTool  = toolsCache.find(t => t.id === replacementId);
  const selectedUsages   = manageUsages.filter(u => targetIds.includes(u.task_id));

  const usageList = selectedUsages.map(u =>
    `<li><strong>${escapeHTML(u.activity_name)}</strong> → ${escapeHTML(u.task_name)}</li>`
  ).join("");

  const isAll = targetIds.length === manageUsages.length;

  manageModalBody.innerHTML = `
    <div class="confirm-warning">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <div>
        <p>L'outil <strong>${escapeHTML(replacementTool.name)}</strong> va remplacer
        <strong>${escapeHTML(manageTarget.name)}</strong> pour les usages suivants :</p>
      </div>
    </div>

    <ul class="usage-ul">${usageList}</ul>

    <p class="modal-hint">
      ${isAll
        ? `Tous les usages (${selectedUsages.length}) seront remplacés.`
        : `${selectedUsages.length} usage(s) sur ${manageUsages.length} seront remplacés. Les autres resteront inchangés.`}
    </p>
  `;

  manageModalFooter.innerHTML = `
    <button class="btn btn-ghost" id="backStep1Btn"><i class="fa-solid fa-arrow-left"></i> Retour</button>
    <button class="btn btn-brown" id="confirmReplaceBtn">
      <i class="fa-solid fa-check"></i> Confirmer le remplacement
    </button>
  `;

  document.getElementById("backStep1Btn")?.addEventListener("click", renderManageStep1);
  document.getElementById("confirmReplaceBtn")?.addEventListener("click",
    () => doReplace(manageTarget.id, replacementId, targetIds));
}

/* ── Exécution remplacement ──────────────────────────────── */
async function doReplace(srcId, dstId, taskIds) {
  const btn = document.getElementById("confirmReplaceBtn");
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> En cours…'; }

  try {
    const res  = await fetch(`/gestion_outils/api/tools/${srcId}/replace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ replacement_id: dstId, task_ids: taskIds }),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || "Échec du remplacement.", "error"); return; }
    showToast(`Remplacement effectué (${data.replaced_count || taskIds.length} usage(s)).`);
    toggleModal(manageModal, false);
    await loadTools();
  } catch {
    showToast("Erreur réseau.", "error");
  }
}

/* ── Exécution suppression/détachement ───────────────────── */
async function doDeleteSelection(noUsages) {
  const tool = manageTarget;

  // Aucun usage → suppression directe
  if (noUsages) {
    await doFullDelete(tool);
    return;
  }

  const targetIds = getTargetTaskIds(); // décochés = à détacher
  if (targetIds.length === 0) return showToast("Décoche au moins un usage à détacher.", "warn");

  const isAll = targetIds.length === manageUsages.length;

  try {
    if (isAll) {
      await doFullDelete(tool);
    } else {
      // Détachement partiel (seulement les décochés)
      const res  = await fetch(`/gestion_outils/api/tools/${tool.id}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_ids: targetIds }),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.error || "Échec.", "error"); return; }
      if (data.deleted) {
        showToast(`Outil « ${tool.name} » détaché et supprimé.`);
      } else {
        showToast(`Détaché de ${targetIds.length} tâche(s). ${data.remaining} usage(s) restant(s).`);
      }
      toggleModal(manageModal, false);
      await loadTools();
    }
  } catch {
    showToast("Erreur réseau.", "error");
  }
}

async function doFullDelete(tool) {
  try {
    const res  = await fetch(`/gestion_outils/api/tools/${tool.id}?force_detach=true`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || "Échec suppression.", "error"); return; }
    showToast(`Outil « ${tool.name} » supprimé.`);
    toggleModal(manageModal, false);
    await loadTools();
  } catch {
    showToast("Erreur réseau.", "error");
  }
}

/* ── Utils ───────────────────────────────────────────────── */
function toggleModal(modal, show = true) {
  if (!modal) return;
  if (show) {
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  } else {
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }
}

function escapeHTML(s) {
  return (s ?? "").toString().replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}
