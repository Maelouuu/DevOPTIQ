// static/js/gestion_rh.js
//
// Gestion RH — les personnes, les rôles, l'accès à la carto, les propositions.
//
// Trois principes, tirés de ce qui n'allait pas :
//
//   · UN seul appel de données (`/gestion_rh/api/tableau`). La page en faisait
//     dix qui se recoupaient, et deux se contredisaient sur qui est
//     collaborateur — d'où des sections vides sans raison visible.
//   · Le RÔLE est le pivot : il porte des personnes d'un côté, il ouvre (ou
//     non) la cartographie de l'autre. C'est pour ça que le partage vit ici et
//     plus sur un écran séparé.
//   · Un rafraîchissement après une action ne doit RIEN faire disparaître.
//     Vider la page pour afficher une attente puis tout ré-animer rendait
//     l'usage pénible (leçon de la page Partage).

(function () {
  'use strict';

  const L = (k) => (window.GRH_L && window.GRH_L[k]) || k;
  const $ = (s, r = document) => r.querySelector(s);

  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

  let D = null;            // le tableau renvoyé par le serveur
  let filtreTexte = '';
  let filtreRole = '';
  let fenetre = null;      // { mode: 'role' | 'personne', id }

  /* ── Réseau ─────────────────────────────────────────────────────────── */

  const getJSON = (url) => fetch(url).then((r) => r.json());
  const postJSON = (url, corps) => fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corps || {}),
  }).then((r) => r.json());

  function toast(message, type) {
    const hote = $('#toast-container');
    if (!hote) return;
    const el = document.createElement('div');
    el.className = 'grh-toast' + (type === 'error' ? ' is-error' : '');
    el.textContent = message;
    hote.appendChild(el);
    setTimeout(() => el.classList.add('is-out'), 2200);
    setTimeout(() => el.remove(), 2600);
  }

  /* ── Petits objets d'affichage ──────────────────────────────────────── */

  const initiales = (p) => ((p.prenom || '?')[0] + (p.nom || '')[0] || '?')
    .toUpperCase();

  // Une teinte stable par personne : deux collègues ne se confondent pas, et la
  // couleur ne bouge pas d'un chargement à l'autre.
  const TEINTES = [198, 262, 340, 24, 152, 288, 8, 174, 42, 316];
  function teinte(cle) {
    let h = 0;
    for (const c of String(cle)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return TEINTES[h % TEINTES.length];
  }

  const avatar = (p, taille) => `<span class="grh-av${taille ? ' grh-av--' + taille : ''}"
      style="--av-h:${teinte(p.email || p.id)}">${esc(initiales(p))}</span>`;

  const nomDe = (p) => `${p.prenom || ''} ${p.nom || ''}`.trim() || p.email;

  // `users.status` est un texte LIBRE, saisi différemment selon les instances
  // (« admin », « administrateur », « Gestionnaire de compétences »…). On en
  // déduit une famille pour la couleur, comme le fait Code/permissions.py —
  // jamais une égalité stricte, qui laisserait un statut mal orthographié se
  // fondre dans les autres.
  function famille(statut) {
    const s = (statut || '').toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    if (/^admin/.test(s)) return 'admin';
    if (s.includes('champion') || s.startsWith('gestionnaire')
        || (s.includes('manager') && /comp|skill/.test(s))) return 'champion';
    return 'user';
  }

  function personneParId(id) {
    return (D.personnes || []).find((p) => p.id === id) || null;
  }

  function roleParId(id) {
    return (D.roles || []).find((r) => r.id === id) || null;
  }

  /* ── Chargement ─────────────────────────────────────────────────────── */

  // ⚠️ `discret` : après une action de l'utilisateur, on remet à jour SANS
  // vider la page ni rejouer les entrées. C'est ce qui rendait la page Partage
  // insupportable à l'usage.
  async function charger(opts) {
    const discret = !!(opts && opts.discret);
    const cible = opts && opts.entityId;
    if (!discret) {
      $('#liste-personnes').innerHTML = attente();
      $('#liste-roles').innerHTML = attente();
    }
    try {
      const url = '/gestion_rh/api/tableau' + (cible ? `?entity_id=${cible}` : '');
      const data = await getJSON(url);
      if (data.error) { erreurGlobale(data.error); return; }
      D = data;
      const y = window.scrollY;
      rendre();
      if (discret) window.scrollTo(0, y);
      if (fenetre) rendreFenetre();
    } catch (_) {
      erreurGlobale(L('save_error'));
    }
  }

  const attente = () =>
    `<div class="grh-wait"><i class="fa-solid fa-spinner fa-spin"></i> ${esc(L('loading'))}</div>`;

  function erreurGlobale(message) {
    $('#liste-personnes').innerHTML = `<p class="grh-empty">${esc(message)}</p>`;
    $('#liste-roles').innerHTML = '';
  }

  function rendre() {
    rendreBandeau();
    rendreTuiles();
    rendreFiltreRoles();
    rendrePersonnes();
    rendreRoles();
    rendrePropositions();
  }

  /* ── Bandeau : l'entité, puis le calendrier ─────────────────────────── */

  function rendreBandeau() {
    const e = D.entite;
    const cal = D.calendrier || {};
    const champs = [
      ['work_hours_per_day', 'hours_per_day'],
      ['work_days_per_week', 'days_per_week'],
      ['work_weeks_per_year', 'weeks_per_year'],
      ['work_days_per_year', 'days_per_year'],
    ];

    $('#grh-topbar').innerHTML = `
      <div class="grh-topbar-main">
        <i class="fa-solid fa-diagram-project grh-topbar-icon"></i>
        <div class="grh-topbar-id">
          ${e ? `<h2>${esc(e.name)}</h2>` : `<h2 class="is-muted">${esc(L('entity_none'))}</h2>`}
          ${e ? `<span class="grh-chip ${e.is_shared ? 'grh-chip--shared' : ''}">
                   <i class="fa-solid ${e.is_shared ? 'fa-users' : 'fa-lock'}"></i>
                   ${esc(e.is_shared ? L('shared') : L('private'))}
                 </span>` : ''}
        </div>
        ${(D.entites || []).length > 1 ? `
          <label class="grh-topbar-pick">
            <span>${esc(L('entity_choose'))}</span>
            <select id="grh-entite" class="grh-select">
              ${(D.entites || []).map((x) => `
                <option value="${x.id}"${e && x.id === e.id ? ' selected' : ''}
                  >${esc(x.name)}</option>`).join('')}
            </select>
          </label>` : ''}
      </div>
      <div class="grh-cal">
        <span class="grh-cal-label"><i class="fa-regular fa-calendar"></i> ${esc(L('calendar'))}</span>
        ${champs.map(([cle, lib]) => `
          <button type="button" class="grh-cal-item" data-cle="${cle}"
                  title="${esc(L(lib))} — ${esc(L('edit'))}">
            <b>${cal[cle] != null ? esc(cal[cle]) : '—'}</b>
            <span>${esc(L(lib))}</span>
          </button>`).join('')}
      </div>`;

    $('#grh-entite')?.addEventListener('change', (ev) =>
      charger({ entityId: parseInt(ev.target.value, 10) }));
    document.querySelectorAll('.grh-cal-item').forEach((b) =>
      b.addEventListener('click', () => editerCalendrier(b)));
  }

  // Modifier sur place : un champ qui remplace le chiffre, Entrée valide.
  // Une pop-up pour changer un nombre serait disproportionnée.
  function editerCalendrier(bouton) {
    const cle = bouton.dataset.cle;
    const avant = (D.calendrier || {})[cle];
    if (bouton.querySelector('input')) return;
    bouton.innerHTML = `<input type="number" min="0" step="0.5" value="${avant != null ? avant : ''}">`;
    const champ = bouton.querySelector('input');
    champ.focus();
    champ.select();

    const finir = async (garder) => {
      const valeur = champ.value;
      if (!garder || valeur === String(avant == null ? '' : avant)) { rendreBandeau(); return; }
      try {
        const corps = new URLSearchParams({ key: cle, value: valeur });
        const r = await fetch('/gestion_rh/update_single_setting',
          { method: 'POST', body: corps });
        const data = await r.json();
        if (!data.success) throw new Error(data.error || '');
        D.calendrier[cle] = data.value;
        toast(L('saved'));
      } catch (_) {
        toast(L('save_error'), 'error');
      }
      rendreBandeau();
    };
    champ.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') finir(true);
      if (ev.key === 'Escape') finir(false);
    });
    champ.addEventListener('blur', () => finir(true));
  }

  /* ── Les tuiles : trois chiffres qui mènent à leur bloc ──────────────── */

  function rendreTuiles() {
    const tuiles = [
      ['bloc-personnes', 'fa-users', (D.personnes || []).length, L('tile_people'), 'a'],
      ['bloc-roles', 'fa-tags', (D.roles || []).length, L('tile_roles'), 'b'],
      ['bloc-propositions', 'fa-code-pull-request',
        (D.propositions || []).length, L('tile_changes'), 'c'],
    ];
    $('#grh-tiles').innerHTML = tuiles.map(([cible, icone, n, lib, ton]) => `
      <button type="button" class="grh-tile grh-tile--${ton}" data-cible="${cible}">
        <i class="fa-solid ${icone}"></i>
        <b>${n}</b>
        <span>${esc(lib)}</span>
      </button>`).join('');

    document.querySelectorAll('.grh-tile').forEach((t) =>
      t.addEventListener('click', () => {
        const bloc = document.getElementById(t.dataset.cible);
        if (!bloc) return;
        bloc.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Un simple défilement passe inaperçu : on DÉSIGNE le bloc atteint.
        bloc.classList.add('is-pointed');
        setTimeout(() => bloc.classList.remove('is-pointed'), 1400);
      }));
  }

  /* ── ① Les personnes ────────────────────────────────────────────────── */

  function rendreFiltreRoles() {
    const sel = $('#grh-filtre-role');
    const avant = sel.value;
    sel.innerHTML = `<option value="">${esc(L('tile_roles'))}</option>`
      + (D.roles || []).map((r) =>
        `<option value="${r.id}">${esc(r.name)}</option>`).join('');
    sel.value = avant;
  }

  function personnesVisibles() {
    const q = filtreTexte.trim().toLowerCase();
    return (D.personnes || []).filter((p) => {
      if (filtreRole && !p.roles.some((r) => String(r.id) === filtreRole)) return false;
      if (!q) return true;
      return (nomDe(p) + ' ' + p.email).toLowerCase().includes(q);
    });
  }

  function rendrePersonnes() {
    const gens = personnesVisibles();
    if (!gens.length) {
      $('#liste-personnes').innerHTML = `<p class="grh-empty">${esc(L('people_empty'))}</p>`;
      return;
    }
    const devs = (D.personnes || []).filter((p) => p.est_dev);
    const peut = !!(D.droits || {}).affecte;

    $('#liste-personnes').innerHTML = `<div class="grh-people">${gens.map((p) => `
      <article class="grh-person${p.est_dev ? ' is-dev' : ''}" data-id="${p.id}">
        ${avatar(p)}
        <div class="grh-person-id">
          <b>${esc(nomDe(p))}</b>
          <span>${esc(p.email)}</span>
        </div>
        <div class="grh-person-tags">
          <span class="grh-col-label">${esc(L('col_status'))}</span>
          <span class="grh-chip grh-chip--status" data-fam="${famille(p.statut)}"
            >${esc(p.statut || '—')}</span>
          ${p.est_dev ? `<span class="grh-chip grh-chip--dev" title="${esc(L('permanent_hint'))}">
             <i class="fa-solid fa-seedling"></i> ${esc(L('dev_badge'))}</span>` : ''}
        </div>
        <div class="grh-person-tags">
          <span class="grh-col-label">${esc(L('col_roles'))}</span>
          <button type="button" class="grh-person-roles" data-roles="${p.id}"
                  title="${esc(L('manage_roles'))}">
            ${p.roles.length
              ? p.roles.slice(0, 3).map((r) =>
                  `<span class="grh-chip">${esc(r.name)}</span>`).join('')
                + (p.roles.length > 3 ? `<span class="grh-chip">+${p.roles.length - 3}</span>` : '')
              : `<span class="grh-chip grh-chip--none">${esc(L('no_role'))}</span>`}
          </button>
        </div>
        <div class="grh-person-dev">
          <span class="grh-col-label">${esc(L('dev_label'))}</span>
          ${boutonDev(p, devs, peut)}
        </div>
      </article>`).join('')}</div>`;

    document.querySelectorAll('[data-roles]').forEach((b) =>
      b.addEventListener('click', () => ouvrirPersonne(parseInt(b.dataset.roles, 10))));
    document.querySelectorAll('.grh-devpick').forEach((b) =>
      b.addEventListener('click', (e) => { e.stopPropagation(); ouvrirMenuDev(b); }));
  }

  // ⚠️ Un `<select>` natif rend la liste du SYSTÈME : aucune feuille de style de
  // la page ne l'atteint. Le bouton fermé était soigné, la liste ouverte ne
  // pouvait pas l'être. On dessine donc les deux.
  function boutonDev(p, devs, peut) {
    const actuel = devs.find((d) => d.id === p.dev_id);
    return `
      <button type="button" class="grh-devpick" data-dev="${p.id}" ${peut ? '' : 'disabled'}>
        ${actuel ? avatar(actuel, 'xs') : '<span class="grh-devpick-none"></span>'}
        <span class="grh-devpick-name${actuel ? '' : ' is-empty'}"
          >${esc(actuel ? nomDe(actuel) : L('dev_none'))}</span>
        <i class="fa-solid fa-chevron-down"></i>
      </button>`;
  }

  let menuOuvert = null;

  function fermerMenuDev() {
    if (!menuOuvert) return;
    menuOuvert.panneau.remove();
    menuOuvert.bouton.classList.remove('is-open');
    menuOuvert = null;
    document.removeEventListener('keydown', _echapMenu, true);
  }

  function _echapMenu(e) { if (e.key === 'Escape') fermerMenuDev(); }

  function ouvrirMenuDev(bouton) {
    const userId = parseInt(bouton.dataset.dev, 10);
    if (menuOuvert && menuOuvert.userId === userId) { fermerMenuDev(); return; }
    fermerMenuDev();

    const p = personneParId(userId);
    const devs = (D.personnes || []).filter((x) => x.est_dev && x.id !== userId);

    const panneau = document.createElement('div');
    panneau.className = 'grh-devmenu';
    panneau.innerHTML = `
      <button type="button" class="grh-devmenu-item${p.dev_id ? '' : ' is-current'}"
              data-choix="">
        <span class="grh-devpick-none"></span>
        <span class="grh-devmenu-name is-empty">${esc(L('dev_none'))}</span>
        ${p.dev_id ? '' : '<i class="fa-solid fa-check"></i>'}
      </button>
      ${devs.length ? devs.map((d) => `
        <button type="button" class="grh-devmenu-item${p.dev_id === d.id ? ' is-current' : ''}"
                data-choix="${d.id}">
          ${avatar(d, 'xs')}
          <span class="grh-devmenu-name">${esc(nomDe(d))}</span>
          ${p.dev_id === d.id ? '<i class="fa-solid fa-check"></i>' : ''}
        </button>`).join('')
        : `<p class="grh-devmenu-empty">${esc(L('dev_no_candidate'))}</p>`}`;

    document.body.appendChild(panneau);
    // Position fixe, calée sous le bouton : le menu doit échapper au
    // `overflow` de la liste des personnes, sinon il serait tronqué.
    const r = bouton.getBoundingClientRect();
    const h = panneau.offsetHeight;
    const enBas = r.bottom + h + 8 < window.innerHeight;
    panneau.style.left = Math.min(r.left, window.innerWidth - panneau.offsetWidth - 12) + 'px';
    panneau.style.top = (enBas ? r.bottom + 6 : Math.max(8, r.top - h - 6)) + 'px';
    panneau.style.minWidth = r.width + 'px';

    bouton.classList.add('is-open');
    menuOuvert = { userId, bouton, panneau };
    document.addEventListener('keydown', _echapMenu, true);

    panneau.querySelectorAll('[data-choix]').forEach((b) =>
      b.addEventListener('click', () => {
        const v = b.dataset.choix;
        fermerMenuDev();
        affecterDev(userId, v ? parseInt(v, 10) : null);
      }));
  }

  async function affecterDev(userId, devId) {
    try {
      const data = await postJSON('/gestion_rh/assign_manager_simple',
        { user_id: userId, manager_id: devId, role_ids: null });
      if (!data.success) throw new Error();
      toast(L('saved'));
      await charger({ discret: true });
    } catch (_) { toast(L('save_error'), 'error'); }
  }

  /* ── ② Les rôles — le pivot de la page ──────────────────────────────── */

  function rendreRoles() {
    const roles = D.roles || [];
    const gere = !!(D.droits || {}).gere_acces;
    const commune = !!(D.entite && D.entite.is_shared);
    const tous = !!(D.entite && D.entite.open_to_all);

    if (!roles.length) {
      $('#liste-roles').innerHTML = `<p class="grh-empty">${esc(L('roles_empty'))}</p>`;
    } else {
      $('#liste-roles').innerHTML = `<div class="grh-roles">${roles.map((r) => `
        <article class="grh-role${r.permanent ? ' is-permanent' : ''}" data-id="${r.id}">
          <button type="button" class="grh-role-main" data-holders="${r.id}">
            <span class="grh-role-name">
              <i class="fa-solid ${r.permanent ? 'fa-seedling' : 'fa-tag'}"></i>
              ${esc(r.name)}
            </span>
            <span class="grh-role-count">
              <i class="fa-solid fa-user"></i> ${r.titulaires.length}
              <em>${esc(L('holders'))}</em>
            </span>
          </button>
          <div class="grh-role-side">
            ${commune ? `
              <label class="grh-switch" title="${esc(L('opens_map_hint'))}">
                <input type="checkbox" class="grh-acces" value="${r.id}"
                       ${r.ouvre_carto ? 'checked' : ''} ${gere ? '' : 'disabled'}>
                <span>${esc(L('opens_map'))}</span>
              </label>` : ''}
            ${r.permanent
              ? `<span class="grh-chip grh-chip--dev" title="${esc(L('permanent_hint'))}">
                   ${esc(L('permanent'))}</span>`
              : `<button type="button" class="grh-icon danger" data-suppr="${r.id}"
                         title="${esc(L('del'))}"><i class="fa-solid fa-trash"></i></button>`}
          </div>
        </article>`).join('')}</div>`;
    }

    // Ce que l'écran doit dire de lui-même, sans qu'on ait à le deviner.
    const notes = [L('roles_from_map')];
    if (commune && tous) notes.push(L('open_to_all'));
    if (!gere) notes.push(L('readonly'));
    $('#note-roles').textContent = notes.join(' · ');

    document.querySelectorAll('[data-holders]').forEach((b) =>
      b.addEventListener('click', () => ouvrirRole(parseInt(b.dataset.holders, 10))));
    document.querySelectorAll('[data-suppr]').forEach((b) =>
      b.addEventListener('click', () => supprimerRole(parseInt(b.dataset.suppr, 10))));
    document.querySelectorAll('.grh-acces').forEach((c) =>
      c.addEventListener('change', enregistrerAcces));
  }

  // Cocher enregistre tout de suite : un bouton « Enregistrer » de plus laisse
  // partir sans sauver, et l'écran ment alors sur qui a accès.
  async function enregistrerAcces() {
    if (!D.entite) return;
    try {
      const data = await postJSON(`/cartography/api/access/${D.entite.id}`, {
        is_shared: true,
        role_ids: [...document.querySelectorAll('.grh-acces:checked')]
          .map((c) => parseInt(c.value, 10)),
      });
      if (data.error) { toast(data.error, 'error'); await charger({ discret: true }); return; }
      toast(L('saved'));
      await charger({ discret: true });
    } catch (_) { toast(L('save_error'), 'error'); }
  }

  async function supprimerRole(roleId) {
    const r = roleParId(roleId);
    if (!r || r.permanent) return;
    if (!window.confirm(L('confirm_delete').replace('%s', r.name))) return;
    try {
      const rep = await fetch(`/gestion_rh/delete_role/${roleId}`, { method: 'POST' });
      if (!rep.ok) throw new Error();
      toast(L('saved'));
      await charger({ discret: true });
    } catch (_) { toast(L('save_error'), 'error'); }
  }

  function initNouveauRole() {
    const form = $('#form-nouveau-role');
    $('#btn-nouveau-role').addEventListener('click', () => {
      form.classList.toggle('hidden');
      if (!form.classList.contains('hidden')) $('#nom-nouveau-role').focus();
    });
    $('#annuler-nouveau-role').addEventListener('click', () => form.classList.add('hidden'));
    $('#valider-nouveau-role').addEventListener('click', async () => {
      const nom = $('#nom-nouveau-role').value.trim();
      if (!nom) return;
      try {
        const corps = new URLSearchParams({ name: nom });
        const rep = await fetch('/gestion_rh/role', { method: 'POST', body: corps });
        if (!rep.ok) throw new Error();
        $('#nom-nouveau-role').value = '';
        form.classList.add('hidden');
        toast(L('saved'));
        await charger({ discret: true });
      } catch (_) { toast(L('save_error'), 'error'); }
    });
  }

  /* ── ③ Les propositions ─────────────────────────────────────────────── */

  function rendrePropositions() {
    const liste = D.propositions || [];
    if (!liste.length) {
      $('#liste-propositions').innerHTML = `
        <p class="grh-empty">${esc(L('changes_empty'))}</p>`;
      return;
    }
    $('#liste-propositions').innerHTML = `<div class="grh-changes">${liste.map((c) => `
      <article class="grh-change">
        <i class="fa-solid fa-code-pull-request"></i>
        <div class="grh-change-id">
          <b>${esc(c.titre || L('tile_changes'))}</b>
          <span>${esc(L('by'))} ${esc(c.auteur)}${c.le ? ' · ' + esc(dateCourte(c.le)) : ''}</span>
        </div>
        <a class="grh-btn grh-btn--ghost" href="/cartography/editor?proposition=${c.id}">
          ${esc(L('changes_review'))} <i class="fa-solid fa-arrow-right"></i>
        </a>
      </article>`).join('')}</div>`;
  }

  function dateCourte(iso) {
    try {
      return new Date(iso).toLocaleDateString(window.GRH_CTX?.lang === 'en' ? 'en-GB' : 'fr-FR',
        { day: '2-digit', month: 'short' });
    } catch (_) { return ''; }
  }

  /* ── La fenêtre : un rôle ↔ ses titulaires, une personne ↔ ses rôles ── */

  function ouvrirRole(roleId) {
    if (!(D.droits || {}).affecte) return;
    fenetre = { mode: 'role', id: roleId };
    ouvrir();
  }

  function ouvrirPersonne(userId) {
    if (!(D.droits || {}).affecte) return;
    fenetre = { mode: 'personne', id: userId };
    ouvrir();
  }

  function ouvrir() {
    $('#grh-modal').classList.remove('hidden');
    $('#grh-modal-q').value = '';
    rendreFenetre();
    setTimeout(() => $('#grh-modal-q').focus(), 40);
  }

  function fermerFenetre() {
    fenetre = null;
    $('#grh-modal').classList.add('hidden');
  }

  function rendreFenetre() {
    if (!fenetre) return;
    const q = ($('#grh-modal-q').value || '').trim().toLowerCase();

    if (fenetre.mode === 'role') {
      const r = roleParId(fenetre.id);
      if (!r) { fermerFenetre(); return; }
      $('#grh-modal-over').textContent = L('tile_roles');
      $('#grh-modal-titre').textContent = r.name;
      const gens = (D.personnes || []).filter((p) =>
        !q || (nomDe(p) + ' ' + p.email).toLowerCase().includes(q));
      $('#grh-modal-body').innerHTML = gens.map((p) => ligne(
        avatar(p, 'sm'), nomDe(p), p.email,
        r.titulaires.includes(p.id), `${p.id}:${r.id}`)).join('')
        || `<p class="grh-empty">${esc(L('people_empty'))}</p>`;
    } else {
      const p = personneParId(fenetre.id);
      if (!p) { fermerFenetre(); return; }
      $('#grh-modal-over').textContent = L('manage_roles');
      $('#grh-modal-titre').textContent = nomDe(p);
      const roles = (D.roles || []).filter((r) => !q || r.name.toLowerCase().includes(q));
      $('#grh-modal-body').innerHTML = roles.map((r) => ligne(
        `<span class="grh-role-dot${r.permanent ? ' is-permanent' : ''}"></span>`,
        r.name,
        r.ouvre_carto && D.entite && D.entite.is_shared ? L('opens_map') : '',
        r.titulaires.includes(p.id), `${p.id}:${r.id}`)).join('')
        || `<p class="grh-empty">${esc(L('roles_empty'))}</p>`;
    }

    document.querySelectorAll('.grh-pick').forEach((el) =>
      el.addEventListener('change', () => {
        const [u, r] = el.dataset.paire.split(':').map(Number);
        majLien(u, r, el.checked);
      }));
  }

  const ligne = (visuel, titre, sousTitre, coche, paire) => `
    <label class="grh-row">
      ${visuel}
      <span class="grh-row-id">
        <b>${esc(titre)}</b>
        ${sousTitre ? `<span>${esc(sousTitre)}</span>` : ''}
      </span>
      <input type="checkbox" class="grh-pick" data-paire="${paire}" ${coche ? 'checked' : ''}>
    </label>`;

  // ⚠️ Un seul endpoint pour les deux sens, et il travaille PAR PAIRE : les
  // routes de la page Comptes, elles, remplacent TOUS les rôles d'une personne
  // (delete puis insert) — les appeler d'ici lui retirerait ses rôles sur les
  // autres cartos.
  async function majLien(userId, roleId, ajouter) {
    if (!D.entite) return;
    try {
      const data = await postJSON(
        `/cartography/api/access/${D.entite.id}/roles/${roleId}/holders`,
        ajouter ? { add: [userId] } : { remove: [userId] });
      if (data.error) { toast(data.error, 'error'); return; }
      await charger({ discret: true });
    } catch (_) { toast(L('save_error'), 'error'); }
  }

  /* ── Démarrage ──────────────────────────────────────────────────────── */

  function demarrer() {
    $('#grh-q').addEventListener('input', (e) => {
      filtreTexte = e.target.value;
      rendrePersonnes();
    });
    $('#grh-filtre-role').addEventListener('change', (e) => {
      filtreRole = e.target.value;
      rendrePersonnes();
    });
    $('#grh-modal-q').addEventListener('input', rendreFenetre);
    $('#grh-modal-x').addEventListener('click', fermerFenetre);
    $('#grh-modal-fond').addEventListener('click', fermerFenetre);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && fenetre) fermerFenetre();
    });
    document.addEventListener('click', (e) => {
      if (menuOuvert && !e.target.closest('.grh-devmenu')) fermerMenuDev();
    });
    // Le panneau est en position FIXE : il ne suivrait pas son bouton.
    window.addEventListener('resize', fermerMenuDev);
    document.addEventListener('scroll', fermerMenuDev, true);
    initNouveauRole();
    charger();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
