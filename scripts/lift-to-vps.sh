#!/usr/bin/env bash
# Copy one claude transcript for the current cwd to the devbox and print the
# resume command. Fallback for when the claude-projects mutagen session is off.
# Paths match on both machines through the /Users/bryan bridge, so nothing is
# rewritten.
#
# Usage:
#   cd ~/dev/<project>
#   scripts/lift-to-vps.sh                # latest session in cwd
#   scripts/lift-to-vps.sh <session-id>   # a specific session uuid

set -euo pipefail

REMOTE="${LIFT_REMOTE:-${VPS_HOST:-devbox}}"
ENCODED=$(echo "$PWD" | tr / -)
DIR="$HOME/.claude/projects/$ENCODED"

[ -d "$DIR" ] || { echo "no claude project dir for $PWD (expected $DIR)" >&2; exit 1; }

if [ "${1:-}" ]; then
  SESSION_ID="$1"
  JSONL="$DIR/$SESSION_ID.jsonl"
  [ -f "$JSONL" ] || { echo "no jsonl for session $SESSION_ID (expected $JSONL)" >&2; exit 1; }
else
  JSONL=$(ls -t "$DIR"/*.jsonl 2>/dev/null | head -1)
  [ -n "$JSONL" ] || { echo "no jsonl files in $DIR" >&2; exit 1; }
  SESSION_ID=$(basename "$JSONL" .jsonl)
fi

echo "  cwd:      $PWD"
echo "  session:  $SESSION_ID ($(du -h "$JSONL" | cut -f1))"
echo "  remote:   $REMOTE"

ssh "$REMOTE" "mkdir -p '$DIR'"
rsync -aq "$JSONL" "$REMOTE:$DIR/"
if [ -d "$DIR/$SESSION_ID" ]; then
  rsync -aq "$DIR/$SESSION_ID/" "$REMOTE:$DIR/$SESSION_ID/"
fi
if [ -d "$HOME/.claude/file-history/$SESSION_ID" ]; then
  ssh "$REMOTE" "mkdir -p ~/.claude/file-history/$SESSION_ID"
  rsync -aq "$HOME/.claude/file-history/$SESSION_ID/" "$REMOTE:.claude/file-history/$SESSION_ID/"
fi

cat <<EOF

Resume on $REMOTE:

  cvps                          # tmux on the devbox, same cwd
  dclaude --resume $SESSION_ID

EOF
