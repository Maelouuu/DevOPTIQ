'use strict';

/* ══════════════════════════════════════════════════════════════════════════
   Page Carte — examiner les modifications proposées, TOUTES cartos confondues.
   ══════════════════════════════════════════════════════════════════════════
   Le bandeau n'existe que pour qui valide (le serveur ne l'écrit pas pour les
   autres) et seulement quand quelque chose attend. Cliquer ouvre la fenêtre :
   la liste à gauche, groupée par carto, et la proposition choisie à droite —
   ce qu'elle change en image et en mots, puis la décision.

   ⚠️ Appliquer REMPLACE la carto par la version proposée. Quand la carto a
   bougé depuis le dépôt, le détail le dit AVANT le clic (`since`).

   Routes : /cartography/api/changes/a_examiner, /api/changes/<id>,
            /api/changes/<id>/approve|reject ; la comparaison avant / après
            vient de static/js/carto_comparaison.js.
   ══════════════════════════════════════════════════════════════════════════ */

(function () {
  const $ = (s, r) => (r || document).querySelector(s);

  function L(cle) {
    const cat = window.CEX_I18N || {};
    return cat[cle] || cle;
  }

  function F(cle, vars) {
    return Object.entries(vars || {}).reduce(
      (txt, [k, v]) => txt.split('{' + k + '}').join(String(v)), L(cle));
  }

  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  // ⚠️ Le serveur écrit ses dates en UTC SANS fuseau (`datetime.utcnow()`) :
  // lues telles quelles, elles seraient prises pour l'heure locale et
  // afficheraient deux heures de décalage à Paris.
  function dateCourte(iso) {
    if (!iso) return '';
    const utc = /[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z';
    try {
      return new Date(utc).toLocaleString(L('lang') === 'en' ? 'en-GB' : 'fr-FR',
        { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    } catch (_) { return iso.slice(0, 10); }
  }

  const S = {
    liste: [],          // les propositions en attente, telles que le serveur les rend
    choisi: null,       // id de la proposition affichée
    detail: null,       // son détail (résumé, écart depuis le dépôt…)
    recharger: false,   // la carto AFFICHÉE a changé : recharger à la fermeture
    occupe: false,
    cmp: null,          // la comparaison avant / après montée dans le détail
  };

  /* ── Ouvrir, fermer ──────────────────────────────────────────────────── */

  async function ouvrir() {
    const fen = $('#cex');
    if (!fen) return;
    fen.hidden = false;
    fen.querySelector('.cex-boite').classList.remove('is-fini');
    document.body.classList.add('cex-ouverte');
    $('#cex-liste').innerHTML = '';
    $('#cex-detail').innerHTML = attente();
    try {
      // ⚠️ Les deux files, en PARALLÈLE et dans la MÊME fenêtre : un
      // coordinateur a un seul endroit où décider. Deux écrans finiraient par
      // ne plus dire la même chose du même geste, et surtout l'un des deux ne
      // serait jamais ouvert.
      const [rc, ra] = await Promise.all([
        fetch('/cartography/api/changes/a_examiner'),
        fetch('/api/propositions/a_examiner'),
      ]);
      const dc = await rc.json();
      if (!rc.ok) throw new Error(dc.error || '');
      const da = ra.ok ? await ra.json() : { requests: [] };
      // ⚠️ Les identifiants des DEUX tables se chevauchent : la proposition
      // de carto n° 3 et celle d'activité n° 3 existent toutes les deux. Tout
      // passe donc par `cle`, jamais par `id` seul.
      S.liste = [
        ...(dc.requests || []).map((r) => ({ ...r, genre: 'carto', cle: 'c' + r.id })),
        ...(da.requests || []).map((r) => ({ ...r, genre: 'activite', cle: 'a' + r.id })),
      ];
    } catch (_) {
      $('#cex-detail').innerHTML = `<p class="cex-err">${esc(L('err'))}</p>`;
      return;
    }
    majBandeau();
    if (!S.liste.length) { rendreFini(); return; }
    rendreListe();
    choisir(S.liste[0].cle);
  }

  function fermer() {
    const fen = $('#cex');
    if (!fen || fen.hidden) return;
    fen.hidden = true;
    demonter();
    document.body.classList.remove('cex-ouverte');
    // La carto affichée derrière la fenêtre n'est plus la bonne : la laisser
    // telle quelle, c'est montrer une version qui n'existe plus.
    if (S.recharger) window.location.reload();
  }

  function attente() {
    return '<p class="cex-attente"><i class="fa-solid fa-spinner fa-spin"></i></p>';
  }

  /* ── La liste, groupée par carto ─────────────────────────────────────── */

  function groupes() {
    const parCarto = new Map();
    S.liste.forEach((r) => {
      if (!parCarto.has(r.entity_id)) {
        parCarto.set(r.entity_id, { nom: r.entity_name || '—', items: [] });
      }
      parCarto.get(r.entity_id).items.push(r);
    });
    return [...parCarto.values()].sort((a, b) => a.nom.localeCompare(b.nom));
  }

  function rendreListe() {
    const n = S.liste.length;
    $('#cex-sous').textContent = n === 1 ? L('compte_1') : F('compte_n', { n });
    // Une seule proposition : une liste d'un élément ne sert qu'à prendre de
    // la place à la proposition elle-même.
    $('#cex-corps').classList.toggle('is-seule', n <= 1);
    $('#cex-liste').innerHTML = groupes().map((g) => `
      <div class="cex-groupe">
        <p class="cex-groupe-nom">
          <i class="fa-solid fa-diagram-project"></i>
          <span title="${esc(g.nom)}">${esc(g.nom)}</span>
          <b>${g.items.length}</b>
        </p>
        ${g.items.map((r) => `
          <button type="button" class="cex-item${r.cle === S.choisi ? ' is-on' : ''}"
                  data-id="${esc(r.cle)}"${r.cle === S.choisi ? ' aria-current="true"' : ''}>
            <span class="cex-item-titre">
              <i class="fa-solid ${r.genre === 'activite' ? 'fa-list-check' : 'fa-diagram-project'} cex-genre"
                 title="${esc(L(r.genre === 'activite' ? 'genre_activite' : 'genre_carto'))}"></i>
              ${esc(r.title || L(r.genre === 'activite' ? 'sans_activite' : 'sans_titre'))}</span>
            <span class="cex-item-meta">${esc(r.author)} · ${esc(dateCourte(r.created_at))}</span>
          </button>`).join('')}
      </div>`).join('');
  }

  /* ── Le détail d'une proposition ─────────────────────────────────────── */

  const parCle = (cle) => S.liste.find((x) => x.cle === cle);

  async function choisir(cle) {
    S.choisi = cle;
    rendreListe();
    const zone = $('#cex-detail');
    demonter();
    zone.innerHTML = attente();
    const item = parCle(cle);
    if (!item) return;
    const url = item.genre === 'activite'
      ? `/api/propositions/${item.id}`
      : `/cartography/api/changes/${item.id}`;
    try {
      const rep = await fetch(url);
      const r = await rep.json();
      if (!rep.ok) throw new Error(r.error || '');
      if (S.choisi !== cle) return;     // on a cliqué ailleurs entre-temps
      S.detail = { ...r, genre: item.genre, cle };
      demonter();
      zone.innerHTML = item.genre === 'activite' ? detailActiviteHtml(r) : detailHtml(r);
      zone.scrollTop = 0;
      if (item.genre !== 'activite') monterComparaison(r);
    } catch (_) {
      if (S.choisi === cle) zone.innerHTML = `<p class="cex-err">${esc(L('err'))}</p>`;
    }
  }

  /* ── Le détail d'une proposition d'ACTIVITÉ ──────────────────────────────
     ⚠️ Pas d'avant / après en image : une fiche d'activité n'est pas un
     dessin. Ce qu'on examine, ce sont les GESTES — et c'est aussi ce qui
     sera rejoué, dans cet ordre, à l'application. */

  function phraseGeste(g) {
    const bouts = String(g.op || '').split('.');
    const objet = g.objet
      ? (L('lang') === 'en' ? ` “${g.objet}”` : ` « ${g.objet} »`) : '';
    return L('v_' + (bouts[1] || 'update')) + ' ' + L('f_' + (bouts[0] || 'task')) + objet;
  }

  function detailActiviteHtml(r) {
    const gestes = r.gestes || [];
    return `
      <div class="cex-acp-tete">
        <span class="cex-acp-ic"><i class="fa-solid fa-code-pull-request"></i></span>
        <div class="cex-acp-t">
          <p class="cex-acp-sur">${esc(L('par').replace('%s', r.author))} ·
            ${esc(dateCourte(r.submitted_at || r.created_at))}</p>
          <h4>${esc(r.title || L('sans_activite'))}</h4>
          <p class="cex-acp-carto"><i class="fa-solid fa-diagram-project"></i>${esc(r.entity_name || '—')}</p>
        </div>
        <span class="cex-acp-n">${gestes.length}</span>
      </div>
      ${r.message ? `<blockquote class="cex-msg">${esc(r.message)}</blockquote>` : ''}

      <ol class="cex-gestes">
        ${gestes.map((g) => {
          const bouts = String(g.op || '').split('.');
          return `
          <li class="cex-g">
            <div class="cex-g-t">
              <p class="cex-g-verbe">${esc(L('v_' + (bouts[1] || 'update')))}
                ${esc(L('f_' + (bouts[0] || 'task')))}</p>
              <p class="cex-g-objet">${esc(g.objet || '—')}</p>
            </div>
            <span class="cex-g-ou">${esc(g.activite || L('hors_activite'))}</span>
          </li>`;
        }).join('')}
      </ol>
      <p class="cex-g-note"><i class="fa-solid fa-circle-info"></i>${esc(L('gestes_note'))}</p>

      ${r.can_review ? `
        <div class="cex-decision">
          <h5 class="cex-h">${esc(L('decision'))}</h5>
          <label class="cex-lab" for="cex-comment">${esc(F('commentaire', { nom: r.author }))}</label>
          <textarea id="cex-comment" rows="2" placeholder="${esc(L('commentaire_ph'))}"></textarea>
          <small class="cex-aide">${esc(L('commentaire_aide'))}</small>
          <div class="cex-actions">
            <button type="button" class="cex-btn cex-btn--non" data-trancher="reject">
              <i class="fa-solid fa-xmark"></i>${esc(L('refuser'))}</button>
            <button type="button" class="cex-btn cex-btn--oui" data-trancher="approve">
              <i class="fa-solid fa-check"></i>${esc(L('appliquer'))}</button>
          </div>
        </div>` : ''}`;
  }

  function ligneResume(n, cle, noms) {
    if (!n) return '';
    const detail = (noms && noms.length)
      ? `<span class="cex-sum-noms">${esc(noms.slice(0, 4).join(', '))}${noms.length > 4 ? '…' : ''}</span>`
      : '';
    // Singulier / pluriel plutôt que « ajoutée(s) » : c'est la ligne qu'on lit
    // pour comprendre la proposition, elle doit se lire d'une traite.
    return `<li><strong>${n}</strong><span>${esc(L(n > 1 ? cle + '_p' : cle))}</span>${detail}</li>`;
  }

  function resumeHtml(s) {
    if (!s) return '';
    const lignes = [
      ligneResume(s.added.length, 'added', s.added),
      ligneResume(s.removed.length, 'removed', s.removed),
      ligneResume(s.renamed.length, 'renamed', s.renamed.map((x) => `${x.from} → ${x.to}`)),
      ligneResume(s.moved.length, 'moved', s.moved),
      ligneResume(s.links_added, 'links_added'),
      ligneResume(s.links_removed, 'links_removed'),
    ].filter(Boolean).join('');
    return lignes ? `<ul class="cex-sum">${lignes}</ul>`
                  : `<p class="cex-vide">${esc(L('rien'))}</p>`;
  }

  function detailHtml(r) {
    return `
      <div class="cex-d-tete">
        <span class="cex-chip"><i class="fa-solid fa-diagram-project"></i>${esc(r.entity_name || '—')}</span>
        <h4>${esc(r.title || L('sans_titre'))}</h4>
        <p class="cex-d-meta">
          <i class="fa-solid fa-user-pen"></i>${esc(L('par').replace('%s', r.author))}
          <span>·</span>${esc(dateCourte(r.created_at))}
        </p>
      </div>
      ${r.message ? `<blockquote class="cex-msg">${esc(r.message)}</blockquote>` : ''}

      ${r.since ? `
        <div class="cex-depuis" role="alert">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <div>
            <b>${esc(L('depuis_titre'))}</b>
            ${resumeHtml(r.since)}
            <p>${esc(L('depuis_txt'))}</p>
          </div>
        </div>` : ''}

      <h5 class="cex-h">${esc(L('image'))}</h5>
      <div class="cex-cmp" id="cex-cmp"></div>

      <h5 class="cex-h">${esc(L('resume'))}</h5>
      ${resumeHtml(r.summary)}

      ${r.can_review ? `
        <div class="cex-decision">
          <h5 class="cex-h">${esc(L('decision'))}</h5>
          <label class="cex-lab" for="cex-comment">${esc(F('commentaire', { nom: r.author }))}</label>
          <textarea id="cex-comment" rows="2" placeholder="${esc(L('commentaire_ph'))}"></textarea>
          <small class="cex-aide">${esc(L('commentaire_aide'))}</small>
          <div class="cex-actions">
            <button type="button" class="cex-btn cex-btn--non" data-trancher="reject">
              <i class="fa-solid fa-xmark"></i>${esc(L('refuser'))}</button>
            <button type="button" class="cex-btn cex-btn--oui" data-trancher="approve">
              <i class="fa-solid fa-check"></i>${esc(L('appliquer'))}</button>
          </div>
        </div>` : ''}`;
  }

  /* ── Avant / après : les vraies cartos (static/js/carto_comparaison.js) ── */

  function monterComparaison(r) {
    const hote = $('#cex-cmp');
    if (!hote || !window.CartoComparaison) return;
    S.cmp = window.CartoComparaison.monter(hote, {
      id: r.id,
      marques: r.marques,
      libelles: {
        avant: L('avant'), apres: L('apres'), agrandir: L('agrandir'), fermer: L('fermer'),
        leg_retire: L('leg_retire'), leg_ajoute: L('leg_ajoute'), leg_change: L('leg_change'),
      },
    });
  }

  function demonter() {
    if (S.cmp) { S.cmp.detruire(); S.cmp = null; }
  }

  /* ── Trancher ────────────────────────────────────────────────────────── */

  async function trancher(action) {
    const r = S.detail;
    if (!r || S.occupe) return;
    S.occupe = true;
    const zone = $('#cex-detail');
    const btn = zone.querySelector(`[data-trancher="${action}"]`);
    zone.querySelectorAll('[data-trancher]').forEach((b) => { b.disabled = true; });
    if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

    let data = {};
    let rep = null;
    try {
      const base = r.genre === 'activite'
        ? `/api/propositions/${r.id}` : `/cartography/api/changes/${r.id}`;
      rep = await fetch(`${base}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: ($('#cex-comment')?.value || '').trim() }),
      });
      data = await rep.json().catch(() => ({}));
    } catch (_) { rep = null; }
    S.occupe = false;

    // 409 : quelqu'un a tranché avant nous. La proposition quitte la liste —
    // la laisser proposerait une décision qui n'est plus possible.
    if (rep && rep.status === 409 && data.code !== 'rejeu') {
      annoncer(L('deja'), 'warn');
      retirer(r.cle);
      return;
    }
    // ⚠️ 409 `rejeu` : un geste ne s'applique plus (l'objet a disparu, ou
    // quelqu'un l'a déjà changé). RIEN n'a été écrit — on applique tout ou
    // rien — et la proposition RESTE en attente : on dit lequel a bloqué,
    // pour que le coordinateur puisse en parler à son auteur.
    if (rep && rep.status === 409 && data.code === 'rejeu') {
      annoncer(F('rejeu', { n: (data.rang || 0) + 1, quoi: data.objet || '—' }), 'err');
      choisir(r.cle);
      return;
    }
    if (!rep || !rep.ok) {
      annoncer(rep && rep.status === 403 ? L('interdit') : L('err_decision'), 'err');
      choisir(r.cle);
      return;
    }

    // La décision part à l'auteur, avec le message s'il y en a un : on le
    // dit, sinon on croirait l'avoir écrit pour soi.
    const averti = ' ' + F('averti', { nom: r.author });
    if (action === 'approve') {
      const active = window.ACTIVE_ENTITY && window.ACTIVE_ENTITY.id;
      // Une proposition d'ACTIVITÉ ne change pas le dessin : recharger la
      // page Carte n'y montrerait rien de neuf.
      if (r.genre !== 'activite'
          && active && Number(active) === Number(r.entity_id)) S.recharger = true;
      annoncer(data.sync_warning ? L('avert_sync')
        : L('applique') + averti + (S.recharger ? ' ' + L('recharge') : ''),
      data.sync_warning ? 'warn' : 'ok');
    } else {
      annoncer(L('refuse') + averti, 'ok');
    }
    retirer(r.cle);
  }

  // L'ordre qu'on VOIT (groupé par carto), pas celui du serveur (par date).
  const ordreAffiche = () => groupes().flatMap((g) => g.items).map((x) => x.cle);

  function retirer(cle) {
    const pos = ordreAffiche().indexOf(cle);
    S.liste = S.liste.filter((x) => x.cle !== cle);
    majBandeau();
    if (!S.liste.length) { rendreFini(); return; }
    // La suivante : celle qui était juste en dessous dans la liste.
    const ordre = ordreAffiche();
    choisir(ordre[Math.min(Math.max(pos, 0), ordre.length - 1)]);
  }

  function rendreFini() {
    // Plus de liste ni de proposition : la fenêtre se resserre sur son message
    // au lieu de le laisser flotter dans un grand cadre vide.
    $('#cex .cex-boite').classList.add('is-fini');
    demonter();
    $('#cex-sous').textContent = '';
    $('#cex-corps').classList.add('is-seule');
    $('#cex-liste').innerHTML = '';
    $('#cex-detail').innerHTML = `
      <div class="cex-fini">
        <span class="cex-fini-ic"><i class="fa-solid fa-check"></i></span>
        <b>${esc(L('fini'))}</b>
        <p>${esc(L('fini_sous'))}</p>
        <button type="button" class="cex-btn cex-btn--oui" data-cex="fermer">${esc(L('fermer'))}</button>
      </div>`;
  }

  /* ── Le bandeau suit ce qui reste ────────────────────────────────────── */

  function majBandeau() {
    const b = $('#cex-bandeau');
    if (!b) return;
    const n = S.liste.length;
    if (!n) { b.hidden = true; return; }
    const cartos = new Map(S.liste.map((x) => [x.entity_id, x.entity_name || '—']));
    $('#cex-bandeau-titre').textContent = n === 1 ? L('bandeau_1') : F('bandeau_n', { n });
    $('#cex-bandeau-sous').textContent = cartos.size === 1
      ? F('sur_carto', { nom: [...cartos.values()][0] })
      : F('sur_n_cartos', { n: cartos.size });
  }

  /* ── Annonce ─────────────────────────────────────────────────────────── */

  function annoncer(texte, ton) {
    let t = $('#cex-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'cex-toast';
      t.setAttribute('role', 'status');
      document.body.appendChild(t);
    }
    t.className = 'cex-toast cex-toast--' + (ton || 'ok');
    t.textContent = texte;
    requestAnimationFrame(() => t.classList.add('is-on'));
    clearTimeout(annoncer._h);
    annoncer._h = setTimeout(() => t.classList.remove('is-on'), 3200);
  }

  /* ── Branchements ────────────────────────────────────────────────────── */

  function demarrer() {
    const bandeau = $('#cex-bandeau');
    const fen = $('#cex');
    if (!bandeau || !fen) return;
    bandeau.addEventListener('click', ouvrir);

    fen.addEventListener('click', (e) => {
      if (e.target.closest('[data-cex="fermer"]')) { fermer(); return; }
      const item = e.target.closest('.cex-item');
      if (item) { choisir(item.dataset.id); return; }
      const t = e.target.closest('[data-trancher]');
      if (t) trancher(t.dataset.trancher);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      // La comparaison en grand format se referme d'elle-même sur Échap (elle
      // arrête l'événement) : on n'arrive ici que si elle est en vignettes.
      if (S.cmp && S.cmp.enLoupe()) return;
      fermer();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
