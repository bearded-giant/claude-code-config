#!/usr/bin/env bash
# Self-check for wt-carry.sh: two local repos stand in for the laptop and the devbox.
#
# Usage:
#   scripts/test-wt-carry.sh

set -euo pipefail

carry="$(cd "$(dirname "$0")" && pwd)/wt-carry.sh"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

git init -q "$T/a"
cd "$T/a"
git config user.email t@example.com && git config user.name t
echo one > f1; echo two > f2
git add . && git commit -qm init
git clone -q "$T/a" "$T/b"
git -C "$T/b" config user.email t@example.com && git -C "$T/b" config user.name t

send() {
  local from="$T/$1" to="$T/$2" br head snap
  read -r br head snap < <(cd "$from" && "$carry" make)
  [ -n "${snap:-}" ] || fail "make printed nothing in $1"
  git -C "$from" push -q --force "$to" "$head:refs/carry-in/head/$br" "$snap:refs/carry-in/snap/$br"
  (cd "$to" && "$carry" apply "$br")
}
# paths only: staged and unstaged changes both arrive unstaged
state() { (cd "$T/$1" && git rev-parse HEAD && git status --porcelain | cut -c4- | sort && find . -path ./.git -prune -o -type f -print0 | sort -z | xargs -0 shasum); }
same() { [ "$(state a)" = "$(state b)" ] || fail "$1: a and b differ"; }

# commit, modified, deleted, untracked in a new dir, staged new file
(cd "$T/a" && echo c > f3 && git add f3 && git commit -qm c2 && echo mod >> f1 && rm f2 && mkdir d && echo new > d/n && echo staged > s && git add s)
send a b
same "first carry"
[ ! -e "$T/b/f2" ] || fail "deleted file came back on the receiver"
[ "$(cat "$T/b/d/n")" = new ] || fail "untracked file missing on the receiver"

# receiver still holds exactly what was carried: a second carry may overwrite it
(cd "$T/a" && echo more >> f1 && rm d/n)
send a b
same "second carry"

# work on the receiver, then carry back
(cd "$T/b" && git add -A && git commit -qm onbox && echo wip > w)
send b a
same "carry back"
[ "$(cat "$T/a/w")" = wip ] || fail "receiver work missing after carry back"

# receiver has work that was never carried: refuse and touch nothing
(cd "$T/b" && echo local > x)
(cd "$T/a" && echo y >> f1)
if send a b 2>/dev/null; then fail "overwrote uncarried work"; fi
[ "$(cat "$T/b/x")" = local ] || fail "uncarried file destroyed"

# receiver has a commit the sender lacks: refuse and keep HEAD
(cd "$T/b" && git add -A && git commit -qm b-only)
before=$(git -C "$T/b" rev-parse HEAD)
if send a b 2>/dev/null; then fail "applied over a diverged branch"; fi
[ "$(git -C "$T/b" rev-parse HEAD)" = "$before" ] || fail "HEAD moved on a refused apply"

echo ok
