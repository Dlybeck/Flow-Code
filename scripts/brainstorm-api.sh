#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi
export BRAINSTORM_PUBLIC_DIR="${BRAINSTORM_PUBLIC_DIR:-$ROOT/poc-brainstorm-ui/public}"
export BRAINSTORM_GOLDEN_REPO="${BRAINSTORM_GOLDEN_REPO:-$ROOT/fixtures/golden-fastapi}"
cd "$ROOT/packages/raw-indexer"
if [[ -x .venv/bin/uvicorn ]]; then
  exec .venv/bin/uvicorn raw_indexer.api:app --host 127.0.0.1 --port 8000 "$@"
elif command -v uvicorn &>/dev/null; then
  exec uvicorn raw_indexer.api:app --host 127.0.0.1 --port 8000 "$@"
else
  echo "Install API deps: cd packages/raw-indexer && pip install -e '.[api]'" >&2
  exit 1
fi
