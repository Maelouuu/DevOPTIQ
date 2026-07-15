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
      c_gap: 'Écart', c_results: 'Résultats', c_last: 'Dernière éval.',
      competence: 'Compétence principale', analyze_gap: "Analyser l'écart",
      save_eval: "Enregistrer l'évaluation", evaluate: 'Évaluer', not_assessed: 'Non évalué',
      no_result: "Aucun résultat qualifié pour cette activité. Qualifiez d'abord les sorties.",
      std: 'Standard minimal', self: 'Auto-évaluation', saved: 'Évaluation enregistrée',
      no_activities: 'Aucune activité pour ce rôle.', pick_role: 'Sélectionnez un rôle.',
      none: '—', back: "← Évaluation", save_diag: 'Enregistrer le diagnostic', gen_plan: 'Générer le plan',
      cause_q: "Quelle est la cause de l'écart ?", linked_caps: 'Capacités reliées à ce résultat',
      no_gap: 'Aucun résultat en écart : le niveau requis est tenu.', dem: 'démontré', req: 'requis',
      plan_title: "Plan d'accompagnement", diag_saved: 'Diagnostic enregistré', gen: 'Génération…',
    },
    en: {
      manager: 'Manager', collaborators: 'Team members', no_collab: 'No team member.',
      title: 'Skills', pick_collab: 'Select a team member to start.',
      pick_collab2: 'Select a team member then a role.',
      c_activity: 'Activity', c_required: 'Required level', c_demonstrated: 'Demonstrated level',
      c_gap: 'Gap', c_results: 'Results', c_last: 'Last eval.',
      competence: 'Main competence', analyze_gap: 'Analyze gap',
      save_eval: 'Save evaluation', evaluate: 'Evaluate', not_assessed: 'Not assessed',
      no_result: 'No qualified result for this activity. Qualify the outputs first.',
      std: 'Minimum standard', self: 'Self-assessment', saved: 'Evaluation saved',
      no_activities: 'No activity for this role.', pick_role: 'Select a role.',
      none: '—', back: '← Evaluation', save_diag: 'Save diagnosis', gen_plan: 'Generate plan',
      cause_q: 'What is the cause of the gap?', linked_caps: 'Capabilities linked to this result',
      no_gap: 'No result below the required level.', dem: 'demonstrated', req: 'required',
      plan_title: 'Support plan', diag_saved: 'Diagnosis saved', gen: 'Generating…',
    },
  };
  const T = k => (I18N[LANG][k] || k);

  const state = { userId: null, userName: '', roleId: null, roleName: '', scale: {}, notAssessed: 'Non évalué', activity: null };

  function api(url, opts) { return fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts)).then(r => r.json()); }
  function toast(msg) { const t = $('#cv2-toast'); t.textContent = msg; t.classList.add('show'); setTimeout(() => t.classList.remove('show'), 1900); }
  function applyStaticI18n() { document.querySelectorAll('[data-i18n]').forEach(el => { const k = el.dataset.i18n; if (I18N[LANG][k]) el.textContent = I18N[LANG][k]; }); }

  function levelName(lvl) { return lvl === null || lvl === undefined ? state.notAssessed : (state.scale[String(lvl)] || String(lvl)); }
  function initials(f, l) { return ((f || '')[0] || '').toUpperCase() + ((l || '')[0] || '').toUpperCase(); }

  // ── Chargement initial ──────────────────────────────────────────────
  async function boot() {
    applyStaticI18n();
    const sc = await api('/mastery/scale');
    state.scale = sc.mastery || {}; state.notAssessed = sc.not_assessed || 'Non évalué';
    const mgr = await api('/competences/current_user_manager');
    if (mgr && mgr.manager_id) {
      $('#cv2-mgr-name').textContent = mgr.manager_name || '—';
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
      li.innerHTML = `<span class="av">${initials(u.first_name, u.last_name)}</span><span>${u.first_name} ${u.last_name}</span>`;
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
    renderRoles((r && r.roles) || []);
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
      { cls: 'btn-ghost', label: T('analyze_gap'), on: showDiagnostic },
      { cls: 'btn-primary', label: T('save_eval'), on: saveEvaluation, id: 'cv2-save-btn' },
    ]);
  }

  function renderResults(st) {
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const warn = $('#cv2-drawer-warn');
    const sb = () => $('#cv2-save-btn');
    if (!st.results || !st.results.length) { warn.classList.remove('hidden'); warn.textContent = T('no_result'); if (sb()) sb().disabled = true; return; }
    warn.classList.add('hidden'); if (sb()) sb().disabled = false;
    // bandeau niveau global vs requis
    const g = document.createElement('div'); g.className = 'cv2-global';
    g.innerHTML = `<div><div class="k">${T('c_demonstrated')} (min)</div>${chip(st.color, st.global_label)}</div>
                   <div style="text-align:right"><div class="k">${T('c_required')}</div>${st.required_level === null ? T('none') : chip('grey', st.required_label)}</div>`;
    body.appendChild(g);
    st.results.forEach(r => {
      const card = document.createElement('div'); card.className = 'cv2-res'; card.dataset.dataId = r.data_id;
      const levels = [null, 0, 1, 2, 3, 4].map(lv => {
        const sel = (r.demonstrated_level === lv) ? ' sel' : '';
        const lbl = lv === null ? T('not_assessed') : lv;
        return `<button class="cv2-lvbtn${sel}" data-lv="${lv === null ? '' : lv}">${lbl}</button>`;
      }).join('');
      card.innerHTML =
        `<div class="rhead"><div><div class="rname">${r.name}</div>${r.minimum_performance_text ? `<div class="rstd">${T('std')} : ${r.minimum_performance_text}</div>` : ''}</div></div>
         ${r.self_level !== null && r.self_level !== undefined ? `<div class="self">${T('self')} : ${levelName(r.self_level)}</div>` : ''}
         <div class="cv2-levels">${levels}</div>
         <textarea class="cv2-ev" placeholder="${T('c_last')}…"></textarea>`;
      card.querySelectorAll('.cv2-lvbtn').forEach(b => b.onclick = () => {
        card.querySelectorAll('.cv2-lvbtn').forEach(x => x.classList.remove('sel')); b.classList.add('sel');
      });
      body.appendChild(card);
    });
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

  document.addEventListener('DOMContentLoaded', boot);
})();
