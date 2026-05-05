(() => {
  const select = document.getElementById("user-select");
  const fullList = document.getElementById("full-list");
  const partialList = document.getElementById("partial-list");
  const alertBox = document.getElementById("alert");
  const spinner = document.getElementById("spinner");
  const filterInput = document.getElementById("job-filter");
  const detailPanel = document.getElementById("job-detail-panel");

  const fullCount = document.getElementById("full-count");
  const partialCount = document.getElementById("partial-count");

  const fullMoreBtn = document.getElementById("full-more");
  const partialMoreBtn = document.getElementById("partial-more");

  const INITIAL_LIMIT = 30;
  const MORE_CHUNK = 20;

  let currentUserId = null;
  let fullOffset = 0;
  let partialOffset = 0;
  let fullTotal = 0;
  let partialTotal = 0;

  function showAlert(msg) {
    if (!alertBox) return;
    alertBox.textContent = msg || "";
    alertBox.style.display = msg ? "block" : "none";
  }

  function setLoading(isLoading) {
    if (spinner) spinner.classList.toggle("show", isLoading);
  }

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
      btn.classList.add("is-loading");
      btn.setAttribute("disabled", "disabled");
    } else {
      btn.classList.remove("is-loading");
      btn.removeAttribute("disabled");
    }
  }

  function clearLists() {
    if (fullList) fullList.innerHTML = "";
    if (partialList) partialList.innerHTML = "";
    if (fullCount) fullCount.textContent = "0/0";
    if (partialCount) partialCount.textContent = "0/0";
    fullOffset = 0;
    partialOffset = 0;
    fullTotal = 0;
    partialTotal = 0;

    if (fullMoreBtn) fullMoreBtn.style.display = "none";
    if (partialMoreBtn) partialMoreBtn.style.display = "none";

    if (detailPanel) {
      detailPanel.innerHTML = `
        <div class="pm-detail-empty">
          <div class="pm-detail-empty-icon"><i class="fa-solid fa-magnifying-glass-chart"></i></div>
          <h2 class="pm-card-title" style="margin-bottom:8px;">Détail d’un métier</h2>
          <p class="pm-help">Cliquez sur un métier pour voir :</p>
          <ul class="pm-detail-empty-list">
            <li>Le score global de correspondance</li>
            <li>Les compétences ROME déjà couvertes</li>
            <li>Les compétences à développer</li>
          </ul>
        </div>`;
    }
  }

  function scoreClass(p) {
    if (p >= 100) return "badge-green";
    if (p >= 60) return "badge-lime";
    if (p >= 30) return "badge-amber";
    if (p > 0) return "badge-orange";
    return "badge-gray";
  }

  function renderJobDetail(item, kind) {
    if (!detailPanel || !item) return;
    const ownedCount = item.owned_count ?? (Array.isArray(item.owned) ? item.owned.length : 0);
    const missingCount = item.missing_count ?? (Array.isArray(item.missing) ? item.missing.length : 0);
    const total = item.total ?? ownedCount + missingCount;

    detailPanel.innerHTML = `
      <div class="pm-detail">
        <div class="pm-detail-head">
          <div>
            <div class="pm-detail-title">${item.label || "Métier ROME"}</div>
            <div class="pm-detail-code">${item.code ? `Code ROME : ${item.code}` : ""}</div>
          </div>
          <div class="pm-score-circle">
            <div class="pm-score-value">${item.score != null ? item.score : 0}%</div>
            <div class="pm-score-label">${
              kind === "full" ? "Métiers maîtrisables" : "Métiers envisageables"
            }</div>
          </div>
        </div>

        <div class="pm-detail-metrics">
          <span class="met ok">Compétences couvertes : <b>${ownedCount}</b></span>
          <span class="met miss">À développer : <b>${missingCount}</b></span>
          <span class="met tot">Total ROME : <b>${total}</b></span>
        </div>

        <div class="pm-detail-blocks">
          <div class="pm-detail-section">
            <h3>Compétences déjà couvertes</h3>
            ${
              Array.isArray(item.owned) && item.owned.length
                ? `<ul class="pm-detail-list">
                    ${item.owned.map((v) => `<li>${v}</li>`).join("")}
                  </ul>`
                : `<p class="pm-detail-empty-text">Aucune compétence ROME n’a été reconnue comme couverte pour ce métier.</p>`
            }
          </div>
          <div class="pm-detail-section">
            <h3>Compétences à développer</h3>
            ${
              Array.isArray(item.missing) && item.missing.length
                ? `<ul class="pm-detail-list">
                    ${item.missing.map((v) => `<li>${v}</li>`).join("")}
                   </ul>`
                : `<p class="pm-detail-empty-text">Aucune compétence manquante détectée : ce métier est pleinement maîtrisé.</p>`
            }
          </div>
        </div>
      </div>
    `;
  }

  function makeList(items, kind) {
    const frag = document.createDocumentFragment();

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "job-card";
      if (kind === "partial") li.classList.add("is-partial");

      li.dataset.label = (item.label || "").toLowerCase();
      li.dataset.code = (item.code || "").toLowerCase();
      li.dataset.kind = kind;

      const header = document.createElement("div");
      header.className = "job-row";

      const title = document.createElement("strong");
      title.className = "job-title";
      title.textContent = `${item.label || "Métier"}${item.code ? " (" + item.code + ")" : ""}`;

      const score = document.createElement("span");
      score.className = `badge ${scoreClass(item.score)}`;
      score.textContent = `${item.score}%`;

      header.appendChild(title);
      header.appendChild(score);
      li.appendChild(header);

      const metrics = document.createElement("div");
      metrics.className = "metrics";
      metrics.innerHTML = `
        <span class="met ok">En commun : <b>${
          item.owned_count ?? (Array.isArray(item.owned) ? item.owned.length : 0)
        }</b></span>
        <span class="met miss">À développer : <b>${
          item.missing_count ?? (Array.isArray(item.missing) ? item.missing.length : 0)
        }</b></span>
        <span class="met tot">Total : <b>${
          item.total ?? (
            (Array.isArray(item.owned) ? item.owned.length : 0) +
            (Array.isArray(item.missing) ? item.missing.length : 0)
          )
        }</b></span>`;
      li.appendChild(metrics);

      const details = document.createElement("div");
      details.className = "lists-wrap";

      if (Array.isArray(item.owned) && item.owned.length) {
        const d1 = document.createElement("details");
        d1.className = "job-details owned";
        const s1 = document.createElement("summary");
        s1.textContent = `Compétences en commun (${item.owned.length})`;
        d1.appendChild(s1);

        const ul1 = document.createElement("ul");
        ul1.className = "owned-list";
        item.owned.slice(0, 10).forEach((v) => {
          const li1 = document.createElement("li");
          li1.textContent = v;
          ul1.appendChild(li1);
        });
        if (item.owned.length > 10) {
          const more = document.createElement("em");
          more.textContent = `… et ${item.owned.length - 10} autres`;
          ul1.appendChild(more);
        }
        d1.appendChild(ul1);
        details.appendChild(d1);
      }

      if (Array.isArray(item.missing) && item.missing.length) {
        const d2 = document.createElement("details");
        d2.className = "job-details missing";
        const s2 = document.createElement("summary");
        s2.textContent = `Compétences à développer (${item.missing.length})`;
        d2.appendChild(s2);

        const ul2 = document.createElement("ul");
        ul2.className = "missing-list";
        item.missing.slice(0, 10).forEach((v) => {
          const li2 = document.createElement("li");
          li2.textContent = v;
          ul2.appendChild(li2);
        });
        if (item.missing.length > 10) {
          const more = document.createElement("em");
          more.textContent = `… et ${item.missing.length - 10} autres`;
          ul2.appendChild(more);
        }
        d2.appendChild(ul2);
        details.appendChild(d2);
      }

      li.appendChild(details);

      li.addEventListener("click", (evt) => {
        if (evt.target.closest("details")) return;
        document.querySelectorAll(".job-card.selected").forEach((c) => c.classList.remove("selected"));
        li.classList.add("selected");
        renderJobDetail(item, kind);
      });

      frag.appendChild(li);
    });

    return frag;
  }

  function updateCounters() {
    if (fullCount) fullCount.textContent = fullTotal;
    if (partialCount) partialCount.textContent = partialTotal;
  }

  async function fetchPage({ userId, fullLim = 0, fullOff = 0, partialLim = 0, partialOff = 0 }) {
    const url = new URL(
      window.location.origin + `/projection_metier/analyze/${encodeURIComponent(userId)}`
    );
    if (fullLim !== null) url.searchParams.set("full_limit", fullLim);
    if (fullOff !== null) url.searchParams.set("full_offset", fullOff);
    if (partialLim !== null) url.searchParams.set("partial_limit", partialLim);
    if (partialOff !== null) url.searchParams.set("partial_offset", partialOff);

    const res = await fetch(url.toString(), { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function initialLoad(userId) {
    setLoading(true);
    showAlert("");
    clearLists();
    try {
      const data = await fetchPage({
        userId,
        fullLim: INITIAL_LIMIT,
        fullOff: 0,
        partialLim: INITIAL_LIMIT,
        partialOff: 0,
      });

      const full = Array.isArray(data.full) ? data.full : [];
      const partial = Array.isArray(data.partial) ? data.partial : [];

      fullTotal = data?.page?.full?.total || full.length;
      fullOffset = (data?.page?.full?.offset || 0) + full.length;

      partialTotal = data?.page?.partial?.total || partial.length;
      partialOffset = (data?.page?.partial?.offset || 0) + partial.length;

      if (full.length && fullList) {
        fullList.appendChild(makeList(full, "full"));
      }
      if (partial.length && partialList) {
        partialList.appendChild(makeList(partial, "partial"));
      }

      if (data?.page?.full?.has_more && fullMoreBtn) {
        fullMoreBtn.style.display = "inline-flex";
      } else if (fullMoreBtn) {
        fullMoreBtn.style.display = "none";
      }

      if (data?.page?.partial?.has_more && partialMoreBtn) {
        partialMoreBtn.style.display = "inline-flex";
      } else if (partialMoreBtn) {
        partialMoreBtn.style.display = "none";
      }

      if (fullTotal === 0 && partialTotal === 0) {
        showAlert("Aucun métier trouvé avec les données actuelles.");
      }

      updateCounters();
      applyFilter();
    } catch (e) {
      console.error(e);
      showAlert("Une erreur est survenue lors de l'analyse (connexion ou serveur).");
    } finally {
      setLoading(false);
    }
  }

  async function loadMore(kind) {
    if (!currentUserId) return;
    if (kind === "full") setButtonLoading(fullMoreBtn, true);
    else setButtonLoading(partialMoreBtn, true);

    try {
      let params;
      if (kind === "full") {
        params = {
          userId: currentUserId,
          fullLim: MORE_CHUNK,
          fullOff: fullOffset,
          partialLim: 0,
          partialOff: 0,
        };
      } else {
        params = {
          userId: currentUserId,
          fullLim: 0,
          fullOff: 0,
          partialLim: MORE_CHUNK,
          partialOff: partialOffset,
        };
      }
      const data = await fetchPage(params);

      if (kind === "full") {
        const arr = Array.isArray(data.full) ? data.full : [];
        if (arr.length && fullList) {
          fullList.appendChild(makeList(arr, "full"));
          fullOffset += arr.length;
        }
        if (!(data?.page?.full?.has_more) && fullMoreBtn) fullMoreBtn.style.display = "none";
      } else {
        const arr = Array.isArray(data.partial) ? data.partial : [];
        if (arr.length && partialList) {
          partialList.appendChild(makeList(arr, "partial"));
          partialOffset += arr.length;
        }
        if (!(data?.page?.partial?.has_more) && partialMoreBtn) partialMoreBtn.style.display = "none";
      }

      updateCounters();
      applyFilter();
    } catch (e) {
      console.error(e);
      showAlert("Impossible de charger plus d'éléments.");
    } finally {
      if (kind === "full") setButtonLoading(fullMoreBtn, false);
      else setButtonLoading(partialMoreBtn, false);
    }
  }

  function applyFilter() {
    const q = (filterInput?.value || "").trim().toLowerCase();
    const cards = document.querySelectorAll(".job-card");
    if (!q) {
      cards.forEach((c) => (c.style.display = ""));
      return;
    }
    cards.forEach((c) => {
      const label = c.dataset.label || "";
      const code = c.dataset.code || "";
      c.style.display = label.includes(q) || code.includes(q) ? "" : "none";
    });
  }

  if (fullMoreBtn) fullMoreBtn.addEventListener("click", () => loadMore("full"));
  if (partialMoreBtn) partialMoreBtn.addEventListener("click", () => loadMore("partial"));

  if (select) {
    select.addEventListener("change", (e) => {
      const val = e.target.value;
      if (!val || val === "0") {
        currentUserId = null;
        clearLists();
        showAlert("");
        return;
      }
      currentUserId = val;
      initialLoad(currentUserId);
    });
  }

  if (filterInput) {
    filterInput.addEventListener("input", () => {
      applyFilter();
    });
  }
})();
