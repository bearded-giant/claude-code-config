#!/usr/bin/env bash
# Laptop <-> devbox mutagen sessions for the state dirs that are not git repos:
# claude transcripts and the Obsidian vault. Idempotent.
#
# Usage:
#   scripts/mutagen-sync-state.sh                # host $VPS_HOST, default devbox
#   scripts/mutagen-sync-state.sh --recreate     # terminate + recreate the sessions

set -euo pipefail

VPS_HOST="${VPS_HOST:-devbox}"
REMOTE_HOME="/Users/bryan"
RECREATE="${1:-}"

# name|local|remote|comma-separated ignores
SESSIONS=(
  "claude-projects|$HOME/.claude/projects|$REMOTE_HOME/.claude/projects|"
  "vault|$HOME/Recharge-Notes|$REMOTE_HOME/Recharge-Notes|.git/,.obsidian/workspace*"
)

mutagen daemon start >/dev/null 2>&1 || true
ssh "$VPS_HOST" "mkdir -p $REMOTE_HOME/.claude/projects $REMOTE_HOME/Recharge-Notes"

for spec in "${SESSIONS[@]}"; do
  IFS='|' read -r name src dst ignores <<<"$spec"
  if mutagen sync list "$name" >/dev/null 2>&1; then
    if [ "$RECREATE" = "--recreate" ]; then
      echo "==> terminating '$name'"
      mutagen sync terminate "$name"
    else
      echo "==> '$name' exists, skipping (--recreate to start over)"
      continue
    fi
  fi
  flags=()
  IFS=',' read -ra pats <<<"$ignores"
  for p in "${pats[@]}"; do [ -n "$p" ] && flags+=(--ignore="$p"); done
  echo "==> creating '$name': $src <-> $VPS_HOST:$dst"
  mutagen sync create --name="$name" \
    --sync-mode=two-way-resolved \
    --symlink-mode=posix-raw \
    ${flags[@]+"${flags[@]}"} \
    "$src" "$VPS_HOST:$dst"
done

echo
mutagen sync list | grep -E '^Name|^\s*Status'
echo
echo "watch: mutagen sync monitor <name>    sessions pause while Twingate is down and resume on their own"
