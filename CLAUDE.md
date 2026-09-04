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

## Page Comptes — droits et langue

- **Droits** (`Code/routes/gestion_compte.py`) : `User.status` est un texte libre, écrit différemment selon les instances → comparaison sur une forme **normalisée** (minuscules, sans accents, séparateurs unifiés) via `_norm_status()`.
  - `_ADMIN_STATUSES` = admin / administrateur / administrator.
  - `_ACCOUNT_CREATOR_STATUSES` = gestionnaire de compétences (+ variantes, `competency manager`). **Créer** un compte — formulaire ET import Excel — exige admin OU ce statut.
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
- **Valeur canonique** `gestionnaire` (13 car., tient dans la colonne) proposée dans les listes déroulantes création / édition / filtre. Le badge de la liste affiche la **valeur brute** quand elle n'est reconnue par aucune règle, au lieu de la faire passer pour « Utilisateur » : un statut mal orthographié se voit, au lieu de produire des droits inexpliqués.

### Partage d'une entité (tous les statuts, avec consentement)

Une entité n'appartient qu'à son propriétaire (`Entity.get_active` est strict sur `owner_id`) : il n'existe pas d'accès partagé. **Partager = déposer une COPIE** chez chaque destinataire, qui repart ensuite avec la sienne sans toucher à l'originale.

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
workflows. Compte unique `Mael_Girardin` (secret `HUB_PASSWORD`, défaut baké
`testtest`), anti-force-brute, `noindex`.

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
