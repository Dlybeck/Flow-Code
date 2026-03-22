#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RI="$ROOT/packages/raw-indexer"
OUT="$ROOT/poc-brainstorm-ui/public/raw.json"
cd "$RI"
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m raw_indexer index "$ROOT/fixtures/golden-fastapi" -o "$OUT"
else
  python3 -m raw_indexer index "$ROOT/fixtures/golden-fastapi" -o "$OUT"
fi
echo "Wrote $OUT"
