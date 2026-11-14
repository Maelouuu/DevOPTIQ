/* ══ LE CALENDRIER PARTAGÉ ═══════════════════════════════════════════════
   Deux sources sur une même grille : les séances d'évaluation (Compétences)
   et les créneaux des activités (Temps).

   ⚠️⚠️ Une activité N'A PAS DE DATE. Elle a un rythme. Chaque rythme se pose
   sur l'étendue qu'il occupe vraiment — le mois, la semaine, ou chaque jour
   ouvré — et jamais sur un jour choisi au hasard : un calendrier qui annonce
   « Chiffrer l'offre, mardi 17 » fabrique un rendez-vous auquel personne ne
   s'est engagé. Le serveur range donc les créneaux en trois registres
   (`creneaux.mois`, `.semaine`, `.jour`) et l'écran les pose là.          */
(function () {
  'use strict';

  var L = window.CAL_I18N || { lang: 'fr' };
  var T = function (k) { return (k in L) ? L[k] : k; };
  var $ = function (s) { return document.querySelector(s); };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;',
                 '"': '&quot;', "'": '&#39;' }[c];
      });
  }
  function nombre(x) {
    try { return Number(x).toLocaleString(L.lang === 'en' ? 'en-GB' : 'fr-FR'); }
    catch (_) { return String(x); }
  }
  /* Les heures d'un créneau. Sous l'heure on écrit des minutes — « 0.0h »
     pour 25 minutes est un mensonge, et cette page se lit en minutes. */
  function fmtH(min) {
    var m = Math.round(min || 0);
    if (m <= 0) return '0 min';
    if (m < 60) return m + ' min';
    return (Math.round(m / 6) / 10) + 'h';
  }
  function phrase(cle, vals) {
    return String(T(cle)).replace(/\{(\w+)\}/g, function (_, k) {
      return vals && (k in vals) ? vals[k] : '';
    });
  }

  var D = null;                                   // ce que le serveur rend
  var etat = {
    temps: true, comp: true,                      // les deux sources
    portee: 'tout', roleId: null, userId: null,   // les trois niveaux
    mois: null, choisie: null
  };

  /* ── Ce que la portée laisse passer ────────────────────────────────── */

  function seanceVisible(s) {
    if (!etat.comp) return false;
    if (etat.portee === 'role') return etat.roleId && s.role_id === etat.roleId;
    if (etat.portee === 'personne') return etat.userId && s.user_id === etat.userId;
    return true;
  }
  function creneauVisible(c) {
    if (!etat.temps) return false;
    if (etat.portee === 'role')
      return !!etat.roleId && (c.roles || []).indexOf(etat.roleId) >= 0;
    if (etat.portee === 'personne')
      return !!etat.userId && (c.users || []).indexOf(etat.userId) >= 0;
    return true;
  }
  function creneaux(registre) {
    return ((D && D.creneaux && D.creneaux[registre]) || []).filter(creneauVisible);
  }

  /* ── La barre : deux interrupteurs, puis trois niveaux ─────────────── */

  function rendreBarre() {
    var src = $('#cl-sources');
    src.innerHTML =
      bouton('temps', 'src_temps', 'fa-solid fa-clock')
      + bouton('comp', 'src_comp', 'fa-solid fa-chart-simple');
    src.querySelectorAll('[data-src]').forEach(function (b) {
      b.addEventListener('click', function () {
        etat[b.dataset.src] = !etat[b.dataset.src];
        rendre();
      });
    });

    var p = $('#cl-portee');
    var niveaux = [['tout', 'p_tout'], ['role', 'p_role'], ['personne', 'p_personne']];
    p.innerHTML = '<span class="cl-portee-k">' + esc(T('portee')) + '</span>'
      + '<span class="cl-seg">'
      + niveaux.map(function (n) {
          return '<button type="button" class="cl-seg-b' + (etat.portee === n[0] ? ' est-actif' : '')
            + '" data-portee="' + n[0] + '" aria-pressed="' + (etat.portee === n[0]) + '">'
            + esc(T(n[1])) + '</button>';
        }).join('')
      + '</span>'
      + listeDe();
    p.querySelectorAll('[data-portee]').forEach(function (b) {
      b.addEventListener('click', function () {
        etat.portee = b.dataset.portee;
        /* ⚠️ On choisit d'office le premier de la liste : « par rôle » sans
           rôle choisi n'afficherait RIEN, et l'écran paraîtrait cassé. */
        if (etat.portee === 'role' && !etat.roleId && (D.roles || []).length)
          etat.roleId = D.roles[0].id;
        if (etat.portee === 'personne' && !etat.userId && (D.gens || []).length)
          etat.userId = D.gens[0].id;
        rendre();
      });
    });
    var sel = p.querySelector('select');
    if (sel) sel.addEventListener('change', function () {
      var v = parseInt(sel.value, 10);
      if (etat.portee === 'role') etat.roleId = v; else etat.userId = v;
      rendre();
    });
  }

  function bouton(cle, libelle, icone) {
    return '<button type="button" class="cl-src cl-src--' + cle
      + (etat[cle] ? ' est-actif' : '') + '" data-src="' + cle
      + '" aria-pressed="' + etat[cle] + '">'
      + '<span class="cl-src-ic"><i class="' + icone + '"></i></span>'
      + esc(T(libelle)) + '<i class="cl-src-i"></i></button>';
  }

  function listeDe() {
    if (etat.portee === 'tout') return '';
    var items = etat.portee === 'role' ? (D.roles || []) : (D.gens || []);
    var choisi = etat.portee === 'role' ? etat.roleId : etat.userId;
    if (!items.length)
      return '<span class="cl-vide-sel">' + esc(T('rien')) + '</span>';
    return '<label class="cl-pick"><span class="sr">'
      + esc(T(etat.portee === 'role' ? 'ch_role' : 'ch_personne')) + '</span>'
      + '<select class="input">'
      + items.map(function (x) {
          return '<option value="' + x.id + '"' + (x.id === choisi ? ' selected' : '')
            + '>' + esc(x.nom) + '</option>';
        }).join('')
      + '</select></label>';
  }

  /* ── Le mois ───────────────────────────────────────────────────────── */

  function jourISO(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
      + '-' + String(d.getDate()).padStart(2, '0');
  }
  function dateDe(iso) {
    if (!iso) return null;
    var p = String(iso).slice(0, 10).split('-');
    return p.length === 3 ? new Date(+p[0], +p[1] - 1, +p[2]) : null;
  }
  /* ⚠️ Un « 2026-11-17 » dans une fiche n'est pas une date, c'est une clé de
     base. Et la langue vient du CATALOGUE, pas du navigateur : un écran
     anglais sur un navigateur français écrirait « mardi 17 ». */
  function jourLisible(iso) {
    var d = dateDe(iso);
    if (!d) return '';
    try {
      return d.toLocaleDateString(L.lang === 'en' ? 'en-GB' : 'fr-FR',
        { weekday: 'long', day: 'numeric', month: 'long' });
    } catch (_) { return String(iso); }
  }

  function rendreMois() {
    var z = $('#cl-mois');
    var m = etat.mois, an = m.getFullYear(), mo = m.getMonth();
    var decal = (new Date(an, mo, 1).getDay() + 6) % 7;      // la semaine part du lundi
    var nJours = new Date(an, mo + 1, 0).getDate();
    var titre = m.toLocaleDateString(L.lang === 'en' ? 'en-GB' : 'fr-FR',
                                     { month: 'long', year: 'numeric' });
    var auj = new Date(); auj.setHours(0, 0, 0, 0);

    var parJour = {};
    (D.seances || []).filter(seanceVisible).forEach(function (s) {
      var d = dateDe(s.date_prevue);
      if (d && d.getFullYear() === an && d.getMonth() === mo)
        (parJour[d.getDate()] = parJour[d.getDate()] || []).push(s);
    });

    var quotidien = creneaux('jour');
    var chargeJour = quotidien.reduce(function (s, c) { return s + c.minutes; }, 0);

    var jours = ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim'];
    var g = jours.map(function (k, i) {
      return '<span class="cl-jn' + (i > 4 ? ' est-we' : '') + '">' + esc(T(k)) + '</span>';
    }).join('');

    /* ⚠️ La bande de SEMAINE s'insère entre les rangées, sur toute la
       largeur (`grid-column: 1 / -1`) : un créneau hebdomadaire appartient à
       la semaine, pas à un de ses jours. */
    var hebdo = creneaux('semaine');
    var bandeSem = '<div class="cl-bande cl-bande--sem">'
      + '<span class="cl-bande-k">' + esc(T('bande_sem')) + '</span>'
      + (hebdo.length
         ? hebdo.map(pastille).join('')
         : '<span class="cl-bande-vide">' + esc(T('vide_sem')) + '</span>')
      + '</div>';

    var cases = '';
    for (var i = 0; i < decal; i++) cases += '<span class="cl-case cl-case--hors"></span>';
    for (var j = 1; j <= nJours; j++) {
      var dj = new Date(an, mo, j);
      var we = dj.getDay() === 0 || dj.getDay() === 6;
      var ses = parJour[j] || [];
      var iso = jourISO(dj);
      var cls = 'cl-case' + (we ? ' est-we' : '') + (+dj === +auj ? ' est-auj' : '');
      var dedans = '<span class="n">' + j + '</span>';
      if (ses.length) {
        var s = ses[0];
        var teinte = s.statut === 'tenue' ? 'tenue' : (s.en_retard ? 'retard' : 'prevue');
        cls += ' cl-case--' + teinte + (etat.choisie === s.id ? ' est-choisie' : '');
        dedans += '<span class="qui"><i class="pt"></i>' + esc(s.nom) + '</span>';
        if (ses.length > 1) dedans += '<span class="plus">+' + (ses.length - 1) + '</span>';
      }
      // ⚠️ La charge du jour ne se met QUE sur un jour ouvré : les activités
      // journalières se comptent en jours travaillés, c'est la règle de toute
      // la page Temps.
      if (!we && chargeJour > 0)
        dedans += '<span class="cl-jcharge" title="' + esc(T('charge_jour')) + '">'
          + esc(fmtH(chargeJour)) + '</span>';
      cases += ses.length
        ? '<button type="button" class="' + cls + '" data-ses="' + ses[0].id + '">' + dedans + '</button>'
        : '<div class="' + cls + '">' + dedans + '</div>';
    }

    var mensuel = creneaux('mois');

    z.innerHTML =
      '<div class="cl-mois-h">'
      + '<h3>' + esc(titre.charAt(0).toUpperCase() + titre.slice(1)) + '</h3>'
      + '<span class="sp"></span>'
      + '<button type="button" class="cl-nav" data-dm="-1" aria-label="' + esc(T('mois_prec')) + '">‹</button>'
      + '<button type="button" class="cl-nav cl-nav--auj" data-auj="1">' + esc(T('aujourdhui')) + '</button>'
      + '<button type="button" class="cl-nav" data-dm="1" aria-label="' + esc(T('mois_suiv')) + '">›</button>'
      + '</div>'
      + '<div class="cl-bande cl-bande--mois">'
      + '<span class="cl-bande-k">' + esc(T('bande_mois')) + '</span>'
      + (mensuel.length ? mensuel.map(pastille).join('')
                        : '<span class="cl-bande-vide">' + esc(T('vide_mois')) + '</span>')
      + '</div>'
      + bandeSem
      + '<div class="cl-grille">' + g + cases + '</div>'
      + '<div class="cl-leg">'
      + '<span><i class="p p--prevue"></i>' + esc(T('leg_prevue')) + '</span>'
      + '<span><i class="p p--retard"></i>' + esc(T('leg_retard')) + '</span>'
      + '<span><i class="p p--tenue"></i>' + esc(T('leg_tenue')) + '</span>'
      + '<span><i class="p p--creneau"></i>' + esc(T('leg_creneau')) + '</span>'
      + '</div>';

    z.querySelectorAll('[data-dm]').forEach(function (b) {
      b.addEventListener('click', function () {
        etat.mois = new Date(etat.mois.getFullYear(),
                             etat.mois.getMonth() + (+b.dataset.dm), 1);
        rendreMois();
      });
    });
    z.querySelector('[data-auj]').addEventListener('click', function () {
      var a = dateDe(D.aujourdhui) || new Date();
      etat.mois = new Date(a.getFullYear(), a.getMonth(), 1);
      rendreMois();
    });
    z.querySelectorAll('[data-ses]').forEach(function (b) {
      b.addEventListener('click', function () {
        etat.choisie = parseInt(b.dataset.ses, 10);
        rendreMois(); rendreCote();
      });
    });
  }

  function rythme(c) {
    var r = c.recurrence || '';
    var cle = r.indexOf('mens') === 0 ? 'r_mensuel'
            : r.indexOf('trimestr') === 0 ? 'r_trimestriel'
            : r.indexOf('ann') === 0 ? 'r_annuel'
            : r.indexOf('hebdo') === 0 ? 'bande_sem'
            : r.indexOf('jour') === 0 ? 'charge_jour' : 'r_inconnu';
    return T(cle);
  }

  function pastille(c) {
    var f = c.frequence > 1 ? ' · ' + phrase('fois', { n: c.frequence }) : '';
    return '<span class="cl-pa" title="' + esc(rythme(c) + f) + '">'
      + '<i class="cl-pa-pt"></i>'
      + '<span class="cl-pa-n">' + esc(c.activite) + '</span>'
      + '<b>' + esc(fmtH(c.minutes)) + '</b></span>';
  }

  /* ── Le côté : ce que le mois contient, et la séance choisie ───────── */

  function rendreCote() {
    var z = $('#cl-cote');
    var vues = (D.seances || []).filter(seanceVisible);
    var nC = creneaux('jour').length + creneaux('semaine').length + creneaux('mois').length;
    var s = etat.choisie
      ? vues.filter(function (x) { return x.id === etat.choisie; })[0] : null;

    z.innerHTML =
      '<div class="cl-compte">'
      + '<div class="cl-compte-i"><b>' + nombre(vues.length) + '</b><span>'
      + esc(T(vues.length === 1 ? 'n_seance' : 'n_seances')) + '</span></div>'
      + '<div class="cl-compte-i"><b>' + nombre(nC) + '</b><span>'
      + esc(T(nC === 1 ? 'n_creneau' : 'n_creneaux')) + '</span></div>'
      + '</div>'
      + (s
         ? '<div class="cl-fiche">'
           + '<div class="cl-fiche-d">' + esc(jourLisible(s.date_prevue)) + '</div>'
           + '<div class="cl-fiche-n">' + esc(s.nom) + '</div>'
           + '<div class="cl-fiche-r">' + esc(s.role) + '</div>'
           + (s.objet ? '<p class="cl-fiche-o">' + esc(s.objet) + '</p>' : '')
           + '</div>'
         : '');
  }

  function rendre() { rendreBarre(); rendreMois(); rendreCote(); }

  /* ── Arrivée : la source par défaut dépend de la PORTE ─────────────── */

  async function demarrer() {
    if (!document.getElementById('page-calendrier')) return;
    var de = new URLSearchParams(location.search).get('de');
    /* ⚠️ Entré depuis la page Temps, on ne veut voir QUE le temps ; depuis
       les Compétences, QUE les séances. Sans paramètre, les deux. */
    if (de === 'temps') { etat.temps = true; etat.comp = false; }
    else if (de === 'comp') { etat.temps = false; etat.comp = true; }

    try {
      var r = await fetch('/calendrier/api/donnees');
      D = await r.json();
    } catch (_) { D = null; }
    if (!D || !D.ok) {
      $('#cl-mois').innerHTML = '<div class="cl-err">' + esc(T('erreur')) + '</div>';
      return;
    }
    var a = dateDe(D.aujourdhui) || new Date();
    etat.mois = new Date(a.getFullYear(), a.getMonth(), 1);
    rendre();
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', demarrer);
  else demarrer();
})();
