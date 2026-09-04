#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Répétition de l'image applicative SANS Docker.
#
# Depuis que le hub fait rejouer la suite SUR l'instance (module Panel), le
# code tourne dans un arbre que personne n'exerce en local : exclusions du
# .dockerignore + purge bytecode (`compileall -b` puis suppression des .py,
# tests/ épargné). Un test qui lit un fichier source y échoue alors qu'il passe
# ici — c'est exactement ce qui est arrivé à tests/test_61_pulse.py.
#
# Usage :  bash tools/repet_image.sh  [chemin/vers/le/python]
# ─────────────────────────────────────────────────────────────────────────────
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMG="${IMG:-/tmp/repet_image}"
# Le venv vit à la racine du dépôt ; depuis un worktree (.claude/worktrees/x)
# il faut remonter. On essaie les candidats plausibles avant python3 système.
PY="${1:-}"
for c in "$PY" "$SRC/.venv/bin/python" \
         "$SRC/../../../.venv/bin/python" "$SRC/../../.venv/bin/python"; do
  if [ -n "$c" ] && [ -x "$c" ]; then PY="$c"; break; fi
done
[ -n "$PY" ] && [ -x "$PY" ] || PY="$(command -v python3)"

echo "source : $SRC"
echo "python : $PY"

rm -rf "$IMG"; mkdir -p "$IMG"

# Contexte de build : les exclusions du .dockerignore qui changent le résultat.
rsync -a --quiet \
  --exclude '.git' --exclude '.claude' --exclude '__pycache__' --exclude '*.pyc' \
  --exclude 'docs/' --exclude 'doc/' --exclude 'Archives/' --exclude 'backup/' \
  --exclude 'tools/' --exclude 'distribution/' --exclude 'uploads/' \
  --exclude '*.vsdx' --exclude '*.db' --exclude 'instance' --exclude '.venv' \
  --exclude 'hub/_docs' \
  "$SRC/" "$IMG/"

# WITH_TESTS=1 (nos instances) : tests/ reste, avec ses SOURCES. Puis la purge
# bytecode du Dockerfile, à l'identique.
"$PY" -m compileall -b -q -x '(^|/)tests/' "$IMG" > /dev/null 2>&1
find "$IMG" -name "*.py" ! -path "$IMG/gunicorn.conf.py" ! -path "$IMG/tests/*" -delete
find "$IMG" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

echo "sources .py hors tests/ : $(find "$IMG" -name '*.py' -not -path "$IMG/tests/*" | wc -l) (attendu : 1, gunicorn.conf.py)"
echo "fichiers de tests       : $(ls "$IMG"/tests/test_*.py 2>/dev/null | wc -l)"

cd "$IMG"
TESTPANEL_ENABLED=1 REQUIRE_LICENSE=0 "$PY" -m pytest tests/ -q --no-header \
  -p no:cacheprovider | tail -20
