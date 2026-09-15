/* competences_v2.js — Page Compétences (V1.1, CDC 6).
   Parcours : Collaborateur → Synthèse tous rôles → Rôle → Activité → Résultats
   → (écart) → Diagnostic → Plan de formation.

   Trois partis pris tenus partout dans le fichier :

   1. L'écart est une DISTANCE, pas un nombre : requis et démontré se lisent sur
      la même jauge, et le requis est marqué là où l'on choisit.
   2. Un niveau NON ÉVALUÉ n'est pas un zéro (règle du CDC) : il se dessine en
      creux, et « effacer » est un bouton à part, jamais un palier de plus.
   3. Il y a DEUX notes et une seule fait foi. Le niveau validé par le
      développeur de compétences est le résultat ; l'auto-évaluation est un
      repère, utile aux deux, jamais officielle (CDC 3.6). Elles ne se
      ressemblent donc jamais à l'écran.

   Le masquage n'est pas une sécurité : les routes refusent de leur côté
   (Code/competences_acces.py). */
(function () {
  'use strict';
  const LANG = window.OPTIQ_LANG === 'en' ? 'en' : 'fr';
  const $ = s => document.querySelector(s);

  const I18N = {
    fr: {
      manager: 'Développeur de compétences', my_dev: 'Votre développeur de compétences',
      collaborators: 'Collaborateurs', me: 'Vous', no_collab: 'Aucun collaborateur.',
      no_dev: 'Aucun',
      no_dev_hint: "Aucun développeur de compétences ne vous est rattaché, et vous n'encadrez personne. La page Gestion RH permet d'affecter les collaborateurs à un développeur de compétences.",
      title: 'Compétences', pick_collab: 'Sélectionnez un collaborateur pour commencer.',
      pick_collab2: 'Sélectionnez un collaborateur pour voir où il en est.',
      c_activity: 'Activité', c_level: 'Niveau', c_required: 'Niveau requis',
      c_demonstrated: 'Niveau démontré', c_gap: 'Écart', c_tech: 'Technicité',
      tech_gap: 'Écart', tech_ok: 'Tenu',
      competence: 'Compétence principale', save_eval: "Enregistrer l'évaluation",
      save_self: 'Enregistrer mon auto-évaluation',
      evaluate: 'Évaluer', consult: 'Consulter', not_assessed: 'Non évalué', erase: 'Effacer',
      std: 'Standard minimal', saved: 'Évaluation enregistrée',
      no_activities: 'Aucune activité pour ce rôle.', no_roles: "Ce collaborateur n'a aucun rôle.",
      none: '—', back: '← Évaluation', back_synthese: "Vue d'ensemble", gen_plan: 'Générer le plan',
      cause_q: "Quelle est la cause de l'écart ?", linked_caps: 'Capacités reliées à ce résultat',
      no_gap: 'Aucun résultat en écart : le niveau requis est tenu.', dem: 'démontré', req: 'requis',
      gen: 'Génération…',
      validate_analysis: "Valider l'analyse", to_qualify: 'À qualifier',
      setup_done: 'Activité configurée', min_perf_ph: 'Standard minimal de performance…',
      no_out: "Cette activité n'a aucune donnée de sortie à qualifier.",
      req_set: 'Niveau requis mis à jour', not_set: 'Non défini',
      setup_btn: 'Analyser les sorties avec l’IA', setup_btn_off: 'Qualifier les sorties à la main',
      configure_short: 'Configurer',
      eval_hint: 'Fixez, pour chaque résultat, le niveau tenu par le collaborateur.',
      eval_hint_self: 'Situez-vous sur chaque résultat. Votre développeur de compétences verra votre estimation à côté de la sienne.',
      evidence_ph: 'Preuve / commentaire (facultatif)', add_evidence: '+ Ajouter une preuve',
      diagnose: "Diagnostiquer l'écart",
      configuring: 'Analyse des sorties en cours…', loading: 'Chargement…',
      need_result: "Marquez au moins une sortie comme « Résultat de l'activité » avant de valider : c'est ce niveau que vous évaluerez ensuite.",
      configured_go_eval: 'Sorties qualifiées ✓ — évaluez maintenant le niveau du collaborateur pour chaque résultat, puis enregistrez.',
      req_failed: 'Action impossible (erreur réseau ou serveur).',
      forbidden: "Vous n'avez pas le droit de noter ce collaborateur.",
      pick_level: 'À évaluer', roles_label: 'Rôles du collaborateur',
      self_assess: "S'auto-évaluer",
      pas_configuree: "Cette activité n'est pas encore configurée : son développeur de compétences doit d'abord qualifier ses données de sortie.",
      b_held: 'Niveau tenu', b_gap: 'En écart', b_todo: 'À évaluer', b_setup: 'À configurer',
      filter_off: 'Tout afficher', no_match: 'Aucune activité dans cette catégorie.',
      m_result_one: 'résultat', m_result_many: 'résultats', m_partial: 'sur',
      m_eval_one: 'évalué', m_eval_many: 'évalués',
      m_last: 'évalué le', m_never: 'jamais évaluée', m_toqualify: 'sorties à qualifier',
      target_short: 'requis',
      // Synthèse
      r_open: 'Ouvrir', r_activity_one: 'activité', r_activity_many: 'activités', r_level: 'Niveau du rôle',
      r_partial: 'Niveau non calculable tant que toutes les activités ne sont pas évaluées.',
      r_none: 'Aucune activité rattachée à ce rôle.',
      // Les deux notes
      n_official: 'Niveau validé', n_official_tag: 'fait foi', n_self: 'Auto-évaluation',
      n_self_mine: 'Votre auto-évaluation', n_by_dev: 'Niveau validé par votre développeur',
      n_none_yet: 'Pas encore validé', n_self_none: 'Pas encore renseignée',
      acc_ok: 'Même lecture', acc_haut: 'Se situe au-dessus', acc_bas: 'Se situe en dessous',
      acc_haut_mine: 'Vous vous situez au-dessus', acc_bas_mine: 'Vous vous situez en dessous',
      // Blocs
      bloc_cible: 'Le niveau attendu', bloc_cible_d: 'Ce que le rôle exige sur cette activité. Cliquez un palier pour le fixer.',
      bloc_cible_ro: "Ce que le rôle exige sur cette activité. Seul votre développeur de compétences peut le changer.",
      bloc_eval: "L'évaluation", bloc_tech: 'La technicité',
      bloc_tech_d: "Axe SÉPARÉ de la maîtrise : la même activité peut s'exercer dans des contextes techniques différents (ex. Plastique / Métal).",
      // IA
      ia_qualify_t: "Ce que l'IA fait ici",
      ia_qualify_d: "Elle lit l'activité — ses tâches, ses connexions sortantes, ses destinataires — et propose, pour chaque donnée produite, sa nature : est-ce un RÉSULTAT (ce dont la tenue démontre la maîtrise), une mesure, un événement, ou une simple information ?",
      ia_qualify_w: 'Rien n’est enregistré tant que vous n’avez pas validé, et chaque proposition reste modifiable.',
      ia_off_t: 'IA non configurée',
      ia_off_d: "Aucune clé IA n'est renseignée sur cette instance : qualifiez les sorties à la main. Rien n'est inventé à la place.",
      ia_conf_high: 'IA — sûr', ia_conf_medium: 'IA — à vérifier', ia_conf_low: 'IA — peu sûr',
      ia_touched: 'Corrigé à la main',
      // Plan de formation
      plan_title: 'Plan de formation', plan_open: 'Plan de formation',
      plan_none_t: 'Aucun écart sur ce rôle',
      plan_none_d: "Le niveau requis est tenu partout : il n'y a rien à combler.",
      plan_empty_t: 'Pas encore de plan',
      plan_empty_d: "Partez d'une proposition, puis ajustez les charges et les curseurs jusqu'à ce que le plan tienne dans le temps disponible.",
      plan_propose: 'Proposer un plan', plan_repropose: 'Proposer à nouveau',
      plan_save: 'Enregistrer le plan', plan_saved: 'Plan enregistré',
      plan_need: 'Ce qu’il y a à faire', plan_capacity: 'Ce qu’on peut y consacrer',
      plan_hours_week: 'Heures par semaine', plan_weeks: 'Durée visée',
      plan_week_unit: 'sem.', plan_h: 'h',
      plan_need_total: 'Besoin', plan_cap_total: 'Capacité',
      plan_ok: 'Le plan tient : il reste [[x]] h de marge sur la période.',
      plan_tendu: 'Ça passe de justesse — aucune marge en cas d’imprévu.',
      plan_trop: 'Il manque [[x]] h. Il faudrait [[s]] semaines à ce rythme, ou [[h]] h par semaine sur la durée visée.',
      plan_juste: 'Caler sur la durée juste nécessaire ([[s]] sem.)',
      plan_sched: 'Répartition semaine par semaine',
      plan_source_ai: 'Proposé par l’IA — à relire et ajuster',
      plan_source_local: 'Construit depuis les capacités en écart relevées en base (aucune clé IA)',
      plan_gap_intro: 'activité(s) sous le niveau requis',
      plan_del: 'Retirer cette action',
      plan_target: 'Objectif', plan_proof: 'Preuve attendue', plan_crit: 'Réussi quand',
    },
    en: {
      manager: 'Competency developer', my_dev: 'Your competency developer',
      collaborators: 'Team members', me: 'You', no_collab: 'No team member.',
      no_dev: 'None',
      no_dev_hint: 'No competency developer is attached to you, and you manage nobody. Use the HR page to attach team members to a competency developer.',
      title: 'Skills', pick_collab: 'Select a team member to start.',
      pick_collab2: 'Select a team member to see where they stand.',
      c_activity: 'Activity', c_level: 'Level', c_required: 'Required level',
      c_demonstrated: 'Demonstrated level', c_gap: 'Gap', c_tech: 'Technicity',
      tech_gap: 'Gap', tech_ok: 'Met',
      competence: 'Main competence', save_eval: 'Save evaluation',
      save_self: 'Save my self-assessment',
      evaluate: 'Evaluate', consult: 'View', not_assessed: 'Not assessed', erase: 'Clear',
      std: 'Minimum standard', saved: 'Evaluation saved',
      no_activities: 'No activity for this role.', no_roles: 'This team member has no role.',
      none: '—', back: '← Evaluation', back_synthese: 'Overview', gen_plan: 'Generate plan',
      cause_q: 'What is the cause of the gap?', linked_caps: 'Capabilities linked to this result',
      no_gap: 'No result below the required level.', dem: 'demonstrated', req: 'required',
      gen: 'Generating…',
      validate_analysis: 'Validate analysis', to_qualify: 'To qualify',
      setup_done: 'Activity configured', min_perf_ph: 'Minimum performance standard…',
      no_out: 'This activity has no output data to qualify.',
      req_set: 'Required level updated', not_set: 'Not set',
      setup_btn: 'Analyse outputs with AI', setup_btn_off: 'Qualify outputs manually',
      configure_short: 'Configure',
      eval_hint: 'For each result, set the level the team member holds.',
      eval_hint_self: 'Place yourself on each result. Your competency developer will see your estimate next to theirs.',
      evidence_ph: 'Evidence / comment (optional)', add_evidence: '+ Add evidence',
      diagnose: 'Diagnose the gap',
      configuring: 'Analysing outputs…', loading: 'Loading…',
      need_result: 'Mark at least one output as “Activity result” before validating: that is the level you will evaluate next.',
      configured_go_eval: 'Outputs qualified ✓ — now set the team member’s level for each result, then save.',
      req_failed: 'Action failed (network or server error).',
      forbidden: 'You are not allowed to assess this team member.',
      pick_level: 'To assess', roles_label: "Team member's roles",
      self_assess: 'Self-assess',
      pas_configuree: 'This activity is not configured yet: its competency developer must first qualify its output data.',
      b_held: 'Level met', b_gap: 'Below target', b_todo: 'To assess', b_setup: 'To configure',
      filter_off: 'Show all', no_match: 'No activity in this category.',
      m_result_one: 'result', m_result_many: 'results', m_partial: 'of',
      m_eval_one: 'assessed', m_eval_many: 'assessed',
      m_last: 'assessed on', m_never: 'never assessed', m_toqualify: 'outputs to qualify',
      target_short: 'required',
      r_open: 'Open', r_activity_one: 'activity', r_activity_many: 'activities', r_level: 'Role level',
      r_partial: 'Level cannot be computed until every activity is assessed.',
      r_none: 'No activity attached to this role.',
      n_official: 'Validated level', n_official_tag: 'official', n_self: 'Self-assessment',
      n_self_mine: 'Your self-assessment', n_by_dev: 'Level validated by your developer',
      n_none_yet: 'Not validated yet', n_self_none: 'Not filled in yet',
      acc_ok: 'Same reading', acc_haut: 'Rates themselves higher', acc_bas: 'Rates themselves lower',
      acc_haut_mine: 'You rate yourself higher', acc_bas_mine: 'You rate yourself lower',
      bloc_cible: 'The expected level', bloc_cible_d: 'What the role requires on this activity. Click a step to set it.',
      bloc_cible_ro: 'What the role requires on this activity. Only your competency developer can change it.',
      bloc_eval: 'The assessment', bloc_tech: 'Technicity',
      bloc_tech_d: 'A SEPARATE axis from mastery: the same activity can be performed in different technical contexts (e.g. Plastic / Metal).',
      ia_qualify_t: 'What the AI does here',
      ia_qualify_d: 'It reads the activity — its tasks, outgoing connections and recipients — and proposes, for each piece of data produced, its nature: is it a RESULT (what demonstrates mastery when met), a measure, an event, or plain information?',
      ia_qualify_w: 'Nothing is saved until you validate, and every proposal stays editable.',
      ia_off_t: 'AI not configured',
      ia_off_d: 'No AI key is set on this instance: qualify the outputs manually. Nothing is invented in its place.',
      ia_conf_high: 'AI — confident', ia_conf_medium: 'AI — check it', ia_conf_low: 'AI — unsure',
      ia_touched: 'Edited manually',
      plan_title: 'Training plan', plan_open: 'Training plan',
      plan_none_t: 'No gap on this role',
      plan_none_d: 'The required level is met everywhere: there is nothing to close.',
      plan_empty_t: 'No plan yet',
      plan_empty_d: 'Start from a proposal, then adjust the workloads and the sliders until the plan fits the time available.',
      plan_propose: 'Propose a plan', plan_repropose: 'Propose again',
      plan_save: 'Save plan', plan_saved: 'Plan saved',
      plan_need: 'What has to be done', plan_capacity: 'What we can put in',
      plan_hours_week: 'Hours per week', plan_weeks: 'Target duration',
      plan_week_unit: 'wk', plan_h: 'h',
      plan_need_total: 'Need', plan_cap_total: 'Capacity',
      plan_ok: 'The plan fits: [[x]] h of slack over the period.',
      plan_tendu: 'It just fits — no slack if anything slips.',
      plan_trop: '[[x]] h short. You would need [[s]] weeks at this pace, or [[h]] h per week over the target duration.',
      plan_juste: 'Snap to the duration actually needed ([[s]] wk)',
      plan_sched: 'Week by week',
      plan_source_ai: 'Proposed by AI — review and adjust',
      plan_source_local: 'Built from the capability gaps recorded in the database (no AI key)',
      plan_gap_intro: 'activity(ies) below the required level',
      plan_del: 'Remove this action',
      plan_target: 'Objective', plan_proof: 'Expected evidence', plan_crit: 'Done when',
    },
  };
  // Clés communes aux deux langues, déclarées une fois.
  const COMMUN = {
    tech_exp: {
      fr: "Fixez le niveau technique requis par le rôle et le niveau démontré par le collaborateur.",
      en: 'Set the technical level required by the role and the level demonstrated by the team member.' },
    tech_required: { fr: 'Requis', en: 'Required' },
    tech_demonstrated: { fr: 'Démontré', en: 'Demonstrated' },
    tech_add_ph: { fr: 'Nouveau domaine (ex. Plastique)…', en: 'New domain (e.g. Plastic)…' },
    tech_link: { fr: 'Ajouter', en: 'Add' },
    tech_pick: { fr: 'Choisir un domaine existant…', en: 'Pick an existing domain…' },
    tech_empty: { fr: 'Aucun domaine technique lié à cette activité.', en: 'No technical domain linked to this activity.' },
    qualify_title: { fr: 'Qualification des sorties', en: 'Output qualification' },
  };
  Object.keys(COMMUN).forEach(k => { I18N.fr[k] = COMMUN[k].fr; I18N.en[k] = COMMUN[k].en; });

  const T = k => (I18N[LANG][k] || k);
  const Tv = (k, vars) => Object.keys(vars || {}).reduce(
    (s, v) => s.split('[[' + v + ']]').join(vars[v]), T(k));

  const state = {
    moi: null, estDev: false,
    cible: null, cibleNom: '',
    ecran: null, roleId: null, roleName: null,
    scale: {}, notAssessed: 'Non évalué', domScale: {},
    rows: [], filtre: null, activity: null, lastState: null,
    plan: null,
  };

  // Qui écrit quoi : '2' = le développeur pose le niveau qui fait foi,
  // '0' = le collaborateur pose son auto-évaluation.
  const jeSuisLeDev = () => state.estDev && state.cible !== (state.moi && state.moi.id);
  const monEvaluateur = () => (jeSuisLeDev() ? '2' : '0');

  // ══ Utilitaires ════════════════════════════════════════════════════
  async function api(url, opts, silencieux) {
    const rate = msg => { if (!silencieux) toast(msg); };
    try {
      const r = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
      const txt = await r.text();
      let data; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = null; }
      if (!r.ok || data === null) {
        rate(r.status === 403 ? T('forbidden') : T('req_failed'));
        return { __error: true, status: r.status };
      }
      return data;
    } catch (e) { rate(T('req_failed')); return { __error: true }; }
  }
  function toast(msg) {
    const t = $('#cv2-toast'); t.textContent = msg; t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2100);
  }
  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function applyStaticI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const k = el.dataset.i18n; if (I18N[LANG][k]) el.textContent = I18N[LANG][k];
    });
  }
  const estNul = v => v === null || v === undefined;
  function levelName(lvl) { return estNul(lvl) ? state.notAssessed : (state.scale[String(lvl)] || String(lvl)); }
  function initials(f, l) { return ((f || '')[0] || '').toUpperCase() + ((l || '')[0] || '').toUpperCase(); }
  function fmtDate(iso) {
    if (!iso) return T('none');
    try { return new Date(iso).toLocaleDateString(LANG === 'en' ? 'en-GB' : 'fr-FR'); } catch (e) { return T('none'); }
  }

  // ══ Chargement initial ═════════════════════════════════════════════
  async function boot() {
    applyStaticI18n();
    bindDrawer();
    bindPlan();
    const [sc, ds] = await Promise.all([api('/mastery/scale'), api('/domains/scale')]);
    state.scale = sc.mastery || {}; state.notAssessed = sc.not_assessed || T('not_assessed');
    state.domScale = (ds && ds.scale) || {};

    const ctx = await api('/competences/contexte', undefined, true);
    if (!ctx || ctx.__error) { montrerVide(T('no_dev_hint')); return; }
    state.moi = ctx.moi; state.estDev = !!ctx.est_dev; state.iaDispo = !!ctx.ia_disponible;

    $('#cv2-mgr-lbl').textContent = state.estDev ? T('manager') : T('my_dev');
    $('#cv2-mgr-name').textContent = ctx.dev ? ctx.dev.name : T('no_dev');
    $('#cv2-mgr-av').textContent = ctx.dev ? (initials(...String(ctx.dev.name).split(' ')) || 'M') : '—';

    // Le collaborateur se voit LUI dans la liste : c'est son propre dossier
    // qu'il vient consulter et compléter.
    const gens = state.estDev ? ctx.collaborateurs
      : [{ id: ctx.moi.id, first_name: ctx.moi.first_name, last_name: ctx.moi.last_name, moi: true }];
    $('#cv2-collab-title').textContent = state.estDev ? T('collaborators') : T('me');
    renderCollabs(gens);
    // Un seul dossier à regarder : on l'ouvre, personne n'a envie de cliquer
    // sur son propre nom pour entrer chez soi.
    if (gens.length === 1) choisirCollab(gens[0], $('#cv2-collab').firstElementChild);
  }

  function renderCollabs(list) {
    const ul = $('#cv2-collab'); ul.innerHTML = '';
    if (!list.length) {
      $('#cv2-collab-empty').classList.remove('hidden');
      montrerVide(T('no_dev_hint'));
      return;
    }
    $('#cv2-collab-empty').classList.add('hidden');
    list.forEach(u => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="av">${esc(initials(u.first_name, u.last_name))}</span>` +
        `<span>${esc(u.first_name)} ${esc(u.last_name)}</span><span class="chev">›</span>`;
      li.onclick = () => choisirCollab(u, li);
      ul.appendChild(li);
    });
  }

  function montrerVide(msg) {
    ['#cv2-ecran-synthese', '#cv2-ecran-role'].forEach(s => $(s).classList.add('hidden'));
    const ph = $('#cv2-placeholder'); ph.classList.remove('hidden'); ph.textContent = msg;
  }
  function montrerEcran(nom) {
    state.ecran = nom;
    $('#cv2-placeholder').classList.add('hidden');
    $('#cv2-ecran-synthese').classList.toggle('hidden', nom !== 'synthese');
    $('#cv2-ecran-role').classList.toggle('hidden', nom !== 'role');
  }

  // ══ ÉCRAN 1 — la synthèse ══════════════════════════════════════════
  async function choisirCollab(u, li) {
    document.querySelectorAll('.cv2-collab li').forEach(x => x.classList.remove('active'));
    if (li) li.classList.add('active');
    state.cible = u.id; state.cibleNom = `${u.first_name} ${u.last_name}`.trim();
    $('#cv2-sub').textContent = state.cibleNom;
    await chargerSynthese();
  }

  async function chargerSynthese() {
    const d = await api(`/mastery/synthese/${state.cible}`);
    if (d.__error) { montrerVide(T('req_failed')); return; }
    state.synthese = d;
    montrerEcran('synthese');
    renderBilan($('#cv2-bilan'), d.totals, null);
    const box = $('#cv2-rolecards'); box.innerHTML = '';
    if (!d.roles.length) { box.innerHTML = `<div class="cv2-vide">${esc(T('no_roles'))}</div>`; return; }
    d.roles.forEach((r, i) => box.appendChild(carteRole(r, i)));
  }

  function carteRole(r, i) {
    const el = document.createElement('div');
    const teinte = r.n_activities ? (r.color || 'grey') : 'grey';
    el.className = `cv2-rolecard cv2-rolecard--${teinte}`;
    el.style.animation = `cv2-entre .26s ease-out ${i * 45}ms backwards`;

    const etats = [
      ['held', T('b_held'), 'green'], ['gap', T('b_gap'), 'orange'],
      ['todo', T('b_todo'), 'blue'], ['setup', T('b_setup'), 'grey'],
    ].filter(([k]) => r.counts[k])
      .map(([k, lib, t]) => `<span class="cv2-etat cv2-etat--${t}"><i></i>${r.counts[k]} ${esc(lib)}</span>`)
      .join('');

    // Le niveau d'un rôle est le MINIMUM de ses activités, et il n'existe que
    // si toutes sont évaluées : une moyenne partielle laisserait croire qu'un
    // rôle à moitié noté est tenu.
    const partiel = estNul(r.level) && (r.counts.todo || r.counts.setup);
    el.innerHTML = `
      <div class="rc-tete">
        <div>
          <div class="rc-nom">${esc(r.role_name)}</div>
          <div class="rc-n">${r.n_activities} ${esc(r.n_activities === 1 ? T('r_activity_one') : T('r_activity_many'))}</div>
        </div>
      </div>
      <div class="rc-jauge">${blocJauge(r.level, r.required_level, r.color, r.gap, r.level_label)}</div>
      <div class="cv2-etats">${etats || `<span class="cv2-etat cv2-etat--grey"><i></i>${esc(T('r_none'))}</span>`}</div>
      <div class="rc-pieds">
        ${partiel ? `<div class="rc-note">${esc(T('r_partial'))}</div>` : ''}
        ${r.n_gap && jeSuisLeDev() ? `<button type="button" class="btn btn-ghost btn-sm" data-plan="1">${esc(T('plan_open'))}</button>` : ''}
        <button type="button" class="btn btn-primary btn-sm" data-ouvrir="1">${esc(T('r_open'))}</button>
      </div>`;
    el.querySelector('[data-ouvrir]').onclick = () => ouvrirRole(r);
    const bp = el.querySelector('[data-plan]');
    if (bp) bp.onclick = () => { state.roleId = r.role_id; state.roleName = r.role_name; ouvrirPlan(); };
    return el;
  }

  // Une jauge + son libellé + son écart, réutilisée par la carte de rôle et la
  // ligne d'activité : la même information ne peut pas se lire de deux façons.
  function blocJauge(niveau, requis, couleur, ecart, libelle) {
    const req = estNul(requis) ? null : requis;
    const inconnu = estNul(niveau);
    const titre = [
      `${T('c_demonstrated')} : ${inconnu ? state.notAssessed : (libelle || levelName(niveau))}`,
      req === null ? '' : `${T('target_short')} : ${req} · ${levelName(req)}`,
    ].filter(Boolean).join(' — ');
    return `<div class="cv2-jauge cv2-j--${esc(couleur || 'grey')}" title="${esc(titre)}">
        ${jauge(niveau, req, couleur)}
        <span class="cv2-jauge-txt">
          <span class="lv">${esc(inconnu ? state.notAssessed : (libelle || levelName(niveau)))}</span>
        </span>
        ${badgeEcart(ecart)}
      </div>`;
  }

  // ══ La jauge ═══════════════════════════════════════════════════════
  // Quatre pas = les niveaux 1 à 4. Le niveau 0 « Non démontré » est une jauge
  // VIDE — c'est exactement ce qu'il veut dire. Non évalué (null) se dessine en
  // creux : une absence, pas un zéro.
  function jauge(niveau, requis, couleur) {
    const inconnu = estNul(niveau);
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

  // Seul un écart NÉGATIF porte un badge : c'est le cas qui demande une action.
  function badgeEcart(gap) {
    if (estNul(gap) || gap >= 0) return '';
    return `<span class="cv2-ecart neg">${gap}</span>`;
  }

  function categorie(a) {
    if (!a.n_results) return 'setup';
    if (estNul(a.demonstrated_level)) return 'todo';
    if (a.demonstrated_level < 2) return 'gap';
    if (!estNul(a.required_level) && a.demonstrated_level < a.required_level) return 'gap';
    return 'held';
  }

  // ══ Le bandeau de situation ════════════════════════════════════════
  function renderBilan(box, compte, onFiltre) {
    box.innerHTML = '';
    const tuiles = [
      ['held', T('b_held'), 'green'], ['gap', T('b_gap'), 'orange'],
      ['todo', T('b_todo'), 'blue'], ['setup', T('b_setup'), 'grey'],
    ];
    tuiles.forEach(([cle, libelle, teinte]) => {
      if (!compte[cle] && state.filtre !== cle) return;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = `cv2-tuile cv2-tuile--${teinte}` + (onFiltre && state.filtre === cle ? ' is-on' : '');
      b.innerHTML = `<div class="n"><span class="pt"></span>${compte[cle]}</div><div class="k">${esc(libelle)}</div>`;
      if (onFiltre) {
        b.title = state.filtre === cle ? T('filter_off') : libelle;
        b.onclick = () => onFiltre(cle);
      } else { b.disabled = true; b.style.cursor = 'default'; }
      box.appendChild(b);
    });
    box.classList.toggle('hidden', !box.children.length);
  }

  // ══ ÉCRAN 2 — le détail d'un rôle ══════════════════════════════════
  async function ouvrirRole(r) {
    state.roleId = r.role_id || r.id; state.roleName = r.role_name || r.name; state.filtre = null;
    const d = await api(`/mastery/dashboard/${state.cible}/${state.roleId}`);
    if (d.__error) return;
    montrerEcran('role');
    $('#cv2-fil-role').textContent = state.roleName;
    renderDashboard(d);
  }

  function renderDashboard(d, reutiliser) {
    if (!reutiliser) state.rows = (d && d.activities) || [];
    const rows = state.rows;
    const compte = { held: 0, gap: 0, todo: 0, setup: 0 };
    rows.forEach(a => { compte[categorie(a)] += 1; });
    renderBilan($('#cv2-bilan-role'), compte, cle => {
      state.filtre = state.filtre === cle ? null : cle; renderDashboard(null, true);
    });
    // Le plan n'a de sens que s'il y a un écart à combler.
    $('#cv2-btn-plan').classList.toggle('hidden', !compte.gap || !jeSuisLeDev());

    const box = $('#cv2-lignes'); box.innerHTML = '';
    if (!rows.length) { box.innerHTML = `<div class="cv2-vide">${esc(T('no_activities'))}</div>`; return; }
    const visibles = state.filtre ? rows.filter(a => categorie(a) === state.filtre) : rows;
    if (!visibles.length) { box.innerHTML = `<div class="cv2-vide">${esc(T('no_match'))}</div>`; return; }
    visibles.forEach(a => box.appendChild(ligneActivite(a)));
  }

  function ligneActivite(a) {
    const cat = categorie(a);
    const el = document.createElement('div');
    el.className = 'cv2-ligne';
    const libelleBtn = cat === 'setup'
      ? (jeSuisLeDev() ? T('configure_short') : T('consult'))
      : (jeSuisLeDev() ? T('evaluate') : T('self_assess'));
    el.innerHTML = `
      <div>
        <div class="cv2-nom">${esc(a.activity_name)}</div>
        ${a.competence ? `<div class="cv2-comp-line" title="${esc(a.competence)}">${esc(a.competence)}</div>` : ''}
        <div class="cv2-meta">${metaActivite(a)}</div>
      </div>
      <div>${blocJauge(a.demonstrated_level, a.required_level, a.color || 'grey', a.gap, a.demonstrated_label)}</div>
      <div class="cv2-cell-tech">${celluleTech(a.technicity)}</div>
      <div class="cv2-cell-act">
        <button class="btn btn-sm ${cat === 'setup' && jeSuisLeDev() ? 'btn-todo' : 'btn-primary'}">
          ${esc(libelleBtn)}</button>
      </div>`;
    el.querySelector('button').onclick = () => openDrawer(a);
    return el;
  }

  function metaActivite(a) {
    if (!a.n_results) return `<span>${esc(T('m_toqualify'))}</span>`;
    const bouts = [];
    const nEval = estNul(a.n_evaluated) ? null : a.n_evaluated;
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

  function chip(color, label) { return `<span class="chip ${esc(color)}"><span class="lv"></span>${esc(label)}</span>`; }
  const dash = () => `<span class="cv2-dash">${T('none')}</span>`;
  function celluleTech(status) {
    if (status === 'gap') return chip('orange', T('tech_gap'));
    if (status === 'ok') return chip('green', T('tech_ok'));
    return dash();
  }

  // ══ Fenêtre d'évaluation ═══════════════════════════════════════════
  function bindDrawer() {
    $('#cv2-drawer-close').onclick = closeDrawer;
    $('#cv2-overlay').onclick = () => { closeDrawer(); fermerPlan(); };
    $('#cv2-retour').onclick = () => chargerSynthese();
    $('#cv2-btn-plan').onclick = () => ouvrirPlan();
    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      if ($('#cv2-plan-win').classList.contains('open')) fermerPlan();
      else if ($('#cv2-drawer').classList.contains('open')) closeDrawer();
    });
  }
  function closeDrawer() {
    $('#cv2-drawer').classList.remove('open');
    if (!$('#cv2-plan-win').classList.contains('open')) $('#cv2-overlay').classList.remove('open');
  }

  function setFooter(buttons, cible) {
    const f = $(cible || '#cv2-footer'); f.innerHTML = '';
    f.classList.toggle('hidden', !buttons.length);
    buttons.forEach(b => {
      const el = document.createElement('button');
      el.className = 'btn ' + b.cls; el.textContent = b.label; el.onclick = b.on;
      if (b.id) el.id = b.id;
      f.appendChild(el);
    });
  }
  function showBusy(msg, cible) {
    $(cible || '#cv2-drawer-body').innerHTML =
      `<div class="cv2-busy"><span class="cv2-spin"></span><div>${esc(msg || T('loading'))}</div></div>`;
  }

  function openDrawer(row) {
    state.activity = row;
    $('#cv2-drawer-title').textContent = row.activity_name;
    $('#cv2-drawer-role').textContent = `${state.cibleNom} · ${state.roleName}`;
    $('#cv2-drawer').classList.add('open'); $('#cv2-overlay').classList.add('open');
    $('#cv2-drawer-body').scrollTop = 0;
    showEvaluation();
  }

  async function showEvaluation() {
    showBusy();
    setFooter([]);
    const st = await api(`/mastery/activity/${state.cible}/${state.activity.activity_id}?role_id=${state.roleId}`);
    if (st.__error) return;
    state.lastState = st;
    renderResults(st);
  }

  function bloc(numero, titre, detail, variante, aDroite) {
    const b = document.createElement('div');
    b.className = 'cv2-bloc' + (variante ? ' cv2-bloc--' + variante : '');
    b.innerHTML = `<div class="cv2-bloc-tete">
        <span class="cv2-bloc-num">${numero}</span>
        <div class="cv2-bloc-txt"><div class="cv2-bloc-h">${esc(titre)}</div>
        ${detail ? `<div class="cv2-bloc-d">${esc(detail)}</div>` : ''}</div>
        ${aDroite || ''}
      </div>`;
    return b;
  }

  function renderResults(st) {
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const aEvaluer = !!(st.results && st.results.length);

    if (state.activity.competence) {
      const c = document.createElement('div'); c.className = 'cv2-comp';
      c.innerHTML = `<span class="tag">${esc(T('competence'))}</span>${esc(state.activity.competence)}`;
      body.appendChild(c);
    }
    // ── Bloc 1 : le niveau attendu ──────────────────────────────────
    // Il n'y a plus de bandeau récapitulatif au-dessus : il répétait le niveau
    // requis que ce bloc sert justement à régler, et deux affichages du même
    // nombre finissent toujours par diverger.
    const b1 = bloc(1, T('bloc_cible'), jeSuisLeDev() ? T('bloc_cible_d') : T('bloc_cible_ro'));
    b1.appendChild(cibleRequise(st));
    body.appendChild(b1);

    // ── Bloc 2 : l'évaluation ───────────────────────────────────────
    // Le niveau qui fait foi se lit dans l'en-tête du bloc : c'est le résultat
    // de ce qu'on y règle, il appartient à cette section.
    const resume = aEvaluer ? `<div class="cv2-bloc-bilan">
        <div class="k">${esc(T('n_official'))} <span class="cv2-officielle-tag">${esc(T('n_official_tag'))}</span></div>
        ${blocJauge(st.global_level, estNul(st.required_level) ? null : st.required_level,
                    st.color, st.gap, st.global_label)}
      </div>` : '';
    const b2 = bloc(2, T('bloc_eval'), jeSuisLeDev() ? T('eval_hint') : T('eval_hint_self'), null, resume);
    body.appendChild(b2);

    if (!aEvaluer) {
      // Le collaborateur n'a rien à configurer : lui expliquer ce que l'IA fait
      // dans un écran qu'il ne peut pas actionner n'aiderait personne.
      if (jeSuisLeDev()) {
        b2.appendChild(panneauIA(true));
        const b = document.createElement('button');
        b.className = 'btn btn-primary';
        b.textContent = state.iaDispo ? T('setup_btn') : T('setup_btn_off');
        b.onclick = () => showQualify(b);
        b2.appendChild(b);
      } else {
        const w = document.createElement('div'); w.className = 'cv2-warn';
        w.textContent = T('pas_configuree'); b2.appendChild(w);
      }
      body.appendChild(blocTechnicite());
      setFooter([]);
      return;
    }

    if (state.justConfigured) {
      state.justConfigured = false;
      const ok = document.createElement('div'); ok.className = 'cv2-ok';
      ok.textContent = T('configured_go_eval'); b2.appendChild(ok);
    }
    st.results.forEach(r => b2.appendChild(resultCard(r, st.required_level)));
    body.appendChild(blocTechnicite());

    const pied = [{
      cls: 'btn-primary', id: 'cv2-save-btn',
      label: jeSuisLeDev() ? T('save_eval') : T('save_self'), on: saveEvaluation,
    }];
    if (jeSuisLeDev() && aUnEcart(st)) pied.unshift({ cls: 'btn-ghost', label: T('diagnose'), on: showDiagnostic });
    setFooter(pied);
  }

  function aUnEcart(st) {
    const req = st.required_level;
    return (st.results || []).some(r => !estNul(r.demonstrated_level)
      && (r.demonstrated_level < 2 || (!estNul(req) && r.demonstrated_level < req)));
  }

  // ── Le niveau requis ──────────────────────────────────────────────
  // ⚠️ C'était un lien « modifier » qui dépliait six boutons gris : rien ne
  // disait que c'était réglable, ni qu'il s'agissait d'une CIBLE.
  function cibleRequise(st) {
    const wrap = document.createElement('div');
    const req = estNul(st.required_level) ? null : st.required_level;
    const peut = jeSuisLeDev();
    let html = `<div class="cv2-cible">`;
    for (let lv = 0; lv <= 4; lv++) {
      html += `<button type="button" class="cv2-cible-niv${req === lv ? ' sel' : ''}" data-req="${lv}"
        ${peut ? '' : 'disabled'} title="${esc(levelName(lv))}">${lv}</button>`;
    }
    html += `<button type="button" class="cv2-cible-off${req === null ? ' sel' : ''}" data-req=""
      ${peut ? '' : 'disabled'}>${esc(T('not_set'))}</button></div>
      <div class="cv2-cible-dit">${req === null ? esc(T('not_set'))
        : `${req} · ${esc(levelName(req))}`}</div>`;
    wrap.innerHTML = html;
    if (peut) {
      wrap.querySelectorAll('[data-req]').forEach(b => b.onclick = () => {
        const v = b.dataset.req;
        setRequired(v === '' ? null : +v);
      });
    }
    return wrap;
  }

  // ── La carte d'un RÉSULTAT ────────────────────────────────────────
  // L'échelle interactive porte MA note ; l'autre note s'affiche à côté, dans
  // une forme qui ne peut pas être confondue avec elle.
  function resultCard(r, requis) {
    const card = document.createElement('div');
    const maNote = jeSuisLeDev() ? r.demonstrated_level : r.self_level;
    const autreNote = jeSuisLeDev() ? r.self_level : r.demonstrated_level;
    card.className = 'cv2-res' + (estNul(maNote) ? '' : ' est-note');
    card.dataset.dataId = r.data_id;
    const req = estNul(requis) ? null : requis;

    let paliers = '';
    for (let lv = 0; lv <= 4; lv++) {
      const sel = maNote === lv ? ' sel' : '';
      const cible = req === lv ? ' cible' : '';
      // Le repère de l'AUTRE note, posé sur l'échelle : on voit l'accord ou le
      // désaccord pendant qu'on choisit, sans quitter des yeux ce qu'on fait.
      const autre = (!estNul(autreNote) && autreNote === lv) ? ' auto' : '';
      const bulle = levelName(lv) + (req === lv ? ` — ${T('target_short')}` : '');
      paliers += `<button type="button" class="cv2-niv${sel}${cible}${autre}" data-lv="${lv}"
        title="${esc(bulle)}">${lv}</button>`;
    }
    const efface = estNul(maNote) ? ' sel' : '';
    const preuve = (jeSuisLeDev() ? r.evidence : r.self_evidence) || '';

    card.innerHTML = `
      <div class="rtete">
        <div class="rname">${esc(r.name)}
          ${r.minimum_performance_text ? `<div class="rstd">${esc(T('std'))} : ${esc(r.minimum_performance_text)}</div>` : ''}
        </div>
      </div>
      <div class="cv2-note">
        <div class="nlbl"><span class="pastille"></span>${esc(jeSuisLeDev() ? T('n_official') : T('n_self_mine'))}
          ${jeSuisLeDev() ? `<span class="cv2-officielle-tag">${esc(T('n_official_tag'))}</span>` : ''}</div>
      </div>
      <div class="cv2-echelle">
        ${paliers}
        <button type="button" class="cv2-gomme${efface}" data-lv="">${esc(T('erase'))}</button>
      </div>
      <div class="cv2-lu"></div>
      ${autreLigne(autreNote, maNote)}
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

  // La note de l'autre, et ce qu'elle dit de l'accord entre les deux.
  function autreLigne(autre, mienne) {
    const dev = jeSuisLeDev();
    const titre = dev ? T('n_self') : T('n_by_dev');
    if (estNul(autre)) {
      return `<div class="cv2-note cv2-note--auto"><div class="nlbl"><span class="pastille"></span>${esc(titre)}</div>
        <div class="cv2-auto">${esc(dev ? T('n_self_none') : T('n_none_yet'))}</div></div>`;
    }
    let accord = '';
    if (!estNul(mienne)) {
      // Comparaison du point de vue de celui qui regarde : « il se situe
      // au-dessus » pour le développeur, « vous vous situez » pour l'intéressé.
      const auto = dev ? autre : mienne;
      const off = dev ? mienne : autre;
      const cls = auto === off ? 'ok' : (auto > off ? 'haut' : 'bas');
      const cle = cls === 'ok' ? 'acc_ok'
        : (dev ? (cls === 'haut' ? 'acc_haut' : 'acc_bas')
               : (cls === 'haut' ? 'acc_haut_mine' : 'acc_bas_mine'));
      accord = `<span class="cv2-accord cv2-accord--${cls}">${esc(T(cle))}</span>`;
    }
    // Une seule ligne : libellé, niveau et verdict. En trois lignes, la note de
    // repère pesait autant à l'œil que celle qui fait foi.
    return `<div class="cv2-note cv2-note--auto cv2-note--ligne">
        <span class="nlbl"><span class="pastille"></span>${esc(titre)}</span>
        <span class="cv2-auto"><b>${autre}</b> · ${esc(levelName(autre))}</span>
        ${accord}
      </div>`;
  }

  async function saveEvaluation() {
    const cards = document.querySelectorAll('#cv2-drawer-body .cv2-res');
    const btn = $('#cv2-save-btn'); if (btn) btn.disabled = true;
    for (const c of cards) {
      const sel = c.querySelector('[data-lv].sel');
      if (!sel) continue;
      const raw = sel.dataset.lv;
      const r = await api('/mastery/evaluate', {
        method: 'POST',
        body: JSON.stringify({
          user_id: state.cible, activity_id: state.activity.activity_id, data_id: +c.dataset.dataId,
          evaluator: monEvaluateur(), mastery_level: raw === '' ? null : +raw,
          evidence: c.querySelector('.cv2-ev').value, role_id: state.roleId,
        }),
      });
      if (r.__error) { if (btn) btn.disabled = false; return; }
    }
    toast(T('saved'));
    await showEvaluation();
    await refreshDashboard();
  }

  async function setRequired(lvl) {
    const r = await api('/mastery/required', {
      method: 'POST',
      body: JSON.stringify({
        activity_id: state.activity.activity_id, role_id: state.roleId, required_mastery_level: lvl }),
    });
    if (r.__error) return;
    toast(T('req_set'));
    await showEvaluation();
    await refreshDashboard();
  }

  async function refreshDashboard() {
    const d = await api(`/mastery/dashboard/${state.cible}/${state.roleId}`);
    if (d && d.activities) {
      renderDashboard(d);
      const row = d.activities.find(a => a.activity_id === state.activity.activity_id);
      if (row) state.activity = row;
    }
  }

  // ══ Technicité — axe SÉPARÉ de la maîtrise (CDC 4) ═════════════════
  function blocTechnicite() {
    const b = bloc(3, T('bloc_tech'), T('bloc_tech_d'), 'tech');
    const zone = document.createElement('div');
    zone.innerHTML = `<div class="cv2-domlist"></div><div class="cv2-domadd"></div>`;
    b.appendChild(zone);
    loadTech(zone);
    return b;
  }
  function domSelect(val, onchange) {
    const s = document.createElement('select'); s.className = 'cv2-domsel';
    const opts = [['', '—']].concat(Object.keys(state.domScale).map(k => [k, `${k} · ${state.domScale[k]}`]));
    opts.forEach(([v, l]) => {
      const o = document.createElement('option'); o.value = v; o.textContent = l;
      if (estNul(val) ? v === '' : String(val) === v) o.selected = true;
      s.appendChild(o);
    });
    s.onchange = () => onchange(s.value === '' ? null : +s.value);
    if (!jeSuisLeDev()) s.disabled = true;
    return s;
  }
  async function loadTech(zone) {
    const aid = state.activity.activity_id;
    const [dom, all] = await Promise.all([
      api(`/domains/activity/${aid}?role_id=${state.roleId}&user_id=${state.cible}`), api('/domains/list')]);
    renderDomList(zone.querySelector('.cv2-domlist'), aid, (dom && dom.domains) || []);
    if (jeSuisLeDev()) renderDomAdd(zone, aid, (all && all.domains) || [], (dom && dom.domains) || []);
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
        { user_id: state.cible, domain_id: d.domain_id, demonstrated_level: v }, list, aid)));
      row.appendChild(rq); row.appendChild(dm);
      if (!estNul(d.gap)) {
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
    const dom = await api(`/domains/activity/${aid}?role_id=${state.roleId}&user_id=${state.cible}`);
    renderDomList(list, aid, (dom && dom.domains) || []);
    refreshDashboard();
  }
  function renderDomAdd(zone, aid, allDomains, linked) {
    const add = zone.querySelector('.cv2-domadd'); add.innerHTML = '';
    const linkedIds = new Set(linked.map(d => d.domain_id));
    const avail = allDomains.filter(d => !linkedIds.has(d.id));
    if (avail.length) {
      const sel = document.createElement('select'); sel.className = 'cv2-domsel';
      sel.innerHTML = `<option value="">${esc(T('tech_pick'))}</option>` +
        avail.map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
      const b = document.createElement('button'); b.className = 'btn btn-ghost btn-sm'; b.textContent = T('tech_link');
      b.onclick = async () => { if (!sel.value) return; await linkDom(aid, +sel.value); await loadTech(zone); };
      add.appendChild(sel); add.appendChild(b);
    }
    const inp = document.createElement('input'); inp.placeholder = T('tech_add_ph');
    const cb = document.createElement('button'); cb.className = 'btn btn-primary btn-sm'; cb.textContent = '＋';
    cb.onclick = async () => {
      const nm = inp.value.trim(); if (!nm) return;
      const r = await api('/domains/create', { method: 'POST', body: JSON.stringify({ name_fr: nm }) });
      if (r && r.id) { await linkDom(aid, r.id); inp.value = ''; await loadTech(zone); }
    };
    add.appendChild(inp); add.appendChild(cb);
  }
  async function linkDom(aid, did) {
    await api(`/domains/activity/${aid}/link`, { method: 'POST', body: JSON.stringify({ domain_id: did }) });
    refreshDashboard();
  }

  // ══ Ce que l'IA fait ═══════════════════════════════════════════════
  // ⚠️ On lançait une analyse sans jamais dire ce qu'elle allait faire ni ce
  // qu'elle avait fait. Une proposition de la machine s'annonce et se justifie.
  function panneauIA(avant) {
    const off = state.iaDispo === false;
    const d = document.createElement('div');
    d.className = 'cv2-ia' + (off ? ' cv2-ia--off' : '');
    d.innerHTML = `<span class="cv2-ia-ico"><i class="fa-solid fa-wand-magic-sparkles"></i></span>
      <div><div class="cv2-ia-t">${esc(off ? T('ia_off_t') : T('ia_qualify_t'))}</div>
      <div class="cv2-ia-d">${esc(off ? T('ia_off_d') : T('ia_qualify_d'))}
      ${off || !avant ? '' : `<div style="margin-top:6px;font-style:italic">${esc(T('ia_qualify_w'))}</div>`}</div></div>`;
    return d;
  }

  async function showQualify(btn) {
    if (btn) { btn.disabled = true; btn.textContent = T('gen'); }
    const aid = state.activity.activity_id;
    showBusy(T('configuring'));
    setFooter([]);
    const [outs, ana] = await Promise.all([api(`/qualify/outputs/${aid}`), api(`/qualify/analyze/${aid}`, { method: 'POST' })]);
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    // La source dit si une IA a réellement répondu. On ne présente jamais un
    // repli comme une analyse.
    state.iaDispo = !(ana && ana.source && ana.source !== 'AI');
    const b = bloc(1, T('qualify_title'), null);
    body.appendChild(b);
    b.appendChild(panneauIA(false));

    const outputs = outs.outputs || [], labels = outs.labels || {};
    if (!outputs.length) {
      b.insertAdjacentHTML('beforeend',
        `<div class="cv2-warn">${esc((ana && ana.warning) || T('no_out'))}</div>`);
      setFooter([{ cls: 'btn-quiet', label: T('back'), on: showEvaluation }]);
      return;
    }
    if (ana && ana.warning) {
      b.insertAdjacentHTML('beforeend', `<div class="cv2-warn">${esc(ana.warning)}</div>`);
    }
    const props = {}; (ana.outputs || []).forEach(p => props[p.data_id] = p);
    outputs.forEach(o => {
      const p = props[o.data_id] || {}, nature = o.nature || p.suggested_nature || '';
      const row = document.createElement('div'); row.className = 'cv2-qz'; row.dataset.dataId = o.data_id;
      const opts = `<option value="">${esc(T('to_qualify'))}</option>` +
        Object.keys(labels).map(k => `<option value="${esc(k)}" ${nature === k ? 'selected' : ''}>${esc(labels[k])}</option>`).join('');
      const mv = o.minimum_performance_text || p.suggested_minimum_performance || '';
      // D'où vient la proposition, et à quel point elle est sûre : sans ça on
      // valide une suggestion sans savoir que c'en est une.
      let marque = '';
      if (o.nature && o.qualification_source === 'MANUAL') {
        marque = `<span class="cv2-prop cv2-prop--touche">${esc(T('ia_touched'))}</span>`;
      } else if (p.suggested_nature) {
        const conf = p.confidence === 'low' ? 'low' : (p.confidence === 'medium' ? 'medium' : 'high');
        marque = `<span class="cv2-prop${conf === 'high' ? '' : ' cv2-prop--low'}">${esc(T('ia_conf_' + conf))}</span>`;
      }
      row.innerHTML = `<div style="flex:1">
          <div class="qn">${esc(o.name)}</div>
          ${p.justification ? `<div class="qj">${esc(p.justification)}</div>` : ''}
          ${marque}
          <input class="cv2-minperf ${nature === 'RESULT' ? '' : 'hidden'}" placeholder="${esc(T('min_perf_ph'))}" value="${esc(mv)}">
        </div>
        <select class="cv2-natsel">${opts}</select>`;
      const sel = row.querySelector('.cv2-natsel'), mp = row.querySelector('.cv2-minperf');
      sel.onchange = () => mp.classList.toggle('hidden', sel.value !== 'RESULT');
      b.appendChild(row);
    });
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
    if (!outputs.some(o => o.nature === 'RESULT')) {
      let w = $('#cv2-need-result');
      if (!w) {
        w = document.createElement('div'); w.id = 'cv2-need-result'; w.className = 'cv2-warn';
        const panel = $('#cv2-drawer-body .cv2-bloc'); (panel || $('#cv2-drawer-body')).prepend(w);
      }
      w.textContent = T('need_result'); w.scrollIntoView({ block: 'nearest' });
      return;
    }
    showBusy(T('configuring'));
    const save = await api(`/qualify/save/${aid}`, { method: 'POST', body: JSON.stringify({ outputs }) });
    if (save.__error) { return showQualify(); }
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

  // ══ Diagnostic de l'écart (CDC 6.5-6.9) ════════════════════════════
  async function showDiagnostic() {
    showBusy();
    setFooter([]);
    const st = state.lastState
      || await api(`/mastery/activity/${state.cible}/${state.activity.activity_id}?role_id=${state.roleId}`);
    const req = st.required_level;
    const gapRes = (st.results || []).filter(r => !estNul(r.demonstrated_level)
      && (r.demonstrated_level < 2 || (!estNul(req) && r.demonstrated_level < req)));
    const fams = await api('/diagnostic/families');
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const b = bloc(1, T('diagnose'), T('cause_q'));
    body.appendChild(b);
    if (!gapRes.length) {
      const p = document.createElement('div'); p.className = 'cv2-ok'; p.textContent = T('no_gap');
      b.appendChild(p);
    }
    for (const r of gapRes) b.appendChild(await diagBlock(r, (fams && fams.families) || []));
    setFooter([{ cls: 'btn-quiet', label: T('back'), on: showEvaluation }]);
  }

  async function diagBlock(result, families) {
    const st = await api(`/diagnostic/${state.cible}/${state.activity.activity_id}/${result.data_id}?role_id=${state.roleId}`);
    const wrap = document.createElement('div'); wrap.className = 'cv2-diagres'; wrap.dataset.dataId = result.data_id;
    const selected = new Set(st.families || []);
    wrap.innerHTML = `
      <div class="dtitle"><span>${esc(st.result.name)}</span>
        ${chip(result.demonstrated_level < 2 ? 'red' : 'orange', st.status.label)}</div>
      <div class="cv2-diagsub">${esc(st.demonstrated_label)} (${esc(T('dem'))}) · ${esc(st.required_label)} (${esc(T('req'))})</div>
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
          user_id: state.cible, activity_id: state.activity.activity_id,
          data_id: +wrap.dataset.dataId, families: [...selected] }),
      });
    }
    if (selected.has(st.individual_family)) {
      capsBox.classList.remove('hidden');
      capsBox.innerHTML = `<div class="cv2-capstitle">${esc(T('linked_caps'))}</div>` +
        (st.capabilities.length ? st.capabilities.map(c =>
          `<div class="cv2-cap"><div><span class="ct">${esc(c.type_label)}</span><div>${esc(c.label || '—')}</div></div>
           <div class="lvls">${estNul(c.demonstrated_level) ? T('none') : c.demonstrated_level}
             / ${estNul(c.required_level) ? T('none') : c.required_level}</div></div>`).join('')
          : `<div class="cv2-emptydom">${esc(T('none'))}</div>`);
      // Le plan complet vit dans sa propre fenêtre : ici on y mène.
      const btn = document.createElement('button');
      btn.className = 'btn btn-primary btn-sm'; btn.style.marginTop = '10px'; btn.textContent = T('plan_open');
      btn.onclick = () => { closeDrawer(); ouvrirPlan(); };
      capsBox.appendChild(btn);
      planBox.innerHTML = '';
    } else { capsBox.classList.add('hidden'); planBox.innerHTML = ''; }
  }

  // ══════════════════════════════════════════════════════════════════
  //  LE PLAN DE FORMATION
  //  Le besoin (les actions et leurs heures) d'un côté, la capacité (heures
  //  par semaine × durée) de l'autre. Le verdict est ARITHMÉTIQUE et local :
  //  les curseurs ne rappellent jamais le serveur, sinon on n'oserait pas les
  //  faire glisser.
  // ══════════════════════════════════════════════════════════════════
  const BORNES = { heures_semaine: [1, 20], semaines: [1, 52] };

  function bindPlan() {
    $('#cv2-plan-close').onclick = fermerPlan;
  }
  function fermerPlan() {
    $('#cv2-plan-win').classList.remove('open');
    if (!$('#cv2-drawer').classList.contains('open')) $('#cv2-overlay').classList.remove('open');
  }

  async function ouvrirPlan() {
    $('#cv2-plan-sub').textContent = `${state.cibleNom} · ${state.roleName}`;
    $('#cv2-plan-win').classList.add('open'); $('#cv2-overlay').classList.add('open');
    showBusy(null, '#cv2-plan-body');
    setFooter([], '#cv2-plan-footer');
    const d = await api(`/plan/${state.cible}/${state.roleId}`);
    if (d.__error) { fermerPlan(); return; }
    state.plan = {
      parametres: Object.assign({}, d.parametres),
      actions: (d.actions || []).map(a => Object.assign({}, a)),
      activites: d.activites || [], source: d.source, types: d.types || {},
    };
    renderPlan();
  }

  function renderPlan() {
    const p = state.plan;
    const body = $('#cv2-plan-body');
    if (!p.activites.length) {
      body.innerHTML = `<div class="cv2-plan-vide"><div class="cv2-ia-t">${esc(T('plan_none_t'))}</div>
        <div style="margin-top:6px">${esc(T('plan_none_d'))}</div></div>`;
      setFooter([], '#cv2-plan-footer');
      return;
    }
    if (!p.actions.length) {
      body.innerHTML = `<div class="cv2-plan-vide">
        <div class="cv2-ia-t">${esc(T('plan_empty_t'))}</div>
        <div style="margin-top:6px;max-width:460px;margin-left:auto;margin-right:auto">${esc(T('plan_empty_d'))}</div>
        <div style="margin-top:8px;font-size:12px;color:var(--faint)">
          ${p.activites.length} ${esc(T('plan_gap_intro'))}</div></div>`;
      setFooter([{ cls: 'btn-primary', label: T('plan_propose'), on: proposerPlan, id: 'cv2-plan-prop' }],
                '#cv2-plan-footer');
      return;
    }

    body.innerHTML = `<div class="cv2-plan-grille">
        <div>
          <div class="cv2-plan-h">${esc(T('plan_need'))}<span class="tot" id="cv2-tot"></span></div>
          ${p.source === 'AI'
            ? `<div class="cv2-prop" style="margin:0 0 9px">${esc(T('plan_source_ai'))}</div>`
            : `<div class="cv2-prop cv2-prop--touche" style="margin:0 0 9px">${esc(T('plan_source_local'))}</div>`}
          <div id="cv2-actions"></div>
        </div>
        <div>
          <div class="cv2-plan-h">${esc(T('plan_capacity'))}</div>
          <div class="cv2-reglages">
            ${curseur('heures_semaine', T('plan_hours_week'), T('plan_h'))}
            ${curseur('semaines', T('plan_weeks'), T('plan_week_unit'))}
            <div class="cv2-verdict">
              <div class="cv2-barre" id="cv2-barre"><i></i></div>
              <div class="cv2-chiffres">
                <span>${esc(T('plan_need_total'))} <b id="cv2-besoin">—</b></span>
                <span>${esc(T('plan_cap_total'))} <b id="cv2-capacite">—</b></span>
              </div>
              <div class="cv2-dit" id="cv2-dit"></div>
              <button type="button" class="cv2-juste" id="cv2-juste"></button>
              <div class="cv2-semaines" id="cv2-semaines"></div>
              <div class="cv2-echlbl">${esc(T('plan_sched'))}</div>
            </div>
          </div>
        </div>
      </div>`;

    renderActions();
    ['heures_semaine', 'semaines'].forEach(cle => {
      const inp = body.querySelector(`[data-curseur="${cle}"]`);
      inp.addEventListener('input', () => {
        p.parametres[cle] = +inp.value;
        majCurseur(inp);
        recalculer();
      });
      majCurseur(inp);
    });
    $('#cv2-juste').onclick = () => {
      const { semainesNecessaires } = calcul();
      const inp = body.querySelector('[data-curseur="semaines"]');
      inp.value = p.parametres.semaines = Math.min(BORNES.semaines[1], semainesNecessaires);
      majCurseur(inp); recalculer();
    };
    recalculer();
    setFooter([
      { cls: 'btn-quiet', label: T('plan_repropose'), on: proposerPlan, id: 'cv2-plan-prop' },
      { cls: 'btn-primary', label: T('plan_save'), on: enregistrerPlan },
    ], '#cv2-plan-footer');
  }

  function curseur(cle, libelle, unite) {
    const v = state.plan.parametres[cle];
    const [min, max] = BORNES[cle];
    return `<div class="cv2-curseur">
        <div class="cl">${esc(libelle)}<span class="cv"><span data-val="${cle}">${v}</span> ${esc(unite)}</span></div>
        <input type="range" min="${min}" max="${max}" value="${v}" data-curseur="${cle}">
      </div>`;
  }
  // La piste colorée d'un input[type=range] ne se remplit pas toute seule sous
  // WebKit : on lui donne la proportion à peindre.
  function majCurseur(inp) {
    const min = +inp.min, max = +inp.max, v = +inp.value;
    inp.style.setProperty('--p', ((v - min) / (max - min) * 100) + '%');
    const lbl = inp.closest('.cv2-curseur').querySelector('[data-val]');
    if (lbl) lbl.textContent = v;
  }

  function renderActions() {
    const box = $('#cv2-actions'); box.innerHTML = '';
    state.plan.actions.forEach((a, i) => {
      const el = document.createElement('div');
      el.className = `cv2-action cv2-action--${esc(a.type || 'FORMATION')}`;
      el.style.animationDelay = (i * 35) + 'ms';
      const nomAct = (state.plan.activites.find(x => x.activity_id === a.activity_id) || {}).activity_name;
      el.innerHTML = `<div class="ac-corps">
          <div class="ac-t">${esc(a.titre)}</div>
          <div class="ac-m">
            <span class="cv2-typetag cv2-typetag--${esc(a.type || 'FORMATION')}">${esc(state.plan.types[a.type] || a.type || '')}</span>
            <span class="cv2-heures"><input type="number" min="1" max="200" value="${+a.heures || 1}"> ${esc(T('plan_h'))}</span>
            ${nomAct ? `<span style="font-size:11.5px;color:var(--faint);font-weight:600">${esc(nomAct)}</span>` : ''}
          </div>
          ${a.objectif ? `<div class="ac-o"><b>${esc(T('plan_target'))} :</b> ${esc(a.objectif)}</div>` : ''}
          ${a.critere ? `<div class="ac-c"><b>${esc(T('plan_crit'))}</b> ${esc(a.critere)}</div>` : ''}
        </div>
        <button type="button" class="ac-x" title="${esc(T('plan_del'))}">&times;</button>`;
      el.querySelector('input').addEventListener('input', e => {
        a.heures = Math.max(1, Math.min(200, +e.target.value || 1));
        recalculer();
      });
      el.querySelector('.ac-x').onclick = () => {
        state.plan.actions.splice(i, 1); renderActions(); recalculer();
      };
      box.appendChild(el);
    });
  }

  // Le calcul : besoin, capacité, et ce qu'il faudrait pour que ça tienne.
  function calcul() {
    const p = state.plan;
    const besoin = p.actions.reduce((s, a) => s + (+a.heures || 0), 0);
    const hs = Math.max(1, +p.parametres.heures_semaine || 1);
    const sem = Math.max(1, +p.parametres.semaines || 1);
    const capacite = hs * sem;
    return {
      besoin, capacite, hs, sem,
      manque: Math.max(0, besoin - capacite),
      marge: Math.max(0, capacite - besoin),
      semainesNecessaires: Math.ceil(besoin / hs),
      heuresNecessaires: Math.ceil(besoin / sem),
    };
  }

  function recalculer() {
    const c = calcul();
    $('#cv2-tot').textContent = `${c.besoin} ${T('plan_h')}`;
    $('#cv2-besoin').textContent = `${c.besoin} ${T('plan_h')}`;
    $('#cv2-capacite').textContent = `${c.capacite} ${T('plan_h')}`;

    const barre = $('#cv2-barre');
    const part = c.capacite ? Math.min(100, c.besoin / c.capacite * 100) : 100;
    barre.querySelector('i').style.width = part + '%';
    const etat = c.manque > 0 ? 'trop' : (part > 92 ? 'tendu' : 'ok');
    barre.className = 'cv2-barre' + (etat === 'ok' ? '' : ' ' + etat);

    const dit = $('#cv2-dit');
    dit.className = 'cv2-dit cv2-dit--' + etat;
    dit.textContent = etat === 'trop'
      ? Tv('plan_trop', { x: c.manque, s: c.semainesNecessaires, h: c.heuresNecessaires })
      : (etat === 'tendu' ? T('plan_tendu') : Tv('plan_ok', { x: c.marge }));

    const juste = $('#cv2-juste');
    juste.textContent = Tv('plan_juste', { s: c.semainesNecessaires });
    juste.classList.toggle('hidden', c.semainesNecessaires === c.sem);

    renderSemaines(c);
  }

  // L'échéancier : on remplit les semaines l'une après l'autre, à hauteur de ce
  // qu'on a dit pouvoir y consacrer. Ce qui dépasse se voit en rouge.
  function renderSemaines(c) {
    const box = $('#cv2-semaines'); box.innerHTML = '';
    const total = Math.max(c.sem, Math.min(BORNES.semaines[1], c.semainesNecessaires));
    let reste = c.besoin;
    for (let i = 0; i < total; i++) {
      const pris = Math.min(c.hs, reste);
      reste -= pris;
      const el = document.createElement('div');
      el.className = 'cv2-semaine' + (i >= c.sem && pris > 0 ? ' deborde' : '');
      el.title = `S${i + 1} · ${pris} ${T('plan_h')}`;
      el.innerHTML = `<i style="height:${c.hs ? (pris / c.hs * 100) : 0}%"></i>`;
      box.appendChild(el);
    }
  }

  async function proposerPlan() {
    const btn = $('#cv2-plan-prop');
    if (btn) { btn.disabled = true; btn.textContent = T('gen'); }
    const r = await api('/plan/proposer', {
      method: 'POST',
      body: JSON.stringify({ user_id: state.cible, role_id: state.roleId,
                             parametres: state.plan.parametres }),
    });
    if (r.__error) { if (btn) { btn.disabled = false; btn.textContent = T('plan_propose'); } return; }
    state.plan.actions = r.actions || [];
    state.plan.activites = r.activites || state.plan.activites;
    state.plan.source = r.source === 'AI' ? 'AI' : 'LOCAL';
    renderPlan();
  }

  async function enregistrerPlan() {
    const r = await api('/plan/enregistrer', {
      method: 'POST',
      body: JSON.stringify({
        user_id: state.cible, role_id: state.roleId,
        parametres: state.plan.parametres, actions: state.plan.actions,
        source: state.plan.source }),
    });
    if (!r.__error) toast(T('plan_saved'));
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
