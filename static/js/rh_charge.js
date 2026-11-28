/* ══════════════════════════════════════════════════════════════════════════
   LA CHARGE DE TRAVAIL — section ④ de la page RH

   Un DAMIER rôle × cartographie. La question « pour un même rôle, qu'est-ce
   que chaque carto demande » — celle qui permet de comparer d'une entité à
   l'autre — se lit EN LIGNE, et la couleur donne l'ordre de grandeur sans
   qu'on lise un chiffre.

   ⚠️ Les COLONNES sont les cartos réellement mesurées ce mois-là, jamais
   toutes les entités : neuf rôles pour trois cartos laisseraient les deux
   tiers des cases vides, et un damier creux se lit comme un tableau cassé.
   Les rôles SANS mesure sortent de la matrice — ils n'ont rien à y mettre —
   et se rangent dessous, avec le mois où ils l'ont été pour la dernière fois.

   ⚠️ La COULEUR dit la part d'un temps plein, et la légende l'écrit : une
   échelle « léger → lourd » ne dit pas combien de personnes un rôle demande.

   ⚠️ « Non mesuré » ne vaut JAMAIS zéro — c'est la règle de toute
   l'application (NULL ≠ 0), et les deux ne se corrigent pas de la même
   façon : l'un se mesure sur la page Temps, l'autre se comble.

   ⚠️ Le poids d'une personne est la SOMME des poids de ses rôles, chacun en
   ENTIER : le poids d'un rôle est le travail qu'il exige de qui le tient.
   On ne le divise pas par le nombre de titulaires — ce serait inventer un
   partage que rien dans l'application ne décide. La ligne du rôle porte son
   nombre de titulaires : la question reste visible.
   ══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const I = window.RHCH_I18N || {};
  const LANG = I.lang === 'en' ? 'en' : 'fr';
  const L = (k) => (k in I ? I[k] : k);
  const V = (k, vars) => Object.keys(vars || {}).reduce(
    (s, x) => s.split('{' + x + '}').join(vars[x]), L(k));
  /* ⚠️ Le singulier ne couvre pas les mêmes nombres : « 0 titulaire » en
     français, « 0 holders » en anglais. Même règle que `gestion_rh.js`. */
  const unSeul = (n) => (LANG === 'en' ? n === 1 : n <= 1);
  const nf = (c, n, vars) =>
    V(c + (unSeul(n) ? '_1' : '_n'), Object.assign({ n: fmt(n) }, vars || {}));

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.prototype.slice.call((r || document).querySelectorAll(s));
  const esc = (v) => String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  const NOMBRE = new Intl.NumberFormat(LANG === 'en' ? 'en-GB' : 'fr-FR');
  const fmt = (n) => NOMBRE.format(n);
  /* Les heures d'une année s'écrivent entières : « 3 090 h ». La décimale
     n'apprend rien sur une grandeur de cet ordre. */
  const heures = (min) => (min == null ? '—'
    : fmt(Math.round(min / 60)) + ' h');
  const pct = (p) => (p == null ? '—'
    : fmt(Math.round(p * 100)) + (LANG === 'en' ? '%' : ' %'));

  function moisLong(p) {
    const m = /^(\d{4})-(\d{1,2})/.exec(String(p || ''));
    if (!m) return '';
    const t = new Intl.DateTimeFormat(LANG === 'en' ? 'en-GB' : 'fr-FR',
      { month: 'long', year: 'numeric' })
      .format(new Date(+m[1], +m[2] - 1, 1));
    return t.charAt(0).toUpperCase() + t.slice(1);
  }
  function moisCourt(p) {
    const m = /^(\d{4})-(\d{1,2})/.exec(String(p || ''));
    if (!m) return '';
    return new Intl.DateTimeFormat(LANG === 'en' ? 'en-GB' : 'fr-FR',
      { month: 'short', year: 'numeric' }).format(new Date(+m[1], +m[2] - 1, 1));
  }

  /* ⚠️ Une teinte PAR CARTO, stable : dérivée du nom, donc la même d'une
     visite à l'autre et d'un écran à l'autre. Un tirage au hasard ferait
     changer les couleurs du damier à chaque chargement. */
  const TEINTES = [262, 192, 330, 24, 152, 288, 8, 174, 42, 316];
  function teinte(cle) {
    let h = 0;
    for (let i = 0; i < String(cle).length; i++) h = (h * 31 + String(cle).charCodeAt(i)) | 0;
    return TEINTES[Math.abs(h) % TEINTES.length];
  }

  /* L'échelle de chaleur : la part d'un TEMPS PLEIN, pas un rang abstrait. */
  const PALIERS = [0.25, 0.5, 0.75, 1, 1.5];
  function niveau(part) {
    if (part == null) return null;
    let n = 0;
    while (n < PALIERS.length && part >= PALIERS[n]) n++;
    return n;                                   // 0 … 5
  }

  let D = null;                                  // le dernier payload
  let periode = null;

  /* ══ LECTURE ═══════════════════════════════════════════════════════════ */

  async function charger(p) {
    const corps = $('#ch-corps');
    if (corps && !D) corps.innerHTML = `<p class="grh-empty">${esc(L('loading'))}</p>`;
    try {
      const r = await fetch('/gestion_rh/api/charge' + (p ? '?periode=' + encodeURIComponent(p) : ''));
      const j = await r.json();
      if (!j || !j.ok) throw new Error('ko');
      D = j;
      periode = j.periode;
    } catch (_) {
      if (corps) corps.innerHTML = `<p class="grh-empty">${esc(L('err'))}</p>`;
      return;
    }
    rendrePeriodes();
    rendre();
    remplirCellules();
  }

  function rendrePeriodes() {
    const sel = $('#ch-periode');
    if (!sel) return;
    sel.innerHTML = (D.periodes || [])
      .map((p) => `<option value="${esc(p)}"${p === periode ? ' selected' : ''}
                   >${esc(moisLong(p))}</option>`).join('');
    sel.classList.toggle('hidden', (D.periodes || []).length < 2);
    const lab = $('.grh-ch-per');
    if (lab) lab.classList.toggle('hidden', (D.periodes || []).length < 2);
  }

  /* ══ LE DAMIER ═════════════════════════════════════════════════════════ */

  function colonnes(mesures) {
    /* ⚠️ Les cartos RÉELLEMENT mesurées, dans l'ordre du poids total : une
       colonne par entité de l'instance laisserait un damier creux. */
    const poids = {};
    mesures.forEach((m) => {
      const k = m.entite_id == null ? '_' : String(m.entite_id);
      poids[k] = (poids[k] || 0) + m.annuel_min;
      poids['nom:' + k] = m.entite;
    });
    return Object.keys(poids).filter((k) => k.indexOf('nom:') !== 0)
      .sort((a, b) => poids[b] - poids[a])
      .map((k) => ({ cle: k, nom: poids['nom:' + k] || '—' }));
  }

  /* ⚠️ L'anneau d'un titulaire dit SA charge totale : pour un même rôle,
     c'est ce qui permet de comparer ses tenants d'un coup d'œil — « qui
     performe ». La comparaison entre CARTOS, elle, se lit en ligne.
     ⚠️ Les mêmes trois couleurs que les pastilles de pourcentage : un
     quatrième code couleur sur le même écran ne se retiendrait pas. */
  function avatar(p) {
    const ini = ((p.nom || '?').trim().split(/\s+/).map((x) => x[0]).join('') || '?')
      .slice(0, 2).toUpperCase();
    const q = (D.personnes || []).find((x) => x.id === p.id);
    const part = q ? q.part_plafond : null;
    const cls = part == null ? 'no'
      : (part > 1 ? 'hi' : (part > 0.75 ? 'mi' : 'lo'));
    const dit = part == null ? p.nom
      : V('ch_av', { p: p.nom, pc: pct(part) });
    return `<span class="ch-av a-${cls}" style="background:hsl(${
      teinte(p.nom || p.id)} 58% 46%)" title="${esc(dit)}">${esc(ini)}</span>`;
  }

  function rendre() {
    const corps = $('#ch-corps');
    if (!corps) return;
    const mes = (D.roles || []).filter((r) => r.mesure);
    const sans = (D.roles || []).filter((r) => !r.mesure);
    const plein = D.plein_temps_min || 0;

    /* ⚠️ AUCUN rôle pesé : on ne dessine pas un damier à zéro colonne. Il
       resterait trois en-têtes au-dessus de rien, ce qui se lit comme un
       tableau cassé — alors que la vérité est « personne n'a encore pesé de
       rôle », et qu'elle a une suite : la page Temps. Les rôles connus sont
       quand même listés dessous : ce sont eux qu'il y a à peser. */
    if (!mes.length) {
      corps.innerHTML = `<div class="ch-vide">
          <span class="ch-vide-i"><i class="fa-solid fa-scale-balanced"></i></span>
          <b>${esc(L('ch_empty'))}</b><p>${esc(L('ch_empty_d'))}</p>
          <a class="ch-go" href="/temps/"><i class="fa-solid fa-stopwatch"></i>
            ${esc(L('ch_empty_go'))}</a>
        </div>` + (sans.length ? zoneSansMesure(sans) : '');
      brancherSans(corps);
      return;
    }

    const toutes = [];
    mes.forEach((r) => r.mesures.forEach((m) => toutes.push(m)));
    const cols = colonnes(toutes);
    const total = toutes.reduce((s, m) => s + m.annuel_min, 0);
    const trop = (D.personnes || []).filter(
      (p) => p.part_plafond != null && p.part_plafond > 1);

    /* ── les trois chiffres ── */
    const etp = plein ? total / plein : null;
    corps.innerHTML = `
      <div class="ch-chif">
        <div><u>${esc(L('ch_tile_mes'))}</u><b>${heures(total)}</b>
          <i>${esc(nf('ch_roles', mes.length))} · ${
            etp == null ? '' : esc(nf('ch_etp', Math.round(etp * 10) / 10))}</i></div>
        <button type="button" class="ch-k-al" data-aller="trop">
          <u>${esc(L('ch_tile_over'))}</u>
          <b>${trop.length ? esc(nf('ch_pers', trop.length)) : esc(L('ch_pers_0'))}</b>
          <i>${trop.length ? esc(trop.slice(0, 2).map((p) => p.nom).join(' · ')) : ''}</i>
        </button>
        <button type="button" class="ch-k-al ch-k-no" data-aller="sans">
          <u>${esc(L('ch_tile_no'))}</u>
          <b>${esc(nf('ch_nb_roles', sans.length))}</b>
          <i>${esc(V('ch_sans_bilan', {
            a: fmt(sans.filter((r) => (r.cartos_possibles || []).length).length),
            m: fmt(sans.filter((r) => !(r.cartos_possibles || []).length).length),
          }))}</i>
        </button>
      </div>
      ${damier(mes, cols, plein)}
      ${legende(plein)}
      ${sans.length ? zoneSansMesure(sans) : ''}`;

    const al = $('[data-aller="trop"]', corps);
    if (al) al.onclick = () => {
      const bloc = $('#bloc-personnes');
      if (!bloc) return;
      bloc.scrollIntoView({ behavior: 'smooth', block: 'start' });
      bloc.classList.add('est-pointe');
      setTimeout(() => bloc.classList.remove('est-pointe'), 1600);
    };

    brancherSans(corps);
    /* ⚠️ La tuile DÉPLIE la zone en plus d'y mener : repliée par défaut,
       elle conduirait sinon à un en-tête fermé, c'est-à-dire à rien. */
    const vers = $('[data-aller="sans"]', corps);
    if (vers) vers.onclick = () => {
      const zone = $('.ch-sans', corps);
      if (!zone) return;
      if (zone.dataset.ouvert !== '1') $('[data-sans-plier]', zone)?.click();
      zone.scrollIntoView({ behavior: 'smooth', block: 'start' });
      zone.classList.add('est-pointe');
      setTimeout(() => zone.classList.remove('est-pointe'), 1600);
    };
  }

  function damier(roles, cols, plein) {
    const libres = roles.some((r) => (r.sans_carto || []).length);
    const tete = cols.map((c) =>
      `<th class="ch-c"><span class="ch-dot" style="background:hsl(${
        teinte(c.nom)} 62% 48%)"></span>${esc(c.nom)}</th>`).join('');
    const lignes = roles.map((r) => {
      const par = {};
      r.mesures.forEach((m) => { par[m.entite_id == null ? '_' : String(m.entite_id)] = m; });
      const cases = cols.map((c) => {
        const m = par[c.cle];
        /* ⚠️ C'EST ICI que « qui performe » se lit : les titulaires posés
           dans LEUR carto. Un rôle commun à deux cartos pesait pareil pour
           tous ses tenants — on comparait des cartos, jamais des personnes.
           Le placement vient du SERVEUR (`titulaires_carto`), pas d'un second
           calcul de l'attache. */
        const qui = (r.titulaires_carto || {})[c.cle] || [];
        const pastilles = !qui.length ? '' : `<span class="ch-t-av">${
          qui.slice(0, 3).map(avatar).join('')}${
          qui.length > 3 ? `<span class="ch-av ch-av--p">+${
            qui.length - 3}</span>` : ''}</span>`;
        /* ⚠️ Une case VIDE porte quand même ses titulaires : quelqu'un
           travaille là et personne n'y a pesé ce rôle. Sans cela la personne
           disparaissait de la ligne de son propre rôle — elle n'était ni
           dans une case (aucune mesure) ni dans « non situés » (elle EST
           située). La case dit alors ce qu'il y a à faire. */
        if (!m) {
          return `<td><div class="ch-t v0">${
            qui.length ? esc(L('ch_nomes_ici')) : '—'}${pastilles}</div></td>`;
        }
        const n = niveau(plein ? m.annuel_min / plein : null);
        return `<td><div class="ch-t n${n}">
            <b>${heures(m.annuel_min)}</b>
            <span>${esc(nf('ch_acts', m.n_activites))}</span>
            ${pastilles}
          </div></td>`;
      }).join('');
      const part = r.part;
      const larg = Math.max(2, Math.min(100, (part || 0) / 2 * 100));
      return `<tr>
          <th class="ch-r" title="${esc(r.nom)}">${esc(r.nom)}</th>
          ${cases}
          <td><div class="ch-tot">
            <b>${heures(r.annuel_min)}</b>
            <span class="ch-piste"><i style="width:${larg.toFixed(1)}%"></i>
              <u style="left:50%" title="${esc(L('ch_full'))}"></u></span>
            <em class="${part > 1 ? 'hi' : (part > 0.5 ? 'mi' : 'lo')}"
              >${esc(V('ch_pct_full', { n: fmt(Math.round((part || 0) * 100)) }))}</em>
          </div></td>
          ${!libres ? '' : `<td><div class="ch-tit">${
            (r.sans_carto || []).length
              ? (r.sans_carto || []).slice(0, 4).map(avatar).join('')
                + (r.sans_carto.length > 4 ? `<span class="ch-av ch-av--p">+${
                    r.sans_carto.length - 4}</span>` : '')
              : `<span class="ch-rien">—</span>`}</div></td>`}
        </tr>`;
    }).join('');
    /* ⚠️ La dernière colonne ne porte que les titulaires que PERSONNE n'a
       situés : les autres sont dans leur case, et les redire ici les
       compterait deux fois à l'œil. Elle DISPARAÎT quand tout le monde est
       situé — le damier devient alors une pure comparaison — et elle est
       intacte sur une instance qui vient de prendre ce code, où aucune
       attache n'existe encore : rien ne bouge tant qu'on n'a rien situé. */
    return `<div class="ch-dam"><table class="ch-dm">
        <thead><tr><th class="ch-r">${esc(L('ch_role'))}</th>${tete}
          <th class="ch-c">${esc(L('ch_total'))}</th>
          ${libres ? `<th class="ch-c">${esc(L('ch_holders_free'))}</th>` : ''}
          </tr></thead>
        <tbody>${lignes}</tbody></table></div>`;
  }

  function legende(plein) {
    const bornes = [0].concat(PALIERS);
    const ech = bornes.map((b, i) =>
      `<span class="ch-l-t n${i}"><u>${
        i === bornes.length - 1 ? '≥ ' + pct(b) : pct(b)}</u></span>`).join('');
    const cal = D.calendrier || {};
    return `<div class="ch-lgd">
        <span class="ch-lgd-t">${esc(L('ch_legend'))}</span>
        <span class="ch-ech">${ech}</span>
        <span class="ch-lgd-c">${esc(V('ch_cal', {
          s: fmt(cal.weeks_per_year || 0), j: fmt(cal.days_per_week || 0),
          h: fmt(cal.hours_per_day || 0), t: heures(plein) }))}</span>
      </div>`;
  }

  /* ══ SANS MESURE : une liste de TRAVAIL, pas un mur ═══════════════════
     Mesuré chez le pilote : 108 rôles, une pastille chacun, « jamais
     mesuré » répété cent huit fois — plus haut que le damier qu'ils
     suivent, et rien pour les replier. Trois choses la rendent utilisable.

     ⚠️ 1. « À MESURER » et « AUCUNE ACTIVITÉ » ne se corrigent pas de la
        même façon. La page Temps n'offre que les rôles qui tiennent une
        activité de la carto regardée (`roles_de_la_carto`) : un rôle qui
        n'en tient aucune ne peut être pesé NULLE PART. Mêlés, ils font
        croire qu'il reste cent mesures à faire quand il y en a neuf.
     ⚠️ 2. REPLIÉE par défaut, le compte dans son en-tête : c'est le compte
        qu'on vient lire, pas les cent noms.
     ⚠️ 3. Chaque rôle à mesurer est une PORTE vers son analyse. Une liste
        qui dit ce qui manque sans permettre d'y aller reste un rapport.
     ══════════════════════════════════════════════════════════════════ */

  const CLE_SANS = 'rh.charge.sans';

  function sansEstOuvert() {
    try { return localStorage.getItem(CLE_SANS) === '1'; } catch (e) { return false; }
  }
  function poserSansOuvert(v) {
    try { localStorage.setItem(CLE_SANS, v ? '1' : '0'); } catch (e) { /* refusé */ }
  }

  const sansAccent = (s) => String(s || '').toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '');

  function pastilleSans(r) {
    const cartos = r.cartos_possibles || [];
    const quand = r.derniere_periode
      ? V('ch_last', { m: moisCourt(r.derniere_periode) }) : L('ch_never');
    /* Rien à mesurer : pas de porte. Un bouton qui mène à un écran où le
       rôle n'existe pas est pire qu'une ligne qui dit pourquoi. */
    if (!cartos.length) {
      return `<span class="ch-sans-p est-muet">
          <b>${esc(r.nom)}</b><em>${esc(quand)}</em></span>`;
    }
    /* ⚠️ La pastille NOMME la carto où elle mène : avec plusieurs cartos
       candidates, un clic muet choisirait à la place de l'utilisateur. */
    const c = cartos[0];
    const ou = cartos.length > 1
      ? V('ch_sans_ou_n', { c: c.nom, n: fmt(cartos.length - 1) }) : c.nom;
    return `<a class="ch-sans-p est-porte"
        href="/temps/?analyse=role&amp;role=${r.id}&amp;carto=${c.id}"
        title="${esc(V('ch_sans_aller', { r: r.nom, c: c.nom }))}">
        <b>${esc(r.nom)}</b><em>${esc(quand)}</em>
        <u><i class="fa-solid fa-stopwatch"></i>${esc(ou)}</u></a>`;
  }

  function zoneSansMesure(sans) {
    const faire = sans.filter((r) => (r.cartos_possibles || []).length);
    const muets = sans.filter((r) => !(r.cartos_possibles || []).length);
    const ouv = sansEstOuvert();
    const groupe = (g, cle, liste, dit) => (liste.length
      ? `<div class="ch-sans-g" data-g="${g}">
        <u>${esc(nf(cle, liste.length))}</u>
        ${dit ? `<p>${esc(dit)}</p>` : ''}
        <div class="ch-sans-l">${liste.map(pastilleSans).join('')}</div>
      </div>` : '');
    return `<div class="ch-sans" data-ouvert="${ouv ? '1' : '0'}">
        <button type="button" class="ch-sans-h" data-sans-plier
                aria-expanded="${ouv ? 'true' : 'false'}">
          <i class="fa-solid fa-chevron-right ch-sans-c"></i>
          <span>${esc(L('ch_nomes_zone'))}</span>
          <b>${esc(nf('ch_nb_roles', sans.length))}</b>
          <em>${esc(V('ch_sans_bilan', { a: fmt(faire.length),
                                         m: fmt(muets.length) }))}</em>
        </button>
        <div class="ch-sans-b">
          <label class="ch-sans-q">
            <i class="fa-solid fa-magnifying-glass"></i>
            <input type="search" data-sans-q
                   placeholder="${esc(L('ch_sans_cherche'))}"
                   aria-label="${esc(L('ch_sans_cherche'))}">
          </label>
          ${groupe('faire', 'ch_sans_faire', faire, '')}
          ${groupe('muet', 'ch_sans_muet', muets, L('ch_sans_muet_d'))}
          <p class="ch-sans-rien" hidden>${esc(L('ch_sans_rien'))}</p>
        </div>
      </div>`;
  }

  function brancherSans(corps) {
    const zone = $('.ch-sans', corps);
    if (!zone) return;
    const plier = $('[data-sans-plier]', zone);
    if (plier) plier.onclick = () => {
      const o = zone.dataset.ouvert !== '1';
      zone.dataset.ouvert = o ? '1' : '0';
      plier.setAttribute('aria-expanded', o ? 'true' : 'false');
      poserSansOuvert(o);
    };
    const q = $('[data-sans-q]', zone);
    if (!q) return;
    /* ⚠️ Il MASQUE, il ne re-rend pas : réécrire la liste à chaque frappe
       ferait perdre le curseur du champ qu'on tape.
       ⚠️ Et `input`, pas `change` : sur `change` il ne filtrerait rien
       pendant la frappe, sans la moindre erreur pour le dire. */
    q.addEventListener('input', () => {
      const t = sansAccent(q.value.trim());
      let vus = 0;
      $$('.ch-sans-p', zone).forEach((p) => {
        const ok = !t || sansAccent(p.textContent).indexOf(t) >= 0;
        p.hidden = !ok;
        if (ok) vus += 1;
      });
      // Un groupe dont toutes les pastilles sont masquées se masque aussi,
      // sinon on lit son titre au-dessus de rien.
      $$('.ch-sans-g', zone).forEach((g) => {
        g.hidden = !$$('.ch-sans-p', g).some((p) => !p.hidden);
      });
      const rien = $('.ch-sans-rien', zone);
      if (rien) rien.hidden = vus > 0;
    });
  }

  /* ══ LA COLONNE DE LA SECTION ① ════════════════════════════════════════
     ⚠️ C'est `gestion_rh.js` qui rend la liste des personnes : il y pose une
     cellule VIDE (`[data-ch]`) et prévient par un événement. On la remplit
     ici, dans les deux sens — à chaque rendu de la liste, et dès que la
     charge arrive. Aucun des deux fichiers n'attend l'autre. */

  function remplirCellules() {
    if (!D) return;
    const gens = {};
    (D.personnes || []).forEach((p) => { gens[p.id] = p; });
    const plafond = D.plafond_min || 0;
    $$('[data-ch]').forEach((box) => {
      const p = gens[+box.dataset.ch];
      if (!p) { box.innerHTML = ''; return; }
      box.innerHTML = cellule(p, plafond);
      const b = $('[data-ch-ouvre]', box);
      if (b) b.onclick = (e) => { e.stopPropagation(); ouvrirDetail(p.id); };
    });
  }

  function cellule(p, plafond) {
    if (!p.n_roles) {
      return `<span class="ch-cell-rien">${esc(L('ch_no_role'))}</span>`;
    }
    if (p.annuel_min == null) {
      return `<span class="ch-cell-rien">${esc(L('ch_only_nomes'))}</span>`;
    }
    const part = p.part_plafond || 0;
    /* L'échelle de la jauge va jusqu'à 2,5 × le plafond : au-delà on la
       plafonne, et la pastille porte le vrai pourcentage. */
    const ech = Math.max(plafond * 2.5, p.annuel_min) || 1;
    let x = 0;
    const segs = (p.roles || []).filter((r) => r.annuel_min != null).map((r) => {
      const w = r.annuel_min / ech * 100;
      const h = `<span class="s" style="left:${x.toFixed(2)}%;width:${w.toFixed(2)}%;
        background:hsl(${teinte(r.nom)} 62% 48%)" title="${esc(r.nom)} · ${
        heures(r.annuel_min)}"></span>`;
      x += w;
      return h;
    }).join('');
    const cls = part > 1 ? 'hi' : (part > 0.75 ? 'mi' : 'lo');
    return `<span class="ch-jauge">${segs}
        <span class="ch-plaf" style="left:${(plafond / ech * 100).toFixed(2)}%"></span></span>
      <button type="button" class="ch-heures" data-ch-ouvre="${p.id}"
              title="${esc(V('ch_load', { h: heures(plafond) }))}">
        <b>${heures(p.annuel_min)}</b>
        <span class="ch-pc ${cls}">${pct(part)}</span>
        ${p.sans_mesure ? `<em>${esc(nf('ch_plus_nomes', p.sans_mesure))}</em>` : ''}
      </button>`;
  }

  /* ══ OÙ CETTE PERSONNE TIENT CE RÔLE ═══════════════════════════════════
     ⚠️ Le SEUL endroit qui déplace une attache. Cocher un rôle depuis une
     carto n'en remplit qu'une vide : ce clic dit « cette personne tient ce
     rôle », et l'attache est un second fait, plus lourd — c'est lui qui
     décide de sa charge mesurée. Il se pose donc là où on lit cette charge.
     ⚠️ Et il est ÉCRIT, jamais deviné : sans cette ligne, une personne
     rattachée sortait des comptages d'une carto sans que rien ne le dise. */

  function ligneOu(p, r) {
    /* ⚠️ La carto d'attache figure dans la liste MÊME si le rôle n'y est pas
       mesuré : c'est le cas qui demande une correction, et un sélecteur qui
       ne montre pas la valeur en place dit le contraire de la vérité. */
    const choix = (r.cartos || []).slice();
    if (r.entite_id && !choix.some((c) => c.id === r.entite_id)) {
      choix.push({ id: r.entite_id, nom: r.entite, annuel_min: null });
    }
    const opts = [`<option value=""${r.entite_id ? '' : ' selected'}>${
      esc(L('ch_where_none'))}</option>`].concat(choix.map((c) =>
      `<option value="${c.id}"${c.id === r.entite_id ? ' selected' : ''}>${
        esc(c.nom)}${c.annuel_min == null ? '' : ' · ' + heures(c.annuel_min)}</option>`));
    return `<div class="ch-ou">
        <span class="ch-ou-l"><i class="fa-solid fa-location-dot"></i>
          ${esc(L('ch_where'))}</span>
        <select class="ch-ou-s" data-ou="${p.id}:${r.id}">${opts.join('')}</select>
        ${choix.length ? '' : `<em class="ch-ou-rien">${esc(L('ch_where_empty'))}</em>`}
      </div>`;
  }

  async function poserOu(userId, roleId, entiteId, champ) {
    champ.disabled = true;
    try {
      const rep = await fetch('/gestion_rh/role_carto', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, role_id: roleId,
                               entity_id: entiteId || null }),
      });
      const j = await rep.json();
      if (!j || !j.ok) { champ.disabled = false; return; }
      /* ⚠️ On RECHARGE : l'attache change le poids de la personne, celui de
         ses voisins dans le damier et la colonne « non situés ». Redresser
         ces trois choses à la main donnerait une seconde règle pour un seul
         verdict — c'est la leçon de `dashboard_rows`. La pop-up se rouvre
         sur la personne, donc le réglage suivant est à un clic. */
      await charger(periode);
      ouvrirDetail(userId);
    } catch (_) { champ.disabled = false; }
  }

  /* ══ LA FENÊTRE DE DÉTAIL ══════════════════════════════════════════════ */

  function ouvrirDetail(userId) {
    if (!D) return;
    const p = (D.personnes || []).find((x) => x.id === userId);
    if (!p) return;
    const plafond = D.plafond_min || 0;
    const ech = Math.max(plafond * 2.5, p.annuel_min || 0) || 1;
    let x = 0;
    const segs = (p.roles || []).filter((r) => r.annuel_min != null).map((r) => {
      const w = r.annuel_min / ech * 100;
      const h = `<span class="s" style="left:${x.toFixed(2)}%;width:${w.toFixed(2)}%;
        background:hsl(${teinte(r.nom)} 62% 48%)">${
        w > 16 ? esc(r.nom) : ''}</span>`;
      x += w;
      return h;
    }).join('');
    $('#grh-ch-titre').textContent = p.nom;
    $('#grh-ch-sous').textContent = V('ch_pop_sub', { m: moisLong(periode) });
    $('#grh-ch-body').innerHTML = `
      <div class="ch-pop-g">
        <span class="ch-jauge ch-jauge--xl">${segs}
          <span class="ch-plaf" data-l="${esc(V('ch_ceiling', { h: heures(plafond) }))}"
                style="left:${(plafond / ech * 100).toFixed(2)}%"></span></span>
        <div class="ch-pop-ax"><span>0 h</span><span>${heures(ech)}</span></div>
      </div>
      <div class="ch-pop-h">${esc(L('ch_pop_roles'))}</div>
      ${(p.roles || []).map((r) => `<div class="ch-pl">
          <span class="ch-pl-n"><u style="background:hsl(${teinte(r.nom)} 62% 48%)"></u>
            ${esc(r.nom)}</span>
          <b>${heures(r.annuel_min)}</b>
          <span class="ch-pc ${r.annuel_min == null ? 'no'
            : (plafond && r.annuel_min / plafond > 1 ? 'hi' : 'lo')}">${
            r.annuel_min == null
              ? esc(L(r.entite_id ? 'ch_where_nomes' : 'ch_nomes'))
              : pct(plafond ? r.annuel_min / plafond : null)}</span>
        </div>
        ${ligneOu(p, r)}`).join('')}
      <div class="ch-pl ch-pl--tot">
        <span class="ch-pl-n">${esc(L('ch_total'))}</span>
        <b>${heures(p.annuel_min)}</b>
        <span class="ch-pc ${p.part_plafond > 1 ? 'hi' : 'lo'}">${pct(p.part_plafond)}</span>
      </div>`;
    $$('[data-ou]', $('#grh-ch-body')).forEach((s) => {
      s.onchange = () => {
        const [u, r] = s.dataset.ou.split(':');
        poserOu(+u, +r, s.value ? +s.value : null, s);
      };
    });
    $('#grh-ch-win').classList.remove('hidden');
  }

  function fermerDetail() { $('#grh-ch-win').classList.add('hidden'); }

  /* ══ L'AVERTISSEMENT DU PLAFOND ════════════════════════════════════════
     ⚠️ Une PRÉVENTION, jamais un refus : la décision d'affecter quelqu'un
     appartient à qui affecte. Et elle s'affiche DANS la ligne où l'on coche —
     une fenêtre par-dessus la fenêtre cacherait le chiffre qu'on vient lire
     pour décider (la règle déjà posée pour les formulaires de la page
     Compétences). */

  /* ⚠️ `entiteId` est la carto DEPUIS LAQUELLE on coche — celle à laquelle le
     lien va être attaché. Sans elle, l'avertissement annoncerait la somme de
     toutes les cartos du rôle alors que la personne n'en portera qu'une : un
     plafond franchi sur le papier et pas en vrai. C'est la MÊME règle que
     `charge_travail.poids_du_role`, et le serveur sert déjà le poids carto
     par carto (`r.mesures`) pour qu'elle ne soit pas réécrite ici. */
  function verdict(userId, roleId, entiteId) {
    if (!D) return null;
    const p = (D.personnes || []).find((x) => x.id === userId);
    const r = (D.roles || []).find((x) => x.id === roleId);
    const plafond = D.plafond_min || 0;
    if (!p || !r || !plafond) return null;
    const ajout = entiteId == null ? r.annuel_min
      : ((r.mesures || []).find((m) => m.entite_id === entiteId) || {}).annuel_min;
    /* Un rôle non mesuré — ou non mesuré SUR CETTE CARTO — n'ajoute rien de
       connu : on ne prévient pas d'un dépassement qu'on ne sait pas calculer. */
    if (ajout == null) return null;
    const avant = p.annuel_min || 0;
    const apres = avant + ajout;
    return {
      role: r.nom, qui: p.nom, avant: avant, apres: apres, plafond: plafond,
      depasse: apres > plafond, deja: avant > plafond,
    };
  }

  function avertir(userId, roleId, coche, suite, entiteId) {
    const v = verdict(userId, roleId, entiteId);
    if (!v || !v.depasse) return false;
    const ligne = coche.closest('.grh-row') || coche.parentElement;
    if (!ligne) return false;
    const vieux = ligne.parentElement.querySelector('.ch-alerte');
    if (vieux) vieux.remove();

    const box = document.createElement('div');
    box.className = 'ch-alerte';
    box.innerHTML = `
      <span class="ch-al-i"><i class="fa-solid fa-triangle-exclamation"></i></span>
      <div class="ch-al-c">
        <b>${esc(V('ch_warn_t', { r: v.role, p: v.qui,
                                  pc: pct(v.apres / v.plafond) }))}</b>
        <p>${esc(V('ch_warn_d', { a: heures(v.avant), b: heures(v.apres),
                                  c: heures(v.plafond) }))}</p>
        ${v.deja ? `<p class="ch-al-deja">${esc(L('ch_warn_already'))}</p>` : ''}
        <div class="ch-al-b">
          <button type="button" class="ch-al-ok">${esc(L('ch_warn_ok'))}</button>
          <button type="button" class="ch-al-no">${esc(L('cancel'))}</button>
        </div>
      </div>`;
    ligne.insertAdjacentElement('afterend', box);
    /* L'avertissement doit entrer ENTIER dans la fenêtre : posé en bas de la
       liste des rôles, ses deux boutons tombaient sous le bord. Trois choses,
       toutes mesurées :
       ⚠️ `scrollIntoView({block:'nearest'})` ne compte pas la MARGE, et il
          laissait l'avertissement à cheval sur le bord ;
       ⚠️ `offsetTop` se mesure depuis l'`offsetParent`, qui n'est pas le
          conteneur qui DÉFILE dès que celui-ci n'est pas positionné — relevé
          102 px sous le bord. On calcule par les RECTANGLES ;
       ⚠️ et le défilement est INSTANTANÉ : un défilement doux est piloté par
          une animation, et une animation ne progresse pas dans un volet qui
          ne peint pas (scrollTop figé à 117,5 sur 218). Ici le signal est la
          boîte rouge qui paraît, pas le mouvement. */
    const boite = ligne.closest('.grh-modal-body') || ligne.parentElement;
    if (boite) {
      const ra = box.getBoundingClientRect();
      const rc = boite.getBoundingClientRect();
      const delta = ra.bottom + 16 - rc.bottom;
      if (delta > 0) {
        boite.scrollTo({ top: boite.scrollTop + delta, behavior: 'instant' });
      }
    }
    $('.ch-al-ok', box).onclick = () => { box.remove(); suite(); };
    $('.ch-al-no', box).onclick = () => { box.remove(); coche.checked = false; };
    return true;
  }

  /* ══ DÉMARRAGE ═════════════════════════════════════════════════════════ */

  function demarrer() {
    const sel = $('#ch-periode');
    if (sel) sel.addEventListener('change', () => charger(sel.value));
    const x = $('#grh-ch-x'); if (x) x.addEventListener('click', fermerDetail);
    const f = $('#grh-ch-fond'); if (f) f.addEventListener('click', fermerDetail);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('#grh-ch-win').classList.contains('hidden')) fermerDetail();
    });
    document.addEventListener('grh:personnes', remplirCellules);
    window.RHCharge = { avertir: avertir, verdict: verdict, recharger: () => charger(periode) };
    charger(null);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
