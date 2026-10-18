#!/usr/bin/env bash
# bash, not dispatch.py: PostToolUse runs this on every tool call and a python spawn costs ~40ms
cat >/dev/null
[[ -n "${TMUX_PANE:-}" ]] || exit 0
t=(-p -t "$TMUX_PANE")
toast() {
	# the pane on screen needs no nudge; everything off screen does
	[[ "$(tmux display -p -t "$TMUX_PANE" '#{&&:#{pane_active},#{&&:#{window_active},#{session_attached}}}')" == 1 ]] && return 0
	tmux display-message -d 4000 -t "$TMUX_PANE" "claude $1: #{session_name}:#{window_index} #{b:pane_current_path}"
}
case "${1:-}" in
off)
	tmux set-option "${t[@]}" -u @claude_state \; set-option "${t[@]}" -u @claude_state_at \; \
		set-option "${t[@]}" -u @claude_attention \; set-option "${t[@]}" -u @claude_attention_sent \; set-option "${t[@]}" -u @claude_attention_ack \; \
		set-option "${t[@]}" -u @claude_agents \; set-option "${t[@]}" -u @claude_ctx \; set-option "${t[@]}" -u @claude_err \; set-option "${t[@]}" -u @claude_model \; \
		set-option "${t[@]}" -u @doit-pane-list
	;;
submit)
	# a /loop tick submits too, so babysit re-raises attention on every run while something is pending
	tmux set-option "${t[@]}" -u @claude_attention \; set-option "${t[@]}" @claude_agents 0 \; \
		set-option "${t[@]}" @claude_state busy \; set-option "${t[@]}" @claude_state_at "$(date +%s)"
	;;
agent+|agent-)
	n=$(tmux show-option -pv -t "$TMUX_PANE" @claude_agents 2>/dev/null)
	n=${n:-0}
	if [[ "$1" == agent+ ]]; then n=$((n + 1)); else n=$((n > 0 ? n - 1 : 0)); fi
	tmux set-option "${t[@]}" @claude_agents "$n"
	;;
err)
	tmux set-option "${t[@]}" @claude_err "${2:-api error}"
	toast err
	;;
errclear)
	tmux set-option "${t[@]}" -u @claude_err
	;;
*)
	tmux set-option "${t[@]}" @claude_state "$1" \; set-option "${t[@]}" @claude_state_at "$(date +%s)"
	[[ "$1" == ask || "$1" == ready ]] && toast "$1"
	;;
esac 2>/dev/null
exit 0
