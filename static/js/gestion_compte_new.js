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

  /* ── La fiche d'un compte ──────────────────────────────────────────── */
  function ouvrirFiche(ligne) {
    const f = $('#acc-fiche');
    if (!f) return;
    const form = $('#acc-form');
    const creation = !ligne;
    form.reset();
    if (creation) {
      form.action = CTX.urlCreate;
      $('#acc-fiche-titre').textContent = L('modal_new');
      $('#acc-fiche-sous').textContent = '';
      $('#acc-mdp').required = true;
      $('#acc-mdp-aide').textContent = L('pw_hint_new');
      $('#acc-mdp-etoile').hidden = false;
      $('#acc-valider').querySelector('span').textContent = L('btn_create');
    } else {
      const d = ligne.dataset;
      form.action = String(CTX.urlUpdate).replace(/0$/, d.id);
      $('#acc-fiche-titre').textContent = L('modal_edit');
      $('#acc-fiche-sous').textContent = d.email;
      $('#acc-prenom').value = d.prenom || '';
      $('#acc-nom').value = d.nomFamille || '';
      $('#acc-email').value = d.email || '';
      $('#acc-age').value = d.age || '';
      const sel = $('#acc-role-sel');
      if (sel) sel.value = d.roleId || '';
      const palier = $(`#acc-paliers input[value="${cssEchap(famillePourFormulaire(d.famille))}"]`);
      if (palier) palier.checked = true;
      // ⚠️ Un mot de passe vide ne change rien : c'est la seule façon de
      // modifier un nom sans toucher au mot de passe.
      $('#acc-mdp').required = false;
      $('#acc-mdp-aide').textContent = L('pw_hint_edit');
      $('#acc-mdp-etoile').hidden = true;
      $('#acc-valider').querySelector('span').textContent = L('btn_save');
    }
    f.hidden = false;
    document.body.classList.add('acc-modal-ouverte');
    setTimeout(() => $('#acc-prenom').focus(), 40);
  }

  // Le formulaire écrit « administrateur », la liste range en « admin ».
  const famillePourFormulaire = (f) => (f === 'admin' ? 'administrateur' : f || 'user');
  const cssEchap = (v) => String(v).replace(/"/g, '\\"');

  function fermerFiche() {
    const f = $('#acc-fiche');
    if (f) f.hidden = true;
    document.body.classList.remove('acc-modal-ouverte');
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
    // L'URL nettoyée : rafraîchir la page ne rejoue pas le message.
    if (msg || edit) window.history.replaceState({}, '', window.location.pathname);
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
        default:
      }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      fermerFiche();
      fermerSuppression();
    });

    chargerDroits();
    messageDeLUrl();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
