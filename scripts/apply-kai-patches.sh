#!/usr/bin/env bash
# Reapply local patches to the kai plugin clone after `git pull`.
#
# kai lives at $KAI_DIR (default ~/dev/ai/kai). Each *.patch file under
# kai-patches/ is checked with `git apply --check`; on success, applied.
# Already-applied or upstream-conflicting patches are reported, not retried.

set -euo pipefail

KAI_DIR="${KAI_DIR:-$HOME/dev/ai/kai}"
PATCH_DIR="$(cd "$(dirname "$0")/.." && pwd)/kai-patches"

if [ ! -d "$KAI_DIR/.git" ]; then
  echo "kai clone not a git repo: $KAI_DIR" >&2
  exit 1
fi

if [ ! -d "$PATCH_DIR" ]; then
  echo "patch dir missing: $PATCH_DIR" >&2
  exit 1
fi

shopt -s nullglob
patches=("$PATCH_DIR"/*.patch)
shopt -u nullglob

if [ "${#patches[@]}" -eq 0 ]; then
  echo "no patches in $PATCH_DIR"
  exit 0
fi

echo "==> applying patches in $KAI_DIR"
applied=0 skipped=0 failed=0

for p in "${patches[@]}"; do
  name="$(basename "$p")"

  if git -C "$KAI_DIR" apply --reverse --check "$p" >/dev/null 2>&1; then
    echo "  - $name: already applied"
    skipped=$((skipped + 1))
    continue
  fi

  if ! git -C "$KAI_DIR" apply --check "$p" >/dev/null 2>&1; then
    echo "  ! $name: does not apply cleanly (upstream drift?)" >&2
    failed=$((failed + 1))
    continue
  fi

  git -C "$KAI_DIR" apply "$p"
  echo "  + $name: applied"
  applied=$((applied + 1))
done

echo
echo "summary: $applied applied, $skipped skipped, $failed failed"
[ "$failed" -eq 0 ]
