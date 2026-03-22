#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="$ROOT/poc-brainstorm-ui/public/raw.json"
OVR="$ROOT/poc-brainstorm-ui/public/overlay.json"
cd "$ROOT/packages/raw-indexer"
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
else
  PY=python3
fi
"$PY" -m raw_indexer orphans "$RAW" "$OVR"
