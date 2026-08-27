#!/usr/bin/env bash
# Déploiement OptiqFluent (branche optiqfluent-staging) sur Cloud Run.
#
# Remplace devoptiq-staging-mv par un service renommé optiqfluent-staging :
# Cloud Run ne permet PAS de renommer un service — on en crée un nouveau en
# recopiant les variables d'environnement de l'ancien, puis on supprime
# l'ancien (sur confirmation).
#
# À lancer depuis la racine du dépôt, branche optiqfluent-staging :
#   bash tools/deploy/deploy_cloudrun.sh
#
# Prérequis : gcloud authentifié (gcloud auth login) + projet actif
# (gcloud config set project <projet>), et la clé de prompts disponible
# (tools/prompts/prompts_key.txt, généré par tools/prompts/encrypt_prompts.py).

set -euo pipefail

OLD_SERVICE="devoptiq-staging-mv"
NEW_SERVICE="optiqfluent-staging"
REGION="europe-west1"

echo "== Vérifications préalables =="
command -v gcloud >/dev/null || { echo "gcloud introuvable"; exit 1; }
test -f Dockerfile || { echo "À lancer depuis la racine du dépôt"; exit 1; }
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ "$BRANCH" = "optiqfluent-staging" ] || echo "⚠ Branche courante : $BRANCH (attendu : optiqfluent-staging)"

echo "== Bundle de prompts chiffré =="
python3 tools/prompts/encrypt_prompts.py > /dev/null
PROMPTS_KEY=$(cat tools/prompts/prompts_key.txt)
echo "prompts.enc prêt"

echo "== Récupération des variables d'env de $OLD_SERVICE =="
# Reprises telles quelles sur le nouveau service (séparateur ## : les valeurs
# type DATABASE_URL contiennent virgules ET arobases)
OLD_ENV=$(gcloud run services describe "$OLD_SERVICE" --region "$REGION" --format=json 2>/dev/null | \
  python3 -c "
import sys, json
svc = json.load(sys.stdin)
envs = svc['spec']['template']['spec']['containers'][0].get('env', [])
skip = {'REQUIRE_LICENSE', 'PROMPTS_KEY', 'TESTPANEL_ENABLED'}
print('##'.join(f\"{e['name']}={e['value']}\" for e in envs
               if e['name'] not in skip and 'value' in e))
") || OLD_ENV=""
if [ -n "$OLD_ENV" ]; then
  echo "Variables reprises : $(echo "$OLD_ENV" | sed 's/##/\n/g' | cut -d= -f1 | tr '\n' ' ')"
else
  echo "⚠ Aucune variable récupérée de $OLD_SERVICE — pense à définir DATABASE_URL,"
  echo "  SECRET_KEY, OPENAI_API_KEY, MAIL_* à la main (--set-env-vars ou console)."
fi

NEW_ENV="REQUIRE_LICENSE=0##TESTPANEL_ENABLED=1##PROMPTS_KEY=${PROMPTS_KEY}"
[ -n "$OLD_ENV" ] && NEW_ENV="${OLD_ENV}##${NEW_ENV}"

# Build explicite puis déploiement de l'image : le raccourci
# `gcloud run deploy --source` échoue avec « Container import failed »
# (constaté en conditions réelles) — la voie en deux temps est fiable.
IMAGE="${REGION}-docker.pkg.dev/$(gcloud config get-value project)/cloud-run-source-deploy/optiqfluent:$(date +%Y%m%d-%H%M%S)"
echo "== Build Cloud Build → $IMAGE =="
gcloud builds submit --region "$REGION" --tag "$IMAGE" .

echo "== Déploiement de $NEW_SERVICE =="
gcloud run deploy "$NEW_SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --set-env-vars "^##^${NEW_ENV}"  # ## : jamais dans une valeur (contrairement à @, présent dans DATABASE_URL)

URL=$(gcloud run services describe "$NEW_SERVICE" --region "$REGION" --format='value(status.url)')
echo "== Vérification =="
curl -fsS "$URL/healthz" && echo " ← healthz OK sur $URL"

echo
read -r -p "Supprimer l'ancien service $OLD_SERVICE ? [y/N] " CONFIRM
if [ "${CONFIRM:-n}" = "y" ]; then
  gcloud run services delete "$OLD_SERVICE" --region "$REGION" --quiet
  echo "$OLD_SERVICE supprimé — le service est désormais $NEW_SERVICE ($URL)"
else
  echo "Ancien service conservé. Supprime-le plus tard avec :"
  echo "  gcloud run services delete $OLD_SERVICE --region $REGION"
fi
