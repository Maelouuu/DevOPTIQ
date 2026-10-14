// Code/static/js/time.js
(() => {
  // Libelles injectes par le gabarit : sans eux (page servie hors
  // time_dashboard) on retombe sur le francais plutot que sur 'undefined'.
  const L = window.TIME_I18N || {};
  const tl = (cle, defaut) => L[cle] || defaut;
  const $ = (s, c=document) => c.querySelector(s);
  const $$ = (s, c=document) => Array.from(c.querySelectorAll(s));
  const v = (sel) => $(sel)?.value;
  const n = (sel) => parseFloat(v(sel) || "0");
  /* ⚠️ Une PROMESSE, pas un booléen : `window.confirm` sortait de
     l'application (fenêtre du navigateur, styles du système) et affichait un
     texte en dur que rien ne traduisait. Tous les appelants sont `async`. */
  const confirmDel = (cle, defaut) => window.optiqConfirm(
    tl(cle, defaut),
    { title: tl('del_title', 'Supprimer ?'),
      ok: tl('del_ok', 'Supprimer'),
      cancel: tl('del_cancel', 'Annuler'),
      danger: true });

  let currentActivityEditId = null;
  /* Ce qu'on est en train de modifier : {type, id, nom}. Nul = on crée.
     ⚠️ Sans ce repère, « Enregistrer » crée une analyse de plus au lieu de
     remplacer celle qu'on vient d'ouvrir — et rien à l'écran ne le dit. */
  let edition = null;
  let calendarParams = {hours_per_day:7, days_per_week:5, weeks_per_year:47};

  /* ─────────────────── Les trois ecrans de la page ───────────────────
     Quatre onglets cote a cote, c'etaient quatre modeles mentaux sans rien
     qui les relie : on arrive (accueil), on choisit (choix), on saisit
     (travail) — une seule analyse a l'ecran a la fois. */
  const ANALYSES = {
    projet:    { ic: 'fa-diagram-project',      cle: 'tab_project'  },
    activite:  { ic: 'fa-bolt',                 cle: 'tab_activity' },
    role:      { ic: 'fa-user-tie',             cle: 'tab_role'     },
    faiblesse: { ic: 'fa-triangle-exclamation', cle: 'tab_weakness' }
  };

  function ouvrirEcran(nom){
    $$('.tm-ecran').forEach(e => e.classList.toggle('is-actif', e.id === 'tm-' + nom));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function ouvrirAccueil(){
    ouvrirEcran('accueil');
    // On revient de la saisie : tout ce que l'accueil montre a pu bouger.
    await chargerTableauDeBord();
  }

  function majBandeauEdition(){
    const b = $('#tm-mod');
    if (!b) return;
    b.classList.toggle('hidden', !edition);
    if (edition) updateKpi('tm-mod-nom', edition.nom || tl('tm_mod', ''));
  }

  function sortirEdition(){
    edition = null;
    currentActivityEditId = null;
    $('#act-editing')?.classList.add('hidden');
    majBandeauEdition();
  }

  async function ouvrirPourModifier(type, id, nom){
    edition = { type: type, id: id, nom: nom || '' };
    ouvrirAnalyse(type);
    let ok = false;
    if (type === 'projet')    ok = await chargerProjet(id);
    if (type === 'activite')  ok = await chargerActivite(id);
    if (type === 'role')      ok = await chargerRole(id);
    if (type === 'faiblesse') ok = await chargerFaiblesse(id);
    if (!ok) { sortirEdition(); return; }
    majBandeauEdition();
  }

  function ouvrirAnalyse(type, activityId){
    const a = ANALYSES[type];
    if (!a) return;
    // Arriver depuis « ce qui n'est pas chiffre » : l'activite est DEJA
    // choisie. Sans cela on tombait sur une liste deroulante qui porte tout,
    // y compris ce qui est deja mesure — et rien ne disait laquelle ouvrir.
    if (type === 'activite' && activityId) {
      const sel = $('#act-activity');
      if (sel) {
        sel.value = String(activityId);
        currentActivityEditId = null;
        $('#act-editing')?.classList.add('hidden');
        // On repart d'une saisie vierge : la duree de la fiche doit pouvoir
        // se poser, et `intact()` refuse d'ecraser un champ deja touche.
        const c = $('#act-duration');
        if (c) delete c.dataset.saisi;
        refreshActivityDefaults();
      }
    }
    $$('.subtab-panel').forEach(p => p.classList.remove('active'));
    $('#subtab-' + type)?.classList.add('active');
    $$('.tm-res-bloc').forEach(b => b.classList.toggle('is-actif', b.dataset.pour === type));
    const titre = $('#tm-barre-titre');
    if (titre) titre.textContent = tl(a.cle, type);
    const ic = $('#tm-barre-ic');
    if (ic) ic.innerHTML = '<i class="fa-solid ' + a.ic + '"></i>';
    const ecran = $('#tm-travail');
    if (ecran) ecran.dataset.analyse = type;
    // On n'hérite pas d'une modification commencée sur une AUTRE analyse.
    if (edition && edition.type !== type) sortirEdition();
    majBandeauEdition();
    ouvrirEcran('travail');
    // Le panneau de droite ne doit jamais s'ouvrir sur un chiffre perime.
    if (type === 'projet')    recalcProjectTotals();
    if (type === 'activite')  majResultatActivite();
    if (type === 'role')      recalcRoleTotals();
    if (type === 'faiblesse') { refreshWeaknessDefaults().then(() => calculFaiblesse()); }
  }

  $('#tm-btn-nouvelle')?.addEventListener('click', () => ouvrirEcran('choix'));
  $$('.tm-retour').forEach(b => b.addEventListener('click', () => ouvrirAccueil()));
  /* ⚠️ Les portes ET le rail de l'accueil, pas `[data-analyse]` tout court :
     `#tm-travail` porte cet attribut (c'est lui qui teinte l'icone de la
     barre), on lui poserait un ecouteur qui le rouvrirait sur lui-meme. */
  $$('.tm-porte, .tm-rail-t').forEach(
    b => b.addEventListener('click', () => { sortirEdition(); ouvrirAnalyse(b.dataset.analyse); }));
  $('#tm-mod-sortir')?.addEventListener('click', () => {
    // Quitter la modification remet l'écran à neuf : garder la saisie
    // laisserait croire qu'elle est encore rattachée à l'analyse ouverte.
    const type = edition && edition.type;
    sortirEdition();
    if (type) viderSaisie(type);
  });
  // ---------- Utils ----------
  function toMinutes(qty, unit){
    const k={minutes:1, heures:60, jours:1440};
    return (parseFloat(qty||0)*(k[(unit||'minutes').toLowerCase()]||1));
  }
  function fmtH(min){
    if(min===null||min===undefined||isNaN(min)) return '—';
    const h=min/60;
    return (Math.round(h*10)/10).toFixed(1)+'h';
  }
  const echap = (x) => String(x == null ? '' : x)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  /* ⚠️ La MEME regle que `annuel_minutes` cote serveur. Elle etait deja
     reecrite ici (dans recalcRoleTotals) ; le tableau de bord en aurait fait
     une troisieme. Un seul endroit, et un test confronte les deux. */
  function annuelMinutes(parPeriode, rec){
    const dpw = calendarParams.days_per_week || 5;
    const wpy = calendarParams.weeks_per_year || 47;
    const r = String(rec || '').toLowerCase();
    const q = parseFloat(parPeriode || 0);
    if (r.startsWith('jour'))  return q * dpw * wpy;
    if (r.startsWith('hebdo')) return q * wpy;
    if (r.startsWith('mens'))  return q * 12;
    return q;
  }

  function nombre(x){
    const lang = L.lang === 'en' ? 'en-GB' : 'fr-FR';
    try { return Number(x).toLocaleString(lang); } catch (_) { return String(x); }
  }

  function unitSelect(){
    const s=document.createElement('select');
    s.className='input';
    s.innerHTML = `<option value="minutes">${tl('minutes', 'minutes')}</option>`
                + `<option value="heures">${tl('hours', 'heures')}</option>`
                + `<option value="jours">${tl('days', 'jours')}</option>`;
    return s;
  }

  async function loadCalendarParams(){
    try{
      const r = await fetch('/temps/api/calendar_params');
      const j = await r.json();
      if (j.ok) calendarParams = {hours_per_day:j.hours_per_day, days_per_week:j.days_per_week, weeks_per_year:j.weeks_per_year};
    }catch(_){}
  }

  // =====================================================
  // ===============  FAIBLESSE (SOUS-ONGLET) ============
  // =====================================================
  const fwGlobal = $('#fw-global');
  const fwTasks = $('#fw-tasks');
  const fwTaskBody = $('#fw-task-rows');
  const fwTaskSum = $('#fw-task-sum');

  function toggleFwMode() {
    const modeEl = $$('input[name="fw-mode"]:checked')[0];
    if (!modeEl) return;
    const mode = modeEl.value;
    if (mode === 'tasks') {
      fwGlobal?.classList.remove('hidden');
      fwTasks?.classList.remove('hidden');
      $('#fw-dur')?.setAttribute('readonly', 'readonly');
    } else {
      fwTasks?.classList.add('hidden');
      $('#fw-dur')?.removeAttribute('readonly');
    }
  }
  $$('input[name="fw-mode"]').forEach(r => r.onchange = toggleFwMode);

  function activitySelectFromTemplate(selectId='#act-activity'){
    const s=document.createElement('select');
    s.className='input';
    const base = $$(selectId+' option');
    s.innerHTML = base.map(o=>`<option value="${o.value}">${o.textContent}</option>`).join('');
    return s;
  }

  async function refreshWeaknessDefaults() {
    const actSel = $('#fw-activity');
    const act = actSel && actSel.value;
    if (!act) return;

    try {
      const r = await fetch(`/temps/api/activity_defaults/${act}`);
      const j = await r.json();

      const durationMin = parseFloat(j.duration_minutes) || 0;
      const delayMin = parseFloat(j.delay_minutes) || 0;

      // ⚠️ Quatrieme site de pre-remplissage, oublie par le correctif des
      // trois autres : taper une duree puis choisir l'activite la remettait
      // a la valeur de la fiche.
      const durInput = $('#fw-dur');
      if (intact(durInput)) {
        durInput.value = durationMin;
        if ($('#fw-dur-unit')) $('#fw-dur-unit').value = 'minutes';
      }
      const delInput = $('#fw-del');
      if (intact(delInput)) {
        delInput.value = delayMin;
        if ($('#fw-del-unit')) $('#fw-del-unit').value = 'minutes';
      }

      if (fwTaskBody) {
        fwTaskBody.innerHTML = (j.tasks||[]).map(t=>{
          const taskDur = parseFloat(t.duration_minutes) || 0;
          const taskDel = parseFloat(t.delay_minutes) || 0;
          return `<tr data-task="${t.id}">
            <td>${echap(t.name)}</td>
            <td><input type="number" class="input t-dur" step="0.1" min="0" value="${taskDur}" /></td>
            <td class="td-unit"></td>
            <td><input type="number" class="input t-del" step="0.1" min="0" value="${taskDel}" /></td>
            <td class="td-dunit"></td>
          </tr>`;
        }).join('');

        $$('#fw-task-rows tr').forEach(tr=>{
          const u1 = unitSelect();
          const tdUnit = tr.querySelector('.td-unit');
          if (tdUnit) { tdUnit.appendChild(u1); u1.value='minutes'; }
          const u2 = unitSelect();
          const tdDunit = tr.querySelector('.td-dunit');
          if (tdDunit) { tdDunit.appendChild(u2); u2.value='minutes'; }
        });
      }

      recalcTaskSum();

    } catch (err) {
      console.error('Faiblesse — chargement des valeurs par defaut :', err);
    }
  }

  function recalcTaskSum() {
    if (!fwTaskBody) return;
    let sum = 0;
    $$('#fw-task-rows tr').forEach(tr=>{
      const durInput = tr.querySelector('.t-dur');
      const unitSel = tr.querySelector('.td-unit select');
      if (durInput && unitSel) {
        const d = parseFloat(durInput.value || '0');
        const u = unitSel.value;
        sum += toMinutes(d, u);
      }
    });
    if (fwTaskSum) fwTaskSum.textContent = fmtH(sum);
    
    // En mode tâches, la durée globale est la somme des tâches
    const modeEl = $$('input[name="fw-mode"]:checked')[0];
    if (modeEl && modeEl.value === 'tasks' && $('#fw-dur')) { 
      $('#fw-dur').value = Math.round(sum); 
      if ($('#fw-dur-unit')) $('#fw-dur-unit').value = 'minutes'; 
    }
  }

  $('#fw-activity')?.addEventListener('change', refreshWeaknessDefaults);
  $('#fw-tasks')?.addEventListener('input', (e)=> {
    if (e.target.classList.contains('t-dur')) recalcTaskSum();
  });
  toggleFwMode();

  function flashFeedback(id, isOk, msg) {
    const el = document.getElementById(id);
    if (!el) { if (!isOk) alert(msg); return; }
    el.textContent = msg;
    el.className = 'time-inline-feedback ' + (isOk ? 'ok' : 'error');
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3500);
  }

  function showFwFeedback(isOk, msg) { flashFeedback('fw-feedback', isOk, msg); }

  async function sendWeakness(save=false, discret=false){
    const modeEl = $$('input[name="fw-mode"]:checked')[0];
    if (!modeEl) { if (!discret) showFwFeedback(false, tl('error', 'Erreur')); return; }
    const mode = modeEl.value;

    const payload = {
      mode,
      activity_id: parseInt($('#fw-activity')?.value || '0', 10),
      recurrence: $('#fw-rec')?.value || 'journalier',
      frequency: parseInt($('#fw-freq')?.value || '1', 10),
      weakness: $('#fw-k')?.value || '',
      L_work_added: n('#fw-l'), L_unit: v('#fw-l-unit') || 'minutes',
      M_wait_added: n('#fw-m'), M_unit: v('#fw-m-unit') || 'minutes',
      N_prob_denom: parseInt(n('#fw-n') || 1, 10),
      delay_std: n('#fw-del'), delay_unit: v('#fw-del-unit') || 'minutes',
      save
    };
    if (mode === 'tasks') {
      payload.tasks = $$('#fw-task-rows tr').map(tr => ({
        task_id: parseInt(tr.dataset.task,10),
        duration_std: parseFloat(tr.querySelector('.t-dur')?.value || '0'),
        duration_unit: tr.querySelector('.td-unit select')?.value || 'minutes',
        delay_std: parseFloat(tr.querySelector('.t-del')?.value || '0'),
        delay_unit: tr.querySelector('.td-dunit select')?.value || 'minutes'
      }));
    } else {
      payload.duration_std = n('#fw-dur');
      payload.duration_unit = v('#fw-dur-unit') || 'minutes';
    }

    // ⚠️ Le calcul EN DIRECT (`discret`) ne modifie jamais : il interroge la
    // route de création sans enregistrer. Seul « Enregistrer » met à jour.
    const modif = save && edition && edition.type === 'faiblesse';
    const r = await fetch(modif ? '/temps/api/weakness/' + edition.id : '/temps/api/weakness',
                          {method: modif ? 'PUT' : 'POST',
                           headers:{'Content-Type':'application/json'},
                           body: JSON.stringify(payload)});
    const j = await r.json();
    if (!j.ok) { if (!discret) showFwFeedback(false, tl('error', 'Erreur')); return; }

    const m = j.calc || {};
    ['S','T','U','V','W','X','Y','Z'].forEach(k=>{
      const val = m[k] != null ? fmtH(m[k]) : '—';
      const el = document.getElementById(k);
      if (el) el.textContent = val;
    });
    // ⚠️ La base de calcul du mensuel, écrite noir sur blanc : il divise par
    // les mois TRAVAILLÉS (semaines/an ÷ 4,34524), pas par douze. Sans ça on
    // lit « annuel ÷ 12 » et on conclut à une erreur.
    const base = document.getElementById('fw-base-mois');
    if (base) {
      const sem = (j.params || {}).weeks_per_year || calendarParams.weeks_per_year || 47;
      const mois = (sem / 4.34524).toFixed(1).replace('.', ',');
      base.textContent = tl('fw_base_mois', 'Base : {sem} semaines par an, soit {mois} mois travaillés.')
        .replace('{sem}', sem).replace('{mois}', mois);
    }
    // AA = occurrences (nombre, pas de conversion)
    const aaEl = document.getElementById('AA');
    if (aaEl) aaEl.textContent = m['AA'] != null ? Math.round(m['AA']) : '—';
    // Les résultats n'apparaissent qu'après un premier calcul réussi
    document.getElementById('fw-results-empty')?.classList.add('hidden');
    document.getElementById('fw-results-section')?.classList.remove('hidden');

    // Le panneau colle a droite : le cout ANNUEL en tete, deux secondaires.
    updateKpi('tm-fw-an',   fmtH((m['U'] || 0) + (m['V'] || 0)));
    updateKpi('tm-fw-mois', fmtH((m['W'] || 0) + (m['X'] || 0)));
    updateKpi('tm-fw-occ',  m['AA'] != null ? Math.round(m['AA']) : '—');

    if (save) {
      if (modif) { edition.nom = payload.weakness; majBandeauEdition(); }
      showFwFeedback(true, modif ? tl('tm_maj', '')
                                 : 'Analyse faiblesse enregistrée avec succès');
    }
  }

  $('#btn-fw-save')?.addEventListener('click', ()=> sendWeakness(true));

  /* ⚠️ Le resultat se met a jour PENDANT la saisie, mais la formule reste
     celle du serveur : la reecrire ici en ferait une seconde, et deux
     implementations d'un meme verdict finissent par diverger. On appelle
     donc la route, en differe — pas a chaque frappe. */
  let minuterieFw = null;
  function calculFaiblesse(){
    if (!$('#fw-activity')?.value) return;
    clearTimeout(minuterieFw);
    minuterieFw = setTimeout(() => { sendWeakness(false, true); }, 420);
  }
  $('#subtab-faiblesse')?.addEventListener('input', calculFaiblesse);
  $('#subtab-faiblesse')?.addEventListener('change', calculFaiblesse);
  marqueSaisie($('#fw-dur'));
  marqueSaisie($('#fw-del'));

  // =====================================================
  // =================== CHARGES - PROJET ================
  // =====================================================
  const projectBody = $('#project-rows');
  const addLineBtn = $('#btn-add-line'), saveProjBtn = $('#btn-save-project');

  function activitySelectFromAll(){
    const s=document.createElement('select');
    s.className='input';
    s.innerHTML = [...$$('#act-activity option')].map(o=>`<option value="${o.value}">${o.textContent}</option>`).join('');
    return s;
  }

  /* ⚠️ Un champ qu'on a TOUCHÉ ne se fait plus écraser par le
     pré-remplissage d'une activité. On marque la saisie plutôt que de
     regarder la valeur : une durée volontairement mise à 0 est un choix,
     « vide » n'en est pas un. */
  function marqueSaisie(champ) {
    if (!champ || champ.dataset.saisi) return;
    champ.addEventListener('input', () => { champ.dataset.saisi = '1'; });
  }
  const intact = (champ) => !!champ && !champ.dataset.saisi;

  function addProjectRow(pre) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="cell-act"></td>
      <td><input type="number" min="0" step="0.1" class="input cell-dur" /></td>
      <td class="cell-du"></td>
      <td><input type="number" min="0" step="0.1" class="input cell-del" /></td>
      <td class="cell-deu"></td>
      <td><input type="number" min="1" step="1" class="input cell-nbp" value="1" /></td>
      <td class="cell-chg">0</td>
      <td><button class="icon-btn danger btn-del" title="${echap(tl('del_ok', 'Supprimer'))}">🗑</button></td>
    `;
    const act = activitySelectFromAll(); tr.querySelector('.cell-act').appendChild(act);
    const du = unitSelect(); tr.querySelector('.cell-du').appendChild(du);
    const deu = unitSelect(); tr.querySelector('.cell-deu').appendChild(deu);

    async function prefillDefaults(){
      const id = act.value;
      const r = await fetch(`/temps/api/activity_defaults/${id}`);
      const j = await r.json();
      const cDur = tr.querySelector('.cell-dur'), cDel = tr.querySelector('.cell-del');
      // ⚠️ On ne remplit que ce qui n'a pas été saisi : taper 30 puis choisir
      // l'activité remettait 0, d'où les projets enregistrés à 0 h.
      if (intact(cDur)) { cDur.value = parseFloat(j.duration_minutes) || 0; du.value = 'minutes'; }
      if (intact(cDel)) { cDel.value = parseFloat(j.delay_minutes) || 0; deu.value = 'minutes'; }
      recalc();
    }
    marqueSaisie(tr.querySelector('.cell-dur'));
    marqueSaisie(tr.querySelector('.cell-del'));
    act.onchange = prefillDefaults;
    if (pre) {
      // Une ligne ENREGISTRÉE : ses valeurs priment sur celles de la fiche,
      // donc on la marque saisie et on ne pré-remplit pas.
      act.value = String(pre.activity_id);
      const cD = tr.querySelector('.cell-dur'), cL = tr.querySelector('.cell-del');
      cD.value = pre.duration_minutes; cD.dataset.saisi = '1'; du.value = 'minutes';
      cL.value = pre.delay_minutes;    cL.dataset.saisi = '1'; deu.value = 'minutes';
      tr.querySelector('.cell-nbp').value = pre.nb_people || 1;
      // ⚠️ Le total lit `.cell-chg[data-minutes]`, que SEUL `recalc()` pose.
      // Sans cet appel, un projet à 10,5 h se rouvre en affichant 0,0 h.
      recalc();
    } else {
      prefillDefaults();
    }

    function recalc(){
      const d = parseFloat(tr.querySelector('.cell-dur').value || '0');
      const duV = du.value;
      const nbp = parseInt(tr.querySelector('.cell-nbp').value || '1', 10);
      const durMin = toMinutes(d, duV);
      const charge = durMin * Math.max(1, nbp);
      const chgCell = tr.querySelector('.cell-chg');
      chgCell.textContent = fmtH(charge);
      chgCell.dataset.minutes = charge;
      recalcProjectTotals();
    }
    tr.addEventListener('input', recalc);
    tr.querySelector('.btn-del').onclick = ()=> { tr.remove(); recalcProjectTotals(); };
    projectBody?.appendChild(tr);
  }

  function updateKpi(id, val){ const el = document.getElementById(id); if (el) el.textContent = String(val); }

  function recalcProjectTotals() {
    const rows = $$('#project-rows tr');
    let nb = 0, sumD = 0, sumDelay = 0, sumC = 0;
    rows.forEach(tr=>{
      nb++;
      const d = parseFloat(tr.querySelector('.cell-dur').value || '0');
      const du = tr.querySelector('.cell-du select').value;
      const del = parseFloat(tr.querySelector('.cell-del').value || '0');
      const delu = tr.querySelector('.cell-deu select').value;
      sumD += toMinutes(d, du);
      sumDelay += toMinutes(del, delu);
      const chgCell = tr.querySelector('.cell-chg');
      sumC += parseFloat(chgCell?.dataset?.minutes || '0');
    });

    updateKpi('kpi-proj-nb', nb);
    updateKpi('kpi-proj-dur', fmtH(sumD));
    updateKpi('kpi-proj-del', fmtH(sumDelay / (nb || 1)));
    updateKpi('kpi-proj-charge', fmtH(sumC));
  }

  addLineBtn?.addEventListener('click', ()=> addProjectRow());
  saveProjBtn?.addEventListener('click', async ()=>{
    const rows = $$('#project-rows tr').map(tr=>({
      activity_id: parseInt(tr.querySelector('.cell-act select').value, 10),
      duration: parseFloat(tr.querySelector('.cell-dur').value || '0'),
      duration_unit: tr.querySelector('.cell-du select').value,
      delay: parseFloat(tr.querySelector('.cell-del').value || '0'),
      delay_unit: tr.querySelector('.cell-deu select').value,
      nb_people: parseInt(tr.querySelector('.cell-nbp').value || '1', 10)
    }));
    const payload = { name: $('#project-name').value || 'Projet', lines: rows };
    const modif = edition && edition.type === 'projet';
    const r = await fetch(modif ? '/temps/api/project/' + edition.id : '/temps/api/project',
                          {method: modif ? 'PUT' : 'POST',
                           headers:{'Content-Type':'application/json'},
                           body: JSON.stringify(payload)});
    const j = await r.json();
    if (j.ok) {
      flashFeedback('proj-feedback', true,
                    modif ? tl('tm_maj', '') : 'Projet enregistré avec succès');
      if (modif) { edition.nom = payload.name; majBandeauEdition(); }
      else {
        projectBody.innerHTML = '';
        $('#project-name').value = '';
        addProjectRow(); recalcProjectTotals();
      }
    } else {
      flashFeedback('proj-feedback', false, "Erreur d'enregistrement");
    }
  });

  // =====================================================
  // =================== CHARGES - ACTIVITÉ ==============
  // =====================================================
  async function refreshActivityDefaults() {
    const act = $('#act-activity')?.value;
    if (!act) return;
    const r = await fetch(`/temps/api/activity_defaults/${act}`);
    const j = await r.json();
    if (intact($('#act-duration'))) {
      $('#act-duration').value = parseFloat(j.duration_minutes) || 0;
      $('#act-duration-unit').value = 'minutes';
    }
    const total = toMinutes(n('#act-duration'), v('#act-duration-unit')) * parseInt(v('#act-frequency')||'1',10) * parseInt(v('#act-people')||'1',10);
    $('#act-total').textContent = fmtH(total);
  }
  marqueSaisie($('#act-duration'));
  $('#act-activity')?.addEventListener('change', refreshActivityDefaults);

  // ⚠️ L'aperçu n'était recalculé QUE sur le changement d'activité et après
  // sauvegarde : taper 30 min, fréquence 2, 3 personnes laissait « 0.0 h » à
  // l'écran alors que l'enregistrement rendait 3,0 h. Le chiffre affiché
  // pendant la saisie ne décrivait rien.
  function majApercuActivite() { majResultatActivite(); }

  /* Le total par occurrence ne dit pas grand-chose seul : une demi-heure
     par jour et une demi-heure par an s'affichaient pareil. */
  function majResultatActivite() {
    const parOcc = toMinutes(n('#act-duration'), v('#act-duration-unit'))
                 * parseInt(v('#act-frequency') || '1', 10)
                 * parseInt(v('#act-people') || '1', 10);
    const an = annuelMinutes(parOcc, v('#act-recurrence'));
    updateKpi('act-total', fmtH(parOcc));
    updateKpi('tm-act-an', fmtH(an));
    updateKpi('tm-act-mois', fmtH(an / 12));
  }
  ['#act-duration', '#act-duration-unit', '#act-frequency', '#act-people', '#act-recurrence']
    .forEach(sel => {
      $(sel)?.addEventListener('input', majApercuActivite);
      $(sel)?.addEventListener('change', majApercuActivite);
    });

  $('#btn-act-save')?.addEventListener('click', async ()=>{
    const payload = {
      activity_id: parseInt(v('#act-activity'),10),
      duration: n('#act-duration'),
      duration_unit: v('#act-duration-unit'),
      recurrence: v('#act-recurrence'),
      frequency: parseInt(v('#act-frequency')||'1',10),
      nb_people: parseInt(v('#act-people')||'1',10)
    };

    let j;
    if (currentActivityEditId) {
      const r = await fetch(`/temps/api/activity_workload/${currentActivityEditId}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      j = await r.json();
      if (!j.ok) return flashFeedback('act-feedback', false, 'Erreur de mise à jour');
      flashFeedback('act-feedback', true, 'Analyse activité mise à jour.');
    } else {
      const r = await fetch('/temps/api/activity_workload', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      j = await r.json();
      if (!j.ok) return flashFeedback('act-feedback', false, "Erreur d'enregistrement");
      flashFeedback('act-feedback', true, 'Analyse activité enregistrée.');
    }

    majResultatActivite();
    if (!(edition && edition.type === 'activite')) {
      currentActivityEditId = null;
      $('#act-editing')?.classList.add('hidden');
      await refreshActivityDefaults();
    }
  });

  // =====================================================
  // =================== CHARGES - RÔLE ==================
  // =====================================================
  const roleBody = $('#role-rows');

  // Cache des activités filtrées pour le rôle courant
  let roleActivitiesOptions = []; // [{id, name}, ...]

  function buildRoleActivitySelect(){
    const s=document.createElement('select');
    s.className='input';
    if (roleActivitiesOptions.length) {
      s.innerHTML = roleActivitiesOptions.map(a=>`<option value="${a.id}">${a.name}</option>`).join('');
    } else {
      // fallback (ne devrait pas arriver si /role_activities marche)
      s.innerHTML = [...$$('#act-activity option')].map(o=>`<option value="${o.value}">${o.textContent}</option>`).join('');
    }
    return s;
  }

  function addRoleRow(activityId=null, duration=0, _unit='minutes', recurrence='journalier', frequency=1){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="r-act"></td>
      <td><input type="number" min="0" step="0.1" class="input r-dur" /></td>
      <td class="r-rec"></td>
      <td><input type="number" min="1" step="1" class="input r-freq" value="1" /></td>
      <td class="r-weight">0</td>
      <td class="r-actions"><button class="icon-btn danger r-del" title="${echap(tl('del_ok', 'Supprimer'))}">🗑</button></td>
    `;
    const actSel = buildRoleActivitySelect();
    tr.querySelector('.r-act').appendChild(actSel);

    const recSel = document.createElement('select');
    recSel.className='input';
    recSel.innerHTML = `<option value="journalier">Journalier</option><option value="hebdomadaire">Hebdomadaire</option><option value="mensuel">Mensuel</option><option value="annuel">Annuel</option>`;
    tr.querySelector('.r-rec').appendChild(recSel);

    if (activityId) actSel.value = String(activityId);
    tr.querySelector('.r-dur').value = duration || 0;
    recSel.value = recurrence || 'journalier';
    tr.querySelector('.r-freq').value = frequency || 1;

    async function prefillDuration(){
      const id = actSel.value;
      const r = await fetch(`/temps/api/activity_defaults/${id}`);
      const j = await r.json();
      const champ = tr.querySelector('.r-dur');
      if (intact(champ)) champ.value = parseFloat(j.duration_minutes) || 0;
      recalc();
    }

    marqueSaisie(tr.querySelector('.r-dur'));
    // Même raison que pour le projet : la pesée vit dans `data-minutes`.
    if (duration) recalc(); else prefillDuration();

    function recalc(){
      const durMin = parseFloat(tr.querySelector('.r-dur').value || '0');
      const freq = parseInt(tr.querySelector('.r-freq').value || '1', 10);
      const weight = durMin * Math.max(1, freq);
      const wCell = tr.querySelector('.r-weight');
      wCell.textContent = fmtH(weight);
      wCell.dataset.minutes = weight;
      recalcRoleTotals();
    }
    tr.addEventListener('input', recalc);
    actSel.onchange = prefillDuration;
    tr.querySelector('.r-del').onclick = ()=>{ tr.remove(); recalcRoleTotals(); };
    roleBody?.appendChild(tr);
  }

  function recalcRoleTotals(){
    let sumD=0, sumW=0, sumM=0, sumA=0;
    $$('#role-rows tr').forEach(tr=>{
      const recSel = tr.querySelector('.r-rec select');
      if (!recSel) return;
      const wCell = tr.querySelector('.r-weight');
      const weight = parseFloat(wCell?.dataset?.minutes || wCell?.textContent || '0');
      const rec = recSel.value;
      if (rec.startsWith('jour')) sumD += weight;
      else if (rec.startsWith('hebdo')) sumW += weight;
      else if (rec.startsWith('mens')) sumM += weight;
      else sumA += weight;
    });

    const annual = annuelMinutes(sumD, 'journalier') + annuelMinutes(sumW, 'hebdomadaire')
                 + annuelMinutes(sumM, 'mensuel') + annuelMinutes(sumA, 'annuel');
    const monthly = annual / 12;

    updateKpi('kpi-role-d', fmtH(sumD));
    updateKpi('kpi-role-w', fmtH(sumW));
    updateKpi('kpi-role-m', fmtH(sumM));
    updateKpi('kpi-role-a', fmtH(sumA));
    updateKpi('kpi-role-monthly', fmtH(monthly));
    updateKpi('kpi-role-annual', fmtH(annual));
  }

  /* Les OPTIONS du rôle, sans créer de ligne : rouvrir une analyse
     enregistrée doit garder SES lignes, pas une par activité du rôle. */
  async function chargerOptionsRole(roleId){
    roleActivitiesOptions = [];
    if (!roleId) return false;
    try {
      const j = await (await fetch(`/temps/api/role_activities/${roleId}`)).json();
      if (!j.ok) return false;
      roleActivitiesOptions = j.activities || [];
      return true;
    } catch (_) { return false; }
  }

  async function loadRoleActivities(roleId){
    roleBody.innerHTML = '';
    const ok = await chargerOptionsRole(roleId);
    if (!ok) { roleBody.innerHTML = `<tr><td colspan="6" class="muted">${tl('load_error', 'Erreur de chargement')}</td></tr>`; return; }
    if (!roleActivitiesOptions.length) {
      roleBody.innerHTML = `<tr><td colspan="6" class="muted">${tl('role_no_activity', 'Aucune activité pour ce rôle.')}</td></tr>`;
      return;
    }
    // Pré-remplir une ligne par activité du rôle (comme avant)
    for (const a of roleActivitiesOptions){
      addRoleRow(a.id, 0, 'minutes', 'journalier', 1);
    }
    setTimeout(recalcRoleTotals, 0);
  }

  $('#role-select')?.addEventListener('change', (e)=> loadRoleActivities(e.target.value));
  $('#btn-role-add-line')?.addEventListener('click', ()=> addRoleRow());

  $('#btn-role-save')?.addEventListener('click', async ()=>{
    const lines = $$('#role-rows tr').filter(tr=>tr.querySelector('.r-rec select')).map(tr=>({
      activity_id: parseInt(tr.querySelector('.r-act select').value,10),
      duration: parseFloat(tr.querySelector('.r-dur').value || '0'),
      duration_unit: 'minutes',
      recurrence: tr.querySelector('.r-rec select').value,
      frequency: parseInt(tr.querySelector('.r-freq').value || '1',10)
    }));
    const payload = {
      role_id: parseInt($('#role-select').value,10),
      name: $('#role-name').value || 'Analyse rôle',
      lines
    };
    const modif = edition && edition.type === 'role';
    const r = await fetch(modif ? '/temps/api/role_analysis/' + edition.id
                                : '/temps/api/role_analysis',
                          {method: modif ? 'PATCH' : 'POST',
                           headers:{'Content-Type':'application/json'},
                           body: JSON.stringify(payload)});
    const j = await r.json();
    if (j.ok){
      flashFeedback('role-feedback', true,
                    modif ? tl('tm_maj', '') : 'Analyse rôle enregistrée.');
      if (modif) { edition.nom = payload.name; majBandeauEdition(); }
      else $('#role-name').value='';
    } else flashFeedback('role-feedback', false, "Erreur d'enregistrement");
  });

  // =====================================================
  // =============== OUVRIR POUR MODIFIER ================
  // =====================================================
  function viderSaisie(type){
    if (type === 'projet') {
      $('#project-name').value = '';
      if (projectBody) projectBody.innerHTML = '';
      addProjectRow(); recalcProjectTotals();
    }
    if (type === 'activite') {
      ['#act-duration'].forEach(x => { const c = $(x); if (c) delete c.dataset.saisi; });
      $('#act-frequency').value = 1; $('#act-people').value = 1;
      refreshActivityDefaults();
    }
    if (type === 'role') {
      $('#role-name').value = '';
      if ($('#role-select')?.value) loadRoleActivities($('#role-select').value);
    }
    if (type === 'faiblesse') {
      $('#fw-k').value = '';
      ['#fw-l', '#fw-m'].forEach(x => { const c = $(x); if (c) c.value = ''; });
      $('#fw-n').value = 1; $('#fw-freq').value = 1;
      ['#fw-dur', '#fw-del'].forEach(x => { const c = $(x); if (c) delete c.dataset.saisi; });
      refreshWeaknessDefaults().then(() => calculFaiblesse());
    }
  }

  async function chargerProjet(id){
    const j = await (await fetch('/temps/api/project/' + id)).json();
    if (!j.ok) return false;
    $('#project-name').value = (j.project || {}).name || '';
    if (projectBody) projectBody.innerHTML = '';
    (j.lines || []).forEach(l => addProjectRow(l));
    recalcProjectTotals();
    return true;
  }

  async function chargerActivite(id){
    const j = await (await fetch('/temps/api/activity_workload/' + id)).json();
    if (!j.ok) return false;
    const it = j.item;
    $('#act-activity').value = it.activity_id;
    const d = $('#act-duration');
    d.value = it.duration_minutes;
    d.dataset.saisi = '1';          // la valeur enregistrée prime sur la fiche
    $('#act-duration-unit').value = 'minutes';
    $('#act-recurrence').value = it.recurrence;
    $('#act-frequency').value = it.frequency;
    $('#act-people').value = it.nb_people;
    currentActivityEditId = id;
    $('#act-editing')?.classList.remove('hidden');
    majResultatActivite();
    return true;
  }

  async function chargerRole(id){
    const j = await (await fetch('/temps/api/role_analysis/' + id)).json();
    if (!j.ok) return false;
    const r = j.role || {};
    if ($('#role-select') && r.role_id) $('#role-select').value = String(r.role_id);
    $('#role-name').value = r.name || '';
    // ⚠️ Les OPTIONS du rôle seulement : `loadRoleActivities` crée aussi une
    // ligne par activité, ce qui écraserait les lignes enregistrées.
    await chargerOptionsRole(r.role_id);
    if (roleBody) roleBody.innerHTML = '';
    (j.lines || []).forEach(l => addRoleRow(l.activity_id, l.duration_minutes,
                                            'minutes', l.recurrence, l.frequency));
    setTimeout(recalcRoleTotals, 0);
    return true;
  }

  async function chargerFaiblesse(id){
    const j = await (await fetch('/temps/api/weakness/' + id)).json();
    if (!j.ok) return false;
    const it = j.item;
    if ($('#fw-activity')) $('#fw-activity').value = String(it.activity_id);
    const mode = $$('input[name="fw-mode"]').find(r => r.value === it.mode);
    if (mode) { mode.checked = true; toggleFwMode(); }
    await refreshWeaknessDefaults();
    // APRÈS le pré-remplissage : c'est la valeur ENREGISTRÉE qui fait foi.
    const poser = (sel, v) => { const c = $(sel); if (c) { c.value = v; c.dataset.saisi = '1'; } };
    poser('#fw-dur', it.duration_std);
    poser('#fw-del', it.delay_std);
    if ($('#fw-dur-unit')) $('#fw-dur-unit').value = 'minutes';
    if ($('#fw-del-unit')) $('#fw-del-unit').value = 'minutes';
    $('#fw-rec').value = it.recurrence;
    $('#fw-freq').value = it.frequency;
    $('#fw-k').value = it.weakness;
    $('#fw-n').value = it.N_prob_denom;
    $('#fw-l').value = it.L_work_added; $('#fw-l-unit').value = 'minutes';
    $('#fw-m').value = it.M_wait_added; $('#fw-m-unit').value = 'minutes';
    (it.tasks || []).forEach(t => {
      const tr = $('#fw-task-rows tr[data-task="' + t.task_id + '"]');
      if (!tr) return;
      tr.querySelector('.t-dur').value = t.duration_std;
      tr.querySelector('.t-del').value = t.delay_std;
    });
    recalcTaskSum();
    calculFaiblesse();
    return true;
  }

  // =====================================================
  // ================== TABLEAU DE BORD ==================
  // =====================================================
  const PLAFOND_BARRES = 8;

  function fmtPhrase(cle, defaut, vals){
    let out = tl(cle, defaut);
    Object.keys(vals).forEach(k => { out = out.split('{' + k + '}').join(vals[k]); });
    return out;
  }

  function barres(cible, items, repere){
    if (!cible) return;
    const vus = items.slice(0, PLAFOND_BARRES);
    const max = Math.max(repere || 0, ...vus.map(i => i.annuel_min), 1);
    cible.innerHTML = vus.map(it => {
      const p = Math.min(100, (it.annuel_min / max) * 100);
      // ⚠️ Le repere du temps plein est pose sur la MEME echelle que les
      // barres : ailleurs il ne voudrait rien dire.
      const trait = repere
        ? `<span class="tm-repere" style="left:${Math.min(100, (repere / max) * 100)}%"></span>` : '';
      return `<div class="tm-barre-l" data-ouvrir="${echap(it.ouvrir || '')}">
        <span class="tm-barre-nom" title="${echap(it.nom)}">${echap(it.nom)}</span>
        <span class="tm-barre-piste"><span class="tm-barre-in" style="width:${p}%"></span>${trait}</span>
        <span class="tm-barre-val">${fmtH(it.annuel_min)}</span>
      </div>`;
    }).join('');
    if (items.length > PLAFOND_BARRES) {
      cible.insertAdjacentHTML('beforeend',
        `<div class="tm-barre-plus">+ ${items.length - PLAFOND_BARRES}</div>`);
    }
  }

  function rendreFaiblesses(d){
    const items = (d.faiblesses || {}).items || [];
    updateKpi('tm-faib', items.length ? Math.round((d.faiblesses.travail_min || 0) / 60) : '—');

    // L'attente, dite a part et nommee pour ce qu'elle est.
    const att = $('#tm-attente');
    if (att) {
      const v = (d.faiblesses || {}).attente_min || 0;
      att.innerHTML = (items.length && v)
        ? `<span>${echap(tl('tm_faib_attente', ''))}</span>`
          + `<b>${fmtH(v)}</b>`
          + `<i>${echap(tl('tm_faib_attente_dit', ''))}</i>` : '';
    }

    const sous = $('#tm-faib-sous');
    if (sous) {
      if (!items.length) sous.textContent = tl('tm_faib_aucune', '');
      else {
        const part = d.faiblesses.part != null
          ? fmtPhrase('tm_faib_part', '{p} %', { p: Math.round(d.faiblesses.part * 100) }) + ' · ' : '';
        const cle = items.length > 1 ? 'tm_faib_n_pl' : 'tm_faib_n';
        sous.textContent = part + fmtPhrase(cle, '{n}', { n: items.length });
      }
    }

    const apercu = $('#tm-faib-liste');
    if (apercu) {
      const max = Math.max(1, ...items.map(f => f.travail_annuel_min));
      apercu.innerHTML = items.slice(0, 3).map(f => `
        <div class="tm-faib-l">
          <span class="tm-faib-nom" title="${echap(f.nom || f.activite)}">${echap(f.nom || f.activite)}</span>
          <span class="tm-faib-barre" style="width:${Math.max(6, (f.travail_annuel_min / max) * 46)}px"></span>
          <span class="tm-faib-val">${fmtH(f.travail_annuel_min)}</span>
        </div>`).join('');
    }

  }

  /* ─────────────────── « Vos analyses » ───────────────────
     Trois rendus séparés, chacun avec son accordéon, son renommage en place
     et sa suppression ligne à ligne — et pourtant « on ne peut pas modifier
     une analyse ». Un seul rendu désormais : des lignes denses, et un clic
     qui ouvre l'analyse dans l'écran de saisie, où tout est modifiable par
     construction. */
  const LISTES = {
    projet:    { cible: '#tm-l-projet',    suppr: (id) => '/temps/api/project/' + id,
                 cle: 'del_project', defaut: 'Supprimer ce projet ?' },
    activite:  { cible: '#tm-l-activite',  suppr: (id) => '/temps/api/activity_workload/' + id,
                 cle: 'del_activity_analysis', defaut: 'Supprimer cette analyse ?' },
    role:      { cible: '#tm-l-role',      suppr: (id) => '/temps/api/role_analysis/' + id,
                 cle: 'del_role_analysis', defaut: 'Supprimer cette analyse ?' },
    faiblesse: { cible: '#tm-l-faiblesse', suppr: (id) => '/temps/api/weakness/' + id,
                 cle: 'del_faiblesse', defaut: 'Supprimer cette faiblesse ?' }
  };

  const MEMO_GRP = 'optiq.temps.groupes';

  function groupesOuverts(){
    try { return JSON.parse(localStorage.getItem(MEMO_GRP) || '[]'); }
    catch (_) { return []; }   // navigateur qui refuse le stockage
  }
  function memoriserGroupes(ouverts){
    try { localStorage.setItem(MEMO_GRP, JSON.stringify(ouverts)); } catch (_) {}
  }
  function appliquerGroupes(){
    const ouverts = groupesOuverts();
    $$('.tm-grp').forEach(g => g.classList.toggle('is-ouvert',
                                                  ouverts.indexOf(g.dataset.grp) >= 0));
  }
  $$('.tm-grp-tete').forEach(b => b.addEventListener('click', () => {
    const g = b.closest('.tm-grp');
    const ouvert = g.classList.toggle('is-ouvert');
    const liste = groupesOuverts().filter(x => x !== g.dataset.grp);
    if (ouvert) liste.push(g.dataset.grp);
    memoriserGroupes(liste);
  }));

  function lignesDepuis(d){
    const acts = (n) => fmtPhrase('tm_acts', '{n} act.', { n: n });
    return {
      projet: (d.projets || []).map(p => ({
        id: p.id, nom: p.nom || tl('tab_project', 'Projet'),
        chips: [acts(p.n_activites)], val: fmtH(p.charge_min) })),
      activite: (d.par_activite || []).map(a => ({
        id: a.id, nom: a.activite,
        chips: [a.recurrence, '× ' + a.frequence], val: fmtH(a.annuel_min) })),
      role: (d.par_role || []).map(r => ({
        id: r.id, nom: r.nom || r.role,
        chips: [r.role, acts(r.n_activites)], val: fmtH(r.annuel_min) })),
      faiblesse: ((d.faiblesses || {}).items || []).map(f => ({
        id: f.id, nom: f.nom || f.activite,
        chips: [f.activite], val: fmtH(f.travail_annuel_min) }))
    };
  }

  function rendreAnalyses(d){
    const paquets = lignesDepuis(d);
    Object.keys(LISTES).forEach(type => {
      const items = paquets[type] || [];
      updateKpi('tm-g-n-' + type, items.length);
      const cible = $(LISTES[type].cible);
      if (!cible) return;
      cible.innerHTML = items.length
        ? items.map(it => `
            <div class="tm-ligne" tabindex="0" role="button"
                 data-type="${type}" data-id="${it.id}" title="${echap(it.nom)}">
              <span class="tm-ligne-nom">${echap(it.nom)}</span>
              <span class="tm-ligne-chips">${it.chips.filter(Boolean)
                  .map(c => `<em>${echap(c)}</em>`).join('')}</span>
              <span class="tm-ligne-val">${it.val}</span>
              <button type="button" class="tm-ligne-x"
                      title="${echap(tl('del_ok', 'Supprimer'))}">
                <i class="fa-solid fa-trash"></i></button>
            </div>`).join('')
        : `<div class="tm-grp-vide">${echap(tl('tm_vide_grp', ''))}</div>`;

      $$('.tm-ligne', cible).forEach(l => {
        const ouvrir = () => ouvrirPourModifier(l.dataset.type,
                                                parseInt(l.dataset.id, 10),
                                                l.querySelector('.tm-ligne-nom').textContent);
        l.addEventListener('click', (e) => {
          if (e.target.closest('.tm-ligne-x')) return;
          ouvrir();
        });
        // Au clavier : une ligne qui s'ouvre au clic doit s'ouvrir à Entrée.
        l.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ouvrir(); }
        });
        l.querySelector('.tm-ligne-x').onclick = async (e) => {
          e.stopPropagation();
          const cfg = LISTES[l.dataset.type];
          if (!(await confirmDel(cfg.cle, cfg.defaut))) return;
          const r = await fetch(cfg.suppr(l.dataset.id), { method: 'DELETE' });
          if ((await r.json()).ok) {
            // On quitte la modification si c'est CELLE-LÀ qu'on supprimait.
            if (edition && edition.type === l.dataset.type
                && String(edition.id) === l.dataset.id) sortirEdition();
            await chargerTableauDeBord();
          }
        };
      });
    });
    appliquerGroupes();
  }

  async function chargerTableauDeBord(){
    let d;
    try {
      const r = await fetch('/temps/api/tableau_de_bord');
      d = await r.json();
    } catch (_) { return; }
    if (!d || !d.ok) return;

    const c = d.calendrier || {};
    const base = $('#tm-base');
    if (base) base.textContent = fmtPhrase('tm_base', '', {
      sem: c.weeks_per_year, jours: c.days_per_week, heures: c.hours_per_day });

    // — Charge
    const an = (d.charge || {}).annuel_min || 0;
    updateKpi('tm-charge', an ? nombre(Math.round(an / 60)) : '—');
    updateKpi('tm-charge-mois', an ? fmtH(d.charge.mensuel_min) : '—');
    updateKpi('tm-charge-sem', an ? fmtH(d.charge.hebdo_min) : '—');
    const etp = $('#tm-etp');
    if (etp) {
      // ⚠️ `etp` est NUL quand rien n'est mesure : « 0 equivalent temps
      // plein » se lirait comme un resultat, pas comme une absence.
      if (d.charge.etp == null) etp.textContent = tl('tm_rien_mesure', '');
      else {
        const v2 = Math.round(d.charge.etp * 100) / 100;
        etp.textContent = fmtPhrase(v2 > 1 ? 'tm_etp_pl' : 'tm_etp', '{n}',
                                    { n: nombre(v2) });
      }
    }

    rendreFaiblesses(d);
    rendreAnalyses(d);

    // — Couverture
    const couv = d.couverture || { chiffrees: 0, total: 0 };
    const reste = Math.max(0, couv.total - couv.chiffrees);
    const manquent = couv.a_chiffrer || [];
    updateKpi('tm-couv-nb', reste);
    const sur = $('#tm-couv-sur');
    if (sur) sur.textContent = ' ' + fmtPhrase('tm_couv_sur', '/ {t}', { t: couv.total });
    const cbase = $('#tm-couv-base');
    if (cbase) {
      // ⚠️ Trois phrases, pas une : « ne porte que sur 0 activites » ne veut
      // rien dire, et au pluriel en plus.
      if (reste === 0) cbase.textContent = tl('tm_couv_tout', '');
      else if (!couv.chiffrees) cbase.textContent = tl('tm_couv_aucune', '');
      else cbase.textContent = fmtPhrase(
        couv.chiffrees === 1 ? 'tm_couv_base_une' : 'tm_couv_base', '{n}',
        { n: couv.chiffrees });
    }
    const jauge = $('#tm-couv-jauge');
    if (jauge) jauge.style.width = (couv.total ? (couv.chiffrees / couv.total) * 100 : 0) + '%';

    const liste = $('#tm-couv-liste');
    if (liste) {
      liste.innerHTML = manquent.slice(0, 3).map(a2 =>
        `<button type="button" class="tm-couv-l" data-chiffrer="${a2.id}">
           <span>${echap(a2.nom)}</span><i class="fa-solid fa-arrow-right"></i>
         </button>`).join('')
        + (manquent.length > 3
           ? `<div class="tm-couv-plus">${echap(fmtPhrase('tm_couv_autres', '+ {n}',
                { n: manquent.length - 3 }))}</div>` : '');
      $$('#tm-couv-liste .tm-couv-l').forEach(b => {
        b.onclick = () => ouvrirAnalyse('activite', parseInt(b.dataset.chiffrer, 10));
      });
    }

    const bouton = $('#tm-btn-couv');
    bouton?.classList.toggle('hidden', reste === 0);
    if (bouton && manquent.length) {
      // Le bouton NOMME ce qu'il va ouvrir : « les suivantes » ne disait pas
      // lesquelles, ni ou on atterrissait.
      updateKpi('tm-btn-couv-txt',
                fmtPhrase('tm_couv_btn_nom', '{nom}', { nom: manquent[0].nom }));
      bouton.onclick = () => ouvrirAnalyse('activite', manquent[0].id);
    }

    // — Ce que chaque analyse contient deja
    updateKpi('tm-n-projet',    (d.projets || []).length);
    updateKpi('tm-n-activite',  (d.par_activite || []).length);
    updateKpi('tm-n-role',      (d.par_role || []).length);
    updateKpi('tm-n-faiblesse', ((d.faiblesses || {}).items || []).length);

    // — Deux lectures
    barres($('#tm-role-liste'),
           (d.par_role || []).map(r2 => ({ nom: r2.role || r2.nom, annuel_min: r2.annuel_min })),
           d.plein_temps_min);
    if (!(d.par_role || []).length && $('#tm-role-liste'))
      $('#tm-role-liste').innerHTML = `<div class="muted">${tl('tm_vide_role', '')}</div>`;
    const pied = $('#tm-role-pied');
    if (pied) pied.textContent = (d.par_role || []).length
      ? fmtPhrase('tm_repere_plein', '', { h: fmtH(d.plein_temps_min) }) : '';

    barres($('#tm-act-liste'),
           (d.par_activite || []).slice().sort((a, b) => b.annuel_min - a.annuel_min)
             .map(a2 => ({ nom: a2.activite, annuel_min: a2.annuel_min })), 0);
    if (!(d.par_activite || []).length && $('#tm-act-liste'))
      $('#tm-act-liste').innerHTML = `<div class="muted">${tl('tm_vide_act', '')}</div>`;
  }

  // ---------------------- INIT ------------------------
  (async () => {
    await loadCalendarParams();

    // Weakness: si la sous-page existe dans le DOM, init
    if ($('#subtab-faiblesse') || $('#fw-activity')) {
      // Construire le select activité de la faiblesse depuis la liste principale
      const fwAct = $('#fw-activity');
      if (fwAct && !fwAct.children.length) {
        const actOptions = $$('#act-activity option');
        if (actOptions.length) {
          fwAct.innerHTML = actOptions.map(o=>`<option value="${o.value}">${o.textContent}</option>`).join('');
        }
      }
    }

    await chargerTableauDeBord();

    // Prefill bloc Activité
    if ($('#act-activity') && $('#act-activity').value) {
      const r0 = await fetch(`/temps/api/activity_defaults/${$('#act-activity').value}`);
      const j0 = await r0.json();
      if (intact($('#act-duration'))) {
        $('#act-duration').value = parseFloat(j0.duration_minutes) || 0;
        $('#act-duration-unit').value = 'minutes';
      }
      majResultatActivite();
    }

    // Projet : une ligne par défaut au démarrage
    if ($$('#project-rows tr').length === 0 && $('#project-rows')) { addProjectRow(); recalcProjectTotals(); }

    // Rôle
    if ($('#role-select') && $('#role-select').value) {
      await loadRoleActivities($('#role-select').value);
      setTimeout(recalcRoleTotals, 0);
    }
  })();

})();