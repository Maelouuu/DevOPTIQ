/* ════════════════════════════════════════════════════════════════════
   Page Comptes — la liste, la fiche d'un compte, ce que chaque palier ouvre.

   Une seule liste, rendue par le serveur : on ne filtre ici que l'affichage.
   ⚠️ Créer et modifier passent par la MÊME fiche — ce sont les mêmes
   questions, et deux écrans finissaient par ne plus se ressembler.
   ⚠️ Rien de ce qui est masqué ici n'est un droit : chaque route refuse de
   son côté (Code/routes/gestion_compte.py).
   ════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const CTX = window.ACC_CTX || {};
  const L = (cle) => (window.ACC_L || {})[cle] || cle;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ── La liste : filtrer ce qui est déjà là ─────────────────────────── */
  let filtre = 'tous';

  function filtrer() {
    const q = ($('#acc-q').value || '').trim().toLowerCase();
    const role = $('#acc-role').value;
    let n = 0;
    $$('.acc-ligne').forEach((l) => {
      const ok = (filtre === 'tous' || l.dataset.famille === filtre)
        && (!q || l.dataset.nom.toLowerCase().includes(q))
        && (!role || (l.dataset.roles || '').split('|').includes(role));
      l.hidden = !ok;
      if (ok) n += 1;
    });
    $('#acc-rien').hidden = n > 0;
  }

  /* ── La fiche d'un compte ──────────────────────────────────────────────
     À gauche qui est la personne, à droite ce qu'elle peut faire. L'en-tête
     suit la saisie (initiales, nom, niveau choisi) : on voit QUI on règle.
     ⚠️ Les rôles bougent PAR PAIRE : la fiche envoie ce qu'on ajoute et ce
     qu'on retire, jamais « la liste complète » — un rôle tenu sur une carto
     qu'on ne voit pas ici ne doit pas disparaître parce qu'on a corrigé un
     nom. */
  const FICHE = {
    ligne: null,          // la ligne de la liste ; null = création
    roles: [],            // les rôles tenus à l'ouverture
    ajout: new Map(),     // id → rôle ajouté
    retrait: new Set(),   // ids retirés
    mdpOuvert: false,
    depart: null,         // la fiche à l'ouverture : repère des modifications
  };
  const PALIERS = ['user', 'champion', 'coordinateur', 'administrateur'];
  // Le formulaire écrit « administrateur », la liste range en « admin ».
  const famillePourFormulaire = (f) => (f === 'admin' ? 'administrateur' : f || 'user');
  const familleDuPalier = (p) => (p === 'administrateur' ? 'admin' : p || 'user');
  const cssEchap = (v) => String(v).replace(/"/g, '\\"');

  // « 0 modification » en français, « 0 changes » en anglais : le catalogue
  // porte les deux formes, « un|plusieurs ».
  function P(cle, n) {
    const formes = L(cle).split('|');
    const un = CTX.lang === 'en' ? n === 1 : n <= 1;
    return (un ? formes[0] : formes[formes.length - 1]).split('{n}').join(n);
  }

  const creation = () => !FICHE.ligne;
  const palierChoisi = () => ($('#acc-paliers input:checked') || {}).value || 'user';

  function ouvrirFiche(ligne) {
    const f = $('#acc-fiche');
    if (!f) return;
    const form = $('#acc-form');
    form.reset();
    FICHE.ligne = ligne || null;
    FICHE.ajout = new Map();
    FICHE.retrait = new Set();
    FICHE.roles = [];
    effacerErreurs();
    if (!ligne) {
      form.action = CTX.urlCreate;
      $('#acc-fiche-titre').textContent = L('modal_new');
      $('#acc-valider span').textContent = L('btn_create');
    } else {
      const d = ligne.dataset;
      form.action = String(CTX.urlUpdate).replace(/0$/, d.id);
      $('#acc-fiche-titre').textContent = L('modal_edit');
      $('#acc-prenom').value = d.prenom || '';
      $('#acc-nom').value = d.nomFamille || '';
      $('#acc-email').value = d.email || '';
      $('#acc-age').value = d.age || '';
      try { FICHE.roles = JSON.parse(d.rolesJson || '[]'); } catch (_) { FICHE.roles = []; }
      const palier = $(`#acc-paliers input[value="${cssEchap(famillePourFormulaire(d.famille))}"]`);
      if (palier) palier.checked = true;
      $('#acc-valider span').textContent = L('btn_save');
    }
    reglerMdp(!ligne);
    reglerEchelle();
    reglerRoles();
    majEntete();
    FICHE.depart = photo();
    majEtat();
    f.hidden = false;
    document.body.classList.add('acc-modal-ouverte');
    setTimeout(() => $('#acc-prenom').focus(), 40);
  }

  function fermerFiche() {
    const f = $('#acc-fiche');
    if (!f || f.hidden) return;
    fermerAjout();
    f.hidden = true;
    document.body.classList.remove('acc-modal-ouverte');
  }

  /* L'en-tête : la personne telle qu'on est en train de la décrire. */
  function majEntete() {
    const prenom = $('#acc-prenom').value.trim();
    const nom = $('#acc-nom').value.trim();
    const famille = familleDuPalier(palierChoisi());
    const av = $('#acc-fiche-av');
    const initiales = ((prenom[0] || '') + (nom[0] || '')).toUpperCase();
    av.className = 'acc-fiche-av acc-av--' + famille;
    av.innerHTML = initiales ? esc(initiales) : '<i class="fa-solid fa-user-plus"></i>';
    $('#acc-fiche-nom').textContent = `${prenom} ${nom}`.trim() || L('modal_new');
    $('#acc-fiche-mail').textContent = $('#acc-email').value.trim();
    const puce = $('#acc-fiche-statut');
    puce.className = 'acc-statut s-' + famille;
    puce.textContent = L('st_' + palierChoisi() + '_f');
  }

  /* Le mot de passe : ouvert d'office à la création, sur demande ensuite. */
  function reglerMdp(ouvert) {
    FICHE.mdpOuvert = !!ouvert;
    const zone = $('#acc-mdp-zone');
    zone.dataset.ouvert = ouvert ? '1' : '0';
    zone.dataset.creation = creation() ? '1' : '0';
    const champ = $('#acc-mdp');
    champ.value = '';
    champ.type = 'password';
    $('#acc-mdp-etoile').hidden = !creation();
    $('#acc-mdp-genere').hidden = true;
    majOeil();
  }

  function majOeil() {
    const visible = $('#acc-mdp').type === 'text';
    const b = $('[data-action="mdp-voir"]');
    b.innerHTML = `<i class="fa-solid ${visible ? 'fa-eye-slash' : 'fa-eye'}"></i>`;
    b.title = L(visible ? 'pw_hide' : 'pw_show');
    b.setAttribute('aria-label', b.title);
  }

  // Sans 0/O ni 1/l/I : un mot de passe provisoire se recopie à la main.
  function genererMdp() {
    const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
    const speciaux = '!?#@%+';
    const tirage = new Uint32Array(12);
    (window.crypto || window.msCrypto).getRandomValues(tirage);
    let mdp = '';
    tirage.forEach((v, i) => {
      mdp += (i === 5 || i === 10) ? speciaux[v % speciaux.length] : alphabet[v % alphabet.length];
    });
    const champ = $('#acc-mdp');
    champ.value = mdp;
    champ.type = 'text';
    majOeil();
    $('#acc-mdp-genere').hidden = false;
    champ.dispatchEvent(new Event('input', { bubbles: true }));
  }

  /* L'échelle des niveaux d'accès. */
  function reglerEchelle() {
    const moiMeme = !creation() && Number(FICHE.ligne.dataset.id) === Number(CTX.moi);
    $$('#acc-paliers .acc-marche').forEach((m) => {
      const niv = Number(m.dataset.niveau);
      // ⚠️ On ne crée pas au-dessus de soi ; on ne change que si l'on est
      // administrateur, et jamais son propre niveau. Le serveur refuse de
      // son côté : l'échelle éteinte n'est qu'une politesse.
      const actif = creation() ? niv <= Number(CTX.monNiveau) : (CTX.estAdmin && !moiMeme);
      m.querySelector('input').disabled = !actif;
      m.classList.toggle('is-off', !actif);
      m.title = (!actif && creation()) ? L('status_above') : '';
    });
    const note = $('#acc-statut-note');
    const texte = creation() ? '' : (moiMeme ? L('status_locked_self')
      : (CTX.estAdmin ? '' : L('status_locked_admin')));
    note.hidden = !texte;
    note.querySelector('span').textContent = texte;
    majMarches();
  }

  function majMarches() {
    const k = PALIERS.indexOf(palierChoisi());
    $$('#acc-paliers .acc-marche').forEach((m) => {
      const niv = Number(m.dataset.niveau);
      m.classList.toggle('is-choisi', niv === k);
      // Chaque palier ajoute aux droits du précédent : les marches du
      // dessous restent allumées, c'est ce que « échelle » veut dire.
      m.classList.toggle('is-inclus', niv < k);
    });
  }

  /* Les rôles de l'entreprise. */
  function reglerRoles() {
    $('#acc-ajout').hidden = !CTX.gereRoles;
    $('#acc-roles-note').hidden = !!CTX.gereRoles;
    fermerAjout();
    rendreRoles();
  }

  function rendreRoles() {
    const zone = $('#acc-roles-zone');
    const affiches = FICHE.roles.concat(Array.from(FICHE.ajout.values()));
    if (!affiches.length) {
      zone.innerHTML = `<p class="acc-roles-vide">${esc(L('roles_none'))}</p>`;
      return;
    }
    zone.innerHTML = `<div class="acc-puces">${affiches.map(puce).join('')}</div>`;
  }

  function puce(r) {
    const nouveau = FICHE.ajout.has(r.id);
    const retire = FICHE.retrait.has(r.id);
    const modifiable = CTX.gereRoles;
    let bouton = '';
    if (modifiable) {
      bouton = retire
        ? `<button type="button" class="acc-puce-btn" data-action="role-remettre" data-id="${r.id}"
                   title="${esc(L('roles_undo'))}" aria-label="${esc(L('roles_undo'))}"><i class="fa-solid fa-rotate-left"></i></button>`
        : `<button type="button" class="acc-puce-btn" data-action="role-retirer" data-id="${r.id}"
                   title="${esc(L('roles_remove'))}" aria-label="${esc(L('roles_remove'))}"><i class="fa-solid fa-xmark"></i></button>`;
    }
    return `<span class="acc-puce${nouveau ? ' is-ajoute' : ''}${retire ? ' is-retire' : ''}">
        <span class="acc-puce-nom">${esc(r.name)}</span>
        ${nouveau ? `<em>${esc(L('roles_new'))}</em>` : ''}${retire ? `<em>${esc(L('roles_removed'))}</em>` : ''}
        ${bouton}
      </span>`;
  }

  function ouvrirAjout() {
    const p = $('#acc-ajout-panneau');
    p.hidden = false;
    $('[data-action="roles-ouvrir"]').setAttribute('aria-expanded', 'true');
    $('#acc-ajout-q').value = '';
    rendreAjout();
    setTimeout(() => $('#acc-ajout-q').focus(), 20);
  }

  function fermerAjout() {
    const p = $('#acc-ajout-panneau');
    if (p) p.hidden = true;
    const b = $('[data-action="roles-ouvrir"]');
    if (b) b.setAttribute('aria-expanded', 'false');
  }

  function rendreAjout() {
    const q = ($('#acc-ajout-q').value || '').trim().toLowerCase();
    const tenus = new Set(FICHE.roles.filter((r) => !FICHE.retrait.has(r.id)).map((r) => r.id));
    FICHE.ajout.forEach((_, id) => tenus.add(id));
    const libres = (window.ACC_ROLES || []).filter((r) => !tenus.has(r.id));
    const restant = libres.length;
    const vus = libres.filter((r) => !q || r.name.toLowerCase().includes(q));
    const html = vus.map((r) => `<button type="button" class="acc-ajout-item"
        data-action="role-ajouter" data-id="${r.id}">${esc(r.name)}</button>`).join('');
    $('#acc-ajout-liste').innerHTML = html
      || `<p class="acc-ajout-vide">${esc(L(restant ? 'roles_no_match' : 'roles_nothing_left'))}</p>`;
  }

  function ajouterRole(id) {
    if (FICHE.retrait.has(id)) {
      FICHE.retrait.delete(id);             // on revient sur un retrait : rien à AJOUTER
    } else {
      const r = (window.ACC_ROLES || []).find((x) => x.id === id);
      if (!r) return;
      FICHE.ajout.set(id, { id, name: r.name });
    }
    rendreRoles();
    rendreAjout();
    majEtat();
  }

  function retirerRole(id) {
    if (FICHE.ajout.has(id)) FICHE.ajout.delete(id);   // un ajout qu'on annule disparaît
    else FICHE.retrait.add(id);                        // un rôle tenu reste visible, barré
    rendreRoles();
    majEtat();
  }

  function remettreRole(id) {
    FICHE.retrait.delete(id);
    rendreRoles();
    majEtat();
  }

  /* Ce qui a changé depuis l'ouverture. */
  function photo() {
    return {
      first_name: $('#acc-prenom').value.trim(),
      last_name: $('#acc-nom').value.trim(),
      age: $('#acc-age').value.trim(),
      email: $('#acc-email').value.trim(),
      status: palierChoisi(),
    };
  }

  function nbModifs() {
    const avant = FICHE.depart || {};
    const maintenant = photo();
    let n = Object.keys(maintenant).filter((k) => maintenant[k] !== avant[k]).length;
    if (FICHE.mdpOuvert && $('#acc-mdp').value) n += 1;
    return n + FICHE.ajout.size + FICHE.retrait.size;
  }

  // En modification, « Enregistrer » ne s'allume que s'il y a quelque chose
  // à enregistrer — et le pied dit combien.
  function majEtat() {
    const bouton = $('#acc-valider');
    const etat = $('#acc-pied-etat');
    if (creation()) {
      etat.textContent = '';
      bouton.disabled = false;
      return;
    }
    const n = nbModifs();
    etat.textContent = n ? P('changes_n', n) : L('changes_none');
    etat.classList.toggle('is-modifie', n > 0);
    bouton.disabled = n === 0;
  }

  /* Les erreurs s'écrivent SOUS le champ fautif. */
  const ERREURS = {
    error_email_exists: 'err_email_exists',
    error_missing_name: 'err_missing_name',
    error_missing_email: 'err_missing_email',
    error_missing_password: 'err_password_short',
    error_invalid_age: 'err_invalid_age',
    error_status_too_high: 'err_status_too_high',
    error_role_unknown: 'err_role_unknown',
    error_forbidden_roles: 'err_forbidden_roles',
    error_forbidden_create: 'err_forbidden',
    error_forbidden_edit: 'err_forbidden',
  };

  function effacerErreurs() {
    $$('#acc-fiche [data-champ].is-err').forEach((c) => c.classList.remove('is-err'));
    $$('#acc-fiche .acc-champ-err').forEach((s) => { s.textContent = ''; });
    const a = $('#acc-fiche-alerte');
    a.hidden = true;
    a.textContent = '';
  }

  function montrerErreur(champ, texte) {
    const zone = champ && $(`#acc-fiche [data-champ="${cssEchap(champ)}"]`);
    if (!zone) {
      const a = $('#acc-fiche-alerte');
      a.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i><span>${esc(texte)}</span>`;
      a.hidden = false;
      return;
    }
    zone.classList.add('is-err');
    const s = zone.querySelector('.acc-champ-err');
    if (s) s.textContent = texte;
    const saisie = zone.querySelector('input:not([type=radio])');
    if (saisie) saisie.focus();
  }

  function valider() {
    let ok = true;
    const echec = (champ, cle) => {
      if (ok) montrerErreur(champ, L(cle));
      else {
        const z = $(`#acc-fiche [data-champ="${champ}"]`);
        if (z) { z.classList.add('is-err'); z.querySelector('.acc-champ-err').textContent = L(cle); }
      }
      ok = false;
    };
    const v = photo();
    if (!v.first_name) echec('first_name', 'err_missing_name');
    if (!v.last_name) echec('last_name', 'err_missing_name');
    if (!v.email) echec('email', 'err_missing_email');
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.email)) echec('email', 'err_email_format');
    if (v.age && !/^\d+$/.test(v.age)) echec('age', 'err_invalid_age');
    const mdp = $('#acc-mdp').value;
    if ((creation() && mdp.length < 6) || (!creation() && FICHE.mdpOuvert && mdp && mdp.length < 6)) {
      echec('password', 'err_password_short');
    }
    return ok;
  }

  async function envoyer(e) {
    e.preventDefault();
    effacerErreurs();
    if (!valider()) return;
    if (!creation() && nbModifs() === 0) return;
    const form = $('#acc-form');
    const donnees = new FormData(form);
    if (!FICHE.mdpOuvert || !$('#acc-mdp').value) donnees.delete('password');
    FICHE.ajout.forEach((_, id) => donnees.append('roles_ajout', id));
    FICHE.retrait.forEach((id) => donnees.append('roles_retrait', id));

    const bouton = $('#acc-valider');
    const avant = bouton.innerHTML;
    bouton.disabled = true;
    bouton.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>${esc(L('saving'))}</span>`;
    try {
      const rep = await fetch(form.action, {
        method: 'POST', body: donnees, credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      const d = await rep.json().catch(() => ({}));
      if (rep.ok && d.ok) {
        // La liste est rendue par le serveur : on la relit plutôt que de la
        // rafistoler ligne par ligne.
        window.location.href = window.location.pathname + '?msg=' + encodeURIComponent(d.code);
        return;
      }
      montrerErreur(d.champ || null, L(ERREURS[d.code] || 'err_generic'));
    } catch (_) {
      montrerErreur(null, L('err_generic'));
    }
    bouton.innerHTML = avant;
    majEtat();
  }

  function brancherFiche() {
    const form = $('#acc-form');
    if (!form) return;
    form.addEventListener('submit', envoyer);
    form.addEventListener('input', (e) => {
      const z = e.target.closest('[data-champ]');
      if (z && z.classList.contains('is-err')) {
        z.classList.remove('is-err');
        z.querySelector('.acc-champ-err').textContent = '';
      }
      if (e.target.id === 'acc-ajout-q') { rendreAjout(); return; }
      majEntete();
      majEtat();
    });
    form.addEventListener('change', (e) => {
      if (e.target.name === 'status') { majMarches(); majEntete(); majEtat(); }
    });
    // Un clic hors du sélecteur de rôles le referme.
    // ⚠️ Choisir un rôle REDESSINE la liste : quand le clic remonte jusqu'ici,
    // l'élément cliqué est déjà détaché et `closest()` ne trouve plus rien —
    // le sélecteur se refermait à chaque ajout. Un élément détaché venait
    // forcément de l'intérieur.
    document.addEventListener('click', (e) => {
      const p = $('#acc-ajout-panneau');
      if (!p || p.hidden || !e.target.isConnected) return;
      if (!e.target.closest('#acc-ajout')) fermerAjout();
    });
  }

  function ouvrirSuppression(id, qui) {
    $('#acc-suppr-qui').textContent = qui;
    $('#acc-suppr-form').action = String(CTX.urlDelete).replace(/0$/, id);
    $('#acc-suppr').hidden = false;
    document.body.classList.add('acc-modal-ouverte');
  }

  function fermerSuppression() {
    $('#acc-suppr').hidden = true;
    document.body.classList.remove('acc-modal-ouverte');
  }

  /* ── ② Ce que chaque palier ouvre ───────────────────────────────────
     Une MATRICE, pas une liste : on lit un droit en ligne et un palier en
     colonne, et c'est la comparaison entre paliers qui renseigne.

     ⚠️ La colonne `admin` est cochée et VERROUILLÉE. Se retirer les
     Paramètres, ce serait perdre l'écran depuis lequel on les remettrait —
     la porte se refermerait de l'intérieur, sans poignée. */
  const ORDRE_DROITS = ['propose_carto', 'edit_carto', 'review_carto', 'manage_acces',
                        'acces_rh', 'cree_comptes', 'parametres_admin'];
  let DR = null;

  async function chargerDroits() {
    try {
      const r = await fetch('/comptes/droits', { credentials: 'same-origin' });
      if (!r.ok) return;                 // pas le droit de lire : le bloc reste absent
      DR = await r.json();
      $('#acc-bloc-droits').hidden = false;
      rendreDroits();
    } catch (_) { /* le bloc reste absent : il n'est pas le sujet de la page */ }
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
          <span>${esc(L('droit_' + d))}</span>
          ${sensible ? `<em>${esc(L('droit_parametres_admin_warn'))}</em>` : ''}
        </th>
        ${paliers.map((p) => {
          const coche = !!DR.droits[d][p];
          const verrou = p === 'admin';
          const change = !verrou && coche !== !!(DR.defaut[d] || {})[p];
          const bulle = verrou ? L('admin_verrou')
            : (change ? L('defaut') + ' : ' + ((DR.defaut[d] || {})[p] ? '✓' : '—') : '');
          return `<td${change ? ' class="a-change"' : ''}>
            <label title="${esc(bulle)}">
              <input type="checkbox" class="acc-droit" data-droit="${d}" data-palier="${p}"
                     ${coche ? 'checked' : ''} ${(verrou || !mod) ? 'disabled' : ''}>
            </label>
          </td>`;
        }).join('')}
      </tr>`;
    }).join('');

    $('#acc-droits').innerHTML = `
      <div class="acc-droits-wrap">
        <table class="acc-droits">
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
      <p class="acc-droits-note">
        <i class="fa-solid fa-lock"></i> ${esc(L('admin_verrou'))}
        ${mod ? '' : ' · ' + esc(L('lecture_seule'))}
      </p>`;

    const bouton = $('#acc-droits-reset');
    if (bouton) {
      bouton.hidden = !mod || !aUnEcart();
      bouton.onclick = () => enregistrerDroits(DR.defaut);
    }
    $$('.acc-droit').forEach((c) => c.addEventListener('change', () => {
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
      const r = await fetch('/comptes/droits', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ droits: table }),
      });
      const d = await r.json();
      if (!r.ok || !d.ok) throw new Error();
      DR.droits = d.droits;
      rendreDroits();
      toast(L('enregistre'));
    } catch (_) {
      toast(L('err_save'), true);
      chargerDroits();      // on relit plutôt que de laisser l'écran mentir
    }
  }

  /* ── Messages ──────────────────────────────────────────────────────── */
  let minuterie = null;
  function toast(texte, erreur) {
    const t = $('#acc-toast');
    if (!t) return;
    t.textContent = texte;
    t.classList.toggle('is-err', !!erreur);
    t.classList.add('on');
    clearTimeout(minuterie);
    minuterie = setTimeout(() => t.classList.remove('on'), 3200);
  }

  const MESSAGES = {
    created: () => L('msg_created'),
    updated: () => L('msg_updated'),
    deleted: () => L('msg_deleted'),
  };

  function messageDeLUrl() {
    const p = new URLSearchParams(window.location.search);
    const msg = p.get('msg');
    if (msg) {
      const lib = MESSAGES[msg] ? MESSAGES[msg]() : L('msg_error');
      setTimeout(() => toast(lib, !MESSAGES[msg]), 120);
    }
    const edit = p.get('edit');
    if (edit) {
      const ligne = $(`.acc-ligne[data-id="${cssEchap(edit)}"]`);
      if (ligne) setTimeout(() => ouvrirFiche(ligne), 60);
    }
    // On arrive de la carte, qui renvoie ici une liste de collaborateurs :
    // la fenêtre d'import s'ouvre d'elle-même, sinon il faudrait redire quoi
    // faire à quelqu'un qu'on vient d'envoyer ici pour ça.
    if (p.get('import') && window.OptiqImport) {
      setTimeout(() => window.OptiqImport.ouvrir('comptes'), 80);
    }
    // L'URL nettoyée : rafraîchir la page ne rejoue pas le message.
    if (msg || edit || p.get('import')) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  }

  /* ── Branchements ──────────────────────────────────────────────────── */
  function init() {
    if (!$('.acc')) return;
    $('#acc-q').addEventListener('input', filtrer);
    $('#acc-role').addEventListener('change', filtrer);
    $$('.acc-tuile').forEach((b) => b.addEventListener('click', () => {
      filtre = b.dataset.filtre;
      $$('.acc-tuile').forEach((x) => {
        x.classList.toggle('on', x === b);
        x.setAttribute('aria-pressed', String(x === b));
      });
      filtrer();
    }));

    document.addEventListener('click', (e) => {
      const el = e.target.closest('[data-action]');
      if (!el) return;
      switch (el.dataset.action) {
        case 'nouveau': return ouvrirFiche(null);
        case 'modifier': return ouvrirFiche(el.closest('.acc-ligne'));
        case 'supprimer': return ouvrirSuppression(el.dataset.id, el.dataset.qui);
        case 'fermer-fiche': return fermerFiche();
        case 'fermer-suppr': return fermerSuppression();
        case 'mdp-ouvrir':
          reglerMdp(true);
          majEtat();
          return setTimeout(() => $('#acc-mdp').focus(), 20);
        case 'mdp-fermer': reglerMdp(false); return majEtat();
        case 'mdp-voir': {
          const c = $('#acc-mdp');
          c.type = c.type === 'password' ? 'text' : 'password';
          return majOeil();
        }
        case 'mdp-generer': return genererMdp();
        case 'mdp-copier': {
          const valeur = $('#acc-mdp').value;
          if (!valeur || !navigator.clipboard) return undefined;
          return navigator.clipboard.writeText(valeur).then(() => {
            el.textContent = L('pw_copied');
            setTimeout(() => { el.textContent = L('pw_copy'); }, 1600);
          }).catch(() => {});
        }
        case 'roles-ouvrir': {
          const panneau = $('#acc-ajout-panneau');
          return panneau.hidden ? ouvrirAjout() : fermerAjout();
        }
        case 'role-ajouter': return ajouterRole(Number(el.dataset.id));
        case 'role-retirer': return retirerRole(Number(el.dataset.id));
        case 'role-remettre': return remettreRole(Number(el.dataset.id));
        default:
      }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      // Le sélecteur de rôles d'abord : Échap le referme sans fermer la fiche.
      const p = $('#acc-ajout-panneau');
      if (p && !p.hidden) { fermerAjout(); return; }
      fermerFiche();
      fermerSuppression();
    });
    brancherFiche();

    chargerDroits();
    messageDeLUrl();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
