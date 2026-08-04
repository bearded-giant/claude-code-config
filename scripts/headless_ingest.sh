#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: headless_ingest.sh -f <customer-ids-file> [-C <worktree-dir>] [-n] [extra prompt text...]" >&2
  echo "  -f  file of customer ids to ingest (required)" >&2
  echo "  -C  frost worktree to run in (default: \$RC_INGEST_WORKTREE or cwd)" >&2
  echo "  -n  dry-run: print the claude command, do not run" >&2
  exit 64
}

WORKTREE="${RC_INGEST_WORKTREE:-$PWD}"
DRY_RUN=0
IDFILE=""

while getopts "f:C:n" opt; do
  case "$opt" in
    f) IDFILE="$OPTARG" ;;
    C) WORKTREE="$OPTARG" ;;
    n) DRY_RUN=1 ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))

[ -n "$IDFILE" ] || usage
[ -f "$IDFILE" ] || { echo "id file not found: $IDFILE" >&2; exit 66; }

IDFILE_ABS="$(cd "$(dirname "$IDFILE")" && pwd)/$(basename "$IDFILE")"
LOG_DIR="$WORKTREE/.giantmem/ingest-headless"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run-$(date +%Y%m%dT%H%M%S).log"

PROMPT="Invoke the recharge-inactive-ingest skill for the customer ids in $IDFILE_ABS. $*
If a prior run ledger exists for this batch, resume from the last incomplete part instead of restarting.
On transient 5xx, retry the failed part rather than restarting the batch; report which part resumed.
After the run, execute post_ingest_qa.py and print the expected-vs-actual row count table.
Your FINAL output line must be exactly 'INGEST_RESULT: PASS' if every QA check passed, else 'INGEST_RESULT: FAIL'."

CMD=(claude -p "$PROMPT" --allowedTools "Read,Write,Edit,Bash,Glob,Grep,Skill")

if [ "$DRY_RUN" = 1 ]; then
  printf 'cd %q && ' "$WORKTREE"
  printf '%q ' "${CMD[@]}"
  echo
  exit 0
fi

cd "$WORKTREE"
"${CMD[@]}" 2>&1 | tee "$LOG"

if tail -5 "$LOG" | grep -q "INGEST_RESULT: PASS"; then
  echo "ingest PASS ($LOG)"
else
  echo "ingest FAIL or missing result marker ($LOG)" >&2
  exit 1
fi
