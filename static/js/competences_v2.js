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
      no_activities: 'Aucune activité pour ce rôle.',
      no_caps: "Aucune capacité n'est reliée à ce résultat.",
      cap_requis: 'Requis', cap_demontre: 'Démontré', cap_non_mesure: 'non mesuré', no_roles: "Ce collaborateur n'a aucun rôle.",
      none: '—', back: '← Évaluation', back_synthese: "Vue d'ensemble", gen_plan: 'Générer le plan',
      cause_q: "Quelle est la cause de l'écart ?", linked_caps: 'Capacités reliées à ce résultat',
      no_gap: 'Aucun résultat en écart : le niveau requis est tenu.', dem: 'démontré', req: 'requis',
      gen: 'Génération…',
      req_set: 'Niveau requis mis à jour', not_set: 'Non défini',
      setup_btn: 'Analyser les sorties avec l’IA', setup_btn_off: 'Qualifier les sorties à la main',
      configure_short: 'Configurer',
      conf_title: "Configurer l'activité",
      // Configurer une activité : UNE question, pas un cours de méthode.
      conf_q: 'Sur quoi jugerez-vous cette activité ?',
      conf_q_d: 'Cochez ce qu’elle doit produire, puis dites à quoi on voit que c’est réussi : c’est le repère de l’évaluation.',
      conf_list: 'Ce que l’activité produit', conf_list_d: 'les flèches qui en partent sur la carte',
      conf_vers: 'vers « [[x]] »', conf_fleche: 'Flèche vers « [[x]] »',
      conf_std: 'Réussi quand…', conf_std_lu: 'Réussi quand :', conf_std_ph: 'ex. : validé par le client sans reprise',
      conf_ia_on: 'L’IA a pré-coché ce qui lui semble juste. Vérifiez avant d’enregistrer.',
      conf_ia_off: 'Pas d’IA sur cette instance : cochez vous-même.',
      conf_ia_tag: 'IA', conf_ia_check: 'à vérifier',
      conf_n_0: 'Cochez au moins un élément', conf_n_1: '1 élément retenu', conf_n_n: '[[n]] éléments retenus',
      conf_trop: 'Plus de trois : l’activité en regroupe peut-être plusieurs.',
      conf_save: 'Enregistrer', conf_cancel: 'Annuler',
      conf_busy_open: 'L’IA lit l’activité…', conf_busy_save: 'Enregistrement…',
      conf_empty: 'Aucune flèche ne part de cette activité sur la carte : elle ne produit rien sur quoi la juger. Ajoutez une flèche sortante dans la cartographie, puis revenez ici.',
      conf_done_comp: 'Compétence', conf_done_on: 'Elle sera évaluée sur',
      conf_go: "Configurer cette activité",
      conf_close: 'Fermer', conf_done_go: 'Évaluer maintenant',
      rien_a_evaluer: "Cette activité n'est pas encore configurée : on ne sait pas encore sur quoi la juger. Configurez-la d'abord — une fois pour l'activité, pas pour chaque collaborateur.",
      conf_done_t: 'Activité configurée',
      evidence_ph: 'Preuve / commentaire (facultatif)', add_evidence: '+ Ajouter une preuve',
      diagnose: "Diagnostiquer l'écart",
      loading: 'Chargement…',
      configured_go_eval: 'Sorties qualifiées ✓ — évaluez maintenant le niveau du collaborateur pour chaque résultat, puis enregistrez.',
      req_failed: 'Action impossible (erreur réseau ou serveur).',
      forbidden: "Vous n'avez pas le droit de noter ce collaborateur.",
      pick_level: 'À évaluer', roles_label: 'Rôles du collaborateur',
      self_assess: "S'auto-évaluer",
      pas_configuree: "Cette activité n'est pas encore configurée : son développeur de compétences doit d'abord dire sur quoi la juger.",
      b_held: 'Niveau tenu', b_gap: 'En écart', b_todo: 'À évaluer', b_setup: 'À configurer',
      filter_off: 'Tout afficher', no_match: 'Aucune activité dans cette catégorie.',
      m_result_one: 'résultat', m_result_many: 'résultats', m_partial: 'sur',
      m_eval_one: 'évalué', m_eval_many: 'évalués',
      m_last: 'évalué le', m_never: 'jamais évaluée', m_toqualify: 'pas encore configurée',
      target_short: 'requis',
      // Synthèse
      r_open: 'Ouvrir', r_activity_one: 'activité', r_activity_many: 'activités', r_level: 'Niveau du rôle',
      p_title: 'Profil de compétences', p_role_one: 'rôle', p_role_many: 'rôles',
      p_coverage: 'du requis tenu', p_required: 'Requis', p_demonstrated: 'Démontré',
      p_by_role: 'Par rôle',
      p_detail: 'Détail du rôle', p_back_radar: 'Revenir au profil',
      p_bars_hint: 'Cliquez un point du graphe pour ouvrir le détail d\u2019un rôle.',
      p_bars_one: 'Ce rôle ne porte qu\u2019une activité : le graphe la dit déjà.',
      p_not_assessed: 'non évalué',
      p_on_1: '[[a]] activité évaluée sur [[b]]', p_on_n: '[[a]] activités évaluées sur [[b]]',
      p_capped: 'Les [[n]] activités les plus en écart sont représentées.',
      p_axes_0: 'aucune activité sur le graphe', p_axes_1: '1 activité sur le graphe',
      p_axes_n: '[[n]] activités sur le graphe',
      p_role_partiel: 'Niveau non calculable',
      p_too_few: "Trop peu d'activités évaluées pour tracer un profil.",
      r_none: 'Aucune activité rattachée à ce rôle.',
      // Les deux notes
      n_official: 'Niveau validé', n_official_tag: 'fait foi', n_self: 'Auto-évaluation', n_you: 'vous',
      n_self_mine: 'Votre auto-évaluation', n_by_dev: 'Niveau validé par votre développeur',
      n_none_yet: 'Pas encore validé', n_self_none: 'Pas encore renseignée',
      acc_ok: 'Même lecture', acc_haut: 'Se situe au-dessus', acc_bas: 'Se situe en dessous',
      acc_haut_mine: 'Vous vous situez au-dessus', acc_bas_mine: 'Vous vous situez en dessous',
      // Blocs
      bloc_cible: 'Le niveau attendu', bloc_cible_d: 'Ce que le rôle exige sur cette activité. Cliquez un palier pour le fixer.',
      bloc_eval: "L'évaluation", bloc_tech: 'La technicité',
      // IA
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
      plan_gap_1: 'activité sous le niveau requis', plan_gap_intro: 'activités sous le niveau requis',
      plan_del: 'Retirer cette action',
      plan_target: 'Objectif', plan_deliv: 'Livrable', plan_crit: 'Réussi quand',
      plan_other: 'Autres actions',
      plan_steps_1: '1 étape', plan_steps_n: '[[n]] étapes',
      plan_week_1: 'Semaine [[a]]', plan_week_n: 'Semaines [[a]] → [[b]]',
      plan_week_over: 'dépasse la durée visée',
      plan_week_step_1: 'étape [[l]]', plan_week_step_n: 'étapes [[l]]', plan_wk: 'S',
      plan_load: 'Charge en heures', plan_less: 'Moins d’heures', plan_more: 'Plus d’heures',
      plan_remove: 'Retirer', plan_mix: 'Répartition des heures par nature d’action',
      plan_gap_from_to: 'Niveau actuel → niveau visé',
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
      competence: 'Main competency', save_eval: 'Save evaluation',
      save_self: 'Save my self-assessment',
      evaluate: 'Evaluate', consult: 'View', not_assessed: 'Not assessed', erase: 'Clear',
      std: 'Minimum standard', saved: 'Evaluation saved',
      no_activities: 'No activity for this role.',
      no_caps: 'No capability is linked to this result.',
      cap_requis: 'Required', cap_demontre: 'Demonstrated', cap_non_mesure: 'not measured', no_roles: 'This team member has no role.',
      none: '—', back: '← Evaluation', back_synthese: 'Overview', gen_plan: 'Generate plan',
      cause_q: 'What is the cause of the gap?', linked_caps: 'Capabilities linked to this result',
      no_gap: 'No result below the required level.', dem: 'demonstrated', req: 'required',
      gen: 'Generating…',
      req_set: 'Required level updated', not_set: 'Not set',
      setup_btn: 'Analyse outputs with AI', setup_btn_off: 'Qualify outputs manually',
      configure_short: 'Configure',
      conf_title: 'Configure the activity',
      conf_q: 'What will you judge this activity on?',
      conf_q_d: 'Tick what it must produce, then say how you can tell it is done well: that is the benchmark for assessment.',
      conf_list: 'What the activity produces', conf_list_d: 'the arrows leaving it on the map',
      conf_vers: 'to “[[x]]”', conf_fleche: 'Arrow to “[[x]]”',
      conf_std: 'Done well when…', conf_std_lu: 'Done well when:', conf_std_ph: 'e.g. approved by the client with no rework',
      conf_ia_on: 'The AI has pre-ticked what it thinks fits. Check before saving.',
      conf_ia_off: 'No AI on this instance: tick them yourself.',
      conf_ia_tag: 'AI', conf_ia_check: 'check this',
      conf_n_0: 'Tick at least one item', conf_n_1: '1 item selected', conf_n_n: '[[n]] items selected',
      conf_trop: 'More than three: the activity may bundle several.',
      conf_save: 'Save', conf_cancel: 'Cancel',
      conf_busy_open: 'The AI is reading the activity…', conf_busy_save: 'Saving…',
      conf_empty: 'No arrow leaves this activity on the map: it produces nothing to judge it on. Add an outgoing arrow in the map, then come back here.',
      conf_done_comp: 'Competency', conf_done_on: 'It will be assessed on',
      conf_go: 'Configure this activity',
      conf_close: 'Close', conf_done_go: 'Assess now',
      rien_a_evaluer: 'This activity is not configured yet: nothing says what to judge it on. Configure it first — once for the activity, not for each team member.',
      conf_done_t: 'Activity configured',
      evidence_ph: 'Evidence / comment (optional)', add_evidence: '+ Add evidence',
      diagnose: 'Diagnose the gap',
      loading: 'Loading…',
      configured_go_eval: 'Outputs qualified ✓ — now set the team member’s level for each result, then save.',
      req_failed: 'Action failed (network or server error).',
      forbidden: 'You are not allowed to assess this team member.',
      pick_level: 'To assess', roles_label: "Team member's roles",
      self_assess: 'Self-assess',
      pas_configuree: 'This activity is not configured yet: its competency developer must first say what to judge it on.',
      b_held: 'Level met', b_gap: 'Below target', b_todo: 'To assess', b_setup: 'To configure',
      filter_off: 'Show all', no_match: 'No activity in this category.',
      m_result_one: 'result', m_result_many: 'results', m_partial: 'of',
      m_eval_one: 'assessed', m_eval_many: 'assessed',
      m_last: 'assessed on', m_never: 'never assessed', m_toqualify: 'not configured yet',
      target_short: 'required',
      r_open: 'Open', r_activity_one: 'activity', r_activity_many: 'activities', r_level: 'Role level',
      p_title: 'Competency profile', p_role_one: 'role', p_role_many: 'roles',
      p_coverage: 'of the requirement met', p_required: 'Required', p_demonstrated: 'Demonstrated',
      p_by_role: 'By role',
      p_detail: 'Role detail', p_back_radar: 'Back to the profile',
      p_bars_hint: 'Click a point on the chart to open a role\u2019s detail.',
      p_bars_one: 'This role holds a single activity: the chart already shows it.',
      p_not_assessed: 'not assessed',
      p_on_1: '[[a]] of [[b]] activities assessed', p_on_n: '[[a]] of [[b]] activities assessed',
      p_capped: 'Showing the [[n]] activities with the widest gap.',
      p_axes_0: 'no activity on the chart', p_axes_1: '1 activity on the chart',
      p_axes_n: '[[n]] activities on the chart',
      p_role_partiel: 'Level not computable',
      p_too_few: 'Too few assessed activities to draw a profile.',
      r_none: 'No activity attached to this role.',
      n_official: 'Validated level', n_official_tag: 'official', n_self: 'Self-assessment', n_you: 'you',
      n_self_mine: 'Your self-assessment', n_by_dev: 'Level validated by your developer',
      n_none_yet: 'Not validated yet', n_self_none: 'Not filled in yet',
      acc_ok: 'Same reading', acc_haut: 'Rates themselves higher', acc_bas: 'Rates themselves lower',
      acc_haut_mine: 'You rate yourself higher', acc_bas_mine: 'You rate yourself lower',
      bloc_cible: 'The expected level', bloc_cible_d: 'What the role requires on this activity. Click a step to set it.',
      bloc_eval: 'The assessment', bloc_tech: 'Technicity',
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
      plan_gap_1: 'activity below the required level', plan_gap_intro: 'activities below the required level',
      plan_del: 'Remove this action',
      plan_target: 'Objective', plan_deliv: 'Deliverable', plan_crit: 'Done when',
      plan_other: 'Other actions',
      plan_steps_1: '1 step', plan_steps_n: '[[n]] steps',
      plan_week_1: 'Week [[a]]', plan_week_n: 'Weeks [[a]] → [[b]]',
      plan_week_over: 'runs past the target duration',
      plan_week_step_1: 'step [[l]]', plan_week_step_n: 'steps [[l]]', plan_wk: 'W',
      plan_load: 'Workload in hours', plan_less: 'Fewer hours', plan_more: 'More hours',
      plan_remove: 'Remove', plan_mix: 'Hours by kind of action',
      plan_gap_from_to: 'Current level → target level',
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
  };
  Object.keys(COMMUN).forEach(k => { I18N.fr[k] = COMMUN[k].fr; I18N.en[k] = COMMUN[k].en; });

  const T = k => (I18N[LANG][k] || k);
  const Tv = (k, vars) => Object.keys(vars || {}).reduce(
    (s, v) => s.split('[[' + v + ']]').join(vars[v]), T(k));
  // « Libellé : valeur » en français, « Label: value » en anglais : l'espace
  // avant les deux-points est une règle de typographie FRANÇAISE.
  const DP = LANG === 'fr' ? ' : ' : ': ';

  const state = {
    moi: null, estDev: false,
    cible: null, cibleNom: '',
    ecran: null, roleId: null, roleName: null,
    scale: {}, notAssessed: '', domScale: {},
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
    if (await ouvrirDemande(gens)) return;
    // Un seul dossier à regarder : on l'ouvre, personne n'a envie de cliquer
    // sur son propre nom pour entrer chez soi.
    if (gens.length === 1) choisirCollab(gens[0], $('#cv2-collab').firstElementChild);
  }

  // `?personne=<id>&role=<id>` — une case du tableau global de la page RH.
  // Arriver ici pour y chercher soi-même la personne puis son rôle, c'est
  // refaire le chemin qu'on vient de désigner d'un clic. L'adresse est
  // nettoyée : revenir en arrière ne doit pas rouvrir le même dossier.
  async function ouvrirDemande(gens) {
    let q;
    try { q = new URLSearchParams(window.location.search); } catch (_) { return false; }
    const pid = parseInt(q.get('personne'), 10);
    if (!pid) return false;
    try { window.history.replaceState({}, '', window.location.pathname); } catch (_) { /* rien */ }
    const i = gens.findIndex(u => u.id === pid);
    if (i < 0) return false;
    await choisirCollab(gens[i], $('#cv2-collab').children[i]);
    const rid = parseInt(q.get('role'), 10);
    const r = rid && ((state.synthese && state.synthese.roles) || []).find(x => x.role_id === rid);
    if (r) await ouvrirRole(r);
    return true;
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
    renderProfil(d);
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
        ${r.n_gap && jeSuisLeDev() ? `<button type="button" class="btn btn-ghost btn-sm" data-plan="1">${esc(T('plan_open'))}</button>` : ''}
        <button type="button" class="btn btn-primary btn-sm" data-ouvrir="1">${esc(T('r_open'))}</button>
      </div>`;
    // ⚠️ Toute la carte ouvre le rôle : viser le bouton « Ouvrir » alors que la
    // carte entière a l'air cliquable (elle se soulève au survol) est une
    // promesse que le survol fait et que le clic ne tenait pas.
    el.onclick = () => ouvrirRole(r);
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.onkeydown = e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ouvrirRole(r); }
    };
    const bp = el.querySelector('[data-plan]');
    if (bp) {
      // Le plan est une AUTRE destination : son clic ne doit pas remonter à la
      // carte, sinon on ouvre le rôle derrière la fenêtre du plan.
      bp.onclick = e => {
        e.stopPropagation();
        state.roleId = r.role_id; state.roleName = r.role_name; ouvrirPlan();
      };
    }
    return el;
  }

  // Une jauge + son libellé + son écart, réutilisée par la carte de rôle et la
  // ligne d'activité : la même information ne peut pas se lire de deux façons.
  function blocJauge(niveau, requis, couleur, ecart, libelle) {
    const req = estNul(requis) ? null : requis;
    const inconnu = estNul(niveau);
    const titre = [
      `${T('c_demonstrated')}${DP}${inconnu ? state.notAssessed : (libelle || levelName(niveau))}`,
      req === null ? '' : `${T('target_short')}${DP}${req} · ${levelName(req)}`,
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
        <div class="cv2-nom">${esc(a.activity_name)}
          ${a.competence ? `<button type="button" class="cv2-i" data-info="1"
            aria-label="${esc(T('competence'))}"><i class="fa-solid fa-info"></i></button>` : ''}
        </div>
        <div class="cv2-meta">${metaActivite(a)}</div>
      </div>
      <div>${blocJauge(a.demonstrated_level, a.required_level, a.color || 'grey', a.gap, a.demonstrated_label)}</div>
      <div class="cv2-cell-tech">${celluleTech(a.technicity)}</div>
      <div class="cv2-cell-act">
        <button class="btn btn-sm ${cat === 'setup' && jeSuisLeDev() ? 'btn-todo' : 'btn-primary'}">
          ${esc(libelleBtn)}</button>
      </div>`;
    // ⚠️ Deux boutons, deux fenêtres. « Configurer » parle de l'ACTIVITÉ (que
    // produit-elle ?), « Évaluer » parle d'une PERSONNE. Les mélanger faisait
    // passer l'IA de la configuration pour une IA de notation.
    el.querySelector('.cv2-cell-act button').onclick = () =>
      (cat === 'setup' && jeSuisLeDev()) ? ouvrirConfiguration(a) : openDrawer(a);
    const info = el.querySelector('[data-info]');
    if (info) brancherInfo(info, T('competence'), a.competence);
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


  // ══════════════════════════════════════════════════════════════════
  //  LE PROFIL — ce que la vue d'ensemble apporte de plus que des cartes
  //  Un radar : un axe par activité, deux formes superposées — ce que les
  //  rôles EXIGENT et ce que la personne TIENT. On lit d'un coup où la
  //  seconde rentre dans la première et où elle en sort.
  //
  //  ⚠️ Dessiné à la main en SVG. Aucune bibliothèque de graphes n'est chargée
  //  dans l'application, et en ajouter une pour dix polygones se paierait à
  //  chaque chargement de page.
  // ══════════════════════════════════════════════════════════════════
  const RADAR_MAX_AXES = 12;

  function renderProfil(d) {
    const box = $('#cv2-profil');
    // ⚠️ On ne trace QUE ce qui est mesuré. Poser une activité non évaluée à 0
    // effondrait le polygone vers le centre : le graphe disait « rien de
    // démontré » là où la vérité est « pas encore regardé » — la distinction
    // que tout le module tient par ailleurs (NULL ≠ 0).
    const avecCible = (d.profil || []).filter(a => !estNul(a.required_level) && a.required_level > 0);
    const axes = avecCible.filter(a => !estNul(a.demonstrated_level));
    const horsGraphe = avecCible.length - axes.length;
    if (!d.roles.length) { box.classList.add('hidden'); return; }
    box.classList.remove('hidden');

    const trop = axes.length > RADAR_MAX_AXES;
    // Au-delà d'une douzaine d'axes le radar devient illisible : on garde les
    // plus parlantes — celles où l'écart est le plus grand. Le serveur les a
    // déjà triées par écart croissant.
    const vus = trop ? axes.slice(0, RADAR_MAX_AXES) : axes;

    box.innerHTML = `
      <div class="cv2-profil-tete">
        <div>
          <div class="cv2-profil-h">${esc(T('p_title'))}</div>
        </div>
        <div class="cv2-profil-kpi">
          <div class="cv2-kpi">
            <div class="n">${d.roles.length}</div>
            <div class="k">${esc(d.roles.length === 1 ? T('p_role_one') : T('p_role_many'))}</div>
          </div>
          <div class="cv2-kpi">
            <div class="n">${d.n_activities_uniques}</div>
            <div class="k">${esc(d.n_activities_uniques === 1 ? T('r_activity_one') : T('r_activity_many'))}</div>
          </div>
          <div class="cv2-kpi cv2-kpi--fort">
            <div class="n">${estNul(d.couverture) ? '—' : d.couverture + '<small>%</small>'}</div>
            <div class="k">${esc(T('p_coverage'))}</div>
          </div>
        </div>
      </div>
      <div class="cv2-profil-corps">
        <div class="cv2-radar-zone" data-vue="radar">${vus.length >= 3 ? radarSVG(vus) : ''}
          <div class="cv2-barres-zone"></div>
          <div class="cv2-radar-bulle"></div>
          <div class="cv2-radar-leg">
            <button type="button" class="cv2-leg-b" data-couche="req">
              <i class="cv2-leg cv2-leg--req"></i>${esc(T('p_required'))}</button>
            <button type="button" class="cv2-leg-b" data-couche="dem">
              <i class="cv2-leg cv2-leg--dem"></i>${esc(T('p_demonstrated'))}</button>
          </div>
          ${trop ? `<div class="cv2-radar-note">${esc(Tv('p_capped', { n: RADAR_MAX_AXES }))}</div>` : ''}
          ${vus.length < 3 ? `<div class="cv2-radar-note">${esc(T('p_too_few'))}</div>` : ''}
        </div>
        <div class="cv2-parrole">
          <div class="cv2-parrole-h">${esc(T('p_by_role'))}</div>
          ${d.roles.map(r => barreRole(r)).join('')}
        </div>
      </div>`;

    box.querySelectorAll('.cv2-parrole-l').forEach(b => b.onclick = () => {
      const r = d.roles.find(x => String(x.role_id) === b.dataset.role);
      if (r) ouvrirRole(r);
    });
    // ⚠️ Un point du radar porte UNE activité, mais le radar superpose tout :
    // il ne dit pas où un rôle en est activité par activité. Le clic ouvre donc
    // le détail du rôle auquel ce point appartient — c'est le geste naturel,
    // puisque survoler un rôle allume déjà ses points.
    box.querySelectorAll('.cv2-radar-zone [data-role]').forEach(el => {
      el.classList.add('est-cliquable');
      el.addEventListener('click', ev => {
        ev.stopPropagation();
        const r = (d.roles || []).find(x => String(x.role_id) === el.dataset.role);
        if (r) ouvrirBarres(box, r);
      });
    });
    animerProfil(box, vus, d);
  }

  // ── Le profil, vivant ────────────────────────────────────────────────
  // Trois gestes, tous réversibles et sans clic : survoler une légende met SA
  // couche au premier plan ; survoler un rôle n'éclaire que ses activités ;
  // survoler un axe donne son détail. Un graphe qui ne réagit pas se lit une
  // fois puis devient un décor.
  function animerProfil(box, axes, d) {
    const svg = box.querySelector('.cv2-radar');
    if (!svg) return;

    box.querySelectorAll('[data-couche]').forEach(b => {
      const dessus = () => svg.setAttribute('data-avant', b.dataset.couche);
      const dessous = () => svg.removeAttribute('data-avant');
      b.addEventListener('mouseenter', dessus);
      b.addEventListener('focus', dessus);
      b.addEventListener('mouseleave', dessous);
      b.addEventListener('blur', dessous);
    });

    // Survoler un rôle : SES axes s'allument, les autres s'éteignent, et ses
    // deux niveaux s'affichent. On n'agrandit pas le graphe — un zoom
    // déplacerait les deux polygones, et c'est justement leur superposition
    // qu'on est venu lire.
    const bulleR = box.querySelector('.cv2-radar-bulle');
    box.querySelectorAll('.cv2-parrole-l').forEach(b => {
      const r = (d.roles || []).find(x => String(x.role_id) === b.dataset.role);
      const allume = () => {
        let vus = 0;
        svg.querySelectorAll('[data-role]').forEach(el => {
          const sien = el.dataset.role === b.dataset.role;
          el.classList.toggle('est-eteint', !sien);
          el.classList.toggle('est-vu', sien);
          if (sien && el.classList.contains('cv2-r-pt')) vus += 1;
        });
        if (!r || !bulleR) return;
        // Un rôle dont rien n'est tracé doit le DIRE : sinon on survole et il
        // ne se passe rien, ce qui ressemble à une panne.
        const niveaux = estNul(r.level)
          ? `<span class="vide">${esc(T('p_role_partiel'))}</span>`
          : `<span class="req">${esc(T('p_required'))} ${estNul(r.required_level) ? '—' : r.required_level}</span>
             <span class="dem">${esc(T('p_demonstrated'))} ${r.level}</span>`;
        bulleR.innerHTML = `<div class="t">${esc(r.role_name)}</div>
          <div class="r">${vus ? Tv(vus === 1 ? 'p_axes_1' : 'p_axes_n', { n: vus })
            : esc(T('p_axes_0'))}${estNul(r.couverture) ? '' : ' · ' + r.couverture + ' %'}</div>
          <div class="n">${niveaux}</div>`;
        // Un rôle parle de l'ENSEMBLE du graphe : sa bulle se pose au centre,
        // pas sur un point en particulier.
        poserBulle(bulleR, box, null);
        bulleR.classList.add('est-la');
      };
      const eteint = () => {
        svg.querySelectorAll('.est-eteint, .est-vu').forEach(el =>
          el.classList.remove('est-eteint', 'est-vu'));
        if (bulleR) bulleR.classList.remove('est-la');
      };
      b.addEventListener('mouseenter', allume);
      b.addEventListener('focus', allume);
      b.addEventListener('mouseleave', eteint);
      b.addEventListener('blur', eteint);
    });

    const bulle = box.querySelector('.cv2-radar-bulle');
    svg.querySelectorAll('[data-axe]').forEach(el => {
      el.addEventListener('mouseenter', () => {
        const a = axes[+el.dataset.axe]; if (!a || !bulle) return;
        svg.querySelectorAll('.est-eteint').forEach(x => x.classList.remove('est-eteint'));
        svg.querySelectorAll(`[data-axe="${el.dataset.axe}"]`).forEach(x => x.classList.add('est-vu'));
        bulle.innerHTML = `<div class="t">${esc(a.activity_name)}</div>
          <div class="r">${esc(a.role_name)}</div>
          <div class="n"><span class="req">${esc(T('p_required'))} ${a.required_level}</span>
            <span class="dem">${esc(T('p_demonstrated'))} ${a.demonstrated_level}</span></div>`;
        // ⚠️ Elle se posait TOUJOURS au même endroit : on survolait un point à
        // gauche et l'explication apparaissait en haut au centre, sans rien qui
        // relie l'une à l'autre. Elle suit désormais le point survolé.
        poserBulle(bulle, box, el);
        bulle.classList.add('est-la');
      });
      el.addEventListener('mouseleave', () => {
        svg.querySelectorAll('.est-vu').forEach(x => x.classList.remove('est-vu'));
        if (bulle) bulle.classList.remove('est-la');
      });
    });
  }

  // Une barre par rôle : la part du requis tenue, et sur quelle base elle se lit.
  function barreRole(r) {
    const c = r.couverture;
    const teinte = estNul(c) ? 'grey' : (c >= 100 ? 'green' : (c >= 70 ? 'orange' : 'red'));
    // La base du calcul va SOUS le nom : en suffixe, elle poussait le nom du
    // rôle hors de sa colonne et c'est lui qu'on tronquait.
    const base = r.n_evaluated === r.n_activities ? ''
      : `<span class="sur">${esc(Tv(r.n_evaluated === 1 ? 'p_on_1' : 'p_on_n',
                                   { a: r.n_evaluated, b: r.n_activities }))}</span>`;
    return `<button type="button" class="cv2-parrole-l" data-role="${r.role_id}">
        <span class="nom"><span class="t">${esc(r.role_name)}</span>${base}</span>
        <span class="jauge cv2-jb--${teinte}"><i style="width:${estNul(c) ? 0 : Math.min(100, c)}%"></i></span>
        <span class="pc">${estNul(c) ? '—' : c + ' %'}</span>
      </button>`;
  }

  // Poser la bulle près de l'élément survolé, sans sortir du cadre. Les
  // coordonnées d'un nœud SVG sont dans le repère du VIEWBOX : on passe par
  // `getBoundingClientRect`, qui rend des pixels d'écran, seuls comparables à
  // ceux de la zone.
  function poserBulle(bulle, zone, el) {
    const z = zone.getBoundingClientRect();
    bulle.style.visibility = 'hidden';
    bulle.classList.add('est-la');
    const b = bulle.getBoundingClientRect();
    bulle.classList.remove('est-la');
    bulle.style.visibility = '';

    let x, y;
    if (el) {
      const r = el.getBoundingClientRect();
      x = r.left + r.width / 2 - z.left - b.width / 2;
      y = r.top - z.top - b.height - 10;
      // Trop haut pour tenir au-dessus : on passe dessous le point.
      if (y < 2) y = r.bottom - z.top + 10;
    } else {
      x = z.width / 2 - b.width / 2;
      y = 6;
    }
    bulle.style.left = Math.max(4, Math.min(x, z.width - b.width - 4)) + 'px';
    bulle.style.top = Math.max(2, Math.min(y, z.height - b.height - 2)) + 'px';
  }

  // Le radar. Rayon = niveau 0..4 ; deux polygones, le requis en trait plein
  // clair et le démontré rempli par-dessus.
  // ── Le détail d'un rôle, en barres ─────────────────────────────────
  // Le radar répond « quelle est la FORME du profil » ; il ne répond pas
  // « sur quelle activité ce rôle décroche ». Les barres répondent à ça :
  // une ligne par activité, la cible marquée sur la piste.
  function barresRole(role) {
    const actes = (role.activities || []).slice()
      .sort((a, b) => (a.gap == null ? 99 : a.gap) - (b.gap == null ? 99 : b.gap)
                      || a.activity_name.localeCompare(b.activity_name));
    const lignes = actes.map((a, i) => {
      const dem = estNul(a.demonstrated_level) ? null : a.demonstrated_level;
      const req = estNul(a.required_level) ? null : a.required_level;
      const coul = a.color || 'grey';
      // ⚠️ Une activité non évaluée n'a PAS une barre à zéro : zéro veut dire
      // « non démontré », et tout le module distingue les deux. Elle le dit.
      const piste = dem === null
        ? `<span class="cv2-bar-vide">${esc(T('p_not_assessed'))}</span>`
        : `<i class="cv2-bar-plein cv2-bar--${coul}" style="--w:${(dem / 4) * 100}%"></i>`;
      const cible = req === null ? ''
        : `<i class="cv2-bar-cible" style="--x:${(req / 4) * 100}%" title="${esc(T('p_required'))} ${req}"></i>`;
      return `<div class="cv2-bar-l" style="--i:${i}">
          <span class="cv2-bar-nom" title="${esc(a.activity_name)}">${esc(a.activity_name)}</span>
          <span class="cv2-bar-piste">${piste}${cible}</span>
          <span class="cv2-bar-val">${dem === null ? '—' : dem}<small>/${req === null ? '—' : req}</small></span>
        </div>`;
    }).join('');

    return `<div class="cv2-barres">
        <div class="cv2-barres-tete">
          <button type="button" class="cv2-barres-retour">
            <i class="fa-solid fa-arrow-left"></i> ${esc(T('p_back_radar'))}</button>
          <div class="cv2-barres-t">${esc(role.role_name)}</div>
        </div>
        ${actes.length > 1 ? `<div class="cv2-barres-corps">${lignes}</div>`
          : `<div class="cv2-barres-corps">${lignes}
             <p class="cv2-barres-note">${esc(T('p_bars_one'))}</p></div>`}
      </div>`;
  }

  function ouvrirBarres(box, role) {
    const zone = box.querySelector('.cv2-radar-zone');
    const hote = box.querySelector('.cv2-barres-zone');
    if (!zone || !hote) return;
    box.querySelector('.cv2-radar-bulle')?.classList.remove('est-la');
    hote.innerHTML = barresRole(role);
    // Le changement de vue se fait sur l'attribut : le CSS porte l'animation,
    // et rien ne bouge si l'utilisateur a demandé moins de mouvement.
    zone.dataset.vue = 'barres';
    hote.querySelector('.cv2-barres-retour')?.addEventListener('click', () => {
      zone.dataset.vue = 'radar';
      // On vide APRÈS la transition : retirer le contenu tout de suite ferait
      // disparaître les barres d'un coup au lieu de les laisser s'effacer.
      setTimeout(() => { if (zone.dataset.vue === 'radar') hote.innerHTML = ''; }, 320);
    });
  }

  function radarSVG(axes) {
    const R = 132, CX = 260, CY = 186, MAX = 4;
    const n = axes.length;
    const pt = (i, v) => {
      const a = (Math.PI * 2 * i / n) - Math.PI / 2;
      const d = R * (Math.max(0, Math.min(MAX, v)) / MAX);
      return [CX + Math.cos(a) * d, CY + Math.sin(a) * d];
    };
    const poly = vals => vals.map((v, i) => pt(i, v).map(x => x.toFixed(1)).join(',')).join(' ');

    let toile = '';
    for (let k = 1; k <= MAX; k++) {
      toile += `<polygon class="cv2-r-grid" points="${poly(axes.map(() => k))}"></polygon>`;
    }
    axes.forEach((a, i) => {
      const [x, y] = pt(i, MAX);
      toile += `<line class="cv2-r-axe" x1="${CX}" y1="${CY}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"></line>`;
    });

    // Une activité non évaluée n'a pas de point : la laisser à 0 la ferait
    // passer pour « non démontrée », ce qu'on distingue partout ailleurs.
    const dem = axes.map(a => a.demonstrated_level);
    const req = axes.map(a => a.required_level);
    const points = axes.map((a, i) => {
      const [x, y] = pt(i, a.demonstrated_level);
      const sous = a.demonstrated_level < a.required_level ? ' cv2-r-pt--sous' : '';
      return `<circle class="cv2-r-pt${sous}" data-axe="${i}" data-role="${a.role_id}"
          cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.8"></circle>`;
    }).join('');

    // ⚠️ Les noms d'activite sont longs et se chevauchent des qu'on depasse
    // une poignee d'axes. On coupe court (16 signes) et on rend l'axe SURVOLABLE :
    // le nom entier, son role et ses deux niveaux s'affichent dans une bulle.
    // Un libelle complet grave dans le SVG deborderait quoi qu'on fasse.
    const etiquettes = axes.map((a, i) => {
      const [x, y] = pt(i, MAX + 0.52);
      const ancre = Math.abs(x - CX) < 14 ? 'middle' : (x > CX ? 'start' : 'end');
      const nom = a.activity_name.length > 16 ? a.activity_name.slice(0, 15) + '…' : a.activity_name;
      const [zx, zy] = pt(i, MAX);
      return `<g class="cv2-r-axe-g" data-axe="${i}" data-role="${a.role_id}">
          <line class="cv2-r-zone" x1="${CX}" y1="${CY}" x2="${zx.toFixed(1)}" y2="${zy.toFixed(1)}"></line>
          <text class="cv2-r-lbl" x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="${ancre}">${esc(nom)}</text>
        </g>`;
    }).join('');

    return `<svg class="cv2-radar" viewBox="14 6 492 370" role="img"
                 aria-label="${esc(T('p_title'))}">
        ${toile}
        <polygon class="cv2-r-req" points="${poly(req)}"></polygon>
        <polygon class="cv2-r-dem" points="${poly(dem)}"></polygon>
        ${points}${etiquettes}
      </svg>`;
  }

  // Une explication qui ne tient pas sur une ligne ne doit pas EN PRENDRE une :
  // elle attend derrière un « i », au survol comme au clic (le survol seul
  // n'existe pas sur un écran tactile).
  // ⚠️ La carte est posée sur le BODY, pas sur la ligne : elle survit donc à
  // la disparition de son bouton. Sans ce ménage, elle restait affichée en
  // plein milieu de l'écran suivant. Tout ce qui déplace ou remplace ce qu'il y
  // a dessous la referme : un clic ailleurs, un défilement, un changement de
  // taille de fenêtre.
  function fermerInfos() {
    document.querySelectorAll('.cv2-info').forEach(e => e.remove());
  }
  document.addEventListener('click', fermerInfos);
  window.addEventListener('scroll', fermerInfos, true);
  window.addEventListener('resize', fermerInfos);

  function brancherInfo(bouton, titre, texte) {
    if (!texte) return;
    let carte = null;
    const fermer = () => { if (carte) { carte.remove(); carte = null; } };
    const ouvrir = () => {
      if (carte) return;
      fermerInfos();
      carte = document.createElement('div');
      carte.className = 'cv2-info';
      carte.innerHTML = `<div class="t">${esc(titre)}</div><div class="d">${esc(texte)}</div>`;
      document.body.appendChild(carte);
      // En `position: fixed` sur le body : la liste des activités a son propre
      // défilement, une carte posée dedans serait tronquée.
      const r = bouton.getBoundingClientRect(), b = carte.getBoundingClientRect();
      carte.style.left = Math.max(8, Math.min(r.left, window.innerWidth - b.width - 8)) + 'px';
      const dessus = r.top - b.height - 8;
      carte.style.top = (dessus > 8 ? dessus : r.bottom + 8) + 'px';
    };
    bouton.addEventListener('mouseenter', ouvrir);
    bouton.addEventListener('mouseleave', fermer);
    bouton.addEventListener('focus', ouvrir);
    bouton.addEventListener('blur', fermer);
    bouton.addEventListener('click', e => {
      e.stopPropagation();                 // ne pas ouvrir le rôle derrière
      carte ? fermer() : ouvrir();
    });
  }

  // Une capacité reliée à un résultat : son niveau requis se RÈGLE ici.
  function carteCapacite(c) {
    let paliers = '';
    for (let lv = 1; lv <= 4; lv++) {
      paliers += `<button type="button" class="cv2-capniv${c.required_level === lv ? ' sel' : ''}"
        data-cap="1" data-niv="${lv}" title="${esc(levelName(lv))}">${lv}</button>`;
    }
    const dem = estNul(c.demonstrated_level)
      ? `<span class="nonmes">${esc(T('cap_non_mesure'))}</span>`
      : `<b>${c.demonstrated_level}</b>`;
    return `<div class="cv2-cap" data-lien="${c.link_id}">
        <div class="ci">
          <span class="ct">${esc(c.type_label)}</span>
          <div class="cl">${esc(c.label || '—')}</div>
        </div>
        <div class="cr">
          <div class="cbloc"><span class="ck">${esc(T('cap_requis'))}</span>
            <span class="cniv">${paliers}
              <button type="button" class="cv2-capniv cv2-capniv--off${estNul(c.required_level) ? ' sel' : ''}"
                data-cap="1" data-niv="">${esc(T('not_set'))}</button></span></div>
          <div class="cbloc"><span class="ck">${esc(T('cap_demontre'))}</span>
            <span class="cdem">${dem}</span></div>
        </div>
      </div>`;
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
    const d = $('#cv2-drawer');
    d.dataset.mode = 'eval';
    $('#cv2-drawer-title').textContent = row.activity_name;
    // Le collaborateur et son rôle ne sont pas une légende du titre : ce sont
    // deux informations de même rang. Côte à côte, les deux peuvent grossir.
    $('#cv2-drawer-role').innerHTML =
      `<span class="qui">${esc(state.cibleNom)}</span><span class="ou">${esc(state.roleName)}</span>`;
    d.classList.add('open'); $('#cv2-overlay').classList.add('open');
    $('#cv2-drawer-body').scrollTop = 0;
    showEvaluation();
  }

  // Configurer une activité ne regarde PERSONNE : ni le collaborateur choisi, ni
  // son niveau. La fenêtre ne porte donc pas son nom — c'est le premier signe
  // qu'on a changé de sujet.
  function ouvrirConfiguration(row) {
    state.activity = row;
    const d = $('#cv2-drawer');
    d.dataset.mode = 'config';
    $('#cv2-drawer-title').textContent = T('conf_title');
    $('#cv2-drawer-role').innerHTML = `<span class="qui">${esc(row.activity_name)}</span>`;
    d.classList.add('open'); $('#cv2-overlay').classList.add('open');
    $('#cv2-drawer-body').scrollTop = 0;
    showQualify();
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
      c.innerHTML = `<span class="tag"><i class="fa-solid fa-bullseye"></i>${esc(T('competence'))}</span>`
        + esc(state.activity.competence);
      body.appendChild(c);
    }
    // ── Bloc 1 : le niveau attendu ──────────────────────────────────
    // Il n'y a plus de bandeau récapitulatif au-dessus : il répétait le niveau
    // requis que ce bloc sert justement à régler, et deux affichages du même
    // nombre finissent toujours par diverger.
    const b1 = bloc(1, T('bloc_cible'), null);
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
    const b2 = bloc(2, T('bloc_eval'), null, 'eval', resume);
    body.appendChild(b2);

    if (!aEvaluer) {
      // ⚠️ Plus une trace d'IA ici. Il n'y a rien à évaluer tant que l'activité
      // n'a pas de résultat qualifié : on le dit, et on renvoie vers l'autre
      // fenêtre — celle qui parle de l'activité.
      const w = document.createElement('div'); w.className = 'cv2-warn';
      w.textContent = jeSuisLeDev() ? T('rien_a_evaluer') : T('pas_configuree');
      b2.appendChild(w);
      if (jeSuisLeDev()) {
        const b = document.createElement('button');
        b.className = 'btn btn-primary'; b.textContent = T('conf_go');
        b.onclick = () => ouvrirConfiguration(state.activity);
        b2.appendChild(b);
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
      ${peut ? '' : 'disabled'}>${esc(T('not_set'))}</button>
      <div class="cv2-cible-dit">${req === null ? esc(T('not_set'))
        : `<b>${req}</b> · ${esc(levelName(req))}`}</div></div>`;
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
  // ⚠️ Les deux notes avaient deux POIDS VISUELS différents : la note officielle
  // était une échelle, l'auto-évaluation une ligne de texte minuscule en
  // dessous. On ne savait plus laquelle était laquelle, et l'une avait l'air
  // d'être un commentaire de l'autre. Elles ont désormais le MÊME objet —
  // l'échelle 0→4 — et se distinguent par une identité tenue partout :
  //
  //     niveau validé      bleu (accent de la page) · écusson · « fait foi »
  //     auto-évaluation    violet                   · silhouette
  //
  // Celle qui vous appartient est cliquable ; l'autre est posée, verrouillée.
  // L'ordre ne bouge jamais : la note qui fait foi d'abord, quel que soit le
  // regard — on sait toujours où regarder.
  function echelleNote(o) {
    let paliers = '';
    for (let lv = 0; lv <= 4; lv++) {
      const cls = ['cv2-niv'];
      if (o.niveau === lv) cls.push('sel');
      if (o.requis === lv) cls.push('cible');
      const bulle = levelName(lv) + (o.requis === lv ? ` — ${T('target_short')}` : '');
      paliers += `<button type="button" class="${cls.join(' ')}" data-lv="${lv}"
        ${o.modifiable ? '' : 'disabled'} title="${esc(bulle)}">${lv}</button>`;
    }
    const valeur = estNul(o.niveau)
      ? `<span class="cv2-nt-vide">${esc(o.modifiable ? T('pick_level') : T('n_none_yet'))}</span>`
      : `<b>${o.niveau}</b> · ${esc(levelName(o.niveau))}`;
    return `<div class="cv2-nt cv2-nt--${o.genre}${o.modifiable ? ' is-mienne' : ' is-posee'}"
                 data-note="${o.genre}">
        <div class="cv2-nt-tete">
          <span class="cv2-nt-ico"><i class="fa-solid ${o.genre === 'off' ? 'fa-circle-check' : 'fa-user'}"></i></span>
          <span class="cv2-nt-lbl">${esc(o.titre)}</span>
          ${o.tag ? `<span class="cv2-nt-tag">${esc(o.tag)}</span>` : ''}
          <span class="cv2-nt-val">${valeur}</span>
        </div>
        <div class="cv2-echelle">${paliers}
          ${o.modifiable ? `<button type="button" class="cv2-gomme${estNul(o.niveau) ? ' sel' : ''}" data-lv="">${esc(T('erase'))}</button>` : ''}
        </div>
        ${o.accord || ''}
      </div>`;
  }

  function resultCard(r, requis) {
    const dev = jeSuisLeDev();
    const card = document.createElement('div');
    const maNote = dev ? r.demonstrated_level : r.self_level;
    card.className = 'cv2-res' + (estNul(maNote) ? '' : ' est-note');
    card.dataset.dataId = r.data_id;
    const req = estNul(requis) ? null : requis;
    const preuve = (dev ? r.evidence : r.self_evidence) || '';

    const officielle = echelleNote({
      genre: 'off', titre: T('n_official'), tag: T('n_official_tag'),
      niveau: r.demonstrated_level, requis: req, modifiable: dev,
    });
    const auto = echelleNote({
      genre: 'auto', titre: dev ? T('n_self') : T('n_self_mine'), tag: dev ? '' : T('n_you'),
      niveau: r.self_level, requis: req, modifiable: !dev,
      accord: accordBadge(r.self_level, r.demonstrated_level, dev),
    });

    // ⚠️ Le standard minimal n'est plus ÉCRIT : il tenait deux lignes de petit
    // texte par résultat, et la fenêtre en portait autant que de résultats. Il
    // reste sous le nom, au survol — c'est une référence qu'on consulte, pas
    // une consigne qu'on relit à chaque fois.
    card.innerHTML = `
      <div class="rtete">
        <div class="rname"${r.minimum_performance_text
          ? ` title="${esc(T('std'))}${DP}${esc(r.minimum_performance_text)}"` : ''}>${esc(r.name)}
          ${r.minimum_performance_text ? '<i class="fa-regular fa-circle-question cv2-astuce"></i>' : ''}
        </div>
      </div>
      ${officielle}${auto}
      <button type="button" class="cv2-preuve-btn${preuve ? ' hidden' : ''}">${esc(T('add_evidence'))}</button>
      <textarea class="cv2-ev${preuve ? '' : ' hidden'}" placeholder="${esc(T('evidence_ph'))}">${esc(preuve)}</textarea>`;

    // Seule MA note se clique ; l'autre est posée là pour être lue.
    const mienne = card.querySelector('.cv2-nt.is-mienne');
    mienne.querySelectorAll('[data-lv]').forEach(b => b.onclick = () => {
      mienne.querySelectorAll('[data-lv]').forEach(x => x.classList.remove('sel'));
      b.classList.add('sel');
      card.classList.toggle('est-note', b.dataset.lv !== '');
      majValeur(mienne, card, r, dev);
    });
    const bp = card.querySelector('.cv2-preuve-btn'), ta = card.querySelector('.cv2-ev');
    bp.onclick = () => { bp.classList.add('hidden'); ta.classList.remove('hidden'); ta.focus(); };
    return card;
  }

  // Le niveau choisi s'écrit dans l'en-tête de SA note, et le verdict d'accord
  // se recalcule aussitôt : sinon il resterait celui d'avant le clic.
  function majValeur(bloc, card, r, dev) {
    const sel = bloc.querySelector('[data-lv].sel');
    const brut = sel ? sel.dataset.lv : '';
    const lv = brut === '' ? null : +brut;
    bloc.querySelector('.cv2-nt-val').innerHTML = estNul(lv)
      ? `<span class="cv2-nt-vide">${esc(T('pick_level'))}</span>`
      : `<b>${lv}</b> · ${esc(levelName(lv))}`;
    const off = dev ? lv : r.demonstrated_level;
    const perso = dev ? r.self_level : lv;
    const cible = card.querySelector('.cv2-nt--auto');
    const ancien = cible.querySelector('.cv2-accord');
    if (ancien) ancien.remove();
    const neuf = accordBadge(perso, off, dev);
    if (neuf) cible.insertAdjacentHTML('beforeend', neuf);
  }

  // Le verdict d'accord vit sur l'auto-évaluation : c'est ELLE qu'on situe par
  // rapport à la note qui fait foi, jamais l'inverse.
  function accordBadge(auto, officielle, dev) {
    if (estNul(auto) || estNul(officielle)) return '';
    const cls = auto === officielle ? 'ok' : (auto > officielle ? 'haut' : 'bas');
    const cle = cls === 'ok' ? 'acc_ok'
      : (dev ? (cls === 'haut' ? 'acc_haut' : 'acc_bas')
             : (cls === 'haut' ? 'acc_haut_mine' : 'acc_bas_mine'));
    return `<span class="cv2-accord cv2-accord--${cls}">${esc(T(cle))}</span>`;
  }

  async function saveEvaluation() {
    const cards = document.querySelectorAll('#cv2-drawer-body .cv2-res');
    const btn = $('#cv2-save-btn'); if (btn) btn.disabled = true;
    for (const c of cards) {
      // ⚠️ Bien `.is-mienne` : la carte porte maintenant DEUX échelles, et un
      // `querySelector` non qualifié ramènerait la première — celle du
      // développeur — jusque dans l'enregistrement d'un collaborateur.
      const sel = c.querySelector('.cv2-nt.is-mienne [data-lv].sel');
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
    // Plus de texte d'explication : il disait ce que le bandeau et les deux
    // colonnes « Requis / Démontré » montrent déjà.
    const b = bloc(3, T('bloc_tech'), null, 'tech');
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

  // ══════════════════════════════════════════════════════════════════
  //  CONFIGURER UNE ACTIVITÉ — sur quoi la jugera-t-on ?
  //  ⚠️ L'écran était un cours de méthode : « Qualification des sorties », une
  //  question par ligne (« Cette donnée démontre-t-elle la tenue… »), un grand
  //  bouton et sa phrase, trois pastilles « Mesure / Événement / Information »
  //  et encore une phrase, un paragraphe sur l'IA — sept bouts de texte par
  //  ligne pour une décision qui est BINAIRE.
  //  ⚠️ Et les trois autres natures ne servaient à RIEN : aucun code de l'app ne
  //  lit autre chose que RESULT (mastery, diagnostic, result_capabilities). On
  //  faisait classer à l'utilisateur ce que personne ne lit.
  //  Désormais : une question, une liste à cocher de ce que l'activité produit
  //  — montré comme la FLÈCHE de la carte qu'il est, avec sa destination —, et
  //  pour ce qui est coché, un seul champ : « Réussi quand… ».
  // ══════════════════════════════════════════════════════════════════
  async function showQualify() {
    const aid = state.activity.activity_id;
    showBusy(T('conf_busy_open'));
    setFooter([]);
    const [outs, ana] = await Promise.all([
      api(`/qualify/outputs/${aid}`), api(`/qualify/analyze/${aid}`, { method: 'POST' })]);
    // La source dit si une IA a réellement répondu : on ne présente jamais un
    // repli comme une analyse.
    const ia = !!(ana && ana.source === 'AI');

    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    const tete = document.createElement('div');
    tete.className = 'cv2-cf-tete';
    tete.innerHTML = `<h3>${esc(T('conf_q'))}</h3><p>${esc(T('conf_q_d'))}</p>`;
    body.appendChild(tete);

    const outputs = outs.outputs || [];
    if (!outputs.length) {
      body.insertAdjacentHTML('beforeend',
        `<div class="cv2-cf-vide"><i class="fa-solid fa-arrow-right-long"></i>
           <span>${esc(T('conf_empty'))}</span></div>`);
      setFooter([{ cls: 'btn-quiet', label: T('conf_close'), on: closeDrawer }]);
      return;
    }

    body.insertAdjacentHTML('beforeend',
      `<div class="cv2-cf-ia${ia ? '' : ' is-off'}">
         <i class="fa-solid ${ia ? 'fa-wand-magic-sparkles' : 'fa-hand-pointer'}"></i>
         <span>${esc(T(ia ? 'conf_ia_on' : 'conf_ia_off'))}</span></div>
       <div class="cv2-cf-lh">${esc(T('conf_list'))} <span>· ${esc(T('conf_list_d'))}</span></div>`);

    const props = {}; (ana.outputs || []).forEach(x => props[x.data_id] = x);
    const liste = document.createElement('div');
    liste.className = 'cv2-cf-liste';
    outputs.forEach(o => liste.appendChild(ligneProduit(o, props[o.data_id] || {})));
    body.appendChild(liste);

    setFooter([{ cls: 'btn-quiet', label: T('conf_cancel'), on: closeDrawer },
               { cls: 'btn-primary', label: T('conf_save'), on: saveQualify, id: 'cv2-q-ok' }]);
    // Le compte vit DANS le pied, à côté du bouton qu'il conditionne.
    const compte = document.createElement('div');
    compte.className = 'cv2-cf-compte'; compte.id = 'cv2-qcompte';
    $('#cv2-footer').prepend(compte);
    majCompteQualif();
  }

  function ligneProduit(o, p) {
    // Ce qui est ENREGISTRÉ l'emporte sur la proposition : l'IA ne revient pas
    // sur un choix déjà fait par quelqu'un.
    const coche = o.nature ? o.nature === 'RESULT' : p.suggested_nature === 'RESULT';
    const parIA = !o.nature && p.suggested_nature === 'RESULT';
    const std = o.minimum_performance_text || (coche ? (p.suggested_minimum_performance || '') : '');
    // Ce qui n'est pas coché garde sa nature d'avant : l'écran ne la montre plus,
    // ce n'est pas une raison de l'effacer.
    const autre = (o.nature && o.nature !== 'RESULT') ? o.nature
                : (p.suggested_nature && p.suggested_nature !== 'RESULT' ? p.suggested_nature : '');

    const nom = o.sans_libelle ? Tv('conf_fleche', { x: o.vers }) : o.name;
    const vers = (!o.sans_libelle && o.vers) ? Tv('conf_vers', { x: o.vers }) : '';
    const doute = parIA && p.confidence && p.confidence !== 'high';

    const el = document.createElement('div');
    el.className = 'cv2-cf-item' + (coche ? ' is-on' : '');
    el.dataset.dataId = o.data_id;
    el.dataset.autre = autre;
    el.innerHTML = `
      <label class="cv2-cf-l">
        <input type="checkbox" ${coche ? 'checked' : ''}>
        <span class="cv2-cf-box"><i class="fa-solid fa-check"></i></span>
        <span class="cv2-cf-nom">
          <b>${esc(nom)}</b>
          ${vers ? `<small><i class="fa-solid fa-arrow-right-long"></i>${esc(vers)}</small>` : ''}
        </span>
        ${parIA ? `<span class="cv2-cf-tag${doute ? ' is-doute' : ''}"
            ${p.justification ? `title="${esc(p.justification)}"` : ''}>
            <i class="fa-solid fa-wand-magic-sparkles"></i>${esc(T('conf_ia_tag'))}${doute
              ? ` · ${esc(T('conf_ia_check'))}` : ''}</span>` : ''}
      </label>
      <div class="cv2-cf-std">
        <label>${esc(T('conf_std'))}</label>
        <input type="text" class="cv2-cf-in" value="${esc(std)}" placeholder="${esc(T('conf_std_ph'))}">
      </div>`;
    const cb = el.querySelector('input[type=checkbox]');
    cb.addEventListener('change', () => {
      el.classList.toggle('is-on', cb.checked);
      majCompteQualif();
      // On vient de cocher : c'est le repère qu'on va écrire ensuite.
      if (cb.checked) {
        const champ = el.querySelector('.cv2-cf-in');
        if (!champ.value && p.suggested_minimum_performance) champ.value = p.suggested_minimum_performance;
        setTimeout(() => champ.focus(), 30);
      }
    });
    return el;
  }

  // Ce qui manque, dit AVANT le clic, à côté du bouton qu'il conditionne.
  function majCompteQualif() {
    const n = document.querySelectorAll('#cv2-drawer-body .cv2-cf-item.is-on').length;
    const box = $('#cv2-qcompte'); if (!box) return;
    box.className = 'cv2-cf-compte' + (n ? (n > 3 ? ' is-trop' : ' is-ok') : ' is-vide');
    box.textContent = n === 0 ? T('conf_n_0') : (n === 1 ? T('conf_n_1') : Tv('conf_n_n', { n }));
    box.title = n > 3 ? T('conf_trop') : '';
    if (n > 3) box.textContent += ' — ' + T('conf_trop');
    const ok = $('#cv2-q-ok');
    if (ok) ok.disabled = !n;
  }

  async function saveQualify() {
    const aid = state.activity.activity_id;
    const lignes = [...document.querySelectorAll('#cv2-drawer-body .cv2-cf-item')];
    const outputs = lignes.map(l => {
      const on = l.classList.contains('is-on');
      return { data_id: +l.dataset.dataId,
               nature: on ? 'RESULT' : (l.dataset.autre || null),
               minimum_performance_text: on ? l.querySelector('.cv2-cf-in').value : '',
               source: 'MANUAL' };
    });
    if (!outputs.some(o => o.nature === 'RESULT')) { majCompteQualif(); return; }

    showBusy(T('conf_busy_save'));
    setFooter([]);
    const save = await api(`/qualify/save/${aid}`, { method: 'POST', body: JSON.stringify({ outputs }) });
    if (save.__error) { return showQualify(); }
    const comp = await api(`/competence/generate/${aid}`, { method: 'POST' });
    let competence = '';
    if (comp.competence && (comp.competence.description_fr || comp.competence.description_en)) {
      const c = comp.competence;
      competence = (LANG === 'en' ? c.description_en : c.description_fr)
        || c.description_fr || c.description_en;
      // ⚠️ L'IA rédige les deux versions : n'en garder qu'une montrait la
      // phrase française à un anglophone (et l'inverse).
      await api(`/competence/save/${aid}`, {
        method: 'POST',
        body: JSON.stringify({ description: competence,
                               description_fr: c.description_fr || '',
                               description_en: c.description_en || '' }),
      });
    }
    await api(`/competence/result_links/generate/${aid}`, { method: 'POST' });
    await refreshDashboard();
    // ⚠️ On ne bascule PAS tout seul sur l'évaluation. Configurer et évaluer
    // sont deux décisions : enchaîner d'office redonnerait à l'ensemble l'air
    // d'un seul parcours, ce qu'on vient précisément de séparer.
    confTerminee(competence || state.activity.competence || '',
                 (save.outputs || []).filter(x => x.nature === 'RESULT'));
  }

  // L'écran de fin MONTRE ce que la configuration a produit — la compétence et
  // ce sur quoi on jugera — au lieu de deux phrases qui disaient que c'était fait.
  function confTerminee(competence, resultats) {
    const body = $('#cv2-drawer-body'); body.innerHTML = '';
    body.insertAdjacentHTML('beforeend', `
      <div class="cv2-cf-fin">
        <div class="cv2-cf-fin-t"><i class="fa-solid fa-circle-check"></i>${esc(T('conf_done_t'))}</div>
        ${competence ? `<div class="cv2-cf-fin-k">${esc(T('conf_done_comp'))}</div>
          <div class="cv2-cf-fin-comp">${esc(competence)}</div>` : ''}
        <div class="cv2-cf-fin-k">${esc(T('conf_done_on'))}</div>
        <ul class="cv2-cf-fin-l">${resultats.map(r => `<li><b>${esc(r.name)}</b>${
          r.minimum_performance_text ? `<span>${esc(T('conf_std_lu'))} ${esc(r.minimum_performance_text)}</span>` : ''
        }</li>`).join('')}</ul>
      </div>`);
    setFooter([
      { cls: 'btn-quiet', label: T('conf_close'), on: () => { closeDrawer(); } },
      { cls: 'btn-primary', label: T('conf_done_go'), on: () => openDrawer(state.activity) },
    ]);
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
        (st.capabilities.length
          ? st.capabilities.map(c => carteCapacite(c)).join('')
          : `<div class="cv2-emptydom">${esc(T('no_caps'))}</div>`);
      capsBox.querySelectorAll('[data-cap]').forEach(b => b.onclick = () => {
        const carte = b.closest('.cv2-cap');
        const v = b.dataset.niv === '' ? null : +b.dataset.niv;
        carte.querySelectorAll('[data-cap]').forEach(x => x.classList.remove('sel'));
        b.classList.add('sel');
        api(`/competence/result_links/${state.activity.activity_id}`, {
          method: 'POST',
          body: JSON.stringify({ link_id: +carte.dataset.lien, required_level: v }),
        });
      });
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
    $('#cv2-plan-sub').innerHTML =
      `<span class="qui">${esc(state.cibleNom)}</span><span class="ou">${esc(state.roleName)}</span>`;
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
    state.plan.actions = ordonner(state.plan.actions);
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
          ${p.activites.length} ${esc(p.activites.length === 1 ? T('plan_gap_1') : T('plan_gap_intro'))}</div></div>`;
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
          <div class="cv2-mix" id="cv2-mix" title="${esc(T('plan_mix'))}"></div>
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

    renderActions(true);
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

  /* ══ Le parcours ═══════════════════════════════════════════════════════
     ⚠️ La liste était une PILE de cartes : les actions de toutes les activités
     mêlées, et dans chaque carte un type minuscule, un champ d'heures et le nom
     de l'activité posés sur une même ligne sans rien pour les distinguer, puis
     un « Objectif » qui répétait souvent le titre. On ne savait ni POURQUOI une
     action était là, ni DANS QUEL ORDRE les faire, ni QUAND elles tombaient —
     alors que le panneau de droite calcule justement les semaines.
     Désormais : une section par activité (l'écart qu'on vient combler, du
     niveau actuel au niveau visé), des étapes NUMÉROTÉES dans l'ordre du plan,
     et dans chaque carte trois zones qui ne se mélangent plus — la nature et la
     charge en tête, l'action, puis ses champs étiquetés — et en pied, les
     semaines où elle tombe. */

  // La nature d'une action porte sa couleur et son pictogramme partout : la
  // pastille numérotée, l'étiquette de la carte, la barre de répartition.
  const NATURES = {
    TERRAIN: 'fa-briefcase',
    ACCOMPAGNEMENT: 'fa-handshake-angle',
    FORMATION: 'fa-graduation-cap',
  };
  const nature = a => (NATURES[a.type] ? a.type : 'FORMATION');
  const connue = id => id != null && state.plan.activites.some(x => x.activity_id === id);

  /* ⚠️ Le plan est une SUITE : l'IA ordonne ses actions (« ce qui conditionne
     le reste d'abord ») et l'échéancier remplit les semaines dans cet ordre.
     On regroupe par activité en gardant l'ordre de PREMIÈRE apparition — un
     tri par écart déferait la séquence proposée. Appliqué au chargement : l'ordre
     affiché, l'ordre enregistré et l'ordre des semaines sont le même. */
  function ordonner(actions) {
    const ordre = [], paquets = {};
    actions.forEach(a => {
      const k = connue(a.activity_id) ? String(a.activity_id) : '_';
      if (!paquets[k]) { paquets[k] = []; if (k !== '_') ordre.push(k); }
      paquets[k].push(a);
    });
    if (paquets._) ordre.push('_');
    return ordre.reduce((tout, k) => tout.concat(paquets[k]), []);
  }

  // Où tombe chaque action : on les enchaîne à hauteur de ce qu'on a dit
  // pouvoir y consacrer par semaine — le même remplissage que l'échéancier.
  function planning(c) {
    let cumul = 0;
    return state.plan.actions.map(a => {
      const ws = Math.floor(cumul / c.hs) + 1;
      cumul += Math.max(1, +a.heures || 1);
      const we = Math.ceil(cumul / c.hs);
      return { ws, we, deborde: we > c.sem };
    });
  }
  const dateEtape = st => (st.ws === st.we ? Tv('plan_week_1', { a: st.ws })
                                           : Tv('plan_week_n', { a: st.ws, b: st.we }));

  function renderActions(anime) {
    const p = state.plan;
    const groupes = [];
    p.actions.forEach((a, i) => {
      const k = connue(a.activity_id) ? a.activity_id : null;
      let g = groupes[groupes.length - 1];
      if (!g || g.k !== k) { g = { k, items: [] }; groupes.push(g); }
      g.items.push(i);
    });
    const box = $('#cv2-actions');
    box.innerHTML = groupes.map(g => {
      const act = g.k != null ? p.activites.find(x => x.activity_id === g.k) : null;
      // ⚠️ Un <div>, pas un <header> : competences.css déclare
      // `header { position: sticky }` pour TOUTE la page — un <header> ici
      // collait en haut de la fenêtre et passait par-dessus les cartes.
      return `<section class="cv2-etapes-g">
          <div class="cv2-etapes-gh">
            <div class="l1">
              <div class="t">${esc(act ? act.activity_name : T('plan_other'))}</div>
              <div class="tot" data-gtot></div>
            </div>
            ${act ? `<div class="niv" title="${esc(T('plan_gap_from_to'))}">
                <span>${esc(act.demonstrated_label)}</span>
                <i class="fa-solid fa-arrow-right"></i>
                <b>${esc(act.required_label)}</b></div>` : ''}
          </div>
          <ol class="cv2-etapes">${g.items.map(i => carteEtape(p.actions[i], i, anime)).join('')}</ol>
        </section>`;
    }).join('');
    brancherEtapes(box);
  }

  function carteEtape(a, i, anime) {
    const n = nature(a);
    // Seuls les champs remplis s'affichent : une étiquette suivie de rien se
    // lit comme une information manquante.
    const champs = [[T('plan_target'), a.objectif], [T('plan_deliv'), a.livrable],
                    [T('plan_crit'), a.critere]].filter(([, v]) => v && String(v).trim());
    return `<li class="cv2-etape cv2-t--${n}" data-i="${i}"
                ${anime ? `style="animation-delay:${i * 35}ms"` : 'data-calme="1"'}>
        <span class="cv2-etape-n" aria-hidden="true">${i + 1}</span>
        <div class="cv2-etape-c">
          <div class="cv2-etape-h">
            <span class="cv2-etape-type"><i class="fa-solid ${NATURES[n]}"></i>${esc(state.plan.types[n] || n)}</span>
            <span class="cv2-pas" role="group" aria-label="${esc(T('plan_load'))}">
              <button type="button" data-pas="-1" aria-label="${esc(T('plan_less'))}">&minus;</button>
              <input type="number" min="1" max="200" value="${Math.max(1, +a.heures || 1)}"
                     aria-label="${esc(T('plan_load'))}">
              <span class="u">${esc(T('plan_h'))}</span>
              <button type="button" data-pas="1" aria-label="${esc(T('plan_more'))}">+</button>
            </span>
          </div>
          <div class="cv2-etape-t">${esc(a.titre)}</div>
          ${champs.length ? `<dl class="cv2-etape-d">${champs.map(([k, v]) =>
              `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` : ''}
          <div class="cv2-etape-f">
            <span class="cv2-etape-sem"><i class="fa-regular fa-calendar"></i><span data-sem></span></span>
            <button type="button" class="cv2-etape-x" title="${esc(T('plan_del'))}">
              <i class="fa-solid fa-trash-can"></i>${esc(T('plan_remove'))}</button>
          </div>
        </div>
      </li>`;
  }

  function brancherEtapes(box) {
    box.querySelectorAll('.cv2-etape').forEach(li => {
      const i = +li.dataset.i;
      const a = state.plan.actions[i];
      const inp = li.querySelector('.cv2-pas input');
      const poser = h => {
        a.heures = Math.max(1, Math.min(200, Math.round(+h) || 1));
        recalculer();
      };
      inp.addEventListener('input', () => poser(inp.value));
      // Le champ se corrige à la SORTIE, pas pendant la frappe : effacer « 12 »
      // pour taper « 8 » passerait sinon par un « 1 » imposé.
      inp.addEventListener('change', () => { inp.value = a.heures; });
      // Le pas suit l'ordre de grandeur : une heure près d'une charge de 3 h,
      // cinq près d'une charge de 60.
      li.querySelectorAll('[data-pas]').forEach(b => b.addEventListener('click', () => {
        const h = +a.heures || 1;
        poser(h + (+b.dataset.pas) * (h < 10 ? 1 : (h < 40 ? 2 : 5)));
        inp.value = a.heures;
      }));
      li.querySelector('.cv2-etape-x').addEventListener('click', () => {
        state.plan.actions.splice(i, 1);
        renderActions(false);
        recalculer();
      });
      li.addEventListener('mouseenter', () => eclairer(i, nature(a)));
      li.addEventListener('mouseleave', () => eclairer(null));
    });
  }

  // Survoler une étape allume SES semaines dans l'échéancier : la liste et les
  // curseurs parlent enfin du même temps.
  function eclairer(i, n) {
    const box = $('#cv2-semaines');
    const st = (i == null || !state.planning) ? null : state.planning[i];
    if (!box) return;
    box.classList.toggle('is-lit', !!st);
    if (st) box.dataset.nature = n; else delete box.dataset.nature;
    box.querySelectorAll('.cv2-semaine').forEach((el, w) =>
      el.classList.toggle('lit', !!st && w + 1 >= st.ws && w + 1 <= st.we));
  }

  // Ce qui dépend des heures se met à jour SUR PLACE : réécrire les cartes à
  // chaque frappe ferait perdre le curseur du champ qu'on est en train de taper.
  function majEtapes(c) {
    const plan = state.planning;
    document.querySelectorAll('#cv2-actions .cv2-etape').forEach(li => {
      const st = plan[+li.dataset.i];
      if (!st) return;
      li.classList.toggle('deborde', st.deborde);
      li.querySelector('[data-sem]').textContent =
        dateEtape(st) + (st.deborde ? ' · ' + T('plan_week_over') : '');
    });
    document.querySelectorAll('#cv2-actions .cv2-etapes-g').forEach(g => {
      const idx = [...g.querySelectorAll('.cv2-etape')].map(li => +li.dataset.i);
      const h = idx.reduce((t, i) => t + (+state.plan.actions[i].heures || 0), 0);
      g.querySelector('[data-gtot]').textContent =
        (idx.length === 1 ? T('plan_steps_1') : Tv('plan_steps_n', { n: idx.length }))
        + ` · ${h} ${T('plan_h')}`;
    });
    majMix();
  }

  // La répartition par nature, et du même coup la légende des couleurs. Le CDC
  // veut qu'un écart se comble D'ABORD en situation : cette barre le montre.
  function majMix() {
    const box = $('#cv2-mix');
    if (!box) return;
    const par = {};
    state.plan.actions.forEach(a => { par[nature(a)] = (par[nature(a)] || 0) + (+a.heures || 0); });
    const total = Object.keys(par).reduce((t, k) => t + par[k], 0) || 1;
    const ordre = ['TERRAIN', 'ACCOMPAGNEMENT', 'FORMATION'].filter(n => par[n]);
    box.innerHTML = `<div class="cv2-mix-bar">${ordre.map(n =>
        `<i class="cv2-t--${n}" style="flex-basis:${par[n] / total * 100}%"></i>`).join('')}</div>
      <div class="cv2-mix-leg">${ordre.map(n =>
        `<span class="cv2-t--${n}"><i class="fa-solid ${NATURES[n]}"></i>${esc(state.plan.types[n] || n)}
          <b>${par[n]} ${esc(T('plan_h'))}</b></span>`).join('')}</div>`;
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
    state.planning = planning(c);
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

    majEtapes(c);
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
      const dedans = (state.planning || [])
        .map((st, k) => (i + 1 >= st.ws && i + 1 <= st.we ? k + 1 : 0)).filter(Boolean);
      el.title = `${T('plan_wk')}${i + 1} · ${pris} ${T('plan_h')}` + (dedans.length
        ? ' · ' + Tv(dedans.length === 1 ? 'plan_week_step_1' : 'plan_week_step_n', { l: dedans.join(', ') })
        : '');
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
    state.plan.activites = r.activites || state.plan.activites;
    state.plan.actions = ordonner(r.actions || []);
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
