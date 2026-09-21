// static/js/rh_competences.js
//
// Page RH — ③ les compétences de TOUT LE MONDE, sur toutes les cartos.
//
// Une ligne par personne, une colonne par rôle (groupées par carto), et dans
// chaque case le niveau du rôle dessiné comme sur la page Compétences : quatre
// pas, un trait au niveau requis, pointillés tant que ce n'est pas évalué.
// Les chiffres viennent du serveur (`/gestion_rh/api/competences`) — qui
// tranche avec les fonctions mêmes de la page Compétences : les deux écrans ne
// peuvent pas se contredire.

(function () {
  'use strict';

  const L = (k) => (window.RHC_I18N || {})[k] || k;
  // « 0 activité » en français, « 0 activities » en anglais : le catalogue
  // porte les deux formes, « un|plusieurs ».
  function P(cle, n, vars) {
    const formes = L(cle).split('|');
    const un = L('lang') === 'en' ? n === 1 : Math.abs(n) <= 1;
    let s = un ? formes[0] : formes[formes.length - 1];
    Object.entries(Object.assign({ n }, vars || {})).forEach(([k, v]) => {
      s = s.split('{' + k + '}').join(String(v));
    });
    return s;
  }
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

  const S = { data: null, carto: '', q: '', filtre: 'tous', charge: false };

  /* ── Données ─────────────────────────────────────────────────────────── */

  async function charger(discret) {
    const zone = $('#rhc-corps');
    if (!zone) return;
    if (!discret || !S.data) {
      zone.innerHTML = `<p class="grh-wait"><i class="fa-solid fa-spinner fa-spin"></i>${esc(L('loading'))}</p>`;
    }
    try {
      const url = '/gestion_rh/api/competences' + (S.carto ? `?entity_id=${S.carto}` : '');
      const rep = await fetch(url);
      const d = await rep.json();
      if (!rep.ok) throw new Error(d.error || '');
      S.data = d;
      S.charge = true;
    } catch (_) {
      zone.innerHTML = `<p class="grh-empty">${esc(L('err'))}</p>`;
      return;
    }
    rendre();
    publierResume();
  }

  // La tuile « En écart » de la page vit dans gestion_rh.js : on lui laisse le
  // chiffre, elle le relit chaque fois qu'elle se redessine.
  function publierResume() {
    const gens = (S.data && S.data.personnes) || [];
    window.RHC_RESUME = { n_gap: gens.filter((p) => p.counts.gap > 0).length };
    const b = document.querySelector('.grh-tile[data-cible="bloc-competences"] b');
    if (b) b.textContent = window.RHC_RESUME.n_gap;
  }

  /* ── Filtres ─────────────────────────────────────────────────────────── */

  const ETATS = {
    gap: (p) => p.counts.gap > 0,
    todo: (p) => p.counts.todo > 0,
    held: (p) => p.counts.gap === 0 && p.counts.todo === 0 && p.counts.held > 0,
  };

  function correspond(p) {
    const q = S.q.trim().toLowerCase();
    if (q && !`${p.prenom} ${p.nom} ${p.email}`.toLowerCase().includes(q)) return false;
    return S.filtre === 'tous' || ETATS[S.filtre](p);
  }

  function rendreCartos() {
    const sel = $('#rhc-carto');
    if (!sel || !S.data) return;
    sel.innerHTML = `<option value="">${esc(L('all_maps'))}</option>`
      + S.data.cartos.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
    sel.value = S.carto;
  }

  function puces() {
    const gens = S.data.personnes;
    const n = (k) => (k === 'tous' ? gens.length : gens.filter(ETATS[k]).length);
    return `<div class="rhc-puces" role="group">${[
      ['tous', L('f_all'), ''],
      ['gap', L('f_gap'), 'red'],
      ['todo', L('f_todo'), 'grey'],
      ['held', L('f_held'), 'green'],
    ].map(([k, lib, ton]) => `
      <button type="button" class="rhc-puce${ton ? ' rhc-puce--' + ton : ''}${S.filtre === k ? ' is-on' : ''}"
              data-filtre="${k}" aria-pressed="${S.filtre === k}">
        ${ton ? '<span class="rhc-pt"></span>' : ''}${esc(lib)}<b>${n(k)}</b>
      </button>`).join('')}</div>`;
  }

  /* ── La matrice ──────────────────────────────────────────────────────── */

  // Quatre pas = les niveaux 1 à 4 ; le niveau 0 « Non démontré » est une
  // jauge VIDE. Non évalué (null) se dessine en pointillés : une absence, pas
  // un zéro. Le trait suit le pas REQUIS — « la jauge doit atteindre ce trait ».
  function jauge(niveau, requis) {
    const inconnu = niveau === null || niveau === undefined;
    let pas = '';
    for (let i = 1; i <= 4; i++) {
      const cls = [];
      if (inconnu) cls.push('vide');
      else if (niveau >= i) cls.push('on');
      if (requis === i) cls.push('cible');
      pas += `<i class="${cls.join(' ')}"></i>`;
    }
    return `<span class="rhc-pas">${pas}</span>`;
  }

  function bas(s) {
    const c = s.counts;
    if (c.setup === s.n_activities) return `<span class="rhc-m rhc-m--setup">${esc(L('setup'))}</span>`;
    const morceaux = [];
    if (c.gap) morceaux.push(`<span class="rhc-m rhc-m--gap">${esc(P('n_gap', c.gap))}</span>`);
    if (c.todo) morceaux.push(`<span class="rhc-m rhc-m--todo">${esc(P('n_todo', c.todo))}</span>`);
    if (!morceaux.length) morceaux.push(`<span class="rhc-m rhc-m--held"><i class="fa-solid fa-check"></i>${esc(L('held'))}</span>`);
    return morceaux.join('');
  }

  function bulle(r, carto, s) {
    const c = s.counts;
    const etats = [c.held && P('n_held', c.held), c.gap && P('n_gap', c.gap),
      c.todo && P('n_todo', c.todo), c.setup && P('n_setup', c.setup)].filter(Boolean);
    return [
      `${r.name} · ${carto}`,
      P('tip_level', 0, { v: s.level_label }),
      s.required_level === null ? '' : P('tip_required', 0, { v: s.required_label }),
      `${P('tip_activities', s.n_activities)} — ${etats.join(', ')}`,
      s.couverture === null ? '' : `${s.couverture} % ${L('coverage')}`,
      L('tip_open'),
    ].filter(Boolean).join('\n');
  }

  function cellule(p, r, carto) {
    const s = p.roles[String(r.id)];
    if (!s) {
      return `<td class="rhc-c rhc-c--vide" title="${esc(L('not_held'))}"><span class="rhc-rien"></span></td>`;
    }
    const url = `/competences/view?personne=${p.id}&role=${r.id}`;
    return `<td class="rhc-c">
      <a class="rhc-cel rhc-j--${esc(s.color)}" href="${url}" title="${esc(bulle(r, carto, s))}">
        ${jauge(s.level, s.required_level)}
        <span class="rhc-cel-bas">${bas(s)}</span>
      </a></td>`;
  }

  function ensemble(p) {
    const cov = p.couverture;
    return `<td class="rhc-ens">
      <span class="rhc-cov">${cov === null ? '—' : `${cov}<small>%</small>`}</span>
      <span class="rhc-cov-barre"><i style="width:${cov === null ? 0 : Math.min(100, cov)}%"></i></span>
      <span class="rhc-cov-sur">${esc(P('evaluated', p.n_evaluated, { m: p.n_activities }))}</span>
    </td>`;
  }

  function teinte(p) {
    let h = 0;
    for (const ch of String(p.email || p.id)) h = (h * 31 + ch.charCodeAt(0)) % 360;
    return h;
  }

  function rendre() {
    const zone = $('#rhc-corps');
    if (!zone || !S.data) return;
    rendreCartos();
    const d = S.data;
    if (!d.personnes.length) {
      zone.innerHTML = `<p class="grh-empty">${esc(L('empty'))}</p>`;
      return;
    }
    const gens = d.personnes.filter(correspond);
    const roles = d.colonnes.flatMap((g) => g.roles.map((r) => ({ r, carto: g.carto })));
    const tete1 = d.colonnes.map((g) =>
      `<th class="rhc-carto" colspan="${g.roles.length}"><span><i class="fa-solid fa-diagram-project"></i>${esc(g.carto)}</span></th>`).join('');
    const tete2 = roles.map(({ r }) =>
      `<th class="rhc-role" title="${esc(r.name)}"><span>${esc(r.name)}</span></th>`).join('');
    const corps = gens.map((p) => `
      <tr>
        <th class="rhc-pers" scope="row"><span class="rhc-pers-in">
          <span class="rhc-av" style="--h:${teinte(p)}">${esc(((p.prenom || '?')[0] + (p.nom || '')[0]).toUpperCase())}</span>
          <span class="rhc-nom">${esc(`${p.prenom} ${p.nom}`.trim() || p.email)}</span>
        </span></th>
        ${roles.map(({ r, carto }) => cellule(p, r, carto)).join('')}
        ${ensemble(p)}
      </tr>`).join('');

    zone.innerHTML = `
      ${puces()}
      ${gens.length ? `
      <div class="rhc-scroll">
        <table class="rhc-t">
          <thead>
            <tr class="rhc-t1">
              <th class="rhc-coin" rowspan="2">${esc(L('person'))}</th>
              ${tete1}
              <th class="rhc-ens rhc-ens--tete" rowspan="2">${esc(L('overall'))}</th>
            </tr>
            <tr class="rhc-t2">${tete2}</tr>
          </thead>
          <tbody>${corps}</tbody>
        </table>
      </div>` : `<p class="grh-empty">${esc(L('no_match'))}</p>`}
      <p class="rhc-leg">
        <span><b class="rhc-pt rhc-pt--green"></b>${esc(L('leg_green'))}</span>
        <span><b class="rhc-pt rhc-pt--orange"></b>${esc(L('leg_orange'))}</span>
        <span><b class="rhc-pt rhc-pt--red"></b>${esc(L('leg_red'))}</span>
        <span><b class="rhc-pt rhc-pt--vide"></b>${esc(L('leg_grey'))}</span>
        <span><b class="rhc-trait"></b>${esc(L('leg_tick'))}</span>
      </p>`;
  }

  /* ── Branchements ────────────────────────────────────────────────────── */

  function demarrer() {
    const bloc = $('#bloc-competences');
    if (!bloc) return;
    bloc.addEventListener('click', (e) => {
      const puce = e.target.closest('[data-filtre]');
      if (puce) { S.filtre = puce.dataset.filtre; rendre(); }
    });
    $('#rhc-carto').addEventListener('change', (e) => { S.carto = e.target.value; charger(); });
    $('#rhc-q').addEventListener('input', (e) => { S.q = e.target.value; rendre(); });
    // La tuile « En écart » mène ici ET filtre : on vient y voir qui.
    document.addEventListener('rhc:filtre', (e) => {
      S.filtre = (e.detail && ETATS[e.detail]) ? e.detail : 'tous';
      rendre();
    });
    // Une affectation faite plus haut dans la page change les rôles tenus :
    // on se remet à jour sans vider l'écran.
    document.addEventListener('grh:charge', () => { if (S.charge) charger(true); });
    charger();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
