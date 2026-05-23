#!/usr/bin/env bash
# Lift the most recent claude session for the current cwd from this laptop
# to the VPS, preserving JSONL chat history + tool calls so `dclaude --resume`
# (or `--continue`) picks up where you left off.
#
# Path translation: laptop paths /Users/bryan/... become VPS-canonical
# /home/bryan/... in the lifted artifacts (project dir name, jsonl `cwd`
# fields, history.jsonl entries). This matches the keys claude uses in
# ~/.claude.json's `projects` map on the VPS.
#
# Assumes:
#   - claude installed on VPS with same major version
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

LOCAL_USERS_HOME="/Users/bryan"
REMOTE_HOME="/home/bryan"

# Encoded project dir name = absolute cwd with `/` → `-`.
ENCODED_LOCAL=$(echo "$PWD" | tr / -)
LOCAL_DIR="$HOME/.claude/projects/$ENCODED_LOCAL"

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

# Translate to VPS-canonical paths.
REMOTE_PWD="${PWD/#$LOCAL_USERS_HOME/$REMOTE_HOME}"
ENCODED_REMOTE=$(echo "$REMOTE_PWD" | tr / -)

echo "  local cwd:    $PWD"
echo "  remote cwd:   $REMOTE_PWD"
echo "  encoded:      $ENCODED_LOCAL  →  $ENCODED_REMOTE"
echo "  session:      $SESSION_ID"
echo "  jsonl size:   $(du -h "$LOCAL_JSONL" | cut -f1)"
echo "  remote host:  $REMOTE"

# Rewrite cwd inside jsonl events laptop → VPS-canonical, then ship.
TMP_JSONL=$(mktemp)
trap 'rm -f "$TMP_JSONL"' EXIT
sed "s|\"cwd\":\"$LOCAL_USERS_HOME|\"cwd\":\"$REMOTE_HOME|g" "$LOCAL_JSONL" > "$TMP_JSONL"

ssh "$REMOTE" "mkdir -p \"\$HOME/.claude/projects/$ENCODED_REMOTE\""
rsync -av "$TMP_JSONL" "$REMOTE:.claude/projects/$ENCODED_REMOTE/$SESSION_ID.jsonl"
ssh "$REMOTE" "touch \"\$HOME/.claude/projects/$ENCODED_REMOTE/$SESSION_ID.jsonl\""

# Append history.jsonl entries with path translation so the resume picker
# enumerates the lifted session under the right project key.
HISTORY_LINES=$(grep -F "\"sessionId\":\"$SESSION_ID\"" "$HOME/.claude/history.jsonl" 2>/dev/null \
  | sed "s|\"project\":\"$LOCAL_USERS_HOME|\"project\":\"$REMOTE_HOME|g" || true)
if [ -n "$HISTORY_LINES" ]; then
  COUNT=$(printf '%s\n' "$HISTORY_LINES" | wc -l | tr -d ' ')
  echo "  appending $COUNT history.jsonl entries → $REMOTE"
  printf '%s\n' "$HISTORY_LINES" | ssh "$REMOTE" 'cat >> ~/.claude/history.jsonl'
else
  echo "  warning: no history.jsonl entries match session $SESSION_ID (resume picker may not see it)"
fi

# Mirror file-history dir if present (per-session edit revisions; keyed
# by sessionId so no path translation needed).
if [ -d "$HOME/.claude/file-history/$SESSION_ID" ]; then
  echo "  syncing file-history/$SESSION_ID → $REMOTE"
  ssh "$REMOTE" "mkdir -p ~/.claude/file-history/$SESSION_ID"
  rsync -aq "$HOME/.claude/file-history/$SESSION_ID/" "$REMOTE:.claude/file-history/$SESSION_ID/"
fi

cat <<EOF

Resume on VPS:

  cvps                      # local → VPS tmux, lands at $REMOTE_PWD
  dclaude --continue        # OR: dclaude --resume $SESSION_ID

EOF
