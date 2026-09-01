# -*- coding: utf-8 -*-
"""Inventaire de l'écosystème DevOPTIQ / OptiqFluent.

Séparé de la présentation : c'est CE fichier qu'on retouche quand une instance
change d'URL, qu'un outil apparaît ou qu'une base est renommée. Le gabarit ne
contient aucune donnée en dur.

⚠️ Aucun secret ici — ni URL de base complète, ni mot de passe. On nomme les
bases et les secrets GitHub, on ne les recopie pas.
"""

PROJET = "562171553379"
REGION = "europe-west1"


def _url(service):
    return f"https://{service}-{PROJET}.{REGION}.run.app"


# ── Instances en ligne ────────────────────────────────────────────────────
# `sonde` : chemin interrogé pour l'état de santé. On vise /login plutôt que
# la racine : elle répond 302 vers /login, et /healthz est intercepté par le
# frontend Google sur *.run.app (404 avant même le conteneur).
INSTANCES = [
    {
        "cle": "prod",
        "nom": "DevOPTIQ — Production",
        "service": "devoptiq",
        "url": _url("devoptiq"),
        "sonde": "/login",
        "accent": "prod",
        "role": "Version stable destinée aux clients finaux.",
        "branche": "main",
        "base": "Neon — base de production",
        "workflow": "deploy-production.yml",
        "public": "Clients en production",
        "notes": "Ne recevoir que des versions validées sur staging.",
    },
    {
        "cle": "staging",
        "nom": "DevOPTIQ — Staging",
        "service": "devoptiq-staging",
        "url": _url("devoptiq-staging"),
        "sonde": "/login",
        "accent": "staging",
        "role": "Instance de travail AFDEC : c'est ici qu'on valide avant production.",
        "branche": "staging",
        "base": "Neon — base staging",
        "workflow": "deploy-staging.yml",
        "public": "AFDEC (interne)",
        "notes": "Panel de tests et carnet de bord actifs.",
        "liens": [
            {"libelle": "Panel de tests", "href": "/testpanel/"},
            {"libelle": "Carnet de bord", "href": "/testpanel/journal"},
            {"libelle": "Cartographie", "href": "/cartography/editor"},
            {"libelle": "Paramètres", "href": "/parametres"},
        ],
    },
    {
        "cle": "pilote",
        "nom": "OptiqFluent — Pilote ARaymond",
        "service": "optiqfluent-staging",
        "url": _url("optiqfluent-staging"),
        "sonde": "/login",
        "accent": "pilote",
        "role": "Version rebrandée OptiqFluent, mise à disposition des testeurs ARaymond (Inde).",
        "branche": "optiqfluent-staging",
        "base": "Neon — optiqfluent_pilot (dédiée, isolée de staging)",
        "workflow": "deploy-beta.yml (sur la branche pilote)",
        "public": "7 comptes ARaymond + AFDEC",
        "notes": "Licence désactivée (REQUIRE_LICENSE=0), prompts chiffrés, panel de tests coupé.",
        "liens": [
            {"libelle": "Cartographie", "href": "/cartography/editor"},
            {"libelle": "Paramètres", "href": "/parametres"},
        ],
    },
    {
        "cle": "pulse",
        "nom": "OptiqPulse — Suivi d'audience",
        "service": "optiq-pulse",
        "url": _url("optiq-pulse"),
        "sonde": "/login",
        "accent": "pulse",
        "role": "Dashboard privé : qui utilise les instances, quand, sur quelles pages, combien de temps.",
        "branche": "staging (dossier pulse/)",
        "base": "Lecture seule sur les bases des instances suivies",
        "workflow": "deploy-pulse.yml",
        "public": "AFDEC uniquement — compte Mael_Girardin",
        "notes": "Ne jamais exposer aux utilisateurs : données nominatives.",
    },
]


# ── Documentation (fichiers servis par le hub) ────────────────────────────
DOCUMENTS = [
    {
        "cle": "doc",
        "titre": "Documentation technique",
        "resume": "Architecture, modèles de données, blueprints, APIs, déploiement. "
                  "La référence pour comprendre le code.",
        "href": "/doc",
        "source": "docs/doc_technique.html",
        "accent": "doc",
        "icone": "livre",
    },
    {
        "cle": "guide",
        "titre": "Guide utilisateur",
        "resume": "Prise en main page par page, bilingue FR/EN, thème clair/sombre, "
                  "36 captures et 16 vidéos de manipulation.",
        "href": "/guide",
        "source": "docs/guide.html",
        "accent": "guide",
        "icone": "boussole",
    },
    {
        "cle": "refonte",
        "titre": "Refonte Compétences V1.1",
        "resume": "Le plan de la chaîne Activité → Résultat → Compétence → Diagnostic → Plan, "
                  "et l'état d'avancement des 7 lots.",
        "href": "/doc/refonte",
        "source": "docs/refonte_competences_v1_1.md",
        "accent": "refonte",
        "icone": "plan",
    },
]


# ── Outils qui s'exécutent en local ───────────────────────────────────────
# Une page web ne peut pas lancer un script sur le poste de Maël : chaque
# entrée porte donc la commande EXACTE, copiable en un clic, avec ce qu'elle
# fait et quand s'en servir.
RACINE = "~/AFDEC/DEV/DevOPTIQ"
PY = ".venv/bin/python"

OUTILS = [
    {
        "categorie": "Tests",
        "accent": "tests",
        "entrees": [
            {
                "titre": "Suite de tests complète",
                "quoi": "Les ~1860 tests de l'application (pytest).",
                "quand": "Avant chaque push, et après toute correction.",
                "cmd": f"cd {RACINE} && {PY} -m pytest tests/ -q",
            },
            {
                "titre": "Un fichier de tests",
                "quoi": "Cible un seul domaine — beaucoup plus rapide.",
                "quand": "Pendant le développement d'une correction.",
                "cmd": f"cd {RACINE} && {PY} -m pytest tests/test_62_task_tool_files.py -q",
            },
            {
                "titre": "Banc cartographie",
                "quoi": "Rejoue l'import VSDX dans un navigateur sans interface et "
                        "mesure croisements, chevauchements, angles.",
                "quand": "Après toute modification de l'importeur ou du rendu des flèches.",
                "cmd": f"cd {RACINE} && python3 -m http.server 8099 & node tests/carto/drive.mjs",
            },
            {
                "titre": "Mise au point carto en local",
                "quoi": "Instance jetable (SQLite) avec deux comptes source/cible sur le port 8123.",
                "quand": "Pour rejouer un import de paquet .optiqcarto.",
                "cmd": f"cd {RACINE} && {PY} tools/devrun_carto_check.py",
            },
        ],
    },
    {
        "categorie": "Provisionnement",
        "accent": "provisioning",
        "entrees": [
            {
                "titre": "Simuler un plan",
                "quoi": "Affiche tout ce que le plan ferait, sans rien écrire.",
                "quand": "TOUJOURS avant d'appliquer.",
                "cmd": (f'cd {RACINE} && DATABASE_URL="postgresql://…" {PY} '
                        "tools/provisioning/provision.py "
                        "--plan tools/provisioning/plans/pilote_fluidclip_tasks.json --dry-run"),
            },
            {
                "titre": "Appliquer un plan",
                "quoi": "Crée comptes et entités, injecte cartos et données Excel. Idempotent.",
                "quand": "Après une simulation conforme.",
                "cmd": (f'cd {RACINE} && DATABASE_URL="postgresql://…" {PY} '
                        "tools/provisioning/provision.py "
                        "--plan tools/provisioning/plans/pilote_fluidclip_tasks.json"),
            },
            {
                "titre": "Rejouer pour un seul compte",
                "quoi": "Restreint le plan à un propriétaire — les autres entités ne sont pas rouvertes.",
                "quand": "Pour corriger ou compléter un compte isolé.",
                "cmd": (f'cd {RACINE} && DATABASE_URL="postgresql://…" {PY} '
                        "tools/provisioning/provision.py "
                        "--plan tools/provisioning/plans/pilote_fluidclip_tasks.json "
                        "--only priya.bhivare@araymond.com"),
            },
            {
                "titre": "Convertir un .vsdx en carto JSON",
                "quoi": "Passe le fichier Visio dans l'importeur de l'app et produit le JSON du plan.",
                "quand": "Quand un client fournit une nouvelle carte Visio.",
                "cmd": (f"cd {RACINE} && python3 -m http.server 8099 & {PY} "
                        "tools/guide/extract_carto.py chemin/vers/carte.vsdx"),
            },
        ],
    },
    {
        "categorie": "Guide & captures",
        "accent": "guide",
        "entrees": [
            {
                "titre": "Base de démo",
                "quoi": "Recrée une base réaliste depuis example.vsdx, dans la langue voulue.",
                "quand": "Avant de refaire les captures du guide.",
                "cmd": f"cd {RACINE} && GUIDE_LANG=fr {PY} tools/guide/seed_demo.py",
            },
            {
                "titre": "Captures d'écran",
                "quoi": "Playwright parcourt l'app et refait les 36 captures.",
                "quand": "Après toute évolution visuelle de l'application.",
                "cmd": f"cd {RACINE} && GUIDE_LANG=fr {PY} tools/guide/capture_screens.py",
            },
            {
                "titre": "Vidéos de manipulation",
                "quoi": "Refait les 16 vidéos, curseur visible.",
                "quand": "Quand un parcours utilisateur change.",
                "cmd": f"cd {RACINE} && GUIDE_LANG=fr {PY} tools/guide/capture_videos.py",
            },
            {
                "titre": "Guide autonome",
                "quoi": "Emballe tout en un seul fichier HTML (~32 Mo, images et vidéos en base64).",
                "quand": "Pour envoyer le guide par mail ou sur clé USB.",
                "cmd": f"cd {RACINE} && {PY} tools/guide/build_standalone.py",
            },
        ],
    },
    {
        "categorie": "Distribution client",
        "accent": "distrib",
        "entrees": [
            {
                "titre": "Chiffrer les prompts IA",
                "quoi": "Produit Code/prompts/prompts.enc, seul fichier de prompts embarqué chez le client.",
                "quand": "Avant chaque build d'image client.",
                "cmd": f"cd {RACINE} && PROMPTS_KEY=… {PY} tools/prompts/encrypt_prompts.py",
            },
            {
                "titre": "Générer une licence",
                "quoi": "Licence JSON signée Ed25519, à durée limitée.",
                "quand": "À la livraison d'un client, et à chaque renouvellement.",
                "cmd": (f"cd {RACINE} && {PY} tools/licensing/make_license.py "
                        '--licensee "ARaymond" --days 90'),
            },
            {
                "titre": "Répéter l'installation client",
                "quoi": "Rejoue INSTALL.md sans Docker : licence, arbre bytecode, PostgreSQL vierge, 9 vérifications.",
                "quand": "Avant de livrer une nouvelle version au client.",
                "cmd": f"cd {RACINE} && bash tools/test_install.sh",
            },
            {
                "titre": "Comparer les fournisseurs IA",
                "quoi": "Rapport côte à côte Claude / OpenAI sur les vrais prompts.",
                "quand": "Avant de basculer AI_PROVIDER.",
                "cmd": f"cd {RACINE} && {PY} tools/ai_eval/run_compare.py",
            },
        ],
    },
]


# ── Dépôt et intégration continue ─────────────────────────────────────────
DEPOT = "https://github.com/Maelouuu/DevOPTIQ"

BRANCHES = [
    {"nom": "staging", "role": "Branche de travail AFDEC. Tout passe par elle.",
     "deploie": "devoptiq-staging", "accent": "staging"},
    {"nom": "main", "role": "Production stable. N'y merger que du validé.",
     "deploie": "devoptiq", "accent": "prod"},
    {"nom": "optiqfluent-staging", "role": "Pilote client : rebranding, licence, prompts chiffrés.",
     "deploie": "optiqfluent-staging", "accent": "pilote"},
]

WORKFLOWS = [
    {"fichier": "deploy-staging.yml", "titre": "Deploy → Staging",
     "declencheur": "push sur staging", "cible": "devoptiq-staging"},
    {"fichier": "deploy-production.yml", "titre": "Deploy → Production",
     "declencheur": "push sur main", "cible": "devoptiq"},
    {"fichier": "deploy-beta.yml", "titre": "Deploy → Pilote",
     "declencheur": "push sur optiqfluent-staging", "cible": "optiqfluent-staging"},
    {"fichier": "deploy-pulse.yml", "titre": "Deploy → OptiqPulse",
     "declencheur": "push touchant pulse/**", "cible": "optiq-pulse"},
    {"fichier": "deploy-hub.yml", "titre": "Deploy → Hub",
     "declencheur": "push touchant hub/**", "cible": "optiq-hub"},
    {"fichier": "client-image.yml", "titre": "Image client OptiqFluent",
     "declencheur": "tag client-v*", "cible": "ghcr.io/maelouuu/optiqfluent"},
]

SECRETS = [
    {"nom": "STAGING_DATABASE_URL", "usage": "Base Neon de l'instance staging."},
    {"nom": "PROD_DATABASE_URL", "usage": "Base Neon de production."},
    {"nom": "PILOT_DATABASE_URL", "usage": "Base Neon dédiée du pilote ARaymond."},
    {"nom": "PROMPTS_KEY", "usage": "Clé Fernet de déchiffrement des prompts IA."},
    {"nom": "PULSE_PASSWORD", "usage": "Mot de passe du dashboard OptiqPulse."},
    {"nom": "HUB_PASSWORD", "usage": "Mot de passe de ce hub."},
    {"nom": "GCP_WIF_PROVIDER / GCP_SA_EMAIL", "usage": "Authentification des déploiements Cloud Run."},
]
