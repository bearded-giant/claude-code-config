#!/usr/bin/env bash
# Create the laptop ↔ VPS Mutagen sync for ~/dev with the right flags +
# ignores derived from real-world lessons. Idempotent: skips if "dev" session
# already exists. Re-create from scratch with --recreate.
#
# Usage:
#   scripts/mutagen-sync-dev.sh <vps-public-ip>
#   scripts/mutagen-sync-dev.sh <vps-public-ip> --recreate

set -euo pipefail

if [ $# -lt 1 ]; then
  cat <<EOF
usage: $(basename "$0") <vps-public-ip> [--recreate]

  vps-public-ip   Hetzner cloud public IP. NOT the tailnet hostname —
                  Tailscale SSH strips file mode bits and breaks the agent.
                  hcloud server ip claude-vps

  --recreate      Terminate existing "dev" session and create fresh.
EOF
  exit 1
fi

VPS_IP="$1"
RECREATE="${2:-}"
SESSION_NAME="dev"
LOCAL_PATH="$HOME/dev"
REMOTE_PATH="/home/bryan/dev"

# Sync mode: two-way-resolved — both sides can write. On conflict, the side
# with the newer mtime wins. Deletes propagate. This lets dclaude on the VPS
# edit code that mutagen syncs back to the laptop for git commit + push.
#
# (Previously one-way-safe; flipped because VPS-side dclaude edits otherwise
# get stranded on the VPS and git push from there requires per-remote auth
# the VPS can't always satisfy — e.g. corporate GitLab behind ZTNA.)
SYNC_MODE="two-way-resolved"

# Excludes — derived from runbook lessons. Path-style (with trailing slash)
# for directories; plain name for any-depth matching.
IGNORES=(
  # build/runtime caches
  'node_modules'
  '.venv'
  'venv'
  '__pycache__'
  '.mypy_cache'
  '.pytest_cache'
  '.tox'
  '.gradle'
  'target/'
  'dist/'
  'build/'
  '.next/'
  '.nuxt/'
  '*.pyc'
  '.DS_Store'

  # claude-code-config runtime caches — regenerate per-host, would conflict
  'plugins/cache/'
  'plugins/marketplaces/'
  'plugins/repos/'
  'plugins/subtask/'
  'plugins/install-counts-cache.json'
  'plugins/known_marketplaces.json'

  # ALL .git dirs — every repo's git state is per-host. Mutagen syncing refs
  # races against git operations and corrupts HEAD. Commits + pushes happen on
  # the laptop only; the VPS edits files but never commits.
  '.git/'

  # session memory artifacts
  '.giantmem'
)

mutagen daemon start >/dev/null 2>&1 || true

if mutagen sync list "$SESSION_NAME" >/dev/null 2>&1; then
  if [ "$RECREATE" = "--recreate" ]; then
    echo "==> terminating existing '$SESSION_NAME' session"
    mutagen sync terminate "$SESSION_NAME"
  else
    echo "==> '$SESSION_NAME' already exists. Pass --recreate to start over."
    mutagen sync list "$SESSION_NAME" | grep -E "Status|Conflicts|files"
    exit 0
  fi
fi

ignore_flags=()
for i in "${IGNORES[@]}"; do
  ignore_flags+=(--ignore="$i")
done

echo "==> creating sync '$SESSION_NAME': $LOCAL_PATH -> bryan@$VPS_IP:$REMOTE_PATH ($SYNC_MODE)"
mutagen sync create --name="$SESSION_NAME" \
  --sync-mode="$SYNC_MODE" \
  --symlink-mode=posix-raw \
  "${ignore_flags[@]}" \
  "$LOCAL_PATH" "bryan@$VPS_IP:$REMOTE_PATH"

echo
echo "==> initial scan + transfer running in background"
echo "    watch:   mutagen sync monitor $SESSION_NAME"
echo "    status:  mutagen sync list $SESSION_NAME"
echo
echo "First sync takes 30-60 min over typical home upload."
