#!/usr/bin/env bash
# Bring the claude session for the current directory back from the devbox: exit it there if it
# is idle, carry the checkout's git state back (branch tip plus uncommitted work), copy the
# transcript, and resume it here. The reverse of lift-to-vps.sh.
#
# Usage:
#   cd ~/dev/<project>
#   scripts/land-from-vps.sh                 # resume here on the team login
#   scripts/land-from-vps.sh --acct ent      # resume on the Enterprise login
#   scripts/land-from-vps.sh --no-resume     # sync only, print the resume command
#   scripts/land-from-vps.sh --force         # exit the box session even mid-turn
#   scripts/land-from-vps.sh <session-id>    # a specific session, not the box's newest

set -euo pipefail

REMOTE="${LIFT_REMOTE:-${VPS_HOST:-devbox}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ACCT="${DCLAUDE_ACCT:-team}"; RESUME=1; FORCE=0; SESSION_ID=""
while [ $# -gt 0 ]; do
  case "$1" in
    --acct)      [ $# -ge 2 ] || { echo "land: --acct needs team|ent" >&2; exit 2; }
                 ACCT="$2"; shift 2;;
    --no-resume) RESUME=0; shift;;
    --force)     FORCE=1; shift;;
    -h|--help)   sed -n '2,12p' "$0"; exit 0;;
    -*)          echo "land: unknown flag: $1" >&2; exit 2;;
    *)           SESSION_ID="$1"; shift;;
  esac
done
case "$ACCT" in team|ent) ;; *) echo "land: --acct must be team or ent (got '$ACCT')" >&2; exit 2 ;; esac

die() { echo "land: $*" >&2; exit 1; }
# the script comes on stdin; every argument is quoted for the remote login shell
rsh() { local q; q=$(printf '%q ' "$@"); ssh "$REMOTE" "bash -l -s -- $q"; }

DIR="$HOME/.claude/projects/$(echo "$PWD" | sed 's/[^A-Za-z0-9]/-/g')"
NAME=$(basename "$PWD")
case "$(dirname "$PWD")" in *-wt) NAME="$(basename "$(dirname "$PWD")")-$NAME" ;; esac
NAME=${NAME//[.:]/_}

rsh "$NAME" "$FORCE" <<'EOF' || die "the session on $REMOTE is still running; nothing was brought back"
name=$1 force=$2
idle() { ! tmux has-session -t "=$name" 2>/dev/null || [ "$(tmux display-message -p -t "=$name:" '#{pane_current_command}')" = bash ]; }
idle && exit 0
if [ "$force" != 1 ]; then
  plan=$(curl -fsS -m 10 -X POST http://127.0.0.1:7777/restart -H "x-daemon-token: $DISCORD_DAEMON_TOKEN" \
    -H 'content-type: application/json' -d "{\"target\":\"$name\",\"dry_run\":true}" || true)
  case "$plan" in
    *"would wait"*) echo "land: the box session '$name' is mid-turn: wait for it, or land --force" >&2; exit 1 ;;
  esac
fi
tmux send-keys -t "=$name:" "/exit"
sleep 1
tmux send-keys -t "=$name:" Enter
for _ in $(seq 60); do idle && exit 0; sleep 1; done
echo "land: the box session '$name' did not exit: cvps and close it" >&2
exit 1
EOF

if [ -z "$SESSION_ID" ]; then
  SESSION_ID=$(ssh "$REMOTE" "ls -t $(printf %q "$DIR")/????????-*.jsonl 2>/dev/null | head -1")
  SESSION_ID=$(basename "${SESSION_ID:-}" .jsonl)
fi
[ -n "$SESSION_ID" ] || die "$REMOTE has no session for $PWD"

echo "  cwd:      $PWD"
echo "  session:  $SESSION_ID"
echo "  remote:   $REMOTE"

if TOP=$(git rev-parse --show-toplevel 2>/dev/null); then
  COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd)
  read -r BRANCH HEAD_SHA SNAP < <(ssh "$REMOTE" "cd $(printf %q "$TOP") && bash -s -- make" < "$HERE/wt-carry.sh") || true
  [ -n "${SNAP:-}" ] || die "could not snapshot $TOP on $REMOTE"
  git fetch -q "$REMOTE:$COMMON" \
    "+refs/carry/head/$BRANCH:refs/carry-in/head/$BRANCH" "+refs/carry/snap/$BRANCH:refs/carry-in/snap/$BRANCH"
  (cd "$TOP" && "$HERE/wt-carry.sh" apply "$BRANCH") \
    || die "this checkout refused the box's code state (above); the transcript was not copied"
  echo "  code:     $BRANCH @ ${HEAD_SHA:0:8}$([ "$SNAP" = "$HEAD_SHA" ] || echo ' + uncommitted work')"
fi

mkdir -p "$DIR"
rsync -aq "$REMOTE:$DIR/$SESSION_ID.jsonl" "$DIR/"
rsync -aq "$REMOTE:$DIR/$SESSION_ID/" "$DIR/$SESSION_ID/" 2>/dev/null || true

if [ "$RESUME" = 0 ]; then
  echo
  echo "  claude --resume $SESSION_ID"
  exit 0
fi
exec env CLAUDE_SECURESTORAGE_CONFIG_DIR="$HOME/.claude-$ACCT" claude --resume "$SESSION_ID"
