# OptiqPulse — suivi d'audience DevOPTIQ / OptiqFluent

Dashboard **privé** (hors app) qui suit l'usage réel des instances : connectés
en direct, pics de simultanés, moyennes, pages visitées, temps passé par page,
parcours détaillé par utilisateur.

## Comment ça marche

1. **Chaque instance d'app** journalise sa télémétrie dans SA base Neon via
   `Code/routes/pulse_track.py` (tables `usage_events` + `usage_beats`,
   créées au boot par `create_all`) et `static/js/pulse.js` (battement de
   présence ~60 s, onglet visible uniquement).
2. **Ce service** (déployé à part sur Cloud Run, service `optiq-pulse`) se
   branche en **lecture seule** sur les bases des instances listées dans
   `PULSE_DBS` et agrège tout côté serveur.

L'app elle-même n'affiche jamais rien : aucune fuite de données d'usage vers
les utilisateurs.

## Accès

Un seul compte (personne d'autre ne doit y avoir accès) :
identifiant `Mael_Girardin` — mot de passe par défaut `testtest`.
**Changer le mot de passe** : poser la variable `PULSE_PASSWORD` sur le
service Cloud Run (ou le secret GitHub `PULSE_PASSWORD`, repris à chaque
déploiement). Anti-force-brute : 8 essais / 15 min par IP.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `PULSE_DBS` | JSON `[{"name": "Pilote ARaymond", "url": "postgresql://…"}, …]` |
| `PULSE_DBS_B64` | même JSON en base64 (utilisé par le workflow CI — évite l'escaping gcloud) |
| `PULSE_SECRET_KEY` | clé de session Flask (généré par le workflow si absent) |
| `PULSE_USER` | identifiant (défaut `Mael_Girardin`) |
| `PULSE_PASSWORD` | mot de passe en clair (prioritaire sur le hash) |
| `PULSE_PASSWORD_HASH` | hash werkzeug pbkdf2 (défaut baké = `testtest`) |
| `PULSE_INSECURE_COOKIE` | `1` = cookies non-secure (tests locaux uniquement) |

## Ajouter une instance à suivre

Deux options :
- **Durable (recommandé)** : secret GitHub `PULSE_EXTRA_DBS` = JSON
  `[{"name": "Staging", "url": "postgresql://…"}]` — fusionné avec la base
  pilote à chaque déploiement (`.github/workflows/deploy-pulse.yml`).
- **Ponctuel** : éditer la variable `PULSE_DBS_B64` du service dans la
  console Cloud Run (écrasée au prochain déploiement du workflow).

L'instance doit avoir le code de télémétrie (tables créées au boot). Une base
sans les tables apparaît « injoignable » dans le bandeau d'erreur du
dashboard, sans casser le reste.

## Rétention (côté app)

Battements : 90 jours · événements : 400 jours (purge au boot de l'app).

## Lancer en local

```bash
cd pulse
pip install -r requirements.txt
PULSE_INSECURE_COOKIE=1 PULSE_DBS='[{"name":"Local","url":"sqlite:///../Code/instance/optiq.db"}]' python app.py
```
