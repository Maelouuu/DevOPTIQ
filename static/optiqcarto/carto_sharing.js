'use strict';

/* ══════════════════════════════════════════════════
   OptiqCarto — carto COMMUNE : proposer, examiner
   ══════════════════════════════════════════════════
   Une carto commune est UNE ligne travaillée par plusieurs comptes. Deux
   régimes selon le statut :

     champion / administrateur → « Sauvegarder » écrit directement ;
     tout autre compte         → « Sauvegarder » devient « Proposer », et la
                                 version part à l'examen d'un champion.

   Ce fichier est chargé APRÈS editor.js et se contente d'habiller ce qui existe
   (bouton Sauvegarder, raccourci Ctrl+S) : rien de la gouvernance ne vit dans
   editor.js, qui reste l'éditeur et rien d'autre.

   ⚠️ Le masquage n'est pas une sécurité : /cartography/api/save refuse aussi
   côté serveur, avec le code « must_propose » que l'on rattrape ici. */

(function () {
  const GOV = window.OPTIQCARTO_GOV || {};
  const L = (key, ...subs) => {
    const s = (window.OPTIQ_I18N && window.OPTIQ_I18N[key]) || key;
    return subs.length ? s.replace('%s', subs[0]) : s;
  };
  const API = window.OPTIQCARTO_API_BASE || '/cartography';
  const $id = (id) => document.getElementById(id);

  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  const peutArbitrer = !!GOV.can_review;
  const doitProposer = !!GOV.must_propose;

  // Rien à faire sur une carto privée : l'éditeur garde son comportement.
  if (!GOV.is_shared && !peutArbitrer) return;

  /* ── Bandeau ────────────────────────────────────────────────────────── */

  function poseBandeau() {
    const bar = $id('carto-gov-bar');
    if (!bar || !GOV.is_shared) return;
    bar.style.display = 'flex';
    const txt = $id('gov-bar-text');
    if (txt) {
      txt.textContent = doitProposer ? L('change.propose_hint') : L('access.shared_hint');
    }
    // Le canevas descend d'autant : sans ça le bandeau recouvrirait la carto.
    document.body.classList.add('has-gov-bar');

    if (peutArbitrer) {
      const btn = $id('gov-review-btn');
      if (btn) {
        btn.style.display = '';
        btn.addEventListener('click', ouvrirExamen);
      }
      rafraichirCompteur();
    }
  }

  async function rafraichirCompteur() {
    try {
      const res = await fetch(`${API}/api/changes?status=pending`);
      const data = await res.json();
      const n = (data.requests || []).filter(r => !r.is_mine).length;
      const pastille = $id('gov-review-count');
      if (pastille) {
        pastille.textContent = n;
        pastille.classList.toggle('is-zero', n === 0);
      }
    } catch (_) { /* le bandeau reste utilisable sans le compteur */ }
  }

  /* ── Proposer ───────────────────────────────────────────────────────── */

  function ouvrirProposition() {
    const modal = $id('propose-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    const titre = $id('propose-title');
    if (titre) { titre.value = ''; titre.focus(); }
    const msg = $id('propose-message');
    if (msg) msg.value = '';
  }

  function fermerProposition() {
    const modal = $id('propose-modal');
    if (modal) modal.style.display = 'none';
  }

  async function envoyerProposition() {
    const btn = $id('propose-send');
    const avant = btn ? btn.innerHTML : null;
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
    try {
      const res = await fetch(`${API}/api/changes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_id: GOV.entity_id,
          title: ($id('propose-title')?.value || '').trim(),
          message: ($id('propose-message')?.value || '').trim(),
          diagram: (typeof window.getCartoState === 'function' ? window.getCartoState() : null),
        }),
      });
      const data = await res.json();
      if (data.error) { alert(data.error); return; }
      fermerProposition();
      // La proposition EST l'enregistrement de son travail : on ne doit plus
      // avertir « modifications non enregistrées » en quittant la page.
      if (typeof window.markCartoSaved === 'function') window.markCartoSaved();
      if (typeof window.showToast === 'function') window.showToast(L('change.sent'));
      else alert(L('change.sent'));
    } catch (_) {
      alert(L('editor.toast.error_network') || 'Erreur réseau');
    } finally {
      if (btn) { btn.disabled = false; if (avant !== null) btn.innerHTML = avant; }
    }
  }

  /* ── Examiner ───────────────────────────────────────────────────────── */

  function ouvrirExamen() {
    const modal = $id('review-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    chargerListe();
  }

  function fermerExamen() {
    const modal = $id('review-modal');
    if (modal) modal.style.display = 'none';
  }

  const LIBELLE_STATUT = {
    pending: 'change.status_pending',
    approved: 'change.status_approved',
    rejected: 'change.status_rejected',
  };

  function dateCourte(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString(undefined,
        { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch (_) { return iso.slice(0, 10); }
  }

  async function chargerListe() {
    const body = $id('review-body');
    if (!body) return;
    body.innerHTML = '<p class="gov-loading"><i class="fa-solid fa-spinner fa-spin"></i></p>';
    try {
      const res = await fetch(`${API}/api/changes?entity_id=${GOV.entity_id}`);
      const data = await res.json();
      if (data.error) { body.innerHTML = `<p class="gov-error">${esc(data.error)}</p>`; return; }

      const liste = data.requests || [];
      if (!liste.length) {
        body.innerHTML = `<p class="gov-empty">${esc(L('change.none'))}</p>`;
        return;
      }
      body.innerHTML = `<div class="gov-list">${liste.map(carte).join('')}</div>`;
      body.querySelectorAll('.gov-item').forEach(el => {
        el.addEventListener('click', (e) => {
          if (e.target.closest('button')) return;
          ouvrirDetail(parseInt(el.dataset.id, 10));
        });
      });
    } catch (_) {
      body.innerHTML = `<p class="gov-error">${esc(L('change.load_error'))}</p>`;
    }
  }

  function carte(r) {
    return `
      <article class="gov-item gov-item--${esc(r.status)}" data-id="${r.id}">
        <div class="gov-item-head">
          <span class="gov-item-title">${esc(r.title || L('change.propose_title'))}</span>
          <span class="gov-item-status gov-item-status--${esc(r.status)}">${
            esc(L(LIBELLE_STATUT[r.status] || r.status))}</span>
        </div>
        <div class="gov-item-meta">
          <span>${esc(r.is_mine ? L('change.mine') : L('change.by', r.author))}</span>
          <span class="gov-item-date">${esc(dateCourte(r.created_at))}</span>
        </div>
        ${r.message ? `<p class="gov-item-msg">${esc(r.message)}</p>` : ''}
      </article>`;
  }

  function ligneResume(n, cle, exemples) {
    if (!n) return '';
    const detail = (exemples && exemples.length)
      ? ` <span class="gov-sum-names">${esc(exemples.slice(0, 4).join(', '))}${
          exemples.length > 4 ? '…' : ''}</span>`
      : '';
    // Singulier / pluriel plutôt que « ajoutée(s) » : c'est la ligne qu'on lit
    // pour comprendre la proposition, elle doit se lire d'une traite.
    return `<li><strong>${n}</strong> ${esc(L(n > 1 ? cle + '_p' : cle))}${detail}</li>`;
  }

  function resumeHtml(s) {
    if (!s) return '';
    const lignes = [
      ligneResume(s.added.length, 'change.added', s.added),
      ligneResume(s.removed.length, 'change.removed', s.removed),
      ligneResume(s.renamed.length, 'change.renamed',
        s.renamed.map(r => `${r.from} → ${r.to}`)),
      ligneResume(s.moved.length, 'change.moved', s.moved),
      ligneResume(s.links_added, 'change.links_added'),
      ligneResume(s.links_removed, 'change.links_removed'),
    ].filter(Boolean).join('');
    return lignes
      ? `<ul class="gov-sum">${lignes}</ul>`
      : `<p class="gov-empty">${esc(L('change.nothing'))}</p>`;
  }

  async function ouvrirDetail(id) {
    const body = $id('review-body');
    if (!body) return;
    body.innerHTML = '<p class="gov-loading"><i class="fa-solid fa-spinner fa-spin"></i></p>';
    try {
      const res = await fetch(`${API}/api/changes/${id}`);
      const r = await res.json();
      if (r.error) { body.innerHTML = `<p class="gov-error">${esc(r.error)}</p>`; return; }

      body.innerHTML = `
        <button class="gov-back" id="gov-back"><i class="fa-solid fa-chevron-left"></i> ${
          esc(L('change.back_to_list'))}</button>
        <article class="gov-detail">
          <h4 class="gov-detail-title">${esc(r.title || L('change.propose_title'))}</h4>
          <div class="gov-item-meta">
            <span>${esc(r.is_mine ? L('change.mine') : L('change.by', r.author))}</span>
            <span class="gov-item-date">${esc(dateCourte(r.created_at))}</span>
          </div>
          ${r.message ? `<p class="gov-detail-msg">${esc(r.message)}</p>` : ''}
          <h5 class="gov-sum-title">${esc(L('change.summary_title'))}</h5>
          ${resumeHtml(r.summary)}
          ${r.can_review ? `
            <input type="text" class="gov-comment" id="gov-comment"
                   placeholder="${esc(L('change.comment_ph'))}">
            <div class="gov-card-actions">
              <button class="gov-btn gov-btn--danger" id="gov-reject">
                <i class="fa-solid fa-xmark"></i> ${esc(L('change.reject'))}
              </button>
              <button class="gov-btn gov-btn--primary" id="gov-approve">
                <i class="fa-solid fa-check"></i> ${esc(L('change.approve'))}
              </button>
            </div>` : (r.is_mine && r.status === 'pending' ? `
            <div class="gov-card-actions">
              <button class="gov-btn gov-btn--ghost" id="gov-withdraw">
                <i class="fa-solid fa-rotate-left"></i> ${esc(L('change.withdraw'))}
              </button>
            </div>` : '')}
        </article>`;

      $id('gov-back')?.addEventListener('click', chargerListe);
      $id('gov-approve')?.addEventListener('click', () => trancher(id, 'approve'));
      $id('gov-reject')?.addEventListener('click', () => trancher(id, 'reject'));
      $id('gov-withdraw')?.addEventListener('click', () => retirer(id));
    } catch (_) {
      body.innerHTML = `<p class="gov-error">${esc(L('change.load_error'))}</p>`;
    }
  }

  async function trancher(id, action) {
    const btn = $id(action === 'approve' ? 'gov-approve' : 'gov-reject');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
    try {
      const res = await fetch(`${API}/api/changes/${id}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: ($id('gov-comment')?.value || '').trim() }),
      });
      const data = await res.json();
      if (data.error) { alert(data.error); return; }
      if (data.sync_warning) alert(data.sync_warning);
      await rafraichirCompteur();
      if (action === 'approve') {
        // La carto de référence vient de changer : la recharger évite d'écraser
        // la modification qu'on vient d'appliquer avec l'état affiché à l'écran.
        window.location.reload();
        return;
      }
      chargerListe();
    } catch (_) {
      alert(L('change.load_error'));
    }
  }

  async function retirer(id) {
    try {
      const res = await fetch(`${API}/api/changes/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.error) { alert(data.error); return; }
      chargerListe();
    } catch (_) { alert(L('change.load_error')); }
  }

  /* ── Détournement du bouton Sauvegarder ─────────────────────────────── */

  function habilleSauvegarde() {
    if (!doitProposer) return;
    const btn = $id('btn-save');
    if (btn) {
      const libelle = btn.querySelector('span');
      if (libelle) libelle.textContent = L('change.propose');
      btn.title = L('change.propose_hint');
      btn.classList.add('is-propose');
      const icone = btn.querySelector('i');
      if (icone) icone.className = 'fa-solid fa-code-pull-request';
      // capture: on passe AVANT le gestionnaire d'editor.js, qui appellerait
      // /api/save — refusé côté serveur, et l'utilisateur n'aurait qu'une erreur.
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopImmediatePropagation();
        ouvrirProposition();
      }, true);
    }
    // Ctrl+S mène au même endroit que le bouton.
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        e.stopImmediatePropagation();
        ouvrirProposition();
      }
    }, true);
  }

  function demarrer() {
    poseBandeau();
    habilleSauvegarde();
    $id('propose-cancel')?.addEventListener('click', fermerProposition);
    $id('propose-send')?.addEventListener('click', envoyerProposition);
    $id('review-close')?.addEventListener('click', fermerExamen);
    $id('propose-modal')?.addEventListener('click', (e) => {
      if (e.target.id === 'propose-modal') fermerProposition();
    });
    $id('review-modal')?.addEventListener('click', (e) => {
      if (e.target.id === 'review-modal') fermerExamen();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
