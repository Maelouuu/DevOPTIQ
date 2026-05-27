# Code/translations.py
# Dictionnaire de traductions FR/EN pour l'interface DevOPTIQ.
# Usage :  from Code.translations import t
#          t('nav.activities')           → utilise la langue de la session Flask
#          t('nav.activities', lang='en') → force la langue

from flask import session

TRANSLATIONS = {
    'fr': {
        # ── Navigation ──────────────────────────────────────────────────────
        'nav.activities':   'Activités',
        'nav.roles':        'Rôles',
        'nav.competences':  'Compétences',
        'nav.time':         'Temps',
        'nav.accounts':     'Comptes',
        'nav.hr':           'Gestion RH',
        'nav.career':       'Projection Métiers',
        'nav.tools':        'Gestion Outils',
        'nav.carto':        'Cartographie',
        'nav.settings':     'Paramètres',
        'nav.logout':       'Déconnexion',

        # ── Page Settings ────────────────────────────────────────────────────
        'settings.title':           'Paramètres',
        'settings.subtitle':        'Personnalisez votre expérience OPTIQ',
        'settings.language':        'Langue de l\'interface',
        'settings.language.desc':   'Choisissez la langue d\'affichage de l\'application.',
        'settings.language.fr':     'Français',
        'settings.language.en':     'English',
        'settings.save':            'Enregistrer',
        'settings.saved':           'Paramètres enregistrés',
        'settings.section.interface': 'Interface',

        # ── Boutons génériques ───────────────────────────────────────────────
        'btn.save':       'Enregistrer',
        'btn.cancel':     'Annuler',
        'btn.delete':     'Supprimer',
        'btn.add':        'Ajouter',
        'btn.edit':       'Modifier',
        'btn.import':     'Importer',
        'btn.export':     'Exporter',
        'btn.confirm':    'Confirmer',
        'btn.close':      'Fermer',
        'btn.validate':   'Valider',
        'btn.reset':      'Réinitialiser',
        'btn.send':       'Envoyer',
        'btn.generate':   'Générer',
        'btn.download':   'Télécharger',
        'btn.back':       'Retour',
        'btn.create':     'Créer',
        'btn.apply':      'Appliquer',

        # ── Statuts ──────────────────────────────────────────────────────────
        'status.loading': 'Chargement…',
        'status.saving':  'Enregistrement…',
        'status.saved':   'Enregistré',
        'status.error':   'Une erreur est survenue',
        'status.success': 'Opération réussie',
        'status.empty':   'Aucun élément',
        'status.no_data': 'Aucune donnée disponible',

        # ── Champs communs ───────────────────────────────────────────────────
        'common.name':        'Nom',
        'common.description': 'Description',
        'common.date':        'Date',
        'common.type':        'Type',
        'common.status':      'Statut',
        'common.level':       'Niveau',
        'common.role':        'Rôle',
        'common.user':        'Utilisateur',
        'common.action':      'Action',
        'common.yes':         'Oui',
        'common.no':          'Non',
        'common.required':    'Obligatoire',
        'common.optional':    'Optionnel',
        'common.search':      'Rechercher',
        'common.filter':      'Filtrer',
        'common.all':         'Tous',
        'common.none':        'Aucun',
        'common.total':       'Total',
        'common.average':     'Moyenne',

        # ── Titres de pages ──────────────────────────────────────────────────
        'page.activities':  'Activités',
        'page.roles':       'Rôles',
        'page.competences': 'Compétences',
        'page.time':        'Gestion du temps',
        'page.accounts':    'Gestion des comptes',
        'page.hr':          'Gestion RH',
        'page.career':      'Projection Métiers',
        'page.tools':       'Gestion des outils',
        'page.carto':       'Cartographie',
        'page.settings':    'Paramètres',
        'page.import':      'Import',
        'page.export':      'Export',
        'page.changelog':   'Journal des modifications',
        'page.chatbot':     'Assistant IA',
        'page.performance': 'Performance',

        # ── Activités ────────────────────────────────────────────────────────
        'activity.label':       'Activité',
        'activity.tasks':       'Tâches',
        'activity.tools':       'Outils',
        'activity.competences': 'Compétences',
        'activity.links':       'Connexions',
        'activity.performance': 'Performance',
        'activity.garant':      'Garant',

        # ── Rôles ────────────────────────────────────────────────────────────
        'role.label':      'Rôle',
        'role.members':    'Titulaires',
        'role.onboarding': 'Plan d\'onboarding',

        # ── Compétences ──────────────────────────────────────────────────────
        'competence.savoir_faire': 'Savoir-faire',
        'competence.savoir':       'Savoir',
        'competence.softskill':    'Compétence comportementale',
        'competence.aptitude':     'Aptitude',

        # ── Temps ────────────────────────────────────────────────────────────
        'time.project':  'Analyse par projet',
        'time.analysis': 'Analyse par activité',
        'time.role':     'Analyse par rôle',
        'time.weakness': 'Analyse des faiblesses',

        # ── Import ───────────────────────────────────────────────────────────
        'import.excel':   'Import Excel',
        'import.ai':      'Import IA',
        'import.analyze': 'Analyser',
        'import.inject':  'Injecter en base',

        # ── Évaluations ──────────────────────────────────────────────────────
        'eval.garant':      'Garant',
        'eval.manager':     'Manager',
        'eval.rh':          'RH',
        'eval.level':       'Niveau',
        'eval.note':        'Note',
        'eval.eval_number': 'N° évaluation',

        # ── Cartographie ─────────────────────────────────────────────────────
        'carto.editor':      'Éditeur',
        'carto.save':        'Sauvegarder la cartographie',
        'carto.bands':       'Bandes',
        'carto.shapes':      'Formes',
        'carto.connections': 'Connexions',
    },

    'en': {
        # ── Navigation ──────────────────────────────────────────────────────
        'nav.activities':   'Activities',
        'nav.roles':        'Roles',
        'nav.competences':  'Competencies',
        'nav.time':         'Time',
        'nav.accounts':     'Accounts',
        'nav.hr':           'HR Management',
        'nav.career':       'Career Mapping',
        'nav.tools':        'Tools Management',
        'nav.carto':        'Cartography',
        'nav.settings':     'Settings',
        'nav.logout':       'Log out',

        # ── Page Settings ────────────────────────────────────────────────────
        'settings.title':           'Settings',
        'settings.subtitle':        'Customize your OPTIQ experience',
        'settings.language':        'Interface language',
        'settings.language.desc':   'Choose the display language for the application.',
        'settings.language.fr':     'Français',
        'settings.language.en':     'English',
        'settings.save':            'Save',
        'settings.saved':           'Settings saved',
        'settings.section.interface': 'Interface',

        # ── Boutons génériques ───────────────────────────────────────────────
        'btn.save':       'Save',
        'btn.cancel':     'Cancel',
        'btn.delete':     'Delete',
        'btn.add':        'Add',
        'btn.edit':       'Edit',
        'btn.import':     'Import',
        'btn.export':     'Export',
        'btn.confirm':    'Confirm',
        'btn.close':      'Close',
        'btn.validate':   'Validate',
        'btn.reset':      'Reset',
        'btn.send':       'Send',
        'btn.generate':   'Generate',
        'btn.download':   'Download',
        'btn.back':       'Back',
        'btn.create':     'Create',
        'btn.apply':      'Apply',

        # ── Statuts ──────────────────────────────────────────────────────────
        'status.loading': 'Loading…',
        'status.saving':  'Saving…',
        'status.saved':   'Saved',
        'status.error':   'An error occurred',
        'status.success': 'Operation successful',
        'status.empty':   'No items',
        'status.no_data': 'No data available',

        # ── Champs communs ───────────────────────────────────────────────────
        'common.name':        'Name',
        'common.description': 'Description',
        'common.date':        'Date',
        'common.type':        'Type',
        'common.status':      'Status',
        'common.level':       'Level',
        'common.role':        'Role',
        'common.user':        'User',
        'common.action':      'Action',
        'common.yes':         'Yes',
        'common.no':          'No',
        'common.required':    'Required',
        'common.optional':    'Optional',
        'common.search':      'Search',
        'common.filter':      'Filter',
        'common.all':         'All',
        'common.none':        'None',
        'common.total':       'Total',
        'common.average':     'Average',

        # ── Titres de pages ──────────────────────────────────────────────────
        'page.activities':  'Activities',
        'page.roles':       'Roles',
        'page.competences': 'Competencies',
        'page.time':        'Time Management',
        'page.accounts':    'Account Management',
        'page.hr':          'HR Management',
        'page.career':      'Career Mapping',
        'page.tools':       'Tools Management',
        'page.carto':       'Cartography',
        'page.settings':    'Settings',
        'page.import':      'Import',
        'page.export':      'Export',
        'page.changelog':   'Changelog',
        'page.chatbot':     'AI Assistant',
        'page.performance': 'Performance',

        # ── Activités ────────────────────────────────────────────────────────
        'activity.label':       'Activity',
        'activity.tasks':       'Tasks',
        'activity.tools':       'Tools',
        'activity.competences': 'Competencies',
        'activity.links':       'Connections',
        'activity.performance': 'Performance',
        'activity.garant':      'Owner',

        # ── Rôles ────────────────────────────────────────────────────────────
        'role.label':      'Role',
        'role.members':    'Members',
        'role.onboarding': 'Onboarding plan',

        # ── Compétences ──────────────────────────────────────────────────────
        'competence.savoir_faire': 'Know-how',
        'competence.savoir':       'Knowledge',
        'competence.softskill':    'Soft skill',
        'competence.aptitude':     'Aptitude',

        # ── Temps ────────────────────────────────────────────────────────────
        'time.project':  'Project analysis',
        'time.analysis': 'Activity analysis',
        'time.role':     'Role analysis',
        'time.weakness': 'Weakness analysis',

        # ── Import ───────────────────────────────────────────────────────────
        'import.excel':   'Excel import',
        'import.ai':      'AI import',
        'import.analyze': 'Analyse',
        'import.inject':  'Inject to database',

        # ── Évaluations ──────────────────────────────────────────────────────
        'eval.garant':      'Owner',
        'eval.manager':     'Manager',
        'eval.rh':          'HR',
        'eval.level':       'Level',
        'eval.note':        'Note',
        'eval.eval_number': 'Evaluation #',

        # ── Cartographie ─────────────────────────────────────────────────────
        'carto.editor':      'Editor',
        'carto.save':        'Save cartography',
        'carto.bands':       'Bands',
        'carto.shapes':      'Shapes',
        'carto.connections': 'Connections',
    },
}

_FALLBACK = 'fr'


def t(key: str, lang: str | None = None) -> str:
    """
    Retourne la traduction pour `key` dans la langue `lang`.
    Si `lang` est None, lit session['lang'] (défaut : 'fr').
    Si la clé est absente dans la langue demandée, tente le fallback 'fr',
    puis retourne la clé brute.
    """
    if lang is None:
        try:
            lang = session.get('lang', _FALLBACK)
        except RuntimeError:
            # Hors contexte applicatif (tests unitaires, CLI…)
            lang = _FALLBACK

    lang = lang if lang in TRANSLATIONS else _FALLBACK
    result = TRANSLATIONS[lang].get(key)
    if result is None and lang != _FALLBACK:
        result = TRANSLATIONS[_FALLBACK].get(key)
    return result if result is not None else key
