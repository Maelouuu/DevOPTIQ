# Audit avant livraison client — 2026-11-25

Relevé sur `staging` au commit `385dda1fa8`, avant l'envoi de l'application
sur le serveur du client indien. Les adaptations de déploiement sont hors
périmètre ; ce document ne porte que sur **ce qui marche ou pas**.

**Méthode.** Rien n'est repris de la documentation : chaque constat a été
reproduit, et plusieurs ont démenti ce que `CLAUDE.md` affirmait. Le banc
principal est un **PostgreSQL 16 vierge** monté par le démarrage NORMAL de
l'application (`create_app`, donc `create_all` plus toutes les migrations à
chaud) — c'est le scénario exact du client le jour 1. S'y ajoutent le balayage
des 104 routes GET, la suite complète, et une relecture au navigateur en
anglais.

## Si vous ne lisez qu'une chose

**Corrigé ici** : trois défauts, dont deux 500 qu'un client neuf aurait vus le
jour 1. Suite : **5196 passés, 1 sauté, zéro rouge**.

**Ce que je prendrais ensuite, dans cet ordre** :

| # | quoi | pourquoi d'abord | coût |
|---|---|---|---|
| 1 | **les 99 routes d'écriture gardées une par une** | les trois trous d'accès trouvés jusqu'ici y étaient tous, un par un et à l'usage | une passe construite |
| 2 | **le gris des quatre dérivés de l'accent** | 212 occurrences, visible sur les dix pages, et c'est la première chose qu'on voit | 40 lignes de CSS |
| 3 | **l'assistant d'INSTALLATION, 100 % français** | c'est le PREMIER écran de l'image, celui où il saisit sa base et ses clés — et il n'a aucun mécanisme de traduction | une demi-journée |
| 4 | **les ~33 chaînes françaises visibles** | elles sortent quand quelque chose rate, donc devant un client anglophone | une demi-journée |
| 5 | **le guide utilisateur** | c'est le document que le client va LIRE, et il décrit une app d'il y a trois mois | un chantier |
| 6 | **le code mort** (176 Ko de JS, 3 blueprints, 1 écran) | livré et servi publiquement ; pas de fuite, mais ça se voit | une demi-journée |
| 7 | **les drapeaux du cookie de session** | trois lignes ; le CSRF lui-même est un chantier à décider | 3 lignes + décision |

---

## Corrigé dans cette passe

### 1 · `/temps/api/tableau_de_bord` rendait 500 sur TOUTE installation neuve

La page Temps s'ouvrait vide chez le client, le jour 1.

Chaîne du défaut, reproduite par une vraie requête HTTP sur PostgreSQL 16 :
`get_calendar_params()` ne trouve aucune ligne `entreprise_settings` (base
neuve) → retombe sur `get_company_params()` → `SELECT … FROM company_params`
échoue, car **cette table n'a aucun modèle : rien ne la crée** → `except: pass`
→ sur PostgreSQL un ordre raté **avorte toute la transaction** → trois lignes
plus loin, `Activities.for_active_entity()` lève `InFailedSqlTransaction`.

⚠️ **Pourquoi aucun des 5176 tests ne pouvait le voir** : mesuré, sur SQLite la
session **survit** au SELECT raté. C'est la famille « ce que SQLite accepte et
que PostgreSQL refuse », et cette instance n'avait jamais été attrapée.

⚠️ **Et le défaut guérit tout seul** dès que quelqu'un enregistre le calendrier
de travail en page RH : il ne mord donc que le compte neuf, et disparaît avant
qu'on puisse le reproduire. C'est le pire profil pour un signalement client.

**Deux fausses pistes, mesurées avant d'arriver au correctif** — elles valent
d'être écrites, parce qu'elles ont l'air justes :

| tentative | ce qu'elle fait vraiment |
|---|---|
| `db.session.rollback()` dans le `except` | répare la transaction, mais `get_calendar_params` est appelé depuis des routes qui ÉCRIVENT : le rollback **jette le travail en attente de l'appelant** |
| `db.session.begin_nested()` (SAVEPOINT) | a l'air de régler ça, et ne le règle PAS : `begin_nested` **flushe** la session avant de poser le point de reprise, donc le travail en attente part DANS le savepoint et le rollback l'emporte. Mesuré : l'objet ajouté juste avant disparaissait de `session.new` |

**Retenu** : une **connexion dédiée** (`db.engine.connect()`), qui ne touche à
aucune transaction de la session — il n'y a rien à réparer et rien à perdre.
C'est le parti déjà pris pour OptiqPulse.

Vérifié après correctif : `/temps/api/tableau_de_bord` → **200** avec ses
données sur PostgreSQL ; sur SQLite, zéro savepoint émis, session utilisable,
travail en attente **préservé**.

### 2 · `/performance_perso/*` rendait 500 sur PostgreSQL, depuis toujours

`ensure_history_schema()` exécutait une DDL écrite en **SQLite pur** —
`id INTEGER PRIMARY KEY AUTOINCREMENT` et `datetime('now')` — que PostgreSQL
refuse (`syntax error at or near "AUTOINCREMENT"`). Elle est appelée en tête de
**six des sept routes** du blueprint. Donc cassé sur les deux instances en
ligne, aujourd'hui, et pour le client.

⚠️ `test_67_schema_postgres` compile le DDL des **modèles** avec le dialecte
PostgreSQL ; une chaîne brute dans une route lui échappe entièrement.

Gravité réelle **basse** : `performance_personnalisee.js` n'est chargé par
aucun gabarit — la fonctionnalité est injoignable depuis l'interface. Ce sont
donc des routes mortes qui rendaient 500, pas une fonctionnalité cassée. La DDL
branche désormais sur le dialecte ; le vrai sujet est au point 13.

### 3 · L'URL de la base ne nommait pas son pilote — la mine du 29/10, restée

`Code/app.py` ne faisait que normaliser `postgres://` → `postgresql://`. Or
`postgresql://` seul désignait **psycopg2** en SQLAlchemy 2.0 et désigne
**psycopg (v3)** depuis la **2.1**, qui n'est pas installé : chaque lecture
meurt sur « No module named 'psycopg' ». C'est l'incident qui a mis tout le hub
à terre sans qu'un seul commit ne change — et **le correctif n'avait été porté
que dans `hub/` et `pulse/`**.

⚠️ L'épinglage (`SQLAlchemy==2.0.52`) protège aujourd'hui. Mais
`distribution/docker-compose.yml` passe au client un `postgresql://` **nu** :
une reconstruction d'image avec une SQLAlchemy plus récente ferait exploser son
installation, et il n'y aurait rien à voir dans le code pour l'expliquer.

L'URL nomme désormais son pilote. Une URL qui en désigne déjà un (`+psycopg`,
`+asyncpg`) n'est pas réécrite.

### 4 · Les cliquets

`tests/test_165_base_neuve.py` — 19 cas. **Sept vérifiés rouges**, dont les
**trois** versions fautives de la sonde (le défaut d'origine, la réparation par
rollback, le SAVEPOINT).

⚠️ Un cliquet d'abord écrit ne gardait **rien** : il remettait le défaut
d'origine, invisible sur SQLite par construction. Le cas qui tient vraiment
affirme l'**invariant** — la sonde ouvre sa propre connexion — et c'est lui
qui tombe sur les trois.

Après correctifs : **104 routes GET balayées sur base PostgreSQL neuve, zéro
cassée**, 85 en 200.

---

## À décider — par ordre de ce qui menace la livraison

### 5 · Zéro protection CSRF dans toute l'application

Aucun `CSRFProtect`, aucun `csrf_token`, pas de `flask_wtf` : zéro occurrence
dans `Code/`.

### 6 · Le cookie de session ne porte aucun drapeau

Mesuré sur l'app : `SESSION_COOKIE_SECURE = False`, `SESSION_COOKIE_SAMESITE`
non posé, `HTTPONLY = True` (défaut Flask). Aucun de ces réglages n'apparaît
dans `Code/app.py` ni dans `gunicorn.conf.py`.

**Conséquence réelle, mesurée** : `SameSite` absent fait que le navigateur
retombe sur `Lax`, qui bloque les POST croisés. Et des 104 routes GET, seules
**trois** écrivent (toutes dans `gestion_rh`) — leurs commits ne sont que du
provisionnement idempotent (`assurer_roles_permanents`). **Il n'y a donc pas de
vecteur CSRF exploitable aujourd'hui.**

Ce qui reste : `SECURE = False` laisse le cookie partir en clair si le client
sert jamais du HTTP ; et surtout, « aucune protection CSRF, aucun SameSite »
est le genre de constat qui fait échouer une revue de sécurité chez un groupe
industriel. **Coût du correctif** : trois lignes de config pour les cookies ;
le CSRF lui-même est un chantier (tous les POST de l'app, et les ~60 appels
`fetch` du JS doivent porter le jeton).

### 7 · Le login n'est pas limité en débit

`mot_de_passe.debit_depasse` ne couvre que la demande de réinitialisation. Le
`/login` lui-même accepte un nombre illimité de tentatives.

### 8 · `FORWARDED_ALLOW_IPS` vaut `*` par défaut

Gunicorn croit l'`X-Forwarded-For` de n'importe qui. Derrière le proxy du
client c'est sans effet, mais une requête directe peut usurper son IP — et
c'est cette IP que la limitation de débit du reset compte.

### 9 · `/testpanel/**` n'a aucune authentification

Vérifié : son `before_request` ne fait que synchroniser. **Fermé chez le
client** (`TESTPANEL_ENABLED=0` baké dans le Dockerfile, blueprint non
enregistré — vérifié). **Ouvert sur `staging`**, qui est sur Internet, y
compris `POST /run/all` et `POST /admin/clone_entity`.

### 10 · Les quatre dérivés de l'accent rendent du GRIS sur toute l'application

Mesuré **dans le navigateur**, sur la page Activités : `--pg-accent` vaut bien
le violet `#7c3aed`, mais `--pg-accent-soft` se résout en
`color-mix(in srgb, #64748b 10%, #ffffff)` — le **gris par défaut**.

Cause : les quatre dérivés sont déclarés sur `:root` (`ui-theme.css` 60-63), où
`--pg-accent` vaut encore `#64748b` ; les dix classes `.page--*` ne
redéfinissent que `--pg-accent` et `-deep`. Une propriété personnalisée se
résout là où elle est **déclarée**.

Ampleur mesurée, et il faut dire ce que chaque chiffre vaut :

- **212 occurrences** de ces quatre jetons dans 8 feuilles de style
  (`activities_list.css` 48, `share.css` 39, `competences.css` 32,
  `gestion_outils.css` 32, `gestion_rh.css` 30, `time.css` 14, `ui-theme.css`
  14, `projection_metier.css` 3). C'est le compte exact de ce qui lit un gris
  en croyant lire la couleur de la page.
- **272 éléments** de la seule page Activités rendent exactement cette teinte
  grise. ⚠️ Ce compteur relève une COULEUR, pas un défaut : une part de ces
  éléments emploie peut-être un gris voulu qui se résout à la même valeur. Il
  donne l'ordre de grandeur, pas la liste des corrections.

L'écart se voit : `soft` devrait être un violet pâle
(`srgb 0.949 0.923 0.993`) et rend un gris neutre (`0.939 0.945 0.955`) ; la
bordure devrait être un violet franc (`0.856 0.784 0.980`) et rend
`0.830 0.847 0.873`. C'est surtout sur les bordures que ça se remarque.

**Coût du correctif** : quatre lignes dans chacune des dix classes `.page--*`.
À faire en regardant les dix pages, parce qu'il rend sa couleur à chacune d'un
coup.

### 11 · L'assistant d'INSTALLATION est en français, sans aucun moyen de traduire

C'est le **premier écran de l'image client** : celui où son informatique colle
la licence, saisit l'URL de sa base, sa clé OpenAI, ses identifiants de mail et
le compte administrateur. S'il ne le lit pas, l'installation n'a pas lieu.

Vérifié : `setup_wizard.html` fait **412 lignes, dont 257 dans un seul bloc
`<script>`** qui construit les cinq étapes — et il porte **zéro mécanisme de
traduction** : pas un `t()`, pas de catalogue, pas de `data-i18n`. Il est donc
100 % français par construction, quelle que soit la langue de la session.

Échantillon de ce que le client lira : « Assistant d'installation », « URL de
connexion PostgreSQL », « Clé API OpenAI », « Mot de passe d'application »,
« Adresse d'envoi », « L'application redémarre avec votre configuration. »

Même chose pour **`license_blocked.html`** — l'écran servi si la licence
expire : « Licence requise », « Contactez AFDEC pour obtenir ou renouveler
votre licence. »

⚠️ **Rectification de ma propre mesure** : j'avais d'abord compté 18 fragments
français dans ce gabarit par un détecteur qui lisait l'intérieur des `<script>`.
Le compte importe moins que le constat, qui est plus net que prévu : il n'y a
rien à compléter, il n'y a **rien du tout**.

### 12 · La dette de traduction du reste, mesurée — et plus petite qu'annoncé

`CLAUDE.md` annonçait « 191 chaînes françaises en dur dans 23 fichiers JS ».
Mesure détaillée : **236** chaînes dans 30 fichiers vivants, mais une fois
séparé ce qui se voit vraiment :

| | nombre |
|---|---|
| **certainement visibles** (`innerHTML`, `optiqAlert`, `title=`…) | **52** |
| dont dans du **code mort** (`activities_map.js`, ancrages absents) | −16 |
| → **visibles sur un écran vivant** | **≈ 33** |
| traces de mise au point (`console.log`) | 66 |
| à trancher (fragments HTML, options) | 101 |
| moitié française d'un catalogue bilingue **légitime** | 300 |

Les 33 se concentrent sur `performance.js` (7), `propose_aptitudes.js` (6),
`competencies.js` (5), `propose_savoirs.js` (5), `propose_savoirs_faires.js`
(4), `propose_softskills.js` (3) — ce sont presque tous des **messages
d'erreur** des chemins d'IA (« Impossible de récupérer les détails de
l'activité (voir console) », « Aucune proposition retournée »). Ils
s'affichent exactement quand quelque chose rate : chez un client sans clé IA
ou avec un réseau capricieux, donc souvent.

**Les écrans au repos sont propres** : 496 textes relevés sur la liste des
activités en anglais, attributs compris, **zéro fuite**.

### 13 · Du code mort que le client recevra

- **10 fichiers JS, 176 Ko**, chargés par aucun gabarit : `debug_decisions.js`
  (34 Ko), `test.js` (27 Ko), `synth_competences.js` (45 Ko),
  `plan_formation.js` (24 Ko), `performance_perso.js` (25 Ko),
  `performance_personnalisee.js`, `gestion_compte.js`,
  `global_users_summary.js`, `performance_history.js`, et **`main copy.js`**.
  Tous suivis par git, et `.dockerignore` n'exclut pas `static/` : **ils
  partent dans l'image et sont servis publiquement** sous `/static/js/`.
  ⚠️ **Vérifié : aucun ne contient de clé, de jeton, de mot de passe, d'adresse
  interne ni d'endpoint caché.** C'est de l'hygiène, pas une fuite — mais
  `debug_decisions.js` est le genre de nom de fichier qui invite à fouiller.
- **2 CSS morts** : `menu.css`, `softskills.css`.
- **3 blueprints enregistrés** dont aucun écran ne mène : `performance_perso`
  (7 routes), `competences_plan`, `plan_storage`.
- **`projection_metier` : un écran entier injoignable** — vérifié, aucun lien
  depuis la nav ni depuis aucun autre gabarit. Son gabarit et son JS sont
  largement en français — c'est une partie de la dette inventoriée par
  `test_78`. **Le traduire serait du
  travail perdu ; la question est de le supprimer ou de le rebrancher.**

### 14 · Cinq tables nommées en SQL brut sans modèle

`company_params` et `gestion_rh_params` sont **lues et jamais créées** (c'est
l'origine du point 1) ; `performance_personnalisee_historique`, `training_plan`
et `prerequis_comment` se créent à chaud depuis leur route. Pour mémoire,
`entreprise_settings` et `user_activity_plans` ont chacune coûté un 500 en
production avant d'obtenir leur modèle. Le cliquet du point 4 inventorie les
cinq : une sixième sera un choix écrit, pas un effet de bord.

### 15 · L'erreur `alembic_version` s'imprime à chaque démarrage

Sur une base PostgreSQL neuve, le journal du premier démarrage est propre
**sauf** `[DB] alembic_version: (psycopg2.errors.UndefinedTable) relation
"alembic_version" does not exist`, avec sa ligne SQL et son lien SQLAlchemy.
L'erreur est attrapée et sans conséquence, mais l'informatique du client lira
« psycopg2.errors » dans son journal du jour 1 et ouvrira un ticket.

### 16 · Le guide utilisateur est périmé

`docs/guide.html` décrit encore le partage de carto par **copie seule**,
l'ancien import IA global, et ignore les quatre paliers, les propositions, les
paliers de performance et la page Temps refondue. **C'est le document que le
client va lire.** Déjà noté priorité 1 dans `CLAUDE.md` ; la livraison le rend
urgent.

---

## Le point aveugle qui mériterait une passe à lui seul

Mesuré : la porte centrale (`Code/ecriture.py`) **refuse 102** routes
d'écriture à un compte `user` — elle fait son travail. Mais **99 autres la
traversent** (25 préfixes dans `TOUT_COMPTE`, 7 dans `SANS_COMPTE`), parce
qu'elles portent une règle plus fine : `/comptes/*`, `/gestion_rh/*`,
`/mastery/*`, `/paliers/*`, `/plan/*`, les routes d'IA, `/login`…

⚠️ **C'est exactement dans cette seconde moitié qu'étaient les trois trous
trouvés jusqu'ici**, un par un et à l'usage : le garant (05/11), `/tools/add`
(22/11), les dix routes d'IA (aujourd'hui). Chacun se présentait pareil — un
champion recevait `lecture_seule`, le motif réservé à `user`.

Je ne peux pas trancher ces 99 par un balayage : il faudrait les APPELER
vraiment, donc écrire en base. Les vérifier demande une passe construite,
route par route, avec un décor jetable — c'est le chantier que je
recommanderais avant la livraison, devant la traduction et devant le gris.

## Ce qui va bien — vérifié, pas supposé

- **Suite : 5176 passés, 1 sauté, aucun rouge** (avant correctifs).
- **Les 61 tables déclarées sont bien créées** sur une base PostgreSQL vierge
  par le démarrage normal. Aucune ne manque.
- **104 routes GET balayées** sur base neuve : zéro cassée après correctifs.
- **Les verrous de l'image client sont corrects** : `tests/` retiré,
  bytecode seul (`compileall -b` puis suppression des `.py`),
  `REQUIRE_LICENSE=1`, `TESTPANEL_ENABLED=0`.
- **Les migrations tournent UNE fois** : `preload_app = True` avec
  `Code.app:app` — elles s'exécutent dans le master avant le fork, pas une
  fois par worker. (Un doublon observé venait de mon propre script de mesure,
  pas de la production.)
- **Le SQL concaténé est sûr** : quatre sites, tous avec des listes blanches de
  littéraux et les valeurs utilisateur en paramètres liés. Aucune injection.
- **Aucun débordement horizontal** à 1600 px sur la page relue.
- Un `VARCHAR` trop court relevé — `users.status` (20) ne tient pas
  « Gestionnaire de compétences » (27) — mais la valeur canonique est
  désormais `champion` (8) et `update_user` tronque : sans effet sur une
  installation neuve.

## Ce que je n'ai PAS vérifié

À dire clairement, pour que personne ne le croie couvert :

- **Les parcours d'ÉCRITURE écran par écran**, et les 99 routes ci-dessus.
  J'ai balayé les 104 routes GET ; les POST/PUT/DELETE ne sont couverts que
  par la suite, qui tourne sur SQLite.
- **L'éditeur OptiqCarto** (`static/optiqcarto/editor.js`), le plus gros
  morceau de JS de l'application, n'a pas été exercé.
- **Le guide utilisateur** et les captures.
- **Les deux instances en ligne** : tout a été mesuré en local et sur un
  PostgreSQL jetable.
- Un parcours complet dans les **deux langues** sur chacune des dix pages ;
  seule la page Activités a été relue au navigateur dans cette passe.
