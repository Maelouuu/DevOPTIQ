/* ════════════════════════════════════════════════════════════════════
   Qui ouvre quelles cartos — la matrice rôles × cartos (page Carte).

   Un rôle en ligne, une carto en colonne : c'est la comparaison entre
   lignes qui renseigne, et une carto par écran obligeait à la tenir de tête.

   ⚠️ On envoie des CASES, jamais la table entière : cocher une colonne, c'est
   envoyer ses cases. Deux personnes qui règlent l'accès en même temps ne
   s'effacent donc pas l'une l'autre.
   ⚠️ Rien n'est masqué en guise de droit : `/api/access/matrice` refuse de
   son côté (Code/routes/carto_sharing.py).
   ════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const L = (cle) => (window.CACC_L || {})[cle] || cle;
  const P = (cle, n) => {
    const formes = String(L(cle)).split('|');
    const un = (L('lang') === 'fr') ? Math.abs(n) <= 1 : n === 1;
    return (un ? formes[0] : formes[formes.length - 1]).split('{n}').join(n);
  };
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const $ = (s, r) => (r || document).querySelector(s);

  let D = null;          // { cartos, roles }
  let filtre = '';
  let occupe = false;

  async function ouvrir() {
    const f = $('#cacc');
    if (!f) return;
    f.hidden = false;
    document.body.classList.add('cacc-ouvert');
    $('#cacc-corps').innerHTML = `<div class="cacc-attente"><i class="fa-solid fa-circle-notch fa-spin"></i></div>`;
    await charger();
  }

  function fermer() {
    const f = $('#cacc');
    if (f) f.hidden = true;
    document.body.classList.remove('cacc-ouvert');
  }

  async function charger() {
    try {
      const r = await fetch('/cartography/api/access/matrice', { credentials: 'same-origin' });
      D = await r.json();
      if (!r.ok) throw new Error(D.error || L('err'));
    } catch (e) {
      $('#cacc-corps').innerHTML = `<p class="cacc-err">${esc(e.message || L('err'))}</p>`;
      return;
    }
    rendre();
  }

  const ouvert = (role, eid) => (role.cartos || []).includes(eid);

  function rendre() {
    const zone = $('#cacc-corps');
    if (!D || !D.cartos.length) {
      zone.innerHTML = `<p class="cacc-vide">${esc(L('aucune'))}</p>`;
      return;
    }
    const q = filtre.trim().toLowerCase();
    const roles = D.roles.filter(r => !q
      || (r.nom || '').toLowerCase().includes(q) || (r.carto || '').toLowerCase().includes(q));

    const colonnes = D.cartos.map(c => {
      // Une carto dit son état : privée (cocher la rendra commune) ou ouverte
      // à tous (cocher la restreindra). C'est la conséquence, pas l'étiquette.
      const etat = !c.commune ? `<em class="est-privee">${esc(L('privee'))}</em>`
        : (c.ouverte_a_tous ? `<em class="est-ouverte">${esc(L('ouverte'))}</em>`
          : `<em>${esc(P('n_roles', c.n_roles))}</em>`);
      return `<th scope="col">
        <button type="button" class="cacc-col" data-carto="${c.id}" title="${esc(L('tout_carto'))}">
          <span>${esc(c.name)}</span>${etat}
        </button>
      </th>`;
    }).join('');

    const lignes = roles.map(r => `
      <tr data-role="${r.id}">
        <th scope="row">
          <button type="button" class="cacc-lig" data-role="${r.id}" title="${esc(L('tout_role'))}">
            <span>${esc(r.nom)}</span><em>${esc(r.carto)}</em>
          </button>
        </th>
        ${D.cartos.map(c => `<td>
          <label><input type="checkbox" class="cacc-case" data-role="${r.id}" data-carto="${c.id}"
                        ${ouvert(r, c.id) ? 'checked' : ''}></label>
        </td>`).join('')}
      </tr>`).join('');

    zone.innerHTML = `
      <div class="cacc-table-wrap">
        <table class="cacc-table">
          <thead><tr><td class="cacc-coin">${esc(L('role'))}</td>${colonnes}</tr></thead>
          <tbody>${lignes || `<tr><td colspan="${D.cartos.length + 1}" class="cacc-vide">${esc(L('vide'))}</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  /* Cocher une colonne ou une ligne = envoyer ses cases. Si tout est déjà
     coché, le même clic décoche : un bouton qui ne fait rien la deuxième fois
     laisse croire qu'il a échoué. */
  function casesColonne(eid) {
    const tous = D.roles.every(r => ouvert(r, eid));
    return D.roles.map(r => ({ role_id: r.id, entity_id: eid, on: !tous }));
  }

  function casesLigne(rid) {
    const role = D.roles.find(r => r.id === rid);
    if (!role) return [];
    const tous = D.cartos.every(c => ouvert(role, c.id));
    return D.cartos.map(c => ({ role_id: rid, entity_id: c.id, on: !tous }));
  }

  async function envoyer(cases) {
    if (occupe || !cases.length) return;
    occupe = true;
    $('#cacc-corps').classList.add('est-occupe');
    try {
      const r = await fetch('/cartography/api/access/matrice', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cases }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || L('err'));
      D = d;
      rendre();
      const communes = (d.rendues_communes || []).length;
      message(communes ? L('enregistre') + ' · ' + P('commune_faite', communes) : L('enregistre'));
    } catch (e) {
      message(e.message || L('err'), true);
      charger();          // on relit plutôt que de laisser l'écran mentir
    }
    occupe = false;
    $('#cacc-corps').classList.remove('est-occupe');
  }

  let minuterie = null;
  function message(texte, erreur) {
    let t = $('#cacc-msg');
    if (!t) {
      t = document.createElement('div');
      t.id = 'cacc-msg';
      t.className = 'cacc-msg';
      document.body.appendChild(t);
    }
    t.textContent = texte;
    t.classList.toggle('est-err', !!erreur);
    t.classList.add('on');
    clearTimeout(minuterie);
    minuterie = setTimeout(() => t.classList.remove('on'), 3000);
  }

  function brancher() {
    const bouton = document.getElementById('btn-carto-acces');
    if (bouton) bouton.addEventListener('click', ouvrir);
    const f = $('#cacc');
    if (!f) return;
    f.addEventListener('click', (e) => {
      const el = e.target.closest('[data-cacc], .cacc-col, .cacc-lig');
      if (!el) return;
      if (el.dataset.cacc === 'fermer') return fermer();
      if (el.classList.contains('cacc-col')) return envoyer(casesColonne(Number(el.dataset.carto)));
      if (el.classList.contains('cacc-lig')) return envoyer(casesLigne(Number(el.dataset.role)));
    });
    f.addEventListener('change', (e) => {
      const el = e.target;
      if (!el.classList.contains('cacc-case')) return;
      envoyer([{ role_id: Number(el.dataset.role), entity_id: Number(el.dataset.carto),
                 on: el.checked }]);
    });
    const q = $('#cacc-q');
    if (q) q.addEventListener('input', () => { filtre = q.value; rendre(); });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !f.hidden) fermer();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', brancher);
  else brancher();
})();
