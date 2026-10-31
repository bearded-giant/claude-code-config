#!/usr/bin/env bash
# usage: from-note.sh [-y] <vault note.md>
# opens an interactive claude session that runs /claude-artifact on the note; -y skips the confirm
set -euo pipefail
# gui callers start with a bare PATH
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

usage="usage: from-note.sh [-y] <note.md>"
yes=""
[ "${1:-}" = "-y" ] && { yes=1; shift; }
[ $# -eq 1 ] && [ -f "$1" ] || { echo "$usage" >&2; exit 2; }
note=$(realpath "$1")
rev=$(sed -n '2,/^---$/s/^artifact_rev: *//p' "$note")

if [ -z "$yes" ]; then
  osascript -e "display dialog \"Publish rev $((${rev:-0} + 1)) of $(basename "$note") to the artifacts hub?\" buttons {\"Cancel\", \"OK\"} default button \"OK\"" >/dev/null 2>&1 || exit 0
fi

# an exported api key would override the claude.ai login
cmd="env -u ANTHROPIC_API_KEY claude $(printf %q "/claude-artifact $note")"
vault=${OBSIDIAN_VAULT:-$HOME/Recharge-Notes}
if [ -n "${TMUX:-}" ]; then
  tmux new-window -n "artifact" -c "$vault" "$cmd"
else
  wezterm start --cwd "$vault" -- bash -lc "$cmd" >/dev/null 2>&1 &
fi
echo "artifact session opened"
