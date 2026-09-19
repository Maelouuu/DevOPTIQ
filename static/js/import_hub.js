/* ════════════════════════════════════════════════════════════════════
   Importer des données — la fenêtre d'import de la page Carte.

   Trois natures (rôles, tâches, outils) et un import multiple. Les règles
   vivent côté serveur (Code/routes/import_hub.py) ; ici on les MONTRE :
   choisir → déposer → vérifier → importer.

   ⚠️ Les comptes n'entrent pas ici : une liste de collaborateurs est repérée
   et renvoyée vers la page Comptes, qui garde ses propres droits.
   ⚠️ Ce que propose l'IA n'est JAMAIS appliqué d'office : sa lecture d'un
   fichier comme ses rattachements d'activités passent par un compte rendu
   qu'on accepte — ou pas.
   ════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // ── Libellés ───────────────────────────────────────────────────────
  function L(cle) { return (window.IMPH_I18N || {})[cle] || cle; }
  function F(cle, vars) {
    let s = (window.IMPH_I18N || {})[cle] || cle;
    Object.keys(vars || {}).forEach(k => { s = s.split('{' + k + '}').join(vars[k]); });
    return s;
  }
  // « 0 rôle » en français, « 0 roles » en anglais : la règle du singulier
  // n'est pas la même. Le catalogue porte les deux formes, « un|plusieurs ».
  function P(cle, n) {
    const lib = window.IMPH_I18N || {};
    const formes = (lib[cle] || cle).split('|');
    const un = (lib.lang || 'fr') === 'fr' ? Math.abs(n) <= 1 : n === 1;
    return (un ? formes[0] : formes[formes.length - 1]).split('{n}').join(n);
  }
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Chaque nature porte la couleur de la page où vivent ses données.
  const COULEUR = { roles: '#059669', taches: '#7c3aed', outils: '#ea580c', multiple: '#0d9488',
                    comptes: '#e11d48' };
  const ICONE = { roles: 'fa-user-tie', taches: 'fa-list-check', outils: 'fa-screwdriver-wrench',
                  multiple: 'fa-layer-group', comptes: 'fa-users' };
  const CARTES = ['roles', 'taches', 'outils'];
  const ORDRE = ['roles', 'outils', 'taches'];
  const GARDABLES = new Set(['nouveau', 'partiel']);
  const EXT = /\.(xlsx|xlsm|csv)$/i;
  const MAX_FICHIERS = 8;

  let CTX = null;
  let S = neuf();
  const dom = {};

  function neuf() {
    return {
      ecran: 'choix', type: null,
      fichiers: [], parts: [], enLecture: [],
      verifs: {}, enCours: {}, jetons: {},
      exclus: {}, choix: {}, parIA: {}, ignorees: {}, filtres: {}, seulIA: {},
      active: null, cibles: [], portee: 'active',
      occupe: null, erreur: null, resultat: null, quitter: false, ecranRendu: null,
      rapport: null,   // rattachements proposés par l'IA, en attente de validation
      lecture: null,   // lecture d'une feuille par l'IA, en attente de validation
      recents: null,   // groupes que l'IA vient de rattacher : mis en évidence
      examen: {},      // ce que l'IA a déjà examiné, par part et par portée
    };
  }

  // ── Petits outils ──────────────────────────────────────────────────
  const nature = ty => (CTX && CTX.natures && CTX.natures[ty]) || { champs: [] };
  const partActive = () => S.parts.find(p => p.id === S.active) || S.parts[0];
  const aConfirmer = p => !!(p && p.ambigu && !p.nature_choisie);
  // ⚠️ Une feuille dont la nature est AMBIGUË (« Nom | Description » : des
  // rôles ou des outils ?) n'est pas importée tant qu'on ne l'a pas dite :
  // « Tout importer » aurait sinon créé des presses à injecter comme rôles.
  const inclue = p => !!(p && CARTES.includes(p.type) && p.reconnu && !S.ignorees[p.id]
                         && !aConfirmer(p));
  const exclus = p => (S.exclus[p.id] = S.exclus[p.id] || new Set());
  const listeDe = v => String(v || '').split(/[,;\n]/).map(x => x.trim()).filter(Boolean);
  const pourcent = x => F('pourcent', { n: Math.round(x * 100) });

  function gardees(p) {
    const v = S.verifs[p.id];
    if (!v) return [];
    const ex = exclus(p);
    return v.lignes.filter(l => GARDABLES.has(l.statut) && !ex.has(l._i)).map(l => l._i);
  }
  const nbGardees = p => (inclue(p) ? gardees(p).length : 0);
  const totalGardees = () => S.parts.reduce((n, p) => n + nbGardees(p), 0);

  // Ce qu'il ADVIENT d'une ligne : la même catégorie nourrit la pastille de la
  // ligne et le compteur qui la filtre — les deux disent la même chose.
  function issue(p, l) {
    if (GARDABLES.has(l.statut)) return exclus(p).has(l._i) ? 'ecartes' : 'ajoutes';
    return { present: 'deja', ignore: 'ecartes', a_rattacher: 'a_rattacher' }[l.statut] || 'invalide';
  }

  function compter(p, v) {
    const c = { tous: v.lignes.length, ajoutes: 0, deja: 0, ecartes: 0, a_rattacher: 0, invalide: 0 };
    v.lignes.forEach(l => { c[issue(p, l)] += 1; });
    return c;
  }

  function lettre(i) {
    let s = '';
    for (i += 1; i > 0; i = Math.floor((i - 1) / 26)) s = String.fromCharCode(65 + (i - 1) % 26) + s;
    return s;
  }

  async function envoyer(url, corps, json) {
    const r = await fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: json ? { 'Content-Type': 'application/json' } : undefined,
      body: json ? JSON.stringify(corps) : corps,
    });
    let data = null;
    try { data = await r.json(); } catch (e) { /* réponse sans JSON */ }
    if (!r.ok) throw new Error((data && data.error) || L('err_reseau'));
    return data;
  }

  // ── Libellés qui dépendent de la nature (accords, pluriels) ─────────
  function libTuile(cat, ty, n) {
    return {
      roles: { tous: P('tu_tous_roles', n), ajoutes: P('tu_ajoutes_roles', n),
               deja: P('tu_deja_roles', n), ecartes: P('tu_ecartes_roles', n),
               invalide: P('tu_invalide_roles', n) },
      outils: { tous: P('tu_tous_outils', n), ajoutes: P('tu_ajoutes_outils', n),
                deja: P('tu_deja_outils', n), ecartes: P('tu_ecartes_outils', n),
                invalide: P('tu_invalide_outils', n) },
      taches: { tous: P('tu_tous_taches', n), ajoutes: P('tu_ajoutes_taches', n),
                deja: P('tu_deja_taches', n), ecartes: P('tu_ecartes_taches', n),
                invalide: P('tu_invalide_taches', n), a_rattacher: P('tu_rattacher_taches', n) },
    }[ty][cat];
  }

  function libPastille(cat, ty, partiel) {
    const genre = {
      ajoutes: { roles: L('pas_ajoute_roles'), outils: L('pas_ajoute_outils'), taches: L('pas_ajoute_taches') },
      partiel: { roles: L('pas_partiel_roles'), outils: L('pas_partiel_outils'), taches: L('pas_partiel_taches') },
      ecartes: { roles: L('pas_ecarte_roles'), outils: L('pas_ecarte_outils'), taches: L('pas_ecarte_taches') },
    };
    if (cat === 'ajoutes') return (partiel ? genre.partiel : genre.ajoutes)[ty];
    if (cat === 'ecartes') return genre.ecartes[ty];
    return { deja: L('pas_deja'), a_rattacher: L('pas_rattacher'), invalide: L('pas_corriger') }[cat];
  }

  // La confiance de l'IA se lit TOUJOURS de la même façon : trois traits et un mot.
  function jauge(conf) {
    const c = ['high', 'medium', 'low'].includes(conf) ? conf : 'medium';
    const mot = { high: L('conf_high'), medium: L('conf_medium'), low: L('conf_low') }[c];
    return `<span class="imh-jauge c-${c}" title="${esc(mot)}"><span class="imh-jauge-t"><i></i><i></i><i></i></span>${esc(mot)}</span>`;
  }

  // ══════════════════════════════════════════════════════════════════
  //  Ouvrir, fermer
  // ══════════════════════════════════════════════════════════════════
  function ouvrir() {
    S = neuf();
    CTX = null;     // l'entité active a pu changer depuis la dernière ouverture
    dom.racine.hidden = false;
    document.body.classList.add('imh-ouvert');
    rendre();
    chargerContexte();
    setTimeout(() => dom.fenetre.focus(), 30);
  }

  function fermer(force) {
    // Rien n'est écrit avant « Importer » : partir est sans conséquence, mais
    // on ne jette pas une vérification en cours d'examen sur un clic égaré.
    if (!force && S.ecran === 'revue' && S.parts.length && S.occupe !== 'import') {
      S.quitter = true;
      rendrePied();
      return;
    }
    dom.racine.hidden = true;
    document.body.classList.remove('imh-ouvert');
    dom.corps.innerHTML = '';
    S = neuf();
  }

  async function chargerContexte() {
    try {
      const r = await fetch('/api/import/contexte', { credentials: 'same-origin' });
      if (!r.ok) throw new Error(L('err_reseau'));
      CTX = await r.json();
      porteeParDefaut();
    } catch (e) {
      S.erreur = e.message || L('err_reseau');
    }
    rendre();
  }

  function porteeParDefaut() {
    const cibles = CTX.cibles || [];
    const active = cibles.find(c => c.active);
    S.cibles = active ? [active.id] : (cibles[0] ? [cibles[0].id] : []);
    S.portee = active ? 'active' : 'choisir';
  }

  // ══════════════════════════════════════════════════════════════════
  //  Rendu
  // ══════════════════════════════════════════════════════════════════
  function rendre() {
    if (!dom.racine || dom.racine.hidden) return;
    const haut = dom.corps.scrollTop;
    const vue = S.ecran + (S.rapport ? ':rapport' : '') + (S.lecture ? ':lecture' : '');
    dom.fenetre.style.setProperty('--tc', COULEUR[S.type] || '#db2777');
    dom.fenetre.dataset.ecran = S.ecran;
    rendreTete();
    const ecran = { choix: ecranChoix, depot: ecranDepot, revue: ecranRevue, fin: ecranFin }[S.ecran];
    dom.corps.innerHTML = erreurHtml() + ecran();
    rendrePied();
    dom.corps.scrollTop = S.ecranRendu === vue ? haut : 0;
    S.ecranRendu = vue;
  }

  function rendreTete() {
    const i = ['choix', 'depot', 'revue', 'fin'].indexOf(S.ecran);
    const etapes = [L('etape_nature'), L('etape_fichier'), L('etape_verif'), L('etape_import')];
    dom.etapes.innerHTML = etapes.map((lib, j) => {
      const cl = j < i ? 'fait' : (j === i ? 'ici' : '');
      const puce = j < i ? '<i class="fa-solid fa-check"></i>' : String(j + 1);
      return `<li class="${cl}"${j === i ? ' aria-current="step"' : ''}><span>${puce}</span><em>${esc(lib)}</em></li>`;
    }).join('');
    const sous = {
      choix: L('sous_choix'),
      depot: S.type ? F('sous_depot', { x: nature(S.type).nom }) : '',
      revue: S.rapport || S.lecture ? L('sous_ia') : L('sous_revue'),
      fin: L('sous_fin'),
    }[S.ecran];
    dom.sous.textContent = sous || '';
    dom.logo.innerHTML = `<i class="fa-solid ${S.type ? ICONE[S.type] : 'fa-file-import'}"></i>`;
  }

  function erreurHtml() {
    if (!S.erreur) return '';
    return `<div class="imh-erreur" role="alert"><i class="fa-solid fa-circle-exclamation"></i>
      <span>${esc(S.erreur)}</span>
      <button type="button" data-action="erreur-ok" aria-label="${esc(L('fermer'))}"><i class="fa-solid fa-xmark"></i></button></div>`;
  }

  // ── 1 · Choisir la nature ──────────────────────────────────────────
  function ecranChoix() {
    if (!CTX) return S.erreur ? '' : `<div class="imh-attente"><i class="fa-solid fa-circle-notch fa-spin"></i></div>`;
    const promesses = [
      ['fa-eye', L('promesse_apercu')],
      CTX.ia ? ['fa-wand-magic-sparkles', L('promesse_ia')] : ['fa-file-arrow-down', L('promesse_modele')],
      ['fa-map-location-dot', L('promesse_portee')],
    ];
    return `<div class="imh-choix">
      <div class="imh-cartes">${CARTES.map(carte).join('')}</div>
      ${carteMultiple()}
      <ul class="imh-promesses">${promesses.map(([ic, txt], i) =>
        `<li style="--i:${i + 4}"><i class="fa-solid ${ic}"></i><span>${esc(txt)}</span></li>`).join('')}</ul>
    </div>`;
  }

  const puce = c => `<span class="imh-puce${c.requis ? ' is-requis' : ''}">${esc(c.label)}</span>`;

  function carte(ty, i) {
    const n = nature(ty), ok = !!CTX.peut;
    return `<button type="button" class="imh-carte" data-type="${ty}" style="--tc:${COULEUR[ty]};--i:${i}"${ok ? '' : ' disabled'}>
      <span class="imh-carte-haut">
        <span class="imh-carte-ic"><i class="fa-solid ${ICONE[ty]}"></i></span>
        <span class="imh-carte-go" aria-hidden="true"><i class="fa-solid fa-arrow-right"></i></span>
      </span>
      <span class="imh-carte-t">${esc(n.nom)}</span>
      <span class="imh-carte-d">${esc(n.desc)}</span>
      <span class="imh-carte-champs">${n.champs.map(puce).join('')}</span>
      <span class="imh-carte-portee"><i class="fa-solid fa-map-location-dot"></i>${esc(n.portee)}</span>
      ${ok ? '' : `<span class="imh-carte-verrou"><i class="fa-solid fa-lock"></i>${esc(L('verrou_cartos'))}</span>`}
    </button>`;
  }

  function carteMultiple() {
    const n = nature('multiple'), ok = !!CTX.peut;
    const ics = CARTES.map(ty => `<span style="--tc:${COULEUR[ty]}"><i class="fa-solid ${ICONE[ty]}"></i></span>`).join('');
    return `<button type="button" class="imh-carte imh-carte--multi" data-type="multiple" style="--tc:${COULEUR.multiple};--i:3"${ok ? '' : ' disabled'}>
      <span class="imh-multi-ics" aria-hidden="true">${ics}</span>
      <span class="imh-multi-txt">
        <span class="imh-carte-t">${esc(n.nom)}</span>
        <span class="imh-carte-d">${esc(n.desc)}</span>
      </span>
      <span class="imh-carte-portee"><i class="fa-solid fa-sitemap"></i>${esc(n.portee)}</span>
      <span class="imh-carte-go" aria-hidden="true"><i class="fa-solid fa-arrow-right"></i></span>
    </button>`;
  }

  // ── 2 · Déposer le fichier ─────────────────────────────────────────
  function ecranDepot() {
    const ty = S.type, multi = ty === 'multiple', n = nature(ty);
    const lecture = S.occupe === 'lecture';
    const attendu = multi
      ? `<span class="imh-attendu-t">${esc(L('multi_reconnues'))}</span>` + CARTES.map(t =>
          `<span class="imh-puce is-type" style="--tc:${COULEUR[t]}"><i class="fa-solid ${ICONE[t]}"></i>${esc(nature(t).nom)}</span>`).join('')
      : `<span class="imh-attendu-t">${esc(L('colonnes_reconnues'))}</span>${n.champs.map(puce).join('')}
         <span class="imh-attendu-leg"><i></i>${esc(L('obligatoire'))}</span>`;
    return `<div class="imh-depot">
      <label class="imh-zone${lecture ? ' is-lecture' : ''}" tabindex="0">
        <input type="file" id="imh-input" accept=".xlsx,.xlsm,.csv"${multi ? ' multiple' : ''} hidden${lecture ? ' disabled' : ''}>
        ${lecture ? zoneLecture() : zoneRepos(multi)}
      </label>
      <div class="imh-attendu">${attendu}</div>
      <div class="imh-depot-bas">
        <a class="imh-lien" href="/api/import/modele/${ty}" download><i class="fa-solid fa-file-arrow-down"></i>${esc(multi ? L('modele_multi') : L('modele'))}</a>
        ${CTX.ia ? `<span class="imh-astuce"><i class="fa-solid fa-wand-magic-sparkles"></i>${esc(L('astuce_ia'))}</span>` : ''}
      </div>
    </div>`;
  }

  function zoneRepos(multi) {
    return `<span class="imh-zone-ic"><i class="fa-solid fa-file-arrow-up"></i></span>
      <strong class="imh-zone-t">${esc(multi ? L('zone_titre_multi') : L('zone_titre'))}</strong>
      <span class="imh-zone-s">${esc(L('zone_ou'))} <u>${esc(L('zone_parcourir'))}</u></span>
      <small class="imh-zone-f">.xlsx · .xlsm · .csv — ${esc(F('zone_max', { n: CTX.max_mo }))}</small>`;
  }

  function zoneLecture() {
    const noms = S.enLecture.map(n => `<span><i class="fa-solid fa-file-excel"></i>${esc(n)}</span>`).join('');
    return `<span class="imh-zone-ic is-anime"><i class="fa-solid fa-file-lines"></i></span>
      <strong class="imh-zone-t">${esc(L('lecture'))}</strong>
      <span class="imh-zone-fichiers">${noms}</span>
      <span class="imh-barre"><span></span></span>`;
  }

  // ── 3 · Vérifier ───────────────────────────────────────────────────
  function ecranRevue() {
    const p = partActive();
    if (!p) return '';
    if (S.type !== 'multiple') {
      return `<div class="imh-revue" style="--tc:${COULEUR[p.type] || COULEUR[S.type]}">
        ${tetePart(p)}${corpsPart(p)}
      </div>`;
    }
    return `<div class="imh-revue is-multi">
      ${S.rapport || S.lecture ? '' : blocPortee()}
      <div class="imh-split">
        ${rail()}
        <div class="imh-part" style="--tc:${COULEUR[p.type] || '#94a3b8'}">
          ${tetePart(p)}${corpsPart(p)}
        </div>
      </div>
    </div>`;
  }

  // Ce qu'on montre pour une feuille, par ordre de priorité : ce que l'IA
  // attend qu'on valide, puis ce qui empêche de l'importer, puis la liste.
  function corpsPart(p) {
    if (S.lecture && S.lecture.partId === p.id) return blocLecture(S.lecture.part);
    if (S.rapport && S.rapport.partId === p.id) return blocRapport();
    if (S.ignorees[p.id]) return blocIgnoree();
    if (p.type === 'comptes') return blocComptes(p);
    if (aConfirmer(p)) return blocAmbigu(p) + blocSource(p);
    if (!p.type || !p.reconnu) return blocNonReconnu(p);
    return blocSource(p) + (S.type === 'multiple' ? '' : blocPortee()) + blocListe(p);
  }

  function tetePart(p) {
    const multi = S.type === 'multiple';
    const feuille = p.n_feuilles > 1 ? ` <span class="imh-tp-feuille">› ${esc(p.feuille)}</span>` : '';
    const compte = p.reconnu ? ` <span class="imh-tp-n">· ${esc(P('n_lignes', p.lignes.length))}</span>` : '';
    const titre = p.type === 'comptes' ? L('cpt_rail') : (p.type ? nature(p.type).nom : L('nature_inconnue'));
    let action = '';
    // Une feuille de personnes n'est déjà pas importée : offrir de « ne pas
    // l'importer » laisserait croire qu'elle le serait.
    if (multi && !S.rapport && !S.lecture && p.type !== 'comptes') {
      action = `<button type="button" class="imh-btn-lien" data-action="ignorer"><i class="fa-solid ${S.ignorees[p.id] ? 'fa-rotate-left' : 'fa-eye-slash'}"></i>${esc(S.ignorees[p.id] ? L('reprendre_feuille') : L('ignorer_feuille'))}</button>`;
    } else if (!multi && p.reconnu && !S.rapport && !S.lecture) {
      action = `<button type="button" class="imh-btn-lien" data-action="autre-fichier"><i class="fa-solid fa-arrow-rotate-left"></i>${esc(L('autre_fichier'))}</button>`;
    }
    const natures = multi && !S.ignorees[p.id] && !S.rapport && !S.lecture && p.type !== 'comptes'
      ? choixNature(p) : '';
    return `<div class="imh-tp">
      <span class="imh-tp-ic"><i class="fa-solid ${ICONE[p.type] || 'fa-question'}"></i></span>
      <div class="imh-tp-txt">
        <strong>${esc(titre)}</strong>
        <span class="imh-tp-src"><i class="fa-regular fa-file-excel"></i>${esc(p.fichier)}${feuille}${compte}</span>
      </div>
      ${action}
    </div>${natures}`;
  }

  // Import multiple : la nature se corrige d'un clic, la feuille est relue.
  function boutonsNature(p, tous) {
    const doute = aConfirmer(p);
    return CARTES.map(ty => {
      const on = !tous && p.type === ty && !doute;
      return `<button type="button" class="imh-nat${on ? ' on' : ''}" data-comme="${ty}" style="--tc:${COULEUR[ty]}"${on || S.occupe ? ' disabled' : ''} aria-pressed="${on}"><i class="fa-solid ${ICONE[ty]}"></i>${esc(nature(ty).nom)}</button>`;
    }).join('');
  }

  function choixNature(p) {
    return `<div class="imh-nats"><span class="imh-mini">${esc(L('feuille_contient'))}</span>${boutonsNature(p, false)}</div>`;
  }

  function blocAmbigu(p) {
    const [a, b] = p.ambigu;
    const choix = p.ambigu.map(ty => `<button type="button" class="imh-amb-b" data-comme="${ty}" style="--tc:${COULEUR[ty]}"${S.occupe ? ' disabled' : ''}>
        <span class="imh-carte-ic"><i class="fa-solid ${ICONE[ty]}"></i></span>
        <span><strong>${esc(nature(ty).nom)}</strong><small>${esc(nature(ty).desc)}</small></span>
      </button>`).join('');
    return `<div class="imh-amb">
      <div class="imh-amb-t"><span class="imh-nr-ic"><i class="fa-solid fa-circle-question"></i></span>
        <div><h3>${esc(F('ambigu_titre', { a: nature(a).nom, b: nature(b).nom }))}</h3>
        <p>${esc(L('ambigu_texte'))}</p></div></div>
      <div class="imh-amb-choix">${choix}</div>
    </div>`;
  }

  // Une liste de collaborateurs : elle se reconnaît, et se renvoie ailleurs.
  function blocComptes(p) {
    const c = CTX.comptes || {};
    const lien = c.peut
      ? `<a class="imh-btn-sec" href="${esc(c.url)}" target="_blank" rel="noopener"><i class="fa-solid fa-arrow-up-right-from-square"></i>${esc(L('cpt_lien'))}</a>`
      : '';
    const autre = S.type === 'multiple'
      ? `<div class="imh-nats"><span class="imh-mini">${esc(L('cpt_pas_personnes'))}</span>${boutonsNature(p, true)}</div>`
      : `<div class="imh-nr-actions">
          <button type="button" class="imh-btn-sec" data-comme="${S.type}"><i class="fa-solid ${ICONE[S.type]}"></i>${esc(F('lire_comme', { x: nature(S.type).nom.toLocaleLowerCase() }))}</button>
          <button type="button" class="imh-btn-sec" data-action="autre-fichier"><i class="fa-solid fa-arrow-rotate-left"></i>${esc(L('autre_fichier'))}</button>
        </div>`;
    return `<div class="imh-nr imh-cpt">
      <div class="imh-nr-tete">
        <span class="imh-nr-ic is-cpt"><i class="fa-solid fa-users"></i></span>
        <div><h3>${esc(L('cpt_titre'))}</h3><p>${esc(c.peut ? L('cpt_texte') : L('cpt_texte_reserve'))}</p></div>
        ${lien}
      </div>
      ${apercuBrut(p)}
      ${autre}
    </div>`;
  }

  function colonne(p, i) {
    const titre = p.ligne_entete >= 0 && p.entetes ? p.entetes[i] : '';
    // « … » en français, “…” en anglais : les guillemets suivent la langue.
    return titre ? F('citation', { x: titre }) : F('colonne', { x: lettre(i) });
  }

  function blocSource(p) {
    const ia = p.source === 'IA';
    const maps = nature(p.type).champs.filter(c => p.correspondance[c.cle] != null).map(c =>
      `<span class="imh-map"><span class="imh-map-col">${esc(colonne(p, p.correspondance[c.cle]))}</span><i class="fa-solid fa-arrow-right"></i><span class="imh-map-f">${esc(c.label)}</span></span>`);
    return `<div class="imh-source ${ia ? 'is-ia' : 'is-fichier'}">
      <div class="imh-source-t">
        <span class="imh-source-ic"><i class="fa-solid ${ia ? 'fa-wand-magic-sparkles' : 'fa-circle-check'}"></i></span>
        <strong>${esc(ia ? L('source_ia') : L('source_fichier'))}</strong>${ia ? jauge(p.confiance) : ''}
      </div>
      <div class="imh-maps">${maps.join('')}</div>
    </div>`;
  }

  function bouton(k, ic, lib) {
    const on = S.portee === k;
    return `<button type="button" role="radio" class="imh-seg-b${on ? ' on' : ''}" aria-checked="${on}" data-portee="${k}"><i class="fa-solid ${ic}"></i><span>${esc(lib)}</span></button>`;
  }

  function blocPortee() {
    const cibles = CTX.cibles || [];
    if (!S.parts.some(inclue)) return '';
    if (!cibles.length) {
      return `<section class="imh-portee is-bloque"><span class="imh-portee-ic"><i class="fa-solid fa-lock"></i></span><p>${esc(L('portee_aucune'))}</p></section>`;
    }
    const texte = S.type === 'multiple' ? L('portee_multiple')
      : { roles: L('portee_roles'), outils: L('portee_outils'), taches: L('portee_taches') }[S.type];
    const active = cibles.find(c => c.active);
    const seg = cibles.length > 1
      ? `<div class="imh-seg" role="radiogroup" aria-label="${esc(L('portee_titre'))}">
          ${active ? bouton('active', 'fa-location-dot', F('portee_active', { x: active.name })) : ''}
          ${bouton('choisir', 'fa-list-check', L('portee_choisir'))}
          ${bouton('toutes', 'fa-layer-group', F('portee_toutes', { n: cibles.length }))}
        </div>`
      : `<span class="imh-portee-une"><i class="fa-solid fa-location-dot"></i>${esc(cibles[0].name)}</span>`;
    const liste = S.portee === 'choisir' && cibles.length > 1
      ? `<div class="imh-cartos">${cibles.map(c => {
          const on = S.cibles.includes(c.id);
          return `<button type="button" class="imh-carto${on ? ' on' : ''}" data-carto="${c.id}" aria-pressed="${on}"><i class="fa-${on ? 'solid fa-square-check' : 'regular fa-square'}"></i><span>${esc(c.name)}</span>${c.active ? `<em>${esc(L('carto_active'))}</em>` : ''}${c.shared ? `<em class="is-commune">${esc(L('carto_commune'))}</em>` : ''}</button>`;
        }).join('')}</div>`
      : '';
    return `<section class="imh-portee">
      <div class="imh-portee-tete">
        <span class="imh-portee-ic"><i class="fa-solid fa-location-crosshairs"></i></span>
        <div class="imh-portee-txt"><h4>${esc(L('portee_titre'))}</h4><p>${esc(texte)}</p></div>
        ${seg}
      </div>
      ${liste}
    </section>`;
  }

  function blocListe(p) {
    const v = S.verifs[p.id];
    if (!S.cibles.length) {
      return `<div class="imh-vide"><i class="fa-solid fa-map-location-dot"></i>${esc(L('choisir_carto'))}</div>`;
    }
    if (!v) return `<div class="imh-attente"><i class="fa-solid fa-circle-notch fa-spin"></i>${esc(L('verification'))}</div>`;
    if (!v.lignes.length) return `<div class="imh-vide"><i class="fa-regular fa-folder-open"></i>${esc(L('aucune_ligne'))}</div>`;
    const filtre = S.filtres[p.id] || 'tous';
    return `<div class="imh-liste-zone${S.enCours[p.id] ? ' is-maj' : ''}">
      ${tuiles(p, v, filtre)}
      ${p.type === 'taches' ? listeTaches(p, v, filtre) : listePlate(p, v, filtre)}
    </div>`;
  }

  // Les compteurs disent ce qu'il ADVIENT des lignes — et de quelles lignes
  // il s'agit : « 60 tâches ajoutées », pas « 60 nouveaux ».
  // Une tuile vide ne dit rien — sauf celle qu'on est en train de filtrer :
  // la retirer sous le pointeur laisserait une liste sans titre.
  function categories(p, c, filtre) {
    return ['tous', 'ajoutes', 'deja', 'ecartes', 'a_rattacher', 'invalide']
      .filter(k => (k !== 'a_rattacher' || p.type === 'taches')
        && (c[k] > 0 || k === 'tous' || k === 'ajoutes' || k === filtre));
  }

  function tuiles(p, v, filtre) {
    const c = compter(p, v);
    const cats = categories(p, c, filtre);
    const eligibles = v.lignes.filter(l => GARDABLES.has(l.statut)).length;
    const tout = eligibles
      ? `<label class="imh-tout"><input type="checkbox" data-action="tout"${gardees(p).length === eligibles ? ' checked' : ''}><span>${esc(L('tout_garder'))}</span></label>`
      : '';
    return `<div class="imh-tuiles">
      ${cats.map(k => `<button type="button" class="imh-tuile t-${k}${filtre === k ? ' on' : ''}" data-filtre="${k}" aria-pressed="${filtre === k}"><b>${c[k]}</b><span>${esc(libTuile(k, p.type, c[k]))}</span></button>`).join('')}
      ${tout}
    </div>`;
  }

  function listePlate(p, v, filtre) {
    const lignes = v.lignes.filter(l => filtre === 'tous' || issue(p, l) === filtre);
    if (!lignes.length) return `<div class="imh-vide">${esc(L('filtre_vide'))}</div>`;
    return `<div class="imh-liste">${lignes.map(l => ligne(p, l)).join('')}</div>`;
  }

  function ligne(p, l) {
    const gardable = GARDABLES.has(l.statut);
    const garde = gardable && !exclus(p).has(l._i);
    return `<div class="imh-l${garde || !gardable ? '' : ' is-off'} st-${l.statut}" data-i="${l._i}">
      <input type="checkbox" class="imh-cb" data-i="${l._i}"${garde ? ' checked' : ''}${gardable ? '' : ' disabled'} aria-label="${esc(L('garder'))}">
      <div class="imh-l-c">${contenu(p.type, l)}${notes(l)}</div>
      ${pastille(p, l)}
    </div>`;
  }

  function contenu(ty, l) {
    if (ty === 'taches') {
      const puces = [
        ...listeDe(l.outils).map(x => `<span class="imh-chip c-outil"><i class="fa-solid fa-screwdriver-wrench"></i>${esc(x)}</span>`),
        l.realisateur ? `<span class="imh-chip"><i class="fa-solid fa-user-gear"></i>${esc(F('realise', { x: l.realisateur }))}</span>` : '',
        l.approbateur ? `<span class="imh-chip"><i class="fa-solid fa-user-check"></i>${esc(F('valide', { x: l.approbateur }))}</span>` : '',
        ...listeDe(l.competences).map(x => `<span class="imh-chip c-comp"><i class="fa-solid fa-graduation-cap"></i>${esc(x)}</span>`),
      ].join('');
      return `<span class="imh-l-t"><strong>${esc(l.tache || '—')}</strong>${l.description ? `<span class="imh-l-s">${esc(l.description)}</span>` : ''}</span>
        ${puces ? `<span class="imh-l-puces">${puces}</span>` : ''}`;
    }
    const sec = ty === 'roles' ? l.mission : l.description;
    return `<span class="imh-l-t"><strong>${esc(l.nom || '—')}</strong>${sec ? `<span class="imh-l-s">${esc(sec)}</span>` : ''}</span>`;
  }

  function notes(l) {
    const out = [];
    if (l.raison) out.push(`<span class="imh-note ${l.statut === 'invalide' ? 'n-bad' : 'n-neutre'}">${esc(l.raison)}</span>`);
    if (l.statut === 'partiel') {
      out.push(`<span class="imh-note n-info">${esc(F('partiel_detail', { deja: l.n_deja, total: l.n_nouveau + l.n_deja }))}</span>`);
    }
    return out.length ? `<span class="imh-notes">${out.join('')}</span>` : '';
  }

  function pastille(p, l) {
    const cat = issue(p, l);
    const ic = { ajoutes: 'fa-plus', deja: 'fa-check', ecartes: 'fa-minus', a_rattacher: 'fa-link-slash',
                 invalide: 'fa-triangle-exclamation' }[cat];
    return `<span class="imh-pas p-${cat}"><i class="fa-solid ${ic}"></i>${esc(libPastille(cat, p.type, l.statut === 'partiel'))}</span>`;
  }

  // Les tâches se lisent par activité : c'est à l'activité qu'on les rattache.
  function listeTaches(p, v, filtre) {
    const restants = v.groupes.filter(g => g.mode === 'a_rattacher');
    const vus = examinees(p);
    const aExaminer = restants.filter(g => !(g.activite_fichier in vus));
    const parIA = S.parIA[p.id] || {};
    const nIA = v.groupes.filter(g => estParIA(g, parIA)).length;
    const seul = S.seulIA[p.id] && nIA;
    const barre = aExaminer.length ? barreRapprocher(aExaminer.length)
      : restants.length ? barreDejaVu(restants, vus) : '';
    const bilanIA = nIA ? `<div class="imh-ia-bilan"><i class="fa-solid fa-wand-magic-sparkles"></i>
        <span>${esc(P('rp_appliques', nIA))}</span>
        <button type="button" class="imh-btn-lien" data-action="seul-ia">${esc(seul ? L('voir_tout') : L('voir_ia'))}</button></div>` : '';
    const recents = S.recents && S.recents.partId === p.id ? new Set(S.recents.noms) : new Set();
    const groupes = v.groupes
      .filter(g => !seul || estParIA(g, parIA))
      .map((g, i) => groupe(p, g, i, filtre, v, recents.has(g.activite_fichier))).join('');
    return `${barre}${bilanIA}<div class="imh-groupes">${groupes || `<div class="imh-vide">${esc(L('filtre_vide'))}</div>`}</div>`;
  }

  const estParIA = (g, parIA) => g.mode === 'manuel' && parIA[g.activite_fichier]
    && parIA[g.activite_fichier].activite === g.choix;

  function barreRapprocher(n) {
    if (!CTX.ia) {
      return `<div class="imh-ia-barre is-sans"><span class="imh-ia-ic"><i class="fa-solid fa-link-slash"></i></span><span class="imh-ia-txt">${esc(P('a_rattacher_sans_ia', n))}</span></div>`;
    }
    const enCours = S.occupe === 'rapprocher';
    return `<div class="imh-ia-barre${enCours ? ' is-anime' : ''}">
      <span class="imh-ia-ic"><i class="fa-solid fa-wand-magic-sparkles"></i></span>
      <span class="imh-ia-txt">${esc(P('ia_rapprocher_texte', n))}</span>
      <button type="button" class="imh-btn-ia" data-action="rapprocher"${enCours ? ' disabled' : ''}>${enCours
        ? `<i class="fa-solid fa-circle-notch fa-spin"></i>${esc(L('ia_en_cours'))}`
        : `<i class="fa-solid fa-wand-magic-sparkles"></i>${esc(L('ia_rapprocher'))}`}</button>
    </div>`;
  }

  // Ce que l'IA a déjà examiné pour cette part — à portée égale : d'autres
  // cartos, ce sont d'autres activités candidates, l'examen est à refaire.
  function examinees(p) {
    const ex = S.examen[p.id];
    return ex && ex.cle === S.cibles.join(',') ? ex.props : {};
  }

  // Les activités restantes, l'IA les a déjà vues : lui redemander rendrait
  // la même réponse. On le dit, et on rouvre ses propositions si elle en a fait.
  function barreDejaVu(restants, vus) {
    const avecProposition = restants.some(g => vus[g.activite_fichier]);
    return `<div class="imh-ia-barre is-vu">
      <span class="imh-ia-ic"><i class="fa-solid fa-wand-magic-sparkles"></i></span>
      <span class="imh-ia-txt">${esc(P('ia_deja_vu', restants.length))}</span>
      ${avecProposition ? `<button type="button" class="imh-btn-lien" data-action="revoir"><i class="fa-solid fa-rotate-left"></i>${esc(L('ia_revoir'))}</button>` : ''}
    </div>`;
  }

  function groupe(p, g, i, filtre, v, recent) {
    const lignes = g.lignes.filter(l => filtre === 'tous' || issue(p, l) === filtre);
    if (!lignes.length) return '';
    const ia = estParIA(g, S.parIA[p.id] || {}) ? S.parIA[p.id][g.activite_fichier] : null;
    const meta = [
      g.garant ? `<span class="imh-chip c-garant"><i class="fa-solid fa-shield-halved"></i>${esc(F('garant', { x: g.garant }))}</span>` : '',
      `<span class="imh-g-n">${esc(P('n_taches', g.lignes.length))}</span>`,
      g.choix && g.n_cibles > 1 ? `<span class="imh-g-n">${esc(F('dans_n_cartos', { n: g.n_cartos, total: g.n_cibles }))}</span>` : '',
    ].join('');
    const cl = ['imh-g', 'm-' + g.mode, ia ? 'is-ia' : '', recent ? 'is-recent' : ''].join(' ');
    return `<section class="${cl}" style="--i:${Math.min(i, 12)}" data-groupe="${esc(g.activite_fichier)}">
      <div class="imh-g-tete">
        <div class="imh-g-src"><span class="imh-mini">${esc(L('dans_fichier'))}</span><strong>${esc(g.activite_fichier || L('sans_activite'))}</strong></div>
        <i class="fa-solid fa-arrow-right-long imh-g-fleche" aria-hidden="true"></i>
        <div class="imh-g-dest"><span class="imh-mini">${esc(L('dans_carto'))}</span>
          ${selectActivite(g, v)}${legende(g, ia)}
        </div>
      </div>
      <div class="imh-g-meta">${meta}</div>
      <div class="imh-liste">${lignes.map(l => ligne(p, l)).join('')}</div>
    </section>`;
  }

  function selectActivite(g, v) {
    if (g.mode === 'sans_activite') return '';
    const val = g.mode === 'ignore' ? '__ignorer__' : (g.choix || '');
    const opt = (nom, lib) => `<option value="${esc(nom)}"${nom === val ? ' selected' : ''}>${esc(lib || nom)}</option>`;
    const proches = g.possibles.filter(x => x.score >= 0.5);
    return `<select class="imh-sel" data-groupe="${esc(g.activite_fichier)}" aria-label="${esc(L('dans_carto'))}">
      ${val === '' ? `<option value="" selected disabled>${esc(L('choisir_activite'))}</option>` : ''}
      ${proches.length ? `<optgroup label="${esc(L('les_plus_proches'))}">${proches.map(x => opt(x.nom, `${x.nom} · ${pourcent(x.score)}`)).join('')}</optgroup>` : ''}
      <optgroup label="${esc(L('toutes_activites'))}">${v.activites.map(n => opt(n)).join('')}</optgroup>
      <option value="__ignorer__"${val === '__ignorer__' ? ' selected' : ''}>${esc(L('ignorer_groupe'))}</option>
    </select>`;
  }

  // D'où vient le rattachement : une LIGNE de texte sous le choix, jamais une
  // pastille — rien ici ne se clique, cela ne doit pas en avoir l'air.
  function legende(g, ia) {
    if (ia) {
      return `<p class="imh-leg is-ia"><i class="fa-solid fa-wand-magic-sparkles"></i><span>${esc(L('leg_ia'))}</span>${jauge(ia.confiance)}${ia.raison ? `<em>${esc(ia.raison)}</em>` : ''}</p>`;
    }
    const top = g.possibles[0];
    const cfg = {
      exact: ['is-ok', 'fa-check', L('leg_exact')],
      proche: ['is-proche', 'fa-wave-square', F('leg_proche', { x: top ? pourcent(top.score) : '' })],
      manuel: ['', 'fa-hand-pointer', L('leg_manuel')],
      a_rattacher: ['is-warn', 'fa-link-slash', L('leg_a_rattacher')],
      ignore: ['is-off', 'fa-eye-slash', L('leg_ignore')],
    }[g.mode];
    return cfg ? `<p class="imh-leg ${cfg[0]}"><i class="fa-solid ${cfg[1]}"></i><span>${esc(cfg[2])}</span></p>` : '';
  }

  // ── Les deux comptes rendus de l'IA — rien n'est appliqué sans eux ──
  function blocRapport() {
    const r = S.rapport;
    const trouves = r.noms.filter(n => r.props[n]).length;
    const lignes = r.noms.map((n, i) => {
      const pr = r.props[n];
      const src = `<div class="imh-rp-src"><span class="imh-mini">${esc(L('dans_fichier'))}</span><strong>${esc(n)}</strong></div>
        <i class="fa-solid fa-arrow-right-long imh-rp-fl" aria-hidden="true"></i>`;
      if (!pr) {
        return `<div class="imh-rp is-vide" style="--i:${i}"><span class="imh-rp-case"></span>${src}
          <div class="imh-rp-dest"><span class="imh-mini">${esc(L('rp_propose'))}</span><strong>${esc(L('rp_rien'))}</strong><small>${esc(L('rp_rien_suite'))}</small></div></div>`;
      }
      const on = r.retenus.has(n);
      return `<label class="imh-rp${on ? ' on' : ''} c-${pr.confiance}" style="--i:${i}">
        <input type="checkbox" class="imh-rp-cb" data-nom="${esc(n)}"${on ? ' checked' : ''}>
        <span class="imh-rp-case"><i class="fa-solid fa-check"></i></span>
        ${src}
        <div class="imh-rp-dest"><span class="imh-mini">${esc(L('rp_propose'))}</span><strong>${esc(pr.activite)}</strong>
          ${jauge(pr.confiance)}${pr.raison ? `<small>${esc(pr.raison)}</small>` : ''}</div>
      </label>`;
    }).join('');
    return `<div class="imh-rapport">
      <div class="imh-rp-tete">
        <span class="imh-ia-ic"><i class="fa-solid fa-wand-magic-sparkles"></i></span>
        <div><h3>${esc(L('rp_titre'))}</h3><p>${esc(P('rp_examinees', r.noms.length))} · ${esc(P('rp_rapprochees', trouves))}</p></div>
      </div>
      <p class="imh-rp-consigne"><i class="fa-solid fa-circle-info"></i>${esc(L('rp_consigne'))}</p>
      <div class="imh-rp-liste">${lignes}</div>
    </div>`;
  }

  function exemples(np, cle) {
    const vals = [];
    for (const l of np.lignes) {
      const v = String(l[cle] || '').trim();
      if (v && !vals.includes(v)) vals.push(v);
      if (vals.length >= 3) break;
    }
    return vals;
  }

  function blocLecture(np) {
    const tete = `<div class="imh-rp-tete">
        <span class="imh-ia-ic"><i class="fa-solid fa-wand-magic-sparkles"></i></span>
        <div><h3>${esc(L('lc_titre'))}</h3>${np.remarque ? `<p>${esc(np.remarque)}</p>` : ''}</div>
        ${np.type ? jauge(np.confiance) : ''}
      </div>`;
    if (!np.type) {
      return `<div class="imh-rapport">${tete}<div class="imh-vide"><i class="fa-regular fa-folder-open"></i>${esc(L('lc_rien'))}</div></div>`;
    }
    const champs = nature(np.type).champs;
    const lignes = champs.map(c => {
      const col = np.correspondance[c.cle];
      const trouve = col != null;
      const ex = trouve ? exemples(np, c.cle) : [];
      return `<div class="imh-lc-l${trouve ? '' : ' is-absent'}${c.requis && !trouve ? ' is-manque' : ''}">
        <span class="imh-lc-champ">${esc(c.label)}${c.requis ? '<em aria-hidden="true">*</em>' : ''}</span>
        <span class="imh-lc-col">${trouve ? esc(colonne(np, col)) : esc(L('lc_absent'))}</span>
        <span class="imh-lc-ex">${ex.map(x => `<span>${esc(x)}</span>`).join('')}</span>
      </div>`;
    }).join('');
    const manque = champs.filter(c => np.manquants.includes(c.cle)).map(c => c.label).join(', ');
    return `<div class="imh-rapport">
      ${tete}
      <p class="imh-rp-consigne"><i class="fa-solid fa-circle-info"></i>${esc(np.ligne_entete >= 0 ? F('lc_entete', { n: np.ligne_entete + 1 }) : L('lc_sans_entete'))} ${esc(L('lc_consigne'))}</p>
      <div class="imh-lc">
        <div class="imh-lc-l is-tete"><span>${esc(L('lc_champ'))}</span><span>${esc(L('lc_colonne'))}</span><span>${esc(L('lc_exemples'))}</span></div>
        ${lignes}
      </div>
      ${np.reconnu
        ? `<p class="imh-lc-bilan is-ok"><i class="fa-solid fa-circle-check"></i>${esc(P('lc_lignes', np.lignes.length))}</p>`
        : `<p class="imh-lc-bilan is-manque"><i class="fa-solid fa-triangle-exclamation"></i>${esc(np.erreur || F('lc_manque', { x: manque }))}</p>`}
      <p class="imh-nr-garantie"><i class="fa-solid fa-shield-halved"></i>${esc(L('garantie_ia'))}</p>
    </div>`;
  }

  function blocNonReconnu(p) {
    const ty = p.type;
    const champs = ty ? nature(ty).champs.filter(c => c.requis) : [];
    const enCours = S.occupe === 'ia';
    const manquent = champs.filter(c => p.manquants.includes(c.cle)).map(c => c.label).join(', ');
    const texte = p.erreur ? p.erreur : (!ty ? L('nr_texte_nature') : F('nr_texte', { x: manquent }));
    const attendu = champs.length ? `<div class="imh-nr-att">${champs.map(c => {
      const manque = p.manquants.includes(c.cle);
      return `<span class="imh-att ${manque ? 'manque' : 'ok'}"><i class="fa-solid ${manque ? 'fa-xmark' : 'fa-check'}"></i>${esc(c.label)}</span>`;
    }).join('')}</div>` : '';
    const actions = enCours
      ? `<div class="imh-ia-lit"><span class="imh-ia-ic is-anime"><i class="fa-solid fa-wand-magic-sparkles"></i></span><div><strong>${esc(L('ia_lit'))}</strong><span class="imh-ia-lignes"><i></i><i></i><i></i></span></div></div>`
      : `<div class="imh-nr-actions">
          ${CTX.ia ? `<button type="button" class="imh-btn-ia is-grand" data-action="organiser"><i class="fa-solid fa-wand-magic-sparkles"></i>${esc(L('organiser_ia'))}</button>` : ''}
          <a class="imh-btn-sec" href="/api/import/modele/${ty || 'multiple'}" download><i class="fa-solid fa-file-arrow-down"></i>${esc(L('modele'))}</a>
          ${S.type !== 'multiple' ? `<button type="button" class="imh-btn-sec" data-action="autre-fichier"><i class="fa-solid fa-arrow-rotate-left"></i>${esc(L('autre_fichier'))}</button>` : ''}
        </div>
        <p class="imh-nr-garantie"><i class="fa-solid ${CTX.ia ? 'fa-shield-halved' : 'fa-circle-info'}"></i>${esc(CTX.ia ? L('garantie_ia') : L('sans_ia'))}</p>`;
    return `<div class="imh-nr">
      <div class="imh-nr-tete">
        <span class="imh-nr-ic"><i class="fa-solid fa-table-cells-large"></i></span>
        <div><h3>${esc(ty ? L('nr_titre') : L('nr_titre_nature'))}</h3><p>${esc(texte)}</p></div>
      </div>
      ${attendu}
      ${apercuBrut(p)}
      ${actions}
    </div>`;
  }

  // Les premières lignes telles qu'elles sont dans le fichier, colonnes
  // repérées par leur lettre : c'est ce que l'IA regarde aussi.
  function apercuBrut(p) {
    const lignes = (p.echantillon || []).slice(0, 6);
    if (!lignes.length) return '';
    const n = Math.min(8, Math.max(...lignes.map(l => l.length)));
    const tete = `<thead><tr><th></th>${Array.from({ length: n }, (_, i) => `<th>${lettre(i)}</th>`).join('')}</tr></thead>`;
    const corps = lignes.map((l, i) => `<tr${i === p.ligne_entete ? ' class="is-entete"' : ''}><th>${i + 1}</th>${Array.from({ length: n }, (_, j) => `<td title="${esc(l[j] || '')}">${esc(l[j] || '')}</td>`).join('')}</tr>`).join('');
    return `<div class="imh-brut"><span class="imh-mini">${esc(L('apercu_fichier'))}</span><div class="imh-brut-t"><table>${tete}<tbody>${corps}</tbody></table></div></div>`;
  }

  function blocIgnoree() {
    return `<div class="imh-vide is-ignoree"><i class="fa-solid fa-eye-slash"></i>${esc(L('feuille_ignoree'))}</div>`;
  }

  function rail() {
    const items = S.parts.map(p => {
      const v = S.verifs[p.id];
      const etat = S.ignorees[p.id] ? L('rail_ignoree')
        : p.type === 'comptes' ? L('rail_comptes')
        : !p.type ? L('rail_nature')
        : !p.reconnu ? L('rail_organiser')
        : aConfirmer(p) ? L('rail_confirmer')
        : v ? P('rail_gardees', nbGardees(p)) : '…';
      const cl = [p.id === S.active ? 'ici' : '', S.ignorees[p.id] || p.type === 'comptes' ? 'is-ignoree' : '',
                  inclue(p) ? 'is-ok' : 'is-attente'].join(' ');
      const titre = p.type === 'comptes' ? L('cpt_rail') : (p.type ? nature(p.type).nom : L('nature_inconnue'));
      return `<button type="button" class="imh-rail-i ${cl}" data-part="${esc(p.id)}" style="--tc:${COULEUR[p.type] || '#94a3b8'}"${S.rapport || S.lecture ? ' disabled' : ''}>
        <span class="imh-rail-ic"><i class="fa-solid ${ICONE[p.type] || 'fa-question'}"></i></span>
        <span class="imh-rail-txt"><strong>${esc(titre)}</strong>
          <small>${esc(p.fichier)}${p.n_feuilles > 1 ? ' › ' + esc(p.feuille) : ''}</small></span>
        <span class="imh-rail-etat">${esc(etat)}</span>
      </button>`;
    }).join('');
    const plein = S.fichiers.length >= MAX_FICHIERS || S.rapport || S.lecture;
    return `<nav class="imh-rail" aria-label="${esc(L('feuilles'))}">
      <span class="imh-mini">${esc(P('n_feuilles', S.parts.length))}</span>
      ${items}
      ${plein ? '' : `<label class="imh-rail-plus"><input type="file" data-role="ajout" accept=".xlsx,.xlsm,.csv" multiple hidden><i class="fa-solid fa-plus"></i>${esc(L('ajouter_fichiers'))}</label>`}
    </nav>`;
  }

  // ── 4 · Bilan ──────────────────────────────────────────────────────
  // Deux feuilles d'une même nature font UN bilan : on lit le résultat par
  // nature, pas par fichier.
  function parNature(resultats) {
    const out = {};
    resultats.forEach(x => {
      const o = out[x.type] = out[x.type] || { type: x.type, par_carto: {} };
      Object.keys(x).forEach(k => { if (typeof x[k] === 'number') o[k] = (o[k] || 0) + x[k]; });
      Object.keys(x.par_carto || {}).forEach(c => { o.par_carto[c] = (o.par_carto[c] || 0) + x.par_carto[c]; });
    });
    return ORDRE.filter(t => out[t]).map(t => out[t]);
  }

  function ecranFin() {
    const r = S.resultat || { resultats: [], cibles: [] };
    const res = parNature(r.resultats);
    const total = res.reduce((n, x) => n + (x.crees || x.tasks_created || 0), 0);
    const ou = F('fin_dans', { x: (r.cibles || []).map(c => c.name).join(', ') });
    return `<div class="imh-fin">
      <div class="imh-fin-ic${total ? '' : ' is-neutre'}"><svg viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="24"/><path d="M15 27l7 7 15-16"/></svg></div>
      <h3>${esc(total ? L('fin_titre') : L('fin_rien_titre'))}</h3>
      <p class="imh-fin-sous">${esc(total ? ou : L('fin_rien'))}</p>
      <div class="imh-fin-blocs">${res.map(blocResultat).join('')}</div>
    </div>`;
  }

  function blocResultat(x, i) {
    let n, lib, details = [];
    if (x.type === 'taches') {
      n = x.tasks_created; lib = P('res_taches', n);
      if (x.tools_created) details.push(x.tools_created + ' ' + P('res_outils', x.tools_created));
      if (x.roles_created) details.push(x.roles_created + ' ' + P('res_roles', x.roles_created));
      if (x.competencies_created) details.push(x.competencies_created + ' ' + P('res_competences', x.competencies_created));
      if (x.activities_updated) details.push(x.activities_updated + ' ' + P('res_activites', x.activities_updated));
    } else {
      n = x.crees; lib = x.type === 'roles' ? P('res_roles', n) : P('res_outils', n);
      // Le détail par carto ne dit quelque chose qu'à partir de deux cartos :
      // pour une seule, le sous-titre l'a déjà nommée.
      const cartos = Object.keys(x.par_carto || {});
      if (cartos.length > 1) details = cartos.map(c => `${c} · ${x.par_carto[c]}`);
    }
    return `<div class="imh-res${n ? '' : ' is-zero'}" style="--tc:${COULEUR[x.type]};--i:${i}">
      <span class="imh-res-ic"><i class="fa-solid ${ICONE[x.type]}"></i></span>
      <div class="imh-res-txt"><b>${n}</b><span>${esc(lib)}</span>
        ${details.length ? `<small>${details.map(esc).join(' · ')}</small>` : ''}</div>
    </div>`;
  }

  // ── Pied ───────────────────────────────────────────────────────────
  function rendrePied() {
    if (S.quitter) {
      dom.pied.hidden = false;
      dom.pied.innerHTML = `<div class="imh-quitter"><i class="fa-solid fa-circle-question"></i><span>${esc(L('quitter_q'))}</span>
        <button type="button" class="imh-btn-sec" data-action="rester">${esc(L('rester'))}</button>
        <button type="button" class="imh-btn-danger" data-action="quitter">${esc(L('quitter'))}</button></div>`;
      return;
    }
    let g = '', d = '';
    if (S.ecran === 'depot') {
      g = `<button type="button" class="imh-btn-sec" data-action="retour"><i class="fa-solid fa-arrow-left"></i>${esc(L('retour_nature'))}</button>`;
    }
    if (S.ecran === 'revue' && S.rapport) {
      const n = S.rapport.retenus.size;
      g = `<button type="button" class="imh-btn-sec" data-action="rp-annuler"><i class="fa-solid fa-xmark"></i>${esc(L('annuler'))}</button>`;
      d = `<button type="button" class="imh-btn-ia" data-action="rp-appliquer"${n ? '' : ' disabled'}><i class="fa-solid fa-check"></i>${esc(P('rp_appliquer', n))}</button>`;
    } else if (S.ecran === 'revue' && S.lecture) {
      const np = S.lecture.part;
      g = `<button type="button" class="imh-btn-sec" data-action="lc-annuler"><i class="fa-solid fa-xmark"></i>${esc(L('annuler'))}</button>`;
      d = np.type ? `<button type="button" class="imh-btn-ia" data-action="lc-utiliser"${np.reconnu ? '' : ' disabled'}><i class="fa-solid fa-check"></i>${esc(L('lc_utiliser'))}</button>` : '';
    } else if (S.ecran === 'revue') {
      g = `<button type="button" class="imh-btn-sec" data-action="autre-fichier"><i class="fa-solid fa-arrow-left"></i>${esc(L('retour_fichier'))}</button>`;
      // Rien de lisible encore (fichier à organiser) : pas de bouton d'import
      // éteint qui laisserait croire qu'il manque seulement une case à cocher.
      if (S.parts.some(inclue)) {
        const n = totalGardees();
        const attente = Object.keys(S.enCours).length > 0;
        const pret = n > 0 && !attente && S.cibles.length && S.occupe !== 'import';
        d = `<span class="imh-pied-resume">${esc(resume(n))}</span>
          <button type="button" class="imh-btn-prim" data-action="importer"${pret ? '' : ' disabled'}>${S.occupe === 'import'
            ? `<i class="fa-solid fa-circle-notch fa-spin"></i>${esc(L('import_en_cours'))}`
            : `<i class="fa-solid fa-file-import"></i>${esc(libelleImport(n))}`}</button>`;
      }
    }
    if (S.ecran === 'fin') {
      g = `<button type="button" class="imh-btn-sec" data-action="encore"><i class="fa-solid fa-rotate-right"></i>${esc(L('encore'))}</button>`;
      d = `<button type="button" class="imh-btn-prim" data-action="fermer"><i class="fa-solid fa-check"></i>${esc(L('terminer'))}</button>`;
    }
    dom.pied.hidden = !g && !d;
    dom.pied.innerHTML = `<div class="imh-pied-g">${g}</div><div class="imh-pied-d">${d}</div>`;
  }

  function libelleImport(n) {
    if (S.type === 'multiple') return F('btn_multiple', { n });
    return { roles: P('btn_roles', n), taches: P('btn_taches', n), outils: P('btn_outils', n) }[S.type];
  }

  function resume(n) {
    if (!n) return L('rien_a_importer');
    const cibles = (CTX.cibles || []).filter(c => S.cibles.includes(c.id));
    return cibles.length === 1 ? F('resume_une', { x: cibles[0].name }) : P('resume_cartos', cibles.length);
  }

  // Après un clic de case : la ligne, les compteurs, le pied et le rail — pas
  // toute la liste : on ne perd ni la position, ni le focus.
  function majCase(p, i) {
    const v = S.verifs[p.id];
    if (!v) return;
    const l = v.lignes.find(x => x._i === i);
    const el = dom.corps.querySelector(`.imh-l[data-i="${i}"]`);
    if (l && el) {
      el.classList.toggle('is-off', exclus(p).has(i));
      const pas = el.querySelector('.imh-pas');
      if (pas) pas.outerHTML = pastille(p, l);
    }
    majCompteurs(p);
  }

  function majCompteurs(p) {
    rendrePied();
    const etat = dom.corps.querySelector(`.imh-rail-i[data-part="${CSS.escape(p.id)}"] .imh-rail-etat`);
    if (etat) etat.textContent = P('rail_gardees', nbGardees(p));
    const v = S.verifs[p.id];
    if (!v) return;
    const c = compter(p, v);
    const bloc = dom.corps.querySelector('.imh-tuiles');
    const filtre = S.filtres[p.id] || 'tous';
    const avant = bloc ? [...bloc.querySelectorAll('.imh-tuile')].map(b => b.dataset.filtre).join() : '';
    // Décocher une tâche fait naître « 1 tâche écartée » : une tuile qui
    // n'existait pas. On redessine alors la rangée, et la rangée seulement.
    if (bloc && avant !== categories(p, c, filtre).join()) {
      const focus = document.activeElement && document.activeElement.dataset.action === 'tout';
      bloc.outerHTML = tuiles(p, v, filtre);
      if (focus) dom.corps.querySelector('.imh-tout input')?.focus();
      return;
    }
    dom.corps.querySelectorAll('.imh-tuile').forEach(b => {
      const k = b.dataset.filtre;
      b.querySelector('b').textContent = c[k];
      b.querySelector('span').textContent = libTuile(k, p.type, c[k]);
    });
    const tout = dom.corps.querySelector('.imh-tout input');
    if (tout) tout.checked = gardees(p).length === v.lignes.filter(l => GARDABLES.has(l.statut)).length;
  }

  // ══════════════════════════════════════════════════════════════════
  //  Actions
  // ══════════════════════════════════════════════════════════════════
  function choisirType(ty) {
    S.type = ty;
    S.ecran = 'depot';
    S.erreur = null;
    rendre();
    const z = dom.corps.querySelector('.imh-zone');
    if (z) z.focus();
  }

  function reprendreFichier() {
    const { type, cibles, portee } = S;
    S = Object.assign(neuf(), { type, cibles, portee, ecran: 'depot' });
    rendre();
  }

  async function recevoir(liste) {
    if (S.occupe) return;
    const tous = Array.from(liste || []);
    const fichiers = tous.filter(f => EXT.test(f.name));
    if (!fichiers.length) {
      if (tous.length) { S.erreur = F('err_format_fichier', { x: tous[0].name }); rendre(); }
      return;
    }
    const multi = S.type === 'multiple';
    const lot = multi ? fichiers.slice(0, MAX_FICHIERS - S.fichiers.length) : fichiers.slice(0, 1);
    if (!lot.length) return;
    const base = multi ? S.fichiers.length : 0;
    S.occupe = 'lecture';
    S.enLecture = lot.map(f => f.name);
    S.erreur = tous.length > fichiers.length ? F('err_format_fichier', { x: tous.find(f => !EXT.test(f.name)).name }) : null;
    if (S.ecran !== 'revue') S.ecran = 'depot';
    rendre();
    try {
      const fd = new FormData();
      fd.append('type', S.type);
      lot.forEach(f => fd.append('fichiers', f));
      const rep = await envoyer('/api/import/lire', fd);
      rep.parts.forEach(p => {
        const i = Number(p.id.split(':')[0]);
        p.fichierIdx = base + i;
        p.id = `${base + i}:${p.feuille}`;
      });
      if (multi) {
        S.fichiers = S.fichiers.concat(lot);
        S.parts = S.parts.concat(rep.parts);
      } else {
        S.fichiers = lot;
        S.parts = rep.parts;
      }
      const echecs = rep.erreurs || [];
      S.occupe = null;
      if (!S.parts.length) {
        S.erreur = echecs.length ? `${echecs[0].fichier} — ${echecs[0].erreur}` : L('err_vide');
        return rendre();
      }
      if (echecs.length) S.erreur = echecs.map(e => `${e.fichier} — ${e.erreur}`).join(' · ');
      if (!S.active || !multi) S.active = (rep.parts.find(p => p.reconnu) || S.parts[0]).id;
      S.ecran = 'revue';
      rendre();
      await verifierTout();
    } catch (e) {
      S.occupe = null;
      S.erreur = e.message || L('err_reseau');
      rendre();
    }
  }

  // ⚠️ Une réponse lente ne doit jamais écraser une plus récente : chaque
  // vérification porte un jeton, seule la dernière demandée s'affiche.
  async function verifier(p) {
    if (!inclue(p)) return;
    if (!S.cibles.length) { delete S.verifs[p.id]; rendre(); return; }
    const jeton = S.jetons[p.id] = (S.jetons[p.id] || 0) + 1;
    S.enCours[p.id] = true;
    rendrePied();
    const zone = dom.corps.querySelector('.imh-liste-zone');
    if (zone && p.id === S.active) zone.classList.add('is-maj');
    try {
      const res = await envoyer('/api/import/verifier', {
        type: p.type, lignes: p.lignes, cibles: S.cibles, choix: S.choix[p.id] || {},
      }, true);
      if (jeton !== S.jetons[p.id]) return;
      S.verifs[p.id] = res;
    } catch (e) {
      if (jeton !== S.jetons[p.id]) return;
      S.erreur = e.message;
    }
    delete S.enCours[p.id];
    rendre();
    montrerRecents();
  }

  // Ce que l'IA vient de rattacher ne se perd pas dans la liste : on y amène
  // le regard, une fois.
  function montrerRecents() {
    if (!S.recents || !S.recents.defiler) return;
    const el = dom.corps.querySelector('.imh-g.is-recent');
    if (!el) return;
    S.recents.defiler = false;
    el.scrollIntoView({ block: 'center' });
  }

  async function verifierTout() {
    for (const ty of ORDRE) {
      await Promise.all(S.parts.filter(p => p.type === ty && inclue(p)).map(verifier));
    }
  }

  let minuterie = null;
  function planifier(fn) {
    clearTimeout(minuterie);
    minuterie = setTimeout(fn, 280);
  }

  function changerPortee(k) {
    const cibles = CTX.cibles || [];
    S.portee = k;
    if (k === 'active') {
      const a = cibles.find(c => c.active);
      S.cibles = a ? [a.id] : [];
    } else if (k === 'toutes') {
      S.cibles = cibles.map(c => c.id);
    } else if (!S.cibles.length && cibles[0]) {
      S.cibles = [cibles[0].id];
    }
    rendre();
    planifier(verifierTout);
  }

  function basculerCarto(id) {
    const i = S.cibles.indexOf(id);
    if (i >= 0) S.cibles.splice(i, 1); else S.cibles.push(id);
    rendre();
    planifier(verifierTout);
  }

  function remplacerPart(ancienne, nouvelle) {
    nouvelle.id = ancienne.id;
    nouvelle.fichierIdx = ancienne.fichierIdx;
    nouvelle.n_feuilles = ancienne.n_feuilles;
    S.parts[S.parts.indexOf(ancienne)] = nouvelle;
    delete S.verifs[ancienne.id];
    delete S.exclus[ancienne.id];
    delete S.choix[ancienne.id];
    delete S.parIA[ancienne.id];
    delete S.filtres[ancienne.id];
    delete S.seulIA[ancienne.id];
  }

  // L'IA lit la feuille ; sa lecture s'affiche et ATTEND qu'on l'accepte.
  async function organiser(p) {
    const f = S.fichiers[p.fichierIdx];
    if (!f || S.occupe) return;
    S.occupe = 'ia';
    S.erreur = null;
    rendre();
    try {
      const fd = new FormData();
      fd.append('type', S.type);
      fd.append('fichier', f);
      fd.append('feuille', p.feuille);
      fd.append('id', p.id);
      if (p.nature_choisie && CARTES.includes(p.type)) fd.append('comme', p.type);
      const rep = await envoyer('/api/import/organiser', fd);
      rep.part.nature_choisie = p.nature_choisie;
      S.lecture = { partId: p.id, part: rep.part };
    } catch (e) {
      S.erreur = e.message || L('err_ia');
    }
    S.occupe = null;
    rendre();
  }

  async function utiliserLecture() {
    const l = S.lecture;
    const p = l && S.parts.find(x => x.id === l.partId);
    S.lecture = null;
    if (!p || !l.part.reconnu) return rendre();
    remplacerPart(p, l.part);
    rendre();
    await verifier(l.part);
  }

  async function relireComme(p, ty) {
    const f = S.fichiers[p.fichierIdx];
    if (!f || S.occupe) return;
    if (ty === p.type && p.reconnu) {
      // La nature détectée était la bonne : on la confirme, rien à relire.
      p.nature_choisie = true;
      rendre();
      await verifier(p);
      return;
    }
    S.occupe = 'lecture-part';
    rendre();
    try {
      const fd = new FormData();
      fd.append('type', S.type);
      fd.append('fichiers', f);
      fd.append('feuille', p.feuille);
      fd.append('comme', ty);
      const rep = await envoyer('/api/import/lire', fd);
      const np = rep.parts[0];
      if (!np) throw new Error(L('err_vide'));
      np.nature_choisie = true;
      remplacerPart(p, np);
      S.occupe = null;
      rendre();
      if (inclue(np)) await verifier(np);
    } catch (e) {
      S.occupe = null;
      S.erreur = e.message;
      rendre();
    }
  }

  // L'IA propose des rattachements ; un compte rendu les montre AVANT qu'ils
  // ne touchent la liste. Ce dont elle doute arrive décoché.
  async function rapprocher(p) {
    const v = S.verifs[p.id];
    if (!v || S.occupe) return;
    const vus = examinees(p);
    const noms = v.groupes.filter(g => g.mode === 'a_rattacher' && !(g.activite_fichier in vus))
      .map(g => g.activite_fichier);
    if (!noms.length) return;
    const cle = S.cibles.join(',');
    S.occupe = 'rapprocher';
    rendre();
    try {
      const rep = await envoyer('/api/import/rapprocher', { noms, cibles: S.cibles }, true);
      const props = rep.propositions || {};
      S.rapport = {
        partId: p.id, noms, props,
        retenus: new Set(noms.filter(n => props[n] && props[n].confiance !== 'low')),
      };
      const ex = S.examen[p.id] && S.examen[p.id].cle === cle ? S.examen[p.id]
        : (S.examen[p.id] = { cle, props: {} });
      noms.forEach(n => { ex.props[n] = props[n] || null; });
    } catch (e) {
      S.erreur = e.message || L('err_ia');
    }
    S.occupe = null;
    rendre();
  }

  // On revient sur des propositions qu'on avait laissées : rien n'est
  // pré-coché, c'est un choix délibéré.
  function revoir(p) {
    const v = S.verifs[p.id];
    if (!v) return;
    const vus = examinees(p);
    const noms = v.groupes.filter(g => g.mode === 'a_rattacher' && vus[g.activite_fichier])
      .map(g => g.activite_fichier);
    if (!noms.length) return;
    const props = {};
    noms.forEach(n => { props[n] = vus[n]; });
    S.rapport = { partId: p.id, noms, props, retenus: new Set() };
    rendre();
  }

  function appliquerRapport() {
    const r = S.rapport;
    const p = r && S.parts.find(x => x.id === r.partId);
    S.rapport = null;
    if (!p) return rendre();
    const choix = S.choix[p.id] = S.choix[p.id] || {};
    const parIA = S.parIA[p.id] = S.parIA[p.id] || {};
    const appliques = [];
    r.retenus.forEach(n => {
      if (!r.props[n]) return;
      choix[n] = r.props[n].activite;
      parIA[n] = r.props[n];
      appliques.push(n);
    });
    S.recents = appliques.length ? { partId: p.id, noms: appliques, defiler: true } : null;
    rendre();
    verifier(p);
  }

  async function importer() {
    const parts = S.parts.filter(p => nbGardees(p) > 0).map(p => {
      const g = new Set(gardees(p));
      return { type: p.type, id: p.id, lignes: p.lignes.filter(l => g.has(l._i)), choix: S.choix[p.id] || {} };
    });
    if (!parts.length || S.occupe) return;
    S.occupe = 'import';
    S.erreur = null;
    rendrePied();
    dom.fenetre.classList.add('is-import');
    try {
      const rep = await envoyer('/api/import/importer', { parts, cibles: S.cibles }, true);
      S.resultat = rep;
      S.ecran = 'fin';
      document.dispatchEvent(new CustomEvent('optiq:import-termine', { detail: rep }));
    } catch (e) {
      S.erreur = e.message || L('err_import');
    }
    S.occupe = null;
    dom.fenetre.classList.remove('is-import');
    rendre();
  }

  // ══════════════════════════════════════════════════════════════════
  //  Événements — délégués une fois pour toutes, le contenu est redessiné
  // ══════════════════════════════════════════════════════════════════
  function clic(e) {
    const el = e.target.closest('button, [data-action]');
    if (!el || !dom.racine.contains(el) || el.disabled) return;
    const ds = el.dataset;
    if (ds.action === 'fermer') return fermer();
    if (ds.type && S.ecran === 'choix') return choisirType(ds.type);
    if (ds.portee) return changerPortee(ds.portee);
    if (ds.carto) return basculerCarto(Number(ds.carto));
    if (ds.part) { S.active = ds.part; S.recents = null; return rendre(); }
    const p = partActive();
    if (ds.filtre) { S.filtres[p.id] = ds.filtre; return rendre(); }
    if (ds.comme) return relireComme(p, ds.comme);
    switch (ds.action) {
      case 'erreur-ok': S.erreur = null; return rendre();
      case 'retour': S.type = null; S.ecran = 'choix'; S.erreur = null; return rendre();
      case 'autre-fichier': return reprendreFichier();
      case 'organiser': return organiser(p);
      case 'lc-utiliser': return utiliserLecture();
      case 'lc-annuler': S.lecture = null; return rendre();
      case 'rapprocher': return rapprocher(p);
      case 'rp-appliquer': return appliquerRapport();
      case 'rp-annuler': S.rapport = null; return rendre();
      case 'seul-ia': S.seulIA[p.id] = !S.seulIA[p.id]; return rendre();
      case 'revoir': return revoir(p);
      case 'ignorer':
        S.ignorees[p.id] = !S.ignorees[p.id];
        rendre();
        if (!S.ignorees[p.id]) verifier(p);
        return;
      case 'importer': return importer();
      case 'encore': {
        const { cibles, portee } = S;
        S = Object.assign(neuf(), { cibles, portee });
        return rendre();
      }
      case 'rester': S.quitter = false; return rendrePied();
      case 'quitter': return fermer(true);
      default:
    }
  }

  function changement(e) {
    const el = e.target;
    if (el.id === 'imh-input' || el.dataset.role === 'ajout') {
      recevoir(el.files);
      el.value = '';
      return;
    }
    const p = partActive();
    if (!p) return;
    if (el.classList.contains('imh-rp-cb') && S.rapport) {
      if (el.checked) S.rapport.retenus.add(el.dataset.nom); else S.rapport.retenus.delete(el.dataset.nom);
      el.closest('.imh-rp').classList.toggle('on', el.checked);
      return rendrePied();
    }
    if (el.classList.contains('imh-cb')) {
      const i = Number(el.dataset.i);
      if (el.checked) exclus(p).delete(i); else exclus(p).add(i);
      return majCase(p, i);
    }
    if (el.dataset.action === 'tout') {
      const v = S.verifs[p.id];
      if (!v) return;
      const ex = exclus(p);
      v.lignes.filter(l => GARDABLES.has(l.statut)).forEach(l => (el.checked ? ex.delete(l._i) : ex.add(l._i)));
      return rendre();
    }
    if (el.classList.contains('imh-sel')) {
      const choix = S.choix[p.id] = S.choix[p.id] || {};
      if (el.value === '__ignorer__') choix[el.dataset.groupe] = '';
      else if (el.value) choix[el.dataset.groupe] = el.value;
      else delete choix[el.dataset.groupe];
      // Un choix fait à la main n'est plus « rattaché par l'IA ».
      if (S.parIA[p.id]) delete S.parIA[p.id][el.dataset.groupe];
      return verifier(p);
    }
  }

  const cibleDepot = e => e.target.closest && e.target.closest('.imh-zone, .imh-rail-plus');

  function brancher() {
    dom.racine.addEventListener('click', clic);
    dom.racine.addEventListener('change', changement);
    // ⚠️ Un fichier lâché à côté de la zone ouvrirait le navigateur dessus et
    // ferait quitter la page : on l'intercepte partout dans la fenêtre.
    dom.racine.addEventListener('dragover', e => {
      e.preventDefault();
      const z = cibleDepot(e);
      if (z && !S.occupe) z.classList.add('survol');
    });
    dom.racine.addEventListener('dragleave', e => {
      const z = cibleDepot(e);
      if (z && !z.contains(e.relatedTarget)) z.classList.remove('survol');
    });
    dom.racine.addEventListener('drop', e => {
      e.preventDefault();
      const z = cibleDepot(e);
      if (z) z.classList.remove('survol');
      if (z || S.ecran === 'depot') recevoir(e.dataTransfer.files);
    });
    dom.corps.addEventListener('keydown', e => {
      const z = e.target.closest('.imh-zone');
      if (z && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault();
        z.querySelector('input').click();
      }
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !dom.racine.hidden) fermer();
    });
  }

  function init() {
    dom.racine = document.getElementById('imh');
    if (!dom.racine) return;
    dom.fenetre = dom.racine.querySelector('.imh-fenetre');
    dom.corps = document.getElementById('imh-corps');
    dom.pied = document.getElementById('imh-pied');
    dom.etapes = document.getElementById('imh-etapes');
    dom.sous = document.getElementById('imh-sous');
    dom.logo = document.getElementById('imh-logo');
    brancher();
    const declencheur = document.getElementById('btn-import-full');
    if (declencheur) declencheur.addEventListener('click', ouvrir);
    window.OptiqImport = { ouvrir };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
