// static/js/share.js
//
// Console de partage — tout le processus, et de quoi le comprendre en le voyant.
//
// Trois idées la portent :
//   · on CHOISIT une carto en la voyant (vignette dessinée d'après la vraie
//     carte : ses bandes, ses activités), pas dans une liste déroulante ;
//   · l'accès se règle et se VÉRIFIE au même endroit — les rôles avec leurs
//     titulaires, puis les personnes qui ouvrent réellement la carto ;
//   · chaque bloc mène ailleurs quand c'est utile (la carte, l'éditeur, les
//     comptes) : on n'y arrive pas dans un cul-de-sac.

(function () {
  const CTX = window.SHARE_PAGE || {};
  const L = (k) => (window.SHARE_L && window.SHARE_L[k]) || k;
  const $ = (s, r = document) => r.querySelector(s);

  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

  let cartes = [];        // aperçus de toutes les cartos accessibles
  let etat = null;        // détail de la carto choisie
  let entityId = CTX.activeId || null;
  // La fenêtre de gestion sert des DEUX côtés : { mode: 'role'|'person', cible }
  let fenetre = null;

  /* ── Réseau ───────────────────────────────────────────────────────────── */

  const getJSON = (url) => fetch(url).then(r => r.json());
  const postJSON = (url, corps) => fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corps || {}),
  }).then(r => r.json());

  /* ── Petits objets d'affichage ────────────────────────────────────────── */

  const initiales = (nom) => (nom || '?').trim().split(/\s+/)
    .slice(0, 2).map(m => m[0]).join('').toUpperCase();

  // Une teinte stable par personne : deux collègues ne se confondent pas, et la
  // couleur ne change pas d'un chargement à l'autre.
  const TEINTES = [198, 262, 340, 24, 152, 288, 8, 174, 42, 316];
  function teinte(cle) {
    let h = 0;
    for (const c of String(cle)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return TEINTES[h % TEINTES.length];
  }

  function avatar(personne, taille) {
    const t = teinte(personne.email || personne.name);
    return `<span class="sh-av${taille ? ' sh-av--' + taille : ''}"
      style="--av-h:${t}" title="${esc(personne.name)} · ${esc(personne.email)}"
      >${esc(initiales(personne.name))}</span>`;
  }

  // La vignette EST la carto : le serveur la rend en SVG (bandes, tracés réels
  // des flèches, activités). Deux cartos ne se ressemblent plus.
  function vignette(carte, classe) {
    if (!carte || !carte.has_thumbnail) {
      return `<div class="sh-thumb sh-thumb--empty ${classe || ''}">
        <i class="fa-solid fa-diagram-project"></i>
        <span>${esc(L('emptyMap'))}</span></div>`;
    }
    return `<div class="sh-thumb ${classe || ''}">
      <img src="/cartography/api/access/${carte.id}/thumbnail.svg"
           alt="${esc(carte.name || '')}" loading="lazy">
    </div>`;
  }

  /* ── Galerie des cartos ───────────────────────────────────────────────── */

  async function chargerGalerie() {
    const hote = $('#sh-gallery-list');
    hote.innerHTML = '<div class="sh-skeleton"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    try {
      const data = await getJSON('/cartography/api/access/previews');
      if (data.error) { hote.innerHTML = erreur(data.error); return; }
      cartes = data.maps || [];
      if (!cartes.length) {
        hote.innerHTML = `<p class="sh-empty">${esc(L('reachEmpty'))}</p>`;
        $('#sh-main').innerHTML = '';
        return;
      }
      if (!cartes.some(c => c.id === entityId)) entityId = cartes[0].id;
      rendreGalerie();
      charger();
    } catch (_) {
      hote.innerHTML = erreur(L('loadError'));
    }
  }

  // Une carto est bien plus HAUTE que large : en pleine largeur de carte elle
  // se recadrait en un bandeau de couleurs, et toutes les lignes se
  // ressemblaient. En vignette portrait à gauche du nom, on voit la silhouette
  // entière de la carte — c'est elle qui distingue deux cartographies.
  function rendreGalerie() {
    $('#sh-gallery-list').innerHTML = cartes.map(c => `
      <button type="button" class="sh-map${c.id === entityId ? ' is-active' : ''}"
              data-id="${c.id}">
        ${vignette(c, 'sh-thumb--row')}
        <span class="sh-map-body">
          <span class="sh-map-name">${esc(c.name)}</span>
          <span class="sh-map-meta">
            <span class="sh-tag${c.is_shared ? ' sh-tag--shared' : ''}">
              <i class="fa-solid ${c.is_shared ? 'fa-users' : 'fa-lock'}"></i>
              ${esc(c.is_shared ? L('badgeShared') : L('badgePrivate'))}
            </span>
            <span class="sh-map-count">${c.activities} ${esc(L('activities'))}</span>
          </span>
        </span>
        <i class="fa-solid fa-chevron-right sh-map-chev"></i>
      </button>`).join('');

    $('#sh-gallery-list').querySelectorAll('.sh-map').forEach(b =>
      b.addEventListener('click', () => {
        entityId = parseInt(b.dataset.id, 10);
        rendreGalerie();
        charger();
        history.replaceState(null, '', `/share/?entity_id=${entityId}`);
      }));
  }

  /* ── La carto choisie ─────────────────────────────────────────────────── */

  const squelette = () => '<div class="sh-skeleton"><i class="fa-solid fa-spinner fa-spin"></i></div>';
  const erreur = (m) => `<p class="sh-error">${esc(m)}</p>`;

  async function charger() {
    if (!entityId) return;
    $('#sh-main').innerHTML = squelette();
    try {
      const data = await getJSON(`/cartography/api/access/${entityId}/roles`);
      if (data.error) { $('#sh-main').innerHTML = erreur(data.error); return; }
      etat = data;
      etat.changes = await getJSON(`/cartography/api/changes?entity_id=${entityId}`)
        .catch(() => ({ requests: [] }));
      rendreMain();
    } catch (_) {
      $('#sh-main').innerHTML = erreur(L('loadError'));
    }
  }

  function carteCourante() {
    return cartes.find(c => c.id === entityId) || {};
  }

  function rendreMain() {
    const c = carteCourante();
    const gele = !etat.can_manage_access;
    const attente = (etat.changes.requests || []).filter(r => r.status === 'pending').length;

    $('#sh-main').innerHTML = `
      ${enTete(c, gele)}
      ${tuiles(attente)}
      ${blocAcces(gele)}
      ${blocPortee()}
      ${blocChangements(attente)}`;

    // Les morceaux arrivent l'un après l'autre : on suit l'ordre de lecture
    // au lieu de recevoir la page d'un bloc.
    // ⚠️ Onglet en arrière-plan : le navigateur met les animations en pause, et
    // une entrée qui PART d'opacité 0 laisserait la page blanche jusqu'au retour
    // sur l'onglet. On n'anime donc que si la page est réellement visible.
    if (document.visibilityState === 'visible') {
      [...$('#sh-main').children].forEach((el, i) => {
        el.style.setProperty('--rang', i);
        el.classList.add('sh-enters');
      });
    }

    brancherEnTete(gele);
    brancherTuiles();
    brancherRoles(gele);
    brancherPersonnes(gele);
    brancherChangements();
  }

  /* ── En-tête de la carto ──────────────────────────────────────────────── */

  function enTete(c, gele) {
    const commune = !!etat.is_shared;
    return `
    <section class="sh-hero${commune ? ' is-shared' : ''}">
      ${vignette(c, 'sh-thumb--hero')}
      <div class="sh-hero-body">
        <span class="sh-tag${commune ? ' sh-tag--shared' : ''}">
          <i class="fa-solid ${commune ? 'fa-users' : 'fa-lock'}"></i>
          ${esc(commune ? L('badgeShared') : L('badgePrivate'))}
        </span>
        <h2 class="sh-hero-name">${esc(etat.entity_name || c.name || '')}</h2>
        <p class="sh-hero-hint">${esc(commune ? L('sharedHint') : L('privateHint'))}</p>

        <div class="sh-hero-actions">
          <a class="sh-link" href="/activities/map"><i class="fa-solid fa-map"></i>${esc(L('openMap'))}</a>
          <a class="sh-link" href="/cartography/editor"><i class="fa-solid fa-pen-ruler"></i>${esc(L('openEditor'))}</a>
          ${etat.must_propose ? `<a class="sh-link sh-link--accent" href="/cartography/editor">
              <i class="fa-solid fa-code-pull-request"></i>${esc(L('proposeLink'))}</a>` : ''}
        </div>
      </div>

      <label class="sh-switch${gele ? ' is-locked' : ''}" id="sh-switch">
        <input type="checkbox" id="sh-shared-cb" ${commune ? 'checked' : ''} ${gele ? 'disabled' : ''}>
        <span class="sh-switch-track"><span class="sh-switch-knob"></span></span>
        <span class="sh-switch-label">${esc(L('sharedLabel'))}</span>
      </label>
    </section>`;
  }

  function brancherEnTete(gele) {
    if (gele) return;
    $('#sh-shared-cb')?.addEventListener('change', enregistrerAcces);
  }

  /* ── Tuiles de chiffres ───────────────────────────────────────────────── */

  // Un chiffre appelle le clic : chaque tuile mène au bloc qui l'explique.
  function tuiles(attente) {
    const n = (etat.reach || []).length;
    const ouverts = (etat.roles || []).filter(r => r.granted).length;
    return `
    <div class="sh-tiles">
      <button type="button" class="sh-tile sh-tile--people" data-va="2">
        <span class="sh-tile-n">${n}</span>
        <span class="sh-tile-k">${esc(L('statPeople'))}</span>
        <i class="fa-solid fa-arrow-right sh-tile-go"></i>
      </button>
      <button type="button" class="sh-tile sh-tile--roles" data-va="1">
        <span class="sh-tile-n${etat.open_to_all ? ' is-word' : ''}">${
          etat.open_to_all ? esc(L('statAll')) : ouverts}</span>
        <span class="sh-tile-k">${esc(L('statRoles'))}</span>
        <i class="fa-solid fa-arrow-right sh-tile-go"></i>
      </button>
      <button type="button" class="sh-tile sh-tile--pending${attente ? ' is-warn' : ''}" data-va="3">
        <span class="sh-tile-n">${attente}</span>
        <span class="sh-tile-k">${esc(L('statPending'))}</span>
        <i class="fa-solid fa-arrow-right sh-tile-go"></i>
      </button>
    </div>`;
  }

  function brancherTuiles() {
    document.querySelectorAll('.sh-tile').forEach(t =>
      t.addEventListener('click', () => {
        const bloc = document.querySelectorAll('.sh-block')[parseInt(t.dataset.va, 10) - 1];
        if (!bloc) return;
        bloc.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Un défilement seul se remarque mal : le bloc visé s'annonce.
        bloc.classList.remove('is-pointed');
        void bloc.offsetWidth;
        bloc.classList.add('is-pointed');
        setTimeout(() => bloc.classList.remove('is-pointed'), 1400);
      }));
  }

  /* ── 1 · Accès : les rôles, avec leurs titulaires ─────────────────────── */

  function blocAcces(gele) {
    if (!etat.is_shared) {
      return section('fa-users', L('sharepage_step1'), `
        <p class="sh-note"><i class="fa-solid fa-lock"></i> ${esc(L('privateHint'))}</p>`);
    }
    const roles = etat.roles || [];
    const corps = !roles.length
      ? `<p class="sh-empty">${esc(L('noRoles'))}</p>`
      : `<div class="sh-roles">${roles.map(r => carteRole(r, gele)).join('')}</div>
         ${etat.open_to_all ? `<p class="sh-note sh-note--ok">
            <i class="fa-solid fa-earth-europe"></i> ${esc(L('openToAll'))}</p>` : ''}`;
    return section('fa-users', L('sharepage_step1'),
      `<p class="sh-lead">${esc(L('rolesHint'))}</p>${corps}`,
      gele ? `<span class="sh-readonly"><i class="fa-solid fa-lock"></i> ${esc(L('readonly'))}</span>` : '');
  }

  function carteRole(r, gele) {
    return `
    <article class="sh-role${r.granted ? ' is-granted' : ''}${gele ? '' : ' is-clickable'}"
             data-role="${r.id}"${gele ? '' : ` title="${esc(L('manage'))}"`}>
      <header class="sh-role-head">
        <label class="sh-check">
          <input type="checkbox" class="sh-role-cb" value="${r.id}"
                 ${r.granted ? 'checked' : ''} ${gele ? 'disabled' : ''}>
          <span class="sh-check-box"><i class="fa-solid fa-check"></i></span>
        </label>
        <span class="sh-role-name">${esc(r.name)}</span>
        <span class="sh-role-n">${r.holders.length}</span>
      </header>
      <div class="sh-role-people">
        ${r.holders.map(h => `
          <span class="sh-chip">${avatar(h)}<span class="sh-chip-name">${esc(h.name)}</span>
            ${gele ? '' : `<button type="button" class="sh-chip-x" data-role="${r.id}"
                 data-user="${h.id}" title="${esc(L('removeHolder'))}">
                 <i class="fa-solid fa-xmark"></i></button>`}
          </span>`).join('')
        || `<span class="sh-nobody">${esc(L('noHolder'))}</span>`}
        ${gele ? '' : `<button type="button" class="sh-add" data-role="${r.id}">
            <i class="fa-solid fa-plus"></i> ${esc(L('addHolder'))}</button>`}
      </div>
    </article>`;
  }

  function brancherRoles(gele) {
    if (gele) return;
    document.querySelectorAll('.sh-role-cb').forEach(cb =>
      cb.addEventListener('change', enregistrerAcces));
    document.querySelectorAll('.sh-add').forEach(b =>
      b.addEventListener('click', (e) => {
        e.stopPropagation();
        ouvrirRole(parseInt(b.dataset.role, 10));
      }));
    document.querySelectorAll('.sh-chip-x').forEach(b =>
      b.addEventListener('click', (e) => {
        e.stopPropagation();
        majLien(parseInt(b.dataset.user, 10), parseInt(b.dataset.role, 10), false);
      }));
    // Toute la carte est une poignée — sauf la case, qui décide de l'accès.
    document.querySelectorAll('.sh-role').forEach(el =>
      el.addEventListener('click', (e) => {
        if (e.target.closest('.sh-check, button')) return;
        ouvrirRole(parseInt(el.dataset.role, 10));
      }));
  }

  // Cocher un rôle enregistre tout de suite : un bouton « Enregistrer » de plus
  // laisse partir sans sauver, et l'écran ment alors sur qui a accès.
  async function enregistrerAcces() {
    try {
      const data = await postJSON(`/cartography/api/access/${entityId}`, {
        is_shared: $('#sh-shared-cb').checked,
        role_ids: [...document.querySelectorAll('.sh-role-cb:checked')]
          .map(c => parseInt(c.value, 10)),
      });
      if (data.error) { alert(data.error); await charger(); return; }
      annoncer(L('saved'));
      const c = cartes.find(x => x.id === entityId);
      if (c) { c.is_shared = data.is_shared; c.open_to_all = data.open_to_all; }
      rendreGalerie();
      await charger();
    } catch (_) { alert(L('netError')); }
  }

  /* ── Le lien (compte ↔ rôle), réglable des deux côtés ─────────────────── */

  // Un seul endpoint pour les deux sens : il travaille par PAIRE, donc jamais
  // il ne retire à quelqu'un ses rôles sur les autres cartos.
  async function majLien(userId, roleId, ajouter) {
    try {
      const data = await postJSON(
        `/cartography/api/access/${entityId}/roles/${roleId}/holders`,
        ajouter ? { add: [userId] } : { remove: [userId] });
      if (data.error) { alert(data.error); return; }
      await charger();
      if (fenetre) rafraichirFenetre();
    } catch (_) { alert(L('netError')); }
  }

  function ouvrirRole(roleId) {
    const r = (etat.roles || []).find(x => x.id === roleId);
    if (!r || !etat.can_manage_access) return;
    fenetre = { mode: 'role', id: roleId };
    ouvrirFenetre(L('roleHolders'), r.name, L('searchAccount'));
  }

  function ouvrirPersonne(userId) {
    const u = (etat.accounts || []).find(x => x.id === userId);
    if (!u || !etat.can_manage_access) return;
    fenetre = { mode: 'person', id: userId };
    ouvrirFenetre(L('personRoles'), u.name, L('searchRole'));
  }

  function ouvrirFenetre(surtitre, titre, invite) {
    $('#sh-picker-eyebrow').textContent = surtitre;
    $('#sh-picker-role').textContent = titre;
    const champ = $('#sh-picker-search');
    champ.value = '';
    champ.placeholder = invite;
    rendreFenetre('');
    $('#sh-picker').classList.add('is-open');
    champ.focus();
  }

  function rafraichirFenetre() {
    rendreFenetre($('#sh-picker-search').value);
  }

  function rendreFenetre(filtre) {
    if (!fenetre) return;
    const q = (filtre || '').toLowerCase();
    const hote = $('#sh-picker-list');

    if (fenetre.mode === 'role') {
      const r = (etat.roles || []).find(x => x.id === fenetre.id);
      if (!r) { hote.innerHTML = `<p class="sh-empty">—</p>`; return; }
      const dedans = new Set((r.holders || []).map(h => h.id));
      hote.innerHTML = (etat.accounts || [])
        .filter(u => !q || u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))
        .map(u => ligneFenetre(u.id, avatar(u), u.name, u.email, dedans.has(u.id)))
        .join('') || `<p class="sh-empty">—</p>`;
      brancherFenetre((id, coche) => majLien(id, r.id, coche));
      return;
    }

    const roles = etat.roles || [];
    if (!roles.length) { hote.innerHTML = `<p class="sh-empty">${esc(L('noRoleHere'))}</p>`; return; }
    hote.innerHTML = roles
      .filter(r => !q || r.name.toLowerCase().includes(q))
      .map(r => ligneFenetre(
        r.id,
        `<span class="sh-role-ico${r.granted ? ' is-granted' : ''}">
           <i class="fa-solid fa-id-badge"></i></span>`,
        r.name,
        r.granted ? L('roleOpens') : L('roleClosed'),
        (r.holders || []).some(h => h.id === fenetre.id)))
      .join('') || `<p class="sh-empty">—</p>`;
    brancherFenetre((id, coche) => majLien(fenetre.id, id, coche));
  }

  function ligneFenetre(id, visuel, titre, sousTitre, coche) {
    return `
      <label class="sh-pick${coche ? ' is-in' : ''}">
        <input type="checkbox" value="${id}" ${coche ? 'checked' : ''}>
        ${visuel}
        <span class="sh-pick-text">
          <span class="sh-pick-name">${esc(titre)}</span>
          <span class="sh-pick-mail">${esc(sousTitre)}</span>
        </span>
        <span class="sh-pick-state"><i class="fa-solid fa-check"></i></span>
      </label>`;
  }

  function brancherFenetre(action) {
    $('#sh-picker-list').querySelectorAll('input').forEach(cb =>
      cb.addEventListener('change', () => action(parseInt(cb.value, 10), cb.checked)));
  }

  /* ── 2 · Qui ouvre cette carto ────────────────────────────────────────── */

  const MOTIF = {
    owner: ['reasonOwner', 'fa-crown'],
    admin: ['reasonAdmin', 'fa-shield-halved'],
    champion: ['reasonChampion', 'fa-award'],
    all: ['reasonAll', 'fa-earth-europe'],
    role: ['reasonRole', 'fa-id-badge'],
  };

  function blocPortee() {
    const gens = etat.reach || [];
    const corps = gens.length ? `
      <div class="sh-people">
        ${gens.map(u => {
          const [cle, ico] = MOTIF[u.reason] || ['reasonRole', 'fa-id-badge'];
          return `
          <article class="sh-person sh-person--${esc(u.reason)}${
            etat.can_manage_access ? ' is-clickable' : ''}" data-user="${u.id}"${
            etat.can_manage_access ? ` title="${esc(L('manage'))}"` : ''}>
            ${avatar(u, 'lg')}
            <div class="sh-person-body">
              <span class="sh-person-name">${esc(u.name)}</span>
              <span class="sh-person-mail">${esc(u.email)}</span>
              <span class="sh-why"><i class="fa-solid ${ico}"></i>${esc(L(cle))}</span>
              ${u.roles.length ? `<span class="sh-person-roles">${esc(u.roles.join(' · '))}</span>` : ''}
            </div>
          </article>`;
        }).join('')}
      </div>` : `<p class="sh-empty">${esc(L('reachEmpty'))}</p>`;
    return section('fa-user-check', L('sharepage_step2'), corps,
      `<a class="sh-link sh-link--sm" href="/comptes">
         <i class="fa-solid fa-users-gear"></i>${esc(L('manageAccounts'))}</a>`);
  }

  function brancherPersonnes(gele) {
    if (gele) return;
    document.querySelectorAll('.sh-person').forEach(el =>
      el.addEventListener('click', () => ouvrirPersonne(parseInt(el.dataset.user, 10))));
  }

  /* ── 3 · Modifications proposées ──────────────────────────────────────── */

  const STATUT = { pending: 'statusPending', approved: 'statusApproved', rejected: 'statusRejected' };

  function dateCourte(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString(undefined,
        { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch (_) { return iso.slice(0, 10); }
  }

  function blocChangements(attente) {
    const liste = etat.changes.requests || [];
    const corps = liste.length
      ? `<div class="sh-changes">${liste.map(carteChangement).join('')}</div>`
      : `<div class="sh-cta">
           <i class="fa-solid fa-code-pull-request"></i>
           <p>${esc(L('changesNone'))}</p>
           <a class="sh-link sh-link--accent" href="/cartography/editor">
             <i class="fa-solid fa-pen-ruler"></i>${esc(L('changesNoneCta'))}</a>
         </div>`;
    return section('fa-code-pull-request', L('sharepage_step3'), corps,
      attente ? `<span class="sh-badge-warn">${attente}</span>` : '', 'sh-changes-host');
  }

  function carteChangement(r) {
    return `
    <article class="sh-change sh-change--${esc(r.status)}" data-id="${r.id}">
      <div class="sh-change-top">
        <span class="sh-change-title">${esc(r.title || L('proposeTitle'))}</span>
        <span class="sh-state sh-state--${esc(r.status)}">${esc(L(STATUT[r.status] || r.status))}</span>
      </div>
      <div class="sh-change-meta">
        ${avatar({ name: r.author, email: String(r.author_id) })}
        <span>${esc(r.is_mine ? L('changeMine') : L('changeBy').replace('%s', r.author))}</span>
        <span class="sh-change-date">${esc(dateCourte(r.created_at))}</span>
      </div>
      ${r.message ? `<p class="sh-change-msg">${esc(r.message)}</p>` : ''}
    </article>`;
  }

  function brancherChangements() {
    document.querySelectorAll('.sh-change').forEach(el =>
      el.addEventListener('click', (e) => {
        if (e.target.closest('button')) return;
        ouvrirChangement(parseInt(el.dataset.id, 10));
      }));
  }

  function ligneResume(n, cle, exemples) {
    if (!n) return '';
    const detail = (exemples && exemples.length)
      ? `<span class="sh-sum-names">${esc(exemples.slice(0, 4).join(', '))}${
          exemples.length > 4 ? '…' : ''}</span>` : '';
    return `<li><strong>${n}</strong><span>${esc(L(n > 1 ? cle + '_p' : cle))}</span>${detail}</li>`;
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
    return lignes ? `<ul class="sh-sum">${lignes}</ul>`
                  : `<p class="sh-empty">${esc(L('nothing'))}</p>`;
  }

  async function ouvrirChangement(id) {
    const hote = $('.sh-changes-host');
    if (!hote) return;
    hote.innerHTML = squelette();
    try {
      const r = await getJSON(`/cartography/api/changes/${id}`);
      if (r.error) { hote.innerHTML = erreur(r.error); return; }
      hote.innerHTML = `
        <button class="sh-back" id="sh-back"><i class="fa-solid fa-chevron-left"></i>${esc(L('back'))}</button>
        <div class="sh-detail">
          <div class="sh-change-top">
            <h3 class="sh-detail-title">${esc(r.title || L('proposeTitle'))}</h3>
            <span class="sh-state sh-state--${esc(r.status)}">${esc(L(STATUT[r.status] || r.status))}</span>
          </div>
          <div class="sh-change-meta">
            ${avatar({ name: r.author, email: String(r.author_id) })}
            <span>${esc(r.is_mine ? L('changeMine') : L('changeBy').replace('%s', r.author))}</span>
            <span class="sh-change-date">${esc(dateCourte(r.created_at))}</span>
          </div>
          ${r.message ? `<p class="sh-detail-msg">${esc(r.message)}</p>` : ''}
          <span class="sh-eyebrow sh-sum-title">${esc(L('summaryTitle'))}</span>
          ${resumeHtml(r.summary)}
          ${r.can_review ? `
            <div class="sh-search sh-search--comment">
              <i class="fa-solid fa-comment"></i>
              <input type="text" id="sh-comment" placeholder="${esc(L('commentPh'))}">
            </div>
            <div class="sh-detail-actions">
              <button class="sh-btn sh-btn--danger" id="sh-reject">
                <i class="fa-solid fa-xmark"></i>${esc(L('reject'))}</button>
              <button class="sh-btn sh-btn--accent" id="sh-approve">
                <i class="fa-solid fa-check"></i>${esc(L('approve'))}</button>
            </div>` : ''}
        </div>`;
      $('#sh-back').addEventListener('click', () => charger());
      $('#sh-approve')?.addEventListener('click', () => trancher(id, 'approve'));
      $('#sh-reject')?.addEventListener('click', () => trancher(id, 'reject'));
    } catch (_) {
      hote.innerHTML = erreur(L('loadError'));
    }
  }

  async function trancher(id, action) {
    const btn = $(action === 'approve' ? '#sh-approve' : '#sh-reject');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
    try {
      const data = await postJSON(`/cartography/api/changes/${id}/${action}`,
        { comment: ($('#sh-comment')?.value || '').trim() });
      if (data.error) { alert(data.error); return; }
      if (data.sync_warning) alert(data.sync_warning);
      annoncer(action === 'approve' ? L('approved') : L('rejected'));
      // Une modification appliquée redessine la carto : la vignette doit suivre.
      await chargerGalerie();
    } catch (_) { alert(L('netError')); }
  }

  /* ── Charpente ────────────────────────────────────────────────────────── */

  function section(icone, titre, corps, extra, classeCorps) {
    return `
    <section class="sh-block">
      <header class="sh-block-head">
        <span class="sh-block-ico"><i class="fa-solid ${icone}"></i></span>
        <h3 class="sh-block-title">${esc(titre)}</h3>
        <span class="sh-grow"></span>
        ${extra || ''}
      </header>
      <div class="sh-block-body ${classeCorps || ''}">${corps}</div>
    </section>`;
  }

  function annoncer(texte) {
    let t = $('#sh-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'sh-toast';
      t.className = 'sh-toast';
      document.body.appendChild(t);
    }
    t.textContent = texte;
    t.classList.add('is-on');
    clearTimeout(annoncer._h);
    annoncer._h = setTimeout(() => t.classList.remove('is-on'), 2400);
  }

  /* ── Démarrage ────────────────────────────────────────────────────────── */

  function demarrer() {
    if (!$('#sh-gallery-list')) return;
    $('#sh-picker-close').addEventListener('click',
      () => $('#sh-picker').classList.remove('is-open'));
    $('#sh-picker').addEventListener('click', (e) => {
      if (e.target.id === 'sh-picker') e.currentTarget.classList.remove('is-open');
    });
    $('#sh-picker-search').addEventListener('input', (e) => rendreFenetre(e.target.value));
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') $('#sh-picker').classList.remove('is-open');
    });
    chargerGalerie();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
