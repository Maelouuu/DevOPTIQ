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

### En cours
- *(rien)*

### À faire (par priorité)
1. Gestion compte + onboarding (`gestion_compte.py`, `onboarding.py`)
2. Éditeur OptiqCarto côté JS (`static/optiqcarto/editor.js`)
3. Tous les autres blueprints (export, changelog, projection_metier, roles_view, skills, softskills.py, savoirs.py, savoir_faires.py, aptitudes.py, etc.)

---

## Notes importantes

- La branche principale de travail est **`staging`** (pas `main`)
- `main` = production stable — ne merger que les versions validées
- Les fichiers `.vsdx` dans `Code/` sont des exemples Visio pour les tests
- `Code/instance/optiq.db` = base SQLite locale (ne pas committer)
- Les variables d'environnement sensibles (DB_URL, ANTHROPIC_KEY…) sont dans Cloud Run, pas dans le code
