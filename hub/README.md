# Optiq Hub — point d'entrée unique de l'écosystème

Service Cloud Run **séparé de l'application** (comme OptiqPulse). Il répond à un
problème d'exploitation : entre les instances en ligne, les fichiers de doc, les
URLs et les lignes de terminal, plus rien n'était retrouvable au même endroit.

Le hub rassemble :

| Section | Ce qu'elle apporte |
|---|---|
| **Instances** | Les 4 services déployés, à qui ils s'adressent, sur quelle base ils tournent, et leur **état mesuré en direct** (sondé par le hub, pas déclaré). |
| **Documentation** | La doc technique et le guide utilisateur **servis par le hub** — plus de fichier local à retrouver. Le plan Refonte V1.1 aussi. |
| **Outils locaux** | Le catalogue des commandes : ce que fait chacune, quand s'en servir, la ligne exacte copiable en un clic. |
| **Dépôt & CI** | Quelle branche part où, par quel workflow, et quels secrets GitHub sont en jeu. |

## Ce que le hub ne fait pas

Il **ne lance pas** les traitements locaux. Une page web hébergée sur Cloud Run
ne peut pas exécuter `pytest` ni un script de provisionnement sur le poste de
l'utilisateur — il faudrait un agent installé sur la machine, avec les risques
que ça suppose. Le hub en garde donc le mode d'emploi et la commande exacte,
copiable ; l'exécution reste dans le terminal.

Les traitements qui *peuvent* vivre en ligne y sont déjà : déploiements
(GitHub Actions), panel de tests et carnet de bord (dans l'app staging),
suivi d'audience (OptiqPulse).

## Accès

Comptes nommés — le hub nomme les bases, les secrets et les instances internes,
ce n'est pas une page publique.

| Identifiant | Mot de passe | Variables de surcharge |
|---|---|---|
| `Mael_Girardin` | secret `HUB_PASSWORD`, défaut baké `testtest` | `HUB_USER`, `HUB_PASSWORD`, `HUB_PASSWORD_HASH` |
| `Hubert_Grandjean` | défaut baké | `HUB_PASSWORD_HG`, `HUB_PASSWORD_HASH_HG` |

- ⚠️ Le dépôt ne contient **que des hashes** (pbkdf2-sha256, 600 000 tours) :
  aucun mot de passe en clair n'y figure. Les défauts baqués restent des
  défauts — à remplacer par un secret dès qu'un compte compte vraiment.
- ⚠️ `_check_credentials` parcourt **tous** les comptes sans court-circuit :
  sortir dès que l'identifiant ne correspond pas rendrait la réponse plus
  rapide pour un nom inconnu que pour un nom connu, et on énumérerait les
  comptes au chronomètre.
- anti-force-brute mémoire : 8 essais / 15 min par IP ; `noindex`.

## Déploiement

`.github/workflows/deploy-hub.yml` — push sur `staging` touchant `hub/**` ou
`docs/**`, ou lancement manuel (*Run workflow*). Le workflow :

1. copie `docs/` dans `hub/_docs` (le `.dockerignore` de la racine exclut
   `docs/` de l'image applicative ; ici le contexte de build est `hub/`) ;
2. construit et pousse l'image ;
3. conserve `HUB_SECRET_KEY` d'un déploiement à l'autre — sinon chaque livraison
   déconnecterait la session ;
4. vérifie `/health` **et** que `/` redirige bien vers la connexion.

⚠️ `/health` et pas `/healthz` : ce dernier est intercepté par le frontend
Google sur `*.run.app` (404 avant même d'atteindre le conteneur).

## Retoucher le contenu

Tout le contenu vit dans **`inventaire.py`** — instances, documents, commandes,
branches, workflows, secrets. Le gabarit ne contient aucune donnée en dur :
ajouter une instance ou une commande, c'est éditer une liste Python.

⚠️ Aucun secret dans ce fichier : on **nomme** les bases et les secrets GitHub,
on ne recopie jamais leurs valeurs.

## En local

```bash
cd hub
mkdir -p _docs && cp ../docs/doc_technique.html ../docs/guide.html ../docs/refonte_competences_v1_1.md _docs/
ln -sfn ../../docs/assets _docs/assets
PORT=8134 HUB_INSECURE_COOKIE=1 HUB_PASSWORD=testtest python app.py
```

`HUB_INSECURE_COOKIE=1` est nécessaire hors HTTPS, sinon le cookie de session
n'est pas posé et la connexion boucle.
