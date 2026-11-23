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

  /* ⚠️ Le singulier ne couvre pas les mêmes nombres d'une langue à l'autre :
     « 0 activité » en français, « 0 activities » en anglais. */
  function nf(cle, n) {
    var un = (L.lang === 'en') ? (n === 1) : (n < 2);
    return F(cle + (un ? '_1' : '_n'), { n: n });
  }

  /* ── Les familles : un pictogramme et la couleur de la PAGE où la donnée
     vit (Activités violet, Outils orange, Rôles vert, Compétences bleu).
     C'est la convention de la fenêtre d'import, et elle veut dire quelque
     chose — ce n'est pas un arc-en-ciel décoratif. */
  var FAM = {
    garant:      { ic: 'fa-user-shield', c: '#059669' },
    task:        { ic: 'fa-list-check',  c: '#7c3aed' },
    tool:        { ic: 'fa-wrench',      c: '#ea580c' },
    skill:       { ic: 'fa-certificate', c: '#2563eb' },
    savoir:      { ic: 'fa-book',        c: '#2563eb' },
    savoirfaire: { ic: 'fa-screwdriver-wrench', c: '#0e7490' },
    aptitude:    { ic: 'fa-seedling',    c: '#0e7490' },
    hsc:         { ic: 'fa-comments',    c: '#6d28d9' },
    contrainte:  { ic: 'fa-triangle-exclamation', c: '#b91c1c' },
    donnee:      { ic: 'fa-file-lines',  c: '#475569' }
  };
  /* L'ordre dans lequel on REMPLIT une activité : le garant, les tâches,
     les outils, puis ce qu'il faut savoir, puis les contraintes. */
  var ORDRE = ['garant', 'task', 'tool', 'skill', 'savoir', 'savoirfaire',
               'aptitude', 'hsc', 'contrainte', 'donnee'];
  function famDe(g) { return String(g.op || '').split('.')[0] || 'task'; }
  function rangFam(f) {
    var i = ORDRE.indexOf(f);
    return i < 0 ? ORDRE.length : i;
  }

  var S = { n: 0, gestes: [], id: null, ouvert: false, socle: null,
            socleOuvert: false, fam: null, texte: '' };

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

  /* ⚠️⚠️ **Le défaut que l'usage a relevé : « ça me dit 1 truc manquant alors
     que j'ai rempli 30 % des activités ».** Le serveur rendait le bon compte
     — mesuré, `{garant: 0, outil: 26, tache: 26}` sur 36 activités — mais
     l'écran n'affichait qu'une PASTILLE PAR FAMILLE. Quand une famille est
     déjà complète partout (le garant vient de l'import carto), il n'en reste
     qu'UNE : on lisait « une chose manque » là où VINGT-SIX activités sont
     incomplètes.

     Le chiffre de tête est donc le nombre d'ACTIVITÉS à compléter. Les
     familles passent dessous, en détail, et chacune dit sur combien
     d'activités elle manque. */
  function detailManque(manque) {
    return ['garant', 'tache', 'outil'].filter(function (c) {
      return manque[c] > 0;
    }).map(function (c) {
      return '<span class="acp-ex"><b>' + esc(T('socle_c_' + c)) + '</b>'
        + '<i>' + manque[c] + '</i></span>';
    }).join('');
  }

  /* ⚠️ Le socle n'est plus un pavé DANS le défilement : c'est la bande qui
     décide si l'envoi est possible, elle reste sous les yeux. Les deux
     paragraphes d'explication sont passés derrière un « i » — c'est le motif
     de la maison, et ils occupaient 160 px de la hauteur utile. */
  function rendreSocle() {
    var z = document.getElementById('acp-socle-z');
    if (!z) return;
    var s = S.socle;
    if (!s || !S.gestes.length) { z.innerHTML = ''; z.hidden = true; return; }
    z.hidden = false;

    if (s.complet) {
      z.innerHTML = '<div class="acp-sb acp-sb--ok">'
        + '<span class="acp-sb-ic"><i class="fa-solid fa-circle-check"></i></span>'
        + '<p class="acp-sb-t">' + esc(T(s.total ? 'socle_ok' : 'socle_vide')) + '</p>'
        + '</div>';
      return;
    }

    var reste = Math.max(0, (s.total || 0) - (s.pretes || 0));
    var part = s.total ? Math.round((s.pretes / s.total) * 100) : 0;
    var noms = (s.activites || []).map(function (a) {
      return '<li><button type="button" class="acp-sa-b" data-aller="' + a.id + '">'
        + '<span class="acp-sa-n">' + esc(a.nom || '—') + '</span>'
        + (a.manque || []).map(function (c) {
          return '<em>' + esc(T('socle_c_' + c)) + '</em>';
        }).join('')
        + '<i class="fa-solid fa-arrow-right" aria-hidden="true"></i></button></li>';
    }).join('');
    if (s.reste > 0) {
      noms += '<li class="acp-sa-plus">' + esc(F('et_autres', { n: s.reste })) + '</li>';
    }

    z.innerHTML = '<div class="acp-sb">'
      + '<span class="acp-sb-ic"><i class="fa-solid fa-layer-group"></i></span>'
      + '<div class="acp-sb-t">'
      /* LE chiffre : des ACTIVITÉS, pas des familles. */
      + '<strong>' + esc(nf('socle_restent', reste)) + '</strong>'
      + '<span class="acp-sb-j"><i style="width:' + part + '%"></i></span>'
      + '<span class="acp-sb-p">' + esc(F('socle_barre', { n: s.pretes, t: s.total }))
      + '</span></div>'
      + '<button type="button" class="acp-sb-v" data-socle-voir aria-expanded="'
      + (S.socleOuvert ? 'true' : 'false') + '">'
      + esc(T(S.socleOuvert ? 'socle_cacher' : 'socle_voir'))
      + '<i class="fa-solid fa-chevron-' + (S.socleOuvert ? 'up' : 'down') + '"></i></button>'
      + '</div>'
      + (s.rejeu
         ? '<p class="acp-sb-r">' + esc(F('socle_rejeu', { n: s.rejeu.rang })) + '</p>'
         : '')
      + (S.socleOuvert
         ? '<div class="acp-sb-d">'
           + '<p class="acp-sb-l">' + esc(T('socle_manque')) + '</p>'
           + '<div class="acp-exs">' + detailManque(s.manque || {}) + '</div>'
           + (noms ? '<p class="acp-sb-l">' + esc(T('socle_liste')) + '</p>'
                     + '<ul class="acp-sa">' + noms + '</ul>' : '')
           + '</div>'
         : '');
    var h = z.querySelector('.acp-sb-t strong');
    if (h) h.appendChild(boutonSocleInfo());
  }

  /* Les deux paragraphes qui expliquaient la règle — pourquoi d'un bloc, et
     que rien n'est perdu — tiennent derrière un « i ». */
  function boutonSocleInfo() {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'acp-i';
    b.setAttribute('aria-label', T('socle_titre'));
    b.title = T('socle_titre') + ' — ' + T('socle_exige') + ' ' + T('socle_pourquoi')
      + ' ' + T('socle_garde');
    b.innerHTML = '<i class="fa-solid fa-circle-info" aria-hidden="true"></i>';
    return b;
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
    placer();
    if (S.ouvert) rendre();
  }

  /* ── La fenêtre : on relit, on retire, on envoie ───────────────────── */
  function ouvrir() {
    var w = document.getElementById('acp-win');
    if (!w) return;
    w.hidden = false;
    S.ouvert = true;
    // On rouvre sur TOUT : un filtre gardé d'une fois sur l'autre ferait
    // croire qu'il manque des gestes.
    S.fam = null; S.texte = ''; S.socleOuvert = false;
    rendre();
    chargerSocle();
  }

  /* Le titre DIT ce qu'on soumet ; la phrase « rien n'est appliqué tant
     que… » est une pastille d'état à côté, et non une ligne à lire.
     ⚠️ Il se refait à chaque rendu, pas seulement à l'ouverture : retirer un
     geste laissait « 27 modifications » au-dessus d'une liste qui en montre
     25. */
  function majTitre() {
    var h = document.getElementById('acp-h');
    if (!h) return;
    h.textContent = S.n === 1 ? T('mes_1') : F('mes_n', { n: S.n || 0 });
    var noms = [];
    S.gestes.forEach(function (g) {
      var nom = g.activite || T('hors_activite');
      if (noms.indexOf(nom) < 0) noms.push(nom);
    });
    document.getElementById('acp-tsous').textContent =
      noms.length === 1 ? noms[0]
        : (noms.length ? F('sur_n_fiches', { n: noms.length }) : T('sous'));
  }

  function fermer() {
    var w = document.getElementById('acp-win');
    if (w) w.hidden = true;
    S.ouvert = false;
  }

  /* ── Le filtre ────────────────────────────────────────────────────
     ⚠️ « Tout a la même tronche, pas de filtre, c'est pas agréable d'aller
     chercher là-dedans » — mesuré : 27 gestes de 86 px, 2361 px de liste
     pour 544 px visibles. Une pastille par famille PRÉSENTE (jamais les dix
     : on ne propose pas de filtrer sur rien), plus une recherche sur le nom
     de l'objet et sur l'activité. */
  function rendreFiltres() {
    var z = document.getElementById('acp-filtres');
    if (!z) return;
    if (S.gestes.length < 6) { z.innerHTML = ''; z.hidden = true; return; }
    z.hidden = false;
    var compte = {};
    S.gestes.forEach(function (g) {
      var f = famDe(g);
      compte[f] = (compte[f] || 0) + 1;
    });
    var fams = Object.keys(compte).sort(function (a, b) {
      return rangFam(a) - rangFam(b);
    });
    var puces = fams.map(function (f) {
      var d = FAM[f] || FAM.donnee;
      return '<button type="button" class="acp-pf" data-fam="' + f + '"'
        + ' aria-pressed="' + (S.fam === f) + '" style="--fc:' + d.c + '">'
        + '<i class="fa-solid ' + d.ic + '" aria-hidden="true"></i>'
        + esc(T('g_' + f)) + '<b>' + compte[f] + '</b></button>';
    }).join('');
    z.innerHTML = '<div class="acp-pfs">'
      + '<button type="button" class="acp-pf acp-pf--tout" data-fam=""'
      + ' aria-pressed="' + (S.fam === null) + '">'
      + esc(T('filtre_tout')) + '<b>' + S.gestes.length + '</b></button>'
      + puces + '</div>'
      + '<label class="acp-rech"><i class="fa-solid fa-magnifying-glass"></i>'
      + '<input type="search" id="acp-rech" placeholder="' + esc(T('filtre_ph'))
      + '" aria-label="' + esc(T('filtre_ph')) + '"></label>';
    var champ = document.getElementById('acp-rech');
    if (champ) {
      champ.value = S.texte;
      /* ⚠️ `input`, pas `change` : sur `change` le filtre n'agirait qu'à la
         perte du focus, sans la moindre erreur pour le dire. Et on ne
         re-rend QUE la liste — réécrire la barre ferait perdre le curseur
         du champ qu'on tape. */
      champ.addEventListener('input', function () {
        S.texte = champ.value;
        rendreListe();
      });
    }
  }

  function retenus() {
    var txt = S.texte.trim().toLowerCase();
    return S.gestes.map(function (g, i) { return { g: g, rang: i }; })
      .filter(function (e) {
        if (S.fam && famDe(e.g) !== S.fam) return false;
        if (!txt) return true;
        return ((e.g.objet || '') + ' ' + (e.g.activite || ''))
          .toLowerCase().indexOf(txt) >= 0;
      });
  }

  /* ── La liste, GROUPÉE PAR FAMILLE ────────────────────────────────
     ⚠️ L'ordre affiché n'est donc plus celui du rejeu. Ce n'est pas une
     perte : le numéro de chaque ligne reste son RANG réel — c'est lui que
     `data-retirer` porte, et c'est lui que le serveur rejoue. Grouper ne
     change que la lecture. */
  function rendreListe() {
    var z = document.getElementById('acp-corps');
    if (!z) return;
    if (!S.gestes.length) { rendreMiennes(z); return; }

    var liste = retenus();
    if (!liste.length) {
      z.innerHTML = '<p class="acp-vide">' + esc(T('filtre_rien')) + '</p>';
      return;
    }
    var paquets = {};
    liste.forEach(function (e) {
      var f = famDe(e.g);
      (paquets[f] = paquets[f] || []).push(e);
    });

    z.innerHTML = Object.keys(paquets).sort(function (a, b) {
      return rangFam(a) - rangFam(b);
    }).map(function (f) {
      var d = FAM[f] || FAM.donnee;
      var lignes = paquets[f].map(function (e) {
        var verbe = String(e.g.op || '').split('.')[1] || 'update';
        // ⚠️ Un outil n'appartient à aucune activité : c'est le catalogue de
        // la carto. Le dire, plutôt que de laisser une ligne muette.
        var ou = e.g.activite ? esc(e.g.activite) : esc(T('hors_activite'));
        return '<li class="acp-l">'
          + '<span class="acp-n">' + (e.rang + 1) + '</span>'
          + '<div class="acp-l-t">'
          + '<p class="acp-objet">' + esc(e.g.objet || '—') + '</p>'
          /* ⚠️ Le nom de l'activité est dans un <span> : le `gap` d'une boîte
             flex ne s'applique qu'entre ÉLÉMENTS, jamais autour d'un nœud de
             texte nu — relevé à l'écran, « AddManage Commercial Offer ». */
          + '<p class="acp-ou"><em>' + esc(T('v_' + verbe)) + '</em>'
          + '<span>' + ou + '</span></p>'
          + '</div>'
          + '<button type="button" class="acp-del" data-retirer="' + e.rang + '" '
          + 'aria-label="' + esc(T('retirer')) + '" title="' + esc(T('retirer')) + '">'
          + '<i class="fa-solid fa-xmark"></i></button></li>';
      }).join('');
      return '<section class="acp-grp" style="--fc:' + d.c + '">'
        + '<h4 class="acp-gh"><span class="acp-gi"><i class="fa-solid ' + d.ic
        + '" aria-hidden="true"></i></span>' + esc(T('g_' + f))
        + '<b>' + paquets[f].length + '</b></h4>'
        + '<ul class="acp-liste">' + lignes + '</ul></section>';
    }).join('');
  }

  /* ── Le pied : il ne défile plus ───────────────────────────────────
     ⚠️ Il vivait DANS le corps : sur un portable, il fallait dérouler
     3191 px de liste pour atteindre « Envoyer ». */
  function rendrePied() {
    var z = document.getElementById('acp-pied-z');
    if (!z) return;
    if (!S.gestes.length) { z.innerHTML = ''; z.hidden = true; return; }
    z.hidden = false;
    // Le palier se lit AVANT le bouton : le découvrir après avoir cliqué
    // serait le découvrir trop tard.
    var bloque = !!(S.socle && !S.socle.complet);
    /* ⚠️ Le pied ne se RECONSTRUIT pas s'il est déjà là : le socle arrive en
       différé et un retrait re-rend tout — réécrire le champ ferait perdre le
       mot qu'on est en train d'écrire, et le curseur avec. Seul l'état du
       bouton change. */
    var deja = document.getElementById('acp-message');
    if (deja) {
      var b = z.querySelector('[data-envoyer]');
      if (b) {
        b.disabled = bloque;
        b.setAttribute('aria-disabled', bloque ? 'true' : 'false');
      }
      return;
    }
    /* ⚠️ Tout sur UNE ligne : le mot pour l'auteur, puis les deux boutons.
       Le libellé au-dessus d'un champ d'une ligne coûtait 30 px de la
       hauteur que la liste n'a pas — il passe en invite, et la fenêtre dit
       déjà à qui ce mot s'adresse. */
    z.innerHTML = '<div class="acp-pied">'
      + '<textarea id="acp-message" rows="1" class="acp-msg1" placeholder="'
      + esc(T('message_ph')) + '" aria-label="' + esc(T('message')) + '"></textarea>'
      + '<button type="button" class="acp-danger" data-abandonner'
      + ' title="' + esc(T('abandonner')) + '">'
      + '<i class="fa-solid fa-trash-can"></i>'
      + '<span>' + esc(T('abandonner')) + '</span></button>'
      + '<button type="button" class="acp-ok" data-envoyer'
      + (bloque ? ' disabled aria-disabled="true"' : '') + '>'
      + '<span class="ic"><i class="fa-solid fa-paper-plane"></i></span>'
      + esc(T('envoyer')) + '</button></div>';
  }

  function rendre() {
    majTitre();
    rendreSocle();
    rendreFiltres();
    rendreListe();
    rendrePied();
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

  /* ══ CE QU'ON A ÉCRIT, LÀ OÙ ON L'A ÉCRIT ═══════════════════════════
     ⚠️ Le défaut de fond du palier, relevé à l'usage : « on écrit la tâche,
     elle n'apparaît pas dans l'activité, on ne peut consulter ce que l'on a
     fait qu'en haut de page — sur 150 activités, c'est intenable ». Le geste
     est détourné vers le brouillon et n'atteint jamais la base : la fiche
     restait donc muette, et on saisissait à l'aveugle.

     Les gestes reviennent se poser DANS leur activité, marqués en attente.
     Ils ne se mêlent pas aux vraies lignes — ils n'y sont pas encore — mais
     ils sont là où on vient les relire.

     ⚠️ Un geste qui en VISE un autre (outiller une tâche en attente) se range
     SOUS lui : à plat, on ne saurait pas quel outil va sur quelle tâche. */
  function groupeParActivite() {
    var par = {};
    S.gestes.forEach(function (g, i) {
      if (!g.activity_id) return;      // le catalogue d'outils n'a pas de fiche
      var cle = String(g.activity_id);
      (par[cle] = par[cle] || []).push({ g: g, rang: i });
    });
    return par;
  }

  function carteGeste(e, enfants) {
    var bouts = String(e.g.op || '').split('.');
    var fils = (enfants || []).map(function (f) {
      return '<span class="acp-pc-chip">'
        + '<i class="fa-solid fa-wrench"></i>' + esc(f.g.objet || '—')
        + '<button type="button" class="acp-pc-chipx" data-retirer="' + f.rang + '" '
        + 'aria-label="' + esc(T('retirer')) + '" title="' + esc(T('retirer')) + '">'
        + '<i class="fa-solid fa-xmark"></i></button></span>';
    }).join('');
    // Seule une tâche AJOUTÉE s'outille : on ne propose pas d'accrocher un
    // outil à une suppression, ni à un savoir.
    var outillable = e.g.op === 'task.add';
    var d = FAM[famDe(e.g)] || FAM.donnee;
    return '<li class="acp-pc" data-rang="' + e.rang + '" style="--fc:' + d.c + '">'
      + '<span class="acp-pc-ic"><i class="fa-solid ' + d.ic + '"></i></span>'
      + '<div class="acp-pc-t">'
      + '<p class="acp-pc-v">' + esc(T('v_' + (bouts[1] || 'update'))) + ' '
      + esc(T('f_' + (bouts[0] || 'task'))) + '</p>'
      + '<p class="acp-pc-o">' + esc(e.g.objet || '—') + '</p>'
      + (fils ? '<p class="acp-pc-chips">' + fils + '</p>' : '')
      + (outillable
         ? '<button type="button" class="acp-pc-plus" data-outiller="' + e.rang + '">'
           + '<i class="fa-solid fa-wrench"></i>' + esc(T('pose_outiller')) + '</button>'
         : '')
      + '<div class="acp-pc-form" data-form="' + e.rang + '" hidden></div>'
      + '</div>'
      + '<button type="button" class="acp-pc-x" data-retirer="' + e.rang + '" '
      + 'aria-label="' + esc(T('retirer')) + '" title="' + esc(T('retirer')) + '">'
      + '<i class="fa-solid fa-xmark"></i></button></li>';
  }

  function placer() {
    // On repart de zéro : un geste retiré doit disparaître de la fiche.
    var anciens = document.querySelectorAll('[data-acp-pose]');
    Array.prototype.forEach.call(anciens, function (n) { n.remove(); });

    var par = groupeParActivite();
    Object.keys(par).forEach(function (id) {
      var hote = document.querySelector('.tasks-section-modern[data-acp-act="' + id + '"]');
      if (!hote) return;                 // la fiche n'est pas (encore) à l'écran

      var liste = par[id];
      var racines = liste.filter(function (e) { return !(e.g.vise || []).length; });
      /* ⚠️ Groupées PAR FAMILLE : les tâches avec les tâches, les
         savoir-faire avec les savoir-faire. À plat, une fiche qui porte six
         gestes de quatre natures se lisait comme un tas. Le rang réel reste
         sur chaque carte — c'est lui que `data-retirer` porte. */
      racines.sort(function (x, y) {
        var d = rangFam(famDe(x.g)) - rangFam(famDe(y.g));
        return d !== 0 ? d : x.rang - y.rang;
      });

      var fam = null;
      var html = racines.map(function (e) {
        var enfants = liste.filter(function (f) {
          return (f.g.vise || []).indexOf(e.rang) >= 0;
        });
        var f = famDe(e.g);
        var tete = '';
        if (f !== fam) {
          fam = f;
          var d = FAM[f] || FAM.donnee;
          tete = '<li class="acp-pf-h" style="--fc:' + d.c + '">'
            + '<i class="fa-solid ' + d.ic + '" aria-hidden="true"></i>'
            + esc(T('g_' + f)) + '</li>';
        }
        return tete + carteGeste(e, enfants);
      }).join('');
      // Un geste dont la cible n'est pas sur cette fiche reste visible seul :
      // mieux vaut une carte orpheline qu'un geste invisible.
      html += liste.filter(function (e) {
        return (e.g.vise || []).length
          && !racines.some(function (r) { return (e.g.vise || []).indexOf(r.rang) >= 0; });
      }).map(function (e) { return carteGeste(e, []); }).join('');

      var bloc = document.createElement('div');
      bloc.className = 'acp-pose';
      bloc.setAttribute('data-acp-pose', id);
      bloc.innerHTML = '<p class="acp-pose-h">'
        + '<i class="fa-solid fa-paper-plane"></i>' + esc(T('pose_titre'))
        + '<span class="acp-pose-n">' + liste.length + '</span></p>'
        + '<p class="acp-pose-d">' + esc(T('pose_d')) + '</p>'
        + '<ul class="acp-pose-l">' + html + '</ul>';
      var avant = hote.querySelector('.add-item-section');
      if (avant) hote.insertBefore(bloc, avant); else hote.appendChild(bloc);
    });
  }

  /* ── Outiller une tâche qui n'existe pas encore ────────────────────
     ⚠️ Le geste ne peut PAS porter l'identifiant de la tâche : elle n'en a
     pas. Il porte le RANG du geste qui la crée (`b:0`), et le rejeu le
     résout par ce qu'il vient d'écrire. Sans cela le palier — un outil par
     activité — était infranchissable sur toute activité vierge. */
  async function ouvrirOutils(rang) {
    var z = document.querySelector('[data-form="' + rang + '"]');
    if (!z) return;
    if (!z.hidden) { z.hidden = true; z.innerHTML = ''; return; }
    z.hidden = false;
    z.innerHTML = '<p class="acp-of-att">…</p>';
    var outils = [];
    try {
      var r = await window.__acpFetch('/tools/all');
      outils = (await r.json()) || [];
    } catch (_) { outils = []; }
    outils.sort(function (a, b) {
      return String(a.name || '').localeCompare(String(b.name || ''),
                                                undefined, { sensitivity: 'base' });
    });
    z.innerHTML = '<div class="acp-of">'
      + (outils.length
         ? '<div class="acp-of-l">' + outils.map(function (o) {
             return '<label class="acp-of-p"><input type="checkbox" value="' + o.id + '">'
               + '<i class="fa-solid fa-wrench"></i><span>' + esc(o.name || '') + '</span></label>';
           }).join('') + '</div>'
         : '<p class="acp-of-vide">' + esc(T('pose_aucun_outil')) + '</p>')
      + '<label class="acp-of-n"><span>' + esc(T('pose_nouv')) + '</span>'
      + '<input type="text" class="acp-of-new" placeholder="' + esc(T('pose_nouv_ph')) + '"></label>'
      + '<p class="acp-of-err" hidden></p>'
      + '<div class="acp-of-pied">'
      + '<button type="button" class="acp-of-ko" data-outils-annuler="' + rang + '">'
      + esc(T('pose_annuler')) + '</button>'
      + '<button type="button" class="acp-of-ok" data-outils-ok="' + rang + '">'
      + esc(T('pose_valider')) + '</button></div></div>';
  }

  async function validerOutils(rang) {
    var z = document.querySelector('[data-form="' + rang + '"]');
    if (!z) return;
    var ids = Array.prototype.slice
      .call(z.querySelectorAll('input[type=checkbox]'))
      .filter(function (c) { return c.checked; })
      .map(function (c) { return parseInt(c.value, 10); });
    var champ = z.querySelector('.acp-of-new');
    var noms = (champ ? champ.value : '').split(',')
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s.length; });
    if (!ids.length && !noms.length) {
      var err = z.querySelector('.acp-of-err');
      if (err) { err.hidden = false; err.textContent = T('pose_rien_choisi'); }
      return;
    }
    // ⚠️ UN seul geste : `new_tools` crée-ou-rattache par nom. Passer d'abord
    // par `/gestion_outils/api/tools` pour créer l'outil, comme le fait le
    // formulaire des tâches existantes, donnerait un second geste détourné
    // dont on ne pourrait pas lire l'identifiant.
    await window.fetch('/tools/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: 'b:' + rang,
                             existing_tool_ids: ids, new_tools: noms })
    });
    await charger();
  }

  /* ⚠️ La liste des activités arrive par lots de 20 : une fiche affichée
     plus tard n'aurait jamais reçu ses gestes. On replace à chaque fois que
     le conteneur change, une seule fois par salve. */
  var attente = null, signature = '';

  function fiches() {
    return Array.prototype.map
      .call(document.querySelectorAll('[data-acp-act]'),
            function (n) { return n.getAttribute('data-acp-act'); })
      .join(',');
  }

  function observer() {
    var hote = document.getElementById('main-activities-list');
    if (!hote || !window.MutationObserver) return;
    signature = fiches();
    new MutationObserver(function () {
      /* ⚠️⚠️ On ne replace QUE si la liste des fiches a changé. L'observateur
         surveille tout le sous-arbre, et les cartes posées y vivent : ouvrir
         le choix des outils était une mutation de plus, `placer()` repartait
         de zéro 60 ms plus tard et le formulaire disparaissait sous le
         pointeur. Mesuré au banc — la boucle se referme sur elle-même. */
      var s = fiches();
      if (s === signature) return;
      signature = s;
      clearTimeout(attente);
      attente = setTimeout(placer, 60);
    }).observe(hote, { childList: true, subtree: true });
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
    // ⚠️ Les trois zones FIXES se vident aussi : laissées en place, l'écran
    // de fin s'afficherait sous une bande de palier et au-dessus d'un bouton
    // « Envoyer » qui n'a plus rien à envoyer.
    ['acp-socle-z', 'acp-filtres', 'acp-pied-z'].forEach(function (id) {
      var n = document.getElementById(id);
      if (n) { n.innerHTML = ''; n.hidden = true; }
    });
    var z = document.getElementById('acp-corps');
    if (z) {
      z.innerHTML = '<div class="acp-fini">'
        + '<span class="acp-fini-ic"><i class="fa-solid fa-circle-check"></i></span>'
        + '<b>' + esc(T('envoye')) + '</b>'
        + '<p>' + esc(T('envoye_d')) + '</p></div>';
    }
  }

  /* Ouvrir l'activité à compléter, depuis la liste du palier : la fenêtre se
     ferme, la page défile jusqu'à sa fiche et l'ouvre. C'est ce qui fait de
     cette liste un plan de travail plutôt qu'un rapport. */
  function allerA(activityId) {
    fermer();
    var hote = document.querySelector('.tasks-section-modern[data-acp-act="'
                                      + activityId + '"]');
    var carte = hote ? hote.closest('.activity-container') : null;
    if (!carte) { signaler(T('socle_introuvable')); return; }
    var tete = carte.querySelector('.activity-header');
    // ⚠️ On n'ouvre que si la fiche est FERMÉE : un second clic la
    // refermerait juste après l'avoir montrée.
    if (tete && !hote.offsetParent) tete.click();
    carte.scrollIntoView({ block: 'center', behavior: 'smooth' });
    carte.classList.add('est-pointee');
    setTimeout(function () { carte.classList.remove('est-pointee'); }, 1600);
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
    var ou = e.target.closest ? e.target.closest('[data-outiller]') : null;
    if (ou) { ouvrirOutils(parseInt(ou.dataset.outiller, 10)); return; }
    var ok = e.target.closest ? e.target.closest('[data-outils-ok]') : null;
    if (ok) { validerOutils(parseInt(ok.dataset.outilsOk, 10)); return; }
    var ko = e.target.closest ? e.target.closest('[data-outils-annuler]') : null;
    if (ko) { ouvrirOutils(parseInt(ko.dataset.outilsAnnuler, 10)); return; }
    var pf = e.target.closest ? e.target.closest('[data-fam]') : null;
    if (pf) { S.fam = pf.dataset.fam || null; rendreFiltres(); rendreListe(); return; }
    var sv = e.target.closest ? e.target.closest('[data-socle-voir]') : null;
    if (sv) { S.socleOuvert = !S.socleOuvert; rendreSocle(); return; }
    var al = e.target.closest ? e.target.closest('[data-aller]') : null;
    if (al) { allerA(parseInt(al.dataset.aller, 10)); return; }
    var r = e.target.closest ? e.target.closest('[data-retirer]') : null;
    if (r) { retirer(parseInt(r.dataset.retirer, 10)); return; }
    if (e.target.closest && e.target.closest('[data-abandonner]')) { abandonner(); return; }
    if (e.target.closest && e.target.closest('[data-envoyer]')) { envoyer(); }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && S.ouvert) fermer();
  });

  function demarrer() { observer(); charger(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
