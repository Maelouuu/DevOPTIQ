#!/bin/bash
# run_tests.sh — Lance la suite de tests DevOPTIQ et génère les rapports
# Usage :
#   ./run_tests.sh                  → tous les tests
#   ./run_tests.sh -k activities    → filtre par nom
#   ./run_tests.sh -m tasks         → filtre par marqueur

set -e

VENV=".venv/bin"
PYTEST="${VENV}/pytest"
PYTHON="${VENV}/python"

echo "=========================================="
echo "  DevOPTIQ — Suite de tests automatisés"
echo "=========================================="

# Lancer pytest avec sorties JUnit XML et HTML (pytest-html)
${PYTEST} tests/ \
  --junitxml=tests/results.xml \
  --html=tests/report_pytest.html \
  --self-contained-html \
  -v \
  "$@" || true   # ne pas bloquer si des tests échouent

echo ""
echo "------------------------------------------"
echo "  Génération du rapport visuel..."
echo "------------------------------------------"

${PYTHON} tests/generate_report.py tests/results.xml tests/report_visuel.html

echo ""
echo "=========================================="
echo "  Rapports disponibles :"
echo "  → tests/report_visuel.html  (rapport par page)"
echo "  → tests/report_pytest.html  (rapport pytest détaillé)"
echo "=========================================="
