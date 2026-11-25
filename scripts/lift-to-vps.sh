#!/usr/bin/env bash
# Hand the claude session in the current directory to the devbox in one step, after /exit:
# carry the checkout's git state (branch tip plus uncommitted work), copy the transcript, and
# start dclaude on it in the box's tmux session for this directory. Paths match on both
# machines through the /Users/bryan bridge, so nothing is rewritten.
#
# Usage:
#   cd ~/dev/<project>
#   scripts/lift-to-vps.sh                   # newest session in cwd
#   scripts/lift-to-vps.sh <session-id>      # a specific session uuid
#   scripts/lift-to-vps.sh -a --acct ent     # attach once it is up; other flags go to dclaude
#   scripts/lift-to-vps.sh --no-start        # carry code and transcript, print the resume command

set -euo pipefail

REMOTE="${LIFT_REMOTE:-${VPS_HOST:-devbox}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SESSION_ID=""; ATTACH=0; START=1; DCLAUDE_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -a|--attach)             ATTACH=1; shift;;
    --no-start)              START=0; shift;;
    -h|--help)               sed -n '2,12p' "$0"; exit 0;;
    --acct|--effort|--model) [ $# -ge 2 ] || { echo "lift: $1 needs a value" >&2; exit 2; }
                             DCLAUDE_ARGS+=("$1" "$2"); shift 2;;
    -*)                      DCLAUDE_ARGS+=("$1"); shift;;
    *)                       SESSION_ID="$1"; shift;;
  esac
done

die() { echo "lift: $*" >&2; exit 1; }
# the script comes on stdin; every argument is quoted for the remote login shell
rsh() { local q; q=$(printf '%q ' "$@"); ssh "$REMOTE" "bash -l -s -- $q"; }

DIR="$HOME/.claude/projects/$(echo "$PWD" | sed 's/[^A-Za-z0-9]/-/g')"
[ -d "$DIR" ] || die "no claude project dir for $PWD (expected $DIR)"
if [ -n "$SESSION_ID" ]; then
  JSONL="$DIR/$SESSION_ID.jsonl"
  [ -f "$JSONL" ] || die "no jsonl for session $SESSION_ID (expected $JSONL)"
else
  JSONL=$(ls -t "$DIR"/????????-*.jsonl 2>/dev/null | head -1)
  [ -n "$JSONL" ] || die "no session transcripts in $DIR"
  SESSION_ID=$(basename "$JSONL" .jsonl)
fi

NAME=$(basename "$PWD")
case "$(dirname "$PWD")" in *-wt) NAME="$(basename "$(dirname "$PWD")")-$NAME" ;; esac
NAME=${NAME//[.:]/_}

echo "  cwd:      $PWD"
echo "  session:  $SESSION_ID ($(du -h "$JSONL" | cut -f1))"
echo "  remote:   $REMOTE"

if TOP=$(git rev-parse --show-toplevel 2>/dev/null); then
  COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd)
  ssh "$REMOTE" "test -d $(printf %q "$COMMON")" \
    || die "$REMOTE has no repo at $COMMON: scripts/devbox-clone-repos.sh $REMOTE --only <alias>"
  read -r BRANCH HEAD_SHA SNAP < <(cd "$TOP" && "$HERE/wt-carry.sh" make) || true
  [ -n "${SNAP:-}" ] || die "could not snapshot $TOP"
  git push -q --force "$REMOTE:$COMMON" \
    "$HEAD_SHA:refs/carry-in/head/$BRANCH" "$SNAP:refs/carry-in/snap/$BRANCH"

  rsh "$TOP" "$BRANCH" "$HEAD_SHA" <<'EOF' || die "could not create the worktree on $REMOTE"
top=$1 branch=$2 head=$3
[ -e "$top/.git" ] && exit 0
base=$(dirname "$top")
[ -d "$base/.bare" ] || { echo "lift: $top is missing on the box and $base is not a worktree layout" >&2; exit 1; }
git -C "$base/.bare" rev-parse -q --verify "refs/heads/$branch" >/dev/null || git -C "$base/.bare" branch -q "$branch" "$head"
prefix=$(wt_projects 2>/dev/null | awk -v b="$base" '$2 == b { print $1; exit }')
if [ -n "$prefix" ] && [ "$base/$branch" = "$top" ]; then
  # the prefix function asks y/N once, then runs the project's own worktree setup
  printf 'y\n' | "${prefix}a" "$branch" >/dev/null 2>&1 || true
fi
[ -e "$top/.git" ] || git -C "$base/.bare" worktree add -q "$top" "$branch"
EOF

  ssh "$REMOTE" "cd $(printf %q "$TOP") && bash -s -- apply $(printf %q "$BRANCH")" < "$HERE/wt-carry.sh" \
    || die "$REMOTE refused the code state (above); nothing was started"
  echo "  code:     $BRANCH @ ${HEAD_SHA:0:8}$([ "$SNAP" = "$HEAD_SHA" ] || echo ' + uncommitted work')"
fi

ssh "$REMOTE" "mkdir -p $(printf %q "$DIR")"
rsync -aq "$JSONL" "$REMOTE:$DIR/"
if [ -d "$DIR/$SESSION_ID" ]; then
  rsync -aq "$DIR/$SESSION_ID/" "$REMOTE:$DIR/$SESSION_ID/"
fi
if [ -d "$HOME/.claude/file-history/$SESSION_ID" ]; then
  ssh "$REMOTE" "mkdir -p ~/.claude/file-history/$SESSION_ID"
  rsync -aq "$HOME/.claude/file-history/$SESSION_ID/" "$REMOTE:.claude/file-history/$SESSION_ID/"
fi

RESUME="dclaude --resume $SESSION_ID"
[ ${#DCLAUDE_ARGS[@]} -eq 0 ] || RESUME="$RESUME$(printf ' %q' "${DCLAUDE_ARGS[@]}")"

if [ "$START" = 0 ]; then
  cat <<EOF

Resume on $REMOTE:

  cvps                          # tmux on the devbox, same cwd
  $RESUME

EOF
  exit 0
fi

rsh "$NAME" "$PWD" "$RESUME" <<'EOF' || die "code and transcript are on $REMOTE, but the session did not start"
name=$1 cwd=$2 cmd=$3
if tmux has-session -t "=$name" 2>/dev/null; then
  if [ "$(tmux display-message -p -t "=$name:" '#{pane_current_command}')" != bash ]; then
    echo "lift: tmux session '$name' on the box is running something: cvps to look" >&2
    exit 1
  fi
  tmux send-keys -t "=$name:" "cd $(printf %q "$cwd") && $cmd" Enter
else
  tmux new-session -d -s "$name" -c "$cwd" "bash -lc $(printf %q "$cmd")"
fi
EOF

echo "  started:  tmux '$NAME' on $REMOTE, Discord thread '$NAME'"
echo "  next:     cvps to attach, land to bring it back"
[ "$ATTACH" = 0 ] || exec ssh -t "$REMOTE" "tmux attach -t $(printf %q "=$NAME")"
