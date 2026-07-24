# OptiqFluent — Guide d'installation (beta test)

Installation autonome sur votre infrastructure, via Docker. Durée estimée : 20 minutes.

## 1. Prérequis

- Une machine (serveur ou VM) avec **Docker** et **Docker Compose** installés
  (Linux recommandé ; 2 vCPU / 4 Go RAM suffisent pour le test).
- Le **jeton d'accès au registre** fourni par AFDEC (lecture seule).
- Le **fichier de licence** `optiqfluent.lic` fourni par AFDEC.
- Un **compte OpenAI** avec une clé API (cf. section 4 du `.env.example`).
- Facultatif : un compte Google dédié pour l'envoi des emails de
  réinitialisation de mot de passe (cf. section 5 du `.env.example`).

## 2. Récupérer l'application

```bash
docker login ghcr.io -u <utilisateur-fourni> -p <jeton-fourni>

mkdir optiqfluent && cd optiqfluent
# Déposez ici les 2 fichiers fournis par AFDEC :
#   docker-compose.yml
#   .env.example
mkdir license
# Déposez la licence dans license/optiqfluent.lic
```

## 3. Configurer

```bash
cp .env.example .env
nano .env    # remplir chaque section en suivant les commentaires
```

Minimum obligatoire : `POSTGRES_PASSWORD`, `SECRET_KEY`, `ADMIN_EMAIL`,
`ADMIN_PASSWORD`, `OPENAI_API_KEY`.

## 4. Démarrer

```bash
docker compose up -d
docker compose logs -f app   # attendre « [BOOTSTRAP] Compte administrateur créé »
```

L'application est disponible sur `http://<machine>:8080`. Connectez-vous avec
`ADMIN_EMAIL` / `ADMIN_PASSWORD`, changez ce mot de passe, puis créez les
comptes de vos collaborateurs (menu Gestion des comptes).

La base de données se crée entièrement toute seule au premier démarrage —
aucune étape SQL manuelle.

## 5. Mettre à jour (nouvelles versions livrées par AFDEC)

```bash
docker compose pull && docker compose up -d
```

Rien d'autre : la configuration (`.env`), la licence et vos données sont
conservées ; les migrations de base s'appliquent automatiquement au démarrage.

## 6. Renouveler la licence

Remplacez `license/optiqfluent.lic` par le nouveau fichier fourni par AFDEC.
Prise en compte immédiate, sans redémarrage. L'état de la licence est visible
sur `http://<machine>:8080/license`.

## 7. Sauvegardes (recommandé)

Vos données vivent dans le volume Docker `optiqfluent-db` :

```bash
docker compose exec db pg_dump -U optiqfluent optiqfluent > sauvegarde_$(date +%F).sql
```

## En cas de problème

- `docker compose logs app` — les messages `[DB]`, `[BOOTSTRAP]`, `[LICENSE]`,
  `[MAIL]` indiquent l'état de chaque composant au démarrage.
- Page blanche « Licence requise » : licence absente/expirée → contactez AFDEC.
- Reset de mot de passe sans email reçu : section 5 du `.env` non remplie.
- Support : afdec.enterprise.services@gmail.com
