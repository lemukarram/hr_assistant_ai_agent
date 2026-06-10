#!/usr/bin/env bash
# scripts/run_tests.sh
# Run the test suite in tiers. Usage: ./scripts/run_tests.sh [unit|integration|e2e|all]

set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'

TIER="${1:-unit}"
BACKEND_DIR="backend"

run_unit() {
  echo -e "${GREEN}▶ Running unit tests...${NC}"
  cd "$BACKEND_DIR"
  python -m pytest tests/unit/ -v --tb=short -m "not slow"
  cd ..
}

run_integration() {
  echo -e "${GREEN}▶ Running integration tests (requires DB)...${NC}"
  cd "$BACKEND_DIR"
  python -m pytest tests/integration/ -v --tb=short
  cd ..
}

run_e2e() {
  echo -e "${GREEN}▶ Running end-to-end tests (requires full stack)...${NC}"
  echo "Ensure docker-compose up is running first."
  cd "$BACKEND_DIR"
  python -m pytest tests/e2e/ -v --tb=short -s --timeout=120
  cd ..
}

run_eval() {
  echo -e "${GREEN}▶ Running RAG evaluation...${NC}"
  python evaluation/run_eval.py
}

case "$TIER" in
  unit)        run_unit ;;
  integration) run_integration ;;
  e2e)         run_e2e ;;
  eval)        run_eval ;;
  all)         run_unit; run_integration; run_e2e; run_eval ;;
  *)           echo "Usage: $0 [unit|integration|e2e|eval|all]"; exit 1 ;;
esac

echo -e "${GREEN}✓ Done.${NC}"
