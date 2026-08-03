#!/usr/bin/env bash
set -euo pipefail

VENV="${VENV:-/Users/sgawde/work/py-shared-env/dev}"
PYTHON="$VENV/bin/python3"
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
STATUS_DIR="$PROJECT_ROOT/webapp/.run_status"

PHASES=(
  phase1-baseline
  phase2-checklist
  phase3-context
  phase4-assistant
  phase6-history
  phase7-reference-rag
)

mkdir -p "$STATUS_DIR"

for phase in "${PHASES[@]}"; do
  status_file="$STATUS_DIR/${phase}.json"
  echo ""
  echo "========================================"
  echo "  Starting $phase"
  echo "========================================"
  rm -f "$status_file"

  "$PYTHON" "$PROJECT_ROOT/$phase/src/main.py" \
    --status-file "$status_file" \
    --provider local \
    --judge-provider local \
    --regenerate

  echo "  $phase finished"
done

echo ""
echo "========================================"
echo "  All 6 pipelines complete"
echo "========================================"
