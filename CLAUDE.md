# CLAUDE.md — DevOPTIQ

Fichier de contexte lu automatiquement par Claude Code à chaque session.
Toujours le mettre à jour après chaque travail significatif.

---

## ⚠️ INSTRUCTION CRITIQUE — À exécuter en PREMIER à chaque session

**Avant toute autre action**, bascule sur la branche `staging` et récupère les derniers changements :

```bash
git fetch origin staging
git checkout staging
git pull origin staging
```

Toutes les modifications (docs/index.html, CLAUDE.md) doivent être committées et pushées sur `staging`. Ne jamais travailler sur la branche de session par défaut.

**Séquence de fin de session obligatoire :**
```bash
git add docs/index.html CLAUDE.md
git commit -m "Docs: <description de ce qui a été documenté>"
git push -u origin staging
```

Si le push échoue, réessayer jusqu'à 4 fois (attendre 2s, 4s, 8s, 16s entre chaque tentative).

---

## Présentation du projet

**DevOPTIQ** est une application web de gestion des compétences et activités d'une organisation.
Elle permet de cartographier les activités métier, gérer les compétences des collaborateurs,
suivre les performances, et piloter la formation.

Développée par **AFDEC** (Mael Girardin). Application en production sur **Google Cloud Run**.

---

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | Python 3, Flask |
| Base de données | PostgreSQL (prod) / SQLite (local `Code/instance/optiq.db`) |
| ORM | SQLAlchemy via Flask-SQLAlchemy |
| Frontend | HTML Jinja2 + CSS vanilla + JavaScript vanilla (pas de framework) |
| Auth | Sessions Flask + bcrypt |
| IA | API Anthropic Claude (chatbot, import IA, propositions) |
| Cartographie | OptiqCarto — outil SVG maison (éditeur + viewer) |
| Déploiement | Google Cloud Run, image Docker |

---

## Architecture des fichiers

```
DevOPTIQ/
├── Code/
│   ├── app.py              # Point d'entrée Flask, création de l'app, enregistrement blueprints
│   ├── extensions.py       # db = SQLAlchemy(), login_manager, etc.
│   ├── base_sql.py         # Init DB alternative (scripts)
│   ├── models/
│   │   └── models.py       # TOUS les modèles SQLAlchemy
│   └── routes/
│       ├── templates/      # Templates Jinja2 (partials inclus via {% include %})
│       └── *.py            # Blueprints Flask (1 fichier = 1 domaine fonctionnel)
├── static/
│   ├── *.css               # CSS par domaine (optiq.css = global)
│   ├── js/                 # JS par domaine
│   └── optiqcarto/         # Outil cartographie (editor.js, style.css, vsdx_importer.js)
└── docs/
    └── index.html          # Documentation progressive (à compléter par la routine)
```

---

## Modèles de données principaux

| Modèle | Table | Rôle |
|--------|-------|------|
| `Entity` | `entities` | Entité organisationnelle (département, service…) |
| `Activities` | `activities` | Activité métier (liée à une Entity, issue de la carto) |
| `Role` | `roles` | Rôle/bande dans la cartographie (ex: "Niveau 1") |
| `Link` | `links` | Lien entre deux activités (flux, connexion) |
| `Task` | `tasks` | Tâche associée à une activité |
| `Tool` | `tools` | Outil utilisé dans une activité |
| `Competency` | `competencies` | Compétence associée à une activité |
| `Softskill` | `softskills` | Soft skill |
| `Savoir` | `savoirs` | Connaissance théorique |
| `SavoirFaire` | `savoir_faires` | Savoir-faire pratique |
| `Aptitude` | `aptitudes` | Aptitude |
| `User` | `users` | Utilisateur de l'app |
| `UserRole` | `user_roles` | Rôle d'un utilisateur (admin, viewer…) |
| `Performance` | `performances` | Indicateur de performance d'une activité |
| `TimeAnalysis` | `time_analysis` | Analyse des temps par activité |
| `activity_roles` | (table Core) | Association activité ↔ rôle (many-to-many) |

---

## Pages / Blueprints principaux

| Fichier route | URL | Description |
|---------------|-----|-------------|
| `activities_map.py` | `/activities/map` | Carte des activités + gestion entités |
| `cartography_editor.py` | `/cartography/editor` | Éditeur OptiqCarto |
| `activities.py` | `/activities/` | Liste et détail des activités |
| `activities_view.py` | `/activities/<id>` | Vue fiche activité |
| `tasks.py` | `/tasks/` | Gestion des tâches |
| `tools.py` | `/tools/` | Gestion des outils |
| `gestion_rh.py` | `/rh/` | Gestion RH / collaborateurs |
| `competences.py` | `/competences/` | Gestion des compétences |
| `performance.py` | `/performance/` | Tableaux de bord performance |
| `import_full.py` | `/import/` | Import IA global (Claude API) |
| `chatbot.py` | `/chatbot/` | Chatbot IA intégré |
| `connexion_routes.py` | `/login` | Authentification |

---

## OptiqCarto — outil de cartographie

Outil SVG maison intégré dans l'app. **Deux repos liés :**
- `DevOPTIQ/static/optiqcarto/` ← source principale
- `OptiqCarto/static/js/` et `OptiqCarto/static/css/` ← copie synchronisée

**Règle critique : toujours synchroniser les deux repos après chaque modification.**

Fonctionnement :
- `editor.js` : éditeur interactif SVG (formes, bandes, connexions, import VSDX)
- `vsdx_importer.js` : parseur de fichiers Visio (.vsdx)
- `style.css` : styles de l'éditeur
- À chaque sauvegarde (`/cartography/api/save`), `_sync_carto_to_db()` extrait les données vers les modèles `Activities`, `Role`, `Link`

### Import VSDX & flèches (reconstruction classique — mode UNIQUE)
- **L'agencement automatique a été RETIRÉ** (bouton, `_computeAutoLayout`, libavoid + worker, modale avant/après, animation de chargement — ~710 lignes). Raison mesurée au banc `tests/carto/` : **re-router les flèches JETTE le bon tracé humain de Visio et AJOUTE des croisements** (carto normale : 0 → 8 ; re-disposition compacte : 817 vs 350 sur hard.vsdx). Le tracé Visio est déjà bon → on le garde.
- **Import = reconstruction CLASSIQUE (fidèle Visio), par défaut, sans dialogue.** Les tracés exacts (`customPath`) deviennent les `userPts` rendus — SAUF les **détours aberrants** (waypoint hors carto, OU loin hors de la boîte des 2 extrémités, marge 180 px) : ceux-là sont jetés (`userPts=null`) et routés proprement (orthogonal + évitement). Corrige les flèches qui plongeaient dans le vide / dépassaient leur forme (2 angles inutiles). Une flèche visant un **groupe** conteneur se connecte au **bord du cadre du groupe** (comme dans Visio), PAS re-ciblée sur une forme membre (essayé : ça entassait les flèches sur un membre et augmentait les croisements). Mesuré hard.vsdx : croisements 400+ → ~269, 0 flèche hors carto / dans le vide. Puis `_reconstructClassicPolish()` retouche SANS ré-agencer :
  1. **angles droits** — `_orthogonalizeStaircase()` orthogonalise chaque tracé Visio quasi-droit (union-find : segment vertical → X commun, horizontal → Y commun ; valeur ancrée aux ports, sinon médiane). Mesuré hard.vsdx : 209 segments biaisés → 21 (reste = vraies diagonales Visio).
  2. **labels** — `architectLabels()` place les labels près des pointes SANS jamais les poser là où une flèche en croise une autre (222/243 placés, 0 sur une autre flèche).
- **Curseur global des labels** (remplace le bouton « Agencement auto » ; toolbar, `#label-pos-slider`) : `setLabelsAlongArrows(t)` pose TOUS les labels à la même fraction `t` de LEUR flèche — gauche = origine (source), droite = pointe — en direct. `_pointAlongPath()` donne point + angle ; une marge par flèche évite le chevauchement des formes d'extrémité.
- **Pointes** (au rendu, toujours actif) : `polylineToPath(pts,R,tipPad=18)` (approche droite ≥18 px avant la tête) + `_alignPortApproach()` (dernier segment aligné sur l'axe du port → la tête ne pivote pas).
- **Losanges décoratifs** (non connectés, posés « sur » une flèche dans Visio sans `<Connect>`) : `spliceDecisions` DÉSACTIVÉ (les insérer dans le flux complexifiait les flèches pour rien). `_seatDecorativeDiamonds()` les repose sur LEUR flèche APRÈS le polish : quand on redresse un angle ou qu'on rejette un tracé en détour, la flèche bouge — le losange, associé au connecteur dont le `customPath` Visio d'origine passe le plus près (seuil 60 px), est reposé sur le tracé FINAL de ce connecteur, à la même fraction. Mesuré hard.vsdx : 17/19 losanges à ≤5 px de leur flèche ; les 2 restants sont VRAIMENT flottants dans Visio (>90 px de tout connecteur) → laissés à leur position Visio. Banc : métrique `deco.offArrow`.
- ⚠️ **Réalité hard.vsdx** : 165 formes / 243 flèches / 43 flèches « retour » (graphe cyclique) → **~400 croisements MÊME dans le Visio d'origine fait à la main**. Densité inhérente, aucun algo (ni Graphviz, ni l'humain) ne fait mieux. Sur une carto de taille normale : **0 croisement**. On juge la réussite sur les cartos normales, PAS sur hard.vsdx (cas extrême / stress-test).

---

## Conventions de code

- **Pas de framework JS** : tout en vanilla JS, `$()` est un alias `document.querySelector`
- **CSS par domaine** : chaque page a son CSS dédié, `optiq.css` = styles globaux
- **Templates Jinja2** : les pages incluent des partials (`{% include "partial.html" %}`)
- **Blueprints Flask** : chaque domaine est un blueprint enregistré dans `app.py`
- **Couleurs thème** : rose `#ec4899` / `#be185d` (principal), vert `#22c55e` (accent)
- **Pas de commentaires évidents** dans le code : seulement pour les WHY non-évidents

---

## État de la documentation (`docs/index.html`)

> Mis à jour par la routine de documentation. Indiquer ici ce qui a été documenté.

### Complété (session 1 — 2026-05-12)
- **Architecture** : diagramme SVG infrastructure, flux de démarrage `create_app()`, gestion fichiers éphémères Cloud Run, arborescence des fichiers
- **Stack technique** : description complète de chaque couche (Flask, SQLAlchemy, JS vanilla, Claude API, OptiqCarto, Docker/Cloud Run)
- **Modèles de données** : diagramme ER SVG, description détaillée de tous les modèles (`Entity`, `Activities`, `Role`, `Link`, `Task`, `Tool`, compétences x5, `User`, `TimeAnalysis`, `FileBlob`, `RecentEvent`, `TaskLinkAssignment`), event listeners SQLAlchemy
- **Cartographie OptiqCarto** : éditeur et viewer, format JSON `optiqcarto_data`, logique `_sync_carto_to_db()`, gestion SVG multi-entités, import VSDX, API cross-carto
- **Authentification** : flux login/logout, patterns de contrôle d'accès, variables de session, reset password
- **APIs** : référence complète des endpoints cartographie (30+ routes documentées)
- **Déploiement** : variables d'environnement Cloud Run, workflow docker/gcloud, stratégie migrations DB (pas d'Alembic en prod)
- **Conventions** : JS vanilla, CSS, Blueprints, commentaires, workflow Git

### Complété (session 2 — 2026-05-13)
- **Activités — Fiche & Liste** : architecture modulaire (diagramme SVG des 8 sous-modules), page liste `GET /activities/view` (données rassemblées par activité : tâches, connexions, garant, task_conn_map, compétences), API détail `GET /activities/<id>/details` (JSON pour modales "Proposer…"), API items `GET /your_api/activity_items/<id>`, CRUD Performance sur les connexions, endpoints contraintes/data/reorder/update-cartography, fonctions utilitaires de résolution de liens
- **Import IA — Excel → DB** : flux en deux étapes (analyze → inject), format Excel attendu (colonnes auto-détectées, merged cells propagées), algorithme de matching 3 passes (exact/inclusion/fuzzy, seuils 0.60/0.75/0.90), enrichissement OpenAI optionnel (silencieux si indisponible), injection en base (déduplication tâches, get-or-create outils/rôles, compétences), référence complète API avec exemple de réponse JSON

### Complété (session 3 — 2026-05-15)
- **Compétences & Évaluations** (`competences.py`) : modèle `CompetencyEvaluation` (user/activité/item/type/eval_number/note), système multi-évaluateurs Garant/Manager/RH, hiérarchie manager global + manager par rôle, UPSERT delete+insert robuste PostgreSQL, 11 endpoints documentés (view, save_evaluations, role_structure, global_summary, etc.)
- **Performance** (`performance.py`) : indicateurs sur connexions `Link`, CRUD complet (add/update/delete), rendu fragment HTML server-side, fallback via activity_id, 5 endpoints documentés
- **Gestion RH** (`gestion_rh.py`) : rôles (CRUD + import CSV), affectation collaborateurs, managers global/par-rôle, paramètres temps de travail entité, migration `ALTER TABLE` idempotente au démarrage, 17 endpoints documentés
- **Chatbot IA** (`chatbot.py`) : assistant OPTIQ propulsé par **OpenAI GPT** (`gpt-4o-mini`), 2 modes (créer/améliorer), règles OPTIQ dans le prompt système (5-8 tâches, protocole "Ça dépend"), conversation stateless (historique côté client), injection `Task`+`Tool`+`Data`+`Link` en base, schéma JSON de réponse documenté

### Complété (session 4 — 2026-05-15)
- **Gestion du temps** (`time_view.py`, `time_extra.py`) : 4 sous-modules (Projet/Activité/Rôle/Faiblesse), 6 modèles SQLAlchemy (`TimeProject`, `TimeProjectLine`, `TimeAnalysis`, `TimeRoleAnalysis`, `TimeRoleLine`, `TimeWeakness`), helpers `to_minutes()`/`get_calendar_params()`/`ensure_time_role_schema()`, calcul de charge rôle par récurrence (journalier/hebdo/mensuel/annuel), formules de la faiblesse (variables O→AA avec probabilités), 18 endpoints documentés
- **Propositions IA** (`propose_common.py`, `propose_savoir_faires.py`, `propose_savoirs.py`, `propose_softskills.py`, `propose_aptitudes.py`) : module commun `build_activity_context()`/`openai_client_or_none()`/`dummy_from_context()`, 4 types GPT-4o-mini (savoir-faires verbes d'action, savoirs nominaux, HSC norme X50-766 avec niveau 1-4 et justification, scoring inclusion 5 catégories + faisabilité ICF), fallback 200 systématique sans clé OpenAI, 5 endpoints documentés

### Complété (session 5 — 2026-05-16)
- **Gestion des comptes** (`gestion_compte.py`) : 10 endpoints CRUD utilisateurs filtrés par entité active, import en masse JSON (prenom/nom/email/age/mot_de_passe/role/statut), assignation manager mode unitaire/multi, `flag_modified()` pour forcer UPDATE du hash password, déduplication par email à l'import
- **Onboarding IA** (`onboarding.py`) : plan d'onboarding GPT-4 en 4 modules (Formation/REX/Coaching/Autonome) exclusivement centré sur les HSC transmises par le client, sauvegardé dans `role.onboarding_plan`, 2 endpoints documentés
- **Export** (`export.py`) : export Excel 6 feuilles (openpyxl, thème violet) + HTML standalone autonome imprimable, stockage fichiers en DB via `FileBlob` (cloud-native, pas de filesystem), filtrage par rôle Garant ou entité entière, 4 endpoints documentés
- **Changelog** (`changelog.py`) : 3 niveaux de priorité (fichier curé JSON > cache mémoire/hash commit TTL 1h > génération OpenAI gpt-4o-mini depuis 30 commits git), journal activité récente depuis `RecentEvent` avec formatage relatif FR, 2 endpoints documentés
- **Vue des rôles** (`roles_view.py`) : 5 blocs de données par rôle (activités Garant, tâches non-Garant, compétences, savoirs/SF/aptitudes/softskills, titulaires), SQL brut pour `mission_generale` (colonne dynamique), introspection `PRAGMA table_info()` pour validation_level, 3 endpoints documentés
- **CRUD Connaissances** (`savoirs.py`, `savoir_faires.py`, `aptitudes.py`, `softskills.py`, `skills.py`) : 5 blueprints symétriques (add/update/delete/render), savoir-faires ajout en lot, softskill UPSERT par nom insensible à la casse, skills propositions IA GPT-4o-mini NF X50-124 + fallback regex
- **Projection métier** (`projection_metier.py`) : matching compétences utilisateur ↔ fiches ROME 4.0 (France Travail), OAuth2 client_credentials avec 2 tentatives + cache token, algorithme normalisation/tokenisation/Jaccard+SequenceMatcher (seuils 0.60/0.82), résultat paginé `{full, partial}`, 2 endpoints documentés

### Complété (session 6 — 2026-05-17)
- **Plan de compétences IA** (`competences_plan.py` + `plan_storage.py`) : génération GPT-4o-mini (3 types de plan : FORMATION/ACCOMPAGNEMENT/MAINTIEN), fallback systématique sans clé OpenAI, commentaires prérequis par item (UPSERT delete+insert), persistance JSON avec gestion conflit 409/force, 5 endpoints documentés
- **Performance personnalisée** (`performance_personnalisee.py`) : soft delete, normalisation statut multi-format, audit trail complet (create/update/delete avec détection de changement), rétrocompatibilité schéma historique, 7 endpoints documentés
- **Gestion des rôles** (`roles.py`) : CRUD rôles avec scope entité active, auto-création à l'assignation Garant, suppression en cascade activity_roles/task_roles, fragment HTML onboarding, 5 endpoints documentés
- **Traduction HSC** (`translate_softskills.py`) : traduction texte libre → 4-6 HSC normalisées X50-766 via GPT-4o-mini, règles anti-générique dans le prompt, mapping niveaux numériques → libellés officiels, 1 endpoint documenté
- **Liens tâches** (`task_link_assignments.py`) : assignations directionnelles tâche ↔ lien, table auto-créée checkfirst, upsert par delete+insert, GET par activité via jointure 3 tables, erreur silencieuse GET, 3 endpoints documentés
- **Contraintes** (`constraints.py`) : CRUD contraintes d'activité, validation existence activité, double clé activity_id+constraint_id sur PUT/DELETE, fragment HTML render, 4 endpoints documentés
- **Gestion des outils** (`gestion_outils.py`) : cycle de vie complet des outils (create/update/replace/delete), 4 stratégies de suppression (directe/force_detach/partielle/409), remplacement atomique inter-tâches, pré-chargement anti-N+1, unicité insensible à la casse par entité, 7 endpoints documentés

### En cours
- *(rien)*

### À faire (par priorité)
1. Éditeur OptiqCarto côté JS (`static/optiqcarto/editor.js`) — seul élément majeur restant

---

## Notes importantes

- La branche principale de travail est **`staging`** (pas `main`)
- `main` = production stable — ne merger que les versions validées
- Les fichiers `.vsdx` dans `Code/` sont des exemples Visio pour les tests
- `Code/instance/optiq.db` = base SQLite locale (ne pas committer)
- Les variables d'environnement sensibles (DB_URL, ANTHROPIC_KEY…) sont dans Cloud Run, pas dans le code

## Panel de tests & patchs (`/testpanel/`)

- Le panel est alimenté par la DB (`TestPage`/`TestCase`/`TestRun`/`TestResult` dans `Code/models/test_models.py`). Les runs sont déclenchés depuis le panel (subprocess pytest → DB).
- **Traçabilité des correctifs** : modèle `TestPatch` + registre versionné `tests/patches.json` (source de vérité). Le panel synchronise le JSON en DB à chaque consultation (`sync_patches_to_db`, même logique que `sync_tests_to_db`). Les patchs s'affichent par test (case), par page, et dans le tableau de bord global.
- Pour enregistrer un patch : ajouter une entrée à `tests/patches.json` (helper `tests/record_patch.py`). Champs clés : `failure_reason`, `was_real_bug`, `root_cause` (app_bug | test_isolation | test_quality), `error`, `fix_description`, `files_changed`, `fixed_at`.
- **Carnet de bord** (`/testpanel/journal`) : page visuelle pilotée par `tests/journal.json` (helper `tests/record_journal.py`). Affiche le **plan en cours** (étapes + progression) et le **journal des exécutions** (compte rendu bref par run). Lecture directe du fichier (pas de DB).
- **Prompt de la routine de tests** : référence versionnée dans `tests/ROUTINE_PROMPT.md` (la routine consacre ~30 % de chaque lancement à corriger les tests qui échouent + tracer les patchs, et termine chaque run par une entrée de carnet de bord + MAJ du plan).
- ⚠️ La base ET la session de test sont partagées (`scope=session` dans `conftest.py`) : 1re cause de faux échecs (pollution). Écrire des tests isolés (données dédiées + cleanup).
