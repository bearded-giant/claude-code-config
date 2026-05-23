#!/usr/bin/env bash
# Manage a discord-daemon over HTTP. Usable against local or remote (tailnet).
#
# Config via env or ~/.discord-daemon-cli:
#   DAEMON_URL    default: http://127.0.0.1:7777
#   DAEMON_TOKEN  required
#
# Commands:
#   health
#   list
#   status <session_id>
#   kill <session_id>
#   tail <session_id>           (SSE follow)
#   inject <thread_id> <text>   (mock-mode only)

set -euo pipefail

CONFIG_FILE="${HOME}/.discord-daemon-cli"
if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

DAEMON_URL="${DAEMON_URL:-http://127.0.0.1:7777}"
DAEMON_TOKEN="${DAEMON_TOKEN:-}"

if [ -z "$DAEMON_TOKEN" ]; then
  echo "DAEMON_TOKEN unset. Export it or put in $CONFIG_FILE:" >&2
  echo "  DAEMON_URL=http://claude-vps:7777" >&2
  echo "  DAEMON_TOKEN=..." >&2
  exit 1
fi

usage() {
  cat <<EOF
usage: $(basename "$0") <command> [args...]

  health
  list
  status <session_id>
  kill   <session_id>
  tail   <session_id>             stream inbox SSE
  inject <thread_id> <text...>    mock-mode only

env:
  DAEMON_URL   = $DAEMON_URL
  DAEMON_TOKEN = (set)
EOF
}

call() {
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -sf -X "$method" \
      -H "x-daemon-token: $DAEMON_TOKEN" \
      -H 'content-type: application/json' \
      -d "$body" \
      "$DAEMON_URL$path"
  else
    curl -sf -X "$method" \
      -H "x-daemon-token: $DAEMON_TOKEN" \
      "$DAEMON_URL$path"
  fi
}

case "${1:-}" in
  health)
    call GET /health | jq
    ;;
  list|ls)
    call GET /sessions | jq -r '
      if (.sessions | length) == 0 then "(no sessions)" else
        .sessions[] | "\(.label)\t\(.sessionId)\t\(.cwd)\tthread=\(.threadId)"
      end'
    ;;
  status)
    [ -n "${2:-}" ] || { usage; exit 1; }
    call GET /sessions | jq --arg id "$2" '.sessions[] | select(.sessionId==$id or .label==$id)'
    ;;
  kill)
    [ -n "${2:-}" ] || { usage; exit 1; }
    # Resolve label → session_id if needed
    SID=$(call GET /sessions | jq -r --arg id "$2" '.sessions[] | select(.sessionId==$id or .label==$id) | .sessionId' | head -1)
    [ -n "$SID" ] || { echo "no session matching $2"; exit 1; }
    call DELETE "/sessions/$SID" | jq
    ;;
  tail)
    [ -n "${2:-}" ] || { usage; exit 1; }
    exec curl -sN -H "x-daemon-token: $DAEMON_TOKEN" "$DAEMON_URL/sessions/$2/inbox"
    ;;
  inject)
    [ -n "${2:-}" ] && [ -n "${3:-}" ] || { usage; exit 1; }
    TID="$2"; shift 2; TEXT="$*"
    call POST /_mock/inject "$(jq -nc --arg t "$TID" --arg c "$TEXT" '{thread_id:$t, content:$c}')" | jq
    ;;
  ''|-h|--help|help) usage ;;
  *) usage; exit 1 ;;
esac
