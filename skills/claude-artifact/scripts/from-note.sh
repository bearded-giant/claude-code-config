#!/usr/bin/env bash
# usage: from-note.sh [-y] [--mirror | --account rc-inc|rc-team] <vault note.md>
# opens an interactive claude session on the account's keychain slot that runs /claude-artifact on the note;
# account defaults to the note's artifact_account, else this shell's login; --mirror = the other account; -y skips the confirm
set -euo pipefail
# gui callers start with a bare PATH
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

usage="usage: from-note.sh [-y] [--mirror | --account rc-inc|rc-team] <note.md>"
yes="" mirror="" acct=""
while [ $# -gt 1 ]; do
  case "$1" in
    -y) yes=1 ;;
    --mirror) mirror=1 ;;
    --account) acct=$2; shift ;;
    *) echo "$usage" >&2; exit 2 ;;
  esac
  shift
done
[ -f "${1:-}" ] || { echo "$usage" >&2; exit 2; }
note=$(realpath "$1")
note_py="$HOME/.claude/skills/obsidian-note/scripts/note.py"
owner=$(sed -n '2,/^---$/s/^artifact_account: *//p' "$note")

if [ -n "$mirror" ]; then
  case "$owner" in
    rc-inc) acct=rc-team ;;
    rc-team) acct=rc-inc ;;
    *) echo "no mirror account for artifact_account '$owner'" >&2; exit 2 ;;
  esac
fi
acct=${acct:-${owner:-$(python3 "$note_py" account)}}
# slot dirs match the claude-team / claude-ent aliases in dotfiles shell/.bash_aliases
case "$acct" in
  rc-team) slot=$HOME/.claude-team ;;
  rc-inc) slot=$HOME/.claude-ent ;;
  *) echo "no keychain slot for account '$acct'" >&2; exit 2 ;;
esac

read -r kind m s cached <<<"$(python3 "$note_py" role --account "$acct" "$note")"
case "$kind" in
  mirror)
    [ "$m" = "$s" ] && { echo "$acct mirror already at rev $s"; exit 0; }
    [ "$cached" = "-" ] && { echo "rev $s not cached on this machine; republish from $owner first" >&2; exit 1; }
    ask="Mirror rev $s to $acct?" ;;
  new) ask="Create rev 1 as $acct?" ;;
  *) ask="Create rev $((m + 1)) as $acct?" ;;
esac

if [ -z "$yes" ]; then
  osascript -e "display dialog \"$ask\" buttons {\"Cancel\", \"OK\"} default button \"OK\"" >/dev/null 2>&1 || exit 0
fi

# claude -p has no Artifact tool, so this must be an interactive session; an exported api key would override the claude.ai login
cmd="env -u ANTHROPIC_API_KEY CLAUDE_SECURESTORAGE_CONFIG_DIR=$(printf %q "$slot") claude $(printf %q "/claude-artifact $note")"
vault=${OBSIDIAN_VAULT:-$HOME/Recharge-Notes}
if [ -n "${TMUX:-}" ]; then
  tmux new-window -n "artifact:$acct" -c "$vault" "$cmd"
else
  wezterm start --cwd "$vault" -- bash -lc "$cmd" >/dev/null 2>&1 &
fi
echo "artifact session opened as $acct"
