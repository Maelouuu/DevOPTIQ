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
| `import_full.py` | `/import/` | Moteur d'appariement et d'injection des tâches (réutilisé par `import_hub`) |
| `import_hub.py` | `/api/import` | Fenêtre « Importer des données » de la page Carte |
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

### Paquet de cartographie `.optiqcarto` (distribuer une carto corrigée)
Une carto reprise à la main ne doit **jamais** être redistribuée sous forme de `.vsdx` : réimporter
le fichier Visio d'origine ré-introduit les défauts que l'utilisateur vient de corriger. Le paquet
transporte le diagramme **tel qu'il est en base**, d'un compte à l'autre.
- **Format** : JSON, `{format:"optiqcarto/entity", version, exported_at, entity:{name,description,vsdx_filename}, diagram:{…}}`. Un **diagramme brut** (ce que renvoie `/api/load`, et ce que contient `tools/provisioning/carto/`) est aussi accepté à l'import — un seul format de fichier pour les deux chemins.
- **Export** : `GET /cartography/api/export` (`?entity_id=` sinon entité active) → pièce jointe `<entité>.optiqcarto`. Bouton **« Exporter la carto »** dans la barre de l'éditeur ; il **enregistre d'abord** si le diagramme est modifié, sinon on distribuerait une version antérieure aux retouches.
- **Import** : `POST /cartography/api/import` (multipart `file`, optionnels `name`, `entity_id`) → **crée** une entité pour le compte connecté (nom suffixé « (2) » s'il est déjà pris), la rend active, puis dérive activités / rôles / connexions via `_sync_carto_to_db` — exactement comme après un import Visio. Avec `entity_id`, remplace la carto d'une entité existante **du compte connecté** (les autres renvoient 404). Bouton **« Importer une carto »** à côté de « Créer » dans la pop-up Gestion des entités.
- `tools/provisioning/provision.py` (`apply_carto`) dégrafe l'enveloppe : le même fichier sert au provisionnement AFDEC et à l'import manuel dans l'interface.
- ⚠️ **Contrat DOM editor.js ↔ gabarits** : `editor.js` câble ses boutons SANS garde (`document.getElementById('btn-x').addEventListener(…)`). Un id absent d'un gabarit lève une TypeError qui interrompt TOUTE la suite de l'init, **chargement de la carto compris** — symptôme silencieux : la page Cartographie affiche un cadre gris et vide alors que les données sont en base. Le viewer (lecture seule) déclare donc des **boutons vides** dont le seul rôle est de satisfaire ce câblage. `tests/test_49_carto_dom_contract.py` vérifie que la liste reste complète des deux côtés. Mise au point : `tools/devrun_carto_check.py` (instance jetable SQLite + deux comptes source/cible, port 8123) pour rejouer un import de paquet en local.
- Tests : `tests/test_48_carto_package.py` (13 cas — aller-retour export/import entre deux comptes, préservation des multi-liens, collision de noms, remplacement, cloisonnement par compte, fichiers invalides).

- ⚠️ **Un import VSDX est une modification NON ENREGISTRÉE.** La fin de l'import
  repart d'une baseline d'historique neuve (`history = [state]`) : plus aucune
  « version » ne séparait l'état affiché de son point de départ, `snapshot()`
  n'était jamais appelé, et `isDirty` restait faux — on quittait la page sans le
  moindre avertissement, l'import perdu. L'import pose donc `isDirty = true` et
  relance l'auto-sauvegarde.
- ⚠️ **La mini map se posait SUR la pastille de zoom** : les deux occupaient le coin
  bas-droit du canevas. Elles partagent maintenant le même bord droit (`--corner-gap`),
  la mini map juste au-dessus (`--zoom-pill-h`). Elle s'appelle **« Mini map »** dans les
  deux langues — c'est le terme produit, comme « Optiq Map ».
- ⚠️ **La barre d'outils débordait sur un portable et flottait sur un 27 pouces.**
  Elle est ancrée à gauche ET à droite (`left/right: 10px`), et son contenu du milieu
  était dessiné en pixels fixes : mesuré à 1180 px de large, il passait **68 px sous**
  « Panneau » et « Propriétés ». Un facteur unique `--ui-k`
  (`static/optiqcarto/ui_scale.js`, `largeur / 1400` borné à 0,70–1,25, recalculé au
  redimensionnement) tient les deux bouts : à 1024 px il reste 22 px de marge de chaque
  côté, à 2560 px la barre occupe 54 % de l'écran au lieu de 43 %.
  ⚠️ Le zoom porte sur **`#toolbar > *`**, pas sur `#toolbar` : zoomer le conteneur
  réduirait aussi sa largeur ancrée, la barre ne tiendrait plus toute la fenêtre.
  ⚠️ **`zoom` et pas `transform: scale()`** : un `transform` crée un bloc conteneur pour
  les descendants `position: fixed` — les menus déroulants de la barre se retrouveraient
  ancrés au mauvais repère. Vérifié : le menu Fichier reste sous son bouton.
  Contrat gardé par `tests/test_49_carto_dom_contract.py`.
- ⚠️ **Le viewer charge `editor.js` mais n'injectait aucune traduction** : chaque
  `_L()` y affichait la CLÉ BRUTE (« editor.minimap »). `cartography_viewer.html`
  reçoit désormais `i18n_data`, comme l'éditeur. Les libellés de la **mini-carte**
  (titre et trois info-bulles) étaient en dur en français : ils passent par
  `editor.minimap*`.

### Import VSDX & flèches (reconstruction classique — mode UNIQUE)
- **Lecture de la géométrie des connecteurs — CORRIGÉ (bug racine de l'import)** : `readConnGeom()` lisait les `Row` d'une Section Geometry comme si l'origine du repère local était le point **Begin**. C'est **Pin − LocPin** : `LocPinY` valant la demi-hauteur du connecteur, chaque tracé était décalé → flèches en biais sur toute leur longueur. Deuxième bug : une `Cell` X ou Y **absente** d'une Row est **héritée du master** ; on jetait la Row entière, donc la géométrie de la majorité des connecteurs. On reconstruit désormais les valeurs manquantes depuis Begin/End (extrémités) ou le sommet précédent (Visio est orthogonal), on saute les Row `Del='1'`, et on accepte les arcs (`ArcTo`/`EllipticalArcTo`, réduits à leur point d'arrivée — le renderer arrondit). Mesuré : **tracés Visio exacts 38/88 → 88/88** (carto client ARaymond), 178/245 → 245/245 (hard.vsdx), 10/31 → 31/31 (example/CT/TSM) ; **segments en biais : 64 % → 0 %** ; **détours rejetés 9 → 0**.
- **`orthoClean()` + `finalizeConnPaths()`** (vsdx_importer) : les extrémités d'un tracé sont replacées sur les bords des formes, et `cleanupBands`/`antiOverlap`/`stretchBands` déplacent les formes APRÈS la construction des connexions. `finalizeConnPaths()` (dernière phase) recolle les deux bouts sur les bords définitifs puis `orthoClean()` ré-équerre : bruit flottant Visio (1e-15) aligné, raccord des extrémités par alignement (≤ 4,5 px) ou par vrai coude au-delà, points colinéaires supprimés. `cleanupBands()` décale aussi les `customPath` (il ne le faisait pas, contrairement à `stretchBands`).
- **Multi-liens (fourches et fusions)** — `bundleMultiLinks()` : Visio dessine « une flèche qui se divise en deux » comme N connecteurs qui **partagent leurs premiers sommets** (le tronc) avant de diverger. Lus littéralement ces troncs donnaient N polylignes *presque* identiques, que le renderer traitait comme N flèches distinctes et écartait → bouillie de traits superposés au départ des losanges. On aligne chaque portion commune sur une polyligne unique (tolérance 7 px, partition récursive : les branches divergent à des profondeurs différentes) et on marque les membres (`bundleId`, `trunkFrom`/`trunkTo`). Mesuré : 11 fourches sur la carto client, **écart max sur les troncs 0,000 px**.
- **Flèches parallèles qui s'inversaient** : deux corrections. (1) `_nudgePortConflicts()` écartait les ports trop proches — y compris deux branches partant **exactement** du même point Visio, c'est-à-dire une vraie fourche : ce cas est désormais exempté (écart ≤ 1e-4 = même point = tronc commun). (2) Dans `renderConnections`, l'ordre d'`unifiedUsage` (auto-spread des ports sans `portT` explicite) suivait l'ordre de `state.connections` → deux flèches parallèles entre les deux mêmes formes se retrouvaient interverties ; il est désormais **géométrique** (trié sur la position de l'autre extrémité). `bundleOffset` ne compte plus que les points de départ **distincts**, pour que les branches d'une fourche gardent un tronc commun même en routage automatique.
- **L'agencement automatique a été RETIRÉ** (bouton, `_computeAutoLayout`, libavoid + worker, modale avant/après, animation de chargement — ~710 lignes). Raison mesurée au banc `tests/carto/` : **re-router les flèches JETTE le bon tracé humain de Visio et AJOUTE des croisements** (carto normale : 0 → 8 ; re-disposition compacte : 817 vs 350 sur hard.vsdx). Le tracé Visio est déjà bon → on le garde.
- **Import = reconstruction CLASSIQUE (fidèle Visio), par défaut, sans dialogue.** Les tracés exacts (`customPath`) deviennent les `userPts` rendus — SAUF les **détours aberrants** (waypoint hors carto, OU loin hors de la boîte des 2 extrémités, marge 180 px) : ceux-là sont jetés (`userPts=null`) et routés proprement (orthogonal + évitement). Corrige les flèches qui plongeaient dans le vide / dépassaient leur forme (2 angles inutiles). Une flèche visant un **groupe** conteneur se connecte au **bord du cadre du groupe** (comme dans Visio), PAS re-ciblée sur une forme membre (essayé : ça entassait les flèches sur un membre et augmentait les croisements). Mesuré hard.vsdx : croisements 400+ → ~269, 0 flèche hors carto / dans le vide. Puis `_reconstructClassicPolish()` retouche SANS ré-agencer :
  1. **angles droits** — `_orthogonalizeStaircase()` orthogonalise chaque tracé Visio quasi-droit (union-find : segment vertical → X commun, horizontal → Y commun ; valeur ancrée aux ports, sinon médiane). Mesuré hard.vsdx : 209 segments biaisés → 21 (reste = vraies diagonales Visio).
  2. **voies** — `_separateLanes()` sépare les segments de flèches parallèles qui se superposent (2-3 flèches empilées sur la même ligne, typiquement en bordure quand plusieurs ports sont alignés) en voies distinctes (GAP 16 px). Segments collés à un port = ancres FIXES (on ne bouge que les segments intérieurs, jamais à travers une forme). Mesuré hard.vsdx : chevauchements (>30 px) 24 → 3.
  3. **labels** — `architectLabels()` place les labels près des pointes SANS jamais les poser là où une flèche en croise une autre (222/243 placés, 0 sur une autre flèche).
- **Curseur global des labels** (remplace le bouton « Agencement auto » ; toolbar, `#label-pos-slider`) : `setLabelsAlongArrows(t)` pose TOUS les labels à la même fraction `t` de LEUR flèche — gauche = origine (source), droite = pointe — en direct. `_pointAlongPath()` donne point + angle ; une marge par flèche évite le chevauchement des formes d'extrémité.
- **Pointes** (au rendu, toujours actif) : `polylineToPath(pts,R,tipPad=18)` (approche droite ≥18 px avant la tête) + `_alignPortApproach()` (dernier segment aligné sur l'axe du port → la tête ne pivote pas).
- **Losanges = vrais nœuds du flux (2026-08-27)** — `tagDecorativeDiamonds()`
  (vsdx_importer). Un losange Visio n'est PAS connecté : il est posé sur les
  flèches, et l'import en faisait un décor. Conséquence : une décision à deux
  sorties donnait **deux flèches complètes** qui redessinaient chacune le tronc
  d'entrée — deux traits presque superposés que rien n'aligne parfaitement.
  Désormais on **coupe** la flèche sur le losange : une entrée, une ou deux
  sorties, tronc unique par construction.
  - **Quelle flèche ?** La couleur de trait Visio (`LineColor` de la forme, sinon
    du master) est le seul signal fiable : les flèches d'une même décision
    partagent une couleur. ⚠️ Le losange lui-même n'a PAS de couleur propre dans
    les fichiers réels (forme « Small If » qui hérite tout de son master) — c'est
    la FAMILLE de couleur la mieux représentée autour de lui qui désigne sa
    décision. Mesuré sur la carto client : 25 losanges sur 28 corroborés par une
    famille de couleur.
  - **On ne coupe que le tronc** : parmi les flèches qui passent à ≤45 px, seules
    celles issues de la MÊME source sont coupées (une flèche isolée exige ≤14 px).
    Couper tout ce qui passe fabriquait des entrées parasites — c'est ce qui avait
    fait abandonner l'ancien `spliceDecisions`, resté désactivé.
  - Le modèle métier n'en souffre pas : `_do_sync` retrouve A → B à travers le
    losange (`decision_upstream`) et absorbe son libellé en `choice_label`.
    Couvert par `tests/test_48_carto_package.py`.
  - Mesuré (banc `tests/carto`) : carto client 12 losanges insérés dans le flux,
    28/28 losanges à ≤0,5 px de LEUR flèche ; hard.vsdx inchangé (croisements
    198 → 197, chevauchements 20 → 19 pour 11 connexions de plus).
  - **Coupe SÉQUENTIELLE** : deux losanges posés sur la MÊME flèche la coupaient
    chacun de leur côté, sur le tracé d'origine → deux demi-flèches concurrentes
    (le doublon visible sur la carto client). Chaque losange travaille donc sur
    les flèches telles qu'elles sont APRÈS les coupes précédentes. Mesuré carto
    client : croisements 52 → 46, chevauchements 15 → 7 (mieux qu'avant l'insertion
    des losanges), hard.vsdx inchangé (198 croisements, chevauchements 20 → 16).
  - **Où couper** : au point de divergence des branches — l'angle droit de la
    décision — mais **seulement s'il tombe sous le losange** (≤45 px). Deux branches
    partagent souvent un long tronc depuis leur source : couper là déplacerait le
    losange à l'autre bout de la carto. Sinon on coupe à l'endroit où Visio a posé
    le losange, et toutes les branches sont coupées au MÊME point (tronc unique,
    90° exact entre les deux sorties).
  - **Aimantation = insertion** (`_snapDiamondToArrow` → `_insertDiamondOnArrow`) :
    lâcher un losange à moins de 14 px d'une flèche le coupe dessus, exactement
    comme à l'import. ⚠️ Un losange posé à la main ne doit PAS rester un décor
    par-dessus la flèche : les liens métier suivent le flux, et deux régimes
    (connecté / décoratif) donnaient des liens différents selon qui l'avait posé.
    La **pop-up de placement** (`_startDiamondPlacement`) branche elle aussi ce
    qu'elle valide — « Valider » comme « Tout garder » : sinon les losanges
    ajustés à la main restaient décoratifs alors que ceux de l'import étaient
    dans le flux. Mesuré carto client : après validation, 28/28 losanges
    connectés, 0 avec plusieurs entrées, croisements 45, chevauchements 4.
  - **Après la coupe, suivre sa flèche** : une flèche coupée disparaît, et les
    losanges qui s'y rattachaient pointaient dans le vide — l'éditeur les
    reposait alors sur « la plus proche », c'est-à-dire n'importe laquelle. On
    re-pointe chaque losange sur la MOITIÉ qui passe encore chez lui, en suivant
    la chaîne quand la moitié a elle-même été recoupée.
  - **Fan-out** : au départ d'une activité, toutes ses flèches sortantes passent
    par le même point — « la plus proche » est un tirage au sort. On pénalise
    (60 px) les candidates dont la projection tombe sur une EXTRÉMITÉ du tracé :
    celle que le losange traverse en son milieu gagne.
  - **Recentrage après retouche** (`_alignDiamondsOnFlow`) : le polish redresse
    les angles et sépare les voies APRÈS l'insertion. Un losange branché n'était
    plus repositionné (seuls les décoratifs le sont) et se retrouvait à côté de
    son propre trait. Chaque flèche qui le touche impose une coordonnée (segment
    vertical → X, horizontal → Y) ; deux passes, car bouger le losange bouge ses
    ports.
  - **Rendu** : une flèche qui ENTRE dans un losange n'a **ni pointe ni marge**
    (`tipPad` 0, pas de `marker-end`) — le flux ne s'arrête pas à la décision, il
    se divise, et toute marge agrandirait la zone sensible autour du losange.
  - Une branche qui SORT d'un losange garde la couleur du flux : sans ça, la
    propagation « couleur de la forme source » repeignait toutes les sorties de
    décision en gris.
- **Losanges décoratifs** (non connectés, posés « sur » une flèche dans Visio sans `<Connect>`) : `spliceDecisions` DÉSACTIVÉ (les insérer dans le flux complexifiait les flèches pour rien). `_seatDecorativeDiamonds()` les repose sur LEUR flèche APRÈS le polish : quand on redresse un angle ou qu'on rejette un tracé en détour, la flèche bouge — le losange, associé au connecteur dont le `customPath` Visio d'origine passe le plus près (seuil 60 px), est reposé sur le tracé FINAL de ce connecteur, à la même fraction. Mesuré hard.vsdx : 17/19 losanges à ≤5 px de leur flèche ; les 2 restants sont VRAIMENT flottants dans Visio (>90 px de tout connecteur) → laissés à leur position Visio. Banc : métrique `deco.offArrow`.
- **Légende de l'export (PDF / SVG uniquement)** — `_buildExportLegend()` +
  `LEGEND_PALETTE` (editor.js). Refaite sur le modèle des cartes Visio AFDEC :
  bandeau d'index « Légende » (`#ebf1df`, filet `#94ac6a`, mention AFDEC©),
  7 formes-témoins commentées (activité, résultat, activité client/fournisseur
  hachurée, activité d'une autre entité, activité communautaire ombrée, renvoi,
  renvoi vers une autre carte), nature des liaisons (trait plein = donnée
  déclenchante, pointillé = nourrissante) + schéma de décision oui/non, et
  surtout la **palette des 30 familles de compétences** relevée dans le Visio
  (`Marketing #820d0d` … `Tutorat #ccc2d9`, 5 colonnes × 6 lignes). Sans elle,
  la couleur d'une activité — l'information principale d'une carto AFDEC —
  n'était expliquée nulle part sur le document imprimé. Bilingue (`legend.*`,
  58 clés/langue). ⚠️ Deux pièges : (1) les `defs` du canevas sont clonées AVANT
  la construction de la légende → sa hachure est déclarée dans ses propres
  `defs` (`#legend-hatch`), pas via `ensureHatchPattern` ; (2) `EXPORT_LEGEND_W`
  (2648 px) élargit la vue de l'export quand la carto est plus étroite, sinon la
  palette serait coupée à droite. N'apparaît JAMAIS à l'écran.
- ⚠️ **Une carto déjà en base ne se corrige pas en corrigeant l'importeur.**
  Les cartos du pilote portaient une bande `#06b6d4` — une couleur de la palette
  de repli `FALLBACK_COLORS`, absente du Visio — parce qu'elles avaient été
  importées AVANT le correctif de `_extractLaneFill`. L'importeur actuel rend
  bien `#ff0000` : c'est la donnée stockée (`Entity.optiqcarto_data`) qu'il faut
  réparer, entité par entité. Fait le 2026-08-30 sur 12 entités du pilote (la
  couleur de bande ne vit QUE dans ce JSON — aucune resynchronisation requise).
- **Couleur des bandes = celle du BANDEAU D'INDEX du couloir Visio**
  (`_extractLaneFill`). Trois défauts corrigés : (1) on gardait « le dernier
  enfant coloré », qui ramenait tantôt le bandeau, tantôt le fond du couloir —
  d'où des bandes qui ne ressemblaient pas au fichier ; on prend désormais
  l'enfant qui PORTE le libellé. (2) Un couloir qui ne redéfinit rien **hérite**
  la couleur de la sous-forme correspondante de son gabarit (`MasterShape` →
  `subFills`) : sans ça la 3e bande de la carto client sortait grise au lieu de
  rouge. ⚠️ `getMasterInfo` s'arrête à la forme primaire (`break` dès qu'il a ses
  dimensions) — les sous-formes se collectent dans une passe SÉPARÉE. (3) Sans
  aucune couleur, on piochait dans une palette de repli (`FALLBACK_COLORS`) : la
  carto affichait des couleurs **absentes du Visio**. Le repli est maintenant
  neutre (`#d1d5db`). Mesuré : carto client 18/18 bandes conformes, hard.vsdx
  14/14 (aucune neutre).
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

## Page Activités & fiche Rôle — points d'attention

- **« Tout ouvrir » / « Tout fermer »** (`display_list.html`) : déplie toutes les
  cartes AFFICHÉES (recherche et pagination comprises), le libellé et l'icône du
  bouton suivent l'état.
- ⚠️ **Statut `Garant` : la casse comptait.** L'import carto écrivait
  `status='garant'` (minuscule) dans `activity_roles`, la page Rôles cherchait
  `'Garant'` — un rôle garant d'après la carte n'apparaissait donc NULLE PART
  dans sa fiche (blocs Activités garant, compétences et savoirs associés).
  Corrigé des deux côtés : l'écriture est capitalisée partout, les lectures
  comparent en `LOWER(...)` (roles_view, export, gestion_rh, roles), et un
  `UPDATE` au démarrage normalise les lignes existantes. `activities_view.py`
  était déjà insensible à la casse — d'où une fiche activité juste et une fiche
  rôle vide, le symptôme trompeur.
- **Provenance de l'activité épinglée** : `/activities/view?activity_id=…` reçoit
  aussi `from=carto|roles`. Le bandeau rouge disait « sélectionnée depuis la
  cartographie » même en venant de la page Rôles ; il dit maintenant la bonne
  origine, et un libellé neutre sans paramètre.
- **Groupes (éditeur)** : le cadre d'un groupe expose 4 **poignées de connexion**
  au survol/sélection (`data-group-port`) — on pouvait viser un groupe avec une
  flèche mais jamais en partir. Le panneau de droite liste d'abord les formes DU
  groupe (« Dans le groupe (n) ») puis les autres (« Ajouter au groupe ») : il
  affichait toute la carto dans l'ordre du modèle.
- **Boutons de bandes** : croix et « + » filiformes sur fond sombre → boutons
  pleins avec icônes (`fa-trash`, `fa-rotate-left`). ⚠️ Le « + » de la liste des
  bandes RESTAURE une bande masquée ; il n'existe pas de création de bande dans
  l'éditeur (les bandes viennent de l'import VSDX).
- **Libellés** : la forme `special` s'appelle **Résultat** (et non plus
  « Sous-activité »), et la marque affichée dans l'éditeur est **Optiq Map**.
- **Gabarit traduit** (bandes pré-créées + textes pré-remplis des formes) :
  chaque bande par défaut porte une `key` (`editor.dband.*`) et chaque forme
  déposée une `labelKey` (`editor.shape_*`). `_applyTemplateI18n(state)` réécrit
  ces libellés **à l'ouverture** de la carto, pas au rendu : `label` part tel quel
  vers `_sync_carto_to_db`, qui ne saurait pas résoudre une clé. ⚠️ Renommer une
  bande (`delete b.key`) ou retoucher le texte d'une forme (`delete s.labelKey`)
  détache définitivement le libellé du catalogue — sinon la saisie de
  l'utilisateur serait écrasée au prochain changement de langue.
- **Deux bandes de gabarit en plus** : `network` / `other` (« Réseau », « Autre »),
  index vert pastel `#A9DFBF` et **corps blanc** via le nouveau champ
  `band.bodyColor` (`renderBands` : `band.bodyColor || bandBgColor(band.color)`).
  Choisir une couleur de bande à la main efface `bodyColor` (le corps redevient
  la version pâle de l'index).
- **Ligne de bande entièrement cliquable** (liste de la barre d'outils) : viser
  un bouton de 26 px pour masquer/restaurer était pénible — un clic n'importe où
  sur la ligne déclenche son bouton, qui n'est plus qu'un repère visuel.
- **Terme produit en anglais = « Map »** (`nav.carto`, `page.carto`,
  `map.card_title`, `carto.save`, toasts éditeur). Les URLs, fichiers et ids
  restent `cartography` : ce sont des chemins, pas de l'affichage.

## Page Activités — ce qui restait en français

Le gabarit initial était traduit, mais tout ce qui est **re-rendu ou construit
ensuite** repassait au français. Trois familles, corrigées ensemble :

- **Fragments re-rendus par le serveur** après un ajout/suppression :
  `softskills_partial.html` et `constraints_partial.html` étaient restés en dur
  (le partial d'origine, lui, était traduit). Une simple action faisait donc
  basculer la liste en français.
- **Niveaux HSC** : la valeur STOCKÉE en base est la chaîne française
  (« 3 (Maîtrise) ») et ne doit jamais être réécrite — seul l'AFFICHAGE suit la
  langue. `hsc_level_label()` (Code/translations.py, exposé aux gabarits par le
  context processor) traduit à la volée ; les `<option value=…>` gardent leur
  valeur d'origine, seul leur texte change. La table `HSC_LEVELS` (CDC 7.2) vit
  maintenant dans `translations.py`, `hsc_positioning.py` la ré-exporte.
- **Messages construits en JS** : l'onglet Temps de la fiche activité
  (`window.ACTTIME_I18N`), les alertes des listes S/SF/Apt/HSC/contraintes
  (`window.CRUD_I18N` + helper `_CR()`), les erreurs de tâches
  (`window.TASK_I18N`), et la modale **Traduire les soft skills** — qui
  RÉÉCRIVAIT le bouton du gabarit avec « Traduire » en dur, et bâtissait les
  en-têtes de son tableau en français.
- ⚠️ **`_CR()` vit dans `optiq_alert.js`**, chargé en premier : ces cinq fichiers
  partagent la portée globale, un `const` répété dans chacun lèverait une
  SyntaxError et couperait tout le script.

## Liste des activités — tâches et outils

- ⚠️ **Ordre des tâches** : `order` seul ne départage pas deux tâches de même
  rang — les lignes sortaient alors dans leur ordre PHYSIQUE, que PostgreSQL
  change après un UPDATE : la tâche qu'on venait de modifier « sautait » dans la
  liste. `id` est désormais le dernier critère de tri (vue liste ET partial).
- **Choix des outils** = liste à cocher (`.tool-picker`, `loadExistingTools`) :
  classée par nom, les outils déjà rattachés sont cochés/désactivés et signalés,
  et on en prend plusieurs sans ctrl+clic. Un outil accompagné d'un fichier
  porte l'icône `fa-file-lines` et un fond ambré (`.tool-badge--file`,
  `.tool-pick--file`), comme les contraintes avec pièce jointe.
- **Deux pièces jointes distinctes** : `Task.file_path` (NOUVEAU, migration à
  chaud `tasks.file_path`) = mode opératoire de la tâche ; `Tool.file_path` =
  notice de l'outil. Le panneau « + outil » n'affichait qu'un dépôt, posé sous la
  liste des outils : on ne savait pas à quoi le fichier se rattachait. Il est
  désormais scindé en deux blocs encadrés (`.tool-form-block`) — outils existants
  d'un côté, création d'un outil ET **son** fichier de l'autre — et le fichier de
  la tâche vit dans les formulaires de tâche (ajout et édition), avec une pastille
  `.task-file-chip` à côté de son nom.
- **Fiche d'un outil** (`openToolCard`, `tasks.js`) : cliquer le badge d'un outil
  dans une tâche ouvre une modale (nom, description, dépôt de fichier) →
  `PUT /gestion_outils/api/tools/<id>`. Sans elle, un outil déjà enregistré ne
  pouvait **plus jamais** recevoir de fichier : le seul dépôt existant servait à
  la création. La modale est construite en JS (pas de gabarit) car
  `tasks_partial.html` est inclus une fois PAR activité. `/tools/all` renvoie
  aussi `description` (le champ de la fiche restait vide sinon).
- Tests : `tests/test_62_task_tool_files.py` (8 cas — création/ajout/retrait des
  deux fichiers, indépendance, renommage sans perte).
- ⚠️ **`static/js/tools.js` est chargé APRÈS `tasks.js`** (`script_loader.html`).
  Il redéfinissait `showToolForm`/`hideToolForm`/`submitTools` : l'ancienne
  version (un `<select>` d'`<option>`) écrasait silencieusement la nouvelle, et
  le sélecteur refait ne s'affichait jamais. Ces doublons ont été retirés — ne
  rien redéfinir dans `tools.js` de ce que `tasks.js` expose déjà.

## Fenêtre de bienvenue — refondue, et le défaut enfin MESURÉ (2026-10-31)

`Code/bienvenue.py` · `Code/routes/templates/welcome_popup.html` ·
`static/welcome_popup.css` · banc `tools/devrun_bienvenue.py` ·
tests `tests/test_127_fenetre_bienvenue.py` (36, 21 cliquets vérifiés rouges).

### ⚠️ Ce que cette section disait, et pourquoi c'était faux

Elle affirmait : « `sessionStorage` est PAR ONGLET […] on mémorise maintenant
dans `localStorage` la signature des nouveautés lues : la fenêtre ne revient que
lorsque le changelog change vraiment ». **L'utilisateur voyait pourtant la
fenêtre revenir.** Mesuré au banc (Playwright, `getItem`/`setItem` instrumentés
avant tout script de page) :

- La garde `localStorage` **tenait bien le cas simple** — dans un onglet ouvert
  par Ctrl+clic, `sessionStorage` est vide (il n'est PAS recopié), la signature
  correspond, la fenêtre ne revient pas. Et elle était présente sur les trois
  branches qui se déploient. La doc n'était donc pas mensongère : elle était
  **incomplète**, et c'est pire — elle fermait l'enquête.
- Elle lâchait par **trois autres chemins**, tous reproduits :

| scénario rejoué | la fenêtre revenait | voile invisible sur la page |
|---|---|---|
| Ctrl+clic, rien d'autre | non | non |
| **la langue change** | **OUI** | oui |
| **`localStorage` refuse d'écrire** | **OUI** | oui |
| `/api/changelog` répond 500 | non | **OUI, définitivement** |

1. **La signature était bâtie sur de la PROSE TRADUITE** (`title` + 40 premiers
   caractères de `desc`), or `changelog.py` sert `title_en`/`desc_en` à une
   session anglaise. Les mêmes trois nouveautés donnaient deux signatures.
   Avec `DEFAULT_LANG = 'en'` et un écran de connexion qui repose la langue à
   l'anglais (`connexion_routes.py`), l'écart arrivait tout seul.
2. **Le `try/catch` autour du stockage n'était pas une protection** : il avalait
   l'échec, et la fenêtre revenait dans CHAQUE nouvel onglet, sans fin.
3. **`#welcome-popup-overlay` valait `display: flex` AU REPOS** (seulement
   `opacity: 0`) et l'affichage dépendait d'un `fetch`. Un changelog en erreur
   laissait donc un voile `inset: 0; z-index: 9999` tendu sur l'application
   entière : **plus un seul clic ne passait, et rien ne se voyait.** Pire que le
   défaut signalé — et les deux pop-ups qui s'enchaînent derrière attendaient
   leur tour indéfiniment.

### Ce qui remplace tout cela : le SERVEUR tranche

Plus aucune décision dans le navigateur. Le processeur de contexte
(`Code/app.py`) injecte `bienvenue` dans tous les gabarits ; `Code/bienvenue.py`
rend `montrer`, les portes, les attentes et les nouveautés. Conséquences :
pas de course, pas de voile au repos, pas de dépendance au réseau.

- **La signature identifie, elle ne décrit pas.** Chaque entrée de
  `static/changelog_user.json` porte un **`id`** stable ; la signature vaut
  `"b1:" + ids joints`, lue sur le fichier **non traduit**. Reformuler un texte
  (ou corriger l'anglais) ne fait plus revenir la fenêtre chez tout le monde.
  ⚠️ Sans `id`, on retombe sur une empreinte du texte français : **toujours
  mettre un `id`** en ajoutant une nouveauté.
- **« Déjà vue » appartient au COMPTE, pas au navigateur** : table
  `welcome_seen` (`user_id`, `signature`, `seen_at`), créée au boot comme les
  autres. C'est la seule chose qui survive à un stockage refusé et à un second
  poste. `POST /api/bienvenue/vue` écrit **la signature du serveur**, jamais
  celle que le navigateur envoie.
- **Le voile naît `display: none`.** ⚠️ Les deux fenêtres suivantes
  (`entity_share_popup.html`, `carto_decision_popup.html`) lisent
  `getComputedStyle(#welcome-popup-overlay).display === 'none'` pour savoir si
  leur tour est venu, et surveillent les attributs `style` et `class`. La
  fermeture DOIT donc reposer `style.display = 'none'` : un test le garde.

### Ce qu'elle montre, et à qui

Tranchée sur maquettes avant d'écrire (canvas « Fenêtre de bienvenue —
3 organisations » : Le seuil / Deux volets / La carte des portes). **Le seuil**
— une colonne qui s'allonge — avait été retenu parce que le contenu varie du
simple au quadruple selon le palier, et que deux volets laissaient une colonne
à moitié pleine pour un `user`. ⚠️ **Arbitrage revu à l'écran : trop haut.**
620 × 780 px chez un administrateur, sous le pli d'un portable. La fenêtre est
passée en **deux colonnes** — l'objection d'origine tenait, elle a été traitée
plutôt que contournée (voir le troisième piège ci-dessous).

Trois blocs : à gauche **ce qui vous attend** (n'apparaît que s'il y a quelque
chose) puis **les nouveautés** — ce qui a CHANGÉ depuis la dernière visite ; à
droite **ce que votre compte ouvre** — la carte des portes, qui ne bouge pas
d'une visite à l'autre. ⚠️ Les nouveautés restent avant les portes dans l'ordre
du DOM : c'est leur changement qui fait APPARAÎTRE la fenêtre, et c'est l'ordre
que retrouvent un lecteur d'écran, le clavier, et le repli en colonne unique.
L'ancien volet « activité récente » (20 événements avec avant/après) est parti :
c'est une page, pas un accueil — `/api/recent-activity` existe toujours.

**Les portes se lisent par `a_le_droit`, jamais par une liste de statuts** : les
droits des trois premiers paliers se règlent depuis la page Comptes, et une
liste figée recommencerait à annoncer des portes fermées. Deux lignes de
plancher (consulter, suivre ses compétences) pour qu'un `user` n'ouvre pas une
fenêtre vide. Deux droits se FONDENT quand ils vont ensemble (« enregistrer »
couvre « proposer » ; « créer » et « modifier » un compte tiennent en une
phrase) : mesuré, un administrateur avait dix lignes et les nouveautés passaient
sous le pli. Compté à l'écran : **user 2 portes, champion 3, coordinateur 7,
administrateur 8**.

### Réouverture

Bouton rond, icône seule, **à côté de la déconnexion** — donc HORS de
`.card-scroll`, et **sans la classe `nav-card`**. ⚠️ Dans cette barre, un
`nav-card` est une PAGE : une entrée parmi les pages aurait fait passer la
fenêtre pour un écran de plus, alors qu'elle se superpose à celui qu'on
regarde. Le logo et la déconnexion vivent déjà dans cette zone qui ne défile
pas : c'est la place des commandes qui ne mènent nulle part. Coût mesuré :
**une carte de page visible en moins au-delà de 1600 px, zéro en deçà** — la nav
défilait déjà et a ses flèches. Le gabarit rend la fenêtre **même fermée**, ce
qui permet de la rouvrir sans seconde voie de rendu en JavaScript — donc sans
second jeu de libellés à tenir.

### ⚠️ Trois pièges d'habillage, tous mesurés

- **La première refonte était illisible : blanche, grise, en tout petit.** Elle
  « collait au design system » au point d'avoir retiré toute couleur — or le
  design system donne une GRAMMAIRE, pas l'ordre d'effacer. Refusée à l'écran,
  reprise avec son bandeau indigo→violet et une pastille d'icône teintée par
  ligne. Une fenêtre d'accueil est le premier écran qu'on voit : elle a droit à
  une présence.
- **Et elle était rendue à 80 %.** `body.pg` / `body:has(.pg-root)` portent
  `zoom: .8` (ui-theme) : un « 13.5 px » y paraît 10,8 px, et la carto (non
  zoomée) montrait la MÊME fenêtre 25 % plus grande qu'ailleurs. La carte porte
  donc `zoom: 1.25` là où le body est zoomé — les deux se compensent, une seule
  densité partout. ⚠️ **Et surtout : pas de `vh` ici.** Les unités de fenêtre
  passent elles aussi par ce zoom — `calc(100vh - 48px)` bornait la carte à
  76 % de la hauteur réelle et coupait les nouveautés. On se mesure sur le
  VOILE (`max-height: 100%`), dont le `inset: 0` couvre bien l'écran entier :
  **mesuré sur neuf pages**, le zoom du body ne casse PAS cette couverture — il
  ne mord que sur les coordonnées calculées en JS (voir le menu du développeur
  de compétences et la bulle du tableau des droits).
- **Puis elle était trop HAUTE.** Même lisible et à la bonne échelle, la
  colonne unique empilait en-tête (160 px) + attentes + nouveautés + portes.
  **La ressource dont on dispose ici, c'est la largeur** — un voile occupe
  l'écran entier, pas une colonne de texte. L'en-tête tient donc sur une ligne
  (identité à gauche, phrase du palier dans un panneau translucide à droite) et
  le corps est une grille de deux colonnes. Mesuré, administrateur FR :
  **620 × 780 → 1000 × 701**, plus de défilement jusqu'en 1280 × 800 (19 px à
  faire défiler en 1280 × 720, le seul cas restant), et la même taille rendue
  sur une page non zoomée. ⚠️ **Le nombre de portes dépend du palier, et la
  mise en page suit** : `.wp-portes` est sur UNE colonne, et passe à deux via
  `:has(.wp-porte:nth-child(4))` — deux colonnes pour les 2 portes d'un `user`
  laissaient un vide à droite qui avait l'air d'un défaut. `auto-fit` ne sait
  pas faire cette bascule : il compte des pixels, pas des éléments. ⚠️ En
  dessous de 900 px de large (largeur RÉELLE : les requêtes média ignorent le
  zoom) tout retombe en une colonne, et le repli doit reprendre le sélecteur
  `:has()` — sinon la règle des quatre portes, plus spécifique, l'emporte.

### ⚠️ Une clé de traduction ne s'ASSEMBLE pas

`tests/test_78_i18n_couverture.py` a attrapé deux fois la même faute ici : une
clé construite par concaténation (préfixe + palier) échappe au contrôle de
couverture, et le jour où un palier s'ajoute sa phrase s'afficherait en clair.
Les quatre clés de palier sont donc écrites en toutes lettres dans
`bienvenue.PHRASE_PALIER`, et la phrase est résolue en Python.
⚠️ **Ce contrôle lit aussi les COMMENTAIRES** : il a ensuite signalé le
commentaire qui citait la forme fautive. Ne pas écrire d'appel de traduction
d'exemple dans un commentaire de `Code/`.

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

### Page Compétences — refonte visuelle (2026-09-15)

Le contenu était juste, l'écran illisible. Deux défauts de structure, chacun avec
une conséquence mesurable :

- ⚠️ **Le tableau principal était un `<table>` à HUIT colonnes en `min-width: 760px`.**
  La colonne de droite fait **870 px CSS** (conteneur plafonné à 1200, moins la barre
  latérale) : le tableau débordait, la page défilait horizontalement, et le bouton
  **« Évaluer » — l'action principale — se retrouvait hors écran**. Remplacé par une
  grille CSS (`.cv2-ligne`), qui aligne les lignes sans imposer de largeur minimale.
  ⚠️ Les points de bascule s'écrivent en px RÉELS, la mise en page en px CSS :
  `body.pg` porte `zoom: 0.8` (ui-theme), et les media queries ignorent ce zoom.
  Le conteneur plafonne dès **960 px réels** — retirer une colonne à 1180 px ne
  servait à rien, rien ne bouge entre 960 et 1440.
- ⚠️ **La notation était SIX barres pleine largeur empilées PAR RÉSULTAT** : 430 px
  chacun, **1266 px de défilement dans une fenêtre qui en montre 644** pour une
  activité à deux résultats. Or le niveau de l'activité est le **MINIMUM** des
  résultats : ne jamais les voir ensemble, c'est rendre la règle incompréhensible.
  L'échelle 0→4 est ordonnée, elle se dessine **en ligne** (5 paliers + une gomme
  « Effacer » à part — effacer n'est pas un niveau de plus). Mesuré après : **685 px
  pour la même activité**, tout tient dans un écran.

**La jauge** (`jauge()`, `.cv2-pas`) remplace les trois colonnes requis / démontré /
écart : quatre pas (niveaux 1 à 4 ; le niveau 0 « Non démontré » est une jauge VIDE,
c'est exactement ce qu'il veut dire), et une **barre verticale après le pas requis** —
« la jauge doit atteindre ce trait ». Un tiret posé SOUS le pas avait été essayé
d'abord : à cette densité il disparaissait. L'écart est une distance, il se regarde ;
ce n'était qu'un nombre à lire. Le badge d'écart ne subsiste que s'il est NÉGATIF
(le cas qui demande une action) — sinon il mangeait la largeur du libellé.

**Bandeau de situation** : quatre compteurs (tenu / en écart / à évaluer / à configurer)
qui sont aussi les **filtres** de la liste. Il n'existait pas — pour savoir où en était
quelqu'un il fallait lire les six lignes une à une.

- ⚠️ **`evidence` était enregistrée et jamais renvoyée.** `/mastery/activity/…` ne
  portait pas la preuve : l'écran rouvrait la zone de saisie VIDE, et le prochain
  enregistrement l'écrasait par une chaîne vide. La preuve se perdait au deuxième
  passage sans que personne ne l'ait effacée. `activity_mastery` renvoie désormais
  `evidence` (toujours une chaîne) et `n_evaluated` — sans ce dernier, un niveau
  global vide ne se distingue pas d'une activité qu'on n'a pas commencée.
- Le `<style>` en ligne (200 lignes dans le `<head>`) devient `static/competences.css`.
  ⚠️ Le lien reste **dans le `<head>`**, à la place exacte qu'occupait le `<style>` :
  `header_buttons.html` charge optiq.css et ui-theme.css depuis le `<body>`, donc
  APRÈS — déplacer le lien change la cascade.
- « Manager » devient **« Développeur de compétences »** dans les libellés de la page.
- Mise au point : `tools/devrun_competences.py` (instance jetable SQLite, port 8125,
  `/devrun/<qui>` pour changer de compte) — un développeur, trois collaborateurs et
  les **six états** que la page doit savoir montrer présents en même temps : sans ça
  on ne regarde jamais que le cas heureux.
- Tests : `tests/test_57_mastery.py::TestPreuveEtAvancement` (4 cas, vérifiés rouges
  sur l'ancien code).

### Page Compétences — deux notes, synthèse, plan de formation (2026-09-15)

**Les deux notes (CDC 3.6) — et le trou de sécurité qu'elles révélaient.**
- ⚠️ **`POST /mastery/evaluate` n'avait AUCUN contrôle d'accès.** Tout compte
  connecté pouvait poser n'importe quel niveau sur n'importe qui — y compris se
  décerner le niveau qui fait foi. Sans grande conséquence tant que seuls les
  développeurs de compétences ouvraient l'écran ; plus du tout dès que les
  collaborateurs y viennent s'auto-évaluer. `Code/competences_acces.py` est la
  source unique : `peut_noter(acteur, cible, evaluateur)` et `peut_lire(...)`.
  Règle : l'auto-évaluation (`eval_number '0'`) ne se pose que sur SOI ; le
  niveau validé (`'1'` garant, `'2'` développeur) par le développeur de la
  personne, ou par un champion/admin. `/mastery/dashboard`, `/mastery/synthese`
  et tout `/plan/*` passent par les mêmes portes.
  ⚠️ `encadre()` regarde les DEUX rattachements (`users.manager_id` global ET
  `user_roles.manager_id` par rôle) : n'en lire qu'un ferait dépendre le droit
  de la FAÇON dont l'affectation a été faite.
- **La page a deux modes**, décidés par un seul appel `GET /competences/contexte` :
  développeur (liste de collaborateurs, pose le niveau qui fait foi, règle le
  requis, ouvre le plan) et collaborateur (se voit lui, pose SON auto-évaluation,
  lit le niveau validé, ne règle rien).
- **Ce qui fait foi reste le niveau du développeur.** `activity_mastery` rend
  aussi `self_global_level` (même règle du MINIMUM, jamais la moyenne) et
  `n_self_evaluated` — mais la synthèse ne remonte jamais l'auto-évaluation comme
  résultat. À l'écran elles ne se ressemblent pas : la note officielle est une
  échelle pleine avec la pastille « fait foi », l'auto-évaluation un contour
  pointillé posé sur le même palier, plus un verdict d'accord (« se situe
  au-dessus / en dessous »).
- ⚠️ **`evidence` par évaluateur** : chacun garde la sienne (`evidence` pour le
  niveau validé, `self_evidence` pour l'auto-évaluation). Les écraser l'une par
  l'autre faisait disparaître la preuve de celui qui n'avait pas enregistré en
  dernier.

**La synthèse — `GET /mastery/synthese/<user_id>`.** On entrait directement dans
le détail d'un rôle : où en était la personne, tous rôles confondus, ne se voyait
nulle part. Une carte par rôle (jauge, compteurs, écart, accès au plan), puis on
entre dans le détail. ⚠️ Le niveau d'un rôle est le MINIMUM de ses activités et
n'existe QUE si toutes sont évaluées — une moyenne partielle laisserait croire
qu'un rôle à moitié noté est tenu. `dashboard_rows()` a été extrait de la route
pour que la synthèse et la liste détaillée comptent avec le MÊME code :
deux implémentations donneraient deux chiffres, ce qu'une vue d'ensemble ne peut
pas se permettre.

**Le plan de formation — `Code/routes/plan_formation.py`, fenêtre dédiée.**
Le partage des rôles est volontaire :
- **l'IA propose le CONTENU** (quelles actions, quelle charge en heures) ;
- **le calcul décide si ça TIENT** : heures/semaine × durée = capacité, somme des
  charges = besoin. Le verdict est arithmétique, local et instantané — les
  curseurs ne rappellent JAMAIS le serveur. Un curseur qui attendrait trois
  secondes une réponse réseau ne serait pas un curseur.
  Bouton « au plus juste » = caler la durée sur `ceil(besoin / heures_semaine)`.
  Un échéancier semaine par semaine montre ce qui déborde.
- Sans clé IA, `_plan_local()` bâtit le plan depuis les **capacités en écart
  relevées en base** (`result_capability_links` via `_linked_capabilities`) : plus
  sec, mais chaque ligne correspond à quelque chose de réel. L'écran dit toujours
  d'où vient le contenu — on ne présente jamais un repli comme une analyse IA.
- Modèle `PlanFormation` (table `plans_formation`), UN plan par couple
  (collaborateur, rôle) : on le reprend, on ne l'empile pas. ⚠️ Un VRAI modèle,
  pas du SQL brut dans une route — `training_plan` et `user_activity_plans` ont
  chacune coûté un 500 en production parce que rien ne les créait sur une base
  neuve. L'ordonnancement n'est jamais stocké : il dépend des deux blocs, un
  chiffre figé mentirait dès qu'on touche un curseur.
- Prompt dans le catalogue (`plan_formation.system`), jamais en dur dans la route.
- ⚠️ `competences_plan.py` / `plan_storage.py` et leurs JS (`plan_formation.js`,
  `synth_competences.js`) sont les vestiges de l'ANCIENNE page : aucun gabarit ne
  les charge. Ne pas les confondre avec ce module.

**Trois défauts d'écran corrigés au passage.**
- ⚠️ **Le niveau requis se réglait par un lien « modifier »** qui dépliait six
  boutons gris minuscules : rien ne disait que c'était réglable, ni qu'il
  s'agissait d'une CIBLE et non d'une note. C'est maintenant un bloc à part
  entière, même échelle que la notation mais **en creux** — une cible se dessine,
  elle ne se remplit pas.
- ⚠️ **Évaluation et Technicité se confondaient** : deux blocs blancs à la suite,
  rien ne disait qu'on changeait de sujet. Ce sont deux AXES distincts (maîtrise
  d'un côté, contexte technique de l'autre) : blocs numérotés, en-tête propre,
  et la technicité en TEAL, pas dans l'accent de la page.
- ⚠️ **L'IA ne disait pas ce qu'elle faisait** : on cliquait « Configurer », ça
  réfléchissait trois secondes, une liste apparaissait. Un panneau l'annonce
  AVANT (ce qu'elle lit, ce qu'elle propose, que rien n'est enregistré sans
  validation), chaque proposition porte sa confiance (`sûr` / `à vérifier` /
  `peu sûr`) et sa justification, et une ligne corrigée à la main le dit.
  `/competences/contexte` renvoie `ia_disponible` : promettre une analyse puis
  servir un repli était exactement le reproche fait à cet écran.

**Tests** : `tests/test_77_competences_deux_notes.py` (28 cas — qui note qui,
ce qui fait foi, la synthèse, le contexte, le plan), les refus vérifiés **rouges**
en retirant le contrôle d'accès.
⚠️ `auth_client` et `client` sont le MÊME objet en portée session : un fichier qui
remet la session à zéro doit la rendre en fin de module, sinon tous les tests
suivants qui comptent sur `auth_client` se retrouvent déconnectés.
Mise au point : `tools/devrun_competences.py` (port 8125) sème aussi des
auto-évaluations volontairement discordantes et des capacités en écart.


### Page Compétences — profil global et lisibilité des deux notes (2026-09-15)

- ⚠️ **`flex: none` sur les en-têtes et pieds de fenêtre.** `.cv2-dh`, `.cv2-ph` et
  `.cv2-df` sont des éléments FLEX d'une colonne plafonnée à 90vh : avec leur
  `flex-shrink` par défaut, un contenu long les **écrase**. Le sous-titre
  (« Untel · Tel rôle ») se retrouvait tranché en deux sous la première section —
  présent à l'écran, illisible. Le symptôme est trompeur : on cherche un
  `overflow` ou un `z-index` alors que c'est la boîte qui rétrécit.
- ⚠️ **Les deux notes avaient deux POIDS VISUELS différents** : le niveau validé
  était une échelle, l'auto-évaluation une ligne de texte minuscule en dessous —
  on ne savait plus laquelle était laquelle, et la seconde avait l'air d'un
  commentaire de la première. Elles portent désormais le MÊME objet (l'échelle
  0→4) et se distinguent par une identité tenue partout :
  **niveau validé = bleu (accent de page) + écusson + « fait foi »**,
  **auto-évaluation = violet `--cv-auto` + silhouette**. Celle qui vous
  appartient se clique, l'autre est posée (`.is-posee`, boutons `disabled`).
  ⚠️ **L'ordre ne bouge jamais** — celle qui fait foi d'abord, quel que soit le
  regard : on sait toujours où regarder. ⚠️ `saveEvaluation` cible
  `.cv2-nt.is-mienne [data-lv].sel` : la carte porte deux échelles, un
  `querySelector` non qualifié ramènerait celle du développeur jusque dans
  l'enregistrement d'un collaborateur.
- **Moins de petit texte.** Le standard minimal d'un résultat n'est plus écrit
  (deux lignes par résultat, autant que de résultats) : il reste au survol du nom,
  signalé par un « ? ». La description du bloc « niveau attendu » a sauté — le
  titre et l'échelle disent tout.
- **La vue d'ensemble porte un PROFIL** (`GET /mastery/synthese` enrichi) :
  nombre de rôles, d'activités, **taux de couverture**, un **radar SVG dessiné à
  la main** (un axe par activité, requis en contour vert / démontré en surface
  bleue) et une barre par rôle. Sans lui l'écran n'était qu'une rangée de portes.
  - ⚠️ **`couverture()` ne compte que les activités ÉVALUÉES.** Compter une
    activité non évaluée comme un zéro confondrait « pas démontré » et « pas
    encore regardé » — la distinction que tout le module tient (NULL ≠ 0). Le
    nombre d'évaluées est renvoyé à côté pour lire le taux avec sa base.
  - ⚠️ **Chaque activité est plafonnée à SON requis** (`min(dem, req)`) : sans ce
    plafond, un expert sur une activité masquerait une lacune sur une autre et on
    afficherait 100 % en étant en écart.
  - ⚠️ **Le radar ne trace QUE les activités évaluées** : posées à 0, elles
    effondraient le polygone vers le centre — le graphe disait « rien de
    démontré » là où la vérité est « pas encore regardé ». Une note sous le
    graphe dit combien sont absentes. Plafonné à 12 axes (les plus en écart, le
    serveur trie par écart croissant) ; sous 3 axes, pas de radar.
  - ⚠️ **Une activité portée par deux rôles ne compte qu'une fois** dans le
    profil : sinon la forme dirait surtout combien de rôles se la partagent.
  - Aucune bibliothèque de graphes : elle se paierait à chaque chargement de page
    pour dix polygones.
- **La carte de rôle entière s'ouvre** (et au clavier) : elle se soulevait au
  survol, promesse que seul le bouton « Ouvrir » tenait. ⚠️ Le bouton « Plan de
  formation » fait un `stopPropagation` — sans lui on ouvrait le rôle DERRIÈRE la
  fenêtre du plan. Les lignes « par rôle » du profil ouvrent le rôle elles aussi.
- Tests : `tests/test_77_competences_deux_notes.py::TestCouvertureEtProfil` (6 cas).

⚠️ **« Pourquoi j'ai perdu mes données de notation ? » — DEUX PÉRIMÈTRES DANS LE
MÊME ÉCRAN.** Rien n'était perdu. `synthese` listait **TOUS** les rôles du
collaborateur, toutes cartos confondues (`UserRole.query.filter_by(user_id=…)`,
sans entité), tandis que `dashboard_rows` filtre les activités sur
`Activities.entity_id == Entity.get_active_id()`. Changer de carto active — ce
que font la page Cartographie **et le sélecteur de la page RH**
(`api_tableau` pose `session['active_entity_id']`) — affichait donc les rôles
d'une carto avec les activités d'une AUTRE : « 0 activité » sur chaque rôle,
« — du requis tenu », et l'écran paraissait vidé de ses évaluations.
Un rôle qui ne PEUT PAS porter d'activité sur cet écran n'a rien à y faire : la
synthèse ne retient plus que les rôles de l'entité active. Reproduit puis
vérifié par `TestPerimetreDeLaSynthese` (2 cas, le premier **rouge** avant le
correctif — `activities: []`, tous les compteurs à zéro, exactement la capture
rapportée).
### Le radar cède la place au détail d'un rôle (2026-09-16)

Le radar répond « quelle est la FORME du profil ». Il ne répond pas « sur quelle
activité ce rôle décroche » : il superpose requis et démontré de TOUTES les
activités, et un rôle n'y est qu'une teinte au survol. **Cliquer un point ouvre
donc les barres de SON rôle**, au même endroit — une ligne par activité, la
cible marquée sur la piste. Remplacer plutôt que juxtaposer garde l'attention là
où elle était.

- ⚠️ **Le détail NE PEUT PAS se reconstituer depuis `profil`** : cette liste est
  **dédupliquée par activité** (une activité portée par deux rôles n'y figure
  qu'une fois, attribuée à l'un d'eux) — la filtrer par rôle en perdrait
  silencieusement. Chaque rôle de `/mastery/synthese` porte donc sa propre liste
  `activities`, complète.
- ⚠️ **La couleur vient du SERVEUR** (`color_for`, CDC 3.5), pas d'un calcul en
  JS : deux implémentations d'un même verdict finissent par diverger, comme
  `dashboard_rows` l'a déjà montré pour les compteurs.
- ⚠️ **Une activité non évaluée n'a PAS une barre à zéro** : zéro veut dire
  « non démontré », et tout le module distingue les deux (NULL ≠ 0). Elle écrit
  « non évalué » à la place de sa barre.
- Les deux vues vivent dans la MÊME zone (`.cv2-radar-zone[data-vue]`), les
  barres en `position: absolute` par-dessus : dans le flux, la hauteur de la
  carte sauterait à chaque bascule. Le retour vide le contenu **après** la
  transition — le retirer tout de suite ferait disparaître les barres d'un coup
  au lieu de les laisser s'effacer. Tout est désactivé sous
  `prefers-reduced-motion`.
- L'entrée des barres est échelonnée (`--i`, 45 ms) : on LIT la comparaison au
  lieu de la découvrir d'un bloc.
- ⚠️ Mise au point : dans un volet navigateur qui ne peint pas, une transition
  CSS **ne progresse pas** — `getComputedStyle` rend alors la valeur figée en
  cours de route (opacité 0 alors que `data-vue` vaut déjà `radar`). Couper la
  transition et relire donne la valeur CIBLE : c'est le seul moyen de distinguer
  un vrai défaut de CSS d'un volet endormi.

**Page RH** : la phrase « Tous les comptes sont des collaborateurs, quel que soit
leur statut » est retirée du bloc Personnes (et sa clé `rh.block_people_sub` du
catalogue). Elle expliquait un choix d'implémentation, pas ce que l'écran montre.

ℹ️ **Le sélecteur de carto de la page RH existe déjà** — bandeau du haut,
`gestion_rh.js::rendreBandeau`, visible dès qu'un compte a **plus d'une** entité
accessible. Il passe `?entity_id=` à `/gestion_rh/api/tableau`, qui valide la
demande contre `Entity.accessible(moi)`. ⚠️ Il pose AUSSI
`session['active_entity_id']`, et c'est nécessaire : les écritures de la page
(créer un rôle, affecter un collaborateur) lisent `get_active_entity_id()` —
changer l'affichage sans changer l'entité active enverrait les modifications
dans la mauvaise carto.


### Qualification des sorties, technicité, radar vivant (2026-09-15)

- ⚠️ **L'écran de qualification ne disait pas ce qu'il demandait.** Un menu
  déroulant « À qualifier » posé à droite d'un nom, et parfois un champ
  pré-rempli d'un « 100 % » que rien n'expliquait. On ne voyait pas qu'il y avait
  un choix à faire, et « Valider » refusait **après coup**, avec un message
  affiché tout en haut de la fenêtre — loin du bouton, loin de la ligne à
  corriger (`prepend` sur `.cv2-bloc`, donc AU-DESSUS de l'en-tête du bloc).
  Trois corrections, toutes de même nature — rendre la décision VISIBLE :
  1. les quatre natures sont des **boutons**, plus un `<select>` ;
  2. celle qu'on choisit **s'explique** juste en dessous (`q_dit_*`) ;
  3. le champ du standard porte son libellé et **dit d'où vient sa valeur**
     (« Proposé par l'IA à partir de l'activité — corrigez-le si besoin »).
  Et « Valider » ne refuse plus : il reste **éteint** tant qu'aucun résultat
  n'est marqué, avec un compteur sous les sorties qui dit ce qui manque.
  Recliquer la nature déjà choisie la retire — sinon on ne pouvait plus revenir
  à « pas encore décidé » une fois un bouton touché.
- **La technicité passe en BLEU PLEIN** (bandeau, texte blanc). Elle était en
  teal, qui se lit comme du vert et entrait en conflit avec le vert sémantique
  « niveau tenu ». Le bandeau la sépare franchement de l'évaluation tout en
  restant dans le bleu de la page.
- ⚠️ **Tailles de police des fenêtres.** L'app est calibrée à 80 %
  (`body.pg { zoom: .8 }`, ui-theme) : un « 12 px » y est rendu à moins de 10.
  Dans une fenêtre où l'on décide d'un niveau, c'est trop petit. Les tailles
  secondaires des **fenêtres seulement** sont remontées d'environ 1 px — pas
  celles des listes de la page, qui garderaient leur densité.
- **Le radar devient vivant** (`animerProfil`) : survoler une **légende** met sa
  couche au premier plan (on estompe l'autre — le SVG n'a pas de `z-index`, et
  réordonner les nœuds ferait clignoter) ; survoler un **rôle** allume ses axes,
  éteint les autres et affiche ses deux niveaux ; survoler un **axe** donne le
  nom complet, le rôle et les deux niveaux dans une bulle.
  ⚠️ **On ne zoome pas** sur le rôle survolé : agrandir déplacerait les deux
  polygones, et c'est justement leur superposition qu'on est venu lire.
  ⚠️ Les noms d'activité sont longs : coupés à 16 signes, la zone sensible d'un
  axe est un trait transparent de 26 px du centre au bord (viser une étiquette
  de 10 px serait pénible), et le nom entier vit dans la bulle. Un libellé
  complet gravé dans le SVG déborderait quoi qu'on fasse.
- ⚠️ **La fenêtre « Désigner le rôle garant »** (page Liste des activités) était
  restée à l'état d'ébauche : treize lignes de HTML avec leurs styles EN LIGNE
  (`top:20%; left:30%`), des libellés **en dur en français** et des `alert()`
  pour les erreurs. Elle reprend le patron de modale de la page
  (`.modal-*-propose`), passe par le catalogue (`garant.*`, 10 clés × 2 langues)
  et écrit ses refus DANS la fenêtre — une alerte système ferme le contexte au
  moment précis où on a besoin de le relire pour corriger.
  ⚠️ `.hidden` n'existait **nulle part** dans `activities_list.css` : la classe
  ne masquait rien. Déclarée à côté de ce qui s'en sert.

### Qualification : la décision est binaire, pas un menu à quatre entrées (2026-09-15)

- ⚠️ **« À quoi servent les trois autres boutons ? »** La question était juste :
  quatre natures présentées au MÊME RANG, dont une seule ouvrait la suite et
  débloquait l'enregistrement — les trois autres semblaient ne mener nulle part.
  Or la décision est **binaire** (cette donnée démontre-t-elle la tenue de
  l'activité ?) et les trois autres ne font que **ranger** ce qui n'en est pas.
  La hiérarchie visuelle dit maintenant la hiérarchie réelle : un grand bouton
  « Oui — c'est un résultat de l'activité » portant son explication, puis
  « Sinon, rangez-la : » avec les trois autres en petites pastilles, et la phrase
  qui manquait — « ces trois natures sont enregistrées avec l'activité, mais ne
  donnent pas lieu à évaluation ».
- ⚠️ **Le panneau « Ce que l'IA fait ici » restait affiché APRÈS l'analyse.** Un
  texte qui décrit une action déjà faite se relit en cherchant ce qu'il reste à
  comprendre. Avant, le panneau ANNONCE ; après, il REND COMPTE (combien de
  sorties examinées, combien de résultats proposés, et que rien n'est encore
  enregistré) — fond vert, icône de presse-papiers : on voit que l'étape est
  passée.
- ⚠️ **L'info-bulle du radar se posait TOUJOURS au même endroit.** On survolait
  un point à gauche et l'explication surgissait en haut au centre, sans rien qui
  relie l'une à l'autre. `poserBulle()` la place près de l'élément survolé, en la
  bornant au cadre, et bascule sous le point quand il n'y a pas la place
  au-dessus. ⚠️ Les coordonnées d'un nœud SVG sont dans le repère du **viewBox** :
  on passe par `getBoundingClientRect`, seul comparable aux pixels de la zone.
  Une bulle de rôle, elle, parle de l'ensemble : elle reste centrée.
- **La technicité est bleue en ENTIER**, plus seulement son en-tête : un bandeau
  coloré au-dessus d'un contenu blanc laissait croire que ce qui suit est hors de
  la section. Les contrôles restent blancs — un champ translucide sur fond bleu
  ne se lit plus dès qu'on y saisit quelque chose — et les pastilles d'écart
  gardent leurs couleurs sémantiques. Le texte d'explication a sauté : le
  bandeau et les deux colonnes « Requis / Démontré » disent la même chose.

### CONFIGURER n'est pas ÉVALUER — et où l'IA intervient vraiment (2026-09-15)

**Où l'IA intervient, une bonne fois.** Elle est appelée à DEUX endroits, et
jamais ailleurs :

1. **la configuration d'une activité** — `/qualify/analyze` propose la NATURE de
   chaque donnée produite, puis `/competence/generate` et
   `/competence/result_links/generate` en dérivent la compétence et ses liens ;
2. **le plan de formation** — `/plan/proposer`.

⚠️ Elle ne touche **jamais** `mastery_level`. Aucune route IA n'écrit un niveau :
les notes sont posées à la main, par le développeur de compétences ou par le
collaborateur pour son auto-évaluation.

- ⚠️ **Mais l'écran disait le contraire.** La qualification des sorties s'ouvrait
  DANS la fenêtre d'évaluation, sous le nom du collaborateur et sous le titre de
  son activité : l'IA avait donc l'air de participer à la notation. C'était une
  faute de RANGEMENT, pas de code. Deux fenêtres désormais :
  - **« Configurer l'activité »** — en-tête ardoise, sous-titre = le nom de
    l'activité, **aucun nom de personne** : configurer ne regarde personne, et
    se fait une fois pour toutes, pas par collaborateur ;
  - **évaluer** — en-tête bleu, sous-titre = « Untel · Tel rôle », et **plus une
    seule trace d'IA**. Une activité sans résultat qualifié y affiche pourquoi
    il n'y a rien à évaluer, avec un bouton vers l'autre fenêtre.
  ⚠️ On ne bascule PAS automatiquement de la configuration à l'évaluation une
  fois validée : enchaîner d'office redonnerait à l'ensemble l'air d'un seul
  parcours, ce qu'on vient précisément de séparer. L'écran de fin propose les
  deux sorties.
- ⚠️ **L'écran et le plan ne s'accordaient pas sur le mot « écart ».** L'écran
  compte une activité en écart dès que le niveau démontré est sous 2 (l'autonomie
  n'est pas démontrée, requis ou pas) ; `contexte_ecart()` filtrait sur
  `gap < 0`, or `gap` est NUL quand le rôle n'a fixé aucun niveau requis. Le
  bouton « Plan de formation » s'affichait donc, et la fenêtre répondait « aucun
  écart sur ce rôle ». Les deux passent maintenant par `categorie_activite()`,
  et à défaut de requis la cible du plan est le **seuil d'autonomie**
  (`SEUIL_AUTONOMIE = 2`).
- **Un plan ne se bâtit que sur du MESURÉ** : une activité non évaluée — ou
  évaluée à moitié — n'entre jamais dans un plan. Ce n'est pas une activité en
  retard, c'est une activité qu'on n'a pas regardée.
- ⚠️ « IA non configurée » héritait du **vert** du panneau de bilan : une absence
  de clé prenait l'apparence d'une analyse réussie.
- Tests : `tests/test_77_competences_deux_notes.py::TestLePlanSuitLEcran` (3 cas,
  le désaccord vérifié **rouge** en remettant l'ancien filtre).
### Moins de phrases, plus de place pour ce qui compte (2026-09-15)

**Cinq phrases retirées.** Chacune expliquait ce que l'écran montre déjà —
« Fixez, pour chaque résultat, le niveau tenu… » au-dessus d'une échelle 0→4,
« Ce que les rôles exigent, et ce qui est tenu » au-dessus d'un radar légendé
« Requis / Démontré », « Calculé sur les seules activités évaluées… » sous des
barres qui portent déjà « 4 activités évaluées sur 6 ». Elles occupaient la
place de ce qu'on vient vraiment lire. Sont parties : `eval_hint`,
`eval_hint_self`, `p_sub`, `p_basis`, `p_not_plotted*`, `r_partial` (194 clés
par langue, contre 197).

- ⚠️ **L'explication d'une activité tenait une LIGNE sous son nom**, tronquée et
  grise : illisible, mais elle volait la place de « évalué le 15/09/2026 », qui,
  lui, se lit vraiment. Elle attend maintenant derrière un « i » (`brancherInfo`,
  `.cv2-i` / `.cv2-info`), au survol **comme au clic** — le survol seul n'existe
  pas sur un écran tactile. La date d'évaluation passe de 11,5 à 13 px.
  ⚠️ La carte est posée sur le **body** en `position: fixed`, pas dans la ligne :
  la liste des activités a son propre défilement, une carte posée dedans serait
  tronquée. Conséquence : elle survit à la disparition de son bouton — elle
  restait affichée en plein milieu de l'écran suivant. `fermerInfos()` est donc
  branché sur tout ce qui déplace ce qu'il y a dessous (clic ailleurs,
  défilement en capture, redimensionnement). ⚠️ Le clic du bouton fait un
  `stopPropagation` : sans lui, ouvrir la bulle la refermerait aussitôt, et le
  clic ouvrirait le rôle derrière.
- **La compétence principale est le SUJET de la fenêtre**, pas une note de bas
  de page : tout ce qu'on va noter en découle. Elle était écrite en 13 px gris
  sur un fond à peine teinté, entre deux sections blanches. Elle porte
  maintenant la couleur de la page en aplat, un liseré d'accent, son icône, et
  16 px.
- **La jauge grossit** : pas de 16×11 → 21×14 px, colonne de la liste 256 → 272.
  ⚠️ En fenêtre étroite (< 980 px) elle redescend à 18×12 — à pleine taille elle
  chasse le libellé du palier hors de sa colonne. ⚠️ Même cause dans les blocs :
  le bilan de section perdait « Autonome / compétent » (138 px de texte pour 85
  disponibles) — le libellé passe à la ligne sous la jauge plutôt que d'élargir
  le bilan, qui aurait mangé le titre de la section.
- **Titre et sous-titre côte à côte** (fenêtre d'évaluation ET fenêtre du plan).
  Ce ne sont pas un titre et sa légende : l'activité d'un côté, la personne et
  son rôle de l'autre, deux informations de même rang. Côte à côte, les deux
  peuvent grossir (16 → 19 px, 12,5 → 14 px) ; le rôle devient une pastille.
  Sous 760 px réels le filet de séparation saute, sinon il se retrouve à gauche
  d'une ligne repliée.
- **Le niveau lu passe à DROITE des paliers** (bloc 1) : sous l'échelle, il
  poussait tout le bloc vers le bas pour une ligne de texte.
- ⚠️ **Un simple filet séparait les blocs 1 et 2** : deux étendues blanches à la
  suite, on ne voyait pas où l'une finissait. Le 3 se distinguait déjà (bleu
  plein). Les trois portent donc chacun SA surface — la cible sur fond neutre,
  ce qu'on note sur fond clair cerclé d'accent (`.cv2-bloc--eval`), la
  technicité en bleu — et le filet a disparu.

**La liste des capacités du diagnostic affichait « — / — » sur chaque ligne.**
Deux nombres que RIEN dans l'application ne remplissait : `required_level` ne se
posait qu'à la **création** du lien (`upsert_result_link`), et les liens
naissent de l'IA — on cherchait donc dans cet écran un réglage qui n'existait
nulle part. Le payload `{link_id, required_level}` règle désormais le niveau
requis d'un lien existant (`null` pour revenir à « non défini » : sans ce
retour, une cible posée par mégarde ne s'enlevait plus). ⚠️ Le lien est filtré
sur `activity_id` : son id vient du client, il ne doit pas suffire à écrire sur
l'activité d'à côté.
Le niveau **démontré**, lui, dit en toutes lettres qu'il n'est **pas mesuré** —
`_capability_demonstrated` lit de vieilles lignes `CompetencyEvaluation`
(`savoirs` / `savoir_faires` / `hsc`) que la page V1.1 n'écrit jamais. Un tiret
laissait croire à une valeur manquante ; c'est une valeur qui n'est pas prise.
Le plan, lui, n'en souffre pas : `_plan_local()` retombe sur l'écart de
l'activité quand celui de la capacité est nul.
Tests : `tests/test_56_result_capabilities.py::TestReglerLeNiveauRequis`
(5 cas, vérifiés **rouges** en retirant le bloc `link_id`).

**La section 2 passe en bleu pastel**, ses cartes de résultat restant blanches :
c'est le contraste entre les deux qui fait ressortir chaque activité à noter.

⚠️ **Et cela a révélé que `--pg-accent-soft` rend du GRIS sur TOUTE
l'application.** Les quatre dérivés — `--pg-accent-soft`, `-softer`, `-border`,
`-glow` — sont déclarés sur `:root` dans `ui-theme.css`, où `--pg-accent` vaut
encore le gris par défaut `#64748b`. Une propriété personnalisée est résolue là
où elle est **déclarée**, pas là où elle est employée : `.page--competences` (et
les huit autres classes de page) ne redéfinissent que `--pg-accent` et
`--pg-accent-deep`, donc les dérivés gardent le gris de la racine. Mesuré dans
la fenêtre d'évaluation : `--pg-accent` = `#2563eb`, mais `--pg-accent-soft` =
`color-mix(in srgb, #64748b 10%, #ffffff)`.
Conséquence visible : sur chaque page, les fonds doux, les bordures d'accent, le
halo des ombres et les survols de ligne sont gris au lieu de la couleur de la
page — alors que tout ce qui passe par `var(--pg-accent)` **dans la règle
elle-même** (y compris un `color-mix` écrit sur place, comme `.cv2-nt--off`) sort
bien en couleur. D'où l'aspect panaché : la carte « niveau validé » est bleue,
la pastille du niveau lu est grise.
`.cv2-bloc--eval` écrit donc son mélange dans la règle. **Le correctif de fond —
déplacer les quatre dérivés dans chaque classe `.page--*` — n'est PAS fait** :
il rendrait sa couleur à chaque page d'un coup, ce qui se décide en regardant
les neuf pages, pas depuis celle-ci.


### Le plan de formation : un PARCOURS, pas une pile de cartes (2026-09-18)

Le panneau de droite (curseurs, verdict, échéancier) plaisait : c'est lui qui
rend le plan modulable. La liste de gauche, elle, ne se comprenait pas. Quatre
défauts, tous corrigés dans `competences_v2.js` (`renderActions` et suivantes) :

- ⚠️ **Les actions de toutes les activités étaient MÊLÉES** dans une seule pile,
  et l'activité visée n'était qu'un mot gris perdu dans la ligne de méta. On ne
  savait pas POURQUOI une action était là. Une section par activité, avec
  l'écart qu'elle vient combler en toutes lettres (« En acquisition →
  Maîtrise étendue ») et son sous-total.
- ⚠️ **Rien ne disait l'ORDRE ni le MOMENT.** L'IA ordonne ses actions (« ce qui
  conditionne le reste d'abord ») et l'échéancier remplit les semaines dans cet
  ordre — mais la liste n'était pas numérotée et ne disait pas quand chaque
  action tombait. Les étapes sont numérotées sur un rail, et chaque carte porte
  ses semaines (`planning()`, le MÊME remplissage que l'échéancier) — en rouge
  quand elle dépasse la durée visée. Survoler une étape allume SES semaines
  dans l'échéancier : la liste et les curseurs parlent enfin du même temps.
- ⚠️ **Chaque carte posait sur une même ligne, sans étiquette**, un type
  minuscule, un champ d'heures et le nom de l'activité. La carte a désormais
  trois zones qui ne se mélangent plus : la nature (pictogramme + couleur) et
  la charge en tête, l'action, puis des champs ÉTIQUETÉS (Objectif, Livrable,
  Réussi quand) — seuls ceux qui sont remplis. Le **livrable** que l'IA fournit
  n'était jamais affiché.
- **La charge se présente comme un réglage** (− valeur +, pas adapté à l'ordre
  de grandeur) : c'est elle qui nourrit le besoin, à droite.
- Une **barre de répartition** par nature (situation de travail, accompagnement,
  formation) sert aussi de légende des couleurs — et montre d'un coup d'œil la
  règle du CDC : un écart se comble d'abord en situation.

⚠️ **Le regroupement garde l'ordre de PREMIÈRE apparition** (`ordonner()`), pas un
tri par écart : trier déferait la séquence proposée. Il est appliqué au
chargement et à la proposition, donc l'ordre affiché, l'ordre enregistré et
l'ordre des semaines sont le même.
⚠️ Ce qui dépend des heures (semaines, sous-totaux, répartition) se met à jour
**sur place** (`majEtapes`) : réécrire les cartes à chaque frappe ferait perdre
le curseur du champ qu'on tape. Et le champ se corrige à la SORTIE, pas pendant
la frappe — effacer « 12 » pour taper « 8 » passerait sinon par un « 1 » imposé.
⚠️ **`competences.css` déclare `header { position: sticky }` pour TOUTE la
page.** Un `<header>` d'en-tête de groupe collait donc en haut de la fenêtre et
passait par-dessus les cartes au défilement : l'en-tête est un `<div>`.

**Le plan construit SANS IA disait deux fois la même chose** (`_plan_local`) :
« Combler : Arbitrage », puis « Objectif : HSC — Arbitrage ». Désormais :
- le titre dit l'action, et la nature suit la famille de capacité
  (`NATURE_PAR_CAPACITE` : un savoir s'apprend → Formation ; un savoir-faire et
  une HSC se travaillent avec un appui → Accompagnement) ;
- l'objectif dit le RÉSULTAT qui réclame la capacité (`_capacites_en_ecart`
  garde désormais `resultat`) ;
- la mise en situation porte les **standards des résultats** comme critère —
  un par ligne — et **ces résultats comme livrable**. ⚠️ Le standard n'est PAS
  recopié sur chaque capacité : il se lisait trois fois de suite, et laissait
  croire qu'une formation suffit à le tenir. Il se vérifie en situation.
- En anglais, plus de guillemets français dans les champs construits.

Tests : `tests/test_77_competences_deux_notes.py::TestLeRepliDitQuoiFaire`
(8 cas, 6 vérifiés **rouges** sur l'ancien repli). Suite : 2348 passés. Éprouvé
dans les deux langues sur `tools/devrun_competences.py`, avec le repli ET un
plan de forme IA (actions mêlées entre deux activités, livrables, critères) :
regroupement, +/−, frappe, retrait, curseurs, « caler », enregistrement relu.


### « Configurer l'activité » : une question, pas un cours de méthode (2026-09-18)

« Je ne comprends pas ce qu'on est en train de faire, pourquoi tu me parles
d'une sortie, après on peut rentrer du texte on ne sait pas pourquoi. » Le
reproche était exact : l'écran s'appelait « Qualification des sorties », et
chaque ligne empilait une question (« Cette donnée démontre-t-elle la tenue de
l'activité ? »), un grand bouton avec sa phrase, « Sinon, rangez-la : » et trois
pastilles avec encore une phrase — sept bouts de texte par ligne, sous un
paragraphe de trois lignes sur l'IA.

⚠️ **Et la moitié de ce qu'on demandait ne servait à RIEN.** Seule la nature
`RESULT` est lue quelque part (`mastery`, `diagnostic`, `result_capabilities`) ;
Mesure, Événement et Information ne sont lues par AUCUN code. On faisait classer
à l'utilisateur ce que personne ne lit. La décision réelle est binaire.
`tests/test_51_qualify_outputs.py::test_seule_la_nature_RESULTAT_est_lue_par_l_application`
le tient : le jour où une autre nature sert, l'écran devra la redemander.

**L'écran pose désormais UNE question** — « Sur quoi jugerez-vous cette
activité ? » — suivie d'une phrase qui dit aussi à quoi sert le champ de texte
(« …puis dites à quoi on voit que c'est réussi : c'est le repère de
l'évaluation »). Puis :
- **« Ce que l'activité produit · les flèches qui en partent sur la carte »**,
  une liste à cocher. ⚠️ « Sortie » est un mot de méthode : chaque ligne est
  montrée comme la FLÈCHE qu'elle est, avec sa destination (« → vers « Chiffrer
  l'offre » »). `/qualify/outputs` renvoie `vers` et `sans_libelle` — une flèche
  sans libellé n'a pour nom que sa destination, affichée telle quelle on lirait
  que l'activité « produit » une autre activité : elle devient « Flèche vers … ».
- **Un seul champ, « Réussi quand… »**, et seulement pour ce qui est coché (il
  prend le focus au moment où on coche). Un champ offert à côté d'une case
  vide ne disait pas à quoi il servait.
- **L'IA en une ligne** (« L'IA a pré-coché ce qui lui semble juste. Vérifiez
  avant d'enregistrer. ») et une étiquette « IA » sur ce qu'elle a coché — en
  ambre « à vérifier » quand elle doute, sa justification au survol.
- ⚠️ **Ce qui est ENREGISTRÉ l'emporte sur la proposition** : rouvrir la fenêtre
  ne laisse pas l'IA revenir sur un choix fait par quelqu'un. Et une ligne
  décochée garde sa nature d'avant (`data-autre`) : l'écran ne la montre plus,
  ce n'est pas une raison de l'effacer.
- **Le compte vit dans le pied**, à côté du bouton qu'il conditionne
  (« 1 élément retenu », ambre au-delà de trois : l'activité en regroupe
  peut-être plusieurs). « Enregistrer » reste éteint tant que rien n'est coché.
- **L'écran de fin MONTRE ce qui a été produit** — la compétence rédigée et
  « Elle sera évaluée sur » avec chaque repère — au lieu de deux phrases qui
  disaient que c'était fait.
- La liste des activités disait « sorties à qualifier » : elle dit « pas encore
  configurée ».

Retirés : `panneauIA`, 35 clés de catalogue par langue (`q_*`, `ia_qualify_*`, `ia_done_*`,
`need_result`…) et ~176 lignes de CSS mort de TROIS générations du même écran
(`.cv2-qz`, `.cv2-oui`, `.cv2-sinon`, `.cv2-nature*`, `.cv2-qstd`, `.cv2-setup`,
`.cv2-natsel`…). ⚠️ Mise au point : dans le volet navigateur qui ne peint pas,
les transitions CSS restent figées en cours de route — la case cochée paraissait
vide et le bouton éteint alors que leurs styles calculés étaient justes. Couper
les transitions avant la capture.

Tests : `test_51` (+2 : la destination de chaque flèche, et le garde-fou
ci-dessus). Suite : 2350 passés. Éprouvé dans les deux langues, sans IA ET avec
une réponse d'IA simulée (pré-cochage, doute, repères proposés, décocher,
enregistrer, relire en base).


### Compétences et Gestion RH en anglais : ce qui échappait aux catalogues (2026-09-18)

Vérification demandée après les refontes de la journée. **Les catalogues
étaient complets** : 202 libellés × 2 langues dans `competences_v2.js`, 84 clés
injectées dans `GRH_L`, toutes présentes en FR et en EN (`test_78` le tient
déjà). Ce qui restait en français, c'est ce qui NE passe PAS par une clé — et
qu'on ne trouve qu'en parcourant les écrans en anglais. Méthode : un détecteur
injecté dans la page, qui cherche les 1 028 phrases françaises des catalogues
(celles dont l'anglais diffère) plus les accents et mots-outils français dans le
texte ET les attributs (`title`, `aria-label`, `placeholder`), passé sur chaque
écran et chaque fenêtre — profil, radar et ses bulles, liste, évaluation (vue
développeur et vue collaborateur), preuve, diagnostic, capacités, plan de
formation, configuration ; et côté RH chaque section, le menu du développeur,
les fiches personne / rôle / cartos, le nouveau rôle, le calendrier, la matrice
des droits (administrateur ET coordinateur).

Corrigé :
- ⚠️ **Le rôle système « Développeur de compétences »** est créé en français
  pour chaque entité : l'interface anglaise l'affichait tel quel partout où les
  rôles sont listés. `role_i18n.nom_affiche(role, lang)` : le rôle système vient
  du catalogue (`rh.dev_badge`), les autres prennent la traduction EN CACHE
  (remplie par la page Rôles), sinon leur nom d'origine — **sans appel IA**
  depuis ces pages, qui se chargent à chaque visite. Branché dans
  `api_tableau` (RH) et `/mastery/dashboard|synthese`. La liste des rôles est
  triée sur le nom AFFICHÉ, sinon le rôle système restait à la lettre D.
- ⚠️ **La compétence principale n'existait qu'en UNE langue** : l'IA la rédige
  en français ET en anglais, et on ne gardait que celle de la personne qui
  configurait. `Competency` porte désormais `description_fr` / `description_en`
  (migration à chaud) et `texte(lang)` ; `description` reste la version de
  référence, et une compétence d'avant s'affiche telle quelle.
- **« Libellé : valeur »** : l'espace avant les deux-points est une règle
  FRANÇAISE, écrite en dur dans trois infobulles (`DP` suit la langue).
- **« S1 · 4 h »** dans l'échéancier du plan : « W1 » en anglais (`plan_wk`).
- **« 1 holders »** : singulier/pluriel, et le singulier ne couvre pas les
  mêmes nombres — « 0 titulaire » en français, « 0 holders » en anglais.
- **« Main competence »** → « Main competency », seul écart de terminologie.
- Le message au collaborateur sur une activité non configurée parlait encore de
  « qualifier ses données de sortie » : aligné sur l'écran de configuration.
- ⚠️ **Écrits en dur, invisibles à l'œil** : le `<title>` de la page
  (« OPTIQ — Compétences » dans l'onglet anglais), `aria-label="Fermer"` ×2,
  « Ouvrir le menu » et « Navigation principale » (en-tête, toutes les pages).
  Les contrôles qui ne lisent que le texte ne les voient pas — `test_82` lit
  les attributs. `competences_view.html` sort de l'inventaire de dette de
  `test_78` : son dernier fragment français était ce titre.

Vu en chemin, puis corrigé dans la foulée :
- ⚠️ **Le journal « Activité récente » se lit dans la langue de CELUI QUI LIT.**
  Il était écrit dans celle de la personne qui agissait (« Rôle créé : Qualité »
  pour un anglophone, parce qu'un francophone avait créé le rôle). Le libellé
  est rebâti à la lecture (`changelog._libelle_evenement`) depuis le TYPE
  d'événement et le nom de l'objet ; le libellé stocké ne sert plus que de repli
  pour un type inconnu du catalogue. À l'écriture, les « modifié » gardent
  désormais le NOM de l'objet et des CLÉS de champ (`name`, `description`,
  `mission`) au lieu de « Nom » / « Mission » ; les anciennes lignes sont
  relues telles quelles (nom retrouvé dans le libellé, champ français mappé).
  ⚠️ SQLAlchemy ne connaît l'ancienne valeur que si l'attribut a été LU avant
  d'être modifié : sur un objet expiré, `history.deleted` est vide et aucun
  « avant → après » n'est enregistré. En route c'est toujours le cas ; en test,
  il faut lire l'attribut d'abord.
- Le titre d'onglet de la page de connexion suit la langue.
Tests : `tests/test_83_journal_dans_la_langue_du_lecteur.py` (6 cas, 5 vérifiés
rouges). ⚠️ `test_82` et `test_83` rendent la session telle qu'ils l'ont
trouvée (`_session_rendue`) : `client` est partagé, une langue laissée à « en »
changerait les messages que les fichiers suivants comparent.

Tests : `tests/test_82_traduction_competences_rh.py` (12 cas, 10 vérifiés
**rouges** sur le code d'avant — les deux autres confirment que la page RH
était déjà propre sur ces points). Suite : 2361 passés.

---

## Guide utilisateur (`docs/guide.html`)

- **Un seul fichier, deux langues, deux thèmes.** Barre en haut à droite : segment
  FR/EN à indicateur glissant + bascule clair/sombre (icônes SVG, pas d'emoji —
  ils ne se rendent pas partout). Choix mémorisés dans `localStorage`, chaque accès
  en try/catch : un fichier ouvert depuis une clé USB ou une pièce jointe peut
  refuser le stockage. Au premier affichage le thème suit `prefers-color-scheme`.
- **Traduction** : les deux versions cohabitent dans le document
  (`<span class="t-fr">` / `<span class="t-en">`) et le CSS n'affiche que la langue
  active (`:root[lang=…]`). Aucun rechargement, le fichier reste autonome. ⚠️ Ne
  jamais envelopper un fragment qui traverse une balise (`…</b><span>…`) : le
  navigateur répare l'imbrication et le texte reste affiché dans les deux langues.
- **Thème sombre** : seuls les jetons CSS changent. Les maquettes miniatures (`.mk`)
  gardent volontairement un fond CLAIR : elles représentent l'application, qui est
  claire, comme les captures juste à côté.
- **Vidéos bilingues** : `GUIDE_LANG=fr|en` (voir `tools/guide/README.md`). Chaque
  `<video>` est doublée `t-fr`/`t-en` ; le changement de langue met en pause les
  lectures en cours (une vidéo masquée continuerait sinon).
- **Fichier autonome** : `tools/guide/build_standalone.py` → `docs/guide_standalone.html`
  (tout en base64, ~32 Mo avec les deux jeux de vidéos ; exclu de git).

---


### QUATRE statuts, et « champion » change de sens (2026-09-16)

Une échelle, pas une liste : chaque palier ajoute aux droits du précédent.

    user  <  champion  <  coordinateur  <  admin

| Statut | Cartographie | Page RH | Paramètres |
|---|---|---|---|
| `user` | **consulte** — ne modifie rien, ne propose rien | non | langue seule |
| `champion` | + **propose** une modification | non | langue seule |
| `coordinateur` | + **modifie** directement, **valide** les propositions, règle l'accès | **oui** | langue seule |
| `admin` | tout | oui | **tout** |

⚠️ **« champion » désignait l'ARBITRE ; c'est désormais le coordinateur.** Le
mot nomme maintenant le palier au-dessous, qui propose sans pouvoir valider.
Conséquences, toutes nécessaires :
- `is_coordinator_status()` reconnaît **tous les libellés historiques de
  l'arbitre** (`manager`, « Gestionnaire de compétences », sa troncature à
  20 caractères, « Competency Manager »). `is_champion_status()` ne reconnaît
  que le mot exact.
- ⚠️ **`migrer_anciens_champions()` tourne au DÉMARRAGE**, avant de servir la
  moindre requête : sans elle, un compte qui validait les propositions se
  réveillerait avec le droit de seulement les déposer. Elle s'applique donc à
  CHAQUE instance qui prend ce code — y compris le pilote, le jour où la
  branche le reçoit.
- ⚠️⚠️ **Et elle ne se joue QU'UNE FOIS** (marqueur `statuts_quatre_paliers`
  dans `app_settings`). Rejouée à chaque démarrage — ce qu'elle faisait — elle
  promouvait `coordinateur` **tout champion créé DEPUIS** : elle lit `champion`
  au sens ANCIEN, celui de l'arbitre. On nommait donc quelqu'un « champion »
  pour qu'il propose sans valider, et le redéploiement suivant lui donnait le
  droit de valider. Le nouveau palier n'existait que jusqu'au prochain
  démarrage. Le marqueur vit en BASE, pas en mémoire : une instance qui
  redémarre, se duplique ou se redéploie doit lire la même réponse.
  `migrer_anciens_champions(force=True)` rejoue la reprise (les tests s'en
  servent — l'application de test l'a déjà passée à son propre démarrage).
  Tenu par `test_66::TestRepriseDesComptes` (le cas neuf vérifié **rouge** :
  « un champion nommé APRÈS la reprise est devenu coordinateur »).
- Les ~8 appels à `is_champion()` du code voulaient tous dire « l'arbitre » :
  ils sont devenus `is_coordinator()`. `is_champion()` existe encore, avec le
  nouveau sens « au moins champion ».

**Ce qui se ferme, et où.** Le masquage n'est jamais une sécurité — chaque règle
est appliquée côté serveur :
- `POST /cartography/api/save` distingue **deux refus** : `must_propose` pour un
  champion (« proposez »), `lecture_seule` pour un `user`. ⚠️ Dire « proposez » à
  quelqu'un qui n'en a pas le droit l'envoie vers un bouton qui n'existe pas.
- `POST /cartography/api/changes` ne regardait que `can_read` : un `user`
  pouvait déposer une proposition en appelant l'API directement. Il exige
  maintenant `can_propose`.
- ⚠️ **La page Gestion RH n'avait AUCUN contrôle d'accès** : tout compte
  connecté l'ouvrait, et pouvait de là créer des rôles et affecter des
  personnes. Réservée au coordinateur et à l'administrateur.
- L'éditeur **s'ouvre en lecture seule** pour un `user`
  (`access_summary()['lecture_seule']` → `window.OPTIQCARTO_READONLY`, le même
  drapeau que le viewer). Refuser seulement à l'enregistrement laisserait
  quelqu'un travailler dix minutes avant d'apprendre qu'il n'en a pas le droit.
- Les Paramètres n'ont pas bougé : la page est ouverte à tous (chacun choisit sa
  langue) et les sections d'administration ne sont **pas rendues du tout** pour
  les autres — CSS compris.

Tests : `test_66_carto_sharing.py::TestLesQuatrePaliers` et
`::TestRepriseDesComptes`, `test_50::TestCeQueChaquePalierOuvre` (les quatre
paliers × cinq droits, en table). Suite : 2243 passés.

⚠️ **Deux pièges d'isolation rencontrés en chemin**, tous deux invisibles hors
suite complète (la base est partagée) :
- une entité de test créée **sans `owner_id`** est lisible par TOUT LE MONDE
  (`can_read` : `entity.owner_id in (None, user.id)`) — elle entrait dans le
  repli « aucune entité active » d'un autre fichier ;
- une carto laissée **commune et ouverte à tous** en fin de module devient le
  repli des fichiers suivants. `test_66` la rend privée en partant.

### Le filtre par carto active de `dashboard_rows` était REDONDANT et nuisible

⚠️ Suite du signalement « j'ai perdu mes données de notation ». Le premier
correctif — ne lister que les rôles de la carto active — visait la mauvaise
moitié : un collaborateur n'a pas forcément ACCÈS à la carto où il tient un rôle
(`Entity.get_active` valide contre les cartos accessibles, puis retombe sur « sa
première entité »), et l'écran se vidait alors pour une autre raison.

Le vrai coupable était dans `dashboard_rows` :
`Activities.entity_id == Entity.get_active_id()`.
- **Redondant** : `_sync_carto_to_db` crée rôles ET activités avec l'`entity_id`
  de la même entité — un lien `activity_roles` joint toujours deux objets de la
  même carto, le rôle borne déjà le périmètre.
- **Nuisible** : dès que le repli de l'entité active ne tombait pas sur la carto
  du rôle, toutes ses activités disparaissaient. D'où « 0 activité » sur chaque
  rôle, « — du requis tenu », et l'impression d'évaluations perdues.

Le filtre est retiré ; un rôle porte ses activités quelle que soit la carto
active. `TestPerimetreDeLaSynthese` le tient.

### L'éditeur en CONSULTATION — et le dépôt qui tuait la page (2026-09-16)

⚠️ **Le glisser-déposer HTML5 ne passe PAS par `onDown`.** Le garde de lecture
seule vivait dans le `mousedown` du canevas ; tirer une forme depuis la barre
d'outils emprunte `dragstart` → `dragover` → `drop`, qui ne le croisent jamais.
Un compte `user` posait donc des activités sur la carto — et ne l'apprenait
qu'à l'enregistrement, après le travail. Le `drop` refuse maintenant, et la
palette n'est même plus `draggable`.

**Ce que voit un `user`** (`window.OPTIQCARTO_CONSULTATION`, classe
`body.carto-consultation` posée par le gabarit) : la carte, **Sélection**,
**Centrer**, le zoom (pastille + sensibilité), la **mini map**, le panneau
Propriétés, et du menu Fichier **les trois exports seulement**. Partent :
annuler / rétablir, Box, la section Création entière (bandes, formes, calques,
grouper, pile), le curseur Labels, Vérifier, Supprimer, Enregistrer, Charger,
Importer Visio.
- **Cliquer une forme ouvre sa fiche**, en lecture. ⚠️ Le viewer et l'éditeur en
  consultation partagent `OPTIQCARTO_READONLY` mais n'attendent PAS la même
  chose d'un clic : le viewer est une vignette dans la page Carte et prévient
  sa page parente ; ici il n'y a pas de page parente, un `postMessage` n'irait
  nulle part. D'où le second drapeau.
- Le panneau est verrouillé **une fois** à l'init (`_verrouillerProprietes`) :
  il est écrit dans le gabarit, pas reconstruit à chaque sélection. `disabled`
  n'empêche pas `updateProps()` d'y poser les valeurs — on lit la fiche
  entière. La feuille de style rend l'encre pleine (un champ désactivé gris
  serait illisible) et masque les boutons de suppression.
- ⚠️ **Les boutons sont MASQUÉS, jamais retirés du document.** `editor.js` les
  câble sans garde : un id absent lève une TypeError qui interrompt TOUTE
  l'init, chargement de la carto compris — cadre gris et vide alors que les
  données sont en base. C'est le piège que `tests/test_49_carto_dom_contract.py`
  garde, et que le viewer contourne avec ses boutons vides. ⚠️ Et ce test lit le
  gabarit comme du TEXTE : un `{% if %}` autour d'un bouton le laisserait passer
  au vert tout en faisant disparaître l'id au rendu.
- ⚠️ **Masquer un bouton ne désarme pas son raccourci.** Suppr, Ctrl+Z, Ctrl+S
  et « G » appellent directement `deleteSelected` / `undo` / `saveJSON` /
  `createGroup`, qui n'avaient AUCUN garde. En consultation on sélectionne
  désormais une forme pour la lire : Suppr l'aurait retirée de l'écran sans
  rien enregistrer — une carto fausse sous les yeux. Les cinq fonctions qui
  écrivent se refusent elles-mêmes.

**Le zoom pouvait valoir ZÉRO, et un dépôt empoisonnait alors la carto.**
`fitView()` posait `vpScale = Math.min(r.width / dw, r.height / dh, 2)` **sans
borne basse**. Un « ajuster » joué sur un canevas pas encore posé (largeur 0 :
onglet caché, volet replié, `fit-view` reçu par `postMessage` depuis la page
Carte) rendait donc un facteur NUL. Reproduit et mesuré :
`translate(0,0) scale(0)` → `screenToSVG` divise par ce zéro → la forme déposée
naissait à une abscisse **non finie** → `_fitShapeIntoBand` ajoutait cet infini
à la hauteur d'une bande → le rendu jetait des `<rect x="Infinity">` et des
`<circle cx="NaN">`, la carto disparaissait et le navigateur s'étranglait. Rien
ne lève d'exception dans cette chaîne : la page paraît simplement **gelée**.
Quatre verrous, du plus amont au plus aval :
1. `fitView()` borne par `ZOOM_MIN` (0,08 — la même borne que la molette) et
   **renonce** sur un canevas dégénéré ou des bornes non finies ;
2. `screenToSVG` ne divise jamais par un facteur nul ou non fini ;
3. le `drop` **refuse un point hors des nombres** — on ne dépose rien plutôt
   que n'importe quoi, car la forme serait ENREGISTRÉE ;
4. dernier filet, `applyViewport` repart du cadrage par défaut plutôt que
   d'écrire `scale(0)` ou `translate(NaN,NaN)`.

⚠️ **Le défilement au bord s'emballait.** `_edgeScrollStep` se rappelle en
`requestAnimationFrame` tant qu'une vitesse est posée, et SEULS un `mousemove`
ou un `mouseleave` sur le canevas l'arrêtaient. Or un glisser-déposer HTML5
n'émet ni l'un ni l'autre : une fois lancé, la carto filait toute seule sous le
pointeur et la forme atterrissait ailleurs que là où on visait (mesuré : la
translation verticale dérivait de 36 px pendant un seul geste). `mouseup`,
`dragstart`, `dragend`, `drop`, `blur` et le passage de l'onglet en arrière-plan
le coupent désormais — et `cancelAnimationFrame` annule la frame déjà demandée,
car remettre la vitesse à zéro ne suffit pas.

Tests : `tests/test_79_carto_consultation.py` (42 cas — 33 vérifiés **rouges**
sur le code d'avant). Mise au point : `tools/devrun_partage.py` (port 8124)
sème maintenant les QUATRE paliers, `coord@test.local` étant l'arbitre.

### Le bandeau « Échap pour quitter le plein écran » couvrait la barre de nav

Il était posé en `position: fixed; top: 74px; right: 18px` — sur la barre de
navigation et sur les menus qui s'ouvrent depuis son bord droit — restait cinq
secondes et **interceptait les clics** (`pointer-events: auto`). Retiré, pas
déplacé : le navigateur affiche déjà sa propre mention quand une page bascule en
plein écran. On répétait, par-dessus l'interface, ce qu'il dit tout seul. Le
passage en plein écran automatique, lui, est conservé.

---

## Page Comptes — droits et langue

- **Droits** (`Code/routes/gestion_compte.py`) : `User.status` est un texte libre, écrit différemment selon les instances → comparaison sur une forme **normalisée** (minuscules, sans accents, séparateurs unifiés) via `_norm_status()`.
  - `_ADMIN_STATUSES` = admin / administrateur / administrator.
  - **Trois statuts et trois seulement** : `user`, `champion`, `admin`. « RH » a été
    retiré des listes déroulantes et du badge (il ne portait aucun droit ; l'évaluateur
    « RH » de la page Compétences est un AUTRE mécanisme, conservé).
  - `champion` = l'ancien « gestionnaire de compétences ». Il **crée des comptes**,
    **règle l'accès aux cartos communes** et **arbitre les modifications proposées**.
    `is_champion_status()` reconnaît toujours les libellés déjà en base (`manager`,
    « Gestionnaire de compétences », sa troncature « gestionnaire de comp »,
    « competency manager ») : personne ne perd ses droits parce que le mot affiché a
    changé. `is_competency_manager_status` reste un alias.
  - ⚠️ Le **filtre de statut** de la liste comparait `users.status` BRUT à la valeur de
    l'option : un champion enregistré sous un ancien libellé ne ressortait dans aucun
    filtre. Le gabarit expose désormais la **famille** (`admin` | `champion` | `user`)
    dans `data-status`.
  - **Modifier** un compte : admin, ou soi-même uniquement (`_can_edit_account`). Le champ `status` n'est appliqué que si l'appelant est admin — sinon on s'auto-promeut depuis l'édition de son propre compte. **Supprimer** : admin seulement.
  - Le gabarit masque les onglets Créer/Import sans le droit, et les boutons Modifier/Supprimer hors périmètre ; les routes refusent quand même côté serveur (le masquage n'est pas une sécurité).
- **Onglet d'accueil** = **Utilisateurs** (`list-tab`), placé en premier ; Créer et Import viennent après.
- **Langue** : colonne `users.lang` (VARCHAR(5), défaut `en`), ajoutée à chaud par `_safe_add_column` avec rattrapage des lignes existantes au démarrage. `DEFAULT_LANG` et `DEFAULT_FRENCH_ACCOUNTS` vivent dans `models.py` : seul `afdec.enterprise.services@gmail.com` naît en français. La connexion applique `user.lang` à `session['lang']`, `/parametres/set_language` persiste le choix sur le compte, et un `before_request` pose `session['lang']` par défaut — les dizaines de `session.get('lang', 'fr')` disséminées dans les vues ne retombent donc jamais sur le français.
- ⚠️ **Modification d'un compte** : un champ « âge » laissé vide arrive comme `''`.
  Envoyé tel quel dans une colonne entière, PostgreSQL rejette la requête — et
  c'est TOUTE modification qui tombait en 500 (même un simple nom de famille), y
  compris le changement de statut. `update_user` convertit désormais l'âge
  (`int` ou `None`), refuse proprement un âge non numérique ou un email déjà pris,
  tronque le statut à la taille de la colonne (20), rend le rôle facultatif et
  rattrape toute `SQLAlchemyError` en message plutôt qu'en 500.
- Tests : `tests/test_50_accounts_permissions_lang.py` (36 cas).
- **Où vivent les droits** : `Code/permissions.py` — source unique pour la page Comptes, les Paramètres et le partage d'entités. `is_competency_manager_status()` reconnaît une **famille** de valeurs plutôt qu'une liste figée : `users.status` est un VARCHAR(20), donc « Gestionnaire de compétences » y arrive **tronqué** (« gestionnaire de comp »), et le libellé est saisi tantôt en français tantôt en anglais. Règle : commence par « gestionnaire », OU contient « manager » + (« competency » | « competence » | « skill »).
- **Valeur canonique** `champion` (8 car., tient dans la colonne) proposée dans les listes déroulantes création / édition / filtre. Le badge de la liste affiche la **valeur brute** quand elle n'est reconnue par aucune règle, au lieu de la faire passer pour « Utilisateur » : un statut mal orthographié se voit, au lieu de produire des droits inexpliqués.

### Carto COMMUNE — accès par rôle (modèle principal)

`Code/carto_access.py` — **source unique** de « qui voit, qui modifie, qui arbitre ».
Recopier l'entité chez chacun (modèle historique, décrit plus bas) fabriquait autant de
cartos que de comptes : plus rien ne les reliait, et une correction devait être refaite
sur chaque copie. Une carto **commune** est au contraire **UNE seule ligne** travaillée
par plusieurs comptes — ce qui est validé est vu par tout le monde, il n'y a rien à
propager.

- **`Entity.is_shared`** (migration à chaud) : privée par défaut. Une carto qu'un compte
  crée pour lui n'obéit à rien de ce qui suit.
- **`entity_role_access`** (entity_id, role_id) : on ouvre l'accès à des **RÔLES**, jamais
  à des comptes — qui reçoit le rôle demain entre sans qu'on revienne sur l'écran d'accès.
  **Aucune ligne = ouverte à tous les comptes** de la page Comptes. Les rôles viennent de
  la carto elle-même (bandes de la carte).
- **Qui règle l'accès** : champions et administrateurs, y compris sur une carto qui ne
  leur appartient pas — rendre une carto commune engage toute l'organisation. Le
  propriétaire d'une carto privée ne peut donc pas la partager seul.
- **Qui écrit** : sur une carto commune, champion / admin enregistrent directement ; tout
  autre compte **propose**. Sur une carto privée, son propriétaire fait ce qu'il veut.
- **`carto_change_requests`** : la proposition emporte une COPIE du diagramme (elle doit
  rester examinable si la carto bouge entre-temps) et `base_diagram`, ce que l'auteur
  avait sous les yeux — c'est la référence du résumé. Appliquée, elle écrit sur l'entité
  commune puis passe par `_sync_carto_to_db`, exactement comme un enregistrement normal.
- **API** (`Code/routes/carto_sharing.py`, préfixe `/cartography`) :
  `GET|POST /api/access/<entity_id>` · `GET /api/changes[?entity_id=&status=]` ·
  `GET /api/changes/<id>` (avec le résumé) · `POST /api/changes` ·
  `POST /api/changes/<id>/approve|reject` · `DELETE /api/changes/<id>` (retrait par l'auteur).
- **Interface — la page `/share`, un seul écran pour tout le processus.**
  Régler l'accès se faisait sur la carte, mais dire QUI tient un rôle se faisait sur la
  page Rôles : deux moitiés de la même décision, à deux endroits. La page Partage
  (`share_page_bp`, `share.html`, `static/js/share.js`, `static/share.css`) porte les
  trois temps, dans l'ordre : **1 · Qui a accès** (interrupteur *Carto commune* + les
  rôles, chacun avec ses **titulaires** ajoutables/retirables sur place) · **2 · Qui
  ouvre cette carto** (les comptes, avec le motif : propriétaire, champion, ouverte à
  tous, ou *par son rôle* — le contrôle d'un coup d'œil qui n'existait nulle part) ·
  **3 · Modifications proposées** (file d'examen complète).
  Nav : juste après Cartographie, cyan `#0891b2` (`page--share`).
- **On choisit sa carto en la VOYANT.**
  `GET /cartography/api/access/<id>/thumbnail.svg` rend la **vraie carte** :
  bandes, flèches sur leur **tracé enregistré** (`_computedOrthopts`, sinon `userPts` /
  `customPath`, sinon la droite entre les deux formes), activités avec leur couleur.
  ⚠️ Une abstraction en barres de couleur avait été essayée d'abord : **toutes les
  cartos se ressemblaient**, c'est la trajectoire des flèches qui les distingue.
  ⚠️ Une carto **sans `optiqcarto_data`** (importée du temps où seul le SVG Visio était
  stocké) n'affichait RIEN alors qu'elle existe : on sert alors `svg_content` tel quel
  (plafond 3 Mo). Sans l'un ni l'autre → 404 et état vide explicite.
  ⚠️ Les couleurs viennent d'un fichier Visio et partent telles quelles dans le SVG :
  `_echap_couleur` écarte tout ce qui contient `< > " ' &`.
  Cadrage : la carto est bien plus **haute que large**. En pleine largeur de carte,
  recadrée, elle donnait un bandeau de couleurs où toutes les lignes se ressemblaient.
  La galerie est donc une **liste** : vignette **portrait** (48 px, 3/4, `contain`) à
  gauche du nom — on voit la silhouette entière, c'est elle qui distingue deux
  cartographies. L'en-tête montre la carte entière en 4/3.
  `/api/access/previews` ne porte plus que les chiffres et `has_thumbnail`.
- ⚠️ **La galerie a un plafond de hauteur** (`max-height: min(62vh, 560px)` + défilement
  interne) : sans lui, dix cartographies poussaient la colonne de travail hors de vue.
- **Rien ne se lit en lignes de tableau** : une carte par rôle (cochée = teintée
  d'accent), une carte par personne avec son initiale colorée (teinte stable, dérivée de
  l'e-mail) et un liseré gauche par motif d'accès. Une petite liste ne se parcourt pas.
- **Les deux cartes sont des poignées.** Un rôle et une personne sont les deux bouts de
  la même relation : cliquer un **rôle** ouvre « qui le tient », cliquer une **personne**
  ouvre « ses rôles sur cette carto » — avec, en face de chaque rôle, s'il *ouvre
  l'accès* ou non. La même fenêtre sert aux deux et écrit avec le même endpoint par
  paire. Sur la carte de rôle, la case à cocher garde son clic (elle décide de l'accès,
  pas des titulaires).
- « Rôles ouverts » affiche **Tous / All** quand aucun rôle n'est coché : un « ∞ » ne dit
  pas combien de personnes sont concernées.
- **Les tuiles de chiffres sont des boutons** : un chiffre appelle le clic. Chacune fait
  défiler jusqu'au bloc qui l'explique et le **désigne** (`is-pointed`, 1,4 s) — un
  défilement seul passe inaperçu.
- **Couleur : la famille FUCHSIA**, déclinée (fuchsia `#c026d3`, violet `#9333ea`, prune
  `#7e22ce`, rose `#db2777`). Chaque tuile porte sa nuance, les en-têtes de bloc et les
  dégradés reprennent la famille : la page tient sans grands aplats blancs.
- ⚠️ **L'entrée en scène des blocs n'est posée que si `document.visibilityState` vaut
  `visible`.** L'animation PART d'opacité 0 : dans un onglet en arrière-plan le
  navigateur la met en pause, et la page serait restée blanche jusqu'au retour sur
  l'onglet.
- **Chaque bloc ouvre une porte** : *Voir la carte*, *Ouvrir l'éditeur*, *Proposer une
  modification* (affiché seulement à qui doit proposer), *Gérer les comptes*, et quand la
  file d'examen est vide, un appel à l'action vers l'éditeur plutôt qu'un mur.
- ⚠️ **Cocher un rôle enregistre tout de suite** — il n'y a pas de bouton « Enregistrer ».
  Un bouton de plus laisse partir sans sauver, et l'écran ment alors sur qui a accès.
  ⚠️ **Les rôles viennent des bandes de la carto** : on ne peut pas en créer ici, et un
  rôle créé à la main ailleurs serait effacé au prochain enregistrement de la carto
  (`_sync_carto_to_db` supprime les rôles absents de la carte). L'écran le dit.
  ⚠️ `POST /api/access/<e>/roles/<r>/holders` travaille **par PAIRE (compte, rôle)** :
  les endpoints de la page RH, eux, remplacent TOUS les rôles d'une personne (delete
  puis insert) — les appeler d'ici lui retirerait ses rôles sur les autres cartos.
- **La carte ne règle plus l'accès** : « Accès à la carto » de la fiche entité mène à
  `/share/?entity_id=…` (la modale d'accès a été retirée — deux écrans pour un même
  réglage finissent par donner deux réponses). **« Envoyer une copie »** est un bouton
  distinct, à côté : c'est une action sur l'entité, pas le processus de la carto commune.
- **Dans l'éditeur** : un **bandeau** dit d'un coup d'œil si ce qu'on fait s'applique ou
  part à l'examen, le bouton **Sauvegarder devient « Proposer la modification »** (ambre,
  icône de proposition, Ctrl+S compris), et les champions ont un bouton **Propositions**
  avec le compte en attente. Le détail d'une proposition affiche **ce qu'elle change** —
  activités ajoutées / retirées / renommées / déplacées, flèches — pas du JSON.
  Tout vit dans `static/optiqcarto/carto_sharing.js`, chargé APRÈS `editor.js` :
  la gouvernance n'entre pas dans l'éditeur, qui reste l'éditeur.
- ⚠️ **Le masquage n'est pas une sécurité** : `/cartography/api/save` refuse aussi côté
  serveur, avec le code `must_propose` que le JS rattrape pour ouvrir la modale.
- ⚠️ **`Entity.get_active` n'est plus strict sur `owner_id`** — il accepte une carto
  commune ouverte au compte. Le **repli** (aucune entité active en session) reste en
  revanche « sa première entité, ordre d'insertion » : trier par nom changerait l'entité
  par défaut de tous les comptes qui en possèdent plusieurs. `Entity.accessible()` rend
  la liste réelle (siennes + communes) ; `Entity.for_user()` reste la requête « les
  siennes ».
- ⚠️ **Ménage obligatoire** : supprimer une entité efface `entity_role_access` et
  `carto_change_requests` (PostgreSQL applique les FK, SQLite non), et
  `_sync_carto_to_db` efface l'accès d'un rôle qui disparaît de la carte.
- ⚠️ **`BOOLEAN DEFAULT 0` a mis staging à terre.** PostgreSQL refuse un entier
  comme défaut de booléen (« column is of type boolean but default expression is
  of type integer ») ; SQLite l'accepte, donc **aucun test de la suite ne pouvait
  le voir**. `_safe_add_column` avalant l'erreur (il ne sait pas distinguer
  « colonne déjà là » d'un DDL invalide), `entities.is_shared` n'était jamais
  créée et **toute** requête sur `entities` tombait en 500 — page carte comprise.
  Écrire `DEFAULT FALSE` dans les ALTER, et `sa.false()` (pas `text('0')`) en
  `server_default` de modèle : `text('0')` rend « DEFAULT 0 » en PG et casserait
  aussi `create_all` sur une base neuve. Le démarrage vérifie désormais les
  colonnes indispensables (`_verifier_colonnes`) et le crie dans les journaux.
- Tests : `tests/test_66_carto_sharing.py` (34 cas — statuts, lecture par rôle, réglage
  de l'accès, refus d'écriture directe, cycle complet d'une proposition, activation,
  ménage), `tests/test_68_share_page.py` (21 cas — la page, l'entité de l'URL, les
  titulaires par paire, la portée et ses motifs, l'absence de doublon avec la carte
  et les vignettes) et `tests/test_67_schema_postgres.py` (5 cas — le DDL des modèles est compilé avec le
  dialecte PostgreSQL, sans serveur, et les ALTER écrits à la main dans `create_app`
  sont relus : c'est le seul filet contre un SQL que SQLite accepte et que la production
  refuse). ⚠️ Ces derniers RELISENT `Code/app.py` : ils sautent dans l'arbre d'image
  (bytecode-only), comme `tests/test_61_pulse.py` — `tools/repet_image.sh` l'a montré.

### Envoyer une COPIE indépendante (mécanisme secondaire, conservé)

Déposer une copie fait autre chose que partager : le destinataire devient propriétaire
d'une carto **à part**, qu'il fait évoluer de son côté et qui ne reçoit plus rien. Ce
chemin reste disponible, mais il n'est plus le bouton principal : on l'atteint depuis le
pied de la modale « Accès à la carto ».

Une entité n'appartient qu'à son propriétaire : **partager par copie = déposer une COPIE** chez chaque destinataire, qui repart ensuite avec la sienne sans toucher à l'originale.

**Tout le monde peut partager ses propres entités.** Ce que change le statut, c'est le
CONSENTEMENT du destinataire :
- **administrateur → il choisit** (`mode` dans le POST, sélecteur dans la modale) :
  **dépôt d'autorité** (défaut) ou **proposition** comme tout le monde. Un dépôt
  d'autorité laisse une **notification** (`EntityShareOffer` en statut `delivered`) :
  le destinataire voit à sa prochaine ouverture « X vous a transféré une entité »,
  avec un seul bouton **Compris** (`action:"acknowledge"` → statut `acknowledged`).
  Recevoir une entité sans avoir rien demandé mérite une explication. Sur ce
  chemin l'admin **nomme** l'entité déposée (`name`) et peut viser une entité
  **existante** du destinataire pour l'écraser (`replace: {user_id: entity_id}`)
  au lieu d'empiler « Nom (2) » ; la notification le dit (« a remplacé une de vos
  entités »). Les entités de chaque compte ne sont listées (`entities` dans
  `share/candidates`) que pour un admin en dépôt direct ;
- **tout autre statut → proposition**. Rien n'est créé à l'envoi : une ligne
  `EntityShareOffer` (table `entity_share_offers`) porte une **copie du contenu**
  (nom, description, `vsdx_filename`, SVG, `optiqcarto_data`) — le destinataire
  reçoit ce qui lui a été proposé même si l'expéditeur modifie ou supprime son
  entité entre-temps. À sa prochaine ouverture de l'app, une pop-up centrée
  (`entity_share_popup.html`, incluse par `header_buttons.html`, donc sur toutes
  les pages) annonce « X vous propose son entité … » avec **Accepter / Refuser**.
  Accepter crée l'entité et dérive activités/rôles/liens ; refuser ne crée rien.

- `GET /activities/api/entities/<id>/share/candidates` → comptes cibles + `direct`
  (dépôt direct ou proposition), `already_has`, `pending`.
- `POST /activities/api/entities/<id>/share` `{user_ids:[…]}` → `shared` (dépôts) et/ou
  `pending` (propositions). Une seule proposition en attente par (expéditeur, entité,
  destinataire) : renvoyer deux fois ne fait pas deux pop-ups.
- `GET /activities/api/share/offers` → propositions en attente du compte connecté.
- `POST /activities/api/share/offers/<id>/respond` `{action:"accept"|"update"|"decline"}` →
  404 si l'offre vise un autre compte, 409 si elle est déjà traitée.
- **Carto déjà présente chez le destinataire** : la liste des propositions renvoie
  `existing` (l'entité de MÊME NOM qu'il possède déjà) avec `differs` (comparaison
  JSON des deux `optiqcarto_data`). La pop-up propose alors **Mettre à jour la
  mienne** (`action:"update"` — remplace SA carto par celle reçue au lieu d'empiler
  « Nom (2) »), **Créer une copie**, ou Refuser ; si les deux cartos sont identiques,
  le bouton de mise à jour disparaît. `update` sans entité du même nom → 400.
  ⚠️ Mettre à jour passe par `_sync_carto_to_db`, qui fait un **upsert** (shape_id
  puis nom) : les activités communes gardent tâches, compétences et évaluations,
  mais celles absentes de la carto reçue sont **supprimées** avec leurs données
  liées. La pop-up le dit avant de valider.
- Les routes d'envoi exigent la **propriété** de l'entité (404 sinon) — plus le statut admin.
  Le dépôt (direct ou après acceptation) passe par `_deposer_copie()` : nom suffixé
  « (2) » en cas de collision, puis `_sync_carto_to_db` — sinon le destinataire reçoit
  une carte sans activités ni rôles.
- La pop-up attend que la **fenêtre de bienvenue** soit refermée (MutationObserver) pour
  ne pas empiler deux modales, et ne recharge la page qu'après une acceptation.
- Tests : `tests/test_51_entity_share.py` (40 cas).

---

## Conventions de code

- **Pas de framework JS** : tout en vanilla JS, `$()` est un alias `document.querySelector`
- **CSS par domaine** : chaque page a son CSS dédié, `optiq.css` = styles globaux
- **Templates Jinja2** : les pages incluent des partials (`{% include "partial.html" %}`)
- **Blueprints Flask** : chaque domaine est un blueprint enregistré dans `app.py`
- **Pas de commentaires évidents** dans le code : seulement pour les WHY non-évidents

---

## Design system UI (2026-07 — cohérence visuelle globale)

Toutes les pages (SAUF la cartographie `/activities/map` + éditeur, intouchée)
partagent un design system chargé partout via `header_buttons.html` :

- **`static/ui-theme.css`** = source de vérité : tokens (`--pg-font` DM Sans,
  `--pg-font-display` Fraunces, encres `--ink/--ink-2/--muted/--faint`, surfaces
  `--card/--card-2/--border`, rayons `--r-card` 14 / `--r-btn` 9, ombre `--sh-card`),
  **échelle typo UNIQUE en px** : bandeau 26 (Fraunces) · en-tête de carte/volet
  15/700 · corps 15 · secondaire/boutons/tables 13.5 · labels uppercase 12.5/700 ·
  th 12 uppercase · badges/méta 12 (min 11). ⚠️ Ne JAMAIS réintroduire d'em/rem
  fantaisistes ni de tailles hors échelle dans un CSS de page.
- **Couleur par page** = celle de son icône dans la nav (classes `page--carto`
  `#0d9488`, `page--activities` `#7c3aed`, `page--roles` `#059669`,
  `page--competences` `#2563eb` (Projection métier incluse), `page--time`
  `#d97706`, `page--accounts` `#e11d48`, `page--rh` `#16a34a`, `page--tools`
  `#ea580c`, `page--settings` `#6366f1`). Poser `pg-root page--<clé>` sur la
  racine (ou `class="pg page--<clé>"` sur `<body>`) → accent via `var(--pg-accent)`
  + dérivés `--pg-accent-deep/-soft/-softer/-border/-glow`.
- **Liseré de défilement de la nav** (`cardnav.css` + `js/cardnav.js`) : la barre
  native est masquée, et sans trackpad la nav ne pouvait pas défiler. Un liseré
  court (200 px max, ~20 % de la largeur de la nav) et vert `#49e8a4` — celui
  du contour de la nav — est posé en bas de la zone des items ;
  **il se tire**, un clic saute à la position, et la molette
  verticale défile la nav tant qu'elle n'est pas en butée (au-delà, la page
  reprend la main). Invisible au repos, il apparaît au survol de la nav et
  pendant le défilement ; masqué sur mobile (le menu s'y déplie en colonne).
  ⚠️ **Zone de captation ≠ rail visible** : viser 3 px de haut serait pénible, donc
  `.card-scrollbar` est une bande TRANSPARENTE de 13 px sur toute la largeur des
  items, et `.card-scrollbar-track` est le rail visible (200 px centré) à
  l'intérieur. La bande descend sous la zone des items (`bottom:-6px`) pour ne pas
  voler le clic des boutons de nav, qui doivent continuer à mener à leur page ;
  un clic n'importe où dans la bande est ramené sur le rail (bornes comprises).
- **2 éléments d'identité communs** : la nav (cardnav) + le **bandeau de page**
  `{% include "page_banner.html" %}` (icône teintée, titre Fraunces, sous-titre,
  encart chiffre optionnel). Fond commun gris-bleu `#f2f4f9` + halo couleur de
  page (défini dans ui-theme, ne pas remettre de `background` sur body en CSS de page).
- **`optiq.css`** = base neutre (body DM Sans 15px). ⚠️ L'ancien
  `body { font-size:30px; Arial }` + `input { width:40ch; min-height:48px }` a
  été supprimé : c'était la cause racine des incohérences (chargé APRÈS le CSS
  de page depuis la nav, il écrasait tout). Ne jamais remettre de styles
  opinionated globaux dedans.
- Boutons primaires = dégradé `linear-gradient(135deg, var(--pg-accent), var(--pg-accent-deep))`
  13.5/600 radius `--r-btn` ; secondaires = bord `--border-strong` ; th de tables =
  12px uppercase `--muted` fond `--card-2`. Couleurs SÉMANTIQUES (feux vert/orange/
  rouge d'évaluation, sévérité Faiblesse, badge rose cross-carto) conservées.
- Page Temps : refonte ergonomique (KPI intermédiaires sobres vs finaux accent 22px,
  résultats Faiblesse masqués avant calcul, feedback inline au lieu d'alert()).
  ⚠️ Endpoints `/temps/api/activity_workload*`, `role_activities`, PATCH projet
  restaurés dans `time_view.py` (perdus à la divergence des branches — le JS les
  appelait dans le vide).
- Fichiers morts supprimés (21) : anciens partials activity_*, time_list/form,
  gestion_compte v1, synthese_comp.css & co (jamais liés).

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

### Complété (session 8 — 2026-07-31)
- **Guide utilisateur entièrement refondu** (`docs/guide.html`) : orienté prise en
  main par des non-techniciens — sections dans l'ordre de la nav avec le code
  couleur de l'app, « à quoi ça sert / ce que vous voyez / pas-à-pas », 18 vraies
  captures + 6 vidéos de manipulation (curseur visible) dans `docs/assets/guide/`.
- **Pipeline de captures automatique** (`tools/guide/` — README dedans) : base de
  démo réaliste seedée depuis `Code/example.vsdx` via l'API carto, puis Playwright
  capture écrans et vidéos tout seul. À relancer après toute évolution visuelle.
- Correctif prod : `/competences/current_user_manager` renvoyait l'id 114 codé en
  dur → page Compétences morte sur toute autre base. Désormais : l'utilisateur
  connecté s'il encadre, sinon son manager.

### Complété (session 9 — 2026-08-26)
- **Guide bilingue jusqu'aux DONNÉES** (`tools/guide/demo_data_i18n.py`) : le VSDX
  d'exemple mélange les langues (20 bandes anglaises, 16 activités et 27 flèches
  françaises) — le guide français affichait donc des rôles anglais et le guide
  anglais des activités françaises. `traduire_diagramme()` réécrit les libellés
  AVANT `/cartography/api/save` (activités, rôles et liens naissent traduits) et
  tout le contenu enrichi est décliné (outils, verbes de tâches, savoirs, HSC,
  missions, projet, faiblesse). `libelles_non_traduits()` signale au démarrage du
  seed tout libellé sans entrée. Les 36 captures et 16 vidéos ont été refaites.
- **Voile sombre sur les captures du guide** : les images des paires FR/EN
  portaient `loading="lazy"` — une image cachée n'est jamais chargée, et en thème
  sombre le `.frame` laissait voir `var(--card)` (#141d2e) le temps du décodage.
  Correction : plus de `loading="lazy"` sur les paires (le fichier autonome
  embarque déjà les octets en data:) + fond de cadre clair constant.
- **Traductions applicatives manquantes** (visibles dans les captures anglaises) :
  carte des activités (« Cartographie », « 14 activités », « Rechercher une
  activité »… → `map.*`), page Temps (en-têtes des 3 tableaux construits par
  `time.js` + résumé des projets → `window.TIME_I18N`, helper `tl(cle, defaut)`),
  fenêtre de bienvenue et journal d'activité (`welcome.*`, `event.*`, dates,
  nouveautés curées bilingues via `title_en`/`desc_en` dans
  `static/changelog_user.json`). Balayage automatisé : 36 mots français sur les
  9 pages anglaises → 0.
- ⚠️ **Piège RecentEvent** : les listeners SQLAlchemy de `models.py` écrivent le
  libellé de l'événement (« Rôle modifié : X ») dans la langue de `session['lang']`
  au moment de l'écriture. Un script qui travaille dans un simple `app_context()`
  n'a pas de session → tout repart en français. `seed_demo.py` enrichit donc dans
  un `test_request_context()` avec `session['lang']` posé.

### Complété (session 10 — 2026-10-19) — `docs/doc_technique.html` refondue

« Cela fait très longtemps qu'on ne l'a pas tenue à jour, et son design fait
vraiment amateur avec la barre 100 % faite. » Les deux reproches étaient
justes, et le second mesurable.

**L'écart de contenu, mesuré avant de toucher à quoi que ce soit.** Recherche
des termes un par un dans le fichier : « carto commune », « coordinateur »,
« champion », « palier », `import_hub`, `ecriture.py`, `ActivityChangeRequest`,
`roles_communs`, `entites_uniques`, « matrice » — **zéro occurrence pour
chacun**. La doc datait du 16/09 et décrivait l'application d'avant les quatre
paliers, l'accès par rôle, les propositions, la porte d'écriture, les paliers
de performance, la page Temps refondue, la page Comptes refaite, l'historique
des imports. Elle citait encore `time_extra.py`, **supprimé depuis** (c'est lui
qui a mis la réunion des rôles à terre en production).

⚠️ **La barre « Progression globale » affichait 100 % par CONSTRUCTION.** Elle
comptait des badges `badge-done` posés à la main : **35 sections sur 37** les
portaient. Elle a donc affiché 100 % pendant tout le mois où la doc prenait son
retard — un indicateur qui ne peut pas descendre ne mesure rien. Remplacée par
des **faits datés** (relue le…, sur le code de `staging · <sha>`, n sections,
**4 à reprendre**), et chaque section périmée le dit **en tête, avant qu'on la
lise** : le lecteur ne doit jamais découvrir après coup qu'il vient d'apprendre
un écran qui n'existe plus.

**Le design : on RACCORDE, on ne redessine pas.** La doc est servie par le hub
(`/doc`), qui a une direction artistique aboutie — chaux, Fraunces en italique
pour les sur-titres, olive `#7d8c2e` pour sa section Documentation. La doc,
elle, était en Segoe UI rose-et-vert avec une barre latérale plate : on
cliquait « Documentation » dans un lieu soigné et on tombait dans un autre
monde. ⚠️ **C'est cet écart qui faisait amateur, pas le détail des pages** — et
c'est la raison pour laquelle les deux refontes de la page Carte avaient été
refusées (« j'avais redessiné ce qui ne devait pas bouger »). Tranché sur
maquette avant d'écrire : canvas « Doc technique — la coque » (la page, la
barre avant/après, le sommaire avant/après).

**Le sommaire se construit DEPUIS les sections**, il n'est plus écrit à la
main. ⚠️ C'est ce qui a manqué pendant un mois : une liste tenue à part finit
par ne plus correspondre au document. Chaque `<section>` déclare sa famille
(`data-fam`) et son état (`data-etat="neuf"|"vieux"`) ; six familles au lieu de
37 liens à plat, plus un champ de recherche. Deux marques et deux seulement —
**NEUF** et **À REPRENDRE** : les deux questions qu'on se pose en ouvrant une
doc.

**Sept sections écrites** : la gouvernance (quatre paliers, tableau des droits,
porte d'écriture), l'accès (carto commune, rôles et statuts), les propositions
(carte et données), les paliers de performance, Importer des données et son
historique, le hub / panel / pulse, et l'outillage (bancs `devrun_*`, suite de
tests, `repet_image.sh`). **Quatre marquées à reprendre** : `import-ia`, `rh`,
`competences`, `gestion-compte` — chacune avec un bandeau qui dit ce qui a
bougé et renvoie vers la section à jour. Les 33 sections existantes sont
reprises **telles quelles** : réécrire 33 sections d'un coup, c'est en abîmer
quelques-unes sans s'en apercevoir. 33 → **40 sections**.

⚠️⚠️ **Ni `IntersectionObserver` ni `requestAnimationFrame` ne tirent dans le
volet de mise au point.** Mesuré : un observateur NEUF, posé à la main, ne rend
**rien** — pas même l'appel initial que la spécification garantit ; et
`window.scrollY` change (55 513) pendant que le compteur d'événements `scroll`
reste à **0**. Même famille que les transitions CSS figées en cours de route,
déjà connue : tout ce qui dépend du rendu est invérifiable là-bas. Conséquence
pratique : l'allumage de la section lue n'utilise **pas** d'observateur — un
calcul au défilement se prouve en rejouant la fonction à chaque position, ce
qui a d'ailleurs montré un vrai défaut (la **dernière** section ne pouvait
jamais s'allumer : la page ne défile plus assez pour la faire monter dans la
bande de lecture).

⚠️ Les cinq diagrammes hérités déclarent `Segoe UI` en **attribut de
présentation** (`font-family="…"` sur le `<svg>`), pas en `style` : une règle
d'auteur l'emporte donc sans `!important`, et `svg { font-family: var(--f-corps) }`
les raccorde sans toucher à leur tracé.

**Puis les onze sections qui restaient fausses ou creuses** (même jour) :
- ⚠️ **La carte des modèles comptait 18 lignes pour 49 modèles** — c'est le
  premier endroit qu'on ouvre en arrivant. Refaite en bloc, par domaine, avec
  les deux pièges de schéma qui ont coûté des 500 en production (une table lue
  en SQL brut que rien ne crée ; deux modèles pour une même table).
- **`import-ia` devient « Le moteur d'appariement des tâches »** : l'écran a
  disparu, le moteur est resté et `import_hub` le réutilise. **`gestion-compte`**
  réécrite sur la page refaite. **`rh`** dit ce qui reste et où sont partis les
  trois blocs. **`competences`** dit lequel des deux modèles d'évaluation sert,
  et pour quoi. Les quatre marques « À reprendre » tombent — **0 section
  périmée**, et la tuile disparaît d'elle-même.
- **`temps`** (refonte en trois écrans, les trois défauts de calcul de
  l'audit), **`stack`** (les versions épinglées), **`deploiement`** (trois
  branches / trois bases, et la sauvegarde qu'il faut RELIRE),
  **`cartographie`** (la page refondue, les rôles communs, les noms uniques),
  **`activites`** (l'import parti, le filtre « sans tâches »).
- **`conventions` porte désormais « Les pièges qui ont mordu plus d'une
  fois »** : ce que SQLite accepte et que PostgreSQL refuse, les contrôles qui
  dépendent de la machine, la base de test partagée, le `zoom: .8`, `[hidden]`,
  les propriétés personnalisées résolues à la déclaration, le volet qui ne
  peint pas, les deux conventions de substitution, et les règles de travail
  (un test se vérifie ROUGE, une refonte se tranche sur maquettes, une
  suppression se fait sur des bornes). C'est la partie à lire avant d'écrire
  du code.

⚠️ **Le nettoyage d'un bandeau a laissé deux `</div>` orphelins.** Le retrait
coupait au PREMIER `</div>` alors que le bloc en contient deux (le cadre, et
la boîte du texte). Trouvé en parcourant le document balise par balise, pas à
l'œil : un déséquilibre de `<div>` ne se voit pas forcément à l'écran. Le
contrôle vaut d'être rejoué après toute retouche structurelle — ouvertures et
fermetures doivent s'équilibrer, et la profondeur ne jamais devenir négative.

**Reste pour une prochaine fois** : le guide utilisateur (`docs/guide.html`),
que l'utilisateur a explicitement remis à plus tard, et les captures des
écrans refondus.

### En cours
- *(rien)*

### ⚠️ Rien n'était ÉPINGLÉ : une image pouvait cesser de démarrer sans qu'aucun commit ne change (2026-09-27)

`Deploy → Staging` a réussi son build puis échoué au démarrage — *« The
user-provided container failed to start and listen on the port … PORT=8080 »* —
le **26/09**, sur un commit qui ne touchait **QUE des fichiers de `tests/`**.
Le déploiement du 24/09, lui, était passé. Rejoué à l'identique : même échec.

**La cause n'est pas dans le code, elle est dans `requirements.txt` :** aucune
version n'y était épinglée. Chaque construction d'image installait « la
dernière version du jour ». Et **`SQLAlchemy` n'y était même pas déclarée** :
elle arrivait comme dépendance de `flask_sqlalchemy`, qui accepte
`>=2.0.16`. Mesuré en montant un venv neuf depuis le fichier d'alors :
**2.1.1** — une version MAJEURE — là où tout ce qui avait été éprouvé et
déployé tournait sur **2.0.52**.

⚠️ **Et cela ne se voit PAS en local.** Le venv de développement garde les
versions du jour où il a été créé : la suite reste verte, `tools/repet_image.sh`
aussi, pendant que l'image part sur autre chose. C'est exactement le piège de
`tests/conftest.py` qui retire les clés IA — un contrôle qui dépend de la
machine ne contrôle rien.

**Ce qui a été écarté en chemin, mesuré, à ne pas re-chercher :**
- pas un défaut d'import ni de bytecode : l'arbre d'image (`repet_image.sh`)
  passe la suite, et **gunicorn y démarre et répond 200 sur `/health`** —
  y compris avec les dépendances NEUVES ;
- pas gunicorn : 26.2.0 des deux côtés ;
- pas la taille (`tests/` = 16 Mo) ; pas le recensement des tests (il vit dans
  un `before_request` du panel, pas au démarrage).

**Le correctif** : les 19 dépendances déclarées portent une version exacte, et
`SQLAlchemy==2.0.52` est déclarée EXPLICITEMENT — elle décide du dialecte SQL
de toute l'application, la laisser choisir par `flask_sqlalchemy` revient à ne
pas la choisir. Vérifié : installation depuis zéro dans un venv neuf, imports,
et démarrage gunicorn dans l'arbre d'image.
Cliquet : `test_72::TestLesDependancesSontEpinglees` (3 cas, deux vérifiés
**rouges** en remettant les noms nus).

⚠️ **Monter une version est désormais un CHANGEMENT** : la modifier dans
`requirements.txt`, lancer la suite ET `tools/repet_image.sh`, puis livrer.
Ce n'est plus un effet de bord d'une reconstruction.

### Quatre écrans repris : l'import, la page Temps, la carte, la page RH (2026-09-27)

**L'écran « Vérifier » de l'import était illisible** — « trop d'info, on est
surchargé ». Trois blocs de MÉTA occupaient le haut avant qu'on voie la
moindre ligne de données : une carte pleine largeur « Où importer ? » (titre +
phrase + segment), une rangée « Cette feuille contient : [Rôles][Tâches]
[Outils] » qu'on ne touche jamais quand la nature est certaine, et un encadré
« Lu tel quel » étalant SEPT pastilles de correspondance. Aucun n'est une
décision : ce sont des confirmations.
- la **destination** devient une barre d'une ligne (`is-barre`), sans titre ni
  phrase — le pied de la fenêtre disait déjà « → carto » ;
- la **correspondance des colonnes** se replie en « 7 colonnes reconnues »,
  qui s'ouvre d'un clic. ⚠️ Sauf quand c'est l'IA qui a lu : là il y a vraiment
  quelque chose à vérifier, elle reste dépliée ;
- la **nature** attend derrière « Ce n'est pas ça ? » : on ne la déplie que
  pour CONTESTER ce qui a été lu ;
- le **rail des feuilles** répétait le nom du fichier sur chaque ligne (six
  fois « Purchase Task.xlsx › … »), ce qui chassait le nom de l'onglet. Il est
  dit UNE fois en tête, et le nom d'onglet disparaît quand il redit la nature
  (« Rôles » / « Rôles »).

**Page Temps : `window.confirm` pour supprimer.** La fenêtre du navigateur,
avec ses styles système et un texte français écrit en dur — cinq fois.
`optiqConfirm(message, {title, ok, cancel, danger})` rejoint `optiqAlert` dans
`static/js/optiq_alert.js` : même pop-up que le reste de l'app, rend une
PROMESSE (les cinq appelants étaient déjà `async`). ⚠️ Le focus part sur
**Annuler** et un clic à côté annule : sur une suppression, le geste ambigu ne
vaut jamais un oui. ⚠️ `header_buttons.html` ne charge PAS `optiq_alert.js` —
la page Temps doit l'inclure elle-même, avant `time.js`. Sept clés `time.del_*`.

**Page Carte : l'ordre des boutons** suit ce qu'on fait — gérer les entités,
importer, régler l'accès, puis afficher les connexions.

**Page RH, « les compétences de chacun » : la case ne porte QUE sa couleur.**
Une pastille, rien d'autre — ni jauge, ni texte. La jauge à quatre pas y était
répétée sur toute la grille (N personnes × M rôles) : un damier qu'on ne lit
pas ; et la ligne « 2 en écart » / « Niveau tenu » qui l'accompagnait mettait
autant de phrases que de cases. Tout cela — barème, niveaux, ce qui reste à
faire, compteurs, couverture — vit dans une **bulle**, au survol MAINTENU
(900 ms : on traverse la grille sans être dérangé).
⚠️ Posée sur le BODY en `position: fixed` : le tableau a son propre défilement,
une bulle posée dedans serait tronquée. Elle se ferme sur tout ce qui déplace
ce qu'il y a dessous (défilement en capture, redimensionnement, clic) et
s'ouvre SANS attendre au clavier, où le survol n'existe pas.
⚠️ Pas d'attribut `title` sur la case : il ouvrirait la bulle du système
par-dessus la nôtre. ⚠️ `pointer-events: none` sur la bulle — elle ne doit
jamais voler le clic de la case qu'elle explique.
⚠️⚠️ **Et elle se dessinait 20 % trop haut et trop à gauche de sa case** :
`body.pg` porte `zoom: .8` (ui-theme), donc un enfant du body en
`position: fixed` voit ses coordonnées MULTIPLIÉES par ce zoom, alors que
`getBoundingClientRect()` les rend déjà en pixels d'écran. On divise par le
zoom avant d'écrire `left`/`top`, et on multiplie `offsetWidth` pour le
comparer à `window.innerWidth`. **Exactement le même piège que le menu du
développeur de compétences** (`gestion_rh.js`) — c'est la deuxième fois : tout
élément posé sur le body en `fixed` dans cette application doit faire cette
conversion. Mesuré après : écart horizontal 0,0 px avec le centre de la case.

### À faire (par priorité)
1. **`docs/guide.html` — le guide utilisateur est le seul des deux documents à
   n'avoir pas été repris** (la doc technique l'a été le 19/10/2026). Il décrit
   encore le partage de carto par COPIE seul, l'ancien import global IA, et
   ignore les quatre paliers, les propositions, les paliers de performance et
   la page Temps refondue. Captures comprises — et elles se refont avec
   `tools/guide/`.
2. **Les captures de la doc technique** : elle n'en porte aucune, et quelques
   écrans gagneraient à être montrés (la fenêtre d'examen, le relief des
   paliers, la matrice d'accès).
3. Éditeur OptiqCarto côté JS (`static/optiqcarto/editor.js`) — seul élément majeur restant

---

## Distribution client — branche `optiqfluent-staging`

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

## Administration & UX IA (branche optiqfluent-staging)

- **Clé IA à chaud** : `Code/ai_key.py` — `get_openai_key()` / `get_anthropic_key()`
  (table `app_settings` clés `openai_api_key`/`anthropic_api_key` en priorité, puis env).
  ⚠️ Ne JAMAIS lire les clés par `os.getenv` dans une route. Message d'erreur
  standard : « Clé IA non renseignée. »
- **Fournisseur IA interchangeable (2026-07)** : `Code/ai_client.py` —
  `make_ai_client()` renvoie (client, model, err) ; interface OpenAI
  `chat.completions` conservée partout, Claude servi via le point d'accès
  compatible OpenAI d'Anthropic (`https://api.anthropic.com/v1/`, zéro dépendance).
  Sélection : `AI_PROVIDER` (`auto` défaut : Claude si clé Anthropic présente,
  sinon OpenAI) ; modèle : `AI_MODEL` sinon `claude-haiku-4-5-20251001` /
  `gpt-4o-mini`. ⚠️ Ne JAMAIS écrire `model="gpt-4o-mini"` en dur : utiliser
  `ai_model()` (ré-exporté par propose_common). Banc de non-régression qualité :
  `tools/ai_eval/run_compare.py` (rapport côte à côte sur les prompts réels —
  à lancer avec les 2 clés AVANT d'activer la bascule).
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

## Suivi d'audience OptiqPulse (2026-08)

Service **privé** de suivi des utilisateurs, séparé de l'app (données sensibles,
jamais exposées aux utilisateurs). Deux morceaux :

- **Instrumentation dans l'app** : `Code/routes/pulse_track.py` (after_request →
  `usage_events` : pages vues GET HTML + actions POST/PUT/PATCH/DELETE, durée
  serveur ; endpoint `/pulse/beat`) + `static/js/pulse.js` (battement ~60 s,
  onglet visible, inclus via `header_buttons.html`) → table `usage_beats`.
  Modèles dans models.py (`UsageEvent`, `UsageBeat`, sans FK users), tables
  créées par create_all au boot. Écriture en connexion Core dédiée (jamais la
  session ORM), toute erreur avalée. **Désactivé sous TESTING** (activer par
  test : `app.config['PULSE_FORCE']=True`) ; kill switch `PULSE_DISABLED=1`.
  Bruit ignoré : /static, /pulse, /healthz, /parametres/admin/logs. Purge au
  boot : battements 90 j, événements 400 j.
- **Dashboard `pulse/`** (Flask autonome, service Cloud Run `optiq-pulse`,
  workflow `.github/workflows/deploy-pulse.yml` sur push de `pulse/**`) : se
  branche en LECTURE sur les bases Neon listées dans `PULSE_DBS[_B64]`
  (composées en CI depuis les secrets `PILOT_DATABASE_URL` +
  `PULSE_EXTRA_DBS`). Agrégation 100 % Python (`aggregates.py`, testable
  SQLite) : connectés maintenant (battement < 3 min), pic de simultanés
  (buckets minute), moyenne/jour, temps par page (deltas entre battements,
  plafond 90 s), top pages (libellés FR), table utilisateurs + parcours
  chronologique. **Compte unique** `Mael_Girardin` (mdp défaut `testtest`,
  changer via secret/env `PULSE_PASSWORD`), anti-force-brute, noindex.
  Tests : `tests/test_61_pulse.py` (14). Doc : `pulse/README.md`.

## Optiq Hub — point d'entrée unique (2026-09)

`hub/` — service Cloud Run **séparé de l'app** (même patron qu'OptiqPulse),
déployé par `.github/workflows/deploy-hub.yml` sur push `staging` touchant
`hub/**` ou `docs/**`. Il regroupe ce qui était éparpillé : instances en ligne
avec leur **état sondé en direct** (côté serveur, cache 25 s, pool de threads),
documentation **servie par le hub** (`/doc`, `/guide`, `/doc/refonte`, médias
sous `/assets/…`), catalogue des commandes locales copiables, branches et
workflows. Deux comptes — `Mael_Girardin` (secret `HUB_PASSWORD`, défaut baké
`testtest`) et `Hubert_Grandjean` (`HUB_PASSWORD_HG`, défaut baké) — anti-force-brute,
`noindex`. ⚠️ Le dépôt ne porte que des HASHES, et `_check_credentials` compare tous
les comptes sans court-circuit (sinon on les énumère au chronomètre).

- ⚠️ **Tout le contenu vit dans `hub/inventaire.py`** — instances, documents,
  commandes, branches, secrets. Le gabarit ne porte aucune donnée en dur :
  ajouter une instance, c'est éditer une liste Python. **Aucun secret dedans** :
  on nomme les bases et les secrets GitHub, on ne recopie pas leurs valeurs.
- ⚠️ **La doc est copiée dans `hub/_docs` par le workflow, jamais versionnée**
  (`.gitignore`) : le `.dockerignore` de la racine exclut `docs/`, mais le
  contexte de build du hub est `hub/`, donc cette exclusion ne s'y applique pas.
  `guide_standalone.html` (~32 Mo) reste dehors — le guide servi charge ses
  médias depuis `/assets`.
- ⚠️ `/health` et **pas** `/healthz` (intercepté par le frontend Google sur
  `*.run.app`) ; `HUB_SECRET_KEY` est conservée d'un déploiement à l'autre,
  sinon chaque livraison déconnecte la session.
- **Ce que le hub ne fait pas** : lancer les traitements locaux
  (provisionnement, captures du guide). Une page hébergée ne peut pas exécuter
  un script sur le poste de l'utilisateur ; le hub en garde le mode d'emploi et
  la commande exacte, copiable en un clic. **La suite de tests, elle, tourne
  bien depuis le hub** — voir le module ci-dessous.

### Module « Panel de tests » (2026-09-04)

Le hub ne se contente plus de pointer vers le panel : il en est la façade.
`/panel` (carrousel des pages) et `/panel/<slug>` (détail d'une page).

- **L'exécution a lieu SUR l'instance**, pas dans GitHub Actions.
  `_start_run` lance pytest en sous-processus sur une **base SQLite jetable**
  (`tests/conftest.py`), jamais sur la base de l'application. Trois
  conséquences, toutes nécessaires :
  1. ⚠️ **`tests/` n'est plus exclu par `.dockerignore`** — c'est le
     **Dockerfile** qui tranche (`ARG WITH_TESTS`, défaut 0). Le build staging
     passe `--build-arg WITH_TESTS=1` ; l'image client, elle, supprime le
     dossier. Exclure au niveau du contexte privait les deux du choix, et le
     panel déployé affichait **0 test** (`sync_tests_to_db` ne trouvait aucun
     fichier) — le symptôme rapporté.
  2. ⚠️ **La purge bytecode épargne `tests/`** : pytest collecte des `.py`, pas
     des `.pyc`, et le panel analyse les sources pour recenser les cas
     (`compileall -x '(^|/)tests/'` + `find … ! -path "/app/tests/*"`).
  3. ⚠️ **Cloud Run staging tourne en `--no-cpu-throttling`** : le
     sous-processus démarre APRÈS la réponse HTTP ; sans CPU alloué en continu
     il est étranglé à ~5 % et une exécution de 3 min en prend 60.
     Contrepartie : CPU facturé tant qu'une instance vit (`--cpu 2`,
     `--memory 4Gi`, `--timeout 900`).
- **Plus aucun jeton.** L'ancienne page `/tests` déclenchait `tests.yml` via
  l'API GitHub et exigeait `HUB_GITHUB_TOKEN` — d'où « Jeton GitHub absent ».
  Page, gabarit, `ci_github.py` et les routes `/api/tests/*` sont **supprimés**.
  Le workflow `tests.yml` reste (il tourne au push) ; ses journaux sont liés
  depuis le pied du module.
- ⚠️ **Le blueprint `/testpanel/**` n'a AUCUNE authentification** (y compris
  `POST /run/all` et `POST /admin/clone_entity`, qui duplique des entités en
  base). C'était sans conséquence tant que l'image ne contenait aucun test ;
  chaque appel anonyme coûte désormais deux minutes de deux vCPU. En attendant
  une vraie décision sur l'accès, un **plafond de 3 pytest simultanés**
  (`_reserver_creneau` / `_liberer_creneau`) borne la casse. Le garde vit dans
  le **worker**, pas dans la route : le contrat du panel — un run par demande,
  id distinct, portée exacte — reste celui que `tests/test_37_test_panel.py`
  vérifie, et une route qu'un test neutralise n'est jamais bridée. Ce n'est PAS
  une authentification.
- ⚠️ **Un test écrit en fonction de MODULE compte autant qu'un test de classe.**
  `_parse_test_file` ne parcourait que les `ClassDef` : sept fichiers entiers
  (`test_48`, `49`, `50`, `51`, `52`, `62`… soit ~120 tests) sortaient à **zéro
  cas**, affichaient « jamais joué » même après une exécution complète et ne
  pesaient dans aucun taux de fiabilité. Trois endroits à tenir ensemble : le
  parseur (node_id **sans** segment de classe), `_save_results` (JUnit donne
  `tests.test_51_x` sans classe — prendre `parts[-1]` faisait passer le NOM DU
  MODULE pour une classe, le résultat ne se rattachait à rien) et `_build_args`
  (`fichier.py::::nom` ne veut rien dire pour pytest → on rejoue le `node_id`
  recensé).
- **API côté app** (`Code/routes/test_panel.py`) : `/testpanel/api/etat`,
  `/api/pages`, `/api/page/<slug>` — le seul contrat entre l'app et le hub.
  `_fiabilite()` **exclut les cas jamais joués** du calcul : les compter comme
  des échecs ferait chuter le score d'une page qu'on n'a pas encore lancée.
  Tests : `tests/test_65_panel_api.py` (21 cas).
- **Pont côté hub** (`hub/panel_client.py`) : le navigateur ne peut pas appeler
  l'instance (deux domaines, aucun CORS) — le hub appelle côté serveur et
  republie sous son domaine. `PANEL_BASE` vise une autre instance pour la mise
  au point locale.
- ⚠️ **Un POST vers un `*.run.app` DOIT porter un corps**, même vide. Sans
  `data`, urllib n'envoie pas de `Content-Length` et le **frontend Google**
  répond **411 Length Required** sans jamais atteindre l'application. Rien ne
  s'interpose en local : le lancement passait au banc et échouait en ligne.
  `_appel()` envoie donc `data=b""` sur les POST. Couvert par
  `tests/test_65_panel_api.py::TestPontDuHub`.
- **Identité visuelle** : même langage que le hub (Fraunces, arrondis,
  italique des sur-titres) mais on doit voir qu'on a changé de lieu — la
  **verrière** remplace le mur chaulé, le **pignon de serre** remplace l'arche,
  un bandeau de module donne le chemin de retour. Lavande `#8b6fb5` (couleur de
  la section Tests). `panel.html` / `panel_page.html` n'étendent PAS
  `base.html` : un module n'a pas la barre de navigation du hub.
- ⚠️ **`.car-socle` en `pointer-events:none`** : l'ombre au sol couvre le bas de
  la carte active et volait le clic sur « Voir le détail ».
- ⚠️ **La molette verticale n'est PAS captée** par le carrousel : la confisquer
  empêchait de faire défiler la page dès que le pointeur passait sur l'anneau.
  Navigation : flèches, clavier, glisser, geste horizontal, champ de filtre
  (70 pages à la flèche serait une corvée).
- ⚠️ **La suite tourne désormais là où les CLÉS IA existent.** Des dizaines de
  tests vérifient le comportement *sans* clé et comptaient sur le fait qu'un
  poste de développement n'en a pas ; sur l'instance, Cloud Run porte
  `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` dans l'environnement, que le
  sous-processus pytest hérite → **15 tests rouges sur 5 fichiers** (16, 22, 47,
  56, 58), donc un taux de fiabilité faux par construction. `tests/conftest.py`
  retire ces variables avant de créer l'application : la suite ne dépend plus de
  la machine (mesuré : 1877 passés avec ET sans clés).
- **Le panel compte des FONCTIONS, pytest compte des EXÉCUTIONS** : un
  `@pytest.mark.parametrize` (4 dans `test_50`) rend un cas recensé et plusieurs
  résultats. L'écart 1860 recensés / 1877 joués est normal.
- **`tools/repet_image.sh`** — répète la disposition de l'image SANS Docker
  (exclusions `.dockerignore` + purge bytecode, `tests/` épargné) et y lance la
  suite. À passer avant toute livraison qui touche au Dockerfile ou aux tests :
  depuis que la suite tourne sur l'instance, un test qui lit un fichier SOURCE
  échoue là-bas en passant ici. C'est ainsi qu'a été trouvé le défaut de
  `tests/test_61_pulse.py` (fixture `pulse_app` : `spec_from_file_location` sur
  `pulse/app.py`, absent d'un arbre bytecode → 4 erreurs à chaque exécution).
  Mesuré : 1867 passés en local, 1863 passés + 4 sautés dans l'arbre d'image.
### Le panel de tests mettait 31 s à répondre — 2318 requêtes pour rien (2026-09-16)

⚠️ **`sync_tests_to_db()` envoyait UNE REQUÊTE PAR CAS.** Il chargeait bien
`page.cases` pour savoir ce qui existait déjà… puis refaisait un
`TestCase.query.filter_by(node_id=…).first()` sur chacun. Mesuré au compteur de
curseur : **2400 requêtes au premier appel, 2318 pour une synchro qui ne change
rien**, sur 83 pages et 2148 cas. La base vivant sur Neon, à ~15 ms de Cloud
Run, cela faisait **31 s à chaud** — et il tournait à CHAQUE lecture de
`/api/etat` et `/api/pages`.

Conséquence en bout de chaîne : `panel_client.DELAI` vaut 25 s, donc l'appel
**dépassait toujours son délai**. La page `/panel` du hub attendait 25 s, puis
s'affichait en annonçant « l'instance ne répond pas » — alors que l'instance
répondait très bien, six secondes plus tard.

- **Le correctif** : deux requêtes pour tout charger (`TestPage.query.all()` +
  `TestCase.query.all()`), puis un dictionnaire en mémoire. Mesuré après :
  **4 requêtes** au premier appel, **1** ensuite.
- **Et on ne resynchronise que si les fichiers ont bougé** (`_empreinte_tests()`
  = nom, taille, date de chaque `test_*.py`). Les fichiers de test ne changent
  qu'au déploiement. ⚠️ L'empreinte seule ne suffit pas : un processus qui a
  déjà synchronisé ne sait rien d'une base remise à zéro sous lui — on vérifie
  donc aussi que `TestPage` porte des lignes. `sync_tests_to_db(force=True)`
  refait tout.
- Effet de bord bienvenu : la suite complète passe de **72 s à 40 s** (le
  `before_request` du panel synchronisait à chaque requête de test).
- Tests : `tests/test_65_panel_api.py::TestCoutDuRecensement` (3 cas — vérifiés
  **rouges** en remettant la requête dans la boucle : 2155 requêtes relevées).
  ⚠️ Ils comptent des **requêtes**, pas des secondes : la suite tourne sur
  SQLite, où tout est dans le processus et où le défaut est invisible au
  chronomètre.

⚠️ **La page `/panel` du hub bloquait son rendu sur un appel inter-services.**
`render_template("panel.html", etat=panel_client.etat())` : le HTML ne partait
qu'une fois l'instance interrogée. Elle ne le fait plus — le squelette part
immédiatement, et les chiffres arrivent par `/api/panel/pages`. Le résumé de
l'en-tête (`#mod-resume`) est rempli par le JS et **dit qu'il attend** tant que
la réponse n'est pas là (italique estompé) : « Lecture du catalogue… » posé en
style définitif se lisait comme un état, pas comme une attente.
Nouveauté au passage : `/api/panel/etat` est appelé **en parallèle** du
catalogue et **rattrape une exécution déjà en cours** — en rouvrant la page
pendant que la suite tournait, on ne voyait rien et on la relançait par-dessus.

### « L'historique des tests se remet à zéro » — il n'était jamais affiché (2026-09-16)

⚠️ **Le module du hub ne montrait AUCUN historique.** `/api/pages` et
`/api/page/<slug>` ne portent que `last_status` — l'état du DERNIER passage — et
le gabarit n'affichait rien d'autre. D'où l'impression, très légitime, que tout
se remettait à zéro : il n'y avait simplement jamais rien à voir.

**Vérifié avant de corriger, plutôt que supposé.** Relevé sur l'instance :
`dernier = {id: 2, fin: 2026-09-16T12:41:59}`. Après un redéploiement complet de
staging, la même exécution était **toujours là**. La base ne se vide donc pas, et
rien dans le code ne supprime `test_runs` / `test_results` — `_save_results`
ajoute une ligne par cas et par exécution, sans jamais en retirer.
⚠️ Deux pistes ont été écartées EN CHEMIN, et méritent de l'être par écrit :
- *« pytest écrase la base de l'app »* — non : `tests/conftest.py` impose
  `SQLALCHEMY_DATABASE_URI` sur un SQLite temporaire avant tout `create_all`.
- *« les sept `--set-env-vars` du workflow s'écrasent, donc pas de
  `DATABASE_URL` »* — non : `deploy-officielle.yml` emploie le même motif et
  sert les données réelles de l'entreprise depuis des mois.

**Le correctif est un AFFICHAGE, pas une persistance** :
- `GET /testpanel/api/runs?limit=` — les exécutions terminées, via
  `_recent_runs()` qui existait déjà pour le tableau de bord de l'app. La limite
  est **bornée à 60** : le paramètre vient du client, et `?limit=100000`
  remonterait toute la table à chaque ouverture de page. Pas de
  `_sync_tolerant()` ici — on lit du passé, le recensement des fichiers n'y
  change rien.
- ⚠️ Seules les exécutions `status == 'done'` sortent : une exécution en cours
  n'a pas encore de résultat, et l'afficher donnerait une barre à zéro qui
  ressemble à un échec total.
- `hub/panel_client.runs()` + `GET /api/panel/runs` : le navigateur ne peut pas
  appeler l'instance (deux domaines, aucun CORS), le hub republie sous le sien.
- **La frise** (`#frise`, `panel.js::frise()`) : une barre par exécution, hauteur
  et couleur selon le taux de vert, **la plus récente à DROITE** — sens de
  lecture d'une chronologie. Masquée tant qu'il n'y a rien : une frise vide vaut
  moins que pas de frise. Le pourcentage ne tient pas dans 12 px de large, il
  vit dans l'info-bulle — et reste écrit pour les lecteurs d'écran.
- ⚠️ **Et l'historique, une fois affiché, a montré son propre mensonge** :
  l'exécution du 14/09 sortait à « **100 %** » avec **3 échecs** sur 2054 cas —
  `round(99,85)` rend 100, et la frise l'aurait peinte en vert plein. Cent pour
  cent ne se lit désormais que si RIEN n'a échoué ; en dessous on plafonne à 99
  et on arrondit vers le BAS, pour ne jamais annoncer mieux que la réalité.
- Tests : `tests/test_65_panel_api.py::TestHistoriqueDesExecutions` (7 cas —
  la forme de chaque exécution, l'exclusion des exécutions en cours, la borne de
  `limit`, la route côté hub, et les deux cas de l'arrondi).
  ⚠️ Ces cas créent leur PROPRE page et leur propre cas (`_cas_jetable`) :
  prendre `TestCase.query.first()` les faisait dépendre du recensement, donc
  d'un autre test lancé avant — seuls, ils tombaient sur `None`.

### Module « Courrier » du hub — ce qui part, ce qui revient (2026-10-29)

`/courrier` (`hub/courrier.py`, `hub/templates/courrier.html`,
`hub/static/courrier.css` et `.js`, accent verdigris `#0f8a7d`). Deux questions
au même endroit, et elles ne se recouvrent pas : **combien** de
réinitialisations de mot de passe ont été demandées, et **qu'est-ce qui est
revenu** sur l'adresse d'envoi. La première ne sait que ce qui a été ENVOYÉ ;
seule la seconde apprend qu'un mail n'est **pas arrivé** — c'est là
qu'atterrissent les rejets.

#### Les chiffres : la lecture, par le chemin de `pulse/`

- `HUB_DBS_B64` est composée au déploiement par la **même recette que
  `deploy-pulse.yml`** : les trois secrets connus, puis **tout service Cloud Run
  du projet qui porte une `DATABASE_URL`**. Aucune URL n'est recopiée à la main,
  et une branche déployée demain est suivie au prochain déploiement du hub.
- ⚠️ **Le hub ne lisait AUCUNE base jusqu'ici** : il sonde les instances en HTTP
  et republie les données du panel par `hub/panel_client.py`. C'est un vrai
  élargissement de surface — assumé parce que `pulse/` a déjà ces mêmes
  identifiants, et borné par `_lecture_seule()` : `SET TRANSACTION READ ONLY`
  sur PostgreSQL. Rien n'écrit ici, mais ce code ouvre la base d'un CLIENT, et
  une faute de frappe dans un futur `text(...)` ne doit pas pouvoir y toucher.
- **L'agrégation est 100 % Python** (comme `pulse/aggregates.py`) : elle se joue
  donc sur SQLite, sans PostgreSQL ni serveur.
- ⚠️ **Aucune empreinte ne sort.** `password_resets` ne porte que les empreintes
  de l'adresse saisie, du jeton et de l'IP — c'est voulu : une lecture de la
  base ne doit rendre ni un lien utilisable, ni la liste des adresses qu'un
  inconnu a essayées. `user_id`, lui, est en clair : le COMPTE se nomme
  (jointure `users`, en **une** requête — un SELECT par ligne ferait autant
  d'allers à Neon que de demandes). Une demande sur une adresse inconnue reste
  anonyme, par construction.
  ⚠️ Le cliquet correspondant n'a mordu qu'au SECOND essai : la première
  injection remplaçait une colonne du SELECT que le code dépaquette dans
  `_expire` et n'utilise jamais — rien ne fuyait, et le test restait vert à
  juste titre. Une fuite réelle demande DEUX gestes : lire l'empreinte **et** la
  mettre dans la réponse.
- ⚠️ **Une instance sans la table est un ÉTAT, pas une erreur.** La
  réinitialisation n'est déployée que sur staging et le pilote : `nouveau-point`
  a des dizaines de commits de retard et sa base ne porte pas
  `password_resets`. L'écran dit « pas encore déployée » ; afficher une erreur
  de base de données enverrait chercher une panne qui n'existe pas.
- Les instances sont lues **en parallèle** : en série, trois bases Neon froides
  font trois fois ~1 s pour des lectures indépendantes.
- Un seul chiffre porte une couleur, et c'est celui sur lequel on agit : les
  demandes **restées sans suite**. Tout colorer, c'est ne rien signaler. Les
  comptes sont triés par nombre de demandes décroissant — celui qui redemande
  sans cesse est celui qui a un problème.
- La série est en **barres, pas en courbe** : entre deux jours il n'y a rien à
  lisser, ce sont des événements comptés. L'échelle est celle du maximum
  observé, sinon toute série peu fournie serait plate.

#### La boîte : lecture stricte

- IMAP sur `HUB_IMAP_USER` et `HUB_IMAP_PASSWORD` (`imaplib`, `email` :
  bibliothèque standard, aucune dépendance de plus).
- ⚠️ **`select(readonly=True)` et `BODY.PEEK`** : rien n'est marqué comme lu,
  rien n'est déplacé, rien n'est supprimé. Et seuls les **en-têtes** sont
  téléchargés — ni corps, ni pièces jointes : on cherche à savoir ce qui est
  revenu, pas à lire le courrier de quelqu'un.
- Les messages sont classés **rejet / réponse automatique / réponse**, les
  rejets d'abord : c'est la seule nature sur laquelle on agit.
- ⚠️ **Il faut un SECOND mot de passe d'application**, distinct de celui qui
  sert à envoyer : révoquer l'un ne doit pas couper l'autre. Et un mot de passe
  d'application Google **n'est pas limitable** — il ouvre la boîte en lecture ET
  l'envoi SMTP. C'est inhérent au procédé, pas un oubli : Google n'offre pas de
  portée plus étroite. L'écran nomme les deux secrets et le dit.
- Sans identifiants, la moitié s'éteint **proprement** et dit QUOI faire. Un
  « non configuré » sec envoie chercher ailleurs.
- ⚠️ **Une variable d'environnement VIDE n'est pas une variable absente** —
  troisième fois que ce défaut se présente. `--update-env-vars` est additif,
  mais il CRÉE la variable même quand le secret n'existe pas : elle arrive
  présente et vide, et `getenv(cle, defaut)` ne regarde alors jamais son défaut.
  Le workflow ne pose donc les deux variables que si les deux secrets sont
  **non vides**, et `boite()` teste la VALEUR, pas la présence de la clé.

#### Deux pièges du hub, dont un déjà payé

- ⚠️ **Le rendu ne bloque JAMAIS sur une lecture.** C'est la leçon de `/panel` :
  la route y interrogeait l'instance pour deux nombres et retenait le HTML le
  temps d'un appel inter-services — 25 s d'attente, puis une page qui annonçait
  « l'instance ne répond pas » alors que tout allait bien. Ici une base Neon
  froide demande ~1 s et IMAP deux à quatre secondes. Le squelette part tout de
  suite, les deux moitiés arrivent par `/api/courrier/reset` et
  `/api/courrier/boite`, **en parallèle**, et chacune s'affiche dès qu'elle est
  là : une boîte lente ne retient pas les chiffres. Cache court (90 s et 120 s)
  — on vient y voir ce qui arrive MAINTENANT.
- ⚠️ **`@app.route("/courrier", endpoint="courrier")`, explicitement.**
  `page_active` vaut `request.endpoint` et la nav le compare à la clé de
  `inventaire.PAGES` : sans cet `endpoint`, l'entrée de nav ne s'allumerait
  jamais. Et la vue ne peut PAS s'appeler `courrier` — elle masquerait le module
  du même nom dans `hub/app.py`.

#### Mise au point

Le banc vit dans le répertoire de travail de la session, pas dans `tools/` :
une base SQLite semée, le hub monté en mémoire par son client de test, et on
LIT le JSON et le HTML. ⚠️ Pas de capture d'écran — le volet de mise au point
**ne peint pas** (transitions figées en cours de route, observateurs muets),
c'est écrit plus haut et c'est toujours vrai. Mesuré : 6 demandes / 2 abouties /
4 sans suite / 1 adresse inconnue, trois comptes nommés avec leur langue, une
troisième instance « pas encore déployée », **zéro empreinte dans la réponse**,
et la nav allumée sur `/courrier` comme éteinte ailleurs.

Tests : `tests/test_124_hub_courrier.py` (25 cas ; **sept gardes retirées une
par une, sept cliquets tombés**). ⚠️ Ils **sautent dans l'arbre d'image** : le
hub est un service séparé et la purge bytecode retire ses `.py`, que
`spec_from_file_location` exige. Même garde que la fixture `pulse_app`,
`test_65`, `test_107` et `test_111` — un test qui rougit toujours n'est plus lu,
et le jour où il a raison personne ne regarde.

**Reste à faire, et c'est une action de l'utilisateur** : créer le second mot de
passe d'application, puis poser `HUB_IMAP_USER` et `HUB_IMAP_PASSWORD` en
secrets GitHub. Tant qu'ils manquent, les chiffres fonctionnent et la boîte dit
calmement ce qu'il lui faut.

#### « J'ai pourtant déjà ce qu'elle demande » — non : ce sont d'autres secrets (2026-11-19)

Signalé après coup, capture des secrets du dépôt à l'appui. **Rien n'était
cassé.** `HUB_IMAP_USER` et `HUB_IMAP_PASSWORD` n'existent tout simplement pas
dans `Settings → Secrets → Actions` — le workflow les lit (`deploy-hub.yml`,
étape *Deploy to Cloud Run*) et ne les pose que si **les deux** sont non vides,
donc le service n'en voit aucun et la page dit vrai.

⚠️ **Ce qui existe, et qui n'a rien à voir** : `MAIL_USERNAME`,
`MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`. Ceux-là font **ENVOYER
l'application** — ils sont posés sur les services de l'app par
`deploy-staging.yml`, `deploy-officielle.yml` et `deploy-beta.yml`. Le hub a
son propre service Cloud Run : **il ne les voit pas**, et la séparation est
voulue (révoquer la lecture ne doit pas couper l'envoi). Les noms se
ressemblent, ils sont dans la même liste, et on les prend pour les bons.

Correction apportée : `courrier.boite()` rend désormais `manque` et `pose` — la
page **nomme** ce qui manque (l'un, l'autre ou les deux) au lieu d'un « non
configuré » global, et affiche un encart qui dit explicitement que
`MAIL_USERNAME` / `MAIL_PASSWORD` ne sont **pas** lus ici. Les trois étapes
pointent le bon écran GitHub (*Secrets and variables → Actions → New repository
secret*) et rappellent que le workflow n'écrit les variables que si les deux
secrets existent. `inventaire.SECRETS` nomme les deux familles côte à côte,
avec la différence en toutes lettres.

#### ⚠️⚠️ La livraison a cassé TOUT le hub, et pour deux raisons (2026-10-29)

Rapporté par l'utilisateur après le déploiement : la page Courrier n'affichait
que « Lecture impossible : No module named 'psycopg' » sur les trois instances,
et **le reste du hub s'affichait en HTML nu** — liens soulignés, icônes noires,
police par défaut. Deux défauts indépendants, tous deux introduits par cette
livraison.

**1 · Une règle CSS jamais fermée a emporté la feuille entière.**
La palette d'une section tient sur **deux lignes** :

```
.page--ci{--p1:…;--p5:#4566ae;
  --p6:…;--p-touche:#a9bef0}
```

J'ai inséré `.page--courrier{…;` juste au-dessus, **sans sa seconde ligne ni son
accolade**. Le navigateur avale alors tout ce qui suit dans le bloc resté
ouvert : la feuille ne s'applique plus du tout, sur toutes les pages. Mesuré
après coup : **349 accolades ouvrantes pour 348 fermantes**.
⚠️ Le symptôme ne désigne pas sa cause — on voit « le hub est cassé », pas « une
accolade manque » : le défaut est à une ligne, l'effet est global.
⚠️ **Et le test qui aurait dû le voir cherchait la PRÉSENCE d'une chaîne**
(`.page--courrier` est bien dans le fichier), pas la VALIDITÉ du fichier. Une
insertion se vérifie sur la STRUCTURE — c'est exactement la leçon déjà écrite
pour les `<div>` orphelins de la doc technique, et pour les commentaires HTML de
`test_85`. Elle vaut aussi pour le CSS.
⚠️ Mon banc local ne pouvait pas le voir non plus : il vérifiait que
`courrier.css` était **lié** dans la page, pas que `hub.css` **parsait** encore.

**2 · `SQLAlchemy>=2.0,<3` a installé 2.1.6, qui ne parle plus psycopg2.**
`postgresql://` désignait le pilote **psycopg2** en SQLAlchemy 2.0 ; depuis
**2.1**, il désigne **psycopg (v3)**. L'image du hub, construite sur une
fourchette, a pris la dernière du jour — 2.1.6 — et chaque lecture est morte sur
« No module named 'psycopg' », alors que `psycopg2-binary` était bien installé.
⚠️ **Invisible en local** : le venv de développement est resté en **2.0.45**. La
suite restait verte pendant que l'image partait sur autre chose — exactement le
piège du 2026-09-26, et exactement la raison pour laquelle le contrôle lit le
FICHIER et pas l'environnement.
⚠️ **La leçon du 27/09 n'avait été appliquée qu'à la racine.** `hub/` et
`pulse/` étaient restés en fourchette : **`pulse/` portait donc la même mine** et
serait tombé de la même façon à son prochain déploiement, sans qu'un seul commit
ne change.

Deux correctifs, et ils sont complémentaires :
- **le pilote est NOMMÉ dans l'URL** (`postgresql+psycopg2://`, posé par
  `load_sources`) : une URL qui dit son pilote ne dépend plus du tout de ce que
  pip a installé. Une URL qui en désigne déjà un n'est pas réécrite ;
- **les versions sont épinglées à l'exact** dans `hub/` et `pulse/`.
  ⚠️ **Gelées sur ce que la fourchette installait déjà** (`Flask==3.1.3`,
  `gunicorn==23.0.0`) : un correctif d'incident ne saute pas trois majeures de
  gunicorn sur deux services qu'on ne peut pas éprouver ici. S'aligner sur les
  `26.2.0` de la racine est un CHANGEMENT à part — suite ET image rejouées.

**Les cliquets qui manquaient**, les deux vérifiés rouges sur le défaut remis
tel quel :
- `test_85::test_chaque_feuille_de_style_ferme_ses_regles` — équilibre des
  accolades **et** règle ouverte DANS une autre, sur les 58 feuilles de l'app et
  du hub. Commentaires et chaînes retirés d'abord (une accolade dans un
  `content: "{"` n'est pas une accolade de structure) ; seules les at-règles
  (`@media`, `@supports`) ont le droit d'en contenir d'autres ;
- `test_72::test_les_services_separes_epinglent_AUSSI` — `hub/` et `pulse/`,
  paramétré ;
- `test_124::test_le_pilote_postgresql_est_NOMME_dans_l_url`.

⚠️ **Deux fois dans la même journée, un `\n` écrit dans un heredoc a produit un
VRAI retour à la ligne** au lieu de la séquence d'échappement — une fois dans le
script Python embarqué de `deploy-hub.yml` (YAML invalide), une fois dans une
chaîne de `test_72` (SyntaxError). Les deux ont été vus tout de suite parce
qu'un contrôle les relisait. Écrire la séquence par `chr(92) + "n"`, ou passer
par un fichier plutôt qu'un heredoc.


### Module « Atelier » du hub — le plan de travail (2026-11-19)

`/atelier` — une **toile infinie** où poser tout ce qui ne tient pas dans un
ticket : notes, listes à cocher, captures collées, liens, cadres de
regroupement, et surtout des **maquettes de pages de l'application** sur
lesquelles on accroche les fonctionnalités. `hub/atelier.py`,
`hub/templates/atelier.html`, `hub/static/atelier.{css,js}`.

**Le geste central, c'est le badge.** Une note ou une ligne de liste porte un
badge « *page · section* ». La maquette, en face, affiche dans chaque section
tout ce qui lui est rattaché. On réordonne les sections à la souris, on les
renomme, on change leur genre (en-tête, liste, tableau, formulaire, graphique,
panneau, pied) — c'est un **schéma pour penser la structure**, jamais un rendu
de l'app. Trois chemins pour rattacher : le bouton ⊕ de la note, le rail
« Pages & sections », ou lâcher la note sur la section.

- ⚠️ **Le navigateur tient la toile (IndexedDB), le serveur n'est qu'un
  MIROIR.** L'ordre inverse rendrait chaque frappe tributaire d'un
  aller-retour. Conséquence assumée : **l'atelier marche sans aucun secret** —
  `HUB_ATELIER_DB` absente, tout vit en local et la page le dit, avec l'export
  fichier comme filet. Un outil de travail qui réclame un secret avant la
  première note n'est pas un outil de travail.
- ⚠️ **`indexedDB` et pas `localStorage`** : ce dernier plafonne autour de 5 Mo
  pour tout le domaine. Une dizaine de captures suffisaient à faire échouer un
  enregistrement **en silence**.
- ⚠️ **Les captures sortent du document** (table `hub_atelier_piece`, une
  data-URL immuable par identifiant de contenu). Inlinées, chaque
  enregistrement repousserait plusieurs Mo d'images inchangées pour un titre
  corrigé. Elles sont réduites à 1600 px / WebP q0.86 **avant** d'être rangées.
- ⚠️ **Une base À SOI, jamais celle d'une instance.** `HUB_DBS_B64` porte les
  bases des clients et ne se lit qu'en lecture seule ; l'atelier écrit.
  `test_156::test_l_atelier_n_ouvre_JAMAIS_une_base_d_instance` interdit la
  moindre mention croisée dans le code (commentaires exclus).
- ⚠️ **`navigator.sendBeacon` ne poste qu'en POST** : la route
  `/api/atelier/toile/<cle>` accepte donc POST en plus de PUT. C'est elle qui
  pousse la dernière frappe à la fermeture de l'onglet — un 405 là ne se voit
  nulle part, la page n'existe déjà plus.
- ⚠️ **`rev` est un garde-fou, pas un verrou** : une écriture partie d'une
  révision plus ancienne que celle en base rend 409 avec la version en place,
  plutôt que d'écraser le travail d'un onglet resté ouvert ailleurs.
- ⚠️ **`hidden` ne vaut qu'un `display:block`.** Les `display:grid` / `flex` de
  la feuille le piétinaient : l'aide, le rail et le sélecteur de page
  s'affichaient en permanence par-dessus la toile. Neutralisé en tête de
  `atelier.css`, et tenu par un test.
- ⚠️ **La signature d'une maquette inclut ce que les AUTRES pièces lui
  accrochent.** Sans ça, rattacher une note ailleurs n'invalidait pas son
  rendu : le badge apparaissait sur la note et la section restait vide — on
  croyait le rattachement perdu.
- **Au passage** : `base.html` expose le bandeau en `{% block heros %}` (une
  page plein cadre le remplace), et la nav passe à **neuf** entrées — d'où
  `navbar-in` à 1400 px et des pilules resserrées, sinon « Dépôt & CI » sortait
  du cadre sans ascenseur.

#### Modèles — le plan de l'app, posé en un clic (2026-11-19)

`hub/atelier_modeles.py` : des pièces prêtes à poser, servies par
`/api/atelier/modeles` et `/api/atelier/modele/<cle>`. Trois entrées — les
**14 pages de l'application** (82 sections, chacune avec ce qu'elle porte), la
**liste des chantiers**, et les deux ensemble.

- ⚠️ **Ce fichier DÉCRIT l'app, il ne la lit pas.** Le hub est un service
  séparé : ni gabarits, ni blueprints, ni base. Relevé le 19/11/2026 sur
  `staging` ; quand une page bouge, c'est là qu'on le reporte. Un test
  interdit tout `create_engine` / `HUB_*` dans ce module : ce sont des données
  de dépôt, pas de l'état.
- ⚠️ **On POSE, on n'importe pas.** L'import de sauvegarde remplace toute la
  toile ; un modèle s'ajoute à droite de l'existant, reste sélectionné, et
  Ctrl+Z le retire d'un coup.
- ⚠️ **Les chantiers visent leur page par NOM** (`page_ref`), pas par
  identifiant : ils se rattachent à des maquettes posées il y a trois jours
  comme à celles du même modèle. `test_156` vérifie que chaque couple
  (page, section) existe — une faute de frappe ne lève rien, elle fait
  disparaître le badge en silence.
- ⚠️ `trouverPageParNom` parcourt **toutes** les maquettes homonymes :
  s'arrêter à la première laissait un chantier sans badge dès qu'une vieille
  maquette du même nom traînait sans la bonne section.
- Les sections portent désormais un champ `quoi` — ce qu'elles contiennent
  dans l'app. Masqué tant qu'il est vide, pour qu'une maquette qu'on esquisse
  n'affiche pas dix invites grises.

#### Deux corrections d'usage, au premier retour (2026-11-19)

Rapporté après la première ouverture : « on ne peut pas se déplacer » et
« je ne vois pas ce que tu décris, j'ai l'ancienne toile par défaut ».

- ⚠️ **Glisser le fond DÉPLACE la toile.** C'était la sélection au lasso, et
  le déplacement demandait Espace, le clic du milieu ou Alt — autant dire
  rien pour qui n'ouvre pas l'aide. Le lasso passe sous **Maj + glisser**
  (même modificateur que le clic qui ajoute à la sélection), un clic sans
  déplacement désélectionne toujours, et le curseur du fond est une main.
- ⚠️ **Le bouton « Modèles » est à l'ÉTABLI**, libellé, pas en icône muette
  au fond de la barre du haut : personne ne l'avait vu, et le plan de l'app
  restait à poser. Un modèle est une pièce qu'on pose — sa place est avec les
  six autres. La toile de départ et l'écran vide y renvoient aussi.

#### La molette zoome, et la maquette se LIT (2026-11-20)

« Il faut que la molette zoome et dézoome », et « les données du modèle des
pages, là tout est compact et serré, on comprend pas trop ». Les deux étaient
exacts, et le second se mesurait.

**La molette zoome, sans modificateur.** Le zoom était derrière Ctrl et la
molette nue faisait défiler : sur un plan sans bord, c'est le geste inverse de
celui qu'on fait. Maj + molette défile, un balayage HORIZONTAL ne zoome jamais
(deux doigts qui glissent de côté ne demandent pas un zoom), et Ctrl + molette
reste accepté — c'est le pincement d'un pavé tactile.

- ⚠️⚠️ **Le pas se NORMALISE avant d'entrer dans le zoom.** Un cran vaut
  **100** en pixels (Chrome), **3** en lignes (Firefox) et **1** en pages :
  avec le facteur brut d'origine (`0,99^deltaY`), le même cran donnait
  **×0,37** d'un côté et **×0,97** de l'autre. On ramène tout en pixels (une
  ligne = 33 px), on borne la rafale d'inertie d'un pavé tactile à ±220, et un
  cran vaut alors **×1,128** partout. Mesuré : Chrome 1,128 / Firefox 1,126, et
  le point sous le curseur ne bouge pas d'un pixel.

**La maquette : le croquis était la chose la plus LOURDE de chaque section.**
Mesuré avant de redessiner : une bande de barres colorées de ~30 px posée sous
chaque titre, plus lourde que le nom (11,5 px) et bien plus que le texte —
celui-là même qui dit ce que la section porte, en **10,8 px italiques gris**.
Dix sections faisaient un mur de barres. Et le genre était écrit DEUX fois : le
croquis le dessinait, un mot le répétait à droite du titre.

- **Le croquis devient une VIGNETTE de 32 × 25 px**, devant le nom, et il
  porte le choix du genre : le `<select>` est étendu dessus en transparence.
  Un seul objet, qui se lit d'un coup d'œil et qui se clique — le menu natif
  s'ouvre sous la vignette, et c'est là qu'on lit le mot.
  ⚠️ `pointer-events: none` sur le croquis, sinon il intercepte le clic du
  select posé dessus.
- **Ce que la section porte devient le CORPS** : 12,3 px, police du corps,
  encre normale. Il était en italique grise, c'est-à-dire en note de bas de
  page — alors que c'est la seule chose qu'on vienne lire.
- **Les cartes passent de 340 à 400 px**, et ⚠️ **la hauteur se CALCULE sur le
  texte**. Le forfait de 96 px par section laissait défiler à l'intérieur toute
  page dont les phrases dépassaient deux lignes, et une maquette qu'on ne voit
  jamais en entier ne sert plus de plan. Les quatre constantes sont **mesurées
  à l'écran** sur les 83 sections : 56 signes par ligne au pire, 20 px la
  ligne, 62 px le reste d'une section, 134 px le haut et le bas. Relevé après
  coup : **aucune page sous-estimée, 14 maquettes sur 14 sans défilement
  interne**, la plus juste gardant 16 px.
- ⚠️ **Une section PORTE les chantiers qu'on lui accroche** : sans eux au
  calcul, la page la plus chargée défilait encore de 69 px. `_hauteur` reçoit
  donc le compte par (page, section) ; 33 px la première pastille, 29 les
  suivantes.
- ⚠️ **Le badge « page · section » d'une ligne de liste ne se replie QUE si
  une barre de défilement a volé 15 px à la carte** — c'est-à-dire seulement
  si la hauteur est trop courte. Le calcul juste est donc son propre point
  fixe : assez haut, rien ne défile, rien ne se replie. 81 px de réserve
  prévus pour ce repli ont été retirés une fois le point fixe atteint.
- **Les pastilles de chantier prennent toute la largeur**, une par ligne.
  Bornées à 150 px et côte à côte, elles rendaient « Échanger les boutons
  « Ouv… » — on ne savait plus de quel chantier on parlait, et deux pastilles
  tenaient de toute façon sur deux lignes : la largeur ne coûte rien.
  ⚠️ `min-width: 0` sur la pastille **et** sur son texte : la taille minimale
  automatique d'un élément flex est celle de son CONTENU, et un libellé en
  `nowrap` débordait de 13 px hors de sa propre boîte.
- ⚠️ **Une maquette posée à la main fait la même largeur que celles du
  modèle** (`GABARIT.maquette.w` = `LARGEUR`), sinon le plan part en dents de
  scie dès qu'on ajoute une page. Tenu par un test qui lit les deux fichiers.

Tests : `tests/test_156_hub_atelier.py` passe de 51 à **62 cas** ; **11 défauts
remis un par un, 11 cliquets tombés**. Même garde de saut dans l'arbre d'image
que `test_124`.

**Pour brancher le miroir (facultatif)** : une base PostgreSQL à soi →
secret `HUB_ATELIER_DB` → rejouer *Deploy → Optiq Hub*. Les tables se créent
toutes seules au premier appel.


## Provisionnement — compléter une carto avec un Excel client

`tools/provisioning/provision.py` sait aussi **injecter les tâches d'un tableur
client dans une carto déjà en place** (bloc `tasks_excel` du plan) : il réutilise
le pipeline d'import de l'app (`Code/routes/import_full`) — même lecture du
fichier, mêmes get-or-create outils/rôles, déduplication des tâches par nom (donc
idempotent). `Guarantor` → rôle **Garant** de l'activité, `Doer`/`Approver` →
rôles de tâche, `Skills` → compétences.

- ⚠️ **L'appariement est une table explicite** (`data/*_mapping.json`), pas du
  fuzzy : les libellés du client ne sont pas ceux de la carte harmonisée
  (« Identify Part » → « Develop Preliminary Technical Solution »). L'appariement
  automatique ne sert que de filet, et seulement au-delà de 90 %.
- **Cloisonnement par compte** : `owner_email` + `require_existing` + le nouveau
  `match_name_contains` (retrouve l'entité même renommée, **chez ce propriétaire
  seulement**). Si l'entité n'existe pas chez lui, le script s'arrête sans rien
  écrire — même si une entité du même nom existe chez quelqu'un d'autre.
- `plans/maelg_fluidclip_tasks.json` : carto « FluidCLip » du compte
  `mael.pierre.girardin@icloud.com` complétée par `CLIP_ RFQ Tasks.xlsx`.
  ⚠️ **Sept autres comptes de l'instance pilote possèdent une entité du MÊME
  nom** — d'où le cloisonnement par propriétaire. Appliqué le 2026-08-30 sur
  `optiqfluent_pilot` (Neon) : 25/25 activités appariées, 96 tâches, 28 outils,
  14 rôles, 53 compétences ; entités des autres comptes inchangées (0 tâche).
  Rejouable tel quel (`--dry-run` d'abord).
- ⚠️ **La colonne Skills sert aussi à dire qu'il n'y a RIEN à savoir faire** :
  « No Special skills required » (27 lignes du fichier) et « - » devenaient des
  compétences portant la phrase elle-même. `_est_non_competence()` écarte ces
  mentions d'absence (regex « no/not/aucun… » + « skill/compétence », plus une
  liste de valeurs vides : `-`, `n/a`, `none`…). 17 lignes supprimées après coup
  sur le pilote : 53 → 36 compétences.
- ⚠️ **`--dry-run` n'était pas étanche** : `_sync_carto_to_db` finit par un
  `commit()`, qui figeait tout ce que le plan avait écrit avant lui (le rollback
  final n'annulait plus que la dernière étape). `_neutraliser_commits()` remplace
  `commit` par `flush` en simulation. Vérifié au banc : un plan qui crée compte +
  entité + carto + Excel laisse la base vide après `--dry-run`.
- `plans/pilote_fluidclip_tasks.json` : les **six** comptes ARaymond gardent leur
  carto FluidClip et reçoivent les données de l'Excel ; Maël reçoit en plus
  **« Entité de rendu FluidClip »** (copie de LEUR carto + les mêmes données) pour
  contrôler leur rendu. Appliqué le 2026-08-30 : 96 tâches / 28 outils / 32 rôles /
  36 compétences par entité (les tâches saisies à la main par ces comptes sont
  conservées : Hubert 100, Madhuri 97, Vaishali 97). Priya Bhivare n'avait aucune
  FluidClip : la sienne a été **créée** depuis le même modèle (42 activités,
  96 tâches). ⚠️ Une entité portant un bloc `carto` est **re-synchronisée à
  chaque rejeu**, et `_sync_carto_to_db` efface les rôles absents de la carte :
  les rôles issus de l'Excel sont donc recréés à chaque passage (leurs `id`
  changent). D'où l'option **`--only EMAIL`**, qui rejoue un plan pour un seul
  compte.

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
### Couverture complète de la traduction FR/EN (2026-09-16)

`tests/test_78_i18n_couverture.py` — 40 cas. L'app traduit par **quatre
mécanismes**, et aucun ne lève d'erreur quand il échoue : c'est ce silence que
ce fichier ferme, mécanisme par mécanisme.

| Mécanisme | Comment il échoue |
|---|---|
| `t('cle')` (catalogue Python) | clé absente en EN → **repli silencieux sur le français** ; absente partout → la clé brute s'affiche |
| `window.XXX_I18N` injecté par un gabarit | clé oubliée → le JS sert son **repli français en dur** |
| `data-i18n="cle"` (page Compétences) | clé inconnue du catalogue JS → le français du gabarit **reste affiché** |
| texte écrit en dur dans un gabarit | ne passe par rien : français dans les deux langues |

**Le contrôle le plus fort ne dépend d'aucun mécanisme** : on demande les
11 pages EN ANGLAIS et on y cherche les **844 phrases françaises** du catalogue
(celles dont l'EN diffère). Une phrase du catalogue français n'a aucune raison
d'apparaître sur une page anglaise, quel que soit le chemin qu'elle a pris.
- ⚠️ **Et cela ne doit jamais accuser une DONNÉE.** Les noms d'activités, rôles,
  outils, savoir-faire sont français dans le jeu de test. Deux garde-fous :
  les libellés de dix modèles sont relus en base et retirés des pièges, et un
  piège doit être une **phrase** (≥ 12 signes, au moins une espace). Sans le
  second, « Savoir-faire » faisait tomber la page Activités — parce qu'un AUTRE
  fichier de tests avait créé un savoir-faire de ce nom. ⚠️ Le défaut ne se
  voyait **qu'en suite complète**, la base étant partagée : un fichier vert tout
  seul ne prouve rien ici.

**Ce que le contrôle a trouvé, et qui est corrigé :**
- ⚠️ **`"{{ t('x') }}"` entre guillemets dans un `<script>` : 34 occurrences,
  dont 7 déjà visiblement abîmées.** Le navigateur décode les entités HTML dans
  un ATTRIBUT, jamais dans un script — `propose.err_saving` arrivait donc au JS
  sous la forme « Impossible d&#39;ajouter… », affichée telle quelle. Mesuré au
  rendu : en dur → `c&#39;est`, avec `|tojson` → `c'est`. Toutes converties
  (`display_list.html` 32, `competency_modal.html` 2). **En attribut la même
  écriture est correcte** — d'où un contrôle strictement limité aux blocs script.
- **Sept libellés qui avaient déjà leur version anglaise** mais que le gabarit
  n'employait pas : le `<title>` de la liste des activités, le titre de la
  pop-up d'import des tâches, le sous-titre du bandeau Compétences, et quatre
  sur Projection métier / import IA. Trois clés nouvelles créées au passage.
- ⚠️ **`<html lang="fr">` écrit en dur sur 8 gabarits.** Un lecteur d'écran
  annonçait la page en français et le navigateur proposait de la traduire
  *depuis* le français — alors qu'elle s'affichait en anglais.
- ⚠️ **`/roles/view` n'existe pas** (c'est `/roles_view/`) : la page rendait 404,
  le contrôle la **sautait**, et elle passait pour vérifiée. Les chemins viennent
  désormais d'`url_map`. Trois pages ajoutées.

**La dette est ÉCRITE, et elle ne peut que décroître.** 76 fragments français en
dur sur 12 gabarits — dont trois écrans jamais traduits (`import_full_modal` 25,
`projection_metier` 14, `import_tasks_modal` 11). Les traduire demande d'écrire
de vraies tournures anglaises, pas de déplacer du texte : c'est un travail à
part. `TestFrancaisEnDur` tient donc un **cliquet** : un gabarit hors inventaire
doit être propre, un gabarit inventorié ne doit pas empirer, et
`test_l_inventaire_suit_la_realite` exige de **baisser le plafond** dès qu'on
nettoie — sans quoi un retour en arrière se cacherait sous une marge.

⚠️ Pièges d'analyse rencontrés, tous corrigés dans le fichier :
- l'injection s'écrit `window.X = Object.assign(window.X || {}, { … })` —
  prendre « la première accolade après le `=` » tombe sur le `{}` du repli et
  rend **zéro clé**, donc un contrôle vert qui ne regarde rien ;
- le compteur d'accolades ne saute ni les chaînes ni les expressions
  régulières : une accolade dans un littéral fait courir le « corps » d'une
  fonction jusqu'à la fin du fichier, et on attribuait alors à l'accesseur
  toutes les chaînes du fichier (« carto-wizard-popup » relevé comme clé) ;
- chaque test d'analyse est doublé d'un **garde-fou de volume**
  (`test_le_catalogue_est_bien_garni`, `test_le_jeu_de_pieges_est_consequent`) :
  si un jour les repères changent et que l'analyse ne trouve plus rien, les
  contrôles passeraient au vert en ne lisant plus RIEN.

### Organisation des branches et des bases (2026-09-10)

| Branche | Instance Cloud Run | Base | À quoi elle sert |
|---------|--------------------|------|------------------|
| `staging` | `devoptiq-staging` | `devoptiq_sandbox` | **Bac à sable Maël + Claude.** On y développe sans pression, on pousse quand une nouveauté est finie. |
| `nouveau-point` | `devoptiq` | `neondb` | **Version officielle interne AFDEC.** On n'y pousse que du fini. |
| `optiqfluent-staging` | `optiqfluent-staging` | `optiqfluent_pilot` | **Pilote ARaymond (Inde).** On n'y touche pas ; les correctifs partent le soir (nuit là-bas). |

- ⚠️ **`nouveau-point`, pas `main`.** C'est cette branche qui alimente le service
  `devoptiq` (vérifié dans la console Cloud Run). `main` n'a pas bougé depuis mai.
  L'inventaire du hub annonçait « push sur main » et un `deploy-beta.yml` qui n'existe
  pas : corrigé.
- **`deploy-officielle.yml`** (2026-09-10) : `nouveau-point` → service `devoptiq`,
  calqué sur `deploy-staging.yml`. Il manquait — la branche avançait sans que
  l'instance bouge, et `devoptiq` a servi le code de mai 2026 pendant quatre mois.
  Sans `WITH_TESTS` (le panel de tests reste le rôle de staging : `/testpanel` n'a
  aucune authentification et chaque appel coûterait deux minutes de CPU).
- ⚠️ **Un service, un chemin de déploiement.** `deploy-production.yml` visait le
  MÊME service `devoptiq` sur push de **`prod-stable`**, branche figée au 07/05/2026
  (pré-OptiqCarto) : un push là-bas aurait ramené la version officielle quatre mois
  en arrière. Son déclenchement automatique est retiré — il reste lançable à la main,
  dans le même groupe `concurrency` que `deploy-officielle.yml` pour que les deux ne
  déploient jamais en même temps.
### Importer des données — la fenêtre d'import de la page Carte (2026-09-19)

Remplace l'ancien « Import IA global » : `import_full_modal.html`,
`import_full.js` et `import_full.css` sont supprimés, et les 57 clés `impf.*`
qu'eux seuls lisaient ont quitté le catalogue (restent celles que la route
`import_full.py` renvoie). Serveur : `Code/routes/import_hub.py` (`/api/import`) ;
écran : `import_hub_modal.html` + `static/js/import_hub.js` +
`static/import_hub.css` (clés `imph.*`, injectées par `IMPH_I18N` en `| tojson`).

⚠️ **La même fenêtre sert à la page Comptes** (`?pour=comptes`), où elle ne
propose que les collaborateurs — voir « La page Comptes refaite » plus bas.

- **Une carte par nature** — rôles, tâches, outils — dans la couleur de la page
  où vivent ses données (Rôles `#059669`, Activités `#7c3aed`, Outils
  `#ea580c`), avec ses colonnes (obligatoires
  marquées) et sa portée. Plus l'**import multiple** : plusieurs fichiers, ou un
  classeur dont CHAQUE feuille est reconnue (nature déduite des en-têtes,
  départagée par le nom de la feuille ou du fichier).
- **Parcours** : lire → (organiser avec l'IA) → vérifier → importer.
  `GET contexte` · `GET modele/<nature|multiple>` · `POST lire` ·
  `POST organiser` · `POST verifier` · `POST rapprocher` · `POST importer`.
- **Lu tel quel quand c'est lisible** : xlsx/xlsm (valeurs calculées), csv
  (séparateur deviné, cp1252 en repli) ; en-tête cherché dans les dix premières
  lignes ; synonymes FR/EN comparés au MOT près (« prénom » ne contient pas
  « nom ») ; cellules fusionnées propagées ; mentions
  d'absence (« No special skills required », « - ») retirées DÈS la lecture —
  l'aperçu montre ce qui sera vraiment importé. ⚠️ `.xls` est refusé en clair :
  openpyxl ne le lit pas, l'accepter ferait échouer plus loin sans explication.
- ⚠️ **Le code ne devine pas.** Un fichier non reconnu n'est pas lu « à
  moitié » : l'écran dit ce qui manque, montre le début du fichier tel quel
  (colonnes repérées par leur lettre) et propose l'IA ou le modèle.
- ⚠️ **L'IA désigne les colonnes, elle n'écrit AUCUNE donnée** (prompt
  `import.correspondance`) : ligne d'en-tête et numéro de colonne par champ, puis
  le code relit les valeurs dans le fichier. Une réponse qui porterait des
  lignes est ignorée, un numéro hors du fichier écarté. L'écran montre la
  correspondance (« Adresse » → E-mail) et la confiance. Une IA qui réécrirait
  les lignes pourrait en inventer ; une IA qui désigne des colonnes se vérifie
  d'un coup d'œil.
- **La portée dépend de la donnée.** Rôles et outils vont dans une, plusieurs
  ou toutes les cartos, avec le statut « ajouté en partie » quand ils n'en
  manquent qu'à une partie ; une tâche va dans chaque carto où son activité
  existe.
  ⚠️ Seulement les cartos où le compte ÉCRIT (`can_edit`) : un identifiant venu
  du navigateur ne suffit jamais.
- **Une tâche se rattache à SON activité** : au nom près ou à 90 % de
  ressemblance ; en dessous, l'utilisateur choisit (les plus proches d'abord) et
  « Rapprocher avec l'IA » (prompt `import.enrich`) PROPOSE par le sens
  (« Identify Part » → « Develop Preliminary Technical Solution ») — dans un
  compte rendu, jamais directement dans la liste (voir plus bas). L'écriture
  passe par `injecter_groupes`, carto par carto.
- ⚠️ **Le garant ne déborde plus d'une activité sur la suivante** : la
  propagation des cellules fusionnées repart de zéro à chaque nouvelle
  activité. Un garant manquant se voit et se complète ; un garant FAUX lie un
  rôle à une activité qu'il ne tient pas.
- ⚠️ **Une feuille ambiguë n'est pas importée tant qu'on ne l'a pas dite**
  (« Nom | Description » : des rôles ou des outils ?) — « Tout importer » aurait
  créé des presses à injecter comme rôles.
- **L'import revérifie tout** — rien de ce que renvoie le navigateur n'est cru,
  pas même le statut d'une ligne — et un import multiple s'écrit en UNE
  transaction, dans l'ordre rôles → outils → tâches : un rôle créé par la
  feuille « Rôles » existe quand une tâche le désigne comme garant.
- ⚠️ **Les messages que la ROUTE renvoie s'affichent tels quels** (motifs de
  statut, erreurs) : ils passent par le catalogue comme le reste — c'était le
  troisième côté oublié de l'ancien écran.

⚠️ **`Role.hors_carte`** (migration à chaud) — le défaut de fond que l'import a
mis au jour. `_sync_carto_to_db` effaçait, à chaque enregistrement de la carte,
tout rôle absent de ses bandes : un rôle importé, créé depuis la page RH ou
désigné garant disparaissait avec ses titulaires et ses liens aux tâches.
Importer des rôles ne servait à rien. Les rôles créés hors de la carte portent
désormais la marque et survivent ; `reprendre_roles_hors_carte()`
(`roles_permanents.py`) marque UNE fois (marqueur `roles_hors_carte` en base)
ceux qui existaient déjà — reconnus à ce qu'ils manquent aux bandes de la carto
ENREGISTRÉE. Une carto sans diagramme lisible est laissée telle quelle.

⚠️ `/api/import-full/inject` — l'ancienne route, gardée pour ses fonctions —
écrivait dans l'entité active sans demander le droit d'y écrire : elle exige
désormais `can_edit`.

- ⚠️ Piège de test : `t("imph.t_" + x)` est relevé par `test_78` comme la clé
  « imph.t_ ». Écrire `t("imph.t_%s" % x)` ; ces clés construites sont tenues
  par `test_84::test_les_libelles_construits_existent_dans_les_deux_langues`.
- `import_tasks_modal.html` : « Télécharger le modèle » passe par le catalogue,
  sa dette tombe de 11 à 10 fragments.
- Mise au point : `tools/devrun_import.py` (port 8126, `/devrun/admin`) — deux
  cartos, des fichiers d'exemple servis sous `/devrun/fichier/<nom>` (propre,
  export RH désordonné, csv, tableau du client, classeur multiple avec une
  feuille ambiguë et une illisible) et une IA SIMULÉE. La simulation vit dans
  l'outil, jamais dans l'application.
- Tests : `tests/test_84_import_hub.py` (45 cas — lecture, IA, portée, import,
  transaction, droits, modèles relus dans les deux langues, reprise des rôles,
  listes de personnes reconnues et jamais importées ; la survie des rôles
  importés et le contrôle de l'ancienne route vérifiés **rouges** sur le code
  d'avant).

#### Les comptes s'importent depuis la page Comptes ; l'IA rend compte AVANT d'agir

- ⚠️ **L'import de la CARTE ne crée pas de comptes.** Créer un compte engage
  toute l'instance et relève de ceux qui les gèrent (`can_create_accounts`) :
  c'est la page Comptes, qui ouvre la même fenêtre avec `?pour=comptes`. La
  carte n'en propose pas la carte, un import multiple ne les prend jamais.
- **Une liste de personnes est RECONNUE, jamais importée** (`_personnes`) : une
  colonne titrée exactement « Nom » (ou « Nom complet »…) à côté d'un prénom ou
  d'e-mails (au titre, ou ≥ 60 % des valeurs d'une colonne). La feuille devient
  une part `comptes`, sans lignes, avec un lien vers `/comptes/?tab=import-tab`
  (qui ouvre l'onglet d'import) pour qui a le droit — sinon une phrase dit que
  c'est réservé.
  ⚠️ « Nom du rôle » n'est pas « Nom », et un tableau de tâches complet
  l'emporte toujours. En cas d'erreur, l'utilisateur a le dernier mot : « Lire
  quand même comme des rôles » (paramètre `comme` de `/lire`, qui force la
  nature).
- **Les compteurs disent ce qu'il ADVIENT des lignes, et de QUELLES lignes** :
  « 60 tâches ajoutées », plus « 60 New ». Six issues (`issue()`) — ajoutée,
  ajoutée en partie, écartée (décochée), déjà là, à rattacher, à corriger —
  libellées par nature et au pluriel (`tu_<issue>_<nature>`, `pas_*`).
  ⚠️ Décocher fait NAÎTRE une tuile (« 1 tâche écartée ») : `majCompteurs`
  redessine la rangée quand l'ensemble des tuiles change, et garde celle qu'on
  filtre même à zéro — la retirer sous le pointeur laisserait une liste sans
  titre.
- ⚠️ **Rien de ce que propose l'IA ne touche la liste sans compte rendu.**
  « Rapprocher avec l'IA » appliquait tout d'un coup : on retombait sur la
  liste, ses rattachements mêlés à ceux qu'on avait déjà validés, sans savoir
  lesquels venaient d'elle. Deux comptes rendus désormais :
  - **rapprochement** (`blocRapport`) : pour chaque activité, ce que l'IA
    propose, sa confiance et sa raison ; ce dont elle doute (`low`) arrive
    décoché ; « Appliquer n choix ». Ensuite la liste défile jusqu'aux groupes
    rattachés, les met en évidence, et « Ne voir qu'elles » les isole ;
  - **lecture** (`blocLecture`, « Organiser avec l'IA ») : champ → colonne du
    fichier → premières valeurs lues ; « Utiliser cette lecture » reste éteint
    s'il manque un champ obligatoire.
- **L'IA ne se relance pas pour rien** : ce qu'elle a examiné est mémorisé par
  part ET par portée (`S.examen`, clé = cartos visées : d'autres cartos, ce
  sont d'autres activités candidates). Si elle a déjà vu les activités
  restantes, la barre le dit (« choisissez-la dans la liste ») et propose
  « Revoir ses propositions » — rien de pré-coché, on revient sur un choix
  délibéré.
- **Sa raison est écrite dans la langue de l'écran** : elle s'affiche telle
  quelle. `/rapprocher` transmet `langue_des_remarques`, et `import.enrich`
  demande aussi de laisser un groupe dans `still_unmatched` plutôt que de
  forcer un rapprochement.
- **Trois styles pour un même fait.** Le résultat de l'IA dans la liste avait
  une apparence par niveau de confiance, et ressemblait à des boutons. C'est
  une LIGNE de texte sous le choix d'activité (`legende()`) : « Rattachée par
  l'IA », une jauge à trois barres et son mot (élevée / moyenne / faible), la
  raison en italique. Les autres origines prennent la même forme (« Même nom
  que dans la carto », « Nom proche (91 %) : vérifiez », « Choisie à la
  main ») : rien là ne se clique, rien ne doit en avoir l'air.
- Suite : 2412 passés. Éprouvé dans les deux langues sur
  `tools/devrun_import.py` (fichiers `moyens.xlsx` et `taches_blocs.xlsx`
  ajoutés, IA simulée qui choisit la nature la mieux couverte).

### La page Comptes refaite, et ce qui y a déménagé (2026-09-20)

**L'écran** (`gestion_compte_new.html` + `static/gestion_compte_new.css` +
`static/js/gestion_compte_new.js`) : plus d'onglets. Une liste, et la fiche
d'un compte PAR-DESSUS elle.

- ⚠️ **Créer et modifier posaient les mêmes questions dans deux écrans
  différents** — une page `edit_user.html` à part, avec sa propre identité
  visuelle, et le mot de passe en section séparée « sans risque d'autofill ».
  Une seule fiche désormais, trois groupes qui disent ce qu'on demande :
  identité · connexion · place dans l'organisation. Les libellés sont
  AU-DESSUS des champs (un `placeholder` disparaît dès qu'on tape) et le
  niveau d'accès se choisit en lisant ce qu'il ouvre, pas dans une liste de
  quatre mots. `GET /comptes/update/<id>` **redirige** vers la liste
  (`?edit=<id>`, la fiche s'ouvre dessus) ; `edit_user.html` est supprimé.
- **Les compteurs par palier SONT les filtres** de la liste, et chaque palier
  garde sa couleur de la tuile jusqu'à la pastille de la ligne.
- ⚠️ **`/comptes/create` n'empêchait pas de créer AU-DESSUS de soi** : un
  compte autorisé à créer des comptes se fabriquait un administrateur. Le
  niveau demandé est comparé au sien (`niveau_status` / `niveau`), comme le
  fait l'import depuis toujours. Le masquage du champ dans la page ne coûtait
  rien à contourner.
- **La liste ne fait plus deux requêtes par ligne** : les rôles de tout le
  monde sont chargés en deux requêtes, puis indexés en mémoire.

**L'import IA des comptes revient — page Comptes, et là seulement.** C'est la
MÊME fenêtre que la page Carte (`/api/import`, `import_hub_modal.html`),
ouverte avec `?pour=comptes` : elle ne propose alors que les collaborateurs et
s'ouvre DIRECTEMENT sur le dépôt (un choix à une seule carte n'est pas un
choix). L'ancien import Excel de la page (`/comptes/import_excel`, son
aperçu et son modale de format) est supprimé.
- ⚠️ `_peut(moi, type_)` : les comptes ne suivent pas les droits carto —
  `can_create_accounts` décide, et lui seul, **même sans aucune carto**
  (`verifier`/`importer` acceptent une liste de cartos vide pour `users` :
  les cartos ne servent qu'à attribuer le rôle).
- ⚠️ `_analyser_feuille` n'écarte une liste de personnes (`comptes`) que
  lorsque `users` n'est PAS une nature attendue : le repérage qui protège la
  carte ne doit pas écarter le fichier qu'on vient justement importer ici.
- ⚠️ Un import MULTIPLE ne prend jamais les comptes (`CARTO` = rôles, outils,
  tâches) : créer un compte engage l'instance, cela ne se glisse pas dans une
  feuille d'un classeur déposé sur la carte.
- Le reste est celui d'avant, restauré : nom complet scindé (« DUPONT Jean »,
  cas courant d'un export RH), statut refusé au-dessus du sien, rôle inconnu
  signalé ou créé (« créer les rôles absents »), mots de passe jamais renvoyés
  à l'écran et provisoires montrés UNE fois, téléchargeables en csv.

**« Droits par statut » quitte la page RH pour la page Comptes.** C'est ici
qu'on donne un statut à quelqu'un : c'est ici qu'on doit lire ce qu'il ouvre.
`GET|POST /comptes/droits` (lecture : administrateur ou qui crée les comptes ;
écriture : administrateur seul, colonne `admin` verrouillée). Les clés du
catalogue passent de `rh.right_*` / `rh.rights_*` à `droit.*`. La section 4 de
la page RH et son JS sont retirés.

Tests : `test_84` (53 cas, les comptes reviennent avec leurs droits),
`test_18`, `test_50`, `test_81` (l'URL des droits suit), et
`gestion_compte_new.html` sort de l'inventaire de dette de `test_78`.

### Page Carto : « Qui ouvre quelles cartos », en une matrice (2026-09-20)

Bouton **Accès** dans l'en-tête de la page Carte (coordinateurs et
administrateurs — `can_manage_access`, réglable par le tableau des droits).
Une fenêtre, une MATRICE : un rôle en ligne, une carto en colonne, une case à
cocher à l'intersection. Cliquer l'en-tête d'une **colonne** coche (ou
décoche) tous les rôles de cette carto ; cliquer un **rôle** fait de même sur
toutes les cartos. `GET|POST /cartography/api/access/matrice`,
`carto_acces_modal.html` + `static/js/carto_acces.js` + `static/carto_acces.css`.

- ⚠️ **On envoie des CASES, jamais la table entière.** Deux personnes qui
  règlent l'accès en même temps s'effaceraient l'une l'autre, et une case
  oubliée dans l'envoi fermerait un accès que personne n'a décidé de fermer.
- ⚠️ Les deux pièges de l'accès sont écrits DANS l'en-tête de chaque colonne :
  une carto **privée** ignore les rôles (la cocher la rend commune, ce que la
  réponse annonce en retour), une carto commune **sans aucun rôle est ouverte
  à tous** (y poser le premier rôle la restreint).
- Une ligne porte le nom du rôle ET la carto d'où il vient : deux cartos
  peuvent avoir un rôle du même intitulé.
- ⚠️ Cette matrice ne remplace pas la page **Partage** : là-bas on travaille
  UNE carto (ses titulaires, ses propositions, sa vignette), ici on regarde
  l'ensemble. Les deux écrivent la même table (`entity_role_access`) — ils ne
  peuvent pas diverger sur le fond.
- Tests : `tests/test_66_carto_sharing.py::TestLaMatriceDesAcces` (7 cas —
  le refus pour un `user`, la carto rendue commune, la colonne d'un coup, les
  cases non envoyées qu'on ne touche pas, une carto hors de portée ignorée, et
  le bouton absent pour qui ne règle rien). ⚠️ Ces cas montent LEUR propre
  carto : le décor du module est remanié par les tests de ménage (une bande
  retirée emporte son rôle), une matrice bâtie dessus dépendrait de l'ordre.

### Plusieurs développeurs de compétences pour une personne (2026-09-20)

C'était déjà vrai en base et dans les routes (`user_roles.manager_id`,
`/gestion_rh/dev_scope` qui ne touche jamais aux affectations des AUTRES
développeurs) : un collaborateur peut être suivi par Lou sur « Qualité » et
par Sacha sur « Logistique ». L'inverse est impossible **par construction** —
le lien vit sur la ligne (compte, rôle), qui porte UN développeur ; poser le
second remplace le premier.
Ce qui manquait : le dire. Tests : `test_80::TestPlusieursDeveloppeurs`
(3 cas). Banc : `tools/devrun_partage.py` sème un SECOND développeur
(`dev2@test.local`) — avec un seul candidat, le cas ne pouvait même pas se
jouer.

**La fenêtre refaite (2026-09-21)** — « on ne sait pas si cela enlève le
précédent ». Le panneau présentait un choix global (tous ses rôles / certains
rôles) puis une liste de cases : poser un second développeur avait l'air de
remplacer le premier. Il montre désormais la SEULE chose vraie — **un
développeur par rôle** — sous la forme d'une ligne par rôle tenu, chacune avec
SON développeur (« Qui accompagne Noe ? »). Cliquer une ligne la déplie sur les
candidats ; en choisir un n'écrit que CE rôle (`/gestion_rh/role_dev`), et la
phrase « Un développeur par rôle : en changer un ne touche pas aux autres » le
dit une fois pour toutes. En pied, « Le même pour tous ses rôles »
(`/gestion_rh/dev_scope`, `role_ids: null`) est un raccourci séparé.
- ⚠️ La fenêtre **reste ouverte** après chaque choix : on règle deux rôles de
  suite sans la rouvrir. La page se redessine derrière (`charger({discret})`) ;
  le panneau se raccroche au bouton RECRÉÉ (`raccrocher()`), et un drapeau
  (`tenirOuvert`) empêche le défilement de rattrapage de la refermer.
- La ligne qui vient d'être écrite s'éclaire une seconde (`is-recent`) : sans
  ça, rien ne montrait où l'écriture avait porté.

### Page Comptes : les tuiles filtrent enfin (2026-09-21)

⚠️ Cliquer une tuile ne faisait RIEN : le JS posait bien `hidden` sur les
lignes écartées, mais `.acc-ligne { display: grid }` l'emportait sur la règle
du navigateur `[hidden] { display: none }` — une règle d'auteur bat toujours
la feuille par défaut. `.acc-ligne[hidden] { display: none; }`. Deux phrases
d'en-tête ont aussi quitté la page (« Qui entre dans l'application… », « L'échelle
des quatre paliers ne change pas… ») : elles décrivaient ce que l'écran montre.

`tests/test_85_gabarits_bien_formes.py` — un commentaire HTML ouvert sans être
fermé (ou l'inverse) affiche du texte brut dans la page : c'est arrivé sur la
page RH, en retirant une section ligne à ligne. Le contrôle compte `<!--` et
`-->` dans chaque gabarit (commentaires Jinja retirés).

### Les propositions s'examinent depuis la page CARTE, toutes cartos (2026-09-21)

Elles vivaient dans la page RH (section ③), cadrées par la carto ACTIVE : celui
qui valide ne les voyait qu'en activant la carto visée — donc souvent jamais.
Un **bandeau d'alerte** sur la page Carte (`#cex-bandeau`, ambre) les annonce
désormais toutes (« 2 modifications proposées attendent votre décision · sur 2
cartos »), et le clic ouvre la **fenêtre d'examen** (`carto_examen_modal.html`
+ `static/js/carto_examen.js` + `static/carto_examen.css`, catalogue
`CEX_I18N` / clés `examen.*`) : la liste groupée par carto à gauche, la
proposition à droite — avant/après en image (la loupe ouvre le VRAI viewer),
ce qu'elle change, puis un commentaire et Refuser / Appliquer à la carto.
- **Source unique** : `carto_sharing.propositions_a_examiner(user)` — en
  attente, pas les siennes, et seulement là où `can_review(entity)`. Elle sert
  au bandeau (`activities_map._examen_en_attente`, rendu serveur : pas de
  bandeau qui clignote, ni de bandeau vide) ET à la liste
  (`GET /cartography/api/changes/a_examiner`) : le chiffre annoncé et la
  liste ouverte ne peuvent pas diverger.
- ⚠️ **Appliquer REMPLACE la carto par la version proposée.** Si la carto a
  bougé depuis le dépôt (autre proposition appliquée, retouche d'un
  coordinateur), l'appliquer efface ces changements sans que rien ne le dise.
  `GET /api/changes/<id>` renvoie `since` — ce qui a changé entre le dépôt et
  maintenant, comparé en formes et en flèches (`_resume_changement`), pas en
  texte : un simple réenregistrement réécrit le JSON sans rien changer.
- Une proposition appliquée sur la carto AFFICHÉE recharge la page à la
  fermeture de la fenêtre (pas avant : on peut avoir d'autres propositions à
  traiter). Un 409 (déjà tranchée ailleurs) retire la ligne au lieu d'afficher
  une erreur. Les dates du serveur sont en UTC SANS fuseau : le JS ajoute le
  `Z`, sinon deux heures de décalage à Paris.
- La section ③ de la page RH, sa tuile, `rendrePropositions()`, le champ
  `propositions` de `/gestion_rh/api/tableau` et six clés `rh.*` sont retirés.

⚠️ **Et les lignes « valider » / « enregistrer directement » du tableau des
droits ne décidaient de RIEN.** `carto_access.can_review` et `can_edit`
lisaient le statut brut (`is_admin or is_coordinator`), jamais
`can_review_carto` / `can_edit_carto` : cocher « valider » pour le champion ne
lui ouvrait rien, le décocher pour le coordinateur ne lui retirait rien. Ils
passent désormais par le tableau — le défaut reproduit exactement l'ancienne
règle — et exigent en plus de pouvoir OUVRIR la carto (`can_read`) : un
champion à qui l'on confierait l'examen ne tranche pas sur une carto qu'il ne
voit pas.

### Le mot du valideur parvient à l'auteur (2026-09-21)

⚠️ **Le message à l'auteur était enregistré et lu par personne.** La fenêtre
d'examen offrait « un mot pour l'auteur » ; `review_comment` était bien écrit…
et AUCUN écran ne le montrait : ni la page Partage, ni l'éditeur, ni la moindre
notification. L'utilisateur a conclu, à raison, que « ça ne marche pas » —
qu'on applique ou qu'on refuse.
- `CartoChangeRequest.author_seen_at` (migration à chaud, `TIMESTAMP`) : NULL
  sur une proposition tranchée = à annoncer. Appliquer / Refuser le remettent à
  NULL (`_annoncer_a_l_auteur`) ; on ne s'annonce pas sa propre décision.
- `GET /cartography/api/changes/decisions` (mes décisions non lues) et
  `POST …/decisions/vues` `{ids}` (« Compris » — seulement celles dont on est
  l'AUTEUR : les ids viennent du navigateur).
- `carto_decision_popup.html`, incluse par `header_buttons.html` : la décision
  (appliquée / refusée), la carto, qui, quand, et le mot — sur n'importe quelle
  page, jusqu'à « Compris ». Elle attend que la bienvenue ET la notification de
  transfert d'entité soient refermées : on n'empile pas deux fenêtres.
- Le mot se relit aussi là où l'auteur relit sa proposition : bloc « Décision »
  de la page Partage (`share.js::decisionHtml`) et de l'éditeur
  (`carto_sharing.js::decisionHtml`, style sombre `.gov-decision` dans
  `style.css`).
- Côté valideur, le champ nomme son destinataire (« Votre message à Lou
  Vasseur — il le recevra avec votre décision ») et l'annonce le confirme.
- Au passage : les dates des propositions (page Partage, éditeur) suivaient la
  langue du NAVIGATEUR et l'heure UTC (13:31 pour 15:31 à Paris) : le serveur
  écrit en UTC sans fuseau, le JS ajoute le `Z` et suit la langue de l'appli.
- Tests : `tests/test_88_decision_a_l_auteur.py` (8 cas).

### Avant / après : les VRAIES cartos, et une bascule instantanée (2026-09-21)

`static/js/carto_comparaison.js` + `static/carto_comparaison.css` — UN composant
pour la fenêtre d'examen de la page Carte (`carto_examen.js`) ET celle de
l'éditeur (`carto_sharing.js`) : deux écrans qui ne peuvent plus diverger.
- **Les vignettes SONT le viewer d'OptiqCarto** (`/cartography/changes/<id>/
  apercu/<quel>`), pas un schéma reconstruit. Même taille qu'avant (4/3). Un
  voile prend le clic (agrandir) et laisse la molette faire défiler la fenêtre
  au lieu de zoomer la carte.
- **Un seul cadre pour les deux** : les bornes RÉUNIES des deux cartos,
  imposées aux deux viewers. `editor.js` expose `window.cartoViewport`
  (`get` / `set` / `bounds` / `fit`) et `fitView(bornes, plancher)`.
  ⚠️ Le plancher par défaut reste `ZOOM_MIN` (0,08, celui de la molette) ; le
  cadre imposé descend à 0,004 — sinon une grande carto ne tenait pas dans une
  vignette et n'en montrait qu'un morceau (mesuré : la carto FluidClip exige
  0,045). `test_79` garde le plancher STRICTEMENT positif.
- **Les formes touchées sont entourées dans la vraie carto** (retirée rouge sur
  l'avant, ajoutée verte sur l'après, déplacée / renommée ambre des deux côtés)
  par une feuille de style injectée dans chaque viewer — `marques` vient de
  `GET /api/changes/<id>`. ⚠️ `vector-effect: non-scaling-stroke` : un trait
  en unités de carte fait moins d'un pixel en vignette et devient épais en
  grand ; en pixels d'écran il se voit partout.
- **Agrandir ne recharge rien** : les MÊMES iframes, agrandies en CSS
  (`.cmp[data-mode="loupe"]`, fixe, 16 px du bord). ⚠️ Déplacer une iframe
  dans la page la recharge — c'est ce demi-seconde que l'utilisateur voyait à
  chaque bascule. La vue masquée est en `visibility: hidden`, JAMAIS
  `display: none` (un viewer de taille nulle ne se cadre plus).
- **La bascule garde le cadrage** : on recopie `get()` de la vue affichée sur
  l'autre AVANT de la montrer — on compare le même endroit, au même zoom.
  Mesuré : 35 ms, clic compris. Tab bascule, Échap referme le grand format
  (pas la fenêtre d'examen) — y compris quand le viewer a le focus (écouteurs
  posés dans chaque iframe). ⚠️ Pas l'espace : maintenu, il déplace la carte.
- ⚠️ **Dans l'éditeur, la fiche d'examen s'ouvre sur une animation en
  `transform`** conservée (`both`) : elle devenait le repère des éléments fixes
  et le grand format y restait enfermé. `#review-modal .gov-card {
  animation-fill-mode: backwards; }` — rien ne change à l'œil.
- ⚠️ **Les viewers de la comparaison préviennent leur page à chaque clic sur
  une forme** (`shape-click`), et la page Carte part alors vers la fiche de
  l'activité. `activities_map.js` ignore les messages des iframes de `#cex` —
  vérifié à l'écran : sans ce filtre, cliquer « Clarify RFI Scope » en grand
  quittait la page.
- Retirés : la route SVG `/api/changes/<id>/apercu/<quel>.svg`, `_cadre_commun`,
  les marques de `_svg_depuis_diagramme` (qui ne sert plus qu'à la galerie de la
  page Partage), la loupe de `carto_examen.js` et `carto_sharing.js`, et les
  styles `.gov-ba*` / `.gov-dot*` / `.gov-loupe*`.
- `editor.js` et `style.css` synchronisés dans le dépôt OptiqCarto (contenus
  identiques, fins de ligne LF là-bas).
- Tests : `test_66::TestApercuAvantApres` / `::TestApercuEnGrand` réécrits sur
  les nouvelles garanties (cadre commun, pas de rechargement, bascule qui garde
  le cadrage, vue masquée qui garde sa taille, grand format fixe, filtre des
  clics).

### La fiche de compte, deuxième passe (2026-09-21)

« Pas satisfaisant, plus d'ergonomie. » Et en la reprenant, un défaut de FOND :
- ⚠️ **Corriger un nom pouvait retirer un rôle — et l'accès à une carto.** La
  fiche ne portait qu'UN rôle, choisi parmi ceux de la carto ACTIVE, et
  `update_user` remplaçait « le » rôle de la personne (`UserRole…first()`).
  Pour quelqu'un qui tenait un rôle ailleurs, un simple « Enregistrer » envoyait
  un rôle vide : son rôle était supprimé. Les rôles bougent désormais PAR PAIRE
  (`roles_ajout` / `roles_retrait`, `_appliquer_roles`) et seulement ceux que la
  fiche nomme ; le développeur de compétences posé sur chaque rôle reste. Un
  `role_id` (ancien formulaire) ne fait plus qu'ajouter. `test_50::
  test_le_role_est_facultatif_a_la_modification` affirmait l'ANCIEN comportement
  destructeur : il affirme maintenant que rien n'est retiré.
- Qui attribue quoi : un rôle ouvre des cartos, donc seuls l'administrateur et
  qui ouvre la page RH (`can_access_rh`) en attribuent ; un administrateur
  n'importe lequel, les autres ceux des cartos qu'ils ouvrent. On ne se donne pas
  de rôle depuis sa propre fiche. Une fiche refusée n'écrit RIEN (pas même le
  nom), et une création refusée ne laisse pas de compte à moitié fait.
- ⚠️ **Un administrateur ne change pas son propre niveau** : il perdrait
  l'écran depuis lequel il le remettrait.
- **L'envoi se fait en arrière-plan** (`Accept: application/json` →
  `{ok, code, champ}`) : une erreur s'écrit SOUS le champ fautif et la saisie
  reste. Avant, un e-mail déjà pris rechargeait la page et tout était perdu.
  Sans cet en-tête, les routes redirigent comme avant.
- **L'écran** : un en-tête qui montre la PERSONNE (initiales et couleur de son
  niveau, qui suivent la saisie), deux colonnes — identité et connexion ;
  niveau d'accès en **échelle** (les marches inférieures restent allumées :
  chaque palier inclut le précédent) et **rôles carto par carto** (retirés
  barrés avec « annuler », ajoutés marqués, sélecteur avec recherche). Le mot
  de passe se change SUR DEMANDE, avec « Générer » (sans 0/O/1/l) et
  « Afficher ». « Enregistrer » ne s'allume qu'avec une modification, et le
  pied dit combien.
- ⚠️ Choisir un rôle redessine la liste : l'élément cliqué est DÉTACHÉ quand le
  clic remonte, et le « clic à l'extérieur » refermait le sélecteur (puis Échap
  fermait la fiche). Un élément détaché venait forcément de l'intérieur.
- Tests : `tests/test_87_fiche_compte.py` (15 cas ; 5 vérifiés **rouges** sur
  l'ancien code, dont le rôle effacé). Banc : `tools/devrun_partage.py` donne à
  `user@test.local` un rôle sur la carto PRIVÉE du coordinateur.

### Tout ce qui a été ajouté, relu dans les DEUX langues (2026-09-21)

Avant de livrer sur `nouveau-point` et le pilote. Trois passes :
1. **Les tests existants** (`test_78`, `82`, `83`, `85`) : verts.
2. **Une analyse statique des nouveaux écrans** : chaque JS lit un catalogue
   (`CEX_I18N`, `CDP_I18N`, `ACC_L`, `GRH_L`, `RHC_I18N`, `IMPH_I18N`,
   `CACC_L`, `SHARE_L`, `OPTIQ_I18N`) par un accesseur qui rend la CLÉ quand
   elle manque — aucun repli français. Toutes les clés lues sont injectées.
3. **Les vrais écrans parcourus en anglais PUIS en français** (Playwright,
   bancs `devrun_partage` / `devrun_competences`), avec un détecteur injecté
   qui relève dans le texte ET les attributs (`title`, `aria-label`,
   `placeholder`) les phrases du catalogue de l'autre langue, les accents et
   mots-outils de l'autre langue, et les clés affichées telles quelles — après
   avoir retiré les DONNÉES (tout texte lu dans les bases de mise au point).
   ⚠️ Pièges du banc : `pg.evaluate()` ATTEND une promesse — appeler une
   fonction qui ouvre une fenêtre (`cartoProposeInstead`, `_promptLiaisonLabel`,
   `_confirmBandDelete`…) le bloque jusqu'à sa fermeture : l'envelopper dans
   `() => { f(); }`. Et le banc `devrun_partage` CONSOMME ses propositions (on
   les tranche) : le relancer entre les deux langues.

**Les écrans ajoutés étaient propres.** Ce qui ne l'était pas, et qui est
corrigé — tout sur des écrans plus anciens, que le pilote (anglophone) ouvre
tous les jours :
- **Éditeur** : info-bulles écrites en dur, en français (« Position des
  labels… », « Créer une pile… ») ET en anglais (« Box select — drag… ») ;
  les avertissements des piles (en anglais) ; et des fenêtres ENTIÈRES bâties
  en JS sans catalogue : diagnostic carto, correction des erreurs, placement
  des losanges, fichier Visio incomplet, suppression d'une bande. 80 clés
  `editor.*`. ⚠️ `_L()` substitue `{0}`, `{1}`… dans l'ordre des arguments.
- **Éditeur** : une erreur réseau à l'envoi d'une proposition affichait
  `editor.toast.error_network` — une clé qui n'a jamais existé
  (`editor.err_network_propose` désormais).
- **Page Carte** : « 42 activités » (gestion des entités, et le compteur de la
  recherche dès qu'on tapait une lettre), toute la fenêtre des liaisons entre
  cartos (officialiser, dé-officialiser, nom affiché sous l'activité), les
  erreurs des entités. Nouveau catalogue `window.MAP_I18N` (accesseurs
  `ML()` / `MF()` dans `activities_map.js`).
- Six info-bulles en dur sur des pages traduites (fiche activité, tâches,
  rôles, bienvenue, connexion).

⚠️ `activities_map.js` porte encore du français en dur, mais dans du code
MORT : les étapes de l'ancien import VSDX/SVG (écrans `step1`–`step3` absents
du gabarit), `loadSvgInline` (`#svg-container` n'existe plus), les panneaux
SCS/VCM, l'import de paquet (`#wizard-import-carto-btn` absent) et la modale
d'export (`#btn-export` absent). Rien de tout cela ne s'affiche ; à supprimer
plutôt qu'à traduire.
⚠️⚠️ **Cette liste est juste, et INCOMPLÈTE — c'est pire.** Elle ne mentionne
pas la modale « Envoyer une copie » (`openShareModal` / `confirmShare`), dont
les ancrages `#wizard-copy-btn`, `#share-confirm-btn` et `#share-modal` sont
bien dans le gabarit : elle est VIVANTE. Ses quatre phrases françaises sont
les **replis** de `SHARE_I18N`, dont toutes les clés existent — elle est donc
déjà traduite, mais pour une raison que cette note ne donnait pas. Vérifié le
25/11 : il reste **3** alertes vraiment en dur dans ce fichier, toutes dans du
mort, et `tests/test_167_alertes_des_listes.py` les tient à ce plafond.

Restent en français, connus et inventoriés : `projection_metier`,
`import_tasks_modal`, `chatbot_widget`, l'assistant d'installation.
`tests/test_89_libelles_carte_et_editeur.py` : cliquet des ATTRIBUTS en dur
(que `test_78` ne lit pas), toute clé `_L()` de l'éditeur présente dans les
deux langues, et les pages Carte / éditeur rendues en anglais.
`cartography_editor.html`, `activities_map.html` et `cartography_viewer.html`
sortent de l'inventaire de dette de `test_78`. Suite : 2573 passés.

### Les rôles sont COMMUNS à l'entreprise (2026-09-23)

« On a des rôles différents en fonction de l'entité choisie. » C'était exact, et
c'était le modèle : `Role.entity_id` faisait d'un rôle une chose de SA carto.
Deux cartos qui portent la bande « Qualité » donnaient deux rôles « Qualité »
sans rien qui les relie — un titulaire ici n'était pas titulaire là, et
`entity_role_access` ouvrait l'accès à l'un sans rien dire de l'autre. Comme les
comptes, un rôle est une chose de l'ENTREPRISE : `Code/roles_communs.py` est
désormais la source unique.

- `role_par_nom(nom, …)` : **une ligne par nom** (comparaison normalisée —
  minuscules, sans accents, espaces resserrés ; un tiret n'est PAS un
  séparateur). `entity_id` ne dit plus que l'ORIGINE, et ne filtre plus rien :
  ni la page RH, ni la fiche de compte, ni la matrice d'accès, ni l'import.
- ⚠️ **`_sync_carto_to_db` ne supprime plus un rôle qui sert ailleurs.** Il
  effaçait tout rôle absent des bandes de la carte : enregistrer la carto A
  emportait le rôle que la carto B venait de créer. Il DÉTACHE maintenant les
  liens de CETTE carto, et ne supprime que si `est_utilise(role)` est faux
  (aucun titulaire, aucune activité, aucune tâche — toutes cartos confondues).
- ⚠️ **`fusionner_doublons()` réunit les doublons d'hier, UNE fois** (marqueur
  `roles_communs` en base, `force=True` pour rejouer). Le rôle gardé est celui
  qui a le plus de titulaires, puis le plus petit id ; tout ce qui pointait vers
  les autres est re-pointé (titulaires, activités, tâches, accès aux cartos,
  plans de formation, exigences de domaine, analyses de temps). Sans ce
  rapprochement, la mise en commun laisserait l'existant tel quel : le défaut
  serait « corrigé » pour les rôles à venir seulement.
- ⚠️ **Le rôle système « Développeur de compétences » est lui aussi unique.**
  `assurer_roles_permanents(entity_id)` en rendait un PAR carto ; il rend le
  rôle global, et `reprendre_roles_hors_carte` ne marque que les rôles des
  cartos qu'on peut ouvrir.
- ⚠️ `_compute_removals` (avertissement « ce que l'enregistrement va retirer »)
  lisait les bandes du diagramme en MÉMOIRE : une bande sans activité n'y
  figurait pas, et sa disparition n'était pas annoncée. Il part du diagramme
  ENREGISTRÉ (`roles_permanents._bandes`).
- Tests : `test_66` (un rôle né ailleurs ouvre la carto, un rôle retiré de la
  carte ne part que s'il ne sert plus, une seule ligne par rôle, et la réunion
  elle-même — `TestLaReunionDesRoles`), `test_68`, `test_73`, `test_52`,
  `test_84`, `test_86`, `test_87`.

⚠️⚠️ **Et la réunion est tombée EN PRODUCTION, sans qu'aucun test la voie.**
Relevé dans la console serveur de staging après la livraison :
`[DB] réunion des rôles: Table 'time_project' is already defined for this
MetaData instance`. Deux causes qui se sont additionnées :
- **`Code/routes/time_extra.py` redéclarait CINQ tables déjà définies dans
  `models.py`** (`time_project`, `time_project_line`, `time_role_analysis`,
  `time_role_line`, `time_weakness`). Deux modèles pour une même table lèvent
  cette erreur **dès qu'on importe le second**, et elle frappe l'APPELANT, pas
  le fichier fautif. Personne n'importait ce module : il dormait depuis des
  mois, et `_fusionner_paire` a été le premier à y toucher. Fichier supprimé,
  `TimeRoleAnalysis` vient de `models.py`. Cliquet :
  `test_67::test_aucune_table_n_est_declaree_deux_fois`.
  ⚠️ Ce contrôle sautait d'abord `models.py` EN ENTIER parce qu'il contient
  `extend_existing` (pour ses tables d'ASSOCIATION) : il regarde désormais le
  VOISINAGE de chaque `__tablename__`, pas le fichier.
- **Aucun test n'appelait `fusionner_doublons()`.** Une reprise qui ne tourne
  qu'au démarrage n'est vérifiée par rien tant qu'on ne la joue pas
  explicitement. Mesuré sur staging avant correctif : 73 lignes de rôles pour
  68 noms — les doublons étaient restés.
⚠️ Le marqueur `roles_communs` n'avait PAS été posé (l'exception précède le
commit) : la reprise rejouera au prochain démarrage, rien à réparer à la main.

⚠️ **`_verifier_colonnes` criait avant l'ALTER qu'il attendait.** Journal :
« COLONNE MANQUANTE entities.statuts_regles », puis dix lignes plus bas
« Colonne entities.statuts_regles ajoutée ». L'ALTER est remonté AVANT la
vérification — un avertissement qui crie à chaque premier démarrage ne se lit
plus le jour où il a raison.

**L'entité « fantôme » qu'on ne pouvait pas supprimer.**
⚠️ `delete_entity` cherchait `Entity.query.filter_by(id=…, owner_id=user_id)` :
une carto dont `owner_id` est **NULL** — ou appartenant à quelqu'un d'autre —
n'était jamais trouvée. Elle s'affichait pourtant dans la liste
(`can_read` rend la main sur `owner_id in (None, user.id)`), d'où le message
« entité fantôme » et l'impossibilité d'en sortir. La route lit maintenant
l'entité par son id et refuse seulement si elle appartient à un AUTRE compte et
qu'on n'est pas administrateur. Elle ne supprime plus que les rôles devenus
orphelins (les rôles sont communs).
`tools/db/etat_entites.py --url … [--nom purchase]` inventorie une base en
**lecture seule** : cartos sans propriétaire joignable, noms portés par
plusieurs cartos, et les rôles que le démarrage va réunir.

**Page RH : « coordinateur » s'affichait en français dans l'interface anglaise.**
Le tableau envoyait `users.status` BRUT (un texte libre, écrit tel qu'il a été
saisi) là où la page Comptes passe par le catalogue. `api_tableau` envoie
désormais le **palier** (`famille_statut`), et le JS l'affiche traduit
(`st_user` / `st_champion` / `st_coordinateur` / `st_admin`, repris de
`account.status_*`).

### La fenêtre d'accès a deux sections : par rôle, par statut (2026-09-23)

Un rôle dit ce qu'on FAIT dans l'organisation ; un statut dit ce qu'on EST dans
l'application. Les deux ouvrent une carto, et la fenêtre « Qui ouvre quelles
cartos » (page Carte) les sépare : deux matrices, même colonnes, en-tête teal
pour les rôles, ambre pour les statuts.

- `EntityStatusAccess` (`entity_status_access`, unique par (carto, palier)) +
  `Entity.statuts_regles` (migration à chaud, `BOOLEAN DEFAULT FALSE`).
- **Par défaut, coordinateur et administrateur ouvrent toutes les cartos**
  (`STATUTS_DEFAUT`) — exactement ce que `can_read` faisait avant, en dur.
- ⚠️ **Le premier réglage GRAVE d'abord le défaut** : sans cela, décocher
  « coordinateur » aurait rouvert l'accès par le défaut resté implicite.
- ⚠️ **La ligne `admin` est verrouillée** (`STATUT_VERROU`, cases `disabled`, et
  le SERVEUR refuse de la retirer). Se décocher sur une carto qu'on ne possède
  pas la ferait disparaître de la fenêtre d'accès — il n'existerait plus aucun
  écran d'où se la rendre. Même raison que la colonne `admin` du tableau des
  droits.
- ⚠️ **La table unique donne les lignes, elle ne donne pas la FRONTIÈRE.**
  Premier jet : deux bandes pastel, et l'ensemble se lisait comme un seul bloc
  (« c'est trop un tout »). La séparation se rejoue donc sur TROIS plans, tous
  sans coût en hauteur : une bande **pleine** en couleur soutenue (teal pour
  les rôles, ambre pour les statuts) à texte blanc ; cette bande reste
  **collée sous l'en-tête** pendant qu'on défile — on sait toujours dans quel
  groupe on coche ; et un **liseré vertical** court sur toute la hauteur du
  groupe, la zone des statuts portant en plus son propre fond.
  ⚠️ `top` de la bande = hauteur RÉELLE de l'en-tête, mesurée après le rendu
  (`--cacc-thead`) : un nom de carto qui passe à la ligne la change.
  ⚠️ **Ordre d'empilement** : coin (7), en-tête (6), bande (4/3), première
  colonne du corps (1). La bande vient APRÈS l'en-tête dans le document — à
  `z-index` égal, c'est elle qui passerait par-dessus lui.
  ⚠️ Et le fond de ZONE des statuts repeignait la BANDE (même spécificité,
  déclarée plus bas) : son texte blanc devenait invisible. Troisième fois que
  ce piège mord dans cette feuille — une règle de bande se met APRÈS celle de
  la zone, et plus spécifique.
- ⚠️ **UNE table, deux BANDES — pas deux tables.** Deux tables, c'était deux
  en-têtes de colonnes (les mêmes cartos, écrites deux fois), deux titres de
  section et deux zones de défilement : les quatre paliers, en `flex: none`,
  prenaient tout ce qu'il leur fallait et il ne restait **deux lignes de rôles
  à l'écran**. L'en-tête des cartos est donc écrit UNE fois, collé en haut, et
  chaque groupe n'ajoute qu'une bande colorée — qui porte aussi le « tout
  cocher » de chaque colonne, et son compte. Mesuré sur une fenêtre de 760 px :
  **2 lignes de rôles → 9**, plus les 4 paliers, tout le temps visibles.
  Les colonnes s'alignent par construction (une seule table) : plus de
  défilement horizontal à synchroniser.
- **Les statuts d'abord** : quatre lignes fixes, donc toujours sous les yeux ;
  les rôles sont une liste longue, ils prennent la suite et défilent.
- ⚠️ **`display: flex` sur un `th` le sort de la mise en page de TABLE** : sa
  colonne n'est plus tenue et les cartos se décalent. Le flex de la bande vit
  dans un `<span>` à l'intérieur.
- ⚠️ **Le fond de la bande perdait sa première cellule** : `.cacc-table tbody
  th { background: #fff }` a la MÊME spécificité et est déclarée plus bas. Les
  règles de bande passent par `.cacc-grp`.
- `POST /cartography/api/access/matrice` accepte `cases` et/ou `cases_statut`,
  toujours **case par case** — jamais la table entière.
- Tests : `test_66::TestLAccesParStatut` (9 cas ; le verrou vérifié **rouge**).

### Page RH ③ : les compétences de chacun, toutes cartos (2026-09-21)

Le tableau global d'autrefois (`/competences/users/global_summary`, une
personne par ligne, un rôle par colonne) revient, dans la page RH et avec le
modèle V1.1 : `GET /gestion_rh/api/competences[?entity_id=]` →
`Code/competences_globales.py::tableau_global`, écran
`static/js/rh_competences.js` (catalogue `RHC_I18N`, clés `rh.comp_*`).
Une ligne par personne, une colonne par rôle **groupée par carto**, dans chaque
case la jauge de la page Compétences (quatre pas, trait au requis, pointillés
tant que ce n'est pas évalué) et ce qui reste (« 2 en écart », « 1 à évaluer »,
« Niveau tenu », « À configurer ») ; une colonne « Ensemble » porte la
couverture de la personne. Filtres : carto (défaut **toutes**), recherche, et
quatre puces d'état (tout le monde / en écart / à évaluer / au niveau). La
tuile « En écart » en tête de page mène au bloc ET filtre. Une case ouvre la
page Compétences sur CETTE personne et CE rôle (`?personne=&role=`,
`ouvrirDemande()` dans `competences_v2.js`, adresse nettoyée ensuite).
- ⚠️ **Indépendant de la carto choisie en haut de la page RH** : celle-ci cadre
  ce qu'on RÈGLE (personnes, rôles, accès) ; ce tableau sert à VOIR, et la vue
  utile d'abord est celle de toute l'entreprise.
- ⚠️ **Mêmes chiffres que la page Compétences, par construction** : la
  couleur, l'état d'une activité et la couverture viennent de `mastery`
  (`color_for`, `categorie_activite`, `couverture`) ; le niveau d'une activité
  et celui d'un rôle suivent la règle du MINIMUM (NULL tant que ce n'est pas
  complet). `test_86::test_memes_chiffres_que_la_page_competences` compare
  champ par champ avec `/mastery/synthese`.
- ⚠️ **Pas `dashboard_rows` en boucle** : ~6 requêtes par activité et par
  personne — soixante personnes, deux rôles, quinze activités, dix mille
  requêtes, deux minutes et demie sur Neon. Le calcul est fait en BLOC, en un
  nombre FIXE de requêtes (`test_le_cout_ne_grandit_pas_avec_l_effectif`
  compte les requêtes avant et après six personnes de plus : égalité).
- ⚠️ **`get_activity_outputs` ÉCRIT** (il matérialise les sorties en `Data`) :
  on ne l'appelle pas depuis une page de lecture. `_resultats()` relit ce qu'il
  a déjà matérialisé, avec sa règle exacte (index par nom normalisé, le
  dernier l'emporte ; résultats hérités via `Link.target_data_id`).
- Un rôle sans activité (le développeur de compétences, une bande vide) ou que
  personne ne tient n'a pas de colonne. Qui voit qui : coordinateur et
  administrateur, tout le monde ; sinon soi-même et ceux qu'on encadre (la
  règle de `peut_lire`, en bloc).

⚠️ **`competences_acces._statut_eleve` donnait l'arbitrage au mauvais
palier.** Elle disait « champion ou administrateur ». Depuis les quatre
paliers, `champion` nomme le palier du DESSOUS (il propose sans valider) et
l'ancien arbitre s'appelle `coordinateur` : un champion pouvait lire et NOTER
tout le monde — jusqu'à se décerner le niveau qui fait foi — et le coordinateur
ne voyait plus que ses propres collaborateurs sur la page Compétences. Règle
désormais : `niveau_status(statut) >= NIVEAU_COORDINATEUR`. C'était un appel
de STATUT (`is_champion_status`), pas `is_champion()` : la reprise des
« ~8 appels à `is_champion()` » ne pouvait pas le voir.

Tests : `tests/test_86_examen_et_competences_rh.py` (25 cas ; les huit qui
portent sur les droits vérifiés **rouges** sur le code d'avant). Bancs :
`tools/devrun_partage.py` sème une troisième carto commune avec sa proposition,
retouchée APRÈS le dépôt (l'avertissement `since`) ; `tools/devrun_competences.py`
une seconde carto « Atelier » (tenu, en écart, pas évalué).

### Page RH : un rôle sur PLUSIEURS cartos (2026-09-17)

Ouvrir une carto à un rôle se faisait carto par carto : changer l'entité en
haut de page, cocher, recommencer — cinq cartos, cinq allers-retours — et
aucun endroit d'où VOIR ce qu'un rôle ouvre au total. La carte de rôle porte
un bouton **« Cartos »** : une fenêtre, toutes les cartos accessibles, tout
part de là. `GET|POST /gestion_rh/role_cartos`.

⚠️ **`set_access` (page Partage) n'accepte que les rôles DE l'entité réglée, et
c'est juste là-bas** : on y règle une carto et on coche parmi SES bandes. Ici
on part du rôle. `can_read` s'en accommode depuis toujours — il compare les
rôles du compte aux rôles autorisés **sans jamais demander à quelle entité ces
rôles appartiennent**. Seul l'écrivain était restrictif.

⚠️ **Deux conséquences que l'écran annonce AVANT le clic**, parce qu'elles
décident de qui voit quoi :
- une carto **privée** ignore les rôles (`can_read` rend la main au
  propriétaire avant même de les consulter) — la cocher la rend commune, sinon
  on enregistrerait un accès qui ne produit rien ;
- une carto commune **sans aucun rôle autorisé est ouverte à TOUS**. Y poser le
  premier rôle la RESTREINT : cocher peut retirer l'accès à des gens qui
  l'avaient. C'est le piège de cet écran, il est écrit ligne par ligne.

⚠️ On ne réécrit QUE la ligne de ce rôle : régler un rôle ne doit pas effacer le
travail fait sur les autres.

### Page RH : un développeur de compétences PAR RÔLE (2026-09-17)

⚠️ **Il existait déjà en base et aucun écran ne le posait.**
`user_roles.manager_id` porte ce lien, `competences_acces.encadre()` le lit
déjà (il regarde les DEUX rattachements), et `assign_manager_simple` accepte
un paramètre `role_ids` — mais la page envoyait `role_ids: null`, c'est-à-dire
« le même développeur pour tous les rôles ». La capacité était là, injoignable.

Or celui qui suit quelqu'un sur « Qualité » ne le suit pas forcément sur
« Logistique ». La fiche d'une personne donne donc un sélecteur **par rôle
TENU** (`POST /gestion_rh/role_dev`) — poser un développeur sur un rôle qu'elle
ne tient pas n'aurait aucun lien pour le porter, la route refuse et l'écran le
dit plutôt que d'offrir un bouton qui échoue.
- Le même menu sert aux deux portées (global et par rôle) : deux menus pour un
  même choix finiraient par se contredire, et le second oublierait la coche
  « aucun », qui est ce qui RETIRE l'affectation.
- La liste annonce **« n développeurs »** quand ils diffèrent d'un rôle à
  l'autre : afficher un seul nom serait un mensonge.

### Le droit de MODIFIER un compte (2026-10-27)

Demandé par le pilote. Le tableau des droits portait « Créer des comptes »
sans son pendant : hors administrateur, `can_edit_account` ne laissait chacun
modifier QUE son propre compte, et un coordinateur devait passer par un
administrateur pour corriger la fiche d'un collaborateur.

Huitième ligne du tableau — `modifie_comptes` — ouverte par défaut au
**coordinateur** et à l'administrateur, fermée au champion et au simple
utilisateur. Elle se règle comme les sept autres, **page Comptes**.

⚠️ **Elle ne se règle PAS depuis la popup d'accès de la page Carte**, qui y
renvoie sans la régler : deux écrans pour un même réglage finissent par donner
deux réponses. C'est la règle déjà posée pour la matrice d'accès et pour le
tableau des droits.

⚠️⚠️ **On ne modifie JAMAIS le compte d'un palier PLUS HAUT que le sien.**
`/comptes/set_password` passe par cette porte : sans cette garde, un
coordinateur réinitialiserait le mot de passe d'un administrateur puis se
connecterait à sa place — le droit de modifier vaudrait le droit d'être
administrateur. Même règle que `/comptes/create`, qui refuse déjà de créer
au-dessus de soi. Son PROPRE compte reste modifiable sans aucun droit : on
n'a pas besoin d'une permission pour changer son mot de passe.

**Ce qui ne bouge pas** : le STATUT d'autrui reste réservé à l'administrateur
(`update_user` ne l'applique que pour lui), les rôles restent derrière
`can_access_rh`, la suppression reste à l'administrateur seul.

⚠️ **Le bouton « Modifier » de la liste est un drapeau PAR LIGNE**
(`item.peut_modifier`), plus une condition dans le gabarit : la règle dépend
désormais du palier de la CIBLE, et une condition unique ne peut plus la dire.
Il est calculé par la MÊME fonction que les routes — un second avis dans le
gabarit finirait par ne plus dire la même chose.

Tests : `tests/test_81_droits_reglables.py` passe de 11 à 23 cas ; deux gardes
retirées une par une, deux cliquets tombés (la garde de palier → 4 rouges dont
`set_password`, le bouton revenu à l'ancienne condition → 1 rouge).
Suite : 3474 passés sur staging, 2916 sur la base du pilote.

⚠️ **Porté sur le pilote par CHERRY-PICK, pas par la recette habituelle.**
`optiqfluent-staging` avait 44 commits de retard : rejouer l'arbre de staging
y aurait déversé les paliers de performance, les propositions d'activité et
les refontes des pages Temps et Compétences — ce n'est pas un patch. Le seul
commit a été greffé sur la base du pilote, suite complète rejouée dessus, et
l'invariant vérifié avant de pousser (`git diff --name-status
origin/optiqfluent-staging HEAD` ne rend que les 6 fichiers). Livré à **22h04
en Inde**, la fenêtre du soir est tenue.

#### Le STATUT se change depuis la fiche — sauf le palier administrateur (2026-10-28)

Suite immédiate du droit ci-dessus, demandée par le pilote. `update_user`
n'appliquait le champ `status` que pour un administrateur (`if _is_admin(moi)
and moi.id != user.id`) : un coordinateur qui venait de recevoir le droit de
modifier un compte pouvait donc tout corriger SAUF ce qu'on lui demandait de
corriger — le palier de la personne.

`peut_changer_statut(acteur, cible, nouveau)` (`Code/permissions.py`) est la
source unique. Trois règles, et c'est la troisième qui compte :

1. **jamais le sien** (`error_status_self`) — un administrateur qui se retire
   son palier perd l'écran depuis lequel il le remettrait ;
2. **jamais au-dessus de soi** (`error_status_too_high`) — exactement ce que
   `/comptes/create` applique déjà à la création ;
3. ⚠️ **le palier administrateur ne se DONNE ni ne se RETIRE que par un
   administrateur** (`error_status_admin_only`). La règle 2 couvre déjà le
   don — administrateur est le sommet ; c'est le RETRAIT qu'elle laisse
   passer, et c'est lui qui compte : sans elle un coordinateur rétrograde un
   administrateur, et le garde-fou de palier de `can_edit_account` s'ouvre
   alors sur son compte — mot de passe réinitialisé, connexion à sa place.

⚠️ **L'ordre des règles est une décision.** Le contrôle du palier
administrateur passe AVANT la règle générale : quand il est en jeu, le refus
doit dire POURQUOI, pas « au-dessus de votre niveau ». On ne corrige pas un
refus qu'on ne comprend pas.

⚠️ **On compare les PALIERS, pas les libellés.** `users.status` est du texte
libre : « administrateur » vaut « admin », « manager » vaut « coordinateur ».
Et la fiche renvoie TOUJOURS le champ statut — comparer les chaînes ferait
donc échouer un simple changement de nom de famille, et réécrirait au passage
le libellé historique d'un compte qui n'a pas changé de palier.

⚠️ `can_edit_account` refuse déjà d'ouvrir la fiche d'un palier PLUS HAUT, ce
qui couvre la règle 3 par un autre chemin. Elle est redite dans
`peut_changer_statut` parce qu'une règle de sécurité ne doit pas dépendre
d'une seconde, écrite ailleurs, qu'on pourrait desserrer un jour sans y
penser.

**L'écran suit la même règle** (`reglerEchelle`, `gestion_compte_new.js`) :
les marches au-dessus de son palier restent éteintes, celle de
l'administrateur aussi pour un non-administrateur, et toute l'échelle est
éteinte sur la fiche d'un administrateur. Le masquage n'est pas une sécurité —
le serveur refuse de son côté, avec le code que l'écran écrit SOUS le champ
fautif.

⚠️⚠️ **La colonne `admin` du tableau des droits est tenue par DEUX
mécanismes, dont le second par ACCIDENT.** `droits_effectifs` la reforce à
vrai, et `enregistrer_droits` ne stocke que les ÉCARTS au défaut — or aucune
ligne de `DROITS_DEFAUT` ne porte de clé « admin », donc un `admin: False`
posté est « égal au défaut » et n'est jamais écrit. Conséquence pour les
tests : retirer le premier verrou SEUL ne change RIEN, et le cliquet ne mord
qu'en remettant AUSSI la version naïve de l'écriture. C'est le piège — qui
« simplifierait » un jour la logique des écarts déverrouillerait la colonne
sans s'en apercevoir. Côté accès, un coordinateur LIT le tableau et ne
l'écrit pas : `POST /comptes/droits` rend 403 hors administrateur.

Tests : `tests/test_81_droits_reglables.py` passe de 23 à **36 cas** ; **huit
gardes retirées une par une, huit cliquets tombés**. Suite : **3502 passés**,
1 sauté.

**Report sur le pilote, par greffe, le MÊME jour.** Même recette que la
veille : le commit de staging greffé sur la base du pilote (`cherry-pick -n`),
CLAUDE.md écarté — la doc du pilote suit une autre lignée et la synchroniser
y déverserait la documentation de fonctionnalités qu'il n'a pas. Les 5
fichiers de code et le fichier de tests étaient **identiques** des deux côtés
(seul `translations.py` diverge, de 271 lignes, et il s'est fusionné tout
seul) ; le diff greffé a été comparé ligne à ligne à celui de staging —
identique. Invariant vérifié avant de pousser (`git diff --name-status
origin/optiqfluent-staging HEAD` ne rend que les 6 fichiers), suite complète
rejouée sur la base du pilote : **2929 passés**.

⚠️ **Livré à 17h20 en Inde, en pleine journée de travail** — dérogation
explicite de l'utilisateur, demandée après l'avoir prévenu de l'heure locale.
La règle du soir reste la bonne : un redémarrage coupe les requêtes en vol.
Aucune conséquence observée — `/health` 200, et le JS servi porte bien
`error_status_admin_only`, `error_status_self` et `cibleAdmin`.
⚠️ Travaillé dans un worktree JETABLE taillé sur `origin/optiqfluent-staging`
plutôt qu'en index temporaire : un cherry-pick qui peut conflicter a besoin
d'un arbre de travail, et celui de la session ne devait pas bouger. Retiré
après la livraison, avec son entrée `safe.directory`.

### Page RH ④ : ce que chaque palier ouvre se RÈGLE (2026-09-17)

L'échelle `user < champion < coordinateur < admin` est la grammaire du produit
et ne bouge pas. Ce que chaque palier OUVRE se règle, parce qu'une entreprise
n'a pas les mêmes usages qu'une autre. Une matrice (7 droits × 4 paliers) en
section 4 de la page RH ; `GET|POST /gestion_rh/droits`.

- **Où c'est branché** : `Code/permissions.py` — `DROITS_DEFAUT`,
  `droits_effectifs()`, `a_le_droit(droit, user)`. Les `can_*` délèguent toutes
  à `a_le_droit`, y compris `can_manage_access` (carto_access).
- ⚠️ **Le tableau par défaut EST le comportement d'hier.** Une instance qui n'a
  jamais rien réglé ne change pas de comportement en prenant ce code — sans
  cette règle, une livraison redistribuerait silencieusement les droits de tout
  le monde. Vérifié par `test_81::TestLeDefautEstLeComportementDHier`.
- ⚠️ **La colonne `admin` est verrouillée à VRAI, et le SERVEUR la reforce.**
  Se retirer les Paramètres, ce serait perdre l'écran depuis lequel on les
  remettrait : la porte se refermerait de l'intérieur, sans poignée.
- ⚠️ **Seul un administrateur ÉCRIT** ; un coordinateur LIT. Un coordinateur qui
  pourrait s'attribuer les sections d'administration s'attribuerait la clé IA
  de l'entreprise. La ligne `parametres_admin` porte d'ailleurs, en clair, ce
  qu'elle ouvre : clé IA, adresse de la base, console serveur.
- ⚠️ **On ne stocke que les ÉCARTS** au défaut. Enregistrer la table entière
  figerait les valeurs d'origine : le jour où le produit en change une, les
  instances qui n'y avaient jamais touché garderaient l'ancienne sans le savoir.
- ⚠️ **Pas de cache dans `flask.g`** — une première version en posait un pour
  éviter une dizaine de lectures par page. `g` vit aussi longtemps que le
  CONTEXTE, pas la requête : la suite de tests garde un contexte applicatif
  ouvert du début à la fin (`conftest.app`), si bien que le premier réglage lu
  y restait figé pour toute la session. Deux tests tombaient, et le défaut
  aurait frappé n'importe quel contexte long. `db.session.get()` sur une clé
  primaire passe déjà par la carte d'identité : un aller en base par session,
  c'est-à-dire par requête — la granularité voulue, sans la dépasser.

Tests : `tests/test_80_rh_acces_et_dev.py` (15 cas) et
`tests/test_81_droits_reglables.py` (11 cas). Suite : 2328 passés.

### Le développeur par rôle : QUI et SUR QUOI, au même endroit (2026-09-17)

La capacité était branchée, l'écran la rendait introuvable et illisible. Trois
reproches, trois causes distinctes — dont une de FOND.

⚠️ **Le fond : restreindre à un rôle ne produisait RIEN.** `encadre()` lit les
DEUX rattachements (`users.manager_id` global ET `user_roles.manager_id`). Tant
que le lien global existe, il couvre TOUS les rôles — y compris celui dont on
venait de retirer le développeur. On affichait donc une restriction que le
droit ignorait. `_dissoudre_lien_global()` reporte le lien global sur chaque
rôle tenu puis l'efface : ce qu'il couvrait reste couvert, et la portée
demandée veut enfin dire quelque chose. Appelé par `/role_dev` comme par
`/dev_scope`.

- **`POST /gestion_rh/dev_scope`** `{user_id, dev_id|null, role_ids}` porte la
  décision ENTIÈRE. `role_ids` nul = tous ses rôles (le lien global, qui
  couvrira aussi les rôles reçus plus tard) ; une LISTE = exactement ces rôles,
  le développeur étant retiré des autres **sans toucher aux affectations des
  autres développeurs**. ⚠️ Un seul appel : en deux requêtes, un refus au
  milieu laissait un développeur posé partout en attendant une portée qui
  n'arrivait jamais.
- **La portée se choisit dans le menu « Développeur de compétences »**, dans la
  liste des personnes. Elle vivait dans la fiche de la personne, derrière le
  bouton des RÔLES : personne ne l'y cherchait, et le menu du développeur ne
  proposait que des noms. Une question, un endroit — et le panneau s'ouvre sur
  la RÉALITÉ (couverture partielle = déjà dépliée, rôles cochés).
- **Un NOM SEUL était un mensonge par omission** : « Lou Vasseur » se lisait
  pareil que le développeur suive les trois rôles ou un seul. Le bouton porte
  sa portée en seconde ligne — « tous ses rôles » en gris, « 1 rôle sur 2 » en
  AMBRE avec un liseré (ce n'est pas une erreur, c'est la nuance qu'on n'avait
  aucun moyen de voir) — et les pastilles de rôle de la liste marquent celles
  qui sont SUIVIES. La fiche d'une personne annonce « Rôles suivis : 1 sur 2 »
  avant de détailler.
- ⚠️ **`couverture()` calcule la portée EFFECTIVE, pas la saisie** : un rôle
  dont la ligne est vide est couvert par le lien global, et une personne qui ne
  tient AUCUN rôle de la carto regardée peut très bien avoir un développeur
  global — afficher « Aucun » serait faux dans les deux cas.
- ⚠️ **Le bouton « n développeurs » était `disabled`** : avec deux développeurs
  sur deux rôles, on ne pouvait plus rien changer depuis la liste — exactement
  la situation où on en a besoin. Il ouvre le panneau comme les autres.

Deux défauts d'interface trouvés en éprouvant l'écran, tous deux antérieurs :

- ⚠️ **Le menu était dessiné 20 % trop haut et trop à gauche de son bouton.**
  `body.pg` porte `zoom: .8` : un enfant du body en `position: fixed` voit ses
  coordonnées MULTIPLIÉES par ce zoom, alors que `getBoundingClientRect()` les
  rend déjà en pixels d'écran. Invisible tant que le menu était étroit, criant
  dès qu'il s'élargit. `offsetWidth`, lui, est déjà dans le repère du body.
- ⚠️ **Un clic DANS le panneau le refermait.** Le clic du document ferme le
  menu quand sa cible n'est pas dans `.grh-devmenu` — or changer la portée
  REDESSINE le panneau : la cible est déjà DÉTACHÉE quand l'événement remonte,
  `closest()` ne trouve plus rien. La remontée s'arrête donc au panneau.

Tests : `tests/test_80_rh_acces_et_dev.py::TestLaPorteeDUnDeveloppeur` (8 cas —
la dissolution du lien global vérifiée **rouge** sur le code d'avant). Suite :
2336 passés. Éprouvé dans les DEUX langues sur `tools/devrun_partage.py` :
poser, resserrer, élargir, retirer, et une personne sans aucun rôle.

### Report sur le pilote : 15 cartos homonymes numérotées, écart nul ailleurs (2026-09-29)

Report habituel, rejoué d'après la recette du 17/09 (arbre de staging à
l'identique + `.github/workflows/deploy-beta.yml`, index temporaire, invariant
vérifié avant de pousser : `git diff --name-status origin/staging <commit>` ne
rend que ce fichier). 3 commits de retard rattrapés.

⚠️ **La branche du pilote s'appelle `optiqfluent-staging`**, pas
« optiqfluent-beta-test » : ce nom-là n'existe plus sur le dépôt (seul le
workflow a gardé le nom `deploy-beta.yml`). Les titres de section qui le
citaient encore sont corrigés.

**Ce que la numérotation a fait sur une base EN SERVICE.** Relevé avant
(`tools/db/etat_entites.py`, lecture seule) : 20 cartos pour 17 noms, trois
groupes d'homonymes — **9 « FluidCLip »**, 4 « test », 2 « Purchase ». Après le
démarrage : **0 nom porté par plusieurs cartos**, 15 renommages, aucune carto
perdue. Chacune a gardé son ORTHOGRAPHE : #22 s'écrivait « FluidClip » (c
minuscule), elle est devenue « FluidClip 9 » et non « FluidCLip 9 ».
⚠️ Et **écart NUL sur les 52 autres tables** (comparées au manifeste de la
sauvegarde) ; seuls `app_settings` (+1, le marqueur `entites_nom_unique`) et
`usage_events` (+4, les sondes de contrôle) bougent, comme prévu.

⚠️ **Sauvegarde AVANT, et relue.**
`~/AFDEC/sauvegardes/optiqfluent_pilot-2026-09-29` — 54 tables, 15 518 lignes,
les 54 relues sans écart, et les 4 pièces jointes décodées depuis le base64
jusqu'à leurs octets de signature (la carte Visio harmonisée du client :
902 068 octets, le même compte qu'aux 17 et 28/09). L'inventaire d'avant est
archivé à côté (`_inventaire_avant.txt`).
⚠️ Le binaire est écrit `{"__b64__": "…"}` (`dump_db.MARQUE_BINAIRE`) : un
script de relecture qui attend une chaîne annonce « base64 illisible » sur les
quatre pièces jointes et laisse croire à une sauvegarde abîmée.

Livré à **21h58 en Inde**, mardi soir — la règle est tenue. Vérifié en ligne :
`/health` 200, les fichiers servis portent bien les nouveautés
(`openImportHistory`, `imh-hist-head`, `btn-sans-taches`), et les fichiers de
l'ancien import de tâches rendent 404.

### La page Carte devient une SCÈNE (2026-10-01)

« C'est dommage qu'on ne voie pas la carto en plus grand, c'est le cœur de
l'app. » Le reproche était chiffrable, et il l'a été avant de toucher à quoi
que ce soit :

| Écran | Carto affichée | Haut du dessin | Page |
|---|---|---|---|
| 1920×1080 | 1226×580 — **34 % de la fenêtre** | à 311 px du bord | 390 px de vide en bas |
| 1440×900 | 1050×580 — 47 % | à 311 px | **débordait** (941 px) |
| 1280×800 | 890×580 — 50 % | à 367 px | **débordait** (996 px) |

Le viewer était plafonné à **580 px de haut quel que soit l'écran** —
`.carto-right { height: 650px }` fixait la hauteur du panneau, et la carte
s'alignait dessus. Au-dessus, **trois bandeaux empilés** répétaient la même
chose : barre de page (titre + nom d'entité), rappel de navigation (une ligne
entière pour dire qu'on déplace à la souris), en-tête de carte (titre + nom
d'entité À NOUVEAU, à 60 px du premier).

**Après** : 66 % de la fenêtre sur un 1920×1080, le dessin commence à 175 px,
et **plus aucun défilement** aux trois tailles. Tiroir replié, la carto gagne
encore **320 px, soit +26 % de largeur**.

**Ce qui a changé.**
- `.carto-scene` : une colonne de la hauteur de l'écran, `overflow: hidden`.
  Une barre, la carto, un tiroir. Les anciennes règles ne sont pas touchées —
  la nouvelle section arrive APRÈS dans `cartography.css` et les écrase par
  l'ordre de déclaration ; elles servent encore aux fenêtres de la page.
- **Une seule barre** (58 px) : titre, entité, « lecture seule », puis les
  actions. L'en-tête de carte est supprimé, le rappel de navigation aussi —
  son texte attend derrière un « ? ».
- **Le tiroir se replie** (bouton, languette, raccourci `l`), et son état vit
  dans `localStorage` : il se retrouve replié à la visite suivante.
- **Plein écran** (bouton, raccourci `f`) et **recentrage** (le logo, `c`).

⚠️ **On RECADRE la carto après un repli ou un passage en plein écran** — et il
a fallu le voir à l'écran pour le trancher. Le premier jet ne recadrait pas,
au nom du « on ne vole pas son point de vue à l'utilisateur » que respecte tout
outil de dessin. Sauf que le viewer ancre la carto par son **coin**, pas par
son centre : replier le tiroir ne donnait donc pas « plus de marge autour du
dessin », il donnait **320 px de vide à droite**. Or on replie précisément pour
voir plus grand. Le recadrage attend la fin de la transition (380 ms) : plus
tôt, le viewer se cadrerait sur une largeur qui n'est pas encore la bonne.

⚠️ **Le tiroir POUSSE la carto, il ne la recouvre pas.** La mini map et la
pastille de zoom du viewer vivent en bas à droite : un panneau flottant posé
par-dessus les masquerait.

⚠️ **`100vh - 86px` était une constante DEVINÉE.** La barre de navigation et sa
marge occupent 106 px : la page débordait de 28 px et se remettait à défiler,
ce qu'on venait justement de supprimer. `--cs-top` est désormais **mesuré** par
`carto_scene.js` (`getBoundingClientRect().top`), recalculé au redimensionnement
et au passage en plein écran — où il vaut 0, et la règle donne 100vh toute
seule.

⚠️ **Il restait 8 px de défilement** : `optiq.css` ne remet pas la marge du
`body` à zéro, et celle du navigateur s'ajoute SOUS la scène, qui finit
pourtant pile au bord. Huit pixels suffisent à faire réapparaître la barre de
défilement d'une page calibrée pour n'en avoir aucune. La classe
`body.a-carto-scene`, posée par le script, la neutralise — sans rien changer
ailleurs.

⚠️ **`position: absolute` cherche son repère dans le premier ANCÊTRE
positionné.** Le bandeau des connexions était resté AU-DESSUS du corps : il se
posait n'importe où. Il vit maintenant DANS `.carto-container`, dont la
position est relative. Tenu par `test_94`.

⚠️ **Les raccourcis ne se déclenchent jamais pendant une saisie** : la
recherche d'activité est à deux centimètres, et « f » y sert à écrire. Ni
quand une fenêtre est ouverte par-dessus : Échap doit la fermer, pas sortir du
plein écran.

⚠️ **`requestFullscreen` rend une PROMESSE** qui peut être rejetée (permission,
iframe) : sans `.catch()`, un simple refus remplit la console d'erreurs non
gérées.

⚠️ **L'entrée en scène part d'une opacité nulle** : elle n'est posée que si
l'onglet est visible, sinon le navigateur met l'animation en pause et la page
reste blanche jusqu'au retour dessus. (Même piège que la page Partage.)

⚠️ **Le bandeau d'examen des propositions est un enfant FLEX de la scène** :
sans `flex: none` il se laisse écraser quand la place manque, et l'alerte
devient illisible au moment où elle compte.

**Sans carto**, les boutons de la scène ne sont pas RENDUS (pas seulement
masqués) : replier ou passer en plein écran n'a aucun sens devant un écran
d'accueil.

#### La barre, l'écho et le fond — deuxième passe (2026-10-02)

« Toute la section du haut, c'est hideux. » C'était exact, et chiffrable : la
barre alignait **cinq vocabulaires de boutons** côte à côte — trois pleins
roses, un en contour rose, un sombre, puis trois icônes blanches — et deux de
ses icônes étaient des **PNG recolorés par un filtre CSS** à côté d'icônes
vectorielles. Tout criait au même volume, donc rien ne ressortait.

- **UN seul bouton** (`.cs-b`), et **une seule action primaire** : ouvrir
  l'éditeur. Les réglages (entités, import, accès, connexions) partagent la
  même forme discrète ; « Connexions » est un interrupteur, donc il a un état
  plein — en bleu, pour ne pas se confondre avec l'action primaire.
  ⚠️ Sa classe `.active` est posée par `activities_map.js` : ne pas la renommer.
- **Les trois gestes de la scène** (aide, plein écran, tiroir) sont réunis dans
  un segment : ils parlent de l'ÉCRAN, pas des données.
- **Le nom de la carto devient le titre** — c'est lui qu'on vient lire.
  « Cartographie des activités » passe en surtitre.
- Les deux `<img>` deviennent des icônes Font Awesome. Un PNG qu'on recolore
  au `filter` ne suivra jamais l'état du bouton.

**L'écho — trois contours, chacun un peu plus grand.**
⚠️ **Premier jet en `box-shadow` : invisible.** Six ombres emboîtées, alternant
blanc et filet sombre — à taille réelle, un halo mou. Un anneau d'ombre doit se
détacher sur la couleur EXACTE du fond pour qu'on voie l'écart, et ce fond
porte deux dégradés radiaux : l'anneau « vide » ne tombe jamais pile dessus.
Ce sont donc **deux pseudo-éléments en `border`** sur `.carto-left` : de vrais
traits, transparents au milieu, qui se voient sur n'importe quoi.
⚠️ **Et il a coûté 10 POINTS de surface au premier essai** : 66 % → 56,6 % sur
un 1920×1080, 53,6 % → 41,7 % sur un 1280×800 — on revenait vers l'état d'avant
la refonte, alors que « on ne voit pas la carto en grand » était le reproche de
départ. Les anneaux se resserrent (−6 / −12), le padding de la scène cède la
place à celui du corps (ils s'additionnaient), et l'écart carte/tiroir tombe à
26 px. Résultat : **63,8 %**, l'écho coûte 2,3 points. Sous 1480 px il se
resserre encore (−4 / −8), sous 1100 il n'en reste qu'un.
⚠️ Le tiroir n'a PAS d'écho : deux échos côte à côte, c'est aucun centre.

**Le fond.** `--bg-canvas: #F3F5F2` plus une trame de points NOIRS à 8 % tous
les 22 px : un gris plat et sale sur lequel une carto claire ne ressort pas. Le
canevas devient une **feuille** (#fdfdff, trame deux fois plus discrète, halos
froids dans les angles) posée sur un **plan de travail** plus soutenu
(#e9e7f2 + halos). C'est l'écart entre les deux qui détache le dessin, pas la
beauté de l'un ou de l'autre.
⚠️ La règle du canevas vit dans `cartography_viewer.html`, **pas** dans
`static/optiqcarto/style.css` : cette feuille est partagée avec l'ÉDITEUR et
recopiée dans le dépôt OptiqCarto. Le fond de l'éditeur est une autre décision,
qu'on ne prend pas en passant.

#### LE STUDIO — la carto sur une scène sombre (2026-10-02)

« Ça ne m'en met pas plein les yeux. » Deux passes **claires** n'y avaient rien
changé, et pour une raison de fond : la carto est un objet **CLAIR** — une
feuille blanche couverte de bandes pâles. Posée sur un fond clair, elle ne peut
pas éclater, il n'y a aucun écart à exploiter. On ne pend pas un tableau sur un
mur de la même couleur que lui.

La page devient donc une **scène sombre**. Le dessin est la seule chose
lumineuse de l'écran ; tout le reste — îlots de commande, tiroir, languette —
est en verre sombre et ne lui dispute jamais le regard. Bénéfice qu'on n'avait
pas vu venir : la barre de navigation de l'application est un galet
**graphite**, et elle flottait jusqu'ici sur du lavande pâle. Les deux se
raccordent enfin. La page Carte est explicitement HORS du design system clair
(voir « Design system UI ») : c'est la seule page qui a droit à cette identité.

- **La scène** : bleu de nuit `#080a14` (le noir pur écrase, celui-ci garde de
  la matière), une trame de 46 px pour l'échelle, trois halos aux angles, une
  **vignette** qui éteint les bords, et **3,8 % de grain** — sans lui, un fond
  fait de dégradés purs a l'air plat et numérique. Un souffle de 40 s derrière
  la carto : la page RESPIRE, elle ne clignote pas.
- **DEUX ÎLOTS, pas un bandeau.** Sur un 1920, une barre pleine largeur laissait
  700 px de vide entre le titre et les actions — et ce vide était du verre, donc
  il bouchait le haut de la scène. Deux îlots laissent passer l'aurore : ce qui
  est plein ne l'est que là où il y a quelque chose.
- **Le nom de la carto prend la police d'affichage** (Fraunces) : c'est le titre
  de la scène, une graisse de plus ne suffisait pas à le dire.
- **Les boutons sont en verre**, et il n'y a **qu'une seule couleur pleine** :
  ouvrir l'éditeur. Un éclat la traverse au survol — la seule fantaisie, et elle
  ne dure que le temps du geste. L'interrupteur « Connexions » s'allume en cyan,
  et son bandeau reprend ce cyan : on voit d'où il vient.
- **L'écho** (trois contours espacés) devient **lumineux** : sur du sombre, un
  trait PORTE. Il ne se dessine que s'il y a une carto (classe `a-carto`, posée
  par `carto_scene.js`) — sinon il encadrait l'écran d'accueil, trois anneaux
  autour de rien. ⚠️ Le tiroir n'en a pas : deux échos côte à côte, c'est aucun
  centre.

⚠️⚠️ **Le verre ne fonctionne QUE sur fond sombre.** Replié, le tiroir laisse la
carto s'étendre SOUS la languette : son fond devenait la feuille blanche et son
libellé clair disparaissait dessus — une pastille blanche avec du texte blanc.
Tout ce qui peut atterrir sur le dessin (languette, bandeau des connexions) est
donc une pastille **sombre et opaque**, jamais du verre.

⚠️ **Les trois états vifs d'une activité** — survol depuis le dessin, cible
d'une liaison, origine d'une liaison — étaient des fonds PÂLES posés en
`!important`. Sur le tiroir sombre, le libellé est clair : le fond pâle le
rendait invisible. Mêmes signaux, mêmes couleurs, en version lumineuse.

⚠️ **Remplacer une passe de style emporte aussi sa MISE EN PAGE.** La passe
précédente portait les deux ; la retirer a emporté `display: inline-flex` et
`gap` avec elle — icône et libellé se chevauchaient, et le segment des trois
gestes tombait hors de la barre. La structure des commandes est désormais
écrite à part, avant leur peau.

⚠️ `color: var(--st-encre)` était posé sur le **body**, alors que la variable
est déclarée sur `.carto-scene` : une propriété personnalisée se résout là où
elle est DÉCLARÉE, la règle ne faisait donc rien. Et la poser vraiment sur le
body aurait éclairci le texte des **fenêtres claires** de la page.

**La surface reste tenue** : **62,8 %** de la fenêtre sur un 1920×1080 (34 %
avant la refonte de la veille), rien ne déborde aux trois tailles. L'écho a déjà
coûté 10 points une fois — il se resserre sous 1480 px, et il n'en reste qu'un
sous 1100.

#### FLOTTANT — tranché sur maquettes, pas dans le code (2026-10-06)

Deux refontes écrites directement dans le code ont été refusées l'une après
l'autre (« hideux », puis « ça ne m'en met pas plein les yeux »). La troisième
est passée par un **canvas de maquettes** : cinq organisations dessinées à
l'échelle, la même carto et la même nav dans toutes, une seule décision à
prendre. **C'est la bonne méthode pour cette page** — une passe de style coûte
une demi-journée de code et se juge en trois secondes.

⚠️ **Et les deux premières ont échoué pour la même raison : j'avais redessiné
ce qui ne devait pas bouger.** La barre de navigation est un galet ARGENTÉ
clair à tuiles blanches — je l'avais maquettée en sombre ; et je changeais le
fond du dessin à chaque direction. Les deux sont fixes, au pixel près.

**Ce qui est retenu — la carto prend tout, les commandes se posent dessus.**

| Écran | Dessin affiché |
|---|---|
| 1920×1080 | 1904×974 — **89,4 %** de la fenêtre |
| 1440×900 | 1424×794 — 87,2 % |
| 1280×800 | 1264×694 — 85,7 % |

(34 % avant la première refonte, 62,8 % avec la scène sombre.) Rien ne déborde
aux trois tailles.

- **Deux couleurs, et deux seulement** : **ROSE** pour l'action et la sélection
  (ouvrir l'éditeur, la ligne choisie), **VERT** pour l'état actif (le mode
  Connexions, sa pastille, son bandeau). Tout le reste est neutre. Les passes
  précédentes empilaient sombre + rose + violet + cyan + ambre : « multicolore
  de partout ».
- **Deux îlots blancs** posés sur le dessin : l'identité à gauche, les
  commandes à droite. ⚠️ Ils vivent DANS `.carto-container` — posés au-dessus,
  ils reprendraient au dessin la hauteur qu'on vient de lui rendre. Et la barre
  qui les porte est en `pointer-events: none` : elle couvre toute la largeur,
  sans ça on ne pourrait plus déplacer la carto sous elle.
- **Les réglages se REPLIENT** (`#cs-plier`, classe `is-plie` sur `#cs-actions`,
  mémorisée dans `localStorage`) : l'îlot tombe de sept boutons à quatre
  pastilles. ⚠️ Le repli n'emporte QUE les réglages — recadrer est le geste le
  plus utile de l'écran, il reste dehors, toujours à un clic.
- ⚠️ **Le PLEIN ÉCRAN est retiré, remplacé par RECADRER.** Agrandir la fenêtre
  ne sert presque jamais sur cette page ; remettre le dessin au milieu de la
  zone, on le fait sans arrêt. Partis avec lui : `basculerPlein`, `majPlein`,
  le raccourci `f`, l'écouteur `fullscreenchange`, les règles `:fullscreen` et
  les clés `map.sc_plein` / `map.sc_quitter_plein`. Raccourcis restants :
  `c` recadrer, `l` la liste, `b` les réglages.

⚠️⚠️ **Renversement d'une décision écrite noir sur blanc ici-même.** « Le
tiroir POUSSE la carto, il ne la recouvre pas : la mini map et la pastille de
zoom du viewer vivent en bas à droite. » **C'était faux pour le viewer** — relu
dans le code plutôt que supposé : `renderMinimap()` sort immédiatement
(`OPTIQCARTO_READONLY && !CONSULTATION`), et `#zoom-pill` n'est pas dans
`cartography_viewer.html`. Ces deux pièces appartiennent à l'ÉDITEUR. Le coin
est libre, le panneau peut s'y poser — et c'est ce qui rend ces 89 % possibles.
⚠️ Conséquence : **on ne recadre plus après un repli**. La zone d'affichage ne
change pas de taille quand le panneau s'efface ; recadrer ferait sauter le
dessin pour rien. L'autre moitié de la note de la veille tombe avec.

⚠️ **Remplacer une passe de style emporte aussi sa MISE EN PAGE** — deuxième
fois. La structure des commandes (`display: inline-flex`, `gap`) est réécrite
en tête de la nouvelle section, avant leur peau.

Tests : `tests/test_94_page_carte_scene.py` (10 cas — le geste de recadrage à
la place du plein écran, le repli qui n'emporte que les réglages, et tout ce
qui flotte vérifié À L'INTÉRIEUR du corps). Suite : 2736 passés.
Maquettes : canvas « Page Carto — 5 organisations » (Dock/Capsule, Papier,
Volets, Flottant, Colonne).

#### LE BOARD — tuiles en haut, dessin au centre, liste à droite (2026-10-10)

Quatrième passe, et la première qui parte d'une maquette que l'UTILISATEUR a
retravaillée de son côté (board PDF, trois planches). Deux corrections
demandées, appliquées :
- **le vert et le violet deviennent notre ROSE FUCHSIA**, décliné en quatre
  teintes (voile `#fdf2f8`, pâle `#fce7f3`, poudré `#fbcfe8`, plein `#ec4899`
  → `#9d174d`). Le VERT ne reste que pour **l'état actif** du mode Connexions
  — c'est la règle déjà tenue partout dans l'app, et c'est la seule qui
  justifie une deuxième couleur ;
- **le bouton flèche n'existe pas** : le board posait un carré blanc à « ↗ »
  sur « Ouvrir l'éditeur ». Il ne correspond à aucune fonction — la tuile
  entière EST le lien. Retiré. Tenu par
  `test_94::test_le_bouton_fleche_du_board_n_existe_pas`.
  ⚠️ La tuile de repli « ‹ / B », elle, est GARDÉE : c'est le repli des
  réglages demandé à la passe précédente, pas une invention du board.

**Ce que le board change, et ce qu'il coûte.**

| Écran | Dessin affiché | Liste repliée |
|---|---|---|
| 1920×1080 | 1574×874 — **66,3 %** | 1878×874 — **79,2 %** |
| 1600×1000 | 1254×794 — 62,2 % | |
| 1440×900 | 1094×694 — 58,6 % | |
| 1280×800 | 934×594 — 54,2 % | |

Rien ne déborde, et aucun titre ne se tronque aux quatre tailles. ⚠️ **C'est
moins que les 89,4 % de la passe FLOTTANT** : les commandes reviennent dans le
FLUX (84 px de rangée) au lieu de se poser sur le dessin. C'est le prix de
l'organisation choisie, il est écrit ici pour qu'on ne le redécouvre pas.
⚠️ La rangée est mesurée à **84 px et non les ~150 du board** : un board se
dessine plus grand que nature, et chaque pixel pris là est pris au dessin.

⚠️⚠️ **Et cela renverse une note de la veille** — « on ne recadre plus après
un repli ». Le tiroir POUSSE de nouveau le dessin (c'est ce que montre la
planche 2 du board) : replier change donc la largeur de la zone d'affichage,
et sans recadrage on gagnerait 304 px de vide à droite au lieu d'un dessin
plus grand. `carto_scene.js` recadre **après** la transition (380 ms) : plus
tôt, le viewer se cadrerait sur une largeur qui n'est pas encore la bonne.

**La rangée du haut.** Une carte d'identité à gauche (pastille de rubrique,
nom de la carto en Fraunces 23 px, « Lecture seule »), puis une TUILE par
réglage : pastille d'icône colorée, mot, et le même glyphe en filigrane à 8 %.
UNE seule tuile est pleine — ouvrir l'éditeur. Le mode Connexions porte un
vrai **interrupteur** (et `aria-pressed`), gris éteint, vert allumé.

- ⚠️ **Le bandeau des Connexions était BLEU** alors que sa tuile s'allume en
  vert : deux couleurs pour un même état. Il prend celle de son interrupteur.
- ⚠️ Sous **1380 px** les quatre réglages deviennent des carrés (le libellé
  d'une tuile est un confort, une rangée qui déborde est un défaut), et
  l'interrupteur disparaît — sans ça il décalait son icône vers le haut et la
  tuile ne ressemblait plus à ses voisines.

**La bande des couleurs — ce qui manquait vraiment.** Le board remplissait le
bout vide de la carte d'identité avec une trame décorative. Elle porte à la
place **les bandes de la carto, dans leur ordre**, et c'est la CLÉ d'une
nouveauté de la liste : **la pastille numérotée d'une activité porte la
couleur de SA forme** sur le dessin (`editor.js` : `s.color = band.color`).
On retrouve une activité dans la carte sans lire son nom. Rien, jusqu'ici, ne
disait d'où venait une couleur.
- ⚠️ **La couleur vient d'un fichier Visio et part dans un attribut `style`** :
  seul un hexadécimal passe. Jinja protège de la sortie d'attribut, **pas** de
  l'injection d'une propriété CSS (« red;background:url(…) »). Même garde que
  `_echap_couleur` pour les vignettes de la page Partage. Vérifié **rouge** en
  retirant le filtre.
- Sans forme reconnue, pastille **neutre** — on n'invente pas une couleur,
  c'est le repli de `_extractLaneFill`.
- ⚠️ La bande s'efface **avant** que le nom de la carto ne se tronque (sous
  1600 px), et la pastille de rubrique part à son tour sous 1500 px : la barre
  de navigation dit déjà où on est, le NOM de la carto ne se lit nulle part
  ailleurs. Mesuré : plus aucune troncature de 1280 à 1920.
- Les noms de bande sont au **survol** — écrits, dix-huit libellés ne
  tiendraient dans aucune largeur.

**Le tiroir : le NOMBRE est le titre.** « ACTIVITÉS » en capitales, puis 42 en
Fraunces 38 px, puis son mot. ⚠️ **Deux éléments, pas un** : `activities_map.js`
écrit le compte par `textContent`, ce qui effacerait un `<strong>` niché
dedans. `majCompteListe(montrés, total)` remplace les deux écritures
d'autrefois (recherche, changement de calque) et affiche « 3/42 » quand on
filtre. Replié, le tiroir devient un **onglet vertical** au bord, qui porte son
compte.

**Les trois gestes de l'écran quittent la barre** et se posent au coin du
dessin — là où on les cherche en regardant la carte : « ? », **recadrer**
(le plus gros : c'est le plus utile) et replier la liste, chacun avec sa
lettre. ⚠️ Ils vivent **dans `.carto-left`** : `position: absolute` cherche son
repère dans le premier ancêtre positionné.

⚠️ **Cette passe remplace les DEUX précédentes dans `cartography.css`**
(« LA SCÈNE » puis « FLOTTANT », 820 lignes) : trois générations de règles s'y
empilaient, dont une bonne moitié de mort (`.cs-logo`, `.cs-meta`,
`.cs-entite`, `.cs-editeur`, `.cs-b`, `.cs-ic`, `.cs-seg`, `.cs-id-txt`…). La
section porte la MISE EN PAGE autant que la peau, écrite d'abord — **oublier
la première a déjà cassé cette barre deux fois**.

Tests : `tests/test_94_page_carte_scene.py` (16 cas — la rangée dans le flux,
ce qui se pose sur le dessin, le repli qui n'emporte que les réglages, la
flèche absente, la couleur des pastilles et son garde-fou, la bande des
couleurs, le compte en deux morceaux). Suite : 2794 passés. Éprouvé au banc
(`tools/devrun_import.py`) dans les deux langues, de 1280 à 1920 : repli des
réglages et sa mémoire, repli de la liste et son recadrage, languette,
raccourcis `c` / `l` / `b`, recherche, mode Connexions.

##### Reprise du board : la couleur, le glissé, le cadrage (2026-10-11)

Sept reproches sur la première implantation, tous mesurés avant d'être
corrigés.

**« On a du rose mais pas de vert, et la moitié des boutons ont perdu leurs
couleurs. »** Le mode Connexions était GRIS tant qu'il était éteint — il ne
devenait vert qu'une fois allumé, donc jamais à l'ouverture de la page. Un
bouton ne perd pas son identité parce qu'il est au repos : la tuile est verte
dans les deux états, c'est son INTERRUPTEUR qui dit lequel. C'est aussi la
seule façon de tenir la règle des deux couleurs sans que le vert soit
invisible neuf fois sur dix.

**« L'ouverture et la fermeture des réglages est brute. »** Elle l'était :
`display: none` ne s'anime pas. Deux tentatives, la seconde retenue :
- ⚠️ **colonne de grille `1fr` → `0fr`** : séduisant (on anime « jusqu'à la
  largeur naturelle » sans la connaître), mais mesuré — la boîte interne ne
  suit pas sa cellule (**237 px dehors, 100 px dedans** à mi-course), et un
  écart se creusait entre les tuiles et la poignée pendant tout le mouvement.
- **Retenu** : `carto_scene.js` mesure la largeur naturelle une fois
  (`--cs-pliable-w`), la boîte interne est **ancrée à droite** et garde cette
  largeur, et c'est le conteneur qui se referme. Les tuiles se rangent DANS la
  poignée au lieu de s'écraser sur place. ⚠️ Sans script le repli reste
  instantané (classe `a-mesure` posée seulement après la mesure) : jamais
  cassé, juste sans glissé. ⚠️ La mesure se refait à l'arrivée des polices
  (`document.fonts.ready`) — une police tardive change la largeur des
  libellés et la mesure d'avant ne vaudrait plus rien.
- ⚠️ **Même durée et même courbe pour la largeur et l'opacité** : à 0,26 s
  contre 0,42 s, les tuiles avaient disparu avant la fin du mouvement et on
  regardait un vide glisser.

**« Le bouton qui ouvre le menu ne peut pas avoir le même design que les
boutons qu'il contient. »** Exact : même rayon, même ombre, même silhouette —
on le prenait pour un cinquième réglage. Les tuiles sont POSÉES (ombre
portée), la poignée est CREUSÉE (pastille étroite, ombre interne, pas de
bordure). Deux vocabulaires, deux rôles.

**« Le bouton afficher la liste ne sert à rien. »** Il y avait TROIS portes
pour un seul interrupteur : la languette (ouvrir), le chevron du tiroir
(fermer), et ce bouton au coin du dessin. Retiré. Le coin ne porte plus que
l'aide et le recadrage.

**« Fermer la liste doit recadrer pour que la carto soit la plus grande
possible. »** Mesuré, et ce n'était pas qu'une affaire de réglage : la boîte
du dessin fait **8787 × 6221 (ratio 1,41)** quand la zone d'affichage fait
**1572 × 863 (1,80)**, ou **1876 × 863 (2,15)** liste repliée. Le cadrage est
donc borné par la **hauteur** dans les deux cas — replier n'ajoute que de la
largeur, et **à cadrage strict le dessin ne grandissait pas d'un pixel** : on
gagnait 304 px de vide. D'où deux cadrages, exactement comme demandé :

| | zoom | dessin | zone remplie |
|---|---|---|---|
| liste ouverte — **strict** | 0,1361 | 1196 × 847 | 74,6 %, tout visible |
| liste repliée — **généreux** | **0,1524** | 1339 × 948 | **78,5 %**, 9 % hors champ |

`fitView(bornes, plancher, tolerance)` : au-delà de 1, on agrandit jusqu'à
`tolerance` fois le cadrage strict — ⚠️ **jamais plus que le cadrage par
l'autre axe**, qui serait un zoom sur un morceau et non une carte. Le dessin
reste centré, donc ce qui dépasse se répartit des deux côtés et se retrouve au
glisser. La page décide (`TOLERANCE_GENEREUSE = 1.12`), l'éditeur applique.
⚠️ La tolérance arrive par `postMessage` d'une autre fenêtre : elle n'est
acceptée que comme nombre fini dans ]1, 2].

**« La typo est trop petite, du texte brut. »** Le libellé d'une tuile était
en 12,5 px — c'est pourtant le texte qu'on vient lire. Toute la rangée monte :
libellé 12,5 → **14 px** (14,5 sur l'action pleine), titre 23 → 25, pastille
de rubrique 10,5 → 11, « Lecture seule » 11,5 → 12,5, « Bandes » 9,5 → 10,5,
pastille d'icône 28 → 30 px. Le mode compact passe de 1380 à **1480 px** :
des libellés plus larges débordent plus tôt.

**« Ouvrir l'éditeur est rognée en haut. »** Elle ne l'était pas : `.cs-t:hover`
SOULÈVE une tuile de 2 px, et la barre touchait le bord d'une scène en
`overflow: hidden` — les 2 px du survol et le halo de l'ombre étaient coupés
net, d'où le coin carré dès qu'on passait dessus. La scène a 9 px de marge en
haut.

Tests : `test_94` (19 cas — une seule porte pour ouvrir et une pour fermer, le
conteneur qui permet le glissé, le cadrage qui dépend de l'état de la liste),
`test_79` (la signature de `fitView` est un contrat : le cliquet l'a vue
changer, et il garde en plus le fait que le cadrage généreux reste borné).
Suite : 2849 passés, `repet_image` 2821 + 28 sautés. `editor.js` resynchronisé
dans le dépôt OptiqCarto. Éprouvé au banc de 1280 à 1920, dans les deux
langues : plus aucun fragment français sur l'écran anglais.

##### Le zoom s'aligne sur la LARGEUR, et deux boutons qui ne ressemblent à rien d'autre (2026-10-11)

**Le cadrage, troisième version — et la bonne.** Les deux précédentes
partaient du cadrage « tout tient », borné par la HAUTEUR : mesuré, la boîte
du dessin (**8787 × 6221, ratio 1,41**) est bien plus carrée que la zone
(**1,80** liste ouverte, **2,15** repliée), si bien que le zoom valait 0,1361
dans les deux cas — replier la liste ne faisait pas grandir le dessin d'un
pixel. La tolérance (× 1,12) ne faisait que compenser à la marge.

Le zoom s'aligne donc sur la **largeur de la zone**, point. Une carto est
large et se lit de gauche à droite : on lui donne toute la largeur, et ce qui
dépasse en hauteur se parcourt au glisser.

| | zoom | dessin rendu | zone |
|---|---|---|---|
| liste ouverte | **0,1765** | 1551 × 1098 | 1572 × 863 |
| liste repliée | **0,2106** | 1851 × 1310 | 1876 × 863 |

La largeur est remplie exactement ; 27 % (liste ouverte) à 34 % (repliée) de
la hauteur passe sous la ligne de flottaison. ⚠️ **Un dessin plus haut que la
zone se cale en HAUT, pas au centre** : centré, on couperait son premier
couloir autant que le dernier — or une carto se lit depuis le haut.
`fitView(bornes, plancher, cadrage)` ; `cadrage: 'largeur'` est la seule
valeur reconnue, tout le reste retombe sur « tout tient » (les vignettes de
la comparaison avant/après en dépendent).

⚠️ **Et le zoom PAR DÉFAUT n'était pas celui de la page.** Le viewer se cadre
lui-même à la fin de son chargement (`fitView()` sans mode) : mesuré 0,1361 à
l'ouverture contre 0,2106 après un clic sur « recadrer ». La page écoute donc
`carto-state-ready` — le signal que l'éditeur émettait déjà — et impose son
cadrage.

**Les réglages sont REPLIÉS par défaut.** La page s'ouvre sur la carto, pas
sur ce qui sert à la régler. ⚠️ Seul un choix mémorisé les déplie : rien en
mémoire = replié.

**La poignée des réglages : un DISQUE vert en verre liquide.** Elle avait
encore la forme d'une tuile ; on la prenait pour un cinquième réglage.
Désormais 52 px de diamètre, trois verts superposés, des masses qui dérivent
sous la surface (`csLiquide`, 9 s) et le reflet figé par-dessus.
⚠️ **Le chevron passe au-dessus des deux pseudo-éléments** : ceux-ci sont
positionnés, ils peindraient donc par-dessus un contenu qui ne l'est pas.
⚠️ **Son état se lit sans la cliquer** : déployée elle est soutenue et calme,
repliée elle s'éclaircit et porte un anneau. Le chevron TOURNE (règle CSS sur
`.is-plie`) au lieu de changer de classe — remplacer une classe ne s'anime
pas. La lettre du raccourci a quitté le bouton : elle ne tient pas dans un
disque, elle vit dans l'info-bulle.

**« Ouvrir l'éditeur » : une PILULE à plusieurs fuchsias.** C'était un aplat
de la même forme que les réglages. ⚠️ Deux différences de FORME, pas
seulement de couleur : rayon plein (pilule) quand les réglages sont des
rectangles, et contenu en LIGNE (pastille à gauche, mot à droite) quand le
leur est en colonne. ⚠️ Et le rapport s'inverse — les réglages posent une
pastille VIVE sur un fond pâle, l'action une pastille PASTEL sur un fond vif.
Le fond empile quatre fuchsias (vif, pastel, prune, un soupçon de lilas) au
lieu d'un aplat, et un reflet traverse la pilule au survol : le seul mouvement
de la rangée, et il ne dure que le geste. Le filigrane est retiré — c'était
un repère de tuile, sur une pilule il ne fait que du bruit.

Tests : `test_94` (22 cas — le cadrage sur la largeur, le zoom par défaut, le
calage en haut, les réglages repliés par défaut), `test_79` (la signature de
`fitView` est un contrat, le cliquet l'a vue changer deux fois).
Suite : 2859 passés, `repet_image` 2831 + 28 sautés. `editor.js` resynchronisé
dans le dépôt OptiqCarto. Éprouvé au banc de 1280 à 1920, dans les deux
langues.

### L'import se lit aussi dans l'AUTRE SENS (2026-10-01)

L'écran de vérification des tâches ne savait poser qu'une question : pour chaque
activité DU FICHIER, laquelle de la carto ? Quand il en reste sans
correspondance, la question se pose pourtant à l'envers — « cette activité de ma
carto n'a aucune tâche : laquelle de ces lignes la remplit ? ». La bascule
**« Partir des activités sans tâches »** ouvre cette seconde lecture.

- **UNE décision, deux lectures.** Le panneau écrit dans le MÊME `S.choix` que
  la liste et rappelle la MÊME vérification : attribuer un groupe à une activité
  ici, ou choisir l'activité là-bas, produit exactement la même chose. Deux
  mécanismes auraient fini par dire deux choses —
  `test_84::test_l_autre_sens_pose_EXACTEMENT_le_meme_choix` le tient.
- ⚠️ **La bascule n'existe que s'il RESTE des lignes à placer** (au moins un
  groupe en `a_rattacher`) : tout rattaché, elle n'ouvrirait qu'un écran vide.
  ⚠️ Mais une fois DEDANS on y reste — la première version refermait le panneau
  d'un coup quand on plaçait le dernier groupe (`restants` tombait à zéro, la
  liste revenait sous le pointeur). La règle porte sur l'ACCÈS, pas sur le
  maintien de l'écran qu'on est en train d'utiliser ; le compte dit alors
  « Tout est placé. ».
- **`activites_vides`** (`_activites_sans_taches`, renvoyé par `/verifier`) :
  les activités des cartos visées qui ne portent encore AUCUNE tâche. ⚠️ « Vide »
  veut dire vide PARTOUT dans les cartos visées — une activité déjà remplie dans
  l'une d'elles n'est pas une activité à remplir, même si une autre carto la
  porte encore nue : on ne propose que ce qui est vraiment vierge.
- **Une activité ne reçoit qu'un groupe** : poser le nouveau retire d'abord ce
  qu'elle portait. Et un groupe déjà placé quitte les options des autres lignes
  (le serveur le repasse en `manuel`, il sort des « restants »).
- Les options montrent les groupes restants **plus celui qui vise déjà cette
  activité** — qu'il ait été choisi à la main ou rattaché tout seul : sans lui
  on ne pourrait plus le retirer, et on proposerait de remplir ce qui l'est déjà.
- La flèche de chaque ligne pointe **vers la gauche**, vers l'activité : tout
  l'écran lit fichier → carto, ici on lit carto ← fichier, et c'est la flèche
  qui le dit sans phrase.
- ⚠️ **Un champ de recherche, sinon l'écran n'est pas utilisable** : mesuré au
  banc, 42 activités vides pour 2 groupes à placer. Il **MASQUE**, il ne re-rend
  pas — réécrire le panneau à chaque frappe ferait perdre le curseur du champ
  qu'on tape (le piège déjà rencontré sur les cartes du plan de formation). Son
  texte vit dans `S.invFiltre` pour survivre au re-rendu que déclenche chaque
  attribution.
- ⚠️ **`change` ne se déclenche qu'à la PERTE DE FOCUS** : branché là, le champ
  ne filtrait rien pendant qu'on tape — 42 lignes visibles quoi qu'on écrive, et
  aucune erreur pour le dire. Il lui faut `input`.
- ⚠️ **`[hidden]` est une règle du NAVIGATEUR** : `.imh-inv-l { display: flex }`
  et `.imh-vide { display: flex }` l'emportaient, et le masquage ne masquait
  rien. Troisième fois que ce piège mord (les tuiles de la page Comptes en
  premier) — toute classe d'auteur qui pose un `display` doit déclarer son
  `[hidden]`.

Tests : `test_84::TestVerifier` (+4 ; 2 vérifiés **rouges** en retirant le
filtre). Suite : 2693 passés. Éprouvé dans les deux langues sur
`tools/devrun_import.py` : la bascule, l'attribution, le groupe qui quitte les
autres options, le retour qui montre le rattachement dans la liste, le filtre
(frappe, accents, sans résultat, survie au re-rendu), le dernier placement et la
bascule qui disparaît ensuite.

### Une carto par nom, un historique des imports, un filtre « sans tâches » (2026-09-29)

**Deux cartos ne peuvent plus porter le même nom.** `Code/entites_uniques.py`
est la source unique. Le nom d'une carto est ce qui la désigne PARTOUT :
sélecteur d'entité active, galerie de la page Partage, colonnes de la matrice
d'accès, tableau des compétences de la page RH, file des propositions. Cinq
« FluidClip » — ce que le dépôt de copies avait fabriqué sur le pilote —
rendent tous ces écrans indéchiffrables : rien ne dit laquelle on regarde.

- ⚠️ **La comparaison est NORMALISÉE** (minuscules, sans accents, espaces
  resserrés) : « FluidClip », « fluidclip » et « Fluid  Clip » désignent la même
  chose pour un lecteur, et c'est le lecteur qu'on protège. Elle est donc plus
  stricte qu'une contrainte UNIQUE en base, qui laisserait passer les trois —
  d'où l'absence d'index unique et le passage OBLIGÉ par ce module.
- ⚠️ **Créer ou renommer est REFUSÉ** (409, `code: "nom_pris"`), jamais corrigé
  en douce : on vient de taper ce nom, une carto qui s'appelle autrement est
  introuvable. Les chemins AUTOMATIQUES, eux, cherchent un nom libre
  (`nom_unique` → « Nom (2) ») : dépôt d'une copie, import d'un paquet
  `.optiqcarto`, clone du panel.
- ⚠️ **L'unicité est celle de l'INSTANCE, plus celle d'un compte.** Les deux
  anciens helpers (`_unique_entity_name_for`, `_unique_entity_name`) ne
  regardaient que les entités du destinataire : déposer la même carto chez six
  comptes donnait six homonymes, légalement.
- ⚠️ **Conséquence à rattraper** : la copie reçue ne porte plus le nom de la
  source, donc le rapprochement « l'entité de MÊME NOM qu'il possède déjà » ne
  trouvait plus rien et le bouton « Mettre à jour la mienne » disparaissait.
  `_entite_jumelle` compare désormais les noms de BASE (`base_nom`, qui retire
  un « (n) » final — et LUI SEUL : « Atelier 2 » est peut-être le vrai nom d'un
  second atelier). Quatre cas de `test_51` affirmaient l'ancienne règle ; ils
  affirment la nouvelle.
- **Les homonymes déjà en base** : `numeroter_doublons()` au démarrage,
  marqueur `entites_nom_unique` en BASE. La plus ANCIENNE prend le « 1 », puis
  « 2 », « 3 »… (`created_at`, à défaut l'id — les lignes d'avant la colonne la
  portent à NULL, ce sont les plus anciennes). ⚠️ **Chaque carto garde son
  ORTHOGRAPHE** : on numérote pour distinguer, on ne réécrit pas ce que
  quelqu'un a saisi. ⚠️ Et la reprise ne se joue qu'UNE fois : rejouée à chaque
  démarrage, elle renommerait « X 1 » en « X 1 1 » au premier homonyme suivant.

**L'historique des imports** — modèle `ImportRecord` (`import_records`), écrit
par `/api/import/importer` dans la MÊME transaction que l'import (une trace qui
survivrait à un import annulé mentirait), lu par `GET /api/import/historique`.
Une carto se remplit par petits bouts : un classeur de rôles un jour, les
tâches d'un atelier le lendemain, un fichier client le mois suivant. Sans
trace, « d'où vient cette tâche, et qui l'a mise là ? » n'a aucune réponse — les
données importées ne se distinguent plus de celles saisies à la main.

- **Où** : un **écran de la fenêtre « Importer des données »** — c'est elle qui
  regroupe déjà tout ce qui concerne les imports, et une seconde porte ailleurs
  finirait par ne plus dire la même chose. On y entre par une barre au bas de
  l'écran d'accueil de la fenêtre, et par un bouton de l'écran de fin (ce qu'on
  vient d'écrire a laissé une trace : la montrer ferme la boucle). Une frise, le
  dernier dépôt en haut, la couleur de la page où la donnée habite (rôles vert,
  outils orange, tâches violet, comptes rouge) — la convention des cartes de
  nature, pour reconnaître ce qui a été ajouté sans lire son nom.
  ⚠️ **Ce n'est pas une ÉTAPE** : le rail des quatre étapes est vidé et le titre
  de la fenêtre devient « Historique des imports » (puis reprend celui du
  gabarit en sortant) — laisser le rail ferait croire qu'on a quitté le parcours
  en cours de route. Le retour ramène à l'écran d'où l'on vient.
  ⚠️ **Le détail est REPLIÉ par défaut** : ouvert, une entrée de dix-huit
  libellés occupe tout l'écran et on ne voit plus qu'un import à la fois. Un
  historique se parcourt d'abord du regard, le détail se demande.
  ⚠️ En mode **Comptes** (`?pour=comptes`) l'entrée n'existe pas : un compte ne
  vit dans aucune carto.
  ⚠️ **Deux vues, deux questions.** « Qu'a-t-on importé DANS cette carto ? » —
  et « qu'a-t-on importé, tout court ? », celle qui manquait : quand on cherche
  d'où vient quelque chose on ne sait pas toujours où regarder, et un dépôt qui
  visait trois cartos ne se lisait qu'en les ouvrant une à une. `?portee=tout`
  balaie toutes les cartos LISIBLES, `?entity_id=` n'en regarde qu'une. Le
  `<select>` porte « Toutes les cartos » en tête, et chaque entrée de la vue
  d'ensemble porte **sa** carto en pastille — cliquable, elle ouvre cette carto
  seule.
  ⚠️ **La vue d'ensemble a EXACTEMENT la même portée que la vue par carto** :
  elle ne montre rien qu'on ne puisse déjà aller lire. Et les cartos du
  `<select>` viennent de la RÉPONSE, pas de `CTX.cibles` (les cartos où l'on
  ÉCRIT) : tout ce qui paraît dans l'ensemble doit pouvoir s'ouvrir seul, sinon
  le sélecteur et la liste se contredisent.
  ⚠️ **« Le même dépôt a servi à … » disparaît en vue d'ensemble** : les deux
  lignes y sont côte à côte, le redire ne ferait que répéter ce qu'on voit.
  ⚠️ L'entrée de l'ACCUEIL ouvre l'ensemble (on vient y chercher d'où vient
  quelque chose) ; le bouton de l'écran de FIN ouvre la carto qu'on vient de
  remplir. L'aller-retour réseau vérifie qu'on est toujours sur la même portée
  avant d'écrire la réponse à l'écran.
  ⚠️ **`data-carto` était DÉJÀ pris** : le répartiteur de clics de la fenêtre le
  lit AVANT le `switch` (`if (ds.carto) return basculerCarto(…)`), si bien que
  l'entrée de l'historique ne faisait que cocher une carto dans la portée — sans
  la moindre erreur. L'attribut s'appelle `data-histo-carto`.
- **Une ligne par (dépôt, carto, nature)**, réunies par `lot` : c'est ce qui
  permet de dire « le même dépôt a servi à … », qu'on ne peut pas deviner ligne
  par ligne. ⚠️ Un **rôle** importé dans deux cartos ne laisse qu'UNE trace : un
  rôle appartient à l'entreprise, créé pour l'une il existe pour les autres —
  deux traces diraient qu'il a été ajouté deux fois. Un **outil** appartient à
  sa carto, lui en laisse deux.
- ⚠️ `detail` porte les **LIBELLÉS**, pas des identifiants : l'historique doit
  rester lisible même si l'objet a été renommé ou supprimé depuis. Plafonné à
  400 entrées par ligne ; au-delà, « et n de plus ».
- ⚠️ **Rien n'est écrit quand rien n'a été ajouté** : relire un fichier déjà
  importé est le geste le plus courant, une trace vide ferait croire à un
  import.
- ⚠️ **Lisible par qui peut OUVRIR la carto**, pas seulement par qui a importé :
  la question se pose d'abord à celui qui trouve la tâche.
- ⚠️ `fichier` et `feuille` viennent du navigateur : tronqués, jamais
  interprétés — des étiquettes, pas des chemins.
- ⚠️ Supprimer une carto efface ses `import_records` — **et ses
  `entity_status_access`, qui manquaient** au ménage de `delete_entity` depuis
  la section « accès par statut » : PostgreSQL applique les clés étrangères,
  effacer une carto dont les statuts avaient été réglés aurait échoué.

**Les trois « promesses » de l'écran d'accueil de l'import sont retirées**
(`.imh-promesses`, quatre clés `imph.promesse_*`) : « Vous voyez chaque ligne
avant d'importer », « L'IA les retrouve, sans rien inventer », « Une carto,
plusieurs, ou toutes à la fois ». Elles annonçaient ce que la fenêtre fait de
toute façon, et occupaient une rangée entière au-dessus des cartes qu'on vient
choisir.

**Le filtre « sans tâches »** (liste des activités) : les activités nées de la
carto qu'on n'a pas encore complétées. ⚠️ Le cadrage est **SERVEUR**
(`_cadrer`) : la liste arrive par lots de 20 et la recherche passe déjà par le
serveur — un masquage en JS ne cacherait que ce qui est déjà à l'écran, et le
compte serait faux. L'état vit dans l'URL (`?sans_taches=1`), donc il survit au
rechargement et se partage ; `/view/more` et `/view/search` le portent aussi.
⚠️ Le compteur du bouton porte sur **toute la carto**, pas sur le lot affiché :
il dit ce qui reste à faire, il ne bouge pas quand on filtre.

**Le bouton « Importer des tâches » a quitté la page Activités** : l'import
passe par la page Carte, deux portes pour un même geste finissent par donner
deux comportements. Supprimés avec lui : `import_tasks_modal.html`,
`static/js/import_tasks.js`, `static/import_tasks.css`, le blueprint
`Code/routes/import_tasks.py` (`/api/import-tasks/*`, injoignable désormais et
sans contrôle d'accès), `tests/test_26_import_tasks.py` et les deux clés
`act_list.import_*`. `import_tasks_modal.html` sort des inventaires de dette de
`test_78` et `test_89`.

⚠️ **Trois pièges rencontrés, tous déjà connus sous une autre forme :**
- **`/activities/map` est rendue comme un FRAGMENT** — pas de `<!DOCTYPE>`, pas
  de `<html>`, pas de `<head>` : le navigateur bâtit un document implicite dont
  `documentElement.lang` est VIDE, et les dates de l'historique repartaient en
  français dans l'interface anglaise. Toute date affichée par un script de cette
  page doit donc lire la langue du catalogue qui l'accompagne — `IMPH_I18N.lang`
  pour la fenêtre d'import, qui le portait déjà. Le défaut de structure de la
  page, lui, reste entier.
- **Une clé i18n CONSTRUITE se relit tronquée à son préfixe** : `ML('h_nat_' +
  n)` est relevé comme la clé « h_nat_ ». Les quatre clés sont écrites en
  entier. ⚠️ Et le contrôle lit aussi les COMMENTAIRES : écrire l'appel fautif
  dans le commentaire qui l'explique le fait échouer à nouveau.
- **`_CLE` exige un `{` ou une `,` juste avant la clé** : un commentaire glissé
  entre l'accolade ouvrante et la première clé d'un `window.XXX_I18N` rend
  cette clé invisible au contrôle d'injection. Le commentaire se met AVANT
  l'affectation.

Tests : `tests/test_91_noms_uniques_et_historique.py` (26 cas ; 13 vérifiés
**rouges** en neutralisant `nom_libre`, `_tracer` et `_cadrer`). Suite : 2644
passés, et `tools/repet_image.sh` 2616 passés + 28 sautés.
⚠️ `test_65::test_le_pont_du_hub_expose_la_route` relit les sources de `hub/`,
absentes de l'arbre d'image : il échouait à CHAQUE répétition depuis le 16/09.
Il saute désormais, comme la fixture `pulse_app` — un contrôle qui rougit
toujours n'est plus lu, et le jour où il a raison personne ne regarde.

### Report sur le pilote : 380 rôles réunis en 56, sans rien perdre (2026-09-28)

Report habituel, rejoué **tel quel** d'après la recette du 17/09 : l'arbre de
staging à l'identique, plus le seul fichier propre au pilote
(`.github/workflows/deploy-beta.yml`), et l'invariant vérifié AVANT de pousser —
`git diff --name-status origin/staging <commit>` ne rend que ce fichier.
Construit avec un **index temporaire** (`GIT_INDEX_FILE` + `read-tree` +
`commit-tree`, deux parents) : rien à sortir ni à remettre dans le worktree
courant, donc rien à casser en chemin. 11 commits de retard rattrapés.

**Ce que la réunion des rôles a fait sur une base EN SERVICE.** Relevé avant
(`tools/db/etat_entites.py`, lecture seule) : **380 lignes de rôles pour 56
noms distincts**, 34 noms à réunir — le modèle « un rôle par carto » avait
fabriqué jusqu'à **14 exemplaires du même rôle** (« Supplier », « Network »…).
Après le démarrage : **56 lignes pour 56 noms, plus aucun doublon.**
⚠️ Et surtout, **écart NUL sur toutes les autres tables métier** (comparées au
manifeste de la sauvegarde) : 8 titulaires, 813 `activity_roles`, 579
`task_roles`, 601 activités, 932 tâches, 985 liens, 348 compétences, 4 pièces
jointes. La réunion re-pointe, elle ne perd pas.
- ⚠️ Deux rôles « Développeur de compétences » portaient CHACUN un titulaire
  (#607 et #608) : à égalité, c'est le plus petit id qui est gardé et l'autre
  titulaire est reporté dessus — les deux se retrouvent sur le même rôle.
- 3 cartos **sans propriétaire joignable** (#12, #28, #30) : elles redeviennent
  supprimables. `purchase` #30 en fait partie — c'est l'« entité fantôme »
  signalée par l'utilisateur.

⚠️ **Sauvegarde AVANT, et relue.**
`~/AFDEC/sauvegardes/optiqfluent_pilot-2026-09-28` — 53 tables, 13 470 lignes,
les 53 relues sans écart avec le manifeste, et les 4 pièces jointes décodées
depuis le base64 jusqu'à leurs octets de signature (dont la carte Visio
harmonisée du client, 902 068 octets — le même compte qu'au 17/09).
L'inventaire d'avant est archivé À CÔTÉ de la sauvegarde
(`_inventaire_avant.txt`) : sans lui, on ne peut plus dire ce que la réunion a
changé une fois qu'elle a eu lieu.

⚠️ **Livré à 11h38, lundi matin en Inde** — contre la règle « les correctifs
partent le soir ». Décision explicite de l'utilisateur, après lui avoir posé la
question avec l'heure locale et le fait que la reprise TOUCHE AUX DONNÉES.
Aucune conséquence observée (le service répond, les tables métier sont
intactes), mais la règle reste la bonne : un redémarrage coupe les requêtes en
vol, et une migration de données ne se rattrape que par la sauvegarde.

### Le pilote repris sur staging — 108 commits d'un coup (2026-09-17)

`optiqfluent-staging` avait 108 commits de retard et 39 commits propres. Sur le
fond, pourtant, l'écart tenait à **un seul fichier** : son
`.github/workflows/deploy-beta.yml`. Les 39 « commits propres » refaisaient un
travail que staging portait déjà par d'autres commits (losanges, paquet
`.optiqcarto`, OptiqPulse…). La fusion s'est donc faite en prenant **l'arbre de
staging à l'identique** puis en y remettant ce workflow — et l'invariant se
vérifie d'une commande : `git diff --name-status origin/staging` ne doit rendre
que `deploy-beta.yml`. À rejouer tel quel au prochain report.

⚠️ **Le Dockerfile du pilote ne différait que par l'absence de `WITH_TESTS`**,
que staging a ajouté depuis. Le durcissement (licence, prompts chiffrés,
bytecode) vit dans le MÊME Dockerfile pour les deux : il n'y a pas de
« Dockerfile client » séparé à préserver. Le workflow pilote ne passe pas
`--build-arg WITH_TESTS=1`, donc l'image du client reste sans tests.

**La bascule aux quatre paliers sur une base en service.** Relevé avant
(`tools/db/etat_statuts.py`, lecture seule) : 8 comptes — 2 `administrateur`,
6 `manager`, **aucun `user`**, et 20 cartos toutes PRIVÉES. Conséquences, toutes
vérifiées après le démarrage :
- les 6 `manager` sont devenus `coordinateur`, **et rien d'autre n'a bougé sur
  ces lignes** (comparaison champ à champ avec la sauvegarde) ;
- aucune carto commune → personne ne perd le droit de proposer, et
  ⚠️ `can_edit` rend la main au **propriétaire d'une carto privée quel que soit
  son statut** : les six comptes ARaymond continuent d'éditer la leur ;
- 16 tables métier comparées à la sauvegarde : **écart nul**.

⚠️ **Sauvegarde AVANT, et relue.** `~/AFDEC/sauvegardes/optiqfluent_pilot-2026-09-17`
— 49 tables, 11 537 lignes, les 49 relues sans écart avec le manifeste, et les
4 pièces jointes décodées depuis le base64 jusqu'à leurs octets de signature
(dont la carte Visio harmonisée du client, 902 Ko). Une sauvegarde qu'on n'a pas
relue ne prouve rien — c'est ce qui avait coûté 13 fichiers en septembre.

### ⚠️ `/healthz` n'atteint JAMAIS l'application sur un `*.run.app`

Le frontend Google l'intercepte et sert sa PROPRE 404. La route existe pourtant
bien dans `Code/app.py` : la requête n'arrive simplement pas. **Comment on le
prouve** — les deux 404 ne se ressemblent pas : celle de `/healthz` n'a ni
cookie de session Flask ni `x-cloud-trace-context`, alors qu'une route
réellement inconnue de l'app en porte. C'est le seul moyen de distinguer « la
route manque » de « la requête n'est pas passée ».

Le hub et pulse avaient déjà basculé sur `/health` pour cette raison ; le test
de fumée de `deploy-beta.yml`, lui, sondait encore `/healthz` — il **échouait
donc à chaque livraison du pilote**, après un déploiement pourtant réussi. Un
contrôle qui rougit toujours n'est plus un contrôle : on finit par ne plus le
lire, et le jour où il a raison, personne ne regarde.

- `Code/app.py` expose désormais `/health` **à côté de** `/healthz`.
- ⚠️ `/healthz` est CONSERVÉ : la sonde de `distribution/docker-compose.yml` et
  `tools/test_install.sh` l'appellent sur `localhost`, où rien ne s'interpose.
  Le contrôle ne signale donc que les sondes vers une adresse EXTERNE.
- `tools/deploy/deploy_cloudrun.sh` avait le même défaut.
- Tests : `test_72::TestLaSondeDeSanteEstJoignable` (2 cas, le second vérifié
  **rouge** sur la branche pilote avant le correctif).

### Savoir ce qu'une bascule de statuts fera, AVANT de la faire

`tools/db/etat_statuts.py --url … [--details]` — **lecture seule**
(`set_session(readonly=True)`, et deux tests interdisent toute écriture dans son
code : il tourne sur la base d'un client). Il répond aux trois questions qui
décident de la manœuvre : quels libellés sont écrits en base (le champ est du
texte libre), quel palier chaque compte aura après la reprise, et combien de
cartos sont COMMUNES — la seule situation où un compte ordinaire perd un droit
réel.
⚠️ Sa prédiction est confrontée à `Code/permissions` par un test, sur tous les
libellés rencontrés : un outil d'inventaire qui diverge du code décide à côté,
et c'est sur lui qu'on s'autorise à toucher aux comptes d'un client.

### ⚠️ Les deux instances ont partagé UNE SEULE base jusqu'au 14/09/2026

`PROD_DATABASE_URL` et `STAGING_DATABASE_URL` pointaient tous deux sur `neondb`.
La version officielle de l'entreprise et le bac à sable travaillaient donc sur les
MÊMES données, sans que rien ne le dise. Conséquence directe : la remise à zéro du
10/09, faite sur « la base de staging », a effacé les données officielles — 30
entités, 59 comptes, 991 activités. Remises en place le 14/09 depuis la sauvegarde.

**Séparation faite** : `devoptiq_sandbox` (base neuve) pour staging, `neondb` pour
la version officielle. ⚠️ Le garde-fou `--expect-db` de `reset_db.py` ne valait rien
tant que les deux bases portaient le MÊME NOM : il passait des deux côtés. Deux noms
distincts, c'est ce qui rend la vérification réelle.

**Comptes** (les deux instances) : `mael.pierre.girardin@icloud.com` / `testtest`,
administrateur. `afdec.enterprise.services@gmail.com` n'existe plus nulle part ;
elle reste seulement dans `DEFAULT_FRENCH_ACCOUNTS` (langue, pas connexion).

### Sauvegarder et restaurer (`tools/db/`)

- **`dump_db.py`** — sauvegarde JSON complète, un fichier par table, sans `pg_dump`.
  ⚠️ **Sa première version DÉTRUISAIT le binaire** : `bytes(v).decode("utf-8",
  "replace")` remplaçait chaque octet non-UTF-8 par U+FFFD. Les 13 fichiers de
  `file_blobs` de la sauvegarde du 10/09 avaient perdu 31 à 45 % de leurs octets —
  et la base ayant été vidée derrière, c'était leur seule copie. **Ces 13 fichiers
  sont perdus** (docx, xlsx, pdf, une photo ; déposés entre avril et juin 2026).
  Encodage base64 désormais, relu par la restauration.
- **`restore_db.py`** — retire les 78 clés étrangères, vide, charge, **les remet —
  ce qui VALIDE les données au passage** — puis repositionne les 47 séquences (sans
  quoi le prochain enregistrement entre en collision de clé primaire, des jours plus
  tard). Le tout dans **UNE transaction** : un échec à la 50ᵉ table rend la base
  intacte (vérifié deux fois en conditions réelles). N'écrit que les colonnes
  présentes des deux côtés et nomme les écarts. **Contrôle préalable d'unicité** :
  la base du 10/09 portait 7 e-mails en double alors que `users.email` est devenu
  UNIQUE depuis — sans ce contrôle on l'apprenait à la 40ᵉ table.
- **`set_password.py`** — pose un mot de passe connu sur un compte après
  restauration (les comptes reviennent avec celui de la sauvegarde). Passe par
  `Code/security.py` et **relit le hash après commit** pour le vérifier.
- ⚠️ **Une sauvegarde ne se restaure pas dans le schéma qu'elle a quitté.** Trois
  familles d'écart rencontrées, toutes silencieuses : des tables disparues
  (`user_competencies`, `performance_personnalisee_historique`), des tables que
  l'application crée **à l'exécution** et non par `create_all` (`training_plan`,
  `prerequis_comment` — créées par `competences_plan._ensure_tables_exist`, à créer
  AVANT la restauration sinon leurs 44 lignes sont perdues), et des contraintes
  ajoutées après coup que les anciennes données ne respectent pas.
- ⚠️ **Les migrations à chaud ne s'appliquent qu'au DÉMARRAGE de l'app sur cette
  base.** `neondb` a refusé la restauration tant que `softskills.niveau` était en
  VARCHAR(10) : l'instance officielle tournait encore sur le code du 10/09, elle
  n'avait donc jamais joué l'élargissement. Un `ALTER` à la main a suffi. À garder
  en tête chaque fois qu'on écrit dans une base que l'app en service n'a pas encore
  redémarrée avec le code courant.

### ⚠️ `softskills.niveau` était en VARCHAR(10) — 500 sur toute base neuve

La valeur STOCKÉE est le libellé HSC entier (« 2 (Acquisition) », 15 caractères) :
c'est ce qui permet à `hsc_level_label()` de traduire l'affichage sans jamais
réécrire la base. **Aucun** des quatre niveaux ne tenait dans 10 caractères — donc
chez un nouveau client, enregistrer une HSC tombait en 500. Invisible pour la
suite : elle tourne sur SQLite, **qui n'applique PAS les longueurs de VARCHAR**.
Même famille que `BOOLEAN DEFAULT 0` et `user_activity_plans`. Modèle élargi à 50,
migration à chaud pour les bases déjà déployées, test dans
`tests/test_67_schema_postgres.py` (vérifié rouge sur l'ancien modèle).

- ⚠️ **`neondb` et `optiqfluent_pilot` vivent sur le MÊME endpoint Neon**
  (`ep-solitary-bonus-abrhwgrs`). Une URL mal recopiée efface le travail du client :
  `tools/db/reset_db.py` exige `--expect-db` et refuse d'agir si le nom ne correspond pas.
- **Outils de base** : `tools/db/dump_db.py` (sauvegarde JSON complète, sans `pg_dump` —
  Neon n'est pas joignable avec `psql` depuis tous les postes) et `tools/db/reset_db.py`
  (efface le schéma, laisse le démarrage NORMAL de l'app le reconstruire — donc les
  migrations à chaud sont exercées au passage — puis crée les comptes de départ).
  Trois garde-fous : `--expect-db` obligatoire, `--yes` explicite, sauvegarde exigée.
- **Sauvegardes hors dépôt** (`~/AFDEC/sauvegardes/`) : `neondb-2026-09-10` (l'état
  d'avant la remise à zéro — 59 tables, 25 853 lignes), `neondb-2026-09-10-corrige`
  (la même, doublons d'e-mail résolus : c'est celle qui a été restaurée),
  `neondb-2026-09-14-avant-restauration` (filet de sécurité pris juste avant).
- ⚠️ **La remise à zéro a révélé un défaut de longue date** : `user_activity_plans` était
  lue et écrite en SQL brut par `plan_storage.py` mais **rien ne la créait**. Elle
  survivait sur les instances anciennes comme vestige d'une migration disparue ; sur
  toute base NEUVE — donc chez un nouveau client — le premier enregistrement d'un plan
  tombait en 500. Pire : `tests/test_28_plan_storage.py` **fabriquait la table lui-même**
  (« absente de SQLAlchemy models », disait son commentaire), si bien que ses 20 tests
  passaient. La table a maintenant son modèle `UserActivityPlan`, et le contournement du
  test est devenu une vérification. Même famille que `entreprise_settings` en son temps.
- ⚠️ **Le hub déclarait des instances « injoignables » alors qu'elles répondent.**
  Cloud Run redescend à zéro instance ; mesuré depuis un poste, `devoptiq-staging` répond
  en **15,2 s** à froid (démarrage lourd : create_all + migrations, `--cpu 2`) et
  `optiqfluent-staging` en 8,9 s — la sonde coupait à **12 s**. Délai porté à 28 s, et un
  dépassement rend désormais **« en veille »** (bleu calme) et non « injoignable » (rouge
  d'alerte) : le service dort, il n'est pas cassé.

### Un développeur de compétences l'est PAR RÔLE, pas par personne (2026-10-13)

« Je suis développeur de compétences pour 2 rôles pour une personne qui en a
4. Or quand je vais sur l'évaluation, je vois les 4 rôles alors que je ne suis
censé pouvoir en évaluer que 2. » C'était exact — et ce n'était pas qu'un
affichage.

⚠️ **`encadre()` répond par PERSONNE** : vrai dès qu'il existe UN rattachement,
quel que soit le rôle
(`UserRole.filter_by(user_id=…, manager_id=dev).count() > 0`). `peut_lire`
ET `peut_noter` s'appuyaient dessus, et la synthèse bouclait sur TOUS les
`UserRole` de la personne. Il ne voyait donc pas seulement les quatre rôles :
il pouvait les **noter**.

- `encadre_pour_role(dev, collaborateur, role)` : le lien **global**
  (`users.manager_id`) couvre tous les rôles — c'est son rôle — le lien **par
  rôle** ne couvre que le sien. C'est la distinction que `_dissoudre_lien_global`
  maintient depuis le début côté ÉCRITURE, et qui n'était lue nulle part côté
  lecture.
- `roles_suivis(acteur, collaborateur)` rend `None` pour « aucune
  restriction » (soi-même, lien global, coordinateur). ⚠️ `None` et une liste
  VIDE ne disent pas la même chose : les confondre rouvrirait le défaut dans
  l'autre sens, en cachant les rôles d'un développeur global.
- ⚠️ **Les routes qui ÉCRIVENT EXIGENT le rôle** (`role_required`, 400) :
  sans lui le contrôle retombe sur la règle par personne, donc l'omettre
  suffirait à contourner le contrôle. L'écran l'envoyait déjà.
- ⚠️ **Et le rôle doit PORTER l'activité** : sinon on noterait l'activité d'un
  rôle qu'on ne suit pas, en présentant celui qu'on suit.

⚠️⚠️ **Deux routes n'avaient AUCUN contrôle**, trouvées en tirant le fil :
- `GET /mastery/activity/<u>/<a>` — tout compte connecté lisait le niveau de
  n'importe qui sur n'importe quelle activité, **preuves comprises** ;
- `POST /mastery/required` — le niveau ATTENDU d'un rôle est une décision, et
  n'importe quel compte connecté la posait. Il faut désormais suivre ce rôle,
  ou être coordinateur.

⚠️ Le test `test_77::test_le_rattachement_PAR_ROLE_ouvre_le_meme_droit`
affirmait le DÉFAUT (« un rattachement par rôle ouvre le même droit ») : il est
renversé. Son décor explique d'ailleurs le symptôme — le développeur n'était
rattaché qu'à `collab`, et c'est le lien par rôle posé sur `tiers` qui lui
ouvrait TOUS les rôles de `tiers`.

Tests : `tests/test_104_developpeur_par_role.py` (15 cas, le scénario du
client au mot près — 3 vérifiés **rouges** en remettant la règle par
personne). `test_57` passe le rôle partout (la route l'exige), et son helper
nomme ses rôles de façon unique : les rôles sont COMMUNS à l'entreprise
depuis le 23/09, un nom fixe fait collision dès que deux tests tournent.
Suite : 2958 passés, `repet_image` 2930 + 28 sautés.

### Chaque bouton de la carte dit ce qu'il fait (2026-10-13)

« On ne sait pas à quoi servent les boutons. Seul le bouton Liens a une
légende quand on le survole. » C'était exact, et vérifiable : un seul des
cinq portait un `title`. Et sous le seuil du mode compact leur LIBELLÉ est
masqué — ils deviennent des carrés d'icône muets, ce qui est précisément
l'écran sur lequel on les regardait.

- Une bulle **dessinée par la page**, pas un `title`. Celui du système met
  une seconde à sortir, ne se voit jamais au clavier, et se superposerait à
  la nôtre si les deux cohabitaient (le piège déjà rencontré sur la matrice
  RH) : aucun des cinq boutons n'en porte plus. `aria-label` porte la MÊME
  phrase, parce qu'une bulle dessinée par la page n'existe pas pour un
  lecteur d'écran. Elle sort aussi au `:focus-within`.
- Elle dit ce que le bouton FAIT, pas comment il s'appelle : une bulle qui
  répète le libellé n'apprend rien.
- **Les libellés tiennent jusqu'à 1200 px** (contre 1480) : tuiles resserrées
  (114 → 102 px de large), et sous 1340 px c'est la taille du NOM de la carto
  qui cède, pas les libellés qui disent à quoi servent les boutons.

⚠️ **DEUX boîtes tranchaient la bulle, et le symptôme trompe** : on voit son
BEC et pas elle, donc on cherche un z-index.
1. `.cs-pliable` est en `overflow: hidden` — c'est ce qui fait glisser les
   tuiles dans la poignée au repli — et il coupe au ras. Il lui faut de l'air
   dessous (`--cs-tt-air`, rendu à la mise en page par une marge négative :
   la rangée ne grandit pas d'un pixel, et la boîte interne remonte son bas
   d'autant, sinon les tuiles s'étireraient dedans).
2. `.carto-container` vient APRÈS la rangée dans le document et il est en
   `position: relative` : à z-index automatique, c'est lui qui passait
   devant. La rangée prend donc `position: relative; z-index: 20`.

⚠️ **Et la requête qui réduit le titre ne faisait RIEN** : déclarée avant la
règle de base qui le pose à 25 px, à spécificité égale c'est la dernière
déclarée qui gagne. Troisième fois que ce piège mord dans cette feuille.

Tests : `tests/test_94_page_carte_scene.py` (28 cas). Suite : 2910 passés.

### L'audit du client : les quatre premiers défauts (2026-10-11)

Cinq classeurs de remarques (03–05/10/2026), confrontés au code un par un.
Ce qui suit est ce qui a été **vérifié dans le dépôt** puis corrigé ; le tri
complet (ce qui est déjà réglé, ce qui relève d'une décision produit, ce qui
tient à la qualité du fichier source du client) a été rendu à part.

#### ⚠️⚠️ 39 fichiers de routes écrivaient SANS aucun contrôle d'accès

Le plus gros point, et plus large que ce que l'audit avait vu. `tasks.py`
(5 routes d'écriture), `gestion_outils.py` (4), `roles.py`, `savoirs`,
`savoir_faires`, `aptitudes`, `softskills`, `constraints`,
`propose_from_file.py`, `time_view.py` (14)… **aucune garde, et aucun
`before_request` global non plus**. Le tableau des droits disait pourtant
depuis le début que `user` consulte et ne modifie rien.

Mesuré, porte retirée : un compte `user` crée une tâche et réécrit la
description d'un outil du catalogue partagé ; et ⚠️ **`POST /tasks/add` SANS
AUCUN COMPTE rendait 201 et écrivait la tâche en base** — pire que le défaut
signalé, et invisible parce que *toute la suite de tests écrivait de cette
façon*.

`Code/ecriture.py` — **une porte centrale, pas 39 gardes**. Trente-neuf
fichiers corrigés un par un, c'est trente-neuf occasions d'en oublier un, et
surtout la quarantième route écrite demain serait ouverte à nouveau. Ici le
défaut est fermé par CLASSE : toute méthode d'écriture est refusée sauf ce qui
est nommé, et le droit consulté est `edit_carto` — celui du tableau réglable,
pas une liste de statuts en dur.

- ⚠️ **La liste d'exemptions est le cœur du fichier**, et elle a été écrite
  d'après ce que la porte a RÉELLEMENT refusé en rejouant la suite (66 refus
  journalisés avec le statut du compte), pas d'après ce qu'on imaginait :
  trois familles n'avaient pas été prévues. Elle ne contient que des routes
  qui portent DÉJÀ une règle plus fine — `/plan` (le développeur de
  compétences est désigné par un rattachement, pas par un statut),
  `/cartography/api` (c'est `/api/save` qui distingue « proposez » de
  « lecture seule »), `/comptes`, `/gestion_rh`, `/mastery`, `/api/import`,
  `/activities/api/entities`. La porte s'efface devant elles, elle ne les
  remplace pas.
- ⚠️ **La règle anonyme s'efface sous TESTING, volontairement** : 115 tests
  fabriquent des clients anonymes (`app.test_client()`) pour s'isoler de la
  session partagée, pas pour éprouver l'anonymat. Les reprendre un par un
  noierait la correction. **Conséquence à ne pas oublier : passer la suite ne
  prouve PAS que l'anonyme est fermé** — seul `test_102` le prouve, en
  appelant `porte()` avec `en_test=False`. Un test dit la dérogation à voix
  haute pour qu'elle ne pourrisse pas.
- ⚠️ La tentative d'avant est instructive : donner une identité par défaut à
  tous les clients de test (un fixture autouse) a cassé les tests qui
  éprouvent VRAIMENT l'anonymat (`test_46`, `test_61`). Un décor global qui
  authentifie tout le monde efface les cas qu'on voulait garder.
- Vérifié de bout en bout, vrai POST HTTP : `user` → **403 lecture_seule,
  rien en base** ; `coordinateur` → 201, tâche écrite.

⚠️⚠️ **Et la porte était plus STRICTE que la règle carto** — relevé sur le
pilote AVANT la livraison, pas après. Deux comptes ARaymond (un `champion`
qui POSSÈDE une cartographie, un `user`) y auraient perdu le droit d'écrire
les données de LEUR propre carto. Or `carto_access.can_edit` dit depuis
toujours que sur une carto PRIVÉE, son propriétaire fait ce qu'il veut quel
que soit son statut. Une porte qui contredit la règle qu'elle fait respecter
est un deuxième avis, pas une porte : elle consulte donc `can_edit` sur la
carto ACTIVE, et ne retombe sur le droit de statut que lorsqu'il n'y a pas de
carto active. Sur une carto COMMUNE, en revanche, c'est bien le tableau des
droits qui tranche — elle engage toute l'organisation.

⚠️ Ce défaut ne pouvait PAS se voir dans la suite : le compte de test est
`admin`, donc toutes les portes lui sont ouvertes. Il s'est vu en LISANT la
base du client avant de pousser (`tools/db/etat_statuts.py`, lecture seule).
L'inventaire avant livraison n'est pas une formalité.

Tests : `tests/test_102_porte_ecriture.py` (37 cas).

#### Page Temps — trois défauts, trois causes distinctes

- ⚠️ **« Durée (h) » était en MINUTES** (R04/H13/F36). `addRoleRow` lit le
  champ tel quel (`durMin`) : saisir 60 posait une heure. Le calcul, lui, est
  cohérent — c'est l'en-tête qui mentait, donc c'est lui qui change.
  ⚠️ **Sans renommer la clé partout** : `time.col_duration_h` sert à QUATRE
  tableaux et trois sont JUSTES (ils affichent `fmtH(duration_minutes)`, donc
  des heures). Seul le tableau de SAISIE du rôle reçoit sa propre clé,
  `time.col_duration_min`.
- ⚠️ **L'aperçu « Total estimé » ne se recalculait jamais** (R05/H14/T17). Il
  n'était écrit que dans `refreshActivityDefaults()` — sur le changement
  d'ACTIVITÉ — et après sauvegarde : **aucun écouteur** sur durée, fréquence
  ni nombre de personnes. 30 min × 2 × 3 affichait « 0.0 h » et enregistrait
  3,0 h. Le chiffre montré pendant la saisie ne décrivait rien.
- ⚠️ **La fréquence de la Faiblesse était LUE, STOCKÉE, et n'entrait dans
  AUCUN calcul** (R08/T19/F37). Reproduit avec les chiffres du rapport
  (hebdomadaire, 60 min, 1 chance sur 2, +30 min, +60 min d'attente) :
  fréquence 1 et fréquence 2 rendaient exactement 16 occurrences, 8 h et 24 h.
  `H` compte les PÉRIODES par an et `freq` le nombre de fois PAR période —
  c'est la lecture de l'onglet Rôle (`weight = durée × fréquence`) : le
  produit des deux est le nombre d'occurrences. `H = H * max(1, freq)`.
  ⚠️ **Cela déplace les résultats déjà enregistrés** d'un facteur `freq` — ce
  qui est le but, mais une analyse relue après coup ne donnera plus le même
  chiffre qu'avant.

Tests : `tests/test_103_temps_audit.py` (8 cas, la fréquence vérifiée
**rouge** en retirant la ligne). Suite : 2904 passés, `repet_image` 2876 + 28
sautés.

#### Deux points laissés en arbitrage, et pourquoi

- **Le mensuel de la Faiblesse divise par 7,36, pas par 12** (R07/H16).
  `W = U / (Sa / WPM)` : avec 32 semaines par an, cela fait 7,36 **mois
  travaillés**. Leur relevé (annuel 8 h → mensuel 1,1 h) tombe exactement
  juste. Ce n'est donc pas un défaut de calcul mais une **convention non
  écrite** : « moyenne par mois travaillé » et non « annuel ÷ 12 ». Rien n'a
  été changé — le choix se décide, il ne se devine pas.
- **Exigence atteinte ≠ autonomie démontrée** (A10/F42/C24). Attendu 1 +
  officiel 1 donnent « 100 % » ET « Below target ». Ce n'est pas une
  contradiction : ce sont deux règles, mélangées dans un seul compteur. La
  correction est d'**afficher les deux séparément**, pas de recalculer.


### La page Temps refondue : on arrive, on choisit, on saisit (2026-10-13)

« Vraiment pas au niveau vis-à-vis du reste de l'app, très très brouillon, on
ne comprend pas tout, on s'emmêle. » Mesuré avant de redessiner :

| Onglet | Hauteur | Champs | Chiffres à l'arrivée |
|---|---|---|---|
| Projet | 333 px | 7 | 4 (tous à 0,0 h) |
| Activité | 406 px | 6 | **0** |
| Rôle | 611 px | **26** | 6 |
| Faiblesse | 631 px | **15** | **0** avant de calculer |

Quatre causes, chacune traitée :
1. **Quatre onglets = quatre modèles mentaux** sans rien qui les relie, et un
   vocabulaire différent dans chacun pour la même notion (« Nb », « Fréq. »,
   « Quantité », « Nombre d'exécutions par période »).
2. **Six chiffres dans l'onglet Rôle** — Somme Jour/Hebdo/Mensuelle/Annuelle,
   puis Estimation Mensuelle/Annuelle — et la différence entre « Somme » et
   « Estimation » n'était écrite **nulle part**.
3. **Tout à 0,0 h en arrivant** : un formulaire vierge qui ressemble à un
   résultat vide, et rien qui dise ce qui avait déjà été mesuré.
4. **Les analyses enregistrées en bas de CHAQUE onglet** : le travail déjà
   fait ne se voyait qu'en entrant dans la saisie. 1180 px utilisés sur 1920.

**La méthode d'abord.** Trois restructurations dessinées À L'ÉCHELLE dans un
canvas (« Page Temps — 3 restructurations ») avant la moindre ligne de code —
la même méthode que pour la page Carte, et pour la même raison : une passe de
style coûte une demi-journée et se juge en trois secondes. L'arbitrage n'était
pas « laquelle » mais **« jusqu'où »** : les trois pièces (le tableau de bord
d'arrivée, les quatre portes, le panneau de résultat permanent) sont
complémentaires, mais les trois PAGES ne le sont pas — 2 et 3 proposaient
toutes deux l'écran d'accueil. Retenu : les trois enchaînées.

**Trois écrans** (`.tm-ecran`, `is-actif`), plus un seul onglet :
- **`#tm-accueil`** — un chiffre de tête (charge annuelle + équivalent temps
  plein), le coût des faiblesses, **ce qui n'est pas chiffré**, deux lectures
  (par rôle avec le repère du temps plein, par activité), et les analyses
  enregistrées réunies en un seul endroit.
- **`#tm-choix`** — « De quoi voulez-vous estimer la charge ? », quatre portes
  qui disent **quand** s'en servir, avec un exemple.
- **`#tm-travail`** — une analyse à l'écran, et son **résultat collé à droite**
  (`position: sticky`) qui vit pendant la frappe.

⚠️ **Ce qui rend la refonte sûre : les IDs des compteurs n'ont pas bougé.**
`updateKpi` écrit par ID — déplacer un compteur du bas du formulaire vers le
panneau de droite ne casse rien TANT QUE l'id survit. Les quatre panneaux de
saisie, eux, sont repris tels quels. `test_105` garde la liste des seize ids.

**`GET /temps/api/tableau_de_bord`** — tout ce que l'accueil montre, en UNE
requête (calendrier, charge, faiblesses, couverture, par rôle, par activité,
projets). Quatre appels auraient donné quatre instants différents.

⚠️⚠️ **L'ATTENTE N'EST PAS DU TRAVAIL — le défaut que seul le banc a montré.**
La carte des faiblesses additionnait le travail refait (U) et l'attente (V),
puis comparait le total à la charge de TRAVAIL. Relevé au banc : **61 h de
travail refait contre 984 h d'attente**, et l'écran annonçait « 84 % de la
charge » pour **5 %** réels. Une activité qui attend deux jours la réponse
d'un fournisseur ne coûte deux jours de travail à personne. Les deux natures
sont désormais rendues séparément (`travail_min` / `attente_min`), la part ne
compte que le travail, et le classement des faiblesses suit le travail refait
— sinon celle qui ne coûte rien mais fait attendre trois jours arrive en tête.

⚠️ **Le mode « par tâches » écrit une ligne PAR TÂCHE plus une ligne de total**
(`task_id` nul) : le tableau de bord ne compte que les lignes de total, sinon
chaque faiblesse détaillée coûterait le double. Et `DELETE /api/weakness/<id>`
— qui n'existait pas, une faiblesse enregistrée pesait à jamais — emporte les
lignes de tâche de son total.

**Une seule règle d'annualisation** : `annuel_minutes()` (serveur) et
`annuelMinutes()` (navigateur). Elle était écrite dans `_role_summary` ET dans
`recalcRoleTotals` ; le tableau de bord en aurait fait une troisième.
`_role_summary` l'appelle désormais, et `test_105` confronte les deux
implémentations — la Python sur ses chiffres, la JS sur ses quatre facteurs.
⚠️ Elle compte en calendrier CIVIL (mensuel = 12). Ce n'est **pas** la base de
l'onglet Faiblesse, qui compte en périodes TRAVAILLÉES (`cout_faiblesse`,
mensuel = 47 ÷ 4,34524). Les deux coexistent depuis toujours et n'ont pas été
unifiées : changer l'une déplacerait des analyses déjà enregistrées.

**La faiblesse se calcule PENDANT la saisie** — le bouton « Calculer » a
disparu. ⚠️ Mais la formule reste celle du SERVEUR, appelée en différé
(420 ms) : la réécrire dans le navigateur en ferait une seconde, et deux
implémentations d'un même verdict finissent par diverger. C'est le choix
inverse de celui des curseurs du plan de formation, et pour une raison
mesurable : là-bas le verdict est une division, ici ce sont treize variables.

⚠️ **Le corps de cette page porte `zoom: .8`.** Le conteneur passé à 1440 px
n'occupait que **72 %** d'une fenêtre de 1600 — à peine mieux qu'avant la
refonte. Et les requêtes de media, elles, IGNORENT ce zoom : le seuil de
1180 px se déclenchait alors qu'il restait 1475 px de mise en page. Corrigé :
conteneur 1680 px (**84 %** à 1600, 70 % à 1920), seuil à 1000 px réels. Même
piège que pour la page Compétences, écrit noir sur blanc plus haut.

⚠️⚠️ **`delete(synchronize_session=False)` laisse des objets MORTS dans la
session** — et le symptôme ne désigne pas le coupable. Ma route de suppression
l'employait : trois tests plus loin, `POST /api/weakness` tombait en 500 sur
son `commit()` avec « 'NoneType' object has no attribute '__dict__' ».
SQLAlchemy retrouve au flush un objet expiré dont la ligne n'existe plus,
tente de la relire pour calculer sa clé d'identité, et n'obtient rien. **En
production le défaut ne se voit pas** (la session est déposée à la fin de
chaque requête) ; dans la suite elle est PARTAGÉE du début à la fin. On
supprime objet par objet.

⚠️ **Deux tests relisaient `Code/routes/time_view.py`** : verts en local,
rouges à chaque exécution dans l'arbre d'image (bytecode-only). Réécrits sur
le COMPORTEMENT — l'ordre rendu plutôt que la ligne de tri, les chiffres de
`_role_summary` plutôt que le texte de sa source. C'est mieux que de les faire
sauter : le contrôle y gagne.

**Trois défauts corrigés au passage**, tous visibles seulement à l'écran :
- `refreshWeaknessDefaults` était le **quatrième** site de pré-remplissage,
  oublié par le correctif des trois autres : taper une durée puis choisir
  l'activité la remettait à la valeur de la fiche. Ses neuf `console.log` de
  mise au point sont partis avec.
- La ligne d'une analyse de rôle, sur l'accueil, affichait « J:0.0h · H:1.13h ·
  M:0.4h · A:0.0h · Mensuel:19.4h · Annuel:223.9h » — six chiffres bruts,
  exactement le défaut que la refonte corrige dans l'écran de saisie.
- Le sous-titre du bandeau (« Estimez et suivez les charges : projets,
  activités, rôles et impact des faiblesses ») décrivait ce que l'écran
  montre, juste au-dessus de la question qu'il pose.

Banc : **`tools/devrun_temps.py`** (port 8127, `/devrun/fr` et `/devrun/en`) —
douze activités dont **six seulement chiffrées**, deux rôles (l'un au-dessus
du temps plein, l'autre bien en dessous), trois faiblesses de coûts très
inégaux, deux projets, et un calendrier de travail réglé. Sans les activités
non chiffrées on ne voit jamais que le cas heureux, où le total annoncé porte
sur toute la carto.

Tests : `tests/test_105_temps_refonte.py` (25 cas ; **six défauts remis un par
un, six cliquets tombés** — l'attente recomptée, le double comptage des
tâches, l'ETP rendu à zéro, la règle d'annualisation réécrite, les onglets
remis, le bouton « Calculer »). Suite : 2993 passés, `repet_image` 2965 + 28
sautés. Éprouvé au banc de 1280 à 1920 dans les deux langues : parcours
complet, résultat en direct, zéro fuite française sur l'écran anglais, aucun
débordement horizontal.


#### L'accueil ouvre les quatre analyses, et dit ce qui manque (2026-10-13)

Deux retours, deux défauts de la même nature — un écran qui compte sans dire
quoi faire du compte.

**« On pourrait retrouver nos 4 types via la page d'accueil, et pas
obligatoirement en passant par la création d'une analyse. »** La seule porte
était « + Nouvelle analyse » — un bouton qui annonce une CRÉATION, alors qu'on
vient souvent relire. Un **rail de quatre tuiles** en tête de « Vos analyses »
ouvre chaque type directement, et porte le nombre de ce qui y est enregistré.
⚠️ Les écouteurs visent `.tm-porte, .tm-rail-t`, **pas `[data-analyse]`** :
`#tm-travail` porte cet attribut (c'est lui qui teinte l'icône de la barre),
on lui poserait un écouteur qui le rouvrirait sur lui-même.

**« Je n'ai ni compris ce que c'était, ni ce qu'il fallait y faire une fois
cliqué sur Chiffrer les suivantes. »** La carte annonçait « 12 activités sur
12 » et « Le total ci-contre ne porte que sur **0 activités** » — un compte
sans objet, un pluriel sur zéro, et une phrase qui désigne la carte voisine
par sa POSITION, fausse dès que l'écran se replie en colonne (sous 1000 px).
Puis le bouton ouvrait un formulaire générique dont la liste déroulante
portait TOUTES les activités : rien ne disait lesquelles manquaient.

Elle **nomme** désormais ce qui manque (`couverture.a_chiffrer`, plafonné à
60 — une carto de six cents activités n'a pas à les envoyer toutes pour
remplir une carte qui en montre trois) ; chaque nom ouvre SON activité, déjà
choisie ; et le bouton dit laquelle : « Chiffrer « Archiver le dossier » ».
⚠️ Ouvrir une activité depuis cette carte **remet le champ durée à l'état non
saisi** (`delete dataset.saisi`) : `intact()` refuse sinon d'y poser la durée
de la fiche, et on arriverait sur un zéro.
⚠️ Trois phrases, pas une : tout chiffré / rien chiffré / partiellement. La
version « ne porte que sur {n} » ne veut rien dire quand n vaut zéro.

**`tools/db/seed_temps.py`** — remplir la page Temps d'une carto existante
avec des données plausibles, bâties sur SES activités et SES rôles (jamais
d'activités inventées). `--dry-run` par défaut, `--yes` pour écrire, `--purge`
pour repartir à zéro. ⚠️ L'URL se passe en argument, **jamais dans un
fichier**. ⚠️ Et **trois activités sur cinq seulement sont chiffrées** : si
tout l'est, la carte « ce qui n'est pas chiffré » ne se voit jamais et on ne
sait pas qu'elle existe.

⚠️ **Un test supposait non chiffrée l'activité du décor commun** : vert seul,
rouge en suite complète (un autre fichier l'avait mesurée entre-temps). Il
crée la sienne — et la carto où la poser vient du tableau de bord lui-même,
pas de `Entity.get_active_id()`, qui lit la session Flask et n'a pas de
réponse hors requête.

Tests : `test_105` passe de 25 à 40 cas. Suite : 3008 passés, `repet_image`
2980 + 28 sautés.


#### Ouvrir une analyse pour la MODIFIER, et une liste qui tient (2026-10-14)

Trois retours, une fois la page remplie de vraies données.

**« On ne peut pas modifier une analyse, quel que soit son type. De plus on
peut supprimer une analyse mais pas, à l'intérieur, un élément : cela oblige,
si erreur, à supprimer et refaire au complet. »** Exact, et pour **trois des
quatre types** : seule l'analyse d'ACTIVITÉ avait un `PATCH`. Le projet ne
savait que se renommer, le rôle non plus, et la faiblesse ne se relisait même
pas — aucune route ne la rendait.

Ajouté : `PUT /api/project/<id>` (nom + lignes), `PATCH /api/role_analysis/<id>`
qui accepte désormais `lines`, `GET` et `PUT /api/weakness/<id>`. Tous
reprennent EXACTEMENT la forme de leur route de création — un écran qui
enregistre et un écran qui modifie ne doivent pas parler deux langages.
⚠️ `lines` ABSENT ne touche à rien : le renommage en place existait, il ne
doit pas se mettre à vider l'analyse.
⚠️ La faiblesse **garde son identifiant** : l'écran qui vient de l'ouvrir la
retrouve au même endroit, et la liste ne montre pas un doublon.
⚠️ Le calcul EN DIRECT de la faiblesse interroge la route de CRÉATION sans
enregistrer ; seul « Enregistrer » met à jour. Sans cette distinction, taper
une valeur écraserait l'analyse ouverte à chaque frappe.

Côté écran : **cliquer une ligne ouvre l'analyse dans l'écran de saisie**, où
tout est modifiable par construction — y compris retirer une ligne, qui était
le reproche. Un repère « Modification · <nom> ✕ » dans la barre dit ce que va
faire « Enregistrer » ; sans lui on ne sait pas s'il crée une analyse de plus
ou remplace celle qu'on a ouverte.

⚠️⚠️ **Une ligne POSÉE n'est pas une ligne CALCULÉE.** Relevé au banc : un
projet enregistré à 10,5 h se rouvrait en affichant **« 0.0h »**. Les
activités et les durées étaient justes — mais le total lit
`.cell-chg[data-minutes]`, que SEUL `recalc()` renseigne, et il n'était appelé
que par le pré-remplissage. Le même piège dormait côté rôle :
`loadRoleActivities` passe toujours une durée NULLE, donc le pré-remplissage
courait ; rouvrir une analyse enregistrée est le premier cas qui passe une
durée.

**« Avec des données, les listes deviennent vite très verbeuses. »** Mesuré :
dix-huit lignes empilées, chacune avec son accordéon, ses badges et sa ligne
de méta — **neuf cents pixels** de défilement pour retrouver une analyse.
Quatre sections **repliables, fermées au départ** (le compte dans l'en-tête
suffit à savoir s'il y a quelque chose à ouvrir ; les dix-huit lignes, non),
et des lignes d'une seule ligne : nom, deux pastilles, le chiffre. Mesuré
après : **255 px**. L'état des sections vit dans `localStorage`, chaque accès
en try/catch.

**Trois rendus de liste disparaissent** (`refreshProjectList`,
`refreshActivityWorkloadList`, `refreshRoleAnalyses` — environ trois cents
lignes, leurs accordéons, leurs renommages en place et leurs suppressions
ligne à ligne) au profit d'UN rendu nourri par le tableau de bord. C'est ce
qui rend la modification possible : la liste n'est plus une vue de détail,
c'est une porte.

**Les deux boutons de l'en-tête** reprennent le vocabulaire décidé sur
maquettes pour la page Carte : rapport INVERSÉ entre les deux. L'action
principale (« Nouvelle analyse ») pose une pastille PASTEL sur un fond vif et
un éclat la traverse au survol ; le réglage (« Calendrier de travail ») pose
une pastille VIVE sur un fond clair. Deux formes qui se distinguent sans se
disputer le regard.

⚠️ **Deux info-bulles écrites en dur, en français, dans le JS** (`title=
"Supprimer"` des lignes de saisie) : elles s'affichaient telles quelles sur
l'écran anglais. `test_78` ne les voit pas — il ne lit que les gabarits.

⚠️ **Un nettoyage d'injection a failli couper six clés vivantes.** En retirant
les 29 clés `TIME_I18N` devenues mortes avec les anciennes listes, le script
cherchait `fmtPhrase('cle', …)` — or six sont choisies par un TERNAIRE
(`fmtPhrase(n > 1 ? 'tm_etp_pl' : 'tm_etp', …)`). Elles auraient disparu, et
l'écran aurait affiché la CLÉ BRUTE : l'accesseur rend la clé quand elle
manque, il ne lève rien. Vérifiées une par une dans le JS avant d'être
remises, et le gabarit porte la mise en garde.

⚠️ **`test_103::test_les_tableaux_de_LECTURE_gardent_les_heures` visait du
code supprimé** (les tableaux des accordéons). Réécrit sur ce qui reste vrai
et utile : `recalc()` du rôle lit son champ TEL QUEL, sans conversion — c'est
ce qui rend l'en-tête « Durée (min) » juste.

⚠️ **Au passage, `test_107` (arrivé de staging) relisait une SOURCE Python**
via `runpy.run_path` : ses trois cas rougissaient à CHAQUE exécution sur
l'instance, l'arbre d'image étant compilé en bytecode. Garde de saut posée,
comme pour la fixture `pulse_app`.

Tests : `test_105` passe de 40 à 57 cas ; **sept défauts remis un par un,
sept cliquets tombés**. Suite : 3029 passés, `repet_image` 2997 + 32 sautés.
Éprouvé au banc dans les deux langues : les quatre types ouverts, modifiés,
enregistrés et relus EN BASE (projet 10,5 → 19,0 h sans doublon ; rôle 223,8 →
216,8 h après retrait d'une ligne ; activité fréquence 1 → 5 sur 6 analyses
toujours ; faiblesse 50,6 → 101,3 h sur 3 faiblesses toujours).

---

### Les PALIERS DE PERFORMANCE à l'écran (2026-10-14)

Le moteur était écrit et testé (`Code/paliers.py`, 10 routes, `test_108` — le
parcours de Bob aux chiffres exacts : 96 h → 72 h → 48 h, puis 24 h). Il ne se
voyait nulle part. Les quatre écrans ont été **tranchés sur maquettes avant
d'écrire une ligne de code** (canvas « Compétences — paliers de performance ») :
c'est la méthode retenue pour tout ce qui se juge en trois secondes, et qui
coûte une demi-journée à écrire.

**La règle, inchangée** : la norme atteinte = niveau 2 (qualifié), dépassée
d'un palier = niveau 3 (avancé), le niveau 4 n'est **jamais déduit**. Une
sortie sans norme chiffrée garde sa note 0→4 posée à la main.

#### Ce que l'écran montre

- **L'échelle des paliers** (`carteMesuree`, `railHtml`) remplace l'échelle
  0→4 **pour les sorties mesurées seulement** : `96 ● ─── 72 ● ─── 48 ◉ NORME
  ┄┄ 24 ○`. Chaque marche porte sa cible, son verdict et ce qui a été mesuré ;
  la norme est marquée d'un drapeau noir ; l'échéance du palier en cours est
  une pastille ambre, rouge dès qu'elle est dépassée.
  ⚠️ **Le dispatch se fait sur la NORME, pas sur la nature de la sortie**
  (`carteSortie`) : c'est le seul critère, et les deux régimes cohabitent dans
  la même fenêtre — c'est ce qui rend la règle lisible.
- **Le calendrier** (`cv2-cal-win`, bouton du fil d'Ariane du rôle) : les
  compteurs, le mois, et la session choisie à droite — où l'on relève les
  chiffres et où les verdicts tombent.
- **L'évolution** (`showEvolution`, sous-vue de la fenêtre d'évaluation) : le
  graphe d'une sortie **dans son unité**, les zones « qualifié » et « avancé »,
  et l'historique complet (palier posé → session tenue → mesure → verdict).
- **Un palier manqué ouvre l'analyse des savoirs** (`apresEchec`), jamais
  « reposez la même cible » : reposer la marche sans rien changer, c'est
  attendre le même résultat (CDC 6.8).

#### Les décisions qui ont coûté quelque chose

- ⚠️ **Le graphe garde l'unité réelle**, pas un score normalisé : une durée
  descend vers la norme, un taux y monte. Conséquence assumée — deux sorties
  se lisent dans des sens opposés, et chaque carte le dit (`ev_descend` /
  `ev_monte`). Un score normalisé lirait pareil des deux côtés, mais on ne
  lirait plus « 70 h » — or c'est ce chiffre qu'on vient voir.
- ⚠️ **« Enregistrer » disparaît quand toutes les sorties sont mesurées.** Le
  niveau vient du chiffre relevé en session : un bouton d'enregistrement
  n'écrirait rien et laisserait croire qu'on a oublié une note.
- ⚠️ **Le pas « au-delà » peut tomber HORS de la grandeur** — une norme de 2 j
  avec un pas de 4 donne « −2 j », un taux de 100 % donne « 120 % ». Relevé au
  banc sur les deux cas. `plausible()` ne le dessine pas alors, et **n'invente
  pas un autre seuil** pour le remplacer : la marge est celle que le
  développeur a posée, ou il n'y en a pas. C'est un garde-fou d'AFFICHAGE — le
  niveau reste celui du serveur.
- ⚠️ **La marche « au-delà » se REMPLIT quand la mesure la dépasse.** Elle
  restait creuse alors que la pastille annonçait « Qualifié · avancé » : la
  carte disait une chose, son échelle en disait une autre juste en dessous.
- ⚠️ **Le calendrier ne se cadre PAS sur un collaborateur** : celui qui tient
  les rendez-vous les tient pour tout le monde. Cadré sur une personne, une
  session ne se voit qu'en ayant d'abord choisi la bonne — c'est exactement ce
  qui faisait manquer les propositions de carto dans la page RH. Il est
  **large, pas ouvert** : un développeur voit les rendez-vous de SES
  collaborateurs (lien global ou lien par rôle), un coordinateur voit tout.
- ⚠️ **Il s'ouvre sur une session**, la plus urgente d'abord. Sans cela la
  moitié droite de la fenêtre s'ouvre vide — elle occupe la place de ce qu'on
  vient faire sans rien en dire.
- ⚠️ **`_sessions_lisibles` charge en DEUX requêtes** ce que l'acteur encadre,
  puis filtre en mémoire : `peut_lire` dans une boucle relit l'utilisateur et
  compte ses rattachements à chaque appel — cinquante sessions feraient cent
  requêtes pour une page qui s'ouvre à chaque visite.
- ⚠️ **Une session se clôt en UNE transaction** (`POST /paliers/session/<id>/
  cloturer`) : en trois appels, un refus au milieu laisserait une session
  « prévue » dont la moitié des paliers sont tranchés, et plus personne ne
  saurait ce qui reste à faire. Les identifiants venant du navigateur, on ne
  tranche QUE des paliers de cette session.
- ⚠️ **Les formulaires s'ouvrent DANS la carte**, jamais en fenêtre : une
  modale par-dessus une modale cache le chiffre qu'on vient lire pour décider.
  Et pas de `window.prompt` pour planifier une session — la fenêtre du
  navigateur arrive avec ses styles système et son texte en dur, c'est ce
  qu'on a retiré de la page Temps.
- ⚠️ **La fenêtre s'élargit à 1060 px pour le graphe, et pour lui seul.** Dans
  les 720 px de la fenêtre d'évaluation, un SVG de 820 px de viewBox est rendu
  à 0,82 — et `body.pg` porte en plus `zoom: .8`, donc un libellé écrit en
  11,5 px arrive à **7,6 px réels**, sous le plancher de l'échelle
  typographique. `data-vue` est remis à `eval` à chaque ouverture : sinon
  rouvrir après le graphe gardait une fiche deux fois trop large.
- **Les deux boutons** reprennent le vocabulaire tranché sur la page Temps :
  rapport INVERSÉ — l'action pose une pastille PASTEL sur un fond vif avec un
  éclat qui traverse au survol, le réglage une pastille VIVE sur un fond clair.
  Une sortie déjà qualifiée passe son bouton en discret : poser une marche de
  plus reste possible, ce n'est plus ce qu'on vient faire.
- ⚠️ **Aucune règle neuve ne lit `--pg-accent-soft`** ni ses trois frères :
  déclarés sur `:root`, où `--pg-accent` vaut encore le gris par défaut, ils
  rendent du GRIS sur toute l'application. Les mélanges sont écrits DANS la
  règle (`color-mix` sur place). Tenu par `test_109`.
- ⚠️ **Un verdict masqué par `.hidden` dans une classe qui pose un `display`** :
  quatrième fois que ce piège se présente. Ici il ne mordait pas (`.hidden`
  porte `!important`), mais la ligne n'est plus rendue du tout quand il n'y a
  rien à dire.

#### Le semis — `tools/db/seed_competences.sql`

À coller dans l'éditeur SQL de Neon, sur la **même carto** que
`seed_temps.sql` (le même `carto_id`). Trois requêtes : inventaire (lecture
seule), semis (un bloc atomique), relecture.

- Il **matérialise les sorties exactement comme l'application** (nom = libellé
  de la flèche, à défaut l'activité visée ; une flèche qui vise une donnée
  n'a rien à matérialiser) : un semis qui nommerait autrement ferait naître
  des doublons au premier passage de `materialize_activity_outputs`.
- ⚠️ **Il REFUSE de rejouer** sur une carto qui porte déjà des paliers.
  Mesuré : un second passage empilait 76 paliers là où il en faut 38 — six
  marches au lieu de trois, un historique qui ne veut plus rien dire. Et
  fusionner silencieusement serait pire : des paliers fictifs se mêleraient à
  de vraies évaluations. `purger := true` pour recommencer.
- ⚠️ **Il s'arrête si personne ne tient de rôle** sur la carto : sans
  titulaire il n'y a personne à évaluer, et on ne fabrique pas de
  collaborateurs pour remplir un écran.
- ⚠️ **Deux activités sur cinq restent SANS norme**, volontairement — même
  principe que `seed_temps.sql` : une carto où tout est mesuré ne montre
  jamais la moitié de l'écran.
- ⚠️ **Les quatre parcours tournent sur un compteur de PAIRES** (personne ×
  sortie), pas sur la somme des deux rangs : avec deux personnes et deux
  sorties, cette somme ne prend que trois valeurs sur quatre — et c'est
  « qualifié · avancé », la fin heureuse de l'histoire, qui n'apparaissait
  jamais. Relevé à l'essai, pas deviné.
- ⚠️ La requête de relecture rend la **dernière** mesure, pas la plus grande :
  sur une durée, la plus grande est la PIRE — on lirait l'inverse de la
  progression.
- **Éprouvé sur un vrai PostgreSQL 16** (conteneur jetable), schéma monté par
  le démarrage NORMAL de l'application : un SQL que SQLite accepte et que
  PostgreSQL refuse ne se verrait qu'une fois sous les yeux du client.
  Mesuré : 38 paliers, 0 sur la carto voisine, 2 sorties laissées à la main,
  et les quatre états présents.

Tests : `tests/test_109_paliers_ecran.py` (24 cas ; **cinq défauts remis un
par un, cinq cliquets tombés** — le garde-fou de l'au-delà, le calendrier
cadré sur tout le monde, la clôture acceptant n'importe quel palier, les
parcours du semis, la note redemandée sur une sortie mesurée). Suite : 3078
passés, `repet_image` 3043 + 36 sautés. Banc : `tools/devrun_competences.py`
sème les paliers — en cours, en retard, qualifié-et-au-delà, manqué, et trois
sorties laissées sans norme. Éprouvé dans les deux langues (détecteur de
fuites : zéro phrase française sur l'écran anglais).

#### Évaluer n'est plus un TIROIR, c'est une page (2026-10-14)

« On ne peut pas faire cela dans cette petite pop-up, il faut le faire sur la
page directement. On a prévu des graphiques, de belles choses, et là tout est
en petit compressé. » Le reproche était exact, et sa cause est une erreur
d'implantation, pas de maquette : **les quatre maquettes validées étaient des
pages de 1440 × 1240** ; je les ai implantées dans le tiroir existant, qui fait
**720 px CSS — soit 576 px RÉELS** (`body.pg` porte `zoom: .8`). J'y avais
comprimé une échelle de paliers, un graphe et un historique.

**La page a été tranchée sur maquettes** — trois organisations à l'échelle
(canvas « Compétences — la page d'évaluation ») : le pupitre (trois colonnes),
le dossier (onglets + pleine largeur), la séance (une chose à la fois). Retenu :
**le pupitre**, plus **la séance** comme écran séparé, ouvert par le calendrier.

**Deux écrans nouveaux**, `#cv2-ecran-eval` et `#cv2-ecran-seance`, posés HORS
de `.cv2-layout` : dedans, ils partageraient la largeur avec la barre des
collaborateurs. `pleineLargeur()` efface cette barre ET le bandeau de page
(qui redirait le nom écrit en grand dans l'en-tête), et `body.a-cv2-page`
desserre `.pg-container` de 1200 à 1760 px — 960 réels, c'était trop étroit
pour trois colonnes. Mesuré à 1280 px d'écran : **240 / 983 / 282**, aucun
défilement horizontal.

- **Colonne 1, les activités du rôle.** On passe de l'une à l'autre sans
  revenir en arrière : évaluer six activités ne fait plus six allers-retours.
  Chacune porte sa jauge fine et son niveau.
- **Colonne 2, la sortie.** Le rail est le héros de la page : pastilles de
  30 px avec leur ombre portée, chiffres en Fraunces 27 px, drapeau de norme
  en noir. Le graphe se **déplie dans la carte** (`basculerGraphe`) — le rail
  reste sous les yeux pendant qu'on le lit.
- **Colonne 3, le contexte** : le niveau de l'activité en 36 px, la prochaine
  échéance, la cible du rôle, la technicité en bleu plein, la légende.

⚠️ **L'état ET l'historique partent ENSEMBLE** (`Promise.all`) : le graphe se
déplie dans sa carte, il ne doit pas attendre un aller-retour de plus au clic.

⚠️ **Le tiroir reste, pour les deux DIALOGUES courts** — configurer une
activité, diagnostiquer un écart. C'est une division nette : la page sert à
regarder et à mesurer, le tiroir à régler. `showEvaluation`, `renderResults` et
`blocTechnicite` sont supprimés ; `ouvrirDialogue()` remplace `openDrawer()`,
et le retour du diagnostic **referme** la fenêtre au lieu de rebâtir une
évaluation qui vit désormais derrière.

**La séance** (`#cv2-ecran-seance`, ouverte par « Tenir la séance » dans le
calendrier) : une chose à faire à la fois. Le rail situe ce qu'on mesure, le
champ **« Qu'a-t-on mesuré ? »** fait 36 px en Fraunces — c'est pour ça qu'on
est là — et le verdict tombe en direct.

- ⚠️ **UN seul endroit pose une mesure.** Le panneau du calendrier est passé
  en LECTURE : deux écrans de saisie finiraient par ne plus dire la même chose
  du même geste. `cloturer(sid, z)` a disparu avec lui.
- ⚠️ **Le verdict affiché est UNE comparaison**, pour montrer d'avance ce que
  le serveur dira. C'est `trancher()` qui l'écrit, à la clôture — on ne
  reconstruit pas la règle côté navigateur.
- ⚠️ **La saisie met à jour SUR PLACE** (`lire()` : le verdict, la file, la
  liste, le compteur) : réécrire la page à chaque touche ferait perdre le
  curseur du champ qu'on tape. Le piège déjà rencontré sur les cartes du plan
  de formation, et sur l'autre sens de l'import.
- ⚠️ `/paliers/session/<id>/detail` porte désormais la **progression entière**
  de chaque sortie (`etat_sortie`), pas seulement le palier du jour : sans
  elle, la moitié gauche de l'écran restait vide et on posait un chiffre sans
  savoir d'où il venait ni s'il restait une marche après.
- La clôture revient sur le RÔLE : la séance est tenue, il n'y a plus rien à y
  faire, et les niveaux qu'elle vient de déplacer se lisent dans la liste.

⚠️ **« Jamais évaluée » à côté d'un niveau tout neuf.** `last_evaluation` ne
lisait que les `CompetencyEvaluation` — or une sortie MESURÉE n'en écrit
aucune : son niveau vient du palier tranché en séance. `dashboard_rows` prend
donc aussi la dernière date de palier, en **UNE** requête pour toutes les
activités du rôle (pas une par activité).

⚠️ **Les conventions de pluriel diffèrent dans ce catalogue** — `_1`/`_n` ici,
`_pl` là, la forme nue ailleurs. `nf()` essaie dans l'ordre celle qui EXISTE :
une clé absente ne lève rien, elle s'affiche telle quelle — « ev_nb_act_n » a
été relevé à l'écran avant correction. Et « Les 1 mesures sont prêtes » a eu
son singulier : il ne se devine pas d'une forme plurielle.

**Le visuel est monté d'un cran**, parce que « le design visuel paraît un peu
simplet » : en-tête d'identité en nuit profonde (`#1b2a4a → #0b1120`) avec son
halo radial et son ombre portée, Fraunces sur tous les grands chiffres (nom,
titre d'activité, valeurs du rail, niveau, date de séance, champ de mesure),
cartes en couches avec une ombre colorée sur la sortie mesurée, et les deux
boutons au rapport inversé déjà tranché sur la page Temps. Un troisième
bouton apparaît — `.pal-b--verre`, pour le fond sombre uniquement.

Tests : `tests/test_109_paliers_ecran.py` passe de 24 à **37 cas** ; six
défauts remis un par un, six cliquets tombés (l'évaluation rendue au tiroir,
la page qui partage la largeur, le graphe qui attend un appel de plus, la
séance sans progression, la date qui ignore les paliers, le pluriel à une
seule convention). ⚠️ Le premier ne mordait PAS au premier essai : il
cherchait `ouvrirEvaluation(a);` n'importe où dans le fichier, et la colonne
de gauche de la page l'appelle aussi — il vise maintenant le corps de
`ligneActivite`. Suite : **3091 passés**, `repet_image` 3056 + 36 sautés.
Éprouvé au banc à 1280 et 1600 px, dans les deux langues : zéro fuite
française sur l'écran anglais, aucun débordement horizontal.

#### La page reprise sur huit points, et deux pièges pour la quatrième fois (2026-10-15)

Huit reproches sur la première implantation du pupitre, tous mesurés avant
d'être corrigés.

**« Quand on clique sur un rôle, cela doit nous amener DIRECTEMENT sur
l'évaluation. »** L'écran intermédiaire — la liste des activités du rôle — ne
décidait de rien : on y cliquait « Évaluer » sur une ligne, et c'est tout. La
colonne de gauche de la page fait exactement la même chose, sans aller-retour.
`ouvrirRole` ouvre donc l'activité la plus urgente (en écart, sinon à évaluer,
sinon la première). Partis avec l'écran : `#cv2-ecran-role`, `#cv2-fil-role`,
`#cv2-lignes`, `ligneActivite`, `metaActivite`, `celluleTech`, et les boutons
`#cv2-btn-cal` / `#cv2-btn-plan` qu'il portait.
⚠️ **Le bandeau de situation le suit** : il disait ce qui reste à faire, et il
FILTRE — il se pose donc en tête de la colonne des activités, le seul endroit
où le chiffre et la liste qu'il résume se regardent ensemble. ⚠️ La ligne
OUVERTE reste visible quel que soit le filtre : la page parlerait sinon d'une
activité absente de sa propre liste.

**« La page d'accueil est vraiment pas ouf, trop vide. »** Trois causes
distinctes, chacune corrigée :
- ⚠️ **Le radar ne traçait QUE les activités évaluées.** Un collaborateur qu'on
  vient d'affecter n'avait donc aucun profil — l'écran le plus vide est celui
  qu'on ouvre en premier. On trace le REQUIS de toutes celles qui en portent un
  (mesuré : **8 axes** là où il n'y en avait aucun), et le démontré se remplit
  par-dessus. ⚠️ La surface démontrée ne se FERME que si tout est mesuré :
  ailleurs ce sont des morceaux de polyligne (`.cv2-r-dem-part`) — fermer le
  polygone sur un sommet absent le ferait passer par zéro, c'est-à-dire par
  « non démontré », la distinction que tout le module tient. Un axe sans mesure
  n'a pas de point.
- **Les quatre compteurs s'affichent même à zéro** : « 0 en écart » est une
  information. Ils ne disparaissent que quand un filtre est actif — là, une
  tuile vide ne mène nulle part.
- **« Prochaines séances »** sur la vue d'ensemble (`#cv2-seances`) : les
  siennes, pas celles de tout le monde, et un accès au calendrier.

**« La page est vachement rétrécie, ça crée un décalage. »** Mesuré :
`.pg-container` plafonnait à 1200 px pour la vue d'ensemble et sautait à
1760 px dès qu'on ouvrait une activité — **deux pages d'un même écran**. Une
seule largeur désormais, et les blocs de l'accueil (profil, rôles, bilan) la
suivent au lieu de garder leur ancien plafond.

⚠️⚠️ **L'en-tête de la page passait PAR-DESSUS la barre de navigation.**
`competences.css` déclare `header { position: sticky; top: 0; z-index: 30 }`
pour TOUTE la feuille — et mes en-têtes de page SONT des `<header>` : même
z-index que la nav, et comme ils viennent après dans le document, ils
gagnaient au défilement. En mise en page il n'y avait pourtant aucun
chevauchement (nav à 78,1 px, en-tête à 81,3 px) : c'est ce qui rend le
symptôme trompeur. `.ev-tete, .sq-tete { position: relative; top: auto;
z-index: 1; }`. **Quatrième fois que cette règle globale mord.**

**« Trancher ce palier » devient « Évaluer ce palier »** — le mot de métier ne
dit pas au lecteur ce que fait le bouton. Un cliquet interdit désormais tout
libellé visible qui le redirait. ⚠️ Il cherche le MOT ENTIER : « un palier
franchi » contient « ranch ».

**Deux pavés d'explication passent derrière un « i ».** La règle du minimum
(« le minimum de ses sorties, jamais la moyenne ») et l'échelle 0→4 occupaient
la place de ce qu'on vient lire. ⚠️ Et le 4 a été RÉÉCRIT : « jamais déduite,
elle se pose » ne voulait rien dire — c'est « Expertise — aucun chiffre ne la
définit : elle se pose à la main. »
⚠️ **La bulle se posait 20 % trop haut et trop à gauche de son bouton** :
`body.pg` porte `zoom: .8`, donc un enfant du body en `position: fixed` voit
ses coordonnées MULTIPLIÉES par ce zoom, alors que `getBoundingClientRect()`
les rend déjà en pixels d'écran. On divise par le zoom avant d'écrire
`left`/`top`, et on multiplie la taille de la carte pour la comparer à
`window.innerWidth`. Mesuré après : **0 px d'écart**. **Quatrième fois que ce
piège mord dans cette application** — tout élément posé sur le body en `fixed`
doit faire cette conversion.

**Le calendrier devient une PAGE** (`#cv2-ecran-cal`). Enfermé dans une
pop-up, il avait 1180 px — 944 réels au zoom .8 — pour un mois ET la séance
choisie. C'est une vue, pas un dialogue. Il sait d'où l'on vient (`cal.retour`)
et garde sa porte unique vers la séance : `data-tenir`, rien qui saisisse.

**Les quatre sections de contexte étaient dépareillées** — une bleu plein, une
marron, une blanche fade. Même silhouette, même en-tête, et des fonds PASTEL
tirés de la couleur que chacune porte déjà : le niveau en bleu très pâle (la
couleur de la page), la prochaine séance en ambre, la technicité en teal — un
AUTRE axe, donc une autre teinte, mais de la même famille claire. Les tuiles
du calendrier et le filtre des activités reprennent la même palette.

Tests : `tests/test_109_paliers_ecran.py` passe de 37 à **50 cas** ; **dix
défauts remis un par un, dix cliquets tombés** (l'écran intermédiaire, le
calendrier en fenêtre, le radar refiltré, la règle du minimum en clair, la
bulle sans le zoom, l'en-tête sous le sticky global, les deux largeurs, les
compteurs à zéro effacés, le bouton qui redit « trancher », les écrans morts
revenus au gabarit). Suite : **3147 passés**, `repet_image` 3112 + 36 sautés
(les 4 cas du semis SQL sautent : `tools/` est retiré de l'arbre d'image).
Éprouvé au banc à 1600 px dans les deux langues : accueil, rôle → page,
calendrier, séance et retour ; zéro fuite française sur l'écran anglais.

⚠️ **Et `test_110::test_sans_connexion_401`, arrivé de la routine de tests,
ne pouvait passer que s'il tournait EN PREMIER.** La fixture `client` est en
portée SESSION : c'est le MÊME objet que `auth_client`, et il arrive connecté
dès qu'un fichier précédent s'est authentifié — `test_109` le fait. Un test
de l'ANONYMAT fabrique donc son propre client (`app.test_client()`), comme le
font déjà la centaine de cas qui s'isolent de cette session partagée.

#### Les notes ne s'enregistraient PAS, et six autres points (2026-10-15)

⚠️⚠️ **« Ça dit que c'est enregistré, mais en rechargeant, les notes ne sont
pas là. »** Exact, et le plus grave de la passe. `saveEvaluation` cherchait ses
cartes dans **`#cv2-drawer-body`** — le TIROIR, d'où l'évaluation est partie la
veille. Mesuré au banc : **2 cartes dans `#ev-centre`, 0 dans le tiroir**. La
boucle ne tournait donc pas une seule fois, aucune requête ne partait, et le
`toast(T('saved'))` tombait **après** la boucle, inconditionnellement. On
notait, on validait, on était rassuré, et rien n'était écrit.
- Deux corrections, pas une : il lit `#ev-centre`, **et** il n'annonce plus un
  succès sans avoir rien écrit (`ecrites`). Un enregistrement silencieux qui se
  félicite est pire qu'une erreur — il n'y a aucun moment où l'on peut
  s'apercevoir de la perte.
- Vérifié de bout en bout, vrai rechargement de page : note 1 et preuve
  `CTRL-…` relues en base après F5.

**Le calendrier : les quatre tuiles FILTRENT, et une case pose la date.**
- Chaque tuile est un bouton (`data-f`, `aria-pressed`) ; recliquer celle qui
  est allumée l'éteint — sans quoi on ne revient jamais à « tout ». Le mois se
  cale sur la première séance retenue : filtrer sur un mois qui n'en porte
  aucune ne montrerait rien.
- ⚠️ **L'appartenance à une tuile vient du SERVEUR** (`j["tuiles"]`), calculée
  dans la boucle même qui incrémente les compteurs. Refaire en JS les quatre
  prédicats (en retard, cette semaine, ce mois, tenues cette année) donnerait
  un second verdict, et le chiffre annoncé finirait par ne plus désigner les
  cases mises en avant. Le cliquet vérifie l'INVARIANT : le compteur d'une
  tuile est le nombre de séances qu'elle marque.
- ⚠️ **Le filtre met en avant, il ne masque pas** : une case qui disparaîtrait
  laisserait un trou dans le mois et on ne saurait plus quel jour on lit. Les
  séances hors filtre s'éteignent (`.est-eteint`), celles qui restent portent
  un anneau.
- **Un jour du calendrier renseigne la date du formulaire** (`poserJour`), et
  la case visée porte un anneau d'accent : c'est le seul lien entre la grille
  de gauche et le champ de droite. ⚠️ **Le formulaire ouvert l'emporte** — un
  clic sur un jour DÉJÀ occupé pose la date au lieu de charger sa séance,
  sinon on quitterait la planification en cours de route. ⚠️ Et le jour visé
  vit dans `cal`, pas seulement dans le champ : le mois se redessine à chaque
  clic.
- Une case libre n'est un bouton que pour qui peut vraiment planifier.

**Le niveau attendu QUITTE la page d'évaluation.** Trois objets dans un même
écran — l'activité choisie à gauche, ses sorties au milieu, la cible du RÔLE à
droite — et on ne savait plus lequel on notait. Il se règle désormais dans le
**détail d'un rôle, sur la vue d'ensemble** (`barresRole`), qui montrait déjà
une ligne par activité avec sa cible sur la piste : cinq pas en creux par
ligne. Une cible se dessine, elle ne se remplit pas.
- ⚠️ Le réglage recharge la synthèse ENTIÈRE : la couleur, le compteur « en
  écart » et le radar en dépendent, et les redresser à la main donnerait une
  seconde règle pour un seul verdict. ⚠️ `box` et `hote` sont alors DÉTACHÉS
  (`renderProfil` réécrit le bloc) — on rouvre les barres sur la zone neuve.
- `cibleRequise`, la clé `ev_attendu` et la phrase `ev_tech_d` (« Un axe à
  part : le contexte technique, pas la maîtrise ») sont supprimées.

**Les deux premières colonnes portent un NUMÉRO** et une phrase qui nomme ce
qu'elles montrent — ① les activités du rôle, ② ce que l'activité produit,
« les sorties de l'activité choisie à gauche ; c'est là-dessus qu'on note ».
⚠️ L'en-tête de la colonne 2 est reconstruit par `remplirCentre`, pas écrit
dans le gabarit de la page : cette fonction VIDE `#ev-centre`, elle l'aurait
effacé au premier remplissage.

**L'évolution se referme par le BAS** (`.pal-evo-fin`, chevron vers le haut) :
une fois le graphe et l'historique dépliés, le bouton qui a ouvert la section
se retrouve en plein milieu, et il faut le chercher. ⚠️ Il est posé en DERNIER
enfant de la carte, pas après l'historique : `.pal-form` vient ensuite, et une
marche posée pendant la lecture glisserait un formulaire sous lui.

⚠️ **« Pourquoi “Demande de tests qualité” est en écart alors que le seuil de
95 % est atteint ? » — ce n'est pas un défaut de calcul.** Vérifié des deux
côtés (`categorie()` en JS, `categorie_activite()` au serveur) : la **norme
atteinte vaut 2** (qualifié), un palier **au-delà** vaut 3 (avancé), et le rôle
exigeait 3. 97 % ≥ 95 % donne donc bien « Qualifié · 2 », et 2 < 3 donne « en
écart ». Ce qui manquait, c'est que l'écran montrait la cible du rôle à dix
centimètres de la note de la sortie sans jamais dire qu'elles ne mesurent pas
la même chose. Le déplacement ci-dessus est le correctif ; la règle, elle, est
juste. Pour aller à 3, il faut **poser la marche suivante** — le bouton est sur
la carte.

Tests : `tests/test_109_paliers_ecran.py` passe de 50 à **67 cas** ;
**quatorze défauts remis un par un, quatorze cliquets tombés**.
⚠️ Le cliquet des tuiles relisait d'abord `Code/routes/paliers_routes.py` : vert
en local, **rouge dans l'arbre d'image** (bytecode-only). Réécrit sur le
COMPORTEMENT — il appelle `/paliers/calendrier` et compare chaque compteur au
nombre de séances marquées — ce qui en fait un contrôle plus fort, pas un
contrôle sauté.
Suite : **3164 passés**, `repet_image` 3129 + 36 sautés. Éprouvé au banc à
1600 px dans les deux langues : enregistrement relu après rechargement, filtre
des quatre tuiles (compteur et cases accordés), clic d'un jour libre et d'un
jour occupé, annulation, réglage du niveau attendu depuis l'accueil (3 → 4 →
3, relu), fermeture de l'évolution par le bas ; zéro fuite française sur
l'écran anglais.

#### ⚠️⚠️ Dépasser la norme ne faisait PAS monter le niveau (2026-10-15)

« La norme de "Demande de tests qualité" est fixée à 95 %, pourtant une marche
à 98 % mesurée à 99 % nous laisse à 2. » Exact, et c'est le défaut le plus
lourd du module : **le niveau d'une activité est le MINIMUM de ses sorties, et
celui d'un rôle le minimum de ses activités** — l'erreur redescendait jusqu'au
verdict « apte / pas apte ».

**La cause.** `pas_de_progression` ne regardait que les marches **en deçà** de
la norme et en déduisait une marge. Reproduit au chiffre près :

```
cibles 67 → 81 → 95 (norme) → 98      marge déduite 14   au-delà = 109 %
mesure 99 %                            →  niveau 2
```

**109 %** : une valeur qui n'existe pas sur un pourcentage, donc un seuil que
personne ne franchira jamais. Pendant ce temps le développeur avait posé une
marche à **98 %**, exprès, au-dessus de l'attendu — et elle ne comptait pas.

⚠️ **Et « Enquête client » marchait par HASARD** : 20 → 14 → 10 (norme) → 6
donne une marge de 4, donc un au-delà à 6 — qui tombe pile sur la marche
posée. Le même code rendait le bon résultat d'un côté et le mauvais de
l'autre, ce qui est la pire façon d'avoir tort.

**La règle, écrite une fois** : `seuil_au_dela(cibles, norme, sens, marge)` —
**une marche posée au-delà de la norme EST le seuil**, et c'est la PREMIÈRE
(les suivantes vont plus loin, elles ne déplacent pas la frontière). À défaut,
on retombe sur le pas de progression : la règle d'avant reste la bonne quand
personne n'a rien posé plus loin. `niveau_depuis_mesure` accepte ce seuil
explicite, qui l'emporte sur celui qu'on déduit. Vérifié de bout en bout, vrai
POST HTTP : sortie 3 → activité 3 → `gap` 0 sur un rôle qui exigeait 3.

⚠️ **Le rail dessinait son propre seuil** (`n.valeur + perf.marge`) : il aurait
montré 109 % quand le niveau se jouait sur 98 %. `etat_sortie` renvoie
désormais `au_dela`, et l'écran s'en sert — une frontière, une source.

#### Le rail était une ligne BRISÉE, et la mesure illisible (2026-10-15)

- ⚠️ **« La courbe UI casse, ce n'est pas beau. »** Le drapeau de norme était
  un `inline-block` avec `margin-bottom: 5px`, et les marches sans drapeau
  portaient un bloc vide de 22 px : la marche **flaguée descendait de ~5 px**
  et le rail formait un décroché à chaque drapeau. Une bande `.pal-marque` de
  hauteur FIXE, drapeau ou pas. Mesuré après : **0 px** d'écart entre les
  centres des pastilles, à 1280 comme à 1600.
- ⚠️ **DEUX drapeaux « Norme de l'entreprise » sur le même rail.** `mieux()`
  répond « atteint » : toute marche **à partir de** la norme le portait. La
  norme est un passage, pas une zone — c'est la PREMIÈRE marche qui l'atteint.
  La marche au-delà porte sa propre marque (`pal_audela_tag`), verte.
- **La mesure se lit autant que la cible.** « mesuré 19 j » était en 12,5 px
  gris sous une cible en 19 px — or c'est le chiffre qu'on vient voir, celui
  qu'on a relevé en séance. Il prend une pastille à la couleur de son verdict,
  valeur en 15 px gras.
- **Le niveau déduit** — le niveau ACTUEL de la personne dans l'entreprise —
  passe de 13 px à une pastille à chiffre Fraunces 25 px.
- Le crayon de la norme devient **sphérique**, et la pastille de norme aussi.

#### La boucle était FERMÉE : une sortie ne pouvait pas recevoir sa norme

⚠️ « Je note une première fois, je valide, et rien ne se passe ; comment
j'ajoute des marches, comment je renseigne le niveau requis ? » Le reproche
visait un vrai trou de structure : `resultCard` (une sortie SANS norme) ne
proposait **nulle part** de poser le standard de l'entreprise. Née à la main,
une sortie restait à la main pour toujours — l'échelle des paliers était
inatteignable, et on notait donc avant d'avoir pu dire ce qui est attendu.

La carte porte désormais un bloc « Jugée à la main » qui dit pourquoi elle
n'a pas de rail, et **« Définir la norme de l'entreprise »** ouvre le même
formulaire que la carte mesurée (`formNorme`, route `/paliers/norme/<id>`
inchangée). Vérifié au banc : une sortie à la main reçoit 48 h « au plus » et
devient mesurée, avec son rail et « Poser la marche suivante ».

#### Ce qui se dit moins, et ce qui se dit mieux

- « On passe de l'une à l'autre sans quitter la page » : retiré, l'écran le
  fait de toute façon.
- « Les sorties de l'activité choisie à gauche » passe derrière le « i » du
  titre de colonne.
- ⚠️ **« Les verdicts se calculent, ils ne se cochent pas »** ne disait ni ce
  qu'est un verdict ni ce qu'on attend du lecteur. Derrière un « i », et
  réécrite sur le GESTE : « En séance, vous relevez le chiffre mesuré — rien
  d'autre. L'application le compare à la cible du palier et en tire le
  verdict… et c'est ce verdict qui fait monter le niveau. »
- **L'aide « cliquez un jour »** occupait toute la largeur du panneau pour
  huit mots, à côté d'un champ de date de 117 px. Les deux sont sur une seule
  ligne, l'aide à droite.
- **« + Ajouter une preuve »** était un lien souligné : c'est une pastille
  avec son trombone.
- **Les deux notes partagent un seul cadre** (`.cv2-notes`) au lieu de deux
  rectangles gris empilés : un liseré bleu pour ce qui fait foi, violet pour
  l'auto-évaluation, pastilles rondes, échelle plus grande, gomme à icône.

⚠️ **Et un faux pas à ne pas refaire** : le retrait de `.pal-drapeau-vide` a
d'abord été écrit en regex (`/\* .*?Un bloc vide.*?\*/\n\.pal-drapeau-vide…`
en `re.S`). Le `.*?` non gourmand part du **premier** `/*` du fichier :
**1 840 lignes de `competences.css` ont disparu d'un coup**, et le symptôme
était trompeur — `.pal-rail` rendait `display: block`, donc un rail vertical,
comme si c'était la nouvelle mise en page qui échouait. Restauré depuis git,
puis retrait par chaîne EXACTE. Une suppression se fait sur des bornes, pas
sur un motif ouvert.

Tests : `tests/test_109_paliers_ecran.py` passe de 67 à **84 cas** ; **treize
défauts remis un par un, treize cliquets tombés** (le seuil deviné, le pas qui
l'emporte sur la marche posée, le domino jusqu'au rôle, la bande devinée du
rail, le drapeau sur toute marche, le rail qui redéduit son seuil, la mesure
en ligne grise, la boucle refermée, la phrase de la colonne 1, le verdict
réaffirmé, l'aide pleine largeur, les notes réempilées, la preuve soulignée).
⚠️ Trois cliquets ne mordaient PAS au premier essai, et c'était l'injection
qui visait à côté — dont un vrai défaut de contrôle : `data-poser-norme`
existe aussi dans le SÉLECTEUR de la liaison, donc retirer le bouton laissait
le test vert. Il cherche `data-poser-norme>`, la balise.
Suite : **3181 passés**, `repet_image` 3146 + 36 sautés. Éprouvé au banc à
1280 et 1600 px dans les deux langues : rail droit (0 px d'écart), norme posée
après coup, marche au-delà franchie → niveau 3 remonté jusqu'à l'activité,
aucun débordement horizontal, zéro fuite française sur l'écran anglais.

#### LE RELIEF remplace le rail — tranché sur maquettes (2026-10-16)

« Visuellement tout est à la même hauteur alors que le niveau augmente. » Le
reproche portait sur le rail : les marches côte à côte, pastilles alignées,
rien qui montre la montée. Deux séries de maquettes ont été refusées avant
celle-ci (« aucun n'est satisfaisant, j'attends plus de finesse »), puis une
direction retenue et poussée seule jusqu'au détail. **C'est la méthode pour
tout ce qui se juge en trois secondes** — la troisième fois qu'elle évite une
demi-journée de code écrite pour rien.

**Le relief**, c'est le même objet sur **deux axes réels** :
- en abscisse le **TEMPS** : les séances sont à 17, 17 puis 26 jours d'écart,
  donc la dernière pente est plus douce — « on a mis plus longtemps à reprendre
  moins ». Un axe par rang l'aurait caché.
- en ordonnée la valeur **ORDONNÉE PAR MÉRITE** : une durée compte à rebours,
  un taux à l'endroit. ⚠️ C'est un **renversement de la règle d'hier** (« une
  durée descend vers la norme, un taux y monte ») : avec le mérite, MONTER veut
  toujours dire PROGRESSER, et les deux moitiés des cartes se lisent dans le
  même sens. Les étiquettes de l'échelle portent l'unité réelle, donc rien
  n'est caché. `ev_descend` / `ev_monte` sont retirées.
- ⚠️ **Le tracé est DROIT entre deux mesures** : rien n'a été relevé entre les
  deux, une courbe lissée inventerait ce qu'on ne sait pas. Ce qui n'est pas
  mesuré est en **pointillé** vers un **anneau creux**.
- Une seule bascule de teinte, posée **exactement là où le tracé coupe la
  norme** (un `linearGradient` en `userSpaceOnUse` dont l'arrêt est calculé par
  interpolation), pas au point suivant. La masse sous le fil est NEUTRE : c'est
  le fil qui porte la couleur, une masse teintée ferait deux signaux pour une
  seule information.

**Ce qui disparaît** : `blocGraphe` (le relief EST le graphe, et il est là dès
l'ouverture de la carte), `state.histo`, l'appel à `/paliers/historique` —
⚠️ il ne rendait qu'un SOUS-ENSEMBLE de `perf.paliers`, donc une requête de
plus dont personne ne lisait la réponse. La route, elle, reste (elle est
testée, et c'est une lecture légitime de l'API paliers). `pal_evolution`,
`ev_masquer_evo`, `ev_zone_q`, `ev_zone_a`, `ev_leg_*`, `ev_graphe_de` partent
avec. Le bouton « Voir l'évolution » devient **« Le détail des séances »**,
dans la ligne de bilan, et n'ouvre plus que l'historique.

⚠️ **Le rail reste à la SÉANCE** (`railHtml`, `.sq-rail`). Deux questions
différentes : « quelle marche suis-je en train de mesurer » (une échelle), et
« comment cela a progressé » (un relief). Même précédent que le radar et les
barres de la vue d'ensemble.

**« Fais attention que les choses écrites ne se superposent pas. »** Ce n'est
pas une liste de cas particuliers mais un **placeur** : chaque étiquette a une
boîte, on les pose dans un ORDRE DE PRIORITÉ, et ce qui ne rentre pas n'est
pas dessiné. ⚠️ **L'ordre EST la décision** : la norme, puis les mesures (la
plus récente d'abord), puis les cibles, la pastille d'échéance, « au-delà »,
« la norme », l'échelle, la règle des mois, et en dernier « zone tenue ».
Quand la place manque, ce qui saute est la décoration, jamais le chiffre
relevé.

Les six défauts que **la mesure** a trouvés — `getBBox()` au banc, pas l'œil :
- ⚠️ **Le même relevé dessiné DEUX FOIS.** `construireRail` recopie la dernière
  mesure sur le seuil d'au-delà pour que le RAIL le montre franchi ; dans le
  relief cette copie faisait un second point, à une date où personne n'a rien
  mesuré, et le tracé partait à plat vers la droite. Mesuré : deux « 0,8 % »
  pour trois séances. Un fantôme n'est jamais une mesure, et n'emprunte pas la
  date de ce qu'il recopie.
- ⚠️ **« norme franchie » écrit deux fois** — `mieux()` répond « atteint »,
  donc toute marche à partir de la norme se disait franchie. Exactement le
  piège du drapeau du rail, un mois plus tôt : c'est `estNorme` qui tranche.
- ⚠️ **Deux étiquettes se touchaient de 1,7 px** alors que le placeur avait dit
  non-collision : les boîtes sont ESTIMÉES (rien n'est dans le document pendant
  la construction du SVG), elles se testent donc avec une **marge**.
- ⚠️ **« 14.4 essais » sortait 24 px à GAUCHE du cadre** : la gouttière était
  une constante. Elle se calcule désormais sur les étiquettes elles-mêmes, et
  la zone des points recule d'autant.
- ⚠️ **« target 2 j · to be measured » sortait 19 px à DROITE** — trouvé en
  relisant l'écran ANGLAIS, où les libellés sont plus longs. L'écart minimal
  tient les étiquettes entre elles, pas contre les BORDS : une étiquette qui
  déborde glisse vers l'intérieur, et si le glissement l'éloignait trop de sa
  marche elle se raccourcit à sa date.
- ⚠️ **C'était l'étiquette de la mesure la plus RÉCENTE qui sautait** quand la
  place manquait, au profit d'une échéance à venir — relevé sur une sortie dont
  la marche 4 avait été tranchée avant la 3. L'ordre de pose des étiquettes du
  bas part donc des mesures, la plus récente en tête.

**Deux autres décisions prises à l'écran**, pas au clavier :
- ⚠️ **Sans aucune mesure, le relief est COURT** (198 px de viewBox au lieu de
  300) : il n'y a rien à tracer, et le relief plein laissait trois cents pixels
  de vide sous une norme et une cible.
- **L'étiquetage du bas a quatre modes**, choisis sur la place DISPONIBLE :
  « cible 10 j · 11/09 » fait ~108 px, donc au-delà de six marches il faut deux
  rangées alternées, puis la date seule, puis une étiquette sur deux. Et les
  abscisses sont **écartées** (deux passes sur une chaîne d'intervalles) pour
  garantir l'écart du mode retenu ; la règle des mois passe alors par les
  couples (jour, x) réellement posés — calculée sur le temps brut, elle
  mentirait.
- ⚠️ **Un SVG n'hérite PAS des polices de la feuille** : `font-family` est
  écrit sur chaque texte (Fraunces pour les chiffres, DM Sans pour l'unité).

**Le bilan** remplace en une ligne ce que l'historique disait en dix :
« 3 marches tenues sur 3 · 5,5 j repris depuis le départ · 34 jours de suivi ».
⚠️ Un gain se dit autrement selon le sens — on *reprend* du temps, on *gagne*
des points.

⚠️ **Et un faux pas de méthode, à ne pas refaire** : la suppression d'une règle
CSS avait d'abord été écrite en expression régulière non gourmande ; le `.*?`
est parti du PREMIER `/*` du fichier et **1 840 lignes de `competences.css`
ont disparu d'un coup**, avec un symptôme trompeur (`.pal-rail` rendait
`display: block`). Restauré depuis git, puis retrait par chaîne EXACTE. Une
suppression se fait sur des bornes, jamais sur un motif ouvert.

Tests : `tests/test_109_paliers_ecran.py` passe de 84 à **101 cas** ; **neuf
défauts remis un par un, neuf cliquets tombés** (l'axe par magnitude, le
fantôme compté comme mesure, les boîtes sans marge, la gouttière fixe, le
cadre sans butée, le double « norme franchie », le relief jamais court, la
courbe lissée, la cible qui l'emporte sur un relevé). Suite : **3213 passés**,
`repet_image` 3163 + 36 sautés.
Éprouvé au banc (`tools/devrun_competences.py`, 1600 px) dans les deux
langues : six reliefs réels plus une **épreuve de charge à dix marches** (dont
deux le même jour et deux à un jour d'écart) — **zéro chevauchement, zéro
texte hors cadre** sur les 29 étiquettes du cas le plus chargé, et zéro fuite
française sur l'écran anglais.
Maquettes : canvas « Paliers — le relief » (le système, le relief, les trois
états, la densité).


#### La PREMIÈRE MESURE se pose en une fois — et le 4 redevient atteignable (2026-10-16)

Quatre reproches, et l'un d'eux ouvrait un trou de structure.

**« Si on définit la norme et qu'on l'enregistre, on ne peut plus saisir la
note de l'user après. »** Exact. Poser la norme fait basculer la sortie du
régime JUGÉ (échelle 0→4 à la main) au régime MESURÉ (le niveau se déduit du
chiffre) : l'échelle disparaît, `POST /mastery/evaluate` refuse (`measured_
output`), et il n'existait **aucun** endroit où entrer ce qu'on avait relevé.
Une norme sans mesure ne dit rien de personne.

**Et le symptôme inverse** : une note déjà posée, puis la norme ajoutée — la
carte affichait « Non évalué » pendant que l'activité montrait toujours 4. La
donnée était intacte (`ref` garde la note tant que `perf["niveau"]` est NULL),
c'est la CARTE qui ne montrait que le niveau déduit.

- **`POST /paliers/premiere`** — la norme et la mesure dans UNE transaction,
  et l'écran les demande ensemble : « Première mesure » remplace « Poser un
  palier » sur une sortie sans marche, et c'est aussi ce qu'ouvre « Définir la
  norme » depuis une carte jugée à la main.
  ⚠️ **La norme ne se redemande PAS quand elle existe** : elle vit sur la
  sortie, pas sur la personne. Qui prend un rôle déjà tenu ailleurs en hérite
  — l'écran la rappelle en lecture seule et ne demande que la mesure. C'est
  exactement le cas que l'utilisateur avait isolé.
  ⚠️ Poser la norme engage l'organisation : la route exige `peut_noter` POUR
  la mesure **et** la porte de `/norme` pour la norme — pas l'une à la place
  de l'autre.
- ⚠️ **La cible du premier relevé, deux fois corrigée.** Lui donner la NORME
  rendait « 0 · Non démontré » à quelqu'un qui fait le travail : on ne rate
  pas une marche que personne n'avait posée. Lui donner la MESURE fabriquait
  l'inverse — mesuré au banc, 40 h pour une norme de 48 h se décernait **3 ·
  Maîtrise étendue dès le premier jour**, parce que la cible devenait un
  « palier au-delà », là où le même chiffre vaut 2 par le chemin normal. La
  règle : la cible est la mesure, **jamais au-delà de la norme**. Dépasser est
  une marche qu'on DÉCIDE de poser.
- **Le troisième élément se MONTRE, il ne se tape pas.** L'utilisateur
  demandait les trois (note, norme, mesure) ; le niveau se déduit du chiffre —
  c'est la règle du module, et c'est ce que dit déjà le « i » de l'échelle. Le
  formulaire affiche donc « Niveau qui en découle · 1 · En acquisition » avant
  de valider. ⚠️ C'est un APERÇU, pas une seconde règle : avec une seule
  marche il n'y a que deux issues (la norme est atteinte, ou non), et c'est le
  serveur qui tranche.

⚠️⚠️ **« Comment un 4/4 se lit-il contre la norme ? »** La question a mis au
jour un vrai plafond : `niveau_depuis_mesure` ne rend JAMAIS 4 — la déduction
s'arrête à 3 (« la norme dépassée »), et c'est écrit dans la règle depuis le
début (« le 4 n'est jamais déduit : c'est un jugement »). Mais sur une sortie
mesurée, l'échelle 0→4 disparaît : **le 4 n'était plus atteignable par aucun
chemin**, et l'échelle mentait sur son propre palier du haut.
`/mastery/evaluate` accepte donc, d'un évaluateur qui fait foi et sur une
sortie mesurée, **le 4 et lui seul** (`null` l'efface) ; `activity_mastery` lui
donne la priorité sur le niveau déduit. La carte porte un bouton « Expertise »
et écrit les deux chiffres : « 4 · Expertise · posée à la main · mesuré :
1 · En acquisition ». Sans ce second chiffre, elle disait 1 pendant que
l'activité lisait 4 — le même défaut d'accord, dans l'autre sens.

**L'unité se choisit** (`champUnite`) : `%`, `j`, `h` en liste, plus un champ
libre pour le reste. ⚠️ Une norme NEUVE part sur « % », pas sur « Autre… » :
ouvrir le champ libre d'emblée, c'est remettre au clavier ce qu'on vient d'en
retirer. ⚠️ Une norme EXISTANTE sans unité garde son vide — on ne change pas
une donnée enregistrée en passant. ⚠️ Les trois VALEURS sont les mêmes dans
les deux langues (`j`, pas `d`) : l'unité est une donnée portée par la sortie,
pas un libellé ; seul son intitulé suit la langue.

**Le radar ne se dessinait pas** alors que la personne a trois activités, et
le message annonçait « à partir de trois activités ». Les axes étaient filtrés
sur le seul `required_level` : quelqu'un dont aucun rôle n'a fixé de cible
n'avait **aucun** axe. Un axe existe désormais dès qu'il y a quelque chose à y
porter — un requis OU un démontré — et le message dit la vraie condition.
⚠️ La couche du REQUIS suit alors la même règle que celle du démontré : des
morceaux de polyligne, jamais un polygone fermé sur un sommet absent — le
fermer à zéro dirait « rien n'est exigé ici » là où la vérité est « personne
n'a encore fixé d'exigence ». Mesuré au banc : 0 requis + 2 démontrés → 2 axes
(sous le seuil, donc pas de radar, ce qui est juste) ; +1 requis → 3 axes et
le radar paraît.
ℹ️ Un axe qui porte un requis ISOLÉ ne dessine pas de segment (il en faut
deux) : la cible reste lisible dans les barres par rôle et dans la bulle. Pas
de marqueur dédié — il ajouterait du bruit au cas normal, où le requis est un
contour fermé.

Tests : `test_108` (+1, l'expertise ; le cas « 0→3 refusés » couvre maintenant
les quatre niveaux), `test_109` (+13 — la première mesure, la norme héritée,
la transaction, l'aperçu qui n'est pas une règle, la liste d'unités, le radar
des deux côtés). **Huit défauts remis un par un, huit cliquets tombés.**
⚠️ L'un d'eux ne mordait PAS au premier essai : sans mesure posée, le niveau
déduit est NULL et le contrôle de priorité de l'expertise passait sans rien
éprouver. Le cas tranche donc un palier d'abord.
Suite : **3227 passés**, `repet_image` 3187 + 41 sautés. Éprouvé au banc
dans les deux langues : parcours
complet des deux chemins (norme absente / norme héritée), unité par défaut,
expertise posée puis retirée, et zéro fuite française sur l'écran anglais
(texte ET attributs).

⚠️ **Relevé en chemin : `tests/test_111_debug_decisions_ia.py` rougissait à
chaque exécution sur l'instance.** Cinq de ses cas lisent `Code/example.vsdx`,
que `.dockerignore` exclut (`*.vsdx`) — ils échouaient donc dans l'arbre
d'image en passant en local. Garde de saut posée, comme pour la fixture
`pulse_app`, `test_65` et `test_107` : un contrôle qui rougit toujours n'est
plus lu, et le jour où il a raison personne ne regarde. C'est la quatrième
fois — tout cas qui ouvre un fichier hors de `static/`, des gabarits ou de
`tests/` doit se demander s'il existe dans l'image.


#### LA FICHE — la section de notation, tranchée sur maquettes (2026-10-16)

« Autant dans le style que dans l'agencement de la section que dans son
manque de couleurs, les phrases en petit et en gris au lieu de mettre des i. »
Cinq directions dessinées à l'échelle (canvas « Notation à la main —
5 directions » : la règle, les deux lectures, le verdict, l'escalier, la
fiche), une retenue — **la fiche** — avec trois corrections demandées :
le fond sombre du verdict passe à gauche, les crans ne portent que leur
chiffre, et la porte vers les paliers prend le vert au lieu de l'ocre.

**Ce qui n'allait pas, mesuré avant de redessiner** : trois boîtes grises de
poids égal empilées, deux échelles identiques de cinq carrés BLANCS bordés de
gris — un 0 et un 4 s'y ressemblaient trait pour trait — chaque cran portant
son libellé en 10 px (« Autonome / compétent » sur un bouton de 50 px, cinq
fois, deux fois par sortie), et un pavé de deux lignes de 12,5 px gris pour
expliquer le régime jugé. Rien n'y disait ce qu'on regarde en premier.

**La section se sépare en deux.**
- ⚠️ **Ce qu'on JUGE passe sur fond de nuit** — le même dégradé que l'en-tête
  de la page. Ce n'est pas un décor : c'est le CONTRASTE qui désigne le sujet.
  En gris clair, la colonne de gauche n'aurait été qu'une quatrième boîte.
  Elle porte le nom de la sortie en Fraunces, **le standard minimal ÉCRIT**
  (derrière une info-bulle que personne ne survole, la phrase qui dit sur quoi
  on note n'existait pas) et le **niveau attendu en 44 px vert pastel**
  `#7ee0b8` — la barre à franchir, lisible de loin.
- **Ce qu'on POSE** à sa droite : les deux notes, le verdict d'accord, la
  preuve.

**La rampe de couleur, qui manquait.** Chaque cran porte au repos une teinte
pâle de SON palier, et la teinte bascule une fois, au niveau 2 — le seuil
d'autonomie, exactement comme le relief bascule au franchissement de la
norme. Le cran choisi prend la couleur pleine. ⚠️ **Sur le bloc qui fait foi
la couleur dit le NIVEAU ; sur l'auto-évaluation elle dit QUI** (violet), et
cela ne change pas selon qui regarde — sinon la même note changerait de
couleur d'un lecteur à l'autre.

⚠️ **Un cran ne porte plus que son chiffre.** Le nom du palier vient au
survol, **après une demi-seconde** (`transition-delay` sur `:hover`
seulement) : assez pour ne pas clignoter quand on traverse la rangée. Au
clavier il n'y a pas de survol, la bulle sort au `:focus-visible`, sans
délai. ⚠️ **Pas d'attribut `title`** : l'info-bulle du système sortirait
par-dessus la nôtre, une seconde plus tard et sans sa couleur — le piège déjà
rencontré sur la matrice RH. `aria-label` porte « 2 · Autonome / compétent ».

**La porte vers les paliers passe au VERT**, en rappel du niveau attendu, et
en **six teintes** pour qu'elle ne soit pas un aplat : fond en dégradé
`#eaf6f1 → #f6fbf9`, filet `#bfe3d4`, pastille blanche à glyphe `#11835e`,
titre `#0a5540`, phrase `#4e8775`, bouton `#11835e → #0a5540`.

⚠️ **Le verdict d'accord sort des deux blocs.** Posé dans celui du bas, il se
lisait comme un commentaire de l'auto-évaluation ; il parle de l'ÉCART, donc
des deux. `majValeur` écrit désormais dans `[data-accord]`.

⚠️ **Les crochets de l'enregistrement survivent à la refonte.**
`saveEvaluation` lit `.cv2-nt.is-mienne [data-lv].sel`, et **la gomme en fait
partie** : la sortir du bloc (comme la maquette le montrait) aurait fait
qu'un niveau effacé ne serait plus trouvé, et l'enregistrement l'aurait sauté
en silence. Elle reste donc dans la rangée, en pastille creuse à l'écart.

⚠️ **Le standard se cite avec un `<q>`**, pas des chevrons écrits à la main :
ils sont une convention française, et le navigateur pose les guillemets de la
langue du document tout seul. ⚠️ Le cliquet qui l'exige lit aussi les
COMMENTAIRES — en écrire un qui contient le caractère le fait échouer sur son
propre texte, comme pour les clés i18n construites.

Trois phrases passent derrière un « i » : l'échelle 0 → 4, le pourquoi du
régime jugé, et — pour les sorties mesurées — ce qu'elle était déjà.
Hauteur de la section : **430 → 327 px**.

Tests : `tests/test_109_paliers_ecran.py` passe de 114 à **126 cas** ; **sept
défauts remis un par un, sept cliquets tombés** (le fond de nuit retiré, le
requis en petit, le nom rendu au cran, la bulle sans délai, la rampe
invisible, la porte en ocre, le verdict rendu à l'auto). Suite : **3239
passés**, `repet_image` 3199 + 41 sautés. Éprouvé au banc à 1600 px dans les
deux langues : les deux états de
la fiche (avec et sans niveau attendu), la bulle non rognée par
l'`overflow: hidden` de la carte (48 px sous son bord haut), et zéro fuite
française sur l'écran anglais — texte ET attributs.

#### Les formulaires de la carte deviennent des FORMULAIRES (2026-10-16)

« Cette partie-là est encore visuellement moche. » Les quatre formulaires de
la carte mesurée — poser la norme, poser la première mesure, poser une marche,
**évaluer un palier** — partageaient un patron qui n'en était pas un : un
rectangle pâle sans en-tête ni pied, où le titre flottait en 15 px, la
référence contre laquelle on mesure tenait dans une ligne grise de 13 px au
milieu du corps, le champ qu'on vient remplir faisait **130 px et 14,5 px** —
plus petit que le titre — et la SUPPRESSION traînait en lien rouge souligné,
**au ras des deux boutons**.

`ouvrirForm(zone, o, surValider)` prend désormais un objet et porte les trois
étages :
- **un en-tête** (`.pf-tete`) : pastille d'icône, titre, et à droite le
  `repere` — la cible en pastille (`.pf-rep`, Fraunces 19 px) avec son sens
  (« au plus » / « au moins »). Contre quoi on mesure est la moitié de la
  décision : elle ne se lit pas dans une ligne de corps ;
- **un corps** dont le champ est le SUJET (`.pf-grand` / `.pf-saisie`) :
  27 px Fraunces, **aligné à droite** pour que le chiffre et son unité se
  touchent ;
- **un pied** où l'irréversible est à l'AUTRE bout (`.pf-danger` avant le
  ressort, `.pf-ko` / `.pf-ok` après) : un geste qui ne se rattrape pas ne se
  pose pas à côté de celui qu'on répète.

Les quatre appels y passent — un seul qui s'en écarterait et la carte
porterait deux grammaires de formulaire. Teinte verte partout : ils
appartiennent tous au régime mesuré.

⚠️ **« Évaluer ce palier » donne son verdict PENDANT la frappe**
(`.pf-verdict`, vert ou rouge, « Atteint · contre une cible de 5 j ») : on
tapait un chiffre et rien ne répondait, alors que la séance, elle, répond en
direct. ⚠️ Mais c'est un **aperçu** de la comparaison, pas la règle : c'est
`trancher()`, au serveur, qui écrit le statut — le reconstruire côté navigateur
en ferait un second verdict, et deux implémentations d'un même verdict
finissent par diverger.

⚠️⚠️ **Deux pièges de spécificité CSS, tous deux silencieux.**
1. **`.pf-saisie input` ne posait RIEN de sa taille.** La règle globale de
   l'application vise `input[type="text"]` — un sélecteur d'ATTRIBUT, donc
   (0,2,0) — et bat une classe suivie d'un élément (0,1,1). Mesuré : la
   largeur de 128 px passait, la taille restait à **13,5 px**. Le sélecteur
   porte donc l'attribut lui aussi. Le même piège mordait déjà
   `.pal-champs input`, qui croyait poser 14,5 px depuis le début.
2. **`.pf-grand > span` prenait aussi la boîte de saisie**, qui est un span :
   elle héritait des capitales, du gris et du corps du libellé — l'unité
   sortait en « ESSAIS » gris clair à côté du chiffre. On vise `.pf-lbl`.

⚠️ **Et une leçon de shell, pas de CSS** : écrire ces commentaires par un
heredoc Bash entre guillemets a fait **évaluer les backticks** — chaque nom de
sélecteur cité entre `` ` `` a disparu du fichier, laissant des commentaires
amputés (« ⚠️ , pas  : … »). Un commentaire qui cite du code se pose par la
Write tool ou un heredoc *quoté*.

⚠️ `test_109::TestUnSeulEndroitPoseUneMesure::…ne_rerend_pas_la_page…` est
**ancré sur `rendreCourant`** : le formulaire de la carte déclare lui aussi un
`lire`, plus haut dans le fichier, et la découpe non ancrée tombait dessus —
le cas passait au vert sans rien lire de la séance.

Tests : `tests/test_109_paliers_ecran.py` passe de 126 à **134 cas** ; **huit
défauts remis un par un, huit cliquets tombés** (l'en-tête retiré, la référence
rendue à une ligne, le champ ramené à 14,5 px, les deux spécificités, le
verdict muet, la suppression ramenée à côté de « Valider », une clé absente de
l'anglais). Suite : **3247 passés**, `repet_image` 3207 + 41 sautés. Éprouvé au
banc à 1600 px dans les deux langues (`tools/devrun_competences.py`) : les deux
verdicts, et zéro fuite française sur l'écran anglais — les trois relevés sont
des DONNÉES du banc (le nom de la sortie et son standard).

### Proposer une modification d'ACTIVITÉ — tâches, outils, compétences (2026-10-19)

Le même principe que la cartographie, pour l'autre moitié des données : un
champion dépose ce qu'il veut changer sur une fiche d'activité, un
coordinateur applique ou refuse, et ce qui est appliqué vaut pour tout le
monde — c'est la même ligne en base, il n'y a rien à propager.

⚠️⚠️ **Ce n'était pas « rien » avant : c'était un MUR.** `Code/ecriture.py`
consulte `carto_access.can_edit`, qui rend faux pour un champion sur une carto
COMMUNE. Il se faisait donc refuser l'ajout d'une tâche avec le code
`lecture_seule` — **le motif réservé à `user`**. Il pouvait proposer une
modification de la CARTE, et rien de ce qu'elle porte.

**Le périmètre** : tâches (et leurs rôles), outils, compétences, savoirs,
savoir-faire, aptitudes, HSC, contraintes, données — tout ce qui s'écrit
depuis la page Activités.

#### Les trois décisions qui structurent le module

- ⚠️ **Des GESTES, pas un instantané.** Une carto est un diagramme : on en
  recopie l'état et on compare deux images. Une fiche d'activité n'a pas
  d'état global — la page fait des appels CRUD atomiques et il n'existe aucun
  brouillon. `ActivityChangeRequest.actions` porte donc la suite des requêtes
  **telles qu'elles ont été faites** (chemin, méthode, corps), rejouées dans
  l'ordre. Transporter un instantané aurait demandé de réécrire la page
  entière pour qu'elle travaille sur une copie.
- ⚠️ **La porte DÉTOURNE, elle ne refuse plus.** Le verdict
  `VERDICT_PROPOSITION` est rendu par `porte()` quand `can_propose` dit oui sur
  la carto active et que le chemin est de ceux qu'on sait rejouer ;
  `_detourner()` range le geste et répond **202** avec `code: "proposition"`.
  Les 39 fichiers de routes ne changent pas — c'est le même argument qui a
  fait de `ecriture.py` une porte centrale, et la quarantième route écrite
  demain sera couverte sans rien faire.
- ⚠️ **Un LOT, pas un geste par proposition** (`status='draft'` tant qu'on
  accumule). Corriger une fiche, c'est cinq ou six clics ; une proposition par
  clic demanderait six décisions au coordinateur pour un seul travail — et on
  refuse une intention, pas une touche de clavier.

#### Appliquer : on rappelle les VRAIES routes, en une transaction

`rejouer()` résout chaque geste dans `url_map`, pousse un
`test_request_context` et appelle la vue. Zéro duplication de la logique
métier : ce qui est appliqué est exactement ce que le champion aurait écrit, et
une seconde implémentation de « ajouter une tâche » finirait par diverger de la
première — ce qu'on cherche précisément à éviter en faisant relire.

- ⚠️ **Chaque route appelée fait son propre `commit()`.** Rejoués tels quels,
  cinq gestes donnent cinq transactions : si le troisième échoue, les deux
  premiers sont déjà écrits et **personne ne peut dire où la proposition s'est
  arrêtée**. `_neutraliser_commits()` remplace `commit` par `flush` le temps du
  rejeu — le motif de `tools/provisioning/provision.py`, pour la même raison.
  Mesuré : un geste impossible → 409 `rejeu`, **0 ligne écrite**, la
  proposition **reste `pending`**, et l'écran dit LEQUEL a bloqué.
- ⚠️ La session est recopiée dans le contexte du rejeu, et `active_entity_id`
  est posée sur la carto de la PROPOSITION : le coordinateur tranche depuis la
  page Carte, souvent sur une autre entité que la sienne.
- ⚠️ **On ne détourne que ce qu'on saura rejouer** (`route_existe`). Trouvé par
  un cliquet qui ne mordait pas : un POST vers une URL qui n'accepte que PUT
  devenait une proposition — acceptée, examinée, puis **impossible à
  appliquer**. Hors de la liste explicite `_SEGMENTS`, la porte refuse comme
  avant : détourner une écriture qu'on n'a pas prévue, c'est promettre un
  examen pour un geste qui échouera.

#### L'écran

- **Page Activités** : un bandeau ambre (la couleur de la gouvernance, déjà
  celle du bouton « Proposer » de l'éditeur) avec le compte du brouillon, une
  fenêtre pour relire / retirer / envoyer, et « Mes propositions » avec leur
  décision. Rendu **seulement pour qui propose** (`propose_activites`, le même
  verdict que la porte : le bandeau ne doit jamais promettre un examen que la
  porte refuserait).
- ⚠️ **On enveloppe `fetch`, on ne touche pas aux huit fichiers JS** de la
  page. Chacun lit sa réponse à sa façon ; les reprendre un par un, c'est huit
  occasions d'en oublier un. ⚠️ On **clone** la réponse : un flux ne se lit
  qu'une fois, et l'appelant va le lire à son tour.
- ⚠️ **Un TOAST, pas une modale** (`optiqAlert` reste pour ce qui ARRÊTE) :
  cinq gestes, c'était cinq fenêtres à fermer. Relevé à l'écran.
- **Examen** : la MÊME fenêtre que les propositions de carto (page Carte), et
  le bandeau compte les deux files — un coordinateur décide au même endroit, et
  une seconde porte finirait par ne jamais être ouverte (c'est ce qui faisait
  manquer les propositions du temps où elles vivaient dans la page RH). Pas
  d'avant/après en image : une fiche n'est pas un dessin, on lit les gestes
  numérotés, dans l'ordre où ils seront rejoués.
- ⚠️ **Les identifiants des DEUX tables se chevauchent** : la proposition de
  carto n° 3 et celle d'activité n° 3 existent toutes les deux. Tout passe par
  `cle` (`'c'+id` / `'a'+id`), jamais par `id` seul.

#### Trois pièges rencontrés, tous déjà connus sous une autre forme

- ⚠️⚠️ **DEUX conventions de substitution coexistent** : `{n}` (lu par
  `carto_examen.js`) et `[[n]]` (lu par `activite_propositions.js`). Une clé
  qui prend la mauvaise affiche son marqueur **tel quel**, et rien ne lève
  d'erreur — relevé à l'écran avec « **[[N]] MODIFICATIONS PROPOSÉES** ». Une
  clé suit la convention du FICHIER qui la lit ; `test_112` le tient dans les
  deux sens.
- ⚠️ **Le libellé se rebâtit à la LECTURE**, jamais à l'écriture : le champion
  propose dans sa langue, le coordinateur lit dans la sienne. On stocke
  `op` + `objet`, le verbe et la famille viennent du catalogue (`acp.v_*` /
  `acp.f_*`) — une clé par couple ferait 54 libellés par langue, et l'article
  s'accorde dans la famille (« la tâche », « l'outil »), ce que l'anglais
  ignore. C'est la leçon du journal d'activité récente.
- ⚠️ **Un OUTIL n'appartient à aucune activité** : c'est le catalogue de la
  carto. Le corps d'une création en porte pourtant une (elle part du panneau
  d'une tâche) — la retenir faisait paraître « Ajouter l'outil X » sous une
  fiche qui ne le porte pas. Trouvé parce que le cliquet correspondant ne
  mordait PAS : il neutralisait un garde que le chemin rendait inutile.
- ⚠️ Supprimer une carto efface ses `activity_change_requests` : PostgreSQL
  applique les clés étrangères.

#### La popup Accès dit enfin ce que l'accès OUVRE

Cet écran décide QUI entre, et ne disait nulle part ce qu'on y fait. La
question s'est posée en étendant les propositions : ouvrir une carto ouvre
désormais aussi le droit d'y **proposer** des tâches, des outils et des
compétences. Un bandeau en tête de la fenêtre dit les trois paliers (consulte /
propose / écrit et valide) et **renvoie** vers le tableau des droits de la page
Comptes — ⚠️ il ne le règle pas : deux écrans pour un même réglage finissent
par donner deux réponses.

Aucun droit nouveau : `propose_carto`, `edit_carto` et `review_carto` servent
tels quels. Les activités SONT les données d'une carto — c'est déjà ce que dit
`DROIT_ECRITURE = "edit_carto"` dans `ecriture.py`.

Tests : `tests/test_112_propositions_activite.py` (33 cas ; **18 défauts remis
un par un, 18 cliquets tombés**). Suite : **3282 passés**, `repet_image`
3242 + 41 sautés. Éprouvé au banc
(`tools/devrun_partage.py`) dans les deux langues : parcours complet champion →
envoi → coordinateur → application, les trois objets **relus en base**, le
refus d'un `user`, et zéro fuite française sur l'écran anglais.

#### Le style des propositions d'activité, repris sur maquettes (2026-10-20)

« Techniquement c'est exactement ce que je voulais, par contre niveau visuel
je suis assez déçu, c'est vraiment bas étage. » Le reproche était juste, et
chiffrable — mesuré à l'écran avant de redessiner :

| | Avant | Après |
|---|---|---|
| Bandeau | **57 px**, titre 14 px, sous-titre 12,5, bouton 13 | 63 px, titre 17 px (Fraunces), chiffre **32 px** |
| Fenêtre | 496 × 374, lignes de 51 px, libellé 13,5 px | 544 × 523, rail numéroté, objet **18 px** (Fraunces) |

⚠️ **Tout était à l'échelle des MÉTA** — celle d'une ligne de date ou d'un
compteur. Or le bandeau annonce un **changement de régime** (« ici vous ne
modifiez pas, vous proposez »), une information permanente et structurante ;
et la fenêtre est le moment où l'on **engage son travail devant quelqu'un**.

⚠️ **Et le bandeau ne MONTRAIT rien** : « 3 modifications » sans dire
lesquelles — il fallait ouvrir la fenêtre pour savoir ce qu'on venait de
poser. Il affiche désormais les deux premiers gestes, puis « et n de plus ».
C'est le défaut de fond, pas la peau.

**Tranché sur maquettes** (canvas « Propositions d'activité — le style » :
le bandeau en deux directions, la fenêtre, l'écran du coordinateur), direction
**B — « le filet »** retenue : un liseré vertical porte la couleur, le chiffre
porte le poids, la ligne du bas porte les gestes.

**Le vocabulaire est celui déjà tranché ailleurs**, rien d'inventé :
- **l'en-tête sur fond de NUIT** (`#4a2d0a → #2d1b06`), comme la fiche de
  notation — c'est le CONTRASTE qui désigne le sujet, pas un filet de couleur ;
- **Fraunces sur ce qu'on vient lire** : le compte, le nom de l'objet ;
- **le rapport INVERSÉ** entre l'action et le réglage (page Temps, page
  Carte) : au repos le bouton du bandeau est discret — on vient LIRE ; plein
  dès qu'il y a quelque chose à envoyer — on vient AGIR ;
- **l'ambre de gouvernance**, pas le violet de la page : prendre l'accent de
  la page rangerait ce bandeau parmi ses contenus, alors qu'il parle de ce qui
  ARRIVE à ce qu'on écrit.

⚠️ **Les gestes sont un RAIL NUMÉROTÉ** (`<ol>`, pas `<ul>`) : l'ordre
affiché EST celui du rejeu, et c'est la seule chose que le coordinateur doit
lire avant d'appliquer. Le verbe passe en capitales au-dessus, l'objet porte
la police d'affichage — c'est lui qu'on vient lire, pas « Ajouter la tâche ».

⚠️ **Les DEUX écrans parlent la même langue** : le champion et le
coordinateur regardent le même objet, deux vocabulaires finiraient par dire
deux choses du même geste. Même en-tête de nuit, même rail, mêmes tailles —
`carto_examen.css` reprend la peau de `activite_propositions.css`.
ℹ️ Seul le bouton « Appliquer à la carto » garde le **teal** de la fenêtre
d'examen : il est partagé avec les propositions de CARTO, et lui donner une
autre couleur ici ferait deux verdicts visuels pour un même geste.

**Le toast est conservé** tel quel : corriger une fiche, c'est cinq ou six
gestes, et une fenêtre à fermer entre chacun transformerait la saisie en
parcours d'obstacles. Il passe simplement sur le fond de nuit, comme le reste.

⚠️ **Piège rencontré pour la énième fois** : le cliquet qui interdit
`--pg-accent-soft` tombait sur **le commentaire qui l'explique**. Il retire
donc les commentaires CSS avant de chercher — on parle de RÈGLES. Même famille
que les clés i18n construites, et que le `<section>` écrit dans un commentaire
de la doc technique.

Tests : `tests/test_112_propositions_activite.py` passe de 33 à **41 cas** ;
**huit défauts remis un par un, huit cliquets tombés** (le bandeau qui compte
sans montrer, le chiffre et l'icône au même endroit, le bouton sans son
rapport inversé, la liste non ordonnée, les deux écrans qui divergent,
l'accent doux de la racine, le toast qui vole un clic, une clé absente de
l'anglais). Suite : **3317 passés**, `repet_image` 3277 + 41 sautés.
Éprouvé au banc dans les deux langues :
bandeau vide et plein, fenêtre, envoi, examen côté coordinateur — zéro fuite
française sur l'écran anglais (texte ET attributs).

---

### La réinitialisation de mot de passe, refaite (2026-10-28)

« On a des retours comme quoi il ne marche pas. » C'était exact, et pire que
ça : **il n'a jamais marché sur aucune des deux instances.** Sondé en direct,
les deux rendaient la même chose pour n'importe quelle adresse :

    [error] L'envoi d'email n'est pas configuré sur cette instance.

C'est la branche `if not current_app.config.get("MAIL_CONFIGURED")`, et
`MAIL_CONFIGURED` vaut `bool(MAIL_USERNAME and MAIL_PASSWORD)` — or **`MAIL_*`
n'apparaissait dans AUCUN workflow de déploiement.** Le code était entier ; il
n'a jamais eu de quoi envoyer.

⚠️ **Et les 23 tests passaient**, parce qu'ils forcent
`app.config["MAIL_CONFIGURED"] = True` pour atteindre les branches d'envoi.
Même famille que le piège des clés IA de `conftest` : un contrôle qui fabrique
la condition qu'il devrait vérifier ne vérifie rien.

#### Les deux workflows ne posent pas les variables de la même façon

| | commande | effet |
|---|---|---|
| staging / officielle | `--set-env-vars` | **remplace tout le jeu** — une variable posée à la main dans la console est effacée au déploiement suivant |
| pilote | `--update-env-vars` | additif — une variable posée à la main survit |

Les trois workflows portent donc désormais `MAIL_USERNAME`, `MAIL_PASSWORD` et
`MAIL_DEFAULT_SENDER` (secrets GitHub du dépôt). Sans les secrets, l'écran dit
proprement que l'envoi n'est pas configuré — c'est le repli d'origine.

⚠️⚠️ **Un commentaire au milieu d'une commande à antislashs devient un
ARGUMENT.** Posé par erreur en branchant ces variables : sept lignes
d'explication glissées dans le `gcloud run deploy` seraient parties comme
arguments, et le déploiement aurait échoué sur les deux instances à la fois.
Cliquet : `test_72::TestLesCommandesDesWorkflowsNeSontPasCoupees`.

#### `Code/mot_de_passe.py` — la source unique

La politique était écrite à **cinq** endroits (quatre à six caractères, un à
huit) et le jeton ne vivait que dans sa route. Tout est passé dans un module :
`MIN_LONGUEUR` (**8**, on aligne vers le haut), `valider`, `poser`,
`empreinte_session`, `regle_session_perimee`, `debit_depasse`,
`fabriquer_jeton`, `lire_jeton`, `consommer`, `purger`.

⚠️ **Rien de ce module ne dépend du canal d'envoi** : le même code sert
l'instance hébergée par AFDEC et l'installation chez le client — seules les
variables `MAIL_*` changent, et l'assistant `/setup` les demande déjà. C'est
écrit une fois, ça marche partout.

#### Le jeton : trois verrous, et il faut dire lequel fait quoi

La charge était l'**adresse e-mail** signée, et rien n'était stocké : le lien
restait valable une heure **même après** le changement de mot de passe.
Désormais la charge porte `{u: id, e: empreinte(hash courant)}`, et une ligne
`password_resets` accompagne chaque demande.

1. la signature et l'âge — c'est tout ce que faisait la version d'avant ;
2. **l'empreinte du mot de passe courant. C'est LUI qui interdit le rejeu**, et
   il le fait seul : chaque écriture re-sale le hash, donc même reposer le MÊME
   mot de passe change l'empreinte. Il couvre aussi le changement par un autre
   chemin (un administrateur depuis la page Comptes) et vaut même si la ligne
   en base a disparu ;
3. la ligne en base. ⚠️ **Elle n'est PAS un second verrou contre le rejeu** —
   le banc de cliquets l'a montré : en la retirant, aucun test de rejeu ne
   rougissait. Elle exige qu'une demande ait été **réellement enregistrée**
   (un jeton ressorti après la purge ne passe pas) et porte la limitation de
   débit et la trace d'audit.

⚠️ **Rien d'exploitable n'est stocké** : ni l'adresse saisie, ni le jeton, ni
l'IP — seulement leurs empreintes SHA-256. Une lecture de la base ne doit
rendre ni un lien utilisable, ni la liste des adresses essayées.
⚠️ `password_resets.user_id` n'est **pas** une clé étrangère, comme
`usage_events` : PostgreSQL applique les FK et SQLite non, donc une FK ici
ferait échouer la suppression d'un compte en production sans qu'aucun test ne
puisse le voir.

#### La limitation de débit, et le piège Cloud Run

3 demandes par adresse et 10 par IP, par quart d'heure, **comptées en base**.
⚠️ Le motif en mémoire de `hub/app.py` ne tient pas ici : Cloud Run redescend
à zéro instance et en relance plusieurs, chacune avec son dictionnaire.
⚠️ **Une adresse INCONNUE est tracée aussi** : ne compter que les envois réels
dirait, par le simple fait de ne pas ralentir, que l'adresse est inconnue.
⚠️⚠️ **L'IP vient de `X-Forwarded-For`, pas de `request.remote_addr`** : sur
Cloud Run celui-ci est l'IP du frontend Google, et la limite par IP
verrouillerait l'instance ENTIÈRE au dixième essai. L'en-tête est falsifiable,
il ne sert qu'au débit — la protection qui compte est celle par adresse.

#### L'énumération : le message neutre était annulé par son voisin

L'intention était bonne (« Si cette adresse correspond à un compte… ») mais le
`try/except` de l'envoi vivait **à l'intérieur du `if user:`** : « Erreur lors
de l'envoi de l'email » ne pouvait apparaître QUE pour un compte existant. Il
suffisait d'essayer des adresses. L'incident part au journal, l'écran rend le
même message dans tous les cas.
⚠️ **Et le login disait laquelle des deux moitiés était fausse** (« Compte
introuvable. » / « Mot de passe incorrect. ») : de quoi dresser la liste du
personnel. Un seul message, `login.bad_credentials`.

#### Les sessions se ferment — sinon on change la clé sans reprendre le logement

`users.password_changed_at` (migration à chaud) + `session['pwd_at']` posé au
login + un `before_request` dans `create_app`. Sans cela, l'intrus déjà
connecté — celui qu'on veut précisément mettre dehors — y reste jusqu'à ce
qu'il se déconnecte lui-même.
⚠️ **Une session sans empreinte est acceptée tant que le compte n'a jamais
changé de mot de passe** : sinon la mise en service déconnecterait tout le
monde d'un coup. L'absence ne devient une péremption qu'au premier changement.
⚠️ **Le re-hachage transparent du login ne pose PAS l'horodatage** : il
déconnecterait chacun à sa propre connexion. Seule `mdp.poser` l'écrit.
⚠️ **La porte NE DÉTOURNE PAS `/login`, `/logout`, `/forgot_password` ni
`/reset_password`.** Trouvé en écrivant le test, pas à l'usage : renvoyer vers
/login depuis un lien de réinitialisation enverrait dans le mur la personne
qui vient de cliquer son lien — sa session est périmée PARCE QUE son mot de
passe a changé, et c'est exactement ce qu'elle est en train de faire.

#### Ce qui a coûté le plus : le décor de tests

⚠️ **Trente fichiers posent `session['user_id']` à la main**, et une douzaine
de helpers y REMPLACENT `user_id` sans toucher à l'empreinte qu'un vrai login
a laissée. La porte les met dehors, et le symptôme ne désigne jamais sa cause :
302 vers /login, ou 403 parce que `_current_user()` est devenu None, ou un
`KeyError` sur une réponse JSON qui n'en est plus une — dans un fichier qui ne
parle pas de mots de passe. Mesuré : huit rouges sur cinq fichiers.

La concession vit **dans le décor**, jamais dans l'application : la porte ne
mord que sous le levier `PWD_SESSION_STRICTE` (fixture `porte_stricte` de
`test_117`), et la RÈGLE est éprouvée dans les deux sens directement sur
`regle_session_perimee`, que le remplacement ne touche pas. C'est pour cela
que `session_perimee` est un ALIAS distinct de la règle : ne jamais appeler
`regle_session_perimee` depuis l'application, le décor ne pourrait plus rien
tolérer.

⚠️ **Et `test_35` / `test_117` doivent rendre le compte partagé INTACT** — le
mot de passe ET `password_changed_at`, en SQL brut suivi d'un `expire_all()`
(la session SQLAlchemy des tests est partagée, sa carte d'identité garderait
l'ancienne valeur). Sans cela l'horodatage restait bougé pour toute la suite.
⚠️ `auth_client` **expire** l'objet avant de lire l'horodatage, pour la même
raison. ⚠️ Un test qui se connecte POUR DE VRAI prend son propre client
(`app.test_client()`) : `client` et `auth_client` sont le même objet.

#### Ce qui n'est pas fait, et doit être dit

- ⚠️ **Il faut un mot de passe d'application Google et trois secrets GitHub**
  (`MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`) pour que le reset
  parte. Tant qu'ils manquent, l'écran dit proprement qu'il n'est pas
  configuré — rien n'est cassé, mais rien ne part.
- ⚠️ **Expéditeur Gmail + lien vers un `*.run.app`** = la signature d'un mail
  de hameçonnage : il partira souvent en indésirables, et le message de l'app
  le dit (« Pensez à regarder vos indésirables »). Le correctif de fond est un
  domaine à soi avec SPF/DKIM/DMARC — **même cause structurelle que le blocage
  Edge du pilote**. À décider, pas à deviner.
- ⚠️ **Aucun CSRF dans toute l'application** — zéro occurrence de
  `CSRFProtect`, `csrf_token`, `flask_wtf` dans `Code/`, et aucun réglage
  `SESSION_COOKIE_*` (SameSite, Secure, HttpOnly). Ça dépasse le reset : c'est
  tous les POST. Chantier à part, pas à faire en passant.
- **La force brute du LOGIN n'est pas limitée** : `debit_depasse` ne couvre que
  la demande de réinitialisation. Suite immédiate.
- Le temps de réponse n'est pas égalisé : seuls les MESSAGES sont alignés.

#### ⚠️⚠️ Une variable VIDE n'est pas une variable ABSENTE (2026-10-28)

Trouvé en regardant la console Cloud Run **avant** de poser le moindre secret :
les trois `MAIL_*` y étaient **déjà créées, et toutes les trois vides**. C'est
`--set-env-vars` qui les crée — il pose ce que le workflow lui donne, et
`${{ secrets.X }}` d'un secret inexistant rend la chaîne vide.

Or `os.getenv(cle, defaut)` ne regarde son défaut que si la clé est **absente**.
Une clé présente et vide rend `""`. Les deux conséquences ont été mesurées, et
la première est le défaut qui aurait fait échouer toute la mise en service :

- **expéditeur vide → AUCUN envoi ne part.** `flask_mail` lève
  `AssertionError: The message does not specify a sender…` — et l'envoi vit
  dans le `try/except` qui ne montre que le message neutre. On aurait donc posé
  les deux secrets, et rien ne serait jamais parti, **avec à l'écran exactement
  le même message qu'avant le correctif**. Introuvable sans les journaux.
- **port vide → `int("")` lève au DÉMARRAGE**, dans `create_app` : le conteneur
  ne démarre plus. C'est la panne « failed to start and listen on the port »
  déjà vécue le 26/09, pour une variable qu'on aurait seulement laissée vide.

`config_mail(env)` (`Code/app.py`) est la source unique, et lit **avec `or`**,
jamais avec le second argument de `getenv`. Fonction de module, pas un bloc
inline : elle s'IMPORTE, donc son contrôle tourne aussi dans l'arbre d'image —
un test qui relit `Code/app.py` comme du texte y sauterait (c'est ce que fait
`test_67`).

ℹ️ **Les deux familles de workflow ne se comportent pas pareil**, et c'est
voulu : staging et l'officielle REMPLACENT tout le jeu (`--set-env-vars` →
variables créées vides), le pilote AJOUTE (`--update-env-vars`) et ne pose ses
identifiants **que s'ils ne sont pas vides** — sinon un secret absent
écraserait une valeur réglée à la main dans la console. Le pilote n'a donc
jamais eu le défaut ci-dessus. Tenu par `test_72::TestLesIdentifiantsDEnvoiSontServis`.

⚠️ **Et le lien du mail partait en `http://`.** Le TLS s'arrête au frontend
Google, qui transmet `X-Forwarded-Proto: https` — mais gunicorn ne le croit que
d'un émetteur listé dans `forwarded_allow_ips`, dont le défaut (`127.0.0.1`)
n'est jamais l'adresse d'où Cloud Run livre la requête. `url_for(_external=True)`
lisait donc `http`. Le lien **fonctionne** quand même (tout le TLD `.app` est en
HSTS préchargé, le navigateur force https avant que la requête parte), mais un
lien http écrit dans un mail est un **signal d'hameçonnage de plus** — et ce
message en porte déjà deux. `forwarded_allow_ips` est désormais posé dans
`gunicorn.conf.py`, resserrable par `FORWARDED_ALLOW_IPS`.
⚠️ Sans conséquence ailleurs : `request.remote_addr` n'est lu qu'à UN endroit
dans tout `Code/` — le repli de `_ip_client()`, déjà précédé par
`X-Forwarded-For`.

#### Mesures

Suite : **3539 passés**, 1 sauté. Vingt-et-une gardes retirées une par une,
**vingt-et-un cliquets tombés** (dont un qui a corrigé ma documentation : voir
le verrou 3). Les six derniers tiennent les variables vides, l'expéditeur, le
port, le lien https, le mot de passe jamais écrit en clair dans un workflow et
le pilote qui n'écrase pas une valeur posée à la main.
⚠️ `tools/repet_image.sh` : **3487 passés, 45 sautés** sur une passe propre,
mais l'arbre d'image rend 0 à 2 rouges selon le passage, sur une distribution
TOURNANTE de fichiers qui ne parlent pas de mots de passe (`test_14`,
`test_48`, `test_62`, `test_63`, `test_86`, `test_91`), et une seconde passe
dans le même arbre est verte. Expérience pour trancher : la porte des sessions
**neutralisée**, une première passe dans un arbre neuf ne rend qu'UNE erreur —
celle du test qui éprouve la porte. Aucun autre fichier ne tombe. Donc la
porte n'est pas la cause ; c'est l'instabilité connue de cette suite à base
partagée. Écrit ici pour ne pas la rechercher une troisième fois.

Tests : `tests/test_117_mot_de_passe.py` (**29 cas** — usage unique, débit,
énumération, sessions, politique, langue, rien de sensible stocké, et les
variables vides), `test_35_password_reset.py` réécrit (**22 cas**),
`test_72_deploiement.py` (+4 — les identifiants servis, jamais en clair, le
pilote qui n'écrase pas, le lien https), et `test_48`, `test_54`, `test_59`,
`test_116` alignés.

#### Le mail suit la langue du compte — et l'inconnu vaut l'ANGLAIS (2026-10-29)

La route lisait déjà `users.lang` et non la session — c'est juste : la demande
part d'un écran de connexion, où personne n'est identifié. Mais la mesure a
montré un trou, et c'est exactement celui que le pilote anglophone redoutait :

| `users.lang` | corps du mail |
|---|---|
| `en`, `NULL`, `''` | anglais |
| `fr` | français |
| `EN`, `en-US`, `de`, `hi` | **français** |

⚠️ **Toute valeur qui n'est pas EXACTEMENT `en` ou `fr` sortait en français**,
parce que `t(cle, langue)` fait `langue if langue in TRANSLATIONS else
_FALLBACK`, et `_FALLBACK` vaut `'fr'`. Le `or "en"` de la route ne gardait
que le vide et le NULL.

**Ce repli-là est pourtant VOULU — pour les CLÉS.** Une clé absente de
l'anglais doit s'afficher en français plutôt qu'en clé brute (c'est écrit plus
haut : « clé absente en EN → repli silencieux sur le français »). Deux choses
différentes vivaient dans la même constante : le repli de clé, et le repli de
LANGUE. Seul le second est faux — et il ne mord que là où la langue ne vient
pas de la session validée, c'est-à-dire **au mail**, dont la langue vient d'une
colonne de TEXTE LIBRE.

`Code/translations.py::langue_destinataire(valeur)` normalise avant d'appeler
`t()` : casse et sous-tag régional acceptés (« EN », « en-US » → anglais),
l'inconnu vaut `LANGUE_PAR_DEFAUT`.
- ⚠️ **`LANGUE_PAR_DEFAUT = 'en'` redit `models.DEFAULT_LANG`**, parce que
  `translations` ne peut pas importer `models` : il n'importe aujourd'hui que
  flask, et le sens de dépendance s'inverserait. Les deux valeurs sont donc
  tenues égales par un test — deux sources de vérité qui dérivent en silence,
  c'est le défaut qu'on a déjà payé sur `dashboard_rows`.
- **Par l'application, la valeur fautive n'est PAS atteignable** :
  `/parametres/set_language` refuse en 400 hors `_ALLOWED_LANGS`, le login
  dérive de `default_lang_for(email)`, l'import de comptes aussi, et le
  rattrapage au démarrage n'écrit que `en` ou `fr`. Mais une correction à la
  main en SQL ou une restauration depuis un vieux dump peut tout contenir — et
  la base du pilote a connu les deux.
- ⚠️ **Le correctif de FOND n'est pas fait** : `t()` garde son repli de langue
  français. Le changer toucherait les neuf pages d'un coup (et
  `role_i18n.nom_affiche` passe aussi une langue explicite, même si elle vient
  de la session, donc validée) — cela se décide en regardant l'application,
  pas depuis la route du mail.

Tests : `test_117::TestLeMailSuitLaLangueDuDestinataire` passe de 3 à 6 cas —
les huit valeurs de la colonne jouées BOUT EN BOUT, une IP distincte par cas
(la limite par IP ne doit pas décider du résultat d'un test sur la langue).
**Trois cliquets, trois rouges.**

### Seize petites choses relevées à l'usage (2026-11-03)

Une liste sans sujet commun — six écrans différents — mais toutes de la même
forme : un détail qui **mentait**, ou qui n'était **pas possible**. Deux
d'entre elles cachaient un défaut de fond.

Cliquets : `tests/test_130_retours_du_pilote.py` (63 cas), plus trois cas
renouvelés dans `test_95`, `test_105` et `test_51` qui affirmaient ce qu'on
vient de changer. **32 gardes retirées une par une, 32 cliquets tombés.**
Suite : **3722 passés**, 1 sauté. Éprouvé à l'écran dans les deux langues sur
`tools/devrun_temps.py` et `tools/devrun_competences.py`.

#### ⚠️⚠️ En anglais, la page Temps comptait 60 fois trop peu

Le symptôme rapporté était un libellé : « on a `j` pour jour, cela doit être
`day` ». En le corrigeant, la cause en a découvert une autre, bien plus lourde.

Les cinq sélecteurs d'unité de la page Temps étaient écrits
`<option>{{ t('time.unit_hours') }}</option>` — **sans attribut `value`**. Or
la valeur d'une option sans `value` EST son texte : en anglais le navigateur
envoyait `hours`, et `UNIT_TO_MIN.get('hours', 1)` rend **1**, c'est-à-dire des
MINUTES. Choisir « hours » ou « days » ne faisait donc rien, en silence, dans
toute la page — analyses de projet, d'activité, de faiblesse.

Le commentaire du gabarit disait pourtant la règle (« la VALEUR envoyée au
serveur reste française »), et la fonction JS `unitSelect()`, qui construit les
lignes par tâche, la respectait : c'est le gabarit qui ne l'appliquait pas.
Les `value=` sont posés, et un cliquet relit `UNIT_TO_MIN` pour exiger que
chaque clé du serveur apparaisse en `value=` dans le gabarit.

⚠️ La fiche d'activité, elle, écrivait ses unités **en dur** (`>j</option>`)
alors que les clés existaient (`acttime.unit_*`) et servaient déjà aux lignes
par tâche, dix lignes plus bas. EN : `min` / `hrs` / `day`, FR : `min` / `h` /
`j` — la même triade partout, page Temps comprise (« mettre min hrs day au
lieu du nom complet »).

#### ⚠️⚠️ Le coût annuel du retard comptait le travail DEUX FOIS

« Pour le coût annuel du délai on ne doit pas comprendre le temps de travail
mais juste le retard. » C'était une erreur d'arithmétique, pas de libellé :
`V = (L + M) · P` (travail refait + attente), quand `U = L · P`. Le total de
l'accueil valant `U + V`, il rendait **2·L·P + M·P** — le travail deux fois —
et la carte intitulée « attente » annonçait du travail. `V = M · P`, et le
mensuel `X = V / base` suit. Mesuré à l'écran (L = 10, M = 5, 20 %, 45
occurrences/an) : U 7,5 h, V **3,8 h** au lieu de 11,3 h.

⚠️ `T = C + (L+M)·O` (le délai moyen corrigé, par exécution) n'a **pas**
changé : refaire du travail retarde bien la sortie. C'est le CUMUL ANNUEL qui
ne doit pas additionner deux fois la même minute. Les deux phrases
d'explication (`fw_desc_delay_annual`, `fw_desc_delay_month`) le disent.

#### La probabilité d'une faiblesse se saisit en POURCENTAGE

« 1 sur N » demandait de penser à l'envers, et un cas sur trois ne s'écrivait
pas : 3 rend 33,3 %, jamais 30 %. `time_weakness.prob_percent` (migration à
chaud) fait foi quand il est là.
⚠️ `prob_denom` reste **écrit**, arrondi (`_denom_depuis_pct`), et reste
**accepté** en entrée : des appels anciens l'envoient encore, et la suite de
tests aussi. Quand les deux arrivent, le pourcentage gagne.
⚠️ Une ligne écrite AVANT la colonne rend `100/N` (`_pct_stocke`) : c'est la
traduction exacte de son denominateur, il n'y a rien à deviner.

#### Un délai de production ne tombe pas sous la durée de travail

`delai_plancher(B, C)` : on ne produit pas un résultat en moins de temps qu'il
n'en demande. L'écran borne le champ **à la sortie** (pas pendant la frappe —
effacer « 120 » pour taper « 90 » passerait par un « 1 » imposé) et dit
pourquoi la valeur a bougé ; le serveur borne avant d'écrire, sinon la base
garderait l'état impossible.
⚠️ **Trois cas de la suite posaient cet état** et affirmaient les chiffres qui
en découlent (`test_95::_calc` avec 60/20, `test_105` avec 60/30). Leur décor
est corrigé, pas leur sujet : un test qui encode un état impossible ne garde
rien.

#### Page Temps : le rail de l'accueil MONTRE, il ne crée plus

Les quatre tuiles de « Vos analyses » ouvraient l'écran de saisie **vierge** —
ce que fait déjà « + Nouvelle analyse », à dix centimètres au-dessus — alors
que chaque tuile porte le NOMBRE d'analyses de son type : annoncer « 3 » puis
ouvrir une page blanche est un mensonge. `montrerGroupe(type)` déplie le
groupe, le mémorise et le **désigne** une seconde et demie (`est-pointe`) :
un défilement seul passe inaperçu quand le groupe est déjà à l'écran.

#### Page Temps : les lignes d'une analyse de rôle sont celles du RÔLE

On pouvait « Ajouter une ligne » — avec un sélecteur portant **toute la
carto** — et supprimer une ligne au bouton : une analyse de rôle se retrouvait
avec des activités que le rôle ne tient pas, et sans celles qu'il tient, alors
que c'est le rôle qui définit son périmètre. L'activité est désormais un
**libellé** (son identifiant vit sur la ligne, `tr.dataset.activityId`), la
colonne « Actions » a disparu, et il ne reste à régler que la durée, la
récurrence et la fréquence — ce qu'on vient vraiment estimer.
⚠️ Les quatre récurrences étaient écrites **en dur, en français**, dans
`addRoleRow` : elles s'affichaient telles quelles en anglais.

#### Les contraintes passent SOUS les connexions

Côte à côte (`2fr 1fr`), les connexions portaient déjà deux colonnes internes
et trois en-têtes dont « Performance » : chaque libellé se repliait sur deux ou
trois lignes, et une contrainte — qui est une phrase — sur quatre ou cinq.
L'une sous l'autre, les deux ont toute la largeur de la carte.

#### Le rôle d'une tâche se lit dans la langue de l'écran

On choisissait « Doer » en anglais et le badge affichait « Réalisateur » après
validation. La valeur **stockée** reste la chaîne française : c'est elle que le
serveur renvoie, elle qui porte la classe CSS du badge, et la réécrire
casserait les lignes déjà en base. Seul l'AFFICHAGE suit la langue
(`roleStatusLabel`) — exactement la règle des niveaux HSC.
⚠️⚠️ **`static/js/tasks_roles.js` est chargé APRÈS `tasks.js` et redéfinit
CINQ de ses fonctions** (`showTaskRoleForm`, `hideTaskRoleForm`,
`submitTaskRoles`, `loadTaskRolesForDisplay`, `deleteRoleFromTask`) : c'est lui
qui gagne au rendu, et le bloc correspondant de `tasks.js` est du code MORT.
Même piège que `tools.js` / `tasks.js`. Les deux sont corrigés — le traducteur
est déclaré avec `function`, jamais `const` : un `const` répété dans deux
fichiers de la même portée lève une SyntaxError et coupe tout le script.

#### Supprimer un rôle : l'administrateur, et lui seul

Un rôle est commun à l'entreprise (`roles_communs`) : le supprimer emporte ses
titulaires, ses liens aux activités et aux tâches de **toutes** les cartos, et
l'accès qu'il ouvrait. Renommer reste permis à qui le pouvait — c'est
réversible, ceci ne l'est pas. Le bouton n'est plus rendu hors administrateur
(`peut_supprimer`), et la route refuse de son côté : le masquage n'est pas une
sécurité. Le `confirm()` passe par le catalogue, il était en dur en français.

#### Le droit de MODIFIER un compte : il existait déjà

« On a mis le créer, pas le modifier. » Vérifié sur `origin/staging` :
`modifie_comptes` est la huitième ligne du tableau des droits depuis le
**27/10** (commit `cfbb158cb2`), par défaut **administrateur + coordinateur**,
champion et utilisateur fermés — exactement ce qui était demandé. Elle se règle
**page Comptes**, section « Droits par statut » ; la popup d'accès de la page
Carte y **renvoie sans la régler**, et c'est voulu (deux écrans pour un même
réglage finissent par donner deux réponses).
Ce qui a été corrigé : son libellé disait « Modifier un compte **(hors
statut)** », ce qui n'est plus vrai depuis le 28/10 — le statut se change
depuis la fiche, sous `peut_changer_statut`. Et la ligne a désormais son
cliquet, qui vérifie le défaut ET que `/comptes/droits` la sert.

#### Page Compétences : une flèche SANS libellé ne produit plus de sortie

« Si les sorties ont une data inconnue on ne doit pas prendre le nom de la
destination. » `_current_output_specs` le faisait : on lisait que « Usiner la
pièce » produit « Contrôle qualité » — c'est-à-dire une autre **activité**, pas
une donnée. Et cette fausse sortie se faisait noter, évaluer, et comptait dans
le MINIMUM qui fait le niveau de l'activité. Une donnée dont personne n'a écrit
le nom sur la carte n'est pas connue : on ne l'invente pas.
⚠️ `output_ids_en_bloc` (le tableau global de la page RH) et `_destinataires`
suivent la même règle : deux règles donneraient deux chiffres pour la même
personne.
⚠️ Les lignes déjà semées en base par la règle d'avant ne sont pas effacées :
`porte_du_travail` les garde si quelqu'un y a travaillé, et elles sortent de la
liste sinon. Le cliquet correspondant ne mordait pas tant que le décor n'en
portait pas une — la version en bloc ne retient que des `Data` qui existent.

#### Page Compétences : les cartes de rôle du bas redisaient le radar

Elles REDISAIENT la liste « par rôle » posée à côté du radar : même liste, même
ordre, même geste (un clic ouvre le rôle). Ce qu'elles portaient en plus — les
quatre compteurs, le bouton du plan de formation — vit sur la page
d'évaluation, celle-là même qu'un clic ouvre (depuis le 15/10). Retirées, avec
`carteRole`.
⚠️ **L'état vide reste** (`#cv2-sans-role`) : il vivait dans ces cartes, et sans
lui quelqu'un sans aucun rôle n'aurait plus rien du tout à l'écran.

#### Page Compétences : la norme vient de la LISTE DES ACTIVITÉS

« Enlever la définition de la norme quand elles ne sont pas encore notées. La
norme de l'entreprise est récupérée par ce que l'on a noté dans la page liste
des activités. »

Ce qu'on y note, c'est l'**indicateur de performance** d'une connexion
sortante — la colonne « Performance » de la fiche d'activité
(`Performance.link_id`). C'est là que l'entreprise écrit ce qu'elle attend
d'une sortie ; la page Compétences le **lit** (`indicateurs_de_sortie`), elle
ne le redemande pas. À défaut de repère de réussite propre, la fiche le montre
comme standard, en disant d'où il vient.

- `norme_depuis_indicateur(texte)` (`Code/paliers.py`) en tire une
  **proposition** — valeur, unité, sens — que la première mesure pré-remplit et
  que la personne confirme. Un indicateur illisible ne propose **rien** plutôt
  que d'inventer un chiffre. Éprouvé sur onze écritures réelles
  (« ≤ 48 h », « 95 % de conformité », « sous 5 jours », « at least 90 % »,
  « within 2 days », « max 3 retouches », « 1,5 jour »…).
  ⚠️ Le SENS se devine, et c'est le seul endroit où l'on devine : un
  pourcentage se bat à la hausse, tout le reste à la baisse. Les marqueurs
  explicites l'emportent toujours.
- **La porte « Définir la norme » n'apparaît qu'une fois la sortie NOTÉE.**
  Poser la norme bascule la sortie en régime mesuré, et la note à la main
  cesse alors d'être saisissable : offerte sur une sortie que personne n'a
  regardée, elle demandait d'arbitrer un chiffre attendu avant d'avoir jamais
  jugé la chose. On juge, puis on mesure. Mesuré à l'écran : sortie notée →
  porte présente ; sortie non notée → porte absente.
  ⚠️ C'est bien **la première mesure** qui s'ouvre, pas la seule norme : les
  deux se décident dans le même geste (`/paliers/premiere`), sinon le régime
  basculerait sans qu'aucun chiffre n'ait été relevé.

#### Deux pièges déjà connus, revus ici

⚠️ **Le cliquet du standard minimal lit aussi les COMMENTAIRES.**
`test_109::test_le_standard_minimal_revient_ECRIT` interdit les guillemets
français écrits à la main dans le corps de `resultCard` (le texte cité passe
par `<q>`, qui pose ceux de la langue du document) — et il a d'abord attrapé
**le commentaire qui explique le correctif**. Troisième fois, après les clés
i18n construites et le `<section>` de la doc technique.

⚠️ **`playwright.fill` déplace le focus**, ce qui déclenche une borne posée sur
`change` au milieu de la saisie : mesuré, le champ de délai contenait
« 12010 ». C'est le banc, pas l'écran — mais le cas ne prouve alors plus rien.
On pose les valeurs puis on émet `change` à la main.

#### Deux points de la liste restent ouverts

- « **dans la page temps supprimer** » : la phrase s'arrête là. Rien n'a été
  supprimé — on ne devine pas ce qu'on retire d'un écran.
- « les cards d'en bas sont redondantes avec celle de la légende du schéma,
  **comme on peut <** » : la fin manque aussi, mais le début suffisait et les
  cartes sont parties.

### Les retours du pilote indien, confrontés au code (2026-11-05)

Classeur « OPTIQ Tool Query » — **36 lignes du 07/09 au 29/10**, par cinq
personnes d'ARaymond. Chacune relue dans le code de `staging` plutôt que de
mémoire. Le tri :

| verdict | n | ce que ça veut dire |
|---|---|---|
| corrigés ici | 7 | un défaut, ou un trou d'une ligne |
| déjà réglés sur `staging` | 12 | signalés chez eux, corrigés depuis ; le report les portera |
| clos par eux-mêmes | 5 | leur feuille porte « Closed » et la solution |
| à arbitrer | 12 | une fonctionnalité, un choix produit, ou une demande à préciser |

Cliquets : `tests/test_135_retours_pilote_inde.py` (30 cas). **17 gardes
retirées une par une, 17 cliquets tombés.**

#### ⚠️⚠️ « AI assistance is not in english » — la cause n'était pas l'interface

`chatbot.py` sert bien le prompt système en anglais (`chatbot.system.en`,
`chatbot.mode_creer.en`). Mais `chatbot.js` construisait le **premier tour
UTILISATEUR en français** : « Mode création activé. Je souhaite créer les
tâches pour l'activité "X" via un entretien guidé. Commence l'interview. » Un
modèle qui reçoit une consigne française répond en français — c'est ce que le
pilote voyait, et aucun réglage de langue n'y changeait rien.

⚠️ **Et c'était un PROMPT écrit dans le navigateur**, ce que le catalogue
chiffré interdit (`Code/prompts/catalog.py` est exclu de l'image client et
servi en Fernet). L'amorce est donc **retirée, pas traduite** : elle était
redondante — `chatbot.mode_*.{lang}` est déjà ajouté au prompt système et porte
la consigne d'ouverture (« Start with ONE SINGLE open question… »). Le client
poste `demarrage: true` et le serveur **n'ajoute aucun tour utilisateur**.
⚠️ Conséquence : `if not message` devient `if not message and not demarrage`,
et l'historique ne range rien au démarrage (un tour vide se relirait à chaque
tour suivant).

L'écran, lui, passe au catalogue : **40 clés × 2 langues** (`chat.*`), les six
attributs (`title`, `aria-label`, `placeholder`) compris — que `test_78` ne lit
pas. `chatbot_widget.html` sort de l'inventaire de dette i18n (il y valait 5).
⚠️ `CL()` rend la CLÉ quand elle manque, jamais un repli français : un repli en
dur ne se voit pas, et c'est exactement ce que le pilote a signalé.
⚠️ Le bouton d'injection porte **UNE** clé avec son nombre dedans
(`chat.inject`, `[[n]]`) : « Injecter » + un compteur + « tâche(s) dans
l'activité » découpait une phrase en trois, et l'ordre des mots n'est pas le
même d'une langue à l'autre.
⚠️ Le cliquet des deux langues lit les **DICTIONNAIRES**, pas `t()` : une clé
absente de l'anglais retombe silencieusement sur le français, si bien que la
première version du test restait VERTE en retirant une clé.

#### ⚠️ Renommer une carto : le même défaut que `delete_entity`, resté ailleurs

« Not able to change the name or rename the imported Map » (Madhuri, 24/09) et
« in my ID I am not able to rename the map » (Arun, 29/10). `update_entity`
cherchait `Entity.query.filter_by(id=entity_id, owner_id=user_id)` — **exacte­
ment ce qui avait été corrigé dans `delete_entity` le 23/09**, et laissé ici.
Or la liste des cartos mélange ses propres cartos, celles **sans propriétaire**
et les cartos communes ouvertes à ses rôles. Le bouton « Renommer » était donc
offert sur une carto de sa propre liste, et la réponse disait « Entité non
trouvée ». Leur instance porte **trois cartos sans propriétaire** (#12, #28,
#30) : c'est elles.

On lit la carto par son id, puis on applique `carto_access.can_edit` — la règle
de `/cartography/api/save`. **Une porte qui contredit la règle qu'elle fait
respecter est un second avis, pas une porte** (la leçon de `ecriture.py`).

⚠️ **Et il reste sept autres sites de la même famille**, non touchés ici :
`upload-cartography` et l'import VSDX (lignes ~1384 et ~1584), et les quatre
routes de liaisons cross-carto. Remplacer la propriété par `can_edit` y est
plus qu'une ligne — remplacer le diagramme d'une carto COMMUNE relève de la
proposition, pas de l'écriture directe. À reprendre dans une passe à part.

#### Une carto VISIBLE ne se dit pas « non trouvée »

« Can not delete the map » (Arun, 29/10). Le défaut de fond était corrigé
depuis le 23/09 ; ce qui restait, c'est le **message**. Une carto commune
ouverte à ses rôles s'affiche dans sa liste avec son bouton Supprimer, et le
refus répondait 404 « Entité non trouvée » — on cherche alors une carto
disparue. Le refus est juste, c'est le motif qui manquait : **403
`pas_proprietaire`**, avec la phrase qui dit pourquoi.

#### ⚠️ La récurrence TRIMESTRIELLE, et le piège de la valeur inconnue

« In Time Management - quaterly recurrence is not available » (Arun, 29/10).
Quatre récurrences seulement. Le piège : une récurrence inconnue retombe sur
`return q`, c'est-à-dire sur l'**ANNUEL** — ajouter l'option sans le facteur
aurait fait compter une charge trimestrielle **quatre fois trop peu, en
silence**. Même famille que les `<option>` sans `value` du 03/11.

Le facteur est posé aux **trois** endroits qui comptent :
`annuel_minutes` (calendrier civil → 4), `cout_faiblesse`
(`H = Sa * 4 / SEMAINES_PAR_AN`, semaines TRAVAILLÉES, la convention de ses
voisines) et `annuelMinutes` côté navigateur.
⚠️ **`test_105::test_une_recurrence_inconnue_ne_multiplie_rien` se servait de
« trimestriel » comme exemple de récurrence INCONNUE** : il affirmait l'absence
qu'on vient de combler. Son décor est corrigé (« lunaire »), pas son sujet —
et `test_les_quatre_recurrences` devient `…_les_cinq_…`.
⚠️ Et **un cliquet a attrapé un défaut de ma propre retouche** : la chaîne de
remplacement passée à `re.sub` était BRUTE, donc le gabarit a reçu
`<option value=\"trimestriel\">`, antislashs compris — l'attribut aurait été
invalide. Une insertion se vérifie sur le rendu, pas sur le succès du script.

#### Désigner le garant se propose — mais le garant SEUL

« Unable to set the garentor in activity list — grant the access » (Arun,
29/10). Depuis le 19/10 un champion qui touche aux données d'une activité sur
une carto commune dépose une **proposition** ; le garant manquait à la liste
(`_SEGMENTS` porte `tasks`, `gestion_outils`, `savoirs`, `constraints`… pas
`/roles`). Il se faisait donc refuser en `lecture_seule` — le motif d'un
`user`, alors que proposer est précisément ce qui l'en distingue.

⚠️ **On n'a PAS mis `roles` dans `_SEGMENTS`** : cela rendrait proposable la
SUPPRESSION d'un rôle, qui emporte ses titulaires et ses liens dans toutes les
cartos et qui est réservée à l'administrateur depuis le 03/11. Seul
`/roles/garant/activity/` est ouvert, avec sa famille (`garant`), son verbe
(`designer`), son activité lue dans le CHEMIN et son objet = le **nom** du
rôle (le corps ne porte qu'un `role_id`, et la proposition doit rester lisible
si le rôle est renommé d'ici l'examen). Deux clés neuves — `acp.v_designer`,
`acp.f_garant` — injectées dans les **DEUX** écrans (l'auteur et le
coordinateur regardent le même geste).

#### Rechercher une cartographie

« Add "search" option to find chart » (Manoj, 29/10). Lu comme « trouver une
carto » : leur instance en porte une quinzaine, dont neuf du même nom de base
numérotées le 29/09. Un champ dans la pop-up Gestion des entités.
⚠️ Il **MASQUE**, il ne re-rend pas la grille : la réécrire à chaque frappe
ferait perdre le curseur du champ qu'on tape. ⚠️ Branché sur `input`, pas
`change` — sur `change` il ne filtrerait rien pendant la frappe, sans erreur
pour le dire. ⚠️ Et `.entity-grid-item[hidden] { display: none }` est déclaré à
la main : `[hidden]` est une règle du NAVIGATEUR, une classe d'auteur qui pose
un `display` l'emporte. **Quatrième fois** que ce piège mord.

#### Les douze points NON implémentés, et pourquoi

Deux **contredisent un choix écrit de l'app** :
- ⚠️ « Roles are visible for all — only related map roles needs to be visible »
  (28) est exactement le modèle quitté le 23/09 (`roles_communs.py`) : revenir
  au cloisonnement refabriquerait les 380 lignes pour 56 noms réunies le 28/09.
  Le besoin est réel mais il est d'**affichage** — filtrer la liste sur les
  rôles qui portent une activité de la carto regardée.
- « For each activity and line setting and name correction approval is not
  required » (33) : le modèle des propositions ne distingue pas le cosmétique
  du structurant, et c'est délibéré. Levier plus simple déjà là : cocher
  « enregistrer directement » pour le champion dans le tableau des droits.

Cinq sont des **fonctionnalités de l'éditeur** (`editor.js`, synchronisé avec
le dépôt OptiqCarto) : ajustement automatique du texte dans les formes et les
losanges (19, 25 — `wrapText` existe, la réduction de police non), verrou de
proportions et anti-chevauchement VIVANT (20 — `antiOverlap` n'agit qu'à
l'import), index des activités dans l'éditeur (30 — la vue en lecture l'a, pas
l'éditeur ; vérifié, aucun index dedans).

Trois sont des **décisions** : bloquer l'import tant que tout n'est pas
rattaché (22 — contredit l'import partiel, l'historique et la lecture « dans
l'autre sens », tous bâtis pour qu'on revienne finir) ; une carto par défaut
par compte (24 — petite et cohérente, mais elle ajoute un écran) ; le temps de
chargement (18 — **mesuré : 15,2 s de démarrage à froid** sur Cloud Run, qui
redescend à zéro instance ; le levier est une instance toujours chaude, et il
se paie).

Deux sont **à préciser** : « Bands are not same as the template » (10 — la
couleur a été corrigée le 30/08 ET les 12 entités du pilote réparées en base,
or le retour date du 07/09 : il parle peut-être des noms ou de l'ordre) et
« Activity List & Map activity name auto correct » (15 — la ligne entière, sans
solution proposée, trois lectures possibles).

Et le guide utilisateur (29) existe mais est périmé : c'est déjà le point 1 du
« reste à faire » de la doc technique.

### La fenêtre de bienvenue dit enfin ce qui ATTEND (2026-11-08)

« Je le trouve un peu vide avec son nouveau design. » C'était exact, et la
cause n'était pas l'habillage : `attentes()` ne portait que **deux** lignes,
toutes deux des COMPTEURS, et toutes deux lues sur une seule des deux files de
propositions.

#### ⚠️⚠️ Le défaut de fond : une seule file sur deux était lue

`attentes()` interrogeait `carto_sharing.propositions_a_examiner` et
`CartoChangeRequest`. Or le bandeau de la page Carte (`_examen_en_attente`) lit
les **DEUX** files depuis le 19/10, avec un commentaire qui dit pourquoi : « le
coordinateur décide au même endroit, et un bandeau qui n'en compterait qu'une
laisserait l'autre dormir ». La fenêtre, elle, en ignorait une : un
coordinateur pouvait lire **« 2 à arbitrer » ici et « 5 » sur le bandeau**,
pour la même attente. Même défaut sur les décisions : une décision tombée sur
une proposition de FICHE ne s'annonçait nulle part dans la fenêtre.

`_deux_files(user)` est désormais la source, et les décisions bouclent sur
`_modeles_propositions()`. Les deux fonctions sources rendent `[]` tout de
suite pour qui ne tranche pas — c'est ce qui permet de calculer ceci à chaque
page.

#### Les propositions sont NOMMÉES, pas comptées

`propositions_recues()` rend `{n, lignes, reste, cartos, href}`. Chaque ligne
dit **qui** a proposé, sur **quelle carto**, et **ce que ça touche** (« la
cartographie » ou « 2 modification(s) de fiche »). Un chiffre n'apprenait
rien : il fallait ouvrir la file pour savoir ce qu'on venait de recevoir.

- ⚠️ **Plafond à `PROPOSITIONS_NOMMEES = 3`**, puis « et n autres en attente ».
  La fenêtre est LARGE, pas haute (c'est écrit dans son gabarit) : dix lignes
  la feraient défiler, et c'est la file d'examen qui est faite pour les lire
  toutes.
- ⚠️ **Les auteurs en UNE requête.** `cr.author` dans la boucle ferait un aller
  par proposition, sur une fenêtre rendue à CHAQUE page.
- ⚠️ **La ligne « n propositions à arbitrer » a disparu** des attentes : elle
  redirait ce que la section NOMME juste au-dessus. `welcome.wait.review` est
  retirée du catalogue, elle n'était plus lue par personne.
- ⚠️ `_quand(cr)` : les deux modèles ne nomment pas la colonne pareil —
  `created_at` pour une carto, `submitted_at` pour une fiche. Le plus ANCIEN
  d'abord : c'est celui qui attend depuis le plus longtemps.

#### Deux attentes concrètes de plus

- **le brouillon non envoyé** : on range trois modifications, on change de
  page, et personne ne les examinera jamais. ⚠️ On compte les **GESTES**, pas
  les lignes : un brouillon ouvert et vide n'attend rien de personne.
- **les séances d'évaluation à tenir** dans les sept jours.
  ⚠️ **Un COUNT indexé sur `date_prevue`, JAMAIS `_sessions_lisibles`** :
  celui-ci rend `SessionEvaluation.query.all()` pour un statut élevé, et cette
  fenêtre est rendue à chaque page de l'application.

#### ⚠️ Tout ce qui est ici se paie à CHAQUE page

`etat()` calcule le CONTENU même quand `montrer` est faux — c'est ce qui permet
au bouton de réouverture de ne rien re-rendre, donc de n'avoir qu'un seul jeu
de libellés. La règle qui en découle, et qui est désormais écrite dans le
docstring d'`attentes()` : **des COUNT indexés, et rien qui charge une table.**

#### L'habillage : l'ambre de la gouvernance

La section porte l'**ambre**, comme le bandeau des propositions d'activité et
la fenêtre d'examen ; le reste de la fenêtre est en indigo→violet. L'écart est
voulu, c'est lui qui désigne la seule chose de cet écran sur laquelle quelqu'un
d'autre attend une réponse.

- ⚠️ Elle vit **dans la colonne de gauche**, en tête, et avant les nouveautés.
  Le gabarit le dit : « une section de plus va dans une colonne existante — une
  troisième colonne ne tiendrait pas la largeur ». Un cliquet compte les
  colonnes.
- ⚠️ **Aucune règle neuve ne lit `--pg-accent-soft`** ni ses trois frères :
  déclarés sur `:root` où `--pg-accent` vaut encore le gris par défaut, ils
  rendent du GRIS. Les mélanges sont écrits sur place.
- ⚠️ `min-width: 0` sur le texte d'une ligne : sans lui, un nom de carto long
  élargit la fenêtre entière.

#### ⚠️ Le détecteur de fuites de langue ne lisait que les PRÉFIXES

En ajoutant `welcome.props_more` = « et %s de plus », les huit cas de fuite de
langue sont passés au ROUGE : `_valeurs_welcome()` comparait
`fr.split("%s")[0]`, donc le fragment **« et »** — deux lettres, qu'on retrouve
dans n'importe quel texte anglais. Le détecteur a été **renforcé** plutôt que
contourné : il lit maintenant TOUS les fragments fixes (suffixes compris) et
ne retient que ceux d'au moins `FRAGMENT_MIN = 6` signes.

⚠️ Effet de bord bienvenu : un libellé dont le nombre vient EN PREMIER
(« %s modification(s) de fiche ») n'avait aucun préfixe et sortait donc
**entièrement** du contrôle. Il y rentre.

#### ⚠️ Et le piège du COMMENTAIRE, pour la quatrième fois

`test_la_fenetre_ne_charge_JAMAIS_toute_la_table_des_seances` interdit
`_sessions_lisibles` dans `bienvenue.py` — et il s'est d'abord attrapé
lui-même, sur le commentaire qui explique POURQUOI on ne l'appelle pas. Les
commentaires et les docstrings sont retirés avant la recherche. (Les trois
occurrences précédentes : les clés i18n construites, le `<section>` de la doc
technique, les guillemets du standard minimal.)

#### ⚠️ Un cliquet de coût peut ne rien garder

`test_les_auteurs_sont_lus_en_UNE_requete` est resté **VERT** en remettant une
requête par ligne : toutes les propositions du décor venaient du MÊME auteur,
donc `ids` n'avait qu'un élément et le compte ne changeait pas. Le décor sème
désormais TROIS auteurs, et le test regarde la requête des auteurs
(`FROM users … users.id IN`) au lieu du total — le total, lui, grandit de toute
façon, parce que `carto_access.can_review` interroge la base une fois par
proposition. **Ce coût-là lui appartient, il est antérieur, et le cliquet n'est
pas là pour le maquiller.**

#### ⚠️⚠️ Deux cliquets qui ne gardaient rien, et c'est l'arbre d'image qui l'a dit

**1 · Un test qui relit une SOURCE `.py` rougit dans l'arbre d'image.**
`test_la_fenetre_ne_charge_JAMAIS_toute_la_table_des_seances` lisait
`Code/bienvenue.py` pour y interdire `_sessions_lisibles` : **vert en local,
rouge dans `tools/repet_image.sh`**, qui est compilé en bytecode. Cinquième
occurrence (après la fixture `pulse_app`, `test_65`, `test_107`, `test_111`) —
et la première que j'ai écrite en connaissant le piège, après l'avoir corrigée
la veille dans `test_105`.

Réécrit sur le **COMPORTEMENT** plutôt que sauté : il espionne les REQUÊTES
envoyées pendant `attentes()`. Portable, et plus fort — il mordrait aussi sur
un chargement écrit autrement. C'est la règle à préférer : *un contrôle qui
saute ne garde rien, un contrôle réécrit sur le comportement y gagne.*

**2 · `count()` enveloppe la requête, et sa sous-requête liste TOUTES les
colonnes.** La version réécrite affirmait d'abord
`"developpeur_user_id" in requete` — or SQLAlchemy rend
`SELECT count(*) FROM (SELECT sessions_evaluation.id, …,
sessions_evaluation.developpeur_user_id, … FROM …) AS anon_1` : la colonne y
figure **même sans aucun filtre**. Vérifié : le cas restait VERT en retirant le
filtre. L'assertion porte désormais sur ce qui suit le `WHERE`.

⚠️ Règle qui en découle : **une assertion sur le TEXTE d'une requête doit viser
la clause**, jamais la requête entière — la liste des colonnes y met tous les
noms de la table.

Tests : `tests/test_127_fenetre_bienvenue.py` passe de 36 à **56 cas** ;
**19 gardes retirées une par une, 19 cliquets tombés** — dont trois dont
l'injection visait d'abord à côté, et deux assertions qui ne gardaient rien
(voir ci-dessus). Suite complète : **3790 passés**, 1 sauté.

### Les formulaires de la page Temps : trois directions, rien d'implémenté

« Ils sont vraiment trop blanc gris et écrit en petit. » Mesuré avant de
dessiner, dans `static/time.css` puis multiplié par le `zoom: .8` que
`ui-theme.css` pose sur `body.pg` :

| élément | feuille | écran |
|---|---|---|
| titre de sous-carte | 13 px | **10,4 px** |
| libellé de champ | 12,5 px | **10 px** |
| valeur saisie | 13,5 px | **10,8 px** |
| phrase d'aide | 12 px | **9,6 px** |

La phrase d'aide est donc **sous le plancher de 11 px** de l'échelle
typographique du design system. Et les quatre formulaires partagent
`--card-2` + `--border` : rien ne dit lequel on remplit, alors que les quatre
couleurs existent déjà (`--tm-projet` `#64748b`, `--tm-activite` `#7c3aed`,
`--tm-role` `#d97706`, `--tm-faiblesse` `#dc2626`) et servent aux portes de
l'accueil.

Trois directions proposées sur maquettes à l'échelle, **avant d'écrire une
ligne** — c'est la méthode retenue pour tout ce qui se juge en trois secondes,
et la quatrième fois qu'elle évite une demi-journée écrite pour rien :
**A · le bandeau** (la couleur du type en tête, typo remontée, structure
intacte, une demi-journée), **B · ce que je dis / ce qui s'en déduit** (feuille
de calcul, panneau de sortie collé à droite), **C · les trois temps** (le
formulaire Faiblesse pose en réalité trois questions, et rien ne le dit).

⚠️ Point relevé pour B : la faiblesse se calcule déjà en direct **au serveur**,
en différé de 420 ms (treize variables ; la réécrire dans le navigateur en
ferait une seconde implémentation). Un panneau « qui bouge pendant la frappe »
veut donc dire *420 ms après*.

Arbitrage rendu : **A pour les quatre, C pour la Faiblesse, et le panneau de
B conservé** — « il permet de faire un résumé clair et limpide de ce qui se
passe ». Livré le 08/11.

### La saisie de la page Temps : A + C livrées, et le panneau réparé (2026-11-08)

#### ⚠️⚠️ Le panneau de droite RE-ADDITIONNAIT le travail et l'attente

Le panneau demandé existait déjà — `<aside class="tm-res">`, collant, un bloc
par type — mais son bloc Faiblesse écrivait `fmtH(m['U'] + m['V'])` sous un
seul libellé « Coût annuel », et `W + X` pour le mois. **Du travail refait et
du temps d'horloge dans un même nombre**, alors que `time_view.py` dit
l'inverse en toutes lettres depuis le 03/11 :

> ⚠️ DEUX natures, jamais additionnées : `travail_min` est du travail refait,
> comparable à la charge ; `attente_min` est du temps d'horloge, qui ne coûte
> de travail à personne. Les sommer donnait « 84 % de la charge » pour 5 %
> réels.

Le tableau de bord de l'accueil les sépare ; cet écran-là ne le faisait pas.
**Deux écrans de la même page disaient deux choses.** Le panneau porte
désormais **cinq chiffres NOMMÉS** — travail refait / an, retard subi en aval
/ an, occurrences ratées / an, délai moyen corrigé, travail refait / mois
travaillé — et son titre suit le type (« Ce que ça coûte » pour la faiblesse,
« Résultat » pour les trois autres, par le MÊME `data-pour` que les blocs).

⚠️ Trois libellés ont donc changé de SENS, pas seulement de mot : `tm_fw_an`,
`tm_fw_mois` et `tm_fw_occ` nommaient une somme.

#### ⚠️ Les deux routes de la faiblesse rendaient un `calc` de forme différente

`POST /temps/api/weakness` **reconstruisait** le dict avec une liste de clés
figée ; `GET /temps/api/weakness/<id>` renvoie `cout_faiblesse` tel quel. Le
bilan partiel du temps 2 marchait donc à la réouverture d'une analyse et
**pas pendant la saisie** — vu à l'écran, pas déduit. `B` et `C` sont
désormais dans `calc` des deux côtés, et un cliquet compare les deux formes.

#### Direction C — les trois temps

Le formulaire posait dix champs à plat ; il pose trois questions, et rien ne
le disait : *quand tout va bien, combien ça coûte* · *et quand ça rate* ·
*combien de fois par an*. Rail numéroté, et **un bilan partiel par temps** —
on comprend la formule en la remplissant au lieu de la découvrir à la fin.

- ⚠️ **Tous les `id` survivent** : `time.js` écrit par id, et bascule
  `#fw-global` / `#fw-tasks` selon le mode. On a changé l'ordre et le récit,
  jamais le contrat. Un cliquet liste les vingt ids.
- ⚠️ **Le mode « par tâches » ne CACHE pas le bloc global** : il le laisse
  visible et passe `#fw-dur` en lecture seule, parce que c'est la somme des
  tâches qui l'alimente. Mon banc vérifiait d'abord la mauvaise chose.
- ⚠️ Les bilans sont **masqués tant qu'aucun calcul n'a abouti** : un bilan à
  zéro se lit comme un résultat.
- ⚠️ Ils **lisent** ce que le serveur renvoie (`C` est borné par
  `delai_plancher`, `Y` est le délai du cas dégradé) : les recalculer dans le
  navigateur en ferait une seconde implémentation.
- ⚠️ **Convention de substitution** : `time.js` résout `{cle}` par
  `fmtPhrase(cle, defaut, vals)` — pas `[[cle]]`, qui est celle de `acp.*` et
  `chat.*`. Une clé qui prend la mauvaise affiche son marqueur TEL QUEL, et
  rien ne lève d'erreur. Un cliquet le tient dans les deux sens.

#### Direction A — la couleur du type, et la typographie mesurée

Les quatre couleurs existaient déjà comme jetons (`--tm-projet` `#64748b`,
`--tm-activite` `#7c3aed`, `--tm-role` `#d97706`, `--tm-faiblesse` `#dc2626`)
et ne servaient qu'aux portes de l'accueil. `#tm-travail[data-analyse="…"]`
pose maintenant `--tm-c`, que la carte, les sous-cartes et le rail des temps
consomment.

Les tailles, **mesurées à l'écran** avant et après (le corps porte
`zoom: .8`, donc tout est rendu à 80 %) :

| élément | avant (réel) | après (réel) |
|---|---|---|
| question / titre de sous-carte | 10,4 px | **15,2 px** |
| libellé de champ | 10,0 px | **11,6 px** |
| valeur saisie | 10,8 px | **12,0 px** |
| phrase d'aide | 9,6 px | **10,8 px** |

⚠️ Le plancher de l'échelle typographique du design system est **11 px
RÉELS**, soit 13,75 px écrits dans une page zoomée à .8. Ce qu'on LIT le passe
désormais ; l'aide reste juste en dessous, assumé — elle est secondaire, et
elle a gagné 12 %.
⚠️ Tout est scopé à `#tm-travail` : `.subcard`, `.input` et `.field-hint`
servent aussi à l'accueil, qui garde sa densité.

#### ⚠️ Un cliquet qui ne gardait rien : `css.index` sur toute la feuille

`test_les_quatre_types_posent_leur_couleur` cherchait
`#tm-travail[data-analyse="role"]` dans `static/time.css` entier —
`css.index` tombait sur une règle **préexistante** (`.tm-barre-ic`, plus haut
dans le fichier), et le cas restait **VERT** en cassant la règle neuve. Il
cherche désormais dans le bloc « DIRECTION A ».

⚠️ Règle qui en découle, et c'est la deuxième fois en deux jours (après la
sous-requête de `count()`) : **un cliquet qui cherche une chaîne doit borner
la zone** — un fichier assez gros contient presque toujours un homonyme de ce
qu'on croit garder.

#### ⚠️⚠️ Ce qui a été livré d'abord n'ÉTAIT PAS la direction A

L'utilisateur a renvoyé deux captures côte à côte — la maquette, puis l'écran
réel — avec « on a exactement les mêmes soucis qu'avant, trop de blanc trop de
gris ». Il avait raison, et la cause est précise :

- la maquette A portait une **BANDE COLORÉE** en tête du formulaire. Elle n'a
  pas été construite : la carte a reçu un **filet de 3 px**, c'est tout ;
- le reste des règles visait `.subcard` — or les écrans **Projet, Activité et
  Rôle n'en ont AUCUNE** : ils sont faits d'un `.form-grid` nu. Trois écrans
  sur quatre n'ont donc rien reçu.

⚠️ **La leçon** : la couleur d'un type entre par une **SURFACE**, pas par un
trait. Et une règle d'habillage doit viser les structures qui existent
VRAIMENT dans chaque écran — relire le gabarit de chacun, pas supposer qu'ils
se ressemblent.

⚠️ **Et la leçon de méthode** : j'avais vérifié le rendu par du texte (compter
les `.tm-tps-n`, lire les tailles calculées) sans jamais REGARDER une capture.
Tout ce que je mesurais était juste ; ce qui manquait n'était pas mesuré. Pour
un travail d'habillage, la capture d'écran n'est pas un luxe — c'est le seul
contrôle qui porte sur ce qu'on livre.

Ce qui est en place depuis :

- **`.tm-barre` est devenue la bande** — dégradé de `--tm-c`, texte blanc,
  pastille et bouton Retour translucides, et une **seconde ligne** qui dit à
  quoi sert l'analyse (`time.sub_<type>`, quatre clés). Sans elle, la bande ne
  dirait rien que l'écran ne montre déjà.
  ⚠️ La pastille reprenait la couleur du type EN APLAT : sur une bande de la
  même couleur, elle disparaissait. Son override a la même spécificité que la
  règle par type (`#id` + attribut + classe) et est déclaré PLUS BAS.
- **La zone de saisie est teintée** : `.form-grid` **et** `.subcard`, fond à
  6 % de la couleur, liseré de 3 px à gauche.
- **Le bouton primaire prend la couleur du TYPE.** Il lisait `--pg-accent` —
  l'accent de la PAGE, ambre pour Temps — d'où un bouton **orange au bas d'un
  formulaire violet**. Et son ombre lisait `--pg-accent-glow`, l'un des quatre
  dérivés qui rendent du GRIS sur `:root`.
- **Le panneau de droite** porte un bandeau teinté et son grand chiffre en
  couleur.

#### ⚠️ Deux descriptions affichaient leurs balises EN CLAIR

Vu sur la capture, pas déduit : `fw_desc_extra_annual` et
`fw_desc_delay_annual` portent des `<em>` et étaient rendues **sans
`| safe`** — « Total des minutes de `<em>`travail supplémentaire`</em>` que
génère… » s'affichait tel quel. La première datait d'avant ; la seconde a été
écrite le 03/11 en recopiant le défaut.

Un cliquet général le tient désormais : **toute clé rendue sans `| safe` dont
la valeur contient une balise fait virer le test au ROUGE**, pour tout le
gabarit.

#### ⚠️⚠️ Le cliquet qui comptait a mis TROIS écritures à garder quelque chose

`test_la_zone_de_saisie_est_TEINTEE_y_compris_sans_sous_carte` vise exactement
l'omission d'origine. Il est resté VERT deux fois en la remettant :

1. **ancré sur le texte du COMMENTAIRE** qui explique la règle — or ce
   commentaire cite `.form-grid`. Il lisait sa propre explication. (Cinquième
   occurrence de ce piège dans ce dépôt.)
2. **ancré sur un bout de corps** (`color-mix(… 6%, …)`) que `.tm-tps-mode`
   partage : il regardait la mauvaise règle.

Il cherche maintenant la règle qui teinte les SOUS-CARTES, dans un CSS dont
les commentaires sont retirés, et exige que `.form-grid` partage sa **liste de
sélecteurs**.

⚠️ Règle générale, troisième fois en trois jours : **un cliquet qui cherche
une chaîne doit borner sa zone ET retirer les commentaires** — un fichier
assez gros contient presque toujours un homonyme de ce qu'on croit garder.

Tests : `tests/test_105_temps_refonte.py` passe de 57 à **78 cas** ; **20
gardes retirées une par une, 20 cliquets tombés**. Les quatre écrans relus sur
CAPTURE, pas seulement mesurés. Éprouvé au banc
(`tools/devrun_temps.py`, port libre) dans les deux langues avec Playwright :
les trois temps numérotés et traduits, la bascule de mode, les deux bilans
remplis, les cinq chiffres du panneau, zéro erreur JS, zéro fuite française
sur l'écran anglais.

#### L'aide passe derrière un « i », et les Résultats deviennent un SCHÉMA (2026-11-08)

« Au lieu d'écrire pour chaque saisie son explication au-dessous en petit, mets
tout dans des i », et « la section résultat d'une faiblesse : on comprend très
mal ce que l'on tente de mettre en exergue — tous les textes ont la même taille
donc rien ne ressort, et les couleurs rendent plus joli mais ne servent pas à
mettre en lumière les résultats ». Les deux reproches étaient mesurables.

**L'aide : huit sous les champs, dix sous les chiffres.** Une macro Jinja
`aide(cle)` les porte toutes — écrite une fois, elle garantit la même forme
partout, et son `| safe` couvre d'un coup les deux aides qui portent des `<em>`
et les deux qui portent des entités.
- ⚠️ **Pas d'attribut `title`** : l'info-bulle du système sortirait par-dessus la
  nôtre, une seconde plus tard et sans sa mise en forme, et elle n'existe pas au
  clavier. Celle du mode (`fw_hint_mode`) affichait de surcroît ses entités **en
  clair** — `&ldquo;` n'est pas décodé dans un attribut échappé.
- ⚠️ **`#fw-del-note` reste ÉCRIT**, et c'est voulu : il dit POURQUOI la valeur
  a bougé toute seule. Ce n'est pas l'explication d'un champ, c'est une réaction
  à ce qu'on vient de taper — derrière un « i », on cacherait une correction que
  l'utilisateur doit voir.
- ⚠️ Le texte vit dans le bouton (`.tm-i-txt`), **masqué par `clip`, jamais par
  `display: none`** : il doit rester dans l'arbre d'accessibilité, sinon l'aide
  n'existe plus que pour la souris. La bulle est en `pointer-events: none` — elle
  ne doit jamais voler le clic de ce qu'elle explique.
- `fw_hint_desc` existait dans le catalogue et n'était employé nulle part : le
  champ « Description de la faiblesse » le porte enfin.

⚠⚠ **Et le motif recopié de la page Compétences pose la bulle 12 px TROP
BAS.** `getBoundingClientRect()` rend **déjà** des pixels d'écran — le `zoom: .8`
y est appliqué ; seules les coordonnées qu'on **écrit** repassent par lui.
`brancherInfo` (competences_v2.js) multiplie pourtant la hauteur par le zoom
avant de la soustraire. Mesuré ici : bas de bulle à 558 px pour un bouton dont
le haut est à 556 — soit sa hauteur fois (1 − 0,8), donc **par-dessus son propre
bouton**. Après correction : 546, les 10 px demandés.
ℹ️ L'horizontal, lui, était juste des deux côtés (0,0 px d'écart) : le `* z` n'y
intervient que dans une borne qui ne mord presque jamais. C'est pour cela que la
mesure de 2026-09-17 ne l'avait pas vu — elle ne portait que sur l'horizontal.

**Les Résultats : DEUX encodages, et deux seulement.**
Avant : quatre groupes de même poids, dix chiffres à 20 px, dix explications à
12 px (**9,6 px RÉELS** sous le zoom du corps, sous le plancher de l'échelle
typographique) et quatre accents décoratifs — rose, orange, rouge, violet.

Après, la même grammaire du schéma jusqu'aux chiffres : **travail = plein**,
**attente = hachuré**, **ce qui coûterait de toute façon = gris**. C'est la
distinction que `time_view.py` interdit de confondre depuis le 03/11 — « DEUX
natures, jamais additionnées » ; elle se VOIT, maintenant. Et la règle est
écrite sous les deux chiffres annuels, là où la tentation de les additionner se
présente.

**Le schéma** — deux pistes à l'échelle (normale, dégradée), la livraison qui
glisse de `C` à `Y`, la fréquence en proportion (« 45 fois par an sur les 225
exécutions »).
- ⚠⚠ **Le travail refait est marqué À PART, pas allongé sur la piste** :
  `Y = C + M` — le modèle ne le compte PAS dans la livraison. Un schéma qui
  l'allongerait dirait autre chose que le calcul qu'il illustre. Il porte sa
  propre pastille, qui dit en toutes lettres « la livraison ne bouge pas pour
  autant ».
- ⚠⚠ **Les deux lignes partagent UNE grille** (`display: contents` sur chacune).
  Mesuré avec une grille par ligne : la colonne « livré en » de la ligne
  dégradée porte un « i » de plus, donc elle est plus large, donc son `1fr`
  valait **720 px contre 743**. Deux pistes de largeurs différentes ne se
  comparent pas, et c'est tout le propos d'un schéma à l'échelle.
- ⚠️ **Un plancher de 4 px** sur les segments non nuls : l'attente ajoutée vaut
  souvent 4 % du total (une heure sur vingt-cinq) et serait invisible — or c'est
  elle qu'on vient voir. La classe `est-nul` empêche ce plancher de dessiner un
  segment pour une valeur de zéro.
- ⚠️ **La légende ne décrit QUE la piste.** Elle annonçait « travail refait »
  en rouge plein, or rien n'est rouge plein sur la piste : une légende qui promet
  un remplissage absent envoie chercher ce qui n'existe pas. Relevé sur la
  capture.
- ⚠️ `L` et `H` sont **rendus par le serveur** (`cout_faiblesse`) : `C` est borné
  par `delai_plancher` et `H` compte en semaines TRAVAILLÉES — les recalculer
  dans le navigateur en ferait une seconde implémentation.
- ⚠⚠ Et la route POST **recopiait une liste de clés figée** là où l'autre renvoie
  `cout_faiblesse` tel quel : `L` et `H` n'auraient existé que d'un côté, et le
  schéma aurait marché à la réouverture d'une analyse et pas pendant la saisie —
  exactement le défaut du bilan du temps 2. Elle rend `m` directement.

**La hiérarchie**, mesurée à l'écran (le corps porte `zoom: .8`) :

| élément | avant (réel) | après (réel) |
|---|---|---|
| le chiffre héros (travail refait / an) | 16 px | **36,8 px** |
| le second (attente / an) | 16 px | 25,6 px |
| livraison du schéma | — | 15,2 px |
| les quatre chiffres divisés | 16 px | 16,8 px |
| les explications | 9,6 px | *derrière un « i »* |

⚠️ **UN seul bloc porte la couleur du type** — le coût annuel. Les trois titres
dans le rouge, c'était trois blocs de même poids, le défaut qu'on venait de
corriger. Un écran doit avoir UNE chose qu'on vient y lire.

**Deux défauts trouvés PAR la capture, indépendants de la refonte :**
- ⚠️ **L'unité était écrite deux fois** : `fmtH` rend déjà « 24.0h » et un
  `<span class="fw-kpi-unit">h</span>` était posé à côté — « 0.8h h ».
- ⚠️ **« Based on 45 weeks per year, i.e. 10,4 working months. »** : la virgule
  décimale est une convention FRANÇAISE, posée en dur par `.replace('.', ',')`.

Tests : `test_105` passe de 78 à **99 cas** ; **22 gardes retirées une par une,
22 cliquets tombés**. Suite : **3 873 passés**, 1 sauté ; `repet_image`
**3 802 passés** + 72 sautés. Éprouvé au banc dans les deux langues, de 900 à
1600 px :
pistes alignées au pixel, bulle à 0,0 px de son bouton, aucun débordement
horizontal, zéro erreur JS, zéro fuite française sur l'écran anglais.

##### Finition : trois phrases de moins, et le badge qui ne mordait plus

- **Les trois phrases des temps sont parties** (`fw_t1_p`, `fw_t2_p`,
  `fw_t3_p`, clés comprises) : elles décrivaient ce que l'écran montre déjà.
  La question et les champs disent tout.
- **La règle des deux natures passe derrière le « i » de SA section** (le
  titre du coût annuel) : elle parle des deux chiffres que cette section
  annonce, et le bandeau ambre qui la portait prenait une ligne entière pour
  une phrase qu'on lit une fois.

⚠️⚠️ **Un « i » de 17 px ne TIENT PAS dans une ligne de 14,5 px.** Mesuré sur
les sept libellés du formulaire : il débordait de **2,6 px** par le bas, se
retrouvait à **0,0 px** du champ qui suit — donc il le touchait, exactement ce
que la capture de l'utilisateur montrait — et était décentré de **3,8 px** par
rapport à son texte. Un libellé qui porte un « i » est donc une ligne **FLEX**
(`#tm-travail label:has(> .tm-i)`) : le badge se centre sur le texte au lieu
d'être posé sur la ligne de base. Mesuré après : **0 débordement, 0
chevauchement, 0,0 px de décentrage, 4,6 px jusqu'au champ**.
ℹ️ Les hôtes déjà flex (`.fw-chif-k`, `.fw-min-k`…) étaient, eux, centrés au
dixième près — c'est ce qui a désigné la cause.

⚠️ **Six injections MORTES dans `TIME_I18N`** : les libellés des trois temps y
étaient posés « au cas où », et `time.js` ne les lit nulle part (les sections
vivent dans le gabarit). Les trois `_p` ayant quitté le catalogue, elles
affichaient en plus une clé inconnue — et c'est `test_78` qui l'a vu.

**L'anglais, vérifié écran par écran** (banc + Playwright, pas à l'œil) :
accueil replié ET déplié, écran de choix, les quatre écrans de saisie, le mode
« par tâches » de la faiblesse, la section Résultats et le texte des bulles.
**6 348 textes relevés** (contenu + `title`, `aria-label`, `placeholder`),
confrontés aux **1 475 phrases françaises** du catalogue dont l'anglais
diffère, les DONNÉES du banc écartées. Résultat : **0 fuite française, 0 clé
brute, 0 unité française sur 389 options de `<select>` vérifiées**.
⚠️ Le collecteur lisait d'abord le texte des `<script>` — l'injection
`TIME_I18N` y figure en clair, d'où 561 fausses « clés brutes ». Un détecteur
qui parcourt le DOM doit sauter `script`, `style`, `noscript`, `template`.

Tests : `test_105` passe de 99 à **101 cas** ; **3 gardes retirées une par une,
3 cliquets tombés** (les phrases revenues, la règle rendue au bandeau, le
libellé qui redevient une ligne de base). Suite : **3 875 passés**, 1 sauté ;
`repet_image` **3 804 passés** + 72 sautés.

#### Le nom d'une analyse, et les deux bandes qui disaient la même chose (2026-11-09)

**1 · « Je n'ai pas l'impression que l'on puisse modifier le nom d'une
analyse. »** Il se modifiait depuis toujours, et les trois routes l'écrivent
(`PUT /api/project/<id>`, `PATCH /api/role_analysis/<id>`,
`PUT /api/weakness/<id>`) — des cas de `test_105` le tenaient déjà. C'était
un défaut de DÉCOUVRABILITÉ, et il tenait à deux choses :

- ⚠️ **Le champ ne portait qu'un `placeholder`**, poussé tout à DROITE d'un
  `card-head` par un `spacer`. Ouvert pour modification, le champ est REMPLI :
  plus de placeholder non plus, donc une simple boîte de texte sans étiquette
  au bout d'un en-tête. Projet et Rôle étaient dans ce cas ; la Faiblesse
  avait déjà son libellé (`fw_desc_label`), et l'analyse d'ACTIVITÉ n'a pas
  de nom — son identité, c'est l'activité choisie.
- ⚠️ **Le repère du haut portait un CRAYON et le nom** — la promesse
  universelle d'un renommage — et la seule chose cliquable à côté était la
  croix qui QUITTE la modification. C'est là que l'utilisateur a cliqué :
  « ce qui embrouille davantage, car je pensais trouver la fonctionnalité à
  l'endroit en question ».

Le champ prend donc un libellé et la **première place du formulaire**, à
gauche ; les deux `card-head` disparaissent, ils n'existaient que pour
l'aligner à droite. Et le nom du repère devient un **bouton qui MÈNE au
champ** (focus + sélection).
- ⚠️ **Il ne porte PAS une seconde saisie** : le nom n'a qu'une source. Deux
  champs pour une même valeur finiraient par se contredire. Il s'éteint quand
  le type n'a pas de champ de nom (activité).
- ⚠️ **`.tm-mod button` visait TOUS les boutons du repère** : le nom, devenu
  bouton, serait devenu une pastille ronde de 20 px. La pastille est visée par
  son id. Et `.tm-barre .tm-mod button { color: #fff }` — une AUTRE règle,
  voulue — peint ce bouton en blanc : son trait pointillé suit donc
  `currentColor`, un ambre y serait invisible.
- ⚠️ **`w-280` & co ne sont que des PLAFONDS** (`max-width`) : un `<input>`
  nu se pose à sa taille par défaut, **177 px**. Le bloc porte la base
  (300 px), le champ la remplit.

**2 · « Pourquoi les deux barres affichent 0.5h alors que la seconde compte
l'attente ajoutée ? »**
⚠️⚠️ **Le schéma avait raison ; c'est `fmtH` qui mentait.** Reproduit au
chiffre près (durée 30 min, délai 30 min, travail refait 1,5 h) :

| attente ajoutée | bande 1 | bande 2 | la puce |
|---|---|---|---|
| 0 min | 0.5h | 0.5h | *(pas de puce)* |
| **1 min** | **0.5h** | **0.5h** | **+ 0.0h** |
| 2 min | 0.5h | 0.5h | + 0.0h |
| 3 min | 0.5h | **0.6h** | + 0.0h |

La puce était affichée sur la capture — or `fw-q-m` n'apparaît que si
`M > 0` : l'attente valait donc **une ou deux minutes**, pas zéro.
`Y = C + M` donne 31 min, et `(31/60).toFixed(1)` rend « 0.5 » comme 30 min.
Quatre signaux se contredisaient : deux livraisons identiques, une puce à
« 0.0h », et un segment hachuré bel et bien dessiné.

**`fmtH` écrit des MINUTES sous une heure.** « 0.0h » pour une minute est un
mensonge, et la page se saisit en minutes — elle peut les écrire. Mesuré
après : « livré en 30 min » / « livré en 31 min », « + 1 min d'attente
subie en aval », et « Retard total / mois travaillé : 11 min » au lieu de
« 0.2h ».
- ⚠️ **On arrondit AVANT de choisir l'unité** : sinon 59,6 min sortirait
  « 60 min » juste à côté d'un « 1.0h » qui vaut la même chose.
- ⚠️ Espace **insécable**, et « min » s'écrit pareil dans les deux langues :
  rien à traduire ici.
- ⚠️ **Deux en-têtes annonçaient encore des heures** au-dessus de valeurs qui
  portent désormais leur unité — « Pesée (h) » au-dessus de « 35 min »,
  c'est-à-dire le défaut qu'on venait de corriger. `col_charge` et
  `col_weight` perdent leur « (h) » ; les colonnes de SAISIE gardent la leur
  (`col_duration_min`), le nombre y est nu.
- ℹ️ `col_duration_h`, `col_delay_h`, `col_load_h`, `col_total_h` et
  `col_weighed_h` ne sont lues par AUCUN gabarit ni JS : clés mortes, laissées
  telles quelles — c'est un ménage à part.

⚠️⚠️ **Le heredoc du shell AVALE un antislash** — troisième fois dans ce
dépôt. Un `"\\n"` écrit dans un `<<'EOF'` arrive `"\n"` dans le fichier,
donc un VRAI retour à la ligne côté Python : `js.index("\n  }")` est devenu une
chaîne non terminée et le fichier de tests ne se compilait plus. Composer par
`chr(10)` / `chr(92)`, ou passer par un éditeur qui écrit exactement.

Tests : `tests/test_105_temps_refonte.py` passe de 101 à **110 cas** ; **neuf
gardes retirées une par une, neuf cliquets tombés**.
Éprouvé au banc (`tools/devrun_temps.py`) dans les deux langues : renommage
d'un projet et d'une analyse de rôle **relus en base**, clic du repère qui
focalise et sélectionne le champ, et l'audit anglais repassé — étendu aux
analyses ouvertes pour modification — sur **8 182 textes** : 0 fuite, 0 clé
brute, 0 unité française sur 518 options.
Suite : **3 884 passés**, 1 sauté ; `repet_image` **3 813 passés** +
72 sautés.

#### LES CINQ CARTES du haut, arbitrées sur maquette (2026-11-13)

Les cartes de l'accueil disaient leurs chiffres sans dire ce qu'ils veulent
dire. Trois propositions écrites directement dans le code avaient été
refusées ; la quatrième est passée par un **prototype cliquable à l'échelle
réelle**, carte par carte, repris en trois versions — et le premier essai
visait encore à côté : il proposait des agencements de cartes quand ce qu'on
demandait était **leur contenu**. C'est la huitième fois que la méthode évite
une journée écrite pour rien. L'écran assemblé du dernier onglet est ce qui a
été implanté, sans retouche.

Les largeurs du prototype étaient JUSTES, mesurées à l'écran après coup :
**633,45 / 487,28 / 487,29 px** pour la rangée du haut, exactement ce que la
maquette annonçait.

- **1 · Deux étages** — le total, les trois rythmes dans un panneau creusé,
  puis ce que ce total couvre. ⚠️ **« Par jour travaillé » est NEUF** : c'est
  le rythme qu'on se représente le mieux et il manquait ; le serveur l'envoie
  désormais (`charge.quotidien_min`). La couverture se **COMPTE en carrés** :
  une jauge à moitié pleine se lit « à moitié fait ». ⚠️ Au-delà de
  `PLAFOND_PILE` (24) on n'ose plus compter : la pile cède la place à sa seule
  phrase — et le plafond doit être APPLIQUÉ, pas seulement déclaré (le
  cliquet est tombé là-dessus).
- **2 · La part, et sur quoi** — deux barres, **chacune nommant SON tout**
  (« 5 % de la charge (1 250 h) ») ; sans ça, deux barres de tailles
  différentes laissent croire à une seule échelle. L'attente reste
  **hachurée** : c'est du temps d'horloge, jamais additionné au travail. Le
  bloc gris dit ce qu'on **gagnerait** à lever les faiblesses, en JOURS —
  « 61,2 h » est abstrait, « 8,7 jours » se compare à une semaine de travail.
  ⚠️ Quatre tournures : avec ou sans attente, au singulier ou au pluriel — et
  l'accord du mot « jour » ne se devine pas d'une langue à l'autre (le
  français met au singulier sous 2, l'anglais au pluriel dès qu'on quitte 1).
- **3 · L'ordre de grandeur** — la question qu'on se pose vraiment en lisant la
  carte 1 : « et en vrai, ça fait combien ? » Étiquetée **ESTIMATION**,
  hachurée, et surtout **le calcul est ÉCRIT** : « Moyenne des activités
  chiffrées : 208 h. Appliquée à chacune des 6 activités sans durée :
  + 1 250 h, soit ~ 2 500 h en tout. » La première rédaction disait « ce n'est
  pas une mesure », ce qui demandait de croire sur parole ; celle-ci se
  vérifie.
  - ⚠️ **Elle n'entre dans AUCUN total** : `charge.annuel_min` reste celle des
    activités réellement mesurées, et l'écran le dit.
  - ⚠️ **La moyenne porte sur les ACTIVITÉS mesurées, jamais sur le nombre
    d'ANALYSES** : une même activité peut en porter plusieurs, et la moyenne
    tomberait sous la charge réelle d'une activité.
  - ⚠️ **NUL, pas zéro, sans rien de mesuré** : sans moyenne il n'y a rien à
    extrapoler, et un zéro se lirait comme un résultat. La carte retombe alors
    sur le COMPTE de ce qui manque.
  - ⚠️ **Un ordre de grandeur ne se donne pas à l'heure près.** Relevé à
    l'écran : « ~ 2 499 h ? » se contredit lui-même — le tilde annonce une
    approximation, le chiffre prétend le contraire. Deux chiffres
    significatifs (`ordreDeGrandeur`), **écrits une fois** : le grand chiffre
    et le calcul qui l'explique doivent annoncer le même nombre.
  - ⚠️ **La liste des trois noms a quitté cette carte** avec la maquette :
    c'est le BOUTON qui porte l'action, et il nomme ce qu'il ouvre
    (« Chiffrer « Archiver le dossier » »). Le plafond de la liste, lui, reste
    — côté serveur (`[:60]`), où il protège la réponse et non l'affichage.
- **4 · La phrase** — le fait d'abord, **écrit en toutes lettres**, puis les
  rôles pour le vérifier. ⚠️ Elle ne s'écrit **jamais d'avance** : un rôle peut
  dépasser le temps plein, et il peut n'y en avoir qu'un — « le plus chargé »
  n'aurait alors aucun sens. Trois tournures, choisies sur les chiffres. Le
  pied qui expliquait le trait du temps plein est parti : la phrase le dit
  déjà.
- **5 · Le cumul** — une seule barre de 100 %, segmentée par activité. Les
  barres d'avant, mises à l'échelle du MAXIMUM, faisaient paraître les trois
  premières presque égales ; on lit maintenant qu'elles font **89 %**.
  ⚠️ On ne réunit une queue que si elle contient PLUS d'une activité : avec
  six activités pour six teintes, la sixième devenait « + 1 autres » au lieu
  d'être nommée. Et « les trois premières font n % » ne se dit qu'à partir de
  quatre activités.

⚠️ **La charge s'écrit PAREIL partout où elle est citée en bloc.** Relevé au
banc : la carte 1 annonçait « 1 250 » et ses voisines « 1249.5h », à deux
centimètres — deux chiffres pour la même grandeur. `fmtHr` (heures entières,
localisées) sert partout où l'on parle de la charge globale ; `fmtH` garde sa
décimale pour les mesures fines.
ℹ️ **Reste** : `fmtH` écrit « 922.5h » avec un POINT décimal, même en français
(`toFixed(1)`). Défaut antérieur, visible sur toute la page ; un cliquet exige
cette forme, le corriger est un chantier à part.

⚠️ **L'espace avant le % est une règle FRANÇAISE.** Vu sur l'écran anglais du
banc : « 5% of the load » (qui passe par le catalogue, donc juste) à deux
centimètres d'un « 4 % » écrit en dur dans le JS. `pourCent()` suit la langue.

**Les deux cliquets qui ne gardaient RIEN**, et c'est le banc qui l'a dit :
- deux cas montaient leur décor **sans le cas qu'ils éprouvent** — la moyenne
  ne diverge que si une activité porte DEUX analyses, et l'estimation n'existe
  que s'il y a à la fois une activité chiffrée et une activité sans durée. Ils
  sèment donc les leurs ;
- ⚠️ l'analyse des clefs lues ratait celles choisies par un **ternaire
  imbriqué** (`p >= 100 ? 'a' : (n === 1 ? 'b' : 'c')`) : retirer l'injection de
  `tm_role_ph_sur` laissait le contrôle vert, et l'écran aurait affiché la
  **clef brute**, sans la moindre erreur. On cherche désormais toute chaîne du
  JS qui porte le nom d'une clef `time.tm_*` ou `time.fw_*`.
  ℹ️ Restreint à ces deux familles : `loading` et `role` coïncident avec
  `time.loading` et `time.role` sans être des lectures, et un contrôle qui crie
  à tort n'est plus lu.

Tests : `tests/test_105_temps_refonte.py` passe de 101 à **128 cas** ;
**18 défauts remis un par un, 18 cliquets tombent**. Deux cas existants ont été
**réécrits** plutôt que supprimés : le plafond de la liste vise désormais le
serveur, et « aucune phrase ne désigne une carte par sa POSITION » vaut pour
TOUT le catalogue `time.*` au lieu de deux clefs.
Suite : **4 105 passés**, 1 sauté ; `repet_image` **3 671 passés** + 72 sautés.
Éprouvé au banc (`tools/devrun_temps.py`) dans les deux langues, de 790 à
1600 px : **zéro fuite française sur l'écran anglais** (182 textes relevés,
attributs compris — tout ce qui reste en français est une DONNÉE du banc),
zéro erreur console, aucun débordement horizontal.
Maquette : artefact « Les cartes, une par une ».

#### Sept retours sur la page Temps — dont deux défauts de FOND (2026-11-14)

Relevés à l'écran par l'utilisateur, sur ses propres données. Deux d'entre eux
cachaient autre chose qu'un défaut d'affichage.

##### ⚠️⚠️ RENVERSEMENT : le travail refait DÉCALE la livraison

« Avec 10 heures en surcroît de travail, le message du dessous nous dit que le
travail sort en 4 h comme d'hab ; cela devrait être 14 non ? » Oui. Et c'est
le modèle qui se contredisait, pas l'affichage.

`Y` valait `C + M` — et la note du 08/11 justifiait le schéma par là même :
« le travail refait est marqué À PART, pas allongé sur la piste : `Y = C + M`
ne le compte pas dans la livraison ». Or `T = C + (L+M)·O`, le **délai moyen
corrigé**, est la moyenne de `C` (cas normal) et de `Y` (cas dégradé) pondérée
par `O` : il compte `L` depuis toujours. Les deux ne pouvaient pas être vrais
ensemble, et c'est ce que l'écran montrait — relevé sur la capture, aux
chiffres exacts : **le panneau de droite annonçait « Délai moyen corrigé :
14,0 h » pendant que le bilan du temps 2 disait « le résultat sort en 4,0 h au
lieu de 4,0 h »**, à dix centimètres l'un de l'autre.

`Y = C + L + M`. Refaire du travail retarde la sortie.

- ⚠️ **Le CUMUL ANNUEL ne bouge pas** : `U = L·P` et `V = M·P` comptent chaque
  minute une fois, et c'est le correctif du 03/11. Deux questions
  différentes — ce qui coûte sur l'année, et ce que subit l'aval un jour où ça
  rate — qui ne s'additionnent pas de la même façon.
- **Le schéma suit** : le travail refait a son segment sur la piste dégradée
  (`fw-sg-l-seg`), PLEIN et non hachuré — c'est du travail, comme le segment
  du début ; c'est l'attente qui se hachure, elle que personne ne passe à
  travailler. La pastille « la livraison ne bouge pas pour autant » est partie
  avec la règle qu'elle énonçait.
- ⚠️ **La légende doit décrire EXACTEMENT ce qui est sur la piste.** Le
  cliquet compare les deux jeux (`fw-seg--*` et `fw-pt--*`) et exige
  l'égalité : une légende qui promet un remplissage absent envoie chercher ce
  qui n'existe pas, une légende qui en oublie un laisse une couleur sans nom.
  Les deux se sont présentés en un mois.

##### ⚠️⚠️ L'analyse de rôle s'enregistrait sans pouvoir jamais s'afficher

« On la saisit, on enregistre, ça dit bien enregistré, mais quechi. » Rien
n'était perdu : il n'y avait simplement **aucune ligne** dans ce qui partait.

Depuis que les rôles sont COMMUNS à l'entreprise (23/09), un rôle peut ne
tenir aucune activité de la carto qu'on regarde. Or :
- `page()` listait `Role.query.all()` — **tous** les rôles de l'entreprise ;
- `/api/role_activities/<id>` ne filtrait sur aucune entité.

On choisissait donc un rôle qui ne tient rien ici (table vide), ou dont les
activités sont dans une AUTRE carto. Le tableau de bord, lui, ne retient que
les analyses portant sur la carto active (`any(ln.activity_id in noms …)`, et
`any()` sur une liste vide est faux) : l'analyse n'apparaissait nulle part.

Trois correctifs, et c'est le troisième qui ferme le défaut :
1. `roles_de_la_carto()` — le sélecteur n'offre que les rôles qui tiennent au
   moins une activité d'ici ;
2. `/api/role_activities` passe par `Activities.for_active_entity()` — une
   ligne appartient à la carto qu'on regarde, sinon le total du rôle
   compterait des activités qui ne sont pas « le temps de l'entité » que cet
   écran annonce ;
3. ⚠️ **une analyse SANS LIGNE est refusée** (400 `aucune_ligne`), à la
   création comme au `PATCH`. Quelle que soit la cause, on ne peut plus
   enregistrer quelque chose qui n'apparaîtra jamais. **Un enregistrement
   silencieux qui se félicite est pire qu'une erreur** : il n'y a aucun moment
   où l'on peut s'apercevoir de la perte.
   ⚠️ `lines` ABSENT ne touche à rien (le renommage seul reste possible) ;
   c'est la liste VIDE qui est refusée.

##### Les deux unités d'une même section se suivent — dans UN SEUL sens

Une durée en heures à côté d'un délai en minutes se lit de travers, et
`borneDelaiStandard` ramène alors l'une sur l'autre sans qu'on comprenne
pourquoi. La PREMIÈRE règle la seconde (`#fw-dur-unit` → `#fw-del-unit`,
`#fw-l-unit` → `#fw-m-unit`).
⚠️ **Jamais l'inverse** : dans les deux sens elles s'annuleraient, et on ne
pourrait plus jamais en mettre deux différentes.
⚠️ Poser `.value` en JavaScript ne déclenche AUCUN événement : on émet
`change`, qui remonte à `#subtab-faiblesse` d'où part le calcul.

##### Les listes déroulantes sont DESSINÉES (`static/js/tm_select.js`)

« Le truc par défaut qui ne s'ouvre pas tout le temps de manière pratique, et
visuellement tout blanc et noir. » On ne peut pas styler le panneau d'un
`<select>` : la seule façon de le tenir est de le dessiner.

- ⚠️ **Le `<select>` RESTE, et il reste la source de vérité.** Une quinzaine
  d'endroits lisent `tr.querySelector('.r-rec select').value`, écrivent
  `$('#fw-dur-unit').value = 'minutes'`, ou reconstruisent `innerHTML` : les
  reprendre un par un serait quinze occasions d'en oublier un. Il est masqué à
  l'œil (jamais `display: none` — la largeur du bouton se règle sur
  l'enveloppe), sorti de la tabulation, et c'est LUI qu'on écrit.
- ⚠️ La propriété `value` est interceptée **sur l'élément**, jamais sur le
  prototype : un `defineProperty` sur `HTMLSelectElement.prototype` vaudrait
  pour toute l'application.
- ⚠️ **Les DEUX événements, et ils remontent** : un `<select>` natif émet
  `input` ET `change`, et la page écoute tantôt l'un (la table des rôles
  recalcule sur `input` posé sur le `<tr>`) tantôt l'autre. N'en émettre qu'un
  casse silencieusement l'autre moitié.
- ⚠️ **Le panneau est posé sur le BODY en `position: fixed`** : dans une
  cellule de tableau, `.table-wrap` est en `overflow-x: auto` et le
  découperait. Donc la conversion de zoom — `body.pg` porte `zoom: .8`, un
  enfant du body en `fixed` voit ses coordonnées MULTIPLIÉES par ce zoom alors
  que `getBoundingClientRect()` les rend déjà en pixels d'écran. **Sixième
  fois** que ce piège se présente. Mesuré après : 0,0 px d'écart à gauche, et
  le panneau bascule au-dessus du bouton quand il n'y a pas la place dessous.
- ⚠️ Un observateur sur `#page-temps` habille les `<select>` créés APRÈS le
  chargement (lignes de projet, de rôle, de tâche, sélecteur cloné) : un
  balayage unique n'en verrait aucun.
- ⚠️ **Dans une rangée `.inline`** (un nombre et son unité), une enveloppe en
  `width: 100 %` devient un élément flex de 470 px et passe à la ligne sous son
  champ. Vu à l'écran : la mise en page d'un composant se vérifie LÀ OÙ il est
  posé, pas dans l'abstrait.

###### ⚠️⚠️ On ne pouvait pas DÉFILER dedans — et l'accent était celui de la page (2026-11-14)

« C'est top, seulement on ne peut pas scroller dedans, cela le ferme direct. »

- **Le défilement.** `window.addEventListener('scroll', fermer, true)` — en
  CAPTURE, donc il voyait TOUS les défilements, **y compris celui du panneau
  lui-même**. Et pas seulement au geste de l'utilisateur : à l'ouverture d'une
  longue liste, `viser()` appelle `scrollIntoView`, qui fait défiler le panneau
  quand l'option choisie est sous le pli — le panneau se refermait donc tout
  seul, une image après s'être ouvert. Un défilement qui naît DANS le panneau
  ne le referme plus ; tout autre si, car le panneau est posé sur le body et ne
  suivrait pas son bouton.
  ⚠️ **Le `true` reste** : un événement `scroll` ne REMONTE pas, seule la phase
  de capture le voit. Le retirer débrancherait la fermeture.
  ⚠️ Et `overscroll-behavior: contain` sur le panneau : arrivé au bout de SON
  défilement, il passait la main à la page — qui défile, et le referme.
- **L'accent suit le TYPE du formulaire** (`--tms-a`, dérivé du `--tm-c` que
  pose `#tm-travail[data-analyse]`) : rouge pour une faiblesse, violet pour une
  activité, ambre pour un rôle, ardoise pour un projet. Il prenait l'accent de
  la PAGE, qui est l'ambre du rôle — donc l'un des quatre, posé sur les quatre.
  ⚠️ **Le PANNEAU est posé sur le body** : il vit hors de `#tm-travail` et
  n'hérite de rien. Le JS lui recopie la valeur CALCULÉE sur le bouton, qui est
  dedans. Mesuré : bouton et panneau à `#dc2626` dans une faiblesse, `#7c3aed`
  dans une activité, `#d97706` dans un rôle, `#64748b` dans un projet.
  ⚠️ `.tms-o.est-choisi` assombrit SUR PLACE (`color-mix`) : les quatre
  couleurs de type n'ont pas de variante profonde déclarée, et
  `--pg-accent-deep` ramènerait l'ambre de la page.

⚠️ **Un cliquet est resté vert sur le défaut même, et c'est ma déclaration qui
l'avait masqué** : `_regle(css, ".tms-p {")` tombait sur
`.tms, .tms-p { --tms-a: … }`, écrite dans le même changement et plus haut dans
la feuille. Il faut ancrer sur `".tms-p {" + saut de ligne`. *(Troisième fois
en une semaine : un cliquet qui cherche une chaîne doit borner sa zone — et
l'homonyme peut être une ligne qu'on vient d'ajouter soi-même.)*

⚠️⚠️ **Et le volet de mise au point ne tire AUCUN événement `scroll`** :
mesuré, `window.scrollY` passe bien de 0 à 150 pendant que le compteur
d'événements reste à **zéro**. Faire défiler pour éprouver la garde ne prouve
donc rien — ni dans un sens ni dans l'autre. On DÉPÊCHE l'événement à la main
(`panneau.dispatchEvent(new Event('scroll'))`), ce qui traverse la phase de
capture et éprouve exactement la garde : panneau et option → il reste ;
`document` et conteneur quelconque → il se referme. *(Même famille que les
transitions CSS figées en cours de route et que les observateurs muets, déjà
écrits plus bas.)*

##### La carte 1 : la pile revient, et la carte prend du relief

⚠️ **RÉVISION du plafond.** Il valait 24 (« au-delà, on n'ose plus compter »)
— et une carto de **45 activités**, la taille courante, n'avait donc AUCUNE
pile : juste sa phrase. C'est ce que l'utilisateur a signalé. On ne compte pas
45 carrés un par un, mais on en voit la proportion d'un coup d'œil, et c'est
ce qu'on vient y chercher. Les carrés rétrécissent avec le nombre
(`tailleCarre` : 14 → 8 px, le pas d'écart proportionnel) ; au-delà de **60**,
c'est une barre pleine largeur. Mesuré : 45 activités → carrés de 10 px, deux
rangées, aucun débordement.

**Le relief** : quatre ombres portées empilées (la lumière n'en fait pas une
seule, nette) plus deux arêtes internes — le haut éclairé, le bas dans
l'épaisseur.
⚠️ **Pas de `transform`** : il ferait de la carte le repère des descendants
`position: fixed`, et les bulles d'aide comme le panneau des listes sont posés
sur le BODY.

« Soit 10,31 équivalents temps plein » est retiré, avec ses deux clefs.

##### Le calendrier de travail n'est plus écrit en 10 px

« C'est une bonne idée de rappeler ces éléments, mais pas en tout petit sous
le titre. » Il était en 13 px — **10,4 px réels** sous le `zoom: .8` du corps.
C'est pourtant la BASE de tous les chiffres de l'écran : changez une des trois
valeurs et la page entière bouge. Trois pastilles, le chiffre dans la police
d'affichage, à côté du bouton qui les règle.

##### À quoi servait le bouton « Calendrier de travail »

Question de l'utilisateur. Il n'ouvre pas un calendrier : il mène aux
**réglages du temps de travail** (semaines / jours / heures), qui vivent dans
le bandeau de la page RH et que `get_calendar_params()` lit. Il y menait déjà,
mais sans rien désigner — d'où « il amène simplement en haut de la page RH ».
Il pointe maintenant `#calendrier`, et `rendreBandeau` fait défiler jusqu'au
bloc et l'**allume** 1,6 s.
⚠️ Un ancrage HTML ne suffisait pas : ce bandeau est construit en JS,
l'élément n'existe pas au chargement.

##### La carte 4 a un vrai état vide, la carte 5 une rampe qui s'étale

- **L'état vide du rôle** était une ligne grise de 12 px collée en haut à
  gauche d'une carte haute : on la lisait comme un défaut de chargement, et
  elle ne disait pas quoi faire. C'est un bloc — icône, phrase, et le bouton
  qui crée l'analyse.
  ⚠️ `[hidden]` est une règle du NAVIGATEUR : une classe d'auteur qui pose un
  `display` l'emporte. **Sixième fois** que ce piège se présente.
- **« Les trois premières font 79 % »** est parti : la barre le MONTRE, et la
  phrase prenait la place qui manquait à la barre et à sa légende. La clef
  part avec son seul lecteur.
- ⚠️ **La rampe S'ÉTALE sur le nombre de segments.** Figée à six teintes,
  trois activités n'en prenaient que les trois premières — trois violets
  voisins, dont on ne distinguait pas les segments. On interpole le long de la
  rampe entière : mesuré à l'écran, trois valeurs donnent `#4c1d95`,
  `#8b5cf6`, `#e9e2fd` ; six la parcourent lentement. Plus il y en a, plus le
  dégradé est progressif.

##### ⚠️ Six libellés de retour étaient écrits EN DUR, en français

Relevés en passant : les `flashFeedback` des trois formulaires portaient leur
phrase dans le code (« Analyse activité enregistrée. », « Erreur
d'enregistrement »…), et le nom par DÉFAUT d'une analyse de rôle aussi — celui
qui est ENREGISTRÉ. L'écran anglais les affichait tels quels. Sept clefs
neuves.

##### Trois pièges rencontrés, tous déjà connus

- ⚠️ **Un remplacement entre bornes CONSERVE sa borne de fin.** Un anchor
  partiel (« carte 2 · la part ») coupe donc le début de sa propre ligne : le
  `# ─────` d'un séparateur est parti ainsi, et le fichier de tests ne se
  compilait plus. On recule jusqu'au début de la ligne de la borne.
- ⚠️ **Un commentaire HTML dupliqué** par la même cause a laissé un `<!--`
  jamais fermé dans le gabarit. `test_85` l'a attrapé — c'est exactement ce
  pour quoi il existe.
- ⚠️ **Trois cliquets ne gardaient RIEN au premier essai** : l'un appelait
  l'aide `roles_de_la_carto` au lieu de regarder ce que la PAGE offre (remettre
  `Role.query.all()` dans la route le laissait vert) ; un autre comptait les
  occurrences d'une couleur au lieu des COUCHES d'ombre ; le troisième
  cherchait `new MutationObserver`, qui apparaît deux fois dans le fichier.
- ⚠️⚠️ **Et DEUX cas écrits la veille lisaient `Code/routes/time_view.py`
  comme une SOURCE** : verts ici, ROUGES à chaque exécution dans l'arbre
  d'image, compilé en bytecode. **Sixième occurrence de ce piège** — et la
  première que j'écris après l'avoir documentée. Réécrits sur le COMPORTEMENT
  (une carto jetable, `_CartoJetable`, avec 62 activités non chiffrées) plutôt
  que sautés : c'est portable, et c'est un contrôle plus fort — il mordrait
  aussi sur un plafond écrit autrement. *Un contrôle qui saute ne garde rien ;
  un contrôle réécrit sur le comportement y gagne.*

Tests : `tests/test_105_temps_refonte.py` passe de 128 à **146 cas**, plus
deux cas alignés dans `test_95` ; **32 défauts remis un par un, 32 cliquets
tombés**.
ℹ️ `test_139::test_une_note_EFFACEE_arrete_le_report` échoue, et il échouait
**déjà sur l'arbre propre** (vérifié en mettant ce travail de côté) : il est
antérieur à cette passe et reste à traiter.
Éprouvé au banc (`tools/devrun_temps.py`) à 1600 px dans les deux langues :
les chiffres exacts de la capture (2 h / 4 h / 10 h → « sort en 14,0 h au lieu
de 4,0 h », délai moyen 14,0 h, les deux enfin d'accord), le lien des unités
dans les deux sens, le panneau d'une liste à 0,0 px de son bouton, une analyse
de rôle enregistrée qui apparaît aussitôt sur l'accueil, le refus d'une
analyse vide, l'état vide, et **zéro fuite française sur l'écran anglais** sur
les cinq écrans (texte et attributs ; tout ce qui reste en français est une
DONNÉE du banc).

### Quatre retours du pilote corrigés — et trois étaient PETITS (2026-11-10)

Sur les douze points laissés ouverts le 09/11, l'utilisateur en a tranché
quatre, chacun avec la solution recommandée. Les huit autres attendent sa
réflexion ou un arbitrage avec son collègue — **ne pas y toucher**.

⚠️⚠️ **La leçon de la passe : lire le code AVANT de chiffrer.** Le 05/11
j'avais rangé les cinq demandes « éditeur » en bloc comme « du vrai travail
d'éditeur », **sans ouvrir `editor.js`**. En le lisant ligne par ligne, trois
des quatre points retenus se sont révélés petits : un défaut de mesure d'une
ligne, un panneau qui existait déjà, et deux champs numériques.

#### #25 — une largeur de texte se MESURE, et TROIS sites l'estimaient

`renderConnections` dimensionnait le fond blanc d'une étiquette de flèche à
`maxLineLen * 6` — six pixels par caractère — pour un texte rendu en
`font-size: 14`. Mesuré au navigateur : **7,94 px** en moyenne. Le fond était
donc trop étroit, et **les lettres qui dépassaient n'avaient plus rien
derrière elles : elles tombaient sur le trait**. C'est mot pour mot le
« words are getting overlapped on the line if exceed than specific length »
du pilote — l'écart grandit avec la longueur.

Mesuré sur la carto du banc : **80 étiquettes sur 83 débordaient** (pire
12,8 px de chaque côté) → **0 sur 83**.

⚠️ **Le cliquet a trouvé DEUX AUTRES sites** que celui signalé : `labelNode`
(la pop-up de placement des losanges, texte en 9,5 px) et
`setLabelsAlongArrows` — là, la largeur sert à ménager une marge aux deux
bouts de la flèche, et sous-estimée elle laisse l'étiquette glisser sur la
forme d'extrémité.

⚠️ Deux défauts de plus dans le même bloc : **aucune marge** (8 px de chaque
côté désormais — sans elle, même à la bonne largeur la première et la dernière
lettre touchent le bord), et `lineH = 13` pour une police de **14** : les deux
lignes d'une étiquette à deux lignes se chevauchaient.

ℹ️ `mesurerTexte` réutilise UN contexte de canevas. Vérifié au banc : sa
mesure et `getComputedTextLength` coïncident à **0,1 px** près — c'est ce qui
rend la méthode juste. Les deux polices de mesure DOIVENT suivre ce que le
rendu SVG écrit : une mesure faite dans une autre police ne mesure rien.

#### #19 — le texte d'une forme : trois défauts, dont un jamais signalé

1. ⚠️ `wrapText(..., maxLines = 4)` finit par `.slice(0, maxLines)` :
   **au-delà de quatre lignes, la fin du libellé disparaissait sans rien
   dire** — pas d'ellipse, pas de signal.
2. La hauteur n'était **jamais** vérifiée : `totalH` était calculé puis
   ignoré. Quatre lignes à 18 px font 95 px dans une forme de 90.
3. Aucune marge intérieure, et `0.52·w` pour un losange est la largeur **à
   mi-hauteur** : les lignes du haut et du bas sortaient sur les côtés.

`ajusterTexteForme` cherche la plus **grande** police qui tienne (de
`s.fontSize` à 10 px), en largeur ET en hauteur, et au plancher pose une
**ellipse**. `_largeurUtile` rend la largeur **par ligne** : un losange est un
quadrilatère, sa demi-largeur à la distance `dy` du centre vaut
`(w/2)·(1 − 2·dy/h)`.

Mesuré sur la même carto, 73 formes et 170 lignes :
**5 lignes trop larges (pire 34 px) → 0**, **2 piles trop hautes (21 px) → 0**,
**3 libellés tronqués en silence → 0** (une seule ellipse visible).

⚠️ **La marge est PROPORTIONNELLE** (`min(10, w·0,12, h·0,12)`) : mesuré, sur
un renvoi de 50 px, 10 px de chaque côté donnent 40 % de la forme à du vide,
et un mot courant n'y tient plus même à la police plancher.

⚠️ **On ne GROSSIT jamais** une police réglée plus petite à la main :
`plancher = Math.min(POLICE_MIN, base)`.

⚠️ **Un cache** (`_cacheForme`, clé = libellé + boîte + police + type) : la
pose est recalculée à chaque image pendant un glissé, et elle ne change pas.
Vidé au-delà de 2 000 entrées plutôt qu'invalidé à la main.

⚠️⚠️ **`getBBox()` d'un `<text>` n'est PAS sa largeur d'avance** : 52,3 px
pour un texte qui en mesure 40,1 (les glyphes débordent de leur chasse).
Mesurer un débordement avec `getBBox` fabrique des faux positifs — cinq ici,
que j'ai failli « corriger ». La bonne mesure est `getComputedTextLength`,
celle-là même que la mise en page emploie.

#### #30 — l'index des activités EXISTAIT déjà

`renderCanvasMap` construit groupes, bandes, formes triées et connexions,
chaque ligne sélectionnant la forme, la centrant et ouvrant les Propriétés ;
son conteneur `#canvas-map-list` est dans **les deux** gabarits. Il vivait
**tout en bas** du panneau gauche, après les six lignes de légende, et **sans
champ de recherche** — « like read only view », c'était ça qui manquait.

Il remonte **avant la légende** (une légende se lit une fois, un index sert à
chaque recherche de forme) et prend son champ et son compte.

⚠️ Il **masque**, il ne re-rend pas : `render()` reconstruit déjà la liste, et
la redessiner à chaque frappe ferait perdre le curseur du champ qu'on tape.
⚠️ Il écoute `input`, pas `change` : sur `change` il ne filtrerait rien
pendant la frappe, sans la moindre erreur pour le dire.
⚠️ `_filtrerIndex()` est rappelé à la fin de `renderCanvasMap` — sinon taper
puis déplacer une forme rendrait tout visible à nouveau.
⚠️ Une **section dont toutes les lignes sont masquées se masque aussi**,
sinon on lit « Formes » suivi de rien.
⚠️ `.cmap-item[hidden]` est déclaré à la main : `[hidden]` est une règle du
NAVIGATEUR, une classe d'auteur qui pose un `display` l'emporte. **Cinquième
fois** que ce piège se présente dans ce dépôt.
⚠️ Le champ existe dans les **deux** gabarits parce que `editor.js` câble sans
garde — un id absent interrompt TOUTE l'init, chargement de la carto compris
(`tests/test_49_carto_dom_contract.py`).

#### #22 — l'import NOMME ce qu'il laisse dehors

L'écran de vérification montrait déjà les compteurs et une tuile « à
rattacher », mais le bouton « Importer » n'était conditionné par **rien** : on
pouvait cliquer sans l'avoir regardée. Une confirmation nomme désormais ce qui
restera dehors — 8 activités au plus, puis « et n autres » — **avec le compte
de tâches par activité**.

⚠️ Ce compte n'est pas décoratif : « 3 tâches ne seront pas importées »
au-dessus de DEUX noms (vu au banc) ne disait pas ce qu'on lisait — les noms
sont des **activités**, pas les tâches.
⚠️ On ne **bloque** pas : refuser 60 tâches parce que 3 ne s'apparient pas
serait un recul, et l'historique, l'écran de vérification et la lecture
« dans l'autre sens » sont tous bâtis pour qu'on revienne finir.
⚠️ Seules les **tâches** ont un rattachement à faire : un rôle ou un outil n'a
pas d'activité à retrouver.
⚠️ L'**ambre** de la tuile « à rattacher », pas le rose-violet de l'IA : c'est
un avertissement, pas une proposition.

#### ⚠️ Quatre cliquets ne gardaient RIEN au premier essai

- le découpage sur bornes **retirait les commentaires AVANT** de chercher une
  borne qui EST un commentaire ;
- `"'…'" in corps` passait, parce que l'ellipse sert **aussi à mesurer** la
  place qu'elle prendra : ce qui compte est qu'elle soit **posée** sur la
  dernière ligne ;
- `"zoneH" in corps` restait vrai avec une borne remplacée (il y en a deux) :
  on exige désormais que **chaque** `Math.floor(… / …)` divise `zoneH` ;
- `"c.noms" in corps` restait vrai avec `c.noms.length`.

Tests : `tests/test_137_pilote_quatre_corrections.py` (**45 cas**) ;
**26 défauts remis un par un, 26 cliquets tombés**. `editor.js` et `style.css`
resynchronisés dans le dépôt OptiqCarto. Éprouvé au banc
(`tools/devrun_import.py`) dans les deux langues : l'index (182 éléments →
3 sur 182 → Aucun résultat), la confirmation d'import, le retour à la liste,
et l'import réel (5 tâches écrites, 3 laissées).

Suite : **3 929 passés**, 1 sauté ; `repet_image` **3 858 passés** + 72 sautés.
⚠️ Un rouge en chemin, **sans rapport** : `test_61_pulse::test_summarize_daily_and_pages`
rougit entre 00:00 et ~00:08 à Paris. Sa fixture sème à `now(utc) − 1/6/8 min` et
`aggregates.summarize` range les journées en heure de PARIS : les événements tombent
alors dans la veille alors que `today = daily[-1]` est la nouvelle journée. Il passe
seul (16/16) et la passe suivante est verte. Correctif d'une ligne, non fait ici :
caler le `NOW` de la fixture en milieu de journée plutôt qu'à l'heure réelle.

---

### L'AXE PARTAGÉ et l'HISTORIQUE DES NOTES (2026-11-10)

« Cette différence entre une activité pas encore notée et une activité qui a
déjà au moins une note : c'est une belle idée mais pas une bonne, c'est trop
brouillon. » Le reproche portait sur une vraie fracture du code :
`carteSortie` aiguillait vers DEUX cartes qui n'avaient rien en commun —
`resultCard` (la FICHE, fond de nuit, deux échelles 0→4) pour une sortie jugée
à la main, `carteMesuree` (le rail des paliers, le relief, les formulaires)
pour une sortie mesurée. Empilées, elles donnaient un écran sans ligne de
lecture.

**Tranché sur PROTOTYPE, pas dans le code** — quatre propositions écrites
directement dans l'app avaient été refusées l'une après l'autre. La cinquième
est passée par un artefact cliquable à l'échelle réelle, repris en quatre
versions. C'est la méthode pour tout ce qui se juge en trois secondes, et
c'est la sixième fois qu'elle évite une journée écrite pour rien.

#### Ce que l'écran montre

- **UNE rangée par sortie**, la même graduation, la même **zone attendue**.
  La différence entre les deux régimes se lit DANS la piste, plus dans la mise
  en page : une sortie notée porte sa barre, une sortie pas encore notée porte
  une hachure ambre.
- **La zone attendue est une SURFACE**, pas un trait : « la barre doit entrer
  dans le vert » se regarde, un filet de 2 px se cherche. Elle court d'une
  rangée à l'autre, donc elle se lit comme UNE bande.
  ⚠️ Et il n'y en a pas quand le rôle n'a fixé aucun requis : NULL ≠ 0, une
  bande posée à 0 dirait que tout est au niveau.
- **Le DÉTAIL s'ouvre à la demande**, une sortie à la fois, sous l'axe. Il
  porte `carteSortie(r)` TEL QUEL : le rail des paliers, le relief en unités
  réelles, les formulaires, la preuve, la fiche de notation du 16/10. Rien
  n'est perdu — c'était l'empilement qu'on reprochait à l'écran, pas le
  contenu.
- **L'historique des notes**, carte nouvelle : une courbe par sortie, plus la
  courbe du **niveau de l'activité**.

#### ⚠️ Les décisions qui ont coûté quelque chose

- ⚠️ **UNE source pour la note : `state.saisie`.** La piste de l'axe ET
  l'échelle du détail posent la MÊME note. `saveEvaluation` lisait le DOM de
  l'échelle (`.cv2-nt.is-mienne [data-lv].sel`) ; deux contrôles qui écrivent
  chacun dans leur coin finissent par se contredire. Les deux écrivent donc
  dans `state.saisie`, et c'est elle qu'on enregistre.
- ⚠️⚠️ **La PREUVE part toujours avec la note.** `/mastery/evaluate` fait
  `(evidence or "").strip() or None` : une note enregistrée sans elle EFFACE
  la preuve en base. Poser un niveau depuis la piste — où il n'y a pas de
  champ de preuve — aurait suffi à perdre ce que quelqu'un avait écrit.
  `poserNote` emporte donc la preuve existante.
- ⚠️ **Le NUMÉRO relie les deux cartes.** « On ne comprend pas bien que les
  différents points sont les niveaux des sorties individuellement » : la
  rangée porte son numéro, et c'est le même qui termine SA courbe dans
  l'historique. Sans lui, deux sorties du même état ont la même couleur et
  rien ne les distingue.
- ⚠️ **Les pastilles blanches des paliers franchis sont RETIRÉES** de la
  piste. Elles posaient l'historique SUR la barre — à l'endroit où l'on vient
  lire une seule chose : le niveau tenu aujourd'hui.
- **DES RAMPES, PAS DEUX TEINTES.** Une famille n'est pas « un clair et un
  foncé » : c'est une rampe dont la TEINTE DÉRIVE (le bleu part du ciel et
  finit en indigo, le vert finit en émeraude). Le niveau monte DANS la rampe,
  et le grand chiffre porte la même marche que sa barre.
  ⚠️ Aucune règle neuve ne lit `--pg-accent-soft` ni ses trois frères : ils
  sont déclarés sur `:root`, où `--pg-accent` vaut encore le gris par défaut,
  et rendent donc du GRIS. Les mélanges sont écrits SUR PLACE.
- ⚠️ **La piste ne peint PAS le vert** : elle s'arrête à `--xr` et laisse
  passer la bande. Peinte des deux côtés, le même dégradé ne tombait pas au
  même endroit (la bande est plus large que la piste) — on voyait une couture,
  et le bout arrondi de la piste ressortait comme un défaut. Même raison pour
  la hachure d'une sortie non notée : opaque sur toute la largeur, elle
  recouvrait la bande, qui s'interrompait sur cette rangée-là.
- ⚠️ **La norme de l'entreprise porte son relevé DEDANS** (`≤ 48 h → 46 h`,
  le relevé à la couleur de son verdict). Trois lignes grises de « mesuré 46 h
  le 12 oct. » ont disparu, et la comparaison se VOIT au lieu de se lire.
  Trois états : **posée** (ardoise gravée), **lue** dans la fiche de l'activité
  mais pas reprise ici (creuse + « à reprendre »), **sans norme chiffrée**
  (c'est le repère écrit qui en tient lieu).

#### L'historique — `Code/historique_notes.py` + `GET /mastery/historique/<u>/<a>`

⚠️⚠️ **DEUX RÉGIMES, DEUX PROFONDEURS D'HISTORIQUE, et c'est une limite de
STRUCTURE, pas d'affichage :**

- une sortie **MESURÉE** garde tout. Chaque palier est une ligne qui porte sa
  cible et son échéance avant, sa mesure et son verdict après — c'est ce qui
  en fait un point d'historique. ⚠️ Mais un palier ne stocke PAS de niveau :
  le niveau de chaque date se **RECALCULE** depuis la mesure, avec les seuils
  d'aujourd'hui (la norme ne change pas rétroactivement de sens) ;
- une sortie **JUGÉE À LA MAIN n'a qu'UN point**. `/mastery/evaluate` fait un
  upsert sur (collaborateur, activité, sortie, évaluateur) : la note
  précédente est ÉCRASÉE, et seule sa date survit. Sa « courbe » est un point.
  L'écran le dit (`une_seule_note`, derrière un « i ») au lieu de laisser
  croire à une progression qu'on n'a pas gardée.
  **Le correctif de fond demanderait une table d'historique en AJOUT SEUL** —
  c'est un changement de schéma, il se décide, il ne se glisse pas ici.

⚠️ **LA COURBE GLOBALE n'existe QUE là où TOUTES les sorties portent une
note** — c'est la règle du module (le MINIMUM, et NULL tant qu'il en manque
une). Le grand chiffre de l'écran dit « — » au même moment ; la frise ne doit
pas inventer un niveau que la carte du dessus refuse d'afficher.
⚠️ Et le niveau d'une sortie **SE CONSERVE** d'une date à l'autre : il vaut
jusqu'à la note suivante. Sans ce report, la colonne du jour ne portait que la
sortie qu'on venait de noter — la globale sautait à SA valeur, et elle
annonçait **4 pour une activité qui vaut 2**, à deux centimètres du grand
chiffre qui disait 2. Vu sur capture, pas déduit.
⚠️ La globale se dessine **SOUS** les courbes : là où elle en rejoint une, on
voit la plus basse portée par un large ruban. La règle du minimum se regarde
au lieu de s'écrire.
⚠️ **Un SEGMENT porte l'état de son point d'ARRIVÉE** : une courbe qui passe
de 1 à 3 change de famille en chemin, là où elle franchit l'attendu. D'une
seule couleur, elle disait que la sortie avait toujours été au niveau.
⚠️ La route se lit avec la MÊME porte que `/mastery/activity` (`peut_lire`) :
elle porte les niveaux d'une personne et jusqu'aux mesures relevées en séance.
Une route d'historique laissée ouverte rouvrirait par la bande ce que
`/mastery/activity` vient de fermer.

#### Deux pièges déjà connus, revus ici

- ⚠️ **Un SVG en `width:100%` rapetisse ses TEXTES** avec lui, et la taille
  calculée reste celle du repère du viewBox — la mesure ne le voit pas. Le
  viewBox est taillé sur la place disponible (une unité = un pixel) ; sous la
  largeur minimale, c'est la frise qui défile, pas la page.
- ⚠️ **La seconde lecture ne retient PAS le rendu.** La carte d'historique
  part vide, se remplit quand la réponse arrive, et se **retire** si elle
  n'arrive pas. C'est la leçon de `/panel`, qui retenait son HTML le temps
  d'un appel inter-services et annonçait ensuite une panne.
- ⚠️ **Dix dates en « 07/10/2026 » se chevauchent** : l'axe porte une date
  courte, la date entière reste dans l'info-bulle du point.

Tests : `tests/test_139_historique_notes.py` (11 cas — le niveau recalculé,
l'unique point d'une sortie jugée à la main, la règle de complétude, le
report, la porte) et `tests/test_140_axe_partage.py` (15 cas). **Dix défauts
remis un par un, dix cliquets tombés.** `test_109` voit cinq de ses cas
réécrits : ils affirmaient la structure d'avant (les cartes empilées, le DOM
scruté à l'enregistrement, l'unique aller-retour). Suite : **3961 passés**,
1 sauté. Éprouvé au banc (`tools/devrun_competences.py`) à 1600 px dans les
deux langues : axe, détail ouvert, historique, et **zéro fuite française sur
l'écran anglais** — 81 textes relevés, attributs et SVG compris.

---

#### Ce qui manquait dans la BASE, et qui est comblé (2026-11-10, suite)

Les quatre limites relevées en livrant l'axe partagé tenaient à la structure,
pas à l'écran. Trois sont des changements de schéma, la quatrième un contrat
de route. Tout est en place.

**1 · `NoteEvaluation` — le REGISTRE des notes posées à la main, en ajout
seul** (table `notes_evaluation`). `CompetencyEvaluation` porte UNE ligne par
(collaborateur, activité, sortie, évaluateur) et `/mastery/evaluate` l'écrase
à chaque enregistrement : la note précédente disparaissait, seule sa date
survivait, et la courbe d'une sortie jugée à la main se réduisait à un point.
Un ÉVÉNEMENT par écriture est désormais ajouté, dans la MÊME transaction —
un état courant sans son événement serait un trou dans l'historique.
- ⚠️ **On COMPLÈTE, on ne remplace pas.** L'état courant reste dans
  `CompetencyEvaluation`, lu partout (tableaux RH, synthèse, diagnostic,
  plan) ; l'histoire vit dans le registre, lue par la seule frise. Un
  registre qu'on relirait pour connaître l'état courant coûterait un balayage
  à chaque ligne de chaque tableau.
- ⚠️ **`niveau` NULL est un vrai événement** : c'est l'effacement d'une note.
  La frise ne le dessine pas — il n'y a pas de point à tracer — mais il DATE
  la fin du report. Sans lui, une note retirée continuerait de peser sur le
  niveau de l'activité.
- ⚠️ **Deux écritures le MÊME jour ne font qu'un point** : c'est l'état du
  jour qui compte, donc la dernière. Sinon la courbe rebrousserait chemin sur
  une abscisse unique. À égalité de jour, un événement posé à la main
  l'emporte sur un palier — c'est la règle de `activity_mastery`, où
  l'expertise posée gagne sur la déduction.
- ⚠️ **Pas de filtre de rôle à la lecture** : une note vaut pour
  (collaborateur, activité, sortie, évaluateur), exactement comme la ligne
  d'état courant. Filtrer sur le rôle ferait disparaître l'historique d'une
  personne qui change de rôle.

**2 · `PalierPerformance.niveau_atteint` — le verdict du jour, FIGÉ.**
Il se déduisait de la mesure à chaque lecture, avec les seuils
d'AUJOURD'HUI : poser plus tard une marche au-delà de la norme relisait tout
le passé avec la nouvelle frontière, et l'historique changeait
rétroactivement sans que personne n'ait rien touché. Mesuré : sur
96 → 72 → 48 (la norme), une mesure de 30 h vaut 2 ; poser ensuite une marche
à 36 h faisait dire **3** à la déduction pour la même journée. `trancher()`
enregistre désormais le niveau comme il enregistre la mesure.
⚠️ La déduction reste en REPLI pour les lignes tranchées avant la colonne :
sans elle, tout l'historique déjà en base tomberait d'un coup.

**3 · `/mastery/evaluate` ne touche à `evidence` que si la clé est ENVOYÉE.**
Elle faisait `(evidence or "").strip() or None` sur une clé absente : une
note enregistrée sans preuve effaçait celle qui était en base. Poser un
niveau depuis la piste de l'axe — où il n'y a pas de champ de preuve —
suffisait à perdre ce que quelqu'un avait écrit. L'écran n'a plus à la
trimballer avec chaque note : il ne l'envoie que s'il l'a touchée.

**4 · `reprendre_notes_existantes()` — la reprise, UNE fois.**
Les notes déjà en base n'ont aucun événement : sans reprise, la frise
perdrait le seul point qu'elle savait montrer. Ces lignes portent
`source='reprise'` — on ne présente pas une recopie comme une note qu'on
aurait vue poser ce jour-là, et c'est ce qui permet à l'écran de dire **d'où
part l'historique** (`avant_registre`, derrière un « i »). La mention
disparaît d'elle-même dès qu'une note est posée après.
⚠️ Le marqueur (`notes_evaluation_reprise`) vit en BASE, pas en mémoire : une
instance qui redémarre, se duplique ou se redéploie doit lire la même
réponse. Rejouée à chaque démarrage, la reprise ajouterait une ligne de plus
à chaque fois. `force=True` la rejoue, et elle reste idempotente.

ℹ️ **Ce qui n'a PAS été touché** : les deux notions de « requis » qui
cohabitent — `activity_roles.required_mastery_level` (par activité × rôle,
celui que l'axe dessine) et `result_capability_links.required_level` (par
capacité, lu par le diagnostic). Ce n'est pas un manque de sauvegarde, c'est
une question de modèle : elle se tranche en regardant les deux écrans.

Tests : `test_139` passe de 11 à **22 cas**, et **neuf défauts remis un par
un, neuf cliquets tombés** (le registre débranché, la preuve écrasée, le
niveau non figé, le figé ignoré, l'effacement qui ne coupe plus le report,
les deux écritures du même jour, la reprise sans garde, `avant_registre`
vidé, la preuve renvoyée à chaque note). Éprouvé au banc de bout en bout :
deux notes posées d'affilée, la courbe gagne son point et le niveau suit.

---

### LE CLASSEUR — l'écran d'évaluation, et les courbes en fenêtre (2026-11-11)

« Le seul truc sympa de la page c'est le bandeau. » Trois passes avaient été
refusées l'une après l'autre (« hideux », « ça ne m'en met pas plein les
yeux », « les notes ne sont vraiment pas au niveau »). La quatrième est passée
par un **prototype cliquable à l'échelle réelle**, repris en quatre versions —
la méthode pour tout ce qui se juge en trois secondes, et la septième fois
qu'elle évite une journée écrite pour rien.

**Ce qui était reproché, mesuré avant d'être corrigé :**

| | avant | après |
|---|---|---|
| surfaces à l'écran | 12 | **4** |
| familles de couleur | 6 (bleu, vert, ambre, teal, violet, rouge) | **3** |
| crans de notation | 10 (deux échelles) | **5** (une piste) |
| sections de courbes dans l'écran de note | 2 | **0** |
| colonne de droite redisant les sorties | 1 | 0 |
| hauteur | 721 à 1 070 px pour la seule colonne de travail | **395 à 446 px** en tout |

#### Trois surfaces, trois rôles — l'inversion STRUCTURE, elle ne décore pas

**NUIT** = qui on regarde (le bandeau, **inchangé** : c'est le morceau qui
tient). **BLEU** = le résultat — la bande du classeur, son nom d'activité en
Fraunces 28 px, le niveau tenu en 50 px, et les **languettes découpées dans
son bord bas**. **ARDOISE** = ce qui est DONNÉ et ne se règle pas ici : la
norme de l'entreprise, le repère de réussite, gravés.

⚠️ **Bande + languettes + feuille ne font qu'UN objet** : un rayon, une ombre,
un `overflow: hidden`. Trois cartes empilées, c'étaient trois contours pour un
seul sujet — et c'est l'empilement qu'on reprochait à l'écran.

#### Les LANGUETTES portent la comparaison

C'est ce qui manquait au premier jet : un onglet portait un chiffre de 23 px
et rien d'autre. Chaque languette porte **sa jauge en quatre pas et le trait
de l'attendu** — la convention de toute l'application — plus son numéro et son
régime (« mesurée · 5 j », « jugée à la main », « rien encore »). On compare
les sorties sans ouvrir quoi que ce soit : c'est l'axe partagé du 10/11, rangé
là où il ne coûte plus une section.
- ⚠️ **Pas de largeur maximale** : relevé SUR CAPTURE, un plafond de 420 px
  laissait un grand vide bleu à droite de la bande dès qu'il n'y avait que
  deux sorties. Elles remplissent la bande ; sous 212 px elles défilent dedans.
- ⚠️ **La sortie ouverte survit au re-rendu** (`sortieOuverte`) : sinon toute
  note posée ramènerait à la première.

#### UNE piste, cinq marches

Le niveau qui fait foi **EST** la piste, et ce qu'il dit de lui-même est un
repère **sur** cette piste. Avant : deux échelles de cinq crans l'une sous
l'autre, la distinction portée par la seule couleur.
- ⚠️ **Le 0 ne se remplit JAMAIS** — « non démontré », c'est une jauge vide.
  Posé, il porte un anneau : sinon rien ne distinguerait « 0 » de « rien ».
- ⚠️ **La zone attendue est une SURFACE**, pas un trait : « la barre doit
  entrer dans le vert » se regarde, un filet de 2 px se cherche. Et NULL ≠ 0 :
  sans requis, pas de zone.
- ⚠️ **La gomme vit HORS des crans** (`.crans` l'exclut) : effacer n'est pas un
  niveau de plus, et la zone attendue ne doit pas l'englober — elle aurait
  l'air d'un sixième cran.
- ⚠️ **Une sortie mesurée se LIT** (`.piste.lue`) : son niveau vient du chiffre
  relevé en séance. L'auto-évaluation, elle, reste toujours permise — c'est un
  repère que le collaborateur se donne.
- ⚠️ **Un cran ne porte que son chiffre** ; le nom du palier vient au survol
  après une demi-seconde. **Pas d'attribut `title`** : l'info-bulle du système
  sortirait par-dessus la nôtre, une seconde plus tard et sans sa couleur.
- ⚠️ **La mise à jour se fait SUR PLACE** (`majNota`, `majLanguette`) :
  réécrire la piste ferait perdre le focus du cran qu'on vient de cliquer et
  couperait la transition de la marche qui se remplit — c'est elle qui fait
  comprendre le geste.

#### LES COURBES quittent la page — une fenêtre, DEUX schémas

« Mettre les courbes à part dans un truc qu'on peut ouvrir, pour différencier
les deux ; on mettrait donc ici toutes les courbes, avec deux types de schémas
différents. » Les deux vivaient dans l'écran où l'on NOTE, l'une sous l'autre.

`#cv2-crb-win` (`ouvrirCourbes`) porte les deux, choisis par **languettes** —
la même grammaire que le classeur, parce que c'est le même geste (choisir ce
qu'on regarde) :
- **LES NIVEAUX** — la frise : une ligne par sortie, de 0 à 4, plus celle de
  l'activité (le plus bas des sorties). On compare les sorties ENTRE ELLES, ce
  que seule une échelle commune permet ;
- **LES VALEURS** — le relief d'UNE sortie mesurée, dans son unité réelle,
  avec sa norme et ses marches. On ne compare plus, on suit une progression.

Le **détail des séances** les accompagne : la feuille dit l'ÉTAT, la fenêtre
dit l'HISTOIRE.
- ⚠️ **L'historique ne se charge QUE là, et une fois** : il ne pèse plus du
  tout sur l'ouverture d'une activité, où personne ne l'avait demandé.
- ⚠️ **UNE seule porte**, et elle est sur la bande. Relevé sur capture : le
  bouton s'affichait des DEUX côtés sur une sortie mesurée — c'est la faute
  que mon propre commentaire annonçait.
- ⚠️ **Sans sortie mesurée, la languette « Les valeurs » le DIT** au lieu
  d'ouvrir un écran vide ; et le sélecteur de sortie n'existe que s'il y a de
  quoi choisir — une rangée d'un seul bouton est un titre déguisé.
- ⚠️ **Le voile est partagé par les TROIS fenêtres** (tiroir, plan, courbes) :
  le retirer dès qu'une se ferme laisserait les deux autres posées sur la
  page, sans voile et sans clic pour en sortir.
- ⚠️ `basculerHisto` s'accrochait à `.pal-pied`, qui n'existe plus : un
  `querySelector` qui rend `null` aurait coupé toute la suite sans rien dire.
  Il vise `.pal-bilan`, avec un repli.

#### Ce qui quitte la page avec elles

- **La colonne de droite** : elle redisait les sorties mot pour mot. Ses deux
  réglages deviennent des **pastilles de verre sur la bande** — la technicité
  (qui ouvre le tiroir, comme les deux autres dialogues courts) et la
  prochaine séance, en ambre.
  ⚠️ **UNE source pour les domaines** (`state.tech`) : la pastille et le
  dialogue la relisent tous deux, deux chargements finiraient par afficher
  deux comptes du même réglage.
- **Le rail des activités** passe à l'horizontale : 218 px rendus à la largeur
  de ce qu'on vient lire, pour une liste qu'on parcourt une fois. Des
  pastilles posées sur le papier, pas une carte — un contour autour de six
  boutons, c'était un contour pour rien. Le bandeau de situation le suit : il
  FILTRE, il reste donc avec ce qu'il résume.
- **830 lignes de CSS mort** (`.cv2-axe`, `.cv2-rg`, `.fi-*`, `.cv2-nt*`,
  `.pal-tete/-corps/-pied`, `.ev-ctx`, `.ev-acts`…). ⚠️ Retirées par un
  découpage de RÈGLES, pas par un motif de texte : une règle partagée —
  `.cv2-axe, .cv2-histo, .cv2-det { --ax-… }` — perd ses sélecteurs morts et
  garde le vivant, car la frise lit encore ces jetons.

#### ⚠️⚠️ `perl -0pi` a mis tout `competences.css` en MOJIBAKE

Une substitution d'une ligne, et les 4 386 lignes du fichier sont ressorties
en « Page CompÃ©tences » : sans `-CSD`, perl relit les octets en latin-1 et
réécrit en UTF-8. Restauré depuis git, refait en Python avec l'encodage dit
explicitement. **Ne jamais employer `perl -0pi` sur un fichier de ce dépôt.**

⚠️ Et **le heredoc du shell avale les backticks** — troisième et quatrième
fois dans ce dépôt le même jour : un `bash -c '... <<"EOF" ...'` dont le
contenu Python porte des gabarits JS (`` ` ``) les évalue comme des
substitutions de commande. Passer par un fichier.

#### Deux pièges déjà connus, revus ici

- ⚠️ **Une vieille règle `.piste { height: 36px }`** (la piste de la rangée de
  l'axe partagé) écrasait la neuve : les crans de 76 px débordaient d'une
  boîte de 36. Toute refonte qui reprend un nom de classe doit vérifier qu'il
  n'existe pas plus haut dans la feuille.
- ⚠️ **`.ev-corps` gardait `align-items: start`** de sa grille à trois
  colonnes : en flex-column, le classeur se dimensionnait à son contenu et
  faisait 196 px de moins que le bandeau au-dessus. Remplacer un `display` ne
  suffit pas — la règle entière part.
- ⚠️ **Le cliquet des chevrons français s'est attrapé sur le commentaire qui
  l'explique** : sixième occurrence. Les commentaires se retirent avant de
  chercher, en CSS comme en JS.
- ⚠️⚠️ **Le repère d'auto-évaluation VOLAIT le clic du cran qu'il désigne.**
  Posé par-dessus les crans (`z-index: 2`), il tombe pile au milieu de l'un
  d'eux : ce cran-là ne se posait plus, et rien ne le disait. Trouvé au banc
  en rejouant le parcours complet — noter, enregistrer, **recharger la page**,
  relire — pas à l'œil. `pointer-events: none`, la règle déjà écrite pour la
  bulle de la matrice RH : ce qui explique ne vole jamais le clic de ce qu'il
  explique. Vérifié ensuite de bout en bout : niveau 2 et preuve relus après
  rechargement.

Tests : `tests/test_140_classeur_evaluation.py` (46 cas, **15 défauts remis un
par un, 15 cliquets tombés**) ; `test_109` voit **quatorze de ses cas
réécrits** et `TestLaFicheDeNotation` retirée — ils affirmaient la structure
d'avant, et un cas qui affirme une structure remplacée ne garde plus rien.
Éprouvé au banc (`tools/devrun_competences.py`) de 1280 à 1600 px dans les
deux langues : les deux régimes de sortie, la fenêtre et ses deux schémas, le
détail des séances, le dialogue de technicité — **zéro fuite française sur
l'écran anglais** (119 textes relevés, attributs compris), zéro clé brute,
zéro erreur console, aucun débordement horizontal.

#### Ce qui était dit DEUX FOIS, le 0 qui se remplit, et la frise d'un autre (2026-11-11)

Quatre libellés, une règle renversée, et un défaut qui montrait les données de
quelqu'un d'autre.

**Quatre libellés disaient ce qu'un autre élément montrait déjà**, souvent plus
gros et à deux centimètres :
- « 2 activités évaluées sur 2 » (bandeau nuit) — le rail des activités porte
  déjà le compte ET l'état de chacune ;
- « Maîtrise étendue · le minimum de ses 2 sorties » (bande du classeur) —
  redisait le grand chiffre juste au-dessus et la règle que le « i » explique.
  La bande ne garde que **ce qui reste à noter**, la seule chose actionnable ;
- « La norme est atteinte. Seule l'expertise se pose à la main. » — la piste
  est verte et la pastille dit « qualifié ». ⚠️ `nota_mes_ko` RESTE : il dit ce
  qui FERA monter le niveau ;
- la tuile verte **« Niveau tenu »** du bandeau de situation — elle se
  confondait avec le NIVEAU TENU de l'activité, juste en dessous et bien plus
  gros : deux chiffres du même nom qui ne comptent pas la même chose. Les trois
  autres disent ce qui RESTE à faire.

Les clés devenues mortes (`ev_evaluees`, `nota_mes_ok`, `cl_min_1`, `cl_min_n`)
quittent le catalogue — vérifié qu'aucune n'est construite par concaténation.

#### ⚠️ RENVERSEMENT : le 0 se remplit comme les autres

La règle du 11/11 (« le 0 ne se REMPLIT jamais : non démontré, c'est une jauge
vide ») venait de la jauge à **quatre pas**, où le niveau 0 est bien une jauge
vide. Sur une piste qui porte un cran « 0 », elle laissait un trou blanc à
gauche d'une barre qui part à 1 — on le lisait comme un défaut, pas comme un
sens.

La distinction **NULL ≠ 0 tient toujours, et mieux** : rien de posé, rien de
rempli ; 0 posé, le seul cran 0. Un cran plein se voit de loin, un anneau se
cherche — `.cran.zero` disparaît avec sa règle.

#### La pastille dit QUEL niveau on vient de poser

Un cran rempli ne dit pas lequel on a choisi : il fallait lire le mot à l'autre
bout de la ligne. La pastille se pose **sur son cran**, avec son bec, à la
couleur de la marche (bleu, vert dès l'attendu atteint).
- ⚠️ `pointer-events: none` — ce qui explique ne vole jamais le clic de ce
  qu'il explique. La règle était déjà écrite pour la bulle de la matrice RH, et
  payée la veille sur le repère d'auto-évaluation.
- ⚠️ Elle **se DÉPLACE**, elle ne se redessine pas ailleurs : deux pastilles sur
  la même piste diraient deux niveaux.
- ⚠️ **L'auto-évaluation passe SOUS la piste**, point et libellé : le dessus est
  pris, et les deux tombent sur le même cran dès qu'on se situe là où l'on est
  noté — c'est-à-dire le cas courant. Ce qui fait foi au-dessus, ce qu'on se dit
  en dessous : on sait toujours lequel on lit.
- ⚠️ Mesuré : à 28 px de marge, la pastille mordait de **4 px** sur la ligne
  d'en-tête. 42 px au-dessus, 26 px en dessous.

#### ⚠️⚠️ « Les niveaux : aucune note posée, peu importe le collaborateur »

Le reproche visait un vrai défaut, et le banc l'a montré **pire que signalé** :
`crb.histo` ne portait **aucune clé**. Ouvert une fois, il restait affiché pour
TOUTE autre personne et toute autre activité — mesuré : **Lina et Theo lisaient
la frise de Noe**, au mot près. Et là où le premier historique était vide, tout
le reste l'était aussi : c'est le « aucune note posée » signalé, vu de l'autre
côté.

Le cache porte désormais `cle = cible/activité/rôle`. ⚠️ Et `crb.sortie` (la
sortie retenue pour le relief) est remise à zéro quand la clé change : gardée
d'une activité à l'autre, elle ne s'y retrouve pas et le sélecteur s'ouvrait sur
la mauvaise.

Mesuré après, sans recharger la page entre les trois : Noe sa frise, Lina et
Theo « aucune note » — chacun pour ses propres données.

Tests : `tests/test_140_classeur_evaluation.py` passe de 46 à **53 cas** ;
**13 défauts remis un par un, 13 cliquets tombés**. `test_109` voit l'ancre de
son cas sur le cache suivre. Éprouvé au banc dans les deux langues : zéro
chevauchement de la pastille, zéro erreur console, zéro débordement, et les
trois collaborateurs lus d'affilée sans rechargement.

#### Le rail s'en va, les flèches arrivent — et trois surfaces de moins (2026-11-11)

Cinq retouches sur le classeur livré le matin même, chacune mesurée avant
d'être faite.

**1 · L'ardoise porte le fond de l'EN-TÊTE.** Elle avait ses deux bleus à elle
(`--ard1` / `--ard2`, un dégradé à 100°) quand l'en-tête d'identité en a trois
à 118° : deux surfaces sombres de deux bleus différents sur le même écran se
lisent comme un défaut d'impression. ⚠️ Ce sont DEUX déclarations — l'en-tête
écrit son dégradé, l'ardoise lit le jeton `--nuit` — donc un cliquet compare
les deux : sinon l'une changerait sans l'autre.

**2 · Le RAIL des activités est remplacé par deux flèches sur la bande.** Une
ligne de pastilles au-dessus du classeur, pour une liste qu'on parcourt une
fois : une surface de plus pour un geste qu'on fait deux fois. On change
d'activité là où on lit son nom, à droite du niveau tenu.

- ⚠️ **Une flèche qui ne mène nulle part n'est pas un bouton** : la gauche
  n'existe que passé la première activité, la droite que tant qu'il en reste
  une. Et sous deux activités, pas de navigation du tout.
- ⚠️ Le compte **« 2 / 6 »** entre les deux remplace le « 6 activités » que
  portait le rail : sans lui, rien ne dirait qu'il y en a d'autres.
- ⚠️ L'info-bulle de chaque flèche **nomme l'activité visée** : une flèche nue
  ne dit même pas comment s'appelle celle d'à côté.
- ⚠️ **Le classeur GLISSE** — le sortant s'efface, le neuf entre du côté d'où
  l'on vient. Sans mouvement, changer d'activité se lit comme un rechargement
  de page. On ne passe donc PAS par l'attente : `showBusy` remplacerait le
  classeur par une roue, ce qui couperait le glissé. Et un échec réseau rend
  le classeur tel qu'il était, plutôt qu'un écran à moitié sorti.
- ⚠️ La classe d'animation est retirée à `animationend` : un
  `animation-fill-mode: both` laisse son `transform` appliqué, et un élément
  transformé devient le repère des descendants `position: fixed` — le piège
  déjà payé sur la fiche d'examen de l'éditeur.
- ⚠️ **Les quatre tuiles de filtre sont parties avec le rail** : un filtre qui
  n'a plus de liste à filtrer ne filtre rien. Le bandeau de situation de la
  VUE D'ENSEMBLE (`renderBilan`) n'est pas touché — c'est un autre écran, et
  il garde ses quatre tuiles.

**3 · `nota-k` et `nota-d` sont supprimés.** Le premier annonçait le régime
(« Le niveau vient de la mesure · rien à poser ») et redisait l'attendu, que
la zone verte de la piste DESSINE ; le second écrivait le niveau en 52 px —
une TROISIÈME fois, après la languette et la bande. Ne reste que ce qui n'est
écrit nulle part ailleurs : la piste, et **le verdict d'accord**, qui parle de
l'ÉCART entre les deux notes et se lit à côté d'elles. Sept clés quittent le
catalogue (`nota_foi`, `nota_mes`, `nota_vous`, `nota_vous_auto`, `nota_rien`,
`nota_att`, `nota_cette`).

- ⚠️ **L'échelle 0 → 4 se range au bout de SA piste** : son explication vivait
  dans l'en-tête parti. C'est le motif de la maison — une phrase passe derrière
  un « i », elle ne disparaît pas.
- ⚠️ **La piste est BORNÉE** (780 px) : cinq crans étalés sur les 1 700 px de
  la feuille ne sont plus une échelle, ce sont cinq panneaux.

**4 · Un seul vocabulaire de boutons.** Trois formes cohabitaient sur le même
écran : des PILULES à pastille ronde (l'en-tête, les formulaires), des
RECTANGLES arrondis à icône nue (la bande, l'ardoise), et le bouton de retour,
qui dessinait son chevron en SVG — il ne pouvait donc pas recevoir la pastille
des autres. Une seule grammaire désormais, celle déjà tranchée sur la page
Temps : **tout ce qui AGIT est une pilule**, son icône porte une pastille ronde
dès qu'il y a un libellé, et le bouton EST un disque quand il n'y en a pas (les
flèches de navigation).
⚠️ **Les CRANS n'en sont pas.** Ce sont les graduations d'une échelle, pas des
actions : ils gardent leur rectangle — une règle se lit, elle ne s'actionne pas
— et ne reçoivent du vocabulaire commun que le SOIN (relief, ombre colorée sous
la marche qui porte le niveau, légère levée au survol), jamais la forme.

**5 · Et la bulle d'un « i » se posait SUR son propre bouton.** Mesuré au banc :
son bas tombait **18 px sous le haut du « i »** (31 px pour celui du niveau
tenu), c'est-à-dire par-dessus ce qu'elle explique. ⚠️
`getBoundingClientRect()` rend DÉJÀ des pixels d'écran — le `zoom: .8` du corps
y est appliqué ; seules les coordonnées qu'on ÉCRIT repassent par lui.
`brancherInfo` multipliait pourtant la hauteur par le zoom avant de la
soustraire. **C'est exactement le correctif appliqué à la page Temps le 08/11,
resté à faire ici — alors que c'est d'ICI que le motif y avait été recopié.**
Mesuré après : 8 px au-dessus et zéro chevauchement, des deux côtés.

Tests : `tests/test_140_classeur_evaluation.py` passe à **65 cas**, plus un cas
réécrit dans `test_109` ; **21 défauts remis un par un, 21 cliquets tombés**.
Éprouvé au banc (`tools/devrun_competences.py`) à 1280 et 1600 px dans les deux
langues : les deux régimes de sortie, les flèches dans les deux sens, le
glissé, et l'enregistrement **relu après rechargement** (niveau 2 reposé,
retrouvé) — zéro erreur console, zéro débordement horizontal, zéro fuite
française sur l'écran anglais.

**Reste à faire** : 73 clés de catalogue ne sont plus lues (quatre sont
parties le 11/11 au soir avec les libellés qu elles portaient ; dont une
cinquantaine orphelines depuis cette refonte — `ax_*`, `fi_*`, `n_*`,
`ev_col_*`). Elles ne coûtent rien à l'exécution et une clé retirée à tort
s'affiche TELLE QUELLE à l'écran sans rien lever : le ménage se fait à part,
en vérifiant qu'aucune n'est construite par concaténation. Les sept clés
`nota_*` du bloc supprimé ci-dessus, elles, ont quitté le catalogue avec lui —
une clé qu'on retire en même temps que son seul lecteur ne laisse rien
derrière elle.

---

### « OÙ VOUS ÊTES » : le bassin, et les DEUX notes (2026-11-14)

Tranché sur maquettes à l'échelle réelle — trois organisations dessinées, une
retenue — avant d'écrire une ligne. C'est la neuvième fois que la méthode
évite une journée écrite pour rien.

#### ⚠️⚠️ Il y a TOUJOURS deux notes, et on n'en voyait plus qu'une

« Il manque quand même quelque chose : il y a toujours deux notes, celle
d'auto-évaluation par l'user et celle du responsable. » Exact, et c'était un
défaut de LECTURE, pas de données : le classeur (11/11) avait compressé la
seconde en un REPÈRE posé sous les crans de la première — un point et un
libellé, sur la piste de l'autre. Elle existait, elle ne se lisait plus comme
une note.

Elles portent désormais chacune la même échelle 0 → 4 :

| | celle qui FAIT FOI | ce que le collaborateur SE DONNE |
|---|---|---|
| couleur | bleu · écusson | violet · silhouette |
| le développeur | une PISTE (il la pose) | une graduation, posée |
| le collaborateur | une graduation, posée | une PISTE (il la pose) |
| sortie MESURÉE | le RAIL des marches | une piste ou une graduation |

- ⚠️ **L'ordre ne bouge JAMAIS** : celle qui fait foi d'abord, quel que soit
  le regard — on sait toujours laquelle on lit.
- ⚠️ **Celle qui vous appartient se CLIQUE, l'autre est POSÉE** : des `<span>`,
  jamais des `<button>` — rien ne s'y clique et rien ne doit en avoir l'air.
  Deux pistes empilées, c'est ce que le classeur avait précisément retiré, et
  c'est ce que le collaborateur voyait tant que la note qui fait foi restait
  une piste verrouillée.
- ⚠️⚠️ **Les cinq colonnes tombent au MÊME PIXEL**, et c'est tout le propos :
  c'est leur alignement qui se lit comme un accord ou un écart. La piste porte
  un bout que la graduation n'avait pas (la gomme, et le « i » de l'échelle) —
  mesuré : **4,5 px d'écart au deuxième cran, 18 au cinquième**. La graduation
  rend donc des **JUMEAUX masqués** de ces deux éléments, pas une largeur
  recopiée à la main qui dériverait. ⚠️ Et avec les MÊMES classes : `ev-i`
  retire la bordure du « i », donc un jumeau sans elle restait 1 px trop
  large. Mesuré après : **0,000 px**.
- ⚠️ **La gomme d'une piste en lecture est masquée à l'œil, pas retirée du
  flux** : sortie du flux, la piste redevenait plus large que la graduation.
- ⚠️ **L'identité se tient PARTOUT** : une graduation porte la couleur de SA
  note, donc celle qui fait foi reste bleue même lue par le collaborateur.
  Sinon la même note changerait de couleur selon qui la regarde.
- Le verdict d'accord reste HORS des deux blocs : il parle de l'ÉCART, donc
  des deux (décision du 11/11, inchangée).

#### LE BASSIN : la règle du minimum se REGARDE

Le niveau d'une activité est le MINIMUM de ses sorties — et c'était une phrase
derrière un « i ». Le bloc de nuit porte une jauge verticale : l'eau monte au
niveau de l'activité, chaque sortie porte son repère, **l'eau s'arrête au
repère le plus bas**. Éprouvé au banc : on monte une sortie de 1 à 4, l'eau ne
bouge PAS (l'autre la retient) et c'est l'autre repère qui prend l'anneau ; on
descend à 0, l'eau tombe.

- ⚠️ **NULL ≠ 0** : une sortie pas encore notée n'a PAS de repère à zéro, elle
  n'en a pas du tout — et l'eau devient HACHURÉE, parce que l'activité n'a
  alors aucun niveau. Un trait plein dirait un verdict que personne n'a rendu.
- ⚠️ **Le niveau affiché est un APERÇU, pas une seconde règle.**
  `niveauActivite()` recalcule le minimum côté navigateur parce que le serveur
  ne connaît pas la note qu'on vient de poser — et c'est justement elle qu'on
  veut voir bouger l'eau. Le serveur reste la source : l'écran se recharge
  après l'enregistrement.
- ⚠️ **Sur place, jamais réécrit** : l'eau MONTE, et c'est ce mouvement qui
  fait comprendre la règle. Réécrit, le bassin sauterait d'un niveau à l'autre.
- ⚠️ **Deux sorties au même niveau s'empilent** (`--k`) : elles tombent sur la
  même ligne, et c'est justement là qu'on vient lire laquelle retient l'eau —
  aucune n'est masquée.
- ⚠️ **La pastille d'un repère garde son NUMÉRO**, celui de la carte de
  droite, et ne reçoit que sa couleur. `majBassin` y écrivait le NIVEAU —
  relevé sur capture : ce que la HAUTEUR du repère dit déjà, et le seul lien
  entre le bassin et la carte était coupé.

#### Les sorties CÔTE À CÔTE, et un bandeau de moins

Le classeur ne montrait qu'UNE sortie à la fois, derrière des languettes : on
ne voyait jamais ensemble les deux chiffres dont le plus bas fait le niveau.
Elles sont désormais toutes visibles, une carte chacune, numérotées comme leur
repère. Les deux régimes prennent la MÊME forme — un rail de couleur dit
lequel, un disque dit le niveau : c'est leur ressemblance qui rend la
différence lisible.

- ⚠️ **Le bandeau d'identité (`ev-tete`) a disparu DANS le bloc de nuit** : il
  redisait le nom de la personne et le niveau du rôle à dix centimètres de la
  chaîne qui les porte. La classe reste déclarée — la séance et le calendrier
  s'en servent toujours.
- La **chaîne** (le collaborateur → son rôle → l'activité) porte le verdict de
  chaque maillon : la cascade du minimum se lit d'un bout à l'autre.
- Le bloc de nuit **suit le défilement** (`sticky`) : c'est le bassin qui porte
  la comparaison, il doit rester sous les yeux pendant qu'on note à droite.
  ⚠️ En colonne unique (sous **1100 px RÉELS** — `body.pg` porte `zoom: .8` et
  les requêtes média ignorent ce zoom) il redevient `static` : collé, il
  masquerait la carte qu'on vient lire.
- Partis avec le classeur : `languettes`, `majLanguette`, `montrerSortie`,
  `sortieOuverte`, `bandeClasseur`, `feuilleSortie`, et **neuf clés** de
  catalogue (`cl_reste_*`, `cl_mes`, `cl_main`, `cl_rien`, `ev_nb_act*`,
  `ev_suivi_par`, `ev_niv_role`). Une clé qu'on retire en même temps que son
  seul lecteur ne laisse rien derrière elle — un cliquet le garde.

#### Mesures

Tests : `test_140` (deux classes réécrites — elles affirmaient la structure du
classeur), `test_109` (quatre cas), `test_130` (un cas). **29 cliquets
vérifiés ROUGES**, en trois salves. Suite : **4241 passés**, 1 sauté.
Éprouvé au banc (`tools/devrun_competences.py`) de 1000 à 1600 px dans les
deux langues : les deux modes (développeur et collaborateur), l'eau qui ne
bouge pas quand on monte la sortie qui ne retient rien, l'enregistrement relu
après rechargement, **zéro fuite française sur l'écran anglais** (95 textes
relevés, attributs compris), zéro débordement horizontal.

⚠️ **Reste à faire** : la page 1 de la maquette (la vue d'ensemble — le
classement et les marches dans un même bloc, la bande des notes, le relief au
format compact, le radar en section dédiée) n'est PAS implantée. Seul l'écran
où l'on note l'est.

### LA VUE D'ENSEMBLE : le classement, les marches, toutes les notes (2026-11-15)

Elle ne portait que le radar et la liste des rôles : on y lisait la FORME d'un
profil, jamais ce qui le retient. Tranchée sur la même maquette que l'écran de
notation, à l'échelle réelle. Elle porte maintenant, dans l'ordre où l'on se
les pose : **ce qui tient tout en bas** · **le classement** des activités et
les **marches** de celle qu'on choisit · **toutes les notes d'un coup** · le
**relief** d'une sortie mesurée · la **prochaine séance**.

#### ⚠️ Ce qui bloquait : l'API ne servait pas ces données

Le classement, les marches, la bande et le relief demandent les MÊMES
données — les sorties de chaque activité, la note qui fait foi sur chacune, et
leurs paliers — et `/mastery/synthese` n'en porte aucune. Les servir activité
par activité, c'est ~6 requêtes par activité (`dashboard_rows`) **plus une par
sortie** (`paliers_de`) : le défaut déjà payé sur le tableau global de la page
RH, qui mettait deux minutes et demie à s'ouvrir.

`Code/apercu_competences.py` + `GET /mastery/apercu/<user_id>` les servent en
un nombre **FIXE** de requêtes. Mesuré au banc : **9 requêtes** pour 8
activités, 12 sorties et 9 paliers — et `test_145` ajoute six activités
mesurées puis recompte : **pas une requête de plus**.

- ⚠️ **Les mêmes fonctions pour trancher**, jamais une copie : `etat_sortie`
  (paliers), `categorie_activite`, `color_for`, `couverture`,
  `output_ids_en_bloc`. Deux écrans qui comptent avec deux codes finissent par
  afficher deux chiffres — c'est écrit dans ce dépôt, et ça a déjà coûté une
  enquête.
- ⚠️ `paliers.etat_sortie` accepte désormais une progression **déjà chargée**
  (`paliers=…`). On passe la liste plutôt que de recopier la règle ailleurs.
- ⚠️ **Le périmètre est celui de `roles_suivis`**, comme sur la synthèse :
  `encadre()` répond par PERSONNE, et un développeur de 2 rôles sur 4 verrait
  les 4. Deux périmètres dans le même écran, c'est la panne « j'ai perdu mes
  données de notation ».
- ⚠️ Le requis d'une activité portée par **deux rôles** est le **plus
  exigeant** : prendre le premier venu ferait dépendre le verdict de l'ordre
  des lignes, et une activité paraîtrait tenue parce qu'un rôle n'exige rien
  d'elle.

#### ⚠️⚠️ DEUX chiffres, et ils ne disent pas la même chose

`niveau` **tranche** : le minimum, et NULL tant qu'une activité évaluable
n'est pas notée — la règle de tout le module, celle qui refuse de déclarer
tenu quelqu'un à moitié noté. `plus_bas` **décrit** : le plus bas de ce qui est
posé, quoi qu'il manque.

C'est `plus_bas` que la vue d'ensemble montre, sous « ce qui tient tout en
bas », et le compteur « à évaluer » dit juste à côté combien d'activités n'ont
pas été regardées. Sans cette distinction, l'écran afficherait « — » chez
quelqu'un qui a huit activités dont six notées, et ne dirait plus rien.

#### Le CLASSEMENT, et les marches de l'activité choisie

Une barre par activité, de la plus basse à la plus haute, **les sans-verdict à
la fin** : une activité non évaluée n'a pas de rang dans la progression, elle
n'est pas « en bas ». Cliquer une barre change les marches à droite.

- ⚠️ **Un socle de 10 px** : à hauteur nulle, le niveau 0 se confondrait avec
  « pas de barre du tout », c'est-à-dire avec NULL. Et les deux absences ne se
  corrigent pas de la même façon — « ? » et une barre hachurée pour ce qui
  reste à noter, « — » et un simple socle pour ce qui n'a aucune sortie :
  l'une se note, l'autre se configure.
- ⚠️ **La barre porte la couleur SÉMANTIQUE** de l'activité, celle que le
  serveur calcule (CDC 3.5) et qu'elle a partout ailleurs. La bande des notes,
  elle, a son propre dégradé bleu→vert : elle montre des SORTIES, et elle
  porte sa légende. Deux devices, deux échelles, et chacune dit laquelle.
- ⚠️ **Les marches réutilisent `railHtml`**, le rail de l'écran d'évaluation :
  une sortie mesurée se lit de la même façon partout, ou elle se lit deux
  fois. Seules ses ENCRES changent — il est posé sur un panneau sombre.

#### Toutes les notes d'un coup, et le relief

La bande est **le seul endroit de l'application où l'on voit D'OÙ vient le
minimum** sans ouvrir une activité : une ligne par activité, une cellule par
sortie, l'attendu au bout.
⚠️ La cellule d'une sortie **mesurée** porte un liseré : son niveau ne vient
pas d'une note mais d'un chiffre relevé en séance, et les deux ne se corrigent
pas de la même façon.

Le relief est **le MÊME `reliefSvg`** que la fenêtre des courbes : deux tracés
d'une même progression finiraient par ne plus dire la même chose. Son
sélecteur n'existe que s'il y a plus d'une sortie mesurée — une rangée d'un
seul bouton est un titre déguisé.

#### Deux pièges, et une leçon de méthode

- ⚠️ **DEUX lectures, en PARALLÈLE** (`Promise.all`) : la synthèse porte les
  rôles et le profil, l'aperçu porte les sorties et leurs paliers. En série,
  c'est deux allers vers la base pour une page qui se rouvre à chaque
  changement de collaborateur. Et un échec de l'aperçu **n'emporte pas la
  page** : le radar et les rôles s'affichent, les cartes qui en dépendent se
  retirent — c'est la leçon de `/panel`, qui retenait son HTML le temps d'un
  appel et annonçait ensuite une panne.
- ⚠️ **`renderBilan` est parti avec son seul appelant.** Ses quatre tuiles
  sont devenues le PANNEAU du grand chiffre, à côté de ce qu'elles expliquent
  — et elles s'affichent toujours toutes les quatre, même à zéro.
- ⚠️ **La typographie se mesure en pixels RÉELS.** `body.pg` porte
  `zoom: .8` : les noms du classement et les libellés du panneau, écrits à
  9,5 px, étaient rendus à **7,6 px** — sous le plancher de l'échelle
  (badges/méta 12, minimum 11). Remontés après mesure à l'écran.

#### ⚠️ Deux injections de cliquet qui visaient À CÔTÉ

Les deux sont des leçons à relire avant d'en écrire d'autres :

1. **Un HOMONYME.** `.ev-ou` (l'écran de notation) et `.vo-nuit` portent la
   MÊME ombre à quatre couches : `src.replace(present, fautif, 1)` frappait la
   première, et le cliquet de `.vo-nuit` restait vert sur le défaut. Une
   injection doit borner sa zone, exactement comme un cliquet qui cherche une
   chaîne.
2. **Un décor qui ne peut pas démentir la règle.** Le cliquet du minimum
   partiel restait vert parce que l'activité du décor n'avait qu'UNE sortie :
   avec une seule note, un minimum partiel et un minimum complet donnent le
   même chiffre. Le décor porte désormais une activité à deux sorties dont une
   seule est notée.

#### Mesures

Tests : `tests/test_145_vue_ensemble.py` (25 cas), plus trois cas réécrits
dans `test_109` et `test_140` — ils affirmaient `renderBilan`. **17 cliquets
vérifiés ROUGES.** Suite : **4354 passés**, 1 sauté.
Éprouvé au banc (`tools/devrun_competences.py`) de 1000 à 1600 px dans les
deux langues : les cinq états d'activité présents en même temps, le clic d'une
barre qui change les marches, **zéro fuite française sur l'écran anglais**
(163 textes relevés, attributs compris), zéro clé brute, zéro débordement
horizontal.

⚠️ **Trouvé en chemin, et corrigé** :
`test_139::test_une_note_EFFACEE_arrete_le_report` rougissait **entre minuit
et une heure à Paris**, sur HEAD comme ici. Son décor datait le palier au
calendrier LOCAL (`date.today()`) et la note en UTC (`utcnow()`) : passé
minuit les deux ne sont plus le même jour, le palier et la note du même geste
tombaient dans deux colonnes, et la courbe globale démarrait une colonne trop
loin. Même famille que `test_61_pulse` entre 00:00 et 00:08. Les deux aides
datent désormais sur la même horloge.

#### Les trois défauts du CAS CHARGÉ (2026-11-15, même jour)

« Petit souci de disposition… pas mal de trucs s'affichent mal, les niveaux
sur la pile se marchent dessus. » Mon banc n'avait que des activités à UNE ou
DEUX sorties, dont au plus trois marches : les vraies données en portent
quatre, toutes mesurées, **toutes au même niveau**. Sans ce cas on ne regarde
que l'heureux — `tools/devrun_competences.py` sème désormais « Négocier
l'offre » : quatre sorties, quatre marches chacune, toutes qualifiées.

Les trois défauts ont été **mesurés** avant d'être corrigés :

- ⚠️ **Les repères du bassin se chevauchaient de 2 px, et deux sortaient du
  bassin par le haut.** Ils étaient EMPILÉS (`--k` × 30 px) alors que la
  pastille en fait 26 px de haut — à deux sorties ça passait, à quatre non.
  Ils se posent désormais **côte à côte** (`--k` × 34 px en abscisse), et à
  plusieurs ils ne gardent que leur NUMÉRO, celui de la carte de droite. Seule
  à son niveau, une sortie garde son nom : c'est le cas courant, et c'est ce
  que la maquette montrait. ⚠️ Le nom survit dans l'info-bulle et dans
  l'`aria-label` — une pastille réduite n'efface pas l'information.
- ⚠️ **Le panneau des marches faisait 847 px**, quatre fois le classement
  d'à côté, et les rails se marchaient dessus. Il ne porte plus qu'**UNE
  sortie à la fois**, avec le pager de l'écran d'évaluation (`‹ 2 / 4 ›`) —
  **244 px** après. Même règle que la navigation entre activités : pas de
  bouclage, une flèche qui ne mène nulle part n'est pas un bouton. Et une
  hauteur PLANCHER, sinon passer de quatre marches à une fait sauter le bloc.
- ⚠️⚠️ **La mesure était écrite en BLANC sur VERT PÂLE** : `.pal-m` est une
  PASTILLE, pas une ligne de texte, et la variante sombre ne lui donnait
  qu'une encre. Quatre rectangles clairs et vides à l'écran. Elle reçoit son
  propre fond, verdict par verdict. Le drapeau « au-delà » sortait aussi du
  panneau de 8 px : resserré.
- La pastille de norme ne redit plus « NORME DE L'ENTREPRISE » — le drapeau
  du rail le dit deux lignes plus bas. Elle ne garde que ce qu'elle seule
  porte : « ≤ 10 j ».

**La barre des collaborateurs passe EN HAUT** sur la vue d'ensemble : en
colonne elle prenait 268 px à la page qui en a le plus besoin. Le bloc de nuit
passe de 1 100 à **1 373 px**. Les autres écrans n'ont pas de barre du tout
(`pleineLargeur`) — c'est donc le seul qui s'en sert, et la rendre horizontale
ici ne touche à rien d'autre.

⚠️ **Et un cliquet d'un autre fichier est tombé en chemin** :
`test_109::test_la_mesure_se_lit_autant_que_la_cible` lisait `.pal-pas .pal-m`
par un `rsplit` — « c'est la DERNIÈRE qui gagne ». La variante sombre du
panneau des marches est devenue la dernière du fichier, et le cliquet lisait
une règle qui ne le concernait pas. Il ne retient plus que les règles qui
visent la carte. *Un cliquet qui cherche une chaîne doit borner sa zone* — et
c'est la troisième fois en deux jours.

Tests : `test_140` (+2 cas), `test_145` (+5), `test_109` (1 réécrit).
**9 cliquets vérifiés ROUGES.** Suite : **4359 passés**, 1 sauté. Éprouvé au
banc sur le cas chargé, de 1000 à 1600 px, dans les deux langues : zéro
chevauchement, zéro repère hors du bassin, zéro fuite française sur l'écran
anglais (167 textes, attributs compris).

#### ⚠️⚠️ Supprimer une section de feuille emporte ce qui s'y trouvait pour d'autres

« Les boutons de la card bleue sont toujours dégueux. » Ils l'étaient, et ce
n'était pas une affaire de goût : **`.cl-rb` avait disparu AVEC le bloc du
classeur**, que la refonte de l'écran de notation a remplacé en bloc. Seule la
règle de son ICÔNE avait survécu, dans la section « LES BOUTONS : UN SEUL
VOCABULAIRE », plus bas dans la feuille.

Les pastilles sont donc retombées sur le **bouton blanc par défaut** — et leur
pastille d'icône, taillée pour un fond sombre (`rgba(255,255,255,.17)` sur
`#fff`), est devenue **blanche sur blanc** : quatre pâtés blancs à glyphe
invisible sur la carte de nuit. Le verre est restauré, à côté de `.ou-reg` qui
s'en sert.

Trois retouches au passage, toutes mesurées :
- ⚠️ **« Technicitéaucun domaine »** — le `gap` d'une boîte flex ne s'applique
  qu'entre ÉLÉMENTS, et le libellé était un nœud de texte nu. Il est dans un
  `<span>`. (Troisième fois ce jour-là, après les pastilles de la vue
  d'ensemble.)
- ⚠️ **Et la valeur ABSENTE ne s'annonce plus** : « aucun domaine » en blanc
  gras se lisait comme un verdict, et ces 75 px faisaient passer la rangée sur
  deux lignes.
- ⚠️ **La rangée est une GRILLE à deux colonnes**, pas un `flex-wrap` : à
  quatre pastilles pour 520 px (mesuré : 544 px de contenu), trois restaient
  sur une ligne et une tombait seule en dessous — ça se lit comme un
  débordement, pas comme une disposition.

#### ⚠️⚠️ Le bassin : DEUX repentirs avant de trouver

« Je ne comprends pas les 4 bulles vertes, il y a un problème je pense. » Il y
en avait un, et c'était le MIEN : deux tentatives avaient échoué pour la même
raison — **on ne regarde pas un bassin pour y lire une liste.**

1. **EMPILÉES** vers le haut : des pastilles de 26 px posées tous les 24 px se
   chevauchaient de 2 px, et deux d'entre elles sortaient du bassin.
2. **CÔTE À CÔTE et réduites à leur numéro** : quatre disques verts qui ne
   disaient plus rien du tout.

C'est **UNE pastille par NIVEAU**, pas par sortie. Seule à son niveau, une
sortie porte son NOM avec son numéro — le cas courant, et ce que la maquette
montrait. À plusieurs, la ligne porte le COMPTE (« 4 sorties à ce niveau ») et
c'est tout ce qu'on a besoin d'y lire : le détail est sur les cartes de
droite, et les noms restent dans l'info-bulle et l'`aria-label`.
⚠️ Et **pas de disque** sur la pastille de groupe : il y dirait un numéro de
carte, et c'est justement ce qu'on ne peut plus désigner.

Tests : `test_140` (+4 cas, 2 réécrits), `test_145` (+1). **7 cliquets
vérifiés ROUGES.** Suite : **4362 passés**, 1 sauté. Éprouvé au banc sur le
cas chargé dans les deux langues.

#### ⚠️⚠️ TROIS traits pleine largeur sur le même pixel (2026-11-15, même jour)

« Cet élément là n'est pas bien géré : lorsque l'on a plusieurs sorties au
même niveau, elles se marchent dessus. » La pastille unique par niveau (la
veille) avait réglé les pastilles entre elles ; ce qui restait tenait à la
géométrie du bassin, et il y avait **trois défauts** :

1. **Le badge de l'attendu était à cheval sur sa ligne** (`top: -10px`). Or le
   niveau d'une activité égale souvent l'attendu — c'est le cas qu'on vient
   vérifier — et la ligne de l'attendu, la surface de l'eau et la ligne du
   repère tombent alors **au même pixel**. La surface passait en travers du
   texte du badge. Il se pose désormais **SOUS** sa ligne et la pastille
   **AU-DESSUS** de la sienne : c'est ce qui les empêche de se croiser, quelle
   que soit la langue et quelle que soit la largeur.
   ⚠️ Au niveau 0 il n'y a que 16 px sous la ligne : `.att.hors` le repasse
   au-dessus.
2. **La pastille TOUCHAIT sa propre ligne.** `top: -33px` pour une pastille de
   33 px de haut : son bord bas tombait exactement sur la ligne, donc dans la
   surface de l'eau, qui déborde d'un pixel au-dessus. Mesuré au banc : la
   pastille du repère le plus bas croisait la surface sur **quatre activités
   sur neuf** — et seulement celles-là, parce que la pastille de GROUPE (sans
   disque) ne fait que 24 px et dégageait. Les deux formes partagent donc une
   `min-height`, et `top` la dépasse (`-37px`).
3. **La pastille du niveau 4 était rognée par le haut.** `basY(4)` vaut
   `h - fond` **quelle que soit la hauteur du bassin** : avec un fond et un
   ciel égaux (20 px), elle débordait TOUJOURS de 13 px. Le bassin a donc un
   fond (16) et un **ciel** (46) distincts — il faut au ciel la hauteur d'une
   pastille. Mesuré après : 10,4 px de marge au-dessus.

Et **l'eau porte son niveau toute seule** : la ligne du repère le plus bas
redoublait la surface au pixel près. `.bassin.a-eau .mk.est-bas .bar` ne se
dessine plus — sans niveau (NULL) il n'y a pas de surface, et le repère garde
sa ligne. ⚠️ Un repère **muet** (pas le premier de son niveau) ne laisse plus
RIEN non plus, pas même sa ligne : quatre traits identiques au même pixel,
c'est exactement ce qui « se marchait dessus ».

Mesuré au banc sur les **neuf** activités du collaborateur, animations
coupées : **0 collision, 0 pastille hors cadre**.

#### Le même écart entre toutes les cartes — DEUX COLONNES, pas deux rangées

« J'aimerais que l'on ait le même espacement entre chaque carte, que ça fasse
propre. » En grille, la hauteur d'une rangée est celle de sa carte la plus
haute : le profil fait deux fois la carte des notes, et « Prochaines séances »
attendait donc **190 px** sous la carte qu'elle suit — un trou qui ne se lit
comme rien. Trois écarts différents cohabitaient par-dessus (le `gap` de la
grille, la marge basse du profil, la marge haute des séances).

Chaque colonne est désormais une **pile** (`.vo-col`, flex en colonne), et un
jeton unique — `--vo-gap` — sépare toutes les cartes dans les deux sens.
⚠️ Une grille ne sait pas faire ce tassement : c'est « masonry », que personne
n'implémente encore.
⚠️ **Conséquence assumée** : en colonne unique (sous 1100 px RÉELS) l'ordre
suit les COLONNES — profil, relief, notes, séances — et non les rangées.
Mesuré : **12,8 px partout**, à 1600 px comme à 1000, et aucun débordement
horizontal.
⚠️ Les écarts ne se mesurent qu'**animations coupées** : l'entrée des cartes
part d'un décalage, et dans ce volet une animation reste figée en cours de
route — relevé 8 px ici et 18 px là pour un écart qui vaut 12,8.

#### Le drapeau dit « Norme », et son voisin « Au-delà »

Les deux drapeaux du rail marquent des marches **VOISINES**, et chacun est
centré sur la sienne : leur largeur cumulée ne peut pas dépasser deux fois le
pas du rail. Mesuré sur le panneau des marches de la vue d'ensemble (pas de
75 px) : « NORME DE L'ENTREPRISE » + « AU-DELÀ DE LA NORME » faisaient 236 px
et se chevauchaient de 60 — c'est la capture du pilote.

⚠️ **Et raccourcir le premier ne suffisait pas.** En français « Norme » +
« Au-delà de la norme » tombe à 146 px et dégage de 2 px ; **en anglais**
« Standard » + « Beyond the standard » fait 162 px et **se chevauchait encore
de 6** — relevé en repassant l'écran en anglais, pas déduit. Les deux sont
donc courts : mesuré après, 31 px d'écart en français, 26 en anglais.
Le cliquet porte sur la **LONGUEUR** des deux libellés dans les deux langues :
c'est elle qui décide, et une traduction plus bavarde rouvrirait le défaut.
`pal_norme_tag` disparaît — c'était une seconde clé pour le même mot que
`pal_norme`.

#### Deux retraits, et une porte

- **« Une sortie mesurée n'a pas de note à saisir… »** est partie, avec sa
  clé : elle expliquait, sous un pied vide, une règle que le rail des marches
  montre déjà juste au-dessus.
- **Le maillon du RÔLE est une PORTE** : il ramène à la vue d'ensemble,
  ouverte sur le détail de CE rôle — une ligne par activité, avec sa cible. On
  n'y venait que par un point du radar, et il n'existait **aucun** chemin
  depuis l'écran où l'on note.
  ⚠️ `state.voRole` ne vaut que pour cette arrivée : gardé, il rouvrirait les
  barres à chaque changement de collaborateur et le radar ne se verrait plus
  jamais. Et il se lit **APRÈS** `animerProfil`, qui remet la zone sur le
  radar.
  ⚠️ C'est un `<button>` au milieu d'une chaîne de trois maillons : sans
  `font: inherit` et `color: inherit`, il aurait été le seul dans la police du
  système.

⚠️ **Deux pièges de banc, tous deux déjà connus** : `String.split(sep, n)` en
JavaScript prend une **LIMITE**, pas un nombre de coupes — `split(a, 1)` rend
un tableau d'un seul élément, et mon détecteur de fuites a d'abord lu **zéro
clé** dans les deux catalogues, donc zéro fuite, donc un contrôle vert qui ne
regardait rien. Et un heredoc de shell **avale les antislashs** : un `\\d` écrit
dans un script Python embarqué arrive `d`. Passer par un fichier.

Tests : `test_140` (+5 cas, 2 réécrits), `test_145` (+2), `test_109` (+2,
1 réécrit). **19 cliquets vérifiés ROUGES.** Suite : **4373 passés**, 1 sauté.
Éprouvé au banc
(`tools/devrun_competences.py`) à 1600 et 1000 px dans les deux langues :
neuf bassins sans une collision, les écarts à 12,8 px, la porte du rôle qui
ouvre les barres et ne survit pas au collaborateur suivant, et **zéro fuite
française sur l'écran anglais** (1 082 textes relevés, attributs compris —
tout ce qui reste en français est une DONNÉE du banc).

### LA GALERIE D'ACCUEIL : la page ne s'ouvre plus sur une phrase (2026-11-15)

« Cette sous-page fait une page très vide et qui de toute façon ne conserve
pas sa structure, alors autant la reprendre ; il serait sympa d'avoir le
graphique de l'ancienne page pour visualiser en un coup d'œil les compétences
du collaborateur. » Mesuré avant de redessiner, à 1600 × 1000 :

| | avant |
|---|---|
| vide sous le seul contenu de la page | **726 px** (la page fait 1000) |
| largeur utilisée | **38 %** — 432 px de cadre pointillé pour 1144 disponibles |
| la barre des collaborateurs | **214 × 253 à gauche**, puis **1373 × 67 en haut** dès qu'on choisit quelqu'un |
| information sur l'équipe | **aucune**, alors que tout était déjà calculé |

Le reproche sur la structure était exact et il est chiffrable : ce n'est pas
une adaptation, c'est un autre objet.

**Tranché sur maquette** — trois organisations cliquables à l'échelle réelle,
avec les données du banc (artefact « Écran d'accueil Compétences ») : **A** la
galerie, **B** la barre qui ne bouge pas plus un radar d'équipe, **C** les
deux. Retenu : **A**. C'est la dixième fois que la méthode évite une journée
écrite pour rien.

#### Ce que l'écran montre

Une carte par collaborateur : son profil en vignette, sa couverture, ses
quatre compteurs, et ce qui reste à noter. **Les cartes SONT la liste** — pas
de barre à l'arrivée ; une barre de noms au-dessus d'une grille des mêmes noms
serait deux portes pour un seul geste. La barre revient quand on entre dans un
dossier, et un bouton **« L'équipe »** y ramène.

#### ⚠️ Le serveur : `apercu` par personne, c'était dix requêtes chacune

`Code/apercu_competences.py::galerie(acteur, gens)` + `GET /mastery/galerie`.
Un nombre **FIXE** de requêtes quel que soit l'effectif — mesuré : trois
collaborateurs de plus ne coûtent pas une requête de plus. C'est le défaut qui
mettait le tableau global de la page RH à deux minutes et demie.

- ⚠️ **La carte est la VIGNETTE du dossier, pas un second calcul.** Le corps
  de la boucle d'`apercu` est extrait dans `_activites_du` et les deux
  l'appellent : deux calculs d'un même niveau finiraient par afficher deux
  chiffres, et c'est une enquête qu'on a déjà payée ici. Un cliquet compare
  les deux, personne par personne et activité par activité.
- ⚠️ **Les gens viennent de `collaborateurs_de`, et de nulle part ailleurs.**
  `/competences/contexte` remplissait sa liste à la main ; la fonction vit
  maintenant dans `Code/competences_acces.py` et les deux la lisent. Une carte
  que la liste ne porte pas serait une carte qu'aucun clic n'ouvre.
- ⚠️ **Le périmètre des RÔLES reste celui de `roles_suivis`** : un développeur
  de 2 rôles sur 4 ne voit pas les 4. `_suivis_en_bloc` applique la règle sans
  refaire deux requêtes par personne, et `None` (aucune restriction) ne se
  confond pas avec une liste VIDE (il n'en suit aucun).
- ⚠️ **La galerie n'ÉCRIT rien.** `get_activity_outputs` matérialise les
  connexions sortantes en `Data` : on ne l'appelle pas depuis une page de
  lecture. On relit avec `output_ids_en_bloc`, et un cliquet compte les `Data`
  avant et après — son décor porte exprès une activité dont les sorties ne
  sont pas matérialisées, sans quoi il resterait vert même sur une page qui
  écrit.
- `_paliers_en_bloc` délègue à `_paliers_multi` : une seule forme de requête
  pour une personne comme pour dix.

#### La vignette, et les deux décisions qu'elle a coûtées

- ⚠️ **Le requis passe en FANTÔME.** Premier essai avec le requis rempli,
  comme sur le grand radar : **les trois cartes se ressemblaient trait pour
  trait**. Normal — le requis est le même pour tout le monde, c'est la carto
  qui l'impose. Ce qui distingue les gens, c'est le DÉMONTRÉ : c'est lui qu'on
  remplit.
- ⚠️ **Pas d'étiquettes** : à 150 px, neuf noms d'activité en 10,5 px ne
  tiennent pas. C'est la FORME qui se lit d'un coup d'œil ; les noms sont à
  l'intérieur, sur le grand radar.
- ⚠️ **Les axes sont ceux de CETTE personne**, triés par écart croissant —
  exactement `synthese.profil`, que le radar du dossier dessine. Des axes
  communs à tout le monde donneraient deux graphes différents d'une même
  personne, et une activité hors de son périmètre se lirait comme une activité
  non évaluée.
- ⚠️ **NULL ≠ 0**, ici comme partout : une activité que personne n'a notée n'a
  pas de point. Lina n'a que 2 activités notées sur 9 — son radar est presque
  vide, et c'est exactement ce qu'on doit voir.
- **UNE seule fonction** (`radarSVG(axes, opts)`) pour les deux tailles :
  même géométrie, même règle de couche.

#### La largeur de la carte, en deux essais

- `auto-fill` à `1fr` : des colonnes vides et des cartes étroites au milieu
  d'un écran large — le vide qu'on venait de corriger, sous une autre forme.
- `auto-fit` à `1fr` : l'inverse — mesuré, **trois cartes étirées à 562 px CSS
  dont le contenu n'occupait que la moitié**.
- Retenu : la piste est **plafonnée à 460 px** (la largeur éprouvée sur
  maquette) et ce qui reste est **centré**. Mesuré : 3 cartes par rangée de
  1280 à 1920, 2 à 980, aucun débordement horizontal nulle part.
- ⚠️ Le repli étroit ne touche PAS à la grille : `1fr` défaisait le plafond et
  rendait, à 980 px réels, une carte de **1 161 px CSS** de large.

#### ⚠️ Trois pièges, tous déjà connus

- **`[hidden]` est une règle du NAVIGATEUR** : `.gal-c` pose un `display`, donc
  la recherche ne masquait rien tant que `.gal-c[hidden]` n'était pas déclaré.
  **Septième fois** que ce piège se présente dans cette application.
- **Un cliquet qui découpe sur un repère de SECTION doit couper après le
  `*/`** : le repère est lui-même un commentaire, et il cite les quatre jetons
  qu'il interdit. Retirer les commentaires d'abord ne suffit pas — le texte
  reprend au milieu du commentaire, dont la fin survit au nettoyage. Sixième
  fois.
- **Un id RETIRÉ ne se réemploie pas.** Le bouton de retour s'appelait d'abord
  `#cv2-retour` — or `test_109` exige que cet id soit MORT, parce qu'il avait
  « survécu une version de trop et cassé le démarrage ». Lui redonner vie
  désarmait ce cliquet : le retour s'appelle `#cv2-vers-galerie`.
- ⚠️ **Deux cliquets découpaient sur une LONGUEUR FIXE** (900 signes après une
  ancre, et la signature `radarSVG(axes)`). Ils ont rougi sans qu'une seule
  règle ait bougé, parce qu'un commentaire s'est glissé dedans et qu'une
  fonction a pris un second argument. Ils bornent désormais sur ce qui SUIT.

#### Mesures

Tests : `tests/test_147_galerie_accueil.py` (25 cas), plus trois cas de
`test_109` réécrits sur ce qui reste vrai. **27 gardes retirées une par une,
27 cliquets tombés.** Suite : **4 423 passés**, 1 sauté ; `repet_image`
4 327 passés + 72 sautés. Éprouvé au banc
(`tools/devrun_competences.py`) de 980 à 1920 px dans les deux langues :
parcours complet (carte → dossier → retour), recherche (frappe, accents, sans
résultat), un collaborateur qui entre droit dans son dossier sans voir de
galerie, zéro erreur console, et **zéro fuite française sur l'écran anglais**
(516 clés, 492 pièges, 158 textes relevés, attributs compris).

#### Le détail des séances ne faisait RIEN, et le bandeau flottait (2026-11-15)

« Structurellement c'est top ; on peut améliorer le visuel, pas ce que
contiennent les sections — les graphiques — mais le reste. Et dans la section
"comment machin a bougé", une fois un user sélectionné, le bouton détail des
séances ne marche plus. Mets en sorte qu'il se développe sur le côté, comme on
a de la place, plutôt que de rallonger en bas. »

#### ⚠️⚠️ Le bouton était rendu et câblé NULLE PART

`bilanRelief` écrit « Le détail des séances → » ; `rendreValeurs` (la fenêtre
des courbes) branche `[data-evol]` sur `basculerHisto`. **`renderRelief`, lui,
ne branchait rien** : sur la vue d'ensemble, le bouton existait depuis le jour
de son arrivée et ne faisait rien. Mesuré au banc avant correction :
`b.onclick === null`.

#### ⚠️⚠️ Et le partager EN L'ÉTAT était impossible — c'est la mesure qui a tranché

Le relief a un `viewBox` de **828 unités** et `width: 100 %`. Dans les 680 px
réels d'une colonne de la vue d'ensemble il se rendait déjà à **0,78**, et ses
libellés tombaient entre **6,6 et 10,2 px RÉELS** — sous le plancher de 11 de
l'échelle typographique. Ouvrir un panneau à côté l'aurait ramené à 490 px,
soit **4 px**. Illisible.

Le relief quitte donc les deux colonnes et devient une **BANDE pleine largeur**
(`vo-bande`, posée après `.vo-cols`). Trois conséquences, toutes mesurées :

| | avant | après |
|---|---|---|
| le SVG du relief | 647 px réels (×0,78) | **1 316** (×1,59) |
| ses libellés | 6,6 à 10,2 px réels | **13 à 21** |
| panneau ouvert | — | relief 961 px (×1,16), panneau 336 |
| hauteur de la bande | 619 px | **491** une fois ouverte |

Elle rééquilibre aussi les colonnes : la gauche faisait 801 px contre 443 à
droite — **358 px de vide**, exactement la place que l'utilisateur voyait.

- ⚠️ `.pal-evo-duo` porte les deux colonnes et `.pal-evo-g` tient le relief et
  son bilan. Sans ce couple, le panneau se place sous le bilan.
- ⚠️ **Un seul bouton de fermeture à côté.** Le bouton du bas existe parce que,
  empilé, celui qui a OUVERT se retrouve en plein milieu. À côté il ne bouge
  pas d'un pixel : un second bouton ne ferait que doubler celui qu'on a sous
  les yeux. La fenêtre des courbes, elle, reste empilée (1 060 px : le partage
  y ramènerait les libellés sous 6 px) et garde le sien.
- ⚠️ Sous **1150 px réels**, la bande repasse en pile. La borne est en px
  RÉELS — `body.pg` porte `zoom: .8` et les requêtes média l'ignorent.
- ⚠️ **`innerHTML` vide les enfants, PAS l'attribut.** Changer de sortie
  pendant que le détail est ouvert laissait `data-evo="1"` sur une bande sans
  panneau : deux colonnes dont la seconde est vide, et un relief rétréci pour
  rien. Trouvé en relisant le code, pas à l'écran.

#### Le bandeau de page flottait — sur TOUS les écrans de la page

`.page-banner` plafonne à **1200 px CSS** quand
`body.pg.page--competences .pg-container` va à **1760**. Mesuré à 1800 px :
960 px réels de bandeau au-dessus de 1 408 px de contenu — **448 px plus
étroit**, centré. C'est ce décalage qu'on lit comme un défaut de mise en page,
bien avant le détail des cartes. Le bandeau suit désormais le conteneur.

#### ⚠️⚠️ `repeat(auto-fit, minmax(A, B))` compte les pistes sur B, pas sur A

Et resserrer peut donc EMPIRER les choses. La galerie plafonne ses cartes à
460 px ; à 1 760 px, trois cartes se centraient en laissant 123 px de gouttière
de chaque côté pendant que le bandeau et les compteurs allaient d'un bord à
l'autre. Premier essai : conteneur à 1 440 px. Mesuré —
`floor((1396 + 14) / 474)` rend **DEUX** pistes, et la galerie est passée à
deux cartes par rangée. Il en faut **1 452** pour trois ; l'accueil se cadre à
**1 500** (classe `a-cv2-galerie`), ce qui pose les trois cartes avec 24 px de
marge. Bandeau, compteurs et cartes s'alignent enfin.

#### La passe de style — tout sauf les graphiques

- la **tuile** porte le MÊME liseré coloré que la carte qu'elle résume (c'est
  ce qui les fait lire comme une famille), son chiffre passe à 26 px, et la
  pastille ronde part : elle redisait le liseré ;
- les **cartes** prennent une ombre à **quatre couches** — la lumière ne fait
  pas une ombre nette, et c'est ce qui les pose sur la page au lieu de les y
  coller. Même traitement au survol, en accent ;
- le **pied de carte** passe du pointillé au filet plein : le pointillé dit
  « provisoire », et ce pied porte le compte des notes et la porte du dossier ;
- ⚠️ **« Aucune activité à évaluer » était faux et se lisait comme une panne.**
  Le radar manque quand il y a moins de trois axes à tracer, pas quand il n'y a
  rien à évaluer. Le libellé devient « Pas encore de quoi tracer un profil », et
  il s'inscrit dans un **disque en pointillé** : une phrase grise seule au
  milieu de la place du radar se lit comme un échec de chargement.

#### Mesures

Tests : `test_145` (+5), `test_147` (+3), et trois cas de `test_109` et
`test_145` réécrits sur ce qui reste vrai. **9 gardes retirées une par une,
9 cliquets tombés.** Suite : **4 431 passés**, 1 sauté ; repet_image
4 359 passés + 72 sautés. Éprouvé au banc à 1400 et 1800 px dans les deux langues : le bouton
ouvre et referme, le panneau est à droite du relief, la bande RACCOURCIT en
s'ouvrant, et **zéro fuite française sur l'écran anglais** (363 textes relevés,
attributs compris — les quatre relevés sont des DONNÉES du banc).

### END_DT : un socle de présentation, posé par SQL (2026-11-16)

`tools/db/seed_end_dt.sql` — à coller dans l'éditeur SQL de Neon, sur la base
du pilote. Trois requêtes : inventaire (lecture seule), le semis (un seul bloc
atomique), relecture. Il crée une carto `END_DT` qui porte **la carto exacte**
d'une entité existante, la partage, et la remplit de données de temps.

Pourquoi en SQL plutôt qu'un script `tools/db/` en Python : lire la
`DATABASE_URL` du pilote depuis Cloud Run a été **refusée** par le contrôle de
permissions, et c'est la bonne réponse — on ne contourne pas. L'utilisateur
colle, le script se garde tout seul.

#### Les décisions qui ont coûté quelque chose

- ⚠️ **La carto n'est PAS re-dérivée du diagramme.** On COPIE les lignes que
  `_sync_carto_to_db` a déjà produites pour la source. Réécrire cette
  dérivation en SQL en ferait une seconde implémentation, et les deux
  finiraient par ne plus dire la même chose — la règle que tout ce dépôt tient.
  `optiqcarto_data` est recopié tel quel : la carto est exacte par
  construction. Mesuré : **identique octet pour octet** (65 311), et les
  42 `shape_id` conservés.
- ⚠️ **Seules les connexions activité → activité sont copiées.** Une connexion
  dont un bout est une `Data` pointerait la donnée de l'AUTRE carto. On la
  laisse : le prochain enregistrement de la carto dans l'éditeur la recréera
  depuis le diagramme, qui est copié. Mesuré : 72/72 copiées, **0 connexion
  hors carto**.
- ⚠️⚠️ **Le partage compte par compte N'EXISTE PAS.** `can_read` n'ouvre une
  carto commune que par **rôle** ou par **palier de statut**. « Partagée à nous
  deux » se traduit donc par : propriétaire = Maël, plus **UN** rôle ouvert — et
  ce rôle doit être celui qui a **le MOINS de titulaires**, car un rôle autorisé
  ouvre la carto à *tous* ceux qui le tiennent. Le bloc le dit en clair, et la
  requête 3 nomme ensuite tout le monde. Mesuré au banc : Hubert tenait deux
  rôles porteurs, l'un à quatre titulaires et l'autre à lui seul — le script
  a choisi le second.
- ⚠️ **Le rôle ouvert doit porter une activité d'ICI.** `_sync_carto_to_db`
  efface l'accès d'un rôle absent de la carte : un rôle pris ailleurs
  s'évaporerait au premier enregistrement dans l'éditeur.
- ⚠️ **Intersection vide → la carto reste PRIVÉE**, et le bloc dit quoi faire.
  Une carto commune sans aucun rôle autorisé est ouverte À TOUS, le contraire
  de ce qui est demandé.
- ⚠️ **Il REFUSE de rejouer.** Un second passage empilerait une deuxième copie
  des activités et des analyses. Vérifié : second passage → `ERROR`, et les
  neuf compteurs inchangés.
- ⚠️ **Une durée SAISIE n'est jamais remplacée** (`NULLIF(…, 0)`) : on ne
  réécrit pas un chiffre que quelqu'un a posé. Vérifié avec un témoin à
  777/888 min, relu à 777/888.
- ⚠️ **Sans ligne `entreprise_settings` pour CETTE carto**,
  `get_calendar_params` retombe sur la **PREMIÈRE ligne de la table**,
  c'est-à-dire le calendrier d'une autre entité. Le script en pose une.
- ⚠️ **Deux activités sur dix restent non chiffrées, volontairement** : la
  carte « ce qui n'est pas chiffré » est la seule qui dise que le total annoncé
  ne porte pas sur toute la carto. Si tout est mesuré, on ne la voit jamais.
  Mesuré : 34 chiffrées sur 42, 8 nommées à chiffrer.
- ⚠️ **Les analyses de rôle prennent TOUT le périmètre du rôle** (plafond 20).
  Mesuré avec un plafond à 8 : les deux analyses tombaient **sous** le temps
  plein (78 % et 83 %) — la variante la moins parlante de la carte des rôles.
  Avec leur périmètre réel : **136 % et 83 %**, un rôle au-dessus de la ligne
  et un bien en dessous, ce que la carte est faite pour montrer.
- ⚠️ **Le tableau de bord cadre une analyse de rôle par ses LIGNES**, pas par
  le rôle : celles-ci pointent END_DT, donc l'analyse ne paraît pas sur la
  carto source, même si le rôle est commun aux deux (depuis le 23/09).
- ⚠️ **Travail refait et attente ne s'additionnent jamais** : trois faiblesses
  de natures différentes (surtout du travail, surtout de l'attente, aucune
  attente). Et le délai standard ne tombe pas sous la durée
  (`delai_plancher`) : l'écran le bornerait à l'enregistrement, on n'écrit pas
  un état qu'il refuserait.
- `prob_percent` est arrivé le 03/11 : le script regarde
  `information_schema.columns` au lieu de présumer.

#### Éprouvé, pas supposé

Banc : un **vrai PostgreSQL 16** (conteneur jetable), schéma monté par le
démarrage NORMAL de l'application, carto source dérivée par
`_sync_carto_to_db` depuis `tools/provisioning/carto/map_rfq_fluidclip.json`
(42 activités, 72 connexions, 9 rôles porteurs — l'échelle du pilote).
Huit témoins SQL, tous verts ; puis le **vrai endpoint**
`/temps/api/tableau_de_bord` interrogé pour de bon : **HTTP 200**, les cinq
cartes pleines (8 517 h/an, 5,05 ETP ; 57 h de travail refait et 368 h
d'attente, séparés ; 34/42 chiffrées ; 136 %/83 % par rôle ; 34 activités), les
quatre groupes de « Vos analyses » non vides, et **les mêmes chiffres en
anglais**.

⚠️ Écarté en chemin : le classement des faiblesses lit bien
`travail_annuel_min` (le travail seul) et jamais l'`annuel_min` d'un item, qui
somme les deux natures. Il n'y a donc pas de défaut d'addition dans l'écran —
vérifié dans `time.js`, pas supposé.

⚠️ **Et un piège de shell, pour la quatrième fois** : un heredoc Bash a avalé
les apostrophes d'un SQL français (`unexpected EOF`). Un fichier qui porte du
texte français se pose par la Write tool, jamais par un heredoc.

### Report sur le pilote : la page Temps, sans l'écran Compétences (2026-11-16)

Même recette que le 11/11, et elle se vérifie d'une commande : l'arbre de
staging À L'IDENTIQUE, puis les **trois fichiers d'écran** rendus à leur
version du pilote —
`Code/routes/templates/competences_view.html`, `static/competences.css`,
`static/js/competences_v2.js`. L'invariant :
`git diff --name-status origin/staging <commit>` ne rend que ces trois-là.

Bâti avec un **index temporaire** (`GIT_INDEX_FILE` + `read-tree` +
`update-index --cacheinfo` + `commit-tree`, deux parents) : rien à sortir ni à
remettre dans l'arbre de travail de la session.
⚠️ Et avec le git de **Windows**, pas celui de WSL : le `.git` d'un worktree
de session pointe une UNC que WSL ne résout pas (`fatal: not a git
repository`).

**Ce qui part** : la page Temps refondue (les trois écrans, les cinq
récurrences, les deux natures du coût d'une faiblesse, les listes déroulantes
dessinées, la passe de style), l'ancre `#calendrier` de la page RH, et le
backend Compétences en ENTIER — il ne peut pas être tenu en arrière sans
casser la page RH ni le démarrage, et il porte deux correctifs d'accès.

**Mesuré sur l'arbre du pilote**, dans un worktree jetable : **4 132 passés,
302 sautés, 0 rouge**. Les 302 sont exactement les quatre fichiers d'écran
(`test_109` 125, `test_140` 89, `test_145` 37, `test_147` 28), deux classes
de `test_130` (13) et le saut d'arbre d'image de `test_51`. Chaque saut porte
sa raison : la garde est un PRÉDICAT SUR LE FICHIER
(`"renderGalerie" in competences_v2.js`), jamais un drapeau de branche — elle
s'éteindra d'elle-même le jour où l'écran partira, et il n'y a rien à défaire.

⚠️ **Vérifié EN LIGNE après le déploiement**, pas seulement au vert du
workflow : `/health` 200, `time.js` (78 Ko) porte `saved_weakness` et
`trimestriel`, `tm_select.js` est servi, et `competences_v2.js` fait toujours
2 126 lignes sans `renderGalerie` ni `cv2-ecran-eval`.

Livré à **06h31 en Inde**, avant la journée de travail — la règle du soir est
tenue.

#### Le contrôle de traduction qui va avec

La page Temps parcourue EN ANGLAIS au banc, écran par écran : accueil groupes
dépliés, les quatre écrans de saisie, les panneaux des listes déroulantes, la
section Résultats et ses onze bulles, les unités (`min` / `hrs` / `day`) et
les cinq récurrences. **Une seule fuite**, corrigée : le retour
d'enregistrement d'une faiblesse (voir plus haut).

⚠️ Le détecteur ne doit PAS prendre pour français les mots que l'anglais
emploie aussi : `role`, `charge`, `analyse`, `project`, `minutes`. Avec eux,
« No role reaches a full-time job » et « Minutes of work to redo… » ressortent
comme des fuites, et on finit par ne plus lire la liste.

**La dette, elle, est mesurée** : **191 chaînes françaises écrites en dur**
dans 23 fichiers JS encore chargés par un gabarit — `propose_aptitudes.js`
(47), `activities_map.js` (26, déjà signalé comme du code mort),
`tasks.js` (22), `propose_from_file.js` (16), `tasks_roles.js` (10),
`competencies.js` (10)… plus **129 dans 8 fichiers que plus aucun gabarit ne
charge** (`synth_competences.js`, `plan_formation.js`, `performance_perso.js`,
`test.js`…). Ce n'est pas une passe de relecture : c'est un chantier à part,
et il se tranche écran par écran.

### Le report sur le pilote SANS la page Compétences (2026-11-11)

« Je voudrais que l'on puisse push tout sauf la page compétences, car j'estime
qu'elle a encore besoin de travail pour être au niveau de ce que j'attends. »
91 commits de retard rattrapés, **un seul écran retenu**.

⚠️ **`deploy-beta.yml` n'est plus propre au pilote** : staging le porte à
l'identique. La recette du 17/09 (« l'arbre de staging + ce fichier ») se
simplifie donc en **l'arbre de staging, et rien d'autre** — vérifié, aucun
fichier n'existe chez le pilote qui manque à staging
(`git diff --diff-filter=D` ne rend rien).

**L'écran Compétences tient en TROIS fichiers**, et c'est tout ce qui est gelé
à la version du pilote : `Code/routes/templates/competences_view.html`,
`static/competences.css`, `static/js/competences_v2.js` (5 500 lignes ajoutées,
541 retirées entre les deux versions).

⚠️⚠️ **Le BACKEND Compétences, lui, part en ENTIER — il n'y a pas le choix, et
c'est mesuré.** `Code/competences_globales.py`, qui alimente le tableau de la
page RH, importe `output_ids_en_bloc` de `qualify_outputs` et cinq symboles de
`mastery` ; `historique_notes.py`, appelé au DÉMARRAGE par `app.py`, importe
`get_activity_outputs` et les aides de `paliers` ; et `paliers_routes.py`
appelle `peut_lire(..., role_id=)` / `peut_noter(..., role_id=)`, signatures qui
n'existent que dans la version neuve de `competences_acces.py`. Reculer un seul
de ces fichiers casse la page RH ou le démarrage. Et il y aurait un prix :
`competences_acces` porte le correctif du **développeur par rôle** (un
développeur de 2 rôles sur 4 pouvait NOTER les 4), et `mastery` deux routes qui
n'avaient **aucun contrôle d'accès** (`/mastery/activity`, `/mastery/required`)
— on ne livre pas sciemment trois trous à un client pour geler un écran.

⚠️ **Conséquence VISIBLE sur l'ancien écran, et il faut la dire** :
`activity_mastery` ne filtre plus sur `semantic_nature == "RESULT"` (toute
sortie est évaluable). L'ancien écran en tire son état « À configurer »
(`if (!a.n_results) return 'setup'`), et c'est sa SEULE porte vers la fenêtre de
qualification : elle devient inatteignable chez le pilote. Rien n'est perdu —
depuis le 10/11, ce que l'entreprise attend d'une sortie se lit dans la colonne
**Performance** de la liste des activités, que le pilote édite toujours ; c'est
l'ancien écran qui ne sait pas l'afficher.

⚠️ **La NOTATION, elle, marche — vérifié, pas supposé** : l'ancien écran envoie
déjà `role_id` à `/mastery/evaluate` (que la version neuve exige), et
`mesurable(d)` réclame `d.norme_valeur`, que rien n'écrit sans le nouvel écran
— aucune sortie n'est donc « mesurée » chez eux et le refus `measured_output`
ne se déclenche pas.

⚠️ Et `translations.py` ne retire **aucune** clé Compétences (ses 41 retraits
sont `time.*`, `droit.*`, `acttime.*`) : le catalogue de cette page vit DANS
`competences_v2.js` (`I18N`, `T = k => I18N[LANG][k] || k`), donc l'écran gelé
emporte le sien.

**Les tests : une garde de saut qui est un PRÉDICAT SUR LE FICHIER.**
Trois fichiers lisent cet écran et rougissaient — mesuré, **158 rouges**. Le
saut vaut `"cv2-ecran-eval" in competences_v2.js`, jamais un drapeau de branche :

- `test_109_paliers_ecran` et `test_140_classeur_evaluation` sautent en entier.
  Leurs rouges se répartissent sur **26 et 15 classes** : un saut par classe
  serait 41 retouches. ⚠️ Le MOTEUR des paliers reste tenu par `test_108`, qui
  ne lit aucun gabarit et tourne partout ;
- `test_130_retours_du_pilote` saute **deux classes seulement**
  (`TestLesCartesDeRoleDuBas`, `TestLaNormeVientDeLaListeDesActivites`) : ses
  55 autres cas gardent des correctifs qui, eux, partent.

⚠️ **Il ne saute JAMAIS sur staging**, et c'est vérifié dans les deux sens :
**295 passés / 0 sauté** avec l'écran neuf, **85 passés / 210 sautés / 0 rouge**
avec l'écran gelé. L'arbre du pilote reste donc celui de staging aux trois
fichiers près, et le jour où l'écran part le saut s'éteint de lui-même :
**rien à défaire au prochain report**.

---

### Le calendrier partagé, RETIRÉ le jour même (2026-11-14)

Écrit, livré, puis **repris** quelques heures plus tard : « l'idée est trop
complexe et je veux pas faire un truc à la va-vite, donc on revient à notre
calendrier exclusivement dans les compétences ». Le calendrier de la page
Compétences (`#cv2-ecran-cal`, 2026-10-15) est donc le seul, avec son style
d'avant.

Partis : `Code/routes/calendrier.py`, son gabarit, `static/js/calendrier.js`,
`static/calendrier.css`, `tests/test_141_calendrier_partage.py`, le verdict
`calendrier_ouvert` du processeur de contexte, les trois portes (page Temps,
page Compétences, pied de la fenêtre de bienvenue) et les 43 clés `cal.*` × 2
langues.

⚠️ **Le bouton de la page Temps GARDE son nouveau nom** — « Temps de
travail » / « Working hours ». Il avait été renommé parce qu'un vrai
calendrier arrivait à côté ; la raison a disparu, mais le nom reste le juste :
il ouvre les **réglages du temps de travail** (semaines / jours / heures,
bandeau de la page RH, ancre `#calendrier`), pas un calendrier. C'est la
question qu'avait posée l'utilisateur.

ℹ️ Ce qui n'a PAS été rendu, parce que c'étaient des correctifs à part entière :
les deux retouches de `tests/test_105_temps_refonte.py` — `_CartoJetable`
repose TOUJOURS une entité active au lieu de retirer la clef, et le cas des
deux boutons de l'en-tête découpe sur une borne au lieu de 600 signes.

#### ⚠️⚠️ La leçon qui survit au retrait : l'échec se lisait TROIS FICHIERS PLUS LOIN

`test_141` passait seul ; la suite complète rendait **six rouges dans
`test_14_cartography_editor`**, qui ne parle ni de calendrier ni de temps.
Mesuré plutôt que supposé : la suite SANS `test_141` était propre, et
`test_141` + `test_14` seuls l'étaient aussi — c'est donc l'état ACCUMULÉ
plus ce fichier.

La cause : `test_141` écrivait ses activités dans l'entité du DÉCOR COMMUN —
et `test_14` comme `test_15` lisent la carto de l'entité ACTIVE
(`/cartography/api/load` rendait 200 là où il attendait 404). Les créations et
les suppressions s'équilibraient pourtant ; c'est le va-et-vient de l'entité
active, que `auth_client` repose avec `setdefault` — donc sans CORRIGER une
valeur laissée derrière — qui faisait le reste.

**La garde n'était pas un rattrapage mais une ISOLATION** : le fichier
travaillait sur SA PROPRE carto (détruite en fin de module) avec un
`owner_id` — une entité de test sans propriétaire est lisible par TOUT LE
MONDE et devient le repli des fichiers suivants — et une fixture `autouse`
PROUVAIT après chaque cas qu'il ne restait rien (carto, SVG et cinq compteurs
comparés avant/après : un reliquat devient un échec DANS ce fichier, pas trois
fichiers plus loin).

ℹ️ Règle qui en découle, et elle vaut pour tout fichier à venir : **un fichier
de tests neuf se donne sa propre carto.** Écrire dans celle du décor commun
s'équilibre peut-être à la ligne près, mais l'entité ACTIVE, elle, ne revient
pas toute seule — et le défaut se lit chez un fichier qui ne parle pas du même
sujet. C'est la même règle que `test_82` et `test_83` appliquent déjà à la
LANGUE.

### LE PALIER DE SOUMISSION, et quatre points relevés à l'usage (2026-11-22)

Cinq demandes d'un coup. L'une est un changement de modèle ; les quatre
autres sont des détails, dont deux cachaient un défaut.

#### ⚠️⚠️ Une carto ne part à l'examen que COMPLÈTE — `Code/socle_activites.py`

« Sur une carto de cent activités, si on dépose une demande dès qu'on met un
truc, on va faire des centaines de demandes pour remplir la carto. » Le
reproche porte sur le coordinateur : c'est lui qui arbitre, et un arbitre noyé
n'arbitre plus. Une première version se soumet donc d'un bloc.

**La règle** : chaque activité porte un GARANT, au moins une TÂCHE et au moins
un OUTIL. Sans exception — c'est ce qui la rend lisible, elle ne se négocie pas
activité par activité.

- ⚠️ **« Chaque activité » veut dire chaque activité que la carto TIENT.** Un
  **RÉSULTAT** (`is_result`) est une SORTIE, pas un travail ; une activité
  **`external` / `extco`** appartient à une AUTRE carto. Les exiger rendrait le
  palier inatteignable, donc inutile. La seconde règle n'est pas inventée ici :
  `activities_map` écarte déjà ces deux sous-types quand il cherche « la vraie
  activité ». Un RENVOI, lui, n'a même pas de ligne (`_sync_carto_to_db` ne crée
  d'activité que pour les formes de `_ACTIVITY_TYPES`).
- ⚠️ **Le palier se libère TOUT SEUL.** Une fois la carto complète il ne gêne
  plus : corriger une seule tâche passe le contrôle, puisque le contrôle est
  « la carto est complète ». Il n'y a donc PAS de « première version » à
  marquer, ni de drapeau à tenir — ce serait un état de plus dont on pourrait
  se tromper, et qui resterait faux une fois mal posé.
- ⚠️⚠️ **Ce qui est mesuré, c'est la carto PLUS LE BROUILLON.** Sur une carto
  commune, tout ce que le champion écrit est DÉTOURNÉ dans son brouillon
  (`ecriture.porte` → 202) et n'atteint jamais la base. Mesuré sur la base
  seule, le palier annoncerait « 0 activité complète » quel que soit le travail
  fourni, et ne se franchirait **jamais**. On SIMULE donc le brouillon.
- **`propositions_activite.simuler(cr, mesurer)`** rejoue les gestes par le
  chemin NORMAL (`_appliquer_gestes`, extrait de `rejouer`) puis **annule dans
  un `finally`**. Une seconde implémentation de « ajouter une tâche » finirait
  par diverger de celle qu'on applique vraiment — c'est l'argument qui a fait
  de `ecriture.py` une porte centrale, et il vaut ici.
- ⚠️ Le coût ne grandit pas avec la carto : **quatre requêtes**, cadrées par un
  JOIN sur l'entité et jamais par un `IN (…)` d'identifiants (une carto du
  pilote en porte 601, et SQLite borne le nombre de paramètres). La simulation,
  elle, coûte un rejeu : elle n'est PAS calculée au rendu de chaque page, mais
  à l'ouverture de la fenêtre et à l'envoi.
- ⚠️ Un geste **qui ne s'applique plus** (une tâche supprimée entre-temps) ne se
  mesure pas : on le DIT (`rejeu`) et le socle est déclaré incomplet. Mesurer
  « ce que les gestes d'avant donnent » laisserait croire à un envoi que
  `rejouer` refuserait de toute façon.
- **La garde vit dans la ROUTE** (`POST /api/propositions/envoyer` → 409
  `socle`), après le contrôle « vide » : le bouton éteint de la fenêtre n'est
  pas une sécurité. ⚠️ Et la ligne du brouillon est **reprise après la
  simulation** — celle qu'on tenait est expirée par le rollback.
- **L'écran** (`GET /api/propositions/socle`, bloc ambre dans la fenêtre) :
  combien d'activités sont prêtes, ce qui manque par famille, puis la liste
  **nommée** (15 au plus, « et n autres »). Un compteur seul n'apprend rien —
  on vient chercher QUOI remplir.

⚠️⚠️ **Ce que la demande a mis au jour : `/tools/add` et `/tools/delete`
n'étaient PAS dans `_SEGMENTS`.** Un champion se faisait donc refuser l'ajout
d'un outil avec le code `lecture_seule` — **le motif réservé à `user`**, alors
que proposer est précisément ce qui l'en distingue. Sans ce correctif le
nouveau palier aurait été **insatisfiable** : on ne peut pas exiger un outil
par activité si l'outil ne peut pas se proposer. Même famille que le garant,
oublié de la même liste le 05/11. Trouvé en se demandant, AVANT d'écrire les
tests, si un champion peut réellement satisfaire la règle.
- ⚠️ Un OUTIL n'appartient à aucune activité : c'est le catalogue de la carto,
  et il se rattache à une TÂCHE (`task_tools`). L'activité d'un geste d'outil
  se lit donc par sa tâche (`_activite_de_la_tache`), et « au moins un outil »
  veut dire « au moins une tâche de cette activité est outillée ».

ℹ️ **La sauvegarde de ce qui est saisi existait déjà** : le brouillon
(`ActivityChangeRequest` en `status='draft'`, un par auteur et par carto) porte
les gestes depuis le 19/10 et survit à la déconnexion. Ce qui manquait n'était
pas la persistance, c'était le palier et la phrase qui l'explique.

Tests : `tests/test_159_palier_soumission.py` (58 cas) ; `test_112` et
`test_114` franchissent le palier en base (`_franchir_le_palier`) — ils portent
sur la MÉCANIQUE du dépôt, pas sur le palier, et ce qu'ils déposent est la
correction d'une carto déjà remplie. ⚠️ Trois de leurs assertions comptaient
des lignes (`count() == 1`) : elles comparent désormais des NOMS, puisque la
carto porte maintenant la tâche du palier.
⚠️ **Deux cas lisaient un `.py` comme un SOURCE** — septième occurrence du
piège : ils auraient rougi à chaque exécution dans l'arbre d'image, compilé en
bytecode. Réécrits sur le COMPORTEMENT plutôt que sautés, et les deux y
gagnent : le coût se mesure sur le SQL réellement envoyé (le nombre de
paramètres ne bouge pas quand on ajoute 30 activités), et le refus du serveur
s'éprouve en appelant la route. ⚠️ Un `NOT IN (?, ?)` subsiste dans le SQL —
les deux sous-types hors carto : ce n'est pas une liste d'identifiants, elle
ne grandit pas. C'est le NOMBRE DE PARAMÈTRES qu'on garde, pas le mot `IN`.

#### ⚠️⚠️ L'unité d'une ligne de rôle n'était jamais LUE — 60× trop peu

« Pour l'analyse de rôle rajouter comme unité heure et jours (actuellement que
minute). » Le sélecteur manquait, mais le défaut était plus bas : `addRoleRow`
recevait déjà un paramètre `unit`, **nommé `_unit` et jamais employé**, et le
serveur écrivait `float(ln.get('duration') or 0)` — la valeur BRUTE. Une durée
saisie en heures se serait donc enregistrée en MINUTES, sans la moindre erreur
pour le dire. Même famille que les `<option>` sans `value` du 03/11.
- `_duree_ligne_role(ln)` convertit aux DEUX sites d'écriture (création et
  `PATCH`), et la colonne « Durée (min) » redevient « Durée » puisqu'elle n'en
  impose plus une. ⚠️ Sans renommer la clé partout : `time.col_duration_h` sert
  à quatre tableaux dont trois affichent de vraies heures.
- ⚠️ `time.col_duration_min` n'a plus de lecteur : elle quitte le catalogue avec
  lui.

#### Une analyse neuve part d'un formulaire VIDE

`viderSaisie(type)` existait et n'était câblé nulle part : les quatre portes de
l'accueil, l'état vide du rôle et le bouton « Chiffrer … » ouvraient l'écran
avec ce qu'il restait de la saisie précédente — nom compris. `ouvrirNeuve()`
sort du mode modification, ouvre, puis vide.

#### La page Carte : l'ÉDITEUR rentre dans les réglages, les entités en sortent

Les deux boutons sont échangés. « Ouvrir l'éditeur » prend la première place du
bloc repliable, « Gérer les entités » devient la pilule pleine qui reste
dehors — c'est elle qu'on vient chercher en arrivant sur la page.

#### ⚠️⚠️ LE NIVEAU EST POSÉ SUR LA LIGNE D'EAU (page Compétences)

« Intensifier le découlement de l'activité vis-à-vis de ses résultats dans la
carte bleue : visuellement, le lien entre les deux doit être plus marqué. »

Le reproche était mesurable. Le niveau de l'activité s'écrivait en 48 px
au-dessus du bassin, et la ligne d'eau — **295 px plus bas, relevé à l'écran** —
disait exactement la même valeur. Deux énoncés d'une seule chose, que rien ne
reliait.

Le chiffre est donc posé **SUR la surface**, dans un **couloir réservé** à
droite du bassin (`--rail`), et la ligne d'eau **traverse ce couloir** pour
venir finir sous lui. Poser une note déplace le repère le plus bas, donc l'eau,
donc le chiffre : mesuré au banc, `bottom` du cartouche et `height` de l'eau
suivent la même valeur (240 → 85,5 → 240). Le découlement se REGARDE.

- ⚠️ **Tout le bassin s'arrête au couloir — SAUF la surface.** L'eau, les
  graduations, l'attendu et les repères prennent `right: var(--rail)` ; la
  surface garde `right: 0`, parce que **c'est elle qui fait le lien**. Mesuré :
  18 à 36 px de trait nu entre l'eau et le cartouche, selon la langue.
- ⚠️⚠️ **Le CHIFFRE est centré sur la ligne, pas la boîte.** Le JS ancre le
  cartouche à `basY(niveau)` et une `margin-bottom` négative (la moitié du
  chiffre plus le rembourrage bas) le descend d'autant. Mesuré : **0 px**
  d'écart entre le centre du chiffre et la surface, aux cinq niveaux.
- ⚠️⚠️ **Les deux bords du bassin lui réservent sa moitié.** `basY(0)` vaut
  `bas` et `basY(4)` vaut `h - haut` : centré sur la ligne, le cartouche
  déborde par le fond au niveau 0 et par le ciel au niveau 4. `BAS` passe de
  `{bas: 16, haut: 46}` à `{bas: 34, haut: 60}` — 26 px passent sous la ligne,
  52 restent au-dessus. Mesuré : 6 px de marge en bas, 7 en haut.
- ⚠️ **La pastille d'écart ne passe JAMAIS à la ligne** (`nowrap`) : deux
  lignes et le cartouche grandit de 12 px, donc sort du bassin au niveau 4.
  C'est l'ANGLAIS qui décide — « below target · −3 » fait 92 px contre 70 pour
  « en écart · −3 ». Les sept activités du banc relues en anglais : le plus
  large cartouche fait 112 px pour 122 disponibles.
- ⚠️ Elle s'empile **au-dessus** du chiffre, jamais en dessous, où le fond du
  bassin la rognerait au niveau 0.
- ⚠️ **`bottom: 0` par défaut** : `majBassin` le pose à chaque rendu, mais sans
  valeur de départ il vaudrait `auto` — c'est-à-dire le HAUT du bassin, l'exact
  contraire du fond. Relevé à l'écran.
- ⚠️ **`majBassin` ne REÉCRIT rien** : le chiffre et l'écart sont écrits par
  `majNiveauTenu`, dont c'est le métier, et le bassin ne touche qu'à ce qui
  BOUGE. Un `innerHTML` dedans le ferait sauter d'un niveau à l'autre au lieu
  de l'y faire monter — c'est le cliquet qui l'a rappelé.
- **La couleur du chiffre est celle de la SURFACE** (et le filet du cartouche
  la reprend) : le chiffre et le trait sont une seule chose, ils changent de
  teinte ensemble. Sans cela le lien ne tiendrait que par la position.
- Le bloc `.ou-niv` disparaît : l'activité reprend toute la largeur de l'en-tête,
  et `cl_tenu` quitte le catalogue avec son dernier lecteur. Le libellé ne
  manque pas — le bassin ne parle que de ça, et le « i » y explique la règle du
  minimum.

Tests : `tests/test_140_classeur_evaluation.py` +8 cas
(`TestLeNiveauEstPoseSurLaLigneDEau`), **8 défauts remis un par un, 8 cliquets
tombés** ; un cas de `test_109` réécrit (il affirmait que l'en-tête porte le
niveau). Éprouvé au banc (`tools/devrun_competences.py`) dans les deux langues,
aux cinq niveaux plus le cas NULL : 0 px d'écart chiffre/ligne, 0 débordement,
0 croisement avec les pastilles de repère, 0 erreur console.

### LE BROUILLON SE VOIT, ET IL S'OUTILLE (2026-11-23)

Suite immédiate du palier du 22/11. Il marchait comme demandé — et c'est en
s'en servant que le défaut est apparu : « on crée une tâche, elle ne s'affiche
pas dans l'activité mais se rajoute à la proposition… on ne peut consulter ce
que l'on a fait qu'à partir du truc en haut de page ; si on a 150 activités,
cela va être trop chiant. De plus, comment j'associe un outil à une tâche si
elle n'apparaît pas dans l'interface ? »

#### ⚠️⚠️ Le palier était INFRANCHISSABLE, et personne ne pouvait le voir

La seconde question n'était pas une gêne d'ergonomie, c'était un mur. Le
palier exige **au moins un outil par activité** ; un outil se rattache à une
**TÂCHE** (`task_tools`) ; et sur une activité vierge la tâche que le champion
vient d'écrire n'existe **pas en base** — elle est dans son brouillon, elle
n'a aucun identifiant à viser. Sur toute activité sans tâche préexistante, le
palier ne pouvait donc **jamais** se franchir.

⚠️ **Et on ne peut PAS écrire l'identifiant que la simulation vient de
produire** : il naît d'un `flush` annulé juste après (`simuler` rejoue puis
annule dans un `finally`), et le vrai rejeu, à l'approbation, en donnera un
autre. Un geste qui le porterait viserait une ligne au hasard.

**Les références locales** (`Code/propositions_activite.py`) : un geste désigne
le **RANG** du geste qui crée l'objet — `b:0` — et le rejeu le résout par ce
qu'il vient réellement d'écrire (`_resoudre_refs`, `_id_cree` lit le `id` que
la vue renvoie). Trois gardes, toutes éprouvées :

- ⚠️ **Une référence vers un rang qui n'a RIEN produit lève** (`EchecDeRejeu`,
  motif `ref: b:N`). Laisser passer la chaîne « b:0 » la ferait arriver
  jusqu'à `int()` dans la route visée : le rejeu s'arrêterait sur une pile
  Python au lieu d'un motif lisible.
- ⚠️⚠️ **Retirer un geste emporte ce qui le visait, et RENUMÉROTE le reste.**
  `retirer_geste` enlève par index : sans cascade, l'outil posé sur la tâche
  qu'on vient d'enlever a perdu son sujet et le rejeu buterait dessus à
  l'approbation ; sans renumérotation, « outiller la tâche du geste 2 » se
  mettrait à désigner le geste 1, c'est-à-dire n'importe quoi.
- ⚠️ `lire_geste` reçoit `deja` (les gestes déjà rangés) : c'est de là que le
  geste d'outillage tire son **activité**, donc la fiche sous laquelle on
  viendra le relire. Sans elle il partait « hors activité ».

Mesuré au banc, carto commune de 36 activités : une tâche et un outil déposés
depuis l'écran → `/api/propositions/socle` rend **1 activité prête sur 36**.
C'est la preuve de bout en bout : le brouillon compte, et un champion peut
désormais satisfaire le palier sans qu'un coordinateur intervienne.

#### Ce qu'on a écrit se voit LÀ OÙ on l'a écrit

Un bloc ambre « En attente d'envoi » se pose dans la fiche de chaque activité
concernée : une carte par geste, le verbe, l'objet en Fraunces, et une croix
pour le retirer sans remonter en haut de page.

- ⚠️ **L'ancre est `data-acp-act` sur `.tasks-section-modern`, PAS sur
  `#tasks-list-<id>`** : ce dernier n'est rendu que si l'activité porte déjà
  une tâche — c'est-à-dire jamais dans le cas qui nous occupe.
- ⚠️ **Les cartes ne se confondent jamais avec les vraies lignes** : fond
  ambre hachuré, bordure en pointillé, et la phrase qui dit qu'elles ne sont
  pas encore dans l'activité. Ambre comme le bandeau et la fenêtre — c'est la
  couleur de la gouvernance, pas celle de la page.
- **Une tâche en attente s'OUTILLE** : un bouton ouvre, DANS la carte, la liste
  des outils de la carto plus un champ pour en nommer de nouveaux.
  ⚠️ **Un seul geste** (`/tools/add` avec `new_tools`) : passer d'abord par
  `/gestion_outils/api/tools` pour créer l'outil — ce que fait le formulaire
  des tâches existantes — donnerait un second geste détourné dont on ne
  pourrait pas lire l'identifiant.
  ⚠️ Pas une fenêtre : on en ouvrirait une par tâche, et une modale cacherait
  justement la tâche qu'on outille.
- Un geste qui en VISE un autre se range **sous** lui (pastilles d'outil sous
  leur tâche) : à plat, on ne saurait pas quel outil va sur quelle tâche.
  `/api/propositions/brouillon` renvoie pour cela `vise` — des **RANGS**, pas
  des identifiants ; le corps de la requête ne sort toujours pas.

⚠️⚠️ **L'observateur se mordait la queue.** La liste des activités arrive par
lots de 20, donc un `MutationObserver` sur `#main-activities-list` replace les
cartes. Mais les cartes posées vivent DANS ce sous-arbre : ouvrir le choix des
outils était une mutation de plus, `placer()` repartait de zéro 60 ms plus
tard, et le formulaire disparaissait sous le pointeur. Mesuré au banc. On ne
replace donc que si la **liste des fiches** a changé (signature des
`data-acp-act`), jamais sur une mutation quelconque.

#### ⚠️⚠️ La fenêtre de bienvenue revenait à CHAQUE page — un 403

« Avec le compte de Noe Berthier, à chaque fois que je vais sur une nouvelle
page j'ai la pop-up de bienvenue. » La console le disait :
`POST /api/bienvenue/vue → 403`. La route n'était pas dans les exemptions de
la porte d'écriture : pour tout compte sans droit d'écriture, la signature
n'était **jamais** écrite, et la fenêtre revenait indéfiniment. Elle n'écrit
aucune donnée métier (une ligne dans `welcome_seen`), porte sa propre garde
(401 sans compte) et calcule la signature elle-même — elle rejoint la première
famille d'exemptions, celle de `/parametres/set_language`.

#### ⚠️⚠️ Le chatbot : refusé, et refusé EN FRANÇAIS

Deux défauts dans le même écran, tous deux visibles sur la capture du pilote.

1. **`/api/chatbot/chat` était refusé par la porte.** Il n'écrit pas une
   ligne : il appelle l'IA et rend du texte. Il est en POST parce qu'il porte
   un historique. Exempté. ⚠️ `/api/chatbot/inject`, lui, écrit : il reste
   sous la porte, et **se propose** désormais comme n'importe quel ajout de
   tâche (famille `task`, objet = les libellés de la fournée). Sans cette
   ligne un champion recevait `lecture_seule` — le motif réservé à `user` —
   pour un geste qu'il peut faire à la main. Même famille que l'oubli du
   garant (05/11) et de `/tools/add` (22/11).
2. ⚠️ **Le motif du refus était une PHRASE FRANÇAISE en dur.** `MOTIF` porte
   désormais des CLÉS (`porte.lecture_seule`, `porte.non_connecte`), résolues
   par `t()` à la réponse. Le texte part tel quel dans le JSON et plusieurs
   écrans l'affichent sans le relire — le chatbot en tête
   (`_appendBotMessage('❌ ' + data.error)`) : « lecture seule » s'écrivait en
   plein milieu d'une interface anglaise. Le CODE, lui, ne change pas : c'est
   lui que le JS teste.

⚠️ **Et cinq phrases restaient en dur dans `chatbot.js`**, dont trois que
`_clearDraft()` **réécrivait par-dessus le gabarit pourtant traduit** — c'est
là que le français revenait, dès l'ouverture de l'assistant. Exactement le
piège de la modale « Traduire les soft skills ». Six clés neuves, et le
sous-titre du bouton suit désormais le **régime d'écriture** : on ne promet
pas un ajout immédiat à qui va déposer une proposition.
⚠️ L'id `chatbot-inject-label` doit survivre à cette réécriture : c'est lui que
`_updateInjectBtn` remplit, et sans lui le bouton reste à « 0 tâche ».
⚠️ Une injection DÉTOURNÉE (202) ne recharge plus la fiche : annoncer « n
tâches ajoutées » puis recharger montrerait une liste inchangée.

**La peau** reprend le vocabulaire des propositions — en **VIOLET** (« on garde
le violet, je veux pas de orange ») : en-tête sur un fond de nuit avec son
halo, Fraunces sur les libellés de tâche, **rail numéroté** (le numéro a sa
pastille ; collé au libellé, « T1. Peser » se lisait comme un bout du texte),
et le rapport INVERSÉ du bouton d'action — pastille pastel sur fond vif, avec
l'éclat au survol. Le vert a disparu : la famille de cet écran est le violet.
L'ambre ne reste qu'aux signaux SÉMANTIQUES (une tâche douteuse).
⚠️ Les tailles passent en **pixels** : `rem` ignore le `zoom: .8` de `body.pg`,
et un « 0.76rem » était rendu à 9,7 px réels — sous le plancher de 11.

#### Page Temps : rien n'est choisi tant que rien n'est choisi

« Cela présélectionne la première activité de la liste. » Trois `<select>`
sans option vide : le navigateur retenait la première activité de la carto, on
enregistrait une charge sur une activité que personne n'avait désignée, et
l'écran annonçait « enregistré ».

- Une option vide en tête des trois listes, `viderSaisie` les remet à vide (un
  `<select>` garde en plus le choix précédent d'une page à l'autre), et les
  quatre boutons refusent avec un message **sous le champ**, jamais un `alert`.
- ⚠️ **Le serveur refuse aussi** (`sujet_choisi`, 400 `sans_activite` /
  `sans_role` / `ligne_sans_activite`) : le masquage n'est pas une garde. Et
  la valeur arrivait jusqu'à `int('')`, c'est-à-dire un **500** — un refus se
  dit, il ne tombe pas.
- Les trois pré-remplissages n'interrogent plus `/activity_defaults/` sans
  identifiant, et le total comme le bilan de faiblesse reviennent à vide :
  laissés tels quels, ils décrivaient l'analyse précédente sous un formulaire
  neuf.

#### Le lien entre l'activité et CE QU'ELLE PRODUIT (vue d'ensemble)

« Rien ne fait le lien entre les deux. » On cliquait une barre à gauche, un
panneau changeait à droite, sous un titre — « SES marches de performance » —
dont le « ses » ne désignait rien.

Trois attaches, et **aucune ne demande de géométrie calculée en JS**, donc
rien à recalculer au redimensionnement :

1. la **TEINTE** : `--vo-c` est posée sur le DUO (pas sur le panneau — la
   barre choisie et le panneau vivent dans deux colonnes sœurs et doivent lire
   la même), et la barre, la flèche, le liseré du panneau et la pastille du
   sujet la lisent toutes ;
2. le **NOM** : le panneau nomme l'activité qu'il décrit (« Ce que produit · 
   *Valider le prototype* »), avec sa pastille de couleur ;
3. la **FLÈCHE**, posée dans la **gouttière** de la grille — les barres
   reposent toutes sur la même ligne de fond et `.esc` a une hauteur fixe,
   d'où un décalage constant. ⚠️ `top: 82px` est **mesuré à l'écran** (milieu
   des barres à 89 px du haut du panneau, flèche de 14 px) : relevé après
   correctif, **0 px d'écart**. Sous 1100 px réels les blocs s'empilent et la
   flèche regarde vers le bas.

⚠️ Pas de trait tiré de la barre jusqu'au panneau : il faudrait mesurer la
position de la colonne choisie à chaque rendu ET à chaque redimensionnement —
et dans ce volet, une mesure de mise en page n'est pas fiable.

#### Deux pièges déjà connus, revus ici

- ⚠️ **Un cliquet qui cherche une chaîne doit borner sa zone.** `#chatbot-inject-btn {`
  existe DEUX fois dans la feuille (la règle d'origine et la neuve) : `index`
  lisait la première, et le cas restait vert sur le défaut. `rindex`.
- ⚠️ **Et il doit lire la BALISE, pas une fenêtre de n signes.** Le contrôle
  de l'ancre `data-acp-act` cherchait `tasks-section-modern` dans les 120
  signes précédents — le commentaire qui l'explique s'est glissé entre les
  deux, et le cliquet est tombé sur sa propre explication. Septième
  occurrence de cette famille.
- ⚠️ `test_142` monkeypatchait `lire_geste` par un `lambda *a` : la signature
  prend désormais `deja`, et un faux qui ne l'accepte pas lève une TypeError —
  le cas n'éprouvait plus rien de ce qu'il dit éprouver.

Tests : `tests/test_162_brouillon_visible.py` (53 cas) ; **20 gardes retirées
une par une, 20 cliquets tombés**. `test_114` voit son cas sur la forme du
brouillon renforcé (`vise` s'ajoute, le corps ne sort toujours pas).

**Reste, et c'est un point à part** : les quatre lignes de « Ce qui vous
attend » (fenêtre de bienvenue) sont écrites au pluriel seul — « 1
modifications prêtes à envoyer ». Chacune demande sa paire singulier/pluriel
dans les deux langues ; ce n'est pas le sujet de cette passe.

---

### LA FENÊTRE DU PALIER, REPRISE — et le compte qui se lisait à l'envers (2026-11-23)

« J'aime le style, techniquement ça a l'air de marcher, mais l'agencement à
l'intérieur des sections n'est pas idéal. La première section ne fait aucun
distingo visuel, ne propose aucun filtre : comme tout a la même tronche, ce
n'est pas agréable d'aller chercher là-dedans. La deuxième prend de la place,
plein de petit texte, et surtout elle ne sert à rien : elle me dit 1 truc
manquant alors que j'ai rempli 30 % des activités. Et sur mon portable la
pop-up ne s'affiche pas en entier. »

Tout a été **mesuré avant d'être touché**, sur un portable 1366×768, carto de
36 activités, brouillon de 27 gestes :

| | avant | après |
|---|---|---|
| hauteur utilisée par la fenêtre | **676** des 960 px CSS | 920 |
| contenu à dérouler | **3191 px** pour 544 visibles | 1897 pour 545 |
| hauteur d'une ligne de geste | 86 px | **57** |
| le pied (Abandonner / Envoyer) | **dans** le défilement | hors |
| le panneau du palier | un pavé de **551 px** au milieu | une bande de 140 |

#### ⚠️⚠️ « 1 truc manquant » : le serveur avait raison, l'écran lisait faux

Relevé au banc : `manque = {garant: 0, outil: 26, tache: 26}` sur 36 activités.
Le compte était juste. Mais l'écran n'affichait **qu'une pastille PAR
FAMILLE** : quand une famille est déjà complète partout — et le garant l'est,
il vient de l'import carto — il n'en reste qu'**UNE**. On lisait « une chose
manque » là où **vingt-six activités** sont incomplètes.

Le chiffre de tête compte donc des **ACTIVITÉS** (`socle_restent`, total −
prêtes), avec une jauge ; les familles passent dans un détail **replié**, où
chacune dit sur combien d'activités elle manque.

⚠️ **Et la liste devient un plan de travail** : chaque nom ouvre son activité
(la fenêtre se ferme, la page défile jusqu'à la fiche, l'ouvre et la désigne
1,6 s). Sans cela elle restait un rapport — elle disait ce qui manque et ne
permettait pas d'aller le remplir. `NOMMEES` passe de 15 à **60** : on en
nommait 15 sur 26, « et 11 autres » sans dire lesquelles. La borne reste, elle :
une carto du pilote porte 601 activités.

⚠️ Les deux paragraphes de règle (pourquoi d'un bloc, et que rien n'est perdu)
passent derrière un « i » — ils occupaient 160 px de la hauteur utile, et
c'est le motif de la maison.

#### ⚠️⚠️ La fenêtre perdait 30 % de sa hauteur — `vh` passe par le zoom

`max-height: 88vh` sur `.acp-boite`. `body.pg` porte `zoom: .8` (ui-theme), et
les unités de fenêtre passent elles aussi par ce zoom : la fenêtre se bornait
à **676 des 960 px CSS** disponibles. C'est exactement le piège déjà écrit
pour la fenêtre de bienvenue — « pas de `vh` ici ». On se mesure sur le VOILE
(`.acp` en `inset: 0`, passé en flex avec un padding), et la boîte prend
`max-height: 100%`.

#### TROIS zones fixes, une seule qui défile

Le pied vivait DANS le corps : il fallait dérouler 3191 px de liste pour
atteindre « Envoyer ». Le gabarit porte désormais quatre zones sœurs — socle,
filtres, corps, pied — et seul le corps défile (`flex: none` sur les trois
autres, tenu par un cliquet).

- **Le pied tient sur UNE ligne** : le mot pour l'auteur en invite, puis les
  deux boutons. Le libellé au-dessus d'un champ d'une ligne coûtait 30 px.
  167 px → **73**.
- Resserrés en même temps : en-tête 130 → 114, filtres → 49 (une ligne, qui
  défile latéralement plutôt que d'en prendre une seconde).

#### La liste : groupée, distinguée, filtrable

- **Groupée par FAMILLE** — « les tâches avec les tâches, les savoir-faire
  avec les savoir-faire ». ⚠️ L'ordre affiché n'est donc plus celui du rejeu,
  et ce n'est pas une perte : **le numéro de chaque ligne reste son RANG
  RÉEL**, celui que `data-retirer` porte et que le serveur rejoue. Grouper ne
  change que la lecture — un cliquet le tient.
- **Un pictogramme et une couleur par famille**, et la couleur est celle de la
  PAGE où la donnée vit (Activités violet, Outils orange, Rôles vert,
  Compétences bleu). C'est la convention de la fenêtre d'import : elle veut
  dire quelque chose, ce n'est pas un arc-en-ciel.
- **Un filtre** : une pastille par famille PRÉSENTE (jamais les dix — on ne
  propose pas de filtrer sur rien), plus une recherche sur le nom de l'objet
  et sur l'activité.
  ⚠️ `input`, jamais `change` : sur `change` le filtre n'agirait qu'à la perte
  du focus, sans la moindre erreur pour le dire.
  ⚠️ Et on ne re-rend **que la liste** : réécrire la barre à chaque frappe
  ferait perdre le curseur du champ qu'on tape — le piège déjà payé sur les
  cartes du plan de formation et sur l'autre sens de l'import.
- **La ligne se resserre** : le verbe passe en méta à côté de l'activité,
  l'objet garde seul la police d'affichage. 86 px → 57.
- ⚠️ **Les familles se nomment au PLURIEL, sans article** (`acp.g_*`). Les
  `f_*` portent le leur — ils se composent en « Ajouter **la tâche** » — et un
  en-tête qui les reprend affichait « LA TÂCHE 8 », qui se lit comme un compte
  de la même tâche.

#### Et dans la fiche de l'activité

Les cartes en attente sont **groupées par famille** elles aussi, chacune sous
son en-tête, et la pastille de chaque carte porte le pictogramme et la couleur
de sa famille. À plat, une fiche qui porte six gestes de quatre natures se
lisait comme un tas. ⚠️ Les outils rattachés à une tâche en attente restent
NICHÉS sous elle : le groupement ne vaut que pour les gestes de tête.

#### Trois pièges, tous déjà connus

- ⚠️ **Le `gap` d'une boîte flex ne s'applique qu'entre ÉLÉMENTS** : le nom de
  l'activité, laissé en nœud de texte nu, donnait « AddManage Commercial
  Offer ». Troisième occurrence.
- ⚠️ **Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES** :
  celui qui interdit `change` dans le filtre s'est pris sur l'explication
  écrite juste au-dessus. Septième occurrence.
- ⚠️ **Le banc ne recharge pas les gabarits** : une zone ajoutée au gabarit
  n'existait pas dans le DOM tant que `devrun_partage.py` n'avait pas
  redémarré, et la mesure disait « socle: 0 » sans que rien ne soit cassé.

ℹ️ Deux fausses pistes écartées en chemin, et les deux venaient du banc, pas
de l'application : `/savoirs/add` attend `description` et non `name`, et les
contraintes vivent sous `/constraints/<id>/add` et non `/activities/
constraints/`. Dans les deux cas la porte a fait exactement ce qu'elle devait —
le second a d'ailleurs montré que le socle SAIT dire « l'étape n° 3 ne
s'applique plus ».

Tests : `tests/test_159_palier_soumission.py` passe de 58 à **70 cas** (les
trois cliquets qui affirmaient l'ancienne structure sont RÉÉCRITS sur la
nouvelle, pas supprimés) ; `test_112` voit son cliquet du rail réécrit sur le
groupement. Éprouvé au banc dans les deux langues.


### PRUNE & TILLEUL : la page Compétences change de feux (2026-11-23)

« Aucun des verts et des rouges n'est sympa. » Le reproche portait sur les
couleurs SÉMANTIQUES — rouge « autonomie non démontrée », ambre « écart au
requis », vert « niveau tenu » — et il était juste pour une raison qu'on ne
voit qu'en les posant sur la carte de nuit de la vue d'ensemble : **elles ont
été choisies pour du papier blanc.** Sur un bleu saturé, le rouge se ternit
et le vert vire à l'acide.

⚠️ **Quatre premières propositions ont toutes été refusées, et c'était le même
défaut quatre fois** : je ne déplaçais que la TEINTE — quatre rouges, quatre
verts, le même principe à chaque fois. Les six suivantes changeaient de
PRINCIPE (une sans aucun vert, où le niveau tenu est de la lumière ; une
entièrement désaturée ; une sombre et dense…), et chacune était montrée **sur
le fond de nuit, en barres du classement** — une couleur ne se juge ni sur du
blanc ni sur une pastille de 12 px. Retenue : **prune & tilleul**, qui déplace
les deux familles loin du rouge et du vert canoniques.

**Les jetons, et rien d'autre.** `static/competences.css` déclare deux échelles
de neuf tons (`--cv-g-02` … `--cv-g-80` pour le tilleul, `--cv-r-05` … `--cv-r-80`
pour la prune) et tout en dérive : `--cv-green` / `--cv-red`, les quatre
`--pal-vert-*`, les quatre `--pal-rouge-*`, la rampe du radar et celle de la
bande des notes. **154 valeurs écrites en dur** ont été remplacées dans la
feuille et dans le JS ; un balayage par teinte vérifie qu'il n'en reste aucune.

⚠️ **Le relief est dessiné en SVG par le JS** : ses couleurs sont des
ATTRIBUTS, pas des règles, donc aucun jeton CSS ne les atteint. Elles sont
posées à la main dans `competences_v2.js` — c'est le seul endroit du module où
une valeur se répète, et il faut y penser à chaque retouche de palette.

⚠️ **L'ambre a dû bouger, lui aussi.** Le tilleul est un jaune-vert : sur le
fond de nuit, l'or vif de l'ambre s'en rapprochait trop. Deux jetons dédiés
(`--cv-a-40` / `--cv-a-70`) le posent plus sourd et plus chaud — mais SEULEMENT
là, sur fond sombre ; sur les écrans clairs `--pal-ambre` ne bouge pas.

⚠️ **Une rampe doit rester MONOTONE.** La table de correspondance avait fait
tomber trois paliers du radar sur le même jeton (`--ax-v5`, `-v6` et `-v8`
devenus identiques) : le dégradé s'aplatissait au milieu sans que rien ne le
signale. Les deux rampes sont réécrites palier par palier.

⚠️ **Le contraste se vérifie, il ne se devine pas.** Les deux encres de texte
sont choisies pour tenir sur du blanc : `--cv-g-70` (#557c18) à 4,8:1 et
`--cv-r-60` (#b02a58) à 6,0:1. Un tilleul plus clair est plus joli et illisible.

**Les touches.** Le BLEU reste la couleur de la page : les deux nouvelles
familles n'y sont que des ponctuations, et chacune est posée là où la couleur
DIT quelque chose —
- le **trait de l'attendu** (barres du classement, ligne du bassin) passe au
  tilleul : c'est l'endroit où le tilleul commence ;
- la **jauge de couverture** part du bleu et FINIT en tilleul : pleine, elle
  atteint la couleur de ce qui est tenu ;
- la **sélection de texte**, sur toute la page ;
- **fermer une fenêtre** passe par la prune — le seul geste de ces en-têtes
  qui défait quelque chose ;
- le **« i »** et sa carte. ⚠️ Au passage : ce bouton lisait les dérivés doux
  de l'accent, donc il était **GRIS** partout (le piège des quatre dérivés
  déclarés sur `:root`, écrit plus haut). Il est tilleul.

⚠️ **Le cliquet qui interdit ces dérivés lit AUSSI les commentaires** : il
s'est attrapé sur l'explication ci-dessus, écrite dans la feuille. Huitième
occurrence de ce piège — ne jamais écrire la forme interdite dans un
commentaire, pas même pour expliquer qu'on l'évite.

⚠️ **Deux cliquets épinglaient une couleur EN DUR** (`#6ee7b7` dans le rail du
panneau des marches, un `#[0-9a-f]{6}` lu dans la surface du bassin) : réécrits
sur l'INTENTION — la même teinte des deux côtés — en acceptant un jeton aussi
bien qu'un hexadécimal. Un cliquet qui épingle une valeur tombe à la première
palette ; un cliquet qui épingle une égalité survit.

Éprouvé à l'écran dans les deux langues sur `tools/devrun_competences.py` :
galerie, vue d'ensemble, écran d'évaluation, séance, calendrier, fenêtres des
courbes et du plan.

---

### L'ÉCRAN D'ÉVALUATION, quatrième passe : le verdict en tête (2026-11-24)

« Techniquement parlant c'est bien, mais on se retrouve dans le visuel avec
trop de texte, trop d'info ; sur le graphe en bas on comprend rien, c'est
dommage. » Plus : le bleu des deux surfaces sombres, les trois boutons du bas,
les deux fenêtres, et « les courbes on supprime ».

Tranché sur **prototype cliquable à l'échelle réelle** — trois organisations du
bloc de gauche, trois densités de bleu, deux formes de boutons, les deux
fenêtres — avec les données de la capture. Retenu : **organisation 2 (« le
verdict en tête ») + densité 2**, la bande de données en densité 2 elle aussi,
« et le même bleu pour les deux, qu'on n'ait pas un bleu un peu décalé ».
C'est la onzième fois que la méthode évite une journée écrite pour rien.

Mesuré avant de redessiner : le bloc faisait **560 × 761 px** et portait **huit
étiquettes en capitales** — « OÙ VOUS ÊTES », « LE COLLABORATEUR », « LE RÔLE »,
« L'ACTIVITÉ », « CE QUE VOUS NOTEZ », « LA COMPÉTENCE PRINCIPALE », « ATTENDU »,
« EN ÉCART ». Les étiquettes étaient plus nombreuses que ce qu'elles
étiquetaient, et c'est ça, le « trop de texte ». Après : **448 × 401 px, UNE
étiquette.**

#### ⚠️⚠️ La cuve verticale est ABANDONNÉE — et le défaut n'était pas la métaphore

Le bassin échouait pour une raison précise, qu'il fallait mesurer pour voir :
**les NOMS des sorties étaient DANS le graphe**, et deux libellés anglais de
cinquante signes s'y chevauchaient et s'y tronquaient. C'est ça, « sur le graphe
en bas on comprend rien » — pas l'eau qui monte.

La piste va donc de gauche à droite, comme toutes les autres jauges de
l'application, et **les sorties sont SOUS elle** : une ligne chacune, le nom en
entier, le numéro qui la relie à sa carte de droite, sa jauge à quatre pas.
On y perd la métaphore de l'eau ; on y gagne 90 px de hauteur, la lecture, et
le correctif du vrai défaut. C'est l'arbitrage de cette passe.

- ⚠️ **NULL ≠ 0**, ici comme partout : une activité dont une sortie n'est pas
  notée n'a PAS de niveau — sa piste est **hachurée** jusqu'au plus bas de ce
  qu'on sait, pas remplie à zéro, qui voudrait dire « non démontré ».
- ⚠️ **Un socle de 10 px dès qu'un niveau est POSÉ** : à largeur nulle, le
  niveau 0 se confondrait avec « pas de niveau du tout ». C'est la décision
  déjà prise pour les barres du classement, et les deux absences ne se
  corrigent pas de la même façon.
- ⚠️ **La règle du MINIMUM se voit** : la ligne qui retient le niveau est mise
  en avant. C'était une phrase derrière un « i ».
- ⚠️ **Le trait de l'attendu tombe SUR sa graduation.** Posée en
  `space-between`, la graduation répartit les SPANS, pas leurs centres : le
  « 3 » tombait à 291 px quand le trait, lui, est à 75 % de la voie, soit 293.
  Les deux sont posés à la même fraction et centrés dessus. Mesuré après :
  **0,0 px d'écart**.
- ⚠️ **Sur place, jamais réécrite** : la piste S'ÉTEND quand on pose une note,
  et c'est ce mouvement qui fait comprendre la règle.

#### Le verdict en tête, et une seule étiquette

Le niveau de l'activité et son écart se lisaient **deux fois** : en 48 px
au-dessus du bassin, puis 295 px plus bas sur la ligne d'eau (c'était le
correctif du 22/11 — il a tenu une journée, et la refonte le remplace par plus
simple). Ils sont posés **une seule fois**, à côté du nom de l'activité.

- ⚠️ `[data-niv]` garde SON contrat : il porte le chiffre ET le « /4 », parce
  que `majNiveauTenu` y écrit sans réécrire le bloc de nuit.
- ⚠️ **L'écart ne se replie JAMAIS** : « below target · −2 » fait 92 px en
  anglais contre 70 en français, et sur deux lignes la rangée grandit sous le
  nom de l'activité.
- ⚠️ **Les trois étiquettes de la chaîne tombent à l'ŒIL et restent dans
  l'`aria-label`** : elles nommaient ce qui se reconnaît sans elles — une
  personne, un rôle, une activité — mais un lecteur d'écran, lui, ne lit pas la
  chaîne d'un coup d'œil.
- La description de la compétence passe derrière un « i ». C'est le motif de la
  maison : une phrase passe derrière un « i », elle ne disparaît pas.

#### ⚠️ La typographie se mesure en PIXELS RÉELS — le prototype ne le sait pas

`body.pg` porte `zoom: .8`, et le prototype était écrit dans une page qui ne le
porte pas : ses valeurs arrivent ici **20 % plus petites**. Relevé au banc avant
correction — graduation **9,6 px réels**, nom d'une sortie **10,4**, maillon de
la chaîne **10,0**, écart **8,0**, étiquette **8,4** — quand le plancher de
l'échelle typographique est **11 px réels**. Ce qu'on LIT y remonte (nom 11,6 ·
graduation 11,2 · niveau d'une sortie 12) ; les étiquettes en capitales restent
à la taille des étiquettes de cette page, et il n'en reste qu'UNE.
ℹ️ Toute la page Compétences tourne sous ce plancher pour son texte secondaire
(`.cl-rb` 10,4 · `.pal-m` 9,6 · `.ev-retour` 10,4) : c'est un chantier à part,
comme les quatre dérivés de l'accent.

#### UN SEUL BLEU pour les trois surfaces sombres

« Qu'on n'ait pas un bleu un peu décalé et un effet de con. » Le bloc de
gauche, la bande de données et l'en-tête d'identité portaient **trois dégradés
différents**, dont un finissait sur `#0b1120` — presque du noir dans une carte
blanche. Une seule paire de bouts (`--nuit-1: #1d2c56`, `--nuit-2: #2c58b6`),
et **seul l'ANGLE change** d'une surface à l'autre : une bande large et un bloc
haut ne se traversent pas pareil.
⚠️ Ce sont DEUX déclarations — l'en-tête écrit son dégradé, l'ardoise lit le
jeton `--nuit` — et un cliquet compare les deux : si l'une change, l'autre doit
suivre.

#### Les trois boutons, et « Les courbes » qui part

« Les boutons de formation et technicité ne sont pas top, c'est écrit en petit
et en bas. » Chacun porte désormais sa pastille d'icône, son nom, et **CE QU'IL
CONTIENT** — c'est la valeur qui dit s'il faut l'ouvrir.
⚠️ **RENVERSEMENT** de la règle du 11/11 (« rien à annoncer ne s'annonce pas ») :
elle venait d'une rangée de QUATRE pastilles où la valeur partageait la ligne du
nom et faisait déborder la colonne. Trois boutons, deux lignes : « aucun
domaine » tient, et il dit quelque chose — on sait qu'il n'y a rien sans ouvrir.
⚠️ **Le troisième n'existe que pour le développeur** : un collaborateur n'en voit
que deux, et trois colonnes figées lui laissaient un vide à droite qui a l'air
d'un défaut. La bascule se fait sur le NOMBRE d'éléments
(`:has(.cl-rb:nth-child(3))`) — `auto-fit` ne sait pas la faire, il compte des
pixels. C'est le cas de `.wp-portes` (fenêtre de bienvenue).

#### ⚠️⚠️ La fenêtre des courbes s'en va, et la frise avec elle

« Elles sont déjà accessibles, donc la pop-up à deux pages des courbes ça
dégage. » Les deux schémas n'étaient PAS accessibles de la même façon : le
relief des VALEURS se lit sur la vue d'ensemble, **la frise des NIVEAUX n'avait
que cette fenêtre**. Elle s'en va avec — ce n'est pas un oubli, c'est le prix de
la suppression, et il est écrit.

Partis : la fenêtre, `rendreCourbes` / `rendreValeurs` / `rendreOngletsCrb`,
`friseSvg`, `legendeHistorique`, `dateCourte`, les `.hi-*`, `.cv2-histo`, et
**34 clés de catalogue** (10 `h_*`, 7 `crb_*`, `cl_courbes`, `ou_titre`…).
Une clé qu'on retire en même temps que son seul lecteur ne laisse rien derrière
elle. `GET /mastery/historique/` n'est plus appelé par aucun écran ; la route
reste (elle est testée, et c'est une lecture légitime de l'API).

⚠️ **Et le retrait a mis au jour 130 lignes de CSS mort** que le CLASSEUR du
11/11 avait rendues muettes sans le dire : l'axe partagé (`.cv2-rg`, `.rg-*`,
`.ax-grad`, `.p-zone`, `.cv2-lv` et les jetons `--ax-*`). Mesuré : aucun n'existe
dans le JS ni dans le gabarit, et rien d'ailleurs ne lit ces jetons. **Supprimer
une section de feuille, c'est emporter ce qui s'y trouvait pour d'autres** — la
leçon inverse est écrite plus haut, et les deux valent.

⚠️ `basculerHisto` avait **deux dispositions** : à côté sur la bande de la vue
d'ensemble, empilée dans la fenêtre. La fenêtre partie, le seul appelant est la
bande, qui construit toujours son `.pal-evo-duo` : la branche empilée était
injoignable, et son bouton de fermeture par le bas part avec elle.

#### La fenêtre TECHNICITÉ, refaite

C'était un formulaire nu — un nom, **deux menus déroulants du système**, une
pastille d'écart. Elle dit maintenant **d'abord à quoi ça sert** (un domaine
technique, c'est le terrain sur lequel l'activité se joue, et c'est un AXE À
PART), puis montre chaque domaine en carte, et range l'ajout en bas avec ses
deux champs **étiquetés** — un `placeholder` disparaît dès qu'on tape.

- ⚠️ **Des CRANS, plus un `<select>`** : c'était le seul endroit de cette page
  où l'on posait un niveau autrement, et un menu déroulant arrive avec ses
  styles système au milieu d'un écran qui n'en a aucun.
- ⚠️ **CINQ crans, et non la jauge à quatre pas de la maquette** : l'échelle
  technique distingue le niveau 0 (« aucun ») de l'absence de niveau (NULL).
  C'est la distinction que tout le module tient, et quatre pas ne savent pas
  l'exprimer. Avec la gomme — **à l'écart des crans**, effacer n'est pas un
  niveau de plus — chaque valeur du modèle est atteignable.
- ⚠️ **Le requis en creux, le démontré en plein** : une cible se dessine, elle
  ne se remplit pas.
- ⚠️ Le verdict dit ce qu'il EST (« en écart · −2 », « tenu »), pas un nombre
  nu — et avec le **signe moins** (U+2212), que le reste de la page écrit :
  deux glyphes pour le même signe sur le même écran donnent l'air d'un défaut
  d'impression.
- 32 règles mortes retirées au passage (`.cv2-domrow`, `.cv2-domsel`,
  `.cv2-bloc--tech`). ⚠️ `.cv2-emptydom` RESTE : la liste des capacités s'en
  sert encore.

#### La fenêtre PLAN DE FORMATION, aérée

La **structure ne bouge pas** — c'est elle qui rend le plan modulable, et elle
est juste. Ce qui change, c'est la densité : les trois micro-champs d'une étape
(objectif, livrable, réussi quand) étaient écrits en 13 px, soit **10,4 px
réels**, et le panneau de droite n'avait que 258 px pour un verdict qu'on vient
lire. Fenêtre 940 → **1 000 px**, panneau 258 → **318 px**, champs 14 px,
chiffres du verdict 15 → 19 px.

⚠️ **« Caler au plus juste » lisait DEUX des quatre dérivés de l'accent** —
`--pg-accent-border` et `--pg-accent-soft`, déclarés sur `:root` où
`--pg-accent` vaut encore le gris par défaut : son filet et son survol étaient
GRIS sur une page bleue. Le mélange s'écrit SUR PLACE. Le correctif de fond
(déplacer les quatre dérivés dans chaque `.page--*`) **n'est toujours pas
fait** : ~35 règles de cette feuille les lisent encore, et cela se décide en
regardant les neuf pages.

#### ⚠️ Trois pièges, et deux d'entre eux pour la énième fois

- ⚠️ **Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES.** Le
  contrôle « la fenêtre n'existe plus » s'est attrapé sur le commentaire qui
  explique le retrait — et ce commentaire NOMME ce qui est retiré. **Neuvième
  occurrence** dans ce dépôt.
- ⚠️⚠️ **Un cliquet doit viser l'EMPLOI, pas la présence du nom.** Deux cas
  sont restés VERTS sur le défaut remis : `est-bas` survivait dans une branche
  de ternaire morte (`false ? ' est-bas' : ''`), et `aria-label` survivait dans
  une flèche vidée de son contenu. Ils visent maintenant le fragment exact du
  gabarit.
- ⚠️ **`.ev-corps` existait TROIS fois** dans la feuille. Le retrait de
  `.cv2-crb-win` de son sélecteur a cassé deux ancres de cliquet qui lisaient
  « la » règle : les deux adjacentes sont fusionnées, et l'ancre vise
  explicitement la seule écrite sur plusieurs lignes.

Tests : `tests/test_148_technicite_et_plan.py` (12 cas, NEUF), `test_140`
(deux classes du bassin réécrites en `TestLaPistePorteLaComparaison` et
`TestLeVerdictEstEnTETE`, plus `TestLesCourbesQuittentLaPage`), `test_109`,
`test_145`. **14 défauts remis un par un, 14 cliquets tombés** — dont les deux
qui ne gardaient rien au premier essai. Éprouvé au banc
(`tools/devrun_competences.py`) à 1600 px dans les deux langues : le bloc, les
deux fenêtres, un domaine technique créé puis noté, un plan proposé — **zéro
fuite française sur l'écran anglais** (134 textes relevés, attributs compris ;
tout ce qui reste en français est une DONNÉE du banc), zéro débordement
horizontal, zéro erreur console.

### LE LIEN : la flèche n'avait que sa pointe (2026-11-24)

« Dans le rendu de la flèche on a que la pointe dans l'app, c'est dommage ; on
perd donc aussi l'animation qui faisait son charme. » Le reproche était exact,
et il visait une décision écrite ici même.

La maquette **« L'entre-deux »** comparait **cinq mouvements** à l'échelle
réelle pour relier le classement au panneau des marches, et le n° 1 — **« Le
lien »** — avait été retenu : *« il se trace du niveau de la barre jusqu'au
panneau, puis la pointe se pose »*. Ce qui a été livré, c'est **la pointe
seule** : un triangle de bordure (`border-width: 7px 0 7px 9px`) posé à un
`top: 82px` fixe. Sans tige, rien ne part de la barre, donc rien ne bouge
quand on en change — et l'animation n'avait plus de support.

#### ⚠️⚠️ Le prétexte était faux, et il confondait deux choses

La note d'alors disait : *« Pas de trait tiré de la barre jusqu'au panneau :
il faudrait mesurer la position de la colonne choisie à chaque rendu ET à
chaque redimensionnement — et dans ce volet, une mesure de mise en page n'est
pas fiable. »*

Elle mélangeait **ce que l'application sait faire** et **ce que je sais
vérifier**. Mesurer une grille au rendu est le pain quotidien de cette page
(la bulle du « i » le fait déjà) ; et la seconde moitié était fausse aussi :
le volet mesure très bien **dès qu'on lui pose une taille**. Les rects à 0×0
qui m'avaient fait écrire cela venaient d'un volet **replié**, sans viewport —
`window.innerWidth` valait **0**. Avec `resize_window`, les mêmes mesures
sortent justes au dixième de pixel.

⚠️ Règle qui en découle : *un volet replié rend TOUT à zéro.* Avant de
conclure qu'une mesure est impossible, poser une taille et relire.

#### Ce que le lien demande, et ce qu'il coûte

- **DEUX points relevés sur la carte**, et deux seulement : le **haut de la
  barre choisie** — c'est-à-dire son NIVEAU — et la **pastille du panneau**.
  Une bézier aux poignées posées à plat (`M 1 y1 C 30 y1, 20 y2, 45 y2`) les
  relie : elle sort de la barre à l'horizontale et entre dans le panneau de
  même, au lieu de couper la gouttière en diagonale.
- ⚠️⚠️ **La mesure se DIVISE par le zoom.** `getBoundingClientRect()` rend des
  pixels d'ÉCRAN — le `zoom: .8` de `body.pg` y est appliqué — et l'écart de
  deux rects est donc en px d'écran, alors qu'on l'ÉCRIT dans le repère de la
  page. On divise à l'écriture, on ne multiplie nulle part. **Septième fois**
  que ce piège se présente dans cette application.
- ⚠️ **Une gouttière sans hauteur ne dessine RIEN** : volet replié, onglet
  jamais peint, parent masqué — tout rend des rects nuls, et un tracé à des
  coordonnées non finies, c'est le `<rect x="Infinity">` de `fitView`.
- **La gouttière devient une COLONNE** de la grille (`56px`, `gap: 0`) : un
  `gap` n'est pas une boîte, et le lien a besoin d'une boîte. Mesuré, le
  classement y perd **36 px** — le `gap` de 20 disparaît, la colonne en prend
  56. C'est le prix du trait, il est écrit.
- ⚠️ **Le nœud est RECONSTRUIT à chaque changement d'activité** : une
  animation CSS ne se rejoue pas sur un élément qu'on laisse en place. Rien à
  remettre à zéro à la main.
- ⚠️ **Un tracé se dessine par son POINTILLÉ**, et seul le navigateur connaît
  la longueur réelle d'une bézier : `--len` la lui demande
  (`getTotalLength()`). **La lueur garde SON pointillé** — un éclat court qui
  défile : on ne lui pose que la longueur, jamais le `stroke-dasharray` du
  tracé, qui la ferait courir sur tout le chemin d'un coup.
- ⚠️ **`animation-fill-mode: both` est NÉCESSAIRE** sur les deux retards :
  sans lui la pointe serait posée pendant que le trait se tire encore. Le
  garde-fou qui veut qu'on retire une classe d'animation vise un CONTENEUR —
  un élément transformé devient le repère de ses descendants
  `position: fixed` ; ici ce sont deux feuilles dans une boîte en
  `pointer-events: none`.
- ⚠️ **La barre choisie ne porte plus SA pointe.** La sienne partait de son
  BAS, qui ne dit rien ; le lien part de son HAUT. Deux pointes à 160 px
  l'une de l'autre, toutes deux « vers le panneau », ne désignaient plus rien.
- ⚠️ **Sous `prefers-reduced-motion` le lien RESTE** — c'est lui qui relie les
  deux colonnes ; seul son mouvement s'arrête. La lueur, qui n'est QUE du
  mouvement, ne se dessine pas.
- ⚠️ **Sous 1100 px RÉELS** (les requêtes média ignorent le zoom du corps) les
  colonnes s'empilent : la gouttière n'est plus entre elles, et un trait tiré
  de gauche à droite ne relierait plus rien. Le lien s'efface, et la pointe
  d'avant — qui garde son sens dans ce sens-là — regarde vers le bas.

#### ⚠️ `var()` dans un attribut de présentation SVG : oui, il se résout

`stroke="var(--vo-c)"` fonctionne — mesuré, le tracé sort en `rgb(239, 115,
150)`, la prune de la palette. ⚠️ Ce qui ne fonctionne pas, c'est l'inverse,
et c'est déjà écrit : une règle d'AUTEUR l'emporte sur un attribut de
présentation. D'où `fill` neutralisé dans la feuille et `stroke` porté par
chaque tracé.

#### ⚠️⚠️ TROIS cliquets bornés à côté, le même jour

Un cliquet qui cherche une chaîne doit borner sa zone — et l'homonyme peut
être un bloc qui existait déjà :

- `@media (prefers-reduced-motion: reduce)` et `@media (max-width: 1100px)`
  ouvrent **plusieurs blocs** dans `competences.css` (**cinq** pour le
  second !), et `split(…, 1)[1]` prend le PREMIER. Deux cas lisaient donc un
  bloc qui ne parle pas du lien. L'aide `_bloc(css, entete, marqueur)` rend
  celui qui PORTE le marqueur.
- Le troisième coupait **avant** le premier `@media (max-width: 1100px)`,
  ligne 2432 — soit 1 400 lignes avant le lien : il affirmait l'absence de la
  pointe dans une zone où elle n'avait jamais été, et restait **VERT** sur le
  défaut remis. Il COMPTE désormais les occurrences, ce qui n'a pas de zone à
  borner.
- Un QUATRIÈME dormait dans `test_162` depuis la veille : il cherchait le
  premier média de 1100 px **à partir de** la position de la pointe. Celle-ci
  ayant rejoint le repli en colonne, c'est le média SUIVANT qui tombait sous
  la lecture.

#### Trois cliquets de `test_162` RÉÉCRITS, pas supprimés

`TestLeLienEntreLActiviteEtCeQuElleProduit` affirmait la structure remplacée :
la pointe posée dans la gouttière (`left: -21px`) et la pointe de la barre
choisie. Un cas qui affirme une structure disparue ne garde plus rien — et le
supprimer ne garderait rien non plus. Ils disent désormais ce qui reste vrai :
la gouttière est une COLONNE qui porte un tracé, et la barre marque son
NIVEAU au lieu de pointer depuis son bas.

Tests : `tests/test_145_vue_ensemble.py` passe de 50 à **63 cas**
(`TestLeLienEstUnTrace`), plus trois cas de `test_162` réécrits ; **16 défauts
remis un par un, 16 cliquets tombés** — l'un d'eux seulement après avoir été
reborné. Éprouvé au banc
(`tools/devrun_competences.py`) de 1000 à 1600 px dans les deux langues :
**départ à 0,16 px du haut de la barre, arrivée à 0,16 px du centre de la
pastille**, la longueur qui suit la géométrie (144 / 100 / 56 px selon
l'activité), la teinte qui suit l'activité, le lien qui revient de lui-même
sur un `resize`, rien de dessiné quand la gouttière n'a pas de hauteur, le
repli en colonne, zéro débordement horizontal et zéro erreur console.

### LES PROMPTS IA, passés en revue un par un (2026-11-25)

L'application appelle l'IA à **vingt-trois endroits** dans `Code/` — vingt-deux
routes, plus le prompt trivial de `role_i18n` — et rien ne vérifiait que
chacun dit au modèle dans quelle langue répondre. Trois façons de le dire
cohabitaient, toutes légitimes : le prompt a une **variante** par langue, la
route **ajoute** une consigne au message, ou la langue voyage dans le
**contexte JSON**. Ce qui ne marche pas, c'est de ne rien dire — un prompt
français rend du français, quelle que soit la langue de l'écran, et personne ne
lève d'erreur : le pilote anglophone lit simplement du français.

Catalogue : **38 → 54 prompts**. Cliquets : `tests/test_164_prompts_ia.py`
(85 cas) ; **35 gardes retirées une par une, 35 cliquets tombés**.

⚠️⚠️ **Et la branche anglaise est le DÉFAUT, pas un cas limite.**
`DEFAULT_LANG = 'en'` et `Code/app.py` pose `session['lang']` dès la requête :
les dizaines de `session.get("lang", "fr")` disséminées dans les routes ne
retombent **jamais** sur leur défaut français. Chaque phrase française écrite en
dur était donc servie au compte par défaut — c'est ce qui a fait tomber trois
cas de `test_40` et `test_63`, qui épinglaient un message de refus en comptant
sur le fait qu'il était INCONDITIONNEL. Ils posent désormais la langue, et la
rendent : `client` est partagé par toute la suite.

#### ⚠️⚠️ Le plus gros : AUCUNE proposition d'IA n'était joignable sur une carto COMMUNE

`Code/ecriture.py` refusait `/propose_savoirs`, `/propose_savoir_faires`,
`/propose_softskills`, `/propose_aptitudes`, `/translate_softskills`,
`/skills/propose`, `/diagnostic/plan` et `/hsc/position` — avec le code
`lecture_seule`, **le motif réservé à `user`** — à un champion qui a pourtant le
droit de PROPOSER des tâches et des compétences. Or ces routes **n'écrivent pas
une ligne** : elles appellent l'IA et rendent du JSON, et elles sont en POST
parce qu'elles portent l'activité entière dans leur corps.

C'est exactement le cas du chatbot, exempté le 23/11, et c'est la configuration
du pilote (cartos communes + champions) : ni savoirs, ni savoir-faire, ni HSC,
ni aptitudes, ni compétences proposables. Vérifié au banc
(`tools/devrun_partage.py`, compte `champion@test.local` sur la carto commune) :
**200 et des propositions anglaises**, là où c'était 403.

- ⚠️ **Ce qu'elles PRÉPARENT reste sous la porte** : `/skills/add`,
  `/savoirs/add`, `/competence/save`… Proposer n'est pas enregistrer. Mesuré au
  banc : `/skills/add` rend **202 `proposition`** pour le champion — son
  écriture part dans son brouillon, ce qui est la bonne réponse.
- ⚠️ **Trois préfixes sont PRÉCIS** (`/skills/propose`, `/diagnostic/plan`,
  `/hsc/position`) : exempter `/skills` ou `/hsc` ouvrirait `/skills/add`,
  `/diagnostic/save` et `/hsc/descriptors`, qui écrivent. Un cliquet le garde
  dans les deux sens.
- ⚠️ **L'exemption ne tient que parce que c'est vrai**, et ça se COMPTE : un
  cliquet appelle les dix routes et vérifie que **pas une ligne** ne naît
  derrière (neuf tables comptées avant / après). Lire les imports ne suffisait
  pas — un helper venu d'ailleurs pourrait écrire ; un second cliquet vérifie
  en plus que ces cinq blueprints ne tiennent aucune session SQLAlchemy, sur le
  MODULE chargé et pas sur son source (l'arbre d'image n'a pas les `.py`).
- ⚠️ C'est bien `TOUT_COMPTE`, donc `user` compris, comme le chatbot. Un appel
  d'IA coûte de l'argent et rien ici ne le limite : même risque que celui que le
  chatbot porte depuis le 23/11, assumé de la même façon.

#### ⚠️⚠️ Huit prompts système étaient ÉCRITS DANS les routes

`propose_aptitudes.py` (2), `propose_softskills.py` (2),
`translate_softskills.py` (2), `onboarding.py` (2). Ils nomment les
référentiels — **XP X50-766, CIF** — c'est-à-dire du savoir-faire, et le
catalogue existe précisément pour qu'il soit chiffré dans l'image client au lieu
de voyager dans le bytecode d'une route. La règle était écrite ici depuis la
phase 2 d'OptiqFluent (« Ne JAMAIS remettre un prompt en dur dans une route ») ;
elle avait été oubliée huit fois.

Rapatriés en cinq paires `.fr` / `.en`, et le cliquet porte sur ce que la route
**DEMANDE au catalogue**, pas sur le texte envoyé : ⚠️ un prompt réécrit en dur
contiendrait peut-être encore le mot « English » — c'est ce que faisaient les
deux prompts des aptitudes — et une règle qui ne regarde que la consigne de
langue ne l'aurait pas vu. La clé manquante, elle, se voit.

⚠️ `Code/routes/test.py` est **supprimé** : deux prompts de plus, en dur, dans
un fichier sans Blueprint ni route que **rien n'importait**, et qui appelait
`openai.ChatCompletion.create` — l'API d'avant openai 1.0, retirée de la version
épinglée. Ce n'était pas du code mort fonctionnel : c'était du code mort cassé,
qui faisait voyager du savoir-faire dans l'image.

#### ⚠️⚠️ « Answer in English » ajouté à un prompt FRANÇAIS ne suffit pas — mesuré

Cinq routes disaient la langue par la deuxième voie : un prompt français, suivi
d'une consigne anglaise. Mesuré en comptant les marqueurs de langue dans ce qui
part réellement au modèle (banc `preuve_langue`, vrai catalogue, les deux
langues) :

| route, en anglais | avant | après |
|---|---|---|
| `/skills/propose` | **fr 2 / en 1** | fr 0 / en 4 |
| `/hsc/position` | fr 2 / en 2 | fr 0 / en 4 |
| `/diagnostic/plan` | fr 2 / en 2 | fr 0 / en 4 |
| `/competence/generate` | **fr 6 / en 3** | fr 0 / en 6 |
| `/competence/result_links/generate` | **fr 5 / en 3** | fr 0 / en 6 |

Le prompt pèse plus que son post-scriptum. Les cinq passent donc en
**variantes** — la première des trois voies, et la seule qui ne se batte pas
contre son propre support. L'inventaire `LANGUE_DITE_PAR_LA_ROUTE` du fichier de
tests est désormais **vide**, et il reste là pour obliger à décider au prompt
suivant.

- ⚠️ **La consigne finale est GARDÉE à part.** Depuis que les prompts sont des
  variantes, plus aucun autre cas ne voyait `_consigne_langue` : une ligne que
  rien ne garde est une ligne qui pourrit.
- ⚠️ **Et les BLOCS DE CONTEXTE comptent autant.** `build_activity_context`
  (savoirs, savoir-faire), `_build_context` (chatbot, à chaque tour),
  `_result_ctx` (compétence), `_build_context` (qualification) et
  `_contexte_reponses` (HSC) envoyaient des intitulés français sous un prompt
  anglais : c'est le texte le plus LONG du message, et le signal mixte qui fait
  repasser le modèle au français. Tous suivent la langue.

#### ⚠️⚠️ Les libellés S/SF/HSC naissaient en français — et ils sont ENREGISTRÉS

`result_capabilities.sfhsc.system` n'avait ni variante ni consigne, et la route
n'ajoutait rien. Les savoir-faire, savoirs et HSC que l'IA propose sont
**sauvegardés** comme intitulés d'items (`Savoir.description`,
`SavoirFaire.description`, `Softskill.habilete`) : nés en français chez un compte
anglais, ils y restaient — rien ne les retraduit ensuite, contrairement aux rôles
(`role_i18n`). Le prompt le dit maintenant en toutes lettres, dans les deux
variantes.

La **compétence principale**, elle, était juste par son SCHÉMA
(`description_fr` + `description_en`, exigés par `COMP_SCHEMA`) mais le prompt
n'en parlait pas : ⚠️ une consigne portée par le seul schéma se perd à la
première réécriture. Les deux variantes la portent.

#### ⚠️⚠️ Le changelog généré servait du FRANÇAIS à tout le monde

`changelog.system` disait « **Langue : français uniquement** ». Son résultat
s'affiche dans la fenêtre de bienvenue de **chaque page**, et il est **mis en
cache par empreinte de commit** puis relu par des comptes de langues
différentes. Le fichier curé, lui, est bilingue depuis toujours
(`title_en` / `desc_en`, servis par `_curated_lang`).

Le prompt demande donc désormais les **deux langues**, et `_servir` applique
`_curated_lang` **à la LECTURE**. ⚠️ Jamais avant la mise en cache : la langue du
premier lecteur gèlerait celle de tous les suivants pendant une heure.
`_fallback_changelog` — le dernier recours — est bilingue lui aussi.

#### Sans clé IA, les replis parlaient français

C'est le cas le plus courant chez un client qui n'en a pas, et c'est tout
l'intérêt de « en toute circonstance » :

- `dummy_from_context` rendait « **Connaître** les procédures principales de
  l'activité « X » » à un compte anglais. ⚠️ Les guillemets `« »` sont une
  convention FRANÇAISE : la version anglaise emploie des guillemets droits.
- ⚠️ **Le repli relit le contexte pour y prendre le titre** : il cherchait
  « Titre: », qui n'existe plus quand le contexte est anglais. Traduire l'un
  sans l'autre faisait perdre le nom de l'activité dans les propositions.
- Les messages d'erreur de `skills.py` (3) et de `translate_softskills.py` (4),
  et le `note` de `/hsc/position`, étaient en dur en français.
  ⚠️ « Clé IA non renseignée » est un **MARQUEUR** lu par `optiqAiCheck`, pas un
  texte d'écran : sa regex `NO_KEY_MARKERS` porte aussi la forme anglaise
  (`ai key not configured`), la traduire est donc sûr — et le `source` que rend
  `make_ai_client` reste en français **exprès**, c'est un code que le JS
  reconnaît pour afficher SA propre pop-up bilingue.

#### Deux chemins du même prompt, dont un seul disait la langue

`import.enrich` rédige `match_reason` dans « langue_des_remarques » quand elle
est fournie. `import_hub` la passe depuis toujours ;
`import_full._try_openai_enrich` ne la passait pas — la remarque revenait en
français. ⚠️ Ce chemin-là n'est appelé par **aucun écran** (`/api/import-full/*`
n'apparaît nulle part dans le front depuis que la fenêtre d'import a déménagé),
mais la route existe et répond : deux chemins du même prompt ne doivent pas
diverger sur la langue.

#### Ce qui a été VÉRIFIÉ et laissé tel quel

- `carto.decisions.system` et `carto.reposition.system` ne rendent **pas de
  prose** : des coordonnées, et les libellés fournis recopiés sans traduction
  (« conserve exactement les labels »). Rien à dire sur la langue.
- `plan_formation.system` et `import.correspondance` / `import.enrich` restent
  sur la **troisième voie** : la langue voyage dans le contexte JSON
  (`"langue": "English"`, `langue_des_remarques`) et le prompt le dit
  explicitement (« Rédige tous les textes dans la langue demandée »,
  « rédigée dans *langue_des_remarques* quand elle est fournie »). Les traduire
  en variantes voudrait dire réécrire 1 600 signes de règles OPTIQ, pour un gain
  qu'aucune mesure ne montre.
  ⚠️ **Ce qui est mesuré et ce qui est seulement RELU**, parce que la nuance
  compte : `plan_formation` et le chemin d'`import_full` sont mesurés par un
  cliquet (le champ part bien dans le contexte) ; les deux routes
  d'`import_hub`, elles, ont été **relues** — elles passent
  `langue_des_remarques` depuis toujours, et `test_84` les couvre par ailleurs,
  mais je ne les ai pas fait tourner avec un enregistreur.
- ⚠️ `competences_plan.py` / `plan_storage.py` sont les vestiges de l'ANCIENNE
  page Compétences : **aucun gabarit ne les charge** (c'est déjà écrit plus
  haut). Leur paire `competences_plan.header.{fr,en}` est donc un prompt mort —
  laissé en place, pas vérifié à l'écran.
- `/competence/result_links/generate` **écrit** (items + liens) : il reste sous
  la porte, et il n'est pas dans `_SEGMENTS`, donc un champion ne peut ni
  l'écrire ni le proposer. Le rendre proposable est une décision de modèle, pas
  une ligne d'exemption.

#### ⚠️ Quatre pièges, dont trois déjà connus sous une autre forme

- ⚠️⚠️ **Un NameError dans le `try` d'une route devient un repli silencieux.**
  L'ajout du paramètre `lang` à `_build_context` (qualification) sans toucher à
  sa signature levait un NameError **avalé par le `except`** :
  `/qualify/analyze` rendait son repli en **200**, l'appel IA disparu sans un
  mot. C'est le banc qui l'a vu (« AUCUN APPEL »), pas la suite. Toute route
  dont l'appel IA vit dans un `try/except` qui rend un repli **cache ses propres
  bugs** : c'est pour cela que la règle du fichier de tests commence par
  « aucun appel au modèle : la route est tombée dans un repli ».
- ⚠️ **Un cliquet qui cherche une chaîne doit borner sa zone** — deux fois ici.
  `"title_en" in t` restait **vert** le schéma du changelog vidé, parce que la
  consigne juste au-dessus cite « title_en/desc_en » en toutes lettres ; il vise
  maintenant `'"title_en":"'`, la forme du schéma. Et `doit_dire_anglais`, la
  règle générale, ne voyait **pas** un contexte remis en français — « Activité: »
  et « Tâches: » ne contiennent pas le mot « français » : les deux cas
  concernés épinglent désormais un intitulé anglais précis.
- ⚠️ **Compter les guillemets d'une ligne pour la découper est faux** : une
  chaîne à guillemets DOUBLES qui contient une apostrophe (`d'activité`) rend le
  compte de `'` impair, et mon helper avalait la ligne suivante — il a failli
  effacer le prompt voisin. Chaque prompt du catalogue tient sur UNE ligne : on
  travaille par lignes.
- ⚠️ Deux fixtures de langue dans la même signature de test (`en` **et** `fr`)
  s'annulent : la seconde repose la langue avant que le cas ne tourne. Le test a
  attrapé ma propre erreur.

ℹ️ `Code/prompts/prompts.enc` est régénéré par **chaque** workflow de
déploiement (`python tools/prompts/encrypt_prompts.py`, avant le build) : un
prompt ajouté au catalogue part tout seul dans l'image client. Vérifié ici —
chiffrement puis relecture par le chemin du client, **54 prompts**, accents
intacts.

**Reste, et c'est un chantier à part** : les **191 chaînes françaises écrites en
dur** dans les JS encore chargés par un gabarit (`propose_aptitudes.js` 47,
`tasks.js` 22, `propose_from_file.js` 16…), déjà inventoriées le 16/11. Ce
travail-ci porte sur ce qui part vers le modèle et sur ce qu'il en revient ; ce
que les écrans en font ensuite se traite écran par écran.

---

### AUDIT AVANT LIVRAISON CLIENT : deux 500 sur une base NEUVE, et la mine du 29/10 (2026-11-25)

Rapport complet et classé : `docs/audit_avant_livraison.md`. Banc principal :
un **PostgreSQL 16 vierge** monté par le démarrage NORMAL de l'application —
c'est le scénario du client le jour 1, et les 104 routes GET y ont été balayées.
**Deux rendaient 500, et aucune des 5176 lignes de la suite ne pouvait les
voir : elle tourne sur SQLite.**

#### ⚠️⚠️ `/temps/api/tableau_de_bord` : une sonde qui empoisonnait la session

`get_calendar_params()` ne trouve aucune ligne `entreprise_settings` (base
neuve) → retombe sur `get_company_params()` → `SELECT … FROM company_params`
échoue, car **cette table n'a AUCUN modèle : rien ne la crée** → `except: pass`
→ sur PostgreSQL un ordre raté **avorte TOUTE la transaction** → trois lignes
plus loin, `Activities.for_active_entity()` lève `InFailedSqlTransaction`.

⚠️ **Mesuré : sur SQLite la session SURVIT au SELECT raté.** D'où le silence de
la suite. Famille « ce que SQLite accepte et que PostgreSQL refuse », déjà
écrite ici pour `BOOLEAN DEFAULT 0` et `softskills.niveau` — cette instance-là
n'avait jamais été attrapée.
⚠️ **Et le défaut guérit tout seul** dès qu'on enregistre le calendrier de
travail en page RH : il ne mord que le compte neuf et disparaît avant qu'on
puisse le reproduire. Le pire profil pour un signalement client.

⚠️⚠️ **Deux fausses pistes, mesurées — elles ont l'air justes :**
- `db.session.rollback()` dans le `except` répare la transaction, mais
  `get_calendar_params` est appelé depuis des routes qui ÉCRIVENT : le rollback
  **jette le travail en attente de l'appelant** ;
- `db.session.begin_nested()` (SAVEPOINT) a l'air de régler ça et **ne le règle
  PAS** : `begin_nested` **FLUSHE** la session avant de poser le point de
  reprise, donc le travail en attente part DANS le savepoint et le rollback
  l'emporte. Mesuré : l'objet ajouté juste avant disparaissait de
  `session.new`.

**Retenu : une connexion DÉDIÉE** (`db.engine.connect()`), qui ne touche à
aucune transaction de la session — rien à réparer, rien à perdre. C'est le
parti déjà pris pour OptiqPulse (« écriture en connexion Core dédiée, jamais la
session ORM »). Vérifié : 200 sur PostgreSQL, et sur SQLite zéro savepoint,
session utilisable, travail en attente **préservé**.

#### ⚠️⚠️ `/performance_perso/*` : une DDL en SQLite PUR, dans une route

`ensure_history_schema()` exécutait `id INTEGER PRIMARY KEY AUTOINCREMENT` et
`datetime('now')` — syntaxe SQLite que PostgreSQL refuse (`syntax error at or
near "AUTOINCREMENT"`). Appelée en tête de **six des sept routes** du
blueprint : cassé sur les deux instances en ligne, depuis toujours.
⚠️ **`test_67_schema_postgres` compile le DDL des MODÈLES** avec le dialecte
PostgreSQL ; une chaîne brute dans une route lui échappe entièrement.
Gravité basse — `performance_personnalisee.js` n'est chargé par aucun gabarit,
la fonctionnalité est injoignable : des routes mortes qui rendaient 500.

#### ⚠️⚠️ L'URL de la base ne nommait pas son PILOTE — la mine du 29/10, restée

`Code/app.py` ne faisait que normaliser `postgres://` → `postgresql://`. Or
`postgresql://` seul désignait **psycopg2** en SQLAlchemy 2.0 et désigne
**psycopg (v3)** depuis la **2.1**, qui n'est pas installé. C'est l'incident qui
a mis tout le hub à terre sans qu'un seul commit ne change, et **le correctif
n'avait été porté que dans `hub/` et `pulse/`.**

⚠️ L'épinglage (`SQLAlchemy==2.0.52`) protège aujourd'hui — mais
`distribution/docker-compose.yml` passe au client un `postgresql://` **NU**, et
une reconstruction d'image ferait exploser son installation. Une URL qui dit son
pilote ne dépend plus du tout de ce que pip a installé.

`normaliser_url_db(url)` est une **fonction de module** (même raison que
`config_mail` : elle s'importe, donc son cliquet tourne aussi dans l'arbre
d'image). ⚠️ Une URL qui nomme DÉJÀ son pilote (`+psycopg`, `+asyncpg`) n'est
pas réécrite : ce serait décider à la place de celui qui l'a posée.

⚠️ **Deux cas de `test_157` ont été RENVERSÉS** : ils affirmaient que
`postgresql://` était laissé TEL QUEL, c'est-à-dire exactement ce qu'on vient
de changer. Un cas qui affirme une règle remplacée ne garde plus rien — on le
réécrit sur la vérité neuve, on ne le supprime pas. Un troisième cas s'ajoute :
une URL qui nomme déjà son pilote n'est pas touchée.

#### ⚠️ Un cliquet qui ne gardait RIEN, et pourquoi

Le premier cas écrit remettait le défaut **d'origine** — invisible sur SQLite
par construction, donc il restait vert. Le cas qui tient affirme l'**INVARIANT**
(la sonde ouvre SA PROPRE connexion) et tombe sur les **trois** versions
fautives. Règle : *quand le défaut est invisible sur le moteur de la suite, le
cliquet porte sur le mécanisme qui le ferme, pas sur le symptôme.*

#### ⚠️⚠️ L'ASSISTANT D'INSTALLATION est 100 % français, sans aucun moyen de traduire

C'est le **premier écran de l'image client** : celui où son informatique colle
la licence, saisit l'URL de sa base, sa clé OpenAI, ses identifiants de mail et
le compte administrateur. S'il ne le lit pas, l'installation n'a pas lieu.

Vérifié : `setup_wizard.html` fait **412 lignes dont 257 dans un seul bloc
`<script>`** qui construit les cinq étapes — et **zéro mécanisme de
traduction** : pas un `t()`, pas de catalogue, pas de `data-i18n`. Il n'y a
rien à compléter, il n'y a rien du tout. Idem pour `license_blocked.html`,
l'écran servi quand la licence expire.

⚠️ **Rectification de ma propre mesure** : j'avais d'abord compté 18 fragments
français dans ce gabarit avec un détecteur qui lisait l'intérieur des
`<script>` — il gonflait aussi le compte des autres gabarits. *Un détecteur
qui parcourt un gabarit doit sauter `script`, `style`, `noscript` et
`template`, exactement comme celui qui parcourt le DOM.*

#### Trois mesures qui corrigent ce que ce fichier affirmait

- **La dette de traduction est plus PETITE qu'annoncé** (191) : sur 236 chaînes
  relevées dans 30 fichiers vivants, **52 sont certainement visibles**, dont 16
  dans du **code mort** → **≈ 33 sur un écran vivant**, presque toutes des
  messages d'erreur des chemins d'IA. Le reste : 66 `console.log`, 101 à
  trancher, et 300 qui sont la moitié française d'un catalogue bilingue
  **légitime**. ⚠️ Compter les chaînes françaises d'un fichier ne mesure rien
  tant qu'on n'a pas séparé le catalogue, les traces et le code mort.
- **`projection_metier` est un écran ENTIER injoignable** — aucun lien depuis la
  nav ni depuis aucun gabarit. Ses 16 fragments français inventoriés par
  `test_78` ne se voient nulle part : **le traduire serait du travail perdu**.
- **`synth_competences.js`, `performance_perso.js` et `plan_formation.js` sont
  bien morts** (ce fichier le disait, mon premier détecteur le niait : il les
  croyait chargés parce qu'un AUTRE JS citait leur nom). **10 fichiers JS morts,
  176 Ko**, dont `main copy.js`.

#### Mesuré et laissé tel quel (le rapport détaille)

- **Zéro CSRF** dans `Code/`, et le cookie de session sans drapeaux
  (`SECURE=False`, `SAMESITE` non posé — mesuré). ⚠️ **Pas de vecteur
  exploitable aujourd'hui** : `SameSite` absent retombe sur `Lax` côté
  navigateur, et des 104 routes GET seules **trois** écrivent, du
  provisionnement idempotent. Ce qui reste : le cookie en clair si du HTTP est
  servi, et le constat en revue de sécurité client.
- **Les 4 dérivés de l'accent rendent du GRIS** : mesuré au navigateur,
  `--pg-accent` = `#7c3aed` mais `--pg-accent-soft` =
  `color-mix(… #64748b …)`. **212 occurrences** dans 8 feuilles lisent un gris
  en croyant lire la couleur de la page (`activities_list.css` 48,
  `share.css` 39, `competences.css` 32, `gestion_outils.css` 32,
  `gestion_rh.css` 30…). ⚠️ Un second compteur donne « 272 éléments » sur la
  page Activités : il relève une COULEUR, pas un défaut — l'ordre de grandeur,
  pas la liste des corrections. Le correctif de fond — les quatre jetons dans
  chaque `.page--*` — reste à faire en regardant les dix pages.
- Le `/login` n'est pas limité en débit ; `FORWARDED_ALLOW_IPS` vaut `*` ;
  `/testpanel` est sans authentification mais **bien fermé chez le client**
  (`TESTPANEL_ENABLED=0` baké, vérifié) et ouvert sur staging.
- L'erreur `alembic_version` s'imprime à **chaque** démarrage sur PG neuf, avec
  sa trace — inoffensive, mais le client la lira le jour 1.

#### ⚠️ Le point aveugle : 99 routes d'écriture gardées UNE PAR UNE

Mesuré : la porte centrale **refuse 102** routes d'écriture à un compte
`user` — elle fait son travail. Mais **99 la traversent** (25 préfixes dans
`TOUT_COMPTE`, 7 dans `SANS_COMPTE`) parce qu'elles portent une règle plus
fine : `/comptes/*`, `/gestion_rh/*`, `/mastery/*`, `/paliers/*`, `/plan/*`,
les routes d'IA, `/login`…

⚠️⚠️ **C'est exactement dans cette moitié qu'étaient les trois trous trouvés
jusqu'ici**, un par un et à l'usage : le garant (05/11), `/tools/add` (22/11),
les dix routes d'IA (25/11). Chacun se présentait pareil — un champion
recevait `lecture_seule`, le motif réservé à `user`. Un balayage ne peut pas
les trancher (il faudrait les APPELER, donc écrire) : cela demande une passe
construite, route par route, avec un décor jetable. **C'est le chantier à
faire avant la livraison, devant la traduction et devant le gris.**

#### Ce qui a été vérifié BON, pas supposé

Suite : **5196 passés, 1 sauté, zéro rouge** ·
61/61 tables créées sur une base vierge · zéro route cassée après correctifs ·
verrous de l'image client corrects · **`preload_app = True` avec
`Code.app:app` → les migrations tournent UNE fois**, pas une par worker (le
doublon observé venait de mon propre script : `Code/app.py` porte
`app = create_app()` au niveau module, et mon script appelait la fabrique en
plus) · les 4 sites de SQL concaténé sont sûrs (listes blanches de littéraux,
valeurs en paramètres liés).

Cliquets : `tests/test_165_base_neuve.py` (19 cas ; **sept vérifiés rouges**,
dont les trois versions fautives de la sonde). Un inventaire y tient les cinq
tables sans modèle et les trois fichiers autorisés à porter de la syntaxe
SQLite — une sixième table, ou un quatrième fichier, sera un choix écrit.
⚠️ **Deux garde-fous de VOLUME** : dans l'arbre d'image, `Code/` n'a plus aucun
`.py`, et les deux balayages y liraient ZÉRO fichier — ils verdiraient sans
rien vérifier. Sous 40 sources lues, ils sautent franchement. (Mesuré : 104
sources en temps normal.)

---

### TROIS POINTS DE L'AUDIT TRAITÉS : le code mort, le gris, les alertes (2026-11-25)

Suite directe de `docs/audit_avant_livraison.md`. Trois de ses points, choisis
par l'utilisateur ; les autres attendent.

#### ⚠️⚠️ Le gris : une propriété personnalisée se substitue LÀ OÙ ELLE EST DÉCLARÉE

Les quatre dérivés de l'accent (`--pg-accent-soft`, `-softer`, `-border`,
`-glow`) étaient déclarés sur `:root` SEUL, où `--pg-accent` vaut encore le
gris par défaut `#64748b`. Le gris était donc déjà **cuit** dans leur valeur
quand elle héritait aux dix pages — et c'est pour cela que tout ce qui passait
par `var(--pg-accent)` **dans la règle elle-même** sortait, lui, en couleur :
d'où l'aspect panaché relevé depuis des mois.

Mesuré au navigateur **avant** (page Activités) : `--pg-accent` = `#7c3aed`,
mais `--pg-accent-soft` = `color-mix(in srgb, #64748b 10%, #ffffff)`, et
**272 éléments de la page** rendaient exactement cette teinte grise.

Le correctif tient en une règle : les quatre dérivés se redéclarent **sur les
mêmes sélecteurs que l'accent** — `:root` plus les vingt sélecteurs des dix
pages, `body:has()` comprises, car c'est souvent le `body` qui porte l'accent.
Chaque élément recalcule alors ses dérivés depuis SON `--pg-accent`.

Mesuré **après**, les neuf pages servies, chacune par son propre jeton :

| page | accent | `-soft` rendu | `-border` rendu |
|---|---|---|---|
| Activités | `#7c3aed` | violet pâle | violet |
| Rôles | `#059669` | vert pâle | vert |
| Compétences | `#2563eb` | bleu pâle | bleu |
| Temps | `#d97706` | ambre pâle | ambre |
| Comptes | `#e11d48` | rose pâle | rose |
| RH | `#16a34a` | vert pâle | vert |
| Outils | `#ea580c` | orange pâle | orange |
| Paramètres | `#6366f1` | indigo pâle | indigo |
| Partage | `#c026d3` | fuchsia pâle | fuchsia |

Et sur la page Activités, **0 élément sur 6 821** rend encore l'ancien gris
(272 avant). ⚠️ C'est surtout sur les **bordures** que l'écart se voyait :
`-border` rendait `0,830 0,847 0,873` là où il doit rendre
`0,856 0,784 0,980`.

⚠️ **Rien d'autre n'a changé d'apparence** : les en-têtes de carte d'activité
sont violets *par construction* (`linear-gradient(135deg, var(--pg-accent),
var(--pg-accent-deep))` écrit dans la règle), ils l'étaient déjà.
⚠️ Le correctif **n'est pas** « quatre lignes dans chacune des dix classes »
comme le rapport le chiffrait : une seule règle à vingt-et-un sélecteurs, ce
qui évite dix copies qui dériveraient.

Cliquet : `tests/test_168_couleur_de_page.py` (9 cas) — il compare les **deux
listes de sélecteurs** et exige qu'elles soient identiques, donc une page
ajoutée demain qui poserait l'accent sans ses dérivés est un échec, pas un
gris silencieux. **Trois défauts remis un par un, trois cliquets tombés.**

#### Le code mort qui partait dans l'image client

Retirés : **11 fichiers JS** (179 Kio), **2 CSS** (`menu.css`,
`softskills.css`), **3 blueprints** et leurs 3 fichiers de tests, **2 prompts**
du catalogue. Tous vérifiés d'abord : aucun gabarit ne les cite, aucun Python
ne les importe, et il n'existe **aucun chargement dynamique de script** dans
l'application (ni `createElement('script')` hors bibliothèque, ni `url_for`
avec un nom concaténé).

⚠️⚠️ **« Chargé par un gabarit » ne veut pas dire VIVANT.**
`activities_time.js` était bien dans `display_list.html` — et ses ancrages
(`.activity-time[data-activity-id]`, `.at-save`, `.at-global`,
`.at-task-rows`) n'existent dans **aucun** gabarit, ni dans aucun autre JS.
L'onglet Temps de la fiche activité a été refait en JS **inline** dans
`activity_time_new.html`, avec ses ids `time-*` et son catalogue
`ACTTIME_I18N` — déjà traduit. Ses quatre alertes françaises ne s'affichaient
donc nulle part : les traduire aurait été du travail perdu. **C'est le 11e
fichier mort, et l'audit ne l'avait pas vu** parce qu'il ne cherchait que les
fichiers qu'aucun gabarit ne charge.

⚠️ **Les trois blueprints ne se sont pas contentés de partir** : chacun
créait sa table à chaud (`performance_personnalisee_historique`,
`training_plan`, `prerequis_comment`). Ces trois noms quittent l'inventaire
`CONNUES` de `test_165` — plus rien ne les mentionne — et il tombe de cinq
tables sans modèle à **deux** (`company_params`, `gestion_rh_params`, les deux
qui sont seulement LUES et qui ont produit le 500 du tableau de bord).
⚠️ Les **modèles** `PerformancePersonnalisee` et `UserActivityPlan` restent,
eux, avec leurs tables : retirer un modèle est une décision de schéma, et
`UserActivityPlan` n'existe que parce que son absence avait coûté un 500.

⚠️ **Un inventaire doit MAIGRIR avec le code qui part.** `competences_plan.py`
figurait dans l'inventaire des fichiers autorisés à porter de la syntaxe
SQLite ; le fichier parti, le cas « déjà propres » **SAUTAIT sur le premier
fichier absent** et cessait de surveiller les deux autres, sans rien dire.
L'inventaire tombe à deux entrées, et les deux cas tournent de nouveau
(vérifié : PASSED, pas SKIPPED).

⚠️ Le cas qui éprouvait la DDL de `performance_personnalisee` part avec son
sujet. La **leçon**, elle, reste — tenue par
`test_seuls_les_fichiers_INVENTORIES_portent_de_la_syntaxe_SQLite`, pour tout
`Code/` et non pour ce seul fichier : un contrôle plus fort, pas un contrôle
sauté.

#### ⚠️⚠️ `projection_metier` n'est PAS du code mort — et il n'a pas été touché

L'audit le rangeait avec le code mort ; la mesure dit autre chose. C'est une
fonctionnalité **complète et éprouvée** : 27 Ko de route, son gabarit, son
CSS, son JS, et **108 cas de test** (`test_32`). Elle est seulement **non
reliée** — aucun lien depuis la nav ni depuis aucun gabarit.

⚠️ Et elle est **spécifique à la France** : elle interroge l'API ROME de
**France Travail** et exige `ROME_CLIENT_ID` / `ROME_CLIENT_SECRET`, un compte
partenaire que le pilote indien n'a pas, pour une classification des métiers
qui ne décrit pas son marché. La rebrancher exposerait donc un écran qui ne
peut pas fonctionner chez lui ; la supprimer jetterait le travail d'AFDEC.

Rien n'a été fait : supprimer ou rebrancher est une **décision produit**, et
108 tests en dépendent. ⚠️ Le conditionner à la présence de ses identifiants
serait possible, mais ferait rougir `test_32` en entier et `test_78` (qui
charge `/projection_metier/`) — ce n'est pas une ligne.

#### Les alertes des listes de la fiche activité

**Trente-neuf libellés** s'affichaient EN DUR, donc en français quel que soit
l'écran : les dix alertes de `performance.js`, les quatre « Confirmez-vous la
suppression… » (contrainte, HSC, rôle, outil), les erreurs des quatre écrans
« Proposer… », les deux de `file-picker.js`, les six titres et invites de
l'écran des aptitudes, et le « Résumé : » de `main.js`. Ils sortent
précisément quand quelque chose rate — chez un client sans clé IA ou avec un
réseau capricieux, donc souvent.

⚠️ **`test_78` ne pouvait pas les voir** : il lit les GABARITS, et ces phrases
vivent dans le JS.

⚠️⚠️ **Le catalogue `CRUD_I18N` n'était injecté que par `display_list.html`.**
`file-picker.js` sert aussi la page **Outils**, qui n'inclut pas ce gabarit :
son message d'erreur y retombait sur le repli français de `_CRUD_FR`. Il vit
désormais dans **`header_buttons.html`** — la nav, donc chaque page de
l'application — et `display_list.html` ne le redéclare plus : deux sources,
c'est la dernière rendue qui gagne, et plus personne ne sait laquelle.
⚠️ `optiq_alert.js`, qui définit `_CR`, **n'est pas chargé par la page
Outils** : `file-picker.js` a donc son PROPRE accesseur. Un composant partagé
par deux pages ne s'appuie que sur ce qu'il apporte lui-même.

⚠️ **Une chaîne française en second argument d'un accesseur est un REPLI, pas
un libellé en dur** — `_piComp('cle', "français")` ne s'affiche que si la clé
manque. Mon premier détecteur les comptait : 72 relevés pour 39 réels, dont
les cinq de `competencies.js` (déjà traduit depuis toujours) et les quatre de
la modale « Envoyer une copie » d'`activities_map.js`, qui sont les replis de
`SHARE_I18N` et dont **toutes les clés existent**.

⚠️ **Et cela corrige une note de ce fichier** : « `activities_map.js` porte
encore du français en dur, mais dans du code MORT ». La liste qu'elle donnait
était juste mais **incomplète** — elle ne mentionnait pas la modale de
partage, dont les ancrages (`#wizard-copy-btn`, `#share-confirm-btn`,
`#share-modal`) sont bien dans le gabarit, donc VIVANTE. Elle est déjà
traduite ; il reste **3** alertes en dur dans ce fichier, toutes dans du mort
(`importCartoPackage`, dont le bouton n'existe plus, et `submitWizard`).

⚠️ **L'accord ne se devine pas d'une langue à l'autre** : le libellé des
aptitudes accordait en JS (`added > 1 ? 's' : ''`). Il passe par deux clés
`_1` / `_n`, la convention déjà employée dans ce catalogue.

Cliquet : `tests/test_167_alertes_des_listes.py` (15 cas) — aucune alerte en
dur hors inventaire, l'inventaire de dette qui **ne peut que baisser** (un cas
exige l'égalité stricte, sinon une marge masquerait un retour en arrière), les
clés présentes dans les deux langues, et une clé anglaise recopiée du français
qui échoue. **Sept défauts remis un par un, sept cliquets tombés.**

#### ⚠️ Deux cliquets qui ne gardaient rien, et c'est toujours la même faute

- **Viser l'EMPLOI, pas la présence du nom.** `"window.CRUD_I18N" in s`
  restait vrai avec `window.CRUD_I18N_DESACTIVE` : le cliquet passait au vert
  sur le défaut remis. Il cherche désormais l'affectation
  (`window\.CRUD_I18N\s*=\s*\{`).
- **Un balayage ne garde que ce qu'il regarde.** Celui des alertes ne lit que
  `alert(` / `confirm(` — les six libellés des aptitudes sont du HTML
  (`innerHTML`, `placeholder=`) et lui échappaient entièrement. Ils ont leur
  propre cas, qui vérifie que chaque libellé passe par le catalogue.

#### ⚠️⚠️ Un test de `test_30` ne passait QUE grâce à l'ordre

Relevé en jouant la suite avec `-p no:randomly` : deux cas de
`TestSkillsPropose` épinglaient le message **français** de `/skills/propose`
en comptant sur le fait qu'il était inconditionnel. Il est bilingue depuis la
passe des prompts (24/11), et le défaut de session est l'**ANGLAIS**
(`DEFAULT_LANG = 'en'`, plus le `before_request` de `create_app`) : ils ne
passaient que si un fichier joué AVANT avait laissé la langue à « fr ». Verts
en suite complète, **rouges tout seuls**.

Ils posent désormais la langue avec le `_langue()` déjà écrit pour `test_40`,
et lisent le refus dans les **deux** langues — ces phrases s'affichent telles
quelles dans la modale de proposition.

#### Ce qui reste, et qui a été vu en chemin

- **`activities_map.js`** : séparer le vif du mort dans 1 900 lignes d'un
  fichier LIVE (la page Carte, refondue quatre fois) ne se fait pas en
  passant. Les blocs morts sont identifiés — l'ancien assistant VSDX/SVG
  (`#wizard-title`, `#wizard-progress`, `screen-import` absents), les panneaux
  SCS/VCM, l'import de paquet (`wireCartoImport` rend la main tout de suite,
  son bouton n'existe plus). `goToScreen` est vivant, mais ses deux écritures
  françaises sont derrière des gardes (`if (title)`, `if (prog)`) que rien ne
  satisfait.
- **« Développeur de compétences » s'affiche en français sur la page
  Comptes.** `role_i18n.nom_affiche` est branché dans `api_tableau` (RH) et
  `/mastery/*`, pas dans la liste des rôles de cette page. Antérieur, hors des
  trois points demandés.
- **`confirm()` reste la fenêtre du NAVIGATEUR** dans ces fichiers. Seul
  `window.alert` est détourné vers la pop-up maison ; passer à `optiqConfirm`
  demande de rendre les appelants `async`, ce qui est un changement de
  comportement et pas une traduction.

Suite : voir le commit. Éprouvé au banc (`tools/devrun_partage.py`) dans les
deux langues : les neuf pages mesurées une à une pour la couleur, les alertes
déclenchées pour de vrai sur l'écran anglais (« Performance field not
found. », « Delete this performance indicator? », « Delete this constraint? »,
« Delete this socio-cognitive ability? »), le catalogue vérifié présent sur la
page Outils où il manquait, et le détecteur de fuites passé sur quatre
écrans : **zéro fuite française** (2 136 textes relevés sur la seule liste des
activités, attributs compris — tout ce qui reste en français est une DONNÉE du
banc).

---

### LE SOCLE : le premier remplissage s'écrit DIRECTEMENT (2026-11-26)

Reprise du palier du 22/11 sur le découlement que l'utilisateur a décrit :
« un coordinateur crée une entité, lui importe une carto, la partage aux
champions ; l'un d'eux la remplit avec un import Excel. Au lieu d'une demande
par modification, le palier se met en place. Une fois validé, on rebascule
dans une modification = une demande. »

**Deux régimes, et c'est `Entity.socle_etat` qui dit lequel s'applique.**

| état | ce qu'on peut écrire | qui décide |
|---|---|---|
| `saisie` | les DONNÉES d'activité, **directement**, par qui peut proposer | `carto_access.can_fill` |
| `soumis` | plus rien : le coordinateur examine un état FIXE | la porte, motif `socle_en_examen` |
| `valide` | une modification = une demande (le régime du 19/10) | `can_propose`, comme avant |

`Code/socle_activites.py` porte l'état, le palier et les trois transitions ;
`Code/routes/activite_propositions.py` les expose
(`/socle`, `/socle/soumettre`, `/socle/valider`, `/socle/renvoyer`).

#### ⚠️⚠️ Pourquoi la saisie DIRECTE, et pas un brouillon rendu en place

Le palier d'origine mesurait la base **plus le brouillon SIMULÉ** : la saisie
du champion était détournée (202) et n'atteignait jamais la base. Deux faits
mesurés ont tranché contre ce modèle :

- ⚠️⚠️ **L'import Excel ne vise que les cartos où le compte a `can_edit`**
  (`import_hub._cibles_possibles`), et `can_edit` rend faux pour un champion
  sur une carto commune. Mesuré avant : la liste des cibles était **VIDE** —
  le PREMIER PAS du découlement était donc impossible, et aucun brouillon ne
  pouvait le rattraper (un import n'est pas un geste qu'on rejoue) ;
- la demande était explicite : « la saisie se fait de manière standard, cela
  nous évitera d'avoir une section donnée officielle / donnée saisie pour
  chaque élément ».

Conséquence heureuse : **le palier se mesure en base seule**, quatre requêtes,
sans simulation. Assez peu cher pour que la page Activités l'affiche à chaque
rendu — ce que le brouillon simulé interdisait.

⚠️ `propositions_activite.simuler` est donc partie avec son dernier appelant.
`_appliquer_gestes` reste, partagé par `rejouer` ; les références locales
(`b:0`) restent aussi — elles servent à l'approbation en phase 2.

#### ⚠️⚠️ `can_fill` n'est PAS `can_edit`, et c'est tout l'arbitrage

`can_edit` ouvre aussi le **DIAGRAMME** : `/cartography/api/save`, l'import
Visio, le renommage de la carto. Le rendre vrai pour un champion lui donnerait
la carte elle-même, qui vient du coordinateur et n'est pas à remplir.
`can_fill` = `can_edit` **ou** (carto commune + socle en `saisie` +
`propose_carto`). Trois appelants y passent, et trois seulement :
`ecriture._peut_ecrire`, `import_hub._cibles_possibles`, `import_full.inject`.
Le reste garde `can_edit`.

⚠️ Le droit consulté est **`propose_carto`**, celui du tableau des droits : un
`user` consulte et ne modifie rien, et ce régime ne change pas la grammaire du
produit. Ce qu'il change, c'est que pendant la saisie une PROPOSITION devient
une écriture — et une seule validation à la fin.

#### ⚠️⚠️ La REPRISE, sans laquelle cette livraison est un recul d'accès

Le défaut de la colonne est `'saisie'`, et **toutes les lignes existantes
l'héritent** : sans reprise, cette livraison ouvrirait l'écriture directe à
tout champion sur des données déjà officielles.
`reprendre_cartos_existantes()` passe toutes les cartos en `'valide'` au
démarrage, **une seule fois** (marqueur `socle_cartos_existantes` dans
`app_settings`). Rejouée, elle validerait le socle de chaque carto qu'on est
en train de remplir : on ouvrirait la saisie le matin et le redéploiement du
soir la refermerait — exactement le défaut de `migrer_anciens_champions`.

⚠️ Les cartos PRIVÉES sont reprises aussi : le socle y dort (leur
propriétaire écrit de toute façon), mais si l'une devient commune demain elle
ne doit pas rouvrir l'écriture directe sur ce qu'elle porte déjà.

#### L'écran : un panneau en tête de la page Activités

`socle_panneau.html` + `static/socle_saisie.{css,js}`, inclus par
`display_list.html`, servi par `activities_view._socle()`.

- **Rendu par le SERVEUR**, pas rempli par un `fetch` : un panneau qui
  apparaît une image plus tard se lit comme un défaut. Le JS ne met à jour
  que les VALEURS, sur place (réécrire le panneau ferait sauter la barre au
  lieu de la laisser avancer).
- ⚠️ Calculé par la ROUTE, **pas par le processeur de contexte** : le palier
  coûte quatre requêtes et le processeur tourne au rendu de CHAQUE page, nav
  comprise. Et `etat()` s'arrête avant le palier dès que le socle est validé
  ou la carto privée — coût nul dans le cas normal.
- **UN seul « i »** pour toute la page : « tout ce que vous voyez dans ces
  fiches est la saisie des champions ; la carto n'apporte que les activités
  et ce qui entre et sort de chacune ». C'est ce qui évite de répéter « non
  validé » sur chaque champ de chaque fiche.
- **Un rappel latéral** quand le panneau sort de vue : un anneau, un compte,
  et il y ramène. ⚠️ Pas d'`IntersectionObserver` — il ne tire pas dans le
  volet de mise au point ; un calcul au défilement se rejoue à la main
  (`window.__sclRail`, exposé pour le banc).
- **Deux défauts d'habillage, mesurés puis corrigés** : la barre
  d'avancement ne se lisait pas (piste crème + remplissage ambre clair sur
  panneau crème — à 22 % on voyait une ligne pâle), et le bouton éteint à
  `opacity: .55` se lisait comme un décor. Piste CREUSÉE, remplissage PLEIN,
  et un bouton éteint qui garde sa FORME et son encre.
- ⚠️ **Le mot du champion se cite avec `<q>`** : « » est une convention
  FRANÇAISE, relevée à l'écran au milieu d'une phrase anglaise.
- ⚠️ La carte du « i » est posée sur le BODY en `position: fixed` : elle
  DIVISE par le zoom du corps avant d'écrire `left`/`top`. Septième fois.

#### LE COMPTEUR remplace la barre droite, et les trois exigences disent QUOI

« L'écran n'indique pas ce qu'il manque est où, de plus je trouve assez léger
le nombre d'info que l'on a, j'imaginais un truc un peu plus sympa avec une
courbe pas juste droite mais en mode arrondie (compteur de vitesse). »

Le premier reproche était un **défaut**, pas une préférence : le panneau est
rendu par le serveur, et `relire()` — qui tire après chaque écriture — ne met
à jour que les CHIFFRES, sans toucher au HTML du serveur. La liste de travail
restait donc dans l'état du chargement de page, et le bouton annonçait
« Masquer » au-dessus de RIEN. Une seule implantation désormais, et c'est le
JS — `rendreListe()`, appelée par `majValeurs()`, donc par le même chemin que
les chiffres.
⚠️ Le premier cliquet est resté **VERT** sur ce défaut : il cherchait
« rendreListe() » entre `majValeurs` et `majRail`, or la DÉFINITION de
rendreListe vit entre les deux — il lisait son propre sujet. D'où
`_corps_js()`, qui borne un corps de fonction sur SA propre accolade.

Le second était une question de FORME, tranchée sur **prototype cliquable à
l'échelle réelle** — trois organisations autour du même cadran. Retenue :
**A — le compteur et les trois exigences**, qui répond à « qu'est-ce qui
manque ».

- **Le cadran** : un arc de 240°, du bas-gauche au bas-droit. Les graduations
  marquent chaque ACTIVITÉ — on compte des activités, pas des pourcentages,
  et c'est ce qui fait qu'on lit « 9 sur 36 » sans aller chercher le chiffre.
  ⚠️ Plafonnées à 40 : l'arc fait 354 px, soit 8,9 px entre deux traits ; une
  carto du pilote en porte six cents, et l'échelle se lirait comme une
  hachure.
- **Les trois exigences**, une barre chacune : on voit d'un coup que les
  garants sont acquis (31/36) et que ce sont les outils qui traînent (9/36).
  C'est ce que l'ancienne phrase « Il manque : 1 tâche · 2 outils » disait en
  petit, et sans dire SUR COMBIEN.
  ⚠️ Elles montrent ce qui est ACQUIS (`total − manque[code]`), pas ce qui
  manque : une barre remplie avec le second se VIDERAIT à mesure qu'on
  avance.
- ⚠⚠ **218 px, pas 174** : `body:has(.pg-root)` porte `zoom: .8`, et le
  prototype vivait dans une page SANS ce zoom. Repris tel quel, le cadran
  arrivait 20 % plus petit. 218 × 0,8 = 174, la taille éprouvée à l'écran.
- ⚠️ **La hauteur est RÉSERVÉE en CSS** (0,92 × 218 = 201) : le cadran se
  dessine dans le JS — un arc demande de la trigonométrie, et le bâtir AUSSI
  en Jinja ferait deux implantations du même dessin, exactement le défaut
  qu'on venait de corriger sur la liste. Les données arrivent par
  `SOCLE_ETAT`, donc sans aller-retour ; seule la hauteur manquerait.
- **La liste s'ouvre D'ELLE-MÊME** sous sept activités restantes : c'est le
  moment où l'on chasse les dernières, et c'est précisément ce qu'on
  reprochait à l'écran. Au-delà elle reste pliée — vingt-huit lignes
  enterreraient les fiches qu'elles désignent — et le bouton porte le compte.
  ⚠️ Posé UNE fois, à l'init : dans `majValeurs`, chaque écriture rouvrirait
  ce que l'on vient de replier.
- **Les deux cas de bord** (carto vide, plus rien à compléter) vivent dans la
  ZONE DE LA LISTE : elle est le seul endroit du panneau qui parle des
  activités, et une phrase posée ailleurs aurait demandé un troisième
  emplacement à tenir.

⚠⚠ **Et la mesure a trouvé ce que l'œil n'avait pas vu — la maquette portait
le même défaut.** Un balayage de 240° fait pointer l'aiguille vers le BAS à
ses deux extrêmes, où elle atteint C + r/2 : à 36/36, **dix pixels de
recouvrement sur le coin haut-droit des chiffres**, et comme le texte est
peint par-dessus, la pointe paraissait s'arrêter dans le « 6 ». On DESCEND la
lecture (0,805·T) plutôt que de raccourcir l'aiguille — un pointeur à 31 % du
rayon ne ressemble plus à rien — et la boîte passe de 0,859·T à 0,92·T, soit
dix pixels réels de plus. Mesuré après : **9,1 px d'écart**.
⚠️ Le cliquet rejoue la géométrie en Python, et les proportions sont LUES
dans le JS, jamais recopiées : un cliquet qui porte sa propre copie de la
formule ne garde rien.

⚠️ Les couleurs du cadran sont des ATTRIBUTS SVG — aucun jeton CSS ne les
atteint — et s'écrivent donc à la main, comme celles du relief de la page
Compétences. Seules les deux encres de texte passent par une classe.

Catalogue : −10 clés par langue (`manque`, les six `m_*`, les deux `reste_*`,
`voir`), +5 (`x_garant`, `x_tache`, `x_outil`, `voir_1`, `voir_n`).
⚠️ `pretes_1/n` était injectée et lue par PERSONNE : elle porte désormais
l'étiquette du cadran pour un lecteur d'écran, avec ses DEUX nombres
(`role="img"` masque le texte interne du SVG). Et l'analyse d'injection lit
maintenant les TABLES de libellés (`CHIP`, `LIB`) : les pastilles y
échappaient entièrement, une injection oubliée serait passée inaperçue.

#### ⚠️ Le bloc « palier » a quitté la fenêtre des propositions

Il y affichait une bande « il reste n activités à compléter » et **éteignait
« Envoyer »** — au nom d'une règle qui ne s'applique plus en phase 2, puisque
`/envoyer` ne regarde plus le palier (un brouillon ne peut pas exister pendant
le premier remplissage). Ce n'était pas du ménage : c'était un défaut
fonctionnel. Partis : `chargerSocle`, `rendreSocle`, `detailManque`,
`boutonSocleInfo`, `allerA`, la zone `acp-socle-z`, **20 clés `acp.socle_*`**
et 110 lignes de CSS.

⚠️ **Et les deux écrans ne cohabitent jamais** : `_propose_activites` rend
faux dès que `can_fill` ou `en_examen`. Vu au banc en basculant l'état à la
main — le bandeau « vos modifications partent à l'examen » s'affichait à côté
du panneau, annonçant une SECONDE file là où il n'y en a qu'une.

#### Trois pièges, dont deux payés dans la même journée

- ⚠️⚠️ **Une suppression ligne à ligne dans un catalogue Python doit tenir
  compte des valeurs sur PLUSIEURS lignes.** En ne retirant que la ligne de
  la clé, j'ai laissé **9 continuations orphelines** et `translations.py` ne
  se compilait plus — 265 erreurs d'un coup, dans des fichiers qui ne parlent
  pas du sujet.
- ⚠️⚠️ **Un cliquet qui cherche une chaîne doit retirer les COMMENTAIRES** :
  celui qui explique un retrait cite forcément ce qu'il retire. Le piège a
  mordu **trois fois ce jour-là** — dans le script de retrait, puis deux fois
  dans mes propres tests (une clé construite citée en commentaire, et le nom
  de l'observateur qu'on explique ne pas employer). D'où `_js_nu()` dans
  `test_169`.
- ⚠️ **Une clé i18n ne s'ASSEMBLE pas**, ni dans un gabarit (`t('socle.c_' +
  code)` est relevé comme la clé « socle.c_ ») ni dans le JS (`nf('m_' +
  code, n)`). Les six libellés passent par une table écrite en toutes
  lettres.
- ⚠️ `socle_par_id` est une clé étrangère vers `users` : `delete_user` la
  détache, sinon la suppression d'un compte tomberait en 500 **en production
  seulement** (PostgreSQL applique les FK, SQLite non).

#### Mesures

Parcours complet éprouvé en vrai HTTP sur le banc : saisie → écriture
directe (201, la tâche en base) → soumission refusée sur palier incomplet
(409 `palier`) → écriture pendant l'examen refusée (409 `socle_en_examen`) →
renvoi sans mot refusé (409 `sans_mot`) → renvoi avec mot lu par le champion
→ resoumission → validation → **la même écriture rend 202 `proposition`**. Un
`user` reste à 403 `lecture_seule` du début à la fin.

Tests : `tests/test_169_socle_saisie.py` (**86 cas**, NEUF) ;
`test_159_palier_soumission.py` reconstruit (30 cas — ce qui restait vrai est
gardé tel quel, ce qui affirmait la simulation est RÉÉCRIT, pas supprimé) ;
`test_112`, `test_114`, `test_162` posent `socle_etat="valide"` sur leur carto
— ils éprouvent le régime d'APRÈS. **Treize défauts remis un par un, treize
cliquets tombés.** Suite : **5 199 passés**, 1 sauté ; arbre d'image 5 081 + 119 sautés.

Banc : `tools/devrun_partage.py` sème les TROIS états en même temps (#1 en
saisie avec 8 activités complètes, #4 soumise et complète, #3 validée), plus
`/devrun/socle/<état>` et `/devrun/carto/<id>`. ⚠️ Sans les activités à
moitié remplies, on ne voit jamais que le cas malheureux ; et l'import carto
pose un garant à CHAQUE activité, donc la troisième exigence ne se voit qu'en
le retirant à la main.

#### Ce qui n'est PAS fait, et qui se décide

- **Le bandeau de la page Carte ne compte pas les socles soumis.** La fenêtre
  d'examen est faite pour des GESTES et pour un diagramme ; ajouter le compte
  sans ajouter la liste ferait diverger le chiffre de ce qui s'ouvre.
  L'attente vit donc dans la **fenêtre de bienvenue** (« ce qui vous
  attend »), un COUNT que seul un valideur paie.
- **Aucune pop-up de décision** pour le champion : le panneau porte le mot du
  coordinateur en rouge, en tête, et la validation se voit au changement de
  régime. Une pop-up demanderait une colonne de plus (le valideur) — à
  décider.
- **Rouvrir la saisie d'une carto validée** n'existe pas : cela rendrait
  l'écriture directe sur des données officielles, et personne ne l'a demandé.

### LES DEUX FENÊTRES, ET LA NORME QU'ON NE DEVINE PLUS (2026-11-27)

Quatre demandes : reprendre le style de la fenêtre **Technicité** (« il me
semble que je t'avais déjà demandé de t'en charger »), celui de la fenêtre
**Plan de formation**, revoir la **fonctionnalité** du plan (« l'app a pas mal
évolué depuis la création de la fonctionnalité ») et se pencher sur la **norme
de l'entreprise** (« on doit la déduire de la performance mais je n'ai pas
l'impression que cela marche super »). Tranché sur **maquette à l'échelle
réelle** (artefact « Compétences — les deux fenêtres et la norme », quatre
onglets) : c'est la douzième fois que la méthode évite une journée écrite pour
rien. Arbitrage rendu : les deux styles, **C** pour la norme (« le truc sur pas
de devinette »), et le plan laissé à mon appréciation.

#### ⚠️⚠️ La TECHNICITÉ ne s'alignait pas — 97 px d'écart entre trois lignes

La passe du 24/11 avait repris cette fenêtre et n'avait pas touché son vrai
défaut, qui se mesure : le nom du domaine était en `flex: 1 1 150px`, donc
chaque ligne poussait ses deux échelles où elle pouvait. Relevé à l'écran, le
« Requis » partait à **x = 472 / 513 / 569** et le « Démontré » à 622 / 664 /
719. On ne pouvait **pas comparer deux domaines**, ce qui est tout l'objet
d'une liste.

C'est une **TABLE** (grille à quatre colonnes, `minmax(130px,1fr) auto auto
auto` — c'est le nom qui cède, deux échelles de cinq crans ont une largeur
fixe). Mesuré après : **0,0 px d'écart**, dans les deux langues.

- Les étiquettes « Requis / Démontré » montent en **EN-TÊTE** : écrites une
  fois au lieu de six, et c'est ce qui libère la place des crans. `domEchelle`
  devient `domPas` — elle ne rend plus que les crans.
- Les crans faisaient **20,8 × 16 px RÉELS, chiffre de 8,8** (`body.pg` porte
  `zoom: .8`), sous le plancher de 11 de l'échelle typographique, à côté d'un
  cran de notation de 76 px de haut. Ils passent à **27,2 × 22,4 @ 11,6**.
- ⚠️ **LE TEAL**, sa couleur à elle (`--cv-t-05` … `--cv-t-80`, encre à
  6,0:1 sur blanc). Elle emprunte(ait) le **bleu** de la note qui fait foi et
  le **tilleul** de ce qui est tenu, alors que c'est un **axe à part**. Le teal
  avait été écarté le 15/09 « parce qu'il se lit comme du vert » — c'était vrai
  contre le vert FRANC d'alors ; depuis le 23/11 ce qui est tenu est TILLEUL
  (jaune-vert), et les deux ne se confondent plus. Les **verdicts** gardent
  prune / tilleul : « en écart » et « tenu » veulent dire la même chose
  partout, et la colonne des verdicts n'est pas la colonne d'un axe.
- ⚠️ **Un domaine NULL a son verdict** — « non situé », en neutre : sans lui la
  colonne s'effondre une ligne sur trois, et « pas encore regardé » n'est ni 0
  (« aucun ») ni « au niveau ».
- ⚠️ **L'ajout est un BOUTON qui déplie**, et son libellé n'est plus FAUX : le
  ternaire était inversé, on lisait « Rattacher un domaine qui existe »
  au-dessus d'un champ « Nouveau domaine… » quand tout était déjà rattaché.
  ⚠️ `.tch-champs[hidden]` est déclaré à la main — `[hidden]` est une règle du
  NAVIGATEUR, une classe d'auteur qui pose un `display` l'emporte. **Huitième
  fois** dans cette application.
- **L'explication passe derrière un « i »** (`tech_quoi` + `tech_note`) : trois
  lignes en tête pour une règle qu'on lit une fois, et elles prenaient la place
  de la table. ⚠️ `brancherInfo` ÉCHAPPE son texte : les marqueurs `[[b]]` s'y
  afficheraient en clair, on les retire.
- **La fenêtre passe à 900 px** (`[data-vue="tech"]`, comme `evol` le fait déjà
  à 1060) : la table mesure 818 px au plus serré. ⚠️ `ouvrirDialogue` repose
  `vue = 'eval'` à chaque ouverture, donc la largeur ne déborde pas sur les
  deux autres dialogues.

#### Le PLAN : une passe de densité, et le piège d'une règle déclarée plus bas

La structure est juste (le besoin à gauche, la capacité à droite, un verdict en
direct) et ne bouge pas. Relevé : **14 textes sous le plancher de 11 px
réels**, dont les trois étiquettes d'une action — « Objectif / Livrable /
Réussi quand » — à **9,2**. Mesuré après : **plus aucun**.

- ⚠️⚠️ **Et deux d'entre eux ont résisté à la passe.** Le bloc « LISIBILITÉ DES
  FENÊTRES » (15/09) redéclare `.cv2-dit` à 13 px et `.cv2-prop` à 11,5 **deux
  cents lignes plus bas** : à spécificité égale, c'est lui que le navigateur
  applique, et mes retouches sur les règles d'origine ne changeaient RIEN. La
  fenêtre du plan reprend donc les siennes (`#cv2-plan-body .cv2-dit`), après
  ce bloc et plus spécifique. ⚠️ On ne remonte pas les deux classes en entier :
  elles servent aussi au diagnostic et à la configuration.
  ⚠️ **Et le cliquet du plancher restait VERT** — il lisait la première règle
  qu'il croisait. `_taille_effective()` prend la DERNIÈRE déclaration qui vise
  la classe : *un cliquet qui lit une règle CSS doit lire celle qui GAGNE.*
  C'est le banc qui l'a trouvé, pas le test.
- **Le bandeau prend le NUIT** des deux autres surfaces sombres de la page : il
  était violet, et trois dégradés sombres différents sur un même écran se
  lisent comme un défaut d'impression.
- **L'échéancier porte ses semaines** (S1 · S10 · S21 · S31) au lieu d'une
  légende centrée sous un peigne muet. ⚠️ Les repères sont posés sur les
  semaines **RÉELLEMENT dessinées** : calés sur la seule durée visée, ils
  décaleraient dès qu'une barre rouge s'ajoute.

#### ⚠️⚠️ LE PLAN avait été écrit AVANT trois mécanismes — et les ignorait tous

Relevé en cherchant « palier », « domain » et « séance » dans
`plan_formation.py` : **zéro occurrence des trois**. Et son repli
**dégénérait** — mesuré au banc : trois activités en écart rendaient **trois
actions**, une par activité, toutes « Tenir « X » en situation réelle », parce
que tout le reste dépendait de `result_capability_links`, que **seul le
diagnostic remplit**.

- **Les PALIERS** : `contexte_ecart` porte désormais, par résultat,
  `mesurable` / `norme` / `mesure` / `palier` — et l'action parle en CHIFFRES.
  Mesuré au banc : « Amener « Rapport d'essais » à 8 essais · mesuré 5 essais ·
  norme au moins 8 essais · échéance 24/11/2026 ». ⚠️ La **marche posée**
  d'abord (c'est l'engagement en cours), la norme à défaut.
- **Les SÉANCES** : `_prochaine_seance` rend la prochaine prévue, et le panneau
  de capacité la montre avec un bouton **« Caler sur la séance · n sem. »**. On
  réglait une durée visée de douze semaines à côté d'un rendez-vous pris pour
  dans trois. ⚠️ Une séance réservée à un AUTRE rôle ne concerne pas ce plan ;
  une séance sans rôle, si.
- **La TECHNICITÉ** : un domaine à −2 ne produisait AUCUNE action. ⚠️ Lu par la
  MÊME fonction que la fenêtre (`domaines_de_activite`, extraite de sa route) —
  deux lectures d'un même écart finiraient par donner deux verdicts. ⚠️ Et
  l'action est de type **FORMATION** : un domaine technique s'apprend, c'est le
  terrain sur lequel l'activité se joue, pas l'activité elle-même.
- **Le repli ne dégénère plus** : une action de terrain **par RÉSULTAT** en
  écart, chacune avec SON livrable et SON critère. Le plan parle de RÉSULTATS,
  qui sont la chaîne du module.
- ⚠️⚠️ **La porte d'entrée n'a PAS été élargie.** Une activité entre dans le
  plan parce que `categorie_activite` la dit « gap » — sur sa MAÎTRISE, et rien
  d'autre. Un écart purement technique n'ouvre donc pas le plan : élargir la
  porte ferait diverger l'écran et le plan sur le mot « écart », ce qui a déjà
  été corrigé une fois (15/09). La technicité ENRICHIT les activités déjà en
  écart ; elle ne les fait pas entrer.
- Le prompt apprend les trois (`plan_formation.system`, dans le CATALOGUE —
  l'image client le sert chiffré), et l'IA reçoit `prochaine_seance`,
  `domaines_techniques_en_ecart` et le bloc `mesure` de chaque résultat.

#### LA NORME : elle n'est pas déduite, c'est son PRÉ-REMPLISSAGE qui ratait

Bonne nouvelle d'abord : elle est **stockée, structurée et fait foi**
(`Data.norme_valeur/unite/sens`, ce que lit `mesurable()`). La déduction ne
sert qu'à pré-remplir. Deux défauts mesurés :

1. ⚠️ **Elle lisait un champ presque toujours VIDE** : l'indicateur de
   performance d'une connexion sortante (colonne « Performance » de la liste
   des activités). Relevé au banc, les deux sorties de l'activité ouverte
   rendaient `indicateur: ""` pendant que `minimum_performance_text` portait
   « Plan d'essais couvert à 100 % » — le champ que la fenêtre de configuration
   collecte ELLE-MÊME.
2. ⚠️⚠️ **Elle prenait le PREMIER nombre de la phrase.** Corpus de 28
   indicateurs plausibles : **22 justes, 6 faux — et les six d'une seule
   cause** : un numéro d'étiquette (« Indicateur 1 — délai sous 5 jours » → 1),
   une année (« Objectif 2026 — taux 95 % » → 2026), un « n°2 », la borne
   BASSE d'un intervalle. Et comme l'unité doit SUIVRE immédiatement le nombre
   retenu, la perdre faisait retomber le sens sur son défaut : **une cause,
   trois symptômes**.

**Le parseur prend le dernier nombre PORTÉ PAR UNE UNITÉ** ; à défaut le nombre
s'il est SEUL (il n'y a rien à choisir, donc rien à deviner) ; sinon **rien** —
mieux vaut un champ vide qu'un chiffre faux, c'est lui qui décidera du niveau de
quelqu'un. Mesuré après : **27/28, aucune lecture fausse** ; la seule manquée ne
propose rien (« Volume 1 500 pièces » — deux nombres non portés, et on ne
tranche pas à la place de celui qui a écrit la phrase).

**Et la norme se règle LÀ OÙ LA PHRASE S'ÉCRIT** (option C) : trois champs —
valeur · unité · au plus/au moins — à côté de « Réussi quand… », dans la
fenêtre de configuration.
- ⚠️ **RIEN n'est pré-rempli.** Ce que le serveur sait lire est offert en
  **BOUTON** (« Proposé d'après cette phrase : 5 j · au plus — Utiliser ») :
  l'app propose, la personne pose. C'est toute la différence avec ce qu'on
  retire. Et ce qui est ENREGISTRÉ l'emporte sur la proposition.
- ⚠️ Les trois champs sont EXACTEMENT ceux de la fenêtre des paliers
  (`.pal-champs`, `champUnite`, `lireUnite`), et l'écriture passe par les MÊMES
  gardes (`_lire_norme`, `_peut_regler_la_norme`) : deux routes qui écrivent
  les trois mêmes colonnes avec deux validateurs finissent par ne plus écrire
  la même chose.
- ⚠️ **La ZONE est la LIGNE**, pas la fenêtre : `lireUnite` et `brancherUnite`
  prennent le PREMIER champ qu'ils trouvent, et il y a une ligne par sortie —
  on réglerait l'unité de la première pour tout le monde.
- ⚠️ **On ne touche à la norme que si la clé est ENVOYÉE** (même règle que
  `evidence` dans `/mastery/evaluate`) : un client plus ancien effacerait sinon
  une norme que personne n'a retirée. Une valeur VIDE, elle, rend la sortie
  qualitative — c'est un choix, pas une suppression.
- ⚠️ `.cv2-cf-std > label` et non `label` : les trois champs sont des `<label>`
  eux aussi, et la règle leur posait un `display: block` — même spécificité que
  `.pal-champs label`, donc c'est l'ORDRE du fichier qui tranchait.

#### ⚠️⚠️ Et la fenêtre de configuration était devenue INJOIGNABLE

Trouvé au banc, **en allant poser une norme**. Son SEUL chemin d'accès était le
bouton de `.ev-vide`, qui ne s'affiche que si l'activité n'a **aucune** sortie
— or `activity_mastery` appelle `get_activity_outputs`, qui **matérialise** les
connexions sortantes : dès qu'une activité a une flèche qui en part, elle a des
sorties, et le bouton disparaît pour toujours. Depuis « TOUTES les sorties, sans
filtre de nature » (nov.), la nature `RESULT` ne sert plus de porte, et plus
rien n'ouvrait cette fenêtre.

C'était sans grande conséquence tant qu'elle ne portait que la nature des
sorties (que personne ne lit) et leur phrase de réussite. **Ce ne l'est plus :
la norme s'y règle.** La rangée des réglages porte donc une **quatrième
pastille**, « Configurer l'activité », pour le développeur seulement — et sa
valeur dit s'il faut l'ouvrir (« 1 sortie sans norme » / « toutes chiffrées »),
parce que « 2 sorties » aurait répété ce que l'écran montre déjà.
⚠️ À quatre, la rangée repasse à **deux colonnes** : à trois, le quatrième
restait seul avec deux tiers de vide. La règle est déclarée APRÈS celle des
trois — à spécificité égale, c'est l'ordre du fichier qui tranche.

#### ⚠️ Un lien MORT dans la fenêtre de bienvenue

Trouvé au banc aussi : `Code/bienvenue.py` pointait la ligne « séances à
tenir » sur `/competences/`, qui rend **404** — la page est
`/competences/view`. Cette fenêtre s'affiche sur **chaque page** de
l'application. Cliquet : `test_127::TestAucunLienMort` relève tous les `href`
que le module écrit et exige qu'ils résolvent dans `url_map`.

#### Mesures

Tests : `tests/test_170_fenetres_et_norme.py` (**46 cas**, NEUF) ; `test_148`
(7 cas RÉÉCRITS sur la nouvelle structure, pas supprimés), `test_77` (3),
`test_93` (3), `test_109` (le cliquet des pluriels apprend à lire `COMMUN`),
`test_127` (+1). **44 gardes retirées une par une, 44 cliquets tombés** — dont
**quatre qui ne gardaient RIEN** au premier essai, tous de la même famille :
chercher la présence d'un nom au lieu de son EMPLOI, ne pas borner la zone, et
lire une règle CSS que le navigateur n'applique pas.
Suite complète : voir le commit.

Éprouvé au banc (`tools/devrun_competences.py`, qui sème désormais **trois**
domaines — les trois verdicts — un domaine libre au catalogue et un indicateur
de performance) à 1600 px dans les deux langues : table alignée au pixel,
plancher tenu dans tout le plan, cinq actions dont une de technicité et trois
en chiffres, la séance et son bouton (12 → 2 semaines), la norme proposée puis
posée (5 j au plus), **zéro fuite française sur l'écran anglais**, zéro erreur
console, zéro débordement horizontal.

### LE PLAN DE FORMATION : une PAGE, et deux dessins (2026-11-27)

« C'est vraiment pas bon le plan de formation actuellement : la pop-up est
trop petite, visuellement c'est pas très beau et surtout on comprend que
dalle, c'est pas du tout intuitif. » Les trois reproches se chiffrent, et ils
ont été chiffrés au banc **avant** de redessiner :

| | relevé |
|---|---|
| la fenêtre | **800 × 736 px réels** dans 1600 × 1000 — **50 % de la largeur** |
| à dérouler | **1 089 px** pour 794 visibles |
| à l'ouverture | un cadre de 800 × 277, presque vide |
| le verdict « il manque 74 h » | **6ᵉ élément** de la colonne de droite |
| « Rapport d'essais » dans sa carte | écrit **trois fois** |
| l'écart qui justifie le plan | **disparaît** dès que le plan est proposé |
| l'échéancier | 31 barres de 3 px pour dire « ça déborde » |

⚠️ **Le « on comprend que dalle » se diagnostique** : l'écran pose un argument
en trois temps — *voilà ce qui manque · voilà ce qu'on fait · voilà si ça
tient* — et il n'en montrait **jamais deux ensemble**. Le « pourquoi »
n'existait que dans l'état vide, et il s'évaporait au moment où le plan
apparaissait.

**Tranché sur PROTOTYPE cliquable à l'échelle réelle** (trois organisations,
puis deux reprises du contenu) — la treizième fois que la méthode évite une
journée écrite pour rien. ⚠️ Et le prototype porte `zoom: .8` sur sa scène :
sans lui, chaque valeur arrive **20 % plus petite** dans l'application, le
piège déjà payé sur le compteur du socle.

#### Une PAGE, comme l'évaluation l'est devenue le 14/10

`#cv2-ecran-plan` rejoint `ECRANS` et `montrerEcran` ; `pleineLargeur` efface
la barre des collaborateurs et le bandeau de page. Mesuré : **86 % de la
largeur**, et plus aucun défilement INTERNE. La fenêtre, son en-tête, son
corps et son pied quittent le gabarit.
⚠️ `state.planRetour` retient d'où l'on vient : le plan s'ouvre depuis la page
d'évaluation ET depuis le diagnostic, et un retour qui tomberait toujours sur
la galerie ferait refaire deux clics à chaque fois.

#### ⚠️⚠️ Les deux dessins REMPLACENT, ils ne s'ajoutent pas

Le premier jet gardait les listes **et** ajoutait les images : « cela devient
presque trop chargé et trop complexe, la version juste avant avait le seul
avantage de paraître simple à comprendre ». C'est la règle de cette passe, et
elle se vérifie ligne à ligne :

- **la FRISE** prend la place de l'échéancier en peigne, **des deux chiffres
  d'entrée du verdict** (sa longueur totale EST le besoin, l'étiquette de son
  trait blanc la capacité) et **de la barre de répartition par nature** (elle
  colore par nature et porte sa légende) ;
- **le CLASSEMENT** prend celle des trois jauges **et de la liste de détail**
  qui redisait, activité par activité, ce que la colonne du chemin écrit déjà ;
- **le chemin reste la seule LISTE** : c'est lui qui porte le texte et les −/+.

Partis avec : `majMix`, `renderSemaines`, `curseur`, `majCurseur`, `blocSeance`,
`bindPlan`, `fermerPlan`, et **16 clés de catalogue** (`plan_need`,
`plan_capacity`, `plan_need_total`, `plan_cap_total`, `plan_mix`,
`plan_target`, `plan_deliv`, `plan_juste`, `plan_seance_cal`,
`plan_week_step_*`, `plan_gap_intro`, `plan_seance*`). Une clé qu'on retire en
même temps que son seul lecteur ne laisse rien derrière elle.

#### LA FRISE — une seule image pour « quand » et « ça tient »

⚠️ **Les heures et les semaines sont la MÊME grandeur** — une semaine, c'est
les heures qu'on y met — donc la longueur d'un segment dit à la fois ce qu'il
coûte et combien de temps il prend. Le trait blanc est la capacité ; ce qui est
à sa droite est hachuré. **Le verdict n'est plus un nombre à chercher, c'est
l'endroit où la barre CASSE.**

- ⚠️ **La hachure VOILE, elle ne couvre pas.** À 46 % sur des raies de 5 px
  pour 6 de vide, les numéros des segments qu'elle traverse ne se lisaient
  plus — relevé **sur la capture**, pas à la mesure. 30 % sur 4 px pour 14.
- ⚠️ **L'étiquette de coupe se borne aux deux bords** : le bandeau est en
  `overflow: hidden`, et près du bord une étiquette centrée serait coupée sans
  rien signaler.
- ⚠️ **Le trait descend jusque sous l'axe des semaines** — c'est la même
  frontière dans les deux unités — **mais pas jusque dans la légende**, qu'il
  barrait.
- ⚠️ **L'axe est posé sur les semaines RÉELLEMENT couvertes**, pas sur la seule
  durée visée : il décalerait dès que le besoin déborde.
- La légende ne nomme que les natures **réellement présentes** : une entrée
  pour une couleur absente du dessin n'apprend rien.

#### LE VERDICT — UN seul chiffre

Il en portait trois (« à combler », « disponibles », « il manque »). Les deux
premiers sont les ENTRÉES de la soustraction, et la frise les montre déjà.
Reste celui sur lequel on agit, en 46 px, et la phrase dit l'ALTERNATIVE —
plus le chiffre qu'on vient de lire à dix centimètres.

#### LE CLASSEMENT — les activités sur une échelle commune 0 → 4

- ⚠️ **Le requis est un TIRET posé sur la colonne**, pas un remplissage : une
  cible se dessine, elle ne se remplit pas. C'est le device de la vue
  d'ensemble, repris pour la même question.
- ⚠️ **Un socle de 10 px** dès qu'un niveau est posé : à hauteur nulle, le
  niveau 0 se confondrait avec « pas de niveau du tout ». (NULL n'arrive pas
  ici : un plan ne se bâtit que sur du MESURÉ.)
- ⚠️ **Le bouton prend toute la VOIE, pas la largeur de sa barre.** Mesuré :
  dans 62 px, le nom de l'activité partait sur quatre lignes. La barre fait
  58 % du bouton, le tiret 78 %, et **la zone du nom est bornée** — sinon elle
  pousse la légende de 16 px.
- ⚠️ **Il SUIT le défilement** (`position: sticky`) : mesuré, il s'arrête à
  400 px en face d'une colonne d'actions de 919, et c'est la référence qu'on
  garde sous les yeux en lisant la liste.
- Cliquer une colonne met en avant les actions de CETTE activité dans la
  colonne d'à côté : c'est ce qui relie les deux dessins.

#### LA CARTE D'ACTION, resserrée

248 px, le nom du résultat écrit **trois fois**, et trois étiquettes en
capitales rendues à **9,2 px RÉELS** (le plancher est 11). Désormais : le titre
est l'action — une fois — la ligne qui suit porte la mesure telle que le
serveur la rédige (« mesuré 5 essais · norme au moins 8 essais · échéance
24/11/2026 »), et « Réussi quand » attend derrière un « ? ».
⚠️ **« Livrable » est parti** : dans le repli c'est le nom du résultat, donc le
titre. Il ne revient que quand le titre ne le dit pas déjà.
⚠️ **Le segment de frise et la carte s'allument ENSEMBLE, par CLASSE et sans
re-rendu** : un re-rendu à chaque survol ferait sauter ce qu'on regarde.

#### Les deux états VIDES, éprouvés à part

C'est le seul chemin que le banc ne joue pas tout seul : aucun collaborateur
n'a à la fois un rôle sans écart et un rôle sans action.
- ⚠️ **Retirer la DERNIÈRE action repasse par la page entière**, qui porte
  l'état vide et sa porte de sortie. Mesuré sans ce retour : une frise vide
  sous un verdict qui annonce « il reste 48 h » — arithmétiquement juste, et
  muet.
- ⚠️ **Sans aucune activité en écart, il n'y a PAS de bouton « Proposer »** :
  il n'y a rien à proposer. Mesuré après : divs équilibrées (9/9), zéro erreur.
- ⚠️ **L'espace avant les deux-points est une règle FRANÇAISE** : l'info-bulle
  du « ? » passe par `DP`, qui suit la langue. C'est `test_82` qui l'a
  attrapée, sur la suite complète.



#### Le plancher typographique, mesuré puis tenu

11 px RÉELS, soit 13,75 écrits sous le `zoom: .8` du corps. Relevé avant :
**14 textes en dessous**, dont la provenance du plan à **9,2**. Après : **4**,
et les quatre sont nommés — deux graduations de la frise (les heures d'un
segment, les repères de son axe), et deux classes PARTAGÉES de l'application
(`.ev-retour`, `.btn`), identiques sur la page d'évaluation.

#### ⚠️ Trois pièges, tous déjà connus

- ⚠️⚠️ **Un découpage de section CSS doit jeter ce qui RESTE du commentaire
  d'en-tête.** Le repère de section EST un commentaire : la coupe tombe en son
  milieu, son `/*` est parti, et `_sans_commentaires_css` ne le reconnaît plus
  — le cliquet du gris s'est attrapé sur la phrase qui l'explique. **Onzième
  fois** que cette famille se présente.
- ⚠️ **Un cliquet qui cherche une chaîne doit viser un nom EXACT** :
  `cv2-barre` est un préfixe de `cv2-barres` (la vue d'ensemble), et le cliquet
  lisait le mauvais nom.
- ⚠️⚠️ **Et un cliquet qui boucle doit lire sa variable de boucle.**
  `for cle in ("juste", "seance"): assert "borner('semaines'" in r` vérifiait
  **deux fois la même chose** : la troisième branche (le pas des deux réglages)
  n'était gardée par personne, et le cas est resté **VERT** sur le défaut remis.
- ⚠️ **Le heredoc du shell avale les antislashs** — deux fois de plus dans
  cette passe. Un fichier qui porte des échappements ou du texte français
  s'écrit avec la Write tool, jamais par heredoc.

Tests : `tests/test_170_fenetres_et_norme.py` gagne `TestLePlanEstUnePage`
(16 cas) et voit `TestLePlanChangeDeDensite` RÉÉCRITE ; `test_148` voit
`TestLaFenetreDuPlan` devenir `TestLaPageDuPlan` (5 cas réécrits) et `test_140`
son cliquet du bouton de retour (QUATRE écrans en portent un). **22 défauts
remis un par un, 22 cliquets tombés** — dont deux qui ne gardaient rien au
premier essai. Éprouvé au banc (`tools/devrun_competences.py`) à 1280 et
1600 px dans les deux langues : **frise sans trou** (somme des segments 1039,8
pour 1039,9 de piste), tiret du requis à **0 px** de sa graduation, nom hors de
sa voie **0 px**, **zéro fuite française** sur l'écran anglais (176 textes
relevés, attributs compris), zéro clé brute, zéro débordement horizontal, zéro
erreur console.

### LA CHARGE DE TRAVAIL : le mois d'une analyse, et le damier de la page RH (2026-11-28)

Trois demandes d'un coup : rendre VISIBLE le « Proposer un plan » quand il n'y
a pas encore de plan, montrer que l'IA tourne, et surtout — fonctionnalité
neuve — dater les analyses de temps pour en tirer, page RH, le poids de chaque
rôle et de chaque personne, avec un plafond de prévention.

#### L'écran vide du plan invite, et l'attente se voit

⚠️ **« Aucun plan n'existe encore » et « vous ne pouvez rien faire ici » se
ressemblaient** : un texte GRIS centré (`.cv2-plan-vide`, `color: --muted`) et,
pour toute porte, une pastille discrète au fond d'un pied de page.
`blocVide()` porte donc l'action EN PLEIN — le rapport inversé déjà tranché sur
les pages Temps et Carte, pastille pastel sur fond vif — avec **de quoi partir
sous les yeux** : les activités en écart et leur écart, qui prouvent qu'il y a
matière.
- ⚠️ **Une seule porte** : le pied n'est pas rendu dans cet état (sa ligne de
  provenance ne décrirait rien, et deux boutons pour un geste finissent par
  diverger).
- ⚠️ `plan_empty_d` parlait encore des **curseurs**, retirés le 27/11 : une clé
  qu'on remplace, pas qu'on garde.

⚠️ **L'appel IA dure trois secondes, et le bouton se contentait de passer en
« Génération… »** : rien ne bougeait, et on cliquait une seconde fois.
L'attente est le **SQUELETTE de la frise** — les segments se remplissent de
gauche à droite dans les trois couleurs de nature : on voit ce qu'on attend, au
lieu d'une roue qui pourrait tourner pour n'importe quoi. Rien ne clignote sous
`prefers-reduced-motion`.
- ⚠️ **L'en-tête est REBÂTI**, pas conservé : garder celui en place laissait la
  frise de l'ANCIEN plan sous les yeux pendant qu'on en calculait un autre.
  `teteDuPlan()` est donc écrit une fois pour les TROIS états (le plan, le
  vide, l'attente) — trois copies finiraient par diverger, et c'est lui qui dit
  de qui et de quel rôle on parle.
- ⚠️ Un échec repasse par `renderPlan()` : laisser le squelette, c'est annoncer
  un plan qui ne vient pas.

#### LE MOIS d'une analyse de temps — `Code/periode.py`

Une analyse de temps n'est pas vraie pour l'éternité : une charge fluctue, et
un poids de rôle relevé en janvier ne dit rien de novembre. Les **quatre**
analyses (projet, activité, rôle, faiblesse) portent donc le mois qu'elles
décrivent.

- **Format « YYYY-MM », VARCHAR(7)** : il se trie LEXICALEMENT (donc en SQL,
  sans conversion) et traverse les deux dialectes tel quel. Un mois n'est pas
  une date — stocker le 1er en TIMESTAMP inviterait à y lire un jour qui n'a
  aucun sens ici.
- ⚠️ **Jamais NULL après la reprise** : `periode_posee(d, actuelle)` pose le
  mois COURANT à la création et garde celui EN PLACE à la modification. Une
  analyse sans période ne figurerait dans aucun tableau par mois et
  disparaîtrait de l'écran sans que personne ne l'ait retirée.
- ⚠️ **`lire_periode` rend le DÉFAUT sur tout ce qui n'est pas un mois** : la
  valeur vient du navigateur, et un mois inventé rangerait une analyse dans une
  période qui n'existe pas.
- **La reprise** (`reprendre_periodes`, au démarrage) pose la période des
  lignes d'avant depuis `created_at`. Sans elle, chaque analyse déjà en base
  sortirait de tous les tableaux par période, et le nouvel écran paraîtrait
  vide sur une instance en service — ce qui se lit comme une perte de données.
  ⚠️ **Aucun marqueur en base, et c'est voulu** : `periode IS NULL` la rend
  idempotente par construction, et rien dans l'application ne peut ramener une
  période à NULL. Contrairement à une reprise qui PROMEUT (`migrer_anciens_
  champions`), elle n'a pas à se garder d'un second passage.
  ⚠️ `TimeAnalysis` (l'analyse d'ACTIVITÉ) n'a pas de `created_at` : il n'y a
  rien à en déduire, ses lignes d'avant restent sans période, et aucun écran ne
  prétend le contraire.

**Le champ vit dans la BANDE** du haut (`tm-periode-m` / `tm-periode-a`) :
c'est une propriété de l'analyse ENTIÈRE, comme son nom, et la bande est le
seul endroit commun aux quatre types — un champ dans chacun des quatre
formulaires, c'étaient quatre occasions d'en oublier un.
- ⚠️ **DEUX `<select>`, jamais un `<input type="month">`** : Firefox ne sait
  pas le rendre et retombe sur un champ de texte où il faut taper « 2026-11 ».
  Et un `<select>` de cette page est habillé par `tm_select.js` : il porte donc
  le même panneau que ses voisins.
- ⚠️ **En DERNIÈRE place** : posé avant le repère de modification, il glissait
  de 180 px dès qu'on ouvrait une analyse.
- ⚠️ Les noms de mois viennent d'`Intl`, dans la langue de la PAGE : douze clés
  par langue dans le catalogue seraient douze occasions de divergence pour ce
  qu'une bibliothèque standard fait déjà. ⚠️ Et l'année d'une analyse plus
  ancienne que la plage offerte s'AJOUTE : sans cela, rouvrir une analyse de
  2021 la rangerait en silence dans une année qui n'est pas la sienne.
- ⚠️ On ne DÉPÊCHE pas `change` en posant la valeur : `tm_select.js` intercepte
  `value` sur l'élément et recopie le libellé tout seul ; l'émettre réveillerait
  les écouteurs des voisins (celui du rôle recharge ses lignes).
- Le mois est la PREMIÈRE pastille des listes de l'accueil : c'est ce qui
  distingue deux analyses du même rôle.

#### ④ LA CHARGE DE TRAVAIL — `Code/charge_travail.py`

**Tranché sur maquette** (artefact « Charge de travail RH », trois
organisations à l'échelle réelle avec les chiffres sortis du calcul).
L'utilisateur a retenu **le DAMIER** — contre ma recommandation, qui était le
tableau à pistes segmentées — et **le poids d'un rôle porté EN ENTIER par
chacun de ses titulaires**.

**La règle, écrite une fois** : le poids d'une personne est la SOMME des poids
de ses rôles, chacun en entier. ⚠️ On ne le DIVISE pas par le nombre de
titulaires : le poids d'un rôle est le travail que ce rôle exige de qui le
tient, et un partage serait une règle que rien dans l'application ne décide. La
ligne du rôle affiche donc son nombre de titulaires — la question reste
visible.

**Le plafond est 80 % d'un temps plein** (`PART_PLAFOND`) : on ne planifie
personne à 100 % de son année. C'est un plafond de PRÉVENTION — l'écran
avertit, il ne refuse jamais : la décision d'affecter appartient à qui affecte.

- ⚠️ **Tout est cadré par une PÉRIODE.** Un rôle sans analyse pour le mois
  regardé est « non mesuré » — JAMAIS zéro — et l'écran dit en quel mois il l'a
  été pour la dernière fois : « jamais pesé » et « pesé le mois dernier » ne se
  corrigent pas de la même façon.
- ⚠️ **Une mesure par (rôle, carto)** : deux analyses du même rôle sur la même
  carto et le même mois sont deux TENTATIVES, pas deux charges — les
  additionner compterait le travail deux fois. La plus récente l'emporte. Entre
  CARTOS, en revanche, les poids s'additionnent : un rôle qui travaille dans
  deux cartos porte bien les deux.
- ⚠️ **L'entité d'une analyse se lit sur sa première ligne** : les lignes
  viennent toutes de la même carto (`/temps/api/role_activities` les filtre sur
  l'entité active). Une analyse bâtie autrement compterait pour sa première
  carto — et comme l'écran NOMME l'entité, l'anomalie se voit.
- ⚠️ **Le calendrier est celui de l'entité ACTIVE**, même quand le tableau
  traverse plusieurs cartos : c'est celui avec lequel `_role_summary` annualise
  déjà, donc les chiffres d'ici et ceux de la page Temps ne peuvent pas
  diverger. L'écran nomme l'entité dont il lit le calendrier.
- ⚠️ **`_role_summary` accepte désormais ses caches** (`params`, `durees`) : UNE
  seule implémentation pour l'onglet Rôle, le tableau de bord et la page RH.
  Jamais une seconde version pour aller plus vite.
- ⚠️⚠️ **Le coût ne grandit pas avec l'effectif**, et il a fallu le mesurer :
  `R.lines` est une relation PARESSEUSE, donc une requête par analyse — relevé
  12 puis 16 requêtes pour quatre analyses de plus. `selectinload` la charge en
  bloc, et `user_roles` n'est lue qu'une fois pour ses deux index. C'est le
  défaut qui mettait le tableau des compétences à deux minutes et demie.
- ⚠️ `GET /gestion_rh/api/charge` porte **sa propre garde** (`can_access_rh`) :
  le `before_request` du blueprint ne ferme que les ÉCRITURES, et ce tableau
  nomme la charge de chacun.

**L'écran** (`rh_charge.js`, `#bloc-charge`) : un damier rôle × cartographie.
La comparaison « pour un même rôle, qu'est-ce que chaque carto demande » se lit
EN LIGNE, et la couleur donne l'ordre de grandeur sans qu'on lise un chiffre.

- ⚠️ **Les COLONNES sont les cartos réellement mesurées ce mois-là**, jamais
  toutes les entités. C'est le défaut mesuré du damier, et la raison pour
  laquelle je ne le recommandais pas : neuf rôles pour trois cartos laisseraient
  les deux tiers des cases vides, et un damier creux se lit comme un tableau
  cassé. Les rôles SANS mesure sortent de la matrice — ils n'ont rien à y
  mettre — et se rangent dessous, chacun avec son dernier mois.
- ⚠️ **La couleur dit la part d'un TEMPS PLEIN, et la légende l'écrit** en
  pourcentages réels : une échelle « léger → lourd » ne dirait pas combien de
  personnes un rôle demande. Elle va du tilleul à la prune — la rampe sémantique
  de l'application, et un rôle au-delà d'un temps plein demande VRAIMENT plus
  d'une personne.
- La colonne **Total** porte le chiffre ET l'image : une piste qui va jusqu'à
  deux temps pleins, avec le trait du premier.
- ⚠️ **La colonne des rôles est COLLÉE à gauche** : au-delà de trois ou quatre
  cartos le damier défile, et sans elle on perd le nom de la ligne qu'on lit.
- **L'anneau d'un titulaire dit SA charge totale** : pour un même rôle, c'est
  ce qui permet de comparer ses tenants d'un coup d'œil — « qui performe ». Les
  mêmes trois couleurs que les pastilles de pourcentage : un quatrième code
  couleur sur le même écran ne se retiendrait pas.
- ⚠️ **Aucun rôle pesé n'affiche PAS un damier à zéro colonne** : il resterait
  trois en-têtes au-dessus de rien, ce qui se lit comme un tableau cassé — alors
  que la vérité est « personne n'a encore pesé de rôle », et qu'elle a une
  suite : la page Temps. Les rôles connus sont quand même listés dessous.

**Dans la section ① des personnes** : une sixième colonne, la charge. Une jauge
SEGMENTÉE par rôle avec le trait du plafond — la grammaire de la frise du plan
de formation, pour la même question — et le nombre d'heures est un BOUTON qui
ouvre le détail.
- ⚠️ **La cellule naît VIDE et `rh_charge.js` la remplit**, dans les deux sens :
  à chaque rendu de la liste (l'événement `grh:personnes`) et dès que sa lecture
  arrive. Aucun des deux fichiers n'attend l'autre, et `gestion_rh.js` n'a pas à
  connaître le calcul de la charge.
- L'échelle de la jauge est la MÊME pour tout le monde (2,5 × le plafond) : des
  jauges à l'échelle de chacun ne se compareraient pas.

**L'avertissement du plafond** s'affiche DANS la ligne où l'on coche le rôle —
une fenêtre par-dessus la fenêtre cacherait le chiffre qu'on vient lire pour
décider (la règle des formulaires de la page Compétences). Il dit la charge
avant, après, et le plafond ; « Ajouter quand même » rappelle `majLien`.

#### ⚠️ Sept pièges, dont trois nouveaux

- ⚠️⚠️ **Une propriété personnalisée ne descend qu'à ses DESCENDANTS.** La
  rampe était déclarée sur `#bloc-charge` — or la cellule de charge vit dans le
  bloc ① des personnes, et la fenêtre de détail comme l'avertissement vivent
  hors de tout bloc. `var(--ch-rouge)` y était INVALIDE, donc transparent :
  mesuré, la pastille d'alerte et le bouton « Ajouter quand même » étaient des
  rectangles vides à texte blanc. C'est la famille de `--pg-accent-soft`, dans
  l'autre sens — trop haut là-bas, trop bas ici.
- ⚠️⚠️ **Un BACKTICK dans un commentaire HTML écrit à l'intérieur d'un littéral
  de gabarit ferme la chaîne** : `gestion_rh.js` ne se compilait plus. Un
  commentaire qui cite un nom de fichier n'a rien à faire entre deux backticks
  de gabarit — il vit au-dessus de la fonction, en commentaire JS.
- ⚠️⚠️ **Un défilement « doux » ne progresse pas dans le volet de mise au
  point** — même famille que les transitions CSS figées en cours de route.
  Mesuré : l'avertissement restait 102 px sous le bord. `behavior: 'instant'`,
  et le signal reste la boîte rouge qui paraît, pas le mouvement.
  ⚠️ Et `offsetTop` se mesure depuis l'`offsetParent`, pas depuis le conteneur
  qui DÉFILE : on calcule par les rectangles.
- ⚠️ **Une hauteur fixe sur une cellule de tableau déborde en SILENCE** : à
  46 px, les trois étages de la colonne Total en demandaient 50, et les lignes
  paraissaient décalées d'une demi-hauteur. `min-height` sur le bloc, et une
  hauteur de 1 px sur la CELLULE pour rendre `height: 100%` résoluble.
- ⚠️ **Le cliquet s'est attrapé sur son propre commentaire** — douzième
  occurrence de cette famille : le contrôle qui interdit `type="month"` dans le
  gabarit lisait l'explication qui cite cette forme. Les commentaires se
  retirent AVANT la recherche, en HTML comme en CSS et en JS. ⚠️ Et une
  TREIZIÈME dans la foulée : celui qui vérifie que la liste des personnes
  prévient par un événement cherchait le NOM de l'événement, qui figure aussi
  dans le commentaire expliquant la couture — il est resté VERT sur le défaut
  remis. On vise l'appel, jamais le nom.
- ⚠️⚠️ **Une règle non-média écrase un repli déclaré PLUS HAUT.** La carte
  d'une personne passe à six colonnes dans la section neuve, posée à la fin de
  la feuille — et le `@media (max-width: 900px)` qui la remet sur deux colonnes
  est déclaré neuf cents lignes avant : à spécificité égale, c'est la dernière
  déclaration qui gagne, donc la carte débordait aussi en étroit. Le repli est
  REDIT après. Même famille que « remplacer une passe de style emporte aussi sa
  mise en page », déjà payée deux fois sur la page Carte.

Tests : `tests/test_171_charge_travail.py` (44 cas, NEUF) ; **28 défauts remis
un par un**. Banc : `tools/devrun_charge.py` (port 8142) sème tous les états en
même temps — un rôle mesuré dans DEUX cartos, un qui dépasse le temps plein,
un mesuré le mois dernier seulement, un jamais mesuré, une personne au-delà du
plafond, une dont le seul rôle n'est pas mesuré, et deux périodes.
Éprouvé à l'écran de 1 200 à 1 600 px dans les deux langues : parcours complet
(damier, pop-up de détail, avertissement, « Ajouter quand même » relu EN BASE —
823 h / 63 % → 3 913 h / 297 %), **zéro fuite française sur l'écran anglais**
(401 textes relevés, attributs compris), zéro débordement horizontal, zéro
erreur console.

**Reste, et c'est une décision** : « qui performe » se lit entre CARTOS, pas
entre personnes — `user_roles` est global et ne dit pas dans quelle carto
quelqu'un tient son rôle. Le damier compare donc les cartos et NOMME les
titulaires ; attribuer une carto à un titulaire demanderait une colonne de plus
sur `user_roles`.

#### ⚠️⚠️ UNE BOUCLE A MIS TOUTE L'APPLICATION À TERRE — `for _t in (…)` (2026-11-28)

« J'ai un internal server error lorsque je vais sur l'app. » Mesuré :
`/login` **500** et `/parametres/` **500** sur staging, pendant que
`/testpanel/` et `/health` rendaient 200 — et que l'officielle comme le pilote
rendaient `/login` 200. Le défaut était donc dans le code de staging, livré la
nuit même avec la charge de travail.

**La cause, en une ligne.** `create_app` relie
`from Code.translations import t as _t`, et son processeur de contexte rend
`{'t': _t, …}`. **`_t` est donc une CELLULE de `create_app`**, partagée avec la
fonction imbriquée — pas une variable locale ordinaire. La boucle de migration
que j'avais ajoutée 480 lignes plus bas s'appelait `for _t in ("time_project",
…)` : elle a **réécrit cette cellule**. À la fin de `create_app`, `t` valait la
chaîne « time_weakness », et `{{ t('login.heading') }}` rendait
**`TypeError: 'str' object is not callable`** — sur CHAQUE page, connexion
comprise, donc l'application entière.

⚠️⚠️ **Et aucune des 5 319 lignes de la suite ne pouvait le voir.** Tout le
bloc de migration vit **APRÈS** `if test_config is not None: … return app`
(`Code/app.py`, ~400 lignes plus bas) : la suite, le conftest et tout banc qui
passe `test_config` **retournent avant**. C'est la même zone aveugle que les
deux 500 du 25/11 (la sonde de `get_calendar_params`, la DDL en SQLite pur) —
troisième défaut qui s'y loge. Mon propre contrôle local passait
`test_config` : il rendait 200 et ne prouvait rien.

**Le cliquet lit du BYTECODE**, pas la source — `inspect.getsource` échoue dans
l'arbre d'image, et un contrôle qui rougit toujours n'est plus lu (septième
occurrence de ce piège). L'invariant, vérifié sur le code objet :
**un nom qu'une fonction imbriquée FERME est relié exactement UNE fois par
`create_app`**. Mesuré : 18 fonctions imbriquées, 8 noms fermés, et `_t` était
le seul relié deux fois — l'invariant est donc propre, et il tombe sur le
défaut remis. Un troisième cas garde la RAISON de lire du bytecode : si le
retour anticipé disparaissait, le bloc deviendrait joignable et un contrôle
comportemental serait alors préférable.

⚠️ **Ce que la mesure a écarté en chemin**, pour ne pas le rechercher : ce
n'était ni une transaction PostgreSQL avortée (le suspect naturel, et la
famille du 25/11), ni une colonne `periode` manquante (les quatre ALTER
passent : vérifié, `periode=True` sur les quatre tables), ni le déploiement
(le workflow est vert), ni l'instance (les trois révisions répondent).
Balayage complet après correctif sur un **PostgreSQL 16 vierge** monté par le
démarrage NORMAL : **103 routes GET sans paramètre, 0 en erreur**.

Tests : `tests/test_165_base_neuve.py::TestLesCELLULESDeCreateAppNeSeReECRIVENTPas`
(3 cas ; **2 vérifiés rouges** en remettant la boucle fautive).

#### OÙ une personne tient son rôle — et « qui performe » (2026-11-28)

« Je rattache un titulaire à sa carto, pour comparer les personnes d'un même
rôle ? Si cela améliore le tout oui. » Cela l'améliore, et c'est mesurable :
`Qualité` pèse 3 090 h réparties sur deux cartos, et **ses deux titulaires
portaient tous les deux 3 090 h**. Le damier comparait des CARTOS ; deux
personnes du même rôle, jamais. Or c'est la question posée au départ — « pour
un même rôle, la charge de travail de différents champions afin d'analyser
qui performe ».

`UserRole.entity_id` (migration à chaud) dit OÙ la personne tient ce rôle.
Mesuré après, au banc : **Hubert 1 939 h (FluidClip), Madhuri 1 152 h
(END_DT)** — la ligne « Qualité » du damier porte les deux, chacun dans sa
colonne.

⚠️ **NULL n'est pas « la carto 0 » : c'est « pas rattaché »**, et cela garde
EXACTEMENT le comportement d'avant (toutes les cartos sommées). C'est ce qui
rend la colonne sûre sur une instance en service — **aucune reprise à jouer**,
aucun marqueur en base, et aucun chiffre déjà affiché ne bouge tant que
personne n'a situé qui que ce soit.

⚠️ **La clé primaire reste (user_id, role_id)** : une personne ne tient donc
ce rôle QU'À UN endroit. Ce n'est pas un oubli — c'est ce qui fait de l'attache
une réponse unique à « où cette personne fait-elle ce rôle ».

#### La règle, écrite à UN seul endroit

`charge_travail.poids_du_role(poids_role, poids_carto, role_id, entite_id)` —
le tableau, la pop-up de détail et l'avertissement du plafond la lisent tous
là. Deux calculs d'un même poids finissent par afficher deux chiffres.

- **pas rattachée** → la somme de toutes les cartos (le comportement d'avant) ;
- **rattachée** → le poids du rôle DANS SA CARTO, et lui seul ;
- ⚠️ **rattachée à une carto où le rôle n'est pas mesuré** → **NUL, pas zéro**,
  même si le rôle est mesuré ailleurs. Elle travaille là où personne n'a pesé
  ce rôle : « on ne sait pas » et « rien à faire » ne demandent pas le même
  geste, et tout ce module tient cette distinction.

#### Qui écrit l'attache, et qui ne l'écrit PAS

⚠️⚠️ **Cocher un rôle REMPLIT une attache vide, il n'en DÉPLACE jamais une
posée.** `majLien` (page RH) et la page Partage postent déjà sur
`/cartography/api/access/<e>/roles/<r>/holders` — **la carto est donc déjà
dans l'appel**, et l'attache se remplit toute seule, sans écran de plus. Mais
ce clic dit « cette personne tient ce rôle » ; l'attache est un SECOND fait,
plus lourd, puisqu'il décide de sa charge mesurée. Un second fait ne s'écrit
pas par un geste qui visait le premier — surtout depuis la page RH, où la
carto du bandeau peut n'être que celle qu'on regardait.

Le déplacement se fait donc explicitement : **`POST /gestion_rh/role_carto`**,
un sélecteur sous chaque rôle dans la pop-up de détail — là où on LIT la
charge, donc là où se règle ce qui la décide. `entity_id: null` détache (sans
ce retour, une attache posée par mégarde ne s'enlèverait plus).
⚠️ Elle refuse une carto inconnue (l'identifiant vient du navigateur) et un
rôle que la personne ne tient pas (aucune ligne pour porter l'attache).

⚠️ `_appliquer_roles` (fiche de compte) travaille déjà PAR PAIRE et ne touche
à rien d'autre : une attache y survit. Les deux routes `/assign_roles` et
`/collaborateur_roles`, elles, remplacent TOUS les rôles d'une personne et
effaceraient les attaches — elles ne sont appelées par **aucun gabarit ni
aucun JS** (vérifié), et sont laissées telles quelles.

⚠️ **`delete_entity` DÉTACHE** (`UserRole.entity_id → NULL`), à côté du
détachement de `User.entity_id` qui existait déjà : c'est une clé étrangère
vers `entities`, donc PostgreSQL refuserait la suppression — et SQLite non,
le défaut ne se verrait qu'en production. On détache, on ne retire pas le
rôle : la personne le tient toujours, on ne sait simplement plus où.

#### L'écran

Les titulaires sont posés **DANS LEUR CASE**, et le placement vient du serveur
(`titulaires_carto`), pas d'un second calcul de l'attache. La dernière colonne
ne porte plus que les **non situés**, et elle **disparaît** quand tout le monde
est placé — le damier devient alors une pure comparaison. Sur une instance qui
vient de prendre ce code, où aucune attache n'existe, elle est intacte : rien
ne bouge tant qu'on n'a rien situé.

⚠️⚠️ **Et une personne ne doit JAMAIS disparaître de la ligne de son rôle.**
Premier jet : les titulaires étaient attachés aux MESURES. Madhuri, située sur
END_DT où « Méthodes » n'est pas mesuré, ne tombait alors dans aucune case —
ni dans « non situés », puisqu'elle EST située. Vu à l'écran, pas déduit. Elle
est désormais posée dans la case VIDE de sa carto, qui dit la seule chose
vraie : quelqu'un travaille là, et personne n'y a pesé ce rôle.
⚠️ Les clés de `titulaires_carto` sont du **TEXTE** : c'est ce que le
navigateur compare (`String(entite_id)`), et une clé entière ne tomberait sur
aucune colonne, en silence.

⚠️ **Le verdict du plafond prend la carto cochée.** Sans elle, il annoncerait
la somme de toutes les cartos du rôle alors que la personne n'en portera
qu'une : un plafond franchi sur le papier et pas en vrai. Et une carto où le
rôle n'est pas mesuré ne prévient de **RIEN** — on ne prévient pas d'un
dépassement qu'on ne sait pas calculer.

⚠️ **La pastille de case est la MÊME que dans la colonne.** Essayée à 20 px,
elle rendait ses initiales à **8,4 px RÉELS** (`body.pg` porte `zoom: .8`, et
le plancher de l'échelle est 11) ; celle de la colonne est déjà à 10 —
descendre encore ferait deux tailles de marqueur pour un seul sens. Et la case
passe à trois lignes, donc son plancher monte : un `min-height` trop court
déborde EN SILENCE, c'est ce qui avait décalé les lignes d'une demi-hauteur
quand la colonne Total est passée à trois étages.

⚠️ Relevé au passage sur l'écran anglais : `rh.ch_pct_full` écrivait
« 188 % of a full-time » — l'espace avant le % est une convention FRANÇAISE, à
côté des « 162% » que `pct()` écrit déjà sans espace. Deux formes du même signe
sur un seul écran.

#### Deux pièges, tous deux déjà connus

- ⚠️ **Un cliquet qui cherche une chaîne doit viser un fragment qui ne soit
  pas une SOUS-CHAÎNE d'un autre.** `"libres ?"` est contenu dans
  `"!libres ?"` : retirer la garde de l'en-tête de colonne laissait le cas au
  VERT. Il vise maintenant les deux fragments exacts.
- ⚠️ **Lire `.id` sur une instance supprimée lève** (SQLAlchemy tente de la
  rafraîchir) : le décor d'un test qui supprime une carto doit la retirer de
  son inventaire, et capturer l'identifiant AVANT.

Tests : `tests/test_171_charge_travail.py` passe de 44 à **72 cas** ;
**19 défauts remis un par un, 19 cliquets tombés** — dont un qui ne gardait
rien au premier essai. Banc : `tools/devrun_charge.py` sème les CINQ états en
même temps (deux titulaires du même rôle sur deux cartos, un rôle tenu sans
attache, une attache sur une carto sans mesure, un rôle mesuré le mois d'avant,
un jamais mesuré). Éprouvé à l'écran dans les deux langues : parcours complet
(déplacement d'une attache **relu en base** — Hubert 2 131 h / 162 % → 1 344 h
/ 102 %, et HG qui passe de la colonne FluidClip à END_DT, à côté de MP), zéro
fuite française sur l'écran anglais (396 textes relevés, attributs compris),
zéro débordement horizontal.

#### LE MOIS SE CHOISIT DANS UN MINI CALENDRIER, et il vit DANS le formulaire (2026-11-28)

« L'intégration dégueu que tu m'as faite dans le formulaire c'est non, en plus
le truc se trouve en haut dans un nav, isolé du formulaire. »

⚠️⚠️ **La note d'hier défendait un argument JUSTE et en tirait une conséquence
FAUSSE.** Elle disait : « le mois vit dans la BANDE : c'est une propriété de
l'analyse ENTIÈRE, comme son nom, et la bande est le seul endroit commun aux
quatre types — quatre champs dans quatre formulaires, c'étaient quatre
occasions d'en oublier un. » Les deux prémisses tiennent. Mais la bande est un
**BANDEAU DE TITRE** : un champ posé là se lit comme un réglage d'écran, isolé
de ce qu'on remplit. Et « une seule implémentation » ne demandait pas la
bande — seulement un endroit écrit UNE fois. La tête de la colonne de saisie
en est un, et il est DANS le formulaire.

**Le contrôle, lui, change de nature.** Ni `<input type="month">` (Firefox ne
le rend pas et retombe sur un champ texte où il faut taper « 2026-11 »), ni
deux menus déroulants : **douze mois dans une année qu'on fait défiler**, le
vocabulaire du calendrier des séances de la page Compétences (`cal-mois-h`,
`cal-grille`, `cal-case`, le repère `est-auj`) en miniature. Un mois se
CHOISIT dans une année ; il ne se compose pas en deux temps.

- ⚠️ **Le panneau est posé en `absolute` DANS son champ**, jamais sur le body
  en `fixed` : `body.pg` porte `zoom: .8`, et tout élément posé sur le body
  doit alors convertir ses coordonnées — **septième fois** que ce piège se
  présente. Ici le repère est le champ lui-même, il n'y a rien à convertir.
  Vérifié : aucun ancêtre ne le découpe, 6 px sous son bouton, 0 case hors
  cadre.
- ⚠️ La bascule vers le HAUT quand la place manque est une **CLASSE**, pas un
  pixel calculé (`bottom` au lieu de `top`) — pour la même raison. Et elle se
  mesure APRÈS l'affichage, sinon le panneau n'a pas de hauteur.
- ⚠️ `[hidden]` est une règle du NAVIGATEUR : `.tm-mois-p` pose un `display`,
  donc `.tm-mois-p[hidden]` est déclaré à la main. **Neuvième fois.**
- ⚠️ **Un clic DANS le panneau ne le ferme pas**, et la remontée s'arrête au
  panneau plutôt que de tester la cible depuis le document : choisir un mois
  réécrit la grille, donc la cible est DÉTACHÉE quand l'événement remonte et
  `closest()` ne trouverait plus rien. Même piège que le panneau du
  développeur de compétences.
- ⚠️ Le mois COURANT se marque même quand il n'est pas choisi : sans lui, une
  année qu'on fait défiler n'a plus aucun point fixe.
- Les noms de mois viennent d'`Intl`, dans la langue de la PAGE : douze clés
  par langue seraient douze occasions de divergence pour ce qu'une
  bibliothèque standard fait déjà. Trois clés neuves seulement
  (`periode_ce_mois`, `periode_an_prec`, `periode_an_suiv`).

Partis avec : `.tm-per`, `.tm-per-duo`, `#tm-periode-m`, `#tm-periode-a`,
`remplirPeriode`, `PER_AVANT`/`PER_APRES`. Éprouvé au banc dans les deux
langues : ouvrir, changer d'année, choisir, « Ce mois-ci », clic dehors,
Échap, et l'aller-retour complet — mois enregistré **relu en base**
(`2025-08`) puis retrouvé à la réouverture de l'analyse.

#### Des analyses DATÉES pour voir le damier — `tools/db/seed_charge.sql`

« Je manque cruellement d'analyse datée. » C'était exact, et le damier disait
vrai : il n'affichait que trois cases et cent rôles « jamais mesuré ».

⚠️ **Et la cause était dans l'outillage** : `seed_temps.sql` a été écrit AVANT
la colonne `periode` et créait donc des analyses **sans mois**. Une analyse
sans mois ne figure dans AUCUN tableau par période — ni le damier, ni le
sélecteur de la page Temps : elle est invisible, et on cherche longtemps
pourquoi l'écran reste vide. Ses quatre insertions datent désormais ce
qu'elles créent (`mois_courant`), vérifié sur PostgreSQL : 16 lignes, 0 sans
mois.

**Le semis neuf** (trois requêtes, comme ses voisins : inventaire en lecture
seule, bloc atomique, relecture) donne au damier de quoi parler — plusieurs
mois, des poids très inégaux, des titulaires situés, et des rôles laissés sans
mesure.

- ⚠️⚠️ **IL VISE UNE PART DE TEMPS PLEIN, et en DÉDUIT la durée** — l'inverse
  de ce qu'on ferait spontanément. Mesuré sur un premier jet qui posait des
  durées « plausibles » : les parts sortaient entre **0 et 49 %** quand
  l'échelle de couleur du damier va de 25 % à plus de 150 %. Toutes les cases
  tombaient dans les deux premières teintes, et la couleur — qui est TOUTE
  l'information de ce tableau — ne disait plus rien. La raison est
  arithmétique : la RÉCURRENCE écrase tout le reste, avec un facteur **225**
  entre « journalier » et « annuel » que nulle durée raisonnable ne rattrape.
  Une ligne annuelle pèse zéro quoi qu'on y mette. Après correctif, mesuré :
  **8 % → 192 %, les six teintes couvertes**, sur n'importe quelle carto et
  quel que soit son calendrier.
- ⚠️ `trimestriel` et `annuel` sont donc **écartés** : à part égale ils
  demanderaient des durées absurdes (504 h en une fois). Trois récurrences
  suffisent à varier sans mentir.
- ⚠️ **Il REFUSE de rejouer** : un second passage empilerait une analyse par
  (rôle, mois) — le damier n'en retient qu'une, la plus récente, mais la liste
  de la page Temps les montre toutes et on ne sait plus laquelle est la vraie.
  `purger := true` pour recommencer.
- ⚠️ **Il ne DÉPLACE aucune attache** : il ne remplit que les `entity_id`
  vides. Déplacer celle de quelqu'un changerait sa charge mesurée, et c'est
  une décision de la page RH, pas d'un semis.
- ⚠️ Seuls les rôles qui portent une activité de CETTE carto : un rôle est
  commun à l'entreprise, mesuré ailleurs il irait grossir une autre colonne.
- ⚠️ `delay_minutes` et `nb_people` sont NOT NULL et leur défaut vit dans le
  MODÈLE, pas dans le schéma : un INSERT en SQL brut doit les écrire lui-même.

Éprouvé sur un **vrai PostgreSQL 16** (conteneur jetable, schéma monté par le
démarrage NORMAL de l'application) : 36 analyses sur 4 mois, rejeu refusé,
purge qui relance à l'identique, 9 rôles mesurés et 3 laissés, 5 titulaires
situés, et le damier relu mois par mois.

⚠️ **Deux pièges de banc**, tous deux déjà connus : `text()` de SQLAlchemy
prend les `%` du script (modulos, marqueurs de `RAISE NOTICE`) pour des
paramètres liés — l'éditeur SQL de Neon envoie le texte brut, c'est donc le
BANC qu'on aligne, par le curseur du pilote. Et le découpage sur
`-- REQUÊTE n` coupe au MILIEU d'un commentaire : ce qui reste (« — SEMER »
sans ses deux tirets) n'est plus un commentaire pour PostgreSQL, il faut
recoller le préfixe. Même famille que le découpage des sections CSS.

#### ⚠️⚠️ Le semis était INFRANCHISSABLE, et son issue de secours détruisait (2026-11-28)

Rapporté le jour même : « la requête 2 ne passe pas lorsque je mets l'id de la
carto (16) ». Elle répondait

    ERROR: La carto #16 (PAlier test) porte déjà 1 analyse(s) de rôle datée(s).

**UNE seule analyse, écrite à la main, fermait tout le semis** — et la seule
sortie que le message offrait, `purger := true`, l'aurait effacée (la purge
supprimait TOUTE analyse de rôle touchant la carto, datée ou non). On ne
proposait donc que de détruire le travail de quelqu'un pour pouvoir semer.

⚠️ **Le garde-fou protège d'un REJEU, pas de l'existence d'une analyse.** Ce
qu'il lui manquait, c'est de savoir distinguer ce que le semis a créé. Chaque
analyse semée porte désormais un préfixe, `marque`, **déclaré à UN seul
endroit** : l'insertion le pose, le refus et la purge le cherchent. Deux
écritures de ce préfixe finiraient par diverger, et la purge se mettrait alors
à effacer ce qu'elle doit épargner.

- ⚠️ **Les identifiants sont relevés AVANT toute suppression** (`ra_ids`) :
  une fois les lignes parties, plus rien ne rattache l'analyse à sa carto, et
  il faudrait retomber sur « toute analyse sans ligne » — ce que faisait le
  second DELETE, qui **balayait donc la base entière**, y compris les analyses
  orphelines d'une autre carto.
- ⚠️ Le compte rendu dit en toutes lettres ce qu'il a laissé intact, et que
  sur un même rôle et un même mois le damier montre la plus récente — donc
  celle du semis, l'analyse faite à la main restant dans la liste de la page
  Temps.

⚠️⚠️ **Et la requête 3 n'avait JAMAIS tourné : `round(double precision,
integer)` n'existe pas.** `time_role_line.duration_minutes` est un `db.Float`,
donc `sum(...)` rend un `double precision` — et seule la forme à UN argument
de `round` accepte un flottant. La relecture tombait sur
`function round(double precision, integer) does not exist`. Le « éprouvé sur
un vrai PostgreSQL 16 » écrit la veille ne couvrait donc que les requêtes 1
et 2 : **un semis se prouve requête par requête, pas en bloc.** Conversion en
`numeric` avant d'arrondir, et un cliquet relit **les quatre semis** : tout
`round` à deux arguments dont le premier touche une colonne flottante doit
porter la conversion.
⚠️ Il lit les colonnes flottantes dans **`db.metadata`**, jamais dans le
source des modèles : l'arbre d'image n'a pas les `.py` — et il refuse de
passer s'il n'en relève aucune, sinon il verdirait sans rien lire.
⚠️ Et il équilibre les parenthèses au lieu de chercher un motif : une
expression régulière s'arrête à la PREMIÈRE parenthèse fermante, donc elle
tronque `round(sum(x) / 60.0, 1)` à `round(sum(x)` et ne voit jamais le
second argument, celui qui décide.

⚠️ `_sans_commentaires_sql` rejoint ses deux sœurs : les commentaires de ce
semis CITENT les formes qu'ils interdisent (le préfixe, et la phrase qui
explique que `round` à deux arguments refuse un flottant). **Onzième
occurrence** de cette famille.

Éprouvé sur un **vrai PostgreSQL 16**, sur le scénario exact du signalement —
une carto portant une analyse datée faite à la main : le semis passe, elle
survit, le rejeu reste refusé, la purge n'efface que les 16 analyses semées,
et la requête 3 relit.
Tests : `test_171` passe de 83 à **88 cas** ; **six défauts remis un par un,
six cliquets tombés**.

#### ⚠️ Quatre cliquets qui ne gardaient rien, et c'est trois fois la même faute

Vérifiés rouges un par un, quatre sont restés VERTS au premier essai :

- `est-auj` survivait dans le **COMMENTAIRE** qui l'explique — un commentaire
  qui justifie un marqueur le CITE forcément. **Dixième occurrence** de cette
  famille ; d'où `_sans_commentaires_js` dans ce fichier ;
- `data-an` est une **SOUS-CHAÎNE** de `data-analyse`, que le même fichier
  emploie trois fois : retirer les deux flèches laissait le cas vert ;
- `stopPropagation` figure **trois fois** dans la fonction visée : retirer
  celui qui compte ne changeait rien ;
- et une injection qui ne reproduisait pas le défaut que le cas garde.

La règle, maintenant écrite trois fois dans ce fichier : **un cliquet vise
l'EMPLOI exact, dans un texte dont les commentaires sont retirés, et sur un
fragment qui n'est la sous-chaîne de rien d'autre.**

Tests : `tests/test_171_charge_travail.py` passe de 72 à **83 cas** (la classe
qui affirmait le champ dans la bande est RÉÉCRITE, pas supprimée) ; **19
défauts remis un par un, 19 cliquets tombés**.

---

## Notes importantes (suite)

- `main` = ancienne branche de production, figée depuis mai 2026.
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
