// static/js/file-picker.js
// Composant drag & drop pour l'upload de fichiers vers /utils/upload-file

/**
 * Initialise un composant file-picker.
 * Structure HTML attendue :
 *   <div class="fp-wrap">
 *     <div class="fp-zone">...</div>
 *     <div class="fp-selected hidden">...</div>
 *     <input type="file" class="fp-input" style="display:none">
 *     <input type="hidden" class="fp-path">
 *   </div>
 *
 * @param {HTMLElement} el - Le conteneur .fp-wrap
 */
function initFilePicker(el) {
  if (!el || el.dataset.fpInit) return;
  el.dataset.fpInit = "1";

  const zone     = el.querySelector(".fp-zone");
  const fileIn   = el.querySelector(".fp-input");
  const selDiv   = el.querySelector(".fp-selected");
  const fnameEl  = el.querySelector(".fp-fname");
  const clearBtn = el.querySelector(".fp-clear");
  const pathIn   = el.querySelector(".fp-path");
  const spinner  = el.querySelector(".fp-spinner");

  if (!zone || !fileIn || !pathIn) return;

  /* ── Affichage ── */
  function showSelected(name, path) {
    pathIn.value = path;
    if (fnameEl) fnameEl.textContent = name;
    zone.classList.add("hidden");
    if (selDiv) selDiv.classList.remove("hidden");
  }

  function resetPicker() {
    pathIn.value = "";
    fileIn.value = "";
    if (fnameEl) fnameEl.textContent = "";
    zone.classList.remove("hidden");
    if (selDiv) selDiv.classList.add("hidden");
    zone.classList.remove("fp-uploading");
  }

  /* ── Upload ── */
  async function handleFile(file) {
    zone.classList.add("fp-uploading");
    if (spinner) spinner.style.display = "";

    const fd = new FormData();
    fd.append("file", file);

    try {
      const r = await fetch("/utils/upload-file", { method: "POST", body: fd });
      const d = await r.json();
      if (r.ok && d.path) {
        showSelected(d.original_name || file.name, d.path);
      } else {
        alert("Erreur upload : " + (d.error || "inconnue"));
      }
    } catch {
      alert("Erreur réseau lors de l'upload.");
    } finally {
      zone.classList.remove("fp-uploading");
      if (spinner) spinner.style.display = "none";
    }
  }

  /* ── Events ── */
  zone.addEventListener("click", () => fileIn.click());

  fileIn.addEventListener("change", () => {
    if (fileIn.files && fileIn.files[0]) handleFile(fileIn.files[0]);
  });

  zone.addEventListener("dragover", e => {
    e.preventDefault();
    zone.classList.add("fp-dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("fp-dragover"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("fp-dragover");
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  clearBtn && clearBtn.addEventListener("click", e => {
    e.stopPropagation();
    resetPicker();
  });
}

/* ─────────────────────────────────────────
   Helpers publics
   ───────────────────────────────────────── */

/** Retourne le chemin uploadé ou "" */
function fpGetPath(el) {
  return (el && el.querySelector(".fp-path") || {}).value || "";
}

/** Réinitialise un picker (appelé après submit) */
function fpReset(el) {
  if (!el) return;
  const pathIn = el.querySelector(".fp-path");
  const fileIn = el.querySelector(".fp-input");
  const fnameEl = el.querySelector(".fp-fname");
  const zone   = el.querySelector(".fp-zone");
  const selDiv = el.querySelector(".fp-selected");
  if (pathIn) pathIn.value = "";
  if (fileIn) fileIn.value = "";
  if (fnameEl) fnameEl.textContent = "";
  if (zone)   zone.classList.remove("hidden");
  if (selDiv) selDiv.classList.add("hidden");
}

/** Pré-remplit un picker avec un chemin existant (édition) */
function fpSetPath(el, path, displayName) {
  if (!el) return;
  const pathIn = el.querySelector(".fp-path");
  const fnameEl = el.querySelector(".fp-fname");
  const zone   = el.querySelector(".fp-zone");
  const selDiv = el.querySelector(".fp-selected");
  if (!path) { fpReset(el); return; }
  if (pathIn) pathIn.value = path;
  if (fnameEl) fnameEl.textContent = displayName || path.split("/").pop().split("\\").pop();
  if (zone)   zone.classList.add("hidden");
  if (selDiv) selDiv.classList.remove("hidden");
}

/* ─────────────────────────────────────────
   HTML helper : génère le markup d'un picker
   ───────────────────────────────────────── */
function fpHTML(id, accept) {
  const acceptAttr = accept ? `accept="${accept}"` : "";
  return `
<div class="fp-wrap" id="${id}">
  <div class="fp-zone">
    <span class="fp-spinner" style="display:none"><i class="fa-solid fa-spinner fa-spin"></i></span>
    <i class="fa-solid fa-cloud-arrow-up fp-icon"></i>
    <p class="fp-text">Glisser un fichier ici ou <span class="fp-browse">parcourir</span></p>
    <p class="fp-hint">PDF, Word, Excel, Visio, JSON…</p>
  </div>
  <div class="fp-selected hidden">
    <i class="fa-solid fa-file-circle-check fp-ok-icon"></i>
    <span class="fp-fname"></span>
    <button type="button" class="fp-clear" title="Supprimer le fichier"><i class="fa-solid fa-xmark"></i></button>
  </div>
  <input type="file" class="fp-input" ${acceptAttr}>
  <input type="hidden" class="fp-path">
</div>`;
}

/* ─────────────────────────────────────────
   Auto-init au chargement
   ───────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".fp-wrap").forEach(initFilePicker);
});
