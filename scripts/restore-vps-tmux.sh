#!/usr/bin/env bash
# Restore claude sessions inside a tmux session on the VPS after reboot.
# Reads a YAML-ish manifest at ~/.claude/vps-sessions.yml:
#
#   - cwd: ~/dev/foo
#     label: foo                # optional, defaults to basename(cwd)
#   - cwd: ~/dev/bar
#
# Creates one tmux window per entry inside `tmux:main`, runs claude with the
# discord channel flag in each. Existing windows are not duplicated — the
# script is idempotent (window name == label).

set -euo pipefail

TMUX_SESSION="${TMUX_SESSION:-main}"
MANIFEST="${MANIFEST:-$HOME/.claude/vps-sessions.yml}"
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"
CHANNEL="${CHANNEL:-server:discord}"

[ -x "$CLAUDE_BIN" ] || { echo "claude binary not found at $CLAUDE_BIN"; exit 1; }
[ -f "$MANIFEST" ]  || { echo "manifest not found: $MANIFEST"; exit 1; }

if ! tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
  echo "==> creating tmux session '$TMUX_SESSION'"
  tmux new-session -d -s "$TMUX_SESSION" -n shell
fi

cwd=""
label=""
flush_entry() {
  [ -n "$cwd" ] || return 0
  local effective_label="${label:-$(basename "$cwd")}"
  if tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' | grep -qx "$effective_label"; then
    echo "  - $effective_label: window exists, skipping"
  else
    echo "  - $effective_label: cd $cwd && claude --dangerously-load-development-channels $CHANNEL"
    tmux new-window -t "$TMUX_SESSION" -n "$effective_label" \
      "cd '${cwd/#\~/$HOME}' && '$CLAUDE_BIN' --dangerously-load-development-channels '$CHANNEL'"
  fi
  cwd=""; label=""
}

# Crude YAML parser: -<space>cwd: and <space>label: lines only.
while IFS= read -r line; do
  case "$line" in
    -*cwd:*)
      flush_entry
      cwd="${line#*cwd:}"
      cwd="${cwd# }"
      cwd="${cwd%\"}"; cwd="${cwd#\"}"
      ;;
    *label:*)
      label="${line#*label:}"
      label="${label# }"
      label="${label%\"}"; label="${label#\"}"
      ;;
  esac
done < "$MANIFEST"
flush_entry

echo
echo "tmux attach -t $TMUX_SESSION"
