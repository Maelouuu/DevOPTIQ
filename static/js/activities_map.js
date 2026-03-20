/* ============================================================
   CARTOGRAPHIE DES ACTIVITÉS - WIZARD UNIFIÉ
   Version corrigée - ouverture wizard
============================================================ */

const SHAPE_ACTIVITY_MAP = window.CARTO_SHAPE_MAP || {};
const SVG_EXISTS = window.SVG_EXISTS || false;
const ACTIVE_ENTITY = window.ACTIVE_ENTITY || null;
const ALL_ENTITIES = window.ALL_ENTITIES || [];
const VISIO_NS = "http://schemas.microsoft.com/visio/2003/SVGExtensions/";

/* État global */
let svgElement = null;
let currentScale = 0.5;
let panX = 0, panY = 0;
let isPanning = false;
let startX = 0, startY = 0;
let hasMoved = false;
let svgWidth = 0, svgHeight = 0;

const ZOOM_MIN = 0.1, ZOOM_MAX = 10;

/* État du wizard */
const wizardState = {
  selectedEntity: null,
  mode: null,
  vsdxFile: null,
  svgFile: null,
  keepVsdx: false,
  keepSvg: false,
  connectionsPreview: null,
  entitiesCache: []
};

/* Helpers */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const formatSize = (b) => b < 1024 ? b + ' o' : b < 1048576 ? (b/1024).toFixed(1) + ' Ko' : (b/1048576).toFixed(1) + ' Mo';

/* ============================================================
   PAN / ZOOM
============================================================ */
function centerCartography() {
  const wrapper = $("#carto-pan-wrapper");
  if (!wrapper || !svgWidth || !svgHeight) return;
  const r = wrapper.getBoundingClientRect();
  const sw = svgWidth * currentScale;
  const sh = svgHeight * currentScale;
  panX = Math.max(20, (r.width - sw) / 2);
  panY = Math.max(20, (r.height - sh) / 2);
  applyTransform();
}

function updateZoomDisplay() {
  const btn = $("#carto-zoom-reset");
  if (btn) btn.textContent = Math.round(currentScale * 100) + '%';
}

function applyTransform() {
  const inner = $("#pan-inner");
  if (inner) inner.style.transform = `translate(${panX}px, ${panY}px) scale(${currentScale})`;
  updateZoomDisplay();
}

function zoomAt(delta, mx, my) {
  const old = currentScale;
  currentScale = delta > 0 
    ? Math.min(ZOOM_MAX, currentScale * 1.15)
    : Math.max(ZOOM_MIN, currentScale * 0.85);
  const r = currentScale / old;
  panX = mx - (mx - panX) * r;
  panY = my - (my - panY) * r;
  applyTransform();
}

function initZoomButtons() {
  const wrapper = $("#carto-pan-wrapper");
  $("#carto-zoom-in")?.addEventListener("click", () => {
    const r = wrapper?.getBoundingClientRect();
    if (r) zoomAt(1, r.width/2, r.height/2);
  });
  $("#carto-zoom-out")?.addEventListener("click", () => {
    const r = wrapper?.getBoundingClientRect();
    if (r) zoomAt(-1, r.width/2, r.height/2);
  });
  $("#carto-zoom-reset")?.addEventListener("click", () => {
    if (wrapper && svgWidth && svgHeight) {
      const r = wrapper.getBoundingClientRect();
      currentScale = Math.min((r.width - 40) / svgWidth, (r.height - 40) / svgHeight, 1);
      currentScale = Math.max(currentScale, 0.1);
    } else {
      currentScale = 0.5;
    }
    centerCartography();
  });
}

function initPan() {
  const wrapper = $("#carto-pan-wrapper");
  const inner = $("#pan-inner");
  if (!wrapper || !inner) return;

  let sx = 0, sy = 0;

  wrapper.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    isPanning = true;
    hasMoved = false;
    startX = e.clientX;
    startY = e.clientY;
    sx = panX; sy = panY;
    wrapper.classList.add("panning");
    inner.classList.add("no-transition");
  });

  window.addEventListener("mousemove", (e) => {
    if (!isPanning) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    if (Math.sqrt(dx*dx + dy*dy) > 5) hasMoved = true;
    panX = sx + dx;
    panY = sy + dy;
    applyTransform();
  });

  window.addEventListener("mouseup", () => {
    if (!isPanning) return;
    isPanning = false;
    wrapper.classList.remove("panning");
    inner.classList.remove("no-transition");
    setTimeout(() => hasMoved = false, 10);
  });

  wrapper.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = wrapper.getBoundingClientRect();
    zoomAt(e.deltaY > 0 ? -1 : 1, e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
}

/* ============================================================
   CHARGEMENT SVG
============================================================ */
async function loadSvgInline() {
  const container = $("#svg-container");
  if (!container) return;

  if (!SVG_EXISTS) {
    container.innerHTML = '<div class="svg-placeholder"><p>🗺️ Aucune cartographie</p><p>Utilisez "📦 Gérer la cartographie" pour importer</p></div>';
    return;
  }

  try {
    const res = await fetch("/activities/svg?t=" + Date.now());
    if (!res.ok) throw new Error("SVG non trouvé");
    container.innerHTML = await res.text();
    svgElement = container.querySelector("svg");
    if (!svgElement) throw new Error("Pas d'élément SVG");
    setupSvg();
  } catch (e) {
    container.innerHTML = `<div class="svg-error"><p>❌ Erreur</p><p>${e.message}</p></div>`;
  }
}

function setupSvg() {
  if (!svgElement) return;

  const vb = svgElement.viewBox?.baseVal;
  if (vb?.width > 0 && vb?.height > 0) {
    svgWidth = vb.width;
    svgHeight = vb.height;
  } else {
    svgWidth = parseFloat(svgElement.getAttribute("width")) || 1000;
    svgHeight = parseFloat(svgElement.getAttribute("height")) || 800;
  }

  svgElement.style.width = svgWidth + "px";
  svgElement.style.height = svgHeight + "px";
  svgElement.style.display = "block";

  activateSvgClicks();
  initZoomButtons();

  const wrapper = $("#carto-pan-wrapper");
  if (wrapper) {
    const r = wrapper.getBoundingClientRect();
    currentScale = Math.min((r.width - 40) / svgWidth, (r.height - 40) / svgHeight, 1);
    currentScale = Math.max(currentScale, 0.1);
  }

  setTimeout(centerCartography, 50);
}

function activateSvgClicks() {
  if (!svgElement) return;

  svgElement.querySelectorAll("*").forEach((el) => {
    let mid = el.getAttributeNS(VISIO_NS, "mID") || el.getAttribute("v:mID") || el.getAttribute("data-mid");
    if (!mid) {
      for (let a of el.attributes || []) {
        if (a.name.toLowerCase().includes("mid")) { mid = a.value; break; }
      }
    }
    if (!mid) return;

    const actId = SHAPE_ACTIVITY_MAP[mid];
    if (!actId) return;

    el.dataset.activityId = actId;
    el.style.cursor = "pointer";
    el.classList.add("carto-activity");

    el.addEventListener("mouseenter", () => {
      el.style.filter = "drop-shadow(0 0 6px #22c55e)";
      el.style.opacity = "0.9";
    });
    el.addEventListener("mouseleave", () => {
      el.style.filter = "";
      el.style.opacity = "1";
    });
    el.addEventListener("click", (e) => {
      if (!hasMoved) {
        e.stopPropagation();
        window.location.href = `/activities/view?activity_id=${actId}`;
      }
    });
  });
}

function initListClicks() {
  $$(".activity-item").forEach((li) => {
    li.addEventListener("click", () => {
      const id = li.dataset.id;
      if (id) window.location.href = `/activities/view?activity_id=${id}`;
    });
  });
}

/* ============================================================
   GESTION DES MODALS (SÉCURISÉE)
============================================================ */
function hideAllModals() {
  const modals = ["confirm-delete-modal", "rename-modal", "carto-wizard-popup"];
  modals.forEach(id => {
    const modal = document.getElementById(id);
    if (modal) {
      modal.classList.add("hidden");
      modal.style.display = "none";
    }
  });
}

function showModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.remove("hidden");
    modal.style.display = "flex";
  }
}

function hideModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.add("hidden");
    modal.style.display = "none";
  }
}

function initModalOverlays() {
  const deleteModal = $("#confirm-delete-modal");
  const renameModal = $("#rename-modal");

  if (deleteModal) {
    deleteModal.addEventListener("click", (e) => {
      if (e.target === deleteModal) hideModal("confirm-delete-modal");
    });
  }

  if (renameModal) {
    renameModal.addEventListener("click", (e) => {
      if (e.target === renameModal) hideModal("rename-modal");
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      hideModal("confirm-delete-modal");
      hideModal("rename-modal");
      hideModal("carto-wizard-popup");
    }
  });
}

/* ============================================================
   WIZARD
============================================================ */
function initWizard() {
  const popup = $("#carto-wizard-popup");
  const btnOpen = $("#carto-wizard-btn");
  
  if (!popup || !btnOpen) return;

  // CORRECTION: Utiliser showModal pour ouvrir
  btnOpen.addEventListener("click", () => {
    resetWizard();
    loadEntitiesList();
    showModal("carto-wizard-popup");
  });

  $("#close-wizard")?.addEventListener("click", () => hideModal("carto-wizard-popup"));
  popup.addEventListener("click", (e) => {
    if (e.target.classList.contains("wizard-overlay")) hideModal("carto-wizard-popup");
  });

  // Création entité
  $("#wizard-create-entity-btn")?.addEventListener("click", createEntity);
  $("#wizard-new-entity-name")?.addEventListener("keypress", (e) => { if (e.key === "Enter") createEntity(); });

  // Navigation
  $("#action-back")?.addEventListener("click", () => goToScreen("entities"));
  $("#wizard-new-btn")?.addEventListener("click", () => startSteps("new"));
  $("#wizard-update-btn")?.addEventListener("click", () => startSteps("update"));

  // Actions entité
  $("#wizard-activate-btn")?.addEventListener("click", activateEntity);
  $("#wizard-rename-btn")?.addEventListener("click", () => showModal("rename-modal"));
  $("#wizard-delete-btn")?.addEventListener("click", () => showModal("confirm-delete-modal"));

  // Étapes
  $("#step1-back")?.addEventListener("click", () => goToScreen("action"));
  $("#step1-next")?.addEventListener("click", () => goToStep(2));
  $("#step2-back")?.addEventListener("click", () => goToStep(1));
  $("#step2-next")?.addEventListener("click", () => goToStep(3));
  $("#step3-back")?.addEventListener("click", () => goToStep(2));
  $("#step3-submit")?.addEventListener("click", submitWizard);

  // Écrans finaux
  $("#success-close")?.addEventListener("click", () => window.location.reload());
  $("#error-retry")?.addEventListener("click", () => goToStep(3));
  $("#error-close")?.addEventListener("click", () => hideModal("carto-wizard-popup"));

  // Checkboxes
  $("#keep-vsdx-checkbox")?.addEventListener("change", (e) => { wizardState.keepVsdx = e.target.checked; toggleDropzone("vsdx"); });
  $("#keep-svg-checkbox")?.addEventListener("change", (e) => { wizardState.keepSvg = e.target.checked; toggleDropzone("svg"); });

  // Dropzones
  initDropzone("vsdx");
  initDropzone("svg");

  // Modals
  $("#cancel-delete-btn")?.addEventListener("click", () => hideModal("confirm-delete-modal"));
  $("#confirm-delete-btn")?.addEventListener("click", deleteEntity);
  $("#cancel-rename-btn")?.addEventListener("click", () => hideModal("rename-modal"));
  $("#confirm-rename-btn")?.addEventListener("click", renameEntity);

  initModalOverlays();
}

function resetWizard() {
  Object.assign(wizardState, { selectedEntity: null, mode: null, vsdxFile: null, svgFile: null, keepVsdx: false, keepSvg: false, connectionsPreview: null });
  const kv = $("#keep-vsdx-checkbox"), ks = $("#keep-svg-checkbox");
  if (kv) kv.checked = false;
  if (ks) ks.checked = false;
  $("#vsdx-preview")?.classList.add("hidden");
  $("#svg-preview")?.classList.add("hidden");
  $("#vsdx-dropzone")?.classList.remove("hidden", "disabled");
  $("#svg-dropzone")?.classList.remove("hidden", "disabled");
  const vi = $("#vsdx-file-input"), si = $("#svg-file-input");
  if (vi) vi.value = "";
  if (si) si.value = "";
  goToScreen("entities");
  $("#wizard-progress")?.classList.add("hidden");
}

/* Entités */
async function loadEntitiesList() {
  const list = $("#wizard-entities-list");
  const empty = $("#wizard-entities-empty");
  if (!list) return;

  try {
    const res = await fetch("/activities/api/entities");
    const data = await res.json();
    wizardState.entitiesCache = data;

    if (!data.length) { list.innerHTML = ""; empty?.classList.remove("hidden"); return; }
    empty?.classList.add("hidden");

    list.innerHTML = data.map(e => `
      <div class="entity-grid-item ${e.is_active ? 'active' : ''}" data-id="${e.id}">
        <div class="entity-grid-icon">🏢</div>
        <div class="entity-grid-info">
          <span class="entity-grid-name">${e.name}</span>
          <span class="entity-grid-stats">${e.activities_count || 0} activités</span>
        </div>
        ${e.is_active ? '<span class="entity-grid-badge">Active</span>' : ''}
        ${e.svg_filename ? '<span class="entity-grid-svg">🖼️</span>' : ''}
      </div>
    `).join("");

    list.querySelectorAll(".entity-grid-item").forEach(item => {
      item.addEventListener("click", () => selectEntity(parseInt(item.dataset.id)));
    });
  } catch (e) {
    list.innerHTML = '<p class="error">Erreur de chargement</p>';
  }
}

async function createEntity() {
  const input = $("#wizard-new-entity-name");
  const name = input?.value.trim();
  if (!name) { alert("Nom requis"); return; }

  try {
    const res = await fetch("/activities/api/entities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    input.value = "";
    await loadEntitiesList();
    setTimeout(() => selectEntity(data.entity.id), 50);
  } catch (e) { alert("Erreur réseau"); }
}

async function selectEntity(id) {
  const entity = wizardState.entitiesCache.find(e => e.id === id);
  if (!entity) return;

  let connCount = 0;
  try {
    const res = await fetch(`/activities/api/entities/${id}/details`);
    if (res.ok) {
      const d = await res.json();
      connCount = d.connections_count || 0;
      entity.svg_exists = d.svg_exists;
      entity.vsdx_exists = d.vsdx_exists;
      entity.current_svg = d.current_svg;
      entity.current_vsdx = d.current_vsdx;
    }
  } catch (e) {}

  wizardState.selectedEntity = entity;

  $("#selected-entity-name").textContent = entity.name;
  $("#selected-entity-activities").textContent = entity.activities_count || 0;
  $("#selected-entity-connections").textContent = connCount;
  
  const badge = $("#selected-entity-active-badge");
  if (badge) badge.classList.toggle("hidden", !entity.is_active);
  
  const actBtn = $("#wizard-activate-btn");
  if (actBtn) actBtn.style.display = entity.is_active ? "none" : "";

  const svgVal = $("#selected-entity-svg-value");
  const vsdxVal = $("#selected-entity-vsdx-value");
  if (svgVal) {
    svgVal.textContent = entity.svg_exists ? "✓ Présent" : "—";
    svgVal.className = "file-value " + (entity.svg_exists ? "present" : "");
  }
  if (vsdxVal) {
    vsdxVal.textContent = entity.vsdx_exists ? "✓ Présent" : "—";
    vsdxVal.className = "file-value " + (entity.vsdx_exists ? "present" : "");
  }

  const updateBtn = $("#wizard-update-btn");
  if (updateBtn) updateBtn.disabled = !(entity.svg_exists || entity.vsdx_exists);

  goToScreen("action");
}

async function activateEntity() {
  if (!wizardState.selectedEntity) return;
  try {
    const res = await fetch(`/activities/api/entities/${wizardState.selectedEntity.id}/activate`, { method: "POST" });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    window.location.reload();
  } catch (e) { alert("Erreur réseau"); }
}

async function deleteEntity() {
  if (!wizardState.selectedEntity) return;
  try {
    const res = await fetch(`/activities/api/entities/${wizardState.selectedEntity.id}`, { method: "DELETE" });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    hideModal("confirm-delete-modal");
    window.location.reload();
  } catch (e) { alert("Erreur réseau"); }
}

async function renameEntity() {
  if (!wizardState.selectedEntity) return;
  const name = $("#rename-input")?.value.trim();
  if (!name) { alert("Nom requis"); return; }
  try {
    const res = await fetch(`/activities/api/entities/${wizardState.selectedEntity.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    hideModal("rename-modal");
    wizardState.selectedEntity.name = name;
    $("#selected-entity-name").textContent = name;
    await loadEntitiesList();
  } catch (e) { alert("Erreur réseau"); }
}

/* Navigation wizard */
function goToScreen(id) {
  $$(".wizard-screen").forEach(s => s.classList.remove("active"));
  $(`#wizard-screen-${id}`)?.classList.add("active");
  
  const prog = $("#wizard-progress");
  if (prog) prog.classList.toggle("hidden", !["step1", "step2", "step3"].includes(id));

  const title = $("#wizard-title");
  if (title) {
    if (id === "entities") title.textContent = "📦 Gestion de la cartographie";
    else if (id === "action") title.textContent = "📦 " + (wizardState.selectedEntity?.name || "Entité");
    else title.textContent = "📦 Import cartographie";
  }
}

function goToStep(step) {
  updateProgress(step);
  if (step === 1) { goToScreen("step1"); toggleDropzone("vsdx"); }
  else if (step === 2) { goToScreen("step2"); toggleDropzone("svg"); }
  else if (step === 3) { prepareRecap(); goToScreen("step3"); }
}

function startSteps(mode) {
  wizardState.mode = mode;
  const entity = wizardState.selectedEntity;
  const keepVsdx = $("#keep-vsdx-option");
  const keepSvg = $("#keep-svg-option");

  if (mode === "update" && entity) {
    if (entity.vsdx_exists && keepVsdx) {
      keepVsdx.classList.remove("hidden");
      $("#current-vsdx-name").textContent = entity.current_vsdx || "Fichier actuel";
    } else keepVsdx?.classList.add("hidden");

    if (entity.svg_exists && keepSvg) {
      keepSvg.classList.remove("hidden");
      $("#current-svg-name").textContent = entity.current_svg || "Fichier actuel";
    } else keepSvg?.classList.add("hidden");
  } else {
    keepVsdx?.classList.add("hidden");
    keepSvg?.classList.add("hidden");
  }
  goToStep(1);
}

function updateProgress(step) {
  const prog = $("#wizard-progress");
  if (!prog) return;
  prog.classList.remove("hidden");

  for (let i = 1; i <= 3; i++) {
    const el = $(`.progress-step[data-step="${i}"]`);
    if (!el) continue;
    el.classList.remove("active", "completed");
    if (i < step) el.classList.add("completed");
    else if (i === step) el.classList.add("active");
  }
  for (let i = 1; i <= 2; i++) {
    const line = $(`.progress-line[data-line="${i}"]`);
    if (line) line.classList.toggle("filled", i < step);
  }
}

function toggleDropzone(type) {
  const keep = type === "vsdx" ? wizardState.keepVsdx : wizardState.keepSvg;
  const dz = $(`#${type}-dropzone`);
  if (dz) dz.classList.toggle("disabled", keep);
}

/* Dropzones */
function initDropzone(type) {
  const dz = $(`#${type}-dropzone`);
  const input = $(`#${type}-file-input`);
  const remove = $(`#${type}-remove`);
  if (!dz || !input) return;

  dz.addEventListener("click", () => { if (!dz.classList.contains("disabled")) input.click(); });
  dz.addEventListener("dragover", (e) => { e.preventDefault(); if (!dz.classList.contains("disabled")) dz.classList.add("dragover"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("dragover");
    if (!dz.classList.contains("disabled") && e.dataTransfer.files[0]) handleFile(type, e.dataTransfer.files[0]);
  });
  input.addEventListener("change", () => { if (input.files[0]) handleFile(type, input.files[0]); });
  remove?.addEventListener("click", (e) => { e.stopPropagation(); clearFile(type); });
}

function handleFile(type, file) {
  const ext = type === "vsdx" ? ".vsdx" : ".svg";
  if (!file.name.toLowerCase().endsWith(ext)) { alert(`Format ${ext} requis`); return; }

  if (type === "vsdx") { wizardState.vsdxFile = file; analyzeVsdx(file); }
  else wizardState.svgFile = file;

  $(`#${type}-dropzone`)?.classList.add("hidden");
  $(`#${type}-preview`)?.classList.remove("hidden");
  const fn = $(`#${type}-filename`), fs = $(`#${type}-filesize`);
  if (fn) fn.textContent = file.name;
  if (fs) fs.textContent = formatSize(file.size);
}

function clearFile(type) {
  if (type === "vsdx") { wizardState.vsdxFile = null; wizardState.connectionsPreview = null; }
  else wizardState.svgFile = null;
  $(`#${type}-dropzone`)?.classList.remove("hidden");
  $(`#${type}-preview`)?.classList.add("hidden");
  const input = $(`#${type}-file-input`);
  if (input) input.value = "";
}

async function analyzeVsdx(file) {
  if (!wizardState.selectedEntity) return;
  const form = new FormData();
  form.append("file", file);
  form.append("entity_id", wizardState.selectedEntity.id);
  try {
    const res = await fetch("/activities/preview-connections", { method: "POST", body: form });
    const data = await res.json();
    if (!data.error) wizardState.connectionsPreview = data;
  } catch (e) { console.error(e); }
}

/* Récapitulatif */
function prepareRecap() {
  const entity = wizardState.selectedEntity;
  $("#recap-entity-name").textContent = entity?.name || "-";

  const vCard = $("#recap-vsdx"), vName = $("#recap-vsdx-name"), vStatus = $("#recap-vsdx-status");
  vCard?.classList.remove("new-file", "kept-file");
  if (wizardState.vsdxFile) {
    vName.textContent = wizardState.vsdxFile.name;
    vStatus.textContent = "Nouveau"; vStatus.className = "recap-file-status new";
    vCard?.classList.add("new-file");
  } else if (wizardState.keepVsdx && entity?.vsdx_exists) {
    vName.textContent = entity.current_vsdx || "Fichier actuel";
    vStatus.textContent = "Conservé"; vStatus.className = "recap-file-status kept";
    vCard?.classList.add("kept-file");
  } else {
    vName.textContent = "Aucun"; vStatus.textContent = "-"; vStatus.className = "recap-file-status";
  }

  const sCard = $("#recap-svg"), sName = $("#recap-svg-name"), sStatus = $("#recap-svg-status");
  sCard?.classList.remove("new-file", "kept-file");
  if (wizardState.svgFile) {
    sName.textContent = wizardState.svgFile.name;
    sStatus.textContent = "Nouveau"; sStatus.className = "recap-file-status new";
    sCard?.classList.add("new-file");
  } else if (wizardState.keepSvg && entity?.svg_exists) {
    sName.textContent = entity.current_svg || "Fichier actuel";
    sStatus.textContent = "Conservé"; sStatus.className = "recap-file-status kept";
    sCard?.classList.add("kept-file");
  } else {
    sName.textContent = "Aucun"; sStatus.textContent = "-"; sStatus.className = "recap-file-status";
  }

  const connSection = $("#connections-preview-section"), noVsdx = $("#no-vsdx-message");
  const connTitle = connSection?.querySelector("h4");
  
  if (wizardState.vsdxFile && wizardState.connectionsPreview) {
    connSection?.classList.remove("hidden");
    noVsdx?.classList.add("hidden");
    if (connTitle) connTitle.textContent = wizardState.mode === "new" ? "Connexions à importer" : "Aperçu des connexions";
    displayConnections(wizardState.connectionsPreview);
  } else {
    connSection?.classList.add("hidden");
    noVsdx?.classList.remove("hidden");
    const p = noVsdx?.querySelector("p");
    if (p) p.textContent = wizardState.keepVsdx ? "VSDX conservé — connexions inchangées." : "Pas de VSDX — connexions conservées.";
  }
}

function displayConnections(data) {
  const stats = $("#wizard-connections-stats");
  const isNewMode = wizardState.mode === "new";
  const newModeInfo = $("#new-mode-info");
  const missingCount = data.missing_activities?.length || 0;
  const invalidCount = data.invalid_connections || 0;
  
  if (newModeInfo) newModeInfo.classList.toggle("hidden", !isNewMode);
  
  if (stats) {
    if (isNewMode) {
      stats.innerHTML = `
        <div class="stat-box"><div class="stat-value">${data.total_connections || 0}</div><div class="stat-label">Connexions</div></div>
        <div class="stat-box"><div class="stat-value">${data.valid_connections || 0}</div><div class="stat-label">Compatibles</div></div>
        <div class="stat-box ${missingCount > 0 ? 'warning' : ''}"><div class="stat-value">${missingCount}</div><div class="stat-label">Non compatibles</div></div>
      `;
    } else {
      stats.innerHTML = `
        <div class="stat-box"><div class="stat-value">${data.total_connections || 0}</div><div class="stat-label">Total</div></div>
        <div class="stat-box"><div class="stat-value">${data.valid_connections || 0}</div><div class="stat-label">Valides</div></div>
        <div class="stat-box ${invalidCount > 0 ? 'warning' : ''}"><div class="stat-value">${invalidCount}</div><div class="stat-label">Invalides</div></div>
      `;
    }
  }

  const warn = $("#wizard-missing-warning"), list = $("#wizard-missing-list");
  const warnTitle = warn?.querySelector("strong");
  
  if (missingCount > 0) {
    warn?.classList.remove("hidden");
    if (warnTitle) warnTitle.textContent = isNewMode ? "⚠️ Activités non compatibles (absentes du SVG) :" : "⚠️ Activités non trouvées :";
    if (list) list.innerHTML = data.missing_activities.map(n => `<li>${n}</li>`).join("");
  } else {
    warn?.classList.add("hidden");
  }

  const tbody = $("#wizard-connections-tbody");
  if (tbody && data.connections) {
    tbody.innerHTML = data.connections.slice(0, 50).map(c => {
      const tc = c.data_type === "déclenchante" ? "declenchante" : "nourrissante";
      const statusClass = c.valid ? 'status-valid' : 'status-invalid';
      const statusIcon = c.valid ? '✓' : '✗';
      
      return `<tr class="${c.valid ? '' : 'row-invalid'}">
        <td>${c.source || "-"}</td><td>→</td><td>${c.target || "-"}</td>
        <td>${c.data_name || "-"}</td>
        <td>${c.data_type ? `<span class="data-type ${tc}">${c.data_type}</span>` : "-"}</td>
        <td class="${statusClass}">${statusIcon}</td>
      </tr>`;
    }).join("");
  }
}

/* Soumission */
async function submitWizard() {
  const entity = wizardState.selectedEntity;
  if (!entity) { alert("Aucune entité"); return; }

  const hasSvg = wizardState.svgFile || (wizardState.keepSvg && entity.svg_exists);
  if (!hasSvg && wizardState.mode === "new") { alert("SVG requis"); return; }

  goToScreen("processing");
  setStep("svg", "active");

  const form = new FormData();
  form.append("entity_id", entity.id);
  form.append("mode", wizardState.mode);
  if (wizardState.svgFile) form.append("svg_file", wizardState.svgFile);
  form.append("keep_svg", wizardState.keepSvg);
  if (wizardState.vsdxFile) form.append("vsdx_file", wizardState.vsdxFile);
  form.append("keep_vsdx", wizardState.keepVsdx);
  form.append("clear_connections", $("#clear-connections-checkbox")?.checked || false);

  try {
    const res = await fetch("/activities/upload-cartography", { method: "POST", body: form });
    setStep("svg", "done"); setStep("vsdx", "active");
    const data = await res.json();
    setStep("vsdx", "done"); setStep("save", "active");

    if (data.error) { showError(data.error); return; }

    // Auto-activer l'entité uploadée pour qu'elle s'affiche correctement après reload
    await fetch(`/activities/api/entities/${entity.id}/activate`, { method: "POST" });

    await new Promise(r => setTimeout(r, 200));
    setStep("save", "done");

    showSuccess(data);
  } catch (e) { showError("Erreur réseau"); }
}

function setStep(id, status) {
  const el = $(`#proc-step-${id}`);
  if (!el) return;
  el.classList.remove("active", "done");
  el.classList.add(status);
  const icon = el.querySelector(".proc-icon");
  if (icon) icon.textContent = status === "done" ? "✓" : status === "active" ? "⏳" : "○";
}

function showSuccess(data) {
  goToScreen("success");
  const stats = $("#success-stats");
  if (stats && data.stats) {
    stats.innerHTML = `
      <div class="stat-item"><span class="stat-value">${data.stats.activities || 0}</span><span class="stat-label">Activités</span></div>
      <div class="stat-item"><span class="stat-value">${data.stats.connections || 0}</span><span class="stat-label">Connexions</span></div>
    `;
  }
}

function showError(msg) {
  goToScreen("error");
  const el = $("#error-message");
  if (el) el.textContent = msg;
}

/* ============================================================
   INIT
============================================================ */
document.addEventListener("DOMContentLoaded", async () => {
  // Cacher tous les modals immédiatement
  hideAllModals();
  
  // Initialiser
  initListClicks();
  initWizard();
  initPan();
  await loadSvgInline();
});