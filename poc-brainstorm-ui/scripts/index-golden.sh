#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RI="$ROOT/packages/raw-indexer"
OUT="$ROOT/poc-brainstorm-ui/public/raw.json"
FLOW="$ROOT/poc-brainstorm-ui/public/flow.json"
cd "$RI"
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
else
  PY=python3
fi
"$PY" -m raw_indexer index "$ROOT/fixtures/golden-fastapi" -o "$OUT"
"$PY" -m raw_indexer execution-ir "$ROOT/fixtures/golden-fastapi" -o "$FLOW"
echo "Wrote $OUT"
echo "Wrote $FLOW"
