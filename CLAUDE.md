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

Toutes les modifications (docs/doc_technique.html, docs/guide.html, CLAUDE.md) doivent être committées et pushées sur `staging`. Ne jamais travailler sur la branche de session par défaut.

**Séquence de fin de session obligatoire :**
```bash
git add docs/ CLAUDE.md
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
    ├── doc_technique.html  # Documentation technique progressive (ex-index.html)
    └── guide.html          # Guide utilisateur (ordre des sections = ordre de la nav bar)
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
  2. **voies** — `_separateLanes()` sépare les segments de flèches parallèles qui se superposent (2-3 flèches empilées sur la même ligne, typiquement en bordure quand plusieurs ports sont alignés) en voies distinctes (GAP 16 px). Segments collés à un port = ancres FIXES (on ne bouge que les segments intérieurs, jamais à travers une forme). Mesuré hard.vsdx : chevauchements (>30 px) 24 → 3.
  3. **labels** — `architectLabels()` place les labels près des pointes SANS jamais les poser là où une flèche en croise une autre (222/243 placés, 0 sur une autre flèche).
- **Curseur global des labels** (remplace le bouton « Agencement auto » ; toolbar, `#label-pos-slider`) : `setLabelsAlongArrows(t)` pose TOUS les labels à la même fraction `t` de LEUR flèche — gauche = origine (source), droite = pointe — en direct. `_pointAlongPath()` donne point + angle ; une marge par flèche évite le chevauchement des formes d'extrémité.
- **Pointes** (au rendu, toujours actif) : `polylineToPath(pts,R,tipPad=18)` (approche droite ≥18 px avant la tête) + `_alignPortApproach()` (dernier segment aligné sur l'axe du port → la tête ne pivote pas).
- **Losanges décoratifs** (non connectés, posés « sur » une flèche dans Visio sans `<Connect>`) : `spliceDecisions` DÉSACTIVÉ (les insérer dans le flux complexifiait les flèches pour rien). `_seatDecorativeDiamonds()` les repose sur LEUR flèche APRÈS le polish : quand on redresse un angle ou qu'on rejette un tracé en détour, la flèche bouge — le losange, associé au connecteur dont le `customPath` Visio d'origine passe le plus près (seuil 60 px), est reposé sur le tracé FINAL de ce connecteur, à la même fraction. Mesuré hard.vsdx : 17/19 losanges à ≤5 px de leur flèche ; les 2 restants sont VRAIMENT flottants dans Visio (>90 px de tout connecteur) → laissés à leur position Visio. Banc : métrique `deco.offArrow`.
- ⚠️ **Réalité hard.vsdx** : 165 formes / 243 flèches / 43 flèches « retour » (graphe cyclique) → **~400 croisements MÊME dans le Visio d'origine fait à la main**. Densité inhérente, aucun algo (ni Graphviz, ni l'humain) ne fait mieux. Sur une carto de taille normale : **0 croisement**. On juge la réussite sur les cartos normales, PAS sur hard.vsdx (cas extrême / stress-test).
- **Flèches alignées DROITES** (`_straightenAlignedConnectors()`, appelé à l'import avant le polish) : une flèche entre deux formes alignées mais légèrement décalées devenait un ESCALIER (les deux ports tombaient à des X différents). On aligne les deux ports sur une coordonnée commune du recouvrement → tracé rectiligne fidèle Visio. **Garde-fous (essentiels) :** (1) uniquement connecteurs longs (>120 px) et formes qui se recouvrent (≥28 px) ; (2) **jamais à travers une forme tierce** (`pickFree` évite les X occupés par une forme → sinon on garde le routage qui la contourne) ; (3) **anti-empilement** : deux droites parallèles gardent ≥16 px d'écart (deux flèches bidirectionnelles entre formes empilées → deux voies distinctes, plus de croisement). Banc hard.vsdx : 45 verticales alignées → 0 escalier, 0 traversée de forme ; example/CT/TSM : 0 croisement, 0 superposition.
- **Connexions « à moitié collées » récupérées** (`_recoverFloatingConnections()`, vsdx_importer) : un connecteur Visio n'ayant un `<Connect>` que d'UN côté (l'autre bout flotte mais tombe pile dans une forme) était jeté (source/target absent). On infère l'extrémité manquante via la boîte Visio qui contient le point (tol 0,4). Corrige le renvoi isolé « Spare Parts Stock » ET les losanges « au milieu de nulle part » (posés sur ces flèches perdues). Banc hard.vsdx : 243 → 245 connexions.
- **Détour rejeté même vers un GROUPE** : le rejet de détour (import classique) résout désormais les groupes (`getGroupBounds`) — un connecteur visant un groupe avait une boîte infinie → un plongeon « descend puis remonte » DANS les bandes n'était jamais rejeté. Corrigé (« Bar Feeder Technician » plongeait 650 px sous sa source).
- **Agencement auto (NOUVEAU)** — moteur isolé `static/optiqcarto/optiqarrange.js` + `_computeAutoArrange()` dans editor.js, déclenché par un bouton **dans la pop-up Diagnostic carto** (bouton Vérifier). Layered/Sugiyama contraint aux bandes : réordonne les formes en colonnes gauche→droite (plus-long-chemin après cassage des cycles), **chaque forme reste dans sa bande d'origine**, route les flèches de zéro + polish, flèches RETOUR dans un canal dédié au-dessus de la carto (packing par intervalle x). **N'est PAS utilisé à l'import VSDX** (l'import reste la reconstruction classique fidèle Visio). Banc : `?arrange=1` / `?arrange2=1` (vraie fonction embarquée) → 0 superposition sur example/CT/TSM.
- **Placement manuel des losanges à l'import** (`_startDiamondPlacement()`) : après reconstruction + pré-placement, une pop-up (DA outil) propose d'ajuster chaque losange décoratif un par un dans une fenêtre zoomée (« cadre » : contexte formes+flèches, losange gris glissable). La **flèche associée** au losange (`_seatDecorativeDiamonds` mémorise `_seatConnId`) est **surlignée** (halo ambré) ; les **étiquettes** des flèches sont affichées et **glissables** (MAJ `c.labelOffset`) → on ajuste losange ET labels l'un par rapport à l'autre. Position validée = définitive. « Tout garder » accepte le reste pré-placé. Finalisation de l'import différée derrière la pop-up. Carto sans losange → pop-up sautée. Banc : `?diamonds=1`.
- **Routage par défaut d'une connexion manuelle = Z propre (1 décrochement)** (`orthogonalPts`, geometry.js). Deux activités en diagonale reliées à la main donnaient un ESCALIER (5 segments, 2 décrochements) sur les cas même-axe (V→V, H→H). On produit désormais un Z propre à UN seul décrochement (`[fp, coude1, coude2, tp]`, 4 points : sortir le long du port → traverser une fois → entrer) — plus lisible. Cas alignés (droit) et cas mixtes (H→V/V→H, déjà propres) inchangés. N'affecte QUE les connexions sans `userPts` (créées/reroutées à la main) ; les tracés Visio importés (avec `userPts`) ne changent pas.
- **Décision Oui/Non RETIRÉE** : le badge « ? » sur les losanges de décision (clic → cycle `decisionYesDir` → tag `choiceLabel` Oui/Non + badges O/N) a été supprimé de l'éditeur (jugé inutile). Retiré : le rendu des badges O/N (aux pointes du losange + sur les flèches), le handler de clic `decision-dir-badge`, `_syncChoiceLabels()`, `_nearbyConnections()`, `_renderChoiceBadgesOnConns()`, le défaut `decisionYesDir`. ⚠️ Le champ `Link.choice_label` (DB) et son affichage dans les **fiches activité** (`activity_connections.html`, `activity_card_new.html`) sont un AUTRE mécanisme, conservés : un connecteur de décision dont le libellé est « Oui »/« Non » est toujours absorbé en `choice_label` par `_do_sync` et affiché dans les vues activité (pas dans l'éditeur carto).
- **Correction ciblée des erreurs (NOUVEAU)** — bouton **« Corriger les erreurs »** dans la pop-up Diagnostic carto (à côté d'« Agencement auto »). Contrairement à l'agencement auto (réorganise TOUTE la carto), la correction ciblée ne touche QUE les formes fautives relevées et laisse le reste tel quel. Flux en 3 temps : `_computeFixes(issues)` (propose sans appliquer) → `_showFixPreview(fixes)` (**pop-up de validation avec aperçu ZOOMÉ** de chaque correction : position actuelle en rouge pointillé, cible en vert + flèche, croix rouge pour une suppression, nouveau libellé pour un renommage ; cases à cocher, défaut cochées) → `_applyFixes(sel)` (applique la sélection validée). **4 familles corrigées** : `outofband` (recentrage vertical dans la bande la plus proche via `_nearestBand`), `overlap` (nouvelle détection dans `runCartoCheck` → `_findFreeSpot` déplace la forme vers l'emplacement libre le plus proche, en restant dans sa bande), `renvoi` orphelin (**suppression** de la forme + ses connexions), `duplicate` (**renommage** avec suffixe « (n) », la 1re occurrence est conservée). Seules les flèches rattachées à une forme déplacée voient leur routage réinitialisé (`userPts/customPath/…` = null) ; les tracés Visio des autres flèches sont intacts. `isolated` reste listé seulement (pas de correction déterministe). Testé (`tests/carto` — `test_autofix.js` + intégration navigateur : aperçu, validation, application des 4 familles, préservation des tracés).

---

## Refonte Compétences V1.1 (CDC OPTIQ — en cours)

Plan complet : `docs/refonte_competences_v1_1.md`. Recâble le module autour de la chaîne
**Activité → Données de sortie → RÉSULTAT → Compétence → Diagnostic → Plan**. L'évaluation
commence par le RÉSULTAT ; S/SF/HSC ne servent qu'au diagnostic d'un écart. Niveau global
d'activité = **min** des résultats (jamais de moyenne) ; NULL (non évalué) ≠ 0. Codes
techniques internes (RESULT, DAILY, WORK_ARCHITECTURE…) **jamais affichés** : libellés FR/EN.

**Itération 1 livrée (backend testé + page refondue) :**
- **P1** `qualify_outputs.py` (`/qualify`) — `Data` +`semantic_nature`/`minimum_performance_text`/
  `qualification_source`/`qualification_updated_at`. Analyse IA des sorties (RESULT/MEASURE/
  EVENT/INFORMATION), repli sans clé = « à qualifier » (jamais inventé).
  ⚠️ **Correctif (les sorties = connexions sortantes).** Une « donnée de sortie » d'une activité
  EST une **connexion sortante** (Link activité→activité) de la carto ; son nom = le libellé de la
  flèche (`Link.description`), à défaut le nom de l'activité destinataire. Les `Link` sont
  supprimés/recréés à chaque sauvegarde carto → la qualification ne peut PAS vivre sur le `Link`.
  `materialize_activity_outputs()` matérialise chaque connexion sortante en `Data` durable ancrée
  via `Data.producer_activity_id` (sans `shape_id` → invisible dans la carto, jamais touchée par
  `_sync_carto_to_db`). Idempotent (get-or-create par nom) ; une sortie déjà qualifiée est
  conservée même si le libellé de sa connexion change. Corrige « Configurer (qualifier les sorties)
  » qui affichait toujours « aucune donnée de sortie ». Tests : `tests/test_51_qualify_outputs.py`.
- **P2** `result_capabilities.py` (`/competence`) — table `result_capability_links` (RESULT↔S/SF/HSC).
  Compétence PRINCIPALE (fondée sur les RESULT, sans énumérer S/SF/HSC) ; S/SF/HSC générés par résultat ; badges « R1 ».
- **P3** `mastery.py` (`/mastery`) — `activity_roles.required_mastery_level`, `CompetencyEvaluation`
  +`mastery_level`/`evidence`/`evaluated_at`/`evaluator_user_id`. Éval par RESULT (`item_type='activity_results'`),
  global = min, couleur calculée. Échelle 0-4 + NULL.
- **P6** page Compétences **refondue en place** (`competences_view.html` + `competences_v2.js`) :
  tableau requis/démontré/écart/résultats → tiroir éval par résultat → diagnostic 3 familles
  (`diagnostic.py` `/diagnostic`, table `result_diagnostics`) → plan (règle CDC 6.8 : pas de plan
  individuel auto si l'écart relève de l'Architecture ou des Conditions d'exécution).
- Migrations idempotentes cross-dialect (`_safe_add_column` + `__table__.create(checkfirst=True)`).
  IA = gpt-4o-mini, JSON strict, repli propre. 1402 tests existants OK (non-régression).

**Itération 2 livrée (backend testé) :**
- **P4** `technical_domains.py` (`/domains`) — 4 tables (technical_domains,
  activity_technical_domains, role_activity_domain_requirements, user_domain_levels), échelle
  technique 0-4 dédiée. Alerte « Technicité » branchée sur le tableau principal (`domain_gap`).
- **P5** `cadence.py` (`/cadence`) — `Activities` +cadence, `Data` +update_cadence/max_age_hours,
  9 codes. Analyse « Cohérence des rythmes » LECTURE SEULE (règles, sans IA) : point de vigilance
  + question OPTIQ quand une donnée est plus lente que l'activité aval.
- **P7** `hsc_positioning.py` (`/hsc`) — niveaux stabilisés (4 = Expertise, plus « Excellence »),
  table `hsc_level_descriptors` (référentiel comportemental), auto-positionnement IA (niveau
  probable, jamais validé seul).

**Reste (finitions, premier jet à retravailler) :** UI de gestion des domaines et curseur de
cadence sur la fiche activité ; panneau de qualification des sorties + badges « R1 » sur les
écrans S/SF/HSC ; widget d'auto-positionnement HSC ; carto : badge cadence (repo OptiqCarto).

---

## Conventions de code

- **Pas de framework JS** : tout en vanilla JS, `$()` est un alias `document.querySelector`
- **CSS par domaine** : chaque page a son CSS dédié, `optiq.css` = styles globaux
- **Templates Jinja2** : les pages incluent des partials (`{% include "partial.html" %}`)
- **Blueprints Flask** : chaque domaine est un blueprint enregistré dans `app.py`
- **Couleurs thème** : rose `#ec4899` / `#be185d` (principal), vert `#22c55e` (accent)
- **Pas de commentaires évidents** dans le code : seulement pour les WHY non-évidents

---

## État de la documentation (`docs/doc_technique.html` + `docs/guide.html`)

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

### Complété (session 7 — 2026-07-27)
- **Renommage** : `docs/index.html` → `docs/doc_technique.html` (liens du guide mis à jour)
- **Doc technique — mise à niveau OptiqFluent & V1.1** : nouvelle section « Refonte Compétences V1.1 » (7 blueprints P1-P7, chaîne Résultat, règles min/NULL), nouvelle section « Distribution OptiqFluent » (durcissement, licence Ed25519, prompts chiffrés Fernet, image bytecode-only, assistant /setup, kit client, CI ghcr.io), nouvelle section « Administration & UX IA » (ai_key, settings admin, logstream, optiq_alert). Sections mises à jour : Stack (IA = OpenAI gpt-4o-mini partout + Claude en secours carto ; auth = security.py PBKDF2 600k), Architecture (~49 blueprints, gunicorn.conf.py, lock_timeout), Modèles (tables V1.1 + app_settings + test_*), Cartographie (import VSDX classique + polish, diagnostic/agencement auto/correction ciblée, curseur labels, losanges), Auth (politique mots de passe), RH (EntrepriseSettings ORM), Chatbot (get_openai_key, 503 ai_unavailable, prompts catalog), Déploiement (variables complètes, branche optiqfluent-beta-test)
- **Guide utilisateur — restructuration + illustrations** : sections réordonnées sur l'ordre de la nav bar (Carto → Activités → Rôles → Compétences → Temps → Comptes → RH → Outils → [IA, Performance, Export] → Paramètres → Glossaire). 3 nouvelles sections illustrées : Rôles (fiche 5 blocs + onboarding IA déplacé depuis RH), Comptes (mockup table + import en masse déplacé depuis RH), Outils (4 cartes cycle de vie). Nouveaux blocs : évaluation par RÉSULTAT (chaîne + mockup tiroir d'éval + diagnostic 3 familles + technicité/cadence/HSC), import Visio fidèle (mockup avant/après), Diagnostic carto (mockup pop-up Corriger les erreurs / Agencement auto), « Et si l'IA n'est pas configurée ? », Paramètres → section Administration (mockup clé IA + console serveur) + note édition OptiqFluent, calendrier de travail déplacé dans RH, 2 entrées de glossaire (Résultat, Diagnostic d'écart)
- **App — nav bar réordonnée** (`header_buttons.html`) : Cartographie, Activités, Rôles, Compétences, Temps, Comptes, RH, Outils, Paramètres — même ordre que le guide (règle : Cartographie première, Paramètres dernière)

### En cours
- *(rien)*

### À faire (par priorité)
1. Éditeur OptiqCarto côté JS (`static/optiqcarto/editor.js`) — seul élément majeur restant

---

## Distribution client — branche `optiqfluent-beta-test`

Branche dédiée à la mise à disposition de l'app chez un client pilote (rebrandée
**OptiqFluent**), basée sur `staging`. Modèle retenu : **image Docker sur registre
privé (ghcr.io) + licence signée à expiration + contrat d'évaluation**. Contenu :

- **Durcissement pré-livraison** (tout dans cette branche) : mot de passe Gmail
  AFDEC retiré du code (mail 100 % par env, désactivé proprement sans config —
  `MAIL_CONFIGURED`) ; endpoint debug `/api/debug-decisions/env-check` (fuite des
  vars d'env) supprimé ; `SECRET_KEY` sans défaut public (secret éphémère + warning
  si absente) ; `DEBUG` piloté par `FLASK_DEBUG` (défaut off) ; pool DB configurable
  (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`) ; seed de démo derrière `DEMO_SEED=1` ;
  **bootstrap 1er compte admin** (`ADMIN_EMAIL`/`ADMIN_PASSWORD`, seulement si 0
  utilisateur) ; gunicorn unifié (`gunicorn.conf.py`, `WEB_CONCURRENCY`) ;
  `.dockerignore` étendu (zips, backups, tests, docs, vsdx, scripts dev, tools/).
- **Licence** (`Code/licensing.py`) : JSON signé Ed25519 (clé publique embarquée
  `Code/license_pubkey.pem`, clé privée JAMAIS committée), date d'expiration,
  active si `REQUIRE_LICENSE=1` (baké dans le Dockerfile de cette branche — nos
  propres déploiements passent `REQUIRE_LICENSE=0`). Bloque tout sauf `/healthz`,
  `/license`, `/static` (page `license_blocked.html`). Renouvellement à chaud :
  remplacer le fichier `.lic`, pris en compte sans redémarrage. Outils AFDEC :
  `tools/licensing/keygen.py` (une fois, avant le 1er build client — la clé
  publique committée doit correspondre à une clé privée conservée) et
  `tools/licensing/make_license.py --licensee … --days …`.
- **Kit client** (`distribution/`, exclu de l'image) : `.env.example` commenté
  (DB embarquée ou hébergée, clé OpenAI du client, compte Google + mot de passe
  d'application pour le mail, admin initial), `docker-compose.yml` (app +
  postgres:16 + volume), `INSTALL.md`, `CONTRAT_EVALUATION.md` (projet à faire
  valider par un juriste).
- **Rebranding** : DevOPTIQ → OptiqFluent dans l'UI, emails et en-têtes.
- **Phase 2 (livrée)** :
  - **Prompts IA externalisés + chiffrés** : TOUS les prompts (36, dont le
    référentiel X50-766) vivent dans `Code/prompts/catalog.py` (dict `PROMPTS`,
    exclu de l'image client). `get_prompt(key, **vars)` (`Code/prompts/__init__.py`),
    placeholders `[[var]]` (PAS `.format` : accolades JSON). Image client = bundle
    chiffré Fernet `Code/prompts/prompts.enc` (généré par
    `tools/prompts/encrypt_prompts.py`), clé via env `PROMPTS_KEY` ou champ
    `prompts_key` de la licence signée. Sans clé → chaque route dégrade comme
    « sans clé OpenAI » (fallbacks existants). ⚠️ Ne JAMAIS remettre un prompt en
    dur dans une route — tout passe par le catalogue. Seul `role_i18n.py` garde
    son prompt trivial en dur (aucun savoir-faire dedans).
  - **Anti-inspection** : image bytecode-only (Dockerfile : `compileall -b` puis
    suppression des `.py` sauf `gunicorn.conf.py`). `load_dotenv()` avec chemin
    explicite (l'auto-détection casse en bytecode). Dissuasion, pas protection
    absolue (le vrai verrou = prompts chiffrés + licence + contrat).
  - **`/testpanel` désactivé chez le client** : blueprint non enregistré si
    `TESTPANEL_ENABLED=0` (baké dans le Dockerfile ; réactivable par env).
  - **LibreOffice retiré** du Dockerfile (~1,5 Go) : aucun usage dans le code
    (exports = openpyxl/python-docx).
  - **CI** : `.github/workflows/client-image.yml` — push d'un tag `client-v*` →
    build + push `ghcr.io/maelouuu/optiqfluent:<version>` + `:beta` (secret GitHub
    `PROMPTS_KEY` requis). Runbook AFDEC complet : `distribution/RELEASE.md`
    (keygen, licences, token client, leviers de contrôle).
  - **Déploiement Cloud Run interne** : `tools/deploy/deploy_cloudrun.sh` —
    remplace `devoptiq-staging-mv` par `optiqfluent-staging` (Cloud Run ne
    renomme pas : création + recopie des env vars + suppression sur
    confirmation ; ajoute REQUIRE_LICENSE=0, PROMPTS_KEY, TESTPANEL_ENABLED=1).
    ⚠️ `.gcloudignore` obligatoire (sinon gcloud suit .gitignore qui exclut
    prompts.enc → build cassé).
  - **Répétition d'installation client** : `tools/test_install.sh` — rejoue
    INSTALL.md sans Docker (licence de test avec prompts_key embarquée, arbre
    bytecode-only, PostgreSQL 16 vierge, gunicorn, 9 vérifications curl/logs
    dont prompts-via-licence). Passe 9/9.
  - **Assistant d'installation web** (`/setup`) : premier démarrage de l'image
    client (`SETUP_WIZARD=1` dans le compose + aucune config écrite) → mode
    installation (`Code/routes/setup_wizard.py` + `setup_wizard.html`) : gate
    before_request vers /setup, étapes licence (collée, validée, sauvée sur le
    volume) → BDD (test de connexion, pré-remplie avec la base intégrée) →
    clé OpenAI (testée) → mail optionnel (test SMTP) → compte admin → récap.
    « Installer » écrit `/app/config/optiqfluent.env` (volume `./config`,
    valeurs dotenv double-quotées) puis SIGTERM au master gunicorn → le
    conteneur redémarre configuré et le boot NORMAL fait tout (create_all,
    migrations, bootstrap admin) ; `ADMIN_PASSWORD` est purgé du fichier après
    création du compte. Relancer l'assistant = supprimer le fichier de config.
    Les vraies variables d'env gardent priorité sur le fichier. `/setup` exempt
    du blocage licence. Tests : `tests/test_60_setup_wizard.py` (14) + E2E
    Postgres. ⚠️ Ne s'applique pas à Cloud Run (pas de volume persistant —
    nos déploiements restent configurés par variables d'environnement).

## Administration & UX IA (branche optiqfluent-beta-test)

- **Clé IA à chaud** : `Code/ai_key.py` — `get_openai_key()` (table `app_settings`
  clé `openai_api_key` en priorité, puis env `OPENAI_API_KEY`). ⚠️ Ne JAMAIS lire
  `os.getenv("OPENAI_API_KEY")` dans une route : toujours `get_openai_key()`
  (toutes les routes IA recâblées). Message d'erreur standard : « Clé IA non
  renseignée. »
- **Paramètres → section Administration** (`settings.py`, visible seulement si
  `User.status` ∈ {admin, administrateur} ; invisible sinon) : clé IA masquée
  (révélation/modification via `/parametres/admin/openai-key[...]`), URL BDD
  masquée, **console serveur** rétractable (polling `/parametres/admin/logs`).
- **Console serveur** : `Code/logstream.py` — tee stdout/stderr + handler logging
  vers `/tmp/optiqfluent-server.log` (plafonné 2 Mo), init dans `create_app`
  (hors tests), lecture incrémentale par offset.
- **Pop-up in-app** : `static/js/optiq_alert.js` — `optiqAlert()` (modal DA),
  `optiqAiCheck(data)` (détecte les réponses IA dégradées → pop-up « clé IA non
  renseignée » ou « IA indisponible »), et **override de `window.alert`** (toute
  page qui inclut le script convertit ses alert() en pop-ups stylées). Inclus via
  `script_loader.html`, `chatbot_widget.html`, `competences_view.html`,
  `activity_savoirs.html`. Checks ajoutés dans les handlers propose_* /
  competencies. Chatbot sans clé → 503 `ai_unavailable`.

## Notes importantes

- **Mots de passe (politique de hachage)** : centralisée dans `Code/security.py` —
  `hash_password()` / `verify_password()` / `needs_rehash()`. Standard = **PBKDF2-SHA256
  600 000 itérations** (recommandation OWASP, ~102 caractères → tient dans toutes les
  variantes historiques de la colonne). Les anciens hashes (scrypt Werkzeug 3, ~162 car.,
  cause du bug « le changement de mot de passe ne prend pas » quand la colonne prod était
  trop étroite) restent acceptés au login et sont **re-hachés silencieusement** vers le
  standard. `set_password` et le reset par email **relisent le hash en base après commit**
  (jamais de faux succès). Migration idempotente au démarrage : `users.password` élargi
  à VARCHAR(255). Ne jamais appeler `generate_password_hash` directement — passer par
  `Code/security.py`.
- **Paramètres entreprise** : modèle `EntrepriseSettings` (table `entreprise_settings`,
  1 ligne par entité) — historiquement en SQL brut sans modèle, donc jamais créée par
  `create_all()` en prod (section RH vide + faux succès d'enregistrement). Endpoints
  réécrits en ORM avec liste blanche des clés (`SETTING_KEYS`) et relecture post-commit ;
  le JS (`gestion_rh.js`) vérifie désormais `res.ok`. `get_calendar_params()` (time_view)
  lit maintenant cette table (l'ancienne requête visait `enterprise_settings`, inexistante).
- **Traduction des rôles** : `Code/role_i18n.py` — `Role.name` = saisie d'origine (jamais
  réécrite), caches `name_fr`/`name_en`. À la création/renommage, le nom saisi remplit le
  cache de la langue courante ; l'autre langue est traduite à la volée (gpt-4o-mini) au
  premier affichage de la page Rôles puis persistée. Sans clé OpenAI → nom d'origine
  (jamais inventé). Appeler `on_role_name_saved(role, name)` sur tout create/rename de rôle.
- **i18n JS** : page RH → `window.GRH_I18N` (gestion_rh.js) ; fichier DCP →
  clés `pf_*` dans `window.PROPOSE_I18N` (propose_from_file.js, repli français intégré).
  Injecter les chaînes avec `| tojson` (jamais `"{{ t(...) }}"` → entités HTML dans le JS).
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
