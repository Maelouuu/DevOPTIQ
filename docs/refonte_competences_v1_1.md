# Plan de refonte — Module Compétences (DevOPTIQ V1.1)

> Source : *CDC_OPTIQ_V1_1 — Évolutions V1.1* (AFDEC / Méthode OPTIQ, 12/07/2026).
> Statut : **PLAN — à valider avant tout développement.** Aucun code n'est écrit à ce stade.
> Principe directeur du CDC : *« La V1.1 n'est pas une refonte de DevOPTIQ. Elle corrige les fondations
> pour que le module Compétences fonctionne avec des activités à plusieurs sorties, plusieurs niveaux et
> plusieurs domaines de technicité. On conserve l'existant, on l'enrichit, on ne casse rien. »*

---

## 1. La chaîne métier cible (le fil rouge de toute la refonte)

```
ACTIVITÉ
  └► produit des DONNÉES DE SORTIE
        └► l'IA qualifie leur nature (RESULT / MEASURE / EVENT / INFORMATION)
              └► les RÉSULTATS (RESULT) portent un STANDARD MINIMAL de performance
                    └► la COMPÉTENCE = tenir régulièrement les résultats au niveau requis
                          └► si un résultat n'est pas tenu → DIAGNOSTIC de la cause
                                ├─ Architecture du travail
                                ├─ Capacité à agir (S / SF / HSC en écart)   ← seul cas → plan individuel
                                └─ Conditions d'exécution
                                      └► PLAN D'ACCOMPAGNEMENT → RÉÉVALUATION du résultat
```

**8 principes non négociables** (à câbler dans l'UI *et* les prompts IA) :
1. L'activité est l'unité de base. Elle produit des données ; toutes ne sont pas des résultats.
2. Une donnée `RESULT` participe **directement** à la démonstration de la maîtrise.
3. La compétence = **capacité démontrée** à tenir l'activité au niveau minimal requis.
4. S/SF/HSC **ne sont pas** la compétence — ils expliquent *pourquoi* un résultat n'est pas tenu.
5. L'évaluation **commence par le résultat** ; le diagnostic S/SF/HSC vient *ensuite*, seulement en cas d'écart.
6. Niveau **requis** = couple Rôle × Activité. Niveau **démontré** = individu.
7. Performance > standard ≠ plus compétent (juste plus performant). Pas d'augmentation auto de niveau.
8. Activité à plusieurs résultats → niveau global = **minimum** des résultats (jamais de moyenne).
9. La grammaire cartographique OPTIQ **ne change pas** (activités, rôles, flux, sens de lecture).

**Convention codes** : `RESULT`, `DAILY`, `WORK_ARCHITECTURE`… sont des **codes techniques internes** (base/code),
**jamais affichés** tels quels. L'UI affiche le libellé FR ou EN. Tout ajout d'UI est **bilingue FR/EN**.

---

## 2. État actuel vs cible — analyse d'écart (grounded)

| Objet existant | Aujourd'hui | Manque pour la V1.1 |
|---|---|---|
| `Data` (`models.py:212`) | id, entity_id, shape_id, name, `type`, description, layer | nature sémantique, standard mini, cadence/fraîcheur, traçabilité qualif. |
| `Activities` (`:162`) | name, description, `is_result`(bool legacy), tasks, competencies… | cadence de l'activité |
| `activity_roles` (`:17`) | (activity_id, role_id, `status`) — `status='Garant'` | niveau requis par le rôle |
| `Competency` (`:277`) | 1 ligne/activité, mais l'app en génère **plusieurs** | 1 compétence **principale** fondée sur les RESULT |
| `Savoir`/`SavoirFaire`/`Softskill`(HSC) (`:381`,`:389`,`:285`) | liés à `activity_id` uniquement | liaison **par résultat**, niveau requis, badges résultat |
| `CompetencyEvaluation` (`:441`) | user, activity, item_id, item_type, `eval_number`(0-3), `note`(str couleur) | `mastery_level`, `evidence`, `evaluated_at`, `evaluator_user_id` |
| `PerformancePersonnalisee` (`:357`) | content, validation_status, historique | renommage UI « Objectifs individuels de performance » |
| `TaskLinkAssignment` (`:612`) | link↔task, direction | réutilisé pour relier tâches → RESULT |
| Générateur de plan (`competences_plan.py`) | entrée = liste globale de S/SF/HSC | entrée = **RESULT en écart** + capacités liées |
| Page Compétences (`competences.py`, `competences_view.html`) | eval par activité, multi-évaluateurs, note couleur | **parcours par résultat** : requis→démontré→écart→diagnostic→plan |

**Objets entièrement nouveaux** : `result_capability_links`, `technical_domains`,
`activity_technical_domains`, `role_activity_domain_requirements`, `user_domain_levels`,
référentiel comportemental HSC (descripteurs par niveau).

---

## 3. Deltas modèle de données (toutes migrations idempotentes `ALTER TABLE … IF NOT EXISTS`)

> Contrainte de non-régression (CDC §8) : **aucune** de ces colonnes ne doit être remise à NULL par la
> synchro cartographie→base ; les nouvelles tables sont **scopées `entity_id`** ; ne pas porter de donnée
> métier critique uniquement sur `Link` (la sauvegarde carto supprime/recrée des Link).

### 3.1 Enrichir `Data` (CDC 1 & 5)
- `semantic_nature` — Enum nullable `RESULT|MEASURE|EVENT|INFORMATION` (NULL = non qualifié).
- `minimum_performance_text` — Text nullable (surtout pour RESULT ; standard « tenu au niveau 2 »).
- `qualification_source` — `AI|MANUAL` nullable ; `qualification_updated_at` — Datetime nullable.
- `update_cadence_code` — code cadence nullable ; `max_age_hours` — Integer nullable.
- ⚠️ **Ne pas** réutiliser `Data.type` ni le type de `Link` (deux questions différentes). **Ne pas** créer `is_competence_result` (le code `RESULT` suffit).

### 3.2 Enrichir `Activities` (CDC 5)
- `cadence_code` — code cadence nullable ; `cadence_details` — Text nullable.

### 3.3 Enrichir `activity_roles` (CDC 3)
- `required_mastery_level` — Integer 0–4 ou NULL. Défaut **2** pour l'association `status='Garant'`, NULL sinon.

### 3.4 Enrichir `CompetencyEvaluation` (CDC 3)
- `mastery_level` (Int 0–4 nullable), `evidence` (Text), `evaluated_at` (Datetime), `evaluator_user_id` (FK User).
- Évaluer un RESULT → `item_type='activity_results'`, `item_id=data_id`. Garder `item_type='activities'` pour lire l'ancien.
- Conserver `note` (compat) ; **les couleurs deviennent calculées** depuis `mastery_level` + écart au requis.

### 3.5 Nouvelle table `result_capability_links` (CDC 2.7)
`id, entity_id(FK), activity_id(FK), data_id(FK→Data RESULT), item_type(SAVOIR|SAVOIR_FAIRE|HSC),
item_id, required_level(Int 1–4 nullable), source(AI|MANUAL), created_at, updated_at`.
→ Un S/SF/HSC peut être relié à **plusieurs** RESULT.

### 3.6 Domaines de technicité (CDC 4) — 4 tables
- `technical_domains` : id, entity_id, name_fr/name_en (+description, active).
- `activity_technical_domains` : activity_id, domain_id.
- `role_activity_domain_requirements` : role_id, activity_id, domain_id, required_level (0–4).
- `user_domain_levels` : user_id, domain_id, demonstrated_level, evidence, evaluated_at, evaluator_user_id.
- ⚠️ Libellé **« Domaine de technicité / Technical domain »** — jamais « expertise domain » (Expertise = niveau 4).

### 3.7 Référentiel comportemental HSC (CDC 7)
Pour chacune des **16 HSC** existantes × 4 niveaux : `descriptor_fr/en`, `observable_behaviors_fr/en`,
`example_situations_fr/en`, `development_focus_fr/en`. (Table `hsc_level_descriptors` ou JSON de référence versionné.)
Libellés de niveau **stabilisés partout** : 1 Aptitude/Basic, 2 Acquisition/Developing, 3 Maîtrise/Proficient,
4 **Expertise**/Expert. **Supprimer « Excellence »** pour le niveau 4.

---

## 4. Deltas IA / prompts

| Prompt | Fichier probable | Changement |
|---|---|---|
| **Qualifier les sorties** (CDC 1.6) | nouveau (ou étend `propose_common`) | entrée = activité+tâches+sorties+flux+destinataires+perfs ; sortie = `{outputs:[{data_id, suggested_nature, confidence, justification, suggested_minimum_performance}]}` |
| **Compétence principale** (CDC 2.2–2.4) | `propose_*` / génération compétence | n'analyse que les `RESULT` ; 1 compétence, sans énumérer S/SF/HSC ni le standard ; `granularity_alert` |
| **S/SF/HSC par résultat** (CDC 2.5) | `propose_savoirs/savoir_faires/softskills` | raisonnement **résultat par résultat** : RESULT → tâches (via `TaskLinkAssignment`) → SF → S → HSC ; dédup en gardant les liens |
| **Cohérence des rythmes** (CDC 5.5) | nouveau (lecture seule) | `{warnings:[{source/target_activity_id, data_id, severity, finding, optiq_question}]}` — jamais de correction auto |
| **Auto-positionnement HSC** (CDC 7.4) | `translate_softskills` voisin | 4–6 situations comportementales → `{probable_level, confidence, evidence_summary, missing_evidence_for_next_level, development_focus}` |

**Règles IA transverses (CDC §8)** : indispo IA → renvoyer « à qualifier » / proposition vide (jamais de donnée
générique faussement qualifiée) ; l'IA ne modifie **jamais** automatiquement la cartographie, un niveau validé,
une exigence de rôle ou un diagnostic validé.

---

## 5. Refonte de la page Compétences (le cœur — CDC 6)

Recentrer sur : **« La personne tient-elle les résultats de l'activité au niveau requis par son rôle ? »**
Parcours : `COLLABORATEUR → RÔLE → ACTIVITÉS DU RÔLE → RÉSULTATS → ÉCART → DIAGNOSTIC → ACCOMPAGNEMENT → RÉÉVALUATION`.

### 5.1 Écran 1 — Tableau principal (par collaborateur × rôle)
Colonnes : Activité · **Niveau requis** (activity_roles) · **Niveau démontré** (min des RESULT validés) ·
**Écart** · **Résultats** (n au requis / total) · **Technicité** (alerte si domaine en écart) ·
Dernière évaluation (dernière validation Garant/Manager) · Action (Évaluer / Analyser l'écart / Voir le plan).
Couleurs = **calculées** (mastery_level vs required_level). `NULL` (non évalué) ≠ `0` (non démontré).

### 5.2 Écran 2 — Évaluation d'une activité (par résultat)
- Compétence principale en tête.
- Un bloc **par RESULT** : son standard minimal, l'auto-évaluation + dernière éval validée, saisie/révision du
  niveau (0–4) + preuve/commentaire.
- Niveau global d'activité **calculé = minimum** des RESULT ; comparé au niveau requis du rôle.

### 5.3 Écran 3 — Diagnostic d'un écart (RESULT < requis)
- États : `<2` Autonomie non démontrée · `≥2 mais < requis` Écart de développement · `≥ requis` Niveau tenu.
- **3 familles de causes** (l'IA propose, le Garant/Manager valide) :
  `WORK_ARCHITECTURE` (Architecture du travail) · `ABILITY_TO_ACT` (Capacité à agir) · `EXECUTION_CONDITIONS` (Conditions d'exécution).
- Si **Capacité à agir** validée → afficher **uniquement** les S/SF/HSC liés à ce RESULT (`result_capability_links`),
  niveau démontré vs `required_level`. Les items non liés ne polluent pas le diagnostic.

### 5.4 Écran 4 — Plan d'accompagnement (générateur adapté)
- Entrée = RESULT en écart + capacités validées comme cause (plus collaborateur/rôle/activité/tâches/domaine/preuves).
- Champs plan : `development_objective, target_level, work_situations, support_mode, steps, evidence_expected,
  review_date, reviewer, status(TO_START|IN_PROGRESS|TO_ASSESS|VALIDATED)`.
- **Règle impérative** : si l'écart relève d'**Architecture** ou **Conditions d'exécution** → **pas** de plan de
  formation auto ; afficher « L'écart ne relève pas prioritairement d'un développement individuel. »
- Boucle : preuves réunies → `TO_ASSESS` → l'évaluation renvoie vers le **RESULT initial**.

### 5.5 Enrichissements de fiches (pas de nouveaux écrans complets)
- **Fiche activité** : action « Analyser les sorties » (CDC 1) + panneau de validation unique des natures ;
  onglet **Domaines de technicité** (tags, ajout/création validée) ; badge cadence.
- **Écrans S/SF/HSC existants** : conserver ; ajouter un **badge « R1 — … »** par item relié ; items non reliés →
  « Liaison résultat à définir ».
- **HSC** : auto-positionnement (4–6 situations), niveau probable IA distinct du niveau validé (CDC 7).
- Renommer **« Performance personnalisée » → « Objectifs individuels de performance »** (UI seulement ; n'altère jamais `mastery_level`).

---

## 6. Ordre de développement (imposé par le CDC §1, dépendances respectées)

| Phase | Périmètre | Prérequis | Livrable clé |
|---|---|---|---|
| **P1** — CDC 1 *(bloquant)* | `Data.semantic_nature`+champs, prompt « Analyser les sorties », panneau de validation unique, standard mini | — | Sorties qualifiées RESULT/MEASURE/EVENT/INFO en 1 validation |
| **P2** — CDC 2 *(bloquant)* | 1 compétence principale, table `result_capability_links`, prompts compétence + S/SF/HSC par résultat, badges | P1 | Compétence fondée sur RESULT + capacités liées par résultat |
| **P3** — CDC 3 *(bloquant)* | `required_mastery_level`, échelle 0–4, éval par RESULT (`CompetencyEvaluation` +4 champs), niveau global = min | P1 | Requis (rôle) vs démontré (individu), sans moyenne |
| **P4** — CDC 4 *(haute)* | 4 tables domaines, onglet fiche activité, requis rôle + démontré individu | P3 | Une activité, plusieurs domaines, niveaux distincts |
| **P5** — CDC 5 *(haute)* | cadences activité+data, badges carto (option Afficher les cadences), analyse « Cohérence des rythmes » | — | Points de vigilance rythme (lecture seule) |
| **P6** — CDC 6 *(bloquant)* | **la refonte de la page Compétences** (§5), diagnostic 3 familles, plan adapté, boucle réévaluation | P1→P4 | Parcours complet requis→écart→diagnostic→plan→réévaluation |
| **P7** — CDC 7 *(complément)* | référentiel comportemental 16 HSC × 4, auto-positionnement, validation évaluateur | P2, P6 | Positionnement HSC par comportements observables |

*Note : P5 est indépendant et peut être mené en parallèle. P6 consomme P1–P4. P7 vient après P6.*

---

## 7. Non-régression & migration (CDC §8, transverse à toutes les phases)

- Ne **pas** supprimer de routes existantes ; les nouvelles complètent l'existant.
- `CompetencyEvaluation.note` (couleurs) reste **lisible** ; anciennes compétences / S/SF/HSC non reliés restent
  visibles avec « Liaison résultat à définir ».
- Synchro carto→base : **ne jamais** réécrire `semantic_nature`, `minimum_performance_text`, cadences, champs enrichis à NULL.
- Nouvelles tables scopées `entity_id` (multi-entités).
- Migrations idempotentes au démarrage (pattern existant `ensure_*_schema` déjà utilisé dans `gestion_rh.py`).
- Hors périmètre V1.1 (à ne **pas** développer) : Open Badges, passeport, moteur de mobilité, référentiel skills mondial,
  dashboard Learning Organisation complet — mais concevoir les objets pour servir de fondation à ces évolutions.

---

## 8. Traçabilité des tests d'acceptation (CDC §9 — à couvrir dans le panel `/testpanel/`)

Formation → RESULT/MEASURE/EVENT en 1 validation · 2 RESULT niveaux 3&1 → activité=1 (pas de moyenne) ·
Junior 2 / Senior 3 sur la même activité (une seule Activity) · Start up Plastic&Metal (1 activité, 2 domaines,
niveaux distincts) · RESULT défaillant → seules ses capacités liées au diagnostic · cause outil/méthode → pas de
plan formation auto · source mensuelle → aval quotidien = point de vigilance · perf individuelle > standard → pas
de hausse auto de niveau · HSC Planif requis 3 / estimé 2 → comportement manquant affiché · ancienne éval couleur
toujours visible · UI EN → aucun code technique affiché.

---

## 9. Décisions à trancher avant de démarrer (questions ouvertes)

1. **Périmètre de la première itération** : livrer P1→P3 + P6 d'abord (le strict « bloquant » qui rend la page
   utilisable), en repoussant P4/P5/P7 ? ou suivre l'ordre complet CDC ?
2. **HSC = `Softskill`** (habilete/niveau/justification). Confirmer que `Aptitude` reste **hors** du triptyque S/SF/HSC
   (le CDC ne parle que de Savoir/SavoirFaire/HSC).
3. **Référentiel comportemental HSC** : table SQL `hsc_level_descriptors` vs fichier JSON versionné (comme
   `tests/patches.json`) — quelle option préfères-tu ?
4. **Modèle IA** : les prompts existants sont sur GPT-4o-mini. On garde ? (le CDC ne l'impose pas).
5. **Emplacement UI** : refondre `competences_view.html` en place, ou nouvelles vues à côté avec bascule ?
