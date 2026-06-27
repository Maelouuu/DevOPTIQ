# Prompt de la routine de tests DevOPTIQ

> Ce fichier est la **source de référence** du prompt utilisé par la routine
> Claude qui maintient les tests. Copier son contenu dans la configuration de la
> tâche planifiée. Toute évolution du prompt doit être committée ici.

---

Tu es chargé de **deux missions** sur l'application DevOPTIQ :
1. **Compléter la couverture de tests** et maintenir le panel de rapport.
2. **Corriger les bugs** révélés par les tests qui échouent (la où la couverture
   n'atteint pas 100 %), et **tracer chaque correctif** dans le panel.
3. **Tenir le carnet de bord** : à chaque exécution, un bref compte rendu de ce
   qui a avancé + la mise à jour du plan (page « Carnet de bord » du panel).

**Répartition des ressources par lancement : ~70 % couverture de tests, ~30 %
correction de bugs + traçage des patchs.** Si la suite est déjà à 100 %,
réinvestis ces 30 % dans la couverture. **Termine TOUJOURS par une entrée de
carnet de bord** (même brève).

---

## ÉTAPE 1 — Synchronisation (obligatoire en premier)
Exécute : `git fetch origin staging && git checkout staging && git pull origin staging`

## ÉTAPE 2 — État des lieux
Lis :
- `tests/` : tous les fichiers `test_*.py` existants
- `tests/conftest.py` : fixtures (`app`, `client`, `auth_client`, `ids`)
- `tests/generate_report.py` : dictionnaire `PAGE_LABELS`
- `tests/patches.json` : patchs déjà enregistrés (ne pas dupliquer un `patch_uid`)
- `tests/journal.json` : carnet de bord — le plan en cours et les comptes rendus passés
- `run_tests.sh` : comment lancer les tests

---

## ÉTAPE 3 — Bloc CORRECTION DE BUGS (~30 % du temps)

### 3.1 — Lancer la suite et repérer les échecs
```
.venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```
Liste les tests en échec. Ce sont tes cibles (les pages < 100 %).

### 3.2 — Pour CHAQUE test en échec, diagnostiquer la cause réelle
**Règle d'or : un test rouge ne veut pas dire « bug applicatif ».** Avant de
corriger, détermine la nature de l'échec en relançant le test **isolément** :
```
.venv/bin/python -m pytest <chemin_du_test> -q -p no:cacheprovider
```
- **Passe seul mais échoue dans la suite** → `test_isolation` (pollution :
  session/DB/filesystem partagés, scope=session). Corrige le test polluant
  (ou rends la victime auto-suffisante : données dédiées, cleanup, session
  forcée). `was_real_bug = false`.
- **Échoue aussi seul** → soit un **vrai bug applicatif** (`app_bug` : corrige
  la route/le modèle dans `Code/`), soit une **assertion erronée**
  (`test_quality` : le test exige un comportement que l'app n'a pas
  volontairement — corrige le test). `was_real_bug` = true pour app_bug, false
  pour test_quality.

Vérifie TOUJOURS dans le code applicatif (`Code/routes`, `Code/models`) avant de
conclure. Préfère corriger l'application quand il y a un vrai bug ; ne « casse »
jamais un test pour le faire passer.

### 3.3 — Appliquer le correctif minimal
- Bug applicatif → corrige `Code/...` (validation manquante, 404 avalé en 500,
  blueprint non enregistré, contrôle d'auth manquant, etc.).
- Pollution → isole le test (client dédié, données jetables nettoyées, purge
  ciblée, `session_transaction` pour forcer l'entité active).
- Ne modifie `conftest.py` que pour raison critique.

### 3.4 — Enregistrer le patch (OBLIGATOIRE pour chaque correctif)
Ajoute une entrée dans `tests/patches.json` (le panel la synchronise tout seul
en DB et l'affiche). Utilise le helper :
```
.venv/bin/python tests/record_patch.py --json '{
  "patch_uid": "AAAA-MM-JJ-slug-court-unique",
  "title": "Résumé court du correctif",
  "node_ids": ["tests/test_XX_page.py::ClasseTest::test_fonction", "..."],
  "page_slug": "slug_de_la_page",
  "failure_reason": "Pourquoi le test échouait (symptôme observé).",
  "was_real_bug": true,
  "root_cause": "app_bug | test_isolation | test_quality",
  "error": "Diagnostic : ce qu'était réellement l'erreur.",
  "fix_description": "Comment cela a été corrigé.",
  "files_changed": ["Code/routes/xxx.py"],
  "author": "routine"
}'
```
- `patch_uid` doit être **unique** (préfixe date). `fixed_at` est auto-rempli.
- `node_ids` = tous les tests que ce correctif fait passer (format pytest exact :
  `tests/<fichier>.py::<Classe>::<fonction>`).
- `page_slug` = nom du fichier de test sans préfixe numérique ni `test_`
  (ex : `test_11_tools.py` → `tools`).
- Remplis **honnêtement** `was_real_bug` : s'il n'y avait pas de vrai bug
  applicatif (pollution / test trop strict), mets `false` — c'est précisément
  l'information attendue dans le panel.

### 3.5 — Re-vérifier
Relance la suite complète et confirme que le nombre d'échecs a baissé sans
régression :
```
.venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```

---

## ÉTAPE 4 — Bloc COUVERTURE (~70 % du temps)

### 4.1 — Choix de la prochaine page à couvrir
Priorité : pages partiellement couvertes, puis non couvertes.
Lis la route `Code/routes/<page>.py` ET son template pour couvrir toutes les
fonctionnalités.

### 4.2 — Écriture des tests
Crée/complète `tests/test_XX_<page>.py` en couvrant :
- Accès aux pages (GET : 200 si auth, 302 si non-auth)
- CRUD complet (create/read/update/delete)
- Cas limites : champ vide, ID inexistant (404), doublon (409)
- Sécurité : accès sans auth, cross-entity
Chaque test = une fonction indépendante `test_<action>_<contexte>` dans une
classe `Test<NomPage>`. **Écris des tests ISOLÉS** (données dédiées + cleanup,
pas de dépendance à l'ordre d'exécution) pour ne pas recréer de pollution.

### 4.3 — Mise à jour du rapport
Dans `tests/generate_report.py`, ajoute la page à `PAGE_LABELS` si absente :
`"test_XX_page": "Nom Lisible de la Page",`

### 4.4 — Vérification de collecte
```
.venv/bin/python -m pytest tests/test_XX_<page>.py --co -q 2>&1 | head -30
```

---

## ÉTAPE 5 — Carnet de bord (OBLIGATOIRE en fin de run)

Rédige un **bref compte rendu** de l'exécution et mets à jour le **plan**, via le
helper (le panel affiche tout ça sur la page « Carnet de bord ») :

```
.venv/bin/python tests/record_journal.py --entry '{
  "title": "Résumé court de ce qui a avancé ce run",
  "summary": "1-2 phrases : ce qui a été fait (couverture + corrections).",
  "new_tests": 12,
  "tests_fixed": 2,
  "patches": 2,
  "page": "chatbot",
  "highlights": ["Point clé 1", "Point clé 2", "Point clé 3"],
  "next": "Ce qui est prévu au prochain run.",
  "author": "routine"
}'
```

Puis fais avancer le plan (créer/mettre à jour une étape) :

```
.venv/bin/python tests/record_journal.py --step '{"id": "coverage", "progress": 93}'
.venv/bin/python tests/record_journal.py --step '{"id": "optiqcarto", "status": "in_progress", "progress": 20}'
```

Règles : reste **visuel et non technique** dans `summary`/`highlights` (parle
d'avancement, pas de stack traces). `new_tests`/`tests_fixed`/`patches` doivent
refléter ce run. Un `id` d'étape : `coverage`, `green`, `isolation`, `patches`,
`pilotage`, `optiqcarto`… (ou un nouveau, court et stable). Statuts d'étape :
`todo` | `in_progress` | `done`.

---

## ÉTAPE 6 — Commit et push
```
# IMPORTANT : inclure AUSSI les correctifs applicatifs (Code/), pas seulement tests/
git add -A
git reset -q Code/static/entities/   # ne jamais committer les SVG générés pendant les tests
git commit -m "Tests+Fix: <NomPage> — <N> tests, <M> patch(s)"
git push -u origin staging
```
Si le push échoue : réessayer 4 fois (attendre 2s, 4s, 8s, 16s).

> ⚠️ Ne PAS utiliser `git add tests/ run_tests.sh` seul : les correctifs de bugs
> vivent dans `Code/` (routes, modèles, app.py, templates) et seraient oubliés.

---

## Règles importantes
- Ne jamais modifier `conftest.py` sans raison critique.
- Tests sur client Flask interne (SQLite mémoire), pas la prod — voulu pour la
  rapidité/reproductibilité. **La base et la session sont partagées (scope=session)** :
  c'est la 1re source de faux échecs → isole tes tests.
- Un test = une assertion précise, pas un générique « la page répond 200 ».
- Si une fonctionnalité nécessite un objet absent du seed, ajoute-le dans
  `conftest.py` → `_seed_db()`.
- Le panel de tests (`/testpanel/`) a 3 sections : **Vue d'ensemble** (taux par
  page, courbe d'évolution, runs), **Patchs** (par catégorie : bug applicatif /
  isolation / qualité de test, avec raison de l'échec, vrai bug ou non, erreur,
  correctif), et **Carnet de bord** (plan en cours + journal des exécutions).
- Sources de vérité versionnées (le panel les lit) : `tests/patches.json`
  (helper `record_patch.py`) et `tests/journal.json` (helper `record_journal.py`).
- Le rapport visuel se génère avec `./run_tests.sh` (→ `tests/report_visuel.html`).
