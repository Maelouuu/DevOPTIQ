// static/js/gestion_outils.js

// Références DOM
const toolsContainer = document.getElementById("toolsContainer");
const toast = document.getElementById("toast");

// Modale édition
const editModal        = document.getElementById("editModal");
const editModalTitle   = document.getElementById("editModalTitle");
const editLabel        = document.getElementById("editLabel");
const editInput        = document.getElementById("editInput");
const saveEditBtn      = document.getElementById("saveEditBtn");
const cancelEditBtn    = document.getElementById("cancelEditBtn");
const cancelEditBtn2   = document.getElementById("cancelEditBtn2");

// Modale suppression
const deleteModal       = document.getElementById("deleteModal");
const deleteModalTitle  = document.getElementById("deleteModalTitle");
const deleteModalUsages = document.getElementById("deleteModalUsages");
const replacementSelect = document.getElementById("replacementSelect");
const confirmReplaceBtn = document.getElementById("confirmReplaceBtn");
const forceDeleteBtn    = document.getElementById("forceDeleteBtn");
const closeDeleteModal  = document.getElementById("closeDeleteModal");
const closeDeleteModal2 = document.getElementById("closeDeleteModal2");

// Modale usages
const usageModal     = document.getElementById("usageModal");
const usageModalTitle = document.getElementById("usageModalTitle");
const usageModalBody  = document.getElementById("usageModalBody");
const closeUsageModal  = document.getElementById("closeUsageModal");
const closeUsageModal2 = document.getElementById("closeUsageModal2");

// Création
const createToolBtn = document.getElementById("createToolBtn");
const newToolName   = document.getElementById("newToolName");
const newToolDesc   = document.getElementById("newToolDesc");

// Compteur dans le banner
const toolsCount = document.getElementById("toolsCount");

let toolsCache  = [];
let toolToDelete = null;
let editContext  = { toolId: null, field: null };

document.addEventListener("DOMContentLoaded", () => {
  loadTools();

  createToolBtn.addEventListener("click", createTool);
  newToolName.addEventListener("keydown", e => { if (e.key === "Enter") createTool(); });

  // Suppression
  closeDeleteModal?.addEventListener("click",  () => toggleModal(deleteModal, false));
  closeDeleteModal2?.addEventListener("click", () => toggleModal(deleteModal, false));
  confirmReplaceBtn.addEventListener("click", doReplaceInDeleteFlow);
  forceDeleteBtn.addEventListener("click", doForceDelete);

  // Usages
  closeUsageModal?.addEventListener("click",  () => toggleModal(usageModal, false));
  closeUsageModal2?.addEventListener("click", () => toggleModal(usageModal, false));

  // Édition
  cancelEditBtn?.addEventListener("click",  () => toggleModal(editModal, false));
  cancelEditBtn2?.addEventListener("click", () => toggleModal(editModal, false));
  saveEditBtn.addEventListener("click", saveEdit);
  editInput.addEventListener("keydown", e => { if (e.key === "Enter") saveEdit(); });

  // Esc pour toutes les modales
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      [editModal, deleteModal, usageModal].forEach(m => {
        if (!m.classList.contains("hidden")) toggleModal(m, false);
      });
    }
  });
});

function showToast(msg, type = "ok") {
  toast.textContent = msg;
  toast.className = `toast show ${type}`;
  setTimeout(() => (toast.className = "toast"), 2400);
}

/* ── Chargement ──────────────────────────────────────────── */
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

/* ── Rendu cartes ────────────────────────────────────────── */
function renderTools() {
  // Mise à jour du compteur dans le banner
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

  const allOptions = toolsCache
    .map(t => `<option value="${t.id}">${escapeHTML(t.name)}</option>`)
    .join("");

  toolsContainer.innerHTML = "";

  toolsCache.forEach(tool => {
    const card = document.createElement("div");
    card.className = "tool-card";
    card.dataset.id = tool.id;

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
        <span class="badge ${count ? "badge-brown" : "badge-gray"}">
          <i class="fa-solid fa-link" style="font-size:.7rem;"></i>
          ${count} usage${count > 1 ? "s" : ""}
        </span>
        <button class="btn-link" data-action="see-usage">
          <i class="fa-solid fa-eye"></i> Voir
        </button>
      </div>

      <hr class="tool-card__sep">

      <div class="tool-card__replace">
        <select class="select replace-select">
          <option value="">— Remplacer par —</option>
          ${allOptions}
        </select>
        <button class="btn btn-brown btn-small" data-action="replace" title="Remplacer partout">
          <i class="fa-solid fa-arrows-rotate"></i>
        </button>
      </div>

      <div class="tool-card__actions">
        <button class="btn btn-danger btn-small" data-action="delete">
          <i class="fa-solid fa-trash"></i> Supprimer
        </button>
      </div>
    `;

    // Désactiver l'option de l'outil lui-même dans le select de remplacement
    card.querySelector(`option[value="${tool.id}"]`)?.setAttribute("disabled", "disabled");

    toolsContainer.appendChild(card);
  });

  toolsContainer.onclick = onCardClick;
}

function onCardClick(e) {
  const btn = e.target.closest("button");
  if (!btn) return;

  const card = btn.closest(".tool-card");
  const id   = parseInt(card?.dataset?.id || "0", 10);
  if (!id) return;

  // Édition via icône crayon
  if (btn.dataset.edit === "name" || btn.dataset.edit === "description") {
    const tool = toolsCache.find(t => t.id === id);
    openEditModal(tool, btn.dataset.edit);
    return;
  }

  const action = btn.dataset.action;

  if (action === "replace") {
    const select = card.querySelector(".replace-select");
    const target = parseInt(select.value || "0", 10);
    if (!target || target === id) return showToast("Choisis un autre outil de remplacement.", "warn");
    return replaceTool(id, target);
  }

  if (action === "delete") {
    const tool = toolsCache.find(t => t.id === id);
    return openDelete(tool);
  }

  if (action === "see-usage") {
    const tool = toolsCache.find(t => t.id === id);
    return openUsage(tool);
  }
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
  if (!name) {
    showToast("Renseigne un nom d'outil.", "warn");
    newToolName.focus();
    return;
  }
  createToolBtn.disabled = true;
  createToolBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Ajout…';
  try {
    const res  = await fetch("/gestion_outils/api/tools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc }),
    });
    const data = await res.json();
    if (!res.ok) return showToast(data.error || "Échec de création.", "error");
    newToolName.value = "";
    newToolDesc.value = "";
    showToast(`Outil « ${name} » ajouté.`);
    await loadTools();
  } catch {
    showToast("Erreur réseau.", "error");
  } finally {
    createToolBtn.disabled = false;
    createToolBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Ajouter';
  }
}

/* ── Remplacement ────────────────────────────────────────── */
async function replaceTool(srcId, dstId) {
  try {
    const res  = await fetch(`/gestion_outils/api/tools/${srcId}/replace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ replacement_id: parseInt(dstId, 10) }),
    });
    const data = await res.json();
    if (!res.ok) return showToast(data.error || "Échec du remplacement.", "error");
    showToast("Remplacement effectué.");
    await loadTools();
  } catch {
    showToast("Erreur réseau.", "error");
  }
}

/* ── Suppression ─────────────────────────────────────────── */
function openDelete(tool) {
  toolToDelete = tool;
  deleteModalTitle.textContent = `Supprimer « ${tool.name} »`;
  replacementSelect.innerHTML  =
    `<option value="">— Choisir un outil —</option>` +
    toolsCache.filter(t => t.id !== tool.id)
              .map(t => `<option value="${t.id}">${escapeHTML(t.name)}</option>`)
              .join("");
  deleteModalUsages.innerHTML = `<div class="loading-soft"><i class="fa-solid fa-spinner fa-spin"></i> Recherche des usages…</div>`;
  toggleModal(deleteModal, true);

  fetch(`/gestion_outils/api/tools/${tool.id}/usages`)
    .then(r => r.json())
    .then(data => {
      const usages = data.usages || [];
      if (!usages.length) {
        deleteModalUsages.innerHTML = `<div class="empty-soft">Aucun usage détecté — suppression sans impact.</div>`;
      } else {
        deleteModalUsages.innerHTML = `<ul class="usage-ul">${
          usages.map(u => `<li><strong>${escapeHTML(u.activity_name)}</strong> → ${escapeHTML(u.task_name)}</li>`).join("")
        }</ul>`;
      }
    })
    .catch(() => {
      deleteModalUsages.innerHTML = `<div class="error-soft">Impossible d'obtenir les usages.</div>`;
    });
}

async function doReplaceInDeleteFlow() {
  if (!toolToDelete) return;
  const dst = replacementSelect.value;
  if (!dst) return showToast("Choisis un outil de remplacement.", "warn");
  await replaceTool(toolToDelete.id, dst);
  toggleModal(deleteModal, false);
}

async function doForceDelete() {
  if (!toolToDelete) return;
  try {
    const res  = await fetch(`/gestion_outils/api/tools/${toolToDelete.id}?force_detach=true`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) return showToast(data.error || "Échec suppression.", "error");
    showToast(`Outil « ${toolToDelete.name} » supprimé.`);
    toggleModal(deleteModal, false);
    await loadTools();
  } catch {
    showToast("Erreur réseau.", "error");
  }
}

/* ── Usages ──────────────────────────────────────────────── */
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
      usageModalBody.innerHTML = `<div class="error-soft">Erreur de chargement des usages.</div>`;
    });
}

/* ── Utils ───────────────────────────────────────────────── */
function toggleModal(modal, show = true) {
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
