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
| `--only EMAIL` | ne traiter que les entités de ce propriétaire — rejouer un plan pour **un seul compte** sans retoucher les autres |
| `--force-password` | réinitialise aussi le mot de passe des comptes **déjà existants** (sans ce drapeau, un compte existant garde le sien) |

Le script est **idempotent** : comptes retrouvés par e-mail, entité par nom +
propriétaire, carto re-synchronisée par `shape_id`/nom. Le rejouer ne duplique rien.

> ⚠️ **Une entité portant un bloc `carto` est re-synchronisée à chaque
> passage**, et `_sync_carto_to_db` supprime les rôles absents de la carte :
> les rôles venus de l'Excel (« Account Manger », « PDE »…) sont donc effacés
> puis recréés à chaque rejeu. Sans conséquence sur le résultat, mais leurs
> `id` changent — d'où `--only` pour ne rejouer que ce qu'on vise.

> ⚠️ **`--dry-run` a longtemps menti.** Le plan réutilise du code applicatif
> (`_sync_carto_to_db`) qui se termine par un `commit()` : dès qu'un plan
> synchronisait une carto, ce commit figeait TOUT ce que les étapes
> précédentes avaient écrit, et le rollback final n'annulait plus que la
> dernière. En simulation, `commit` est désormais remplacé par `flush`
> (`_neutraliser_commits`) : les contraintes sont vérifiées, rien n'est figé.

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
      "entity": "Nom de l'entité",  // rattachement du compte
      "roles": ["Rôle A", "Rôle B"] // rôles tenus, voir plus bas
    }
  ],
  "entities": [
    {
      "name": "Nom de l'entité",
      "description": "…",
      "owner_email": "prenom.nom@client.com",   // OBLIGATOIRE, voir ci-dessous
      "managers": ["prenom.nom@client.com"],
      "vsdx_filename": "Source.vsdx",           // affiché dans l'app
      "carto": "../carto/fichier.json",         // chemin relatif AU PLAN
      "content": "../data/fichier.json"         // contenu des activités, voir plus bas
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

### Repartir d'une carto corrigée à la main

Quand une carto a été **reprise dans l'éditeur** (retouches que le `.vsdx` ne
contient pas), on ne repasse pas par Visio : depuis le compte concerné, bouton
**« Exporter la carto »** de l'éditeur → fichier `.optiqcarto`. Déposez-le dans
`tools/provisioning/carto/` et référencez-le tel quel dans le plan :

```jsonc
"carto": "../carto/rfq_fluidclip_corrige.optiqcarto"
```

`apply_carto` accepte aussi bien le paquet que le diagramme brut. Le même fichier
peut être remis à un utilisateur : dans l'app, **Gestion des entités → Importer une
carto** recrée l'entité et sa cartographie sur son compte.

## Compléter une carto avec un Excel client

Un client fournit souvent ses tâches dans un tableur (`ID | Department | Activity |
Guarantor | Task | Tool | Doer | Approver | Skills`), avec les libellés **de son
vocabulaire**, alors que la carto a été harmonisée. Le bloc `tasks_excel` injecte
ce contenu dans une carto **déjà en place** :

```jsonc
{
  "name": "ARaymond — RFQ FluidClip",
  "match_name_contains": "fluidclip",   // retrouve l'entité même renommée
  "owner_email": "…@…",                 // périmètre : CE compte, pas un autre
  "require_existing": true,             // ne crée rien si elle est absente
  "tasks_excel": {
    "file": "../data/clip_rfq_tasks.xlsx",
    "mapping": "../data/clip_rfq_mapping.json"   // libellé Excel → activité carto
  }
}
```

- L'injection réutilise le pipeline d'import de l'app (`Code/routes/import_full`) :
  même lecture du fichier (valeurs propagées sur les lignes fusionnées), mêmes
  get-or-create outils/rôles, **déduplication des tâches par nom** — rejouer le
  plan ne crée rien en double.
- Le **mapping est explicite** parce que les libellés ne se ressemblent pas assez
  pour un rapprochement automatique fiable (« Risk Assements » → « Conduct Risk
  Assessment » passe, « Identify Part » → « Develop Preliminary Technical
  Solution » non). Une entrée à `null` écarte une ligne ; une activité absente du
  mapping n'est reprise que si l'appariement automatique atteint 90 %.
- `Guarantor` devient un rôle **Garant** de l'activité, `Doer`/`Approver` des
  rôles de tâche, `Skills` des compétences. L'activité garde aussi le garant
  hérité de sa bande : ce sont deux garants, comme après un import Excel dans
  l'interface.
- `require_existing` + `owner_email` **cloisonnent le plan à un compte** : si
  l'entité n'existe pas chez ce propriétaire, le script s'arrête sans rien
  écrire, y compris si une entité du même nom existe chez quelqu'un d'autre.

## Rattacher des comptes à des rôles

`roles` sur un compte crée les lignes `user_roles` — c'est ce qui fait d'un
collaborateur le **titulaire** d'un rôle, et ce que lisent la page des rôles et
la page Compétences.

```jsonc
{ "email": "ines.lemoine@example.com", "entity": "…", "roles": ["Technicien Méthodes", "Opérateur Assemblage"] }
```

Les rôles **naissent des bandes de la carto** : l'étape passe donc après
`apply_carto`, et un rôle nommé dans le plan mais absent de la carte est
signalé sans être créé — `_sync_carto_to_db` supprime les rôles hors carte, il
disparaîtrait au rejeu suivant. Un compte peut tenir plusieurs rôles.

## Compléter les activités sans passer par un Excel

`tasks_excel` part du tableur d'un client. Quand le contenu est écrit à la main
— jeu de démonstration, entité de référence — le bloc `content` pointe un JSON
et couvre en plus ce que l'Excel ne porte pas : savoirs, savoir-faire,
aptitudes et HSC.

```jsonc
"content": "../data/jeu_de_test_contenu.json"
```

```jsonc
{
  "activities": {
    "Assembler le sous-ensemble": {          // LIBELLÉ exact de la forme dans la carto
      "description": "…",
      "duration_minutes": 45, "delay_minutes": 0,
      "tasks": [
        { "name": "Réaliser les opérations de vissage", "description": "…",
          "duration_minutes": 20, "tools": ["Visseuse dynamométrique"] }
      ],
      "competencies":  ["…"],
      "savoirs":       ["…"],
      "savoir_faires": ["…"],
      "aptitudes":     ["…"],
      "softskills": [
        { "habilete": "Concentration", "niveau": "3 (Maîtrise)", "justification": "…" }
      ]
    }
  }
}
```

- Les activités sont retrouvées **par nom** : une clé qui ne correspond à aucune
  forme de la carto est signalée et ignorée, jamais créée.
- Les outils cités sont créés au besoin, au niveau de l'entité, puis réutilisés.
- Niveaux HSC admis par l'interface : `1 (Aptitude)`, `2 (Acquisition)`,
  `3 (Maîtrise)`, `4 (Excellence)` — le libellé complet est stocké tel quel.
- Idempotent : tâches dédoublonnées par nom, items par libellé. Un rejeu
  n'ajoute rien.

## Plans existants

| Plan | Contenu |
|---|---|
| `plans/araymond.json` | Compte `vikrant.khadapkar@araymond.com` (manager) + entité **ARaymond — RFQ FluidClip** issue de `Map_RFQ_FluidClip_Harmonized_HG_v9.vsdx` — 42 activités, 18 rôles, 72 connexions. |
| `plans/pilote_fluidclip_tasks.json` | Instance pilote : injecte l'Excel client dans les **six** entités « FluidCLip » existantes (Aditya, Hubert, Madhuri, Rakesh, Vaishali, Vikrant) **sans toucher à leur carte**, et crée chez Maël **« Entité de rendu FluidClip »** — copie de la carto que ces comptes ont aujourd'hui, complétée des mêmes données, pour contrôler ce qu'ils voient. Priya Bhivare n'en avait aucune : la sienne est **créée** depuis le même modèle. Non couverts volontairement : « FluidCLip (2) » (2ᵉ copie de h.grandjean) et l'entité sans propriétaire. |
| `plans/jeu_de_test.json` | **Jeu de test — Atelier Assemblage** : entité de démonstration à données fictives chez `mael.pierre.girardin@icloud.com` — 3 rôles, 8 activités entièrement renseignées (24 tâches, 7 outils, compétences, savoirs, savoir-faire, aptitudes, HSC), Inès Lemoine sur **deux** rôles et Rémi Delaunay sur un seul. Le compte propriétaire doit déjà exister. |
| `plans/maelg_fluidclip_tasks.json` | **Compte `afdec.enterprise.services@gmail.com` uniquement** : complète sa carto FluidClip avec l'Excel client `CLIP_ RFQ Tasks` — 25 activités, 96 tâches, 28 outils, 14 rôles, 53 compétences. Ne crée ni compte ni entité. |
