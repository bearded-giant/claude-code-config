#!/usr/bin/env bash
# bash, not dispatch.py: PostToolUse runs this on every tool call and a python spawn costs ~40ms
cat >/dev/null
[[ -n "${TMUX_PANE:-}" ]] || exit 0
if [[ "${1:-}" == "off" ]]; then
	tmux set-option -p -t "$TMUX_PANE" -u @claude_state \; set-option -p -t "$TMUX_PANE" -u @claude_state_at
else
	tmux set-option -p -t "$TMUX_PANE" @claude_state "$1" \; set-option -p -t "$TMUX_PANE" @claude_state_at "$(date +%s)"
fi 2>/dev/null
exit 0
