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
      ax_col_sorties: 'Ce que l’activité produit · et sa norme',
      ax_col_tenu: 'Le niveau tenu',
      ax_attendu: 'attendu',
      ax_detail: 'Ouvrir le détail',
      ax_pas_notee: 'Pas encore notée',
      ax_effacer: 'Effacer la note',
      nt_foi: 'Ce qui fait foi',
      nt_mienne: 'la vôtre',
      nt_mesure: 'la mesure',
      nt_auto: 'Ce que [[x]] se donne',
      nt_auto_moi: 'Ce que vous vous donnez',
      nt_rien: 'non posée',
      ou_notez: 'Ce que vous notez',
      ou_comp: 'la compétence principale',
      ou_collab: 'le collaborateur',
      ou_role: 'le rôle',
      ou_act: "l'activité",
      ou_attendu: 'attendu [[n]]',
      ou_voir_role: 'Voir ce rôle activité par activité',
      ou_manque_1: '1 sortie pas encore notée',
      ou_manque_n: '[[n]] sorties pas encore notées',
      ou_n_sorties_1: '1 sortie à ce niveau',
      ou_n_sorties_n: '[[n]] sorties à ce niveau',
      ou_ecart: 'en écart · −[[n]]',
      ou_au_niveau: 'au niveau',
      ou_au_dessus: 'au niveau · +[[n]]',
      so_main: 'jugée à la main',
      so_mesuree: 'mesurée',
      vo_couv: 'couverture',
      vo_roles_1: 'rôle', vo_roles_n: 'rôles',
      vo_acts_1: 'activité', vo_acts_n: 'activités',
      vo_sorties_1: 'sortie', vo_sorties_n: 'sorties',
      vo_tout_en_bas: 'Ce qui tient tout en bas',
      vo_classement: 'Le classement — cliquez une activité',
      vo_produit: 'Ce que produit',
      vo_marches: 'Ses marches de performance',
      vo_sortie_suiv: 'Sortie suivante', vo_sortie_prec: 'Sortie précédente',
      vo_ouvrir: 'Ouvrir cette activité',
      vo_sans_marche: 'Aucune sortie mesurée sur cette activité : rien à relever en séance.',
      vo_sans_sortie: "Cette activité n'a pas encore de sortie à évaluer.",
      vo_au_plus: 'au plus', vo_au_moins: 'au moins',
      vo_notes: "Toutes les notes, d'un coup",
      vo_notees: '[[n]] / [[t]] notées',
      vo_aucune_sortie: 'aucune sortie',
      vo_leg_sous: "sous l'attendu", vo_leg_atteint: 'attendu atteint',
      vo_leg_mesure: 'relevé en séance', vo_leg_rien: 'pas de note',
      vo_bouge: 'Comment « [[x]] » a bougé',
      vo_pas_qualifie: 'la norme reste à franchir',
      cl_prec: 'Activité précédente',
      cl_suiv: 'Activité suivante',
      cl_seance: 'Séance',
      cl_tech_0: 'aucun domaine',
      cl_tech_1: '1 domaine',
      cl_tech_n: '[[n]] domaines',
      tech_cat_1: '1 domaine dans le catalogue',
      tech_cat_n: '[[n]] domaines dans le catalogue',
      cl_tech_ecart_1: '1 en écart',
      cl_tech_ecart_n: '[[n]] en écart',
      grv_mesure: 'mesuré [[x]]',
      nota_zero: 'Non évalué n’est pas zéro : [[b]]zéro se pose[[/b]], et il veut dire « non démontré ».',
      nota_mes_ko: 'La norme n’est pas encore atteinte : c’est la mesure qui fera monter le niveau.',
      pr_k: 'La preuve',
      pr_vide: 'Ce sur quoi vous vous appuyez pour poser ce niveau.',
      ax_reprendre: 'à reprendre',
      ax_reussi: 'réussi quand',
      ax_sans_norme: 'pas de norme chiffrée',
      ax_en_attente_1: '1 note posée, pas encore enregistrée',
      ax_en_attente_n: '{n} notes posées, pas encore enregistrées',
      ev_min_i: "Le niveau d'une activité est le PLUS BAS de ses sorties, jamais leur moyenne : on ne tient une activité que si on tient tout ce qu'elle produit. Une sortie non évaluée ne compte pas pour zéro — elle laisse le niveau en attente.",
      sq_prete_1: 'La mesure est prête.',
      ev_retour_role: 'Retour au rôle',
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
      pal_norme_deja_c: "Elle vit sur la sortie, pas sur la personne : on ne redemande que la mesure.",
      pal_trancher_ok: 'Enregistrer la mesure',
      pf_contre: 'contre une cible de [[c]]',
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
      pal_audela_tag: 'Au-delà',
      pal_mesure_k: 'mesuré',
      pal_sans_norme: 'Jugée à la main',
      fi_sujet: "Ce qu'on juge",
      fi_pose: "Ce qu'on pose",
      fi_requis: 'Requis par le rôle',
      fi_sans_requis: 'Aucun niveau attendu',
      fi_suivre: 'La suivre en paliers mesurés',
      fi_suivre_d: "Donnez-lui un chiffre attendu, et son niveau se déduira de ce qu'on relève en séance.",
      pal_sans_norme_d: "Cette sortie n'a pas de chiffre attendu : son niveau se pose sur l'échelle ci-dessus. Donnez-lui la norme de l'entreprise pour la suivre en paliers mesurés.",
      pal_definir_norme: "Définir la norme de l'entreprise",
      pal_indic: 'Indicateur de performance',
      pal_indic_ou: 'noté sur la connexion, dans la liste des activités',
      pal_norme_vient: "Reprise de l'indicateur noté dans la liste des activités (« [[x]] ») — corrigez-la si besoin.",
      ses_verdicts_t: 'Comment le verdict tombe',
      pal_audela_d: "un palier de mieux que l'attendu",
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
      conf_open: "Configurer l'activité",
      conf_sans_norme_1: '1 sortie sans norme', conf_sans_norme_n: '[[n]] sorties sans norme',
      conf_tout_norme: 'toutes chiffrées',
      conf_std: 'Réussi quand…', conf_std_lu: 'Réussi quand :', conf_std_ph: 'ex. : validé par le client sans reprise',
      conf_norme: "La norme de l'entreprise",
      conf_norme_i: "Un chiffre et un sens. Avec eux, le niveau de cette sortie se "
        + "DÉDUIT de ce qu'on relève en séance, et il n'y a plus de note à poser à la "
        + "main. Sans eux, elle se juge de 0 à 4. La norme appartient à l'activité, "
        + "pas à la personne : elle est la même pour tous ceux qui la tiennent.",
      conf_norme_off: 'Laissez la valeur vide : cette sortie se jugera à la main, de 0 à 4.',
      conf_prop: 'Proposé d\u2019après cette phrase : [[x]]',
      conf_prop_ok: 'Utiliser',
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
      pick_level: 'À évaluer',
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
      // La GALERIE d'accueil. `p_coverage`, `b_held`/`b_gap`/`b_todo`/`b_setup`
      // et `r_activity_*` sont ceux de la vue d'ensemble : un seul vocabulaire.
      g_team: "Où en est votre équipe ?", g_back: "L'équipe",
      g_open: 'Ouvrir son dossier', g_search: 'Rechercher un collaborateur',
      g_nores: 'Aucun collaborateur ne porte ce nom.',
      g_profil: 'Profil de [[n]]',
      g_noted_1: '[[n]] activité notée sur [[t]]',
      g_noted_n: '[[n]] activités notées sur [[t]]',
      g_no_act: 'Pas encore de quoi tracer un profil',
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
      // le plan en PAGE : la frise, le classement, le verdict unique
      plan_vise: 'visé',
      plan_hors: 'ne rentre pas dans la durée visée',
      plan_manque_k: 'il manque',
      plan_reste_k: 'il reste',
      plan_cl_t: 'Ce qui manque',
      plan_che_t: 'Le chemin',
      plan_cl_dem: 'démontré',
      plan_cl_req: 'requis par le rôle',
      plan_gap_n: '[[n]] activités en écart',
      plan_retour: 'Retour',
      plan_juste_b: 'Au plus juste',
      plan_seance_b: 'Caler sur la séance',
      plan_none_t: 'Aucun écart sur ce rôle',
      plan_none_d: "Le niveau requis est tenu partout : il n'y a rien à combler.",
      plan_empty_t: 'Pas encore de plan',
      plan_empty_d: "Partez d'une proposition, puis ajustez les charges et les curseurs jusqu'à ce que le plan tienne dans le temps disponible.",
      plan_propose: 'Proposer un plan', plan_repropose: 'Proposer à nouveau',
      plan_save: 'Enregistrer le plan', plan_saved: 'Plan enregistré',
      plan_hours_week: 'Heures par semaine', plan_weeks: 'Durée visée',
      plan_week_unit: 'sem.', plan_h: 'h',
      plan_ok: 'Le plan tient dans [[s]] semaines à [[h]] h par semaine.',
      plan_tendu: 'Ça passe de justesse — aucune marge en cas d’imprévu.',
      plan_trop: 'Il faudrait [[s]] semaines à ce rythme, ou [[h]] h par semaine sur la durée visée.',
      plan_source_ai: 'Proposé par l’IA — à relire et ajuster',
      plan_source_local: 'Construit depuis les capacités en écart relevées en base (aucune clé IA)',
      plan_gap_1: '1 activité en écart',
      plan_del: 'Retirer cette action',
      plan_crit: 'Réussi quand',
      plan_other: 'Autres actions',
      plan_steps_1: '1 étape', plan_steps_n: '[[n]] étapes',
      plan_week_1: 'Semaine [[a]]', plan_week_n: 'Semaines [[a]] → [[b]]',
      plan_week_over: 'dépasse la durée visée',
      plan_wk: 'S',
      plan_load: 'Charge en heures', plan_less: 'Moins d’heures', plan_more: 'Plus d’heures',
      plan_remove: 'Retirer',
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
      ax_col_sorties: 'What the activity produces · and its standard',
      ax_col_tenu: 'Level held',
      ax_attendu: 'expected',
      ax_detail: 'Open the detail',
      ax_pas_notee: 'Not rated yet',
      ax_effacer: 'Clear the rating',
      nt_foi: 'What counts',
      nt_mienne: 'yours',
      nt_mesure: 'the measurement',
      nt_auto: 'What [[x]] gives themselves',
      nt_auto_moi: 'What you give yourself',
      nt_rien: 'not set',
      ou_notez: 'What you are rating',
      ou_comp: 'the main competency',
      ou_collab: 'the person',
      ou_role: 'the role',
      ou_act: 'the activity',
      ou_attendu: 'target [[n]]',
      ou_voir_role: 'See this role activity by activity',
      ou_manque_1: '1 output not rated yet',
      ou_manque_n: '[[n]] outputs not rated yet',
      ou_n_sorties_1: '1 output at this level',
      ou_n_sorties_n: '[[n]] outputs at this level',
      ou_ecart: 'below target · −[[n]]',
      ou_au_niveau: 'on target',
      ou_au_dessus: 'on target · +[[n]]',
      so_main: 'rated by hand',
      so_mesuree: 'measured',
      vo_couv: 'coverage',
      vo_roles_1: 'role', vo_roles_n: 'roles',
      vo_acts_1: 'activity', vo_acts_n: 'activities',
      vo_sorties_1: 'output', vo_sorties_n: 'outputs',
      vo_tout_en_bas: 'What sits lowest',
      vo_classement: 'The ranking — click an activity',
      vo_produit: 'What this produces',
      vo_marches: 'Its performance steps',
      vo_sortie_suiv: 'Next output', vo_sortie_prec: 'Previous output',
      vo_ouvrir: 'Open this activity',
      vo_sans_marche: 'No measured output on this activity: nothing to record in a session.',
      vo_sans_sortie: 'This activity has no output to assess yet.',
      vo_au_plus: 'at most', vo_au_moins: 'at least',
      vo_notes: 'Every rating at once',
      vo_notees: '[[n]] / [[t]] rated',
      vo_aucune_sortie: 'no output',
      vo_leg_sous: 'below target', vo_leg_atteint: 'target met',
      vo_leg_mesure: 'recorded in a session', vo_leg_rien: 'not rated',
      vo_bouge: 'How “[[x]]” moved',
      vo_pas_qualifie: 'the standard is not met yet',
      cl_prec: 'Previous activity',
      cl_suiv: 'Next activity',
      cl_seance: 'Session',
      cl_tech_0: 'no domain',
      cl_tech_1: '1 domain',
      cl_tech_n: '[[n]] domains',
      tech_cat_1: '1 domain in the catalogue',
      tech_cat_n: '[[n]] domains in the catalogue',
      cl_tech_ecart_1: '1 short',
      cl_tech_ecart_n: '[[n]] short',
      grv_mesure: 'measured [[x]]',
      nota_zero: 'Not assessed is not zero: [[b]]zero is set[[/b]], and it means “not demonstrated”.',
      nota_mes_ko: 'The standard is not met yet: the measurement is what raises the level.',
      pr_k: 'Evidence',
      pr_vide: 'What you base this level on.',
      ax_reprendre: 'to take up',
      ax_reussi: 'successful when',
      ax_sans_norme: 'no numeric standard',
      ax_en_attente_1: '1 rating posted, not saved yet',
      ax_en_attente_n: '{n} ratings posted, not saved yet',
      ev_min_i: "An activity's level is the LOWEST of its outputs, never their average: you only hold an activity if you hold everything it produces. An output that has not been assessed does not count as zero — it leaves the level pending.",
      sq_prete_1: 'The measurement is ready.',
      ev_retour_role: 'Back to the role',
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
      pal_norme_deja_c: 'It lives on the output, not on the person: only the measurement is asked for.',
      pal_trancher_ok: 'Save the measurement',
      pf_contre: 'against a target of [[c]]',
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
      pal_audela_tag: 'Beyond',
      pal_mesure_k: 'measured',
      pal_sans_norme: 'Judged by hand',
      fi_sujet: 'What is being judged',
      fi_pose: 'What you set',
      fi_requis: 'Required by the role',
      fi_sans_requis: 'No target level',
      fi_suivre: 'Track it in measured steps',
      fi_suivre_d: 'Give it a target figure, and its level will follow from what is measured in session.',
      pal_sans_norme_d: 'This output has no expected figure: its level is set on the scale above. Give it the company standard to follow it as measured steps.',
      pal_definir_norme: 'Set the company standard',
      pal_indic: 'Performance indicator',
      pal_indic_ou: 'recorded on the connection, in the activity list',
      pal_norme_vient: 'Taken from the indicator recorded in the activity list (\u201c[[x]]\u201d) — correct it if needed.',
      ses_verdicts_t: 'How the verdict is reached',
      pal_audela_d: 'one step better than expected',
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
      conf_open: 'Configure the activity',
      conf_sans_norme_1: '1 output without a standard',
      conf_sans_norme_n: '[[n]] outputs without a standard',
      conf_tout_norme: 'all quantified',
      conf_std: 'Done well when…', conf_std_lu: 'Done well when:', conf_std_ph: 'e.g. approved by the client with no rework',
      conf_norme: 'The company standard',
      conf_norme_i: 'A figure and a direction. With them, this output\u2019s level is '
        + 'DERIVED from what is measured in a session, and there is no level left to set '
        + 'by hand. Without them, it is judged from 0 to 4. The standard belongs to the '
        + 'activity, not to the person: it is the same for everyone who holds it.',
      conf_norme_off: 'Leave the value empty: this output will be judged by hand, from 0 to 4.',
      conf_prop: 'Suggested from this sentence: [[x]]',
      conf_prop_ok: 'Use it',
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
      pick_level: 'To assess',
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
      g_team: 'Where does your team stand?', g_back: 'The team',
      g_open: 'Open their file', g_search: 'Search for a team member',
      g_nores: 'No team member by that name.',
      g_profil: 'Profile of [[n]]',
      g_noted_1: '[[n]] activity assessed out of [[t]]',
      g_noted_n: '[[n]] activities assessed out of [[t]]',
      g_no_act: 'Not enough yet to plot a profile',
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
      // le plan en PAGE : la frise, le classement, le verdict unique
      plan_vise: 'target',
      plan_hors: 'does not fit the target duration',
      plan_manque_k: 'short by',
      plan_reste_k: 'slack',
      plan_cl_t: 'What is missing',
      plan_che_t: 'The path',
      plan_cl_dem: 'demonstrated',
      plan_cl_req: 'required by the role',
      plan_gap_n: '[[n]] activities in gap',
      plan_retour: 'Back',
      plan_juste_b: 'Tightest fit',
      plan_seance_b: 'Fit to the session',
      plan_none_t: 'No gap on this role',
      plan_none_d: 'The required level is met everywhere: there is nothing to close.',
      plan_empty_t: 'No plan yet',
      plan_empty_d: 'Start from a proposal, then adjust the workloads and the sliders until the plan fits the time available.',
      plan_propose: 'Propose a plan', plan_repropose: 'Propose again',
      plan_save: 'Save plan', plan_saved: 'Plan saved',
      plan_hours_week: 'Hours per week', plan_weeks: 'Target duration',
      plan_week_unit: 'wk', plan_h: 'h',
      plan_ok: 'The plan fits in [[s]] weeks at [[h]] h per week.',
      plan_tendu: 'It just fits — no slack if anything slips.',
      plan_trop: 'You would need [[s]] weeks at this pace, or [[h]] h per week over the target duration.',
      plan_source_ai: 'Proposed by AI — review and adjust',
      plan_source_local: 'Built from the capability gaps recorded in the database (no AI key)',
      plan_gap_1: '1 activity in gap',
      plan_del: 'Remove this action',
      plan_crit: 'Done when',
      plan_other: 'Other actions',
      plan_steps_1: '1 step', plan_steps_n: '[[n]] steps',
      plan_week_1: 'Week [[a]]', plan_week_n: 'Weeks [[a]] → [[b]]',
      plan_week_over: 'runs past the target duration',
      plan_wk: 'W',
      plan_load: 'Workload in hours', plan_less: 'Fewer hours', plan_more: 'More hours',
      plan_remove: 'Remove',
      plan_gap_from_to: 'Current level → target level',
    },
  };
  // Clés communes aux deux langues, déclarées une fois.
  const COMMUN = {
    tech_demonstrated: { fr: 'Démontré', en: 'Demonstrated' },
    tech_add_ph: { fr: 'Nouveau domaine (ex. Plastique)…', en: 'New domain (e.g. Plastic)…' },
    tech_link: { fr: 'Ajouter', en: 'Add' },
    tech_pick: { fr: 'Choisir un domaine existant…', en: 'Pick an existing domain…' },
    tech_empty: { fr: 'Aucun domaine technique lié à cette activité.', en: 'No technical domain linked to this activity.' },
    tech_quoi: {
      fr: "[[b]]Un domaine technique, c'est le terrain sur lequel l'activité se joue[[/b]] — une matière, un procédé, une famille de machines. Il se règle une fois pour l'activité, puis chaque personne y a son niveau. [[b]]C'est un axe à part :[[/b]] on peut tenir une activité sans maîtriser tout son domaine, et l'inverse.",
      en: "[[b]]A technical domain is the ground the activity is played on[[/b]] — a material, a process, a family of machines. It is set once for the activity, then each person has their own level in it. [[b]]It is a separate axis:[[/b]] you can hold an activity without mastering all of its domain, and the other way round." },
    tech_les: { fr: 'Les domaines de cette activité', en: 'This activity\u2019s domains' },
    tech_requis_role: { fr: 'Requis par le rôle', en: 'Required by the role' },
    tech_lier_t: { fr: 'Rattacher un domaine qui existe', en: 'Link an existing domain' },
    tech_creer_t: { fr: 'ou en créer un', en: 'or create one' },
    tech_tenu: { fr: 'tenu', en: 'met' },
    tech_ecart: { fr: 'en écart · −[[n]]', en: 'short · −[[n]]' },
    tech_effacer: { fr: 'Effacer le niveau', en: 'Clear the level' },
    tech_note: {
      fr: 'Les niveaux se posent ici ; ils ne touchent pas à l\u2019évaluation de l\u2019activité.',
      en: 'Levels are set here; they do not affect the activity\u2019s evaluation.' },
    tech_dom: { fr: 'Domaine', en: 'Domain' },
    // ⚠️ Sans verdict pour un domaine NULL, la colonne s'effondre une ligne sur
    // trois — et « pas encore regardé » n'est pas « au niveau ».
    tech_nonsitue: { fr: 'non situé', en: 'not set' },
    tech_ajouter: { fr: 'Ajouter un domaine', en: 'Add a domain' },
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
    // La GALERIE d'accueil : les gens listés, leurs cartes, et le texte du
    // champ de recherche — il survit au re-rendu que fait le retour.
    gens: [], galerie: null, galQ: '',
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
  // Le seuil d'autonomie (CDC) : à défaut de niveau requis posé par le rôle,
  // c'est lui qui fait la couleur — « autonome / compétent », le palier à
  // partir duquel on tient l'activité sans appui.
  const SEUIL_TENU = 2;
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
    state.gens = gens;
    renderCollabs(gens);
    if (await ouvrirDemande(gens)) return;
    // Un seul dossier à regarder : on l'ouvre, personne n'a envie de cliquer
    // sur son propre nom pour entrer chez soi.
    if (gens.length === 1) { choisirCollab(gens[0], $('#cv2-collab').firstElementChild); return; }
    await ouvrirGalerie();
  }

  // ══ ÉCRAN 0 — la GALERIE ═══════════════════════════════════════════════
  // La page s'ouvrait sur une phrase dans un cadre pointillé : mesuré à
  // 1600 × 1000, 726 px de vide et 38 % de la largeur utilisée. Et la barre
  // des collaborateurs passait de 214 × 253 à gauche à 1373 × 67 en haut dès
  // qu'on choisissait quelqu'un — ce n'était plus le même objet.
  async function ouvrirGalerie() {
    montrerEcran('galerie');
    // ⚠️ On ne retient JAMAIS le rendu le temps d'une lecture : le squelette
    // part tout de suite, les chiffres arrivent ensuite. C'est la leçon de
    // `/panel`, qui attendait 25 s puis annonçait une panne.
    if (!state.galerie) showBusy(T('loading'), '#cv2-ecran-galerie');
    const g = await api('/mastery/galerie');
    if (g.__error) { montrerVide(T('req_failed')); return; }
    state.galerie = g;
    renderGalerie(g);
    const ret = $('#cv2-vers-galerie');
    if (ret) { ret.classList.remove('hidden'); ret.onclick = () => ouvrirGalerie(); }
  }

  // Minuscules sans accents : « Théo » se trouve en tapant « theo ».
  const pliage = s => String(s || '').toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '');

  function renderGalerie(g) {
    const zone = $('#cv2-ecran-galerie');
    const t = g.totaux || {};
    // La pastille ronde faisait double emploi avec le liseré de la tuile,
    // qui porte déjà la couleur de l'état — et c'est le même liseré que la
    // carte qu'elle résume.
    const tuile = (k, lbl, ton) =>
      `<div class="gal-t gal-t--${ton}">
         <span class="n">${t[k] || 0}</span><span class="k">${esc(T(lbl))}</span></div>`;
    zone.innerHTML = `
      <div class="gal-haut">
        <div class="gal-tuiles">
          ${tuile('held', 'b_held', 'g')}${tuile('gap', 'b_gap', 'r')}
          ${tuile('todo', 'b_todo', 'a')}${tuile('setup', 'b_setup', 'n')}
        </div>
        <label class="gal-rech">
          <i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i>
          <input type="search" id="gal-q" value="${esc(state.galQ || '')}"
                 placeholder="${esc(T('g_search'))}" aria-label="${esc(T('g_search'))}">
        </label>
      </div>
      <div class="gal-grille">${(g.gens || []).map(carteGal).join('')}</div>
      <p class="gal-rien hidden" id="gal-rien">${esc(T('g_nores'))}</p>`;

    zone.querySelectorAll('.gal-c').forEach(b => {
      b.onclick = () => {
        const u = (state.gens || []).find(x => String(x.id) === b.dataset.uid);
        if (u) choisirCollab(u);
      };
    });
    // ⚠️ `input`, pas `change` : `change` n'arrive qu'à la perte du focus, donc
    // le champ ne filtrerait rien pendant la frappe, sans la moindre erreur
    // pour le dire.
    const q = $('#gal-q');
    if (q) q.addEventListener('input', () => { state.galQ = q.value; filtrerGalerie(); });
    filtrerGalerie();
  }

  function carteGal(c) {
    const nom = `${c.first_name} ${c.last_name}`.trim();
    const cpt = c.compte || {};
    // La couleur du liseré dit ce qui ARRIVE en premier : un écart appelle une
    // action, une activité non évaluée un regard, le reste est tenu.
    const ton = cpt.gap ? 'r' : (cpt.todo ? 'a' : 'g');
    // La MÊME règle que le radar du dossier : un axe existe dès qu'il y a
    // QUELQUE CHOSE à y porter — un requis OU un démontré — et on garde les
    // plus parlantes, le serveur les ayant triées par écart croissant.
    const axes = (c.axes || []).filter(a =>
      (!estNul(a.required_level) && a.required_level > 0) || !estNul(a.demonstrated_level));
    const vus = axes.slice(0, RADAR_MAX_AXES);
    const ligne = (k, lbl, ton2) =>
      `<span class="gal-e"><i class="gal-p--${ton2}"></i><b>${cpt[k] || 0}</b>${esc(T(lbl))}</span>`;
    return `
      <button type="button" class="gal-c gal-c--${ton}" data-uid="${esc(c.user_id)}"
              data-nom="${esc(pliage(nom))}">
        <span class="gal-c-h">
          <span class="gal-av">${esc(initials(c.first_name, c.last_name))}</span>
          <span class="gal-ident">
            <span class="gal-nom">${esc(nom)}</span>
            <span class="gal-roles">${(c.roles || []).map(r => `<i>${esc(r)}</i>`).join('')}</span>
          </span>
        </span>
        <span class="gal-c-b">
          <span class="gal-radar">${vus.length >= 3
            ? radarSVG(vus, { mini: true, R: 56, CX: 75, CY: 75,
                              titre: Tv('g_profil', { n: nom }) })
            : `<span class="gal-sans">${esc(T('g_no_act'))}</span>`}</span>
          <span class="gal-chif">
            <span class="gal-cov"><b>${estNul(c.couverture) ? '—'
              : c.couverture + '<small>%</small>'}</b><span>${esc(T('p_coverage'))}</span></span>
            <span class="gal-jauge"><i style="width:${estNul(c.couverture) ? 0 : c.couverture}%"></i></span>
            <span class="gal-etats">
              ${ligne('held', 'b_held', 'g')}${ligne('gap', 'b_gap', 'r')}
              ${ligne('todo', 'b_todo', 'a')}${ligne('setup', 'b_setup', 'n')}
            </span>
          </span>
        </span>
        <span class="gal-c-p">
          <span>${esc(nf('g_noted', c.n_evaluated || 0, c.n_activities || 0))}</span>
          <span class="go">${esc(T('g_open'))} →</span>
        </span>
      </button>`;
  }

  // ⚠️ On MASQUE, on ne re-rend pas : réécrire la grille à chaque frappe ferait
  // perdre le curseur du champ qu'on tape.
  function filtrerGalerie() {
    const q = pliage(state.galQ || '').trim();
    let n = 0;
    document.querySelectorAll('#cv2-ecran-galerie .gal-c').forEach(c => {
      const ok = !q || (c.dataset.nom || '').indexOf(q) >= 0;
      c.hidden = !ok;
      if (ok) n++;
    });
    const rien = $('#gal-rien');
    if (rien) rien.classList.toggle('hidden', n > 0);
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
      // La carte d'accueil ouvre un dossier sans passer par cette liste : elle
      // designe la ligne a allumer par son id.
      li.dataset.uid = u.id;
      li.innerHTML = `<span class="av">${esc(initials(u.first_name, u.last_name))}</span>` +
        `<span>${esc(u.first_name)} ${esc(u.last_name)}</span><span class="chev">›</span>`;
      li.onclick = () => choisirCollab(u, li);
      ul.appendChild(li);
    });
  }

  const ECRANS = ['#cv2-ecran-galerie', '#cv2-ecran-synthese', '#cv2-ecran-eval',
                  '#cv2-ecran-seance', '#cv2-ecran-cal', '#cv2-ecran-plan'];

  function montrerVide(msg) {
    ECRANS.forEach(s => $(s).classList.add('hidden'));
    pleineLargeur(false);
    const ph = $('#cv2-placeholder'); ph.classList.remove('hidden'); ph.textContent = msg;
  }
  function montrerEcran(nom) {
    state.ecran = nom;
    $('#cv2-placeholder').classList.add('hidden');
    $('#cv2-ecran-galerie').classList.toggle('hidden', nom !== 'galerie');
    $('#cv2-ecran-synthese').classList.toggle('hidden', nom !== 'synthese');
    $('#cv2-ecran-eval').classList.toggle('hidden', nom !== 'eval');
    $('#cv2-ecran-seance').classList.toggle('hidden', nom !== 'seance');
    $('#cv2-ecran-cal').classList.toggle('hidden', nom !== 'cal');
    $('#cv2-ecran-plan').classList.toggle('hidden', nom !== 'plan');
    // ⚠️ La GALERIE garde le bandeau de page (elle n'ecrit le nom de personne)
    // mais pas la barre : les cartes SONT la liste.
    pleineLargeur(nom !== 'synthese' && nom !== 'galerie');
    const lay = document.querySelector('.cv2-layout');
    if (lay && nom === 'galerie') lay.classList.add('hidden');
    // ⚠️ L'accueil se cadre plus étroit que le reste de la page, et c'est
    // ce qui l'aligne : à 1 760 px, trois cartes plafonnées à 460 px se
    // centraient en laissant 123 px de gouttière de chaque côté, pendant que
    // le bandeau et la rangée de compteurs allaient d'un bord à l'autre. À
    // 1 440 px, les trois cartes remplissent la largeur au pixel près.
    document.body.classList.toggle('a-cv2-galerie', nom === 'galerie');
    $('#cv2-sub').textContent = nom === 'galerie'
      ? T('g_team') : (state.cibleNom || T('pick_collab'));
    // ⚠️ Sur la VUE D'ENSEMBLE, la barre des collaborateurs passe EN HAUT :
    // en colonne elle prenait 268 px de large à une page qui en a besoin —
    // le bloc de nuit y porte deux colonnes, et le panneau des marches
    // débordait. Les autres écrans n'ont pas de barre du tout
    // (`pleineLargeur`), c'est donc le seul qui s'en sert.
    const l = document.querySelector('.cv2-layout');
    if (l) l.classList.toggle('est-large', nom === 'synthese');
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
    // Une carte d'accueil ouvre un dossier sans passer par la liste : on
    // retrouve sa ligne par l'id, sinon la barre n'allumerait personne.
    const ligne = li || document.querySelector(`.cv2-collab li[data-uid="${u.id}"]`);
    if (ligne) ligne.classList.add('active');
    state.cible = u.id; state.cibleNom = `${u.first_name} ${u.last_name}`.trim();
    $('#cv2-sub').textContent = state.cibleNom;
    await chargerSynthese();
  }

  // ⚠️ DEUX lectures, en PARALLÈLE. La synthèse porte les rôles et le profil
  // (le radar) ; l'aperçu porte les sorties, leurs notes et leurs paliers —
  // le classement, les marches, la bande et le relief. En série, c'est deux
  // allers vers la base pour une page qui se rouvre à chaque changement de
  // collaborateur.
  async function chargerSynthese() {
    const [d, ap] = await Promise.all([
      api(`/mastery/synthese/${state.cible}`),
      api(`/mastery/apercu/${state.cible}`),
    ]);
    if (d.__error) { montrerVide(T('req_failed')); return; }
    state.synthese = d;
    // ⚠️ Un échec sur l'aperçu n'emporte pas la page : le radar et les rôles
    // s'affichent, et les cartes qui en dépendent se retirent. C'est la leçon
    // de `/panel`, qui retenait son HTML le temps d'un appel et annonçait
    // ensuite une panne.
    state.apercu = ap.__error ? null : ap;
    montrerEcran('synthese');
    renderOeil(state.apercu);
    renderProfil(d);
    renderNotes(state.apercu);
    renderRelief(state.apercu);
    rendreSeances();
    const vide = $('#cv2-sans-role');
    if (vide) {
      vide.classList.toggle('hidden', !!d.roles.length);
      vide.textContent = d.roles.length ? '' : T('no_roles');
    }
  }

  // Une jauge + son libellé + son écart, réutilisée par la ligne de rôle et la
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

  // ══════════════════════════════════════════════════════════════════════
  // LA VUE D'ENSEMBLE — le classement, les marches, toutes les notes
  //
  // Tranchée sur maquette, à l'échelle. Elle ne portait que le radar et la
  // liste des rôles : on y lisait la FORME d'un profil, jamais ce qui le
  // retient. Elle porte maintenant, dans l'ordre où l'on se les pose :
  //   · ce qui tient tout en bas, et combien d'activités sont dans chaque état ;
  //   · le CLASSEMENT des activités, de la plus basse à la plus haute, et les
  //     MARCHES de celle qu'on choisit — deux choses qui ne se voyaient qu'en
  //     ouvrant l'écran d'évaluation, une activité à la fois ;
  //   · toutes les notes d'un coup, une ligne par activité, une cellule par
  //     sortie ;
  //   · le relief d'une sortie mesurée, et la prochaine séance.
  //
  // ⚠️ UNE seule lecture pour tout cela (`/mastery/apercu`), en un nombre FIXE
  // de requêtes : servir chaque activité séparément, c'est le défaut qui
  // mettait le tableau global de la page RH à deux minutes et demie.
  // ══════════════════════════════════════════════════════════════════════

  // Le classement : la hauteur d'une barre dit le niveau. Un pas de 34 px,
  // et un socle de 10 px pour que le niveau 0 se VOIE — à hauteur nulle il se
  // confondrait avec « pas de barre du tout », c'est-à-dire avec NULL.
  const CL_SOCLE = 10, CL_PAS = 34;
  const clH = n => CL_SOCLE + CL_PAS * n;

  function renderOeil(ap) {
    const z = $('#vo-nuit');
    if (!ap || !ap.activites.length) { z.classList.add('hidden'); return; }
    z.classList.remove('hidden');
    const c = ap.compte;
    z.innerHTML = `
      <div class="vo-htop">
        <div class="vo-hid">
          <p class="ou-lbl">${esc(T('ou_collab'))}</p>
          <h1>${esc(ap.user_name)}</h1>
          <div class="vo-chips">
            ${/* ⚠️ Le libellé est dans un <span> : le `gap` d'une boîte flex ne
                  s'applique qu'entre ÉLÉMENTS, et un nœud de texte nu n'en est
                  pas un — relevé à l'écran, « 3rôles » collé. */''}
            <span class="chip"><b>${ap.n_roles}</b><span>${esc(nf('vo_roles', ap.n_roles))}</span></span>
            <span class="chip"><b>${ap.n_activities}</b><span>${esc(nf('vo_acts', ap.n_activities))}</span></span>
            <span class="chip"><b>${ap.n_sorties}</b><span>${esc(nf('vo_sorties', ap.n_sorties))}</span></span>
            <span class="chip"><span>${esc(T('vo_couv'))}</span><b>${ap.couverture}&nbsp;%</b></span>
          </div>
        </div>
        <div class="vo-hbas">
          <p class="ou-lbl">${esc(T('vo_tout_en_bas'))}<span data-min></span></p>
          <p class="vo-grand">${estNul(ap.plus_bas) ? '—' : ap.plus_bas}<i>/4</i></p>
          <div class="vo-pann">
            ${[['held', 'b_held', 'g'], ['gap', 'b_gap', 'r'],
               ['todo', 'b_todo', 'a'], ['setup', 'b_setup', 'n']]
              .map(([k, lbl, t]) =>
                `<div><span class="e">${esc(T(lbl))}</span><span class="v ${t}">${c[k]}</span></div>`)
              .join('')}
          </div>
        </div>
      </div>

      <div class="vo-duo">
        <div class="vo-cl">
          <p class="vo-dt">${esc(T('vo_classement'))}</p>
          <div class="esc" id="vo-esc"></div>
          <div class="escn" id="vo-escn"></div>
        </div>
        ${/* ⚠️ Rien ne reliait les deux colonnes : on cliquait une barre à
              gauche et un panneau changeait à droite, sous un titre (« SES
              marches ») dont le « ses » ne désignait rien. Trois attaches : le
              panneau NOMME l'activité qu'il décrit, il prend SA couleur
              (liseré gauche, pastille, lien), et LE LIEN se trace du niveau
              de la barre choisie jusqu'à la pastille du panneau.

              ⚠️ La gouttière est une COLONNE de la grille, pas un `gap` : le
              lien doit avoir une boîte à lui pour s'y dessiner. Elle coûte
              36 px à la colonne du classement (le `gap` de 20 px disparaît,
              la colonne du lien en prend 56) — mesuré, et c'est le prix du
              trait. */''}
        <div class="vo-lane" id="vo-lane" aria-hidden="true"></div>
        <div class="vo-mp" id="vo-mp">
          <div class="vo-dth">
            <p class="vo-dt">${esc(T('vo_produit'))}</p>
            <div class="cl-nav hidden" id="vo-mnav"></div>
          </div>
          <p class="vo-sujet" id="vo-sujet"></p>
          <div class="mpan" id="vo-mpan"></div>
        </div>
      </div>`;
    z.querySelector('[data-min]').appendChild(boutonInfo(T('ev_min_t'), texteMinimum()));
    classement(ap);
  }

  // ── LE CLASSEMENT : de la plus basse à la plus haute ─────────────────
  // ⚠️ Une activité NON ÉVALUÉE n'a pas une barre à zéro : zéro veut dire
  // « non démontré », et tout le module distingue les deux. Elle porte une
  // barre hachurée et un « ? » — et celle qui n'a rien à évaluer, un « — »
  // et un simple socle : les deux absences ne se corrigent pas de la même
  // façon (l'une se note, l'autre se configure).
  function classement(ap) {
    const esc_ = $('#vo-esc'), noms = $('#vo-escn');
    esc_.innerHTML = ''; noms.innerHTML = '';
    if (!ap.activites.some(a => a.activity_id === state.voAct)) {
      state.voAct = ap.activites[0].activity_id;
    }
    ap.activites.forEach(a => {
      const vide = a.etat === 'setup';
      const niv = a.demonstrated_level;
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'st' + (a.activity_id === state.voAct ? ' on' : '');
      b.setAttribute('aria-label', a.activity_name + DP
        + (estNul(niv) ? T(vide ? 'b_setup' : 'b_todo') : niv + ' · ' + levelName(niv)));
      // ⚠️ La barre porte la couleur SÉMANTIQUE de l'activité, celle que le
      // serveur calcule (CDC 3.5) et qu'elle a partout ailleurs : rouge tant
      // que l'autonomie n'est pas démontrée, ambre pour un écart au requis,
      // vert quand il est tenu. La bande des notes, elle, a son propre
      // dégradé — elle montre des SORTIES, pas des activités, et elle porte
      // sa légende.
      const teinte = estNul(niv) ? 'q'
        : ({ green: 'g', orange: 'a', red: 'r' }[a.color] || 'b');
      b.innerHTML = `<span class="n${estNul(niv) ? ' q' : ''}">${estNul(niv) ? (vide ? '—' : '?') : niv}</span>
        <span class="bar ${teinte}" style="height:${estNul(niv) ? (vide ? 8 : clH(2)) : clH(niv)}px"></span>
        ${estNul(a.required_level) ? ''
          : `<span class="req" style="bottom:${clH(a.required_level)}px"></span>`}`;
      b.onclick = () => {
        state.voAct = a.activity_id; state.voMarche = 0;
        classement(ap); marches(ap);
      };
      esc_.appendChild(b);

      const n = document.createElement('span');
      n.className = (a.activity_id === state.voAct ? 'on' : '');
      n.textContent = a.activity_name;
      noms.appendChild(n);
    });
    marches(ap);
  }

  // ── LES MARCHES de l'activité choisie ────────────────────────────────
  // Le rail des marches est celui de l'écran d'évaluation : une sortie
  // mesurée se lit de la même façon partout, ou elle se lit deux fois.
  // ⚠️ UNE sortie à la fois, et des flèches pour passer à la suivante. Elles
  // étaient toutes empilées : mesuré à quatre sorties de quatre marches, le
  // panneau faisait 847 px — le bloc de nuit devenait quatre fois plus haut
  // que le classement d'à côté, et les rails se marchaient dessus.
  // ⚠️ La pastille de norme ne redit plus « NORME DE L'ENTREPRISE » : le
  // drapeau du rail le dit déjà, deux lignes plus bas. Elle ne garde que ce
  // que lui seul porte — la valeur et son sens (« ≤ 10 j »).
  // La teinte d'une activité, la MÊME des deux côtés : c'est elle qui dit
  // que le panneau de droite décrit la barre de gauche.
  // ⚠️ Chaque valeur est le HAUT du dégradé de SA barre
  // (`--cv-g-40`, `--cv-a-40`, `--cv-r-40`, et le bleu de `.bar.b`) : le liseré du
  // panneau doit tomber sur la même teinte que la barre choisie, sinon il ne la
  // désigne plus. Si l'une bouge, l'autre suit.
  const TEINTE = { g: '#bfe074', a: '#ecc45f', r: '#ef7396', b: '#7cb3fb' };
  const teinteDe = a => (estNul(a.demonstrated_level) ? 'rgba(255,255,255,.45)'
    : (TEINTE[{ green: 'g', orange: 'a', red: 'r' }[a.color]] || TEINTE.b));

  function marches(ap) {
    const z = $('#vo-mpan'), nav = $('#vo-mnav');
    if (!z) return;
    const a = ap.activites.find(x => x.activity_id === state.voAct);
    // ⚠️ Le sujet se nomme AVANT les marches : « ses marches » ne désignait
    // rien, et on ne savait pas de quelle barre ce panneau parlait.
    // ⚠️ La teinte se pose sur le DUO, pas sur le panneau : la barre choisie
    // et le panneau doivent lire la même, et elles vivent dans deux colonnes
    // sœurs.
    const duo = document.querySelector('#vo-nuit .vo-duo'), suj = $('#vo-sujet');
    if (duo) duo.style.setProperty('--vo-c', a ? teinteDe(a) : 'rgba(255,255,255,.3)');
    if (suj) {
      suj.innerHTML = a
        ? `<i class="vo-pt"></i><b>${esc(a.activity_name)}</b>` : '';
    }
    z.innerHTML = '';
    if (nav) { nav.innerHTML = ''; nav.classList.add('hidden'); }
    if (!a) { poserLien(); return; }
    const mes = a.sorties.filter(s => s.mesurable && s.norme);
    if (!mes.length) {
      z.innerHTML = `<p class="vo-rien">${esc(T(a.sorties.length ? 'vo_sans_marche' : 'vo_sans_sortie'))}</p>`;
    } else {
      if (!(state.voMarche >= 0) || state.voMarche >= mes.length) state.voMarche = 0;
      const s = mes[state.voMarche];
      const u = s.norme.unite ? ' ' + s.norme.unite : '';
      const signe = s.norme.sens === SENS_MOINS ? '≤ ' : '≥ ';
      z.innerHTML = `<div class="mh"><b>${esc(s.nom)}</b>
          <span class="nm2">${esc(signe + nombre(s.norme.valeur) + u)}</span>
        </div>${railHtml(s)}`;
      // ⚠️ Même règle que la navigation entre activités : une flèche qui ne
      // mène nulle part n'est pas un bouton. Pas de bouclage.
      if (nav && mes.length > 1) {
        nav.classList.remove('hidden');
        const fleche = sens => {
          const cible = mes[state.voMarche + sens];
          const b = document.createElement('button');
          b.type = 'button'; b.className = 'cl-nav-b'; b.dataset.sens = String(sens);
          const lbl = T(sens > 0 ? 'vo_sortie_suiv' : 'vo_sortie_prec') + ' · ' + cible.nom;
          b.title = lbl; b.setAttribute('aria-label', lbl);
          b.innerHTML = `<i class="fa-solid fa-chevron-${sens > 0 ? 'right' : 'left'}"></i>`;
          b.onclick = () => { state.voMarche += sens; marches(ap); };
          return b;
        };
        if (state.voMarche > 0) nav.appendChild(fleche(-1));
        const p = document.createElement('span');
        p.className = 'cl-nav-p';
        p.textContent = (state.voMarche + 1) + ' / ' + mes.length;
        nav.appendChild(p);
        if (state.voMarche < mes.length - 1) nav.appendChild(fleche(1));
      }
    }
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'pal-b pal-b--verre vo-ouvrir';
    b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-arrow-right"></i></span>`
      + esc(T('vo_ouvrir'));
    b.onclick = () => ouvrirDepuisApercu(a);
    z.appendChild(b);
    // ⚠️ APRÈS le panneau : le lien arrive sur la pastille du sujet, et on ne
    // mesure pas la position de quelque chose qui n'est pas encore écrit.
    poserLien();
  }

  // ══════════════════════════════════════════════════════════════════════
  // LE LIEN — du NIVEAU de la barre choisie jusqu'au panneau
  //
  // Tranché sur maquette (« L'entre-deux », cinq mouvements comparés à
  // l'échelle réelle) : le trait se tire, une lueur le parcourt une fois, et
  // la pointe se pose. C'est ce passage qui fait que quelque chose a CIRCULÉ
  // entre les deux colonnes, et pas seulement poussé.
  //
  // ⚠️ La version d'avant n'en gardait que la POINTE — un triangle de
  // bordure posé à un `top` fixe, sans tige : rien ne partait de la barre,
  // donc rien ne bougeait quand on en changeait. Et la pointe de la barre
  // choisie partait de son BAS, qui ne dit rien ; le lien part de son HAUT,
  // c'est-à-dire de son NIVEAU, qui est tout le propos de cette colonne.
  // ══════════════════════════════════════════════════════════════════════

  // DEUX points relevés sur la carte, et deux seulement : le haut de la barre
  // choisie, la pastille du panneau.
  // ⚠️⚠️ `getBoundingClientRect()` rend des pixels d'ÉCRAN, et `body.pg` porte
  // `zoom: .8` : la différence de deux rects est donc en px d'écran, alors
  // qu'on l'ÉCRIT dans le repère de la page. On divise à l'écriture, et on ne
  // multiplie nulle part — même correctif que la bulle du « i ». Sans lui le
  // tracé arrive 20 % trop haut.
  function geoLien() {
    const lane = $('#vo-lane');
    const bar = document.querySelector('#vo-esc .st.on .bar');
    if (!lane || !bar) return null;
    const L = lane.getBoundingClientRect();
    const z = parseFloat(getComputedStyle(document.body).zoom) || 1;
    const h = L.height / z;
    // ⚠️ Un volet replié, un onglet jamais peint, un parent masqué : tout rend
    // des rects NULS. On ne dessine alors RIEN plutôt qu'un tracé à des
    // coordonnées non finies — c'est le piège payé sur `fitView` de l'éditeur,
    // où un facteur nul avait fini en `<rect x="Infinity">`.
    if (!(h > 40) || !isFinite(h)) return null;
    const b = bar.getBoundingClientRect();
    const pt = document.querySelector('#vo-sujet .vo-pt');
    const r = pt && pt.getBoundingClientRect();
    const borne = v => Math.max(4, Math.min(h - 4, v));
    const y1 = borne((b.top - L.top) / z);
    const y2 = borne(r ? (r.top + r.height / 2 - L.top) / z : h / 2);
    if (!isFinite(y1) || !isFinite(y2)) return null;
    return { h: h, y1: y1, y2: y2 };
  }

  // ⚠️ La courbe part HORIZONTALEMENT de la barre et arrive HORIZONTALEMENT
  // sur la pastille (les deux poignées de la bézier sont posées à plat) :
  // c'est ce qui la fait sortir de la barre et entrer dans le panneau au lieu
  // de couper la gouttière en diagonale.
  function lienHtml(g) {
    const H = Math.round(g.h), y1 = Math.round(g.y1), y2 = Math.round(g.y2);
    const d = `M 1 ${y1} C 30 ${y1}, 20 ${y2}, 45 ${y2}`;
    return `<svg width="56" height="${H}" viewBox="0 0 56 ${H}">
        <path class="ln-halo" d="${d}" stroke="var(--vo-c)" stroke-width="11" opacity=".13"/>
        <path class="ln-trace" d="${d}" stroke="var(--vo-c)" stroke-width="1.9"/>
        <path class="ln-glint" d="${d}" stroke="#fff" stroke-width="2.4" opacity=".9"/>
      </svg>
      <i class="ln-src" style="top:${y1}px"></i>
      <i class="ln-tete" style="left:38px;top:${y2}px"></i>`;
  }

  function poserLien() {
    const lane = $('#vo-lane');
    if (!lane) return;
    const g = geoLien();
    if (!g) { lane.innerHTML = ''; return; }
    // ⚠️ On RECONSTRUIT le nœud : une animation CSS ne se rejoue pas sur un
    // élément qu'on laisse en place, et c'est à chaque changement d'activité
    // qu'on veut la revoir. Rien à remettre à zéro à la main.
    lane.innerHTML = lienHtml(g);
    // ⚠️ Un tracé se dessine par son POINTILLÉ, et seul le navigateur connaît
    // la longueur réelle du chemin : `--len` la lui demande.
    lane.querySelectorAll('.ln-halo, .ln-trace').forEach(p => {
      const l = Math.ceil(p.getTotalLength());
      p.style.setProperty('--len', l);
      p.style.strokeDasharray = l;
    });
    // ⚠️ La lueur garde SON pointillé — un éclat court qui défile : on ne lui
    // pose que la longueur, jamais le `stroke-dasharray` du tracé.
    lane.querySelectorAll('.ln-glint').forEach(p =>
      p.style.setProperty('--len', Math.ceil(p.getTotalLength())));
    surveillerLien(lane.parentElement);
  }

  // ⚠️ DEUX déclencheurs, et ils ne couvrent pas la même chose : `resize` dit
  // que la FENÊTRE a changé, l'observateur dit que la GRILLE a changé sans
  // elle — le détail des séances qui s'ouvre, le relief qui bascule, une
  // police qui arrive et déplace la pastille du panneau.
  // ⚠️ Il est GARDÉ dans une variable : sans référence vive, le navigateur
  // peut le ramasser, et le lien resterait au cadrage du premier rendu.
  const OBS_LIEN = typeof ResizeObserver === 'function'
    ? new ResizeObserver(() => poserLien()) : null;
  function surveillerLien(duo) {
    // Le duo est reconstruit à chaque rendu du profil : on ne l'observe
    // qu'une fois, et l'ancien nœud détaché ne coûte rien.
    if (!duo || !OBS_LIEN || duo.dataset.lienObs) return;
    duo.dataset.lienObs = '1';
    OBS_LIEN.observe(duo);
  }
  window.addEventListener('resize', poserLien);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(poserLien);

  // ⚠️ L'écran d'évaluation se cadre TOUJOURS sur un rôle : le niveau attendu
  // vient du rôle, pas de l'activité. On prend le premier qui la porte — et
  // on passe par le dashboard, qui remplit `state.rows` dont vivent les
  // flèches de navigation.
  async function ouvrirDepuisApercu(a) {
    const rid = (a.role_ids || [])[0];
    const r = (state.synthese && state.synthese.roles || []).find(x => x.role_id === rid);
    if (!r) return;
    state.roleId = r.role_id; state.roleName = r.role_name; state.filtre = null;
    const d = await api(`/mastery/dashboard/${state.cible}/${state.roleId}`);
    if (d.__error) return;
    state.rows = (d && d.activities) || [];
    const row = state.rows.find(x => x.activity_id === a.activity_id) || state.rows[0];
    if (row) await ouvrirEvaluation(row);
  }

  // ── TOUTES LES NOTES, D'UN COUP ──────────────────────────────────────
  // ⚠️ Une ligne par activité, une cellule par SORTIE : c'est le seul endroit
  // de l'application où l'on voit d'où vient le minimum sans ouvrir une
  // activité. La cellule d'une sortie MESURÉE porte un liseré — son niveau ne
  // vient pas d'une note mais d'un chiffre relevé en séance, et les deux ne
  // se corrigent pas de la même façon.
  function renderNotes(ap) {
    const z = $('#vo-notes');
    if (!ap || !ap.activites.length) { z.classList.add('hidden'); return; }
    z.classList.remove('hidden');
    const notees = ap.activites.reduce(
      (n, a) => n + a.sorties.filter(s => !estNul(s.niveau)).length, 0);
    let h = `<div class="vo-ct"><p class="vo-ctitre">${esc(T('vo_notes'))}</p>
      <span class="vo-cn">${esc(Tv('vo_notees', { n: notees, t: ap.n_sorties }))}</span></div>
      <div class="heat">`;
    ap.activites.forEach(a => {
      const cells = a.sorties.length
        ? a.sorties.map(s => {
            const n = s.niveau;
            const vert = !estNul(n) && (estNul(a.required_level) ? n >= SEUIL_TENU : n >= a.required_level);
            const cls = estNul(n) ? 'q' : ((vert ? 'g' : 'n') + n);
            return `<i class="hc ${cls}${s.mesurable && s.norme ? ' mes' : ''}"
              title="${esc(s.nom + DP + (estNul(n) ? state.notAssessed : n + ' · ' + levelName(n)))}"
              >${estNul(n) ? '?' : n}</i>`;
          }).join('')
        : `<i class="hc vide">${esc(T('vo_aucune_sortie'))}</i>`;
      h += `<div class="hr"><span class="nm">${esc(a.activity_name)}</span>
        <span class="cells">${cells}</span>
        <span class="req2">${estNul(a.required_level) ? '' : esc(Tv('ou_attendu', { n: a.required_level }))}</span></div>`;
    });
    h += `</div><div class="hleg">
      <span><i class="l-b"></i>${esc(T('vo_leg_sous'))}</span>
      <span><i class="l-g"></i>${esc(T('vo_leg_atteint'))}</span>
      <span><i class="l-m"></i>${esc(T('vo_leg_mesure'))}</span>
      <span><i class="l-q"></i>${esc(T('vo_leg_rien'))}</span></div>`;
    z.innerHTML = h;
  }

  // ── COMMENT UNE SORTIE A BOUGÉ ───────────────────────────────────────
  // Le relief de l'écran d'évaluation, posé sur la vue d'ensemble : il répond
  // à « est-ce que ça progresse ? », la question qu'on se pose avant d'ouvrir
  // quoi que ce soit. ⚠️ Le MÊME `reliefSvg` — deux tracés d'une même
  // progression finiraient par ne plus dire la même chose.
  function renderRelief(ap) {
    const z = $('#vo-relief');
    const mes = [];
    (ap ? ap.activites : []).forEach(a => a.sorties.forEach(s => {
      if (s.mesurable && s.norme && (s.paliers || []).length) mes.push(s);
    }));
    if (!mes.length) { z.classList.add('hidden'); return; }
    z.classList.remove('hidden');
    let s = mes.find(x => String(x.data_id) === String(state.voSortie)) || mes[0];
    state.voSortie = s.data_id;
    z.innerHTML = `<div class="vo-ct">
        <p class="vo-ctitre">${esc(Tv('vo_bouge', { x: s.nom }))}</p>
        <span class="vo-cn ${s.qualifie ? 'ok' : ''}">${esc(
          s.qualifie ? T('pal_qualifie') : T('vo_pas_qualifie'))}</span>
      </div>`;
    // ⚠️ Le sélecteur n'existe que s'il y a de quoi choisir : une rangée d'un
    // seul bouton est un titre déguisé.
    if (mes.length > 1) {
      const pick = document.createElement('div');
      pick.className = 'crb-pick';
      mes.forEach(x => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'crb-p' + (String(x.data_id) === String(s.data_id) ? ' on' : '');
        b.textContent = x.nom;
        b.onclick = () => { state.voSortie = x.data_id; renderRelief(ap); };
        pick.appendChild(b);
      });
      z.appendChild(pick);
    }
    // ⚠️ Le détail des séances s'ouvre À CÔTÉ : `.pal-evo-duo` porte les
    // deux colonnes, et `.pal-evo-g` tient le relief et son bilan. Sans ce
    // couple, le panneau se placerait sous le bilan et rallongerait la carte
    // — alors que la bande a toute la largeur de la page.
    const duo = document.createElement('div');
    duo.className = 'pal-evo-duo';
    const g = document.createElement('div');
    g.className = 'pal-evo-g';
    const box = document.createElement('div');
    box.className = 'vo-relief';
    box.innerHTML = reliefSvg({ name: s.nom, performance: s });
    g.appendChild(box);
    const bil = document.createElement('div');
    bil.innerHTML = bilanRelief(s);
    g.appendChild(bil);
    duo.appendChild(g);
    z.appendChild(duo);
    z.classList.add('pal-evo-cote');
    // ⚠️ `innerHTML` vide les enfants, PAS l'attribut : changer de sortie
    // pendant que le détail est ouvert laissait `data-evo="1"` sur une bande
    // sans panneau — deux colonnes dont la seconde est vide, et un relief
    // rétréci pour rien.
    z.dataset.evo = '';
    // ⚠️⚠️ Le bouton « Le détail des séances » était rendu ici et CÂBLÉ
    // NULLE PART : il ne faisait rien, depuis le jour où le relief est
    // arrivé sur la vue d'ensemble. `rendreValeurs` le branchait, pas celle-ci.
    const b = z.querySelector('[data-evol]');
    if (b) b.onclick = () => basculerHisto(z, { name: s.nom, performance: s });
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
    if (state.ecran === 'eval') majNav();
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
    // ⚠️ On revient de l'écran d'évaluation PAR le maillon du rôle : la vue
    // d'ensemble s'ouvre alors sur le détail de ce rôle, pas sur le radar.
    // `state.voRole` ne vaut que pour cette arrivée — gardé, il rouvrirait
    // les barres à chaque changement de collaborateur. Et il se pose APRÈS
    // `animerProfil`, qui remet la zone sur le radar.
    if (state.voRole) {
      const vr = (d.roles || []).find(x => x.role_id === state.voRole);
      state.voRole = null;
      if (vr) ouvrirBarres(box, vr);
    }
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

  // `opts.mini` : la vignette d'une carte d'accueil. MEME fonction, donc
  // meme geometrie et meme regle de couche — deux tracages d'un meme profil
  // finiraient par ne plus dire la meme chose.
  function radarSVG(axes, opts) {
    const o = opts || {};
    const mini = !!o.mini;
    const R = o.R || 132, CX = o.CX || 260, CY = o.CY || 186, MAX = 4;
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
    // ⚠️ En MINIATURE, le requis passe en FANTOME. Il est le meme pour tout le
    // monde — c'est la carto qui l'impose — donc rempli il devient la forme
    // dominante et toutes les cartes se ressemblent trait pour trait. Ce qui
    // distingue les gens, c'est le demontre : c'est lui qu'on remplit.
    const coucheReq = couche('required_level',
                             mini ? 'cv2-r-req--g' : 'cv2-r-req',
                             mini ? 'cv2-r-req--g' : 'cv2-r-req-part');
    const coucheDem = couche('demonstrated_level', 'cv2-r-dem', 'cv2-r-dem-part');
    const points = axes.map((a, i) => {
      if (estNul(a.demonstrated_level)) return '';
      const [x, y] = pt(i, a.demonstrated_level);
      const sous = a.demonstrated_level < a.required_level ? ' cv2-r-pt--sous' : '';
      return `<circle class="cv2-r-pt${sous}" data-axe="${i}"${
        mini ? '' : ` data-role="${a.role_id}"`}
          cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${mini ? 2.6 : 3.8}"></circle>`;
    }).join('');

    // ⚠️ Les noms d'activite sont longs et se chevauchent des qu'on depasse
    // une poignee d'axes. On coupe court (16 signes) et on rend l'axe SURVOLABLE :
    // le nom entier, son role et ses deux niveaux s'affichent dans une bulle.
    // Un libelle complet grave dans le SVG deborderait quoi qu'on fasse.
    // ⚠️ Une vignette ne porte PAS d'etiquettes : a 150 px, neuf noms
    // d'activite en 10,5 px ne tiennent pas. C'est la FORME qui se lit d'un
    // coup d'oeil ; les noms sont a l'interieur, sur le grand radar.
    const etiquettes = mini ? '' : axes.map((a, i) => {
      const [x, y] = pt(i, MAX + 0.52);
      const ancre = Math.abs(x - CX) < 14 ? 'middle' : (x > CX ? 'start' : 'end');
      const nom = a.activity_name.length > 16 ? a.activity_name.slice(0, 15) + '…' : a.activity_name;
      const [zx, zy] = pt(i, MAX);
      return `<g class="cv2-r-axe-g" data-axe="${i}" data-role="${a.role_id}">
          <line class="cv2-r-zone" x1="${CX}" y1="${CY}" x2="${zx.toFixed(1)}" y2="${zy.toFixed(1)}"></line>
          <text class="cv2-r-lbl" x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="${ancre}">${esc(nom)}</text>
        </g>`;
    }).join('');

    return `<svg class="cv2-radar${mini ? ' cv2-radar--mini' : ''}"
                 viewBox="${mini ? `0 0 ${CX * 2} ${CY * 2}` : '14 6 492 370'}" role="img"
                 aria-label="${esc(o.titre || T('p_title'))}">
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
      // ⚠️⚠️ `getBoundingClientRect()` rend DÉJÀ des pixels d'écran — le zoom
      // y est appliqué. Seules les coordonnées qu'on ÉCRIT repassent par lui :
      // on divise à l'écriture, et on ne multiplie NULLE PART. Mesuré avant
      // correction : la bulle se posait SUR son propre bouton, son bas 18 px
      // sous le haut du « i » — exactement sa hauteur fois (1 − zoom), moins
      // les 8 px voulus. Même correctif que la page Temps (08/11), resté à
      // faire ici : c'est pourtant d'ICI que le motif y avait été recopié.
      carte.style.left = Math.max(8, Math.min(r.left, window.innerWidth - b.width - 8)) / z + 'px';
      const dessus = r.top - b.height - 8;
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
    $('#cv2-overlay').onclick = closeDrawer;

    document.addEventListener('keydown', e => {
      if (e.key !== 'Escape') return;
      if ($('#cv2-drawer').classList.contains('open')) closeDrawer();
    });
  }
  function closeDrawer() {
    $('#cv2-drawer').classList.remove('open');
    $('#cv2-overlay').classList.remove('open');
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
  // ══════════════════════════════════════════════════════════════════════
  // LA FEUILLE D'UNE SORTIE — une ardoise, UNE piste       (11/11/2026)
  //
  // Chaque sortie avait SA carte, et les deux régimes en avaient deux très
  // différentes : « pas encore notée » ne ressemblait en rien à « déjà
  // notée », et empilées elles donnaient un écran sans ligne de lecture.
  // Les sorties sont devenues les LANGUETTES d'un classeur (voir plus bas) :
  // la comparaison se lit sur les languettes, et la feuille ne porte qu'UNE
  // sortie à la fois.
  //
  // ⚠️ L'INVERSION structure, elle ne décore pas. Trois surfaces, trois
  // rôles : NUIT = qui on regarde (le bandeau de la page), BLEU = le résultat
  // (la bande du classeur et ses languettes), ARDOISE = ce qui est DONNÉ et
  // ne se règle pas ici (la norme de l'entreprise, le repère de réussite).
  //
  // ⚠️ Et LES COURBES N'Y SONT PLUS : le relief d'une sortie mesurée et la
  // frise des niveaux a disparu avec la fenêtre des courbes, et
  // le détail des séances. La feuille dit l'ÉTAT, la fenêtre dit l'HISTOIRE.
  // ══════════════════════════════════════════════════════════════════════

  // ── LA PISTE — cinq marches, et UNE seule ─────────────────────────────
  // Avant : deux échelles de cinq crans l'une sous l'autre, et la distinction
  // portée par la seule couleur. Ici le niveau qui fait foi EST la piste, et
  // ce qu'il dit de lui-même est un repère SUR cette piste.
  //
  // ⚠️ Le 0 ne se REMPLIT jamais : « non démontré », c'est une jauge vide.
  // Posé, il se marque d'un anneau — sinon rien ne distinguerait « 0 » de
  // « rien ».
  // ⚠️ La gomme vit HORS des crans : effacer n'est pas un niveau de plus, et
  // la zone attendue ne doit pas l'englober — elle aurait l'air d'un sixième
  // cran.
  // ⚠️ Pas d'attribut `title` sur un cran : l'info-bulle du système sortirait
  // par-dessus la nôtre, une seconde plus tard et sans sa couleur (le piège
  // déjà rencontré sur la matrice RH). `data-nom` + `aria-label`.
  // ⚠️ Le repère d'auto-évaluation a QUITTÉ la piste. Il y a TOUJOURS deux
  // notes — celle qui fait foi et ce que le collaborateur se donne — et
  // compressée en un point sous les crans, la seconde ne se lisait plus
  // comme une note. Elle est redevenue une note à part entière : voir
  // `graduation()` et `notaSortie()` juste en dessous.
  function piste(pose, attendu, lue) {
    let h = `<div class="piste${lue ? ' lue' : ''}"><div class="crans">`;
    if (attendu !== null) h += `<span class="zone" style="--x:${attendu * 20}%"></span>`;
    const vert = attendu !== null && !estNul(pose) && pose >= attendu;
    for (let i = 0; i <= 4; i++) {
      let c = 'cran';
      // ⚠️ Le 0 se REMPLIT comme les autres. Il restait blanc à gauche d'une
      // barre qui part à 1 : un trou au début de la jauge, qu'on lisait comme
      // un défaut. Rien de posé → rien de rempli ; 0 posé → le seul cran 0 —
      // la distinction NULL ≠ 0 se voit toujours, et mieux qu'avec un anneau.
      if (!estNul(pose) && i <= pose) c += ' f' + (vert ? ' v' : '');
      if (i === attendu) c += ' but';
      // La pastille du niveau CHOISI, posée sur son cran : elle dit de quoi
      // il s'agit sans qu'on aille lire le mot à l'autre bout de la ligne.
      const pic = (!estNul(pose) && i === pose)
        ? `<span class="pic">${esc(levelName(i))}</span>` : '';
      h += `<button type="button" class="${c}" data-lv="${i}"${lue ? ' tabindex="-1"' : ''}
        data-nom="${esc(levelName(i))}" aria-label="${esc(i + ' · ' + levelName(i))}">${i}${pic}</button>`;
    }
    // ⚠️ La gomme est RENDUE même sur une piste en lecture, et seulement
    // masquée à l'œil : elle tient la largeur. Retirée du flux, la piste
    // devenait plus large que la graduation d'en dessous, et les deux notes
    // ne s'alignaient plus — or c'est leur alignement qui dit l'accord.
    h += `</div><button type="button" class="gomme" data-lv=""${lue ? ' tabindex="-1"' : ''}
      aria-label="${esc(T('ax_effacer'))}"><i class="fa-solid fa-eraser"></i></button>`;
    return h + '</div>';
  }

  // ── LA GRADUATION : la note POSÉE, celle qui n'est pas la vôtre ───────
  // La MÊME échelle que la piste, et la MÊME géométrie — cinq colonnes, le
  // même espacement, la largeur de la gomme en bout — pour que les deux
  // notes s'alignent au pixel. Des <span>, jamais des <button> : rien ne s'y
  // clique, et rien ne doit en avoir l'air.
  function graduation(niveau) {
    let h = '<div class="grad"><div class="gcs">';
    for (let i = 0; i <= 4; i++) {
      const on = !estNul(niveau) && i === niveau;
      h += `<span class="gc${on ? ' on' : ''}">${on ? i : '<i></i>'}</span>`;
    }
    // ⚠️ Le BOUT de la piste — la gomme et le « i » de l'échelle — est rendu
    // ici aussi, en JUMEAUX masqués à l'œil. Sans lui les cinq colonnes ne
    // tombent pas au même pixel que celles de la piste (mesuré : 4,5 px
    // d'écart au deuxième cran, 18 au cinquième), et c'est justement leur
    // alignement qui se lit comme un accord. Des jumeaux plutôt qu'une
    // largeur recopiée : celle-ci dériverait le jour où l'un des deux change
    // de taille.
    // ⚠️ Les MÊMES classes que les vrais, `ev-i` comprise : elle retire la
    // bordure du « i », donc un jumeau sans elle était 1 px plus large — et
    // le cinquième cran se décalait de 0,8 px. Mesuré, puis corrigé.
    return h + '</div><span class="gomme" aria-hidden="true"></span>'
      + '<span class="cv2-i ev-i" aria-hidden="true"></span></div>';
  }

  // Ce qu'une note vaut, en toutes lettres, au bout de son en-tête.
  function valeurNote(niveau) {
    return estNul(niveau)
      ? `<em>${esc(T('nt_rien'))}</em>`
      : `<b>${niveau}</b>${esc(levelName(niveau))}`;
  }

  // L'en-tête d'une note : ce qu'elle est, à qui elle appartient, ce qu'elle
  // vaut. `genre` vaut 'foi' (bleu, écusson), 'mes' (la mesure, ardoise) ou
  // 'auto' (violet, silhouette) — une identité tenue partout.
  function enteteNote(genre, titre, pastille, niveau) {
    const ic = { foi: 'fa-shield-halved', mes: 'fa-gauge-high', auto: 'fa-user' }[genre];
    return `<div class="nt-h">
      <span class="nt-k ${genre}"><i class="fa-solid ${ic}"></i>${esc(titre)}</span>
      ${pastille ? `<span class="p">${esc(pastille)}</span>` : ''}
      <span class="v" data-v>${valeurNote(niveau)}</span>
    </div>`;
  }

  // Le niveau qui FAIT FOI sur cette sortie, du point de vue du lecteur.
  // ⚠️ Sur une sortie mesurée il vient du chiffre relevé en séance — et
  // l'expertise POSÉE l'emporte sur la déduction, qui plafonne à 3.
  function niveauOfficiel(r) {
    if (r.mesurable && r.performance) {
      const p = r.performance;
      if (p.expertise === true) return 4;
      return estNul(p.niveau) ? p.niveau_pose : p.niveau;
    }
    return jeSuisLeDev() ? maNote(r) : r.demonstrated_level;
  }

  // Ce que JE peux poser ici : rien sur une sortie mesurée quand je suis le
  // développeur (le niveau vient de la mesure), mon auto-évaluation sinon.
  const jePosePour = r => (jeSuisLeDev() ? !r.mesurable : true);

  // ── L'ARDOISE : ce qui est DONNÉ, et ne se règle pas ici ──────────────
  // La norme vient de la colonne Performance de la LISTE DES ACTIVITÉS : cet
  // écran la MONTRE, il ne la redemande pas. Gravée, donc — et le relevé
  // entre DANS la pastille, là où « mesuré 46 h le 12 oct. » était une ligne
  // grise de plus sous chaque sortie.
  function ardoiseSortie(r, st, form) {
    const dev = jeSuisLeDev();
    const perf = r.performance || {}, n = perf.norme || {};
    const req = estNul(st.required_level) ? null : st.required_level;
    const a = document.createElement('div');
    a.className = 'grav';

    let gauche;
    if (r.mesurable && perf.norme && !estNul(n.valeur)) {
      const u = n.unite ? ' ' + n.unite : '';
      gauche = `<div class="bl"><p class="k">${esc(T('pal_norme'))}</p>
        <p class="v"><span class="sg">${n.sens === SENS_MOINS ? '≤' : '≥'}</span>${esc(nombre(n.valeur) + u)}
        ${estNul(perf.mesure) ? ''
          : `<span class="fl"><i class="fa-solid fa-arrow-right"></i></span>
             <span class="mes${perf.qualifie ? '' : ' ko'}">${esc(Tv('grv_mesure', { x: nombre(perf.mesure) + u }))}</span>`}
        </p></div>`;
    } else {
      const std = r.minimum_performance_text || r.indicateur || '';
      gauche = `<div class="bl"><p class="k">${esc(r.minimum_performance_text ? T('ax_reussi')
          : (r.indicateur ? T('pal_indic') : T('pal_norme_off')))}</p>
        <p class="v">${std
          ? `<q>${esc(std)}</q>`
          : `<span class="rien">${esc(T('pal_norme_off_d'))}</span>`}</p></div>`;
    }

    const att = req === null ? ''
      : `<span class="sep"></span><div class="bl"><p class="k">${esc(T('fi_requis'))}</p>
         <p class="v">${req}<span class="mot">${esc(levelName(req))}</span></p></div>`;

    a.innerHTML = gauche + att + '<span class="pousse"></span><span class="gbs"></span>';
    const gbs = a.querySelector('.gbs');
    const gb = (cle, icone, prim, lbl) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'gb' + (prim ? ' prim' : '');
      b.dataset.g = cle;
      b.innerHTML = `<i class="fa-solid ${icone}"></i>${esc(lbl)}`;
      gbs.appendChild(b);
      return b;
    };

    // ⚠️ L'ardoise ne porte QUE les gestes de sa sortie. « Les courbes » vit
    // sur la bande, et une seule fois : relevé sur capture, le bouton
    // s'affichait des DEUX côtés sur une sortie mesurée — deux portes pour un
    // seul sujet, ce que mon propre commentaire annonçait.
    if (!dev) return a;

    if (r.mesurable && perf.norme) {
      const vierge = !(perf.paliers || []).length;
      const expert = perf.expertise === true;
      gb('norme', 'fa-pen', false, T('pal_norme_mod')).onclick = () => formNorme(form, r);
      if (!vierge) {
        gb('exp', 'fa-award', false, expert ? T('pal_exp_retirer') : T('pal_exp_poser'))
          .onclick = () => poserExpertise(r, !expert);
      }
      const encours = perf.palier_en_cours;
      if (vierge) gb('prem', 'fa-ruler', true, T('pal_premiere')).onclick = () => formPremiere(form, r);
      else if (encours) gb('tr', 'fa-gavel', true, T('pal_trancher')).onclick = () => formTrancher(form, r, encours);
      else gb('pos', 'fa-plus', !perf.qualifie, T('pal_poser_suivant')).onclick = () => formPoser(form, r);
      return a;
    }

    // ⚠️ La norme ne se définit QU'APRÈS une première note à la main : poser
    // la norme bascule la sortie en régime mesuré, et la note à la main cesse
    // alors d'être saisissable. Offerte sur une sortie que personne n'a
    // regardée, elle demandait d'arbitrer un chiffre attendu avant d'avoir
    // jamais jugé la chose. On juge, puis on mesure.
    if (!estNul(maNote(r)) || !estNul(r.demonstrated_level)) {
      gb('norme', 'fa-bullseye', false, T('pal_definir_norme'))
        .onclick = () => formPremiere(form, r);
    }
    return a;
  }

  // ══ LA NOTATION — DEUX notes, toujours ════════════════════════════════
  //
  // Il y en a toujours deux : celle qui FAIT FOI, et ce que le collaborateur
  // se donne. Elles portent la MÊME échelle, et c'est leur ALIGNEMENT qui
  // dit l'accord — c'est pour cela que la seconde n'est pas une phrase, ni
  // un point posé sous les crans de la première.
  //
  //     ce qui fait foi      bleu · écusson   (la mesure : ardoise · jauge)
  //     ce qu'on se donne    violet · silhouette
  //
  // ⚠️ L'ordre ne bouge JAMAIS : celle qui fait foi d'abord, quel que soit
  // le regard — on sait toujours laquelle on lit.
  // ⚠️ Celle qui vous appartient se CLIQUE (une piste de cinq crans),
  // l'autre est POSÉE (la même échelle, en graduation). Le développeur pose
  // celle qui fait foi, le collaborateur la sienne — et sur une sortie
  // MESURÉE personne ne pose la première : elle vient du chiffre relevé en
  // séance, donc c'est le rail des marches qui en tient lieu.
  function notaSortie(r, st) {
    const dev = jeSuisLeDev();
    const req = estNul(st.required_level) ? null : st.required_level;
    const off = niveauOfficiel(r);
    const soi = dev ? r.self_level : maNote(r);
    const mesuree = !!(r.mesurable && r.performance && r.performance.norme);
    const maFoi = dev && !mesuree;
    const monAuto = !dev;

    const z = document.createElement('div');
    z.className = 'nota' + (maFoi || monAuto ? '' : ' est-lue');

    const f = document.createElement('div');
    f.className = 'nt nt--foi';
    f.innerHTML = enteteNote(mesuree ? 'mes' : 'foi', T('nt_foi'),
                             mesuree ? T('nt_mesure') : (maFoi ? T('nt_mienne') : ''), off)
      + (mesuree ? railHtml(r.performance) : (maFoi ? piste(off, req, false) : graduation(off)));
    if (maFoi) {
      // L'échelle 0 → 4 se range où elle sert : au bout de SA piste.
      f.querySelector('.piste').appendChild(boutonInfo(T('pal_echelle_t'), texteEchelle()));
      brancherCrans(f, r, st);
    }

    const a = document.createElement('div');
    a.className = 'nt nt--auto';
    a.innerHTML = enteteNote('auto',
                             dev ? Tv('nt_auto', { x: prenomCible() }) : T('nt_auto_moi'),
                             monAuto ? T('nt_mienne') : '', soi)
      + (monAuto ? piste(soi, req, false) : graduation(soi));
    if (monAuto) {
      a.querySelector('.piste').appendChild(boutonInfo(T('pal_echelle_t'), texteEchelle()));
      brancherCrans(a, r, st);
    }

    z.appendChild(f);
    z.appendChild(a);
    // ⚠️ Le verdict d'accord est HORS des deux blocs : posé dans celui du
    // bas, il se lisait comme un commentaire de l'auto-évaluation — or il
    // parle de l'ÉCART, donc des deux.
    const v = document.createElement('p');
    v.className = 'nota-vd'; v.dataset.vd = '';
    z.appendChild(v);
    majNota(z, r, st);
    return z;
  }

  function brancherCrans(bloc, r, st) {
    bloc.querySelectorAll('.cran, .gomme').forEach(b => {
      b.onclick = () => poserNote(r, b.dataset.lv === '' ? null : +b.dataset.lv, st);
    });
  }

  function prenomCible() {
    return String(state.cibleNom || '').trim().split(/\s+/)[0] || '';
  }

  // ⚠️ Sur place, et non en réécrivant la piste : la réécrire ferait perdre
  // le focus du cran qu'on vient de cliquer, et couperait la transition de la
  // marche qui se remplit — c'est elle qui fait comprendre le geste.
  function majNota(z, r, st) {
    const dev = jeSuisLeDev();
    const req = estNul(st.required_level) ? null : st.required_level;
    const off = niveauOfficiel(r);
    const soi = dev ? r.self_level : maNote(r);
    const perf = r.performance || {};

    const foi = z.querySelector('.nt--foi'), au = z.querySelector('.nt--auto');
    if (foi) { majPiste(foi, off, req); majValeur(foi, off); }
    if (au) { majPiste(au, soi, req); majGrad(au, soi); majValeur(au, soi); }

    // Le verdict : l'écart entre les deux notes quand les deux existent,
    // sinon ce que la situation appelle.
    let vd = '';
    if (r.mesurable && perf.expertise === true) {
      vd = `<b>${esc(T('pal_exp_posee'))}</b>`
        + (estNul(perf.niveau) ? '' : ' · ' + esc(Tv('pal_exp_mesure',
            { n: perf.niveau, l: levelName(perf.niveau) })));
    } else if (estNul(off)) {
      vd = gras(T('nota_zero'));
    } else if (!estNul(soi)) {
      vd = accordBadge(dev ? soi : maNote(r), dev ? off : r.demonstrated_level, dev);
    } else if (r.mesurable && !perf.qualifie) {
      vd = esc(T('nota_mes_ko'));
    }
    z.querySelector('[data-vd]').innerHTML = vd;
  }

  // ⚠️ Sur place, et non en réécrivant la piste : la réécrire ferait perdre
  // le focus du cran qu'on vient de cliquer, et couperait la transition de la
  // marche qui se remplit — c'est elle qui fait comprendre le geste.
  function majPiste(bloc, niveau, attendu) {
    const vert = attendu !== null && !estNul(niveau) && niveau >= attendu;
    bloc.querySelectorAll('.cran').forEach(b => {
      const i = +b.dataset.lv;
      b.classList.remove('f', 'v');
      if (!estNul(niveau) && i <= niveau) {
        b.classList.add('f');
        if (vert) b.classList.add('v');
      }
      // ⚠️ La pastille se DÉPLACE, elle ne se redessine pas ailleurs : deux
      // pastilles sur la même piste diraient deux niveaux.
      const p = b.querySelector('.pic');
      if (p && i !== niveau) p.remove();
      if (!p && !estNul(niveau) && i === niveau) {
        const n = document.createElement('span');
        n.className = 'pic'; n.textContent = levelName(i);
        b.appendChild(n);
      }
    });
  }

  function majGrad(bloc, niveau) {
    bloc.querySelectorAll('.grad .gc').forEach((c, i) => {
      const on = !estNul(niveau) && i === niveau;
      c.classList.toggle('on', on);
      c.innerHTML = on ? String(i) : '<i></i>';
    });
  }

  function majValeur(bloc, niveau) {
    const v = bloc.querySelector('[data-v]');
    if (v) v.innerHTML = valeurNote(niveau);
  }

  // ── LA PREUVE ─────────────────────────────────────────────────────────
  function preuveSortie(r, st) {
    const dev = jeSuisLeDev();
    const dejaLa = (dev ? r.evidence : r.self_evidence) || '';
    const z = document.createElement('div');
    z.className = 'preuve';
    z.innerHTML = `<span class="k">${esc(T('pr_k'))}</span>
      <textarea class="cv2-ev${dejaLa ? '' : ' hidden'}"
        placeholder="${esc(T('evidence_ph'))}">${esc(dejaLa)}</textarea>
      <span class="ch${dejaLa ? ' hidden' : ''}"><em>${esc(T('pr_vide'))}</em></span>
      <button type="button" class="pb${dejaLa ? ' hidden' : ''}">
        <i class="fa-solid fa-paperclip"></i>${esc(T('add_evidence'))}</button>`;
    const ta = z.querySelector('.cv2-ev'), b = z.querySelector('.pb'), ch = z.querySelector('.ch');
    b.onclick = () => {
      b.classList.add('hidden'); ch.classList.add('hidden');
      ta.classList.remove('hidden'); ta.focus();
    };
    ta.addEventListener('input', () => noterPreuve(r, ta.value, st));
    return z;
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
  // ⚠️⚠️ Il cherchait ses cartes dans `#cv2-drawer-body` — le TIROIR, d'où
  // l'évaluation est partie le 14/10. Il n'en trouvait donc aucune, la boucle
  // ne tournait pas, et le « Enregistré » tombait quand même : on notait, on
  // validait, et rien n'était écrit. Un enregistrement qui ne trouve rien à
  // écrire n'annonce plus un succès.
  // ⚠️ Et il lisait le DOM de l'échelle. Depuis que la note se pose aussi sur
  // la PISTE de l'axe, le DOM n'est plus la source : `state.saisie` l'est.
  async function saveEvaluation() {
    const ids = Object.keys(state.saisie || {});
    if (!ids.length) { toast(T('save_rien')); return; }
    const btn = $('#cv2-save-btn'); if (btn) btn.disabled = true;
    let ecrites = 0;
    for (const id of ids) {
      const s = state.saisie[id];
      const corps = {
        user_id: state.cible, activity_id: state.activity.activity_id,
        data_id: +id, evaluator: monEvaluateur(),
        mastery_level: estNul(s.niveau) ? null : s.niveau,
        role_id: state.roleId,
      };
      // ⚠️ La preuve n'est envoyée QUE si on l'a touchée : la route ne
      // réécrit `evidence` que sur PRÉSENCE de la clé, et l'omettre la laisse
      // intacte. C'est ce qui permet de poser un niveau depuis la piste sans
      // emporter la preuve avec lui.
      if ('preuve' in s) corps.evidence = s.preuve || '';
      const r = await api('/mastery/evaluate', {
        method: 'POST', body: JSON.stringify(corps),
      });
      if (r.__error) { if (btn) btn.disabled = false; return; }
      ecrites += 1;
    }
    state.saisie = {};
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
      // Les fleches de la bande se lisent sur `state.rows` : trancher un
      // palier change le niveau de l'activite, et l'info-bulle d'une fleche
      // nomme celle d'a cote.
      if (state.ecran === 'eval') majNav();
    }
  }

  // ══ Technicité — axe SÉPARÉ de la maîtrise (CDC 4) ═════════════════
  // ⚠️ DES CRANS, et plus un menu déroulant du système : c'était le seul
  // endroit de cette page où l'on posait un niveau autrement, et un `<select>`
  // arrive avec ses styles système au milieu d'un écran qui n'en a aucun.
  // ⚠️ CINQ crans : l'échelle technique distingue 0 (« aucun ») de NULL
  // (« pas encore regardé »), et c'est la distinction que tout le module tient.
  // La gomme est à l'écart — effacer n'est pas un niveau de plus.
  function domPas(cle, val, cible, onchange) {
    const pas = document.createElement('div');
    pas.className = 'tch-pas' + (cible ? ' cible' : '');
    const dev = jeSuisLeDev();
    Object.keys(state.domScale).forEach(k => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = k;
      b.className = (!estNul(val) && String(val) === String(k)) ? 'on' : '';
      b.title = k + DP + state.domScale[k];
      b.setAttribute('aria-label', T(cle) + DP + k + ' · ' + state.domScale[k]);
      b.disabled = !dev;
      b.onclick = () => onchange(+k);
      pas.appendChild(b);
    });
    if (dev) {
      const g = document.createElement('button');
      g.type = 'button'; g.className = 'gom';
      g.innerHTML = '<i class="fa-solid fa-eraser"></i>';
      g.title = T('tech_effacer'); g.setAttribute('aria-label', T('tech_effacer'));
      g.onclick = () => onchange(null);
      pas.appendChild(g);
    }
    return pas;
  }
  // ⚠️ UNE source pour les domaines : `state.tech`. La pastille de la bande et
  // le dialogue la relisent tous deux — deux chargements finiraient par
  // afficher deux comptes du même réglage.
  async function loadTech(zone) {
    const aid = state.activity.activity_id;
    const [dom, all] = await Promise.all([
      api(`/domains/activity/${aid}?role_id=${state.roleId}&user_id=${state.cible}`, null, true),
      api('/domains/list', null, true)]);
    state.tech = { domains: (dom && dom.domains) || [], all: (all && all.domains) || [] };
    majChipTech();
    if (!zone) return;
    renderDomList(zone.querySelector('.cv2-domlist'), aid, state.tech.domains);
    if (jeSuisLeDev()) renderDomAdd(zone, aid, state.tech.all, state.tech.domains);
  }
  // ⚠️⚠️ UNE TABLE, parce que les trois lignes ne s'ALIGNAIENT PAS : le nom du
  // domaine était en `flex: 1 1 150px`, donc chaque ligne poussait ses deux
  // échelles où elle pouvait — mesuré, le « Requis » partait à x = 472 / 513 /
  // 569, soit 97 px d'écart. On ne pouvait comparer deux domaines, ce qui est
  // tout l'objet d'une liste. Et les étiquettes montent en en-tête : écrites
  // UNE fois au lieu de six, ce qui libère la place des crans.
  function renderDomList(list, aid, domains) {
    list.innerHTML = '';
    if (!domains.length) {
      list.className = 'cv2-domlist';
      list.innerHTML = `<div class="tch-vide">${esc(T('tech_empty'))}</div>`;
      return;
    }
    list.className = 'cv2-domlist tch-tab';
    list.insertAdjacentHTML('beforeend',
      `<div class="hd">${esc(T('tech_dom'))}</div>
       <div class="hd c">${esc(T('tech_requis_role'))}</div>
       <div class="hd c">${esc(T('tech_demonstrated'))}</div>
       <div class="hd"></div>`);
    const cel = (cls, enfant) => {
      const c = document.createElement('div');
      c.className = 'cel' + (cls ? ' ' + cls : '');
      if (enfant) c.appendChild(enfant);
      list.appendChild(c);
      return c;
    };
    domains.forEach(d => {
      cel('nom').textContent = d.name;
      cel('', domPas('tech_requis_role', d.required_level, true,
        v => setDom('/domains/required',
          { role_id: state.roleId, activity_id: aid, domain_id: d.domain_id, required_level: v },
          list, aid)));
      cel('', domPas('tech_demonstrated', d.demonstrated_level, false,
        v => setDom('/domains/user_level',
          { user_id: state.cible, domain_id: d.domain_id, demonstrated_level: v }, list, aid)));
      // Le verdict dit ce qu'il EST, pas un nombre nu : « en écart · −2 » ou
      // « tenu ». Un « +1 » vert ne se lit pas comme un verdict.
      // ⚠️ Et NULL a le SIEN — « non situé », en neutre : sans lui la colonne
      // s'effondre, et « pas encore regardé » n'est pas « au niveau ».
      const g = document.createElement('span');
      if (estNul(d.gap)) { g.className = 'tch-v nul'; g.textContent = T('tech_nonsitue'); }
      else if (d.gap < 0) { g.className = 'tch-v ko'; g.textContent = Tv('tech_ecart', { n: -d.gap }); }
      else { g.className = 'tch-v ok'; g.textContent = T('tech_tenu'); }
      cel('', g);
    });
  }
  async function setDom(url, body, list, aid) {
    const r = await api(url, { method: 'POST', body: JSON.stringify(body) });
    if (r.__error) return;
    const dom = await api(`/domains/activity/${aid}?role_id=${state.roleId}&user_id=${state.cible}`);
    state.tech = Object.assign({ all: [] }, state.tech, { domains: (dom && dom.domains) || [] });
    majChipTech();
    renderDomList(list, aid, state.tech.domains);
    refreshDashboard();
  }
  // ⚠️ L'ajout est un BOUTON qui DÉPLIE ses champs : la zone dépliée en
  // permanence se lisait comme une ligne de plus de la liste.
  // ⚠️⚠️ Et son libellé était FAUX quand tout était déjà rattaché : le ternaire
  // était inversé, on lisait « Rattacher un domaine qui existe » au-dessus d'un
  // champ « Nouveau domaine… ». Chaque champ porte désormais le sien, et celui
  // qui n'a rien à proposer n'est pas rendu.
  function renderDomAdd(zone, aid, allDomains, linked) {
    const add = zone.querySelector('.cv2-domadd');
    add.className = 'cv2-domadd'; add.innerHTML = '';
    const linkedIds = new Set(linked.map(d => d.domain_id));
    const avail = allDomains.filter(d => !linkedIds.has(d.id));

    const rangee = document.createElement('div');
    rangee.className = 'tch-add';
    const pl = document.createElement('button');
    pl.type = 'button'; pl.className = 'pl';
    pl.innerHTML = `<i class="fa-solid fa-plus"></i>${esc(T('tech_ajouter'))}`;
    rangee.appendChild(pl);
    if (avail.length) {
      const h = document.createElement('span'); h.className = 'hint';
      h.textContent = nf('tech_cat', avail.length);
      rangee.appendChild(h);
    }
    add.appendChild(rangee);

    const champs = document.createElement('div');
    champs.className = 'tch-champs'; champs.hidden = true;
    add.appendChild(champs);
    pl.onclick = () => {
      champs.hidden = !champs.hidden;
      if (!champs.hidden) (sel || inp).focus();
    };

    let sel = null;
    if (avail.length) {
      const ch = document.createElement('div'); ch.className = 'ch';
      ch.innerHTML = `<span>${esc(T('tech_lier_t'))}</span>`;
      sel = document.createElement('select');
      sel.innerHTML = `<option value="">${esc(T('tech_pick'))}</option>` +
        avail.map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
      ch.appendChild(sel); champs.appendChild(ch);
    }
    const ch2 = document.createElement('div'); ch2.className = 'ch';
    ch2.innerHTML = `<span>${esc(T('tech_creer_t'))}</span>`;
    const inp = document.createElement('input'); inp.placeholder = T('tech_add_ph');
    ch2.appendChild(inp); champs.appendChild(ch2);

    const b = document.createElement('button');
    b.type = 'button'; b.className = 'pal-b pal-b--prim';
    b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-plus"></i></span>${esc(T('tech_link'))}`;
    b.onclick = async () => {
      const nm = inp.value.trim();
      if (nm) {
        const r = await api('/domains/create', { method: 'POST', body: JSON.stringify({ name_fr: nm }) });
        if (r && r.id) { await linkDom(aid, r.id); inp.value = ''; await loadTech(zone); }
        return;
      }
      if (sel && sel.value) { await linkDom(aid, +sel.value); await loadTech(zone); }
    };
    champs.appendChild(b);
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
        ${blocNorme(o, p)}
      </div>`;
    brancherNorme(el, o, p);
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

  /* ══ LA NORME SE RÈGLE ICI ════════════════════════════════════════════
     ⚠️⚠️ Elle se DEVINAIT, plus tard, dans l'écran d'évaluation, à partir d'un
     texte libre — et elle ratait pour deux raisons mesurées. Elle lisait
     l'indicateur de performance d'une connexion sortante, vide sur les deux
     sorties du banc, en ignorant « réussi quand… » qui porte le chiffre ; et
     son parseur prenait le PREMIER nombre de la phrase (22 justes sur 28, les
     six faux d'une seule cause). Le second défaut est corrigé côté serveur,
     mais le premier est de FOND : tant qu'on LIT une phrase humaine, on
     devine — et ce qu'on devine ici décide du niveau de quelqu'un.
     Elle se pose donc À CÔTÉ de la phrase, au moment où on l'écrit.
     ⚠️ Les trois champs sont EXACTEMENT ceux de la fenêtre des paliers
     (`.pal-champs`, `champUnite`, `lireUnite`) : deux façons de régler la même
     norme finiraient par ne plus écrire la même chose.
     ⚠️ Rien n'est PRÉ-REMPLI. Ce que le serveur sait lire dans la phrase est
     offert en BOUTON : l'app propose, la personne pose. C'est toute la
     différence avec ce qu'on vient de retirer. */
  function blocNorme(o, p) {
    const a = !estNul(o.norme_valeur);
    // Ce qui est ENREGISTRÉ l'emporte sur la proposition : on ne revient pas
    // sur un chiffre posé par quelqu'un.
    const prop = a ? null : (o.norme_proposee || p.norme_proposee || null);
    return `<div class="cv2-cf-nrm">
        <div class="k">${esc(T('conf_norme'))}
          <span class="cv2-i" tabindex="0" role="button" aria-label="${esc(T('conf_norme'))}"
            ><i class="fa-solid fa-info"></i></span></div>
        <div class="pal-champs">
          <label><span>${esc(T('pal_valeur'))}</span>
            <input type="text" data-v inputmode="decimal"
                   value="${esc(a ? fmtNb(o.norme_valeur) : '')}"></label>
          ${champUnite(a ? (o.norme_unite || '') : null)}
          <label><span>${esc(T('pal_sens'))}</span>
            <select data-s>
              <option value="moins"${o.norme_sens === 'plus' ? '' : ' selected'}>${esc(T('pal_moins'))}</option>
              <option value="plus"${o.norme_sens === 'plus' ? ' selected' : ''}>${esc(T('pal_plus'))}</option>
            </select></label>
        </div>
        ${prop ? `<button type="button" class="cv2-cf-prop" data-prop>
            <i class="fa-solid fa-arrow-turn-down"></i>
            <span>${esc(Tv('conf_prop', { x: fmtVal(prop.valeur, prop.unite) + ' · '
              + (prop.sens === 'plus' ? T('pal_au_moins') : T('pal_au_plus')) }))}</span>
            <b>${esc(T('conf_prop_ok'))}</b></button>` : ''}
        <p class="cv2-cf-nrm-off">${esc(T('conf_norme_off'))}</p>
      </div>`;
  }

  function brancherNorme(el, o, p) {
    // ⚠️ La ZONE est la LIGNE, pas la fenêtre : `lireUnite` et `brancherUnite`
    // prennent le PREMIER champ qu'ils trouvent, et il y a une ligne par
    // sortie — on réglerait l'unité de la première pour tout le monde.
    brancherUnite(el);
    brancherInfo(el.querySelector('.cv2-cf-nrm .cv2-i'), T('conf_norme'), T('conf_norme_i'));
    const b = el.querySelector('[data-prop]');
    if (!b) return;
    const prop = o.norme_proposee || p.norme_proposee;
    b.onclick = () => {
      el.querySelector('[data-v]').value = fmtNb(prop.valeur);
      const sel = el.querySelector('[data-us]'), libre = el.querySelector('[data-u]');
      if (sel) {
        const connue = UNITES.indexOf(prop.unite || '') >= 0;
        sel.value = connue ? prop.unite : '*';
        if (libre) {
          libre.classList.toggle('hidden', connue);
          libre.value = connue ? '' : (prop.unite || '');
        }
      }
      el.querySelector('[data-s]').value = prop.sens === 'plus' ? 'plus' : 'moins';
      b.remove();                       // posé : il n'y a plus rien à proposer
    };
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
      const o = { data_id: +l.dataset.dataId,
                  nature: on ? 'RESULT' : (l.dataset.autre || null),
                  minimum_performance_text: on ? l.querySelector('.cv2-cf-in').value : '',
                  source: 'MANUAL' };
      // ⚠️ La norme ne part QUE pour ce qui est coché : le serveur n'y touche
      // pas si la clé est absente, donc décocher une sortie ne lui retire pas
      // la norme que l'entreprise lui a donnée.
      if (on) {
        const v = lireNb(l, '[data-v]');
        o.norme_valeur = isFinite(v) ? v : '';
        o.norme_unite = lireUnite(l);
        o.norme_sens = l.querySelector('[data-s]').value;
      }
      return o;
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
  //  LE PLAN DE FORMATION — une PAGE, et deux dessins
  //  ⚠️ C'était une FENÊTRE de 800 × 736 px réels dans un écran de
  //  1600 × 1000 — la moitié de la largeur — avec 1 089 px à dérouler pour
  //  794 visibles, et le verdict « il manque 74 h » en SIXIÈME position de la
  //  colonne de droite. L'écran pose un argument en trois temps — voilà ce qui
  //  manque · voilà ce qu'on fait · voilà si ça tient — et il n'en montrait
  //  jamais deux ensemble. C'est une page, comme l'évaluation l'est devenue le
  //  14/10 pour le même reproche.
  //  ⚠️⚠️ Et les deux dessins REMPLACENT, ils ne s'ajoutent pas : la FRISE
  //  prend la place de l'échéancier en peigne, des deux chiffres d'entrée du
  //  verdict (sa longueur totale EST le besoin, son trait blanc la capacité) et
  //  de la barre de répartition par nature ; le CLASSEMENT prend celle des
  //  trois jauges et de la liste de détail qui redisait, activité par activité,
  //  ce que la colonne du chemin écrit déjà. Le chemin reste la seule LISTE —
  //  c'est lui qui porte le texte et les −/+.
  //  Le verdict est ARITHMÉTIQUE et local : les réglages ne rappellent JAMAIS
  //  le serveur, sinon on n'oserait pas y toucher.
  // ══════════════════════════════════════════════════════════════════
  const BORNES = { heures_semaine: [1, 40], semaines: [1, 60] };
  // la lettre de chaque nature dans la frise et sa légende
  const CLN = { TERRAIN: 't', ACCOMPAGNEMENT: 'a', FORMATION: 'f' };
  // ⚠️ Le vrai signe moins : deux glyphes pour le même signe sur le même
  // écran donnent l'air d'un défaut d'impression.
  const MOINS = '\u2212';

  async function ouvrirPlan() {
    // ⚠️ D'où l'on vient : le plan s'ouvre depuis la page d'évaluation ET
    // depuis le diagnostic. Le retour doit ramener là, pas à la galerie.
    state.planRetour = state.ecran;
    montrerEcran('plan');
    showBusy(null, '#cv2-ecran-plan');
    const d = await api(`/plan/${state.cible}/${state.roleId}`);
    if (d.__error) { retourDuPlan(); return; }
    state.plan = {
      parametres: Object.assign({}, d.parametres),
      actions: (d.actions || []).map(a => Object.assign({}, a)),
      activites: d.activites || [], source: d.source, types: d.types || {},
      seance: d.seance || null,
    };
    state.plan.actions = ordonner(state.plan.actions);
    state.planActif = null;
    renderPlan();
  }

  function retourDuPlan() {
    if (state.planRetour === 'eval' && state.activity) ouvrirEvaluation(state.activity);
    else chargerSynthese();
  }

  function renderPlan() {
    const p = state.plan;
    const z = $('#cv2-ecran-plan');
    z.classList.add('pl');
    const tete = `<div class="pl-nuit"><div class="pl-h">
          <button type="button" class="ev-retour" data-pl-retour>
            <i class="fa-solid fa-chevron-left"></i>${esc(T('plan_retour'))}</button>
          <div class="pl-ch"><b>${esc(state.cibleNom || '')}</b><i>→</i>
            <b>${esc(state.roleName || '')}</b><i>→</i>
            <span>${esc(T('plan_title'))}</span></div>
        </div>`;
    const brancherRetour = () => {
      const b = z.querySelector('[data-pl-retour]');
      if (b) b.onclick = retourDuPlan;
    };

    if (!p.activites.length || !p.actions.length) {
      const vide = p.activites.length
        ? `<div class="cv2-ia-t">${esc(T('plan_empty_t'))}</div>
           <div style="margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto">
             ${esc(T('plan_empty_d'))}</div>`
        : `<div class="cv2-ia-t">${esc(T('plan_none_t'))}</div>
           <div style="margin-top:6px">${esc(T('plan_none_d'))}</div>`;
      z.innerHTML = tete + '</div>'
        + `<div class="pl-bloc" style="margin-top:18px"><div class="cv2-plan-vide">${vide}</div></div>`
        + (p.activites.length ? pied() : '');
      brancherRetour();
      brancherPied(z);
      return;
    }

    z.innerHTML = tete
      + `<div class="pl-corps">
           <div class="pl-g"><div id="pl-frise"></div><div class="pl-v" id="pl-verdict"></div></div>
           <div class="pl-rg" id="pl-reglages"></div>
         </div></div>
         <div class="pl-cols">
           <div class="pl-bloc pl-bloc--cl">
             <div class="pl-bh"><em>1</em>${esc(T('plan_cl_t'))}
               <span class="q" id="pl-cl-q"></span></div>
             <div id="pl-classement"></div>
           </div>
           <div class="pl-bloc">
             <div class="pl-bh"><em>2</em>${esc(T('plan_che_t'))}
               <span class="q" id="pl-che-q"></span></div>
             <div id="cv2-actions"></div>
           </div>
         </div>` + pied();
    brancherRetour();
    brancherPied(z);
    renderActions(true);
    recalculer();
  }

  function pied() {
    const loc = state.plan.source !== 'AI';
    return `<div class="pl-pied">
        <div class="cv2-prop${loc ? ' cv2-prop--touche' : ''}">${
          esc(T(loc ? 'plan_source_local' : 'plan_source_ai'))}</div>
        <span class="pl-pousse"></span>
        <button type="button" class="btn btn-quiet" data-pl-prop id="cv2-plan-prop">${
          esc(T(state.plan.actions.length ? 'plan_repropose' : 'plan_propose'))}</button>
        ${state.plan.actions.length
          ? `<button type="button" class="btn btn-primary" data-pl-save>${esc(T('plan_save'))}</button>`
          : ''}
      </div>`;
  }
  function brancherPied(z) {
    const pr = z.querySelector('[data-pl-prop]'); if (pr) pr.onclick = proposerPlan;
    const sv = z.querySelector('[data-pl-save]'); if (sv) sv.onclick = enregistrerPlan;
  }

  /* ══ LA FRISE ═══════════════════════════════════════════════════════════
     ⚠️ Les heures et les semaines sont la MÊME grandeur — une semaine, c'est
     les heures qu'on y met — donc la longueur d'un segment dit à la fois ce
     qu'il coûte et combien de temps il prend : une seule image répond à
     « quand » et à « ça tient ». Le trait blanc est la capacité ; ce qui est à
     sa droite est hachuré. Le verdict n'est plus un nombre à chercher, c'est
     l'endroit où la barre CASSE. */
  function renderFrise(c) {
    const box = $('#pl-frise'); if (!box) return;
    const p = state.plan, pl = state.planning;
    const ech = Math.max(c.besoin, c.capacite) || 1;
    const coupe = Math.min(100, c.capacite / ech * 100);
    const semMax = Math.max(1, Math.ceil(ech / c.hs));
    const pc = x => Math.round(x * 100) / 100;

    let h = '<div class="pl-fr"><div class="pl-fr-t">';
    p.actions.forEach((a, i) => {
      const hh = Math.max(1, +a.heures || 1), st = pl[i];
      const w = hh / ech * 100;
      h += `<div class="pl-fr-s ${CLN[nature(a)]}" data-i="${i}"
              style="left:${pc(st.debut / ech * 100)}%;width:${pc(w)}%"
              title="${esc(a.titre)} — ${hh} ${esc(T('plan_h'))}, ${esc(dateEtape(st))}">`
        + (w > 3.4 ? `<b>${i + 1}</b>` : '')
        + (w > 7 ? `<span>${hh} ${esc(T('plan_h'))}</span>` : '')
        + '</div>';
    });
    if (coupe < 100) h += `<div class="pl-fr-de" style="left:${pc(coupe)}%"></div>`;
    h += '</div>';
    // ⚠️ Près du bord, l'étiquette centrée sortirait de la boîte — et le
    // bandeau est en `overflow: hidden`, donc elle serait coupée sans rien
    // signaler.
    const tr = coupe > 88 ? 'translateX(-100%)' : (coupe < 7 ? 'none' : 'translateX(-50%)');
    h += `<div class="pl-fr-c" style="left:${pc(coupe)}%"></div>`
      + `<div class="pl-fr-cl" style="left:${pc(coupe)}%;transform:${tr}">`
      + `${esc(T('plan_vise'))} · ${T('plan_wk')}${c.sem} · ${c.capacite} ${esc(T('plan_h'))}</div>`;

    // l'axe des semaines : c'est lui qui fait de la barre une frise
    const pas = Math.max(1, Math.round(semMax / 7));
    h += '<div class="pl-fr-ax">';
    const marque = w => {
      const x = pc(Math.min(100, (w - 1) * c.hs / ech * 100));
      return `<i style="left:${x}%"></i><span class="${w > c.sem ? 'de' : ''}"
                style="left:${x}%">${T('plan_wk')}${w}</span>`;
    };
    for (let w = 1; w <= semMax; w += pas) h += marque(w);
    h += `<i style="left:100%"></i><span class="${semMax > c.sem ? 'de' : ''}"
            style="left:100%;transform:translateX(-100%)">${T('plan_wk')}${semMax}</span></div>`;

    // la légende des couleurs : c'est elle qui remplace la barre de répartition
    const vues = [...new Set(p.actions.map(nature))];
    h += '<div class="pl-fr-leg">'
      + vues.map(n => `<span><u class="${CLN[n]}"></u>${esc(p.types[n] || n)}</span>`).join('')
      + (c.manque > 0 ? `<span><u class="h"></u>${esc(T('plan_hors'))}</span>` : '')
      + '</div></div>';
    box.innerHTML = h;
    box.querySelectorAll('.pl-fr-s').forEach(s => {
      s.addEventListener('mouseenter', () => eclairer(+s.dataset.i));
      s.addEventListener('mouseleave', () => eclairer(null));
    });
  }

  /* ══ LE VERDICT : UN seul chiffre ═══════════════════════════════════════
     ⚠️ Il en portait TROIS — « à combler », « disponibles », « il manque ».
     Les deux premiers sont les entrées de la soustraction, et la frise les
     montre déjà : sa longueur totale est le besoin, l'étiquette de son trait
     blanc la capacité. Reste celui sur lequel on agit. */
  function renderVerdict(c) {
    const box = $('#pl-verdict'); if (!box) return;
    const ok = c.manque <= 0;
    const phrase = c.manque > 0
      ? Tv('plan_trop', { s: c.semainesNecessaires, h: c.heuresNecessaires })
      : (c.marge <= Math.max(1, c.hs) ? T('plan_tendu')
                                      : Tv('plan_ok', { s: c.sem, h: c.hs }));
    box.innerHTML = `<div class="pl-vn ${ok ? 'ok' : 'ko'}">
        <span>${esc(T(ok ? 'plan_reste_k' : 'plan_manque_k'))}</span>
        <b>${ok ? c.marge : c.manque} ${esc(T('plan_h'))}</b></div>
      <p class="pl-vph${ok ? ' ok' : ''}">${phrase}</p>`;
  }

  /* ───────────────── LES RÉGLAGES, contre le verdict qu'ils font bouger ── */
  function renderReglages(c) {
    const box = $('#pl-reglages'); if (!box) return;
    const sc = state.plan.seance;
    const nb = (cle, v) => `<span class="pl-nb">
        <button type="button" data-r="${cle}" data-d="-1" aria-label="${esc(T('plan_less'))}">&minus;</button>
        <span>${v}</span>
        <button type="button" data-r="${cle}" data-d="1" aria-label="${esc(T('plan_more'))}">+</button></span>`;
    box.innerHTML = `
      <div><div class="pl-rg-l">${esc(T('plan_hours_week'))}</div>
        <div class="pl-rg-r">${nb('heures_semaine', c.hs)}
          <span class="u">${esc(T('plan_h'))}</span></div></div>
      <div><div class="pl-rg-l">${esc(T('plan_weeks'))}</div>
        <div class="pl-rg-r">${nb('semaines', c.sem)}
          <span class="u">${esc(T('plan_week_unit'))}</span></div></div>
      <hr>
      ${sc ? `<button type="button" class="pl-bn" data-r="seance">
          <i class="fa-solid fa-calendar-check"></i>${esc(T('plan_seance_b'))}
          <em>· ${esc(fmtDate(sc.date))} · ${sc.semaines} ${esc(T('plan_week_unit'))}</em>
        </button>` : ''}
      <button type="button" class="pl-bn" data-r="juste">
        <i class="fa-solid fa-compress"></i>${esc(T('plan_juste_b'))}
        <em>· ${c.semainesNecessaires} ${esc(T('plan_week_unit'))}</em></button>`;
    box.querySelectorAll('[data-r]').forEach(b => b.onclick = () => {
      const p = state.plan.parametres, d = +b.dataset.d || 0, cle = b.dataset.r;
      if (cle === 'juste') p.semaines = borner('semaines', calcul().semainesNecessaires);
      // ⚠️ Borné comme le réglage : une séance dans deux ans ne doit pas
      // écrire une valeur qu'on ne peut plus reprendre à la main.
      else if (cle === 'seance') p.semaines = borner('semaines', state.plan.seance.semaines);
      else p[cle] = borner(cle, (+p[cle] || 1) + d);
      recalculer();
    });
  }
  const borner = (cle, v) =>
    Math.min(BORNES[cle][1], Math.max(BORNES[cle][0], Math.round(v) || 1));

  /* ══ LE CLASSEMENT : les activités sur une échelle commune 0 → 4 ═════════
     ⚠️ Il remplace les trois jauges : elles se lisaient l'une après l'autre,
     et le niveau de l'activité est précisément ce qui se COMPARE. Le requis
     est un tiret posé sur la colonne — une cible se dessine, elle ne se
     remplit pas, c'est le device de la vue d'ensemble.
     ⚠️ Cliquer une colonne met en avant les actions de CETTE activité dans la
     colonne d'à côté : c'est ce qui relie les deux. */
  function renderClassement() {
    const box = $('#pl-classement'); if (!box) return;
    const p = state.plan, H = 168, PAS = H / 4;
    const parAct = {};
    p.actions.forEach(a => {
      const k = connue(a.activity_id) ? a.activity_id : '_';
      parAct[k] = (parAct[k] || 0) + (+a.heures || 0);
    });
    const pc = x => Math.round(x * 100) / 100;
    let h = '<div class="pl-cl"><div class="pl-cl-y">';
    for (let n = 0; n <= 4; n++) h += `<span style="bottom:${n * PAS}px">${n}</span>`;
    h += '</div><div class="pl-cl-p">';
    for (let g = 1; g <= 4; g++) h += `<div class="pl-cl-g" style="bottom:${g * PAS}px"></div>`;
    const larg = 100 / Math.max(1, p.activites.length);
    p.activites.forEach((a, i) => {
      const dem = Math.max(0, Math.min(4, +a.demonstrated_level || 0));
      const req = Math.max(0, Math.min(4, +a.required_level || 0));
      const on = state.planActif === a.activity_id;
      // ⚠️ Le bouton prend toute la VOIE, pas la largeur de sa barre : le nom
      // de l'activité est écrit dessous, et dans 62 px il partait sur quatre
      // lignes. La barre et le tiret du requis vivent DEDANS, en pourcentage.
      // ⚠️ Un socle de 10 px : à hauteur nulle, le niveau 0 se confondrait
      // avec « pas de niveau du tout », et les deux ne se corrigent pas de la
      // même façon.
      h += `<button type="button" class="pl-cl-b${on ? ' on' : ''}" data-act="${a.activity_id}"
              style="left:${pc(i * larg + larg * 0.06)}%;width:${pc(larg * 0.88)}%;height:${H}px"
              title="${esc(a.activity_name)} — ${esc(a.demonstrated_label)} / ${esc(a.required_label)}">
            <span class="pl-cl-ec" style="bottom:${req * PAS + 13}px">${
              esc(String(a.gap).replace('-', MOINS))}</span>
            <span class="pl-cl-f" style="height:${Math.max(10, dem * PAS)}px"></span>
            <span class="pl-cl-req" style="bottom:${req * PAS - 2}px"></span>
            <span class="pl-cl-x">${esc(court(a.activity_name))}<br>
              <b>${parAct[a.activity_id] || 0} ${esc(T('plan_h'))}</b></span>
          </button>`;
    });
    h += `</div></div><div class="pl-cl-lg">
        <span><u class="d"></u>${esc(T('plan_cl_dem'))}</span>
        <span><u class="r"></u>${esc(T('plan_cl_req'))}</span></div>`;
    box.innerHTML = h;
    box.querySelectorAll('[data-act]').forEach(b => b.onclick = () => {
      const id = +b.dataset.act;
      state.planActif = state.planActif === id ? null : id;
      renderClassement(); majEtapes();
    });
    $('#pl-cl-q').textContent = p.activites.length === 1
      ? T('plan_gap_1') : Tv('plan_gap_n', { n: p.activites.length });
  }
  // ⚠️ Sous la colonne, un nom entier passerait sur quatre lignes : il est
  // coupé, et il reste entier dans l'info-bulle du bouton.
  const court = s => (String(s).length > 17 ? String(s).slice(0, 16).trim() + '…' : s);

  /* ══ Le parcours ═══════════════════════════════════════════════════════
     Une section par activité (l'écart qu'on vient combler), des étapes
     NUMÉROTÉES dans l'ordre du plan, et dans chaque carte ce qui n'est écrit
     nulle part ailleurs. */

  // La nature d'une action porte sa couleur et son pictogramme partout : la
  // pastille numérotée, l'étiquette de la carte, le segment de la frise.
  const NATURES = {
    TERRAIN: 'fa-briefcase',
    ACCOMPAGNEMENT: 'fa-handshake-angle',
    FORMATION: 'fa-graduation-cap',
  };
  const nature = a => (NATURES[a.type] ? a.type : 'FORMATION');
  const connue = id => id != null && state.plan.activites.some(x => x.activity_id === id);

  /* ⚠️ Le plan est une SUITE : l'IA ordonne ses actions (« ce qui conditionne
     le reste d'abord ») et la frise remplit les semaines dans cet ordre.
     On regroupe par activité en gardant l'ordre de PREMIÈRE apparition — un
     tri par écart déferait la séquence proposée. Appliqué au chargement :
     l'ordre affiché, l'ordre enregistré et l'ordre des semaines sont le même. */
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
  // pouvoir y consacrer par semaine. `debut` est le cumul d'heures AVANT
  // l'action — c'est l'abscisse de son segment de frise.
  function planning(c) {
    let cumul = 0;
    return state.plan.actions.map(a => {
      const debut = cumul;
      const ws = Math.floor(cumul / c.hs) + 1;
      cumul += Math.max(1, +a.heures || 1);
      const we = Math.max(ws, Math.ceil(cumul / c.hs));
      return { ws, we, debut, deborde: we > c.sem };
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
      return `<section class="cv2-etapes-g" data-gact="${act ? act.activity_id : ''}">
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
    $('#pl-che-q').textContent = (p.actions.length === 1
      ? T('plan_steps_1') : Tv('plan_steps_n', { n: p.actions.length }));
  }

  /* ⚠️ 248 px, avec le nom du résultat écrit TROIS fois et trois étiquettes en
     capitales rendues à 9,2 px réels (le plancher de l'échelle est 11). Le
     titre est l'action — une fois — la ligne qui suit porte la mesure telle
     que le serveur la rédige (« mesuré 5 essais · norme au moins 8 essais ·
     échéance 24/11/2026 »), et « Réussi quand » attend derrière un « ? ».
     ⚠️ « Livrable » est parti : dans le repli c'est le nom du résultat, donc
     le titre. Il ne revient que quand le titre ne le dit pas déjà. */
  function carteEtape(a, i, anime) {
    const n = nature(a);
    const liv = (a.livrable || '').trim();
    const montreLiv = liv && String(a.titre || '').indexOf(liv) < 0;
    const crit = (a.critere || '').trim();
    return `<li class="cv2-etape cv2-t--${n}" data-i="${i}"
                ${anime ? `style="animation-delay:${i * 35}ms"` : 'data-calme="1"'}>
        <span class="cv2-etape-n" aria-hidden="true">${i + 1}</span>
        <div class="cv2-etape-c">
          <div class="cv2-etape-h">
            <span class="cv2-etape-type"><i class="fa-solid ${NATURES[n]}"></i>${
              esc(state.plan.types[n] || n)}</span>
            <span class="cv2-pas" role="group" aria-label="${esc(T('plan_load'))}">
              <button type="button" data-pas="-1" aria-label="${esc(T('plan_less'))}">&minus;</button>
              <input type="number" min="1" max="200" value="${Math.max(1, +a.heures || 1)}"
                     aria-label="${esc(T('plan_load'))}">
              <span class="u">${esc(T('plan_h'))}</span>
              <button type="button" data-pas="1" aria-label="${esc(T('plan_more'))}">+</button>
            </span>
          </div>
          <div class="cv2-etape-t">${esc(a.titre)}${crit
            ? ` <span class="pl-q" title="${esc(T('plan_crit') + DP + crit)}">?</span>` : ''}</div>
          ${a.objectif ? `<div class="cv2-etape-o">${esc(a.objectif)}</div>` : ''}
          <div class="cv2-etape-f">
            <span class="pl-ch-s" data-sem></span>
            ${montreLiv ? `<span class="pl-ch-s">${esc(liv)}</span>` : ''}
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
        // Retirer la DERNIERE action vide le plan : on repasse par la page
        // entiere, qui porte l'etat vide et sa porte de sortie. Mesure sans
        // elle : une frise vide sous un verdict qui annonce 48 h de marge.
        if (!state.plan.actions.length) return renderPlan();
        renderActions(false);
        recalculer();
      });
      li.addEventListener('mouseenter', () => eclairer(i));
      li.addEventListener('mouseleave', () => eclairer(null));
    });
  }

  // ⚠️ Le segment de frise et la carte s'allument ENSEMBLE, par CLASSE et sans
  // re-rendu : un re-rendu à chaque survol ferait sauter ce qu'on regarde.
  function eclairer(i) {
    document.querySelectorAll('#pl-frise .pl-fr-s').forEach(s =>
      s.classList.toggle('hi', i != null && +s.dataset.i === i));
    document.querySelectorAll('#cv2-actions .cv2-etape').forEach(li =>
      li.classList.toggle('hi', i != null && +li.dataset.i === i));
  }

  // Ce qui dépend des heures se met à jour SUR PLACE : réécrire les cartes à
  // chaque frappe ferait perdre le curseur du champ qu'on est en train de taper.
  function majEtapes() {
    const plan = state.planning;
    document.querySelectorAll('#cv2-actions .cv2-etape').forEach(li => {
      const st = plan[+li.dataset.i];
      if (!st) return;
      li.classList.toggle('deborde', st.deborde);
      const s = li.querySelector('[data-sem]');
      s.classList.toggle('ko', st.deborde);
      s.textContent = dateEtape(st) + (st.deborde ? ' · ' + T('plan_week_over') : '');
    });
    document.querySelectorAll('#cv2-actions .cv2-etapes-g').forEach(g => {
      const idx = [...g.querySelectorAll('.cv2-etape')].map(li => +li.dataset.i);
      const h = idx.reduce((t, i) => t + (+state.plan.actions[i].heures || 0), 0);
      g.querySelector('[data-gtot]').textContent = `${h} ${T('plan_h')}`;
      // la colonne choisie dans le classement met SES actions en avant
      const a = g.dataset.gact;
      g.classList.toggle('dim', !!state.planActif && String(state.planActif) !== a);
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
    state.planning = planning(c);
    renderFrise(c);
    renderVerdict(c);
    renderReglages(c);
    renderClassement();
    majEtapes();
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
    state.planActif = null;
    // Une séance a pu être fixée entre-temps : la réponse la porte.
    if ('seance' in r) state.plan.seance = r.seance;
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
        ? `<span class="pal-drapeau">${esc(T('pal_norme'))}</span>`
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
        + '" height="' + (yN - RL.YT).toFixed(1) + '" fill="#557c18" fill-opacity=".038"></rect>');
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
        + '<stop offset="' + o.toFixed(3) + '" stop-color="#557c18"></stop>'
        + '<stop offset="1" stop-color="#557c18"></stop>';
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
          + y(rail[suite].cible).toFixed(1) + '" fill="none" stroke="#3a5511"'
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
          + '" r="6" fill="' + (franchi ? '#557c18' : '#fff') + '" stroke="#3a5511"'
          + ' stroke-width="2"' + (franchi ? '' : ' stroke-dasharray="2.6 2.4"')
          + '></circle>');
        return;
      }
      const atteintNorme = yN !== null && mieux(s.mesure, n.valeur, sens);
      const col = s.statut === 'manque' ? '#b02a58'
        : (atteintNorme ? '#557c18' : (i === mes[0] ? '#a9bbd4' : '#7aa7e8'));
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
      const col = s.statut === 'manque' ? '#b02a58'
        : (atteintNorme ? '#557c18' : (i === mes[0] ? '#475467' : '#2f6fd0'));
      const colU = s.statut === 'manque' ? '#c98fa6'
        : (atteintNorme ? '#97a86f' : (i === mes[0] ? '#98a2b3' : '#8aa6cf'));
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
        + ' font-size="11.5"' + (vert ? ' font-weight="600" fill="#557c18"' : ' fill="#667085"')
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
          + (tard ? '#fdf1f5' : '#fdf4e3') + '"></rect>');
        txt.push('<text x="' + cx.toFixed(1) + '" y="' + yb + '" text-anchor="middle"'
          + ' font-size="11" font-weight="600" fill="' + (tard ? '#b02a58' : '#93571a')
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
          + ' letter-spacing="1.2" fill="#3a5511">' + esc(t) + '</text>');
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
          + ' fill="#557c18" opacity=".75">' + esc(t) + '</text>');
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

  // ⚠️ Les formulaires s'ouvrent DANS la carte, jamais en fenêtre : une modale
  // par-dessus une modale cache le chiffre qu'on vient lire pour décider.
  // ⚠️ Un formulaire qui s'ouvre DANS la carte reste un formulaire. Sans
  // en-tête ni pied, c'était un rectangle pâle où le titre flottait en 15 px,
  // la référence («&nbsp;Cible&nbsp;: 7&nbsp;%&nbsp;») tenait dans une ligne grise, le champ
  // qu'on vient remplir faisait 130 px — et la SUPPRESSION traînait en lien
  // rouge souligné, au ras des deux boutons. Le patron porte donc les trois :
  // qui on est, ce qu'on fait, et ce qui est irréversible — à l'autre bout
  // du pied, jamais à côté de « Valider ».
  function ouvrirForm(zone, o, surValider) {
    zone.innerHTML = `
      <div class="pf-tete">
        <span class="pf-ic"><i class="fa-solid ${o.icone || 'fa-pen'}"></i></span>
        <div class="pf-t"><b>${esc(o.titre)}</b>${o.sous ? `<p>${esc(o.sous)}</p>` : ''}</div>
        ${o.repere || ''}
      </div>
      <div class="pf-corps">${o.corps}</div>
      <div class="pal-form-pied">
        ${o.danger ? `<button type="button" class="pf-danger" data-del>
            <i class="fa-solid fa-trash-can"></i>${esc(o.danger)}</button>` : ''}
        <span class="sp"></span>
        <button type="button" class="pf-ko" data-ko>${esc(T('pal_annuler'))}</button>
        <button type="button" class="pf-ok" data-ok>
          <span class="ic"><i class="fa-solid fa-check"></i></span>${esc(o.valider || T('pal_valider'))}</button>
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
    /* ⚠️ La norme est RÉCUPÉRÉE de l'indicateur de performance noté dans la
       liste des activités — on ne redemande pas un chiffre que l'entreprise a
       déjà écrit ailleurs. C'est une proposition : rien n'est enregistré sans
       validation, et un indicateur illisible ne propose rien plutôt que
       d'inventer. Le serveur le lit (`norme_depuis_indicateur`) ; ici on ne
       fait que remplir les champs. */
    const sug = (!deja && r.norme_suggeree) || null;
    ouvrirForm(zone, {
      icone: 'fa-ruler', titre: T('pal_premiere'), sous: T('pal_premiere_d'),
      repere: !deja ? '' : `<span class="pf-rep"><span class="k">${esc(T('pal_norme'))}</span>`
        + `<b>${esc(fmtVal(n.valeur, n.unite))}</b>`
        + `<span class="s">${esc(n.sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins'))}</span></span>`,
      corps: `
      ${deja
        ? `<p class="pal-deja"><i class="fa-solid fa-lock"></i>${esc(T('pal_norme_deja_c'))}</p>`
        : `<div class="pal-champs">
             <label><span>${esc(T('pal_valeur'))}</span>
               <input type="text" data-v inputmode="decimal"
                      value="${esc(sug ? fmtNb(sug.valeur) : '')}"></label>
             ${champUnite(sug && sug.unite ? sug.unite : null)}
             <label><span>${esc(T('pal_sens'))}</span>
               <select data-s>
                 <option value="moins"${sug && sug.sens === 'plus' ? '' : ' selected'}>${esc(T('pal_moins'))}</option>
                 <option value="plus"${sug && sug.sens === 'plus' ? ' selected' : ''}>${esc(T('pal_plus'))}</option>
               </select></label>
           </div>
           ${sug ? `<p class="pal-vient"><i class="fa-solid fa-arrow-turn-down"></i>${esc(Tv('pal_norme_vient', { x: r.indicateur }))}</p>` : ''}`}
      <label class="pf-grand"><span class="pf-lbl">${esc(Tv('pal_mesure_q', { x: state.cibleNom }))}</span>
        <span class="pf-saisie"><input type="text" data-m inputmode="decimal" placeholder="—"></span></label>
      <p class="pal-suivra" data-apercu></p>`,
    },
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
    ouvrirForm(zone, {
      icone: 'fa-bullseye', titre: T('pal_norme_titre'), sous: T('pal_norme_d'),
      corps: `
      <div class="pal-champs">
        <label><span>${esc(T('pal_valeur'))}</span>
          <input type="text" data-v value="${esc(estNul(n.valeur) ? '' : fmtNb(n.valeur))}" inputmode="decimal"></label>
        ${champUnite(estNul(n.valeur) ? null : (n.unite || ''))}
        <label><span>${esc(T('pal_sens'))}</span>
          <select data-s>
            <option value="moins"${n.sens !== 'plus' ? ' selected' : ''}>${esc(T('pal_moins'))}</option>
            <option value="plus"${n.sens === 'plus' ? ' selected' : ''}>${esc(T('pal_plus'))}</option>
          </select></label>
      </div>`,
      // ⚠️ Effacer la norme REND la sortie qualitative : c'est irréversible
      // pour sa progression, donc c'est un danger — à l'autre bout du pied,
      // pas un lien souligné collé au bouton « Valider ».
      danger: estNul(n.valeur) ? '' : T('pal_effacer_norme'),
    },
      async z => {
        const v = lireNb(z, '[data-v]');
        if (!isFinite(v)) { toast(T('pal_valeur')); return; }
        await poserNorme(r, { valeur: v, unite: lireUnite(z),
                              sens: z.querySelector('[data-s]').value });
      });
    brancherUnite(zone);
    const off = zone.querySelector('[data-del]');
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
    const perf = r.performance, n = perf.norme || {}, u = n.unite || '';
    const prop = perf.proposition;
    ouvrirForm(zone, {
      icone: 'fa-stairs', titre: T('pal_poser_suivant'),
      sous: estNul(prop) ? '' : Tv('pal_propose', { v: fmtVal(prop, u) }),
      repere: estNul(n.valeur) ? '' : `<span class="pf-rep"><span class="k">${esc(T('pal_norme'))}</span>`
        + `<b>${esc(fmtVal(n.valeur, u))}</b>`
        + `<span class="s">${esc(n.sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins'))}</span></span>`,
      corps: `
      <div class="pal-champs">
        <label><span>${esc(T('pal_cible'))}${u ? ' (' + esc(u) + ')' : ''}</span>
          <input type="text" data-c value="${esc(estNul(prop) ? '' : fmtNb(prop))}" inputmode="decimal"></label>
        <label><span>${esc(T('pal_delai'))} (${esc(T('pal_jours'))})</span>
          <input type="text" data-j value="30" inputmode="numeric"></label>
      </div>`,
    },
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
    const n = r.performance.norme || {}, u = n.unite || '';
    const sens = n.sens || SENS_MOINS;
    ouvrirForm(zone, {
      icone: 'fa-flag-checkered', titre: T('pal_trancher'),
      valider: T('pal_trancher_ok'), danger: T('pal_retirer'),
      repere: `<span class="pf-rep"><span class="k">${esc(T('pal_cible'))}</span>`
        + `<b>${esc(fmtVal(palier.cible, u))}</b>`
        + `<span class="s">${esc(sens === SENS_MOINS ? T('pal_au_plus') : T('pal_au_moins'))}</span></span>`,
      corps: `
      <label class="pf-grand"><span class="pf-lbl">${esc(T('pal_mesure_lbl'))}</span>
        <span class="pf-saisie"><input type="text" data-m inputmode="decimal"
          placeholder="—">${u ? `<em>${esc(u)}</em>` : ''}</span></label>
      <p class="pf-verdict" data-verdict></p>
      <label class="pal-champ-large"><span>${esc(T('ses_note'))}</span>
        <textarea data-p rows="2" placeholder="${esc(T('pal_preuve_ph'))}"></textarea></label>`,
    },
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
    // ⚠️ Un APERÇU de la comparaison, pour montrer d'avance ce que le serveur
    // dira — c'est `trancher()` qui l'écrit. On tapait un chiffre et rien ne
    // répondait, alors que la séance, elle, donne son verdict en direct.
    const vue = zone.querySelector('[data-verdict]');
    const inp = zone.querySelector('[data-m]');
    const lire = () => {
      const m = lireNb(zone, '[data-m]');
      if (!isFinite(m)) { vue.className = 'pf-verdict'; vue.textContent = ''; return; }
      const ok = mieux(m, palier.cible, sens);
      vue.className = 'pf-verdict is-' + (ok ? 'ok' : 'ko');
      vue.innerHTML = `<i class="fa-solid fa-${ok ? 'circle-check' : 'circle-xmark'}"></i>`
        + `<b>${esc(T(ok ? 'pal_atteint' : 'pal_manque'))}</b>`
        + `<span>${esc(Tv('pf_contre', { c: fmtVal(palier.cible, u) }))}</span>`;
    };
    inp.addEventListener('input', lire);
    lire();
  }

  function apresEchec() {
    const b2 = $('#ev-sorties');
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
  // s'affiche telle quelle — une clé de ce catalogue a déjà été relevée
  // ainsi à l'écran.
  function nf(c, n, u) {
    const essais = n === 1 ? [c + '_1', c] : [c + '_n', c + '_pl', c];
    const k = essais.find(x => T(x) !== x) || c;
    return Tv(k, { n: n, t: u });
  }

  // ⚠️ `sens` : +1 pour l'activite suivante, −1 pour la precedente. Les
  // fleches de la bande ont remplace le rail, et passer d'une activite a
  // l'autre sans mouvement se lit comme un rechargement de page. On ne passe
  // donc pas par l'attente — `showBusy` remplacerait le classeur par une
  // roue, ce qui couperait le glisse : le sortant s'efface, le neuf entre.
  async function ouvrirEvaluation(row, sens) {
    state.activity = row;
    montrerEcran('eval');
    state.glisse = sens || 0;
    const sortant = state.glisse ? $('#ev-deux') : null;
    if (sortant) sortant.classList.add(state.glisse > 0 ? 'est-sort-d' : 'est-sort-g');
    else showBusy(null, '#cv2-ecran-eval');
    // ⚠️ UN SEUL appel. Le relief se dessine depuis les paliers que
    // `/mastery/activity` porte déjà (cible, mesure, date, échéance) :
    // `/paliers/historique` n'en rendait qu'un sous-ensemble, et une requête
    // dont personne ne lit la réponse est du temps pris à l'ouverture.
    const st = await api(
      `/mastery/activity/${state.cible}/${row.activity_id}?role_id=${state.roleId}`);
    if (st.__error) {
      // ⚠️ Un echec reseau ne doit pas laisser le classeur efface : on le
      // rend tel qu'il etait plutot qu'un ecran a moitie sorti.
      if (sortant) sortant.classList.remove('est-sort-d', 'est-sort-g');
      state.glisse = 0;
      return;
    }
    state.lastState = st;
    renderEval(st);
  }

  // ══════════════════════════════════════════════════════════════════════
  // L'ÉCRAN OÙ L'ON NOTE — « Où vous êtes », et les sorties CÔTE À CÔTE
  //
  // Tranché sur maquette, à l'échelle, avant d'écrire une ligne : trois
  // organisations dessinées, une retenue. Le classeur (11/11) ne montrait
  // qu'UNE sortie à la fois, derrière des languettes — on ne voyait donc
  // jamais ensemble les deux chiffres dont le plus bas EST le niveau de
  // l'activité, et c'est pourtant la règle de tout le module.
  //
  // À gauche un bloc de nuit qui dit OÙ L'ON EST : la chaîne (le
  // collaborateur, son rôle, l'activité — chacun avec son verdict), ce qu'on
  // note, et le BASSIN. À droite une carte par sortie, toutes visibles,
  // chacune avec ses deux notes.
  //
  // ⚠️ Le bandeau d'identité d'avant (`ev-tete`) a disparu DANS ce bloc : il
  // redisait le nom de la personne et le niveau du rôle à dix centimètres de
  // la chaîne qui les porte. Un seul objet, pas deux.
  // ══════════════════════════════════════════════════════════════════════
  function renderEval(st) {
    const z = $('#cv2-ecran-eval');
    z.innerHTML = `
      <div class="ev-corps">
        <div class="ev-deux" id="ev-deux">
          <section class="ev-ou" id="ev-ou"></section>
          <div class="ev-droite">
            <div class="ev-sorties" id="ev-sorties"></div>
            <div class="ev-pied" id="ev-pied"></div>
          </div>
        </div>
      </div>`;
    remplirOu(st);
    remplirSorties(st);
    majPied(st);
    // La technicité ne retient pas l'écran : elle remplit sa pastille quand
    // elle arrive. Elle vivait dans une colonne, elle est un réglage.
    chargerTech();
    // Le bloc neuf entre du côté d'où l'on vient. On ne remonte la page que
    // si l'on ARRIVE sur l'écran : en changeant d'activité on est déjà
    // dessus, et la faire sauter effacerait le glissé.
    glisserEntree();
    if (!state.glisse) z.scrollIntoView({ block: 'start' });
    state.glisse = 0;
  }

  // ── LE BLOC DE NUIT : où l'on est, et ce qu'on note ──────────────────
  function remplirOu(st) {
    const z = $('#ev-ou');
    const a = state.activity;
    const niv = niveauActivite(st);
    const dev = jeSuisLeDev();
    // ⚠️ UNE seule étiquette en capitales dans tout le bloc. Il en portait
    // HUIT, plus nombreuses que ce qu'elles étiquetaient : « OU VOUS ETES »
    // au-dessus d'une chaîne qui se reconnaît, les trois noms de ses maillons,
    // « LA COMPETENCE PRINCIPALE » au-dessus d'un paragraphe, « ATTENDU » et
    // « EN ECART » sur des pastilles qui portent déjà leur chiffre.
    z.innerHTML = `
      <div class="ou-h">
        <button type="button" class="ev-retour" data-retour>
          <i class="fa-solid fa-chevron-left"></i>${esc(state.roleName || T('ev_retour_role'))}</button>
        <span class="ou-pousse"></span>
        <div class="cl-nav" id="ev-nav"></div>
      </div>
      <div class="fil">${chaineHtml(st, niv)}</div>
      <div class="bas">
        <div class="bas-h">
          <div class="g">
            <div>
              <p class="bas-k">${esc(T('ou_notez'))}</p>
              <h1>${esc(a.activity_name)}</h1>
            </div>
            <span data-comp></span>
          </div>
          <div class="bas-d" data-verdict>
            <div class="z">
              <p class="bas-v"><b data-niv>—<i>/4</i></b></p>
              <span class="bas-e" data-ecart></span>
            </div>
            <span data-min></span>
          </div>
        </div>
        ${pisteHtml(st)}
        <div class="lgs" id="ev-lgs"></div>
        <p class="bas-note" data-bnote></p>
      </div>
      <div class="ou-reg" id="ev-cl-reg"></div>`;

    z.querySelector('[data-retour]').onclick = () => chargerSynthese();
    const pr = z.querySelector('[data-aller-role]');
    if (pr) pr.onclick = () => { state.voRole = state.roleId; chargerSynthese(); };
    z.querySelector('[data-min]').appendChild(boutonInfo(T('ev_min_t'), texteMinimum()));
    // ⚠️ La description de la compétence passe derrière un « i ». Elle
    // occupait un paragraphe de trois lignes sous le nom de l'activité, avec
    // sa propre étiquette au-dessus — c'est le motif de la maison : une
    // phrase passe derrière un « i », elle ne disparaît pas.
    if (a.competence) {
      z.querySelector('[data-comp]').appendChild(boutonInfo(T('ou_comp'), a.competence));
    }
    // ⚠️ Le CHIFFRE et l'écart sont écrits par la fonction dont c'est le
    // métier, pas ici : `majPiste` ne touche qu'à ce qui BOUGE (la largeur du
    // remplissage). Un `innerHTML` dans la piste la ferait sauter d'un niveau
    // à l'autre au lieu de l'y faire s'étendre.
    majNiveauTenu(st);
    majPiste(st);
    reglagesOu(st);
    majNav();
  }

  // ── LA CHAÎNE : le collaborateur, son rôle, l'activité ───────────────
  // ⚠️ Chaque maillon porte SON verdict, et c'est la cascade du minimum qui
  // se lit : le niveau d'un rôle est le plus bas de ses activités, celui
  // d'une activité le plus bas de ses sorties. NULL ≠ 0 — un rôle dont une
  // activité n'est pas notée n'a pas de niveau du tout, pas un zéro.
  function chaineHtml(st, nivAct) {
    const ch = `<svg class="ch" width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M9 6l6 6-6 6"/></svg>`;
    const bd = v => estNul(v)
      ? `<span class="bd na">${esc(T('not_assessed'))}</span>`
      : `<span class="bd">${v}</span>`;
    // ⚠️ L'ÉTIQUETTE tombe à l'ŒIL et reste dans l'`aria-label` : « LE
    // COLLABORATEUR », « LE RÔLE », « L'ACTIVITÉ » nommaient ce qui se
    // reconnaît sans elles, et c'étaient trois des huit étiquettes du bloc.
    // Un lecteur d'écran, lui, ne lit pas la chaîne d'un coup d'œil.
    const dedans = (nom, badge) =>
      `<span class="d"><span class="z">${esc(nom)}</span></span>${badge}`;
    const aria = (cle, nom) => `aria-label="${esc(T(cle) + ' : ' + nom)}"`;
    const mail = (cle, nom, badge, ici) =>
      `<span class="mail${ici ? ' ici' : ''}" ${aria(cle, nom)}>${dedans(nom, badge)}</span>`;
    // ⚠️ Le maillon du RÔLE est une PORTE : il ramène à la vue d'ensemble,
    // ouverte sur le détail de CE rôle — une ligne par activité, avec sa
    // cible. On n'y venait que par un point du radar, et il n'existait aucun
    // chemin depuis l'écran où l'on note.
    const porte = (cle, nom, badge) =>
      `<button type="button" class="mail est-porte" data-aller-role
         title="${esc(T('ou_voir_role'))}" ${aria(cle, nom)}>${dedans(nom, badge)}
         <i class="fa-solid fa-arrow-up-right-from-square"></i></button>`;
    const nomRole = state.roleName || '—';
    return mail('ou_collab', state.cibleNom, '', false) + ch
      + (state.roleId ? porte('ou_role', nomRole, bd(niveauRoleNum()))
                      : mail('ou_role', nomRole, bd(niveauRoleNum()), false)) + ch
      + mail('ou_act', state.activity.activity_name, bd(nivAct), true);
  }

  // Le niveau d'un rôle : le MINIMUM de ses activités, et NULL tant qu'il en
  // manque une. Une moyenne partielle laisserait croire qu'un rôle à moitié
  // noté est tenu.
  function niveauRoleNum() {
    const niv = state.rows.map(a => a.demonstrated_level).filter(v => !estNul(v));
    if (!niv.length || niv.length < state.rows.length) return null;
    return Math.min.apply(null, niv);
  }

  function niveauRole() {
    const m = niveauRoleNum();
    return m === null ? T('not_assessed') : m + ' · ' + levelName(m);
  }

  // ⚠️ Le niveau de l'activité TEL QU'IL SERAIT si l'on enregistrait. C'est
  // un APERÇU, pas une seconde règle : le serveur reste la source, et l'écran
  // se recharge après l'enregistrement. Mais il ne connaît pas la note qu'on
  // vient de poser — et c'est justement elle qu'on veut voir bouger l'eau.
  function niveauActivite(st) {
    const v = (st.results || []).map(r => niveauOfficiel(r));
    if (!v.length || v.some(estNul)) return null;
    return Math.min.apply(null, v);
  }

  function majEcart(z, niv, req) {
    const e = z.querySelector('[data-ecart]'); if (!e) return;
    if (estNul(niv) || req === null) {
      e.className = 'bas-e'; e.textContent = estNul(niv) ? T('not_assessed') : '';
      return;
    }
    const d = niv - req;
    e.className = 'bas-e ' + (d >= 0 ? 'ok' : 'ko');
    e.textContent = d > 0 ? Tv('ou_au_dessus', { n: d })
      : (d === 0 ? T('ou_au_niveau') : Tv('ou_ecart', { n: -d }));
  }

  // ── LA PISTE : le niveau de l'activité, et la règle du minimum ──────
  //
  // ⚠️ LA CUVE VERTICALE EST ABANDONNÉE. C'est l'arbitrage de cette passe,
  // tranché sur prototype : on y perd la métaphore de l'eau qui monte, on y
  // gagne 90 px de hauteur et surtout la lecture — la jauge va de gauche à
  // droite, comme toutes les autres jauges de l'application.
  //
  // ⚠️ Et c'est ce qui CORRIGE le bassin : les noms des sorties étaient
  // DEDANS, tronqués et superposés (« sur le graphe en bas on comprend
  // rien »). Ils sont désormais sous la piste, une ligne chacun, en entier,
  // avec le numéro qui les relie à leur carte de droite.
  //
  // ⚠️ NULL ≠ 0 : une activité dont une sortie n'est pas notée n'a PAS de
  // niveau, et sa piste est HACHURÉE jusqu'au plus bas de ce qu'on sait —
  // pas remplie à zéro, qui voudrait dire « non démontré ».
  const PST = n => (n / 4) * 100;

  function pisteHtml(st) {
    const req = estNul(st.required_level) ? null : st.required_level;
    let g = '';
    for (let i = 0; i <= 4; i++) {
      g += `<span data-g="${i}" style="left:${PST(i)}%">${i}</span>`;
    }
    return `<div class="pst">
      <div class="pst-v">
        <span class="pst-r" data-pst></span>
        ${req === null ? '' : `<span class="pst-a" style="left:${PST(req)}%"
          aria-label="${esc(Tv('ou_attendu', { n: req }))}"
          title="${esc(Tv('ou_attendu', { n: req }))}"></span>`}
      </div>
      <div class="pst-g">${g}</div>
    </div>`;
  }

  // ⚠️ Sur place, et non en réécrivant la piste : elle S'ÉTEND quand on pose
  // une note, et c'est ce mouvement qui fait comprendre la règle du minimum.
  // Réécrite, elle sauterait d'un niveau à l'autre.
  function majPiste(st) {
    const z = $('#ev-ou'); if (!z) return;
    const req = estNul(st.required_level) ? null : st.required_level;
    const niv = niveauActivite(st);
    const notes = (st.results || []).map(r => niveauOfficiel(r));
    const connus = notes.filter(v => !estNul(v));
    const manque = notes.length - connus.length;
    const bas = connus.length ? Math.min.apply(null, connus) : 0;
    const vert = !estNul(niv) && req !== null && niv >= req;

    const r = z.querySelector('[data-pst]');
    if (r) {
      r.className = 'pst-r ' + (estNul(niv) ? 'hach' : (vert ? 'vert' : 'bleu'));
      r.style.width = PST(estNul(niv) ? bas : niv) + '%';
    }
    // La graduation met en avant le niveau tenu et la cible : ce sont les deux
    // seuls chiffres de l'échelle qui veulent dire quelque chose ici.
    z.querySelectorAll('.pst-g span').forEach(g => {
      const n = +g.dataset.g;
      g.className = (n === req || (!estNul(niv) && n === niv)) ? 'fort' : '';
    });
    const d = z.querySelector('[data-verdict]');
    if (d) {
      d.classList.toggle('est-vert', vert);
      d.classList.toggle('est-vide', estNul(niv));
    }

    // ── les sorties, une ligne chacune ──
    const lg = z.querySelector('#ev-lgs');
    if (lg) {
      lg.innerHTML = (st.results || []).map((x, i) => {
        const v = niveauOfficiel(x);
        const nu = estNul(v);
        // ⚠️ Celle qui RETIENT le niveau est mise en avant : c'est la règle
        // du minimum, et c'est ici qu'elle se VOIT. Tant qu'il manque une
        // note, c'est la plus basse de celles qu'on a.
        const porte = !nu && v === (estNul(niv) ? bas : niv);
        const tenu = !nu && (req === null ? v >= SEUIL_TENU : v >= req);
        let j = '';
        for (let k = 1; k <= 4; k++) {
          j += `<i class="${!nu && k <= v ? 'on' + (tenu ? ' v' : '') : ''}"></i>`;
        }
        return `<div class="s${porte ? ' est-bas' : ''}${nu ? ' est-off' : ''}">
          <b class="${tenu ? 'v' : ''}">${i + 1}</b>
          <span class="nm" title="${esc(x.name)}">${esc(x.name)}</span>
          <span class="nv"><span class="jau">${j}</span>
            <u>${nu ? esc(T('not_assessed')) : v}</u></span>
        </div>`;
      }).join('');
    }
    const note = z.querySelector('[data-bnote]');
    if (note) note.textContent = manque ? nf('ou_manque', manque) : '';
  }

  // ── Les réglages : trois pastilles de verre, et les deux portes ──────
  function reglagesOu(st) {
    const reg = $('#ev-cl-reg'); if (!reg) return;
    reg.innerHTML = '';
    const chip = (cls, icone, lbl, val) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'cl-rb' + (cls ? ' ' + cls : '');
      // ⚠️ Deux lignes : le nom, puis CE QUE LE BOUTON CONTIENT. C'est la
      // valeur qui dit s'il faut l'ouvrir, et elle a sa ligne à elle — sur la
      // même que le nom, elle faisait déborder la colonne.
      b.innerHTML = `<span class="ic"><i class="fa-solid ${icone}"></i></span>`
        + `<span class="tx"><b>${esc(lbl)}</b>`
        + `<span class="val">${esc(val || '')}</span></span>`;
      reg.appendChild(b);
      return b;
    };
    chip('', 'fa-microchip', T('ev_tech'), '…').onclick = () => ouvrirTechnicite();
    reg.lastChild.id = 'ev-chip-tech';
    // ⚠️ L'ambre ne se pose que s'il y a une échéance : une pastille
    // d'avertissement allumée en permanence n'avertit plus de rien.
    const ech = prochaineEcheance(st);
    chip(ech ? 'amb' : '', 'fa-calendar-days', T(ech ? 'cl_seance' : 'ses_cal'),
         ech ? fmtDate(ech.quand) : '').onclick = () => ouvrirCalendrier();
    if (jeSuisLeDev()) {
      chip('', 'fa-file-lines', T('plan_open')).onclick = () => ouvrirPlan();
      // ⚠️⚠️ CONFIGURER n'était plus joignable : son seul chemin était le
      // bouton de `.ev-vide`, qui ne s'affiche que sur une activité SANS
      // sortie — et `activity_mastery` matérialise les connexions sortantes,
      // donc une activité qui a une flèche en a toujours. C'était sans
      // conséquence tant que la fenêtre ne portait que la nature des sorties
      // (que personne ne lit) ; ce ne l'est plus : la NORME s'y règle.
      // ⚠️ La valeur dit s'il faut l'ouvrir — combien de sorties n'ont pas de
      // norme chiffrée. « 2 sorties » aurait répété ce que l'écran montre.
      const sans = (st.results || []).filter(r => !r.mesurable).length;
      chip('', 'fa-sliders', T('conf_open'),
           sans ? nf('conf_sans_norme', sans) : T('conf_tout_norme'))
        .onclick = () => ouvrirConfiguration(state.activity);
    }
    majChipTech();
  }

  // ── LA NAVIGATION : une flèche de chaque côté ────────────────────────
  // ⚠️ La flèche gauche n'existe que passé la première, la droite que tant
  // qu'il en reste une : un bouton qui ne mène nulle part n'est pas un
  // bouton. Le compte « 2 / 5 » dit où l'on est — sans lui, rien ne dirait
  // qu'il y en a d'autres.
  function indexActivite() {
    const id = (state.activity || {}).activity_id;
    return state.rows.findIndex(a => a.activity_id === id);
  }

  function majNav() {
    const z = $('#ev-nav'); if (!z) return;
    const i = indexActivite(), n = state.rows.length;
    z.innerHTML = '';
    // Une seule activité : il n'y a nulle part où aller.
    z.classList.toggle('hidden', i < 0 || n < 2);
    if (i < 0 || n < 2) return;
    const fleche = (sens, cible) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'cl-nav-b'; b.dataset.sens = String(sens);
      // ⚠️ L'info-bulle dit OÙ l'on va : une flèche nue ne dit même pas
      // comment s'appelle l'activité d'à côté.
      const lbl = T(sens > 0 ? 'cl_suiv' : 'cl_prec') + ' · ' + cible.activity_name;
      b.title = lbl; b.setAttribute('aria-label', lbl);
      b.innerHTML = `<i class="fa-solid fa-chevron-${sens > 0 ? 'right' : 'left'}"></i>`;
      b.onclick = () => ouvrirEvaluation(cible, sens);
      return b;
    };
    if (i > 0) z.appendChild(fleche(-1, state.rows[i - 1]));
    const p = document.createElement('span');
    p.className = 'cl-nav-p'; p.textContent = (i + 1) + ' / ' + n;
    z.appendChild(p);
    if (i < n - 1) z.appendChild(fleche(1, state.rows[i + 1]));
  }

  // ⚠️ La classe est retirée à la fin de l'animation : un
  // `animation-fill-mode: both` laisse son `transform` appliqué, et un élément
  // transformé devient le repère des descendants `position: fixed` — le piège
  // déjà payé sur la fiche d'examen de l'éditeur.
  function glisserEntree() {
    if (!state.glisse) return;
    const cl = $('#ev-deux'); if (!cl) return;
    const c = state.glisse > 0 ? 'est-ent-d' : 'est-ent-g';
    cl.classList.add(c);
    cl.addEventListener('animationend', () => cl.classList.remove(c), { once: true });
  }

  // ══════════════════════════════════════════════════════════════════════
  // CE QUE TOUT L'ÉCRAN RELIT — une note, une source
  //
  // ⚠️ Chaque sortie avait SA carte, et les deux régimes en avaient deux très
  // différentes : « pas encore notée » ne ressemblait en rien à « déjà
  // notée ». L'axe partagé (10/11) les a mises sur la même rangée ; le
  // CLASSEUR (11/11) en fait les languettes d'un classeur — la comparaison
  // se lit sur les languettes, et la feuille ne porte qu'UNE sortie.
  //
  // La note posée et pas encore enregistrée vit dans `state.saisie`, et
  // c'est la seule source : la piste, la languette, la bande et le pied la
  // relisent tous. Deux états parallèles finiraient par se contredire.
  // ══════════════════════════════════════════════════════════════════════

  // Un nombre lisible : 48 et non 48.0, 46.5 et non 46.500000000000004.
  function nombre(v) {
    if (estNul(v)) return '';
    const n = Math.round(v * 100) / 100;
    return String(n).replace('.', LANG === 'en' ? '.' : ',');
  }

  // Ma note sur cette sortie : ce que je viens de poser s'il y a lieu, sinon
  // ce qui est enregistré. UNE source — la piste de la feuille l'écrit, et
  // tout ce qui affiche la note relit cette carte.
  function maNote(r) {
    const s = state.saisie && state.saisie[r.data_id];
    if (s && 'niveau' in s) return s.niveau;
    return jeSuisLeDev() ? r.demonstrated_level : r.self_level;
  }

  // ══════════════════════════════════════════════════════════════════════
  // LE CLASSEUR — la bande, les languettes, la feuille     (11/11/2026)
  //
  // ⚠️ Bande + languettes + feuille ne font qu'UN objet, avec une seule
  // ombre : trois cartes empilées, c'étaient trois contours pour un seul
  // sujet, et c'est l'empilement qu'on reprochait à l'écran.
  //
  // ⚠️ La comparaison entre sorties se lit SUR LES LANGUETTES : chacune porte
  // sa jauge en quatre pas et le trait de l'attendu — la convention de toute
  // l'application. Une barre de 5 px ne la portait pas.
  //
  // ⚠️ La colonne de droite a disparu : elle redisait les sorties mot pour
  // mot, et ses deux réglages (technicité, prochaine séance) sont des
  // pastilles sur la bande.
  // ══════════════════════════════════════════════════════════════════════

  // La sortie ouverte dans la feuille. Elle survit au re-rendu des
  // languettes : sinon toute note posée ramènerait à la première sortie.
  // ── LES SORTIES, TOUTES VISIBLES ─────────────────────────────────────
  // ⚠️ Elles étaient les LANGUETTES d'un classeur et la feuille n'en portait
  // qu'une : on ne voyait jamais ensemble les deux chiffres dont le plus bas
  // EST le niveau de l'activité. Elles sont désormais côte à côte, dans la
  // colonne de droite, et c'est le BASSIN qui porte la comparaison.
  function remplirSorties(st) {
    // Ce qui a été POSÉ et pas encore enregistré. UNE source : la piste de la
    // carte écrit ici, et tout ce qui affiche la note relit cette carte.
    state.saisie = {};
    const z = $('#ev-sorties');
    z.innerHTML = '';
    if (!(st.results && st.results.length)) {
      const w = document.createElement('div');
      w.className = 'ev-vide';
      w.innerHTML = `<p>${esc(jeSuisLeDev() ? T('rien_a_evaluer') : T('pas_configuree'))}</p>`;
      if (jeSuisLeDev()) {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'pal-b pal-b--prim';
        b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-sliders"></i></span>${esc(T('conf_go'))}`;
        b.onclick = () => ouvrirConfiguration(state.activity);
        w.appendChild(b);
      }
      z.appendChild(w);
      majPiste(st);
      return;
    }
    (st.results || []).forEach((r, i) => z.appendChild(carteSortie(r, st, i)));
    majPiste(st);
  }

  // ── LA CARTE D'UNE SORTIE ────────────────────────────────────────────
  // ⚠️ Les deux régimes prennent la MÊME forme : un rail de couleur dit
  // lequel, un disque dit le niveau. C'est leur ressemblance qui rend la
  // différence lisible — et le disque le plus bas, c'est le niveau de
  // l'activité.
  // ⚠️ Le NUMÉRO relie la carte à son repère dans le bassin : sans lui, rien
  // ne dirait quelle pastille appartient à quelle sortie.
  function carteSortie(r, st, i) {
    const mesuree = !!(r.mesurable && r.performance && r.performance.norme);
    const f = document.createElement('section');
    f.className = 'so' + (mesuree ? ' lue' : ' pose');
    f.dataset.dataId = r.data_id;

    const tete = document.createElement('div');
    tete.className = 'so-t';
    tete.innerHTML = `<span class="so-n">${i + 1}</span>
      <span class="disq" data-disq></span>
      <div class="nm"><b>${esc(r.name)}</b></div>
      <span class="regime ${mesuree ? 'b' : 'a'}">${esc(T(mesuree ? 'so_mesuree' : 'so_main'))}</span>`;
    f.appendChild(tete);

    // ⚠️ Les formulaires s'ouvrent DANS la carte, jamais en fenêtre : une
    // modale par-dessus une modale cache le chiffre qu'on vient lire pour
    // décider.
    const form = document.createElement('div');
    form.className = 'pal-form hidden';
    f.appendChild(ardoiseSortie(r, st, form));
    f.appendChild(form);
    f.appendChild(notaSortie(r, st));
    if (jePosePour(r)) f.appendChild(preuveSortie(r, st));
    majDisque(f, r, st);
    return f;
  }

  function majDisque(carte, r, st) {
    const d = carte.querySelector('[data-disq]'); if (!d) return;
    const v = niveauOfficiel(r);
    const req = estNul(st.required_level) ? null : st.required_level;
    const vert = !estNul(v) && (req === null ? v >= SEUIL_TENU : v >= req);
    d.className = 'disq' + (estNul(v) ? ' q' : (vert ? ' g' : ''));
    d.textContent = estNul(v) ? '—' : String(v);
  }

  // ⚠️ UNE seule source : `state.saisie`. La piste, le disque, le bassin, la
  // chaîne et le pied relisent tous cette carte — deux états parallèles
  // finiraient par se contredire, c'est le piège des deux implémentations
  // d'un même verdict.
  function poserNote(r, niveau, st) {
    state.saisie = state.saisie || {};
    const avant = state.saisie[r.data_id] || {};
    // ⚠️ On ne touche PAS à la preuve. La route ne réécrit `evidence` que si
    // la CLÉ est envoyée : avant ce correctif elle faisait
    // `(evidence or "").strip() or None` sur une clé absente, donc poser un
    // niveau là où il n'y a pas de champ de preuve effaçait ce que quelqu'un
    // avait écrit. C'est la ROUTE qui a été réparée, pas l'écran.
    state.saisie[r.data_id] = Object.assign({}, avant, { niveau: niveau });
    const carte = $(`#ev-sorties .so[data-data-id="${r.data_id}"]`);
    if (carte) {
      const z = carte.querySelector('.nota');
      if (z) majNota(z, r, st);
      majDisque(carte, r, st);
    }
    majPiste(st);
    majNiveauTenu(st);
    majPied(st);
  }

  // Le niveau de l'activité, et le maillon de la chaîne qui le porte : ils
  // bougent avec l'eau, sans réécrire le bloc de nuit — le réécrire ferait
  // sauter l'eau d'un niveau à l'autre au lieu de la faire monter.
  function majNiveauTenu(st) {
    const z = $('#ev-ou'); if (!z) return;
    const niv = niveauActivite(st);
    const req = estNul(st.required_level) ? null : st.required_level;
    const v = z.querySelector('[data-niv]');
    if (v) v.innerHTML = (estNul(niv) ? '—' : niv) + '<i>/4</i>';
    const m = z.querySelector('.mail.ici .bd');
    if (m) {
      m.className = 'bd' + (estNul(niv) ? ' na' : '');
      m.textContent = estNul(niv) ? T('not_assessed') : String(niv);
    }
    majEcart(z, niv, req);
  }

  function noterPreuve(r, texte, st) {
    state.saisie = state.saisie || {};
    const avant = state.saisie[r.data_id] || {};
    if (!('niveau' in avant)) avant.niveau = maNote(r);
    avant.preuve = texte;
    state.saisie[r.data_id] = avant;
    majPied(st);
  }

  // ── LA TECHNICITÉ : un réglage, donc un dialogue ──────────────────────
  // ⚠️ C'est un AUTRE axe que la maîtrise (le contexte technique), et c'est un
  // réglage : il n'a pas à occuper une colonne de l'écran où l'on note. Le
  // tiroir porte les dialogues courts — configurer, diagnostiquer, et ceci.
  const chargerTech = () => loadTech(null);

  function majChipTech() {
    const c = $('#ev-chip-tech'); if (!c) return;
    const t = state.tech;
    // ⚠️ La valeur n'est plus le `<b>` (c'est le NOM du bouton désormais) :
    // elle a sa ligne, et son crochet.
    const b = c.querySelector('.val'); if (!b) return;
    if (!t) { b.textContent = '…'; return; }
    const ecart = t.domains.filter(d => !estNul(d.gap) && d.gap < 0).length;
    // ⚠️ RENVERSEMENT : « aucun domaine » s'écrit de nouveau. La règle d'avant
    // (« rien à annoncer ne s'annonce pas ») venait d'une rangée de QUATRE
    // pastilles où la valeur partageait la ligne du nom et faisait déborder la
    // colonne. Trois boutons, deux lignes : elle tient, et elle dit quelque
    // chose — on sait qu'il n'y a rien sans avoir à ouvrir.
    b.textContent = t.domains.length
      ? (ecart ? nf('cl_tech_ecart', ecart) : nf('cl_tech', t.domains.length))
      : T('cl_tech_0');
    c.classList.toggle('ko', !!ecart);
  }

  function ouvrirTechnicite() {
    ouvrirDialogue(T('ev_tech'), true);
    // ⚠️ `ouvrirDialogue` repose `vue = 'eval'` à chaque ouverture : la
    // largeur de la table ne déborde donc pas sur les deux autres dialogues.
    $('#cv2-drawer').dataset.vue = 'tech';
    const b = $('#cv2-drawer-body');
    // ⚠️ L'explication passe derrière un « i » : trois lignes en tête de
    // fenêtre pour une règle qu'on lit une fois, et elles prenaient la place
    // de la table. C'est le motif de la maison — une phrase se range derrière
    // un « i », elle ne disparaît pas.
    b.innerHTML = `<div class="cv2-tech-z">
      <div class="tch-h"><span class="t">${esc(T('tech_les'))}</span>
        <span class="cv2-i" tabindex="0" role="button" aria-label="${esc(T('ev_tech'))}"
          ><i class="fa-solid fa-info"></i></span></div>
      <div class="cv2-domlist"></div>
      <div class="cv2-domadd"></div>
    </div>`;
    setFooter([]);
    const z = b.querySelector('.cv2-tech-z');
    // ⚠️ `brancherInfo` ÉCHAPPE son texte : les marqueurs [[b]] s'y
    // afficheraient en clair. On les retire, et `tech_note` suit — c'est
    // l'autre moitié de ce que la fenêtre disait en tête.
    brancherInfo(z.querySelector('.cv2-i'), T('ev_tech'),
      T('tech_quoi').split('[[b]]').join('').split('[[/b]]').join('')
      + '\n\n' + T('tech_note'));
    const aid = state.activity.activity_id;
    const t = state.tech || { domains: [], all: [] };
    renderDomList(z.querySelector('.cv2-domlist'), aid, t.domains);
    if (jeSuisLeDev()) renderDomAdd(z, aid, t.all, t.domains);
  }

  // ⚠️ « Enregistrer » ne s'allume QUE si quelque chose a été posé. Un bouton
  // toujours actif qui ne trouve rien à écrire annonce un succès qui n'a pas
  // eu lieu — on notait, on validait, et rien n'était enregistré (15/10).
  function majPied(st) {
    const pied = $('#ev-pied'); if (!pied) return;
    const n = Object.keys(state.saisie || {}).length;
    pied.innerHTML = `<p>${esc(n ? nf('ax_en_attente', n) : '')}</p>`;
    if (jeSuisLeDev() && aUnEcart(st)) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'pal-b pal-b--doux';
      b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-magnifying-glass-chart"></i></span>${esc(T('diagnose'))}`;
      b.onclick = () => showDiagnostic();
      pied.appendChild(b);
    }
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'pal-b pal-b--prim'; b.id = 'cv2-save-btn';
    b.disabled = !n;
    b.innerHTML = `<span class="pal-b-ic"><i class="fa-solid fa-check"></i></span>`
      + esc(jeSuisLeDev() ? T('save_eval') : T('save_self'));
    b.onclick = saveEvaluation;
    pied.appendChild(b);
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

  // ── Le détail des séances ──
  // ⚠️ Il n'y a plus de second graphe à ouvrir : le relief EST le graphe, et
  // il est là dès l'ouverture de la carte. Ce qui se déplie, c'est ce qu'il
  // ne peut pas montrer — séance par séance, qui a relevé quoi, et la preuve.
  // ⚠️ Il s'ouvre À CÔTÉ (`.pal-evo-duo`), parce que la bande de la vue
  // d'ensemble a toute la largeur de la page. Il avait une seconde
  // disposition, EMPILÉE, pour la fenêtre des courbes — 1 060 px, où le
  // partage ramenait les libellés du relief sous 6 px. La fenêtre est
  // partie, et avec elle le seul endroit qui l'empilait.
  function basculerHisto(card, r) {
    const ouvert = card.querySelector('.pal-histo');
    if (ouvert) {
      ouvert.remove();
      card.dataset.evo = '';
      majLibelleEvo(card, false);
      return;
    }
    const bloc = blocHistorique(r);
    // À CÔTÉ : le bouton qui a OUVERT la section ne bouge pas d'un pixel —
    // il reste au pied du relief, et son libellé devient « masquer ». Un
    // second bouton de fermeture dans le panneau ne ferait que doubler celui
    // qu'on a sous les yeux.
    // ⚠️ Le BILAN sert de repère de repli : `.pal-pied` n'existe plus, et un
    // `querySelector` qui rend `null` couperait la suite sans rien dire.
    const anc = card.querySelector('.pal-evo-duo')
      || card.querySelector('.pal-bilan') || card.lastElementChild;
    if (anc.classList.contains('pal-evo-duo')) anc.appendChild(bloc);
    else anc.insertAdjacentElement('afterend', bloc);
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
            <i class="fa-solid fa-chevron-left"></i>${esc(T('ses_cal'))}</button>
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
          <i class="fa-solid fa-chevron-left"></i>${esc(retour)}</button>
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
