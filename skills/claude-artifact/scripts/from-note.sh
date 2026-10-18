#!/usr/bin/env bash
# usage: from-note.sh [-y] <vault note.md>
# opens an interactive claude session that runs /claude-artifact on the note; -y skips the account confirm
set -euo pipefail
# gui callers (obsidian shell commands) start with a bare PATH
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

yes=""
[ "${1:-}" = "-y" ] && yes=1 && shift
[ -f "${1:-}" ] || { echo "usage: from-note.sh [-y] <note.md>" >&2; exit 2; }
note=$(realpath "$1")
acct=$(python3 "$HOME/.claude/skills/obsidian-note/scripts/note.py" account "$note")

if [ -z "$yes" ]; then
  osascript -e "display dialog \"Create claude artifact as $acct?\" buttons {\"Cancel\", \"Create\"} default button \"Create\"" >/dev/null 2>&1 || exit 0
fi

# claude -p has no Artifact tool, so this must be an interactive session; an exported api key would override the claude.ai login
cmd="env -u ANTHROPIC_API_KEY claude $(printf %q "/claude-artifact $note")"
vault=${OBSIDIAN_VAULT:-$HOME/Recharge-Notes}
if [ -n "${TMUX:-}" ]; then
  tmux new-window -n "artifact:$acct" -c "$vault" "$cmd"
else
  wezterm start --cwd "$vault" -- bash -lc "$cmd" >/dev/null 2>&1 &
fi
echo "artifact session opened as $acct"
