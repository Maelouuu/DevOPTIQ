/* ══════════════════════════════════════════════════════════════════════════
   ATELIER — plan de travail infini : notes, listes, captures, liens, et des
   MAQUETTES de pages de l'application sur lesquelles on accroche ce qui doit
   y apparaître.

   ⚠️ **Le navigateur tient la toile.** Tout passe d'abord par IndexedDB :
   c'est instantané, ça survit à une coupure réseau et ça ne dépend d'aucun
   secret. Le serveur n'est qu'un MIROIR, poussé en différé quand il existe.
   L'ordre inverse (écrire au serveur puis afficher) rendrait chaque frappe
   dépendante d'un aller-retour — inutilisable pour un outil où l'on tape.

   ⚠️ Les captures sortent du document et vivent dans leur propre magasin.
   Inlinées, chaque enregistrement aurait repoussé plusieurs méga-octets
   d'images inchangées pour un titre corrigé.

   Trois couches, UNE caméra : le fond quadrillé (background-position), les
   liens (SVG, coordonnées du monde) et les pièces (DOM, pour rester
   éditables au clavier). Une seule transformation les déplace toutes.
   ══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var scene = document.getElementById("at-scene");
  if (!scene) { return; }

  var monde = document.getElementById("at-monde");
  var zNoeuds = document.getElementById("at-noeuds");
  var zLiens = document.getElementById("at-liens-g");
  var fond = document.getElementById("at-fond");
  var lasso = document.getElementById("at-lasso");
  var zVide = document.getElementById("at-vide");
  var zOnglets = document.getElementById("at-toiles");
  var zEtat = document.getElementById("at-etat");
  var tEtat = document.getElementById("at-etat-txt");
  var rail = document.getElementById("at-rail");
  var railCorps = document.getElementById("at-rail-corps");
  var pop = document.getElementById("at-pop");
  var popCorps = document.getElementById("at-pop-corps");
  var mini = document.getElementById("at-mini");
  var miniSvg = document.getElementById("at-mini-svg");
  var champCherche = document.getElementById("at-cherche");
  var nCherche = document.getElementById("at-cherche-n");
  var voile = document.getElementById("at-voile");

  // ══ Vocabulaire ═════════════════════════════════════════════════════════

  var TEINTES = ["craie", "ocre", "olive", "ciel", "garance", "sienne", "lavande"];
  var TEINTE_HEX = {
    craie: "#b9ae97", ocre: "#e0a015", olive: "#588b2f", ciel: "#3d92b5",
    garance: "#b5497e", sienne: "#b4603a", lavande: "#8b6fb5"
  };

  var GENRES = [
    { cle: "entete", nom: "En-tête", n: 3 },
    { cle: "liste", nom: "Liste", n: 3 },
    { cle: "table", nom: "Tableau", n: 8 },
    { cle: "form", nom: "Formulaire", n: 3 },
    { cle: "graphe", nom: "Graphique", n: 4 },
    { cle: "panneau", nom: "Panneau", n: 2 },
    { cle: "pied", nom: "Pied de page", n: 2 }
  ];

  var GABARIT = {
    note: { w: 260, h: 180, titre: "", teinte: "ocre" },
    liste: { w: 280, h: 230, titre: "", teinte: "olive" },
    image: { w: 320, h: 260, titre: "", teinte: "ciel" },
    lien: { w: 260, h: 130, titre: "", teinte: "lavande" },
    maquette: { w: 400, h: 420, titre: "", teinte: "garance" },
    cadre: { w: 560, h: 400, titre: "Groupe", teinte: "sienne" }
  };

  var ICONES = {
    note: "i-note", liste: "i-coche-liste", image: "i-image",
    lien: "i-lien-nd", maquette: "i-maquette", cadre: "i-cadre"
  };

  var MIN_W = 150, MIN_H = 90, PAS_GRILLE = 24;
  var ZOOM_MIN = 0.2, ZOOM_MAX = 2.6;

  // ══ Petits outils ═══════════════════════════════════════════════════════

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;",
               '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function uid(p) {
    return (p || "n") + Date.now().toString(36)
         + Math.random().toString(36).slice(2, 7);
  }

  function borne(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }
  function copie(o) { return JSON.parse(JSON.stringify(o)); }

  function differe(fn, ms) {
    var t = null;
    return function () {
      var args = arguments, moi = this;
      if (t) { clearTimeout(t); }
      t = setTimeout(function () { t = null; fn.apply(moi, args); }, ms);
    };
  }

  /* Empreinte courte et stable d'une chaîne (FNV-1a). Sert d'identifiant de
     capture : deux collages de la MÊME image ne doivent donner qu'une pièce,
     sinon le miroir regrossit à chaque copier-coller. */
  function empreinte(s) {
    var h = 0x811c9dc5, i;
    for (i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = (h + (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24)) >>> 0;
    }
    return h.toString(36);
  }

  // ══ Magasin local — IndexedDB ═══════════════════════════════════════════
  // ⚠️ IndexedDB et pas localStorage : une capture réduite pèse 150 Ko, et
  // localStorage plafonne autour de 5 Mo pour TOUT le domaine. Une dizaine de
  // captures auraient suffi à faire échouer silencieusement un enregistrement.

  var BASE = "optiq-atelier", bdd = null;

  function ouvrirBase() {
    return new Promise(function (ok, ko) {
      if (bdd) { return ok(bdd); }
      if (!window.indexedDB) { return ko(new Error("IndexedDB indisponible")); }
      var req = indexedDB.open(BASE, 1);
      req.onupgradeneeded = function () {
        var d = req.result;
        if (!d.objectStoreNames.contains("doc")) { d.createObjectStore("doc"); }
        if (!d.objectStoreNames.contains("pieces")) {
          d.createObjectStore("pieces", { keyPath: "id" });
        }
      };
      req.onsuccess = function () { bdd = req.result; ok(bdd); };
      req.onerror = function () { ko(req.error); };
    });
  }

  function dbLire(magasin, cle) {
    return ouvrirBase().then(function (d) {
      return new Promise(function (ok, ko) {
        var r = d.transaction(magasin, "readonly").objectStore(magasin).get(cle);
        r.onsuccess = function () { ok(r.result || null); };
        r.onerror = function () { ko(r.error); };
      });
    });
  }

  function dbEcrire(magasin, valeur, cle) {
    return ouvrirBase().then(function (d) {
      return new Promise(function (ok, ko) {
        var tx = d.transaction(magasin, "readwrite");
        var r = cle === undefined ? tx.objectStore(magasin).put(valeur)
                                  : tx.objectStore(magasin).put(valeur, cle);
        r.onsuccess = function () { ok(true); };
        r.onerror = function () { ko(r.error); };
      });
    });
  }

  function dbToutesPieces() {
    return ouvrirBase().then(function (d) {
      return new Promise(function (ok) {
        var r = d.transaction("pieces", "readonly").objectStore("pieces").getAll();
        r.onsuccess = function () { ok(r.result || []); };
        r.onerror = function () { ok([]); };
      });
    });
  }

  // ══ Miroir serveur ══════════════════════════════════════════════════════

  var miroir = { actif: false, rev: 0, erreur: null };
  var CLE_TOILE = "principale";

  function jsonGet(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    });
  }

  function jsonEnvoi(url, corps, methode) {
    return fetch(url, {
      method: methode || "PUT", credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps)
    }).then(function (r) {
      return r.json().then(function (j) { j._code = r.status; return j; });
    });
  }

  // ══ État ════════════════════════════════════════════════════════════════

  var etat = null;          // { v, toiles:[…], active }
  var revLocale = 0;        // dernière révision connue du miroir
  var sale = false;         // des changements n'ont pas encore été poussés
  var pieces = {};          // id → data-URL, en mémoire pour l'affichage

  function toile() {
    var i;
    for (i = 0; i < etat.toiles.length; i++) {
      if (etat.toiles[i].id === etat.active) { return etat.toiles[i]; }
    }
    return etat.toiles[0];
  }

  function noeuds() { return toile().noeuds; }
  function liens() { return toile().liens; }

  function noeud(id) {
    var l = noeuds(), i;
    for (i = 0; i < l.length; i++) { if (l[i].id === id) { return l[i]; } }
    return null;
  }

  function toileNeuve(nom) {
    return { id: uid("t"), nom: nom || "Toile", cam: { x: 0, y: 0, k: 1 },
             noeuds: [], liens: [] };
  }

  function neuf(type, x, y) {
    var g = GABARIT[type] || GABARIT.note;
    var n = { id: uid(), type: type, x: Math.round(x), y: Math.round(y),
              w: g.w, h: g.h, teinte: g.teinte, titre: g.titre };
    if (type === "note") { n.texte = ""; n.page = null; }
    if (type === "liste") { n.items = [nouvelItem()]; }
    if (type === "image") { n.piece = null; n.legende = ""; n.page = null; }
    if (type === "lien") { n.url = ""; }
    if (type === "maquette") {
      n.chemin = "/";
      n.sections = [
        { id: uid("s"), nom: "En-tête", genre: "entete", quoi: "" },
        { id: uid("s"), nom: "Contenu", genre: "liste", quoi: "" },
        { id: uid("s"), nom: "Actions", genre: "panneau", quoi: "" }
      ];
    }
    return n;
  }

  function nouvelItem(txt) {
    return { id: uid("i"), fait: false, texte: txt || "", page: null };
  }

  // ══ Historique ══════════════════════════════════════════════════════════
  // Instantanés de la TOILE ACTIVE seulement : annuler ne doit jamais faire
  // revenir une autre toile dans un état qu'on n'a pas vu à l'écran.

  var histo = [], futur = [], MAX_HISTO = 70, premierCoup = false;

  function avant() {
    var t = toile();
    histo.push({ id: t.id, noeuds: copie(t.noeuds), liens: copie(t.liens) });
    if (histo.length > MAX_HISTO) { histo.shift(); }
    futur.length = 0;
    majBoutonsHisto();
  }

  function restaurer(pile, autre) {
    if (!pile.length) { return; }
    var pas = pile.pop(), t = null, i;
    for (i = 0; i < etat.toiles.length; i++) {
      if (etat.toiles[i].id === pas.id) { t = etat.toiles[i]; }
    }
    if (!t) { majBoutonsHisto(); return; }
    etat.active = t.id;
    autre.push({ id: t.id, noeuds: copie(t.noeuds), liens: copie(t.liens) });
    t.noeuds = pas.noeuds;
    t.liens = pas.liens;
    sel.clear(); selLien = null;
    majOnglets();
    rendre(true);
    marquer();
    majBoutonsHisto();
  }

  function majBoutonsHisto() {
    document.getElementById("at-annuler").disabled = !histo.length;
    document.getElementById("at-refaire").disabled = !futur.length;
  }

  // ══ Caméra ══════════════════════════════════════════════════════════════

  var cam = { x: 0, y: 0, k: 1 };

  function appliquerCam() {
    monde.style.transform = "translate(" + cam.x + "px," + cam.y + "px) scale("
                          + cam.k + ")";
    var p = PAS_GRILLE * cam.k;
    fond.style.backgroundSize = p + "px " + p + "px";
    fond.style.backgroundPosition = (cam.x % p) + "px " + (cam.y % p) + "px";
    document.getElementById("at-zoom-val").textContent =
      Math.round(cam.k * 100) + " %";
    dessinerMini();
    camSauve();
  }

  var camSauve = differe(function () {
    if (!etat) { return; }
    toile().cam = { x: cam.x, y: cam.y, k: cam.k };
    sauverLocal();
  }, 500);

  function versMonde(cx, cy) {
    var r = scene.getBoundingClientRect();
    return { x: (cx - r.left - cam.x) / cam.k, y: (cy - r.top - cam.y) / cam.k };
  }

  function zoomer(k, cx, cy) {
    var r = scene.getBoundingClientRect();
    var ax = cx === undefined ? r.width / 2 : cx - r.left;
    var ay = cy === undefined ? r.height / 2 : cy - r.top;
    var nk = borne(k, ZOOM_MIN, ZOOM_MAX);
    cam.x = ax - (ax - cam.x) * (nk / cam.k);
    cam.y = ay - (ay - cam.y) * (nk / cam.k);
    cam.k = nk;
    appliquerCam();
  }

  function boite(liste) {
    if (!liste.length) { return null; }
    var x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity, i, n;
    for (i = 0; i < liste.length; i++) {
      n = liste[i];
      if (n.x < x1) { x1 = n.x; }
      if (n.y < y1) { y1 = n.y; }
      if (n.x + n.w > x2) { x2 = n.x + n.w; }
      if (n.y + n.h > y2) { y2 = n.y + n.h; }
    }
    return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
  }

  function cadrer(b, marge, kMax) {
    if (!b) { return; }
    var r = scene.getBoundingClientRect();
    marge = marge === undefined ? 90 : marge;
    var k = borne(Math.min((r.width - marge * 2) / Math.max(b.w, 1),
                           (r.height - marge * 2) / Math.max(b.h, 1)),
                  ZOOM_MIN, kMax || 1.25);
    voler(r.width / 2 - (b.x + b.w / 2) * k,
          r.height / 2 - (b.y + b.h / 2) * k, k);
  }

  var volEnCours = null;

  function voler(x, y, k) {
    if (volEnCours) { cancelAnimationFrame(volEnCours); }
    var d0 = { x: cam.x, y: cam.y, k: cam.k }, t0 = performance.now(), duree = 380;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      cam.x = x; cam.y = y; cam.k = k; appliquerCam(); return;
    }
    (function pas(t) {
      var p = borne((t - t0) / duree, 0, 1);
      var e = 1 - Math.pow(1 - p, 3);
      cam.x = d0.x + (x - d0.x) * e;
      cam.y = d0.y + (y - d0.y) * e;
      cam.k = d0.k + (k - d0.k) * e;
      appliquerCam();
      if (p < 1) { volEnCours = requestAnimationFrame(pas); }
      else { volEnCours = null; }
    })(t0);
  }

  // ══ Sélection ═══════════════════════════════════════════════════════════
  //
  // ⚠️ `sel` est un Set : on en sort un tableau avec `Array.from`, JAMAIS avec
  // `[].slice.call()`. `slice` veut un objet qui a une `length` — un Set n'en
  // a pas, il a une `size` — et il rend donc un tableau VIDE, sans erreur.
  // Supprimer, déplacer et dupliquer ne touchaient rien tout en se croyant
  // exécutés : `sel.size` disait 7, la liste passée en argument était vide.

  var sel = new Set(), selLien = null, zMax = 10;

  function choisir(ids, ajouter) {
    if (!ajouter) { sel.clear(); }
    (ids || []).forEach(function (i) { sel.add(i); });
    selLien = null;
    peindreSelection();
  }

  function peindreSelection() {
    zNoeuds.querySelectorAll(".at-noeud").forEach(function (e) {
      e.classList.toggle("choisi", sel.has(e.dataset.id));
    });
    zLiens.querySelectorAll(".at-lien-g").forEach(function (g) {
      g.classList.toggle("choisi", g.dataset.id === selLien);
    });
  }

  // ══ Rendu ═══════════════════════════════════════════════════════════════

  var vues = {};   // id → élément

  function sig(n) {
    // Tout sauf la géométrie : déplacer une pièce ne doit pas reconstruire
    // son contenu (on perdrait le curseur dans un champ en cours d'édition).
    var c = {};
    Object.keys(n).forEach(function (k) {
      if (k !== "x" && k !== "y" && k !== "w" && k !== "h") { c[k] = n[k]; }
    });
    var s = JSON.stringify(c);
    // ⚠️ Une maquette affiche ce que les AUTRES pièces lui accrochent. Sans
    // ce complément, sa signature ne bougeait pas quand on rattachait une
    // note ailleurs : le badge apparaissait sur la note, et la section
    // restait vide — on croyait le rattachement perdu.
    if (n.type === "maquette") {
      s += "|" + (n.sections || []).map(function (x) {
        return attaches(n.id, x.id).map(function (a) {
          return a.texte + (a.fait ? "✓" : "");
        }).join(",");
      }).join(";");
    }
    return s;
  }

  function placer(el, n) {
    el.style.left = n.x + "px";
    el.style.top = n.y + "px";
    el.style.width = n.w + "px";
    el.style.height = n.h + "px";
  }

  function rendre(complet) {
    var vus = {}, l = noeuds(), i, n, el;
    for (i = 0; i < l.length; i++) {
      n = l[i];
      vus[n.id] = true;
      el = vues[n.id];
      if (!el) {
        el = document.createElement("article");
        el.className = "at-noeud";
        el.dataset.id = n.id;
        zNoeuds.appendChild(el);
        vues[n.id] = el;
        el.dataset.sig = "";
      }
      placer(el, n);
      el.className = "at-noeud t-" + n.type + " at-teinte-"
                   + (n.teinte || "craie")
                   + (sel.has(n.id) ? " choisi" : "");
      if (complet || el.dataset.sig !== sig(n)) { peupler(el, n); }
    }
    Object.keys(vues).forEach(function (id) {
      if (!vus[id]) { vues[id].remove(); delete vues[id]; }
    });
    dessinerLiens();
    majVide();
    majRail();
    dessinerMini();
    if (motCherche) { appliquerRecherche(); }
  }

  function resig(el, n) { el.dataset.sig = sig(n); }

  function majVide() {
    zVide.hidden = noeuds().length > 0;
  }

  // ── Le corps d'une pièce ────────────────────────────────────────────────

  function peupler(el, n) {
    var h = tete(n);
    if (n.type === "note") { h += corpsNote(n); }
    else if (n.type === "liste") { h += corpsListe(n); }
    else if (n.type === "image") { h += corpsImage(n); }
    else if (n.type === "lien") { h += corpsLien(n); }
    else if (n.type === "maquette") { h += corpsMaquette(n); }
    else if (n.type === "cadre") { h += '<div class="at-corps"></div>'; }
    if (n.type !== "cadre") {
      h += '<span class="at-prise" data-prise="1" title="Tirer un lien"></span>';
    }
    h += '<span class="at-poignee" data-taille="1"></span>';
    el.innerHTML = h;
    // Les lignes de liste sont des textarea d'une ligne : elles doivent
    // s'ouvrir à la hauteur de leur contenu, sinon un texte long est coupé.
    el.querySelectorAll("[data-item-txt],[data-sec-quoi]").forEach(autoHauteur);
    resig(el, n);
  }

  function tete(n) {
    var compte = "";
    if (n.type === "liste" && n.items && n.items.length) {
      compte = '<span class="at-compte">'
             + n.items.filter(function (i) { return i.fait; }).length
             + "/" + n.items.length + "</span>";
    }
    return '<header class="at-tete" data-poignee="1">'
      + '<svg class="at-tete-ic" viewBox="0 0 24 24"><use href="#'
      + ICONES[n.type] + '"></use></svg>'
      + '<input class="at-titre" data-champ="titre" value="' + esc(n.titre)
      + '" placeholder="' + esc(placeholderTitre(n)) + '" spellcheck="false">'
      + compte
      + '<span class="at-tete-btns">'
      + '<button class="at-mini-btn" data-teinte="1" title="Teinte">'
      + '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"/></svg></button>'
      + '<button class="at-mini-btn sup" data-sup="1" title="Supprimer">'
      + '<svg viewBox="0 0 24 24"><path d="M5 7h14M9.5 7V5h5v2M7 7l1 13h8l1-13"/>'
      + "</svg></button></span></header>";
  }

  function placeholderTitre(n) {
    return { note: "Note", liste: "Liste", image: "Capture", lien: "Lien",
             maquette: "Nom de la page", cadre: "Groupe" }[n.type] || "Titre";
  }

  // ── Note ────────────────────────────────────────────────────────────────

  function corpsNote(n) {
    return '<div class="at-corps">'
      + '<div class="at-rendu" data-editer="1">' + rendreTexte(n.texte) + "</div>"
      + badges(n.page, true)
      + "</div>";
  }

  /* Markdown de poche : titres, listes, gras, italique, code, traits, liens.
     Volontairement minuscule — une note doit s'écrire au kilomètre, pas se
     mettre en page. On échappe AVANT de poser le moindre balisage. */
  function rendreTexte(txt) {
    if (!txt || !txt.trim()) {
      return '<span class="at-vide-txt">Cliquez pour écrire…</span>';
    }
    var lignes = esc(txt).split(/\r?\n/), out = [], liste = false, i, l;

    function enligne(s) {
      return s
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
        .replace(/(https?:\/\/[^\s<]+)/g,
                 '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    }

    for (i = 0; i < lignes.length; i++) {
      l = lignes[i];
      if (/^\s*[-*]\s+/.test(l)) {
        if (!liste) { out.push("<ul>"); liste = true; }
        out.push("<li>" + enligne(l.replace(/^\s*[-*]\s+/, "")) + "</li>");
        continue;
      }
      if (liste) { out.push("</ul>"); liste = false; }
      if (/^\s*#{1,4}\s+/.test(l)) {
        out.push("<h4>" + enligne(l.replace(/^\s*#{1,4}\s+/, "")) + "</h4>");
      } else if (/^\s*---+\s*$/.test(l)) {
        out.push("<hr>");
      } else if (l.trim()) {
        out.push("<p>" + enligne(l) + "</p>");
      }
    }
    if (liste) { out.push("</ul>"); }
    return out.join("");
  }

  // ── Liste ───────────────────────────────────────────────────────────────

  function corpsListe(n) {
    var items = n.items || [], faits = 0, out = "", i, it;
    for (i = 0; i < items.length; i++) { if (items[i].fait) { faits++; } }
    out += '<div class="at-corps">';
    out += '<div class="at-jauge"><i style="width:'
         + (items.length ? Math.round((faits / items.length) * 100) : 0)
         + '%"></i></div>';
    out += '<ul class="at-items">';
    for (i = 0; i < items.length; i++) {
      it = items[i];
      out += '<li class="at-item' + (it.fait ? " faite" : "")
           + '" data-item="' + esc(it.id) + '">'
           + '<input class="at-case" type="checkbox" data-coche="1"'
           + (it.fait ? " checked" : "") + ">"
           + '<span class="at-item-corps">'
           + '<textarea class="at-item-txt" rows="1" data-item-txt="1"'
           + ' placeholder="Une ligne…">' + esc(it.texte) + "</textarea>"
           + badges(it.page, true)
           + "</span>"
           + '<button class="at-mini-btn sup at-item-sup" data-item-sup="1"'
           + ' title="Retirer">×</button></li>';
    }
    out += "</ul>";
    out += '<button class="at-ajout" data-item-plus="1">+ une ligne</button>';
    return out + "</div>";
  }

  // ── Capture ─────────────────────────────────────────────────────────────

  function corpsImage(n) {
    var dedans;
    if (n.piece && pieces[n.piece]) {
      dedans = '<img src="' + esc(pieces[n.piece]) + '" alt="' + esc(n.titre) + '">';
    } else if (n.piece) {
      dedans = '<span class="at-image-vide">Chargement…</span>';
    } else {
      dedans = '<span class="at-image-vide" data-choisir-image="1">'
        + '<svg viewBox="0 0 24 24"><use href="#i-image"></use></svg>'
        + "Collez une capture (Ctrl+V)<br>ou cliquez pour choisir un fichier"
        + "</span>";
    }
    return '<div class="at-image">' + dedans + "</div>"
      + '<input class="at-legende" data-champ="legende" value="'
      + esc(n.legende) + '" placeholder="légende…">'
      + '<div class="at-badges-pied">' + badges(n.page, true) + "</div>";
  }

  // ── Lien ────────────────────────────────────────────────────────────────

  function corpsLien(n) {
    var sur = /^https?:\/\//i.test(n.url || "");
    return '<div class="at-corps at-lien-corps">'
      + '<input class="at-url" data-champ="url" value="' + esc(n.url)
      + '" placeholder="https://…" spellcheck="false">'
      + (sur ? '<a class="at-ouvrir" href="' + esc(n.url)
             + '" target="_blank" rel="noopener noreferrer">Ouvrir →</a>'
             : "")
      + "</div>";
  }

  // ── Maquette de page ────────────────────────────────────────────────────

  function corpsMaquette(n) {
    var out = '<div class="at-mq-chrome">'
      + '<span class="at-mq-pastilles"><i></i><i></i><i></i></span>'
      + '<input class="at-mq-url" data-champ="chemin" value="' + esc(n.chemin)
      + '" placeholder="/chemin/de/la/page" spellcheck="false"></div>'
      + '<div class="at-corps"><div class="at-sections">';
    var secs = n.sections || [], i;
    for (i = 0; i < secs.length; i++) { out += uneSection(n, secs[i]); }
    out += "</div>"
      + '<button class="at-ajout at-sec-ajout" data-sec-plus="1">'
      + "+ une section</button></div>";
    return out;
  }

  function uneSection(n, s) {
    var g = genre(s.genre), i, traits = "", att = attaches(n.id, s.id);
    for (i = 0; i < g.n; i++) { traits += "<span></span>"; }

    var opts = GENRES.map(function (x) {
      return '<option value="' + x.cle + '"' + (x.cle === s.genre ? " selected" : "")
           + ">" + esc(x.nom) + "</option>";
    }).join("");

    var puces = "";
    if (att.length) {
      puces = '<div class="at-accroches">' + att.map(function (a) {
        return '<button class="at-accroche' + (a.fait ? " faite" : "")
             + '" data-aller-accroche="' + esc(a.noeud) + '" title="'
             + esc(a.texte) + '"><span>' + esc(a.texte) + "</span></button>";
      }).join("") + "</div>";
    }

    /* ⚠️ Le croquis est une VIGNETTE dans la tête, plus une bande sous le
       titre. En bande il pesait une trentaine de pixels de barres colorées
       PAR section — plus lourd que le nom, bien plus lourd que le texte :
       dix sections faisaient un mur de barres qu'on ne lisait pas. Il porte
       en prime le choix du genre (le <select> est posé dessus, transparent)
       au lieu d'un mot répété à droite de chaque titre : un seul objet, qui
       se lit d'un coup d'œil et qui se clique. */
    return '<div class="at-sec" data-sec="' + esc(s.id) + '">'
      + '<div class="at-sec-tete">'
      + '<span class="at-sec-grip" data-sec-grip="1" title="Glisser pour réordonner"></span>'
      + '<label class="at-genre" title="' + esc(g.nom) + ' — changer le genre">'
      + '<span class="at-croquis g-' + esc(s.genre) + '">' + traits + "</span>"
      + '<select class="at-sec-genre" data-sec-genre="1"'
      + ' aria-label="Genre de la section">' + opts + "</select></label>"
      + '<input class="at-sec-nom" data-sec-nom="1" value="' + esc(s.nom)
      + '" placeholder="Section">'
      + (att.length ? '<span class="at-sec-n" title="' + att.length
         + ' pièce(s) rattachée(s)">' + att.length + "</span>" : "")
      + '<button class="at-mini-btn sup at-sec-sup" data-sec-sup="1"'
      + ' title="Retirer la section">×</button>'
      + "</div>"
      // Ce que la section PORTE dans l'app : c'est le texte qu'on vient
      // lire, donc c'est lui qui a la taille et l'encre, pas le croquis.
      + '<div class="at-sec-corps">'
      + '<textarea class="at-sec-quoi" rows="1" data-sec-quoi="1"'
      + ' placeholder="ce que cette section porte…">' + esc(s.quoi || "")
      + "</textarea>"
      + puces
      + "</div></div>";
  }

  function genre(cle) {
    var i;
    for (i = 0; i < GENRES.length; i++) {
      if (GENRES[i].cle === cle) { return GENRES[i]; }
    }
    return GENRES[1];
  }

  /* Ce qui est accroché à une section : les notes et les lignes de liste qui
     portent son badge. C'est le sens même de la maquette — voir d'un coup
     d'œil tout ce qui doit apparaître à cet endroit de la page. */
  function attaches(idPage, idSec) {
    var out = [], l = noeuds(), i, j, n;
    for (i = 0; i < l.length; i++) {
      n = l[i];
      if (n.page && n.page.n === idPage && n.page.s === idSec) {
        out.push({ noeud: n.id, texte: n.titre || resume(n.texte) || "Note",
                   fait: false });
      }
      if (n.items) {
        for (j = 0; j < n.items.length; j++) {
          if (n.items[j].page && n.items[j].page.n === idPage
              && n.items[j].page.s === idSec) {
            out.push({ noeud: n.id, texte: n.items[j].texte || "(ligne vide)",
                       fait: !!n.items[j].fait });
          }
        }
      }
    }
    return out;
  }

  function resume(t) {
    return (t || "").replace(/[#*`>-]/g, " ").trim().split(/\s+/)
           .slice(0, 7).join(" ");
  }

  // ── Badges ──────────────────────────────────────────────────────────────

  function badges(page, avecPlus) {
    var out = '<div class="at-badges">';
    if (page) {
      var p = noeud(page.n), s = null, i;
      if (p && p.sections) {
        for (i = 0; i < p.sections.length; i++) {
          if (p.sections[i].id === page.s) { s = p.sections[i]; }
        }
      }
      if (p) {
        out += '<button class="at-badge" data-badge="1" style="--b:'
          + (TEINTE_HEX[p.teinte] || "#b5497e") + '" title="Aller à la section">'
          + "<i></i><b>" + esc(p.titre || "Page") + "</b>"
          + (s ? "<em>· " + esc(s.nom) + "</em>" : "") + "</button>";
      } else {
        out += '<button class="at-badge" data-badge="1" style="--b:#a8a091"'
          + ' title="La maquette n\'existe plus"><i></i><b>page supprimée</b>'
          + "</button>";
      }
    }
    if (avecPlus) {
      out += '<button class="at-badge-plus" data-badge-plus="1">'
           + (page ? "changer" : "⊕ page") + "</button>";
    }
    return out + "</div>";
  }

  // ── Liens entre pièces ──────────────────────────────────────────────────

  function ancre(n, vx, vy) {
    var cx = n.x + n.w / 2, cy = n.y + n.h / 2;
    var dx = vx - cx, dy = vy - cy;
    if (!dx && !dy) { return { x: cx, y: cy }; }
    var hw = n.w / 2, hh = n.h / 2;
    var t = Math.min(hw / Math.abs(dx || 1e-6), hh / Math.abs(dy || 1e-6));
    return { x: cx + dx * t, y: cy + dy * t };
  }

  function dessinerLiens() {
    var l = liens(), out = "", i, a, b, p1, p2, dx, mx;
    for (i = 0; i < l.length; i++) {
      a = noeud(l[i].de); b = noeud(l[i].vers);
      if (!a || !b) { continue; }
      p1 = ancre(a, b.x + b.w / 2, b.y + b.h / 2);
      p2 = ancre(b, a.x + a.w / 2, a.y + a.h / 2);
      dx = Math.max(40, Math.abs(p2.x - p1.x) * 0.45);
      var d = "M" + p1.x + "," + p1.y + " C" + (p1.x + dx) + "," + p1.y
            + " " + (p2.x - dx) + "," + p2.y + " " + p2.x + "," + p2.y;
      mx = (p1.x + p2.x) / 2;
      out += '<g class="at-lien-g' + (selLien === l[i].id ? " choisi" : "")
           + '" data-id="' + esc(l[i].id) + '">'
           + '<path class="at-lien-prise" d="' + d + '"></path>'
           + '<path class="at-lien-trait" d="' + d + '"></path>'
           + (l[i].texte ? '<text class="at-lien-etiq" x="' + mx + '" y="'
                         + ((p1.y + p2.y) / 2 - 7) + '">' + esc(l[i].texte)
                         + "</text>" : "")
           + "</g>";
    }
    zLiens.innerHTML = out;
  }

  // ── Mini-carte ──────────────────────────────────────────────────────────

  var miniB = null;

  function dessinerMini() {
    if (!etat) { return; }
    var l = noeuds();
    var r = scene.getBoundingClientRect();
    var vue = { x: -cam.x / cam.k, y: -cam.y / cam.k,
                w: r.width / cam.k, h: r.height / cam.k };
    var b = boite(l) || { x: vue.x, y: vue.y, w: vue.w, h: vue.h };
    // La vue fait partie du cadrage : sinon, en s'éloignant des pièces, on
    // ne verrait plus où l'on est.
    var x1 = Math.min(b.x, vue.x), y1 = Math.min(b.y, vue.y);
    var x2 = Math.max(b.x + b.w, vue.x + vue.w);
    var y2 = Math.max(b.y + b.h, vue.y + vue.h);
    var m = Math.max((x2 - x1), (y2 - y1)) * 0.06 + 20;
    x1 -= m; y1 -= m; x2 += m; y2 += m;
    miniB = { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
    var sx = 160 / miniB.w, sy = 110 / miniB.h, s = Math.min(sx, sy);
    var ox = (160 - miniB.w * s) / 2, oy = (110 - miniB.h * s) / 2;
    miniB.s = s; miniB.ox = ox; miniB.oy = oy;

    var out = "", i, n;
    for (i = 0; i < l.length; i++) {
      n = l[i];
      out += '<rect class="mc-n" x="' + (ox + (n.x - x1) * s).toFixed(1)
           + '" y="' + (oy + (n.y - y1) * s).toFixed(1)
           + '" width="' + Math.max(1.5, n.w * s).toFixed(1)
           + '" height="' + Math.max(1.5, n.h * s).toFixed(1) + '" rx="1"/>';
    }
    out += '<rect class="mc-vue" x="' + (ox + (vue.x - x1) * s).toFixed(1)
         + '" y="' + (oy + (vue.y - y1) * s).toFixed(1)
         + '" width="' + Math.max(2, vue.w * s).toFixed(1)
         + '" height="' + Math.max(2, vue.h * s).toFixed(1) + '" rx="1.5"/>';
    miniSvg.innerHTML = out;
  }

  mini.addEventListener("pointerdown", function (ev) {
    if (!miniB) { return; }
    var r = mini.getBoundingClientRect();
    var px = (ev.clientX - r.left) * (160 / r.width);
    var py = (ev.clientY - r.top) * (110 / r.height);
    var wx = miniB.x + (px - miniB.ox) / miniB.s;
    var wy = miniB.y + (py - miniB.oy) / miniB.s;
    var s = scene.getBoundingClientRect();
    voler(s.width / 2 - wx * cam.k, s.height / 2 - wy * cam.k, cam.k);
  });

  // ══ Rail : les pages et leurs sections ══════════════════════════════════

  function majRail() {
    if (rail.hidden) { return; }
    var pages = noeuds().filter(function (n) { return n.type === "maquette"; });
    if (!pages.length) {
      railCorps.innerHTML = '<p class="at-rail-vide">Aucune maquette sur cette '
        + "toile. Posez-en une (touche <b>P</b>) pour commencer à placer les "
        + "fonctionnalités dans les pages.</p>";
      return;
    }
    railCorps.innerHTML = pages.map(function (p) {
      var secs = (p.sections || []).map(function (s) {
        var n = attaches(p.id, s.id).length;
        return '<li><button class="at-rp-sec" data-rp="' + esc(p.id)
          + '" data-rp-sec="' + esc(s.id) + '">'
          + "<span>" + esc(s.nom) + "</span>"
          + "<em>" + (n || "") + "</em></button></li>";
      }).join("");
      return '<div class="at-rp at-teinte-' + esc(p.teinte || "garance") + '">'
        + '<button class="at-rp-tete" data-rp="' + esc(p.id) + '">'
        + "<b>" + esc(p.titre || "Page sans nom") + "</b>"
        + "<em>" + esc(p.chemin || "") + "</em></button>"
        + '<ul class="at-rp-secs">' + secs + "</ul></div>";
    }).join("");
  }

  railCorps.addEventListener("click", function (ev) {
    var bSec = ev.target.closest("[data-rp-sec]");
    var bPage = ev.target.closest(".at-rp-tete");
    if (bSec) {
      // Avec une sélection : on rattache. Sans : on va voir.
      var cibles = Array.from(sel).map(noeud).filter(function (n) {
        return n && (n.type === "note" || n.type === "image");
      });
      if (cibles.length) {
        avant();
        cibles.forEach(function (n) {
          n.page = { n: bSec.dataset.rp, s: bSec.dataset.rpSec };
        });
        rendre();
        marquer();
        return;
      }
      allerSection(bSec.dataset.rp, bSec.dataset.rpSec);
      return;
    }
    if (bPage) { allerNoeud(bPage.dataset.rp); }
  });

  document.getElementById("at-rail-bascule").addEventListener("click", function () {
    var ouvert = rail.hidden;
    rail.hidden = !ouvert;
    this.setAttribute("aria-pressed", ouvert ? "true" : "false");
    if (ouvert) { majRail(); }
    dessinerMini();
  });
  document.getElementById("at-rail-fermer").addEventListener("click", function () {
    rail.hidden = true;
    document.getElementById("at-rail-bascule").setAttribute("aria-pressed", "false");
  });

  function allerNoeud(id) {
    var n = noeud(id);
    if (!n) { return; }
    choisir([id]);
    cadrer({ x: n.x, y: n.y, w: n.w, h: n.h }, 120, 1.1);
  }

  function allerSection(idPage, idSec) {
    allerNoeud(idPage);
    setTimeout(function () {
      var el = vues[idPage];
      if (!el) { return; }
      var s = el.querySelector('[data-sec="' + idSec + '"]');
      if (!s) { return; }
      s.classList.add("brille");
      s.scrollIntoView({ block: "nearest" });
      setTimeout(function () { s.classList.remove("brille"); }, 1600);
    }, 420);
  }

  // ══ Choix d'une page/section ════════════════════════════════════════════

  var popCible = null;   // { noeud, item | null }
  var popMode = "badge"; // "badge" (rattacher) | "modeles" (poser des pièces)

  function ouvrirPop(ancreEl, cible) {
    popMode = "badge";
    popCible = cible;
    pop.querySelector(".at-pop-tete").textContent = "Rattacher à…";
    var pages = noeuds().filter(function (n) { return n.type === "maquette"; });
    var courant = cible.item
      ? (ligneItem(cible) || {}).page
      : (noeud(cible.noeud) || {}).page;

    if (!pages.length) {
      popCorps.innerHTML = '<p class="at-pop-vide">Il n\'y a pas encore de '
        + "maquette de page sur cette toile.<br>Posez-en une avec la touche "
        + "<b>P</b>, puis revenez accrocher cette ligne dessus.</p>";
    } else {
      popCorps.innerHTML = pages.map(function (p) {
        return '<div class="at-pop-p at-teinte-' + esc(p.teinte || "garance")
          + '"><i></i>' + esc(p.titre || "Page sans nom") + "</div>"
          + (p.sections || []).map(function (s) {
            var actif = courant && courant.n === p.id && courant.s === s.id;
            var n = attaches(p.id, s.id).length;
            return '<button class="at-pop-s' + (actif ? " actif" : "")
              + '" data-pp="' + esc(p.id) + '" data-ps="' + esc(s.id) + '">'
              + esc(s.nom) + (n ? "<em>" + n + "</em>" : "") + "</button>";
          }).join("");
      }).join("")
      + (courant ? '<button class="at-pop-rien" data-pp-rien="1">'
                 + "Retirer le rattachement</button>" : "");
    }

    pop.hidden = false;
    placerPop(ancreEl);
  }

  function placerPop(ancreEl) {
    // L'ancre peut avoir déjà disparu (un blur a reconstruit la pièce avant
    // que le clic n'arrive) : on retombe alors sur la position du pointeur.
    var r = ancreEl.getBoundingClientRect();
    if (!r.width && !r.height) {
      r = { left: souris.x, right: souris.x, top: souris.y, bottom: souris.y };
    }
    var x = borne(r.left, 8, window.innerWidth - pop.offsetWidth - 8);
    var y = r.bottom + 6;
    if (y + pop.offsetHeight > window.innerHeight - 8) {
      y = Math.max(8, r.top - pop.offsetHeight - 6);
    }
    pop.style.left = x + "px";
    pop.style.top = y + "px";
  }

  function fermerPop() { pop.hidden = true; popCible = null; popMode = "badge"; }

  function ligneItem(cible) {
    var n = noeud(cible.noeud), i;
    if (!n || !n.items) { return null; }
    for (i = 0; i < n.items.length; i++) {
      if (n.items[i].id === cible.item) { return n.items[i]; }
    }
    return null;
  }

  popCorps.addEventListener("click", function (ev) {
    if (popMode === "modeles") {
      var m = ev.target.closest("[data-modele]");
      if (m) { fermerPop(); insererModele(m.dataset.modele); }
      return;
    }
    var b = ev.target.closest("[data-pp]"), rien = ev.target.closest("[data-pp-rien]");
    if (!popCible || (!b && !rien)) { return; }
    avant();
    var valeur = rien ? null : { n: b.dataset.pp, s: b.dataset.ps };
    if (popCible.item) {
      var it = ligneItem(popCible);
      if (it) { it.page = valeur; }
    } else {
      var n = noeud(popCible.noeud);
      if (n) { n.page = valeur; }
    }
    fermerPop();
    rendre();
    marquer();
  });

  document.addEventListener("pointerdown", function (ev) {
    if (pop.hidden) { return; }
    if (!pop.contains(ev.target) && !ev.target.closest("[data-badge-plus]")
        && ev.target.closest("#at-modeles") === null) {
      fermerPop();
    }
  }, true);

  // ══ Modèles — des pièces prêtes à poser ═════════════════════════════════
  // Le plan de l'application et la liste des chantiers vivent dans le dépôt
  // (hub/atelier_modeles.py) : on les POSE sur la toile, on ne les importe
  // pas. L'import remplace tout ; ici, on ajoute, et Ctrl+Z retire.

  function ouvrirPopModeles(ancreEl) {
    popMode = "modeles";
    popCible = null;
    pop.querySelector(".at-pop-tete").textContent = "Poser un modèle…";
    popCorps.innerHTML = '<p class="at-pop-vide">Chargement…</p>';
    pop.hidden = false;
    placerPop(ancreEl);
    jsonGet("/api/atelier/modeles").then(function (liste) {
      popCorps.innerHTML = liste.map(function (m) {
        return '<button class="at-pop-mod" data-modele="' + esc(m.cle) + '">'
          + "<b>" + esc(m.titre) + "</b><span>" + esc(m.quoi) + "</span></button>";
      }).join("")
      + '<p class="at-pop-note">Les pièces se posent à droite de ce qui est '
      + "déjà là, et restent sélectionnées — <b>Ctrl+Z</b> les retire d'un "
      + "coup.</p>";
      placerPop(ancreEl);
    }).catch(function (e) {
      popCorps.innerHTML = '<p class="at-pop-vide">Modèles indisponibles : '
        + esc(e.message) + "</p>";
    });
  }

  /* Un rattachement de modèle se lit de deux façons : par identifiant local
     (les pièces du modèle entre elles) ou par NOM (une liste de chantiers qui
     vise des maquettes déjà posées, peut-être il y a trois jours). */
  function trouverPageParNom(nomPage, nomSection) {
    // ⚠️ On parcourt TOUTES les maquettes homonymes. S'arrêter à la première
    // qui porte le bon titre laissait un chantier sans badge dès qu'une vieille
    // maquette du même nom traînait sur la toile sans la bonne section.
    var l = noeuds(), i, j, p;
    for (i = 0; i < l.length; i++) {
      p = l[i];
      if (p.type !== "maquette" || (p.titre || "") !== nomPage) { continue; }
      for (j = 0; j < (p.sections || []).length; j++) {
        if (p.sections[j].nom === nomSection) {
          return { n: p.id, s: p.sections[j].id };
        }
      }
    }
    return null;
  }

  function resoudrePage(page, ref, carte) {
    if (page && carte[page.n] && carte[page.s]) {
      return { n: carte[page.n], s: carte[page.s] };
    }
    if (ref) { return trouverPageParNom(ref.page, ref.section); }
    return page || null;
  }

  function insererModele(cle) {
    etatVisuel("cours", "…", "Pose du modèle");
    jsonGet("/api/atelier/modele/" + encodeURIComponent(cle))
      .then(function (m) {
        if (!m || !m.noeuds || !m.noeuds.length) { return; }
        avant();
        // À droite de tout ce qui existe : on n'empile jamais un modèle sur
        // le travail en cours.
        var ici = boite(noeuds()), la = boite(m.noeuds);
        var dx = ici ? (ici.x + ici.w + 140) - la.x : 0;
        var dy = ici ? ici.y - la.y : 0;

        var carte = {};
        var neufs = m.noeuds.map(function (src) {
          var c = copie(src);
          carte[src.id] = c.id = uid();
          (c.sections || []).forEach(function (s) {
            var v = uid("s"); carte[s.id] = v; s.id = v;
          });
          (c.items || []).forEach(function (it) { it.id = uid("i"); });
          c.x = Math.round(c.x + dx);
          c.y = Math.round(c.y + dy);
          return c;
        });

        // Poser AVANT de résoudre : une ligne de chantier peut viser une page
        // du même modèle, qui n'existe qu'une fois sur la toile.
        var liste = noeuds();
        neufs.forEach(function (c) { liste.push(c); });
        neufs.forEach(function (c) {
          c.page = resoudrePage(c.page, c.page_ref, carte);
          delete c.page_ref;
          (c.items || []).forEach(function (it) {
            it.page = resoudrePage(it.page, it.page_ref, carte);
            delete it.page_ref;
          });
        });
        (m.liens || []).forEach(function (l) {
          if (carte[l.de] && carte[l.vers]) {
            liens().push({ id: uid("l"), de: carte[l.de], vers: carte[l.vers],
                           texte: l.texte || "" });
          }
        });

        choisir(neufs.map(function (c) { return c.id; }));
        rendre();
        marquer();
        cadrer(boite(neufs), 70, 0.9);
      })
      .catch(function (e) {
        etatVisuel("mal", "modèle KO", e.message);
      });
  }

  document.getElementById("at-modeles").addEventListener("click", function () {
    if (!pop.hidden && popMode === "modeles") { fermerPop(); return; }
    ouvrirPopModeles(this);
  });

  // ══ Enregistrement ══════════════════════════════════════════════════════

  function etatVisuel(classe, texte, titre) {
    zEtat.className = "at-etat " + classe;
    tEtat.textContent = texte;
    zEtat.title = titre || "";
  }

  var sauverLocal = differe(function () {
    if (!etat) { return; }
    dbEcrire("doc", { doc: etat, rev: revLocale, sale: sale }, "courant")
      .catch(function (e) {
        etatVisuel("mal", "local KO", "IndexedDB : " + e.message);
      });
  }, 350);

  function marquer() {
    sale = true;
    etatVisuel("cours", "…", "Enregistrement en cours");
    sauverLocal();
    pousser();
  }

  var pousser = differe(function () {
    if (!etat) { return; }
    if (!miroir.actif) {
      sale = false;
      sauverLocal();
      etatVisuel("local", "local", "Enregistré dans ce navigateur. "
        + "Aucun miroir : posez HUB_ATELIER_DB pour garder la toile côté serveur.");
      return;
    }
    envoyerPieces().then(function () {
      return jsonEnvoi("/api/atelier/toile/" + CLE_TOILE,
                       { contenu: JSON.stringify(etat), rev: revLocale });
    }).then(function (j) {
      if (j._code === 409) {
        etatVisuel("mal", "conflit",
          "Une version plus récente est enregistrée côté serveur — "
          + "rechargez la page pour la reprendre.");
        return;
      }
      if (j.ok) {
        revLocale = j.rev;
        sale = false;
        sauverLocal();
        etatVisuel("ok", "enregistré", "Toile et miroir à jour.");
      } else {
        etatVisuel("mal", "miroir KO", j.erreur || "le miroir a refusé l'écriture");
      }
    }).catch(function (e) {
      // La toile locale est intacte : on le dit, et on ne perd rien.
      etatVisuel("mal", "hors ligne",
        "Enregistré dans ce navigateur, pas encore dans le miroir ("
        + e.message + ").");
    });
  }, 1800);

  /* Les captures ne sont envoyées qu'UNE fois. On demande d'abord au miroir
     ce qu'il a déjà : sans ça, chaque enregistrement repousserait toutes les
     images de la toile. */
  var piecesEnvoyees = {};

  function envoyerPieces() {
    var utiles = {}, l, i, j, t;
    for (t = 0; t < etat.toiles.length; t++) {
      l = etat.toiles[t].noeuds;
      for (i = 0; i < l.length; i++) {
        if (l[i].piece) { utiles[l[i].piece] = true; }
      }
    }
    var ids = Object.keys(utiles).filter(function (id) {
      return !piecesEnvoyees[id];
    });
    if (!ids.length) { return Promise.resolve(); }
    return jsonEnvoi("/api/atelier/pieces", { ids: ids }, "POST")
      .then(function (j) {
        (j.connues || []).forEach(function (id) { piecesEnvoyees[id] = true; });
        var reste = ids.filter(function (id) { return !piecesEnvoyees[id]; });
        return Promise.all(reste.map(function (id) {
          if (!pieces[id]) { return Promise.resolve(); }
          var mime = (pieces[id].match(/^data:([^;]+);/) || [])[1] || "image/png";
          return jsonEnvoi("/api/atelier/piece/" + id,
                           { mime: mime, donnees: pieces[id] })
            .then(function (r) { if (r.ok) { piecesEnvoyees[id] = true; } });
        }));
      });
  }

  // ══ Captures ════════════════════════════════════════════════════════════
  // On réduit AVANT de ranger : une capture d'écran brute pèse 1 à 4 Mo, et
  // personne ne lit une note de 60 Mo. 1600 px de large suffisent largement
  // pour relire une erreur ou un écran.

  var LARGEUR_MAX = 1600, QUALITE = 0.86;

  function reduireImage(blob) {
    return new Promise(function (ok, ko) {
      var url = URL.createObjectURL(blob), img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        var ech = Math.min(1, LARGEUR_MAX / Math.max(img.width, img.height));
        if (ech >= 1 && blob.size < 320 * 1024) {
          var fr = new FileReader();
          fr.onload = function () { ok(fr.result); };
          fr.onerror = function () { ko(fr.error); };
          fr.readAsDataURL(blob);
          return;
        }
        var c = document.createElement("canvas");
        c.width = Math.round(img.width * ech);
        c.height = Math.round(img.height * ech);
        var ctx = c.getContext("2d");
        ctx.drawImage(img, 0, 0, c.width, c.height);
        var d = c.toDataURL("image/webp", QUALITE);
        // Safari ancien ne sait pas écrire du WebP : il rend du PNG, souvent
        // plus lourd que l'original. On garde alors le JPEG.
        if (d.indexOf("data:image/webp") !== 0) {
          d = c.toDataURL("image/jpeg", QUALITE);
        }
        ok(d);
      };
      img.onerror = function () { URL.revokeObjectURL(url); ko(new Error("image illisible")); };
      img.src = url;
    });
  }

  function rangerPiece(dataUrl) {
    var id = "p" + dataUrl.length.toString(36) + "_" + empreinte(dataUrl);
    pieces[id] = dataUrl;
    var mime = (dataUrl.match(/^data:([^;]+);/) || [])[1] || "image/png";
    dbEcrire("pieces", { id: id, mime: mime, donnees: dataUrl });
    return id;
  }

  function poserImage(blob, x, y) {
    return reduireImage(blob).then(function (d) {
      var id = rangerPiece(d);
      avant();
      var n = neuf("image", x, y);
      n.piece = id;
      // On cadre la pièce sur les proportions de l'image : une capture
      // écrasée dans un carré ne se relit pas.
      return new Promise(function (ok) {
        var img = new Image();
        img.onload = function () {
          var r = img.width / img.height;
          n.w = borne(Math.round(Math.sqrt(300 * 300 * r)), 180, 620);
          n.h = Math.round(n.w / r) + 96;     // estimation, corrigée ci-dessous
          noeuds().push(n);
          choisir([n.id]);
          rendre();
          // ⚠️ La hauteur de l'en-tête, de la légende et de la ligne de badge
          // dépend de la police chargée : une constante tombait toujours à
          // côté, et chaque capture large s'affichait tassée entre deux
          // bandes vides. On MESURE la pièce rendue, une fois, et on ajuste.
          var el = vues[n.id];
          var zone = el && el.querySelector(".at-image");
          if (zone && zone.clientHeight > 0) {
            n.h = Math.round(n.w / r) + (n.h - zone.clientHeight);
            placer(el, n);
          }
          marquer();
          ok(n);
        };
        img.onerror = function () {
          noeuds().push(n); rendre(); marquer(); ok(n);
        };
        img.src = d;
      });
    }).catch(function (e) {
      etatVisuel("mal", "image KO", e.message);
    });
  }

  function chargerPieceManquante(id) {
    if (pieces[id]) { return Promise.resolve(); }
    return dbLire("pieces", id).then(function (p) {
      if (p && p.donnees) { pieces[id] = p.donnees; return true; }
      if (!miroir.actif) { return false; }
      return jsonGet("/api/atelier/piece/" + id).then(function (j) {
        if (j && j.donnees) {
          pieces[id] = j.donnees;
          dbEcrire("pieces", { id: id, mime: j.mime, donnees: j.donnees });
          piecesEnvoyees[id] = true;
          return true;
        }
        return false;
      }).catch(function () { return false; });
    });
  }

  function chargerPieces() {
    var besoins = {}, t, l, i;
    for (t = 0; t < etat.toiles.length; t++) {
      l = etat.toiles[t].noeuds;
      for (i = 0; i < l.length; i++) {
        if (l[i].piece && !pieces[l[i].piece]) { besoins[l[i].piece] = true; }
      }
    }
    var ids = Object.keys(besoins);
    if (!ids.length) { return Promise.resolve(); }
    return Promise.all(ids.map(chargerPieceManquante)).then(function () {
      rendre(true);
    });
  }

  // ══ Poser une pièce ═════════════════════════════════════════════════════

  var arme = null, souris = { x: 0, y: 0 };

  function poser(type, x, y) {
    avant();
    var n = neuf(type, x - GABARIT[type].w / 2, y - 24);
    noeuds().push(n);
    choisir([n.id]);
    rendre();
    marquer();
    // Le titre est le premier geste attendu : on y met le curseur TOUT DE
    // SUITE. ⚠️ Pas de `setTimeout` : qui double-clique enchaîne sur la
    // frappe, et les premières lettres partaient dans le vide avant d'être
    // effacées par le `select()` différé.
    var el = vues[n.id];
    if (el) {
      var c = el.querySelector(".at-titre");
      if (c) { c.focus(); c.select(); }
    }
    return n;
  }

  document.querySelectorAll("[data-poser]").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = b.dataset.poser;
      if (arme === t) { arme = null; } else { arme = t; }
      document.querySelectorAll("[data-poser]").forEach(function (o) {
        o.classList.toggle("arme", o.dataset.poser === arme);
      });
      scene.classList.toggle("relie", !!arme);
    });
  });

  // ══ Gestes sur la scène ═════════════════════════════════════════════════

  var geste = null;   // {mode, …}
  var espace = false;

  scene.addEventListener("pointerdown", function (ev) {
    if (ev.button === 2) { return; }
    // L'établi et la mini-carte vivent DANS la scène : sans cette garde, un
    // clic sur un bouton d'outil ouvrirait aussi un lasso derrière lui.
    if (ev.target.closest(".at-etabli") || ev.target.closest(".at-mini")) {
      return;
    }
    scene.focus({ preventScroll: true });

    var surPrise = ev.target.closest("[data-prise]");
    var surTaille = ev.target.closest("[data-taille]");
    var surTete = ev.target.closest("[data-poignee]");
    var surGrip = ev.target.closest("[data-sec-grip]");
    var carte = ev.target.closest(".at-noeud");
    var lienG = ev.target.closest(".at-lien-g");

    // Déplacer la toile : espace, clic milieu, ou fond nu avec Alt.
    if (espace || ev.button === 1 || (!carte && ev.altKey)) {
      geste = { mode: "cam", x0: ev.clientX, y0: ev.clientY,
                cx: cam.x, cy: cam.y };
      scene.classList.add("tire-en-cours");
      scene.setPointerCapture(ev.pointerId);
      ev.preventDefault();
      return;
    }

    if (surGrip && carte) {
      demarrerGlisserSection(ev, carte, surGrip);
      return;
    }

    if (surPrise && carte) {
      geste = { mode: "lien", de: carte.dataset.id };
      scene.setPointerCapture(ev.pointerId);
      ev.preventDefault();
      return;
    }

    if (surTaille && carte) {
      var n0 = noeud(carte.dataset.id);
      avant();
      geste = { mode: "taille", id: n0.id, x0: ev.clientX, y0: ev.clientY,
                w0: n0.w, h0: n0.h };
      scene.setPointerCapture(ev.pointerId);
      ev.preventDefault();
      return;
    }

    if (surTete && carte) {
      // ⚠️ Le titre et les boutons VIVENT dans la poignée. Sans cette sortie,
      // le `preventDefault` du glisser empêchait purement et simplement de
      // cliquer dans le champ du titre.
      //
      // ⚠️ Mais le titre OCCUPE la poignée : l'en exclure ne laissait, pour
      // attraper la carte, que la bande de quelques pixels autour de l'icône.
      // Le glisser est donc DIFFÉRÉ : on ne saisit rien tant que le pointeur
      // n'a pas bougé de 4 px. En deçà, c'est un clic — le champ prend le
      // curseur. Au-delà, on lâche le champ et la carte suit. Un clic n'ouvre
      // donc aucune entrée d'historique, et on peut tirer une pièce par son
      // titre comme dans n'importe quelle fenêtre.
      if (ev.target.closest("button")) { return; }
      var id = carte.dataset.id;
      if (ev.shiftKey) { sel.add(id); }
      else if (!sel.has(id)) { sel.clear(); sel.add(id); }
      selLien = null;
      peindreSelection();
      monter(carte);
      geste = { mode: "deplacer", x0: ev.clientX, y0: ev.clientY,
                carte: carte, differe: true, pris: [] };
      // Hors champ de saisie, on coupe la sélection de texte tout de suite ;
      // sur le champ, surtout pas — il doit pouvoir prendre le curseur.
      if (!dansUnChamp(ev.target)) { ev.preventDefault(); }
      return;
    }

    if (lienG) {
      selLien = lienG.dataset.id;
      sel.clear();
      peindreSelection();
      return;
    }

    if (carte) { return; }   // clic dans le corps d'une pièce : à elle de voir

    // Fond nu
    if (arme) {
      var p = versMonde(ev.clientX, ev.clientY);
      poser(arme, p.x, p.y);
      arme = null;
      document.querySelectorAll("[data-poser]").forEach(function (o) {
        o.classList.remove("arme");
      });
      scene.classList.remove("relie");
      return;
    }

    // ⚠️ Glisser le fond DÉPLACE LA TOILE. C'est le geste qu'on fait cent
    // fois par séance sur un plan sans bord ; l'imposer avec Espace ou le
    // clic du milieu, c'est le rendre inaccessible à qui ne lit pas l'aide.
    // La sélection au lasso reste là, sous Maj — le même modificateur que le
    // clic qui ajoute une pièce à la sélection.
    if (ev.shiftKey) {
      geste = { mode: "lasso", x0: ev.clientX, y0: ev.clientY, ajout: true };
      scene.setPointerCapture(ev.pointerId);
      return;
    }
    geste = { mode: "cam", x0: ev.clientX, y0: ev.clientY,
              cx: cam.x, cy: cam.y, surFond: true };
    scene.classList.add("tire-en-cours");
    scene.setPointerCapture(ev.pointerId);
  });

  /* Le glisser commence pour de bon : c'est ICI qu'on prend l'instantané
     d'historique et qu'on fige les positions de départ. Le faire au
     `pointerdown` empilait une entrée d'annulation à chaque simple clic. */
  function demarrerDeplacement(ev) {
    geste.differe = false;
    if (document.activeElement && document.activeElement.blur) {
      document.activeElement.blur();
    }
    scene.focus({ preventScroll: true });
    try { scene.setPointerCapture(ev.pointerId); } catch (e) { /* synthétique */ }
    avant();
    var pris = Array.from(sel).map(noeud).filter(Boolean);
    // Un cadre emporte ce qu'il contient : c'est tout son intérêt.
    pris = pris.concat(contenusDesCadres(pris));
    if (!pris.length) { return false; }
    geste.pris = pris.map(function (n) { return { n: n, x: n.x, y: n.y }; });
    geste.pris.forEach(function (p) {
      if (vues[p.n.id]) { vues[p.n.id].classList.add("glisse"); }
    });
    return true;
  }

  function contenusDesCadres(pris) {
    var out = [], ids = {};
    pris.forEach(function (n) { ids[n.id] = true; });
    pris.filter(function (n) { return n.type === "cadre"; }).forEach(function (c) {
      noeuds().forEach(function (n) {
        if (ids[n.id] || n.id === c.id) { return; }
        if (n.x >= c.x && n.y >= c.y && n.x + n.w <= c.x + c.w
            && n.y + n.h <= c.y + c.h) {
          ids[n.id] = true;
          out.push(n);
        }
      });
    });
    return out;
  }

  function monter(el) { el.style.zIndex = ++zMax; }

  scene.addEventListener("pointermove", function (ev) {
    souris.x = ev.clientX; souris.y = ev.clientY;
    if (!geste) { return; }

    if (geste.mode === "cam") {
      cam.x = geste.cx + (ev.clientX - geste.x0);
      cam.y = geste.cy + (ev.clientY - geste.y0);
      appliquerCam();
      return;
    }

    if (geste.mode === "deplacer") {
      if (geste.differe) {
        if (Math.abs(ev.clientX - geste.x0) < 4
            && Math.abs(ev.clientY - geste.y0) < 4) { return; }
        if (!demarrerDeplacement(ev)) { geste = null; return; }
      }
      var dx = (ev.clientX - geste.x0) / cam.k;
      var dy = (ev.clientY - geste.y0) / cam.k;
      if (!ev.altKey) {
        dx = Math.round(dx / (PAS_GRILLE / 2)) * (PAS_GRILLE / 2);
        dy = Math.round(dy / (PAS_GRILLE / 2)) * (PAS_GRILLE / 2);
      }
      geste.pris.forEach(function (p) {
        p.n.x = Math.round(p.x + dx);
        p.n.y = Math.round(p.y + dy);
        if (vues[p.n.id]) { placer(vues[p.n.id], p.n); }
      });
      dessinerLiens();
      viserSection(ev);
      return;
    }

    if (geste.mode === "taille") {
      var n = noeud(geste.id);
      if (!n) { return; }
      n.w = Math.max(MIN_W, Math.round(geste.w0 + (ev.clientX - geste.x0) / cam.k));
      n.h = Math.max(MIN_H, Math.round(geste.h0 + (ev.clientY - geste.y0) / cam.k));
      placer(vues[n.id], n);
      dessinerLiens();
      return;
    }

    if (geste.mode === "lasso") {
      var r = scene.getBoundingClientRect();
      var x1 = Math.min(geste.x0, ev.clientX) - r.left;
      var y1 = Math.min(geste.y0, ev.clientY) - r.top;
      var w = Math.abs(ev.clientX - geste.x0), h = Math.abs(ev.clientY - geste.y0);
      lasso.hidden = false;
      lasso.style.left = x1 + "px"; lasso.style.top = y1 + "px";
      lasso.style.width = w + "px"; lasso.style.height = h + "px";
      return;
    }

    if (geste.mode === "lien") {
      var a = noeud(geste.de);
      if (!a) { return; }
      var p = versMonde(ev.clientX, ev.clientY);
      var q = ancre(a, p.x, p.y);
      var f = zLiens.querySelector(".at-lien-fantome");
      if (!f) {
        f = document.createElementNS("http://www.w3.org/2000/svg", "path");
        f.setAttribute("class", "at-lien-fantome");
        zLiens.appendChild(f);
      }
      f.setAttribute("d", "M" + q.x + "," + q.y + " L" + p.x + "," + p.y);
      var sous = document.elementFromPoint(ev.clientX, ev.clientY);
      var c = sous && sous.closest(".at-noeud");
      zNoeuds.querySelectorAll(".at-noeud").forEach(function (e) {
        e.classList.toggle("cible", e === c && e.dataset.id !== geste.de);
      });
    }
  });

  function viserSection(ev) {
    // Lâcher une note sur une section de maquette la rattache : c'est le
    // geste naturel pour « cette fonctionnalité va là ».
    var pris = geste.pris.map(function (p) { return p.n; });
    var rattachables = pris.filter(function (n) {
      return n.type === "note" || n.type === "image";
    });
    document.querySelectorAll(".at-sec.vise").forEach(function (s) {
      s.classList.remove("vise");
    });
    geste.secVisee = null;
    if (rattachables.length !== 1 || pris.length !== 1) { return; }
    pris.forEach(function (n) {
      if (vues[n.id]) { vues[n.id].style.pointerEvents = "none"; }
    });
    var sous = document.elementFromPoint(ev.clientX, ev.clientY);
    pris.forEach(function (n) {
      if (vues[n.id]) { vues[n.id].style.pointerEvents = ""; }
    });
    var secEl = sous && sous.closest(".at-sec");
    var carte = sous && sous.closest(".at-noeud");
    if (!secEl || !carte || carte.dataset.id === rattachables[0].id) { return; }
    secEl.classList.add("vise");
    geste.secVisee = { n: carte.dataset.id, s: secEl.dataset.sec,
                       quoi: rattachables[0].id };
  }

  scene.addEventListener("pointerup", function (ev) {
    scene.classList.remove("tire-en-cours");
    if (!geste) { return; }
    var g = geste;
    geste = null;

    // Un clic sur le fond, sans déplacement : c'est une désélection. Depuis
    // que le glisser déplace la toile, c'est le seul moyen qui reste de
    // tout désélectionner à la souris.
    if (g.mode === "cam" && g.surFond
        && Math.abs(ev.clientX - g.x0) < 4 && Math.abs(ev.clientY - g.y0) < 4) {
      choisir([]);
      return;
    }

    if (g.mode === "deplacer") {
      // Le pointeur n'a jamais bougé : c'était un clic, rien à enregistrer.
      if (g.differe) { return; }
      Object.keys(vues).forEach(function (id) {
        vues[id].classList.remove("glisse");
      });
      document.querySelectorAll(".at-sec.vise").forEach(function (s) {
        s.classList.remove("vise");
      });
      if (g.secVisee) {
        var q = noeud(g.secVisee.quoi);
        if (q) { q.page = { n: g.secVisee.n, s: g.secVisee.s }; }
        rendre();
      }
      marquer();
      dessinerMini();
      return;
    }

    if (g.mode === "taille") { rendre(); marquer(); return; }

    if (g.mode === "lasso") {
      lasso.hidden = true;
      var a = versMonde(Math.min(g.x0, ev.clientX), Math.min(g.y0, ev.clientY));
      var b = versMonde(Math.max(g.x0, ev.clientX), Math.max(g.y0, ev.clientY));
      if (Math.abs(b.x - a.x) < 4 && Math.abs(b.y - a.y) < 4) { return; }
      var dedans = noeuds().filter(function (n) {
        return n.x + n.w > a.x && n.x < b.x && n.y + n.h > a.y && n.y < b.y;
      }).map(function (n) { return n.id; });
      choisir(dedans, g.ajout);
      return;
    }

    if (g.mode === "lien") {
      var f = zLiens.querySelector(".at-lien-fantome");
      if (f) { f.remove(); }
      zNoeuds.querySelectorAll(".at-noeud").forEach(function (e) {
        e.classList.remove("cible");
      });
      var sous = document.elementFromPoint(ev.clientX, ev.clientY);
      var c = sous && sous.closest(".at-noeud");
      if (c && c.dataset.id !== g.de) {
        var existe = liens().some(function (l) {
          return (l.de === g.de && l.vers === c.dataset.id)
              || (l.de === c.dataset.id && l.vers === g.de);
        });
        if (!existe) {
          avant();
          liens().push({ id: uid("l"), de: g.de, vers: c.dataset.id, texte: "" });
          rendre();
          marquer();
        }
      }
    }
  });

  scene.addEventListener("pointercancel", function () {
    geste = null;
    lasso.hidden = true;
    scene.classList.remove("tire-en-cours");
  });

  // ── Réordonner les sections ─────────────────────────────────────────────

  function demarrerGlisserSection(ev, carte, grip) {
    var n = noeud(carte.dataset.id);
    var secEl = grip.closest(".at-sec");
    if (!n || !secEl) { return; }
    ev.preventDefault();
    ev.stopPropagation();
    var liste = [].slice.call(carte.querySelectorAll(".at-sec"));
    var depuis = liste.indexOf(secEl);
    var rects = liste.map(function (e) { return e.getBoundingClientRect(); });
    secEl.style.opacity = ".4";

    function bouge(e) {
      var k = indexSous(e.clientY);
      liste.forEach(function (el, i) { el.classList.toggle("vise", i === k && i !== depuis); });
    }

    function indexSous(y) {
      var i;
      for (i = 0; i < rects.length; i++) {
        if (y < rects[i].bottom) { return i; }
      }
      return rects.length - 1;
    }

    function fini(e) {
      document.removeEventListener("pointermove", bouge);
      document.removeEventListener("pointerup", fini);
      secEl.style.opacity = "";
      liste.forEach(function (el) { el.classList.remove("vise"); });
      var vers = indexSous(e.clientY);
      if (vers !== depuis && vers >= 0) {
        avant();
        var s = n.sections.splice(depuis, 1)[0];
        n.sections.splice(vers, 0, s);
        rendre();
        marquer();
      }
    }

    document.addEventListener("pointermove", bouge);
    document.addEventListener("pointerup", fini);
  }

  // ══ Molette ═════════════════════════════════════════════════════════════

  /* ⚠️ Le pas se NORMALISE avant d'entrer dans le zoom. Un cran de molette
     vaut 100 en PIXELS (Chrome), 3 en LIGNES (Firefox) et 1 en PAGES : avec
     un facteur brut, le même cran faisait ×0,37 d'un côté et ×0,97 de
     l'autre. La ligne compte donc 33 px, la rafale d'inertie d'un pavé
     tactile est bornée, et un cran vaut ~12 % de zoom partout. */
  function pasMolette(ev) {
    var d = ev.deltaY;
    if (ev.deltaMode === 1) { d *= 33; }
    else if (ev.deltaMode === 2) { d *= 400; }
    return borne(d, -220, 220);
  }

  scene.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    // Un balayage HORIZONTAL n'est jamais une intention de zoom.
    if (!ev.ctrlKey && !ev.metaKey
        && Math.abs(ev.deltaX) > Math.abs(ev.deltaY)) {
      cam.x -= ev.deltaX; appliquerCam(); return;
    }
    if (ev.shiftKey) { cam.y -= ev.deltaY; appliquerCam(); return; }
    zoomer(cam.k * Math.pow(0.9988, pasMolette(ev)), ev.clientX, ev.clientY);
  }, { passive: false });

  scene.addEventListener("dblclick", function (ev) {
    if (ev.target.closest(".at-noeud")) { return; }
    var p = versMonde(ev.clientX, ev.clientY);
    poser("note", p.x, p.y);
  });

  // ══ Champs et boutons dans les pièces ═══════════════════════════════════

  zNoeuds.addEventListener("focusin", function () { premierCoup = true; });

  zNoeuds.addEventListener("input", function (ev) {
    var carte = ev.target.closest(".at-noeud");
    if (!carte) { return; }
    var n = noeud(carte.dataset.id);
    if (!n) { return; }
    if (premierCoup) { avant(); premierCoup = false; }

    var champ = ev.target.dataset.champ;
    if (champ) {
      n[champ] = ev.target.value;
      if (champ === "titre" || champ === "chemin") { majRail(); }
      resig(carte, n);
      marquer();
      return;
    }
    if (ev.target.dataset.itemTxt) {
      var li = ev.target.closest(".at-item");
      var it = (n.items || []).filter(function (x) {
        return x.id === li.dataset.item;
      })[0];
      if (it) {
        it.texte = ev.target.value;
        autoHauteur(ev.target);
        resig(carte, n);
        marquer();
      }
      return;
    }
    if (ev.target.dataset.secNom || ev.target.dataset.secQuoi) {
      var sEl = ev.target.closest(".at-sec");
      var sec = (n.sections || []).filter(function (x) {
        return x.id === sEl.dataset.sec;
      })[0];
      if (sec) {
        if (ev.target.dataset.secQuoi) {
          sec.quoi = ev.target.value;
          autoHauteur(ev.target);
        } else {
          sec.nom = ev.target.value;
          majRail();
        }
        resig(carte, n);
        marquer();
      }
      return;
    }
    if (ev.target.classList.contains("at-texte")) {
      n.texte = ev.target.value;
      resig(carte, n);
      marquer();
    }
  });

  zNoeuds.addEventListener("change", function (ev) {
    var carte = ev.target.closest(".at-noeud");
    if (!carte) { return; }
    var n = noeud(carte.dataset.id);
    if (!n) { return; }
    if (ev.target.dataset.coche) {
      var li = ev.target.closest(".at-item");
      var it = (n.items || []).filter(function (x) {
        return x.id === li.dataset.item;
      })[0];
      if (it) { avant(); it.fait = ev.target.checked; rendre(); marquer(); }
      return;
    }
    if (ev.target.dataset.secGenre) {
      var sEl = ev.target.closest(".at-sec");
      var sec = (n.sections || []).filter(function (x) {
        return x.id === sEl.dataset.sec;
      })[0];
      if (sec) { avant(); sec.genre = ev.target.value; rendre(); marquer(); }
    }
  });

  function autoHauteur(ta) {
    ta.style.height = "auto";
    ta.style.height = ta.scrollHeight + "px";
  }

  zNoeuds.addEventListener("click", function (ev) {
    var carte = ev.target.closest(".at-noeud");
    if (!carte) { return; }
    var n = noeud(carte.dataset.id);
    if (!n) { return; }

    if (ev.target.closest("[data-sup]")) {
      supprimer([n.id]);
      return;
    }
    if (ev.target.closest("[data-teinte]")) {
      avant();
      n.teinte = TEINTES[(TEINTES.indexOf(n.teinte) + 1) % TEINTES.length];
      rendre();
      marquer();
      return;
    }
    if (ev.target.closest("[data-item-plus]")) {
      avant();
      n.items.push(nouvelItem());
      rendre();
      marquer();
      focusDernierItem(n);
      return;
    }
    if (ev.target.closest("[data-item-sup]")) {
      var li = ev.target.closest(".at-item");
      avant();
      n.items = n.items.filter(function (x) { return x.id !== li.dataset.item; });
      rendre();
      marquer();
      return;
    }
    if (ev.target.closest("[data-sec-plus]")) {
      avant();
      n.sections.push({ id: uid("s"), nom: "Section", genre: "liste", quoi: "" });
      rendre();
      marquer();
      return;
    }
    if (ev.target.closest("[data-sec-sup]")) {
      var sEl = ev.target.closest(".at-sec");
      avant();
      n.sections = n.sections.filter(function (x) { return x.id !== sEl.dataset.sec; });
      rendre();
      marquer();
      return;
    }
    if (ev.target.closest("[data-badge-plus]")) {
      var liB = ev.target.closest(".at-item");
      ouvrirPop(ev.target.closest("[data-badge-plus]"),
                { noeud: n.id, item: liB ? liB.dataset.item : null });
      return;
    }
    if (ev.target.closest("[data-badge]")) {
      var liC = ev.target.closest(".at-item");
      var p = liC
        ? (n.items.filter(function (x) { return x.id === liC.dataset.item; })[0] || {}).page
        : n.page;
      if (p) { allerSection(p.n, p.s); }
      return;
    }
    if (ev.target.closest("[data-aller-accroche]")) {
      allerNoeud(ev.target.closest("[data-aller-accroche]").dataset.allerAccroche);
      return;
    }
    if (ev.target.closest("[data-choisir-image]")) {
      choisirFichierImage(n);
      return;
    }
    if (ev.target.closest("[data-editer]")) {
      editerNote(carte, n);
    }
  });

  function focusDernierItem(n) {
    var el = vues[n.id];
    if (!el) { return; }
    var tas = el.querySelectorAll("[data-item-txt]");
    if (tas.length) { tas[tas.length - 1].focus(); }
  }

  /* Une note se lit en permanence et s'édite au clic : garder un textarea en
     place afficherait le balisage au lieu du texte mis en forme. */
  function editerNote(carte, n) {
    var zone = carte.querySelector(".at-corps");
    if (!zone || carte.querySelector(".at-texte")) { return; }
    var h = zone.clientHeight;
    zone.innerHTML = '<textarea class="at-texte" placeholder="Écrivez…&#10;'
      + "# titre   - liste   **gras**   `code`\"></textarea>"
      + badges(n.page, true);
    var ta = zone.querySelector(".at-texte");
    ta.value = n.texte || "";
    ta.style.minHeight = Math.max(40, h - 30) + "px";
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);
    ta.addEventListener("blur", function () {
      peupler(carte, n);
    });
  }

  function choisirFichierImage(n) {
    var f = document.createElement("input");
    f.type = "file";
    f.accept = "image/*";
    f.onchange = function () {
      if (!f.files || !f.files[0]) { return; }
      reduireImage(f.files[0]).then(function (d) {
        avant();
        n.piece = rangerPiece(d);
        rendre(true);
        marquer();
      });
    };
    f.click();
  }

  // Entrée dans une ligne de liste : on en ouvre une nouvelle en dessous.
  zNoeuds.addEventListener("keydown", function (ev) {
    if (!ev.target.dataset || !ev.target.dataset.itemTxt) { return; }
    var carte = ev.target.closest(".at-noeud");
    var n = noeud(carte.dataset.id);
    var li = ev.target.closest(".at-item");
    var i = n.items.findIndex(function (x) { return x.id === li.dataset.item; });
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      avant();
      n.items.splice(i + 1, 0, nouvelItem());
      rendre();
      marquer();
      var tas = vues[n.id].querySelectorAll("[data-item-txt]");
      if (tas[i + 1]) { tas[i + 1].focus(); }
      return;
    }
    if (ev.key === "Backspace" && !ev.target.value && n.items.length > 1) {
      ev.preventDefault();
      avant();
      n.items.splice(i, 1);
      rendre();
      marquer();
      var t2 = vues[n.id].querySelectorAll("[data-item-txt]");
      if (t2[Math.max(0, i - 1)]) {
        var c = t2[Math.max(0, i - 1)];
        c.focus();
        c.setSelectionRange(c.value.length, c.value.length);
      }
    }
  });

  // ══ Supprimer / dupliquer ═══════════════════════════════════════════════

  function supprimer(ids) {
    if (!ids.length) { return; }
    avant();
    var ens = {};
    ids.forEach(function (i) { ens[i] = true; });
    var t = toile();
    t.noeuds = t.noeuds.filter(function (n) { return !ens[n.id]; });
    t.liens = t.liens.filter(function (l) {
      return !ens[l.de] && !ens[l.vers];
    });
    // Les badges qui pointaient vers une maquette disparue sont effacés : un
    // badge « page supprimée » qu'on ne peut plus suivre n'apprend rien.
    t.noeuds.forEach(function (n) {
      if (n.page && ens[n.page.n]) { n.page = null; }
      (n.items || []).forEach(function (it) {
        if (it.page && ens[it.page.n]) { it.page = null; }
      });
    });
    sel.clear();
    rendre();
    marquer();
  }

  function dupliquer() {
    var pris = Array.from(sel).map(noeud).filter(Boolean);
    if (!pris.length) { return; }
    avant();
    var neufs = pris.map(function (n) {
      var c = copie(n);
      c.id = uid();
      c.x += 28; c.y += 28;
      if (c.items) { c.items.forEach(function (i) { i.id = uid("i"); }); }
      if (c.sections) { c.sections.forEach(function (s) { s.id = uid("s"); }); }
      noeuds().push(c);
      return c.id;
    });
    choisir(neufs);
    rendre();
    marquer();
  }

  // ══ Clavier ═════════════════════════════════════════════════════════════

  function dansUnChamp(t) {
    return t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA"
                 || t.tagName === "SELECT" || t.isContentEditable);
  }

  document.addEventListener("keydown", function (ev) {
    if (ev.key === " " && !dansUnChamp(ev.target)) {
      espace = true;
      scene.classList.add("tire");
    }

    var mod = ev.ctrlKey || ev.metaKey;

    if (ev.key === "Escape") {
      if (!pop.hidden) { fermerPop(); return; }
      if (!voile.hidden) { voile.hidden = true; return; }
      if (dansUnChamp(ev.target)) { ev.target.blur(); return; }
      choisir([]);
      return;
    }

    if (mod && ev.key.toLowerCase() === "f") {
      ev.preventDefault();
      champCherche.focus();
      champCherche.select();
      return;
    }

    if (mod && ev.key.toLowerCase() === "z" && !dansUnChamp(ev.target)) {
      ev.preventDefault();
      if (ev.shiftKey) { restaurer(futur, histo); } else { restaurer(histo, futur); }
      return;
    }
    if (mod && ev.key.toLowerCase() === "y" && !dansUnChamp(ev.target)) {
      ev.preventDefault();
      restaurer(futur, histo);
      return;
    }

    if (dansUnChamp(ev.target)) { return; }

    if (mod && ev.key.toLowerCase() === "d") {
      ev.preventDefault(); dupliquer(); return;
    }
    if (mod && ev.key.toLowerCase() === "a") {
      ev.preventDefault();
      choisir(noeuds().map(function (n) { return n.id; }));
      return;
    }
    if (ev.key === "Delete" || ev.key === "Backspace") {
      if (selLien) {
        avant();
        var t = toile();
        t.liens = t.liens.filter(function (l) { return l.id !== selLien; });
        selLien = null;
        rendre(); marquer();
        return;
      }
      if (sel.size) { ev.preventDefault(); supprimer(Array.from(sel)); }
      return;
    }

    if (ev.key === "?" || (ev.shiftKey && ev.key === "/")) {
      voile.hidden = !voile.hidden; return;
    }
    // ⚠️ `ev.code` et pas `ev.key` : sur un clavier français, Maj+1 rend
    // « 1 » et la touche non pressée rend « & ». Le code physique est le seul
    // repère commun aux dispositions.
    if (ev.shiftKey && ev.code === "Digit1") {
      ev.preventDefault(); cadrer(boite(noeuds())); return;
    }
    if (ev.shiftKey && ev.code === "Digit2") {
      ev.preventDefault();
      cadrer(boite(Array.from(sel).map(noeud).filter(Boolean)));
      return;
    }

    var raccourcis = { n: "note", l: "liste", p: "maquette", i: "image",
                       u: "lien", c: "cadre" };
    if (!mod && raccourcis[ev.key.toLowerCase()]) {
      var w = versMonde(souris.x || window.innerWidth / 2,
                        souris.y || window.innerHeight / 2);
      poser(raccourcis[ev.key.toLowerCase()], w.x, w.y);
      return;
    }

    if (ev.key.indexOf("Arrow") === 0 && sel.size) {
      ev.preventDefault();
      var pas = ev.shiftKey ? PAS_GRILLE : 2;
      var dx = (ev.key === "ArrowRight" ? pas : 0) - (ev.key === "ArrowLeft" ? pas : 0);
      var dy = (ev.key === "ArrowDown" ? pas : 0) - (ev.key === "ArrowUp" ? pas : 0);
      if (premierCoup !== "fleches") { avant(); premierCoup = "fleches"; }
      sel.forEach(function (id) {
        var n = noeud(id);
        if (n) { n.x += dx; n.y += dy; placer(vues[id], n); }
      });
      dessinerLiens();
      marquer();
    }
  });

  document.addEventListener("keyup", function (ev) {
    if (ev.key === " ") {
      espace = false;
      scene.classList.remove("tire");
    }
    if (ev.key.indexOf("Arrow") === 0) { premierCoup = true; }
  });

  // ══ Coller et déposer ═══════════════════════════════════════════════════

  document.addEventListener("paste", function (ev) {
    if (dansUnChamp(ev.target)) { return; }
    var items = (ev.clipboardData || {}).items || [], i, f;
    var p = versMonde(souris.x || window.innerWidth / 2,
                      souris.y || window.innerHeight / 2);
    for (i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image/") === 0) {
        f = items[i].getAsFile();
        if (f) { ev.preventDefault(); poserImage(f, p.x, p.y); return; }
      }
    }
    var txt = (ev.clipboardData || {}).getData
            ? ev.clipboardData.getData("text/plain") : "";
    if (txt && txt.trim()) {
      ev.preventDefault();
      avant();
      var est = /^https?:\/\/\S+$/i.test(txt.trim());
      var n = neuf(est ? "lien" : "note", p.x, p.y);
      if (est) { n.url = txt.trim(); n.titre = "Lien collé"; }
      else { n.texte = txt; }
      noeuds().push(n);
      choisir([n.id]);
      rendre();
      marquer();
    }
  });

  scene.addEventListener("dragover", function (ev) { ev.preventDefault(); });
  scene.addEventListener("drop", function (ev) {
    var fs = (ev.dataTransfer || {}).files;
    if (!fs || !fs.length) { return; }
    ev.preventDefault();
    var p = versMonde(ev.clientX, ev.clientY), i, dec = 0;
    for (i = 0; i < fs.length; i++) {
      if (fs[i].type.indexOf("image/") === 0) {
        poserImage(fs[i], p.x + dec, p.y + dec);
        dec += 30;
      }
    }
  });

  // ══ Recherche ═══════════════════════════════════════════════════════════

  var motCherche = "", trouves = [], iTrouve = -1;

  function texteDe(n) {
    var t = [n.titre || "", n.texte || "", n.legende || "", n.url || "",
             n.chemin || ""];
    (n.items || []).forEach(function (i) { t.push(i.texte || ""); });
    (n.sections || []).forEach(function (s) { t.push(s.nom || ""); });
    return t.join(" ").toLowerCase();
  }

  function appliquerRecherche() {
    var m = motCherche.trim().toLowerCase();
    trouves = [];
    if (!m) {
      Object.keys(vues).forEach(function (id) {
        vues[id].classList.remove("trouve", "estompe");
      });
      nCherche.textContent = "";
      return;
    }
    noeuds().forEach(function (n) {
      if (texteDe(n).indexOf(m) >= 0) { trouves.push(n.id); }
    });
    Object.keys(vues).forEach(function (id) {
      var ok = trouves.indexOf(id) >= 0;
      vues[id].classList.toggle("trouve", ok);
      vues[id].classList.toggle("estompe", !ok);
    });
    nCherche.textContent = trouves.length
      ? (iTrouve + 1 || 1) + "/" + trouves.length : "rien";
  }

  champCherche.addEventListener("input", function () {
    motCherche = champCherche.value;
    iTrouve = -1;
    appliquerRecherche();
  });

  champCherche.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && trouves.length) {
      ev.preventDefault();
      iTrouve = (iTrouve + (ev.shiftKey ? -1 : 1) + trouves.length) % trouves.length;
      allerNoeud(trouves[iTrouve]);
      nCherche.textContent = (iTrouve + 1) + "/" + trouves.length;
    }
    if (ev.key === "Escape") {
      champCherche.value = ""; motCherche = ""; appliquerRecherche();
      champCherche.blur();
    }
  });

  // ══ Onglets de toiles ═══════════════════════════════════════════════════

  function majOnglets() {
    zOnglets.innerHTML = etat.toiles.map(function (t) {
      return '<button class="at-onglet' + (t.id === etat.active ? " actif" : "")
        + '" data-toile="' + esc(t.id) + '">' + esc(t.nom)
        + '<span class="at-onglet-n">' + t.noeuds.length + "</span>"
        + '<span class="at-onglet-x" data-toile-x="' + esc(t.id)
        + '" title="Supprimer cette toile">×</span></button>';
    }).join("");
  }

  zOnglets.addEventListener("click", function (ev) {
    var x = ev.target.closest("[data-toile-x]");
    if (x) {
      ev.stopPropagation();
      if (etat.toiles.length < 2) {
        alert("C'est la dernière toile — elle ne peut pas être supprimée.");
        return;
      }
      var t = etat.toiles.filter(function (o) { return o.id === x.dataset.toileX; })[0];
      if (!confirm("Supprimer la toile « " + (t ? t.nom : "") + " » et tout ce "
                   + "qu'elle porte ? C'est définitif.")) { return; }
      etat.toiles = etat.toiles.filter(function (o) { return o.id !== x.dataset.toileX; });
      etat.active = etat.toiles[0].id;
      histo.length = 0; futur.length = 0;
      ouvrirToile();
      marquer();
      return;
    }
    var b = ev.target.closest("[data-toile]");
    if (!b || b.dataset.toile === etat.active) { return; }
    etat.active = b.dataset.toile;
    histo.length = 0; futur.length = 0;
    ouvrirToile();
    marquer();
  });

  zOnglets.addEventListener("dblclick", function (ev) {
    var b = ev.target.closest("[data-toile]");
    if (!b) { return; }
    var t = etat.toiles.filter(function (o) { return o.id === b.dataset.toile; })[0];
    if (!t) { return; }
    var nom = prompt("Nom de la toile", t.nom);
    if (nom === null) { return; }
    t.nom = nom.trim() || t.nom;
    majOnglets();
    marquer();
  });

  document.getElementById("at-toile-plus").addEventListener("click", function () {
    var t = toileNeuve("Toile " + (etat.toiles.length + 1));
    etat.toiles.push(t);
    etat.active = t.id;
    histo.length = 0; futur.length = 0;
    ouvrirToile();
    marquer();
  });

  function ouvrirToile() {
    var t = toile();
    Object.keys(vues).forEach(function (id) { vues[id].remove(); });
    vues = {};
    sel.clear(); selLien = null;
    cam = { x: t.cam.x, y: t.cam.y, k: t.cam.k };
    majOnglets();
    rendre(true);
    appliquerCam();
    majBoutonsHisto();
  }

  // ══ Barre ═══════════════════════════════════════════════════════════════

  document.getElementById("at-annuler").addEventListener("click", function () {
    restaurer(histo, futur);
  });
  document.getElementById("at-refaire").addEventListener("click", function () {
    restaurer(futur, histo);
  });
  document.getElementById("at-zoom-plus").addEventListener("click", function () {
    zoomer(cam.k * 1.2);
  });
  document.getElementById("at-zoom-moins").addEventListener("click", function () {
    zoomer(cam.k / 1.2);
  });
  document.getElementById("at-zoom-val").addEventListener("click", function () {
    zoomer(1);
  });
  document.getElementById("at-cadrer").addEventListener("click", function () {
    cadrer(boite(noeuds()));
  });
  document.getElementById("at-aide").addEventListener("click", function () {
    voile.hidden = false;
  });
  document.getElementById("at-aide-fermer").addEventListener("click", function () {
    voile.hidden = true;
  });
  voile.addEventListener("click", function (ev) {
    if (ev.target === voile) { voile.hidden = true; }
  });

  // ── Sauvegarde par fichier ──────────────────────────────────────────────
  // Le filet de sécurité qui ne dépend de rien : ni du miroir, ni du profil
  // du navigateur. Un atelier où l'on passe des heures mérite un export.

  document.getElementById("at-exporter").addEventListener("click", function () {
    dbToutesPieces().then(function (ps) {
      var utiles = {}, t, l, i;
      for (t = 0; t < etat.toiles.length; t++) {
        l = etat.toiles[t].noeuds;
        for (i = 0; i < l.length; i++) {
          if (l[i].piece) { utiles[l[i].piece] = true; }
        }
      }
      var paquet = {
        format: "optiq-atelier", v: 1,
        exporte: new Date().toISOString(),
        etat: etat,
        pieces: ps.filter(function (p) { return utiles[p.id]; })
      };
      var b = new Blob([JSON.stringify(paquet)], { type: "application/json" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = "atelier-" + new Date().toISOString().slice(0, 10) + ".json";
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
    });
  });

  var champFichier = document.getElementById("at-fichier");
  document.getElementById("at-importer").addEventListener("click", function () {
    champFichier.click();
  });
  champFichier.addEventListener("change", function () {
    var f = champFichier.files && champFichier.files[0];
    if (!f) { return; }
    var fr = new FileReader();
    fr.onload = function () {
      var p;
      try { p = JSON.parse(fr.result); } catch (e) { p = null; }
      if (!p || p.format !== "optiq-atelier" || !p.etat || !p.etat.toiles) {
        alert("Ce fichier n'est pas une sauvegarde d'atelier.");
        return;
      }
      if (!confirm("Remplacer l'atelier actuel par cette sauvegarde ("
                   + p.etat.toiles.length + " toile(s)) ? "
                   + "L'état actuel sera perdu.")) { return; }
      Promise.all((p.pieces || []).map(function (pc) {
        pieces[pc.id] = pc.donnees;
        return dbEcrire("pieces", pc);
      })).then(function () {
        etat = p.etat;
        histo.length = 0; futur.length = 0;
        piecesEnvoyees = {};
        ouvrirToile();
        marquer();
      });
    };
    fr.readAsText(f);
    champFichier.value = "";
  });

  // ══ Départ ══════════════════════════════════════════════════════════════

  function semer() {
    var t = toileNeuve("Plan de travail");
    var page = neuf("maquette", 420, 40);
    page.titre = "Fiche activité";
    page.chemin = "/activities/<id>";
    page.sections[0].nom = "En-tête — nom, entité, rôle";
    page.sections[1].nom = "Tâches";
    page.sections[2].nom = "Compétences";

    var mode = neuf("note", 40, 40);
    mode.titre = "Comment s'en servir";
    mode.teinte = "craie";
    mode.h = 320;
    mode.texte = "**Modèles**, en bas à droite de l'établi, pose d'un coup "
      + "le plan de l'application et vos chantiers.\n"
      + "\n---\n"
      + "Glissez le fond pour déplacer la toile.\n"
      + "Double-cliquez dessus pour une note. Collez une capture avec "
      + "**Ctrl+V**.\n"
      + "- `N` note · `L` liste · `P` page · `I` capture\n"
      + "- Tirez la bille à droite d'une pièce pour la relier\n"
      + "- Le badge ⊕ accroche une ligne à une section de page\n"
      + "- `?` ouvre tous les raccourcis\n"
      + "\n---\nCette note est un exemple : supprimez-la.";

    var liste = neuf("liste", 40, 300);
    liste.titre = "À faire";
    liste.items = [nouvelItem("Rattacher une ligne à une section →"),
                   nouvelItem("Poser une maquette par page de l'app"),
                   nouvelItem("Coller la capture de l'erreur")];
    liste.items[0].page = { n: page.id, s: page.sections[1].id };

    t.noeuds = [mode, page, liste];
    t.liens = [{ id: uid("l"), de: liste.id, vers: page.id, texte: "alimente" }];
    return { v: 1, toiles: [t], active: t.id };
  }

  function valider(d) {
    if (!d || !d.toiles || !d.toiles.length) { return null; }
    d.toiles.forEach(function (t) {
      t.noeuds = t.noeuds || [];
      t.liens = t.liens || [];
      t.cam = t.cam || { x: 0, y: 0, k: 1 };
    });
    if (!d.toiles.filter(function (t) { return t.id === d.active; }).length) {
      d.active = d.toiles[0].id;
    }
    return d;
  }

  function demarrer() {
    etatVisuel("cours", "Chargement…", "");
    var local = null;

    dbLire("doc", "courant").catch(function () { return null; })
      .then(function (l) {
        local = l;
        return jsonGet("/api/atelier/etat").catch(function () {
          return { miroir: false, erreur: "hub injoignable" };
        });
      })
      .then(function (e) {
        miroir.actif = !!e.miroir;
        miroir.erreur = e.erreur || null;
        majPiedAide(e);
        if (!miroir.actif) { return null; }
        return jsonGet("/api/atelier/toile/" + CLE_TOILE).catch(function () {
          miroir.actif = false;
          return null;
        });
      })
      .then(function (distant) {
        var dLocal = local && local.doc ? valider(local.doc) : null;
        var revL = local ? (local.rev || 0) : 0;
        var saleL = local ? !!local.sale : false;
        var dDist = null;

        if (distant && distant.contenu) {
          try { dDist = valider(JSON.parse(distant.contenu)); } catch (e) { dDist = null; }
        }

        if (dLocal && dDist) {
          // Le local gagne s'il porte des changements non poussés — sinon,
          // la version du miroir est au moins aussi récente.
          if (saleL || (distant.rev || 0) <= revL) {
            etat = dLocal; revLocale = revL; sale = saleL;
          } else {
            etat = dDist; revLocale = distant.rev; sale = false;
          }
        } else if (dDist) {
          etat = dDist; revLocale = distant.rev; sale = false;
        } else if (dLocal) {
          // ⚠️ `sale` passe à vrai dès qu'un miroir répond sans connaître
          // cette toile : c'est le cas au PREMIER déploiement avec
          // HUB_ATELIER_DB, et aussi quand on ouvre l'atelier sur un poste
          // qui a déjà travaillé hors miroir. Sans ça, la page affichait
          // « enregistré » alors que la base était vide — et personne ne
          // s'en apercevait avant de changer de poste.
          etat = dLocal; revLocale = revL; sale = saleL || miroir.actif;
        } else {
          etat = semer(); revLocale = 0; sale = true;
        }

        ouvrirToile();
        if (sale) { marquer(); }
        else {
          etatVisuel(miroir.actif ? "ok" : "local",
                     miroir.actif ? "enregistré" : "local",
                     miroir.actif ? "Toile et miroir à jour."
                                  : "Enregistré dans ce navigateur uniquement.");
        }
        return chargerPieces();
      })
      .catch(function (e) {
        etat = semer();
        ouvrirToile();
        etatVisuel("mal", "démarrage KO", e.message);
      });
  }

  function majPiedAide(e) {
    var pied = document.getElementById("at-aide-pied");
    if (!pied) { return; }
    if (e.miroir) {
      pied.innerHTML = "<b>Où vit votre travail.</b> La toile est écrite dans "
        + "ce navigateur à chaque geste, puis recopiée sur le miroir du hub "
        + "(<code>HUB_ATELIER_DB</code>) — elle vous suit d'un poste à l'autre. "
        + "L'export reste le filet : il emporte aussi les captures.";
    } else {
      pied.innerHTML = "<b>Où vit votre travail.</b> Tout est enregistré dans "
        + "<em>ce navigateur</em> (IndexedDB) : instantané, hors ligne, sans "
        + "aucun secret — mais lié à ce profil. Pour que la toile suive d'un "
        + "poste à l'autre, posez le secret <code>HUB_ATELIER_DB</code> "
        + "(une base PostgreSQL à vous) et redéployez le hub. "
        + "D'ici là, exportez de temps en temps : c'est un vrai fichier, "
        + "captures comprises."
        + (e.erreur ? "<br><b>Miroir :</b> " + esc(e.erreur) : "");
    }
  }

  // Un dernier passage avant de fermer l'onglet : le différé de 1,8 s ne doit
  // pas faire perdre la dernière frappe.
  window.addEventListener("pagehide", function () {
    if (!etat || !sale || !miroir.actif || !navigator.sendBeacon) { return; }
    try {
      // ⚠️ `sendBeacon` envoie TOUJOURS en POST : la route accepte donc POST
      // en plus de PUT. Sans ça, la dernière frappe partait dans un 405 que
      // personne ne voit — la page est déjà fermée.
      navigator.sendBeacon(
        "/api/atelier/toile/" + CLE_TOILE,
        new Blob([JSON.stringify({ contenu: JSON.stringify(etat), rev: revLocale })],
                 { type: "application/json" }));
    } catch (e) { /* le local a déjà la version à jour */ }
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden" && sale) { pousser(); }
  });

  window.addEventListener("resize", dessinerMini);

  demarrer();
})();
