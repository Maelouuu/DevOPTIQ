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
      p_profil_peu: "Le profil se dessine à partir de trois activités évaluées ou dotées d'un niveau attendu. En attendant, les voici une par une.",
      cal_voir_tout: 'Voir le calendrier',
      cal_aucune_a_venir: 'Aucune séance prévue pour le moment.',
      cal_seances: 'Prochaines séances',
      ev_filtres: 'Filtrer',
      ev_min_t: 'Comment se calcule ce niveau',
      pal_echelle_t: "L'échelle 0 → 4",
      ev_min_i: "Le niveau d'une activité est le PLUS BAS de ses sorties, jamais leur moyenne : on ne tient une activité que si on tient tout ce qu'elle produit. Une sortie non évaluée ne compte pas pour zéro — elle laisse le niveau en attente.",
      sq_prete_1: 'La mesure est prête.',
      ev_retour_role: 'Retour au rôle',
      ev_niv_role: 'Niveau du rôle',
      ev_nb_act: '[[n]] activités',
      ev_nb_act_1: '1 activité',
      ev_suivi_par: 'suivi par [[x]]',
      ev_evaluees: '[[n]] activités évaluées sur [[t]]',
      ev_col_sor: 'Ce que l’activité produit',
      ev_col_sor_d: 'Les sorties de l’activité choisie à gauche. C’est là-dessus qu’on note.',
      save_rien: 'Rien à enregistrer sur cette activité.',
      p_regler_req: 'Réglez le niveau attendu',
      ses_f_on: 'Ne montrer que celles-ci',
      ses_f_off: 'Montrer tout le monde',
      ses_f_tout: 'Tout afficher',
      ses_f_actif: '[[t]] · [[n]] séance',
      ses_f_actif_n: '[[t]] · [[n]] séances',
      ses_clic_jour: 'Cliquez un jour du calendrier pour poser la date.',
      ses_poser_le: 'Planifier ce jour-là',
      ev_col_act: 'Les activités du rôle',
      ev_sorties_n: '[[n]] sorties',
      ev_sorties_1: '1 sortie',
      ev_non_eval: 'non évaluée',
      ev_a_config: 'à configurer',
      ev_en_retard_n: '[[n]] en retard',
      ev_niv_act: 'Niveau de cette activité',
      ev_min_de: 'le [[b]]minimum[[/b]] de ses sorties, jamais la moyenne',
      ev_cible_dit: 'une cible se dessine, elle ne se remplit pas',
      ev_tech: 'Technicité',
      ev_rien_eval: "Rien à évaluer tant que l'activité n'est pas configurée.",
      ev_enregistrer: 'Enregistrer les notes',
      sq_titre: "Séance d'évaluation",
      sq_ouvrir: 'Tenir la séance',
      sq_rouvrir: 'Revoir la séance',
      sq_tranches: 'paliers évalués',
      sq_q: "Qu'a-t-on mesuré ?",
      sq_observe: "Ce qu'on a observé",
      sq_observe_ph: 'Deux relances du client, sinon le fond y est.',
      sq_passer: 'Passer',
      sq_suivant: 'Évaluer et passer au suivant',
      sq_dernier: 'Évaluer le dernier',
      sq_liste: 'Les paliers de la séance',
      sq_liste_d: "on peut revenir sur n'importe lequel",
      sq_en_cours: 'En cours de relevé',
      sq_a_venir: 'à venir',
      sq_bilan: 'Ce que la séance aura changé',
      sq_rien_ecrit: "Rien n'est écrit tant que la séance n'est pas clôturée.",
      sq_clore_t: 'Clôturer la séance',
      sq_clore_d: "Les mesures seront enregistrées d'un bloc, et les verdicts calculés.",
      sq_reste: 'Il reste [[n]] paliers à évaluer.',
      sq_reste_1: 'Il reste 1 palier à évaluer.',
      sq_prete: 'Les [[n]] mesures sont prêtes.',
      sq_vide: 'Aucun palier rattaché à cette séance.',
      sq_cible_de: 'cible [[v]]',
      sq_deviendra: 'deviendra',
      sq_tenue_le: 'Séance tenue le [[d]]',
      pal_norme: 'Norme',
      pal_norme_mod: "Modifier la norme de l'entreprise",
      pal_au_plus: 'au plus',
      pal_au_moins: 'au moins',
      pal_norme_titre: "La norme de l'entreprise",
      pal_norme_d: 'Ce qui est attendu de cette sortie, pour tout le monde — elle ne dépend pas de qui fait le travail.',
      pal_valeur: 'Valeur',
      pal_unite: 'Unité',
      pal_unite_ph: 'essais, lignes, €…',
      pal_unite_autre: 'Autre…',
      pal_u_pct: '% (pourcent)',
      pal_u_j: 'j (jours)',
      pal_u_h: 'h (heures)',
      pal_premiere: 'Première mesure',
      pal_premiere_d: "Trois choses, en une fois : ce que l'entreprise attend, ce qui a été relevé, et le niveau qui en découle.",
      pal_premiere_ok: 'Première mesure enregistrée.',
      pal_norme_deja: 'Norme déjà définie pour cette sortie —',
      pal_mesure_q: "Qu'a-t-on mesuré pour [[x]] ?",
      pal_mesure_manque: 'Donnez la valeur mesurée.',
      pal_niveau_suivra: 'Niveau qui en découle',
      pal_niveau_pose: 'Niveau posé à la main',
      pal_exp_poser: 'Expertise',
      pal_exp_retirer: "Retirer l'expertise",
      pal_exp_posee: 'posée à la main',
      pal_exp_mesure: 'mesuré : [[n]] · [[l]]',
      pal_exp_d: "Aucun chiffre ne définit le niveau 4 : la déduction plafonne à 3. L'expertise se pose.",
      pal_exp_ok: 'Expertise posée.',
      pal_exp_off: 'Expertise retirée.',
      pal_sens: "Mieux, c'est",
      pal_moins: 'moins',
      pal_plus: 'plus',
      pal_norme_off: 'Pas de norme chiffrée',
      pal_norme_off_d: 'Ce résultat se juge, il ne se mesure pas.',
      pal_poser_norme: 'Poser une norme',
      pal_effacer_norme: 'Retirer la norme',
      pal_norme_ok: 'Norme enregistrée',
      pal_norme_retiree: 'Norme retirée — ce résultat se note à la main',
      pal_atteint: 'Atteint',
      pal_manque: 'Manqué',
      pal_encours: 'En cours',
      pal_audela: 'Au-delà',
      pal_audela_tag: 'Au-delà de la norme',
      pal_mesure_k: 'mesuré',
      pal_sans_norme: 'Jugée à la main',
      pal_sans_norme_d: "Cette sortie n'a pas de chiffre attendu : son niveau se pose sur l'échelle ci-dessus. Donnez-lui la norme de l'entreprise pour la suivre en paliers mesurés.",
      pal_definir_norme: "Définir la norme de l'entreprise",
      ses_verdicts_t: 'Comment le verdict tombe',
      pal_audela_d: "un palier de mieux que l'attendu",
      pal_norme_tag: "Norme de l'entreprise",
      pal_mesure_de: 'mesuré [[v]]',
      pal_echeance: 'échéance [[d]]',
      pal_retard: 'en retard',
      pal_niveau_deduit: 'Niveau déduit de la dernière mesure',
      pal_qualifie: 'Qualifié',
      pal_qualifie_av: 'Qualifié · avancé',
      pal_rien: 'Aucun palier posé',
      pal_rien_d: 'Posez la première marche : une cible, une échéance.',
      pal_poser: 'Poser un palier',
      pal_poser_suivant: 'Poser la marche suivante',
      pal_trancher: 'Évaluer ce palier',
      pal_cible: 'Cible',
      pal_delai: 'Délai',
      pal_jours: 'jours',
      pal_propose: 'Proposé : [[v]]',
      pal_cree: 'Palier posé',
      pal_supprime: 'Palier retiré',
      pal_tranche_ok: 'Palier atteint',
      pal_tranche_ko: 'Palier manqué',
      pal_mesure_lbl: 'Mesuré',
      pal_preuve_ph: "Ce qu'on a observé",
      pal_retirer: 'Retirer ce palier',
      pal_annuler: 'Annuler',
      pal_valider: 'Valider',
      pal_comment: 'Comment le niveau se déduit',
      pal_comment_0: 'sous le premier palier',
      pal_comment_1: 'un palier franchi, pas la norme',
      pal_comment_2: 'la norme atteinte — qualifié',
      pal_comment_3: 'un palier au-delà — avancé',
      pal_comment_4: "Expertise — aucun chiffre ne la définit : elle se pose à la main.",
      pal_pas_de_note: "Une sortie mesurée n'a pas de note à saisir : le niveau vient du chiffre relevé en session.",
      pal_apres_echec: 'Ce palier est manqué. Analysez les savoirs plutôt que de reposer la même cible.',
      pal_vers_diag: 'Analyser les savoirs',
      ses_titre: "Sessions d'évaluation",
      ses_sub: 'Chaque échéance de palier pose une session. On y relève les chiffres, et les verdicts tombent.',
      ses_cal: 'Calendrier',
      ses_ouvrir: 'Ouvrir le calendrier',
      ses_prochaine: 'Prochaine session',
      ses_aucune: 'Aucune session prévue',
      ses_planifier: 'Planifier une session',
      ses_en_retard: 'en retard',
      ses_semaine: 'cette semaine',
      ses_mois: 'ce mois',
      ses_tenues: 'tenues cette année',
      ses_dans: 'dans [[n]] jours',
      ses_demain: 'demain',
      ses_aujourdhui: "aujourd'hui",
      ses_passe: 'il y a [[n]] jours',
      ses_a_trancher: '[[n]] palier à évaluer',
      ses_a_trancher_pl: '[[n]] paliers à évaluer',
      ses_tenue: 'Tenue',
      ses_annulee: 'Annulée',
      ses_prevue: 'Prévue',
      ses_rien_a_trancher: 'Aucun palier rattaché à cette session.',
      ses_cloturer: 'Clôturer la session',
      ses_reporter: 'Reporter',
      ses_note: "Ce qu'on a observé",
      ses_verdicts_calc: "En séance, vous relevez le chiffre mesuré — rien d'autre. L'application le compare à la cible du palier et en tire le verdict : atteint si la cible est tenue, manqué sinon. Personne ne coche le résultat à la main, et c'est ce verdict qui fait monter le niveau.",
      ses_close_ok: 'Session clôturée',
      ses_cree: 'Session planifiée',
      ses_suppr: 'Session retirée',
      ses_legend_palier: 'palier à évaluer',
      ses_legend_retard: 'échéance dépassée',
      ses_legend_tenue: 'session tenue',
      ses_vide_mois: 'Aucune session ce mois-ci.',
      ses_choisir_une: 'Choisissez une session dans le calendrier.',
      ses_objet_ph: 'Objet de la session (facultatif)',
      ses_date: 'Date',
      ses_lun: 'lun',
      ses_mar: 'mar',
      ses_mer: 'mer',
      ses_jeu: 'jeu',
      ses_ven: 'ven',
      ses_sam: 'sam',
      ses_dim: 'dim',
      ses_mois_prec: 'Mois précédent',
      ses_mois_suiv: 'Mois suivant',
      ev_titre: 'Évolution',
      ev_retour: '← Évaluation',
      ev_histo: "Tout ce qui s'est passé",
      ev_rien: 'Aucune mesure encore : le graphe apparaîtra après la première session tenue.',
      ev_pose: 'Palier posé : [[v]]',
      ev_aligne: 'Aligné sur la norme : [[v]]',
      ev_atteindre: "L'atteindre rendra qualifié.",
      ev_a_venir: 'à venir',
      ev_session_prevue: "Session d'évaluation",
      ev_session_tenue: 'Session tenue',
      rel_bas: 'cible [[c]] · [[d]]',
      rel_a_mesurer: 'à mesurer',
      rel_seuil: 'seuil « avancé »',
      rel_norme: 'la norme',
      rel_zone: 'zone tenue',
      rel_franchie: 'norme franchie',
      rel_tenues: 'marches tenues sur [[t]]',
      rel_tenues_1: 'marche tenue sur [[t]]',
      rel_repris: 'repris depuis le départ',
      rel_gagne: 'gagnés depuis le départ',
      rel_suivi: 'jours de suivi',
      rel_suivi_1: 'jour de suivi',
      rel_detail: 'Le détail des séances',
      rel_detail_off: 'Masquer le détail',
      rel_aria: "Le relief de « [[x]] » : [[n]] mesures, norme [[v]]. Le temps en abscisse, la valeur en ordonnée — monter veut dire progresser.",
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
      rien_a_evaluer: "Cette activité ne produit rien dans la cartographie : aucune flèche n'en part. Il n'y a donc rien à évaluer tant qu'elle n'a pas de sortie.",
      conf_done_t: 'Activité configurée',
      evidence_ph: 'Preuve / commentaire (facultatif)', add_evidence: '+ Ajouter une preuve',
      diagnose: "Diagnostiquer l'écart",
      loading: 'Chargement…',
      configured_go_eval: 'Sorties qualifiées ✓ — évaluez maintenant le niveau du collaborateur pour chaque résultat, puis enregistrez.',
      req_failed: 'Action impossible (erreur réseau ou serveur).',
      forbidden: "Vous n'avez pas le droit de noter ce collaborateur.",
      pick_level: 'À évaluer', roles_label: 'Rôles du collaborateur',
      self_assess: "S'auto-évaluer",
      pas_configuree: "Cette activité ne produit rien dans la cartographie : aucune flèche n'en part. Il n'y a donc rien à évaluer.",
      b_held: 'Niveau tenu', b_gap: 'En écart', b_todo: 'À évaluer', b_setup: 'Sans sortie',
      filter_off: 'Tout afficher', no_match: 'Aucune activité dans cette catégorie.',
      m_result_one: 'résultat', m_result_many: 'résultats', m_partial: 'sur',
      m_eval_one: 'évalué', m_eval_many: 'évalués',
      m_last: 'évalué le', m_never: 'jamais évaluée', m_toqualify: 'aucune sortie dans la carto',
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
      p_profil_peu: 'The profile takes shape from three activities that are assessed or carry a target level. In the meantime, here they are one by one.',
      cal_voir_tout: 'Open the calendar',
      cal_aucune_a_venir: 'No session scheduled at the moment.',
      cal_seances: 'Upcoming sessions',
      ev_filtres: 'Filter',
      ev_min_t: 'How this level is worked out',
      pal_echelle_t: 'The 0 → 4 scale',
      ev_min_i: "An activity's level is the LOWEST of its outputs, never their average: you only hold an activity if you hold everything it produces. An output that has not been assessed does not count as zero — it leaves the level pending.",
      sq_prete_1: 'The measurement is ready.',
      ev_retour_role: 'Back to the role',
      ev_niv_role: 'Role level',
      ev_nb_act: '[[n]] activities',
      ev_nb_act_1: '1 activity',
      ev_suivi_par: 'followed by [[x]]',
      ev_evaluees: '[[n]] of [[t]] activities assessed',
      ev_col_sor: 'What the activity produces',
      ev_col_sor_d: 'The outputs of the activity picked on the left. This is what you rate.',
      save_rien: 'Nothing to save on this activity.',
      p_regler_req: 'Set the expected level',
      ses_f_on: 'Show only these',
      ses_f_off: 'Show everyone',
      ses_f_tout: 'Show all',
      ses_f_actif: '[[t]] · [[n]] session',
      ses_f_actif_n: '[[t]] · [[n]] sessions',
      ses_clic_jour: 'Click a day in the calendar to set the date.',
      ses_poser_le: 'Schedule that day',
      ev_col_act: "The role's activities",
      ev_sorties_n: '[[n]] outputs',
      ev_sorties_1: '1 output',
      ev_non_eval: 'not assessed',
      ev_a_config: 'to configure',
      ev_en_retard_n: '[[n]] overdue',
      ev_niv_act: 'Level of this activity',
      ev_min_de: 'the [[b]]lowest[[/b]] of its outputs, never the average',
      ev_cible_dit: 'a target is outlined, never filled in',
      ev_tech: 'Technicity',
      ev_rien_eval: 'Nothing to assess until the activity is configured.',
      ev_enregistrer: 'Save the levels',
      sq_titre: 'Evaluation session',
      sq_ouvrir: 'Hold the session',
      sq_rouvrir: 'Review the session',
      sq_tranches: 'steps assessed',
      sq_q: 'What was measured?',
      sq_observe: 'What was observed',
      sq_observe_ph: 'Two client reminders, otherwise the substance is there.',
      sq_passer: 'Skip',
      sq_suivant: 'Assess and move on',
      sq_dernier: 'Assess the last one',
      sq_liste: "The session's steps",
      sq_liste_d: 'you can go back to any of them',
      sq_en_cours: 'Being recorded',
      sq_a_venir: 'upcoming',
      sq_bilan: 'What the session will change',
      sq_rien_ecrit: 'Nothing is written until the session is closed.',
      sq_clore_t: 'Close the session',
      sq_clore_d: 'The measurements are saved together, and the verdicts computed.',
      sq_reste: '[[n]] steps left to assess.',
      sq_reste_1: '1 step left to assess.',
      sq_prete: 'All [[n]] measurements are ready.',
      sq_vide: 'No step attached to this session.',
      sq_cible_de: 'target [[v]]',
      sq_deviendra: 'will become',
      sq_tenue_le: 'Session held on [[d]]',
      pal_norme: 'Standard',
      pal_norme_mod: 'Change the company standard',
      pal_au_plus: 'at most',
      pal_au_moins: 'at least',
      pal_norme_titre: 'The company standard',
      pal_norme_d: 'What is expected of this output, for everyone — it does not depend on who does the work.',
      pal_valeur: 'Value',
      pal_unite: 'Unit',
      pal_unite_ph: 'tests, lines, €…',
      pal_unite_autre: 'Other…',
      pal_u_pct: '% (percent)',
      pal_u_j: 'j (days)',
      pal_u_h: 'h (hours)',
      pal_premiere: 'First reading',
      pal_premiere_d: 'Three things at once: what the company expects, what was measured, and the level that follows.',
      pal_premiere_ok: 'First reading saved.',
      pal_norme_deja: 'Standard already set for this output —',
      pal_mesure_q: 'What was measured for [[x]]?',
      pal_mesure_manque: 'Enter the measured value.',
      pal_niveau_suivra: 'Level this gives',
      pal_niveau_pose: 'Level set by hand',
      pal_exp_poser: 'Expertise',
      pal_exp_retirer: 'Remove expertise',
      pal_exp_posee: 'set by hand',
      pal_exp_mesure: 'measured: [[n]] · [[l]]',
      pal_exp_d: 'No figure defines level 4: the derivation caps at 3. Expertise is set by hand.',
      pal_exp_ok: 'Expertise set.',
      pal_exp_off: 'Expertise removed.',
      pal_sens: 'Better means',
      pal_moins: 'less',
      pal_plus: 'more',
      pal_norme_off: 'No numeric standard',
      pal_norme_off_d: 'This result is judged, not measured.',
      pal_poser_norme: 'Set a standard',
      pal_effacer_norme: 'Remove the standard',
      pal_norme_ok: 'Standard saved',
      pal_norme_retiree: 'Standard removed — this result is now graded by hand',
      pal_atteint: 'Met',
      pal_manque: 'Missed',
      pal_encours: 'Under way',
      pal_audela: 'Beyond',
      pal_audela_tag: 'Beyond the standard',
      pal_mesure_k: 'measured',
      pal_sans_norme: 'Judged by hand',
      pal_sans_norme_d: 'This output has no expected figure: its level is set on the scale above. Give it the company standard to follow it as measured steps.',
      pal_definir_norme: 'Set the company standard',
      ses_verdicts_t: 'How the verdict is reached',
      pal_audela_d: 'one step better than expected',
      pal_norme_tag: 'Company standard',
      pal_mesure_de: 'measured [[v]]',
      pal_echeance: 'due [[d]]',
      pal_retard: 'overdue',
      pal_niveau_deduit: 'Level derived from the last measurement',
      pal_qualifie: 'Qualified',
      pal_qualifie_av: 'Qualified · advanced',
      pal_rien: 'No step set',
      pal_rien_d: 'Set the first step: a target and a deadline.',
      pal_poser: 'Set a step',
      pal_poser_suivant: 'Set the next step',
      pal_trancher: 'Assess this step',
      pal_cible: 'Target',
      pal_delai: 'Deadline',
      pal_jours: 'days',
      pal_propose: 'Suggested: [[v]]',
      pal_cree: 'Step set',
      pal_supprime: 'Step removed',
      pal_tranche_ok: 'Step met',
      pal_tranche_ko: 'Step missed',
      pal_mesure_lbl: 'Measured',
      pal_preuve_ph: 'What was observed',
      pal_retirer: 'Remove this step',
      pal_annuler: 'Cancel',
      pal_valider: 'Confirm',
      pal_comment: 'How the level is derived',
      pal_comment_0: 'below the first step',
      pal_comment_1: 'a step cleared, not the standard',
      pal_comment_2: 'the standard met — qualified',
      pal_comment_3: 'one step beyond — advanced',
      pal_comment_4: 'Expert — no figure defines it: it is set by hand.',
      pal_pas_de_note: 'A measured output has no level to type: it comes from the figure recorded in the session.',
      pal_apres_echec: 'This step was missed. Analyse the underlying knowledge rather than setting the same target again.',
      pal_vers_diag: 'Analyse knowledge',
      ses_titre: 'Evaluation sessions',
      ses_sub: 'Each step deadline sets a session. You record the figures there, and the verdicts follow.',
      ses_cal: 'Calendar',
      ses_ouvrir: 'Open the calendar',
      ses_prochaine: 'Next session',
      ses_aucune: 'No session scheduled',
      ses_planifier: 'Schedule a session',
      ses_en_retard: 'late',
      ses_semaine: 'this week',
      ses_mois: 'this month',
      ses_tenues: 'held this year',
      ses_dans: 'in [[n]] days',
      ses_demain: 'tomorrow',
      ses_aujourdhui: 'today',
      ses_passe: '[[n]] days ago',
      ses_a_trancher: '[[n]] step to assess',
      ses_a_trancher_pl: '[[n]] steps to assess',
      ses_tenue: 'Held',
      ses_annulee: 'Cancelled',
      ses_prevue: 'Scheduled',
      ses_rien_a_trancher: 'No step attached to this session.',
      ses_cloturer: 'Close the session',
      ses_reporter: 'Postpone',
      ses_note: 'What was observed',
      ses_verdicts_calc: 'In a session you record the measured figure — nothing else. The app compares it with the step target and derives the verdict: reached if the target is met, missed otherwise. Nobody ticks the outcome by hand, and it is that verdict which raises the level.',
      ses_close_ok: 'Session closed',
      ses_cree: 'Session scheduled',
      ses_suppr: 'Session removed',
      ses_legend_palier: 'step to assess',
      ses_legend_retard: 'deadline passed',
      ses_legend_tenue: 'session held',
      ses_vide_mois: 'No session this month.',
      ses_choisir_une: 'Pick a session from the calendar.',
      ses_objet_ph: 'Session purpose (optional)',
      ses_date: 'Date',
      ses_lun: 'Mon',
      ses_mar: 'Tue',
      ses_mer: 'Wed',
      ses_jeu: 'Thu',
      ses_ven: 'Fri',
      ses_sam: 'Sat',
      ses_dim: 'Sun',
      ses_mois_prec: 'Previous month',
      ses_mois_suiv: 'Next month',
      ev_titre: 'Progress',
      ev_retour: '← Evaluation',
      ev_histo: 'Everything that happened',
      ev_rien: 'No measurement yet: the chart appears after the first session held.',
      ev_pose: 'Step set: [[v]]',
      ev_aligne: 'Aligned on the standard: [[v]]',
      ev_atteindre: 'Reaching it brings qualification.',
      ev_a_venir: 'upcoming',
      ev_session_prevue: 'Evaluation session',
      ev_session_tenue: 'Session held',
      rel_bas: 'target [[c]] · [[d]]',
      rel_a_mesurer: 'to be measured',
      rel_seuil: '“advanced” threshold',
      rel_norme: 'the standard',
      rel_zone: 'standard met',
      rel_franchie: 'standard reached',
      rel_tenues: 'steps met out of [[t]]',
      rel_tenues_1: 'step met out of [[t]]',
      rel_repris: 'cut since the start',
      rel_gagne: 'gained since the start',
      rel_suivi: 'days of follow-up',
      rel_suivi_1: 'day of follow-up',
      rel_detail: 'Session by session',
      rel_detail_off: 'Hide the detail',
      rel_aria: 'Progress relief for “[[x]]”: [[n]] measurements, standard [[v]]. Time along the bottom, value up the side — rising means progress.',
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
      rien_a_evaluer: 'This activity produces nothing on the map: no arrow leaves it. There is nothing to assess until it has an output.',
      conf_done_t: 'Activity configured',
      evidence_ph: 'Evidence / comment (optional)', add_evidence: '+ Add evidence',
      diagnose: 'Diagnose the gap',
      loading: 'Loading…',
      configured_go_eval: 'Outputs qualified ✓ — now set the team member’s level for each result, then save.',
      req_failed: 'Action failed (network or server error).',
      forbidden: 'You are not allowed to assess this team member.',
      pick_level: 'To assess', roles_label: "Team member's roles",
      self_assess: 'Self-assess',
      pas_configuree: 'This activity produces nothing on the map: no arrow leaves it. There is nothing to assess.',
      b_held: 'Level met', b_gap: 'Below target', b_todo: 'To assess', b_setup: 'No output',
      filter_off: 'Show all', no_match: 'No activity in this category.',
      m_result_one: 'result', m_result_many: 'results', m_partial: 'of',
      m_eval_one: 'assessed', m_eval_many: 'assessed',
      m_last: 'assessed on', m_never: 'never assessed', m_toqualify: 'no output on the map',
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
    rows: [], filtre: null, activity: null, lastState: null, devNom: '',
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
    state.devNom = ctx.dev ? ctx.dev.name : '';
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

  const ECRANS = ['#cv2-ecran-synthese', '#cv2-ecran-eval',
                  '#cv2-ecran-seance', '#cv2-ecran-cal'];

  function montrerVide(msg) {
    ECRANS.forEach(s => $(s).classList.add('hidden'));
    pleineLargeur(false);
    const ph = $('#cv2-placeholder'); ph.classList.remove('hidden'); ph.textContent = msg;
  }
  function montrerEcran(nom) {
    state.ecran = nom;
    $('#cv2-placeholder').classList.add('hidden');
    $('#cv2-ecran-synthese').classList.toggle('hidden', nom !== 'synthese');
    $('#cv2-ecran-eval').classList.toggle('hidden', nom !== 'eval');
    $('#cv2-ecran-seance').classList.toggle('hidden', nom !== 'seance');
    $('#cv2-ecran-cal').classList.toggle('hidden', nom !== 'cal');
    pleineLargeur(nom !== 'synthese');
  }

  // ⚠️ Une PAGE d'évaluation ne partage pas la largeur avec la barre des
  // collaborateurs ni avec le bandeau : les trois colonnes en ont besoin, et
  // le bandeau redirait le nom qu'on vient d'écrire en grand dans l'en-tête.
  function pleineLargeur(oui) {
    const l = document.querySelector('.cv2-layout');
    if (l) l.classList.toggle('hidden', oui);
    const b = document.querySelector('.page-banner');
    if (b) b.classList.toggle('hidden', oui);
    document.body.classList.toggle('a-cv2-page', oui);
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
    rendreSeances();
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
      // ⚠️ Sur la vue d'ensemble on les montre TOUS, même à zéro : trois
      // compteurs absents sur quatre laissaient la page nue, et « 0 en
      // écart » est une information, pas un vide.
      if (onFiltre && !compte[cle] && state.filtre !== cle) return;
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
  // Un rôle ouvre DIRECTEMENT son premier chantier : la liste seule ne
  // décidait de rien, et la colonne de gauche de la page la remplace.
  async function ouvrirRole(r) {
    state.roleId = r.role_id || r.id; state.roleName = r.role_name || r.name; state.filtre = null;
    const d = await api(`/mastery/dashboard/${state.cible}/${state.roleId}`);
    if (d.__error) return;
    state.rows = (d && d.activities) || [];
    if (!state.rows.length) { montrerVide(T('no_activities')); return; }
    // Celle qui appelle : le plus grand écart d'abord, sinon la première.
    const urgente = state.rows.find(a => categorie(a) === 'gap')
      || state.rows.find(a => categorie(a) === 'todo') || state.rows[0];
    await ouvrirEvaluation(urgente);
  }

  function renderDashboard(d, reutiliser) {
    if (!reutiliser) state.rows = (d && d.activities) || [];
    if (state.ecran === 'eval' && $('#ev-acts-l')) remplirActivites();
  }



  function chip(color, label) { return `<span class="chip ${esc(color)}"><span class="lv"></span>${esc(label)}</span>`; }
  const dash = () => `<span class="cv2-dash">${T('none')}</span>`;


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
    // ⚠️ Et un axe existe dès qu'il y a QUELQUE CHOSE à y porter — un requis
    // OU un démontré. Filtré sur le seul requis, le profil de quelqu'un dont
    // aucun rôle n'a fixé de cible restait VIDE, en affichant « le profil se
    // dessine à partir de trois activités » alors qu'il en avait trois.
    const axes = (d.profil || []).filter(a =>
      (!estNul(a.required_level) && a.required_level > 0) || !estNul(a.demonstrated_level));
    const horsGraphe = axes.filter(a => estNul(a.demonstrated_level)).length;
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
          ${vus.length < 3 ? `<div class="cv2-radar-note">${esc(T('p_profil_peu'))}</div>` : ''}
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
    const peutRegler = jeSuisLeDev();
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
      // ⚠️ Le niveau ATTENDU se règle ICI, pas dans la page d'évaluation :
      // c'est une décision de rôle, et là-bas elle se confondait avec la note
      // qu'on venait poser sur les sorties de l'activité.
      const regle = peutRegler ? `<span class="cv2-bar-req" data-act="${a.activity_id}">
          ${[0, 1, 2, 3, 4].map(lv => `<button type="button" class="cv2-bar-q${req === lv ? ' sel' : ''}"
             data-lv="${lv}" title="${esc(levelName(lv))}">${lv}</button>`).join('')}
          <button type="button" class="cv2-bar-q cv2-bar-q--off${req === null ? ' sel' : ''}"
             data-lv="" title="${esc(T('not_set'))}">—</button></span>` : '';
      return `<div class="cv2-bar-l" style="--i:${i}">
          <span class="cv2-bar-nom" title="${esc(a.activity_name)}">${esc(a.activity_name)}</span>
          <span class="cv2-bar-piste">${piste}${cible}</span>
          <span class="cv2-bar-val">${dem === null ? '—' : dem}<small>/${req === null ? '—' : req}</small></span>
          ${regle}
        </div>`;
    }).join('');

    return `<div class="cv2-barres">
        <div class="cv2-barres-tete">
          <button type="button" class="cv2-barres-retour">
            <i class="fa-solid fa-arrow-left"></i> ${esc(T('p_back_radar'))}</button>
          <div class="cv2-barres-t">${esc(role.role_name)}</div>
          ${peutRegler ? `<span class="cv2-barres-lg">${esc(T('p_regler_req'))}</span>` : ''}
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
    hote.querySelectorAll('.cv2-bar-req [data-lv]').forEach(b => b.onclick = async () => {
      const v = b.dataset.lv;
      const r = await api('/mastery/required', { method: 'POST', body: JSON.stringify({
        activity_id: +b.closest('[data-act]').dataset.act, role_id: role.role_id,
        required_mastery_level: v === '' ? null : +v }) });
      if (r.__error) return;
      toast(T('req_set'));
      // On recharge la synthèse ENTIÈRE : le niveau attendu décide de la
      // couleur, du compteur « en écart » et du radar — les redresser à la
      // main en JS donnerait une seconde règle pour un seul verdict.
      // ⚠️ `box` et `hote` sont DÉTACHÉS après ce rechargement : `renderProfil`
      // réécrit tout le bloc. On rouvre les barres sur la zone NEUVE.
      await chargerSynthese();
      const neuf = ((state.synthese && state.synthese.roles) || [])
        .find(x => x.role_id === role.role_id);
      const zone = $('#cv2-profil');
      if (neuf && zone) ouvrirBarres(zone, neuf);
    });
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
    // ⚠️ La même règle vaut pour le REQUIS : un axe sans cible ne se ferme
    // pas à zéro, sinon le contour dirait « rien n'est exigé ici » là où la
    // vérité est « personne n'a encore fixé d'exigence ».
    const couche = (cle, pleine, partielle) => {
      const tout = axes.every(a => !estNul(a[cle]) && (cle !== 'required_level' || a[cle] > 0));
      if (tout) {
        return `<polygon class="${pleine}" points="${poly(axes.map(a => a[cle]))}"></polygon>`;
      }
      const suites = [];
      let courante = [];
      axes.forEach((a, i) => {
        const v = a[cle];
        if (estNul(v) || (cle === 'required_level' && !(v > 0))) {
          if (courante.length > 1) suites.push(courante);
          courante = [];
        } else courante.push(pt(i, v));
      });
      if (courante.length > 1) suites.push(courante);
      return suites.map(p => `<polyline class="${partielle}"
          points="${p.map(c => c.map(x => x.toFixed(1)).join(',')).join(' ')}"></polyline>`).join('');
    };
    const coucheReq = couche('required_level', 'cv2-r-req', 'cv2-r-req-part');
    const coucheDem = couche('demonstrated_level', 'cv2-r-dem', 'cv2-r-dem-part');
    const points = axes.map((a, i) => {
      if (estNul(a.demonstrated_level)) return '';
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
        ${coucheReq}
        ${coucheDem}
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
      carte.innerHTML = `<div class="t">${esc(titre)}</div>
        <div class="d" style="white-space:pre-line">${esc(texte)}</div>`;
      document.body.appendChild(carte);
      // En `position: fixed` sur le body : la liste des activités a son propre
      // défilement, une carte posée dedans serait tronquée.
      const r = bouton.getBoundingClientRect(), b = carte.getBoundingClientRect();
      const z = parseFloat(getComputedStyle(document.body).zoom) || 1;
      const large = b.width * z;
      carte.style.left = Math.max(8, Math.min(r.left, window.innerWidth - large - 8)) / z + 'px';
      const dessus = r.top - b.height * z - 8;
      carte.style.top = (dessus > 8 ? dessus : r.bottom + 8) / z + 'px';
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

  // Le tiroir ne porte plus que les deux DIALOGUES courts : configurer une
  // activité, et diagnostiquer un écart. L'évaluation, elle, est une PAGE —
  // il lui faut une échelle de paliers, un graphe et un historique, et 576 px
  // réels n'y suffisaient pas.
  function ouvrirDialogue(titre, avecLaPersonne) {
    const d = $('#cv2-drawer');
    d.dataset.mode = 'eval';
    d.dataset.vue = 'eval';
    $('#cv2-drawer-title').textContent = titre;
    $('#cv2-drawer-role').innerHTML = avecLaPersonne
      ? `<span class="qui">${esc(state.cibleNom)}</span><span class="ou">${esc(state.roleName)}</span>`
      : '';
    d.classList.add('open'); $('#cv2-overlay').classList.add('open');
    $('#cv2-drawer-body').scrollTop = 0;
  }

  // Configurer une activité ne regarde PERSONNE : ni le collaborateur choisi, ni
  // son niveau. La fenêtre ne porte donc pas son nom — c'est le premier signe
  // qu'on a changé de sujet.
  function ouvrirConfiguration(row) {
    state.activity = row;
    const d = $('#cv2-drawer');
    d.dataset.mode = 'config';
    d.dataset.vue = 'eval';
    $('#cv2-drawer-title').textContent = T('conf_title');
    $('#cv2-drawer-role').innerHTML = `<span class="qui">${esc(row.activity_name)}</span>`;
    d.classList.add('open'); $('#cv2-overlay').classList.add('open');
    $('#cv2-drawer-body').scrollTop = 0;
    showQualify();
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


  // `demonstrated_level` porte DÉJÀ le niveau déduit d'une sortie mesurée
  // (`activity_mastery` l'écrase avec `etat_sortie`) : un palier manqué entre
  // donc dans l'écart sans traitement à part.
  function aUnEcart(st) {
    const req = st.required_level;
    return (st.results || []).some(r => !estNul(r.demonstrated_level)
      && (r.demonstrated_level < 2 || (!estNul(req) && r.demonstrated_level < req)));
  }

  // ── Le niveau requis ──────────────────────────────────────────────
  // ⚠️ C'était un lien « modifier » qui dépliait six boutons gris : rien ne
  // disait que c'était réglable, ni qu'il s'agissait d'une CIBLE.
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
          <span class="cv2-nt-ico"><i class="fa-solid ${o.genre === 'off' ? 'fa-shield-halved' : 'fa-user'}"></i></span>
          <div class="cv2-nt-qui">
            <span class="cv2-nt-lbl">${esc(o.titre)}</span>
            ${o.tag ? `<span class="cv2-nt-tag">${esc(o.tag)}</span>` : ''}
          </div>
          <span class="cv2-nt-val">${valeur}</span>
        </div>
        <div class="cv2-echelle">${paliers}
          ${o.modifiable ? `<button type="button" class="cv2-gomme${estNul(o.niveau) ? ' sel' : ''}" data-lv="">
             <i class="fa-solid fa-eraser"></i>${esc(T('erase'))}</button>` : ''}
        </div>
        ${o.accord || ''}
      </div>`;
  }

  // Une sortie porte une NORME chiffrée, ou elle n'en porte pas. C'est le seul
  // critère, et il décide de tout ce qui suit : l'échelle des paliers d'un
  // côté, la note 0→4 à la main de l'autre.
  function carteSortie(r, requis) {
    return (r.mesurable && r.performance) ? carteMesuree(r) : resultCard(r, requis);
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
      <div class="cv2-notes">${officielle}${auto}</div>
      <button type="button" class="cv2-preuve-btn${preuve ? ' hidden' : ''}">
        <span class="ic"><i class="fa-solid fa-paperclip"></i></span>${esc(T('add_evidence'))}</button>
      <textarea class="cv2-ev${preuve ? '' : ' hidden'}" placeholder="${esc(T('evidence_ph'))}">${esc(preuve)}</textarea>
      ${dev ? `<div class="cv2-vers-pal">
          <div class="t"><i class="fa-solid fa-ruler"></i>
            <span>${esc(T('pal_sans_norme'))}</span></div>
          <p class="d">${esc(T('pal_sans_norme_d'))}</p>
          <button type="button" class="pal-b pal-b--doux" data-poser-norme>
            <span class="pal-b-ic"><i class="fa-solid fa-bullseye"></i></span>${esc(T('pal_definir_norme'))}</button>
        </div>
        <div class="pal-form hidden"></div>` : ''}`;

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
    // ⚠️ C'est la PREMIÈRE MESURE qui s'ouvre, pas la seule norme : poser la
    // norme bascule la sortie en régime mesuré, et la note à la main qu'on
    // lit juste au-dessus cesse alors d'être saisissable. Les deux se
    // décident donc dans le même geste.
    const bn = card.querySelector('[data-poser-norme]');
    if (bn) bn.onclick = () => formPremiere(card.querySelector('.pal-form'), r);
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

  // ⚠️⚠️ Il cherchait ses cartes dans `#cv2-drawer-body` — le TIROIR, d'où
  // l'évaluation est partie le 14/10. Il n'en trouvait donc aucune, la boucle
  // ne tournait pas, et le « Enregistré » tombait quand même : on notait, on
  // validait, et rien n'était écrit. Un enregistrement qui ne trouve rien à
  // écrire n'annonce plus un succès.
  async function saveEvaluation() {
    const cards = document.querySelectorAll('#ev-centre .cv2-res');
    if (!cards.length) { toast(T('save_rien')); return; }
    const btn = $('#cv2-save-btn'); if (btn) btn.disabled = true;
    let ecrites = 0;
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
      ecrites += 1;
    }
    toast(ecrites ? T('saved') : T('save_rien'));
    if (!ecrites) { if (btn) btn.disabled = false; return; }
    await refreshDashboard();
    await ouvrirEvaluation(state.activity);
  }

  async function setRequired(lvl) {
    const r = await api('/mastery/required', {
      method: 'POST',
      body: JSON.stringify({
        activity_id: state.activity.activity_id, role_id: state.roleId, required_mastery_level: lvl }),
    });
    if (r.__error) return;
    toast(T('req_set'));
    await refreshDashboard();
    await ouvrirEvaluation(state.activity);
  }

  async function refreshDashboard() {
    const d = await api(`/mastery/dashboard/${state.cible}/${state.roleId}`);
    if (d && d.activities) {
      renderDashboard(d);
      const row = d.activities.find(a => a.activity_id === (state.activity || {}).activity_id);
      if (row) state.activity = row;
      // La colonne de gauche de la page porte les niveaux : trancher un
      // palier sans la rafraîchir laisserait l'ancien juste à côté du neuf.
      if (state.ecran === 'eval' && $('#ev-acts-l')) remplirActivites();
    }
  }

  // ══ Technicité — axe SÉPARÉ de la maîtrise (CDC 4) ═════════════════
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
      { cls: 'btn-primary', label: T('conf_done_go'), on: () => ouvrirEvaluation(state.activity) },
    ]);
  }

  // ══ Diagnostic de l'écart (CDC 6.5-6.9) ════════════════════════════
  async function showDiagnostic() {
    ouvrirDialogue(state.activity.activity_name, true);
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
    setFooter([{ cls: 'btn-quiet', label: T('back'), on: closeDrawer }]);
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

  // ══ LES PALIERS DE PERFORMANCE ═════════════════════════════════════
  // Une sortie MESURABLE ne se note pas à la main : on lui pose des marches
  // — 96 h sous 30 jours, puis 72 h, puis la norme — et le niveau 0→4 se
  // DÉDUIT du chiffre relevé en session (Code/paliers.py).
  //
  // ⚠️ Les deux régimes cohabitent dans la même fenêtre, et c'est voulu :
  // « Cahier des charges validé » n'a pas de durée, il garde son échelle 0→4.
  // Ce qui les distingue à l'écran, c'est la NORME — présente ou absente.

  const SENS_MOINS = 'moins';
  const mieux = (a, b, sens) => (sens === SENS_MOINS ? a <= b : a >= b);

  // Un nombre se lit sans sa queue décimale inutile : « 48 h », pas « 48.0 h ».
  function fmtNb(v) {
    if (estNul(v)) return '—';
    const n = Math.round(v * 100) / 100;
    return String(n % 1 === 0 ? n : n.toFixed(2).replace(/0$/, ''));
  }
  function fmtVal(v, unite) {
    if (estNul(v)) return '—';
    return fmtNb(v) + (unite ? ' ' + unite : '');
  }
  function jourISO(d) {
    const z = n => (n < 10 ? '0' : '') + n;
    return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate());
  }
  // ⚠️ Une date du serveur est un JOUR (`date_prevue` est un DATE, pas un
  // horodatage) : `new Date('2026-04-17')` le lit en UTC et recule d'un jour
  // à l'ouest de Greenwich. On découpe la chaîne.
  function dateJour(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function ecartJours(iso) {
    const d = dateJour(iso); if (!d) return null;
    const a = new Date(); a.setHours(0, 0, 0, 0);
    return Math.round((d - a) / 86400000);
  }
  function quandDit(iso) {
    const n = ecartJours(iso);
    if (n === null) return '';
    if (n === 0) return T('ses_aujourdhui');
    if (n === 1) return T('ses_demain');
    if (n > 1) return Tv('ses_dans', { n: n });
    return Tv('ses_passe', { n: -n });
  }

  // ⚠️ L'« au-delà » est un pas de plus que la norme — et ce pas peut tomber
  // HORS de ce que la grandeur permet : une norme de 2 jours avec un pas de
  // 4 donne « −2 j », un taux de 100 % donne « 120 % ». On ne l'affiche pas
  // alors, et on n'invente pas non plus un autre seuil pour le remplacer :
  // la marge est celle que le développeur a posée, ou il n'y en a pas.
  // C'est un garde-fou d'AFFICHAGE — le niveau, lui, reste celui du serveur.
  function plausible(v, sens, unite) {
    if (!isFinite(v)) return false;
    if (sens === SENS_MOINS) return v > 0;
    return !/%/.test(unite || '') || v <= 100;
  }

  // ── Le rail : les marches, la norme, et l'au-delà ─────────────────
  // ⚠️ La norme n'est PAS une marche de plus : c'est l'arrivée. Quand aucun
  // palier ne l'atteint encore, on la dessine quand même — sinon on ne voit
  // pas où mène la progression. Et l'« au-delà » n'existe que s'il y a un pas
  // de progression connu : on n'invente pas un seuil pour pouvoir en montrer
  // un (même règle que `pas_de_progression`, côté serveur).
  function construireRail(perf) {
    const n = perf.norme || {}, sens = n.sens || SENS_MOINS;
    const au = estNul(perf.au_dela) ? null : perf.au_dela;
    // ⚠️ UN SEUL drapeau de norme. `mieux()` répond « atteint », donc toute
    // marche À PARTIR de la norme le portait : sur 67 → 81 → 95 → 98, deux
    // marches s'annonçaient « norme de l'entreprise ». La norme est un
    // passage, pas une zone — c'est la PREMIÈRE marche qui l'atteint.
    let norme_vue = false;
    const rail = (perf.paliers || []).map(p => {
      const atteintNorme = mieux(p.cible, n.valeur, sens);
      const estNorme = atteintNorme && !norme_vue;
      if (atteintNorme) norme_vue = true;
      return {
        id: p.id, cible: p.cible, statut: p.statut, mesure: p.mesure,
        quand: p.evalue_le, echeance: p.echeance, estNorme: estNorme,
        // La marche POSÉE au-delà porte sa propre marque : c'est elle qui
        // fait passer à « avancé », et elle doit se distinguer de la norme.
        estAuDela: au !== null && mieux(p.cible, au, sens) && !estNorme,
      };
    });
    if (!norme_vue) {
      rail.push({ cible: n.valeur, statut: 'cible', estNorme: true, fantome: true });
    }
    // Le seuil d'au-delà ne se dessine que si AUCUNE marche ne l'occupe déjà :
    // sinon on doublait la marche réelle d'un fantôme à la même valeur.
    const deja = rail.some(x => x.estAuDela);
    if (au !== null && !deja && plausible(au, sens, n.unite)) {
      // ⚠️ Cette marche se REMPLIT quand la dernière mesure la dépasse. Elle
      // restait creuse alors que la pastille annonçait « avancé » : la carte
      // disait une chose, son échelle en disait une autre juste en dessous.
      const franchie = !estNul(perf.mesure) && mieux(perf.mesure, au, sens);
      rail.push({ cible: au, statut: franchie ? 'atteint' : 'audela', estAuDela: true,
                  mesure: franchie ? perf.mesure : null,
                  quand: franchie ? perf.mesure_le : null, fantome: true });
    }
    return rail;
  }

  function railHtml(perf) {
    const u = (perf.norme || {}).unite || '';
    const rail = construireRail(perf);
    const atteintAvant = i => i > 0 && rail[i - 1].statut === 'atteint';
    let html = '<div class="pal-rail">';
    rail.forEach((s, i) => {
      const dernier = i === rail.length - 1;
      const plein = s.statut === 'atteint';
      const gauche = i === 0 ? 'vide' : (atteintAvant(i) ? 'ok' : 'tirets');
      const droite = dernier ? 'vide' : (plein ? 'ok' : 'tirets');
      let ico = '', sous = '';
      if (plein) ico = '<i class="fa-solid fa-check"></i>';
      else if (s.statut === 'manque') ico = '<i class="fa-solid fa-xmark"></i>';
      if (s.statut === 'atteint' || s.statut === 'manque') {
        // ⚠️ La CIBLE dit ce qu'on visait ; la MESURE dit ce qui a été fait.
        // C'est elle qu'on vient lire, et elle était en 12,5 px gris sous la
        // cible en 19 px — on ne la voyait pas. Même rang visuel désormais :
        // une pastille à la couleur du verdict, le chiffre en gras.
        sous = `<p class="pal-m"><span class="k">${esc(T('pal_mesure_k'))}</span>`
          + `<b>${esc(fmtVal(s.mesure, u))}</b></p>`
          + `<p class="pal-q">${esc(fmtDate(s.quand))}</p>`;
      } else if (s.statut === 'en_cours') {
        const n = ecartJours(s.echeance);
        sous = s.echeance
          ? `<p class="pal-ech${n !== null && n < 0 ? ' est-tard' : ''}">
               <i class="fa-regular fa-clock"></i>${esc(Tv('pal_echeance', { d: fmtDate(s.echeance) }))}</p>
             <p class="pal-q">${esc(quandDit(s.echeance))}</p>`
          : '';
      } else if (s.statut === 'audela') {
        sous = `<p class="pal-q">${esc(T('pal_audela_d'))}</p>`;
      }
      const mot = { atteint: 'pal_atteint', manque: 'pal_manque', en_cours: 'pal_encours',
                    audela: 'pal_audela', cible: 'pal_cible' }[s.statut];
      // ⚠️ Le drapeau vit dans une bande de HAUTEUR FIXE, drapeau ou pas :
      // posé en `inline-block` avec sa marge, il descendait sa marche de 5 px
      // et le rail n'était plus une ligne — il « cassait » à chaque drapeau.
      const marque = s.estNorme
        ? `<span class="pal-drapeau">${esc(T('pal_norme_tag'))}</span>`
        : (s.estAuDela ? `<span class="pal-drapeau pal-drapeau--au">${esc(T('pal_audela_tag'))}</span>` : '');
      html += `<div class="pal-pas pal-pas--${s.statut}${s.estAuDela ? ' est-audela' : ''}">
          <div class="pal-marque">${marque}</div>
          <div class="pal-ligne">
            <span class="pal-fil pal-fil--${gauche}"></span>
            <span class="pal-dot">${ico}</span>
            <span class="pal-fil pal-fil--${droite}"></span>
          </div>
          <p class="pal-v">${esc(fmtVal(s.cible, u))}</p>
          <p class="pal-s">${esc(T(mot))}</p>
          ${sous}
        </div>`;
    });
    return html + '</div>';
  }

  // ══ LE RELIEF ══════════════════════════════════════════════════════
  // Le rail posait les marches côte à côte, TOUTES À LA MÊME HAUTEUR : on n'y
  // voyait pas que le niveau monte. Le relief les porte sur deux axes réels.
  //  · en abscisse le TEMPS : l'écart entre deux séances se voit, donc un
  //    ralentissement se voit — « on a mis plus longtemps à reprendre moins ».
  //  · en ordonnée la valeur ORDONNÉE PAR MÉRITE : une durée compte à
  //    rebours, un taux à l'endroit. Dans les deux cas MONTER = PROGRESSER,
  //    et ce sont les étiquettes de l'échelle qui portent l'unité réelle.
  // ⚠️ Le tracé est DROIT entre deux mesures : rien n'a été relevé entre les
  // deux, une courbe lissée inventerait ce qu'on ne sait pas. Ce qui n'est
  // pas encore mesuré est en pointillé, vers un anneau creux.

  // Le cadre horizontal ne bouge jamais ; la HAUTEUR, si — une sortie sans
  // mesure n'a pas de quoi remplir trois cents pixels (voir `G` plus bas).
  const RL = { X0: 62, X1: 812, PX0: 162, PX1: 762, YT: 20 };
  // ⚠️ Un SVG n'hérite PAS des polices de la feuille : `font-family` doit être
  // écrit sur chaque texte. Les grands chiffres sont en Fraunces — c'est la
  // police d'affichage du design system — et leur unité en DM Sans.
  const FD = 'Fraunces, Georgia, serif';
  const FT = 'DM Sans, system-ui, sans-serif';

  // Une boîte de texte ESTIMÉE : rien n'est dans le document pendant qu'on
  // construit le SVG, donc rien à mesurer. Les facteurs sont ceux de DM Sans
  // (0,55 em) et de Fraunces en chiffres (0,62 em), relevés au banc avec
  // `getBBox()` — l'estimation sert à placer, la mesure à vérifier.
  function boiteTexte(x, yb, texte, px, ancre, fac) {
    const w = String(texte === null || texte === undefined ? '' : texte).length
      * px * (fac || 0.55);
    const x1 = ancre === 'middle' ? x - w / 2 : (ancre === 'end' ? x - w : x);
    return { x1: x1, x2: x1 + w, y1: yb - px * 0.78, y2: yb + px * 0.24 };
  }

  // ⚠️ L'ORDRE DE POSE EST LA DÉCISION : quand la place manque, ce qui
  // disparaît est la décoration — la trame, les mentions de zone — jamais le
  // chiffre relevé. On pose donc d'abord la dernière mesure, et en dernier
  // tout ce qui ne fait que commenter.
  // ⚠️ Les boîtes sont ESTIMÉES : on les teste donc avec une marge, sinon
  // deux étiquettes que le calcul croit voisines se touchent vraiment au
  // rendu. Mesuré au banc sur une carto chargée : « 8 essais » et
  // « 9,2 essais » se recouvraient de 1,7 px alors que le placeur avait dit
  // non-collision.
  const MARGE_X = 3, MARGE_Y = 2;
  // ⚠️ L'écart minimal tient les étiquettes entre elles, pas contre les BORDS :
  // « target 2 j · to be measured », centré sur la dernière marche, sortait
  // 19 px à droite du cadre — donc coupé. De combien faut-il la glisser vers
  // l'intérieur pour qu'elle y rentre ?
  function glisser(b) {
    if (b.x1 < 4) return 4 - b.x1;
    if (b.x2 > 824) return 824 - b.x2;
    return 0;
  }
  const bouger = (b, dx) => ({ x1: b.x1 + dx, x2: b.x2 + dx, y1: b.y1, y2: b.y2 });
  function placeur() {
    const prises = [];
    const cogne = b => prises.some(o =>
      !(b.x2 + MARGE_X <= o.x1 || b.x1 - MARGE_X >= o.x2
        || b.y2 + MARGE_Y <= o.y1 || b.y1 - MARGE_Y >= o.y2));
    return {
      libre: b => !cogne(b),
      poser: b => { if (cogne(b)) return false; prises.push(b); return true; },
      forcer: b => { prises.push(b); return true; },
    };
  }

  function reliefSvg(r) {
    const perf = r.performance || {}, n = perf.norme || {};
    const sens = n.sens || SENS_MOINS, u = n.unite || '';
    const rail = construireRail(perf);
    if (!rail.length) return '';

    // Un fantôme (la norme qu'aucune marche n'atteint, le seuil d'au-delà)
    // n'est PAS une mesure : il ne porte ni point ni chiffre sur le tracé.
    const estMes = s => !s.fantome && !estNul(s.mesure) && isFinite(s.mesure);
    const mes = [];
    rail.forEach((s, i) => { if (estMes(s)) mes.push(i); });

    // ⚠️ Sans la moindre mesure, il n'y a RIEN à tracer : le relief plein
    // laissait 300 px de vide sous une norme et une cible. On le raccourcit
    // alors à l'échelle qui porte ce qui existe — la norme, et les marches
    // qui attendent leur séance.
    const G = mes.length
      ? { H: 300, YH: 64, YB: 210, YAXE: 228, BAS1: 268, BAS2: 286 }
      : { H: 198, YH: 52, YB: 118, YAXE: 134, BAS1: 170, BAS2: 188 };

    // ── L'échelle couvre tout ce qui sera dessiné, norme comprise ──
    const merite = v => (sens === SENS_MOINS ? -v : v);
    const vals = [];
    const garde = v => { if (!estNul(v) && isFinite(v)) vals.push(v); };
    rail.forEach(s => { garde(s.cible); garde(s.mesure); });
    garde(n.valeur);
    if (!vals.length) return '';
    let mmin = Math.min.apply(null, vals.map(merite));
    let mmax = Math.max.apply(null, vals.map(merite));
    const pad = (mmax - mmin) * 0.08 || Math.max(Math.abs(mmax) * 0.2, 1);
    mmin -= pad; mmax += pad;
    const y = v => G.YB - ((merite(v) - mmin) / (mmax - mmin)) * (G.YB - G.YH);
    const vDe = m => (sens === SENS_MOINS ? -m : m);

    // ── La gouttière de gauche s'ajuste à ce qu'on doit y écrire ──
    // ⚠️ Une unité longue déborde du cadre : mesuré au banc, « 14.4 essais »
    // sortait 24 px à GAUCHE du viewBox, donc invisible. La largeur de la
    // gouttière vient des étiquettes elles-mêmes, pas d'une constante.
    const reperes = [mmin + pad, (mmin + mmax) / 2, mmax - pad].map(vDe);
    let gut = 0;
    reperes.forEach(v => {
      gut = Math.max(gut, boiteTexte(0, 0, fmtVal(v, u), 11, 'start', 0.6).x2);
    });
    if (!estNul(n.valeur)) {
      gut = Math.max(gut, boiteTexte(0, 0, fmtVal(n.valeur, u), 13, 'start', 0.62).x2);
    }
    G.X0 = Math.max(62, Math.round(gut) + 16);
    G.PX0 = Math.max(RL.PX0, G.X0 + 100);

    // ── Le temps : la date d'une marche, c'est sa mesure ou son échéance ──
    // ⚠️ Un FANTÔME n'a pas de date de son côté. `construireRail` recopie la
    // dernière mesure sur le seuil d'au-delà pour que le rail le montre
    // franchi — dans le relief, cette copie dessinait un SECOND point au même
    // relevé, à une date où personne n'a rien mesuré, et le tracé partait à
    // plat vers la droite. Mesuré au banc : deux « 0,8 % » sur trois séances.
    const dateDe = s => (s.fantome ? (s.echeance || null) : (s.quand || s.echeance || null));
    const jourDe = d => Math.round(d.getTime() / 86400000);
    const N = rail.length;
    const dts = rail.map(s => dateJour(dateDe(s)));
    const jours = dts.map(d => (d ? jourDe(d) : null));
    const connus = jours.map((j, i) => (j === null ? -1 : i)).filter(i => i >= 0);
    if (!connus.length) {
      for (let i = 0; i < N; i++) jours[i] = i * 14;
    } else {
      const pr = connus[0], dr = connus[connus.length - 1];
      // Une queue sans date se prolonge du pas MOYEN : la coller sur sa
      // voisine ferait croire à deux séances le même jour.
      const pas = dr > pr
        ? Math.max(1, Math.round((jours[dr] - jours[pr]) / (dr - pr))) : 14;
      for (let k = 0; k < connus.length - 1; k++) {
        const a = connus[k], b = connus[k + 1];
        for (let i = a + 1; i < b; i++) {
          jours[i] = jours[a] + ((jours[b] - jours[a]) * (i - a)) / (b - a);
        }
      }
      for (let i = pr - 1; i >= 0; i--) jours[i] = jours[i + 1] - pas;
      for (let i = dr + 1; i < N; i++) jours[i] = jours[i - 1] + pas;
    }
    // ⚠️ La progression est une ÉCHELLE : les marches gardent leur ordre de
    // rang même si une date a été saisie à l'envers — un tracé qui revient
    // en arrière ne se lit pas.
    for (let i = 1; i < N; i++) jours[i] = Math.max(jours[i], jours[i - 1]);

    // ── Le mode d'étiquetage se choisit sur la place DISPONIBLE ──
    // « cible 10 j · 11/09 » fait ~108 px à 11,5 px : au-delà de six marches
    // il faut deux rangées, puis la date seule, puis une étiquette sur deux.
    const LARG = RL.PX1 - G.PX0;
    const MODES = [{ bas: 'plein', min: 118, deux: false },
                   { bas: 'plein', min: 62, deux: true },
                   { bas: 'date', min: 44, deux: true },
                   { bas: 'rare', min: 26, deux: false }];
    let mode = MODES[MODES.length - 1];
    for (let k = 0; k < MODES.length; k++) {
      if ((N - 1) * MODES[k].min <= LARG) { mode = MODES[k]; break; }
    }
    const MIN = mode.min, tient = (N - 1) * MIN <= LARG;

    const xs = [];
    const j0 = jours[0], jn = jours[N - 1];
    if (N === 1) xs.push((G.PX0 + RL.PX1) / 2);
    else if (!tient || jn === j0) {
      for (let i = 0; i < N; i++) xs.push(G.PX0 + (LARG * i) / (N - 1));
    } else {
      for (let i = 0; i < N; i++) xs.push(G.PX0 + (LARG * (jours[i] - j0)) / (jn - j0));
      // Écarter : deux passes suffisent, la contrainte étant une chaîne
      // d'intervalles — en avant pour imposer l'écart, en arrière pour
      // rentrer dans le cadre.
      for (let i = 1; i < N; i++) xs[i] = Math.max(xs[i], xs[i - 1] + MIN);
      if (xs[N - 1] > RL.PX1) {
        xs[N - 1] = RL.PX1;
        for (let i = N - 2; i >= 0; i--) xs[i] = Math.min(xs[i], xs[i + 1] - MIN);
        if (xs[0] < G.PX0) {
          const d = G.PX0 - xs[0];
          for (let i = 0; i < N; i++) xs[i] = Math.min(xs[i] + d, RL.PX1);
        }
      }
    }
    let dmin = Infinity;
    for (let i = 1; i < N; i++) dmin = Math.min(dmin, xs[i] - xs[i - 1]);
    if (!isFinite(dmin)) dmin = LARG;

    // La règle des mois passe par les COUPLES (jour, x) réellement posés :
    // après un écartement l'abscisse n'est plus linéaire dans le temps, et
    // une graduation calculée sur le temps brut mentirait.
    const xDuJour = j => {
      if (j <= jours[0]) return xs[0];
      for (let i = 1; i < N; i++) {
        if (j <= jours[i]) {
          const d = jours[i] - jours[i - 1];
          return d ? xs[i - 1] + ((xs[i] - xs[i - 1]) * (j - jours[i - 1])) / d : xs[i];
        }
      }
      return xs[N - 1];
    };

    const P = placeur();
    const fond = [], trace = [], marques = [], txt = [];
    const yN = estNul(n.valeur) ? null : y(n.valeur);

    // ── La zone tenue, et la trame ──
    if (yN !== null && yN > RL.YT + 4) {
      fond.push('<rect x="' + G.X0 + '" y="' + RL.YT + '" width="' + (RL.X1 - G.X0)
        + '" height="' + (yN - RL.YT).toFixed(1) + '" fill="#11835e" fill-opacity=".038"></rect>');
    }

    // ── Les mesures : le tracé plein, et sa masse neutre ──
    // ⚠️ C'est le FIL qui porte la couleur : une masse teintée ferait deux
    // signaux pour une seule information.
    const co = mes.map(i => [xs[i], y(rail[i].mesure)]);

    // Le fil ne change de teinte QU'UNE FOIS, et exactement là où il coupe la
    // norme — pas au point suivant. C'est le dégradé qui le place, au pixel.
    let off = null;
    if (yN !== null && mes.length) {
      if (mieux(rail[mes[0]].mesure, n.valeur, sens)) off = 0;
      else {
        for (let k = 1; k < mes.length; k++) {
          const a = rail[mes[k - 1]].mesure, b = rail[mes[k]].mesure;
          if (!mieux(a, n.valeur, sens) && mieux(b, n.valeur, sens) && b !== a) {
            const t = (n.valeur - a) / (b - a);
            const xc = co[k - 1][0] + (co[k][0] - co[k - 1][0]) * t;
            const tot = co[co.length - 1][0] - co[0][0];
            off = tot > 0 ? (xc - co[0][0]) / tot : 0;
            break;
          }
        }
      }
    }
    const gid = 'rl-fil-' + (r.data_id || 0);
    let stops = '<stop offset="0" stop-color="#a9bbd4"></stop>'
      + '<stop offset=".5" stop-color="#7aa7e8"></stop>'
      + '<stop offset="1" stop-color="#2f6fd0"></stop>';
    if (off !== null) {
      const o = Math.max(0.02, Math.min(0.98, off));
      stops = '<stop offset="0" stop-color="#a9bbd4"></stop>'
        + '<stop offset="' + (o * 0.55).toFixed(3) + '" stop-color="#7aa7e8"></stop>'
        + '<stop offset="' + (o - 0.012).toFixed(3) + '" stop-color="#2f6fd0"></stop>'
        + '<stop offset="' + o.toFixed(3) + '" stop-color="#11835e"></stop>'
        + '<stop offset="1" stop-color="#11835e"></stop>';
    }
    const defs = '<defs>'
      + '<linearGradient id="' + gid + '" gradientUnits="userSpaceOnUse" x1="'
      + (co.length ? co[0][0].toFixed(1) : 0) + '" y1="0" x2="'
      + (co.length ? co[co.length - 1][0].toFixed(1) : 1) + '" y2="0">' + stops + '</linearGradient>'
      + '<linearGradient id="' + gid + '-m" x1="0" y1="0" x2="0" y2="1">'
      + '<stop offset="0" stop-color="#475467" stop-opacity=".09"></stop>'
      + '<stop offset="1" stop-color="#475467" stop-opacity="0"></stop>'
      + '</linearGradient></defs>';

    if (co.length > 1) {
      const d = co.map(c => c[0].toFixed(1) + ' ' + c[1].toFixed(1)).join(' L ');
      trace.push('<path d="M ' + d + ' L ' + co[co.length - 1][0].toFixed(1) + ' '
        + G.YAXE + ' L ' + co[0][0].toFixed(1) + ' ' + G.YAXE
        + ' Z" fill="url(#' + gid + '-m)"></path>');
      trace.push('<polyline points="'
        + co.map(c => c[0].toFixed(1) + ',' + c[1].toFixed(1)).join(' ')
        + '" fill="none" stroke="url(#' + gid + ')" stroke-width="2.5"'
        + ' stroke-linejoin="round" stroke-linecap="round"></polyline>');
    }
    // Ce qui reste à faire : pointillé jusqu'à la première marche non mesurée.
    if (co.length) {
      const suite = rail.findIndex((s, i) => estNul(s.mesure) && i > mes[mes.length - 1]);
      if (suite > 0) {
        trace.push('<path d="M ' + co[co.length - 1][0].toFixed(1) + ' '
          + co[co.length - 1][1].toFixed(1) + ' L ' + xs[suite].toFixed(1) + ' '
          + y(rail[suite].cible).toFixed(1) + '" fill="none" stroke="#0a5540"'
          + ' stroke-width="2" stroke-dasharray="2 5" stroke-linecap="round" opacity=".5"></path>');
      }
    }

    // ── Les pastilles ──
    const dernierMes = mes.length ? mes[mes.length - 1] : -1;
    rail.forEach((s, i) => {
      const mesuree = estMes(s);
      const cy = mesuree ? y(s.mesure) : y(s.cible);
      if (!isFinite(cy)) return;
      const cx = xs[i];
      if (!mesuree) {
        // Un seuil DÉJÀ franchi se remplit : laissé creux, l'échelle disait
        // le contraire de la pastille « qualifié · avancé » juste au-dessus.
        const franchi = s.statut === 'atteint';
        marques.push('<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1)
          + '" r="6" fill="' + (franchi ? '#11835e' : '#fff') + '" stroke="#0a5540"'
          + ' stroke-width="2"' + (franchi ? '' : ' stroke-dasharray="2.6 2.4"')
          + '></circle>');
        return;
      }
      const atteintNorme = yN !== null && mieux(s.mesure, n.valeur, sens);
      const col = s.statut === 'manque' ? '#a5192f'
        : (atteintNorme ? '#11835e' : (i === mes[0] ? '#a9bbd4' : '#7aa7e8'));
      const creux = s.statut !== 'manque' && !atteintNorme && i === mes[0];
      if (i === dernierMes) {
        marques.push('<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1)
          + '" r="15" fill="' + col + '" fill-opacity=".1"></circle>');
      }
      marques.push('<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1)
        + '" r="' + (i === dernierMes ? 6 : 5) + '" fill="' + (creux ? '#fff' : col)
        + '" stroke="' + col + '" stroke-width="2.5"></circle>');
    });

    // ── LES ÉTIQUETTES, par ordre de priorité ──
    // 1 · la norme sur l'axe : c'est la référence de tout le graphe.
    if (yN !== null) {
      const tn = fmtVal(n.valeur, u);
      P.forcer(boiteTexte(G.X0 - 14, yN + 4, tn, 13, 'end', 0.62));
      fond.push('<line x1="' + G.X0 + '" y1="' + yN.toFixed(1) + '" x2="' + RL.X1
        + '" y2="' + yN.toFixed(1) + '" stroke="#101828" stroke-width="1.5"'
        + ' stroke-opacity=".34"></line>');
      txt.push('<text x="' + (G.X0 - 14) + '" y="' + (yN + 4).toFixed(1)
        + '" text-anchor="end" font-family="' + FD + '" font-size="13" font-weight="600"'
        + ' fill="#101828">' + esc(tn) + '</text>');
    }

    // 2 · les mesures, la DERNIÈRE d'abord — c'est le niveau actuel.
    let fv = dmin >= 100 ? 26 : dmin >= 78 ? 22 : dmin >= 60 ? 18 : 15;
    const ordre = mes.slice().reverse();
    const posees = {};
    for (let essai = 0; essai < 3; essai++) {
      const vu = placeur();
      let ok = true;
      ordre.forEach(i => {
        const t = fmtVal(rail[i].mesure, u);
        const px = i === dernierMes ? fv + 4 : fv;
        const haut = y(rail[i].mesure) - 19;
        const bas = y(rail[i].mesure) + 30;
        // Au-dessus par défaut ; en dessous quand le haut du cadre manque, ou
        // quand la place est prise — on ne jette jamais le chiffre relevé.
        let yb = haut - px * 0.78 >= RL.YT - 14 ? haut : bas;
        let b = boiteTexte(xs[i], yb, t, px, 'middle', 0.62);
        if (!vu.libre(b) && bas + px * 0.24 < G.YAXE - 6) {
          yb = yb === haut ? bas : haut;
          b = boiteTexte(xs[i], yb, t, px, 'middle', 0.62);
        }
        if (!vu.libre(b)) { ok = false; }
        vu.forcer(b);
        posees[i] = { t: t, px: px, yb: yb, b: b };
      });
      if (ok || fv <= 15) break;
      fv -= 4;
    }
    ordre.forEach(i => {
      const o = posees[i];
      if (!o) return;
      const s = rail[i];
      const atteintNorme = yN !== null && mieux(s.mesure, n.valeur, sens);
      const col = s.statut === 'manque' ? '#a5192f'
        : (atteintNorme ? '#11835e' : (i === mes[0] ? '#475467' : '#2f6fd0'));
      const colU = s.statut === 'manque' ? '#c08490'
        : (atteintNorme ? '#6e9b8b' : (i === mes[0] ? '#98a2b3' : '#8aa6cf'));
      const m = /^(.*?)(\s+\S+)$/.exec(o.t);
      const nb = m ? m[1] : o.t, un = m ? m[2].trim() : '';
      P.forcer(o.b);
      txt.push('<text x="' + xs[i].toFixed(1) + '" y="' + o.yb.toFixed(1)
        + '" text-anchor="middle" font-family="' + FD + '" font-size="' + o.px
        + '" font-weight="600" fill="' + col + '">' + esc(nb)
        + (un ? '<tspan font-family="' + FT + '" font-size="'
            + Math.round(o.px * 0.46) + '" font-weight="500" fill="' + colU
            + '" dx="3">' + esc(un) + '</tspan>' : '') + '</text>');
    });

    // 3 · ce que chaque marche visait, et quand — sous l'axe du temps.
    const basTexte = (s, court) => {
      // Le seuil d'au-delà n'est pas une marche posée : il n'a pas de date, et
      // écrire « cible X · à mesurer » laisserait croire qu'une séance
      // l'attend. Il dit ce qu'il est — la frontière de « avancé ».
      if (s.fantome && s.estAuDela) return T('rel_seuil');
      const d = dateDe(s);
      const quand = d ? fmtDate(d) : T('rel_a_mesurer');
      return (court || mode.bas === 'date') ? quand
        : Tv('rel_bas', { c: fmtVal(s.cible, u), d: quand });
    };
    // ⚠️ L'ordre de POSE n'est pas l'ordre des marches : quand deux étiquettes
    // se disputent la place, celle qui cède doit être une cible à venir, pas
    // un relevé. Relevé au banc sur une sortie dont la marche 4 avait été
    // tranchée avant la 3 : « cible 4 j · 15/10 » — la mesure la plus
    // RÉCENTE — sautait au profit d'une échéance.
    const ordreBas = mes.slice().reverse()
      .concat(rail.map((s, i) => i).filter(i => mes.indexOf(i) < 0));
    ordreBas.forEach(i => {
      const s = rail[i];
      if (mode.bas === 'rare' && i % 2 === 1 && i !== N - 1) return;
      const yb = mode.deux && i % 2 === 1 ? G.BAS2 : G.BAS1;
      let t = basTexte(s, false);
      let b = boiteTexte(xs[i], yb, t, 11.5, 'middle', 0.56);
      let dx = glisser(b);
      // Glisser vers l'intérieur, oui — mais pas au point que l'étiquette
      // désigne la mauvaise marche. Au-delà, on la raccourcit à sa date.
      if (Math.abs(dx) > Math.max(26, dmin * 0.4)) {
        t = basTexte(s, true);
        b = boiteTexte(xs[i], yb, t, 11.5, 'middle', 0.56);
        dx = glisser(b);
      }
      if (!P.poser(bouger(b, dx))) return;
      // ⚠️ `mieux()` répond « atteint », donc TOUTE marche à partir de la
      // norme se disait franchie — « norme franchie » s'écrivait deux fois,
      // sous la marche de la norme et sous le seuil d'au-delà. La norme est
      // un passage : c'est la marche qui le porte, et elle seule.
      const vert = s.statut === 'atteint' && yN !== null && s.estNorme;
      txt.push('<text x="' + (xs[i] + dx).toFixed(1) + '" y="' + yb + '" text-anchor="middle"'
        + ' font-size="11.5"' + (vert ? ' font-weight="600" fill="#11835e"' : ' fill="#667085"')
        + '>' + esc(t) + '</text>');
      if (vert && !mode.deux && mode.bas === 'plein') {
        const t2 = T('rel_franchie');
        const b2 = boiteTexte(xs[i], G.BAS2, t2, 11, 'middle', 0.56);
        if (P.poser(b2)) {
          txt.push('<text x="' + xs[i].toFixed(1) + '" y="' + G.BAS2
            + '" text-anchor="middle" font-size="11" fill="#98a2b3">' + esc(t2) + '</text>');
        }
      }
    });

    // 4 · la pastille de la marche en cours : son échéance.
    const ec = rail.findIndex(s => s.statut === 'en_cours' && s.echeance);
    if (ec >= 0) {
      const cy = y(rail[ec].cible);
      const j = ecartJours(rail[ec].echeance);
      const t = fmtDate(rail[ec].echeance) + ' · ' + quandDit(rail[ec].echeance);
      const w = Math.max(96, t.length * 6.2 + 20);
      const hautDabord = cy > (G.YH + G.YB) / 2;
      [hautDabord ? cy - 28 : cy + 32, hautDabord ? cy + 32 : cy - 28].some(yb => {
        const b0 = { x1: xs[ec] - w / 2, x2: xs[ec] + w / 2, y1: yb - 14, y2: yb + 6 };
        const dx = glisser(b0);
        if (!P.poser(bouger(b0, dx))) return false;
        const cx = xs[ec] + dx, tard = j !== null && j < 0;
        marques.push('<rect x="' + (cx - w / 2).toFixed(1) + '" y="' + (yb - 14)
          + '" width="' + w.toFixed(1) + '" height="20" rx="10" fill="'
          + (tard ? '#fdf1f2' : '#fdf4e3') + '"></rect>');
        txt.push('<text x="' + cx.toFixed(1) + '" y="' + yb + '" text-anchor="middle"'
          + ' font-size="11" font-weight="600" fill="' + (tard ? '#a5192f' : '#93571a')
          + '">' + esc(t) + '</text>');
        return true;
      });
    }

    // 5 · la marche posée AU-DELÀ de la norme : c'est elle qui fait « avancé ».
    const ia = rail.findIndex(s => s.estAuDela);
    if (ia >= 0 && estNul(rail[ia].mesure)) {
      const yb = y(rail[ia].cible) - 20;
      const t = T('pal_audela').toUpperCase();
      const b = boiteTexte(xs[ia], yb, t, 9, 'middle', 0.72);
      if (yb - 8 >= RL.YT - 12 && P.poser(b)) {
        txt.push('<text x="' + xs[ia].toFixed(1) + '" y="' + yb.toFixed(1)
          + '" text-anchor="middle" font-size="9" font-weight="700"'
          + ' letter-spacing="1.2" fill="#0a5540">' + esc(t) + '</text>');
      }
    }

    // 6 · l'étiquette « LA NORME », de part et d'autre de son filet.
    if (yN !== null) {
      const t = T('rel_norme').toUpperCase();
      const w = Math.max(70, t.length * 6.6 + 16);
      [yN - 16, yN + 3].some(ry => {
        const b = { x1: G.X0, x2: G.X0 + w, y1: ry, y2: ry + 17 };
        if (!P.poser(b)) return false;
        marques.push('<rect x="' + G.X0 + '" y="' + ry.toFixed(1) + '" width="'
          + w.toFixed(1) + '" height="17" rx="3" fill="#101828"></rect>');
        txt.push('<text x="' + (G.X0 + w / 2).toFixed(1) + '" y="' + (ry + 12).toFixed(1)
          + '" text-anchor="middle" font-size="8.5" font-weight="700"'
          + ' letter-spacing="1.1" fill="#fff">' + esc(t) + '</text>');
        return true;
      });
    }

    // 7 · l'échelle : le pire, le milieu, le meilleur — dans l'unité réelle.
    reperes.forEach(v => {
      const yy = y(v);
      if (!isFinite(yy) || yy < RL.YT || yy > G.YB + 14) return;
      fond.push('<line x1="' + G.X0 + '" y1="' + yy.toFixed(1) + '" x2="' + RL.X1
        + '" y2="' + yy.toFixed(1) + '" stroke="#f2f4f7" stroke-width="1"></line>');
      const t = fmtVal(v, u);
      const b = boiteTexte(G.X0 - 14, yy + 4, t, 11, 'end', 0.6);
      if (!P.poser(b)) return;
      txt.push('<text x="' + (G.X0 - 14) + '" y="' + (yy + 4).toFixed(1)
        + '" text-anchor="end" font-size="11" fill="#98a2b3">' + esc(t) + '</text>');
    });

    // 8 · l'axe du temps, et sa règle des mois quand elle a du sens.
    fond.push('<line x1="' + G.X0 + '" y1="' + G.YAXE + '" x2="' + RL.X1
      + '" y2="' + G.YAXE + '" stroke="#eaecf0" stroke-width="1"></line>');
    const reels = dts.filter(Boolean);
    if (reels.length > 1 && mode.bas !== 'rare') {
      const a = reels[0], z = reels[reels.length - 1];
      let m = new Date(a.getFullYear(), a.getMonth() + 1, 1);
      let garde2 = 0;
      while (m <= z && garde2++ < 8) {
        const mx = xDuJour(jourDe(m));
        const nom = m.toLocaleDateString(LANG === 'en' ? 'en-GB' : 'fr-FR',
          { month: 'short' }).toUpperCase();
        const b = boiteTexte(mx, 247, nom, 10, 'start', 0.62);
        if (P.poser(b)) {
          fond.push('<line x1="' + mx.toFixed(1) + '" y1="' + G.YAXE + '" x2="'
            + mx.toFixed(1) + '" y2="' + (G.YAXE + 5) + '" stroke="#d0d5dd"'
            + ' stroke-width="1"></line>');
          txt.push('<text x="' + mx.toFixed(1) + '" y="247" font-size="10"'
            + ' font-weight="600" letter-spacing=".9" fill="#b4bcc8">' + esc(nom) + '</text>');
        }
        m = new Date(m.getFullYear(), m.getMonth() + 1, 1);
      }
    }

    // 9 · « zone tenue » : la seule mention purement explicative, donc la
    // dernière à passer — et la première à sauter quand la place manque.
    if (yN !== null && yN - RL.YT >= 26) {
      const t = T('rel_zone').toUpperCase();
      const b = boiteTexte(RL.X1 - 6, RL.YT + 13, t, 9, 'end', 0.72);
      if (P.poser(b)) {
        txt.push('<text x="' + (RL.X1 - 6) + '" y="' + (RL.YT + 13)
          + '" text-anchor="end" font-size="9" font-weight="700" letter-spacing="1.2"'
          + ' fill="#11835e" opacity=".75">' + esc(t) + '</text>');
      }
    }

    const aria = Tv('rel_aria', { x: r.name, n: mes.length,
      v: estNul(n.valeur) ? T('none') : fmtVal(n.valeur, u) });
    return '<svg viewBox="0 0 828 ' + G.H + '" role="img" aria-label="' + esc(aria) + '">'
      + defs + fond.join('') + trace.join('') + marques.join('') + txt.join('') + '</svg>';
  }

  // Le bilan dit en une ligne ce que l'historique disait en dix.
  function bilanRelief(perf) {
    const n = perf.norme || {}, sens = n.sens || SENS_MOINS, u = n.unite || '';
    const faits = (perf.paliers || []).filter(p => !estNul(p.mesure));
    const items = [];
    if (faits.length) {
      const tenues = faits.filter(p => p.statut === 'atteint').length;
      items.push([tenues === faits.length ? 'ok' : '', String(tenues),
                  nf('rel_tenues', tenues, faits.length)]);
    }
    if (faits.length > 1) {
      const a = faits[0].mesure, z = faits[faits.length - 1].mesure;
      const gagne = sens === SENS_MOINS ? a - z : z - a;
      if (gagne > 0) {
        items.push(['ok', fmtVal(gagne, u),
                    T(sens === SENS_MOINS ? 'rel_repris' : 'rel_gagne')]);
      }
      const d1 = dateJour(faits[0].evalue_le);
      const d2 = dateJour(faits[faits.length - 1].evalue_le);
      if (d1 && d2) {
        const j = Math.round((d2 - d1) / 86400000);
        if (j > 0) items.push(['', String(j), nf('rel_suivi', j)]);
      }
    }
    return '<div class="pal-bilan">'
      + items.map(it => '<div><span class="n' + (it[0] ? ' est-ok' : '') + '">'
          + esc(it[1]) + '</span> <span class="l">' + esc(it[2]) + '</span></div>').join('')
      + '<span class="sp"></span>'
      + '<button type="button" class="pal-detail" data-evol>' + esc(T('rel_detail'))
      + ' <i class="fa-solid fa-arrow-right"></i></button></div>';
  }

  // ── La carte d'une sortie MESURÉE ─────────────────────────────────
  function carteMesuree(r) {
    const perf = r.performance, n = perf.norme || {}, dev = jeSuisLeDev();
    const card = document.createElement('div');
    const niv = perf.niveau;
    // ⚠️ VIERGE : une norme posée, aucune mesure. La carte affichait alors
    // « Non évalué » pendant que l'activité montrait encore la note posée à
    // la main — et plus rien ne permettait de saisir ce qu'on avait relevé.
    // Tant que rien n'est mesuré, c'est cette note-là qui se lit, et le geste
    // qu'on propose est la PREMIÈRE MESURE.
    const vierge = !(perf.paliers || []).length;
    const expert = perf.expertise === true;
    // ⚠️ L'expertise POSÉE est le niveau qui compte — la déduction plafonne à
    // 3. Sans ça la carte affichait « 1 · En acquisition » pendant que
    // l'activité, elle, lisait 4 : le même défaut d'accord que plus haut,
    // dans l'autre sens.
    const lu = expert ? 4 : (estNul(niv) ? perf.niveau_pose : niv);
    card.className = 'cv2-res pal-res' + (perf.qualifie ? ' est-qualifie' : '')
      + (estNul(lu) ? '' : ' est-note');
    card.dataset.dataId = r.data_id;
    card.dataset.mesurable = '1';

    const encours = perf.palier_en_cours;
    const badge = perf.qualifie
      ? `<span class="pal-badge"><i class="fa-solid fa-check"></i>${esc(niv >= 3 ? T('pal_qualifie_av') : T('pal_qualifie'))}</span>`
      : '';
    card.innerHTML = `
      <div class="pal-tete">
        <div class="pal-tete-txt">
          <div class="rname"${r.minimum_performance_text
            ? ` title="${esc(T('std'))}${DP}${esc(r.minimum_performance_text)}"` : ''}>${esc(r.name)}
            ${r.minimum_performance_text ? '<i class="fa-regular fa-circle-question cv2-astuce"></i>' : ''}
          </div>
        </div>
        ${badge}
        <div class="pal-norme">
          <span class="k">${esc(T('pal_norme'))}</span>
          <span class="v">${esc(fmtVal(n.valeur, n.unite))}</span>
          <span class="s">${esc(n.sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins'))}</span>
          ${dev ? `<button type="button" class="pal-ic" data-norme aria-label="${esc(T('pal_norme_mod'))}"
                    title="${esc(T('pal_norme_mod'))}"><i class="fa-solid fa-pen"></i></button>` : ''}
        </div>
      </div>
      <div class="pal-corps">${(perf.paliers || []).length || perf.norme
        ? `<div class="pal-relief">${reliefSvg(r)}</div>${bilanRelief(perf)}`
        : `<p class="pal-vide">${esc(T('pal_rien_d'))}</p>`}</div>
      <div class="pal-pied">
        <span class="pal-pied-k">${esc((vierge || expert) ? T('pal_niveau_pose') : T('pal_niveau_deduit'))}<span data-echelle></span></span>
        ${estNul(lu)
          ? `<span class="pal-niv pal-niv--off">${esc(T('not_assessed'))}</span>`
          : `<span class="pal-niv pal-niv--${lu >= 2 ? 'ok' : 'bas'}"><b>${lu}</b> · ${esc(levelName(lu))}</span>`}
        ${expert ? `<span class="pal-exp-tag"><i class="fa-solid fa-hand"></i>${esc(T('pal_exp_posee'))}${
            estNul(niv) ? '' : ' · ' + esc(Tv('pal_exp_mesure', { n: niv, l: levelName(niv) }))}</span>` : ''}
        <span class="pal-pied-sp"></span>
        ${dev && !vierge ? `<button type="button" class="pal-exp${expert ? ' est-on' : ''}"
            data-exp aria-pressed="${expert ? 'true' : 'false'}"
            title="${esc(T('pal_exp_d'))}"><i class="fa-solid fa-award"></i>${esc(
              expert ? T('pal_exp_retirer') : T('pal_exp_poser'))}</button>` : ''}
        <!-- Une sortie déjà qualifiée n'appelle plus d'action : poser une
             marche de plus reste possible, mais ce n'est pas ce qu'on vient
             faire. Le bouton passe donc en discret. -->
        ${dev && vierge
          ? `<button type="button" class="pal-b pal-b--prim" data-premiere>
               <span class="pal-b-ic"><i class="fa-solid fa-ruler"></i></span>${esc(T('pal_premiere'))}</button>`
          : (dev && encours
            ? `<button type="button" class="pal-b pal-b--prim" data-trancher="${encours.id}">
                 <span class="pal-b-ic"><i class="fa-solid fa-gavel"></i></span>${esc(T('pal_trancher'))}</button>`
            : (dev ? `<button type="button" class="pal-b pal-b--${perf.qualifie ? 'doux' : 'prim'}" data-poser>
                 <span class="pal-b-ic"><i class="fa-solid fa-plus"></i></span>${esc(T('pal_poser_suivant'))}</button>` : ''))}
      </div>
      <div class="pal-form hidden"></div>`;

    const zone = card.querySelector('.pal-form');
    const q = s => card.querySelector(s);
    if (q('[data-norme]')) q('[data-norme]').onclick = () => formNorme(zone, r);
    if (q('[data-premiere]')) q('[data-premiere]').onclick = () => formPremiere(zone, r);
    if (q('[data-exp]')) q('[data-exp]').onclick = () => poserExpertise(r, !expert);
    // ⚠️ Le lien du bilan n'existe pas sur une sortie sans palier ni norme :
    // il n'y a rien à détailler, et un câblage sans garde couperait toute la
    // suite de l'init de la carte.
    if (q('[data-evol]')) q('[data-evol]').onclick = () => basculerHisto(card, r);
    const ech = q('[data-echelle]');
    if (ech) ech.appendChild(boutonInfo(T('pal_echelle_t'), texteEchelle()));
    if (q('[data-poser]')) q('[data-poser]').onclick = () => formPoser(zone, r);
    if (q('[data-trancher]')) q('[data-trancher]').onclick =
      () => formTrancher(zone, r, encours);
    return card;
  }

  // ⚠️ Les formulaires s'ouvrent DANS la carte, jamais en fenêtre : une modale
  // par-dessus une modale cache le chiffre qu'on vient lire pour décider.
  function ouvrirForm(zone, html, surValider) {
    zone.innerHTML = html + `<div class="pal-form-pied">
        <button type="button" class="btn btn-ghost" data-ko>${esc(T('pal_annuler'))}</button>
        <button type="button" class="btn btn-primary" data-ok>${esc(T('pal_valider'))}</button>
      </div>`;
    zone.classList.remove('hidden');
    zone.querySelector('[data-ko]').onclick = () => { zone.classList.add('hidden'); zone.innerHTML = ''; };
    zone.querySelector('[data-ok]').onclick = () => surValider(zone);
    const p = zone.querySelector('input, select, textarea');
    if (p) p.focus();
  }

  // ── L'unité : trois couvrent presque tout ─────────────────────────
  // ⚠️ %, jours, heures reviennent à chaque sortie : les retaper au clavier
  // est une corvée, et deux orthographes de la même grandeur (« j » et
  // « jours ») se liraient ensuite comme deux unités différentes. Le champ
  // libre reste, pour tout le reste.
  const UNITES = ['%', 'j', 'h'];
  const CLE_UNITE = { '%': 'pal_u_pct', j: 'pal_u_j', h: 'pal_u_h' };
  function champUnite(courante) {
    // ⚠️ Une norme NEUVE (`null`) part sur « % », pas sur « Autre… » : ouvrir
    // le champ libre d'emblée, c'est remettre au clavier ce qu'on vient d'en
    // retirer. Une norme EXISTANTE sans unité, elle, garde son vide — on ne
    // change pas une donnée enregistrée en passant.
    const neuve = estNul(courante);
    const val = neuve ? UNITES[0] : courante;
    const connue = UNITES.indexOf(val) >= 0;
    return `<label><span>${esc(T('pal_unite'))}</span>
        <span class="pal-unite">
          <select data-us>
            ${UNITES.map(x => `<option value="${esc(x)}"${val === x ? ' selected' : ''}>${esc(T(CLE_UNITE[x]))}</option>`).join('')}
            <option value="*"${connue ? '' : ' selected'}>${esc(T('pal_unite_autre'))}</option>
          </select>
          <input type="text" data-u class="${connue ? 'hidden' : ''}"
                 value="${esc(connue ? '' : (val || ''))}"
                 placeholder="${esc(T('pal_unite_ph'))}">
        </span></label>`;
  }
  function brancherUnite(zone, apres) {
    const s = zone.querySelector('[data-us]'), i = zone.querySelector('[data-u]');
    if (!s || !i) return;
    s.addEventListener('change', () => {
      i.classList.toggle('hidden', s.value !== '*');
      if (s.value === '*') i.focus();
      if (apres) apres();
    });
  }
  function lireUnite(zone) {
    const s = zone.querySelector('[data-us]'), i = zone.querySelector('[data-u]');
    if (!s) return ((i && i.value) || '').trim();
    return s.value === '*' ? ((i && i.value) || '').trim() : s.value;
  }
  const lireNb = (zone, sel) => parseFloat(
    ((zone.querySelector(sel) || {}).value || '').replace(',', '.').trim());

  // ── La PREMIÈRE mesure : la norme et le relevé, ensemble ──────────
  // ⚠️ Les deux se posaient séparément, et c'était le trou signalé : on
  // réglait la norme, la carte basculait en régime mesuré, et il n'existait
  // plus aucun endroit où saisir ce qu'on avait relevé — la sortie restait
  // « Non évalué » pendant que l'activité affichait encore l'ancienne note.
  // ⚠️ Et la norme ne se redemande PAS quand elle existe : elle vit sur la
  // sortie, pas sur la personne. Qui prend un rôle déjà tenu ailleurs hérite
  // de la norme de l'entreprise, on ne lui demande que sa mesure.
  function formPremiere(zone, r) {
    const n = (r.performance && r.performance.norme) || {};
    const deja = !estNul(n.valeur);
    ouvrirForm(zone, `
      <div class="pal-form-h">${esc(T('pal_premiere'))}</div>
      <p class="pal-form-d">${esc(T('pal_premiere_d'))}</p>
      ${deja
        ? `<p class="pal-deja"><i class="fa-solid fa-lock"></i>${esc(T('pal_norme_deja'))}
             <b>${esc(fmtVal(n.valeur, n.unite))} ${esc(n.sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins'))}</b></p>`
        : `<div class="pal-champs">
             <label><span>${esc(T('pal_valeur'))}</span>
               <input type="text" data-v inputmode="decimal"></label>
             ${champUnite(null)}
             <label><span>${esc(T('pal_sens'))}</span>
               <select data-s>
                 <option value="moins">${esc(T('pal_moins'))}</option>
                 <option value="plus">${esc(T('pal_plus'))}</option>
               </select></label>
           </div>`}
      <div class="pal-champs">
        <label class="pal-champ-mesure">
          <span>${esc(Tv('pal_mesure_q', { x: state.cibleNom }))}</span>
          <input type="text" data-m inputmode="decimal"></label>
      </div>
      <p class="pal-suivra" data-apercu></p>`,
      async z => {
        const m = lireNb(z, '[data-m]');
        if (!isFinite(m)) { toast(T('pal_mesure_manque')); return; }
        const corps = { user_id: state.cible, data_id: r.data_id,
                        role_id: state.roleId, mesure: m };
        if (!deja) {
          const v = lireNb(z, '[data-v]');
          if (!isFinite(v)) { toast(T('pal_valeur')); return; }
          corps.valeur = v; corps.unite = lireUnite(z);
          corps.sens = z.querySelector('[data-s]').value;
        }
        const res = await api('/paliers/premiere',
          { method: 'POST', body: JSON.stringify(corps) });
        if (res.__error) return;
        toast(T('pal_premiere_ok'));
        await refreshDashboard();
        await ouvrirEvaluation(state.activity);
      });

    // ⚠️ Un APERÇU, pas une règle : c'est le serveur qui tranche. Avec une
    // seule marche il n'y a que deux issues — la norme est atteinte (2) ou
    // non (1). Ni 0 (on ne rate pas une marche que personne n'avait posée),
    // ni 3 (aucun palier au-delà n'existe encore).
    const vue = zone.querySelector('[data-apercu]');
    const maj = () => {
      const m = lireNb(zone, '[data-m]');
      const v = deja ? n.valeur : lireNb(zone, '[data-v]');
      const sens = deja ? (n.sens || SENS_MOINS)
        : ((zone.querySelector('[data-s]') || {}).value || SENS_MOINS);
      if (!isFinite(m) || !isFinite(v)) { vue.textContent = ''; return; }
      const lvl = mieux(m, v, sens) ? 2 : 1;
      vue.innerHTML = `<span class="k">${esc(T('pal_niveau_suivra'))}</span>`
        + `<b class="pal-suivra-n pal-suivra-n--${lvl >= 2 ? 'ok' : 'bas'}">${lvl}</b>`
        + `<span>${esc(levelName(lvl))}</span>`;
    };
    brancherUnite(zone, maj);
    zone.querySelectorAll('input, select').forEach(e => {
      e.addEventListener('input', maj); e.addEventListener('change', maj);
    });
    maj();
  }

  function formNorme(zone, r) {
    const n = (r.performance && r.performance.norme) || {};
    ouvrirForm(zone, `
      <div class="pal-form-h">${esc(T('pal_norme_titre'))}</div>
      <p class="pal-form-d">${esc(T('pal_norme_d'))}</p>
      <div class="pal-champs">
        <label><span>${esc(T('pal_valeur'))}</span>
          <input type="text" data-v value="${esc(estNul(n.valeur) ? '' : fmtNb(n.valeur))}" inputmode="decimal"></label>
        ${champUnite(estNul(n.valeur) ? null : (n.unite || ''))}
        <label><span>${esc(T('pal_sens'))}</span>
          <select data-s>
            <option value="moins"${n.sens !== 'plus' ? ' selected' : ''}>${esc(T('pal_moins'))}</option>
            <option value="plus"${n.sens === 'plus' ? ' selected' : ''}>${esc(T('pal_plus'))}</option>
          </select></label>
      </div>
      ${estNul(n.valeur) ? '' : `<button type="button" class="pal-retirer" data-off>${esc(T('pal_effacer_norme'))}</button>`}`,
      async z => {
        const v = lireNb(z, '[data-v]');
        if (!isFinite(v)) { toast(T('pal_valeur')); return; }
        await poserNorme(r, { valeur: v, unite: lireUnite(z),
                              sens: z.querySelector('[data-s]').value });
      });
    brancherUnite(zone);
    const off = zone.querySelector('[data-off]');
    if (off) off.onclick = () => poserNorme(r, { valeur: null });
  }

  // ⚠️ L'EXPERTISE est le seul niveau qu'aucun chiffre ne donne : la
  // déduction plafonne à 3 (« la norme dépassée »). Sans cette porte, une
  // sortie mesurée ne pourrait JAMAIS valoir 4, et l'échelle mentirait sur
  // son propre palier du haut.
  async function poserExpertise(r, oui) {
    const res = await api('/mastery/evaluate', { method: 'POST', body: JSON.stringify({
      user_id: state.cible, activity_id: state.activity.activity_id,
      data_id: r.data_id, role_id: state.roleId, evaluator: '2',
      mastery_level: oui ? 4 : null }) });
    if (res.__error) return;
    toast(T(oui ? 'pal_exp_ok' : 'pal_exp_off'));
    await refreshDashboard();
    await ouvrirEvaluation(state.activity);
  }

  async function poserNorme(r, corps) {
    const res = await api(`/paliers/norme/${r.data_id}`,
      { method: 'POST', body: JSON.stringify(corps) });
    if (res.__error) return;
    toast(estNul(corps.valeur) ? T('pal_norme_retiree') : T('pal_norme_ok'));
    await refreshDashboard();
    await ouvrirEvaluation(state.activity);
  }

  function formPoser(zone, r) {
    const perf = r.performance, u = (perf.norme || {}).unite || '';
    const prop = perf.proposition;
    ouvrirForm(zone, `
      <div class="pal-form-h">${esc(T('pal_poser_suivant'))}</div>
      <div class="pal-champs">
        <label><span>${esc(T('pal_cible'))}${u ? ' (' + esc(u) + ')' : ''}</span>
          <input type="text" data-c value="${esc(estNul(prop) ? '' : fmtNb(prop))}" inputmode="decimal"></label>
        <label><span>${esc(T('pal_delai'))} (${esc(T('pal_jours'))})</span>
          <input type="text" data-j value="30" inputmode="numeric"></label>
      </div>
      ${estNul(prop) ? '' : `<p class="pal-form-d">${esc(Tv('pal_propose', { v: fmtVal(prop, u) }))}</p>`}`,
      async z => {
        const c = parseFloat((z.querySelector('[data-c]').value || '').replace(',', '.'));
        if (!isFinite(c)) { toast(T('pal_cible')); return; }
        const j = parseInt(z.querySelector('[data-j]').value, 10);
        const d = new Date(); d.setDate(d.getDate() + (isFinite(j) ? j : 30));
        const res = await api('/paliers/palier', { method: 'POST', body: JSON.stringify({
          user_id: state.cible, data_id: r.data_id, role_id: state.roleId,
          cible: c, echeance: jourISO(d) }) });
        if (res.__error) return;
        toast(T('pal_cree'));
        await refreshDashboard(); await ouvrirEvaluation(state.activity);
      });
  }

  function formTrancher(zone, r, palier) {
    const u = (r.performance.norme || {}).unite || '';
    ouvrirForm(zone, `
      <div class="pal-form-h">${esc(T('pal_trancher'))}</div>
      <p class="pal-form-d">${esc(T('pal_cible'))}${DP}<b>${esc(fmtVal(palier.cible, u))}</b></p>
      <div class="pal-champs">
        <label><span>${esc(T('pal_mesure_lbl'))}${u ? ' (' + esc(u) + ')' : ''}</span>
          <input type="text" data-m inputmode="decimal"></label>
      </div>
      <label class="pal-champ-large"><span>${esc(T('ses_note'))}</span>
        <textarea data-p rows="2" placeholder="${esc(T('pal_preuve_ph'))}"></textarea></label>
      <button type="button" class="pal-retirer" data-del>${esc(T('pal_retirer'))}</button>`,
      async z => {
        const m = parseFloat((z.querySelector('[data-m]').value || '').replace(',', '.'));
        if (!isFinite(m)) { toast(T('pal_mesure_lbl')); return; }
        const res = await api(`/paliers/palier/${palier.id}/trancher`, {
          method: 'POST',
          body: JSON.stringify({ mesure: m, preuve: z.querySelector('[data-p]').value }) });
        if (res.__error) return;
        toast(res.statut === 'atteint' ? T('pal_tranche_ok') : T('pal_tranche_ko'));
        await refreshDashboard(); await ouvrirEvaluation(state.activity);
        // ⚠️ Un palier manqué n'ouvre PAS « reposez la même cible » : il ouvre
        // l'analyse des savoirs. Reposer la marche sans rien changer, c'est
        // attendre le même résultat (CDC 6.8).
        if (res.statut === 'manque') apresEchec();
      });
    const del = zone.querySelector('[data-del]');
    if (del) del.onclick = async () => {
      const res = await api(`/paliers/palier/${palier.id}`, { method: 'DELETE' });
      if (res.__error) return;
      toast(T('pal_supprime'));
      await refreshDashboard(); await ouvrirEvaluation(state.activity);
    };
  }

  function apresEchec() {
    const b2 = $('#ev-centre');
    if (!b2) return;
    const w = document.createElement('div');
    w.className = 'pal-echec';
    w.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i>
      <span>${esc(T('pal_apres_echec'))}</span>
      <button type="button" class="pal-b pal-b--doux">
        <span class="pal-b-ic"><i class="fa-solid fa-magnifying-glass-chart"></i></span>${esc(T('pal_vers_diag'))}</button>`;
    w.querySelector('button').onclick = () => showDiagnostic();
    b2.insertBefore(w, b2.children[1] || null);
    w.classList.add('pal-echec--page');
    w.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function blocHistorique(r) {
    const perf = r.performance, u = (perf.norme || {}).unite || '';
    const sens = (perf.norme || {}).sens || SENS_MOINS;
    const box = document.createElement('div');
    box.className = 'pal-histo';
    let items = '';
    (perf.paliers || []).forEach(p => {
      const estNorme = mieux(p.cible, perf.norme.valeur, sens);
      items += `<div class="pal-h-l">
          <span class="pal-h-pt pal-h-pt--${estNorme ? 'norme' : 'pose'}"></span>
          <div><p class="d">${esc(fmtDate(p.echeance || p.evalue_le))}</p>
          <p class="t">${esc(Tv(estNorme ? 'ev_aligne' : 'ev_pose', { v: fmtVal(p.cible, u) }))}</p>
          ${estNorme && p.statut !== 'atteint' ? `<p class="s">${esc(T('ev_atteindre'))}</p>` : ''}</div>
        </div>`;
      if (p.evalue_le) {
        items += `<div class="pal-h-l">
            <span class="pal-h-pt pal-h-pt--${p.statut === 'atteint' ? 'ok' : 'ko'}"></span>
            <div><p class="d">${esc(fmtDate(p.evalue_le))} · ${esc(T('ev_session_tenue'))}</p>
            <p class="t">${esc(fmtVal(p.mesure, u))} — ${esc(T(p.statut === 'atteint' ? 'pal_atteint' : 'pal_manque'))}</p>
            ${p.preuve ? `<p class="s">${esc(p.preuve)}</p>` : ''}</div>
          </div>`;
      }
    });
    if (perf.palier_en_cours && perf.palier_en_cours.echeance) {
      items += `<div class="pal-h-l">
          <span class="pal-h-pt pal-h-pt--venir"></span>
          <div><p class="d">${esc(fmtDate(perf.palier_en_cours.echeance))} · ${esc(T('ev_a_venir'))}</p>
          <p class="t">${esc(T('ev_session_prevue'))}</p></div>
        </div>`;
    }
    box.innerHTML = `<div class="pal-histo-h">${esc(T('ev_histo'))}</div>`
      + (items || `<p class="pal-vide">${esc(T('ev_rien'))}</p>`);
    return box;
  }

  // ══ LE CALENDRIER DES SESSIONS ═════════════════════════════════════
  // ⚠️ Il ne se cadre PAS sur un collaborateur : celui qui tient les
  // rendez-vous les tient pour tout le monde. Cadré sur une personne, une
  // session ne se voit qu'en ayant d'abord choisi la bonne — c'est ce qui
  // faisait manquer les propositions de carto dans la page RH.
  const cal = { mois: null, sessions: [], compteurs: {}, choisie: null,
                detail: null, retour: 'synthese', filtre: null, vise: null };

  // ⚠️ L'appartenance d'une session à une tuile vient du SERVEUR (`tuiles`),
  // calculée dans la boucle qui incrémente les compteurs : refaire ici les
  // quatre prédicats (en retard, cette semaine, ce mois, tenues cette année)
  // donnerait un second verdict, et le chiffre de la tuile finirait par ne
  // plus désigner les cases qu'elle met en avant.
  const LIB_TUILE = { en_retard: 'ses_en_retard', semaine: 'ses_semaine',
                      mois: 'ses_mois', tenues_annee: 'ses_tenues' };
  const dansTuile = (ses, cle) => (ses.tuiles || []).indexOf(cle) >= 0;
  const visibles = () => (cal.filtre
    ? cal.sessions.filter(x => dansTuile(x, cal.filtre)) : cal.sessions);



  // Un chiffre appelle le clic : chaque tuile FILTRE le mois, et se
  // rallume pour dire lequel. Recliquer celle qui est allumée l'éteint —
  // sinon on ne peut plus revenir à « tout ».
  function tuileCal(cle, lbl, teinte) {
    const n = cal.compteurs[cle] || 0;
    const on = cal.filtre === cle;
    return `<button type="button" class="cal-tuile cal-tuile--${teinte}${on ? ' is-on' : ''}"
        data-f="${cle}" aria-pressed="${on ? 'true' : 'false'}"
        title="${esc(on ? T('ses_f_off') : T('ses_f_on'))}">
        <span class="n">${n}</span>
        <span class="l">${esc(T(lbl))}</span></button>`;
  }

  // Filtrer sur un mois qui ne porte aucune session visée ne montrerait
  // rien : on se pose sur le mois de la première session retenue.
  function filtrerCal(cle) {
    cal.filtre = cal.filtre === cle ? null : cle;
    const vus = visibles();
    if (cal.filtre && vus.length) {
      const j = dateJour(vus[0].date_prevue);
      if (j) cal.mois = new Date(j.getFullYear(), j.getMonth(), 1);
    }
    rendreCal();
    if (cal.choisie) chargerSession(cal.choisie);
  }

  function rendreMois() {
    const z = $('#cal-mois');
    const m = cal.mois, an = m.getFullYear(), mo = m.getMonth();
    const premier = new Date(an, mo, 1);
    const decal = (premier.getDay() + 6) % 7;            // la semaine part du lundi
    const nJours = new Date(an, mo + 1, 0).getDate();
    const titre = m.toLocaleDateString(LANG === 'en' ? 'en-GB' : 'fr-FR',
                                       { month: 'long', year: 'numeric' });
    const parJour = {};
    cal.sessions.forEach(s => {
      const d = dateJour(s.date_prevue);
      if (d && d.getFullYear() === an && d.getMonth() === mo) {
        (parJour[d.getDate()] = parJour[d.getDate()] || []).push(s);
      }
    });
    // Planifier : une case se clique pour poser sa date. Elle n'est offerte
    // qu'à qui peut vraiment planifier — un bouton qui ne mène nulle part
    // vaut moins qu'un simple jour.
    const planif = !!(state.estDev && state.roleId && state.cible);
    const jours = ['ses_lun', 'ses_mar', 'ses_mer', 'ses_jeu', 'ses_ven', 'ses_sam', 'ses_dim'];
    let g = '';
    jours.forEach((k, i) => {
      g += `<span class="cal-jn${i > 4 ? ' est-we' : ''}">${esc(T(k))}</span>`;
    });
    for (let i = 0; i < decal; i++) g += '<span class="cal-case cal-case--hors"></span>';
    const auj = new Date(); auj.setHours(0, 0, 0, 0);
    for (let j = 1; j <= nJours; j++) {
      const dj = new Date(an, mo, j), we = dj.getDay() === 0 || dj.getDay() === 6;
      const ses = parJour[j] || [];
      const iso = jourISO(dj);
      const base = `${we ? ' est-we' : ''}${+dj === +auj ? ' est-auj' : ''}`
        + (cal.vise === iso ? ' est-visee' : '');
      if (!ses.length) {
        g += planif
          ? `<button type="button" class="cal-case cal-case--libre${base}" data-jour="${iso}"
               title="${esc(T('ses_poser_le'))}"><span class="n">${j}</span>
               <span class="pose"><i class="fa-solid fa-plus"></i></span></button>`
          : `<div class="cal-case${base}"><span class="n">${j}</span></div>`;
        continue;
      }
      const s = ses[0];
      const teinte = s.statut === 'tenue' ? 'tenue' : (s.en_retard ? 'retard' : 'prevue');
      const n = s.a_trancher || s.n_paliers || 0;
      const vise = !cal.filtre || dansTuile(s, cal.filtre);
      g += `<button type="button" class="cal-case cal-case--${teinte}${base}${cal.choisie === s.id ? ' est-choisie' : ''}${cal.filtre ? (vise ? ' est-vise' : ' est-eteint') : ''}"
              data-ses="${s.id}" data-jour="${iso}">
          <span class="n">${j}</span>
          <span class="qui"><i class="pt"></i>${esc(s.nom)}</span>
          <span class="sub">${esc(n ? Tv(n > 1 ? 'ses_a_trancher_pl' : 'ses_a_trancher', { n: n })
                                    : T('ses_' + (s.statut === 'tenue' ? 'tenue' : 'prevue')))}</span>
          ${ses.length > 1 ? `<span class="plus">+${ses.length - 1}</span>` : ''}
        </button>`;
    }
    z.innerHTML = `
      <div class="cal-mois-h">
        <h3>${esc(titre.charAt(0).toUpperCase() + titre.slice(1))}</h3>
        <span class="sp"></span>
        <button type="button" class="cal-nav" data-dm="-1" aria-label="${esc(T('ses_mois_prec'))}">‹</button>
        <button type="button" class="cal-nav" data-dm="1" aria-label="${esc(T('ses_mois_suiv'))}">›</button>
      </div>
      <div class="cal-grille">${g}</div>
      <div class="cal-leg">
        <span><i class="p p--prevue"></i>${esc(T('ses_legend_palier'))}</span>
        <span><i class="p p--retard"></i>${esc(T('ses_legend_retard'))}</span>
        <span><i class="p p--tenue"></i>${esc(T('ses_legend_tenue'))}</span>
      </div>`;
    z.querySelectorAll('[data-dm]').forEach(b => b.onclick = () => {
      cal.mois = new Date(cal.mois.getFullYear(), cal.mois.getMonth() + (+b.dataset.dm), 1);
      rendreMois();
    });
    // ⚠️ Le formulaire ouvert l'emporte : tant qu'on planifie, un clic
    // n'importe où dans le mois POSE la date — y compris sur un jour déjà
    // occupé, puisqu'une deuxième séance le même jour est légitime.
    z.querySelectorAll('[data-jour]').forEach(b => b.addEventListener('click', ev => {
      const champ = $('#cal-detail [data-d]');
      if (champ) { ev.stopPropagation(); poserJour(b.dataset.jour); return; }
      if (!b.dataset.ses) formSession(b.dataset.jour);
    }));
    z.querySelectorAll('[data-ses]').forEach(b => b.addEventListener('click', () => {
      if ($('#cal-detail [data-d]')) return;      // le formulaire a déjà pris le clic
      chargerSession(+b.dataset.ses);
    }));
    if (!Object.keys(parJour).length) {
      z.querySelector('.cal-grille').insertAdjacentHTML('afterend',
        `<p class="pal-vide">${esc(T('ses_vide_mois'))}</p>`);
    }
  }

  async function chargerSession(sid) {
    cal.choisie = sid;
    showBusy(null, '#cal-detail');
    const d = await api(`/paliers/session/${sid}/detail`);
    if (d.__error) return;
    cal.detail = d;
    rendreMois();
    rendreDetail(d);
  }

  function rendreDetail(d) {
    const s = d.session, z = $('#cal-detail');
    const tenue = s.statut === 'tenue';
    let lignes = '';
    (d.paliers || []).forEach(p => {
      const cls = p.statut === 'en_cours' ? 'att' : (p.statut === 'atteint' ? 'ok' : 'ko');
      lignes += `<div class="cal-pal cal-pal--${cls}">
          <div class="h"><span class="so">${esc(p.sortie)}</span>
            <span class="ac">${esc(p.activite)}</span><span class="sp"></span>
            <span class="ci">${esc(T('pal_cible'))}${DP}<b>${esc(fmtVal(p.cible, p.unite))}</b>
              ${esc(p.sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins'))}</span></div>
          ${p.statut === 'en_cours' ? '' : `<p class="m2">
            ${esc(Tv('pal_mesure_de', { v: fmtVal(p.mesure, p.unite) }))}
            <span class="v v--${cls}">${esc(T(p.statut === 'atteint' ? 'pal_atteint' : 'pal_manque'))}</span></p>`}
        </div>`;
    });
    const ret = s.en_retard ? `<span class="cal-d-retard">${esc(T('pal_retard'))}</span>` : '';
    z.innerHTML = `
      <div class="cal-d-h">
        <p class="k">${esc(fmtDate(s.date_prevue))} · ${esc(quandDit(s.date_prevue))} ${ret}</p>
        <h3>${esc(s.nom)}</h3>
        <p class="r">${s.role ? `<span class="pastille">${esc(s.role)}</span>` : ''}
          ${esc(tenue ? T('ses_tenue')
            : (s.n_paliers ? Tv(s.n_paliers > 1 ? 'ses_a_trancher_pl' : 'ses_a_trancher',
                                { n: s.n_paliers }) : ''))}</p>
      </div>
      <div class="cal-d-corps">${lignes || `<p class="pal-vide">${esc(T('ses_rien_a_trancher'))}</p>`}</div>
      <div class="cal-d-pied">
        <span class="cal-d-info"></span>
        ${(d.paliers || []).length && state.estDev
          ? `<button type="button" class="pal-b pal-b--prim" data-tenir>
              <span class="pal-b-ic"><i class="fa-solid fa-gavel"></i></span>
              ${esc(tenue ? T('sq_rouvrir') : T('sq_ouvrir'))}</button>` : ''}
      </div>`;
    // ⚠️ UN seul endroit pose une mesure : la séance. Le calendrier dit
    // QUAND et QUOI ; deux écrans de saisie finiraient par ne plus dire la
    // même chose du même geste.
    const inf = z.querySelector('.cal-d-info');
    if (inf) inf.appendChild(boutonInfo(T('ses_verdicts_t'), T('ses_verdicts_calc')));
    const b = z.querySelector('[data-tenir]');
    if (b) b.onclick = () => ouvrirSeance(s.id);
  }

  // ⚠️ Pas de `window.prompt` : la fenêtre du navigateur arrive avec ses
  // styles système et son texte en dur — c'est exactement ce qu'on a retiré
  // de la page Temps. Le formulaire s'ouvre DANS le panneau de droite.
  // ⚠️ Le jour VISÉ vit dans `cal`, pas seulement dans le champ : le mois se
  // redessine à chaque clic, et c'est lui qui marque la case choisie.
  function poserJour(iso) {
    const champ = $('#cal-detail [data-d]');
    if (!champ) return;
    champ.value = iso;
    cal.vise = iso;
    const j = dateJour(iso);
    if (j && (j.getMonth() !== cal.mois.getMonth() || j.getFullYear() !== cal.mois.getFullYear())) {
      cal.mois = new Date(j.getFullYear(), j.getMonth(), 1);
    }
    rendreMois();
  }

  function formSession(iso) {
    const z = $('#cal-detail');
    const d = new Date(); d.setDate(d.getDate() + 15);
    const depart = iso || jourISO(d);
    cal.vise = depart;
    z.innerHTML = `
      <div class="cal-d-h"><h3>${esc(T('ses_planifier'))}</h3>
        <p class="r"><span class="pastille">${esc(state.roleName || '')}</span>${esc(state.cibleNom || '')}</p></div>
      <div class="cal-d-corps">
        <div class="cal-d-date">
          <label><span>${esc(T('ses_date'))}</span>
            <input type="date" data-d value="${esc(depart)}"></label>
          <p class="cal-d-aide"><i class="fa-regular fa-hand-pointer"></i>${esc(T('ses_clic_jour'))}</p>
        </div>
        <label class="pal-champ-large"><span>${esc(T('ses_objet_ph'))}</span>
          <input type="text" data-o></label>
      </div>
      <div class="cal-d-pied">
        <p class="d"></p>
        <button type="button" class="btn btn-ghost" data-ko>${esc(T('pal_annuler'))}</button>
        <button type="button" class="pal-b pal-b--prim" data-ok>
          <span class="pal-b-ic"><i class="fa-solid fa-calendar-plus"></i></span>${esc(T('ses_planifier'))}</button>
      </div>`;
    z.querySelector('[data-d]').addEventListener('change', e => {
      cal.vise = e.target.value || null; rendreMois();
    });
    z.querySelector('[data-ko]').onclick = () => {
      cal.vise = null; rendreMois();
      if (cal.choisie) chargerSession(cal.choisie);
      else z.innerHTML = `<p class="pal-vide">${esc(T('ses_choisir_une'))}</p>`;
    };
    z.querySelector('[data-ok]').onclick = async () => {
      const quand = z.querySelector('[data-d]').value;
      if (!quand) { toast(T('ses_date')); return; }
      const res = await api('/paliers/session', { method: 'POST', body: JSON.stringify({
        user_id: state.cible, role_id: state.roleId, date_prevue: quand,
        objet: z.querySelector('[data-o]').value }) });
      if (res.__error) return;
      toast(T('ses_cree'));
      cal.vise = null;
      cal.mois = dateJour(quand);
      cal.mois = new Date(cal.mois.getFullYear(), cal.mois.getMonth(), 1);
      await ouvrirCalendrier(res.session && res.session.id);
    };
    rendreMois();
    z.querySelector('[data-d]').focus();
  }


  // ══ LA PAGE D'ÉVALUATION ═══════════════════════════════════════════
  // ⚠️ Évaluer n'est plus un tiroir. Le tiroir fait 720 px, et `body.pg`
  // porte `zoom: .8` : 576 px RÉELS pour une échelle de paliers, un graphe
  // et un historique. Tout y était comprimé. La page prend les trois
  // colonnes : les activités du rôle à gauche (on passe de l'une à l'autre
  // sans revenir en arrière), la sortie au centre, le contexte à droite.
  //
  // Le tiroir reste — pour les deux DIALOGUES courts : configurer une
  // activité, et le diagnostic d'un écart.

  // ⚠️ Les clés de pluriel ne suivent pas toutes la même convention dans ce
  // catalogue — `_1`/`_n` ici, `_pl` là, la forme nue ailleurs. On essaie
  // dans l'ordre celle qui EXISTE : une clé absente ne lève rien, elle
  // s'affiche telle quelle (« ev_nb_act_n » relevé à l'écran).
  function nf(c, n, u) {
    const essais = n === 1 ? [c + '_1', c] : [c + '_n', c + '_pl', c];
    const k = essais.find(x => T(x) !== x) || c;
    return Tv(k, { n: n, t: u });
  }

  async function ouvrirEvaluation(row) {
    state.activity = row;
    montrerEcran('eval');
    showBusy(null, '#cv2-ecran-eval');
    // ⚠️ UN SEUL appel. Le relief se dessine depuis les paliers que
    // `/mastery/activity` porte déjà (cible, mesure, date, échéance) :
    // `/paliers/historique` n'en rendait qu'un sous-ensemble, et une requête
    // dont personne ne lit la réponse est du temps pris à l'ouverture.
    const st = await api(
      `/mastery/activity/${state.cible}/${row.activity_id}?role_id=${state.roleId}`);
    if (st.__error) return;
    state.lastState = st;
    renderEval(st);
  }

  function renderEval(st) {
    const z = $('#cv2-ecran-eval');
    const dev = jeSuisLeDev();
    const nAct = state.rows.length;
    const nEval = state.rows.filter(a => !estNul(a.demonstrated_level)).length;
    z.innerHTML = `
      <header class="ev-tete">
        <div class="ev-tete-in">
          <button type="button" class="ev-retour" data-retour>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 6l-6 6 6 6"/></svg>
            ${esc(state.roleName || T('ev_retour_role'))}</button>
          <span class="ev-sep"></span>
          <span class="ev-av">${esc(initials(...String(state.cibleNom).split(' ')))}</span>
          <div class="ev-qui">
            <p class="n">${esc(state.cibleNom)}</p>
            <p class="s"><span class="pastille">${esc(nf('ev_nb_act', nAct))}</span>
              ${state.devNom ? esc(Tv('ev_suivi_par', { x: state.devNom })) : ''}</p>
          </div>
          <span class="ev-pousse"></span>
          <div class="ev-niv">
            <p class="k">${esc(T('ev_niv_role'))}</p>
            <p class="v">${esc(niveauRole())}</p>
            <p class="d">${esc(Tv('ev_evaluees', { n: nEval, t: nAct }))}</p>
          </div>
          <span class="ev-sep"></span>
          <div class="ev-actions">
            <button type="button" class="pal-b pal-b--verre" data-cal>
              <span class="pal-b-ic"><i class="fa-solid fa-calendar-days"></i></span>${esc(T('ses_cal'))}</button>
            ${dev ? `<button type="button" class="pal-b pal-b--prim" data-plan>
              <span class="pal-b-ic"><i class="fa-solid fa-file-lines"></i></span>${esc(T('plan_open'))}</button>` : ''}
          </div>
        </div>
      </header>

      <div class="ev-corps">
        <aside class="ev-acts">
          <div class="ev-acts-h">
            <p class="k"><span class="num">1</span>${esc(T('ev_col_act'))}</p>
            <div class="ev-acts-f" id="ev-acts-f"></div>
          </div>
          <div class="ev-acts-l" id="ev-acts-l"></div>
        </aside>
        <main class="ev-centre" id="ev-centre"></main>
        <aside class="ev-ctx" id="ev-ctx"></aside>
      </div>`;

    z.querySelector('[data-retour]').onclick = () => chargerSynthese();
    z.querySelector('[data-cal]').onclick = () => ouvrirCalendrier();
    const bp = z.querySelector('[data-plan]');
    if (bp) bp.onclick = () => ouvrirPlan();

    remplirActivites();
    remplirCentre(st);
    remplirContexte(st);
    z.scrollIntoView({ block: 'start' });
  }

  function niveauRole() {
    const niv = state.rows.map(a => a.demonstrated_level).filter(v => !estNul(v));
    if (!niv.length || niv.length < state.rows.length) return T('not_assessed');
    const m = Math.min.apply(null, niv);
    return m + ' · ' + levelName(m);
  }

  function remplirActivites() {
    rendreFiltres();
    const box = $('#ev-acts-l'); box.innerHTML = '';
    const vues = state.filtre
      ? state.rows.filter(a => categorie(a) === state.filtre) : state.rows;
    if (!vues.length) {
      box.innerHTML = `<p class="pal-vide">${esc(T('no_match'))}</p>`;
      return;
    }
    vues.forEach(a => {
      const cat = categorie(a);
      const ouverte = a.activity_id === state.activity.activity_id;
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'ev-act' + (ouverte ? ' est-ouverte' : '');
      const niv = estNul(a.demonstrated_level) ? null : a.demonstrated_level;
      const couleur = niv === null ? '#8b96a6'
        : (niv >= 3 ? '#15803d' : (niv >= 2 ? '#1d4ed8' : '#b45309'));
      let etat;
      if (cat === 'setup') etat = `<span class="ev-act-e">${esc(T('ev_a_config'))}</span>`;
      else if (niv === null) etat = `<span class="ev-act-e">${esc(T('ev_non_eval'))}</span>`;
      else etat = `<span class="ev-act-n" style="color:${couleur}">${niv}</span>`;
      el.innerHTML = `<span class="ev-act-h"><span class="ev-act-t">${esc(a.activity_name)}</span>${etat}</span>
        ${niv === null ? '' : `<span class="ev-act-j">${jaugeFine(niv, a.required_level, couleur)}
          <span class="ev-act-s">${esc(nf('ev_sorties', a.n_results || 0))}</span></span>`}`;
      el.onclick = () => { if (!ouverte) ouvrirEvaluation(a); };
      box.appendChild(el);
    });
  }

  function rendreFiltres() {
    const z = $('#ev-acts-f'); if (!z) return;
    const compte = { held: 0, gap: 0, todo: 0, setup: 0 };
    state.rows.forEach(a => { compte[categorie(a)] += 1; });
    const tuiles = [['held', T('b_held'), 'green'], ['gap', T('b_gap'), 'orange'],
                    ['todo', T('b_todo'), 'blue'], ['setup', T('b_setup'), 'grey']];
    z.innerHTML = tuiles.filter(([c]) => compte[c] || state.filtre === c)
      .map(([c, lbl, teinte]) => `<button type="button"
          class="ev-f ev-f--${teinte}${state.filtre === c ? ' is-on' : ''}"
          data-f="${c}" title="${esc(state.filtre === c ? T('filter_off') : lbl)}">
          <span class="n">${compte[c]}</span><span class="k">${esc(lbl)}</span></button>`).join('');
    z.querySelectorAll('[data-f]').forEach(b => b.onclick = () => {
      state.filtre = state.filtre === b.dataset.f ? null : b.dataset.f;
      remplirActivites();
    });
  }

  // La même jauge que la liste, en plus fin : quatre pas, un trait au requis.
  function jaugeFine(niveau, requis, couleur) {
    let h = '';
    for (let lv = 1; lv <= 4; lv++) {
      if (!estNul(requis) && lv === requis + 1) h += '<span class="ev-j-trait"></span>';
      const plein = !estNul(niveau) && niveau >= lv;
      h += `<span class="ev-j-pas"${plein ? ` style="background:${couleur}"` : ''}></span>`;
    }
    return h;
  }

  function remplirCentre(st) {
    const box = $('#ev-centre');
    box.innerHTML = `<div class="ev-centre-h">
        <p class="k"><span class="num">2</span>${esc(T('ev_col_sor'))}</p>
      </div>`;
    box.querySelector('.ev-centre-h .k')
       .appendChild(boutonInfo(T('ev_col_sor'), T('ev_col_sor_d')));
    const tete = document.createElement('div');
    tete.className = 'ev-sujet';
    tete.innerHTML = `<h1>${esc(state.activity.activity_name)}</h1>
      ${state.activity.competence
        ? `<p class="comp"><span class="ico"><i class="fa-solid fa-bullseye"></i></span>${esc(state.activity.competence)}</p>`
        : ''}`;
    box.appendChild(tete);

    if (!(st.results && st.results.length)) {
      const w = document.createElement('div'); w.className = 'ev-vide';
      w.innerHTML = `<p>${esc(jeSuisLeDev() ? T('rien_a_evaluer') : T('pas_configuree'))}</p>`;
      if (jeSuisLeDev()) {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'pal-b pal-b--prim';
        b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-sliders"></i></span>${esc(T('conf_go'))}`;
        b.onclick = () => ouvrirConfiguration(state.activity);
        w.appendChild(b);
      }
      box.appendChild(w);
      return;
    }

    st.results.forEach(r => box.appendChild(carteSortie(r, st.required_level)));

    // ⚠️ « Enregistrer » n'apparaît que s'il y a quelque chose à SAISIR : sur
    // une activité toute mesurée, le niveau vient du chiffre relevé en séance.
    const aSaisir = st.results.some(r => !r.mesurable);
    const pied = document.createElement('div');
    pied.className = 'ev-pied';
    pied.innerHTML = `<p>${esc(aSaisir ? '' : T('pal_pas_de_note'))}</p>`;
    if (jeSuisLeDev() && aUnEcart(st)) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'pal-b pal-b--doux';
      b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-magnifying-glass-chart"></i></span>${esc(T('diagnose'))}`;
      b.onclick = () => showDiagnostic();
      pied.appendChild(b);
    }
    if (aSaisir) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'pal-b pal-b--prim'; b.id = 'cv2-save-btn';
      b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-check"></i></span>`
        + esc(jeSuisLeDev() ? T('save_eval') : T('save_self'));
      b.onclick = saveEvaluation;
      pied.appendChild(b);
    }
    box.appendChild(pied);
  }

  function remplirContexte(st) {
    const box = $('#ev-ctx'); box.innerHTML = '';
    const niv = st.global_level;
    const couleur = estNul(niv) ? '#5b6676'
      : (niv >= 3 ? '#14532d' : (niv >= 2 ? '#1d4ed8' : '#78350f'));

    let lignes = '';
    (st.results || []).forEach(r => {
      const n = r.demonstrated_level;
      const c = estNul(n) ? '#8b96a6' : (n >= 3 ? '#15803d' : (n >= 2 ? '#2563eb' : '#b45309'));
      lignes += `<div class="ev-ctx-l"><span class="b" style="background:${c}"></span>
        <span class="t">${esc(r.name)}</span>
        <span class="n" style="color:${c}">${estNul(n) ? '—' : n}</span></div>`;
    });

    const carte = document.createElement('section');
    carte.className = 'ev-carte';
    carte.innerHTML = `<p class="k">${esc(T('ev_niv_act'))}</p>
      <p class="gros" style="color:${couleur}">${estNul(niv) ? '—' : niv}</p>
      <p class="mot" style="color:${couleur}">${esc(estNul(niv) ? T('not_assessed') : levelName(niv))}</p>
      <div class="ev-ctx-ls">${lignes}</div>`;
    // La règle du MINIMUM : utile une fois, encombrante à chaque regard.
    carte.querySelector('.k').appendChild(boutonInfo(T('ev_min_t'), texteMinimum()));
    box.appendChild(carte);

    // La prochaine échéance se LIT dans les paliers déjà chargés : un appel de
    // plus pour un chiffre qu'on a déjà serait une seconde source de vérité.
    const ech = prochaineEcheance(st);
    if (ech) {
      const s = document.createElement('section');
      s.className = 'ev-carte ev-carte--ses';
      s.innerHTML = `<p class="k"><i class="fa-regular fa-calendar"></i>${esc(T('ses_prochaine'))}</p>
        <p class="date">${esc(fmtDate(ech.quand))}</p>
        <p class="d">${esc(quandDit(ech.quand))} · ${esc(nf('ses_a_trancher', ech.n))}</p>
        <button type="button" class="pal-b pal-b--doux" data-cal2>
          <span class="pal-b-ic"><i class="fa-solid fa-calendar-days"></i></span>${esc(T('ses_ouvrir'))}</button>`;
      s.querySelector('[data-cal2]').onclick = () => ouvrirCalendrier();
      box.appendChild(s);
    }

    const tech = document.createElement('section');
    tech.className = 'ev-carte ev-carte--tech';
    tech.innerHTML = `<p class="k">${esc(T('ev_tech'))}</p>
      <div class="cv2-domlist"></div><div class="cv2-domadd"></div>`;
    box.appendChild(tech);
    loadTech(tech);

  }

  // Les libellés du catalogue portent [[b]]…[[/b]] pour un seul mot en gras :
  // le reste de la phrase doit rester traduisible d'un bloc.
  function gras(txt) {
    return esc(txt).split('[[b]]').join('<strong>').split('[[/b]]').join('</strong>');
  }

  function prochaineEcheance(st) {
    let quand = null, n = 0;
    (st.results || []).forEach(r => {
      const p = r.performance && r.performance.palier_en_cours;
      if (!p || !p.echeance) return;
      n += 1;
      if (!quand || p.echeance < quand) quand = p.echeance;
    });
    return quand ? { quand: quand, n: n } : null;
  }

  // ── Le détail des séances se déplie DANS la carte, sous le relief ──
  // ⚠️ Il n'y a plus de second graphe à ouvrir : le relief EST le graphe, et
  // il est là dès l'ouverture de la carte. Ce qui se déplie, c'est ce qu'il
  // ne peut pas montrer — séance par séance, qui a relevé quoi, et la preuve.
  function basculerHisto(card, r) {
    const ouvert = card.querySelector('.pal-histo');
    if (ouvert) {
      ouvert.remove();
      const f = card.querySelector('.pal-evo-fin');
      if (f) f.remove();
      card.dataset.evo = '';
      majLibelleEvo(card, false);
      return;
    }
    const pied = card.querySelector('.pal-pied');
    pied.insertAdjacentElement('afterend', blocHistorique(r));
    // ⚠️ Le bouton qui a OUVERT la section se retrouve en plein milieu une
    // fois l'historique déplié : il faut le chercher pour refermer. On
    // referme donc par le BAS, là où la lecture s'arrête.
    const bas = document.createElement('button');
    bas.type = 'button'; bas.className = 'pal-evo-fin';
    bas.innerHTML = `<i class="fa-solid fa-chevron-up"></i>${esc(T('rel_detail_off'))}`;
    bas.onclick = () => { basculerHisto(card, r); card.scrollIntoView({ block: 'nearest' }); };
    // ⚠️ En DERNIER enfant de la carte, pas après l'historique : `.pal-form`
    // vient après lui, et une marche posée pendant qu'on lit l'évolution
    // glisserait un formulaire SOUS le bouton qui sert à la refermer.
    card.appendChild(bas);
    card.dataset.evo = '1';
    majLibelleEvo(card, true);
  }
  function majLibelleEvo(card, ouvert) {
    const b = card.querySelector('[data-evol]');
    if (!b || !b.firstChild) return;
    // ⚠️ Le libellé est le PREMIER nœud du lien — la flèche vient après. Un
    // `lastChild` réécrirait l'icône et on perdrait le libellé.
    b.firstChild.textContent = (ouvert ? T('rel_detail_off') : T('rel_detail')) + ' ';
  }

  // ══ LA SÉANCE ══════════════════════════════════════════════════════
  // La page est le RENDEZ-VOUS : une chose à faire à la fois, le champ de
  // mesure en grand — c'est pour ça qu'on est là — et le verdict qui tombe.
  const sq = { sid: null, session: null, paliers: [], saisie: {}, i: 0 };

  async function ouvrirSeance(sid) {
    const d = await api(`/paliers/session/${sid}/detail`);
    if (d.__error) return;
    sq.sid = sid; sq.session = d.session; sq.paliers = d.paliers || [];
    sq.saisie = {};
    sq.paliers.forEach(p => {
      if (!estNul(p.mesure)) sq.saisie[p.palier_id] = { mesure: p.mesure, preuve: p.preuve || '' };
    });
    sq.i = sq.paliers.findIndex(p => !sq.saisie[p.palier_id]);
    if (sq.i < 0) sq.i = 0;
    fermerCal();
    montrerEcran('seance');
    renderSeance();
  }

  // ⚠️ UNE comparaison, et c'est tout : le verdict qui FAIT FOI est celui
  // que le serveur calcule à la clôture (`Code/paliers.py::trancher`). Ici on
  // montre d'avance ce qu'il va dire, pas une seconde règle.
  function verdictLocal(p) {
    const v = sq.saisie[p.palier_id] && sq.saisie[p.palier_id].mesure;
    if (estNul(v) || !isFinite(v)) return null;
    return (p.sens === SENS_MOINS ? v <= p.cible : v >= p.cible) ? 'atteint' : 'manque';
  }
  const sqFaits = () => sq.paliers.filter(p => verdictLocal(p)).length;

  function renderSeance() {
    const z = $('#cv2-ecran-seance');
    const s = sq.session || {};
    const n = sq.paliers.length;
    z.innerHTML = `
      <header class="sq-tete">
        <div class="sq-tete-in">
          <button type="button" class="ev-retour" data-cal>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 6l-6 6 6 6"/></svg>
            ${esc(T('ses_cal'))}</button>
          <div class="sq-quand">
            <p class="k">${esc(T('sq_titre'))}</p>
            <p class="v">${esc(fmtDate(s.date_prevue))}</p>
          </div>
          <span class="ev-sep"></span>
          <span class="ev-av">${esc(initials(...String(s.nom || '').split(' ')))}</span>
          <div class="ev-qui"><p class="n">${esc(s.nom || '')}</p><p class="s">${esc(s.role || '')}</p></div>
          <span class="ev-pousse"></span>
          <div class="sq-compte"><p class="v">${sqFaits()}<span>/ ${n}</span></p>
            <p class="d">${esc(T('sq_tranches'))}</p></div>
        </div>
        <div class="sq-file" id="sq-file"></div>
      </header>
      <div class="sq-corps" id="sq-corps"></div>
      <div class="sq-bas">
        <section class="sq-liste" id="sq-liste"></section>
        <section class="ev-carte sq-clore" id="sq-clore"></section>
      </div>`;
    z.querySelector('[data-cal]').onclick = () => ouvrirCalendrier(sq.sid);
    rendreFile(); rendreCourant(); rendreListeSeance(); rendreClore();
    z.scrollIntoView({ block: 'start' });
  }

  function rendreFile() {
    const f = $('#sq-file'); f.innerHTML = '';
    sq.paliers.forEach((p, i) => {
      const v = verdictLocal(p);
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'sq-f' + (i === sq.i ? ' est-courant' : (v ? ' est-fait' : ''));
      el.innerHTML = `<span class="h">
          <span class="p">${v === 'atteint' ? '<i class="fa-solid fa-check"></i>'
            : (v === 'manque' ? '<i class="fa-solid fa-xmark"></i>' : (i + 1))}</span>
          <span class="t">${esc(p.sortie)}</span></span>
        <span class="d">${v ? esc(fmtVal(sq.saisie[p.palier_id].mesure, p.unite) + ' · '
              + T(v === 'atteint' ? 'pal_atteint' : 'pal_manque'))
            : (i === sq.i ? esc(T('sq_en_cours')) : esc(p.activite))}</span>`;
      el.onclick = () => { sq.i = i; rendreFile(); rendreCourant(); };
      f.appendChild(el);
    });
  }

  function rendreCourant() {
    const box = $('#sq-corps'); box.innerHTML = '';
    if (!sq.paliers.length) {
      box.innerHTML = `<p class="pal-vide">${esc(T('sq_vide'))}</p>`;
      return;
    }
    const p = sq.paliers[sq.i];
    const saisi = sq.saisie[p.palier_id] || {};
    box.innerHTML = `
      <div class="sq-sujet">
        <div class="t"><h1>${esc(p.sortie)}</h1>
          <p>${esc(p.activite)}${p.norme ? ' · ' + esc(T('pal_norme')) + DP + esc(fmtVal(p.norme, p.unite))
            + ' ' + esc(p.sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins')) : ''}</p></div>
        <div class="c"><span class="k">${esc(T('pal_cible'))}</span>
          <span class="v">${esc(fmtVal(p.cible, p.unite))}</span></div>
      </div>
      ${p.progression ? `<div class="sq-rail">${railHtml(p.progression)}</div>`
        : '<div class="sq-rail"></div>'}
      <div class="sq-geste">
        <label for="sq-m">${esc(T('sq_q'))}</label>
        <div class="sq-champ">
          <input id="sq-m" type="text" inputmode="decimal"
                 value="${esc(estNul(saisi.mesure) ? '' : fmtNb(saisi.mesure))}">
          <span class="u">${esc(p.unite || '')}</span>
        </div>
        <div class="sq-verdict" id="sq-verdict"></div>
        <label for="sq-p">${esc(T('sq_observe'))}</label>
        <textarea id="sq-p" rows="3" placeholder="${esc(T('sq_observe_ph'))}">${esc(saisi.preuve || '')}</textarea>
        <div class="sq-boutons">
          <button type="button" class="btn btn-ghost" data-passer>${esc(T('sq_passer'))}</button>
          <button type="button" class="pal-b pal-b--prim" data-suivant>
            <span class="pal-b-ic"><i class="fa-solid fa-arrow-right"></i></span>
            ${esc(sq.i === sq.paliers.length - 1 ? T('sq_dernier') : T('sq_suivant'))}</button>
        </div>
      </div>`;

    const inp = box.querySelector('#sq-m'), ta = box.querySelector('#sq-p');
    // ⚠️ On met à jour SUR PLACE : réécrire la page à chaque frappe ferait
    // perdre le curseur du champ qu'on est en train de taper.
    const lire = () => {
      const v = parseFloat((inp.value || '').replace(',', '.'));
      if (isFinite(v)) sq.saisie[p.palier_id] = { mesure: v, preuve: ta.value };
      else delete sq.saisie[p.palier_id];
      rendreVerdict(p); rendreFile(); rendreListeSeance(); rendreClore();
      const c = $('.sq-compte .v');
      if (c) c.innerHTML = sqFaits() + '<span>/ ' + sq.paliers.length + '</span>';
    };
    inp.oninput = lire;
    ta.oninput = () => { if (sq.saisie[p.palier_id]) sq.saisie[p.palier_id].preuve = ta.value; };
    box.querySelector('[data-passer]').onclick = () => avancerSeance();
    box.querySelector('[data-suivant]').onclick = () => { lire(); avancerSeance(); };
    rendreVerdict(p);
    inp.focus();
  }

  function rendreVerdict(p) {
    const z = $('#sq-verdict'); if (!z) return;
    const v = verdictLocal(p);
    if (!v) { z.className = 'sq-verdict'; z.innerHTML = ''; return; }
    const ok = v === 'atteint';
    z.className = 'sq-verdict est-' + (ok ? 'ok' : 'ko');
    z.innerHTML = `<span class="p"><i class="fa-solid fa-${ok ? 'check' : 'xmark'}"></i></span>
      <div><p class="t">${esc(T(ok ? 'pal_atteint' : 'pal_manque'))}</p>
      <p class="d">${esc(ok ? '' : T('pal_apres_echec'))}</p></div>`;
  }

  function avancerSeance() {
    const suivant = sq.paliers.findIndex((p, i) => i > sq.i && !verdictLocal(p));
    sq.i = suivant >= 0 ? suivant : Math.min(sq.i + 1, sq.paliers.length - 1);
    rendreFile(); rendreCourant();
  }

  function rendreListeSeance() {
    const z = $('#sq-liste'); if (!z) return;
    let h = `<div class="sq-liste-h"><h2>${esc(T('sq_liste'))}</h2>
      <span>${esc(T('sq_liste_d'))}</span></div>`;
    sq.paliers.forEach((p, i) => {
      const v = verdictLocal(p);
      const cls = v === 'atteint' ? 'ok' : (v === 'manque' ? 'ko' : (i === sq.i ? 'cur' : ''));
      h += `<button type="button" class="sq-l sq-l--${cls || 'att'}" data-i="${i}">
          <span class="p">${v === 'atteint' ? '<i class="fa-solid fa-check"></i>'
            : (v === 'manque' ? '<i class="fa-solid fa-xmark"></i>' : (i + 1))}</span>
          <span class="t"><span class="n">${esc(p.sortie)}</span>
            <span class="a">${esc(p.activite)} · ${esc(Tv('sq_cible_de', { v: fmtVal(p.cible, p.unite) }))}
              ${esc(p.sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins'))}</span></span>
          ${v ? `<span class="m">${esc(fmtVal(sq.saisie[p.palier_id].mesure, p.unite))}</span>
                 <span class="v v--${v === 'atteint' ? 'ok' : 'ko'}">${esc(T(v === 'atteint' ? 'pal_atteint' : 'pal_manque'))}</span>`
              : `<span class="e">${esc(i === sq.i ? T('sq_en_cours') : T('sq_a_venir'))}</span>`}
        </button>`;
    });
    z.innerHTML = h;
    z.querySelectorAll('[data-i]').forEach(b => b.onclick = () => {
      sq.i = +b.dataset.i; rendreFile(); rendreCourant(); rendreListeSeance();
    });
  }

  function rendreClore() {
    const z = $('#sq-clore'); if (!z) return;
    const faits = sqFaits(), reste = sq.paliers.length - faits;
    const tenue = (sq.session || {}).statut === 'tenue';
    z.innerHTML = `<p class="k">${esc(T('sq_clore_t'))}</p>
      <p class="d">${esc(T('sq_clore_d'))}</p>
      <button type="button" class="pal-b pal-b--prim sq-clore-b" data-clore ${faits ? '' : 'disabled'}>
        <span class="pal-b-ic"><i class="fa-solid fa-gavel"></i></span>${esc(T('sq_clore_t'))}</button>
      <p class="r">${esc(tenue ? Tv('sq_tenue_le', { d: fmtDate(sq.session.tenue_le) })
        : (reste ? nf('sq_reste', reste) : nf('sq_prete', faits)))}</p>`;
    const b = z.querySelector('[data-clore]');
    if (b && faits) b.onclick = cloturerSeance;
  }

  async function cloturerSeance() {
    const mesures = sq.paliers.filter(p => verdictLocal(p)).map(p => ({
      palier_id: p.palier_id, mesure: sq.saisie[p.palier_id].mesure,
      preuve: sq.saisie[p.palier_id].preuve || '' }));
    if (!mesures.length) return;
    const res = await api(`/paliers/session/${sq.sid}/cloturer`, {
      method: 'POST', body: JSON.stringify({ mesures: mesures }) });
    if (res.__error) return;
    toast(T('ses_close_ok'));
    // ⚠️ On revient sur le RÔLE, pas sur la séance : elle est tenue, il n'y a
    // plus rien à y faire — et les niveaux qu'elle vient de déplacer se lisent
    // dans la liste des activités.
    await refreshDashboard();
    if (state.activity) await ouvrirEvaluation(state.activity);
    else chargerSynthese();
    if ((res.manques || []).length) toast(T('pal_tranche_ko'));
  }


  // ══ LE CALENDRIER : une PAGE, plus une fenêtre ═════════════════════
  // ⚠️ Enfermé dans une pop-up, le mois et la séance choisie se disputaient
  // 1180 px — 944 réels au zoom .8. Le calendrier est une vue, pas un
  // dialogue : il prend la page, comme l'évaluation et la séance.

  function enteteSombre(retour, bloc, droite) {
    return `<div class="ev-tete-in">
        <button type="button" class="ev-retour" data-retour>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 6l-6 6 6 6"/></svg>
          ${esc(retour)}</button>
        <span class="ev-sep"></span>
        ${bloc}
        <span class="ev-pousse"></span>
        ${droite || ''}
      </div>`;
  }

  async function ouvrirCalendrier(sessionId) {
    if (state.ecran !== 'cal') cal.retour = state.ecran || 'synthese';
    montrerEcran('cal');
    showBusy(null, '#cv2-ecran-cal');
    const d = await api('/paliers/calendrier');
    if (d.__error) return;
    cal.sessions = d.sessions || [];
    cal.compteurs = d.compteurs || {};
    const urgente = cal.sessions.find(s => s.en_retard)
      || cal.sessions.find(s => s.statut === 'prevue')
      || cal.sessions[cal.sessions.length - 1];
    cal.choisie = sessionId || (urgente && urgente.id) || null;
    if (!cal.mois) {
      const ref = cal.sessions.find(s => s.id === cal.choisie) || urgente;
      const j = dateJour((ref && ref.date_prevue) || d.aujourdhui) || new Date();
      cal.mois = new Date(j.getFullYear(), j.getMonth(), 1);
    }
    rendreCal();
    if (cal.choisie) await chargerSession(cal.choisie);
  }

  function fermerCal() {
    if (state.ecran !== 'cal') return;
    if (cal.retour === 'eval' && state.activity) ouvrirEvaluation(state.activity);
    else chargerSynthese();
  }

  function rendreCal() {
    const z = $('#cv2-ecran-cal');
    const peut = state.estDev && state.roleId && state.cible;
    z.innerHTML = `
      <header class="ev-tete">
        ${enteteSombre(T('back_synthese'),
          `<div class="sq-quand"><p class="k">${esc(T('ses_titre'))}</p>
             <p class="v">${esc(T('ses_cal'))}</p></div>`,
          peut ? `<button type="button" class="pal-b pal-b--prim" data-planif>
              <span class="pal-b-ic"><i class="fa-solid fa-calendar-plus"></i></span>${esc(T('ses_planifier'))}</button>` : '')}
      </header>
      <div class="cal-tuiles">
        ${tuileCal('en_retard', 'ses_en_retard', 'rouge')}
        ${tuileCal('semaine', 'ses_semaine', 'ambre')}
        ${tuileCal('mois', 'ses_mois', 'bleu')}
        ${tuileCal('tenues_annee', 'ses_tenues', 'vert')}
      </div>
      ${cal.filtre ? `<div class="cal-filtre">
          <span class="k">${esc(nf('ses_f_actif', visibles().length, T(LIB_TUILE[cal.filtre])))}</span>
          <button type="button" class="cal-f-off" data-foff>
            <i class="fa-solid fa-xmark"></i>${esc(T('ses_f_tout'))}</button>
        </div>` : ''}
      <div class="cal-duo">
        <div class="cal-mois" id="cal-mois"></div>
        <div class="cal-detail" id="cal-detail">
          <p class="pal-vide">${esc(T('ses_choisir_une'))}</p>
        </div>
      </div>`;
    z.querySelector('[data-retour]').onclick = fermerCal;
    const bp = z.querySelector('[data-planif]');
    if (bp) bp.onclick = () => formSession();
    z.querySelectorAll('[data-f]').forEach(b => b.onclick = () => filtrerCal(b.dataset.f));
    const bf = z.querySelector('[data-foff]');
    if (bf) bf.onclick = () => filtrerCal(cal.filtre);
    rendreMois();
    z.scrollIntoView({ block: 'start' });
  }

  // ══ Les deux explications, derrière un « i » ═══════════════════════
  // ⚠️ Écrites en clair, elles occupaient la place de ce qu'on vient lire.
  // Derrière un « i » elles restent accessibles sans encombrer : la règle du
  // MINIMUM et l'échelle 0→4 s'expliquent une fois, pas à chaque regard.
  function boutonInfo(titre, texte) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'cv2-i ev-i';
    b.setAttribute('aria-label', titre);
    b.innerHTML = '<i class="fa-solid fa-info"></i>';
    brancherInfo(b, titre, texte);
    return b;
  }

  // ══ L'accueil : les prochaines séances ════════════════════════════
  // La vue d'ensemble disait où en est la personne, jamais ce qui l'attend.
  async function rendreSeances() {
    const z = $('#cv2-seances'); if (!z) return;
    const d = await api('/paliers/calendrier', undefined, true);
    if (!d || d.__error) { z.classList.add('hidden'); return; }
    const miennes = (d.sessions || [])
      .filter(x => x.user_id === state.cible && x.statut === 'prevue')
      .slice(0, 4);
    z.classList.remove('hidden');
    z.innerHTML = `
      <div class="cv2-sea-h">
        <span class="k"><i class="fa-regular fa-calendar"></i>${esc(T('cal_seances'))}</span>
        <button type="button" class="cv2-sea-tout" data-cal>${esc(T('cal_voir_tout'))}
          <i class="fa-solid fa-arrow-right"></i></button>
      </div>
      ${miennes.length ? `<div class="cv2-sea-l">${miennes.map(x => `
        <button type="button" class="cv2-sea${x.en_retard ? ' est-tard' : ''}" data-ses="${x.id}">
          <span class="d">${esc(fmtDate(x.date_prevue))}</span>
          <span class="q">${esc(quandDit(x.date_prevue))}</span>
          <span class="r">${esc(x.role || '')}</span>
          <span class="n">${esc(x.a_trancher
            ? nf('ses_a_trancher', x.a_trancher) : T('ses_prevue'))}</span>
        </button>`).join('')}</div>`
        : `<p class="cv2-sea-vide">${esc(T('cal_aucune_a_venir'))}</p>`}`;
    z.querySelector('[data-cal]').onclick = () => ouvrirCalendrier();
    z.querySelectorAll('[data-ses]').forEach(b =>
      b.onclick = () => ouvrirCalendrier(+b.dataset.ses));
  }

  const texteMinimum = () => T('ev_min_i');
  const texteEchelle = () => [
    T('pal_comment_0'), T('pal_comment_1'), T('pal_comment_2'),
    T('pal_comment_3'), T('pal_comment_4'),
  ].map((l, i) => i + ' · ' + l).join('\n');

})();
