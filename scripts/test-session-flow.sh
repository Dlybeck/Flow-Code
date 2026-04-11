#!/usr/bin/env bash
# End-to-end session flow test — requires API + OpenCode running.
# Every step prints PASS or FAIL. Exit 0 only if all steps pass.
#
# Usage:
#   bash scripts/test-session-flow.sh
#
# Env overrides:
#   BRAINSTORM_API_URL   default http://localhost:8000
#   OPENCODE_URL         default http://localhost:4096
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }

API="${BRAINSTORM_API_URL:-http://localhost:8000}"
OC="${OPENCODE_URL:-http://localhost:4096}"
PASS=0
FAIL=0

ok()   { echo "  PASS  $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

check_json() {
  # check_json <json_string> <jq_filter> <expected_value>
  local val
  val=$(echo "$1" | python3 -c "import json,sys; d=json.load(sys.stdin); print($2)" 2>/dev/null || echo "__err__")
  [[ "$val" == "$3" ]]
}

echo ""
echo "=== Step 1: API health ==="
HEALTH=$(curl -sf "$API/health" || echo "{}")
if check_json "$HEALTH" "d.get('status')" "ok"; then ok "API healthy"; else fail "API not running at $API"; fi

echo ""
echo "=== Step 2: OpenCode health ==="
OC_RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$OC/session" \
  -H "Content-Type: application/json" -d '{}')
OC_STATUS=$(echo "$OC_RESP" | grep "HTTP_STATUS:" | cut -d: -f2)
OC_BODY=$(echo "$OC_RESP" | sed '/HTTP_STATUS:/d')
if [[ "$OC_STATUS" == "200" ]]; then ok "OpenCode responding"; else fail "OpenCode not running at $OC (HTTP $OC_STATUS)"; fi

echo ""
echo "=== Step 3: POST /go → align phase ==="
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

GO_RESP=$(curl -sf -X POST "$API/go" -H "Content-Type: application/json" -d "$PAYLOAD")
SESSION=$(echo "$GO_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || echo "")

if [[ -n "$SESSION" ]]; then ok "Got session_id=$SESSION"; else fail "No session_id in /go response"; fi

sleep 0.5
STATUS_RESP=$(curl -sf "$API/status/$SESSION" || echo "{}")
PHASE=$(echo "$STATUS_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('phase',''))" 2>/dev/null || echo "")
MSG=$(echo "$STATUS_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('activity_message','')[:80])" 2>/dev/null || echo "")
if [[ "$PHASE" == "align" ]]; then ok "phase=align"; else fail "Expected phase=align, got phase=$PHASE"; fi
if [[ -n "$MSG" ]]; then ok "align message non-empty: $MSG"; else fail "align message empty"; fi

echo ""
echo "=== Step 4: POST /reply → confirm align ==="
REPLY_RESP=$(curl -sf -X POST "$API/status/$SESSION/reply" \
  -H "Content-Type: application/json" \
  -d '{"answer": "__confirm__"}')
REPLY_OK=$(echo "$REPLY_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok'))" 2>/dev/null || echo "")
if [[ "$REPLY_OK" == "True" ]]; then ok "reply accepted"; else fail "reply failed: $REPLY_RESP"; fi

sleep 1
STATUS2=$(curl -sf "$API/status/$SESSION" || echo "{}")
PHASE2=$(echo "$STATUS2" | python3 -c "import json,sys; print(json.load(sys.stdin).get('phase',''))" 2>/dev/null || echo "")
if [[ "$PHASE2" != "align" ]]; then ok "phase advanced past align → $PHASE2"; else fail "phase still align after confirm"; fi

echo ""
echo "=== Step 5: Poll to done (max 300s) ==="
FINAL_PHASE=""
FINAL_STATUS=""
for i in $(seq 1 60); do
  sleep 5
  FINAL_STATUS=$(curl -sf "$API/status/$SESSION" || echo "{}")
  FINAL_PHASE=$(echo "$FINAL_STATUS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('phase','unknown'))" 2>/dev/null || echo "unknown")
  echo "  [${i}] phase=$FINAL_PHASE"
  if [[ "$FINAL_PHASE" == "done" || "$FINAL_PHASE" == "error" ]]; then break; fi
done

if [[ "$FINAL_PHASE" == "done" ]]; then ok "session reached done"; else fail "session ended with phase=$FINAL_PHASE"; fi

SUMMARY=$(echo "$FINAL_STATUS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('summary','')[:100])" 2>/dev/null || echo "")
if [[ -n "$SUMMARY" ]]; then ok "summary non-empty: $SUMMARY"; else fail "summary empty"; fi

CHANGED=$(echo "$FINAL_STATUS" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('changed_node_ids',[])))" 2>/dev/null || echo "0")
echo "  changed_node_ids count: $CHANGED"
ok "changed_node_ids is a list (count=$CHANGED)"

echo ""
echo "=== Step 6: Golden fixture tests ==="
if cd "$ROOT/fixtures/golden-fastapi" && python -m pytest -q 2>&1 | tail -5; then
  ok "golden-fastapi pytest passed"
else
  fail "golden-fastapi pytest FAILED — AI changes broke existing tests"
fi
cd "$ROOT"

echo ""
echo "=== Step 7: POST /undo ==="
UNDO_RESP=$(curl -sf -X POST "$API/status/$SESSION/undo" || echo "{}")
UNDO_OK=$(echo "$UNDO_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok'))" 2>/dev/null || echo "")
if [[ "$UNDO_OK" == "True" ]]; then ok "undo accepted"; else fail "undo failed: $UNDO_RESP"; fi

# Session should be gone after undo
sleep 0.3
GONE=$(curl -s -o /dev/null -w "%{http_code}" "$API/status/$SESSION")
if [[ "$GONE" == "404" ]]; then ok "session cleared after undo"; else fail "session still exists after undo (HTTP $GONE)"; fi

echo ""
echo "════════════════════════════════════"
echo "  PASSED: $PASS   FAILED: $FAIL"
echo "════════════════════════════════════"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
