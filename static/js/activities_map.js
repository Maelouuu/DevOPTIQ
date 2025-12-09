/* ============================================================
   CARTOGRAPHIE DES ACTIVITÉS - VERSION SVG INLINE + ENTITÉS
   
   Cette version charge le SVG inline dans le DOM, ce qui permet
   un contrôle total sur les événements (pan + clic activités)
============================================================ */

const SHAPE_ACTIVITY_MAP = window.CARTO_SHAPE_MAP || {};
const SVG_EXISTS = window.SVG_EXISTS || false;
const ACTIVE_ENTITY = window.ACTIVE_ENTITY || null;
const ALL_ENTITIES = window.ALL_ENTITIES || [];

const VISIO_NS = "http://schemas.microsoft.com/visio/2003/SVGExtensions/";

/* ============================================================
   ÉTAT GLOBAL PAN / ZOOM
============================================================ */
let svgElement = null;
let currentScale = 0.5;

let panX = 0;
let panY = 0;

// Pour le pan (drag)
let isPanning = false;
let startX = 0;
let startY = 0;
let hasMoved = false;

// Dimensions du SVG
let svgWidth = 0;
let svgHeight = 0;

// Éléments cliquables (activités)
let clickableElements = new Set();

// Limites de zoom
const ZOOM_MIN = 0.1;
const ZOOM_MAX = 10;

// Entité actuellement sélectionnée dans le gestionnaire
let selectedEntityId = null;

/* ============================================================
   CENTRER LA CARTOGRAPHIE AU CHARGEMENT
============================================================ */
function centerCartography() {
  const wrapper = document.getElementById("carto-pan-wrapper");
  const panInner = document.getElementById("pan-inner");
  if (!wrapper || !panInner || !svgWidth || !svgHeight) return;

  const wrapperRect = wrapper.getBoundingClientRect();
  const scaledWidth = svgWidth * currentScale;
  const scaledHeight = svgHeight * currentScale;

  panX = (wrapperRect.width - scaledWidth) / 2;
  panY = (wrapperRect.height - scaledHeight) / 2;

  if (scaledWidth > wrapperRect.width) {
    panX = 20;
  }
  if (scaledHeight > wrapperRect.height) {
    panY = 20;
  }

  panInner.style.transform = `translate(${panX}px, ${panY}px) scale(${currentScale})`;
  updateZoomDisplay();
}

/* ============================================================
   ZOOM
============================================================ */
function updateZoomDisplay() {
  const btn = document.getElementById("carto-zoom-reset");
  if (btn) {
    btn.textContent = `${Math.round(currentScale * 100)}%`;
  }
}

function applyTransform() {
  const panInner = document.getElementById("pan-inner");
  if (!panInner) return;
  panInner.style.transform = `translate(${panX}px, ${panY}px) scale(${currentScale})`;
  updateZoomDisplay();
}

function zoomAtPoint(delta, mouseX, mouseY) {
  const wrapper = document.getElementById("carto-pan-wrapper");
  if (!wrapper) return;

  const oldScale = currentScale;
  const zoomStep = 0.15;

  if (delta > 0) {
    currentScale = Math.min(ZOOM_MAX, currentScale * (1 + zoomStep));
  } else {
    currentScale = Math.max(ZOOM_MIN, currentScale * (1 - zoomStep));
  }

  const scaleRatio = currentScale / oldScale;
  panX = mouseX - (mouseX - panX) * scaleRatio;
  panY = mouseY - (mouseY - panY) * scaleRatio;

  applyTransform();
}

function zoomAtCenter(delta) {
  const wrapper = document.getElementById("carto-pan-wrapper");
  if (!wrapper) return;

  const rect = wrapper.getBoundingClientRect();
  const centerX = rect.width / 2;
  const centerY = rect.height / 2;

  zoomAtPoint(delta, centerX, centerY);
}

function initZoomButtons() {
  const btnIn = document.getElementById("carto-zoom-in");
  const btnOut = document.getElementById("carto-zoom-out");
  const btnReset = document.getElementById("carto-zoom-reset");

  if (btnIn) {
    btnIn.onclick = () => zoomAtCenter(1);
  }
  if (btnOut) {
    btnOut.onclick = () => zoomAtCenter(-1);
  }
  if (btnReset) {
    btnReset.onclick = () => {
      const wrapper = document.getElementById("carto-pan-wrapper");
      if (wrapper && svgWidth && svgHeight) {
        const wrapperRect = wrapper.getBoundingClientRect();
        const scaleX = (wrapperRect.width - 40) / svgWidth;
        const scaleY = (wrapperRect.height - 40) / svgHeight;
        currentScale = Math.min(scaleX, scaleY, 1);
        currentScale = Math.max(currentScale, 0.1);
      } else {
        currentScale = 0.5;
      }
      centerCartography();
    };
  }
}

/* ============================================================
   PAN (DÉPLACEMENT À LA SOURIS)
============================================================ */
function initPan() {
  const wrapper = document.getElementById("carto-pan-wrapper");
  const panInner = document.getElementById("pan-inner");
  if (!wrapper || !panInner) return;

  const MOVE_THRESHOLD = 5;
  let startPanX = 0;
  let startPanY = 0;

  wrapper.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    
    e.preventDefault();

    isPanning = true;
    hasMoved = false;
    startX = e.clientX;
    startY = e.clientY;
    startPanX = panX;
    startPanY = panY;
    
    wrapper.classList.add("panning");
    panInner.classList.add("no-transition");
  });

  window.addEventListener("mousemove", (e) => {
    if (!isPanning) return;

    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance > MOVE_THRESHOLD && !hasMoved) {
      hasMoved = true;
    }

    panX = startPanX + dx;
    panY = startPanY + dy;
    applyTransform();
  });

  window.addEventListener("mouseup", (e) => {
    if (!isPanning) return;

    isPanning = false;
    wrapper.classList.remove("panning");
    panInner.classList.remove("no-transition");

    setTimeout(() => {
      hasMoved = false;
    }, 10);
  });

  wrapper.addEventListener("dragstart", (e) => e.preventDefault());
}

/* ============================================================
   ZOOM À LA MOLETTE
============================================================ */
function initWheelZoom() {
  const wrapper = document.getElementById("carto-pan-wrapper");
  if (!wrapper) return;

  wrapper.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();

      const delta = e.deltaY > 0 ? -1 : 1;

      const rect = wrapper.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      zoomAtPoint(delta, mouseX, mouseY);
    },
    { passive: false }
  );
}

/* ============================================================
   CHARGEMENT DU SVG INLINE
============================================================ */
async function loadSvgInline() {
  const container = document.getElementById("svg-container");
  if (!container) {
    console.error("[CARTO] Container svg-container non trouvé !");
    return;
  }

  console.log("[CARTO] SVG_EXISTS =", SVG_EXISTS);

  if (!SVG_EXISTS) {
    container.innerHTML = `
      <div class="svg-placeholder">
        <p>🗺️ Aucune cartographie disponible</p>
        <p>Utilisez le <strong>Gestionnaire d'entités</strong> pour importer un fichier SVG</p>
      </div>
    `;
    return;
  }

  try {
    // Charger le SVG depuis l'API
    const svgUrl = "/activities/svg?t=" + Date.now();
    console.log("[CARTO] Chargement du SVG depuis:", svgUrl);
    
    const response = await fetch(svgUrl);
    
    if (!response.ok) {
      throw new Error(`Fichier SVG introuvable (${response.status})`);
    }

    const svgText = await response.text();
    console.log("[CARTO] SVG chargé, taille:", svgText.length, "caractères");
    
    container.innerHTML = svgText;

    // Récupérer l'élément SVG
    svgElement = container.querySelector("svg");
    if (!svgElement) {
      throw new Error("Pas d'élément <svg> trouvé dans le fichier");
    }

    // Configurer le SVG
    setupSvg();

  } catch (error) {
    console.error("[CARTO] Erreur chargement SVG:", error);
    container.innerHTML = `
      <div class="svg-error">
        <p>❌ Erreur de chargement de la cartographie</p>
        <p>${error.message}</p>
      </div>
    `;
  }
}

/* ============================================================
   CONFIGURATION DU SVG APRÈS CHARGEMENT
============================================================ */
function setupSvg() {
  if (!svgElement) return;

  // Récupérer les dimensions via viewBox en priorité
  const vb = svgElement.viewBox && svgElement.viewBox.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    svgWidth = vb.width;
    svgHeight = vb.height;
  } else {
    const widthAttr = svgElement.getAttribute("width");
    const heightAttr = svgElement.getAttribute("height");
    
    if (widthAttr && heightAttr) {
      svgWidth = parseFloat(widthAttr) || 1000;
      svgHeight = parseFloat(heightAttr) || 800;
    } else {
      const rect = svgElement.getBoundingClientRect();
      svgWidth = rect.width || 1000;
      svgHeight = rect.height || 800;
    }
  }

  console.log(`[CARTO] Dimensions SVG: ${svgWidth} x ${svgHeight}`);

  // Appliquer les dimensions au SVG
  svgElement.style.width = svgWidth + "px";
  svgElement.style.height = svgHeight + "px";
  svgElement.style.display = "block";
  svgElement.style.overflow = "visible";

  // Activer les clics sur les activités
  activateSvgClicks();

  // Initialiser zoom
  initZoomButtons();
  
  // Calculer le scale initial
  const wrapper = document.getElementById("carto-pan-wrapper");
  if (wrapper) {
    const wrapperRect = wrapper.getBoundingClientRect();
    const scaleX = (wrapperRect.width - 40) / svgWidth;
    const scaleY = (wrapperRect.height - 40) / svgHeight;
    currentScale = Math.min(scaleX, scaleY, 1);
    currentScale = Math.max(currentScale, 0.1);
  }
  
  setTimeout(() => {
    centerCartography();
  }, 50);

  console.log(`[CARTO] SVG configuré: scale=${Math.round(currentScale * 100)}%`);
}

/* ============================================================
   ACTIVATION DES CLICS SUR LES ACTIVITÉS
============================================================ */
function activateSvgClicks() {
  if (!svgElement) {
    console.error("[CARTO] svgElement est null");
    return;
  }

  console.log("[CARTO] === ACTIVATION DES CLICS ===");
  console.log("[CARTO] SHAPE_ACTIVITY_MAP:", SHAPE_ACTIVITY_MAP);
  console.log("[CARTO] Nombre d'entrées:", Object.keys(SHAPE_ACTIVITY_MAP).length);

  const allElements = svgElement.querySelectorAll("*");
  console.log("[CARTO] Éléments dans le SVG:", allElements.length);

  let foundMids = [];
  let activatedCount = 0;

  allElements.forEach((el) => {
    // Chercher l'attribut mID (plusieurs méthodes)
    let mid = el.getAttributeNS(VISIO_NS, "mID");
    
    if (!mid) {
      mid = el.getAttribute("v:mID");
    }
    
    if (!mid) {
      mid = el.getAttribute("data-mid");
    }
    
    if (!mid) {
      for (let attr of el.attributes || []) {
        if (attr.name.toLowerCase().includes("mid") || attr.name.toLowerCase().includes("shapeid")) {
          mid = attr.value;
          break;
        }
      }
    }

    if (mid) {
      foundMids.push(mid);
    }

    if (!mid) return;

    const activityId = SHAPE_ACTIVITY_MAP[mid];
    
    if (!activityId) return;

    activatedCount++;
    console.log(`[CARTO] ✓ Activité: mID="${mid}" → id=${activityId}`);

    // Marquer comme cliquable
    clickableElements.add(el);
    el.dataset.activityId = activityId;
    el.dataset.mid = mid;

    // Style
    el.style.cursor = "pointer";
    el.classList.add("carto-activity");

    // Effets au survol
    el.addEventListener("mouseenter", () => {
      el.style.filter = "drop-shadow(0 0 8px #22c55e)";
      el.style.opacity = "0.85";
    });

    el.addEventListener("mouseleave", () => {
      el.style.filter = "";
      el.style.opacity = "1";
    });

    // Clic sur l'activité
    el.addEventListener("click", (e) => {
      if (!hasMoved) {
        e.stopPropagation();
        e.preventDefault();
        const url = `/activities/view?activity_id=${activityId}`;
        console.log(`[CARTO] Navigation vers: ${url}`);
        window.location.href = url;
      }
    });
  });

  console.log("[CARTO] === RÉSUMÉ ===");
  console.log(`[CARTO] mIDs trouvés: ${foundMids.length}`);
  console.log(`[CARTO] Activités cliquables: ${activatedCount}`);
  
  if (activatedCount === 0 && Object.keys(SHAPE_ACTIVITY_MAP).length > 0) {
    console.warn("[CARTO] ⚠️ Aucune activité cliquable !");
    console.warn("[CARTO] mIDs dans SVG:", [...new Set(foundMids)].slice(0, 20));
    console.warn("[CARTO] mIDs attendus:", Object.keys(SHAPE_ACTIVITY_MAP).slice(0, 20));
  }
}

/* ============================================================
   LISTE DES ACTIVITÉS (colonne de droite)
============================================================ */
function initListClicks() {
  document.querySelectorAll(".activity-item").forEach((li) => {
    li.addEventListener("click", () => {
      const id = li.dataset.id;
      if (!id) return;
      window.location.href = `/activities/view?activity_id=${id}`;
    });
  });
}

/* ============================================================
   POPUP ACTIONS CARTOGRAPHIE
============================================================ */
function initPopup() {
  const popup = document.getElementById("carto-actions-popup");
  const btnOpen = document.getElementById("carto-actions-btn");
  const btnClose = document.getElementById("close-popup");

  if (!popup || !btnOpen || !btnClose) return;

  btnOpen.onclick = () => popup.classList.remove("hidden");
  btnClose.onclick = () => popup.classList.add("hidden");

  popup.addEventListener("click", (e) => {
    if (e.target === popup) {
      popup.classList.add("hidden");
    }
  });
}

function initReloadButton() {
  const btn = document.getElementById("reload-carto-btn");
  if (!btn) return;

  btn.onclick = () => {
    btn.textContent = "⏳ Mise à jour…";
    btn.disabled = true;
    window.location.reload();
  };
}

function initResyncButton() {
  const btn = document.getElementById("resync-activities-btn");
  if (!btn) return;

  btn.onclick = async () => {
    btn.textContent = "⏳ Re-synchronisation...";
    btn.disabled = true;

    try {
      const res = await fetch("/activities/resync", { method: "POST" });
      const data = await res.json();

      if (data.error) {
        alert("Erreur: " + data.error);
        btn.textContent = "🔄 Re-synchroniser les activités depuis le SVG";
        btn.disabled = false;
        return;
      }

      const msg = `Re-synchronisation terminée!\n\nActivités ajoutées: ${data.sync.added}\nActivités existantes: ${data.sync.existing}\nActivités ignorées (erreurs): ${data.sync.skipped || 0}\nTotal dans SVG: ${data.sync.total_in_svg}`;
      alert(msg);
      
      // Recharger la page pour voir les nouvelles activités
      window.location.reload();

    } catch (e) {
      alert("Erreur réseau: " + e);
      btn.textContent = "🔄 Re-synchroniser les activités depuis le SVG";
      btn.disabled = false;
    }
  };
}

/* ============================================================
   GESTIONNAIRE D'ENTITÉS
============================================================ */
function initEntityManager() {
  const popup = document.getElementById("entity-manager-popup");
  const btnOpen = document.getElementById("entity-manager-btn");
  const btnClose = document.getElementById("close-entity-manager");

  if (!popup || !btnOpen) return;

  btnOpen.onclick = () => {
    popup.classList.remove("hidden");
    loadEntitiesList();
  };
  
  if (btnClose) {
    btnClose.onclick = () => popup.classList.add("hidden");
  }

  popup.addEventListener("click", (e) => {
    if (e.target === popup) {
      popup.classList.add("hidden");
    }
  });

  // Bouton créer entité
  const createBtn = document.getElementById("create-entity-btn");
  if (createBtn) {
    createBtn.onclick = createEntity;
  }

  // Boutons d'action
  document.getElementById("activate-entity-btn")?.addEventListener("click", activateEntity);
  document.getElementById("rename-entity-btn")?.addEventListener("click", showRenameModal);
  document.getElementById("delete-entity-btn")?.addEventListener("click", showDeleteModal);

  // Modals
  document.getElementById("cancel-delete-btn")?.addEventListener("click", hideDeleteModal);
  document.getElementById("confirm-delete-btn")?.addEventListener("click", confirmDelete);
  document.getElementById("cancel-rename-btn")?.addEventListener("click", hideRenameModal);
  document.getElementById("confirm-rename-btn")?.addEventListener("click", confirmRename);

  // Dropzone entité
  initEntityDropzone();
}

async function loadEntitiesList() {
  try {
    const response = await fetch("/activities/api/entities");
    const entities = await response.json();

    const list = document.getElementById("entities-list");
    if (!list) return;

    if (entities.length === 0) {
      list.innerHTML = '<li class="no-entity">Aucune entité créée</li>';
      return;
    }

    list.innerHTML = entities.map(e => `
      <li class="entity-item ${e.is_active ? 'active' : ''}" data-id="${e.id}">
        <span class="entity-name">${e.name}</span>
        ${e.is_active ? '<span class="entity-active-badge">Active</span>' : ''}
        <span class="entity-count">${e.activities_count} activités</span>
      </li>
    `).join("");

    // Ajouter les clics
    list.querySelectorAll(".entity-item").forEach(li => {
      li.addEventListener("click", () => selectEntity(parseInt(li.dataset.id)));
    });

  } catch (error) {
    console.error("Erreur chargement entités:", error);
  }
}

function selectEntity(entityId) {
  selectedEntityId = entityId;

  // Highlight dans la liste
  document.querySelectorAll(".entity-item").forEach(li => {
    li.classList.toggle("selected", parseInt(li.dataset.id) === entityId);
  });

  // Afficher les détails
  const placeholder = document.getElementById("entity-details-placeholder");
  const details = document.getElementById("entity-details");
  
  if (placeholder) placeholder.classList.add("hidden");
  if (details) details.classList.remove("hidden");

  // Charger les infos
  fetch(`/activities/api/entities`)
    .then(r => r.json())
    .then(entities => {
      const entity = entities.find(e => e.id === entityId);
      if (entity) {
        document.getElementById("entity-detail-name").textContent = entity.name;
        document.getElementById("entity-detail-description").textContent = entity.description || "Pas de description";
        document.getElementById("entity-activities-count").textContent = entity.activities_count;
        document.getElementById("entity-svg-status").textContent = entity.svg_filename ? "✓" : "—";
        
        // Masquer le bouton activer si déjà active
        const activateBtn = document.getElementById("activate-entity-btn");
        if (activateBtn) {
          activateBtn.style.display = entity.is_active ? "none" : "inline-block";
        }
      }
    });
}

async function createEntity() {
  const nameInput = document.getElementById("new-entity-name");
  const name = nameInput?.value.trim();

  if (!name) {
    alert("Veuillez entrer un nom pour l'entité");
    return;
  }

  try {
    const response = await fetch("/activities/api/entities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });

    const data = await response.json();

    if (data.error) {
      alert("Erreur: " + data.error);
      return;
    }

    nameInput.value = "";
    loadEntitiesList();
    
    // Sélectionner la nouvelle entité
    setTimeout(() => selectEntity(data.entity.id), 100);

  } catch (error) {
    alert("Erreur réseau");
  }
}

async function activateEntity() {
  if (!selectedEntityId) return;

  try {
    const response = await fetch(`/activities/api/entities/${selectedEntityId}/activate`, {
      method: "POST"
    });

    const data = await response.json();

    if (data.error) {
      alert("Erreur: " + data.error);
      return;
    }

    // Recharger la page pour mettre à jour tout le contexte
    window.location.reload();

  } catch (error) {
    alert("Erreur réseau");
  }
}

function showDeleteModal() {
  if (!selectedEntityId) return;
  document.getElementById("confirm-delete-modal")?.classList.remove("hidden");
}

function hideDeleteModal() {
  document.getElementById("confirm-delete-modal")?.classList.add("hidden");
}

async function confirmDelete() {
  if (!selectedEntityId) return;

  try {
    const response = await fetch(`/activities/api/entities/${selectedEntityId}`, {
      method: "DELETE"
    });

    const data = await response.json();

    if (data.error) {
      alert("Erreur: " + data.error);
      return;
    }

    hideDeleteModal();
    
    // Recharger la page
    window.location.reload();

  } catch (error) {
    alert("Erreur réseau");
  }
}

function showRenameModal() {
  if (!selectedEntityId) return;
  
  const currentName = document.getElementById("entity-detail-name")?.textContent || "";
  const input = document.getElementById("rename-input");
  if (input) input.value = currentName;
  
  document.getElementById("rename-modal")?.classList.remove("hidden");
}

function hideRenameModal() {
  document.getElementById("rename-modal")?.classList.add("hidden");
}

async function confirmRename() {
  if (!selectedEntityId) return;

  const newName = document.getElementById("rename-input")?.value.trim();
  if (!newName) {
    alert("Veuillez entrer un nom");
    return;
  }

  try {
    const response = await fetch(`/activities/api/entities/${selectedEntityId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName })
    });

    const data = await response.json();

    if (data.error) {
      alert("Erreur: " + data.error);
      return;
    }

    hideRenameModal();
    loadEntitiesList();
    selectEntity(selectedEntityId);

  } catch (error) {
    alert("Erreur réseau");
  }
}

/* ============================================================
   DROPZONE ENTITÉ (Upload SVG)
============================================================ */
function initEntityDropzone() {
  const zone = document.getElementById("entity-dropzone");
  const status = document.getElementById("entity-dropzone-status");
  if (!zone || !status) return;

  // Input file caché
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".svg";
  fileInput.style.display = "none";
  document.body.appendChild(fileInput);

  zone.addEventListener("click", () => {
    if (!selectedEntityId && !ACTIVE_ENTITY) {
      alert("Veuillez d'abord sélectionner ou activer une entité");
      return;
    }
    fileInput.click();
  });

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (file) {
      await uploadEntitySvg(file, status);
    }
  });

  // Drag & drop
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  });

  zone.addEventListener("dragleave", () => {
    zone.classList.remove("dragover");
  });

  zone.addEventListener("drop", async (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");

    const file = e.dataTransfer.files[0];
    if (file) {
      await uploadEntitySvg(file, status);
    }
  });
}

async function uploadEntitySvg(file, status) {
  if (!file.name.toLowerCase().endsWith(".svg")) {
    status.innerHTML = "❌ Format invalide — fichier SVG requis";
    status.className = "dropzone-status error";
    return;
  }

  // Vérifier qu'on a une entité active ou sélectionnée
  const targetEntityId = selectedEntityId || (ACTIVE_ENTITY ? ACTIVE_ENTITY.id : null);
  
  if (!targetEntityId) {
    status.innerHTML = "❌ Aucune entité active";
    status.className = "dropzone-status error";
    return;
  }

  // Si l'entité sélectionnée n'est pas active, l'activer d'abord
  if (selectedEntityId && (!ACTIVE_ENTITY || ACTIVE_ENTITY.id !== selectedEntityId)) {
    status.innerHTML = "⏳ Activation de l'entité...";
    status.className = "dropzone-status loading";
    
    await fetch(`/activities/api/entities/${selectedEntityId}/activate`, {
      method: "POST"
    });
  }

  status.innerHTML = "⏳ Upload en cours...";
  status.className = "dropzone-status loading";

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch("/activities/upload-carto", {
      method: "POST",
      body: form,
    });

    const data = await res.json();

    if (data.error) {
      status.innerHTML = "❌ " + data.error;
      status.className = "dropzone-status error";
      return;
    }

    status.innerHTML = "✓ Cartographie installée — rechargement...";
    status.className = "dropzone-status success";
    setTimeout(() => window.location.reload(), 1200);

  } catch (error) {
    status.innerHTML = "❌ Erreur réseau";
    status.className = "dropzone-status error";
  }
}

/* ============================================================
   INITIALISATION GLOBALE
============================================================ */
document.addEventListener("DOMContentLoaded", async () => {
  console.log("[CARTO] ========================================");
  console.log("[CARTO] Initialisation de la cartographie");
  console.log("[CARTO] ACTIVE_ENTITY:", ACTIVE_ENTITY);
  console.log("[CARTO] SVG_EXISTS:", SVG_EXISTS);
  console.log("[CARTO] SHAPE_ACTIVITY_MAP:", Object.keys(SHAPE_ACTIVITY_MAP).length, "entrées");
  console.log("[CARTO] ========================================");

  // Initialiser les contrôles UI
  initListClicks();
  initPopup();
  initReloadButton();
  initResyncButton();
  initEntityManager();

  // Initialiser pan et zoom
  initPan();
  initWheelZoom();

  // Charger le SVG inline
  await loadSvgInline();
  
  console.log("[CARTO] Initialisation terminée");
});