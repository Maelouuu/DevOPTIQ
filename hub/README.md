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
| **Courrier** | Les réinitialisations de mot de passe demandées sur chaque instance (lecture SEULE de `password_resets`), et ce qui est REVENU sur l'adresse d'envoi — les rejets, seule preuve qu'un mail n'est pas arrivé. |
| **Atelier** | Le plan de travail : une toile infinie de notes, listes à cocher, captures, liens — et des **maquettes de pages** de l'application sur lesquelles on accroche les fonctionnalités à venir. Le bouton *Modèles* y pose d'un clic les 14 pages de l'app et la liste des chantiers, déjà rattachés. |

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

La page **Courrier** demande deux secrets de plus, et elle s'éteint proprement sans eux : `HUB_IMAP_USER` (l'adresse d'envoi) et `HUB_IMAP_PASSWORD`.
⚠️ **Ce ne sont pas `MAIL_USERNAME` / `MAIL_PASSWORD`.** Ceux-là font ENVOYER l'application et sont posés sur *ses* services Cloud Run par `deploy-staging.yml`, `deploy-officielle.yml` et `deploy-beta.yml` ; le hub, qui a son propre service, ne les voit pas. Les noms se ressemblent et vivent dans la même liste de secrets : la page nomme donc explicitement ce qui lui manque, et dit que ces deux-là ne sont pas lus ici.
⚠️ Ce mot de passe d'application doit être un **second**, distinct de celui qui sert à ENVOYER (`MAIL_PASSWORD` des instances) : révoquer l'un ne doit pas couper l'autre. Et un mot de passe d'application Google n'est **pas limitable** — il ouvre la boîte en lecture ET l'envoi SMTP. C'est inhérent au procédé ; le hub s'y tient en lecture stricte (`readonly=True`, `BODY.PEEK`, en-têtes seulement).
Les bases lues par cette page arrivent dans `HUB_DBS_B64`, composée au déploiement depuis les specs Cloud Run — aucune URL à recopier.

La page **Atelier** n'exige **rien**. Sa toile est écrite dans le navigateur (IndexedDB) à chaque geste : instantané, hors ligne, sans aucun secret — mais liée à ce profil. Le secret facultatif `HUB_ATELIER_DB` (une base PostgreSQL **à soi**) allume le miroir serveur, et la toile suit alors d'un poste à l'autre ; les tables se créent au premier appel. Sans lui, le filet reste l'export en fichier, captures comprises.
⚠️ Une base **à soi**, jamais celle d'une instance : `HUB_DBS_B64` est en lecture seule, l'atelier écrit. Les deux ne se croisent nulle part dans le code, et un test l'interdit.

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

Les modèles de l'atelier vivent dans **`atelier_modeles.py`** — les pages de
l'application, leurs sections et ce qu'elles portent, plus la liste des
chantiers. ⚠️ Ce fichier **décrit** l'application, il ne la lit pas (le hub
n'a ni ses gabarits ni sa base) : quand une page bouge, on le reporte ici.
Un chantier désigne sa page par son NOM ; `tests/test_156_hub_atelier.py`
vérifie que chaque couple (page, section) existe, car une faute de frappe ne
lève rien — elle fait disparaître le badge en silence.

⚠️ **La hauteur d'une maquette se CALCULE sur son texte** (`_hauteur`), elle
ne se devine pas à la section : un forfait laissait défiler à l'intérieur
toute page dont les phrases dépassaient deux lignes, et une maquette qu'on ne
voit jamais en entier ne sert plus de plan. Les constantes sont **mesurées à
l'écran** (56 signes par ligne, 20 px la ligne, 62 px le reste d'une section,
134 px le haut et le bas, 33 px la première pastille de chantier) : les
changer sans remesurer rouvre le défaut. Et les pastilles comptent — une
section porte ce qu'on lui accroche.

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

Pour exercer le miroir de l'atelier sans base distante, SQLite suffit — c'est
aussi ce que font les tests :

```bash
HUB_ATELIER_DB="sqlite:////tmp/atelier.db" PORT=8134 HUB_INSECURE_COOKIE=1 \
  HUB_PASSWORD=testtest python app.py
```
