#!/usr/bin/env bash
# Integration test script for the OpenCode session flow.
# Claude runs this via Bash tool to diagnose issues without user involvement.
#
# Usage:
#   bash scripts/dev-test.sh
#
# Requires: API running on :8000, OpenCode running on $OPENCODE_URL (:4096 default)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }

API="${BRAINSTORM_API_URL:-http://localhost:8000}"
OC="${OPENCODE_URL:-http://localhost:4096}"

echo "=== Checking API ($API) ==="
curl -sf "$API/health" && echo " OK" || { echo "FAIL — API not running at $API"; exit 1; }

echo ""
echo "=== Checking OpenCode ($OC) ==="
OC_RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$OC/session" \
  -H "Content-Type: application/json" -d '{}')
OC_BODY=$(echo "$OC_RESP" | sed '/HTTP_STATUS:/d')
OC_STATUS=$(echo "$OC_RESP" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "HTTP $OC_STATUS: $OC_BODY"
if [[ "$OC_STATUS" != "200" ]]; then
  echo "FAIL — OpenCode session creation failed"
  exit 1
fi
OC_PROBE_ID=$(echo "$OC_BODY" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
echo "OpenCode probe session: $OC_PROBE_ID"

echo ""
echo "=== Sampling OpenCode SSE for 3s ==="
timeout 3 curl -sN "$OC/global/event" 2>/dev/null | head -40 || true

echo ""
echo "=== Firing test session via POST /go ==="
NODE_ID=$(python3 -c "
import json
try:
    doc = json.load(open('$ROOT/poc-brainstorm-ui/public/flow.json'))
    eps = doc.get('entrypoints', [])
    print(eps[0] if eps else '')
except Exception:
    print('')
" 2>/dev/null || echo "")

PAYLOAD=$(python3 -c "
import json
nid = '$NODE_ID'
print(json.dumps({
  'brief': 'Make the greeting handle empty strings gracefully.',
  'node_ids': [nid] if nid else [],
  'node_labels': ['greeting_for'] if nid else [],
}))")

echo "Payload: $PAYLOAD"
GO_RESP=$(curl -sf -X POST "$API/go" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")
echo "Response: $GO_RESP"
SESSION=$(echo "$GO_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['session_id'])")
echo "Session ID: $SESSION"

echo ""
echo "=== Polling /debug/sessions (up to 60s) ==="
PHASE=""
for i in $(seq 1 90); do
  sleep 5
  STATE=$(curl -sf "$API/debug/sessions" | python3 -c "
import json,sys
d = json.load(sys.stdin)
s = d.get('$SESSION', {})
print(json.dumps(s, indent=2))
" 2>/dev/null || echo "{}")
  PHASE=$(echo "$STATE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('phase','unknown'))" 2>/dev/null || echo "unknown")
  echo "[$i] phase=$PHASE"
  if [[ "$PHASE" == "done" || "$PHASE" == "error" ]]; then
    echo ""
    echo "=== Final session state ==="
    echo "$STATE"
    break
  fi
done

echo ""
echo "=== Result: $PHASE ==="
[[ "$PHASE" == "done" ]] && exit 0 || exit 1
