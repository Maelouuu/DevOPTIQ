// Code/static/js/propose_aptitudes.js
(function () {
  const API_PROPOSE     = "/propose_aptitudes/propose";
  const API_FEASIBILITY = "/propose_aptitudes/feasibility";

  const safeShowSpinner = () => (typeof showSpinner === "function" ? showSpinner() : void 0);
  const safeHideSpinner = () => (typeof hideSpinner === "function" ? hideSpinner() : void 0);

  function $(sel, ctx = document) { return ctx.querySelector(sel); }

  function escHtml(str) {
    return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
  }

  async function fetchWithTimeout(url, opts = {}, timeoutMs = 60000) {
    const ctl = new AbortController();
    const id  = setTimeout(() => ctl.abort(), timeoutMs);
    try { return await fetch(url, { signal: ctl.signal, ...opts }); }
    finally { clearTimeout(id); }
  }

  // ============================================================
  //  AIDES / COMPENSATIONS PRÉDÉFINIES
  // ============================================================
  const AIDS_CATEGORIES = [
    { title: "Aides visuelles", items: [
      "Zoom / agrandissement écran", "Contraste élevé", "Lecteur d'écran", "Grand écran / double écran"
    ]},
    { title: "Aides auditives", items: [
      "Prothèse auditive", "Boucle magnétique", "Sous-titrage temps réel", "Communication écrite prioritaire"
    ]},
    { title: "Aides motrices", items: [
      "Clavier / souris adapté", "Reconnaissance vocale / dictée", "Support bras / poignet", "Bureau réglable en hauteur"
    ]},
    { title: "Aides cognitives", items: [
      "Aide-mémoire / check-lists", "Logiciel de structuration", "Temps supplémentaire", "Consignes simplifiées"
    ]},
    { title: "Aides environnementales", items: [
      "Bureau isolé / calme", "Casque anti-bruit", "Éclairage adapté", "Horaires aménagés"
    ]}
  ];

  // ============================================================
  //  STATE
  // ============================================================
  let _scoringData = null;
  let _activityName = "";
  let _activityId = null;

  // ============================================================
  //  MODAL MANAGEMENT
  // ============================================================
  function ensureModal() {
    let overlay = $("#proposeAptitudesModalOverlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "proposeAptitudesModalOverlay";
      overlay.className = "modal-overlay-propose";
      overlay.style.display = "none";
      overlay.onclick = (e) => { if (e.target === overlay) hideModal(); };

      const dialog = document.createElement("div");
      dialog.id = "proposeAptitudesModal";
      dialog.className = "modal-content-propose modal-wide";
      dialog.innerHTML = `
        <div class="modal-header-propose">
          <h3 id="apt-modal-title"><i class="fa-solid fa-universal-access"></i> Analyse Inclusion</h3>
          <button class="modal-close-btn-propose" id="apt-close">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
        <div class="modal-body-propose" id="apt-modal-body"></div>
        <div class="modal-footer-propose" id="apt-modal-footer"></div>
      `;
      overlay.appendChild(dialog);
      document.body.appendChild(overlay);
      $("#apt-close", dialog).onclick = () => hideModal();
    }
    return overlay;
  }

  function showModal() { ensureModal().style.display = "flex"; }
  function hideModal() { const m = $("#proposeAptitudesModalOverlay"); if (m) m.style.display = "none"; }

  // ============================================================
  //  STEP 1 : SCORING INCLUSION
  // ============================================================
  function renderNiveauBadge(niveau) {
    const m = String(niveau).match(/(\d)/);
    const n = m ? m[1] : "0";
    return `<span class="scoring-niveau-badge scoring-niveau-${n}">${escHtml(niveau)}</span>`;
  }

  function renderScoringStep(data) {
    const body = $("#apt-modal-body");
    const footer = $("#apt-modal-footer");
    const title = $("#apt-modal-title");
    title.innerHTML = '<i class="fa-solid fa-universal-access"></i> Analyse Inclusion — Scoring';

    let html = '';

    // Step indicator (dot 2 cliquable pour aller à la faisabilité si scoring chargé)
    html += `
      <div class="step-indicator">
        <span class="step-dot active">1</span>
        <span class="step-label active">Scoring Inclusion</span>
        <span class="step-separator"></span>
        <span class="step-dot inactive clickable" id="apt-dot-2">2</span>
        <span class="step-label">Faisabilité</span>
      </div>
    `;

    html += '<div class="scoring-container">';

    // Vision
    if (data.vision) {
      html += `
        <div class="scoring-category">
          <div class="scoring-category-header">
            <span class="scoring-category-title"><i class="fa-solid fa-eye"></i> Vision</span>
            ${renderNiveauBadge(data.vision.niveau)}
          </div>
          <div class="scoring-risque">${escHtml(data.vision.risque || '')}</div>
          <ul class="scoring-leviers">
            ${(data.vision.leviers || []).map(l => `<li>${escHtml(l)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Auditif
    if (data.auditif) {
      html += `
        <div class="scoring-category">
          <div class="scoring-category-header">
            <span class="scoring-category-title"><i class="fa-solid fa-ear-deaf"></i> Auditif</span>
            ${renderNiveauBadge(data.auditif.niveau)}
          </div>
          <div class="scoring-risque">${escHtml(data.auditif.risque || '')}</div>
          <ul class="scoring-leviers">
            ${(data.auditif.leviers || []).map(l => `<li>${escHtml(l)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Physique — sous-niveaux comme badges dans le header
    if (data.physique) {
      const p = data.physique;
      html += `
        <div class="scoring-category">
          <div class="scoring-category-header">
            <span class="scoring-category-title"><i class="fa-solid fa-person"></i> Physique</span>
            <div class="scoring-physique-badges">
              <span class="scoring-physique-sub"><span class="scoring-physique-label">Haut</span>${renderNiveauBadge(p.haut_du_corps)}</span>
              <span class="scoring-physique-sub"><span class="scoring-physique-label">Bas</span>${renderNiveauBadge(p.bas_du_corps)}</span>
              <span class="scoring-physique-sub"><span class="scoring-physique-label">Fatigue</span>${renderNiveauBadge(p.fatigabilite)}</span>
            </div>
          </div>
          <div class="scoring-risque">${escHtml(p.risque || '')}</div>
          <ul class="scoring-leviers">
            ${(p.leviers || []).map(l => `<li>${escHtml(l)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Environnemental
    if (data.environnemental) {
      html += `
        <div class="scoring-category">
          <div class="scoring-category-header">
            <span class="scoring-category-title"><i class="fa-solid fa-volume-high"></i> Environnemental</span>
            ${renderNiveauBadge(data.environnemental.niveau)}
          </div>
          <div class="scoring-risque">${escHtml(data.environnemental.risque || '')}</div>
          <ul class="scoring-leviers">
            ${(data.environnemental.leviers || []).map(l => `<li>${escHtml(l)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Exposition / Risque
    if (data.exposition_risque) {
      html += `
        <div class="scoring-category">
          <div class="scoring-category-header">
            <span class="scoring-category-title"><i class="fa-solid fa-triangle-exclamation"></i> Exposition / Risque</span>
            ${renderNiveauBadge(data.exposition_risque.niveau)}
          </div>
          <div class="scoring-risque">${escHtml(data.exposition_risque.risque || '')}</div>
          <ul class="scoring-leviers">
            ${(data.exposition_risque.leviers || []).map(l => `<li>${escHtml(l)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    html += '</div>'; // end scoring-container

    // Profils valorisables
    if (data.profils_valorisables && data.profils_valorisables.length) {
      html += `<div style="margin-top:18px;">`;
      html += `<div class="scoring-profils-title"><i class="fa-solid fa-star"></i> Profils valorisables</div>`;
      data.profils_valorisables.forEach(pv => {
        html += `
          <div class="profil-valorisable">
            <div class="profil-name">${escHtml(pv.profil)}</div>
            <div class="profil-atout">${escHtml(pv.atout_possible)}</div>
            <div class="profil-condition">${escHtml(pv.condition)}</div>
          </div>
        `;
      });
      html += '</div>';
    }

    body.innerHTML = html;

    // Dot 2 → naviguer vers faisabilité
    const dot2 = $("#apt-dot-2");
    if (dot2) dot2.onclick = () => renderFeasibilityForm();

    // Footer
    footer.innerHTML = `
      <button class="btn-modal-secondary-propose" id="apt-close-btn">
        <i class="fa-solid fa-xmark"></i> Fermer
      </button>
      <button class="btn-modal-secondary-propose" id="apt-save-leviers-btn">
        <i class="fa-solid fa-floppy-disk"></i> Sauvegarder les leviers
      </button>
      <button class="btn-modal-primary-propose" id="apt-feasibility-btn">
        <i class="fa-solid fa-wheelchair"></i> Évaluer la faisabilité
      </button>
    `;

    $("#apt-close-btn").onclick = () => hideModal();
    $("#apt-save-leviers-btn").onclick = () => saveLeviers(data);
    $("#apt-feasibility-btn").onclick = () => renderFeasibilityForm();
  }

  // ============================================================
  //  STEP 2 : FAISABILITÉ FORM
  // ============================================================
  function renderFeasibilityForm() {
    const body = $("#apt-modal-body");
    const footer = $("#apt-modal-footer");
    const title = $("#apt-modal-title");
    title.innerHTML = '<i class="fa-solid fa-wheelchair"></i> Faisabilité d\'adaptation';

    const profileFields = [
      { key: "vision", label: "Vision" },
      { key: "audition", label: "Audition / communication" },
      { key: "motricite_fine", label: "Motricité fine (mains)" },
      { key: "mobilite_posture", label: "Mobilité / posture" },
      { key: "endurance", label: "Endurance / fatigabilité" },
      { key: "sensibilite_env", label: "Sensibilité environnementale" }
    ];

    const options = `
      <option value="inconnu">— Non renseigné —</option>
      <option value="0">0 (Aucune limitation)</option>
      <option value="1">1 (Légère)</option>
      <option value="2">2 (Modérée)</option>
      <option value="3">3 (Sévère)</option>
    `;

    let html = '';

    // Step indicator (dot 1 cliquable pour revenir au scoring)
    html += `
      <div class="step-indicator">
        <span class="step-dot inactive clickable" id="apt-dot-1">1</span>
        <span class="step-label">Scoring Inclusion</span>
        <span class="step-separator"></span>
        <span class="step-dot active">2</span>
        <span class="step-label active">Faisabilité</span>
      </div>
    `;

    // Profil fonctionnel
    html += `<div class="feasibility-section-title"><i class="fa-solid fa-user-gear"></i> Profil fonctionnel</div>`;
    html += '<div class="feasibility-form">';
    profileFields.forEach(f => {
      html += `
        <div class="feasibility-field">
          <label for="feas-${f.key}">${f.label}</label>
          <select id="feas-${f.key}">${options}</select>
        </div>
      `;
    });
    html += '</div>';

    // Commentaire
    html += `
      <div class="feasibility-section-title"><i class="fa-solid fa-comment"></i> Commentaire court (facultatif)</div>
      <div class="feasibility-field" style="max-width:100%;">
        <input type="text" id="feas-commentaire" placeholder="Sans détail médical..." style="width:100%;">
      </div>
    `;

    // Aides / compensations
    html += `<div class="feasibility-section-title"><i class="fa-solid fa-toolbox"></i> Aides / compensations déjà en place</div>`;
    html += '<div class="aids-section">';
    AIDS_CATEGORIES.forEach(cat => {
      html += `<div class="aids-group-title">${escHtml(cat.title)}</div>`;
      html += '<div class="aids-checklist">';
      cat.items.forEach(item => {
        const id = 'aid-' + item.replace(/[^a-zA-Z0-9]/g, '-').toLowerCase();
        html += `<label><input type="checkbox" id="${id}" value="${escHtml(item)}"> ${escHtml(item)}</label>`;
      });
      html += '</div>';
    });
    html += `
      <div class="aids-other-field">
        <input type="text" id="feas-aids-other" placeholder="Autres aides (préciser)...">
      </div>
    `;
    html += '</div>';

    body.innerHTML = html;

    // Dot 1 → revenir au scoring si disponible
    const dot1 = $("#apt-dot-1");
    if (dot1 && _scoringData) dot1.onclick = () => renderScoringStep(_scoringData);

    // Footer
    footer.innerHTML = `
      <button class="btn-modal-secondary-propose" id="apt-back-btn">
        <i class="fa-solid fa-arrow-left"></i> Retour au scoring
      </button>
      <button class="btn-modal-primary-propose" id="apt-analyze-btn">
        <i class="fa-solid fa-magnifying-glass-chart"></i> Analyser
      </button>
    `;

    $("#apt-back-btn").onclick = () => renderScoringStep(_scoringData);
    $("#apt-analyze-btn").onclick = () => submitFeasibility();
  }

  // ============================================================
  //  SUBMIT FEASIBILITY
  // ============================================================
  async function submitFeasibility() {
    const body = $("#apt-modal-body");
    const footer = $("#apt-modal-footer");

    // Collect profile
    const profil = {};
    ["vision", "audition", "motricite_fine", "mobilite_posture", "endurance", "sensibilite_env"].forEach(k => {
      const sel = $(`#feas-${k}`);
      profil[k] = sel ? sel.value : "inconnu";
    });

    const commentaire = ($("#feas-commentaire") || {}).value || "";

    // Collect aids
    const aids = [];
    document.querySelectorAll('.aids-checklist input[type="checkbox"]:checked').forEach(cb => {
      aids.push(cb.value);
    });
    const other = ($("#feas-aids-other") || {}).value || "";
    if (other.trim()) aids.push(other.trim());

    // Show loading
    body.innerHTML = `
      <div class="modal-loading">
        <div class="spinner-ring"></div>
        <span>Analyse de faisabilité en cours...</span>
      </div>
    `;
    footer.innerHTML = '';

    try {
      const r = await fetchWithTimeout(API_FEASIBILITY, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activity_name: _activityName,
          inclusion_scoring_json: _scoringData,
          profil_fonctionnel: profil,
          commentaire_court: commentaire,
          assistive_products: aids
        })
      }, 60000);

      if (!r.ok) throw new Error(`HTTP ${r.status}`);

      const data = await r.json();
      if (data.error) throw new Error(data.error);

      renderFeasibilityResult(data.result);
    } catch (err) {
      console.error("Erreur faisabilité:", err);
      body.innerHTML = `
        <div style="text-align:center; padding:30px; color:#dc2626;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size:1.5rem; margin-bottom:10px; display:block;"></i>
          <p>${escHtml(err.message)}</p>
        </div>
      `;
      footer.innerHTML = `
        <button class="btn-modal-secondary-propose" id="apt-back-form-btn">
          <i class="fa-solid fa-arrow-left"></i> Retour
        </button>
      `;
      $("#apt-back-form-btn").onclick = () => renderFeasibilityForm();
    }
  }

  // ============================================================
  //  RENDER FEASIBILITY RESULT
  // ============================================================
  function renderFeasibilityResult(result) {
    const body = $("#apt-modal-body");
    const footer = $("#apt-modal-footer");
    const title = $("#apt-modal-title");
    title.innerHTML = '<i class="fa-solid fa-clipboard-check"></i> Résultat — Faisabilité';

    // Determine status class
    let statutClass = 'ok';
    const statut = (result.statut || '').toLowerCase();
    if (statut.includes('adaptations')) statutClass = 'adaptations';
    else if (statut.includes('instruire')) statutClass = 'instruire';
    else if (statut.includes('non recommand')) statutClass = 'non-recommande';

    let html = '';

    // Status banner
    html += `<div class="feasibility-statut ${statutClass}">${escHtml(result.statut)}</div>`;

    html += '<div class="feasibility-result">';

    // Mesures déjà en place
    if (result.mesures_deja_en_place && result.mesures_deja_en_place.length) {
      html += `
        <div class="feasibility-block">
          <div class="feasibility-block-title"><i class="fa-solid fa-check-circle"></i> Mesures déjà en place</div>
          <ul class="feasibility-list positives">
            ${result.mesures_deja_en_place.map(m => `<li>${escHtml(m)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Ajouts recommandés
    if (result.ajouts_recommandes && result.ajouts_recommandes.length) {
      html += `
        <div class="feasibility-block">
          <div class="feasibility-block-title"><i class="fa-solid fa-plus-circle"></i> Ajouts recommandés</div>
          <ul class="feasibility-list warnings">
            ${result.ajouts_recommandes.map(m => `<li>${escHtml(m)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // À ajuster
    if (result.a_ajuster && result.a_ajuster.length) {
      html += `
        <div class="feasibility-block">
          <div class="feasibility-block-title"><i class="fa-solid fa-wrench"></i> À ajuster</div>
          <ul class="feasibility-list negatives">
            ${result.a_ajuster.map(m => `<li>${escHtml(m)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Points à instruire
    if (result.points_a_instruire && result.points_a_instruire.length) {
      html += `
        <div class="feasibility-block">
          <div class="feasibility-block-title"><i class="fa-solid fa-magnifying-glass"></i> Points à instruire</div>
          <ul class="feasibility-list questions">
            ${result.points_a_instruire.map(m => `<li>${escHtml(m)}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    // Risque résiduel
    if (result.risque_residuel) {
      html += `<div class="feasibility-risque"><strong>Risque résiduel :</strong> ${escHtml(result.risque_residuel)}</div>`;
    }

    // Commentaire
    if (result.commentaire) {
      html += `<div class="feasibility-commentaire"><strong>Commentaire :</strong> ${escHtml(result.commentaire)}</div>`;
    }

    html += '</div>'; // end feasibility-result

    body.innerHTML = html;

    // Footer
    footer.innerHTML = `
      <button class="btn-modal-secondary-propose" id="apt-back-scoring-btn">
        <i class="fa-solid fa-arrow-left"></i> Retour au scoring
      </button>
      <button class="btn-modal-secondary-propose" id="apt-redo-btn">
        <i class="fa-solid fa-rotate-left"></i> Nouveau profil
      </button>
      <button class="btn-modal-primary-propose" id="apt-close-final-btn">
        <i class="fa-solid fa-check"></i> Terminé
      </button>
    `;

    $("#apt-back-scoring-btn").onclick = () => renderScoringStep(_scoringData);
    $("#apt-redo-btn").onclick = () => renderFeasibilityForm();
    $("#apt-close-final-btn").onclick = () => hideModal();
  }

  // ============================================================
  //  SAVE LEVIERS → APTITUDES
  // ============================================================
  async function saveLeviers(data) {
    const btn = $("#apt-save-leviers-btn");
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enregistrement...'; }

    // Collecter tous les leviers de toutes les catégories
    const leviers = [];
    ['vision', 'auditif', 'physique', 'environnemental', 'exposition_risque'].forEach(cat => {
      if (data[cat] && Array.isArray(data[cat].leviers)) {
        data[cat].leviers.forEach(l => { if (l && l.trim()) leviers.push(l.trim()); });
      }
    });

    if (!leviers.length) {
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Sauvegarder les leviers'; }
      return;
    }

    let added = 0;
    let errors = 0;
    for (const levier of leviers) {
      try {
        const r = await fetch('/aptitudes/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ description: levier, activity_id: _activityId })
        });
        if (r.ok || r.status === 201) added++;
        else errors++;
      } catch (_) { errors++; }
    }

    // Refresh la liste d'aptitudes dans la page
    if (typeof updateAptitudes === 'function') updateAptitudes(_activityId);

    // Feedback dans le footer
    if (btn) {
      btn.disabled = false;
      if (errors === 0) {
        btn.innerHTML = `<i class="fa-solid fa-check"></i> ${added} levier${added > 1 ? 's' : ''} ajouté${added > 1 ? 's' : ''}`;
        btn.style.background = '#d1fae5';
        btn.style.color = '#065f46';
        btn.style.borderColor = '#6ee7b7';
      } else {
        btn.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${added} ajouté${added > 1 ? 's' : ''}, ${errors} erreur${errors > 1 ? 's' : ''}`;
        btn.style.background = '#fef3c7';
        btn.style.color = '#92400e';
      }
    }
  }

  // ============================================================
  //  MAIN FLOW
  // ============================================================
  async function showProposedAptitudes(activityId) {
    _activityId = activityId;
    safeShowSpinner();
    const overlay = ensureModal();
    const body = $("#apt-modal-body", overlay);
    const footer = $("#apt-modal-footer", overlay);

    body.innerHTML = `
      <div class="modal-loading">
        <div class="spinner-ring"></div>
        <span>Analyse inclusion en cours...</span>
      </div>
    `;
    footer.innerHTML = '';
    showModal();

    try {
      // Fetch activity details
      let activityData = null;
      try {
        const rd = await fetchWithTimeout(`/activities/${activityId}/details`, {}, 15000);
        if (rd.ok) activityData = await rd.json();
      } catch (e) {
        console.warn("Récupération détails activité ignorée :", e);
      }

      _activityName = activityData?.name || activityData?.title || "Activité";

      const proposeBody = activityData
        ? { activity_id: activityId, ...activityData }
        : { activity_id: activityId };

      const r = await fetchWithTimeout(API_PROPOSE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(proposeBody)
      }, 60000);

      if (!r.ok) throw new Error(`HTTP ${r.status}`);

      const data = await r.json();
      if (data.error) throw new Error(data.error);

      _scoringData = data.proposals;

      // Check if proposals is a proper scoring object
      if (_scoringData && typeof _scoringData === 'object' && !Array.isArray(_scoringData)) {
        renderScoringStep(_scoringData);
      } else {
        // Fallback : old format (unlikely but just in case)
        body.innerHTML = `<p style="color:#64748b; padding:20px; text-align:center;">
          Le format de réponse n'est pas reconnu. Veuillez réessayer.
        </p>`;
        footer.innerHTML = `<button class="btn-modal-secondary-propose" onclick="document.getElementById('proposeAptitudesModalOverlay').style.display='none'">
          <i class="fa-solid fa-xmark"></i> Fermer
        </button>`;
      }
    } catch (err) {
      console.error("Erreur showProposedAptitudes:", err);
      body.innerHTML = `
        <div style="text-align:center; padding:30px; color:#dc2626;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size:1.5rem; margin-bottom:10px; display:block;"></i>
          <p>${escHtml(err.message)}</p>
        </div>
      `;
      footer.innerHTML = `<button class="btn-modal-secondary-propose" onclick="document.getElementById('proposeAptitudesModalOverlay').style.display='none'">
        <i class="fa-solid fa-xmark"></i> Fermer
      </button>`;
    } finally {
      safeHideSpinner();
    }
  }

  // Global aliases
  window.showProposedAptitudes = showProposedAptitudes;
  window.openProposeAptitudes  = showProposedAptitudes;
  window.proposeAptitudes      = showProposedAptitudes;

  // Delegation
  document.addEventListener("click", (e) => {
    const btn = e.target.closest('[data-action="propose-aptitudes"]');
    if (btn) {
      const activityId = parseInt(btn.dataset.activityId, 10);
      if (!isNaN(activityId)) showProposedAptitudes(activityId);
    }
  });
})();
