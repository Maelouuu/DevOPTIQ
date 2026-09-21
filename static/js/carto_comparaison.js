'use strict';

/* ══════════════════════════════════════════════════════════════════════════
   Comparer AVANT / APRÈS une modification proposée — les vraies cartos.
   ══════════════════════════════════════════════════════════════════════════
   Servi à la fenêtre d'examen de la page Carte (carto_examen.js) et à celle
   de l'éditeur (carto_sharing.js) : un seul composant, deux écrans qui ne
   peuvent pas diverger.

   - Les vignettes SONT le viewer d'OptiqCarto (une page par côté), pas un
     schéma reconstruit : ce qu'on compare est ce que l'éditeur dessine.
   - Les deux cartos partagent le MÊME cadre (bornes réunies des deux) : sans
     ça, une forme ajoutée au bord recadrait tout un côté, et la carte entière
     semblait avoir bougé.
   - Agrandir ne recharge rien : on agrandit les deux viewers déjà chargés, en
     CSS, sans les déplacer dans la page (déplacer une iframe la recharge).
   - Passer de l'une à l'autre est instantané et garde le zoom et la position :
     le cadrage de la vue affichée est recopié sur l'autre avant la bascule.

   S'appuie sur `window.cartoViewport` et `window.getCartoState`, exposés par
   editor.js dans chaque viewer (même origine).
   ══════════════════════════════════════════════════════════════════════════ */

(function () {
  const COULEUR = { removed: '#ef4444', added: '#22c55e', changed: '#f59e0b' };
  const COTES = ['avant', 'apres'];

  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  const cssEsc = (v) => (window.CSS && CSS.escape ? CSS.escape(String(v)) : String(v).replace(/"/g, '\\"'));
  const apresRendu = (f) => requestAnimationFrame(() => requestAnimationFrame(f));

  /**
   * @param {HTMLElement} hote   où monter la comparaison
   * @param {object} o           { id, marques: {avant:{id:kind}, apres:{…}}, libelles }
   * @returns {{ detruire(): void, enLoupe(): boolean, fermerLoupe(): void }}
   */
  function monter(hote, o) {
    const L = (k) => ((o.libelles || {})[k]) || k;
    const legende = `
      <span><b class="cmp-pt cmp-pt--del"></b>${esc(L('leg_retire'))}</span>
      <span><b class="cmp-pt cmp-pt--add"></b>${esc(L('leg_ajoute'))}</span>
      <span><b class="cmp-pt cmp-pt--chg"></b>${esc(L('leg_change'))}</span>`;
    const vue = (quel) => `
      <figure class="cmp-vue" data-quel="${quel}">
        <figcaption>${esc(L(quel))}</figcaption>
        <div class="cmp-cadre">
          <iframe src="/cartography/changes/${encodeURIComponent(o.id)}/apercu/${quel}"
                  title="${esc(L(quel))}" tabindex="-1"></iframe>
          <span class="cmp-attente"><i class="fa-solid fa-spinner fa-spin"></i></span>
          <button type="button" class="cmp-voile" data-cmp="agrandir" data-quel="${quel}"
                  title="${esc(L('agrandir'))}" aria-label="${esc(L('agrandir'))} — ${esc(L(quel))}">
            <span class="cmp-zoom"><i class="fa-solid fa-up-right-and-down-left-from-center"></i></span>
          </button>
        </div>
      </figure>`;

    const racine = document.createElement('div');
    racine.className = 'cmp';
    racine.dataset.mode = 'vignettes';
    racine.dataset.vue = 'apres';
    racine.innerHTML = `
      <div class="cmp-barre">
        <div class="cmp-bascule" role="tablist">
          ${COTES.map((q) => `<button type="button" class="cmp-onglet" role="tab" data-cmp="voir"
              data-quel="${q}">${esc(L(q))}</button>`).join('')}
        </div>
        <p class="cmp-barre-leg">${legende}</p>
        <button type="button" class="cmp-x" data-cmp="fermer" aria-label="${esc(L('fermer'))}"
                title="${esc(L('fermer'))}"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="cmp-scene">
        ${vue('avant')}
        <i class="fa-solid fa-arrow-right cmp-fleche" aria-hidden="true"></i>
        ${vue('apres')}
      </div>
      <p class="cmp-leg">${legende}</p>`;
    hote.appendChild(racine);

    const cadres = {};
    COTES.forEach((q) => { cadres[q] = racine.querySelector(`.cmp-vue[data-quel="${q}"] iframe`); });
    const pret = { avant: false, apres: false };
    const absent = { avant: false, apres: false };

    const api = (q) => { try { return cadres[q].contentWindow.cartoViewport || null; } catch (_) { return null; } };

    /* ── Chargement ─────────────────────────────────────────────────────── */

    // Le viewer annonce qu'il a chargé SA carto (editor.js : `carto-state-ready`).
    function surMessage(e) {
      if (!e.data || e.data.type !== 'carto-state-ready') return;
      const q = COTES.find((c) => cadres[c] && cadres[c].contentWindow === e.source);
      if (q) marquerPret(q);
    }
    window.addEventListener('message', surMessage);

    COTES.forEach((q) => cadres[q].addEventListener('load', () => {
      // Une proposition déposée avant qu'on garde « ce que l'auteur avait sous
      // les yeux » n'a pas d'AVANT : la page répond 404, sans viewer.
      if (!api(q)) { absent[q] = true; marquerPret(q); return; }
      brancherClavier(q);
    }));
    // Filet : un viewer qui ne répond jamais ne laisse pas un sablier éternel.
    const filet = setTimeout(() => COTES.forEach((q) => marquerPret(q)), 15000);

    function marquerPret(q) {
      if (pret[q]) return;
      pret[q] = true;
      const fig = racine.querySelector(`.cmp-vue[data-quel="${q}"]`);
      if (!fig) return;
      if (absent[q]) {
        fig.remove();
        racine.classList.add('is-une');
        racine.dataset.vue = q === 'avant' ? 'apres' : 'avant';
      } else {
        surligner(q);
        fig.classList.add('is-pret');
      }
      if (pret.avant && pret.apres) {
        clearTimeout(filet);
        cadrerEnsemble();
        if (typeof o.onPret === 'function') o.onPret();
      }
    }

    // Les formes touchées, entourées de LEUR couleur dans la vraie carto. Une
    // feuille de style plutôt qu'un style posé sur les éléments : le viewer
    // redessine ses formes, la règle, elle, reste.
    // ⚠️ `non-scaling-stroke` : un trait en unités de carte disparaît dans une
    // vignette (16 unités × un zoom de 0,05 = moins d'un pixel) et devient
    // épais en grand format. En pixels d'écran, le contour se voit partout.
    function surligner(q) {
      const marques = (o.marques || {})[q] || {};
      const ids = Object.keys(marques);
      if (!ids.length) return;
      let doc = null;
      try { doc = cadres[q].contentDocument; } catch (_) { doc = null; }
      if (!doc || !doc.head) return;
      const st = doc.createElement('style');
      st.textContent = ids.map((id) => `g.shape-group[data-id="${cssEsc(id)}"] [data-shape-fill]{`
        + `stroke:${COULEUR[marques[id]] || COULEUR.changed};stroke-width:7px;`
        + 'vector-effect:non-scaling-stroke;paint-order:stroke}').join('\n');
      doc.head.appendChild(st);
    }

    // Un seul cadre pour les deux : les bornes RÉUNIES des deux cartos.
    function cadrerEnsemble() {
      const bornes = COTES.filter((q) => !absent[q] && api(q))
        .map((q) => { try { return api(q).bounds(); } catch (_) { return null; } })
        .filter(Boolean);
      if (!bornes.length) return;
      const b = {
        minX: Math.min(...bornes.map((x) => x.minX)), minY: Math.min(...bornes.map((x) => x.minY)),
        maxX: Math.max(...bornes.map((x) => x.maxX)), maxY: Math.max(...bornes.map((x) => x.maxY)),
      };
      COTES.forEach((q) => { if (!absent[q] && api(q)) { try { api(q).fit(b); } catch (_) { /* rien */ } } });
    }

    /* ── Grand format ───────────────────────────────────────────────────── */

    function montrer(q) {
      if (absent[q]) return;
      const avant = racine.dataset.vue;
      // ⚠️ Le cadrage d'abord, la bascule ensuite : on compare le MÊME endroit
      // des deux cartos, au même zoom.
      if (racine.dataset.mode === 'loupe' && avant !== q && !absent[avant] && api(avant) && api(q)) {
        try { api(q).set(api(avant).get()); } catch (_) { /* rien */ }
      }
      racine.dataset.vue = q;
      racine.querySelectorAll('.cmp-onglet').forEach((b) => {
        const on = b.dataset.quel === q;
        b.classList.toggle('is-on', on);
        b.setAttribute('aria-selected', String(on));
      });
    }

    function agrandir(q) {
      racine.dataset.mode = 'loupe';
      montrer(absent[q] ? (q === 'avant' ? 'apres' : 'avant') : q);
      apresRendu(cadrerEnsemble);
      const actif = racine.querySelector('.cmp-onglet.is-on');
      if (actif) actif.focus();
    }

    function fermerLoupe() {
      if (racine.dataset.mode !== 'loupe') return;
      racine.dataset.mode = 'vignettes';
      apresRendu(cadrerEnsemble);
    }

    racine.addEventListener('click', (e) => {
      const b = e.target.closest('[data-cmp]');
      if (!b) return;
      if (b.dataset.cmp === 'agrandir') agrandir(b.dataset.quel);
      else if (b.dataset.cmp === 'voir') montrer(b.dataset.quel);
      else if (b.dataset.cmp === 'fermer') fermerLoupe();
    });

    // Au clavier, dans la page ET dans les viewers — une fois qu'on a cliqué
    // la carte, c'est elle qui reçoit les touches. Échap referme, Tab bascule.
    // ⚠️ Pas l'espace : maintenu, il sert au viewer à déplacer la carte.
    function auClavier(e) {
      if (racine.dataset.mode !== 'loupe') return;
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        fermerLoupe();
      } else if (e.key === 'Tab' && !e.repeat) {
        e.preventDefault();
        montrer(racine.dataset.vue === 'avant' ? 'apres' : 'avant');
      }
    }
    document.addEventListener('keydown', auClavier, true);
    function brancherClavier(q) {
      try { cadres[q].contentWindow.addEventListener('keydown', auClavier, true); } catch (_) { /* rien */ }
    }

    montrer('apres');

    return {
      enLoupe: () => racine.dataset.mode === 'loupe',
      fermerLoupe,
      detruire() {
        clearTimeout(filet);
        window.removeEventListener('message', surMessage);
        document.removeEventListener('keydown', auClavier, true);
        racine.remove();
      },
    };
  }

  window.CartoComparaison = { monter };
})();
