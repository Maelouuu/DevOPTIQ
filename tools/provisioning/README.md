# Provisionnement d'une instance client (outil AFDEC)

Crée, sur la base d'une instance déjà déployée, les **comptes**, l'**entité** et sa
**cartographie**, à partir d'un plan JSON. Le script rejoue la même logique que
l'éditeur (`_sync_carto_to_db`) : activités, rôles et connexions sont dérivés de
la carte exactement comme après un import Visio dans l'interface.

> ⚠️ `tools/` est exclu de l'image client (`.dockerignore`). Cet outil s'exécute
> depuis un poste AFDEC ayant accès à la base de l'instance cible.

## Lancer

```bash
export DATABASE_URL="postgresql://user:pass@hôte:5432/base"   # base de l'instance

# 1) toujours commencer par une simulation
python tools/provisioning/provision.py --plan tools/provisioning/plans/araymond.json --dry-run

# 2) appliquer
python tools/provisioning/provision.py --plan tools/provisioning/plans/araymond.json
```

| Option | Effet |
|---|---|
| `--database-url URL` | base cible, à la place de `$DATABASE_URL` |
| `--dry-run` | affiche le détail des actions, ne commit rien |
| `--force-password` | réinitialise aussi le mot de passe des comptes **déjà existants** (sans ce drapeau, un compte existant garde le sien) |

Le script est **idempotent** : comptes retrouvés par e-mail, entité par nom +
propriétaire, carto re-synchronisée par `shape_id`/nom. Le rejouer ne duplique rien.

## Écrire un plan

```jsonc
{
  "label": "Nom lisible du plan",
  "users": [
    {
      "email": "prenom.nom@client.com",
      "first_name": "Prénom", "last_name": "Nom",
      "status": "manager",          // user | rh | administrateur | manager…
      "password": "…",
      "entity": "Nom de l'entité"   // rattachement du compte
    }
  ],
  "entities": [
    {
      "name": "Nom de l'entité",
      "description": "…",
      "owner_email": "prenom.nom@client.com",   // OBLIGATOIRE, voir ci-dessous
      "managers": ["prenom.nom@client.com"],
      "vsdx_filename": "Source.vsdx",           // affiché dans l'app
      "carto": "../carto/fichier.json"          // chemin relatif AU PLAN
    }
  ]
}
```

Deux règles à connaître, tirées du modèle de données :

- **`owner_email` est obligatoire.** `Entity.get_active()` est strict : une
  entité n'est visible que par son propriétaire (`owner_id`). Une entité sans
  propriétaire n'apparaît dans aucune page.
- **« manager » n'est pas un statut.** Dans OPTIQ, on est manager parce que
  d'autres comptes vous désignent (`users.manager_id` / `user_roles.manager_id`) —
  c'est ce lien que lit la page Compétences. `managers: []` établit ce lien pour
  les comptes de l'entité ; `status` ne sert qu'à l'affichage et à la section
  Administration (`administrateur`). Sur une entité qui n'a encore qu'un compte,
  le rattachement est donc sans objet : il prendra effet dès l'ajout de
  collaborateurs (page Comptes, puis Gestion RH).

## Préparer la cartographie

Le plan consomme un **JSON de carto**, pas le `.vsdx` : la conversion utilise
l'importeur Visio de l'app (`static/optiqcarto/vsdx_importer.js`) via le banc
`tests/carto`, dans un navigateur sans interface.

```bash
python3 -m http.server 8099 &                    # servir la racine du dépôt
python tools/guide/extract_carto.py \
       tools/provisioning/carto/Source.vsdx \
       tools/provisioning/carto/source.json
```

Le `.vsdx` d'origine est conservé à côté du JSON : il permet de régénérer la
carto après une amélioration de l'importeur. Les `.vsdx` sont exclus de l'image
client.

## Plans existants

| Plan | Contenu |
|---|---|
| `plans/araymond.json` | Compte `vikrant.khadapkar@araymond.com` (manager) + entité **ARaymond — RFQ FluidClip** issue de `Map_RFQ_FluidClip_Harmonized_HG_v9.vsdx` — 42 activités, 18 rôles, 72 connexions. |
