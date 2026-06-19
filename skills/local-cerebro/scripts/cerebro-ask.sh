#!/usr/bin/env bash
# local-cerebro: preflight + one-shot invoke of the local cerebro raw CLI.
#
#   cerebro-ask.sh "prompt naming the repo" [haiku|sonnet|opus]   # ask
#   cerebro-ask.sh status                                          # readiness report, no Claude call
#
# stdout = the answer only. stderr = status/warnings. exit: 0 ok / 1 run fail /
# 2 build-rejected / 3 not ready.
set -uo pipefail

CEREBRO_DIR="${CEREBRO_DIR:-$HOME/dev/ai/cerebro}"
DEFAULT_MODEL="opus"

err() { printf '%s\n' "$*" >&2; }

# hard readiness: can we invoke at all? (no output)
check_ready() {
  [ -d "$CEREBRO_DIR" ] && [ -f "$CEREBRO_DIR/broker/cli.py" ] || return 3
  command -v uv >/dev/null 2>&1 || return 3
  return 0
}

# verbose report to stderr; exit code mirrors check_ready
print_status() {
  err "local-cerebro status (one-shot; no daemon -- 'ready' = invocable)"
  err "  dir:     $CEREBRO_DIR"
  if [ -d "$CEREBRO_DIR" ] && [ -f "$CEREBRO_DIR/broker/cli.py" ]; then
    err "  cerebro: ok"
  else
    err "  cerebro: NOT FOUND (set CEREBRO_DIR or clone cerebro)"
  fi
  if command -v uv >/dev/null 2>&1; then err "  uv:      ok"; else err "  uv:      MISSING (install uv)"; fi
  if [ -f "$CEREBRO_DIR/.env" ]; then
    err "  .env:    ok"
  else
    err "  .env:    missing (MCP health probe may block boot; see projects/LOCAL_SETUP.md)"
  fi
  if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    err "  api key: set (platform billing)"
  else
    err "  api key: UNSET (will bill your logged-in claude subscription)"
  fi
  local idx="$CEREBRO_DIR/.runtime/project_index.json"
  if [ -f "$idx" ]; then
    err "  repos:   $(grep -co '"gitlab_path"' "$idx" 2>/dev/null | tr -d ' ') indexed"
  else
    err "  repos:   none indexed (run scripts/index_projects.py)"
  fi
  if check_ready; then err "  => READY"; return 0; else err "  => NOT READY"; return 3; fi
}

cmd="${1:-}"
case "$cmd" in
  ""|status|--status|-h|--help)
    print_status; exit $?
    ;;
esac

PROMPT="$cmd"
MODEL="${2:-$DEFAULT_MODEL}"
case "$MODEL" in
  haiku|sonnet|opus) ;;
  *) err "warn: invalid model '$MODEL'; using $DEFAULT_MODEL"; MODEL="$DEFAULT_MODEL" ;;
esac

if ! check_ready; then
  print_status
  err "local-cerebro not ready -- see status above."
  exit 3
fi

[ -n "${ANTHROPIC_API_KEY:-}" ] || err "warn: ANTHROPIC_API_KEY unset -- billing your logged-in subscription, not a platform key."

cd "$CEREBRO_DIR" || { err "cannot cd $CEREBRO_DIR"; exit 3; }
exec uv run python -m broker.cli --ask "$PROMPT" --model "$MODEL"
