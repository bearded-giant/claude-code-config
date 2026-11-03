#!/usr/bin/env bash
# Restart claude sessions on the devbox through discord-daemon: idle panes now, busy ones once their turn ends.
#
# Usage:
#   scripts/devbox-restart.sh                 # all sessions
#   scripts/devbox-restart.sh cc-wt-master    # one session, by label or tmux session name
#   scripts/devbox-restart.sh all --dry-run   # what would happen
#   scripts/devbox-restart.sh all --force     # restart busy ones too

set -euo pipefail

VPS_HOST="${VPS_HOST:-devbox}"
target="all"
force=false
dry=false
for a in "$@"; do
  case "$a" in
    --force) force=true ;;
    --dry-run) dry=true ;;
    -*) echo "unknown flag: $a" >&2; exit 2 ;;
    *) target="$a" ;;
  esac
done
[[ "$target" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "bad target: $target" >&2; exit 2; }

# login shell on the box: it loads DISCORD_DAEMON_TOKEN
ssh "$VPS_HOST" bash -l -s -- "$target" "$force" "$dry" <<'EOF' | python3 -c 'import json, sys; d = json.load(sys.stdin); print(d.get("text") or d)'
for _ in $(seq 15); do curl -fsS -o /dev/null -H "x-daemon-token: $DISCORD_DAEMON_TOKEN" http://127.0.0.1:7777/health && break; sleep 1; done
curl -fsS -X POST http://127.0.0.1:7777/restart \
  -H "x-daemon-token: $DISCORD_DAEMON_TOKEN" -H 'content-type: application/json' \
  -d "{\"target\":\"$1\",\"force\":$2,\"dry_run\":$3}"
EOF
