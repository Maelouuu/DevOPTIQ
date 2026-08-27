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

/* État mode connexions inter-cartos */
let crossCartoMode = false;
let crossCartoMatches = [];
let activityMatchMap = {}; // activity_id → { name, matched_entities }
let _reverseOriginMap = {}; // populated by initCrossCartoMode, module-level for access in initListClicks

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

function fitViewer() {
  const frame = document.getElementById('carto-viewer-frame');
  if (frame && frame.contentWindow) {
    frame.contentWindow.postMessage({ type: 'fit-view' }, '*');
  }
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
      if (crossCartoMode) return;
      if (typeof isExtcoMapHighlightActive === 'function' && isExtcoMapHighlightActive()) return;
      el.style.filter = "drop-shadow(0 0 6px #22c55e)";
      el.style.opacity = "0.9";
    });
    el.addEventListener("mouseleave", () => {
      if (crossCartoMode) return;
      if (typeof isExtcoMapHighlightActive === 'function' && isExtcoMapHighlightActive()) return;
      el.style.filter = "";
      el.style.opacity = "1";
    });
    el.addEventListener("click", (e) => {
      if (!hasMoved) {
        e.stopPropagation();
        if (crossCartoMode) {
          const raw = el.dataset.crossEntities;
          if (raw) {
            const entities = JSON.parse(raw);
            const name = el.dataset.crossActivity || "Activité";
            handleCrossCartoClick(name, entities);
          }
        } else {
          window.location.href = `/activities/view?activity_id=${actId}`;
        }
      }
    });
  });
}

function initListClicks() {
  $$(".activity-item").forEach((li) => {
    li.addEventListener("click", () => {
      const id = li.dataset.id;
      if (!id) return;
      if (crossCartoMode && activityMatchMap[id]) {
        const m = activityMatchMap[id];
        handleCrossCartoClick(m.name, m.matched_entities);
      } else if (crossCartoMode && li.classList.contains("connexion-origin")) {
        const name = (li.dataset.name || '').trim();
        const liaisons = _reverseOriginMap[name.toLowerCase()];
        if (liaisons) _handleOriginClick(name, liaisons);
      } else if (!crossCartoMode) {
        const frame = document.getElementById('carto-viewer-frame');
        if (frame && frame.contentWindow) {
          const name = (li.dataset.name || '').trim();
          frame.contentWindow.postMessage({ type: 'zoom-to-activity', activityName: name }, '*');
        }
      }
    });
  });
}

/* ============================================================
   RECHERCHE DANS LA LISTE DES ACTIVITÉS (panneau droit)
============================================================ */
function initActivitySearch() {
  const input = document.getElementById("carto-activity-search");
  if (!input) return;
  const items = Array.from(document.querySelectorAll("#activities-list .activity-item"));
  const noRes = document.getElementById("carto-activity-noresult");
  const countEl = document.querySelector(".activities-panel-count");
  const total = items.length;
  const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const plural = (n) => "activité" + (n > 1 ? "s" : "");
  input.addEventListener("input", () => {
    const q = norm(input.value.trim());
    let shown = 0;
    items.forEach((li) => {
      const match = !q || norm(li.dataset.name).includes(q);
      li.style.display = match ? "" : "none";
      if (match) shown++;
    });
    if (noRes) noRes.style.display = shown === 0 ? "" : "none";
    if (countEl) countEl.textContent = q
      ? `${shown} / ${total} ${plural(total)}`
      : `${total} ${plural(total)}`;
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
  wireCartoImport();
  $("#wizard-new-entity-name")?.addEventListener("keypress", (e) => { if (e.key === "Enter") createEntity(); });

  // Navigation
  $("#action-back")?.addEventListener("click", () => goToScreen("entities"));

  // Actions entité
  $("#wizard-activate-btn")?.addEventListener("click", activateEntity);
  wireEntityShare();

  $("#wizard-open-editor-btn")?.addEventListener("click", async () => {
    if (!wizardState.selectedEntity) { window.location.href = "/cartography/editor"; return; }
    const entity = wizardState.selectedEntity;
    if (!entity.is_active) {
      try {
        await fetch(`/activities/api/entities/${entity.id}/activate`, { method: "POST" });
      } catch (_) {}
    }
    window.location.href = "/cartography/editor";
  });

  $("#wizard-rename-btn")?.addEventListener("click", () => showModal("rename-modal"));
  $("#wizard-delete-btn")?.addEventListener("click", () => {
    const nameEl = document.getElementById("delete-entity-name-display");
    if (nameEl && wizardState.selectedEntity) nameEl.textContent = wizardState.selectedEntity.name;
    showModal("confirm-delete-modal");
  });

  // Modals
  $("#cancel-delete-btn")?.addEventListener("click", () => hideModal("confirm-delete-modal"));
  $("#confirm-delete-btn")?.addEventListener("click", deleteEntity);
  $("#cancel-rename-btn")?.addEventListener("click", () => hideModal("rename-modal"));
  $("#confirm-rename-btn")?.addEventListener("click", renameEntity);

  initModalOverlays();
}

function resetWizard() {
  Object.assign(wizardState, { selectedEntity: null, mode: null, vsdxFile: null, svgFile: null, keepVsdx: false, keepSvg: false, connectionsPreview: null });
  goToScreen("entities");
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
        <div class="entity-grid-icon"><i class="fa-solid fa-building"></i></div>
        <div class="entity-grid-info">
          <span class="entity-grid-name">${e.name}</span>
          <span class="entity-grid-stats">${e.activities_count || 0} activités</span>
        </div>
        ${e.is_active ? '<span class="entity-grid-badge">Active</span>' : ''}
        ${e.optiqcarto_exists ? '<span class="entity-grid-carto"><i class="fa-solid fa-diagram-project"></i></span>' : ''}
      </div>
    `).join("");

    list.querySelectorAll(".entity-grid-item").forEach(item => {
      item.addEventListener("click", () => selectEntity(parseInt(item.dataset.id)));
    });
  } catch (e) {
    list.innerHTML = '<p class="error">Erreur de chargement</p>';
  }
}

// Import d'un paquet .optiqcarto : recrée l'entité et sa cartographie sans
// repasser par le .vsdx, qui ré-introduirait les défauts déjà corrigés à la main.
function wireCartoImport() {
  const btn = $("#wizard-import-carto-btn");
  const input = $("#wizard-import-carto-file");
  if (!btn || !input) return;
  btn.addEventListener("click", () => { input.value = ""; input.click(); });
  input.addEventListener("change", () => {
    if (input.files && input.files[0]) importCartoPackage(input.files[0]);
  });
}

async function importCartoPackage(file) {
  const btn = $("#wizard-import-carto-btn");
  const label = btn ? btn.innerHTML : null;
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
  try {
    const fd = new FormData();
    fd.append("file", file);
    // Le nom saisi à côté, s'il y en a un, prime sur celui du paquet.
    const wanted = $("#wizard-new-entity-name")?.value.trim();
    if (wanted) fd.append("name", wanted);

    const res = await fetch("/cartography/api/import", { method: "POST", body: fd });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    if (data.sync_warning) {
      alert("Cartographie importée, mais l'extraction des activités a échoué :\n" + data.sync_warning);
    }
    window.location.href = data.redirect_url || "/cartography/editor";
  } catch (e) {
    alert("Erreur réseau pendant l'import de la cartographie");
  } finally {
    if (btn) { btn.disabled = false; if (label !== null) btn.innerHTML = label; }
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
    if (data.redirect_url) { window.location.href = data.redirect_url; return; }
    input.value = "";
    await loadEntitiesList();
    setTimeout(() => selectEntity(data.entity.id), 50);
  } catch (e) { alert("Erreur réseau"); }
}

/* ══════════════════════════════════════════════════
   PARTAGE D'UNE ENTITÉ
   ══════════════════════════════════════════════════
   Partager = déposer une COPIE de l'entité chez chaque destinataire : une
   entité n'appartient qu'à son propriétaire, il n'existe pas d'accès partagé.
   Chacun repart avec la sienne et la modifie sans toucher à l'originale.
   Ouvert à tous : seul le CONSENTEMENT change (dépôt direct pour un admin,
   proposition à accepter sinon). */

function wireEntityShare() {
  $("#wizard-share-btn")?.addEventListener("click", openShareModal);
  $("#share-cancel-btn")?.addEventListener("click", () => hideModal("share-entity-modal"));
  $("#share-confirm-btn")?.addEventListener("click", confirmShare);
}

const SHARE_L = () => window.SHARE_I18N || {};

// Dépôt d'autorité : l'admin vise soit une entité neuve, soit une entité
// existante du destinataire (qui sera écrasée par la carto envoyée).
function cibleSelect(u, L) {
  if (!u.entities || !u.entities.length) return "";
  const options = [`<option value="">${L.targetNew || "Créer une nouvelle entité"}</option>`]
    .concat(u.entities.map(e =>
      `<option value="${e.id}">${(L.targetReplace || 'Remplacer « %s »').replace("%s", e.name)}</option>`));
  return `<select class="share-target" data-user="${u.id}">${options.join("")}</select>`;
}

// Les cibles n'ont de sens qu'en dépôt d'autorité.
function majCibles() {
  const direct = shareDirect && shareMode() === "direct";
  document.querySelectorAll(".share-target").forEach(sel => {
    sel.style.display = direct ? "" : "none";
    if (!direct) sel.value = "";
  });
  const ligne = $("#share-name-row");
  if (ligne) ligne.style.display = direct ? "flex" : "none";
}

// « direct » = dépôt d'autorité (admin), « offer » = proposition à accepter.
const shareMode = () =>
  document.querySelector('#share-mode input[name="share-mode"]:checked')?.value || "direct";

// Un administrateur dépose sa copie directement ; tout autre compte envoie une
// proposition, et l'entité n'est créée qu'après acceptation du destinataire.
let shareDirect = true;

async function openShareModal() {
  const entity = wizardState.selectedEntity;
  if (!entity) return;
  const L = SHARE_L();
  const list = $("#share-user-list");
  const desc = $("#share-modal-desc");
  if (!list) return;

  const confirmBtn = $("#share-confirm-btn");
  if (confirmBtn) confirmBtn.style.display = "";
  const cancelBtn = $("#share-cancel-btn");
  if (cancelBtn) cancelBtn.textContent = L.cancel || "Annuler";
  list.innerHTML = '<p class="share-loading"><i class="fa-solid fa-spinner fa-spin"></i></p>';
  showModal("share-entity-modal");

  try {
    const res = await fetch(`/activities/api/entities/${entity.id}/share/candidates`);
    const data = await res.json();
    if (data.error) { list.innerHTML = `<p class="share-error">${data.error}</p>`; return; }

    shareDirect = data.direct !== false;
    // Un admin choisit son régime ; les autres n'ont pas le choix, on masque.
    const choix = $("#share-mode");
    if (choix) {
      choix.style.display = shareDirect ? "" : "none";
      const radio = choix.querySelector('input[value="direct"]');
      if (radio) radio.checked = true;
    }
    const majBouton = () => {
      if (!confirmBtn) return;
      const direct = shareDirect && shareMode() === "direct";
      confirmBtn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> `
        + (direct ? (L.confirm || "Déposer la copie") : (L.send || "Envoyer la proposition"));
      if (desc) {
        desc.innerHTML = `${data.entity.name}`
          + `<span class="share-mode-hint">${direct ? (L.directHint || "") : (L.offerHint || "")}</span>`;
      }
    };
    const champNom = $("#share-name");
    if (champNom) champNom.value = data.entity.name || "";
    document.querySelectorAll('#share-mode input[name="share-mode"]')
      .forEach(r => r.addEventListener("change", () => { majBouton(); majCibles(); }));
    majBouton();
    if (!data.users.length) {
      list.innerHTML = `<p class="share-empty">${L.noAccount || "Aucun autre compte sur cette instance."}</p>`;
      return;
    }
    list.innerHTML = data.users.map(u => `
      <label class="share-user-row">
        <input type="checkbox" class="share-user-cb" value="${u.id}">
        <span class="share-user-name">${u.name}</span>
        <span class="share-user-mail">${u.email}</span>
        ${u.pending ? `<span class="share-user-flag">${L.pendingFlag || "proposition en attente"}</span>`
                    : (u.already_has ? `<span class="share-user-flag">${L.hasCopy || "déjà une copie"}</span>` : '')}
        ${cibleSelect(u, L)}
      </label>`).join("");
    majCibles();
  } catch (e) {
    list.innerHTML = `<p class="share-error">${L.loadError || "Erreur de chargement des comptes."}</p>`;
  }
}

// { id du compte : id de l'entité à écraser } — vide = tout en création.
function ciblesChoisies() {
  const cibles = {};
  document.querySelectorAll(".share-user-row").forEach(ligne => {
    const cb = ligne.querySelector(".share-user-cb");
    const sel = ligne.querySelector(".share-target");
    if (cb?.checked && sel?.value) cibles[cb.value] = sel.value;
  });
  return cibles;
}

async function confirmShare() {
  const L = SHARE_L();
  const entity = wizardState.selectedEntity;
  const ids = [...document.querySelectorAll(".share-user-cb:checked")].map(cb => parseInt(cb.value));
  if (!entity || !ids.length) { alert(L.pickOne || "Sélectionnez au moins un compte."); return; }

  const btn = $("#share-confirm-btn");
  const label = btn ? btn.innerHTML : null;
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
  try {
    const res = await fetch(`/activities/api/entities/${entity.id}/share`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_ids: ids,
        mode: shareMode(),
        name: ($("#share-name")?.value || "").trim() || undefined,
        replace: ciblesChoisies(),
      }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }

    const deposees = data.shared || [];
    const proposees = data.pending || [];
    const alertes = deposees.filter(s => s.sync_warning);
    const list = $("#share-user-list");
    if (list) {
      const lignes = deposees.map(s => `
        <div class="share-done-row">
          <i class="fa-solid fa-circle-check"></i>
          <span class="share-user-name">${s.user}</span>
          <span class="share-done-entity">${s.entity_name}${
            s.replaced ? ` (${L.replaced || "remplacée"})` : ""}</span>
        </div>`).concat(proposees.map(s => `
        <div class="share-done-row share-done-pending">
          <i class="fa-solid fa-paper-plane"></i>
          <span class="share-user-name">${s.user}</span>
          <span class="share-done-entity">${L.sent || "Proposition envoyée"}</span>
        </div>`)).join("");
      const pied = proposees.length
        ? `<p class="share-ok">${L.donePending || ""}</p>`
        : (alertes.length
            ? `<p class="share-warn">${(L.doneWarn || "%s").replace("%s", alertes.length)}</p>`
            : `<p class="share-ok">${L.doneOk || ""}</p>`);
      list.innerHTML = lignes + pied;
    }
    const desc = $("#share-modal-desc");
    if (desc) desc.textContent = entity.name;
    const confirm = $("#share-confirm-btn");
    if (confirm) confirm.style.display = "none";
    const cancel = $("#share-cancel-btn");
    if (cancel) cancel.textContent = L.close || "Fermer";
    return;
  } catch (e) {
    alert(L.netError || "Erreur réseau pendant le partage.");
  } finally {
    if (btn) { btn.disabled = false; if (label !== null) btn.innerHTML = label; }
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
    if (data.redirect_url) { window.location.href = data.redirect_url; return; }
    input.value = "";
    await loadEntitiesList();
    setTimeout(() => selectEntity(data.entity.id), 50);
  } catch (e) { alert("Erreur réseau"); }
}

/* ══════════════════════════════════════════════════
   PARTAGE D'UNE ENTITÉ (administrateurs)
   ══════════════════════════════════════════════════
   Partager = déposer une COPIE de l'entité chez chaque destinataire : une
   entité n'appartient qu'à son propriétaire, il n'existe pas d'accès partagé.
   Chacun repart avec la sienne et la modifie sans toucher à l'originale. */

async function selectEntity(id) {
  const entity = wizardState.entitiesCache.find(e => e.id === id);
  if (!entity) return;

  wizardState.selectedEntity = entity;

  $("#selected-entity-name").textContent = entity.name;
  $("#selected-entity-activities").textContent = entity.activities_count || 0;

  const badge = $("#selected-entity-active-badge");
  if (badge) badge.classList.toggle("hidden", !entity.is_active);

  const cartoBadge = $("#em-carto-badge");
  if (cartoBadge) cartoBadge.classList.toggle("hidden", !entity.optiqcarto_exists);

  const actBtn = $("#wizard-activate-btn");
  if (actBtn) actBtn.style.display = entity.is_active ? "none" : "";

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
  const btn = document.getElementById("confirm-delete-btn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Suppression…';
  }
  try {
    const res  = await fetch(`/activities/api/entities/${wizardState.selectedEntity.id}`, { method: "DELETE" });
    const data = await res.json();
    if (data.error) {
      alert(data.error);
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-trash"></i> Supprimer'; }
      return;
    }
    hideModal("confirm-delete-modal");
    window.location.reload();
  } catch (e) {
    alert("Erreur réseau");
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-trash"></i> Supprimer'; }
  }
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
/* ============================================================
   MODE CONNEXIONS INTER-CARTOS
============================================================ */

function _sendToFrame(msg) {
  const frame = document.getElementById("carto-viewer-frame");
  if (frame && frame.contentWindow) {
    try { frame.contentWindow.postMessage(msg, "*"); } catch (_) {}
  }
}

function initCrossCartoMode() {
  const btn     = document.getElementById("cross-carto-btn");
  const countEl = document.getElementById("cross-carto-count");
  if (!btn) return;

  // Nombre d'activités externes côté serveur (badge)
  const extcoCount = (window.EXTCO_ACTIVITY_IDS || []).length;
  if (countEl) countEl.textContent = String(extcoCount);

  let _active = false;
  let _matchedShapeIds = []; // shape_ids avec liaisons (pour re-sync si iframe rechargée)
  let _originShapeIds  = []; // shape_ids des activités d'origine (pour re-sync)

  function _setActive(val) {
    _active = val;
    crossCartoMode = val;
    btn.classList.toggle("active", _active);
    document.body.classList.toggle("connexion-mode-active", _active);
    const infoDefault = document.getElementById("carto-info-default");
    const infoCross   = document.getElementById("carto-info-cross");
    if (infoDefault) infoDefault.classList.toggle("hidden", _active);
    if (infoCross)   infoCross.classList.toggle("hidden", !_active);
    if (_active) {
      _applyConnectionsToList();
    } else {
      _clearConnectionsFromList();
    }
  }

  async function _applyConnectionsToList() {
    const _popup = document.getElementById("cx-search-popup");
    if (_popup) _popup.style.display = "flex";
    try {
      const res = await fetch("/activities/api/cross_carto_matches");
      const data = await res.json();
      crossCartoMatches = data.matches || [];
    } catch (_) {
      crossCartoMatches = [];
    } finally {
      if (_popup) _popup.style.display = "none";
    }
    // Seules les activités hachurées (EXTCO_ACTIVITY_IDS) avec une liaison sont colorées
    const extcoSet = new Set((window.EXTCO_ACTIVITY_IDS || []).map(String));
    activityMatchMap = {};
    _matchedShapeIds = [];
    crossCartoMatches.forEach(m => {
      if (m.activity_id && extcoSet.has(String(m.activity_id))) {
        activityMatchMap[String(m.activity_id)] = { name: m.activity_name, matched_entities: m.matched_entities };
        if (m.shape_id) _matchedShapeIds.push(String(m.shape_id));
      }
    });
    // Charger les liaisons inverses (activités de la carto courante référencées comme extco ailleurs)
    _reverseOriginMap = {};
    try {
      const revRes = await fetch("/activities/api/reverse_liaisons_map");
      const revData = await revRes.json();
      for (const entry of (revData.origins || [])) {
        const key = (entry.origin_activity_name || '').trim().toLowerCase();
        if (key) _reverseOriginMap[key] = entry.liaisons || [];
      }
    } catch (_) {}

    // Build origin shape IDs from activity IDs (invert CARTO_SHAPE_MAP)
    const _activityShapeMap = {}; // activity_id → shape_id
    for (const [shapeId, actId] of Object.entries(window.CARTO_SHAPE_MAP || {})) {
      _activityShapeMap[String(actId)] = String(shapeId);
    }
    _originShapeIds = [];
    $$(".activity-item").forEach(li => {
      const id   = li.dataset.id;
      const name = (li.dataset.name || '').trim().toLowerCase();
      if (name && _reverseOriginMap[name] && id) {
        const sid = _activityShapeMap[String(id)];
        if (sid) _originShapeIds.push(sid);
      }
    });

    // Envoyer au viewer : extco = bleu, origines = vert, reste = gris
    _sendToFrame({ type: "connexion-highlight", matchedShapeIds: _matchedShapeIds, originShapeIds: _originShapeIds });
    // Badge
    const countEl = document.getElementById("cross-carto-count");
    if (countEl) countEl.textContent = String(Object.keys(activityMatchMap).length);
    // Highlight liste droite — extco en bleu, origins en vert
    $$(".activity-item").forEach(li => {
      const id   = li.dataset.id;
      const name = (li.dataset.name || '').trim().toLowerCase();
      const isExtco  = id && activityMatchMap[id];
      const isOrigin = name && _reverseOriginMap[name];
      li.classList.toggle("connexion-match",  !!isExtco);
      li.classList.toggle("connexion-origin", !!isOrigin && !isExtco);
      if (isExtco && !li.querySelector(".connexion-chain-icon")) {
        const icon = document.createElement("i");
        icon.className = "fa-solid fa-link connexion-chain-icon";
        li.appendChild(icon);
      }
      if (isOrigin && !isExtco && !li.querySelector(".connexion-origin-icon")) {
        const icon = document.createElement("i");
        icon.className = "fa-solid fa-arrow-up-right-from-square connexion-origin-icon";
        li.appendChild(icon);
      }
      if (!isOrigin || isExtco) {
        li.querySelector(".connexion-origin-icon")?.remove();
      }
    });
  }

  function _clearConnectionsFromList() {
    activityMatchMap = {};
    crossCartoMatches = [];
    _matchedShapeIds = [];
    _originShapeIds  = [];
    _reverseOriginMap = {};
    _sendToFrame({ type: "connexion-reset" });
    $$(".activity-item").forEach(li => {
      li.classList.remove("connexion-match", "connexion-origin");
      li.querySelector(".connexion-chain-icon")?.remove();
      li.querySelector(".connexion-origin-icon")?.remove();
    });
    const countEl = document.getElementById("cross-carto-count");
    if (countEl) countEl.textContent = "0";
  }

  // Messages entrants depuis le viewer iframe
  window.addEventListener("message", function(e) {
    if (!e.data) return;

    // connexion-shape-click : envoyé par le viewer quand connexion mode est actif
    // et que l'utilisateur clique sur une forme hachurée.
    // editor.js ne peut PAS envoyer shape-click dans ce cas (stopImmediatePropagation)
    if (e.data.type === "connexion-shape-click") {
      if (_active) _handleHachuredClick((e.data.activityName || '').trim());
      return;
    }

    // shape-click : envoyé par editor.js en mode normal (connexion inactif)
    // En mode connexion, on l'utilise pour les activités d'ORIGINE (reverse liaison)
    if (e.data.t === "shape-click") {
      if (_active) {
        const name = (e.data.label || '').trim().toLowerCase();
        if (name && _reverseOriginMap[name]) {
          _handleOriginClick(e.data.label.trim(), _reverseOriginMap[name]);
        }
        return;
      }
      const label = (e.data.label || '').toLowerCase().trim();
      if (!label) return;
      const items = document.querySelectorAll('#activities-list .activity-item');
      let found = null;
      for (const item of items) {
        if ((item.dataset.name || '').toLowerCase().trim() === label) { found = item; break; }
      }
      if (!found) {
        for (const item of items) {
          const name = (item.dataset.name || '').toLowerCase().trim();
          if (name.includes(label) || label.includes(name)) { found = item; break; }
        }
      }
      if (found && found.dataset.id) {
        window.location.href = `/activities/view?activity_id=${found.dataset.id}`;
      }
    }

    // Iframe prête (rechargement) → re-synchroniser le mode connexion
    // Ne pas envoyer connexion-highlight ici : state n'est pas encore chargé
    // (le fetch est async), on attend carto-state-ready pour ça.
    if (e.data.type === "viewer-ready" && _active) {
      _sendToFrame({ type: "connexion-mode", active: true });
    }

    // Carto chargée en mémoire → re-appliquer le grisement si connexion mode actif
    if (e.data.type === "carto-state-ready" && _active && (_matchedShapeIds.length > 0 || _originShapeIds.length > 0)) {
      _sendToFrame({ type: "connexion-highlight", matchedShapeIds: _matchedShapeIds, originShapeIds: _originShapeIds });
    }
  });

  async function _handleHachuredClick(activityName) {
    if (!activityName) return;
    try {
      const res = await fetch(`/activities/api/liaison_matches?name=${encodeURIComponent(activityName)}`);
      const data = await res.json();
      handleCrossCartoClick(activityName, data.matches || []);
    } catch (_) {}
  }

  btn.addEventListener("click", () => {
    const newVal = !_active;
    _sendToFrame({ type: "connexion-mode", active: newVal });
    _setActive(newVal);
  });
}


function handleCrossCartoClick(activityName, matches) {
  const popup  = document.getElementById("cross-entity-popup");
  const nameEl = document.getElementById("cross-entity-activity-name");
  const listEl = document.getElementById("cross-entity-list");
  if (!popup || !listEl) return;

  // Blue popup for extco activities
  popup.classList.remove("cross-entity-popup--green");
  popup.classList.add("cross-entity-popup--blue");

  // Retrouver l'ID de l'activité hachurée depuis activityMatchMap (module-level)
  let extcoActivityId = null;
  for (const [aid, info] of Object.entries(activityMatchMap)) {
    if ((info.name || "").trim().toLowerCase() === activityName.trim().toLowerCase()) {
      extcoActivityId = parseInt(aid);
      break;
    }
  }

  if (nameEl) nameEl.textContent = `"${activityName}"`;
  listEl.innerHTML = "";

  if (!matches || matches.length === 0) {
    listEl.innerHTML = '<div class="cross-entity-empty"><i class="fa-solid fa-circle-info"></i> Aucune liaison trouvée dans les autres cartographies.</div>';
    popup.classList.remove("hidden");
    return;
  }

  matches.forEach(m => {
    const item = document.createElement("div");
    item.className = "cross-entity-item";
    const officializeHtml = m.has_active_liaison
      ? `<div class="cross-entity-officialized-row">
           <span class="cross-entity-badge-ok"><i class="fa-solid fa-check"></i> Officialisée</span>
           <button class="cross-entity-btn-deoffice" data-liaison-id="${m.liaison_id}" title="Dé-officialiser">
             <i class="fa-solid fa-link-slash"></i>
           </button>
         </div>`
      : `<button class="cross-entity-btn-officialize" title="Officialiser cette liaison">
           <i class="fa-solid fa-link"></i> Officialiser
         </button>`;
    item.innerHTML = `
      <div class="cross-entity-item-info">
        <i class="fa-solid fa-building"></i>
        <strong>${m.entity_name}</strong>
        <span class="cross-entity-act-name">${m.activity_name}</span>
      </div>
      <div class="cross-entity-item-actions">
        <button class="cross-entity-btn-preview" title="Voir la cartographie">
          <i class="fa-solid fa-eye"></i>
        </button>
        ${officializeHtml}
      </div>`;

    item.querySelector(".cross-entity-btn-preview").addEventListener("click", (e) => {
      e.stopPropagation();
      popup.classList.add("hidden");
      showCartoPreview(m.entity_id, m.entity_name, m.activity_name);
    });

    if (!m.has_active_liaison) {
      item.querySelector(".cross-entity-btn-officialize").addEventListener("click", async (e) => {
        e.stopPropagation();
        const btn = e.currentTarget;
        if (!extcoActivityId) {
          alert("Impossible d'identifier l'activité hachurée.");
          return;
        }
        const label = await _promptLiaisonLabel(m.entity_name);
        if (label === null) return;
        const ok = await officializeLiaison(extcoActivityId, m.entity_id, m.activity_id, m.entity_name, btn, label);
        if (ok) _sendToFrame({ type: 'reload-liaisons' });
      });
    } else {
      item.querySelector(".cross-entity-btn-deoffice")?.addEventListener("click", async (e) => {
        e.stopPropagation();
        popup.classList.add("hidden");
        const ok = await _confirmDeoffice(m.liaison_id, m.entity_name);
        if (ok) {
          _sendToFrame({ type: 'reload-liaisons' });
          // Refresh the popup with the current extco activity
          const nameEl = document.getElementById("cross-entity-activity-name");
          const actName = nameEl ? nameEl.textContent.replace(/^[""]|[""]$/g, '') : '';
          if (actName && extcoActivityId) _handleExtcoClick(actName, extcoActivityId);
        } else {
          popup.classList.remove("hidden");
        }
      });
    }

    listEl.appendChild(item);
  });

  popup.classList.remove("hidden");
}

function _handleOriginClick(activityName, liaisons) {
  const popup  = document.getElementById("cross-entity-popup");
  const nameEl = document.getElementById("cross-entity-activity-name");
  const listEl = document.getElementById("cross-entity-list");
  if (!popup || !listEl) return;

  // Green popup for origin activities
  popup.classList.remove("cross-entity-popup--blue");
  popup.classList.add("cross-entity-popup--green");

  if (nameEl) nameEl.textContent = `"${activityName}"`;
  listEl.innerHTML = "";

  if (!liaisons || liaisons.length === 0) {
    listEl.innerHTML = '<div class="cross-entity-empty"><i class="fa-solid fa-circle-info"></i> Aucune référence trouvée.</div>';
    popup.classList.remove("hidden");
    return;
  }

  liaisons.forEach(m => {
    const item = document.createElement("div");
    item.className = "cross-entity-item";
    item.innerHTML = `
      <div class="cross-entity-item-info">
        <span class="cross-entity-label" style="color:#3b82f6"><i class="fa-solid fa-arrow-up-right-from-square" style="margin-right:4px"></i>${m.entity_name}</span>
        <span class="cross-entity-act-name" style="font-style:italic">${m.activity_name}</span>
      </div>
      <div class="cross-entity-item-actions">
        <button class="cross-entity-btn-preview" title="Voir la cartographie">
          <i class="fa-solid fa-eye"></i>
        </button>
      </div>`;

    item.querySelector(".cross-entity-btn-preview").addEventListener("click", (e) => {
      e.stopPropagation();
      popup.classList.add("hidden");
      // Zoom to the extco shape (the hatched representation of this activity) in the other carto
      showCartoPreview(m.entity_id, m.entity_name, m.activity_name);
    });

    listEl.appendChild(item);
  });

  popup.classList.remove("hidden");
}

function _promptLiaisonLabel(defaultLabel) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = `
      <div style="background:#fff;border-radius:12px;padding:24px;min-width:320px;max-width:420px;box-shadow:0 8px 32px rgba(0,0,0,0.2)">
        <h3 style="margin:0 0 8px;font-size:1rem;font-weight:700;color:#1e293b"><i class="fa-solid fa-tag" style="color:#ec4899;margin-right:6px"></i>Nom affiché sous l'activité</h3>
        <p style="margin:0 0 14px;font-size:0.82rem;color:#64748b">Ce nom apparaîtra sous l'activité hachurée dans la cartographie.</p>
        <input id="_liaison-label-input" type="text" value="${defaultLabel || ''}"
          style="width:100%;box-sizing:border-box;padding:8px 10px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:0.9rem;outline:none"
          maxlength="100">
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
          <button id="_liaison-cancel" style="padding:7px 16px;border:1.5px solid #e2e8f0;border-radius:8px;background:#fff;cursor:pointer;font-size:0.85rem">Annuler</button>
          <button id="_liaison-confirm" style="padding:7px 16px;border:none;border-radius:8px;background:#ec4899;color:#fff;cursor:pointer;font-size:0.85rem;font-weight:600">Confirmer</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const input = overlay.querySelector('#_liaison-label-input');
    input.focus(); input.select();
    overlay.querySelector('#_liaison-confirm').addEventListener('click', () => {
      document.body.removeChild(overlay);
      resolve(input.value.trim() || null);
    });
    overlay.querySelector('#_liaison-cancel').addEventListener('click', () => {
      document.body.removeChild(overlay);
      resolve(null);
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') { overlay.querySelector('#_liaison-confirm').click(); }
      if (e.key === 'Escape') { overlay.querySelector('#_liaison-cancel').click(); }
    });
  });
}

async function officializeLiaison(extcoActivityId, originEntityId, originActivityId, originEntityName, btn, displayLabel) {
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>'; }
  try {
    const res = await fetch("/activities/api/officialize_liaison", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        extco_activity_id: extcoActivityId,
        origin_entity_id:  originEntityId,
        origin_activity_id: originActivityId,
        display_label: displayLabel || null,
      })
    });
    const data = await res.json();
    if (data.error) {
      alert(data.error);
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-link"></i> Officialiser'; }
      return false;
    } else {
      if (btn) {
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Officialisée';
        btn.style.background = "#22c55e";
        btn.classList.add("cross-entity-btn-officialized");
      }
      return true;
    }
  } catch (_) {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-link"></i> Officialiser'; }
    return false;
  }
}

async function _confirmDeoffice(liaisonId, originEntityName) {
  let preview = null;
  try {
    const res = await fetch(`/activities/api/liaison_deoffice_preview?liaison_id=${liaisonId}`);
    preview = await res.json();
  } catch (_) {}

  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center';

    const shapesHtml = preview?.shapes_to_remove?.length
      ? `<ul style="margin:6px 0 0;padding-left:18px;font-size:0.82rem;color:#475569">${
          preview.shapes_to_remove.map(n => `<li>${n}</li>`).join('')
        }</ul>`
      : '';
    const lines = [
      preview?.connections_to_remove ? `${preview.connections_to_remove} connexion(s) associée(s)` : null,
      preview?.db_links_to_remove    ? `${preview.db_links_to_remove} lien(s) DB croisés`          : null,
    ].filter(Boolean);

    overlay.innerHTML = `
      <div style="background:#fff;border-radius:12px;padding:24px;min-width:340px;max-width:460px;box-shadow:0 8px 32px rgba(0,0,0,0.25)">
        <h3 style="margin:0 0 10px;font-size:1rem;font-weight:700;color:#dc2626">
          <i class="fa-solid fa-triangle-exclamation" style="margin-right:6px"></i>Dé-officialiser la liaison
        </h3>
        <p style="margin:0 0 6px;font-size:0.85rem;color:#374151">
          Cette action supprimera dans la cartographie <strong>${preview?.origin_entity_name || originEntityName || '?'}</strong> :
        </p>
        ${shapesHtml}
        ${lines.map(l => `<p style="margin:3px 0 0;font-size:0.82rem;color:#475569">+ ${l}</p>`).join('')}
        <p style="margin:12px 0 0;font-size:0.8rem;color:#94a3b8;font-style:italic">Cette action est irréversible.</p>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
          <button id="_deoffice-cancel" style="padding:7px 16px;border:1.5px solid #e2e8f0;border-radius:8px;background:#fff;cursor:pointer;font-size:0.85rem">Annuler</button>
          <button id="_deoffice-confirm" style="padding:7px 16px;border:none;border-radius:8px;background:#dc2626;color:#fff;cursor:pointer;font-size:0.85rem;font-weight:600">
            <i class="fa-solid fa-link-slash" style="margin-right:5px"></i>Dé-officialiser
          </button>
        </div>
      </div>`;

    document.body.appendChild(overlay);

    overlay.querySelector('#_deoffice-cancel').onclick = () => { overlay.remove(); resolve(false); };
    overlay.querySelector('#_deoffice-confirm').onclick = async () => {
      const btn = overlay.querySelector('#_deoffice-confirm');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
      try {
        const res = await fetch('/activities/api/liaison_deoffice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ liaison_id: liaisonId }),
        });
        const data = await res.json();
        overlay.remove();
        resolve(data.ok === true);
      } catch (_) { overlay.remove(); resolve(false); }
    };
  });
}

let _previewEntityId = null;
let _previewCleanup  = null;

async function showCartoPreview(entityId, entityName, originActivityName = null) {
  _previewEntityId = entityId;

  const previewPopup = document.getElementById("carto-preview-popup");
  const titleEl      = document.getElementById("carto-preview-title");
  const loadingEl    = document.getElementById("carto-preview-loading");
  const svgWrap      = document.getElementById("carto-preview-svg-wrap");
  if (!previewPopup) return;

  if (titleEl)   titleEl.textContent = entityName;
  if (loadingEl) loadingEl.style.display = "flex";
  if (svgWrap)   svgWrap.innerHTML = "";
  if (_previewCleanup) { _previewCleanup(); _previewCleanup = null; }
  previewPopup.classList.remove("hidden");

  // Utilise le viewer OptiqCarto (iframe) — fonctionne pour toutes les entités
  if (svgWrap) {
    const iframe = document.createElement("iframe");
    iframe.src = `/cartography/viewer?entity_id=${entityId}`;
    iframe.style.cssText = "width:100%;height:100%;border:none;border-radius:0 0 8px 8px;display:block";
    iframe.addEventListener("load", () => {
      if (loadingEl) loadingEl.style.display = "none";
      if (originActivityName) {
        setTimeout(() => {
          try {
            iframe.contentWindow.postMessage({ type: 'zoom-to-activity', activityName: originActivityName }, '*');
          } catch (_) {}
        }, 400);
      }
    });
    svgWrap.appendChild(iframe);
  }
}

function _initPreviewPanZoom(wrap) {
  const svg = wrap.querySelector("svg");
  if (!svg) return null;

  const vb  = svg.viewBox?.baseVal;
  const svgW = (vb?.width > 0 ? vb.width : parseFloat(svg.getAttribute("width"))) || 1000;
  const svgH = (vb?.height > 0 ? vb.height : parseFloat(svg.getAttribute("height"))) || 800;

  svg.style.transformOrigin = "0 0";
  svg.style.display = "block";
  svg.style.width   = svgW + "px";
  svg.style.height  = svgH + "px";

  const rect = wrap.getBoundingClientRect();
  let scale  = Math.min((rect.width - 20) / svgW, (rect.height - 20) / svgH) * 0.92;
  let panX   = (rect.width  - svgW * scale) / 2;
  let panY   = (rect.height - svgH * scale) / 2;

  function applyTransform() {
    svg.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  }
  applyTransform();

  let dragging = false, startX = 0, startY = 0;

  function onMouseDown(e) {
    dragging = true; startX = e.clientX - panX; startY = e.clientY - panY;
    wrap.style.cursor = "grabbing";
    e.preventDefault();
  }
  function onMouseMove(e) {
    if (!dragging) return;
    panX = e.clientX - startX; panY = e.clientY - startY;
    applyTransform();
  }
  function onMouseUp()  { dragging = false; wrap.style.cursor = "grab"; }
  function onWheel(e) {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const newScale = Math.max(0.05, Math.min(scale * factor, 8));
    const rect = wrap.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    panX = mx - (mx - panX) * (newScale / scale);
    panY = my - (my - panY) * (newScale / scale);
    scale = newScale;
    applyTransform();
  }

  wrap.style.cursor = "grab";
  wrap.addEventListener("mousedown", onMouseDown);
  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup",   onMouseUp);
  wrap.addEventListener("wheel", onWheel, { passive: false });

  return function cleanup() {
    wrap.removeEventListener("mousedown", onMouseDown);
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup",   onMouseUp);
    wrap.removeEventListener("wheel", onWheel);
  };
}

function initCartoPreview() {
  const closeBtn    = document.getElementById("carto-preview-close");
  const backdrop    = document.getElementById("carto-preview-backdrop");
  const activateBtn = document.getElementById("carto-preview-activate-btn");
  const popup       = document.getElementById("carto-preview-popup");

  function closePreview() {
    if (popup) popup.classList.add("hidden");
    if (_previewCleanup) { _previewCleanup(); _previewCleanup = null; }
    const svgWrap = document.getElementById("carto-preview-svg-wrap");
    if (svgWrap) svgWrap.innerHTML = "";
  }

  if (closeBtn)  closeBtn.addEventListener("click",  closePreview);
  if (backdrop)  backdrop.addEventListener("click",  closePreview);

  if (activateBtn) {
    activateBtn.addEventListener("click", async () => {
      if (!_previewEntityId) return;
      activateBtn.disabled = true;
      activateBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Activation…';
      try {
        await fetch(`/activities/api/entities/${_previewEntityId}/activate`, { method: "POST" });
        window.location.reload();
      } catch (e) {
        activateBtn.disabled = false;
        activateBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Rendre la carto active';
      }
    });
  }
}

async function navigateToLinkedCarto(entityId, entityName, activityName) {
  try {
    await fetch(`/activities/api/entities/${entityId}/activate`, { method: "POST" });
  } catch (e) {
    console.error("Erreur activation entité:", e);
  }
  window.location.href = `/activities/view?highlight_name=${encodeURIComponent(activityName)}`;
}

/* ============================================================
   SHAPE COMPARISON SECTION (SCS)
============================================================ */

function initShapeComparison() {
  const TYPES_INTERESTED = ['process', 'start-end', 'special'];
  const TYPE_LABELS = { process: 'Act.', 'start-end': 'Cer.', special: 'S-Act.' };

  let cartoItems = [];   // { label, type }
  let vsdxItems  = [];   // { label, type }
  let activeType = 'all';

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const listCarto   = document.getElementById('scs-list-carto');
  const listVsdx    = document.getElementById('scs-list-vsdx');
  const countCarto  = document.getElementById('scs-count-carto');
  const countVsdx   = document.getElementById('scs-count-vsdx');
  const searchCarto = document.getElementById('scs-search-carto');
  const searchVsdx  = document.getElementById('scs-search-vsdx');
  const dropzone    = document.getElementById('scs-dropzone');
  const fileInput   = document.getElementById('scs-file-input');
  const browseBtn   = document.getElementById('scs-browse-btn');
  const statusEl    = document.getElementById('scs-vsdx-status');
  const resetBtn    = document.getElementById('scs-reset-vsdx');
  const entityBadge = document.getElementById('scs-entity-badge');
  const filterBtns  = document.querySelectorAll('#scs-type-filters .scs-filter');

  if (!listCarto) return;  // section absent (no carto)

  const entity = window.ACTIVE_ENTITY;
  if (entityBadge && entity) entityBadge.textContent = entity;

  // ── Render helpers ────────────────────────────────────────────────────────
  function renderList(el, items, searchVal) {
    const q = (searchVal || '').toLowerCase().trim();
    let visible = 0;
    el.innerHTML = '';
    for (const it of items) {
      if (activeType !== 'all' && it.type !== activeType) continue;
      const hidden = q && !it.label.toLowerCase().includes(q);
      const div = document.createElement('div');
      div.className = 'scs-item' + (hidden ? ' hidden' : '');
      div.innerHTML = `<span class="scs-type-badge ${it.type}">${TYPE_LABELS[it.type] || it.type}</span>
        <span class="scs-item-label" title="${it.label.replace(/"/g, '&quot;')}">${it.label}</span>`;
      el.appendChild(div);
      if (!hidden) visible++;
    }
    if (el.children.length === 0) {
      el.innerHTML = '<div class="scs-empty">Aucun élément</div>';
    }
    return visible;
  }

  function updateCount(el, items) {
    const count = activeType === 'all'
      ? items.filter(i => TYPES_INTERESTED.includes(i.type)).length
      : items.filter(i => i.type === activeType).length;
    if (el) el.textContent = count;
  }

  function refresh() {
    const vc = renderList(listCarto, cartoItems, searchCarto ? searchCarto.value : '');
    const vv = renderList(listVsdx,  vsdxItems,  searchVsdx  ? searchVsdx.value  : '');
    updateCount(countCarto, cartoItems);
    updateCount(countVsdx,  vsdxItems);
  }

  // ── Load carto data ───────────────────────────────────────────────────────
  async function loadCartoItems() {
    if (!entity) {
      listCarto.innerHTML = '<div class="scs-empty">Entité inconnue</div>';
      return;
    }
    try {
      const res = await fetch(`/cartography/api/load/${encodeURIComponent(entity)}`);
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      cartoItems = (data.shapes || [])
        .filter(s => TYPES_INTERESTED.includes(s.type))
        .map(s => ({ label: (s.label || '').trim(), type: s.type }))
        .sort((a, b) => a.label.localeCompare(b.label, 'fr'));
      refresh();
    } catch (e) {
      listCarto.innerHTML = '<div class="scs-empty">Erreur de chargement</div>';
      console.error('SCS carto load error:', e);
    }
  }

  // ── VSDX parsing ──────────────────────────────────────────────────────────
  async function parseVsdx(file) {
    if (typeof vsdxParse !== 'function') {
      statusEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Parser VSDX non disponible';
      return;
    }
    dropzone.classList.add('hidden');
    statusEl.classList.remove('hidden');
    statusEl.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analyse du VSDX…';

    try {
      const result = await vsdxParse(file, () => {}, () => {});
      vsdxItems = (result.shapes || [])
        .filter(s => TYPES_INTERESTED.includes(s.type))
        .map(s => ({ label: (s.label || '').trim(), type: s.type }))
        .sort((a, b) => a.label.localeCompare(b.label, 'fr'));

      statusEl.classList.add('hidden');
      listVsdx.classList.remove('hidden');
      if (searchVsdx) searchVsdx.classList.remove('hidden');
      resetBtn.classList.remove('hidden');
      refresh();
    } catch (e) {
      console.error('SCS vsdx parse error:', e);
      statusEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Erreur lors de l\'analyse';
    }
  }

  function resetVsdx() {
    vsdxItems = [];
    listVsdx.classList.add('hidden');
    if (searchVsdx) { searchVsdx.classList.add('hidden'); searchVsdx.value = ''; }
    resetBtn.classList.add('hidden');
    dropzone.classList.remove('hidden');
    if (countVsdx) countVsdx.textContent = '—';
    if (fileInput) fileInput.value = '';
  }

  // ── Filter buttons ────────────────────────────────────────────────────────
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeType = btn.dataset.type || 'all';
      refresh();
    });
  });

  // ── Search ────────────────────────────────────────────────────────────────
  if (searchCarto) searchCarto.addEventListener('input', refresh);
  if (searchVsdx)  searchVsdx.addEventListener('input', refresh);

  // ── File input / drop ─────────────────────────────────────────────────────
  if (browseBtn) browseBtn.addEventListener('click', () => fileInput && fileInput.click());
  if (fileInput) fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) parseVsdx(fileInput.files[0]);
  });
  if (dropzone) {
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      const f = e.dataTransfer.files[0];
      if (f && f.name.toLowerCase().endsWith('.vsdx')) parseVsdx(f);
    });
  }
  if (resetBtn) resetBtn.addEventListener('click', resetVsdx);

  // ── Bootstrap ─────────────────────────────────────────────────────────────
  loadCartoItems();
}

/* ============================================================
   VCM MODAL (Correspondance VSDX)
============================================================ */

function initVsdxCompareModal() {
  const overlay    = document.getElementById('vsdx-compare-modal');
  const closeBtn   = document.getElementById('vcm-close');
  const browseBtn  = document.getElementById('vcm-browse-btn');
  const fileInput  = document.getElementById('vcm-file-input');
  const fpRemove   = document.getElementById('vcm-fp-remove');
  const fpName     = document.getElementById('vcm-fp-name');
  const fpPreview  = document.getElementById('vcm-file-preview');
  const dropzone   = document.getElementById('vcm-dropzone');
  const compareBtn = document.getElementById('vcm-btn-compare');
  const bodyUpload = document.getElementById('vcm-body-upload');
  const bodyResult = document.getElementById('vcm-body-results');
  const bodyLoad   = document.getElementById('vcm-body-loading');
  const parseErrs  = document.getElementById('vcm-parse-errors');
  const parseErrsT = document.getElementById('vcm-parse-errors-text');
  const resetBtn   = document.getElementById('vcm-btn-reset');
  const ringCircle = document.getElementById('vcm-ring-circle');
  const ringPct    = document.getElementById('vcm-ring-pct');
  const pctAct     = document.getElementById('vcm-pct-act');
  const pctConn    = document.getElementById('vcm-pct-conn');
  const vcmCounts  = document.getElementById('vcm-counts');
  const diffSect   = document.getElementById('vcm-diff-section');

  if (!overlay) return;

  let selectedFile = null;

  function openModal() { overlay.classList.remove('hidden'); }
  function closeModal() { overlay.classList.add('hidden'); resetUpload(); }

  function setFile(f) {
    selectedFile = f;
    if (fpName) fpName.textContent = f.name;
    if (fpPreview) fpPreview.classList.remove('hidden');
    if (dropzone) dropzone.classList.add('hidden');
    if (compareBtn) compareBtn.disabled = false;
  }

  function resetUpload() {
    selectedFile = null;
    if (fpPreview) fpPreview.classList.add('hidden');
    if (dropzone) dropzone.classList.remove('hidden');
    if (compareBtn) compareBtn.disabled = true;
    if (parseErrs) parseErrs.classList.add('hidden');
    if (fileInput) fileInput.value = '';
    if (bodyResult) bodyResult.classList.add('hidden');
    if (bodyUpload) bodyUpload.classList.remove('hidden');
    if (bodyLoad)   bodyLoad.classList.add('hidden');
  }

  function renderRing(pct) {
    const CIRC = 100.53;  // 2π×16
    const dash = (pct / 100) * CIRC;
    if (ringCircle) {
      ringCircle.style.strokeDasharray = `${dash} ${CIRC}`;
      const hue = Math.round(pct * 1.2);
      ringCircle.style.stroke = `hsl(${hue},78%,48%)`;
    }
    if (ringPct) ringPct.textContent = Math.round(pct) + '%';
  }

  async function runCompare() {
    if (!selectedFile) return;
    if (bodyUpload) bodyUpload.classList.add('hidden');
    if (bodyLoad)   bodyLoad.classList.remove('hidden');
    if (bodyResult) bodyResult.classList.add('hidden');

    try {
      const fd = new FormData();
      fd.append('file', selectedFile);
      const res = await fetch('/cartography/api/vsdx-compare', { method: 'POST', body: fd });
      const data = await res.json();
      if (bodyLoad) bodyLoad.classList.add('hidden');

      if (data.error) {
        if (bodyUpload) bodyUpload.classList.remove('hidden');
        if (parseErrs)  parseErrs.classList.remove('hidden');
        if (parseErrsT) parseErrsT.textContent = data.error;
        return;
      }

      // Ring
      const overallPct = data.overall_score ?? data.activity_score ?? 0;
      renderRing(overallPct);

      // Per-type scores
      if (pctAct  && data.activity_score  != null) pctAct.textContent  = Math.round(data.activity_score) + '%';
      if (pctConn && data.connection_score != null) pctConn.textContent = Math.round(data.connection_score) + '%';

      // Counts
      if (vcmCounts && data.counts) {
        vcmCounts.innerHTML = Object.entries(data.counts)
          .map(([k, v]) => `<span>${k} : <strong>${v}</strong></span>`)
          .join('');
      }

      // Diff section
      if (diffSect && data.diff) {
        diffSect.innerHTML = '';
        for (const [title, items] of Object.entries(data.diff)) {
          if (!items || !items.length) continue;
          const sec = document.createElement('div');
          sec.className = 'vcm-diff-subsection';
          sec.innerHTML = `<div class="vcm-diff-title">${title} <span class="vcm-diff-count">${items.length}</span></div>
            <ul class="vcm-diff-list">${items.map(i => `<li><i class="fa-solid fa-minus"></i>${i}</li>`).join('')}</ul>`;
          diffSect.appendChild(sec);
        }
        if (!diffSect.children.length) {
          diffSect.innerHTML = '<div class="vcm-perfect"><i class="fa-solid fa-check-circle"></i> Correspondance parfaite !</div>';
        }
      }

      if (bodyResult) bodyResult.classList.remove('hidden');

      // Parse warnings
      if (parseErrs && data.errors && data.errors.length) {
        parseErrs.classList.remove('hidden');
        if (parseErrsT) parseErrsT.textContent = data.errors.join(' — ');
      }
    } catch (e) {
      console.error('VCM compare error:', e);
      if (bodyLoad)   bodyLoad.classList.add('hidden');
      if (bodyUpload) bodyUpload.classList.remove('hidden');
    }
  }

  // ── Wiring ────────────────────────────────────────────────────────────────
  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  if (browseBtn) browseBtn.addEventListener('click', () => fileInput && fileInput.click());
  if (fileInput) fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) setFile(fileInput.files[0]);
  });
  if (fpRemove) fpRemove.addEventListener('click', resetUpload);
  if (compareBtn) compareBtn.addEventListener('click', runCompare);
  if (resetBtn) resetBtn.addEventListener('click', () => {
    if (bodyResult) bodyResult.classList.add('hidden');
    if (bodyUpload) bodyUpload.classList.remove('hidden');
  });
  if (dropzone) {
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      const f = e.dataTransfer.files[0];
      if (f && f.name.toLowerCase().endsWith('.vsdx')) setFile(f);
    });
  }

  // Expose opener so other parts of the page can open the modal
  window.openVcmModal = openModal;
}

/* ============================================================
   INIT
============================================================ */
async function initCalqueStrip() {
  const strip = document.getElementById("calque-strip");
  const list  = document.getElementById("calque-strip-list");
  if (!strip || !list) return;

  let calques = [];
  try {
    const r = await fetch("/cartography/api/calques");
    calques = await r.json();
  } catch (_) { return; }

  if (!Array.isArray(calques) || calques.length === 0) return;
  strip.style.display = "flex";

  // Read active calque from session (set by editor or previous calque switch)
  const sessionCalqueId = window.ACTIVE_CALQUE_ID ? String(window.ACTIVE_CALQUE_ID) : null;
  let activeId = sessionCalqueId || "master";

  function setActive(id) {
    activeId = String(id);
    list.querySelectorAll(".calque-chip").forEach(c => c.classList.toggle("active", c.dataset.id === activeId));
  }

  async function _refreshActivitiesList() {
    try {
      const r = await fetch("/activities/map/api/activities");
      const acts = await r.json();
      const ul = document.getElementById("activities-list");
      if (!ul) return;
      ul.innerHTML = acts.map((a, i) =>
        `<li class="activity-item" data-id="${a.id}" data-name="${(a.name || '').toLowerCase()}">
           <span class="num">${i + 1}</span>
           <span class="label">${a.name}</span>
         </li>`
      ).join("");
      const countEl = document.querySelector(".activities-panel-count");
      if (countEl) countEl.textContent = acts.length + " activité" + (acts.length !== 1 ? "s" : "");
      // Re-wire click handlers on new items
      initListClicks();
    } catch (_) {}
  }

  async function applyCalque(id) {
    const frame   = document.getElementById("carto-viewer-frame");
    const overlay = document.getElementById("calque-loading-overlay");
    if (!frame) return;

    // Show loading overlay
    if (overlay) overlay.style.display = 'flex';

    if (id === "master") {
      await fetch("/cartography/api/calques/deactivate", { method: "POST" }).catch(() => {});
    } else {
      await fetch(`/cartography/api/calques/${id}/apply`, { method: "POST" }).catch(() => {});
    }

    // Reload iframe; hide overlay and refresh activities list once loaded
    frame.addEventListener("load", () => {
      if (overlay) overlay.style.display = 'none';
      _refreshActivitiesList();
    }, { once: true });
    frame.src = frame.src;
    setActive(id);
  }

  // Master chip already in DOM — wire it
  const masterChip = document.getElementById("calque-chip-master");
  if (masterChip) masterChip.addEventListener("click", () => applyCalque("master"));

  // Add calque chips
  for (const c of calques) {
    const chip = document.createElement("button");
    chip.className = "calque-chip";
    chip.dataset.id = c.id;
    chip.textContent = c.name;
    chip.addEventListener("click", () => applyCalque(c.id));
    list.appendChild(chip);
  }

  // Set initial active state from session
  setActive(activeId);
}

document.addEventListener("DOMContentLoaded", async () => {
  // Cacher tous les modals immédiatement
  hideAllModals();

  // Initialiser
  initListClicks();
  initActivitySearch();
  initWizard();
  initPan();
  initCrossCartoMode();
  initShapeComparison();
  initVsdxCompareModal();
  initCartoPreview();
  await loadSvgInline();
  initCalqueStrip();

  // Touche Echap pour fermer le popup entité (si ouvert)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const entityPopup = document.getElementById("cross-entity-popup");
      if (entityPopup) entityPopup.classList.add("hidden");
    }
  });
});