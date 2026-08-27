# OptiqFluent — Runbook de release (côté AFDEC)

Procédure interne pour publier une version client et gérer les licences.
Le kit remis au client, lui, est décrit dans `INSTALL.md`.

## 0. Mise en place initiale (une seule fois)

1. **Clés de licence** — sur ta machine, dans le dépôt :
   ```bash
   python tools/licensing/keygen.py
   ```
   - `tools/licensing/license_private.pem` : **gitignorée**. À sauvegarder dans
     un gestionnaire de mots de passe / coffre. La perdre = ne plus pouvoir
     émettre de licences compatibles avec les images déjà livrées.
   - `Code/license_pubkey.pem` : **à committer** (embarquée dans l'image).

2. **Clé des prompts IA** :
   ```bash
   pip install cryptography   # si besoin
   python tools/prompts/encrypt_prompts.py
   ```
   - Génère `tools/prompts/prompts_key.txt` (**gitignorée**, à sauvegarder au
     même endroit que la clé de licence).
   - Ajouter cette clé comme **secret GitHub** `PROMPTS_KEY`
     (repo → Settings → Secrets and variables → Actions) : le workflow de build
     en a besoin pour chiffrer le catalogue.

3. **Premier build** : pousser un tag (voir §1). Après le premier run, aller sur
   la page du package `optiqfluent` (profil GitHub → Packages) :
   - visibilité **Private** ;
   - vérifier le lien avec le dépôt.

4. **Token de lecture pour le client** : GitHub → Settings → Developer settings
   → Personal access tokens → **Fine-grained** de préférence, sinon classic avec
   l'unique scope **`read:packages`**, expiration alignée sur la durée du
   contrat. C'est ce token que le client utilise dans `docker login ghcr.io`.
   Le révoquer coupe l'accès aux mises à jour (pas aux images déjà tirées).

## 1. Publier une version

```bash
git checkout optiqfluent-staging
# ... s'assurer que tout est committé et testé ...
git tag client-v1.0.0
git push origin client-v1.0.0
```

Le workflow GitHub Actions `client-image` construit et pousse :
- `ghcr.io/maelouuu/optiqfluent:1.0.0` (figée)
- `ghcr.io/maelouuu/optiqfluent:beta` (glissante — celle que référence le
  docker-compose client)

Côté client, la mise à jour est ensuite : `docker compose pull && docker compose up -d`.

Contenu automatique de l'image : prompts chiffrés (catalogue en clair exclu),
sources Python compilées en bytecode puis supprimées, licence exigée
(`REQUIRE_LICENSE=1`), testpanel désactivé, pas de LibreOffice.

## 2. Émettre une licence client

```bash
python tools/licensing/make_license.py --licensee "ACME SAS" --days 31
```

- Embarque automatiquement la clé de prompts si `tools/prompts/prompts_key.txt`
  est présent (sinon `--prompts-key ...`). **Sans elle, les fonctions IA du
  client resteront dégradées.**
- Produit `tools/licensing/out/optiqfluent-acme-sas.lic` → à remettre au client
  (il le dépose dans `license/optiqfluent.lic`).

**Renouvellement** : ré-émettre avec une nouvelle date, envoyer le fichier, le
client remplace l'ancien — pris en compte à chaud, sans redémarrage.

**Fin de contrat** : ne rien faire — la licence expire seule et l'app se bloque
(données intactes). Révoquer aussi le token ghcr.

## 3. Ce que contrôle AFDEC, en résumé

| Levier | Action | Effet |
|---|---|---|
| Licence signée | ne pas renouveler | app bloquée à la date d'expiration |
| Clé de prompts | absente de la licence | fonctions IA dégradées |
| Token ghcr | révoquer | plus de mises à jour |
| Contrat | clauses PI + anti-contournement | recours juridique |

## 4. Nos propres déploiements (Cloud Run) depuis cette branche

Ajouter dans la config d'environnement Cloud Run :
- `REQUIRE_LICENSE=0` (ou une licence AFDEC longue durée)
- `PROMPTS_KEY=<la clé>` (l'image n'a que le bundle chiffré)
- `TESTPANEL_ENABLED=1` si besoin du panel (les tests ne sont pas dans l'image :
  le panel s'affiche mais ne peut pas lancer de runs)
