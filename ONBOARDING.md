# 👋 Onboarding développeur — DevOPTIQ

Bienvenue dans **DevOPTIQ**, l'application web de gestion des compétences et activités développée par AFDEC (Mael Girardin). Ce document contient **tout** ce dont tu as besoin pour développer sereinement : accès, environnements, installation locale, workflow Git et conventions.

> 🧭 **Tu es le nouveau développeur ?** Va directement à la [section 4 — Installer ton poste](#4--installer-ton-poste-de-dev) une fois que Mael t'a donné les accès de la [section 1](#1--checklist-des-accès-à-faire-par-mael-ladmin).
>
> 🔑 **Tu es Mael (admin) ?** Commence par la [section 1 — Checklist des accès](#1--checklist-des-accès-à-faire-par-mael-ladmin) : ce sont les seules choses qui ne peuvent pas être automatisées (elles demandent les consoles + l'email du collègue).

---

## Sommaire

0. [TL;DR — l'essentiel en 2 minutes](#0--tldr)
1. [Checklist des accès (à faire par Mael)](#1--checklist-des-accès-à-faire-par-mael-ladmin)
2. [Ce qui est déjà préparé](#2--ce-qui-est-déjà-préparé)
3. [Modèle de branches & environnements](#3--modèle-de-branches--environnements)
4. [Installer ton poste de dev](#4--installer-ton-poste-de-dev)
5. [Workflow Git au quotidien](#5--workflow-git-au-quotidien)
6. [Variables d'environnement](#6--variables-denvironnement)
7. [CI/CD & déploiement](#7--cicd--déploiement)
8. [Base de données (Neon)](#8--base-de-données-neon)
9. [Tests](#9--tests)
10. [Architecture & conventions de code](#10--architecture--conventions-de-code)
11. [Sécurité & pièges à éviter](#11--sécurité--pièges-à-éviter)
12. [Ressources](#12--ressources)

---

## 0 — TL;DR

| | |
|---|---|
| **App** | Application web Flask (Python 3.12) de cartographie d'activités & compétences |
| **Stack** | Flask + SQLAlchemy · PostgreSQL (Neon) en prod / SQLite en local · HTML Jinja2 + CSS/JS vanilla · IA OpenAI & Anthropic |
| **Hébergement** | Google Cloud Run (région `europe-west1`), image Docker |
| **CI/CD** | GitHub Actions : `push` sur une branche ⇒ build Docker ⇒ deploy Cloud Run |
| **Ta branche de travail** | `dev-mv` (quotidien) → tu merges vers `staging-mv` pour tester sur une URL en ligne |
| **Démarrer en local** | `pip install -r requirements.txt` puis `python Code/app.py` → http://localhost:8080 (SQLite auto, **aucune DB à installer**) |

**Les 5 accès dont tu as besoin :** GitHub (1) · Neon / base de données (2) · Google Cloud Run (3) · les secrets GitHub Actions (4) · les clés API IA (5). Détaillés juste en dessous.

---

## 1 — Checklist des accès (à faire par Mael, l'admin)

> Ces 5 étapes demandent les consoles web + l'email du collègue : elles ne peuvent pas être faites par l'assistant. Compte ~15 min. Coche au fur et à mesure.
>
> Avant de commencer, récupère 2 infos du collègue :
> - **son identifiant GitHub** (ex. `@johndoe`)
> - **son email Google** (celui de son compte Google, pour Neon + Google Cloud)

### ☐ 1.1 — GitHub : ajouter le collègue en collaborateur

1. Dépôt **`maelouuu/devoptiq`** → onglet **Settings** → **Collaborators** (menu *Access*).
2. **Add people** → saisis son identifiant GitHub → rôle **Write**.
3. Il reçoit une invitation par email, qu'il doit accepter.

> **Write** = il peut créer des branches et pousser, mais pas changer les réglages du dépôt ni supprimer la prod. C'est le bon niveau.

### ☐ 1.2 — Neon : accès à la base + créer la branche `staging-mv`

**a) L'inviter sur le projet Neon**
1. [console.neon.tech](https://console.neon.tech) → ton projet DevOPTIQ.
2. **Settings → Members** (au niveau de l'organisation) → **Invite member** → son email Google → rôle **Member**.

**b) Créer une branche de base dédiée (données isolées)**
1. Projet → onglet **Branches** → **Create branch**.
2. Nom : **`staging-mv`**. Parent : la branche qui contient les données de référence (en général `production`/`main`).
3. Neon crée une **copie instantanée et isolée** : le collègue peut casser/tester sans jamais toucher staging ni la prod. 👍

**c) Récupérer la chaîne de connexion (pour l'étape 1.4)**
1. Sélectionne la branche **`staging-mv`** → **Connection Details**.
2. Active **Pooled connection** (endpoint `...-pooler...`) — important pour un service serverless.
3. Copie l'URL. Format attendu :
   ```
   postgresql://user:password@ep-xxxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
   👉 Tu la colleras dans le secret `STAGING_MV_DATABASE_URL` (étape 1.4).

### ☐ 1.3 — Google Cloud : droits Cloud Run

1. [console.cloud.google.com](https://console.cloud.google.com) → bon projet (celui des services `devoptiq` / `devoptiq-staging`).
2. **IAM & Admin → IAM** → **Grant access** (Accorder l'accès).
3. **New principals** : l'email Google du collègue.
4. Ajoute ces 3 rôles (= « Dev complet », il déploie seul sans toucher la facturation ni l'IAM) :
   - **Cloud Run Developer** (`roles/run.developer`) — gérer/voir les services Cloud Run
   - **Logs Viewer** (`roles/logging.viewer`) — lire les logs (debug)
   - **Artifact Registry Reader** (`roles/artifactregistry.reader`) — lire les images Docker
5. **Save**.

> Le **pipeline GitHub Actions** continue, lui, d'utiliser le compte de service existant (`GCP_SA_EMAIL`) qui a déjà le droit de créer/déployer des services dans le projet — donc **rien à configurer côté GCP pour que `devoptiq-staging-mv` se crée tout seul** au premier déploiement. Les droits ci-dessus servent au collègue pour inspecter/débuguer manuellement la console.

### ☐ 1.4 — GitHub : ajouter les 2 secrets de l'environnement `staging-mv`

Dépôt → **Settings → Secrets and variables → Actions → New repository secret**. Ajoute :

| Secret | Valeur |
|---|---|
| `STAGING_MV_DATABASE_URL` | l'URL Neon *pooled* de la branche `staging-mv` (étape 1.2c) |
| `STAGING_MV_SECRET_KEY` | une clé Flask aléatoire — génère-la avec :<br>`python -c "import secrets; print(secrets.token_hex(32))"` |

Les autres secrets nécessaires (`GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_SA_EMAIL`) **existent déjà** (ils servent à staging et prod) et sont réutilisés tels quels.

> ⚠️ **À savoir** : tant que ces 2 secrets ne sont pas créés, la toute première exécution du workflow *Deploy → Staging MV* échouera (croix rouge). **C'est normal.** Dès que les secrets sont là, relance-la (onglet **Actions** → le run → **Re-run jobs**) ou pousse un commit sur `staging-mv` : elle passera au vert et créera le service `devoptiq-staging-mv`.

### ☐ 1.5 — Transmettre les clés API IA (canal sécurisé)

Pour le dev local, le collègue a besoin des clés suivantes (à mettre dans son `.env`). **Transmets-les via un gestionnaire de mots de passe / message éphémère, jamais par email en clair, jamais dans Git.**

| Clé | Sert à |
|---|---|
| `OPENAI_API_KEY` | chatbot, import IA, propositions de compétences, changelog |
| `ANTHROPIC_API_KEY` | import IA cartographie, génération assistée |
| `ROME_CLIENT_ID` / `ROME_CLIENT_SECRET` | page « Projection métier » (API France Travail) |

> 💡 Idéalement, crée-lui **ses propres clés** (OpenAI/Anthropic ont des clés par utilisateur) plutôt que de partager les tiennes : tu gardes le contrôle des quotas et tu peux révoquer la sienne sans tout casser.

---

## 2 — Ce qui est déjà préparé

Côté dépôt, tout est en place (pas d'action requise) :

- ✅ Branche **`staging-mv`** créée (depuis `staging`) — environnement de preview du collègue.
- ✅ Branche **`dev-mv`** créée — branche de travail quotidien du collègue.
- ✅ Workflow CI **`.github/workflows/deploy-staging-mv.yml`** — déploie `staging-mv` → service Cloud Run `devoptiq-staging-mv`.
- ✅ **`.env.example`** — modèle de toutes les variables d'environnement à copier en `.env`.
- ✅ **`ONBOARDING.md`** — ce document.

Il ne reste donc que la [checklist d'accès de la section 1](#1--checklist-des-accès-à-faire-par-mael-ladmin) (consoles Neon/GCP/GitHub).

---

## 3 — Modèle de branches & environnements

```
        dev-mv ──(merge)──▶ staging-mv ─────▶ [Cloud Run] devoptiq-staging-mv   (preview du collègue)
   (travail quotidien)        (preview)              DB Neon: branche staging-mv

         staging ───────────────────────────▶ [Cloud Run] devoptiq-staging      (staging commun)
                                                    DB Neon: branche staging

      prod-stable ──────────────────────────▶ [Cloud Run] devoptiq              (PRODUCTION)
                                                    DB Neon: branche production
```

| Branche | Rôle | Auto-déploie vers | Base de données | Qui pousse |
|---|---|---|---|---|
| `dev-mv` | Travail quotidien du collègue | *(rien)* | — (local SQLite) | le collègue |
| `staging-mv` | Preview en ligne du collègue | `devoptiq-staging-mv` | Neon `staging-mv` | le collègue (merge depuis `dev-mv`) |
| `staging` | Staging commun / intégration | `devoptiq-staging` | Neon `staging` | l'équipe (après revue) |
| `prod-stable` | **Production** | `devoptiq` | Neon `production` | Mael uniquement, versions validées |

> Le dépôt contient aussi `main` et d'anciennes branches (`dev-visio`, `Iteration2`…). La **branche de référence de travail est `staging`**, pas `main`. `main`/`prod-stable` = stable.

**Règle d'or :** un push sur `staging-mv`, `staging` ou `prod-stable` **déclenche un déploiement réel**. On ne pousse jamais directement sur `staging`/`prod-stable` sans revue.

---

## 4 — Installer ton poste de dev

> Pré-requis : **Python 3.12**, **Git**. (Optionnel : Docker, seulement si tu veux reproduire l'image de prod en local.)

```bash
# 1) Cloner et se placer sur sa branche de travail
git clone https://github.com/maelouuu/devoptiq.git
cd devoptiq
git checkout dev-mv

# 2) Environnement virtuel Python 3.12
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

# 3) Dépendances
pip install -r requirements.txt

# 4) Configuration : copier le modèle et remplir les clés
cp .env.example .env               # Windows : copy .env.example .env
#   → édite .env : colle tes clés OPENAI_API_KEY / ANTHROPIC_API_KEY / ROME_*
#   → laisse DATABASE_URL VIDE pour démarrer sur SQLite (zéro setup DB)

# 5) Lancer l'app
python Code/app.py
#   → http://localhost:8080
```

Au premier lancement **sans `DATABASE_URL`**, l'app crée automatiquement une base **SQLite** locale (`Code/instance/optiq.db`) avec le schéma complet et quelques données de démo. Aucune base à installer.

**Se créer un compte de test pour se connecter :**

```bash
python create_test_user.py
#   → identifiants : test_iv@devoptiq.test  /  mot de passe : safe
```

> 🔁 **Travailler sur les vraies données de staging-mv** (au lieu de SQLite) : mets dans ton `.env` la `DATABASE_URL` = URL Neon *pooled* de la branche `staging-mv`. À réserver au besoin — au quotidien, SQLite est plus rapide et sans risque.

---

## 5 — Workflow Git au quotidien

```bash
# Partir à jour depuis dev-mv
git checkout dev-mv
git pull origin dev-mv

# (option propre) créer une branche de feature
git checkout -b feature/ma-fonctionnalite

# coder… puis
git add -A
git commit -m "Feat: description claire de ce qui change"
git push -u origin feature/ma-fonctionnalite   # ou directement dev-mv
```

**Tester sur l'URL de preview en ligne** → merge vers `staging-mv` :

```bash
git checkout staging-mv
git pull origin staging-mv
git merge dev-mv            # ou merge ta branche de feature
git push origin staging-mv  # ⇒ déclenche le déploiement Cloud Run devoptiq-staging-mv
```

Quelques minutes plus tard, l'URL du service `devoptiq-staging-mv` (visible dans la console Cloud Run, ou en fin de log du workflow GitHub Actions) reflète tes changements.

**Faire remonter vers le staging commun** : ouvre une **Pull Request `dev-mv` → `staging`** sur GitHub et fais-la relire par Mael. La mise en prod (`staging` → `prod-stable`) reste à la main de Mael.

> Convention de messages de commit (déjà en place dans le repo) : préfixe court — `Feat:`, `Fix:`, `Docs:`, `Refactor:`, `Tests:`…

---

## 6 — Variables d'environnement

Toutes regroupées dans **`.env.example`** (copie-le en `.env`). Récapitulatif :

| Variable | Obligatoire | Rôle / défaut |
|---|---|---|
| `DATABASE_URL` | non en local | URL PostgreSQL Neon. **Vide ⇒ SQLite local** automatique. |
| `SECRET_KEY` | recommandé | Clé de session Flask. Défaut `devoptiq-secret` (à remplacer hors local). |
| `PORT` | non | Port HTTP, défaut `8080`. |
| `OPENAI_API_KEY` | pour l'IA | Chatbot, import IA, propositions, changelog. Absente ⇒ fallback à blanc. |
| `OPENAI_MODEL` | non | Défaut `gpt-4o-mini`. |
| `OPENAI_CHATBOT_MODEL` | non | Défaut `gpt-4o-mini`. |
| `ANTHROPIC_API_KEY` | pour l'IA carto | Aussi accepté : `ANTHROPIC_KEY`. |
| `ROME_CLIENT_ID` / `ROME_CLIENT_SECRET` | pour Projection métier | OAuth2 API France Travail (ROME 4.0). |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` | pour les emails | Reset mot de passe & notifications (SMTP Gmail). |
| `FLASK_ENV` | non | Étiquette d'environnement (`local`/`staging`/`production`). |
| `GOOGLE_CLOUD_PROJECT` | non en local | Injectée par Cloud Run. |

---

## 7 — CI/CD & déploiement

Le déploiement est **100 % automatique via GitHub Actions** (dossier `.github/workflows/`). Chaque workflow : checkout → auth Google Cloud (Workload Identity Federation) → `docker build` → push sur Artifact Registry → `gcloud run deploy`.

| Workflow | Se déclenche sur push | Service Cloud Run | Secrets DB / clé |
|---|---|---|---|
| `deploy-staging-mv.yml` | `staging-mv` | `devoptiq-staging-mv` | `STAGING_MV_DATABASE_URL`, `STAGING_MV_SECRET_KEY` |
| `deploy-staging.yml` | `staging` | `devoptiq-staging` | `STAGING_DATABASE_URL`, `STAGING_SECRET_KEY` |
| `deploy-production.yml` | `prod-stable` | `devoptiq` | `PROD_DATABASE_URL`, `PROD_SECRET_KEY` |

**Secrets GitHub Actions** (Settings → Secrets and variables → Actions) :

- Partagés (déjà présents) : `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_SA_EMAIL`
- Par environnement : `*_DATABASE_URL`, `*_SECRET_KEY` (voir tableau ci-dessus)

Région : `europe-west1` · Mémoire : `2Gi` · Timeout : `120s` · Image servie par **Gunicorn** (`Code.app:app`, voir `Dockerfile` + `startup.sh`).

Suivre un déploiement : onglet **Actions** du dépôt → le run en cours montre chaque étape et l'URL finale du service.

---

## 8 — Base de données (Neon)

- **Prod** = PostgreSQL managé **Neon**. **Local** = SQLite (fallback automatique, voir §4).
- Le code adapte le pool de connexions à Neon (free tier ≈ 20 connexions max) : `pool_size=2`, `max_overflow=3`, `pool_pre_ping`, recyclage 300s (`Code/app.py`).
- **Branches Neon** = copies instantanées isolées. Chaque environnement a la sienne (`production`, `staging`, `staging-mv`). Tester sur `staging-mv` ne touche **jamais** la prod.

**Se connecter en ligne de commande** (debug) :
```bash
psql "postgresql://user:password@ep-xxxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"
```

**Schéma & migrations** — bon à savoir :
- Le schéma est créé/complété au **démarrage de l'app** (`db.create_all()` + quelques `ALTER TABLE` idempotents dans certaines routes). C'est ce qui fait foi en prod.
- Un dossier `migrations/` (Flask-Migrate / Alembic) existe pour l'historique, **mais la prod ne lance pas `alembic upgrade`** automatiquement. Si tu ajoutes une colonne/table, suis le pattern existant (création idempotente au démarrage) plutôt que de présumer qu'une migration Alembic sera jouée.

---

## 9 — Tests

```bash
./run_tests.sh                 # toute la suite + rapports HTML
./run_tests.sh -k activities   # filtrer par nom
pytest tests/ -v               # appel direct
```

Les rapports sont générés dans `tests/` (`report_visuel.html`, `report_pytest.html`). Lance les tests avant d'ouvrir une PR vers `staging`.

---

## 10 — Architecture & conventions de code

**Arborescence (résumé)** — détail complet dans [`CLAUDE.md`](./CLAUDE.md) et la doc HTML [`docs/index.html`](./docs/index.html) :

```
Code/
  app.py            # create_app(), enregistrement des 41 blueprints, config DB/mail
  extensions.py     # db = SQLAlchemy(), mail, pragmas SQLite
  models/models.py  # TOUS les modèles SQLAlchemy
  routes/           # 1 blueprint = 1 domaine fonctionnel (+ templates/ Jinja2)
static/             # CSS & JS par domaine, + static/optiqcarto/ (éditeur SVG maison)
docs/               # documentation progressive (index.html, guide.html)
.github/workflows/  # CI/CD Cloud Run
```

**Conventions (à respecter pour rester cohérent) :**
- **Pas de framework JS** : tout en vanilla JS, `$()` = alias de `document.querySelector`.
- **CSS par domaine** : chaque page a son CSS dédié ; `optiq.css` = styles globaux.
- **Templates Jinja2** : pages composées de partials (`{% include %}`).
- **Blueprints Flask** : un domaine = un fichier dans `Code/routes/`, enregistré dans `app.py`.
- **Couleurs thème** : rose `#ec4899` / `#be185d` (principal), vert `#22c55e` (accent).
- **Commentaires** : seulement pour les *pourquoi* non-évidents, pas pour paraphraser le code.
- ⚠️ **OptiqCarto** (`static/optiqcarto/`) est synchronisé avec un second repo `OptiqCarto/`. Si tu touches `editor.js` / `style.css` / `vsdx_importer.js`, **synchronise les deux** (voir CLAUDE.md).

> 📖 **`CLAUDE.md`** à la racine est le fichier de contexte le plus complet (modèles de données, liste des pages/blueprints, état de la doc). À lire en premier pour comprendre le métier.

---

## 11 — Sécurité & pièges à éviter

- 🚫 **Ne commite jamais `.env`** ni une clé API / mot de passe. (`.env` est déjà dans `.gitignore`.)
- 🧪 **Développe sur SQLite ou sur la branche Neon `staging-mv`**, jamais en pointant `DATABASE_URL` sur la prod.
- 🚀 **Un push sur `staging`/`prod-stable` déploie pour de vrai.** Passe par `dev-mv`/`staging-mv` puis PR.
- 🔑 **À nettoyer (dette existante)** : `Code/app.py` contient des **valeurs par défaut sensibles en clair** — mot de passe applicatif Gmail (`MAIL_PASSWORD`) et `SECRET_KEY` par défaut `devoptiq-secret`. Comme elles sont déjà dans l'historique Git, il est recommandé de **régénérer le mot de passe d'application Gmail** et de **forcer `SECRET_KEY`/`MAIL_PASSWORD` par variables d'environnement uniquement** (retirer les valeurs en dur). À planifier rapidement.
- 🧹 La racine contient des scripts utilitaires one-shot (`cleanup_*.py`, `fix_*.py`, `transfer_db_data.py`…) : ce sont des outils de maintenance ponctuels, **à ne pas exécuter sans comprendre leur effet sur la base**.

---

## 12 — Ressources

| Ressource | Où |
|---|---|
| Contexte métier & technique complet | [`CLAUDE.md`](./CLAUDE.md) |
| Documentation HTML progressive | [`docs/index.html`](./docs/index.html), [`docs/guide.html`](./docs/guide.html) |
| Schéma de la base | `database_schema.png` (racine) |
| Prompts IA & méthodo | dossier [`doc/`](./doc/) (Word/PDF) |
| Dépôt GitHub | `maelouuu/devoptiq` |
| Hébergement | Google Cloud Run — projet GCP (console) |
| Base de données | [console.neon.tech](https://console.neon.tech) |

**Contact :** Mael Girardin — afdec.enterprise.services@gmail.com

---

*Bon dev ! 🚀 — Ce fichier vit avec le projet : tiens-le à jour si le setup évolue.*
