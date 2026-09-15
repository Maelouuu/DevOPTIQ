/* competences_v2.js — Page Compétences (V1.1, CDC 6).
   Parcours : Collaborateur → Rôle → Activités → Résultats → (écart) → Diagnostic → Plan.
   Le développeur de compétences évalue par RÉSULTAT ; le niveau global d'activité = min des résultats.

   Deux partis pris de lecture, tenus partout dans le fichier :
   - l'écart est une DISTANCE, pas un nombre : requis et démontré se lisent sur la
     même jauge, et le requis est marqué là où l'on choisit ;
   - un niveau NON ÉVALUÉ n'est pas un zéro (règle du CDC) : il se dessine en
     creux, et « effacer » est un bouton à part, jamais un palier de plus. */
(function () {
  'use strict';
  const LANG = window.OPTIQ_LANG === 'en' ? 'en' : 'fr';
  const $ = s => document.querySelector(s);

  const I18N = {
    fr: {
      manager: 'Développeur de compétences', collaborators: 'Collaborateurs', no_collab: 'Aucun collaborateur.',
      no_dev: 'Aucun',
      no_dev_hint: "Aucun développeur de compétences ne vous est rattaché, et vous n'encadrez personne. La page Gestion RH permet d'affecter les collaborateurs à un développeur de compétences.",
      title: 'Compétences', pick_collab: 'Sélectionnez un collaborateur pour commencer.',
      pick_collab2: 'Sélectionnez un collaborateur puis un rôle.',
      c_activity: 'Activité', c_level: 'Niveau', c_required: 'Niveau requis', c_demonstrated: 'Niveau démontré',
      c_gap: 'Écart', c_tech: 'Technicité', tech_gap: 'Écart', tech_ok: 'Tenu',
      competence: 'Compétence principale', save_eval: "Enregistrer l'évaluation",
      evaluate: 'Évaluer', not_assessed: 'Non évalué', erase: 'Effacer',
      std: 'Standard minimal', self: 'Auto-évaluation', saved: 'Évaluation enregistrée',
      no_activities: 'Aucune activité pour ce rôle.', pick_role: 'Sélectionnez un rôle.',
      none: '—', back: '← Évaluation', gen_plan: 'Générer le plan',
      cause_q: "Quelle est la cause de l'écart ?", linked_caps: 'Capacités reliées à ce résultat',
      no_gap: 'Aucun résultat en écart : le niveau requis est tenu.', dem: 'démontré', req: 'requis',
      plan_title: "Plan d'accompagnement", gen: 'Génération…',
      qualify_title: 'Qualification des sorties',
      qualify_desc: "L'IA propose une nature pour chaque donnée de sortie. Corrigez si besoin, puis validez. Les données « Résultat » fondent la compétence et servent de base à l'évaluation.",
      validate_analysis: "Valider l'analyse", to_qualify: 'À qualifier',
      setup_done: 'Activité configurée', min_perf_ph: 'Standard minimal de performance…',
      no_out: "Cette activité n'a aucune donnée de sortie à qualifier.", req_set: 'Niveau requis mis à jour',
      not_set: 'Non défini',
      not_configured: "Activité à configurer avant l'évaluation",
      setup_intro: "Indiquez la nature de chaque donnée de sortie. Les données « Résultat » sont celles dont la tenue démontre la maîtrise : ce sont elles que vous évaluerez ensuite.",
      setup_btn: 'Configurer (qualifier les sorties)', configure_short: 'Configurer',
      eval_of: 'Évaluation de', eval_hint: 'Fixez, pour chaque résultat, le niveau tenu par le collaborateur.',
      edit: 'modifier',
      evidence_ph: 'Preuve / commentaire (facultatif)', add_evidence: '+ Ajouter une preuve',
      diagnose: "Diagnostiquer l'écart",
      configuring: 'Configuration en cours… (analyse IA des sorties)', loading: 'Chargement…',
      need_result: "Marquez au moins une sortie comme « Résultat de l'activité » avant de valider : c'est ce niveau que vous évaluerez ensuite.",
      configured_go_eval: 'Sorties qualifiées ✓ — évaluez maintenant le niveau du collaborateur pour chaque résultat, puis enregistrez.',
      req_failed: 'Action impossible (erreur réseau ou serveur).', pick_level: 'À évaluer',
      roles_label: 'Rôles du collaborateur',
      // Bandeau de situation
      b_held: 'Niveau tenu', b_gap: 'En écart', b_todo: 'À évaluer', b_setup: 'À configurer',
      filter_off: 'Tout afficher', no_match: 'Aucune activité dans cette catégorie.',
      // Ligne d'activité
      m_result_one: 'résultat', m_result_many: 'résultats', m_partial: 'sur',
      m_eval_one: 'évalué', m_eval_many: 'évalués',
      m_last: 'évalué le', m_never: 'jamais évaluée', m_toqualify: 'sorties à qualifier',
      target_short: 'requis',
      tech_title: 'Technicité — domaine technique',
      tech_exp: "Axe séparé de la maîtrise : une même activité peut être exercée dans des contextes techniques différents (ex. Plastique / Métal). Fixez le niveau technique requis par le rôle et le niveau démontré par le collaborateur.",
      tech_required: 'Requis', tech_demonstrated: 'Démontré', tech_add_ph: 'Nouveau domaine (ex. Plastique)…',
      tech_link: 'Ajouter', tech_pick: 'Choisir un domaine existant…', tech_empty: 'Aucun domaine technique lié à cette activité.',
    },
    en: {
      manager: 'Competency developer', collaborators: 'Team members', no_collab: 'No team member.',
      no_dev: 'None',
      no_dev_hint: 'No competency developer is attached to you, and you manage nobody. Use the HR page to attach team members to a competency developer.',
      title: 'Skills', pick_collab: 'Select a team member to start.',
      pick_collab2: 'Select a team member then a role.',
      c_activity: 'Activity', c_level: 'Level', c_required: 'Required level', c_demonstrated: 'Demonstrated level',
      c_gap: 'Gap', c_tech: 'Technicity', tech_gap: 'Gap', tech_ok: 'Met',
      competence: 'Main competence', save_eval: 'Save evaluation',
      evaluate: 'Evaluate', not_assessed: 'Not assessed', erase: 'Clear',
      std: 'Minimum standard', self: 'Self-assessment', saved: 'Evaluation saved',
      no_activities: 'No activity for this role.', pick_role: 'Select a role.',
      none: '—', back: '← Evaluation', gen_plan: 'Generate plan',
      cause_q: 'What is the cause of the gap?', linked_caps: 'Capabilities linked to this result',
      no_gap: 'No result below the required level.', dem: 'demonstrated', req: 'required',
      plan_title: 'Support plan', gen: 'Generating…',
      qualify_title: 'Output qualification',
      qualify_desc: 'AI suggests a nature for each output. Adjust if needed, then validate. “Result” data grounds the competence and is the basis for evaluation.',
      validate_analysis: 'Validate analysis', to_qualify: 'To qualify',
      setup_done: 'Activity configured', min_perf_ph: 'Minimum performance standard…',
      no_out: 'This activity has no output data to qualify.', req_set: 'Required level updated',
      not_set: 'Not set',
      not_configured: 'Activity to configure before evaluation',
      setup_intro: 'Set the nature of each output. “Result” data is what demonstrates mastery: those are what you will evaluate next.',
      setup_btn: 'Configure (qualify outputs)', configure_short: 'Configure',
      eval_of: 'Evaluation of', eval_hint: 'For each result, set the level the team member holds.',
      edit: 'edit',
      evidence_ph: 'Evidence / comment (optional)', add_evidence: '+ Add evidence',
      diagnose: 'Diagnose the gap',
      configuring: 'Configuring… (AI analysis of outputs)', loading: 'Loading…',
      need_result: 'Mark at least one output as “Activity result” before validating: that is the level you will evaluate next.',
      configured_go_eval: 'Outputs qualified ✓ — now set the team member’s level for each result, then save.',
      req_failed: 'Action failed (network or server error).', pick_level: 'To assess',
      roles_label: "Team member's roles",
      b_held: 'Level met', b_gap: 'Below target', b_todo: 'To assess', b_setup: 'To configure',
      filter_off: 'Show all', no_match: 'No activity in this category.',
      m_result_one: 'result', m_result_many: 'results', m_partial: 'of',
      m_eval_one: 'assessed', m_eval_many: 'assessed',
      m_last: 'assessed on', m_never: 'never assessed', m_toqualify: 'outputs to qualify',
      target_short: 'required',
      tech_title: 'Technicity — technical domain',
      tech_exp: 'A separate axis from mastery: the same activity can be performed in different technical contexts (e.g. Plastic / Metal). Set the technical level required by the role and the level demonstrated by the team member.',
      tech_required: 'Required', tech_demonstrated: 'Demonstrated', tech_add_ph: 'New domain (e.g. Plastic)…',
      tech_link: 'Add', tech_pick: 'Pick an existing domain…', tech_empty: 'No technical domain linked to this activity.',
    },
  };
  const T = k => (I18N[LANG][k] || k);

  const state = {
    userId: null, userName: '', roleId: null, roleName: '',
    scale: {}, notAssessed: 'Non évalué', activity: null, domScale: {},
    rows: [], filtre: null,
  };

  // api() ne rejette jamais silencieusement : en cas d'erreur réseau/serveur, on prévient
  // l'utilisateur (toast) et on renvoie un objet marqué {__error:true} que les appelants gèrent.
  // `silencieux` : pour les appels dont l'échec est un ÉTAT normal et non une
  // panne — ne pas jeter « Action impossible » à la figure de quelqu'un qui n'a
  // simplement pas de développeur de compétences.
  async function api(url, opts, silencieux) {
    const rate = msg => { if (!silencieux) toast(msg); };
    try {
      const r = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
      const txt = await r.text();
      let data; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = null; }
      if (!r.ok || data === null) { rate(T('req_failed')); return { __error: true, status: r.status }; }
      return data;
    } catch (e) { rate(T('req_failed')); return { __error: true }; }
  }
  function toast(msg) {
    const t = $('#cv2-toast'); t.textContent = msg; t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 1900);
  }
  // Indicateur d'attente dans la fenêtre (les analyses IA prennent plusieurs secondes).
  function showBusy(msg) {
    $('#cv2-drawer-body').innerHTML =
      `<div class="cv2-busy"><span class="cv2-spin"></span><div>${esc(msg || T('loading'))}</div></div>`;
    $('#cv2-footer').querySelectorAll('button').forEach(b => { b.disabled = true; });
  }
  function applyStaticI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const k = el.dataset.i18n; if (I18N[LANG][k]) el.textContent = I18N[LANG][k];
    });
  }
  // Les noms d'activités, de résultats et de domaines viennent de la base : on
  // les échappe partout où ils entrent dans du HTML construit à la main.
  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function levelName(lvl) {
    return lvl === null || lvl === undefined ? state.notAssessed : (state.scale[String(lvl)] || String(lvl));
  }
  function initials(f, l) { return ((f || '')[0] || '').toUpperCase() + ((l || '')[0] || '').toUpperCase(); }
  function fmtDate(iso) {
    if (!iso) return T('none');
    try { return new Date(iso).toLocaleDateString(LANG === 'en' ? 'en-GB' : 'fr-FR'); } catch (e) { return T('none'); }
  }

  // ── Chargement initial ──────────────────────────────────────────────
  async function boot() {
    applyStaticI18n();
    const [sc, ds] = await Promise.all([api('/mastery/scale'), api('/domains/scale')]);
    state.scale = sc.mastery || {}; state.notAssessed = sc.not_assessed || T('not_assessed');
    state.domScale = (ds && ds.scale) || {};
    bindDrawer();
    // 404 sur cet appel = « ce compte n'encadre personne et n'a pas de
    // développeur de compétences ». C'est un état, pas une panne : il se
    // raconte à l'écran, il ne se signale pas par un message d'erreur.
    const mgr = await api('/competences/current_user_manager', undefined, true);
    if (!mgr || !mgr.manager_id) {
      $('#cv2-mgr-name').textContent = T('no_dev');
      $('#cv2-mgr-av').textContent = '—';
      $('#cv2-collab-empty').classList.remove('hidden');
      montrerVide(T('no_dev_hint'));
      return;
    }
    $('#cv2-mgr-name').textContent = mgr.manager_name || '—';
    $('#cv2-mgr-av').textContent = initials(...String(mgr.manager_name || '').split(' ')) || 'M';
    const collabs = await api('/competences/collaborators/' + mgr.manager_id);
    renderCollabs(Array.isArray(collabs) ? collabs : []);
  }

  function renderCollabs(list) {
    const ul = $('#cv2-collab'); ul.innerHTML = '';
    if (!list.length) { $('#cv2-collab-empty').classList.remove('hidden'); return; }
    $('#cv2-collab-empty').classList.add('hidden');
    list.forEach(u => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="av">${esc(initials(u.first_name, u.last_name))}</span>` +
        `<span>${esc(u.first_name)} ${esc(u.last_name)}</span><span class="chev">›</span>`;
      li.onclick = () => selectCollab(u, li);
      ul.appendChild(li);
    });
  }

  async function selectCollab(u, li) {
    document.querySelectorAll('.cv2-collab li').forEach(x => x.classList.remove('active'));
    li.classList.add('active');
    state.userId = u.id; state.userName = `${u.first_name} ${u.last_name}`;
    $('#cv2-sub').textContent = state.userName;
    const r = await api('/competences/get_user_roles/' + u.id);
    const roles = (r && r.roles) || [];
    $('#cv2-roles-lbl').classList.toggle('hidden', !roles.length);
    renderRoles(roles);
  }

  function renderRoles(roles) {
    const box = $('#cv2-roles'); box.innerHTML = '';
    if (!roles.length) { montrerVide(T('pick_role')); return; }
    roles.forEach((ro, i) => {
      const b = document.createElement('button'); b.className = 'cv2-role'; b.textContent = ro.name;
      b.onclick = () => {
        document.querySelectorAll('.cv2-role').forEach(x => x.classList.remove('active'));
        b.classList.add('active'); selectRole(ro);
      };
      box.appendChild(b);
      if (i === 0) b.click();
    });
  }

  async function selectRole(ro) {
    state.roleId = ro.id; state.roleName = ro.name; state.filtre = null;
    renderDashboard(await api(`/mastery/dashboard/${state.userId}/${ro.id}`));
  }

  function montrerVide(msg) {
    $('#cv2-liste').classList.add('hidden');
    $('#cv2-bilan').classList.add('hidden');
    const ph = $('#cv2-placeholder'); ph.classList.remove('hidden'); ph.textContent = msg;
  }

  // ══ La jauge ════════════════════════════════════════════════════════
  // Quatre pas = les niveaux 1 à 4. Le niveau 0 « Non démontré » est une jauge
  // VIDE — c'est exactement ce qu'il veut dire. Non évalué (null) se dessine en
  // creux : une absence, pas un zéro.
  function jauge(niveau, requis, couleur) {
    const inconnu = niveau === null || niveau === undefined;
    let pas = '';
    for (let i = 1; i <= 4; i++) {
      const cls = [];
      if (inconnu) cls.push('vide');
      else if (niveau >= i) cls.push('on');
      if (requis === i) cls.push('cible');
      pas += `<i class="${cls.join(' ')}"></i>`;
    }
    return `<span class="cv2-pas">${pas}</span>`;
  }

  function categorie(a) {
    if (!a.n_results) return 'setup';
    if (a.demonstrated_level === null || a.demonstrated_level === undefined) return 'todo';
    if (a.demonstrated_level < 2) return 'gap';
    if (a.required_level !== null && a.required_level !== undefined
        && a.demonstrated_level < a.required_level) return 'gap';
    return 'held';
  }

  const COULEUR_CAT = { held: 'green', gap: 'orange', todo: 'grey', setup: 'grey' };

  // ══ Le bandeau de situation ═════════════════════════════════════════
  // Quatre compteurs qui sont aussi les filtres de la liste : « montre-moi les
  // trois en écart » est la question qu'on se pose en arrivant.
  function renderBilan(rows) {
    const box = $('#cv2-bilan'); box.innerHTML = '';
    const compte = { held: 0, gap: 0, todo: 0, setup: 0 };
    rows.forEach(a => { compte[categorie(a)] += 1; });
    const tuiles = [
      ['held', T('b_held'), 'green'], ['gap', T('b_gap'), 'orange'],
      ['todo', T('b_todo'), 'blue'], ['setup', T('b_setup'), 'grey'],
    ];
    tuiles.forEach(([cle, libelle, teinte]) => {
      if (!compte[cle] && state.filtre !== cle) return;      // pas de case vide à compter
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `cv2-tuile cv2-tuile--${teinte}` + (state.filtre === cle ? ' is-on' : '');
      b.innerHTML = `<div class="n"><span class="pt"></span>${compte[cle]}</div><div class="k">${esc(libelle)}</div>`;
      b.title = state.filtre === cle ? T('filter_off') : libelle;
      b.onclick = () => { state.filtre = state.filtre === cle ? null : cle; renderDashboard(null, true); };
      box.appendChild(b);
    });
    box.classList.toggle('hidden', !box.children.length);
  }

  // ══ La liste des activités ══════════════════════════════════════════
  function renderDashboard(d, reutiliser) {
    if (!reutiliser) state.rows = (d && d.activities) || [];
    const rows = state.rows;
    if (!rows.length) { montrerVide(T('no_activities')); return; }
    $('#cv2-placeholder').classList.add('hidden');
    $('#cv2-liste').classList.remove('hidden');
    renderBilan(rows);

    const box = $('#cv2-lignes'); box.innerHTML = '';
    const visibles = state.filtre ? rows.filter(a => categorie(a) === state.filtre) : rows;
    if (!visibles.length) {
      box.innerHTML = `<div class="cv2-vide">${esc(T('no_match'))}</div>`;
      return;
    }
    visibles.forEach(a => box.appendChild(ligneActivite(a)));
  }

  function ligneActivite(a) {
    const cat = categorie(a);
    const el = document.createElement('div');
    el.className = 'cv2-ligne';
    el.innerHTML = `
      <div>
        <div class="cv2-nom">${esc(a.activity_name)}</div>
        ${a.competence ? `<div class="cv2-comp-line" title="${esc(a.competence)}">${esc(a.competence)}</div>` : ''}
        <div class="cv2-meta">${metaActivite(a)}</div>
      </div>
      <div>${celluleNiveau(a, cat)}</div>
      <div class="cv2-cell-tech">${celluleTech(a.technicity)}</div>
      <div class="cv2-cell-act">
        <button class="btn btn-sm ${cat === 'setup' ? 'btn-todo' : 'btn-primary'}">
          ${esc(cat === 'setup' ? T('configure_short') : T('evaluate'))}</button>
      </div>`;
    el.querySelector('button').onclick = () => openDrawer(a);
    return el;
  }

  // Une phrase, à la place de deux colonnes de nombres isolés : « 1/2 » dans une
  // case intitulée « Résultats » ne disait pas de quoi il s'agissait.
  function metaActivite(a) {
    if (!a.n_results) return `<span>${esc(T('m_toqualify'))}</span>`;
    const bouts = [];
    const nEval = (a.n_evaluated === null || a.n_evaluated === undefined) ? null : a.n_evaluated;
    const mot = n => (n === 1 ? T('m_result_one') : T('m_result_many'));
    const part = n => (n === 1 ? T('m_eval_one') : T('m_eval_many'));
    if (nEval !== null && nEval < a.n_results) {
      bouts.push(`<span>${nEval} ${esc(T('m_partial'))} ${a.n_results} ${esc(mot(a.n_results))} ${esc(part(a.n_results))}</span>`);
    } else {
      bouts.push(`<span>${a.n_results} ${esc(mot(a.n_results))}</span>`);
    }
    bouts.push(a.last_evaluation
      ? `<span>${esc(T('m_last'))} ${esc(fmtDate(a.last_evaluation))}</span>`
      : `<span>${esc(T('m_never'))}</span>`);
    return bouts.join('<span class="sep">·</span>');
  }

  // Requis, démontré et écart tenaient trois colonnes ; ils tiennent ici un seul
  // objet, parce qu'ils ne veulent rien dire séparément. Le niveau requis n'est
  // pas ÉCRIT dans la ligne : il est marqué SUR la jauge (la légende de l'en-tête
  // dit ce qu'est ce repère), et l'épeler prenait toute la largeur de la case.
  function celluleNiveau(a, cat) {
    const teinte = a.color || COULEUR_CAT[cat] || 'grey';
    const req = (a.required_level === null || a.required_level === undefined) ? null : a.required_level;
    const inconnu = a.demonstrated_level === null || a.demonstrated_level === undefined;
    // La bulle porte les deux niveaux en toutes lettres : la case est étroite,
    // le libellé peut être coupé, et c'est l'information de la ligne.
    const titre = [
      `${T('c_demonstrated')} : ${inconnu ? state.notAssessed : a.demonstrated_label}`,
      req === null ? '' : `${T('target_short')} : ${req} · ${levelName(req)}`,
    ].filter(Boolean).join(' — ');
    return `<div class="cv2-jauge cv2-j--${esc(teinte)}" title="${esc(titre)}">
        ${jauge(a.demonstrated_level, req, teinte)}
        <span class="cv2-jauge-txt">
          <span class="lv">${esc(inconnu ? state.notAssessed : a.demonstrated_label)}</span>
        </span>
        ${badgeEcart(a.gap)}
      </div>`;
  }

  // Seul un écart NÉGATIF porte un badge : c'est le cas qui demande une action.
  // Un dépassement se voit déjà sur la jauge (la barre passe le repère), et un
  // badge sur chaque ligne aurait mangé la largeur du libellé de niveau.
  function badgeEcart(gap) {
    if (gap === null || gap === undefined || gap >= 0) return '';
    return `<span class="cv2-ecart neg">${gap}</span>`;
  }

  function chip(color, label) { return `<span class="chip ${esc(color)}"><span class="lv"></span>${esc(label)}</span>`; }
  const dash = () => `<span class="cv2-dash">${T('none')}</span>`;
  function celluleTech(status) {
    if (status === 'gap') return chip('orange', T('tech_gap'));
    if (status === 'ok') return chip('green', T('tech_ok'));
    return dash();
  }

  // ══ Fenêtre d'évaluation ════════════════════════════════════════════
  function bindDrawer() {
    $('#cv2-drawer-close').onclick = closeDrawer;
    $('#cv2-overlay').onclick = closeDrawer;
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && $('#cv2-drawer').classList.contains('open')) closeDrawer();
    });
  }
  function closeDrawer() { $('#cv2-drawer').classList.remove('open'); $('#cv2-overlay').classList.remove('open'); }

  function setFooter(buttons) {
    const f = $('#cv2-footer'); f.innerHTML = '';
    // Sans bouton, pas de pied : une bande grise vide sous le contenu donne
    // l'impression qu'il manque quelque chose.
    f.classList.toggle('hidden', !buttons.length);
    buttons.forEach(b => {
      const el = document.createElement('button');
      el.className = 'btn ' + b.cls; el.textContent = b.label; el.onclick = b.on;
      if (b.id) el.id = b.id;
      f.appendChild(el);
    });
  }

  function openDrawer(row) {
    state.activity = row;
    $('#cv2-drawer-title').textContent = row.activity_name;
    $('#cv2-drawer-role').textContent = `${state.userName} · ${state.roleName}`;
    $('#cv2-drawer').classList.add('open'); $('#cv2-overlay').classList.add('open');
    $('#cv2-drawer-body').scrollTop = 0;
    showEvaluation();
  }

  async function showEvaluation() {
    showBusy();
    const st = await api(`/mastery/activity/${state.userId}/${state.activity.activity_id}?role_id=${state.roleId}`);
    state.lastState = st;
    renderResults(st);
  }

  function renderResults(st) {
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const aEvaluer = !!(st.results && st.results.length);

    if (state.activity.competence) {
      const c = document.createElement('div'); c.className = 'cv2-comp';
      c.innerHTML = `<span class="tag">${esc(T('competence'))}</span>${esc(state.activity.competence)}`;
      body.appendChild(c);
    }
    body.appendChild(synthese(st));

    const sec = document.createElement('div'); sec.className = 'cv2-section';
    body.appendChild(sec);

    if (!aEvaluer) {
      // Activité pas encore configurée : aucun résultat qualifié, rien à noter.
      const setup = document.createElement('div'); setup.className = 'cv2-setup';
      setup.innerHTML = `<div class="st">${esc(T('not_configured'))}</div><div class="sd">${esc(T('setup_intro'))}</div>`;
      const b = document.createElement('button'); b.className = 'btn btn-primary'; b.textContent = T('setup_btn');
      b.onclick = () => showQualify(b);
      setup.appendChild(b);
      sec.appendChild(setup);
      sec.appendChild(technicitySection());
      // Ni « Enregistrer » ni « Diagnostiquer » : il n'y a rien à enregistrer,
      // et deux boutons inertes en pied de fenêtre font douter de tout l'écran.
      setFooter([]);
      return;
    }

    // Bannière de guidage juste après la configuration des sorties.
    if (state.justConfigured) {
      state.justConfigured = false;
      const ok = document.createElement('div'); ok.className = 'cv2-ok';
      ok.textContent = T('configured_go_eval'); sec.appendChild(ok);
    }
    const h = document.createElement('div'); h.className = 'cv2-evalhead';
    h.innerHTML = `<div class="eh">${esc(T('eval_of'))} ${esc(state.userName)}</div>` +
      `<div class="cv2-evalsub">${esc(T('eval_hint'))}</div>`;
    sec.appendChild(h);
    st.results.forEach(r => sec.appendChild(resultCard(r, st.required_level)));
    sec.appendChild(technicitySection());

    const pied = [{ cls: 'btn-primary', label: T('save_eval'), on: saveEvaluation, id: 'cv2-save-btn' }];
    if (aUnEcart(st)) pied.unshift({ cls: 'btn-ghost', label: T('diagnose'), on: showDiagnostic });
    setFooter(pied);
  }

  // Le diagnostic ne s'offre que s'il y a quelque chose à diagnostiquer : sinon
  // le bouton menait à un écran qui répond « aucun résultat en écart ».
  function aUnEcart(st) {
    const req = st.required_level;
    return (st.results || []).some(r => r.demonstrated_level !== null && r.demonstrated_level !== undefined
      && (r.demonstrated_level < 2 || (req !== null && req !== undefined && r.demonstrated_level < req)));
  }

  // Synthèse : requis (modifiable) · démontré · écart, sur UNE ligne. C'étaient
  // trois cellules encadrées dans une carte encadrée dans la fenêtre.
  function synthese(st) {
    const g = document.createElement('div'); g.className = 'cv2-synth';
    const req = (st.required_level === null || st.required_level === undefined) ? null : st.required_level;

    const cr = document.createElement('div'); cr.className = 'sm';
    cr.innerHTML = `<div class="k">${esc(T('c_required'))}</div>
      <div class="v">
        <div class="cv2-jauge cv2-j--blue">${jauge(req, null, 'blue')}
          <span class="cv2-jauge-txt"><span class="lv">${esc(req === null ? T('not_set') : st.required_label)}</span></span>
        </div>
        <button class="cv2-link cv2-reqedit-btn">${esc(T('edit'))}</button>
      </div>`;
    const row = document.createElement('div'); row.className = 'cv2-reqedit hidden';
    [null, 0, 1, 2, 3, 4].forEach(lv => {
      const b = document.createElement('button');
      b.textContent = lv === null ? T('not_set') : lv;
      if (req === lv) b.classList.add('sel');
      b.onclick = () => setRequired(lv);
      row.appendChild(b);
    });
    cr.appendChild(row);
    cr.querySelector('.cv2-reqedit-btn').onclick = () => row.classList.toggle('hidden');
    g.appendChild(cr);

    const inconnu = st.global_level === null || st.global_level === undefined;
    const cd = document.createElement('div'); cd.className = 'sm';
    cd.innerHTML = `<div class="k">${esc(T('c_demonstrated'))} (min)</div>
      <div class="v"><div class="cv2-jauge cv2-j--${esc(st.color || 'grey')}">
        ${jauge(st.global_level, req, st.color)}
        <span class="cv2-jauge-txt"><span class="lv">${esc(inconnu ? state.notAssessed : st.global_label)}</span></span>
      </div></div>`;
    g.appendChild(cd);

    const cg = document.createElement('div'); cg.className = 'sm';
    const badge = badgeEcart(st.gap);
    cg.innerHTML = `<div class="k">${esc(T('c_gap'))}</div>
      <div class="v">${badge || (st.gap === 0 ? '<span class="cv2-ecart zero">0</span>' : dash())}</div>`;
    g.appendChild(cg);
    return g;
  }

  // ── La carte d'un RÉSULTAT ────────────────────────────────────────────
  // ⚠️ C'étaient SIX barres pleine largeur empilées par résultat. L'échelle
  // 0→4 est ordonnée : elle se dessine en ligne, et le REQUIS est marqué
  // dessus — c'est là qu'on choisit, c'est là qu'il faut voir la cible.
  function resultCard(r, requis) {
    const card = document.createElement('div');
    card.className = 'cv2-res' + (r.demonstrated_level === null || r.demonstrated_level === undefined ? '' : ' est-note');
    card.dataset.dataId = r.data_id;
    const req = (requis === null || requis === undefined) ? null : requis;

    let paliers = '';
    for (let lv = 0; lv <= 4; lv++) {
      const sel = r.demonstrated_level === lv ? ' sel' : '';
      const cible = req === lv ? ' cible' : '';
      const bulle = levelName(lv) + (req === lv ? ` — ${T('target_short')}` : '');
      paliers += `<button type="button" class="cv2-niv${sel}${cible}" data-lv="${lv}"
        title="${esc(bulle)}">${lv}</button>`;
    }
    const efface = (r.demonstrated_level === null || r.demonstrated_level === undefined) ? ' sel' : '';
    const preuve = r.evidence || '';

    card.innerHTML = `
      <div class="rtete">
        <div class="rname">${esc(r.name)}
          ${r.minimum_performance_text ? `<div class="rstd">${esc(T('std'))} : ${esc(r.minimum_performance_text)}</div>` : ''}
        </div>
      </div>
      <div class="cv2-echelle">
        ${paliers}
        <button type="button" class="cv2-gomme${efface}" data-lv="">${esc(T('erase'))}</button>
      </div>
      <div class="cv2-lu"></div>
      ${r.self_level !== null && r.self_level !== undefined
        ? `<div class="cv2-auto">${esc(T('self'))} : ${r.self_level} · ${esc(levelName(r.self_level))}</div>` : ''}
      <button type="button" class="cv2-preuve-btn${preuve ? ' hidden' : ''}">${esc(T('add_evidence'))}</button>
      <textarea class="cv2-ev${preuve ? '' : ' hidden'}" placeholder="${esc(T('evidence_ph'))}">${esc(preuve)}</textarea>`;

    const lu = card.querySelector('.cv2-lu');
    const ecrireLecture = () => {
      const sel = card.querySelector('[data-lv].sel');
      const brut = sel ? sel.dataset.lv : '';
      if (brut === '') { lu.className = 'cv2-lu aprendre'; lu.textContent = T('pick_level'); return; }
      const lv = +brut;
      const sous = req !== null && lv < req;
      lu.className = 'cv2-lu';
      lu.innerHTML = `<span class="num">${lv}</span>${esc(levelName(lv))}` +
        (req === null ? '' : `<span class="rap${sous ? ' sous' : ''}">${esc(T('target_short'))} : ${req}</span>`);
    };
    ecrireLecture();

    card.querySelectorAll('[data-lv]').forEach(b => b.onclick = () => {
      card.querySelectorAll('[data-lv]').forEach(x => x.classList.remove('sel'));
      b.classList.add('sel');
      card.classList.toggle('est-note', b.dataset.lv !== '');
      ecrireLecture();
    });
    const bp = card.querySelector('.cv2-preuve-btn'), ta = card.querySelector('.cv2-ev');
    bp.onclick = () => { bp.classList.add('hidden'); ta.classList.remove('hidden'); ta.focus(); };
    return card;
  }

  async function saveEvaluation() {
    const cards = document.querySelectorAll('#cv2-drawer-body .cv2-res');
    const btn = $('#cv2-save-btn'); if (btn) btn.disabled = true;
    for (const c of cards) {
      const sel = c.querySelector('[data-lv].sel');
      if (!sel) continue;
      const raw = sel.dataset.lv;
      await api('/mastery/evaluate', {
        method: 'POST',
        body: JSON.stringify({
          user_id: state.userId, activity_id: state.activity.activity_id, data_id: +c.dataset.dataId,
          evaluator: '2', mastery_level: raw === '' ? null : +raw,
          evidence: c.querySelector('.cv2-ev').value, role_id: state.roleId,
        }),
      });
    }
    toast(T('saved'));
    await showEvaluation();                 // rafraîchit la fenêtre + le pied
    await refreshDashboard();
  }

  async function setRequired(lvl) {
    await api('/mastery/required', {
      method: 'POST',
      body: JSON.stringify({
        activity_id: state.activity.activity_id, role_id: state.roleId, required_mastery_level: lvl }),
    });
    toast(T('req_set'));
    await showEvaluation();
    await refreshDashboard();
  }

  // Le tableau de fond doit suivre la fenêtre : on y garde l'activité ouverte à
  // jour, sinon « Évaluer » rouvrirait la version d'avant l'enregistrement.
  async function refreshDashboard() {
    const d = await api(`/mastery/dashboard/${state.userId}/${state.roleId}`);
    if (d && d.activities) {
      renderDashboard(d);
      const row = d.activities.find(a => a.activity_id === state.activity.activity_id);
      if (row) state.activity = row;
    }
  }

  // ── Technicité : domaines techniques (axe séparé de la maîtrise, CDC 4) ──────
  function domSelect(val, onchange) {
    const s = document.createElement('select'); s.className = 'cv2-domsel';
    const opts = [['', '—']].concat(Object.keys(state.domScale).map(k => [k, `${k} · ${state.domScale[k]}`]));
    opts.forEach(([v, l]) => {
      const o = document.createElement('option'); o.value = v; o.textContent = l;
      if ((val === null || val === undefined) ? v === '' : String(val) === v) o.selected = true;
      s.appendChild(o);
    });
    s.onchange = () => onchange(s.value === '' ? null : +s.value);
    return s;
  }
  function technicitySection() {
    const det = document.createElement('details'); det.className = 'cv2-tech';
    det.innerHTML = `<summary><span class="ti"><svg width="15" height="15" viewBox="0 0 24 24" fill="none">
      <path d="M12 3l7 4v6c0 4-3 6.5-7 8-4-1.5-7-4-7-8V7l7-4z" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M9 12l2 2 4-4" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
      ${esc(T('tech_title'))}<span class="caret">›</span></summary>
      <div class="tbody"><div class="texp">${esc(T('tech_exp'))}</div><div class="cv2-domlist"></div><div class="cv2-domadd"></div></div>`;
    let loaded = false;
    det.addEventListener('toggle', async () => { if (det.open && !loaded) { loaded = true; await loadTech(det); } });
    return det;
  }
  async function loadTech(det) {
    const aid = state.activity.activity_id;
    const [dom, all] = await Promise.all([
      api(`/domains/activity/${aid}?role_id=${state.roleId}&user_id=${state.userId}`), api('/domains/list')]);
    renderDomList(det.querySelector('.cv2-domlist'), aid, (dom && dom.domains) || []);
    renderDomAdd(det, aid, (all && all.domains) || [], (dom && dom.domains) || []);
  }
  function renderDomList(list, aid, domains) {
    list.innerHTML = '';
    if (!domains.length) { list.innerHTML = `<div class="cv2-emptydom">${esc(T('tech_empty'))}</div>`; return; }
    domains.forEach(d => {
      const row = document.createElement('div'); row.className = 'cv2-domrow';
      const dn = document.createElement('div'); dn.className = 'dn'; dn.textContent = d.name; row.appendChild(dn);
      const rq = document.createElement('div'); rq.className = 'df';
      rq.innerHTML = `<span class="fl">${esc(T('tech_required'))}</span>`;
      rq.appendChild(domSelect(d.required_level, v => setDom('/domains/required',
        { role_id: state.roleId, activity_id: aid, domain_id: d.domain_id, required_level: v }, list, aid)));
      const dm = document.createElement('div'); dm.className = 'df';
      dm.innerHTML = `<span class="fl">${esc(T('tech_demonstrated'))}</span>`;
      dm.appendChild(domSelect(d.demonstrated_level, v => setDom('/domains/user_level',
        { user_id: state.userId, domain_id: d.domain_id, demonstrated_level: v }, list, aid)));
      row.appendChild(rq); row.appendChild(dm);
      if (d.gap !== null && d.gap !== undefined) {
        const g = document.createElement('div');
        g.innerHTML = d.gap < 0 ? chip('red', d.gap) : chip('green', '+' + d.gap);
        row.appendChild(g);
      }
      list.appendChild(row);
    });
  }
  async function setDom(url, body, list, aid) {
    const r = await api(url, { method: 'POST', body: JSON.stringify(body) });
    if (r.__error) return;
    const dom = await api(`/domains/activity/${aid}?role_id=${state.roleId}&user_id=${state.userId}`);
    renderDomList(list, aid, (dom && dom.domains) || []);
    refreshDashboard();
  }
  function renderDomAdd(det, aid, allDomains, linked) {
    const add = det.querySelector('.cv2-domadd'); add.innerHTML = '';
    const linkedIds = new Set(linked.map(d => d.domain_id));
    const avail = allDomains.filter(d => !linkedIds.has(d.id));
    if (avail.length) {
      const sel = document.createElement('select'); sel.className = 'cv2-domsel';
      sel.innerHTML = `<option value="">${esc(T('tech_pick'))}</option>` +
        avail.map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
      const b = document.createElement('button'); b.className = 'btn btn-ghost btn-sm'; b.textContent = T('tech_link');
      b.onclick = async () => { if (!sel.value) return; await linkDom(aid, +sel.value); await loadTech(det); };
      add.appendChild(sel); add.appendChild(b);
    }
    const inp = document.createElement('input'); inp.placeholder = T('tech_add_ph');
    const cb = document.createElement('button'); cb.className = 'btn btn-primary btn-sm'; cb.textContent = '＋';
    cb.onclick = async () => {
      const nm = inp.value.trim(); if (!nm) return;
      const r = await api('/domains/create', { method: 'POST', body: JSON.stringify({ name_fr: nm }) });
      if (r && r.id) { await linkDom(aid, r.id); inp.value = ''; await loadTech(det); }
    };
    add.appendChild(inp); add.appendChild(cb);
  }
  async function linkDom(aid, did) {
    await api(`/domains/activity/${aid}/link`, { method: 'POST', body: JSON.stringify({ domain_id: did }) });
    refreshDashboard();
  }

  // ── Diagnostic de l'écart (CDC 6.5-6.9) ─────────────────────────────
  async function showDiagnostic() {
    showBusy();
    const st = state.lastState
      || await api(`/mastery/activity/${state.userId}/${state.activity.activity_id}?role_id=${state.roleId}`);
    const req = st.required_level;
    const gapRes = (st.results || []).filter(r => r.demonstrated_level !== null
      && (r.demonstrated_level < 2 || (req !== null && req !== undefined && r.demonstrated_level < req)));
    const fams = await api('/diagnostic/families');
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const sec = document.createElement('div'); sec.className = 'cv2-section'; body.appendChild(sec);
    if (!gapRes.length) {
      const p = document.createElement('div'); p.className = 'cv2-ok'; p.textContent = T('no_gap');
      sec.appendChild(p);
    }
    for (const r of gapRes) sec.appendChild(await diagBlock(r, (fams && fams.families) || []));
    setFooter([{ cls: 'btn-quiet', label: T('back'), on: showEvaluation }]);
  }

  async function diagBlock(result, families) {
    const st = await api(`/diagnostic/${state.userId}/${state.activity.activity_id}/${result.data_id}?role_id=${state.roleId}`);
    const wrap = document.createElement('div'); wrap.className = 'cv2-diagres'; wrap.dataset.dataId = result.data_id;
    const selected = new Set(st.families || []);
    wrap.innerHTML = `
      <div class="dtitle"><span>${esc(st.result.name)}</span>
        ${chip(result.demonstrated_level < 2 ? 'red' : 'orange', st.status.label)}</div>
      <div class="cv2-diagsub">${esc(st.demonstrated_label)} (${esc(T('dem'))}) · ${esc(st.required_label)} (${esc(T('req'))})</div>
      <div class="cv2-question">${esc(T('cause_q'))}</div>
      <div class="cv2-fams"></div>
      <div class="cv2-caps hidden"></div>
      <div class="cv2-plan"></div>`;
    const famsBox = wrap.querySelector('.cv2-fams');
    families.forEach(f => {
      const el = document.createElement('div');
      el.className = 'cv2-fam' + (selected.has(f.code) ? ' sel' : ''); el.dataset.code = f.code;
      el.innerHTML = `<div class="fh"><span class="bx"></span>${esc(f.label)}</div><div class="fd">${esc(f.description)}</div>`;
      el.onclick = () => {
        el.classList.toggle('sel');
        selected.has(f.code) ? selected.delete(f.code) : selected.add(f.code);
        onDiagChange(wrap, st, selected);
      };
      famsBox.appendChild(el);
    });
    onDiagChange(wrap, st, selected, true);
    return wrap;
  }

  async function onDiagChange(wrap, st, selected, initial) {
    const capsBox = wrap.querySelector('.cv2-caps'), planBox = wrap.querySelector('.cv2-plan');
    if (!initial) {
      await api('/diagnostic/save', {
        method: 'POST',
        body: JSON.stringify({
          user_id: state.userId, activity_id: state.activity.activity_id,
          data_id: +wrap.dataset.dataId, families: [...selected] }),
      });
    }
    // Capacité à agir → afficher les capacités reliées + bouton plan
    if (selected.has(st.individual_family)) {
      capsBox.classList.remove('hidden');
      capsBox.innerHTML = `<div class="cv2-capstitle">${esc(T('linked_caps'))}</div>` +
        (st.capabilities.length ? st.capabilities.map(c =>
          `<div class="cv2-cap"><div><span class="ct">${esc(c.type_label)}</span><div>${esc(c.label || '—')}</div></div>
           <div class="lvls">${c.demonstrated_level === null ? T('none') : c.demonstrated_level}
             / ${c.required_level === null ? T('none') : c.required_level}</div></div>`).join('')
          : `<div class="cv2-emptydom">${esc(T('none'))}</div>`);
      const btn = document.createElement('button');
      btn.className = 'btn btn-primary btn-sm'; btn.style.marginTop = '10px'; btn.textContent = T('gen_plan');
      btn.onclick = () => genPlan(wrap, btn);
      capsBox.appendChild(btn);
    } else { capsBox.classList.add('hidden'); planBox.innerHTML = ''; }
  }

  async function genPlan(wrap, btn) {
    btn.disabled = true; btn.textContent = T('gen');
    const j = await api('/diagnostic/plan', {
      method: 'POST',
      body: JSON.stringify({
        user_id: state.userId, activity_id: state.activity.activity_id,
        data_id: +wrap.dataset.dataId, role_id: state.roleId }),
    });
    const planBox = wrap.querySelector('.cv2-plan'); planBox.innerHTML = '';
    btn.disabled = false; btn.textContent = T('gen_plan');
    if (j.no_individual_plan) { planBox.innerHTML = `<div class="cv2-noplan">${esc(j.message)}</div>`; return; }
    const items = j.plan || [];
    if (!items.length) {
      planBox.innerHTML = `<div class="cv2-noplan">${esc(j.source && j.source !== 'AI' ? 'IA indisponible.' : T('none'))}</div>`;
      return;
    }
    const liste = items.map(it => {
      const sit = it.work_situations
        ? `<div>${esc(Array.isArray(it.work_situations) ? it.work_situations.join(', ') : it.work_situations)}</div>` : '';
      const et = it.steps
        ? `<div class="steps">${esc(Array.isArray(it.steps) ? it.steps.join(' · ') : it.steps)}</div>` : '';
      return `<div class="cv2-planitem"><b>${esc(it.development_objective || '')}</b>` +
        `${it.target_level ? ` → ${esc(it.target_level)}` : ''}${sit}${et}</div>`;
    }).join('');
    planBox.innerHTML = `<div class="cv2-plantitle">${esc(T('plan_title'))}</div>${liste}`;
  }

  // ── Configuration d'une activité : qualifier les sorties → compétence ───
  async function showQualify(btn) {
    if (btn) { btn.disabled = true; btn.textContent = T('gen'); }
    const aid = state.activity.activity_id;
    showBusy(T('configuring'));
    const [outs, ana] = await Promise.all([api(`/qualify/outputs/${aid}`), api(`/qualify/analyze/${aid}`, { method: 'POST' })]);
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const sec = document.createElement('div'); sec.className = 'cv2-section'; body.appendChild(sec);
    const panel = document.createElement('div'); panel.className = 'cv2-setup';
    panel.innerHTML = `<div class="st">${esc(T('qualify_title'))}</div><div class="sd">${esc(T('qualify_desc'))}</div>`;
    const outputs = outs.outputs || [], labels = outs.labels || {};
    if (!outputs.length) {
      panel.insertAdjacentHTML('beforeend',
        `<div class="cv2-warn" style="margin:0">${esc((ana && ana.warning) || T('no_out'))}</div>`);
      sec.appendChild(panel);
      setFooter([{ cls: 'btn-quiet', label: T('back'), on: showEvaluation }]);
      return;
    }
    const props = {}; (ana.outputs || []).forEach(p => props[p.data_id] = p);
    outputs.forEach(o => {
      const p = props[o.data_id] || {}, nature = o.nature || p.suggested_nature || '';
      const row = document.createElement('div'); row.className = 'cv2-qz'; row.dataset.dataId = o.data_id;
      const opts = `<option value="">${esc(T('to_qualify'))}</option>` +
        Object.keys(labels).map(k => `<option value="${esc(k)}" ${nature === k ? 'selected' : ''}>${esc(labels[k])}</option>`).join('');
      const mv = o.minimum_performance_text || p.suggested_minimum_performance || '';
      row.innerHTML = `<div style="flex:1">
          <div class="qn">${esc(o.name)}</div>${p.justification ? `<div class="qj">${esc(p.justification)}</div>` : ''}
          <input class="cv2-minperf ${nature === 'RESULT' ? '' : 'hidden'}" placeholder="${esc(T('min_perf_ph'))}" value="${esc(mv)}">
        </div>
        <select class="cv2-natsel">${opts}</select>`;
      const sel = row.querySelector('.cv2-natsel'), mp = row.querySelector('.cv2-minperf');
      sel.onchange = () => mp.classList.toggle('hidden', sel.value !== 'RESULT');
      panel.appendChild(row);
    });
    sec.appendChild(panel);
    setFooter([{ cls: 'btn-quiet', label: T('back'), on: showEvaluation },
               { cls: 'btn-primary', label: T('validate_analysis'), on: () => saveQualify() }]);
  }

  async function saveQualify() {
    const aid = state.activity.activity_id;
    const rows = [...document.querySelectorAll('#cv2-drawer-body .cv2-qz')];
    const outputs = rows.map(r => {
      const sel = r.querySelector('.cv2-natsel'), mp = r.querySelector('.cv2-minperf');
      return { data_id: +r.dataset.dataId, nature: sel.value || null,
               minimum_performance_text: mp ? mp.value : '', source: 'MANUAL' };
    });
    // Garde-fou : sans aucune sortie « Résultat », il n'y a rien à évaluer → on prévient et on reste.
    if (!outputs.some(o => o.nature === 'RESULT')) {
      let w = $('#cv2-need-result');
      if (!w) {
        w = document.createElement('div'); w.id = 'cv2-need-result'; w.className = 'cv2-warn';
        const panel = $('#cv2-drawer-body .cv2-setup'); (panel || $('#cv2-drawer-body')).prepend(w);
      }
      w.textContent = T('need_result'); w.scrollIntoView({ block: 'nearest' });
      return;
    }
    showBusy(T('configuring'));
    const save = await api(`/qualify/save/${aid}`, { method: 'POST', body: JSON.stringify({ outputs }) });
    if (save.__error) { return showQualify(); }
    // compétence principale + liens S/SF/HSC (best effort ; sans clé IA → sautés proprement)
    const comp = await api(`/competence/generate/${aid}`, { method: 'POST' });
    if (comp.competence && (comp.competence.description_fr || comp.competence.description_en)) {
      await api(`/competence/save/${aid}`, {
        method: 'POST',
        body: JSON.stringify({
          description: (LANG === 'en' ? comp.competence.description_en : comp.competence.description_fr)
            || comp.competence.description_fr || comp.competence.description_en }),
      });
    }
    await api(`/competence/result_links/generate/${aid}`, { method: 'POST' });
    toast(T('setup_done'));
    await refreshDashboard();
    state.justConfigured = true;
    showEvaluation();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
