// static/js/share.js
//
// Console de partage — tout le processus sur un seul écran.
//
// Avant, régler l'accès se faisait sur la carte des activités, mais dire QUI
// tient un rôle se faisait sur la page Rôles : deux moitiés de la même décision,
// à deux endroits. Ici on coche le rôle ET on met les gens dedans, on voit qui
// accède au total, et on arbitre les modifications proposées.

(function () {
  const CTX = window.SHARE_PAGE || { entities: [] };
  const L = (k) => (window.SHARE_L && window.SHARE_L[k]) || k;
  const $ = (s) => document.querySelector(s);

  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

  let etat = null;        // dernière réponse de /api/access/<id>/roles
  let entityId = null;
  let roleEnCours = null; // rôle dont on choisit les titulaires

  /* ── Réseau ───────────────────────────────────────────────────────────── */

  async function getJSON(url) {
    const r = await fetch(url);
    return r.json();
  }

  async function postJSON(url, corps) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps || {}),
    });
    return r.json();
  }

  /* ── 1. Accès et rôles ────────────────────────────────────────────────── */

  async function charger() {
    if (!entityId) return;
    $('#share-roles').innerHTML = squelette();
    try {
      const data = await getJSON(`/cartography/api/access/${entityId}/roles`);
      if (data.error) { $('#share-roles').innerHTML = erreur(data.error); return; }
      etat = data;
      rendreEtat();
      rendreRoles();
      rendrePortee();
    } catch (_) {
      $('#share-roles').innerHTML = erreur(L('loadError'));
    }
    chargerChangements();
  }

  const squelette = () => '<p class="share-loading"><i class="fa-solid fa-spinner fa-spin"></i></p>';
  const erreur = (m) => `<p class="share-error">${esc(m)}</p>`;

  function rendreEtat() {
    const gele = !etat.can_manage_access;
    const cb = $('#share-shared-cb');
    cb.checked = !!etat.is_shared;
    cb.disabled = gele;
    $('#share-switch-wrap').classList.toggle('is-locked', gele);
    $('#share-readonly').classList.toggle('hidden', !gele);
    $('#share-save').style.display = gele ? 'none' : '';
    majBandeau();
  }

  function majBandeau() {
    const commune = $('#share-shared-cb').checked;
    $('#share-switch-hint').textContent = commune ? L('sharedHint') : L('privateHint');
    $('#share-roles-block').classList.toggle('hidden', !commune);
    const pastille = $('#share-state');
    pastille.textContent = commune ? L('badgeShared') : L('badgePrivate');
    pastille.classList.toggle('pg-pill--accent', commune);
  }

  function rendreRoles() {
    const gele = !etat.can_manage_access;
    const roles = etat.roles || [];
    const hote = $('#share-roles');
    if (!roles.length) {
      hote.innerHTML = `<p class="pg-empty">${esc(L('noRoles'))}</p>`;
      majOuvertATous();
      return;
    }
    hote.innerHTML = roles.map(r => `
      <div class="share-role${r.granted ? ' is-granted' : ''}" data-role="${r.id}">
        <label class="share-role-head">
          <input type="checkbox" class="share-role-cb" value="${r.id}"
                 ${r.granted ? 'checked' : ''} ${gele ? 'disabled' : ''}>
          <span class="share-role-name">${esc(r.name)}</span>
        </label>
        <div class="share-role-holders">
          ${r.holders.length
            ? r.holders.map(h => `
              <span class="share-holder" title="${esc(h.email)}">
                ${esc(h.name)}
                ${gele ? '' : `<button type="button" class="share-holder-x"
                     data-role="${r.id}" data-user="${h.id}"
                     title="${esc(L('removeHolder'))}"><i class="fa-solid fa-xmark"></i></button>`}
              </span>`).join('')
            : `<span class="share-nobody">${esc(L('noHolder'))}</span>`}
          ${gele ? '' : `<button type="button" class="share-add-holder" data-role="${r.id}">
              <i class="fa-solid fa-plus"></i> ${esc(L('addHolder'))}</button>`}
        </div>
      </div>`).join('');

    hote.querySelectorAll('.share-role-cb').forEach(cb =>
      cb.addEventListener('change', () => {
        cb.closest('.share-role').classList.toggle('is-granted', cb.checked);
        majOuvertATous();
      }));
    hote.querySelectorAll('.share-add-holder').forEach(b =>
      b.addEventListener('click', () => ouvrirSelecteur(parseInt(b.dataset.role, 10))));
    hote.querySelectorAll('.share-holder-x').forEach(b =>
      b.addEventListener('click', () => majTitulaires(
        parseInt(b.dataset.role, 10), { remove: [parseInt(b.dataset.user, 10)] })));

    majOuvertATous();
  }

  function majOuvertATous() {
    const aucun = ![...document.querySelectorAll('.share-role-cb')].some(c => c.checked);
    $('#share-openall').classList.toggle('hidden', !aucun || !$('#share-shared-cb').checked);
  }

  async function enregistrerAcces() {
    const btn = $('#share-save');
    const avant = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    try {
      const data = await postJSON(`/cartography/api/access/${entityId}`, {
        is_shared: $('#share-shared-cb').checked,
        role_ids: [...document.querySelectorAll('.share-role-cb:checked')]
          .map(c => parseInt(c.value, 10)),
      });
      if (data.error) { alert(data.error); return; }
      annoncer(L('saved'));
      await charger();
    } catch (_) {
      alert(L('netError'));
    } finally {
      btn.disabled = false;
      btn.innerHTML = avant;
    }
  }

  /* ── Titulaires d'un rôle ─────────────────────────────────────────────── */

  async function majTitulaires(roleId, delta) {
    try {
      const data = await postJSON(
        `/cartography/api/access/${entityId}/roles/${roleId}/holders`, delta);
      if (data.error) { alert(data.error); return; }
      const role = (etat.roles || []).find(r => r.id === roleId);
      if (role) role.holders = data.holders;
      rendreRoles();
      rafraichirPortee();
    } catch (_) { alert(L('netError')); }
  }

  function ouvrirSelecteur(roleId) {
    roleEnCours = (etat.roles || []).find(r => r.id === roleId);
    if (!roleEnCours) return;
    $('#share-picker-title').textContent = roleEnCours.name;
    const champ = $('#share-picker-search');
    champ.value = '';
    champ.placeholder = L('searchAccount');
    rendreSelecteur('');
    $('#share-picker-modal').classList.remove('hidden');
    champ.focus();
  }

  function rendreSelecteur(filtre) {
    const dedans = new Set(roleEnCours.holders.map(h => h.id));
    const q = (filtre || '').toLowerCase();
    const lignes = (etat.accounts || [])
      .filter(u => !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))
      .map(u => `
        <label class="share-pick${dedans.has(u.id) ? ' is-in' : ''}">
          <input type="checkbox" value="${u.id}" ${dedans.has(u.id) ? 'checked' : ''}>
          <span class="share-pick-name">${esc(u.name)}</span>
          <span class="share-pick-mail">${esc(u.email)}</span>
        </label>`).join('');
    $('#share-picker-list').innerHTML = lignes || `<p class="pg-empty">—</p>`;
    $('#share-picker-list').querySelectorAll('input').forEach(cb =>
      cb.addEventListener('change', () => {
        const uid = parseInt(cb.value, 10);
        majTitulaires(roleEnCours.id,
          cb.checked ? { add: [uid] } : { remove: [uid] });
      }));
  }

  /* ── 2. Qui accède au total ───────────────────────────────────────────── */

  const MOTIF = {
    owner: 'reasonOwner', admin: 'reasonAdmin', champion: 'reasonChampion',
    all: 'reasonAll', role: 'reasonRole',
  };

  function rendrePortee() {
    const portee = etat.reach || [];
    $('#share-reach-count').textContent = portee.length;
    $('#share-reach').innerHTML = portee.length ? `
      <table class="pg-table share-reach-table">
        <tbody>
          ${portee.map(u => `
            <tr>
              <td><strong>${esc(u.name)}</strong><span class="share-reach-mail">${esc(u.email)}</span></td>
              <td class="share-reach-why">
                <span class="pg-pill ${u.reason === 'role' ? 'pg-pill--accent' : ''}">${esc(L(MOTIF[u.reason] || u.reason))}</span>
                ${u.roles.length ? `<span class="share-reach-roles">${esc(u.roles.join(', '))}</span>` : ''}
              </td>
            </tr>`).join('')}
        </tbody>
      </table>` : `<p class="pg-empty">${esc(L('reachEmpty'))}</p>`;
  }

  async function rafraichirPortee() {
    try {
      const data = await getJSON(`/cartography/api/access/${entityId}/roles`);
      if (!data.error) { etat.reach = data.reach; rendrePortee(); }
    } catch (_) { /* la portée n'est qu'un contrôle : on ne casse pas l'écran */ }
  }

  /* ── 3. Modifications proposées ───────────────────────────────────────── */

  const STATUT = {
    pending: 'statusPending', approved: 'statusApproved', rejected: 'statusRejected',
  };

  function dateCourte(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString(undefined,
        { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch (_) { return iso.slice(0, 10); }
  }

  async function chargerChangements() {
    const hote = $('#share-changes');
    hote.innerHTML = squelette();
    try {
      const data = await getJSON(`/cartography/api/changes?entity_id=${entityId}`);
      if (data.error) { hote.innerHTML = erreur(data.error); return; }
      const liste = data.requests || [];
      const attente = liste.filter(r => r.status === 'pending').length;
      const pastille = $('#share-changes-count');
      pastille.classList.toggle('hidden', attente === 0);
      pastille.textContent = attente;

      if (!liste.length) {
        hote.innerHTML = `<p class="pg-empty">${esc(L('changesNone'))}</p>`;
        return;
      }
      hote.innerHTML = `<div class="share-changes">${liste.map(carte).join('')}</div>`;
      hote.querySelectorAll('.share-change').forEach(el =>
        el.addEventListener('click', (e) => {
          if (e.target.closest('button')) return;
          ouvrirChangement(parseInt(el.dataset.id, 10));
        }));
    } catch (_) {
      hote.innerHTML = erreur(L('loadError'));
    }
  }

  function carte(r) {
    return `
      <article class="share-change share-change--${esc(r.status)}" data-id="${r.id}">
        <div class="share-change-head">
          <span class="share-change-title">${esc(r.title || L('proposeTitle'))}</span>
          <span class="pg-pill ${r.status === 'pending' ? 'pg-pill--warn'
            : r.status === 'approved' ? 'pg-pill--ok' : 'pg-pill--danger'}">${
            esc(L(STATUT[r.status] || r.status))}</span>
        </div>
        <div class="share-change-meta">
          <span>${esc(r.is_mine ? L('changeMine') : L('changeBy').replace('%s', r.author))}</span>
          <span class="share-change-date">${esc(dateCourte(r.created_at))}</span>
        </div>
        ${r.message ? `<p class="share-change-msg">${esc(r.message)}</p>` : ''}
      </article>`;
  }

  function ligneResume(n, cle, exemples) {
    if (!n) return '';
    const detail = (exemples && exemples.length)
      ? ` <span class="share-sum-names">${esc(exemples.slice(0, 4).join(', '))}${
          exemples.length > 4 ? '…' : ''}</span>` : '';
    return `<li><strong>${n}</strong> ${esc(L(n > 1 ? cle + '_p' : cle))}${detail}</li>`;
  }

  function resumeHtml(s) {
    if (!s) return '';
    const lignes = [
      ligneResume(s.added.length, 'added', s.added),
      ligneResume(s.removed.length, 'removed', s.removed),
      ligneResume(s.renamed.length, 'renamed', s.renamed.map(r => `${r.from} → ${r.to}`)),
      ligneResume(s.moved.length, 'moved', s.moved),
      ligneResume(s.links_added, 'links_added'),
      ligneResume(s.links_removed, 'links_removed'),
    ].filter(Boolean).join('');
    return lignes ? `<ul class="share-sum">${lignes}</ul>`
                  : `<p class="pg-empty">${esc(L('nothing'))}</p>`;
  }

  async function ouvrirChangement(id) {
    const hote = $('#share-changes');
    hote.innerHTML = squelette();
    try {
      const r = await getJSON(`/cartography/api/changes/${id}`);
      if (r.error) { hote.innerHTML = erreur(r.error); return; }
      hote.innerHTML = `
        <button class="pg-btn pg-btn--ghost pg-btn--sm share-back" id="share-back">
          <i class="fa-solid fa-chevron-left"></i> ${esc(L('back'))}
        </button>
        <h3 class="share-detail-title">${esc(r.title || L('proposeTitle'))}</h3>
        <div class="share-change-meta">
          <span>${esc(r.is_mine ? L('changeMine') : L('changeBy').replace('%s', r.author))}</span>
          <span class="share-change-date">${esc(dateCourte(r.created_at))}</span>
        </div>
        ${r.message ? `<p class="share-detail-msg">${esc(r.message)}</p>` : ''}
        <span class="pg-label share-sum-title">${esc(L('summaryTitle'))}</span>
        ${resumeHtml(r.summary)}
        ${r.can_review ? `
          <input type="text" class="pg-input share-comment" id="share-comment"
                 placeholder="${esc(L('commentPh'))}">
          <div class="share-detail-actions">
            <button class="pg-btn pg-btn--danger" id="share-reject">
              <i class="fa-solid fa-xmark"></i> ${esc(L('reject'))}
            </button>
            <button class="pg-btn pg-btn--accent" id="share-approve">
              <i class="fa-solid fa-check"></i> ${esc(L('approve'))}
            </button>
          </div>` : ''}`;
      $('#share-back').addEventListener('click', chargerChangements);
      $('#share-approve')?.addEventListener('click', () => trancher(id, 'approve'));
      $('#share-reject')?.addEventListener('click', () => trancher(id, 'reject'));
    } catch (_) {
      hote.innerHTML = erreur(L('loadError'));
    }
  }

  async function trancher(id, action) {
    const btn = $(action === 'approve' ? '#share-approve' : '#share-reject');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
    try {
      const data = await postJSON(`/cartography/api/changes/${id}/${action}`,
        { comment: ($('#share-comment')?.value || '').trim() });
      if (data.error) { alert(data.error); return; }
      if (data.sync_warning) alert(data.sync_warning);
      annoncer(action === 'approve' ? L('approved') : L('rejected'));
      chargerChangements();
    } catch (_) { alert(L('netError')); }
  }

  /* ── Retour visuel discret ────────────────────────────────────────────── */

  function annoncer(texte) {
    let t = $('#share-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'share-toast';
      t.className = 'share-toast';
      document.body.appendChild(t);
    }
    t.textContent = texte;
    t.classList.add('is-on');
    clearTimeout(annoncer._h);
    annoncer._h = setTimeout(() => t.classList.remove('is-on'), 2600);
  }

  /* ── Démarrage ────────────────────────────────────────────────────────── */

  function demarrer() {
    const select = $('#share-entity');
    if (!select) return;                        // aucune carto accessible
    entityId = parseInt(select.value, 10);
    select.addEventListener('change', () => {
      entityId = parseInt(select.value, 10);
      charger();
    });
    $('#share-shared-cb').addEventListener('change', () => { majBandeau(); majOuvertATous(); });
    $('#share-save').addEventListener('click', enregistrerAcces);
    $('#share-picker-close').addEventListener('click',
      () => $('#share-picker-modal').classList.add('hidden'));
    $('#share-picker-modal').addEventListener('click', (e) => {
      if (e.target.id === 'share-picker-modal') e.currentTarget.classList.add('hidden');
    });
    $('#share-picker-search').addEventListener('input',
      (e) => rendreSelecteur(e.target.value));
    charger();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
