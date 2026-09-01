# -*- coding: utf-8 -*-
"""Inventaire de l'écosystème DevOPTIQ / OptiqFluent.

C'est CE fichier qu'on retouche : instances, infrastructure, documents,
commandes, branches. Les gabarits ne portent aucune donnée en dur.

⚠️ Aucun secret ici. On NOMME les bases et les secrets GitHub, jamais leurs
valeurs. Les textes sont volontairement courts : le hub sert à retrouver,
pas à lire.
"""

PROJET_NUM = "562171553379"
REGION = "europe-west1"

CONSOLE_RUN = ("https://console.cloud.google.com/run/detail/"
               f"{REGION}/{{service}}/metrics?project={PROJET_NUM}")
CONSOLE_RUN_LISTE = f"https://console.cloud.google.com/run?project={PROJET_NUM}"
CONSOLE_NEON = "https://console.neon.tech/app/projects"
DEPOT = "https://github.com/Maelouuu/DevOPTIQ"


def _url(service):
    return f"https://{service}-{PROJET_NUM}.{REGION}.run.app"


# ── Pages du hub ──────────────────────────────────────────────────────────
PAGES = [
    {"cle": "accueil",  "titre": "Accueil",        "route": "/",              "accent": "accueil",  "icone": "grille"},
    {"cle": "instances", "titre": "Instances",     "route": "/instances",     "accent": "instances", "icone": "fenetre"},
    {"cle": "infrastructure", "titre": "Infrastructure", "route": "/infrastructure", "accent": "infra",    "icone": "serveur"},
    {"cle": "documentation", "titre": "Documentation",  "route": "/documentation", "accent": "docs",     "icone": "livre"},
    {"cle": "tests",    "titre": "Tests",          "route": "/tests",         "accent": "tests",    "icone": "ok"},
    {"cle": "outils",   "titre": "Outils",         "route": "/outils",        "accent": "outils",   "icone": "terminal"},
    {"cle": "ci",       "titre": "Dépôt & CI",     "route": "/ci",            "accent": "ci",       "icone": "git"},
]


# ── Instances : les applications qu'on ouvre pour travailler ──────────────
INSTANCES = [
    {
        "cle": "prod", "nom": "DevOPTIQ", "variante": "Production",
        "service": "devoptiq", "url": _url("devoptiq"), "sonde": "/login",
        "accent": "prod",
        "pour": "Clients en production",
        "branche": "main",
        "base": "Base de production",
        "resume": "Version stable. N'y merger que du validé.",
    },
    {
        "cle": "staging", "nom": "DevOPTIQ", "variante": "Staging",
        "service": "devoptiq-staging", "url": _url("devoptiq-staging"), "sonde": "/login",
        "accent": "staging",
        "pour": "AFDEC — interne",
        "branche": "staging",
        "base": "Base staging",
        "resume": "L'instance de travail : tout se valide ici.",
        "liens": [
            {"libelle": "Panel de tests", "href": "/testpanel/"},
            {"libelle": "Carnet de bord", "href": "/testpanel/journal"},
            {"libelle": "Cartographie", "href": "/cartography/editor"},
        ],
    },
    {
        "cle": "pilote", "nom": "OptiqFluent", "variante": "Pilote ARaymond",
        "service": "optiqfluent-staging", "url": _url("optiqfluent-staging"), "sonde": "/login",
        "accent": "pilote",
        "pour": "7 comptes ARaymond (Inde)",
        "branche": "optiqfluent-staging",
        "base": "optiqfluent_pilot",
        "resume": "Version rebrandée, licence désactivée, prompts chiffrés.",
        "liens": [{"libelle": "Cartographie", "href": "/cartography/editor"}],
    },
    {
        "cle": "pulse", "nom": "OptiqPulse", "variante": "Suivi d'audience",
        "service": "optiq-pulse", "url": _url("optiq-pulse"), "sonde": "/login",
        "accent": "pulse",
        "pour": "AFDEC uniquement",
        "branche": "staging · pulse/",
        "base": "Lecture seule sur les autres bases",
        "resume": "Qui utilise quoi, quand, combien de temps.",
    },
]


# ── Infrastructure ────────────────────────────────────────────────────────
SERVICES_RUN = [
    {"service": "devoptiq", "sert": "DevOPTIQ Production", "accent": "prod",
     "workflow": "deploy-production.yml", "declencheur": "push sur main"},
    {"service": "devoptiq-staging", "sert": "DevOPTIQ Staging", "accent": "staging",
     "workflow": "deploy-staging.yml", "declencheur": "push sur staging"},
    {"service": "optiqfluent-staging", "sert": "OptiqFluent Pilote", "accent": "pilote",
     "workflow": "deploy-beta.yml", "declencheur": "push sur optiqfluent-staging"},
    {"service": "optiq-pulse", "sert": "OptiqPulse", "accent": "pulse",
     "workflow": "deploy-pulse.yml", "declencheur": "push touchant pulse/**"},
    {"service": "optiq-hub", "sert": "Ce hub", "accent": "hub",
     "workflow": "deploy-hub.yml", "declencheur": "push touchant hub/** ou docs/**"},
]

# Bases Neon. `endpoint` n'est renseigné que là où il est vérifié ; ailleurs la
# valeur vit dans un secret GitHub et n'a pas à être recopiée ici.
BASES_NEON = [
    {"base": "optiqfluent_pilot", "accent": "pilote",
     "sert": "OptiqFluent — Pilote ARaymond",
     "endpoint": "ep-solitary-bonus-abrhwgrs · eu-west-2",
     "secret": "PILOT_DATABASE_URL",
     "note": "Dédiée, isolée de staging. 9 comptes, 11 entités FluidClip."},
    {"base": "Base staging", "accent": "staging",
     "sert": "DevOPTIQ — Staging",
     "endpoint": None,
     "secret": "STAGING_DATABASE_URL",
     "note": "Données de travail AFDEC."},
    {"base": "Base de production", "accent": "prod",
     "sert": "DevOPTIQ — Production",
     "endpoint": None,
     "secret": "PROD_DATABASE_URL",
     "note": "Données clients. Ne jamais y jouer un plan sans simulation."},
]


# ── Documentation ─────────────────────────────────────────────────────────
DOCUMENTS = [
    {"titre": "Documentation technique", "href": "/doc", "accent": "docs", "icone": "livre",
     "resume": "Architecture, modèles, blueprints, APIs, déploiement."},
    {"titre": "Guide utilisateur", "href": "/guide", "accent": "guide", "icone": "boussole",
     "resume": "Prise en main page par page. Bilingue, 36 captures, 16 vidéos."},
    {"titre": "Refonte Compétences V1.1", "href": "/doc/refonte", "accent": "refonte", "icone": "plan",
     "resume": "La chaîne Activité → Résultat → Compétence, et l'état des 7 lots."},
]


# ── Outils locaux ─────────────────────────────────────────────────────────
RACINE = "~/AFDEC/DEV/DevOPTIQ"
PY = ".venv/bin/python"

OUTILS = [
    {"categorie": "Tests", "accent": "tests", "entrees": [
        {"titre": "Suite complète", "quoi": "Les ~1860 tests.",
         "cmd": f"cd {RACINE} && {PY} -m pytest tests/ -q"},
        {"titre": "Un seul fichier", "quoi": "Cible un domaine.",
         "cmd": f"cd {RACINE} && {PY} -m pytest tests/test_62_task_tool_files.py -q"},
        {"titre": "Banc cartographie", "quoi": "Mesure croisements et chevauchements.",
         "cmd": f"cd {RACINE} && python3 -m http.server 8099 & node tests/carto/drive.mjs"},
        {"titre": "Carto en local", "quoi": "Instance jetable, port 8123.",
         "cmd": f"cd {RACINE} && {PY} tools/devrun_carto_check.py"},
    ]},
    {"categorie": "Provisionnement", "accent": "provisioning", "entrees": [
        {"titre": "Simuler un plan", "quoi": "N'écrit rien. Toujours en premier.",
         "cmd": (f'cd {RACINE} && DATABASE_URL="…" {PY} tools/provisioning/provision.py '
                 "--plan tools/provisioning/plans/pilote_fluidclip_tasks.json --dry-run")},
        {"titre": "Appliquer", "quoi": "Idempotent : rejouer ne duplique rien.",
         "cmd": (f'cd {RACINE} && DATABASE_URL="…" {PY} tools/provisioning/provision.py '
                 "--plan tools/provisioning/plans/pilote_fluidclip_tasks.json")},
        {"titre": "Un seul compte", "quoi": "Ne rouvre pas les autres entités.",
         "cmd": (f'cd {RACINE} && DATABASE_URL="…" {PY} tools/provisioning/provision.py '
                 "--plan tools/provisioning/plans/pilote_fluidclip_tasks.json "
                 "--only priya.bhivare@araymond.com")},
        {"titre": "Visio → carto JSON", "quoi": "Passe un .vsdx dans l'importeur.",
         "cmd": (f"cd {RACINE} && python3 -m http.server 8099 & {PY} "
                 "tools/guide/extract_carto.py carte.vsdx")},
    ]},
    {"categorie": "Guide", "accent": "guide", "entrees": [
        {"titre": "Base de démo", "quoi": "Recrée les données du guide.",
         "cmd": f"cd {RACINE} && GUIDE_LANG=fr {PY} tools/guide/seed_demo.py"},
        {"titre": "Captures", "quoi": "Refait les 36 captures.",
         "cmd": f"cd {RACINE} && GUIDE_LANG=fr {PY} tools/guide/capture_screens.py"},
        {"titre": "Vidéos", "quoi": "Refait les 16 vidéos.",
         "cmd": f"cd {RACINE} && GUIDE_LANG=fr {PY} tools/guide/capture_videos.py"},
        {"titre": "Guide autonome", "quoi": "Un seul fichier, ~32 Mo.",
         "cmd": f"cd {RACINE} && {PY} tools/guide/build_standalone.py"},
    ]},
    {"categorie": "Distribution", "accent": "distrib", "entrees": [
        {"titre": "Chiffrer les prompts", "quoi": "Produit prompts.enc.",
         "cmd": f"cd {RACINE} && PROMPTS_KEY=… {PY} tools/prompts/encrypt_prompts.py"},
        {"titre": "Générer une licence", "quoi": "JSON signé Ed25519.",
         "cmd": f'cd {RACINE} && {PY} tools/licensing/make_license.py --licensee "ARaymond" --days 90'},
        {"titre": "Répéter l'installation", "quoi": "Rejoue INSTALL.md, 9 vérifications.",
         "cmd": f"cd {RACINE} && bash tools/test_install.sh"},
        {"titre": "Comparer les IA", "quoi": "Claude vs OpenAI sur les vrais prompts.",
         "cmd": f"cd {RACINE} && {PY} tools/ai_eval/run_compare.py"},
    ]},
]


# ── Dépôt ─────────────────────────────────────────────────────────────────
BRANCHES = [
    {"nom": "staging", "accent": "staging", "deploie": "devoptiq-staging",
     "role": "Branche de travail. Tout passe par elle."},
    {"nom": "main", "accent": "prod", "deploie": "devoptiq",
     "role": "Production stable."},
    {"nom": "optiqfluent-staging", "accent": "pilote", "deploie": "optiqfluent-staging",
     "role": "Pilote client : rebranding, licence, prompts chiffrés."},
]

WORKFLOWS = [
    {"fichier": "deploy-staging.yml", "titre": "Deploy → Staging", "cible": "devoptiq-staging"},
    {"fichier": "deploy-production.yml", "titre": "Deploy → Production", "cible": "devoptiq"},
    {"fichier": "deploy-beta.yml", "titre": "Deploy → Pilote", "cible": "optiqfluent-staging"},
    {"fichier": "deploy-pulse.yml", "titre": "Deploy → OptiqPulse", "cible": "optiq-pulse"},
    {"fichier": "deploy-hub.yml", "titre": "Deploy → Hub", "cible": "optiq-hub"},
    {"fichier": "client-image.yml", "titre": "Image client", "cible": "ghcr.io/maelouuu/optiqfluent"},
]

SECRETS = [
    ("STAGING_DATABASE_URL", "Base staging"),
    ("PROD_DATABASE_URL", "Base de production"),
    ("PILOT_DATABASE_URL", "Base du pilote"),
    ("PROMPTS_KEY", "Déchiffrement des prompts IA"),
    ("PULSE_PASSWORD", "Accès OptiqPulse"),
    ("HUB_PASSWORD", "Accès à ce hub"),
    ("GCP_WIF_PROVIDER · GCP_SA_EMAIL", "Déploiements Cloud Run"),
]
