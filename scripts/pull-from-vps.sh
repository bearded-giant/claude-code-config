#!/usr/bin/env bash
# Cross-host git pull: commit any pending VPS-side edits, push, then pull on
# laptop. Lets you treat the VPS as a parallel author without manual scp.
#
# Usage:
#   scripts/pull-from-vps.sh <relative-path-under-~/dev>
#
# Example:
#   scripts/pull-from-vps.sh foo                 # ~/dev/foo on both sides
#   scripts/pull-from-vps.sh foo-feat1           # worktree

set -euo pipefail

REL="${1:-}"
if [ -z "$REL" ]; then
  echo "usage: $(basename "$0") <repo-relative-path>" >&2
  exit 1
fi

VPS_HOST="${VPS_HOST:-claude-vps}"
LAPTOP_DIR="$HOME/dev/$REL"
VPS_DIR="\$HOME/dev/$REL"

if [ ! -d "$LAPTOP_DIR" ]; then
  echo "no laptop dir: $LAPTOP_DIR" >&2
  exit 1
fi

echo "==> checking VPS-side state at $VPS_HOST:$VPS_DIR"
remote_state=$(ssh "$VPS_HOST" bash <<EOF
set -e
cd "$VPS_DIR" 2>/dev/null || { echo "missing:$VPS_DIR"; exit 0; }
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "not-a-git-repo"
  exit 0
fi
status=\$(git status --porcelain)
branch=\$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD)
upstream=\$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo none)
echo "branch=\$branch"
echo "upstream=\$upstream"
if [ -n "\$status" ]; then
  echo "dirty"
  echo "----status----"
  echo "\$status"
else
  echo "clean"
fi
EOF
)

echo "$remote_state"

case "$remote_state" in
  *missing:*) echo "==> nothing to do (VPS path missing)"; exit 0 ;;
  *not-a-git-repo*) echo "==> VPS dir is not a git repo, skipping"; exit 0 ;;
esac

if echo "$remote_state" | grep -q '^clean$'; then
  echo "==> VPS clean, just fetch + pull locally"
else
  echo
  read -r -p "VPS is dirty. Commit + push from VPS? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    read -r -p "Commit message: " msg
    msg="${msg:-pull-from-vps: capture VPS edits}"
    ssh "$VPS_HOST" bash <<EOF
set -e
cd "$VPS_DIR"
git add -A
git commit -m "$msg"
git push
EOF
  else
    echo "==> aborted, no changes committed on VPS"
    exit 1
  fi
fi

echo "==> local pull"
cd "$LAPTOP_DIR"
git pull --ff-only
