#!/usr/bin/env bash
# Répétition générale de l'installation client OptiqFluent (sans Docker).
#
# Rejoue le parcours d'INSTALL.md de bout en bout, avec les mêmes mécanismes
# que l'image livrée :
#   1. clés + licence de TEST (clé de prompts embarquée DANS la licence)
#   2. bundle de prompts chiffré
#   3. « image » = arbre bytecode-only (mêmes étapes que le Dockerfile)
#   4. PostgreSQL 16 local VIERGE (comme le postgres du docker-compose client)
#   5. démarrage gunicorn avec un .env de client
#   6. vérifications : tables auto-créées, bootstrap admin, login, /license,
#      prompts déchiffrés via la licence (sans PROMPTS_KEY dans l'env)
#
# Usage : bash tools/test_install.sh [--keep]
# Tout vit dans un dossier temporaire ; les clés du dépôt ne sont pas touchées.

set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
WS=$(mktemp -d /tmp/optiqfluent-install-XXXX)
chmod 755 "$WS"   # l'utilisateur postgres doit pouvoir traverser le workspace
PGBIN=$(ls -d /usr/lib/postgresql/*/bin | tail -1)
PGPORT=54329
APPPORT=8087
KEEP="${1:-}"

cleanup() {
  [ -f "$WS/gunicorn.pid" ] && kill "$(cat "$WS/gunicorn.pid")" 2>/dev/null || true
  su pgtest -c "$PGBIN/pg_ctl -D $WS/pgdata stop -m fast" >/dev/null 2>&1 || true
  if [ "$KEEP" != "--keep" ]; then rm -rf "$WS"; else echo "Workspace conservé : $WS"; fi
}
trap cleanup EXIT

PASS=0; FAIL=0
check() { # check "libellé" condition
  if eval "$2"; then echo "  ✅ $1"; PASS=$((PASS+1)); else echo "  ❌ $1"; FAIL=$((FAIL+1)); fi
}

echo "== 1. Clés + licence de test (avec prompts_key embarquée) =="
python3 - "$WS" <<'EOF'
import base64, json, os, sys
from datetime import date, timedelta
sys.path.insert(0, os.getcwd())
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet
from Code.licensing import canonical_payload_bytes

ws = sys.argv[1]
os.makedirs(f"{ws}/license", exist_ok=True)

key = Ed25519PrivateKey.generate()
open(f"{ws}/license_pubkey.pem", "wb").write(key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo))

prompts_key = Fernet.generate_key().decode()
open(f"{ws}/prompts_key.txt", "w").write(prompts_key)

payload = {"product": "OptiqFluent", "licensee": "Client Test Installation",
           "issued_at": date.today().isoformat(),
           "expires_at": (date.today() + timedelta(days=31)).isoformat(),
           "prompts_key": prompts_key}
doc = {"payload": payload,
       "signature": base64.b64encode(key.sign(canonical_payload_bytes(payload))).decode()}
open(f"{ws}/license/optiqfluent.lic", "w").write(json.dumps(doc))

from Code.prompts.catalog import PROMPTS
data = json.dumps(PROMPTS, ensure_ascii=False).encode()
open(f"{ws}/prompts.enc", "wb").write(Fernet(prompts_key.encode()).encrypt(data))
print(f"licence 31j + bundle chiffré ({len(PROMPTS)} prompts) prêts")
EOF

echo "== 2. Construction de l'« image » (bytecode-only, comme le Dockerfile) =="
IMG="$WS/app"
mkdir -p "$IMG"
cp -r Code static migrations gunicorn.conf.py startup.sh "$IMG/"
rm -rf "$IMG/Code/instance" "$IMG/Code/prompts/catalog.py" "$IMG"/Code/*.vsdx
find "$IMG" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
cp "$WS/license_pubkey.pem" "$IMG/Code/license_pubkey.pem"
cp "$WS/prompts.enc" "$IMG/Code/prompts/prompts.enc"
python3 -m compileall -b -q "$IMG"
find "$IMG" -name "*.py" ! -path "$IMG/gunicorn.conf.py" -delete
echo "  sources .py restantes : $(find "$IMG" -name '*.py' | wc -l) (gunicorn.conf.py)"

echo "== 3. PostgreSQL 16 vierge (équivalent du postgres du docker-compose) =="
id pgtest >/dev/null 2>&1 || useradd -m pgtest
mkdir -p "$WS/pgdata" && chown pgtest "$WS/pgdata"
su pgtest -c "$PGBIN/initdb -D $WS/pgdata -A trust" >/dev/null
su pgtest -c "$PGBIN/pg_ctl -D $WS/pgdata -o '-p $PGPORT -k /tmp' -l $WS/pgdata/pg.log start -w" >/dev/null
su pgtest -c "$PGBIN/createdb -p $PGPORT -h /tmp optiqfluent"
echo "  postgres démarré sur :$PGPORT, base optiqfluent vide"

echo "== 4. Démarrage de l'app (config .env d'un client) =="
cd "$IMG"
env -i PATH="$PATH" HOME="$HOME" PYTHONUNBUFFERED=1 \
  DATABASE_URL="postgresql://pgtest@127.0.0.1:$PGPORT/optiqfluent" \
  SECRET_KEY="$(openssl rand -hex 32)" \
  ADMIN_EMAIL="admin@clienttest.fr" ADMIN_PASSWORD="MotDePasseInitial!" \
  REQUIRE_LICENSE=1 LICENSE_PATH="$WS/license/optiqfluent.lic" \
  PORT=$APPPORT WEB_CONCURRENCY=1 \
  python3 -m gunicorn -c gunicorn.conf.py Code.app:app \
  --pid "$WS/gunicorn.pid" --daemon --log-file "$WS/gunicorn.log" --capture-output
for i in $(seq 1 30); do
  curl -fs "http://127.0.0.1:$APPPORT/healthz" >/dev/null 2>&1 && break; sleep 1
done

echo "== 5. Vérifications =="
B="http://127.0.0.1:$APPPORT"
J="$WS/cookies.txt"
check "healthz répond" \
  '[ "$(curl -s -o /dev/null -w "%{http_code}" $B/healthz)" = "200" ]'
check "tables créées automatiquement (log [DB])" \
  'grep -q "Tables vérifiées/créées" "$WS/gunicorn.log"'
check "bootstrap admin exécuté" \
  'grep -q "Compte administrateur créé" "$WS/gunicorn.log"'
check "licence valide (log [LICENSE])" \
  'grep -q "Licence valide — Client Test Installation" "$WS/gunicorn.log"'
check "/license expose l'état (200 + licencié)" \
  'curl -s $B/license | grep -q "Client Test Installation"'
check "/ redirige vers le login" \
  '[ "$(curl -s -o /dev/null -w "%{http_code}" $B/)" = "302" ]'
check "page de connexion marquée OptiqFluent" \
  'curl -sL $B/login | grep -q OptiqFluent'
check "login admin OK (redirection carte des activités)" \
  'curl -s -c "$J" -o /dev/null -w "%{redirect_url}" -d "email=admin@clienttest.fr&password=MotDePasseInitial!" $B/login | grep -q activities'
# Sans clé OpenAI : 500 « Erreur API OpenAI » = prompts chargés depuis la
# licence puis appel OpenAI tenté ; 503 « prompts non chargés » = échec clé.
check "prompts IA déchiffrés via la licence (chatbot ≠ 503)" \
  '[ "$(curl -s -b "$J" -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "{\"message\":\"test\",\"activity\":{},\"history\":[]}" $B/api/chatbot/chat)" != "503" ]'

echo
echo "===== RÉSULTAT : $PASS OK, $FAIL échec(s) ====="
[ $FAIL -eq 0 ]
