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

Compte unique, comme OptiqPulse — le hub nomme les bases, les secrets et les
instances internes, ce n'est pas une page publique.

- identifiant : `Mael_Girardin` (surchargé par `HUB_USER`)
- mot de passe : secret GitHub **`HUB_PASSWORD`** ; sans ce secret, défaut baké
  `testtest` (à ne pas laisser en l'état).
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
