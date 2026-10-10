#!/usr/bin/env bash
# bash, not dispatch.py: PostToolUse runs this on every tool call and a python spawn costs ~40ms
cat >/dev/null
[[ -n "${TMUX_PANE:-}" ]] || exit 0
case "${1:-}" in
off)
	tmux set-option -p -t "$TMUX_PANE" -u @claude_state \; set-option -p -t "$TMUX_PANE" -u @claude_state_at \; \
		set-option -p -t "$TMUX_PANE" -u @claude_attention \; set-option -p -t "$TMUX_PANE" -u @claude_attention_sent
	;;
submit)
	# a /loop tick submits too, so babysit re-raises attention on every run while something is pending
	tmux set-option -p -t "$TMUX_PANE" -u @claude_attention \; \
		set-option -p -t "$TMUX_PANE" @claude_state busy \; set-option -p -t "$TMUX_PANE" @claude_state_at "$(date +%s)"
	;;
*)
	tmux set-option -p -t "$TMUX_PANE" @claude_state "$1" \; set-option -p -t "$TMUX_PANE" @claude_state_at "$(date +%s)"
	;;
esac 2>/dev/null
exit 0
