/* ════════════════════════════════════════════════════════════════════
   Importer des données — la fenêtre d'import de la page Carte.

   Quatre natures (rôles, collaborateurs, tâches, outils) et un import
   multiple. Les règles vivent côté serveur (Code/routes/import_hub.py) ;
   ici on les MONTRE : choisir → déposer → vérifier → importer.

   ⚠️ Les mots de passe d'un fichier de collaborateurs ne partent jamais à la
   vérification (on n'envoie que leur longueur, masquée) et le serveur ne les
   renvoie pas : les lignes envoyées à l'import sont celles de la LECTURE,
   filtrées par ce que l'écran garde.
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
  const COULEUR = { roles: '#059669', users: '#e11d48', taches: '#7c3aed', outils: '#ea580c',
                    multiple: '#0d9488' };
  const ICONE = { roles: 'fa-user-tie', users: 'fa-users', taches: 'fa-list-check',
                  outils: 'fa-screwdriver-wrench', multiple: 'fa-layer-group' };
  const CARTES = ['roles', 'users', 'taches', 'outils'];
  const ORDRE = ['roles', 'outils', 'users', 'taches'];
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
      exclus: {}, choix: {}, iaActivites: {}, ignorees: {}, filtres: {},
      active: null, cibles: [], portee: 'active', options: { creer_roles: false },
      occupe: null, erreur: null, resultat: null, quitter: false, ecranRendu: null,
    };
  }

  // ── Petits outils ──────────────────────────────────────────────────
  const nature = ty => (CTX && CTX.natures && CTX.natures[ty]) || { champs: [] };
  const partActive = () => S.parts.find(p => p.id === S.active) || S.parts[0];
  // ⚠️ Une feuille dont la nature est AMBIGUË (« Nom | Description » : des
  // rôles ou des outils ?) n'est pas importée tant qu'on ne l'a pas dite :
  // « Tout importer » aurait sinon créé des presses à injecter comme rôles.
  const aConfirmer = p => !!(p && p.ambigu && !p.nature_choisie);
  const inclue = p => !!(p && p.type && p.reconnu && !S.ignorees[p.id] && !aConfirmer(p));
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
  const seulementComptes = () => S.parts.filter(inclue).every(p => p.type === 'users');

  function usersAvecRole() {
    return S.parts.some(p => p.type === 'users' && inclue(p) && p.lignes.some(l => l.role));
  }

  // Les rôles qu'un import multiple va créer : un collaborateur peut les
  // recevoir, ils existeront au moment de l'écriture (l'ordre y veille).
  function rolesPrevus() {
    const noms = [];
    S.parts.filter(p => p.type === 'roles' && inclue(p)).forEach(p => {
      const g = new Set(gardees(p));
      p.lignes.forEach(l => { if (g.has(l._i) && l.nom) noms.push(l.nom); });
    });
    return noms;
  }

  function teinte(texte) {
    let h = 0;
    for (const c of String(texte || '')) h = (h * 31 + c.charCodeAt(0)) % 360;
    return h;
  }
  function initiales(l) {
    const i = ((l.prenom || '')[0] || '') + ((l.nom || '')[0] || '');
    return (i || (l.email || '?')[0]).toUpperCase();
  }
  function libStatut(s) {
    return { user: L('statut_user'), champion: L('statut_champion'),
             coordinateur: L('statut_coordinateur'), admin: L('statut_admin') }[s] || s;
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
    dom.corps.innerHTML = '';     // les mots de passe provisoires ne restent pas dans la page
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
    dom.fenetre.style.setProperty('--tc', COULEUR[S.type] || '#db2777');
    dom.fenetre.dataset.ecran = S.ecran;
    rendreTete();
    const ecran = { choix: ecranChoix, depot: ecranDepot, revue: ecranRevue, fin: ecranFin }[S.ecran];
    dom.corps.innerHTML = erreurHtml() + ecran();
    rendrePied();
    dom.corps.scrollTop = S.ecranRendu === S.ecran ? haut : 0;
    S.ecranRendu = S.ecran;
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
      revue: L('sous_revue'),
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
        `<li style="--i:${i + 5}"><i class="fa-solid ${ic}"></i><span>${esc(txt)}</span></li>`).join('')}</ul>
    </div>`;
  }

  const puce = c => `<span class="imh-puce${c.requis ? ' is-requis' : ''}">${esc(c.label)}</span>`;

  function carte(ty, i) {
    const n = nature(ty), ok = !!CTX.droits[ty];
    const verrou = ty === 'users' ? L('verrou_comptes') : L('verrou_cartos');
    return `<button type="button" class="imh-carte" data-type="${ty}" style="--tc:${COULEUR[ty]};--i:${i}"${ok ? '' : ' disabled'}>
      <span class="imh-carte-haut">
        <span class="imh-carte-ic"><i class="fa-solid ${ICONE[ty]}"></i></span>
        <span class="imh-carte-go" aria-hidden="true"><i class="fa-solid fa-arrow-right"></i></span>
      </span>
      <span class="imh-carte-t">${esc(n.nom)}</span>
      <span class="imh-carte-d">${esc(n.desc)}</span>
      <span class="imh-carte-champs">${n.champs.map(puce).join('')}</span>
      <span class="imh-carte-portee"><i class="fa-solid ${ty === 'users' ? 'fa-globe' : 'fa-map-location-dot'}"></i>${esc(n.portee)}</span>
      ${ok ? '' : `<span class="imh-carte-verrou"><i class="fa-solid fa-lock"></i>${esc(verrou)}</span>`}
    </button>`;
  }

  function carteMultiple() {
    const n = nature('multiple'), ok = !!CTX.droits.multiple;
    const ics = CARTES.map(ty => `<span style="--tc:${COULEUR[ty]}"><i class="fa-solid ${ICONE[ty]}"></i></span>`).join('');
    return `<button type="button" class="imh-carte imh-carte--multi" data-type="multiple" style="--tc:${COULEUR.multiple};--i:4"${ok ? '' : ' disabled'}>
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
      return `<div class="imh-revue" style="--tc:${COULEUR[p.type]}">
        ${tetePart(p)}
        ${p.reconnu ? blocSource(p) + blocPortee() + blocListe(p) : blocNonReconnu(p)}
      </div>`;
    }
    return `<div class="imh-revue is-multi">
      ${blocPortee()}
      <div class="imh-split">
        ${rail()}
        <div class="imh-part" style="--tc:${p.type ? COULEUR[p.type] : '#94a3b8'}">
          ${tetePart(p)}
          ${S.ignorees[p.id] ? blocIgnoree()
            : aConfirmer(p) ? blocAmbigu(p) + blocSource(p)
            : (p.type && p.reconnu ? blocSource(p) + blocListe(p) : blocNonReconnu(p))}
        </div>
      </div>
    </div>`;
  }

  function tetePart(p) {
    const multi = S.type === 'multiple';
    const feuille = p.n_feuilles > 1 ? ` <span class="imh-tp-feuille">› ${esc(p.feuille)}</span>` : '';
    const compte = p.reconnu ? ` <span class="imh-tp-n">· ${esc(P('n_lignes', p.lignes.length))}</span>` : '';
    const action = multi
      ? `<button type="button" class="imh-btn-lien" data-action="ignorer"><i class="fa-solid ${S.ignorees[p.id] ? 'fa-rotate-left' : 'fa-eye-slash'}"></i>${esc(S.ignorees[p.id] ? L('reprendre_feuille') : L('ignorer_feuille'))}</button>`
      : (p.reconnu ? `<button type="button" class="imh-btn-lien" data-action="autre-fichier"><i class="fa-solid fa-arrow-rotate-left"></i>${esc(L('autre_fichier'))}</button>` : '');
    return `<div class="imh-tp">
      <span class="imh-tp-ic"><i class="fa-solid ${p.type ? ICONE[p.type] : 'fa-question'}"></i></span>
      <div class="imh-tp-txt">
        <strong>${esc(p.type ? nature(p.type).nom : L('nature_inconnue'))}</strong>
        <span class="imh-tp-src"><i class="fa-regular fa-file-excel"></i>${esc(p.fichier)}${feuille}${compte}</span>
      </div>
      ${action}
    </div>
    ${multi && !S.ignorees[p.id] ? choixNature(p) : ''}`;
  }

  // Import multiple : la nature se corrige d'un clic, la feuille est relue.
  function choixNature(p) {
    const doute = aConfirmer(p);
    const boutons = CARTES.map(ty => {
      const on = p.type === ty && !doute;
      const ok = CTX.droits[ty] && !S.occupe;
      return `<button type="button" class="imh-nat${on ? ' on' : ''}" data-comme="${ty}" style="--tc:${COULEUR[ty]}"${on || !ok ? ' disabled' : ''} aria-pressed="${on}"><i class="fa-solid ${ICONE[ty]}"></i>${esc(nature(ty).nom)}</button>`;
    }).join('');
    return `<div class="imh-nats"><span class="imh-mini">${esc(L('feuille_contient'))}</span>${boutons}</div>`;
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

  function colonne(p, i) {
    const titre = p.ligne_entete >= 0 && p.entetes ? p.entetes[i] : '';
    // « … » en français, “…” en anglais : les guillemets suivent la langue.
    return titre ? F('citation', { x: titre }) : F('colonne', { x: lettre(i) });
  }

  function blocSource(p) {
    const ia = p.source === 'IA';
    const champs = nature(p.type).champs;
    const maps = champs.filter(c => p.correspondance[c.cle] != null).map(c =>
      `<span class="imh-map"><span class="imh-map-col">${esc(colonne(p, p.correspondance[c.cle]))}</span><i class="fa-solid fa-arrow-right"></i><span class="imh-map-f">${esc(c.label)}</span></span>`);
    if (p.nom_complet != null) {
      maps.unshift(`<span class="imh-map"><span class="imh-map-col">${esc(colonne(p, p.nom_complet))}</span><i class="fa-solid fa-arrow-right"></i><span class="imh-map-f">${esc(L('prenom_et_nom'))}</span></span>`);
    }
    const conf = ia ? `<span class="imh-conf c-${p.confiance || 'medium'}">${esc({ high: L('conf_high'), medium: L('conf_medium'), low: L('conf_low') }[p.confiance || 'medium'])}</span>` : '';
    return `<div class="imh-source ${ia ? 'is-ia' : 'is-fichier'}">
      <div class="imh-source-t">
        <span class="imh-source-ic"><i class="fa-solid ${ia ? 'fa-wand-magic-sparkles' : 'fa-circle-check'}"></i></span>
        <strong>${esc(ia ? L('source_ia') : L('source_fichier'))}</strong>${conf}
      </div>
      ${ia && p.remarque ? `<p class="imh-source-rq">${esc(p.remarque)}</p>` : ''}
      <div class="imh-maps">${maps.join('')}</div>
      ${ia ? `<p class="imh-source-note"><i class="fa-solid fa-shield-halved"></i>${esc(L('garantie_ia'))}</p>` : ''}
    </div>`;
  }

  function bouton(k, ic, lib) {
    const on = S.portee === k;
    return `<button type="button" role="radio" class="imh-seg-b${on ? ' on' : ''}" aria-checked="${on}" data-portee="${k}"><i class="fa-solid ${ic}"></i><span>${esc(lib)}</span></button>`;
  }

  function blocPortee() {
    const cibles = CTX.cibles || [];
    const types = new Set(S.parts.filter(inclue).map(p => p.type));
    if (!types.size) return '';
    const cartos = [...types].some(t => t !== 'users') || usersAvecRole();
    if (!cartos) {
      return `<section class="imh-portee is-seule"><span class="imh-portee-ic"><i class="fa-solid fa-globe"></i></span><p>${esc(L('portee_instance'))}</p></section>`;
    }
    if (!cibles.length) {
      return `<section class="imh-portee is-bloque"><span class="imh-portee-ic"><i class="fa-solid fa-lock"></i></span><p>${esc(L('portee_aucune'))}</p></section>`;
    }
    const texte = S.type === 'multiple' ? L('portee_multiple')
      : { roles: L('portee_roles'), outils: L('portee_outils'), taches: L('portee_taches'),
          users: L('portee_users') }[S.type];
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
    const users = types.has('users') && usersAvecRole()
      ? `<label class="imh-bascule"><input type="checkbox" data-option="creer_roles"${S.options.creer_roles ? ' checked' : ''}><span class="imh-bascule-rail"><span></span></span><span>${esc(L('opt_creer_roles'))}</span></label>`
      : '';
    return `<section class="imh-portee">
      <div class="imh-portee-tete">
        <span class="imh-portee-ic"><i class="fa-solid fa-location-crosshairs"></i></span>
        <div class="imh-portee-txt"><h4>${esc(L('portee_titre'))}</h4><p>${esc(texte)}</p></div>
        ${seg}
      </div>
      ${liste}${users}
    </section>`;
  }

  function blocListe(p) {
    const v = S.verifs[p.id];
    if (p.type !== 'users' && !S.cibles.length) {
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

  function tuiles(p, v, filtre) {
    const t = v.totaux;
    const defs = [
      ['tous', v.lignes.length, L('f_tous')],
      ['nouveau', t.nouveau, L('f_nouveau')],
      ['partiel', t.partiel, L('f_partiel')],
      ['present', t.present, L('f_present')],
      ['a_rattacher', t.a_rattacher, L('f_a_rattacher')],
      ['ignore', t.ignore, L('f_ignore')],
      ['invalide', t.invalide, L('f_invalide')],
    ].filter(([k, n]) => n > 0 || k === 'tous' || k === 'nouveau');
    const eligibles = v.lignes.filter(l => GARDABLES.has(l.statut)).length;
    const tout = eligibles
      ? `<label class="imh-tout"><input type="checkbox" data-action="tout"${gardees(p).length === eligibles ? ' checked' : ''}><span>${esc(L('tout_garder'))}</span></label>`
      : '';
    return `<div class="imh-tuiles">
      ${defs.map(([k, n, lib]) => `<button type="button" class="imh-tuile t-${k}${filtre === k ? ' on' : ''}" data-filtre="${k}" aria-pressed="${filtre === k}"><b>${n}</b><span>${esc(lib)}</span></button>`).join('')}
      ${tout}
    </div>`;
  }

  function listePlate(p, v, filtre) {
    const lignes = v.lignes.filter(l => filtre === 'tous' || l.statut === filtre);
    if (!lignes.length) return `<div class="imh-vide">${esc(L('filtre_vide'))}</div>`;
    return `<div class="imh-liste">${lignes.map(l => ligne(p, l)).join('')}</div>`;
  }

  function ligne(p, l) {
    const gardable = GARDABLES.has(l.statut);
    const garde = gardable && !exclus(p).has(l._i);
    return `<div class="imh-l st-${l.statut}${garde ? '' : ' is-off'}">
      <input type="checkbox" class="imh-cb" data-i="${l._i}"${garde ? ' checked' : ''}${gardable ? '' : ' disabled'} aria-label="${esc(L('garder'))}">
      <div class="imh-l-c">${contenu(p.type, l)}${notes(l)}</div>
      ${pastille(l)}
    </div>`;
  }

  function contenu(ty, l) {
    if (ty === 'users') {
      const nom = [l.prenom, l.nom].filter(Boolean).join(' ');
      const puces = (l.statut_compte ? `<span class="imh-chip c-statut">${esc(libStatut(l.statut_compte))}</span>` : '')
        + (l.role ? `<span class="imh-chip"><i class="fa-solid fa-user-tie"></i>${esc(l.role)}</span>` : '');
      return `<span class="imh-av" style="--h:${teinte(l.email || nom)}">${esc(initiales(l))}</span>
        <span class="imh-l-t"><strong>${esc(nom || '—')}</strong><span class="imh-l-s">${esc(l.email || '—')}</span></span>
        ${puces ? `<span class="imh-l-puces">${puces}</span>` : ''}`;
    }
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
      out.push(`<span class="imh-note n-info">${esc(F('partiel_detail', { n: l.n_nouveau, total: l.n_nouveau + l.n_deja }))}</span>`);
    }
    if (l.avertissement) out.push(`<span class="imh-note n-warn"><i class="fa-solid fa-triangle-exclamation"></i>${esc(l.avertissement)}</span>`);
    if (l.info) out.push(`<span class="imh-note n-info"><i class="fa-solid fa-circle-info"></i>${esc(l.info)}</span>`);
    return out.length ? `<span class="imh-notes">${out.join('')}</span>` : '';
  }

  function pastille(l) {
    const cfg = {
      nouveau: ['fa-plus', L('st_nouveau')],
      partiel: ['fa-circle-half-stroke', L('st_partiel')],
      present: ['fa-check', L('st_present')],
      invalide: ['fa-triangle-exclamation', L('st_invalide')],
      a_rattacher: ['fa-link-slash', L('st_a_rattacher')],
      ignore: ['fa-eye-slash', L('st_ignore')],
    }[l.statut] || ['fa-circle', l.statut];
    return `<span class="imh-pas st-${l.statut}"><i class="fa-solid ${cfg[0]}"></i>${esc(cfg[1])}</span>`;
  }

  // Les tâches se lisent par activité : c'est à l'activité qu'on les rattache.
  function listeTaches(p, v, filtre) {
    const restants = v.groupes.filter(g => g.mode === 'a_rattacher').map(g => g.activite_fichier);
    const barre = restants.length ? barreRapprocher(p, restants.length) : '';
    const groupes = v.groupes.map((g, i) => groupe(p, g, i, filtre, v)).join('');
    return `${barre}<div class="imh-groupes">${groupes || `<div class="imh-vide">${esc(L('filtre_vide'))}</div>`}</div>`;
  }

  function barreRapprocher(p, n) {
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

  function groupe(p, g, i, filtre, v) {
    const lignes = g.lignes.filter(l => filtre === 'tous' || l.statut === filtre);
    if (!lignes.length) return '';
    const ia = (S.iaActivites[p.id] || {})[g.activite_fichier];
    const meta = [
      g.garant ? `<span class="imh-chip c-garant"><i class="fa-solid fa-shield-halved"></i>${esc(F('garant', { x: g.garant }))}</span>` : '',
      `<span class="imh-g-n">${esc(P('n_taches', g.lignes.length))}</span>`,
      g.choix && g.n_cibles > 1 ? `<span class="imh-g-n">${esc(F('dans_n_cartos', { n: g.n_cartos, total: g.n_cibles }))}</span>` : '',
    ].join('');
    const hesite = ia && ia.confiance === 'low' && g.mode === 'a_rattacher'
      ? `<button type="button" class="imh-suggest" data-action="suggestion" data-groupe="${esc(g.activite_fichier)}"><i class="fa-solid fa-wand-magic-sparkles"></i>${esc(F('ia_hesite', { x: ia.activite }))}</button>`
      : '';
    return `<section class="imh-g m-${g.mode}" style="--i:${Math.min(i, 12)}">
      <div class="imh-g-tete">
        <div class="imh-g-src"><span class="imh-mini">${esc(L('dans_fichier'))}</span><strong>${esc(g.activite_fichier || L('sans_activite'))}</strong></div>
        <i class="fa-solid fa-arrow-right-long imh-g-fleche" aria-hidden="true"></i>
        <div class="imh-g-dest"><span class="imh-mini">${esc(L('dans_carto'))}</span>
          <div class="imh-g-choix">${selectActivite(g, v)}${badgeMode(g, ia)}</div>${hesite}
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

  function badgeMode(g, ia) {
    if (ia && g.mode === 'manuel' && ia.activite === g.choix) {
      const sur = ia.confiance === 'high';
      return `<span class="imh-bm b-ia${sur ? '' : ' is-doute'}" title="${esc(ia.raison)}"><i class="fa-solid fa-wand-magic-sparkles"></i>${esc(sur ? L('ia_sure') : L('ia_a_verifier'))}</span>`;
    }
    const top = g.possibles[0];
    const cfg = {
      exact: ['fa-equals', L('mode_exact')],
      proche: ['fa-wave-square', F('mode_proche', { x: top ? pourcent(top.score) : '' })],
      manuel: ['fa-hand-pointer', L('mode_manuel')],
      a_rattacher: ['fa-link-slash', L('mode_a_rattacher')],
      ignore: ['fa-eye-slash', L('mode_ignore')],
    }[g.mode];
    return cfg ? `<span class="imh-bm b-${g.mode}"><i class="fa-solid ${cfg[0]}"></i>${esc(cfg[1])}</span>` : '';
  }

  function blocNonReconnu(p) {
    const ty = p.type;
    const champs = ty ? nature(ty).champs.filter(c => c.requis) : [];
    const enCours = S.occupe === 'ia';
    const titre = !ty ? L('nr_titre_nature') : (p.source === 'IA' ? L('nr_titre_ia') : L('nr_titre'));
    const manquent = champs.filter(c => p.manquants.includes(c.cle)).map(c => c.label).join(', ');
    const texte = p.erreur ? p.erreur
      : (p.source === 'IA' && p.remarque) ? p.remarque
      : (!ty ? L('nr_texte_nature') : F('nr_texte', { x: manquent }));
    const attendu = champs.length ? `<div class="imh-nr-att">${champs.map(c => {
      const manque = p.manquants.includes(c.cle);
      return `<span class="imh-att ${manque ? 'manque' : 'ok'}"><i class="fa-solid ${manque ? 'fa-xmark' : 'fa-check'}"></i>${esc(c.label)}</span>`;
    }).join('')}</div>` : '';
    const actions = enCours
      ? `<div class="imh-ia-lit"><span class="imh-ia-ic is-anime"><i class="fa-solid fa-wand-magic-sparkles"></i></span><div><strong>${esc(L('ia_lit'))}</strong><span class="imh-ia-lignes"><i></i><i></i><i></i></span></div></div>`
      : `<div class="imh-nr-actions">
          ${CTX.ia ? `<button type="button" class="imh-btn-ia is-grand" data-action="organiser"><i class="fa-solid fa-wand-magic-sparkles"></i>${esc(p.source === 'IA' ? L('ia_reessayer') : L('organiser_ia'))}</button>` : ''}
          <a class="imh-btn-sec" href="/api/import/modele/${ty || 'multiple'}" download><i class="fa-solid fa-file-arrow-down"></i>${esc(L('modele'))}</a>
          ${S.type !== 'multiple' ? `<button type="button" class="imh-btn-sec" data-action="autre-fichier"><i class="fa-solid fa-arrow-rotate-left"></i>${esc(L('autre_fichier'))}</button>` : ''}
        </div>
        <p class="imh-nr-garantie"><i class="fa-solid ${CTX.ia ? 'fa-shield-halved' : 'fa-circle-info'}"></i>${esc(CTX.ia ? L('garantie_ia') : L('sans_ia'))}</p>`;
    return `<div class="imh-nr">
      <div class="imh-nr-tete">
        <span class="imh-nr-ic"><i class="fa-solid fa-table-cells-large"></i></span>
        <div><h3>${esc(titre)}</h3><p>${esc(texte)}</p></div>
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
        : !p.type ? L('rail_nature')
        : !p.reconnu ? L('rail_organiser')
        : aConfirmer(p) ? L('rail_confirmer')
        : v ? P('rail_gardees', nbGardees(p)) : '…';
      const cl = [p.id === S.active ? 'ici' : '', S.ignorees[p.id] ? 'is-ignoree' : '',
                  inclue(p) ? 'is-ok' : 'is-attente'].join(' ');
      return `<button type="button" class="imh-rail-i ${cl}" data-part="${esc(p.id)}" style="--tc:${p.type ? COULEUR[p.type] : '#94a3b8'}">
        <span class="imh-rail-ic"><i class="fa-solid ${p.type ? ICONE[p.type] : 'fa-question'}"></i></span>
        <span class="imh-rail-txt"><strong>${esc(p.type ? nature(p.type).nom : L('nature_inconnue'))}</strong>
          <small>${esc(p.fichier)}${p.n_feuilles > 1 ? ' › ' + esc(p.feuille) : ''}</small></span>
        <span class="imh-rail-etat">${esc(etat)}</span>
      </button>`;
    }).join('');
    const plein = S.fichiers.length >= MAX_FICHIERS;
    return `<nav class="imh-rail" aria-label="${esc(L('feuilles'))}">
      <span class="imh-mini">${esc(P('n_feuilles', S.parts.length))}</span>
      ${items}
      ${plein ? '' : `<label class="imh-rail-plus"><input type="file" data-role="ajout" accept=".xlsx,.xlsm,.csv" multiple hidden><i class="fa-solid fa-plus"></i>${esc(L('ajouter_fichiers'))}</label>`}
    </nav>`;
  }

  // ── 4 · Bilan ──────────────────────────────────────────────────────
  // Deux feuilles de collaborateurs font UN bilan de comptes : on lit le
  // résultat par nature, pas par fichier.
  function parNature(resultats) {
    const out = {};
    resultats.forEach(x => {
      const o = out[x.type] = out[x.type] || { type: x.type, par_carto: {}, identifiants: [] };
      Object.keys(x).forEach(k => { if (typeof x[k] === 'number') o[k] = (o[k] || 0) + x[k]; });
      Object.keys(x.par_carto || {}).forEach(c => { o.par_carto[c] = (o.par_carto[c] || 0) + x.par_carto[c]; });
      o.identifiants = o.identifiants.concat(x.identifiants || []);
    });
    return ORDRE.filter(t => out[t]).map(t => out[t]);
  }

  function ecranFin() {
    const r = S.resultat || { resultats: [], cibles: [] };
    const res = parNature(r.resultats);
    const total = res.reduce((n, x) => n + (x.crees || x.tasks_created || 0), 0);
    const ids = [].concat(...res.map(x => x.identifiants));
    const ou = r.cibles && r.cibles.length && res.some(x => x.type !== 'users')
      ? F('fin_dans', { x: r.cibles.map(c => c.name).join(', ') }) : L('fin_instance');
    return `<div class="imh-fin">
      <div class="imh-fin-ic${total ? '' : ' is-neutre'}"><svg viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="24"/><path d="M15 27l7 7 15-16"/></svg></div>
      <h3>${esc(total ? L('fin_titre') : L('fin_rien_titre'))}</h3>
      <p class="imh-fin-sous">${esc(total ? ou : L('fin_rien'))}</p>
      <div class="imh-fin-blocs">${res.map(blocResultat).join('')}</div>
      ${ids.length ? blocIdentifiants(ids) : ''}
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
    } else if (x.type === 'users') {
      n = x.crees; lib = P('res_comptes', n);
      if (x.roles_attribues) details.push(x.roles_attribues + ' ' + P('res_attributions', x.roles_attribues));
      if (x.roles_crees) details.push(x.roles_crees + ' ' + P('res_roles', x.roles_crees));
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

  function blocIdentifiants(ids) {
    const lignes = ids.map(x => `<tr><td>${esc([x.prenom, x.nom].filter(Boolean).join(' '))}</td><td>${esc(x.email)}</td><td><code>${esc(x.mot_de_passe)}</code></td></tr>`).join('');
    return `<div class="imh-ids">
      <div class="imh-ids-tete">
        <span class="imh-ids-ic"><i class="fa-solid fa-key"></i></span>
        <div><strong>${esc(P('ids_titre', ids.length))}</strong><p>${esc(L('ids_texte'))}</p></div>
        <button type="button" class="imh-btn-prim is-petit" data-action="csv"><i class="fa-solid fa-download"></i>${esc(L('ids_csv'))}</button>
      </div>
      <div class="imh-ids-t"><table>
        <thead><tr><th>${esc(L('ids_personne'))}</th><th>${esc(L('ids_email'))}</th><th>${esc(L('ids_mdp'))}</th></tr></thead>
        <tbody>${lignes}</tbody>
      </table></div>
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
    if (S.ecran === 'revue') {
      g = `<button type="button" class="imh-btn-sec" data-action="autre-fichier"><i class="fa-solid fa-arrow-left"></i>${esc(L('retour_fichier'))}</button>`;
    }
    // Rien de lisible encore (fichier à organiser) : pas de bouton d'import
    // éteint qui laisserait croire qu'il manque seulement une case à cocher.
    if (S.ecran === 'revue' && S.parts.some(p => p.type && p.reconnu && !S.ignorees[p.id])) {
      const n = totalGardees();
      const attente = Object.keys(S.enCours).length > 0;
      const pret = n > 0 && !attente && (S.cibles.length || seulementComptes()) && S.occupe !== 'import';
      d = `<span class="imh-pied-resume">${esc(resume(n))}</span>
        <button type="button" class="imh-btn-prim" data-action="importer"${pret ? '' : ' disabled'}>${S.occupe === 'import'
          ? `<i class="fa-solid fa-circle-notch fa-spin"></i>${esc(L('import_en_cours'))}`
          : `<i class="fa-solid fa-file-import"></i>${esc(libelleImport(n))}`}</button>`;
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
    return { roles: P('btn_roles', n), users: P('btn_users', n), taches: P('btn_taches', n),
             outils: P('btn_outils', n) }[S.type];
  }

  function resume(n) {
    if (!n) return L('rien_a_importer');
    if (seulementComptes()) return L('resume_instance');
    const cibles = (CTX.cibles || []).filter(c => S.cibles.includes(c.id));
    return cibles.length === 1 ? F('resume_une', { x: cibles[0].name }) : P('resume_cartos', cibles.length);
  }

  // Après un clic de case : le pied et le rail, pas toute la liste — on ne
  // perd ni la position, ni le focus.
  function majCompteurs(p) {
    rendrePied();
    const etat = dom.corps.querySelector(`.imh-rail-i[data-part="${CSS.escape(p.id)}"] .imh-rail-etat`);
    if (etat) etat.textContent = P('rail_gardees', nbGardees(p));
    const v = S.verifs[p.id];
    const tout = dom.corps.querySelector('.imh-tout input');
    if (tout && v) tout.checked = gardees(p).length === v.lignes.filter(l => GARDABLES.has(l.statut)).length;
    if (p.type === 'roles' && S.parts.some(x => x.type === 'users' && inclue(x))) planifier(verifierComptes);
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
    const { type, cibles, portee, options } = S;
    S = Object.assign(neuf(), { type, cibles, portee, options, ecran: 'depot' });
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
    const ecranAvant = S.ecran;
    S.occupe = 'lecture';
    S.enLecture = lot.map(f => f.name);
    S.erreur = tous.length > fichiers.length ? F('err_format_fichier', { x: tous.find(f => !EXT.test(f.name)).name }) : null;
    if (ecranAvant !== 'revue') S.ecran = 'depot';
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
    if (p.type !== 'users' && !S.cibles.length) { delete S.verifs[p.id]; rendre(); return; }
    const jeton = S.jetons[p.id] = (S.jetons[p.id] || 0) + 1;
    S.enCours[p.id] = true;
    rendrePied();
    const zone = dom.corps.querySelector('.imh-liste-zone');
    if (zone && p.id === S.active) zone.classList.add('is-maj');
    const lignes = p.type === 'users'
      ? p.lignes.map(l => Object.assign({}, l, { mot_de_passe: '•'.repeat((l.mot_de_passe || '').length) }))
      : p.lignes;
    try {
      const res = await envoyer('/api/import/verifier', {
        type: p.type, lignes, cibles: S.cibles, choix: S.choix[p.id] || {},
        options: p.type === 'users' ? { creer_roles: !!S.options.creer_roles, roles_prevus: rolesPrevus() } : {},
      }, true);
      if (jeton !== S.jetons[p.id]) return;
      S.verifs[p.id] = res;
    } catch (e) {
      if (jeton !== S.jetons[p.id]) return;
      S.erreur = e.message;
    }
    delete S.enCours[p.id];
    rendre();
  }

  // Dans l'ordre d'écriture : les rôles d'abord, pour que les comptes sachent
  // lesquels existeront.
  async function verifierTout() {
    for (const ty of ORDRE) {
      await Promise.all(S.parts.filter(p => p.type === ty && inclue(p)).map(verifier));
    }
  }
  const verifierComptes = () => Promise.all(S.parts.filter(p => p.type === 'users' && inclue(p)).map(verifier));

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
    delete S.iaActivites[ancienne.id];
    delete S.filtres[ancienne.id];
  }

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
      if (p.nature_choisie && p.type) fd.append('comme', p.type);
      const rep = await envoyer('/api/import/organiser', fd);
      rep.part.nature_choisie = p.nature_choisie;
      remplacerPart(p, rep.part);
      S.occupe = null;
      rendre();
      if (inclue(rep.part)) await verifier(rep.part);
      if (rep.part.type === 'roles') await verifierComptes();
    } catch (e) {
      S.occupe = null;
      S.erreur = e.message || L('err_ia');
      rendre();
    }
  }

  async function relireComme(p, ty) {
    const f = S.fichiers[p.fichierIdx];
    if (!f || S.occupe) return;
    if (ty === p.type && p.reconnu) {
      // La nature détectée était la bonne : on la confirme, rien à relire.
      p.nature_choisie = true;
      rendre();
      await verifier(p);
      if (ty === 'roles') await verifierComptes();
      return;
    }
    S.occupe = 'lecture-part';
    rendre();
    try {
      const fd = new FormData();
      fd.append('type', 'multiple');
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
      await verifierComptes();
    } catch (e) {
      S.occupe = null;
      S.erreur = e.message;
      rendre();
    }
  }

  async function rapprocher(p) {
    const v = S.verifs[p.id];
    if (!v || S.occupe) return;
    const noms = v.groupes.filter(g => g.mode === 'a_rattacher').map(g => g.activite_fichier);
    S.occupe = 'rapprocher';
    rendre();
    try {
      const rep = await envoyer('/api/import/rapprocher', { noms, cibles: S.cibles }, true);
      const props = rep.propositions || {};
      S.iaActivites[p.id] = Object.assign(S.iaActivites[p.id] || {}, props);
      const choix = S.choix[p.id] = S.choix[p.id] || {};
      // Une proposition dont l'IA doute n'est pas appliquée : elle s'affiche
      // sous le groupe, l'utilisateur la prend ou non.
      Object.keys(props).forEach(nom => { if (props[nom].confiance !== 'low') choix[nom] = props[nom].activite; });
      if (!Object.keys(props).length) S.erreur = L('ia_rien');
      S.occupe = null;
      await verifier(p);
    } catch (e) {
      S.occupe = null;
      S.erreur = e.message || L('err_ia');
      rendre();
    }
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
      const rep = await envoyer('/api/import/importer', {
        parts, cibles: S.cibles, options: { creer_roles: !!S.options.creer_roles },
      }, true);
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

  function telechargerCsv() {
    const ids = [].concat(...parNature((S.resultat || {}).resultats || []).map(x => x.identifiants));
    const cel = v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
    const lignes = [[L('ids_prenom'), L('ids_nom'), L('ids_email'), L('ids_mdp')].map(cel).join(';')]
      .concat(ids.map(x => [x.prenom, x.nom, x.email, x.mot_de_passe].map(cel).join(';')));
    const blob = new Blob(['﻿' + lignes.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = L('ids_fichier') + '.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
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
    if (ds.part) { S.active = ds.part; return rendre(); }
    const p = partActive();
    if (ds.filtre) { S.filtres[p.id] = ds.filtre; return rendre(); }
    if (ds.comme) return relireComme(p, ds.comme);
    switch (ds.action) {
      case 'erreur-ok': S.erreur = null; return rendre();
      case 'retour': S.type = null; S.ecran = 'choix'; S.erreur = null; return rendre();
      case 'autre-fichier': return reprendreFichier();
      case 'organiser': return organiser(p);
      case 'rapprocher': return rapprocher(p);
      case 'suggestion': {
        const ia = (S.iaActivites[p.id] || {})[ds.groupe];
        if (ia) { (S.choix[p.id] = S.choix[p.id] || {})[ds.groupe] = ia.activite; verifier(p); }
        return;
      }
      case 'ignorer':
        S.ignorees[p.id] = !S.ignorees[p.id];
        rendre();
        if (!S.ignorees[p.id]) verifier(p);
        if (p.type === 'roles') planifier(verifierComptes);
        return;
      case 'importer': return importer();
      case 'encore': {
        const { cibles, portee } = S;
        S = Object.assign(neuf(), { cibles, portee });
        return rendre();
      }
      case 'csv': return telechargerCsv();
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
    if (el.classList.contains('imh-cb')) {
      const i = Number(el.dataset.i);
      if (el.checked) exclus(p).delete(i); else exclus(p).add(i);
      el.closest('.imh-l').classList.toggle('is-off', !el.checked);
      return majCompteurs(p);
    }
    if (el.dataset.action === 'tout') {
      const v = S.verifs[p.id];
      if (!v) return;
      const ex = exclus(p);
      v.lignes.filter(l => GARDABLES.has(l.statut)).forEach(l => (el.checked ? ex.delete(l._i) : ex.add(l._i)));
      rendre();
      return majCompteurs(p);
    }
    if (el.classList.contains('imh-sel')) {
      const choix = S.choix[p.id] = S.choix[p.id] || {};
      if (el.value === '__ignorer__') choix[el.dataset.groupe] = '';
      else if (el.value) choix[el.dataset.groupe] = el.value;
      else delete choix[el.dataset.groupe];
      return verifier(p);
    }
    if (el.dataset.option) {
      S.options[el.dataset.option] = el.checked;
      return verifierComptes();
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
