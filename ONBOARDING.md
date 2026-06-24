# 👋 Bienvenue sur DevOPTIQ

Salut ! Tu rejoins le dev de **DevOPTIQ**, une appli web Flask de gestion des compétences et activités.
Ce fichier te dit **juste ce qu'il faut faire pour coder**. En 10 min t'es opérationnel.

> En une phrase : **Flask (Python 3.12) + SQLAlchemy**, base **PostgreSQL** en ligne / **SQLite** en local,
> front en **HTML/CSS/JS vanilla** (pas de framework). En local, **aucune base à installer**.

---

## 1. Ce que Mael te donne

Avant de commencer, tu dois avoir reçu :

- ✅ **Une invitation GitHub** sur le dépôt `maelouuu/devoptiq` → **accepte-la** (elle arrive par mail).
- ✅ **Tes clés API IA** (OpenAI, Anthropic, et France Travail/ROME) → tu les colleras dans ton fichier `.env`.

C'est tout pour démarrer. (Les accès Neon / Google Cloud ne servent que si tu dois debugger en ligne — Mael te les donnera au besoin.)

---

## 2. Installer en local (le chemin rapide)

> Pré-requis : **Python 3.12** et **Git**.

```bash
# 1) Récupérer le code et se mettre sur ta branche de travail
git clone https://github.com/maelouuu/devoptiq.git
cd devoptiq
git checkout dev-mv

# 2) Environnement Python isolé
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

# 3) Dépendances
pip install -r requirements.txt

# 4) Config : copier le modèle et coller tes clés
cp .env.example .env               # Windows : copy .env.example .env
#   → ouvre .env, colle tes clés OPENAI_API_KEY / ANTHROPIC_API_KEY / ROME_*
#   → laisse DATABASE_URL VIDE  (= base SQLite locale créée toute seule)

# 5) Lancer
python Code/app.py
#   → ouvre http://localhost:8080
```

Au premier lancement sans `DATABASE_URL`, l'appli crée une base **SQLite** locale avec le schéma et des données de démo. Rien d'autre à faire.

**Te connecter** — crée un compte de test :

```bash
python create_test_user.py
#   → identifiant : test_iv@devoptiq.test   /   mot de passe : safe
```

---

## 3. Ton workflow Git au quotidien

- **`dev-mv`** = ta branche de travail. C'est là que tu codes au jour le jour.
- **`staging-mv`** = ta preview en ligne. Quand tu y pousses, l'appli se redéploie automatiquement sur une URL que tu peux montrer/tester.

```bash
# Coder sur dev-mv
git checkout dev-mv
git pull origin dev-mv
# ... tes modifs ...
git add -A
git commit -m "Feat: ce que j'ai changé"
git push origin dev-mv

# Voir le résultat en ligne → fusionner dans staging-mv
git checkout staging-mv
git pull origin staging-mv
git merge dev-mv
git push origin staging-mv         # ⇒ déploiement auto, l'URL se met à jour en qq min
```

Quand une fonctionnalité est prête à intégrer au projet commun, ouvre une **Pull Request `dev-mv` → `staging`** sur GitHub : Mael la relit. La mise en production reste gérée par Mael.

> ⚠️ Deux réflexes : **ne commit jamais ton `.env`** (il contient tes clés — il est déjà ignoré par Git), et **pousser sur `staging-mv` déclenche un vrai déploiement** (c'est voulu, c'est ta preview).

---

## 4. Pour comprendre le projet

- 📖 **`CLAUDE.md`** (à la racine) = le contexte complet : modèles de données, liste des pages, conventions de code. À lire en premier pour t'y retrouver.
- 🛠️ Détail de toutes les variables d'environnement : commentaires dans **`.env.example`**.
- 🎨 Convention front : tout en **vanilla JS**, `$()` = `document.querySelector`, un CSS par page, couleurs thème rose `#ec4899` / vert `#22c55e`.

---

**Une question, un accès qui manque ?** → Mael Girardin · afdec.enterprise.services@gmail.com

Bon dev ! 🚀
