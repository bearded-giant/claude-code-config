#!/usr/bin/env bash
# Mutagen session(s) for one repo's .giantmem dirs, laptop <-> devbox. The repo
# is an alias from config/repos.csv or a path; a -wt layout gets one session per
# worktree that exists on both machines.
#
# Usage:
#   scripts/mutagen-sync-giantmem.sh <repo-alias|path> [--recreate]

set -euo pipefail

TARGET="${1:?usage: $(basename "$0") <repo-alias|path> [--recreate]}"
RECREATE="${2:-}"
VPS_HOST="${VPS_HOST:-devbox}"
HERE=$(cd "$(dirname "$0")" && pwd)
CSV="$HERE/../config/repos.csv"

if [ -d "$TARGET" ]; then
  path=$(cd "$TARGET" && pwd)
  alias=$(basename "$path")
else
  alias="$TARGET"
  path=$(python3 - "$CSV" "$TARGET" <<'EOF'
import csv, sys
csv_path, want = sys.argv[1], sys.argv[2].strip().lower()
for names, path, _ in list(csv.reader(open(csv_path)))[1:]:
    if want in [n.strip().lower() for n in names.split("|")]:
        print(path)
        break
EOF
  )
  [ -n "$path" ] || { echo "no repos.csv row for '$TARGET'" >&2; exit 1; }
fi
alias=$(printf '%s' "$alias" | tr -c 'a-zA-Z0-9-' '-')

base="$path"
case "$path" in *-wt/*) base="${path%%-wt/*}-wt" ;; esac
if [ -d "$base/.bare" ]; then
  layout=worktrees
  candidates=()
  for d in "$base"/*/; do
    d="${d%/}"
    [ "$(basename "$d")" = ".bare" ] && continue
    [ -d "$d/.giantmem" ] && candidates+=("$d")
  done
else
  layout=single
  [ -d "$path/.giantmem" ] || { echo "no .giantmem under $path" >&2; exit 1; }
  candidates=("$path")
fi
[ "${#candidates[@]}" -gt 0 ] || { echo "no worktree under $base has a .giantmem" >&2; exit 1; }

# the worktree itself must exist on the devbox; its .giantmem is created
remote_present=$(printf '%s\n' "${candidates[@]}" | ssh "$VPS_HOST" 'while IFS= read -r d; do [ -d "$d" ] && echo "$d"; done; true')

mutagen daemon start >/dev/null 2>&1 || true
created=0
for d in "${candidates[@]}"; do
  if ! grep -qxF "$d" <<<"$remote_present"; then
    echo "==> skip $d: not on $VPS_HOST"
    continue
  fi
  name="gm-$alias"
  [ "$layout" = worktrees ] && name="gm-$alias-$(basename "$d" | tr -c 'a-zA-Z0-9-\n' '-')"
  if mutagen sync list "$name" >/dev/null 2>&1; then
    if [ "$RECREATE" = "--recreate" ]; then
      echo "==> terminating '$name'"
      mutagen sync terminate "$name"
    else
      echo "==> '$name' exists, skipping (--recreate to start over)"
      continue
    fi
  fi
  ssh "$VPS_HOST" "mkdir -p '$d/.giantmem'"
  echo "==> creating '$name': $d/.giantmem <-> $VPS_HOST"
  mutagen sync create --name="$name" \
    --sync-mode=two-way-resolved \
    --symlink-mode=posix-raw \
    --ignore='*.db' --ignore='*.db-*' --ignore='.DS_Store' \
    "$d/.giantmem" "$VPS_HOST:$d/.giantmem"
  created=$((created + 1))
done
echo "created $created session(s); status: mutagen sync list"
