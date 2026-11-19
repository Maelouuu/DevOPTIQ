# -*- coding: utf-8 -*-
"""Modèles de l'atelier — des pièces prêtes à poser sur la toile.

Deux modèles aujourd'hui :

1. **Les pages de l'application** — une maquette par page de DevOPTIQ, avec
   ses sections et ce qu'elles portent réellement. C'est la carte sur laquelle
   on vient accrocher les fonctionnalités à venir.
2. **Les chantiers** — la liste de ce qui est à faire, chaque ligne rattachée
   à la page et à la section où elle se joue.

⚠️ **Ce fichier décrit l'app, il ne la lit pas.** Le hub est un service séparé :
il n'a ni les gabarits, ni les blueprints, ni la base de l'application. Relevé
le 19/11/2026 sur `staging` — quand une page bouge, c'est ICI qu'on le reporte.
Un modèle périmé se repère tout de suite à l'écran, et se corrige à la main sur
la toile : les maquettes sont faites pour être triturées, pas pour faire foi.

⚠️ Les identifiants (`id`) sont LOCAUX au modèle. L'atelier les remplace par
des identifiants neufs à l'insertion — sinon, poser deux fois le même modèle
donnerait deux pièces portant le même id, et un badge pointerait sur les deux.

⚠️ Les chantiers ne désignent pas les pages par id mais par NOM
(`page_ref`) : ils se rattachent aux maquettes DÉJÀ posées sur la toile, et
restent justes qu'on insère les deux modèles ensemble ou à dix minutes
d'écart.
"""

# ── Les pages de l'application ────────────────────────────────────────────
# genre : entete · liste · table · form · graphe · panneau · pied

PAGES = [
    {
        "titre": "Connexion", "chemin": "/login", "teinte": "craie",
        "sections": [
            ("En-tête", "entete",
             "Logo OPTIQ et nom de l'instance. Le gabarit est commun aux trois "
             "instances ; seul le rebranding du pilote change."),
            ("Formulaire", "form",
             "Identifiant, mot de passe, choix de la langue. Sessions Flask + "
             "bcrypt (connexion_routes.py)."),
            ("Mot de passe oublié", "form",
             "Demande de réinitialisation. Écrit dans `password_resets` — la "
             "table que la page Courrier du hub lit en seule lecture. Déployée "
             "sur staging et le pilote, absente de la production."),
            ("Licence", "pied",
             "Blocage si la licence est expirée (license_blocked.html). "
             "Désactivée sur le pilote ARaymond."),
        ],
    },
    {
        "titre": "Cartographie", "chemin": "/activities/map", "teinte": "ciel",
        "sections": [
            ("Barre d'outils", "entete",
             "Ouvrir l'éditeur · Gestion des entités · Import IA · Connexions · "
             "Accès · Export."),
            ("Sélecteur d'entité", "panneau",
             "Entité active, renommer, supprimer, partager. Sans entité, la "
             "page affiche l'écran « aucune entité »."),
            ("Vue de la carte", "graphe",
             "Le SVG OptiqCarto en lecture seule : bandes (rôles), formes "
             "(activités), liens. Cliquer une activité ouvre sa fiche."),
            ("Panneau Activités", "liste",
             "Les activités de la carte courante, avec recherche. C'est le "
             "chemin le plus court vers une fiche."),
            ("Gestion des entités", "table",
             "Créer, renommer, dupliquer, supprimer une entité. "
             "`clone_entity` duplique aussi la carto et les activités."),
            ("Import IA", "form",
             "La fenêtre « Importer des données » (import_hub.py) : un fichier "
             "client, appariement par l'IA, injection des tâches."),
            ("Export", "panneau",
             "Export de la carte et des données (export_bp)."),
        ],
    },
    {
        "titre": "Éditeur OptiqCarto", "chemin": "/cartography/editor",
        "teinte": "ciel",
        "sections": [
            ("Barre d'outils", "entete",
             "Formes, bandes, connexions, annuler/refaire. Outil SVG maison "
             "(static/optiqcarto/editor.js), aucun framework."),
            ("Canevas", "graphe",
             "Pose et déplacement des activités. ⚠️ Les deux dépôts "
             "(DevOPTIQ et OptiqCarto) doivent rester synchronisés."),
            ("Bandes (rôles)", "liste",
             "Création et renommage des bandes. Une bande = un `Role` ; "
             "l'appartenance d'une activité à une bande peuple `activity_roles`."),
            ("Import VSDX", "form",
             "Parseur de fichiers Visio (vsdx_importer.js), avec décisions "
             "d'import (carto_decision_popup)."),
            ("Enregistrement", "panneau",
             "`/cartography/api/save` → `_sync_carto_to_db()` extrait les "
             "données vers Activities, Role et Link. C'est le point de "
             "bascule entre le dessin et la base."),
            ("Accès et partage", "panneau",
             "Qui peut ouvrir la carto (carto_acces_modal, carto_sharing)."),
        ],
    },
    {
        "titre": "Activités", "chemin": "/activities/view", "teinte": "lavande",
        "sections": [
            ("Recherche", "entete",
             "Champ de recherche, compteur de résultats, tout ouvrir / tout "
             "fermer."),
            ("Activité sélectionnée", "panneau",
             "L'encart qui apparaît quand on arrive depuis la cartographie ou "
             "depuis les rôles — l'activité visée est sortie de la liste."),
            ("Liste des activités", "liste",
             "Cartes dépliables, une par activité, chargées par paquets "
             "(« charger plus »)."),
            ("Fiche dépliée", "panneau",
             "Le contenu d'une carte ouverte — voir la maquette « Fiche "
             "activité »."),
        ],
    },
    {
        "titre": "Fiche activité", "chemin": "/activities/view › carte dépliée",
        "teinte": "lavande",
        "sections": [
            ("Informations générales", "entete",
             "Nom, entité, garant, description. C'est ici que se jugerait le "
             "palier « garant + tâche + outil »."),
            ("Connexions", "graphe",
             "Liens entrants et sortants avec les autres activités (modèle "
             "`Link`), tels que l'éditeur les a posés."),
            ("Contraintes", "liste",
             "Les contraintes de l'activité (constraints_bp)."),
            ("Tâches associées", "table",
             "Les tâches et le rôle qui intervient sur chacune. Alimente le "
             "bloc « non Garant » de la page Rôles."),
            ("Compétences requises", "liste",
             "Les compétences liées à l'activité (competences_bp)."),
            ("Savoirs & Savoir-faire", "liste",
             "Connaissances théoriques et savoir-faire pratiques, avec "
             "propositions par l'IA."),
            ("Aptitudes", "liste",
             "Les aptitudes requises, avec propositions par l'IA."),
            ("Compétences comportementales", "liste",
             "Les soft skills, avec propositions et traduction par l'IA."),
            ("Gestion du temps", "graphe",
             "Le temps de l'activité (`TimeAnalysis`), repris par la page "
             "Temps."),
        ],
    },
    {
        "titre": "Rôles", "chemin": "/roles_view", "teinte": "olive",
        "sections": [
            ("Barre", "entete",
             "Recherche d'un rôle, export."),
            ("Carte d'un rôle", "entete",
             "En-tête dépliable : nom du rôle, renommer, supprimer."),
            ("Mission générale", "form",
             "Le texte libre de la mission du rôle."),
            ("Activités où ce rôle est Garant", "liste",
             "Les activités dont il porte la responsabilité."),
            ("Activités/Tâches où il intervient", "table",
             "Là où il agit sans être garant : activité, tâche, statut."),
            ("Compétences associées", "liste",
             "Les compétences des activités dont il est garant."),
            ("Savoirs, Savoir-faire, Aptitudes et HSC", "liste",
             "Les quatre familles, avec le niveau et la justification des HSC."),
            ("Titulaire du rôle", "panneau",
             "Qui tient le rôle aujourd'hui."),
        ],
    },
    {
        "titre": "Compétences", "chemin": "/competences/view",
        "teinte": "garance",
        "sections": [
            ("Galerie", "table",
             "Tous les collaborateurs en vignettes — le point d'entrée."),
            ("Colonne latérale", "liste",
             "Le développeur de compétences et la liste de ses collaborateurs."),
            ("Carte bleue du collaborateur", "panneau",
             "La synthèse d'une personne : son profil, ses rôles, ses séances. "
             "C'est LA carte principale, celle qu'on ouvre en premier. "
             "(L'accent bleu #2563eb est celui de toute la page.)"),
            ("Volet de détail", "panneau",
             "Le tiroir latéral qui s'ouvre sur une compétence : son titre, "
             "le rôle concerné, le corps et le pied d'actions."),
            ("Évaluation", "form",
             "L'écran d'évaluation d'une compétence."),
            ("Séance", "form",
             "L'écran d'une séance de développement."),
            ("Calendrier", "table",
             "Les séances dans le temps."),
            ("Plan de formation", "liste",
             "Le plan de formation du collaborateur (competences_plan)."),
            ("Les courbes", "graphe",
             "La progression tracée dans le temps."),
        ],
    },
    {
        "titre": "Gestion du temps", "chemin": "/temps", "teinte": "ocre",
        "sections": [
            ("Où part le temps de l'entité ?", "entete",
             "L'accueil : charge totale, et sa répartition par mois, par "
             "semaine, par jour."),
            ("Pile des analyses", "graphe",
             "Les analyses empilées : ce qui pèse, et dans quel ordre."),
            ("Faiblesses", "graphe",
             "Le surcoût mesuré (+ N h) et le gain possible."),
            ("Couverture", "panneau",
             "Combien d'activités sont couvertes par une analyse, sur le total."),
            ("Les analyses", "table",
             "Les analyses enregistrées, rouvrables et modifiables."),
            ("De quoi estimer la charge ?", "panneau",
             "Le choix du type d'analyse : Projet · Activité · Rôle · "
             "Faiblesse."),
            ("Analyse d'un projet", "form",
             "Questionnaire d'estimation pour un projet."),
            ("Analyse d'une activité", "form",
             "Questionnaire d'estimation pour une activité. Les durées s'y "
             "saisissent en minutes, heures ou jours."),
            ("Analyse d'un rôle", "form",
             "Questionnaire d'estimation pour un rôle. ⚠️ Les durées n'y "
             "acceptent que des MINUTES, et le formulaire se rouvre prérempli "
             "de l'analyse précédente — deux des chantiers ci-contre."),
            ("Analyse d'une faiblesse", "form",
             "En deux temps : la référence, puis le cas dégradé, d'où se "
             "déduisent le surcoût et le gain."),
        ],
    },
    {
        "titre": "Gestion RH", "chemin": "/gestion_rh", "teinte": "sienne",
        "sections": [
            ("Barre du haut", "entete",
             "L'entité courante et ses chiffres."),
            ("Tuiles", "panneau",
             "Trois chiffres qui mènent chacun à son bloc."),
            ("Les personnes", "table",
             "Qui tient quoi : chaque personne et ses rôles. C'est là que "
             "manquent le poids d'un rôle et l'alerte des 80 %."),
            ("Les rôles", "table",
             "Qui les tient, et lesquels ouvrent la cartographie. C'est là que "
             "manque le choix d'un rôle et d'une période mensuelle."),
            ("Les compétences de chacun", "table",
             "La vue croisée personnes × compétences."),
            ("Fiche d'une personne", "form",
             "La fenêtre d'édition d'une ligne."),
        ],
    },
    {
        "titre": "Comptes", "chemin": "/comptes", "teinte": "sienne",
        "sections": [
            ("Les comptes", "table",
             "La liste des comptes de l'instance."),
            ("Droits par statut", "table",
             "Ce que chaque statut a le droit de faire."),
            ("Fiche d'un compte", "form",
             "La MÊME fiche pour créer et pour modifier : identité, contact, "
             "statut, rôles."),
            ("Supprimer un compte", "panneau",
             "Confirmation de suppression."),
        ],
    },
    {
        "titre": "Gestion des outils", "chemin": "/gestion_outils",
        "teinte": "ocre",
        "sections": [
            ("Ajouter un outil", "form",
             "Le volet de création, replié par défaut."),
            ("Liste des outils", "table",
             "Tous les outils, avec le nombre d'usages."),
            ("Édition d'un outil", "form",
             "La fenêtre de modification."),
            ("Usages", "liste",
             "Où l'outil est utilisé — en lecture seule, depuis le badge."),
            ("Remplacer / supprimer", "panneau",
             "Remplacement d'un outil par un autre avant suppression."),
        ],
    },
    {
        "titre": "Paramètres", "chemin": "/parametres", "teinte": "craie",
        "sections": [
            ("Interface", "form",
             "Langue de l'application (FR / EN)."),
            ("Référentiel DCP", "form",
             "Le fichier de référence DCP."),
            ("Administration", "form",
             "Visible aux seuls administrateurs : clé IA, URL de la base "
             "(mot de passe masqué), console serveur en direct."),
        ],
    },
    {
        "titre": "Projection métier", "chemin": "/projection_metier",
        "teinte": "garance",
        "sections": [
            ("Collaborateur", "form",
             "Le choix de la personne à projeter."),
            ("Aperçu", "panneau",
             "Combien de correspondances complètes, combien de partielles."),
            ("Résultats ROME", "table",
             "Les métiers du référentiel ROME qui correspondent, filtrables."),
            ("Légende", "pied",
             "Ce que veulent dire les couleurs."),
        ],
    },
    {
        "titre": "Panel de tests", "chemin": "/testpanel/", "teinte": "lavande",
        "sections": [
            ("Carrousel des pages", "liste",
             "Une page du panel par domaine testé."),
            ("Lanceur", "panneau",
             "Lance pytest SUR l'instance, sur une base SQLite jetable. "
             "⚠️ Aucune authentification sur /testpanel/** ; un plafond de "
             "3 exécutions simultanées borne la casse."),
            ("Historique", "table",
             "Les exécutions passées et leur résultat."),
            ("Carnet de bord", "liste",
             "Le journal des campagnes de tests."),
        ],
    },
]


# ── Les chantiers ─────────────────────────────────────────────────────────
# ⚠️ Relevé des notes de Maël le 19/11/2026, à sa formulation près. Ce sont
# SES notes : on les range, on ne les réécrit pas.

CHANTIERS = [
    ("Carte bleue « de près » d'un user (page Compétences) : "
     "négociation de l'offre.",
     "Compétences", "Carte bleue du collaborateur"),

    ("Intensifier le découlement de l'activité vis-à-vis de ses résultats, "
     "dans la carte bleue principale d'un user.",
     "Compétences", "Carte bleue du collaborateur"),

    ("Nouvelle analyse de rôle : repartir À VIDE, et remettre le nom à zéro.",
     "Gestion du temps", "Analyse d'un rôle"),

    ("Analyse de rôle : ajouter les unités heure et jour "
     "(aujourd'hui, seules les minutes).",
     "Gestion du temps", "Analyse d'un rôle"),

    ("RH : pouvoir choisir un rôle et une période (mensuelle).",
     "Gestion RH", "Les rôles"),

    ("RH / Les personnes : afficher à côté de chaque rôle le poids obtenu "
     "par le calcul précédent.",
     "Gestion RH", "Les personnes"),

    ("RH / Les personnes : prévenir quand le poids cumulé des rôles d'une "
     "personne dépasse 80 % du total travaillé de l'entreprise.",
     "Gestion RH", "Les personnes"),

    ("Échanger les boutons « Ouvrir l'éditeur » et « Gestion des entités ».",
     "Cartographie", "Barre d'outils"),

    ("Palier : une activité n'est soumise au coordinateur que si elle a un "
     "garant, une tâche ET un outil.",
     "Fiche activité", "Informations générales"),

    ("La carto n'est soumise au coordinateur que lorsque TOUTES ses activités "
     "remplissent les trois conditions.",
     "Cartographie", "Vue de la carte"),
]


# ── Mise en page ──────────────────────────────────────────────────────────
# Rangement en colonnes de hauteur égale : une grille rigide laisserait des
# trous sous les pages courtes, et la toile serait deux fois plus haute.

LARGEUR = 340
ECART_X = 34
ECART_Y = 28
COLONNES = 4


def _hauteur(nb_sections):
    # En-tête + barre d'adresse + une section, bornée : au-delà la maquette
    # défile, ce qui vaut mieux qu'une pièce de deux mètres de haut.
    return min(760, 150 + 96 * nb_sections)


def _maquettes(depart_x=0, depart_y=0):
    noeuds = []
    bas = [depart_y] * COLONNES
    for i, page in enumerate(PAGES):
        col = bas.index(min(bas))
        h = _hauteur(len(page["sections"]))
        noeuds.append({
            "id": "pg%d" % i,
            "type": "maquette",
            "x": depart_x + col * (LARGEUR + ECART_X),
            "y": bas[col],
            "w": LARGEUR, "h": h,
            "teinte": page["teinte"],
            "titre": page["titre"],
            "chemin": page["chemin"],
            "sections": [
                {"id": "pg%ds%d" % (i, j), "nom": nom, "genre": genre,
                 "quoi": quoi}
                for j, (nom, genre, quoi) in enumerate(page["sections"])
            ],
        })
        bas[col] = bas[col] + h + ECART_Y
    return noeuds


def _chantiers(depart_x=0, depart_y=0):
    """Une liste à cocher, chaque ligne rattachée par NOM à sa page."""
    return [{
        "id": "ch",
        "type": "liste",
        "x": depart_x, "y": depart_y,
        "w": 400, "h": 680,
        "teinte": "garance",
        "titre": "Chantiers à venir",
        "items": [
            {"id": "ch%d" % n, "fait": False, "texte": texte,
             "page_ref": {"page": page, "section": section}}
            for n, (texte, page, section) in enumerate(CHANTIERS)
        ],
    }]


# ── Le catalogue ──────────────────────────────────────────────────────────

CATALOGUE = [
    {
        "cle": "tout",
        "titre": "Le plan de l'app + mes chantiers",
        "quoi": "Les %d pages ET la liste des %d chantiers, déjà rattachés à "
                "leur page et à leur section. C'est l'entrée par défaut."
                % (len(PAGES), len(CHANTIERS)),
    },
    {
        "cle": "pages",
        "titre": "Les pages de l'application",
        "quoi": "Une maquette par page de DevOPTIQ, avec ses sections et ce "
                "qu'elles portent. %d pages." % len(PAGES),
    },
    {
        "cle": "chantiers",
        "titre": "Mes chantiers",
        "quoi": "La liste à cocher de ce qui reste à faire, chaque ligne "
                "rattachée à sa page et à sa section. %d lignes."
                % len(CHANTIERS),
    },
]


def catalogue():
    return CATALOGUE


def modele(cle):
    """Les pièces d'un modèle, en format de toile, identifiants LOCAUX."""
    if cle == "pages":
        return {"cle": cle, "titre": "Les pages de l'application",
                "noeuds": _maquettes(), "liens": []}
    if cle == "chantiers":
        return {"cle": cle, "titre": "Mes chantiers",
                "noeuds": _chantiers(), "liens": []}
    if cle == "tout":
        # La liste à gauche, les pages à sa droite : on lit la liste, et les
        # badges emmènent sur la maquette voisine.
        return {"cle": cle, "titre": "Le plan de l'app + mes chantiers",
                "noeuds": _chantiers() + _maquettes(depart_x=460),
                "liens": []}
    return None
