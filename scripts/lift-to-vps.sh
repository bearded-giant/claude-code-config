#!/usr/bin/env bash
# Lift the most recent claude session for the current cwd from this laptop
# to the VPS, preserving JSONL chat history + tool calls so `dclaude --resume`
# picks up where you left off.
#
# Assumes:
#   - `/Users/bryan -> /home/bryan` symlink on VPS (setup-vps.sh creates it)
#   - claude project dir naming convention: full path with `/` → `-`
#   - You've /exit'd local claude first (jsonl is flushed on exit)
#
# Usage:
#   cd ~/dev/<project>
#   ./scripts/lift-to-vps.sh                # latest session in cwd
#   ./scripts/lift-to-vps.sh <session-id>   # pin to a specific session uuid
#
# Output: the exact command to run on VPS to resume.

set -euo pipefail

REMOTE="${LIFT_REMOTE:-claude-vps}"
ENCODED=$(echo "$PWD" | tr / -)
LOCAL_DIR="$HOME/.claude/projects/$ENCODED"

if [ ! -d "$LOCAL_DIR" ]; then
  echo "no claude project dir for $PWD" >&2
  echo "  expected: $LOCAL_DIR" >&2
  exit 1
fi

if [ "${1:-}" ]; then
  SESSION_ID="$1"
  LOCAL_JSONL="$LOCAL_DIR/$SESSION_ID.jsonl"
  if [ ! -f "$LOCAL_JSONL" ]; then
    echo "no jsonl for session $SESSION_ID" >&2
    echo "  expected: $LOCAL_JSONL" >&2
    exit 1
  fi
else
  LOCAL_JSONL=$(ls -t "$LOCAL_DIR"/*.jsonl 2>/dev/null | head -1)
  if [ -z "$LOCAL_JSONL" ]; then
    echo "no jsonl files in $LOCAL_DIR" >&2
    exit 1
  fi
  SESSION_ID=$(basename "$LOCAL_JSONL" .jsonl)
fi

echo "  cwd:        $PWD"
echo "  session:    $SESSION_ID"
echo "  jsonl:      $LOCAL_JSONL ($(du -h "$LOCAL_JSONL" | cut -f1))"
echo "  remote:     $REMOTE"

ssh "$REMOTE" "mkdir -p \"\$HOME/.claude/projects/$ENCODED\""
rsync -av "$LOCAL_JSONL" "$REMOTE:.claude/projects/$ENCODED/"
# Bump mtime so `dclaude --continue` picks the lifted session over any older
# VPS-native session in the same cwd.
ssh "$REMOTE" "touch \"\$HOME/.claude/projects/$ENCODED/$SESSION_ID.jsonl\""

# Append matching history.jsonl entries so claude's --resume picker enumerates
# the lifted session. Without these, the conversation jsonl alone is invisible.
HISTORY_LINES=$(grep -F "\"sessionId\":\"$SESSION_ID\"" "$HOME/.claude/history.jsonl" 2>/dev/null || true)
if [ -n "$HISTORY_LINES" ]; then
  COUNT=$(printf '%s\n' "$HISTORY_LINES" | wc -l | tr -d ' ')
  echo "  appending $COUNT history.jsonl entries → $REMOTE"
  printf '%s\n' "$HISTORY_LINES" | ssh "$REMOTE" 'cat >> ~/.claude/history.jsonl'
else
  echo "  warning: no history.jsonl entries match session $SESSION_ID (resume picker may not see it)"
fi

cat <<EOF

Resume on VPS:

  cvps                      # local → VPS tmux (mirrors cwd)
  cd $PWD                   # symlink resolves /Users/bryan → /home/bryan
  dclaude --continue        # OR: dclaude --resume $SESSION_ID

EOF
