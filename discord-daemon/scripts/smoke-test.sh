#!/usr/bin/env bash
# End-to-end smoke test for discord-daemon — no Discord, no VPS.
# Boots daemon in MOCK_DISCORD mode, exercises the full HTTP+SSE surface,
# asserts the registry/eviction/control flows behave.

set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-7799}"  # avoid clashing with a real daemon
TOKEN="smoke-$(openssl rand -hex 8)"
SID="smoke-$(date +%s)-$$"
URL="http://127.0.0.1:${PORT}"
TMP=$(mktemp -d)
trap 'cleanup' EXIT

cleanup() {
  if [ -n "${DAEMON_PID:-}" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
    kill "$DAEMON_PID" 2>/dev/null || true
    wait "$DAEMON_PID" 2>/dev/null || true
  fi
  if [ -n "${SSE_PID:-}" ] && kill -0 "$SSE_PID" 2>/dev/null; then
    kill "$SSE_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}

require_jq() { command -v jq >/dev/null || { echo "need jq"; exit 1; }; }
require_jq

# Use a private state dir so we don't touch the user's real access.json
export DISCORD_STATE_DIR="$TMP/state"
mkdir -p "$DISCORD_STATE_DIR"
echo '{"dmPolicy":"allowlist","allowFrom":[],"groups":{},"pending":{}}' > "$DISCORD_STATE_DIR/access.json"

DAEMON_DISCORD_MOCK=1 \
DAEMON_TOKEN="$TOKEN" \
DAEMON_BIND_HOST=127.0.0.1 \
DAEMON_BIND_PORT="$PORT" \
  bun run src/server.ts >"$TMP/daemon.log" 2>&1 &
DAEMON_PID=$!

# Wait for HTTP to be reachable (no Discord login dependency).
for i in {1..40}; do
  if curl -sf -H "x-daemon-token: $TOKEN" "$URL/health" >/dev/null 2>&1; then break; fi
  sleep 0.1
done

pass() { printf "  \e[32mPASS\e[0m %s\n" "$1"; }
fail() { printf "  \e[31mFAIL\e[0m %s\n" "$1"; cat "$TMP/daemon.log"; exit 1; }

assert_eq() {
  local got="$1" want="$2" name="$3"
  if [ "$got" = "$want" ]; then pass "$name"; else fail "$name: got=$got want=$want"; fi
}

curl_json() {
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -sf -X "$method" -H "x-daemon-token: $TOKEN" -H 'content-type: application/json' -d "$body" "$URL$path"
  else
    curl -sf -X "$method" -H "x-daemon-token: $TOKEN" "$URL$path"
  fi
}

echo "==> /health"
HEALTH=$(curl_json GET /health)
assert_eq "$(echo "$HEALTH" | jq -r .ok)" "true" "health.ok"
assert_eq "$(echo "$HEALTH" | jq -r .sessions)" "0" "health.sessions=0"

echo "==> auth gate rejects bad token"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$URL/health")
assert_eq "$CODE" "401" "missing token → 401"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -H "x-daemon-token: wrong" "$URL/health")
assert_eq "$CODE" "401" "bad token → 401"

echo "==> register session"
REG=$(curl_json POST /sessions "{\"session_id\":\"$SID\",\"label\":\"smoke\",\"cwd\":\"/tmp\",\"pid\":$$}")
THREAD=$(echo "$REG" | jq -r .session.threadId)
[ -n "$THREAD" ] && [ "$THREAD" != "null" ] || fail "register returned no threadId"
pass "register → thread=$THREAD"

echo "==> list shows it"
COUNT=$(curl_json GET /sessions | jq '.sessions | length')
assert_eq "$COUNT" "1" "list count=1"

echo "==> heartbeat"
assert_eq "$(curl_json POST "/sessions/$SID/heartbeat" | jq -r .ok)" "true" "heartbeat"

echo "==> SSE stream + injected message"
# Spawn an SSE listener in background, capture events to a file
( curl -sN -H "x-daemon-token: $TOKEN" "$URL/sessions/$SID/inbox" > "$TMP/sse.log" 2>/dev/null ) &
SSE_PID=$!
sleep 0.5

curl_json POST /_mock/inject "{\"thread_id\":\"$THREAD\",\"content\":\"hello from smoke\",\"user\":\"tester\",\"user_id\":\"42\"}" >/dev/null
sleep 0.3
grep -q "hello from smoke" "$TMP/sse.log" && pass "SSE delivered injected message" || fail "SSE did not deliver"
grep -q '"kind":"hello"' "$TMP/sse.log" && pass "SSE hello event" || fail "no hello event"

echo "==> send message"
SEND=$(curl_json POST "/sessions/$SID/send" "{\"chat_id\":\"$THREAD\",\"text\":\"reply from smoke\"}")
IDS=$(echo "$SEND" | jq '.ids | length')
assert_eq "$IDS" "1" "send returned 1 id"

echo "==> chat_id authorization"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "x-daemon-token: $TOKEN" -H 'content-type: application/json' \
  -d "{\"chat_id\":\"some-other-thread\",\"text\":\"x\"}" "$URL/sessions/$SID/send")
assert_eq "$CODE" "403" "send with wrong chat_id → 403"

echo "==> edit"
SEND2=$(curl_json POST "/sessions/$SID/send" "{\"chat_id\":\"$THREAD\",\"text\":\"v1\"}")
MID=$(echo "$SEND2" | jq -r '.ids[0]')
EDIT=$(curl_json POST "/sessions/$SID/edit" "{\"chat_id\":\"$THREAD\",\"message_id\":\"$MID\",\"text\":\"v2\"}")
assert_eq "$(echo "$EDIT" | jq -r .id)" "$MID" "edit returns same id"

echo "==> react"
assert_eq "$(curl_json POST "/sessions/$SID/react" "{\"chat_id\":\"$THREAD\",\"message_id\":\"$MID\",\"emoji\":\"👍\"}" | jq -r .ok)" "true" "react"

echo "==> unregister"
assert_eq "$(curl_json DELETE "/sessions/$SID" | jq -r .ok)" "true" "unregister"
assert_eq "$(curl_json GET /sessions | jq '.sessions | length')" "0" "list empty after unregister"

# Optional: check daemon log shows mock thread create+archive
grep -q "createSessionThread" "$TMP/daemon.log" && pass "daemon logged thread create" || fail "missing create log"
grep -q "archiveSessionThread" "$TMP/daemon.log" && pass "daemon logged thread archive" || fail "missing archive log"

echo
echo "✅ all smoke checks passed"
