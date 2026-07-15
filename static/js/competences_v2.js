/* competences_v2.js — Refonte page Compétences (V1.1, CDC 6).
   Parcours : Collaborateur → Rôle → Activités → Résultats → (écart) → Diagnostic → Plan.
   Le manager évalue par RÉSULTAT ; le niveau global d'activité = min des résultats. */
(function () {
  'use strict';
  const LANG = window.OPTIQ_LANG === 'en' ? 'en' : 'fr';
  const $ = s => document.querySelector(s);

  const I18N = {
    fr: {
      manager: 'Manager', collaborators: 'Collaborateurs', no_collab: 'Aucun collaborateur.',
      title: 'Compétences', pick_collab: 'Sélectionnez un collaborateur pour commencer.',
      pick_collab2: 'Sélectionnez un collaborateur puis un rôle.',
      c_activity: 'Activité', c_required: 'Niveau requis', c_demonstrated: 'Niveau démontré',
      c_gap: 'Écart', c_results: 'Résultats', c_last: 'Dernière éval.', c_tech: 'Technicité', tech_gap: 'Écart',
      competence: 'Compétence principale', analyze_gap: "Analyser l'écart",
      save_eval: "Enregistrer l'évaluation", evaluate: 'Évaluer', not_assessed: 'Non évalué',
      no_result: "Aucun résultat qualifié pour cette activité. Qualifiez d'abord les sorties.",
      std: 'Standard minimal', self: 'Auto-évaluation', saved: 'Évaluation enregistrée',
      no_activities: 'Aucune activité pour ce rôle.', pick_role: 'Sélectionnez un rôle.',
      none: '—', back: "← Évaluation", save_diag: 'Enregistrer le diagnostic', gen_plan: 'Générer le plan',
      cause_q: "Quelle est la cause de l'écart ?", linked_caps: 'Capacités reliées à ce résultat',
      no_gap: 'Aucun résultat en écart : le niveau requis est tenu.', dem: 'démontré', req: 'requis',
      plan_title: "Plan d'accompagnement", diag_saved: 'Diagnostic enregistré', gen: 'Génération…',
      configure: "Configurer l'activité", qualify_title: 'Qualification des sorties',
      qualify_desc: "L'IA propose une nature pour chaque donnée de sortie. Corrigez si besoin, puis validez. Les données « Résultat » fondent la compétence et servent de base à l'évaluation.",
      validate_analysis: "Valider l'analyse", to_qualify: 'À qualifier', set_required: 'Définir',
      setup_done: 'Activité configurée', min_perf_ph: 'Standard minimal de performance…',
      no_out: "Cette activité n'a aucune donnée de sortie à qualifier.", req_set: 'Niveau requis mis à jour',
      not_set: 'Non défini', analyze: 'Analyser les sorties',
      not_configured: "Activité à configurer avant l'évaluation",
      setup_intro: "Indiquez la nature de chaque donnée de sortie. Les données « Résultat » sont celles dont la tenue démontre la maîtrise : ce sont elles que vous évaluerez ensuite.",
      setup_btn: 'Configurer (qualifier les sorties)',
      eval_of: 'Évaluation de', eval_hint: 'Fixez, pour chaque résultat, le niveau tenu par le collaborateur.',
      collab_level: 'Niveau du collaborateur', ref: 'référence', edit: 'modifier',
      evidence_ph: 'Preuve / commentaire (facultatif)', diagnose: "Diagnostiquer l'écart",
      configuring: 'Configuration en cours… (analyse IA des sorties)', loading: 'Chargement…',
      need_result: "Marquez au moins une sortie comme « Résultat de l'activité » avant de valider : c'est ce niveau que vous évaluerez ensuite.",
      configured_go_eval: 'Sorties qualifiées ✓ — évaluez maintenant le niveau du collaborateur pour chaque résultat, puis enregistrez.',
      req_failed: 'Action impossible (erreur réseau ou serveur).', pick_level: 'Choisissez un niveau ci-dessous',
      roles_label: 'Rôles du collaborateur',
      tech_title: 'Technicité — domaine technique',
      tech_exp: "Axe séparé de la maîtrise : une même activité peut être exercée dans des contextes techniques différents (ex. Plastique / Métal). Fixez le niveau technique requis par le rôle et le niveau démontré par le collaborateur.",
      tech_required: 'Requis', tech_demonstrated: 'Démontré', tech_add_ph: 'Nouveau domaine (ex. Plastique)…',
      tech_link: 'Ajouter', tech_pick: 'Choisir un domaine existant…', tech_empty: 'Aucun domaine technique lié à cette activité.',
    },
    en: {
      manager: 'Manager', collaborators: 'Team members', no_collab: 'No team member.',
      title: 'Skills', pick_collab: 'Select a team member to start.',
      pick_collab2: 'Select a team member then a role.',
      c_activity: 'Activity', c_required: 'Required level', c_demonstrated: 'Demonstrated level',
      c_gap: 'Gap', c_results: 'Results', c_last: 'Last eval.', c_tech: 'Technicity', tech_gap: 'Gap',
      competence: 'Main competence', analyze_gap: 'Analyze gap',
      save_eval: 'Save evaluation', evaluate: 'Evaluate', not_assessed: 'Not assessed',
      no_result: 'No qualified result for this activity. Qualify the outputs first.',
      std: 'Minimum standard', self: 'Self-assessment', saved: 'Evaluation saved',
      no_activities: 'No activity for this role.', pick_role: 'Select a role.',
      none: '—', back: '← Evaluation', save_diag: 'Save diagnosis', gen_plan: 'Generate plan',
      cause_q: 'What is the cause of the gap?', linked_caps: 'Capabilities linked to this result',
      no_gap: 'No result below the required level.', dem: 'demonstrated', req: 'required',
      plan_title: 'Support plan', diag_saved: 'Diagnosis saved', gen: 'Generating…',
      configure: 'Configure activity', qualify_title: 'Output qualification',
      qualify_desc: 'AI suggests a nature for each output. Adjust if needed, then validate. “Result” data grounds the competence and is the basis for evaluation.',
      validate_analysis: 'Validate analysis', to_qualify: 'To qualify', set_required: 'Set',
      setup_done: 'Activity configured', min_perf_ph: 'Minimum performance standard…',
      no_out: 'This activity has no output data to qualify.', req_set: 'Required level updated',
      not_set: 'Not set', analyze: 'Analyze outputs',
      not_configured: 'Activity to configure before evaluation',
      setup_intro: 'Set the nature of each output. “Result” data is what demonstrates mastery: those are what you will evaluate next.',
      setup_btn: 'Configure (qualify outputs)',
      eval_of: 'Evaluation of', eval_hint: 'For each result, set the level the team member holds.',
      collab_level: "Team member's level", ref: 'reference', edit: 'edit',
      evidence_ph: 'Evidence / comment (optional)', diagnose: 'Diagnose the gap',
      configuring: 'Configuring… (AI analysis of outputs)', loading: 'Loading…',
      need_result: 'Mark at least one output as “Activity result” before validating: that is the level you will evaluate next.',
      configured_go_eval: 'Outputs qualified ✓ — now set the team member’s level for each result, then save.',
      req_failed: 'Action failed (network or server error).', pick_level: 'Pick a level below',
      roles_label: "Team member's roles",
      tech_title: 'Technicity — technical domain',
      tech_exp: 'A separate axis from mastery: the same activity can be performed in different technical contexts (e.g. Plastic / Metal). Set the technical level required by the role and the level demonstrated by the team member.',
      tech_required: 'Required', tech_demonstrated: 'Demonstrated', tech_add_ph: 'New domain (e.g. Plastic)…',
      tech_link: 'Add', tech_pick: 'Pick an existing domain…', tech_empty: 'No technical domain linked to this activity.',
    },
  };
  const T = k => (I18N[LANG][k] || k);

  const state = { userId: null, userName: '', roleId: null, roleName: '', scale: {}, notAssessed: 'Non évalué', activity: null, domScale: {} };

  // api() ne rejette jamais silencieusement : en cas d'erreur réseau/serveur, on prévient
  // l'utilisateur (toast) et on renvoie un objet marqué {__error:true} que les appelants gèrent.
  async function api(url, opts) {
    try {
      const r = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
      const txt = await r.text();
      let data; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = null; }
      if (!r.ok || data === null) { toast(T('req_failed')); return { __error: true, status: r.status }; }
      return data;
    } catch (e) { toast(T('req_failed')); return { __error: true }; }
  }
  function toast(msg) { const t = $('#cv2-toast'); t.textContent = msg; t.classList.add('show'); setTimeout(() => t.classList.remove('show'), 1900); }
  // Indicateur d'attente dans le tiroir (les analyses IA prennent plusieurs secondes).
  function showBusy(msg) {
    const body = $('#cv2-drawer-body');
    body.innerHTML = `<div class="cv2-busy"><span class="cv2-spin"></span><div>${msg || T('loading')}</div></div>`;
    $('#cv2-footer').querySelectorAll('button').forEach(b => { b.disabled = true; });
  }
  function applyStaticI18n() { document.querySelectorAll('[data-i18n]').forEach(el => { const k = el.dataset.i18n; if (I18N[LANG][k]) el.textContent = I18N[LANG][k]; }); }

  function levelName(lvl) { return lvl === null || lvl === undefined ? state.notAssessed : (state.scale[String(lvl)] || String(lvl)); }
  function initials(f, l) { return ((f || '')[0] || '').toUpperCase() + ((l || '')[0] || '').toUpperCase(); }

  // ── Chargement initial ──────────────────────────────────────────────
  async function boot() {
    applyStaticI18n();
    const [sc, ds] = await Promise.all([api('/mastery/scale'), api('/domains/scale')]);
    state.scale = sc.mastery || {}; state.notAssessed = sc.not_assessed || 'Non évalué';
    state.domScale = (ds && ds.scale) || {};
    const mgr = await api('/competences/current_user_manager');
    if (mgr && mgr.manager_id) {
      $('#cv2-mgr-name').textContent = mgr.manager_name || '—';
      $('#cv2-mgr-av').textContent = initials(...String(mgr.manager_name || '').split(' ')) || 'M';
      const collabs = await api('/competences/collaborators/' + mgr.manager_id);
      renderCollabs(collabs || []);
    }
    bindDrawer();
  }

  function renderCollabs(list) {
    const ul = $('#cv2-collab'); ul.innerHTML = '';
    if (!list.length) { $('#cv2-collab-empty').classList.remove('hidden'); return; }
    list.forEach(u => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="av">${initials(u.first_name, u.last_name)}</span><span>${u.first_name} ${u.last_name}</span><span class="chev">›</span>`;
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
    const lbl = $('#cv2-roles-lbl'); lbl.classList.toggle('hidden', !roles.length);
    renderRoles(roles);
  }

  function renderRoles(roles) {
    const box = $('#cv2-roles'); box.innerHTML = '';
    if (!roles.length) { $('#cv2-tablewrap').classList.add('hidden'); $('#cv2-placeholder').classList.remove('hidden'); $('#cv2-placeholder').textContent = T('pick_role'); return; }
    roles.forEach((ro, i) => {
      const b = document.createElement('button'); b.className = 'cv2-role'; b.textContent = ro.name;
      b.onclick = () => { document.querySelectorAll('.cv2-role').forEach(x => x.classList.remove('active')); b.classList.add('active'); selectRole(ro); };
      box.appendChild(b);
      if (i === 0) b.click();
    });
  }

  async function selectRole(ro) {
    state.roleId = ro.id; state.roleName = ro.name;
    const d = await api(`/mastery/dashboard/${state.userId}/${ro.id}`);
    renderDashboard(d);
  }

  function chip(color, label) { return `<span class="chip ${color}"><span class="lv"></span>${label}</span>`; }
  function gapCell(gap) {
    if (gap === null || gap === undefined) return `<span class="gap-zero">${T('none')}</span>`;
    if (gap > 0) return `<span class="gap-pos">+${gap}</span>`;
    if (gap < 0) return `<span class="gap-neg">${gap}</span>`;
    return `<span class="gap-zero">0</span>`;
  }
  function fmtDate(iso) { if (!iso) return T('none'); try { return new Date(iso).toLocaleDateString(LANG === 'en' ? 'en-GB' : 'fr-FR'); } catch (e) { return T('none'); } }

  function renderDashboard(d) {
    const tw = $('#cv2-tablewrap'), ph = $('#cv2-placeholder'), tb = $('#cv2-tbody');
    tb.innerHTML = '';
    if (!d || !d.activities || !d.activities.length) { tw.classList.add('hidden'); ph.classList.remove('hidden'); ph.textContent = T('no_activities'); return; }
    ph.classList.add('hidden'); tw.classList.remove('hidden');
    d.activities.forEach(a => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        `<td><div class="cv2-actname">${a.activity_name}</div>${a.competence ? `<div class="cv2-actcomp">${a.competence}</div>` : ''}</td>
         <td>${a.required_level === null ? T('none') : chip('grey', a.required_label)}</td>
         <td>${chip(a.color, a.demonstrated_label)}</td>
         <td>${gapCell(a.gap)}</td>
         <td>${a.n_at_required}/${a.n_results}</td>
         <td>${a.technicity_alert ? '<span class="chip orange"><span class="lv"></span>' + T('tech_gap') + '</span>' : '<span class="gap-zero">' + T('none') + '</span>'}</td>
         <td>${fmtDate(a.last_evaluation)}</td>
         <td style="text-align:right"><button class="btn btn-primary btn-sm">${T('evaluate')}</button></td>`;
      tr.querySelector('button').onclick = () => openDrawer(a);
      tb.appendChild(tr);
    });
  }

  // ── Drawer : évaluation par résultat + diagnostic ───────────────────
  function bindDrawer() {
    $('#cv2-drawer-close').onclick = closeDrawer;
    $('#cv2-overlay').onclick = closeDrawer;
  }
  function closeDrawer() { $('#cv2-drawer').classList.remove('open'); $('#cv2-overlay').classList.remove('open'); }

  function setFooter(buttons) {
    const f = $('#cv2-footer'); f.innerHTML = '';
    buttons.forEach(b => { const el = document.createElement('button'); el.className = 'btn ' + b.cls; el.textContent = b.label; el.onclick = b.on; if (b.id) el.id = b.id; f.appendChild(el); });
  }

  async function openDrawer(row) {
    state.activity = row;
    $('#cv2-drawer-title').textContent = row.activity_name;
    $('#cv2-drawer-role').textContent = `${state.userName} · ${state.roleName}`;
    const comp = $('#cv2-comp');
    if (row.competence) { comp.classList.remove('hidden'); $('#cv2-comp-text').textContent = row.competence; } else comp.classList.add('hidden');
    $('#cv2-drawer').classList.add('open'); $('#cv2-overlay').classList.add('open');
    showEvaluation();
  }

  async function showEvaluation() {
    const st = await api(`/mastery/activity/${state.userId}/${state.activity.activity_id}?role_id=${state.roleId}`);
    state.lastState = st;
    renderResults(st);
    setFooter([
      { cls: 'btn-ghost', label: T('diagnose'), on: showDiagnostic },
      { cls: 'btn-primary', label: T('save_eval'), on: saveEvaluation, id: 'cv2-save-btn' },
    ]);
  }

  function renderResults(st) {
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const warn = $('#cv2-drawer-warn'); warn.classList.add('hidden');
    const sb = () => $('#cv2-save-btn');
    // Activité pas encore configurée (aucun résultat qualifié) → étape de configuration.
    if (!st.results || !st.results.length) {
      if (sb()) sb().disabled = true;
      const setup = document.createElement('div'); setup.className = 'cv2-setup';
      setup.innerHTML = `<div class="st">${T('not_configured')}</div><div class="sd">${T('setup_intro')}</div>`;
      const b = document.createElement('button'); b.className = 'btn btn-primary'; b.textContent = T('setup_btn');
      b.onclick = () => showQualify(b); setup.appendChild(b);
      body.appendChild(setup);
      body.appendChild(requiredSummary(st));
      body.appendChild(technicitySection());
      return;
    }
    if (sb()) sb().disabled = false;
    // Bannière de guidage juste après la configuration des sorties.
    if (state.justConfigured) {
      state.justConfigured = false;
      const ok = document.createElement('div'); ok.className = 'cv2-ok';
      ok.textContent = T('configured_go_eval'); body.appendChild(ok);
    }
    body.appendChild(requiredSummary(st));
    const h = document.createElement('div'); h.className = 'cv2-evalhead';
    h.innerHTML = `<div class="eh">${T('eval_of')} ${state.userName}</div><div class="cv2-evalsub">${T('eval_hint')}</div>`;
    body.appendChild(h);
    st.results.forEach(r => body.appendChild(resultCard(r)));
    body.appendChild(technicitySection());
  }

  // Résumé compact : requis (éditable) · démontré (min) · écart.
  function requiredSummary(st) {
    const g = document.createElement('div'); g.className = 'cv2-summary';
    // requis
    const cr = document.createElement('div'); cr.className = 'sm';
    const rv = st.required_level === null ? `<span class="gap-zero">${T('not_set')}</span>` : chip('grey', st.required_label);
    cr.innerHTML = `<div class="k">${T('c_required')}</div><div class="v">${rv} <button class="cv2-link cv2-reqedit-btn">${T('edit')}</button></div>`;
    const row = document.createElement('div'); row.className = 'cv2-reqedit hidden';
    [null, 0, 1, 2, 3, 4].forEach(lv => { const b = document.createElement('button'); b.textContent = lv === null ? T('not_set') : lv; if (st.required_level === lv) b.classList.add('sel'); b.onclick = () => setRequired(lv); row.appendChild(b); });
    cr.appendChild(row);
    cr.querySelector('.cv2-reqedit-btn').onclick = () => row.classList.toggle('hidden');
    g.appendChild(cr);
    // démontré (min) + écart
    const cd = document.createElement('div'); cd.className = 'sm'; cd.innerHTML = `<div class="k">${T('c_demonstrated')} (min)</div><div class="v">${chip(st.color, st.global_label)}</div>`; g.appendChild(cd);
    const cg = document.createElement('div'); cg.className = 'sm'; cg.innerHTML = `<div class="k">${T('c_gap')}</div><div class="v">${gapCell(st.gap)}</div>`; g.appendChild(cg);
    return g;
  }

  // Carte d'un RÉSULTAT : le niveau du COLLABORATEUR est le contrôle central. Chaque bouton
  // porte le NUMÉRO + le LIBELLÉ du niveau (0 « Non démontré » … 4 « Expertise ») pour que
  // l'action « évaluer » soit évidente, plus « Non évalué » (≠ 0).
  function resultCard(r) {
    const card = document.createElement('div'); card.className = 'cv2-res'; card.dataset.dataId = r.data_id;
    const levels = [null, 0, 1, 2, 3, 4].map(lv => {
      const sel = r.demonstrated_level === lv ? ' sel' : '';
      const txt = lv === null ? T('not_assessed') : `<b>${lv}</b> ${levelName(lv)}`;
      return `<button class="cv2-lvbtn${sel}" data-lv="${lv === null ? '' : lv}">${txt}</button>`;
    }).join('');
    const needPick = (r.demonstrated_level === null || r.demonstrated_level === undefined);
    card.innerHTML = `
      <div class="rname">${r.name}</div>
      ${r.minimum_performance_text ? `<div class="rstd">${T('std')} : ${r.minimum_performance_text}</div>` : ''}
      <div class="cv2-lvlabel">${T('collab_level')}${needPick ? ` <span class="cv2-pickhint">— ${T('pick_level')}</span>` : ''}</div>
      <div class="cv2-levels">${levels}</div>
      ${r.self_level !== null && r.self_level !== undefined ? `<div class="self">${T('self')} : ${levelName(r.self_level)} · ${T('ref')}</div>` : ''}
      <textarea class="cv2-ev" placeholder="${T('evidence_ph')}"></textarea>`;
    card.querySelectorAll('.cv2-lvbtn').forEach(b => b.onclick = () => {
      card.querySelectorAll('.cv2-lvbtn').forEach(x => x.classList.remove('sel')); b.classList.add('sel');
      const hint = card.querySelector('.cv2-pickhint'); if (hint) hint.remove();
    });
    return card;
  }

  // ── Technicité : domaines techniques (axe séparé de la maîtrise, CDC 4) ──────
  function refreshDashboard() { api(`/mastery/dashboard/${state.userId}/${state.roleId}`).then(renderDashboard); }
  function domSelect(val, onchange) {
    const s = document.createElement('select'); s.className = 'cv2-domsel';
    const opts = [['', '—']].concat(Object.keys(state.domScale).map(k => [k, `${k} · ${state.domScale[k]}`]));
    opts.forEach(([v, l]) => { const o = document.createElement('option'); o.value = v; o.textContent = l;
      if ((val === null || val === undefined) ? v === '' : String(val) === v) o.selected = true; s.appendChild(o); });
    s.onchange = () => onchange(s.value === '' ? null : +s.value);
    return s;
  }
  function technicitySection() {
    const det = document.createElement('details'); det.className = 'cv2-tech';
    det.innerHTML = `<summary><span class="ti"><svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M12 3l7 4v6c0 4-3 6.5-7 8-4-1.5-7-4-7-8V7l7-4z" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M9 12l2 2 4-4" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
      ${T('tech_title')}<span class="caret">›</span></summary>
      <div class="tbody"><div class="texp">${T('tech_exp')}</div><div class="cv2-domlist"></div><div class="cv2-domadd"></div></div>`;
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
    if (!domains.length) { list.innerHTML = `<div class="cv2-emptydom">${T('tech_empty')}</div>`; return; }
    domains.forEach(d => {
      const row = document.createElement('div'); row.className = 'cv2-domrow';
      const dn = document.createElement('div'); dn.className = 'dn'; dn.textContent = d.name; row.appendChild(dn);
      const rq = document.createElement('div'); rq.className = 'df'; rq.innerHTML = `<span class="fl">${T('tech_required')}</span>`;
      rq.appendChild(domSelect(d.required_level, v => setDom('/domains/required', { role_id: state.roleId, activity_id: aid, domain_id: d.domain_id, required_level: v }, list, aid)));
      const dm = document.createElement('div'); dm.className = 'df'; dm.innerHTML = `<span class="fl">${T('tech_demonstrated')}</span>`;
      dm.appendChild(domSelect(d.demonstrated_level, v => setDom('/domains/user_level', { user_id: state.userId, domain_id: d.domain_id, demonstrated_level: v }, list, aid)));
      row.appendChild(rq); row.appendChild(dm);
      if (d.gap !== null && d.gap !== undefined) { const g = document.createElement('div');
        g.innerHTML = d.gap < 0 ? `<span class="chip red"><span class="lv"></span>${d.gap}</span>` : `<span class="chip green"><span class="lv"></span>+${d.gap}</span>`;
        row.appendChild(g); }
      list.appendChild(row);
    });
  }
  async function setDom(url, body, list, aid) {
    const r = await api(url, { method: 'POST', body: JSON.stringify(body) });
    if (r.__error) return;
    const dom = await api(`/domains/activity/${aid}?role_id=${state.roleId}&user_id=${state.userId}`);
    renderDomList(list, aid, (dom && dom.domains) || []); refreshDashboard();
  }
  function renderDomAdd(det, aid, allDomains, linked) {
    const add = det.querySelector('.cv2-domadd'); add.innerHTML = '';
    const linkedIds = new Set(linked.map(d => d.domain_id));
    const avail = allDomains.filter(d => !linkedIds.has(d.id));
    if (avail.length) {
      const sel = document.createElement('select'); sel.className = 'cv2-domsel';
      sel.innerHTML = `<option value="">${T('tech_pick')}</option>` + avail.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
      const b = document.createElement('button'); b.className = 'btn btn-ghost btn-sm'; b.textContent = T('tech_link');
      b.onclick = async () => { if (!sel.value) return; await linkDom(aid, +sel.value); await loadTech(det); };
      add.appendChild(sel); add.appendChild(b);
    }
    const inp = document.createElement('input'); inp.placeholder = T('tech_add_ph');
    const cb = document.createElement('button'); cb.className = 'btn btn-primary btn-sm'; cb.textContent = '＋';
    cb.onclick = async () => { const nm = inp.value.trim(); if (!nm) return;
      const r = await api('/domains/create', { method: 'POST', body: JSON.stringify({ name_fr: nm }) });
      if (r && r.id) { await linkDom(aid, r.id); inp.value = ''; await loadTech(det); } };
    add.appendChild(inp); add.appendChild(cb);
  }
  async function linkDom(aid, did) {
    await api(`/domains/activity/${aid}/link`, { method: 'POST', body: JSON.stringify({ domain_id: did }) });
    refreshDashboard();
  }

  async function saveEvaluation() {
    const cards = document.querySelectorAll('#cv2-drawer-body .cv2-res');
    const btn = $('#cv2-save-btn'); if (btn) btn.disabled = true;
    for (const c of cards) {
      const sel = c.querySelector('.cv2-lvbtn.sel');
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
    await showEvaluation();                 // rafraîchit drawer + footer
    renderDashboard(await api(`/mastery/dashboard/${state.userId}/${state.roleId}`));
  }

  // ── Diagnostic de l'écart (CDC 6.5-6.9) ─────────────────────────────
  async function showDiagnostic() {
    const st = state.lastState || await api(`/mastery/activity/${state.userId}/${state.activity.activity_id}?role_id=${state.roleId}`);
    // résultats en écart : niveau démontré < requis (ou < 2)
    const req = st.required_level;
    const gapRes = (st.results || []).filter(r => r.demonstrated_level !== null &&
      (r.demonstrated_level < 2 || (req !== null && r.demonstrated_level < req)));
    const fams = await api('/diagnostic/families');
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    $('#cv2-drawer-warn').classList.add('hidden');
    if (!gapRes.length) { const p = document.createElement('div'); p.className = 'cv2-warn'; p.style.background = '#f0fdf4'; p.style.borderColor = '#bbf7d0'; p.style.color = '#15803d'; p.classList.remove('hidden'); p.textContent = T('no_gap'); body.appendChild(p); }
    for (const r of gapRes) body.appendChild(await diagBlock(r, fams.families));
    setFooter([{ cls: 'btn-ghost', label: T('back'), on: showEvaluation }]);
  }

  async function diagBlock(result, families) {
    const st = await api(`/diagnostic/${state.userId}/${state.activity.activity_id}/${result.data_id}?role_id=${state.roleId}`);
    const wrap = document.createElement('div'); wrap.className = 'cv2-diagres'; wrap.dataset.dataId = result.data_id;
    const selected = new Set(st.families || []);
    wrap.innerHTML = `<div class="dtitle"><span>${st.result.name}</span>${chip(result.demonstrated_level < 2 ? 'red' : 'orange', st.status.label)}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:4px">${st.demonstrated_label} (${T('dem')}) · ${st.required_label} (${T('req')})</div>
      <div style="font-weight:700;font-size:12.5px;margin:12px 0 2px">${T('cause_q')}</div>
      <div class="cv2-fams"></div>
      <div class="cv2-caps hidden"></div>
      <div class="cv2-plan"></div>`;
    const famsBox = wrap.querySelector('.cv2-fams');
    families.forEach(f => {
      const el = document.createElement('div'); el.className = 'cv2-fam' + (selected.has(f.code) ? ' sel' : ''); el.dataset.code = f.code;
      el.innerHTML = `<div class="fh"><span class="bx"></span>${f.label}</div><div class="fd">${f.description}</div>`;
      el.onclick = () => { el.classList.toggle('sel'); selected.has(f.code) ? selected.delete(f.code) : selected.add(f.code); onDiagChange(wrap, st, selected); };
      famsBox.appendChild(el);
    });
    onDiagChange(wrap, st, selected, true);
    return wrap;
  }

  async function onDiagChange(wrap, st, selected, initial) {
    const capsBox = wrap.querySelector('.cv2-caps'), planBox = wrap.querySelector('.cv2-plan');
    // save du diagnostic (sauf au 1er rendu)
    if (!initial) {
      await api('/diagnostic/save', { method: 'POST', body: JSON.stringify({
        user_id: state.userId, activity_id: state.activity.activity_id, data_id: +wrap.dataset.dataId, families: [...selected] }) });
    }
    // Capacité à agir → afficher les capacités reliées + bouton plan
    if (selected.has(st.individual_family)) {
      capsBox.classList.remove('hidden');
      capsBox.innerHTML = `<div style="font-weight:700;font-size:12px;margin-bottom:6px">${T('linked_caps')}</div>` +
        (st.capabilities.length ? st.capabilities.map(c =>
          `<div class="cv2-cap"><div><span class="ct">${c.type_label}</span><div>${c.label || '—'}</div></div>
           <div class="lvls"><span class="${c.gap !== null && c.gap < 0 ? 'gap-neg' : 'gap-zero'}">${c.demonstrated_level === null ? T('none') : c.demonstrated_level}</span> / ${c.required_level === null ? T('none') : c.required_level}</div></div>`).join('')
          : `<div style="font-size:12px;color:var(--muted)">${T('none')}</div>`);
      const btn = document.createElement('button'); btn.className = 'btn btn-primary btn-sm'; btn.style.marginTop = '10px'; btn.textContent = T('gen_plan');
      btn.onclick = () => genPlan(wrap, btn);
      capsBox.appendChild(btn);
    } else { capsBox.classList.add('hidden'); planBox.innerHTML = ''; }
  }

  async function genPlan(wrap, btn) {
    btn.disabled = true; btn.textContent = T('gen');
    const j = await api('/diagnostic/plan', { method: 'POST', body: JSON.stringify({
      user_id: state.userId, activity_id: state.activity.activity_id, data_id: +wrap.dataset.dataId, role_id: state.roleId }) });
    const planBox = wrap.querySelector('.cv2-plan'); planBox.innerHTML = '';
    btn.disabled = false; btn.textContent = T('gen_plan');
    if (j.no_individual_plan) { planBox.innerHTML = `<div class="cv2-noplan">${j.message}</div>`; return; }
    const items = j.plan || [];
    if (!items.length) { planBox.innerHTML = `<div class="cv2-noplan">${j.source && j.source !== 'AI' ? 'IA indisponible.' : T('none')}</div>`; return; }
    planBox.innerHTML = `<div style="font-weight:700;font-size:12.5px;margin:12px 0 6px">${T('plan_title')}</div>` +
      items.map(it => `<div class="cv2-planitem"><b>${it.development_objective || ''}</b>${it.target_level ? ` → ${it.target_level}` : ''}
        ${it.work_situations ? `<div>${Array.isArray(it.work_situations) ? it.work_situations.join(', ') : it.work_situations}</div>` : ''}
        ${it.steps ? `<div style="color:var(--muted);margin-top:4px">${Array.isArray(it.steps) ? it.steps.join(' · ') : it.steps}</div>` : ''}</div>`).join('');
  }

  async function setRequired(lvl) {
    await api('/mastery/required', { method: 'POST', body: JSON.stringify({
      activity_id: state.activity.activity_id, role_id: state.roleId, required_mastery_level: lvl }) });
    toast(T('req_set'));
    await showEvaluation();
    renderDashboard(await api(`/mastery/dashboard/${state.userId}/${state.roleId}`));
  }

  // ── Configuration d'une activité : qualifier les sorties → compétence ───
  async function showQualify(btn) {
    if (btn) { btn.disabled = true; btn.textContent = T('gen'); }
    const aid = state.activity.activity_id;
    showBusy(T('configuring'));
    const [outs, ana] = await Promise.all([api(`/qualify/outputs/${aid}`), api(`/qualify/analyze/${aid}`, { method: 'POST' })]);
    const body = $('#cv2-drawer-body'); body.innerHTML = ''; $('#cv2-comp').classList.add('hidden');
    const panel = document.createElement('div'); panel.className = 'cv2-setup';
    panel.innerHTML = `<div class="st">${T('qualify_title')}</div><div class="sd">${T('qualify_desc')}</div>`;
    const outputs = outs.outputs || [], labels = outs.labels || {};
    if (!outputs.length) {
      panel.insertAdjacentHTML('beforeend', `<div class="cv2-warn" style="margin:0">${(ana && ana.warning) || T('no_out')}</div>`);
      body.appendChild(panel); setFooter([{ cls: 'btn-ghost', label: T('back'), on: showEvaluation }]); return;
    }
    const props = {}; (ana.outputs || []).forEach(p => props[p.data_id] = p);
    outputs.forEach(o => {
      const p = props[o.data_id] || {}, nature = o.nature || p.suggested_nature || '';
      const row = document.createElement('div'); row.className = 'cv2-qz'; row.dataset.dataId = o.data_id;
      const opts = `<option value="">${T('to_qualify')}</option>` + Object.keys(labels).map(k => `<option value="${k}" ${nature === k ? 'selected' : ''}>${labels[k]}</option>`).join('');
      const mv = (o.minimum_performance_text || p.suggested_minimum_performance || '').replace(/"/g, '&quot;');
      row.innerHTML = `<div style="flex:1"><div class="qn">${o.name}</div>${p.justification ? `<div class="qj">${p.justification}</div>` : ''}
        <input class="cv2-minperf ${nature === 'RESULT' ? '' : 'hidden'}" placeholder="${T('min_perf_ph')}" value="${mv}"></div>
        <select class="cv2-natsel">${opts}</select>`;
      const sel = row.querySelector('.cv2-natsel'), mp = row.querySelector('.cv2-minperf');
      sel.onchange = () => mp.classList.toggle('hidden', sel.value !== 'RESULT');
      panel.appendChild(row);
    });
    body.appendChild(panel);
    setFooter([{ cls: 'btn-ghost', label: T('back'), on: showEvaluation },
               { cls: 'btn-primary', label: T('validate_analysis'), on: () => saveQualify() }]);
  }

  async function saveQualify() {
    const aid = state.activity.activity_id;
    const rows = [...document.querySelectorAll('#cv2-drawer-body .cv2-qz')];
    const outputs = rows.map(r => { const sel = r.querySelector('.cv2-natsel'), mp = r.querySelector('.cv2-minperf');
      return { data_id: +r.dataset.dataId, nature: sel.value || null, minimum_performance_text: mp ? mp.value : '', source: 'MANUAL' }; });
    // Garde-fou : sans aucune sortie « Résultat », il n'y a rien à évaluer → on prévient et on reste.
    if (!outputs.some(o => o.nature === 'RESULT')) {
      let w = $('#cv2-need-result');
      if (!w) { w = document.createElement('div'); w.id = 'cv2-need-result'; w.className = 'cv2-warn'; w.style.margin = '0 0 12px';
        const panel = $('#cv2-drawer-body .cv2-setup'); (panel || $('#cv2-drawer-body')).prepend(w); }
      w.textContent = T('need_result'); w.scrollIntoView({ block: 'nearest' });
      return;
    }
    showBusy(T('configuring'));
    const save = await api(`/qualify/save/${aid}`, { method: 'POST', body: JSON.stringify({ outputs }) });
    if (save.__error) { return showQualify(); }
    // compétence principale + liens S/SF/HSC (best effort ; sans clé IA → sautés proprement)
    const comp = await api(`/competence/generate/${aid}`, { method: 'POST' });
    if (comp.competence && (comp.competence.description_fr || comp.competence.description_en)) {
      await api(`/competence/save/${aid}`, { method: 'POST', body: JSON.stringify({
        description: (LANG === 'en' ? comp.competence.description_en : comp.competence.description_fr) || comp.competence.description_fr || comp.competence.description_en }) });
    }
    await api(`/competence/result_links/generate/${aid}`, { method: 'POST' });
    toast(T('setup_done'));
    const d = await api(`/mastery/dashboard/${state.userId}/${state.roleId}`); renderDashboard(d);
    const row = (d.activities || []).find(a => a.activity_id === aid); if (row) state.activity = row;
    state.justConfigured = true;
    showEvaluation();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
