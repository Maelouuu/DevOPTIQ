# CLAUDE.md — DevOPTIQ

Fichier de contexte lu automatiquement par Claude Code à chaque session.
Toujours le mettre à jour après chaque travail significatif.

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

### Complété
- **Architecture + infrastructure** : diagramme SVG inline, flux de requête, structure fichiers, isolation multi-tenant par entité, variables d'environnement
- **Stack technique** : détail de chaque couche (Python 3.12, Flask, Gunicorn, SQLAlchemy, PostgreSQL/SQLite, Flask-Mail, Anthropic API via SDK openai, LibreOffice, vsdx, openpyxl), tableau des variables d'environnement
- **Modèles de données** (`Code/models/models.py`) : toutes les tables avec colonnes clés, associations many-to-many, pattern `for_active_entity()`, journal d'audit SQLAlchemy event listeners

### En cours
- *(rien)*

### À faire (par priorité)
1. Page cartographie (`activities_map.py` + `activities_map.html`)
2. Éditeur OptiqCarto (`editor.js`)
3. Système d'import IA (`import_full.py` + `import_full.js`)
4. Fiche activité (toutes les routes `activities_*.py`)
5. Gestion RH (`gestion_rh.py`)
6. Performances (`performance.py`)
7. Chatbot (`chatbot.py`)
8. Auth et gestion compte (`connexion_routes.py`, `gestion_compte.py`)
9. Conventions de développement (section déjà initialisée)
10. Déploiement (Dockerfile, startup.sh, Cloud Run)
11. API Reference (tous les endpoints)
12. Tous les autres blueprints

---

## Notes importantes

- La branche principale de travail est **`staging`** (pas `main`)
- `main` = production stable — ne merger que les versions validées
- Les fichiers `.vsdx` dans `Code/` sont des exemples Visio pour les tests
- `Code/instance/optiq.db` = base SQLite locale (ne pas committer)
- Les variables d'environnement sensibles (DB_URL, ANTHROPIC_KEY…) sont dans Cloud Run, pas dans le code
