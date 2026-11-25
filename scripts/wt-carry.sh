#!/usr/bin/env bash
# Carry a git worktree's exact state between two machines: the branch tip plus uncommitted and
# untracked work, as a snapshot commit that never touches the index or the branch history.
# make runs on the sending side, apply on the receiving side; lift-to-vps.sh and land-from-vps.sh
# move the refs between them. Staged and unstaged changes both arrive unstaged; ignored files stay behind.
#
# Usage (inside the worktree):
#   scripts/wt-carry.sh make              # writes refs/carry/{head,snap}/<branch>, prints "<branch> <head> <snap>"
#   scripts/wt-carry.sh apply <branch>    # applies refs/carry-in/{head,snap}/<branch>

set -euo pipefail

die() { echo "wt-carry: $*" >&2; exit 1; }

cd "$(git rev-parse --show-toplevel)"

state_tree() {
  local d tree
  d=$(mktemp -d)
  cp "$(git rev-parse --git-path index)" "$d/index" 2>/dev/null || true
  GIT_INDEX_FILE="$d/index" git add -A . >/dev/null
  tree=$(GIT_INDEX_FILE="$d/index" git write-tree)
  rm -rf "$d"
  echo "$tree"
}

make() {
  local branch head tree snap
  branch=$(git symbolic-ref --short -q HEAD) || die "detached HEAD: check out a branch first"
  head=$(git rev-parse HEAD)
  tree=$(state_tree)
  if [ "$tree" = "$(git rev-parse 'HEAD^{tree}')" ]; then
    snap=$head
  else
    snap=$(git commit-tree "$tree" -p "$head" -m "carry snapshot of $branch")
  fi
  git update-ref "refs/carry/head/$branch" "$head"
  git update-ref "refs/carry/snap/$branch" "$snap"
  echo "$branch $head $snap"
}

apply() {
  local branch="$1" in_head in_snap here cur last base dirty=0
  in_head=$(git rev-parse -q --verify "refs/carry-in/head/$branch") || die "nothing was sent for $branch"
  in_snap=$(git rev-parse -q --verify "refs/carry-in/snap/$branch") || die "nothing was sent for $branch"
  here=$(git symbolic-ref --short -q HEAD || true)

  cur=$(state_tree)
  if [ "$cur" != "$(git rev-parse 'HEAD^{tree}')" ]; then
    last=$(git rev-parse -q --verify "refs/carry/snap/$here^{tree}" || true)
    [ "$cur" = "$last" ] || die "$(hostname -s) has uncommitted work in $PWD that was never carried: commit or stash it first"
    dirty=1
  fi
  base=HEAD
  [ "$here" = "$branch" ] || base=$(git rev-parse -q --verify "refs/heads/$branch" || true)
  if [ -n "$base" ] && ! git merge-base --is-ancestor "$base" "$in_head"; then
    die "$branch on $(hostname -s) has commits the sender lacks: push or carry them the other way first"
  fi

  # everything dropped here is held by refs/carry/snap/<branch>, checked above
  if [ "$dirty" = 1 ]; then
    git reset -q --hard HEAD
    git clean -qfd
  fi
  if [ "$here" != "$branch" ]; then
    git switch -q "$branch" 2>/dev/null || git switch -q -c "$branch" "$in_head"
  fi
  git merge -q --ff-only "$in_head"
  [ "$in_snap" = "$in_head" ] || git restore -q --source="$in_snap" --worktree -- .
  git update-ref "refs/carry/head/$branch" "$in_head"
  git update-ref "refs/carry/snap/$branch" "$in_snap"
  git update-ref -d "refs/carry-in/head/$branch"
  git update-ref -d "refs/carry-in/snap/$branch"
}

case "${1:-}" in
  make)  make ;;
  apply) [ -n "${2:-}" ] || die "apply needs a branch"; apply "$2" ;;
  *)     sed -n '2,9p' "$0"; exit 2 ;;
esac
