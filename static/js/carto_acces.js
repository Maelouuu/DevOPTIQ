/* ════════════════════════════════════════════════════════════════════
   Qui ouvre quelles cartos — page Carte. Deux matrices : les RÔLES et les
   STATUTS, une carto par colonne.

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

  let D = null;          // { cartos, roles, statuts }
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

  const ouvert = (ligne, eid) => (ligne.cartos || []).includes(eid);

  function colonnes(sec) {
    return D.cartos.map(c => {
      const combien = sec === 'statut'
        ? P('n_statuts', (D.statuts || []).filter(s => ouvert(s, c.id)).length)
        : P('n_roles', c.n_roles);
      const etat = !c.commune ? `<em class="est-privee">${esc(L('privee'))}</em>`
        : (sec === 'role' && c.ouverte_a_tous
          ? `<em class="est-ouverte">${esc(L('ouverte'))}</em>`
          : `<em>${esc(combien)}</em>`);
      return `<th scope="col">
        <button type="button" class="cacc-col" data-carto="${c.id}" data-sec="${sec}"
                title="${esc(L('tout_carto'))}">
          <span>${esc(c.name)}</span>${etat}
        </button>
      </th>`;
    }).join('');
  }

  function table(sec, coin, lignes, titreLigne) {
    const corps = lignes.map(l => `
      <tr${l.verrou ? ' class="est-verrou"' : ''}>
        <th scope="row">
          ${l.verrou
            ? `<span class="cacc-lig est-verrou" title="${esc(L('verrou'))}">
                 <span>${esc(l.nom)}</span><i class="fa-solid fa-lock"></i>
               </span>`
            : `<button type="button" class="cacc-lig" data-cle="${esc(String(l.id))}" data-sec="${sec}"
                       title="${esc(titreLigne)}"><span>${esc(l.nom)}</span></button>`}
        </th>
        ${D.cartos.map(c => `<td>
          <label><input type="checkbox" class="cacc-case" data-sec="${sec}"
                        data-cle="${esc(String(l.id))}" data-carto="${c.id}"
                        ${ouvert(l, c.id) ? 'checked' : ''}
                        ${l.verrou ? 'disabled' : ''}></label>
        </td>`).join('')}
      </tr>`).join('');
    return `<div class="cacc-table-wrap">
        <table class="cacc-table">
          <thead><tr><td class="cacc-coin">${esc(coin)}</td>${colonnes(sec)}</tr></thead>
          <tbody>${corps || `<tr><td colspan="${D.cartos.length + 1}" class="cacc-vide">${esc(L('vide'))}</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  function rendre() {
    const zone = $('#cacc-corps');
    if (!D || !D.cartos.length) {
      zone.innerHTML = `<p class="cacc-vide">${esc(L('aucune'))}</p>`;
      return;
    }
    const q = filtre.trim().toLowerCase();
    const roles = D.roles
      .filter(r => !q || (r.nom || '').toLowerCase().includes(q))
      .map(r => ({ id: r.id, nom: r.nom, cartos: r.cartos }));
    const statuts = (D.statuts || [])
      .map(s => ({ id: s.cle, nom: s.nom, cartos: s.cartos, verrou: !!s.verrou }));

    zone.innerHTML = `
      <section class="cacc-sec cacc-sec--roles">
        <h4 class="cacc-sec-tete"><i class="fa-solid fa-id-badge"></i>${esc(L('sec_roles'))}</h4>
        ${table('role', L('role'), roles, L('tout_role'))}
      </section>
      <section class="cacc-sec cacc-sec--statuts">
        <h4 class="cacc-sec-tete"><i class="fa-solid fa-shield-halved"></i>${esc(L('sec_statuts'))}</h4>
        ${table('statut', L('statut'), statuts, L('tout_statut'))}
      </section>`;
    accorderDefilement(zone);
  }

  /* Les deux tables ont les MÊMES colonnes : chacune défile de son côté, et
     lire un statut sous une carto qui n'est plus la même ne veut rien dire. */
  function accorderDefilement(zone) {
    const wraps = [].slice.call(zone.querySelectorAll('.cacc-table-wrap'));
    let enCours = false;
    wraps.forEach((w) => w.addEventListener('scroll', () => {
      if (enCours) return;
      enCours = true;
      wraps.forEach((autre) => { if (autre !== w) autre.scrollLeft = w.scrollLeft; });
      enCours = false;
    }));
  }

  /* Cocher une colonne ou une ligne = envoyer ses cases. Si tout est déjà
     coché, le même clic décoche : un bouton qui ne fait rien la deuxième fois
     laisse croire qu'il a échoué. */
  function casesColonne(eid, sec) {
    if (sec === 'statut') {
      const st = (D.statuts || []).filter(s => !s.verrou);
      const tous = st.every(s => ouvert(s, eid));
      return { cases_statut: st.map(s => ({ statut: s.cle, entity_id: eid, on: !tous })) };
    }
    const tous = D.roles.every(r => ouvert(r, eid));
    return { cases: D.roles.map(r => ({ role_id: r.id, entity_id: eid, on: !tous })) };
  }

  function casesLigne(cle, sec) {
    if (sec === 'statut') {
      const s = (D.statuts || []).find(x => x.cle === cle);
      if (!s) return {};
      const tous = D.cartos.every(c => ouvert(s, c.id));
      return { cases_statut: D.cartos.map(c => ({ statut: cle, entity_id: c.id, on: !tous })) };
    }
    const rid = Number(cle);
    const role = D.roles.find(r => r.id === rid);
    if (!role) return {};
    const tous = D.cartos.every(c => ouvert(role, c.id));
    return { cases: D.cartos.map(c => ({ role_id: rid, entity_id: c.id, on: !tous })) };
  }

  async function envoyer(cases) {
    const combien = (cases.cases || []).length + (cases.cases_statut || []).length;
    if (occupe || !combien) return;
    occupe = true;
    $('#cacc-corps').classList.add('est-occupe');
    try {
      const r = await fetch('/cartography/api/access/matrice', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cases),
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
      if (el.classList.contains('cacc-col')) {
        return envoyer(casesColonne(Number(el.dataset.carto), el.dataset.sec));
      }
      if (el.classList.contains('cacc-lig')) {
        return envoyer(casesLigne(el.dataset.cle, el.dataset.sec));
      }
    });
    f.addEventListener('change', (e) => {
      const el = e.target;
      if (!el.classList.contains('cacc-case')) return;
      const eid = Number(el.dataset.carto);
      envoyer(el.dataset.sec === 'statut'
        ? { cases_statut: [{ statut: el.dataset.cle, entity_id: eid, on: el.checked }] }
        : { cases: [{ role_id: Number(el.dataset.cle), entity_id: eid, on: el.checked }] });
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
