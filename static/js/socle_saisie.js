/* ============================================================
   LE SOCLE — le premier remplissage d'une carto, page Activités.

   Le serveur rend le panneau COMPLET (voir socle_panneau.html) : ce script
   ne met à jour que les VALEURS, sur place. Réécrire le panneau à chaque
   écriture ferait sauter la barre au lieu de la laisser avancer, et
   perdrait le focus du champ qu'on vient de remplir.

   ⚠️ **On enveloppe `fetch`, on ne touche pas aux huit fichiers JS de la
   page.** Les tâches, les outils, les compétences, les savoirs, les HSC et
   les contraintes sont écrits par autant de scripts. Les reprendre un par un,
   c'est huit occasions d'en oublier un — et le neuvième écrit demain passerait
   à côté. C'est le motif déjà retenu pour les propositions.

   ⚠️ Ce script et `activite_propositions.js` ne cohabitent JAMAIS : le
   panneau ne paraît que si le socle n'est pas validé, et le bandeau des
   propositions que si le compte doit PROPOSER — ce qui est faux pendant la
   saisie, puisqu'il écrit directement. Deux régimes, deux écrans.
   ============================================================ */
(function () {
  'use strict';

  var panneau = document.getElementById('scl');
  if (!panneau) return;

  var L = window.SOCLE_I18N || {};
  var S = window.SOCLE_ETAT || {};

  function T(k) { return L[k] !== undefined ? L[k] : k; }
  function F(k, vars) {
    var s = T(k);
    Object.keys(vars || {}).forEach(function (c) {
      s = s.split('[[' + c + ']]').join(vars[c]);
    });
    return s;
  }
  /* ⚠️ Le singulier ne couvre pas les mêmes nombres d'une langue à l'autre :
     « 0 activité » en français, « 0 activities » en anglais. */
  function nf(cle, n, extra) {
    var un = (L.lang === 'en') ? (n === 1) : (n < 2);
    var vars = { n: n };
    Object.keys(extra || {}).forEach(function (k) { vars[k] = extra[k]; });
    return F(cle + (un ? '_1' : '_n'), vars);
  }
  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function $(id) { return document.getElementById(id); }

  /* ⚠️ `getBoundingClientRect()` rend DÉJÀ des pixels d'écran — le zoom du
     corps y est appliqué. Seules les coordonnées qu'on ÉCRIT repassent par
     lui : on DIVISE avant d'écrire `left`/`top`. Septième fois que ce piège
     se présente dans cette application. */
  function zoomCorps() {
    var z = parseFloat(getComputedStyle(document.body).zoom || '1');
    return (z && isFinite(z) && z > 0) ? z : 1;
  }

  /* ── Ce que le panneau dit ─────────────────────────────────────────── */

  function complet() {
    var p = S.palier || {};
    return !!p.complet;
  }

  /* ── LE COMPTEUR ──────────────────────────────────────
     Un arc de 240°, du bas-gauche au bas-droit : la forme d'un cadran de
     tableau de bord, pas une barre pliée. Les graduations marquent chaque
     ACTIVITÉ — on compte des activités, pas des pourcentages, et c'est ce
     qui fait qu'on lit « 8 sur 10 » sans aller chercher le chiffre.

     ⚠️ TAILLE est écrite pour le zoom du corps : `body:has(.pg-root)` porte
     `zoom: .8` (ui-theme), donc 218 px de mise en page font 174 px RÉELS —
     la taille éprouvée sur maquette. La maquette, elle, vivait dans une page
     SANS ce zoom : reprise telle quelle, elle arriverait 20 % plus petite.

     ⚠️ Les proportions sont MESURÉES, pas choisies au jugé. Et la mesure a
     trouvé ce que l'œil n'avait pas vu — la maquette portait le même
     défaut : un balayage de 240° fait pointer l'aiguille vers le BAS à ses
     deux extrêmes, où elle atteint C + r/2, c'est-à-dire DANS les chiffres.
     Le chiffre étant peint par-dessus, la pointe paraissait s'arrêter au
     milieu du « 6 ». On DESCEND donc la lecture (0,805·T) plutôt que de
     raccourcir l'aiguille — un pointeur à 31 % du rayon ne ressemble plus
     à rien — et la boîte passe à 0,92·T. Les valeurs en dur (moyeu,
     aiguille, graduations) suivent le facteur `k`, sinon elles ne
     grandiraient pas avec le cadran. */
  var TAILLE = 218, DEB = -120, SWEEP = 240;
  /* Au-delà, les graduations se touchent et l'échelle se lit comme une
     hachure : l'arc fait 354 px de long, soit 8,9 px entre deux traits à
     quarante. Une carto du pilote en porte six cents. */
  var GRADS_MAX = 40;

  function pt(c, r, deg) {
    var a = (deg - 90) * Math.PI / 180;
    return [c + r * Math.cos(a), c + r * Math.sin(a)];
  }
  function arc(c, r, d1, d2) {
    var a = pt(c, r, d1), b = pt(c, r, d2);
    return 'M ' + a[0].toFixed(2) + ' ' + a[1].toFixed(2)
      + ' A ' + r.toFixed(2) + ' ' + r.toFixed(2) + ' 0 '
      + (Math.abs(d2 - d1) > 180 ? 1 : 0) + ' 1 '
      + b[0].toFixed(2) + ' ' + b[1].toFixed(2);
  }

  function rendreJauge() {
    var zone = $('scl-jauge');
    if (!zone) return;
    var p = S.palier || {};
    var total = p.total || 0, pretes = p.pretes || 0;
    var plein = complet();
    var t = total ? pretes / total : 0;
    var k = TAILLE / 174;
    var C = TAILLE / 2, R = TAILLE * 0.388, EP = TAILLE * 0.0765;
    var H = TAILLE * 0.92, fin = DEB + t * SWEEP;
    /* ⚠️ Les couleurs sont des ATTRIBUTS SVG, donc aucun jeton CSS ne
       les atteint : elles s'écrivent à la main, comme celles du relief de la
       page Compétences. Ce sont les valeurs de --scl-or-f et --scl-ok-f. */
    var vif = plein ? '#10b981' : '#d97706';
    var fonce = plein ? '#047857' : '#b45309';

    var grads = '';
    if (total && total <= GRADS_MAX) {
      for (var i = 0; i <= total; i++) {
        var d = DEB + (i / total) * SWEEP;
        var g1 = pt(C, R - EP / 2 - 3 * k, d);
        var g2 = pt(C, R - EP / 2 - 9 * k, d);
        grads += '<line x1="' + g1[0].toFixed(1) + '" y1="' + g1[1].toFixed(1)
          + '" x2="' + g2[0].toFixed(1) + '" y2="' + g2[1].toFixed(1)
          + '" stroke="' + (i <= pretes ? fonce : '#cdb795')
          + '" stroke-width="' + (2 * k).toFixed(1)
          + '" stroke-linecap="round"></line>';
      }
    }
    var ai = pt(C, R - EP - 14 * k, fin);
    var a1 = pt(C, 7 * k, fin - 90), a2 = pt(C, 7 * k, fin + 90);
    var aiguille = '<path d="M ' + ai[0].toFixed(1) + ' ' + ai[1].toFixed(1)
      + ' L ' + a1[0].toFixed(1) + ' ' + a1[1].toFixed(1)
      + ' L ' + a2[0].toFixed(1) + ' ' + a2[1].toFixed(1)
      + ' Z" fill="' + fonce + '"></path>'
      + '<circle cx="' + C + '" cy="' + C + '" r="' + (6.5 * k).toFixed(1)
      + '" fill="' + fonce + '"></circle>'
      + '<circle cx="' + C + '" cy="' + C + '" r="' + (2.6 * k).toFixed(1)
      + '" fill="#fffdf8"></circle>';

    zone.innerHTML = '<svg viewBox="0 0 ' + TAILLE + ' ' + H.toFixed(1)
      + '" width="' + TAILLE + '" height="' + H.toFixed(1)
      + '" role="img" aria-label="'
      + esc(nf('pretes', pretes, { t: total })) + '">'
      + '<defs><linearGradient id="scl-g" x1="0" y1="1" x2="1" y2="0">'
      + '<stop offset="0" stop-color="' + vif + '"></stop>'
      + '<stop offset="1" stop-color="' + fonce + '"></stop>'
      + '</linearGradient></defs>'
      + '<path d="' + arc(C, R, DEB, DEB + SWEEP) + '" fill="none"'
      + ' stroke="#e4d2ae" stroke-width="' + EP.toFixed(1)
      + '" stroke-linecap="round"></path>'
      + (t > 0.001 ? '<path d="' + arc(C, R, DEB, fin) + '" fill="none"'
        + ' stroke="url(#scl-g)" stroke-width="' + EP.toFixed(1)
        + '" stroke-linecap="round"></path>' : '')
      + grads + aiguille
      + '<text class="scl-n" x="' + C + '" y="' + (TAILLE * 0.805).toFixed(1)
      + '" text-anchor="middle" font-size="' + (TAILLE * 0.205).toFixed(1)
      + '">' + pretes + '</text>'
      + '<text class="scl-d" x="' + C + '" y="' + (TAILLE * 0.895).toFixed(1)
      + '" text-anchor="middle" font-size="' + (TAILLE * 0.0735).toFixed(1)
      + '">' + esc(F('sur_total', { n: total })) + '</text>'
      + '</svg>';
  }

  /* ── Les trois exigences ─────────────────────────────────

     ⚠️ Les trois clés sont écrites EN TOUTES LETTRES : `T('x_' + code)` est
     une clé CONSTRUITE, que les contrôles de couverture relèvent comme la
     clé « x_ » — et le jour où une exigence s'ajoute, son libellé
     s'afficherait en clair. Même règle que dans le gabarit. */
  var EXIGENCES = ['garant', 'tache', 'outil'];
  var LIB = { garant: 'x_garant', tache: 'x_tache', outil: 'x_outil' };

  function rendreExigences() {
    var zone = $('scl-ex');
    if (!zone) return;
    var p = S.palier || {};
    var total = p.total || 0;
    zone.innerHTML = EXIGENCES.map(function (code) {
      /* ⚠️ `manque[code]` compte les activités qui en MANQUENT. Ce qu'on
         montre, c'est celles qui l'ONT : une barre qui se remplit à mesure
         qu'on avance, pas une barre qui se vide. */
      var n = total - ((p.manque || {})[code] || 0);
      var pc = total ? Math.round(n * 100 / total) : 0;
      return '<div class="scl-ex-l'
        + (total && n >= total ? ' est-pleine' : '') + '">'
        + '<span class="scl-ex-lib">' + esc(T(LIB[code])) + '</span>'
        + '<span class="scl-ex-b"><i style="width: ' + pc + '%"></i></span>'
        + '<span class="scl-ex-n">' + n + ' / ' + total + '</span></div>';
    }).join('');
  }

  function majValeurs() {
    var p = S.palier || {};
    var pc = p.total ? Math.round((p.pretes || 0) * 100 / p.total) : 0;
    panneau.classList.toggle('est-complet', complet());
    rendreJauge();
    rendreExigences();

    var voir = $('scl-voir');
    var liste = $('scl-liste');
    var actes = p.activites || [];
    voir.hidden = !actes.length;
    if (!actes.length) {
      // ⚠️ La zone de la liste porte alors la phrase de bord (carto vide,
      // ou plus rien à compléter) : la replier la ferait disparaître.
      liste.hidden = false;
    } else {
      var reste = (p.total || 0) - (p.pretes || 0);
      var ouvert = !liste.hidden;
      voir.innerHTML = '<i class="fa-solid fa-chevron-'
        + (ouvert ? 'up' : 'down') + '"></i>'
        + esc(ouvert ? T('cacher') : nf('voir', reste));
    }
    rendreListe();
    majRail(pc, p);
  }

  /* ⚠️ La liste se rend ICI, et nulle part ailleurs. Rendue aussi par le
     gabarit, elle restait dans l'état du chargement de page : `relire()` met
     à jour les chiffres après chaque écriture, pas le HTML du serveur. Le
     bouton annonçait « Masquer » au-dessus de RIEN, et l'écran ne disait
     plus OÙ était ce qui manque — c'est le défaut relevé à l'usage. */
  var CHIP = { garant: 'c_garant', tache: 'c_tache', outil: 'c_outil' };

  function rendreListe() {
    var liste = $('scl-liste');
    if (!liste) return;
    var p = S.palier || {};
    var actes = p.activites || [];
    /* Les deux cas de bord se disent ICI : la zone de la liste est le seul
       endroit de ce panneau qui parle des activités, et une phrase posée
       ailleurs aurait demandé un troisième emplacement à tenir. */
    if (!p.total) {
      liste.innerHTML = '<p class="scl-l-dit">' + esc(T('vide')) + '</p>';
      return;
    }
    if (!actes.length) {
      liste.innerHTML = '<p class="scl-l-dit est-ok">' + esc(T('pret'))
        + '</p>';
      return;
    }
    var html = actes.map(function (a) {
      var pastilles = (a.manque || []).map(function (code) {
        return '<i class="scl-chip scl-chip--' + code + '">'
          + esc(T(CHIP[code] || code)) + '</i>';
      }).join('');
      return '<button type="button" class="scl-l" data-scl-act="' + a.id + '">'
        + '<span class="scl-l-nom">' + esc(a.nom) + '</span>'
        + '<span class="scl-l-m">' + pastilles + '</span></button>';
    }).join('');
    if (p.reste) {
      html += '<p class="scl-l-reste">' + esc(F('et_autres', { n: p.reste })) + '</p>';
    }
    liste.innerHTML = html;
  }

  function majRail(pc, p) {
    var rail = $('scl-rail');
    if (!rail) return;
    rail.classList.toggle('est-complet', complet());
    rail.querySelector('.scl-rail-anneau').style.setProperty('--p', pc);
    $('scl-rail-n').textContent = p.pretes || 0;
    $('scl-rail-t').textContent = '/ ' + (p.total || 0);
  }

  /* ── L'action : elle dépend de l'état ET du regard ─────────────────── */

  function jeValide() { return panneau.getAttribute('data-valide') === '1'; }
  function jeRemplis() { return panneau.getAttribute('data-remplis') === '1'; }

  function bouton(action, cle, classe, icone) {
    return '<button type="button" class="scl-b ' + classe + '" data-scl="'
      + action + '"><i class="fa-solid ' + icone + '"></i>'
      + esc(T(cle)) + '</button>';
  }

  function majAction() {
    var zone = $('scl-act');
    if (!zone) return;
    var soumis = S.etat === 'soumis';

    if (soumis && jeValide()) {
      // Le coordinateur : ce qu'on lui demande, et les deux sorties.
      // ⚠️ `<q>`, jamais des chevrons ecrits a la main : « » est une
      // convention FRANCAISE, et le navigateur pose les guillemets de la
      // langue du document. Releve a l'ecran : « J'ai repris... » sortait
      // avec ses chevrons au milieu d'une phrase anglaise.
      zone.innerHTML = '<p class="scl-attente"><b>' + esc(T('a_valider'))
        + '</b>' + esc(quiEtQuand()) + (S.message
          ? ' <q>' + esc(S.message) + '</q>' : '') + '</p>'
        + '<div class="scl-form-b">'
        + bouton('renvoyer', 'renvoyer', 'scl-b--sec', 'fa-rotate-left')
        + bouton('valider', 'valider', '', 'fa-circle-check')
        + '</div>';
      return;
    }
    if (soumis) {
      // Le champion : il attend, et les fiches ne bougent plus.
      zone.innerHTML = '<p class="scl-attente"><b>' + esc(T('attente'))
        + '</b>' + esc(T('attente_d')) + '</p>';
      return;
    }
    // En saisie. ⚠️ Un coordinateur valide DIRECTEMENT : il n'a personne à
    // qui soumettre, et attendre une soumission qui ne viendra jamais le
    // laisserait coincé.
    if (jeValide()) {
      zone.innerHTML = complet()
        ? bouton('valider', 'valider', '', 'fa-circle-check')
        : '<p class="scl-attente">' + esc(T('coord_attend')) + '</p>';
      return;
    }
    if (!jeRemplis()) { zone.innerHTML = ''; return; }
    var b = bouton('soumettre', 'soumettre', 'scl-b--ambre', 'fa-paper-plane');
    zone.innerHTML = complet() ? b
      : b.replace('<button ', '<button disabled ');
  }

  function quiEtQuand() {
    var quand = S.le ? new Date(S.le) : null;
    // ⚠️ Le serveur écrit en UTC SANS fuseau : sans le « Z », deux heures
    // de décalage à Paris.
    if (S.le && !/[Zz+]/.test(S.le)) quand = new Date(S.le + 'Z');
    var d = quand ? quand.toLocaleDateString(L.lang === 'en' ? 'en-GB' : 'fr-FR',
                                             { day: 'numeric', month: 'short' }) : '';
    return F('soumis_par', { q: S.par || '—', d: d });
  }

  /* ── Le formulaire, DANS le panneau ────────────────────────────────── */

  function formulaire(action, placeholder, exigeMot) {
    var zone = $('scl-act');
    zone.innerHTML = '<div class="scl-form">'
      + '<textarea id="scl-mot" placeholder="' + esc(T(placeholder)) + '"></textarea>'
      + '<p class="scl-err" id="scl-err" hidden></p>'
      + '<div class="scl-form-b">'
      + '<button type="button" class="scl-b scl-b--sec" data-scl="annuler">'
      + '<i class="fa-solid fa-xmark"></i>' + esc(T('annuler')) + '</button>'
      + '<button type="button" class="scl-b' + (exigeMot ? ' scl-b--ambre' : '')
      + '" data-scl="' + action + '-ok"><i class="fa-solid fa-check"></i>'
      + esc(T('confirmer')) + '</button>'
      + '</div></div>';
    var champ = $('scl-mot');
    if (champ) champ.focus();
  }

  function erreur(texte) {
    var e = $('scl-err');
    if (e) { e.textContent = texte; e.hidden = false; return; }
    if (window.optiqAlert) window.optiqAlert(texte); else alert(texte);
  }

  async function poster(chemin, corps) {
    try {
      var r = await fetch(chemin, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(corps || {})
      });
      var j = await r.json().catch(function () { return {}; });
      if (!r.ok) { erreur(j.error || T('err')); return false; }
      return true;
    } catch (e) { erreur(T('err')); return false; }
  }

  /* ── La liste de travail : chaque nom OUVRE son activité ───────────── */

  function allerA(activityId) {
    var hote = document.querySelector('.tasks-section-modern[data-acp-act="'
                                      + activityId + '"]');
    var carte = hote ? hote.closest('.activity-container') : null;
    if (!carte) {
      if (window.optiqAlert) window.optiqAlert(T('introuvable'));
      return;
    }
    var tete = carte.querySelector('.activity-header');
    // ⚠️ On n'ouvre que si la fiche est FERMÉE : un second clic la
    // refermerait juste après l'avoir montrée.
    if (tete && !hote.offsetParent) tete.click();
    carte.scrollIntoView({ block: 'center', behavior: 'smooth' });
    carte.classList.add('est-pointee');
    setTimeout(function () { carte.classList.remove('est-pointee'); }, 1600);
  }

  /* ── Le « i » : une carte posée sur le BODY ────────────────────────── */

  var carteInfo = null;

  function fermerInfo() {
    if (carteInfo) { carteInfo.remove(); carteInfo = null; }
  }

  function ouvrirInfo(bouton_) {
    if (carteInfo) { fermerInfo(); return; }
    var tpl = $('scl-i-tpl');
    if (!tpl) return;
    carteInfo = document.createElement('div');
    carteInfo.className = 'scl-info';
    carteInfo.setAttribute('role', 'tooltip');
    carteInfo.appendChild(tpl.content.cloneNode(true));
    document.body.appendChild(carteInfo);

    var z = zoomCorps();
    var r = bouton_.getBoundingClientRect();
    var h = carteInfo.offsetHeight;        // déjà dans le repère zoomé
    var w = carteInfo.offsetWidth;
    // Sous le bouton quand il n'y a pas la place au-dessus.
    var dessus = r.top > (h * z + 20);
    var hautReel = dessus ? (r.top - 10) : (r.bottom + 10);
    carteInfo.style.top = (dessus ? (hautReel / z) - h : hautReel / z) + 'px';
    var centre = r.left + r.width / 2;
    var gauche = centre / z - w / 2;
    var min = 16 / z;
    var max = (window.innerWidth - 16) / z - w;
    carteInfo.style.left = Math.max(min, Math.min(gauche, max)) + 'px';
  }

  /* ── Le rappel latéral ─────────────────────────────────────────────── */

  /* ⚠️ Pas d'`IntersectionObserver` : il ne tire PAS dans le volet de mise
     au point, où un observateur neuf ne rend rien — pas même l'appel initial
     que la spécification garantit. Un calcul au défilement, lui, se prouve en
     rejouant la fonction à chaque position. */
  function majVisibiliteRail() {
    var rail = $('scl-rail');
    if (!rail) return;
    var r = panneau.getBoundingClientRect();
    rail.hidden = !(r.bottom < 40);
  }

  /* ── Relire après une écriture ─────────────────────────────────────── */

  var minuteur = null;

  async function relire() {
    try {
      var r = await fetch('/api/propositions/socle');
      if (!r.ok) return;
      var j = await r.json();
      // ⚠️ Un changement d'ÉTAT change la FORME du panneau (ce qu'on y
      // montre, les boutons) : on recharge plutôt que de rebâtir deux
      // rendus du même écran, qui finiraient par diverger.
      if (j.etat !== S.etat || !j.actif) { location.reload(); return; }
      S = j;
      majValeurs();
      majAction();
    } catch (e) { /* le panneau reste à sa dernière valeur connue */ }
  }

  function relirePlusTard() {
    clearTimeout(minuteur);
    minuteur = setTimeout(relire, 260);
  }

  var ECRITURES = { POST: 1, PUT: 1, PATCH: 1, DELETE: 1 };

  function enveloppeFetch() {
    var vrai = window.fetch;
    if (!vrai || window.__sclFetch) return;
    window.__sclFetch = true;
    window.fetch = function (entree, options) {
      var methode = String((options && options.method)
                           || (entree && entree.method) || 'GET').toUpperCase();
      var url = String((entree && entree.url) || entree || '');
      return vrai.apply(this, arguments).then(function (reponse) {
        if (!ECRITURES[methode] || url.indexOf('/api/propositions/socle') >= 0) {
          return reponse;
        }
        // ⚠️ On CLONE : un flux ne se lit qu'une fois, et l'appelant va le
        // lire à son tour.
        if (reponse.status === 409) {
          reponse.clone().json().then(function (j) {
            if (j && j.code === 'socle_en_examen') {
              if (window.optiqAlert) window.optiqAlert(j.error);
            }
          }).catch(function () { });
        }
        if (reponse.ok) relirePlusTard();
        return reponse;
      });
    };
  }

  /* ── Les clics ─────────────────────────────────────────────────────── */

  panneau.addEventListener('click', function (ev) {
    var cible = ev.target.closest('[data-scl], [data-scl-act]');
    if (!cible) return;
    var act = cible.getAttribute('data-scl-act');
    if (act) { allerA(act); return; }

    switch (cible.getAttribute('data-scl')) {
      case 'i':
        ev.stopPropagation();
        ouvrirInfo(cible);
        break;
      case 'liste':
        var liste = $('scl-liste');
        liste.hidden = !liste.hidden;
        majValeurs();
        break;
      case 'soumettre':
        formulaire('soumettre', 'mot_ph', false);
        break;
      case 'renvoyer':
        formulaire('renvoyer', 'retour_ph', true);
        break;
      case 'annuler':
        majAction();
        break;
      case 'soumettre-ok':
        envoyer('/api/propositions/socle/soumettre', 'message', false);
        break;
      case 'renvoyer-ok':
        envoyer('/api/propositions/socle/renvoyer', 'commentaire', true);
        break;
      case 'valider':
        envoyer('/api/propositions/socle/valider', 'commentaire', false);
        break;
    }
  });

  async function envoyer(chemin, cle, exigeMot) {
    var champ = $('scl-mot');
    var mot = champ ? champ.value.trim() : '';
    if (exigeMot && !mot) { erreur(T('err_mot')); return; }
    var corps = {};
    corps[cle] = mot;
    if (S.entity_id) corps.entity_id = S.entity_id;
    if (await poster(chemin, corps)) location.reload();
  }

  var rail = $('scl-rail');
  if (rail) rail.addEventListener('click', function () {
    panneau.scrollIntoView({ block: 'start', behavior: 'smooth' });
  });

  document.addEventListener('click', function (ev) {
    if (carteInfo && !ev.target.closest('.scl-i')) fermerInfo();
  });
  /* ⚠️ En CAPTURE : la carte est posée sur le body, elle ne suit pas son
     bouton quand ce qu'il y a dessous défile. */
  window.addEventListener('scroll', function () {
    fermerInfo();
    majVisibiliteRail();
  }, true);
  window.addEventListener('resize', function () {
    fermerInfo();
    majVisibiliteRail();
  });

  // Exposé pour le banc : dans le volet de mise au point, aucun événement
  // `scroll` ne tire — on rejoue la fonction à la main.
  window.__sclRail = majVisibiliteRail;

  /* ⚠️ La liste s'ouvre D'ELLE-MÊME quand il reste peu à faire : c'est le
     moment où l'on chasse les dernières activités, et c'est précisément ce
     qu'on reprochait à l'écran — il ne disait pas OÙ. Au-delà elle reste
     pliée : vingt-huit lignes enterreraient les fiches qu'elles désignent.
     Posé ICI, avant le premier rendu, pour que le bouton dise la vérité —
     et une seule fois, sinon chaque écriture rouvrirait ce que l'on vient
     de replier. */
  var OUVRE_SI = 6;
  (function ouvrirSiCourt() {
    var p = S.palier || {};
    var reste = (p.total || 0) - (p.pretes || 0);
    var liste = $('scl-liste');
    if (liste && reste && reste <= OUVRE_SI) liste.hidden = false;
  })();

  majValeurs();
  majAction();
  majVisibiliteRail();
  enveloppeFetch();
})();
