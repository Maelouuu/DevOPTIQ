/* ══ LES LISTES DÉROULANTES DE LA PAGE TEMPS ═══════════════════════════════
   Les quatre formulaires affichaient le `<select>` du système : blanc et noir,
   avec un panneau qui s'ouvre où le navigateur veut — parfois à cheval sur le
   champ, parfois hors de la carte. On ne peut pas styler ce panneau-là : la
   seule façon de le tenir est de le dessiner.

   ⚠️ LE `<select>` RESTE, et il reste la source de vérité. Une quinzaine
   d'endroits lisent `tr.querySelector('.r-rec select').value`, écrivent
   `$('#fw-dur-unit').value = 'minutes'`, ou reconstruisent `innerHTML` : les
   reprendre un par un serait quinze occasions d'en oublier un. Il est donc
   masqué à l'œil, sorti de la tabulation, et c'est LUI qu'on écrit.

   ⚠️ Poser `.value` en JavaScript ne déclenche aucun événement, et ne
   rafraîchirait donc pas le libellé du bouton. On intercepte la propriété SUR
   L'ÉLÉMENT (jamais sur le prototype : ça vaudrait pour toute l'application)
   pour que les écritures existantes continuent de marcher telles quelles.

   ⚠️ L'accent du contrôle suit le TYPE du formulaire (rouge pour une
   faiblesse, violet pour une activité), jamais l'ambre de la page : c'est
   `--tms-a`, dérivé du `--tm-c` que pose `#tm-travail[data-analyse]`.

   ⚠️ Le panneau est posé sur le BODY en `position: fixed` : dans une cellule
   de tableau, `.table-wrap` est en `overflow-x: auto` et le découperait. Donc
   la conversion de zoom — `body.pg` porte `zoom: .8`, un enfant du body en
   `fixed` voit ses coordonnées MULTIPLIÉES par ce zoom, alors que
   `getBoundingClientRect()` les rend déjà en pixels d'écran. C'est la sixième
   fois que ce piège se présente dans cette application.                     */
(function () {
  'use strict';

  var MARQUE = 'tmsFait';
  var ouvert = null;               // { sel, bouton, panneau, actif }

  function zoomBody() {
    var z = parseFloat(getComputedStyle(document.body).zoom);
    return (isFinite(z) && z > 0) ? z : 1;
  }

  function options(sel) {
    return Array.prototype.slice.call(sel.options);
  }

  function libelle(sel) {
    var o = sel.options[sel.selectedIndex];
    return o ? o.textContent : '';
  }

  /* ── Le panneau ──────────────────────────────────────────────────────── */

  function fermer() {
    if (!ouvert) return;
    var o = ouvert;
    ouvert = null;
    o.panneau.remove();
    o.bouton.setAttribute('aria-expanded', 'false');
    o.bouton.classList.remove('est-ouvert');
  }

  function placer(o) {
    var z = zoomBody();
    var r = o.bouton.getBoundingClientRect();        // déjà en px d'écran
    var h = o.panneau.offsetHeight * z;              // idem
    var dessous = r.bottom + 6 + h <= window.innerHeight;
    o.panneau.style.minWidth = (r.width / z) + 'px';
    o.panneau.style.left = (r.left / z) + 'px';
    o.panneau.style.top = dessous ? ((r.bottom + 6) / z) + 'px'
                                  : ((r.top - 6 - h) / z) + 'px';
    o.panneau.classList.toggle('est-dessus', !dessous);
  }

  function viser(o, i) {
    var items = o.panneau.querySelectorAll('.tms-o');
    if (!items.length) return;
    o.actif = Math.max(0, Math.min(items.length - 1, i));
    Array.prototype.forEach.call(items, function (el, k) {
      el.classList.toggle('est-vise', k === o.actif);
    });
    items[o.actif].scrollIntoView({ block: 'nearest' });
  }

  function choisir(o, i) {
    var opts = options(o.sel);
    if (!opts[i] || opts[i].disabled) return;
    var avant = o.sel.value;
    o.sel.value = opts[i].value;
    fermer();
    o.bouton.focus();
    if (o.sel.value === avant) return;
    /* ⚠️ Les DEUX événements, et ils REMONTENT : un `<select>` natif émet
       `input` ET `change`, et la page écoute tantôt l'un (la table des rôles
       recalcule sur `input` posé sur le `<tr>`), tantôt l'autre (le calcul de
       la faiblesse est délégué depuis `#subtab-faiblesse`). N'en émettre
       qu'un casserait silencieusement l'autre moitié. */
    o.sel.dispatchEvent(new Event('input', { bubbles: true }));
    o.sel.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function ouvrir(sel, bouton) {
    if (ouvert && ouvert.sel === sel) { fermer(); return; }
    fermer();
    if (sel.disabled) return;

    var panneau = document.createElement('div');
    panneau.className = 'tms-p';
    panneau.setAttribute('role', 'listbox');
    panneau.innerHTML = options(sel).map(function (op, i) {
      return '<div class="tms-o' + (op.selected ? ' est-choisi' : '')
        + (op.disabled ? ' est-eteint' : '') + '" role="option" data-i="' + i
        + '" aria-selected="' + (op.selected ? 'true' : 'false') + '">'
        + '<span>' + (op.textContent || '').replace(/[&<>]/g, function (c) {
          return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c];
        }) + '</span></div>';
    }).join('');

    /* ⚠️ Le panneau est posé sur le BODY : il vit HORS de `#tm-travail` et
       n'hérite donc pas de `--tm-c`, la couleur du type de formulaire. On
       lui recopie la valeur CALCULÉE sur le bouton, qui est dedans. */
    var accent = (getComputedStyle(bouton)
                  .getPropertyValue('--tms-a') || '').trim();
    if (accent && accent.indexOf('var(') < 0)
      panneau.style.setProperty('--tms-a', accent);

    document.body.appendChild(panneau);

    var o = { sel: sel, bouton: bouton, panneau: panneau, actif: sel.selectedIndex };
    ouvert = o;
    bouton.setAttribute('aria-expanded', 'true');
    bouton.classList.add('est-ouvert');
    placer(o);
    viser(o, sel.selectedIndex);

    panneau.addEventListener('mousedown', function (e) { e.preventDefault(); });
    panneau.addEventListener('click', function (e) {
      var el = e.target.closest('.tms-o');
      if (el) choisir(o, parseInt(el.dataset.i, 10));
    });
  }

  /* ── Un select, une fois ─────────────────────────────────────────────── */

  function styliser(sel) {
    if (sel.dataset[MARQUE] || sel.multiple || sel.size > 1) return;
    sel.dataset[MARQUE] = '1';

    var enveloppe = document.createElement('span');
    enveloppe.className = 'tms';
    /* Les classes de largeur (`w-320`…) sont des PLAFONDS posés sur le
       `<select>` ; une fois masqué, elles ne tiendraient plus rien. On les
       reporte sur l'enveloppe, qui devient le contrôle visible. */
    Array.prototype.forEach.call(sel.classList, function (c) {
      if (c !== 'input') enveloppe.classList.add(c);
    });

    var bouton = document.createElement('button');
    bouton.type = 'button';
    bouton.className = 'tms-b';
    bouton.setAttribute('aria-haspopup', 'listbox');
    bouton.setAttribute('aria-expanded', 'false');
    bouton.innerHTML = '<span class="tms-v"'
      + (sel.id ? ' id="' + sel.id + '-tmsv"' : '') + '></span>'
      + '<i class="tms-c" aria-hidden="true"></i>';

    /* ⚠️ Le bouton s'annonce par SON LIBELLÉ puis sa valeur : pointer la
       seule valeur ferait lire « minutes » sans dire de quel champ. Le
       `<label for=…>` vise le `<select>`, qui n'est plus atteignable au
       clavier — on le branche donc sur le bouton, et on lui donne un id
       pour pouvoir le nommer. */
    var etiquette = sel.id
      ? document.querySelector('label[for="' + sel.id + '"]') : null;
    if (etiquette) {
      if (!etiquette.id) etiquette.id = (sel.id || 'tms') + '-tmsl';
      etiquette.addEventListener('click', function (e) {
        e.preventDefault();
        bouton.focus();
      });
    }
    if (sel.id) {
      bouton.setAttribute('aria-labelledby',
        (etiquette ? etiquette.id + ' ' : '') + sel.id + '-tmsv');
    }

    sel.parentNode.insertBefore(enveloppe, sel);
    enveloppe.appendChild(sel);
    enveloppe.appendChild(bouton);

    var valeur = bouton.querySelector('.tms-v');
    function majLibelle() { valeur.textContent = libelle(sel); }
    majLibelle();

    sel.setAttribute('tabindex', '-1');
    sel.setAttribute('aria-hidden', 'true');

    /* L'écriture directe (`sel.value = …`) doit continuer de marcher ET de
       rafraîchir le bouton. Sur l'ÉLÉMENT, jamais sur le prototype. */
    var desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    if (desc && desc.get && desc.set) {
      Object.defineProperty(sel, 'value', {
        configurable: true,
        get: function () { return desc.get.call(this); },
        set: function (v) { desc.set.call(this, v); majLibelle(); }
      });
    }
    var di = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
    if (di && di.get && di.set) {
      Object.defineProperty(sel, 'selectedIndex', {
        configurable: true,
        get: function () { return di.get.call(this); },
        set: function (v) { di.set.call(this, v); majLibelle(); }
      });
    }
    // Les options peuvent être reconstruites (`innerHTML = …`) : le libellé
    // suit, et un panneau ouvert sur l'ancienne liste se referme.
    new MutationObserver(function () {
      majLibelle();
      if (ouvert && ouvert.sel === sel) fermer();
    }).observe(sel, { childList: true, subtree: true });

    sel.addEventListener('change', majLibelle);
    bouton.addEventListener('click', function () { ouvrir(sel, bouton); });
    bouton.addEventListener('keydown', function (e) {
      var opts = options(sel);
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp'
          || e.key === 'Enter' || e.key === ' ') {
        if (!ouvert || ouvert.sel !== sel) {
          e.preventDefault();
          ouvrir(sel, bouton);
          if (e.key === 'ArrowDown') viser(ouvert, Math.min(opts.length - 1, sel.selectedIndex + 1));
          if (e.key === 'ArrowUp') viser(ouvert, Math.max(0, sel.selectedIndex - 1));
          return;
        }
        e.preventDefault();
        if (e.key === 'ArrowDown') viser(ouvert, ouvert.actif + 1);
        else if (e.key === 'ArrowUp') viser(ouvert, ouvert.actif - 1);
        else choisir(ouvert, ouvert.actif);
      } else if (e.key === 'Escape' && ouvert && ouvert.sel === sel) {
        e.preventDefault();
        fermer();
      } else if (e.key === 'Home' && ouvert && ouvert.sel === sel) {
        e.preventDefault(); viser(ouvert, 0);
      } else if (e.key === 'End' && ouvert && ouvert.sel === sel) {
        e.preventDefault(); viser(ouvert, opts.length - 1);
      } else if (e.key.length === 1) {
        // Taper une lettre saute à l'entrée qui commence par elle — c'est ce
        // que fait un `<select>` natif, et on ne le retire pas.
        var c = e.key.toLowerCase();
        for (var i = 0; i < opts.length; i++) {
          if ((opts[i].textContent || '').trim().toLowerCase().indexOf(c) === 0) {
            if (ouvert && ouvert.sel === sel) viser(ouvert, i);
            else choisir({ sel: sel, bouton: bouton, panneau: null }, i);
            break;
          }
        }
      }
    });
  }

  function balayer(racine) {
    (racine || document).querySelectorAll('#page-temps select').forEach(styliser);
  }

  /* ⚠️ Les lignes des tableaux (projet, rôle, tâches d'une faiblesse) sont
     créées APRÈS le chargement, et le sélecteur d'activité d'une faiblesse
     est cloné à la volée : un balayage unique n'en verrait aucun. */
  function demarrer() {
    if (!document.getElementById('page-temps')) return;
    balayer(document);
    new MutationObserver(function (lots) {
      lots.forEach(function (lot) {
        lot.addedNodes.forEach(function (n) {
          if (n.nodeType !== 1) return;
          if (n.tagName === 'SELECT') styliser(n);
          else if (n.querySelectorAll) n.querySelectorAll('select').forEach(styliser);
        });
      });
    }).observe(document.getElementById('page-temps'),
               { childList: true, subtree: true });

    document.addEventListener('mousedown', function (e) {
      if (!ouvert) return;
      if (e.target.closest('.tms-p') || e.target.closest('.tms')) return;
      fermer();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') fermer();
    });
    // Tout ce qui déplace ce qu'il y a dessous referme : le panneau est posé
    // sur le body, il ne suivrait pas son bouton.
    window.addEventListener('resize', fermer);
    /* ⚠️ `scroll` en CAPTURE voyait TOUS les défilements — y compris celui
       du PANNEAU, qui se refermait donc dès qu'on y défilait. Et même tout
       seul à l'ouverture d'une longue liste : `viser()` appelle
       `scrollIntoView`, qui fait défiler le panneau quand l'option choisie
       est sous le pli, et le défilement arrive une image plus tard.
       Un défilement qui naît DANS le panneau ne le referme donc pas ; tout
       autre si, car le panneau est posé sur le body et ne suivrait pas son
       bouton. ⚠️ Un événement `scroll` ne REMONTE pas : seule la phase de
       capture le voit, d'où le `true` qu'on garde. */
    window.addEventListener('scroll', function (e) {
      if (!ouvert) return;
      var c = e.target;
      if (c === ouvert.panneau) return;
      if (c && c.nodeType === 1 && c.closest && c.closest('.tms-p')) return;
      fermer();
    }, true);
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', demarrer);
  else demarrer();
})();
