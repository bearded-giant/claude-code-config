#!/usr/bin/env bash
# Laptop-side driver that brings a fresh VPS to "claude --login ready" state.
# Wraps: rsync code → run setup-vps.sh on VPS → restore backup if given.
#
# Usage:
#   scripts/bootstrap-vps.sh <vps-hostname-or-ip>
#   scripts/bootstrap-vps.sh <vps-hostname-or-ip> --restore path/to/backup.tar.age
#
# Requires: ssh + rsync. Use the VPS public IP if Tailscale SSH strips
# privileges — scripts inside SSH need a regular sshd session.

set -euo pipefail

if [ $# -lt 1 ]; then
  cat <<EOF
usage: $(basename "$0") <vps-host> [--restore <backup.tar.age>]

Bootstraps a fresh VPS end-to-end. Run scripts/provision-hetzner.sh first
to create the box, then this to bring it to "ready" state.
EOF
  exit 1
fi

VPS_HOST="$1"; shift
RESTORE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --restore) RESTORE="$2"; shift 2;;
    *) echo "unknown flag: $1"; exit 1;;
  esac
done

CONFIG_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> sanity: ssh ${VPS_HOST}"
ssh -o ConnectTimeout=5 "$VPS_HOST" 'echo ok' >/dev/null
echo "    ok"

if [ -x "$CONFIG_DIR/scripts/sync-gitconfig.sh" ]; then
  echo "==> sync git config → ${VPS_HOST} (GPG stripped; KEEP_GPG=1 to preserve)"
  "$CONFIG_DIR/scripts/sync-gitconfig.sh" "$VPS_HOST" || echo "    (git config sync skipped)"
fi

echo "==> rsync claude-code-config → ${VPS_HOST}:~/dev/"
ssh "$VPS_HOST" 'mkdir -p ~/dev'
rsync -az --delete \
  --exclude=node_modules \
  --exclude='.giantmem' \
  --exclude=scratch \
  --exclude='archive' \
  --exclude='*.jsonl' \
  --exclude='plugins/cache' \
  --exclude='plugins/marketplaces' \
  --exclude='plugins/repos' \
  --exclude='plugins/subtask' \
  --exclude='.DS_Store' \
  "$CONFIG_DIR/" \
  "$VPS_HOST:~/dev/claude-code-config/"
echo "    ok"

if [ -n "$RESTORE" ]; then
  if [ ! -f "$RESTORE" ]; then
    echo "missing backup: $RESTORE" >&2; exit 1
  fi
  REMOTE_BACKUP="/tmp/$(basename "$RESTORE")"
  echo "==> uploading backup to ${VPS_HOST}:$REMOTE_BACKUP"
  scp "$RESTORE" "$VPS_HOST:$REMOTE_BACKUP"
  # age key must also live on the VPS for in-place restore
  AGE_KEY="${AGE_KEY:-$HOME/.config/age/discord-daemon.key}"
  if [ -f "$AGE_KEY" ]; then
    REMOTE_AGE="/tmp/discord-daemon.key"
    scp "$AGE_KEY" "$VPS_HOST:$REMOTE_AGE"
    EXTRA_ENV="BACKUP_FILE=$REMOTE_BACKUP AGE_KEY=$REMOTE_AGE"
    echo "    age key staged at $REMOTE_AGE"
  else
    echo "WARN: AGE_KEY not found ($AGE_KEY) — restore will fail. Stage manually."
    EXTRA_ENV="BACKUP_FILE=$REMOTE_BACKUP"
  fi
  # Ensure age is on VPS
  ssh "$VPS_HOST" 'command -v age >/dev/null || sudo apt-get install -y age'
else
  EXTRA_ENV=""
fi

echo "==> running setup-vps.sh on ${VPS_HOST}"
# shellcheck disable=SC2087
ssh "$VPS_HOST" "$EXTRA_ENV bash" < "$CONFIG_DIR/scripts/setup-vps.sh"

cat <<EOF

==> bootstrap complete

Now log in interactively to finish:
  ssh $VPS_HOST
  claude                                        # /login flow

Then verify a session:
  cd ~/dev/test 2>/dev/null || mkdir -p ~/dev/test && cd ~/dev/test
  claude --dangerously-load-development-channels server:discord
EOF
