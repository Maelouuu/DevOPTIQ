# OptiqFluent — Guide d'installation (beta test)

Installation autonome sur votre infrastructure, via Docker. Durée : ~15 minutes.

## 1. Prérequis

- Une machine (serveur ou VM) avec **Docker** et **Docker Compose**
  (Linux recommandé ; 2 vCPU / 4 Go RAM suffisent).
- Le **jeton d'accès au registre** fourni par AFDEC.
- Le **fichier de licence** `optiqfluent.lic` fourni par AFDEC.
- Un **compte OpenAI** avec une clé API (platform.openai.com → API keys) —
  peut aussi être ajouté plus tard.

## 2. Installer

```bash
docker login ghcr.io -u <utilisateur-fourni> -p <jeton-fourni>

mkdir optiqfluent && cd optiqfluent
# Déposez ici les 2 fichiers fournis par AFDEC : docker-compose.yml, .env.example
cp .env.example .env
nano .env          # une seule valeur à choisir : POSTGRES_PASSWORD

docker compose up -d
```

## 3. Suivre l'assistant d'installation

Ouvrez **http://\<machine\>:8080** : l'assistant d'installation se lance
automatiquement au premier démarrage et vous guide pas à pas —

1. **Licence** : collez le contenu du fichier `optiqfluent.lic` ;
2. **Base de données** : laissez la valeur pré-remplie (base intégrée), ou
   indiquez l'URL de votre propre PostgreSQL ; testez la connexion ;
3. **Clé OpenAI** : collez votre clé API et testez-la ;
4. **Email** *(facultatif)* : compte d'envoi pour le « mot de passe oublié » ;
5. **Compte administrateur** : votre premier utilisateur.

Cliquez sur **Installer** : l'application redémarre configurée (~30 s) et vous
amène à la page de connexion. Connectez-vous avec le compte administrateur et
créez les comptes de vos collaborateurs (menu Gestion des comptes).

La configuration est enregistrée dans le dossier `./config` ; les tables de la
base se créent automatiquement — aucune manipulation SQL.

## 4. Mettre à jour (nouvelles versions livrées par AFDEC)

```bash
docker compose pull && docker compose up -d
```

Configuration, licence et données sont conservées ; les migrations
s'appliquent automatiquement.

## 5. Renouveler la licence

Remplacez le fichier de licence (`./config/optiqfluent.lic` si installée via
l'assistant, sinon `./license/optiqfluent.lic`) par le nouveau fichier fourni
par AFDEC — pris en compte sans redémarrage. État visible sur
`http://<machine>:8080/license`.

## 6. Sauvegardes (recommandé)

```bash
docker compose exec db pg_dump -U optiqfluent optiqfluent > sauvegarde_$(date +%F).sql
```

Sauvegardez aussi le dossier `./config`.

## En cas de problème

- `docker compose logs app` — messages `[SETUP]`, `[DB]`, `[BOOTSTRAP]`,
  `[LICENSE]`, `[MAIL]` au démarrage.
- **Relancer l'assistant** : supprimez `./config/optiqfluent.env` puis
  `docker compose restart app` (vos données en base sont conservées).
- Page « Licence requise » : licence absente/expirée → contactez AFDEC.
- Support : afdec.enterprise.services@gmail.com
