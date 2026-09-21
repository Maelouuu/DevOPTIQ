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

## Fenêtre de bienvenue

`sessionStorage` est PAR ONGLET : « ouvrir dans un nouvel onglet » repartait d'un
stockage vide et réaffichait la fenêtre. On mémorise maintenant dans
`localStorage` la **signature des nouveautés lues** (titres + début des textes) :
la fenêtre ne revient que lorsque le changelog change vraiment. Tous les accès au
stockage sont en try/catch (navigateur qui refuse le stockage).

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

### En cours
- *(rien)*

### À faire (par priorité)
1. **`docs/doc_technique.html` + `docs/guide.html` : le partage de carto a changé de
   modèle** (carto commune, accès par rôle, propositions de modification, statut
   « champion » à la place de « gestionnaire de compétences », statut « RH » retiré).
   Les deux documents décrivent encore le partage par COPIE seul. À reprendre à la
   prochaine routine de documentation, captures comprises — avec l'examen des
   propositions depuis le bandeau de la page Carte et le tableau global des
   compétences de la page RH (2026-09-21).
2. Éditeur OptiqCarto côté JS (`static/optiqcarto/editor.js`) — seul élément majeur restant
3. **La fenêtre « Importer des données »** (page Carte) remplace l'ancien import global IA :
   le guide et la doc technique décrivent encore l'ancien écran (étapes analyse → revue),
   captures comprises.

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
