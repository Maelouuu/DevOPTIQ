/* ============================================================
   PROPOSER UNE MODIFICATION D'ACTIVITÉ — l'écran du champion.

   ⚠️ **On enveloppe `fetch`, on ne touche pas aux huit fichiers JS de la
   page.** Les tâches, les outils, les compétences, les savoirs, les HSC et
   les contraintes sont écrits par autant de scripts, chacun avec sa façon de
   lire une réponse. Les reprendre un par un, c'est huit occasions d'en
   oublier un — et le neuvième écrit demain passerait à côté. La porte
   d'écriture est centrale côté serveur ; son pendant l'est ici.

   ⚠️ Le serveur répond **202** avec `code: "proposition"` : le geste n'est PAS
   appliqué. On n'autorise donc pas la suite du code à rafraîchir la liste —
   elle montrerait la base inchangée, et on croirait avoir perdu sa saisie.
   ============================================================ */
(function () {
  'use strict';

  var L = window.ACP_I18N || {};
  function T(k) { return L[k] !== undefined ? L[k] : k; }
  function F(k, vars) {
    var s = T(k);
    Object.keys(vars || {}).forEach(function (c) {
      s = s.split('[[' + c + ']]').join(vars[c]);
    });
    return s;
  }
  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  var S = { n: 0, gestes: [], id: null, ouvert: false };

  /* ── Le libellé d'un geste, composé dans la langue de CELUI QUI LIT ──
     ⚠️ Jamais figé à l'écriture : le champion propose dans sa langue, le
     coordinateur lit dans la sienne. Même règle que le journal d'activité. */
  function phrase(g) {
    var bouts = String(g.op || '').split('.');
    var verbe = T('v_' + (bouts[1] || 'update'));
    var famille = T('f_' + (bouts[0] || 'task'));
    var objet = g.objet ? ' « ' + g.objet + ' »' : '';
    if (L.lang === 'en') objet = g.objet ? ' “' + g.objet + '”' : '';
    return verbe + ' ' + famille + objet;
  }

  /* ── Le bandeau ───────────────────────────────────────────────────── */
  function majBandeau() {
    var b = document.getElementById('acp-bandeau');
    if (!b) return;
    b.hidden = false;
    b.classList.toggle('est-plein', S.n > 0);
    document.getElementById('acp-titre').textContent =
      S.n === 0 ? T('bandeau_vide')
                : (S.n === 1 ? T('bandeau_1') : F('bandeau_n', { n: S.n }));
    document.getElementById('acp-sous').textContent =
      S.n === 0 ? T('bandeau_vide_d') : T('bandeau_d');
    var bouton = document.getElementById('acp-ouvrir');
    bouton.textContent = S.n === 0 ? T('mes_titre') : T('relire');
  }

  async function charger() {
    try {
      var r = await window.__acpFetch('/api/propositions/brouillon');
      var j = await r.json();
      S.n = j.n || 0;
      S.gestes = (j.brouillon && j.brouillon.gestes) || [];
      S.id = j.brouillon ? j.brouillon.id : null;
    } catch (e) { /* le bandeau reste à sa dernière valeur connue */ }
    majBandeau();
    if (S.ouvert) rendre();
  }

  /* ── La fenêtre : on relit, on retire, on envoie ───────────────────── */
  function ouvrir() {
    var w = document.getElementById('acp-win');
    if (!w) return;
    w.hidden = false;
    S.ouvert = true;
    document.getElementById('acp-h').textContent = T('titre');
    document.getElementById('acp-tsous').textContent = T('sous');
    rendre();
  }

  function fermer() {
    var w = document.getElementById('acp-win');
    if (w) w.hidden = true;
    S.ouvert = false;
  }

  function rendre() {
    var z = document.getElementById('acp-corps');
    if (!z) return;
    if (!S.gestes.length) { rendreMiennes(z); return; }

    var lignes = S.gestes.map(function (g, i) {
      // ⚠️ Un outil n'appartient à aucune activité : c'est le catalogue de la
      // carto. Le dire, plutôt que de laisser une ligne muette.
      var ou = g.activite ? esc(g.activite) : esc(T('hors_activite'));
      return '<li class="acp-l">'
        + '<span class="acp-n">' + (i + 1) + '</span>'
        + '<div class="acp-l-t"><b>' + esc(phrase(g)) + '</b>'
        + '<span>' + ou + '</span></div>'
        + '<button type="button" class="acp-del" data-retirer="' + i + '" '
        + 'aria-label="' + esc(T('retirer')) + '" title="' + esc(T('retirer')) + '">'
        + '<i class="fa-solid fa-xmark"></i></button></li>';
    }).join('');

    z.innerHTML = '<ul class="acp-liste">' + lignes + '</ul>'
      + '<label class="acp-msg"><span>' + esc(T('message')) + '</span>'
      + '<textarea id="acp-message" rows="2" placeholder="'
      + esc(T('message_ph')) + '"></textarea></label>'
      + '<div class="acp-pied">'
      + '<button type="button" class="acp-danger" data-abandonner>'
      + '<i class="fa-solid fa-trash-can"></i>' + esc(T('abandonner')) + '</button>'
      + '<span class="sp"></span>'
      + '<button type="button" class="acp-ok" data-envoyer>'
      + '<span class="ic"><i class="fa-solid fa-paper-plane"></i></span>'
      + esc(T('envoyer')) + '</button></div>';
  }

  async function rendreMiennes(z) {
    z.innerHTML = '<p class="acp-vide">' + esc(T('vide')) + '</p>';
    try {
      var r = await window.__acpFetch('/api/propositions/miennes');
      var j = await r.json();
      var liste = j.requests || [];
      if (!liste.length) {
        z.innerHTML = '<p class="acp-vide">' + esc(T('mes_vide')) + '</p>';
        return;
      }
      var etat = { pending: 'attente', approved: 'applique', rejected: 'refuse' };
      z.innerHTML = '<h4 class="acp-h4">' + esc(T('mes_titre')) + '</h4>'
        + '<ul class="acp-miennes">' + liste.map(function (p) {
          return '<li class="acp-m acp-m--' + esc(p.status) + '">'
            + '<div class="acp-m-t"><b>' + esc(p.title || T('hors_activite')) + '</b>'
            + '<span class="acp-etat">' + esc(T(etat[p.status] || 'attente')) + '</span></div>'
            + '<p class="acp-m-n">'
            + esc(p.n === 1 ? T('mes_1') : F('mes_n', { n: p.n })) + '</p>'
            + (p.review_comment
               ? '<p class="acp-m-c">« ' + esc(p.review_comment) + ' »</p>' : '')
            + '</li>';
        }).join('') + '</ul>';
    } catch (e) { /* on garde l'état vide */ }
  }

  /* ── Les actions ──────────────────────────────────────────────────── */
  async function retirer(i) {
    await window.__acpFetch('/api/propositions/brouillon/' + i, { method: 'DELETE' });
    await charger();
  }

  async function abandonner() {
    var ok = window.optiqConfirm
      ? await window.optiqConfirm(T('abandon_sur'), { danger: true })
      : true;
    if (!ok) return;
    await window.__acpFetch('/api/propositions/brouillon', { method: 'DELETE' });
    await charger();
  }

  async function envoyer() {
    var champ = document.getElementById('acp-message');
    var r = await window.__acpFetch('/api/propositions/envoyer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: champ ? champ.value : '' })
    });
    if (!r.ok) { signaler(T('err')); return; }
    // ⚠️ `charger()` re-rend la fenêtre quand elle est ouverte, et son rendu
    // asynchrone arrivait APRÈS l'écran de fin : on lisait « Mes
    // propositions » là où on attendait « Proposition envoyée ». On ferme
    // d'abord la vue, on écrit la fin, et seul le BANDEAU se met à jour.
    S.ouvert = false;
    await charger();
    S.ouvert = true;
    var z = document.getElementById('acp-corps');
    if (z) {
      z.innerHTML = '<div class="acp-fini">'
        + '<span class="acp-fini-ic"><i class="fa-solid fa-circle-check"></i></span>'
        + '<b>' + esc(T('envoye')) + '</b>'
        + '<p>' + esc(T('envoye_d')) + '</p></div>';
    }
  }

  /* ⚠️ Un TOAST, pas une modale. Corriger une fiche, c'est cinq ou six
     gestes : une fenêtre à fermer entre chacun transformerait la saisie en
     parcours d'obstacles. La modale reste pour ce qui ARRÊTE (une erreur). */
  var minuteur = null;
  function toast(texte) {
    var t = document.getElementById('acp-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'acp-toast';
      t.className = 'acp-toast';
      t.setAttribute('role', 'status');
      document.body.appendChild(t);
    }
    t.innerHTML = '<i class="fa-solid fa-circle-check"></i><span></span>';
    t.querySelector('span').textContent = texte;
    t.classList.add('est-la');
    clearTimeout(minuteur);
    minuteur = setTimeout(function () { t.classList.remove('est-la'); }, 3200);
  }

  function signaler(texte) {
    if (window.optiqAlert) { window.optiqAlert(texte); return; }
    alert(texte);
  }

  /* ── L'enveloppe de `fetch` ───────────────────────────────────────── */
  window.__acpFetch = window.fetch.bind(window);

  window.fetch = function (entree, options) {
    var p = window.__acpFetch(entree, options);
    return p.then(function (r) {
      if (r.status !== 202) return r;
      // ⚠️ On CLONE : le code appelant va lire le corps à son tour, et un
      // flux de réponse ne se lit qu'une fois.
      return r.clone().json().then(function (j) {
        if (!j || j.code !== 'proposition') return r;
        S.n = j.n || S.n + 1;
        majBandeau();
        charger();
        toast(F('ajoute', { quoi: phrase(j) }));
        // On rend une réponse que l'appelant lira sans rien casser : il
        // affichera son message d'erreur au pire, jamais une fausse réussite.
        return r;
      }).catch(function () { return r; });
    });
  };

  /* ── Branchement ──────────────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    var o = e.target.closest ? e.target.closest('#acp-ouvrir') : null;
    if (o) { ouvrir(); return; }
    var f = e.target.closest ? e.target.closest('[data-acp="fermer"]') : null;
    if (f) { fermer(); return; }
    var r = e.target.closest ? e.target.closest('[data-retirer]') : null;
    if (r) { retirer(parseInt(r.dataset.retirer, 10)); return; }
    if (e.target.closest && e.target.closest('[data-abandonner]')) { abandonner(); return; }
    if (e.target.closest && e.target.closest('[data-envoyer]')) { envoyer(); }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && S.ouvert) fermer();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', charger);
  } else {
    charger();
  }
})();
