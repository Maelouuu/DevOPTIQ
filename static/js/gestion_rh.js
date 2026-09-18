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
  // Le singulier ne couvre pas les mêmes nombres : « 0 titulaire » en
  // français, « 0 holders » en anglais.
  const unSeul = (n) => ((window.GRH_CTX || {}).lang === 'en' ? n === 1 : n <= 1);
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
    chargerDroits();
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
            ${chipsRoles(p)}
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

  /* ⚠️ Ce que dit l'écran doit être ce que dit le DROIT. `encadre()` lit les
     deux rattachements — le lien global (`users.manager_id`) ET celui de
     chaque rôle — donc un développeur posé globalement suit TOUS les rôles,
     même ceux dont la ligne est vide. On calcule donc la portée EFFECTIVE,
     pas la saisie. */
  function couverture(p) {
    const roles = (p.roles || []).map((r) => ({
      id: r.id, name: r.name, dev: r.dev_id || p.dev_id || null,
    }));
    const suivis = roles.filter((x) => x.dev);
    // ⚠️ `roles` ne porte que les rôles de la carto REGARDÉE. Une personne
    // qui n'en tient aucun ici peut très bien avoir un développeur global —
    // afficher « Aucun » serait faux, et le lien couvre bien tous ses rôles.
    const devs = roles.length
      ? [...new Set(roles.map((x) => x.dev).filter(Boolean))]
      : (p.dev_id ? [p.dev_id] : []);
    return {
      roles, devs, n: roles.length, k: suivis.length,
      global: p.dev_id || null,
      // « tous ses rôles » : un seul développeur, et aucun rôle laissé de côté.
      total: roles.length
        ? (suivis.length === roles.length && devs.length === 1)
        : !!p.dev_id,
    };
  }

  // Le nom d'un compte quel qu'il soit : un développeur qui a perdu le rôle
  // « Développeur de compétences » suit toujours ceux qu'on lui a confiés —
  // le chercher dans la seule liste des candidats afficherait « Aucun ».
  function nomCompte(id) {
    const q = personneParId(id);
    return q ? nomDe(q) : '—';
  }

  const portion = (k, n) =>
    L(k === 1 ? 'dev_scope_1' : 'dev_scope_n').replace('{k}', k).replace('{n}', n);

  // ⚠️ On voyait les rôles d'une personne sans jamais voir lesquels sont
  // SUIVIS : la pastille le dit là où on regarde déjà.
  function chipsRoles(p) {
    const c = couverture(p);
    if (!c.n) return `<span class="grh-chip grh-chip--none">${esc(L('no_role'))}</span>`;
    return c.roles.slice(0, 3).map((x) => `
      <span class="grh-chip${x.dev ? ' grh-chip--suivi' : ''}"
            title="${esc(x.dev ? L('dev_followed_by').replace('{nom}', nomCompte(x.dev))
                                : L('dev_none'))}"
        >${x.dev ? '<i class="fa-solid fa-seedling"></i> ' : ''}${esc(x.name)}</span>`).join('')
      + (c.n > 3 ? `<span class="grh-chip">+${c.n - 3}</span>` : '');
  }

  // ⚠️ Un `<select>` natif rend la liste du SYSTÈME : aucune feuille de style de
  // la page ne l'atteint. Le bouton fermé était soigné, la liste ouverte ne
  // pouvait pas l'être. On dessine donc les deux.
  //
  // ⚠️ Et un NOM SEUL était un mensonge par omission : « Lou Vasseur » se
  // lisait pareil que le développeur soit posé sur les trois rôles ou sur un
  // seul. Le bouton porte donc sa PORTÉE, et une portée partielle se voit.
  function boutonDev(p, devs, peut) {
    const c = couverture(p);
    let visuel = '<span class="grh-devpick-none"></span>';
    let nom = L('dev_none');
    let portee_dite = '';
    let partiel = false;
    if (c.devs.length > 1) {
      nom = L('dev_mixed').replace('{n}', c.devs.length);
      portee_dite = portion(c.k, c.n);
      partiel = true;
    } else if (c.devs.length === 1) {
      const d = personneParId(c.devs[0]);
      if (d) visuel = avatar(d, 'xs');
      nom = nomCompte(c.devs[0]);
      partiel = !c.total && c.n > 0;
      portee_dite = partiel ? portion(c.k, c.n) : L('dev_all_roles');
    }
    return `
      <button type="button" class="grh-devpick${partiel ? ' is-partial' : ''}"
              data-dev="${p.id}" ${peut ? '' : 'disabled'}
              title="${esc(L('dev_scope_title'))}">
        ${visuel}
        <span class="grh-devpick-txt">
          <span class="grh-devpick-name${c.devs.length ? '' : ' is-empty'}">${esc(nom)}</span>
          ${portee_dite ? `<span class="grh-devpick-scope${partiel ? ' is-partial' : ''}"
            >${esc(portee_dite)}</span>` : ''}
        </span>
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

  // Le développeur en place SUR CETTE PORTÉE — c'est lui qui porte la coche.
  // `cible` nul = tous ses rôles.
  function devDePortee(c, cible) {
    if (cible === null) return c.total ? c.devs[0] : c.global;
    const ids = [...new Set(cible.map((id) => {
      const x = c.roles.find((y) => y.id === id);
      return x ? x.dev : null;
    }))];
    return (ids.length === 1 && ids[0]) ? ids[0] : null;
  }

  let portee = null;   // { mode: 'tous' | 'precis', roles: Set }

  /* ⚠️ **La portée se choisit ICI, dans le menu du développeur.** Elle vivait
     dans la fiche de la personne, derrière le bouton des RÔLES : personne ne
     l'y cherchait, et le menu « Développeur de compétences » ne proposait que
     des noms — on ne pouvait pas dire sur quoi. Une question, un endroit. */
  function panneauPortee(p, devs) {
    const c = couverture(p);
    const cible = portee.mode === 'tous' ? null : [...portee.roles];
    const actuelId = devDePortee(c, cible);
    const bloque = portee.mode === 'precis' && portee.roles.size === 0;
    const radio = (on) => `<span class="grh-radio${on ? ' is-on' : ''}"></span>`;

    const bloc_portee = !c.n
      ? `<p class="grh-devmenu-note">${esc(L('dev_no_role_scope'))}</p>`
      : `
        <p class="grh-devmenu-scope">${esc(L('dev_scope_title'))}</p>
        <button type="button" class="grh-scope${portee.mode === 'tous' ? ' is-current' : ''}"
                data-mode="tous">
          ${radio(portee.mode === 'tous')}
          <span><b>${esc(L('dev_scope_all'))} (${c.n})</b>
                <em>${esc(L('dev_scope_all_hint'))}</em></span>
        </button>
        <button type="button" class="grh-scope${portee.mode === 'precis' ? ' is-current' : ''}"
                data-mode="precis">
          ${radio(portee.mode === 'precis')}
          <span><b>${esc(L('dev_scope_pick'))}</b></span>
        </button>
        ${portee.mode === 'precis' ? `<div class="grh-scope-roles">${c.roles.map((x) => `
          <label class="grh-scope-role${x.dev ? ' is-suivi' : ''}">
            <input type="checkbox" data-role-pick="${x.id}"
                   ${portee.roles.has(x.id) ? 'checked' : ''}>
            <b>${esc(x.name)}</b>
            <span>${esc(x.dev ? nomCompte(x.dev) : L('dev_none'))}</span>
          </label>`).join('')}</div>` : ''}`;

    return `
      ${bloc_portee}
      <p class="grh-devmenu-scope">${esc(L('dev_who_title'))}</p>
      ${bloque ? `<p class="grh-devmenu-note">${esc(L('dev_scope_none_yet'))}</p>` : ''}
      <button type="button" class="grh-devmenu-item${actuelId ? '' : ' is-current'}"
              data-choix="" ${bloque ? 'disabled' : ''}>
        <span class="grh-devpick-none"></span>
        <span class="grh-devmenu-name is-empty">${esc(L('dev_none'))}</span>
        ${actuelId ? '' : '<i class="fa-solid fa-check"></i>'}
      </button>
      ${devs.length ? devs.map((d) => `
        <button type="button" class="grh-devmenu-item${actuelId === d.id ? ' is-current' : ''}"
                data-choix="${d.id}" ${bloque ? 'disabled' : ''}>
          ${avatar(d, 'xs')}
          <span class="grh-devmenu-name">${esc(nomDe(d))}</span>
          ${actuelId === d.id ? '<i class="fa-solid fa-check"></i>' : ''}
        </button>`).join('')
        : `<p class="grh-devmenu-empty">${esc(L('dev_no_candidate'))}</p>`}`;
  }

  // Liste simple : le développeur d'UN rôle, depuis la fiche de la personne.
  // La portée y est déjà dite par la ligne, il n'y a que le nom à choisir.
  function panneauSimple(p, devs, roleId) {
    const actuelId = devDuRole(p, roleId);
    return `
      <p class="grh-devmenu-scope">${esc(L('dev_for_role'))}</p>
      <button type="button" class="grh-devmenu-item${actuelId ? '' : ' is-current'}"
              data-choix="">
        <span class="grh-devpick-none"></span>
        <span class="grh-devmenu-name is-empty">${esc(L('dev_none'))}</span>
        ${actuelId ? '' : '<i class="fa-solid fa-check"></i>'}
      </button>
      ${devs.length ? devs.map((d) => `
        <button type="button" class="grh-devmenu-item${actuelId === d.id ? ' is-current' : ''}"
                data-choix="${d.id}">
          ${avatar(d, 'xs')}
          <span class="grh-devmenu-name">${esc(nomDe(d))}</span>
          ${actuelId === d.id ? '<i class="fa-solid fa-check"></i>' : ''}
        </button>`).join('')
        : `<p class="grh-devmenu-empty">${esc(L('dev_no_candidate'))}</p>`}`;
  }

  function ouvrirMenuDev(bouton) {
    const userId = parseInt(bouton.dataset.dev, 10);
    const roleId = bouton.dataset.role ? parseInt(bouton.dataset.role, 10) : null;
    const cle = userId + ':' + (roleId || '');
    if (menuOuvert && menuOuvert.cle === cle) { fermerMenuDev(); return; }
    fermerMenuDev();

    const p = personneParId(userId);
    if (!p) return;
    const devs = (D.personnes || []).filter((x) => x.est_dev && x.id !== userId);
    const c = couverture(p);
    // On ouvre sur la RÉALITÉ : une couverture partielle s'affiche déjà
    // dépliée, ses rôles cochés — sinon l'écran demanderait de refaire un
    // choix sans montrer celui qui est en place.
    portee = (c.n > 0 && c.k > 0 && !c.total)
      ? { mode: 'precis', roles: new Set(c.roles.filter((x) => x.dev).map((x) => x.id)) }
      : { mode: 'tous', roles: new Set() };

    const panneau = document.createElement('div');
    panneau.className = 'grh-devmenu' + (roleId ? '' : ' grh-devmenu--portee');
    /* ⚠️ **Un clic DANS le panneau le refermait.** Le clic du dessous
       (document) ferme le menu quand sa cible n'est pas dans `.grh-devmenu` —
       or changer la portée REDESSINE le panneau, si bien que la cible du clic
       est déjà DÉTACHÉE quand l'événement remonte : `closest()` ne trouve plus
       rien et le menu se fermait au premier réglage. On arrête donc la
       remontée au panneau, une fois pour toutes. */
    panneau.addEventListener('click', (e) => e.stopPropagation());
    document.body.appendChild(panneau);

    /* Position fixe, calée sous le bouton : le menu doit échapper au
       `overflow` de la liste des personnes, sinon il serait tronqué.

       ⚠️ **`body.pg` porte `zoom: .8`** (ui-theme). Un enfant du body posé en
       `position: fixed` voit ses coordonnées MULTIPLIÉES par ce zoom, alors
       que `getBoundingClientRect()` les rend déjà en pixels d'écran : le menu
       était dessiné 20 % trop haut et trop à gauche de son bouton. Invisible
       tant qu'il était étroit, criant dès qu'il s'élargit. `offsetWidth`, lui,
       est déjà dans le repère du body — il faut donc le convertir dans l'autre
       sens pour le comparer à `window.innerWidth`. */
    const poser = () => {
      const r = bouton.getBoundingClientRect();
      const z = parseFloat(getComputedStyle(document.body).zoom) || 1;
      const w = panneau.offsetWidth * z;
      const h = panneau.offsetHeight * z;
      const enBas = r.bottom + h + 8 < window.innerHeight;
      const x = Math.max(8, Math.min(r.left, window.innerWidth - w - 12));
      const y = enBas ? r.bottom + 6 : Math.max(8, r.top - h - 6);
      panneau.style.left = (x / z) + 'px';
      panneau.style.top = (y / z) + 'px';
      if (roleId) panneau.style.minWidth = (r.width / z) + 'px';
    };

    const appliquer = (v) => {
      const devId = v ? parseInt(v, 10) : null;
      const roles = roleId ? [roleId]
                  : (portee.mode === 'tous' ? null : [...portee.roles]);
      fermerMenuDev();
      affecterPortee(userId, devId, roles);
    };

    const brancher = () => {
      panneau.querySelectorAll('[data-mode]').forEach((b) =>
        b.addEventListener('click', () => {
          portee.mode = b.dataset.mode;
          if (portee.mode === 'precis' && !portee.roles.size) {
            // Rien de coché : on part de ce qui est en place plutôt que d'une
            // liste vide, qui demanderait de tout ressaisir.
            c.roles.filter((x) => x.dev).forEach((x) => portee.roles.add(x.id));
          }
          redessiner();
        }));
      panneau.querySelectorAll('[data-role-pick]').forEach((el) =>
        el.addEventListener('change', () => {
          const id = parseInt(el.dataset.rolePick, 10);
          if (el.checked) portee.roles.add(id); else portee.roles.delete(id);
          redessiner();
        }));
      panneau.querySelectorAll('[data-choix]').forEach((b) =>
        b.addEventListener('click', () => { if (!b.disabled) appliquer(b.dataset.choix); }));
    };

    const redessiner = () => {
      panneau.innerHTML = roleId ? panneauSimple(p, devs, roleId)
                                 : panneauPortee(p, devs);
      brancher();
      poser();
    };
    redessiner();

    bouton.classList.add('is-open');
    menuOuvert = { cle, userId, roleId, bouton, panneau };
    document.addEventListener('keydown', _echapMenu, true);
  }

  // Le développeur posé sur CE rôle (null s'il n'y en a pas).
  function devDuRole(p, roleId) {
    const lien = (p.roles || []).find((r) => r.id === roleId);
    // ⚠️ Un lien GLOBAL couvre ce rôle même quand sa ligne est vide : afficher
    // « Aucun » serait faux. La première écriture par rôle dissout ce lien
    // global côté serveur — l'affichage et le droit restent d'accord.
    return lien ? (lien.dev_id || p.dev_id || null) : null;
  }

  /* ⚠️ `user_roles.manager_id` portait ce lien depuis toujours et
     `encadre()` le lisait déjà — mais aucun écran ne le posait : la page
     envoyait « le même développeur pour tous les rôles ». Or celui qui suit
     quelqu'un sur « Qualité » ne le suit pas forcément sur « Logistique ».

     ⚠️ Un SEUL appel porte les deux moitiés de la décision (qui, et sur quoi) :
     en deux requêtes, un refus au milieu laisserait un développeur posé
     partout en attendant une portée qui n'arrive jamais. */
  async function affecterPortee(userId, devId, roleIds) {
    try {
      const d = await postJSON('/gestion_rh/dev_scope',
        { user_id: userId, dev_id: devId, role_ids: roleIds });
      if (!d.ok) throw new Error();
      toast(L('saved'));
      await charger({ discret: true });
      if (fenetre) rendreFenetre();
    } catch (_) { toast(L('save_error'), 'error'); }
  }

  /* ── ④ Ce que chaque palier ouvre ───────────────────────────────────────
     L'échelle `user < champion < coordinateur < admin` est la grammaire du
     produit et ne se règle pas. Ce que chaque palier OUVRE, si : une
     entreprise où tout le monde propose n'a pas les mêmes usages qu'une où
     seul un coordinateur touche à la carto.

     ⚠️ La colonne `admin` est cochée et VERROUILLÉE. Se retirer les Paramètres,
     ce serait perdre l'écran depuis lequel on les remettrait — la porte se
     refermerait de l'intérieur, sans poignée. */

  const ORDRE_DROITS = ['propose_carto', 'edit_carto', 'review_carto',
                        'manage_acces', 'acces_rh', 'cree_comptes',
                        'parametres_admin'];
  let DR = null;   // { paliers, droits, defaut, modifiable }

  async function chargerDroits() {
    try {
      const r = await fetch('/gestion_rh/droits');
      if (!r.ok) { $('#bloc-droits').classList.add('hidden'); return; }
      DR = await r.json();
      rendreDroits();
    } catch (_) { $('#bloc-droits').classList.add('hidden'); }
  }

  const nomPalier = (p) => L('st_' + p) || p;

  function rendreDroits() {
    if (!DR) return;
    const paliers = DR.paliers || [];
    const mod = !!DR.modifiable;

    const lignes = ORDRE_DROITS.filter((d) => DR.droits[d]).map((d) => {
      const sensible = d === 'parametres_admin';
      return `
      <tr class="${sensible ? 'is-sensible' : ''}">
        <th scope="row">
          <span>${esc(L('right_' + d))}</span>
          ${sensible ? `<em>${esc(L('right_parametres_admin_warn'))}</em>` : ''}
        </th>
        ${paliers.map((p) => {
          const coche = !!DR.droits[d][p];
          const verrou = p === 'admin';
          const change = !verrou && coche !== !!(DR.defaut[d] || {})[p];
          return `<td${change ? ' class="a-change"' : ''}>
            <label title="${esc(verrou ? L('rights_admin_locked')
                                       : (change ? L('rights_default') + ' : '
                                            + ((DR.defaut[d]||{})[p] ? '✓' : '—') : ''))}">
              <input type="checkbox" class="grh-droit" data-droit="${d}" data-palier="${p}"
                     ${coche ? 'checked' : ''} ${(verrou || !mod) ? 'disabled' : ''}>
            </label>
          </td>`;
        }).join('')}
      </tr>`;
    }).join('');

    $('#liste-droits').innerHTML = `
      <div class="grh-droits-wrap">
        <table class="grh-droits">
          <thead>
            <tr>
              <td></td>
              ${paliers.map((p) => `<th scope="col"
                class="${p === 'admin' ? 'is-locked' : ''}">${esc(nomPalier(p))}</th>`).join('')}
            </tr>
          </thead>
          <tbody>${lignes}</tbody>
        </table>
      </div>
      <p class="grh-droits-note">
        <i class="fa-solid fa-lock"></i> ${esc(L('rights_admin_locked'))}
        ${mod ? '' : ' · ' + esc(L('rights_readonly'))}
      </p>`;

    const bouton = $('#grh-droits-reset');
    if (bouton) {
      bouton.classList.toggle('hidden', !mod || !aUnEcart());
      bouton.onclick = () => enregistrerDroits(DR.defaut);
    }
    document.querySelectorAll('.grh-droit').forEach((c) =>
      c.addEventListener('change', () => {
        DR.droits[c.dataset.droit][c.dataset.palier] = c.checked;
        enregistrerDroits(DR.droits);
      }));
  }

  // Y a-t-il quoi que ce soit qui s'écarte de l'origine ? C'est ce qui décide
  // d'afficher « revenir aux valeurs d'origine » : un bouton toujours là
  // laisserait croire qu'on a réglé quelque chose.
  function aUnEcart() {
    return ORDRE_DROITS.some((d) => DR.droits[d] && Object.keys(DR.droits[d])
      .some((p) => p !== 'admin' && !!DR.droits[d][p] !== !!(DR.defaut[d] || {})[p]));
  }

  async function enregistrerDroits(table) {
    try {
      const d = await postJSON('/gestion_rh/droits', { droits: table });
      if (!d.ok) throw new Error();
      DR.droits = d.droits;
      rendreDroits();
      toast(L('rights_saved'));
    } catch (_) {
      toast(L('save_error'), 'error');
      chargerDroits();     // on relit plutôt que de laisser l'écran mentir
    }
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
              <em>${esc(L(unSeul(r.titulaires.length) ? 'holder_1' : 'holders'))}</em>
            </span>
          </button>
          <div class="grh-role-side">
            ${commune ? `
              <label class="grh-switch" title="${esc(L('opens_map_hint'))}">
                <input type="checkbox" class="grh-acces" value="${r.id}"
                       ${r.ouvre_carto ? 'checked' : ''} ${gere ? '' : 'disabled'}>
                <span>${esc(L('opens_map'))}</span>
              </label>` : ''}
            ${gere ? `
              <button type="button" class="grh-role-maps" data-maps="${r.id}"
                      title="${esc(L('role_maps_hint'))}">
                <i class="fa-solid fa-layer-group"></i>
                <span>${esc(L('role_maps'))}</span>
              </button>` : ''}
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
    document.querySelectorAll('[data-maps]').forEach((b) =>
      b.addEventListener('click', () => ouvrirCartos(parseInt(b.dataset.maps, 10))));
  }

  /* ── Un rôle, PLUSIEURS cartos ──────────────────────────────────────────
     Ouvrir une carto à un rôle se faisait carto par carto : changer l'entité
     en haut de page, cocher, recommencer. Et il n'existait aucun endroit d'où
     VOIR ce qu'un rôle ouvre au total. ⚠️ Cocher enregistre tout de suite,
     comme partout sur cette page : un bouton « Enregistrer » de plus laisse
     partir sans sauver, et l'écran ment alors sur qui a accès. */
  function ouvrirCartos(roleId) {
    fenetre = { mode: 'cartos', id: roleId, cartos: null };
    ouvrir();
    charger_cartos(roleId);
  }

  async function charger_cartos(roleId) {
    try {
      const r = await fetch(`/gestion_rh/role_cartos/${roleId}`);
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || '');
      if (fenetre && fenetre.mode === 'cartos' && fenetre.id === roleId) {
        fenetre.cartos = d.cartos || [];
        rendreFenetre();
      }
    } catch (_) {
      if (fenetre && fenetre.mode === 'cartos') { fenetre.cartos = []; rendreFenetre(); }
      toast(L('save_error'), 'error');
    }
  }

  async function enregistrerCartos(roleId) {
    const ids = [...document.querySelectorAll('.grh-map-pick:checked')]
      .map((c) => parseInt(c.value, 10));
    try {
      const d = await postJSON('/gestion_rh/role_cartos',
        { role_id: roleId, entity_ids: ids });
      if (!d.ok) throw new Error();
      toast(L('maps_saved'));
      // Une carto rendue commune change d'état : on relit plutôt que de
      // supposer, sinon l'avertissement affiché ne correspondrait plus.
      await charger_cartos(roleId);
      await charger({ discret: true });
    } catch (_) { toast(L('save_error'), 'error'); }
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

    if (fenetre.mode === 'cartos') {
      const r = roleParId(fenetre.id);
      $('#grh-modal-over').textContent = L('role_maps_title');
      $('#grh-modal-titre').textContent = r ? r.name : '—';
      if (fenetre.cartos === null) {
        $('#grh-modal-body').innerHTML =
          `<p class="grh-empty">${esc(L('loading'))}</p>`;
        return;
      }
      const liste = fenetre.cartos.filter((c) =>
        !q || (c.name || '').toLowerCase().includes(q));
      $('#grh-modal-body').innerHTML = liste.length
        ? `<p class="grh-modal-hint">${esc(L('role_maps_hint'))}</p>`
          + liste.map((c) => ligneCarto(c)).join('')
        : `<p class="grh-empty">${esc(L('maps_none'))}</p>`;
      document.querySelectorAll('.grh-map-pick').forEach((el) =>
        el.addEventListener('change', () => enregistrerCartos(fenetre.id)));
      return;
    }

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
      const devs = (D.personnes || []).filter((x) => x.est_dev && x.id !== p.id);
      // ⚠️ La liste détaillait sans jamais RÉSUMER : sur dix-neuf rôles dont
      // deux sont tenus, « lesquels sont suivis » ne se lisait qu'en parcourant
      // tout. Le compte est dit d'abord.
      const c = couverture(p);
      $('#grh-modal-body').innerHTML = roles.length
        ? `<div class="grh-dev-bilan${c.n && c.k === c.n ? ' is-complet' : ''}">
             <b>${esc(L('dev_roles_followed')
                        .replace('{k}', c.k).replace('{n}', c.n))}</b>
             <span>${esc(L('dev_per_role_hint'))}</span>
           </div>`
          + roles.map((r) => ligneRolePersonne(p, r, devs)).join('')
        : `<p class="grh-empty">${esc(L('roles_empty'))}</p>`;
    }

    document.querySelectorAll('.grh-pick').forEach((el) =>
      el.addEventListener('change', () => {
        const [u, r] = el.dataset.paire.split(':').map(Number);
        majLien(u, r, el.checked);
      }));
    document.querySelectorAll('.grh-devpick[data-role]').forEach((b) =>
      b.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation();
        ouvrirMenuDev(b); }));
  }

  // Une ligne de la fiche : tient-il ce rôle, et qui l'y suit.
  // ⚠️ Le sélecteur n'apparaît que sur un rôle RÉELLEMENT tenu : le lien
  // `user_roles` qui porterait le développeur n'existe pas avant, et la route
  // refuserait — autant le dire plutôt que d'offrir un bouton qui échoue.
  function ligneRolePersonne(p, r, devs) {
    const tenu = r.titulaires.includes(p.id);
    const devId = devDuRole(p, r.id);
    const dev = devs.find((d) => d.id === devId);
    return `
      <div class="grh-row grh-row--role${tenu && dev ? ' is-suivi' : ''}">
        <label class="grh-row-main">
          <span class="grh-role-dot${r.permanent ? ' is-permanent' : ''}"></span>
          <span class="grh-row-id">
            <b>${esc(r.name)}</b>
            ${r.ouvre_carto && D.entite && D.entite.is_shared
              ? `<span>${esc(L('opens_map'))}</span>` : ''}
          </span>
          <input type="checkbox" class="grh-pick" data-paire="${p.id}:${r.id}"
                 ${tenu ? 'checked' : ''}>
        </label>
        ${tenu ? `
          <button type="button" class="grh-devpick grh-devpick--row"
                  data-dev="${p.id}" data-role="${r.id}"
                  title="${esc(L('dev_for_role'))}">
            ${dev ? avatar(dev, 'xs') : '<span class="grh-devpick-none"></span>'}
            <span class="grh-devpick-name${dev ? '' : ' is-empty'}"
              >${esc(dev ? nomDe(dev) : L('dev_none'))}</span>
            <i class="fa-solid fa-chevron-down"></i>
          </button>`
          : `<span class="grh-row-note">${esc(L('dev_hold_first'))}</span>`}
      </div>`;
  }

  // ⚠️ Deux conséquences que l'écran doit annoncer AVANT le clic :
  //   · une carto PRIVÉE ignore les rôles — la cocher la rendra commune ;
  //   · une carto commune SANS aucun rôle autorisé est ouverte à TOUS, et y
  //     poser le premier rôle la RESTREINT : cocher peut retirer l'accès à
  //     des gens qui l'avaient. C'est le piège de cet écran.
  function ligneCarto(c) {
    const avertit = !c.commune ? L('map_will_share')
                  : (c.sans_filtre && !c.ouverte) ? L('map_open_to_all')
                  : L('map_n_roles').replace('{n}', c.n_roles);
    const grave = !c.commune || (c.sans_filtre && !c.ouverte);
    return `
      <label class="grh-row">
        <span class="grh-map-dot${c.commune ? ' is-shared' : ''}"></span>
        <span class="grh-row-id">
          <b>${esc(c.name)}</b>
          <span class="${grave ? 'grh-row-warn' : ''}">${esc(avertit)}</span>
        </span>
        <input type="checkbox" class="grh-map-pick" value="${c.id}"
               ${c.ouverte ? 'checked' : ''}>
      </label>`;
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
      if (menuOuvert && !menuOuvert.panneau.contains(e.target)
          && !e.target.closest('.grh-devmenu')) fermerMenuDev();
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
