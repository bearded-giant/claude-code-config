#!/usr/bin/env bash
# Back up daemon state to an age-encrypted tarball.
# Pulls .env, access.json, sessions.json from VPS → encrypts locally → stashes
# in ~/Backups/discord-daemon/. Skips inbox/ (large + ephemeral attachments).
#
# Setup once (laptop):
#   brew install age
#   age-keygen -o ~/.config/age/discord-daemon.key
#   grep "public key" ~/.config/age/discord-daemon.key   # → age recipient
#   AGE_RECIPIENT=age1... ./scripts/backup-daemon-state.sh claude-vps
#
# Restore:
#   age -d -i ~/.config/age/discord-daemon.key < backup.tar.age | tar -x -C /

set -euo pipefail

VPS_HOST="${1:-claude-vps}"
AGE_RECIPIENT="${AGE_RECIPIENT:-}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/Backups/discord-daemon}"

if [ -z "$AGE_RECIPIENT" ]; then
  echo "AGE_RECIPIENT env var required (age public key)." >&2
  echo "  age-keygen -o ~/.config/age/discord-daemon.key" >&2
  exit 1
fi
command -v age >/dev/null || { echo "missing: age (brew install age)"; exit 1; }

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$BACKUP_DIR/discord-daemon-${STAMP}.tar.age"

echo "==> backing up $VPS_HOST:~/.claude/channels/discord (excluding inbox/) → $OUT"
ssh "$VPS_HOST" 'tar -C ~/.claude/channels -cf - --exclude=discord/inbox discord' \
  | age -r "$AGE_RECIPIENT" -o "$OUT"

ls -lh "$OUT"

# Retain last 14
ls -1t "$BACKUP_DIR"/discord-daemon-*.tar.age 2>/dev/null | tail -n +15 | while read -r f; do
  echo "==> pruning $f"
  rm -f "$f"
done

echo "done. restore with:"
echo "  age -d -i ~/.config/age/discord-daemon.key < '$OUT' | ssh $VPS_HOST 'tar -C ~/.claude/channels -x'"
