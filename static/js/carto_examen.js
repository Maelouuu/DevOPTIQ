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
            /api/changes/<id>/approve|reject, /api/changes/<id>/apercu/<quel>.svg
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
      const rep = await fetch('/cartography/api/changes/a_examiner');
      const data = await rep.json();
      if (!rep.ok) throw new Error(data.error || '');
      S.liste = data.requests || [];
    } catch (_) {
      $('#cex-detail').innerHTML = `<p class="cex-err">${esc(L('err'))}</p>`;
      return;
    }
    majBandeau();
    if (!S.liste.length) { rendreFini(); return; }
    rendreListe();
    choisir(S.liste[0].id);
  }

  function fermer() {
    const fen = $('#cex');
    if (!fen || fen.hidden) return;
    fen.hidden = true;
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
          <button type="button" class="cex-item${r.id === S.choisi ? ' is-on' : ''}"
                  data-id="${r.id}"${r.id === S.choisi ? ' aria-current="true"' : ''}>
            <span class="cex-item-titre">${esc(r.title || L('sans_titre'))}</span>
            <span class="cex-item-meta">${esc(r.author)} · ${esc(dateCourte(r.created_at))}</span>
          </button>`).join('')}
      </div>`).join('');
  }

  /* ── Le détail d'une proposition ─────────────────────────────────────── */

  async function choisir(id) {
    S.choisi = id;
    rendreListe();
    const zone = $('#cex-detail');
    zone.innerHTML = attente();
    try {
      const rep = await fetch(`/cartography/api/changes/${id}`);
      const r = await rep.json();
      if (!rep.ok) throw new Error(r.error || '');
      if (S.choisi !== id) return;      // on a cliqué ailleurs entre-temps
      S.detail = r;
      zone.innerHTML = detailHtml(r);
      zone.scrollTop = 0;
      brancherImages(zone);
    } catch (_) {
      if (S.choisi === id) zone.innerHTML = `<p class="cex-err">${esc(L('err'))}</p>`;
    }
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
    const image = (quel, libelle) => `
      <figure class="cex-ba-fig" data-quel="${quel}">
        <figcaption>${esc(libelle)}</figcaption>
        <button type="button" class="cex-ba-shot" data-loupe="${quel}" title="${esc(L('agrandir'))}">
          <img src="/cartography/api/changes/${r.id}/apercu/${quel}.svg" alt="${esc(libelle)}">
          <span class="cex-ba-zoom"><i class="fa-solid fa-up-right-and-down-left-from-center"></i></span>
        </button>
      </figure>`;

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
      <div class="cex-ba">
        ${image('avant', L('avant'))}
        <i class="fa-solid fa-arrow-right cex-ba-fleche"></i>
        ${image('apres', L('apres'))}
      </div>
      <p class="cex-leg">
        <span><b class="cex-pt cex-pt--del"></b>${esc(L('leg_retire'))}</span>
        <span><b class="cex-pt cex-pt--add"></b>${esc(L('leg_ajoute'))}</span>
        <span><b class="cex-pt cex-pt--chg"></b>${esc(L('leg_change'))}</span>
      </p>

      <h5 class="cex-h">${esc(L('resume'))}</h5>
      ${resumeHtml(r.summary)}

      ${r.can_review ? `
        <div class="cex-decision">
          <h5 class="cex-h">${esc(L('decision'))}</h5>
          <label class="cex-lab" for="cex-comment">${esc(L('commentaire'))}</label>
          <textarea id="cex-comment" rows="2" placeholder="${esc(L('commentaire_ph'))}"></textarea>
          <div class="cex-actions">
            <button type="button" class="cex-btn cex-btn--non" data-trancher="reject">
              <i class="fa-solid fa-xmark"></i>${esc(L('refuser'))}</button>
            <button type="button" class="cex-btn cex-btn--oui" data-trancher="approve">
              <i class="fa-solid fa-check"></i>${esc(L('appliquer'))}</button>
          </div>
        </div>` : ''}`;
  }

  // Une proposition déposée avant qu'on garde « ce que l'auteur avait sous
  // les yeux » n'a pas d'AVANT : on retire la vignette plutôt que d'afficher
  // une image cassée.
  function brancherImages(zone) {
    zone.querySelectorAll('.cex-ba-fig img').forEach((img) => {
      img.addEventListener('error', () => {
        const fig = img.closest('.cex-ba-fig');
        if (fig) fig.remove();
        zone.querySelector('.cex-ba')?.classList.add('is-une');
      }, { once: true });
    });
  }

  /* ── Voir en grand : la VRAIE carto, pas la vignette agrandie ────────── */

  // Les deux vignettes sont des SVG reconstruits, faits pour COMPARER. En
  // grand, on charge le viewer d'OptiqCarto, qui rend ce que rend l'éditeur.
  function agrandir(id, quel) {
    document.getElementById('cex-loupe')?.remove();
    const ov = document.createElement('div');
    ov.id = 'cex-loupe';
    ov.className = 'cex-loupe';
    const autre = quel === 'avant' ? 'apres' : 'avant';
    ov.innerHTML = `
      <div class="cex-loupe-barre">
        <span class="cex-loupe-titre">${esc(L(quel))}</span>
        <button type="button" class="cex-loupe-bascule" data-loupe-autre="${autre}">
          <i class="fa-solid fa-right-left"></i>${esc(L(autre))}</button>
        <button type="button" class="cex-loupe-x" data-loupe-fermer aria-label="${esc(L('fermer'))}">
          <i class="fa-solid fa-xmark"></i></button>
      </div>
      <iframe class="cex-loupe-vue" title="${esc(L('image'))}"
              src="/cartography/changes/${id}/apercu/${quel}"></iframe>`;
    document.body.appendChild(ov);
    ov.addEventListener('click', (e) => {
      if (e.target === ov || e.target.closest('[data-loupe-fermer]')) ov.remove();
      const b = e.target.closest('[data-loupe-autre]');
      if (b) agrandir(id, b.dataset.loupeAutre);
    });
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
      rep = await fetch(`/cartography/api/changes/${r.id}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: ($('#cex-comment')?.value || '').trim() }),
      });
      data = await rep.json().catch(() => ({}));
    } catch (_) { rep = null; }
    S.occupe = false;

    // 409 : quelqu'un a tranché avant nous. La proposition quitte la liste —
    // la laisser proposerait une décision qui n'est plus possible.
    if (rep && rep.status === 409) {
      annoncer(L('deja'), 'warn');
      retirer(r.id);
      return;
    }
    if (!rep || !rep.ok) {
      annoncer(rep && rep.status === 403 ? L('interdit') : L('err_decision'), 'err');
      choisir(r.id);
      return;
    }

    if (action === 'approve') {
      const active = window.ACTIVE_ENTITY && window.ACTIVE_ENTITY.id;
      if (active && Number(active) === Number(r.entity_id)) S.recharger = true;
      annoncer(data.sync_warning ? L('avert_sync')
        : (S.recharger ? L('applique') + ' ' + L('recharge') : L('applique')),
      data.sync_warning ? 'warn' : 'ok');
    } else {
      annoncer(L('refuse'), 'ok');
    }
    retirer(r.id);
  }

  // L'ordre qu'on VOIT (groupé par carto), pas celui du serveur (par date).
  const ordreAffiche = () => groupes().flatMap((g) => g.items).map((x) => x.id);

  function retirer(id) {
    const pos = ordreAffiche().indexOf(id);
    S.liste = S.liste.filter((x) => x.id !== id);
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
      if (item) { choisir(parseInt(item.dataset.id, 10)); return; }
      const loupe = e.target.closest('[data-loupe]');
      if (loupe && S.detail) { agrandir(S.detail.id, loupe.dataset.loupe); return; }
      const t = e.target.closest('[data-trancher]');
      if (t) trancher(t.dataset.trancher);
    });

    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const loupe = document.getElementById('cex-loupe');
      if (loupe) { loupe.remove(); return; }       // la loupe d'abord
      fermer();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
