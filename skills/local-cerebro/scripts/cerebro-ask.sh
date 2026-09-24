#!/usr/bin/env bash
# local-cerebro: preflight + one-shot invoke of the local cerebro raw CLI.
#
#   cerebro-ask.sh "prompt naming the repo" [haiku|sonnet|opus]   # ask
#   cerebro-ask.sh status                                          # readiness report, no Claude call
#   cerebro-ask.sh repos                                           # list projects/: branch, target, BROKEN
#   cerebro-ask.sh add <repo-path> [name]                          # symlink a git checkout in, re-index
#   cerebro-ask.sh remove <name>                                   # unlink a symlinked project, re-index
#
# stdout = the answer (or repos list) only. stderr = status/warnings. exit: 0 ok /
# 1 run fail or refused / 2 build-rejected / 3 not ready.
set -uo pipefail

CEREBRO_DIR="${CEREBRO_DIR:-$HOME/dev/ai/cerebro}"
# ponytail: a CEREBRO_PROJECTS_DIR set only in cerebro's .env is invisible here; export it too
PROJECTS_DIR="${CEREBRO_PROJECTS_DIR:-$CEREBRO_DIR/projects}"
DEFAULT_MODEL="opus"

err() { printf '%s\n' "$*" >&2; }

# anything linked into projects/ becomes readable by cerebro, so names stay one safe segment
valid_name() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; }

reindex() {
  (cd "$CEREBRO_DIR" && uv run python scripts/index_projects.py --mechanical) >&2
}

list_repos() {
  local p name branch
  for p in "$PROJECTS_DIR"/*; do
    [ -L "$p" ] || [ -d "$p" ] || continue
    name="$(basename "$p")"
    if [ ! -e "$p" ]; then
      printf '%-40s %-28s -> %s\n' "$name" "BROKEN" "$(readlink "$p")"
      continue
    fi
    branch="$(git -C "$p" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    if [ -L "$p" ]; then
      printf '%-40s %-28s -> %s\n' "$name" "$branch" "$(readlink "$p")"
    else
      printf '%-40s %-28s (clone)\n' "$name" "$branch"
    fi
  done
}

add_repo() {
  local src="${1:-}" name="${2:-}" top url link
  [ -n "$src" ] || { err "usage: cerebro-ask.sh add <repo-path> [name]"; return 1; }
  top="$(git -C "$src" rev-parse --show-toplevel 2>/dev/null)" || { err "not a git checkout: $src"; return 1; }
  if [ -z "$name" ]; then
    # worktree dirs are named after the branch (…-wt/main), so name from the remote
    url="$(git -C "$top" remote get-url origin 2>/dev/null)"
    name="$(basename "${url:-$top}" .git)"
  fi
  valid_name "$name" || { err "bad project name '$name' (letters, digits, . _ -; no leading dot)"; return 1; }
  link="$PROJECTS_DIR/$name"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    err "$link is a real clone, not a symlink; remove it by hand first"
    return 1
  fi
  [ -L "$link" ] && err "repointing $name (was -> $(readlink "$link"))"
  ln -sfn "$top" "$link" || return 1
  err "linked $name -> $top"
  reindex
}

remove_repo() {
  local name="${1:-}" link
  [ -n "$name" ] || { err "usage: cerebro-ask.sh remove <name>"; return 1; }
  valid_name "$name" || { err "bad project name '$name'"; return 1; }
  link="$PROJECTS_DIR/$name"
  if [ -L "$link" ]; then
    rm "$link" || return 1
    err "unlinked $name (checkout untouched)"
    reindex
  elif [ -d "$link" ]; then
    err "$name is a real clone; delete it by hand (rm -rf \"$link\"), then: cerebro-ask.sh repos"
    return 1
  else
    err "no project named '$name' in $PROJECTS_DIR (see: cerebro-ask.sh repos)"
    return 1
  fi
}

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
    err "  .env:    missing (MCP health probe may block boot; see docs/CLI.md \"Local Setup\")"
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
  repos)
    list_repos; exit $?
    ;;
  add|remove)
    check_ready || { print_status; exit 3; }
    shift
    if [ "$cmd" = add ]; then add_repo "$@"; else remove_repo "$@"; fi
    exit $?
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
