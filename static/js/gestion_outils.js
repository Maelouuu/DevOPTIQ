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
const createToolBtn  = document.getElementById("createToolBtn");
const newToolName    = document.getElementById("newToolName");
const newToolDesc    = document.getElementById("newToolDesc");
const newToolFilePath = document.getElementById("newToolFilePath");

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

  // Toggle section créer
  document.getElementById("create-toggle-btn")?.addEventListener("click", () => {
    document.getElementById("createSection")?.classList.add("expanded");
    setTimeout(() => newToolName?.focus(), 350);
  });
  document.getElementById("create-collapse-btn")?.addEventListener("click", () => {
    document.getElementById("createSection")?.classList.remove("expanded");
  });

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

  if (searchClear) searchClear.classList.toggle("hidden", !q);

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

    const count    = tool.usages.length;
    const desc     = (tool.description || "").trim();
    const filePath = (tool.file_path || "").trim();

    const fileLink = filePath
      ? `<a class="tool-card__file-link" href="/utils/serve-file?path=${encodeURIComponent(filePath)}" target="_blank" title="Ouvrir : ${escapeHTML(filePath)}">
           <i class="fa-solid fa-paperclip"></i> <span class="tool-file-name">${escapeHTML(filePath.split(/[\\/]/).pop())}</span>
         </a>`
      : "";

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

      ${filePath ? `<div class="tool-card__file">
        ${fileLink}
        <button class="icon-btn" data-edit="file_path" title="Modifier le fichier lié">
          <i class="fa-solid fa-pencil"></i>
        </button>
      </div>` : `<div class="tool-card__file tool-card__file--empty">
        <button class="icon-btn tool-add-file-btn" data-edit="file_path" title="Lier un fichier">
          <i class="fa-solid fa-paperclip"></i> <span style="font-size:.75rem;">Lier un fichier</span>
        </button>
      </div>`}

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

  if (toolSearch?.value.trim()) onSearch();
}

function onCardClick(e) {
  const btn = e.target.closest("button");
  if (!btn) return;

  const card = btn.closest(".tool-card");
  const id   = parseInt(card?.dataset?.id || "0", 10);
  if (!id) return;

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
  const isName     = field === "name";
  const isFilePath = field === "file_path";
  const label      = isName ? "Nom de l'outil" : isFilePath ? "Chemin du fichier lié" : "Description";
  const title      = isName ? "Modifier le nom" : isFilePath ? "Modifier le fichier lié" : "Modifier la description";

  editModalTitle.innerHTML = `<i class="fa-solid fa-pencil"></i> ${title}`;
  editLabel.textContent    = label;
  editInput.value          = (tool[field] || "").trim();
  editInput.placeholder    = isFilePath ? "ex : C:\\Documents\\fichier.pdf" : "";

  // Afficher le champ chemin secondaire si on édite name ou description (pour pouvoir aussi modifier file_path en même temps)
  const fpField = document.getElementById("editFilePathField");
  const fpInput = document.getElementById("editFilePathInput");
  if (fpField && fpInput) {
    if (isName || field === "description") {
      fpField.style.display = "block";
      fpInput.value = (tool.file_path || "").trim();
    } else {
      fpField.style.display = "none";
    }
  }

  toggleModal(editModal, true);
  setTimeout(() => editInput.focus(), 50);
}

async function saveEdit() {
  const { toolId, field } = editContext;
  if (!toolId || !field) return toggleModal(editModal, false);
  const newVal = editInput.value.trim();
  if (field === "name" && !newVal) return showToast("Le nom ne peut pas être vide.", "warn");

  // Build payload — may include file_path from the secondary field
  const payload = { [field]: newVal };
  const fpInput = document.getElementById("editFilePathInput");
  const fpField = document.getElementById("editFilePathField");
  if (fpField && fpField.style.display !== "none" && fpInput) {
    payload.file_path = fpInput.value.trim() || null;
  }

  const ok = await updateToolPayload(toolId, payload);
  if (ok) {
    const tool = toolsCache.find(t => t.id === toolId);
    if (tool) {
      tool[field] = newVal;
      if ("file_path" in payload) tool.file_path = payload.file_path || "";
    }
    toggleModal(editModal, false);
    renderTools();
  }
}

async function updateToolPayload(id, payload) {
  try {
    const res  = await fetch(`/gestion_outils/api/tools/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { showToast(data.error || "Échec de la mise à jour.", "error"); return false; }
    // Sync file_path from server response if available
    const tool = toolsCache.find(t => t.id === id);
    if (tool && data.file_path !== undefined) tool.file_path = data.file_path || "";
    showToast("Modifié avec succès.");
    return true;
  } catch {
    showToast("Erreur réseau.", "error");
    return false;
  }
}

/* ── Création ────────────────────────────────────────────── */
async function createTool() {
  const name     = newToolName.value.trim();
  const desc     = newToolDesc.value.trim();
  const filePath = newToolFilePath ? newToolFilePath.value.trim() : "";
  if (!name) { showToast("Renseigne un nom d'outil.", "warn"); newToolName.focus(); return; }

  createToolBtn.disabled  = true;
  createToolBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Ajout…';
  try {
    const res  = await fetch("/gestion_outils/api/tools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc, file_path: filePath || null }),
    });
    const data = await res.json();
    if (!res.ok) { showToast(data.error || "Échec de création.", "error"); return; }
    newToolName.value = "";
    newToolDesc.value = "";
    if (newToolFilePath) newToolFilePath.value = "";
    document.getElementById("createSection")?.classList.remove("expanded");
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

    const newTool = { id: data.id ?? data.tool_id, name, description: desc, usages: [] };
    if (newTool.id) toolsCache.push(newTool);

    // Ajouter au select de remplacement s'il est visible
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

/* ── Step 1 : Nouvelle UX ────────────────────────────────── */
function renderManageStep1() {
  const tool     = manageTarget;
  const usages   = manageUsages;
  const noUsages = usages.length === 0;

  const allOpts = toolsCache
    .filter(t => t.id !== tool.id)
    .map(t => `<option value="${t.id}">${escapeHTML(t.name)}</option>`)
    .join("");

  // Section usages
  let usageSection = "";
  if (noUsages) {
    usageSection = `<div class="chk-no-usage">
      <i class="fa-solid fa-circle-check"></i>
      Cet outil n'est utilisé dans aucune tâche — suppression directe possible.
    </div>`;
  } else {
    const items = usages.map(u => `
      <label class="usage-item" data-task-id="${u.task_id}">
        <input type="checkbox" class="task-check" value="${u.task_id}">
        <span class="usage-item__icon"><i class="fa-regular fa-circle"></i></span>
        <span class="usage-item__text">
          <strong>${escapeHTML(u.activity_name)}</strong>
          <span class="usage-item__sep">›</span>
          ${escapeHTML(u.task_name)}
        </span>
      </label>`).join("");

    usageSection = `
      <div class="usage-select-bar">
        <label class="usage-select-all">
          <input type="checkbox" id="selectAllTasks">
          <span>Tout sélectionner</span>
        </label>
        <span id="usageSelCount" class="usage-sel-count">0 sélectionné</span>
      </div>
      <div class="usage-items-list">${items}</div>`;
  }

  // Section remplacement
  const replaceSection = noUsages ? "" : `
    <div class="manage-section">
      <div class="modal-divider"></div>
      <div class="modal-section-title">
        <i class="fa-solid fa-arrows-rotate"></i> Remplacer par
        <span class="modal-section-hint">Sélectionnez des usages puis choisissez le nouvel outil</span>
      </div>
      <div class="replace-select-wrap">
        <i class="fa-solid fa-screwdriver-wrench replace-sel-icon"></i>
        <select id="replacementSelectNew" class="replace-select">
          <option value="">— Choisir l'outil de remplacement —</option>
          ${allOpts}
        </select>
      </div>
      <div id="replace-preview" class="replace-preview hidden"></div>
    </div>`;

  // Section créer outil
  const createSection = `
    <div class="manage-section">
      <div class="modal-divider"></div>
      <div class="modal-section-title">
        <i class="fa-solid fa-plus-circle"></i> Créer un nouvel outil
      </div>
      <div class="modal-create-inline">
        <div class="modal-create-row">
          <div class="search-style-wrap">
            <i class="fa-solid fa-tag search-style-icon"></i>
            <input type="text" id="modalNewToolName" class="search-style-input" placeholder="Nom de l'outil *" />
          </div>
          <div class="search-style-wrap">
            <i class="fa-solid fa-align-left search-style-icon"></i>
            <input type="text" id="modalNewToolDesc" class="search-style-input" placeholder="Description (optionnelle)" />
          </div>
          <button class="btn btn-brown btn-small" id="modalCreateToolBtn">
            <i class="fa-solid fa-plus"></i> Créer
          </button>
        </div>
      </div>
    </div>`;

  manageModalBody.innerHTML = `
    <div class="manage-section">
      <div class="modal-section-title">
        <i class="fa-solid fa-list-check"></i> Usages (${usages.length})
        ${noUsages ? "" : `<span class="modal-section-hint">Cochez les usages à traiter</span>`}
      </div>
      ${usageSection}
    </div>

    ${replaceSection}

    <div class="manage-section">
      ${!noUsages ? '<div class="modal-divider"></div>' : ""}
      <div class="modal-section-title modal-section-title--danger">
        <i class="fa-solid fa-trash"></i>
        ${noUsages ? "Supprimer l'outil" : "Zone de danger"}
      </div>
      <p class="modal-hint">
        ${noUsages
          ? "Aucun usage : l'outil sera supprimé immédiatement."
          : "Détache l'outil des usages sélectionnés, puis supprime l'outil si plus aucun usage ne reste."}
      </p>
    </div>

    ${createSection}
  `;

  // Footer
  manageModalFooter.innerHTML = `
    <button class="btn btn-ghost" id="cancelManageBtn"><i class="fa-solid fa-xmark"></i> Annuler</button>
    ${noUsages ? "" : `<button class="btn btn-brown btn-small" id="previewReplaceBtn" disabled><i class="fa-solid fa-arrows-rotate"></i> Remplacer</button>`}
    <button class="btn btn-danger btn-small" id="deleteSelBtn" ${noUsages ? "" : "disabled"}>
      <i class="fa-solid fa-trash"></i> ${noUsages ? "Supprimer" : "Supprimer sélection"}
    </button>
  `;

  // Listeners footer
  document.getElementById("cancelManageBtn")?.addEventListener("click", () => toggleModal(manageModal, false));
  document.getElementById("previewReplaceBtn")?.addEventListener("click", showReplaceConfirmation);
  document.getElementById("deleteSelBtn")?.addEventListener("click", () => doDeleteSelection(noUsages));

  // Listener select remplacement
  const replaceSel = document.getElementById("replacementSelectNew");
  replaceSel?.addEventListener("change", () => {
    updateReplacePreview();
    updateActionButtons();
  });

  // Bouton créer dans la modale
  document.getElementById("modalCreateToolBtn")?.addEventListener("click", createToolInModal);
  document.getElementById("modalNewToolName")?.addEventListener("keydown", e => {
    if (e.key === "Enter") createToolInModal();
  });

  // Checkboxes usages — DÉCOCHÉES par défaut
  const selectAll = document.getElementById("selectAllTasks");
  if (selectAll) {
    selectAll.addEventListener("change", () => {
      document.querySelectorAll(".task-check").forEach(cb => {
        cb.checked = selectAll.checked;
        _updateUsageItemVisual(cb);
      });
      updateUsageSelCount();
      updateActionButtons();
    });
    document.querySelectorAll(".task-check").forEach(cb => {
      cb.addEventListener("change", () => {
        _updateUsageItemVisual(cb);
        syncSelectAll();
        updateUsageSelCount();
        updateActionButtons();
      });
    });
  }
}

/* ── Visuel item usage (coché = sélectionné pour action) ── */
function _updateUsageItemVisual(cb) {
  const label = cb.closest(".usage-item");
  if (!label) return;
  const icon = label.querySelector(".usage-item__icon i");
  label.classList.toggle("usage-item--selected", cb.checked);
  if (icon) {
    icon.className = cb.checked
      ? "fa-solid fa-circle-check"
      : "fa-regular fa-circle";
  }
}

function updateUsageSelCount() {
  const checked = document.querySelectorAll(".task-check:checked").length;
  const total   = document.querySelectorAll(".task-check").length;
  const el      = document.getElementById("usageSelCount");
  if (el) el.textContent = `${checked} / ${total} sélectionné${checked > 1 ? "s" : ""}`;
}

function updateActionButtons() {
  const checked   = document.querySelectorAll(".task-check:checked").length;
  const replaceId = document.getElementById("replacementSelectNew")?.value;

  const replaceBtn = document.getElementById("previewReplaceBtn");
  if (replaceBtn) replaceBtn.disabled = !(checked > 0 && replaceId);

  const deleteBtn = document.getElementById("deleteSelBtn");
  if (deleteBtn) deleteBtn.disabled = checked === 0;
}

function updateReplacePreview() {
  const replaceId = parseInt(document.getElementById("replacementSelectNew")?.value || "0");
  const preview   = document.getElementById("replace-preview");
  if (!preview) return;

  if (replaceId) {
    const dst = toolsCache.find(t => t.id === replaceId);
    preview.innerHTML = `
      <i class="fa-solid fa-right-long"></i>
      <span class="preview-src">${escapeHTML(manageTarget.name)}</span>
      <i class="fa-solid fa-arrow-right"></i>
      <span class="preview-dst">${escapeHTML(dst?.name || "?")}</span>
    `;
    preview.classList.remove("hidden");
  } else {
    preview.classList.add("hidden");
  }
}

function syncSelectAll() {
  const all     = document.querySelectorAll(".task-check");
  const checked = document.querySelectorAll(".task-check:checked");
  const sa      = document.getElementById("selectAllTasks");
  if (!sa) return;
  sa.checked       = all.length > 0 && all.length === checked.length;
  sa.indeterminate = checked.length > 0 && checked.length < all.length;
}

/* Retourne les task_ids COCHÉS (sélectionnés pour action) */
function getTargetTaskIds() {
  return Array.from(document.querySelectorAll(".task-check:checked"))
    .map(cb => parseInt(cb.value, 10));
}

/* ── Step 2 : Confirmation remplacement ─────────────────── */
function showReplaceConfirmation() {
  const replacementId = parseInt(document.getElementById("replacementSelectNew")?.value || "0", 10);
  if (!replacementId) return showToast("Choisis un outil de remplacement.", "warn");

  const targetIds = getTargetTaskIds();
  if (targetIds.length === 0) return showToast("Coche au moins un usage à remplacer.", "warn");

  const replacementTool = toolsCache.find(t => t.id === replacementId);
  const selectedUsages  = manageUsages.filter(u => targetIds.includes(u.task_id));

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

  if (noUsages) {
    await doFullDelete(tool);
    return;
  }

  const targetIds = getTargetTaskIds();
  if (targetIds.length === 0) return showToast("Coche au moins un usage à détacher.", "warn");

  const isAll = targetIds.length === manageUsages.length;

  try {
    if (isAll) {
      await doFullDelete(tool);
    } else {
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
