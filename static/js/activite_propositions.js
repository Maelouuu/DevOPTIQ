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

  var S = { n: 0, gestes: [], id: null, ouvert: false, socle: null };

  /* ══ LE PALIER DE SOUMISSION ════════════════════════════════════════
     Une carto ne part à l'examen que complète : chaque activité porte un
     garant, au moins une tâche et au moins un outil. Sinon le coordinateur
     reçoit autant de demandes que de lignes saisies.

     ⚠️ Le socle coûte un rejeu simulé côté serveur : on le lit quand la
     FENÊTRE s'ouvre — là où l'on vient chercher la réponse — et après un
     retrait. Jamais à chaque geste détourné : le bandeau, lui, ne fait que
     compter.
     ⚠️ Et tant qu'on ne l'a pas, le bouton reste ALLUMÉ. L'écran ne promet
     rien qu'il ne sache ; c'est `/envoyer` qui tranche, et il répond 409
     avec l'état — le bouton éteint n'est pas une sécurité. */
  async function chargerSocle() {
    try {
      var r = await window.__acpFetch('/api/propositions/socle');
      S.socle = r.ok ? await r.json() : null;
    } catch (_) { S.socle = null; }
    if (S.ouvert) rendre();
  }

  function chip(code, n) {
    return '<span class="acp-ex"><b>' + esc(T('socle_c_' + code)) + '</b>'
      + '<i>' + n + '</i></span>';
  }

  function blocSocle(s) {
    if (!s) return '';
    if (s.complet) {
      return '<p class="acp-socle acp-socle--ok">'
        + '<i class="fa-solid fa-circle-check" aria-hidden="true"></i>'
        + esc(T(s.total ? 'socle_ok' : 'socle_vide')) + '</p>';
    }
    var manque = s.manque || {};
    var chips = ['garant', 'tache', 'outil'].filter(function (c) {
      return manque[c] > 0;
    }).map(function (c) { return chip(c, manque[c]); }).join('');

    var noms = (s.activites || []).map(function (a) {
      return '<li><span class="acp-sa-n">' + esc(a.nom || '—') + '</span>'
        + (a.manque || []).map(function (c) {
          return '<em>' + esc(T('socle_c_' + c)) + '</em>';
        }).join('') + '</li>';
    }).join('');
    if (s.reste > 0) {
      noms += '<li class="acp-sa-plus">' + esc(F('et_autres', { n: s.reste })) + '</li>';
    }

    return '<div class="acp-socle">'
      + '<div class="acp-socle-h">'
      + '<span class="acp-socle-ic"><i class="fa-solid fa-layer-group" aria-hidden="true"></i></span>'
      + '<div><strong>' + esc(T('socle_titre')) + '</strong>'
      + '<p>' + esc(T('socle_exige')) + '</p></div>'
      + '<span class="acp-socle-j">'
      + esc(F('socle_pretes', { n: s.pretes, t: s.total })) + '</span></div>'
      + (s.rejeu
         ? '<p class="acp-socle-r">' + esc(F('socle_rejeu', { n: s.rejeu.rang })) + '</p>'
         : '')
      + (chips ? '<p class="acp-socle-l">' + esc(T('socle_manque')) + '</p>'
                 + '<div class="acp-exs">' + chips + '</div>' : '')
      + (noms ? '<p class="acp-socle-l">' + esc(T('socle_liste')) + '</p>'
                + '<ul class="acp-sa">' + noms + '</ul>' : '')
      + '<p class="acp-socle-p">' + esc(T('socle_pourquoi')) + '</p>'
      + '<p class="acp-socle-g"><i class="fa-solid fa-floppy-disk" aria-hidden="true"></i>'
      + esc(T('socle_garde')) + '</p>'
      + '</div>';
  }

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
  /* ⚠️ Le bandeau MONTRE ce qu'on a fait, il ne se contente pas de le
     compter. « 3 modifications » n'apprend rien : il fallait ouvrir la
     fenêtre pour savoir ce qu'on venait de poser. Deux gestes tiennent sur la
     ligne, le reste se dit « et n de plus ». */
  function resume() {
    var deux = S.gestes.slice(0, 2).map(phrase);
    var reste = S.gestes.length - deux.length;
    if (reste > 0) deux.push(F('et_autres', { n: reste }));
    return deux.join(' · ');
  }

  function majBandeau() {
    var b = document.getElementById('acp-bandeau');
    if (!b) return;
    b.hidden = false;
    var plein = S.n > 0;
    b.classList.toggle('est-plein', plein);
    // Le chiffre prend la place de l'icône dès qu'il y a quelque chose à
    // compter : deux repères au même endroit se disputeraient le regard.
    var gros = document.getElementById('acp-n-gros');
    gros.hidden = !plein;
    gros.textContent = plein ? S.n : '';
    document.getElementById('acp-ic').hidden = plein;
    document.getElementById('acp-titre').textContent = T('bandeau_vide');
    document.getElementById('acp-sous').textContent =
      plein ? resume() : T('bandeau_vide_d');
    var bouton = document.getElementById('acp-ouvrir');
    bouton.textContent = plein ? T('relire') : T('mes_titre');
    bouton.classList.toggle('est-vif', plein);
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
    // Le titre DIT ce qu'on soumet ; la phrase « rien n'est appliqué tant
    // que… » devient une pastille d'état à côté, et non une ligne à lire.
    document.getElementById('acp-h').textContent =
      S.n === 1 ? T('mes_1') : F('mes_n', { n: S.n || 0 });
    var ou = document.getElementById('acp-tsous');
    var noms = [];
    S.gestes.forEach(function (g) {
      var nom = g.activite || T('hors_activite');
      if (noms.indexOf(nom) < 0) noms.push(nom);
    });
    ou.textContent = noms.length === 1 ? noms[0]
      : (noms.length ? F('sur_n_fiches', { n: noms.length }) : T('sous'));
    rendre();
    chargerSocle();
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

    /* ⚠️ Un RAIL numéroté, pas une liste de réglages : l'ordre affiché est
       exactement celui du rejeu à l'application. Le verbe passe en capitales
       au-dessus, et c'est l'OBJET qu'on vient lire — c'est lui qui porte la
       police d'affichage. */
    var lignes = S.gestes.map(function (g, i) {
      var bouts = String(g.op || '').split('.');
      // ⚠️ Un outil n'appartient à aucune activité : c'est le catalogue de la
      // carto. Le dire, plutôt que de laisser une ligne muette.
      var ou = g.activite ? esc(g.activite) : esc(T('hors_activite'));
      return '<li class="acp-l">'
        + '<span class="acp-n">' + (i + 1) + '</span>'
        + '<div class="acp-l-t">'
        + '<p class="acp-verbe">' + esc(T('v_' + (bouts[1] || 'update'))) + ' '
        + esc(T('f_' + (bouts[0] || 'task'))) + '</p>'
        + '<p class="acp-objet">' + esc(g.objet || '—') + '</p>'
        + '<p class="acp-ou">' + ou + '</p></div>'
        + '<button type="button" class="acp-del" data-retirer="' + i + '" '
        + 'aria-label="' + esc(T('retirer')) + '" title="' + esc(T('retirer')) + '">'
        + '<i class="fa-solid fa-xmark"></i></button></li>';
    }).join('');

    // ⚠️ Le palier se lit AVANT le message et le bouton : c'est ce qui
    // décide si l'envoi est possible, et le lire après avoir cliqué serait
    // le découvrir trop tard.
    var bloque = !!(S.socle && !S.socle.complet);

    z.innerHTML = '<p class="acp-ordre">' + esc(T('ordre')) + '</p>'
      + '<ol class="acp-liste">' + lignes + '</ol>'
      + blocSocle(S.socle)
      + '<label class="acp-msg"><span>' + esc(T('message')) + '</span>'
      + '<textarea id="acp-message" rows="2" placeholder="'
      + esc(T('message_ph')) + '"></textarea></label>'
      + '<div class="acp-pied">'
      + '<button type="button" class="acp-danger" data-abandonner>'
      + '<i class="fa-solid fa-trash-can"></i>' + esc(T('abandonner')) + '</button>'
      + '<span class="sp"></span>'
      + '<button type="button" class="acp-ok" data-envoyer'
      + (bloque ? ' disabled aria-disabled="true"' : '') + '>'
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
    /* ⚠️ Retirer un geste peut DÉFAIRE le palier : la tâche qu'on vient
       d'enlever était peut-être la seule de son activité. Un panneau qui
       continuerait d'annoncer « complète » mentirait jusqu'au refus. */
    if (S.ouvert) await chargerSocle();
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
    if (!r.ok) {
      /* ⚠️ Le PALIER : le serveur a le dernier mot, et il rend l'état avec
         son refus. On le montre là où l'on vient de cliquer plutôt que de
         dire « erreur » — « ça ne marche pas » n'apprend rien, « il manque un
         garant sur 39 activités » dit quoi faire. */
      var j = null;
      try { j = await r.json(); } catch (_) { j = null; }
      if (j && j.code === 'socle' && j.socle) {
        S.socle = j.socle;
        rendre();
        var p = document.querySelector('.acp-socle');
        if (p && p.scrollIntoView) p.scrollIntoView({ block: 'nearest' });
        return;
      }
      signaler(T('err'));
      return;
    }
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
